import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import secrets
import json
import os
import math
import subprocess, sys
import random

# 扑克牌花色和点数 - 包括所有52张牌
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
            return 11  # 初始值，游戏中会调整
        else:
            return int(self.rank)

class Deck:
    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        self.cards = []
        self.generate_deck()
        self.shuffle()
        self.cut_card_position = 60
    
    def generate_deck(self):
        self.cards = [Card(suit, rank) for _ in range(self.num_decks) for suit in SUITS for rank in RANKS]
    
    def shuffle(self):
        """使用shuffle.py洗牌，失败则使用secrets洗牌"""
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
        print(f"使用secrets洗牌完成，剩余{len(self.cards)}张牌")
    
    def deal_card(self):
        if len(self.cards) == 0:
            self.generate_deck()
            self.shuffle()
            self.cut_card_position = 60
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
    
    def needs_reshuffle(self):
        return len(self.cards) <= 60

class BlackjackGame:
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        self.player_hand = []
        self.dealer_hand = []
        self.main_bet = 0
        self.perfect_pair_bet = 0
        self.twenty_one_plus_three_bet = 0
        self.insurance_bet = 0
        self.stage = "betting"
        self.player_done = False
        self.insurance_taken = False
        self.player_blackjack = False
        self.dealer_blackjack = False
        self.dealer_second_card_dealt = False
        self.dealer_needs_to_play = False
        self.dealer_forced_hit_for_insurance = False
        
        self.special_cards = []
        self.special_multiplier = 1
        self.has_special_card = False
    
    def generate_special_offer(self):
        self.special_cards = []
        
        rand_num = random.random() * 100
        if rand_num < 75:
            num_cards = 2
        elif rand_num < 90:
            num_cards = 3
        elif rand_num < 97:
            num_cards = 4
        else:
            num_cards = 5
        
        all_cards = [Card(suit, rank) for suit in SUITS for rank in RANKS]
        self.special_cards = random.sample(all_cards, num_cards)
        
        rand_mult = random.random() * 100
        if rand_mult < 60:
            self.special_multiplier = 2.5
        elif rand_mult < 85:
            self.special_multiplier = 5
        elif rand_mult < 97.5:
            self.special_multiplier = 10
        elif rand_mult < 99.5:
            self.special_multiplier = 25
        else:
            self.special_multiplier = 50
        
        return self.special_cards, self.special_multiplier
    
    def check_special_card_in_hand(self):
        """检查玩家手牌是否含有特殊牌，并更新has_special_card标志"""
        if not self.special_cards:
            self.has_special_card = False
            return False
        
        special_set = {(c.suit, c.rank) for c in self.special_cards}
        self.has_special_card = any((card.suit, card.rank) in special_set for card in self.player_hand)
        return self.has_special_card
    
    def get_special_match_count(self):
        """返回玩家手牌匹配特殊牌的张数（每张玩家牌独立匹配，允许重复匹配）"""
        if not self.special_cards or not self.player_hand:
            return 0
        special_set = {(c.suit, c.rank) for c in self.special_cards}
        return sum(1 for card in self.player_hand if (card.suit, card.rank) in special_set)
    
    def deal_initial_cards(self):
        # 发牌顺序：玩家第一张 -> 庄家一张 -> 玩家第二张
        self.player_hand = [self.deck.deal_card()]   # 玩家第一张
        self.dealer_hand = [self.deck.deal_card()]   # 庄家明牌
        self.player_hand.append(self.deck.deal_card())  # 玩家第二张
        self.check_special_card_in_hand()
    
    def get_hand_value(self, hand):
        total = 0
        num_aces = 0
        for card in hand:
            if card.rank == 'A':
                total += 11
                num_aces += 1
            else:
                total += card.get_value()
        aces_to_adjust = num_aces
        while total > 21 and aces_to_adjust > 0:
            total -= 10
            aces_to_adjust -= 1
        return total
    
    def is_soft_17(self, hand):
        total = 0
        num_aces = 0
        for card in hand:
            if card.rank == 'A':
                total += 11
                num_aces += 1
            else:
                total += card.get_value()
        aces_counted_as_11 = num_aces
        while total > 21 and aces_counted_as_11 > 0:
            total -= 10
            aces_counted_as_11 -= 1
        return (total == 17) and (aces_counted_as_11 > 0)
    
    def player_hit(self):
        card = self.deck.deal_card()
        self.player_hand.append(card)
        if self.special_cards:
            special_set = {(c.suit, c.rank) for c in self.special_cards}
            if (card.suit, card.rank) in special_set:
                self.has_special_card = True
        return self.get_hand_value(self.player_hand)
    
    def dealer_hit(self):
        card = self.deck.deal_card()
        self.dealer_hand.append(card)
        return self.get_hand_value(self.dealer_hand), card
    
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
        
        def is_straight(values):
            if values[2] - values[1] == 1 and values[1] - values[0] == 1:
                return True
            special_straights = [
                [8, 9, 10], [9, 10, 11], [10, 11, 12],
                [11, 12, 13], [12, 13, 14]
            ]
            return values in special_straights
        
        is_flush = len(set(suits)) == 1
        is_straight_result = is_straight(rank_values)
        
        if is_flush and is_straight_result:
            return "straight_flush"
        elif is_flush:
            return "flush"
        elif is_straight_result:
            return "straight"
        else:
            return None

class BlackjackGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("豪赢21点")
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
            "insurance": 0
        }
        self.bet_widgets = {}
        self.flipping_cards = []
        self.flip_step = 0
        self._resetting = False
        self.dealer_hidden_card_label = None
        self.insurance_offered = False
        self.original_main_bet = 0
        
        self.special_cards_frame = None
        self.special_multiplier_label = None
        self.special_card_labels = []
        self.special_card_size = (60, 90)
        
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
        
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club'
        }

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
        
        self.special_card_images = {}
        small_size = self.special_card_size
        
        try:
            back_img_small = back_img_orig.copy().resize(small_size, Image.LANCZOS)
            self.special_card_images["back"] = ImageTk.PhotoImage(back_img_small)
        except:
            self.special_card_images["back"] = ImageTk.PhotoImage(Image.new('RGB', small_size, 'black'))
        
        for suit in SUITS:
            for rank in RANKS:
                if (suit, rank) in self.original_images:
                    try:
                        img_small = self.original_images[(suit, rank)].copy().resize(small_size, Image.LANCZOS)
                        self.special_card_images[(suit, rank)] = ImageTk.PhotoImage(img_small)
                    except:
                        img_orig = Image.new('RGB', small_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 10)
                        except:
                            font = ImageFont.load_default()
                        text_width, text_height = draw.textsize(text, font=font)
                        x = (small_size[0] - text_width) / 2
                        y = (small_size[1] - text_height) / 2
                        draw.text((x, y), text, fill="white", font=font)
                        self.special_card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
    
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
            text="特殊奖励牌翻倍 & 庄家3张牌爆牌主注平局\n庄家手牌16点必须要牌 任何17点停牌", 
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
        
        special_offer_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        special_offer_frame.pack(fill=tk.X, pady=5)

        special_horizontal_frame = tk.Frame(special_offer_frame, bg='#2a4a3c')
        special_horizontal_frame.pack(fill=tk.X, padx=5, pady=5)

        self.special_cards_frame = tk.Frame(special_horizontal_frame, bg='#2a4a3c', width=340)
        self.special_cards_frame.pack(side=tk.LEFT, padx=5)
        self.special_cards_frame.pack_propagate(False)

        multiplier_frame = tk.Frame(special_horizontal_frame, bg='#2a4a3c')
        multiplier_frame.pack(side=tk.RIGHT, padx=(0, 0))

        self.initialize_special_cards()

        self.special_multiplier_label = tk.Label(multiplier_frame, text="倍数", 
                                                font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='#00FF00')
        self.special_multiplier_label.pack()
        
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
        
        tk.Label(first_row_frame, text=" ", bg='#2a4a3c').pack(side=tk.LEFT, padx=10)
        
        twenty_one_plus_three_label = tk.Label(first_row_frame, text="21+3:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        twenty_one_plus_three_label.pack(side=tk.LEFT)
        
        self.twenty_one_plus_three_var = tk.StringVar(value="0")
        self.twenty_one_plus_three_display = tk.Label(first_row_frame, textvariable=self.twenty_one_plus_three_var, font=('Arial', 14), 
                                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.twenty_one_plus_three_display.pack(side=tk.LEFT, padx=5)
        self.twenty_one_plus_three_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("twenty_one_plus_three"))
        self.twenty_one_plus_three_display.bind("<Button-3>", lambda e: self.clear_bet("twenty_one_plus_three"))
        self.bet_widgets["twenty_one_plus_three"] = self.twenty_one_plus_three_display
        
        main_bet_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        main_bet_frame.pack(fill=tk.X, padx=10, pady=3)
        
        main_bet_label = tk.Label(main_bet_frame, text="主注:", font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='white')
        main_bet_label.pack(side=tk.LEFT, padx=2)
        
        self.main_bet_var = tk.StringVar(value="0")
        self.main_bet_display = tk.Label(main_bet_frame, textvariable=self.main_bet_var, font=('Arial', 18, 'bold'), 
                                    bg='white', fg='black', width=8, relief=tk.SUNKEN, padx=5)
        self.main_bet_display.pack(side=tk.LEFT, padx=2)
        self.main_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("main"))
        self.main_bet_display.bind("<Button-3>", lambda e: self.clear_bet("main"))
        self.bet_widgets["main"] = self.main_bet_display
        
        self.insurance_frame = tk.Frame(main_bet_frame, bg='#2a4a3c')
        self.insurance_frame.pack(side=tk.LEFT, padx=15)
        
        self.insurance_label = tk.Label(self.insurance_frame, text="保险:", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.insurance_label.pack(side=tk.LEFT, padx=5)
        
        self.insurance_var = tk.StringVar(value="0")
        self.insurance_display = tk.Label(self.insurance_frame, textvariable=self.insurance_var, font=('Arial', 18), 
                                     bg='#d3d3d3', fg='black', width=5, relief=tk.SUNKEN, padx=3)
        self.insurance_display.pack(side=tk.LEFT, padx=1)
        self.insurance_display.config(state=tk.DISABLED)
        
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
    
    def initialize_special_cards(self):
        for widget in self.special_cards_frame.winfo_children():
            widget.destroy()
        
        self.special_card_labels = []
        
        for i in range(5):
            card_label = tk.Label(self.special_cards_frame, image=self.special_card_images["back"], bg='#2a4a3c')
            card_label.pack(side=tk.LEFT, padx=2)
            self.special_card_labels.append(card_label)
        
        self.special_cards_frame.config(height=90)

    def show_special_offer(self, *args, **kwargs):
        special_cards = None
        multiplier = None

        if len(args) >= 1:
            maybe = args[0]
            if isinstance(maybe, (list, tuple)):
                special_cards = list(maybe)
        if len(args) >= 2:
            multiplier = args[1]

        if "special_cards" in kwargs:
            special_cards = kwargs.get("special_cards")
        if "multiplier" in kwargs:
            multiplier = kwargs.get("multiplier")

        if special_cards is None:
            special_cards = getattr(self.game, "special_cards", []) or []
        if multiplier is None:
            multiplier = getattr(self.game, "special_multiplier", None)

        if not isinstance(special_cards, (list, tuple)):
            special_cards = list(special_cards) if special_cards else []

        try:
            self.game.special_cards = list(special_cards)
        except Exception:
            try:
                self.special_cards = list(special_cards)
            except Exception:
                pass

        multiplier_value = None
        try:
            if multiplier is None:
                multiplier_value = float(getattr(self.game, "special_multiplier", 1.0) or 1.0)
            elif isinstance(multiplier, str):
                s = multiplier.strip()
                if s.lower().endswith("x"):
                    s = s[:-1].strip()
                multiplier_value = float(s)
            else:
                multiplier_value = float(multiplier)
        except Exception:
            try:
                multiplier_value = float(getattr(self.game, "special_multiplier", 1.0) or 1.0)
            except Exception:
                multiplier_value = 1.0

        try:
            self.game.special_multiplier = multiplier_value
        except Exception:
            try:
                self.special_multiplier = multiplier_value
            except Exception:
                pass

        shown = 0
        try:
            if hasattr(self, "special_cards_frame"):
                for widget in self.special_cards_frame.winfo_children():
                    widget.destroy()
        except Exception:
            pass

        self.special_card_labels = []

        max_slots = 5

        for i, card in enumerate(special_cards):
            if shown >= max_slots:
                break
            try:
                card_img = self.special_card_images.get((card.suit, card.rank), self.special_card_images.get("back"))
            except Exception:
                card_img = None
            try:
                if hasattr(self, "special_cards_frame"):
                    if card_img is not None:
                        card_label = tk.Label(self.special_cards_frame, image=card_img, bg=getattr(self, 'bg_color', '#2a4a3c'))
                    else:
                        card_label = tk.Label(self.special_cards_frame, text=f"{getattr(card,'rank','?')}{getattr(card,'suit','?')}", bg=getattr(self, 'bg_color', '#2a4a3c'))
                    card_label.pack(side=tk.LEFT, padx=2)
                    self.special_card_labels.append(card_label)
            except Exception:
                pass
            shown += 1

        for i in range(shown, max_slots):
            try:
                back_img = self.special_card_images.get("back") if hasattr(self, "special_card_images") else None
                if hasattr(self, "special_cards_frame"):
                    if back_img is not None:
                        card_label = tk.Label(self.special_cards_frame, image=back_img, bg=getattr(self, 'bg_color', '#2a4a3c'))
                    else:
                        card_label = tk.Label(self.special_cards_frame, text="背面", bg=getattr(self, 'bg_color', '#2a4a3c'))
                    card_label.pack(side=tk.LEFT, padx=2)
                    self.special_card_labels.append(card_label)
            except Exception:
                pass

        try:
            if hasattr(self, "special_multiplier_label"):
                try:
                    fmult = float(multiplier_value)
                    mult_text = f"{int(fmult)}X" if float(fmult).is_integer() else f"{fmult}X"
                    self.special_multiplier_label.config(text=mult_text, fg='#00FF00')
                except Exception:
                    try:
                        self.special_multiplier_label.config(text=str(multiplier), fg='#00FF00')
                    except Exception:
                        self.special_multiplier_label.config(text="倍数")
        except Exception:
            pass

        try:
            self.update_idletasks()
        except Exception:
            pass

        return {"shown_cards_count": shown}
    
    def clear_bet(self, bet_type):
        if self.game.stage != "betting":
            return
            
        if bet_type == "main":
            self.main_bet_var.set("0")
        elif bet_type == "perfect_pair":
            self.perfect_pair_var.set("0")
        elif bet_type == "twenty_one_plus_three":
            self.twenty_one_plus_three_var.set("0")
        
        widget = self.bet_widgets[bet_type]
        original_color = widget.cget('bg')
        widget.config(bg='#FFCDD2')
        self.after(300, lambda: widget.config(bg=original_color))
    
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
            display_rank = rank
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
    
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("超级21点游戏规则")
        win.geometry("750x650")
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
        canvas.create_window((0, 0), window=content_frame, anchor='nw')

        # ========== 游戏规则文本（基本规则+特殊奖励说明） ==========
        rules_text = (
            "超级21点 游戏规则\n\n"
            "1. 游戏目标: 使手中牌的点数总和尽可能接近21点，但不能超过21点。\n\n"
            "2. 牌值计算:\n"
            "   - 2-10: 牌面值\n"
            "   - J, Q, K: 10点\n"
            "   - A: 1点或11点（自动选择最有利的值）\n\n"
            "3. 游戏流程:\n"
            "   a. 下注阶段: 玩家下主注，可选择下边注（完美对子、21+3）\n"
            "   b. 特殊奖励抽取: 随机抽取2-5张奖励牌和一个倍数（见下方表格）\n"
            "   c. 发牌: 玩家第1张，庄家第1张，玩家第2张\n"
            "   d. 保险: 庄家第一张为A时，可购买保险（赔率2:1）\n"
            "   e. 玩家回合: 要牌、停牌、加倍、投降\n"
            "   f. 庄家回合: 必须补牌至17点或以上\n\n"
            "4. 特殊规则:\n"
            "   - 使用8副标准52张扑克牌\n"
            "   - 剩余60张牌时，本局结束后洗牌\n"
            "   - 庄家3张牌爆牌，主注平局，边注正常结算\n"
            "   - 玩家获胜且手牌含有特殊奖励牌时，主注额外乘以倍数X和匹配张数Y\n"
            "     例如: 主注100，基础获胜200(含本金)，倍数5X，匹配2张，最终=200*5*2=2000"
        )

        tk.Label(content_frame, text=rules_text, font=('微软雅黑', 11),
                bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X)

        # ========== 辅助函数：创建风格统一的支付表 ==========
        def create_pay_table(parent, title, headers, data):
            tk.Label(parent, text=title, font=('微软雅黑', 12, 'bold'),
                    bg='#F0F0F0').pack(anchor='w', padx=10, pady=(10, 0))
            table_frame = tk.Frame(parent, bg='#F0F0F0')
            table_frame.pack(fill=tk.X, padx=20, pady=5)

            # 表头
            for col, h in enumerate(headers):
                tk.Label(table_frame, text=h, font=('微软雅黑', 10, 'bold'),
                        bg='#4B8BBE', fg='white', padx=10, pady=5).grid(
                    row=0, column=col, sticky='nsew', padx=1, pady=1)

            # 数据行
            for r, row_data in enumerate(data, start=1):
                bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
                for c, txt in enumerate(row_data):
                    tk.Label(table_frame, text=txt, font=('微软雅黑', 10),
                            bg=bg, padx=10, pady=5).grid(
                        row=r, column=c, sticky='nsew', padx=1, pady=1)

            for c in range(len(headers)):
                table_frame.columnconfigure(c, weight=1)

        # ========== 特殊奖励牌数量概率表 ==========
        create_pay_table(
            content_frame,
            "特殊奖励牌数量概率",
            ["抽取牌数", "概率"],
            [
                ("2张", "75%"),
                ("3张", "15%"),
                ("4张", "7%"),
                ("5张", "3%"),
            ]
        )

        # ========== 特殊奖励倍数概率表 ==========
        create_pay_table(
            content_frame,
            "特殊奖励倍数概率",
            ["倍数", "概率"],
            [
                ("2.5X", "60%"),
                ("5X", "25%"),
                ("10X", "12.5%"),
                ("50X", "5%"),
                ("100X", "2.5%"),
            ]
        )

        # ========== 完美对子支付表 ==========
        create_pay_table(
            content_frame,
            "完美对子赔率",
            ["类型", "条件", "赔率"],
            [
                ("完美对子", "相同花色和点数", "25:1"),
                ("同色对子", "相同颜色和点数", "12:1"),
                ("混合对子", "相同点数", "6:1"),
            ]
        )

        # ========== 21+3 支付表 ==========
        create_pay_table(
            content_frame,
            "21+3赔率",
            ["类型", "条件", "赔率"],
            [
                ("同花三条", "三张牌同花色且点数相同", "100:1"),
                ("同花顺", "三张牌同花色且点数连续", "40:1"),
                ("三条", "三张牌点数相同", "30:1"),
                ("顺子", "三张牌点数连续", "10:1"),
                ("同花", "三张牌同花色", "5:1"),
            ]
        )

        # 刷新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        # 关闭按钮
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

        # 鼠标滚轮支持
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
            
            if player_value > 21:
                player_text = f"玩家 - {player_value}点，爆牌"
            else:
                player_text = f"玩家 - {player_value}点"
            self.player_label.config(text=player_text)
        
        if self.game.dealer_hand:
            dealer_value = self.game.get_hand_value(self.game.dealer_hand)
            dealer_text = "庄家"
            if self.game.stage == "showdown" or self.game.player_done:
                if self.game.check_blackjack(self.game.dealer_hand) and len(self.game.dealer_hand) == 2:
                    dealer_text = "庄家 - BJ"
                elif dealer_value > 21:
                    dealer_text = f"庄家 - {dealer_value}点，爆牌"
                else:
                    dealer_text = f"庄家 - {dealer_value}点"
            else:
                if self.game.dealer_hand:
                    first_card_value = self.game.dealer_hand[0].get_value()
                    dealer_text = f"庄家 - {first_card_value}点"
            self.dealer_label.config(text=dealer_text)
    
    def disable_action_buttons(self):
        if hasattr(self, 'hit_button'):
            self.hit_button.config(state=tk.DISABLED)
        if hasattr(self, 'stand_button'):
            self.stand_button.config(state=tk.DISABLED)
        if hasattr(self, 'surrender_button'):
            self.surrender_button.config(state=tk.DISABLED)
        if hasattr(self, 'double_button'):
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
        
    def play_shuffle_animation(self, duration_ms=3500, callback=None):
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
            self.win_details = {
                "main": 0,
                "perfect_pair": 0,
                "twenty_one_plus_three": 0,
                "insurance": 0
            }
            self.last_win = 0
            
            self.game.main_bet = int(self.main_bet_var.get())
            self.game.perfect_pair_bet = int(self.perfect_pair_var.get())
            self.game.twenty_one_plus_three_bet = int(self.twenty_one_plus_three_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return

        if self.game.main_bet < 10:
            messagebox.showerror("错误", "主注至少需要10块")
            return

        total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                    self.game.twenty_one_plus_three_bet)

        if self.balance < total_bet:
            messagebox.showerror("错误", "余额不足以支付所有下注！")
            return

        self.disable_betting_area()
        self.last_win_label.config(text="上局获胜: $0.00")

        self.start_button.config(state=tk.DISABLED)
        self.reset_bets_button.config(state=tk.DISABLED)
        
        self.insurance_display.config(bg='#d3d3d3')

        self.original_main_bet = self.game.main_bet

        self.balance -= total_bet
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        need_shuffle = False
        
        if not hasattr(self.game, 'deck') or self.game.deck is None:
            need_shuffle = True
        else:
            if self.game.deck.needs_reshuffle():
                need_shuffle = True

        def continue_after_shuffle():
            self.game.deck = Deck(8)
            self.game.stage = "special_offer"
            self.show_special_offer_stage()

        def continue_without_shuffle():
            if not hasattr(self.game, 'deck') or self.game.deck is None:
                self.game.deck = Deck(8)
            self.game.stage = "special_offer"
            self.show_special_offer_stage()

        if need_shuffle:
            self.play_shuffle_animation(duration_ms=3500, callback=continue_after_shuffle)
        else:
            continue_without_shuffle()
    
    def show_special_offer_stage(self):
        self.stage_label.config(text="特殊奖励")
        self.status_label.config(text="正在抽取特殊奖励牌和倍数...")
        
        special_cards, multiplier = self.game.generate_special_offer()
        
        self.show_special_offer(special_cards, multiplier)
        
        self.after(2000, self.after_special_offer)
    
    def after_special_offer(self):
        """特殊奖励阶段结束后，重置游戏状态（但保留特殊牌）并开始发牌"""
        # 手动重置游戏状态，但不清空 special_cards / special_multiplier
        self.game.player_hand = []
        self.game.dealer_hand = []
        self.game.stage = "dealing"
        self.game.player_done = False
        self.game.insurance_taken = False
        self.game.player_blackjack = False
        self.game.dealer_blackjack = False
        self.game.dealer_second_card_dealt = False
        self.game.dealer_needs_to_play = False
        self.game.dealer_forced_hit_for_insurance = False
        # 注意：不清空 self.game.special_cards 和 self.game.special_multiplier

        # 重新读取下注金额（保证与 UI 一致）
        self.game.main_bet = int(self.main_bet_var.get())
        self.game.perfect_pair_bet = int(self.perfect_pair_var.get())
        self.game.twenty_one_plus_three_bet = int(self.twenty_one_plus_three_var.get())
        self.original_main_bet = self.game.main_bet

        # 清空 UI 牌容器
        for widget in self.dealer_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.player_cards_frame.winfo_children():
            widget.destroy()

        # 发初始牌
        try:
            self.game.deal_initial_cards()
        except Exception as e:
            print(f"发牌失败: {e}")
            messagebox.showerror("错误", "发牌失败，请重新开始游戏")
            return

        if self.game.check_blackjack(self.game.player_hand):
            self.game.player_blackjack = True

        self.stage_label.config(text="发牌中")
        self.status_label.config(text="正在发牌...")

        self.deal_card_sequence()
    
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
        
        if self.game.player_blackjack:
            self.status_label.config(text="玩家Blackjack！")
            self.after(1000, self.handle_player_blackjack)
            return
        
        dealer_upcard = self.game.dealer_hand[0]
        
        if dealer_upcard.rank == 'A':
            self.offer_insurance()
        else:
            player_value = self.game.get_hand_value(self.game.player_hand)
            if player_value > 21:
                self.game.player_done = True
                self.status_label.config(text="玩家爆牌！立即结算边注")
                
                self.immediate_side_bets_settlement()
                
                if self.game.insurance_bet > 0:
                    self.game.dealer_forced_hit_for_insurance = True
                    self.after(1000, self.dealer_turn_for_insurance_only)
                else:
                    self.after(1000, self.show_showdown)
            else:
                self.game.stage = "player_turn"
                self.stage_label.config(text="玩家回合")
                self.show_player_actions()
    
    def handle_player_blackjack(self):
        self.update_hand_labels()
        
        dealer_upcard = self.game.dealer_hand[0]
        dealer_upcard_value = dealer_upcard.get_value()
        
        if dealer_upcard_value == 10 or dealer_upcard.rank in ['J', 'Q', 'K']:
            self.status_label.config(text="庄家补牌一张检查Blackjack")
            self.dealer_hit_for_blackjack_check()
        elif dealer_upcard.rank == 'A':
            self.offer_insurance_for_blackjack()
        else:
            self.settle_player_blackjack_win()
    
    def dealer_hit_for_blackjack_check(self):
        dealer_card2 = self.game.deck.deal_card()
        self.game.dealer_hand.append(dealer_card2)
        
        dealer_card2_label = self.add_card_to_frame(self.dealer_cards_frame, dealer_card2, show_front=False, position=1)
        self.flip_card_animation(dealer_card2_label, dealer_card2, callback=self.after_dealer_hit_for_blackjack)
    
    def after_dealer_hit_for_blackjack(self):
        self.update_hand_labels()
        
        if self.game.check_blackjack(self.game.dealer_hand):
            self.game.dealer_blackjack = True
            self.status_label.config(text="双方Blackjack，主注平局")
            self.settle_blackjack_push()
        else:
            self.settle_player_blackjack_win()
    
    def offer_insurance_for_blackjack(self):
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
            self.insurance_display.config(bg='white')

            total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                    self.game.twenty_one_plus_three_bet + self.game.insurance_bet)

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.status_label.config(text=f"已购买保险 ${self.game.insurance_bet}")
            self.after(1000, self.dealer_hit_after_insurance_for_blackjack)
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
        self.after(1000, self.dealer_hit_after_insurance_for_blackjack)
    
    def dealer_hit_after_insurance_for_blackjack(self):
        dealer_card2 = self.game.deck.deal_card()
        self.game.dealer_hand.append(dealer_card2)
        
        dealer_card2_label = self.add_card_to_frame(self.dealer_cards_frame, dealer_card2, show_front=False, position=1)
        self.flip_card_animation(dealer_card2_label, dealer_card2, callback=self.after_dealer_hit_with_insurance)
    
    def after_dealer_hit_with_insurance(self):
        self.update_hand_labels()
        
        dealer_second_card = self.game.dealer_hand[1]
        if dealer_second_card.get_value() == 10 or dealer_second_card.rank in ['J', 'Q', 'K']:
            self.game.dealer_blackjack = True
            self.status_label.config(text="双方Blackjack，主注平局，保险获胜！")
            self.settle_blackjack_push_with_insurance()
        else:
            self.settle_player_blackjack_win()
    
    def settle_player_blackjack_win(self):
        side_bets_winnings = 0
        side_bets_details = {
            "perfect_pair": 0,
            "twenty_one_plus_three": 0
        }

        # 完美对子结算
        if self.game.perfect_pair_bet > 0:
            pair_result = self.game.check_perfect_pair()
            if pair_result == "perfect":
                win_amount = self.game.perfect_pair_bet * 25
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "colored":
                win_amount = self.game.perfect_pair_bet * 12
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "mixed":
                win_amount = self.game.perfect_pair_bet * 6
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            else:
                side_bets_details["perfect_pair"] = 0
            side_bets_winnings += side_bets_details["perfect_pair"]

        # 21+3 结算
        if self.game.twenty_one_plus_three_bet > 0:
            twenty_one_result = self.game.check_twenty_one_plus_three()
            if twenty_one_result == "straight_three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 100
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight_flush":
                win_amount = self.game.twenty_one_plus_three_bet * 40
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 30
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight":
                win_amount = self.game.twenty_one_plus_three_bet * 10
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "flush":
                win_amount = self.game.twenty_one_plus_three_bet * 5
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            else:
                side_bets_details["twenty_one_plus_three"] = 0
            side_bets_winnings += side_bets_details["twenty_one_plus_three"]

        # 主注结算（Blackjack 1.5倍）
        main_return = self.calculate_blackjack_winnings()
        special_multiplier_result = self.apply_special_card_multiplier(main_return)
        main_return = special_multiplier_result["final_return"]

        if len(self.game.dealer_hand) == 2 and self.game.get_hand_value(self.game.dealer_hand) == 21:
            self.insurance_var.set("0")
            self.insurance_display.config(bg='#d3d3d3')

        # 边注显示与背景更新（赢则金色并显示金额，输则白色并显示0）
        for bet_type, win_amount in side_bets_details.items():
            if win_amount > 0:
                widget = self.bet_widgets[bet_type]
                widget.config(bg='gold')
                if bet_type == "perfect_pair":
                    self.perfect_pair_var.set(str(int(win_amount)))
                elif bet_type == "twenty_one_plus_three":
                    self.twenty_one_plus_three_var.set(str(int(win_amount)))
            else:
                # 未中奖：显示 0，背景白色
                widget = self.bet_widgets[bet_type]
                widget.config(bg='white')
                if bet_type == "perfect_pair":
                    self.perfect_pair_var.set("0")
                elif bet_type == "twenty_one_plus_three":
                    self.twenty_one_plus_three_var.set("0")

        # 主注显示（Blackjack获胜总返还）
        self.main_bet_var.set(str(int(main_return)))
        self.main_bet_display.config(bg='gold')

        # 保险显示重置（玩家 Blackjack 时保险要么已处理，要么未触发，统一置 0 并灰色）
        self.insurance_var.set("0")
        self.insurance_display.config(bg='#d3d3d3')

        total_winnings = main_return + side_bets_winnings
        self.balance += total_winnings
        self.update_balance()
        self.update_hand_labels()

        special_card_info = ""
        if special_multiplier_result["match_count"] > 0:
            special_card_info = f" (特殊牌{special_multiplier_result['multiplier']}X，匹配{special_multiplier_result['match_count']}张牌)"

        self.status_label.config(text=f"玩家Blackjack胜利！{special_card_info}")

        try:
            self.last_win += total_winnings
        except Exception:
            self.last_win = total_winnings
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")

        self.show_restart_button()
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def settle_blackjack_push(self):
        side_bets_winnings = 0
        side_bets_details = {
            "perfect_pair": 0,
            "twenty_one_plus_three": 0
        }
        
        if self.game.perfect_pair_bet > 0:
            pair_result = self.game.check_perfect_pair()
            if pair_result == "perfect":
                win_amount = self.game.perfect_pair_bet * 25
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "colored":
                win_amount = self.game.perfect_pair_bet * 12
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "mixed":
                win_amount = self.game.perfect_pair_bet * 6
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            else:
                side_bets_details["perfect_pair"] = 0
            side_bets_winnings += side_bets_details["perfect_pair"]
        
        if self.game.twenty_one_plus_three_bet > 0:
            twenty_one_result = self.game.check_twenty_one_plus_three()
            if twenty_one_result == "straight_three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 100
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight_flush":
                win_amount = self.game.twenty_one_plus_three_bet * 40
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 30
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight":
                win_amount = self.game.twenty_one_plus_three_bet * 10
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "flush":
                win_amount = self.game.twenty_one_plus_three_bet * 5
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            else:
                side_bets_details["twenty_one_plus_three"] = 0
            side_bets_winnings += side_bets_details["twenty_one_plus_three"]
        
        main_return = self.game.main_bet
        total_return = main_return + side_bets_winnings
        
        self.balance += total_return
        self.update_balance()
        
        self.update_hand_labels()
        
        self.main_bet_var.set(str(int(main_return)))
        self.main_bet_display.config(bg='light blue')
        
        for bet_type, win_amount in side_bets_details.items():
            if win_amount > 0:
                widget = self.bet_widgets[bet_type]
                widget.config(bg='gold')
                if bet_type == "perfect_pair":
                    self.perfect_pair_var.set(str(int(win_amount)))
                elif bet_type == "twenty_one_plus_three":
                    self.twenty_one_plus_three_var.set(str(int(win_amount)))
        
        self.status_label.config(text="双方Blackjack，主注平局")
        
        self.last_win += side_bets_winnings
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
        
        self.show_restart_button()
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
        
    def settle_blackjack_push_with_insurance(self):
        side_bets_winnings = 0
        side_bets_details = {
            "perfect_pair": 0,
            "twenty_one_plus_three": 0
        }

        # 完美对子结算
        if self.game.perfect_pair_bet > 0:
            pair_result = self.game.check_perfect_pair()
            if pair_result == "perfect":
                win_amount = self.game.perfect_pair_bet * 25
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "colored":
                win_amount = self.game.perfect_pair_bet * 12
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "mixed":
                win_amount = self.game.perfect_pair_bet * 6
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            else:
                side_bets_details["perfect_pair"] = 0
            side_bets_winnings += side_bets_details["perfect_pair"]

        # 21+3 结算
        if self.game.twenty_one_plus_three_bet > 0:
            twenty_one_result = self.game.check_twenty_one_plus_three()
            if twenty_one_result == "straight_three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 100
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight_flush":
                win_amount = self.game.twenty_one_plus_three_bet * 40
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 30
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight":
                win_amount = self.game.twenty_one_plus_three_bet * 10
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "flush":
                win_amount = self.game.twenty_one_plus_three_bet * 5
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            else:
                side_bets_details["twenty_one_plus_three"] = 0
            side_bets_winnings += side_bets_details["twenty_one_plus_three"]

        # 主注平局返还
        main_return = self.game.main_bet
        # 保险赢额
        insurance_win = self.game.insurance_bet * 3 if self.game.insurance_bet > 0 else 0
        total_return = main_return + side_bets_winnings + insurance_win

        self.balance += total_return
        self.update_balance()
        self.update_hand_labels()

        # 主注显示
        self.main_bet_var.set(str(int(main_return)))
        self.main_bet_display.config(bg='light blue')

        # 边注显示（赢则金色，输则白色并显示0）
        for bet_type, win_amount in side_bets_details.items():
            widget = self.bet_widgets[bet_type]
            if win_amount > 0:
                widget.config(bg='gold')
                if bet_type == "perfect_pair":
                    self.perfect_pair_var.set(str(int(win_amount)))
                elif bet_type == "twenty_one_plus_three":
                    self.twenty_one_plus_three_var.set(str(int(win_amount)))
            else:
                widget.config(bg='white')
                if bet_type == "perfect_pair":
                    self.perfect_pair_var.set("0")
                elif bet_type == "twenty_one_plus_three":
                    self.twenty_one_plus_three_var.set("0")

        # 保险显示
        if insurance_win > 0:
            self.insurance_var.set(str(int(insurance_win)))
            self.insurance_display.config(bg='gold')
        else:
            self.insurance_var.set("0")
            self.insurance_display.config(bg='#d3d3d3')

        self.status_label.config(text="双方Blackjack，主注平局，保险获胜！")

        self.last_win += (side_bets_winnings + insurance_win)
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")

        self.show_restart_button()
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
        
    def calculate_blackjack_winnings(self):
        bet = float(getattr(self.game, "main_bet", 0) or 0.0)
        base_return = bet * 2.5
        return base_return
    
    def apply_special_card_multiplier(self, base_return):
        """
        应用特殊牌倍数规则：
        - 如果玩家获胜且手牌含有特殊奖励牌，主注额外乘以倍数X和匹配张数Y
        - 只限主注
        """
        if not getattr(self.game, "special_cards", None) or not getattr(self.game, "player_hand", None):
            return {"final_return": base_return, "multiplier": 0, "match_count": 0}
        
        # 使用 get_special_match_count 方法计算匹配张数（允许重复匹配）
        match_count = self.game.get_special_match_count()
        
        try:
            multiplier = float(getattr(self.game, "special_multiplier", 1) or 1.0)
        except Exception:
            multiplier = 1.0
        
        # 应用倍数规则：系数 = multiplier * match_count，当 match_count == 0 时系数为 1
        if match_count > 0:
            coefficient = multiplier * match_count
            final_return = base_return * coefficient
        else:
            final_return = base_return
        
        return {
            "final_return": final_return,
            "multiplier": multiplier,
            "match_count": match_count
        }
    
    def disable_betting_area(self):
        for bet_type, widget in self.bet_widgets.items():
            widget.unbind("<Button-1>")
            widget.unbind("<Button-3>")
        
    def enable_betting_area(self):
        for bet_type, widget in self.bet_widgets.items():
            widget.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            widget.bind("<Button-3>", lambda e, bt=bet_type: self.clear_bet(bt))
            widget.config(bg='white', fg='black')
        
    def immediate_side_bets_settlement(self):
        side_bets_winnings = 0
        side_bets_details = {
            "perfect_pair": 0,
            "twenty_one_plus_three": 0
        }
        
        if self.game.perfect_pair_bet > 0:
            pair_result = self.game.check_perfect_pair()
            if pair_result == "perfect":
                win_amount = self.game.perfect_pair_bet * 25
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "colored":
                win_amount = self.game.perfect_pair_bet * 12
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "mixed":
                win_amount = self.game.perfect_pair_bet * 6
                side_bets_details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            else:
                side_bets_details["perfect_pair"] = 0
            side_bets_winnings += side_bets_details["perfect_pair"]
        
        if self.game.twenty_one_plus_three_bet > 0:
            twenty_one_result = self.game.check_twenty_one_plus_three()
            if twenty_one_result == "straight_three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 100
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight_flush":
                win_amount = self.game.twenty_one_plus_three_bet * 40
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 30
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight":
                win_amount = self.game.twenty_one_plus_three_bet * 10
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "flush":
                win_amount = self.game.twenty_one_plus_three_bet * 5
                side_bets_details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            else:
                side_bets_details["twenty_one_plus_three"] = 0
            side_bets_winnings += side_bets_details["twenty_one_plus_three"]
        
        if side_bets_winnings > 0:
            self.balance += side_bets_winnings
            self.update_balance()
            
            for bet_type, win_amount in side_bets_details.items():
                if win_amount > 0:
                    widget = self.bet_widgets[bet_type]
                    widget.config(bg='gold')
                    if bet_type == "perfect_pair":
                        self.perfect_pair_var.set(str(int(win_amount)))
                    elif bet_type == "twenty_one_plus_three":
                        self.twenty_one_plus_three_var.set(str(int(win_amount)))
            
            self.last_win += side_bets_winnings
            self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
            self.status_label.config(text=f"玩家爆牌！边注赢得${side_bets_winnings:.2f}")
        else:
            self.status_label.config(text="玩家爆牌！边注未中")
    
    def dealer_turn_for_insurance_only(self):
        self.game.stage = "dealer_turn"
        self.stage_label.config(text="庄家检查保险")
        self.status_label.config(text="庄家补一张牌检查保险")

        if len(self.game.dealer_hand) < 2:
            dealer_card2 = self.game.deck.deal_card()
            self.game.dealer_hand.append(dealer_card2)

            self.dealer_hidden_card_label = self.add_card_to_frame(
                self.dealer_cards_frame, dealer_card2, show_front=False, position=1
            )
            self.game.dealer_second_card_dealt = True

            self.flip_card_animation(self.dealer_hidden_card_label, dealer_card2, callback=self.after_insurance_check)
        else:
            self.after(50, self.after_insurance_check)
        
    def after_insurance_check(self):
        self.update_hand_labels()

        if len(self.game.dealer_hand) >= 2:
            dealer_second_card = self.game.dealer_hand[1]
            if dealer_second_card.rank in ['10', 'J', 'Q', 'K']:
                insurance_win = self.game.insurance_bet * 3
                if insurance_win:
                    self.balance += insurance_win
                    self.update_balance()
                    try:
                        self.last_win += insurance_win
                    except Exception:
                        self.last_win = insurance_win
                    try:
                        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
                    except Exception:
                        pass
                    # 显示保险赢额并改为金色
                    self.insurance_var.set(str(int(insurance_win)))
                    self.insurance_display.config(bg='gold')

                self.win_details['insurance'] = insurance_win
                self.game.insurance_bet = 0
                self.game.insurance_taken = False
                self.status_label.config(text="庄家第二张牌是10/J/Q/K，保险获胜！")
            else:
                # 保险失败：显示 0，背景恢复灰色
                self.insurance_var.set("0")
                self.insurance_display.config(bg='#d3d3d3')
                self.status_label.config(text="庄家第二张牌不是10/J/Q/K，保险失败")

        self.game.dealer_forced_hit_for_insurance = False
        self.after(1000, self.show_showdown)
    
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
            self.insurance_display.config(bg='white')

            total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                    self.game.twenty_one_plus_three_bet + self.game.insurance_bet)

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.status_label.config(text=f"已购买保险 ${self.game.insurance_bet}")
            self.after(1000, self.check_player_actions)
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
        self.after(1000, self.check_player_actions)
    
    def check_player_actions(self):
        player_value = self.game.get_hand_value(self.game.player_hand)
        if player_value > 21:
            self.game.player_done = True
            self.status_label.config(text="玩家爆牌！立即结算边注")
            
            self.immediate_side_bets_settlement()
            
            if self.game.insurance_bet > 0:
                self.game.dealer_forced_hit_for_insurance = True
                self.after(1000, self.dealer_turn_for_insurance_only)
            else:
                self.after(1000, self.show_showdown)
        else:
            self.game.stage = "player_turn"
            self.stage_label.config(text="玩家回合")
            self.show_player_actions()
    
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
        
        can_double = (self.balance >= self.game.main_bet and 
                     len(self.game.player_hand) == 2)
        
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
            self.status_label.config(text="玩家爆牌！立即结算边注")
            
            self.immediate_side_bets_settlement()
            
            if self.game.insurance_bet > 0:
                self.game.dealer_forced_hit_for_insurance = True
                self.after(1000, self.dealer_turn_for_insurance_only)
            else:
                self.after(1000, self.show_showdown)
            return

        if new_value == 21:
            self.game.player_done = True
            self.status_label.config(text="玩家达到21点，自动停牌")
            
            needs_dealer_action = True
            
            if self.game.insurance_bet > 0:
                needs_dealer_action = True
                self.game.dealer_forced_hit_for_insurance = True
            
            if needs_dealer_action:
                self.after(600, self.dealer_turn)
            else:
                self.after(600, self.show_showdown)
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

        self.balance -= self.game.main_bet
        self.game.main_bet *= 2
        self.main_bet_var.set(self.game.main_bet)
        self.update_balance()

        total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                self.game.twenty_one_plus_three_bet + self.game.insurance_bet)

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
            self.status_label.config(text="玩家爆牌（加倍）！立即结算边注")
            
            self.immediate_side_bets_settlement()
            
            if self.game.insurance_bet > 0:
                self.game.dealer_forced_hit_for_insurance = True
                self.after(1000, self.dealer_turn_for_insurance_only)
            else:
                self.after(1000, self.show_showdown)
        else:
            self.status_label.config(text="玩家加倍完成")
            
            needs_dealer_action = True
            
            if self.game.insurance_bet > 0:
                needs_dealer_action = True
                self.game.dealer_forced_hit_for_insurance = True
            
            if needs_dealer_action:
                self.after(800, self.dealer_turn)
            else:
                self.after(800, self.show_showdown)

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

        try:
            self.last_win += surrender_amount
        except Exception:
            self.last_win = surrender_amount
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")

        self.game.main_bet = 0

        try:
            self.main_bet_var.set("投降")
        except Exception:
            pass

        self.update_balance()
        self.game.player_done = True
        self.status_label.config(text="玩家投降，退还一半主注")

        if self.game.insurance_bet > 0:
            self.status_label.config(text="玩家投降，庄家行动.")
            self.game.dealer_forced_hit_for_insurance = True
            self.after(800, self.dealer_turn_for_insurance_only)
        else:
            self.after(800, self.show_showdown)
    
    def dealer_turn(self):
        self.game.stage = "dealer_turn"
        self.stage_label.config(text="庄家回合")

        if len(self.game.dealer_hand) < 2:
            self.status_label.config(text="庄家要牌")
            dealer_card2 = self.game.deck.deal_card()
            self.game.dealer_hand.append(dealer_card2)

            self.dealer_hidden_card_label = self.add_card_to_frame(
                self.dealer_cards_frame, dealer_card2, show_front=False, position=1
            )
            self.game.dealer_second_card_dealt = True

            self.flip_card_animation(self.dealer_hidden_card_label, dealer_card2, callback=self.after_reveal_dealer_card)
        else:
            self.after(50, self.after_reveal_dealer_card)
        
    def after_reveal_dealer_card(self):
        self.update_hand_labels()

        if getattr(self.game, "dealer_forced_hit_for_insurance", False):
            if len(self.game.dealer_hand) >= 2:
                dealer_second_card = self.game.dealer_hand[1]
                if dealer_second_card.get_value() == 10:
                    insurance_win = self.game.insurance_bet * 3
                    if insurance_win:
                        self.balance += insurance_win
                        self.update_balance()
                        try:
                            self.last_win += insurance_win
                        except Exception:
                            self.last_win = insurance_win
                        try:
                            self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
                        except Exception:
                            pass
                        # 显示保险赢额并改为金色
                        self.insurance_var.set(str(int(insurance_win)))
                        self.insurance_display.config(bg='gold')

                    self.win_details['insurance'] = insurance_win
                    self.game.insurance_bet = 0
                    self.game.insurance_taken = False
                    self.status_label.config(text="庄家第二张牌是10/J/Q/K，保险获胜！")
                else:
                    # 保险失败：显示 0，背景恢复灰色
                    self.insurance_var.set("0")
                    self.insurance_display.config(bg='#d3d3d3')
                    self.status_label.config(text="庄家第二张牌不是10/J/Q/K，保险失败")
            self.game.dealer_forced_hit_for_insurance = False

        if len(self.game.dealer_hand) == 2 and self.game.check_blackjack(self.game.dealer_hand):
            self.game.dealer_blackjack = True
            self.update_hand_labels()
            self.status_label.config(text="庄家Blackjack！")

            if hasattr(self, 'original_main_bet') and getattr(self, 'original_main_bet', 0) > 0 and self.game.main_bet > self.original_main_bet:
                double_amount = self.game.main_bet - self.original_main_bet
                if double_amount:
                    self.balance += double_amount
                    self.update_balance()
                    try:
                        self.last_win += double_amount
                    except Exception:
                        self.last_win = double_amount
                    try:
                        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
                    except Exception:
                        pass
                self.game.main_bet = self.original_main_bet
                self.main_bet_var.set(str(int(self.game.main_bet)))
                self.status_label.config(text=f"庄家Blackjack，退还加倍部分 ${double_amount}")

            self.after(800, self.show_showdown)
            return

        if getattr(self.game, "dealer_needs_to_play", False):
            self.after(10, self.dealer_hit_loop)
            return

        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        need_hit = dealer_value < 17

        if need_hit:
            self.status_label.config(text="庄家要牌")
            self.after(10, self.dealer_hit_loop)
        else:
            self.status_label.config(text="庄家停牌")
            self.after(800, self.show_showdown)
            
    def dealer_hit_loop(self):
        self.update_hand_labels()

        dealer_value = self.game.get_hand_value(self.game.dealer_hand)

        need_hit = dealer_value < 17

        if need_hit:
            self.status_label.config(text=f"庄家要牌")
            new_value, new_card = self.game.dealer_hit()

            position = len(self.game.dealer_hand) - 1
            new_card_label = self.add_card_to_frame(self.dealer_cards_frame, new_card, show_front=False, position=position)

            self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_dealer_hit(new_value))
        else:
            self.status_label.config(text=f"庄家停牌")
            self.after(800, self.show_showdown)
    
    def after_dealer_hit(self, new_value):
        self.update_hand_labels()
        self.after(100, self.dealer_hit_loop)
    
    def show_showdown(self):
        self.game.stage = "showdown"
        self.stage_label.config(text="结算")
        
        self.reveal_dealer_second_card_no_animation()
        
        self.after(500, self._do_showdown)
    
    def reveal_dealer_second_card_no_animation(self):
        if len(self.game.dealer_hand) >= 2:
            dealer_card_labels = [w for w in self.dealer_cards_frame.winfo_children() if isinstance(w, tk.Label)]
            if dealer_card_labels and len(dealer_card_labels) > 1:
                second_card_label = dealer_card_labels[1]
                dealer_second_card = self.game.dealer_hand[1]
                
                if hasattr(second_card_label, 'is_face_up') and not second_card_label.is_face_up:
                    second_card_label.config(image=self.card_images.get((dealer_second_card.suit, dealer_second_card.rank), self.back_image))
                    second_card_label.is_face_up = True

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

        player_value = self.game.get_hand_value(self.game.player_hand)
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        dealer_card_count = len(self.game.dealer_hand)

        status_text = ""
        
        self.update_hand_labels()
        
        special_card_info = ""
        special_multiplier_result = self.apply_special_card_multiplier(0)
        
        if special_multiplier_result["match_count"] > 0:
            special_card_info = f" (特殊牌{special_multiplier_result['multiplier']}X，匹配{special_multiplier_result['match_count']}张牌)"
        
        if dealer_card_count == 3 and dealer_value > 21:
            status_text = f"庄家3张牌爆牌，主注平局"
        elif self.game.main_bet == 0:
            status_text = "玩家投降"
        elif self.game.player_blackjack:
            status_text = f"玩家Blackjack胜利！{special_card_info}"
        elif self.game.dealer_blackjack:
            if self.game.insurance_taken:
                status_text = "庄家Blackjack，保险支付"
            else:
                status_text = "庄家Blackjack胜利！"
        elif player_value > 21:
            status_text = "玩家爆牌，庄家胜利"
        elif dealer_value > 21:
            if dealer_card_count == 3:
                status_text = f"庄家3张牌爆牌，主注平局"
            else:
                status_text = f"庄家爆牌，玩家胜利{special_card_info}"
        elif player_value > dealer_value:
            status_text = f"玩家胜利{special_card_info}"
        elif player_value < dealer_value:
            status_text = "庄家胜利"
        else:
            status_text = f"和局"

        self.status_label.config(text=status_text)

        self.last_win += winnings
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")

        self.show_restart_button()
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def show_restart_button(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=lambda: self.reset_game(False),
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=5)

    def calculate_winnings(self):
        winnings = 0.0
        details = {"main": 0.0, "perfect_pair": 0.0, "twenty_one_plus_three": 0.0, "insurance": 0.0}

        bet = float(getattr(self.game, "main_bet", 0) or 0.0)
        player_value = self.game.get_hand_value(self.game.player_hand) if self.game.player_hand else 0
        dealer_value = self.game.get_hand_value(self.game.dealer_hand) if self.game.dealer_hand else 0
        dealer_card_count = len(self.game.dealer_hand) if self.game.dealer_hand else 0

        main_result = 0.0

        if bet == 0:
            main_result = 0.0
            details["main"] = 0.0

        elif self.game.player_blackjack and self.game.dealer_blackjack:
            main_result = bet
            details["main"] = main_result

        elif self.game.player_blackjack and not self.game.dealer_blackjack:
            base_return = bet * 2.5
            special_multiplier_result = self.apply_special_card_multiplier(base_return)
            main_result = special_multiplier_result["final_return"]
            details["main"] = main_result

        elif self.game.dealer_blackjack and not self.game.player_blackjack:
            main_result = 0.0
            details["main"] = 0.0

        else:
            if player_value > 21:
                main_result = 0.0
                details["main"] = 0.0

            elif dealer_value > 21:
                if dealer_card_count == 3:
                    main_result = bet
                    details["main"] = main_result
                else:
                    base_return = bet * 2.0
                    special_multiplier_result = self.apply_special_card_multiplier(base_return)
                    main_result = special_multiplier_result["final_return"]
                    details["main"] = main_result

            else:
                if player_value > dealer_value:
                    base_return = bet * 2.0
                    special_multiplier_result = self.apply_special_card_multiplier(base_return)
                    main_result = special_multiplier_result["final_return"]
                    details["main"] = main_result
                elif player_value < dealer_value:
                    main_result = 0.0
                    details["main"] = 0.0
                else:
                    main_result = bet
                    details["main"] = main_result

        winnings += main_result

        if getattr(self.game, "perfect_pair_bet", 0) > 0:
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
                details["perfect_pair"] = 0.0
            winnings += details["perfect_pair"]

        if getattr(self.game, "twenty_one_plus_three_bet", 0) > 0:
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
                details["twenty_one_plus_three"] = 0.0
            winnings += details["twenty_one_plus_three"]

        if getattr(self.game, "insurance_bet", 0) > 0:
            if self.game.dealer_blackjack:
                insurance_win = self.game.insurance_bet * 3
                details["insurance"] = insurance_win
                winnings += insurance_win
            else:
                details["insurance"] = 0.0

        return winnings, details

    def reset_bets(self):
        self.main_bet_var.set("0")
        self.perfect_pair_var.set("0")
        self.twenty_one_plus_three_var.set("0")
        
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
            
            self.win_details = {
                "main": 0,
                "perfect_pair": 0,
                "twenty_one_plus_three": 0,
                "insurance": 0
            }
            
            self.last_win = 0
            self.last_win_label.config(text="上局获胜: $0.00")
            
            self.stage_label.config(text="下注阶段")
            self.status_label.config(text="设置下注金额并开始游戏")
            
            self.player_label.config(text="玩家")
            self.dealer_label.config(text="庄家")
            
            self.main_bet_var.set("0")
            self.perfect_pair_var.set("0")
            self.twenty_one_plus_three_var.set("0")
            
            self.insurance_var.set("0")
            self.insurance_display.config(bg='#d3d3d3')
            
            for widget in self.bet_widgets.values():
                widget.config(bg='white')
            self.insurance_display.config(bg='#d3d3d3')
            
            self.initialize_special_cards()
            self.special_multiplier_label.config(text="倍数")
            
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