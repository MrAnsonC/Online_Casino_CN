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
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import time
import secrets
import subprocess
import sys
import math

# =========================================================
# 颜色与常量
# =========================================================
ROOT_BG = "#1B3D31"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
GOLD = "#D4AF37"

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}

# =========================================================
# 文件路径工具
# =========================================================
def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def user_data_path() -> str:
    return os.path.join(project_root(), "A_Tools/Account/saving_data.json")

def inout_log_path() -> str:
    log_dir = os.path.join(project_root(), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "In_Or_Out.json")

def get_data_file_path():
    return user_data_path()

def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    with open(get_data_file_path(), 'r', encoding='utf-8') as f:
        return json.load(f)

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:,.2f}"
            break
    save_user_data(users)

# =========================================================
# 扑克牌与牌堆
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
# 历史记录管理
# =========================================================
def load_inout_stats():
    log_path = inout_log_path()
    default = {
        "history_record": {
            "inner_win": 0,
            "outer_win": 0,
            "game": 0,
            "position": {str(i): 0 for i in range(1, 50)},
            "chance_in_or_out": {rank: {"In": 0, "Out": 0} for rank in RANKS}
        },
        "history": []
    }
    if not os.path.exists(log_path):
        return default
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "history_record" not in data:
                data["history_record"] = default["history_record"]
            if "history" not in data:
                data["history"] = []
            for i in range(1, 50):
                if str(i) not in data["history_record"]["position"]:
                    data["history_record"]["position"][str(i)] = 0
            if "chance_in_or_out" not in data["history_record"]:
                data["history_record"]["chance_in_or_out"] = default["history_record"]["chance_in_or_out"]
            else:
                for rank in RANKS:
                    if rank not in data["history_record"]["chance_in_or_out"]:
                        data["history_record"]["chance_in_or_out"][rank] = {"In": 0, "Out": 0}
            return data
    except:
        return default

def save_inout_stats(data):
    with open(inout_log_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def add_inout_history(deck, target_card, final_position, final_card, winnings):
    data = load_inout_stats()
    stats = data["history_record"]
    stats["game"] += 1
    if 1 <= final_position <= 49:
        stats["position"][str(final_position)] += 1
    if final_position % 2 == 1:
        stats["inner_win"] += 1
        region = "In"
    else:
        stats["outer_win"] += 1
        region = "Out"
    rank = final_card.rank
    if rank in stats["chance_in_or_out"]:
        stats["chance_in_or_out"][rank][region] += 1

    if data["history"]:
        last_id = data["history"][-1]["game_id"]
        new_id = last_id + 1
    else:
        new_id = 1

    record = {
        "game_id": new_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "target_card": str(target_card),
        "final_card": {
            "number_of_it_position": final_position,
            "card_name": str(final_card)
        }
    }
    if winnings > 0:
        record["winnings"] = winnings
    data["history"].append(record)
    if len(data["history"]) > 50:
        data["history"] = data["history"][-50:]
    save_inout_stats(data)

# =========================================================
# 游戏逻辑
# =========================================================
class InOutGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.target_card = None
        self.inner_cards = []
        self.outer_cards = []
        self.current_position = 0
        self.finished = False
        self.match_position = None
        self.match_card = None
        self.match_region = None
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence

    def deal_target(self):
        if self.deck.pointer >= 52:
            self.deck = Deck()
        self.target_card = self.deck.deal(1)[0]
        return self.target_card

    def start_round(self):
        self.finished = False
        self.inner_cards = []
        self.outer_cards = []
        self.current_position = 0
        while True:
            if self.deck.pointer >= 52:
                self.deck = Deck()
            card = self.deck.deal(1)[0]
            self.current_position += 1
            if self.current_position % 2 == 1:
                self.inner_cards.append(card)
                region = 'inner'
            else:
                self.outer_cards.append(card)
                region = 'outer'
            if card.rank == self.target_card.rank:
                self.match_position = self.current_position
                self.match_card = card
                self.match_region = region
                self.finished = True
                break
        return self.inner_cards, self.outer_cards, self.match_position, self.match_region, self.match_card

# =========================================================
# 主GUI
# =========================================================
class InOutGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.configure(bg=ROOT_BG)

        self.username = username
        self.balance = initial_balance
        self.game = InOutGame()
        self.card_images = {}
        self.original_images = {}
        self.back_image = None
        self._load_assets()

        self.inner_bet_var = tk.StringVar(value="0")
        self.outer_bet_var = tk.StringVar(value="0")
        self.zone_bet_vars = [tk.StringVar(value="0") for _ in range(10)]

        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.last_win = 0
        self.auto_reset_timer = None
        self.last_game_bet = None
        self.analysis_label = None

        self.bet_canvas = None
        self.bet_cells = {}

        self.betting_enabled = True

        self._create_widgets()
        self.deal_target_card()

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
            back_img = Image.open(back_path).resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
            self.original_images["back"] = back_img
        except:
            img = Image.new('RGB', card_size, 'black')
            self.back_image = ImageTk.PhotoImage(img)
            self.original_images["back"] = img
        for suit in SUITS:
            for rank in RANKS:
                fname = f"{suit_mapping[suit]}{rank}.png"
                path = os.path.join(card_dir, fname)
                try:
                    if os.path.exists(path):
                        img = Image.open(path).resize(card_size)
                    else:
                        img = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img)
                        text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        draw.text((30, 50), text, fill="white", font=font)
                    self.original_images[(suit, rank)] = img
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img)
                except Exception as e:
                    print(f"Error loading {path}: {e}")
                    img = Image.new('RGB', card_size, 'red')
                    self.original_images[(suit, rank)] = img
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img)

    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item in chip.find_all():
                if chip.type(item) == 'oval':
                    x1,y1,x2,y2 = chip.coords(item)
                    chip.create_oval(x1,y1,x2,y2, outline='black', width=2)
                    break
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            for item in chip.find_all():
                t = chip.type(item)
                if t == 'text':
                    text_id = item
                elif t == 'oval':
                    oval_id = item
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                x1,y1,x2,y2 = chip.coords(oval_id)
                chip.create_oval(x1,y1,x2,y2, outline='#2f00ff', width=3, tags="highlight")
                break

    # 修改点：自动调整至上限，而不是报错
    def add_chip_to_bet(self, bet_type, index=None):
        if not self.betting_enabled:
            return
        if not self.selected_chip:
            return
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)

        if bet_type == "inner":
            max_bet = 10000
            cur = float(self.inner_bet_var.get()) if self.inner_bet_var.get() else 0
            new_val = cur + chip_value
            if new_val > max_bet:
                new_val = max_bet
            self.inner_bet_var.set(f"{new_val:.0f}")
        elif bet_type == "outer":
            max_bet = 10000
            cur = float(self.outer_bet_var.get()) if self.outer_bet_var.get() else 0
            new_val = cur + chip_value
            if new_val > max_bet:
                new_val = max_bet
            self.outer_bet_var.set(f"{new_val:.0f}")
        elif bet_type == "zone" and index is not None:
            max_bet = 2500
            cur = float(self.zone_bet_vars[index].get()) if self.zone_bet_vars[index].get() else 0
            new_val = cur + chip_value
            if new_val > max_bet:
                new_val = max_bet
            self.zone_bet_vars[index].set(f"{new_val:.0f}")
        self.update_bet_display()

    def reset_single_bet(self, bet_type, index=None, event=None):
        if bet_type == "inner":
            self.inner_bet_var.set("0")
        elif bet_type == "outer":
            self.outer_bet_var.set("0")
        elif bet_type == "zone" and index is not None:
            self.zone_bet_vars[index].set("0")
        self.update_bet_display()

    def update_bet_display(self):
        if not self.bet_canvas:
            return
        inner_amt = float(self.inner_bet_var.get()) if self.inner_bet_var.get() else 0
        self._update_cell_display("inner", inner_amt)
        outer_amt = float(self.outer_bet_var.get()) if self.outer_bet_var.get() else 0
        self._update_cell_display("outer", outer_amt)
        zone_names = ["1-5","6-10","11-15","16-20","21-25",
                      "26-30","31-35","36-40","41-45","46-49"]
        odds = ["5:2","3:1","9:2","6:1","9:1","14:1","23:1","44:1","125:1","950:1"]
        for i in range(10):
            amt = float(self.zone_bet_vars[i].get()) if self.zone_bet_vars[i].get() else 0
            self._update_cell_display(f"zone_{i}", amt, zone_names[i], odds[i])

    def _update_cell_display(self, cell_id, amount, label=None, odds_text=None):
        if cell_id not in self.bet_cells:
            return
        items = self.bet_cells[cell_id]
        bg_rect, text_ids = items
        for tid in text_ids:
            self.bet_canvas.delete(tid)
        bg_color = "#E8E8E8"
        if label:
            display_text = f"{label}\n{odds_text}\n${amount:.0f}"
        else:
            if cell_id == "inner":
                title = "内区 0.9:1"
            else:
                title = "外区 1:1"
            display_text = f"{title}\n${amount:.0f}"
        self.bet_canvas.itemconfig(bg_rect, fill=bg_color)
        x1, y1, x2, y2 = self.bet_canvas.coords(bg_rect)
        cx = (x1+x2)/2
        cy = (y1+y2)/2
        lines = display_text.split('\n')
        new_text_ids = []
        tag = cell_id
        if len(lines) == 3:
            tid1 = self.bet_canvas.create_text(cx, cy-14, text=lines[0], fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            tid2 = self.bet_canvas.create_text(cx, cy+2, text=lines[1], fill="black", font=("Arial", 8, "bold"), tags=(tag,cell_id))
            tid3 = self.bet_canvas.create_text(cx, cy+16, text=lines[2], fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            new_text_ids = (tid1, tid2, tid3)
        elif len(lines) == 2:
            tid1 = self.bet_canvas.create_text(cx, cy-10, text=lines[0], fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            tid2 = self.bet_canvas.create_text(cx, cy+14, text=lines[1], fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            new_text_ids = (tid1, tid2)
        else:
            tid1 = self.bet_canvas.create_text(cx, cy, text=display_text, fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            new_text_ids = (tid1,)
        self.bet_cells[cell_id] = (bg_rect, new_text_ids)
        self.bet_canvas.tag_raise(f"cover_{cell_id}")

    def _set_cell_display_direct(self, cell_id, lines, bg_color):
        if cell_id not in self.bet_cells:
            return
        bg_rect, old_text_ids = self.bet_cells[cell_id]
        for tid in old_text_ids:
            self.bet_canvas.delete(tid)
        self.bet_canvas.itemconfig(bg_rect, fill=bg_color)
        x1, y1, x2, y2 = self.bet_canvas.coords(bg_rect)
        cx = (x1+x2)/2
        cy = (y1+y2)/2
        new_text_ids = []
        tag = cell_id
        if len(lines) == 3:
            tid1 = self.bet_canvas.create_text(cx, cy-14, text=lines[0], fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            tid2 = self.bet_canvas.create_text(cx, cy+2, text=lines[1], fill="black", font=("Arial", 8, "bold"), tags=(tag,cell_id))
            tid3 = self.bet_canvas.create_text(cx, cy+16, text=lines[2], fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            new_text_ids = (tid1, tid2, tid3)
        elif len(lines) == 2:
            tid1 = self.bet_canvas.create_text(cx, cy-10, text=lines[0], fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            tid2 = self.bet_canvas.create_text(cx, cy+14, text=lines[1], fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            new_text_ids = (tid1, tid2)
        else:
            tid1 = self.bet_canvas.create_text(cx, cy, text=lines[0], fill="black", font=("Arial", 9, "bold"), tags=(tag,cell_id))
            new_text_ids = (tid1,)
        self.bet_cells[cell_id] = (bg_rect, new_text_ids)
        self.bet_canvas.tag_raise(f"cover_{cell_id}")

    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        table = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0)
        table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner_frame = tk.Frame(table, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        inner_frame.place(x=10, y=5, width=670, height=220)
        tk.Label(inner_frame, text="内区", font=('Arial',16), bg='#2a4a3c', fg='white').pack(anchor='w', padx=10, pady=5)
        inner_canvas_frame = tk.Frame(inner_frame, bg='#2a4a3c')
        inner_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.inner_canvas = tk.Canvas(inner_canvas_frame, bg='#2a4a3c', highlightthickness=0)
        h_scroll_inner = ttk.Scrollbar(inner_canvas_frame, orient=tk.HORIZONTAL, command=self.inner_canvas.xview)
        self.inner_canvas.configure(xscrollcommand=h_scroll_inner.set)
        self.inner_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        h_scroll_inner.pack(side=tk.BOTTOM, fill=tk.X)

        target_frame = tk.Frame(table, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        target_frame.place(x=10, y=235, width=200, height=220)
        tk.Label(target_frame, text="目标牌", font=('Arial',16), bg='#2a4a3c', fg='white').pack(anchor='w', padx=10, pady=5)
        self.target_canvas = tk.Canvas(target_frame, bg='#2a4a3c', highlightthickness=0)
        self.target_canvas.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        analysis_frame = tk.Frame(table, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        analysis_frame.place(x=220, y=235, width=200, height=220)
        tk.Label(analysis_frame, text="内外区比例", font=('Arial',14), bg='#2a4a3c', fg='white').pack(anchor='w', padx=10, pady=5)
        self.analysis_canvas = tk.Canvas(analysis_frame, bg='#2a4a3c', highlightthickness=0)
        self.analysis_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        current_card_frame = tk.Frame(table, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        current_card_frame.place(x=430, y=235, width=150, height=220)
        tk.Label(current_card_frame, text="当前的第X张牌", font=('Arial',14), bg='#2a4a3c', fg='white').pack(anchor='w', padx=10, pady=5)
        self.current_card_display = tk.Label(
            current_card_frame,
            text="0",
            font=('Arial', 90, 'bold'),
            bg='#2a4a3c',
            fg='white',
            justify='center'
        )
        self.current_card_display.pack(expand=True)

        outer_frame = tk.Frame(table, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        outer_frame.place(x=10, y=465, width=670, height=220)
        tk.Label(outer_frame, text="外区", font=('Arial',16), bg='#2a4a3c', fg='white').pack(anchor='w', padx=10, pady=5)
        outer_canvas_frame = tk.Frame(outer_frame, bg='#2a4a3c')
        outer_canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.outer_canvas = tk.Canvas(outer_canvas_frame, bg='#2a4a3c', highlightthickness=0)
        h_scroll_outer = ttk.Scrollbar(outer_canvas_frame, orient=tk.HORIZONTAL, command=self.outer_canvas.xview)
        self.outer_canvas.configure(xscrollcommand=h_scroll_outer.set)
        self.outer_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        h_scroll_outer.pack(side=tk.BOTTOM, fill=tk.X)

        right = tk.Frame(main_frame, bg=ROOT_BG, width=380)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        info = tk.Frame(right, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info.pack(fill=tk.X, pady=3)
        tk.Frame(info, bg=HEADER_BG).pack(fill=tk.X)
        body_info = tk.Frame(info, bg=PANEL_BG)
        body_info.pack(fill=tk.X, padx=10, pady=8)
        self.balance_label = tk.Label(body_info, text=f"余额: ${self.balance:,.2f}", font=('Arial',16,'bold'), bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body_info, text="等待开始", font=('Arial',16,'bold'), bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        limit = tk.Frame(right, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit.pack(fill=tk.X, pady=3)
        tk.Frame(limit, bg=HEADER_BG).pack(fill=tk.X)
        body_limit = tk.Frame(limit, bg=PANEL_BG)
        body_limit.pack(fill=tk.X, padx=10, pady=8)
        tbl = tk.Frame(body_limit, bg=PANEL_BG, bd=2, relief=tk.SOLID)
        tbl.pack(fill=tk.X)
        titles = ["内外区最高","区域范围最高"]
        for c,t in enumerate(titles):
            lbl = tk.Label(tbl, text=t, font=('Arial',11,'bold'), bg=PANEL_BG, fg='#2A1B08',
                           borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
            lbl.grid(row=0, column=c, sticky="nsew")
        vals = ["$10,000","$2,500"]
        for c,v in enumerate(vals):
            lbl = tk.Label(tbl, text=v, font=('Arial',12,'bold'), bg=PANEL_BG, fg="#A88100",
                           borderwidth=1, relief=tk.SOLID, padx=5, pady=5)
            lbl.grid(row=1, column=c, sticky="nsew")
        for c in range(2):
            tbl.columnconfigure(c, weight=1)

        combined = tk.Frame(right, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined.pack(fill=tk.X, pady=3)
        tk.Frame(combined, bg=HEADER_BG).pack(fill=tk.X)
        body_comb = tk.Frame(combined, bg=PANEL_BG)
        body_comb.pack(fill=tk.X, padx=10, pady=8)

        chip_row = tk.Frame(body_comb, bg=PANEL_BG)
        chip_row.pack(fill=tk.X, pady=(0,8))
        chip_configs = [('$10','#ffa500','black'),('$25','#00ff00','black'),('$100','#000000','white'),
                        ('$500','#FF7DDA','black'),('$1K','#ffffff','black'),('$2.5K','#ff0000','white')]
        self.chip_buttons = []
        self.chip_texts = {}
        for i,(text,bgcol,fcol) in enumerate(chip_configs):
            cell = tk.Frame(chip_row, bg=PANEL_BG)
            cell.pack(side=tk.LEFT, padx=2, pady=2, expand=True, fill=tk.BOTH)
            canvas = tk.Canvas(cell, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            canvas.pack(anchor='center')
            canvas.create_oval(2,2,49,49, fill=bgcol, outline='black')
            canvas.create_text(25.5,25.5, text=text, fill=fcol, font=('Arial',12,'bold'))
            canvas.bind("<Button-1>", lambda e,t=text: self.select_chip(t))
            self.chip_buttons.append(canvas)
            self.chip_texts[canvas] = text
        self.select_chip("$10")

        bet_frame = tk.Frame(body_comb, bg=PANEL_BG)
        bet_frame.pack(fill=tk.X, pady=5)
        self.bet_canvas = tk.Canvas(bet_frame, width=360, height=260, bg=PANEL_BG, highlightthickness=0)
        self.bet_canvas.pack()
        self._draw_bet_table()

        action = tk.Frame(right, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        action.pack(fill=tk.X, pady=3)
        tk.Frame(action, bg=HEADER_BG).pack(fill=tk.X)
        body_action = tk.Frame(action, bg=PANEL_BG)
        body_action.pack(fill=tk.X, padx=10, pady=8)

        self.status_label = tk.Label(body_action, text="设置下注并开始游戏", font=('Arial',12,'bold'),
                                     bg=PANEL_BG, fg='#2A1B08')
        self.status_label.pack(fill=tk.X, pady=4)

        self.fixed_buttons_frame = tk.Frame(body_action, bg=PANEL_BG)
        self.fixed_buttons_frame.pack(fill=tk.X, pady=5)

        for col in range(3):
            self.fixed_buttons_frame.grid_columnconfigure(col, weight=1)

        self.reset_bets_button = tk.Button(self.fixed_buttons_frame, text="重设金额", command=self.reset_bets,
                                           font=('Arial',12,'bold'), bg='#F44336', fg='white',
                                           relief=tk.RAISED, bd=2, cursor="hand2")
        self.reset_bets_button.grid(row=0, column=0, padx=2, pady=2, sticky='ew')

        self.repeat_bet_button = tk.Button(self.fixed_buttons_frame, text="重复上局下注", command=self.repeat_last_bet,
                                           font=('Arial',12,'bold'), bg='#FFC107', fg='black',
                                           relief=tk.RAISED, bd=2, cursor="hand2",
                                           state=tk.DISABLED)
        self.repeat_bet_button.grid(row=0, column=1, padx=2, pady=2, sticky='ew')

        self.start_button = tk.Button(self.fixed_buttons_frame, text="开始游戏", command=self.start_game,
                                      font=('Arial',12,'bold'), bg='#4CAF50', fg='white',
                                      relief=tk.RAISED, bd=2, cursor="hand2")
        self.start_button.grid(row=0, column=2, padx=2, pady=2, sticky='ew')

        self.restart_button = tk.Button(self.fixed_buttons_frame, text="再来一局", command=self.reset_game,
                                        font=('Arial',12,'bold'), bg='#2196F3', fg='white',
                                        relief=tk.RAISED, bd=2, cursor="hand2",
                                        state=tk.DISABLED)
        self.restart_button.grid(row=0, column=1, columnspan=1, padx=2, pady=2, sticky='ew')
        self.restart_button.grid_remove()
        self.restart_button.bind("<Button-3>", self.show_card_sequence)

        self.action_frame = body_action

        bottom = tk.Frame(right, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        bottom.pack(fill=tk.X, pady=3)
        body_bottom = tk.Frame(bottom, bg=PANEL_BG)
        body_bottom.pack(fill=tk.X, padx=10, pady=8)

        self.current_bet_label = tk.Label(body_bottom, text="本局下注: $0.00", font=('Arial',12), bg=PANEL_BG, fg='black')
        self.current_bet_label.pack(anchor='w')
        row_last = tk.Frame(body_bottom, bg=PANEL_BG)
        row_last.pack(fill=tk.X, pady=2)
        self.last_win_label = tk.Label(row_last, text="上局获胜: $0.00", font=('Arial',12), bg=PANEL_BG, fg='black')
        self.last_win_label.pack(side=tk.LEFT)
        self.info_button = tk.Button(row_last, text="ℹ️", command=self.show_game_instructions,
                                     bg='#4B8BBE', fg='white', font=('Arial',12), width=2, relief=tk.FLAT)
        self.info_button.pack(side=tk.RIGHT)

    def _draw_bet_table(self):
        canvas = self.bet_canvas
        canvas.delete("all")
        self.bet_cells = {}

        padding = 5
        avail_w = 360 - 2 * padding
        gap_h = 0
        gap_v = 3

        top_h = 55
        half_w = (avail_w - gap_h) // 2

        zone_w = (avail_w - 4 * gap_h) // 5
        row_h = 85

        # =========================
        # 内区
        # =========================
        x0 = padding
        y0 = padding

        rect = canvas.create_rectangle(
            x0, y0,
            x0 + half_w, y0 + top_h,
            fill="#E8E8E8",
            outline="black",
            width=2
        )

        tid = canvas.create_text(
            x0 + half_w / 2,
            y0 + top_h / 2,
            text="内区 0.9:1\n$0",
            font=("Arial", 9, "bold")
        )

        self.bet_cells["inner"] = (rect, (tid,))

        cover = canvas.create_rectangle(
            x0, y0,
            x0 + half_w, y0 + top_h,
            fill="",
            outline="",
            tags=("cover_inner",)
        )

        canvas.tag_bind(
            "cover_inner",
            "<Button-1>",
            lambda e: self.add_chip_to_bet("inner")
        )

        canvas.tag_bind(
            "cover_inner",
            "<Button-3>",
            lambda e: self.reset_single_bet("inner")
        )

        # =========================
        # 外区
        # =========================
        x0 = padding + half_w + gap_h

        rect = canvas.create_rectangle(
            x0, y0,
            x0 + half_w, y0 + top_h,
            fill="#E8E8E8",
            outline="black",
            width=2
        )

        tid = canvas.create_text(
            x0 + half_w / 2,
            y0 + top_h / 2,
            text="外区 1:1\n$0",
            font=("Arial", 9, "bold")
        )

        self.bet_cells["outer"] = (rect, (tid,))

        cover = canvas.create_rectangle(
            x0, y0,
            x0 + half_w, y0 + top_h,
            fill="",
            outline="",
            tags=("cover_outer",)
        )

        canvas.tag_bind(
            "cover_outer",
            "<Button-1>",
            lambda e: self.add_chip_to_bet("outer")
        )

        canvas.tag_bind(
            "cover_outer",
            "<Button-3>",
            lambda e: self.reset_single_bet("outer")
        )

        # =========================
        # 区域下注
        # =========================
        zone_names = [
            "1-5", "6-10", "11-15", "16-20", "21-25",
            "26-30", "31-35", "36-40", "41-45", "46-49"
        ]

        odds = [
            "5:2", "3:1", "9:2", "6:1", "9:1",
            "14:1", "23:1", "44:1", "125:1", "950:1"
        ]

        y_start = padding + top_h + gap_v

        for row in range(2):
            y = y_start + row * (row_h + gap_v)

            for col in range(5):

                idx = row * 5 + col
                x = padding + col * (zone_w + gap_h)

                rect = canvas.create_rectangle(
                    x,
                    y,
                    x + zone_w,
                    y + row_h,
                    fill="#E8E8E8",
                    outline="black",
                    width=2
                )

                tid = canvas.create_text(
                    x + zone_w / 2,
                    y + row_h / 2,
                    text=f"{zone_names[idx]}\n{odds[idx]}\n$0",
                    font=("Arial", 8, "bold"),
                    justify="center"
                )

                self.bet_cells[f"zone_{idx}"] = (rect, (tid,))

                cover = canvas.create_rectangle(
                    x,
                    y,
                    x + zone_w,
                    y + row_h,
                    fill="",
                    outline="",
                    tags=(f"cover_zone_{idx}",)
                )

                canvas.tag_bind(
                    f"cover_zone_{idx}",
                    "<Button-1>",
                    lambda e, idx=idx: self.add_chip_to_bet("zone", idx)
                )

                canvas.tag_bind(
                    f"cover_zone_{idx}",
                    "<Button-3>",
                    lambda e, idx=idx: self.reset_single_bet("zone", idx)
                )

        self.update_bet_display()

    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("游戏规则")
        win.geometry("600x500")
        win.resizable(False,False)
        win.configure(bg='#F0F0F0')
        main = tk.Frame(win, bg='#F0F0F0')
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scroll = ttk.Scrollbar(main)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main, bg='#F0F0F0', yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.config(command=canvas.yview)
        content = tk.Frame(canvas, bg='#F0F0F0')
        canvas.create_window((0,0), window=content, anchor='nw')
        rules = """
内外注 游戏规则

1. 下注：
   - 内区：押注匹配牌落在内区（第1、3、5...张），赔率0.9:1
   - 外区：押注匹配牌落在外区（第2、4、6...张），赔率1:1
   - 区间注：押注匹配牌的位置所属区间，赔率如下：
     1-5   : 5:2    6-10  : 3:1    11-15 : 9:2  
     16-20 : 6:1    21-25 : 9:1    26-30 : 14:1
     31-35 : 23:1   36-40 : 44:1   41-45 : 125:1
     46-49 : 950:1
   - 下注1元，赔率5:2，赢2元，共返还3元

2. 发牌流程：
   - 每局先发一张目标牌（显示在目标区）
   - 玩家下注后点击“开始游戏”
   - 系统按牌序交替发牌：先内区，再外区，依次类推
   - 直到某张牌的点数与目标牌相同，停止发牌
   - 记录该牌的位置（第几张）和所在区域

3. 可全不下注，仅观看。

4. 历史记录保存最近50局，统计内/外区获胜次数、各位置出现次数，
   以及每个点数在内/外区出现的次数。
        """
        tk.Label(content, text=rules, font=('微软雅黑',11), bg='#F0F0F0', justify=tk.LEFT).pack(padx=10, pady=10)
        content.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    def deal_target_card(self):
        self.target_canvas.delete("all")
        card = self.game.deal_target()
        img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.target_canvas.create_image(20, 0, image=img, anchor='nw')
        self.target_canvas.image = img
        self.status_label.config(text="目标牌已发，请下注并开始")
        self.update_analysis(card.rank)
        self.current_card_display.config(text="0")

    def start_game(self):
        try:
            inner_bet = float(self.inner_bet_var.get()) if self.inner_bet_var.get() else 0
            outer_bet = float(self.outer_bet_var.get()) if self.outer_bet_var.get() else 0
            zone_bets = [float(v.get()) if v.get() else 0 for v in self.zone_bet_vars]
        except:
            messagebox.showerror("错误", "请输入有效数字")
            return

        # 额外安全检查，但add_chip_to_bet已保证不超过上限
        if inner_bet > 10000 or outer_bet > 10000:
            messagebox.showerror("错误", "内区/外区下注不能超过 $10,000")
            return
        for i, b in enumerate(zone_bets):
            if b > 2500:
                messagebox.showerror("错误", f"区域 {i+1} 下注不能超过 $2,500")
                return

        total = inner_bet + outer_bet + sum(zone_bets)
        if total > self.balance:
            messagebox.showerror("错误", "余额不足")
            return

        self.betting_enabled = False

        self.balance -= total
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total:,.2f}")

        self.last_game_bet = {'inner': inner_bet, 'outer': outer_bet, 'zone': zone_bets[:]}
        self.repeat_bet_button.config(state=tk.NORMAL)

        self.reset_bets_button.grid_remove()
        self.repeat_bet_button.grid_remove()
        self.start_button.grid_remove()
        self.restart_button.grid()
        self.restart_button.config(state=tk.DISABLED)

        for child in self.action_frame.winfo_children():
            if child not in [self.fixed_buttons_frame, self.status_label]:
                child.destroy()

        self.status_label.config(text="发牌中...")
        self.stage_label.config(text="发牌中")

        self.inner_canvas.delete("all")
        self.outer_canvas.delete("all")
        self.game.inner_cards = []
        self.game.outer_cards = []
        self.game.current_position = 0
        self.game.finished = False

        self._deal_next_card(inner_bet, outer_bet, zone_bets)

    def update_analysis(self, rank):
        stats = load_inout_stats()
        record = stats.get("history_record", {})
        chance = record.get("chance_in_or_out", {})
        if rank not in chance:
            self.draw_pie_chart(0, 0)
            return
        data = chance[rank]
        inner_count = data.get("In", 0)
        outer_count = data.get("Out", 0)
        self.draw_pie_chart(inner_count, outer_count)

    def draw_pie_chart(self, inner_count, outer_count):
        canvas = self.analysis_canvas
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 10 or h < 10:
            canvas.after(100, lambda: self.draw_pie_chart(inner_count, outer_count))
            return

        radius = min(w, h) * 0.35
        cx = w * 0.45
        cy = h * 0.5

        total = inner_count + outer_count
        if total == 0:
            canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                            fill='#666666', outline='white', width=2)
            canvas.create_text(cx, cy, text='无数据', fill='white', font=('Arial', 10, 'bold'))
            return

        inner_angle = (inner_count / total) * 360
        outer_angle = 360 - inner_angle

        if inner_angle > 0:
            canvas.create_arc(cx - radius, cy - radius, cx + radius, cy + radius,
                            start=0, extent=inner_angle, fill='#4A90D9', outline='white', width=1)
        if outer_angle > 0:
            canvas.create_arc(cx - radius, cy - radius, cx + radius, cy + radius,
                            start=inner_angle, extent=outer_angle, fill='#E67E22', outline='white', width=1)

        inner_pct = (inner_count / total) * 100
        outer_pct = 100 - inner_pct
        center_text = f"内 {inner_pct:.0f}%\n\n外 {outer_pct:.0f}%"
        canvas.create_text(cx, cy, text=center_text, fill='white', font=('Arial', 20, 'bold'),
                        justify='center')

    def _deal_next_card(self, inner_bet, outer_bet, zone_bets):
        if self.game.finished:
            return
        if self.game.deck.pointer >= 52:
            self.game.deck = Deck()
        card = self.game.deck.deal(1)[0]
        self.game.current_position += 1
        if self.game.current_position % 2 == 1:
            self.game.inner_cards.append(card)
            region = 'inner'
            canvas = self.inner_canvas
        else:
            self.game.outer_cards.append(card)
            region = 'outer'
            canvas = self.outer_canvas

        self.current_card_display.config(text=f"{self.game.current_position}")

        self.update_zone_bets_by_position(self.game.current_position)
        self._animate_card_in(canvas, card, region, lambda: self._after_card_animation(inner_bet, outer_bet, zone_bets, card, region))

    def _animate_card_in(self, canvas, card, region, callback):
        if region == 'inner':
            count = len(self.game.inner_cards) - 1
        else:
            count = len(self.game.outer_cards) - 1
        target_x = count * 20
        total_width = count * 20 + 100 + 20
        canvas.config(scrollregion=(0, 0, total_width, 160))
        img_id = canvas.create_image(-100, 10, image=self.back_image, anchor='nw')
        if not hasattr(canvas, 'images'):
            canvas.images = []
        canvas.images.append(self.back_image)
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self._move_card_to_target(canvas, img_id, target_x, front_img, callback)

    def _move_card_to_target(self, canvas, img_id, target_x, front_img, callback):
        x = canvas.coords(img_id)[0]
        if x < target_x - 2:
            dx = min(20, target_x - x)
            canvas.move(img_id, dx, 0)
            canvas.after(30, lambda: self._move_card_to_target(canvas, img_id, target_x, front_img, callback))
        else:
            canvas.itemconfig(img_id, image=front_img)
            canvas.images.append(front_img)
            callback()

    def _after_card_animation(self, inner_bet, outer_bet, zone_bets, card, region):
        if card.rank == self.game.target_card.rank:
            self.game.match_position = self.game.current_position
            self.game.match_card = card
            self.game.match_region = region
            self.game.finished = True
            self.after(800, lambda: self.settle(inner_bet, outer_bet, zone_bets,
                                                self.game.match_position, self.game.match_region, self.game.match_card))
        else:
            self.after(300, lambda: self._deal_next_card(inner_bet, outer_bet, zone_bets))

    def update_zone_bets_by_position(self, current_pos):
        if current_pos > 49:
            current_idx = 10
        else:
            current_idx = (current_pos - 1) // 5
            if current_idx > 9:
                current_idx = 9

        zone_names = ["1-5","6-10","11-15","16-20","21-25",
                      "26-30","31-35","36-40","41-45","46-49"]
        odds_texts = ["5:2","3:1","9:2","6:1","9:1","14:1","23:1","44:1","125:1","950:1"]

        for i in range(10):
            cell_id = f"zone_{i}"
            if cell_id not in self.bet_cells:
                continue
            if i == current_idx:
                amt = float(self.zone_bet_vars[i].get()) if self.zone_bet_vars[i].get() else 0
                lines = [zone_names[i], odds_texts[i], f"${amt:.0f}"]
                self._set_cell_display_direct(cell_id, lines, "lightblue")
            elif i < current_idx:
                self.zone_bet_vars[i].set("0")
                lines = [zone_names[i], odds_texts[i], "$0"]
                self._set_cell_display_direct(cell_id, lines, "#E8E8E8")
            else:
                amt = float(self.zone_bet_vars[i].get()) if self.zone_bet_vars[i].get() else 0
                lines = [zone_names[i], odds_texts[i], f"${amt:.0f}"]
                self._set_cell_display_direct(cell_id, lines, "#E8E8E8")

    def settle(self, inner_bet, outer_bet, zone_bets, match_pos, region, match_card):
        inner_odds = 0.9
        outer_odds = 1.0
        zone_odds = [2.5, 3, 4.5, 6, 9, 14, 23, 44, 125, 950]

        total_win = 0
        total_payout = 0

        if region == 'inner':
            if inner_bet > 0:
                win = inner_bet * inner_odds
                total_win += win
                payout = inner_bet + win
                total_payout += payout
                self._set_cell_display_direct("inner", [f"内区 0.9:1", f"${payout:.0f}"], "gold")
            else:
                self._set_cell_display_direct("inner", [f"内区 0.9:1", "$0"], "gold")
        else:
            self._set_cell_display_direct("inner", [f"内区 0.9:1", "$0"], "#E8E8E8")

        if region == 'outer':
            if outer_bet > 0:
                win = outer_bet * outer_odds
                total_win += win
                payout = outer_bet + win
                total_payout += payout
                self._set_cell_display_direct("outer", [f"外区 1:1", f"${payout:.0f}"], "gold")
            else:
                self._set_cell_display_direct("outer", [f"外区 1:1", "$0"], "gold")
        else:
            self._set_cell_display_direct("outer", [f"外区 1:1", "$0"], "#E8E8E8")

        zone_names = ["1-5","6-10","11-15","16-20","21-25",
                      "26-30","31-35","36-40","41-45","46-49"]
        odds_texts = ["5:2","3:1","9:2","6:1","9:1","14:1","23:1","44:1","125:1","950:1"]

        for i in range(10):
            self._set_cell_display_direct(f"zone_{i}", [zone_names[i], odds_texts[i], "$0"], "#E8E8E8")

        if 1 <= match_pos <= 49:
            idx = (match_pos - 1) // 5
            if idx > 9:
                idx = 9
            if zone_bets[idx] > 0:
                bet = zone_bets[idx]
                odds = zone_odds[idx]
                win = bet * odds
                total_win += win
                payout = bet + win
                total_payout += payout
                self._set_cell_display_direct(f"zone_{idx}", [zone_names[idx], odds_texts[idx], f"${payout:.0f}"], "gold")
            else:
                self._set_cell_display_direct(f"zone_{idx}", [zone_names[idx], odds_texts[idx], "$0"], "gold")

        self.balance += total_win
        self.update_balance()

        self.last_win = total_payout
        self.last_win_label.config(text=f"上局获胜: ${total_payout:,.2f}")

        add_inout_history(self.game.deck, self.game.target_card, match_pos, match_card, total_win)

        if total_win > 0:
            self.status_label.config(text=f"匹配位置 {match_pos}")
        else:
            self.status_label.config(text=f"匹配位置 {match_pos}")
        self.stage_label.config(text="已结束")

        self.restart_button.config(state=tk.NORMAL)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

        self.betting_enabled = True

        self.game.reset_game()
        self.inner_canvas.delete("all")
        self.outer_canvas.delete("all")
        self.target_canvas.delete("all")
        self.current_card_display.config(text="0")
        self.deal_target_card()
        self.stage_label.config(text="等待开始")
        self.status_label.config(text="已重置，请下注")
        self.start_button.config(state=tk.NORMAL)
        self.reset_bets_button.config(state=tk.NORMAL)
        if self.last_game_bet:
            self.repeat_bet_button.config(state=tk.NORMAL)
        else:
            self.repeat_bet_button.config(state=tk.DISABLED)

        self.restart_button.grid_remove()
        self.reset_bets_button.grid()
        self.repeat_bet_button.grid()
        self.start_button.grid()
        self.reset_bets()

        for child in self.action_frame.winfo_children():
            if child not in [self.fixed_buttons_frame, self.status_label]:
                child.destroy()

        self.current_bet_label.config(text="本局下注: $0.00")
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注并开始游戏"))

    def reset_bets(self):
        self.inner_bet_var.set("0")
        self.outer_bet_var.set("0")
        for v in self.zone_bet_vars:
            v.set("0")
        self.update_bet_display()
        self.status_label.config(text="已重置所有下注")

    def repeat_last_bet(self):
        if not self.last_game_bet:
            return
        self.inner_bet_var.set(f"{self.last_game_bet['inner']:.0f}")
        self.outer_bet_var.set(f"{self.last_game_bet['outer']:.0f}")
        for i, val in enumerate(self.last_game_bet['zone']):
            self.zone_bet_vars[i].set(f"{val:.0f}")
        self.update_bet_display()
        self.status_label.config(text="已重复上局下注")

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


# =========================================================
# 启动
# =========================================================
def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """嵌入现有 Tk 根窗口；未传 parent 时仍可独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return InOutGUI(
            parent, actual_balance, actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("In Or Out")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    page = InOutGUI(root, actual_balance, actual_user)
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
