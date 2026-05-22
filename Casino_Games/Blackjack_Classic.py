import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import secrets
import json
import os
import math
import subprocess, sys

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        
    def __repr__(self):
        return f"{self.rank}{self.suit}"
    
    def get_value(self):
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11
        else:
            return int(self.rank)

class Deck:
    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        self.cards = []
        self.generate_deck()
        self.shuffle()
        self.cut_card_position = len(self.cards) - 60
    
    def generate_deck(self):
        self.cards = [Card(suit, rank) for _ in range(self.num_decks) for suit in SUITS for rank in RANKS]
    
    def shuffle(self):
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            shuffle_script = os.path.join(parent_dir, 'A_Tools', 'Card', 'shuffle.py')
            cmd = [sys.executable, shuffle_script, 'false', str(self.num_decks)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                shuffle_data = json.loads(result.stdout)
                shuffled_deck = shuffle_data['deck']
                self.cards = []
                for card_dict in shuffled_deck:
                    suit = card_dict['suit']
                    rank = card_dict['rank']
                    self.cards.append(Card(suit, rank))
                return
            else:
                print(f"shuffle.py执行失败，使用secrets洗牌: {result.stderr}")
        except Exception as e:
            print(f"调用shuffle.py失败，使用secrets洗牌: {e}")
        self._secrets_shuffle()
    
    def _secrets_shuffle(self):
        n = len(self.cards)
        for i in range(n - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]
        print(f"使用secrets洗牌完成，共{len(self.cards)}张牌")
    
    def deal_card(self):
        if len(self.cards) <= 60:
            print(f"牌堆剩余{len(self.cards)}张牌，重新洗牌")
            self.generate_deck()
            self.shuffle()
            self.cut_card_position = len(self.cards) - 60
        if len(self.cards) == 0:
            self.generate_deck()
            self.shuffle()
            self.cut_card_position = len(self.cards) - 60
        return self.cards.pop()
    
    def get_remaining_cards_count(self):
        count_dict = {}
        for suit in SUITS:
            count_dict[suit] = {}
            for rank in RANKS:
                count_dict[suit][rank] = 0
        for card in self.cards:
            count_dict[card.suit][card.rank] += 1
        return count_dict

class BlackjackGame:
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        self.player_hand = []
        self.dealer_hand = []
        self.main_bet = 0
        self.perfect_pair_bet = 0
        self.twenty_one_plus_three_bet = 0
        self.royal_match_bet = 0
        self.bust_bet = 0
        self.hot_3_bet = 0
        self.lucky_queen_bet = 0
        self.stage = "betting"
        self.player_done = False
        self.insurance_bet = 0
        self.insurance_taken = False
        self.player_blackjack = False
        self.dealer_blackjack = False
        self.double_extra = 0          # 额外加倍金额（用于庄家Blackjack时退还）
        self.dealer_second_dealt = False  # 是否已发庄家第二张牌
    
    def deal_initial_cards(self):
        # 玩家两张牌，庄家一张明牌（暗牌暂时不发）
        self.player_hand = [self.deck.deal_card(), self.deck.deal_card()]
        self.dealer_hand = [self.deck.deal_card()]   # 只有一张明牌
        self.dealer_second_dealt = False
    
    def add_dealer_second_card(self):
        """需要时给庄家补发第二张牌（暗牌）"""
        if not self.dealer_second_dealt:
            self.dealer_hand.append(self.deck.deal_card())
            self.dealer_second_dealt = True
    
    def get_hand_value(self, hand):
        value = sum(card.get_value() for card in hand)
        num_aces = sum(1 for card in hand if card.rank == 'A')
        while value > 21 and num_aces > 0:
            value -= 10
            num_aces -= 1
        return value
    
    def player_hit(self):
        self.player_hand.append(self.deck.deal_card())
        return self.get_hand_value(self.player_hand)
    
    def dealer_hit(self):
        self.dealer_hand.append(self.deck.deal_card())
        return self.get_hand_value(self.dealer_hand)
    
    def check_blackjack(self, hand):
        if len(hand) != 2:
            return False
        values = [card.get_value() for card in hand]
        return (11 in values and 10 in values) or (values[0] + values[1] == 21)
    
    def check_perfect_pair(self):
        if len(self.player_hand) < 2:
            return False
        card1, card2 = self.player_hand[0], self.player_hand[1]
        if card1.rank == card2.rank and card1.suit == card2.suit:
            return "perfect"
        elif (card1.rank == card2.rank and 
              ((card1.suit in ['♥', '♦'] and card2.suit in ['♥', '♦']) or 
               (card1.suit in ['♠', '♣'] and card2.suit in ['♠', '♣']))):
            return "colored"
        elif card1.rank == card2.rank:
            return "mixed"
        else:
            return None
    
    def check_twenty_one_plus_three(self):
        if len(self.player_hand) < 2 or len(self.dealer_hand) < 1:
            return None
        ranks = [self.player_hand[0].rank, self.player_hand[1].rank, self.dealer_hand[0].rank]
        suits = [self.player_hand[0].suit, self.player_hand[1].suit, self.dealer_hand[0].suit]
        if len(set(suits)) == 1:
            rank_values = []
            for r in ranks:
                if r == 'A': rank_values.append(14)
                elif r == 'K': rank_values.append(13)
                elif r == 'Q': rank_values.append(12)
                elif r == 'J': rank_values.append(11)
                else: rank_values.append(int(r))
            rank_values.sort()
            if (rank_values[2] - rank_values[1] == 1 and rank_values[1] - rank_values[0] == 1):
                return "straight_flush"
        if ranks[0] == ranks[1] == ranks[2]:
            if len(set(suits)) == 1:
                return "straight_three_of_a_kind"
            else:
                return "three_of_a_kind"
        rank_values = []
        for r in ranks:
            if r == 'A': rank_values.append(14)
            elif r == 'K': rank_values.append(13)
            elif r == 'Q': rank_values.append(12)
            elif r == 'J': rank_values.append(11)
            else: rank_values.append(int(r))
        rank_values.sort()
        if (rank_values[2] - rank_values[1] == 1 and rank_values[1] - rank_values[0] == 1):
            return "straight"
        if len(set(suits)) == 1:
            return "flush"
        return None
    
    def check_royal_match(self):
        if len(self.player_hand) < 2:
            return False
        card1, card2 = self.player_hand[0], self.player_hand[1]
        if card1.suit != card2.suit:
            return False
        if (card1.rank == 'Q' and card2.rank == 'K') or (card1.rank == 'K' and card2.rank == 'Q'):
            return "royal"
        else:
            return "suited"
    
    def check_hot_3(self):
        if len(self.player_hand) < 2 or len(self.dealer_hand) < 1:
            return None
        player_card1 = self.player_hand[0]
        player_card2 = self.player_hand[1]
        dealer_card = self.dealer_hand[0]
        
        def get_dynamic_value(card, other_cards):
            if card.rank != 'A':
                return card.get_value()
            other_total = 0
            for other_card in other_cards:
                if other_card.rank == 'A':
                    other_total += 11
                else:
                    other_total += other_card.get_value()
            if other_total + 11 > 21:
                return 1
            else:
                return 11
        
        total_value = 0
        cards = [player_card1, player_card2, dealer_card]
        for i, card in enumerate(cards):
            other_cards = [c for j, c in enumerate(cards) if j != i]
            total_value += get_dynamic_value(card, other_cards)
        
        all_sevens = (player_card1.rank == '7' and player_card2.rank == '7' and dealer_card.rank == '7')
        same_suit = (player_card1.suit == player_card2.suit == dealer_card.suit)
        
        if all_sevens:
            if same_suit:
                return "three_seven_same_suit"
            else:
                return "three_seven_mixed"
        elif total_value == 21:
            if same_suit:
                return "twenty_one_same_suit"
            else:
                return "twenty_one_mixed"
        elif total_value == 20:
            return "twenty"
        elif total_value == 19:
            return "nineteen"
        else:
            return None

    def check_lucky_queen(self):
        if len(self.player_hand) < 2:
            return None
        player_card1 = self.player_hand[0]
        player_card2 = self.player_hand[1]
        total_value = player_card1.get_value() + player_card2.get_value()
        if total_value != 20:
            return None
        
        both_queens = (player_card1.rank == 'Q' and player_card2.rank == 'Q')
        same_suit = (player_card1.suit == player_card2.suit)
        same_rank = (player_card1.rank == player_card2.rank)
        dealer_blackjack = self.check_blackjack(self.dealer_hand)
        
        if both_queens and same_suit:
            if dealer_blackjack:
                return "queens_same_suit_dealer_bj"
            else:
                return "queens_same_suit"
        elif same_rank and same_suit:
            return "same_rank_same_suit"
        elif same_suit:
            return "same_suit"
        else:
            return "mixed"

class BlackjackGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("经典21点")
        self.geometry("1150x650+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = BlackjackGame()
        self.card_images = {}
        self.card_positions = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.win_details = {
            "main": 0,
            "perfect_pair": 0,
            "twenty_one_plus_three": 0,
            "royal_match": 0,
            "bust": 0,
            "hot_3": 0,
            "lucky_queen": 0,
            "insurance": 0
        }
        self.bet_widgets = {}
        self.flipping_cards = []
        self.flip_step = 0
        self._resetting = False
        self.dealer_hidden_card_label = None
        self.insurance_offered = False
        self.side_bet_check_vars = {}
        
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
    
    def _load_assets(self):
        card_size = (100, 150)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.current_poker_folder = 'Poker1'
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club'}
        self.original_images = {}
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            back_img = back_img_orig.resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception as e:
            print(f"Error loading back image: {e}")
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
        for suit in SUITS:
            for rank in RANKS:
                suit_name = suit_mapping.get(suit, suit)
                filename = f"{suit_name}{rank}.png"
                path = os.path.join(card_dir, filename)
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        self.original_images[(suit, rank)] = img
                        img_resized = img.resize(card_size)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        text_width, text_height = draw.textsize(text, font=font)
                        x = (card_size[0] - text_width) / 2
                        y = (card_size[1] - text_height) / 2
                        draw.text((x, y), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading card image {path}: {e}")
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    text = "Error"
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    text_width, text_height = draw.textsize(text, font=font)
                    x = (card_size[0] - text_width) / 2
                    y = (card_size[1] - text_height) / 2
                    draw.text((x, y), text, fill="white", font=font)
                    self.original_images[(suit, rank)] = img_orig
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
    
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        if bet_type == "main":
            current = int(self.main_bet_var.get())
            new_value = current + chip_value
            if new_value > 25000:
                new_value = 25000
                messagebox.showwarning("下注限制", f"主注上限为25000，已自动调整")
            self.main_bet_var.set(str(int(new_value)))
        elif bet_type == "perfect_pair":
            current = int(self.perfect_pair_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"完美对子上限为2500，已自动调整")
            self.perfect_pair_var.set(str(int(new_value)))
        elif bet_type == "twenty_one_plus_three":
            current = int(self.twenty_one_plus_three_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"21+3上限为2500，已自动调整")
            self.twenty_one_plus_three_var.set(str(int(new_value)))
        elif bet_type == "royal_match":
            current = int(self.royal_match_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"皇家同花上限为2500，已自动调整")
            self.royal_match_var.set(str(int(new_value)))
        elif bet_type == "bust":
            current = int(self.bust_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"爆！上限为2500，已自动调整")
            self.bust_var.set(str(int(new_value)))
        elif bet_type == "hot_3":
            current = int(self.hot_3_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"热门3上限为2500，已自动调整")
            self.hot_3_var.set(str(int(new_value)))
        elif bet_type == "lucky_queen":
            current = int(self.lucky_queen_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"幸运女王上限为2500，已自动调整")
            self.lucky_queen_var.set(str(int(new_value)))
    
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=20, width=600, height=250)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.info_label = tk.Label(
            table_canvas, 
            text="庄家手牌16点必须要牌 任何17点停牌\n玩家BJ支付3:2 保险支付2:1 允许投降输一半", 
            font=('Arial', 22), 
            bg='#35654d', 
            fg='#FFD700'
        )
        self.info_label.update_idletasks()
        label_width = self.info_label.winfo_width()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        center_x = (canvas_width - label_width) // 2
        self.info_label.place(x=center_x + 355, y=280, anchor='n')
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=365, width=600, height=250)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=250, padx=10, pady=5)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 18),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=5)
        self.stage_label = tk.Label(
            info_frame, 
            text="下注阶段",
            font=('Arial', 18, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=5)
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        chip_configs = [
            ('$10', '#ffa500', 'black'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black'),
            ("$2.5K", '#ff0000', 'white'),
        ]
        self.chip_buttons = []
        self.chip_texts = {}
        for text, bg_color, fg_color in chip_configs:
            chip_canvas = tk.Canvas(chip_row, width=57, height=57, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 55, 55, fill=bg_color, outline='black')
            text_id = chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip("$10")
        minmax_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        minmax_frame.pack(fill=tk.X, pady=5)
        header_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(header_frame, text="主注最低", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="主注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="边注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$25,000", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        first_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        first_row_frame.pack(fill=tk.X, padx=10, pady=3)
        perfect_pair_label = tk.Label(first_row_frame, text="完美对子:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        perfect_pair_label.pack(side=tk.LEFT, padx=1)
        self.perfect_pair_var = tk.StringVar(value="0")
        self.perfect_pair_display = tk.Label(first_row_frame, textvariable=self.perfect_pair_var, font=('Arial', 14), 
                                            bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.perfect_pair_display.pack(side=tk.LEFT, padx=5)
        self.perfect_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("perfect_pair"))
        self.perfect_pair_display.bind("<Button-3>", lambda e: self.clear_bet("perfect_pair"))
        self.bet_widgets["perfect_pair"] = self.perfect_pair_display
        self.side_bet_check_vars["perfect_pair"] = tk.BooleanVar(value=True)
        perfect_pair_check = tk.Checkbutton(first_row_frame, variable=self.side_bet_check_vars["perfect_pair"], 
                                          bg='#2a4a3c', activebackground='#2a4a3c')
        perfect_pair_check.pack(side=tk.LEFT, padx=2)
        tk.Label(first_row_frame, text=" ", bg='#2a4a3c').pack(side=tk.LEFT, padx=11)
        twenty_one_plus_three_label = tk.Label(first_row_frame, text="21+3:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        twenty_one_plus_three_label.pack(side=tk.LEFT)
        self.twenty_one_plus_three_var = tk.StringVar(value="0")
        self.twenty_one_plus_three_display = tk.Label(first_row_frame, textvariable=self.twenty_one_plus_three_var, font=('Arial', 14), 
                                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.twenty_one_plus_three_display.pack(side=tk.LEFT, padx=5)
        self.twenty_one_plus_three_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("twenty_one_plus_three"))
        self.twenty_one_plus_three_display.bind("<Button-3>", lambda e: self.clear_bet("twenty_one_plus_three"))
        self.bet_widgets["twenty_one_plus_three"] = self.twenty_one_plus_three_display
        self.side_bet_check_vars["twenty_one_plus_three"] = tk.BooleanVar(value=True)
        twenty_one_plus_three_check = tk.Checkbutton(first_row_frame, variable=self.side_bet_check_vars["twenty_one_plus_three"], 
                                                   bg='#2a4a3c', activebackground='#2a4a3c')
        twenty_one_plus_three_check.pack(side=tk.LEFT, padx=2)
        second_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        second_row_frame.pack(fill=tk.X, padx=10, pady=3)
        royal_match_label = tk.Label(second_row_frame, text="皇家同花:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        royal_match_label.pack(side=tk.LEFT)
        self.royal_match_var = tk.StringVar(value="0")
        self.royal_match_display = tk.Label(second_row_frame, textvariable=self.royal_match_var, font=('Arial', 14), 
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.royal_match_display.pack(side=tk.LEFT, padx=5)
        self.royal_match_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("royal_match"))
        self.royal_match_display.bind("<Button-3>", lambda e: self.clear_bet("royal_match"))
        self.bet_widgets["royal_match"] = self.royal_match_display
        self.side_bet_check_vars["royal_match"] = tk.BooleanVar(value=True)
        royal_match_check = tk.Checkbutton(second_row_frame, variable=self.side_bet_check_vars["royal_match"], 
                                         bg='#2a4a3c', activebackground='#2a4a3c')
        royal_match_check.pack(side=tk.LEFT, padx=2)
        tk.Label(second_row_frame, text=" ", bg='#2a4a3c').pack(side=tk.LEFT, padx=11)
        bust_label = tk.Label(second_row_frame, text="爆！:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        bust_label.pack(side=tk.LEFT, padx=2)
        self.bust_var = tk.StringVar(value="0")
        self.bust_display = tk.Label(second_row_frame, textvariable=self.bust_var, font=('Arial', 14), 
                                bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.bust_display.pack(side=tk.LEFT, padx=5)
        self.bust_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bust"))
        self.bust_display.bind("<Button-3>", lambda e: self.clear_bet("bust"))
        self.bet_widgets["bust"] = self.bust_display
        self.side_bet_check_vars["bust"] = tk.BooleanVar(value=True)
        bust_check = tk.Checkbutton(second_row_frame, variable=self.side_bet_check_vars["bust"], 
                                  bg='#2a4a3c', activebackground='#2a4a3c')
        bust_check.pack(side=tk.LEFT, padx=2)
        third_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        third_row_frame.pack(fill=tk.X, padx=10, pady=3)
        lucky_queen_label = tk.Label(third_row_frame, text="幸运女王:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        lucky_queen_label.pack(side=tk.LEFT)
        self.lucky_queen_var = tk.StringVar(value="0")
        self.lucky_queen_display = tk.Label(third_row_frame, textvariable=self.lucky_queen_var, font=('Arial', 14), 
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.lucky_queen_display.pack(side=tk.LEFT, padx=5)
        self.lucky_queen_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("lucky_queen"))
        self.lucky_queen_display.bind("<Button-3>", lambda e: self.clear_bet("lucky_queen"))
        self.bet_widgets["lucky_queen"] = self.lucky_queen_display
        self.side_bet_check_vars["lucky_queen"] = tk.BooleanVar(value=True)
        lucky_queen_check = tk.Checkbutton(third_row_frame, variable=self.side_bet_check_vars["lucky_queen"], 
                                         bg='#2a4a3c', activebackground='#2a4a3c')
        lucky_queen_check.pack(side=tk.LEFT, padx=2)
        tk.Label(third_row_frame, text=" ", bg='#2a4a3c').pack(side=tk.LEFT, padx=8)
        hot_3_label = tk.Label(third_row_frame, text="热门3:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        hot_3_label.pack(side=tk.LEFT)
        self.hot_3_var = tk.StringVar(value="0")
        self.hot_3_display = tk.Label(third_row_frame, textvariable=self.hot_3_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.hot_3_display.pack(side=tk.LEFT, padx=5)
        self.hot_3_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("hot_3"))
        self.hot_3_display.bind("<Button-3>", lambda e: self.clear_bet("hot_3"))
        self.bet_widgets["hot_3"] = self.hot_3_display
        self.side_bet_check_vars["hot_3"] = tk.BooleanVar(value=True)
        hot_3_check = tk.Checkbutton(third_row_frame, variable=self.side_bet_check_vars["hot_3"], 
                                   bg='#2a4a3c', activebackground='#2a4a3c')
        hot_3_check.pack(side=tk.LEFT, padx=2)
        fourth_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        fourth_row_frame.pack(fill=tk.X, padx=10, pady=3)
        main_bet_label = tk.Label(fourth_row_frame, text="主注:", font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='white')
        main_bet_label.pack(side=tk.LEFT, padx=2)
        self.main_bet_var = tk.StringVar(value="0")
        self.main_bet_display = tk.Label(fourth_row_frame, textvariable=self.main_bet_var, font=('Arial', 18, 'bold'), 
                                    bg='white', fg='black', width=8, relief=tk.SUNKEN, padx=5)
        self.main_bet_display.pack(side=tk.LEFT, padx=2)
        self.main_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("main"))
        self.main_bet_display.bind("<Button-3>", lambda e: self.clear_bet("main"))
        self.bet_widgets["main"] = self.main_bet_display
        self.side_bet_all_in_frame = tk.Frame(fourth_row_frame, bg='#2a4a3c')
        self.side_bet_all_in_frame.pack(side=tk.LEFT, padx=15)
        self.side_bet_all_in_btn = tk.Button(
            self.side_bet_all_in_frame, text="边注全下", 
            command=self.side_bet_all_in, font=('Arial', 13, 'bold'),
            bg="#00DDFF", fg='black', width=13
        )
        self.side_bet_all_in_btn.pack(side=tk.LEFT, padx=5)
        self.insurance_label = tk.Label(self.side_bet_all_in_frame, text="保险:", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.insurance_var = tk.StringVar(value="0")
        self.insurance_display = tk.Label(self.side_bet_all_in_frame, textvariable=self.insurance_var, font=('Arial', 18), 
                                     bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=3)
        self.side_bet_all_in_btn.pack(side=tk.LEFT, padx=5)
        self.insurance_label.pack_forget()
        self.insurance_display.pack_forget()
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X)
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重置金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
        self.reset_bets_button.config(state=tk.NORMAL)
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        self.start_button.config(state=tk.NORMAL)
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.current_bet_label = tk.Label(
            bet_info_frame, text="本局下注: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        self.last_win_label = tk.Label(
            bet_info_frame, text="上局获胜: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)
        rules_btn = tk.Button(
            bet_info_frame, text="ℹ️",
            command=self.show_game_instructions,
            font=('Arial', 8), bg='#4B8BBE', fg='white', width=2, height=1
        )
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)
        rules_btn.bind("<Button-3>", self.show_remaining_cards)
    
    def side_bet_all_in(self):
        if not self.selected_chip:
            messagebox.showinfo("提示", "请先选择筹码")
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        for bet_type in ["perfect_pair", "twenty_one_plus_three", "royal_match", "bust", "hot_3", "lucky_queen"]:
            if self.side_bet_check_vars[bet_type].get():
                current = int(getattr(self, f"{bet_type}_var").get())
                new_value = current + chip_value
                if new_value > 2500:
                    new_value = 2500
                    messagebox.showwarning("下注限制", f"{bet_type}上限为2500，已自动调整")
                getattr(self, f"{bet_type}_var").set(str(int(new_value)))
        for bet_type in ["perfect_pair", "twenty_one_plus_three", "royal_match", "bust", "hot_3", "lucky_queen"]:
            if self.side_bet_check_vars[bet_type].get():
                widget = self.bet_widgets[bet_type]
                original_color = widget.cget('bg')
                widget.config(bg='#C8E6C9')
                self.after(300, lambda w=widget, c=original_color: w.config(bg=c))
    
    def show_remaining_cards(self, event=None):
        remaining_cards = self.game.deck.get_remaining_cards_count()
        win = tk.Toplevel(self)
        win.title("剩余牌堆统计")
        win.geometry("600x400")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        title_label = tk.Label(
            main_frame, 
            text=f"剩余{len(self.game.deck.cards)}张牌",
            font=('Arial', 16, 'bold'),
            bg='#F0F0F0',
            fg='#333333'
        )
        title_label.pack(pady=(0, 10))
        table_frame = tk.Frame(main_frame, bg='#F0F0F0')
        table_frame.pack(fill=tk.BOTH, expand=True)
        header_frame = tk.Frame(table_frame, bg='#F0F0F0')
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="", width=6, bg='#F0F0F0').pack(side=tk.LEFT)
        for rank in RANKS:
            display_rank = 'X' if rank == '10' else rank
            label = tk.Label(
                header_frame, 
                text=display_rank, 
                width=4, 
                font=('Arial', 10, 'bold'),
                bg='#F0F0F0',
                relief=tk.RAISED,
                bd=1
            )
            label.pack(side=tk.LEFT, padx=1)
        total_label = tk.Label(
            header_frame, 
            text="总计", 
            width=4, 
                font=('Arial', 10, 'bold'),
                bg='#F0F0F0',
                relief=tk.RAISED,
                bd=1
            )
        total_label.pack(side=tk.LEFT, padx=1)
        for suit in SUITS:
            row_frame = tk.Frame(table_frame, bg='#F0F0F0')
            row_frame.pack(fill=tk.X)
            suit_label = tk.Label(
                row_frame, 
                text=suit, 
                width=4, 
                font=('Arial', 12, 'bold'),
                bg='#F0F0F0',
                relief=tk.RAISED,
                bd=1
            )
            suit_label.pack(side=tk.LEFT, padx=1)
            suit_total = 0
            for rank in RANKS:
                count = remaining_cards[suit][rank]
                suit_total += count
                if count == 0:
                    bg_color = '#FFCCCC'
                elif count < 4:
                    bg_color = '#FFFFCC'
                else:
                    bg_color = '#CCFFCC'
                count_label = tk.Label(
                    row_frame, 
                    text=str(count), 
                    width=4,
                    font=('Arial', 10),
                    bg=bg_color,
                    relief=tk.SUNKEN,
                    bd=1
                )
                count_label.pack(side=tk.LEFT, padx=1)
            total_label = tk.Label(
                row_frame, 
                text=str(suit_total), 
                width=4,
                font=('Arial', 10, 'bold'),
                bg='#DDDDDD',
                relief=tk.RAISED,
                bd=1
            )
            total_label.pack(side=tk.LEFT, padx=1)
        separator = tk.Frame(table_frame, height=2, bg='#333333')
        separator.pack(fill=tk.X, pady=5)
        total_row_frame = tk.Frame(table_frame, bg='#F0F0F0')
        total_row_frame.pack(fill=tk.X, padx=8)
        tk.Label(
            total_row_frame, 
            text="总计", 
            width=4, 
            font=('Arial', 10, 'bold'),
            bg='#F0F0F0',
            relief=tk.RAISED,
            bd=1
        ).pack(side=tk.LEFT, padx=1)
        rank_totals = {}
        for rank in RANKS:
            rank_totals[rank] = 0
            for suit in SUITS:
                rank_totals[rank] += remaining_cards[suit][rank]
        grand_total = 0
        for rank in RANKS:
            total = rank_totals[rank]
            grand_total += total
            if total == 0:
                bg_color = '#FFCCCC'
            elif total < 16:
                bg_color = '#FFFFCC'
            else:
                bg_color = '#CCFFCC'
            total_label = tk.Label(
                total_row_frame, 
                text=str(total), 
                width=4,
                font=('Arial', 10, 'bold'),
                bg=bg_color,
                relief=tk.RAISED,
                bd=1
            )
            total_label.pack(side=tk.LEFT, padx=1)
        grand_total_label = tk.Label(
            total_row_frame, 
            text=str(grand_total), 
            width=4,
            font=('Arial', 10, 'bold'),
            bg='#CCCCFF',
            relief=tk.RAISED,
            bd=1
        )
        grand_total_label.pack(side=tk.LEFT, padx=1)
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)
    
    def clear_bet(self, bet_type):
        if self.game.stage != "betting":
            return
        if bet_type == "main":
            self.main_bet_var.set("0")
        elif bet_type == "perfect_pair":
            self.perfect_pair_var.set("0")
        elif bet_type == "twenty_one_plus_three":
            self.twenty_one_plus_three_var.set("0")
        elif bet_type == "royal_match":
            self.royal_match_var.set("0")
        elif bet_type == "bust":
            self.bust_var.set("0")
        elif bet_type == "hot_3":
            self.hot_3_var.set("0")
        elif bet_type == "lucky_queen":
            self.lucky_queen_var.set("0")
        widget = self.bet_widgets[bet_type]
        original_color = widget.cget('bg')
        widget.config(bg='#FFCDD2')
        self.after(300, lambda: widget.config(bg=original_color))
    
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("21点游戏规则")
        win.geometry("900x700")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        rules_text = """
        21点游戏规则

        1. 游戏目标:
           - 使手中牌的点数总和尽可能接近21点，但不能超过
           - 如果超过21点，则称为"爆牌"，自动输掉游戏

        2. 牌值计算:
           - 2-10: 牌面值
           - J, Q, K: 10点
           - A: 1点或11点（自动选择最有利的值）

        3. 游戏流程:
           a. 下注阶段:
               - 玩家下注主注
               - 可选择下注边注：完美对子、21+3、皇家同花、爆！

           b. 发牌:
               - 玩家和庄家各发两张牌
               - 庄家一张牌面朝上，一张牌面朝下

           c. 玩家回合:
               - 要牌: 获得一张新牌
               - 停牌: 不再要牌
               - 加倍: 双倍下注，只能再要一张牌
               - 投降: 输掉一半下注（仅在初始两张牌时可用）

           d. 庄家回合:
               - 庄家必须要牌直到手牌点数达到17点或更高

        4. 结算规则:
           - 玩家Blackjack（A+10/J/Q/K）: 支付1.5倍
           - 玩家点数更高: 支付1倍
           - 庄家点数更高: 玩家输掉下注
           - 平局: 退还下注

        5. 边注规则:
        - 完美对子:
            * 完美对子（相同花色和点数）: 25:1
            * 同色对子（相同颜色和点数）: 12:1
            * 混合对子（相同点数）: 6:1

        - 21+3:
            * 同花三条: 100:1
            * 同花顺: 40:1
            * 三条: 30:1
            * 顺子: 10:1
            * 同花: 5:1

        - 皇家同花:
            * 皇家同花（同花Q和K）: 25:1
            * 同花: 5:2

        - 爆！:
            * 庄家爆牌时根据爆牌的张数支付:
            - 3张: 1:1
            - 4张: 2:1
            - 5张: 10:1
            - 6张: 50:1
            - 7张: 100:1
            - 8张或更多: 250:1

        - 热门3:
            * 玩家的头2张手牌和庄家的第1张手牌
            - 加起来刚好19点: 1:1
            - 加起来刚好20点: 2:1
            - 加起来刚好21点，但花色不一: 4:1
            - 加起来刚好21点，并且3张牌花色一样: 20:1
            - 点数都是7点，但花色不一: 100:1
            - 点数都是7点，并且3张牌花色一样: 500:1

        - 幸运女王:
            * 玩家的头2张手牌刚好20点
            - 但花色不一样的: 4:1
            - 并且花色一样的: 10:1
            - 并且花色和点数^一样的: 30:1
            - 并且花色一样的，两张牌都是Q: 100:1
            - 并且花色一样的，两张牌都是Q，同时庄家是Blackjack: 1000:1

            ^10-10/J-J/K-K; 10-J这种虽然也是代表点数10，但是并不算是点数一样的
    """
        rules_label = tk.Label(
            content_frame, 
            text=rules_text,
            font=('微软雅黑', 11),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        rules_label.pack(fill=tk.X, padx=10, pady=5)
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    
    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item_id)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            for item_id in chip.find_all():
                t = chip.type(item_id)
                if t == 'text':
                    text_id = item_id
                elif t == 'oval':
                    oval_id = item_id
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                x1, y1, x2, y2 = chip.coords(oval_id)
                chip.create_oval(x1, y1, x2, y2, outline='gold', width=3, tags="highlight")
                break
    
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
    
    def update_hand_labels(self):
        if self.game.player_hand:
            player_value = self.game.get_hand_value(self.game.player_hand)
            if self.game.check_blackjack(self.game.player_hand):
                player_text = "玩家 - BJ"
            elif player_value > 21:
                player_text = f"玩家 - {player_value}点 (爆牌)"
            else:
                player_text = f"玩家 - {player_value}点"
            self.player_label.config(text=player_text)
        if self.game.dealer_hand:
            dealer_value = self.game.get_hand_value(self.game.dealer_hand)
            dealer_text = "庄家"
            if self.game.stage == "showdown" or self.game.player_done:
                if self.game.check_blackjack(self.game.dealer_hand):
                    dealer_text = "庄家 - BJ"
                elif dealer_value > 21:
                    dealer_text = f"庄家 - {dealer_value}点 (爆牌)"
                else:
                    dealer_text = f"庄家 - {dealer_value}点"
            else:
                # 只显示第一张牌的值（庄家只有一张明牌）
                first_card_value = self.game.dealer_hand[0].get_value()
                dealer_text = f"庄家 - {first_card_value}点"
            self.dealer_label.config(text=dealer_text)
    
    def disable_action_buttons(self):
        self.hit_button.config(state=tk.DISABLED)
        self.stand_button.config(state=tk.DISABLED)
        self.surrender_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)
        
    def enable_action_buttons(self):
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)
    
    def _create_scaled_image(self, card, width, height, use_back=False):
        if use_back:
            img = self.original_images["back"].copy()
        else:
            img = self.original_images[(card.suit, card.rank)].copy()
        img = img.resize((width, height), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    
    def flip_card_animation(self, card_label, card, callback=None):
        def flip_step(step=0):
            if card_label is None:
                return
            steps = 12
            if step > steps:
                card_label.config(image=self.card_images.get((card.suit, card.rank), self.back_image))
                if callback:
                    callback()
                return
            half = steps // 2
            if step <= half:
                ratio = 1 - (step / float(half))
                use_back = True
            else:
                ratio = (step - half) / float(half)
                use_back = False
            full_w, full_h = 100, 150
            w = max(1, int(full_w * ratio))
            img = self._create_scaled_image(card, w, full_h, use_back=use_back)
            if not hasattr(self, '_temp_flip_images'):
                self._temp_flip_images = {}
            self._temp_flip_images[id(card_label)] = img
            card_label.config(image=img)
            self.after(20, lambda: flip_step(step + 1))
        flip_step()
    
    def add_card_to_frame(self, frame, card, show_front=True, position=None):
        if show_front:
            card_img = self.card_images.get((card.suit, card.rank), self.back_image)
        else:
            card_img = self.back_image
        card_label = tk.Label(frame, image=card_img, bg='#2a4a3c')
        full_w, full_h = 100, 150
        normal_spacing = full_w + 10
        if position is None:
            card_label.pack(side=tk.LEFT, padx=5)
        else:
            x = position * normal_spacing
            card_label.place(x=x, y=0, width=full_w, height=full_h)
        card_label.card = card
        card_label.is_face_up = show_front
        self.active_card_labels.append(card_label)
        try:
            labels = [w for w in frame.winfo_children() if isinstance(w, tk.Label)]
            count = len(labels)
            if count > 5:
                target_spacing = full_w - 70
                duration_ms = 750
                step_time = 20
                steps = max(1, int(duration_ms / step_time))
                start_positions = []
                target_positions = []
                for idx, lbl in enumerate(labels):
                    pi = {}
                    try:
                        pi = lbl.place_info()
                    except Exception:
                        pi = {}
                    if 'x' in pi and pi['x'] != '':
                        try:
                            sx = int(float(pi['x']))
                        except Exception:
                            sx = lbl.winfo_x()
                    else:
                        try:
                            sx = lbl.winfo_x()
                        except Exception:
                            sx = 0
                    start_positions.append(sx)
                    tx = idx * target_spacing
                    target_positions.append(tx)
                deltas = [(target_positions[i] - start_positions[i]) / float(steps) for i in range(len(labels))]
                def do_step(step=1):
                    if self._resetting:
                        for i, lbl in enumerate(labels):
                            try:
                                lbl.place(x=target_positions[i], y=0)
                            except Exception:
                                pass
                        return
                    for i, lbl in enumerate(labels):
                        if i == 0:
                            try:
                                lbl.place(x=0, y=0)
                            except Exception:
                                pass
                            continue
                        new_x = start_positions[i] + deltas[i] * step
                        try:
                            lbl.place(x=int(round(new_x)), y=0)
                        except Exception:
                            try:
                                lbl.place_configure(x=int(round(new_x)), y=0)
                            except Exception:
                                pass
                    if step < steps:
                        self.after(step_time, lambda: do_step(step + 1))
                    else:
                        for i, lbl in enumerate(labels):
                            try:
                                lbl.place(x=target_positions[i], y=0)
                            except Exception:
                                pass
                do_step(1)
        except Exception:
            pass
        return card_label
        
    def play_shuffle_animation(self, duration_ms=10000, callback=None):
        try:
            win = tk.Toplevel(self)
            win.title("正在洗牌...")
            win.resizable(False, False)
            win.transient(self)
            win.grab_set()
            win.configure(bg='#2a2a2a')
            win.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() - 520) // 2
            y = self.winfo_y() + (self.winfo_height() - 220) // 2
            win.geometry(f"520x220+{x}+{y}")
            win.protocol("WM_DELETE_WINDOW", lambda: None)
            canvas = tk.Canvas(win, width=520, height=220, bg='#2a2a2a', highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            small_w, small_h = 90, 135
            try:
                back_img_orig = self.original_images.get("back")
                if back_img_orig is None:
                    back_img = Image.new('RGBA', (small_w, small_h), (0, 0, 0, 255))
                else:
                    back_img = back_img_orig.copy().resize((small_w, small_h), Image.LANCZOS)
            except Exception:
                back_img = Image.new('RGBA', (small_w, small_h), (0, 0, 0, 255))
            num_cards = 10
            center_x = 520 // 2
            center_y = 220 // 2
            spread = 200
            start_x = center_x - spread // 2
            gap = spread // max(1, num_cards - 1)
            if not hasattr(self, '_shuffle_imgs'):
                self._shuffle_imgs = []
            else:
                self._shuffle_imgs.clear()
            items = []
            for i in range(num_cards):
                scale = 0.95 + (i % 3) * 0.03
                iw = max(20, int(small_w * scale))
                ih = max(30, int(small_h * scale))
                try:
                    tmp = back_img.resize((iw, ih), Image.LANCZOS)
                except Exception:
                    tmp = back_img
                tkimg = ImageTk.PhotoImage(tmp)
                self._shuffle_imgs.append(tkimg)
                x = start_x + i * gap
                y = center_y + (i % 2) * 6
                item = canvas.create_image(x, y, image=tkimg, anchor='center')
                items.append({
                    'id': item,
                    'base_x': x,
                    'base_y': y,
                    'phase': (i * 2 * math.pi) / max(1, num_cards),
                    'amp': 10 + (i % 4) * 4,
                    'z': i
                })
            txt = canvas.create_text(520//2, 18, text="正在洗牌，请稍候...", fill='white', font=('Arial', 14, 'bold'))
            total_steps = max(1, int(duration_ms / 40))
            step = {'i': 0}
            def anim_step():
                i = step['i']
                frac = i / float(total_steps)
                for idx, it in enumerate(items):
                    pid = it['id']
                    phase = it['phase']
                    amp = it['amp']
                    dx = math.sin(phase + frac * 12.0) * amp * (0.8 + 0.4 * math.sin(frac * 2 * math.pi + idx))
                    dy = math.sin(phase * 0.7 + frac * 6.0) * (amp / 6.0)
                    new_x = it['base_x'] + dx * (1.0 - frac * 0.3)
                    new_y = it['base_y'] + dy
                    canvas.coords(pid, new_x, new_y)
                    if (i + idx) % 20 < 10:
                        canvas.tag_raise(pid)
                    else:
                        canvas.tag_lower(pid)
                step['i'] += 1
                if step['i'] <= total_steps:
                    win.after(40, anim_step)
                else:
                    def do_close():
                        try:
                            win.grab_release()
                        except Exception:
                            pass
                        try:
                            win.destroy()
                        except Exception:
                            pass
                        if callback:
                            try:
                                callback()
                            except Exception as e:
                                print(f"洗牌回调错误: {e}")
                    win.after(100, do_close)
            anim_step()
        except Exception as e:
            print(f"洗牌动画失败: {e}")
            if callback:
                try:
                    callback()
                except Exception:
                    pass
        
    def start_game(self):
        try:
            self.game.main_bet = int(self.main_bet_var.get())
            self.game.perfect_pair_bet = int(self.perfect_pair_var.get())
            self.game.twenty_one_plus_three_bet = int(self.twenty_one_plus_three_var.get())
            self.game.royal_match_bet = int(self.royal_match_var.get())
            self.game.bust_bet = int(self.bust_var.get())
            self.game.hot_3_bet = int(self.hot_3_var.get())
            self.game.lucky_queen_bet = int(self.lucky_queen_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return
        if self.game.main_bet < 10:
            messagebox.showerror("错误", "主注至少需要10块")
            return
        total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                    self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                    self.game.bust_bet + self.game.hot_3_bet + self.game.lucky_queen_bet)
        if self.balance < total_bet:
            messagebox.showerror("错误", "余额不足以支付所有下注！")
            return
        self.disable_betting_area()
        self.last_win_label.config(text="上局获胜: $0.00")
        self.start_button.config(state=tk.DISABLED)
        self.reset_bets_button.config(state=tk.DISABLED)
        self.side_bet_all_in_btn.pack_forget()
        self.insurance_label.pack(side=tk.LEFT, padx=5)
        self.insurance_display.pack(side=tk.LEFT, padx=1)
        self.insurance_var.set("0")
        self.balance -= total_bet
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        need_shuffle = False
        if not hasattr(self.game, 'deck') or self.game.deck is None:
            need_shuffle = True
        else:
            remaining_cards = len(self.game.deck.cards)
            if remaining_cards <= 60:
                need_shuffle = True
        def continue_after_shuffle():
            self.game.deck = Deck(8)
            self.game.player_hand = []
            self.game.dealer_hand = []
            self.game.stage = "dealing"
            self.game.player_done = False
            self.game.insurance_bet = 0
            self.game.insurance_taken = False
            self.game.player_blackjack = False
            self.game.dealer_blackjack = False
            self.game.double_extra = 0
            self.game.dealer_second_dealt = False
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()
            try:
                self.game.deal_initial_cards()
            except Exception as e:
                print(f"发牌失败: {e}")
                messagebox.showerror("错误", "发牌失败，请重新开始游戏")
                return
            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            self.deal_card_sequence()
        def continue_without_shuffle():
            self.game.player_hand = []
            self.game.dealer_hand = []
            self.game.stage = "dealing"
            self.game.player_done = False
            self.game.insurance_bet = 0
            self.game.insurance_taken = False
            self.game.player_blackjack = False
            self.game.dealer_blackjack = False
            self.game.double_extra = 0
            self.game.dealer_second_dealt = False
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()
            try:
                self.game.deal_initial_cards()
            except Exception as e:
                print(f"发牌失败: {e}")
                messagebox.showerror("错误", "发牌失败，请重新开始游戏")
                return
            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            self.deal_card_sequence()
        if need_shuffle:
            self.play_shuffle_animation(duration_ms=10000, callback=continue_after_shuffle)
        else:
            continue_without_shuffle()
    
    def disable_betting_area(self):
        for bet_type, widget in self.bet_widgets.items():
            widget.unbind("<Button-1>")
            widget.unbind("<Button-3>")
        
    def enable_betting_area(self):
        for bet_type, widget in self.bet_widgets.items():
            widget.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            widget.bind("<Button-3>", lambda e, bt=bet_type: self.clear_bet(bt))
            widget.config(bg='white', fg='black')
        
    def deal_card_sequence(self):
        self.status_label.config(text="发玩家第一张牌")
        player_card1 = self.game.player_hand[0]
        player_card1_label = self.add_card_to_frame(self.player_cards_frame, player_card1, show_front=True, position=0)
        self.flip_card_animation(player_card1_label, player_card1, callback=self.after_player_card1)
    
    def after_player_card1(self):
        first_card_value = self.game.player_hand[0].get_value()
        player_text = f"玩家 - {first_card_value}点"
        self.player_label.config(text=player_text)
        self.status_label.config(text="发庄家第一张牌")
        dealer_card1 = self.game.dealer_hand[0]
        dealer_card1_label = self.add_card_to_frame(self.dealer_cards_frame, dealer_card1, show_front=True, position=0)
        self.flip_card_animation(dealer_card1_label, dealer_card1, callback=self.after_dealer_card1)
    
    def after_dealer_card1(self):
        self.update_hand_labels()
        self.status_label.config(text="发玩家第二张牌")
        player_card2 = self.game.player_hand[1]
        player_card2_label = self.add_card_to_frame(self.player_cards_frame, player_card2, show_front=True, position=1)
        self.flip_card_animation(player_card2_label, player_card2, callback=self.after_player_card2)
    
    def after_player_card2(self):
        self.update_hand_labels()
        # 检查是否提供保险（庄家明牌为A）
        upcard = self.game.dealer_hand[0]
        if upcard.rank == 'A':
            self.offer_insurance()
        else:
            # 不提供保险时，直接检查Blackjack并继续
            self.check_blackjack_and_continue()
    
    def offer_insurance(self):
        self.game.stage = "insurance"
        self.stage_label.config(text="保险选项")
        self.status_label.config(text="庄家明牌是A，是否购买保险？")
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        insurance_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        insurance_frame.pack(pady=5)
        self.insurance_btn = tk.Button(
            insurance_frame, text="购买保险",
            command=self.take_insurance,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=10
        )
        self.insurance_btn.pack(side=tk.LEFT, padx=5)
        self.no_insurance_btn = tk.Button(
            insurance_frame, text="不购买",
            command=self.decline_insurance,
            font=('Arial', 14), bg='#F44336', fg='white', width=10
        )
        self.no_insurance_btn.pack(side=tk.LEFT, padx=5)
    
    def take_insurance(self):
        if hasattr(self, 'insurance_btn'):
            self.insurance_btn.config(state=tk.DISABLED)
        if hasattr(self, 'no_insurance_btn'):
            self.no_insurance_btn.config(state=tk.DISABLED)
        insurance_amount = self.game.main_bet / 2
        if self.balance >= insurance_amount:
            self.balance -= insurance_amount
            self.game.insurance_bet = insurance_amount
            self.game.insurance_taken = True
            self.update_balance()
            self.insurance_var.set(str(int(insurance_amount)))
            total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                    self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                    self.game.bust_bet + self.game.hot_3_bet + self.game.lucky_queen_bet + self.game.insurance_bet)
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.status_label.config(text=f"已购买保险 ${self.game.insurance_bet}")
            self.after(1000, self.check_blackjack_and_continue)
        else:
            messagebox.showerror("错误", "余额不足以购买保险")
            self.decline_insurance()
    
    def decline_insurance(self):
        if hasattr(self, 'insurance_btn'):
            self.insurance_btn.config(state=tk.DISABLED)
        if hasattr(self, 'no_insurance_btn'):
            self.no_insurance_btn.config(state=tk.DISABLED)
        self.game.insurance_taken = False
        self.status_label.config(text="未购买保险")
        self.after(1000, self.check_blackjack_and_continue)
    
    def check_blackjack_and_continue(self):
        """检查玩家Blackjack并决定后续流程"""
        if self.game.check_blackjack(self.game.player_hand):
            self.game.player_blackjack = True
            self.status_label.config(text="玩家有Blackjack！")
            upcard = self.game.dealer_hand[0]
            upcard_value = upcard.get_value()
            # 情况1：庄家明牌不是10也不是A → 直接结算，玩家获胜
            if upcard_value not in (10, 11):
                self.after(1000, self.show_showdown)
                return
            # 情况2：庄家明牌是10点 → 摸第二张牌判断是否庄家Blackjack
            elif upcard_value == 10:
                self.game.stage = "dealer_turn"
                self.stage_label.config(text="庄家回合")
                self.game.add_dealer_second_card()
                second_card = self.game.dealer_hand[1]
                second_card_label = self.add_card_to_frame(self.dealer_cards_frame, second_card,
                                                        show_front=False, position=1)
                self.dealer_hidden_card_label = second_card_label

                def after_reveal():
                    if self.game.check_blackjack(self.game.dealer_hand):
                        self.game.dealer_blackjack = True
                        self.update_hand_labels()
                        self.status_label.config(text="双方Blackjack，平局")
                    else:
                        self.game.dealer_blackjack = False
                        self.status_label.config(text="玩家Blackjack获胜！")
                    self.after(1000, self.show_showdown)

                self.flip_card_animation(second_card_label, second_card, callback=after_reveal)
                return
            # 情况3：庄家明牌是A → 走保险流程，然后摸第二张牌
            elif upcard_value == 11:
                self.offer_insurance_for_blackjack()
                return
        else:
            # 玩家无Blackjack，正常进入玩家回合
            self.game.stage = "player_turn"
            self.stage_label.config(text="玩家回合")
            self.show_player_actions()

    def offer_insurance_for_blackjack(self):
        """玩家Blackjack且庄家明牌为A时提供保险"""
        self.game.stage = "insurance"
        self.stage_label.config(text="保险选项")
        self.status_label.config(text="庄家明牌是A，是否购买保险？")
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        insurance_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        insurance_frame.pack(pady=5)
        self.insurance_btn = tk.Button(
            insurance_frame, text="购买保险",
            command=self.take_insurance_for_blackjack,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=10
        )
        self.insurance_btn.pack(side=tk.LEFT, padx=5)
        self.no_insurance_btn = tk.Button(
            insurance_frame, text="不购买",
            command=self.decline_insurance_for_blackjack,
            font=('Arial', 14), bg='#F44336', fg='white', width=10
        )
        self.no_insurance_btn.pack(side=tk.LEFT, padx=5)

    def take_insurance_for_blackjack(self):
        if hasattr(self, 'insurance_btn'):
            self.insurance_btn.config(state=tk.DISABLED)
        if hasattr(self, 'no_insurance_btn'):
            self.no_insurance_btn.config(state=tk.DISABLED)
        insurance_amount = self.game.main_bet / 2
        if self.balance >= insurance_amount:
            self.balance -= insurance_amount
            self.game.insurance_bet = insurance_amount
            self.game.insurance_taken = True
            self.update_balance()
            self.insurance_var.set(str(int(insurance_amount)))
            total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                        self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                        self.game.bust_bet + self.game.hot_3_bet + self.game.lucky_queen_bet +
                        self.game.insurance_bet)
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.status_label.config(text=f"已购买保险 ${self.game.insurance_bet}")
            self.after(1000, self.continue_after_insurance_for_blackjack)
        else:
            messagebox.showerror("错误", "余额不足以购买保险")
            self.decline_insurance_for_blackjack()

    def decline_insurance_for_blackjack(self):
        if hasattr(self, 'insurance_btn'):
            self.insurance_btn.config(state=tk.DISABLED)
        if hasattr(self, 'no_insurance_btn'):
            self.no_insurance_btn.config(state=tk.DISABLED)
        self.game.insurance_taken = False
        self.status_label.config(text="未购买保险")
        self.after(1000, self.continue_after_insurance_for_blackjack)

    def continue_after_insurance_for_blackjack(self):
        """保险决策后，摸庄家第二张牌并结算"""
        self.game.add_dealer_second_card()
        second_card = self.game.dealer_hand[1]
        second_card_label = self.add_card_to_frame(self.dealer_cards_frame, second_card,
                                                show_front=False, position=1)
        self.dealer_hidden_card_label = second_card_label

        def after_reveal():
            if self.game.check_blackjack(self.game.dealer_hand):
                self.game.dealer_blackjack = True
                self.update_hand_labels()
                self.status_label.config(text="庄家Blackjack，双方平局")
            else:
                self.game.dealer_blackjack = False
                self.status_label.config(text="玩家Blackjack获胜！")
            self.after(1000, self.show_showdown)

        self.flip_card_animation(second_card_label, second_card, callback=after_reveal)

    def show_player_actions(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        action_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        action_frame.pack(pady=5)
        self.hit_button = tk.Button(
            action_frame, text="要牌",
            command=self.hit_action,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=7
        )
        self.hit_button.pack(side=tk.LEFT, padx=5)
        self.stand_button = tk.Button(
            action_frame, text="停牌",
            command=self.stand_action,
            font=('Arial', 14), bg='#2196F3', fg='white', width=7
        )
        self.stand_button.pack(side=tk.LEFT, padx=5)
        can_double = (self.balance >= self.game.main_bet and len(self.game.player_hand) == 2)
        self.double_button = tk.Button(
            action_frame, text="加倍",
            command=self.double_action,
            font=('Arial', 14), bg='#FF9800', fg='white', width=7,
            state=tk.NORMAL if can_double else tk.DISABLED
        )
        self.double_button.pack(side=tk.LEFT, padx=5)
        can_surrender = len(self.game.player_hand) == 2
        self.surrender_button = tk.Button(
            action_frame, text="投降",
            command=self.surrender_action,
            font=('Arial', 14), bg='#F44336', fg='white', width=7,
            state=tk.NORMAL if can_surrender else tk.DISABLED
        )
        self.surrender_button.pack(side=tk.LEFT, padx=5)
        self.status_label.config(text="请选择您的操作")
    
    def hit_action(self):
        self.hit_button.config(state=tk.DISABLED)
        self.stand_button.config(state=tk.DISABLED)
        self.surrender_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)
        new_value = self.game.player_hit()
        new_card = self.game.player_hand[-1]
        position = len(self.game.player_hand) - 1
        new_card_label = self.add_card_to_frame(self.player_cards_frame, new_card, show_front=False, position=position)
        self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_hit(new_value))
    
    def after_hit(self, new_value):
        self.update_hand_labels()
        if new_value > 21:
            self.game.player_done = True
            self.status_label.config(text="玩家爆牌！")
            # 不再立即继续，而是直接触发庄家回合（由 dealer_turn 根据条件决定是否发牌）
            self.after(800, self.dealer_turn)
            return
        if new_value == 21:
            self.game.player_done = True
            self.status_label.config(text="玩家达到21点，自动停牌")
            self.after(600, self.dealer_turn)
            return
        self.hit_button.config(state=tk.NORMAL)
        self.stand_button.config(state=tk.NORMAL)
        self.surrender_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)
        self.status_label.config(text="请选择您的操作")
    
    def stand_action(self):
        try:
            self.disable_action_buttons()
        except Exception:
            pass
        self.game.player_done = True
        self.status_label.config(text="玩家停牌")
        self.after(600, self.dealer_turn)
    
    def double_action(self):
        try:
            self.disable_action_buttons()
        except Exception:
            pass
        if self.balance < self.game.main_bet:
            messagebox.showerror("错误", "余额不足以加倍")
            try:
                self.hit_button.config(state=tk.NORMAL)
                self.stand_button.config(state=tk.NORMAL)
            except Exception:
                pass
            return
        self.game.double_extra = self.game.main_bet
        self.balance -= self.game.main_bet
        self.game.main_bet *= 2
        self.main_bet_var.set(self.game.main_bet)
        self.update_balance()
        total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                self.game.bust_bet + self.game.hot_3_bet + self.game.lucky_queen_bet + self.game.insurance_bet)
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        new_value = self.game.player_hit()
        new_card = self.game.player_hand[-1]
        position = len(self.game.player_hand) - 1
        new_card_label = self.add_card_to_frame(self.player_cards_frame, new_card, show_front=False, position=position)
        self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_double(new_value))
    
    def after_double(self, new_value):
        self.update_hand_labels()
        self.game.player_done = True
        if new_value > 21:
            self.status_label.config(text="玩家爆牌（加倍）！")
        else:
            self.status_label.config(text="玩家加倍完成")
        self.after(800, self.dealer_turn)
    
    def surrender_action(self):
        try:
            self.disable_action_buttons()
        except Exception:
            pass
        surrender_amount = 0
        try:
            surrender_amount = self.game.main_bet / 2
        except Exception:
            surrender_amount = 0
        self.balance += surrender_amount
        self.game.main_bet = 0
        try:
            self.main_bet_var.set("投降")
        except Exception:
            pass
        self.update_balance()
        self.game.player_done = True
        self.status_label.config(text="玩家投降，退还一半主注")
        self.after(800, self.show_showdown)
    
    def dealer_turn(self):
        """庄家回合 - 根据玩家爆牌及边注情况决定是否发庄家第二张牌及后续动作"""
        self.game.stage = "dealer_turn"
        self.stage_label.config(text="庄家回合")

        player_value = self.game.get_hand_value(self.game.player_hand)
        player_busted = player_value > 21
        has_bust_bet = self.game.bust_bet > 0
        has_insurance = self.game.insurance_bet > 0

        # 情形1：玩家爆牌 且 无“爆!”边注 且 无“保险”边注 → 不摸庄家第二张牌，直接结算
        if player_busted and not has_bust_bet and not has_insurance:
            self.show_showdown()
            return

        # 其他情况都需要给庄家补发第二张牌
        self.game.add_dealer_second_card()
        second_card = self.game.dealer_hand[1]

        # 在UI上添加第二张牌（背面，位置1）
        second_card_label = self.add_card_to_frame(self.dealer_cards_frame, second_card,
                                                   show_front=False, position=1)
        self.dealer_hidden_card_label = second_card_label

        def after_reveal():
            # 判断庄家是否为Blackjack
            if self.game.check_blackjack(self.game.dealer_hand):
                self.game.dealer_blackjack = True
                self.update_hand_labels()
                # 庄家Blackjack直接结算，不再继续补牌
                self.after(1000, self.show_showdown)
            else:
                self.game.dealer_blackjack = False
                # 情形2：玩家爆牌 + 只有保险（无爆!） → 只摸第二张牌，不继续补牌
                if player_busted and has_insurance and not has_bust_bet:
                    self.after(1000, self.show_showdown)
                else:
                    # 其他情况：正常补牌（玩家未爆牌 或 有爆!边注）
                    self.dealer_hit_loop()

        # 启动翻牌动画
        self.flip_card_animation(second_card_label, second_card, callback=after_reveal)
    
    def dealer_hit_loop(self):
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        self.update_hand_labels()
        if dealer_value < 17:
            self.status_label.config(text="庄家要牌")
            new_value = self.game.dealer_hit()
            new_card = self.game.dealer_hand[-1]
            position = len(self.game.dealer_hand) - 1
            new_card_label = self.add_card_to_frame(self.dealer_cards_frame, new_card, show_front=False, position=position)
            self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_dealer_hit(new_value))
        else:
            self.status_label.config(text="庄家停牌")
            self.after(1000, self.show_showdown)
    
    def after_dealer_hit(self, new_value):
        self.update_hand_labels()
        self.after(100, self.dealer_hit_loop)
    
    def show_showdown(self):
        self.game.stage = "showdown"
        self.stage_label.config(text="结算")
        # 确保庄家所有牌已经翻开（如果之前没翻，可能因条件判断直接过来，需要再检查）
        for w in self.dealer_cards_frame.winfo_children():
            if isinstance(w, tk.Label) and hasattr(w, 'card') and not w.is_face_up:
                # 这种情况极少发生，但为防万一，直接翻牌（无动画）
                w.config(image=self.card_images.get((w.card.suit, w.card.rank), self.back_image))
                w.is_face_up = True
        self._do_showdown()
        
    def _do_showdown(self):
        winnings, details = self.calculate_winnings()
        self.balance += winnings
        self.update_balance()

        for bet_type, widget in self.bet_widgets.items():
            win_amount = details.get(bet_type, 0)
            original_bet = getattr(self.game, f"{bet_type}_bet", 0)
            if win_amount == 0:
                display_text = "0"
                widget.config(bg='white')
            elif win_amount == original_bet:
                display_text = str(int(original_bet))
                widget.config(bg='light blue')
            else:
                display_text = str(int(win_amount))
                widget.config(bg='gold')
            if bet_type == "main":
                self.main_bet_var.set(display_text)
            elif bet_type == "perfect_pair":
                self.perfect_pair_var.set(display_text)
            elif bet_type == "twenty_one_plus_three":
                self.twenty_one_plus_three_var.set(display_text)
            elif bet_type == "royal_match":
                self.royal_match_var.set(display_text)
            elif bet_type == "bust":
                self.bust_var.set(display_text)
            elif bet_type == "hot_3":
                self.hot_3_var.set(display_text)
            elif bet_type == "lucky_queen":
                self.lucky_queen_var.set(display_text)

        player_value = self.game.get_hand_value(self.game.player_hand)
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        status_text = ""
        self.update_hand_labels()
        if self.game.player_blackjack and self.game.dealer_blackjack:
            status_text = "双方Blackjack，和局"
        elif self.game.player_blackjack:
            status_text = "玩家Blackjack胜利！"
        elif self.game.dealer_blackjack:
            if self.game.insurance_taken:
                status_text = "庄家Blackjack，保险支付"
            else:
                status_text = "庄家Blackjack胜利！"
        elif player_value > 21:
            status_text = "玩家爆牌，庄家胜利"
        elif dealer_value > 21:
            status_text = "庄家爆牌，玩家胜利"
        elif player_value > dealer_value:
            status_text = "玩家胜利"
        elif player_value < dealer_value:
            status_text = "庄家胜利"
        else:
            status_text = "和局"
        self.status_label.config(text=status_text)
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        self.show_restart_button()
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def calculate_winnings(self):
        """计算赢得的金额（包含加倍退还）"""
        winnings = 0
        details = {
            "main": 0,
            "perfect_pair": 0,
            "twenty_one_plus_three": 0,
            "royal_match": 0,
            "bust": 0,
            "hot_3": 0,
            "lucky_queen": 0,
            "insurance": 0
        }
        
        player_value = self.game.get_hand_value(self.game.player_hand)
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        
        # 1. 结算主注 + 加倍退还处理
        main_result = 0
        double_refund = 0
        
        # 庄家 Blackjack 且玩家不是 Blackjack 且玩家曾加倍 → 退还加倍金额
        if (self.game.dealer_blackjack and not self.game.player_blackjack 
                and self.game.double_extra > 0):
            double_refund = self.game.double_extra
        
        if self.game.main_bet == 0:  # 投降情况
            main_result = 0
            details["main"] = 0
        elif player_value == 21 and dealer_value == 21:
            player_card_count = len(self.game.player_hand)
            dealer_card_count = len(self.game.dealer_hand)
            if player_card_count == 2 and dealer_card_count == 2:
                main_result = self.game.main_bet
                details["main"] = self.game.main_bet
            elif player_card_count == 2 and dealer_card_count >= 3:
                main_result = self.game.main_bet * 2.5
                details["main"] = main_result
            elif player_card_count >= 3 and dealer_card_count == 2:
                main_result = 0
                details["main"] = 0
            else:
                main_result = self.game.main_bet
                details["main"] = self.game.main_bet
        elif self.game.player_blackjack and not self.game.dealer_blackjack:
            main_result = self.game.main_bet * 2.5
            details["main"] = main_result
        elif self.game.dealer_blackjack and not self.game.player_blackjack:
            main_result = 0
            details["main"] = 0
        elif player_value > 21:
            main_result = 0
            details["main"] = 0
        elif dealer_value > 21:
            main_result = self.game.main_bet * 2
            details["main"] = main_result
        elif player_value > dealer_value:
            main_result = self.game.main_bet * 2
            details["main"] = main_result
        elif player_value < dealer_value:
            main_result = 0
            details["main"] = 0
        else:  # 和局
            main_result = self.game.main_bet
            details["main"] = self.game.main_bet
        
        winnings += main_result + double_refund
        
        # 2. 结算完美对子
        if self.game.perfect_pair_bet > 0:
            pair_result = self.game.check_perfect_pair()
            if pair_result == "perfect":
                win_amount = self.game.perfect_pair_bet * 25
                details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "colored":
                win_amount = self.game.perfect_pair_bet * 12
                details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "mixed":
                win_amount = self.game.perfect_pair_bet * 6
                details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            else:
                details["perfect_pair"] = 0
            winnings += details["perfect_pair"]
        
        # 3. 结算21+3
        if self.game.twenty_one_plus_three_bet > 0:
            twenty_one_result = self.game.check_twenty_one_plus_three()
            if twenty_one_result == "straight_three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 100
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight_flush":
                win_amount = self.game.twenty_one_plus_three_bet * 40
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 30
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight":
                win_amount = self.game.twenty_one_plus_three_bet * 10
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "flush":
                win_amount = self.game.twenty_one_plus_three_bet * 5
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            else:
                details["twenty_one_plus_three"] = 0
            winnings += details["twenty_one_plus_three"]
        
        # 4. 结算皇家同花
        if self.game.royal_match_bet > 0:
            royal_result = self.game.check_royal_match()
            if royal_result == "royal":
                win_amount = self.game.royal_match_bet * 25
                details["royal_match"] = win_amount + self.game.royal_match_bet
            elif royal_result == "suited":
                win_amount = self.game.royal_match_bet * 2.5
                details["royal_match"] = win_amount + self.game.royal_match_bet
            else:
                details["royal_match"] = 0
            winnings += details["royal_match"]
        
        # 5. 结算爆！（玩家 Blackjack 时退还本金）
        if self.game.bust_bet > 0:
            if self.game.player_blackjack:
                details["bust"] = self.game.bust_bet  # Push
            elif dealer_value > 21:
                dealer_card_count = len(self.game.dealer_hand)
                multiplier = {
                    3: 1,
                    4: 2,
                    5: 10,
                    6: 50,
                    7: 100
                }.get(dealer_card_count, 250)
                win_amount = self.game.bust_bet * multiplier
                details["bust"] = win_amount + self.game.bust_bet
            else:
                details["bust"] = 0
            winnings += details["bust"]
        
        # 6. 结算热门3
        if self.game.hot_3_bet > 0:
            hot_3_result = self.game.check_hot_3()
            if hot_3_result == "three_seven_same_suit":
                win_amount = self.game.hot_3_bet * 500
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "three_seven_mixed":
                win_amount = self.game.hot_3_bet * 100
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "twenty_one_same_suit":
                win_amount = self.game.hot_3_bet * 20
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "twenty_one_mixed":
                win_amount = self.game.hot_3_bet * 4
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "twenty":
                win_amount = self.game.hot_3_bet * 2
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "nineteen":
                win_amount = self.game.hot_3_bet * 1
                details["hot_3"] = win_amount + self.game.hot_3_bet
            else:
                details["hot_3"] = 0
            winnings += details["hot_3"]
        
        # 7. 结算幸运女王
        if self.game.lucky_queen_bet > 0:
            lucky_queen_result = self.game.check_lucky_queen()
            if lucky_queen_result == "queens_same_suit_dealer_bj":
                win_amount = self.game.lucky_queen_bet * 1000
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            elif lucky_queen_result == "queens_same_suit":
                win_amount = self.game.lucky_queen_bet * 100
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            elif lucky_queen_result == "same_rank_same_suit":
                win_amount = self.game.lucky_queen_bet * 30
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            elif lucky_queen_result == "same_suit":
                win_amount = self.game.lucky_queen_bet * 10
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            elif lucky_queen_result == "mixed":
                win_amount = self.game.lucky_queen_bet * 4
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            else:
                details["lucky_queen"] = 0
            winnings += details["lucky_queen"]
        
        # 8. 结算保险
        if self.game.insurance_bet > 0:
            if self.game.dealer_blackjack and not self.game.player_blackjack:
                insurance_win = self.game.insurance_bet * 3
                details["insurance"] = insurance_win
                self.insurance_var.set(str(int(insurance_win)))
                self.insurance_display.config(bg='gold')
            else:
                details["insurance"] = 0
                self.insurance_var.set("0")
            winnings += details["insurance"]
        
        return winnings, details

    def reset_bets(self):
        self.main_bet_var.set("0")
        self.perfect_pair_var.set("0")
        self.twenty_one_plus_three_var.set("0")
        self.royal_match_var.set("0")
        self.bust_var.set("0")
        self.hot_3_var.set("0")
        self.lucky_queen_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        for widget in self.bet_widgets.values():
            widget.config(bg='#FFCDD2')
        self.after(500, lambda: [w.config(bg='white') for w in self.bet_widgets.values()])

    def animate_cards_out(self):
        all_card_labels = []
        for widget in self.dealer_cards_frame.winfo_children():
            if isinstance(widget, tk.Label) and hasattr(widget, 'card'):
                all_card_labels.append(widget)
        for widget in self.player_cards_frame.winfo_children():
            if isinstance(widget, tk.Label) and hasattr(widget, 'card'):
                all_card_labels.append(widget)
        if not all_card_labels:
            return
        total_steps = 20
        step_delay = 20
        total_distance = 800
        def move_step(step):
            if step > total_steps:
                for card_label in all_card_labels:
                    try:
                        card_label.destroy()
                    except:
                        pass
                return
            progress = step / total_steps
            eased_progress = 1 - (1 - progress) ** 3
            current_offset = int(total_distance * eased_progress)
            for card_label in all_card_labels:
                try:
                    place_info = card_label.place_info()
                    if place_info:
                        original_x = int(place_info.get('x', 0))
                        card_label.place(x=original_x + current_offset)
                except:
                    pass
            self.after(step_delay, lambda: move_step(step + 1))
        move_step(1)
    
    def show_restart_button(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=lambda: self.reset_game(False),
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=5)
    
    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except:
                pass
            self.auto_reset_timer = None
        self._resetting = True
        for after_id in self.tk.eval('after info').split():
            self.after_cancel(after_id)
        def after_animation():
            self.game.reset_game()
            self.stage_label.config(text="下注阶段")
            self.status_label.config(text="设置下注金额并开始游戏")
            self.player_label.config(text="玩家")
            self.dealer_label.config(text="庄家")
            self.main_bet_var.set("0")
            self.perfect_pair_var.set("0")
            self.twenty_one_plus_three_var.set("0")
            self.royal_match_var.set("0")
            self.bust_var.set("0")
            self.hot_3_var.set("0")
            self.lucky_queen_var.set("0")
            self.insurance_label.pack_forget()
            self.insurance_display.pack_forget()
            self.insurance_var.set("0")
            self.side_bet_all_in_btn.pack(side=tk.LEFT, padx=5)
            for widget in self.bet_widgets.values():
                widget.config(bg='white')
            self.insurance_display.config(bg='white')
            self.active_card_labels = []
            self.dealer_hidden_card_label = None
            self.flipping_cards = []
            self.flip_step = 0
            self.enable_betting_area()
            for widget in self.action_frame.winfo_children():
                widget.destroy()
            start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
            start_button_frame.pack(pady=5)
            self.reset_bets_button = tk.Button(
                start_button_frame, text="重置金额", 
                command=self.reset_bets, font=('Arial', 14),
                bg='#F44336', fg='white', width=10
            )
            self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
            self.reset_bets_button.config(state=tk.NORMAL)
            self.start_button = tk.Button(
                start_button_frame, text="开始游戏", 
                command=self.start_game, font=('Arial', 14),
                bg='#4CAF50', fg='white', width=10
            )
            self.start_button.pack(side=tk.LEFT)
            self.start_button.config(state=tk.NORMAL)
            self.current_bet_label.config(text="本局下注: $0.00")
            self._resetting = False
            if auto_reset:
                self.status_label.config(text="30秒已到，自动开始新游戏")
                self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
            else:
                self.status_label.config(text="设置下注金额并开始游戏")
        self.animate_cards_out()
        self.after(500, after_animation)

def main(initial_balance=10000, username="Guest"):
    app = BlackjackGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: ${final_balance:.2f}")