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

BLACKJACK_VERSION = "Free Blackjack V9-PEEK-CLASSIC-UI"

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
# 8-deck Blackjack shoe / hand helpers (initial dealer hole-card peek)
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

    PLAYER_ZONE_COLOR = '#35634B'
    PUSH_BLUE = '#b9dcff'
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    SIDE_BET_DIAMETER = 122.0 * 2 / 3

    MIN_BET = 100.0

    # 独立限红
    MAX_MAIN_BET = 500_000.0
    MAX_SIDE_BET = 100_000.0
    MAX_SPLIT_ACTIONS = 3       # casino-style maximum 4 player hands
    MAX_HANDS = 4
    BLACKJACK_PROFIT = 1.5      # 3:2
    INSURANCE_PROFIT = 2.0      # 2:1
    SPLIT_ACES_ONE_CARD_ONLY = True
    SIDE_BET_KEYS = ('Perfect Pair', '21+3', 'Golden Bucket', 'Dealer 22', 'Hot 21', 'Bust!')
    SIDE_BET_LABELS = {
        'Perfect Pair': '完美对子',
        '21+3': '21+3',
        'Golden Bucket': '黄金桶',
        'Dealer 22': '22点',
        'Hot 21': '热辣21',
        'Bust!': '爆牌！',
    }
    SIDE_BET_ODDS_TEXT = {
        'Perfect Pair': '25/12/6:1',
        '21+3': '100/40/30/10/5:1',
        'Golden Bucket': '1000/299/100/60/30/10/3:1',
        'Dealer 22': '50/20/8:1',
        'Hot 21': '500/100/20/4/2/1:1',
        'Bust!': '250/100/50/9/2/1:1',
    }

    M_CHIP_COLOR = '#102d47'
    FREE_CHIP_COLOR = '#d8aa2d'
    FREE_BUTTON_BG = '#e7d36c'
    FREE_BUTTON_FG = '#111111'

    # phase_text is intentionally restricted to these five messages only.
    PHASE_BETTING = '免费黑杰克 · 请下注'
    PHASE_INSURANCE = '免费黑杰克 · 保险？'
    PHASE_EVEN_MONEY = '免费黑杰克 · 立刻赔付？'
    PHASE_PLAYING = '免费黑杰克 · 游戏中'
    PHASE_SETTLING = '免费黑杰克 · 结算中'

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
        self.csm_game_id = f"Free_Double_Blackjack:{self.username or 'local'}:{uuid.uuid4().hex}"
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
        self.ace_decision_mode = None  # None / 'insurance' / 'even_money'
        self.bet_layout_mode = 'home'
        self.previous_round_cards_present = False
        self.hands = []
        self.active_hand_index = 0
        self.dealer_cards = []
        self.dealer_hole_hidden = False
        self.dealer_blackjack_checked = False
        self.dealer_blackjack_found = False
        self.dealer_blackjack_resolved = False
        self.insurance_resolved = False
        self.insurance_early_collected = False
        self.round_deal_sequence = []
        self.side_bet_results = {}
        self.side_bet_return_amounts = {}
        # Record actual side-bet tiers for result bookkeeping and cash payouts.
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
        self._free_rule_flash_actions = frozenset()
        self._free_rule_flash_bright = False
        self._free_rule_flash_job = None
        # Fade the dealer notice only when dealer 22 pushes a live hand.
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
        # winning split hands keep their own base/double chips and left-side profits.
        self.flash_winning_hand_indices = set()
        self.hand_zone_bounds = []
        # Track each hand's base/Double chips below its first card, as in Classic.
        # FREE components retain their own drawing and settlement conversion.
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
                'Blackjack_Free_Double.json'
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
        c.create_text(575, 18, text='免费黑杰克  FREE DOUBLE BLACKJACK',
                      font=(self.cn_font, 16, 'bold'), fill=self.GOLD, tags='static')
        self.dealer_zone_rect = c.create_rectangle(
            355, 44, 795, 197, fill='#4b1e22', outline='', tags='static')
        c.create_text(575, 57, text='庄家', font=(self.cn_font, 16, 'bold'),
                      fill='#F2E6C9', tags='static')
        self.player_zone_home = self.player_zone_round = (22.0, 252.0, 1128.0, 617.0)
        self.player_label_home = self.player_label_round = (575.0, 266.0)
        self.player_zone_mode = 'home'
        self.player_zone_rect = c.create_rectangle(
            *self.player_zone_home, fill=self.PLAYER_ZONE_COLOR, outline='', tags='static')
        self.player_zone_title = c.create_text(
            *self.player_label_home, text='玩家', font=(self.cn_font, 16, 'bold'),
            fill='#F2E6C9', tags='static')

        # Classic's three-column limit table sits to the left of the dealer.
        c.create_rectangle(30, 75, 349, 181, fill=self.PANEL, outline=self.GOLD, tags='static')
        c.create_rectangle(30, 75, 349, 104, fill='#40634B', outline=self.GOLD, tags='static')
        c.create_text(189.5, 89, text='下注上限', font=(self.cn_font, 13, 'bold'),
                      fill='#F2E6C9', tags='static')
        for col, (label, amount) in enumerate((('主注最低', self.MIN_BET),
                                               ('主注最高', self.MAX_MAIN_BET),
                                               ('边注最高', self.MAX_SIDE_BET))):
            left, right = 30 + col * 319 / 3, 30 + (col + 1) * 319 / 3
            c.create_rectangle(left, 104, right, 141, outline='#77906B', tags='static')
            c.create_rectangle(left, 141, right, 181, outline='#77906B', tags='static')
            c.create_text((left + right) / 2, 122, text=label,
                          font=(self.cn_font, 11, 'bold'), fill='#F2E6C9', tags='static')
            c.create_text((left + right) / 2, 161, text=f'${amount:,.0f}',
                          font=(self.cn_font, 12, 'bold'), fill=self.GOLD, tags='static')

        # Keep both FREE descriptions permanently visible on the dealer's right.
        # These positions also remain the origins of the gold FREE-chip animations.
        c.create_rectangle(808, 75, 1128, 181, fill=self.PANEL, outline=self.GOLD,
                           tags=('static', 'free_rules_panel'))
        c.create_rectangle(808, 75, 1128, 104, fill='#40634B', outline=self.GOLD,
                           tags=('static', 'free_rules_panel'))
        c.create_text(968, 89, text='免费玩法说明', font=(self.cn_font, 13, 'bold'),
                      fill='#F2E6C9', tags=('static', 'free_rules_panel'))
        self.rule_split_bar_bounds = (814.0, 107.0, 1122.0, 140.0)
        self.rule_double_bar_bounds = (814.0, 145.0, 1122.0, 178.0)
        for kind, bounds, wording in (
                ('split', self.rule_split_bar_bounds, '玩家对子 A–9 免费分牌'),
                ('double', self.rule_double_bar_bounds, '玩家硬 9–11 免费加倍')):
            x0, y0, x1, y1 = bounds
            center = ((x0 + x1) / 2, (y0 + y1) / 2)
            rect = c.create_rectangle(*bounds, fill=self.FREE_BUTTON_BG,
                outline='#FFF1B3', tags=('static', 'free_rule_bar'))
            label = c.create_text(*center, text=wording, font=(self.cn_font, 11, 'bold'),
                fill=self.FREE_BUTTON_FG, tags=('static', 'free_rule_bar_text'))
            setattr(self, f'rule_{kind}_bar_rect', rect)
            setattr(self, f'rule_{kind}_bar_text', label)
            setattr(self, f'rule_{kind}_bar_center', center)

        self.dealer_total_text = c.create_text(575, 193, text='', state='hidden')
        # Retain the phase item for existing round logic; the Classic title stays fixed.
        self.phase_text = c.create_text(575, 18, text=self.PHASE_BETTING, state='hidden')
        self.rule_strip_bounds = (22.0, 200.0, 1128.0, 248.0)
        self.rule_strip_rect = c.create_rectangle(*self.rule_strip_bounds,
            fill='#173C2E', outline='#65784B', tags='round_rule_strip')
        c.create_line(25, 201, 1125, 201, fill='#E0C879', width=2, tags='round_rule_strip')
        c.create_line(25, 247, 1125, 247, fill='#0C241B', width=2, tags='round_rule_strip')
        self.rule_strip_text = c.create_text(575, 224,
            text='庄家先查黑杰克   软17要牌 / 硬17停牌   保险2:1   黑杰克3:2   庄家22点主注平局   最多分牌3次',
            font=(self.cn_font, 13, 'bold'), fill=self.GOLD,
            tags=('round_rule_strip', 'rule_strip_text'))
        self.rule_strip_left_text = c.create_text(545, 224, text='', state='hidden')
        self.rule_strip_right_text = c.create_text(605, 224, text='', state='hidden')
        self.rule_strip_chip_pos = (575.0, 224.0)
        self.shoe_origin = (575.0, 52.0)

    def draw_board(self):
        """Use Classic's seven fixed circles while retaining Free Double's side bets."""
        c = self.canvas
        radius = self.SIDE_BET_DIAMETER / 2
        centers = {'MAIN': 575.0, **dict(zip(
            self.SIDE_BET_KEYS, (135.0, 285.0, 435.0, 715.0, 865.0, 1015.0)))}
        self.bet_spots, self.side_bet_spots = {}, {}
        for index, (kind, cx) in enumerate(centers.items()):
            bounds, label_pos, chip_pos = self._bet_surface_layout(cx, kind == 'MAIN')
            tag = 'main_bet_spot' if kind == 'MAIN' else f'side_bet_{index - 1}'
            fill = '#175C98' if kind == 'MAIN' else '#173B32'
            outline = '#19345D' if kind == 'MAIN' else self.GOLD
            shape = self._draw_bet_surface(bounds, fill, outline, tag, kind == 'MAIN')
            # An empty MAIN label keeps the original single-player canvas contract.
            label = c.create_text(*label_pos, text='' if kind == 'MAIN' else self.SIDE_BET_LABELS[kind],
                font=(self.cn_font, -14, 'bold'), fill='#F2E6C9',
                tags=(tag, 'betting_spot_label'))
            spot = dict(key=kind, bounds=bounds, label_pos=label_pos, chip_pos=chip_pos,
                rect=shape, label=label, tag=tag, shape='oval' if kind == 'MAIN' else 'rounded_rect', normal_fill=fill,
                normal_outline=outline, normal_width=0 if kind == 'MAIN' else 2, normal_label_fill='#F2E6C9')
            self.bet_spots[kind] = spot
            if spot['shape'] == 'oval':
                self._decorate_main_bet_surface(spot)
            if kind == 'MAIN':
                self.bet_spot_bounds, self.bet_spot_rect, self.bet_spot_label = bounds, shape, label
                c.tag_bind(tag, '<Button-1>', lambda _e: self.place_bet())
                c.tag_bind(tag, '<Button-3>', lambda _e: self.clear_bets())
            else:
                self.side_bet_spots[kind] = spot
                c.tag_bind(tag, '<Button-1>', lambda _e, k=kind: self.place_side_bet(k))
                c.tag_bind(tag, '<Button-3>', lambda _e, k=kind: self.clear_side_bet(k))
            c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
            c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))
        layout = {key: (spot['bounds'], spot['label_pos'], spot['chip_pos'])
                  for key, spot in self.bet_spots.items()}
        self.bet_layout_home = self.bet_layout_round = layout
        self.bet_layout_mode = 'home'
        self.update_bet_chips()

    def draw_bottom_controls(self):
        c = self.canvas
        c.create_rectangle(0, 625, 1150, 748, fill=self.BG, outline=self.PANEL_LINE,
                           width=2, tags='controls')
        self.balance_text = c.create_text(10, 665, anchor='w', text='',
            font=(self.cn_font, 18, 'bold'), fill='white', tags='controls')
        self.total_bet_text = c.create_text(10, 710, anchor='w', text='',
            font=(self.cn_font, 18, 'bold'), fill='white', tags='controls')
        self.clear_button = self._create_canvas_button(278, 650, 344, 704, '清除',
            self.clear_bets, '#9B403A', tag='control_clear', font_size=11)
        diameter, gap = 56, 8
        chip_x = (self.WIDTH - (len(self.CHIP_SPECS) * diameter +
                   (len(self.CHIP_SPECS) - 1) * gap)) / 2
        for value, color, label in self.CHIP_SPECS:
            tag = f'chip_select_{value}'
            outer = c.create_oval(chip_x, 646, chip_x + 56, 702, fill='#182F25',
                outline=self.PANEL_LINE, width=3, tags=(tag, 'chip_selector'))
            inner = c.create_oval(chip_x + 5, 651, chip_x + 51, 697, fill=color,
                outline='#F2E6C9', width=2, tags=(tag, 'chip_selector'))
            label_item = c.create_text(chip_x + 28, 674, text=label,
                font=self._fit_chip_font(label, 25), fill=self.contrast_text_color(color),
                tags=(tag, 'chip_selector'))
            self.chip_selector_items[value] = (outer, inner, label_item)
            self.chip_selector_centers[float(value)] = (chip_x + 28, 674)
            c.tag_bind(tag, '<Button-1>', lambda _e, v=value: self.select_chip(v))
            chip_x += diameter + gap
        self.info_button = self._create_canvas_button(810, 650, 855, 695, '?',
            self.show_game_instructions, '#173f66', tag='control_info', font_size=17)
        self.repeat_button = self._create_canvas_button(862, 638, 1000, 708, '重复下注',
            self.repeat_last_bet, '#536A43', tag='control_repeat', font_size=11)
        self.deal_button = self._create_canvas_button(1012, 628, 1138, 720, '开牌\nENTER',
            self.deal_cards, '#D8B46A', fg='#2A1B08', tag='control_deal', font_size=14)
        specs = (('hit', '要牌', self.hit, '#397A48'),
                 ('stand', '停牌', self.stand, '#FC003F'),
                 ('double', '加倍', self.double, '#A57A36'),
                 ('split', '分牌', self.split, '#635182'),
                 ('surrender', '兑现金额\n$0.00', self.instant_surrender, '#9B403A'))
        for index, (action, label, command, color) in enumerate(specs):
            left = 278 + index * 174
            self.action_buttons[action] = self._create_canvas_button(
                left, 638, left + 164, 720, label, command, color,
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
                c.itemconfigure(face, fill=self._shade_color(button['color'], 1.12))
        def leave(event=None):
            # Canvas Enter/Leave also fires between a button's own layers.
            if inside(event):
                return
            c.configure(cursor='')
            self._set_button(button, button['enabled'])
        def press(event=None):
            if button['enabled'] and inside(event):
                button['pressed'] = True
                c.itemconfigure(face, fill=self._shade_color(button['color'], .72))
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

    def _set_action_button_style(self, key, free_mode=False):
        button = self.action_buttons.get(key)
        if not button:
            return
        styles = {'hit': '#397A48', 'stand': '#FC003F', 'double': '#A57A36',
                  'split': '#635182', 'surrender': '#9B403A'}
        free_mode = free_mode and key in ('double', 'split')
        button['color'] = self.FREE_BUTTON_BG if free_mode else styles.get(key, button['color'])
        button['fg'] = self.FREE_BUTTON_FG if free_mode else 'white'

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
        self._raise_wager_chips()

    def _set_round_control_visibility(self, in_round):
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

    def _refresh_free_rule_flash(self):
        """Blink only the gold rule bars for FREE actions the current hand can take."""
        if self._closing:
            return
        hand = self.active_hand()
        active = bool(self.round_active and self.dealer_blackjack_checked
                      and not self.animation_running and not self.settlement_running
                      and not self.ace_decision_mode and hand and hand['status'] == 'active'
                      and not hand.get('needs_split_draw', False))
        actions = set()
        if active:
            if self.is_free_split(hand) and self.can_split(hand):
                actions.add('split')
            if self.is_free_double(hand) and self.can_double(hand):
                actions.add('double')
        actions = frozenset(actions)
        if actions != self._free_rule_flash_actions or not actions:
            if self._free_rule_flash_job is not None:
                try:
                    self.after_cancel(self._free_rule_flash_job)
                except (tk.TclError, ValueError):
                    pass
                if self._free_rule_flash_job in self.after_ids:
                    self.after_ids.remove(self._free_rule_flash_job)
                self._free_rule_flash_job = None
            self._free_rule_flash_actions = actions
            self._free_rule_flash_bright = bool(actions)
        for kind in ('split', 'double'):
            bright = kind in actions and self._free_rule_flash_bright
            self.canvas.itemconfigure(
                getattr(self, f'rule_{kind}_bar_rect'),
                fill='#fff5ae' if bright else self.FREE_BUTTON_BG,
                outline='#fffbe7' if bright else '#FFF1B3', width=3 if bright else 1)
        if actions and self._free_rule_flash_job is None:
            def step():
                self._free_rule_flash_job = None
                self._free_rule_flash_bright = not self._free_rule_flash_bright
                self._refresh_free_rule_flash()
            self._free_rule_flash_job = self._queue(320, step)

    def _set_rules_strip_visible(self, visible):
        """Classic keeps its rules on-table, including both upper-right FREE rows."""
        self.canvas.itemconfigure('round_rule_strip', state='normal')
        self.canvas.itemconfigure('free_rule_bar', state='normal')
        self.canvas.itemconfigure('free_rule_bar_text', state='normal')
        self._refresh_rule_strip_text()
        if not visible:
            self.canvas.delete('insurance_chip')
        else:
            self._render_insurance_chip()

    def _refresh_rule_strip_text(self):
        # V12: insurance overlays the centre of the BAR; wording never shifts.
        self.canvas.itemconfigure(self.rule_strip_text, state='normal')
        self.canvas.itemconfigure(self.rule_strip_left_text, state='hidden')
        self.canvas.itemconfigure(self.rule_strip_right_text, state='hidden')

    def _set_rule_strip_text_color(self, color):
        for item in (self.rule_strip_text, self.rule_strip_left_text, self.rule_strip_right_text):
            try: self.canvas.itemconfigure(item, fill=color)
            except tk.TclError: pass

    def _render_insurance_chip(self):
        self.canvas.delete('insurance_chip')
        if (not self.insurance_chip_visible or self.insurance_bet <= 0.0
                or self.insurance_early_collected):
            return
        returned = self.insurance_return_amount if self.settlement_running else None
        self._draw_outcome_rows(self._outcome_chip_rows(('insurance',),
            self.insurance_bet, returned, self.rule_strip_chip_pos, self.INSURANCE_CHIP_RADIUS, ('insurance_chip',)))
        self.canvas.tag_raise('insurance_chip')

    def _animate_insurance_chip_to_rule(self, on_complete=None):
        """Fly half of the MAIN bet from the hidden chip-rack area to the rule strip."""
        amount = float(self.insurance_bet)
        sx, sy = 575.0, 674.0
        tx, ty = self.rule_strip_chip_pos
        items = self._draw_baccarat_chip(sx, sy, amount, tags=('insurance_chip_fly',), radius=self.INSURANCE_CHIP_RADIUS)
        self.canvas.tag_raise('insurance_chip_fly')
        steps = 10; frame_ms = 20
        def frame(step=1):
            t = min(1.0, step / steps); e = 1.0 - (1.0 - t) ** 2
            cx, cy = sx + (tx-sx)*e, sy + (ty-sy)*e; r=self.INSURANCE_CHIP_RADIUS
            self.canvas.coords(items[0], cx-r, cy-r, cx+r, cy+r)
            self.canvas.coords(items[1], cx-r+3, cy-r+3, cx+r-3, cy+r-3)
            self.canvas.coords(items[2], cx, cy)
            if step < steps:
                self._queue(frame_ms, frame, step+1)
            else:
                self.canvas.delete('insurance_chip_fly')
                self.insurance_chip_visible = True
                self._refresh_rule_strip_text(); self._render_insurance_chip(); self.update_display()
                if callable(on_complete): on_complete()
        self._queue(frame_ms, frame, 1)

    def _show_ace_decision(self, mode):
        self.ace_decision_mode = mode
        if mode == 'even_money':
            self._set_button(self.decision_buttons['accept'], True, '立刻赔付')
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
        if not mode or self.animation_running or self.settlement_running:
            return
        hand = self.hands[0] if self.hands else None
        if mode == 'even_money':
            self.ace_decision_mode = None
            if accept and hand:
                hand['status'] = 'even_money'
                hand['result'] = 'Even Money +1:1'
                hand['settlement'] = hand['base_settlement'] = 'win'
                hand['double_settlement'] = None
                hand['settlement_return'] = self.round_original_bet * 2.0
                self.balance += hand['settlement_return']
                self.save_balance()
            elif hand:
                hand['status'] = 'blackjack'
                hand['result'] = 'Blackjack'
            self._peek_dealer_blackjack()
            return
        if accept:
            amount = self.round_original_bet / 2.0
            if self.balance + 1e-9 < amount:
                return
            self.balance -= amount
            self.insurance_bet = amount
            self.insurance_result = '保险待定'
            self.ace_decision_mode = None
            self.animation_running = True
            self.save_balance()
            self.update_display()
            self._animate_insurance_chip_to_rule(self._peek_dealer_blackjack)
        else:
            self.ace_decision_mode = None
            self.insurance_result = '未购买保险'
            self._peek_dealer_blackjack()


    def _animate_betting_station(self, to_round, on_complete=None):
        """Classic uses one fixed layout for betting, dealing and settlement."""
        self.bet_layout_mode = self.player_zone_mode = 'round' if to_round else 'home'
        self._set_rules_strip_visible(to_round)
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
        """Compact a chip amount to K/M with at most one visible decimal.

        V16 deliberately truncates rather than rounds.  When non-zero value is
        hidden beyond the visible tenth, append ``+`` (2111 -> 2.1K+,
        1_010_000 -> 1.0M+).  Exact values keep the shorter form.
        """
        amount = float(amount)
        if amount >= 1_000_000:
            scale, suffix = 1_000_000.0, 'M'
        elif amount >= 1_000:
            scale, suffix = 1_000.0, 'K'
        else:
            return f'{amount:g}'

        scaled = amount / scale
        # Bets/returns are non-negative.  A tiny epsilon protects exact decimal
        # amounts from binary floating-point noise before truncation.
        tenths = int((scaled + 1e-12) * 10.0)
        shown = tenths / 10.0
        hidden = amount - shown * scale > max(1e-7, scale * 1e-10)

        if hidden:
            # Keep the .0 when it carries information: 1.01M -> 1.0M+.
            label = f'{shown:.1f}'
        elif abs(shown - round(shown)) < 1e-12:
            label = f'{int(round(shown))}'
        else:
            label = f'{shown:.1f}'
        return f'{label}{suffix}{"+" if hidden else ""}'

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
        for color, width in (('#A5BED4', 9), (spot['normal_outline'], 6)):
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


    def _draw_free_chip(self, cx, cy, tags, radius=None):
        """Retain the gold FREE marker with the same readable rim and diameter."""
        radius = self.WAGER_CHIP_RADIUS if radius is None else float(radius)
        tags = ((tags,) if isinstance(tags, str) else tuple(tags)) + ('wager_chip',)
        outer = self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
            fill='#F7F3E8', outline='#111820', width=2, tags=tags)
        inset = self.CHIP_RIM_INSET
        inner = self.canvas.create_oval(cx-radius+inset, cy-radius+inset,
            cx+radius-inset, cy+radius-inset, fill=self.FREE_CHIP_COLOR,
            outline='', tags=tags)
        label = self.canvas.create_text(cx, cy, text='免费',
            font=(self.cn_font, -max(1, min(18, round(radius*.6))), 'bold'),
            fill='#000000', tags=tags)
        return outer, inner, label

    def _animate_free_chip_to_hand_component(self, hand_index, component, on_complete=None):
        """Spawn a FREE chip inside the relevant gold rule bar, then drop it to the
        selected hand's split/double wager position."""
        layout = self._main_split_wager_layout(len(self.hands)) if self.hands else []
        if not (0 <= int(hand_index) < len(layout)) or component not in ('base', 'double'):
            if callable(on_complete):
                on_complete()
            return
        tx, ty = layout[int(hand_index)][component]
        if component == 'base':
            sx, sy = getattr(self, 'rule_split_bar_center', (tx, ty))
        else:
            sx, sy = getattr(self, 'rule_double_bar_center', (tx, ty))
        self.canvas.delete('free_chip_fly')
        items = self._draw_free_chip(sx, sy, tags=('free_chip_fly',), radius=1)
        self.canvas.tag_raise('free_chip_fly')
        spawn_steps, move_steps, frame_ms = 25, 25, 20

        def draw_at(cx, cy, radius):
            radius = max(1.0, float(radius))
            inner = max(0.0, radius - 3.0)
            self.canvas.coords(items[0], cx-radius, cy-radius, cx+radius, cy+radius)
            self.canvas.coords(items[1], cx-inner, cy-inner, cx+inner, cy+inner)
            self.canvas.coords(items[2], cx, cy)
            size = max(1, int(round(18 * (radius / self.WAGER_CHIP_RADIUS))))
            self.canvas.itemconfigure(items[2], font=(self.cn_font, -size, 'bold'))
            self.canvas.tag_raise('free_chip_fly')

        def spawn_frame(step=1):
            t = min(1.0, step / float(spawn_steps))
            e = t * t * (3.0 - 2.0 * t)
            draw_at(sx, sy, 1.0 + (self.WAGER_CHIP_RADIUS-1.0)*e)
            if step < spawn_steps:
                self._queue(frame_ms, spawn_frame, step + 1)
            else:
                self._queue(frame_ms, move_frame, 1)

        def move_frame(step=1):
            t = min(1.0, step / float(move_steps))
            e = 1.0 - (1.0 - t) ** 2
            cx = sx + (tx - sx) * e
            cy = sy + (ty - sy) * e
            draw_at(cx, cy, self.WAGER_CHIP_RADIUS)
            if step < move_steps:
                self._queue(frame_ms, move_frame, step + 1)
            else:
                self.canvas.delete('free_chip_fly')
                if callable(on_complete):
                    on_complete()

        self._queue(frame_ms, spawn_frame, 1)

    def _animate_free_chips_out(self, positions, on_complete=None, duration_ms=300):
        """Collect FREE stakes with the same continuous upward movement as paid chips."""
        if self._closing:
            return
        tag = 'free_chip_collect_fly'
        self.canvas.delete(tag)
        if not positions:
            if callable(on_complete):
                on_complete()
            return
        drawn = [(float(x), float(y), self._draw_free_chip(x, y,
                  tags=(tag, 'chip_animation'), radius=self.WAGER_CHIP_RADIUS)) for x, y in positions]
        steps = max(1, round(max(20, duration_ms) / 20))
        frame_ms = max(1, round(max(20, duration_ms) / steps))
        def frame(step=0):
            t = min(1.0, step / steps)
            e = t * t * (3.0 - 2.0 * t)
            for x, sy, items in drawn:
                y = sy + (-35.0 - sy) * e
                self.canvas.coords(items[0], x-self.WAGER_CHIP_RADIUS, y-self.WAGER_CHIP_RADIUS, x+self.WAGER_CHIP_RADIUS, y+self.WAGER_CHIP_RADIUS)
                self.canvas.coords(items[1], x-self.WAGER_CHIP_RADIUS+3, y-self.WAGER_CHIP_RADIUS+3, x+self.WAGER_CHIP_RADIUS-3, y+self.WAGER_CHIP_RADIUS-3)
                self.canvas.coords(items[2], x, y)
            self.canvas.tag_raise('chip_animation')
            if step < steps:
                self._queue(frame_ms, frame, step + 1)
            else:
                self.canvas.delete(tag)
                if callable(on_complete):
                    on_complete()
        frame(0)

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
            amount = 0.0 if self.round_active else float(self.current_bet)
        elif self.round_active:
            if spot_key in self.side_bet_early_collected:
                return 0.0
            amount = float(self.round_side_bets.get(spot_key, 0.0))
            if self.settlement_running:
                amount = min(amount, float(self.side_bet_return_amounts.get(spot_key, 0.0)))
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
            amount = self._bet_amount_for_spot(key)
            if amount > 0.0:
                self._draw_baccarat_chip(*spot['chip_pos'], amount,
                    tags=('bet_chip_dynamic', spot['tag'], 'principal_chip'), radius=self.WAGER_CHIP_RADIUS)
            if self.round_active and key != 'MAIN':
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
        """Keep betting labels and the rule strip at their normal colours."""
        for spot in getattr(self, 'bet_spots', {}).values():
            label = spot.get('label')
            if label:
                try:
                    self.canvas.itemconfigure(label, fill=spot.get('normal_label_fill', 'white'))
                except tk.TclError:
                    pass
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
            f'side_bet_collect_{safe}', easing='smooth')

    def _draw_side_bet_win_odds_badges(self):
        self.canvas.delete('side_bet_win_odds')

    def _settlement_losing_chip_sources(self):
        """Visible losing PAID wager components as (x,y,amount,radius)."""
        sources = []
        for key in self.SIDE_BET_KEYS:
            if key in self.side_bet_early_collected:
                continue
            stake = float(self.round_side_bets.get(key, 0.0))
            returned = float(self.side_bet_return_amounts.get(key, 0.0))
            spot = self.bet_spots.get(key)
            if stake > 0.0 and returned <= 0.0 and spot:
                x, y = spot['chip_pos']; sources.append((x, y, stake, self.WAGER_CHIP_RADIUS))

        layout = self._main_split_wager_layout(len(self.hands)) if self.hands else []
        for idx, hand in enumerate(self.hands[:4]):
            if idx >= len(layout): break
            if (not hand.get('base_is_free', False)
                    and float(hand.get('base_bet', 0.0)) > 0
                    and hand.get('base_settlement') == 'lose'):
                x, y = layout[idx]['base']; sources.append((x, y, float(hand['base_bet']), self.WAGER_CHIP_RADIUS))
            if (float(hand.get('double_added', 0.0)) > 0
                    and hand.get('double_settlement') == 'lose'):
                x, y = layout[idx]['double']; sources.append((x, y, float(hand['double_added']), self.WAGER_CHIP_RADIUS))

        if (self.insurance_bet > 0.0 and self.insurance_return_amount <= 0.0
                and not self.insurance_early_collected):
            x, y = self.rule_strip_chip_pos; sources.append((x, y, float(self.insurance_bet), self.INSURANCE_CHIP_RADIUS))
        return sources

    def _settlement_free_chip_collect_positions(self, winning=False):
        """Losing/PUSH FREE stakes leave immediately; winning FREE stakes leave on return."""
        positions = []
        layout = self._main_split_wager_layout()
        for index, hand in enumerate(self.hands):
            for component in ('base', 'double'):
                is_free = (bool(hand.get('base_is_free', False)) if component == 'base'
                           else float(hand.get('free_double_amount', 0.0)) > 0.0)
                state = hand.get(f'{component}_settlement')
                collect = state == 'win' if winning else state in ('lose', 'push', 'refund', 'cashout')
                if is_free and collect:
                    positions.append(layout[index][component])
        return positions

    def _settlement_return_chip_sources(self):
        return [(*row['pos'], row['amount'], row['radius'])
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

    def _animate_settlement_chips(self, sources, destination, duration_ms, tag,
                                 on_complete=None, easing='out'):
        """Move the actual chip drawings continuously, including the starting frame."""
        if self._closing:
            return
        self.canvas.delete(tag)
        if not sources:
            if callable(on_complete):
                on_complete()
            return
        duration_ms = max(20, int(duration_ms))
        steps = max(1, round(duration_ms / 20))
        frame_ms = max(1, round(duration_ms / steps))
        drawn = []
        for sx, sy, amount, radius in sources:
            items = self._draw_baccarat_chip(sx, sy, amount,
                tags=(tag, 'chip_animation'), radius=radius)
            drawn.append((float(sx), float(sy), float(radius), items))

        def frame(step=0):
            t = min(1.0, step / steps)
            e = t * t * (3.0 - 2.0 * t) if easing == 'smooth' else 1.0 - (1.0 - t) ** 2
            for sx, sy, r, items in drawn:
                tx, ty = destination(sx, sy) if callable(destination) else destination
                x, y = sx + (tx - sx) * e, sy + (ty - sy) * e
                self.canvas.coords(items[0], x-r, y-r, x+r, y+r)
                self.canvas.coords(items[1], x-r+3, y-r+3, x+r-3, y+r-3)
                self.canvas.coords(items[2], x, y)
            self.canvas.tag_raise('chip_animation')
            if step < steps:
                self._queue(frame_ms, frame, step + 1)
            else:
                self.canvas.delete(tag)
                if callable(on_complete):
                    on_complete()
        frame(0)

    def _animate_losing_chips_out(self):
        self._animate_settlement_chips(self._settlement_losing_chip_sources(),
            lambda x, y: (x, -35.0), 300, 'settlement_loss_fly', easing='smooth')
        self._animate_free_chips_out(self._settlement_free_chip_collect_positions())

    def _finish_flash_with_chip_return(self):
        """Return each principal/profit chip from its displayed position once."""
        if not self.settlement_running or self.settlement_visual_stage == 'returning':
            return
        sources = self._settlement_return_chip_sources()
        free_positions = self._settlement_free_chip_collect_positions(winning=True)
        self.settlement_visual_stage = 'returning'
        for tag in ('bet_chip_dynamic', 'hand_wager', 'insurance_chip', 'win_flash_area',
                    'side_bet_win_odds', 'side_bet_progress_badge'):
            self.canvas.delete(tag)
        self.flash_mode = None
        remaining = [2]
        def part_done():
            remaining[0] -= 1
            if not remaining[0]:
                self.settlement_running = False
                self._reset_after_round()

        def cash_arrived():
            # Keep the existing cash accounting: FREE winnings are credited exactly
            # once, when their cash-profit chips finish returning to the player.
            free_credit = 0.0
            for hand in self.hands:
                if not hand.get('free_credit_paid', False):
                    free_credit += max(0.0, float(hand.get('free_credit_pending', 0.0)))
                    hand['free_credit_pending'] = 0.0
                    hand['free_credit_paid'] = True
            if free_credit > 0.0:
                self.balance += free_credit
                self.save_balance()
                self.update_display()
            part_done()

        self._animate_free_chips_out(free_positions, on_complete=part_done, duration_ms=200)
        self._animate_settlement_chips(sources, (575.0, 674.0), 200,
                                       'settlement_return_fly', cash_arrived)

    def run_settlement_flash(self):
        """Compatibility entry point: keep the outcome steady, as in Classic."""
        if not self._closing and self.settlement_running:
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

        # MAIN is independently capped at $500K. If the selected denomination is
        # larger than the remaining allowance, silently place only the remainder.
        remaining_limit = max(0.0, self.MAX_MAIN_BET - float(self.current_bet))
        amount = min(float(self.selected_chip), remaining_limit)
        if amount <= 1e-9:
            return

        if self.balance + 1e-9 < amount:
            messagebox.showwarning(
                '余额不足',
                '余额不足以放置该筹码。',
                parent=self.winfo_toplevel()
            )
            return

        self.show_last_win = False
        self.balance -= amount
        self.current_bet += amount
        self.pending_bet_animation['MAIN'] += amount
        self.bet_chip_animation_count += 1
        self.update_display()

        self._animate_selected_chip_to_spot(
            'MAIN',
            lambda: self._finish_bet_chip_animation('MAIN', amount),
            amount=amount
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

        # Every side bet has its own $100K cap. A chip larger than the remaining
        # allowance is silently reduced to exactly fill that side-bet limit.
        current_side_amount = float(self.current_side_bets.get(key, 0.0))
        remaining_limit = max(0.0, self.MAX_SIDE_BET - current_side_amount)
        amount = min(float(self.selected_chip), remaining_limit)
        if amount <= 1e-9:
            return

        if self.balance + 1e-9 < amount:
            messagebox.showwarning(
                '余额不足',
                '余额不足以放置该筹码。',
                parent=self.winfo_toplevel()
            )
            return

        self.show_last_win = False
        self.balance -= amount
        self.current_side_bets[key] += amount
        self.pending_bet_animation[key] += amount
        self.bet_chip_animation_count += 1
        self.update_display()

        self._animate_selected_chip_to_spot(
            key,
            lambda k=key, a=amount: self._finish_bet_chip_animation(k, a),
            amount=amount
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
        if (
            not self.accept_bets
            or self.round_active
            or self.animation_running
            or self.settlement_running
            or self.bet_chip_animation_count > 0
        ):
            return

        targets = {
            'MAIN': min(float(self.last_bet), self.MAX_MAIN_BET),
            **{
                key: min(float(self.last_side_bets.get(key, 0.0)), self.MAX_SIDE_BET)
                for key in self.SIDE_BET_KEYS
            }
        }
        currents = {
            'MAIN': float(self.current_bet),
            **{key: float(self.current_side_bets.get(key, 0.0)) for key in self.SIDE_BET_KEYS}
        }

        additions = {'MAIN': max(0.0, targets['MAIN'] - currents['MAIN'])}
        additions['MAIN'] = min(
            additions['MAIN'],
            max(0.0, self.MAX_MAIN_BET - currents['MAIN']))
        for key in self.SIDE_BET_KEYS:
            add = max(0.0, targets[key] - currents[key])
            additions[key] = min(add, max(0.0, self.MAX_SIDE_BET - currents[key]))

        needed = sum(additions.values())
        if needed <= 0:
            return

        if self.balance + 1e-9 < needed:
            messagebox.showwarning(
                '无法重复下注',
                '余额不足以重复上局下注。',
                parent=self.winfo_toplevel()
            )
            return

        self.show_last_win = False
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
                key,
                add,
                lambda k=key, a=add: self._finish_bet_chip_animation(k, a)
            )

    # -------------------------------------------------------------- Blackjack_Free_Double.json
    # -------------------------------------------------------------- Blackjack_Free_Double.json
    def save_runtime_store(self, burn_complete=True):
        data = {
            'version': 2,
            'variant': 'Free_Double_Blackjack',
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
        dialog.title('免费黑杰克 · 切牌')
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
        # Row 2 and row 3 are separated by one full card-height (140 px) of
        # empty space.  A ten-value burn therefore appears as a clean 5 + 5.
        card_w = float(self.CARD_WIDTH)
        card_h = float(self.CARD_HEIGHT)
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
        rect = self.canvas.create_rectangle(x, y, x + self.CARD_WIDTH, y + self.CARD_HEIGHT, fill=fill,
                                            outline='#d7cbb9', width=2,
                                            tags=(tag, 'temp_card'))
        if face_up and card is not None:
            suit, rank = card
            symbol = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}.get(suit, suit[:1])
            fg = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
            tid = self.canvas.create_text(x + self.CARD_WIDTH / 2, y + self.CARD_HEIGHT / 2, text=f'{rank}\n{symbol}',
                                          font=('Arial', 18, 'bold'), fill=fg,
                                          justify='center', tags=(tag, 'temp_card'))
            self.card_items.extend((rect, tid))
        else:
            self.card_items.append(rect)
        return rect

    def clear_card_display(self):
        for tag in ('dealt_card','temp_card','hand_label','hand_zone','hand_wager','animation_card'):
            self.canvas.delete(tag)
        self.card_items.clear(); self._temp_flip_images.clear()
        self.previous_round_cards_present = False
        if hasattr(self, 'dealer_total_text'):
            self.canvas.itemconfigure(self.dealer_total_text, text='')



    def _hand_centers(self, count=None):
        return [lane[2] for lane in self._player_hand_geometry(count)]


    def _main_split_wager_layout(self, count=None):
        """Classic places each base chip below its first card, with Double to its right."""
        layout = []
        for geometry in self._player_hand_geometry(count):
            x, y = self._player_card_position({}, geometry, 0)
            cx = self._wager_center_x(x + self.CARD_WIDTH / 2, geometry)
            cy = y + self.CARD_HEIGHT + self.WAGER_CHIP_RADIUS + self.CARD_WAGER_GAP
            layout.append({'base': (cx, cy), 'double': (cx + self.CHIP_PITCH, cy)})
        return layout

    def _component_return_amount(self, hand, component):
        """Displayed/returned cash for one paid or FREE main-wager component."""
        if component == 'base':
            amount = float(hand.get('base_bet', 0.0))
            state = hand.get('base_settlement')
            is_free = bool(hand.get('base_is_free', False))
        else:
            free_amount = float(hand.get('free_double_amount', 0.0))
            is_free = free_amount > 0.0
            amount = free_amount if is_free else float(hand.get('double_added', 0.0))
            state = hand.get('double_settlement')
        if amount <= 0.0 or not state:
            return 0.0

        # A FREE chip has no stake to return. It produces exactly one original-bet
        # amount only when that component wins; PUSH/refund/loss collects the chip.
        if is_free:
            return amount if state == 'win' else 0.0

        if state == 'win':
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

    def _finalize_hand_component_credit(self, hand):
        """Credit paid returns now; defer FREE winnings until the return animation ends."""
        paid_credit = 0.0
        free_credit = 0.0
        for component in ('base', 'double'):
            amount = self._component_return_amount(hand, component)
            if amount <= 0.0:
                continue
            is_free = (hand.get('base_is_free', False) if component == 'base'
                       else float(hand.get('free_double_amount', 0.0)) > 0.0)
            if is_free:
                free_credit += amount
            else:
                paid_credit += amount
        if paid_credit > 0.0:
            self.balance += paid_credit
        hand['free_credit_pending'] = free_credit
        hand['free_credit_paid'] = free_credit <= 0.0
        hand['settlement_return'] = paid_credit + free_credit
        return hand['settlement_return']

    def _draw_main_hand_wagers(self):
        self.main_wager_positions = {}
        rows = self._main_wager_rows()
        for index, pos in enumerate(self._main_split_wager_layout()):
            self.main_wager_positions[index] = dict(
                base=pos['base'], double=pos['double'],
                show_base=any(row['key'][:3] == ('main', index, 'base') and
                              row['role'] in ('principal', 'free') for row in rows),
                show_double=any(row['key'][:3] == ('main', index, 'double') and
                                row['role'] in ('principal', 'free') for row in rows))
        self._draw_outcome_rows(rows)


    def _player_card_target(self, hand_index, card_index):
        return self._player_card_position(self.hands[hand_index],
                                         self._player_hand_geometry()[hand_index], card_index)


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
        visible = self.dealer_cards[:1] if self.dealer_hole_hidden else self.dealer_cards
        x, y0 = self._dealer_card_target(len(self.dealer_cards) - 1)
        tip_x, y = x + self.CARD_WIDTH + 6, y0 + self.CARD_HEIGHT / 2
        left, right = tip_x + 10, tip_x + 62
        total, soft = BlackjackEngine.hand_value(visible)
        natural = BlackjackEngine.is_blackjack(visible)
        self.canvas.create_polygon(tip_x, y, left, y-18, right, y-18, right, y+18, left, y+18,
            fill='#000000' if natural else self._dealer_badge_fill(), outline='',
            tags=('hand_label', 'dealer_total_badge'))
        self.canvas.create_text((left + right) / 2, y,
            text=self._hand_total_badge_text(visible, blackjack=natural,
                soft_stand=soft and len(visible) >= 2 and 18 <= total <= 21),
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
            if index == 1 and self.dealer_hole_hidden:
                self._render_back_card(*self._dealer_card_target(index),
                    tags=('dealt_card', 'dealer_dealt_card', 'dealer_hole_card'))
            else:
                self._render_card(card, *self._dealer_card_target(index),
                                  tags=('dealt_card', 'dealer_dealt_card'))
        self._draw_dealer_total_badge()
        self.canvas.itemconfigure(self.dealer_total_text, text='')
        geometry = self._player_hand_geometry()
        self.hand_zone_bounds = []
        for index, hand in enumerate(self.hands):
            left, right, _cx, _order, _n = geometry[index]
            self.hand_zone_bounds.append((left, 256, right, 534))
            for j, card in enumerate(hand['cards']):
                self._render_card(card, *self._player_card_target(index, j),
                    tags=('dealt_card', 'player_dealt_card', f'player_card_{index}_{j}'),
                    rotation=self._player_card_rotation(hand, j))
            self._draw_hand_total_badge(index, left, right)
        self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._raise_visible_bottom_controls(self.round_active)
        self._raise_wager_chips()
        self.canvas.tag_raise('dealer_22_notice')

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
                 from_split=False, split_aces=False, needs_split_draw=False,
                 base_is_free=False, free_base_pending=False):
        return {
            'cards': list(cards or []),
            # base_bet remains the nominal table amount even when a FREE split chip
            # covers it. base_is_free decides whether cash was actually staked.
            'base_bet': float(base_bet),
            'base_is_free': bool(base_is_free),
            'free_base_pending': bool(free_base_pending),
            'double_added': 0.0,              # paid Double amount only
            'free_double_amount': 0.0,        # nominal FREE Double amount
            'free_double_pending': False,
            'contains_original': bool(contains_original),
            'from_split': bool(from_split),
            'split_aces': bool(split_aces),
            'needs_split_draw': bool(needs_split_draw),
            'status': 'active',
            'result': '',
            'cashout_credit': 0.0,
            'settlement': None,
            'base_settlement': None,
            'double_settlement': None,
            'settlement_return': 0.0,
            # FREE winnings are credited only when the flashing/return animation ends.
            'free_credit_pending': 0.0,
            'free_credit_paid': False,
            # Legacy fields are retained only for state compatibility; Free Blackjack
            # has no Spanish immediate-win payout rules.
            'instant_settled': False,
            'instant_profit_odds': None,
            'instant_credit_pending': 0.0,
            'instant_credit_paid': True,
        }

    @staticmethod
    def hand_stake(hand):
        """Cash actually risked on this hand; FREE components are excluded."""
        base = 0.0 if hand.get('base_is_free', False) else float(hand.get('base_bet', 0.0))
        return base + float(hand.get('double_added', 0.0))

    def _instant_rule_for_hand(self, hand):
        """Free Blackjack has no Spanish immediate-win main-bet awards."""
        return None

    def _try_instant_main_settlement(self, hand):
        """Compatibility stub: immediate-win settlement is disabled."""
        return False

    @staticmethod
    def _has_double_component(hand):
        return bool(float(hand.get('double_added', 0.0)) > 0.0
                    or float(hand.get('free_double_amount', 0.0)) > 0.0)

    @staticmethod
    def _free_chip_count_from_hands(hands):
        count = 0
        for hand in hands:
            if hand.get('base_is_free', False):
                count += 1
            if float(hand.get('free_double_amount', 0.0)) > 0.0:
                count += 1
        return count

    def _free_chip_count(self):
        return self._free_chip_count_from_hands(self.hands)

    @staticmethod
    def _golden_bucket_tier(count):
        return {1: 3, 2: 10, 3: 30, 4: 60, 5: 100, 6: 299, 7: 1000}.get(int(count))

    def _refresh_golden_bucket_progress(self):
        """Update 黄金桶's live tier, unless the side bet has already resolved."""
        key = 'Golden Bucket'
        # Once 黄金桶 has been declared a loss (for example because the player
        # skipped an available FREE action), later FREE actions must never revive it.
        if key in self.side_bet_results:
            self.side_bet_hit_odds.pop(key, None)
            self.side_bet_hit_labels.pop(key, None)
            return
        self.side_bet_hit_odds.pop(key, None)
        self.side_bet_hit_labels.pop(key, None)
        count = self._free_chip_count()
        odds = self._golden_bucket_tier(count)
        if odds is not None:
            self.side_bet_hit_odds[key] = float(odds)
            self.side_bet_hit_labels[key] = f'{count}个FREE筹码'

    def _invalidate_golden_bucket_if_free_skipped(self, hand, action_name, *, paid_double=False):
        """Immediately lose 黄金桶 when an available FREE action is declined.

        V3 rule:
        - If the current hand can Free Split and/or Free Double, choosing Hit or
          Stand forfeits 黄金桶 immediately.
        - A paid Double also forfeits 黄金桶 whenever a FREE option was available
          on that hand (for example 4-4: Free Split is available but Double is paid).
        - Taking the actual Free Split / Free Double does not forfeit the side bet.
        """
        key = 'Golden Bucket'
        if not hand or key in self.side_bet_results:
            return False
        free_split_available = self.is_free_split(hand)
        free_double_available = self.is_free_double(hand)
        if not (free_split_available or free_double_available):
            return False
        if paid_double or action_name in ('要牌', '停牌'):
            # Clear any live tier marker before resolving the side bet as a loss.
            self.side_bet_hit_odds.pop(key, None)
            self.side_bet_hit_labels.pop(key, None)
            self._credit_side_bet(key, None, f'放弃免费机会：{action_name}')
            self.update_display()
            return True
        return False

    @staticmethod
    def is_free_double(hand):
        if not hand or hand.get('status') != 'active' or len(hand.get('cards', ())) != 2:
            return False
        if hand.get('split_aces', False):
            return False
        total, soft = BlackjackEngine.hand_value(hand['cards'])
        return (not soft) and 9 <= total <= 11

    @staticmethod
    def is_free_split(hand):
        if not hand or hand.get('status') != 'active' or len(hand.get('cards', ())) != 2:
            return False
        r0, r1 = hand['cards'][0][1], hand['cards'][1][1]
        return r0 == r1 and r0 in {'A', '2', '3', '4', '5', '6', '7', '8', '9'}

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

        # Lock betting before transferring the pending MAIN wager into round state.
        # Classic keeps the table geometry fixed throughout this transition.
        self.accept_bets=False; self.animation_running=True
        self._set_button(self.deal_button, False)
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
        self.update_display()
        # Switch the bottom strip to hand actions immediately after Enter/click.
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
        self.split_actions=0; self.dealer_cards=[]; self.round_deal_sequence=[]; self.side_bet_results={}
        self.side_bet_return_amounts={}; self.side_bet_hit_odds={}; self.side_bet_hit_labels={}
        self.side_bet_early_collected=set()
        self.flash_winning_side_bets=set(); self.flash_main_bet=False; self.flash_main_push_only=False
        self.dealer_22_main_push=False
        self._fade_dealer_22_notice(False)
        self.flash_winning_hand_indices=set(); self.settlement_running=False; self.settlement_flash_step=0
        self.settlement_visual_stage = None
        self.pending_profit_chips = set()
        self.dealer_hole_hidden = True
        self.dealer_blackjack_checked = False
        self.dealer_blackjack_found = False
        self.dealer_blackjack_resolved = False
        self.insurance_resolved = False
        self.insurance_early_collected = False
        self.dealer_phase_active=False
        self.flash_mode=None
        self.hands=[self.new_hand(base_bet=self.round_original_bet,contains_original=True)]
        self.active_hand_index=0; self.last_result_lines=[]
        self._opening_wager_animation = True
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
        self._set_round_control_visibility(True)
        # Keep the resting wager hidden until it finishes its Classic opening lift.
        self.render_cards(); self.update_display(); self._raise_visible_bottom_controls(True)

        sequence=('P','D','P','D')
        def deal_step(index=0):
            if index>=len(sequence):
                self.animation_running=False; self.render_cards(); self._after_initial_deal(); return
            who=sequence[index]
            if who=='P':
                self._deal_player_card_animated(0,on_complete=lambda:self._queue(80,deal_step,index+1))
            else:
                self._deal_dealer_card_animated(
                    on_complete=lambda:self._queue(80,deal_step,index+1), face_up=index != 3)
        self._animate_starting_wagers(deal_step)

    def _after_initial_deal(self):
        self._settle_initial_side_bets()
        hand = self.hands[0]
        natural = BlackjackEngine.is_blackjack(hand['cards'])
        if natural:
            hand['status'] = 'blackjack'
            hand['result'] = 'Blackjack'
        if self.dealer_cards[0][1] == 'A':
            # Insurance/Even Money is chosen before the peek, with no player hand
            # actions available until the dealer has been cleared of Blackjack.
            self.animation_running = False
            self._show_ace_decision('even_money' if natural else 'insurance')
            self.render_cards()
            self.update_display()
        else:
            self._peek_dealer_blackjack()

    def _deal_player_card_animated(self, hand_index, on_complete=None):
        if not (0 <= hand_index < len(self.hands)):
            if callable(on_complete): on_complete()
            return
        hand=self.hands[hand_index]
        card=self.draw_round_card(); card_index=len(hand['cards']); hand['cards'].append(card)
        tx,ty=self._player_card_target(hand_index,card_index)
        def done():
            self.canvas.delete('round_animation_card')
            self.render_cards(); self.update_display()
            if callable(on_complete): on_complete()
        self._animate_card_from_shoe(card,tx,ty,on_complete=done,flip=True,tag='round_animation_card',
                                     rotation=self._player_card_rotation(hand, card_index))

    def _deal_dealer_card_animated(self, on_complete=None, face_up=True):
        card = self.draw_round_card()
        index = len(self.dealer_cards)
        self.dealer_cards.append(card)
        x, y = self._dealer_card_target(index)
        def done():
            self.canvas.delete('round_animation_card')
            self.render_cards()
            self.update_display()
            if callable(on_complete):
                on_complete()
        self._animate_card_from_shoe(card, x, y, on_complete=done,
            flip=face_up, tag='round_animation_card')

    def _prepare_active_split_hand(self, on_ready=None):
        hand = self.active_hand()
        if not hand or not hand.get('needs_split_draw', False):
            if callable(on_ready): on_ready()
            return
        hand['needs_split_draw'] = False
        self.animation_running = True

        def after_draw():
            total, _ = BlackjackEngine.hand_value(hand['cards'])
            if total > 21:
                hand['status'] = 'bust'; hand['result'] = '爆牌'
            elif hand.get('split_aces', False):
                # Split A receives one card only; A+A may be re-split subject to limits.
                if len(hand['cards']) == 2 and hand['cards'][1][1] == 'A' and self.can_split(hand):
                    hand['status'] = 'active'; hand['result'] = '分A后再A：可继续分牌'
                else:
                    hand['status'] = 'stood'; hand['result'] = '分A一张停牌'
            elif total == 21:
                hand['status'] = 'stood'; hand['result'] = '21点停牌'
            self.animation_running = False; self.render_cards(); self.update_display()
            if hand['status'] != 'active':
                self._queue(180, self._advance_hand)
            elif callable(on_ready):
                on_ready()
        self._deal_player_card_animated(self.active_hand_index, on_complete=after_draw)

    def active_hand(self):
        if not self.round_active or not (0 <= self.active_hand_index < len(self.hands)):
            return None
        return self.hands[self.active_hand_index]

    def can_hit(self, hand):
        if not self.dealer_blackjack_checked:
            return False
        if not hand or hand.get('status') != 'active' or hand.get('split_aces', False):
            return False
        total, _ = BlackjackEngine.hand_value(hand.get('cards', ()))
        return total < 21

    def can_double(self, hand):
        if not self.dealer_blackjack_checked:
            return False
        if (not hand or hand.get('status') != 'active' or len(hand.get('cards', ())) != 2
                or hand.get('split_aces', False)):
            return False
        if self.is_free_double(hand):
            return True
        return self.balance + 1e-9 >= float(hand.get('base_bet', 0.0))

    def can_split(self, hand):
        if not self.dealer_blackjack_checked:
            return False
        if not hand or hand.get('status') != 'active' or len(hand.get('cards', ())) != 2:
            return False
        if len(self.hands) >= self.MAX_HANDS or self.split_actions >= self.MAX_SPLIT_ACTIONS:
            return False
        if BlackjackEngine.split_value(hand['cards'][0]) != BlackjackEngine.split_value(hand['cards'][1]):
            return False
        if self.is_free_split(hand):
            return True
        return self.balance + 1e-9 >= float(hand.get('base_bet', 0.0))

    def can_surrender(self, hand):
        if not self.dealer_blackjack_checked:
            return False
        if not hand or hand['status'] != 'active' or not hand['cards']:
            return False
        if BlackjackEngine.is_blackjack(hand['cards']) and not hand.get('from_split', False):
            return False
        return BlackjackEngine.hand_value(hand['cards'])[0] <= 21

    def hit(self):
        hand = self.active_hand()
        if not self.can_hit(hand) or self.animation_running:
            return
        self._invalidate_golden_bucket_if_free_skipped(hand, '要牌')
        self.animation_running = True
        self.update_display(); self._raise_visible_bottom_controls(True)

        def after():
            total, _ = BlackjackEngine.hand_value(hand['cards'])
            if total > 21:
                hand['status'] = 'bust'; hand['result'] = '爆牌'
            elif total == 21:
                hand['status'] = 'stood'; hand['result'] = '21点停牌'
            self.animation_running = False; self.render_cards(); self.update_display()
            if hand['status'] != 'active':
                self._queue(220, self._advance_hand)
        self._deal_player_card_animated(self.active_hand_index, on_complete=after)

    def stand(self):
        hand = self.active_hand()
        if (not self.dealer_blackjack_checked or not hand or
                hand['status'] != 'active' or self.animation_running):
            return
        self._invalidate_golden_bucket_if_free_skipped(hand, '停牌')
        hand['status'] = 'stood'
        hand['result'] = '停牌'
        self.render_cards()
        self.update_display()
        self._advance_hand()

    def double(self):
        hand = self.active_hand()
        if not self.can_double(hand) or self.animation_running:
            return
        free_double = self.is_free_double(hand)
        if not free_double:
            self._invalidate_golden_bucket_if_free_skipped(
                hand, '付款Double', paid_double=True)
        self.animation_running = True
        for button in self.action_buttons.values():
            self._set_button(button, False)
        self._raise_visible_bottom_controls(True)

        amount = float(hand.get('base_bet', 0.0))

        def deal_double_card():
            def after():
                total, _ = BlackjackEngine.hand_value(hand['cards'])
                if total > 21:
                    hand['status'] = 'bust'; hand['result'] = '免费加倍爆牌' if free_double else '加倍爆牌'
                else:
                    hand['status'] = 'stood'; hand['result'] = '免费加倍停牌' if free_double else '加倍停牌'
                self.animation_running = False; self.render_cards(); self.update_display()
                self._queue(250, self._advance_hand)
            self._deal_player_card_animated(self.active_hand_index, on_complete=after)

        if free_double:
            hand['free_double_amount'] = amount
            hand['free_double_pending'] = True
            self._refresh_golden_bucket_progress()
            self.render_cards(); self.update_display()

            def free_arrived():
                hand['free_double_pending'] = False
                self.render_cards(); self.update_display()
                deal_double_card()
            self._animate_free_chip_to_hand_component(
                self.active_hand_index, 'double', on_complete=free_arrived)
        else:
            self.balance -= amount
            hand['double_added'] += amount
            self.save_balance()
            self.render_cards(); self.update_display()
            deal_double_card()


    def _move_canvas_tag(self, tag, dx, dy):
        try:
            self.canvas.move(tag, dx, dy)
        except tk.TclError:
            pass

    def _project_player_card_positions(self, hands_snapshot, count=None):
        n = len(hands_snapshot) if count is None else count
        geometry = self._player_hand_geometry(n)
        return {(index, card_index): self._player_card_position(hand, geometry[index], card_index)
                for index, hand in enumerate(hands_snapshot[:len(geometry)])
                for card_index in range(len(hand.get('cards', [])))}

    def _animate_canvas_positions(self, start_positions, end_positions,
                                  duration_ms=200, easing='smooth',
                                  arc_lifts=None, on_complete=None):
        """Animate canvas tags between exact top-left positions."""
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

    def _commit_split_state(self, preview_hands, on_complete=None):
        self.hands = preview_hands
        self.render_cards()
        self.update_display()
        if callable(on_complete):
            on_complete()

    def _animate_split_sequence(self, hand_index, left, right, on_complete=None):
        """Elegant split: focus the pair, reflow the whole table, then separate it.

        Existing hands and wager stacks move with the new 1..4 lane geometry, so
        re-splitting a later hand never produces a sudden global jump.
        """
        snapshots = [dict(h, cards=list(h.get('cards', []))) for h in self.hands]
        preview_hands = (
            self.hands[:hand_index]
            + [left, right]
            + self.hands[hand_index + 1:]
        )
        preview_snapshots = (
            snapshots[:hand_index]
            + [dict(left, cards=list(left.get('cards', []))),
               dict(right, cards=list(right.get('cards', [])))]
            + snapshots[hand_index + 1:]
        )
        old_count = max(1, len(snapshots))
        new_count = max(1, len(preview_snapshots))
        first_tag = f'player_card_{hand_index}_0'
        second_tag = f'player_card_{hand_index}_1'

        if (not self.canvas.find_withtag(first_tag)
                or not self.canvas.find_withtag(second_tag)):
            self._commit_split_state(preview_hands, on_complete)
            return

        self.canvas.delete('hand_label')
        self.canvas.delete('hand_zone')
        self.canvas.tag_raise('dealt_card')

        old_positions = self._project_player_card_positions(snapshots, old_count)
        final_positions = self._project_player_card_positions(preview_snapshots, new_count)
        old_first = old_positions.get((hand_index, 0))
        old_second = old_positions.get((hand_index, 1))
        if old_first is None or old_second is None:
            self._commit_split_state(preview_hands, on_complete)
            return

        first_final = final_positions[(hand_index, 0)]
        second_final = final_positions[(hand_index + 1, 0)]
        current_cx = self._hand_centers(old_count)[hand_index]

        # Phase 1: a small lift and tighten. This gives the split a deliberate,
        # tactile start without making the cards jump away from their current hand.
        focus_overlap = 24.0
        focus_width = self.CARD_WIDTH + focus_overlap
        focus_y = old_first[1] - 14.0
        focus_first = (current_cx - focus_width / 2.0, focus_y)
        focus_second = (focus_first[0] + focus_overlap, focus_y)

        # Phase 2: all hands reflow while the pair travels as one compact packet
        # to the midpoint of its future two lanes.
        split_mid = ((first_final[0] + self.CARD_WIDTH / 2) + (second_final[0] + self.CARD_WIDTH / 2)) / 2.0
        travel_overlap = 22.0
        travel_width = self.CARD_WIDTH + travel_overlap
        travel_y = min(first_final[1], second_final[1]) - 24.0
        travel_first = (split_mid - travel_width / 2.0, travel_y)
        travel_second = (travel_first[0] + travel_overlap, travel_y)

        self.canvas.tag_raise(first_tag)
        self.canvas.tag_raise(second_tag)

        def stage_two():
            self.canvas.tag_raise(first_tag)
            self.canvas.tag_raise(second_tag)

            start_map = {first_tag: focus_first, second_tag: focus_second}
            end_map = {first_tag: travel_first, second_tag: travel_second}

            # Every already-visible hand reflows at the same time. Later hands shift
            # one lane to the right when the new hand is inserted in the middle.
            for old_idx, snapshot in enumerate(snapshots):
                if old_idx == hand_index:
                    continue
                new_idx = old_idx if old_idx < hand_index else old_idx + 1
                for card_index in range(len(snapshot.get('cards', []))):
                    tag = f'player_card_{old_idx}_{card_index}'
                    start = old_positions.get((old_idx, card_index))
                    end = final_positions.get((new_idx, card_index))
                    if start and end and self.canvas.find_withtag(tag):
                        start_map[tag] = start
                        end_map[tag] = end

            # Existing MAIN wager stacks follow their owning hand instead of
            # remaining behind while the cards move to the new lane geometry.
            old_wagers = self._main_split_wager_layout(old_count)
            new_wagers = self._main_split_wager_layout(new_count)
            wager_moves = []
            for old_idx in range(old_count):
                tag = f'hand_wager_{old_idx}'
                if not self.canvas.find_withtag(tag):
                    continue
                new_idx = old_idx if old_idx < hand_index else (hand_index if old_idx == hand_index else old_idx + 1)
                sx, sy = old_wagers[old_idx]['base']
                tx, ty = new_wagers[new_idx]['base']
                wager_moves.append((tag, tx - sx, ty - sy))

            current = {key: tuple(value) for key, value in start_map.items()}
            moved_wager_fraction = [0.0]
            steps, frame_ms = 14, 20

            def frame(step=1):
                ratio = min(1.0, step / float(steps))
                eased = ratio * ratio * (3.0 - 2.0 * ratio)
                for key, start in start_map.items():
                    end = end_map[key]
                    x = start[0] + (end[0] - start[0]) * eased
                    y = start[1] + (end[1] - start[1]) * eased
                    prev_x, prev_y = current[key]
                    self._move_canvas_tag(key, x - prev_x, y - prev_y)
                    current[key] = (x, y)
                delta = eased - moved_wager_fraction[0]
                moved_wager_fraction[0] = eased
                for tag, dx, dy in wager_moves:
                    self._move_canvas_tag(tag, dx * delta, dy * delta)

                if step < steps:
                    self._queue(frame_ms, frame, step + 1)
                else:
                    # Phase 3: the two cards peel apart on shallow arcs and settle
                    # gently into their exact new hand centres.
                    self._animate_canvas_positions(
                        {first_tag: travel_first, second_tag: travel_second},
                        {first_tag: first_final, second_tag: second_final},
                        duration_ms=360, easing='out',
                        arc_lifts={first_tag: 10.0, second_tag: 18.0},
                        on_complete=lambda: self._commit_split_state(
                            preview_hands, on_complete))

            self._queue(frame_ms, frame, 1)

        self._animate_canvas_positions(
            {first_tag: old_first, second_tag: old_second},
            {first_tag: focus_first, second_tag: focus_second},
            duration_ms=160, easing='smooth',
            arc_lifts={first_tag: 4.0, second_tag: 4.0},
            on_complete=stage_two)

    def split(self):
        hand = self.active_hand()
        if not self.can_split(hand) or self.animation_running:
            return

        free_split = self.is_free_split(hand)
        add = float(hand.get('base_bet', 0.0))

        # Lock all decisions before the first split-animation frame.
        self.animation_running = True
        for button in self.action_buttons.values():
            self._set_button(button, False)
        self._raise_visible_bottom_controls(True)

        if not free_split:
            self.balance -= add
            self.save_balance()
        self.split_actions += 1

        hand_index = self.active_hand_index
        first, second = hand['cards'][0], hand['cards'][1]
        is_aces = first[1] == 'A' and second[1] == 'A'
        left = self.new_hand(
            cards=[first], base_bet=hand['base_bet'],
            contains_original=hand.get('contains_original', False),
            from_split=True, split_aces=is_aces, needs_split_draw=True,
            base_is_free=hand.get('base_is_free', False))
        right = self.new_hand(
            cards=[second], base_bet=hand['base_bet'],
            contains_original=False, from_split=True,
            split_aces=is_aces, needs_split_draw=True,
            base_is_free=free_split, free_base_pending=free_split)
        right_index = hand_index + 1

        def after_layout():
            if free_split:
                self._refresh_golden_bucket_progress()

                def free_arrived():
                    if 0 <= right_index < len(self.hands):
                        self.hands[right_index]['free_base_pending'] = False
                    self.animation_running = False
                    self.render_cards()
                    self.update_display()
                    self._prepare_active_split_hand()

                self._animate_free_chip_to_hand_component(
                    right_index, 'base', on_complete=free_arrived)
            else:
                self.animation_running = False
                self.render_cards()
                self.update_display()
                self._prepare_active_split_hand()

        self.update_display()
        self._animate_split_sequence(
            hand_index, left, right, on_complete=after_layout)

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
        # Normal 52-card rank distribution: A,2..9,10,J,Q,K.
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
        """Infinite-deck H17 dealer distribution: 17..21,22,23+ bust."""
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
    def _infinite_optimal_hit_stand(total, soft, dealer_total, dealer_soft, no_blackjack=False):
        """Return (max win probability, bust probability) using Hit/Stand only.

        This deliberately ignores the real shoe.  At every future player state it
        compares standing now with taking another card and follows whichever path
        produces the higher probability of an outright win.  Pushes are not wins.
        """
        total=int(total); soft=bool(soft); dealer_total=int(dealer_total); dealer_soft=bool(dealer_soft)
        if total > 21:
            return 0.0, 1.0
        ddist = (BubbleBlackjackGame._peek_dealer_distribution(dealer_total, dealer_soft)
                 if no_blackjack else
                 BubbleBlackjackGame._infinite_dealer_distribution(dealer_total, dealer_soft))
        # Dealer 22 is a PUSH in Free Blackjack; only 23+ busts are outright wins.
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
                raw, high>0, dealer_total, dealer_soft, no_blackjack)
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
        win,bust=self._infinite_optimal_hit_stand(ptotal,psoft,dtotal,dsoft,self.dealer_blackjack_checked)
        credit = round((self.hand_stake(hand)*win*2.0) * self.CASHOUT_FACTOR, 2)
        return credit,win,bust,0.0

    def instant_surrender(self):
        hand=self.active_hand()
        if not self.can_surrender(hand) or self.animation_running: return
        credit,win_prob,bust_prob,_=self.surrender_offer(hand)
        self.balance+=credit; hand['status']='surrendered'; hand['cashout_credit']=credit
        hand['result']=f'即时兑现 {self.format_money(credit)}'
        hand['settlement']='cashout'
        hand['base_settlement']='cashout'
        hand['double_settlement']='cashout' if float(hand.get('double_added',0.0))>0 else None
        hand['settlement_return']=credit
        self.save_balance()
        self.last_result_lines.append(
            f'手{self.active_hand_index+1} 即时兑现：获胜概率 {win_prob:.2%}，兑现金额 {self.format_money(credit)}')
        self.render_cards(); self.update_display(); self._advance_hand()

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
        if len(set(vals)) != 3:
            return False
        if vals == [1, 2, 3]:
            return True
        # Normal deck sequences include 8-9-10, 9-10-J and 10-J-Q.
        if vals[2] - vals[0] == 2:
            return True
        # Ace may also be high in Q-K-A.
        high_vals = sorted(14 if v == 1 else v for v in vals)
        return high_vals == [12, 13, 14]

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
        for round bookkeeping regardless of stake. Money is only
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
            self._animate_side_bet_profit(key)
        else:
            self.side_bet_return_amounts[key] = 0.0
            self.side_bet_results[key] = f'{label} {odds_text}'

    def _settle_golden_bucket_side_bet(self):
        key = 'Golden Bucket'
        if key in self.side_bet_results:
            return
        count = self._free_chip_count()
        odds = self._golden_bucket_tier(count)
        if odds is None:
            self._credit_side_bet(key, None, '本局没有FREE筹码')
        else:
            self._credit_side_bet(key, odds, f'{count}个FREE筹码')
        self.save_balance()

    def _settle_initial_side_bets(self):
        if not self.hands or len(self.hands[0]['cards']) < 2 or not self.dealer_cards:
            return
        p0, p1 = self.hands[0]['cards'][:2]
        dealer = self.dealer_cards[0]

        # Perfect Pair: 25 / 12 / 6.
        odds = None
        label = '完美对子'
        if p0[1] == p1[1]:
            if p0[0] == p1[0]:
                odds, label = 25, '完美对子'
            elif self._same_color(p0, p1):
                odds, label = 12, '同色对子'
            else:
                odds, label = 6, '杂色对子'
        self._credit_side_bet('Perfect Pair', odds, label)

        trio = [p0, p1, dealer]
        suits_same = len({card[0] for card in trio}) == 1
        ranks_same = len({card[1] for card in trio}) == 1
        straight = self._is_three_card_straight(trio)

        # 21+3: suited trips > straight flush > trips > straight > flush.
        if suits_same and ranks_same:
            result = (100, '同花+点数一样')
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

        # 黄金桶：若玩家起手既不是对子，也不是硬9-11，则本局不可能出现FREE
        # Split/Double，边注立即判输；否则继续等待本局最终FREE数量。
        free_split_start = (p0[1] == p1[1] and p0[1] in {'A', '2', '3', '4', '5', '6', '7', '8', '9'})
        player_total, player_soft = BlackjackEngine.hand_value([p0, p1])
        hard_nine_to_eleven = (not player_soft) and 9 <= player_total <= 11
        if not (free_split_start or hard_nine_to_eleven):
            self._credit_side_bet('Golden Bucket', None, '起手不符合免费条件')

        # 热辣21: player first two cards + dealer up-card.
        all_sevens = all(card[1] == '7' for card in trio)
        totals = self._three_card_totals(trio)
        if all_sevens and suits_same:
            result = (500, '三张7同花')
        elif all_sevens:
            result = (100, '三张7')
        elif 21 in totals and suits_same:
            result = (20, '三张牌同花21点')
        elif 21 in totals:
            result = (4, '三张牌21点')
        elif 20 in totals:
            result = (2, '三张牌20点')
        elif 19 in totals:
            result = (1, '三张牌19点')
        else:
            result = (None, '未中')
        self._credit_side_bet('Hot 21', *result)
        self.save_balance()

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
        # 黄金桶 is final only after all player Free Split/Double actions are known.
        self._settle_golden_bucket_side_bet()
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



    def _start_dealer_turn(self):
        if not self.round_active or self.animation_running or not self.dealer_blackjack_checked:
            return
        if len(self.dealer_cards) < 2:
            return
        needs_draw = self._has_dealer_dependent_side_wager() or any(
            hand.get('status') not in ('bust', 'surrendered', 'even_money', 'blackjack')
            and BlackjackEngine.hand_value(hand.get('cards', []))[0] <= 21
            for hand in self.hands)
        self.dealer_phase_active = True
        self.animation_running = True
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
        self.render_cards()
        self.update_display()
        def revealed():
            if BlackjackEngine.is_blackjack(self.dealer_cards[:2]):
                self._resolve_dealer_blackjack()
            elif needs_draw:
                self._queue(180, self._dealer_draw_until_done)
            else:
                self._queue(220, self._resolve_normal_round)
        self._reveal_dealer_hole(revealed)

    def _dealer_draw_until_done(self):
        total,soft=BlackjackEngine.hand_value(self.dealer_cards)
        # H17: hit soft 17, but stand on hard 17 and every 18+ total.
        if total < 17 or (total == 17 and soft):
            self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
            self._deal_dealer_card_animated(on_complete=lambda:self._queue(180,self._dealer_draw_until_done))
            return
        self._queue(260,self._resolve_normal_round)

    def _resolve_dealer_blackjack(self):
        """Settle an initial dealer Blackjack before all player hand actions."""
        if not self.round_active or self.dealer_blackjack_resolved:
            return
        self.dealer_blackjack_resolved = True
        self.dealer_blackjack_checked = True
        self.dealer_blackjack_found = True
        self.animation_running = True
        self.dealer_phase_active = True
        self._settle_insurance_after_peek(True)
        self._settle_dealer_dependent_side_bets()
        lines = ['庄家起手 Blackjack；玩家不进行分牌或加倍']
        if self.insurance_result:
            lines.append(self.insurance_result)
        for index, hand in enumerate(self.hands):
            if hand.get('status') in ('surrendered', 'even_money'):
                lines.append(f'手{index + 1}：{hand["result"]}')
                continue
            natural = not hand.get('from_split', False) and BlackjackEngine.is_blackjack(hand['cards'])
            if natural:
                hand['settlement'] = hand['base_settlement'] = 'push'
                hand['double_settlement'] = None
                self._finalize_hand_component_credit(hand)
                hand['result'] = 'Blackjack 和局 PUSH'
            else:
                hand['settlement'] = hand['base_settlement'] = 'lose'
                hand['double_settlement'] = 'lose' if self._has_double_component(hand) else None
                hand['free_credit_pending'] = 0.0
                hand['free_credit_paid'] = True
                hand['settlement_return'] = 0.0
                hand['result'] = f'庄家起手 Blackjack -{self.format_money(self.hand_stake(hand))}'
            lines.append(f'手{index + 1}：{hand["result"]}')
        self.last_result_lines.extend(lines)
        self.save_balance()
        self._reveal_dealer_hole(lambda: self._finish_round(dealer_bj=True))

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
            if hand['status'] in ('surrendered', 'even_money'):
                lines.append(f'手{idx + 1}：{hand["result"]}')
                continue

            paid_stake = self.hand_stake(hand)
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
                hand['double_settlement'] = 'lose' if self._has_double_component(hand) else None
                hand['free_credit_pending'] = 0.0; hand['free_credit_paid'] = True
                hand['settlement_return'] = 0.0
                hand['result'] = f'爆牌 -{self.format_money(paid_stake)}'
                lines.append(f'手{idx + 1}：爆牌')
            elif natural:
                hand['settlement'] = 'win'
                hand['base_settlement'] = 'win'
                hand['double_settlement'] = 'win' if self._has_double_component(hand) else None
                credit = self._finalize_hand_component_credit(hand)
                profit = credit - paid_stake
                hand['result'] = f'Blackjack 3:2 +{self.format_money(profit)}'
                lines.append(f'手{idx + 1}：Blackjack 3:2')
            elif dealer_22:
                hand['settlement'] = 'push'
                hand['base_settlement'] = 'push'
                hand['double_settlement'] = 'push' if self._has_double_component(hand) else None
                credit = self._finalize_hand_component_credit(hand)
                hand['result'] = '庄家22点 Push'
                self.dealer_22_main_push = True
                lines.append(f'手{idx + 1}：庄家22点 Push')
            elif dealer_bust or player_total > dealer_total:
                hand['settlement'] = 'win'
                hand['base_settlement'] = 'win'
                hand['double_settlement'] = 'win' if self._has_double_component(hand) else None
                credit = self._finalize_hand_component_credit(hand)
                profit = credit - paid_stake
                if split_two_card_21:
                    hand['result'] = f'分牌21 胜1:1 +{self.format_money(profit)}'
                    lines.append(f'手{idx + 1}：分牌21 胜1:1')
                else:
                    hand['result'] = f'胜 +{self.format_money(profit)}'
                    lines.append(f'手{idx + 1}：胜 {player_total}')
            elif player_total == dealer_total:
                hand['settlement'] = 'push'
                hand['base_settlement'] = 'push'
                hand['double_settlement'] = 'push' if self._has_double_component(hand) else None
                credit = self._finalize_hand_component_credit(hand)
                hand['result'] = '分牌21 和局 Push' if split_two_card_21 else '和局 Push'
                lines.append(f'手{idx + 1}：{"分牌21 " if split_two_card_21 else ""}Push {player_total}')
            else:
                hand['settlement'] = 'lose'
                hand['base_settlement'] = 'lose'
                hand['double_settlement'] = 'lose' if self._has_double_component(hand) else None
                hand['free_credit_pending'] = 0.0; hand['free_credit_paid'] = True
                hand['settlement_return'] = 0.0
                hand['result'] = f'输 -{self.format_money(paid_stake)}'
                lines.append(f'手{idx + 1}：输 {player_total}')

        self.last_result_lines.extend(lines)
        self._finish_round(dealer_bj=False)

    def _calculate_last_win_amount(self):
        """Total money returned to the player's balance for this round.

        V16 intentionally includes returned stake: normal wins, Blackjack returns,
        PUSH, instant cashout/Even Money, side-bet credits and insurance
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
        """Keep original chips on-table and deal cash winnings to their left."""
        if self._closing or self.settlement_running:
            return
        # Paid returns were credited by the existing evaluators. FREE returns keep
        # their original deferred-credit rule until the cash return reaches the rack.
        self.animation_running = False
        self.save_balance()
        self.last_win_amount = self._calculate_last_win_amount()
        self.show_last_win = True
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_SETTLING)
        self.settlement_running = True
        self.settlement_visual_stage = 'paying'
        self.flash_mode = None
        self.settlement_flash_step = 0
        self.flash_winning_side_bets = set()
        self.flash_winning_hand_indices = set()
        self.flash_main_bet = self.flash_main_push_only = self.flash_insurance_rule = False
        for tag in ('win_flash_area', 'side_bet_win_odds', 'side_bet_progress_badge'):
            self.canvas.delete(tag)
        self._restore_betting_spot_label_colors()
        profits = [row for row in self._settlement_chip_rows()
                   if row['role'] == 'profit' and row['key'][0] != 'side']
        self.pending_profit_chips.update(row['key'] for row in profits)
        self.render_cards()
        self.update_display()
        self._animate_losing_chips_out()
        self._fade_dealer_22_notice(self.dealer_22_main_push)

        def display_outcome():
            if self._closing or not self.settlement_running:
                return
            self.settlement_visual_stage = 'display'
            self._render_settlement_chips()
            self._queue(1800, self._finish_flash_with_chip_return)

        if not profits:
            self._queue(440 if self.pending_profit_chips else 300, display_outcome)
            return
        pending = [len(profits)]
        def arrived(row):
            self.pending_profit_chips.discard(row['key'])
            self._render_settlement_chips()
            pending[0] -= 1
            if not pending[0]:
                display_outcome()
        for index, row in enumerate(profits):
            self._animate_settlement_chips([(575.0, 43.0, row['amount'], row['radius'])],
                row['pos'], 440, f'settlement_profit_fly_{index}', lambda r=row: arrived(r))

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

        self.settlement_visual_stage = None
        self.pending_profit_chips = set()
        self._opening_wager_animation = False
        self.round_active=False; self.round_original_bet=0.0
        self.round_side_bets={key:0.0 for key in self.SIDE_BET_KEYS}
        self.side_bet_results={}; self.side_bet_return_amounts={}
        self.side_bet_hit_odds={}; self.side_bet_hit_labels={}
        self.side_bet_early_collected=set()
        self.flash_winning_side_bets=set(); self.flash_main_bet=False; self.flash_main_push_only=False
        self.dealer_22_main_push=False
        self.flash_winning_hand_indices=set(); self.flash_insurance_rule=False
        self.settlement_running=False; self.settlement_flash_step=0; self.flash_mode=None
        self.dealer_hole_hidden = False
        self.dealer_blackjack_checked = False
        self.dealer_blackjack_found = False
        self.dealer_blackjack_resolved = False
        self.insurance_resolved = False
        self.insurance_early_collected = False
        self.dealer_phase_active=False
        self.round_deal_sequence=[]; self.insurance_bet=0.0; self.insurance_result=''
        self.insurance_return_amount=0.0; self.insurance_chip_visible=False; self.ace_decision_mode=None
        self.hands=[]; self.dealer_cards=[]; self.active_hand_index=0; self.split_actions=0

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
        elif self.ace_decision_mode=='even_money':
            self._set_button(self.decision_buttons.get('accept'),True,'立刻赔付')
            self._set_button(self.decision_buttons.get('decline'),True,'赌！')

        self._set_round_control_visibility(self.round_active)
        hand=self.active_hand()
        active=bool(self.round_active and self.dealer_blackjack_checked
                    and not self.animation_running and not self.settlement_running
                    and not self.ace_decision_mode and hand and hand['status']=='active'
                    and not hand.get('needs_split_draw',False))
        free_double_mode = bool(active and self.is_free_double(hand))
        free_split_mode = bool(active and self.is_free_split(hand))
        self._set_action_button_style('hit', False)
        self._set_action_button_style('stand', False)
        self._set_action_button_style('double', free_double_mode)
        self._set_action_button_style('split', free_split_mode)
        self._set_action_button_style('surrender', False)
        self._set_button(self.action_buttons.get('hit'),active and self.can_hit(hand),'要牌')
        self._set_button(self.action_buttons.get('stand'),active,'停牌')
        double_text = '免费加倍' if free_double_mode else '加倍'
        split_text = '免费分牌' if free_split_mode else '分牌'
        self._set_button(self.action_buttons.get('double'), active and self.can_double(hand), double_text)
        self._set_button(self.action_buttons.get('split'), active and self.can_split(hand), split_text)
        self._refresh_free_rule_flash()
        surrender_enabled=active and self.can_surrender(hand); cashout_text='兑现金额\n$0.00'
        if surrender_enabled:
            credit,win_prob,_bust,_=self.surrender_offer(hand); cashout_text=f'兑现金额\n{self.format_money(credit)}'
        self._set_button(self.action_buttons.get('surrender'),surrender_enabled,cashout_text)
        for _key,spot in self.bet_spots.items():
            self.canvas.itemconfigure(
                spot['rect'], fill=spot['normal_fill'],
                outline='' if spot['shape'] == 'oval' else spot.get('normal_outline', '#9de46f'),
                width=spot.get('normal_width', 3))
            self.canvas.itemconfigure(spot['label'], fill=spot.get('normal_label_fill', 'white'))

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

        dialog.title('免费黑杰克 · 游戏说明')

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
                            ('玩家决策', '庄家确认无黑杰克后，根据手牌选择要牌、停牌、加倍、分牌等可用操作。'),
                            ('庄家开牌', '庄家依本游戏的停牌规则补牌并亮出结果。'),
                            ('结算', '获胜金额放在原注左侧；输/PUSH的FREE立即回收，赢的FREE在现金返回筹码区时回收。'),
                        ],
                        [],
                    ],
                    [
                        '游戏玩法与连续洗牌说明',
                        '8副完整牌 · 美式底牌 / 庄家查牌 · H17',
                        [
                            ('基本目标', '尽量让手牌接近21点而不爆牌，并击败庄家。\n庄家软17要牌、硬17停牌；\n庄家最终22点时普通主注退还。\n玩家天然黑杰克优先，仍按3:2获胜。'),
                            ('免费分牌 / 免费加倍', '起手或分牌后的两张牌为A–9同点对子，可免费分牌；\n两张牌为硬9–11，可免费加倍。\nFREE筹码不扣余额，获胜金额按正常下注方式赔付，在原注左侧显示。\n输或PUSH：主注结算时立即回收FREE；赢：现金返回筹码区时才收走FREE。'),
                            ('美式底牌与庄家查牌', '起手发牌：玩家 → 庄家 → 玩家 → 庄家。\n庄家第二张为盖住的底牌；庄家检查黑杰克后才开放玩家动作。\n庄家起手黑杰克时立即结算，玩家不能先分牌或加倍取得FREE筹码。'),
                            ('庄家A与保险', '庄家明牌A时先决定是否购买保险，再检查底牌，保险获胜利润2:1。\n玩家天然黑杰克遇庄家A时，可选择“立刻赔付”按1:1锁定，或选择“赌！”。\n庄家无黑杰克时保险立即判输；玩家天然黑杰克正常按3:2获胜。'),
                            ('黄金桶资格', '若玩家起手既不符合A–9免费分牌，也不是硬9–11，黄金桶立即输。\n如果本来已有FREE机会，但玩家选择 要牌、停牌 或 付款加倍，黄金桶同样立即判输。\n庄家起手黑杰克时没有FREE动作机会，黄金桶按0个FREE结算为输。'),
                            ('连续发牌', '牌张跨局保留在连续洗牌系统中，不建立或切换独立牌靴。'),
                            ('牌张回收', '每局结束后，已发出的牌进入弃牌区，由连续洗牌机按规则重新混入牌仓。'),
                            ('无需换靴', '不使用剩余牌阈值、切牌或烧牌流程；\n下一局直接由连续洗牌机供牌。'),
                        ],
                        [],
                    ],
                    [
                        '玩家决策按钮',
                        [
                            ('要牌  HIT', '再要一张牌。\n若原本有FREE机会，选择Hit会令黄金桶立即输。'),
                            ('停牌  STAND', '结束当前手。\n若原本有FREE机会，选择Stand会令黄金桶立即输。'),
                            ('加倍  DOUBLE', '付款加倍需追加与该手原注相同金额，只拿一张牌后自动停牌。'),
                            ('分牌  SPLIT', '普通分牌需要支付同额追加注\n10/J/Q/K使用付款分牌。'),
                            ('免费加倍  FREE DOUBLE', '两张牌为硬9–11时出现。\n不扣余额并获得FREE筹码。'),
                            ('免费分牌  FREE SPLIT', '两张牌为A–9同点对子时出现。\n不扣余额并分牌。'),
                            ('兑现金额  CASH OUT', '符合条件时显示即时兑现金额，金额依据当前胜率动态计算。'),
                            ('庄家明牌A的决策', '正常询问：购买保险 / 不购买\n玩家黑杰克：立刻赔付 / 赌！'),
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
                                    ['完美对子', '每项最高$100,000'],
                                    ['21+3', '每项最高$100,000'],
                                    ['黄金桶', '每项最高$100,000'],
                                    ['22点', '每项最高$100,000'],
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
                        '主注与附加赔付',
                        '赔率表示利润赔率；\n正常中奖同时返还下注本金',
                        [],
                        [
                            (
                                '主注 / 保险 / FREE',
                                ['条件', '赔率'],
                                [
                                    ['普通主注获胜', '1:1'],
                                    ['玩家天然黑杰克', '3:2'],
                                    ['玩家黑杰克 + 庄家A选择“立刻赔付”', '1:1'],
                                    ['保险中奖（庄家黑杰克）', '2:1'],
                                    ['庄家最终22点：普通主注', '退还'],
                                    ['庄家最终22点：玩家天然黑杰克', '3:2'],
                                    ['分牌后两张牌组成21点', '1:1'],
                                    ['FREE筹码对应部分获胜', '赢1×原注'],
                                    ['FREE筹码对应部分输 / PUSH', '收回'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '边注赔付表',
                        '六个边注 · 每个最高 $100K',
                        [],
                        [
                            (
                                '完美对子',
                                ['牌型 / 条件', '赔率 / 说明'],
                                [
                                    ['完美对子', '25:1'],
                                    ['同色对子', '12:1'],
                                    ['杂色对子', '6:1'],
                                ],
                            ),
                            (
                                '21+3',
                                ['牌型 / 条件', '赔率 / 说明'],
                                [
                                    ['同花 + 点数一样', '100:1'],
                                    ['同花顺', '40:1'],
                                    ['三条', '30:1'],
                                    ['顺子', '10:1'],
                                    ['同花', '5:1'],
                                ],
                            ),
                            (
                                '黄金桶',
                                ['牌型 / 条件', '赔率 / 说明'],
                                [
                                    ['7个FREE筹码', '1000:1'],
                                    ['6个FREE筹码', '299:1'],
                                    ['5个FREE筹码', '100:1'],
                                    ['4个FREE筹码', '60:1'],
                                    ['3个FREE筹码', '30:1'],
                                    ['2个FREE筹码', '10:1'],
                                    ['1个FREE筹码', '3:1'],
                                ],
                            ),
                            (
                                '热辣21',
                                ['牌型 / 条件', '赔率 / 说明'],
                                [
                                    ['三张7同花', '500:1'],
                                    ['三张7', '100:1'],
                                    ['三张牌同花并等于21', '20:1'],
                                    ['三张牌等于21', '4:1'],
                                    ['三张牌等于20', '2:1'],
                                    ['三张牌等于19', '1:1'],
                                ],
                            ),
                            (
                                '22点',
                                ['牌型 / 条件', '赔率 / 说明'],
                                [
                                    ['庄家22且全部牌同花', '50:1'],
                                    ['庄家22且全部牌同色', '20:1'],
                                    ['庄家22且杂色', '8:1'],
                                ],
                            ),
                            (
                                '爆牌!',
                                ['牌型 / 条件', '赔率 / 说明'],
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
                            ('比较方法', 'A 可计 1 或 11，J、Q、K 计 10；\n免费分牌、免费加倍及庄家 22 按特别规则处理。'),
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
                        '8副完整牌 · 美式底牌 / 庄家查牌 · H17',
                        [
                            ('连续洗牌机', '使用8副完整52张牌，共416张；\n所有牌局均由CSM_Shuffler连续洗牌机发牌。'),
                        ],
                        [],
                    ],
                    [
                        '重要提示',
                        '',
                        [
                            ('21+3顺子', '本版本使用完整52张牌，按照正常连续牌序判断。\n例如A-2-3至Q-K-A也属于顺子。'),
                            ('分A规则', 'A-A属于免费分牌。\n分A后每手通常只补一张牌；\n如果再次得到A并且还没有达到最多4手限制，可以继续免费分A。'),
                            ('黄金桶即时失效', '黄金桶并非单纯等待最终FREE数量。\n起手没有FREE资格时会立即输；\n本可以 免费分牌 或 免费加倍 却选择 要牌 、停牌 或 付款加倍时，黄金桶也会立即判输。'),
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

        tk.Label(header, text='免费黑杰克 · 游戏说明', font=(font_name, 20, 'bold'),

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
                button.configure(
                    bg='#e6d9b9' if idx == index else SIDEBAR,
                    fg=GOLD if idx == index else MUTED
                )

            page_title, subtitle, cards = manual_pages[index]

            top = tk.Frame(content, bg=BG)
            top.pack(fill=tk.X, padx=14, pady=(7, 2))

            tk.Label(
                top, text=page_title, font=(font_name, 20, 'bold'),
                fg=GOLD, bg=BG, anchor='w', justify=tk.LEFT,
                wraplength=690
            ).pack(fill=tk.X)

            if subtitle:
                tk.Label(
                    top, text=subtitle, font=(font_name, 14),
                    fg=MUTED, bg=BG, anchor='w', justify=tk.LEFT,
                    wraplength=690
                ).pack(fill=tk.X, pady=(3, 0))

            for card_data in cards:
                # 兼容没有副标题的三项说明卡。
                if len(card_data) == 3:
                    card_title, rules, tables = card_data
                    card_subtitle = ''
                else:
                    card_title, card_subtitle, rules, tables = card_data

                card = tk.Frame(
                    content, bg=PANEL, highlightbackground=BORDER,
                    highlightcolor=BORDER, highlightthickness=1, bd=0
                )
                card.pack(fill=tk.X, padx=10, pady=7)

                head = tk.Frame(card, bg=PANEL)
                head.pack(fill=tk.X, padx=16, pady=(12, 5))

                tk.Label(
                    head, text=card_title, font=(font_name, 16, 'bold'),
                    fg=GOLD, bg=PANEL, anchor='w', justify=tk.LEFT,
                    wraplength=680
                ).pack(fill=tk.X)

                if card_subtitle:
                    tk.Label(
                        head, text=card_subtitle, font=(font_name, 14),
                        fg=MUTED, bg=PANEL, anchor='w', justify=tk.LEFT,
                        wraplength=680
                    ).pack(fill=tk.X)

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

        if not self.round_active:
            self.balance += self.current_bet + sum(self.current_side_bets.values())
            self.current_bet = 0.0
            self.current_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
        elif self.settlement_running:
            # Paid settlement credits were already applied by the resolver. Only
            # FREE winnings intentionally deferred until the return animation remain.
            self.balance += sum(
                max(0.0, float(hand.get('free_credit_pending', 0.0)))
                for hand in self.hands if not hand.get('free_credit_paid', False)
            )
        else:
            unresolved = 0.0
            for hand in self.hands:
                if (hand.get('status') not in ('surrendered', 'even_money')
                        and hand.get('settlement') is None):
                    unresolved += self.hand_stake(hand)
            if not self.insurance_resolved:
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
        self.canvas.tag_raise('chip_animation')

    def _update_main_spot_visibility_original(self):
        playing = bool(self.round_active or self.settlement_running or
                       (self.animation_running and not self.accept_bets))
        state = 'hidden' if playing else 'normal'
        for item in (self.bet_spots['MAIN']['rect'], self.bet_spots['MAIN']['label']):
            self.canvas.itemconfigure(item, state=state)

    def _update_main_spot_visibility(self):
        self._update_main_spot_visibility_original()
        for spot in self.bet_spots.values():
            if spot.get('shape') == 'oval' and spot.get('surface_tag'):
                state = self.canvas.itemcget(spot['rect'], 'state')
                self.canvas.itemconfigure(spot['surface_tag'], state=state)
                self.canvas.itemconfigure(spot['title_tag'], state=state)
        self._raise_wager_chips()

    def _player_hand_geometry(self, count=None):
        n = max(1, min(self.MAX_HANDS, int(count if count is not None else len(self.hands) or 1)))
        x0, x1 = 22.0, 1128.0
        lane_width = (x1 - x0 - 24.0) / n
        return [(x0 + 12 + index * lane_width, x0 + 12 + (index + 1) * lane_width,
                 x0 + 12 + (index + 0.5) * lane_width, index, n)
                for index in range(n)]

    def _player_card_rotation(self, hand, card_index):
        return 90 if card_index == 2 and self._has_double_component(hand) else 0

    def _player_card_position(self, hand, geometry, card_index):
        left, right, cx, _order, n = geometry
        main_x, main_y = self.bet_spots['MAIN']['chip_pos']
        first_x = (main_x if n == 1 else cx) - self.CARD_WIDTH / 2
        first_y = main_y - self.MAIN_WAGER_LIFT - self.CARD_HEIGHT - self.WAGER_CHIP_RADIUS - self.CARD_WAGER_GAP
        # Match Classic's fixed fan spacing so later hits keep earlier cards in place.
        fan_step = min(44.0, max(0.0, (right - 8 - first_x - self.CARD_WIDTH) / 3))
        index = max(0, int(card_index))
        x = first_x + fan_step * index
        if index <= 3:
            y = first_y - 24.0 * index
        elif index <= 6:
            y = first_y - 72.0 + 24.0 * (index - 3)
        else:
            y = first_y - 24.0 * (index - 6)
        if self._player_card_rotation(hand, index):
            x -= (self.CARD_HEIGHT - self.CARD_WIDTH) / 2
            y += (self.CARD_HEIGHT - self.CARD_WIDTH) / 2
            x += 15
            y -= 15
        return x, y

    def _dealer_badge_fill(self):
        if self.dealer_hole_hidden:
            return '#ffffff'
        total, _soft = BlackjackEngine.hand_value(self.dealer_cards)
        if total == 22:
            return self.PUSH_BLUE
        if total > 21:
            return '#e34848'
        return '#f3cf55' if self.dealer_phase_active else '#ffffff'

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

    def _render_settlement_chips(self):
        self.update_bet_chips()
        self.canvas.delete('hand_wager')
        self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._raise_wager_chips()

    def _draw_outcome_rows(self, rows):
        if self.settlement_visual_stage == 'returning':
            return
        for row in sorted(rows, key=lambda row: row['role'] not in ('principal', 'free')):
            if row['key'] in self.pending_profit_chips:
                continue
            if row['role'] == 'free':
                self._draw_free_chip(*row['pos'], tags=row['tags'], radius=row['radius'])
            else:
                self._draw_baccarat_chip(*row['pos'], row['amount'],
                                        tags=row['tags'], radius=row['radius'])

    def _main_wager_rows(self):
        """Separate paid principal, FREE markers and cash winnings for each hand."""
        if (not self.round_active or self._opening_wager_animation
                or self.settlement_visual_stage == 'returning'):
            return []
        rows = []
        layout = self._main_split_wager_layout()
        for index, hand in enumerate(self.hands):
            base_x, base_y = layout[index]['base']
            for component in ('base', 'double'):
                if component == 'base':
                    nominal = float(hand.get('base_bet', 0.0))
                    is_free = bool(hand.get('base_is_free', False))
                    pending = bool(hand.get('free_base_pending', False))
                else:
                    free_amount = float(hand.get('free_double_amount', 0.0))
                    is_free = free_amount > 0.0
                    nominal = free_amount if is_free else float(hand.get('double_added', 0.0))
                    pending = bool(hand.get('free_double_pending', False))
                if nominal <= 0.0 or pending:
                    continue
                key = ('main', index, component)
                tags = ('hand_wager', f'hand_wager_{index}', f'{component}_wager',
                        f'hand_{index}_{component}_chip')
                position = layout[index][component]
                # Classic's left-to-right order is Double profit, base profit,
                # original base chip, original Double chip, with a 2px gap.
                profit_position = (base_x - ((2*self.CHIP_PITCH) if component == 'double' else self.CHIP_PITCH), base_y)
                returned = self._component_return_amount(hand, component) if self.settlement_running else None
                if is_free:
                    if self.settlement_running and hand.get(f'{component}_settlement') != 'win':
                        continue
                    rows.append(dict(key=(*key, 'free'), role='free', amount=nominal,
                        pos=position, radius=self.WAGER_CHIP_RADIUS, tags=(*tags, 'free_wager')))
                    # Only winning FREE stakes remain during outcome display.
                    # Their cash winnings sit on the left; collect these FREE
                    # stakes when the cash chips return to the rack.
                    if returned is not None and returned > 0.0:
                        rows.append(dict(key=(*key, 'profit'), role='profit', amount=returned,
                            pos=profit_position, radius=self.WAGER_CHIP_RADIUS, tags=(*tags, 'profit_chip')))
                else:
                    rows.extend(self._outcome_chip_rows(key, nominal, returned,
                        position, self.WAGER_CHIP_RADIUS, tags, profit_position=profit_position))
        return rows

    def _animate_starting_wagers(self, on_complete):
        """Lift the MAIN wager 60 px in 220 ms before dealing, as in Classic."""
        starts, ends = {}, {}
        self._opening_wager_animation = True
        layout = self._main_split_wager_layout()
        for index, hand in enumerate(self.hands):
            tag = f'opening_wager_{index}'
            start = self.bet_spots['MAIN']['chip_pos']
            self._draw_baccarat_chip(*start, hand['base_bet'],
                tags=('opening_wager', tag), radius=self.WAGER_CHIP_RADIUS)
            starts[tag], ends[tag] = start, layout[index]['base']
        def landed():
            self.canvas.delete('opening_wager')
            self._opening_wager_animation = False
            self.render_cards()
            self.update_display()
            if callable(on_complete):
                on_complete()
        self._animate_canvas_positions(starts, ends, duration_ms=220, on_complete=landed)

    def _animate_side_bet_profit(self, key):
        if self._closing or self.settlement_visual_stage == 'returning':
            return
        spot = self.bet_spots.get(key)
        if not spot:
            return
        rows = self._outcome_chip_rows(('side', key), self.round_side_bets.get(key, 0.0),
            self.side_bet_return_amounts.get(key, 0.0), spot['chip_pos'], self.WAGER_CHIP_RADIUS,
            ('bet_chip_dynamic', spot['tag']))
        for row in rows:
            if row['role'] != 'profit':
                continue
            self.pending_profit_chips.add(row['key'])
            def arrived(k=row['key']):
                self.pending_profit_chips.discard(k)
                self.update_bet_chips()
            self._animate_settlement_chips([(575.0, 43.0, row['amount'], self.WAGER_CHIP_RADIUS)],
                row['pos'], 440, f'side_profit_fly_{self.SIDE_BET_KEYS.index(key)}', arrived)

    def _settlement_chip_rows(self):
        """Cash principal and cash profits; gold FREE markers are never cash returns."""
        rows = [row for row in self._main_wager_rows() if row['role'] != 'free']
        for key, stake in self.round_side_bets.items():
            if stake > 0.0:
                spot = self.bet_spots[key]
                rows.extend(self._outcome_chip_rows(('side', key), stake,
                    self.side_bet_return_amounts.get(key, 0.0), spot['chip_pos'], self.WAGER_CHIP_RADIUS,
                    ('bet_chip_dynamic', spot['tag'])))
        if self.insurance_bet > 0.0:
            rows.extend(self._outcome_chip_rows(('insurance',), self.insurance_bet,
                self.insurance_return_amount, self.rule_strip_chip_pos, self.INSURANCE_CHIP_RADIUS, ('insurance_chip',)))
        return rows

    def _render_back_card(self, x, y, tags):
        if self.external_back_image is not None:
            return self.canvas.create_image(x, y, image=self.external_back_image, anchor='nw', tags=tags)
        return self.canvas.create_rectangle(x, y, x+self.CARD_WIDTH, y+self.CARD_HEIGHT,
            fill='#253e66', outline='#d7c46a', width=2, tags=tags)

    def _reveal_dealer_hole(self, on_complete=None):
        """Flip the already-dealt second card in place; never draw a replacement card."""
        if not self.dealer_hole_hidden or len(self.dealer_cards) < 2:
            if callable(on_complete):
                on_complete()
            return
        card = self.dealer_cards[1]
        x, y = self._dealer_card_target(1)
        self.canvas.delete('dealer_hole_card')
        item = self._render_back_card(x, y, tags=('dealer_hole_flip', 'animation_card'))
        def frame(step=0):
            if step > 12:
                self.canvas.delete('dealer_hole_flip')
                self._temp_flip_images.pop(item, None)
                self.dealer_hole_hidden = False
                self.render_cards()
                self.update_display()
                if callable(on_complete):
                    on_complete()
                return
            use_back = step <= 6
            ratio = 1.0 - step / 6.0 if use_back else (step - 6) / 6.0
            width = max(1, round(self.CARD_WIDTH * ratio))
            left = x + (self.CARD_WIDTH - width) / 2
            if self.canvas.type(item) == 'image':
                photo = self._create_scaled_flip_image(card, width, self.CARD_HEIGHT, use_back=use_back)
                if photo is not None:
                    self._temp_flip_images[item] = photo
                    self.canvas.itemconfigure(item, image=photo)
                    self.canvas.coords(item, left, y)
            else:
                self.canvas.coords(item, left, y, left+width, y+self.CARD_HEIGHT)
                self.canvas.itemconfigure(item, fill='#253e66' if use_back else '#f4efe4')
            self._raise_wager_chips()
            self._queue(20, frame, step + 1)
        frame(0)

    def _settle_insurance_after_peek(self, dealer_blackjack):
        if self.insurance_resolved:
            return
        self.insurance_resolved = True
        if self.insurance_bet <= 0.0:
            return
        if dealer_blackjack:
            credit = self.insurance_bet * (1.0 + self.INSURANCE_PROFIT)
            self.balance += credit
            self.insurance_return_amount = credit
            self.insurance_result = f'保险胜 +{self.format_money(credit - self.insurance_bet)}'
        else:
            self.insurance_return_amount = 0.0
            self.insurance_result = f'保险输 -{self.format_money(self.insurance_bet)}'
            self.insurance_early_collected = True
            self._render_insurance_chip()
            x, y = self.rule_strip_chip_pos
            self._animate_settlement_chips([(x, y, self.insurance_bet, self.INSURANCE_CHIP_RADIUS)],
                lambda sx, sy: (sx, -35.0), 300, 'insurance_loss_fly', easing='smooth')
        self.save_balance()

    def _peek_dealer_blackjack(self):
        if self._closing or not self.round_active or self.dealer_blackjack_checked:
            return
        if len(self.dealer_cards) < 2:
            return
        self.animation_running = True
        self.update_display()
        def checked():
            self.dealer_blackjack_checked = True
            self.dealer_blackjack_found = BlackjackEngine.is_blackjack(self.dealer_cards[:2])
            self._settle_insurance_after_peek(self.dealer_blackjack_found)
            if self.dealer_blackjack_found:
                # End the main game before any Free Split/Double can create a
                # Golden Bucket tier; the original hole card is then revealed.
                self._resolve_dealer_blackjack()
            else:
                self._continue_after_dealer_peek()
        self._queue(180, checked)

    def _continue_after_dealer_peek(self):
        self.animation_running = False
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
        self.render_cards()
        self.update_display()
        if self._single_natural_blackjack() or self.hands[0].get('status') == 'even_money':
            self._queue(220, self._start_dealer_turn)

    @staticmethod
    @lru_cache(maxsize=None)
    def _peek_dealer_distribution(up_total, up_soft):
        """Use public up-card information, conditioned on the completed non-BJ peek."""
        outcomes = ((11, 1/13),) + tuple((v, 1/13) for v in range(2, 10)) + ((10, 4/13),)
        allowed = [(value, prob) for value, prob in outcomes
                   if not (up_total == 11 and up_soft and value == 10)
                   and not (up_total == 10 and not up_soft and value == 11)]
        weight = sum(prob for _value, prob in allowed)
        result = [0.0] * 7
        for value, prob in allowed:
            total = up_total + value
            aces = int(up_soft) + int(value == 11)
            while total > 21 and aces:
                total -= 10
                aces -= 1
            dist = BubbleBlackjackGame._infinite_dealer_distribution(total, aces > 0)
            for index, chance in enumerate(dist):
                result[index] += prob / weight * chance
        return tuple(result)

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
    root.title('免费黑杰克')
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
