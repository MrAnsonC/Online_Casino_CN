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
        self.push22_bet = 0
        self.stage = "betting"       # betting, dealing, waiting_second_card, player_turn, dealer_turn, showdown
        self.player_done = False
        self.insurance_bet = 0
        self.insurance_taken = False
        self.dealer_blackjack = False
    
    def deal_initial_cards(self):
        # 只发三张牌：庄家明牌、玩家明牌、庄家暗牌
        self.dealer_hand = [self.deck.deal_card(), self.deck.deal_card()]
        self.player_hand = [self.deck.deal_card()]
    
    def player_hit(self):
        self.player_hand.append(self.deck.deal_card())
        return self.get_hand_value(self.player_hand)
    
    def dealer_hit(self):
        self.dealer_hand.append(self.deck.deal_card())
        return self.get_hand_value(self.dealer_hand)
    
    def get_hand_value(self, hand):
        value = sum(card.get_value() for card in hand)
        num_aces = sum(1 for card in hand if card.rank == 'A')
        while value > 21 and num_aces > 0:
            value -= 10
            num_aces -= 1
        return value
    
    def check_blackjack(self, hand):
        if len(hand) != 2:
            return False
        values = [card.get_value() for card in hand]
        return (11 in values and 10 in values) or (values[0] + values[1] == 21)

    def is_suited_blackjack(self, hand):
        return self.check_blackjack(hand) and hand[0].suit == hand[1].suit

class BlackjackGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("21点")
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
            "push22": 0,
            "insurance": 0
        }
        self.bet_widgets = {}
        self.flipping_cards = []
        self.flip_step = 0
        self._resetting = False
        self.dealer_hidden_card_label = None
        self.insurance_offered = False
        
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
        elif bet_type == "push22":
            current = int(self.push22_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"22点平局边注上限为2500，已自动调整")
            self.push22_var.set(str(int(new_value)))
    
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
            text="庄家手牌16点必须要牌 任何17点停牌\n庄家手牌22点，主注全部平局", 
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
        tk.Label(header_frame, text="主注最低", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="主注最高", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="22点平局最高", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$25,000", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        
        # 第一行：22点平局边注 + 保险
        first_row = tk.Frame(bet_frame, bg='#2a4a3c')
        first_row.pack(fill=tk.X, padx=10, pady=3)
        
        push22_label = tk.Label(first_row, text="22点平局:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        push22_label.pack(side=tk.LEFT, padx=1)
        self.push22_var = tk.StringVar(value="0")
        self.push22_display = tk.Label(first_row, textvariable=self.push22_var, font=('Arial', 14), bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.push22_display.pack(side=tk.LEFT, padx=5)
        self.push22_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("push22"))
        self.push22_display.bind("<Button-3>", lambda e: self.clear_bet("push22"))
        self.bet_widgets["push22"] = self.push22_display
        
        self.insurance_label = tk.Label(first_row, text="保险:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.insurance_var = tk.StringVar(value="0")
        self.insurance_display = tk.Label(first_row, textvariable=self.insurance_var, font=('Arial', 14), bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=3)
        self.insurance_label.pack_forget()
        self.insurance_display.pack_forget()
        
        # 第二行：主注
        second_row = tk.Frame(bet_frame, bg='#2a4a3c')
        second_row.pack(fill=tk.X, padx=10, pady=3)
        main_bet_label = tk.Label(second_row, text="主注:", font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='white')
        main_bet_label.pack(side=tk.LEFT, padx=2)
        self.main_bet_var = tk.StringVar(value="0")
        self.main_bet_display = tk.Label(second_row, textvariable=self.main_bet_var, font=('Arial', 18, 'bold'), bg='white', fg='black', width=8, relief=tk.SUNKEN, padx=5)
        self.main_bet_display.pack(side=tk.LEFT, padx=2)
        self.main_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("main"))
        self.main_bet_display.bind("<Button-3>", lambda e: self.clear_bet("main"))
        self.bet_widgets["main"] = self.main_bet_display
        
        # 游戏操作按钮
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
    
    def clear_bet(self, bet_type):
        if self.game.stage != "betting":
            return
        if bet_type == "main":
            self.main_bet_var.set("0")
        elif bet_type == "push22":
            self.push22_var.set("0")
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
           a. 下注阶段: 玩家下注主注和22点平局边注（可选）
           b. 发牌: 庄家第一张明牌 → 玩家第一张明牌 → 庄家第二张暗牌
           c. 玩家决定第二张牌:
               - 要牌（Hit）: 获得第二张牌，然后进入正常玩家回合
               - 加倍（Double）: 主注翻倍，获得第二张牌
                 * 如果第一张牌是A，则加倍后直接进入庄家回合
                 * 否则进入正常玩家回合（可继续要牌、停牌、再加倍）
           d. 正常玩家回合（已有两张牌）:
               - 要牌: 获得一张新牌
               - 停牌: 不再要牌
               - 加倍: 主注翻倍，获得一张新牌（若第一张牌是A，则加倍后立即结束回合；否则可继续）
           e. 庄家回合: 庄家必须继续要牌直到手牌点数≥17

        4. 结算规则:
           - 玩家点数 > 21: 玩家输
           - 庄家点数 > 21: 玩家赢
           - 庄家 Blackjack: 玩家输（保险赔付2:1）
           - 庄家点数等于22: 主注Push（退还），22点平局边注根据庄家手牌花色赔付:
             * 同花（所有牌花色相同）: 50:1
             * 同色（所有牌同为红色或黑色）: 20:1
             * 其他: 8:1
           - 点数比较: 点数高者胜，平局退还主注

        5. 保险:
           - 庄家明牌为A时，玩家可购买保险（主注的一半）
           - 若庄家Blackjack，保险赔付2:1；否则保险输掉
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
        
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
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
            if player_value > 21:
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
                first_card_value = self.game.dealer_hand[0].get_value()
                dealer_text = f"庄家 - {first_card_value}点"
            self.dealer_label.config(text=dealer_text)
    
    def disable_action_buttons(self):
        for widget in self.action_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)
    
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
        
        # 庄家区域压缩动画
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
                    pi = lbl.place_info()
                    if 'x' in pi and pi['x'] != '':
                        sx = int(float(pi['x']))
                    else:
                        sx = lbl.winfo_x()
                    start_positions.append(sx)
                    tx = idx * target_spacing
                    target_positions.append(tx)
                deltas = [(target_positions[i] - start_positions[i]) / float(steps) for i in range(len(labels))]
                def do_step(step=1):
                    if self._resetting:
                        for i, lbl in enumerate(labels):
                            try:
                                lbl.place(x=target_positions[i], y=0)
                            except:
                                pass
                        return
                    for i, lbl in enumerate(labels):
                        if i == 0:
                            try:
                                lbl.place(x=0, y=0)
                            except:
                                pass
                            continue
                        new_x = start_positions[i] + deltas[i] * step
                        try:
                            lbl.place(x=int(round(new_x)), y=0)
                        except:
                            try:
                                lbl.place_configure(x=int(round(new_x)), y=0)
                            except:
                                pass
                    if step < steps:
                        self.after(step_time, lambda: do_step(step + 1))
                    else:
                        for i, lbl in enumerate(labels):
                            try:
                                lbl.place(x=target_positions[i], y=0)
                            except:
                                pass
                do_step(1)
        except:
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
            except:
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
                except:
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
                        except:
                            pass
                        try:
                            win.destroy()
                        except:
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
                except:
                    pass
    
    def start_game(self):
        try:
            self.game.main_bet = int(self.main_bet_var.get())
            self.game.push22_bet = int(self.push22_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return
        
        if self.game.main_bet < 10:
            messagebox.showerror("错误", "主注至少需要10块")
            return
        
        total_bet = self.game.main_bet + self.game.push22_bet
        if self.balance < total_bet:
            messagebox.showerror("错误", "余额不足以支付所有下注！")
            return
        
        self.disable_betting_area()
        self.last_win_label.config(text="上局获胜: $0.00")
        self.start_button.config(state=tk.DISABLED)
        self.reset_bets_button.config(state=tk.DISABLED)
        
        self.balance -= total_bet
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        need_shuffle = False
        if not hasattr(self.game, 'deck') or self.game.deck is None:
            need_shuffle = True
        else:
            if len(self.game.deck.cards) <= 60:
                need_shuffle = True
        
        def continue_after_shuffle():
            self.game.deck = Deck(8)
            self.game.player_hand = []
            self.game.dealer_hand = []
            self.game.stage = "dealing"
            self.game.player_done = False
            self.game.insurance_bet = 0
            self.game.insurance_taken = False
            self.game.dealer_blackjack = False
            
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
            self.game.dealer_blackjack = False
            
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
        # 顺序: 庄家明牌 -> 玩家明牌 -> 庄家暗牌
        self.status_label.config(text="发庄家第一张牌")
        dealer_card1 = self.game.dealer_hand[0]
        dealer_card1_label = self.add_card_to_frame(self.dealer_cards_frame, dealer_card1, show_front=True, position=0)
        self.flip_card_animation(dealer_card1_label, dealer_card1, callback=self.after_dealer_card1)
    
    def after_dealer_card1(self):
        self.status_label.config(text="发玩家第一张牌")
        player_card1 = self.game.player_hand[0]
        player_card1_label = self.add_card_to_frame(self.player_cards_frame, player_card1, show_front=True, position=0)
        self.flip_card_animation(player_card1_label, player_card1, callback=self.after_player_card1)
    
    def after_player_card1(self):
        first_card_value = self.game.player_hand[0].get_value()
        player_text = f"玩家 - {first_card_value}点"
        self.player_label.config(text=player_text)
        
        self.status_label.config(text="发庄家第二张牌")
        dealer_card2 = self.game.dealer_hand[1]
        self.dealer_hidden_card_label = self.add_card_to_frame(self.dealer_cards_frame, dealer_card2, show_front=False, position=1)
        self.after_dealer_card2()
    
    def after_dealer_card2(self):
        upcard = self.game.dealer_hand[0]
        if upcard.rank == 'A':
            self.offer_insurance()
        else:
            self.after_insurance()
    
    def offer_insurance(self):
        self.insurance_label.pack(side=tk.LEFT, padx=5)
        self.insurance_display.pack(side=tk.LEFT, padx=1)
        self.insurance_var.set("0")
        
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
            total_bet = self.game.main_bet + self.game.push22_bet + self.game.insurance_bet
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.status_label.config(text=f"已购买保险 ${self.game.insurance_bet}")
            self.after(1000, self.after_insurance)
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
        self.after(1000, self.after_insurance)
    
    def after_insurance(self):
        if self.game.check_blackjack(self.game.dealer_hand):
            self.flip_card_animation(self.dealer_hidden_card_label, self.game.dealer_hand[1], callback=self.dealer_has_blackjack)
        else:
            self.game.stage = "waiting_second_card"
            self.stage_label.config(text="选择第二张牌")
            self.show_second_card_actions()
    
    def dealer_has_blackjack(self):
        self.game.dealer_blackjack = True
        self.update_hand_labels()
        self.status_label.config(text="庄家Blackjack！")
        self.after(2000, self.show_showdown)
    
    def show_second_card_actions(self):
        # 显示三个按钮，但 Stand 禁用
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        action_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        action_frame.pack(pady=5)
        
        self.hit_second_btn = tk.Button(
            action_frame, text="要牌",
            command=self.hit_second_card,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=7
        )
        self.hit_second_btn.pack(side=tk.LEFT, padx=5)
        
        self.stand_second_btn = tk.Button(
            action_frame, text="停牌",
            command=self.stand_second_card,
            font=('Arial', 14), bg='#2196F3', fg='white', width=7,
            state=tk.DISABLED
        )
        self.stand_second_btn.pack(side=tk.LEFT, padx=5)
        
        self.double_second_btn = tk.Button(
            action_frame, text="加倍",
            command=self.double_second_card,
            font=('Arial', 14), bg='#FF9800', fg='white', width=7
        )
        self.double_second_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_label.config(text="请选择：要第二张牌，或加倍并要第二张牌")
    
    def hit_second_card(self):
        # 禁用所有按钮
        self.hit_second_btn.config(state=tk.DISABLED)
        self.stand_second_btn.config(state=tk.DISABLED)
        self.double_second_btn.config(state=tk.DISABLED)
        
        self.game.player_hit()
        new_card = self.game.player_hand[-1]
        position = 1
        new_card_label = self.add_card_to_frame(self.player_cards_frame, new_card, show_front=False, position=position)
        self.flip_card_animation(new_card_label, new_card, callback=self.after_hit_second_card)
    
    def after_hit_second_card(self):
        self.update_hand_labels()
        # 检查玩家点数是否为21，若是则自动停牌
        player_value = self.game.get_hand_value(self.game.player_hand)
        if player_value == 21:
            self.game.player_done = True
            self.status_label.config(text="玩家达到21点，自动停牌")
            self.after(600, self.dealer_turn)
            return
        # 进入正常玩家回合
        self.game.stage = "player_turn"
        self.stage_label.config(text="玩家回合")
        self.show_player_actions()
    
    def stand_second_card(self):
        # 此函数不会调用，因为按钮禁用，但保留以防万一
        pass
    
    def double_second_card(self):
        # 禁用所有按钮
        self.hit_second_btn.config(state=tk.DISABLED)
        self.stand_second_btn.config(state=tk.DISABLED)
        self.double_second_btn.config(state=tk.DISABLED)
        
        if self.balance < self.game.main_bet:
            messagebox.showerror("错误", "余额不足以加倍")
            # 恢复按钮
            self.hit_second_btn.config(state=tk.NORMAL)
            self.stand_second_btn.config(state=tk.DISABLED)
            self.double_second_btn.config(state=tk.NORMAL)
            return
        
        self.balance -= self.game.main_bet
        self.game.main_bet *= 2
        self.main_bet_var.set(self.game.main_bet)
        self.update_balance()
        total_bet = self.game.main_bet + self.game.push22_bet + self.game.insurance_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        self.game.player_hit()
        new_card = self.game.player_hand[-1]
        position = 1
        new_card_label = self.add_card_to_frame(self.player_cards_frame, new_card, show_front=False, position=position)
        
        first_is_ace = (self.game.player_hand[0].rank == 'A')
        if first_is_ace:
            self.flip_card_animation(new_card_label, new_card, callback=self.after_double_second_card_ace)
        else:
            self.flip_card_animation(new_card_label, new_card, callback=self.after_double_second_card_normal)
    
    def after_double_second_card_ace(self):
        self.update_hand_labels()
        self.game.player_done = True
        self.status_label.config(text="第一张牌为A，加倍后回合结束")
        self.after(800, self.dealer_turn)
    
    def after_double_second_card_normal(self):
        self.update_hand_labels()
        # 检查玩家点数是否为21，若是则自动停牌
        player_value = self.game.get_hand_value(self.game.player_hand)
        if player_value == 21:
            self.game.player_done = True
            self.status_label.config(text="玩家达到21点，自动停牌")
            self.after(600, self.dealer_turn)
            return
        # 进入正常玩家回合
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
        
        self.double_button = tk.Button(
            action_frame, text="加倍",
            command=self.double_action,
            font=('Arial', 14), bg='#FF9800', fg='white', width=7
        )
        if self.balance < self.game.main_bet:
            self.double_button.config(state=tk.DISABLED)
        self.double_button.pack(side=tk.LEFT, padx=5)
        
        self.status_label.config(text="请选择您的操作")
    
    def hit_action(self):
        # 立即禁用所有操作按钮
        self.hit_button.config(state=tk.DISABLED)
        self.stand_button.config(state=tk.DISABLED)
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
            self.after(800, self.dealer_turn)
            return
        if new_value == 21:
            self.game.player_done = True
            self.status_label.config(text="玩家达到21点，自动停牌")
            self.after(600, self.dealer_turn)
            return
        # 恢复按钮（除非已经爆牌或21点）
        self.hit_button.config(state=tk.NORMAL)
        self.stand_button.config(state=tk.NORMAL)
        if self.balance >= self.game.main_bet:
            self.double_button.config(state=tk.NORMAL)
        else:
            self.double_button.config(state=tk.DISABLED)
        self.status_label.config(text="请选择您的操作")
    
    def stand_action(self):
        # 立即禁用所有操作按钮
        self.hit_button.config(state=tk.DISABLED)
        self.stand_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)

        self.game.player_done = True
        self.status_label.config(text="玩家停牌")
        self.after(600, self.dealer_turn)
        
    def double_action(self):
        # 立即禁用所有操作按钮
        self.hit_button.config(state=tk.DISABLED)
        self.stand_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)

        if self.balance < self.game.main_bet:
            messagebox.showerror("错误", "余额不足以加倍")
            self.hit_button.config(state=tk.NORMAL)
            self.stand_button.config(state=tk.NORMAL)
            if self.balance >= self.game.main_bet:
                self.double_button.config(state=tk.NORMAL)
            else:
                self.double_button.config(state=tk.DISABLED)
            return

        self.balance -= self.game.main_bet
        self.game.main_bet *= 2
        self.main_bet_var.set(self.game.main_bet)
        self.update_balance()
        total_bet = self.game.main_bet + self.game.push22_bet + self.game.insurance_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        new_value = self.game.player_hit()
        new_card = self.game.player_hand[-1]
        position = len(self.game.player_hand) - 1
        new_card_label = self.add_card_to_frame(self.player_cards_frame, new_card, show_front=False, position=position)

        first_is_ace = (self.game.player_hand[0].rank == 'A')
        if first_is_ace:
            self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_double_ace(new_value))
        else:
            self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_double_normal(new_value))
    
    def after_double_ace(self, new_value):
        self.update_hand_labels()
        if new_value > 21:
            self.status_label.config(text="玩家爆牌！")
        else:
            self.status_label.config(text="第一张牌为A，加倍后回合结束")
        self.game.player_done = True
        self.after(800, self.dealer_turn)
    
    def after_double_normal(self, new_value):
        self.update_hand_labels()
        if new_value > 21:
            self.game.player_done = True
            self.status_label.config(text="玩家爆牌！")
            self.after(800, self.dealer_turn)
        elif new_value == 21:
            self.game.player_done = True
            if len(self.game.player_hand) == 2 and self.game.check_blackjack(self.game.player_hand):
                self.status_label.config(text="玩家 Blackjack！")
                self.handle_blackjack_settlement()
            else:
                self.status_label.config(text="玩家达到21点，自动停牌")
                self.after(600, self.dealer_turn)
            return
        else:
            # 继续玩家回合
            self.game.player_done = False
            self.hit_button.config(state=tk.NORMAL)
            self.stand_button.config(state=tk.NORMAL)
            if self.balance >= self.game.main_bet:
                self.double_button.config(state=tk.NORMAL)
            else:
                self.double_button.config(state=tk.DISABLED)
            self.status_label.config(text="请选择您的操作")
    
    def dealer_turn(self):
        self.game.stage = "dealer_turn"
        self.stage_label.config(text="庄家回合")
        if self.dealer_hidden_card_label:
            self.flip_card_animation(self.dealer_hidden_card_label, self.game.dealer_hand[1], callback=self.after_reveal_dealer_card)
        else:
            self.after_reveal_dealer_card()
    
    def after_reveal_dealer_card(self):
        self.dealer_hit_loop()
    
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
        # 直接结算，不再重复翻转庄家第二张牌（因为 dealer_turn 或 dealer_has_blackjack 中已经翻转过）
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
            elif bet_type == "push22":
                self.push22_var.set(display_text)
        
        if self.game.insurance_bet > 0:
            insurance_win = details.get("insurance", 0)
            if insurance_win > 0:
                self.insurance_var.set(str(int(insurance_win)))
                self.insurance_display.config(bg='gold')
            else:
                self.insurance_var.set("0")
                self.insurance_display.config(bg='white')
        
        player_value = self.game.get_hand_value(self.game.player_hand)
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        status_text = ""
        self.update_hand_labels()
        
        if self.game.dealer_blackjack:
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
        winnings = 0
        details = {
            "main": 0,
            "push22": 0,
            "insurance": 0
        }
        
        player_value = self.game.get_hand_value(self.game.player_hand)
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        dealer_bj = self.game.check_blackjack(self.game.dealer_hand)
        player_bj = self.game.check_blackjack(self.game.player_hand)
        player_suited_bj = self.game.is_suited_blackjack(self.game.player_hand) if player_bj else False
        
        # 主注结算
        main_result = 0
        if player_bj and not dealer_bj:
            # 玩家 Blackjack，庄家不是 Blackjack
            if player_suited_bj:
                # 同花 Blackjack 赔付 2:1
                main_result = self.game.main_bet * 3   # 本金+2倍
            else:
                # 普通 Blackjack 赔付 3:2
                main_result = int(self.game.main_bet * 2.5)  # 本金+1.5倍
            details["main"] = main_result
        elif dealer_bj:
            # 庄家 Blackjack，玩家输或平局
            if player_bj:
                # 双方 Blackjack，平局返还本金
                main_result = self.game.main_bet
                details["main"] = main_result
            else:
                main_result = 0
                details["main"] = 0
        elif player_value > 21:
            main_result = 0
            details["main"] = 0
        elif dealer_value > 21:
            if dealer_value == 22 and not dealer_bj:
                main_result = self.game.main_bet
                details["main"] = self.game.main_bet
            else:
                main_result = self.game.main_bet * 2
                details["main"] = main_result
        elif player_value > dealer_value:
            main_result = self.game.main_bet * 2
            details["main"] = main_result
        elif player_value < dealer_value:
            main_result = 0
            details["main"] = 0
        else:  # 平局
            main_result = self.game.main_bet
            details["main"] = self.game.main_bet
        
        winnings += main_result
        
        # Push22 边注
        if self.game.push22_bet > 0 and dealer_value == 22:
            pattern = self.get_dealer_suit_pattern()
            if pattern == "flush":
                multiplier = 50
            elif pattern == "color":
                multiplier = 20
            else:
                multiplier = 8
            win_amount = self.game.push22_bet * multiplier
            details["push22"] = win_amount + self.game.push22_bet
            winnings += details["push22"]
        else:
            details["push22"] = 0
        
        # 保险
        if self.game.insurance_bet > 0:
            if dealer_bj and not player_bj:
                insurance_win = self.game.insurance_bet * 3
                details["insurance"] = insurance_win
            else:
                details["insurance"] = 0
            winnings += details["insurance"]
        
        return winnings, details
    
    def get_dealer_suit_pattern(self):
        """返回庄家手牌的花色模式: 'flush', 'color', 'mixed'"""
        suits = [card.suit for card in self.game.dealer_hand]
        # 同花：所有花色相同
        if all(s == suits[0] for s in suits):
            return "flush"
        # 同色：红心/方块 vs 黑桃/梅花
        colors = []
        for s in suits:
            if s in ['♥', '♦']:
                colors.append('red')
            else:
                colors.append('black')
        if all(c == colors[0] for c in colors):
            return "color"
        return "mixed"
    
    def reset_bets(self):
        self.main_bet_var.set("0")
        self.push22_var.set("0")
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
            self.stage_label.config(text="下注阶段")
            self.status_label.config(text="设置下注金额并开始游戏")
            self.player_label.config(text="玩家")
            self.dealer_label.config(text="庄家")
            self.main_bet_var.set("0")
            self.push22_var.set("0")
            self.insurance_label.pack_forget()
            self.insurance_display.pack_forget()
            self.insurance_var.set("0")
            for widget in self.bet_widgets.values():
                widget.config(bg='white')
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
    
    def show_restart_button(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        def restart_game():
            # 立即禁用按钮，防止重复点击
            restart_btn.config(state=tk.DISABLED)
            self.reset_game(False)
        
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=restart_game,
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=5)
    
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
                header_frame, text=display_rank, width=4, font=('Arial', 10, 'bold'),
                bg='#F0F0F0', relief=tk.RAISED, bd=1
            )
            label.pack(side=tk.LEFT, padx=1)
        total_label = tk.Label(
            header_frame, text="总计", width=4, font=('Arial', 10, 'bold'),
            bg='#F0F0F0', relief=tk.RAISED, bd=1
        )
        total_label.pack(side=tk.LEFT, padx=1)
        
        for suit in SUITS:
            row_frame = tk.Frame(table_frame, bg='#F0F0F0')
            row_frame.pack(fill=tk.X)
            suit_label = tk.Label(
                row_frame, text=suit, width=4, font=('Arial', 12, 'bold'),
                bg='#F0F0F0', relief=tk.RAISED, bd=1
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
                    row_frame, text=str(count), width=4, font=('Arial', 10),
                    bg=bg_color, relief=tk.SUNKEN, bd=1
                )
                count_label.pack(side=tk.LEFT, padx=1)
            total_label = tk.Label(
                row_frame, text=str(suit_total), width=4, font=('Arial', 10, 'bold'),
                bg='#DDDDDD', relief=tk.RAISED, bd=1
            )
            total_label.pack(side=tk.LEFT, padx=1)
        
        separator = tk.Frame(table_frame, height=2, bg='#333333')
        separator.pack(fill=tk.X, pady=5)
        
        total_row_frame = tk.Frame(table_frame, bg='#F0F0F0')
        total_row_frame.pack(fill=tk.X, padx=8)
        tk.Label(
            total_row_frame, text="总计", width=4, font=('Arial', 10, 'bold'),
            bg='#F0F0F0', relief=tk.RAISED, bd=1
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
                total_row_frame, text=str(total), width=4, font=('Arial', 10, 'bold'),
                bg=bg_color, relief=tk.RAISED, bd=1
            )
            total_label.pack(side=tk.LEFT, padx=1)
        grand_total_label = tk.Label(
            total_row_frame, text=str(grand_total), width=4, font=('Arial', 10, 'bold'),
            bg='#CCCCFF', relief=tk.RAISED, bd=1
        )
        grand_total_label.pack(side=tk.LEFT, padx=1)
        
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

def main(initial_balance=10000, username="Guest"):
    app = BlackjackGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: ${final_balance:.2f}")