import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import secrets
import time
from collections import Counter

# =========================================================
# 全局颜色与常量
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
# 用户数据管理
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
# 累进大奖文件操作
# =========================================================
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    default = 82188.59
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'CSO':
                    return float(item.get('jackpot', default))
    except:
        pass
    return default

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
        if item.get('Games') == 'CSO':
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({"Games": "CSO", "jackpot": jackpot})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# =========================================================
# 牌局历史日志（修改统计字段）
# =========================================================
def casino_war_log_path() -> str:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Casino_War.json")

def save_casino_war_history(player_card, dealer_card, result_info=None,
                            player_war_card=None, dealer_war_card=None):
    """
    保存一局历史记录。
    :param player_card: 玩家初始牌 (Card)
    :param dealer_card: 庄家初始牌 (Card)
    :param result_info: 包含 winner 和 surrender 的字典
    :param player_war_card: 战争时玩家最后一张牌 (Card)，若无则为 None
    :param dealer_war_card: 战争时庄家最后一张牌 (Card)，若无则为 None
    """
    log_path = casino_war_log_path()
    data = {
        "history_record": {
            "player_win": 0,
            "dealer_win": 0,
            "war": 0,
            "war_fail": 0,
            "war_success": 0,
            "war_push": 0,
            "surrender": 0,
            "game": 0
        },
        "history": []
    }
    # 读取现有数据
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "history_record" in loaded:
                    # 补全可能缺失的字段
                    for key in data["history_record"]:
                        if key not in loaded["history_record"]:
                            loaded["history_record"][key] = 0
                    data["history_record"] = loaded["history_record"]
                    if "history" in loaded:
                        data["history"] = loaded["history"]
                elif isinstance(loaded, list):
                    data["history"] = loaded
                    # 从历史记录重建统计（旧版兼容）
                    stats = {k: 0 for k in data["history_record"]}
                    stats["game"] = len(loaded)
                    for rec in loaded:
                        if "result" in rec and "winner" in rec["result"]:
                            winner = rec["result"]["winner"]
                            # 判断是否战争：检查 war_cards 是否有值
                            war_cards = rec.get("war_cards", {})
                            has_war = war_cards.get("player_war_card") is not None or war_cards.get("dealer_war_card") is not None
                            if has_war:
                                stats["war"] += 1
                                if winner == "player":
                                    stats["war_success"] += 1
                                elif winner == "dealer":
                                    stats["war_fail"] += 1
                                elif winner == "war_push":
                                    stats["war_push"] += 1
                            else:
                                if winner == "player":
                                    stats["player_win"] += 1
                                elif winner == "dealer":
                                    stats["dealer_win"] += 1
                                elif winner == "surrender":
                                    stats["surrender"] += 1
                    data["history_record"] = stats
        except Exception as e:
            print(f"读取历史文件出错: {e}")

    # 计算新的 game_id
    max_id = 0
    for rec in data["history"]:
        if "game_id" in rec and isinstance(rec["game_id"], int):
            if rec["game_id"] > max_id:
                max_id = rec["game_id"]
    new_game_id = max_id + 1

    # 更新统计
    stats = data["history_record"]
    stats["game"] += 1

    winner = result_info.get("winner") if result_info else None
    surrender = result_info.get("surrender", False) if result_info else False

    # 判断是否发生战争
    has_war = player_war_card is not None or dealer_war_card is not None

    if has_war:
        stats["war"] += 1
        if winner == "player":
            stats["war_success"] += 1
        elif winner == "dealer":
            stats["war_fail"] += 1
        elif winner == "war_push":
            stats["war_push"] += 1
        # 如果 winner 是其他值（如 "surrender"），理论上不会发生
    else:
        if winner == "player":
            stats["player_win"] += 1
        elif winner == "dealer":
            stats["dealer_win"] += 1
        elif winner == "surrender":
            stats["surrender"] += 1
        # 其他情况（如 "push"）忽略

    # 构建新记录（移除了 deck_order 和 start_position）
    record = {
        "game_id": new_game_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "player_card": str(player_card),
        "dealer_card": str(dealer_card),
        "war_cards": {
            "player_war_card": str(player_war_card) if player_war_card else None,
            "dealer_war_card": str(dealer_war_card) if dealer_war_card else None
        },
        "result": result_info if result_info else {}
    }
    if winner is not None:
        record["result"]["winner"] = winner

    data["history"].append(record)

    # 只保留最近50条
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# =========================================================
# 扑克牌类与牌堆（全局单例，8副牌）
# =========================================================
class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]
    def __repr__(self):
        return f"{self.rank}{self.suit}"

class Deck:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, num_decks=8):
        if Deck._initialized:
            return
        Deck._initialized = True
        self.num_decks = num_decks
        self.full_deck = []
        self.cut_position = 0
        self.pointer = 0
        self._rebuild()
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % len(self.full_deck) for i in range(len(self.full_deck))]
        self.card_sequence = [self.full_deck[i] for i in self.indexes]

    def _rebuild(self):
        self.full_deck = [Card(s, r) for s in SUITS for r in RANKS] * self.num_decks
        self._secure_shuffle()
        self.cut_position = secrets.randbelow(len(self.full_deck))
        self.pointer = 0
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % len(self.full_deck) for i in range(len(self.full_deck))]
        self.card_sequence = [self.full_deck[i] for i in self.indexes]

    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        remaining = len(self.full_deck) - self.pointer
        if remaining < 60:
            self._rebuild()
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# =========================================================
# 游戏逻辑类（Casino War）
# =========================================================
class CasinoWarGame:
    def __init__(self):
        self.deck = Deck()
        self.player_card = None
        self.dealer_card = None
        self.initial_player_card = None
        self.initial_dealer_card = None
        self.ante = 0
        self.tie_bet = 0
        self.war_bet = 0
        self.jackpot_bet = 0
        self.stage = "bet"
        self.surrendered = False
        self.result = None
        self.player_war_cards = []   # 仅在战争时填充
        self.dealer_war_cards = []
        self.war_comp = 0

    def deal_initial(self):
        self.player_card = self.deck.deal(1)[0]
        self.dealer_card = self.deck.deal(1)[0]
        self.initial_player_card = self.player_card
        self.initial_dealer_card = self.dealer_card

    def compare_cards(self):
        if self.player_card.value > self.dealer_card.value:
            return 1
        elif self.player_card.value < self.dealer_card.value:
            return -1
        else:
            return 0

    def war_compare(self):
        """战争：发4张给玩家，再发4张给庄家，比较第4张（最后一张）"""
        self.player_war_cards = self.deck.deal(4)
        self.dealer_war_cards = self.deck.deal(4)
        war_player = self.player_war_cards[-1]
        war_dealer = self.dealer_war_cards[-1]
        if war_player.value > war_dealer.value:
            self.war_comp = 1
        elif war_player.value < war_dealer.value:
            self.war_comp = -1
        else:
            self.war_comp = 0
        return self.war_comp

# =========================================================
# 主GUI类
# =========================================================
class CasinoWarGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("赌场战争 (Casino War)")
        self.geometry("1150x750+50+10")
        self.resizable(0,0)
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = CasinoWarGame()
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
        self.bet_widgets = {}
        self.game_in_progress = False
        self.high_bet_mode = False
        self.war_animation_running = False
        self.deal_phase = 0
        self.total_bet = 0

        # ---------- 累进大奖 ----------
        self.progressive_amount = load_jackpot()
        self.progressive_var = tk.StringVar(value=f"${self.progressive_amount:,.2f}")
        self.jackpot_bet_var = tk.IntVar(value=0)
        self.last_jackpot_state = 0

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
        self.current_poker_folder = 'Poker1'
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

    # ---------- 筹码交互 ----------
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
            "tie": (12500 if self.high_bet_mode else 2500)
        }
        if bet_type in limits:
            current = float(self.__getattribute__(f"{bet_type}_var").get())
            limit = limits[bet_type]
            if current >= limit:
                names = {"ante":"底注","tie":"平局注"}
                messagebox.showwarning("下注限制", f"{names[bet_type]}已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                new_amount = limit
                if current > 0:
                    names = {"ante":"底注","tie":"平局注"}
                    messagebox.showwarning("下注限制", f"{names[bet_type]}已达上限，自动调整为 {int(new_amount)}")
            self.__getattribute__(f"{bet_type}_var").set(str(int(new_amount)))

    def reset_single_bet(self, bet_type, event):
        if bet_type == "ante":
            self.ante_var.set("0")
        elif bet_type == "tie":
            self.tie_var.set("0")
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
            text="比大小，平局可选投降或开战",
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
        self.stage_label = tk.Label(body_info, text="等待下注", font=('Arial',16,'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # 累进大奖卡片
        progressive_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        progressive_card.pack(fill=tk.X, pady=3)
        header_prog = tk.Frame(progressive_card, bg=HEADER_BG)
        header_prog.pack(fill=tk.X)
        tk.Label(header_prog, text="平局累进大奖", font=('Arial',13,'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_prog = tk.Frame(progressive_card, bg=PANEL_BG)
        body_prog.pack(fill=tk.X, padx=10, pady=8)
        self.progressive_display = tk.Label(body_prog, textvariable=self.progressive_var,
                                            font=('Arial',20,'bold'), bg=PANEL_BG, fg='#A88100')
        self.progressive_display.pack(anchor='center')

        # 限红卡片
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
        titles = ["底注最低","底注最高","平局注最高"]
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

        # 筹码与下注
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

        # 筹码行
        chip_row = tk.Frame(body_combined, bg=PANEL_BG)
        chip_row.grid(row=0, column=0, columnspan=3, pady=(0,8), sticky='ew')
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

        # 累进大奖复选框
        row_jackpot = tk.Frame(body_combined, bg=PANEL_BG)
        row_jackpot.grid(row=1, column=0, columnspan=3, sticky='ew', padx=40, pady=2)
        self.jackpot_check = tk.Checkbutton(
            row_jackpot, text="平局累进大奖 ($2.50)", variable=self.jackpot_bet_var,
            font=('Arial',12,"bold"), bg=PANEL_BG, fg='black', selectcolor=PANEL_BG
        )
        self.jackpot_check.pack(side=tk.LEFT)

        # 下注行
        row1 = tk.Frame(body_combined, bg=PANEL_BG)
        row1.grid(row=2, column=0, columnspan=3, sticky='ew', pady=4)
        tk.Label(row1, text="       底注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(row1, textvariable=self.ante_var, font=('Arial',12),
                                     bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.bet_widgets["ante"] = self.ante_display

        tk.Label(row1, text="平局注:", font=('Arial',12,"bold"), bg=PANEL_BG).pack(side=tk.LEFT, padx=(25,5))
        self.tie_var = tk.StringVar(value="0")
        self.tie_display = tk.Label(row1, textvariable=self.tie_var, font=('Arial',12),
                                    bg='white', fg='black', width=8, relief=tk.SUNKEN)
        self.tie_display.pack(side=tk.LEFT, padx=5)
        self.tie_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("tie"))
        self.tie_display.bind("<Button-3>", lambda e: self.reset_single_bet("tie", e))
        self.bet_widgets["tie"] = self.tie_display

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

        # 底部信息
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

    # ---------- 高额模式切换 ----------
    def toggle_high_bet_limits(self, event=None):
        if self.game_in_progress or self.war_animation_running:
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

    # ---------- 游戏规则说明 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("赌场战争 游戏规则")
        win.geometry("700x500")
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
        赌场战争 (Casino War) 规则

        1. 下注：
           - 底注（必须）：最低$10，最高$10,000（高额模式下最高$50,000）
           - 平局注（可选）：押注玩家和庄家第一张牌点数相同，赔率 1:10
             普通模式上限 $2,500，高额模式上限 $12,500
           - 累进大奖（可选）：下注$2.50，仅当平局且开战时根据牌型赢取大奖

        2. 发牌：
           - 玩家和庄家各发一张牌，牌面朝上。

        3. 比牌：
           - 点数大者赢（A最大，2最小）。
           - 若玩家赢：底注赢 1:1（返还总额为下注×2）。
           - 若庄家赢：玩家输掉底注，格子清零。
           - 若平局：
               * 玩家可选择“投降” → 输掉一半底注（退还另一半）。
               * 玩家可选择“开战” → 自动追加一个底注（从余额扣除）。
                  - 向玩家连续发4张牌，再向庄家连续发4张牌，比较双方的第4张牌（最后一张）。
                  - 若玩家赢：返还总额 = 原底注×2 + 战争加注。
                  - 若庄家赢：输掉所有下注，格子清零。
                  - 若再次平局：玩家胜，返还总额同玩家赢。

        4. 平局注结算：
           - 仅当第一轮两张牌点数相同，平局注赢 1:10。
           - 无论是否开战，平局注只根据第一轮结果结算。

        5. 平局累进大奖（仅开战时）：
           - 下注$2.5后，若开战，根据所有已翻开的牌（初始2张+战争最后2张，共4张）判定：
             * 三张同点数同颜色：$150
             * 三张完全一样：$500
             * 四张同点数：$2,500
             * 四张同点数同颜色：10% 奖池
             * 四张完全一样：100% 奖池
           - 高额模式下固定奖金不变，百分比不变。

        6. 牌靴：
           - 8副牌（416张）顺序发牌，剩余＜60张时自动重洗。

        7. 高额模式：
           - 点击下注上限区域，输入当前时间（HHMM）切换。
        """
        tk.Label(content_frame, text=rules_text, font=('微软雅黑',11),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X, padx=10, pady=5)

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # ---------- 余额更新 ----------
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    # ---------- 开始游戏 ----------
    def start_game(self):
        if self.war_animation_running:
            return
        try:
            self.ante = int(self.ante_var.get())
            self.tie_bet = int(self.tie_var.get())
            self.jackpot_bet = 2.5 if self.jackpot_bet_var.get() else 0
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return

        if self.high_bet_mode:
            min_ante, max_ante, max_tie = 100, 50000, 12500
        else:
            min_ante, max_ante, max_tie = 10, 10000, 2500

        if self.ante < min_ante:
            messagebox.showerror("错误", f"底注至少需要{min_ante}块")
            return
        if self.ante > max_ante:
            self.ante = max_ante
            self.ante_var.set(str(max_ante))
            messagebox.showwarning("下注限制", f"底注上限为{max_ante}，已自动调整")
        if self.tie_bet > max_tie:
            self.tie_bet = max_tie
            self.tie_var.set(str(max_tie))
            messagebox.showwarning("下注限制", f"平局注上限为{max_tie}，已自动调整")

        total_bet = self.ante + self.tie_bet + self.jackpot_bet
        if self.balance < total_bet:
            messagebox.showerror("错误", "余额不足以支付所有下注！")
            return

        self.balance -= total_bet
        self.game_in_progress = True
        self.last_bet = {'ante': self.ante, 'tie': self.tie_bet, 'jackpot': self.jackpot_bet}
        self.last_jackpot_state = self.jackpot_bet_var.get()
        if self.repeat_bet_btn:
            self.repeat_bet_btn.config(state=tk.NORMAL)
        self.update_balance()
        self.total_bet = total_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        self.last_win_label.config(text="上局获胜: $0.00")

        # 重置游戏
        self.game = CasinoWarGame()
        self.game.ante = self.ante
        self.game.tie_bet = self.tie_bet
        self.game.jackpot_bet = self.jackpot_bet
        self.game.player_card = self.game.deck.deal(1)[0]
        self.game.dealer_card = None
        self.game.initial_player_card = self.game.player_card

        for widget in self.dealer_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.player_cards_frame.winfo_children():
            widget.destroy()

        self.animation_queue = []
        self.card_positions = {}
        self.active_card_labels = []
        self.animation_in_progress = False

        self.card_positions["player_0"] = {"current": (50,50), "target": (200,0)}
        self.animation_queue.append("player_0")

        # 禁用下注控件
        self.ante_display.unbind("<Button-1>")
        self.tie_display.unbind("<Button-1>")
        self.jackpot_check.config(state=tk.DISABLED)
        for chip in self.chip_buttons:
            chip.unbind("<Button-1>")

        self.clear_btn_frame()
        self.start_button = tk.Button(
            self.btn_frame, text="发牌中...", state=tk.DISABLED,
            font=('Arial',12,'bold'), bg='#9E9E9E', fg='white', width=10
        )
        self.start_button.pack()

        self.deal_phase = 1
        self.animate_deal()

    # ---------- 初始发牌动画 ----------
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            if self.deal_phase == 1:
                self.after(500, self.reveal_cards_phase1)
            elif self.deal_phase == 2:
                self.after(500, self.reveal_cards_phase2)
            else:
                self.after(500, self.reveal_cards)
            return
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        if card_id.startswith("player"):
            frame = self.player_cards_frame
            card = self.game.player_card
        else:
            frame = self.dealer_cards_frame
            card = self.game.dealer_card

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

    # ---------- 阶段1：翻开玩家牌 ----------
    def reveal_cards_phase1(self):
        for lbl in self.player_cards_frame.winfo_children():
            if hasattr(lbl, "card") and lbl.card is not None and not lbl.is_face_up:
                self.flip_card_animation(lbl)
        self.after(1200, self.deal_dealer_card)

    # ---------- 发庄家牌 ----------
    def deal_dealer_card(self):
        self.game.dealer_card = self.game.deck.deal(1)[0]
        self.game.initial_dealer_card = self.game.dealer_card
        self.animation_queue = []
        self.card_positions = {}
        self.active_card_labels = []
        self.card_positions["dealer_0"] = {"current": (50,50), "target": (200,0)}
        self.animation_queue.append("dealer_0")
        self.deal_phase = 2
        self.animate_deal()

    # ---------- 阶段2：翻开庄家牌 ----------
    def reveal_cards_phase2(self):
        for lbl in self.dealer_cards_frame.winfo_children():
            if hasattr(lbl, "card") and lbl.card is not None and not lbl.is_face_up:
                self.flip_card_animation(lbl)
        self.after(1200, self.after_reveal)

    def reveal_cards(self):
        pass

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

    # ---------- 初始比牌 ----------
    def after_reveal(self):
        comp = self.game.compare_cards()
        self.game.stage = "compare"
        if comp == 1:
            self.game.result = "player"
            self.settle_win()
        elif comp == -1:
            self.game.result = "dealer"
            self.settle_loss()
        else:
            self.game.result = "push"
            if self.game.tie_bet > 0:
                tie_win = self.game.tie_bet * 11
                self.balance += tie_win
                self.last_win_label.config(text=f"上局获胜: ${tie_win:.2f}")
                self.tie_display.config(bg='gold')
                self.tie_var.set(str(tie_win))
            else:
                self.tie_display.config(bg='white')
                self.tie_var.set("0")
            self.show_war_decision()

    # ---------- 平局决策 ----------
    def show_war_decision(self):
        self.stage_label.config(text="平局！")
        self.status_label.config(text="选择 投降 或 开战")
        self.clear_btn_frame()
        surrender_btn = tk.Button(
            self.btn_frame, text="投降 (输一半)", command=self.surrender_action,
            font=('Arial',12,'bold'), bg='#FF9800', fg='white', width=12
        )
        surrender_btn.pack(side=tk.LEFT, padx=5)
        war_btn = tk.Button(
            self.btn_frame, text="开战 (下注 x2)", command=self.start_war,
            font=('Arial',12,'bold'), bg='#2196F3', fg='white', width=12
        )
        war_btn.pack(side=tk.LEFT, padx=5)

    def surrender_action(self):
        self.game.surrendered = True
        refund = self.game.ante * 0.5
        self.balance += refund
        self.update_balance()
        self.status_label.config(text=f"投降，退还 ${refund:.2f}")
        self.last_win = refund
        self.last_win_label.config(text=f"上局获胜: ${refund:.2f}")
        self.ante_display.config(bg='light blue')
        self.ante_var.set(f"{refund:.2f}")
        self.finish_game(winner="surrender")

    # ---------- 战争主流程 ----------
    def start_war(self):
        if self.war_animation_running:
            return
        if self.balance < self.game.ante:
            messagebox.showerror("错误", "余额不足以支付战争加注，请选择投降")
            return
        self.balance -= self.game.ante
        self.update_balance()
        self.game.war_bet = self.game.ante

        self.ante_var.set(str(self.game.ante * 2))
        new_total = self.total_bet + self.game.ante
        self.current_bet_label.config(text=f"本局下注: ${new_total:.2f}")

        self.stage_label.config(text="开战！")
        self.status_label.config(text="战争进行中...")

        self.war_comp = self.game.war_compare()
        # 注意：战争牌保存在 self.game.player_war_cards 和 self.game.dealer_war_cards 中

        self.clear_btn_frame()
        self.start_button = tk.Button(
            self.btn_frame, text="战争进行中...", state=tk.DISABLED,
            font=('Arial',12,'bold'), bg='#9E9E9E', fg='white', width=10
        )
        self.start_button.pack()

        self.war_animation_running = True
        self.move_original_cards_left()

    # ---------- 战争动画 ----------
    def move_original_cards_left(self):
        self.active_card_labels = []
        for frame in (self.player_cards_frame, self.dealer_cards_frame):
            for lbl in frame.winfo_children():
                if not hasattr(lbl, "card"):
                    continue
                x = lbl.winfo_x()
                y = lbl.winfo_y()
                lbl.target_pos = (x - 190, y)
                self.active_card_labels.append(lbl)
        self.after(20, self.animate_war_move)

    def animate_war_move(self):
        finished = True
        for lbl in self.active_card_labels[:]:
            if not lbl.winfo_exists():
                self.active_card_labels.remove(lbl)
                continue
            tx, ty = lbl.target_pos
            cx = lbl.winfo_x()
            cy = lbl.winfo_y()
            dx = tx - cx
            if abs(dx) <= 3:
                lbl.place(x=tx, y=ty)
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
            else:
                finished = False
                step = max(5, abs(dx) * 0.2)
                if dx < 0:
                    cx -= step
                else:
                    cx += step
                lbl.place(x=cx, y=cy)
        if finished:
            self.after(250, lambda: self.deal_player_war_cards(0))
        else:
            self.after(16, self.animate_war_move)

    def deal_player_war_cards(self, index):
        if index >= 4:
            self.flip_player_war_card()
            return
        card = self.game.player_war_cards[index]  # 直接从 game 取
        lbl = tk.Label(self.player_cards_frame, image=self.back_image, bg='#2a4a3c')
        start_x = 800
        target_x = 120 + index * 110
        lbl.place(x=start_x, y=20, width=110, height=140)
        lbl.card = card
        lbl.is_face_up = False
        lbl.target_pos = (target_x, 0)
        lbl.is_moving = True
        self.active_card_labels.append(lbl)
        self.animate_war_single_card(lbl, lambda: self.deal_player_war_cards(index + 1))

    def animate_war_single_card(self, lbl, callback):
        if not lbl.winfo_exists():
            self.after(10, callback)
            return
        cx = lbl.winfo_x()
        cy = lbl.winfo_y()
        tx, ty = lbl.target_pos
        dx = tx - cx
        if abs(dx) <= 3:
            lbl.place(x=tx, y=ty, width=110, height=140)
            if lbl in self.active_card_labels:
                self.active_card_labels.remove(lbl)
            self.after(20, callback)
            return
        step = max(6, abs(dx) * 0.18)
        if dx > 0:
            cx += step
        else:
            cx -= step
        lbl.place(x=cx, y=cy, width=110, height=140)
        self.after(16, lambda: self.animate_war_single_card(lbl, callback))

    def flip_player_war_card(self):
        labels = [lbl for lbl in self.player_cards_frame.winfo_children() if hasattr(lbl, 'card')]
        if labels:
            last_lbl = labels[-1]
            self.flip_card_animation(last_lbl)
        self.after(1000, lambda: self.deal_dealer_war_cards(0))

    def deal_dealer_war_cards(self, index):
        if index >= 4:
            self.flip_dealer_war_card()
            return
        card = self.game.dealer_war_cards[index]  # 直接从 game 取
        lbl = tk.Label(self.dealer_cards_frame, image=self.back_image, bg='#2a4a3c')
        start_x = 800
        target_x = 120 + index * 110
        lbl.place(x=start_x, y=20, width=110, height=140)
        lbl.card = card
        lbl.is_face_up = False
        lbl.target_pos = (target_x, 0)
        lbl.is_moving = True
        self.active_card_labels.append(lbl)
        self.animate_war_single_card(lbl, lambda: self.deal_dealer_war_cards(index + 1))

    def flip_dealer_war_card(self):
        labels = [lbl for lbl in self.dealer_cards_frame.winfo_children() if hasattr(lbl, 'card')]
        if labels:
            last_lbl = labels[-1]
            self.flip_card_animation(last_lbl)
        self.after(1200, self.settle_war)

    # ---------- 累进大奖检测 ----------
    def check_tie_progressive(self, cards):
        if not cards or len(cards) < 4:
            return 0, None
        from collections import defaultdict
        rank_count = defaultdict(int)
        rank_suit_count = defaultdict(lambda: defaultdict(int))
        rank_color_count = defaultdict(lambda: defaultdict(int))
        for c in cards:
            rank_count[c.value] += 1
            rank_suit_count[c.value][c.suit] += 1
            color = 'red' if c.suit in ('♥','♦') else 'black'
            rank_color_count[c.value][color] += 1

        # 四张完全一样
        for val, suit_dict in rank_suit_count.items():
            for suit, cnt in suit_dict.items():
                if cnt >= 4:
                    bonus = self.progressive_amount
                    self.progressive_amount -= bonus
                    if self.progressive_amount < 82188.59:
                        self.progressive_amount = 82188.59
                    save_jackpot(self.progressive_amount)
                    self.progressive_var.set(f"${self.progressive_amount:,.2f}")
                    return bonus, "四张完全一样"

        # 四张同点数同颜色
        for val, color_dict in rank_color_count.items():
            for color, cnt in color_dict.items():
                if cnt >= 4:
                    bonus = self.progressive_amount * 0.1
                    self.progressive_amount -= bonus
                    if self.progressive_amount < 82188.59:
                        self.progressive_amount = 82188.59
                    save_jackpot(self.progressive_amount)
                    self.progressive_var.set(f"${self.progressive_amount:,.2f}")
                    return bonus, "四张同点数同颜色"

        # 四张同点数
        for val, cnt in rank_count.items():
            if cnt >= 4:
                base_bonus = 2500
                bonus = base_bonus
                if self.progressive_amount >= bonus:
                    self.progressive_amount -= bonus
                else:
                    bonus = self.progressive_amount - 82188.59
                    if bonus < 0:
                        bonus = 0
                    self.progressive_amount = 82188.59
                save_jackpot(self.progressive_amount)
                self.progressive_var.set(f"${self.progressive_amount:,.2f}")
                return bonus, "四张同点数"

        # 三张完全一样
        for val, suit_dict in rank_suit_count.items():
            for suit, cnt in suit_dict.items():
                if cnt >= 3:
                    base_bonus = 500
                    bonus = base_bonus
                    if self.progressive_amount >= bonus:
                        self.progressive_amount -= bonus
                    else:
                        bonus = self.progressive_amount - 82188.59
                        if bonus < 0:
                            bonus = 0
                        self.progressive_amount = 82188.59
                    save_jackpot(self.progressive_amount)
                    self.progressive_var.set(f"${self.progressive_amount:,.2f}")
                    return bonus, "三张完全一样"

        # 三张同点数同颜色
        for val, color_dict in rank_color_count.items():
            for color, cnt in color_dict.items():
                if cnt >= 3:
                    base_bonus = 150
                    bonus = base_bonus
                    if self.progressive_amount >= bonus:
                        self.progressive_amount -= bonus
                    else:
                        bonus = self.progressive_amount - 82188.59
                        if bonus < 0:
                            bonus = 0
                        self.progressive_amount = 82188.59
                    save_jackpot(self.progressive_amount)
                    self.progressive_var.set(f"${self.progressive_amount:,.2f}")
                    return bonus, "三张同点数同颜色"

        # 三张同点数
        for val, cnt in rank_count.items():
            if cnt >= 3:
                base_bonus = 50
                bonus = base_bonus
                if self.progressive_amount >= bonus:
                    self.progressive_amount -= bonus
                else:
                    bonus = self.progressive_amount - 82188.59
                    if bonus < 0:
                        bonus = 0
                    self.progressive_amount = 82188.59
                save_jackpot(self.progressive_amount)
                self.progressive_var.set(f"${self.progressive_amount:,.2f}")
                return bonus, "三张同点数"

        return 0, None

    # ---------- 更新奖池 ----------
    def update_progressive_pool(self, total_bet_excluding_jackpot, jackpot_bet):
        contribution = total_bet_excluding_jackpot * 0.001 + jackpot_bet * 0.95
        self.progressive_amount += contribution
        if self.progressive_amount < 82188.59:
            self.progressive_amount = 82188.59
        self.progressive_var.set(f"${self.progressive_amount:,.2f}")
        save_jackpot(self.progressive_amount)

    # ---------- 战争结算 ----------
    def settle_war(self):
        self.war_animation_running = False
        comp = self.war_comp

        tie_payout = 0
        if self.game.result == "push" and self.game.tie_bet > 0:
            tie_payout = self.game.tie_bet * 11

        jackpot_win = 0
        jackpot_name = None
        if self.game.jackpot_bet > 0:
            initial_player = self.game.initial_player_card
            initial_dealer = self.game.initial_dealer_card
            war_player_last = self.game.player_war_cards[-1] if self.game.player_war_cards else None
            war_dealer_last = self.game.dealer_war_cards[-1] if self.game.dealer_war_cards else None
            if war_player_last and war_dealer_last:
                all_revealed = [initial_player, initial_dealer, war_player_last, war_dealer_last]
                jackpot_win, jackpot_name = self.check_tie_progressive(all_revealed)
                if jackpot_win > 0:
                    self.balance += jackpot_win
                    self.update_balance()
                    msg = f"累进大奖中奖！牌型：{jackpot_name}，赢得 ${jackpot_win:,.2f}"
                    messagebox.showinfo("恭喜！", msg)
                    self.progressive_display.config(bg='gold')

        if comp == 1:
            total_return = self.game.ante * 2 + self.game.war_bet
            self.balance += total_return
            self.update_balance()
            self.status_label.config(text=f"战争胜利！赢得 ${total_return:.2f}")
            self.last_win = total_return + tie_payout + jackpot_win
            self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
            self.ante_display.config(bg='gold')
            self.ante_var.set(str(total_return))
            self.finish_game(winner="player")
        elif comp == -1:
            self.status_label.config(text="战争失败，输掉全部下注")
            self.last_win = tie_payout + jackpot_win
            self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
            self.ante_display.config(bg='white')
            self.ante_var.set("0")
            self.finish_game(winner="dealer")
        else:  # 战争再次平局
            total_return = self.game.ante * 2 + self.game.war_bet
            self.balance += total_return
            self.update_balance()
            self.status_label.config(text=f"再次平局，您赢了！赢得 ${total_return:.2f}")
            self.last_win = total_return + tie_payout + jackpot_win
            self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
            self.ante_display.config(bg='gold')
            self.ante_var.set(str(total_return))
            # 使用特殊 winner 值以区分战争平局
            self.finish_game(winner="war_push")

    # ---------- 正常结算 ----------
    def settle_win(self):
        total_return = self.game.ante * 2
        self.balance += total_return
        self.update_balance()
        self.status_label.config(text="玩家赢！")
        self.last_win = total_return
        self.last_win_label.config(text=f"上局获胜: ${total_return:.2f}")
        self.ante_display.config(bg='gold')
        self.ante_var.set(str(total_return))
        self.tie_var.set("0")
        self.tie_display.config(bg='white')
        self.finish_game(winner="player")

    def settle_loss(self):
        self.status_label.config(text="庄家赢，您输了")
        self.last_win = 0
        self.last_win_label.config(text="上局获胜: $0.00")
        self.ante_display.config(bg='white')
        self.ante_var.set("0")
        self.tie_var.set("0")
        self.tie_display.config(bg='white')
        self.finish_game(winner="dealer")

    # ---------- 结束游戏 ----------
    def finish_game(self, winner=None):
        total_bet_excl_jackpot = self.game.ante + self.game.tie_bet + self.game.war_bet
        self.update_progressive_pool(total_bet_excl_jackpot, self.game.jackpot_bet)

        self.game_in_progress = False
        self.game.stage = "finished"

        # 获取战争牌（仅当本次发生了战争）
        player_war_card = self.game.player_war_cards[-1] if self.game.player_war_cards else None
        dealer_war_card = self.game.dealer_war_cards[-1] if self.game.dealer_war_cards else None

        # 保存历史
        try:
            save_casino_war_history(
                self.game.initial_player_card,
                self.game.initial_dealer_card,
                result_info={"winner": winner, "surrender": self.game.surrendered},
                player_war_card=player_war_card,
                dealer_war_card=dealer_war_card
            )
        except Exception as e:
            print(f"保存历史失败: {e}")

        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.tie_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("tie"))
        self.tie_display.bind("<Button-3>", lambda e: self.reset_single_bet("tie", e))
        self.jackpot_check.config(state=tk.NORMAL)
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        self.show_restart_button()

    # ---------- 重置相关 ----------
    def reset_bets(self):
        self.ante_var.set("0")
        self.tie_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')

    def apply_last_bet(self):
        if self.last_bet is None:
            return
        ante = self.last_bet['ante']
        tie = self.last_bet['tie']
        jack = self.last_bet.get('jackpot', 0)
        if self.high_bet_mode:
            max_ante, max_tie = 50000, 12500
            min_ante = 100
        else:
            max_ante, max_tie = 10000, 2500
            min_ante = 10
        if ante < min_ante: ante = min_ante
        if ante > max_ante: ante = max_ante
        if tie > max_tie: tie = max_tie
        self.ante_var.set(str(ante))
        self.tie_var.set(str(tie))
        self.jackpot_bet_var.set(1 if jack > 0 else 0)
        self.status_label.config(text="已应用上次下注金额")
        self.ante_display.config(bg='#E8F5E9')
        self.tie_display.config(bg='#E8F5E9')
        self.after(800, lambda: self.ante_display.config(bg='white'))
        self.after(800, lambda: self.tie_display.config(bg='white'))

    def show_restart_button(self):
        self.clear_btn_frame()
        restart_btn = tk.Button(
            self.btn_frame, text="再来一局",
            command=lambda: self._on_restart(restart_btn),
            font=('Arial',12,'bold'), bg='#2196F3', fg='white', width=10
        )
        restart_btn.pack()
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def _on_restart(self, btn):
        btn.config(state=tk.DISABLED)
        self.reset_game()

    def reset_game(self, auto_reset=False):
        if self.war_animation_running:
            return
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
        self.game = CasinoWarGame()
        self.stage_label.config(text="等待下注")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        self.ante_var.set("0")
        self.tie_var.set("0")
        self.jackpot_bet_var.set(self.last_jackpot_state)
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.progressive_display.config(bg=PANEL_BG)
        self.active_card_labels = []
        for frame in [self.player_cards_frame, self.dealer_cards_frame]:
            for w in frame.winfo_children():
                w.destroy()

        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante", e))
        self.tie_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("tie"))
        self.tie_display.bind("<Button-3>", lambda e: self.reset_single_bet("tie", e))
        self.jackpot_check.config(state=tk.NORMAL)
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))

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
        all_labels = []
        for frame in [self.player_cards_frame, self.dealer_cards_frame]:
            for child in frame.winfo_children():
                if hasattr(child, 'card') and child.winfo_exists():
                    all_labels.append(child)
        if not all_labels:
            self._do_reset(auto_reset)
            return
        for lbl in all_labels:
            try:
                if lbl.winfo_exists():
                    lbl.target_pos = (1200, lbl.winfo_y())
                    self.active_card_labels.append(lbl)
            except:
                pass
        self.animate_card_out_step(auto_reset)

    def animate_card_out_step(self, auto_reset):
        all_done = True
        for lbl in self.active_card_labels[:]:
            if not lbl.winfo_exists():
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
                continue
            try:
                cx = lbl.winfo_x()
                tx, ty = lbl.target_pos
                dx = tx - cx
                if abs(dx) < 5:
                    lbl.place(x=tx, y=ty)
                    lbl.destroy()
                    if lbl in self.active_card_labels:
                        self.active_card_labels.remove(lbl)
                    continue
                new_x = cx + dx * 0.15
                lbl.place(x=new_x)
                all_done = False
            except:
                if lbl in self.active_card_labels:
                    self.active_card_labels.remove(lbl)
        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset))
        else:
            self._do_reset(auto_reset)

    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.btn_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)

# =========================================================
# 主入口
# =========================================================
def main(initial_balance=10000, username="Guest"):
    app = CasinoWarGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")