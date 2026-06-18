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
        self.main_bet_player = 0      # 主注(玩家)
        self.main_bet_dealer = 0      # 主注(庄家)
        self.super_pair_bet = 0
        self.nuclear_bomb_bet = 0
        self.super_tie_bet = 0
        self.sweet_seventeen_bet = 0
        self.stage = "betting"
        self.player_done = False
        self.insurance_bet = 0
        self.insurance_taken = False
        self.player_blackjack = False
        self.dealer_blackjack = False
        self.double_extra = 0
        self.dealer_second_dealt = False
        self.active_main_bet = None     # 'player' 或 'dealer'
    
    def deal_initial_cards(self):
        self.player_hand = [self.deck.deal_card()]
        self.dealer_hand = [self.deck.deal_card()]
        self.player_hand.append(self.deck.deal_card())
        self.dealer_second_dealt = False
    
    def add_dealer_second_card(self):
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
    
    def is_soft_17(self, hand):
        value = sum(card.get_value() for card in hand)
        if value != 17:
            return False
        num_aces = sum(1 for card in hand if card.rank == 'A')
        return num_aces > 0
    
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
    
    def check_super_pair(self):
        """返回: 'both_pair_perfect', 'both_pair', 'single_perfect', 'single_pair', None"""
        def is_perfect_pair(card1, card2):
            return card1.rank == card2.rank and card1.suit == card2.suit
        def is_pair(card1, card2):
            return card1.rank == card2.rank
        player_pair = None
        if len(self.player_hand) >= 2:
            if is_perfect_pair(self.player_hand[0], self.player_hand[1]):
                player_pair = 'perfect'
            elif is_pair(self.player_hand[0], self.player_hand[1]):
                player_pair = 'pair'
        dealer_pair = None
        if len(self.dealer_hand) >= 2:
            if is_perfect_pair(self.dealer_hand[0], self.dealer_hand[1]):
                dealer_pair = 'perfect'
            elif is_pair(self.dealer_hand[0], self.dealer_hand[1]):
                dealer_pair = 'pair'
        if player_pair == 'perfect' and dealer_pair == 'perfect':
            return 'both_pair_perfect'
        if player_pair and dealer_pair:
            return 'both_pair'
        if player_pair == 'perfect' or dealer_pair == 'perfect':
            return 'single_perfect'
        if player_pair or dealer_pair:
            return 'single_pair'
        return None
    
    def check_nuclear_bomb(self):
        player_bust = self.get_hand_value(self.player_hand) > 21
        dealer_bust = self.get_hand_value(self.dealer_hand) > 21
        if player_bust and dealer_bust:
            total_cards = len(self.player_hand) + len(self.dealer_hand)
            return total_cards
        return None
    
    def check_super_tie(self):
        player_val = self.get_hand_value(self.player_hand)
        dealer_val = self.get_hand_value(self.dealer_hand)
        if player_val != dealer_val:
            return None
        if player_val > 21:
            return 'both_bust'
        if self.check_blackjack(self.player_hand) and self.check_blackjack(self.dealer_hand):
            return 'blackjack_tie'
        if player_val == 20:
            return 'twenty_tie'
        if player_val in (17,18,19):
            return 'seventeen_eighteen_nineteen_tie'
        return 'other_tie'
    
    def check_sweet_seventeen(self, action):
        if action == 'hard17_stop':
            return 'hard17_stop'
        if action == 'soft17_hit':
            return 'soft17_hit'
        if action == 'soft17_stop':
            return 'soft17_stop'
        return None

class BlackjackGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("双向21点")
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
        self.last_bet = None
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.win_details = {
            "main_player": 0, "main_dealer": 0, "super_pair": 0,
            "nuclear_bomb": 0, "super_tie": 0, "sweet_seventeen": 0, "insurance": 0
        }
        self.bet_widgets = {}
        self.flipping_cards = []
        self.flip_step = 0
        self._resetting = False
        self.dealer_hidden_card_label = None
        self.insurance_offered = False
        self.active_main_bet = None
        self.sweet_seventeen_action = None
        
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
        
        if bet_type == "main_player":
            if self.active_main_bet is not None and self.active_main_bet != 'player':
                return
            current = int(self.main_player_var.get())
            new_value = current + chip_value
            if new_value > 25000:
                new_value = 25000
                messagebox.showwarning("下注限制", f"主注(玩家)上限为25000，已自动调整")
            self.main_player_var.set(str(int(new_value)))
            if int(new_value) > 0:
                self.set_active_main_bet('player')
            else:
                if self.active_main_bet == 'player':
                    self.set_active_main_bet(None)
        elif bet_type == "main_dealer":
            if self.active_main_bet is not None and self.active_main_bet != 'dealer':
                return
            current = int(self.main_dealer_var.get())
            new_value = current + chip_value
            if new_value > 25000:
                new_value = 25000
                messagebox.showwarning("下注限制", f"主注(庄家)上限为25000，已自动调整")
            self.main_dealer_var.set(str(int(new_value)))
            if int(new_value) > 0:
                self.set_active_main_bet('dealer')
            else:
                if self.active_main_bet == 'dealer':
                    self.set_active_main_bet(None)
        elif bet_type == "super_pair":
            if self.active_main_bet != 'dealer':
                return
            current = int(self.super_pair_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"超级对子上限为2500，已自动调整")
            self.super_pair_var.set(str(int(new_value)))
        elif bet_type == "nuclear_bomb":
            if self.active_main_bet != 'dealer':
                return
            current = int(self.nuclear_bomb_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"核爆！上限为2500，已自动调整")
            self.nuclear_bomb_var.set(str(int(new_value)))
        elif bet_type == "super_tie":
            if self.active_main_bet != 'player':
                return
            current = int(self.super_tie_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"超级平局上限为2500，已自动调整")
            self.super_tie_var.set(str(int(new_value)))
        elif bet_type == "sweet_seventeen":
            if self.active_main_bet != 'player':
                return
            current = int(self.sweet_seventeen_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"甜蜜17上限为2500，已自动调整")
            self.sweet_seventeen_var.set(str(int(new_value)))
    
    def set_active_main_bet(self, which):
        self.active_main_bet = which
        # 更新主注(玩家)区域
        if which == 'player':
            self.main_player_display.config(bg='white', state='normal')
            self.main_player_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("main_player"))
            self.main_player_display.bind("<Button-3>", lambda e: self.clear_bet("main_player"))
            # 主注(庄家)禁用，并用保险区域替换
            self.main_dealer_frame.pack_forget()
            self.insurance_frame.pack(side=tk.LEFT, padx=2)
            self.main_dealer_display.config(bg='#C4C4C4')
            self.main_dealer_display.unbind("<Button-1>")
            self.main_dealer_display.unbind("<Button-3>")
            self.info_label.config(
                text="庄家软17点必须补牌 黑杰克支付3:2\n保险支付2:1 允许投降输一半"
            )
        elif which == 'dealer':
            self.main_dealer_display.config(bg='white', state='normal')
            self.main_dealer_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("main_dealer"))
            self.main_dealer_display.bind("<Button-3>", lambda e: self.clear_bet("main_dealer"))
            self.insurance_frame.pack_forget()
            self.main_dealer_frame.pack(side=tk.LEFT, padx=2)
            self.main_player_display.config(bg='#C4C4C4')
            self.main_player_display.unbind("<Button-1>")
            self.main_player_display.unbind("<Button-3>")
            self.info_label.config(
                text="玩家和庄家软17点必须补牌 黑杰克支付3:2\n玩家爆牌庄家17点 或 双方爆牌，主注平局"
            )
        else:
            # 无激活，两个主注都可输入
            self.main_player_display.config(bg='white')
            self.main_dealer_display.config(bg='white')
            self.main_player_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("main_player"))
            self.main_player_display.bind("<Button-3>", lambda e: self.clear_bet("main_player"))
            self.main_dealer_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("main_dealer"))
            self.main_dealer_display.bind("<Button-3>", lambda e: self.clear_bet("main_dealer"))
            self.insurance_frame.pack_forget()
            self.main_dealer_frame.pack(side=tk.LEFT, padx=2)
            self.info_label.config(
                text="庄家软17点必须补牌 黑杰克支付3:2\n主注选择玩家或庄家以解锁对应的边注"
            )
        self._update_side_bets_state()
    
    def _update_side_bets_state(self):
        # 根据激活主注设置边注启用/禁用背景
        if self.active_main_bet == 'player':
            # 超级对子、核爆！禁用
            self.super_pair_display.config(bg='#C4C4C4', fg='black')
            self.nuclear_bomb_display.config(bg='#C4C4C4', fg='black')
            self.super_pair_display.unbind("<Button-1>")
            self.super_pair_display.unbind("<Button-3>")
            self.nuclear_bomb_display.unbind("<Button-1>")
            self.nuclear_bomb_display.unbind("<Button-3>")
            # 超级平局、甜蜜17启用
            self.super_tie_display.config(bg='white', fg='black')
            self.sweet_seventeen_display.config(bg='white', fg='black')
            self.super_tie_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("super_tie"))
            self.super_tie_display.bind("<Button-3>", lambda e: self.clear_bet("super_tie"))
            self.sweet_seventeen_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("sweet_seventeen"))
            self.sweet_seventeen_display.bind("<Button-3>", lambda e: self.clear_bet("sweet_seventeen"))
        elif self.active_main_bet == 'dealer':
            # 超级对子、核爆！启用
            self.super_pair_display.config(bg='white', fg='black')
            self.nuclear_bomb_display.config(bg='white', fg='black')
            self.super_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("super_pair"))
            self.super_pair_display.bind("<Button-3>", lambda e: self.clear_bet("super_pair"))
            self.nuclear_bomb_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("nuclear_bomb"))
            self.nuclear_bomb_display.bind("<Button-3>", lambda e: self.clear_bet("nuclear_bomb"))
            # 超级平局、甜蜜17禁用
            self.super_tie_display.config(bg='#C4C4C4', fg='black')
            self.sweet_seventeen_display.config(bg='#C4C4C4', fg='black')
            self.super_tie_display.unbind("<Button-1>")
            self.super_tie_display.unbind("<Button-3>")
            self.sweet_seventeen_display.unbind("<Button-1>")
            self.sweet_seventeen_display.unbind("<Button-3>")
        else:
            # 无主注，所有边注禁用
            for disp in [self.super_pair_display, self.nuclear_bomb_display, self.super_tie_display, self.sweet_seventeen_display]:
                disp.config(bg='#C4C4C4', fg='black')
                disp.unbind("<Button-1>")
                disp.unbind("<Button-3>")
    
    def clear_bet(self, bet_type):
        if self.game.stage != "betting":
            return
        if bet_type == "main_player":
            self.main_player_var.set("0")
            if self.active_main_bet == 'player':
                self.set_active_main_bet(None)
        elif bet_type == "main_dealer":
            self.main_dealer_var.set("0")
            if self.active_main_bet == 'dealer':
                self.set_active_main_bet(None)
        elif bet_type == "super_pair":
            self.super_pair_var.set("0")
        elif bet_type == "nuclear_bomb":
            self.nuclear_bomb_var.set("0")
        elif bet_type == "super_tie":
            self.super_tie_var.set("0")
        elif bet_type == "sweet_seventeen":
            self.sweet_seventeen_var.set("0")
        widget = self.bet_widgets[bet_type]
        original_color = widget.cget('bg')
        widget.config(bg='#FFCDD2')
        self.after(300, lambda: widget.config(bg=original_color))
    
    def _build_action_buttons(self):
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
        self.repeat_bet_btn = tk.Button(
            start_button_frame, text="重复上局下注", 
            command=self.apply_last_bet, font=('Arial', 14),
            bg='#4A90E2', fg='white', activebackground='#3A7BC8', width=12,
            state=tk.NORMAL if self.last_bet is not None else tk.DISABLED
        )
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
    
    def apply_last_bet(self):
        if self.last_bet is None:
            self.repeat_bet_btn.config(state=tk.DISABLED)
            return
        # 恢复金额
        self.main_player_var.set(str(self.last_bet.get("main_player", 0)))
        self.main_dealer_var.set(str(self.last_bet.get("main_dealer", 0)))
        self.super_pair_var.set(str(self.last_bet.get("super_pair", 0)))
        self.nuclear_bomb_var.set(str(self.last_bet.get("nuclear_bomb", 0)))
        self.super_tie_var.set(str(self.last_bet.get("super_tie", 0)))
        self.sweet_seventeen_var.set(str(self.last_bet.get("sweet_seventeen", 0)))
        # 根据金额重新激活主注
        if int(self.main_player_var.get()) > 0:
            self.set_active_main_bet('player')
        elif int(self.main_dealer_var.get()) > 0:
            self.set_active_main_bet('dealer')
        else:
            self.set_active_main_bet(None)
        # 闪烁绿色提示
        for widget in self.bet_widgets.values():
            original_color = widget.cget('bg')
            widget.config(bg='#C8E6C9')
            self.after(300, lambda w=widget, c=original_color: w.config(bg=c))
        # 两个主注的背景恢复（已在 set_active_main_bet 中处理）
    
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=20, width=600, height=250)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.info_label = tk.Label(
            table_canvas, 
            text="庄家软17点必须补牌 黑杰克支付3:2\n主注选择玩家或庄家以解锁对应的边注", 
            font=('Arial', 22), 
            bg='#35654d', 
            fg='#FFD700'
        )
        self.info_label.update_idletasks()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        label_width = self.info_label.winfo_width()
        center_x = (canvas_width - label_width) // 2
        self.info_label.place(x=center_x + 355, y=280, anchor='n')
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=365, width=600, height=250)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=450, padx=10, pady=5)
        control_frame.pack_propagate(False)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        self.balance_label = tk.Label(
            info_frame, text=f"余额: ${self.balance:.2f}",
            font=('Arial', 18), bg='#2a4a3c', fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=5)
        self.stage_label = tk.Label(
            info_frame, text="下注阶段",
            font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='#FFD700'
        )
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=5)
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        chip_configs = [
            ('$10', '#ffa500', 'black'), ("$25", '#00ff00', 'black'), ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'), ("$1K", '#ffffff', 'black'), ("$2.5K", '#ff0000', 'white'),
        ]
        self.chip_buttons = []
        for text, bg_color, fg_color in chip_configs:
            chip_canvas = tk.Canvas(chip_row, width=57, height=57, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 55, 55, fill=bg_color, outline='black')
            chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
        self.select_chip("$10")
        minmax_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        minmax_frame.pack(fill=tk.X, pady=5)
        header_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5,0))
        tk.Label(header_frame, text="主注最低", font=('Arial',12,'bold'), bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="主注最高", font=('Arial',12,'bold'), bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="边注最高", font=('Arial',12,'bold'), bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0,5))
        tk.Label(value_frame, text="$10", font=('Arial',12,'bold'), bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$25,000", font=('Arial',12,'bold'), bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial',12,'bold'), bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)

        # 第一行：超级对子 + 核爆！
        first_row = tk.Frame(bet_frame, bg='#2a4a3c')
        first_row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(first_row, text="超级对子:", font=('Arial',14), bg='#2a4a3c', fg="white").pack(side=tk.LEFT)
        self.super_pair_var = tk.StringVar(value="0")
        self.super_pair_display = tk.Label(first_row, textvariable=self.super_pair_var, font=('Arial',14),
                                        bg='white', width=7, relief=tk.SUNKEN)
        self.super_pair_display.pack(side=tk.LEFT, padx=6)
        self.bet_widgets["super_pair"] = self.super_pair_display
        tk.Label(first_row, text=" ", bg='#2a4a3c').pack(side=tk.LEFT, padx=12)
        tk.Label(first_row, text="核爆！:", font=('Arial',14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.nuclear_bomb_var = tk.StringVar(value="0")
        self.nuclear_bomb_display = tk.Label(first_row, textvariable=self.nuclear_bomb_var, font=('Arial',14),
                                            bg='white', width=7, relief=tk.SUNKEN)
        self.nuclear_bomb_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["nuclear_bomb"] = self.nuclear_bomb_display

        # 第二行：超级平局 + 甜蜜17
        second_row = tk.Frame(bet_frame, bg='#2a4a3c')
        second_row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(second_row, text="超级平局:", font=('Arial',14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.super_tie_var = tk.StringVar(value="0")
        self.super_tie_display = tk.Label(second_row, textvariable=self.super_tie_var, font=('Arial',14),
                                        bg='white', width=7, relief=tk.SUNKEN)
        self.super_tie_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["super_tie"] = self.super_tie_display
        tk.Label(second_row, text=" ", bg='#2a4a3c').pack(side=tk.LEFT, padx=11)
        tk.Label(second_row, text="甜蜜17:", font=('Arial',14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.sweet_seventeen_var = tk.StringVar(value="0")
        self.sweet_seventeen_display = tk.Label(second_row, textvariable=self.sweet_seventeen_var, font=('Arial',14),
                                                bg='white', width=7, relief=tk.SUNKEN)
        self.sweet_seventeen_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["sweet_seventeen"] = self.sweet_seventeen_display

        # 第三行：动态容器，用于显示“主注(庄家)”或“保险”
        third_row = tk.Frame(bet_frame, bg='#2a4a3c')
        third_row.pack(fill=tk.X, padx=10, pady=3)
        self.third_row_container = tk.Frame(third_row, bg='#2a4a3c')
        self.third_row_container.pack(side=tk.LEFT)
        # 主注(庄家) 区域（默认显示）
        self.main_dealer_frame = tk.Frame(self.third_row_container, bg='#2a4a3c')
        tk.Label(self.main_dealer_frame, text="      主注(庄家):", font=('Arial',16,'bold'), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.main_dealer_var = tk.StringVar(value="0")
        self.main_dealer_display = tk.Label(self.main_dealer_frame, textvariable=self.main_dealer_var, font=('Arial',16,'bold'),
                                            bg='white', width=8, relief=tk.SUNKEN)
        self.main_dealer_display.pack(side=tk.LEFT, padx=2)
        self.bet_widgets["main_dealer"] = self.main_dealer_display
        # 保险区域（初始隐藏）
        self.insurance_frame = tk.Frame(self.third_row_container, bg='#2a4a3c')
        tk.Label(self.insurance_frame, text="      保险:", font=('Arial',16,'bold'), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=31)
        self.insurance_var = tk.StringVar(value="0")
        self.insurance_display = tk.Label(self.insurance_frame, textvariable=self.insurance_var, font=('Arial',16,'bold'),
                                        bg='#C4C4C4', fg='black', width=8, relief=tk.SUNKEN)
        self.insurance_display.pack(side=tk.LEFT, padx=2)
        # 默认显示主注(庄家)
        self.main_dealer_frame.pack(side=tk.LEFT, padx=2)
        self.insurance_frame.pack_forget()

        # 第四行：主注(玩家) 固定
        fourth_row = tk.Frame(bet_frame, bg='#2a4a3c')
        fourth_row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(fourth_row, text="      主注(玩家):", font=('Arial',16,'bold'), bg='#2a4a3c', fg='white',padx=2).pack(side=tk.LEFT)
        self.main_player_var = tk.StringVar(value="0")
        self.main_player_display = tk.Label(fourth_row, textvariable=self.main_player_var, font=('Arial',16,'bold'),
                                            bg='white', width=8, relief=tk.SUNKEN)
        self.main_player_display.pack(side=tk.LEFT, padx=2)
        self.bet_widgets["main_player"] = self.main_player_display

        # 后续的 action_frame, status_label, bet_info_frame 等保持不变...
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X)
        self._build_action_buttons()
        self.status_label = tk.Label(control_frame, text="设置下注金额并开始游戏", font=('Arial',14), bg='#2a4a3c', fg='white')
        self.status_label.pack(pady=5, fill=tk.X)
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.current_bet_label = tk.Label(bet_info_frame, text="本局下注: $0.00", font=('Arial',12), bg='#2a4a3c', fg='white')
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        self.last_win_label = tk.Label(bet_info_frame, text="上局获胜: $0.00", font=('Arial',12), bg='#2a4a3c', fg='#FFD700')
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)
        rules_btn = tk.Button(bet_info_frame, text="ℹ️", command=self.show_game_instructions,
                            font=('Arial',8), bg='#4B8BBE', fg='white', width=2)
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)
        rules_btn.bind("<Button-3>", self.show_remaining_cards)

        # 初始无激活主注，所有边注禁用（需调用 set_active_main_bet 和 _update_side_bets_state）
        self.set_active_main_bet(None)
    
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
    
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("双向21点 游戏规则")
        win.geometry("900x700")
        win.resizable(False,False)
        win.configure(bg='#F0F0F0')
        mainf = tk.Frame(win, bg='#F0F0F0')
        mainf.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scroll = ttk.Scrollbar(mainf)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(mainf, bg='#F0F0F0', yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=canvas.yview)
        content = tk.Frame(canvas, bg='#F0F0F0')
        canvas.create_window((0,0), window=content, anchor='nw')
        rules = """双向21点 游戏规则

1. 游戏目标: 使手中牌的点数总和尽可能接近21点，但不能超过，超过即爆牌。
2. 牌值: 2-10为面值，J/Q/K为10点，A为1或11点。
3. 主注选择: 每局只能选择“主注(玩家)”或“主注(庄家)”其中一个下注。
   - 主注(玩家): 玩家正常操作手牌（要牌/停牌/加倍/投降），庄家软17要牌。
   - 主注(庄家): 玩家自动要牌至17点或以上(软17要牌)，然后庄家正常补牌；结算按庄家是否获胜判定。
   ** 特别说明： 主注(庄家)会在玩家爆牌庄家最终17点的情况下平局处理。
4. 边注说明:
   - 超级对子、核爆！仅在下注主注(庄家)时可下注。
   - 超级平局、甜蜜17仅在下注主注(玩家)时可下注。
5. 具体赔率见下表。"""
        tk.Label(content, text=rules, font=('微软雅黑',11), bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X)
        def make_table(parent, title, headers, data):
            tk.Label(parent, text=title, font=('微软雅黑',12,'bold'), bg='#F0F0F0').pack(anchor='w', padx=10, pady=(10,0))
            frame = tk.Frame(parent, bg='#F0F0F0')
            frame.pack(fill=tk.X, padx=20, pady=5)
            for c,h in enumerate(headers):
                tk.Label(frame, text=h, font=('微软雅黑',10,'bold'), bg='#4B8BBE', fg='white', padx=10, pady=5).grid(row=0, column=c, sticky='nsew', padx=1, pady=1)
            for r,rowd in enumerate(data,1):
                bg = '#C4C4C4' if r%2==0 else '#F0F0F0'
                for c,txt in enumerate(rowd):
                    tk.Label(frame, text=txt, font=('微软雅黑',10), bg=bg, padx=10, pady=5).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
            for c in range(len(headers)):
                frame.columnconfigure(c, weight=1)
        make_table(content, "超级对子支付表", ["牌型","赔率"],
                   [("双方均为对子）","50:1"),("单方完美对子","5:1"),("单方普通对子","3:1")])
        make_table(content, "核爆！支付表（双方均爆牌）", ["总手牌张数","赔率"],
                   [("6/7","5:1"),("8","15:1"),("9","30:1"),("10","100:1"),("11","150:1"),("12+","250:1")])
        make_table(content, "超级平局支付表", ["牌型","赔率"],
                   [("双方均爆牌","1:1"),("17/18/19点平局","3:1"),("20点平局","8:1"),("非黑杰克平局","15:1"),("黑杰克平局","25:1")])
        make_table(content, "甜蜜17支付表", ["动作","赔率"],
                   [("硬17停牌","5:1"),("软17要牌","5:1"),("软17停牌","6:1")])
        content.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    
    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            for item_id in chip.find_all():
                if chip.type(item_id)=='oval':
                    x1,y1,x2,y2 = chip.coords(item_id)
                    chip.create_oval(x1,y1,x2,y2, outline='black', width=2)
                    break
            chip.delete("highlight")
        for chip in self.chip_buttons:
            for item_id in chip.find_all():
                if chip.type(item_id)=='text' and chip.itemcget(item_id,'text')==chip_text:
                    for oid in chip.find_all():
                        if chip.type(oid)=='oval':
                            x1,y1,x2,y2 = chip.coords(oid)
                            chip.create_oval(x1,y1,x2,y2, outline='gold', width=3, tags="highlight")
                            break
                    break
    
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
    
    def update_hand_labels(self):
        if self.game.player_hand:
            val = self.game.get_hand_value(self.game.player_hand)
            if self.game.check_blackjack(self.game.player_hand):
                self.player_label.config(text="玩家 - 黑杰克")
            elif val>21:
                self.player_label.config(text=f"玩家 - {val}点 (爆牌)")
            else:
                self.player_label.config(text=f"玩家 - {val}点")
        if self.game.dealer_hand:
            val = self.game.get_hand_value(self.game.dealer_hand)
            if self.game.stage=="showdown" or self.game.player_done:
                if self.game.check_blackjack(self.game.dealer_hand):
                    self.dealer_label.config(text="庄家 - 黑杰克")
                elif val>21:
                    self.dealer_label.config(text=f"庄家 - {val}点 (爆牌)")
                else:
                    self.dealer_label.config(text=f"庄家 - {val}点")
            else:
                self.dealer_label.config(text=f"庄家 - {self.game.dealer_hand[0].get_value()}点")
    
    def disable_action_buttons(self):
        for btn in ['hit_button','stand_button','surrender_button','double_button']:
            if hasattr(self, btn):
                getattr(self, btn).config(state=tk.DISABLED)
    
    def _create_scaled_image(self, card, w, h, use_back=False):
        img = (self.original_images["back"] if use_back else self.original_images[(card.suit,card.rank)]).copy()
        img = img.resize((w,h), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    
    def flip_card_animation(self, card_label, card, callback=None):
        def _flip_step(step=0):
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
            self.after(20, lambda: _flip_step(step + 1))
        _flip_step()
    
    def add_card_to_frame(self, frame, card, show_front=True, position=None):
        img = self.card_images.get((card.suit,card.rank), self.back_image) if show_front else self.back_image
        label = tk.Label(frame, image=img, bg='#2a4a3c')
        if position is None:
            label.pack(side=tk.LEFT, padx=5)
        else:
            label.place(x=position*110, y=0, width=100, height=150)
        label.card = card
        label.is_face_up = show_front
        self.active_card_labels.append(label)
        # 拥挤时重新排列
        children = [w for w in frame.winfo_children() if isinstance(w,tk.Label)]
        if len(children)>5:
            target = 30
            for i,ch in enumerate(children):
                ch.place(x=i*target, y=0)
        return label
    
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
            self.game.main_bet_player = int(self.main_player_var.get())
            self.game.main_bet_dealer = int(self.main_dealer_var.get())
            self.game.super_pair_bet = int(self.super_pair_var.get())
            self.game.nuclear_bomb_bet = int(self.nuclear_bomb_var.get())
            self.game.super_tie_bet = int(self.super_tie_var.get())
            self.game.sweet_seventeen_bet = int(self.sweet_seventeen_var.get())
        except:
            messagebox.showerror("错误","请输入有效的下注金额")
            return
        if (self.game.main_bet_player>0 and self.game.main_bet_dealer>0) or (self.game.main_bet_player==0 and self.game.main_bet_dealer==0):
            messagebox.showerror("错误","必须且只能选择一个主注（玩家或庄家）下注")
            return
        if self.game.main_bet_player>0:
            active='player'
            main_bet = self.game.main_bet_player
        else:
            active='dealer'
            main_bet = self.game.main_bet_dealer
        if main_bet<10:
            messagebox.showerror("错误","主注至少10元")
            return
        total = main_bet+self.game.super_pair_bet+self.game.nuclear_bomb_bet+self.game.super_tie_bet+self.game.sweet_seventeen_bet
        if self.balance<total:
            messagebox.showerror("错误","余额不足")
            return
        self.last_bet = {
            "main_player": self.game.main_bet_player,
            "main_dealer": self.game.main_bet_dealer,
            "super_pair": self.game.super_pair_bet,
            "nuclear_bomb": self.game.nuclear_bomb_bet,
            "super_tie": self.game.super_tie_bet,
            "sweet_seventeen": self.game.sweet_seventeen_bet
        }
        self.repeat_bet_btn.config(state=tk.DISABLED)
        self.disable_betting_area()   # 这里只解绑事件，不改颜色
        self.last_win_label.config(text="上局获胜: $0.00")
        self.start_button.config(state=tk.DISABLED)
        self.reset_bets_button.config(state=tk.DISABLED)
        # 保险相关：只在主注玩家时显示，且由UI替换完成，此处不需要额外动作
        if active=='player':
            # 确保保险区域已显示（已由set_active_main_bet处理）
            self.insurance_display.config(bg='#C4C4C4', fg='black')  # 只读
            self.insurance_var.set("0")
        self.balance -= total
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")

        self.game.active_main_bet = active
        need_shuffle = (not hasattr(self.game,'deck') or self.game.deck is None or len(self.game.deck.cards)<=60)
        def after_shuffle():
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
            for w in self.dealer_cards_frame.winfo_children(): w.destroy()
            for w in self.player_cards_frame.winfo_children(): w.destroy()
            self.game.deal_initial_cards()
            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            self.deal_card_sequence()
        def no_shuffle():
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
            for w in self.dealer_cards_frame.winfo_children(): w.destroy()
            for w in self.player_cards_frame.winfo_children(): w.destroy()
            self.game.deal_initial_cards()
            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            self.deal_card_sequence()
        if need_shuffle:
            self.play_shuffle_animation(duration_ms=10000, callback=after_shuffle)
        else:
            no_shuffle()
    
    def disable_betting_area(self):
        # 只解绑事件，不改变颜色
        for w in self.bet_widgets.values():
            w.unbind("<Button-1>")
            w.unbind("<Button-3>")
        self.insurance_display.unbind("<Button-1>")
        self.insurance_display.unbind("<Button-3>")
        # 保险区域的背景色保持不变（不修改）
    
    def enable_betting_area(self):
        # 重新绑定事件基于当前激活状态（由set_active_main_bet负责）
        self.set_active_main_bet(self.active_main_bet)
        # 确保所有边注格子的背景和绑定正确
        self._update_side_bets_state()
        # 主注格子背景由set_active_main_bet处理
        for w in self.bet_widgets.values():
            if w in [self.main_player_display, self.main_dealer_display]:
                continue
            # 这里不改变背景，因为 _update_side_bets_state 已经根据激活状态设置了合适的背景
            pass
    
    def deal_card_sequence(self):
        self.status_label.config(text="发玩家第一张牌")
        card = self.game.player_hand[0]
        lbl = self.add_card_to_frame(self.player_cards_frame, card, True, 0)
        self.flip_card_animation(lbl, card, self.after_player_card1)
    
    def after_player_card1(self):
        first_card = self.game.player_hand[0]
        self.player_label.config(text=f"玩家 - {first_card.get_value()}点")
        self.status_label.config(text="发庄家第一张牌")
        card = self.game.dealer_hand[0]
        lbl = self.add_card_to_frame(self.dealer_cards_frame, card, True, 0)
        self.flip_card_animation(lbl, card, self.after_dealer_card1)
    
    def after_dealer_card1(self):
        first_dcard = self.game.dealer_hand[0]
        self.dealer_label.config(text=f"庄家 - {first_dcard.get_value()}点")
        self.status_label.config(text="发玩家第二张牌")
        card = self.game.player_hand[1]
        lbl = self.add_card_to_frame(self.player_cards_frame, card, True, 1)
        self.flip_card_animation(lbl, card, self.after_player_card2)
    
    def after_player_card2(self):
        # 先更新手牌数据，但暂时不刷新显示的点数
        self.update_hand_labels()  # 这行可以保留，但用户感觉提前，故改用延迟刷新
        # 取消上面的直接更新，改为延迟一小段时间后再刷新，确保卡牌完全显示
        self.after(50, self._safe_update_player_labels)

    def _safe_update_player_labels(self):
        self.update_hand_labels()
        # 后续原有逻辑
        if self.game.active_main_bet == 'player':
            upcard = self.game.dealer_hand[0]
            if upcard.rank == 'A':
                self.offer_insurance()
            else:
                self.check_blackjack_and_continue()
        else:
            self.game.stage = "player_turn"
            self.stage_label.config(text="自动玩家回合")
            self.status_label.config(text="自动要牌中...")
            self.auto_player_play()
    
    def auto_player_play(self):
        val = self.game.get_hand_value(self.game.player_hand)
        is_soft = self.game.is_soft_17(self.game.player_hand)
        # 修改点1：主注为庄家时，玩家自动要牌：17点或以上停牌，但软17例外（需要继续要牌）
        if val >= 17:
            if val == 17 and is_soft:
                # 软17，继续要牌
                pass
            else:
                self.game.player_done = True
                self.status_label.config(text="玩家自动停牌")
                self.after(600, self.dealer_turn)
                return
        self.game.player_hit()
        new_card = self.game.player_hand[-1]
        pos = len(self.game.player_hand)-1
        lbl = self.add_card_to_frame(self.player_cards_frame, new_card, False, pos)
        self.flip_card_animation(lbl, new_card, self.after_auto_hit)
    
    def after_auto_hit(self):
        self.update_hand_labels()
        val = self.game.get_hand_value(self.game.player_hand)
        if val > 21:
            self.game.player_done = True
            self.status_label.config(text="玩家爆牌！")
            self.after(800, self.dealer_turn)
            return
        # 继续循环，再次检查停牌条件
        self.auto_player_play()
    
    def offer_insurance(self):
        self.game.stage = "insurance"
        self.stage_label.config(text="保险选项")
        self.status_label.config(text="庄家明牌是A，是否购买保险？")
        for w in self.action_frame.winfo_children(): w.destroy()
        f = tk.Frame(self.action_frame, bg='#2a4a3c')
        f.pack(pady=5)
        insurance_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        insurance_frame.pack()
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
        amt = self.game.main_bet_player // 2
        if self.balance >= amt:
            self.balance -= amt
            self.game.insurance_bet = amt
            self.game.insurance_taken = True
            self.update_balance()
            self.insurance_var.set(str(int(amt)))
            total = (self.game.main_bet_player + self.game.super_pair_bet + self.game.nuclear_bomb_bet +
                     self.game.super_tie_bet + self.game.sweet_seventeen_bet + amt)
            self.current_bet_label.config(text=f"本局下注: ${total:.2f}")
            self.status_label.config(text=f"已购买保险 ${amt}")
            self.insurance_display.config(bg='white', fg='black')
            self.after(1000, self.check_blackjack_and_continue)
        else:
            messagebox.showerror("错误","余额不足购买保险")
            self.decline_insurance()
    
    def decline_insurance(self):
        self.game.insurance_taken = False
        self.status_label.config(text="未购买保险")
        self.after(1000, self.check_blackjack_and_continue)
    
    def check_blackjack_and_continue(self):
        if self.game.check_blackjack(self.game.player_hand):
            self.game.player_blackjack = True
            self.status_label.config(text="玩家有黑杰克！")
            up = self.game.dealer_hand[0]
            up_value = up.get_value()
            # 庄家明牌为10点（10/J/Q/K）
            if up_value == 10:
                self.game.add_dealer_second_card()
                second = self.game.dealer_hand[1]
                lbl = self.add_card_to_frame(self.dealer_cards_frame, second, False, 1)
                self.dealer_hidden_card_label = lbl
                def reveal():
                    if self.game.check_blackjack(self.game.dealer_hand):
                        self.game.dealer_blackjack = True
                        self.update_hand_labels()
                        self.status_label.config(text="双方黑杰克，平局")
                    else:
                        self.game.dealer_blackjack = False
                        self.status_label.config(text="玩家黑杰克获胜！")
                    self.after(1000, self.show_showdown)
                self.flip_card_animation(lbl, second, reveal)
                return
            # 庄家明牌为A
            elif up_value == 11:
                self.offer_insurance_for_blackjack()
                return
            # 庄家明牌为2~9，不补牌，直接结算
            else:
                self.after(1000, self.show_showdown)
                return
        else:
            self.game.stage = "player_turn"
            self.stage_label.config(text="玩家回合")
            self.show_player_actions()
    
    def offer_insurance_for_blackjack(self):
        self.game.stage = "insurance"
        self.stage_label.config(text="保险选项")
        self.status_label.config(text="庄家明牌是A，是否购买保险？")
        for w in self.action_frame.winfo_children(): w.destroy()
        f = tk.Frame(self.action_frame, bg='#2a4a3c')
        f.pack(pady=5)
        self.insurance_btn = tk.Button(f, text="购买保险", command=self.take_insurance_for_blackjack, font=('Arial',14), bg='#4CAF50', fg='white')
        self.insurance_btn.pack(side=tk.LEFT, padx=5)
        self.no_insurance_btn = tk.Button(f, text="不购买", command=self.decline_insurance_for_blackjack, font=('Arial',14), bg='#F44336', fg='white')
        self.no_insurance_btn.pack(side=tk.LEFT, padx=5)
    
    def take_insurance_for_blackjack(self):
        amt = self.game.main_bet_player // 2
        if self.balance >= amt:
            self.balance -= amt
            self.game.insurance_bet = amt
            self.game.insurance_taken = True
            self.update_balance()
            self.insurance_var.set(str(int(amt)))
            total = (self.game.main_bet_player + self.game.super_pair_bet + self.game.nuclear_bomb_bet +
                     self.game.super_tie_bet + self.game.sweet_seventeen_bet + amt)
            self.current_bet_label.config(text=f"本局下注: ${total:.2f}")
            self.status_label.config(text=f"已购买保险 ${amt}")
            self.insurance_display.config(bg='white', fg='black')
            self.after(1000, self.continue_after_insurance_for_blackjack)
        else:
            messagebox.showerror("错误","余额不足")
            self.decline_insurance_for_blackjack()
    
    def decline_insurance_for_blackjack(self):
        self.game.insurance_taken = False
        self.status_label.config(text="未购买保险")
        self.after(1000, self.continue_after_insurance_for_blackjack)
    
    def continue_after_insurance_for_blackjack(self):
        self.game.add_dealer_second_card()
        second = self.game.dealer_hand[1]
        lbl = self.add_card_to_frame(self.dealer_cards_frame, second, False, 1)
        self.dealer_hidden_card_label = lbl
        def reveal():
            if self.game.check_blackjack(self.game.dealer_hand):
                self.game.dealer_blackjack = True
                self.update_hand_labels()
                self.status_label.config(text="庄家黑杰克，平局")
            else:
                self.game.dealer_blackjack = False
                self.status_label.config(text="玩家黑杰克获胜！")
            self.after(1000, self.show_showdown)
        self.flip_card_animation(lbl, second, reveal)
    
    def show_player_actions(self):
        for w in self.action_frame.winfo_children(): w.destroy()
        f = tk.Frame(self.action_frame, bg='#2a4a3c')
        f.pack(pady=5)
        self.hit_button = tk.Button(
            f, text="要牌",
            command=self.hit_action,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=7
        )
        self.hit_button.pack(side=tk.LEFT, padx=5)
        self.stand_button = tk.Button(
            f, text="停牌",
            command=self.stand_action,
            font=('Arial', 14), bg='#2196F3', fg='white', width=7
        )
        self.stand_button.pack(side=tk.LEFT, padx=5)
        can_double = (self.balance >= self.game.main_bet_player and len(self.game.player_hand)==2)
        self.double_button = tk.Button(
            f, text="加倍",
            command=self.double_action,
            font=('Arial', 14), bg='#FF9800', fg='white', width=7,
            state=tk.NORMAL if can_double else tk.DISABLED
        )
        self.double_button.pack(side=tk.LEFT, padx=5)
        self.surrender_button = tk.Button(
            f, text="投降",
            command=self.surrender_action,
            font=('Arial', 14), bg='#F44336', fg='white', width=7
        )
        self.surrender_button.pack(side=tk.LEFT, padx=5)
        self.status_label.config(text="请选择您的操作")
    
    def hit_action(self):
        if self.game.sweet_seventeen_bet>0 and len(self.game.player_hand)==2:
            val = self.game.get_hand_value(self.game.player_hand)
            if val==17 and self.game.is_soft_17(self.game.player_hand):
                self.sweet_seventeen_action = 'soft17_hit'
        self.disable_action_buttons()
        new_val = self.game.player_hit()
        new_card = self.game.player_hand[-1]
        pos = len(self.game.player_hand)-1
        lbl = self.add_card_to_frame(self.player_cards_frame, new_card, False, pos)
        self.flip_card_animation(lbl, new_card, lambda: self.after_hit(new_val))
    
    def after_hit(self, val):
        self.update_hand_labels()
        if val > 21:
            self.game.player_done = True
            self.status_label.config(text="玩家爆牌！")
            # 如果下注了超级平局，庄家需要继续补牌以判断是否平局
            if self.game.insurance_bet > 0:
                self.after(800, self.dealer_turn)
            elif self.game.super_tie_bet > 0:
                self.after(800, self.dealer_turn)
            else:
                if self.game.active_main_bet == 'player':
                    self.after(800, self.show_showdown)
                else:
                    self.after(800, self.dealer_turn)
            return
        if val == 21:
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
        if self.game.sweet_seventeen_bet>0:
            val = self.game.get_hand_value(self.game.player_hand)
            if val==17:
                if self.game.is_soft_17(self.game.player_hand):
                    self.sweet_seventeen_action = 'soft17_stop'
                else:
                    self.sweet_seventeen_action = 'hard17_stop'
        self.disable_action_buttons()
        self.game.player_done = True
        self.status_label.config(text="玩家停牌")
        self.after(600, self.dealer_turn)
    
    def double_action(self):
        if self.balance < self.game.main_bet_player:
            messagebox.showerror("错误","余额不足")
            self.hit_button.config(state=tk.NORMAL)
            self.stand_button.config(state=tk.NORMAL)
            return
        if self.game.sweet_seventeen_bet>0 and len(self.game.player_hand)==2:
            val = self.game.get_hand_value(self.game.player_hand)
            if val==17 and self.game.is_soft_17(self.game.player_hand):
                self.sweet_seventeen_action = 'soft17_hit'
        self.disable_action_buttons()
        self.game.double_extra = self.game.main_bet_player
        self.balance -= self.game.main_bet_player
        self.game.main_bet_player *= 2
        self.main_player_var.set(self.game.main_bet_player)
        self.update_balance()
        total = (self.game.main_bet_player + self.game.super_pair_bet + self.game.nuclear_bomb_bet +
                 self.game.super_tie_bet + self.game.sweet_seventeen_bet + self.game.insurance_bet)
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")
        new_val = self.game.player_hit()
        new_card = self.game.player_hand[-1]
        pos = len(self.game.player_hand)-1
        lbl = self.add_card_to_frame(self.player_cards_frame, new_card, False, pos)
        self.flip_card_animation(lbl, new_card, lambda: self.after_double(new_val))
    
    def after_double(self, val):
        self.update_hand_labels()
        self.game.player_done = True
        self.status_label.config(text="玩家爆牌（加倍）！" if val > 21 else "玩家加倍完成")
        if val > 21:
            # 如果下注了超级平局，庄家需要继续补牌
            if self.game.insurance_bet > 0:
                self.after(800, self.dealer_turn)
            elif self.game.super_tie_bet > 0:
                self.after(800, self.dealer_turn)
            else:
                if self.game.active_main_bet == 'player' and val > 21:
                    self.after(800, self.show_showdown)
                else:
                    self.after(800, self.dealer_turn)
        else:
            self.after(800, self.dealer_turn)
        
    def surrender_action(self):
        self.disable_action_buttons()
        refund = self.game.main_bet_player // 2
        self.balance += refund
        self.game.main_bet_player = 0
        self.main_player_var.set("投降")
        self.update_balance()
        self.game.player_done = True
        self.status_label.config(text="玩家投降，退还一半主注")
        self.after(800, self.show_showdown)
    
    def dealer_turn(self):
        if self.game.active_main_bet == 'player' and self.game.get_hand_value(self.game.player_hand) > 21:
            if self.game.insurance_bet == 0 and self.game.super_tie_bet == 0:
                self.show_showdown()
                return
            # 否则继续庄家回合，不返回
        self.game.stage = "dealer_turn"
        self.stage_label.config(text="庄家回合")
        self.game.add_dealer_second_card()
        second = self.game.dealer_hand[1]
        lbl = self.add_card_to_frame(self.dealer_cards_frame, second, False, 1)
        self.dealer_hidden_card_label = lbl

        def reveal():
            self.update_hand_labels()
            if self.game.check_blackjack(self.game.dealer_hand):
                self.game.dealer_blackjack = True
                self.after(1000, self.show_showdown)
                return
            self.game.dealer_blackjack = False
            self.dealer_hit_loop()

        self.flip_card_animation(lbl, second, reveal)
    
    def dealer_hit_loop(self):
        val = self.game.get_hand_value(self.game.dealer_hand)
        if val < 17 or (val==17 and self.game.is_soft_17(self.game.dealer_hand)):
            self.status_label.config(text="庄家要牌")
            new_val = self.game.dealer_hit()
            new_card = self.game.dealer_hand[-1]
            pos = len(self.game.dealer_hand)-1
            lbl = self.add_card_to_frame(self.dealer_cards_frame, new_card, False, pos)
            self.flip_card_animation(lbl, new_card, lambda: self.after_dealer_hit(new_val))
        else:
            self.status_label.config(text="庄家停牌")
            self.after(1000, self.show_showdown)
    
    def after_dealer_hit(self, val):
        self.update_hand_labels()
        self.after(100, self.dealer_hit_loop)
    
    def show_showdown(self):
        self.game.stage = "showdown"
        self.stage_label.config(text="结算")
        for w in self.dealer_cards_frame.winfo_children():
            if isinstance(w,tk.Label) and hasattr(w,'card') and not w.is_face_up:
                w.config(image=self.card_images.get((w.card.suit,w.card.rank), self.back_image))
                w.is_face_up = True
        self._do_showdown()
    
    def _do_showdown(self):
        winnings, details = self.calculate_winnings()
        self.balance += winnings
        self.update_balance()
        self.update_hand_labels()

        # 原始下注金额
        bets = {
            "main_player": self.game.main_bet_player,
            "main_dealer": self.game.main_bet_dealer,
            "super_pair": self.game.super_pair_bet,
            "nuclear_bomb": self.game.nuclear_bomb_bet,
            "super_tie": self.game.super_tie_bet,
            "sweet_seventeen": self.game.sweet_seventeen_bet,
            "insurance": self.game.insurance_bet,
        }

        # 更新所有格子显示及背景
        for key, val in details.items():
            if key == "main_player":
                self.main_player_var.set(str(int(val)) if val else "0")
                bet = bets["main_player"]
                if val > bet:
                    self.main_player_display.config(bg='gold')
                elif val == bet and val > 0:
                    self.main_player_display.config(bg='lightblue')
                else:
                    self.main_player_display.config(bg='white')
            elif key == "main_dealer":
                self.main_dealer_var.set(str(int(val)) if val else "0")
                bet = bets["main_dealer"]
                if val > bet:
                    self.main_dealer_display.config(bg='gold')
                elif val == bet and val > 0:
                    self.main_dealer_display.config(bg='lightblue')
                else:
                    self.main_dealer_display.config(bg='white')
            elif key == "super_pair":
                self.super_pair_var.set(str(int(val)) if val else "0")
                bet = bets["super_pair"]
                if val > bet:
                    self.super_pair_display.config(bg='gold')
                elif val == bet and val > 0:
                    self.super_pair_display.config(bg='lightblue')
                else:
                    self.super_pair_display.config(bg='white')
            elif key == "nuclear_bomb":
                self.nuclear_bomb_var.set(str(int(val)) if val else "0")
                bet = bets["nuclear_bomb"]
                if val > bet:
                    self.nuclear_bomb_display.config(bg='gold')
                elif val == bet and val > 0:
                    self.nuclear_bomb_display.config(bg='lightblue')
                else:
                    self.nuclear_bomb_display.config(bg='white')
            elif key == "super_tie":
                self.super_tie_var.set(str(int(val)) if val else "0")
                bet = bets["super_tie"]
                if val > bet:
                    self.super_tie_display.config(bg='gold')
                elif val == bet and val > 0:
                    self.super_tie_display.config(bg='lightblue')
                else:
                    self.super_tie_display.config(bg='white')
            elif key == "sweet_seventeen":
                self.sweet_seventeen_var.set(str(int(val)) if val else "0")
                bet = bets["sweet_seventeen"]
                if val > bet:
                    self.sweet_seventeen_display.config(bg='gold')
                elif val == bet and val > 0:
                    self.sweet_seventeen_display.config(bg='lightblue')
                else:
                    self.sweet_seventeen_display.config(bg='white')
            elif key == "insurance":
                self.insurance_var.set(str(int(val)) if val else "0")
                # 如果未下注保险，背景保持灰色；否则根据是否获胜显示金色或白色
                if self.game.insurance_bet == 0:
                    self.insurance_display.config(bg='#C4C4C4')
                else:
                    self.insurance_display.config(bg='gold' if val > 0 else 'white')

        # 修改点4：根据主注类型，强制某些格子为灰色
        if self.game.active_main_bet == 'player':
            # 超级对子、核爆！保持灰色
            self.super_pair_display.config(bg='#C4C4C4')
            self.nuclear_bomb_display.config(bg='#C4C4C4')
        elif self.game.active_main_bet == 'dealer':
            # 超级平局、甜蜜17、主注(玩家) 保持灰色
            self.super_tie_display.config(bg='#C4C4C4')
            self.sweet_seventeen_display.config(bg='#C4C4C4')
            self.main_player_display.config(bg='#C4C4C4')

        # 状态文字
        pv = self.game.get_hand_value(self.game.player_hand)
        dv = self.game.get_hand_value(self.game.dealer_hand)
        if self.game.active_main_bet == 'player':
            if self.game.player_blackjack and self.game.dealer_blackjack:
                txt = "双方黑杰克，和局"
            elif self.game.player_blackjack:
                txt = "玩家黑杰克胜利！"
            elif self.game.dealer_blackjack:
                txt = "庄家黑杰克胜利！" if not self.game.insurance_taken else "庄家黑杰克，保险支付"
            elif pv > 21:
                txt = "玩家爆牌，庄家胜利"
            elif dv > 21:
                txt = "庄家爆牌，玩家胜利"
            elif pv > dv:
                txt = "玩家胜利"
            elif pv < dv:
                txt = "庄家胜利"
            else:
                txt = "和局"
        else:
            if details["main_dealer"] > self.game.main_bet_dealer:
                if dv == 21 and len(self.game.dealer_hand)==2:
                    if pv == 21 and len(self.game.player_hand)==2:
                        txt = "庄家玩家黑杰克，平局！"
                    else:
                        txt = "庄家黑杰克，你赢了！"
                else:
                    txt = "庄家获胜，你赢了！"
            elif details["main_dealer"] == self.game.main_bet_dealer:
                if pv > 21 and dv == 17:
                    txt = "玩家爆牌庄家17点，退还本金"
                else:
                    txt = "庄家玩家平局，退还本金"
            else:
                txt = "玩家获胜，下局加油！"

        self.status_label.config(text=txt)
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        self.show_restart_button()
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def calculate_winnings(self):
        winnings = 0
        details = {k:0 for k in ["main_player","main_dealer","super_pair","nuclear_bomb","super_tie","sweet_seventeen","insurance"]}
        pv = self.game.get_hand_value(self.game.player_hand)
        dv = self.game.get_hand_value(self.game.dealer_hand)
        p_bj = self.game.check_blackjack(self.game.player_hand)
        d_bj = self.game.check_blackjack(self.game.dealer_hand)
        # 主注(玩家)
        if self.game.active_main_bet == 'player':
            bet = self.game.main_bet_player
            if bet>0:
                if p_bj and not d_bj:
                    win = int(bet*2.5)
                    details["main_player"] = win
                    winnings += win
                elif d_bj and not p_bj:
                    details["main_player"] = 0
                elif pv>21:
                    details["main_player"] = 0
                elif dv>21:
                    win = bet*2
                    details["main_player"] = win
                    winnings += win
                elif pv>dv:
                    win = bet*2
                    details["main_player"] = win
                    winnings += win
                elif pv<dv:
                    details["main_player"] = 0
                else:
                    details["main_player"] = bet
                    winnings += bet
        else:
            bet = self.game.main_bet_dealer
            if bet>0:
                if pv > 21 and dv == 17:
                    details["main_dealer"] = bet
                    winnings += bet
                elif d_bj:
                    win = int(bet*2.5)
                    details["main_dealer"] = win
                    winnings += win
                elif p_bj and not d_bj:
                    details["main_dealer"] = 0
                elif p_bj and d_bj:
                    details["main_dealer"] = bet
                    winnings += bet
                elif pv>21 and dv>21:
                    details["main_dealer"] = bet
                    winnings += bet
                elif pv<=21 and dv>21:
                    details["main_dealer"] = 0
                elif pv>21 and dv<=21:
                    win = bet*2
                    details["main_dealer"] = win
                    winnings += win
                elif dv>pv:
                    win = bet*2
                    details["main_dealer"] = win
                    winnings += win
                elif dv<pv:
                    details["main_dealer"] = 0
                else:
                    details["main_dealer"] = bet
                    winnings += bet
        # 超级对子
        if self.game.super_pair_bet>0:
            res = self.game.check_super_pair()
            if res == 'both_pair_perfect' or res == 'both_pair':
                win = self.game.super_pair_bet * 50
                details["super_pair"] = win + self.game.super_pair_bet
            elif res == 'single_perfect':
                win = self.game.super_pair_bet * 5
                details["super_pair"] = win + self.game.super_pair_bet
            elif res == 'single_pair':
                win = self.game.super_pair_bet * 3
                details["super_pair"] = win + self.game.super_pair_bet
            else:
                details["super_pair"] = 0
            winnings += details["super_pair"]
        # 核爆！
        if self.game.nuclear_bomb_bet>0:
            total_cards = self.game.check_nuclear_bomb()
            if total_cards:
                mult = {6:5, 7:5, 8:15, 9:30, 10:100, 11:150}.get(total_cards, 250 if total_cards >= 12 else 0)
                if mult:
                    win = self.game.nuclear_bomb_bet * mult
                    details["nuclear_bomb"] = win + self.game.nuclear_bomb_bet
                else:
                    details["nuclear_bomb"] = 0
            else:
                details["nuclear_bomb"] = 0
            winnings += details["nuclear_bomb"]
        # 超级平局
        if self.game.super_tie_bet>0:
            tie = self.game.check_super_tie()
            if tie == 'both_bust':
                win = self.game.super_tie_bet * 1
                details["super_tie"] = win + self.game.super_tie_bet
            elif tie == 'seventeen_eighteen_nineteen_tie':
                win = self.game.super_tie_bet * 3
                details["super_tie"] = win + self.game.super_tie_bet
            elif tie == 'twenty_tie':
                win = self.game.super_tie_bet * 8
                details["super_tie"] = win + self.game.super_tie_bet
            elif tie == 'other_tie':
                win = self.game.super_tie_bet * 15
                details["super_tie"] = win + self.game.super_tie_bet
            elif tie == 'blackjack_tie':
                win = self.game.super_tie_bet * 25
                details["super_tie"] = win + self.game.super_tie_bet
            else:
                details["super_tie"] = 0
            winnings += details["super_tie"]
        # 甜蜜17
        if self.game.sweet_seventeen_bet>0 and self.sweet_seventeen_action:
            act = self.sweet_seventeen_action
            if act == 'hard17_stop':
                win = self.game.sweet_seventeen_bet * 5
                details["sweet_seventeen"] = win + self.game.sweet_seventeen_bet
            elif act == 'soft17_hit':
                win = self.game.sweet_seventeen_bet * 5
                details["sweet_seventeen"] = win + self.game.sweet_seventeen_bet
            elif act == 'soft17_stop':
                win = self.game.sweet_seventeen_bet * 6
                details["sweet_seventeen"] = win + self.game.sweet_seventeen_bet
            else:
                details["sweet_seventeen"] = 0
            winnings += details["sweet_seventeen"]
        # 保险
        if self.game.insurance_bet>0 and self.game.dealer_blackjack and not self.game.player_blackjack:
            win = self.game.insurance_bet * 3
            details["insurance"] = win
            winnings += win
        return winnings, details
    
    def reset_bets(self):
        self.main_player_var.set("0")
        self.main_dealer_var.set("0")
        self.super_pair_var.set("0")
        self.nuclear_bomb_var.set("0")
        self.super_tie_var.set("0")
        self.sweet_seventeen_var.set("0")
        
        self.super_pair_display.config(bg='#C4C4C4')
        self.nuclear_bomb_display.config(bg='#C4C4C4')
        self.super_tie_display.config(bg='#C4C4C4')
        self.sweet_seventeen_display.config(bg='#C4C4C4')
        self.insurance_display.config(bg='#C4C4C4')

        self.status_label.config(text="已重置所有下注金额")
        self.set_active_main_bet(None)
    
    def animate_cards_out(self):
        labels = []
        for f in [self.dealer_cards_frame, self.player_cards_frame]:
            for w in f.winfo_children():
                if isinstance(w,tk.Label) and hasattr(w,'card'):
                    labels.append(w)
        if not labels:
            return
        steps=20
        dist=800
        def move(step):
            if step>steps:
                for l in labels:
                    try: l.destroy()
                    except: pass
                return
            prog = step/steps
            off = int(dist * (1 - (1-prog)**3))
            for l in labels:
                try:
                    pi = l.place_info()
                    if pi:
                        x = int(pi.get('x',0)) + off
                        l.place(x=x)
                except: pass
            self.after(20, lambda: move(step+1))
        move(1)
    
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
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer=None
        self._resetting=True
        for aid in self.tk.eval('after info').split():
            self.after_cancel(aid)
        def after_anim():
            self.game.reset_game()
            self.stage_label.config(text="下注阶段")
            self.status_label.config(text="设置下注金额并开始游戏")
            self.player_label.config(text="玩家")
            self.dealer_label.config(text="庄家")
            self.main_player_var.set("0")
            self.main_dealer_var.set("0")
            self.super_pair_var.set("0")
            self.nuclear_bomb_var.set("0")
            self.super_tie_var.set("0")
            self.sweet_seventeen_var.set("0")
            self.insurance_var.set("0")
            self.sweet_seventeen_action = None
            # 恢复主注区域（如果之前是保险状态，切换回主注庄家）
            self.set_active_main_bet(None)
            for w in self.bet_widgets.values():
                if w not in [self.main_player_display, self.main_dealer_display]:
                    w.config(bg='white', fg='black')
            self.insurance_display.config(bg='#C4C4C4')
            self.active_card_labels = []
            self.dealer_hidden_card_label = None
            self.flipping_cards = []
            self.flip_step = 0
            self.enable_betting_area()
            self._build_action_buttons()
            if hasattr(self,'repeat_bet_btn'):
                self.repeat_bet_btn.config(state=tk.NORMAL if self.last_bet is not None else tk.DISABLED)
            self.current_bet_label.config(text="本局下注: $0.00")
            self._resetting = False
            self.status_label.config(text="设置下注金额并开始游戏")
            if auto_reset:
                self.status_label.config(text="30秒已到，自动开始新游戏")
                self.after(1000, self.status_label.config(text="设置下注金额并开始游戏"))
        self.animate_cards_out()
        self.after(500, after_anim)

def main(initial_balance=10000, username="Guest"):
    app = BlackjackGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: ${final_balance:.2f}")