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
            return 11  # 初始值，游戏中会调整
        else:
            return int(self.rank)

class Deck:
    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        self.cards = []
        self.generate_deck()
        self.shuffle()
        # 添加切牌位置（大约60张牌的位置）
        self.cut_card_position = len(self.cards) - 60
    
    def generate_deck(self):
        self.cards = [Card(suit, rank) for _ in range(self.num_decks) for suit in SUITS for rank in RANKS]
    
    def shuffle(self):
        """使用shuffle.py洗牌，失败则使用secrets洗牌"""
        try:
            # 获取shuffle.py的路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            shuffle_script = os.path.join(parent_dir, 'A_Tools', 'Card', 'shuffle.py')
            
            # 构建命令行参数
            cmd = [sys.executable, shuffle_script, 'false', str(self.num_decks)]
            
            # 执行shuffle.py
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # 解析JSON输出
                shuffle_data = json.loads(result.stdout)
                shuffled_deck = shuffle_data['deck']
                
                # 将字典转换为Card对象
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
        
        # 回退到secrets洗牌
        self._secrets_shuffle()
    
    def _secrets_shuffle(self):
        """使用secrets模块进行安全的洗牌"""
        n = len(self.cards)
        for i in range(n - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]
        print(f"使用secrets洗牌完成，共{len(self.cards)}张牌")
    
    def deal_card(self):
        # 检查是否需要重新洗牌（剩余牌数 <= 60）
        if len(self.cards) <= 60:
            print(f"牌堆剩余{len(self.cards)}张牌，重新洗牌")
            self.generate_deck()
            self.shuffle()
            # 重新设置切牌位置
            self.cut_card_position = len(self.cards) - 60
            
        if len(self.cards) == 0:
            self.generate_deck()
            self.shuffle()
            # 重新设置切牌位置
            self.cut_card_position = len(self.cards) - 60
            
        return self.cards.pop()
    
    def get_remaining_cards_count(self):
        """获取剩余牌堆中每种牌的数量"""
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
        if not hasattr(self, 'deck') or self.deck is None:
            self.deck = Deck(8)
        self.player_hand = []
        self.dealer_hand = []
        self.main_bet = 0
        self.perfect_pair_bet = 0
        self.twenty_one_plus_three_bet = 0
        self.royal_match_bet = 0
        self.bust_bet = 0
        self.stage = "betting"  # betting, dealing, insurance, player_turn, dealer_turn, showdown
        self.player_done = False
        self.insurance_bet = 0
        self.insurance_taken = False
        self.player_blackjack = False
        self.dealer_blackjack = False
    
    def deal_initial_cards(self):
        self.player_hand = [self.deck.deal_card(), self.deck.deal_card()]
        self.dealer_hand = [self.deck.deal_card(), self.deck.deal_card()]
    
    def get_hand_value(self, hand):
        value = sum(card.get_value() for card in hand)
        num_aces = sum(1 for card in hand if card.rank == 'A')
        
        # 调整A的值
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
        
        # 完美对子 (相同花色和点数)
        if card1.rank == card2.rank and card1.suit == card2.suit:
            return "perfect"
        # 同色对子 (相同颜色和点数)
        elif (card1.rank == card2.rank and 
              ((card1.suit in ['♥', '♦'] and card2.suit in ['♥', '♦']) or 
               (card1.suit in ['♠', '♣'] and card2.suit in ['♠', '♣']))):
            return "colored"
        # 混合对子 (相同点数)
        elif card1.rank == card2.rank:
            return "mixed"
        else:
            return None
    
    def check_twenty_one_plus_three(self):
        if len(self.player_hand) < 2 or len(self.dealer_hand) < 1:
            return None
            
        ranks = [self.player_hand[0].rank, self.player_hand[1].rank, self.dealer_hand[0].rank]
        
        # 检查同花顺
        suits = [self.player_hand[0].suit, self.player_hand[1].suit, self.dealer_hand[0].suit]
        if len(set(suits)) == 1:  # 同花
            # 检查顺子
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
        
        # 检查三条
        if ranks[0] == ranks[1] == ranks[2]:
            if len(set(suits)) == 1:
                return "straight_three_of_a_kind"
            else:
                return "three_of_a_kind"
        
        # 检查顺子
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
        
        # 检查同花
        if len(set(suits)) == 1:
            return "flush"
            
        return None
    
    def check_royal_match(self):
        if len(self.player_hand) < 2:
            return False
            
        card1, card2 = self.player_hand[0], self.player_hand[1]
        
        # 检查是否是同花
        if card1.suit != card2.suit:
            return False
            
        # 检查是否是Q和K
        if (card1.rank == 'Q' and card2.rank == 'K') or (card1.rank == 'K' and card2.rank == 'Q'):
            return "royal"
        else:
            return "suited"

class BlackjackGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("21点")
        self.geometry("1150x650+50+10")
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
            "bust": 0
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
        
        # 使用Poker1扑克牌
        self.current_poker_folder = 'Poker1'
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        
        # 花色映射
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club'
        }

        self.original_images = {}
        
        # 加载背面图片
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
        
        # 加载扑克牌图片
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
        
        # 更新对应的下注变量
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
    
    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=20, width=600, height=250)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 提示文字
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
        
        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=365, width=600, height=250)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=250, padx=10, pady=5)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 顶部信息栏
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
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        
        # 单行放置5个筹码
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
        
        # 默认选中$10筹码
        self.select_chip("$10")

        # 每注限制
        minmax_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        minmax_frame.pack(fill=tk.X, pady=5)
        
        # 标题行
        header_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        
        tk.Label(header_frame, text="主注最低", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="主注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="边注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        
        # 数值行
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$25,000", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        
        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        
        # 第一行：完美对子 + 21+3
        first_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        first_row_frame.pack(fill=tk.X, padx=40, pady=3)

        # 完美对子
        perfect_pair_label = tk.Label(first_row_frame, text="完美对子:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        perfect_pair_label.pack(side=tk.LEFT, padx=1)

        self.perfect_pair_var = tk.StringVar(value="0")
        self.perfect_pair_display = tk.Label(first_row_frame, textvariable=self.perfect_pair_var, font=('Arial', 14), 
                                            bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.perfect_pair_display.pack(side=tk.LEFT, padx=5)
        self.perfect_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("perfect_pair"))
        self.perfect_pair_display.bind("<Button-3>", lambda e: self.clear_bet("perfect_pair"))  # 右键清零
        self.bet_widgets["perfect_pair"] = self.perfect_pair_display

        # 添加间距
        tk.Label(first_row_frame, text="   ", bg='#2a4a3c').pack(side=tk.LEFT, padx=10)

        # 21+3
        twenty_one_plus_three_label = tk.Label(first_row_frame, text="21+3:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        twenty_one_plus_three_label.pack(side=tk.LEFT)

        self.twenty_one_plus_three_var = tk.StringVar(value="0")
        self.twenty_one_plus_three_display = tk.Label(first_row_frame, textvariable=self.twenty_one_plus_three_var, font=('Arial', 14), 
                                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.twenty_one_plus_three_display.pack(side=tk.LEFT, padx=5)
        self.twenty_one_plus_three_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("twenty_one_plus_three"))
        self.twenty_one_plus_three_display.bind("<Button-3>", lambda e: self.clear_bet("twenty_one_plus_three"))  # 右键清零
        self.bet_widgets["twenty_one_plus_three"] = self.twenty_one_plus_three_display

        # 第二行：皇家同花 + 爆！
        second_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        second_row_frame.pack(fill=tk.X, padx=40, pady=3)

        # 皇家同花
        royal_match_label = tk.Label(second_row_frame, text="皇家同花:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        royal_match_label.pack(side=tk.LEFT)

        self.royal_match_var = tk.StringVar(value="0")
        self.royal_match_display = tk.Label(second_row_frame, textvariable=self.royal_match_var, font=('Arial', 14), 
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.royal_match_display.pack(side=tk.LEFT, padx=5)
        self.royal_match_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("royal_match"))
        self.royal_match_display.bind("<Button-3>", lambda e: self.clear_bet("royal_match"))  # 右键清零
        self.bet_widgets["royal_match"] = self.royal_match_display

        # 添加间距
        tk.Label(second_row_frame, text="   ", bg='#2a4a3c').pack(side=tk.LEFT, padx=10)

        # 爆！
        bust_label = tk.Label(second_row_frame, text="爆！:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        bust_label.pack(side=tk.LEFT, padx=2)

        self.bust_var = tk.StringVar(value="0")
        self.bust_display = tk.Label(second_row_frame, textvariable=self.bust_var, font=('Arial', 14), 
                                bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.bust_display.pack(side=tk.LEFT, padx=5)
        self.bust_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bust"))
        self.bust_display.bind("<Button-3>", lambda e: self.clear_bet("bust"))  # 右键清零
        self.bet_widgets["bust"] = self.bust_display

        # 第三行：主注（居中）
        third_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        third_row_frame.pack(fill=tk.X, padx=90, pady=3)

        # 主注
        main_bet_label = tk.Label(third_row_frame, text="主注:", font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white')
        main_bet_label.pack(side=tk.LEFT)

        self.main_bet_var = tk.StringVar(value="0")
        self.main_bet_display = tk.Label(third_row_frame, textvariable=self.main_bet_var, font=('Arial', 16, 'bold'), 
                                    bg='white', fg='black', width=8, relief=tk.SUNKEN, padx=5)
        self.main_bet_display.pack(side=tk.LEFT, padx=10)
        self.main_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("main"))
        self.main_bet_display.bind("<Button-3>", lambda e: self.clear_bet("main"))  # 右键清零
        self.bet_widgets["main"] = self.main_bet_display
        
        # 游戏操作按钮框架
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X)

        # 创建一个框架来容纳重置按钮和开始游戏按钮
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

        # 添加"重置金额"按钮
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重置金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
        self.reset_bets_button.config(state=tk.NORMAL)

        # 开始游戏按钮
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        self.start_button.config(state=tk.NORMAL)
        
        # 状态信息
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)
        
        # 本局下注和上局获胜金额显示
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 本局下注金额
        self.current_bet_label = tk.Label(
            bet_info_frame, text="本局下注: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        
        # 上局获胜金额
        self.last_win_label = tk.Label(
            bet_info_frame, text="上局获胜: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)
        
        # 添加游戏规则按钮
        rules_btn = tk.Button(
            bet_info_frame, text="ℹ️",
            command=self.show_game_instructions,   # 左键（默认 command）
            font=('Arial', 8), bg='#4B8BBE', fg='white', width=2, height=1
        )
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)

        # 右键绑定显示剩余牌堆（注意：show_remaining_cards 接受 event=None）
        rules_btn.bind("<Button-3>", self.show_remaining_cards)
    
    def show_remaining_cards(self, event=None):
        """显示剩余牌堆的统计信息"""
        # 获取剩余牌堆统计
        remaining_cards = self.game.deck.get_remaining_cards_count()
        
        # 创建新窗口
        win = tk.Toplevel(self)
        win.title("剩余牌堆统计")
        win.geometry("600x400")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        
        # 主框架
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题
        title_label = tk.Label(
            main_frame, 
            text=f"剩余{len(self.game.deck.cards)}张牌",
            font=('Arial', 16, 'bold'),
            bg='#F0F0F0',
            fg='#333333'
        )
        title_label.pack(pady=(0, 10))
        
        # 创建表格框架
        table_frame = tk.Frame(main_frame, bg='#F0F0F0')
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # 表头 - 点数
        header_frame = tk.Frame(table_frame, bg='#F0F0F0')
        header_frame.pack(fill=tk.X)
        
        # 空单元格（用于花色列）
        tk.Label(header_frame, text="", width=6, bg='#F0F0F0').pack(side=tk.LEFT)
        
        # 点数标题
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
        
        # 总计列
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
        
        # 花色行和数据
        for suit in SUITS:
            row_frame = tk.Frame(table_frame, bg='#F0F0F0')
            row_frame.pack(fill=tk.X)
            
            # 花色标签
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
            
            # 每种点数的数量
            for rank in RANKS:
                count = remaining_cards[suit][rank]
                suit_total += count
                
                # 根据数量设置背景色
                if count == 0:
                    bg_color = '#FFCCCC'  # 红色，表示没有牌了
                elif count < 4:
                    bg_color = '#FFFFCC'  # 黄色，表示牌较少
                else:
                    bg_color = '#CCFFCC'  # 绿色，表示牌充足
                
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
            
            # 花色总计
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
        
        # 分隔线
        separator = tk.Frame(table_frame, height=2, bg='#333333')
        separator.pack(fill=tk.X, pady=5)
        
        # 总计行
        total_row_frame = tk.Frame(table_frame, bg='#F0F0F0')
        total_row_frame.pack(fill=tk.X, padx=8)
        
        # 总计标签
        tk.Label(
            total_row_frame, 
            text="总计", 
            width=4, 
            font=('Arial', 10, 'bold'),
            bg='#F0F0F0',
            relief=tk.RAISED,
            bd=1
        ).pack(side=tk.LEFT, padx=1)
        
        # 每种点数的总计
        rank_totals = {}
        for rank in RANKS:
            rank_totals[rank] = 0
            for suit in SUITS:
                rank_totals[rank] += remaining_cards[suit][rank]
        
        grand_total = 0
        for rank in RANKS:
            total = rank_totals[rank]
            grand_total += total
            
            # 根据总数设置背景色
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
        
        # 总牌数
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
        
        # 关闭按钮
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)
    
    def clear_bet(self, bet_type):
        """将指定类型的赌注归零"""
        if self.game.stage != "betting":
            return  # 只有在投注阶段才能清零
            
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
        
        # 视觉反馈：短暂变为红色然后恢复
        widget = self.bet_widgets[bet_type]
        original_color = widget.cget('bg')
        widget.config(bg='#FFCDD2')
        self.after(300, lambda: widget.config(bg=original_color))
    
    def show_game_instructions(self):
        """显示游戏规则说明"""
        win = tk.Toplevel(self)
        win.title("21点游戏规则")
        win.geometry("900x700")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        
        # 创建主框架
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建画布用于滚动
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        # 创建内部框架放置所有内容
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        # 游戏规则文本
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
        
        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 添加关闭按钮
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)
        
        # 绑定鼠标滚轮滚动
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    
    def select_chip(self, chip_text):
        """选择筹码，并更新筹码的高亮状态"""
        self.selected_chip = chip_text
        # 重置所有筹码的边框
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item_id)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break

        # 给选中的筹码加金色高亮
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
        """更新玩家和庄家的手牌点数显示"""
        # 计算玩家当前点数
        if self.game.player_hand:
            player_value = self.game.get_hand_value(self.game.player_hand)
            
            if self.game.check_blackjack(self.game.player_hand):
                player_text = "玩家 - BJ"
            elif player_value > 21:
                player_text = f"玩家 - {player_value}点 (爆牌)"
            else:
                player_text = f"玩家 - {player_value}点"
            self.player_label.config(text=player_text)
        
        # 计算庄家当前点数
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
                # 只显示第一张牌的值
                first_card_value = self.game.dealer_hand[0].get_value()
                dealer_text = f"庄家 - {first_card_value}点"
            self.dealer_label.config(text=dealer_text)
    
    def disable_action_buttons(self):
        self.hit_button.config(state=tk.DISABLED)
        self.stand_button.config(state=tk.DISABLED)
        self.surrender_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)
        
    def enable_action_buttons(self):
        """启用所有操作按钮"""
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)
    
    def _create_scaled_image(self, card, width, height, use_back=False):
        """创建缩放后的图像"""
        if use_back:
            img = self.original_images["back"].copy()
        else:
            img = self.original_images[(card.suit, card.rank)].copy()
        
        img = img.resize((width, height), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    
    def flip_card_animation(self, card_label, card, callback=None):
        """翻牌动画（已修正为使用 100x150 标准尺寸）"""
        def flip_step(step=0):
            if card_label is None:
                return

            steps = 12
            if step > steps:
                # 翻牌完成，显示原始牌面（完整尺寸）
                card_label.config(image=self.card_images.get((card.suit, card.rank), self.back_image))
                # 确保引用防被 GC（通常 self.card_images 已持有）
                if callback:
                    callback()
                return

            # 翻牌动画逻辑（左右缩放）
            half = steps // 2
            if step <= half:
                ratio = 1 - (step / float(half))
                use_back = True
            else:
                ratio = (step - half) / float(half)
                use_back = False

            # 使用标准全尺寸
            full_w, full_h = 100, 150
            w = max(1, int(full_w * ratio))

            # 生成缩放后的图像（宽动态，高保持 full_h，避免变矮）
            img = self._create_scaled_image(card, w, full_h, use_back=use_back)
            if not hasattr(self, '_temp_flip_images'):
                self._temp_flip_images = {}
            # 保持对临时图像的引用，防止被 GC
            self._temp_flip_images[id(card_label)] = img

            card_label.config(image=img)
            # 下一帧
            self.after(20, lambda: flip_step(step + 1))

        flip_step()
    
    def add_card_to_frame(self, frame, card, show_front=True, position=None):
        """添加一张牌到指定框架（统一牌尺寸为 100x150）。
        当为庄家区域（self.dealer_cards_frame）且牌数超过5张时，
        用0.5秒把除第1张以外的牌向左移动，使相邻间距变为 -60（即 x_spacing = 40）。
        返回创建的 card_label（并把它加入 self.active_card_labels）。
        """
        # 图像选择
        if show_front:
            card_img = self.card_images.get((card.suit, card.rank), self.back_image)
        else:
            card_img = self.back_image

        card_label = tk.Label(frame, image=card_img, bg='#2a4a3c')

        full_w, full_h = 100, 150
        # 默认正向间距（当不需要挤压时）
        normal_spacing = full_w + 10  # =110

        if position is None:
            # 默认添加到末尾（pack 保持老行为）
            card_label.pack(side=tk.LEFT, padx=5)
        else:
            # 使用 place 放置，宽高固定
            # 默认按未压缩间距摆放（与原实现保持一致）
            x = position * normal_spacing
            card_label.place(x=x, y=0, width=full_w, height=full_h)

        card_label.card = card
        card_label.is_face_up = show_front

        # 添加到活动卡片列表并保持对 image 的引用
        self.active_card_labels.append(card_label)

        # --- 特殊处理：如果这是庄家区域，并且牌数超过5张（即需要压缩） ---
        try:
            # 当前庄家区内所有卡片（按子控件顺序）
            labels = [w for w in frame.winfo_children() if isinstance(w, tk.Label)]
            count = len(labels)
            # 当超过5张（第6张及以后）时，启动移动动画，使相邻间距 = -70 => x_spacing = full_w - 70
            if count > 5:
                target_spacing = full_w - 70  # 100 - 70 = 30
                duration_ms = 750
                # 动画步数（保证平滑）：每步间隔约20ms
                step_time = 20
                steps = max(1, int(duration_ms / step_time))

                # 计算每个 label 的起始 x 和目标 x（第0张保持在 x=0）
                start_positions = []
                target_positions = []
                for idx, lbl in enumerate(labels):
                    # 读取当前 x（尽量先用 place_info，否则用 winfo_x）
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
                        # widget 可能是用 pack 放的，使用 winfo_x 作为当前位置
                        try:
                            sx = lbl.winfo_x()
                        except Exception:
                            sx = 0
                    start_positions.append(sx)
                    # 目标位置：第0张固定在0，其余按 index * target_spacing
                    tx = idx * target_spacing
                    target_positions.append(tx)

                # 计算每步偏移量
                deltas = [(target_positions[i] - start_positions[i]) / float(steps) for i in range(len(labels))]

                # 执行动画（只移动第1张及以后的标签；第0张保持不动）
                def do_step(step=1):
                    if self._resetting:
                        # 若正在 reset，立即跳出并把位置设为目标（防止残留动画）
                        for i, lbl in enumerate(labels):
                            try:
                                lbl.place(x=target_positions[i], y=0)
                            except Exception:
                                pass
                        return

                    for i, lbl in enumerate(labels):
                        if i == 0:
                            # 保持第一张不动（但确保放置为 x=0）
                            try:
                                lbl.place(x=0, y=0)
                            except Exception:
                                pass
                            continue
                        # 计算并设置新 x
                        new_x = start_positions[i] + deltas[i] * step
                        try:
                            lbl.place(x=int(round(new_x)), y=0)
                        except Exception:
                            # 若放置失败（例如控件还没 map），尝试使用 place_configure
                            try:
                                lbl.place_configure(x=int(round(new_x)), y=0)
                            except Exception:
                                pass

                    if step < steps:
                        self.after(step_time, lambda: do_step(step + 1))
                    else:
                        # 确保最终位置精确到目标值
                        for i, lbl in enumerate(labels):
                            try:
                                lbl.place(x=target_positions[i], y=0)
                            except Exception:
                                pass

                # 启动动画
                do_step(1)
        except Exception:
            # 任何意外不要中断主流程，仅记录/忽略
            pass

        return card_label
    
    def play_shuffle_animation(self, duration_ms=10000, callback=None):
        """
        在一个 modal 窗口上播放洗牌动画，然后调用 callback。
        duration_ms: 动画总时长（毫秒），默认 10000（10 秒）。
        """
        try:
            # 创建模态窗口
            win = tk.Toplevel(self)
            win.title("正在洗牌...")
            win.resizable(False, False)
            win.transient(self)
            win.grab_set()
            win.configure(bg='#2a2a2a')

            W, H = 520, 220
            win.geometry(f"{W}x{H}")

            canvas = tk.Canvas(win, width=W, height=H, bg='#2a2a2a', highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # 生成若干张小背面图（防止 GC：保存在 self._shuffle_imgs）
            small_w, small_h = 90, 135
            try:
                back_img_orig = self.original_images.get("back")
                if back_img_orig is None:
                    # 回退到已有的 back_image
                    back_img = Image.new('RGBA', (small_w, small_h), (0, 0, 0, 255))
                else:
                    back_img = back_img_orig.copy().resize((small_w, small_h), Image.LANCZOS)
            except Exception:
                back_img = Image.new('RGBA', (small_w, small_h), (0, 0, 0, 255))

            # 创建若干 canvas image 项，分布在中间区域
            num_cards = 10
            center_x = W // 2
            center_y = H // 2
            spread = 200  # 总横向分布宽度
            start_x = center_x - spread // 2
            gap = spread // max(1, num_cards - 1)

            # prepare PhotoImages and items
            if not hasattr(self, '_shuffle_imgs'):
                self._shuffle_imgs = []
            else:
                self._shuffle_imgs.clear()

            items = []
            for i in range(num_cards):
                # 轻微尺寸差（制造层次）
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
                y = center_y + (i % 2) * 6  # 交错些
                item = canvas.create_image(x, y, image=tkimg, anchor='center')
                items.append({
                    'id': item,
                    'base_x': x,
                    'base_y': y,
                    'phase': (i * 2 * math.pi) / max(1, num_cards),
                    'amp': 10 + (i % 4) * 4,
                    'z': i
                })

            # 顶部文字
            txt = canvas.create_text(W//2, 18, text="正在洗牌，请稍候...", fill='white', font=('Arial', 14, 'bold'))

            # 动画循环参数
            start_time = self.winfo_toplevel().after_info if hasattr(self.winfo_toplevel(), 'after_info') else None
            t0 = self.winfo_toplevel().tk.call('clock', 'milliseconds')  # 当前毫秒
            # Note: 上面取法跨平台稳定性较好；但我们用内部计数 step 来控制时间戳

            total_steps = max(1, int(duration_ms / 40))  # 每 ~40ms 一帧
            step = {'i': 0}

            def anim_step():
                i = step['i']
                frac = i / float(total_steps)
                # 让卡片做左右小幅摆动并周期性交换 z-order（模拟洗牌）
                for idx, it in enumerate(items):
                    pid = it['id']
                    phase = it['phase']
                    amp = it['amp']
                    # x 波动（由 sin 控制）与一个向中心/离中心的微小位移
                    dx = math.sin(phase + frac * 12.0) * amp * (0.8 + 0.4 * math.sin(frac * 2 * math.pi + idx))
                    dy = math.sin(phase * 0.7 + frac * 6.0) * (amp / 6.0)
                    new_x = it['base_x'] + dx * (1.0 - frac * 0.3)  # 逐渐缩小幅度
                    new_y = it['base_y'] + dy
                    canvas.coords(pid, new_x, new_y)

                    # 在某些帧交替提升/降低 z
                    if (i + idx) % 20 < 10:
                        canvas.tag_raise(pid)
                    else:
                        canvas.tag_lower(pid)

                step['i'] += 1
                if step['i'] <= total_steps:
                    # 继续动画
                    win.after(40, anim_step)
                else:
                    # 动画结束：淡出并关闭窗口
                    def do_close():
                        try:
                            win.grab_release()
                        except Exception:
                            pass
                        try:
                            win.destroy()
                        except Exception:
                            pass
                        # 调用回调（如果有）
                        if callback:
                            try:
                                callback()
                            except Exception as e:
                                print(f"[shuffle callback] 错误: {e}")

                    # 小淡出：隐藏控件 -> 直接销毁
                    win.after(100, do_close)

            # 启动动画
            anim_step()

        except Exception as e:
            # 若动画失败，直接调用回调以免阻塞流程
            print(f"[play_shuffle_animation] 动画失败: {e}")
            if callback:
                try:
                    callback()
                except Exception:
                    pass
    
    def start_game(self):
        """开始一局 —— 使用长期牌靴（8 副），仅当剩余卡数 <= 60 时弹出洗牌动画（10秒），动画结束后重洗并继续发牌。"""
        try:
            # 读取下注数（保留你现有的校验/上限逻辑）
            self.game.main_bet = int(self.main_bet_var.get())
            self.game.perfect_pair_bet = int(self.perfect_pair_var.get())
            self.game.twenty_one_plus_three_bet = int(self.twenty_one_plus_three_var.get())
            self.game.royal_match_bet = int(self.royal_match_var.get())
            self.game.bust_bet = int(self.bust_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return

        # 示例：检查最低主注等（你原来的校验逻辑保留）
        if self.game.main_bet < 10:
            messagebox.showerror("错误", "主注至少需要10块")
            return

        total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                    self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                    self.game.bust_bet)

        if self.balance < total_bet:
            messagebox.showerror("错误", "余额不足以支付所有下注！")
            return

        self.start_button.config(state=tk.DISABLED)
        self.reset_bets_button.config(state=tk.DISABLED)

        # 扣除下注（你原来的处理）
        self.balance -= total_bet
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        # --- 牌靴管理（保持你原来检测方式） ---
        def _cards_remaining(deck):
            """尝试多种方式获取牌靴剩余张数，兼容不同 Deck 实现。"""
            if deck is None:
                return 0
            for attr in ("cards_left", "remaining", "remaining_cards"):
                fn = getattr(deck, attr, None)
                if callable(fn):
                    try:
                        return int(fn())
                    except Exception:
                        pass
            if hasattr(deck, "cards"):
                try:
                    return len(deck.cards)
                except Exception:
                    pass
            try:
                return len(deck)
            except Exception:
                return 0

        # 判断是否需要重洗
        need_new_shoe = False
        if not hasattr(self.game, "deck") or self.game.deck is None:
            need_new_shoe = True
        else:
            remaining = _cards_remaining(self.game.deck)
            if remaining <= 60:
                need_new_shoe = True

        # 定义发牌前后续流程（重用原有发牌流程）
        def continue_after_shuffle():
            # 如果需要，创建新牌靴并做一次“切牌弃掉一张”
            if need_new_shoe:
                try:
                    self.game.deck = Deck(8)
                    try:
                        burned = self.game.deck.deal_card()
                        print(f"[牌靴] 重洗并切牌，弃掉一张：{burned}")
                    except Exception as e:
                        print(f"[牌靴] 切牌弃牌失败：{e}")
                except Exception as e:
                    self.game.deck = None
                    print(f"[牌靴] 无法生成新牌靴：{e}")

            # --- 保留原有局内状态重置（但不要重置下注） ---
            self.game.player_hand = []
            self.game.dealer_hand = []
            self.game.stage = "dealing"
            self.game.player_done = False
            self.game.insurance_bet = 0
            self.game.insurance_taken = False
            self.game.player_blackjack = False
            self.game.dealer_blackjack = False

            # 清空UI牌容器
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()

            # 发初始牌（假设 deal_initial_cards 会从 self.game.deck 发牌）
            try:
                self.game.deal_initial_cards()
            except Exception as e:
                print(f"[发牌] 初始发牌失败：{e}")
                messagebox.showerror("错误", "无法从牌靴发牌（牌靴可能未正确初始化）。")
                try:
                    self.game.deck = Deck(8)
                    self.game.deck.deal_card()  # 切牌
                    self.game.deal_initial_cards()
                except Exception as e2:
                    print(f"[发牌] 重试仍然失败：{e2}")
                    return

            # 更新 UI 状态并进入后续发牌/玩家回合逻辑
            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            # 启动发牌序列（你的原实现）
            self.deal_card_sequence()

        # 如果需要重洗则先播放 10s 洗牌动画，然后再继续；否则直接继续
        if need_new_shoe:
            try:
                # 播放洗牌动画（10秒），动画结束后执行 continue_after_shuffle
                self.play_shuffle_animation(duration_ms=10000, callback=continue_after_shuffle)
                # 直接 return，剩下由回调继续执行
                return
            except Exception as e:
                print(f"[start_game] 播放洗牌动画失败，直接继续：{e}")
                # 若动画失败则直接继续重洗并发牌
                continue_after_shuffle()
        else:
            continue_after_shuffle()
    
    def deal_card_sequence(self):
        """发牌序列"""
        # 第一步：发玩家第一张牌
        self.status_label.config(text="发玩家第一张牌")
        player_card1 = self.game.player_hand[0]
        player_card1_label = self.add_card_to_frame(self.player_cards_frame, player_card1, show_front=True, position=0)
        
        # 翻牌动画
        self.flip_card_animation(player_card1_label, player_card1, callback=self.after_player_card1)
    
    def after_player_card1(self):
        """玩家第一张牌发完后"""
        first_card_value = self.game.player_hand[0].get_value()
        player_text = f"玩家 - {first_card_value}点"
        self.player_label.config(text=player_text)
        
        # 第二步：发庄家第一张牌
        self.status_label.config(text="发庄家第一张牌")
        dealer_card1 = self.game.dealer_hand[0]
        dealer_card1_label = self.add_card_to_frame(self.dealer_cards_frame, dealer_card1, show_front=True, position=0)
        
        # 翻牌动画
        self.flip_card_animation(dealer_card1_label, dealer_card1, callback=self.after_dealer_card1)
    
    def after_dealer_card1(self):
        """庄家第一张牌发完后"""
        self.update_hand_labels()
        
        # 第三步：发玩家第二张牌
        self.status_label.config(text="发玩家第二张牌")
        player_card2 = self.game.player_hand[1]
        player_card2_label = self.add_card_to_frame(self.player_cards_frame, player_card2, show_front=True, position=1)
        
        # 翻牌动画
        self.flip_card_animation(player_card2_label, player_card2, callback=self.after_player_card2)
    
    def after_player_card2(self):
        """玩家第二张牌发完后（处理庄家暗牌后续逻辑）
        - 如果庄家明牌为 'A'：走保险流程（原逻辑）
        - 如果庄家明牌为 10/J/Q/K 并且暗牌为 'A'：立即翻牌并进入庄家 Blackjack 处理（你要求的对称检查）
        - 否则：继续常规流程
        """
        self.update_hand_labels()

        # 第四步：发庄家第二张牌（背面）已经在 caller 中做过，这里直接拿暗牌引用
        dealer_card2 = self.game.dealer_hand[1]
        self.dealer_hidden_card_label = self.add_card_to_frame(self.dealer_cards_frame, dealer_card2, show_front=False, position=1)

        # 更新点数显示
        self.update_hand_labels()

        # 检查庄家的明牌/暗牌组合
        upcard = self.game.dealer_hand[0]
        holecard = self.game.dealer_hand[1]

        # 明牌为 A 的情况：提供保险（原有逻辑）
        if upcard.rank == 'A':
            self.offer_insurance()
            return

        # 如果明牌是 10/J/Q/K，且暗牌是 A -> 庄家为 Blackjack（立刻翻牌并进入处理）
        if upcard.get_value() == 10 and holecard.rank == 'A':
            # 直接把暗牌翻开并进入 dealer_has_blackjack 回调
            # 使用翻牌动画以保持一致性
            self.flip_card_animation(self.dealer_hidden_card_label, holecard, callback=self.dealer_has_blackjack)
            return

        # 否则按原流程继续（既不提供保险也不直接揭示）
        self.check_blackjack_and_continue()
        
    def offer_insurance(self):
        """提供保险选项"""
        self.game.stage = "insurance"
        self.stage_label.config(text="保险选项")
        self.status_label.config(text="庄家明牌是A，是否购买保险？")
        
        # 清除操作按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        insurance_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        insurance_frame.pack(pady=5)
        
        # 购买保险按钮
        self.insurance_btn = tk.Button(
            insurance_frame, text="购买保险",
            command=self.take_insurance,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=10
        )
        self.insurance_btn.pack(side=tk.LEFT, padx=5)
        
        # 不购买保险按钮
        self.no_insurance_btn = tk.Button(
            insurance_frame, text="不购买",
            command=self.decline_insurance,
            font=('Arial', 14), bg='#F44336', fg='white', width=10
        )
        self.no_insurance_btn.pack(side=tk.LEFT, padx=5)
    
    def take_insurance(self):
        """购买保险"""
        # 立即禁用保险按钮
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
            
            # 更新主注显示
            self.main_bet_var.set(f"{int(self.game.main_bet)}🔒")

            total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                        self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                        self.game.bust_bet + self.game.insurance_bet)

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.status_label.config(text=f"已购买保险 ${self.game.insurance_bet}")
            self.after(1000, self.check_dealer_blackjack)
        else:
            messagebox.showerror("错误", "余额不足以购买保险")
            self.decline_insurance()

    def decline_insurance(self):
        """不购买保险"""
        # 立即禁用保险按钮
        if hasattr(self, 'insurance_btn'):
            self.insurance_btn.config(state=tk.DISABLED)
        if hasattr(self, 'no_insurance_btn'):
            self.no_insurance_btn.config(state=tk.DISABLED)
        
        self.game.insurance_taken = False
        self.status_label.config(text="未购买保险")
        self.after(1000, self.check_dealer_blackjack)
    
    def check_dealer_blackjack(self):
        """检查庄家是否有Blackjack"""
        # 检查庄家第二张牌是否是10点牌
        dealer_card2 = self.game.dealer_hand[1]
        if dealer_card2.get_value() == 10:
            # 庄家有Blackjack，翻开暗牌
            self.flip_card_animation(self.dealer_hidden_card_label, dealer_card2, callback=self.dealer_has_blackjack)
        else:
            # 庄家没有Blackjack，继续游戏
            self.check_blackjack_and_continue()
    
    def dealer_has_blackjack(self):
        """庄家有Blackjack"""
        self.game.dealer_blackjack = True
        self.update_hand_labels()
        
        if self.game.insurance_taken:
            # 支付保险
            self.balance += self.game.insurance_bet
            self.update_balance()
        self.status_label.config(text="庄家Blackjack！")
        
        self.after(2000, self.show_showdown)
    
    def check_blackjack_and_continue(self):
        """检查Blackjack并继续游戏"""
        # 检查玩家是否有Blackjack
        if self.game.check_blackjack(self.game.player_hand):
            self.game.player_blackjack = True
            
            # 检查是否有"爆！"下注
            has_bust_bet = self.game.bust_bet > 0
            
            if has_bust_bet:
                # 有"爆！"下注：翻开庄家暗牌并正常补牌
                self.status_label.config(text="玩家有Blackjack！")
                # 翻开庄家暗牌
                if self.dealer_hidden_card_label:
                    dealer_card2 = self.game.dealer_hand[1]
                    self.flip_card_animation(self.dealer_hidden_card_label, dealer_card2, 
                                        callback=lambda: self.after(1000, self.dealer_turn))
                else:
                    self.after(1000, self.dealer_turn)
            else:
                # 没有"爆！"下注：翻开庄家第一张手牌直接结算
                self.status_label.config(text="玩家有Blackjack！")
                # 翻开庄家暗牌但不补牌，直接结算
                if self.dealer_hidden_card_label:
                    dealer_card2 = self.game.dealer_hand[1]
                    self.flip_card_animation(self.dealer_hidden_card_label, dealer_card2, 
                                        callback=lambda: self.after(1000, self.show_showdown))
                else:
                    self.after(1000, self.show_showdown)
        else:
            # 进入玩家回合
            self.game.stage = "player_turn"
            self.stage_label.config(text="玩家回合")
            self.show_player_actions()
    
    def show_player_actions(self):
        """显示玩家操作按钮"""
        # 清除操作按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        action_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        action_frame.pack(pady=5)
        
        # 要牌按钮
        self.hit_button = tk.Button(
            action_frame, text="要牌",
            command=self.hit_action,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=7
        )
        self.hit_button.pack(side=tk.LEFT, padx=5)
        
        # 停牌按钮
        self.stand_button = tk.Button(
            action_frame, text="停牌",
            command=self.stand_action,
            font=('Arial', 14), bg='#2196F3', fg='white', width=7
        )
        self.stand_button.pack(side=tk.LEFT, padx=5)
        
        # 检查是否可以加倍
        can_double = (self.balance >= self.game.main_bet and 
                     len(self.game.player_hand) == 2)
        
        # 加倍按钮
        self.double_button = tk.Button(
            action_frame, text="加倍",
            command=self.double_action,
            font=('Arial', 14), bg='#FF9800', fg='white', width=7,
            state=tk.NORMAL if can_double else tk.DISABLED
        )
        self.double_button.pack(side=tk.LEFT, padx=5)
        
        # 检查是否可以投降
        can_surrender = len(self.game.player_hand) == 2
        
        # 投降按钮
        self.surrender_button = tk.Button(
            action_frame, text="投降",
            command=self.surrender_action,
            font=('Arial', 14), bg='#F44336', fg='white', width=7,
            state=tk.NORMAL if can_surrender else tk.DISABLED
        )
        self.surrender_button.pack(side=tk.LEFT, padx=5)
        
        self.status_label.config(text="请选择您的操作")
    
    def hit_action(self):
        """玩家要牌 -- 按下时立刻禁用4个操作按钮，再发一张牌并播放翻牌动画。"""
        # 立刻禁用玩家四个操作按钮（防止重复点击）
        self.hit_button.config(state=tk.DISABLED)
        self.stand_button.config(state=tk.DISABLED)
        self.surrender_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)

        # 玩家要牌（逻辑在 BlackjackGame.player_hit）
        new_value = self.game.player_hit()
        new_card = self.game.player_hand[-1]

        # 把牌的 UI 放上去（先背面，翻牌动画会展示面）
        position = len(self.game.player_hand) - 1
        new_card_label = self.add_card_to_frame(self.player_cards_frame, new_card, show_front=False, position=position)

        # 翻牌动画，回调到 after_hit 处理后续逻辑
        self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_hit(new_value))

    def after_hit(self, new_value):
        """玩家拿到牌后处理：
        - 若爆牌：如果玩家有 '爆！' 边注，则仍让庄家正常补牌（dealer_turn），否则直接结算；
        - 若刚好21：自动视为停牌（player_done）并进入庄家回合（dealer_turn）；
        - 否则：恢复"要牌/停牌"为可用（投降/加倍仍禁用）。
        """
        self.update_hand_labels()

        # 爆牌情况
        if new_value > 21:
            self.game.player_done = True
            self.status_label.config(text="玩家爆牌！")

            # 如果玩家押了"爆！"边注，则必须让庄家继续正常补牌以决定爆！的赔付（根据你的 calculate_winnings 逻辑）。
            # 否则可以直接进入结算。
            try:
                bust_bet = getattr(self.game, "bust_bet", 0)
            except Exception:
                bust_bet = 0

            if bust_bet and bust_bet > 0:
                # 等一下再让庄家翻牌并补牌
                self.after(800, self.dealer_turn)
            else:
                # 直接结算（保持原来行为）
                self.after(800, self.show_showdown)
            return

        # 刚好21点 -> 自动停牌（不需玩家手动按停）
        if new_value == 21:
            self.game.player_done = True
            self.status_label.config(text="玩家达到21点，自动停牌")
            # 小延迟后进入庄家回合
            self.after(600, self.dealer_turn)
            return

        # 否则仍在玩家回合：恢复"要牌"和"停牌"为可用；"加倍"和"投降"保持禁用（规则：拿到下一张牌后这两项不可再用）
        # 有时按钮实例可能还没创建（保护性判断）
        self.hit_button.config(state=tk.NORMAL)
        self.stand_button.config(state=tk.NORMAL)
        # 保证加倍与投降仍禁用（拿到下一张牌后不可用）
        self.surrender_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)

        self.status_label.config(text="请选择您的操作")

    def stand_action(self):
        """玩家停牌：按下立刻禁用四按钮，然后标记停牌并启动庄家回合。"""
        # 立刻禁用防止二次点击
        try:
            self.disable_action_buttons()
        except Exception:
            pass

        self.game.player_done = True
        self.status_label.config(text="玩家停牌")
        # 小延迟后开始庄家回合（保持与其他流程一致）
        self.after(600, self.dealer_turn)


    def double_action(self):
        """玩家加倍：按下立刻禁用四按钮，扣除加倍金额，发一张牌后进入庄家回合（玩家结束）。"""
        # 立刻禁用
        try:
            self.disable_action_buttons()
        except Exception:
            pass

        # 余额检查
        if self.balance < self.game.main_bet:
            messagebox.showerror("错误", "余额不足以加倍")
            # 余额不足要把按键恢复（恢复为原状态由 show_player_actions 控制，这里直接恢复基础两个）
            try:
                self.hit_button.config(state=tk.NORMAL)
                self.stand_button.config(state=tk.NORMAL)
            except Exception:
                pass
            return

        # 扣除加倍金额并把主注翻倍（保持原实现）
        self.balance -= self.game.main_bet
        self.game.main_bet *= 2
        self.main_bet_var.set(self.game.main_bet)
        self.update_balance()

        total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                    self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                    self.game.bust_bet + self.game.insurance_bet)

        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        # 玩家要一张牌（加倍规则：只要一张牌）
        new_value = self.game.player_hit()
        new_card = self.game.player_hand[-1]

        # 显示牌并翻牌
        position = len(self.game.player_hand) - 1
        new_card_label = self.add_card_to_frame(self.player_cards_frame, new_card, show_front=False, position=position)
        self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_double(new_value))


    def after_double(self, new_value):
        """加倍后处理：更新点数、标记玩家回合结束，若爆牌仍进入庄家回合。"""
        self.update_hand_labels()
        self.game.player_done = True

        if new_value > 21:
            self.status_label.config(text="玩家爆牌（加倍）！")
        else:
            self.status_label.config(text="玩家加倍完成")
        # 一样进入庄家回合结算
        self.after(800, self.dealer_turn)


    def surrender_action(self):
        """玩家投降：按下立刻禁用四按钮，退回一半主注，并在界面将主注显示为'投降'直到 reset。"""
        # 立刻禁用
        try:
            self.disable_action_buttons()
        except Exception:
            pass

        # 退还一半主注
        surrender_amount = 0
        try:
            surrender_amount = self.game.main_bet / 2
        except Exception:
            surrender_amount = 0

        self.balance += surrender_amount

        # 在游戏内部把主注标记为已投降（你的 calculate_winnings 已检查 game.main_bet == 0 来判断投降）
        self.game.main_bet = 0

        # UI上显示为"投降"，直到 reset_game 被调用（reset_game 会把 main_bet_var 重置为 "0"）
        try:
            self.main_bet_var.set("投降")
        except Exception:
            pass

        self.update_balance()
        self.game.player_done = True
        self.status_label.config(text="玩家投降，退还一半主注")
        # 延迟后直接进入结算（投降通常立即结束）
        self.after(800, self.show_showdown)
    
    def dealer_turn(self):
        """庄家回合"""
        self.game.stage = "dealer_turn"
        self.stage_label.config(text="庄家回合")
        
        # 翻开庄家的暗牌
        if self.dealer_hidden_card_label:
            dealer_card2 = self.game.dealer_hand[1]
            self.flip_card_animation(self.dealer_hidden_card_label, dealer_card2, callback=self.after_reveal_dealer_card)
        else:
            self.after_reveal_dealer_card()
    
    def after_reveal_dealer_card(self):        
        # 庄家要牌直到达到17点或更高
        self.dealer_hit_loop()
    
    def dealer_hit_loop(self):
        """庄家要牌循环"""
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        self.update_hand_labels()
        
        if dealer_value < 17:
            # 庄家要牌
            self.status_label.config(text="庄家要牌")
            new_value = self.game.dealer_hit()
            new_card = self.game.dealer_hand[-1]
            
            # 添加新牌到庄家手牌
            position = len(self.game.dealer_hand) - 1
            new_card_label = self.add_card_to_frame(self.dealer_cards_frame, new_card, show_front=False, position=position)
            
            # 翻牌动画
            self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_dealer_hit(new_value))
        else:
            # 庄家停牌
            self.status_label.config(text="庄家停牌")
            self.after(1000, self.show_showdown)
    
    def after_dealer_hit(self, new_value):
        """庄家要牌后"""
        self.update_hand_labels()
        
        # 等待1秒后继续要牌
        self.after(100, self.dealer_hit_loop)
    
    def show_showdown(self):
        """结算阶段"""
        self.game.stage = "showdown"
        self.stage_label.config(text="结算")

        # 确保庄家的第二张手牌被打开
        self.ensure_dealer_second_card_revealed()

    def ensure_dealer_second_card_revealed(self):
        """确保庄家的第二张手牌被打开，但只在特定情况下才执行翻牌动画"""
        if len(self.game.dealer_hand) < 2:
            return
            
        # 检查庄家第二张牌是否已经显示正面
        dealer_second_card = self.game.dealer_hand[1]
        
        # 查找庄家第二张牌的标签
        dealer_card_labels = [w for w in self.dealer_cards_frame.winfo_children() if isinstance(w, tk.Label)]
        if dealer_card_labels and len(dealer_card_labels) > 1:
            second_card_label = dealer_card_labels[1]
            
            # 如果第二张牌是背面朝上且需要翻牌，则使用翻牌动画翻转为正面
            if hasattr(second_card_label, 'is_face_up') and not second_card_label.is_face_up and (self.game.get_hand_value(self.game.player_hand) > 21 and self.game.bust_bet == 0):
                self.flip_card_animation(second_card_label, dealer_second_card, callback=self._do_showdown)
            else:
                # 如果不需要翻牌或者已经正面朝上，直接进行结算
                self._do_showdown()
        else:
            self._do_showdown()

    def _do_showdown(self):
        # 计算赢得的金额（calculate_winnings 会返回总应支付给玩家的金额，包含本金）
        winnings, details = self.calculate_winnings()

        # 把应得金额加回余额（因为开始时已经扣除了本金）
        self.balance += winnings
        self.update_balance()

        # 更新下注显示与颜色（严格按需求：输->显示0，和局->浅蓝且数字不变，赢->金色且数字改为总返回金额）
        for bet_type, widget in self.bet_widgets.items():
            win_amount = details.get(bet_type, 0)  # 这是结算后应返回的总金额（本金+赢额，或本金，或 0）
            original_bet = getattr(self.game, f"{bet_type}_bet", 0)

            # 显示文本：如果输为0；如果和局为原下注；如果赢为总返回金额
            if win_amount == 0:
                display_text = "0"
                widget.config(bg='white')
            elif win_amount == original_bet:
                # 和局：退还本金（数字保持为下注金额），浅蓝背景
                display_text = str(int(original_bet))
                widget.config(bg='light blue')
            else:
                # 赢：显示总返回（本金 + 赢额），金色背景
                display_text = str(int(win_amount))
                widget.config(bg='gold')

            # 更新对应的 StringVar（以确保 UI 文本同步）
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

        # 构建结算消息（显示谁胜谁负）
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

        # 更新上局赢得金额显示（winnings 是本轮应加回的总额）
        # 注意：winnings 是返回给玩家的总金额（包含本金）。如果你想只显示净利改为 winnings - total_bet
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")

        # 显示"再来一局"按钮
        self.show_restart_button()

        # 设置 30 秒后自动重置（如果需要）
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def ensure_dealer_first_card_revealed(self):
        """确保庄家的第一张手牌被打开"""
        if not self.game.dealer_hand:
            return
            
        # 检查庄家第一张牌是否已经显示正面
        dealer_first_card = self.game.dealer_hand[1]
        
        # 查找庄家第一张牌的标签
        dealer_card_labels = [w for w in self.dealer_cards_frame.winfo_children() if isinstance(w, tk.Label)]
        if dealer_card_labels and len(dealer_card_labels) > 0:
            first_card_label = dealer_card_labels[1]
            # 如果第一张牌是背面朝上，则翻转为正面
            if hasattr(first_card_label, 'is_face_up') and not first_card_label.is_face_up:
                first_card_label.config(image=self.card_images.get((dealer_first_card.suit, dealer_first_card.rank), self.back_image))
                first_card_label.is_face_up = True
            
    def show_restart_button(self):
        """显示再来一局按钮"""
        # 清除操作按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=lambda: self.reset_game(False),  # 修改这里
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=5)
        
    def calculate_winnings(self):
        """计算赢得的金额"""
        winnings = 0
        details = {
            "main": 0,
            "perfect_pair": 0,
            "twenty_one_plus_three": 0,
            "royal_match": 0,
            "bust": 0
        }
        
        player_value = self.game.get_hand_value(self.game.player_hand)
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        
        # 1. 结算主注
        main_result = 0
        
        # 检查是否投降
        if self.game.main_bet == 0:  # 标记为投降
            # 投降已经退还一半，不需要额外处理
            main_result = 0
            details["main"] = 0  # 投降显示0
        # 检查双方都是21点的情况
        elif player_value == 21 and dealer_value == 21:
            player_card_count = len(self.game.player_hand)
            dealer_card_count = len(self.game.dealer_hand)
            
            # 玩家2张牌21点 vs 庄家2张牌21点 -> 平局
            if player_card_count == 2 and dealer_card_count == 2:
                main_result = self.game.main_bet  # 和局，退还下注
                details["main"] = self.game.main_bet  # 平局显示原下注金额
            # 玩家2张牌21点 vs 庄家3张或以上牌21点 -> 玩家胜利
            elif player_card_count == 2 and dealer_card_count >= 3:
                main_result = self.game.main_bet * 2.5  # Blackjack支付1.5倍
                details["main"] = main_result  # 赢显示获胜金额
            # 玩家3张或以上牌21点 vs 庄家2张牌21点 -> 庄家胜利
            elif player_card_count >= 3 and dealer_card_count == 2:
                main_result = 0  # 庄家Blackjack胜利
                details["main"] = 0  # 输显示0
            # 其他情况（双方都是3张或以上牌21点）-> 平局
            else:
                main_result = self.game.main_bet  # 和局，退还下注
                details["main"] = self.game.main_bet  # 平局显示原下注金额        
        # 检查玩家Blackjack
        elif self.game.player_blackjack and not self.game.dealer_blackjack:
            main_result = self.game.main_bet * 2.5  # Blackjack支付1.5倍
            details["main"] = main_result  # 赢显示获胜金额
        # 检查庄家Blackjack
        elif self.game.dealer_blackjack and not self.game.player_blackjack:
            if self.game.insurance_taken:
                main_result = self.game.main_bet  # 保险已支付，主注退还
                details["main"] = self.game.main_bet  # 平局显示原下注金额
            else:
                main_result = 0  # 庄家Blackjack，玩家输
                details["main"] = 0  # 输显示0
        elif player_value > 21:  # 玩家爆牌
            main_result = 0
            details["main"] = 0  # 输显示0
        elif dealer_value > 21:  # 庄家爆牌
            main_result = self.game.main_bet * 2
            details["main"] = main_result  # 赢显示获胜金额
        elif player_value > dealer_value:  # 玩家赢
            main_result = self.game.main_bet * 2
            details["main"] = main_result  # 赢显示获胜金额
        elif player_value < dealer_value:  # 玩家输
            main_result = 0
            details["main"] = 0  # 输显示0
        else:  # 和局
            main_result = self.game.main_bet
            details["main"] = self.game.main_bet  # 平局显示原下注金额
        
        winnings += main_result
        
        # 2. 结算完美对子
        if self.game.perfect_pair_bet > 0:
            pair_result = self.game.check_perfect_pair()
            if pair_result == "perfect":
                win_amount = self.game.perfect_pair_bet * 25
                details["perfect_pair"] = win_amount + self.game.perfect_pair_bet  # 包含本金
            elif pair_result == "colored":
                win_amount = self.game.perfect_pair_bet * 12
                details["perfect_pair"] = win_amount + self.game.perfect_pair_bet  # 包含本金
            elif pair_result == "mixed":
                win_amount = self.game.perfect_pair_bet * 6
                details["perfect_pair"] = win_amount + self.game.perfect_pair_bet  # 包含本金
            else:
                win_amount = 0
                details["perfect_pair"] = 0  # 输显示0
            winnings += details["perfect_pair"]
        
        # 3. 结算21+3
        if self.game.twenty_one_plus_three_bet > 0:
            twenty_one_result = self.game.check_twenty_one_plus_three()
            if twenty_one_result == "straight_three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 100
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet  # 包含本金
            elif twenty_one_result == "straight_flush":
                win_amount = self.game.twenty_one_plus_three_bet * 40
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet  # 包含本金
            elif twenty_one_result == "three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 30
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet  # 包含本金
            elif twenty_one_result == "straight":
                win_amount = self.game.twenty_one_plus_three_bet * 10
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet  # 包含本金
            elif twenty_one_result == "flush":
                win_amount = self.game.twenty_one_plus_three_bet * 5
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet  # 包含本金
            else:
                win_amount = 0
                details["twenty_one_plus_three"] = 0  # 输显示0
            winnings += details["twenty_one_plus_three"]
        
        # 4. 结算皇家同花
        if self.game.royal_match_bet > 0:
            royal_result = self.game.check_royal_match()
            if royal_result == "royal":
                win_amount = self.game.royal_match_bet * 25
                details["royal_match"] = win_amount + self.game.royal_match_bet  # 包含本金
            elif royal_result == "suited":
                win_amount = self.game.royal_match_bet * 2.5
                details["royal_match"] = win_amount + self.game.royal_match_bet  # 包含本金
            else:
                win_amount = 0
                details["royal_match"] = 0  # 输显示0
            winnings += details["royal_match"]
        
        # 5. 结算爆！
        if self.game.bust_bet > 0:
            if dealer_value > 21:
                dealer_card_count = len(self.game.dealer_hand)
                multiplier = {
                    3: 1,
                    4: 2,
                    5: 10,
                    6: 50,
                    7: 100
                }.get(dealer_card_count, 250)  # 8张或更多为250:1
                
                win_amount = self.game.bust_bet * multiplier
                details["bust"] = win_amount + self.game.bust_bet  # 包含本金
            else:
                win_amount = 0
                details["bust"] = 0  # 输显示0
            winnings += details["bust"]
        
        return winnings, details
    
    def reset_bets(self):
        """重置下注金额为0"""
        self.main_bet_var.set("0")
        self.perfect_pair_var.set("0")
        self.twenty_one_plus_three_var.set("0")
        self.royal_match_var.set("0")
        self.bust_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        for widget in self.bet_widgets.values():
            widget.config(bg='#FFCDD2')
        self.after(500, lambda: [w.config(bg='white') for w in self.bet_widgets.values()])

    def animate_cards_out(self):
        """将当前所有扑克牌向右移出屏幕的动画"""
        # 收集所有需要动画的卡片标签
        all_card_labels = []
        
        # 收集庄家区域的卡片
        for widget in self.dealer_cards_frame.winfo_children():
            if isinstance(widget, tk.Label) and hasattr(widget, 'card'):
                all_card_labels.append(widget)
        
        # 收集玩家区域的卡片
        for widget in self.player_cards_frame.winfo_children():
            if isinstance(widget, tk.Label) and hasattr(widget, 'card'):
                all_card_labels.append(widget)
        
        if not all_card_labels:
            # 如果没有卡片，直接返回
            return
        
        # 设置动画参数
        total_steps = 20  # 动画总步数
        step_delay = 20   # 每步延迟(毫秒)
        total_distance = 800  # 总移动距离
        
        def move_step(step):
            if step > total_steps:
                # 动画完成，销毁所有卡片
                for card_label in all_card_labels:
                    try:
                        card_label.destroy()
                    except:
                        pass
                return
            
            # 计算当前步的偏移量（使用缓动函数使动画更自然）
            progress = step / total_steps
            # 使用缓出函数
            eased_progress = 1 - (1 - progress) ** 3
            current_offset = int(total_distance * eased_progress)
            
            # 移动所有卡片
            for card_label in all_card_labels:
                try:
                    # 获取当前位置信息
                    place_info = card_label.place_info()
                    if place_info:
                        original_x = int(place_info.get('x', 0))
                        # 设置新位置
                        card_label.place(x=original_x + current_offset)
                except:
                    pass
            
            # 继续下一步
            self.after(step_delay, lambda: move_step(step + 1))
        
        # 开始动画
        move_step(1)
    
    def reset_game(self, auto_reset=False):
        """重置游戏"""
        # 取消自动重置计时器
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except:
                pass
            self.auto_reset_timer = None
        
        # 设置重置标志
        self._resetting = True
        
        # 清除所有挂起的after事件
        for after_id in self.tk.eval('after info').split():
            self.after_cancel(after_id)

        # 先执行卡片移出动画，动画完成后再重置其他状态
        def after_animation():
            # 重置游戏状态
            self.game.reset_game()
            self.stage_label.config(text="下注阶段")
            self.status_label.config(text="设置下注金额并开始游戏")
            
            # 重置标签显示
            self.player_label.config(text="玩家")
            self.dealer_label.config(text="庄家")
            
            # 重置下注金额为0
            self.main_bet_var.set("0")
            self.perfect_pair_var.set("0")
            self.twenty_one_plus_three_var.set("0")
            self.royal_match_var.set("0")
            self.bust_var.set("0")
            
            # 重置背景色为白色
            for widget in self.bet_widgets.values():
                widget.config(bg='white')
            
            # 清空活动卡片列表
            self.active_card_labels = []
            self.dealer_hidden_card_label = None
            
            # 清除所有动画状态
            self.flipping_cards = []
            self.flip_step = 0
            
            # 恢复下注区域
            for bet_type, widget in self.bet_widgets.items():
                widget.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            for chip in self.chip_buttons:
                text = self.chip_texts[chip]
                chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            
            # 恢复操作按钮区域
            for widget in self.action_frame.winfo_children():
                widget.destroy()
            
            start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
            start_button_frame.pack(pady=5)

            # 添加"重置金额"按钮
            self.reset_bets_button = tk.Button(
                start_button_frame, text="重置金额", 
                command=self.reset_bets, font=('Arial', 14),
                bg='#F44336', fg='white', width=10
            )
            self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
            self.reset_bets_button.config(state=tk.NORMAL)

            # 开始游戏按钮
            self.start_button = tk.Button(
                start_button_frame, text="开始游戏", 
                command=self.start_game, font=('Arial', 14),
                bg='#4CAF50', fg='white', width=10
            )
            self.start_button.pack(side=tk.LEFT)
            self.start_button.config(state=tk.NORMAL)
            
            # 重置本局下注显示
            self.current_bet_label.config(text="本局下注: $0.00")
            
            # 重置标志
            self._resetting = False
            
            # 如果是自动重置，显示消息
            if auto_reset:
                self.status_label.config(text="30秒已到，自动开始新游戏")
                self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
            else:
                self.status_label.config(text="设置下注金额并开始游戏")
        
        # 启动卡片移出动画
        self.animate_cards_out()
        
        # 在动画完成后执行重置逻辑
        self.after(500, after_animation)  # 500ms后执行重置，给动画留出时间

def main(initial_balance=10000, username="Guest"):
    app = BlackjackGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")