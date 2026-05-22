import tkinter as tk
from tkinter import ttk, messagebox
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
    1: '对子',
    0: '高牌'
}

# ==================== 新增：月亮扑克赔付表 ====================
# 超級賭注赔付表 (Super Wager)
SUPER_BONUS_PAYOUT = {
    "四条": 250,          # 四条 250:1
    "五张脸牌": 120,      # 五张脸牌 (J,Q,K) 120:1
    "葫芦": 100,          # 葫芦 100:1
    "同花": 60,           # 同花 60:1 (含同花顺/皇家同花顺)
    "顺子": 30,           # 顺子 30:1
    "三条": 8,            # 三条 8:1
    "Ace-king-queen": 5,  # 手牌中有A,K,Q 5:1
    "同颜色": 2            # 五张牌同色（红或黑）2:1
}

# 立即支付表 (Instant Payout) - 针对Ante
INSTANT_PAYOUT = {
    9: 1000,  # 皇家同花顺 1000:1
    8: 200    # 同花顺 200:1
}

# 加注赔付表 (Raise Bet)
RAISE_PAYOUT = {
    9: 100,   # 皇家同花顺 100:1
    8: 50,    # 同花顺 50:1
    7: 20,    # 四条 20:1
    6: 7,     # 葫芦 7:1
    5: 5,     # 同花 5:1
    4: 4,     # 顺子 4:1
    3: 3,     # 三条 3:1
    2: 2,     # 两对 2:1
    1: 1,     # 对子 1:1
    0: 1      # 高牌 1:1
}
# =============================================================

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

# ==================== 按牌型排序函数 ====================
def sort_hand_for_display(hand, hand_eval):
    rank = hand_eval[0]
    if rank in [4, 8, 9]:
        values = [c.value for c in hand]
        if 14 in values and 2 in values and len(set(values)) == 5:
            sorted_hand = sorted(hand, key=lambda c: 1 if c.value == 14 else c.value)
        else:
            sorted_hand = sorted(hand, key=lambda c: c.value)
        return sorted_hand
    else:
        from collections import Counter
        counts = Counter(c.value for c in hand)
        sorted_hand = sorted(hand, key=lambda c: (counts[c.value], c.value), reverse=True)
        return sorted_hand
# =====================================================

def evaluate_five_card_hand(cards):
    if not cards or len(cards) < 5:
        return (0, [])

    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]

    is_flush = len(set(suits)) == 1

    values_sorted_asc = sorted([c.value for c in cards])
    is_straight = False
    straight_values = None

    if len(set(values_sorted_asc)) == 5:
        if values_sorted_asc[-1] - values_sorted_asc[0] == 4:
            is_straight = True
            straight_values = sorted(values, reverse=True)
        elif values_sorted_asc == [2, 3, 4, 5, 14]:
            is_straight = True
            straight_values = [5, 4, 3, 2, 1]

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
        return (1, sorted_values)
    return (0, values)

# ---------- 新增：从 n 张牌中选出最佳 5 张并返回评估结果 ----------
from itertools import combinations as _combinations

def evaluate_best_hand(cards):
    """
    给定 cards (>=5)，在所有 5 张组合中挑出评价最优的一组并返回 (rank, values).
    rank: 与 evaluate_five_card_hand 返回的一致（9..0）
    values: 用于比较的 tiebreaker 列表
    """
    if not cards or len(cards) < 5:
        return (0, [])
    best_rank = -1
    best_values = None
    # 遍历所有 5 张组合
    for combo in _combinations(cards, 5):
        r, vals = evaluate_five_card_hand(list(combo))
        if r > best_rank:
            best_rank = r
            best_values = vals
        elif r == best_rank:
            # 进一步比较 values 列表（逐项比较）
            if best_values is None:
                best_values = vals
            else:
                # 比较 vals 与 best_values 长度可能不同，逐项比
                for i in range(min(len(vals), len(best_values))):
                    if vals[i] > best_values[i]:
                        best_values = vals
                        break
                    elif vals[i] < best_values[i]:
                        break
                else:
                    # 如果到这里仍相等，则比较完整牌面的降序值（更严格的 tiebreaker）
                    v1 = sorted([c.value for c in combo], reverse=True)
                    v2 = sorted([c for c in best_values], reverse=True) if isinstance(best_values[0], int) else sorted([c for c in best_values], reverse=True)
                    if v1 > v2:
                        best_values = vals
    return (best_rank, best_values if best_values is not None else [])

# ---------- 修改：compare_hands 使用 evaluate_best_hand ，支持玩家6张的情况 ----------
def compare_hands(hand1, hand2):
    """
    支持 hand1 或 hand2 为 >=5 张的情况：
    - 从各自牌集中选出最佳 5 张（evaluate_best_hand），再比较 rank 与 values。
    返回 1: hand1 强， -1: hand2 强， 0: 平手
    """
    if not hand1 or len(hand1) < 5 or not hand2 or len(hand2) < 5:
        return 0

    rank1, values1 = evaluate_best_hand(hand1)
    rank2, values2 = evaluate_best_hand(hand2)

    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1
    else:
        # 逐项比较 values 列表
        min_len = min(len(values1), len(values2))
        for i in range(min_len):
            if values1[i] > values2[i]:
                return 1
            elif values1[i] < values2[i]:
                return -1
        # 若仍相等，使用完整牌面降序比较作为最终tiebreak
        values1_full = sorted([c.value for c in hand1], reverse=True)
        values2_full = sorted([c.value for c in hand2], reverse=True)
        for i in range(min(len(values1_full), len(values2_full))):
            if values1_full[i] > values2_full[i]:
                return 1
            elif values1_full[i] < values2_full[i]:
                return -1
        return 0

# ==================== 新增：超级赌注评估函数 ====================
def evaluate_super_bonus(hand):
    """
    评估一手5张牌是否符合超级赌注赔付条件
    返回 (赔付名称, 赔付倍数) 或 (None, 0)
    """
    if not hand or len(hand) < 5:
        return None, 0

    # 检查四条
    rank, values = evaluate_five_card_hand(hand)
    if rank == 7:
        return "四条", SUPER_BONUS_PAYOUT["四条"]

    # 检查五张脸牌 (J, Q, K)
    face_cards = [c for c in hand if c.rank in ['J', 'Q', 'K']]
    if len(face_cards) == 5:
        return "五张脸牌", SUPER_BONUS_PAYOUT["五张脸牌"]

    # 检查葫芦
    if rank == 6:
        return "葫芦", SUPER_BONUS_PAYOUT["葫芦"]

    # 检查同花/同花顺/皇家同花顺
    if rank in [5, 8, 9]:  # 同花、同花顺、皇家同花顺
        return "同花", SUPER_BONUS_PAYOUT["同花"]

    # 检查顺子
    if rank == 4:
        return "顺子", SUPER_BONUS_PAYOUT["顺子"]

    # 检查三条
    if rank == 3:
        return "三条", SUPER_BONUS_PAYOUT["三条"]

    # 检查 Ace-King-Queen (手牌中同时有A、K、Q)
    ranks_in_hand = [c.rank for c in hand]
    if 'A' in ranks_in_hand and 'K' in ranks_in_hand and 'Q' in ranks_in_hand:
        return "Ace-king-queen", SUPER_BONUS_PAYOUT["Ace-king-queen"]

    # 检查同颜色 (全红或全黑)
    suits_in_hand = [c.suit for c in hand]
    all_red = all(s in ['♥', '♦'] for s in suits_in_hand)
    all_black = all(s in ['♠', '♣'] for s in suits_in_hand)
    if all_red or all_black:
        return "同颜色", SUPER_BONUS_PAYOUT["同颜色"]

    return None, 0
# ===============================================================

class LunarPokerGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.player_original_hand = []   # 保存玩家原始5张手牌，用于超级红利
        self.ante = 0
        self.super_bet = 0
        self.buy_exchange_bet = 0
        self.raise_bet = 0
        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False, False, False, False, False],
            "dealer": [False, False, False, False, False]
        }
        self.card_sequence = self.deck.full_deck.copy()
        self.cut_position = self.deck.cut_position
        self.buy_exchange_phase = False
        self.exchanged_cards_count = 0
        self.instant_payout_done = False
        self.player_super_paid = False    # 不再使用，改为 super_paid
        self.dealer_super_paid = False    # 不再使用
        self.super_paid = False            # 统一超级红利是否已支付
        self.buy_used = False
        self.dealer_exchange_cost = 0      # 新增：记录为庄家换牌支付的金额

    def deal_initial(self):
        self.player_hand = self.deck.deal(5)
        self.dealer_hand = self.deck.deal(5)
        self.player_original_hand = self.player_hand.copy()   # 保存原始手牌

    def dealer_qualifies(self):
        if not self.dealer_hand or len(self.dealer_hand) < 5:
            return False
        rank, _ = evaluate_five_card_hand(self.dealer_hand)
        if rank >= 1:
            return True
        has_ace = any(card.rank == 'A' for card in self.dealer_hand)
        has_king = any(card.rank == 'K' for card in self.dealer_hand)
        return has_ace and has_king

class LunarPokerGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("月亮搜哈扑克")
        self.geometry("1150x650+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')

        self.username = username
        self.balance = initial_balance
        self.game = LunarPokerGame()
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
            "raise": 0,
            "super_bonus": 0
        }
        self.bet_widgets = {}
        self.super_bet_var = tk.IntVar(value=0)
        self.flipping_cards = []
        self.flip_step = 0
        self.moved_cards = []
        self.ak_moved = False
        self.fold_button = None
        self.play_button = None
        self.buy_button = None
        self.exchange_button = None
        self.ak_animation_active = False
        self._resetting = False
        self.fold_mode = False

        # 新增：记录当前选择的换牌索引
        self.selected_cards_for_exchange = []

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
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
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
        """添加筹码到下注区域（修改：超级赌注不得大于底注）"""
        if not self.selected_chip:
            return

        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)

        if bet_type == "ante":
            current = float(self.ante_var.get())
            new_value = current + chip_value
            if new_value > 10000:
                new_value = 10000
                messagebox.showwarning("下注限制", f"底注上限为10000，已自动调整")
            self.ante_var.set(str(int(new_value)))
        elif bet_type == "super_bet":
            # 新规则：超级红利必须 <= 底注
            try:
                current_ante = float(self.ante_var.get())
            except Exception:
                current_ante = 0.0
            current = float(self.super_bet_var.get())
            new_value = current + chip_value

            if current_ante > 0:
                if new_value > current_ante:
                    new_value = current_ante
                    messagebox.showwarning("下注限制", "超级红利不得大于底注，已自动调整为底注金额")
            else:
                if new_value > 10000:
                    new_value = 10000
                    messagebox.showwarning("下注限制", f"超级红利上限为10000，已自动调整")

            self.super_bet_var.set(str(int(new_value)))

    def _create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧牌桌区域
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=20, width=600, height=250)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 居中提示
        self.ante_info_label = tk.Label(
            table_canvas,
            text="庄家必须持有高牌A/K或以上牌型才合格\n庄家不合格的 底注获胜 加注平局",
            font=('Arial', 22),
            bg='#35654d',
            fg='#FFD700'
        )
        self.ante_info_label.update_idletasks()
        label_width = self.ante_info_label.winfo_width()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        center_x = (canvas_width - label_width) // 2
        self.ante_info_label.place(x=center_x + 355, y=280, anchor='n')

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
            text="翻牌前",
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
            chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text

        self.select_chip("$10")

        # 下注限制
        minmax_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        minmax_frame.pack(fill=tk.X, pady=5)

        header_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))

        tk.Label(header_frame, text="底注最低", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="底注最高", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="超级最高", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)

        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$10,000", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="等于底注", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)

        # ========== 下注区域 ==========
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)

        # 第一行: 超级红利
        super_row = tk.Frame(bet_frame, bg='#2a4a3c')
        super_row.pack(fill=tk.X, padx=40, pady=3)

        super_label = tk.Label(super_row, text="超级红利:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        super_label.pack(side=tk.LEFT)

        self.super_bet_var = tk.StringVar(value="0")
        self.super_bet_display = tk.Label(super_row, textvariable=self.super_bet_var, font=('Arial', 14),
                                         bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.super_bet_display.pack(side=tk.LEFT, padx=5)
        self.super_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("super_bet"))
        self.bet_widgets["super_bet"] = self.super_bet_display

        # 第二行: 底注 和 换/加牌
        ante_exchange_row = tk.Frame(bet_frame, bg='#2a4a3c')
        ante_exchange_row.pack(fill=tk.X, padx=40, pady=3)

        ante_label = tk.Label(ante_exchange_row, text="底注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        ante_label.pack(side=tk.LEFT)

        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(ante_exchange_row, textvariable=self.ante_var, font=('Arial', 14),
                                     bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(ante_exchange_row, text="   ", bg='#2a4a3c').pack(side=tk.LEFT, padx=10)

        exchange_label = tk.Label(ante_exchange_row, text="换/加牌:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        exchange_label.pack(side=tk.LEFT)

        self.exchange_var = tk.StringVar(value="0")
        self.exchange_display = tk.Label(ante_exchange_row, textvariable=self.exchange_var, font=('Arial', 14),
                                         bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.exchange_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["exchange"] = self.exchange_display

        # 第三行: 加注
        raise_row = tk.Frame(bet_frame, bg='#2a4a3c')
        raise_row.pack(fill=tk.X, padx=40, pady=3)

        raise_label = tk.Label(raise_row, text="加注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        raise_label.pack(side=tk.LEFT)

        self.raise_var = tk.StringVar(value="0")
        self.raise_display = tk.Label(raise_row, textvariable=self.raise_var, font=('Arial', 14),
                                      bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.raise_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["raise"] = self.raise_display

        # 游戏操作按钮框架
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

        # 本局下注和上局获胜金额显示
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

    def show_game_instructions(self):
        """显示月亮扑克游戏规则（表格化风格）"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("月亮扑克游戏规则")
        win.geometry("900x700")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')

        # 主框架
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 画布
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        # 内容框架
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')

        # 标题
        tk.Label(
            content_frame,
            text="月亮扑克游戏规则",
            font=('微软雅黑', 16, 'bold'),
            bg='#F0F0F0',
            fg='#333'
        ).pack(pady=(10, 15))

        # 规则文本
        rules_text = """
        1. 下注阶段:
        - 底注: 基础下注（必须，最低$10，最高$10000）
        - 超级红利: 可选下注，金额必须 ≤ 底注（最高$10000）

        2. 游戏流程:
        a. 发牌: 玩家和庄家各发五张牌，庄家第一张明牌。
        b. 玩家手牌翻开并自动排序。
        c. 立即检查超级红利（根据玩家原始手牌）并支付。
        d. 若玩家手牌为同花顺或皇家同花顺，底注立即支付（见下表），游戏结束。
        e. 否则，玩家进入决策阶段:
            - 弃牌: 输掉底注，庄家开牌后游戏结束。
            - 下注2X: 下注底注2倍的加注，然后进入摊牌。
            - 买入: 支付等于底注的金额获得一张额外牌（共6张），重新排序后再次决策。
            - 换牌: 选择2-5张牌，支付等于底注的金额，从牌堆补回相同数量，重新排序后再次决策。
        f. 买入或换牌后，玩家再次选择 弃牌 或 下注2X。
        g. 摊牌阶段: 庄家开牌，排序。
            - 检查庄家手牌是否符合超级红利赔付条件（与玩家原始手牌比较，取较高倍数支付一次）。
            - 然后比较牌型:
                * 庄家不合格（无A/K或以上牌型）: 底注1:1获胜，加注退还。
                * 庄家合格时:
                    - 玩家赢: 底注退还，加注按玩家牌型赔付（见下表）。
                    - 平局: 底注和加注均退还。
                    - 玩家输: 输掉底注和加注。
        """

        tk.Label(
            content_frame,
            text=rules_text,
            font=('微软雅黑', 11),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=20,
            pady=10
        ).pack(fill=tk.X, padx=10, pady=5)

        # 赔付表标题
        tk.Label(
            content_frame,
            text="赔付表",
            font=('微软雅黑', 14, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 10), anchor='center')

        # 创建赔付表框架
        payout_frame = tk.Frame(content_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=20, pady=5)

        # 表头
        headers = ["牌型", "加注赔付", "超级红利赔付", "立即支付"]
        for col, h in enumerate(headers):
            tk.Label(
                payout_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 数据行
        payout_data = [
            # 牌型               加注赔付  超级红利赔付  立即支付
            ("皇家同花顺",       "100:1",   "60:1",       "1000:1"),
            ("同花顺",           "50:1",    "60:1",       "200:1"),
            ("四条",             "20:1",    "250:1",      "-"),
            ("葫芦",             "7:1",     "100:1",      "-"),
            ("同花",             "5:1",     "60:1",       "-"),
            ("顺子",             "4:1",     "30:1",       "-"),
            ("三条",             "3:1",     "8:1",        "-"),
            ("两对",             "2:1",     "-",          "-"),
            ("对子",             "1:1",     "-",          "-"),
            ("高牌",             "1:1",     "-",          "-"),
            ("五张脸牌(J,Q,K)",  "-",       "120:1",      "-"),
            ("同颜色(全红/黑)",  "-",       "2:1",        "-"),
            ("Ace-King-Queen",   "-",       "5:1",        "-")
        ]

        for r, row_data in enumerate(payout_data, start=1):
            bg_color = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    payout_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg_color,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配列宽
        for c in range(len(headers)):
            payout_frame.columnconfigure(c, weight=1)

        # 注释
        notes = """
        注:
        * 庄家合格条件：必须持有A和K，或牌型≥对子。
        * 超级红利赔付基于玩家原始手牌（5张）或庄家手牌，取较高倍数支付一次。
        * “同花”赔付包含同花顺和皇家同花顺。
        * 立即支付仅在玩家手牌为皇家同花顺或同花顺时触发，且游戏直接结束。
        * 加注赔付倍数为“X:1”，表示净赢额，例如下注$10且赔付100:1，则赢得$1000（净利）。
        """

        tk.Label(
            content_frame,
            text=notes,
            font=('微软雅黑', 10),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=20,
            pady=10
        ).pack(fill=tk.X, padx=10, pady=5)

        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        # 关闭按钮
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)

        # 绑定鼠标滚轮
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
        """
        更新玩家和庄家的手牌标签显示牌型。
        - 玩家：若有 >=5 张牌，使用 evaluate_best_hand 计算最佳 5 张并显示牌型名称。
        - 庄家：只有当 self.game.dealer_sorted 为 True 时才显示牌型名称。
        """
        # 玩家标签
        try:
            if self.game.player_hand and len(self.game.player_hand) >= 5:
                rank, _ = evaluate_best_hand(self.game.player_hand)
                player_hand_name = HAND_RANK_NAMES.get(rank, "未知")
                if rank == 0:
                    has_ace = any(card.rank == 'A' for card in self.game.player_hand)
                    has_king = any(card.rank == 'K' for card in self.game.player_hand)
                    if has_ace and has_king:
                        player_hand_name = "高牌(ACE和KING)"
                self.player_label.config(text=f"玩家 - {player_hand_name}")
            else:
                self.player_label.config(text="玩家")
        except Exception:
            try:
                self.player_label.config(text="玩家")
            except:
                pass

    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)

    def enable_action_buttons(self):
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)

    # ==================== 动画相关方法 ====================
    def start_both_sort_animation(self):
        """
        开始庄家手牌的排序动画（仅调整庄家手牌；玩家手牌保持不变）
        行为：
        - 计算庄家手牌的排序结果并仅对庄家区的牌标签做平移动画
        - 在排序动画开始后 0.5 秒更新庄家标签显示牌型（庄家 - {牌型}）
        - 动画结束后调用 self.after_dealer_sort()
        """
        if getattr(self, "_resetting", False):
            return

        # 评估并排序庄家手牌（只对 dealer）
        try:
            dealer_eval = evaluate_five_card_hand(self.game.dealer_hand)
            sorted_dealer = sort_hand_for_display(self.game.dealer_hand, dealer_eval)
        except Exception:
            # 出错就保底不变
            sorted_dealer = list(self.game.dealer_hand)

        # 更新内部庄家手牌顺序为排序结果（只改庄家）
        try:
            self.game.dealer_hand = sorted_dealer
        except Exception:
            pass

        # 在排序动画正式开始后 0.5s 更新庄家标签显示牌型
        try:
            def update_dealer_label_later():
                try:
                    if self.game.dealer_hand and len(self.game.dealer_hand) >= 5:
                        rank, _ = evaluate_five_card_hand(self.game.dealer_hand)
                        dealer_hand_name = HAND_RANK_NAMES.get(rank, "未知")
                        if rank == 0:
                            has_ace = any(card.rank == 'A' for card in self.game.dealer_hand)
                            has_king = any(card.rank == 'K' for card in self.game.dealer_hand)
                            if has_ace and has_king:
                                dealer_hand_name = "高牌(ACE和KING)"
                        self.dealer_label.config(text=f"庄家 - {dealer_hand_name}")
                    else:
                        self.dealer_label.config(text="庄家")
                except Exception:
                    try:
                        self.dealer_label.config(text="庄家")
                    except Exception:
                        pass
            self.after(500, update_dealer_label_later)
        except Exception:
            pass

        # 获取庄家区的标签列表（只取包含 card 属性的标签）
        dealer_labels = [lbl for lbl in self.dealer_cards_frame.winfo_children() if hasattr(lbl, 'card')]

        # 记录每个庄家标签的起始 x（有 place_info 则用 place x，否则用 winfo_x）
        start_positions = {}
        for label in dealer_labels:
            if not label.winfo_exists():
                continue
            try:
                info = label.place_info()
                start_positions[label] = float(info.get('x', label.winfo_x()))
            except Exception:
                try:
                    start_positions[label] = float(label.winfo_x())
                except Exception:
                    start_positions[label] = 0.0

        # 计算目标 x：根据 sorted_dealer 的索引来决定位置
        target_positions = {}
        slot_width = getattr(self, "CARD_SLOT_WIDTH", 110)  # 可配置，回退为 110
        for idx, card in enumerate(sorted_dealer):
            # 找到对应的标签
            placed = False
            for label in dealer_labels:
                if hasattr(label, 'card') and label.card == card:
                    target_positions[label] = idx * slot_width
                    placed = True
                    break
            if not placed:
                # 如果没有找到对应标签（极端情况），不设置目标，根据现状保持
                pass

        # 为所有有 start_position 且有 target 的标签构建动画数据
        anim_data = []
        steps = 30
        duration = 1200
        try:
            interval = max(1, duration // steps)
        except Exception:
            interval = 40

        for label, start_x in start_positions.items():
            if label in target_positions:
                target_x = target_positions[label]
                dx = (target_x - start_x) / steps
                anim_data.append((label, start_x, dx))

        # 如果没有需要动画的标签，则直接完成（刷新标签并调用后续）
        if not anim_data:
            try:
                self.update_hand_labels()
            except Exception:
                pass
            if getattr(self.game, 'folded', False):
                try:
                    self.settle_fold()
                except Exception:
                    pass
            else:
                try:
                    self.after_dealer_sort()
                except Exception:
                    pass
            return

        # 执行动画
        def animate_step(step):
            if step > steps or getattr(self, "_resetting", False):
                # 最终定位到目标位置
                for lbl, _, _ in anim_data:
                    if lbl.winfo_exists() and lbl in target_positions:
                        try:
                            lbl.place(x=target_positions[lbl])
                        except Exception:
                            pass
                # 更新显示并触发后续逻辑
                try:
                    self.update_hand_labels()
                except Exception:
                    pass
                if getattr(self.game, 'folded', False):
                    try:
                        self.settle_fold()
                    except Exception:
                        pass
                else:
                    try:
                        self.after_dealer_sort()
                    except Exception:
                        pass
                return

            # 每一步平滑移动
            for lbl, start_x, dx in anim_data:
                if lbl.winfo_exists():
                    try:
                        new_x = start_x + dx * step
                        lbl.place(x=new_x)
                    except Exception:
                        pass
            # 下一步
            try:
                self.after(interval, lambda: animate_step(step + 1))
            except Exception:
                # 如果 after 出错，直接跳到结束处理
                animate_step(steps + 1)

        # 启动动画第一步
        animate_step(1)

    def after_dealer_sort(self):
        """庄家排序后，先检查庄家是否合格，如果不合格则显示选项，否则继续结算"""
        if self.game.dealer_qualifies():
            # 合格，正常结算超级红利和摊牌
            self.settle_super_bonus()
            self.settle_showdown()
        else:
            # 不合格，显示选项
            self.show_dealer_exchange_options()

    def show_dealer_exchange_options(self):
        """显示庄家不及格时的选项：为庄家换牌或直接结算"""
        # 清空 action_frame 中的按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        self.status_label.config(text="庄家不合格，选择为庄家更换一张手牌吗？")
        btn_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        btn_frame.pack(pady=5)

        # 为庄家换牌按钮
        self.dealer_exchange_btn = tk.Button(
            btn_frame, text="为庄家换牌", 
            command=self.dealer_exchange_action,
            font=('Arial', 14), bg='#FF9800', fg='white', width=12
        )
        self.dealer_exchange_btn.pack(side=tk.LEFT, padx=5)

        # 直接结算按钮
        self.skip_exchange_btn = tk.Button(
            btn_frame, text="不，直接结算",
            command=self.skip_dealer_exchange,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=12
        )
        self.skip_exchange_btn.pack(side=tk.LEFT, padx=5)

    def skip_dealer_exchange(self):
        """跳过换牌，直接按原规则结算（庄家不合格）"""
        # 先结算超级红利
        self.settle_super_bonus()
        # 然后调用 settle_showdown，它会根据 dealer_qualifies() 处理不合格情况
        self.settle_showdown()

    def dealer_exchange_action(self):
        """为庄家换一张最低价值的牌，支付底注"""
        cost = self.game.ante
        if self.balance < cost:
            messagebox.showerror("错误", "余额不足支付为庄家换牌的费用")
            return

        # 扣款
        self.balance -= cost
        self.update_balance()

        # 将费用记录到 dealer_exchange_cost 并累加到 buy_exchange_bet（或单独处理）
        self.game.dealer_exchange_cost = cost
        # 累加或设置“换/加牌”格子
        current_exchange = float(self.exchange_var.get())
        new_exchange = current_exchange + cost
        self.exchange_var.set(str(int(new_exchange)))
        # 将格子背景设为浅灰色（表示已支付）
        self.exchange_display.config(bg='light grey', fg='black')

        # 更新本局下注总额
        total_bet = (self.game.ante + self.game.super_bet + 
                    self.game.raise_bet + self.game.buy_exchange_bet + cost)
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        # 禁用按钮
        self.dealer_exchange_btn.config(state=tk.DISABLED)
        self.skip_exchange_btn.config(state=tk.DISABLED)

        # 找到庄家手牌中最低价值的牌
        dealer_hand = self.game.dealer_hand
        min_card = min(dealer_hand, key=lambda c: c.value)
        min_index = dealer_hand.index(min_card)

        # 找到对应的标签
        dealer_labels = list(self.dealer_cards_frame.winfo_children())
        dealer_labels.sort(key=lambda lbl: lbl.winfo_x())
        target_label = dealer_labels[min_index]

        # 执行动画
        self.animate_dealer_card_exchange(target_label, min_index)

    def animate_dealer_card_exchange(self, old_label, idx):
        """动画：旧牌缩放消失，新牌缩放出现"""
        # 获取旧牌的位置和尺寸
        try:
            x = int(old_label.place_info().get('x', old_label.winfo_x()))
            y = int(old_label.place_info().get('y', old_label.winfo_y()))
            w = int(old_label.place_info().get('width', old_label.winfo_width()))
            h = int(old_label.place_info().get('height', old_label.winfo_height()))
        except:
            x, y = old_label.winfo_x(), old_label.winfo_y()
            w, h = old_label.winfo_width(), old_label.winfo_height()

        # 从 active_card_labels 中移除旧标签（如果存在）
        if old_label in self.active_card_labels:
            self.active_card_labels.remove(old_label)

        # 缩放消失动画参数
        steps = 20
        duration = 800
        interval = max(1, duration // steps)

        def shrink_step(step):
            if step > steps:
                # 销毁旧标签
                old_label.destroy()
                # 发新牌
                new_card = self.game.deck.deal(1)[0]
                # 替换 dealer_hand 中对应索引的牌
                self.game.dealer_hand[idx] = new_card
                # 创建新标签（正面）
                img = self.card_images.get((new_card.suit, new_card.rank), self.back_image)
                new_label = tk.Label(self.dealer_cards_frame, image=img, bg=self.dealer_cards_frame['bg'])
                new_label.card = new_card
                new_label.is_face_up = True
                # 初始放在中心，大小为1x1
                new_label.place(x=x + w//2, y=y + h//2, width=1, height=1)
                # 缩放出现动画
                self.expand_dealer_card(new_label, x, y, w, h, idx)
                return

            scale = 1.0 - (step / steps)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            new_x = x + (w - new_w) // 2
            new_y = y + (h - new_h) // 2
            try:
                old_label.place_configure(x=new_x, y=new_y, width=new_w, height=new_h)
            except:
                pass
            self.after(interval, lambda: shrink_step(step+1))

        shrink_step(1)

    def expand_dealer_card(self, label, target_x, target_y, target_w, target_h, idx):
        """新牌从中心放大到目标位置"""
        steps = 20
        duration = 800
        interval = max(1, duration // steps)

        def expand_step(step):
            if step > steps:
                # 最终位置
                label.place_configure(x=target_x, y=target_y, width=target_w, height=target_h)
                # 将新牌加入 active_card_labels 以便后续收集
                if label not in self.active_card_labels:
                    self.active_card_labels.append(label)
                # 记录到 moved_cards 用于向上移动动画（如果有）
                try:
                    cur_y = int(label.place_info().get('y', label.winfo_y()))
                except:
                    cur_y = label.winfo_y()
                self.moved_cards.append((label, cur_y))
                # 换牌完成后，重新排序庄家手牌并结算
                self.sort_dealer_hand_after_exchange()
                return

            scale = step / steps
            new_w = max(1, int(target_w * scale))
            new_h = max(1, int(target_h * scale))
            new_x = target_x + (target_w - new_w) // 2
            new_y = target_y + (target_h - new_h) // 2
            label.place_configure(x=new_x, y=new_y, width=new_w, height=new_h)
            self.after(interval, lambda: expand_step(step+1))

        expand_step(1)

    def sort_dealer_hand_after_exchange(self):
        """换牌后对庄家手牌进行排序动画，完成后调用结算"""
        # 强制刷新UI，确保所有标签位置信息是最新的
        self.dealer_cards_frame.update_idletasks()

        # 计算排序后的庄家手牌
        try:
            dealer_eval = evaluate_five_card_hand(self.game.dealer_hand)
            sorted_dealer = sort_hand_for_display(self.game.dealer_hand, dealer_eval)
        except:
            sorted_dealer = list(self.game.dealer_hand)

        # 更新内部手牌
        self.game.dealer_hand = sorted_dealer

        # 获取庄家标签（必须包含新换的牌）
        dealer_labels = [lbl for lbl in self.dealer_cards_frame.winfo_children() if hasattr(lbl, 'card')]
        if not dealer_labels:
            return

        # 记录起始 x（统一使用 winfo_x 确保准确性）
        start_positions = {}
        for lbl in dealer_labels:
            try:
                sx = lbl.winfo_x()
            except:
                sx = 0
            start_positions[lbl] = sx

        # 目标 x（使用与玩家牌一致的槽宽）
        slot_width = getattr(self, "CARD_SLOT_WIDTH", 110)
        target_positions = {}
        for idx, card in enumerate(sorted_dealer):
            for lbl in dealer_labels:
                if hasattr(lbl, 'card') and lbl.card == card:
                    target_positions[lbl] = idx * slot_width
                    break

        # 动画参数
        duration = 1000
        steps = 15
        interval = max(1, duration // steps)

        anim_data = []
        for lbl in dealer_labels:
            if lbl in target_positions:
                dx = (target_positions[lbl] - start_positions[lbl]) / steps
                anim_data.append((lbl, start_positions[lbl], dx))

        def animate_step(step):
            if step > steps or self._resetting:
                for lbl, _, _ in anim_data:
                    if lbl.winfo_exists():
                        lbl.place(x=target_positions[lbl], y=0)
                # 更新庄家标签牌型
                try:
                    dealer_hand_name = self.get_hand_name(self.game.dealer_hand)
                    self.dealer_label.config(text=f"庄家 - {dealer_hand_name}")
                except:
                    pass
                self.settle_after_dealer_exchange()
                return

            for lbl, start_x, dx in anim_data:
                if lbl.winfo_exists():
                    new_x = start_x + dx * step
                    lbl.place(x=new_x)
            self.after(interval, lambda: animate_step(step + 1))

        animate_step(1)

    def settle_after_dealer_exchange(self):
        """庄家换牌后的结算"""
        # 先结算超级红利（基于新庄家手牌）
        self.settle_super_bonus()

        # 判断新庄家是否合格
        dealer_qual = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)

        # 初始化输赢变量
        ante_win = 0
        raise_win = 0

        if not dealer_qual:
            # 交换后仍然不合格：底注Push，加注1:1
            ante_win = self.game.ante*2.5  # 退还3:2底注
            raise_win = self.game.raise_bet  # 加注Push
        else:
            # 庄家合格，根据比较结果
            if comparison > 0:  # 玩家赢
                ante_win = self.game.ante  # 底注退还
                player_rank, _ = evaluate_best_hand(self.game.player_hand)
                payout = RAISE_PAYOUT.get(player_rank, 1)
                raise_win = self.game.raise_bet * (payout + 1)  # 加注按玩家牌型赔付
            elif comparison == 0:  # 平局
                # 检查是否有买入
                if getattr(self.game, 'buy_used', False):
                    # 有买入，按玩家赢处理
                    ante_win = self.game.ante
                    player_rank, _ = evaluate_best_hand(self.game.player_hand)
                    payout = RAISE_PAYOUT.get(player_rank, 1)
                    raise_win = self.game.raise_bet * (payout + 1)
                else:
                    # 无买入，底注Push，加注Push
                    ante_win = self.game.ante
                    raise_win = self.game.raise_bet
            else:  # 玩家输
                # 底注1:1获胜，加注输
                ante_win = self.game.ante * 1.5   # 底注净赢 = 底注，总返还 = 底注*1.5
                raise_win = 0

        # 总赢利
        total_win = ante_win + raise_win
        self.balance += total_win
        self.update_balance()

        # 更新显示
        self.ante_var.set(str(int(ante_win)))
        self.raise_var.set(str(int(raise_win)))

        # 设置背景色
        if ante_win > self.game.ante:
            self.ante_display.config(bg='gold')
        elif ante_win == self.game.ante and self.game.ante > 0:
            self.ante_display.config(bg='light blue')
        else:
            self.ante_display.config(bg='white')

        if raise_win > self.game.raise_bet:
            self.raise_display.config(bg='gold')
        elif raise_win == self.game.raise_bet and self.game.raise_bet > 0:
            self.raise_display.config(bg='light blue')
        else:
            self.raise_display.config(bg='white')

        # 更新上局获胜
        self.last_win = total_win
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")

        # 显示状态
        if not dealer_qual:
            status = "庄家换牌后仍不合格，底注3:2获胜，加注平局"
        else:
            if comparison > 0:
                status = "庄家交换后，您赢了"
            elif comparison == 0:
                if getattr(self.game, 'buy_used', False):
                    status = "平局（因有买入，您获胜）"
                else:
                    status = "平局"
            else:
                status = "庄家交换后，您输了。底注以1:2结算"
        self.status_label.config(text=status)

        # 显示重新开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        self.restart_btn = tk.Button(
            self.action_frame, text="再来一局",
            command=self.reset_game,
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        self.restart_btn.pack(pady=5)
        self.restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def settle_fold(self):
        """弃牌后的结算（先处理超级红利）"""
        # 先结算超级红利（比较玩家原始手牌与庄家手牌）
        try:
            self.settle_super_bonus()
        except Exception:
            pass

        # 弃牌时底注已输，显示底注为 0；换/加牌也应保持其当前显示或清为 0（这里设为 0）
        try:
            self.ante_var.set("0")
        except Exception:
            pass
        try:
            self.exchange_var.set("0")
        except Exception:
            pass
        try:
            self.raise_var.set("0")
        except Exception:
            pass

        # 恢复下注显示背景为白
        try:
            self.ante_display.config(bg='white')
            self.exchange_display.config(bg='white')
            self.raise_display.config(bg='white')
        except Exception:
            pass

        # ===== 移除覆盖 last_win 的语句，保留已在 settle_super_bonus 中累加的值 =====
        # self.last_win = total_win   # 原代码会清零，已删除

        # 更新上局获胜标签（last_win 已在 settle_super_bonus 中累加）
        try:
            self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
        except Exception:
            pass

        # ===== 新增：更新 current_bet_label 显示总返还 =====
        try:
            total_return = (float(self.ante_var.get()) +
                            float(self.exchange_var.get()) +
                            float(self.raise_var.get()) +
                            float(self.super_bet_var.get()))
            self.current_bet_label.config(text=f"本局下注: ${total_return:.2f}")
        except Exception:
            pass
        # =================================================

        # 显示重新开始按钮（替换 action_frame 内部按钮）
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        self.restart_btn = tk.Button(
            self.action_frame, text="再来一局",
            command=self.reset_game,
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        self.restart_btn.pack(pady=5)
        try:
            self.restart_btn.bind("<Button-3>", self.show_card_sequence)
        except Exception:
            pass

        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def settle_showdown(self):
        """最终摊牌结算（先处理超级红利，再计算底注和加注）"""
        # 超级红利已在 after_dealer_sort 或 settle_fold 中处理，这里无需重复
        winnings, details = self.calculate_winnings()
        self.last_win += winnings
        self.balance += winnings
        self.update_balance()

        # 更新显示
        self.ante_var.set(str(int(details["ante"])))
        self.raise_var.set(str(int(details["raise"])))

        # 设置背景色
        for bet_type, widget in self.bet_widgets.items():
            if bet_type == "ante":
                win_amt = details["ante"]
                if win_amt > self.game.ante:
                    widget.config(bg='gold')
                elif win_amt == self.game.ante and self.game.ante > 0:
                    widget.config(bg='light blue')
                else:
                    widget.config(bg='white')
            elif bet_type == "raise":
                win_amt = details["raise"]
                if win_amt > self.game.raise_bet:
                    widget.config(bg='gold')
                elif win_amt == self.game.raise_bet and self.game.raise_bet > 0:
                    widget.config(bg='light blue')
                else:
                    widget.config(bg='white')
            elif bet_type == "super_bet":
                # 超级红利格子已在 settle_super_bonus 中更新
                pass

        dealer_qualifies = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)

        if not dealer_qualifies:
            status = "庄家不合格，底注获胜，加注退还"
        else:
            if comparison > 0:
                status = "本局您赢了"
            elif comparison < 0:
                status = "本局您输了"
            else:
                status = "本局Push"

        self.status_label.config(text=status)
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")

        # 显示重新开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        self.restart_btn = tk.Button(
            self.action_frame, text="再来一局",
            command=self.reset_game,
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        self.restart_btn.pack(pady=5)
        self.restart_btn.bind("<Button-3>", self.show_card_sequence)

        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def calculate_winnings(self):
        """计算底注和加注的赢钱（不含超级红利）"""
        winnings = 0
        details = {"ante": 0, "raise": 0, "super_bonus": 0}

        dealer_qualifies = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)

        if not dealer_qualifies:
            # 底注1:1，加注退还
            details["ante"] = self.game.ante * 2
            details["raise"] = self.game.raise_bet
        else:
            if comparison > 0:  # 玩家赢
                details["ante"] = self.game.ante  # 退还
                player_rank, _ = evaluate_best_hand(self.game.player_hand)
                payout = RAISE_PAYOUT.get(player_rank, 1)
                details["raise"] = self.game.raise_bet * (payout + 1)
            elif comparison == 0:  # 平局
                details["ante"] = self.game.ante
                details["raise"] = self.game.raise_bet
            else:  # 玩家输
                details["ante"] = 0
                details["raise"] = 0

        winnings = details["ante"] + details["raise"]
        return winnings, details

    def settle_super_bonus(self):
        """结算超级红利：仅根据玩家原始5张手牌评估并支付一次。
        - 无赔付：超级注格子显示为 "0"
        - 有赔付：格子显示为 总返还（原注 + 净赢），例如下注 10、2:1 => 净赢 20，总返还 30；格子变金色
        """
        if self.game.super_paid or getattr(self.game, "super_bet", 0) == 0:
            return  # 已支付或没有下注

        player_hand = self.game.player_original_hand  # 原始5张

        player_name, player_mult = evaluate_super_bonus(player_hand)

        if player_mult > 0:
            # 计算支付：净赢 = 下注 * mult，总返还 = 下注 * (mult + 1)
            total_return = int(self.game.super_bet * (player_mult + 1))

            # 给玩家发放总返还（包含本金）
            self.balance += total_return
            self.update_balance()

            self.win_details["super_bonus"] = total_return
            self.last_win += total_return

            # 更新超级红利格子显示：显示总返还（整数显示），并设置金色背景
            try:
                self.super_bet_var.set(str(int(total_return)))
                self.super_bet_display.config(bg='gold', fg='black')
            except Exception:
                pass

            self.game.super_paid = True
        else:
            # 无赔付：格子显示 0，背景恢复白色
            try:
                self.super_bet_var.set("0")
                self.super_bet_display.config(bg='white', fg='black')
            except Exception:
                pass

    # ==================== 游戏流程核心方法 ====================
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.super_bet = int(self.super_bet_var.get())

            if self.ante < 10:
                messagebox.showerror("错误", "底注至少需要10块")
                return
            if self.ante > 10000:
                self.ante = 10000
                self.ante_var.set("10000")
                messagebox.showwarning("下注限制", "底注上限为10000，已自动调整")

            if self.super_bet > 10000:
                self.super_bet = 10000
                self.super_bet_var.set("10000")
                messagebox.showwarning("下注限制", "超级红利上限为10000，已自动调整")

            if self.super_bet > self.ante:
                messagebox.showerror("错误", "超级赌注金额必须小于或等于底注")
                return

            required_for_raise = self.ante * 2
            if self.balance < self.ante + self.super_bet + required_for_raise:
                messagebox.showerror("错误", "余额不足以支付所有下注！")
                return

            self.balance -= (self.ante + self.super_bet)
            self.update_balance()
            self.last_win = 0

            self.current_bet_label.config(text=f"本局下注: ${self.ante + self.super_bet:.2f}")
            self.last_win_label.config(text="上局获胜: $0.00")

            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.super_bet = self.super_bet

            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()

            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            self.moved_cards = []
            self.ak_moved = False
            self.ak_animation_active = False
            self.fold_mode = False
            self.selected_cards_for_exchange = []

            for i in range(5):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {"current": (50, 50), "target": (i * 110, 0)}
                self.animation_queue.append(card_id)
            for i in range(5):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {"current": (50, 50), "target": (i * 110, 0)}
                self.animation_queue.append(card_id)

            for widget in self.action_frame.winfo_children():
                widget.destroy()

            self.stage_label.config(text="派牌")
            self.status_label.config(text="发牌中...")

            self.ante_display.unbind("<Button-1>")
            self.super_bet_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")

            self.animate_deal()

        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return

        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)

        if card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hand[idx]
        else:
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hand[idx]

        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(
            x=self.card_positions[card_id]["current"][0],
            y=self.card_positions[card_id]["current"][1] + 20,
            width=120, height=180
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
                card_label.place(x=target_x, y=target_y, width=120, height=180)
                card_label.is_moving = False
                self.after(100, self.animate_deal)
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

    def reveal_player_cards(self):
        """翻开玩家牌，翻开庄家第一张"""
        self.reveal_dealer_first_card()

        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                card_label.place(width=110, height=180)
                self.flip_card_animation(card_label)
                self.game.cards_revealed["player"][i] = True

        self.update_hand_labels()
        self.after(1000, self.after_player_cards_revealed)

    def reveal_dealer_first_card(self):
        dealer_cards = self.dealer_cards_frame.winfo_children()
        if dealer_cards:
            first_card = dealer_cards[0]
            if hasattr(first_card, "card") and not first_card.is_face_up:
                self.animation_in_progress = True
                self.flip_card_animation(first_card)

    def flip_card_animation(self, card_label):
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.animate_flip(card_label, front_img, 0)

    def animate_flip(self, card_label, front_img, step):
        steps = 10
        if step > steps:
            card_label.config(image=front_img)
            card_label.is_face_up = True
            self.animation_in_progress = False
            card_label.place(width=120, height=180)
            return

        if step <= steps / 2:
            width = 120 - (step * 12)
            if width <= 0:
                width = 1
            card_label.config(image=self.back_image)
        else:
            width = (step - steps / 2) * 12
            if width <= 0:
                width = 1
            card_label.config(image=front_img)

        card_label.place(width=width, height=180)
        step += 1
        self.after(50, lambda: self.animate_flip(card_label, front_img, step))

    def after_player_cards_revealed(self):
        """玩家牌翻开后的处理：先排序，然后检查立即支付（同花顺/皇家同花顺）"""
        if self._resetting:
            return

        self.sort_player_hand_after_reveal()
    
    def sort_player_hand_after_exchange(self):
        """
        换牌后的排序动画（与 sort_player_hand_after_reveal 类似）。
        动画结束后：
        1) 检查即时赔付（check_instant_payout）
        2) 更新玩家牌型显示（self.player_label）
        3) 直接进入 after_buy_exchange_decision()
        """
        # 保护标志：如果正在重置则不运行
        if getattr(self, "_resetting", False):
            return

        try:
            player_eval = evaluate_five_card_hand(self.game.player_hand)
            sorted_hand = sort_hand_for_display(self.game.player_hand, player_eval)
        except Exception:
            sorted_hand = list(self.game.player_hand)

        player_labels = list(self.player_cards_frame.winfo_children())

        # 记录起始 x 坐标
        start_positions = {}
        for label in player_labels:
            if label.winfo_exists():
                try:
                    info = label.place_info()
                    start_positions[label] = float(info.get('x', label.winfo_x()))
                except Exception:
                    start_positions[label] = float(label.winfo_x())

        # 计算目标 x（与其他排序函数一致： idx * 110）
        target_positions = {}
        for idx, card in enumerate(sorted_hand):
            for label in player_labels:
                if hasattr(label, 'card') and label.card == card:
                    target_positions[label] = idx * 110
                    break

        # 若某些 label 没找到对应目标（极少见），把目标设为当前 x
        for label in start_positions:
            if label not in target_positions:
                target_positions[label] = start_positions.get(label, 0.0)

        duration = 1000
        steps = 15
        interval = max(1, duration // steps)

        anim_data = []
        for label, start_x in start_positions.items():
            dx = (target_positions[label] - start_x) / steps
            anim_data.append((label, start_x, dx))

        def animate_step(step):
            if step > steps or getattr(self, "_resetting", False):
                # 定位到最终位置
                for label, start_x, _ in anim_data:
                    if label.winfo_exists():
                        try:
                            label.place(x=target_positions[label])
                        except Exception:
                            pass
                # 更新内部手牌顺序
                try:
                    self.game.player_hand = sorted_hand
                except Exception:
                    pass

                # 先检查即时赔付（若有）
                try:
                    self.check_instant_payout()
                except Exception:
                    pass

                # 更新玩家牌型显示（用你现有的 helper）
                try:
                    player_hand_name = self.get_hand_name_best(self.game.player_hand)
                    self.player_label.config(text=f"玩家 - {player_hand_name}")
                except Exception:
                    try:
                        self.player_label.config(text="玩家")
                    except Exception:
                        pass

                # 排序完成后，直接进入买入/换牌后的二次决策
                try:
                    self.after_buy_exchange_decision()
                except Exception:
                    # 兜底：若调用失败，展示决策按钮（after_buy=True）
                    try:
                        self.show_decision_buttons(after_buy=True)
                    except Exception:
                        pass
                return

            # 每一步线性插值移动
            for label, start_x, dx in anim_data:
                if label.winfo_exists():
                    try:
                        new_x = start_x + dx * step
                        label.place(x=new_x)
                    except Exception:
                        pass

            self.after(interval, lambda: animate_step(step + 1))

        animate_step(1)

    def sort_player_hand_after_reveal(self):
        """玩家手牌排序动画"""
        player_eval = evaluate_five_card_hand(self.game.player_hand)
        sorted_hand = sort_hand_for_display(self.game.player_hand, player_eval)

        player_labels = list(self.player_cards_frame.winfo_children())

        start_positions = {}
        for label in player_labels:
            if label.winfo_exists():
                info = label.place_info()
                start_positions[label] = float(info['x'])

        target_positions = {}
        for idx, card in enumerate(sorted_hand):
            for label in player_labels:
                if hasattr(label, 'card') and label.card == card:
                    target_positions[label] = idx * 110
                    break

        duration = 1000
        steps = 15
        interval = duration // steps

        anim_data = [(label, start_positions[label], (target_positions[label] - start_positions[label]) / steps)
                     for label in start_positions]

        def animate_step(step):
            if step > steps or self._resetting:
                for label, start_x, _ in anim_data:
                    if label.winfo_exists():
                        label.place(x=target_positions[label])
                self.game.player_hand = sorted_hand
                self.after(200, self.check_instant_payout)
                return
            for label, start_x, dx in anim_data:
                if label.winfo_exists():
                    new_x = start_x + dx * step
                    label.place(x=new_x)
            self.after(interval, lambda: animate_step(step + 1))

        animate_step(1)

    def check_instant_payout(self):
        player_rank, _ = evaluate_five_card_hand(self.game.player_hand)
        if player_rank in [8, 9]:
            payout = INSTANT_PAYOUT.get(player_rank, 0)
            ante_win = self.game.ante * payout
            self.balance += ante_win
            self.update_balance()
            self.ante_display.config(bg='gold')
            hand_name = HAND_RANK_NAMES[player_rank]
            messagebox.showinfo("立即支付！", f"牌型: {hand_name}\n底注赢得 ${ante_win:.2f}")
            # ===== 新增：记录并显示上局获胜 =====
            self.last_win = ante_win
            self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
            # =================================
            self.game.instant_payout_done = True
            self.game.stage = "showdown"
            self.stage_label.config(text="游戏结束")
            self.status_label.config(text="立即支付，游戏结束")
            self.show_restart_button()
            return
        self.show_decision_buttons()

    def show_decision_buttons(self, after_buy=False):
        """显示决策按钮"""
        self.game.stage = "decision"
        self.stage_label.config(text="决策")
        if after_buy:
            self.status_label.config(text="买入后：请选择 弃牌 或 下注2X")

        for widget in self.action_frame.winfo_children():
            widget.destroy()

        btn_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        btn_frame.pack(pady=5)

        self.fold_button = tk.Button(btn_frame, text="弃牌", command=self.fold_action,
                                    font=('Arial', 14), bg='#F44336', fg='white', width=8)
        self.fold_button.pack(side=tk.LEFT, padx=2)

        self.play_button = tk.Button(btn_frame, text="下注2X", command=self.play_action,
                                    font=('Arial', 14), bg='#4CAF50', fg='white', width=8)
        self.play_button.pack(side=tk.LEFT, padx=2)

        if self.balance >= 4 * self.game.ante:
            if not after_buy:
                self.status_label.config(text="选择: 弃牌 / 下注2X / 买入 / 换牌")
                self.buy_button = tk.Button(btn_frame, text="买入", command=self.buy_action,
                                            font=('Arial', 14), bg='#FF9800', fg='white', width=8)
                self.buy_button.pack(side=tk.LEFT, padx=2)

                self.exchange_button = tk.Button(btn_frame, text="换牌", command=self.exchange_action,
                                                font=('Arial', 14), bg='#9C27B0', fg='white', width=8)
                self.exchange_button.pack(side=tk.LEFT, padx=2)
            else:
                self.buy_button = None
                self.exchange_button = None
        else:
            self.status_label.config(text="选择: 弃牌 / 下注2X")

    def fold_action(self):
        """玩家弃牌"""
        self.game.folded = True
        self.fold_mode = True
        self.status_label.config(text="您已弃牌")

        for btn in [self.fold_button, self.play_button, self.buy_button, self.exchange_button]:
            if btn:
                btn.config(state=tk.DISABLED)

        self.reveal_dealer_cards()

    def play_action(self):
        raise_amount = self.game.ante * 2
        if self.balance < raise_amount:
            messagebox.showerror("错误", "余额不足")
            return

        self.balance -= raise_amount
        self.update_balance()
        self.game.raise_bet = raise_amount
        self.raise_var.set(str(raise_amount))

        total = self.game.ante + self.game.super_bet + raise_amount + self.game.buy_exchange_bet
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")

        # 禁用按钮前检查有效性
        for btn in [self.fold_button, self.play_button, self.buy_button, self.exchange_button]:
            if btn and btn.winfo_exists():
                btn.config(state=tk.DISABLED)

        self.game.stage = "showdown"
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.reveal_dealer_cards)

    # ---------- 修改：buy_action（加入复位选中，动画改进）----------
    def buy_action(self):
        """买入一张牌（完整动画流程）"""
        if getattr(self.game, "buy_used", False):
            messagebox.showinfo("提示", "买入仅可使用一次")
            return

        # 复位可能的选中牌视觉状态，确保所有牌 y=0
        try:
            self._reset_selected_and_visuals()
        except Exception:
            pass
        for lbl in self.player_cards_frame.winfo_children():
            lbl.place_configure(y=0)

        buy_cost = self.game.ante
        if self.balance < buy_cost:
            messagebox.showerror("错误", "余额不足支付买入")
            return
        
        for btn in [self.fold_button, self.play_button, self.buy_button, self.exchange_button]:
            if btn and btn.winfo_exists():
                btn.config(state=tk.DISABLED)

        # 扣款并记录买入注
        self.balance -= buy_cost
        self.update_balance()
        self.game.buy_exchange_bet = buy_cost
        self.game.buy_used = True
        try:
            self.exchange_var.set(str(int(self.game.ante)))
            self.exchange_display.config(bg='light grey', fg='black')
        except Exception:
            pass

        # 更新本局下注总额显示
        total_bet = self.game.ante + self.game.super_bet + self.game.buy_exchange_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        # 获取当前玩家手牌标签（5张），按当前 x 排序（左到右）
        player_labels = list(self.player_cards_frame.winfo_children())
        player_labels = [lbl for lbl in player_labels if hasattr(lbl, 'card')]
        player_labels.sort(key=lambda lbl: lbl.winfo_x())

        if len(player_labels) != 5:
            return

        # 记录起始 x 坐标
        start_xs = []
        for lbl in player_labels:
            try:
                sx = float(lbl.place_info().get('x', lbl.winfo_x()))
            except:
                sx = lbl.winfo_x()
            start_xs.append(sx)

        # 移动前按起始 x 从小到大（左→右）提升图层，确保最右边最后 lift，从而在最上层
        sorted_by_x_asc = sorted(zip(start_xs, player_labels), key=lambda x: x[0])
        for _, lbl in sorted_by_x_asc:
            lbl.lift()

        # 目标 x 偏移量：第 i 张牌左移 shift[i] 像素
        shifts = [0, 30, 60, 90, 120]
        target_xs = [start_xs[i] - shifts[i] for i in range(5)]

        duration = 1750
        steps = 45
        interval = max(1, duration // steps)
        deltas = [(target_xs[i] - start_xs[i]) / steps for i in range(5)]

        CARD_WIDTH = getattr(self, "CARD_WIDTH", 100)
        CARD_HEIGHT = int(CARD_WIDTH * 1.8)
        TARGET_Y = 0  # 固定 y

        def move_step(step):
            if step > steps:
                # 最终位置，固定 y=0，设置统一尺寸
                for i, lbl in enumerate(player_labels):
                    if lbl.winfo_exists():
                        lbl.place(x=target_xs[i], y=TARGET_Y,
                                width=CARD_WIDTH, height=CARD_HEIGHT)
                # 移动完成后添加新牌（在原第5张牌的原始位置）
                self._add_new_card_after_buy_move(player_labels, start_xs)
                return

            for i, lbl in enumerate(player_labels):
                if not lbl.winfo_exists():
                    continue
                new_x = start_xs[i] + deltas[i] * step
                lbl.place(x=new_x, y=TARGET_Y, width=CARD_WIDTH, height=CARD_HEIGHT)

            self.after(interval, lambda: move_step(step + 1))

        move_step(1)

    def _add_new_card_after_buy_move(self, player_labels, start_xs):
        """移动完成后添加新牌（背面）并翻牌"""
        new_card = self.game.deck.deal(1)[0]
        new_x = start_xs[4]  # 原第5张牌的起始 x 坐标

        CARD_WIDTH = getattr(self, "CARD_WIDTH", 100)

        back_img = self.back_image
        new_label = tk.Label(self.player_cards_frame, image=back_img, bg=self.player_cards_frame['bg'])
        new_label.place(x=new_x, y=0, width=CARD_WIDTH, height=int(CARD_WIDTH * 1.8))
        new_label.card = new_card
        new_label.is_face_up = False
        new_label.lift()

        self.game.player_hand.append(new_card)
        self.active_card_labels.append(new_label)

        front_img = self.card_images.get((new_card.suit, new_card.rank), self.back_image)
        self.animate_flip(new_label, front_img, 0)

        self.after(600, self._sort_after_buy)

    def _sort_after_buy(self):
        """翻牌后对6张牌进行排序动画，最终位置第一张 x=LEFT_MARGIN，后续按 CARD_SLOT_WIDTH 排列（允许重叠）。"""
        if len(self.game.player_hand) != 6:
            return

        # 收集牌的 label（只取有 .card 属性的）
        labels = list(self.player_cards_frame.winfo_children())
        labels = [lbl for lbl in labels if hasattr(lbl, 'card')]
        # 以当前 x 排序，保证动画从视觉上平滑开始
        labels.sort(key=lambda lbl: lbl.winfo_x())

        # 计算最优牌型并对手牌排序（使用你已有的排序函数）
        best_rank, _ = evaluate_best_hand(self.game.player_hand)
        sorted_hand = self.sort_hand_by_rank(self.game.player_hand, best_rank)

        # 支持两种命名的宽度属性（兼容你现有代码）
        display_width = getattr(self, "CARD_DISPLAY_WIDTH", None)
        if display_width is None:
            display_width = getattr(self, "CARD_WIDTH", 100)
        overlap = getattr(self, "CARD_OVERLAP", 20)  # 每张牌与前一张重叠的像素（可调整）
        CARD_SLOT_WIDTH = max(1, int(display_width - overlap))
        LEFT_MARGIN = getattr(self, "CARD_LEFT_MARGIN", 10)

        # 目标 x 列表（6 张牌）
        target_xs = [LEFT_MARGIN + i * CARD_SLOT_WIDTH for i in range(6)]

        # 将排序后的牌与对应的 label 进行映射，得到每个 label 的目标 x
        target_positions = {}
        for idx, card in enumerate(sorted_hand):
            for lbl in labels:
                if hasattr(lbl, 'card') and lbl.card == card:
                    target_positions[lbl] = target_xs[idx]
                    break

        # 读取起始 x（尝试从 place_info 读取，否则用 winfo_x）
        start_positions = {}
        for lbl in labels:
            try:
                sx = float(lbl.place_info().get('x', lbl.winfo_x()))
            except Exception:
                sx = lbl.winfo_x()
            start_positions[lbl] = sx

        # 动画参数
        duration = 1000  # 总时长 ms
        steps = 20
        interval = max(1, duration // steps)

        # 仅对那些有目标位置的 label 做动画
        anim_data = [
            (lbl, start_positions[lbl], (target_positions[lbl] - start_positions[lbl]) / steps)
            for lbl in labels if lbl in target_positions
        ]

        def animate_step(step):
            # 结束或重置情况：把所有牌直接放到目标位置，修正宽高，并更新状态
            if step > steps or self._resetting:
                for lbl, _, _ in anim_data:
                    if lbl.winfo_exists():
                        lbl.place(x=int(target_positions[lbl]), y=0,
                                  width=display_width, height=int(display_width * 1.8))
                # 更新玩家手牌数据为排序后的顺序
                self.game.player_hand = sorted_hand

                # —— 关键修改：按目标 x 从小到大（左 -> 右）排序并依次 lift()
                # 这样最左边的牌先被 lift（处于底层），最右边的牌最后被 lift（位于顶层）
                final_labels = sorted(
                    [lbl for lbl in labels if lbl in target_positions],
                    key=lambda lbl: target_positions.get(lbl, 0)
                )
                for lbl in final_labels:
                    try:
                        lbl.lift()
                    except Exception:
                        pass

                player_hand_name = self.get_hand_name_best(self.game.player_hand)
                self.player_label.config(text=f"玩家 - {player_hand_name}")
                self.show_decision_buttons(after_buy=True)
                return

            # 每一步更新位置（线性插值）
            for lbl, start_x, dx in anim_data:
                if lbl.winfo_exists():
                    new_x = start_x + dx * step
                    lbl.place(x=int(new_x))
            # 下一帧
            self.after(interval, lambda: animate_step(step + 1))

        # 启动动画（从 step=1 开始）
        animate_step(1)

    def _lift_cards_by_index(self, labels, ascending=True):
        """调整卡片图层顺序：
            ascending=True  -> 按列表顺序依次 lift，最后 lift 的在上（索引大的在上）
            ascending=False -> 按反序依次 lift，最前面的在上
        """
        if ascending:
            for lbl in labels:
                lbl.lift()
        else:
            for lbl in reversed(labels):
                lbl.lift()

    def get_hand_name(self, hand):
        """根据5张手牌返回中文牌型名称"""
        if not hand or len(hand) < 5:
            return "未知"
        rank, _ = evaluate_five_card_hand(hand)
        name = HAND_RANK_NAMES.get(rank, "未知")
        if rank == 0:
            has_ace = any(c.rank == 'A' for c in hand)
            has_king = any(c.rank == 'K' for c in hand)
            if has_ace and has_king:
                name = "高牌(ACE和KING)"
        return name

    def get_hand_name_best(self, hand):
        """根据最佳5张手牌返回中文牌型名称（用于6张手牌）"""
        if len(hand) < 5:
            return "未知"
        rank, _ = evaluate_best_hand(hand)
        name = HAND_RANK_NAMES.get(rank, "未知")
        if rank == 0:
            has_ace = any(c.rank == 'A' for c in hand)
            has_king = any(c.rank == 'K' for c in hand)
            if has_ace and has_king:
                name = "高牌(ACE和KING)"
        return name

    def sort_hand_by_rank(self, hand, rank):
        """
        根据牌型 rank 对手牌（可能多于5张）进行排序
        参考 sort_hand_for_display 的逻辑
        """
        from collections import Counter
        import itertools

        if len(hand) == 6 and rank in [4, 8, 9]:
            # 先获取最佳5张牌的评价
            best_rank, best_values = evaluate_best_hand(hand)
            # 遍历所有5张组合，找到构成最佳5张的组合
            best_combo = None
            for combo in itertools.combinations(hand, 5):
                r, vals = evaluate_five_card_hand(list(combo))
                if r == best_rank and vals == best_values:
                    best_combo = list(combo)
                    break
            if best_combo is not None:
                # 将最佳5张按点数升序排序
                sorted_best = sorted(best_combo, key=lambda c: c.value)
                # 找出剩余的一张
                extra = [c for c in hand if c not in best_combo]
                if extra:
                    extra_card = extra[0]
                else:
                    # 如果没有剩余（理论上不会发生），回退到升序
                    return sorted(hand, key=lambda c: c.value)
                return sorted_best + [extra_card]
            else:
                # 意外情况，回退到升序
                return sorted(hand, key=lambda c: c.value)

        elif rank in [4, 8, 9]:  # 顺子类（顺子、同花顺、皇家同花顺）
            # 按点数升序，但需处理A-5顺子（这里简化，直接按值排序）
            sorted_hand = sorted(hand, key=lambda c: c.value)
        else:
            # 按频率和点数降序
            counts = Counter(c.value for c in hand)
            sorted_hand = sorted(hand, key=lambda c: (counts[c.value], c.value), reverse=True)
        return sorted_hand

    def _reset_selected_and_visuals(self):
        """把所有被下移的选中牌复位并清空选中列表（使用 15px）"""
        if not hasattr(self, "selected_cards_for_exchange") or not self.selected_cards_for_exchange:
            self.selected_cards_for_exchange = []
            return

        for lbl in list(self.selected_cards_for_exchange):
            if not lbl.winfo_exists():
                continue
            try:
                cur_y = int(lbl.place_info().get('y', lbl.winfo_y()))
            except Exception:
                cur_y = lbl.winfo_y()
            # 选中是下移 +15，上移则 -15
            lbl.place_configure(y=max(0, cur_y - 15))
            lbl.config(bd=0, relief=tk.FLAT)
        self.selected_cards_for_exchange = []

    def exchange_action(self):
        """
        新的换牌入口：
        - 第一次按：进入选择模式（显示 Disabled 的“立刻换牌”和“取消换牌”）
        - 在选择模式下点击牌由 toggle_card_selection 控制
        - 在选择好（2~5）后，按“立刻换牌”触发 perform_exchange_now
        """
        # 如果已经在选择模式，则不重复进入
        if getattr(self, "exchange_selection_active", False):
            return

        self.exchange_selection_active = True
        self._exchange_executing = False
        self.status_label.config(text="点击要换掉的2-5张牌后按立刻换牌")

        # 清空 action_frame 并显示立即换牌（Disabled）与取消按钮
        for widget in self.action_frame.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass

        btn_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        btn_frame.pack(pady=5)

        # 立刻换牌（初始禁用）
        self.immediate_exchange_btn = tk.Button(
            btn_frame, text="立刻换牌", command=self.perform_exchange_now,
            font=('Arial', 14), bg='#9C27B0', fg='white', width=10, state=tk.DISABLED
        )
        self.immediate_exchange_btn.pack(side=tk.LEFT, padx=5)

        # 取消换牌
        def _cancel_exchange_mode():
            try:
                self._reset_selected_and_visuals()
            except Exception:
                pass
            self.exchange_selection_active = False
            # 恢复原先决策按钮（after_buy 由 game.buy_exchange_phase 决定）
            try:
                for widget in self.action_frame.winfo_children():
                    widget.destroy()
            except Exception:
                pass
            self.after(1, lambda: self.show_decision_buttons(after_buy=getattr(self.game, "buy_exchange_phase", False)))

        self.cancel_btn = tk.Button(
            btn_frame, text="取消换牌", command=_cancel_exchange_mode,
            font=('Arial', 14), bg='#777', fg='white', width=10
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

        # 绑定 player_cards_frame 中每张牌点击到 toggle_card_selection（覆盖原绑定）
        try:
            for w in self.player_cards_frame.winfo_children():
                if hasattr(w, "card"):
                    try:
                        w.unbind("<Button-1>")
                    except Exception:
                        pass
                    try:
                        w.bind("<Button-1>", lambda e, label=w: self.toggle_card_selection(label))
                    except Exception:
                        pass
        except Exception:
            pass

        # 初始化
        self.selected_cards_for_exchange = []
        try:
            self.immediate_exchange_btn.config(state=tk.DISABLED)
        except Exception:
            pass

    def _rebind_active_card_labels_after_exchange(self, include_dealer):
        """
        把当前界面上 player（和可选的 dealer）frame 下的 card Labels 重新收集并绑定到
        self.active_card_labels，这样 reset_game() 就能正确把它们收起。

        include_dealer: 是否也把 dealer_cards_frame 的标签一并收集（默认 False）。
        up_threshold: 用来判断是否算“已上移”的阈值（像你之前把新牌上移 15px，可据此判断）。
        """
        try:
            labels = []
            # 收集玩家牌
            if hasattr(self, "player_cards_frame") and self.player_cards_frame:
                for w in self.player_cards_frame.winfo_children():
                    if hasattr(w, "card") and w.winfo_exists():
                        labels.append(w)

            # 可选：收集庄家牌
            if include_dealer and hasattr(self, "dealer_cards_frame") and self.dealer_cards_frame:
                for w in self.dealer_cards_frame.winfo_children():
                    if hasattr(w, "card") and w.winfo_exists():
                        labels.append(w)

            # 赋值 active_card_labels（覆盖原有）
            self.active_card_labels = labels

            # 重新初始化 moved_cards（reset_game / animate_collect_cards 依赖）
            self.moved_cards = []
            self.ak_moved = False

            for lbl in self.active_card_labels:
                try:
                    cur_y = int(lbl.place_info().get('y', lbl.winfo_y()))
                except Exception:
                    try:
                        cur_y = lbl.winfo_y()
                    except Exception:
                        cur_y = 0
                # moved_cards 期望的是 (label, original_y)
                self.moved_cards.append((lbl, cur_y))

        except Exception:
            # 兜底：不要使主流程中断
            try:
                self.active_card_labels = []
                self.moved_cards = []
                self.ak_moved = False
            except Exception:
                pass

    def perform_exchange_now(self):
        """
        执行换牌（扣款、替换、动画）。
        行为要点：
        - 发新牌并按被换牌的索引替换回 player_hand（保持位次）
        - 刷新为固定 10px 间距（refresh_player_cards_after_exchange）
        - 把新牌向上移动 15px（一次性）
        - 等 1 秒后调用 sort_player_hand_after_exchange()
        """
        if getattr(self, "_exchange_executing", False):
            return
        self._exchange_executing = True

        sel = getattr(self, "selected_cards_for_exchange", [])
        selected_labels = [lbl for lbl in sel if lbl.winfo_exists()]
        cnt = len(selected_labels)
        if cnt < 2 or cnt > 5:
            messagebox.showerror("错误", "换牌数量必须为 2~5 张")
            self._exchange_executing = False
            return

        exchange_cost = self.game.ante
        if self.balance < exchange_cost:
            messagebox.showerror("错误", "余额不足支付换牌")
            self._exchange_executing = False
            return
        
        self.immediate_exchange_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.DISABLED)

        # 扣款
        self.balance -= exchange_cost
        self.update_balance()

        # 记录买入/换牌下注
        self.game.buy_exchange_bet = exchange_cost

        try:
            self.exchange_var.set(str(exchange_cost))
            self.exchange_display.config(bg='light grey', fg='black')
        except Exception:
            pass

        # 更新本局下注总额显示
        total_bet = self.game.ante + self.game.super_bet + self.game.buy_exchange_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        # 找出每个被选标签对应在手牌中的索引（保证替换到原位）
        selected_indices = []
        selected_models = []
        for lbl in selected_labels:
            if not hasattr(lbl, "card"):
                selected_indices.append(None)
                selected_models.append(None)
                continue
            card_model = lbl.card
            selected_models.append(card_model)
            try:
                idx = self.game.player_hand.index(card_model)
            except ValueError:
                idx = None
            selected_indices.append(idx)

        # 若存在 None，按标签 x 排序来推断索引（尽量匹配视觉顺序）
        if any(i is None for i in selected_indices):
            try:
                lbls_sorted = sorted(selected_labels, key=lambda L: int(L.place_info().get('x', L.winfo_x())))
                # 构建可用索引并填补
                available = list(range(len(self.game.player_hand)))
                present = [i for i in selected_indices if i is not None]
                for p in present:
                    if p in available:
                        available.remove(p)
                fill_iter = iter(available)
                new_idx = []
                for orig in selected_indices:
                    if orig is None:
                        new_idx.append(next(fill_iter))
                    else:
                        new_idx.append(orig)
                selected_indices = new_idx
            except Exception:
                # 兜底：把它们视作末尾连续位置
                start = max(0, len(self.game.player_hand) - cnt)
                selected_indices = list(range(start, start + cnt))

        # 动画参数（缩小碎裂）
        duration = 900
        steps = 20
        interval = max(1, duration // steps)

        def shatter_step(step):
            if step > steps:
                # 销毁旧标签
                for lbl in selected_labels:
                    try:
                        lbl.destroy()
                    except Exception:
                        pass

                # 发新牌并按索引替换
                try:
                    new_cards = self.game.deck.deal(len(selected_indices))
                except Exception:
                    new_cards = []

                try:
                    ph = list(self.game.player_hand)
                    pairs = list(zip(selected_indices, new_cards))
                    # 按索引升序替换
                    for idx, new_card in sorted(pairs, key=lambda p: p[0] if p[0] is not None else 9999):
                        if idx is None or idx < 0 or idx >= len(ph):
                            ph.append(new_card)
                        else:
                            ph[idx] = new_card
                    self.game.player_hand = ph
                except Exception:
                    # 兜底：剩余 + new
                    remaining = [c for c in self.game.player_hand if c not in selected_models]
                    self.game.player_hand = remaining + new_cards

                # 刷新为固定 10px 间距（不使用买入动画的叠放逻辑）
                try:
                    self.refresh_player_cards_after_exchange()
                except Exception:
                    try:
                        # 如果该函数不存在，退回到普通刷新（尽量保证能显示）
                        self.refresh_player_cards(animated=False)
                    except Exception:
                        pass

                # 把新牌向上移动 15px（一次性），通过识别 new_cards（集合）
                try:
                    new_set = set(new_cards)
                    moved = 0
                    for w in self.player_cards_frame.winfo_children():
                        if hasattr(w, "card") and w.card in new_set:
                            try:
                                cur_y = int(w.place_info().get('y', w.winfo_y()))
                            except Exception:
                                cur_y = w.winfo_y()
                            w.place_configure(y=max(0, cur_y - 15))
                            moved += 1
                            if moved >= len(new_set):
                                break
                except Exception:
                    pass

                try:
                    # include_dealer=False 一般只需绑定玩家牌；如需也绑定庄家，设 True
                    self._rebind_active_card_labels_after_exchange(include_dealer=True)
                except Exception:
                    pass

                # 退出选择模式，清理按钮并恢复决策按钮（买入后状态）
                self.exchange_selection_active = False
                try:
                    for widget in self.action_frame.winfo_children():
                        widget.destroy()
                except Exception:
                    pass

                # 等 1 秒（动画感），再启动 专用排序 -> 排序结束后会跳到 after_buy_exchange_decision()
                try:
                    self.after(1000, lambda: self.sort_player_hand_after_exchange())
                except Exception:
                    try:
                        self.sort_player_hand_after_exchange()
                    except Exception:
                        pass

                # 清理选中记录和标志
                self.selected_cards_for_exchange = []
                self._exchange_executing = False
                return

            # 缩放步骤（视觉效果：把被换的牌逐步缩小）
            scale = 1.0 - (step / steps)
            for lbl in selected_labels:
                if not lbl.winfo_exists():
                    continue
                try:
                    w0 = int(lbl.place_info().get('width', lbl.winfo_width()))
                    h0 = int(lbl.place_info().get('height', lbl.winfo_height()))
                    cx = int(lbl.place_info().get('x', lbl.winfo_x())) + w0 // 2
                    cy = int(lbl.place_info().get('y', lbl.winfo_y())) + h0 // 2
                    w = max(1, int(w0 * scale))
                    h = max(1, int(h0 * scale))
                    new_x = cx - w // 2
                    new_y = cy - h // 2
                    lbl.place_configure(x=new_x, y=new_y, width=w, height=h)
                except Exception:
                    pass
            self.after(interval, lambda: shatter_step(step + 1))

        shatter_step(1)

    def _rebuild_animation_for_new_cards(self, num_new, duration=1500):
        """
        仅为新加的那 num_new 张牌做扩展动画，避免重建全部牌并移除左右 10px 的间隙。
        num_new: 新加入的牌数量（通常为 1）
        """
        # 安全检查
        if num_new <= 0:
            return

        # 1) 清除可能的 pack/grid padx/pady 等导致的间隙（确保没有遗留的 10px）
        # 如果你在类里已经有 _clear_card_frame_padding()，则调用它；否则执行内联清理
        try:
            self._clear_card_frame_padding()
        except Exception:
            for w in self.player_cards_frame.winfo_children():
                try:
                    w.pack_configure(padx=0, pady=0)
                except Exception:
                    pass
                try:
                    w.grid_configure(padx=0, pady=0)
                except Exception:
                    pass
                try:
                    # place 没有 padx，但修整 x/y 为整数以避免浮点缝隙
                    p = w.place_info()
                    if p:
                        if 'x' in p:
                            w.place_configure(x=int(float(p['x'])))
                        if 'y' in p:
                            w.place_configure(y=int(float(p['y'])))
                except Exception:
                    pass

        # 2) 计算尺寸与槽宽（兼容两种命名）
        card_width = getattr(self, "CARD_DISPLAY_WIDTH", None)
        if card_width is None:
            card_width = getattr(self, "CARD_WIDTH", 100)
        final_w, final_h = int(card_width), int(card_width * 1.8)
        overlap = getattr(self, "CARD_OVERLAP", 20)  # 每张牌与前一张重叠像素，默认 20
        slot = max(1, int(final_w - overlap))
        left_margin = getattr(self, "CARD_LEFT_MARGIN", 10)

        # 3) 建立现有标签映射（card -> label）
        existing_labels = {}
        for w in self.player_cards_frame.winfo_children():
            if hasattr(w, "card"):
                existing_labels[w.card] = w

        # 4) 确定哪些是新牌（取最后 num_new 张作为新牌）
        total = len(self.game.player_hand)
        if num_new > total:
            num_new = total
        new_cards = list(self.game.player_hand[-num_new:])

        # 5) 把已有的 label 精确定位到槽位（如果已经是 place 也会被覆盖为整数坐标）
        #    通过 game.player_hand 的顺序确定每张牌的 index
        for idx, card in enumerate(self.game.player_hand):
            target_x = left_margin + idx * slot
            lbl = existing_labels.get(card)
            if lbl:
                try:
                    # 修正到确切位置与大小，避免之前 pack 带来的 padx
                    lbl.place_configure(x=int(target_x), y=0, width=final_w, height=final_h)
                except Exception:
                    # 如果之前不是 place() 创建的，强制 place()
                    try:
                        lbl.place(x=int(target_x), y=0, width=final_w, height=final_h)
                    except Exception:
                        pass

        # 6) 为新牌创建临时小 label（仅对那些没有现成 label 的卡片创建）
        new_labels = []
        for card in new_cards:
            if card in existing_labels:
                # 若游戏逻辑先创建了 label，则也当作现有牌处理（不会动画）
                continue
            img = self.card_images.get((card.suit, card.rank), self.back_image)
            lbl = tk.Label(self.player_cards_frame, image=img, bg=self.player_cards_frame['bg'])
            lbl.card = card
            lbl.is_face_up = True
            # 放在目标槽中心，初始为 1x1 小尺寸，供扩展动画使用
            idx = self.game.player_hand.index(card)
            target_x = left_margin + idx * slot
            lbl.place(x=int(target_x + final_w // 2), y=int(final_h // 2), width=1, height=1)
            new_labels.append((lbl, idx))  # 保存对应索引，便于动画定位

        # 如果没有实际新建 label（例如 label 已存在），直接返回（或刷新）
        if not new_labels:
            # 仍然保证刷新显示并绑定事件（防止某些 label 没绑定事件）
            for w in self.player_cards_frame.winfo_children():
                if hasattr(w, "card"):
                    try:
                        w.bind("<Button-1>", lambda e, label=w: self.toggle_card_selection(label))
                    except Exception:
                        pass
            self.after(50, lambda: self.refresh_player_cards(animated=False))
            return

        # 7) 动画参数（仅对新_labels 做扩展动画）
        steps = max(8, duration // 60)
        interval = max(1, duration // steps)

        def expand_step(step):
            if step > steps:
                # 动画完成，把新 label 固定为最终位置与尺寸，绑定事件
                for lbl, idx in new_labels:
                    try:
                        final_x = left_margin + idx * slot
                        lbl.place_configure(x=int(final_x), y=0, width=final_w, height=final_h)
                        lbl.bind("<Button-1>", lambda e, label=lbl: self.toggle_card_selection(label))
                        lbl.config(image=self.card_images.get((lbl.card.suit, lbl.card.rank), self.back_image))
                    except Exception:
                        pass
                # 最后强制刷新（非动画）
                self.after(30, lambda: self.refresh_player_cards(animated=False))
                return

            scale = step / steps
            for lbl, idx in new_labels:
                try:
                    w = max(1, int(final_w * scale))
                    h = max(1, int(final_h * scale))
                    x = int(left_margin + idx * slot + (final_w - w) // 2)
                    y = int((final_h - h) // 2)
                    lbl.place_configure(x=x, y=y, width=w, height=h)
                except Exception:
                    pass

            self.after(interval, lambda: expand_step(step + 1))

        # 启动动画
        expand_step(1)

    def refresh_player_cards_after_exchange(self):
        """
        换牌结束后专用刷新（与买入/动画的 refresh_player_cards 区分）
        将玩家手牌按固定 CARD_WIDTH 和 gap=10 放置，不做叠放、不做动画。
        """
        # 清空旧显示
        for w in self.player_cards_frame.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        CARD_WIDTH = 100  # 你的 UI 看起来用 110 间距；若你用 100 可改回
        CARD_HEIGHT = 180
        gap = 10
        start_x = 0
        y = 0

        for i, card in enumerate(self.game.player_hand):
            img = self.card_images.get((card.suit, card.rank))
            if not img:
                # 如果没有图像，跳过（或创建占位）
                lbl = tk.Label(self.player_cards_frame, text=f"{card.rank}{card.suit}", bd=0, bg='#2a4a3c', fg='white')
            else:
                lbl = tk.Label(self.player_cards_frame, image=img, bd=0, bg='#2a4a3c')
                lbl.image = img

            lbl.card = card
            x = start_x + i * (CARD_WIDTH + gap)
            lbl.place(x=x, y=y, width=CARD_WIDTH, height=CARD_HEIGHT)

            # 保持在换牌选择模式下牌可被点
            if getattr(self, "exchange_selection_active", False):
                try:
                    lbl.unbind("<Button-1>")
                except Exception:
                    pass
                try:
                    lbl.bind("<Button-1>", lambda e, label=lbl: self.toggle_card_selection(label))
                except Exception:
                    pass

    # ---------- 修改：refresh_player_cards，加入 y 轴复位动画 ----------
    def refresh_player_cards(self, animated=False):
        """刷新玩家手牌显示（排序后）。如果 animated=True，则从旧位置平滑移动到目标位置。"""
        # 采集旧标签及其位置（按 x 排序）
        old_labels = list(self.player_cards_frame.winfo_children())
        old_labels.sort(key=lambda w: int(w.place_info().get('x', w.winfo_x())) if w.winfo_ismapped() else w.winfo_x())
        old_positions = []
        for lbl in old_labels:
            try:
                ox = int(lbl.place_info().get('x', lbl.winfo_x()))
                oy = int(lbl.place_info().get('y', lbl.winfo_y()))
            except Exception:
                ox, oy = int(lbl.winfo_x()), int(lbl.winfo_y())
            old_positions.append((lbl, ox, oy))

        # 清除旧标签
        for widget in self.player_cards_frame.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass

        # 如果是 5 张牌以上，排序并替换手牌（保持你原来的逻辑）
        if len(self.game.player_hand) >= 5:
            player_eval = evaluate_five_card_hand(self.game.player_hand)
            sorted_hand = sort_hand_for_display(self.game.player_hand, player_eval)
            self.game.player_hand = sorted_hand

        # 统一尺寸/重叠常量（优先使用实例属性）
        card_width = getattr(self, "CARD_WIDTH", 100)
        card_height = getattr(self, "CARD_HEIGHT", int(card_width * 1.8))
        # 用 overlap 表示每张牌与前一张的重叠像素（正值表示覆盖前一张）
        overlap = getattr(self, "CARD_OVERLAP", 20)
        # 槽宽：每张牌的起始 x 增量（小于 card_width 达到重叠效果）
        slot = max(1, int(card_width - overlap))
        left_margin = getattr(self, "CARD_LEFT_MARGIN", 0)

        new_labels = []
        for i, card in enumerate(self.game.player_hand):
            img = self.card_images.get((card.suit, card.rank), self.back_image)
            card_label = tk.Label(self.player_cards_frame, image=img, bg=self.player_cards_frame['bg'])
            # 如果动画，并且存在旧位置，用旧位置开始；否则放到目标位置（整数坐标）
            if animated and i < len(old_positions):
                _, old_x, old_y = old_positions[i]
                card_label.place(x=int(old_x), y=int(old_y), width=int(card_width), height=int(card_height))
            else:
                x0 = left_margin + i * slot
                card_label.place(x=int(x0), y=0, width=int(card_width), height=int(card_height))

            card_label.card = card
            card_label.is_face_up = True
            card_label.bind("<Button-1>", lambda e, label=card_label: self.toggle_card_selection(label))
            try:
                card_label.lift()
            except Exception:
                pass
            new_labels.append(card_label)

        # 如果需要动画，计算目标整数坐标并启动移动
        if animated and new_labels:
            target_xs = [int(left_margin + i * slot) for i in range(len(new_labels))]
            target_ys = [0] * len(new_labels)
            self.animate_move_to_positions(new_labels, target_xs, target_ys, duration=600)

    def animate_move_to_positions(self, labels, target_xs, target_ys=None, duration=500):
        """移动标签到目标位置，支持同时移动 x 和 y。
        注意：在移动过程中使用整数坐标放置，避免浮点导致像素裂缝。
        """
        if not labels:
            return
        # 步数与间隔：最少 8 步，约 20ms/步
        steps = max(8, duration // 20)
        interval = max(1, duration // steps)

        start_xs = []
        start_ys = []
        for lbl in labels:
            try:
                sx = int(lbl.place_info().get('x', lbl.winfo_x()))
                sy = int(lbl.place_info().get('y', lbl.winfo_y()))
            except Exception:
                sx, sy = int(lbl.winfo_x()), int(lbl.winfo_y())
            start_xs.append(sx)
            start_ys.append(sy)

        if target_ys is None:
            target_ys = list(start_ys)

        # 计算每步增量（浮点），但实际放置时会取整
        deltas_x = [(tx - sx) / steps for sx, tx in zip(start_xs, target_xs)]
        deltas_y = [(ty - sy) / steps for sy, ty in zip(start_ys, target_ys)]

        # 保留当前位置为浮点以避免累积舍入误差，然后在 place 时 int(round(...))
        cur_xs = [float(sx) for sx in start_xs]
        cur_ys = [float(sy) for sy in start_ys]

        def step_fn(step):
            if step > steps:
                # 最终落位：确保精确整数目标
                for lbl, tx, ty in zip(labels, target_xs, target_ys):
                    try:
                        lbl.place_configure(x=int(tx), y=int(ty))
                    except Exception:
                        pass
                return

            for i, lbl in enumerate(labels):
                try:
                    # 增量累加（保持 float 精度）
                    cur_xs[i] += deltas_x[i]
                    cur_ys[i] += deltas_y[i]
                    new_x = int(round(cur_xs[i]))
                    new_y = int(round(cur_ys[i]))
                    # 强制整数坐标放置，避免浮点值露出背景
                    lbl.place_configure(x=new_x, y=new_y)
                except Exception:
                    pass

            # 下一帧
            self.after(interval, lambda: step_fn(step + 1))

        # 启动动画
        step_fn(1)

    def toggle_card_selection(self, label):
        """
        切换选牌状态（15px），仅在 exchange 选择模式下响应。
        点击 -> 下移15px=选中；再次点击 -> 上移15px=取消。
        并更新 immediate_exchange_btn 的 enabled 状态（2~5 张时开启）。
        """
        # 仅在换牌选择模式下有效
        if not getattr(self, "exchange_selection_active", False):
            return

        if not hasattr(label, "card"):
            return

        if not hasattr(self, "selected_cards_for_exchange") or self.selected_cards_for_exchange is None:
            self.selected_cards_for_exchange = []

        try:
            cur_y = int(label.place_info().get('y', label.winfo_y()))
        except Exception:
            cur_y = label.winfo_y()

        if label in self.selected_cards_for_exchange:
            # 取消选择，向上 15px
            new_y = max(0, cur_y - 15)
            label.place_configure(y=new_y)
            try:
                self.selected_cards_for_exchange.remove(label)
            except ValueError:
                pass
            label.config(bd=0, relief=tk.FLAT)
        else:
            if len(self.selected_cards_for_exchange) >= 5:
                messagebox.showwarning("提示", "最多只能选择5张牌")
                return
            # 选中，向下 15px
            new_y = cur_y + 15
            label.place_configure(y=new_y)
            self.selected_cards_for_exchange.append(label)
            label.config(bd=3, relief=tk.SOLID, highlightbackground='gold')

        # 更新“立刻换牌”按钮状态（如果存在）
        try:
            cnt = len([lbl for lbl in self.selected_cards_for_exchange if lbl.winfo_exists()])
            if hasattr(self, "immediate_exchange_btn") and self.immediate_exchange_btn:
                if 2 <= cnt <= 5:
                    self.immediate_exchange_btn.config(state=tk.NORMAL)
                else:
                    self.immediate_exchange_btn.config(state=tk.DISABLED)
        except Exception:
            pass

    def after_buy_exchange_decision(self):
        """买入或换牌后的二次决策"""
        self.game.buy_exchange_phase = True
        self.stage_label.config(text="二次决策")
        self.status_label.config(text="选择: 弃牌 或 下注2X")

        for widget in self.action_frame.winfo_children():
            widget.destroy()

        btn_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        btn_frame.pack(pady=5)

        self.fold_button = tk.Button(btn_frame, text="弃牌", command=self.fold_after_buy_exchange,
                                      font=('Arial', 14), bg='#F44336', fg='white', width=9)
        self.fold_button.pack(side=tk.LEFT, padx=5)

        self.play_button = tk.Button(btn_frame, text="下注2X", command=self.play_after_buy_exchange,
                                      font=('Arial', 14), bg='#4CAF50', fg='white', width=9)
        self.play_button.pack(side=tk.LEFT, padx=5)

    def fold_after_buy_exchange(self):
        """买入/换牌后弃牌"""
        self.game.folded = True
        self.fold_mode = True
        self.status_label.config(text="您已弃牌")
        if self.fold_button:
            self.fold_button.config(state=tk.DISABLED)
        if self.play_button:
            self.play_button.config(state=tk.DISABLED)

        self.reveal_dealer_cards()

    def play_after_buy_exchange(self):
        """买入/换牌后下注2X"""
        raise_amount = self.game.ante * 2
        if self.balance < raise_amount:
            messagebox.showerror("错误", "余额不足")
            return

        self.balance -= raise_amount
        self.update_balance()
        self.game.raise_bet = raise_amount
        self.raise_var.set(str(raise_amount))

        total = self.game.ante + self.game.super_bet + self.game.buy_exchange_bet + raise_amount
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")

        if self.fold_button:
            self.fold_button.config(state=tk.DISABLED)
        if self.play_button:
            self.play_button.config(state=tk.DISABLED)

        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.reveal_dealer_cards)

    def reveal_dealer_cards(self):
        """翻开庄家所有牌"""
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["dealer"][i] = True

        self.update_hand_labels()
        self.after(1500, self.start_both_sort_animation)

    def show_restart_button(self):
        """显示重新开始按钮"""
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        self.restart_btn = tk.Button(
            self.action_frame, text="再来一局",
            command=self.reset_game,
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        self.restart_btn.pack(pady=5)
        self.restart_btn.bind("<Button-3>", self.show_card_sequence)

        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    # ==================== 重置和辅助方法 ====================
    def reset_bets(self):
        self.ante_var.set("0")
        self.super_bet_var.set("0")
        self.exchange_var.set("0")
        self.raise_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.ante_display.config(bg='#FFCDD2')
        self.super_bet_display.config(bg='#FFCDD2')
        self.after(500, lambda: self.ante_display.config(bg='white'))
        self.after(500, lambda: self.super_bet_display.config(bg='white'))

    def reset_game(self, auto_reset=False):
        self.cancel_auto_reset_timer()
        self._resetting = True

        for after_id in self.tk.eval('after info').split():
            self.after_cancel(after_id)

        if self.active_card_labels:
            self.disable_action_buttons()
            self.animate_collect_cards(auto_reset)
            return

        self._do_reset(auto_reset)

    def animate_collect_cards(self, auto_reset):
        if self.ak_moved and self.moved_cards:
            self.animate_move_up_step(0, auto_reset)
            return
        self.animate_move_cards_out(auto_reset)

    def animate_move_up_step(self, step, auto_reset):
        if step > 5:
            self.animate_move_cards_out(auto_reset)
            return
        for card_label, original_y in self.moved_cards:
            if card_label.winfo_exists():
                current_y = card_label.winfo_y()
                new_y = current_y - 2
                card_label.place(y=new_y)
        step += 1
        self.after(100, lambda: self.animate_move_up_step(step, auto_reset))

    def animate_move_cards_out(self, auto_reset):
        self.active_card_labels = [label for label in self.active_card_labels if label.winfo_exists()]
        if not self.active_card_labels:
            self._do_reset(auto_reset)
            return

        for card_label in self.active_card_labels:
            card_label.target_pos = (1200, card_label.winfo_y())

        self.animate_card_out_step(auto_reset)

    def animate_card_out_step(self, auto_reset):
        all_done = True
        for card_label in self.active_card_labels[:]:
            if not hasattr(card_label, 'target_pos') or not card_label.winfo_exists():
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
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

        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except:
                pass
            self.auto_reset_timer = None

        for after_id in self.tk.eval('after info').split():
            self.after_cancel(after_id)

        self.game.reset_game()
        self.stage_label.config(text="翻牌前")
        self.status_label.config(text="设置下注金额并开始游戏")

        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")

        self.ante_var.set("0")
        self.super_bet_var.set("0")
        self.exchange_var.set("0")
        self.raise_var.set("0")

        for widget in self.bet_widgets.values():
            widget.config(bg='white')

        self.active_card_labels = []
        self.moved_cards = []
        self.ak_moved = False
        self.ak_animation_active = False
        self.animation_queue = []
        self.animation_in_progress = False
        self.flipping_cards = []
        self.flip_step = 0
        self.selected_cards_for_exchange = []

        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.super_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("super_bet"))
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))

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

        self.start_button = tk.Button(
            start_button_frame, text="开始游戏",
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)

        self.current_bet_label.config(text="本局下注: $0.00")
        self.last_win_label.config(text="上局获胜: $0.00")

        self._resetting = False
        self.fold_mode = False

        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

    def show_card_sequence(self, event):
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
        cut_label = tk.Label(win, text=f"本局切牌位置: {cut_pos + 1}",
                              font=('Arial', 14, 'bold'), bg='#f0f0f0')
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
                card_label = tk.Label(card_container, image=small_images[card_index],
                                      bg=bg_color, borderwidth=1, relief="solid")
                card_label.image = small_images[card_index]
                card_label.pack()
                pos_label = tk.Label(card_container, text=str(card_index+1), bg=bg_color, font=('Arial', 9))
                pos_label.pack()

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

def main(initial_balance=10000, username="Guest"):
    app = LunarPokerGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")