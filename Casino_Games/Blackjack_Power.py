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

# Double Bet Blackjack V29 — no 9/10 ranks / selectable 2X-4X double
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

BLACKJACK_VERSION = "V29-CSM-NO9-10-D2-4"

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
class BubbleBlackjackGame(tk.Frame):
    WIDTH = 1150
    HEIGHT = 750
    GAME_X0 = 12
    GAME_X1 = 1138
    HISTORY_X0 = 778  # compatibility only; no right-side panel in Blackjack
    HISTORY_X1 = 1138

    BG = '#17120f'
    PANEL = '#211811'
    PANEL_LINE = '#665240'
    FELT = '#083f38'
    FELT_2 = '#0c5148'
    LINE = '#c3d5ca'
    GOLD = '#e7d36c'
    PLAYER_BLUE = '#3d67d8'
    DEALER_RED = '#d94a4e'
    TIE_GREEN = '#43a665'

    MIN_BET = 100.0
    MAX_MAIN_BET = 500_000.0
    MAX_SIDE_BET = 100_000.0
    MAX_SPLIT_ACTIONS = 3       # up to 4 player hands (3 split actions)
    MAX_HANDS = 4
    BLACKJACK_PROFIT = 1.5      # 3:2
    INSURANCE_PROFIT = 2.0      # 2:1
    SPLIT_ACES_ONE_CARD_ONLY = True
    SIDE_BET_KEYS = ('Perfect Pair', '21+3', 'Open Card Luck', 'Crazy 7', 'Hot 21', 'Bust!')
    SIDE_BET_LABELS = {
        'Perfect Pair': '完美对子',
        '21+3': '21+3',
        'Open Card Luck': '明牌运气',
        'Crazy 7': '疯狂7',
        'Hot 21': '热辣21',
        'Bust!': '爆牌！',
    }
    SIDE_BET_ODDS_TEXT = {
        'Perfect Pair': '21/10/5:1',
        '21+3': '90/35/25/10/4:1',
        'Open Card Luck': '70/7/3/3:1',
        'Crazy 7': '1500/325/100/18/4:1',
        'Hot 21': '400/80/20/4/2/1:1',
        'Bust!': '200/80/40/7.5/1.5/1:1',
    }

    M_CHIP_COLOR = '#102d47'

    # phase_text is intentionally restricted to these game-state messages.
    PHASE_BETTING = '倍注黑杰克 · 请下注'
    PHASE_INSURANCE = '倍注黑杰克 · 保险？'
    PHASE_EVEN_MONEY = '倍注黑杰克 · 立刻获胜？'
    PHASE_PLAYING = '倍注黑杰克 · 游戏中'
    PHASE_DOUBLE = '倍注黑杰克 · 选择加倍倍数'
    PHASE_SETTLING = '倍注黑杰克 · 结算中'

    CHIP_SPECS = [
        (100, '#202020', '100'),
        (500, '#d780c0', '500'),
        (1000, '#ab0058', '1K'),
        (5000, '#ba3438', '5K'),
        (10000, '#70439a', '10K'),
        (50000, '#2e7542', '50K'),
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

        # One stable local game identity is used so an orderly restart can
        # recover any chamber lease left by the previous instance.
        import uuid
        self.csm_game_id = f"DoubleBetBlackjack:{self.username or 'local'}:{uuid.uuid4().hex}"
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
        self.double_choice_mode = False
        self.bet_layout_mode = 'home'
        self.previous_round_cards_present = False
        self.hands = []
        self.active_hand_index = 0
        self.dealer_cards = []
        self.round_deal_sequence = []
        self.round_discarded_cards = []
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
        self.pending_bet_animation = {'MAIN': 0.0, **{key: 0.0 for key in self.SIDE_BET_KEYS}}
        self._closing = False
        self.last_result_lines = []  # internal only; never shown to the player
        self.runtime_data_file = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..',
                'A_Logs',
                'Json',
                'Blackjack_Classic.json'
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
        self.double_choice_buttons = {}
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

        try:
            top.geometry('1150x750+50+10')
            top.resizable(False, False)
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
            os.path.join(current, 'A_Tools', 'Card', 'Poker1'),
            os.path.join(os.path.dirname(current), 'A_Tools', 'Card', 'Poker1'),
            os.path.join(os.path.dirname(os.path.dirname(current)), 'A_Tools', 'Card', 'Poker1'),
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
                        base = Image.open(path).convert('RGBA').resize((100, 140), resample)
                        self.external_card_pil[(suit, rank)] = base
                        self.external_card_images[(suit, rank)] = ImageTk.PhotoImage(base, master=self)
                back_path = os.path.join(directory, 'Background.png')
                if os.path.exists(back_path):
                    back = Image.open(back_path).convert('RGBA').resize((100, 140), resample)
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
        return image

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
        # V11 keeps the V8 162px/192px dealer/player heights.  During betting
        # the player zone is at the original V8 position (182..374).  After 开牌
        # it translates down 40px to make room for the 30px rules bar, and after
        # settlement it returns to the original position.  Dealer never moves.
        x0, y0, x1, y1 = self.GAME_X0, 4, self.GAME_X1, 422
        self.animation_panel = (x0, y0, x1, y1)
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')

        self.player_zone_home = (x0 + 8, 182.0, x1 - 8, 374.0)
        self.player_zone_round = (x0 + 8, 222.0, x1 - 8, 414.0)
        self.player_label_home = (x0 + 22, 195.0)
        self.player_label_round = (x0 + 22, 235.0)
        self.player_zone_mode = 'home'
        self.dealer_zone_rect = c.create_rectangle(
            x0 + 8, y0 + 8, x1 - 8, 174,
            fill='#4b1e22', outline='#865158', width=2, tags='static')
        self.player_zone_rect = c.create_rectangle(
            *self.player_zone_home, fill='#102d47', outline='#4c6682', width=2, tags='static')
        c.create_text(x0 + 22, y0 + 22, anchor='nw', text='庄家 DEALER',
                      font=(self.cn_font, 17, 'bold'), fill='#ffb5b9', tags='static')
        self.player_zone_title = c.create_text(
            *self.player_label_home, anchor='nw', text='玩家 PLAYER',
            font=(self.cn_font, 17, 'bold'), fill='#b9d6ff', tags='static')

        self.dealer_total_text = c.create_text(
            x0 + 24, 161, anchor='w', text='', font=(self.cn_font, 13, 'bold'),
            fill='white', state='hidden', tags=('dynamic', 'cards'))
        self.phase_text = c.create_text(
            (x0 + x1) / 2, 18, text=self.PHASE_PLAYING,
            font=(self.cn_font, 13, 'bold'), fill=self.GOLD, tags=('dynamic', 'cards'))

        # Exact 30px-high dealer/player rule bar.
        self.rule_strip_bounds = (250.0, 182.0, 900.0, 212.0)
        rx0, ry0, rx1, ry1 = self.rule_strip_bounds
        self.rule_strip_rect = c.create_rectangle(
            rx0, ry0, rx1, ry1, fill='#0c5148', outline='#d7e8df', width=1,
            state='hidden', tags=('round_rule_strip',))
        self.rule_strip_text = c.create_text(
            (rx0 + rx1) / 2, (ry0 + ry1) / 2,
            text='庄家任何17点停牌   移除全部9点和10点   保险2:1   黑杰克3:2',
            font=(self.cn_font, 12, 'bold'), fill='white', state='hidden',
            tags=('round_rule_strip', 'rule_strip_text'))
        # V11: insurance never makes the wording move or split.  The chip is
        # layered above the BAR at its horizontal centre; the full sentence stays
        # exactly where it is.  Legacy split-text items remain hidden for API
        # compatibility with the settlement colour helper.
        self.rule_strip_left_text = c.create_text(
            545, (ry0 + ry1) / 2, anchor='e', text='',
            font=(self.cn_font, 12, 'bold'), fill='white', state='hidden',
            tags=('round_rule_strip', 'rule_strip_split_text'))
        self.rule_strip_right_text = c.create_text(
            605, (ry0 + ry1) / 2, anchor='w', text='',
            font=(self.cn_font, 12, 'bold'), fill='white', state='hidden',
            tags=('round_rule_strip', 'rule_strip_split_text'))
        self.rule_strip_chip_pos = ((rx0 + rx1) / 2, (ry0 + ry1) / 2)

        # V19: keep the off-table deal origin for card-flight animation, but do
        # not draw any SHOE object in the upper-right corner.
        self.shoe_origin = (x1 - 92, 46)

    def draw_board(self):
        """Draw the Evoplay-style station and remember HOME/ROUND geometries."""
        c = self.canvas
        board_x0, board_y0, board_x1, board_y1 = self.GAME_X0, 388, self.GAME_X1, 620
        felt = '#075443'
        self.betting_board_home_bounds = (board_x0, board_y0, board_x1, board_y1)
        # Only the WHOLE betting-area background becomes 30px shorter in-round.
        # The seven individual betting ovals keep their established dimensions.
        self.betting_board_round_bounds = (board_x0, board_y0 + 30.0, board_x1, board_y1)
        self.betting_board_rect = c.create_rectangle(
            *self.betting_board_home_bounds, fill=felt, outline=self.LINE, width=2, tags='static')

        home = {
            'MAIN': ((455.0, 402.0, 695.0, 548.0), (575.0, 430.0), (575.0, 492.0)),
            'Perfect Pair': ((220.0, 486.0, 380.0, 568.0), (300.0, 507.0), (300.0, 542.0)),
            '21+3': ((330.0, 536.0, 450.0, 614.0), (390.0, 554.0), (390.0, 586.0)),
            'Open Card Luck': ((458.0, 552.0, 568.0, 618.0), (513.0, 567.0), (513.0, 594.0)),
            'Crazy 7': ((582.0, 552.0, 692.0, 618.0), (637.0, 567.0), (637.0, 594.0)),
            'Hot 21': ((700.0, 536.0, 820.0, 614.0), (760.0, 554.0), (760.0, 586.0)),
            'Bust!': ((770.0, 486.0, 930.0, 568.0), (850.0, 507.0), (850.0, 542.0)),
        }
        # After Enter, MAIN drops exactly 50 px and the six side bets fan
        # outward to one horizontal level.  V11 restores the exact V9 oval sizes;
        # the 30px reduction applies to the betting AREA background, not these seven ovals.
        round_layout = {
            'MAIN': ((455.0, 452.0, 695.0, 598.0), (575.0, 480.0), (575.0, 542.0)),
            # V16: after 开牌, every SIDE-BET spot sits 20px lower than V15.
            # MAIN deliberately keeps its existing in-round position.
            'Perfect Pair': ((18.0, 504.0, 154.0, 586.0), (86.0, 525.0), (86.0, 560.0)),
            '21+3': ((164.0, 504.0, 274.0, 586.0), (219.0, 525.0), (219.0, 560.0)),
            'Open Card Luck': ((284.0, 504.0, 414.0, 586.0), (349.0, 525.0), (349.0, 560.0)),
            'Crazy 7': ((736.0, 504.0, 846.0, 586.0), (791.0, 525.0), (791.0, 560.0)),
            'Hot 21': ((856.0, 504.0, 966.0, 586.0), (911.0, 525.0), (911.0, 560.0)),
            'Bust!': ((976.0, 504.0, 1132.0, 586.0), (1054.0, 525.0), (1054.0, 560.0)),
        }
        self.bet_layout_home = home
        self.bet_layout_round = round_layout
        self.bet_layout_mode = 'home'

        c.create_oval(427, 394, 723, 562, fill='', outline='#5ea85b', width=1,
                      dash=(5, 6), tags=('static', 'betting_station_guide'))

        self.bet_spots = {}
        self.side_bet_spots = {}
        labels = {'MAIN': '主注\nBLACKJACK', **self.SIDE_BET_LABELS}
        widths = {'MAIN': 4, **{key: 3 for key in self.SIDE_BET_KEYS}}
        fills = {'MAIN': '#0b5f4c', **{key: '#164f47' for key in self.SIDE_BET_KEYS}}
        fonts = {'MAIN': 15, **{key: 12 for key in self.SIDE_BET_KEYS}}
        fonts['Open Card Luck'] = 11

        for index, key in enumerate(('MAIN',) + self.SIDE_BET_KEYS):
            bounds, label_pos, chip_pos = home[key]
            tag = 'main_bet_spot' if key == 'MAIN' else f'side_bet_{index - 1}'
            shape = c.create_oval(*bounds, fill=fills[key], outline='#9de46f', width=widths[key],
                                  tags=(tag, 'betting_spot'))
            label = c.create_text(*label_pos, text=labels[key],
                                  font=(self.cn_font, fonts[key], 'bold'), fill='white',
                                  justify='center', tags=(tag, 'betting_spot_label'))
            spot = {
                'key': key, 'bounds': tuple(bounds), 'label_pos': tuple(label_pos),
                'chip_pos': tuple(chip_pos), 'rect': shape, 'shape': 'oval',
                'label': label, 'tag': tag, 'normal_fill': fills[key],
                'normal_outline': '#9de46f', 'normal_width': widths[key],
            }
            self.bet_spots[key] = spot
            if key == 'MAIN':
                self.bet_spot_bounds = spot['bounds']; self.bet_spot_rect = shape; self.bet_spot_label = label
                c.tag_bind(tag, '<Button-1>', lambda _e: self.place_bet())
                c.tag_bind(tag, '<Button-3>', lambda _e: self.clear_bets())
            else:
                self.side_bet_spots[key] = spot
                c.tag_bind(tag, '<Button-1>', lambda _e, k=key: self.place_side_bet(k))
                c.tag_bind(tag, '<Button-3>', lambda _e, k=key: self.clear_side_bet(k))
            c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
            c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))
        self.update_bet_chips()

    def draw_bottom_controls(self):
        c = self.canvas
        y0, y1 = 625, 748
        c.create_rectangle(0, y0, self.WIDTH, y1, fill=self.BG,
                           outline=self.PANEL_LINE, width=2, tags='controls')
        self.balance_text = c.create_text(10, 665, anchor='w', text='余额: $0',
                                          font=(self.cn_font, 18, 'bold'), fill='white',
                                          tags=('dynamic', 'controls'))
        self.total_bet_text = c.create_text(10, 710, anchor='w', text='本局下注: $0.00',
                                            font=(self.cn_font, 15, 'bold'), fill='white',
                                            tags=('dynamic', 'controls'))
        self.clear_button = self._create_canvas_button(
            270, 650, 336, 704, '清除', self.clear_bets, '#7c3b40',
            tag='control_clear', font_size=11)

        chip_diameter = 56; chip_gap = 8
        total_width = len(self.CHIP_SPECS) * chip_diameter + (len(self.CHIP_SPECS) - 1) * chip_gap
        chip_x = (self.WIDTH - total_width) / 2; chip_y = 646
        self.chip_selector_centers = {}
        for value, color, label in self.CHIP_SPECS:
            tag = f'chip_select_{value}'
            outer = c.create_oval(chip_x, chip_y, chip_x + chip_diameter, chip_y + chip_diameter,
                                  fill='#292522', outline='#6d6259', width=3,
                                  tags=(tag, 'chip_selector', 'predeal_controls'))
            inner = c.create_oval(chip_x + 5, chip_y + 5,
                                  chip_x + chip_diameter - 5, chip_y + chip_diameter - 5,
                                  fill=color, outline='#eee3d6', width=2,
                                  tags=(tag, 'chip_selector', 'predeal_controls'))
            label_id = c.create_text(chip_x + chip_diameter / 2, chip_y + chip_diameter / 2,
                                     text=label, font=(self.cn_font, 10, 'bold'),
                                     fill=self.contrast_text_color(color),
                                     tags=(tag, 'chip_selector', 'predeal_controls'))
            c.tag_bind(tag, '<Button-1>', lambda _e, v=value: self.select_chip(v))
            self.chip_selector_items[value] = (outer, inner, label_id)
            self.chip_selector_centers[float(value)] = (chip_x + chip_diameter / 2,
                                                        chip_y + chip_diameter / 2)
            chip_x += chip_diameter + chip_gap

        self.info_button = self._create_canvas_button(
            810, 650, 855, 695, '❓', self.show_game_instructions, '#315b72',
            tag='control_info', font_size=17)
        self.repeat_button = self._create_canvas_button(
            862, 638, 1000, 708, '重复下注', self.repeat_last_bet, '#5b4938',
            tag='control_repeat', font_size=11)
        self.deal_button = self._create_canvas_button(
            1012, 628, 1138, 720, '开牌\nENTER', self.deal_cards, '#d5ad4d',
            fg='#111111', tag='control_deal', font_size=13)

        specs = [
            ('hit', 270, 638, 432, 720, '要牌', self.hit, '#315b72'),
            ('stand', 442, 638, 604, 720, '停牌', self.stand, '#5b4938'),
            ('double', 614, 638, 776, 720, '加倍', self.double, '#a56d2c'),
            ('split', 786, 638, 948, 720, '分牌', self.split, '#70439a'),
            ('surrender', 958, 638, 1138, 720, '兑现金额\n$0.00', self.instant_surrender, '#7c3b40'),
        ]
        for key, x0, yy0, x1, yy1, label, command, color in specs:
            self.action_buttons[key] = self._create_canvas_button(
                x0, yy0, x1, yy1, label, command, color,
                tag=f'action_{key}', font_size=12)

        # Dealer-A decisions replace the chip rack; no messagebox is used.
        self.decision_buttons['accept'] = self._create_canvas_button(
            405, 642, 565, 716, '购买保险', lambda: self._resolve_ace_decision(True),
            '#a56d2c', tag='decision_accept', font_size=13)
        self.decision_buttons['decline'] = self._create_canvas_button(
            585, 642, 745, 716, '不购买', lambda: self._resolve_ace_decision(False),
            '#315b72', tag='decision_decline', font_size=13)

        # Double first opens a dedicated multiplier chooser.  While it is open,
        # every ordinary hand action is hidden; Back restores the same hand.
        double_specs = [
            ('2x', 270, 638, 472, 720, '2X', lambda: self._resolve_double_choice(2), '#a56d2c'),
            ('3x', 482, 638, 684, 720, '3X', lambda: self._resolve_double_choice(3), '#a56d2c'),
            ('4x', 694, 638, 896, 720, '4X', lambda: self._resolve_double_choice(4), '#a56d2c'),
            ('back', 906, 638, 1138, 720, '返回', self._cancel_double_choice, '#315b72'),
        ]
        for key, x0, y0, x1, y1, label, command, color in double_specs:
            self.double_choice_buttons[key] = self._create_canvas_button(
                x0, y0, x1, y1, label, command, color,
                tag=f'double_choice_{key}', font_size=13)
        self._set_round_control_visibility(False)

    def _create_canvas_button(self, x0, y0, x1, y1, text, command, color,
                              fg='white', tag=None, font_size=12):
        tag = tag or f'button_{len(self.control_buttons)}'
        rect = self.canvas.create_rectangle(x0, y0, x1, y1, fill=color,
                                            outline='#d5cbbd', width=2,
                                            tags=(tag, 'ui_button'))
        txt = self.canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2,
                                      text=text, font=(self.cn_font, font_size, 'bold'),
                                      fill=fg, justify='center', tags=(tag, 'ui_button'))
        button = {'rect': rect, 'text': txt, 'tag': tag, 'command': command,
                  'color': color, 'fg': fg, 'enabled': True}
        self.control_buttons[tag] = button

        def invoke(_event=None, b=button):
            if b.get('enabled', False) and callable(b.get('command')):
                b['command']()

        self.canvas.tag_bind(tag, '<Button-1>', invoke)
        self.canvas.tag_bind(tag, '<Enter>', lambda _e: self.canvas.configure(cursor='hand2'))
        self.canvas.tag_bind(tag, '<Leave>', lambda _e: self.canvas.configure(cursor=''))
        return button

    def _set_button(self, button, enabled, text=None):
        if not button:
            return
        button['enabled'] = bool(enabled)
        if text is not None:
            self.canvas.itemconfigure(button['text'], text=text)
        # Hidden controls stay hidden; enabling only changes their visual style.
        if enabled:
            self.canvas.itemconfigure(button['rect'], fill=button['color'], stipple='')
            self.canvas.itemconfigure(button['text'], fill=button['fg'])
        else:
            self.canvas.itemconfigure(button['rect'], fill='#3d3833', stipple='gray50')
            self.canvas.itemconfigure(button['text'], fill='#8f8880')

    def _button_state(self, button, visible):
        if not button:
            return
        state = 'normal' if visible else 'hidden'
        self.canvas.itemconfigure(button['rect'], state=state)
        self.canvas.itemconfigure(button['text'], state=state)

    def _raise_visible_bottom_controls(self, in_round):
        """Keep only the actual visible controls above the panel background."""
        if not in_round:
            self.canvas.tag_raise('chip_selector')
            buttons = (getattr(self, 'clear_button', None), getattr(self, 'info_button', None),
                       getattr(self, 'repeat_button', None), getattr(self, 'deal_button', None))
        elif self.ace_decision_mode:
            buttons = tuple(getattr(self, 'decision_buttons', {}).values())
        elif self.double_choice_mode:
            buttons = tuple(getattr(self, 'double_choice_buttons', {}).values())
        else:
            buttons = tuple(getattr(self, 'action_buttons', {}).values())
        for button in buttons:
            if button:
                self.canvas.tag_raise(button['rect']); self.canvas.tag_raise(button['text'])
        for item_name in ('balance_text', 'total_bet_text'):
            item = getattr(self, item_name, None)
            if item: self.canvas.tag_raise(item)

    def _set_round_control_visibility(self, in_round):
        """Switch bottom strip between betting, Ace-decision, and hand-action modes."""
        predeal = not in_round
        decision = bool(in_round and self.ace_decision_mode)
        double_choice = bool(in_round and not decision and self.double_choice_mode)
        actions = bool(in_round and not decision and not double_choice)
        self.canvas.itemconfigure('chip_selector', state='normal' if predeal else 'hidden')
        for button in (getattr(self, 'clear_button', None), getattr(self, 'info_button', None),
                       getattr(self, 'repeat_button', None), getattr(self, 'deal_button', None)):
            self._button_state(button, predeal)
        for button in getattr(self, 'action_buttons', {}).values():
            self._button_state(button, actions)
        for button in getattr(self, 'decision_buttons', {}).values():
            self._button_state(button, decision)
        for button in getattr(self, 'double_choice_buttons', {}).values():
            self._button_state(button, double_choice)
        self._raise_visible_bottom_controls(in_round)

    def _set_rules_strip_visible(self, visible):
        state = 'normal' if visible else 'hidden'
        self.canvas.itemconfigure(self.rule_strip_rect, state=state)
        if not visible:
            for item in (self.rule_strip_text, self.rule_strip_left_text, self.rule_strip_right_text):
                self.canvas.itemconfigure(item, state='hidden')
            self.canvas.delete('insurance_chip')
            return
        self._refresh_rule_strip_text()
        self.canvas.tag_raise('round_rule_strip')
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
        if not self.insurance_chip_visible or self.insurance_bet <= 0:
            return
        if self.settlement_running and not self.flash_insurance_rule:
            return  # losing insurance disappears at settlement
        amount = self.insurance_bet
        if self.settlement_running and self.flash_insurance_rule and self.flash_mode == 'win':
            amount = self.insurance_return_amount or self.insurance_bet * (1.0 + self.INSURANCE_PROFIT)
        x, y = self.rule_strip_chip_pos
        self._draw_baccarat_chip(x, y, amount, tags=('insurance_chip',), radius=18)
        self.canvas.tag_raise('insurance_chip')

    def _animate_insurance_chip_to_rule(self, on_complete=None):
        """Fly half of the MAIN bet from the hidden chip-rack area to the rule strip."""
        amount = float(self.insurance_bet)
        sx, sy = 575.0, 674.0
        tx, ty = self.rule_strip_chip_pos
        items = self._draw_baccarat_chip(sx, sy, amount, tags=('insurance_chip_fly',), radius=18)
        self.canvas.tag_raise('insurance_chip_fly')
        steps = 10; frame_ms = 20
        def frame(step=1):
            t = min(1.0, step / steps); e = 1.0 - (1.0 - t) ** 2
            cx, cy = sx + (tx-sx)*e, sy + (ty-sy)*e; r=18
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
                if not self._has_bust_wager():
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

    def _apply_bet_layout_fraction(self, target_layout, starts, fraction,
                                   board_start=None, board_target=None,
                                   player_start=None, player_target=None,
                                   player_label_start=None, player_label_target=None,
                                   move_existing_player_visuals=False):
        for key, spot in self.bet_spots.items():
            sb, sl, sc = starts[key]
            tb, tl, tc = target_layout[key]
            b = tuple(sb[i] + (tb[i]-sb[i])*fraction for i in range(4))
            lp = tuple(sl[i] + (tl[i]-sl[i])*fraction for i in range(2))
            cp = tuple(sc[i] + (tc[i]-sc[i])*fraction for i in range(2))
            self.canvas.coords(spot['rect'], *b); self.canvas.coords(spot['label'], *lp)
            spot['bounds'] = b; spot['label_pos'] = lp; spot['chip_pos'] = cp
        if board_start and board_target:
            bb = tuple(board_start[i] + (board_target[i]-board_start[i])*fraction for i in range(4))
            self.canvas.coords(self.betting_board_rect, *bb)
        if player_start and player_target:
            pb = tuple(player_start[i] + (player_target[i]-player_start[i])*fraction for i in range(4))
            self.canvas.coords(self.player_zone_rect, *pb)
        if player_label_start and player_label_target:
            pp = tuple(player_label_start[i] + (player_label_target[i]-player_label_start[i])*fraction for i in range(2))
            self.canvas.coords(self.player_zone_title, *pp)
        self.bet_spot_bounds = self.bet_spots['MAIN']['bounds']
        self.update_bet_chips()

    def _animate_betting_station(self, to_round, on_complete=None):
        target = self.bet_layout_round if to_round else self.bet_layout_home
        starts = {k: (tuple(v['bounds']), tuple(v.get('label_pos', self.canvas.coords(v['label']))),
                      tuple(v['chip_pos'])) for k,v in self.bet_spots.items()}
        board_start = tuple(self.canvas.coords(self.betting_board_rect))
        board_target = self.betting_board_round_bounds if to_round else self.betting_board_home_bounds
        player_start = tuple(self.canvas.coords(self.player_zone_rect))
        player_target = self.player_zone_round if to_round else self.player_zone_home
        player_label_start = tuple(self.canvas.coords(self.player_zone_title))
        player_label_target = self.player_label_round if to_round else self.player_label_home
        # Existing previous-round PLAYER graphics move with the zone on the return
        # trip. Dealer graphics stay fixed.  New cards are rendered directly into
        # the round geometry, so no move is needed on the outward trip.
        move_existing = (not to_round and self.previous_round_cards_present)
        moved_fraction = [0.0]
        self.bet_layout_mode = 'moving'
        if to_round:
            self.canvas.itemconfigure('betting_station_guide', state='hidden')
            self._set_rules_strip_visible(True)
        steps=10; frame_ms=20
        def frame(step=1):
            t=min(1.0, step/steps); e=t*t*(3.0-2.0*t)
            self._apply_bet_layout_fraction(
                target, starts, e, board_start, board_target, player_start, player_target,
                player_label_start, player_label_target)
            if move_existing:
                de = e - moved_fraction[0]; moved_fraction[0] = e
                dy = -40.0 * de
                for tag in ('player_dealt_card','player_hand_overlay'):
                    try: self.canvas.move(tag, 0, dy)
                    except tk.TclError: pass
            if step < steps: self._queue(frame_ms, frame, step+1)
            else:
                self.bet_layout_mode = 'round' if to_round else 'home'
                self.player_zone_mode = 'round' if to_round else 'home'
                if not to_round:
                    self._set_rules_strip_visible(False)
                    self.canvas.itemconfigure('betting_station_guide', state='normal')
                if callable(on_complete): on_complete()
        self._queue(frame_ms, frame, 1)

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
        color = color.lstrip('#')
        if len(color) != 6:
            return 'white'
        r, g, b = int(color[:2], 16), int(color[2:4], 16), int(color[4:], 16)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return '#111111' if luminance > 165 else 'white'

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

    def _draw_baccarat_chip(self, cx, cy, amount, tags, radius=20, force_color=None):
        """Draw the same two-ring amount chip used by the Baccarat betting board."""
        amount = float(amount)
        chip_color = force_color or self.bet_chip_color(amount)
        text_color = self.contrast_text_color(chip_color)
        outer = self.canvas.create_oval(
            cx-radius, cy-radius, cx+radius, cy+radius,
            fill='#292522', outline='#151311', width=1, tags=tags)
        inner = self.canvas.create_oval(
            cx-radius+3, cy-radius+3, cx+radius-3, cy+radius-3,
            fill=chip_color, outline='#e2ddd5', width=1, tags=tags)
        text = self.canvas.create_text(
            cx, cy, text=self._compact_amount(amount),
            font=('Arial', 9, 'bold'), fill=text_color, tags=tags)
        return (outer, inner, text)

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
            sx, sy, amount, tags=('bet_chip_fly',), radius=20, force_color=selected_color)
        self.canvas.tag_raise('bet_chip_fly')
        steps = 10
        frame_ms = 20

        def frame(step=1):
            ratio = min(1.0, step / float(steps))
            # ease-out keeps the casino-chip movement crisp while still visibly animated
            eased = 1.0 - (1.0 - ratio) ** 2
            cx = sx + (tx - sx) * eased
            cy = sy + (ty - sy) * eased
            r = 20
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
            sx, sy, amount, tags=('bet_chip_fly',), radius=20,
            force_color=self.bet_chip_color(amount))
        self.canvas.tag_raise('bet_chip_fly')
        steps = 10
        frame_ms = 20

        def frame(step=1):
            ratio = min(1.0, step / float(steps))
            eased = 1.0 - (1.0 - ratio) ** 2
            cx = sx + (tx - sx) * eased
            cy = sy + (ty - sy) * eased
            r = 20
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
                return 0.0  # main wager has physically moved above the player hand(s)
            amount = float(self.current_bet)
        else:
            if self.round_active:
                if spot_key in self.side_bet_early_collected:
                    return 0.0
                if self.settlement_running:
                    if spot_key not in self.flash_winning_side_bets:
                        return 0.0  # losing side-bet chips disappear immediately at settlement
                    if self.flash_mode == 'win':
                        return float(self.side_bet_return_amounts.get(spot_key, 0.0))
                amount = float(self.round_side_bets.get(spot_key, 0.0))
            else:
                amount = float(self.current_side_bets.get(spot_key, 0.0))

        if not self.round_active:
            amount -= float(self.pending_bet_animation.get(spot_key, 0.0))
        return max(0.0, amount)

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        for key, spot in self.bet_spots.items():
            amount = self._bet_amount_for_spot(key)
            if amount <= 0:
                continue
            x, y = spot['chip_pos']
            self._draw_baccarat_chip(
                x, y, amount, tags=('bet_chip_dynamic', spot['tag']), radius=20)
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
                try: self.canvas.itemconfigure(label, fill='white')
                except tk.TclError: pass
        self._set_rule_strip_text_color('white')

    def _draw_side_bet_progress_badges(self):
        """Draw non-animated winning side-bet markers during live play.

        V18: known winning side-bet tiers stay WHITE during both player and
        dealer play.  These markers do not change colour when the dealer starts.
        Bust! keeps the V15 behaviour and is not previewed before its final
        dealer-dependent result is settled.  Crazy 7 may update its displayed
        provisional tier as target cards 0, 2 and 3 become available.
        """
        self.canvas.delete('side_bet_progress_badge')
        if not self.round_active or self.settlement_running:
            return

        visible_keys = set(self.side_bet_hit_odds)
        for key in self.SIDE_BET_KEYS:
            if key == 'Bust!' or key not in visible_keys:
                continue
            spot = self.bet_spots.get(key)
            if not spot:
                continue
            odds = self.side_bet_hit_odds.get(key)
            x0, y0, x1, _y1 = spot['bounds']
            cx = (x0 + x1) / 2.0
            box_w, box_h, nose_h = 66.0, 34.0, 13.0
            top = max(426.0, y0 - box_h - nose_h - 5.0)
            bx0, bx1 = cx - box_w / 2.0, cx + box_w / 2.0
            by0, by1 = top, top + box_h
            fill = '#ffffff'

            self.canvas.create_rectangle(
                bx0, by0, bx1, by1, fill=fill, outline='',
                tags=('side_bet_progress_badge',))
            self.canvas.create_polygon(
                cx - 30.0, by1, cx + 30.0, by1, cx, by1 + nose_h,
                fill=fill, outline='', tags=('side_bet_progress_badge',))
            if odds is not None:
                self.canvas.create_text(
                    cx, (by0 + by1) / 2.0, text=f'{float(odds):g}:1',
                    font=(self.cn_font, 17, 'bold'), fill='#000000',
                    tags=('side_bet_progress_badge',))

        self.canvas.tag_raise('side_bet_progress_badge')

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
            [(x, y, stake, 20)], lambda sx, sy: (sx, -35.0), 300,
            f'side_bet_collect_{safe}')

    def _draw_side_bet_win_odds_badges(self):
        """White downward-pointing badges showing only this round's hit tier."""
        self.canvas.delete('side_bet_win_odds')
        if not self.settlement_running:
            return
        for key in self.flash_winning_side_bets:
            spot = self.bet_spots.get(key)
            odds = self.side_bet_hit_odds.get(key)
            if not spot or odds is None:
                continue
            x0, y0, x1, _y1 = spot['bounds']
            cx = (x0 + x1) / 2.0
            # Match the supplied reference: a white rectangle with a broad
            # downward triangular nose aimed at the winning side-bet oval.
            box_w, box_h, nose_h = 66.0, 34.0, 13.0
            top = max(426.0, y0 - box_h - nose_h - 5.0)
            bx0, bx1 = cx - box_w/2.0, cx + box_w/2.0
            by0, by1 = top, top + box_h
            self.canvas.create_rectangle(
                bx0, by0, bx1, by1, fill='#ffffff', outline='',
                tags=('side_bet_win_odds','settlement_flash'))
            self.canvas.create_polygon(
                cx - 30.0, by1, cx + 30.0, by1, cx, by1 + nose_h,
                fill='#ffffff', outline='', tags=('side_bet_win_odds','settlement_flash'))
            self.canvas.create_text(
                cx, (by0 + by1) / 2.0, text=f'{float(odds):g}:1',
                font=(self.cn_font, 17, 'bold'), fill='#000000',
                tags=('side_bet_win_odds','settlement_flash'))

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
                x,y=spot['chip_pos']; sources.append((x,y,stake,20))

        # MAIN is component based so an OBO hand can lose its Original Bet while
        # its Double/supplemental component remains for refund.
        layout=self._main_split_wager_layout(len(self.hands)) if self.hands else []
        for idx,hand in enumerate(self.hands):
            if idx>=len(layout): break
            if float(hand.get('base_bet',0.0))>0 and hand.get('base_settlement')=='lose':
                x,y=layout[idx]['base']; sources.append((x,y,float(hand['base_bet']),20))
            if float(hand.get('double_added',0.0))>0 and hand.get('double_settlement')=='lose':
                x,y=layout[idx]['double']; sources.append((x,y,float(hand['double_added']),20))

        if self.insurance_bet>0.0 and self.insurance_return_amount<=0.0:
            x,y=self.rule_strip_chip_pos; sources.append((x,y,float(self.insurance_bet),18))
        return sources

    def _settlement_return_chip_sources(self):
        """Return all money-returning chips using their displayed return amounts."""
        sources=[]
        for key in self.SIDE_BET_KEYS:
            returned=float(self.side_bet_return_amounts.get(key,0.0))
            spot=self.bet_spots.get(key)
            if returned>0.0 and spot:
                x,y=spot['chip_pos']; sources.append((x,y,returned,20))

        layout=self._main_split_wager_layout(len(self.hands)) if self.hands else []
        for idx,hand in enumerate(self.hands):
            if idx>=len(layout): break
            amount=self._component_return_amount(hand,'base')
            if amount>0.0:
                x,y=layout[idx]['base']; sources.append((x,y,amount,20))
            amount=self._component_return_amount(hand,'double')
            if amount>0.0:
                x,y=layout[idx]['double']; sources.append((x,y,amount,20))

        if self.insurance_return_amount>0.0:
            x,y=self.rule_strip_chip_pos
            sources.append((x,y,float(self.insurance_return_amount),18))
        return sources

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
        """After flashing, fly every returned chip to the bottom chip rack in 0.20 s."""
        self.canvas.delete('win_flash_area'); self.canvas.delete('side_bet_win_odds')
        self.canvas.delete('side_bet_progress_badge')
        self._restore_betting_spot_label_colors()
        sources=self._settlement_return_chip_sources()
        # Hide the stationary settlement chips before drawing their travelling clones.
        self.canvas.delete('bet_chip_dynamic'); self.canvas.delete('hand_wager'); self.canvas.delete('insurance_chip')
        self.flash_mode=None
        def done():
            self.settlement_running=False
            self._reset_after_round()
        self._animate_settlement_chips(sources,(575.0,674.0),200,'settlement_return_fly',done)

    def run_settlement_flash(self):
        """Three Baccarat-style cycles for side bets, whole MAIN, and winning insurance."""
        if self._closing or not self.settlement_running:
            return
        if self.settlement_flash_step >= 6:
            self._finish_flash_with_chip_return(); return

        light_phase = (self.settlement_flash_step % 2 == 0)
        self.flash_mode = 'win' if light_phase else 'original'
        self.canvas.delete('win_flash_area'); self.canvas.delete('side_bet_win_odds')
        self._restore_betting_spot_label_colors()
        if light_phase:
            for key in set(self.flash_winning_side_bets):
                spot=self.bet_spots.get(key)
                if not spot: continue
                x0,y0,x1,y1=spot['bounds']
                self.canvas.create_oval(x0,y0,x1,y1,fill='#ffffff',outline='#111111',width=2,
                                        tags=('win_flash_area','settlement_flash'))
                self.canvas.itemconfigure(spot['label'],fill='#111111'); self.canvas.tag_raise(spot['label'])
            if self.flash_main_bet:
                spot=self.bet_spots.get('MAIN')
                if spot:
                    x0,y0,x1,y1=spot['bounds']
                    main_fill = '#9fdcff' if self.flash_main_push_only else '#ffffff'
                    self.canvas.create_oval(x0,y0,x1,y1,fill=main_fill,outline='#111111',width=3,
                                            tags=('win_flash_area','settlement_flash'))
                    self.canvas.itemconfigure(spot['label'],fill='#111111'); self.canvas.tag_raise(spot['label'])
            if self.flash_insurance_rule:
                x0,y0,x1,y1=self.rule_strip_bounds
                self.canvas.create_rectangle(x0,y0,x1,y1,fill='#ffffff',outline='#111111',width=2,
                                             tags=('win_flash_area','settlement_flash'))
                self._set_rule_strip_text_color('#111111')

        self.update_bet_chips()
        self.canvas.delete('hand_wager'); self._draw_main_hand_wagers()
        self._render_insurance_chip()
        self._draw_side_bet_win_odds_badges()
        self.canvas.tag_raise('win_flash_area')
        self.canvas.tag_raise('side_bet_win_odds')
        for tag in ('betting_spot_label','rule_strip_text','rule_strip_split_text','bet_chip_dynamic',
                    'dealt_card','hand_wager','hand_label','insurance_chip','side_bet_win_odds','settlement_loss_fly'):
            try: self.canvas.tag_raise(tag)
            except tk.TclError: pass
        self._raise_visible_bottom_controls(self.round_active)
        self.settlement_flash_step += 1
        self._queue(300, self.run_settlement_flash)

    def select_chip(self, value):
        self.selected_chip = float(value)
        for chip_value, (outer, _inner, _txt) in self.chip_selector_items.items():
            selected = float(chip_value) == self.selected_chip
            self.canvas.itemconfigure(outer,
                                      outline='#f4d65b' if selected else '#6d6259',
                                      width=5 if selected else 3)

    def place_bet(self):
        if not self.accept_bets or self.round_active or self.animation_running or self.settlement_running:
            return
        # Silently clamp the selected denomination to the remaining MAIN limit.
        # Example: MAIN=450K + selected 250K -> actually place only 50K.
        remaining_limit = max(0.0, self.MAX_MAIN_BET - float(self.current_bet))
        amount = min(float(self.selected_chip), remaining_limit)
        if amount <= 1e-9:
            return
        if self.balance + 1e-9 < amount:
            messagebox.showwarning('余额不足', '余额不足以放置该筹码。', parent=self.winfo_toplevel())
            return
        # A new betting action switches the lower-left readout back from
        # "上局获胜" to the live "本局下注" amount.
        self.show_last_win = False
        # Reserve the wager immediately so rapid clicks cannot overspend, while
        # pending_bet_animation keeps the destination total hidden until arrival.
        self.balance -= amount
        self.current_bet += amount
        self.pending_bet_animation['MAIN'] += amount
        self.bet_chip_animation_count += 1
        self.update_display()
        self._animate_selected_chip_to_spot(
            'MAIN', lambda: self._finish_bet_chip_animation('MAIN', amount), amount=amount)

    def place_side_bet(self, key):
        if (key not in self.SIDE_BET_KEYS or not self.accept_bets or self.round_active
                or self.animation_running or self.settlement_running):
            return
        # Each side bet has its own 100K cap.  A denomination larger than the
        # remaining allowance is silently reduced to exactly fill that side bet.
        current = float(self.current_side_bets.get(key, 0.0))
        remaining_limit = max(0.0, self.MAX_SIDE_BET - current)
        amount = min(float(self.selected_chip), remaining_limit)
        if amount <= 1e-9:
            return
        if self.balance + 1e-9 < amount:
            messagebox.showwarning('余额不足', '余额不足以放置该筹码。', parent=self.winfo_toplevel())
            return
        self.show_last_win = False
        self.balance -= amount
        self.current_side_bets[key] += amount
        self.pending_bet_animation[key] += amount
        self.bet_chip_animation_count += 1
        self.update_display()
        self._animate_selected_chip_to_spot(
            key, lambda k=key, a=amount: self._finish_bet_chip_animation(k, a), amount=amount)

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
        final_main = self.current_bet + additions.get('MAIN', 0.0)
        if final_main > self.MAX_MAIN_BET + 1e-9:
            messagebox.showwarning(
                '无法重复下注',
                f'主注最高下注 {self.format_money(self.MAX_MAIN_BET)}。',
                parent=self.winfo_toplevel())
            return
        for key in self.SIDE_BET_KEYS:
            final_side = self.current_side_bets.get(key, 0.0) + additions.get(key, 0.0)
            if final_side > self.MAX_SIDE_BET + 1e-9:
                messagebox.showwarning(
                    '无法重复下注',
                    f'{self.SIDE_BET_LABELS.get(key, key)}最高下注 {self.format_money(self.MAX_SIDE_BET)}。',
                    parent=self.winfo_toplevel())
                return
        if self.balance + 1e-9 < needed:
            messagebox.showwarning('无法重复下注', '余额不足。', parent=self.winfo_toplevel())
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

    # -------------------------------------------------------------- Classic_Blackjack.json
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
        # keeps no duplicate deck order in Classic_Blackjack.json.
        try:
            self.csm.status()
            return True
        except (OSError, TypeError, ValueError, CSMError):
            return False

    def draw_round_card(self):
        while True:
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

            # Rank 9 and rank 10 are physically consumed into the discard area.
            # They never reach either player/dealer, never enter the visible deal
            # sequence, and the following eligible card is dealt instead.
            if card[1] in ('9', '10'):
                self.round_discarded_cards.append(card)
                continue

            self.round_deal_sequence.append(card)
            return card

    def _show_cut_dialog(self, second=False):
        """Baccarat-style physical packet cut animation."""
        dialog_w, dialog_h = 760, 410
        dialog = tk.Toplevel(self.winfo_toplevel())
        dialog.title('倍注黑杰克 · 切牌')
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
                                flip=True, tag='round_animation_card'):
        """Baccarat-style movement followed by the same width-collapse flip."""
        sx, sy = self.shoe_origin
        start_x, start_y = sx, sy
        back = self.external_back_image
        if back is not None:
            card_id = self.canvas.create_image(start_x, start_y, image=back, anchor='nw',
                                               tags=(tag, 'animation_card'))
        else:
            card_id = self.canvas.create_rectangle(start_x, start_y, start_x+100, start_y+140,
                                                   fill='#253e66', outline='#d7c46a', width=2,
                                                   tags=(tag, 'animation_card'))
        self._round_anim_item = card_id

        def move_step(step=0):
            if self._closing: return
            t = min(1.0, step / 24.0)
            eased = 1.0 - (1.0 - t) ** 3
            x = start_x + (target_x - start_x) * eased
            y = start_y + (target_y - start_y) * eased
            if self.canvas.type(card_id) == 'image':
                self.canvas.coords(card_id, x, y)
            else:
                self.canvas.coords(card_id, x, y, x+100, y+140)
            if step < 24:
                self._queue(12, move_step, step + 1)
            elif flip:
                flip_step(0)
            else:
                if callable(on_complete): on_complete()

        def flip_step(step=0):
            if self._closing: return
            steps = 12
            if step > steps:
                if self.canvas.type(card_id) == 'image':
                    final = self._face_photo(card)
                    if final is not None: self.canvas.itemconfigure(card_id, image=final)
                    self.canvas.coords(card_id, target_x, target_y)
                else:
                    self.canvas.delete(card_id)
                self._temp_flip_images.pop(card_id, None)
                if callable(on_complete): on_complete()
                return
            half = steps // 2
            if step <= half:
                ratio = 1 - step / float(half); use_back = True
            else:
                ratio = (step - half) / float(half); use_back = False
            width = max(1, int(100 * ratio))
            if self.canvas.type(card_id) == 'image':
                image = self._create_scaled_flip_image(card, width, 140, use_back=use_back)
                if image is not None:
                    self._temp_flip_images[card_id] = image
                    self.canvas.itemconfigure(card_id, image=image)
                    self.canvas.coords(card_id, target_x + (100-width)/2, target_y)
            self._queue(20, flip_step, step + 1)
        move_step(0)

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
        for tag in ('dealt_card','temp_card','hand_label','hand_zone','hand_wager',
                    'animation_card','split_lane_animation'):
            self.canvas.delete(tag)
        self.card_items.clear(); self._temp_flip_images.clear()
        self.previous_round_cards_present = False
        if hasattr(self, 'dealer_total_text'):
            self.canvas.itemconfigure(self.dealer_total_text, text='')


    def _hand_overlap(self, count=None):
        """Horizontal card overlap for the current 1..4 hand layout."""
        n = max(1, min(self.MAX_HANDS, int(count if count is not None else len(self.hands) or 1)))
        if n <= 2:
            return 34
        if n == 3:
            return 27
        if n == 4:
            return 21
        return 17

    def _hand_centers(self, count=None):
        """Exact centres of the 1..4 equal player-hand lanes."""
        n = max(1, min(self.MAX_HANDS, int(count if count is not None else len(self.hands) or 1)))
        x0, x1 = 22.0, 1128.0
        gutter = 8.0
        cell_w = (x1 - x0 - gutter * (n - 1)) / n
        return [x0 + cell_w / 2.0 + i * (cell_w + gutter) for i in range(n)]



    def _main_split_wager_layout(self, count=None):
        """Return Evoplay-style MAIN-oval chip positions for 1..4 hands."""
        n = max(1, min(self.MAX_HANDS, int(count if count is not None else len(self.hands) or 1)))
        spot = self.bet_spots.get('MAIN')
        if spot:
            x0, y0, x1, y1 = spot['bounds']
        else:
            x0, y0, x1, y1 = (455.0, 402.0, 695.0, 548.0)
        w, h = x1 - x0, y1 - y0
        normalized = {
            1: ((0.50, 0.62),),
            2: ((0.34, 0.62), (0.66, 0.62)),
            3: ((0.27, 0.57), (0.50, 0.67), (0.73, 0.57)),
            4: ((0.18, 0.54), (0.38, 0.63), (0.59, 0.63), (0.81, 0.54)),
        }[n]
        result = []
        for fx, fy in normalized:
            bx, by = x0 + fx * w, y0 + fy * h
            dy = min(y1 - 16.0, by + 0.255 * h)
            result.append({'base': (bx, by), 'double': (bx, dy)})
        return result


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
        """Draw split wager chips inside MAIN; white flash shows returned amounts."""
        self.main_wager_positions = {}
        if not self.round_active or not self.hands:
            return
        layout = self._main_split_wager_layout(len(self.hands))
        for idx, hand in enumerate(self.hands):
            pos = layout[idx]
            base = float(hand.get('base_bet', 0.0))
            dbl = float(hand.get('double_added', 0.0))
            base_state = hand.get('base_settlement')
            double_state = hand.get('double_settlement')
            show_base = base > 0.0
            show_double = dbl > 0.0
            if self.settlement_running:
                # Only genuinely losing components disappear. Push/refund/cashout
                # components still represent money returned to the player.
                show_base = show_base and base_state != 'lose'
                show_double = show_double and double_state != 'lose'
            self.main_wager_positions[idx] = {
                'base': pos['base'],
                'double': pos['double'] if dbl > 0.0 else None,
                'show_base': show_base,
                'show_double': show_double,
            }

            base_display = base
            double_display = dbl
            if self.settlement_running and self.flash_mode == 'win':
                base_display = self._component_return_amount(hand, 'base')
                double_display = self._component_return_amount(hand, 'double')

            # Draw Double first so the base chip visually sits in front where
            # their edges overlap, matching the supplied split/Double reference.
            if show_double and double_display > 0.0:
                self._draw_baccarat_chip(
                    pos['double'][0], pos['double'][1], double_display,
                    tags=('hand_wager', f'hand_wager_{idx}', 'double_wager'), radius=20)
            if show_base and base_display > 0.0:
                self._draw_baccarat_chip(
                    pos['base'][0], pos['base'][1], base_display,
                    tags=('hand_wager', f'hand_wager_{idx}', 'base_wager'), radius=20)


    def _player_card_target(self, hand_index, card_index):
        """Centre each split hand's card fan in its own lane, below the rules strip."""
        centers = self._hand_centers()
        cx = centers[min(hand_index, len(centers) - 1)]
        overlap = self._hand_overlap()
        cards = self.hands[hand_index]['cards'] if 0 <= hand_index < len(self.hands) else []
        count = max(1, len(cards))
        total_w = 100 + max(0, count - 1) * overlap
        start_x = cx - total_w / 2
        return start_x + card_index * overlap, 252


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
        """Colour ONLY the pointed score badge; never recolour a hand background.

        During player action: current=gold, waiting=light green, processed=light red.
        Once all player hands are processed they all return to white for dealer play.
        At settlement the final hand result takes precedence: win/cashout=green,
        push/refund=blue, lose=red.
        """
        if not (0 <= hand_index < len(self.hands)):
            return '#ffffff'
        hand = self.hands[hand_index]
        settlement = hand.get('settlement')
        if settlement in ('win', 'cashout'):
            return '#b9efb4'
        if settlement in ('push', 'refund'):
            return '#b9dcff'
        if settlement == 'lose':
            return '#f2b0b0'
        # A busted player hand is permanently light red, including the interval
        # after all player decisions finish but before settlement is assigned.
        if hand.get('status') == 'bust':
            return '#f2b0b0'

        if not self.round_active or not self.hands:
            return '#ffffff'
        # Player point badges do NOT change merely because dealer play begins.
        # Once all player decisions are complete they return to white; only the
        # dealer point badge changes colour during the dealer phase.
        all_processed = all(h.get('status') != 'active' for h in self.hands)
        if all_processed:
            return '#ffffff'
        if hand_index == self.active_hand_index and hand.get('status') == 'active':
            return '#f3cf55'
        if hand.get('status') == 'active' or hand.get('needs_split_draw', False):
            return '#b9efb4'
        return '#f2b0b0'


    def _draw_hand_total_badge(self, hand_index, left, right, active=False):
        """Draw the pointed score badge; its colour alone marks hand state."""
        if not (0 <= hand_index < len(self.hands)):
            return
        cards = self.hands[hand_index].get('cards', [])
        if not cards:
            return
        n = max(1, len(self.hands))
        overlap = self._hand_overlap(n)
        total_w = 100 + max(0, len(cards) - 1) * overlap
        cx = self._hand_centers()[hand_index]
        card_left = cx - total_w / 2.0
        card_right = card_left + total_w
        mid_y = 322.0
        if n >= 4:
            box_w, box_h, gap, tip, font_size = 46.0, 46.0, 4.0, 17.0, 14
        elif n == 3:
            box_w, box_h, gap, tip, font_size = 58.0, 46.0, 5.0, 20.0, 17
        else:
            box_w, box_h, gap, tip, font_size = 64.0, 46.0, 5.0, 20.0, 17

        if card_right + gap + box_w + tip <= right - 4:
            tip_x = card_right + gap
            box_x0 = tip_x + tip
            box_x1 = box_x0 + box_w
            points = (tip_x, mid_y,
                      box_x0, mid_y - box_h / 2,
                      box_x1, mid_y - box_h / 2,
                      box_x1, mid_y + box_h / 2,
                      box_x0, mid_y + box_h / 2)
            text_x = (box_x0 + box_x1) / 2
        else:
            tip_x = card_left - gap
            box_x1 = tip_x - tip
            box_x0 = box_x1 - box_w
            points = (tip_x, mid_y,
                      box_x1, mid_y - box_h / 2,
                      box_x0, mid_y - box_h / 2,
                      box_x0, mid_y + box_h / 2,
                      box_x1, mid_y + box_h / 2)
            text_x = (box_x0 + box_x1) / 2

        fill = self._player_hand_badge_fill(hand_index)
        self.canvas.create_polygon(*points, fill=fill, outline='',
                                   tags=('hand_label', 'hand_total_badge', 'player_hand_overlay'))
        hand = self.hands[hand_index]
        natural_blackjack = bool(
            not hand.get('from_split', False)
            and BlackjackEngine.is_blackjack(cards)
        )
        total, soft = BlackjackEngine.hand_value(cards)
        soft_stand = bool(soft and total <= 21 and hand.get('status') == 'stood')
        self.canvas.create_text(
            text_x - 4, mid_y,
            text=self._hand_total_badge_text(
                cards, blackjack=natural_blackjack, soft_stand=soft_stand),
            font=(self.cn_font, font_size, 'bold'), fill='#000000',
            tags=('hand_label', 'hand_total_badge', 'player_hand_overlay'))


    def _dealer_card_target(self, card_index):
        overlap = 42
        count = max(1, len(self.dealer_cards))
        total_w = 100 + max(0, count-1)*overlap
        start_x = 575 - total_w/2
        return start_x + card_index*overlap, 30

    def _draw_dealer_total_badge(self):
        """Dealer gets the same pointed point badge as the player hands."""
        if not self.dealer_cards: return
        overlap=42; total_w=100+max(0,len(self.dealer_cards)-1)*overlap
        left=575-total_w/2; right=left+total_w; mid_y=100.0
        box_w=68.0; box_h=48.0; gap=7.0; tip=22.0
        if right+gap+tip+box_w <= 1118:
            tip_x=right+gap; x0=tip_x+tip; x1=x0+box_w
            pts=(tip_x,mid_y,x0,mid_y-box_h/2,x1,mid_y-box_h/2,x1,mid_y+box_h/2,x0,mid_y+box_h/2)
        else:
            tip_x=left-gap; x1=tip_x-tip; x0=x1-box_w
            pts=(tip_x,mid_y,x1,mid_y-box_h/2,x0,mid_y-box_h/2,x0,mid_y+box_h/2,x1,mid_y+box_h/2)
        dealer_total, dealer_soft = BlackjackEngine.hand_value(self.dealer_cards)
        # V18 dealer point marker: white before dealer play, gold while the dealer
        # is drawing/standing, and light red immediately if the dealer busts.
        if self.dealer_phase_active:
            dealer_badge_fill = '#f2b0b0' if dealer_total > 21 else '#f3cf55'
        else:
            dealer_badge_fill = '#ffffff'
        self.canvas.create_polygon(
            *pts, fill=dealer_badge_fill, outline='',
            tags=('hand_label','dealer_total_badge'))
        dealer_blackjack = BlackjackEngine.is_blackjack(self.dealer_cards)
        dealer_soft_stand = bool(
            dealer_soft and len(self.dealer_cards) >= 2 and 17 <= dealer_total <= 21
        )
        self.canvas.create_text(
            (x0+x1)/2-5, mid_y,
            text=self._hand_total_badge_text(
                self.dealer_cards, blackjack=dealer_blackjack,
                soft_stand=dealer_soft_stand),
            font=(self.cn_font,17,'bold'),fill='#000000',
            tags=('hand_label','dealer_total_badge'))

    def _draw_amount_chip(self, cx, cy, amount, label='', behind=False):
        r = 20
        fill = '#5b2f79' if behind else '#202020'
        outline = '#e8d15b' if not behind else '#d4a8ef'
        self.canvas.create_oval(cx-r,cy-r,cx+r,cy+r,fill=fill,outline=outline,width=3,
                                tags=('hand_wager',))
        self.canvas.create_oval(cx-r+5,cy-r+5,cx+r-5,cy+r-5,fill=fill,outline='#eee3d6',width=1,
                                tags=('hand_wager',))
        if amount >= 1_000_000:
            txt = f'{amount/1_000_000:g}M'
        elif amount >= 1000:
            txt = f'{amount/1000:g}K'
        else:
            txt = f'{amount:g}'
        self.canvas.create_text(cx,cy-5,text=txt,font=(self.cn_font,7,'bold'),fill='white',tags=('hand_wager',))
        if label:
            self.canvas.create_text(cx,cy+8,text=label,font=(self.cn_font,6,'bold'),fill='#ffe898',tags=('hand_wager',))

    def render_cards(self):
        self.canvas.delete('dealt_card'); self.canvas.delete('hand_label')
        self.canvas.delete('hand_zone'); self.canvas.delete('hand_wager')

        for i, card in enumerate(self.dealer_cards):
            x,y=self._dealer_card_target(i); self._render_card(card,x,y,tags=('dealt_card','dealer_dealt_card'))
        if self.dealer_cards: self._draw_dealer_total_badge()
        self.canvas.itemconfigure(self.dealer_total_text, text='')

        centers=self._hand_centers(); n=max(1,len(self.hands)); boundaries=[]
        for i,cx in enumerate(centers):
            left=22 if i==0 else (centers[i-1]+cx)/2+4
            right=1128 if i==n-1 else (cx+centers[i+1])/2-4
            boundaries.append((left,right))
        self.hand_zone_bounds=[]
        for idx,hand in enumerate(self.hands):
            left,right=boundaries[idx]; self.hand_zone_bounds.append((left,230,right,414))
            active=self.round_active and idx==self.active_hand_index and hand['status']=='active'
            # V12: do not use "当前手牌" text and never recolour a lane/background.
            # Split lanes keep only a neutral outline so each card fan still has
            # an obvious centred cell.  The pointed total badge is the state marker.
            if len(self.hands) > 1:
                self.canvas.create_rectangle(left,230,right,414,fill='',outline='#58758c',
                                             width=1,tags=('hand_zone','player_hand_overlay'))
            for j,card in enumerate(hand['cards']):
                x,y=self._player_card_target(idx,j)
                self._render_card(
                    card, x, y,
                    tags=('dealt_card', 'player_dealt_card', f'player_card_{idx}_{j}'))
            self._draw_hand_total_badge(idx,left,right,active=active)
        self._draw_main_hand_wagers()
        for tag in ('dealt_card','hand_wager','hand_label'):
            self.canvas.tag_raise(tag)
        self._render_insurance_chip()

    def _render_card(self, card, x, y, tags=('dealt_card',)):
        if card in self.external_card_images:
            self.canvas.create_image(x, y, image=self.external_card_images[card],
                                     anchor='nw', tags=tags)
            return
        suit, rank = card
        fg = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
        symbol = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}.get(suit, suit[:1])
        self.canvas.create_rectangle(x, y, x + 100, y + 140,
                                     fill='#f4efe4', outline='#d7cbb9', width=2,
                                     tags=tags)
        self.canvas.create_text(x + 50, y + 70, text=f'{rank}\n{symbol}',
                                font=('Arial', 22, 'bold'), fill=fg,
                                justify='center', tags=tags)

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
        self.round_active=True
        self.last_bet=self.current_bet; self.last_side_bets=dict(self.current_side_bets)
        self.round_original_bet=self.current_bet; self.round_side_bets=dict(self.current_side_bets)
        self.current_bet=0.0; self.current_side_bets={key:0.0 for key in self.SIDE_BET_KEYS}
        self.insurance_bet=0.0; self.insurance_result=''; self.insurance_return_amount=0.0
        self.insurance_chip_visible=False; self.flash_insurance_rule=False; self.ace_decision_mode=None
        self.double_choice_mode=False
        self.split_actions=0; self.dealer_cards=[]; self.round_deal_sequence=[]; self.round_discarded_cards=[]
        self.side_bet_results={}
        self.side_bet_return_amounts={}; self.side_bet_hit_odds={}; self.side_bet_hit_labels={}
        self.side_bet_early_collected=set()
        self.flash_winning_side_bets=set(); self.flash_main_bet=False; self.flash_main_push_only=False
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
        deal_step(0)

    def _after_initial_deal(self):
        self._settle_initial_side_bets()
        hand=self.hands[0]; upcard=self.dealer_cards[0]
        player_bj=BlackjackEngine.is_blackjack(hand['cards']); dealer_ace=upcard[1]=='A'
        if dealer_ace:
            self._show_ace_decision('even_money' if player_bj else 'insurance')
            self.update_display(); return
        if player_bj:
            hand['status']='blackjack'; self.render_cards(); self.update_display()
            self._queue(350,self._start_dealer_turn); return
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING); self.update_display()

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
        self._animate_card_from_shoe(card,tx,ty,on_complete=done,flip=True,tag='round_animation_card')

    def _deal_dealer_card_animated(self, on_complete=None):
        card=self.draw_round_card(); card_index=len(self.dealer_cards); self.dealer_cards.append(card)
        tx,ty=self._dealer_card_target(card_index)
        def done():
            self.canvas.delete('round_animation_card')
            self._maybe_settle_crazy7(); self.render_cards(); self.update_display()
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
        self.double_choice_mode=True
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_DOUBLE)
        self.update_display()
        self._set_round_control_visibility(True)
        self._raise_visible_bottom_controls(True)

    def _cancel_double_choice(self):
        if not self.double_choice_mode or self.animation_running:
            return
        self.double_choice_mode=False
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
        self.update_display()
        self._set_round_control_visibility(True)
        self._raise_visible_bottom_controls(True)

    def _resolve_double_choice(self, multiplier):
        hand=self.active_hand()
        multiplier=int(multiplier)
        if (not self.double_choice_mode or multiplier not in (2,3,4)
                or not self.can_double(hand) or self.animation_running):
            return
        add=hand['base_bet']*(multiplier-1)
        if self.balance+1e-9 < add:
            return

        # Lock every player decision immediately after the multiplier is chosen;
        # no button may stay actionable during the wager/card animation.
        self.double_choice_mode=False
        self.animation_running=True
        for button in (*self.action_buttons.values(), *self.double_choice_buttons.values()):
            self._set_button(button, False)
        self._raise_visible_bottom_controls(True)
        self.canvas.itemconfigure(self.phase_text, text=self.PHASE_PLAYING)
        self.balance-=add; hand['double_added']+=add; self.save_balance()
        self.render_cards(); self.update_display()
        def after():
            total,_=BlackjackEngine.hand_value(hand['cards'])
            hand['status']='bust' if total>21 else 'stood'
            hand['result']=f'{multiplier}X加倍爆牌' if total>21 else f'{multiplier}X加倍停牌'
            self.animation_running=False; self.render_cards(); self.update_display()
            self._queue(250,self._advance_hand)
        self._deal_player_card_animated(self.active_hand_index,on_complete=after)


    def _split_target_boundaries(self, count):
        """Return lane bounds for a prospective 1..4-hand player layout."""
        centers = self._hand_centers(count)
        n = len(centers)
        result = []
        for i, cx in enumerate(centers):
            left = 22.0 if i == 0 else (centers[i - 1] + cx) / 2.0 + 4.0
            right = 1128.0 if i == n - 1 else (cx + centers[i + 1]) / 2.0 - 4.0
            result.append((left, 230.0, right, 414.0))
        return result

    def _move_canvas_tag(self, tag, dx, dy):
        """Move every canvas item carrying *tag*; works for image and fallback cards."""
        try:
            self.canvas.move(tag, dx, dy)
        except tk.TclError:
            pass

    def _project_player_card_positions(self, hands_snapshot, count=None):
        """Top-left positions for every visible card under an arbitrary hand layout."""
        hand_count = max(1, min(self.MAX_HANDS, int(count if count is not None else len(hands_snapshot) or 1)))
        centers = self._hand_centers(hand_count)
        overlap = self._hand_overlap(hand_count)
        positions = {}
        for idx, hand in enumerate(hands_snapshot[:hand_count]):
            cards = list(hand.get('cards', []))
            if not cards:
                continue
            total_w = 100.0 + max(0, len(cards) - 1) * overlap
            start_x = centers[idx] - total_w / 2.0
            for card_index in range(len(cards)):
                positions[(idx, card_index)] = (start_x + card_index * overlap, 252.0)
        return positions

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
        """Safety fallback used only when the expected rendered card tags are absent."""
        self.canvas.delete('split_lane_animation')
        self.hands[hand_index] = left
        self.hands.insert(hand_index + 1, right)
        self.animation_running = False
        self.render_cards()
        self.update_display()
        self._prepare_active_split_hand()

    def _animate_split_sequence(self, hand_index, left, right):
        """Elegant split animation that also reflows every existing hand.

        The animation is designed to remain readable no matter which active hand
        is split, and it scales up through the full split limit.
        """
        old_hands = [dict(hand, cards=list(hand.get('cards', []))) for hand in self.hands]
        preview_hands = (
            old_hands[:hand_index]
            + [dict(left, cards=list(left.get('cards', []))), dict(right, cards=list(right.get('cards', [])))]
            + old_hands[hand_index + 1:]
        )
        old_count = max(1, len(old_hands))
        new_count = max(1, len(preview_hands))
        first_tag = f'player_card_{hand_index}_0'
        second_tag = f'player_card_{hand_index}_1'

        if (not self.canvas.find_withtag(first_tag)
                or not self.canvas.find_withtag(second_tag)):
            self._finish_split_without_animation(hand_index, left, right)
            return

        self.canvas.delete('hand_label')
        self.canvas.delete('hand_zone')
        self.canvas.delete('split_lane_animation')
        self.canvas.tag_raise('dealt_card')

        old_positions = self._project_player_card_positions(old_hands, old_count)
        final_positions = self._project_player_card_positions(preview_hands, new_count)

        if (hand_index, 0) not in old_positions or (hand_index, 1) not in old_positions:
            self._finish_split_without_animation(hand_index, left, right)
            return

        old_centers = self._hand_centers(old_count)
        current_cx = old_centers[min(hand_index, len(old_centers) - 1)]
        old_first = old_positions[(hand_index, 0)]
        old_second = old_positions[(hand_index, 1)]
        first_final = final_positions[(hand_index, 0)]
        second_final = final_positions[(hand_index + 1, 0)]

        focus_overlap = 24
        focus_width = 100.0 + focus_overlap
        focus_y = old_first[1] - 14.0
        focus_first = (current_cx - focus_width / 2.0, focus_y)
        focus_second = (focus_first[0] + focus_overlap, focus_y)

        split_mid = ((first_final[0] + 50.0) + (second_final[0] + 50.0)) / 2.0
        travel_overlap = 22
        travel_width = 100.0 + travel_overlap
        travel_y = 238.0
        travel_first = (split_mid - travel_width / 2.0, travel_y)
        travel_second = (travel_first[0] + travel_overlap, travel_y)

        self.canvas.tag_raise(first_tag)
        self.canvas.tag_raise(second_tag)

        def stage_two():
            old_bounds = self._split_target_boundaries(old_count)
            new_bounds = self._split_target_boundaries(new_count)
            rects = []
            start_bounds = []
            end_bounds = []
            for new_idx in range(new_count):
                if new_idx < hand_index:
                    source = old_bounds[new_idx]
                elif new_idx in (hand_index, hand_index + 1):
                    source = old_bounds[hand_index]
                else:
                    source = old_bounds[new_idx - 1]
                rect = self.canvas.create_rectangle(
                    *source, fill='', outline='#6a89a2', width=1,
                    dash=(5, 4), tags=('split_lane_animation',))
                rects.append(rect)
                start_bounds.append(source)
                end_bounds.append(new_bounds[new_idx])
            self.canvas.tag_raise('split_lane_animation')
            self.canvas.tag_raise(first_tag)
            self.canvas.tag_raise(second_tag)

            start_map = {
                first_tag: focus_first,
                second_tag: focus_second,
            }
            end_map = {
                first_tag: travel_first,
                second_tag: travel_second,
            }

            for old_idx, hand in enumerate(old_hands):
                if old_idx == hand_index:
                    continue
                new_idx = old_idx if old_idx < hand_index else old_idx + 1
                for card_index in range(len(hand.get('cards', []))):
                    tag = f'player_card_{old_idx}_{card_index}'
                    start = old_positions.get((old_idx, card_index))
                    end = final_positions.get((new_idx, card_index))
                    if start and end and self.canvas.find_withtag(tag):
                        start_map[tag] = start
                        end_map[tag] = end

            current = {key: tuple(value) for key, value in start_map.items()}
            steps = 14
            frame_ms = 20

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
                for rect, src, dst in zip(rects, start_bounds, end_bounds):
                    bounds = tuple(src[i] + (dst[i] - src[i]) * eased for i in range(4))
                    self.canvas.coords(rect, *bounds)
                if step < steps:
                    self._queue(frame_ms, frame, step + 1)
                else:
                    self._animate_canvas_positions(
                        {first_tag: travel_first, second_tag: travel_second},
                        {first_tag: first_final, second_tag: second_final},
                        duration_ms=360, easing='out',
                        arc_lifts={first_tag: 10.0, second_tag: 18.0},
                        on_complete=stage_three_done)

            self._queue(frame_ms, frame, 1)

        def stage_three_done():
            self.canvas.delete('split_lane_animation')
            self.hands = preview_hands
            self.animation_running = False
            self.render_cards()
            self.update_display()
            self._prepare_active_split_hand()

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
        # Effective shoe excludes rank 9 and rank 10; J/Q/K remain ten-valued.
        outcomes=[(11,1/11)]+[(v,1/11) for v in range(2,9)]+[(10,3/11)]
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
        """Infinite-deck S17 dealer distribution: 17..21,bust."""
        total=int(total); soft=bool(soft)
        if total>21: return (0,0,0,0,0,1.0)
        if total>=17:
            arr=[0.0]*6; arr[total-17 if total<=21 else 5]=1.0; return tuple(arr)
        outcomes=[(11,1/11)]+[(v,1/11) for v in range(2,9)]+[(10,3/11)]
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

        outcomes=((11,1/11),)+tuple((v,1/11) for v in range(2,9))+((10,3/11),)
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
        """Return the live cash-out offer using an infinite-deck Hit/Stand model.

        No real shoe composition or remaining-card count is consulted.  V16
        doubles the previous offer: 2 × outright win probability × current-hand stake.
        """
        if not self.can_surrender(hand) or not self.dealer_cards:
            return 0.0,0.0,1.0,0.0
        ptotal,psoft=BlackjackEngine.hand_value(hand['cards'])
        dtotal,dsoft=self._upcard_state(self.dealer_cards[0])
        win,bust=self._infinite_optimal_hit_stand(ptotal,psoft,dtotal,dsoft)
        credit=self.hand_stake(hand)*win*2.0
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
        else:
            self.side_bet_return_amounts[key] = 0.0
            self.side_bet_results[key] = f'{label} {odds:g}:1'

    @staticmethod
    def _open_card_luck_result(player_cards, dealer_upcard):
        """Return (profit_odds, label) for 明牌运气.

        The dealer upcard must be 2-7.  The player tier is based only on the
        player's first two cards, with the listed tiers applied in priority order.
        """
        if len(player_cards) < 2 or not dealer_upcard:
            return (None, '资料不足')
        p0, p1 = player_cards[:2]
        if dealer_upcard[1] not in ('2', '3', '4', '5', '6', '7'):
            return (None, '庄家明牌非2-7')

        spade_ja = (
            {p0, p1} == {('Spade', 'J'), ('Spade', 'A')}
        )
        if spade_ja:
            return (70, '黑桃J+黑桃A')
        if BlackjackEngine.is_blackjack([p0, p1]):
            return (7, '黑杰克')

        total, _soft = BlackjackEngine.hand_value([p0, p1])
        if 9 <= total <= 11:
            return (3, f'{total}点')
        if 18 <= total <= 20:
            return (3, f'{total}点')
        return (None, '未中')

    def _settle_initial_side_bets(self):
        if not self.hands or len(self.hands[0]['cards']) < 2 or not self.dealer_cards:
            return
        p0, p1 = self.hands[0]['cards'][:2]
        dealer = self.dealer_cards[0]

        # Perfect Pair: always evaluate so a hit flashes even with zero stake.
        odds = None
        label = '完美对子'
        if p0[1] == p1[1]:
            if p0[0] == p1[0]:
                odds, label = 21, '同花对子'
            elif self._same_color(p0, p1):
                odds, label = 10, '同色对子'
            else:
                odds, label = 5, '杂色对子'
        self._credit_side_bet('Perfect Pair', odds, label)

        trio = [p0, p1, dealer]
        suits_same = len({card[0] for card in trio}) == 1
        ranks_same = len({card[1] for card in trio}) == 1
        straight = self._is_three_card_straight(trio)

        # 21+3: suited trips > straight flush > trips > straight > flush.
        if suits_same and ranks_same:
            result = (90, '三张同花同点')
        elif suits_same and straight:
            result = (35, '同花顺')
        elif ranks_same:
            result = (25, '三条')
        elif straight:
            result = (10, '顺子')
        elif suits_same:
            result = (4, '同花')
        else:
            result = (None, '未中')
        self._credit_side_bet('21+3', *result)

        # 明牌运气: dealer upcard 2-7 gates the player's two-card tier.
        self._credit_side_bet(
            'Open Card Luck', *self._open_card_luck_result([p0, p1], dealer))

        # Hot 21. Exact three 7s have priority. Ace may count as 1 or 11.
        all_sevens = all(card[1] == '7' for card in trio)
        totals = self._three_card_totals(trio)
        if all_sevens and suits_same:
            result = (400, '同花三7')
        elif all_sevens:
            result = (80, '三7')
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

        # V19: if Crazy 7 was already known to lose from target card 0, its
        # collection was intentionally deferred until this same post-deal stage
        # where the other resolved losing side bets are collected.
        if self.side_bet_results.get('Crazy 7') == '输':
            self._collect_losing_side_bet_upward('Crazy 7')

        self.save_balance()

    def _maybe_settle_crazy7(self):
        """Synchronise Crazy 7 progressively from round cards 0 -> 2 -> 3.

        Card 0 decides whether the bet is already dead.  If it is a 7, show the
        currently secured 4:1 tier while waiting for card 2.  If card 2 is not a
        7, 4:1 is final; if card 2 is a 7, show the secured 18:1/100:1 tier while
        waiting for card 3.  Card 3 then performs the final odds synchronisation:
        another 7 upgrades to 325:1/1500:1, otherwise the card-2 tier remains.
        Provisional tiers only update the pointed odds marker; money is credited
        exactly once when the tier becomes final.
        """
        key = 'Crazy 7'
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

        # Card 0 is a 7: 4:1 is already secured, but it is provisional until
        # target card 2 is known.
        self.side_bet_hit_odds[key] = 4.0
        self.side_bet_hit_labels[key] = '第一目标7'
        if len(seq) < 3:
            return

        c2 = seq[2]
        if c2[1] != '7':
            self._credit_side_bet(key, 4, '第一目标7')
            self.save_balance()
            return

        # Cards 0 and 2 are both 7.  The secured tier is 18:1, or 100:1 when
        # those two target cards share a suit.  Keep it provisional until card 3.
        if c0[0] == c2[0]:
            provisional_odds, provisional_label = 100.0, '前两目标同花7'
        else:
            provisional_odds, provisional_label = 18.0, '前两目标7'
        self.side_bet_hit_odds[key] = provisional_odds
        self.side_bet_hit_labels[key] = provisional_label
        if len(seq) < 4:
            return

        c3 = seq[3]
        if c3[1] == '7':
            if c0[0] == c2[0] == c3[0]:
                result = (1500, '目标三张同花7')
            else:
                result = (325, '目标三张7')
        else:
            result = (provisional_odds, provisional_label)

        # Final card is known: overwrite the provisional marker with the final
        # correct tier, then settle/credit exactly once.
        self.side_bet_hit_odds.pop(key, None)
        self.side_bet_hit_labels.pop(key, None)
        self._credit_side_bet(key, *result)
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
                odds = 200
            elif count == 7:
                odds = 80
            elif count == 6:
                odds = 40
            elif count == 5:
                odds = 7.5
            elif count == 4:
                odds = 1.5
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
        if not self.round_active or self._has_bust_wager():
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
        self._settle_bust_side_bet()
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
        if not self.round_active or self.animation_running: return

        bust_wager = self._has_bust_wager()
        all_dead = self._all_hands_bust_or_surrendered()
        natural = self._single_natural_blackjack()
        up_rank = self.dealer_cards[0][1] if self.dealer_cards else None

        # V18 fast paths apply only when Bust! was NOT wagered.
        if not bust_wager:
            if all_dead and self.insurance_bet <= 0.0:
                # All hands are already lost/cashed out: no hole card is needed.
                self.animation_running = True
                self.canvas.itemconfigure(self.phase_text, text=self.PHASE_SETTLING)
                self.render_cards(); self.update_display()
                self._queue(220, self._resolve_normal_round)
                return

            if natural and up_rank not in ('A', '10', 'J', 'Q', 'K'):
                # Player natural versus dealer 2-9 wins immediately at 3:2.
                self.animation_running = True
                self.canvas.itemconfigure(self.phase_text, text=self.PHASE_SETTLING)
                self.render_cards(); self.update_display()
                self._queue(220, self._resolve_normal_round)
                return

        self.dealer_phase_active=True
        self.animation_running=True
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
        # All player processing is complete: player pointed totals return to white.
        # During dealer play the dealer's pointed total is gold, or light red on bust.
        self.render_cards(); self.update_display()

        def after_second():
            dealer_bj = BlackjackEngine.is_blackjack(self.dealer_cards[:2])
            if not bust_wager:
                # Insurance with every player hand already bust/surrendered needs
                # exactly this one card; 10/J/Q/K against the dealer Ace wins it.
                if all_dead and self.insurance_bet > 0.0:
                    self._queue(260, self._resolve_finished_hands_after_insurance_probe)
                    return
                # A player natural versus dealer 10-K/A also needs exactly one
                # dealer card: dealer BJ -> PUSH, otherwise player BJ wins.
                if natural:
                    self._queue(260, self._resolve_dealer_blackjack if dealer_bj else self._resolve_normal_round)
                    return
            if dealer_bj:
                self._queue(260,self._resolve_dealer_blackjack)
            else:
                self._queue(260,self._dealer_draw_until_done)
        self._deal_dealer_card_animated(on_complete=after_second)

    def _dealer_draw_until_done(self):
        total,_soft=BlackjackEngine.hand_value(self.dealer_cards)
        if total < 17:
            self.canvas.itemconfigure(self.phase_text,text=self.PHASE_PLAYING)
            self._deal_dealer_card_animated(on_complete=lambda:self._queue(180,self._dealer_draw_until_done))
            return
        self._queue(260,self._resolve_normal_round)

    def _resolve_dealer_blackjack(self):
        dealer_bj = True
        self._maybe_settle_crazy7()
        self._settle_bust_side_bet()
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
        self._settle_bust_side_bet()
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
        """Prepare component flashes; insurance win flashes the complete rule strip."""
        # V19: do not clear dealer_phase_active here.  A dealer that actually
        # reached its stand/bust result keeps the point badge gold/red through
        # settlement instead of reverting to white.  _reset_after_round clears
        # the phase state after the final card image has already been preserved.
        self.animation_running=False; self.save_balance()
        self.last_win_amount = self._calculate_last_win_amount()
        self.show_last_win = True
        self.canvas.itemconfigure(self.phase_text,text=self.PHASE_SETTLING)
        # V10: every winning side-bet condition flashes, even with no wager.
        self.flash_winning_side_bets=set(self.side_bet_hit_odds)
        self.flash_winning_hand_indices={i for i,h in enumerate(self.hands) if float(h.get('settlement_return',0.0))>0.0}
        returned_hands=[h for h in self.hands if float(h.get('settlement_return',0.0))>0.0]
        self.flash_main_bet=bool(returned_hands)
        # A pure PUSH main-game return uses a shallow-blue flash.  If any returned
        # hand is a true win/cashout/refund, white keeps precedence for the whole MAIN.
        self.flash_main_push_only=bool(returned_hands) and all(h.get('settlement')=='push' for h in returned_hands)
        self.flash_insurance_rule=bool(dealer_bj and self.insurance_bet>0 and self.insurance_return_amount>0)
        self.settlement_running=True; self.settlement_flash_step=0; self.flash_mode='original'
        # Re-render first so losing stationary chips are removed.  Matching clones
        # then fly upward for 0.30 s exactly as the first flash begins.
        self.render_cards(); self.update_display()
        def start_flash():
            self._animate_losing_chips_out()
            self.run_settlement_flash()
        self._queue(80,start_flash)

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
        self._set_rules_strip_visible(False)

        self.round_active=False; self.round_original_bet=0.0
        self.round_side_bets={key:0.0 for key in self.SIDE_BET_KEYS}
        self.side_bet_results={}; self.side_bet_return_amounts={}
        self.side_bet_hit_odds={}; self.side_bet_hit_labels={}
        self.side_bet_early_collected=set()
        self.flash_winning_side_bets=set(); self.flash_main_bet=False; self.flash_main_push_only=False
        self.flash_winning_hand_indices=set(); self.flash_insurance_rule=False
        self.settlement_running=False; self.settlement_flash_step=0; self.flash_mode=None
        self.dealer_phase_active=False
        self.round_deal_sequence=[]; self.round_discarded_cards=[]
        self.insurance_bet=0.0; self.insurance_result=''
        self.insurance_return_amount=0.0; self.insurance_chip_visible=False; self.ace_decision_mode=None
        self.double_choice_mode=False
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
                text=f'本局下注: {self.format_money(round_bet)}')
        else:
            pending=self.current_bet+sum(self.current_side_bets.values())
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'本局下注: {self.format_money(pending)}')
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
            self._set_button(self.decision_buttons.get('accept'),True,'立刻获胜')
            self._set_button(self.decision_buttons.get('decline'),True,'赌！')

        hand=self.active_hand()
        if self.double_choice_mode and hand:
            for multiplier in (2,3,4):
                required=hand['base_bet']*(multiplier-1)
                self._set_button(
                    self.double_choice_buttons.get(f'{multiplier}x'),
                    self.balance+1e-9>=required,
                    f'{multiplier}X')
            self._set_button(self.double_choice_buttons.get('back'),True,'返回')

        self._set_round_control_visibility(self.round_active)
        active=bool(self.round_active and not self.animation_running and not self.settlement_running
                    and not self.ace_decision_mode and not self.double_choice_mode
                    and hand and hand['status']=='active'
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

    def show_game_instructions(self):
        parent = self.winfo_toplevel()

        # 防止重复打开多个说明窗口。
        existing = getattr(self, '_instruction_window', None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass

        dialog = tk.Toplevel(parent)
        self._instruction_window = dialog
        dialog.title('倍注黑杰克 · 游戏说明')
        dialog.configure(bg='#0f1311')
        dialog.resizable(False, False)
        dialog.transient(parent)

        # 1000 x 650，正中当前游戏窗口。
        win_w, win_h = 1000, 650
        parent.update_idletasks()
        pw = max(1, parent.winfo_width())
        ph = max(1, parent.winfo_height())
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pos_x = px + (pw - win_w) // 2
        pos_y = py + (ph - win_h) // 2
        dialog.geometry(f'{win_w}x{win_h}+{pos_x}+{pos_y}')
        dialog.minsize(win_w, win_h)
        dialog.maxsize(win_w, win_h)

        font_name = getattr(self, 'cn_font', 'Microsoft YaHei UI')

        BG = '#0f1311'
        HEADER = '#151b18'
        PANEL = '#18201c'
        PANEL_2 = '#202923'
        BORDER = '#43534a'
        GOLD = '#e7d36c'
        TEXT = '#f4f4ee'
        MUTED = '#c1cbc6'
        GREEN = '#0b5f4c'
        GREEN_2 = '#164f47'
        RED = '#8c3f43'
        BLUE = '#315b72'
        ORANGE = '#a56d2c'
        PURPLE = '#70439a'
        CASH = '#7c3b40'
        BLACK = '#111111'
        WHITE = '#ffffff'

        FONT_SMALL = 14
        FONT_NORMAL = 15
        FONT_MEDIUM = 16
        FONT_LARGE = 18
        FONT_TITLE = 20

        # ================================================================
        # 顶部标题栏
        # ================================================================
        header = tk.Frame(dialog, bg=HEADER, height=82)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header, text='倍注黑杰克  POWER BLACKJACK',
            font=(font_name, FONT_TITLE, 'bold'), fg=GOLD, bg=HEADER
        ).place(x=24, y=10)
        tk.Label(
            header, text='玩法 · 连续洗牌 · 决策按钮 · 下注区域 · 赔付表',
            font=(font_name, FONT_SMALL), fg=MUTED, bg=HEADER
        ).place(x=25, y=48)

        close_btn = tk.Button(
            header, text='关闭  ESC', command=dialog.destroy,
            font=(font_name, FONT_SMALL, 'bold'),
            bg='#2a332e', fg=TEXT,
            activebackground='#3a463f', activeforeground=WHITE,
            relief=tk.FLAT, bd=0, cursor='hand2')
        close_btn.place(x=850, y=20, width=120, height=42)
        tk.Frame(dialog, bg=GOLD, height=3).pack(fill=tk.X, side=tk.TOP)

        # ================================================================
        # Scroll Canvas
        # ================================================================
        scroll_host = tk.Frame(dialog, bg=BG)
        scroll_host.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(
            scroll_host, bg=BG, highlightthickness=0, bd=0,
            yscrollincrement=40)
        scrollbar = tk.Scrollbar(
            scroll_host, orient=tk.VERTICAL, command=canvas.yview,
            bg='#263029', troughcolor='#111512', activebackground=GOLD,
            relief=tk.FLAT, bd=0, width=14)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                    padx=(12, 0), pady=(10, 10))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y,
                       padx=(0, 9), pady=(10, 10))

        content = tk.Frame(canvas, bg=BG)
        content_window = canvas.create_window((0, 0), window=content, anchor='nw')

        def _sync_scrollregion(_event=None):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _fit_content_width(event):
            canvas.itemconfigure(content_window, width=event.width)

        content.bind('<Configure>', _sync_scrollregion)
        canvas.bind('<Configure>', _fit_content_width)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
            return 'break'

        dialog.bind('<MouseWheel>', _on_mousewheel)
        dialog.bind('<Button-4>', lambda _e: (canvas.yview_scroll(-1, 'units'), 'break')[1])
        dialog.bind('<Button-5>', lambda _e: (canvas.yview_scroll(1, 'units'), 'break')[1])

        # ================================================================
        # Helpers
        # ================================================================
        def make_card(title, subtitle=None, pady=(8, 8)):
            card = tk.Frame(
                content, bg=PANEL,
                highlightbackground=BORDER, highlightcolor=BORDER,
                highlightthickness=1, bd=0)
            card.pack(fill=tk.X, padx=10, pady=pady)
            head = tk.Frame(card, bg=PANEL)
            head.pack(fill=tk.X, padx=18, pady=(15, 10))
            tk.Label(
                head, text=title, font=(font_name, FONT_LARGE, 'bold'),
                fg=GOLD, bg=PANEL, anchor='w').pack(side=tk.LEFT)
            if subtitle:
                tk.Label(
                    head, text=subtitle, font=(font_name, FONT_SMALL),
                    fg=MUTED, bg=PANEL, anchor='e').pack(side=tk.RIGHT)
            return card

        def add_rule(parent_frame, title, body, accent=GOLD):
            row = tk.Frame(parent_frame, bg=PANEL)
            row.pack(fill=tk.X, padx=18, pady=6)
            tk.Frame(row, bg=accent, width=5).pack(
                side=tk.LEFT, fill=tk.Y, padx=(0, 12))
            text_box = tk.Frame(row, bg=PANEL)
            text_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(
                text_box, text=title,
                font=(font_name, FONT_MEDIUM, 'bold'),
                fg=TEXT, bg=PANEL, anchor='w').pack(fill=tk.X)
            tk.Label(
                text_box, text=body,
                font=(font_name, FONT_SMALL), fg=MUTED, bg=PANEL,
                anchor='w', justify=tk.LEFT, wraplength=850
            ).pack(fill=tk.X, pady=(4, 0))

        def table_block(parent_frame, title, rows):
            block = tk.Frame(
                parent_frame, bg=PANEL_2,
                highlightbackground='#354139', highlightthickness=1, bd=0)
            tk.Label(
                block, text=title,
                font=(font_name, FONT_MEDIUM, 'bold'),
                fg=BLACK, bg=GOLD, anchor='w', padx=12, pady=8
            ).pack(fill=tk.X)
            grid = tk.Frame(block, bg=PANEL_2)
            grid.pack(fill=tk.BOTH, expand=True)
            grid.grid_columnconfigure(0, weight=1)
            grid.grid_columnconfigure(1, minsize=120)
            for i, (condition, payout) in enumerate(rows):
                row_bg = '#1b241f' if i % 2 == 0 else '#202923'
                tk.Label(
                    grid, text=condition, font=(font_name, FONT_SMALL),
                    fg=TEXT, bg=row_bg, anchor='w', padx=12, pady=7
                ).grid(row=i, column=0, sticky='nsew', padx=(0, 1), pady=(0, 1))
                tk.Label(
                    grid, text=payout, font=(font_name, FONT_SMALL, 'bold'),
                    fg=GOLD, bg=row_bg, anchor='center', padx=8, pady=7
                ).grid(row=i, column=1, sticky='nsew', pady=(0, 1))
            return block

        # ================================================================
        # 01 游戏玩法 / 切牌
        # ================================================================
        rules_card = make_card(
            '01  游戏玩法与连续洗牌说明',
            '8副牌 · 发牌时移除9与10 · ENHC / OBO · S17')
        columns = tk.Frame(rules_card, bg=PANEL)
        columns.pack(fill=tk.X, padx=6, pady=(0, 14))
        left_rules = tk.Frame(columns, bg=PANEL)
        right_rules = tk.Frame(columns, bg=PANEL)
        left_rules.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 7))
        right_rules.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(7, 0))

        add_rule(
            left_rules, '核心牌组规则：移除9和10',
            '本游戏不会向玩家或庄家发出点数牌9和点数牌10。牌靴每次抽到这两个牌面时，'
            '会立刻将该牌放进废牌区，并继续抽取，直到把其后第一张非9、非10的牌发出。'
            '只有牌面为9和10的牌被移除；J、Q、K仍然保留，并继续按10点计算。',
            accent='#d94a4e')
        add_rule(
            left_rules, '基本目标',
            '尽量让手牌接近21点而不爆牌，并击败庄家。庄家硬17、软17均停牌（S17）。'
            '普通获胜1:1；未分牌的两张天然黑杰克按3:2支付。')
        add_rule(
            left_rules, '欧洲无底牌 ENHC + OBO',
            '庄家起手只拿一张明牌，庄家回合才拿第二张。若庄家最终为Blackjack，'
            '额外分牌/加倍本金按OBO退回，只有Original Bet承担庄家Blackjack的损失。')
        add_rule(
            left_rules, '分牌 / 加倍',
            '同点数价值的两张牌可分牌，最多分牌3次（共4手）；允许分牌后加倍（DAS）。'
            '任意非分A手只要仍为两张牌即可选择加倍；点击后可选2X、3X或4X总倍数，'
            '分别追加当前手原注的1、2或3倍，只再拿一张牌后自动停牌。可按“返回”取消选择。')
        add_rule(
            left_rules, '分A规则',
            'A-A可分牌。分A后当前手只补一张；若补到A并且仍未达到最多4手限制，可继续分A；'
            '否则该手自动停牌。')
        add_rule(
            left_rules, '庄家A与保险',
            '庄家明牌A时可购买保险，保险金额为Original Bet的一半，中奖利润2:1。'
            '玩家天然Blackjack遇庄家A时，可选择“立刻获胜”按1:1锁定，或选择“赌！”。')

        add_rule(
            right_rules, '① 连续洗牌机',
            '使用8副52张牌，共416张；所有牌局均由CSM_Shuffler连续洗牌机发牌。',
            accent='#7cc8aa')
        add_rule(
            right_rules, '② 9与10进入废牌区',
            '玩家或庄家取牌时，如抽到点数牌9或点数牌10，该牌立即进入废牌区；'
            '本次实际拿到的是它后方第一张非9、非10的牌。J、Q、K不受影响。',
            accent='#7cc8aa')
        add_rule(
            right_rules, '③ 牌张回收',
            '每局结束后，已发出的牌进入弃牌区，由连续洗牌机按规则重新混入牌仓。',
            accent='#7cc8aa')
        add_rule(
            right_rules, '④ 无需换靴',
            '不使用剩余牌阈值、切牌或烧牌流程；下一局直接由连续洗牌机供牌。',
            accent='#7cc8aa')
        add_rule(
            right_rules, '⑤ 即时兑现',
            '即时兑现不读取真实牌靴；使用已移除9与10的无限牌组模型，仅比较Hit/Stand路线。'
            '显示金额 = 2 × 当前估算获胜概率 × 当前手本金。',
            accent='#7cc8aa')

        # ================================================================
        # 02 玩家决策按钮
        # ================================================================
        button_card = make_card(
            '02  玩家决策按钮',
            '所有示意图均由Canvas即时绘制')
        button_cv = tk.Canvas(
            button_card, width=930, height=380,
            bg=PANEL, highlightthickness=0)
        button_cv.pack(fill=tk.X, padx=16, pady=(0, 16))

        def draw_small_card(cv, x, y, rank='A', suit='♠', red=False):
            cv.create_rectangle(
                x, y, x + 40, y + 55, fill='#f5f0e5',
                outline='#d7cbb9', width=2)
            cv.create_text(
                x + 11, y + 13, text=rank,
                font=('Arial', FONT_SMALL, 'bold'),
                fill='#b92f3b' if red else BLACK)
            cv.create_text(
                x + 20, y + 36, text=suit,
                font=('Arial', FONT_SMALL, 'bold'),
                fill='#b92f3b' if red else BLACK)

        def action_icon(cv, kind, x, y, color):
            if kind == 'hit':
                draw_small_card(cv, x, y + 5, '7', '♣')
                draw_small_card(cv, x + 18, y, '4', '♥', True)
                cv.create_oval(x + 50, y + 29, x + 76, y + 55, fill=GOLD, outline='')
                cv.create_text(x + 63, y + 42, text='+',
                               font=('Arial', FONT_LARGE, 'bold'), fill=BLACK)
            elif kind == 'stand':
                cv.create_rectangle(x + 10, y + 5, x + 69, y + 56,
                                    fill='#f1ede4', outline='#d6cab7', width=2)
                cv.create_text(x + 39, y + 31, text='STOP',
                               font=('Arial', FONT_SMALL, 'bold'), fill=RED)
            elif kind == 'double':
                cv.create_oval(x + 5, y + 15, x + 50, y + 60,
                               fill=color, outline='#f3df9a', width=2)
                cv.create_oval(x + 34, y + 3, x + 79, y + 48,
                               fill=color, outline='#f3df9a', width=2)
                cv.create_text(x + 42, y + 32, text='2×',
                               font=('Arial', FONT_SMALL, 'bold'), fill=WHITE)
            elif kind == 'split':
                draw_small_card(cv, x + 2, y + 3, '8', '♠')
                draw_small_card(cv, x + 44, y + 3, '8', '♦', True)
            elif kind == 'cashout':
                cv.create_oval(x + 10, y + 8, x + 65, y + 63,
                               fill='#d4b64a', outline='#fff0a0', width=2)
                cv.create_text(x + 37, y + 35, text='$',
                               font=('Arial', FONT_TITLE, 'bold'), fill=BLACK)
            elif kind == 'ace':
                draw_small_card(cv, x + 2, y + 5, 'A', '♠')
                cv.create_rectangle(x + 50, y + 6, x + 88, y + 29,
                                    fill=ORANGE, outline='')
                cv.create_rectangle(x + 50, y + 38, x + 88, y + 61,
                                    fill=BLUE, outline='')
                cv.create_text(x + 69, y + 17, text='YES',
                               font=('Arial', FONT_SMALL, 'bold'), fill=WHITE)
                cv.create_text(x + 69, y + 49, text='NO',
                               font=('Arial', FONT_SMALL, 'bold'), fill=WHITE)

        def draw_action_tile(x, y, title, detail, color, kind):
            w, h = 440, 108
            button_cv.create_rectangle(
                x + 3, y + 4, x + w + 3, y + h + 4,
                fill='#090c0a', outline='')
            button_cv.create_rectangle(
                x, y, x + w, y + h,
                fill=PANEL_2, outline='#46554d', width=1)
            button_cv.create_rectangle(
                x + 12, y + 13, x + 112, y + 94,
                fill=color, outline='#d8d0bd', width=1)
            action_icon(button_cv, kind, x + 20, y + 21, color)
            button_cv.create_text(
                x + 130, y + 27, text=title, anchor='w',
                font=(font_name, FONT_MEDIUM, 'bold'), fill=TEXT)
            button_cv.create_text(
                x + 130, y + 61, text=detail, anchor='w', width=290,
                font=(font_name, FONT_SMALL), fill=MUTED)

        draw_action_tile(10, 10, '要牌  HIT',
                         '再要一张牌；爆牌后当前手立即结束。', BLUE, 'hit')
        draw_action_tile(470, 10, '停牌  STAND',
                         '结束当前手并进入下一手或庄家回合。', '#5b4938', 'stand')
        draw_action_tile(10, 128, '加倍  DOUBLE',
                         '两张牌可选2X/3X/4X；可返回，只拿一张后自动停牌。', ORANGE, 'double')
        draw_action_tile(470, 128, '分牌  SPLIT',
                         '同点值两张牌可分牌；最多分牌3次（共4手），允许DAS。', PURPLE, 'split')
        draw_action_tile(10, 246, '兑现金额  CASH OUT',
                         '符合条件时按当前胜率模型显示即时兑现金额。', CASH, 'cashout')
        draw_action_tile(470, 246, '庄家明牌A的决策',
                         '正常询问：购买保险 / 不购买\n玩家黑杰克：立刻获胜 / 赌！', '#4e4030', 'ace')

        # ================================================================
        # 03 下注区域 / 限红
        # ================================================================
        bet_card = make_card(
            '03  下注区域与限红',
            '主注 MAX $500K · 每个边注 MAX $100K')
        bet_cv = tk.Canvas(
            bet_card, width=930, height=310,
            bg=PANEL, highlightthickness=0)
        bet_cv.pack(fill=tk.X, padx=16, pady=(0, 15))
        bet_cv.create_rectangle(
            8, 8, 922, 302, fill='#103f36', outline='#4f6f64', width=2)
        bet_cv.create_text(
            30, 30, anchor='w', text='可下注区域示意',
            font=(font_name, FONT_MEDIUM, 'bold'), fill=TEXT)
        bet_cv.create_text(
            900, 30, anchor='e', text='主注最低 $100',
            font=(font_name, FONT_SMALL), fill='#bcd2c8')
        bet_cv.create_oval(
            335, 70, 595, 240, fill=GREEN, outline='#9de46f', width=4)
        bet_cv.create_text(
            465, 125, text='主注\nBLACKJACK',
            font=(font_name, FONT_LARGE, 'bold'), fill=WHITE, justify=tk.CENTER)
        bet_cv.create_text(
            465, 195, text='MAX $500K',
            font=(font_name, FONT_MEDIUM, 'bold'), fill=GOLD)

        side_spots = [
            (40, 74, 225, 140, '完美对子'),
            (40, 172, 225, 238, '21+3'),
            (240, 224, 405, 288, '明牌运气'),
            (525, 224, 690, 288, '疯狂7'),
            (705, 172, 890, 238, '热辣21'),
            (705, 74, 890, 140, '爆牌!'),
        ]
        for x0, y0, x1, y1, label in side_spots:
            bet_cv.create_oval(
                x0, y0, x1, y1, fill=GREEN_2,
                outline='#9de46f', width=3)
            bet_cv.create_text(
                (x0 + x1) / 2, (y0 + y1) / 2 - 10,
                text=label, font=(font_name, FONT_SMALL, 'bold'), fill=WHITE)
            bet_cv.create_text(
                (x0 + x1) / 2, (y0 + y1) / 2 + 15,
                text='MAX $100K', font=(font_name, FONT_SMALL), fill=GOLD)

        tk.Label(
            bet_card,
            text='主注最低 $100、最高 $500,000；六个边注各自最高 $100,000。右键可清除对应下注。',
            font=(font_name, FONT_SMALL), fg=MUTED, bg=PANEL,
            anchor='w', justify=tk.LEFT, wraplength=920
        ).pack(fill=tk.X, padx=20, pady=(0, 16))

        # ================================================================
        # 04 主注赔付
        # ================================================================
        payout_card = make_card(
            '04  主注与保险赔付',
            '赔率表示利润赔率；正常中奖同时返还下注本金')
        main_table = table_block(
            payout_card, '主注 / 保险', [
                ('普通主注获胜', '1:1'),
                ('玩家天然Blackjack（未分牌两张21）', '3:2'),
                ('分牌后两张牌组成21点', '1:1'),
                ('玩家Blackjack + 庄家A选择“立刻获胜”', '1:1'),
                ('保险中奖（庄家Blackjack）', '2:1'),
                ('庄家Blackjack：Original Bet', '输'),
                ('庄家Blackjack：额外分牌/加倍本金', 'OBO退回'),
                ('同点数 / 双方普通同分', 'Push退回'),
            ])
        main_table.pack(fill=tk.X, padx=18, pady=(0, 16))

        # ================================================================
        # 05 边注赔付
        # ================================================================
        side_card = make_card('05  边注赔付表', '六个边注 · 按利润赔率结算')
        side_grid = tk.Frame(side_card, bg=PANEL)
        side_grid.pack(fill=tk.X, padx=18, pady=(0, 16))
        side_grid.grid_columnconfigure(0, weight=1, uniform='payout')
        side_grid.grid_columnconfigure(1, weight=1, uniform='payout')

        tables = [
            ('完美对子', [
                ('同花色同点对子', '21:1'),
                ('同颜色同点对子', '10:1'),
                ('杂色同点对子', '5:1'),
            ]),
            ('21+3', [
                ('三张同花同点', '90:1'),
                ('同花顺', '35:1'),
                ('三条', '25:1'),
                ('顺子', '10:1'),
                ('同花', '4:1'),
            ]),
            ('明牌运气', [
                ('庄2–7 + 玩家黑桃J/黑桃A', '70:1'),
                ('庄2–7 + 玩家Blackjack', '7:1'),
                ('庄2–7 + 玩家9–11点', '3:1'),
                ('庄2–7 + 玩家18–20点', '3:1'),
            ]),
            ('疯狂7', [
                ('目标三张同花7', '1500:1'),
                ('目标三张7', '325:1'),
                ('前两目标同花7', '100:1'),
                ('前两目标7', '18:1'),
                ('第一目标7（第0张）', '4:1'),
            ]),
            ('热辣21', [
                ('三张7同花', '400:1'),
                ('三张7', '80:1'),
                ('三张牌同花且等于21', '20:1'),
                ('三张牌等于21', '4:1'),
                ('三张牌等于20', '2:1'),
                ('三张牌等于19', '1:1'),
            ]),
            ('爆牌!', [
                ('庄家8张或以上爆牌', '200:1'),
                ('庄家7张爆牌', '80:1'),
                ('庄家6张爆牌', '40:1'),
                ('庄家5张爆牌', '7.5:1'),
                ('庄家4张爆牌', '1.5:1'),
                ('庄家3张爆牌', '1:1'),
            ]),
        ]
        for idx, (title, rows) in enumerate(tables):
            block = table_block(side_grid, title, rows)
            row_index = idx // 2
            column_index = idx % 2
            block.grid(
                row=row_index, column=column_index, sticky='nsew',
                padx=(0, 7) if column_index == 0 else (7, 0), pady=7)

        # ================================================================
        # 06 重要提示
        # ================================================================
        notes_card = make_card('06  重要提示', pady=(8, 18))
        add_rule(
            notes_card, '21+3顺子',
            '顺子识别逻辑保持经典牌序不变：A可作低牌或高牌；A-2-3、J-Q-K、Q-K-A'
            '均可判断为顺子。移除9与10不会让牌序自动跨越，因此7-8-J和8-J-Q都不算顺子。')
        add_rule(
            notes_card, '疯狂7取牌位置',
            '疯狂7按本局实际发牌序列的指定目标牌逐步锁定赔率：第一目标为7先保证4:1；'
            '后续目标7可升级到18/100，再升级到325/1500。废弃的9与10不计入发牌序列。')
        add_rule(
            notes_card, '分牌行动顺序',
            '分牌后先给当前第一手补一张并完成该手全部行动；只有第一手结束后，'
            '才激活下一手并补该手的第一张分牌牌。')
        add_rule(
            notes_card, '即时兑现模型',
            '兑现金额为模型估值，不会偷看或消耗真实牌靴中的下一张牌；实际牌局牌序保持不变。')

        def _close_instruction():
            try:
                self._instruction_window = None
            except Exception:
                pass
            try:
                dialog.destroy()
            except tk.TclError:
                pass

        close_btn.configure(command=_close_instruction)
        dialog.protocol('WM_DELETE_WINDOW', _close_instruction)
        dialog.bind('<Escape>', lambda _e: _close_instruction())
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
            self.current_side_bets = {key: 0.0 for key in self.SIDE_BET_KEYS}
        else:
            unresolved = 0.0
            for hand in self.hands:
                if hand.get('status') not in ('surrendered', 'even_money'):
                    unresolved += self.hand_stake(hand)
            unresolved += self.insurance_bet
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
    root.title('倍注黑杰克')
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
