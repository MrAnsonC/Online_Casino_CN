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

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import hashlib
import time
import secrets
import subprocess, sys
from itertools import combinations

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}  # A=14, K=13, ...
# 牛牛点数映射（A=1, 2-9=本身, 10/J/Q/K=10）
NIU_POINTS = { 'A':1, '2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, '10':10, 'J':10, 'Q':10, 'K':10 }

# 牛牛牌型名称
NIU_NAMES = {
    0: '没牛',
    1: '牛一', 2: '牛二', 3: '牛三', 4: '牛四',
    5: '牛五', 6: '牛六', 7: '牛七', 8: '牛八', 9: '牛九',
    10: '牛牛'
}

# 用于排序显示的大到小顺序（K>Q>J>...>3>2>A）
RANK_DISPLAY_ORDER = {
    'A': 1, '2': 2, '3': 3, '4': 4, '5': 5,
    '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 11, 'Q': 12, 'K': 13
}

# 花色顺序（用于排序和比较）
SUIT_ORDER = {'♠': 4, '♥': 3, '♣': 2, '♦': 1}

def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'A_Tools/Account/saving_data.json')

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
        self.value = RANK_VALUES[rank]          # 用于比较大小
        self.niu_point = NIU_POINTS[rank]       # 用于牛牛计算
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
                [sys.executable, shuffle_script],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30
            )
            shuffle_data = json.loads(result.stdout)
            if "deck" not in shuffle_data or "cut_position" not in shuffle_data:
                raise ValueError("Invalid shuffle data format")
            self.full_deck = [
                Card(d["suit"], d["rank"])
                for d in shuffle_data["deck"]
            ]
            self.cut_position = shuffle_data["cut_position"]
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
                ValueError,
                KeyError) as e:
            print(f"Error calling shuffle.py: {e}. Using fallback shuffle.")
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

# ==================== 牛牛牌型评估与排序 ====================
def evaluate_niu(hand):
    """
    评估5张牌，返回 (等级, 排序后的牌列表, 三张组合, 两张组合)
    等级: 0=没牛, 1-9=牛一~牛九, 10=牛牛
    排序规则：点数 K>Q>J>...>2>A，点数相同按花色 黑桃>红心>梅花>方块
    """
    if len(hand) != 5:
        return (0, [], [], [])
    points = [c.niu_point for c in hand]
    best_rank = 0
    best_three = []
    best_two = []
    for combo in combinations(range(5), 3):
        three_sum = sum(points[i] for i in combo)
        if three_sum % 10 == 0:
            remaining = [i for i in range(5) if i not in combo]
            two_sum = sum(points[i] for i in remaining)
            rank = two_sum % 10
            if rank == 0:
                rank = 10
            if rank > best_rank:
                best_rank = rank
                best_three = [hand[i] for i in combo]
                best_two = [hand[i] for i in remaining]
    
    # 排序辅助函数：按点数降序，点数相同按花色降序
    def sort_key(card):
        return (-RANK_DISPLAY_ORDER[card.rank], -SUIT_ORDER[card.suit])
    
    if best_rank == 0:
        # 没牛：全部降序排列
        sorted_hand = sorted(hand, key=sort_key)
        return (0, sorted_hand, [], [])
    else:
        three_sorted = sorted(best_three, key=sort_key)
        two_sorted = sorted(best_two, key=sort_key)
        sorted_hand = three_sorted + two_sorted
        return (best_rank, sorted_hand, three_sorted, two_sorted)

def compare_niu_hands(hand1, hand2):
    """
    比较两手牌，返回1表示hand1赢，0平局，-1表示hand2赢
    先比等级，再比最大牌的点数（使用RANK_VALUES，A最大），再比花色
    """
    rank1, _, _, _ = evaluate_niu(hand1)
    rank2, _, _, _ = evaluate_niu(hand2)
    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1
    else:
        max1 = max(hand1, key=lambda c: (c.value, SUIT_ORDER[c.suit]))
        max2 = max(hand2, key=lambda c: (c.value, SUIT_ORDER[c.suit]))
        if max1.value > max2.value:
            return 1
        elif max1.value < max2.value:
            return -1
        else:
            if SUIT_ORDER[max1.suit] > SUIT_ORDER[max2.suit]:
                return 1
            elif SUIT_ORDER[max1.suit] < SUIT_ORDER[max2.suit]:
                return -1
            else:
                return 0

# ==================== 牛牛游戏主类 ====================
class NiuNiuGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.black_hand = []   # 黑牛手牌
        self.red_hand = []     # 红牛手牌
        self.black_bet = 0
        self.red_bet = 0
        self.black_double = 0
        self.red_double = 0
        self.side_niu_bet = 0
        self.side_double_niu_bet = 0
        self.stage = "pre_flop"   # pre_flop, showdown
        self.cards_revealed = {
            "black": [False]*5,
            "red": [False]*5
        }
        self.card_sequence = self.deck.full_deck.copy()
        self.cut_position = self.deck.cut_position

    def deal_initial(self):
        self.black_hand = self.deck.deal(5)
        self.red_hand = self.deck.deal(5)

# ==================== GUI主类 ====================
class NiuNiuGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("牛牛")
        self.geometry("1150x650+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')

        self.username = username
        self.balance = initial_balance
        self.game = NiuNiuGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self._resetting = False

        # 下注变量
        self.black_bet_var = tk.StringVar(value="0")
        self.red_bet_var = tk.StringVar(value="0")
        self.black_double_var = tk.StringVar(value="0")
        self.red_double_var = tk.StringVar(value="0")
        self.side_niu_var = tk.StringVar(value="0")
        self.side_double_niu_var = tk.StringVar(value="0")

        # 上次下注记录
        self.last_bet = None

        # 加载图片
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def cancel_auto_reset_timer(self):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except:
                pass
            finally:
                self.auto_reset_timer = None

    def on_close(self):
        self.cancel_auto_reset_timer()
        self.destroy()
        self.quit()

    def _load_assets(self):
        card_size = (100, 150)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not hasattr(self, 'current_poker_folder'):
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
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
        except:
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
        """将选中的筹码添加到指定的下注项，包含互斥逻辑"""
        if not self.selected_chip:
            return

        # 获取当前黑牛方和红牛方是否有下注（主注或双倍）
        black_bet = int(self.black_bet_var.get())
        red_bet = int(self.red_bet_var.get())
        black_double = int(self.black_double_var.get())
        red_double = int(self.red_double_var.get())
        black_has = black_bet > 0 or black_double > 0
        red_has = red_bet > 0 or red_double > 0

        # 互斥检查
        if bet_type in ("red", "red_double"):
            if black_has:
                messagebox.showwarning("互斥", "黑牛方已有下注，不能下注红牛方")
                return
        if bet_type in ("black", "black_double"):
            if red_has:
                messagebox.showwarning("互斥", "红牛方已有下注，不能下注黑牛方")
                return

        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)

        # 更新对应变量
        if bet_type == "black":
            current = float(self.black_bet_var.get())
            new_value = current + chip_value
            if new_value > 10000:
                new_value = 10000
                messagebox.showwarning("下注限制", "黑牛下注上限为10000")
            self.black_bet_var.set(str(int(new_value)))
        elif bet_type == "red":
            current = float(self.red_bet_var.get())
            new_value = current + chip_value
            if new_value > 10000:
                new_value = 10000
                messagebox.showwarning("下注限制", "红牛下注上限为10000")
            self.red_bet_var.set(str(int(new_value)))
        elif bet_type == "black_double":
            current = float(self.black_double_var.get())
            new_value = current + chip_value
            if new_value > 10000:
                new_value = 10000
                messagebox.showwarning("下注限制", "黑牛双倍上限为10000")
            self.black_double_var.set(str(int(new_value)))
        elif bet_type == "red_double":
            current = float(self.red_double_var.get())
            new_value = current + chip_value
            if new_value > 10000:
                new_value = 10000
                messagebox.showwarning("下注限制", "红牛双倍上限为10000")
            self.red_double_var.set(str(int(new_value)))
        elif bet_type == "side_niu":
            current = float(self.side_niu_var.get())
            new_value = current + chip_value
            if new_value > 5000:
                new_value = 5000
                messagebox.showwarning("下注限制", "边注牛牛上限为5000")
            self.side_niu_var.set(str(int(new_value)))
        elif bet_type == "side_double_niu":
            current = float(self.side_double_niu_var.get())
            new_value = current + chip_value
            if new_value > 5000:
                new_value = 5000
                messagebox.showwarning("下注限制", "边注双牛牛上限为5000")
            self.side_double_niu_var.set(str(int(new_value)))

        # 更新UI禁用状态
        self._update_bet_widgets_state()

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

    def _create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧牌桌
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 红牛区域（上）
        red_frame = tk.Frame(table_canvas, bg='#ff6060', bd=2, relief=tk.RAISED)
        red_frame.place(x=30, y=20, width=630, height=250)
        self.red_label = tk.Label(red_frame, text="红牛", font=('Arial', 18), bg='#ff6060', fg='black')
        self.red_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.red_cards_frame = tk.Frame(red_frame, bg='#ff6060')
        self.red_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 黑牛区域（下）
        black_frame = tk.Frame(table_canvas, bg='#989898', bd=2, relief=tk.RAISED)
        black_frame.place(x=30, y=365, width=630, height=250)
        self.black_label = tk.Label(black_frame, text="黑牛", font=('Arial', 18), bg='#989898', fg='black')
        self.black_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.black_cards_frame = tk.Frame(black_frame, bg='#989898')
        self.black_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=300, padx=10, pady=5)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # 余额和状态
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        self.balance_label = tk.Label(info_frame, text=f"余额: ${self.balance:.2f}", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=5)
        self.stage_label = tk.Label(info_frame, text="等待下注", font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='#FFD700')
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=5)

        # ---------- 筹码区域 ----------
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        self.chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.chips_label.pack(anchor='w', padx=10, pady=5)
        self.chip_container = tk.Frame(chips_frame, bg='#2a4a3c')
        self.chip_container.pack(fill=tk.X, pady=5, padx=5)
        self._rebuild_chips()

        # ---------- 下注区域 ----------
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)

        # ---- 上部分：边注（牛牛和双牛牛在同一行） ----
        side_frame = tk.LabelFrame(bet_frame, text="边注", bg='#2a4a3c', fg='white', font=('Arial', 12, 'bold'))
        side_frame.pack(fill=tk.X, padx=5, pady=5)

        side_row = tk.Frame(side_frame, bg='#2a4a3c')
        side_row.pack(fill=tk.X, pady=3, padx=5)
        tk.Label(side_row, text="牛牛:", font=('Arial', 12), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.side_niu_display = tk.Label(side_row, textvariable=self.side_niu_var, font=('Arial', 12),
                                         bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.side_niu_display.pack(side=tk.LEFT, padx=5)
        self.side_niu_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("side_niu"))
        tk.Label(side_row, text="   ", bg='#2a4a3c').pack(side=tk.LEFT)
        tk.Label(side_row, text="双牛牛:", font=('Arial', 12), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.side_double_niu_display = tk.Label(side_row, textvariable=self.side_double_niu_var, font=('Arial', 12),
                                                bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.side_double_niu_display.pack(side=tk.LEFT, padx=5)
        self.side_double_niu_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("side_double_niu"))

        # ---- 下部分：主注（左右两列） ----
        main_frame2 = tk.LabelFrame(bet_frame, text="主注", bg='#2a4a3c', fg='white', font=('Arial', 12, 'bold'))
        main_frame2.pack(fill=tk.X, padx=5, pady=5)

        main_inner = tk.Frame(main_frame2, bg='#2a4a3c')
        main_inner.pack(fill=tk.X, padx=5, pady=5)

        # 左列：黑牛
        left_frame = tk.Frame(main_inner, bg='#2a4a3c')
        left_frame.grid(row=0, column=0, sticky='nsew', padx=5)
        tk.Label(left_frame, text="黑牛", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white').pack(anchor='w')
        self.black_bet_display = tk.Label(left_frame, textvariable=self.black_bet_var, font=('Arial', 12),
                                          bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.black_bet_display.pack(pady=2)
        self.black_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("black"))
        tk.Label(left_frame, text="双倍", font=('Arial', 10), bg='#2a4a3c', fg='white').pack(anchor='w')
        self.black_double_display = tk.Label(left_frame, textvariable=self.black_double_var, font=('Arial', 12),
                                             bg='white', fg='black', width=8, relief=tk.SUNKEN, state='normal')
        self.black_double_display.pack(pady=2)
        self.black_double_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("black_double"))

        sep = tk.Frame(main_inner, bg='white', width=2)
        sep.grid(row=0, column=1, sticky='ns', padx=5)

        # 右列：红牛
        right_frame = tk.Frame(main_inner, bg='#2a4a3c')
        right_frame.grid(row=0, column=2, sticky='nsew', padx=5)
        tk.Label(right_frame, text="红牛", font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white').pack(anchor='w')
        self.red_bet_display = tk.Label(right_frame, textvariable=self.red_bet_var, font=('Arial', 12),
                                        bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.red_bet_display.pack(pady=2)
        self.red_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("red"))
        tk.Label(right_frame, text="双倍", font=('Arial', 10), bg='#2a4a3c', fg='white').pack(anchor='w')
        self.red_double_display = tk.Label(right_frame, textvariable=self.red_double_var, font=('Arial', 12),
                                           bg='white', fg='black', width=8, relief=tk.SUNKEN, state='normal')
        self.red_double_display.pack(pady=2)
        self.red_double_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("red_double"))

        main_inner.columnconfigure(0, weight=1)
        main_inner.columnconfigure(2, weight=1)

        # ---------- 操作按钮 ----------
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X)
        self._create_action_buttons()

        # 状态信息
        self.status_label = tk.Label(control_frame, text="设置下注金额并开始游戏",
                                     font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.status_label.pack(pady=5, fill=tk.X)

        # 本局下注和上局获胜
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.current_bet_label = tk.Label(bet_info_frame, text="本局下注: $0.00",
                                          font=('Arial', 12), bg='#2a4a3c', fg='white')
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        self.last_win_label = tk.Label(bet_info_frame, text="上局获胜: $0.00",
                                       font=('Arial', 12), bg='#2a4a3c', fg='#FFD700')
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)

        rules_btn = tk.Button(bet_info_frame, text="ℹ️",
                              command=self.show_game_instructions,
                              font=('Arial', 8), bg='#4B8BBE', fg='white', width=2, height=1)
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)

    def _create_action_buttons(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

        self.reset_bets_button = tk.Button(start_button_frame, text="重置金额",
                                           command=self.reset_bets, font=('Arial', 14),
                                           bg='#F44336', fg='white', width=10)
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0,10))

        self.repeat_bet_btn = tk.Button(start_button_frame, text="重复上局下注", command=self.apply_last_bet,
                                        font=('Arial', 14), bg='#4A90E2', fg='white',
                                        activebackground='#3A7BC8', width=12,
                                        state=tk.NORMAL if self.last_bet is not None else tk.DISABLED)
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=(0,10))

        self.start_button = tk.Button(start_button_frame, text="开始游戏",
                                      command=self.start_game, font=('Arial', 14),
                                      bg='#4CAF50', fg='white', width=10)
        self.start_button.pack(side=tk.LEFT)

    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons = []
        self.selected_chip = None
        chip_configs = [
            ('$10', '#ffa500', 'black'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black'),
            ("$2.5K", '#ff0000', 'white')
        ]
        self.chip_texts = {}
        for text, bg_color, fg_color in chip_configs:
            chip_canvas = tk.Canvas(self.chip_container, width=57, height=57, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 55, 55, fill=bg_color, outline='black')
            chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip("$10")

    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("牛牛游戏规则")
        win.geometry("800x600")
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
        canvas_frame = canvas.create_window((0,0), window=content_frame, anchor='nw')

        rules = """
牛牛游戏规则

1. 下注:
   - 主注：选择下注“黑牛”或“红牛”，只能选一方，另一方自动禁用。
      - 主注赔率：0.95:1（即下注100赢95）
      - 在主注下方可额外下注“双倍”，双倍输赢加倍（见后）。
      - 黑牛方（主注+双倍）与红牛方互斥，任一方有下注则另一方全部禁用。
   - 边注：
      - “牛牛”：若最终黑牛或红牛任意一方牌型为牛牛，则赢，赔率5:1。
      - “双牛牛”：若最终黑牛和红牛双方都是牛牛，则赢，赔率100:1。

2. 发牌与亮牌:
   - 双方各发5张牌，同时亮牌。

3. 牌型判定（牛牛规则）:
   - 从5张牌中选3张，其点数之和为10的倍数（即尾数0），剩余2张点数之和的尾数即为牛几。
   - 尾数1-9为牛一~牛九，尾数0为牛牛。
   - 若无法选出三张和为10的倍数，则为“没牛”。

4. 牌型大小比较:
   牛牛 > 牛九 > 牛八 > ... > 牛一 > 没牛。
   若牌型相同，比较最大牌点数（A最大，2最小），若仍相同，比较花色（黑桃>红心>梅花>方块）。

5. 主注结算:
   - 获胜方：主注赔付0.95:1；若下了双倍，则按以下赔率：
       * 牛牛：2.85:1
       * 牛七/八/九：1.9:1
       * 其他（牛一~牛六、没牛）：0.95:1
   - 失败方：主注全输；若下了双倍，则额外扣除：
       * 对方牌型牛牛：扣除下注额的2倍（即额外200%，连本金共输300%）
       * 对方牌型牛七/八/九：扣除下注额的1倍（即额外100%，连本金共输200%）
       * 其他（没牛~牛六）：只输本金（无额外扣除）

6. 边注结算:
   - 若任意一方为牛牛，则“牛牛”下注赢5倍。
   - 若双方均为牛牛，则“双牛牛”下注赢100倍。

7. 排序显示:
   - 没牛：按从大到小排列（K>Q>...>2>A）。
   - 有牛：三张组成牛的组合降序排列在前，剩余两张降序排列在后，且第三张和第四张之间增加20px间距。
        """
        tk.Label(content_frame, text=rules, font=('微软雅黑', 11), bg='#F0F0F0',
                 justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def reset_bets(self):
        self.black_bet_var.set("0")
        self.red_bet_var.set("0")
        self.black_double_var.set("0")
        self.red_double_var.set("0")
        self.side_niu_var.set("0")
        self.side_double_niu_var.set("0")
        # 恢复所有输入框状态
        self.black_bet_display.config(state='normal', bg='white')
        self.red_bet_display.config(state='normal', bg='white')
        self.black_double_display.config(state='normal', bg='white')
        self.red_double_display.config(state='normal', bg='white')
        self.black_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("black"))
        self.red_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("red"))
        self.black_double_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("black_double"))
        self.red_double_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("red_double"))
        self.side_niu_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("side_niu"))
        self.side_double_niu_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("side_double_niu"))
        for display in [self.black_bet_display, self.red_bet_display,
                        self.black_double_display, self.red_double_display,
                        self.side_niu_display, self.side_double_niu_display]:
            display.config(bg='white')
        self.status_label.config(text="已重置所有下注")

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        self.black_bet_var.set(str(self.last_bet['black']))
        self.red_bet_var.set(str(self.last_bet['red']))
        self.black_double_var.set(str(self.last_bet['black_double']))
        self.red_double_var.set(str(self.last_bet['red_double']))
        self.side_niu_var.set(str(self.last_bet['side_niu']))
        self.side_double_niu_var.set(str(self.last_bet['side_double_niu']))
        self._update_bet_widgets_state()
        self.status_label.config(text="已应用上次下注")

    def _update_bet_widgets_state(self):
        """根据当前下注值更新输入框禁用状态（互斥逻辑）"""
        black_bet = int(self.black_bet_var.get())
        red_bet = int(self.red_bet_var.get())
        black_double = int(self.black_double_var.get())
        red_double = int(self.red_double_var.get())
        black_has = black_bet > 0 or black_double > 0
        red_has = red_bet > 0 or red_double > 0

        # 黑牛方有下注 -> 禁用红牛方
        if black_has:
            self.red_bet_display.config(state='disabled', bg='#C4C4C4')
            self.red_bet_display.unbind("<Button-1>")
            self.red_double_display.config(state='disabled', bg='#C4C4C4')
            self.red_double_display.unbind("<Button-1>")
        else:
            self.red_bet_display.config(state='normal', bg='white')
            self.red_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("red"))
            self.red_double_display.config(state='normal', bg='white')
            self.red_double_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("red_double"))

        # 红牛方有下注 -> 禁用黑牛方
        if red_has:
            self.black_bet_display.config(state='disabled', bg='#C4C4C4')
            self.black_bet_display.unbind("<Button-1>")
            self.black_double_display.config(state='disabled', bg='#C4C4C4')
            self.black_double_display.unbind("<Button-1>")
        else:
            self.black_bet_display.config(state='normal', bg='white')
            self.black_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("black"))
            self.black_double_display.config(state='normal', bg='white')
            self.black_double_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("black_double"))

    def start_game(self):
        try:
            black_bet = int(self.black_bet_var.get())
            red_bet = int(self.red_bet_var.get())
            black_double = int(self.black_double_var.get())
            red_double = int(self.red_double_var.get())
            side_niu = int(self.side_niu_var.get())
            side_double_niu = int(self.side_double_niu_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return

        # 只要四个主投注项任意一项有下注即可
        if black_bet == 0 and red_bet == 0 and black_double == 0 and red_double == 0:
            messagebox.showerror("错误", "请至少下注黑牛或红牛的任意一项（主注或双倍）")
            return
        if black_bet > 0 and red_bet > 0:
            messagebox.showerror("错误", "不能同时下注黑牛和红牛")
            return

        total_bet = black_bet + red_bet + black_double + red_double + side_niu + side_double_niu
        if self.balance < total_bet:
            messagebox.showerror("错误", "余额不足")
            return

        self.balance -= total_bet
        self.update_balance()

        self.last_bet = {
            'black': black_bet,
            'red': red_bet,
            'black_double': black_double,
            'red_double': red_double,
            'side_niu': side_niu,
            'side_double_niu': side_double_niu
        }
        self.repeat_bet_btn.config(state=tk.NORMAL)

        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        self.last_win_label.config(text="上局获胜: $0.00")

        # 禁用操作按钮
        self.reset_bets_button.config(state=tk.DISABLED)
        self.repeat_bet_btn.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)

        self.game.reset_game()
        self.game.deal_initial()
        self.game.black_bet = black_bet
        self.game.red_bet = red_bet
        self.game.black_double = black_double
        self.game.red_double = red_double
        self.game.side_niu_bet = side_niu
        self.game.side_double_niu_bet = side_double_niu

        for widget in self.black_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.red_cards_frame.winfo_children():
            widget.destroy()
        self.active_card_labels = []

        self.black_bet_display.unbind("<Button-1>")
        self.red_bet_display.unbind("<Button-1>")
        self.black_double_display.unbind("<Button-1>")
        self.red_double_display.unbind("<Button-1>")
        self.side_niu_display.unbind("<Button-1>")
        self.side_double_niu_display.unbind("<Button-1>")
        for chip in self.chip_buttons:
            chip.unbind("<Button-1>")

        self.stage_label.config(text="发牌中")
        self.status_label.config(text="发牌...")

        self.animation_queue = []
        self.card_positions = {}
        for i in range(5):
            self.card_positions[f"black_{i}"] = {"current": (50, 50), "target": (i*110, 0)}
            self.animation_queue.append(f"black_{i}")
        for i in range(5):
            self.card_positions[f"red_{i}"] = {"current": (50, 50), "target": (i*110, 0)}
            self.animation_queue.append(f"red_{i}")
        self.animate_deal()

    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_all_cards)
            return
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        if card_id.startswith("black"):
            frame = self.black_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.black_hand[idx]
        else:
            frame = self.red_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.red_hand[idx]
        card_label = tk.Label(frame, image=self.back_image, bg=frame['bg'])
        card_label.place(x=self.card_positions[card_id]["current"][0],
                         y=self.card_positions[card_id]["current"][1]+20,
                         width=120, height=180)
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        self.active_card_labels.append(card_label)
        self.animate_card_move(card_label)

    def animate_card_move(self, card_label):
        if not hasattr(card_label, "target_pos") or card_label not in self.active_card_labels:
            return
        try:
            current_x, current_y = card_label.winfo_x(), card_label.winfo_y()
            target_x, target_y = card_label.target_pos
            dx = target_x - current_x
            dy = target_y - current_y
            distance = math.sqrt(dx**2 + dy**2)
            if distance < 5:
                card_label.place(x=target_x, y=target_y, width=120, height=180)
                card_label.is_moving = False
                self.after(20, self.animate_deal)
                return
            step_x = dx * 0.2
            step_y = dy * 0.2
            new_x = current_x + step_x
            new_y = current_y + step_y
            card_label.place(x=new_x, y=new_y, width=120, height=180)
            self.after(20, lambda: self.animate_card_move(card_label))
        except tk.TclError:
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)
            return

    # ========== 翻牌动画 ==========
    def flip_card_animation(self, card_label, callback=None):
        """单张卡片的翻牌动画，完成后调用callback"""
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self._animate_flip(card_label, front_img, 0, callback)

    def _animate_flip(self, card_label, front_img, step, callback):
        steps = 10
        if step > steps:
            card_label.config(image=front_img)
            card_label.is_face_up = True
            card_label.place(width=120, height=180)
            if callback:
                callback()
            return
        if step <= steps/2:
            width = 120 - (step * 12)
            if width <= 0:
                width = 1
            card_label.config(image=self.back_image)
        else:
            width = (step - steps/2) * 12
            if width <= 0:
                width = 1
            card_label.config(image=front_img)
        card_label.place(width=width, height=180)
        self.after(50, lambda: self._animate_flip(card_label, front_img, step+1, callback))

    # ========== 移动动画 ==========
    def animate_cards_move_to_positions(self, labels_with_targets, callback):
        if not labels_with_targets:
            if callback:
                callback()
            return
        anim_data = []
        for label, tx, ty in labels_with_targets:
            if not label.winfo_exists():
                continue
            cx, cy = label.winfo_x(), label.winfo_y()
            dx = tx - cx
            dy = ty - cy
            anim_data.append((label, cx, cy, dx, dy))
        if not anim_data:
            if callback:
                callback()
            return
        steps = 15
        interval = 20
        self._move_step(anim_data, 0, steps, interval, callback)

    def _move_step(self, anim_data, step, total_steps, interval, callback):
        if step > total_steps:
            for label, cx, cy, dx, dy in anim_data:
                if label.winfo_exists():
                    label.place(x=cx+dx, y=cy+dy)
            if callback:
                callback()
            return
        progress = step / total_steps
        for label, cx, cy, dx, dy in anim_data:
            if label.winfo_exists():
                new_x = cx + dx * progress
                new_y = cy + dy * progress
                label.place(x=new_x, y=new_y)
        self.after(interval, lambda: self._move_step(anim_data, step+1, total_steps, interval, callback))

    # ========== 亮牌（同时翻转所有牌）==========
    def reveal_all_cards(self):
        """同时翻转所有牌"""
        labels = []
        for label in self.black_cards_frame.winfo_children():
            if hasattr(label, 'card') and not label.is_face_up:
                labels.append(label)
        for label in self.red_cards_frame.winfo_children():
            if hasattr(label, 'card') and not label.is_face_up:
                labels.append(label)

        if not labels:
            self.after(100, self.after_reveal)
            return

        self.flip_count = len(labels)
        def on_flip_complete():
            self.flip_count -= 1
            if self.flip_count == 0:
                self.after(500, self.after_reveal)

        for label in labels:
            self.flip_card_animation(label, on_flip_complete)

    # ========== 亮牌后处理：排序并移动 ==========
    def after_reveal(self):
        """亮牌后：评估牌型、排序、显示、结算"""
        # 评估并排序
        black_rank, black_sorted, _, _ = evaluate_niu(self.game.black_hand)
        red_rank, red_sorted, _, _ = evaluate_niu(self.game.red_hand)
        self.game.black_hand = black_sorted
        self.game.red_hand = red_sorted

        # 获取当前卡片标签
        black_labels = list(self.black_cards_frame.winfo_children())
        red_labels = list(self.red_cards_frame.winfo_children())

        # 构建 card -> label 映射
        black_label_map = {label.card: label for label in black_labels if hasattr(label, 'card')}
        red_label_map = {label.card: label for label in red_labels if hasattr(label, 'card')}

        def calc_targets(label_map, sorted_hand, rank):
            targets = []
            for i, card in enumerate(sorted_hand):
                label = label_map.get(card)
                if label and label.winfo_exists():
                    x = i * 110
                    if rank > 0 and i >= 3:
                        x += 20   # 有牛时，后两张右移20px
                    y = label.winfo_y()  # 保持当前垂直位置
                    targets.append((label, x, y))
            return targets

        black_targets = calc_targets(black_label_map, black_sorted, black_rank)
        red_targets = calc_targets(red_label_map, red_sorted, red_rank)

        all_targets = black_targets + red_targets
        if all_targets:
            self.animate_cards_move_to_positions(all_targets, self.after_sort_complete)
        else:
            self.after_sort_complete()

    def after_sort_complete(self):
        """排序动画完成后更新标签并结算"""
        black_rank, _, _, _ = evaluate_niu(self.game.black_hand)
        red_rank, _, _, _ = evaluate_niu(self.game.red_hand)
        self.black_label.config(text=f"黑牛 - {NIU_NAMES[black_rank]}")
        self.red_label.config(text=f"红牛 - {NIU_NAMES[red_rank]}")
        self.settle_game()

    # ========== 结算函数 ==========
    def settle_game(self):
        result = compare_niu_hands(self.game.black_hand, self.game.red_hand)
        black_win = (result == 1)
        red_win = (result == -1)
        push = (result == 0)

        black_rank, _, _, _ = evaluate_niu(self.game.black_hand)
        red_rank, _, _, _ = evaluate_niu(self.game.red_hand)

        # =========================
        # 赔率 / 倒扣规则
        # =========================
        def main_bet_return(stake):
            """主注获胜时的总返还额（本金 + 盈利），赔率 0.95:1"""
            return stake * 1.95

        def double_bet_return(stake, rank):
            """双倍获胜时的总返还额（本金 + 盈利）"""
            if rank == 10:          # 牛牛
                ratio = 2.85
            elif rank >= 7:         # 牛七 / 牛八 / 牛九
                ratio = 1.9
            else:                   # 其他牌型（含牛四）
                ratio = 0.95
            return stake * (1 + ratio)

        def double_extra_loss(opponent_rank, stake):
            """
            双倍失败时的额外扣除额（注意：本金已在开始游戏时扣过）
            对方牛牛       -> 额外扣 2 倍
            对方牛七/八/九 -> 额外扣 1 倍
            其他           -> 不额外扣
            """
            if opponent_rank == 10:
                return stake * 2
            elif opponent_rank >= 7:
                return stake * 1
            else:
                return 0

        bet_results = {
            'black': {'amount': self.game.black_bet, 'gross_return': 0, 'extra_loss': 0, 'win': False, 'push': False},
            'red': {'amount': self.game.red_bet, 'gross_return': 0, 'extra_loss': 0, 'win': False, 'push': False},
            'black_double': {'amount': self.game.black_double, 'gross_return': 0, 'extra_loss': 0, 'win': False, 'push': False},
            'red_double': {'amount': self.game.red_double, 'gross_return': 0, 'extra_loss': 0, 'win': False, 'push': False},
            'side_niu': {'amount': self.game.side_niu_bet, 'gross_return': 0, 'win': False},
            'side_double_niu': {'amount': self.game.side_double_niu_bet, 'gross_return': 0, 'win': False},
        }

        # =========================
        # 主注 / 双倍结算
        # =========================
        if black_win:
            if self.game.black_bet > 0:
                bet_results['black']['win'] = True
                bet_results['black']['gross_return'] = main_bet_return(self.game.black_bet)

            if self.game.black_double > 0:
                bet_results['black_double']['win'] = True
                bet_results['black_double']['gross_return'] = double_bet_return(self.game.black_double, black_rank)

            if self.game.red_bet > 0:
                bet_results['red']['win'] = False

            if self.game.red_double > 0:
                bet_results['red_double']['win'] = False
                bet_results['red_double']['extra_loss'] = double_extra_loss(black_rank, self.game.red_double)

        elif red_win:
            if self.game.red_bet > 0:
                bet_results['red']['win'] = True
                bet_results['red']['gross_return'] = main_bet_return(self.game.red_bet)

            if self.game.red_double > 0:
                bet_results['red_double']['win'] = True
                bet_results['red_double']['gross_return'] = double_bet_return(self.game.red_double, red_rank)

            if self.game.black_bet > 0:
                bet_results['black']['win'] = False

            if self.game.black_double > 0:
                bet_results['black_double']['win'] = False
                bet_results['black_double']['extra_loss'] = double_extra_loss(red_rank, self.game.black_double)

        else:
            # 平局：本金退回，双倍本金也退回
            if self.game.black_bet > 0:
                bet_results['black']['push'] = True
                bet_results['black']['gross_return'] = self.game.black_bet
            if self.game.red_bet > 0:
                bet_results['red']['push'] = True
                bet_results['red']['gross_return'] = self.game.red_bet
            if self.game.black_double > 0:
                bet_results['black_double']['push'] = True
                bet_results['black_double']['gross_return'] = self.game.black_double
            if self.game.red_double > 0:
                bet_results['red_double']['push'] = True
                bet_results['red_double']['gross_return'] = self.game.red_double

        # =========================
        # 边注
        # =========================
        if self.game.side_niu_bet > 0:
            if black_rank == 10 or red_rank == 10:
                bet_results['side_niu']['win'] = True
                bet_results['side_niu']['gross_return'] = self.game.side_niu_bet * 6   # 5:1
            else:
                bet_results['side_niu']['win'] = False
                bet_results['side_niu']['gross_return'] = 0

        if self.game.side_double_niu_bet > 0:
            if black_rank == 10 and red_rank == 10:
                bet_results['side_double_niu']['win'] = True
                bet_results['side_double_niu']['gross_return'] = self.game.side_double_niu_bet * 101  # 100:1
            else:
                bet_results['side_double_niu']['win'] = False
                bet_results['side_double_niu']['gross_return'] = 0

        # =========================
        # 统计净变化
        # =========================
        total_gross_return = 0
        total_extra_loss = 0

        for data in bet_results.values():
            total_gross_return += data.get('gross_return', 0)
            total_extra_loss += data.get('extra_loss', 0)

        total_bet = (
            self.game.black_bet + self.game.red_bet +
            self.game.black_double + self.game.red_double +
            self.game.side_niu_bet + self.game.side_double_niu_bet
        )

        # 这里是“本局最终余额变化”
        # 注意：开始游戏时已经先扣过 total_bet，所以这里再加回返还，并减去额外倒扣
        net_change = total_gross_return - total_bet - total_extra_loss

        self.balance += net_change
        self.update_balance()

        # =========================
        # 更新下注格子显示
        # =========================
        display_map = {
            'black': self.black_bet_display,
            'red': self.red_bet_display,
            'black_double': self.black_double_display,
            'red_double': self.red_double_display,
            'side_niu': self.side_niu_display,
            'side_double_niu': self.side_double_niu_display,
        }

        for key, data in bet_results.items():
            display = display_map.get(key)
            if not display:
                continue

            amount = data['amount']
            if amount == 0:
                display.config(text="0", bg='white')
                continue

            if data.get('win', False):
                # 显示“总返还额”，不是净赢
                display.config(text=f"{data['gross_return']:.2f}", bg='gold')
            elif data.get('push', False):
                display.config(text=f"{amount:.2f}", bg='light blue')
            else:
                extra = data.get('extra_loss', 0)
                if extra > 0:
                    display.config(text=f"-{extra:.2f}", bg='lightcoral')
                else:
                    display.config(text="0", bg='white')

        # =========================
        # 状态栏 / 上局结果
        # =========================
        self.last_win = net_change
        self.last_win_label.config(text=f"上局净变化: ${net_change:.2f}")

        if net_change >= 0:
            self.status_label.config(text=f"结算完成，净赢 ${net_change:.2f}")
        else:
            self.status_label.config(text=f"结算完成，净输 ${-net_change:.2f}")

        if self.game.side_niu_bet > 0 and bet_results['side_niu']['win']:
            self.after(100, lambda: messagebox.showinfo(
                "边注牛牛",
                f"牛牛边注总返还 ${bet_results['side_niu']['gross_return']:.2f}，净赢 ${bet_results['side_niu']['gross_return'] - self.game.side_niu_bet:.2f}"
            ))

        if self.game.side_double_niu_bet > 0 and bet_results['side_double_niu']['win']:
            self.after(100, lambda: messagebox.showinfo(
                "边注双牛牛",
                f"双牛牛边注总返还 ${bet_results['side_double_niu']['gross_return']:.2f}，净赢 ${bet_results['side_double_niu']['gross_return'] - self.game.side_double_niu_bet:.2f}"
            ))

        # 重建操作按钮（只显示“再来一局”）
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        restart_btn = tk.Button(
            self.action_frame,
            text="再来一局",
            command=self.reset_game,
            font=('Arial', 14),
            bg='#2196F3',
            fg='white',
            width=15
        )
        restart_btn.pack(pady=5)
        restart_btn.bind("<Button-3>", self.show_card_sequence)

        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def reset_game(self, auto_reset=False):
        self.cancel_auto_reset_timer()
        self._resetting = True

        # 清空牌面
        for widget in self.black_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.red_cards_frame.winfo_children():
            widget.destroy()
        self.active_card_labels = []

        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="等待下注")
        self.status_label.config(text="设置下注金额并开始游戏")
        self.black_label.config(text="黑牛")
        self.red_label.config(text="红牛")

        # 重置下注变量和显示背景
        self.black_bet_var.set("0")
        self.red_bet_var.set("0")
        self.black_double_var.set("0")
        self.red_double_var.set("0")
        self.side_niu_var.set("0")
        self.side_double_niu_var.set("0")
        for display in [self.black_bet_display, self.red_bet_display,
                        self.black_double_display, self.red_double_display,
                        self.side_niu_display, self.side_double_niu_display]:
            display.config(bg='white', text='0')

        # 重新绑定事件（在 _create_action_buttons 中也会重新创建按钮，但显示绑定需要重新做）
        self.black_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("black"))
        self.red_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("red"))
        self.black_bet_display.config(state='normal')
        self.red_bet_display.config(state='normal')
        self.black_double_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("black_double"))
        self.red_double_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("red_double"))
        self.black_double_display.config(state='normal')
        self.red_double_display.config(state='normal')
        self.side_niu_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("side_niu"))
        self.side_double_niu_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("side_double_niu"))
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))

        # 重建按钮（重置金额/重复下注/开始游戏）
        self._create_action_buttons()

        self._resetting = False
        self.current_bet_label.config(text="本局下注: $0.00")
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

    def show_card_sequence(self, event):
        self.cancel_auto_reset_timer()
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600")
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        cut_label = tk.Label(win, text=f"本局切牌位置: {self.game.cut_position+1}",
                             font=('Arial', 14, 'bold'), bg='#f0f0f0')
        cut_label.pack(pady=(10,5))
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas.create_window((0,0), window=content_frame, anchor='nw')
        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        small_size = (60,90)
        small_images = {}
        for i, card in enumerate(self.game.card_sequence):
            key = (card.suit, card.rank)
            if key in self.original_images:
                orig = self.original_images[key]
                small = orig.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small)
            else:
                back = self.original_images.get("back")
                if back:
                    small = back.resize(small_size, Image.LANCZOS)
                    small_images[i] = ImageTk.PhotoImage(small)
        for row in range(7):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)
            cards_in_row = 8 if row < 6 else 4
            for col in range(cards_in_row):
                idx = row*8 + col
                if idx >= 52: break
                container = tk.Frame(row_frame, bg='#f0f0f0')
                container.grid(row=0, column=col, padx=5, pady=5)
                bg = 'light blue' if idx == self.game.cut_position else '#f0f0f0'
                if idx in small_images:
                    label = tk.Label(container, image=small_images[idx], bg=bg, borderwidth=1, relief="solid")
                    label.image = small_images[idx]
                    label.pack()
                else:
                    card = self.game.card_sequence[idx]
                    label = tk.Label(container, text=f"{card.rank}{card.suit}", bg=bg,
                                     width=6, height=3, borderwidth=1, relief="solid")
                    label.pack()
                pos_label = tk.Label(container, text=str(idx+1), bg=bg, font=('Arial',9))
                pos_label.pack()
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

def main(initial_balance=10000, username="Guest"):
    app = NiuNiuGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")