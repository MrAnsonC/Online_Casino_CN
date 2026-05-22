import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
from collections import Counter
from itertools import combinations
import math
import time
import secrets
import subprocess, sys

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '皇家同花顺', 8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花',
    4: '顺子', 3: '三条', 2: '两对', 1: '对子', 0: '高牌'
}

# 支付表（利润倍数）
BET_PAYOUT = {
    # 胜负平（动态赔率）
    "cowboy_win": 0.95,   # 基准值，实际动态调整
    "bull_win": 0.95,     # 基准值

    # 合并手牌（10张中出现）
    "combined_straight_or_flush": 1.5,   # 顺子/同花
    "combined_full_house": 5,          # 葫芦
    "combined_quads_or_straight_flush": 30,   # 四条/同花顺

    # 赢家牌型
    "high_card": 2.8,        # 高牌
    "pair": 0.6,             # 对子
    "two_pair": 9.5,              # 两对
    "three_of_a_kind": 20,        # 三条
    "straight": 120,               # 顺子
    "flush": 240,                  # 同花
    "full_house": 320,            # 葫芦
    "four_kind_or_straight_flush": 1700  # 四条/同花顺
}

def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

def format_money(amount):
    """格式化金额显示，使用逗号分隔"""
    if amount >= 0:
        return "${:,.2f}".format(amount)
    else:
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
        except Exception as e:
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

def evaluate_hand(cards):
    """评估5张牌的手牌等级（与德州扑克规则一致）"""
    values = sorted((c.value for c in cards), reverse=True)
    counts = Counter(values)
    suits = [c.suit for c in cards]

    unique_vals = sorted(set(values), reverse=True)
    if 14 in unique_vals:
        unique_vals.append(1)
    straight_vals = []
    seq = []
    for v in unique_vals:
        if not seq or seq[-1] - 1 == v:
            seq.append(v)
        else:
            seq = [v]
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
        for v in flush_vals:
            if not seq2 or seq2[-1] - 1 == v:
                seq2.append(v)
            else:
                seq2 = [v]
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
        top5 = sorted((c.value for c in flush_cards), reverse=True)[:5]
        return (5, top5)
    if straight_vals:
        return (4, straight_vals)
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, [three] + kickers)
    pairs = [v for v, cnt in counts_list if cnt == 2]
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
        ev = evaluate_hand(combo)
        if best_eval is None or ev > best_eval:
            best_eval = ev
            best_hand = combo
    return best_eval, best_hand

class TexasHoldemGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.cowboy_hole = []   # 牛仔手牌5张
        self.bull_hole = []     # 公牛手牌5张
        self.bets = {bet_type: 0 for bet_type in BET_PAYOUT}
        self.stage = "betting"
        # 第0张翻开，其余背面
        self.cards_revealed = {
            "cowboy": [True, False, False, False, False],
            "bull": [True, False, False, False, False],
        }
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence
        self.dynamic_payouts = BET_PAYOUT.copy()   # 动态赔率

    def deal_initial(self):
        """发牌：每人5张"""
        self.cowboy_hole = self.deck.deal(5)
        self.bull_hole = self.deck.deal(5)

    def evaluate_hands(self):
        """评估双方的最佳5张手牌（实际就是整手牌）"""
        cowboy_eval, cowboy_best = find_best_5(self.cowboy_hole)
        bull_eval, bull_best = find_best_5(self.bull_hole)
        return cowboy_eval, cowboy_best, bull_eval, bull_best

    def get_winner_hand_type(self, cowboy_eval, bull_eval):
        """确定赢家的牌型（返回字符串键）"""
        if cowboy_eval > bull_eval:
            winner_eval = cowboy_eval
        elif bull_eval > cowboy_eval:
            winner_eval = bull_eval
        else:
            return None, None  # 平手，无赢家牌型

        hand_rank = winner_eval[0]
        if hand_rank in [9, 8, 7]:      # 皇家同花顺、同花顺、四条
            return "four_kind_or_straight_flush", winner_eval
        elif hand_rank == 6:            # 葫芦
            return "full_house", winner_eval
        elif hand_rank == 5:            # 同花
            return "flush", winner_eval
        elif hand_rank == 4:            # 顺子
            return "straight", winner_eval
        elif hand_rank == 3:            # 三条
            return "three_of_a_kind", winner_eval
        elif hand_rank == 2:            # 两对
            return "two_pair", winner_eval
        elif hand_rank == 1:            # 对子
            return "pair", winner_eval
        elif hand_rank == 0:            # 高牌
            return "high_card", winner_eval
        else:
            return None, None

    def check_combined_hands(self):
        """检查合并手牌（10张）中是否存在顺子/同花、葫芦、四条/同花顺"""
        all_cards = self.cowboy_hole + self.bull_hole
        found_quads_or_straight_flush = False
        found_full_house = False
        found_straight_or_flush = False

        for combo in combinations(all_cards, 5):
            eval_result = evaluate_hand(combo)
            rank = eval_result[0]
            if rank in [7, 8, 9]:          # 四条(7) 或 同花顺(8,9)
                found_quads_or_straight_flush = True
            elif rank == 6:                 # 葫芦
                found_full_house = True
            elif rank in [4, 5, 8, 9]:
                found_straight_or_flush = True

        return {
            "combined_quads_or_straight_flush": found_quads_or_straight_flush,
            "combined_full_house": found_full_house,
            "combined_straight_or_flush": found_straight_or_flush
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
        else:  # 点数相同
            cowboy_odds = 0.95
            bull_odds = 0.95

        # 限制在合法范围内并保留两位小数
        cowboy_odds = round(max(0.45, min(1.45, cowboy_odds)), 2)
        bull_odds = round(max(0.45, min(1.45, bull_odds)), 2)

        self.dynamic_payouts["cowboy_win"] = cowboy_odds
        self.dynamic_payouts["bull_win"] = bull_odds

class TexasHoldemGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("梭哈双人对决")
        self.geometry("850x755+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')

        self.username = username
        self.balance = initial_balance
        self.game = TexasHoldemGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.last_win = 0
        self.auto_reset_timer = None
        self.auto_start_timer = None
        self.buttons_disabled = False
        self.win_details = {bet_type: 0 for bet_type in BET_PAYOUT}
        self.bet_widgets = {}
        self.bet_start_time = 0
        self.enter_enabled = True
        self.destroyed = False

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Return>", self.on_enter_key)

    def on_enter_key(self, event):
        if not self.enter_enabled or self.game.stage != "betting":
            return
        self.timer_label.config(text=f"下注时间: 0秒")
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
            self.auto_start_timer = None
        self.enter_enabled = False
        self.start_game()

    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("游戏规则")
        win.geometry("800x650")
        win.resizable(0,0)
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

        rules_text = """
        梭哈双人对决游戏规则

        1. 游戏参与者:
           - 牛仔 (Cowboy): 电脑玩家A
           - 公牛 (Bull): 电脑玩家B

        2. 游戏流程:
           a. 发牌阶段:
               - 系统自动发牌：每人5张
               - 双方的第一张牌会立即翻开作为明牌
           b. 下注阶段:
               - 玩家根据明牌在多个选项上下注（15秒倒计时）
               - 下注完成后按回车或等待时间到自动开始
           c. 结算阶段:
               - 翻开剩余牌，比较双方牌型
               - 根据下注选项结算输赢

        3. 下注选项及赔率:
           a. 胜负平:
               - 牛仔胜：赔率根据明牌点数差动态调整（0.45~1.45）
               - 公牛胜：赔率动态调整
           b. 合并手牌（双方10张牌中出现）:
               - 顺子/同花：1.5:1
               - 葫芦：5:1
               - 四条/同花顺：30:1
           c. 赢家牌型:
               # 赢家牌型
               - 高牌：2.8:1
               - 对子：0.6:1
               - 两对：9.5:1
               - 三条：20:1
               - 顺子：120:1
               - 同花：240:1
               - 葫芦：320:1
               - 四条/同花顺：1700:1
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

    def on_close(self):
        self.destroyed = True
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
            self.auto_start_timer = None
        self.destroy()
        self.quit()

    def _load_assets(self):
        card_size = (75, 105)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not hasattr(self, 'current_poker_folder'):
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
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
            # 处理带K的筹码，如1K或2.5K
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        bet_var = getattr(self, f"{bet_type}_var", None)
        if bet_var:
            current = float(bet_var.get())
            new_value = current + chip_value
            total_bet = self.get_total_bet() + chip_value
            if total_bet > 500000:
                messagebox.showwarning("下注上限", "本局下注总额不能超过500,000")
                return
            bet_var.set(str(int(new_value)))

    def get_total_bet(self):
        total = 0
        for bet_type in BET_PAYOUT:
            bet_var = getattr(self, f"{bet_type}_var", None)
            if bet_var:
                total += float(bet_var.get())
        return total

    def reset_bet_area(self, event, bet_type):
        bet_var = getattr(self, f"{bet_type}_var", None)
        if bet_var:
            bet_var.set("0")
            self.bet_widgets[bet_type].config(bg='white')

    def _create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 顶部信息栏
        info_frame = tk.Frame(main_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        self.balance_label = tk.Label(
            info_frame,
            text=f"余额: {format_money(self.balance)}",
            font=('Arial', 16),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=5)

        # 牌桌区域
        table_frame = tk.Frame(main_frame, bg='#35654d')
        table_frame.pack(fill=tk.BOTH, expand=True)

        # 牛仔区域
        cowboy_frame = tk.Frame(table_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        cowboy_frame.place(x=10, y=5, width=410, height=180)
        self.cowboy_label = tk.Label(cowboy_frame, text="牛仔", font=('Arial', 16), bg='#2a4a3c', fg='white')
        self.cowboy_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.cowboy_cards_frame = tk.Frame(cowboy_frame, bg='#2a4a3c')
        self.cowboy_cards_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 公牛区域
        bull_frame = tk.Frame(table_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bull_frame.place(x=415, y=5, width=410, height=180)
        self.bull_label = tk.Label(bull_frame, text="公牛", font=('Arial', 16), bg='#2a4a3c', fg='white')
        self.bull_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.bull_cards_frame = tk.Frame(bull_frame, bg='#2a4a3c')
        self.bull_cards_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ========== 下注区域（德州扑克风格布局）==========
        bet_frame = tk.Frame(main_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10, padx=10)

        # 第一行：胜负平（牛仔赢 / 公牛赢，缺少平手则第三格留空或隐藏）
        top_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        top_row_frame.pack(fill=tk.X, padx=10, pady=5)

        # 牛仔赢（动态赔率）
        self.cowboy_win_frame = tk.LabelFrame(
            top_row_frame, text="牛仔赢 (0.95:1)",
            font=('Arial', 20, 'bold'), bg='#2a4a3c', fg='white', width=150, height=80
        )
        self.cowboy_win_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.cowboy_win_var = tk.StringVar(value="0")
        cowboy_win_display = tk.Label(
            self.cowboy_win_frame, textvariable=self.cowboy_win_var,
            font=('Arial', 14), bg='white', fg='black', height=2
        )
        cowboy_win_display.pack(fill=tk.BOTH, expand=True)
        cowboy_win_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("cowboy_win"))
        cowboy_win_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "cowboy_win"))
        self.bet_widgets["cowboy_win"] = cowboy_win_display

        # 公牛赢（动态赔率）
        self.bull_win_frame = tk.LabelFrame(
            top_row_frame, text="公牛赢 (0.95:1)",
            font=('Arial', 20, 'bold'), bg='#2a4a3c', fg='white', width=150, height=80
        )
        self.bull_win_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.bull_win_var = tk.StringVar(value="0")
        bull_win_display = tk.Label(
            self.bull_win_frame, textvariable=self.bull_win_var,
            font=('Arial', 14), bg='white', fg='black', height=2
        )
        bull_win_display.pack(fill=tk.BOTH, expand=True)
        bull_win_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bull_win"))
        bull_win_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "bull_win"))
        self.bet_widgets["bull_win"] = bull_win_display

        # 第二行：左右分栏
        bottom_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        bottom_row_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 左侧：合并手牌（垂直排列，类似德州中的“任一人手牌”）
        left_frame = tk.LabelFrame(
            bottom_row_frame, text="双方合并牌型",
            font=('Arial', 20, 'bold'), bg='#2a4a3c', fg='white'
        )
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # 顺子/同花
        suited_frame = tk.LabelFrame(
            left_frame, text="顺子/同花 (1.5:1)",
            font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='white', height=60
        )
        suited_frame.pack(fill=tk.X, padx=10, pady=2)
        self.combined_straight_or_flush_var = tk.StringVar(value="0")
        suited_display = tk.Label(
            suited_frame, textvariable=self.combined_straight_or_flush_var,
            font=('Arial', 14), bg='white', fg='black', height=1
        )
        suited_display.pack(fill=tk.BOTH, expand=True)
        suited_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("combined_straight_or_flush"))
        suited_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "combined_straight_or_flush"))
        self.bet_widgets["combined_straight_or_flush"] = suited_display

        # 葫芦
        pair_frame = tk.LabelFrame(
            left_frame, text="葫芦 (5:1)",
            font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='white', height=60
        )
        pair_frame.pack(fill=tk.X, padx=5, pady=2)
        self.combined_full_house_var = tk.StringVar(value="0")
        pair_display = tk.Label(
            pair_frame, textvariable=self.combined_full_house_var,
            font=('Arial', 14), bg='white', fg='black', height=1
        )
        pair_display.pack(fill=tk.BOTH, expand=True)
        pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("combined_full_house"))
        pair_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "combined_full_house"))
        self.bet_widgets["combined_full_house"] = pair_display

        # 四条/同花顺
        ace_pair_frame = tk.LabelFrame(
            left_frame, text="四条/同花顺 (30:1)",
            font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='white', height=60
        )
        ace_pair_frame.pack(fill=tk.X, padx=5, pady=2)
        self.combined_quads_or_straight_flush_var = tk.StringVar(value="0")
        ace_pair_display = tk.Label(
            ace_pair_frame, textvariable=self.combined_quads_or_straight_flush_var,
            font=('Arial', 14), bg='white', fg='black', height=1
        )
        ace_pair_display.pack(fill=tk.BOTH, expand=True)
        ace_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("combined_quads_or_straight_flush"))
        ace_pair_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "combined_quads_or_straight_flush"))
        self.bet_widgets["combined_quads_or_straight_flush"] = ace_pair_display

        # 右侧：赢家牌型（布局与德州完全相同）
        right_frame = tk.LabelFrame(
            bottom_row_frame, text="赢家牌型",
            font=('Arial', 20, 'bold'), bg='#2a4a3c', fg='white'
        )
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # 第一行：高牌 / 对子
        win_row1 = tk.Frame(right_frame, bg='#2a4a3c')
        win_row1.pack(fill=tk.X, pady=2)
        win_row1.grid_columnconfigure(0, weight=1, uniform='winrow1')
        win_row1.grid_columnconfigure(1, weight=1, uniform='winrow1')

        # 高牌
        high_card_frame = tk.LabelFrame(
            win_row1, text="高牌 (2.8:1)",
            font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60
        )
        high_card_frame.grid(row=0, column=0, sticky='nsew', padx=2)
        self.high_card_var = tk.StringVar(value="0")
        high_card_display = tk.Label(
            high_card_frame, textvariable=self.high_card_var,
            font=('Arial', 10), bg='white', fg='black', height=1
        )
        high_card_display.pack(fill=tk.BOTH, expand=True)
        high_card_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("high_card"))
        high_card_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "high_card"))
        self.bet_widgets["high_card"] = high_card_display

        # 对子
        pair_win_frame = tk.LabelFrame(
            win_row1, text="对子 (0.6:1)",
            font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60
        )
        pair_win_frame.grid(row=0, column=1, sticky='nsew', padx=2)
        self.pair_var = tk.StringVar(value="0")
        pair_win_display = tk.Label(
            pair_win_frame, textvariable=self.pair_var,
            font=('Arial', 10), bg='white', fg='black', height=1
        )
        pair_win_display.pack(fill=tk.BOTH, expand=True)
        pair_win_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("pair"))
        pair_win_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "pair"))
        self.bet_widgets["pair"] = pair_win_display

        # 第二行：两对 / 三条
        win_row2 = tk.Frame(right_frame, bg='#2a4a3c')
        win_row2.pack(fill=tk.X, pady=2)
        win_row2.grid_columnconfigure(0, weight=1, uniform='winrow2')
        win_row2.grid_columnconfigure(1, weight=1, uniform='winrow2')

        # 两对
        two_pair_frame = tk.LabelFrame(
            win_row2, text="两对 (9.5:1)",
            font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60
        )
        two_pair_frame.grid(row=0, column=0, sticky='nsew', padx=2)
        self.two_pair_var = tk.StringVar(value="0")
        two_pair_display = tk.Label(
            two_pair_frame, textvariable=self.two_pair_var,
            font=('Arial', 10), bg='white', fg='black', height=1
        )
        two_pair_display.pack(fill=tk.BOTH, expand=True)
        two_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("two_pair"))
        two_pair_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "two_pair"))
        self.bet_widgets["two_pair"] = two_pair_display

        # 三条
        three_kind_frame = tk.LabelFrame(
            win_row2, text="三条 (20:1)",
            font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60
        )
        three_kind_frame.grid(row=0, column=1, sticky='nsew', padx=2)
        self.three_of_a_kind_var = tk.StringVar(value="0")
        three_kind_display = tk.Label(
            three_kind_frame, textvariable=self.three_of_a_kind_var,
            font=('Arial', 10), bg='white', fg='black', height=1
        )
        three_kind_display.pack(fill=tk.BOTH, expand=True)
        three_kind_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("three_of_a_kind"))
        three_kind_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "three_of_a_kind"))
        self.bet_widgets["three_of_a_kind"] = three_kind_display

        # 第三行：顺子 / 同花
        win_row3 = tk.Frame(right_frame, bg='#2a4a3c')
        win_row3.pack(fill=tk.X, pady=2)
        win_row3.grid_columnconfigure(0, weight=1, uniform='winrow3')
        win_row3.grid_columnconfigure(1, weight=1, uniform='winrow3')

        # 顺子
        straight_frame = tk.LabelFrame(
            win_row3, text="顺子 (120:1)",
            font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60
        )
        straight_frame.grid(row=0, column=0, sticky='nsew', padx=2)
        self.straight_var = tk.StringVar(value="0")
        straight_display = tk.Label(
            straight_frame, textvariable=self.straight_var,
            font=('Arial', 10), bg='white', fg='black', height=1
        )
        straight_display.pack(fill=tk.BOTH, expand=True)
        straight_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("straight"))
        straight_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "straight"))
        self.bet_widgets["straight"] = straight_display

        # 同花
        flush_frame = tk.LabelFrame(
            win_row3, text="同花 (240:1)",
            font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60
        )
        flush_frame.grid(row=0, column=1, sticky='nsew', padx=2)
        self.flush_var = tk.StringVar(value="0")
        flush_display = tk.Label(
            flush_frame, textvariable=self.flush_var,
            font=('Arial', 10), bg='white', fg='black', height=1
        )
        flush_display.pack(fill=tk.BOTH, expand=True)
        flush_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("flush"))
        flush_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "flush"))
        self.bet_widgets["flush"] = flush_display

        # 第四行：葫芦 / 四条/同花顺
        win_row4 = tk.Frame(right_frame, bg='#2a4a3c')
        win_row4.pack(fill=tk.X, pady=2)
        win_row4.grid_columnconfigure(0, weight=1, uniform='winrow4')
        win_row4.grid_columnconfigure(1, weight=1, uniform='winrow4')

        # 葫芦（赢家牌型）
        full_house_win_frame = tk.LabelFrame(
            win_row4, text="葫芦 (320:1)",
            font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60
        )
        full_house_win_frame.grid(row=0, column=0, sticky='nsew', padx=2)
        self.full_house_var = tk.StringVar(value="0")
        full_house_win_display = tk.Label(
            full_house_win_frame, textvariable=self.full_house_var,
            font=('Arial', 10), bg='white', fg='black', height=1
        )
        full_house_win_display.pack(fill=tk.BOTH, expand=True)
        full_house_win_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("full_house"))
        full_house_win_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "full_house"))
        self.bet_widgets["full_house"] = full_house_win_display

        # 四条/同花顺（赢家牌型）
        four_kind_frame = tk.LabelFrame(
            win_row4, text="四条/同花顺 (1700:1)",
            font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60
        )
        four_kind_frame.grid(row=0, column=1, sticky='nsew', padx=2)
        self.four_kind_or_straight_flush_var = tk.StringVar(value="0")
        four_kind_display = tk.Label(
            four_kind_frame, textvariable=self.four_kind_or_straight_flush_var,
            font=('Arial', 10), bg='white', fg='black', height=1
        )
        four_kind_display.pack(fill=tk.BOTH, expand=True)
        four_kind_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("four_kind_or_straight_flush"))
        four_kind_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "four_kind_or_straight_flush"))
        self.bet_widgets["four_kind_or_straight_flush"] = four_kind_display

        # ========== 底部操作区域（筹码、信息、按钮）==========
        bottom_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        bottom_frame.pack(fill=tk.X, pady=10, padx=10)

        # 筹码区域
        chips_frame = tk.Frame(bottom_frame, bg='#2a4a3c')
        chips_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=(10, 5), pady=5, side=tk.LEFT)
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(side=tk.LEFT, fill=tk.X, pady=5)
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
            chip_canvas = tk.Canvas(chip_row, width=55, height=55, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 53, 53, fill=bg_color, outline='black')
            chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip("$100")

        # 信息显示区域
        info_frame = tk.Frame(bottom_frame, bg='#2a4a3c')
        info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.current_bet_label = tk.Label(
            info_frame, text="本局下注: $0",
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(side=tk.TOP, anchor='e', padx=10, pady=3)
        self.last_win_label = tk.Label(
            info_frame, text="上局获胜: $0",
            font=('Arial', 14), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(side=tk.TOP, anchor='e', padx=10, pady=3)
        self.timer_label = tk.Label(
            info_frame, text="下注时间: 15秒",
            font=('Arial', 14, 'bold'), bg='#2a4a3c', fg='#FF0000'
        )
        self.timer_label.pack(side=tk.TOP, anchor='e', padx=10, pady=3)

        # 操作按钮区域
        self.action_frame = tk.Frame(bottom_frame, bg='#2a4a3c')
        self.action_frame.pack(side=tk.RIGHT, fill=tk.X, padx=10)
        button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        button_frame.pack(pady=5)

        self.info_button = tk.Button(
            bottom_frame,
            text="游戏规则",
            command=self.show_game_instructions,
            bg='#4B8BBE',
            fg='white',
            font=('Arial', 12),
            width=10,
            relief=tk.RAISED
        )
        self.info_button.pack(side=tk.RIGHT, padx=10, pady=5)

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
        self.balance_label.config(text=f"余额: {format_money(self.balance)}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    def reset_game(self):
        """重置游戏：发牌、显示明牌、更新赔率显示、启动倒计时"""
        if self.destroyed:
            return

        self._load_assets()
        self.game.reset_game()
        self.game.deal_initial()

        # 计算动态赔率（基于明牌点数）
        cowboy_up = self.game.cowboy_hole[0].value
        bull_up = self.game.bull_hole[0].value
        self.game.calculate_dynamic_payouts(cowboy_up, bull_up)

        # 更新牛仔赢/公牛赢的标题
        self.cowboy_win_frame.config(text=f"牛仔赢 ({self.game.dynamic_payouts['cowboy_win']:.2f}:1)")
        self.bull_win_frame.config(text=f"公牛赢 ({self.game.dynamic_payouts['bull_win']:.2f}:1)")

        # 重置下注金额为0
        self.reset_bets()

        # 清空活动卡片列表和现有卡片
        self.active_card_labels = []
        for widget in self.cowboy_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.bull_cards_frame.winfo_children():
            widget.destroy()

        # 重置牌型标签（只显示名字）
        self.cowboy_label.config(text="牛仔")
        self.bull_label.config(text="公牛")

        # 创建卡片标签，y坐标增加20px确保完全显示
        for i, card in enumerate(self.game.cowboy_hole):
            is_up = self.game.cards_revealed["cowboy"][i]
            img = self.card_images.get((card.suit, card.rank)) if is_up else self.back_image
            card_label = tk.Label(self.cowboy_cards_frame, image=img, bg='#2a4a3c')
            card_label.place(x=i*77.5, y=2)
            card_label.card = card
            card_label.is_face_up = is_up
            card_label.bind("<Button-3>", self.show_card_sequence)
            self.active_card_labels.append(card_label)

        for i, card in enumerate(self.game.bull_hole):
            is_up = self.game.cards_revealed["bull"][i]
            img = self.card_images.get((card.suit, card.rank)) if is_up else self.back_image
            card_label = tk.Label(self.bull_cards_frame, image=img, bg='#2a4a3c')
            card_label.place(x=i*77.5, y=2)
            card_label.card = card
            card_label.is_face_up = is_up
            card_label.bind("<Button-3>", self.show_card_sequence)
            self.active_card_labels.append(card_label)

        # 恢复下注区域绑定
        for bet_type, widget in self.bet_widgets.items():
            widget.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            widget.bind("<Button-3>", lambda e, bt=bet_type: self.reset_bet_area(e, bt))
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))

        # 启动15秒自动开始计时器
        self.bet_start_time = time.time()
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
        self.auto_start_timer = self.after(1000, self.update_timer)
        self.enter_enabled = True
        self.game.stage = "betting"

    def start_game(self):
        """开始结算：扣除下注、翻开剩余牌、结算"""
        if self.destroyed:
            return

        self.enter_enabled = False

        # 收集所有下注金额
        bet_amounts = {
            "cowboy_win": float(self.cowboy_win_var.get()),
            "bull_win": float(self.bull_win_var.get()),
            "combined_straight_or_flush": float(self.combined_straight_or_flush_var.get()),
            "combined_full_house": float(self.combined_full_house_var.get()),
            "combined_quads_or_straight_flush": float(self.combined_quads_or_straight_flush_var.get()), 
            "high_card": float(self.high_card_var.get()),
            "pair": float(self.pair_var.get()),
            "two_pair": float(self.two_pair_var.get()),
            "three_of_a_kind": float(self.three_of_a_kind_var.get()),
            "straight": float(self.straight_var.get()),
            "flush": float(self.flush_var.get()),
            "full_house": float(self.full_house_var.get()),
            "four_kind_or_straight_flush": float(self.four_kind_or_straight_flush_var.get())
        }

        total_bet = sum(bet_amounts.values())
        if total_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            # 清空所有下注
            for bet_type in bet_amounts:
                bet_amounts[bet_type] = 0
            for bet_type, widget in self.bet_widgets.items():
                getattr(self, f"{bet_type}_var").set("0")
                widget.config(bg='white')
            self.current_bet_label.config(text=f"本局下注: {format_money(0)}")
            # 重新启动倒计时
            self.bet_start_time = time.time()
            if self.auto_start_timer:
                self.after_cancel(self.auto_start_timer)
            self.auto_start_timer = self.after(1000, self.update_timer)
            self.enter_enabled = True
            return

        self.balance -= total_bet
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: {format_money(total_bet)}")
        self.game.bets = bet_amounts

        # 取消自动开始计时器
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
            self.auto_start_timer = None

        # 禁用下注区域
        for widget in self.bet_widgets.values():
            widget.unbind("<Button-1>")
        for chip in self.chip_buttons:
            chip.unbind("<Button-1>")

        # 翻开剩余牌（第1~4张）
        self.reveal_remaining_cards()

    def reveal_remaining_cards(self):
        """翻开第1~4张牌（带动画）"""
        flip_list = []
        for i, card_label in enumerate(self.cowboy_cards_frame.winfo_children()):
            if not card_label.is_face_up:
                flip_list.append(card_label)
                self.game.cards_revealed["cowboy"][i] = True
        for i, card_label in enumerate(self.bull_cards_frame.winfo_children()):
            if not card_label.is_face_up:
                flip_list.append(card_label)
                self.game.cards_revealed["bull"][i] = True

        if flip_list:
            # 简单翻转（不使用动画，直接替换图片）
            for card_label in flip_list:
                card = card_label.card
                front_img = self.card_images.get((card.suit, card.rank), self.back_image)
                card_label.config(image=front_img)
                card_label.is_face_up = True

        # 更新牌型标签（此时全部翻开）
        self.update_hand_labels()

        # 等待1秒后开始排序动画
        self.after(1000, self.start_sort_animation)

    def start_sort_animation(self):
        """开始排序动画，持续1.5秒后结算"""
        if self.destroyed:
            return

        # 获取双方手牌评估结果
        cowboy_eval, _, _, _ = self.game.evaluate_hands()
        bull_eval, _, _, _ = self.game.evaluate_hands()

        # 对每方的手牌按规则排序
        sorted_cowboy = self.sort_hand_for_display(self.game.cowboy_hole, cowboy_eval)
        sorted_bull = self.sort_hand_for_display(self.game.bull_hole, bull_eval)

        # 获取所有卡片标签（按当前显示顺序）
        cowboy_labels = self.cowboy_cards_frame.winfo_children()
        bull_labels = self.bull_cards_frame.winfo_children()

        # 记录每张卡的起始位置（x坐标）
        start_positions = {}
        for label in cowboy_labels + bull_labels:
            info = label.place_info()
            start_positions[label] = float(info['x'])

        # 目标位置：根据排序后的顺序，每张卡应放置的x坐标
        # 注意：排序后的列表中的卡可能与原标签对应，但卡片本身不变，只是重新排列顺序
        target_positions = {}
        # 牛仔卡目标位置
        for idx, card in enumerate(sorted_cowboy):
            # 找到对应的标签（根据card对象）
            for label in cowboy_labels:
                if label.card == card:
                    target_positions[label] = idx * 77.5
                    break
        # 公牛卡目标位置
        for idx, card in enumerate(sorted_bull):
            for label in bull_labels:
                if label.card == card:
                    target_positions[label] = idx * 77.5
                    break

        # 动画参数
        duration = 1500  # 1.5秒
        steps = 30       # 步数
        interval = duration // steps

        # 记录每张卡的起始和目标
        anim_data = []
        for label in start_positions:
            start_x = start_positions[label]
            target_x = target_positions[label]
            dx = (target_x - start_x) / steps
            anim_data.append((label, start_x, dx))

        def animate_step(step):
            if step > steps or self.destroyed:
                # 动画结束，确保所有卡到达目标位置，然后结算
                for label, _, _ in anim_data:
                    target_x = target_positions[label]
                    label.place(x=target_x)
                self.settle_game()
                return
            for label, start_x, dx in anim_data:
                new_x = start_x + dx * step
                label.place(x=new_x)
            self.after(interval, lambda: animate_step(step + 1))

        # 开始动画
        animate_step(1)

    def sort_hand_for_display(self, hand, hand_eval):
        """
        根据牌型对手牌进行排序，返回排序后的牌列表（用于显示）。
        - 对于顺子（rank 4）、同花顺/皇家同花顺（rank 8/9）：
        按“从小到大”排序，A-2-3-4-5 的顺序为 A,2,3,4,5；10-J-Q-K-A 的顺序为 10,J,Q,K,A。
        - 对于其它牌型：按出现次数降序（比如三条优先），出现次数相同则按点数降序。
        参数：
        hand: 列表，包含 5 个 Card 对象
        hand_eval: evaluate_hand 返回的元组 (rank, values)
        返回：
        排好序的 Card 对象列表（长度与输入 hand 相同）
        """
        # 防御性检查
        if not hand or not hand_eval:
            return list(hand)

        rank = hand_eval[0]

        # 处理顺子类型：顺子(4)、同花顺(8)、皇家同花顺(9)
        if rank in (4, 8, 9):
            # hand_eval[1] 是 evaluate_hand 返回的“顺子值序列”（evaluate_hand 内部返回的是从高到低的序列，
            # 并且对于 A-2-3-4-5，会把 A 当作 1 放在序列里）
            straight_vals = list(hand_eval[1]) if len(hand_eval) > 1 else []

            # 如果 evaluate_hand 把 A 当作 1（即存在 1），说明这是 A-2-3-4-5 低顺
            if 1 in straight_vals:
                # 我们需要的显示顺序是 A,2,3,4,5 —— 对应数值为 14,2,3,4,5（Card.value 中 A = 14）
                display_order_values = [14, 2, 3, 4, 5]
            else:
                # 否则按照数值升序显示（例如 [10,11,12,13,14] -> 10,J,Q,K,A）
                # 注意 straight_vals 可能是从高到低，先排序再去重以防意外
                display_order_values = sorted(set(straight_vals))

            # 按 display_order_values 顺序从 hand 中取出对应卡片（考虑不同花色的情况）
            hand_copy = list(hand)  # 可变复制
            ordered = []
            for v in display_order_values:
                # 找到第一个 value 等于 v 的卡（并移除以避免重复匹配）
                for c in hand_copy:
                    if c.value == v:
                        ordered.append(c)
                        hand_copy.remove(c)
                        break
            # 如果还有剩余卡（理论上不应有），把它们追加到尾部（以保持长度）
            if hand_copy:
                ordered.extend(hand_copy)
            return ordered

        # 非顺子：按出现次数降序，次数相同按点数降序
        counts = Counter(c.value for c in hand)
        sorted_hand = sorted(hand, key=lambda c: (counts[c.value], c.value), reverse=True)
        return sorted_hand

    def update_hand_labels(self):
        """更新牛仔和公牛的牌型标签（全部翻开后调用）"""
        cowboy_eval, _, bull_eval, _ = self.game.evaluate_hands()  # 一次调用获取双方评估
        cowboy_hand_name = HAND_RANK_NAMES[cowboy_eval[0]] if cowboy_eval else ""
        self.cowboy_label.config(text=f"牛仔 - {cowboy_hand_name}" if cowboy_hand_name else "牛仔")
        bull_hand_name = HAND_RANK_NAMES[bull_eval[0]] if bull_eval else ""
        self.bull_label.config(text=f"公牛 - {bull_hand_name}" if bull_hand_name else "公牛")

    def settle_game(self):
        if self.destroyed:
            return

        # 评估手牌
        cowboy_eval, cowboy_best, bull_eval, bull_best = self.game.evaluate_hands()

        # 确定赢家
        winner = None
        if cowboy_eval > bull_eval:
            winner = "cowboy"
        elif bull_eval > cowboy_eval:
            winner = "bull"
        else:
            # 相同牌型比较具体牌值
            for i in range(len(cowboy_eval[1])):
                if cowboy_eval[1][i] > bull_eval[1][i]:
                    winner = "cowboy"
                    break
                elif bull_eval[1][i] > cowboy_eval[1][i]:
                    winner = "bull"
                    break
            else:
                winner = "tie"  # 完全平局（概率极低）

        # 检查合并手牌
        combined_results = self.game.check_combined_hands()

        # 确定赢家牌型
        winner_hand_type, winner_hand = self.game.get_winner_hand_type(cowboy_eval, bull_eval)

        # 计算赢利
        winnings = 0
        self.win_details = {bet_type: 0 for bet_type in BET_PAYOUT}

        # 胜负平下注结算（使用动态赔率）
        if winner == "cowboy":
            payout = self.game.dynamic_payouts["cowboy_win"]
            winnings += self.game.bets["cowboy_win"] * (1 + payout)
            self.win_details["cowboy_win"] = self.game.bets["cowboy_win"] * (1 + payout)
        elif winner == "bull":
            payout = self.game.dynamic_payouts["bull_win"]
            winnings += self.game.bets["bull_win"] * (1 + payout)
            self.win_details["bull_win"] = self.game.bets["bull_win"] * (1 + payout)
        elif winner == "tie":
            # 平手退本金（赔率0）
            winnings += self.game.bets["cowboy_win"]  # 退牛仔赢的本金
            winnings += self.game.bets["bull_win"]    # 退公牛赢的本金
            self.win_details["cowboy_win"] = self.game.bets["cowboy_win"]
            self.win_details["bull_win"] = self.game.bets["bull_win"]

        # 合并手牌下注结算
        for bet_type in ["combined_straight_or_flush", "combined_full_house", "combined_quads_or_straight_flush"]:
            if combined_results[bet_type]:
                payout = BET_PAYOUT[bet_type]
                winnings += self.game.bets[bet_type] * (1 + payout)
                self.win_details[bet_type] = self.game.bets[bet_type] * (1 + payout)

        # 赢家牌型下注结算
        if winner_hand_type and winner_hand_type != "tie":
            payout = BET_PAYOUT[winner_hand_type]
            winnings += self.game.bets[winner_hand_type] * (1 + payout)
            self.win_details[winner_hand_type] = self.game.bets[winner_hand_type] * (1 + payout)

        # 更新余额
        self.balance += winnings
        self.update_balance()
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: {format_money(winnings)}")

        # 高亮获胜的下注选项并显示赔付金额
        hit_bets = {
            "cowboy_win": winner == "cowboy",
            "bull_win": winner == "bull",
            "combined_straight_or_flush": combined_results["combined_straight_or_flush"],
            "combined_full_house": combined_results["combined_full_house"],
            "combined_quads_or_straight_flush": combined_results["combined_quads_or_straight_flush"],
            "high_card": winner_hand_type == "high_card",
            "pair": winner_hand_type == "pair",
            "two_pair": winner_hand_type == "two_pair",
            "three_of_a_kind": winner_hand_type == "three_of_a_kind",
            "straight": winner_hand_type == "straight",
            "flush": winner_hand_type == "flush",
            "full_house": winner_hand_type == "full_house",
            "four_kind_or_straight_flush": winner_hand_type == "four_kind_or_straight_flush"
        }

        for bet_type, widget in self.bet_widgets.items():
            if hit_bets.get(bet_type, False):
                payout_amount = self.win_details.get(bet_type, 0)
                if payout_amount.is_integer():
                    text = f"{payout_amount:.0f}"
                else:
                    text = f"{payout_amount:.1f}"
                getattr(self, f"{bet_type}_var").set(text)
                widget.config(bg='gold')
            else:
                getattr(self, f"{bet_type}_var").set("0")
                widget.config(bg='white')

        # 5秒后收起卡片并重置
        self.after(5000, self.collect_cards)

    def collect_cards(self):
        if self.destroyed:
            return
        # 简单销毁所有卡片并重置
        self.auto_next_game()

    def auto_next_game(self):
        if self.destroyed:
            return
        # 重置下注区域背景色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        # 重置游戏
        self.reset_game()

    def update_timer(self):
        if self.destroyed:
            return
        elapsed = time.time() - self.bet_start_time
        remaining = max(0, 15 - int(elapsed))
        self.timer_label.config(text=f"下注时间: {remaining}秒")
        if remaining > 0:
            self.auto_start_timer = self.after(1000, self.update_timer)
        else:
            self.enter_enabled = False
            self.start_game()

    def reset_bets(self):
        """重置所有下注金额为0"""
        self.cowboy_win_var.set("0")
        self.bull_win_var.set("0")
        self.combined_straight_or_flush_var.set("0")
        self.combined_full_house_var.set("0")
        self.combined_quads_or_straight_flush_var.set("0")
        self.high_card_var.set("0")
        self.pair_var.set("0")
        self.two_pair_var.set("0")
        self.three_of_a_kind_var.set("0")
        self.straight_var.set("0")
        self.flush_var.set("0")
        self.full_house_var.set("0")
        self.four_kind_or_straight_flush_var.set("0")
        self.current_bet_label.config(text=f"本局下注: {format_money(0)}")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')

    def show_card_sequence(self, event):
        """显示本局牌序窗口"""
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
            self.auto_start_timer = None
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示", "没有牌序信息")
            return
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600")
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        cut_pos = self.game.deck.start_pos
        cut_label = tk.Label(
            win,
            text=f"本局切牌位置: {cut_pos + 1}",
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0'
        )
        cut_label.pack(pady=(10, 5))
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas.create_window((0, 0), window=content_frame, anchor='nw')
        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        small_size = (60, 90)
        small_images = {}
        from PIL import ImageFont, ImageDraw
        for i, card in enumerate(self.game.deck.full_deck):
            key = (card.suit, card.rank)
            if key in self.original_images:
                orig_img = self.original_images[key]
                small_img = orig_img.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small_img)
            else:
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                text = f"{card.rank}{card.suit}"
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                text_width, text_height = draw.textsize(text, font=font)
                x = (small_size[0] - text_width) / 2
                y = (small_size[1] - text_height) / 2
                draw.text((x, y), text, fill="white", font=font)
                small_images[i] = ImageTk.PhotoImage(img)
        for row in range(7):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)
            cards_in_row = 8 if row < 6 else 4
            for col in range(cards_in_row):
                card_index = row * 8 + col
                if card_index >= 52:
                    break
                card_container = tk.Frame(row_frame, bg='#f0f0f0')
                card_container.grid(row=0, column=col, padx=5, pady=5)
                is_cut_position = card_index == self.game.deck.start_pos
                bg_color = 'light blue' if is_cut_position else '#f0f0f0'
                card = self.game.deck.full_deck[card_index]
                card_label = tk.Label(
                    card_container,
                    image=small_images[card_index],
                    bg=bg_color,
                    borderwidth=1,
                    relief="solid"
                )
                card_label.image = small_images[card_index]
                card_label.pack()
                pos_label = tk.Label(
                    card_container,
                    text=str(card_index+1),
                    bg=bg_color,
                    font=('Arial', 9)
                )
                pos_label.pack()
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

def main(initial_balance=10000, username="Guest"):
    app = TexasHoldemGUI(initial_balance, username)
    app.reset_game()
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"最终余额: {final_balance}")