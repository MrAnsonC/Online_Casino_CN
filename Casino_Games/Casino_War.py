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
    def __init__(self, num_decks=6):
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

class CasinoWarGame:
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        self.ante_bet = 0
        self.tie_bet = 0
        self.war_bet = 0
        self.player_card = None
        self.dealer_card = None
        self.player_war_card = None
        self.dealer_war_card = None
        self.burn_cards_player = []
        self.burn_cards_dealer = []
        self.stage = "betting"
        self.surrendered = False
    
    def compare_cards(self, card1, card2):
        v1 = self.card_value(card1)
        v2 = self.card_value(card2)
        if v1 > v2:
            return "player"
        elif v1 < v2:
            return "dealer"
        else:
            return "tie"
    
    def card_value(self, card):
        if card.rank == 'A':
            return 14
        elif card.rank == 'K':
            return 13
        elif card.rank == 'Q':
            return 12
        elif card.rank == 'J':
            return 11
        else:
            return int(card.rank)

class CasinoWarGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("赌场战争")
        self.geometry("1150x650+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = CasinoWarGame()
        self.card_images = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.last_win = 0
        self.auto_reset_timer = None
        
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
    
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=20, width=600, height=250)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=365, width=600, height=250)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 提示文字
        self.info_label = tk.Label(
            table_canvas,
            text="A最大，2最小\n平局赔付10:1并进入战争或选择投降",
            font=('Arial', 22),
            bg='#35654d',
            fg='#FFD700'
        )
        self.info_label.place(x=350, y=315, anchor='center')
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=260, padx=10, pady=5)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        self.balance_label = tk.Label(info_frame, text=f"余额: ${self.balance:.2f}", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=5)
        self.stage_label = tk.Label(info_frame, text="下注阶段", font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='#FFD700')
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=5)
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        chip_configs = [('$10', '#ffa500', 'black'), ("$25", '#00ff00', 'black'), ("$100", '#000000', 'white'),
                        ("$500", "#FF7DDA", 'black'), ("$1K", '#ffffff', 'black'), ("$2.5K", '#ff0000', 'white')]
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
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        tk.Label(header_frame, text="主注最低", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="主注最高", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="平局最高", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$25,000", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X)
        
        # 下注区域 (第一行: Tie + War, 第二行: 主注)
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        
        # 第一行: Tie 和 War（War 整行初始隐藏）
        first_row = tk.Frame(bet_frame, bg='#2a4a3c')
        first_row.pack(fill=tk.X, padx=10, pady=3)
        # Tie
        tk.Label(first_row, text="平局:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=1)
        self.tie_var = tk.StringVar(value="0")
        self.tie_display = tk.Label(first_row, textvariable=self.tie_var, font=('Arial', 14), bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.tie_display.pack(side=tk.LEFT, padx=5)
        self.tie_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("tie"))
        self.tie_display.bind("<Button-3>", lambda e: self.clear_bet("tie"))
        
        # War 整行（文字 + 格子）放入一个 Frame，初始隐藏
        self.war_frame = tk.Frame(first_row, bg='#2a4a3c')
        tk.Label(self.war_frame, text="战争:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=(20,1))
        self.war_var = tk.StringVar(value="0")
        self.war_display = tk.Label(self.war_frame, textvariable=self.war_var, font=('Arial', 14), bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.war_display.pack(side=tk.LEFT, padx=5)
        self.war_display.bind("<Button-1>", lambda e: None)   # 不可手动下注
        self.war_frame.pack(side=tk.LEFT)
        self.war_frame.pack_forget()   # 初始隐藏
        
        # 第二行: 主注 (Ante)
        second_row = tk.Frame(bet_frame, bg='#2a4a3c')
        second_row.pack(fill=tk.X, padx=10, pady=3)
        tk.Label(second_row, text="主注:", font=('Arial', 18), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=1)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(second_row, textvariable=self.ante_var, font=('Arial', 18), bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.clear_bet("ante"))
        
        # 操作按钮区域
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X)
        self._show_start_buttons()
        
        # 状态信息
        self.status_label = tk.Label(control_frame, text="设置下注金额并开始游戏", font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.status_label.pack(pady=5, fill=tk.X)
        
        # 本局下注和上局获胜
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.current_bet_label = tk.Label(bet_info_frame, text="本局下注: $0.00", font=('Arial', 12), bg='#2a4a3c', fg='white')
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        self.last_win_label = tk.Label(bet_info_frame, text="上局获胜: $0.00", font=('Arial', 12), bg='#2a4a3c', fg='#FFD700')
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)
        
        # 规则按钮
        rules_btn = tk.Button(bet_info_frame, text="ℹ️", command=self.show_game_instructions, font=('Arial', 8), bg='#4B8BBE', fg='white')
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)
        rules_btn.bind("<Button-3>", self.show_remaining_cards)
    
    def _show_start_buttons(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        btn_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        btn_frame.pack(pady=5)
        self.reset_bets_button = tk.Button(btn_frame, text="重置金额", command=self.reset_bets, font=('Arial', 14), bg='#F44336', fg='white', width=10)
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0,10))
        self.start_button = tk.Button(btn_frame, text="开始游戏", command=self.start_game, font=('Arial', 14), bg='#4CAF50', fg='white', width=10)
        self.start_button.pack(side=tk.LEFT)
    
    def _show_tie_decision_buttons(self):
        """显示战争/投降按钮，同行显示"""
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        btn_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        btn_frame.pack(pady=5)
        self.surrender_btn = tk.Button(btn_frame, text="投降", command=self.surrender_action, font=('Arial', 14), bg='#FF9800', fg='white', width=10)
        self.surrender_btn.pack(side=tk.LEFT, padx=5)
        self.war_btn = tk.Button(btn_frame, text="战争", command=self.war_action, font=('Arial', 14), bg='#2196F3', fg='white', width=10)
        self.war_btn.pack(side=tk.LEFT, padx=5)
    
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip or self.game.stage != "betting":
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        if bet_type == "ante":
            current = int(self.ante_var.get())
            new_value = current + chip_value
            if new_value > 25000:
                new_value = 25000
                messagebox.showwarning("下注限制", f"主注上限为25000，已自动调整")
            self.ante_var.set(str(int(new_value)))
        elif bet_type == "tie":
            current = int(self.tie_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"Tie上限为2500，已自动调整")
            self.tie_var.set(str(int(new_value)))
    
    def clear_bet(self, bet_type):
        if self.game.stage != "betting":
            return
        if bet_type == "ante":
            self.ante_var.set("0")
        elif bet_type == "tie":
            self.tie_var.set("0")
        widget = self.ante_display if bet_type == "ante" else self.tie_display
        widget.config(bg='#FFCDD2')
        self.after(300, lambda: widget.config(bg='white'))
    
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
        card_img = self.card_images.get((card.suit, card.rank), self.back_image) if show_front else self.back_image
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
        return card_label
    
    def move_card_animation(self, from_x, from_y, target_frame, target_position, card, show_front=True, callback=None):
        temp = tk.Toplevel(self)
        temp.overrideredirect(True)
        temp.attributes('-topmost', True)
        img = self.card_images.get((card.suit, card.rank), self.back_image) if show_front else self.back_image
        label = tk.Label(temp, image=img, bg='#2a4a3c')
        label.pack()
        temp.geometry(f"+{from_x}+{from_y}")
        
        target_x = target_frame.winfo_rootx() + target_position * 110
        target_y = target_frame.winfo_rooty() + 10
        steps = 20
        dx = (target_x - from_x) / steps
        dy = (target_y - from_y) / steps
        
        def step(step_count=0):
            if step_count > steps:
                temp.destroy()
                final_label = self.add_card_to_frame(target_frame, card, show_front=show_front, position=target_position)
                if callback:
                    callback(final_label)
                return
            new_x = from_x + dx * step_count
            new_y = from_y + dy * step_count
            temp.geometry(f"+{int(new_x)}+{int(new_y)}")
            self.after(20, lambda: step(step_count + 1))
        step()
        return temp
    
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
                items.append({'id': item, 'base_x': x, 'base_y': y, 'phase': (i * 2 * math.pi) / max(1, num_cards), 'amp': 10 + (i % 4) * 4, 'z': i})
            canvas.create_text(520//2, 18, text="正在洗牌，请稍候...", fill='white', font=('Arial', 14, 'bold'))
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
                            callback()
                    win.after(100, do_close)
            anim_step()
        except Exception as e:
            print(f"洗牌动画失败: {e}")
            if callback:
                callback()
    
    def start_game(self):
        try:
            self.game.ante_bet = int(self.ante_var.get())
            self.game.tie_bet = int(self.tie_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return
        if self.game.ante_bet < 10:
            messagebox.showerror("错误", "主注至少需要10块")
            return
        total_bet = self.game.ante_bet + self.game.tie_bet
        if self.balance < total_bet:
            messagebox.showerror("错误", "余额不足以支付下注！")
            return
        
        # 禁用下注区域
        self.ante_display.unbind("<Button-1>")
        self.ante_display.unbind("<Button-3>")
        self.tie_display.unbind("<Button-1>")
        self.tie_display.unbind("<Button-3>")
        self.start_button.config(state=tk.DISABLED)
        self.reset_bets_button.config(state=tk.DISABLED)
        
        self.balance -= total_bet
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        need_shuffle = (not hasattr(self.game, 'deck') or self.game.deck is None or len(self.game.deck.cards) <= 60)
        def continue_after_shuffle():
            self.game.deck = Deck(6)
            self.game.reset_game()
            self.game.ante_bet = int(self.ante_var.get())
            self.game.tie_bet = int(self.tie_var.get())
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()
            self.game.player_card = self.game.deck.deal_card()
            self.game.dealer_card = self.game.deck.deal_card()
            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            self._deal_initial_cards()
        
        def continue_without_shuffle():
            self.game.reset_game()
            self.game.ante_bet = int(self.ante_var.get())
            self.game.tie_bet = int(self.tie_var.get())
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()
            self.game.player_card = self.game.deck.deal_card()
            self.game.dealer_card = self.game.deck.deal_card()
            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            self._deal_initial_cards()
        
        if need_shuffle:
            self.play_shuffle_animation(duration_ms=10000, callback=continue_after_shuffle)
        else:
            continue_without_shuffle()
    
    def _deal_initial_cards(self):
        player_card_label = self.add_card_to_frame(self.player_cards_frame, self.game.player_card, show_front=False, position=0)
        self.flip_card_animation(player_card_label, self.game.player_card, callback=lambda: self._after_player_card())
    
    def _after_player_card(self):
        self.player_label.config(text=f"玩家 - {self.game.player_card.rank}{self.game.player_card.suit}")
        dealer_card_label = self.add_card_to_frame(self.dealer_cards_frame, self.game.dealer_card, show_front=False, position=0)
        self.flip_card_animation(dealer_card_label, self.game.dealer_card, callback=self._after_dealer_card)
    
    def _after_dealer_card(self):
        self.dealer_label.config(text=f"庄家 - {self.game.dealer_card.rank}{self.game.dealer_card.suit}")
        self._initial_compare()
    
    def _initial_compare(self):
        result = self.game.compare_cards(self.game.player_card, self.game.dealer_card)
        if result == "player":
            win_amount = self.game.ante_bet * 2
            self.balance += win_amount
            self.update_balance()
            self.last_win = win_amount
            self.last_win_label.config(text=f"上局获胜: ${win_amount:.2f}")
            self.status_label.config(text="玩家手牌更大！你赢了。")
            self.ante_var.set(str(int(win_amount)))
            self.ante_display.config(bg='gold')
            self.tie_var.set("0")
            self.tie_display.config(bg='white')
            self._show_restart_button()
        elif result == "dealer":
            self.last_win = 0
            self.last_win_label.config(text="上局获胜: $0.00")
            self.status_label.config(text="庄家手牌更大！下局加油。")
            self.ante_var.set("0")
            self.ante_display.config(bg='white')
            self.tie_var.set("0")
            self.tie_display.config(bg='white')
            self._show_restart_button()
        else:  # 平局
            tie_win = self.game.tie_bet * 11
            if tie_win > 0:
                self.balance += tie_win
                self.update_balance()
                self.last_win = tie_win
                self.last_win_label.config(text=f"上局获胜: ${tie_win:.2f}")
                self.status_label.config(text=f"平局！你赢得 ${tie_win}")
                self.tie_var.set(str(int(tie_win)))
                self.tie_display.config(bg='gold')
            else:
                self.status_label.config(text="平局！")
                self.tie_var.set("0")
                self.tie_display.config(bg='white')
            self.game.stage = "tie_decision"
            self.stage_label.config(text="战争决策")
            self._show_tie_decision_buttons()
    
    def surrender_action(self):
        # 投降：拿回一半主注，且 Tie 已经赔付过，累加
        refund = self.game.ante_bet / 2
        self.balance += refund
        self.update_balance()
        # 累加获胜金额（已有的 last_win 是 Tie 赢额，加上投降返还）
        total_win = self.last_win + refund
        self.last_win = total_win
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")
        self.status_label.config(text=f"投降，拿回一半主注 ${refund:.2f}")

        # 根据 refund 是否为整数决定显示格式
        if refund.is_integer():
            self.ante_var.set(str(int(refund)))
        else:
            self.ante_var.set(f"{refund:.2f}")

        self.ante_display.config(bg='light pink')
        self.game.surrendered = True
        self._show_restart_button()
    
    def war_action(self):
        if self.balance < self.game.ante_bet:
            messagebox.showerror("错误", "余额不足以支付战争赌注！")
            return

        # 立即禁用投降和战争按钮，防止重复点击
        if hasattr(self, 'surrender_btn'):
            self.surrender_btn.config(state=tk.DISABLED)
        if hasattr(self, 'war_btn'):
            self.war_btn.config(state=tk.DISABLED)

        self.balance -= self.game.ante_bet
        self.game.war_bet = self.game.ante_bet
        self.update_balance()
        total_bet = self.game.ante_bet + self.game.tie_bet + self.game.war_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        self.status_label.config(text="进入战争！烧3张牌后比牌")
        self.game.stage = "war_burn"

        # 显示战争格子（整行）
        self.war_frame.pack(side=tk.LEFT)
        self.war_var.set(str(int(self.game.war_bet)))
        self.war_display.config(bg='white')

        start_x = self.winfo_rootx() + self.winfo_width() // 2 - 50
        start_y = self.winfo_rooty() + 20
        self._burn_player_cards(0, start_x, start_y)
        
    def _burn_player_cards(self, index, start_x, start_y):
        if index >= 3:
            self.game.player_war_card = self.game.deck.deal_card()
            self.move_card_animation(start_x, start_y, self.player_cards_frame, 4, self.game.player_war_card, show_front=False,
                                     callback=lambda lbl: self._reveal_player_war_card(lbl))
            return
        card = self.game.deck.deal_card()
        self.game.burn_cards_player.append(card)
        self.move_card_animation(start_x, start_y, self.player_cards_frame, 1+index, card, show_front=False,
                                 callback=lambda lbl: self._burn_player_cards(index+1, start_x, start_y))
    
    def _reveal_player_war_card(self, lbl):
        self.flip_card_animation(lbl, self.game.player_war_card, callback=self._burn_dealer_cards)
    
    def _burn_dealer_cards(self):
        start_x = self.winfo_rootx() + self.winfo_width() // 2 - 50
        start_y = self.winfo_rooty() + 20
        self._burn_dealer_cards_step(0, start_x, start_y)
    
    def _burn_dealer_cards_step(self, index, start_x, start_y):
        if index >= 3:
            self.game.dealer_war_card = self.game.deck.deal_card()
            self.move_card_animation(start_x, start_y, self.dealer_cards_frame, 4, self.game.dealer_war_card, show_front=False,
                                     callback=lambda lbl: self._reveal_dealer_war_card(lbl))
            return
        card = self.game.deck.deal_card()
        self.game.burn_cards_dealer.append(card)
        self.move_card_animation(start_x, start_y, self.dealer_cards_frame, 1+index, card, show_front=False,
                                 callback=lambda lbl: self._burn_dealer_cards_step(index+1, start_x, start_y))
    
    def _reveal_dealer_war_card(self, lbl):
        self.flip_card_animation(lbl, self.game.dealer_war_card, callback=self._war_compare)
    
    def _war_compare(self):
        result = self.game.compare_cards(self.game.player_war_card, self.game.dealer_war_card)
        if result == "player":
            ante_win = self.game.ante_bet * 2
            war_return = self.game.war_bet
            total_win = ante_win + war_return
            self.balance += total_win
            self.update_balance()
            self.last_win = total_win
            self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")
            self.status_label.config(text="战争胜利！主注获胜，战争平局退还。")
            self.ante_var.set(str(int(ante_win)))
            self.ante_display.config(bg='gold')
            self.war_var.set(str(int(war_return)))
            self.war_display.config(bg='light blue')
        elif result == "dealer":
            self.last_win = 0
            self.last_win_label.config(text="上局获胜: $0.00")
            self.status_label.config(text="战争失败！主注和战争都输。")
            self.ante_var.set("0")
            self.ante_display.config(bg='white')
            self.war_var.set("0")
            self.war_display.config(bg='white')
        else:  # 平局
            ante_win = self.game.ante_bet * 2
            war_return = self.game.war_bet
            total_win = ante_win + war_return
            self.balance += total_win
            self.update_balance()
            self.last_win = total_win
            self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")
            self.status_label.config(text="战争平局！主注获胜，战争平局退还。")
            self.ante_var.set(str(int(ante_win)))
            self.ante_display.config(bg='gold')
            self.war_var.set(str(int(war_return)))
            self.war_display.config(bg='light blue')
        self._show_restart_button()
    
    def _show_restart_button(self):
        self.game.stage = "showdown"
        self.stage_label.config(text="结算")
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        restart_btn = tk.Button(self.action_frame, text="再来一局", command=lambda: self.reset_game(False), font=('Arial', 14), bg='#2196F3', fg='white', width=15)
        restart_btn.pack(pady=5)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def reset_bets(self):
        self.ante_var.set("0")
        self.tie_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for w in [self.ante_display, self.tie_display]:
            w.config(bg='white')
        for w in [self.ante_display, self.tie_display]:
            w.config(bg='#FFCDD2')
        self.after(500, lambda: [w.config(bg='white') for w in [self.ante_display, self.tie_display]])
    
    def animate_cards_out(self):
        all_card_labels = []
        for widget in self.dealer_cards_frame.winfo_children():
            if isinstance(widget, tk.Label):
                all_card_labels.append(widget)
        for widget in self.player_cards_frame.winfo_children():
            if isinstance(widget, tk.Label):
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
            self.ante_var.set("0")
            self.tie_var.set("0")
            self.war_var.set("0")
            # 隐藏战争格子
            self.war_frame.pack_forget()
            self.ante_display.config(bg='white')
            self.tie_display.config(bg='white')
            for widget in self.action_frame.winfo_children():
                widget.destroy()
            self._show_start_buttons()
            # 重新绑定下注事件
            self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
            self.ante_display.bind("<Button-3>", lambda e: self.clear_bet("ante"))
            self.tie_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("tie"))
            self.tie_display.bind("<Button-3>", lambda e: self.clear_bet("tie"))
            self.current_bet_label.config(text="本局下注: $0.00")
            self._resetting = False
            if auto_reset:
                self.status_label.config(text="30秒已到，自动开始新游戏")
                self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
            else:
                self.status_label.config(text="设置下注金额并开始游戏")
        self.animate_cards_out()
        self.after(500, after_animation)
    
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("赌场战争规则")
        win.geometry("700x500")
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
赌场战争规则

1. 游戏使用6副扑克牌，A最大。

2. 玩家可下注 主注(Ante) 和 Tie（Tie为可选）。

3. 游戏开始：玩家和庄家各发一张牌，比较大小。
   - 玩家牌大 → 主注赢 1:1，Tie 输，游戏结束。
   - 庄家牌大 → 主注和 Tie 全输，游戏结束。
   - 平局 → Tie 立即赔付 10:1（若下注），然后进入战争阶段。

4. 战争阶段（仅平局时触发）：
   - 玩家可选择「投降」：拿回一半主注，游戏结束。
   - 或选择「战争」：额外支付与主注相等的赌注（War），然后双方各烧3张牌（背面显示），再各发一张新牌比较。
     * 玩家新牌大于或等于庄家新牌 → 主注赢 1:1，War 赌注退回（平局），游戏结束。
     * 庄家新牌大 → 主注和 War 全输，游戏结束。
        """
        rules_label = tk.Label(content_frame, text=rules_text, font=('微软雅黑', 12), bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10)
        rules_label.pack(fill=tk.X, padx=10, pady=5)
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    
    def show_remaining_cards(self, event=None):
        if not hasattr(self.game, 'deck') or self.game.deck is None:
            messagebox.showinfo("提示", "牌堆未初始化")
            return
        remaining_cards = self.game.deck.get_remaining_cards_count()
        win = tk.Toplevel(self)
        win.title("剩余牌堆统计")
        win.geometry("600x400")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        title_label = tk.Label(main_frame, text=f"剩余{len(self.game.deck.cards)}张牌", font=('Arial', 16, 'bold'), bg='#F0F0F0', fg='#333333')
        title_label.pack(pady=(0, 10))
        table_frame = tk.Frame(main_frame, bg='#F0F0F0')
        table_frame.pack(fill=tk.BOTH, expand=True)
        header_frame = tk.Frame(table_frame, bg='#F0F0F0')
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="", width=6, bg='#F0F0F0').pack(side=tk.LEFT)
        for rank in RANKS:
            display_rank = 'X' if rank == '10' else rank
            label = tk.Label(header_frame, text=display_rank, width=4, font=('Arial', 10, 'bold'), bg='#F0F0F0', relief=tk.RAISED, bd=1)
            label.pack(side=tk.LEFT, padx=1)
        total_label = tk.Label(header_frame, text="总计", width=4, font=('Arial', 10, 'bold'), bg='#F0F0F0', relief=tk.RAISED, bd=1)
        total_label.pack(side=tk.LEFT, padx=1)
        for suit in SUITS:
            row_frame = tk.Frame(table_frame, bg='#F0F0F0')
            row_frame.pack(fill=tk.X)
            suit_label = tk.Label(row_frame, text=suit, width=4, font=('Arial', 12, 'bold'), bg='#F0F0F0', relief=tk.RAISED, bd=1)
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
                count_label = tk.Label(row_frame, text=str(count), width=4, font=('Arial', 10), bg=bg_color, relief=tk.SUNKEN, bd=1)
                count_label.pack(side=tk.LEFT, padx=1)
            total_label = tk.Label(row_frame, text=str(suit_total), width=4, font=('Arial', 10, 'bold'), bg='#DDDDDD', relief=tk.RAISED, bd=1)
            total_label.pack(side=tk.LEFT, padx=1)
        separator = tk.Frame(table_frame, height=2, bg='#333333')
        separator.pack(fill=tk.X, pady=5)
        total_row_frame = tk.Frame(table_frame, bg='#F0F0F0')
        total_row_frame.pack(fill=tk.X, padx=8)
        tk.Label(total_row_frame, text="总计", width=4, font=('Arial', 10, 'bold'), bg='#F0F0F0', relief=tk.RAISED, bd=1).pack(side=tk.LEFT, padx=1)
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
            total_label = tk.Label(total_row_frame, text=str(total), width=4, font=('Arial', 10, 'bold'), bg=bg_color, relief=tk.RAISED, bd=1)
            total_label.pack(side=tk.LEFT, padx=1)
        grand_total_label = tk.Label(total_row_frame, text=str(grand_total), width=4, font=('Arial', 10, 'bold'), bg='#CCCCFF', relief=tk.RAISED, bd=1)
        grand_total_label.pack(side=tk.LEFT, padx=1)
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

def main(initial_balance=10000, username="Guest"):
    app = CasinoWarGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: ${final_balance:.2f}")