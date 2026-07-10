import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import secrets
import subprocess
import sys
import time
from collections import Counter

# ========================== 全局常量和样式 ==========================
ROOT_BG = "#1B3D31"
CYAN = "#007502"
TEXT = "#ffffff"
RED = "#ff2a23"
BLACK = "#050505"
DARK_BLUE = "#173f66"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '皇家同花顺',
    8: '同花顺',
    7: '四条',
    6: '葫芦',
    5: '同花',
    4: '顺子',
    3: '三条',
    2: '两对',
    1: '对子(J-A)',
    0: '高牌'
}

VIDEO_POKER_PAYOUT = {
    9: 800,
    8: 50,
    7: 25,
    6: 9,
    5: 6,
    4: 4,
    3: 3,
    2: 2,
    1: 1
}

# ========================== Progressive 加载/保存（与 Three Card Poker 共用） ==========================
PROGRESSIVE_MIN = 271288.59
PROGRESSIVE_DEFAULT = 271288.59
PROGRESSIVE_KEY = "Progressive_2.50"

def load_progressive():
    """从 Progressive.json 加载奖池金额，若文件不存在或条目缺失则返回默认值"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    if not os.path.exists(path):
        return PROGRESSIVE_DEFAULT
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == PROGRESSIVE_KEY:
                    amount = float(item.get('jackpot', PROGRESSIVE_DEFAULT))
                    return max(amount, PROGRESSIVE_MIN)
    except Exception:
        pass
    return PROGRESSIVE_DEFAULT

def save_progressive(amount):
    """保存奖池金额到 Progressive.json"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    found = False
    for item in data:
        if item.get('Games') == PROGRESSIVE_KEY:
            item['jackpot'] = max(amount, PROGRESSIVE_MIN)
            found = True
            break
    if not found:
        data.append({"Games": PROGRESSIVE_KEY, "jackpot": max(amount, PROGRESSIVE_MIN)})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# ========================== 文件操作（用户余额） ==========================
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

# ========================== 历史记录（Video_Poker.json） ==========================
def video_poker_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Video_Poker.json")

def save_video_poker_history(deck, ori_cards, aft_cards, bet, win_amount, hand_rank, hand_name, is_win):
    """
    保存牌局历史。
    history_record 包含 game, win, lose 以及各牌型计数（含 pair_2_10 和 pair_j_a）。
    """
    log_path = video_poker_log_path()
    # 初始化数据结构
    data = {
        "history_record": {
            "game": 0,
            "win": 0,
            "lose": 0,
            # 牌型计数（英文键）
            "royal_flush": 0,
            "straight_flush": 0,
            "four_of_a_kind": 0,
            "full_house": 0,
            "flush": 0,
            "straight": 0,
            "three_of_a_kind": 0,
            "two_pair": 0,
            "pair_j_a": 0,
            "pair_2_10": 0,
            "high_card": 0
        },
        "history": []
    }

    # 读取已有记录
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "history_record" in loaded:
                    # 确保所有字段存在
                    for key in data["history_record"]:
                        if key not in loaded["history_record"]:
                            loaded["history_record"][key] = 0
                    data["history_record"] = loaded["history_record"]
                    if "history" in loaded:
                        data["history"] = loaded["history"]
                elif isinstance(loaded, list):
                    # 旧格式迁移
                    data["history"] = loaded
                    stats = {"game": len(loaded), "win": 0, "lose": 0}
                    for rec in loaded:
                        if "win_amount" in rec:
                            if rec["win_amount"] > 0:
                                stats["win"] += 1
                            else:
                                stats["lose"] += 1
                    data["history_record"].update(stats)
        except Exception as e:
            print(f"读取历史文件出错: {e}，将使用全新记录")

    stats = data["history_record"]
    stats["game"] += 1
    if win_amount > 0:
        stats["win"] += 1
    else:
        stats["lose"] += 1

    # 根据 hand_name 增加牌型计数
    # hand_name 可能值：皇家同花顺, 同花顺, 四条, 葫芦, 同花, 顺子, 三条, 两对, 对子(J-A), 对子(2-10), 高牌
    name_to_key = {
        '皇家同花顺': 'royal_flush',
        '同花顺': 'straight_flush',
        '四条': 'four_of_a_kind',
        '葫芦': 'full_house',
        '同花': 'flush',
        '顺子': 'straight',
        '三条': 'three_of_a_kind',
        '两对': 'two_pair',
        '对子(J-A)': 'pair_j_a',
        '对子(2-10)': 'pair_2_10',
        '高牌': 'high_card'
    }
    key = name_to_key.get(hand_name, 'high_card')
    stats[key] = stats.get(key, 0) + 1

    # 生成新 game_id
    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1

    # 构建记录
    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "ori_cards": [str(c) for c in ori_cards],
        "aft_cards": [str(c) for c in aft_cards],
        "win_amount": win_amount,
        "hand_rank": hand_rank,
        "hand_name": hand_name,
        "is_win": is_win
    }
    data["history"].append(record)

    # 保留最新50局
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ========================== 扑克牌类与牌堆 ==========================
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

# ========================== 五张牌评估（用于 Progressive） ==========================
def evaluate_five_card_hand(cards):
    if not cards or len(cards) < 5:
        return (0, [])
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1

    values_asc = sorted([c.value for c in cards])
    is_straight = False
    straight_values = None
    if len(set(values_asc)) == 5:
        if values_asc[-1] - values_asc[0] == 4:
            is_straight = True
            straight_values = sorted(values, reverse=True)
        elif values_asc == [2,3,4,5,14]:
            is_straight = True
            straight_values = [5,4,3,2,1]

    is_royal = is_straight and is_flush and values[0] == 14 and values[4] == 10
    if is_straight and is_flush:
        return (9 if is_royal else 8, straight_values)

    value_count = {}
    for v in values:
        value_count[v] = value_count.get(v, 0) + 1
    sorted_counts = sorted(value_count.items(), key=lambda x: (x[1], x[0]), reverse=True)
    sorted_values = [item[0] for item in sorted_counts]

    if sorted_counts[0][1] == 4:
        return (7, sorted_values)
    if sorted_counts[0][1] == 3 and sorted_counts[1][1] == 2:
        return (6, sorted_values)
    if is_flush:
        return (5, values)
    if is_straight:
        return (4, straight_values)
    if sorted_counts[0][1] == 3:
        return (3, sorted_values)
    if sorted_counts[0][1] == 2 and sorted_counts[1][1] == 2:
        return (2, sorted_values)
    if sorted_counts[0][1] == 2:
        pair_value = sorted_counts[0][0]
        if pair_value >= 11:
            return (1, sorted_values)
        else:
            return (0, sorted_values)
    return (0, values)

# ========================== 游戏逻辑类 ==========================
class VideoPokerGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.bet_amount = 0
        self.stage = "betting"
        self.hold_status = [False] * 5
        self.final_hand = False

    def deal_initial(self):
        self.player_hand = self.deck.deal(5)

    def draw_cards(self):
        for i in range(5):
            if not self.hold_status[i]:
                self.player_hand[i] = self.deck.deal(1)[0]
        self.final_hand = True

# ========================== 主GUI类 ==========================
class VideoPokerGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("视频扑克")
        self.geometry("1150x750+50+10")
        self.resizable(0,0)
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = VideoPokerGame()
        self.card_images = {}
        self.original_images = {}
        self.back_image = None
        self.grey_back = None
        self.animation_queue = []
        self.animation_in_progress = False
        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.last_win = 0
        self.last_bet = None
        self.repeat_bet_btn = None
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.bet_widgets = {}

        self.high_bet_mode = False
        self.game_in_progress = False

        self.bottom_labels = []
        self.hold_labels = []
        self.player_label = None
        self.initial_hand = []          # 保存初始发牌时的5张牌（原始手牌）
        self.initial_thumbnails = []    # 缩略图标签列表

        # ---------- Progressive 相关 ----------
        self.progressive_var = tk.IntVar(value=0)        # 复选框状态
        self.progressive_amount = load_progressive()     # 当前奖池金额
        self.min_progressive = PROGRESSIVE_MIN
        self.last_progressive_state = 0                  # 用于重置时恢复

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()

    # ---------- 加载扑克牌 ----------
    def _load_assets(self):
        card_size = (100, 140)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not hasattr(self, 'current_poker_folder'):
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠':'Spade','♥':'Heart','♦':'Diamond','♣':'Club'}
        self.original_images = {}

        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            back_img = back_img_orig.resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
            grey_img = back_img_orig.convert('L').convert('RGB')
            grey_img = grey_img.resize(card_size)
            self.grey_back = ImageTk.PhotoImage(grey_img)
        except:
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
            grey_img = Image.new('RGB', card_size, 'grey')
            self.grey_back = ImageTk.PhotoImage(grey_img)

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
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        text = f"{rank}{suit}"
                        tw, th = draw.textsize(text, font=font)
                        draw.text(((card_size[0]-tw)//2, (card_size[1]-th)//2), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except:
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    draw.text((10,10), "Error", fill="white", font=font)
                    self.original_images[(suit, rank)] = img_orig
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)

    # ---------- 筹码选择 ----------
    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1,y1,x2,y2 = chip.coords(item_id)
                    chip.create_oval(x1,y1,x2,y2, outline='black', width=2)
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
                x1,y1,x2,y2 = chip.coords(oval_id)
                chip.create_oval(x1,y1,x2,y2, outline='#2f00ff', width=3, tags="highlight")
                break

    def add_chip_to_bet(self):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K','')) * 1000
        else:
            chip_value = float(chip_text)

        max_bet = 50000 if not self.high_bet_mode else 250000
        current = int(self.bet_var.get()) if self.bet_var.get().isdigit() else 0
        if current >= max_bet:
            messagebox.showwarning("下注限制", f"主注已满（上限{max_bet}）")
            return
        new_amount = current + chip_value
        if new_amount > max_bet:
            new_amount = max_bet
            if current > 0:
                messagebox.showwarning("下注限制", f"主注已达上限，自动调整为 {int(new_amount)}")
        self.bet_var.set(str(int(new_amount)))

    def reset_bet(self, event=None):
        self.bet_var.set("0")
        if "bet" in self.bet_widgets:
            widget = self.bet_widgets["bet"]
            widget.config(bg='#FFCDD2')
            self.after(500, lambda: widget.config(bg='white'))

    def reset_bets(self):
        self.bet_var.set("0")
        self.status_label.config(text="已重置主注金额")
        if "bet" in self.bet_widgets:
            self.bet_widgets["bet"].config(bg='#FFCDD2')
            self.after(500, lambda: self.bet_widgets["bet"].config(bg='white'))

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        bet = self.last_bet['bet']
        max_bet = 50000 if not self.high_bet_mode else 250000
        if bet > max_bet:
            bet = max_bet
        self.bet_var.set(str(bet))
        self.status_label.config(text="已应用上次下注金额")
        if "bet" in self.bet_widgets:
            self.bet_widgets["bet"].config(bg='#E8F5E9')
            self.after(800, lambda: self.bet_widgets["bet"].config(bg='white'))

    def clear_btn_frame(self):
        for widget in self.btn_frame.winfo_children():
            widget.destroy()

    def add_main_buttons(self):
        self.clear_btn_frame()
        self.btn_frame.pack_propagate(False)
        self.btn_frame.config(height=50)

        self.reset_bets_button = tk.Button(
            self.btn_frame, text="重置金额", command=self.reset_bets,
            font=('Arial',12,'bold'), bg='#F44336', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.repeat_bet_btn = tk.Button(
            self.btn_frame, text="重复上局下注", command=self.apply_last_bet,
            font=('Arial',12,'bold'), bg='#FFC107', fg='black',
            relief=tk.RAISED, bd=2, cursor="hand2", width=12,
            state=tk.NORMAL if self.last_bet is not None else tk.DISABLED
        )
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.start_button = tk.Button(
            self.btn_frame, text="开始游戏", command=self.start_game,
            font=('Arial',12,'bold'), bg='#4CAF50', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.start_button.pack(side=tk.LEFT, padx=5, pady=5)

    def add_draw_button(self):
        self.clear_btn_frame()
        self.btn_frame.pack_propagate(False)
        self.btn_frame.config(height=50)
        self.draw_button = tk.Button(
            self.btn_frame, text="抽牌", command=self.draw_action,
            state=tk.DISABLED,
            font=('Arial',12,'bold'), bg='#2196F3', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.draw_button.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    # ---------- 创建主界面 ----------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_canvas.create_rectangle(0,0,725,720, fill=ROOT_BG, outline=GOLD, width=5)

        # 主牌区（手牌）
        card_area = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        card_area.place(x=40, y=100, width=640, height=275)

        self.player_label = tk.Label(card_area, text="手牌", font=('Arial',18,'bold'),
                                     bg='#2a4a3c', fg='white')
        self.player_label.pack(anchor='w', padx=10, pady=(5,0))

        bottom_frame = tk.Frame(card_area, bg='#2a4a3c')
        bottom_frame.pack(fill=tk.X, pady=(20,5))
        bottom_cards = tk.Frame(bottom_frame, bg='#2a4a3c')
        bottom_cards.pack(pady=5)
        self.bottom_labels = []
        self.hold_labels = []
        for i in range(5):
            container = tk.Frame(bottom_cards, bg='#2a4a3c', width=100, height=160)
            container.pack(side=tk.LEFT, padx=10)
            container.pack_propagate(False)

            hold_lbl = tk.Label(container, text="保留", font=('Arial',10,'bold'),
                                bg='gold', fg='black', padx=5)
            hold_lbl.place(x=0, y=0)
            hold_lbl.place_forget()
            self.hold_labels.append(hold_lbl)

            lbl = tk.Label(container, image=self.back_image, bg='#2a4a3c', bd=0, relief='flat')
            lbl.place(x=0, y=20)
            lbl.bind("<Button-1>", lambda e, idx=i: self.toggle_hold(idx))
            self.bottom_labels.append(lbl)

        # 初始牌显示区（原始手牌）
        initial_area = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        initial_area.place(x=40, y=480, width=640, height=200)
        tk.Label(initial_area, text="原始手牌", font=('Arial',12,'bold'),
                 bg='#2a4a3c', fg='white').pack(anchor='w', padx=10, pady=(5,0))
        initial_cards = tk.Frame(initial_area, bg='#2a4a3c')
        initial_cards.pack(pady=5)
        self.initial_thumbnails = []
        card_size = (100, 140)
        for i in range(5):
            container = tk.Frame(initial_cards, bg='#2a4a3c', width=card_size[0]+10, height=card_size[1]+20)
            container.pack(side=tk.LEFT, padx=8)
            container.pack_propagate(False)
            lbl = tk.Label(container, image=self.back_image, bg='#2a4a3c', bd=0, relief='flat')
            lbl.place(x=5, y=10)
            self.initial_thumbnails.append(lbl)

        # 右侧面板
        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        # ------ 信息卡片 ------
        info_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=3)
        header_info = tk.Frame(info_card, bg=HEADER_BG)
        header_info.pack(fill=tk.X)
        body_info = tk.Frame(info_card, bg=PANEL_BG)
        body_info.pack(fill=tk.X, padx=10, pady=8)

        self.balance_label = tk.Label(body_info, text=f"余额: ${self.balance:,.2f}", font=('Arial',16,'bold'),
                                      bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body_info, text="下注", font=('Arial',16,'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # ------ 限红卡片（可点击切换高额） ------
        limit_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        header_limit = tk.Frame(limit_card, bg=HEADER_BG)
        header_limit.pack(fill=tk.X)
        tk.Label(header_limit, text="下注上限", font=('Arial',13,'bold'),
                 bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_limit = tk.Frame(limit_card, bg=PANEL_BG)
        body_limit.pack(fill=tk.X, padx=10, pady=8)

        table_frame = tk.Frame(body_limit, bg=PANEL_BG, bd=2, relief=tk.SOLID)
        table_frame.pack(fill=tk.X)
        titles = ["主注最低", "主注最高"]
        for col,title in enumerate(titles):
            lbl = tk.Label(table_frame, text=title, font=('Arial',11,'bold'),
                           bg=PANEL_BG, fg='#2A1B08', borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
            lbl.grid(row=0, column=col, sticky="nsew", padx=0, pady=0)
        self.min_bet_label = tk.Label(table_frame, text="$100", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.min_bet_label.grid(row=1, column=0, sticky="nsew")
        self.max_bet_label = tk.Label(table_frame, text="$50,000", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.max_bet_label.grid(row=1, column=1, sticky="nsew")
        for col in range(2):
            table_frame.columnconfigure(col, weight=1)

        for w in [limit_card, header_limit, body_limit, table_frame,
                  self.min_bet_label, self.max_bet_label]:
            w.bind("<Button-1>", self.toggle_high_bet_limits)

        # ------ 累进大奖卡片（新增独立卡片） ------
        progressive_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        progressive_card.pack(fill=tk.X, pady=3)
        header_prog = tk.Frame(progressive_card, bg=HEADER_BG)
        header_prog.pack(fill=tk.X)
        tk.Label(header_prog, text="累进大奖", font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_prog = tk.Frame(progressive_card, bg=PANEL_BG)
        body_prog.pack(fill=tk.X, padx=10, pady=8)
        self.progressive_amount_var = tk.StringVar()
        self.progressive_amount_var.set(f"${self.progressive_amount:,.2f}")
        self.progressive_display = tk.Label(body_prog, textvariable=self.progressive_amount_var,
                                            font=('Arial', 20, 'bold'), bg=PANEL_BG, fg='#A88100')
        self.progressive_display.pack(anchor='center')

        # ------ 筹码与下注卡片（含 Progressive 复选框） ------
        combined_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined_card.pack(fill=tk.X, pady=3)
        header_combined = tk.Frame(combined_card, bg=HEADER_BG)
        header_combined.pack(fill=tk.X)
        tk.Label(header_combined, text="筹码与下注", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_combined = tk.Frame(combined_card, bg=PANEL_BG)
        body_combined.pack(fill=tk.X, padx=10, pady=8)
        body_combined.columnconfigure(0, weight=1)

        chip_row = tk.Frame(body_combined, bg=PANEL_BG)
        chip_row.grid(row=0, column=0, pady=(0,8), sticky='ew')
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)
        self.chip_container = chip_row

        chip_configs = [
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black'),
            ("$5K", '#ff0000', 'white'),
            ("$10K", '#00fbff', 'black'),
            ("$50K", '#00ffae', 'black')
        ]
        self.chip_buttons = []
        self.chip_texts = {}
        for i,(text,bg_color,fg_color) in enumerate(chip_configs):
            cell = tk.Frame(chip_row, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2,2,49,49, fill=bg_color, outline='black')
            chip_canvas.create_text(25.5,25.5, text=text, fill=fg_color, font=('Arial',12,'bold'))
            chip_canvas.bind("<Button-1>", lambda e,t=text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip("$100")

        # ----- Progressive 复选框（不再显示金额，仅复选框） -----
        prog_row = tk.Frame(body_combined, bg=PANEL_BG)
        prog_row.grid(row=1, column=0, sticky='ew', pady=4)
        self.progressive_cb = tk.Checkbutton(
            prog_row, text="累进大奖 ($2.50)", variable=self.progressive_var,
            font=('Arial', 12, 'bold'), bg=PANEL_BG, fg='black', selectcolor=PANEL_BG
        )
        self.progressive_cb.pack(side=tk.LEFT)

        bet_row = tk.Frame(body_combined, bg=PANEL_BG)
        bet_row.grid(row=2, column=0, sticky='ew', pady=4)
        tk.Label(bet_row, text="主注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.bet_var = tk.StringVar(value="0")
        self.bet_display = tk.Label(bet_row, textvariable=self.bet_var, font=('Arial',12),
                                     bg='white', fg='black', width=10, relief=tk.SUNKEN)
        self.bet_display.pack(side=tk.LEFT, padx=5)
        self.bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet())
        self.bet_display.bind("<Button-3>", self.reset_bet)
        self.bet_widgets["bet"] = self.bet_display

        # ------ 操作卡片 ------
        action_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        action_card.pack(fill=tk.X, pady=3)
        header_action = tk.Frame(action_card, bg=HEADER_BG)
        header_action.pack(fill=tk.X)
        tk.Label(header_action, text="操作", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_action = tk.Frame(action_card, bg=PANEL_BG)
        body_action.pack(fill=tk.X, padx=10, pady=8)

        self.status_label = tk.Label(
            body_action, text="设置下注金额并开始游戏", font=('Arial',12,'bold'),
            bg=PANEL_BG, fg='#2A1B08', height=1
        )
        self.status_label.pack(fill=tk.X, pady=4)

        self.btn_frame = tk.Frame(body_action, bg=PANEL_BG)
        self.btn_frame.pack(fill=tk.X, pady=5)
        self.add_main_buttons()

        # ------ 底部信息卡片 ------
        info_bottom_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_bottom_card.pack(fill=tk.X, pady=3)
        body_bottom = tk.Frame(info_bottom_card, bg=PANEL_BG)
        body_bottom.pack(fill=tk.X, padx=10, pady=8)

        self.current_bet_label = tk.Label(
            body_bottom, text="本局下注: $0.00", font=('Arial',12), bg=PANEL_BG, fg='black'
        )
        self.current_bet_label.pack(anchor='w')
        row_last = tk.Frame(body_bottom, bg=PANEL_BG)
        row_last.pack(fill=tk.X, pady=2)
        self.last_win_label = tk.Label(
            row_last, text="上局获胜: $0.00", font=('Arial',12), bg=PANEL_BG, fg='black'
        )
        self.last_win_label.pack(side=tk.LEFT)
        self.info_button = tk.Button(
            row_last, text="ℹ️", command=self.show_game_instructions,
            bg='#4B8BBE', fg='white', font=('Arial',12), width=2, relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)

        # 绑定 Progressive 复选框更新奖池显示（但显示在独立卡片上）
        self.progressive_var.trace_add('write', self._update_progressive_display)

    def _update_progressive_display(self, *args):
        self.progressive_amount_var.set(f"${self.progressive_amount:,.2f}")

    # ---------- 高额模式 ----------
    def toggle_high_bet_limits(self, event=None):
        if self.game_in_progress:
            return
        current_password = time.strftime("%H%M")
        if not self.high_bet_mode:
            pwd = simpledialog.askstring("高额下注", "请输入密码：", parent=self)
            if pwd is None:
                return
            if pwd.strip() != current_password:
                messagebox.showerror("错误","密码错误")
                return
            self.high_bet_mode = True
            self.reset_bets()
        else:
            self.high_bet_mode = False
            self.reset_bets()
        self._update_limits_display()
        self._rebuild_chips()

    def _update_limits_display(self):
        if self.high_bet_mode:
            self.min_bet_label.config(text="$1000")
            self.max_bet_label.config(text="$250,000")
        else:
            self.min_bet_label.config(text="$100")
            self.max_bet_label.config(text="$50,000")

    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons = []
        self.chip_texts = {}
        self.selected_chip = None

        if self.high_bet_mode:
            chip_configs = [
                ("$1K", '#ffffff', 'black'),
                ("$5K", '#ff0000', 'white'),
                ("$10K", '#00fbff', 'black'),
                ("$50K", '#00ffae', 'black'),
                ("$100K", "#FFA600", 'black'),
                ("$250K", "#FF00B7", 'white'),
            ]
            default = "$1K"
        else:
            chip_configs = [
                ("$100", '#000000', 'white'),
                ("$500", "#FF7DDA", 'black'),
                ("$1K", '#ffffff', 'black'),
                ("$5K", '#ff0000', 'white'),
                ("$10K", '#00fbff', 'black'),
                ("$50K", '#00ffae', 'black')
            ]
            default = "$100"

        for i,(text,bg_color,fg_color) in enumerate(chip_configs):
            cell = tk.Frame(self.chip_container, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2,2,49,49, fill=bg_color, outline='black')
            chip_canvas.create_text(25.5,25.5, text=text, fill=fg_color, font=('Arial',12,'bold'))
            chip_canvas.bind("<Button-1>", lambda e,t=text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip(default)

    # ---------- 游戏规则（更新累进大奖说明） ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("视频扑克游戏规则")
        win.geometry("800x700")
        win.resizable(False,False)
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

        rules_text = """
        视频扑克 游戏规则

        1. 下注阶段：
           - 选择筹码点击主注区域增加下注
           - 勾选“累进大奖 ($2.50)”参与累进奖池

        2. 游戏流程：
           a. 发牌：5张手牌全部翻开
           b. 保留阶段：点击牌切换保留状态（保留的牌不替换）
           c. 抽牌：点击“抽牌”从牌堆中抽取新牌替换未保留的牌
           d. 结算：根据最终牌型按赔率支付

        3. 赔付表：
        """
        tk.Label(content_frame, text=rules_text, font=('微软雅黑',11),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        payout_frame = tk.Frame(content_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=20, pady=5)
        headers = ["牌型", "赔率"]
        data = [
            ("皇家同花顺", "800:1"),
            ("同花顺", "50:1"),
            ("四条", "25:1"),
            ("葫芦", "9:1"),
            ("同花", "6:1"),
            ("顺子", "4:1"),
            ("三条", "3:1"),
            ("两对", "2:1"),
            ("对子(J-A)", "1:1"),
            ("其他", "输")
        ]
        for col,h in enumerate(headers):
            tk.Label(payout_frame, text=h, font=('微软雅黑',10,'bold'),
                     bg='#4B8BBE', fg='white', padx=10, pady=5,
                     anchor='center').grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r,row_data in enumerate(data, start=1):
            bg = '#E0E0E0' if r%2==0 else '#F0F0F0'
            for c,txt in enumerate(row_data):
                tk.Label(payout_frame, text=txt, font=('微软雅黑',10),
                         bg=bg, padx=10, pady=5, anchor='center'
                         ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(headers)):
            payout_frame.columnconfigure(c, weight=1)

        # --- 累进大奖表格（新增） ---
        tk.Label(content_frame, text="累进大奖", font=('微软雅黑',12,'bold'),
                 bg='#F0F0F0', fg='#2A1B08', anchor='w').pack(fill=tk.X, padx=20, pady=(15,5))
        prog_frame = tk.Frame(content_frame, bg='#F0F0F0')
        prog_frame.pack(fill=tk.X, padx=20, pady=5)
        prog_headers = ["牌型", "奖励"]
        prog_data = [
            ("皇家同花顺", "100%"),
            ("同花顺", "10%"),
            ("四条", "$1,250"),
            ("葫芦", "$375"),
            ("同花", "$250")
        ]
        for col,h in enumerate(prog_headers):
            tk.Label(prog_frame, text=h, font=('微软雅黑',10,'bold'),
                     bg='#4B8BBE', fg='white', padx=10, pady=5,
                     anchor='center').grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r,row_data in enumerate(prog_data, start=1):
            bg = '#E0E0E0' if r%2==0 else '#F0F0F0'
            for c,txt in enumerate(row_data):
                tk.Label(prog_frame, text=txt, font=('微软雅黑',10),
                         bg=bg, padx=10, pady=5, anchor='center'
                         ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(prog_headers)):
            prog_frame.columnconfigure(c, weight=1)

        notes = """
        注：
        * 累进大奖奖池为未换牌前的扑克
        """
        tk.Label(content_frame, text=notes, font=('微软雅黑',10),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # ---------- 更新余额 ----------
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    # ---------- 辅助：获取牌型显示名称 ----------
    def get_hand_display_name(self, cards):
        rank, values = evaluate_five_card_hand(cards)
        if rank == 1:
            return "对子(J-A)"
        elif rank == 0:
            # 检查是否有一对（低对子）
            value_counts = Counter(c.value for c in cards)
            for v, cnt in value_counts.items():
                if cnt == 2 and v < 11:
                    return "对子(2-10)"
            return "高牌"
        else:
            return HAND_RANK_NAMES.get(rank, "高牌")

    # ---------- 切换保留 ----------
    def toggle_hold(self, idx):
        if self.game.stage != "dealt" or self.buttons_disabled:
            return
        self.game.hold_status[idx] = not self.game.hold_status[idx]
        if self.game.hold_status[idx]:
            self.hold_labels[idx].place(x=0, y=0)
        else:
            self.hold_labels[idx].place_forget()

    # ---------- 开始游戏 ----------
    def start_game(self):
        try:
            bet = int(self.bet_var.get())
            max_bet = 50000 if not self.high_bet_mode else 250000
            if bet < 5:
                messagebox.showerror("错误", "请下注主注")
                return
            if bet > max_bet:
                bet = max_bet
                self.bet_var.set(str(max_bet))
                messagebox.showwarning("下注限制", f"主注上限为{max_bet}，已自动调整")
            # 检查 Progressive 下注
            prog_active = (self.progressive_var.get() == 1)
            prog_cost = 2.5 if prog_active else 0
            total_required = bet + prog_cost
            if self.balance < total_required:
                messagebox.showerror("错误", "余额不足")
                return

            self.balance -= bet
            if prog_active:
                self.balance -= 2.5
                self.last_progressive_state = 1
            else:
                self.last_progressive_state = 0
            self.update_balance()

            self.last_bet = {'bet': bet, 'progressive': prog_active}
            if self.repeat_bet_btn:
                self.repeat_bet_btn.config(state=tk.NORMAL)

            self.game.reset_game()
            self.game.bet_amount = bet
            self.game.deal_initial()

            # 保存原始手牌（深拷贝）
            self.initial_hand = [Card(c.suit, c.rank) for c in self.game.player_hand]

            # 初始手牌缩略图暂时保持背面，等发牌动画结束后再更新
            for lbl in self.bottom_labels:
                lbl.config(image=self.back_image)
            for hold in self.hold_labels:
                hold.place_forget()

            self.add_draw_button()
            self.draw_button.config(state=tk.DISABLED)

            self.stage_label.config(text="发牌")
            self.status_label.config(text="发牌中...")
            self.game_in_progress = True

            self.bet_display.unbind("<Button-1>")
            self.bet_display.unbind("<Button-3>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            self.progressive_cb.config(state=tk.DISABLED)

            self.animation_queue = list(range(5))
            self.animate_deal()

        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    # ---------- 发牌动画 ----------
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return
        self.animation_in_progress = True
        idx = self.animation_queue.pop(0)
        card = self.game.player_hand[idx]
        self.bottom_labels[idx].config(image=self.card_images.get((card.suit, card.rank), self.back_image))
        self.after(200, self.animate_deal)

    def reveal_player_cards(self):
        self.update_hand_label()
        self.game.stage = "dealt"
        self.stage_label.config(text="选择保留牌")
        self.status_label.config(text="选择要保留的牌，然后点击抽牌")
        self.draw_button.config(state=tk.NORMAL)
        self.buttons_disabled = False

        # 首次开牌结束，更新“原始手牌”缩略图
        small_size = (100, 140)
        for i, card in enumerate(self.initial_hand):
            if (card.suit, card.rank) in self.original_images:
                orig = self.original_images[(card.suit, card.rank)]
                small = orig.resize(small_size, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(small)
                self.initial_thumbnails[i].config(image=photo)
                self.initial_thumbnails[i].image = photo
            else:
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                draw.text((10,10), f"{card.rank}{card.suit}", fill='white')
                photo = ImageTk.PhotoImage(img)
                self.initial_thumbnails[i].config(image=photo)
                self.initial_thumbnails[i].image = photo

    def update_hand_label(self):
        if self.game.player_hand:
            display_name = self.get_hand_display_name(self.game.player_hand)
            self.player_label.config(text=f"手牌 - {display_name}")
        else:
            self.player_label.config(text="手牌")

    # ---------- 抽牌（带逐张动画） ----------
    def draw_action(self):
        # ----- 修改点：禁用扑克牌点击 -----
        self.buttons_disabled = True
        # --------------------------------
        self.draw_button.config(state=tk.DISABLED)
        self.status_label.config(text="抽牌中...")
        self.stage_label.config(text="抽牌")

        for i in range(5):
            if not self.game.hold_status[i]:
                self.bottom_labels[i].config(image=self.grey_back)

        self.game.draw_cards()
        self.animation_queue = [i for i in range(5) if not self.game.hold_status[i]]
        if not self.animation_queue:
            self.after(500, self.show_showdown)
        else:
            self.animate_draw()

    def animate_draw(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.show_showdown)
            return
        self.animation_in_progress = True
        idx = self.animation_queue.pop(0)
        card = self.game.player_hand[idx]
        self.bottom_labels[idx].config(image=self.card_images.get((card.suit, card.rank), self.back_image))
        self.after(200, self.animate_draw)

    def update_progressive_pool(self):
        """每局结束后，根据下注金额增加奖池贡献"""
        bet = self.game.bet_amount          # 主注
        prog_active = (self.progressive_var.get() == 1)
        prog_bet = 2.5 if prog_active else 0
        total_bet = bet + prog_bet
        # 贡献 = 总下注的0.1% + 累进下注的95%
        contribution = total_bet * 0.001 + prog_bet * 0.95
        self.progressive_amount += contribution
        if self.progressive_amount < self.min_progressive:
            self.progressive_amount = self.min_progressive
        save_progressive(self.progressive_amount)
        self.progressive_amount_var.set(f"${self.progressive_amount:,.2f}")

    # ---------- 结算 ----------
    def show_showdown(self):
        display_name = self.get_hand_display_name(self.game.player_hand)
        self.player_label.config(text=f"手牌 - {display_name}")

        rank, _ = evaluate_five_card_hand(self.game.player_hand)
        winnings = self.calculate_winnings()
        # 累进大奖赢额（基于原始手牌）
        progressive_win = self.calculate_progressive_win() if self.progressive_var.get() == 1 else 0
        winnings += progressive_win

        self.last_win = winnings
        self.balance += winnings
        self.update_balance()

        payout = VIDEO_POKER_PAYOUT.get(rank, 0)

        # 保存历史（最终手牌）
        is_win = winnings > 0
        save_video_poker_history(
            deck=self.game.deck,
            ori_cards=self.initial_hand,
            aft_cards=self.game.player_hand,
            bet=self.game.bet_amount,
            win_amount=winnings,
            hand_rank=rank,
            hand_name=display_name,
            is_win=is_win
        )

        if winnings > 0:
            self.bet_display.config(bg='gold')
            self.bet_var.set(str(int(winnings - progressive_win)))
            message = f"本局是{display_name}，赔率为{payout}:1，你赢了${winnings}！"
            if progressive_win > 0:
                message = f" 累进大奖赢得${progressive_win:.2f}！"
                self.progressive_display.config(bg='gold')   # 累进大奖卡片变金色
        else:
            self.bet_display.config(bg='white')
            self.bet_var.set("0")
            message = f"送您好运气。"

        self.status_label.config(text=message)
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        self.current_bet_label.config(text=f"本局下注: ${self.game.bet_amount:.2f}")

        self.clear_btn_frame()
        self.btn_frame.pack_propagate(False)
        self.btn_frame.config(height=50)
        restart_btn = tk.Button(
            self.btn_frame, text="再来一局",
            command=lambda: self.reset_game(),
            font=('Arial',12,'bold'), bg='#2196F3', fg='white', width=10
        )
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        restart_btn.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        self.update_progressive_pool()

        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def calculate_winnings(self):
        rank, _ = evaluate_five_card_hand(self.game.player_hand)
        payout = VIDEO_POKER_PAYOUT.get(rank, 0)
        if payout > 0:
            return self.game.bet_amount + (self.game.bet_amount * payout)
        else:
            return 0

    # ---------- 累进大奖计算 ----------
    def calculate_progressive_win(self):
        """基于原始手牌（self.initial_hand）计算累进大奖赢额，并更新奖池"""
        if not self.initial_hand or len(self.initial_hand) != 5:
            return 0
        rank, _ = evaluate_five_card_hand(self.initial_hand)
        # 修改后的赔付映射（仅保留指定牌型）
        payout_map = {
            9: ('jackpot', 1.0),      # 皇家同花顺：奖池100%
            8: ('jackpot', 0.1),      # 同花顺：奖池10%
            7: ('fixed', 1250),       # 四条：$1250
            6: ('fixed', 375),        # 葫芦：$375
            5: ('fixed', 250)         # 同花：$250
        }
        if rank not in payout_map:
            return 0
        mode, value = payout_map[rank]
        if mode == 'jackpot':
            win_amount = self.progressive_amount * value
        else:
            win_amount = value

        if win_amount <= 0:
            return 0

        # 从奖池扣除
        self.progressive_amount -= win_amount
        if self.progressive_amount < self.min_progressive:
            self.progressive_amount = self.min_progressive
        save_progressive(self.progressive_amount)
        self.progressive_amount_var.set(f"${self.progressive_amount:,.2f}")

        # 显示中奖消息
        hand_name = HAND_RANK_NAMES.get(rank, "未知牌型")
        if mode == 'jackpot':
            msg = f"原始手牌{hand_name}！赢得奖池的{int(value*100)}%：${win_amount:,.2f}"
        else:
            msg = f"原始手牌{hand_name}！赢得${win_amount:,.2f}"
        messagebox.showinfo("累进大奖", msg)
        return win_amount

    # ---------- 显示牌序（右键） ----------
    def show_card_sequence(self, event):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示","没有牌序信息")
            return
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("730x750")
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        cut_pos = self.game.deck.start_pos
        tk.Label(win, text=f"本局切牌位置: {cut_pos+1}", font=('Arial',14,'bold'), bg='#f0f0f0').pack(pady=10)
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0,0), window=content_frame, anchor='nw')

        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        small_size = (60,90)
        small_images = {}
        for i, card in enumerate(self.game.deck.full_deck):
            key = (card.suit, card.rank)
            if key in self.original_images:
                orig = self.original_images[key]
                small = orig.resize(small_size, Image.Resampling.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small)
            else:
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                text = f"{card.rank}{card.suit}"
                tw, th = draw.textsize(text, font=font)
                draw.text(((small_size[0]-tw)//2, (small_size[1]-th)//2), text, fill="white", font=font)
                small_images[i] = ImageTk.PhotoImage(img)

        for row in range(6):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X)
            cards_in_row = 9 if row<5 else 7
            for col in range(cards_in_row):
                idx = row*9+col
                if idx>=52: break
                container = tk.Frame(row_frame, bg='#f0f0f0')
                container.grid(row=0, column=col, padx=5)
                is_cut = idx == self.game.deck.start_pos
                bg = 'light blue' if is_cut else '#f0f0f0'
                lbl = tk.Label(container, image=small_images[idx], bg=bg, borderwidth=1, relief="solid")
                lbl.image = small_images[idx]
                lbl.pack()
                pos = tk.Label(container, text=str(idx+1), bg=bg, font=('Arial',9))
                pos.pack()
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

    # ---------- 重置游戏 ----------
    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

        # 重置牌为背面
        for lbl in self.bottom_labels:
            lbl.config(image=self.back_image)
        for hold in self.hold_labels:
            hold.place_forget()
        # 清空初始手牌缩略图（恢复背面）
        for lbl in self.initial_thumbnails:
            lbl.config(image=self.back_image)
        self.initial_hand = []

        self._load_assets()  # 刷新牌面资源
        self.game.reset_game()
        self.stage_label.config(text="下注")
        self.player_label.config(text="手牌")
        self.bet_var.set("0")
        self.bet_display.config(bg='white')
        self.status_label.config(text="设置下注金额并开始游戏")
        self.game_in_progress = False

        # 恢复 Progressive 复选框状态（保留上次选择）
        self.progressive_var.set(self.last_progressive_state)
        self.progressive_cb.config(state=tk.NORMAL)
        # 重置累进大奖卡片背景色
        self.progressive_display.config(bg=PANEL_BG)

        # 重置点击禁用标志（下一局可点击）
        self.buttons_disabled = False

        self.bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet())
        self.bet_display.bind("<Button-3>", self.reset_bet)
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e,t=text: self.select_chip(t))

        self.add_main_buttons()
        if self.last_bet is not None:
            self.repeat_bet_btn.config(state=tk.NORMAL)

        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)

# ========================== 主入口 ==========================
def main(initial_balance=10000, username="Guest"):
    app = VideoPokerGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")