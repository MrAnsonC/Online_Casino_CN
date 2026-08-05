import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import time
import secrets
import subprocess, sys

# =========================================================
# 仿 Three Card Poker UI 颜色与常量
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

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    7: '迷你皇家同花顺',
    6: '同花顺',
    5: '三条',
    4: '顺子',
    3: '同花',
    2: '对子',
    1: '高牌'
}

# Pair Plus支付表
PAIR_PLUS_PAYOUT = {
    7: 100,
    6: 40,
    5: 30,
    4: 6,
    3: 3,
    2: 1
}

# 盲注支付表（打败庄家时）
BLIND_PAYOUT = {
    7: 100,
    6: 20,
    5: 10,
    4: 1,
    3: 1,
    2: 0,
    1: 0
}

# =========================================================
# Progressive 数据存储
# =========================================================
def load_progressive():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    default_progressive = 271288.59
    if not os.path.exists(path):
        return True, default_progressive
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'Progressive_2.50':
                    return False, float(item.get('jackpot', default_progressive))
    except Exception:
        return True, default_progressive
    return True, default_progressive

def save_progressive(jackpot):
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
        if item.get('Games') == 'Progressive_2.50':
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({"Games": "Progressive_2.50", "jackpot": jackpot})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# =========================================================
# 历史记录保存
# =========================================================
def ultimate_three_card_poker_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Ultimate_Three_Card_Poker.json")

def save_ultimate_history(deck, player_cards, dealer_cards, progressive_cards, result_info=None):
    log_path = ultimate_three_card_poker_log_path()
    
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
            print(f"读取历史文件出错: {e}，将使用全新记录")
    
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
        "progressive_cards": [str(c) for c in progressive_cards] if progressive_cards else [],
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner
    elif "winner" not in record["result"]:
        pass
    
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
            self.full_deck = [Card(d["suit"], d["rank"]) for d in shuffle_data["deck"]]
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

# =========================================================
# 手牌评估函数
# =========================================================
def evaluate_three_card_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    if len(set(suits)) == 1 and values == [14, 13, 12]:
        return (7, [14])
    if len(set(suits)) == 1:
        if values == [14, 3, 2]:
            return (6, [3])
        if values[0] - values[1] == 1 and values[1] - values[2] == 1:
            return (6, [values[0]])
    if values[0] == values[1] == values[2]:
        return (5, [values[0]])
    if values == [14, 3, 2]:
        return (4, [3])
    if values[0] - values[1] == 1 and values[1] - values[2] == 1:
        return (4, [values[0]])
    if len(set(suits)) == 1:
        return (3, values)
    if values[0] == values[1]:
        return (2, [values[0], values[2]])
    elif values[1] == values[2]:
        return (2, [values[1], values[0]])
    return (1, values)

def compare_hands(hand1, hand2):
    rank1, values1 = evaluate_three_card_hand(hand1)
    rank2, values2 = evaluate_three_card_hand(hand2)
    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1
    else:
        for v1, v2 in zip(values1, values2):
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        return 0

# =========================================================
# 五张牌分类（用于 Progressive 大奖）
# =========================================================
def classify_five_card_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    is_flush = len(set(suits)) == 1
    is_straight = False
    if len(set(values)) == 5:
        if values[0] - values[4] == 4:
            is_straight = True
        elif values == [14, 5, 4, 3, 2]:
            is_straight = True
    if is_flush and is_straight:
        if values == [14, 13, 12, 11, 10]:
            return 'royal_flush'
        else:
            return 'straight_flush'
    if values[0] == values[3] or values[1] == values[4]:
        return 'four_of_a_kind'
    if (values[0] == values[2] and values[3] == values[4]) or \
       (values[0] == values[1] and values[2] == values[4]):
        return 'full_house'
    if is_flush:
        return 'flush'
    if is_straight:
        return 'straight'
    if values[0] == values[2] or values[1] == values[3] or values[2] == values[4]:
        return 'three_of_a_kind'
    return None

# =========================================================
# 游戏逻辑类（包含 progressive_cards）
# =========================================================
class ThreeCardPokerGame:
    def __init__(self):
        self.reset_game()
        self.progressive_amount = load_progressive()[1]
        self.min_progressive = 271288.59

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.progressive_cards = []
        self.ante = 0
        self.blind = 0
        self.pair_plus = 0
        self.play_bet = 0
        self.progressive_bet = 0
        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False, False, False],
            "dealer": [False, False, False],
            "progressive": [False, False]
        }

    def deal_initial(self):
        self.progressive_cards = self.deck.deal(2)
        self.player_hand = self.deck.deal(3)
        self.dealer_hand = self.deck.deal(3)

    def dealer_qualifies(self):
        hand_rank, _ = evaluate_three_card_hand(self.dealer_hand)
        if hand_rank != 1:
            return True
        max_value = max(card.value for card in self.dealer_hand)
        return max_value >= 12

# =========================================================
# 主 GUI 类
# =========================================================
class ThreeCardPokerGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = ThreeCardPokerGame()
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
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.last_progressive_state = 0
        self.win_details = {
            "ante": 0,
            "blind": 0,
            "pair_plus": 0,
            "play": 0,
            "progressive": 0
        }
        self.bet_widgets = {}
        self.progressive_bet_var = tk.IntVar(value=0)
        self.game_in_progress = False
        self.last_bet = None

        # 高额模式
        self.high_bet_mode = False

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
                        bbox = draw.textbbox((0, 0), text, font=font)
                        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
                        draw.text(((card_size[0]-tw)//2, (card_size[1]-th)//2), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading card image {path}: {e}")
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    draw.text((20, 30), "Error", fill="white", font=font)
                    self.original_images[(suit, rank)] = img_orig
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)

    # ---------- 筹码选择 ----------
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
                chip.create_oval(x1, y1, x2, y2, outline="#2f00ff", width=3, tags="highlight")
                break

    # ---------- 添加筹码到下注区域 ----------
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)

        # 根据高额模式调整限额
        if self.high_bet_mode:
            limits = {"ante": 50000, "pair_plus": 12500}
        else:
            limits = {"ante": 10000, "pair_plus": 2500}

        if bet_type in limits:
            current = float(self.__getattribute__(f"{bet_type}_var").get())
            limit = limits[bet_type]
            if current >= limit:
                messagebox.showwarning("下注限制", f"{bet_type}已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                new_amount = limit
            self.__getattribute__(f"{bet_type}_var").set(str(int(new_amount)))
            if bet_type == "ante":
                self.blind_var.set(self.ante_var.get())  # 盲注自动同步

    def reset_single_bet(self, bet_type, event):
        if bet_type == "ante":
            self.ante_var.set("0")
            self.blind_var.set("0")
        elif bet_type == "pair_plus":
            self.pair_plus_var.set("0")
        if bet_type in self.bet_widgets:
            widget = self.bet_widgets[bet_type]
            widget.config(bg='#FFCDD2')
            self.after(500, lambda: widget.config(bg='white'))

    # ---------- 主界面 UI ----------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧牌桌
        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_canvas.create_rectangle(0, 0, 725, 720, fill=ROOT_BG, outline=GOLD, width=5)

        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=100, y=50, width=400, height=210)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 累进大奖扑克区域（庄家右侧）
        progressive_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        progressive_frame.place(x=520, y=150, width=160, height=400)
        tk.Label(progressive_frame, text="累进大奖扑克", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.progressive_cards_frame = tk.Frame(progressive_frame, bg='#2a4a3c')
        self.progressive_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 中间提示
        self.ante_info_label0 = tk.Label(
            table_canvas,
            text="庄家必须持高牌Q或以上牌型\n没有的为不及格\n\n不及格，底注获胜，加注退还",
            font=('Arial', 22),
            bg=ROOT_BG,
            fg='#FFD700'
        )
        self.ante_info_label0.place(x=300, y=280, anchor='n')

        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=100, y=450, width=400, height=210)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # ===== 右侧控制面板 =====
        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        # 信息卡片
        info_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=3)
        header_info = tk.Frame(info_card, bg=HEADER_BG)
        header_info.pack(fill=tk.X)
        body_info = tk.Frame(info_card, bg=PANEL_BG)
        body_info.pack(fill=tk.X, padx=10, pady=8)
        self.balance_label = tk.Label(body_info, text=f"余额: ${self.balance:,.2f}", font=('Arial', 16, 'bold'),
                                      bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body_info, text="下注", font=('Arial', 16, 'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # 累进大奖卡片
        progressive_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        progressive_card.pack(fill=tk.X, pady=3)
        header_prog = tk.Frame(progressive_card, bg=HEADER_BG)
        header_prog.pack(fill=tk.X)
        tk.Label(header_prog, text="累进大奖", font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_prog = tk.Frame(progressive_card, bg=PANEL_BG)
        body_prog.pack(fill=tk.X, padx=10, pady=8)
        self.progressive_amount_var = tk.StringVar()
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        self.progressive_display = tk.Label(body_prog, textvariable=self.progressive_amount_var,
                                            font=('Arial', 20, 'bold'), bg=PANEL_BG, fg='#A88100')
        self.progressive_display.pack(anchor='center')

        # 限红卡片（点击切换高额模式）
        limit_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        header_limit = tk.Frame(limit_card, bg=HEADER_BG)
        header_limit.pack(fill=tk.X)
        tk.Label(header_limit, text="下注上限", font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_limit = tk.Frame(limit_card, bg=PANEL_BG)
        body_limit.pack(fill=tk.X, padx=10, pady=8)
        table_frame = tk.Frame(body_limit, bg=PANEL_BG, bd=2, relief=tk.SOLID)
        table_frame.pack(fill=tk.X)
        titles = ["底注最低", "底注最高", "对子加注"]
        for col, title in enumerate(titles):
            lbl = tk.Label(table_frame, text=title, font=('Arial', 11, 'bold'),
                           bg=PANEL_BG, fg='#2A1B08', borderwidth=1, relief=tk.SOLID, padx=5, pady=3)
            lbl.grid(row=0, column=col, sticky="nsew")
        # 这些标签需要保存以便更新
        self.min_ante_label = tk.Label(table_frame, text="$10", font=('Arial', 12, 'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=3)
        self.min_ante_label.grid(row=1, column=0, sticky="nsew")
        self.max_ante_label = tk.Label(table_frame, text="$10,000", font=('Arial', 12, 'bold'),
                                       bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=3)
        self.max_ante_label.grid(row=1, column=1, sticky="nsew")
        self.max_pair_plus_label = tk.Label(table_frame, text="$2,500", font=('Arial', 12, 'bold'),
                                            bg=PANEL_BG, fg="#A88100", borderwidth=1, relief=tk.SOLID, padx=5, pady=3)
        self.max_pair_plus_label.grid(row=1, column=2, sticky="nsew")
        for col in range(3):
            table_frame.columnconfigure(col, weight=1)
        # 绑定点击切换高额模式
        for w in [limit_card, header_limit, body_limit, table_frame,
                  self.min_ante_label, self.max_ante_label, self.max_pair_plus_label]:
            w.bind("<Button-1>", self.toggle_high_bet_limits)

        # 筹码与下注卡片
        combined_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined_card.pack(fill=tk.X, pady=3)
        header_combined = tk.Frame(combined_card, bg=HEADER_BG)
        header_combined.pack(fill=tk.X)
        tk.Label(header_combined, text="筹码与下注", font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_combined = tk.Frame(combined_card, bg=PANEL_BG)
        body_combined.pack(fill=tk.X, padx=10, pady=8)
        body_combined.columnconfigure(0, weight=1)
        body_combined.columnconfigure(1, weight=1)
        body_combined.columnconfigure(2, weight=1)

        # 筹码按钮行（将用_rebuild_chips填充）
        chip_row = tk.Frame(body_combined, bg=PANEL_BG)
        chip_row.grid(row=0, column=0, columnspan=3, pady=(0, 8), sticky='ew')
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)
        self.chip_container = chip_row
        self._rebuild_chips()

        # 下注行：累进大奖复选框
        row1 = tk.Frame(body_combined, bg=PANEL_BG)
        row1.grid(row=1, column=0, columnspan=3, sticky='ew', padx=16, pady=5)
        self.progressive_cb = tk.Checkbutton(
            row1, text="累进大奖 ($2.50)", variable=self.progressive_bet_var,
            font=('Arial', 12, "bold"), bg=PANEL_BG, fg='black', selectcolor=PANEL_BG
        )
        self.progressive_cb.pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(row1, text="对子加注:", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.pair_plus_var = tk.StringVar(value="0")
        self.pair_plus_display = tk.Label(row1, textvariable=self.pair_plus_var, font=('Arial', 12),
                                          bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.pair_plus_display.pack(side=tk.LEFT, padx=5)
        self.pair_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("pair_plus"))
        self.pair_plus_display.bind("<Button-3>", lambda e: self.reset_single_bet("pair_plus", e))
        self.bet_widgets["pair_plus"] = self.pair_plus_display

        # 底注
        row_ante = tk.Frame(body_combined, bg=PANEL_BG)
        row_ante.grid(row=2, column=0, columnspan=3, sticky='ew', pady=2)
        tk.Label(row_ante, text="           底注:", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row_ante, textvariable=self.ante_var, font=('Arial', 12),
                                    bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row_ante, text="=", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=5)
        self.blind_var = tk.StringVar(value="0")
        self.blind_display = tk.Label(row_ante, textvariable=self.blind_var, font=('Arial', 12),
                                    bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.blind_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["blind"] = self.blind_display
        tk.Label(row_ante, text=": 盲注", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=5)

        # 加注显示
        row4 = tk.Frame(body_combined, bg=PANEL_BG)
        row4.grid(row=4, column=0, columnspan=3, sticky='ew', pady=4)
        tk.Label(row4, text="           加注:", font=('Arial', 12, "bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(row4, textvariable=self.play_var, font=('Arial', 12),
                                     bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.play_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["play"] = self.play_display

        # 操作卡片
        action_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        action_card.pack(fill=tk.X, pady=3)
        header_action = tk.Frame(action_card, bg=HEADER_BG)
        header_action.pack(fill=tk.X)
        tk.Label(header_action, text="操作", font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_action = tk.Frame(action_card, bg=PANEL_BG)
        body_action.pack(fill=tk.X, padx=10, pady=8)

        self.status_label = tk.Label(
            body_action, text="设置下注金额并开始游戏", font=('Arial', 12, 'bold'),
            bg=PANEL_BG, fg='#2A1B08', height=1
        )
        self.status_label.pack(fill=tk.X, pady=4)

        self.btn_frame = tk.Frame(body_action, bg=PANEL_BG)
        self.btn_frame.pack(fill=tk.X, pady=5)
        self.add_main_buttons()

        # 底部信息卡片
        info_bottom_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_bottom_card.pack(fill=tk.X, pady=3)
        body_bottom = tk.Frame(info_bottom_card, bg=PANEL_BG)
        body_bottom.pack(fill=tk.X, padx=10, pady=8)

        self.current_bet_label = tk.Label(
            body_bottom, text="本局下注: $0.00", font=('Arial', 12), bg=PANEL_BG, fg='black'
        )
        self.current_bet_label.pack(anchor='w')
        row_last = tk.Frame(body_bottom, bg=PANEL_BG)
        row_last.pack(fill=tk.X, pady=2)
        self.last_win_label = tk.Label(
            row_last, text="上局获胜: $0.00", font=('Arial', 12), bg=PANEL_BG, fg='black'
        )
        self.last_win_label.pack(side=tk.LEFT)
        self.info_button = tk.Button(
            row_last, text="ℹ️", command=self.show_game_instructions,
            bg='#4B8BBE', fg='white', font=('Arial', 12), width=2, relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)

        self.action_frame = body_action

    # ---------- 高额模式相关 ----------
    def toggle_high_bet_limits(self, event=None):
        if self.game_in_progress:
            return
        current_password = time.strftime("%H%M")
        if not self.high_bet_mode:
            pwd = simpledialog.askstring("高额下注", "请输入密码：", parent=self)
            if pwd is None:
                return
            if pwd.strip() != current_password:
                messagebox.showerror("错误", "密码错误")
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
            self.max_pair_plus_label.config(text="$12,500")
        else:
            self.min_ante_label.config(text="$10")
            self.max_ante_label.config(text="$10,000")
            self.max_pair_plus_label.config(text="$2,500")

    def _rebuild_chips(self):
        # 清空现有筹码
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

    # ---------- 重建筹码（已在 _rebuild_chips 中实现）----------

    def _rebuild_chips_old(self):  # 保留旧方法名以防引用，但实际使用新方法
        self._rebuild_chips()

    # ---------- 按钮框架管理 ----------
    def clear_btn_frame(self):
        for widget in self.btn_frame.winfo_children():
            widget.destroy()

    def add_main_buttons(self):
        self.clear_btn_frame()
        self.reset_bets_button = tk.Button(
            self.btn_frame, text="重设金额", command=self.reset_bets,
            font=('Arial', 12, 'bold'), bg='#F44336', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)
        self.repeat_bet_btn = tk.Button(
            self.btn_frame, text="重复上局下注", command=self.apply_last_bet,
            font=('Arial', 12, 'bold'), bg='#FFC107', fg='black',
            relief=tk.RAISED, bd=2, cursor="hand2", width=12,
            state=tk.NORMAL if self.last_bet is not None else tk.DISABLED
        )
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=5)
        self.start_button = tk.Button(
            self.btn_frame, text="开始游戏", command=self.start_game,
            font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

    # ---------- 游戏规则说明 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("终极三张牌扑克游戏规则")
        win.geometry("800x700")
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
    终极三张牌扑克 游戏规则

    1. 下注阶段:
    - 底注和盲注必须相等（金额自动同步）
    - 可选择对子加注和累进大奖（$2.50）
    - 点击"开始游戏"开始

    2. 发牌与决策:
    - 玩家、庄家各发三张牌，另外发两张“累进大奖扑克”牌（庄家右侧）
    - 玩家牌朝上，庄家及累进牌朝下
    - 玩家可选择:
        * 弃牌：输掉底注、盲注，保留对子加注和累进大奖结果
        * 下注1倍：加注金额等于底注
        * 下注3倍：只有当手牌为"一对"或更好时才可选用

    3. 结算规则:
    - 庄家必须持高牌Q或以上牌型才合格

    - 底注:
        * 庄家不合格: 退还
        * 庄家合格且玩家赢: 1:1
        * 庄家合格且玩家输: 输
        * 平局: 退还

    - 加注:
        * 玩家赢: 1:1
        * 玩家输: 输
        * 平局: 退还
        * 庄家不合格时，加注正常结算（基于牌型比较）

    - 盲注: 按支付表（基于牌型比较），庄家不合格时同样正常结算

    - 对子加注: 按原支付表（与庄家无关）

    - 累进大奖（$2.50下注）:
        * 将玩家的3张牌与2张累进牌组合成5张牌
        * 支付表见下方
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

        # ---- 对子加注与盲注支付表（合并） ----
        tk.Label(
            content_frame,
            text="对子加注 & 盲注支付表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        combined_frame = tk.Frame(content_frame, bg='#F0F0F0')
        combined_frame.pack(fill=tk.X, padx=20, pady=5)

        # 表头：牌型 | 对子加注 | 盲注（打败庄家时）
        headers = ["牌型", "对子加注", "盲注（含本金）"]
        combined_data = [
            ("迷你皇家同花顺", "100:1", "100:1"),
            ("同花顺", "40:1", "20:1"),
            ("三条", "30:1", "10:1"),
            ("顺子", "6:1", "1:1"),
            ("同花", "3:1", "1:1"),
            ("对子", "1:1", "0:1（退还本金）"),
            ("高牌", "-", "0:1（退还本金）"),
        ]

        for col, h in enumerate(headers):
            tk.Label(
                combined_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        for r, row_data in enumerate(combined_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    combined_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        for c in range(len(headers)):
            combined_frame.columnconfigure(c, weight=1)

        # ---- 累进大奖支付表（独立） ----
        tk.Label(
            content_frame,
            text="累进大奖支付表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        progressive_frame = tk.Frame(content_frame, bg='#F0F0F0')
        progressive_frame.pack(fill=tk.X, padx=20, pady=5)

        headers_prog = ["牌型", "赔付"]
        progressive_data = [
            ("皇家同花顺", "100%"),
            ("同花顺", "10%"),
            ("四条", "$1,250"),
            ("葫芦", "$375"),
            ("同花", "$250")
        ]

        for col, h in enumerate(headers_prog):
            tk.Label(
                progressive_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        for r, row_data in enumerate(progressive_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    progressive_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        for c in range(len(headers_prog)):
            progressive_frame.columnconfigure(c, weight=1)

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # ---------- 更新余额 ----------
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")

    # ---------- 更新手牌标签 ----------
    def update_hand_labels(self):
        if self.game.player_hand:
            player_eval = evaluate_three_card_hand(self.game.player_hand)
            player_hand_name = HAND_RANK_NAMES[player_eval[0]] if player_eval else ""
            self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")
        if self.game.stage == "showdown" or self.game.folded:
            if self.game.dealer_hand:
                dealer_eval = evaluate_three_card_hand(self.game.dealer_hand)
                dealer_hand_name = HAND_RANK_NAMES[dealer_eval[0]] if dealer_eval else ""
                self.dealer_label.config(text=f"庄家 - {dealer_hand_name}" if dealer_hand_name else "庄家")

    # ---------- 开始游戏 ----------
    def start_game(self):
        self.clear_btn_frame()
        try:
            self.ante = int(self.ante_var.get())
            self.blind = int(self.blind_var.get())
            self.pair_plus = int(self.pair_plus_var.get())
            self.progressive_bet = 2.5 if self.progressive_bet_var.get() == 1 else 0
            self.last_progressive_state = self.progressive_bet_var.get()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
            self.add_main_buttons()
            return

        if self.ante != self.blind:
            messagebox.showerror("错误", "底注和盲注必须相等！")
            self.blind_var.set(self.ante_var.get())
            self.blind = self.ante
            self.add_main_buttons()
            return

        # 根据高额模式调整限额
        if self.high_bet_mode:
            min_ante, max_ante, max_pair = 100, 50000, 12500
        else:
            min_ante, max_ante, max_pair = 10, 10000, 2500

        if self.ante < min_ante:
            messagebox.showerror("错误", f"底注至少需要{min_ante}元")
            self.add_main_buttons()
            return
        if self.ante > max_ante:
            messagebox.showwarning("下注限制", f"底注不能超过${max_ante:,}")
            self.ante_var.set(str(max_ante))
            self.blind_var.set(str(max_ante))
            self.ante = max_ante
            self.blind = max_ante
            self.add_main_buttons()
            return
        if self.pair_plus > max_pair:
            messagebox.showwarning("下注限制", f"对子加注不能超过${max_pair:,}")
            self.pair_plus_var.set(str(max_pair))
            self.pair_plus = max_pair
            self.add_main_buttons()
            return

        total_bet = self.ante + self.blind + self.pair_plus + self.progressive_bet
        if self.balance < total_bet:
            messagebox.showwarning("警告", "余额不足")
            self.add_main_buttons()
            return

        self.last_bet = {
            "ante": self.ante,
            "blind": self.blind,
            "pair_plus": self.pair_plus,
            "progressive": 1 if self.progressive_bet else 0,
        }
        if hasattr(self, 'repeat_bet_btn') and self.repeat_bet_btn.winfo_exists():
            self.repeat_bet_btn.config(state=tk.NORMAL)

        self.balance -= total_bet
        self.update_balance()
        self.last_win_label.config(text="上局获胜: $0.00")
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        self.game.reset_game()
        self.game.deal_initial()
        self.game.ante = self.ante
        self.game.blind = self.blind
        self.game.pair_plus = self.pair_plus
        self.game.progressive_bet = self.progressive_bet
        self.game.play_bet = 0

        for widget in self.dealer_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.player_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.progressive_cards_frame.winfo_children():
            widget.destroy()

        self.animation_queue = []
        self.animation_in_progress = False
        self.active_card_labels = []
        self.card_positions = {}

        for i in range(2):
            card_id = f"progressive_{i}"
            self.card_positions[card_id] = {"current": (50, 50), "target": (10, 10 + i * 160)}
            self.animation_queue.append(card_id)
        for i in range(3):
            card_id = f"player_{i}"
            self.card_positions[card_id] = {"current": (50, 50), "target": (i * 120, 0)}
            self.animation_queue.append(card_id)
        for i in range(3):
            card_id = f"dealer_{i}"
            self.card_positions[card_id] = {"current": (50, 50), "target": (i * 120, 0)}
            self.animation_queue.append(card_id)

        self.animate_deal()

        self.stage_label.config(text="决策")
        self.status_label.config(text="做出决策: 弃牌 或 下注1倍/3倍")

        self.disable_bet_controls()

        # 创建决策按钮
        action_button_frame = tk.Frame(self.btn_frame, bg=PANEL_BG)
        action_button_frame.pack()

        self.fold_button = tk.Button(
            action_button_frame, text="弃牌",
            command=self.fold_action,
            state=tk.DISABLED,
            font=('Arial', 12, 'bold'), bg='#F44336', fg='white', width=10
        )
        self.fold_button.pack(side=tk.LEFT, padx=(0, 10))

        self.play_button_1x = tk.Button(
            action_button_frame, text="下注1倍",
            command=lambda: self.play_action(1),
            state=tk.DISABLED,
            font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white', width=10
        )
        self.play_button_1x.pack(side=tk.LEFT, padx=(0, 10))

        self.play_button_3x = tk.Button(
            action_button_frame, text="下注3倍",
            command=lambda: self.play_action(3),
            state=tk.DISABLED,
            font=('Arial', 12, 'bold'), bg='#2196F3', fg='white', width=10
        )
        self.play_button_3x.pack(side=tk.LEFT)

    def disable_bet_controls(self):
        self.ante_display.unbind("<Button-1>")
        self.pair_plus_display.unbind("<Button-1>")
        for chip in self.chip_buttons:
            chip.unbind("<Button-1>")
        self.progressive_cb.config(state=tk.DISABLED)

    # ---------- 动画 ----------
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
        elif card_id.startswith("dealer"):
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hand[idx] if idx < len(self.game.dealer_hand) else None
        else:  # progressive
            frame = self.progressive_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.progressive_cards[idx] if idx < len(self.game.progressive_cards) else None

        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(x=self.card_positions[card_id]["current"][0],
                         y=self.card_positions[card_id]["current"][1] + 20)
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
                self.after(20, self.animate_deal)
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
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["player"][i] = True
        self.update_hand_labels()

        player_rank, _ = evaluate_three_card_hand(self.game.player_hand)
        can_3x = (player_rank >= 2)
        if hasattr(self, 'fold_button') and self.fold_button.winfo_exists():
            self.fold_button.config(state=tk.NORMAL)
        if hasattr(self, 'play_button_1x') and self.play_button_1x.winfo_exists():
            self.play_button_1x.config(state=tk.NORMAL)
        if hasattr(self, 'play_button_3x') and self.play_button_3x.winfo_exists():
            self.play_button_3x.config(state=tk.NORMAL if can_3x else tk.DISABLED)

    def reveal_dealer_cards(self):
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["dealer"][i] = True
        for i, card_label in enumerate(self.progressive_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["progressive"][i] = True
        self.update_hand_labels()

    def flip_card_animation(self, card_label):
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.animate_flip(card_label, front_img, 0)

    def animate_flip(self, card_label, front_img, step):
        steps = 12
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

    # ---------- 游戏动作 ----------
    def play_action(self, multiplier):
        play_bet = self.game.ante * multiplier
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        self.play_var.set(str(play_bet))

        total_bet = self.game.ante + self.game.blind + self.game.pair_plus + play_bet + self.game.progressive_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        if hasattr(self, 'fold_button'): self.fold_button.config(state=tk.DISABLED)
        if hasattr(self, 'play_button_1x'): self.play_button_1x.config(state=tk.DISABLED)
        if hasattr(self, 'play_button_3x'): self.play_button_3x.config(state=tk.DISABLED)

        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)

    def fold_action(self):
        self.game.folded = True
        if hasattr(self, 'fold_button'): self.fold_button.config(state=tk.DISABLED)
        if hasattr(self, 'play_button_1x'): self.play_button_1x.config(state=tk.DISABLED)
        if hasattr(self, 'play_button_3x'): self.play_button_3x.config(state=tk.DISABLED)

        self.reveal_dealer_cards()
        self.update_hand_labels()

        self.stage_label.config(text="结算")
        self.status_label.config(text="游戏结算")

        self.ante_var.set('0')
        self.blind_var.set('0')

        # 结算 Pair Plus
        player_eval = evaluate_three_card_hand(self.game.player_hand)
        pair_plus_win = 0
        if player_eval[0] in PAIR_PLUS_PAYOUT:
            payout = PAIR_PLUS_PAYOUT[player_eval[0]]
            pair_plus_win = self.game.pair_plus * (payout + 1)
            self.balance += pair_plus_win
            self.update_balance()
            self.pair_plus_var.set(str(int(pair_plus_win)))
        else:
            self.pair_plus_var.set("0")

        # 结算 Progressive
        progressive_win = 0
        if self.game.progressive_bet > 0:
            progressive_win = self.calculate_progressive_win()
            if progressive_win > 0:
                self.balance += progressive_win
                self.update_balance()

        self.update_progressive()

        self.ante_display.config(bg='white')
        self.blind_display.config(bg='white')
        self.pair_plus_display.config(bg='gold' if pair_plus_win > 0 else 'white')
        if progressive_win > 0:
            self.progressive_display.config(bg='gold')
        else:
            self.progressive_display.config(bg=PANEL_BG)

        total_win = pair_plus_win + progressive_win
        self.last_win = total_win
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")

        # 保存历史（弃牌）
        result_info = {"fold": True, "total_winnings": total_win}
        save_ultimate_history(self.game.deck, self.game.player_hand, self.game.dealer_hand,
                              self.game.progressive_cards, result_info)

        self.show_restart_button()

    # ---------- 修改后的 calculate_winnings ----------
    def calculate_winnings(self):
        """
        计算各注项结果。
        """
        winnings = 0
        details = {"ante": 0, "blind": 0, "pair_plus": 0, "play": 0, "progressive": 0}

        # 先计算牌型比较
        player_eval = evaluate_three_card_hand(self.game.player_hand)
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)
        dealer_qualifies = self.game.dealer_qualifies()

        # ---- Pair Plus ----
        if player_eval[0] in PAIR_PLUS_PAYOUT:
            payout = PAIR_PLUS_PAYOUT[player_eval[0]]
            pair_plus_win = self.game.pair_plus * (payout + 1)
            winnings += pair_plus_win
            details["pair_plus"] = pair_plus_win

        self.stage_label.config(text="结算")
        self.status_label.config(text="游戏结算")

        # ---- Ante ----
        if not dealer_qualifies:
            ante_win = self.game.ante
        else:
            if comparison > 0:
                ante_win = self.game.ante * 2
            elif comparison == 0:
                ante_win = self.game.ante
            else:
                ante_win = 0
        winnings += ante_win
        details["ante"] = ante_win

        # ---- Play (加注) ----
        if comparison > 0:
            play_win = self.game.play_bet * 2
        elif comparison == 0:
            play_win = self.game.play_bet
        else:
            play_win = 0
        winnings += play_win
        details["play"] = play_win

        # ---- Blind (盲注) ----
        if comparison > 0:
            hand_rank, _ = player_eval
            payout = BLIND_PAYOUT.get(hand_rank, 0)
            blind_win = self.game.blind * (payout + 1)
        elif comparison == 0:
            blind_win = self.game.blind
        else:
            blind_win = 0
        winnings += blind_win
        details["blind"] = blind_win

        return winnings, details

    def show_showdown(self):
        self.reveal_dealer_cards()
        self.update_hand_labels()

        winnings, details = self.calculate_winnings()
        # 暂时存储winnings，后面加上progressive
        self.last_win = winnings
        self.balance += winnings
        self.update_balance()

        self.ante_var.set(str(int(details["ante"])))
        self.blind_var.set(str(int(details["blind"])))
        self.pair_plus_var.set(str(int(details["pair_plus"])))
        self.play_var.set(str(int(details["play"])))

        for bet_type in ["ante", "blind", "pair_plus", "play"]:
            widget = self.bet_widgets.get(bet_type)
            if not widget:
                continue
            win_amount = details[bet_type]
            if bet_type == "ante":
                bet_amt = self.game.ante
            elif bet_type == "blind":
                bet_amt = self.game.blind
            elif bet_type == "pair_plus":
                bet_amt = self.game.pair_plus
            else:
                bet_amt = self.game.play_bet
            if win_amount > bet_amt:
                widget.config(bg='gold')
            elif win_amount == bet_amt and bet_amt > 0:
                widget.config(bg='light blue')
            else:
                widget.config(bg='white')

        progressive_win = 0
        if self.game.progressive_bet > 0:
            progressive_win = self.calculate_progressive_win()
            if progressive_win > 0:
                self.balance += progressive_win
                self.update_balance()
                self.progressive_display.config(bg='gold')
            else:
                self.progressive_display.config(bg=PANEL_BG)
            details["progressive"] = progressive_win
        else:
            details["progressive"] = 0

        # 总赢利 = 普通赢利 + 累进大奖
        total_win = winnings + progressive_win
        self.last_win = total_win
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")

        self.update_progressive()

        # ---- 确定赢家（用于历史记录） ----
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)
        if self.game.folded:
            winner = "fold"
        else:
            if comparison > 0:
                winner = "player"
            elif comparison < 0:
                winner = "dealer"
            else:
                winner = "push"

        result_info = {"winner": winner, "winnings": total_win}
        save_ultimate_history(self.game.deck, self.game.player_hand, self.game.dealer_hand,
                              self.game.progressive_cards, result_info)

        self.show_restart_button()

    # ---------- Progressive 相关 ----------
    def calculate_progressive_win(self):
        # 只检查玩家牌（3张玩家牌 + 2张累进牌）
        player_5 = self.game.player_hand + self.game.progressive_cards
        player_type = classify_five_card_hand(player_5)

        # 新支付表（仅玩家）
        player_payout_map = {
            'royal_flush': ('jackpot', 1.0),      # 奖池100%
            'straight_flush': ('jackpot', 0.1),   # 奖池10%
            'four_of_a_kind': ('fixed', 1250),    # $1250
            'full_house': ('fixed', 375),         # $375
            'flush': ('fixed', 250)               # $250
        }

        win_amount = 0
        if player_type in player_payout_map:
            mode, val = player_payout_map[player_type]
            if mode == 'jackpot':
                win_amount = self.game.progressive_amount * val
            else:  # fixed
                win_amount = val

        if win_amount == 0:
            return 0

        # 从奖池中扣除赢得的金额（并保底）
        self.game.progressive_amount -= win_amount
        if self.game.progressive_amount < self.game.min_progressive:
            self.game.progressive_amount = self.game.min_progressive
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        save_progressive(self.game.progressive_amount)

        # 显示赢奖消息
        hand_name_cn = {
            'royal_flush': '皇家同花顺',
            'straight_flush': '同花顺',
            'four_of_a_kind': '四条',
            'full_house': '葫芦',
            'flush': '同花'
        }
        cn_name = hand_name_cn.get(player_type, player_type.replace('_', ' ').title())
        if player_type == 'royal_flush':
            msg = f"玩家皇家同花顺！赢得奖池的100%：${win_amount:,.2f}"
        elif player_type == 'straight_flush':
            msg = f"玩家同花顺！赢得奖池的10%：${win_amount:,.2f}"
        else:
            msg = f"玩家{cn_name}！赢得${win_amount:,.2f}"

        messagebox.showinfo("累进大奖", msg)
        return win_amount

    def update_progressive(self):
        total_bet = self.game.ante + self.game.blind + self.game.play_bet + self.game.pair_plus + self.game.progressive_bet
        contribution = total_bet * 0.001 + self.game.progressive_bet * 0.95
        self.game.progressive_amount += contribution
        if self.game.progressive_amount < self.game.min_progressive:
            self.game.progressive_amount = self.game.min_progressive
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        save_progressive(self.game.progressive_amount)

    # ---------- 重置与重启 ----------
    def reset_bets(self):
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.pair_plus_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.ante_display.config(bg='#FFCDD2')
        self.blind_display.config(bg='#FFCDD2')
        self.pair_plus_display.config(bg='#FFCDD2')
        self.after(500, lambda: [self.ante_display.config(bg='white'),
                                 self.blind_display.config(bg='white'),
                                 self.pair_plus_display.config(bg='white')])

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        ante = self.last_bet["ante"]
        blind = self.last_bet["blind"]
        pair = self.last_bet["pair_plus"]
        prog = self.last_bet["progressive"]

        # 根据高额模式调整限额
        if self.high_bet_mode:
            max_ante, max_pair = 50000, 12500
            min_ante = 100
        else:
            max_ante, max_pair = 10000, 2500
            min_ante = 10

        if ante < min_ante:
            ante = min_ante
        if ante > max_ante:
            ante = max_ante
        if pair > max_pair:
            pair = max_pair

        self.ante_var.set(str(ante))
        self.blind_var.set(str(blind))   # 保持同步
        self.pair_plus_var.set(str(pair))
        self.progressive_bet_var.set(prog)
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.status_label.config(text="已应用上局下注金额")

    def show_restart_button(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        self.clear_btn_frame()
        self.restart_btn = tk.Button(
            self.btn_frame, text="再来一局",
            command=self.reset_game,
            font=('Arial', 12, 'bold'), bg='#2196F3', fg='white', width=10
        )
        self.restart_btn.pack()
        self.restart_btn.bind("<Button-3>", self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def reset_game(self, auto_reset=False):
        self.restart_btn.config(state=tk.DISABLED)
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if self.active_card_labels:
            self.animate_collect_cards(auto_reset)
            return
        self._do_reset(auto_reset)

    def animate_collect_cards(self, auto_reset):
        self.disable_action_buttons()
        self.animate_move_cards_out(auto_reset)

    def animate_move_cards_out(self, auto_reset):
        if not self.active_card_labels:
            self._do_reset(auto_reset)
            return
        for card_label in self.active_card_labels:
            card_label.target_pos = (1500, card_label.winfo_y())
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
        self.stage_label.config(text="下注")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.pair_plus_var.set("0")
        self.play_var.set("0")
        self.progressive_bet_var.set(self.last_progressive_state)
        # 恢复累进大奖背景
        self.progressive_display.config(bg=PANEL_BG)
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.active_card_labels = []
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.pair_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("pair_plus"))
        self.pair_plus_display.bind("<Button-3>", lambda e: self.reset_single_bet("pair_plus", e))
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        self.progressive_cb.config(state=tk.NORMAL)
        self.clear_btn_frame()
        self.add_main_buttons()
        self.current_bet_label.config(text="本局下注: $0.00")
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
        else:
            self.status_label.config(text="设置下注金额并开始游戏")
        self.game_in_progress = False

    def disable_action_buttons(self):
        self.buttons_disabled = True

    def enable_action_buttons(self):
        self.buttons_disabled = False

    # ---------- 显示牌序 ----------
    def show_card_sequence(self, event):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示", "没有牌序信息")
            return
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("730x750")
        win.resizable(0, 0)
        win.configure(bg='#f0f0f0')
        cut_pos = self.game.deck.start_pos
        cut_label = tk.Label(win, text=f"本局切牌位置: {cut_pos + 1}", font=('Arial', 14, 'bold'), bg='#f0f0f0')
        cut_label.pack(pady=10)
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')

        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        small_size = (60, 90)
        small_images = {}
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
                bbox = draw.textbbox((0, 0), text, font=font)
                tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
                draw.text(((small_size[0]-tw)//2, (small_size[1]-th)//2), text, fill="white", font=font)
                small_images[i] = ImageTk.PhotoImage(img)

        for row in range(6):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X)
            cards_in_row = 9 if row < 5 else 7
            for col in range(cards_in_row):
                card_index = row * 9 + col
                if card_index >= 52:
                    break
                card_container = tk.Frame(row_frame, bg='#f0f0f0')
                card_container.grid(row=0, column=col, padx=5)
                is_cut_position = card_index == self.game.deck.start_pos
                bg_color = 'light blue' if is_cut_position else '#f0f0f0'
                card = self.game.deck.full_deck[card_index]
                card_label = tk.Label(card_container, image=small_images[card_index], bg=bg_color, borderwidth=1, relief="solid")
                card_label.image = small_images[card_index]
                card_label.pack()
                pos_label = tk.Label(card_container, text=str(card_index+1), bg=bg_color, font=('Arial', 9))
                pos_label.pack()

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return ThreeCardPokerGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("Ultimate Three Card Poker")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = ThreeCardPokerGUI(root, actual_balance, actual_user)
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
