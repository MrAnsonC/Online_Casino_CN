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

import json
import math
import os
import sys
import random
import tkinter as tk
from functools import lru_cache
from tkinter import messagebox
from tkinter import font as tkfont

BLACKJACK_VERSION = "DOUBLE_BLACKJACK_V8_CLASSIC_UI"

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
# 8-deck Double Blackjack shoe / hand helpers
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

    MIN_BET = 100.0

    # 限红
    MAX_MAIN_BET = 500_000.0
    MAX_SIDE_BET = 100_000.0
    MAX_TABLE_BET = 700_000.0
    MAX_SPLIT_ACTIONS = 0
    MAX_HANDS = 1
    BLACKJACK_PROFIT = 1.5          # non-suited Blackjack 3:2
    SUITED_BLACKJACK_PROFIT = 2.0   # suited Blackjack 2:1
    INSURANCE_PROFIT = 2.0          # insurance profit payout 2:1
    SPLIT_ACES_ONE_CARD_ONLY = False
    SIDE_BET_KEYS = ('Dealer 22', 'Bust!')
    SIDE_BET_LABELS = {
        'Dealer 22': '22点',
        'Bust!': '爆牌！',
    }
    SIDE_BET_ODDS_TEXT = {
        'Dealer 22': '50/20/8:1',
        'Bust!': '250/100/50/9/2/1:1',
    }

    # Shared Classic table geometry; Double keeps one playable hand.
    SEATS = ('Player1',)
    SEAT_NAMES = {'Player1': '玩家'}
    SEAT_BOUNDS = {'Player1': (22.0, 1128.0)}
    ZONE_COLORS = {'Player1': '#35634B'}
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    SIDE_BET_DIAMETER = 122.0 * 2 / 3
    M_CHIP_COLOR = '#102d47'

    # phase_text is intentionally restricted to these five messages only.
    PHASE_BETTING = '无限加倍黑杰克 · 请下注'
    PHASE_INSURANCE = '无限加倍黑杰克 · 保险？'
    PHASE_EVEN_MONEY = '无限加倍黑杰克 · 决策'
    PHASE_PLAYING = '无限加倍黑杰克 · 游戏中'
    PHASE_SETTLING = '无限加倍黑杰克 · 结算中'

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
        # casino_games opts in to treating the shared root-window X as Back.
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
        self.csm_game_id = f"Double_Blackjack:{self.username or 'local'}:{uuid.uuid4().hex}"
        self.csm = ContinuousShuffleMachine()
        self.engine = BlackjackEngine(self.csm, self.csm_game_id)
        self.selected_chip = 1000.0
        self.current_bet = 0.0
        self.current_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
        self.last_bet = 0.0
        self.last_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
        self.last_win_amount = 0.0
        self.show_last_win = False
        self.round_original_bet = 0.0
        self.round_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
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
        self.dealer_hole_revealed = False
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
        self._opening_wager_items = ()
        self.settlement_flash_step = 0
        self.flash_mode = None
        self.flash_winning_side_bets = set()
        self.flash_main_bet = False
        self.flash_main_push_only = False
        # Double Blackjack: a physical-looking 22-point PUSH marker is dealt onto the
        # upper-right of MAIN only when dealer 22 actually pushes a live main hand.
        self.dealer_22_main_push = False
        # V6: main-game settlement is tracked per player hand instead of one
        # global MAIN spot. This lets a losing split hand disappear while other
        # winning split hands keep their own base/double chips and flash.
        self.flash_winning_hand_indices = set()
        self.hand_zone_bounds = []
        # V7: exact positions of each split-hand wager inside the Evoplay MAIN oval.
        # Used both for drawing the 1–4 base chips / Double chip and settlement flash.
        self.main_wager_positions = {}
        self.bet_chip_animation_count = 0
        self.pending_bet_animation = {'MAIN': 0.0, **{key: 0.0 for key in self.SIDE_BET_KEYS}}
        self._closing = False
        self.last_result_lines = []  # internal only; never shown to the player
        self.runtime_data_file = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..',
                'A_Logs',
                'Json',
                'Blackjack_Double.json'
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

        if self.shoe_resumed:
            self.accept_bets = True
            self.canvas.itemconfigure(self.phase_text, text=self.PHASE_BETTING)
            self.update_display()
        else:
            self.after(180, self.start_new_shoe_cut)

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
        c.create_text(575, 18, text='无限加倍黑杰克  DOUBLE BLACKJACK',
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
            text='庄家软17要牌 / 硬17停牌   保险2:1   同花黑杰克2:1 / 黑杰克3:2   庄家22点主注平局',
            font=(self.cn_font, 13, 'bold'), fill=self.GOLD, tags='rule_strip_text')
        self.rule_strip_left_text = c.create_text(545, 224, text='', state='hidden')
        self.rule_strip_right_text = c.create_text(605, 224, text='', state='hidden')
        self.rule_strip_chip_pos = (575, 224)  # legacy helper compatibility
        self.shoe_origin = (575, 52)  # identical to Caribbean Stud's deal origin
        # Keep the existing phase API without adding another visible title.
        self.phase_text = c.create_text(575, 18, text=self.PHASE_BETTING, state='hidden')

    def draw_board(self):
        """Classic's circular betting spots, with Double's two side bets."""
        c = self.canvas
        self.bet_spots, self.side_bet_spots = {}, {}
        radius = self.SIDE_BET_DIAMETER / 2
        positions = {'MAIN': 575.0, 'Dealer 22': 435.0, 'Bust!': 715.0}
        for index, key in enumerate(('MAIN',) + self.SIDE_BET_KEYS):
            x, y = positions[key], 574.0
            bounds, label_pos, chip_pos = self._bet_surface_layout(x, key == 'MAIN')
            tag = 'main_bet_spot' if key == 'MAIN' else f'side_bet_{index-1}'
            fill = '#2677A6' if key == 'MAIN' else '#173B32'
            outline = '#B9D8E8' if key == 'MAIN' else self.GOLD
            shape = self._draw_bet_surface(bounds, fill, outline, tag, key == 'MAIN')
            label = None
            if key != 'MAIN':
                label = c.create_text(*label_pos, text=self.SIDE_BET_LABELS[key],
                    font=(self.cn_font, -14, 'bold'), fill='#F2E6C9',
                    tags=(tag, 'betting_spot_label'))
            spot = dict(key=key, bounds=bounds, label_pos=label_pos, chip_pos=chip_pos,
                rect=shape, label=label, tag=tag, shape='oval' if key == 'MAIN' else 'rounded_rect', normal_fill=fill,
                normal_outline=outline, normal_width=2)
            self.bet_spots[key] = spot
            if spot['shape'] == 'oval':
                self._decorate_main_bet_surface(spot)
            if key == 'MAIN':
                self.bet_spot_bounds, self.bet_spot_rect = bounds, shape
                self.bet_spot_label = label
                c.tag_bind(tag, '<Button-1>', lambda _e: self.place_bet())
                c.tag_bind(tag, '<Button-3>', lambda _e: self.clear_bets())
            else:
                self.side_bet_spots[key] = spot
                c.tag_bind(tag, '<Button-1>', lambda _e, k=key: self.place_side_bet(k))
                c.tag_bind(tag, '<Button-3>', lambda _e, k=key: self.clear_side_bet(k))
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

        # Double has three actions; it does not allow splitting or cashing out.
        specs = (('hit', '要牌', self.hit, '#397A48'),
                 ('stand', '停牌', self.stand, '#FC003F'),
                 ('double', '加倍', self.double, '#A57A36'))
        for index, (action, label, command, color) in enumerate(specs):
            left = 278 + index * 290
            self.action_buttons[action] = self._create_canvas_button(
                left, 638, left+280, 720, label, command, color,
                tag=f'action_{action}', font_size=12)
        for action, left, right, label, accept in (
                ('accept', 405, 565, '购买保险', True),
                ('decline', 585, 745, '不购买', False)):
            self.decision_buttons[action] = self._create_canvas_button(
                left, 642, right, 716, label, lambda a=accept: self._resolve_ace_decision(a),
                '#A57A36' if accept else '#173f66', tag=f'decision_{action}', font_size=12)
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
        """Classic's bottom strip switches between betting, actions and insurance."""
        in_round = bool(in_round or (self.animation_running and not self.accept_bets))
        decision = bool(in_round and self.ace_decision_mode)
        self.canvas.itemconfigure('chip_selector', state='hidden' if in_round else 'normal')
        for button in (self.clear_button, self.repeat_button, self.deal_button, self.info_button):
            self._button_state(button, not in_round)
        for button in self.action_buttons.values():
            self._button_state(button, in_round and not decision)
        for button in self.decision_buttons.values():
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
        self._draw_outcome_rows(self._insurance_chip_rows())
        self.canvas.tag_raise('insurance_chip')

    def _animate_insurance_chip_to_rule(self, on_complete=None):
        sx, sy = self._selected_chip_origin()
        def landed():
            self.insurance_chip_visible = True
            self._render_insurance_chip()
            self.update_display()
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
                # Without a dealer-dependent side wager, Even Money is final immediately.
                # A live 22点 or Bust! wager still requires the ordinary dealer run.
                if not self._has_dealer_dependent_side_wager():
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
                self.animation_running = True
                self.update_display()
                self._queue(100, self._peek_after_ace_decision)
            self._animate_insurance_chip_to_rule(done)
        else:
            self.ace_decision_mode = None
            self.insurance_result = '未购买保险'
            self.animation_running = True
            self.update_display()
            self._queue(100, self._peek_after_ace_decision)


    def _animate_betting_station(self, to_round, on_complete=None):
        # Classic's table stays in place; the wager itself rises to the hand.
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

    @staticmethod
    def _format_profit_odds(odds):
        odds = float(odds)
        if abs(odds - 4.5) < 1e-9:
            return '9:2'
        if abs(odds - 2.5) < 1e-9:
            return '5:2'
        if abs(odds - 1.5) < 1e-9:
            return '3:2'
        return f'{odds:g}:1'

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

    def _animate_selected_chip_to_spot(self, spot_key, on_complete=None):
        """Fly one selected chip from the rack to a betting area in exactly 0.20 s."""
        spot = self.bet_spots.get(spot_key)
        if not spot:
            if callable(on_complete):
                on_complete()
            return
        sx, sy = self._selected_chip_origin()
        tx, ty = spot['chip_pos']
        amount = float(self.selected_chip)
        selected_color = next((color for value, color, _ in self.CHIP_SPECS
                               if float(value) == amount), self.bet_chip_color(amount))
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
        if spot_key == 'MAIN':
            if self.round_active:
                return 0.0
            amount = float(self.current_bet)
        elif self.round_active:
            if spot_key in self.side_bet_early_collected:
                return 0.0
            stake = float(self.round_side_bets.get(spot_key, 0.0))
            if self.settlement_running:
                amount = min(stake, max(0.0, float(self.side_bet_return_amounts.get(spot_key, 0.0))))
            else:
                amount = stake
        else:
            amount = float(self.current_side_bets.get(spot_key, 0.0))
        if not self.round_active:
            amount -= float(self.pending_bet_animation.get(spot_key, 0.0))
        return max(0.0, amount)

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        self._update_main_spot_visibility()
        if self.settlement_visual_stage == 'returning':
            return
        for key, spot in self.bet_spots.items():
            if key == 'MAIN' and self._opening_wager_animation:
                continue
            amount = self._bet_amount_for_spot(key)
            if amount > 0:
                tags = ('bet_chip_dynamic', spot['tag'], 'principal_chip')
                if key == 'MAIN':
                    tags += ('main_bet_chip',)
                self._draw_baccarat_chip(*spot['chip_pos'], amount,
                    tags=tags, radius=self.WAGER_CHIP_RADIUS)
            if self.round_active and key != 'MAIN' and self.settlement_running:
                rows = self._outcome_chip_rows(('side', key),
                    self.round_side_bets.get(key, 0.0), self.side_bet_return_amounts.get(key, 0.0),
                    spot['chip_pos'], self.WAGER_CHIP_RADIUS, ('bet_chip_dynamic', spot['tag']))
                self._draw_outcome_rows([row for row in rows if row['role'] == 'profit'])
        self.canvas.tag_raise('bet_chip_dynamic')

    def _finish_bet_chip_animation(self, spot_key, amount):
        self.pending_bet_animation[spot_key] = max(
            0.0, float(self.pending_bet_animation.get(spot_key, 0.0)) - float(amount))
        self.bet_chip_animation_count = max(0, self.bet_chip_animation_count - 1)
        self.update_display()
        self.save_balance()

    def _restore_betting_spot_label_colors(self):
        for spot in self.bet_spots.values():
            if spot['label'] is not None:
                self.canvas.itemconfigure(spot['label'], fill='#F2E6C9')
        self._set_rule_strip_text_color(self.GOLD)

    def _draw_side_bet_progress_badges(self):
        self.canvas.delete('side_bet_progress_badge')

    def _collect_losing_side_bet_upward(self, key):
        """Collect one resolved losing side-bet chip upward during live play."""
        if key in ('Dealer 22', 'Bust!') or key in self.side_bet_early_collected:
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

        # MAIN settlement remains component-based so base and accumulated Double chips animate independently.
        layout=self._main_split_wager_layout(len(self.hands)) if self.hands else []
        for idx,hand in enumerate(self.hands[:4]):
            if idx>=len(layout): break
            if float(hand.get('base_bet',0.0))>0 and hand.get('base_settlement')=='lose':
                x,y=self._main_base_wager_position(hand, layout[idx]['base']); sources.append((x,y,float(hand['base_bet']),self.WAGER_CHIP_RADIUS))
            if float(hand.get('double_added',0.0))>0 and hand.get('double_settlement')=='lose':
                bets = self._double_bet_amounts(hand)
                positions = self._double_wager_positions(hand, layout[idx]['base'])
                for amount, (x, y) in zip(bets, positions):
                    sources.append((x, y, amount, self.WAGER_CHIP_RADIUS))

        if self.insurance_bet>0.0 and self.insurance_return_amount<=0.0:
            x,y=self.rule_strip_chip_pos; sources.append((x,y,float(self.insurance_bet),self.INSURANCE_CHIP_RADIUS))
        return sources

    def _settlement_return_chip_sources(self):
        return [(*row['pos'],row['amount'],row['radius'])
                for row in self._settlement_chip_rows()]

    def _dealer_22_push_marker_target(self):
        """Put Double's PUSH placard beside the hand, above the betting circles."""
        cx, cy = self._main_split_wager_layout()[0]['base']
        return cx+105.0, cy-65.0

    def _dealer_22_push_marker_source(self):
        return 735.0, 60.0

    def _draw_dealer_22_push_marker_at(self, x, y):
        """Draw the 50x70 white '22点 / 平局' placard at a top-left coordinate."""
        self.canvas.delete('dealer_22_push_marker')
        w, h = 50.0, 70.0
        rect = self.canvas.create_rectangle(
            x, y, x + w, y + h,
            fill='#ffffff', outline='#111111', width=2,
            tags=('dealer_22_push_marker', 'settlement_flash'))
        label = self.canvas.create_text(
            x + w / 2.0, y + h / 2.0,
            text='22点\n平局', justify='center',
            font=(self.cn_font, 12, 'bold'), fill='#111111',
            tags=('dealer_22_push_marker', 'settlement_flash'))
        self.canvas.tag_raise('dealer_22_push_marker')
        return rect, label

    def _animate_dealer_22_push_marker(self, to_table, on_complete=None):
        """Deal/collect the dealer-22 PUSH placard in exactly 0.20 seconds."""
        if to_table and not self.dealer_22_main_push:
            if callable(on_complete):
                on_complete()
            return
        source = self._dealer_22_push_marker_source()
        target = self._dealer_22_push_marker_target()
        start = source if to_table else target
        end = target if to_table else source
        if not to_table and not self.canvas.find_withtag('dealer_22_push_marker'):
            if callable(on_complete):
                on_complete()
            return

        rect, label = self._draw_dealer_22_push_marker_at(*start)
        w, h = 50.0, 70.0
        steps, frame_ms = 10, 20

        def frame(step=1):
            t = min(1.0, step / float(steps))
            # Smooth physical-card travel while retaining the exact 200 ms duration.
            e = t * t * (3.0 - 2.0 * t)
            x = start[0] + (end[0] - start[0]) * e
            y = start[1] + (end[1] - start[1]) * e
            self.canvas.coords(rect, x, y, x + w, y + h)
            self.canvas.coords(label, x + w / 2.0, y + h / 2.0)
            self.canvas.tag_raise('dealer_22_push_marker')
            if step < steps:
                self._queue(frame_ms, frame, step + 1)
            else:
                if not to_table:
                    self.canvas.delete('dealer_22_push_marker')
                else:
                    self.canvas.tag_raise('dealer_22_push_marker')
                if callable(on_complete):
                    on_complete()

        self._queue(frame_ms, frame, 1)

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
        """After flashing, collect the 22 PUSH placard and returned chips in 0.20 s."""
        if not self.settlement_running or self.settlement_visual_stage == 'returning':
            return
        self.canvas.delete('win_flash_area'); self.canvas.delete('side_bet_win_odds')
        self.canvas.delete('side_bet_progress_badge')
        self._restore_betting_spot_label_colors()
        sources=self._settlement_return_chip_sources()
        self.settlement_visual_stage = 'returning'
        # Hide the stationary settlement chips before drawing their travelling clones.
        self.canvas.delete('bet_chip_dynamic'); self.canvas.delete('hand_wager'); self.canvas.delete('insurance_chip')
        self.flash_mode=None
        # The physical 22/PUSH placard is collected upward at the same moment the
        # settlement chips are returned; both animations are exactly 0.20 seconds.
        if self.dealer_22_main_push:
            self._animate_dealer_22_push_marker(False)
        def done():
            # Immediate Blackjack wins were only visually locked earlier. Credit them
            # now, exactly when the winning main/double chips finish returning.
            instant_credit = 0.0
            for hand in self.hands:
                if hand.get('instant_settled') and not hand.get('instant_credit_paid', False):
                    amount = max(0.0, float(hand.get('instant_credit_pending', 0.0)))
                    instant_credit += amount
                    hand['instant_credit_pending'] = 0.0
                    hand['instant_credit_paid'] = True
            if instant_credit > 0.0:
                self.balance += instant_credit
                self.save_balance()
                self.update_display()
            self.settlement_running=False
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

    def place_bet(self):
        if (
            not self.accept_bets
            or self.round_active
            or self.animation_running
            or self.settlement_running
        ):
            return

        selected_amount = float(self.selected_chip)

        remaining_limit = max(
            0.0,
            self.MAX_MAIN_BET - self.current_bet
        )

        # 已经达到主注上限，静默返回
        if remaining_limit <= 1e-9:
            return

        # 实际下注额不能超过主注剩余额度
        amount = min(
            selected_amount,
            remaining_limit
        )

        if self.balance + 1e-9 < amount:
            messagebox.showwarning(
                '余额不足',
                '余额不足以放置该筹码。',
                parent=self.winfo_toplevel()
            )
            return

        # 新下注后恢复显示“本局下注”
        self.show_last_win = False

        # 立即预扣余额，避免快速连续点击造成超额下注
        self.balance -= amount
        self.current_bet += amount

        self.pending_bet_animation['MAIN'] += amount
        self.bet_chip_animation_count += 1

        self.update_display()

        if abs(amount - selected_amount) <= 1e-9:
            self._animate_selected_chip_to_spot(
                'MAIN',
                lambda a=amount: self._finish_bet_chip_animation(
                    'MAIN',
                    a
                )
            )
        else:
            self._animate_amount_chip_to_spot(
                'MAIN',
                amount,
                lambda a=amount: self._finish_bet_chip_animation(
                    'MAIN',
                    a
                )
            )


    def place_side_bet(self, key):
        if (
            key not in self.SIDE_BET_KEYS
            or not self.accept_bets
            or self.round_active
            or self.animation_running
            or self.settlement_running
        ):
            return

        selected_amount = float(self.selected_chip)

        current_side_amount = float(
            self.current_side_bets.get(key, 0.0)
        )

        remaining_side_limit = max(
            0.0,
            self.MAX_SIDE_BET - current_side_amount
        )

        # 已经达到该边注上限，静默返回
        if remaining_side_limit <= 1e-9:
            return

        # 实际下注额不能超过该边注剩余额度
        amount = min(
            selected_amount,
            remaining_side_limit
        )

        current_total = (
            self.current_bet
            + sum(self.current_side_bets.values())
        )

        remaining_table_limit = max(
            0.0,
            self.MAX_TABLE_BET - current_total
        )

        # 如果桌面额度已经全部用完，静默返回
        if remaining_table_limit <= 1e-9:
            return

        # 再受桌面总上限约束
        amount = min(
            amount,
            remaining_table_limit
        )

        if amount <= 1e-9:
            return

        if self.balance + 1e-9 < amount:
            messagebox.showwarning(
                '余额不足',
                '余额不足以放置该筹码。',
                parent=self.winfo_toplevel()
            )
            return

        # 新下注后恢复显示“本局下注”
        self.show_last_win = False

        # 立即扣除实际下注金额
        self.balance -= amount
        self.current_side_bets[key] += amount

        self.pending_bet_animation[key] += amount
        self.bet_chip_animation_count += 1

        self.update_display()

        if abs(amount - selected_amount) <= 1e-9:
            self._animate_selected_chip_to_spot(
                key,
                lambda k=key, a=amount:
                    self._finish_bet_chip_animation(k, a)
            )
        else:
            self._animate_amount_chip_to_spot(
                key,
                amount,
                lambda k=key, a=amount:
                    self._finish_bet_chip_animation(k, a)
            )

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
                or self.settlement_running or self.bet_chip_animation_count > 0):
            return
        refund = self.current_bet + sum(self.current_side_bets.values())
        if refund > 0:
            self.balance += refund
            self.current_bet = 0.0
            self.current_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
            self.pending_bet_animation = {'MAIN': 0.0, **{key: 0.0 for key in self.SIDE_BET_KEYS}}
            self.update_display()
            self.save_balance()

    def repeat_last_bet(self):
        if (not self.accept_bets or self.round_active or self.animation_running
                or self.settlement_running or self.bet_chip_animation_count > 0):
            return
        targets = {'MAIN': self.last_bet, **self.last_side_bets}
        currents = {'MAIN': self.current_bet, **self.current_side_bets}
        additions = {
            key: max(0.0, float(targets[key]) - float(currents.get(key, 0.0)))
            for key in targets
        }
        needed = sum(additions.values())
        if needed <= 0:
            return
        # ================================================================
        # 检查重复下注后的各区域限红
        # ================================================================
        target_main = self.current_bet + additions.get(
            'MAIN',
            0.0
        )

        if target_main > self.MAX_MAIN_BET + 1e-9:
            messagebox.showwarning(
                '无法重复下注',
                '重复下注后主注将超过最高限红 $500,000。',
                parent=self.winfo_toplevel()
            )
            return

        for key in self.SIDE_BET_KEYS:
            target_side = (
                self.current_side_bets.get(
                    key,
                    0.0
                )
                + additions.get(
                    key,
                    0.0
                )
            )

            if target_side > self.MAX_SIDE_BET + 1e-9:
                side_name = self.SIDE_BET_LABELS.get(
                    key,
                    key
                )

                messagebox.showwarning(
                    '无法重复下注',
                    f'{side_name}重复下注后将超过最高限红 $100,000。',
                    parent=self.winfo_toplevel()
                )
                return

        if self.balance + 1e-9 < needed:
            messagebox.showwarning(
                '无法重复下注',
                '余额不足以完成重复下注。',
                parent=self.winfo_toplevel()
            )
            return

        self.show_last_win = False
        # V16: reserve every repeated wager immediately, exactly like a manual
        # click, but hide each added amount until its rack-to-spot flight lands.
        # This prevents both overspending and a premature destination-chip jump.
        for key, add in additions.items():
            if add <= 0.0:
                continue
            self.balance -= add
            if key == 'MAIN':
                self.current_bet += add
            else:
                self.current_side_bets[key] += add
            self.pending_bet_animation[key] += add
            self.bet_chip_animation_count += 1

        self.update_display()
        for key, add in additions.items():
            if add <= 0.0:
                continue
            self._animate_amount_chip_to_spot(
                key, add, lambda k=key, a=add: self._finish_bet_chip_animation(k, a))

    # -------------------------------------------------------------- Double_Blackjack.json
    def save_runtime_store(self, burn_complete=True):
        data = {
            'version': 2,
            'variant': 'Double_Blackjack',
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
        dialog.title('无限加倍黑杰克 · 切牌')
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
            cv.create_text(380,82,text='切开 → 调换 → 合并',font=('微软雅黑',10),fill='#b7d7cf',tags='cut_anim_text')
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
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)

        # V20 burn layout:
        #   row 1: the single face-up burn-value card, centred;
        #   row 2: up to five burned backs, centred;
        #   row 3: the remaining up to five burned backs, centred.
        # Row 2 and row 3 are separated by one full card-height (112 px) of
        # empty space.  A ten-value burn therefore appears as a clean 5 + 5.
        card_w = float(self.CARD_WIDTH)
        card_h = float(self.CARD_HEIGHT)
        gap_x = 15.0
        face_y = 74.0
        row2_y = 285.0
        row3_y = row2_y + card_h * 2.0  # 112px blank gap between the rows

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
        rect = self.canvas.create_rectangle(x, y, x + self.CARD_WIDTH, y + self.CARD_HEIGHT, fill=fill,
                                            outline='#d7cbb9', width=2,
                                            tags=(tag, 'temp_card'))
        if face_up and card is not None:
            suit, rank = card
            symbol = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}.get(suit, suit[:1])
            fg = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
            tid = self.canvas.create_text(x + self.CARD_WIDTH/2, y + self.CARD_HEIGHT/2, text=f'{rank}\n{symbol}',
                                          font=('Arial', 18, 'bold'), fill=fg,
                                          justify='center', tags=(tag, 'temp_card'))
            self.card_items.extend((rect, tid))
        else:
            self.card_items.append(rect)
        return rect
        return rect

    def clear_card_display(self):
        for tag in ('dealt_card','temp_card','hand_label','hand_zone','hand_wager','animation_card'):
            self.canvas.delete(tag)
        self.card_items.clear(); self._temp_flip_images.clear()
        self.previous_round_cards_present = False
        if hasattr(self, 'dealer_total_text'):
            self.canvas.itemconfigure(self.dealer_total_text, text='')

    def _hand_centers(self, count=None):
        n = max(1, int(count if count is not None else len(self.hands) or 1))
        width = (1128.0 - 22.0 - 24.0) / n
        return [34.0 + (i+0.5)*width for i in range(n)]

    def _main_split_wager_layout(self, count=None):
        n = max(1, int(count if count is not None else len(self.hands) or 1))
        result = []
        for index, cx in enumerate(self._hand_centers(n)):
            if index < len(self.hands):
                x, y = self._player_card_target(index, 0)
                anchor = (x+self.CARD_WIDTH/2, y+self.CARD_HEIGHT+self.WAGER_CHIP_RADIUS+self.CARD_WAGER_GAP)
            else:
                anchor = (cx, self.bet_spots['MAIN']['chip_pos'][1]-self.MAIN_WAGER_LIFT)
            result.append({'base': anchor, 'double': (anchor[0]+self.CHIP_PITCH, anchor[1])})
        return result

    def _double_bet_amounts(self, hand):
        """Return each historical Double increment in chronological order."""
        if not hand:
            return []
        bets = [float(v) for v in hand.get('double_bets', ()) if float(v) > 0.0]
        if bets:
            return bets
        legacy = float(hand.get('double_added', 0.0))
        return [legacy] if legacy > 0.0 else []



    def _main_wager_overflow_position(self, anchor_position, number):
        """Wrap extra discs left of the card fan and its total badge."""
        ax, ay = anchor_position
        rightmost = ax-3*self.CHIP_PITCH
        columns = max(1, int((rightmost-22-self.WAGER_CHIP_RADIUS)/self.CHIP_PITCH)+1)
        return (rightmost-(number % columns)*self.CHIP_PITCH,
                ay-(number // columns+1)*self.CHIP_PITCH)

    def _main_wager_sequence_positions(self, hand, anchor_position):
        count = 1+len(self._double_bet_amounts(hand))
        ax, ay = anchor_position
        columns = max(1, int((1128-self.WAGER_CHIP_RADIUS-ax)/self.CHIP_PITCH)+1)
        return [(ax+index*self.CHIP_PITCH, ay) if index < columns else
                self._main_wager_overflow_position(anchor_position, index-columns)
                for index in range(count)]

    def _main_sequence_profit_position(self, anchor_position, number, wager_count):
        ax, ay = anchor_position
        left_columns = max(1, int((ax-22-self.WAGER_CHIP_RADIUS)/self.CHIP_PITCH))
        if number < left_columns:
            return ax-(number+1)*self.CHIP_PITCH, ay
        right_columns = max(1, int((1128-self.WAGER_CHIP_RADIUS-ax)/self.CHIP_PITCH)+1)
        offset = max(0, wager_count-right_columns)+number-left_columns
        return self._main_wager_overflow_position(anchor_position, offset)


    def _main_base_wager_position(self, hand, anchor_position):
        """Current position of the original MAIN chip after repeated Doubles."""
        return self._main_wager_sequence_positions(hand, anchor_position)[0]

    def _double_wager_positions(self, hand, anchor_position):
        """Current positions of Double increments, oldest to newest, left to right."""
        return self._main_wager_sequence_positions(hand, anchor_position)[1:]

    def blackjack_profit_odds(self, hand):
        cards = list(hand.get('cards', ())) if hand else []
        if not BlackjackEngine.is_blackjack(cards):
            return None
        return (self.SUITED_BLACKJACK_PROFIT
                if cards[0][0] == cards[1][0]
                else self.BLACKJACK_PROFIT)

    def _component_return_amount(self, hand, component):
        """Return the displayed settlement amount for one base/Double chip."""
        if component == 'base':
            amount = float(hand.get('base_bet', 0.0))
            state = hand.get('base_settlement')
        else:
            amount = float(hand.get('double_added', 0.0))
            state = hand.get('double_settlement')
        if amount <= 0.0 or not state:
            return 0.0
        if state == 'instant_win':
            # Immediate Blackjack wins keep the wager chips on the table, but each
            # chip displays its own full return (stake + profit) before settlement.
            odds = float(hand.get('instant_profit_odds') or 0.0)
            return amount * (1.0 + odds)
        if state == 'win':
            bj_odds = self.blackjack_profit_odds(hand)
            return amount * (1.0 + bj_odds) if bj_odds is not None else amount * 2.0
        if state in ('push', 'refund'):
            return amount
        if state == 'cashout':
            stake = self.hand_stake(hand)
            total_return = float(hand.get('settlement_return', 0.0))
            return (total_return * amount / stake) if stake > 0 else 0.0
        return 0.0

    def _draw_main_hand_wagers(self):
        self.main_wager_positions = {}
        if not self.round_active or self._opening_wager_animation:
            return
        layout = self._main_split_wager_layout(len(self.hands))
        rows = self._main_wager_rows()
        for index, hand in enumerate(self.hands):
            positions = self._main_wager_sequence_positions(hand, layout[index]['base'])
            self.main_wager_positions[index] = dict(base=positions[0], double=positions[1:],
                show_base=any(row['key'][1:3] == (index, 'base') for row in rows),
                show_double=any(row['key'][1:3] == (index, 'double') for row in rows))
        self._draw_outcome_rows(rows)

    def _player_card_target(self, hand_index, card_index):
        """Classic's fixed first card and rising card fan."""
        n = max(1, len(self.hands))
        width = (1128.0 - 22.0 - 24.0) / n
        right = 34.0 + (hand_index+1)*width
        cx = self._hand_centers()[hand_index]
        first_x = cx - self.CARD_WIDTH/2
        first_y = self.bet_spots['MAIN']['chip_pos'][1] - self.MAIN_WAGER_LIFT - self.CARD_HEIGHT - self.WAGER_CHIP_RADIUS - self.CARD_WAGER_GAP
        step = min(44.0, max(0.0, (right-8-first_x-self.CARD_WIDTH)/3))
        index = max(0, int(card_index))
        double_indices = self.hands[hand_index].get('double_card_indices', ())
        # Preserve the regular fan, compressing only very long hands to fit the table.
        count = max(index+1, len(self.hands[hand_index]['cards']))
        edge_width = self.CARD_WIDTH
        if double_indices:
            edge_width += (self.CARD_HEIGHT-self.CARD_WIDTH)/2
        step = min(step, max(0.0, (right-8-first_x-edge_width)/max(1, count-1)))
        if index <= 3:
            y = first_y - 24.0*index
        elif index <= 6:
            y = first_y - 72.0 + 24.0*(index-3)
        else:
            y = max(286.0, first_y - 24.0*(index-6))
        y = max(286.0, y)
        x = first_x + step*index
        if index in double_indices:
            # Rotate about the card's centre, preserving the fan's anchor.
            offset = (self.CARD_HEIGHT-self.CARD_WIDTH)/2
            x -= offset
            y += offset
        return x, y

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
        """Classic's badge geometry, showing only the upcard until the hole is flipped."""
        if not self.dealer_cards:
            return
        cards = self.dealer_cards if self.dealer_hole_revealed else self.dealer_cards[:1]
        card_x, card_y = self._dealer_card_target(len(self.dealer_cards)-1)
        tip_x, y = card_x+self.CARD_WIDTH+6, card_y+self.CARD_HEIGHT/2
        box_left, box_right = tip_x+10, tip_x+62
        total, soft = BlackjackEngine.hand_value(cards)
        natural = self.dealer_hole_revealed and BlackjackEngine.is_blackjack(cards)
        fill = '#000000' if natural else self._dealer_badge_fill()
        self.canvas.create_polygon(tip_x, y, box_left, y-18, box_right, y-18,
            box_right, y+18, box_left, y+18, fill=fill, outline='',
            tags=('hand_label', 'dealer_total_badge'))
        self.canvas.create_text((box_left+box_right)/2, y,
            text=self._hand_total_badge_text(cards, blackjack=natural,
                soft_stand=bool(self.dealer_hole_revealed and soft and total >= 18)),
            font=(self.cn_font, 12, 'bold'), fill='#FFFFFF' if natural else '#111111',
            tags=('hand_label', 'dealer_total_badge'))

    def _draw_amount_chip(self, cx, cy, amount, label='', behind=False):
        self._draw_baccarat_chip(cx, cy, amount, tags=('hand_wager',),
                                 force_color='#5b2f79' if behind else None)
        if label:
            self.canvas.create_text(cx,cy+self.WAGER_CHIP_RADIUS+9,text=label,
                font=(self.cn_font,-12,'bold'),fill='#ffe898',tags=('hand_wager',))

    def render_cards(self):
        for tag in ('dealt_card', 'hand_label', 'hand_zone', 'hand_wager'):
            self.canvas.delete(tag)
        for index, card in enumerate(self.dealer_cards):
            x, y = self._dealer_card_target(index)
            if index == 1 and not self.dealer_hole_revealed:
                self._draw_single_temp_card(card, x, y, 'dealer_hole_card', face_up=False)
                self.canvas.addtag_withtag('dealt_card', 'dealer_hole_card')
            else:
                self._render_card(card, x, y, tags=('dealt_card', 'dealer_dealt_card'))
        self._draw_dealer_total_badge()
        self.hand_zone_bounds = []
        width = (1128.0-22.0-24.0)/max(1, len(self.hands))
        for index, hand in enumerate(self.hands):
            left, right = 34.0+index*width, 34.0+(index+1)*width
            self.hand_zone_bounds.append((left, 256, right, 534))
            for j, card in enumerate(hand['cards']):
                self._render_card(card, *self._player_card_target(index, j),
                    tags=('dealt_card', 'player_dealt_card', f'player_card_{index}_{j}'),
                    rotation=90 if j in hand.get('double_card_indices', ()) else 0)
            self._draw_hand_total_badge(index, left, right)
        self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._raise_visible_bottom_controls(self.round_active)
        self._raise_wager_chips()

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
            'double_bets': [],
            'double_count': 0,
            'double_card_indices': [],
            'contains_original': bool(contains_original),
            'from_split': bool(from_split),
            'split_aces': bool(split_aces),
            'needs_split_draw': bool(needs_split_draw),
            'status': 'active',
            'result': '',
            'cashout_credit': 0.0,
            # Component-level settlement is kept for the existing chip animation.
            'settlement': None,
            'base_settlement': None,
            'double_settlement': None,
            'settlement_return': 0.0,
            # Blackjack can settle immediately after the player's second card.
            'instant_settled': False,
            'instant_profit_odds': None,
            'instant_credit_pending': 0.0,
            'instant_credit_paid': False,
        }

    @staticmethod
    def hand_stake(hand):
        return float(hand.get('base_bet', 0.0)) + float(hand.get('double_added', 0.0))

    def _instant_rule_for_hand(self, hand):
        """Only a true two-card Blackjack is an immediate main-bet win."""
        if not hand or hand.get('instant_settled'):
            return None
        odds = self.blackjack_profit_odds(hand)
        if odds is None:
            return None
        suited = hand['cards'][0][0] == hand['cards'][1][0]
        label = '同花Blackjack 2:1（立刻结算）' if suited else 'Blackjack 3:2（立刻结算）'
        return odds, label

    def _try_instant_main_settlement(self, hand):
        """Lock an immediate Blackjack win now; credit it after settlement flash."""
        rule = self._instant_rule_for_hand(hand)
        if rule is None:
            return False
        profit_odds, label = rule
        stake = self.hand_stake(hand)
        credit = stake * (1.0 + float(profit_odds))
        hand['status'] = 'instant_settled'
        hand['instant_settled'] = True
        hand['instant_profit_odds'] = float(profit_odds)
        hand['instant_credit_pending'] = credit
        hand['instant_credit_paid'] = False
        hand['settlement'] = 'instant_win'
        hand['base_settlement'] = 'instant_win'
        hand['double_settlement'] = 'instant_win' if hand.get('double_added', 0.0) > 0 else None
        hand['settlement_return'] = credit
        hand['result'] = f'{label} +{self.format_money(credit - stake)}'
        self.last_result_lines.append(
            f'手{self.hands.index(hand)+1 if hand in self.hands else "?"}：{label}，'
            f'待返还 {self.format_money(credit)}')
        # Deliberately do NOT change balance here. The main/double chips immediately
        # show the return amount and are credited when their settlement flight ends.
        return True

    def deal_cards(self):
        if (not self.accept_bets or self.round_active or self.animation_running
                or self.settlement_running or self.bet_chip_animation_count > 0):
            return
        if self.current_bet + 1e-9 < self.MIN_BET:
            messagebox.showwarning('最低下注', f'最低下注为 {self.format_money(self.MIN_BET)}。',
                                   parent=self.winfo_toplevel()); return
        if self.engine.remaining_cards() < 30:
            messagebox.showerror('自动洗牌机', '目前可用牌不足 30 张，请稍后再试。',
                                 parent=self.winfo_toplevel()); return
        try:
            self.engine.start_round()
        except (CSMError, OSError, RuntimeError) as exc:
            messagebox.showerror('自动洗牌机', f'无法开始牌局：{exc}',
                                 parent=self.winfo_toplevel()); return

        # Reserve the existing MAIN Canvas items before a display refresh can
        # delete them. These same items travel from the betting circle to the hand.
        self._opening_wager_items = tuple(self.canvas.find_withtag('main_bet_chip'))
        self._opening_wager_animation = True
        for item in self._opening_wager_items:
            self.canvas.dtag(item, 'bet_chip_dynamic')
            self.canvas.dtag(item, self.bet_spots['MAIN']['tag'])
            self.canvas.addtag_withtag('opening_wager', item)
        self.accept_bets=False; self.animation_running=True
        self._set_button(self.deal_button, False)
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
        self.update_display()
        # Switch the bottom strip as soon as Enter/click starts the hand.
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
        self.round_active=True
        self.last_bet=self.current_bet; self.last_side_bets=dict(self.current_side_bets)
        self.round_original_bet=self.current_bet; self.round_side_bets=dict(self.current_side_bets)
        self.current_bet=0.0; self.current_side_bets={key:0.0 for key in self.SIDE_BET_KEYS}
        self.insurance_bet=0.0; self.insurance_result=''; self.insurance_return_amount=0.0
        self.insurance_chip_visible=False; self.flash_insurance_rule=False; self.ace_decision_mode=None
        self.split_actions=0; self.dealer_cards=[]; self.dealer_hole_revealed=False; self.round_deal_sequence=[]; self.side_bet_results={}
        self.side_bet_return_amounts={}; self.side_bet_hit_odds={}; self.side_bet_hit_labels={}
        self.side_bet_early_collected=set()
        self.flash_winning_side_bets=set(); self.flash_main_bet=False; self.flash_main_push_only=False
        self.dealer_22_main_push=False
        self.canvas.delete('dealer_22_push_marker')
        self.flash_winning_hand_indices=set(); self.settlement_running=False; self.settlement_flash_step=0
        self.dealer_phase_active=False
        self.flash_mode=None
        self.settlement_visual_stage=None; self.pending_profit_chips=set()
        self.hands=[self.new_hand(base_bet=self.round_original_bet,contains_original=True)]
        self.active_hand_index=0; self.last_result_lines=[]
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
        self._set_round_control_visibility(True)
        # The reserved source chip stays visible until it arrives at the hand.
        # Suppress destination wager rendering throughout that movement.
        self.render_cards(); self.update_display(); self._raise_visible_bottom_controls(True)

        sequence = ('D_UP', 'P', 'D_HOLE')
        def deal_step(index=0):
            if index >= len(sequence):
                self.animation_running = False
                self.render_cards()
                self._after_initial_deal()
                return
            who = sequence[index]
            if who == 'P':
                self._deal_player_card_animated(
                    0, on_complete=lambda: self._queue(80, deal_step, index + 1))
            elif who == 'D_UP':
                self._deal_dealer_card_animated(
                    on_complete=lambda: self._queue(80, deal_step, index + 1), face_up=True)
            else:
                self._deal_dealer_card_animated(
                    on_complete=lambda: self._queue(80, deal_step, index + 1), face_up=False)
        self._animate_starting_wagers(lambda: deal_step(0))

    def _after_initial_deal(self):
        self._settle_initial_side_bets()
        if len(self.dealer_cards) < 2:
            return
        up_rank = self.dealer_cards[0][1]
        if up_rank in ('10', 'J', 'Q', 'K'):
            # Ten-value upcard: peek immediately for an Ace hole card.
            self.animation_running = True
            self.update_display()
            self._queue(120, self._peek_ten_value_upcard)
            return
        if up_rank == 'A':
            # Insurance decision happens before the Ace-upcard Blackjack peek.
            self._show_ace_decision('insurance')
            self.update_display()
            return
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
        self.update_display()

    def _reveal_dealer_hole(self, on_complete=None):
        """Visibly flip the already-dealt dealer hole card in place."""
        if self.dealer_hole_revealed or len(self.dealer_cards) < 2:
            self.dealer_hole_revealed = True
            self.render_cards(); self.update_display()
            if callable(on_complete):
                on_complete()
            return

        card = self.dealer_cards[1]
        tx, ty = self._dealer_card_target(1)

        # Hide the permanent card back first.  The temporary animation card is
        # deliberately raised above every dealt-card layer so the opening motion
        # is visible both during the initial peek and at the normal dealer turn.
        try:
            self.canvas.itemconfigure('dealer_hole_card', state='hidden')
        except tk.TclError:
            pass

        back = self.external_back_image
        if back is not None:
            card_id = self.canvas.create_image(
                tx, ty, image=back, anchor='nw',
                tags=('dealer_hole_reveal_animation', 'animation_card'))
        else:
            card_id = self.canvas.create_rectangle(
                tx, ty, tx + self.CARD_WIDTH, ty + self.CARD_HEIGHT, fill='#253e66',
                outline='#d7c46a', width=2,
                tags=('dealer_hole_reveal_animation', 'animation_card'))
        self.canvas.tag_raise('dealer_hole_reveal_animation')

        # About half a second: back collapses to its centre line, then the face
        # expands out.  The slower timing makes this a clear opening animation
        # rather than an almost-instant image replacement.
        half_steps = 9
        frame_ms = 28

        def flip_step(step=0):
            if self._closing:
                return
            total_steps = half_steps * 2
            if step > total_steps:
                self.canvas.delete('dealer_hole_reveal_animation')
                self._temp_flip_images.pop(card_id, None)
                self.dealer_hole_revealed = True
                self.render_cards(); self.update_display()
                if callable(on_complete):
                    on_complete()
                return

            if step <= half_steps:
                ratio = 1.0 - step / float(half_steps)
                use_back = True
            else:
                ratio = (step - half_steps) / float(half_steps)
                use_back = False

            width = max(2, int(self.CARD_WIDTH * ratio))
            x = tx + (self.CARD_WIDTH - width) / 2.0
            if self.canvas.type(card_id) == 'image':
                image = self._create_scaled_flip_image(card, width, self.CARD_HEIGHT, use_back=use_back)
                if image is not None:
                    self._temp_flip_images[card_id] = image
                    self.canvas.itemconfigure(card_id, image=image)
                    self.canvas.coords(card_id, x, ty)
            else:
                self.canvas.coords(card_id, x, ty, x + width, ty + self.CARD_HEIGHT)
                self.canvas.itemconfigure(
                    card_id, fill='#253e66' if use_back else '#f4efe4',
                    outline='#d7c46a' if use_back else '#d7cbb9')

            self.canvas.tag_raise('dealer_hole_reveal_animation')
            self._queue(frame_ms, flip_step, step + 1)

        flip_step(0)

    def _peek_ten_value_upcard(self):
        if not self.round_active or len(self.dealer_cards) < 2:
            return
        dealer_bj = self.dealer_cards[1][1] == 'A'
        if dealer_bj:
            self.dealer_phase_active = True
            self.canvas.itemconfigure(self.phase_text, text=self.PHASE_SETTLING)
            self._reveal_dealer_hole(
                on_complete=lambda: self._queue(220, self._resolve_dealer_blackjack))
            return
        self.animation_running = False
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
        self.render_cards()
        self.update_display()

    def _peek_after_ace_decision(self):
        if not self.round_active or len(self.dealer_cards) < 2:
            return
        dealer_bj = self.dealer_cards[1][1] in ('10', 'J', 'Q', 'K')
        if dealer_bj:
            self.dealer_phase_active = True
            self.animation_running = True
            self.canvas.itemconfigure(self.phase_text, text=self.PHASE_SETTLING)
            self._reveal_dealer_hole(
                on_complete=lambda: self._queue(220, self._resolve_dealer_blackjack))
            return
        self.animation_running = False
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
        self.render_cards()
        self.update_display()
        self._raise_visible_bottom_controls(True)

    def _deal_player_card_animated(self, hand_index, on_complete=None, rotation=0):
        if not (0 <= hand_index < len(self.hands)):
            if callable(on_complete): on_complete()
            return
        hand=self.hands[hand_index]
        card=self.draw_round_card(); card_index=len(hand['cards']); hand['cards'].append(card)
        if rotation % 180:
            hand.setdefault('double_card_indices', []).append(card_index)
        tx,ty=self._player_card_target(hand_index,card_index)
        def done():
            self.canvas.delete('round_animation_card')
            self.render_cards(); self.update_display()
            if callable(on_complete): on_complete()
        self._animate_card_from_shoe(card,tx,ty,on_complete=done,flip=True,
                                     tag='round_animation_card',rotation=rotation)

    def _deal_dealer_card_animated(self, on_complete=None, face_up=True):
        card = self.draw_round_card()
        card_index = len(self.dealer_cards)
        self.dealer_cards.append(card)
        tx, ty = self._dealer_card_target(card_index)
        def done():
            self.canvas.delete('round_animation_card')
            self.canvas.delete('burn_card')
            self.render_cards()
            self.update_display()
            if callable(on_complete):
                on_complete()
        if face_up:
            self._animate_card_from_shoe(
                card, tx, ty, on_complete=done, flip=True, tag='round_animation_card')
        else:
            self._animate_back_from_shoe(tx, ty, on_complete=done)

    def _prepare_active_split_hand(self, on_ready=None):
        hand=self.active_hand()
        if not hand or not hand.get('needs_split_draw',False):
            if callable(on_ready): on_ready()
            return
        hand['needs_split_draw']=False
        self.animation_running=True
        def after_draw():
            total,_=BlackjackEngine.hand_value(hand['cards'])
            if total>21:
                hand['status']='bust'; hand['result']='爆牌'
            elif self._try_instant_main_settlement(hand):
                pass
            elif hand.get('split_aces',False):
                # Exactly one card after a split Ace. Another Ace is the sole
                # exception and remains active so the player can re-split it.
                if len(hand['cards'])==2 and hand['cards'][1][1]=='A' and self.can_split(hand):
                    hand['status']='active'; hand['result']='分A后再A：可继续分牌'
                else:
                    hand['status']='stood'; hand['result']='分A一张停牌'
            self.animation_running=False; self.render_cards(); self.update_display()
            if hand['status']!='active': self._queue(180,self._advance_hand)
            elif callable(on_ready): on_ready()
        self._deal_player_card_animated(self.active_hand_index,on_complete=after_draw)

    def active_hand(self):
        if not self.round_active or not (0 <= self.active_hand_index < len(self.hands)):
            return None
        return self.hands[self.active_hand_index]

    def can_hit(self, hand):
        return bool(hand and hand['status'] == 'active'
                    and BlackjackEngine.hand_value(hand.get('cards', ()))[0] < 21)

    def can_stand(self, hand):
        # A player must have at least two cards before STAND is available.
        return bool(hand and hand['status'] == 'active'
                    and len(hand.get('cards', ())) >= 2)

    def can_double(self, hand):
        if not hand or hand['status'] != 'active':
            return False
        cards = hand.get('cards', ())
        total, _ = BlackjackEngine.hand_value(cards)
        # Special rule: when the PLAYER'S FIRST card is Ace, Double is allowed
        # only once for that hand. Hit has no corresponding count restriction.
        if cards and cards[0][1] == 'A' and int(hand.get('double_count', 0)) >= 1:
            return False
        current_stake = self.hand_stake(hand)
        return bool(total < 21 and current_stake > 0.0
                    and self.balance + 1e-9 >= current_stake)

    def can_split(self, hand):
        return False

    def can_surrender(self, hand):
        return False

    def hit(self):
        hand = self.active_hand()
        if not self.can_hit(hand) or self.animation_running:
            return
        self.animation_running = True
        self.update_display(); self._raise_visible_bottom_controls(True)
        def after():
            total, _ = BlackjackEngine.hand_value(hand['cards'])
            if total > 21:
                hand['status'] = 'bust'; hand['result'] = '爆牌'
            elif self._try_instant_main_settlement(hand):
                pass
            elif total == 21:
                hand['status'] = 'stood'; hand['result'] = '21点停牌'
            self.animation_running = False
            self.render_cards(); self.update_display()
            if hand['status'] != 'active':
                self._queue(220, self._advance_hand)
        self._deal_player_card_animated(self.active_hand_index, on_complete=after)

    def stand(self):
        hand = self.active_hand()
        if not self.can_stand(hand) or self.animation_running:
            return
        hand['status'] = 'stood'
        hand['result'] = '停牌'
        self.render_cards()
        self.update_display()
        self._advance_hand()

    def double(self):
        hand = self.active_hand()
        if not self.can_double(hand) or self.animation_running:
            return
        # If the player's FIRST card is Ace, this Double is terminal: after the
        # one Double card is dealt, the hand automatically stands.
        ace_first_double = bool(hand.get('cards') and hand['cards'][0][1] == 'A')
        self.animation_running = True
        for button in self.action_buttons.values():
            self._set_button(button, False)
        self._raise_visible_bottom_controls(True)

        # Each press truly doubles the CURRENT hand stake. Repeated doubles are allowed.
        add = self.hand_stake(hand)
        self.balance -= add
        hand['double_added'] += add
        hand.setdefault('double_bets', []).append(add)
        hand['double_count'] = int(hand.get('double_count', 0)) + 1
        self.save_balance()
        self.render_cards(); self.update_display()

        def after():
            total, _ = BlackjackEngine.hand_value(hand['cards'])
            if total > 21:
                hand['status'] = 'bust'; hand['result'] = '加倍后爆牌'
            elif self._try_instant_main_settlement(hand):
                pass
            elif total == 21:
                hand['status'] = 'stood'; hand['result'] = '加倍后21点停牌'
            elif ace_first_double:
                hand['status'] = 'stood'; hand['result'] = 'Ace加倍后自动停牌'
            else:
                hand['status'] = 'active'
                hand['result'] = f'已加倍 ×{hand.get("double_count", 1)}'
            self.animation_running = False
            self.render_cards(); self.update_display()
            if hand['status'] != 'active':
                self._queue(220, self._advance_hand)
            else:
                self._raise_visible_bottom_controls(True)

        self._deal_player_card_animated(self.active_hand_index, on_complete=after, rotation=90)

    def split(self):
        # Split is not available in Double Blackjack.
        return

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
        # Full 52-card rank distribution: A, 2..9, and four ten-value ranks.
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
        """Infinite-deck full-deck H17 dealer distribution: 17..21,22,23+ bust."""
        total=int(total); soft=bool(soft)
        if total >= 22:
            arr=[0.0]*7
            arr[5 if total == 22 else 6] = 1.0
            return tuple(arr)
        if total>17 or (total==17 and not soft):
            arr=[0.0]*7; arr[total-17]=1.0; return tuple(arr)
        outcomes=[(11,1/13)]+[(v,1/13) for v in range(2,10)]+[(10,4/13)]
        result=[0.0]*7
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
        # Dealer 22 is a PUSH; only 23+ busts are outright wins.
        stand_win = ddist[6] + sum(ddist[:max(0, total - 17)])
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
        # Cash out / surrender is not available in Double Blackjack.
        return

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
        # Spanish shoe has no rank-10 cards, so sequences crossing the missing
        # ten use 8-9-J and 9-J-Q as valid consecutive three-card straights.
        if vals in ([8, 9, 11], [9, 11, 12]):
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
        odds_text = self._format_profit_odds(odds)
        if stake > 0.0:
            credit = stake * (1.0 + odds)
            self.balance += credit
            self.side_bet_return_amounts[key] = credit
            self.side_bet_results[key] = f'{label} {odds_text} +{self.format_money(credit - stake)}'
        else:
            self.side_bet_return_amounts[key] = 0.0
            self.side_bet_results[key] = f'{label} {odds_text}'

    @staticmethod
    def _lucky_queen_result(player_cards):
        """Lucky Queen/Royal Match: suited Q+K, otherwise any suited first two cards."""
        if len(player_cards) < 2:
            return (None, '资料不足')
        p0, p1 = player_cards[:2]
        suited = p0[0] == p1[0]
        royal = suited and {p0[1], p1[1]} == {'Q', 'K'}
        if royal:
            return (25, '皇家同花 Q+K')
        if suited:
            return (2.5, '同花')
        return (None, '未中')

    def _settle_initial_side_bets(self):
        # Double Blackjack keeps only dealer-dependent 22点 and 爆牌 side bets.
        return

    def _settle_dealer_22_side_bet(self):
        """Dealer 22 side bet: dealer must finish on exactly 22.

        Payout priority uses every dealer card:
        all same suit 50:1; otherwise all same colour 20:1; otherwise mixed colour 8:1.
        """
        key = 'Dealer 22'
        if key in self.side_bet_results:
            return
        total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        if total != 22:
            self._credit_side_bet(key, None, '庄家非22点')
            self.save_balance()
            return

        suits = {card[0] for card in self.dealer_cards}
        colours = {
            'red' if card[0] in ('Diamond', 'Heart') else 'black'
            for card in self.dealer_cards
        }
        if len(suits) == 1:
            odds, label = 50, '22点·全部牌同花'
        elif len(colours) == 1:
            odds, label = 20, '22点·全部牌同色'
        else:
            odds, label = 8, '22点·杂色'
        self._credit_side_bet(key, odds, label)
        self.save_balance()

    def _settle_bust_side_bet(self):
        key = 'Bust!'
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

    def _has_dealer_22_wager(self):
        return float(self.round_side_bets.get('Dealer 22', 0.0)) > 0.0

    def _has_dealer_dependent_side_wager(self):
        return self._has_bust_wager() or self._has_dealer_22_wager()

    def _settle_dealer_dependent_side_bets(self):
        self._settle_dealer_22_side_bet()
        self._settle_bust_side_bet()

    def _all_hands_bust_or_surrendered(self):
        if not self.hands:
            return False
        for hand in self.hands:
            total, _ = BlackjackEngine.hand_value(hand.get('cards', ()))
            if hand.get('status') in ('surrendered', 'instant_settled'):
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
        if not self.round_active or self._has_dealer_dependent_side_wager():
            return
        # The one-card dealer cannot be bust; record Bust! as a non-hit even when
        # there was no wager, matching the existing settlement bookkeeping.
        self._settle_dealer_dependent_side_bets()
        self.last_result_lines.append('Even Money 1:1；庄家不抽第二张牌')
        self._finish_round(dealer_bj=False)

    def _resolve_finished_hands_after_insurance_probe(self):
        """Legacy compatibility helper; normal Double Blackjack uses the pre-player hole-card peek."""
        dealer_bj = BlackjackEngine.is_blackjack(self.dealer_cards[:2])
        self._settle_dealer_dependent_side_bets()
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
            if hand.get('status') in ('surrendered', 'instant_settled'):
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

        dealer_side_wager = self._has_dealer_dependent_side_wager()
        all_dead = self._all_hands_bust_or_surrendered()

        # If every player wager is already resolved and no dealer-dependent side bet
        # is live, there is no need to expose or draw the dealer hand.
        if not dealer_side_wager and all_dead:
            self.dealer_phase_active = True
            self.animation_running = True

            self.canvas.itemconfigure(
                self.phase_text,
                text=self.PHASE_SETTLING
            )

            self.render_cards()
            self.update_display()

            def after_bust_hole_reveal():
                if not self.round_active:
                    return

                # 暗牌翻开后才正式结算玩家爆牌，
                # 主注会在正常 settlement 流程中被收走。
                self._queue(220, self._resolve_normal_round)

            self._reveal_dealer_hole(
                on_complete=after_bust_hole_reveal
            )
            return

        self.dealer_phase_active = True
        self.animation_running = True
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
        self.render_cards(); self.update_display()

        def after_hole_reveal():
            dealer_bj = BlackjackEngine.is_blackjack(self.dealer_cards[:2])
            if dealer_bj:
                self._queue(220, self._resolve_dealer_blackjack)
            else:
                self._queue(220, self._dealer_draw_until_done)

        self._reveal_dealer_hole(on_complete=after_hole_reveal)

    def _dealer_draw_until_done(self):
        total,soft=BlackjackEngine.hand_value(self.dealer_cards)
        # H17: hit soft 17, but stand on hard 17 and every 18+ total.
        if total < 17 or (total == 17 and soft):
            self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
            self._deal_dealer_card_animated(on_complete=lambda:self._queue(180,self._dealer_draw_until_done))
            return
        self._queue(260,self._resolve_normal_round)

    def _resolve_dealer_blackjack(self):
        dealer_bj = True
        self.dealer_hole_revealed = True
        self.dealer_phase_active = True
        self._settle_dealer_dependent_side_bets()
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
            if hand.get('status') in ('instant_settled', 'even_money'):
                lines.append(f'手{idx + 1}：{hand.get("result", "")}'.rstrip('：'))
                continue
            stake = self.hand_stake(hand)
            natural = BlackjackEngine.is_blackjack(hand.get('cards', ()))
            if natural:
                self.balance += stake
                hand['settlement'] = 'push'
                hand['base_settlement'] = 'push'
                hand['double_settlement'] = 'push' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = stake
                hand['result'] = 'Blackjack Push'
                lines.append(f'手{idx + 1}：Blackjack Push')
            else:
                hand['settlement'] = 'lose'
                hand['base_settlement'] = 'lose'
                hand['double_settlement'] = 'lose' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = 0.0
                hand['result'] = f'庄家Blackjack -{self.format_money(stake)}'
                lines.append(f'手{idx + 1}：庄家Blackjack，输 {self.format_money(stake)}')

        self.last_result_lines.extend(lines)
        self._finish_round(dealer_bj=dealer_bj)

    def _resolve_normal_round(self):
        self._settle_dealer_dependent_side_bets()
        dealer_total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        dealer_bust = dealer_total > 21
        dealer_22 = dealer_total == 22
        self.dealer_22_main_push = False
        lines = [f'庄家 {dealer_total}' + (' 爆牌' if dealer_bust else '')]

        if self.insurance_bet > 0:
            self.insurance_return_amount = 0.0
            self.insurance_result = f'保险输 -{self.format_money(self.insurance_bet)}'
            lines.append(self.insurance_result)

        for idx, hand in enumerate(self.hands):
            if hand['status'] in ('surrendered', 'even_money', 'instant_settled'):
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
                odds = self.blackjack_profit_odds(hand) or self.BLACKJACK_PROFIT
                credit = stake * (1.0 + odds)
                self.balance += credit
                hand['settlement'] = 'win'
                hand['base_settlement'] = 'win'
                hand['double_settlement'] = 'win' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = credit
                label = '同花Blackjack 2:1' if odds == self.SUITED_BLACKJACK_PROFIT else 'Blackjack 3:2'
                hand['result'] = f'{label} +{self.format_money(credit - stake)}'
                lines.append(f'手{idx + 1}：{label}')
            elif dealer_22:
                # Dealer 22: unresolved main wagers push. Blackjack already settled stays paid.
                self.balance += stake
                hand['settlement'] = 'push'
                hand['base_settlement'] = 'push'
                hand['double_settlement'] = 'push' if hand.get('double_added', 0.0) > 0 else None
                hand['settlement_return'] = stake
                hand['result'] = '庄家22点 Push'
                self.dealer_22_main_push = True
                lines.append(f'手{idx + 1}：庄家22点 Push')
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
        PUSH, returned wager components, side-bet credits and insurance
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
        """Show Classic's steady principal/profit payout using Double's settled amounts."""
        self.animation_running = False
        self.save_balance()
        self.last_win_amount = self._calculate_last_win_amount()
        self.show_last_win = True
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_SETTLING)
        self.flash_winning_side_bets = set(self.side_bet_hit_odds)
        self.flash_winning_hand_indices = {
            i for i, hand in enumerate(self.hands) if hand.get('settlement_return', 0.0) > 0}
        self.flash_main_bet = bool(self.flash_winning_hand_indices)
        self.flash_main_push_only = self.flash_main_bet and all(
            self.hands[i].get('settlement') == 'push' for i in self.flash_winning_hand_indices)
        self.flash_insurance_rule = bool(dealer_bj and self.insurance_return_amount > 0)
        self.settlement_running = True
        self.settlement_visual_stage = 'paying'
        self.settlement_flash_step = 0
        self.flash_mode = None
        profits = [row for row in self._settlement_chip_rows() if row['role'] == 'profit']
        self.pending_profit_chips.update(row['key'] for row in profits)
        self.render_cards()
        self.update_display()

        def display_outcome():
            self.settlement_visual_stage = 'display'
            self._render_settlement_chips()
            self._queue(1800, self._finish_flash_with_chip_return)

        def start_payout():
            self._animate_losing_chips_out()
            if self.dealer_22_main_push:
                self._animate_dealer_22_push_marker(True)
            if not profits:
                self._queue(300, display_outcome)
                return
            remaining = [len(profits)]
            def arrived(row):
                self.pending_profit_chips.discard(row['key'])
                self._render_settlement_chips()
                remaining[0] -= 1
                if not remaining[0]:
                    display_outcome()
            for index, row in enumerate(profits):
                self._animate_settlement_chips([(575, 43, row['amount'], row['radius'])],
                    row['pos'], 440, f'settlement_profit_fly_{index}',
                    lambda r=row: arrived(r))
        self._queue(80, start_payout)

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
        self.canvas.delete('dealer_22_push_marker')
        self._set_rules_strip_visible(False)

        self.settlement_visual_stage=None; self.pending_profit_chips=set()
        self._opening_wager_animation=False
        self._opening_wager_items=()
        self.round_active=False; self.round_original_bet=0.0
        self.round_side_bets={key:0.0 for key in self.SIDE_BET_KEYS}
        self.side_bet_results={}; self.side_bet_return_amounts={}
        self.side_bet_hit_odds={}; self.side_bet_hit_labels={}
        self.side_bet_early_collected=set()
        self.flash_winning_side_bets=set(); self.flash_main_bet=False; self.flash_main_push_only=False
        self.dealer_22_main_push=False
        self.flash_winning_hand_indices=set(); self.flash_insurance_rule=False
        self.settlement_running=False; self.settlement_flash_step=0; self.flash_mode=None
        self.dealer_phase_active=False
        self.round_deal_sequence=[]; self.insurance_bet=0.0; self.insurance_result=''
        self.insurance_return_amount=0.0; self.insurance_chip_visible=False; self.ace_decision_mode=None
        self.hands=[]; self.dealer_cards=[]; self.dealer_hole_revealed=False; self.active_hand_index=0; self.split_actions=0

        def after_layout():
            self._set_round_control_visibility(False); self.canvas.itemconfigure('chip_selector',state='normal')
            self._raise_visible_bottom_controls(False); self.select_chip(self.selected_chip)
            self.save_runtime_store(burn_complete=True)
            self.accept_bets=True; self.canvas.itemconfigure(self.phase_text,text=self.PHASE_BETTING)
            self.update_display(); self._set_round_control_visibility(False); self._raise_visible_bottom_controls(False)
        self._animate_betting_station(False,on_complete=after_layout)

    def _hand_short_status(self, hand):
        mapping = {
            'bust': '爆',
            'blackjack': 'BJ',
            'even_money': 'Even',
            'instant_settled': '已结',
        }
        return mapping.get(hand.get('status'), '')

    def update_display(self):
        if self._closing: return
        self.canvas.itemconfigure(self.balance_text,text=f'余额: ${int(self.balance):,}')
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

        can_bet=(self.accept_bets and not self.round_active and not self.animation_running and not self.settlement_running)
        pending_any=self.current_bet>0 or any(v>0 for v in self.current_side_bets.values())
        prev_any=self.last_bet>0 or any(v>0 for v in self.last_side_bets.values())
        no_chip_flying=self.bet_chip_animation_count==0
        self._set_button(self.clear_button,can_bet and pending_any and no_chip_flying)
        self._set_button(self.repeat_button,can_bet and prev_any and no_chip_flying)
        self._set_button(self.deal_button,can_bet and no_chip_flying and self.current_bet>=self.MIN_BET)

        if self.ace_decision_mode=='insurance':
            self._set_button(self.decision_buttons.get('accept'),
                             self.balance+1e-9>=self.round_original_bet/2.0,'购买保险')
            self._set_button(self.decision_buttons.get('decline'),True,'不购买')

        self._set_round_control_visibility(self.round_active)
        hand=self.active_hand()
        active=bool(self.round_active and not self.animation_running and not self.settlement_running
                    and not self.ace_decision_mode and hand and hand['status']=='active'
                    and not hand.get('needs_split_draw',False))
        self._set_button(self.action_buttons.get('hit'), active and self.can_hit(hand), '要牌')
        self._set_button(self.action_buttons.get('stand'), active and self.can_stand(hand), '停牌')
        self._set_button(self.action_buttons.get('double'), active and self.can_double(hand), '加倍')
        for _key,spot in self.bet_spots.items():
            self.canvas.itemconfigure(spot['rect'],fill=spot['normal_fill'])
        self._update_main_spot_visibility()

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

        dialog.title('无限加倍21点 · 游戏说明')

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
                        '8副完整52张牌 · 洞牌 · H17',
                        [
                            ('起手派牌顺序', '庄家明牌1张 → 玩家1张 → 庄家底牌1张。\n第二张庄家牌以牌背朝上放置。'),
                            ('10点值明牌会检查暗牌', '庄家明牌为10 / J / Q / K时，立刻检查底牌是否A。\n若是A，底牌打开，庄家以黑杰克结束本局。'),
                            ('庄家明牌A / 保险', '玩家先选择购买保险或不购买；\n之后庄家检查底牌是否10点值。\n若为黑杰克，底牌打开，庄家以黑杰克结束本局。'),
                            ('玩家黑杰克', '玩家最初两张牌合计21点为黑杰克：同花赔率2:1；\n非同花赔率3:2。'),
                        ],
                        [],
                    ],
                    [
                        '玩家决策按钮',
                        '只使用 要牌 / 停牌 / 加倍',
                        [
                            ('要牌  HIT', '可连续要牌，没有次数限制\n爆牌或到21点后结束玩家行动。'),
                            ('停牌  STAND', '玩家至少拥有2张牌后才可停牌\n停牌后进入庄家回合。'),
                            ('加倍  DOUBLE', '每次追加“当前整手下注额”并补1张牌\n非首张A的手，补牌后仍可继续选择操作。'),
                            ('连续Double金额', '主注100示例：追加100 → 200\n→ 400 → 800 → 1600 ……'),
                            ('庄家底牌 / 翻牌', '10点值或A明牌会先检查底牌\n需要公开时以翻牌动画打开。'),
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
                                    ['主注', '$100–$500,000'],
                                    ['22点', '每项最高$100,000'],
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
                        '主注、保险与Double',
                        '赔率表示利润赔率；\n正常中奖同时返还下注本金',
                        [],
                        [
                            (
                                '主注 / 保险',
                                ['条件', '赔率'],
                                [
                                    ['普通主注获胜', '1:1'],
                                    ['玩家Blackjack：同花', '2:1'],
                                    ['玩家Blackjack：非同花', '3:2'],
                                    ['庄家最终正好22点：尚未提前结算的主注', '退还 / Push'],
                                    ['保险中奖（庄家Blackjack）', '2:1'],
                                    ['保险金额', '原始主注 × 1/2'],
                                    ['首次Double追加', '当前整手下注 × 1'],
                                    ['后续每次Double追加', '当时当前整手下注 × 1'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '边注赔付表',
                        '仅保留22点 / 爆牌 · 利润赔率',
                        [],
                        [
                            (
                                '22点',
                                ['条件', '赔率'],
                                [
                                    ['庄家正好22且全部牌同花', '50:1'],
                                    ['庄家正好22且全部牌同色', '20:1'],
                                    ['庄家正好22且杂色', '8:1'],
                                ],
                            ),
                            (
                                '爆牌！',
                                ['条件', '赔率'],
                                [
                                    ['庄家8张或以上爆牌', '250:1'],
                                    ['庄家7张爆牌', '100:1'],
                                    ['庄家6张爆牌', '50:1'],
                                    ['庄家5张爆牌', '9:1'],
                                    ['庄家4张爆牌', '2:1'],
                                    ['庄家3张爆牌', '1:1'],
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
                            ('比较方法', 'A 可计 1 或 11，J、Q、K 计 10；\n加倍与边注只按本变体的赔率表结算。'),
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
                        '8副完整52张牌 · 洞牌 · H17',
                        [
                            ('连续洗牌机', '使用8副完整52张牌，共416张，并由CSM_Shuffler连续发牌；\n点数10、J、Q、K全部保留并按10点计算。'),
                        ],
                        [],
                    ],
                    [
                        '玩家决策按钮',
                        '只使用 要牌 / 停牌 / 加倍',
                        [
                            ('首张A的特别限制', '若玩家第一张牌是A，加倍后只补1张牌\n操作结束后就庄家动作。'),
                        ],
                        [],
                    ],
                    [
                        '重要提示',
                        '',
                        [
                            ('使用洞牌', '庄家在玩家行动前已经拥有一张盖住的底牌，这是洞牌流程。'),
                            ('首张A：Double后自动停牌', '玩家第一张牌是A时，可以选择要牌，这样无任何限制\n选择加倍，只补1张牌后立即自动停牌，之后不可再有任何玩家操作。'),
                            ('连续加倍是指数式追加', '例如初始主注100：第一次追加100；\n下一次追加当前总注200；\n再追加400、800、1600……。\n每次追加后都会补1张牌；\n首张A选择加倍属于例外，补牌后自动停牌。'),
                            ('加倍筹码位置', '每次加倍时，新一笔加倍筹码追加在已有的主注/加倍筹码右侧，并始终保持下注时间顺序。'),
                            ('庄家22点的两个效果', '庄家最终正好22点时：未结算的主注平局；\n同时“22点”边注按花色/颜色档位结算。\n22点也属于爆牌，因此“爆牌！”边注按最终张数结算。'),
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

        tk.Label(header, text='无限加倍21点 · 游戏说明', font=(font_name, 20, 'bold'),

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
        """In casino_games embedded mode, make the shared root-window X return to casino_games."""
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

            # casino_games calls this only after replace_page() has completed.
            # force=True re-asserts the handler at Tk idle in case the host deferred
            # its own WM_DELETE_WINDOW setup until after the page replacement.
            top.protocol('WM_DELETE_WINDOW', self.exit_game)
        except tk.TclError:
            if not self._embedded_wm_delete_installed:
                self._embedded_wm_delete_previous = None
            self._embedded_wm_delete_installed = False

    def _restore_host_bindings(self):
        """Restore the shared root handlers before returning to casino_games."""
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
                if hand.get('instant_settled'):
                    if not hand.get('instant_credit_paid', False):
                        unresolved += max(0.0, float(hand.get('instant_credit_pending', 0.0)))
                    continue
                if hand.get('status') not in ('surrendered', 'even_money'):
                    unresolved += self.hand_stake(hand)
            unresolved += self.insurance_bet
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
        self._restore_host_bindings()
        if callable(self.on_back):
            self.on_back(self.final_balance)


    @staticmethod
    def _shade_color(color, factor):
        rgb = [max(0, min(255, round(int(color[i:i+2], 16)*factor))) for i in (1, 3, 5)]
        return '#' + ''.join(f'{value:02x}' for value in rgb)


    def _raise_wager_chips(self):
        """Keep every displayed wager above cards, labels, and table controls."""
        self.canvas.tag_raise('wager_chip')


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


    def _render_settlement_chips(self):
        self.update_bet_chips()
        self.canvas.delete('hand_wager')
        self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._raise_wager_chips()


    def _update_main_spot_visibility_original(self):
        playing = bool(self.round_active or self.settlement_running or
                       (self.animation_running and not self.accept_bets))
        self.canvas.itemconfigure(self.bet_spots['MAIN']['rect'],
                                  state='hidden' if playing else 'normal')

    def _update_main_spot_visibility(self):
        self._update_main_spot_visibility_original()
        for spot in self.bet_spots.values():
            if spot.get('shape') == 'oval' and spot.get('surface_tag'):
                state = self.canvas.itemcget(spot['rect'], 'state')
                self.canvas.itemconfigure(spot['surface_tag'], state=state)
                self.canvas.itemconfigure(spot['title_tag'], state=state)
        self._raise_wager_chips()


    def _main_wager_rows(self):
        if not self.round_active or self._opening_wager_animation:
            return []
        rows = []
        layout = self._main_split_wager_layout(len(self.hands))
        for index, hand in enumerate(self.hands):
            bets = [float(hand.get('base_bet', 0.0)), *self._double_bet_amounts(hand)]
            positions = self._main_wager_sequence_positions(hand, layout[index]['base'])
            settled = bool(self.settlement_running or hand.get('instant_settled'))
            total_double = sum(bets[1:])
            for number, (stake, position) in enumerate(zip(bets, positions)):
                component = 'base' if number == 0 else 'double'
                returned = None
                if settled:
                    returned = self._component_return_amount(hand, component)
                    if number and total_double > 0:
                        returned *= stake/total_double
                # Principal stays in its chronological row. Profits queue to the left.
                profit_position = self._main_sequence_profit_position(layout[index]['base'], number, len(bets))
                rows.extend(self._outcome_chip_rows(('main', index, component, number),
                    stake, returned, position, self.WAGER_CHIP_RADIUS,
                    ('hand_wager', f'hand_wager_{index}', f'{component}_wager'),
                    profit_position=profit_position))
        return rows


    def _animate_starting_wagers(self, on_complete):
        self._opening_wager_animation = True
        x, y = self.bet_spots['MAIN']['chip_pos']
        tx, ty = self._main_split_wager_layout()[0]['base']
        def landed():
            self.canvas.delete('opening_wager')
            self._opening_wager_items = ()
            self._opening_wager_animation = False
            self.render_cards()
            self.update_display()
            on_complete()
        if not self._opening_wager_items:
            landed()
            return
        previous = [0.0]
        steps, frame_ms = 11, 20
        def frame(step=1):
            t = min(1.0, step/steps)
            eased = 1.0-(1.0-t)**2
            delta = eased-previous[0]
            previous[0] = eased
            self.canvas.move('opening_wager', (tx-x)*delta, (ty-y)*delta)
            self._raise_wager_chips()
            if step < steps:
                self._queue(frame_ms, frame, step+1)
            else:
                landed()
        self._queue(frame_ms, frame, 1)


    def _insurance_chip_rows(self):
        if not self.insurance_chip_visible or self.insurance_bet <= 0:
            return []
        returned = self.insurance_return_amount if self.settlement_running else None
        return self._outcome_chip_rows(('insurance', 'Player1'), self.insurance_bet,
            returned, self.rule_strip_chip_pos, self.INSURANCE_CHIP_RADIUS, ('insurance_chip',))


    def _dealer_badge_fill(self):
        if not self.dealer_hole_revealed:
            return '#ffffff'
        total, _ = BlackjackEngine.hand_value(self.dealer_cards)
        if total > 21:
            return '#b9dcff' if self.dealer_22_main_push else '#e34848'
        if self.settlement_running and self.hands:
            results = [hand.get('settlement') for hand in self.hands]
            if all(result == 'push' for result in results):
                return '#b9dcff'
            if all(result == 'lose' for result in results):
                return '#b9efb4'
            if all(result in ('win', 'instant_win') for result in results):
                return '#e34848'
        return '#f2b0b0' if self.dealer_phase_active else '#ffffff'


    def _settlement_chip_rows(self):
        rows = self._main_wager_rows()
        for key in self.SIDE_BET_KEYS:
            rows.extend(self._outcome_chip_rows(('side', key),
                self.round_side_bets.get(key, 0.0), self.side_bet_return_amounts.get(key, 0.0),
                self.bet_spots[key]['chip_pos'], self.WAGER_CHIP_RADIUS, ('bet_chip_dynamic', self.bet_spots[key]['tag'])))
        rows.extend(self._insurance_chip_rows())
        return rows


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

    if parent is not None and not isinstance(parent, tk.Misc):
        legacy_balance = parent
        legacy_user = balance if isinstance(balance, str) and user is None else user
        parent = None
        balance = legacy_balance
        user = legacy_user

    if parent is not None:
        return BubbleBlackjackGame(
            parent=parent,
            balance=balance,
            user=user,
            on_back=on_back,
            on_balance_change=on_balance_change,
            close_returns_to_parent=close_returns_to_parent,
        )

    root = tk.Tk()
    root.title('无限加倍21点')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)

    def close_standalone(_final_balance):
        try:
            root.destroy()
        except tk.TclError:
            pass

    game = BubbleBlackjackGame(
        parent=root,
        balance=balance,
        user=user,
        on_back=on_back or close_standalone,
        on_balance_change=on_balance_change,
    )
    game.pack(fill=tk.BOTH, expand=True)
    root.protocol('WM_DELETE_WINDOW', game.exit_game)
    root.mainloop()
    return game


if __name__ == '__main__':
    main(balance=10_000_000)
