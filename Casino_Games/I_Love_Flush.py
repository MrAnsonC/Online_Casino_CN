import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import secrets
import subprocess, sys
import time
from collections import Counter
from itertools import combinations

# =========================================================
# UI 颜色（与原版一致）
# =========================================================
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

# =========================================================
# 边注赔付表（赔率表示“赢”的倍数，返还时需加上本金）
# =========================================================
FLUSH_PAYOUT = {
    7: 300,
    6: 30,
    5: 6,
    4: 3,
}

STRAIGHT_FLUSH_PAYOUT = {
    7: 8000,
    6: 1000,
    5: 100,
    4: 60,
    3: 7,
}

# =========================================================
# 文件操作（用户余额）
# =========================================================
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

# =========================================================
# 牌局历史日志（I_Love_Flush）
# =========================================================
def love_flush_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "I_Love_Flush.json")

def save_love_flush_history(deck, player_cards, dealer_cards, result_info=None):
    log_path = love_flush_log_path()
    data = {
        "history_record": {
            "player_win": 0,
            "dealer_win": 0,
            "push": 0,
            "fold": 0,
            "game": 0
        },
        "history": []
    }
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "history_record" in loaded:
                    for key in data["history_record"]:
                        if key not in loaded["history_record"]:
                            loaded["history_record"][key] = 0
                    data["history_record"] = loaded["history_record"]
                    if "history" in loaded:
                        data["history"] = loaded["history"]
                elif isinstance(loaded, list):
                    data["history"] = loaded
                    stats = {"player_win": 0, "dealer_win": 0, "fold": 0, "push": 0, "game": len(loaded)}
                    for rec in loaded:
                        if "result" in rec and "winner" in rec["result"]:
                            winner = rec["result"]["winner"]
                            if winner == "player":
                                stats["player_win"] += 1
                            elif winner == "dealer":
                                stats["dealer_win"] += 1
                            elif winner == "fold":
                                stats["fold"] += 1
                            elif winner == "push":
                                stats["push"] += 1
                    data["history_record"] = stats
        except Exception as e:
            print(f"读取历史文件出错: {e}")

    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1

    stats = data["history_record"]
    stats["game"] += 1

    winner = None
    if result_info:
        if result_info.get("fold", False):
            winner = "fold"
            stats["fold"] += 1
        elif "winner" in result_info:
            winner = result_info["winner"]
            if winner == "player":
                stats["player_win"] += 1
            elif winner == "dealer":
                stats["dealer_win"] += 1
            elif winner == "push":
                stats["push"] += 1

    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "player_cards": [str(c) for c in player_cards],
        "dealer_cards": [str(c) for c in dealer_cards],
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner
    data["history"].append(record)

    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 扑克牌类与牌堆
# =========================================================
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

# =========================================================
# I_Love_Flush 核心评估函数
# =========================================================
def get_flush_cards(hand):
    """
    从7张手牌中选出同花牌（出现次数最多的花色），
    若多个花色数量相同，则选择牌面列表（降序）字典序更大的那组。
    返回 (selected_cards, max_count)
    """
    if not hand:
        return [], 0
    suits_count = Counter(c.suit for c in hand)
    max_count = max(suits_count.values())
    best_suit = None
    best_sorted_values = []  # 用于比较
    for suit, cnt in suits_count.items():
        if cnt == max_count:
            cards = [c for c in hand if c.suit == suit]
            cards.sort(key=lambda c: c.value, reverse=True)
            values = [c.value for c in cards]
            if best_suit is None or values > best_sorted_values:
                best_suit = suit
                best_sorted_values = values
    selected = [c for c in hand if c.suit == best_suit]
    selected.sort(key=lambda c: c.value, reverse=True)
    return selected, max_count

def get_longest_straight_flush(hand):
    best_len = 0
    for suit in SUITS:
        cards = [c for c in hand if c.suit == suit]
        if len(cards) < 3:
            continue
        values = sorted(set(c.value for c in cards))
        cur_len = 1
        for i in range(1, len(values)):
            if values[i] == values[i-1] + 1:
                cur_len += 1
                best_len = max(best_len, cur_len)
            else:
                cur_len = 1
        if 14 in values and 2 in values and 3 in values and 4 in values and 5 in values:
            best_len = max(best_len, 5)
    return best_len

def compare_flush_hands(player_flush, dealer_flush):
    if len(player_flush) > len(dealer_flush):
        return 1
    elif len(player_flush) < len(dealer_flush):
        return -1
    else:
        for p, d in zip(player_flush, dealer_flush):
            if p.value > d.value:
                return 1
            elif p.value < d.value:
                return -1
        return 0

# =========================================================
# 新排序函数：按花色分组，组内降序，组间按最大牌降序（逐张比较）
# =========================================================
def sort_hand_by_groups(hand):
    """
    将7张牌排序：
    1. 按花色分组，每组内牌面降序排列（A最大）。
    2. 按花色出现次数（同花数量）降序排列各组。
    3. 若出现次数相同，则按组内牌面列表（降序）逐张比较，大的组排前。
    4. 最后将所有组合并返回。
    """
    if not hand:
        return []

    # 按花色分组
    groups = {}
    for c in hand:
        groups.setdefault(c.suit, []).append(c)

    # 每组内部降序
    for suit in groups:
        groups[suit].sort(key=lambda c: c.value, reverse=True)

    # 构建排序项：(数量, 牌面值列表, 牌列表)
    group_items = [(len(cards), [c.value for c in cards], cards) for cards in groups.values()]

    # 按(数量, 牌面值列表) 降序排序
    group_items.sort(key=lambda item: (item[0], item[1]), reverse=True)

    # 合并结果
    sorted_hand = []
    for _, _, cards in group_items:
        sorted_hand.extend(cards)

    return sorted_hand

# =========================================================
# 游戏逻辑类
# =========================================================
class ILoveFlushGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.ante = 0
        self.flush_bet = 0
        self.straight_flush_bet = 0
        self.play_bet = 0
        self.play_multiplier = 0
        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False]*7,
            "dealer": [False]*7
        }

    def deal_initial(self):
        self.player_hand = self.deck.deal(7)
        self.dealer_hand = self.deck.deal(7)

    def get_player_flush(self):
        return get_flush_cards(self.player_hand)[0]

    def get_dealer_flush(self):
        return get_flush_cards(self.dealer_hand)[0]

    def dealer_qualifies(self):
        """庄家合格条件：同花牌数>=3 且 最大牌>=9"""
        flush, cnt = get_flush_cards(self.dealer_hand)
        if cnt < 3:
            return False
        max_val = max(c.value for c in flush) if flush else 0
        return max_val >= 9

# =========================================================
# 主GUI类
# =========================================================
class ILoveFlushGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = ILoveFlushGame()
        self.card_images = {}
        self.original_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.last_win = 0
        self.last_bet = None
        self.repeat_bet_btn = None
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.win_details = {
            "ante": 0,
            "play": 0,
            "flush": 0,
            "straight_flush": 0
        }
        self.bet_widgets = {}
        self.flush_bet_var = tk.StringVar(value="0")
        self.straight_flush_bet_var = tk.StringVar(value="0")
        self.play_amount_var = tk.StringVar(value="0")

        self.high_bet_mode = False
        self.game_in_progress = False

        self._load_assets()
        self._create_widgets()

    def on_close(self):
        timer = getattr(self, "auto_reset_timer", None)
        if timer:
            try:
                self.after_cancel(timer)
            except tk.TclError:
                pass
        try:
            update_balance_in_json(self.username, self.balance)
        except Exception:
            pass
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))
        if callable(self.on_back):
            self.on_back(float(self.balance))


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

    # ---------- 添加筹码 ----------
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K','')) * 1000
        else:
            chip_value = float(chip_text)

        limits = {
            "ante": (50000 if self.high_bet_mode else 10000),
            "flush": (12500 if self.high_bet_mode else 2500),
            "straight_flush": (12500 if self.high_bet_mode else 2500)
        }
        if bet_type in limits:
            var_map = {
                "ante": self.ante_var,
                "flush": self.flush_bet_var,
                "straight_flush": self.straight_flush_bet_var
            }
            current = float(var_map[bet_type].get())
            limit = limits[bet_type]
            if current >= limit:
                names = {"ante":"底注","flush":"同花","straight_flush":"同花顺"}
                messagebox.showwarning("下注限制", f"{names[bet_type]}已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                new_amount = limit
                if current > 0:
                    names = {"ante":"底注","flush":"同花","straight_flush":"同花顺"}
                    messagebox.showwarning("下注限制", f"{names[bet_type]}已达上限，自动调整为 {int(new_amount)}")
            var_map[bet_type].set(str(int(new_amount)))

    # ---------- 重置单个下注 ----------
    def reset_single_bet(self, bet_type, event):
        var_map = {
            "ante": self.ante_var,
            "flush": self.flush_bet_var,
            "straight_flush": self.straight_flush_bet_var
        }
        if bet_type in var_map:
            var_map[bet_type].set("0")
        if bet_type in self.bet_widgets:
            widget = self.bet_widgets[bet_type]
            original_bg = widget.cget('bg')
            widget.config(bg='#FFCDD2')
            self.after(500, lambda: widget.config(bg=original_bg))

    def clear_btn_frame(self):
        for widget in self.btn_frame.winfo_children():
            widget.destroy()

    def add_main_buttons(self):
        self.clear_btn_frame()

        for i in range(3):
            self.btn_frame.grid_columnconfigure(i, weight=1)

        self.reset_bets_button = tk.Button(
            self.btn_frame,
            text="重设金额",
            command=self.reset_bets,
            font=('Arial',12,'bold'),
            bg='#F44336',
            fg='white'
        )
        self.reset_bets_button.grid(row=0, column=0, padx=5, sticky="ew")

        self.repeat_bet_btn = tk.Button(
            self.btn_frame,
            text="重复上局下注",
            command=self.apply_last_bet,
            font=('Arial',12,'bold'),
            bg='#FFC107',
            fg='black',
            state=tk.NORMAL if self.last_bet else tk.DISABLED
        )
        self.repeat_bet_btn.grid(row=0, column=1, padx=5, sticky="ew")

        self.start_button = tk.Button(
            self.btn_frame,
            text="开始游戏",
            command=self.start_game,
            font=('Arial',12,'bold'),
            bg='#4CAF50',
            fg='white'
        )
        self.start_button.grid(row=0, column=2, padx=5, sticky="ew")

    # ---------- 创建主界面 ----------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_canvas.create_rectangle(0,0,790,720, fill=ROOT_BG, outline=GOLD, width=5)

        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=15, y=60, width=760, height=230)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 中间提示
        self.ante_info_label = tk.Label(
            table_canvas,
            text="庄家须同时持有3张或以上同花且最大牌≥9才合格\n不合格的，底注获胜，加注退还",
            font=('Arial',24),
            bg=ROOT_BG,
            fg='#FFD700'
        )
        self.ante_info_label.update_idletasks()
        label_width = self.ante_info_label.winfo_width()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        center_x = (canvas_width - label_width)//2
        self.ante_info_label.place(x=center_x+400, y=330, anchor='n')

        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=15, y=450, width=760, height=230)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 右侧控制面板
        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=340)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        # ---------- 1. 信息卡片 ----------
        info_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=3)
        header_info = tk.Frame(info_card, bg=HEADER_BG)
        header_info.pack(fill=tk.X)
        body_info = tk.Frame(info_card, bg=PANEL_BG)
        body_info.pack(fill=tk.X, padx=10, pady=8)

        self.balance_label = tk.Label(body_info, text=f"余额: ${self.balance:,.2f}", font=('Arial',16,'bold'),
                                      bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body_info, text="翻牌前", font=('Arial',16,'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # ---------- 2. 赔率速查表卡片 ----------
        odds_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        odds_card.pack(fill=tk.X, pady=3)
        header_odds = tk.Frame(odds_card, bg=HEADER_BG)
        header_odds.pack(fill=tk.X)
        tk.Label(header_odds, text="赔率速查表", font=('Arial',13,'bold'),
                bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_odds = tk.Frame(odds_card, bg=PANEL_BG)
        body_odds.pack(fill=tk.X, padx=8, pady=5)

        # 表头（3列）
        headers = ["牌型", "同花边注", "同花顺边注"]
        for col, text in enumerate(headers):
            tk.Label(body_odds, text=text, font=('Arial',9,'bold'),
                    bg='#D8B46A', fg='#2A1B08', borderwidth=1, relief=tk.SOLID,
                    padx=4, pady=2, width=10).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 数据行（只保留三行）
        odds_data = [
            ("7张同花", "300:1", "8000:1"),
            ("6张同花", "30:1", "1000:1"),
            ("5张同花", "6:1", "100:1"),
        ]
        for r, row_data in enumerate(odds_data, start=1):
            for c, text in enumerate(row_data):
                bg_color = '#F0F0F0' if r % 2 == 0 else '#E8E8E8'
                lbl = tk.Label(body_odds, text=text, font=('Arial',9),
                            bg=bg_color, padx=4, pady=2, relief=tk.SOLID, borderwidth=1, width=10)
                lbl.grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        for col in range(3):
            body_odds.columnconfigure(col, weight=1)

        # ---------- 3. 限红卡片 ----------
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
        titles = ["底注最低","底注最高","边注最高"]
        for col,title in enumerate(titles):
            lbl = tk.Label(table_frame, text=title, font=('Arial',11,'bold'),
                           bg=PANEL_BG, fg='#2A1B08', borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
            lbl.grid(row=0, column=col, sticky="nsew", padx=0, pady=0)
        self.min_ante_label = tk.Label(table_frame, text="$10", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.min_ante_label.grid(row=1, column=0, sticky="nsew")
        self.max_ante_label = tk.Label(table_frame, text="$10,000", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.max_ante_label.grid(row=1, column=1, sticky="nsew")
        self.max_side_label = tk.Label(table_frame, text="$2,500", font=('Arial',12,'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
        self.max_side_label.grid(row=1, column=2, sticky="nsew")
        for col in range(3):
            table_frame.columnconfigure(col, weight=1)
        for w in [limit_card, header_limit, body_limit, table_frame,
                  self.min_ante_label, self.max_ante_label, self.max_side_label]:
            w.bind("<Button-1>", self.toggle_high_bet_limits)

        # ---------- 4. 筹码与下注卡片 ----------
        combined_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined_card.pack(fill=tk.X, pady=3)
        header_combined = tk.Frame(combined_card, bg=HEADER_BG)
        header_combined.pack(fill=tk.X)
        tk.Label(header_combined, text="筹码与下注", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_combined = tk.Frame(combined_card, bg=PANEL_BG)
        body_combined.pack(fill=tk.X, padx=10, pady=8)
        body_combined.columnconfigure(0, weight=1)
        body_combined.columnconfigure(1, weight=1)

        # 筹码行
        chip_row = tk.Frame(body_combined, bg=PANEL_BG)
        chip_row.grid(row=0, column=0, columnspan=2, pady=(0,8), sticky='ew')
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)
        self.chip_container = chip_row

        chip_configs = [
            ('$10','#ffa500','black'),
            ("$25",'#00ff00','black'),
            ("$100",'#000000','white'),
            ("$500","#FF7DDA",'black'),
            ("$1K",'#ffffff','black'),
            ("$2.5K",'#ff0000','white'),
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
        self.select_chip("$10")

        # 下注行
        # 第一行：同花注 + 同花顺注
        row1 = tk.Frame(body_combined, bg=PANEL_BG)
        row1.grid(row=1, column=0, columnspan=2, sticky='ew', pady=4)
        tk.Label(row1, text="同花注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(0,5))
        self.flush_display = tk.Label(row1, textvariable=self.flush_bet_var, font=('Arial',12),
                                      bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.flush_display.pack(side=tk.LEFT, padx=5)
        self.flush_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("flush"))
        self.flush_display.bind("<Button-3>", lambda e: self.reset_single_bet("flush", e))
        self.bet_widgets["flush"] = self.flush_display

        tk.Label(row1, text="同花顺注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(7,5))
        self.straight_flush_display = tk.Label(row1, textvariable=self.straight_flush_bet_var, font=('Arial',12),
                                               bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.straight_flush_display.pack(side=tk.LEFT, padx=5)
        self.straight_flush_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("straight_flush"))
        self.straight_flush_display.bind("<Button-3>", lambda e: self.reset_single_bet("straight_flush", e))
        self.bet_widgets["straight_flush"] = self.straight_flush_display

        # 第二行：底注 + 加注
        row2 = tk.Frame(body_combined, bg=PANEL_BG)
        row2.grid(row=2, column=0, columnspan=2, sticky='ew', pady=4)
        tk.Label(row2, text="底注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(17,5))
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row2, textvariable=self.ante_var, font=('Arial',12),
                                     bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row2, text="加注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(41,5))
        self.play_amount_display = tk.Label(row2, textvariable=self.play_amount_var, font=('Arial',12),
                                            bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.play_amount_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["play_amount"] = self.play_amount_display

        # ---------- 5. 操作卡片 ----------
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

        # ---------- 6. 底部信息卡片 ----------
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
            self.min_ante_label.config(text="$100")
            self.max_ante_label.config(text="$50,000")
            self.max_side_label.config(text="$12,500")
        else:
            self.min_ante_label.config(text="$10")
            self.max_ante_label.config(text="$10,000")
            self.max_side_label.config(text="$2,500")

    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons = []
        self.chip_texts = {}
        self.selected_chip = None

        if self.high_bet_mode:
            chip_configs = [
                ("$100", '#000000', 'white'),
                ("$500", "#FF7DDA", 'black'),
                ("$1K", '#ffffff', 'black'),
                ("$5K", '#ff0000', 'white'),
                ("$10K", '#00fbff', 'black'),
                ("$50K", '#00ffae', 'black')
            ]
            default = "$100"
        else:
            chip_configs = [
                ('$10', '#ffa500', 'black'),
                ("$25", '#00ff00', 'black'),
                ("$100", '#000000', 'white'),
                ("$500", "#FF7DDA", 'black'),
                ("$1K", '#ffffff', 'black'),
                ("$2.5K", '#ff0000', 'white')
            ]
            default = "$10"

        for i, (text, bg_color, fg_color) in enumerate(chip_configs):
            cell = tk.Frame(self.chip_container, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2, 2, 49, 49, fill=bg_color, outline='black')
            chip_canvas.create_text(25.5, 25.5, text=text, fill=fg_color, font=('Arial', 12, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text

        self.select_chip(default)

    # ---------- 规则说明 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("I Love Flush 游戏规则")
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
        I Love Flush 游戏规则

        1. 下注阶段：
           - 底注（必须）
           - 同花边注（可选）
           - 同花顺边注（可选）

        2. 发牌：
           - 玩家和庄家各发7张牌
           - 玩家牌全部明牌，庄家牌全部暗牌

        3. 系统自动对玩家牌排序：
           - 按花色分组，组内降序，组间按最大牌降序
           - 选出同花牌（数量最多的花色）并下移10px高亮

        4. 决策：
           - 弃牌：输掉底注和加注，但同花注和同花顺注仍按牌型赔付
           - 下注1倍（加注 = 底注×1）
           - 下注2倍（需同花牌≥5张）
           - 下注3倍（需同花牌≥6张）

        5. 庄家开牌：
           - 庄家牌全部翻开，同样排序并选出同花牌
           - 合格条件：同花牌数量≥3 且 最大牌≥9

        6. 结算：
           - 不合格：底注1:1，加注退还
           - 合格后比较双方同花牌：
               * 先比数量，多者胜
               * 数量相同则逐张比大小
           - 玩家胜：底注1:1，加注1:1
           - 庄家胜：底注和加注全输
           - 平手：底注和加注退回

        7. 边注赔付（按玩家牌型，无论是否弃牌）：
           同花边注（按玩家同花张数）：
           7张: 300:1   6张: 30:1   5张: 6:1   4张: 3:1
           （赔率表示赢的倍数，返还时包含本金）

           同花顺边注（按玩家最长同花顺长度）：
           7张: 8000:1  6张: 1000:1  5张: 100:1  4张: 60:1  3张: 7:1

        注：加注赔率均为1:1，无论牌型。
        """
        tk.Label(content_frame, text=rules_text, font=('微软雅黑',11),
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

    # ---------- 更新手牌标签 ----------
    def update_hand_labels(self):
        if self.game.player_hand and len(self.game.player_hand)==7:
            flush, cnt = get_flush_cards(self.game.player_hand)
            label_text = f"玩家 - {cnt}张同花" if cnt else "玩家"
            self.player_label.config(text=label_text)
        if self.game.dealer_hand and len(self.game.dealer_hand)==7:
            # 检查庄家牌是否已翻开（所有牌都为True）或者阶段为showdown或folded
            if all(self.game.cards_revealed["dealer"]) or self.game.stage == "showdown" or self.game.folded:
                flush, cnt = get_flush_cards(self.game.dealer_hand)
                label_text = f"庄家 - {cnt}张同花" if cnt else "庄家"
                self.dealer_label.config(text=label_text)
            else:
                self.dealer_label.config(text="庄家")

    # ---------- 开始游戏 ----------
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.flush_bet = int(self.flush_bet_var.get())
            self.straight_flush_bet = int(self.straight_flush_bet_var.get())

            if self.high_bet_mode:
                min_ante, max_ante, max_side = 100, 50000, 12500
            else:
                min_ante, max_ante, max_side = 10, 10000, 2500

            if self.ante < min_ante:
                messagebox.showerror("错误", f"底注至少需要{min_ante}块")
                return
            if self.ante > max_ante:
                self.ante = max_ante
                self.ante_var.set(str(max_ante))
                messagebox.showwarning("下注限制", f"底注上限为{max_ante}，已自动调整")
            if self.flush_bet > max_side:
                self.flush_bet = max_side
                self.flush_bet_var.set(str(max_side))
            if self.straight_flush_bet > max_side:
                self.straight_flush_bet = max_side
                self.straight_flush_bet_var.set(str(max_side))

            total_bet = self.ante + self.flush_bet + self.straight_flush_bet
            if self.balance < total_bet:
                messagebox.showerror("错误", "余额不足以支付所有下注！")
                return
            self.balance -= total_bet
            self.game_in_progress = True

            self.last_bet = {
                'ante': self.ante,
                'flush': self.flush_bet,
                'straight_flush': self.straight_flush_bet,
            }
            if self.repeat_bet_btn:
                self.repeat_bet_btn.config(state=tk.NORMAL)
            self.update_balance()

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.last_win_label.config(text="上局获胜: $0.00")

            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.flush_bet = self.flush_bet
            self.game.straight_flush_bet = self.straight_flush_bet
            self.game.play_bet = 0
            self.game.play_multiplier = 0

            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()

            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            self.card_positions = {}
            for i in range(7):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*105,0)}
                self.animation_queue.append(card_id)
            for i in range(7):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*105,0)}
                self.animation_queue.append(card_id)

            for widget in self.btn_frame.winfo_children():
                widget.destroy()

            self.stage_label.config(text="决策")
            self.status_label.config(text="等待牌排序完成...")

            self.ante_display.unbind("<Button-1>")
            self.flush_display.unbind("<Button-1>")
            self.straight_flush_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")

            self.animate_deal()

        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    # ---------- 动画发牌 ----------
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
            card = self.game.player_hand[idx] if idx < len(self.game.player_hand) else None
        else:
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hand[idx] if idx < len(self.game.dealer_hand) else None

        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(x=self.card_positions[card_id]["current"][0],
                         y=self.card_positions[card_id]["current"][1]+20,
                         width=100, height=140)
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
            cx, cy = card_label.winfo_x(), card_label.winfo_y()
            tx, ty = card_label.target_pos
            dx, dy = tx-cx, ty-cy
            dist = math.hypot(dx,dy)
            if dist < 5:
                card_label.place(x=tx, y=ty, width=100, height=140)
                card_label.is_moving = False
                if card_label.target_pos == (50,50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                self.after(20, self.animate_deal)
                return
            step_x, step_y = dx*0.2, dy*0.2
            card_label.place(x=cx+step_x, y=cy+step_y, width=100, height=140)
            self.after(20, lambda: self.animate_card_move(card_label))
        except tk.TclError:
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)

    # ---------- 翻开玩家牌 ----------
    def reveal_player_cards(self):
        for i, lbl in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["player"][i] = True
        self.update_hand_labels()
        self.after(1000, self.after_player_reveal)

    def after_player_reveal(self):
        self.sort_and_highlight_player()

    # ---------- 排序与下移（玩家）使用新排序函数 ----------
    def sort_and_highlight_player(self):
        hand = self.game.player_hand
        if not hand:
            return
        # 使用新的分组排序
        sorted_hand = sort_hand_by_groups(hand)

        # 获取同花牌（用于下移）
        flush, cnt = get_flush_cards(hand)  # 注意这里用原手牌判断同花
        flush_cards = flush

        labels = list(self.player_cards_frame.winfo_children())
        start_pos = {l: float(l.place_info()['x']) for l in labels if l.winfo_exists()}
        target = {}
        for idx, card in enumerate(sorted_hand):
            for l in labels:
                if hasattr(l, 'card') and l.card == card:
                    target[l] = idx * 105
                    break

        steps = 15
        interval = 50
        data = []
        for l in start_pos:
            dx = (target[l] - start_pos[l]) / steps
            data.append((l, start_pos[l], dx))

        def step(cnt):
            if cnt > steps:
                for l,_,_ in data:
                    if l.winfo_exists():
                        l.place(x=target[l])
                self.game.player_hand = sorted_hand
                # 延迟0.5秒后，平滑下移同花牌
                self.after(500, lambda: self.animate_down(flush_cards, self.player_cards_frame))
                self.show_decision_buttons()
                return
            for l,start_x,dx in data:
                if l.winfo_exists():
                    l.place(x=start_x + dx*cnt)
            self.after(interval, lambda: step(cnt+1))
        step(1)

    # ---------- 庄家排序与下移（使用新排序函数） ----------
    def sort_dealer_and_settle(self):
        hand = self.game.dealer_hand
        sorted_hand = sort_hand_by_groups(hand)
        flush, cnt = get_flush_cards(hand)
        flush_cards = flush

        labels = list(self.dealer_cards_frame.winfo_children())
        start_pos = {l: float(l.place_info()['x']) for l in labels if l.winfo_exists()}
        target = {}
        for idx, card in enumerate(sorted_hand):
            for l in labels:
                if hasattr(l, 'card') and l.card == card:
                    target[l] = idx * 105
                    break
        steps = 15
        interval = 50
        data = []
        for l in start_pos:
            dx = (target[l] - start_pos[l]) / steps
            data.append((l, start_pos[l], dx))

        def step(cnt):
            if cnt > steps:
                for l,_,_ in data:
                    if l.winfo_exists():
                        l.place(x=target[l])
                self.game.dealer_hand = sorted_hand
                self.update_hand_labels()
                # 延迟0.5秒后，平滑下移庄家的同花牌
                self.after(500, lambda: self.animate_down(flush_cards, self.dealer_cards_frame))
                # 再延迟0.5秒后结算（确保下移动画完成）
                self.after(1000, self.settle_showdown)
                return
            for l,start_x,dx in data:
                if l.winfo_exists():
                    l.place(x=start_x + dx*cnt)
            self.after(interval, lambda: step(cnt+1))
        step(1)

    # ---------- 平滑下移动画 ----------
    def animate_down(self, cards, frame):
        """将卡片列表中的牌下移10px，使用平滑动画（5步）"""
        labels = [l for l in frame.winfo_children() if hasattr(l, 'card') and l.card in cards]
        if not labels:
            return
        steps = 5
        interval = 50
        start_y = {l: float(l.place_info()['y']) if l.place_info() else 0 for l in labels}
        delta = 10.0 / steps
        def step(cnt):
            if cnt > steps:
                for l in labels:
                    if l.winfo_exists():
                        l.place(y=start_y[l] + 10)
                return
            for l in labels:
                if l.winfo_exists():
                    l.place(y=start_y[l] + delta * cnt)
            self.after(interval, lambda: step(cnt+1))
        step(1)

    # ---------- 翻转动画 ----------
    def flip_card_animation(self, card_label):
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.animate_flip(card_label, front_img, 0)

    def animate_flip(self, card_label, front_img, step):
        steps = 17
        orig_w, orig_h = 100, 140

        # 结束条件：恢复正面全尺寸图片
        if step > steps:
            card_label.is_face_up = True
            self.animation_in_progress = False
            tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
            card_label.place(x=tx, y=ty, width=orig_w, height=orig_h)
            card_label.config(image=front_img)
            return

        # 计算当前帧的宽度比例（前半段背面缩窄，后半段正面展开）
        half = steps // 2
        if step <= half:
            ratio = 1 - (step / float(half))        # 1 → 0
            use_back = True
        else:
            ratio = (step - half) / float(half)     # 0 → 1
            use_back = False

        w = max(1, int(orig_w * ratio))            # 当前宽度（至少1px）

        # 从缓存的原始图像生成缩放后的 PhotoImage
        # 注意：front_img 是完整正面图，但我们需要根据 use_back 选择图像源
        if use_back:
            # 使用背面图像（从 original_images 中获取“back”）
            img_key = "back"
            if img_key in self.original_images:
                pil_img = self.original_images[img_key].resize((w, orig_h), Image.LANCZOS)
            else:
                # 若没有背面原始图，则用当前 back_image 的原始尺寸? 这里直接使用 self.back_image 的原始图像？但 self.back_image 已经是 PhotoImage，无法缩放。
                # 保险做法：使用已加载的背面 PIL 原图（若存在）
                pil_img = self.original_images.get("back", Image.new('RGB', (orig_w, orig_h), 'green'))
                pil_img = pil_img.resize((w, orig_h), Image.LANCZOS)
        else:
            # 正面：从 original_images 中获取对应牌的原图（卡牌原图未缩放）
            # 根据 card_label.card 获取 key
            card = card_label.card
            key = (card.suit, card.rank)
            pil_img = self.original_images.get(key)
            if pil_img is None:
                # 容错：用 front_img 的原始图像？但 front_img 是 PhotoImage，无法获取原图。
                # 这里我们假设 original_images 中一定有该牌，因为 _load_assets 已加载。
                # 若没有，则生成一个占位图
                pil_img = Image.new('RGB', (orig_w, orig_h), 'gray')
            pil_img = pil_img.resize((w, orig_h), Image.LANCZOS)

        # 转换为 PhotoImage 并保存引用防止被垃圾回收
        scaled_img = ImageTk.PhotoImage(pil_img)
        if not hasattr(self, '_temp_flip_images'):
            self._temp_flip_images = {}
        self._temp_flip_images[card_label] = scaled_img   # 用 card_label 作为 key

        # 更新 Label 显示
        tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
        offset = (orig_w - w) // 2      # 水平居中
        card_label.config(image=scaled_img)
        card_label.place(x=tx + offset, y=ty, width=w, height=orig_h)

        # 继续下一帧
        self.after(30, lambda: self.animate_flip(card_label, front_img, step + 1))

    # ---------- 决策按钮 ----------
    def show_decision_buttons(self):
        self.clear_btn_frame()
        # 四列等宽
        for i in range(4):
            self.btn_frame.grid_columnconfigure(i, weight=1)

        flush, cnt = get_flush_cards(self.game.player_hand)
        self.player_flush_count = cnt

        btn_width = 9
        self.fold_btn = tk.Button(
            self.btn_frame, text="弃牌", command=self.fold_action,
            font=('Arial',12,'bold'), bg='#F44336', fg='white', width=btn_width
        )
        self.fold_btn.grid(row=0, column=0, padx=2, sticky='ew')

        self.btn_1 = tk.Button(
            self.btn_frame, text="下注1倍", command=lambda: self.set_multiplier(1),
            font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=btn_width
        )
        self.btn_1.grid(row=0, column=1, padx=2, sticky='ew')

        self.btn_2 = tk.Button(
            self.btn_frame, text="下注2倍", command=lambda: self.set_multiplier(2),
            font=('Arial',12,'bold'), bg='#FF9800', fg='white', width=btn_width,
            state=tk.NORMAL if cnt >= 5 else tk.DISABLED
        )
        self.btn_2.grid(row=0, column=2, padx=2, sticky='ew')

        self.btn_3 = tk.Button(
            self.btn_frame, text="下注3倍", command=lambda: self.set_multiplier(3),
            font=('Arial',12,'bold'), bg='#2196F3', fg='white', width=btn_width,
            state=tk.NORMAL if cnt >= 6 else tk.DISABLED
        )
        self.btn_3.grid(row=0, column=3, padx=2, sticky='ew')

        self.update_play_buttons()
        self.status_label.config(text="选择加注倍数，或弃牌")

    def update_play_buttons(self):
        if not hasattr(self, 'btn_1'):
            return
        ante = self.game.ante
        if self.balance < ante * 1:
            self.btn_1.config(state=tk.DISABLED)
        else:
            self.btn_1.config(state=tk.NORMAL)
        if self.player_flush_count >= 5 and self.balance >= ante * 2:
            self.btn_2.config(state=tk.NORMAL)
        else:
            self.btn_2.config(state=tk.DISABLED)
        if self.player_flush_count >= 6 and self.balance >= ante * 3:
            self.btn_3.config(state=tk.NORMAL)
        else:
            self.btn_3.config(state=tk.DISABLED)

    def set_multiplier(self, mult):
        play_bet = self.game.ante * mult
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足支付加注")
            return
        
        self.fold_btn.config(state=tk.DISABLED)
        self.btn_1.config(state=tk.DISABLED)
        self.btn_2.config(state=tk.DISABLED)
        self.btn_3.config(state=tk.DISABLED)

        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        self.game.play_multiplier = mult
        self.play_amount_var.set(str(play_bet))

        total = self.game.ante + self.game.flush_bet + self.game.straight_flush_bet + play_bet
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")

        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)

    def fold_action(self):
        # 立即禁用所有决策按钮
        self.fold_btn.config(state=tk.DISABLED)
        self.btn_1.config(state=tk.DISABLED)
        self.btn_2.config(state=tk.DISABLED)
        self.btn_3.config(state=tk.DISABLED)

        self.game.folded = True
        self.status_label.config(text="您已弃牌，正在结算边注...")
        self.ante_var.set("0")
        self.play_amount_var.set("0")
        # 注意：边注金额暂时不清零，等结算后显示赢/输
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        # 翻开庄家牌并排序（强制弃牌流程）
        self.reveal_dealer_cards(forced=True)

    # ---------- 摊牌 ----------
    def show_showdown(self):
        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.reveal_dealer_cards()

    def reveal_dealer_cards(self, forced=False):
        for i, lbl in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["dealer"][i] = True
        self.update_hand_labels()
        if forced:
            # 弃牌时也执行庄家排序，但结算用 settle_fold
            self.after(1000, self.sort_dealer_for_fold)
        else:
            self.after(1000, self.sort_dealer_and_settle)

    def sort_dealer_for_fold(self):
        """弃牌时单独对庄家牌排序并更新标签，然后结算弃牌"""
        hand = self.game.dealer_hand
        sorted_hand = sort_hand_by_groups(hand)
        flush, cnt = get_flush_cards(hand)
        flush_cards = flush

        labels = list(self.dealer_cards_frame.winfo_children())
        start_pos = {l: float(l.place_info()['x']) for l in labels if l.winfo_exists()}
        target = {}
        for idx, card in enumerate(sorted_hand):
            for l in labels:
                if hasattr(l, 'card') and l.card == card:
                    target[l] = idx * 105
                    break
        steps = 15
        interval = 50
        data = []
        for l in start_pos:
            dx = (target[l] - start_pos[l]) / steps
            data.append((l, start_pos[l], dx))

        def step(cnt):
            if cnt > steps:
                for l, _, _ in data:
                    if l.winfo_exists():
                        l.place(x=target[l])
                self.game.dealer_hand = sorted_hand
                self.update_hand_labels()
                # 延迟0.5秒后，平滑下移庄家的同花牌
                self.after(500, lambda: self.animate_down(flush_cards, self.dealer_cards_frame))
                # 再延迟0.5秒后结算弃牌（确保下移动画完成）
                self.after(1000, self.settle_fold)
                return
            for l, start_x, dx in data:
                if l.winfo_exists():
                    l.place(x=start_x + dx * cnt)
            self.after(interval, lambda: step(cnt + 1))
        step(1)

    # ---------- 计算边注赢额（返还总额） ----------
    def compute_side_bet_wins(self):
        """返回 (flush_win, sf_win) 分别为同花注和同花顺注的返还总额（包含本金）"""
        flush_win = 0
        sf_win = 0
        if self.game.flush_bet > 0:
            pcnt = get_flush_cards(self.game.player_hand)[1]
            if pcnt in FLUSH_PAYOUT:
                flush_win = self.game.flush_bet * (FLUSH_PAYOUT[pcnt] + 1)  # 返还本金+赢
        if self.game.straight_flush_bet > 0:
            sf_len = get_longest_straight_flush(self.game.player_hand)
            if sf_len in STRAIGHT_FLUSH_PAYOUT:
                sf_win = self.game.straight_flush_bet * (STRAIGHT_FLUSH_PAYOUT[sf_len] + 1)
        return flush_win, sf_win

    # ---------- 结算弃牌 ----------
    def settle_fold(self):
        # 计算边注（玩家手牌已排序，直接用）
        flush_win, sf_win = self.compute_side_bet_wins()
        total_winnings = flush_win + sf_win
        self.balance += total_winnings
        self.update_balance()
        self.last_win = total_winnings
        self.last_win_label.config(text=f"上局获胜: ${total_winnings:.2f}")

        # 更新边注显示
        if flush_win > 0:
            self.flush_bet_var.set(str(flush_win))
            self.flush_display.config(bg='gold')
        else:
            self.flush_bet_var.set("0")
            self.flush_display.config(bg='white')
        if sf_win > 0:
            self.straight_flush_bet_var.set(str(sf_win))
            self.straight_flush_display.config(bg='gold')
        else:
            self.straight_flush_bet_var.set("0")
            self.straight_flush_display.config(bg='white')

        # 底注和加注显示为0（已输）
        self.ante_var.set("0")
        self.play_amount_var.set("0")
        self.ante_display.config(bg='white')
        play_widget = self.bet_widgets.get("play_amount")
        if play_widget:
            play_widget.config(bg='white')
        self.status_label.config(text="您已弃牌")

        self.show_restart_button()
        self._save_history({"fold": True, "total_winnings": total_winnings, "flush_win": flush_win, "sf_win": sf_win})

    # ---------- 结算摊牌 ----------
    def settle_showdown(self):
        winnings = 0
        details = {"ante":0, "play":0, "flush":0, "straight_flush":0}

        dealer_qual = self.game.dealer_qualifies()
        if not dealer_qual:
            ante_return = self.game.ante * 2
            play_return = self.game.play_bet
            winnings += ante_return + play_return
            details["ante"] = ante_return
            details["play"] = play_return
            winner = "player"
        else:
            player_flush, pcnt = get_flush_cards(self.game.player_hand)
            dealer_flush, dcnt = get_flush_cards(self.game.dealer_hand)
            comp = compare_flush_hands(player_flush, dealer_flush)
            if comp > 0:
                ante_return = self.game.ante * 2
                play_return = self.game.play_bet * 2
                winnings += ante_return + play_return
                details["ante"] = ante_return
                details["play"] = play_return
                winner = "player"
            elif comp < 0:
                ante_return = 0
                play_return = 0
                details["ante"] = 0
                details["play"] = 0
                winner = "dealer"
            else:
                ante_return = self.game.ante
                play_return = self.game.play_bet
                winnings += ante_return + play_return
                details["ante"] = ante_return
                details["play"] = play_return
                winner = "push"

        # 计算边注（返还总额）
        flush_win, sf_win = self.compute_side_bet_wins()
        winnings += flush_win + sf_win
        details["flush"] = flush_win
        details["straight_flush"] = sf_win

        self.balance += winnings
        self.update_balance()
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")

        msg = ""
        if not dealer_qual:
            msg = "庄家不合格，底注获胜，加注退还"
        elif winner == "player":
            msg = "本局您赢了！"
        elif winner == "dealer":
            msg = "本局您输了"
        else:
            msg = "本局平手"
        self.status_label.config(text=msg)

        # 更新底注和加注的显示金额及颜色
        self.ante_var.set(str(details["ante"]))
        ante_widget = self.bet_widgets.get("ante")
        if ante_widget:
            ante_bet = self.game.ante
            ante_return = details["ante"]
            if ante_return > ante_bet:
                ante_widget.config(bg='gold')
            elif ante_return == ante_bet and ante_bet > 0:
                ante_widget.config(bg='light blue')
            else:
                ante_widget.config(bg='white')

        self.play_amount_var.set(str(details["play"]))
        play_widget = self.bet_widgets.get("play_amount")
        if play_widget:
            play_bet = self.game.play_bet
            play_return = details["play"]
            if play_bet == 0:
                play_widget.config(bg='white')
            elif play_return > play_bet:
                play_widget.config(bg='gold')
            elif play_return == play_bet:
                play_widget.config(bg='light blue')
            else:
                play_widget.config(bg='white')

        # 更新同花注显示
        if flush_win > 0:
            self.flush_bet_var.set(str(flush_win))
            self.flush_display.config(bg='gold')
        else:
            self.flush_bet_var.set("0")
            self.flush_display.config(bg='white')

        # 更新同花顺注显示
        if sf_win > 0:
            self.straight_flush_bet_var.set(str(sf_win))
            self.straight_flush_display.config(bg='gold')
        else:
            self.straight_flush_bet_var.set("0")
            self.straight_flush_display.config(bg='white')

        self.show_restart_button()
        self._save_history({"winner": winner, "winnings": winnings, "details": details})

    # ---------- 历史记录 ----------
    def _save_history(self, result_info=None):
        try:
            deck = self.game.deck
            if deck is None: return
            save_love_flush_history(deck, self.game.player_hand, self.game.dealer_hand, result_info)
        except Exception as e:
            print(f"保存历史记录出错: {e}")

    # ---------- 重置相关 ----------
    def reset_bets(self):
        self.ante_var.set("0")
        self.flush_bet_var.set("0")
        self.straight_flush_bet_var.set("0")
        self.play_amount_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        ante = self.last_bet['ante']
        flush = self.last_bet['flush']
        sf = self.last_bet['straight_flush']
        if self.high_bet_mode:
            max_ante, max_side = 50000, 12500
            min_ante = 100
        else:
            max_ante, max_side = 10000, 2500
            min_ante = 10
        if ante < min_ante: ante = min_ante
        if ante > max_ante: ante = max_ante
        if flush > max_side: flush = max_side
        if sf > max_side: sf = max_side
        self.ante_var.set(str(ante))
        self.flush_bet_var.set(str(flush))
        self.straight_flush_bet_var.set(str(sf))
        self.status_label.config(text="已应用上次下注金额")
        self.ante_display.config(bg='#E8F5E9')
        self.flush_display.config(bg='#E8F5E9')
        self.straight_flush_display.config(bg='#E8F5E9')
        self.after(800, lambda: self.ante_display.config(bg='white'))
        self.after(800, lambda: self.flush_display.config(bg='white'))
        self.after(800, lambda: self.straight_flush_display.config(bg='white'))

    def show_restart_button(self):
        self.clear_btn_frame()
        restart_btn = tk.Button(
            self.btn_frame, text="再来一局",
            command=lambda: self._on_restart(restart_btn),
            font=('Arial',12,'bold'), bg='#2196F3', fg='white', width=10
        )
        restart_btn.pack()
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def _on_restart(self, btn):
        btn.config(state=tk.DISABLED)
        self.reset_game()

    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if self.active_card_labels:
            self.disable_action_buttons()
            self.animate_collect_cards(auto_reset)
            return
        self._do_reset(auto_reset)

    def _do_reset(self, auto_reset=False):
        self._load_assets()
        self.game.reset_game()
        self.stage_label.config(text="翻牌前")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        # 重置金额显示为0
        self.ante_var.set("0")
        self.flush_bet_var.set("0")
        self.straight_flush_bet_var.set("0")
        self.play_amount_var.set("0")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.active_card_labels = []

        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.flush_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("flush"))
        self.flush_display.bind("<Button-3>", lambda e: self.reset_single_bet("flush", e))
        self.straight_flush_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("straight_flush"))
        self.straight_flush_display.bind("<Button-3>", lambda e: self.reset_single_bet("straight_flush", e))

        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e,t=text: self.select_chip(t))

        self.clear_btn_frame()
        self.add_main_buttons()
        self.current_bet_label.config(text="本局下注: $0.00")
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
        else:
            self.status_label.config(text="设置下注金额并开始游戏")
        self.game_in_progress = False

    def animate_collect_cards(self, auto_reset):
        self.disable_action_buttons()
        self.animate_move_cards_out(auto_reset)

    def animate_move_cards_out(self, auto_reset):
        if not self.active_card_labels:
            self._do_reset(auto_reset)
            return
        for lbl in self.active_card_labels:
            lbl.target_pos = (1200, lbl.winfo_y())
        self.animate_card_out_step(auto_reset)

    def animate_card_out_step(self, auto_reset):
        all_done = True
        for lbl in self.active_card_labels[:]:
            if not hasattr(lbl, 'target_pos') or not lbl.winfo_exists():
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
                continue
            cx = lbl.winfo_x()
            tx, ty = lbl.target_pos
            dx = tx - cx
            if abs(dx) < 5:
                lbl.place(x=tx, y=ty)
                lbl.destroy()
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
                continue
            new_x = cx + dx*0.2
            lbl.place(x=new_x)
            all_done = False
        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset))
        else:
            self._do_reset(auto_reset)

    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)

    # ---------- 显示牌序 ----------
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
                small = orig.resize(small_size, Image.LANCZOS)
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

# =========================================================
# 主入口
# =========================================================
def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return ILoveFlushGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("I Love Flush")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = ILoveFlushGUI(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)

    def close_standalone():
        try:
            update_balance_in_json(page.username, page.balance)
        except Exception:
            pass
        root.destroy()

    page.on_back = lambda final_balance: close_standalone()
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")
