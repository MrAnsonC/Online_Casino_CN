import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
from collections import Counter
from itertools import combinations
import math
import secrets
import subprocess, sys

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    10: '皇家同花顺', 9: '同花顺', 8: '四条', 7: '葫芦', 6: '同花',
    5: '顺子', 4: '三条', 3: '两对', 2: 'Jacks或更好对子', 1: '对子6-10', 0: '高牌'
}

# 主注赔率表（Ante + 3rd/4th/5th 总和）
MAIN_BET_PAYOUT = {
    10: 500,   # 皇家同花顺 500:1
    9: 100,    # 同花顺 100:1
    8: 40,     # 四条 40:1
    7: 10,     # 葫芦 10:1
    6: 6,      # 同花 6:1
    5: 4,      # 顺子 4:1
    4: 3,      # 三条 3:1
    3: 2,      # 两对 2:1
    2: 1,      # Jacks或更好对子 1:1
    1: 0       # 对子6-10 Push（返还本金）
}

# 3 Card Bonus 边注赔率表（基于3张公共牌）
BONUS3_PAYOUT = {
    40: 40,    # 同花顺 40:1
    30: 30,    # 三条 30:1
    6: 6,      # 顺子 6:1
    3: 3,      # 同花 3:1
    1: 1       # 对子 1:1
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
                return (10, seq2[:5]) if seq2[0] == 14 else (9, seq2[:5])

    counts_list = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if counts_list[0][1] == 4:
        quad = counts_list[0][0]
        kicker = max(v for v in values if v != quad)
        return (8, [quad, kicker])
    # ✅ Fix: check len(counts_list) > 1 before accessing index 1
    if len(counts_list) > 1 and counts_list[0][1] == 3 and counts_list[1][1] >= 2:
        return (7, [counts_list[0][0], counts_list[1][0]])
    if flush_suit:
        top5 = sorted((c.value for c in flush_cards), reverse=True)[:5]
        return (6, top5)
    if straight_vals:
        return (5, straight_vals)
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (4, [three] + kickers)
    pairs = [v for v, cnt in counts_list if cnt == 2]
    if len(pairs) >= 2:
        high, low = pairs[0], pairs[1]
        kicker = max(v for v in values if v not in (high, low))
        return (3, [high, low, kicker])
    if counts_list[0][1] == 2:
        pair = counts_list[0][0]
        kickers = [v for v in values if v != pair][:3]
        if pair >= 11:
            return (2, [pair] + kickers)
        elif pair >= 6:
            return (1, [pair] + kickers)
        else:
            return (0, values[:5])
    return (0, values[:5])

def evaluate_3card_hand(cards):
    """评估3张牌的牌型，返回数值等级：40同花顺，30三条，6顺子，3同花，1对子，0高牌"""
    if len(cards) != 3:
        return 0
    values = [c.value for c in cards]
    suits = [c.suit for c in cards]
    flush = len(set(suits)) == 1
    # 顺子检查（包括A23）
    values.sort()
    if values == [2,3,14]:
        straight = True
    elif values[0]+1 == values[1] and values[1]+1 == values[2]:
        straight = True
    else:
        straight = False
    three = values[0]==values[1]==values[2]
    pair = values[0]==values[1] or values[1]==values[2] or values[0]==values[2]
    if three:
        return 30
    elif flush and straight:
        return 40
    elif straight:
        return 6
    elif flush:
        return 3
    elif pair:
        return 1
    else:
        return 0

def find_best_5(cards):
    best_eval = None
    best_hand = None
    for combo in combinations(cards, 5):
        ev = evaluate_hand(combo)
        if best_eval is None or ev > best_eval:
            best_eval = ev
            best_hand = combo
    return best_eval, best_hand

class MississippiStudGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.ante = 0
        self.bonus3 = 0
        self.street3 = 0
        self.street4 = 0
        self.street5 = 0
        self.stage = "pre_flop"  # pre_flop, street3, street4, street5, showdown
        self.folded = False
        self.cards_revealed = {
            "player": [False, False],      # 2张玩家牌
            "community": [False, False, False]  # 3张公共牌
        }
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence

    def deal_initial(self):
        """发初始牌：玩家2张，公共牌3张"""
        self.player_hole = self.deck.deal(2)
        self.community_cards = self.deck.deal(3)

    def evaluate_final_hand(self):
        """评估最终5张牌（玩家2张+公共3张）的牌型等级"""
        cards = self.player_hole + self.community_cards
        return evaluate_hand(cards)[0]

    def evaluate_community_3(self):
        """评估3张公共牌的牌型等级（用于3 Card Bonus）"""
        return evaluate_3card_hand(self.community_cards)

class MississippiStudGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("密⻄⻄⽐梭哈撲克")
        self.geometry("1020x700+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')

        # 下注上限设置
        self.MAIN_BET_MAX = 10000   # Ante 及每轮下注上限
        self.BONUS3_BET_MAX = 2500  # 3 Card Bonus 上限

        self.username = username
        self.balance = initial_balance
        self.game = MississippiStudGame()
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
        self.win_details = {
            "ante": 0,
            "street3": 0,
            "street4": 0,
            "street5": 0,
            "bonus3": 0
        }
        self.bet_widgets = {}

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def disable_all_buttons_in_frame(self, frame):
        """递归禁用框架内所有按钮"""
        for child in frame.winfo_children():
            if isinstance(child, tk.Button):
                child.config(state=tk.DISABLED)
            else:
                self.disable_all_buttons_in_frame(child)

    def show_game_instructions(self):
        """显示游戏规则说明"""
        win = tk.Toplevel(self)
        win.title("游戏规则")
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

        title_label = tk.Label(
            content_frame,
            text="密⻄⻄⽐梭哈撲克 游戏规则",
            font=('微软雅黑', 16, 'bold'),
            bg='#F0F0F0',
            fg='#2a4a3c'
        )
        title_label.pack(pady=(0, 15))

        rules_text = """
        密⻄⻄⽐梭哈撲克是一种使用标准扑克牌的赌场游戏。玩家先下「Ante进场注」，
        并可以选择下「3 Card Bonus」。

        游戏流程:
          1. 玩家下Ante注，可选择3 Card Bonus
          2. 发牌：玩家获得2张底牌，桌上有3张公共牌（面朝下）
          3. 查看底牌后，玩家可以选择Fold弃牌，或下「3rd Street三牌注」
             (金额为Ante的1到3倍)
          4. 翻开第一张公共牌
          5. 玩家可以选择Fold弃牌，或下「4th Street四牌注」
             (金额为Ante的1到3倍)
          6. 翻开第二张公共牌
          7. 玩家可以选择Fold弃牌，或下「5th Street五牌注」
             (金额为Ante的1到3倍)
          8. 翻开第三张公共牌
          9. 结算：Ante + 3rd + 4th + 5th 总和根据牌型支付，3 Card Bonus
             根据三张公共牌支付

        牌型排名（从高到低）:
          皇家同花顺 > 同花顺 > 四条 > 葫芦 > 同花 > 顺子 > 三条 > 两对 >
          Jacks或更好对子 > 对子6-10 > 高牌
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

        tk.Label(
            content_frame,
            text="赔率表",
            font=('微软雅黑', 14, 'bold'),
            bg='#F0F0F0',
            fg='#2a4a3c'
        ).pack(fill=tk.X, padx=10, pady=(20, 10), anchor='center')

        odds_frame = tk.Frame(content_frame, bg='#F0F0F0', relief=tk.RAISED, bd=1)
        odds_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "主注", "3 Card Bonus"]
        header_bg = '#4B8BBE'
        header_fg = 'white'

        for col, header in enumerate(headers):
            header_label = tk.Label(
                odds_frame,
                text=header,
                font=('微软雅黑', 11, 'bold'),
                bg=header_bg,
                fg=header_fg,
                padx=10,
                pady=8,
                width=15
            )
            header_label.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        odds_data = [
            ("皇家同花顺", "500:1", "40:1 (公牌)"),
            ("同花顺", "100:1", "40:1"),
            ("四条", "40:1", "-"),
            ("葫芦", "10:1", "-"),
            ("同花", "6:1", "3:1"),
            ("顺子", "4:1", "6:1"),
            ("三条", "3:1", "30:1"),
            ("两对", "2:1", "-"),
            ("Jacks+对子", "1:1", "-"),
            ("对子6-10", "Push", "1:1"),
            ("高牌", "输", "输")
        ]

        for row, row_data in enumerate(odds_data, start=1):
            row_bg = '#E8F4F8' if row % 2 == 0 else '#FFFFFF'
            for col, cell_text in enumerate(row_data):
                cell_label = tk.Label(
                    odds_frame,
                    text=cell_text,
                    font=('微软雅黑', 10),
                    bg=row_bg,
                    padx=10,
                    pady=8,
                    justify=tk.CENTER,
                    wraplength=150
                )
                cell_label.grid(row=row, column=col, sticky='nsew', padx=1, pady=1)

        for col in range(len(headers)):
            odds_frame.columnconfigure(col, weight=1)
        for row in range(len(odds_data) + 1):
            odds_frame.rowconfigure(row, weight=1)

        notes_text = """
        注意事项:
        - 3 Card Bonus基于3张公共牌的牌型支付，与玩家手牌无关
        - 主注总和（Ante+3rd+4th+5th）根据最终5张牌支付
        - 对子6-10：主注Push（返还本金），3 Card Bonus对子支付1:1
        """

        notes_label = tk.Label(
            content_frame,
            text=notes_text,
            font=('微软雅黑', 10),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=15
        )
        notes_label.pack(fill=tk.X, padx=10, pady=10)

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy,
            style='TButton'
        )
        close_btn.pack(pady=10)

        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        style = ttk.Style()
        style.configure('TButton', font=('微软雅黑', 10))

    def on_close(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()

    def _load_assets(self):
        card_size = (100, 140)
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

    def check_bet_limit(self, bet_type, current_value, chip_value):
        """检查下注是否超过上限，如果超过则自动调整并显示警告"""
        new_value = current_value + chip_value

        if bet_type in ["ante", "street3", "street4", "street5"]:
            if new_value > self.MAIN_BET_MAX:
                messagebox.showwarning("下注上限", "该注已达上限，自动调整为 10000")
                return self.MAIN_BET_MAX
        elif bet_type == "bonus3":
            if new_value > self.BONUS3_BET_MAX:
                messagebox.showwarning("下注上限", "3 Card Bonus 已达上限，自动调整为 2500")
                return self.BONUS3_BET_MAX

        return new_value

    def is_bet_full(self, bet_type, current_value):
        if bet_type in ["ante", "street3", "street4", "street5"]:
            return current_value >= self.MAIN_BET_MAX
        elif bet_type == "bonus3":
            return current_value >= self.BONUS3_BET_MAX
        return False

    def add_chip_to_bet(self, bet_type):
        """添加筹码到下注区域（仅用于游戏开始前的下注，只针对 ante 和 bonus3）"""
        if not self.selected_chip:
            return

        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)

        if self.is_bet_full(bet_type, float(getattr(self, f"{bet_type}_var").get())):
            messagebox.showwarning("下注已满", "该注已满，不能再下注！")
            return

        current = float(getattr(self, f"{bet_type}_var").get())
        new_value = self.check_bet_limit(bet_type, current, chip_value)
        getattr(self, f"{bet_type}_var").set(str(int(new_value)))

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
        """更新玩家的手牌标签显示牌型，根据当前可见的牌数"""
        community_revealed = sum(self.game.cards_revealed["community"])
        # 所有可见牌：玩家2张 + 已翻开的公共牌
        visible_cards = self.game.player_hole + self.game.community_cards[:community_revealed]
        num_cards = len(visible_cards)

        if num_cards < 3:
            player_hand_name = ""
        else:
            values = [c.value for c in visible_cards]
            counts = Counter(values)
            # 按张数降序排序（四条、三条、对子...）
            mult_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)

            if num_cards == 3:
                # 三张牌：三条 或 对子 或 高牌
                if mult_counts[0][1] == 3:
                    player_hand_name = "三条"
                elif mult_counts[0][1] == 2:
                    pair_val = mult_counts[0][0]
                    rank_str = RANKS[pair_val - 2]  # 点数转字符串（2→'2'，14→'A'）
                    player_hand_name = f"对子{rank_str}"
                else:
                    player_hand_name = "高牌"

            elif num_cards == 4:
                # 四张牌：四条、三条、两对、一对、高牌
                if mult_counts[0][1] == 4:
                    player_hand_name = "四条"
                elif mult_counts[0][1] == 3:
                    player_hand_name = "三条"
                elif mult_counts[0][1] == 2:
                    pairs = [v for v, cnt in mult_counts if cnt == 2]
                    if len(pairs) == 2:
                        player_hand_name = "两对"
                    else:
                        pair_val = pairs[0]
                        rank_str = RANKS[pair_val - 2]
                        player_hand_name = f"对子{rank_str}"
                else:
                    player_hand_name = "高牌"

            else:  # num_cards == 5（或更多，但最多5）
                rank, comp = evaluate_hand(visible_cards)  # 使用原有评估函数
                if rank in (0, 1, 2):  # 对子等级
                    # 找出所有对子中最大的点数显示
                    pair_vals = [v for v, cnt in counts.items() if cnt == 2]
                    if pair_vals:
                        pair_val = max(pair_vals)
                        rank_str = RANKS[pair_val - 2]
                        player_hand_name = f"对子{rank_str}"
                    else:
                        player_hand_name = "高牌"  # 降级显示
                else:
                    player_hand_name = HAND_RANK_NAMES.get(rank, "")

        self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")

    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            widget.config(state=tk.DISABLED)

    def enable_action_buttons(self):
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            widget.config(state=tk.NORMAL)

    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧牌桌区域
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')

        # 公共牌区域
        community_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        community_frame.place(x=90, y=80, width=370, height=210)
        community_label = tk.Label(community_frame, text="公共牌", font=('Arial', 18), bg='#2a4a3c', fg='white')
        community_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg='#2a4a3c')
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=130, y=350, width=270, height=210)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=300, padx=10, pady=2)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=10)

        self.balance_label = tk.Label(
            info_frame,
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 18),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)

        self.stage_label = tk.Label(
            info_frame,
            text="准备下注",
            font=('Arial', 18, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=10)

        # 筹码区域
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
            chip_canvas = tk.Canvas(chip_row, width=55, height=55, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 54, 54, fill=bg_color, outline='black')
            chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text

        self.select_chip("$10")

        # 每注限制显示
        minmax_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        minmax_frame.pack(fill=tk.X, pady=5)

        header_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))

        tk.Label(header_frame, text="底注最低", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="底注最高", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="加注最高", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)

        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$10,000", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)

        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=5)

        # 第一行：Ante 和 Bonus3
        row1 = tk.Frame(bet_frame, bg='#2a4a3c')
        row1.pack(fill=tk.X, padx=40, pady=8)

        tk.Label(row1, text="底注:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row1, textvariable=self.ante_var, font=('Arial', 14),
                                    bg='white', fg='black', width=6, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row1, text="三张手牌加注:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=(20, 0))
        self.bonus3_var = tk.StringVar(value="0")
        self.bonus3_display = tk.Label(row1, textvariable=self.bonus3_var, font=('Arial', 14),
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.bonus3_display.pack(side=tk.LEFT, padx=5)
        self.bonus3_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bonus3"))
        self.bet_widgets["bonus3"] = self.bonus3_display

        # 第二行：3rd, 4th, 5th Street（不可点击）
        row2 = tk.Frame(bet_frame, bg='#2a4a3c')
        row2.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(row2, text="三街:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT)
        self.street3_var = tk.StringVar(value="0")
        self.street3_display = tk.Label(row2, textvariable=self.street3_var, font=('Arial', 14),
                                    bg='white', fg='black', width=6, relief=tk.SUNKEN, padx=5)
        self.street3_display.pack(side=tk.LEFT, padx=5)
        # 不绑定点击事件，仅显示

        tk.Label(row2, text="四街:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=(10,0))
        self.street4_var = tk.StringVar(value="0")
        self.street4_display = tk.Label(row2, textvariable=self.street4_var, font=('Arial', 14),
                                    bg='white', fg='black', width=6, relief=tk.SUNKEN, padx=5)
        self.street4_display.pack(side=tk.LEFT, padx=5)
        # 不绑定点击事件

        tk.Label(row2, text="五街:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=(10,0))
        self.street5_var = tk.StringVar(value="0")
        self.street5_display = tk.Label(row2, textvariable=self.street5_var, font=('Arial', 14),
                                    bg='white', fg='black', width=6, relief=tk.SUNKEN, padx=5)
        self.street5_display.pack(side=tk.LEFT, padx=5)
        # 不绑定点击事件

        # 保存所有显示标签以便重置颜色
        self.bet_widgets["street3"] = self.street3_display
        self.bet_widgets["street4"] = self.street4_display
        self.bet_widgets["street5"] = self.street5_display

        # 新增提示文字
        self.hint_label = tk.Label(bet_frame, text="对子5以下输，对子6-10平局，对子J以上赢",
                                font=('Arial', 16), bg='#2a4a3c', fg='#FFD700')
        self.hint_label.pack(pady=(0, 5))

        # 游戏操作按钮框架
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X, pady=10)

        # 开始按钮框架
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

        # 重设金额按钮
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重设金额",
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

        # 开始游戏按钮
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏",
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)

        # 状态信息
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏",
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)

        # 本局下注和上局获胜金额显示（移除本局退还）
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        row1_info = tk.Frame(bet_info_frame, bg='#2a4a3c')
        row1_info.pack(fill=tk.X, padx=10, pady=5)

        self.current_bet_label = tk.Label(
            row1_info, text="本局下注: $0.00",
            font=('Arial', 14), bg='#2a4a3c', fg='white',
            width=25, anchor='w'
        )
        self.current_bet_label.pack(side=tk.LEFT, padx=10)

        # 本局退还标签已移除

        row2_info = tk.Frame(bet_info_frame, bg='#2a4a3c')
        row2_info.pack(fill=tk.X, padx=10, pady=5)

        self.last_win_label = tk.Label(
            row2_info, text="  上局获胜: $0.00",
            font=('Arial', 14), bg='#2a4a3c', fg='#FFD700',
            width=25, anchor='w'
        )
        self.last_win_label.pack(side=tk.LEFT)

        self.info_button = tk.Button(
            row2_info,
            text="ℹ️",
            command=self.show_game_instructions,
            bg='#4B8BBE',
            fg='white',
            font=('Arial', 12),
            width=2,
            relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)

    def start_game(self):
        try:
            ante = int(self.ante_var.get())
            bonus3 = int(self.bonus3_var.get())

            if ante < 5:
                messagebox.showerror("错误", "底注至少需要5块")
                return
            if bonus3 > self.BONUS3_BET_MAX:
                messagebox.showwarning("下注上限", "三张手牌加注已达上限，自动调整为 2500")
                bonus3 = self.BONUS3_BET_MAX
                self.bonus3_var.set(str(bonus3))

            # 检查余额是否足够开始游戏（需要满足 ante*4 + bonus3）
            if ante * 4 + bonus3 > self.balance:
                messagebox.showerror("错误", f"余额不足！需要至少 ${ante * 4 + bonus3:.2f}")
                return

            total_bet = ante + bonus3
            self.balance -= total_bet
            self.update_balance()

            self.reset_bets_button.config(state=tk.DISABLED)
            self.start_button.config(state=tk.DISABLED)

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

            self.game.reset_game()
            self.game.ante = ante
            self.game.bonus3 = bonus3
            self.game.street3 = 0
            self.game.street4 = 0
            self.game.street5 = 0
            self.game.folded = False
            self.game.deal_initial()

            # 清除所有卡片
            for widget in self.community_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()

            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            self.card_positions = {}

            # 添加所有卡片到动画队列，玩家手牌增加10px间距
            for i in range(3):
                card_id = f"community_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50),
                    "target": (i * 110, 0)  # 公共牌之间原有110间距，保持不变
                }
                self.animation_queue.append(card_id)

            for i in range(2):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50),
                    "target": (i * 110, 0)  # 从 i*100 改为 i*110，增加10px间距
                }
                self.animation_queue.append(card_id)

            self.animate_deal()

            self.stage_label.config(text="查看底牌")
            self.status_label.config(text="手牌已打开，请选择下注或弃牌")

            # 禁用所有下注输入
            self.ante_display.unbind("<Button-1>")
            self.bonus3_display.unbind("<Button-1>")
            # street3/4/5 本来就没有绑定，不需要解绑
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")

        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return

        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)

        if card_id.startswith("community"):
            frame = self.community_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.community_cards[idx] if idx < len(self.game.community_cards) else None
        elif card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hole[idx] if idx < len(self.game.player_hole) else None

        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(
            x=self.card_positions[card_id]["current"][0],
            y=self.card_positions[card_id]["current"][1] + 20
        )

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
                card_label.place(x=target_x, y=target_y)
                card_label.is_moving = False
                if card_label.target_pos == (50, 50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                self.after(100, self.animate_deal)
                return

            step_x = dx * 0.2
            step_y = dy * 0.2
            new_x = current_x + step_x
            new_y = current_y + step_y
            card_label.place(x=new_x, y=new_y)

            self.after(20, lambda: self.animate_card_move(card_label))

        except tk.TclError:
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)
            return

    def reveal_player_cards(self):
        """翻开玩家牌（带动画）"""
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["player"][i] = True

        self.update_hand_labels()

        # 1.5秒后显示倍数按钮
        self.after(1500, self.show_street3_buttons)

    def show_street3_buttons(self):
        """显示3rd Street的下注选项"""
        self.game.stage = "street3"
        self.stage_label.config(text="第三街")
        self.status_label.config(text="请选择下注倍数或弃牌")

        # 清空操作按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        btn_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        btn_frame.pack(pady=5)

        ante = self.game.ante

        # 1x 按钮：需要余额 >= ante
        btn1 = tk.Button(btn_frame, text="1x", command=lambda: self.place_street_bet(1),
                         font=('Arial', 14), bg='#4CAF50', fg='white', width=5)
        btn1.pack(side=tk.LEFT, padx=5)
        if self.balance < ante:
            btn1.config(state=tk.DISABLED)

        # 2x 按钮：需要余额 >= ante*4
        btn2 = tk.Button(btn_frame, text="2x", command=lambda: self.place_street_bet(2),
                         font=('Arial', 14), bg='#4CAF50', fg='white', width=5)
        btn2.pack(side=tk.LEFT, padx=5)
        if self.balance < ante * 4:
            btn2.config(state=tk.DISABLED)

        # 3x 按钮：需要余额 >= ante*5
        btn3 = tk.Button(btn_frame, text="3x", command=lambda: self.place_street_bet(3),
                         font=('Arial', 14), bg='#4CAF50', fg='white', width=5)
        btn3.pack(side=tk.LEFT, padx=5)
        if self.balance < ante * 5:
            btn3.config(state=tk.DISABLED)

        tk.Button(btn_frame, text="弃牌", command=self.fold_game,
                  font=('Arial', 14), bg='#F44336', fg='white', width=8).pack(side=tk.LEFT, padx=20)

    def place_street_bet(self, multiplier):
        """处理每轮的下注"""
        # 清空当前操作框架中的所有按钮（即隐藏按钮）
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        ante = self.game.ante
        amount = ante * multiplier

        if self.game.stage == "street3":
            bet_var = "street3"
            next_stage = "street4"
            community_index = 0
        elif self.game.stage == "street4":
            bet_var = "street4"
            next_stage = "street5"
            community_index = 1
        elif self.game.stage == "street5":
            bet_var = "street5"
            next_stage = "showdown"
            community_index = 2
        else:
            return

        # 检查余额（理论上按钮已根据余额禁用，但再次确认）
        if amount > self.balance:
            messagebox.showerror("错误", "余额不足！")
            # 余额不足时，重新显示可用按钮（重新创建）
            if self.game.stage == "street3":
                self.show_street3_buttons()
            elif self.game.stage == "street4":
                self.show_next_street_buttons()  # 注意：这里 stage 已经是 street4
            elif self.game.stage == "street5":
                self.show_next_street_buttons()
            return

        # 扣除余额
        self.balance -= amount
        self.update_balance()

        # 记录下注
        setattr(self.game, bet_var, amount)
        getattr(self, f"{bet_var}_var").set(str(amount))

        # 更新本局下注总额
        total_bet = self.game.ante + self.game.bonus3 + self.game.street3 + self.game.street4 + self.game.street5
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        # 翻开对应公共牌
        self.reveal_community_card(community_index)

        if next_stage == "showdown":
            # 第三张公牌翻完后，直接进入结算（延迟 2000ms 让动画完成）
            self.after(2000, self.show_showdown)
        else:
            # 准备下一阶段：延迟 1500ms 后显示新按钮，让翻牌动画有时间完成
            self.game.stage = next_stage
            if next_stage.upper() == "STREET4":
                self.stage_label.config(text="第四街")
            else:
                self.stage_label.config(text="第五街")
            self.status_label.config(text="请选择下注倍数或弃牌")
            self.after(1500, self.show_next_street_buttons)

    def show_next_street_buttons(self):
        """显示下一轮的按钮"""
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        btn_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        btn_frame.pack(pady=5)

        ante = self.game.ante

        # 根据当前阶段设置条件
        if self.game.stage == "street4":
            # 四街
            btn1 = tk.Button(btn_frame, text="1x", command=lambda: self.place_street_bet(1),
                             font=('Arial', 14), bg='#4CAF50', fg='white', width=5)
            btn1.pack(side=tk.LEFT, padx=5)
            if self.balance < ante:
                btn1.config(state=tk.DISABLED)

            btn2 = tk.Button(btn_frame, text="2x", command=lambda: self.place_street_bet(2),
                             font=('Arial', 14), bg='#4CAF50', fg='white', width=5)
            btn2.pack(side=tk.LEFT, padx=5)
            if self.balance < ante * 3:
                btn2.config(state=tk.DISABLED)

            btn3 = tk.Button(btn_frame, text="3x", command=lambda: self.place_street_bet(3),
                             font=('Arial', 14), bg='#4CAF50', fg='white', width=5)
            btn3.pack(side=tk.LEFT, padx=5)
            if self.balance < ante * 4:
                btn3.config(state=tk.DISABLED)

        elif self.game.stage == "street5":
            # 五街
            btn1 = tk.Button(btn_frame, text="1x", command=lambda: self.place_street_bet(1),
                             font=('Arial', 14), bg='#4CAF50', fg='white', width=5)
            btn1.pack(side=tk.LEFT, padx=5)
            if self.balance < ante:
                btn1.config(state=tk.DISABLED)

            btn2 = tk.Button(btn_frame, text="2x", command=lambda: self.place_street_bet(2),
                             font=('Arial', 14), bg='#4CAF50', fg='white', width=5)
            btn2.pack(side=tk.LEFT, padx=5)
            if self.balance < ante * 2:
                btn2.config(state=tk.DISABLED)

            btn3 = tk.Button(btn_frame, text="3x", command=lambda: self.place_street_bet(3),
                             font=('Arial', 14), bg='#4CAF50', fg='white', width=5)
            btn3.pack(side=tk.LEFT, padx=5)
            if self.balance < ante * 3:
                btn3.config(state=tk.DISABLED)

        tk.Button(btn_frame, text="弃牌", command=self.fold_game,
                  font=('Arial', 14), bg='#F44336', fg='white', width=8).pack(side=tk.LEFT, padx=20)

    def reveal_community_card(self, index):
        """翻开指定位置的公共牌"""
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up and i == index:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["community"][i] = True
                break
        self.update_hand_labels()

    def fold_game(self):
        """玩家弃牌"""
        # 禁用所有按钮，防止重复点击
        self.disable_all_buttons_in_frame(self.action_frame)

        self.game.folded = True
        self.status_label.config(text="玩家弃牌，结算边注...")

        # 翻开所有未翻开的公共牌（为了结算边注）
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["community"][i] = True

        self.update_hand_labels()

        # 2秒后结算
        self.after(2000, self.show_showdown)

    def flip_card_animation(self, card_label):
        """卡片翻转动画"""
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.animate_flip(card_label, front_img, 0)

    def animate_flip(self, card_label, front_img, step):
        steps = 10
        if step > steps:
            card_label.is_face_up = True
            return

        if step <= steps // 2:
            width = 100 - (step * 20)
            if width <= 0:
                width = 1
            card_label.config(image=self.back_image)
        else:
            width = (step - steps // 2) * 20
            if width <= 0:
                width = 1
            card_label.config(image=front_img)

        card_label.place(width=width)
        step += 1
        card_label.after(50, lambda: self.animate_flip(card_label, front_img, step))

    def show_showdown(self):
        """结算并显示结果"""
        # 确保所有牌已翻开
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["community"][i] = True

        self.update_hand_labels()

        # 评估最终手牌
        final_rank = self.game.evaluate_final_hand()
        bonus3_rank = self.game.evaluate_community_3()

        winnings = self.calculate_winnings(final_rank, bonus3_rank)
        self.last_win = winnings
        self.balance += winnings
        self.update_balance()

        # 更新下注格子显示获胜金额（含本金）
        self.ante_var.set(str(int(self.win_details["ante"])))
        self.bonus3_var.set(str(int(self.win_details["bonus3"])))
        self.street3_var.set(str(int(self.win_details["street3"])))
        self.street4_var.set(str(int(self.win_details["street4"])))
        self.street5_var.set(str(int(self.win_details["street5"])))

        # 更新显示
        self.last_win_label.config(text=f"  上局获胜: ${winnings:.2f}")

        # 高亮赢注
        for bet_type, widget in self.bet_widgets.items():
            if bet_type in ["street3", "street4", "street5", "ante"]:
                # 主注部分
                if self.game.folded:
                    widget.config(bg='white')  # 弃牌所有主注输
                else:
                    amt = getattr(self.game, bet_type, 0)
                    if self.win_details[bet_type] > amt:
                        widget.config(bg='gold')  # 赢
                    elif self.win_details[bet_type] == amt:
                        widget.config(bg='light blue')  # Push
                    else:
                        widget.config(bg='white')  # 输
            elif bet_type == "bonus3":
                if self.win_details["bonus3"] > 0:
                    widget.config(bg='gold')
                else:
                    widget.config(bg='white')

        self.status_label.config(text="游戏结束。")

        # 显示再来一局按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        restart_btn = tk.Button(
            self.action_frame, text="再来一局",
            command=self.reset_game,
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=5)
        restart_btn.bind("<Button-3>", self.show_card_sequence)

        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def calculate_winnings(self, final_rank, bonus3_rank):
        """计算总赢取金额"""
        self.win_details = {k:0 for k in self.win_details}
        total = 0

        # 主注部分（Ante + 3rd + 4th + 5th）
        if not self.game.folded:
            main_total = self.game.ante + self.game.street3 + self.game.street4 + self.game.street5
            payout_mult = MAIN_BET_PAYOUT.get(final_rank, -1)  # -1 表示输
            if payout_mult >= 0:
                # 赢或Push：返回本金 * (1 + payout_mult)
                self.win_details["ante"] = self.game.ante * (1 + payout_mult)
                self.win_details["street3"] = self.game.street3 * (1 + payout_mult)
                self.win_details["street4"] = self.game.street4 * (1 + payout_mult)
                self.win_details["street5"] = self.game.street5 * (1 + payout_mult)
                total += self.win_details["ante"] + self.win_details["street3"] + self.win_details["street4"] + self.win_details["street5"]
            else:
                # 输，无返还
                self.win_details["ante"] = self.win_details["street3"] = self.win_details["street4"] = self.win_details["street5"] = 0
        else:
            # 弃牌：所有主注输
            self.win_details["ante"] = self.win_details["street3"] = self.win_details["street4"] = self.win_details["street5"] = 0

        # 3 Card Bonus 边注
        if self.game.bonus3 > 0:
            if bonus3_rank in BONUS3_PAYOUT:
                payout = BONUS3_PAYOUT[bonus3_rank]
                self.win_details["bonus3"] = self.game.bonus3 * (1 + payout)
            else:
                self.win_details["bonus3"] = 0   # 高牌全输
            total += self.win_details["bonus3"]

        return total

    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

        if self.active_card_labels:
            self.disable_action_buttons()
            self.animate_collect_cards(auto_reset)
            return

        self._do_reset(auto_reset)

    def reset_bets(self):
        """重置所有投注金额为0"""
        self.ante_var.set("0")
        self.bonus3_var.set("0")
        self.street3_var.set("0")
        self.street4_var.set("0")
        self.street5_var.set("0")

        self.status_label.config(text="已重置所有下注金额")

        for widget in self.bet_widgets.values():
            widget.config(bg='white')

        # 短暂高亮
        for w in [self.ante_display, self.bonus3_display, self.street3_display, self.street4_display, self.street5_display]:
            w.config(bg='#FFCDD2')
        self.after(500, lambda: [w.config(bg='white') for w in [self.ante_display, self.bonus3_display, self.street3_display, self.street4_display, self.street5_display]])

    def animate_collect_cards(self, auto_reset):
        self.disable_action_buttons()
        self.animate_move_cards_out(auto_reset)

    def animate_move_cards_out(self, auto_reset):
        if not self.active_card_labels:
            self._do_reset(auto_reset)
            return

        for card_label in self.active_card_labels:
            card_label.target_pos = (1200, card_label.winfo_y())

        self.animate_card_out_step(auto_reset)

    def animate_card_out_step(self, auto_reset):
        all_done = True
        for card_label in self.active_card_labels[:]:
            if not hasattr(card_label, 'target_pos'):
                continue

            current_x = card_label.winfo_x()
            target_x, target_y = card_label.target_pos

            dx = target_x - current_x
            if abs(dx) < 5:
                card_label.place(x=target_x, y=target_y)
                card_label.destroy()
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
                continue

            new_x = current_x + dx * 0.2
            card_label.place(x=new_x)
            all_done = False

        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset))
        else:
            self._do_reset(auto_reset)

    def _do_reset(self, auto_reset=False):
        self._load_assets()

        self.game.reset_game()
        self.stage_label.config(text="准备下注")
        self.player_label.config(text="玩家")

        self.ante_var.set("0")
        self.bonus3_var.set("0")
        self.street3_var.set("0")
        self.street4_var.set("0")
        self.street5_var.set("0")

        for widget in self.bet_widgets.values():
            widget.config(bg='white')

        self.active_card_labels = []

        # 重新绑定下注事件（仅 ante 和 bonus3）
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bonus3_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bonus3"))
        # street3/4/5 不绑定
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))

        for widget in self.action_frame.winfo_children():
            widget.destroy()

        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

        self.reset_bets_button = tk.Button(
            start_button_frame, text="重设金额",
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

        self.start_button = tk.Button(
            start_button_frame, text="开始游戏",
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)

        self.current_bet_label.config(text="本局下注: $0.00")

        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

    def show_card_sequence(self, event):
        """显示本局牌序窗口"""
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

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
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')

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
    app = MississippiStudGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")