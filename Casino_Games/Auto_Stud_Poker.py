import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
from collections import Counter
from itertools import combinations
import math
import time
import secrets
import subprocess
import sys

# =========================================================
# Caribbean Stud Poker 风格 UI
# 原始 Auto Stud Poker 的游戏流程与赔付逻辑保持不变
# =========================================================
ROOT_BG = "#1B3D31"
TABLE_PANEL_BG = "#2A4A3C"
TEXT = "#FFFFFF"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
ACCENT_GOLD = "#A88100"
CARD_SIZE = (76, 106)
HAND_CARD_SPACING = 82
TOTAL_BET_LIMIT = 500000.0

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '皇家同花顺', 8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花',
    4: '顺子', 3: '三条', 2: '两对', 1: '对子', 0: '高牌'
}

# 原始支付表（利润倍数）
BET_PAYOUT = {
    "cowboy_win": 0.95,
    "bull_win": 0.95,
    "combined_straight_or_flush": 1.5,
    "combined_full_house": 5,
    "combined_quads_or_straight_flush": 30,
    "high_card": 2.8,
    "pair": 0.6,
    "two_pair": 9.5,
    "three_of_a_kind": 20,
    "straight": 120,
    "flush": 240,
    "full_house": 320,
    "four_kind_or_straight_flush": 1700,
}

# 独立下注上限：玩家1/玩家2获胜各50,000，其余下注各25,000。
BET_LIMITS = {
    bet_type: (50000.0 if bet_type in ('cowboy_win', 'bull_win') else 25000.0)
    for bet_type in BET_PAYOUT
}


def measure_text(draw, text, font):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        return draw.textsize(text, font=font)


def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')


def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)


def load_user_data():
    path = get_data_file_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user.get('user_name') == username:
            user['cash'] = f"{float(new_balance):.2f}"
            save_user_data(users)
            return


def format_money(amount):
    if amount >= 0:
        return "${:,.2f}".format(amount)
    return "-${:,.2f}".format(abs(amount))


class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]

    def __repr__(self):
        return f"{self.rank}{self.suit}"


class Deck:
    def __init__(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        try:
            result = subprocess.run(
                [sys.executable, shuffle_script, "false", "1"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30,
            )
            shuffle_data = json.loads(result.stdout)
            if "deck" not in shuffle_data or "cut_position" not in shuffle_data:
                raise ValueError("Invalid shuffle data format")
            self.full_deck = [Card(d["suit"], d["rank"]) for d in shuffle_data["deck"]]
            self.cut_position = shuffle_data["cut_position"]
        except Exception as exc:
            print(f"Error calling shuffle.py: {exc}. Using fallback shuffle.")
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)

        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]

    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt


def evaluate_hand(cards):
    """评估五张牌，保留原始程式逻辑。"""
    values = sorted((c.value for c in cards), reverse=True)
    counts = Counter(values)
    suits = [c.suit for c in cards]

    unique_vals = sorted(set(values), reverse=True)
    if 14 in unique_vals:
        unique_vals.append(1)

    straight_vals = []
    seq = []
    for value in unique_vals:
        if not seq or seq[-1] - 1 == value:
            seq.append(value)
        else:
            seq = [value]
        if len(seq) >= 5:
            straight_vals = seq[:5]
            break

    flush_suit = next((s for s in SUITS if suits.count(s) >= 5), None)
    flush_cards = [c for c in cards if c.suit == flush_suit] if flush_suit else []

    if flush_cards and straight_vals:
        flush_vals = sorted({c.value for c in flush_cards}, reverse=True)
        if 14 in flush_vals:
            flush_vals.append(1)
        seq2 = []
        for value in flush_vals:
            if not seq2 or seq2[-1] - 1 == value:
                seq2.append(value)
            else:
                seq2 = [value]
            if len(seq2) >= 5:
                return (9, seq2[:5]) if seq2[0] == 14 else (8, seq2[:5])

    counts_list = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if counts_list[0][1] == 4:
        quad = counts_list[0][0]
        kicker = max(v for v in values if v != quad)
        return (7, [quad, kicker])
    if counts_list[0][1] == 3 and counts_list[1][1] >= 2:
        return (6, [counts_list[0][0], counts_list[1][0]])
    if flush_suit:
        return (5, sorted((c.value for c in flush_cards), reverse=True)[:5])
    if straight_vals:
        return (4, straight_vals)
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, [three] + kickers)

    pairs = [v for v, count in counts_list if count == 2]
    if len(pairs) >= 2:
        high, low = pairs[0], pairs[1]
        kicker = max(v for v in values if v not in (high, low))
        return (2, [high, low, kicker])
    if counts_list[0][1] == 2:
        pair = counts_list[0][0]
        kickers = [v for v in values if v != pair][:3]
        return (1, [pair] + kickers)
    return (0, values[:5])


def find_best_5(cards):
    best_eval = None
    best_hand = None
    for combo in combinations(cards, 5):
        current_eval = evaluate_hand(combo)
        if best_eval is None or current_eval > best_eval:
            best_eval = current_eval
            best_hand = combo
    return best_eval, best_hand


class AutoStudPokerGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.cowboy_hole = []
        self.bull_hole = []
        self.bets = {bet_type: 0 for bet_type in BET_PAYOUT}
        self.stage = "dealing"
        self.cards_revealed = {
            "cowboy": [True, False, False, False, False],
            "bull": [True, False, False, False, False],
        }
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence
        self.dynamic_payouts = BET_PAYOUT.copy()

    def deal_initial(self):
        self.cowboy_hole = self.deck.deal(5)
        self.bull_hole = self.deck.deal(5)

    def evaluate_hands(self):
        cowboy_eval, cowboy_best = find_best_5(self.cowboy_hole)
        bull_eval, bull_best = find_best_5(self.bull_hole)
        return cowboy_eval, cowboy_best, bull_eval, bull_best

    def get_winner_hand_type(self, cowboy_eval, bull_eval):
        if cowboy_eval > bull_eval:
            winner_eval = cowboy_eval
        elif bull_eval > cowboy_eval:
            winner_eval = bull_eval
        else:
            return None, None

        hand_rank = winner_eval[0]
        if hand_rank in (9, 8, 7):
            return "four_kind_or_straight_flush", winner_eval
        if hand_rank == 6:
            return "full_house", winner_eval
        if hand_rank == 5:
            return "flush", winner_eval
        if hand_rank == 4:
            return "straight", winner_eval
        if hand_rank == 3:
            return "three_of_a_kind", winner_eval
        if hand_rank == 2:
            return "two_pair", winner_eval
        if hand_rank == 1:
            return "pair", winner_eval
        if hand_rank == 0:
            return "high_card", winner_eval
        return None, None

    def check_combined_hands(self):
        all_cards = self.cowboy_hole + self.bull_hole
        found_quads_or_straight_flush = False
        found_full_house = False
        found_straight_or_flush = False

        for combo in combinations(all_cards, 5):
            rank = evaluate_hand(combo)[0]
            if rank in (7, 8, 9):
                found_quads_or_straight_flush = True
            elif rank == 6:
                found_full_house = True
            elif rank in (4, 5, 8, 9):
                found_straight_or_flush = True

        return {
            "combined_quads_or_straight_flush": found_quads_or_straight_flush,
            "combined_full_house": found_full_house,
            "combined_straight_or_flush": found_straight_or_flush,
        }

    def calculate_dynamic_payouts(self, cowboy_up_value, bull_up_value):
        diff = abs(cowboy_up_value - bull_up_value)
        max_diff = 12

        if cowboy_up_value > bull_up_value:
            cowboy_odds = 0.95 - (diff / max_diff) * 0.5
            bull_odds = 0.95 + (diff / max_diff) * 0.5
        elif bull_up_value > cowboy_up_value:
            cowboy_odds = 0.95 + (diff / max_diff) * 0.5
            bull_odds = 0.95 - (diff / max_diff) * 0.5
        else:
            cowboy_odds = 0.95
            bull_odds = 0.95

        self.dynamic_payouts["cowboy_win"] = round(max(0.45, min(1.45, cowboy_odds)), 2)
        self.dynamic_payouts["bull_win"] = round(max(0.45, min(1.45, bull_odds)), 2)


class AutoStudPokerGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.parent = parent
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.username = username
        self.balance = float(initial_balance)
        self.game = AutoStudPokerGame()

        self.card_images = {}
        self.original_images = {}
        self.back_image = None
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []
        self._temp_flip_images = {}

        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.bet_widgets = {}
        self.last_bet = None
        self.last_win = 0.0
        self.win_details = {bet_type: 0 for bet_type in BET_PAYOUT}

        self.auto_reset_timer = None
        self.auto_start_timer = None
        self.bet_start_time = 0.0
        self.enter_enabled = False
        self.destroyed = False
        self.freeze_current_bet_display = False
        self._return_bind_id = None

        self._load_assets()
        self._create_widgets()

        root = self.winfo_toplevel()
        self._return_bind_id = root.bind("<Return>", self.on_enter_key, add="+")
        self.bind("<Destroy>", self._handle_widget_destroy, add="+")

    # -----------------------------------------------------
    # Parent 生命周期
    # -----------------------------------------------------
    def _cancel_timers(self):
        for attr in ("auto_reset_timer", "auto_start_timer"):
            timer = getattr(self, attr, None)
            if timer:
                try:
                    self.after_cancel(timer)
                except tk.TclError:
                    pass
                setattr(self, attr, None)

    def _unbind_return_key(self):
        if self._return_bind_id:
            try:
                self.winfo_toplevel().unbind("<Return>", self._return_bind_id)
            except tk.TclError:
                pass
            self._return_bind_id = None

    def _handle_widget_destroy(self, event):
        if event.widget is not self:
            return
        self.destroyed = True
        self._cancel_timers()
        self._unbind_return_key()

    def on_close(self):
        if self.destroyed:
            return
        self.destroyed = True
        self._cancel_timers()
        self._unbind_return_key()

        try:
            update_balance_in_json(self.username, self.balance)
        except Exception:
            pass

        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            try:
                self.destroy()
            except tk.TclError:
                pass

    # -----------------------------------------------------
    # 资源
    # -----------------------------------------------------
    def _load_assets(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not hasattr(self, 'current_poker_folder'):
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'

        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club'}
        self.card_images = {}
        self.original_images = {}

        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_orig = Image.open(back_path)
        except Exception as exc:
            print(f"Error loading back image: {exc}")
            back_orig = Image.new('RGB', CARD_SIZE, 'black')
        self.original_images['back'] = back_orig
        self.back_image = ImageTk.PhotoImage(back_orig.resize(CARD_SIZE, Image.LANCZOS))

        for suit in SUITS:
            for rank in RANKS:
                path = os.path.join(card_dir, f"{suit_mapping[suit]}{rank}.png")
                try:
                    if os.path.exists(path):
                        img_orig = Image.open(path)
                    else:
                        img_orig = self._make_placeholder_card(suit, rank, 'blue')
                except Exception as exc:
                    print(f"Error loading card image {path}: {exc}")
                    img_orig = self._make_placeholder_card(suit, rank, 'red')
                self.original_images[(suit, rank)] = img_orig
                self.card_images[(suit, rank)] = ImageTk.PhotoImage(
                    img_orig.resize(CARD_SIZE, Image.LANCZOS)
                )

    def _make_placeholder_card(self, suit, rank, colour):
        image = Image.new('RGB', CARD_SIZE, colour)
        draw = ImageDraw.Draw(image)
        text = f"{rank}{suit}"
        try:
            font = ImageFont.truetype("arial.ttf", 18)
        except Exception:
            font = ImageFont.load_default()
        text_width, text_height = measure_text(draw, text, font)
        draw.text(
            ((CARD_SIZE[0] - text_width) / 2, (CARD_SIZE[1] - text_height) / 2),
            text,
            fill='white',
            font=font,
        )
        return image

    # -----------------------------------------------------
    # UI
    # -----------------------------------------------------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, width=500, height=730, highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.Y)
        table_canvas.pack_propagate(False)
        table_canvas.create_rectangle(3, 3, 496, 726, fill=ROOT_BG, outline=GOLD, width=5)

        player1_frame = tk.Frame(table_canvas, bg=TABLE_PANEL_BG, bd=2, relief=tk.RAISED)
        player1_frame.place(x=25, y=45, width=450, height=185)
        self.cowboy_label = tk.Label(
            player1_frame, text="玩家1", font=('Arial', 15, 'bold'), bg=TABLE_PANEL_BG, fg=TEXT
        )
        self.cowboy_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.cowboy_cards_frame = tk.Frame(player1_frame, bg=TABLE_PANEL_BG)
        self.cowboy_cards_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        tk.Label(
            table_canvas, text="AUTO STUD POKER", font=('Arial', 23, 'bold'), bg=ROOT_BG, fg=GOLD
        ).place(x=250, y=275, anchor='center')
        tk.Label(
            table_canvas, text="双方各五张牌 · 第一张为明牌", font=('Arial', 14, 'bold'),
            bg=ROOT_BG, fg=TEXT
        ).place(x=250, y=315, anchor='center')
        self.table_status_label = tk.Label(
            table_canvas, text="准备发牌", font=('Arial', 15, 'bold'), bg=ROOT_BG, fg='#FFD700'
        )
        self.table_status_label.place(x=250, y=355, anchor='center')

        player2_frame = tk.Frame(table_canvas, bg=TABLE_PANEL_BG, bd=2, relief=tk.RAISED)
        player2_frame.place(x=25, y=410, width=450, height=185)
        self.bull_label = tk.Label(
            player2_frame, text="玩家2", font=('Arial', 15, 'bold'), bg=TABLE_PANEL_BG, fg=TEXT
        )
        self.bull_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.bull_cards_frame = tk.Frame(player2_frame, bg=TABLE_PANEL_BG)
        self.bull_cards_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=620)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        right_panel.pack_propagate(False)

        info_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=(0, 3))
        info_header = tk.Frame(info_card, bg=HEADER_BG)
        info_header.pack(fill=tk.X)
        info_header.columnconfigure(0, weight=1)
        tk.Label(
            info_header, text="游戏信息", font=('Arial', 12, 'bold'), bg=HEADER_BG, fg=TITLE_FG
        ).grid(row=0, column=0, sticky='ew', padx=(72, 0), pady=3)
        self.back_button = tk.Button(
            info_header, text="", command=self.on_close, font=('Arial', 9, 'bold'),
            bg=HEADER_BG, fg='white',
            relief=tk.FLAT, width=7
        )
        self.back_button.grid(row=0, column=1, padx=5, pady=2)

        info_body = tk.Frame(info_card, bg=PANEL_BG)
        info_body.pack(fill=tk.X, padx=10, pady=6)
        for col in range(3):
            info_body.columnconfigure(col, weight=1, uniform='info')
        self.balance_label = tk.Label(
            info_body, text=f"余额: {format_money(self.balance)}", font=('Arial', 13, 'bold'),
            bg=PANEL_BG, fg='black', anchor='w'
        )
        self.balance_label.grid(row=0, column=0, sticky='w')
        self.timer_label = tk.Label(
            info_body, text="下注时间: --", font=('Arial', 15, 'bold'), bg=PANEL_BG,
            fg='#D32F2F', anchor='center'
        )
        self.timer_label.grid(row=0, column=1, sticky='ew')
        self.stage_label = tk.Label(
            info_body, text="准备发牌", font=('Arial', 13, 'bold'), bg=PANEL_BG,
            fg=ACCENT_GOLD, anchor='e'
        )
        self.stage_label.grid(row=0, column=2, sticky='e')

        chip_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        chip_card.pack(fill=tk.X, pady=3)
        chip_header = tk.Frame(chip_card, bg=HEADER_BG)
        chip_header.pack(fill=tk.X)
        tk.Label(chip_header, text="筹码区", font=('Arial', 12, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=3)
        chip_body = tk.Frame(chip_card, bg=PANEL_BG)
        chip_body.pack(fill=tk.X, padx=8, pady=5)
        for col in range(8):
            chip_body.columnconfigure(col, weight=1)

        chip_configs = [
            ('$10', '#ffa500', 'black'),
            ('$25', '#00ff00', 'black'),
            ('$100', '#000000', 'white'),
            ('$500', '#FF7DDA', 'black'),
            ('$1K', '#ffffff', 'black'),
            ('$5K', '#ff0000', 'white'),
            ('$10K', '#00fbff', 'black'),
            ('$50K', '#00ffae', 'black'),
        ]
        for col, (chip_text, bg_colour, fg_colour) in enumerate(chip_configs):
            cell = tk.Frame(chip_body, bg=PANEL_BG)
            cell.grid(row=0, column=col, padx=1, pady=1, sticky='nsew')
            chip = tk.Canvas(cell, width=48, height=48, bg=PANEL_BG, highlightthickness=0)
            chip.pack(anchor='center')
            chip.create_oval(2, 2, 46, 46, fill=bg_colour, outline='black')
            chip.create_text(24, 24, text=chip_text, fill=fg_colour, font=('Arial', 10, 'bold'))
            chip.bind('<Button-1>', lambda event, text=chip_text: self.select_chip(text))
            self.chip_buttons.append(chip)
            self.chip_texts[chip] = chip_text
        self.select_chip('$100')

        limit_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        limit_header = tk.Frame(limit_card, bg=HEADER_BG)
        limit_header.pack(fill=tk.X)
        tk.Label(limit_header, text="下注上限", font=('Arial', 12, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=3)
        limit_body = tk.Frame(limit_card, bg=PANEL_BG)
        limit_body.pack(fill=tk.X, padx=10, pady=5)
        limit_table = tk.Frame(limit_body, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_table.pack(fill=tk.X)
        limit_items = [
            ('玩家1 / 玩家2赢', '$50,000'),
            ('其他下注', '$25,000'),
            ('本局总额', '$500,000'),
        ]
        for col, (title, amount) in enumerate(limit_items):
            limit_table.columnconfigure(col, weight=1, uniform='limit')
            tk.Label(
                limit_table, text=title, font=('Arial', 10, 'bold'), bg=PANEL_BG, fg=TITLE_FG,
                borderwidth=1, relief=tk.SOLID, pady=2
            ).grid(row=0, column=col, sticky='nsew')
            tk.Label(
                limit_table, text=amount, font=('Arial', 11, 'bold'), bg=PANEL_BG, fg=ACCENT_GOLD,
                borderwidth=1, relief=tk.SOLID, pady=2
            ).grid(row=1, column=col, sticky='nsew')

        bet_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        bet_card.pack(fill=tk.BOTH, expand=True, pady=(3, 0))
        bet_header = tk.Frame(bet_card, bg=HEADER_BG)
        bet_header.pack(fill=tk.X)
        tk.Label(bet_header, text="下注区", font=('Arial', 12, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=3)
        bet_body = tk.Frame(bet_card, bg=TABLE_PANEL_BG, bd=2, relief=tk.RAISED)
        bet_body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        def create_bet_box(parent, title, bet_type, *, pack_opts=None, grid_opts=None,
                           title_font=11, display_font=11, display_height=1, title_anchor='w'):
            box = tk.Frame(parent, bg='#315546', bd=1, relief=tk.SOLID)
            if pack_opts is not None:
                box.pack(**pack_opts)
            else:
                box.grid(**grid_opts)
            header = tk.Label(
                box, text=title, font=('Arial', title_font, 'bold'), bg='#345949', fg=TEXT,
                anchor=title_anchor, padx=6, pady=2
            )
            header.pack(fill=tk.X)
            var = tk.StringVar(value='0')
            setattr(self, f'{bet_type}_var', var)
            display = tk.Label(
                box, textvariable=var, font=('Arial', display_font, 'bold'), bg='white', fg='black',
                height=display_height, relief=tk.SUNKEN, bd=1
            )
            display.pack(fill=tk.BOTH, expand=True, padx=4, pady=3)
            display.bind('<Button-1>', lambda event, bt=bet_type: self.add_chip_to_bet(bt))
            display.bind('<Button-3>', lambda event, bt=bet_type: self.reset_bet_area(event, bt))
            self.bet_widgets[bet_type] = display
            return box, header

        top_row = tk.Frame(bet_body, bg=TABLE_PANEL_BG)
        top_row.pack(fill=tk.X, padx=8, pady=(5, 4))
        top_row = tk.Frame(bet_body, bg=TABLE_PANEL_BG)
        top_row.pack(fill=tk.X, padx=8, pady=(7, 5))
        self.cowboy_win_frame, self.cowboy_win_title = create_bet_box(
            top_row, '玩家1赢 (?:1)', 'cowboy_win',
            pack_opts={'side': tk.LEFT, 'fill': tk.BOTH, 'expand': True, 'padx': 4},
            title_font=15, display_font=16, display_height=2
        )
        self.bull_win_frame, self.bull_win_title = create_bet_box(
            top_row, '玩家2赢 (?:1)', 'bull_win',
            pack_opts={'side': tk.LEFT, 'fill': tk.BOTH, 'expand': True, 'padx': 4},
            title_font=15, display_font=16, display_height=2
        )

        middle = tk.Frame(bet_body, bg=TABLE_PANEL_BG)
        middle.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 5))

        combined_group = tk.Frame(middle, bg=TABLE_PANEL_BG)
        combined_group.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        tk.Label(
            combined_group, text='双方合并牌型', font=('Arial', 13, 'bold'),
            bg=TABLE_PANEL_BG, fg=TEXT
        ).pack(anchor='w', pady=(0, 3))
        create_bet_box(
            combined_group, '顺子 / 同花 (1.5:1)', 'combined_straight_or_flush',
            pack_opts={'fill': tk.X, 'pady': 3}, title_font=11
        )
        create_bet_box(
            combined_group, '葫芦 (5:1)', 'combined_full_house',
            pack_opts={'fill': tk.X, 'pady': 3}, title_font=11
        )
        create_bet_box(
            combined_group, '四条 / 同花顺 (30:1)', 'combined_quads_or_straight_flush',
            pack_opts={'fill': tk.X, 'pady': 3}, title_font=11
        )

        winner_group = tk.Frame(middle, bg=TABLE_PANEL_BG)
        winner_group.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        tk.Label(
            winner_group, text='赢家牌型', font=('Arial', 14, 'bold'),
            bg=TABLE_PANEL_BG, fg=TEXT
        ).pack(anchor='w', pady=(0, 3))
        winner_grid = tk.Frame(winner_group, bg=TABLE_PANEL_BG)
        winner_grid.pack(fill=tk.BOTH, expand=True)
        for col in range(3):
            winner_grid.columnconfigure(col, weight=1, uniform='winner')
        for row in range(3):
            winner_grid.rowconfigure(row, weight=1)

        winner_items = [
            ('高牌 (2.8:1)', 'high_card', 0, 0, 1),
            ('对子 (0.6:1)', 'pair', 0, 1, 1),
            ('两对 (9.5:1)', 'two_pair', 0, 2, 1),
            ('三条 (20:1)', 'three_of_a_kind', 1, 0, 1),
            ('顺子 (120:1)', 'straight', 1, 1, 1),
            ('同花 (240:1)', 'flush', 1, 2, 1),
            ('葫芦 (320:1)', 'full_house', 2, 0, 1),
            ('四条 / 同花顺 (1700:1)', 'four_kind_or_straight_flush', 2, 1, 2),
        ]
        for title, bet_type, row, col, columnspan in winner_items:
            create_bet_box(
                winner_grid, title, bet_type,
                grid_opts={
                    'row': row, 'column': col, 'columnspan': columnspan,
                    'sticky': 'nsew', 'padx': 2, 'pady': 2,
                },
                title_font=9, display_font=10
            )

        footer = tk.Frame(bet_body, bg=TABLE_PANEL_BG)
        footer.pack(fill=tk.X, padx=10, pady=(2, 7))

        row1 = tk.Frame(footer, bg=TABLE_PANEL_BG)
        row1.pack(fill=tk.X, pady=(0, 4))
        self.current_bet_label = tk.Label(
            row1, text='本局下注: $0.00', font=('Arial', 11, 'bold'), bg=TABLE_PANEL_BG, fg=TEXT
        )
        self.current_bet_label.pack(side=tk.LEFT)
        row1_buttons = tk.Frame(row1, bg=TABLE_PANEL_BG)
        row1_buttons.pack(side=tk.RIGHT)
        self.info_button = tk.Button(
            row1_buttons, text='游戏规则', command=self.show_game_instructions,
            bg='#4B8BBE', fg='white', font=('Arial', 10, 'bold'), width=8
        )
        self.info_button.pack(side=tk.LEFT, padx=3)
        self.repeat_bet_btn = tk.Button(
            row1_buttons, text='重复下注', command=self.apply_last_bet,
            bg='#FFC107', fg='black', font=('Arial', 10, 'bold'), width=8, state=tk.DISABLED
        )
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=3)

        row2 = tk.Frame(footer, bg=TABLE_PANEL_BG)
        row2.pack(fill=tk.X)
        self.last_win_label = tk.Label(
            row2, text='上局获胜: $0.00', font=('Arial', 11, 'bold'),
            bg=TABLE_PANEL_BG, fg='#FFD700'
        )
        self.last_win_label.pack(side=tk.LEFT)
        row2_buttons = tk.Frame(row2, bg=TABLE_PANEL_BG)
        row2_buttons.pack(side=tk.RIGHT)
        self.reset_button = tk.Button(
            row2_buttons, text='重设金额', command=self.reset_bets,
            bg='#F44336', fg='white', font=('Arial', 10, 'bold'), width=8
        )
        self.reset_button.pack(side=tk.LEFT, padx=3)
        self.start_button = tk.Button(
            row2_buttons, text='开始游戏', command=lambda: self.on_enter_key(None),
            bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'), width=8
        )
        self.start_button.pack(side=tk.LEFT, padx=3)

        self.bet_vars = [getattr(self, f'{bet_type}_var') for bet_type in BET_PAYOUT]
        for var in self.bet_vars:
            var.trace_add('write', lambda *_args: self.refresh_bet_info())
        self.refresh_bet_info()

    # -----------------------------------------------------
    # 下注
    # -----------------------------------------------------
    def _parse_chip_value(self, chip_text):
        raw = chip_text.replace('$', '').upper()
        return float(raw[:-1]) * 1000 if raw.endswith('K') else float(raw)

    def _format_bet_value(self, value):
        value = float(value)
        if value.is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip('0').rstrip('.')

    def get_bet_amounts(self):
        amounts = {}
        for bet_type in BET_PAYOUT:
            try:
                amounts[bet_type] = float(getattr(self, f'{bet_type}_var').get())
            except (ValueError, tk.TclError):
                amounts[bet_type] = 0.0
        return amounts

    def get_total_bet(self):
        return sum(self.get_bet_amounts().values())

    def refresh_bet_info(self):
        if not self.freeze_current_bet_display and hasattr(self, 'current_bet_label'):
            self.current_bet_label.config(text=f"本局下注: {format_money(self.get_total_bet())}")
        self._update_repeat_button_state()

    def set_bet_amounts(self, amounts):
        for bet_type in BET_PAYOUT:
            getattr(self, f'{bet_type}_var').set(self._format_bet_value(amounts.get(bet_type, 0)))
        self.refresh_bet_info()

    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete('highlight')
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            for item_id in chip.find_all():
                if chip.type(item_id) == 'text':
                    text_id = item_id
                elif chip.type(item_id) == 'oval':
                    oval_id = item_id
            if text_id and oval_id and chip.itemcget(text_id, 'text') == chip_text:
                x1, y1, x2, y2 = chip.coords(oval_id)
                chip.create_oval(x1, y1, x2, y2, outline='gold', width=3, tags='highlight')
                break

    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip or self.game.stage != 'betting':
            return
        try:
            chip_value = self._parse_chip_value(self.selected_chip)
        except ValueError:
            return

        var = getattr(self, f'{bet_type}_var')
        current = float(var.get())
        current_total = self.get_total_bet()
        item_limit = BET_LIMITS[bet_type]
        remaining_item = max(0.0, item_limit - current)
        maximum_total = min(TOTAL_BET_LIMIT, self.balance)
        remaining_total = max(0.0, maximum_total - current_total)
        accepted = min(chip_value, remaining_item, remaining_total)

        if accepted <= 0:
            if current >= item_limit:
                messagebox.showwarning(
                    '下注上限',
                    f"该下注项目上限为 {format_money(item_limit)}。",
                    parent=self,
                )
            elif current_total >= self.balance:
                messagebox.showwarning('余额不足', '当前下注已达到可用余额。', parent=self)
            else:
                messagebox.showwarning('下注上限', '本局下注总额上限为 $500,000。', parent=self)
            return

        var.set(self._format_bet_value(current + accepted))
        self.refresh_bet_info()
        if accepted < chip_value:
            if current + accepted >= item_limit:
                reason = f"该下注项目已达到上限 {format_money(item_limit)}"
            else:
                reason = f"本局总下注已达到当前最大可下注金额 {format_money(self.get_total_bet())}"
            messagebox.showwarning('下注调整', f"已自动调整：{reason}。", parent=self)

    def reset_bet_area(self, _event, bet_type):
        getattr(self, f'{bet_type}_var').set('0')
        self.bet_widgets[bet_type].config(bg='white')
        self.refresh_bet_info()

    def reset_bets(self):
        self.set_bet_amounts({bet_type: 0 for bet_type in BET_PAYOUT})
        for widget in self.bet_widgets.values():
            widget.config(bg='white')

    def apply_last_bet(self):
        if self.game.stage != 'betting' or not self.last_bet:
            return
        remaining = min(self.balance, TOTAL_BET_LIMIT)
        applied = {}
        for bet_type in BET_PAYOUT:
            saved = max(0.0, float(self.last_bet.get(bet_type, 0)))
            amount = min(saved, BET_LIMITS[bet_type], remaining)
            applied[bet_type] = amount
            remaining -= amount
        self.set_bet_amounts(applied)

    def _update_repeat_button_state(self):
        if hasattr(self, 'repeat_bet_btn'):
            enabled = self.game.stage == 'betting' and self.last_bet is not None
            self.repeat_bet_btn.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def _set_betting_controls_enabled(self, enabled):
        for bet_type, widget in self.bet_widgets.items():
            widget.unbind('<Button-1>')
            widget.unbind('<Button-3>')
            if enabled:
                widget.bind('<Button-1>', lambda event, bt=bet_type: self.add_chip_to_bet(bt))
                widget.bind('<Button-3>', lambda event, bt=bet_type: self.reset_bet_area(event, bt))

        for chip in self.chip_buttons:
            chip.unbind('<Button-1>')
            if enabled:
                chip_text = self.chip_texts[chip]
                chip.bind('<Button-1>', lambda event, text=chip_text: self.select_chip(text))

        state = tk.NORMAL if enabled else tk.DISABLED
        self.reset_button.config(state=state)
        self.start_button.config(state=state)
        self._update_repeat_button_state()

    # -----------------------------------------------------
    # 游戏流程
    # -----------------------------------------------------
    def update_balance(self):
        self.balance_label.config(text=f"余额: {format_money(self.balance)}")
        if self.username != 'Guest':
            try:
                update_balance_in_json(self.username, self.balance)
            except Exception:
                pass
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def reset_game(self):
        if self.destroyed:
            return

        self._cancel_timers()
        self._load_assets()
        self.game.reset_game()
        self.game.deal_initial()
        self.game.calculate_dynamic_payouts(
            self.game.cowboy_hole[0].value,
            self.game.bull_hole[0].value,
        )

        self.freeze_current_bet_display = False
        self.reset_bets()
        self.active_card_labels = []
        self.animation_queue = []
        self.card_positions = {}
        self._temp_flip_images = {}
        self.enter_enabled = False

        for frame in (self.cowboy_cards_frame, self.bull_cards_frame):
            for child in frame.winfo_children():
                child.destroy()

        self.cowboy_label.config(text='玩家1')
        self.bull_label.config(text='玩家2')
        # 明牌翻开完成前不公开动态赔率。
        self.cowboy_win_title.config(text='玩家1赢 (?:1)')
        self.bull_win_title.config(text='玩家2赢 (?:1)')
        self.stage_label.config(text='发牌中')
        self.timer_label.config(text='下注时间: --')
        self.table_status_label.config(text='先发双方五张暗牌')
        self._set_betting_controls_enabled(False)

        for index in range(5):
            card_id = f'cowboy_{index}'
            self.card_positions[card_id] = {
                'current': (35, 30),
                'target': (index * HAND_CARD_SPACING, 0),
            }
            self.animation_queue.append(card_id)
        for index in range(5):
            card_id = f'bull_{index}'
            self.card_positions[card_id] = {
                'current': (35, 30),
                'target': (index * HAND_CARD_SPACING, 0),
            }
            self.animation_queue.append(card_id)

        self.after(120, self.animate_deal)

    def animate_deal(self):
        if self.destroyed:
            return
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(250, self.reveal_up_cards)
            return

        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        side, index_text = card_id.split('_')
        index = int(index_text)
        if side == 'cowboy':
            frame = self.cowboy_cards_frame
            card = self.game.cowboy_hole[index]
        else:
            frame = self.bull_cards_frame
            card = self.game.bull_hole[index]

        label = tk.Label(frame, image=self.back_image, bg=TABLE_PANEL_BG)
        current_x, current_y = self.card_positions[card_id]['current']
        label.place(x=current_x, y=current_y + 15, width=CARD_SIZE[0], height=CARD_SIZE[1])
        label.card_id = card_id
        label.card = card
        label.is_face_up = False
        label.target_pos = self.card_positions[card_id]['target']
        label.bind('<Button-3>', self.show_card_sequence)
        self.active_card_labels.append(label)
        self.animate_card_move(label)

    def animate_card_move(self, label):
        if self.destroyed or not label.winfo_exists():
            return
        current_x, current_y = label.winfo_x(), label.winfo_y()
        target_x, target_y = label.target_pos
        dx, dy = target_x - current_x, target_y - current_y
        if math.hypot(dx, dy) < 5:
            label.place(x=target_x, y=target_y, width=CARD_SIZE[0], height=CARD_SIZE[1])
            self.after(15, self.animate_deal)
            return
        label.place(
            x=current_x + dx * 0.24,
            y=current_y + dy * 0.24,
            width=CARD_SIZE[0],
            height=CARD_SIZE[1],
        )
        self.after(18, lambda: self.animate_card_move(label))

    def _find_card_label(self, card_id):
        for label in self.active_card_labels:
            if getattr(label, 'card_id', None) == card_id:
                try:
                    if label.winfo_exists():
                        return label
                except tk.TclError:
                    return None
        return None

    def reveal_up_cards(self):
        if self.destroyed:
            return
        self.stage_label.config(text='展示明牌')
        self.table_status_label.config(text='翻开双方第一张明牌')
        for card_id in ('cowboy_0', 'bull_0'):
            label = self._find_card_label(card_id)
            if label is not None:
                self.flip_card_animation(label)
        self.after(650, self.begin_betting_phase)

    def begin_betting_phase(self):
        if self.destroyed:
            return
        self.game.stage = 'betting'
        self.cowboy_win_title.config(
            text=f"玩家1赢 ({self.game.dynamic_payouts['cowboy_win']:.2f}:1)"
        )
        self.bull_win_title.config(
            text=f"玩家2赢 ({self.game.dynamic_payouts['bull_win']:.2f}:1)"
        )
        self.stage_label.config(text='下注中')
        self.table_status_label.config(text='明牌已开，赔率已更新，请下注')
        self._set_betting_controls_enabled(True)
        self.bet_start_time = time.time()
        self.enter_enabled = True
        self.timer_label.config(text='下注时间: 15秒')
        self.auto_start_timer = self.after(1000, self.update_timer)

    def on_enter_key(self, _event):
        if not self.enter_enabled or self.game.stage != 'betting':
            return
        self.timer_label.config(text='下注时间: 0秒')
        if self.auto_start_timer:
            try:
                self.after_cancel(self.auto_start_timer)
            except tk.TclError:
                pass
            self.auto_start_timer = None
        self.enter_enabled = False
        self.start_game()

    def start_game(self):
        if self.destroyed or self.game.stage != 'betting':
            return

        bet_amounts = self.get_bet_amounts()
        total_bet = sum(bet_amounts.values())
        for bet_type, amount in bet_amounts.items():
            if amount > BET_LIMITS[bet_type]:
                messagebox.showerror(
                    '下注上限',
                    f"该下注项目不能超过 {format_money(BET_LIMITS[bet_type])}。",
                    parent=self,
                )
                self.enter_enabled = True
                return
        if total_bet > TOTAL_BET_LIMIT:
            messagebox.showerror('下注上限', '本局下注总额不能超过 $500,000。', parent=self)
            self.enter_enabled = True
            return
        if total_bet > self.balance:
            messagebox.showerror('余额不足', '下注金额超过当前余额。', parent=self)
            self.enter_enabled = True
            return

        if total_bet > 0:
            self.last_bet = bet_amounts.copy()

        self.balance -= total_bet
        self.update_balance()
        self.game.bets = bet_amounts
        self.game.stage = 'showdown'
        self.enter_enabled = False
        self.stage_label.config(text='开牌中')
        self.table_status_label.config(text='翻开双方其余手牌')
        self.timer_label.config(text='下注时间: 0秒')
        self._set_betting_controls_enabled(False)
        self.after(250, self.reveal_remaining_cards)

    def reveal_remaining_cards(self):
        """依次翻开玩家1的4张暗牌，再依次翻开玩家2的4张暗牌。"""
        if self.destroyed:
            return
        self._reveal_side_cards('cowboy', 1)

    def _reveal_side_cards(self, side, index):
        if self.destroyed:
            return

        side_name = '玩家1' if side == 'cowboy' else '玩家2'
        self.table_status_label.config(text=f'正在翻开{side_name}手牌')

        if index >= 5:
            if side == 'cowboy':
                self.after(220, lambda: self._reveal_side_cards('bull', 1))
            else:
                self.table_status_label.config(text='双方手牌已全部打开')
                self.after(500, self.update_hand_labels)
                self.after(1200, self.start_sort_animation)
            return

        label = self._find_card_label(f'{side}_{index}')
        if label is not None and not label.is_face_up:
            self.game.cards_revealed[side][index] = True
            self.flip_card_animation(label)

        # 单张翻牌动画约390毫秒；留出间隔后再翻下一张，避免同时执行造成卡顿。
        self.after(440, lambda: self._reveal_side_cards(side, index + 1))

    def flip_card_animation(self, label):
        front = self.card_images.get((label.card.suit, label.card.rank), self.back_image)
        self.animate_flip(label, front, 0)

    def animate_flip(self, label, front_image, step):
        if self.destroyed or not label.winfo_exists():
            return

        steps = 12
        original_width, original_height = CARD_SIZE
        if step > steps:
            label.is_face_up = True
            target_x, target_y = label.target_pos
            label.place(x=target_x, y=target_y, width=original_width, height=original_height)
            label.config(image=front_image)
            self._temp_flip_images.pop(label, None)
            return

        half = steps // 2
        if step <= half:
            ratio = 1 - step / float(half)
            pil_image = self.original_images.get('back')
        else:
            ratio = (step - half) / float(half)
            pil_image = self.original_images.get((label.card.suit, label.card.rank))

        width = max(1, int(original_width * ratio))
        if pil_image is None:
            pil_image = Image.new('RGB', CARD_SIZE, 'gray')
        scaled = pil_image.resize((width, original_height), Image.LANCZOS)
        temporary = ImageTk.PhotoImage(scaled)
        self._temp_flip_images[label] = temporary

        target_x, target_y = label.target_pos
        label.config(image=temporary)
        label.place(
            x=target_x + (original_width - width) // 2,
            y=target_y,
            width=width,
            height=original_height,
        )
        self.after(30, lambda: self.animate_flip(label, front_image, step + 1))

    def update_hand_labels(self):
        if not all(self.game.cards_revealed['cowboy']) or not all(self.game.cards_revealed['bull']):
            return
        cowboy_eval, _, bull_eval, _ = self.game.evaluate_hands()
        self.cowboy_label.config(text=f"玩家1 - {HAND_RANK_NAMES[cowboy_eval[0]]}")
        self.bull_label.config(text=f"玩家2 - {HAND_RANK_NAMES[bull_eval[0]]}")

    def sort_hand_for_display(self, hand, hand_eval):
        if not hand or not hand_eval:
            return list(hand)
        rank = hand_eval[0]
        if rank in (4, 8, 9):
            straight_values = list(hand_eval[1])
            display_values = [14, 2, 3, 4, 5] if 1 in straight_values else sorted(set(straight_values))
            remaining = list(hand)
            ordered = []
            for value in display_values:
                for card in remaining:
                    if card.value == value:
                        ordered.append(card)
                        remaining.remove(card)
                        break
            return ordered + remaining
        counts = Counter(card.value for card in hand)
        return sorted(hand, key=lambda card: (counts[card.value], card.value), reverse=True)

    def start_sort_animation(self):
        if self.destroyed:
            return
        cowboy_eval, _, bull_eval, _ = self.game.evaluate_hands()
        sorted_cowboy = self.sort_hand_for_display(self.game.cowboy_hole, cowboy_eval)
        sorted_bull = self.sort_hand_for_display(self.game.bull_hole, bull_eval)

        labels = []
        targets = {}
        for side, sorted_cards in (('cowboy', sorted_cowboy), ('bull', sorted_bull)):
            for target_index, card in enumerate(sorted_cards):
                for index in range(5):
                    label = self._find_card_label(f'{side}_{index}')
                    if label is not None and label.card is card:
                        labels.append(label)
                        targets[label] = target_index * HAND_CARD_SPACING
                        break

        starts = {label: float(label.place_info().get('x', 0)) for label in labels}
        duration = 1500
        steps = 30
        interval = duration // steps

        def animate(step):
            if self.destroyed:
                return
            if step > steps:
                for label in labels:
                    label.place(x=targets[label])
                    label.target_pos = (targets[label], 0)
                self.settle_game()
                return
            for label in labels:
                new_x = starts[label] + (targets[label] - starts[label]) * step / steps
                label.place(x=new_x)
            self.after(interval, lambda: animate(step + 1))

        animate(1)

    def settle_game(self):
        if self.destroyed:
            return

        cowboy_eval, _, bull_eval, _ = self.game.evaluate_hands()
        if cowboy_eval > bull_eval:
            winner = 'cowboy'
        elif bull_eval > cowboy_eval:
            winner = 'bull'
        else:
            winner = 'tie'
            for cowboy_value, bull_value in zip(cowboy_eval[1], bull_eval[1]):
                if cowboy_value > bull_value:
                    winner = 'cowboy'
                    break
                if bull_value > cowboy_value:
                    winner = 'bull'
                    break

        combined_results = self.game.check_combined_hands()
        winner_hand_type, _ = self.game.get_winner_hand_type(cowboy_eval, bull_eval)
        winnings = 0.0
        self.win_details = {bet_type: 0.0 for bet_type in BET_PAYOUT}

        # 原始胜负结算：动态赔率；平手退还两边胜负注本金。
        if winner == 'cowboy':
            payout = self.game.dynamic_payouts['cowboy_win']
            amount = self.game.bets['cowboy_win'] * (1 + payout)
            winnings += amount
            self.win_details['cowboy_win'] = amount
        elif winner == 'bull':
            payout = self.game.dynamic_payouts['bull_win']
            amount = self.game.bets['bull_win'] * (1 + payout)
            winnings += amount
            self.win_details['bull_win'] = amount
        else:
            winnings += self.game.bets['cowboy_win'] + self.game.bets['bull_win']
            self.win_details['cowboy_win'] = self.game.bets['cowboy_win']
            self.win_details['bull_win'] = self.game.bets['bull_win']

        for bet_type in (
            'combined_straight_or_flush',
            'combined_full_house',
            'combined_quads_or_straight_flush',
        ):
            if combined_results[bet_type]:
                amount = self.game.bets[bet_type] * (1 + BET_PAYOUT[bet_type])
                winnings += amount
                self.win_details[bet_type] = amount

        if winner_hand_type:
            amount = self.game.bets[winner_hand_type] * (1 + BET_PAYOUT[winner_hand_type])
            winnings += amount
            self.win_details[winner_hand_type] = amount

        self.balance += winnings
        self.update_balance()
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: {format_money(winnings)}")
        self.stage_label.config(text='结算完成')
        result_name = '玩家1' if winner == 'cowboy' else '玩家2' if winner == 'bull' else '平手'
        self.table_status_label.config(text=f"游戏结束：{result_name}获胜" if winner != 'tie' else '游戏结束：双方平手')
        self._set_betting_controls_enabled(False)

        hit_bets = {
            'cowboy_win': winner == 'cowboy',
            'bull_win': winner == 'bull',
            'combined_straight_or_flush': combined_results['combined_straight_or_flush'],
            'combined_full_house': combined_results['combined_full_house'],
            'combined_quads_or_straight_flush': combined_results['combined_quads_or_straight_flush'],
            'high_card': winner_hand_type == 'high_card',
            'pair': winner_hand_type == 'pair',
            'two_pair': winner_hand_type == 'two_pair',
            'three_of_a_kind': winner_hand_type == 'three_of_a_kind',
            'straight': winner_hand_type == 'straight',
            'flush': winner_hand_type == 'flush',
            'full_house': winner_hand_type == 'full_house',
            'four_kind_or_straight_flush': winner_hand_type == 'four_kind_or_straight_flush',
        }

        # 结算时下注格显示赔付，但“本局下注”保持原下注总额。
        self.freeze_current_bet_display = True
        for bet_type, widget in self.bet_widgets.items():
            if hit_bets.get(bet_type, False):
                payout_amount = float(self.win_details.get(bet_type, 0))
                getattr(self, f'{bet_type}_var').set(self._format_bet_value(payout_amount))
                widget.config(bg='gold')
            else:
                getattr(self, f'{bet_type}_var').set('0')
                widget.config(bg='white')

        self.auto_reset_timer = self.after(5000, self.collect_cards)

    def collect_cards(self):
        if self.destroyed:
            return
        self.stage_label.config(text='收牌中')
        labels = list(self.active_card_labels)
        if not labels:
            self.reset_game()
            return

        for label in labels:
            label.collection_target = (20, 20)

        def animate():
            if self.destroyed:
                return
            unfinished = False
            for label in list(self.active_card_labels):
                try:
                    current_x, current_y = label.winfo_x(), label.winfo_y()
                except tk.TclError:
                    self.active_card_labels.remove(label)
                    continue
                target_x, target_y = label.collection_target
                dx, dy = target_x - current_x, target_y - current_y
                if math.hypot(dx, dy) < 5:
                    self.active_card_labels.remove(label)
                    label.destroy()
                    continue
                unfinished = True
                label.place(x=current_x + dx * 0.22, y=current_y + dy * 0.22)
            if unfinished or self.active_card_labels:
                self.after(20, animate)
            else:
                self.reset_game()

        animate()

    def update_timer(self):
        if self.destroyed or self.game.stage != 'betting':
            return
        elapsed = time.time() - self.bet_start_time
        remaining = max(0, 15 - int(elapsed))
        self.timer_label.config(text=f"下注时间: {remaining}秒")
        if remaining > 0:
            self.auto_start_timer = self.after(1000, self.update_timer)
        else:
            self.auto_start_timer = None
            self.enter_enabled = False
            self.start_game()

    # -----------------------------------------------------
    # 说明与牌序
    # -----------------------------------------------------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title('游戏规则')
        win.geometry('800x650')
        win.resizable(False, False)
        win.configure(bg=PANEL_BG)

        main_frame = tk.Frame(win, bg=PANEL_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg=PANEL_BG, yscrollcommand=scrollbar.set, highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content = tk.Frame(canvas, bg=PANEL_BG)
        canvas.create_window((0, 0), window=content, anchor='nw')

        rules = """
梭哈扑克双人对决游戏规则

1. 游戏流程
   - 玩家1和玩家2各获发五张牌。
   - 双方第一张牌先翻开为明牌。
   - 明牌展示后进入15秒下注阶段。
   - 按 Enter、点击“开始游戏”或倒计时结束后，翻开其余牌并结算。

2. 胜负下注
   - 玩家1赢与玩家2赢赔率根据双方明牌点数差动态调整。
   - 动态利润赔率范围为0.45:1至1.45:1。
   - 双方完全平手时，玩家1赢和玩家2赢下注退还本金。

3. 双方合并牌型（双方共10张牌中出现）
   - 顺子/同花：1.5:1
   - 葫芦：5:1
   - 四条/同花顺：30:1

4. 赢家牌型
   - 高牌：2.8:1
   - 对子：0.6:1
   - 两对：9.5:1
   - 三条：20:1
   - 顺子：120:1
   - 同花：240:1
   - 葫芦：320:1
   - 四条/同花顺：1700:1
"""
        tk.Label(
            content, text=rules, font=('微软雅黑', 11), bg=PANEL_BG,
            justify=tk.LEFT, padx=12, pady=12
        ).pack(fill=tk.X)
        content.update_idletasks()
        canvas.config(scrollregion=canvas.bbox('all'))
        ttk.Button(win, text='关闭', command=win.destroy).pack(pady=8)
        win.bind('<MouseWheel>', lambda event: canvas.yview_scroll(int(-event.delta / 120), 'units'))

    def show_card_sequence(self, _event):
        if self.auto_start_timer:
            try:
                self.after_cancel(self.auto_start_timer)
            except tk.TclError:
                pass
            self.auto_start_timer = None

        win = tk.Toplevel(self)
        win.title('本局牌序')
        win.geometry('650x600')
        win.resizable(False, False)
        win.configure(bg='#f0f0f0')
        tk.Label(
            win, text=f"本局切牌位置: {self.game.deck.start_pos + 1}",
            font=('Arial', 14, 'bold'), bg='#f0f0f0'
        ).pack(pady=(10, 5))

        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content = tk.Frame(canvas, bg='#f0f0f0')
        canvas.create_window((0, 0), window=content, anchor='nw')
        card_frame = tk.Frame(content, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        small_images = {}
        for index, card in enumerate(self.game.deck.full_deck):
            original = self.original_images.get((card.suit, card.rank))
            if original is None:
                original = self._make_placeholder_card(card.suit, card.rank, 'blue')
            small_images[index] = ImageTk.PhotoImage(original.resize((60, 90), Image.LANCZOS))

        for row in range(7):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)
            for col in range(8 if row < 6 else 4):
                card_index = row * 8 + col
                if card_index >= 52:
                    break
                cell = tk.Frame(row_frame, bg='#f0f0f0')
                cell.grid(row=0, column=col, padx=5, pady=5)
                is_cut = card_index == self.game.deck.start_pos
                bg = 'light blue' if is_cut else '#f0f0f0'
                card_label = tk.Label(cell, image=small_images[card_index], bg=bg, bd=1, relief=tk.SOLID)
                card_label.image = small_images[card_index]
                card_label.pack()
                tk.Label(cell, text=str(card_index + 1), bg=bg, font=('Arial', 9)).pack()

        content.update_idletasks()
        canvas.config(scrollregion=canvas.bbox('all'))
        win.bind('<MouseWheel>', lambda event: canvas.yview_scroll(int(-event.delta / 120), 'units'))


def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """
    Parent 嵌入接口：
        main(parent=..., balance=..., user=..., on_back=..., on_balance_change=...)

    未传 parent 时仍可独立运行。
    """
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        page = AutoStudPokerGUI(
            parent,
            actual_balance,
            actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.reset_game()
        return page

    root = tk.Tk()
    root.title('梭哈扑克双人对决')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    root.configure(bg=ROOT_BG)

    page = AutoStudPokerGUI(root, actual_balance, actual_user)
    page.pack(fill=tk.BOTH, expand=True)
    page.reset_game()

    def close_standalone(_balance=None):
        try:
            update_balance_in_json(page.username, page.balance)
        except Exception:
            pass
        page._cancel_timers()
        page._unbind_return_key()
        root.destroy()

    page.on_back = close_standalone
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance


if __name__ == '__main__':
    final_balance = main()
    print(f"最终余额: {final_balance}")