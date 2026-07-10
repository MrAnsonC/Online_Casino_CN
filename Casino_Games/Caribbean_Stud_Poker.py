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
# 仿轮盘 UI 颜色（取自 Three_Card_Poker）
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

CARIBBEAN_STUD_PAYOUT = {
    9: 100,  # 皇家同花顺
    8: 50,
    7: 20,
    6: 7,
    5: 5,
    4: 4,
    3: 3,
    2: 2,
    1: 1,
    0: 1
}

FIVE_PLUS_ONE_PAYOUT = {
    9: 1001,
    8: 201,
    7: 101,
    6: 21,
    5: 16,
    4: 11,
    3: 8,
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
# Progressive 文件加载与保存 (Key: 'CSP')
# =========================================================
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    default_jackpot = 271288.59
    if not os.path.exists(path):
        return True, default_jackpot
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'Progressive_2.50':
                    return False, float(item.get('jackpot', default_jackpot))
    except Exception:
        return True, default_jackpot
    return True, default_jackpot

def save_jackpot(jackpot):
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
# 牌局历史日志（加勒比扑克）
# =========================================================
def caribbean_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Caribbean_Stud_Poker.json")

def save_caribbean_history(deck, player_cards, dealer_cards, result_info=None):
    log_path = caribbean_log_path()
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
                    # 旧格式迁移
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
# 扑克牌类与牌堆（与 Three_Card_Poker 一致）
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
# 五张牌评估与比较（保留原逻辑）
# =========================================================
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
        return (1, sorted_values)
    return (0, values)

def compare_hands(hand1, hand2):
    rank1, values1 = evaluate_five_card_hand(hand1)
    rank2, values2 = evaluate_five_card_hand(hand2)
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
        v1_full = sorted([c.value for c in hand1], reverse=True)
        v2_full = sorted([c.value for c in hand2], reverse=True)
        for i in range(len(v1_full)):
            if v1_full[i] > v2_full[i]:
                return 1
            elif v1_full[i] < v2_full[i]:
                return -1
        return 0

def sort_hand_for_display(hand, hand_eval):
    rank = hand_eval[0]
    if rank in [4,8,9]:  # 顺子类
        values = [c.value for c in hand]
        if 14 in values and 2 in values and len(set(values)) == 5:
            return sorted(hand, key=lambda c: 1 if c.value == 14 else c.value)
        else:
            return sorted(hand, key=lambda c: c.value)
    else:
        counts = Counter(c.value for c in hand)
        return sorted(hand, key=lambda c: (counts[c.value], c.value), reverse=True)

# =========================================================
# 游戏逻辑类（加勒比扑克）
# =========================================================
class CaribbeanStudGame:
    def __init__(self):
        self.reset_game()
        self.progressive_amount = load_jackpot()[1]
        self.min_progressive = 271288.59

    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.ante = 0
        self.jackpot_bet = 0
        self.five_plus_one_bet = 0
        self.play_bet = 0
        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False]*5,
            "dealer": [False]*5
        }

    def deal_initial(self):
        self.player_hand = self.deck.deal(5)
        self.dealer_hand = self.deck.deal(5)

    def dealer_qualifies(self):
        if not self.dealer_hand or len(self.dealer_hand) < 5:
            return False
        rank, _ = evaluate_five_card_hand(self.dealer_hand)
        if rank >= 1:
            return True
        has_ace = any(c.rank == 'A' for c in self.dealer_hand)
        has_king = any(c.rank == 'K' for c in self.dealer_hand)
        return has_ace and has_king

# =========================================================
# 主GUI类（仿 Three_Card_Poker 风格）
# =========================================================
class CaribbeanStudGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("加勒⽐梭哈扑克")
        self.geometry("1150x750+50+10")
        self.resizable(0,0)
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = CaribbeanStudGame()
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
        self.last_jackpot_state = 0
        self.win_details = {
            "ante": 0,
            "play": 0,
            "bonus": 0,
            "five_plus_one": 0
        }
        self.bet_widgets = {}
        self.jackpot_bet_var = tk.IntVar(value=0)
        self.five_plus_one_var = tk.StringVar(value="0")
        self.last_game_bet = None

        # 高额模式
        self.high_bet_mode = False
        # 移除固定密码，每次认证时动态生成
        self.game_in_progress = False

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 添加底注监听，联动更新加注
        self.ante_var.trace_add('write', self.on_ante_changed)

    def on_close(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()

    # ---------- 加载扑克牌（交替 Poker1/Poker2） ----------
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

    # ---------- 添加筹码到下注区域 ----------
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
            "five_plus_one": (12500 if self.high_bet_mode else 2500)
        }
        if bet_type in limits:
            current = float(self.__getattribute__(f"{bet_type}_var").get())
            limit = limits[bet_type]
            if current >= limit:
                # 如果已经达到上限，始终提示
                names = {"ante":"底注","five_plus_one":"5+1"}
                messagebox.showwarning("下注限制", f"{names[bet_type]}已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                new_amount = limit
                # 仅当原始金额 > 0 时才弹窗提示，否则静默截断
                if current > 0:
                    names = {"ante":"底注","five_plus_one":"5+1"}
                    messagebox.showwarning("下注限制", f"{names[bet_type]}已达上限，自动调整为 {int(new_amount)}")
            self.__getattribute__(f"{bet_type}_var").set(str(int(new_amount)))

    # ---------- 重置单个下注（右键） ----------
    def reset_single_bet(self, bet_type, event):
        if bet_type == "ante":
            self.ante_var.set("0")
        elif bet_type == "five_plus_one":
            self.five_plus_one_var.set("0")
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
        self.reset_bets_button = tk.Button(
            self.btn_frame, text="重设金额", command=self.reset_bets,
            font=('Arial',12,'bold'), bg='#F44336', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)

        self.repeat_bet_btn = tk.Button(
            self.btn_frame, text="重复上局下注", command=self.apply_last_bet,
            font=('Arial',12,'bold'), bg='#FFC107', fg='black',
            relief=tk.RAISED, bd=2, cursor="hand2", width=12,
            state=tk.NORMAL if self.last_bet is not None else tk.DISABLED
        )
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=5)

        self.start_button = tk.Button(
            self.btn_frame, text="开始游戏", command=self.start_game,
            font=('Arial',12,'bold'), bg='#4CAF50', fg='white',
            relief=tk.RAISED, bd=2, cursor="hand2", width=10
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

    # ---------- 创建主界面 ----------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧牌桌
        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_canvas.create_rectangle(0,0,725,720, fill=ROOT_BG, outline=GOLD, width=5)

        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=60, y=60, width=600, height=230)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 中间提示
        self.ante_info_label = tk.Label(
            table_canvas,
            text="庄家须持有高牌A/K或以上牌型才合格\n庄家不合格的 底注无条件获胜 加注平局",
            font=('Arial',26),
            bg=ROOT_BG,
            fg='#FFD700'
        )
        self.ante_info_label.update_idletasks()
        label_width = self.ante_info_label.winfo_width()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        center_x = (canvas_width - label_width)//2
        self.ante_info_label.place(x=center_x+360, y=330, anchor='n')

        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=60, y=450, width=600, height=230)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial',18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # 右侧控制面板
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

        self.balance_label = tk.Label(body_info, text=f"余额: ${self.balance:,.2f}", font=('Arial',16,'bold'),
                                      bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body_info, text="翻牌前", font=('Arial',16,'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # 累进大奖卡片
        progressive_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        progressive_card.pack(fill=tk.X, pady=3)
        header_prog = tk.Frame(progressive_card, bg=HEADER_BG)
        header_prog.pack(fill=tk.X)
        tk.Label(header_prog, text="累进大奖", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_prog = tk.Frame(progressive_card, bg=PANEL_BG)
        body_prog.pack(fill=tk.X, padx=10, pady=8)
        self.progressive_amount_var = tk.StringVar()
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        self.progressive_display = tk.Label(body_prog, textvariable=self.progressive_amount_var,
                                            font=('Arial',20,'bold'), bg=PANEL_BG, fg='#A88100')
        self.progressive_display.pack(anchor='center')

        # 限红信息卡片（可点击切换高额模式）
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
        # 点击切换高额模式
        for w in [limit_card, header_limit, body_limit, table_frame,
                  self.min_ante_label, self.max_ante_label, self.max_side_label]:
            w.bind("<Button-1>", self.toggle_high_bet_limits)

        # 筹码与下注卡片
        combined_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined_card.pack(fill=tk.X, pady=3)
        header_combined = tk.Frame(combined_card, bg=HEADER_BG)
        header_combined.pack(fill=tk.X)
        tk.Label(header_combined, text="筹码与下注", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_combined = tk.Frame(combined_card, bg=PANEL_BG)
        body_combined.pack(fill=tk.X, padx=10, pady=8)
        body_combined.columnconfigure(0, weight=1)
        body_combined.columnconfigure(1, weight=1)
        body_combined.columnconfigure(2, weight=1)

        # 筹码按钮行
        chip_row = tk.Frame(body_combined, bg=PANEL_BG)
        chip_row.grid(row=0, column=0, columnspan=3, pady=(0,8), sticky='ew')
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)
        self.chip_container = chip_row   # 保存引用，供 _rebuild_chips 使用

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

        # 下注行：底注、5+1、累进大奖
        # 第一行：累进大奖复选框
        row0 = tk.Frame(body_combined, bg=PANEL_BG)
        row0.grid(row=1, column=0, columnspan=3, sticky='ew', padx= 40, pady=2)
        self.jackpot_check = tk.Checkbutton(
            row0, text="累进大奖 ($2.50)", variable=self.jackpot_bet_var,
            font=('Arial',12,"bold"), bg=PANEL_BG, fg='black', selectcolor=PANEL_BG
        )
        self.jackpot_check.pack(side=tk.LEFT)

        # 第二行：底注 和 5+1 并排
        row1 = tk.Frame(body_combined, bg=PANEL_BG)
        row1.grid(row=2, column=0, columnspan=3, sticky='ew', pady=4)
        tk.Label(row1, text="           底注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row1, textvariable=self.ante_var, font=('Arial',12),
                                     bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row1, text="5+1:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(25,5))
        self.five_plus_one_display = tk.Label(row1, textvariable=self.five_plus_one_var, font=('Arial',12),
                                              bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.five_plus_one_display.pack(side=tk.LEFT, padx=5)
        self.five_plus_one_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("five_plus_one"))
        self.five_plus_one_display.bind("<Button-3>", lambda e: self.reset_single_bet("five_plus_one", e))
        self.bet_widgets["five_plus_one"] = self.five_plus_one_display

        # 第三行：加注（可点击切换预下注）
        row2 = tk.Frame(body_combined, bg=PANEL_BG)
        row2.grid(row=3, column=0, columnspan=3, sticky='ew', pady=4)
        tk.Label(row2, text="           加注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(row2, textvariable=self.play_var, font=('Arial',12),
                                     bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.play_display.pack(side=tk.LEFT, padx=5)
        self.play_display.bind("<Button-1>", self.toggle_play_bet)   # 点击切换预下注
        self.bet_widgets["play"] = self.play_display

        # 操作卡片
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

        # 底部信息卡片
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

    # ---------- 底注联动：更新加注 ----------
    def on_ante_changed(self, *args):
        """当底注变化时，如果当前加注不为0，则更新为底注×2"""
        try:
            ante = int(self.ante_var.get())
        except ValueError:
            ante = 0
        current_play = self.play_var.get()
        # 如果当前加注不是"0"或"0.0"，则更新为 ante*2
        if current_play not in ("0", "0.0"):
            self.play_var.set(str(ante * 2))

    # ---------- 高额模式切换 ----------
    def toggle_high_bet_limits(self, event=None):
        if self.game_in_progress:
            return
        # 动态获取当前时间的四位数字作为密码
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

    # ---------- 预下注切换 ----------
    def toggle_play_bet(self, event=None):
        """点击加注格子，在0和底注×2之间循环"""
        try:
            ante = int(self.ante_var.get())
        except ValueError:
            ante = 0
        if ante <= 0:
            messagebox.showwarning("提示", "请先设置底注金额")
            return
        current_play = self.play_var.get()
        # 如果当前是 "0" 或 "0.0"，则设为底注*2，否则设为0
        if current_play in ("0", "0.0"):
            new_play = ante * 2
            self.play_var.set(str(new_play))
        else:
            self.play_var.set("0")

    # ---------- 游戏规则说明 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("加勒比扑克游戏规则")
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
        加勒⽐梭哈扑克 游戏规则

        1. 游戏开始前下注:
           - 底注: 基础下注（必须）
           - 累进大奖: 可选$1下注
           - 5+1: 可选下注（使用庄家第一张明牌和玩家五张牌，共6张牌选出最佳5张牌型）
           - 加注: 点击可在0和底注×2之间切换，若预下注>0则自动进入摊牌（盲注模式）

        2. 游戏流程:
           a. 下注阶段:
               - 玩家下注底注
               - 可选择下注$1参与累进大奖
               - 可选择下注5+1
               - 可选预下注（底注×2）
               - 点击"开始游戏"按钮开始

           b. 发牌:
               - 玩家和庄家各发五张牌
               - 玩家牌面朝上，庄家牌面朝下（只显示第一张）
               - 立刻结算5+1

           c. 决策阶段（仅当未预下注时）:
               - 玩家查看自己的五张牌后选择:
                 * 弃牌: 输掉底注下注，但累进大奖可能赢
                 * 下注2倍: 下注金额等于底注*2

           d. 摊牌:
               - 庄家开牌
               - 庄家必须有一张A和K才能合格
               - 结算所有下注

        3. 结算规则:
           - 底注和加注:
             * 如果庄家不合格:
                 - 底注：1:1
                 - 加注: 退还
             * 如果庄家合格:
                 - 比较玩家和庄家的牌:
                   - 玩家赢: 底注支付1:1，加注根据玩家牌型支付（见赔率表）
                   - 平局: 底注和加注都退还
                   - 玩家输: 输掉底注和加注

           - 累进大奖:
             * 只根据玩家手牌支付
             * 赔付表见下方（高额模式基本赔付×10）

           - 5+1 (需下注5+1):
             * 使用庄家第一张明牌和玩家五张牌，共6张牌选出最佳5张牌型
             * 赔付表见下方
        """
        tk.Label(content_frame, text=rules_text, font=('微软雅黑',11),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        tk.Label(content_frame, text="赔付表汇总", font=('微软雅黑',14,'bold'),
                 bg='#F0F0F0').pack(fill=tk.X, padx=10, pady=(20,10), anchor='center')

        payout_frame = tk.Frame(content_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=20, pady=5)
        headers = ["牌型","加注赔率","5+1赔率","累进大奖"]
        data = [
            ("皇家同花顺","100:1","1000:1","100%"),
            ("同花顺","50:1","200:1","10%"),
            ("四条","20:1","100:1","$1,250"),
            ("葫芦","7:1","20:1","$375"),
            ("同花","5:1","15:1","$250"),
            ("顺子","4:1","10:1","-"),
            ("三条","3:1","7:1","-"),
            ("两对","2:1","-","-"),
            ("对子","1:1","-","-"),
            ("高牌","1:1","-","-")
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

        notes = """
        注:
        * 庄家必须至少有一张A和K才合格
        * 下注金额等于底注*2的下注金额
        * 高额模式下累进大奖赔付×10，且奖池贡献率提升至8%
        * 加注栏点击切换0/底注×2，预下注后开始游戏直接摊牌
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

    # ---------- 更新手牌标签 ----------
    def update_hand_labels(self):
        if self.game.player_hand and len(self.game.player_hand)==5:
            rank, values = evaluate_five_card_hand(self.game.player_hand)
            name = HAND_RANK_NAMES.get(rank, "")
            if rank == 0:  # 高牌
                if len(values) >= 2 and values[0] == 14 and values[1] == 13:
                    name = "高牌ACE+KING"
                else:
                    name = "高牌"
            self.player_label.config(text=f"玩家 - {name}" if name else "玩家")
        if (self.game.stage=="showdown" or self.game.folded) and self.game.dealer_hand and len(self.game.dealer_hand)==5:
            rank, values = evaluate_five_card_hand(self.game.dealer_hand)
            name = HAND_RANK_NAMES.get(rank, "")
            if rank == 0:
                if len(values) >= 2 and values[0] == 14 and values[1] == 13:
                    name = "高牌ACE+KING"
                else:
                    name = "高牌"
            self.dealer_label.config(text=f"庄家 - {name}" if name else "庄家")

    # ---------- 开始游戏 ----------
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.jackpot_bet = self.jackpot_bet_var.get()
            self.five_plus_one_bet = int(self.five_plus_one_var.get())
            self.last_jackpot_state = self.jackpot_bet_var.get()

            # 获取预下注金额（可能是0或ante*2）
            play_bet = int(self.play_var.get()) if self.play_var.get().lstrip('$').isdigit() else 0

            jackpot_cost = 2.5 if self.jackpot_bet else 0
            if self.high_bet_mode:
                min_ante, max_ante, max_five = 100, 50000, 12500
            else:
                min_ante, max_ante, max_five = 10, 10000, 2500

            if self.ante < min_ante:
                messagebox.showerror("错误", f"底注至少需要{min_ante}块")
                return
            if self.ante > max_ante:
                self.ante = max_ante
                self.ante_var.set(str(max_ante))
                messagebox.showwarning("下注限制", f"底注上限为{max_ante}，已自动调整")
            if self.five_plus_one_bet > max_five:
                self.five_plus_one_bet = max_five
                self.five_plus_one_var.set(str(max_five))

            # 总下注 = 底注 + 累进大奖(1) + 5+1 + 预加注(如果有)
            base_total = self.ante + jackpot_cost + self.five_plus_one_bet
            total_bet = base_total + play_bet
            if play_bet != 0:
                if self.balance < total_bet:
                    messagebox.showerror("错误", "余额不足以支付所有下注！")
                    return
            else: 
                if self.balance < total_bet + self.ante*2:
                    messagebox.showerror("错误", "余额不足以支付所有下注！")
                    return
            self.balance -= total_bet
            self.game_in_progress = True

            # 记录下注信息（用于重复）
            self.last_bet = {
                'ante': self.ante,
                'five_plus_one': self.five_plus_one_bet,
                'jackpot': self.jackpot_bet,
                'play': play_bet
            }
            if self.repeat_bet_btn:
                self.repeat_bet_btn.config(state=tk.NORMAL)
            self.update_balance()

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.last_win_label.config(text="上局获胜: $0.00")

            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.jackpot_bet = self.jackpot_bet
            self.game.five_plus_one_bet = self.five_plus_one_bet
            self.game.play_bet = play_bet

            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()

            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            self.card_positions = {}
            for i in range(5):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*110,0)}
                self.animation_queue.append(card_id)
            for i in range(5):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {"current": (50,50), "target": (i*110,0)}
                self.animation_queue.append(card_id)

            for widget in self.btn_frame.winfo_children():
                widget.destroy()

            if play_bet > 0:
                # 预下注模式，直接摊牌
                self.stage_label.config(text="盲注模式")
                self.status_label.config(text="预下注已设，自动进入摊牌")
            else:
                self.stage_label.config(text="决策")
                self.status_label.config(text="做出决策: 弃牌或下注2倍")
                action_frame = tk.Frame(self.btn_frame, bg=PANEL_BG)
                action_frame.pack()
                self.fold_button = tk.Button(
                    action_frame, text="弃牌", command=self.fold_action,
                    state=tk.DISABLED, font=('Arial',12,'bold'), bg='#F44336', fg='white', width=10
                )
                self.fold_button.pack(side=tk.LEFT, padx=(0,10))
                self.play_button = tk.Button(
                    action_frame, text="下注2倍", command=self.play_action,
                    state=tk.DISABLED, font=('Arial',12,'bold'), bg='#4CAF50', fg='white', width=10
                )
                self.play_button.pack(side=tk.LEFT)

            # 禁用下注控件
            self.ante_display.unbind("<Button-1>")
            self.five_plus_one_display.unbind("<Button-1>")
            self.play_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            self.jackpot_check.config(state=tk.DISABLED)

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
                         width=110, height=140)
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
                card_label.place(x=tx, y=ty, width=110, height=140)
                card_label.is_moving = False
                if card_label.target_pos == (50,50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                self.after(20, self.animate_deal)
                return
            step_x, step_y = dx*0.2, dy*0.2
            card_label.place(x=cx+step_x, y=cy+step_y, width=110, height=140)
            self.after(20, lambda: self.animate_card_move(card_label))
        except tk.TclError:
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)

    # ---------- 翻开玩家牌（带翻转动画） ----------
    def reveal_player_cards(self):
        # 翻开庄家第一张
        self.reveal_dealer_first_card()
        for i, lbl in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["player"][i] = True
        self.update_hand_labels()
        self.after(1000, self.after_player_reveal)

    def after_player_reveal(self):
        # 结算5+1
        self.settle_five_plus_one_bet()
        # 排序玩家手牌（无翻转，移动动画）
        self.sort_player_hand_no_flip()

    def sort_player_hand_no_flip(self):
        if not self.game.player_hand:
            return
        eval_ = evaluate_five_card_hand(self.game.player_hand)
        sorted_hand = sort_hand_for_display(self.game.player_hand, eval_)
        labels = list(self.player_cards_frame.winfo_children())
        start_pos = {l: float(l.place_info()['x']) for l in labels if l.winfo_exists()}
        target = {}
        for idx, card in enumerate(sorted_hand):
            for l in labels:
                if hasattr(l, 'card') and l.card == card:
                    target[l] = idx*110
                    break
        # 动画移动
        steps = 15
        interval = 50
        data = []
        for l in start_pos:
            dx = (target[l] - start_pos[l]) / steps
            data.append((l, start_pos[l], dx))
        def step(step_count):
            if step_count > steps:
                for l,_,_ in data:
                    if l.winfo_exists():
                        l.place(x=target[l])
                self.game.player_hand = sorted_hand
                # 如果预下注>0，直接进入摊牌
                if self.game.play_bet > 0:
                    self.after(1000, self.show_showdown)
                else:
                    # 启用决策按钮
                    if hasattr(self, 'fold_button') and self.fold_button:
                        try: self.fold_button.config(state=tk.NORMAL)
                        except: pass
                    if hasattr(self, 'play_button') and self.play_button:
                        try: self.play_button.config(state=tk.NORMAL)
                        except: pass
                return
            for l,start_x,dx in data:
                if l.winfo_exists():
                    l.place(x=start_x + dx*step_count)
            self.after(interval, lambda: step(step_count+1))
        step(1)

    def reveal_dealer_first_card(self):
        dealer_children = self.dealer_cards_frame.winfo_children()
        if dealer_children:
            first = dealer_children[0]
            if hasattr(first, "card") and not first.is_face_up:
                self.animation_in_progress = True
                self.flip_card_animation(first)

    # ---------- 翻转动画 ----------
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
            card_label.place(width=110, height=140)
            return
        if step <= steps//2:
            width = 110 - step*11
            if width <=0: width=1
            card_label.config(image=self.back_image)
        else:
            width = (step - steps//2)*11
            if width<=0: width=1
            card_label.config(image=front_img)
        card_label.place(width=width, height=140)
        self.after(50, lambda: self.animate_flip(card_label, front_img, step+1))

    # ---------- 5+1 结算 ----------
    def settle_five_plus_one_bet(self):
        self.five_plus_one_win = 0
        if self.game.five_plus_one_bet > 0 and self.game.dealer_hand:
            dealer_first = self.game.dealer_hand[0]
            six_cards = self.game.player_hand + [dealer_first]
            best_payout = 0
            for combo in combinations(six_cards, 5):
                rank,_ = evaluate_five_card_hand(list(combo))
                payout = FIVE_PLUS_ONE_PAYOUT.get(rank, 0)
                if payout > best_payout:
                    best_payout = payout
            if best_payout > 0:
                self.five_plus_one_win = self.game.five_plus_one_bet * best_payout
                self.five_plus_one_display.config(bg='gold')
                self.five_plus_one_var.set(str(int(self.five_plus_one_win)))
            else:
                self.five_plus_one_var.set("未赢")

    # ---------- 决策动作 ----------
    def play_action(self):
        if hasattr(self, 'fold_button'): self.fold_button.config(state=tk.DISABLED)
        if hasattr(self, 'play_button'): self.play_button.config(state=tk.DISABLED)
        play_bet = self.game.ante * 2
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        self.play_var.set(str(play_bet))
        jackpot_cost = 2.5 if self.game.jackpot_bet else 0
        total = self.game.ante + self.game.play_bet + jackpot_cost + self.game.five_plus_one_bet
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")
        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)

    def fold_action(self):
        if hasattr(self, 'fold_button'): self.fold_button.config(state=tk.DISABLED)
        if hasattr(self, 'play_button'): self.play_button.config(state=tk.DISABLED)
        self.game.folded = True
        self.status_label.config(text="您已弃牌 ~ 游戏结束")
        self.ante_var.set("0")
        self.play_var.set("0")
        self.reveal_dealer_cards()

    # ---------- 摊牌 ----------
    def show_showdown(self):
        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.reveal_dealer_cards()

    def reveal_dealer_cards(self):
        for i, lbl in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(lbl, "card") and not lbl.is_face_up:
                self.flip_card_animation(lbl)
                self.game.cards_revealed["dealer"][i] = True
        self.update_hand_labels()
        self.after(1000, self.start_both_sort_animation)

    def start_both_sort_animation(self):
        # 排序双方手牌
        player_eval = evaluate_five_card_hand(self.game.player_hand)
        dealer_eval = evaluate_five_card_hand(self.game.dealer_hand)
        sorted_p = sort_hand_for_display(self.game.player_hand, player_eval)
        sorted_d = sort_hand_for_display(self.game.dealer_hand, dealer_eval)
        self.game.player_hand = sorted_p
        self.game.dealer_hand = sorted_d

        p_labels = list(self.player_cards_frame.winfo_children())
        d_labels = list(self.dealer_cards_frame.winfo_children())
        # 计算目标位置
        p_target = {}
        for idx, card in enumerate(sorted_p):
            for l in p_labels:
                if hasattr(l, 'card') and l.card == card:
                    p_target[l] = idx*110
                    break
        d_target = {}
        for idx, card in enumerate(sorted_d):
            for l in d_labels:
                if hasattr(l, 'card') and l.card == card:
                    d_target[l] = idx*110
                    break

        all_labels = p_labels + d_labels
        start = {l: float(l.place_info()['x']) for l in all_labels if l.winfo_exists()}
        target = {**p_target, **d_target}
        steps = 20
        interval = 30
        data = []
        for l in start:
            dx = (target[l] - start[l]) / steps
            data.append((l, start[l], dx))
        def step(cnt):
            if cnt > steps:
                for l,_,_ in data:
                    if l.winfo_exists():
                        l.place(x=target[l])
                self.update_hand_labels()
                # 结算
                if self.game.folded:
                    self.settle_fold()
                else:
                    self.settle_showdown()
                return
            for l,start_x,dx in data:
                if l.winfo_exists():
                    l.place(x=start_x + dx*cnt)
            self.after(interval, lambda: step(cnt+1))
        step(1)

    # ---------- 结算 ----------
    def settle_fold(self):
        bonus_win = 0
        if self.game.jackpot_bet:
            bonus_win = self.calculate_bonus()
            if bonus_win > 0:
                self.balance += bonus_win
                self.update_balance()
                rank,_ = evaluate_five_card_hand(self.game.player_hand)
                msg = f"牌型为{HAND_RANK_NAMES.get(rank,'')}! 赢得奖金${bonus_win:.2f}"
                messagebox.showinfo("恭喜您获得累进大奖！", msg)
                self.progressive_display.config(bg='gold')
        self.update_jackpot()
        self.ante_display.config(bg='white')
        total_win = bonus_win
        self.last_win = total_win
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")
        self.show_restart_button()
        self._save_history({"fold":True, "total_winnings": total_win})

    def settle_showdown(self):
        winnings, details = self.calculate_winnings()
        winnings += self.five_plus_one_win
        self.last_win = winnings
        self.balance += winnings
        self.update_balance()

        self.ante_var.set(str(int(details["ante"])))
        self.play_var.set(str(int(details["play"])))
        # 着色
        for bet_type in ["ante","play"]:
            widget = self.bet_widgets.get(bet_type)
            if not widget: continue
            if bet_type == "ante":
                bet_amt = self.game.ante
                win_amt = details["ante"]
            else:
                bet_amt = self.game.play_bet
                win_amt = details["play"]
            if win_amt > bet_amt:
                widget.config(bg='gold')
            elif win_amt == bet_amt and bet_amt > 0:
                widget.config(bg='light blue')
            else:
                widget.config(bg='white')

        dealer_qual = self.game.dealer_qualifies()
        comp = compare_hands(self.game.player_hand, self.game.dealer_hand)
        if not dealer_qual:
            msg = "庄家不合格，底注获胜，加注退还"
            winner = "player"   # 庄家不合格视为玩家赢（底注）
        elif comp > 0:
            msg = "本局您赢了"
            winner = "player"
        elif comp < 0:
            msg = "本局您输了"
            winner = "dealer"
        else:
            msg = "本局Push"
            winner = "push"
        if self.game.jackpot_bet and details["bonus"] > 0:
            rank,_ = evaluate_five_card_hand(self.game.player_hand)
            msg2 = f"牌型为{HAND_RANK_NAMES.get(rank,'')}! 赢得奖金${details['bonus']:.2f}"
            messagebox.showinfo("恭喜您获得累进大奖！", msg2)
            self.progressive_display.config(bg='gold')
        self.status_label.config(text=msg)
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        self.show_restart_button()
        self._save_history({"winner": winner, "winnings": winnings})

    # ---------- 累进大奖计算 ----------
    def calculate_bonus(self):
        if not self.game.player_hand or len(self.game.player_hand) < 5:
            return 0
        rank, _ = evaluate_five_card_hand(self.game.player_hand)
        jackpot = self.game.progressive_amount
        bonus = 0
        if rank == 9:          # 皇家同花顺 → 奖池的100%
            bonus = jackpot
            self.game.progressive_amount -= bonus
        elif rank == 8:        # 同花顺 → 奖池的10%
            bonus = jackpot * 0.1
            self.game.progressive_amount -= bonus
        elif rank == 7:        # 四条 → $1250
            bonus = 1250.0
            self.game.progressive_amount -= bonus
        elif rank == 6:        # 葫芦 → $375
            bonus = 375.0
            self.game.progressive_amount -= bonus
        elif rank == 5:        # 同花 → $250
            bonus = 250.0
            self.game.progressive_amount -= bonus
        # 其他牌型无累进奖励

        # 保证奖池不低于最低值
        if self.game.progressive_amount < 271288.59:
            self.game.progressive_amount = 271288.59

        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        save_jackpot(self.game.progressive_amount)
        return bonus

    def update_jackpot(self):
        jackpot_cost = 2.5 if self.game.jackpot_bet else 0
        total = self.game.ante + self.game.play_bet + self.game.five_plus_one_bet
        rate = 0.001
        self.game.progressive_amount += total * rate + jackpot_cost*0.95
        if self.game.progressive_amount < 271288.59:
            self.game.progressive_amount = 271288.59
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        save_jackpot(self.game.progressive_amount)

    def calculate_winnings(self):
        winnings = 0
        details = {"ante":0,"play":0,"bonus":0,"five_plus_one":0}
        dealer_qual = self.game.dealer_qualifies()
        comp = compare_hands(self.game.player_hand, self.game.dealer_hand)
        if not dealer_qual:
            ante_result = self.game.ante * 2
            play_result = self.game.play_bet
        else:
            if comp > 0:
                ante_result = self.game.ante * 2
                rank,_ = evaluate_five_card_hand(self.game.player_hand)
                payout = CARIBBEAN_STUD_PAYOUT.get(rank, 1)
                play_result = self.game.play_bet * (payout + 1)
            elif comp == 0:
                ante_result = self.game.ante
                play_result = self.game.play_bet
            else:
                ante_result = 0
                play_result = 0
        winnings += ante_result + play_result
        details["ante"] = ante_result
        details["play"] = play_result

        if self.game.jackpot_bet:
            bonus = self.calculate_bonus()
            winnings += bonus
            details["bonus"] = bonus
        self.update_jackpot()
        return winnings, details

    # ---------- 历史记录 ----------
    def _save_history(self, result_info=None):
        try:
            deck = self.game.deck
            if deck is None: return
            save_caribbean_history(deck, self.game.player_hand, self.game.dealer_hand, result_info)
        except Exception as e:
            print(f"保存历史记录出错: {e}")

    # ---------- 重置相关 ----------
    def reset_bets(self):
        self.ante_var.set("0")
        self.five_plus_one_var.set("0")
        self.play_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.ante_display.config(bg='#FFCDD2')
        self.five_plus_one_display.config(bg='#FFCDD2')
        self.after(500, lambda: self.ante_display.config(bg='white'))
        self.after(500, lambda: self.five_plus_one_display.config(bg='white'))

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        ante = self.last_bet['ante']
        five = self.last_bet['five_plus_one']
        jack = self.last_bet['jackpot']
        # 我们先设置 play_var 为上次的值，再设置 ante_var，trace 会检查 play_var 是否为0，如果是0则不变，如果不是0则更新为 ante*2。
        self.play_var.set(str(self.last_bet.get('play', 0)))

        if self.high_bet_mode:
            max_ante, max_five = 50000, 12500
            min_ante = 100
        else:
            max_ante, max_five = 10000, 2500
            min_ante = 10
        if ante < min_ante: ante = min_ante
        if ante > max_ante: ante = max_ante
        if five > max_five: five = max_five
        self.ante_var.set(str(ante))
        self.five_plus_one_var.set(str(five))
        self.jackpot_bet_var.set(jack)

        self.status_label.config(text="已应用上次下注金额")
        self.ante_display.config(bg='#E8F5E9')
        self.five_plus_one_display.config(bg='#E8F5E9')
        self.after(800, lambda: self.ante_display.config(bg='white'))
        self.after(800, lambda: self.five_plus_one_display.config(bg='white'))

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
        self.ante_var.set("0")
        self.five_plus_one_var.set("0")
        self.play_var.set("0")
        self.jackpot_bet_var.set(self.last_jackpot_state)
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.progressive_display.config(bg=PANEL_BG)
        self.active_card_labels = []

        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.five_plus_one_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("five_plus_one"))
        self.five_plus_one_display.bind("<Button-3>", lambda e: self.reset_single_bet("five_plus_one", e))
        self.play_display.bind("<Button-1>", self.toggle_play_bet)   # 重新绑定
        self.jackpot_check.config(state=tk.NORMAL)
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

    def enable_action_buttons(self):
        self.buttons_disabled = False
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)

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
def main(initial_balance=10000, username="Guest"):
    app = CaribbeanStudGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")