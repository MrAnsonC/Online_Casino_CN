import sys as _account_sys
from pathlib import Path as _AccountPath
_account_root = next((p for p in (_AccountPath(__file__).resolve().parent, *_AccountPath(__file__).resolve().parents) if (p / "A_Tools" / "Account" / "secure_json.py").is_file()), None)
if _account_root is None:
    raise RuntimeError("Cannot locate encrypted account storage")
if str(_account_root) not in _account_sys.path:
    _account_sys.path.insert(0, str(_account_root))
from A_Tools.Account import install_secure_json as _install_secure_json
_install_secure_json()
_PROJECT_ROOT = str(_account_root)
del _install_secure_json, _account_root, _AccountPath, _account_sys

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
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
TEXT = "#ffffff"
RED = "#ff2a23"
BLACK = "#050505"
DARK_BLUE = "#173f66"

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}

# =========================================================
# 文件路径工具
# =========================================================
def project_root() -> str:
    return _PROJECT_ROOT

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
        parent_dir = _PROJECT_ROOT
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
# 玩法与赔率由 In Or Out 提供；牌桌控件沿用 Side Bet City。
GAME_NAME = '内外注'
ZONE_NAMES = ('1-5', '6-10', '11-15', '16-20', '21-25',
              '26-30', '31-35', '36-40', '41-45', '46-49')
ZONE_ODDS = (2.5, 3, 4.5, 6, 9, 14, 23, 44, 125, 950)
ZONE_ODDS_TEXT = ('5:2', '3:1', '9:2', '6:1', '9:1',
                  '14:1', '23:1', '44:1', '125:1', '950:1')
BET_TYPES = ('inner', 'outer') + tuple(f'zone_{i}' for i in range(10))
BET_NAMES = dict(inner='内区', outer='外区',
                 **{f'zone_{i}': name for i, name in enumerate(ZONE_NAMES)})
DEFAULT_BETTING_STATUS = '目标牌已发，请设置下注；也可不下注观看'

def money(value):
    """沿用 Side Bet City 的金额处理：实际扣款、返还均保留两位小数。"""
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

class InOutGame:
    """只负责目标牌、交替发牌和赔率判定，不依赖界面。"""

    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.target_card = None
        self.inner_cards = []
        self.outer_cards = []
        self.current_position = 0
        self.finished = False
        self.match_position = self.match_card = self.match_region = None
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence
        self.stage = 'betting'
        self.bets = dict.fromkeys(BET_TYPES, 0)
        self.results = {}

    def deal_target(self):
        if self.target_card is None:
            self.target_card = self.deck.deal(1)[0]
        return self.target_card

    @property
    def total_bet(self):
        return money(sum(self.bets.values()))

    @property
    def round_return(self):
        return money(sum(result['return'] for result in self.results.values()))

    @property
    def net_winnings(self):
        # 历史文件原 winnings 字段记录中奖项目的净赢，保持其含义。
        return money(sum(result['profit'] for result in self.results.values()))

    def begin_round(self, bets):
        if self.stage != 'betting':
            raise ValueError('本局尚未结束')
        checked = {}
        for kind in BET_TYPES:
            amount = float(bets.get(kind, 0))
            if not math.isfinite(amount) or amount < 0 or not amount.is_integer():
                raise ValueError('下注金额必须为非负整数')
            checked[kind] = int(amount)
        self.deal_target()
        self.bets = checked
        self.results = {}
        self.inner_cards = []
        self.outer_cards = []
        self.current_position = 0
        self.finished = False
        self.match_position = self.match_card = self.match_region = None
        self.stage = 'dealing'

    def deal_next(self):
        if self.finished or self.target_card is None:
            raise ValueError('本局没有可发出的下一张牌')
        if self.deck.pointer >= 52:
            raise ValueError('牌堆已用尽，未找到目标点数')
        card = self.deck.deal(1)[0]
        self.current_position += 1
        region = 'inner' if self.current_position % 2 else 'outer'
        (self.inner_cards if region == 'inner' else self.outer_cards).append(card)
        if card.rank == self.target_card.rank:
            self.match_position = self.current_position
            self.match_card = card
            self.match_region = region
            self.finished = True
        return card, region

    def start_round(self):
        """兼容原接口；按已锁定的牌序发到首张同点数牌。"""
        self.deal_target()
        while not self.finished:
            self.deal_next()
        return (self.inner_cards, self.outer_cards, self.match_position,
                self.match_region, self.match_card)

    def settle_round(self):
        if not self.finished:
            raise ValueError('尚未出现目标点数，不能结算')
        if self.results:
            return self.results
        hit_zone = (self.match_position - 1) // 5
        for kind in BET_TYPES:
            stake = self.bets[kind]
            if kind in ('inner', 'outer'):
                qualifies = kind == self.match_region
                odds = 0.9 if kind == 'inner' else 1.0
            else:
                index = int(kind.split('_')[1])
                qualifies = 1 <= self.match_position <= 49 and index == hit_zone
                odds = ZONE_ODDS[index]
            profit = money(stake * odds) if qualifies else 0.0
            self.results[kind] = dict(stake=stake, odds=odds, qualifies=qualifies,
                                      profit=profit,
                                      **{'return': money(stake + profit) if qualifies else 0.0})
        return self.results

    def finish_round(self):
        if self.stage == 'betting':
            return self.results
        self.start_round()
        return self.settle_round()

class InOutGUI(tk.Frame):
    """Side Bet City 的整桌 Canvas、筹码与交互，配合 In Or Out 玩法。"""

    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    CASHIER_POS = (575, 43)
    PLAYER = 'Player'
    TABLE_GREEN = '#2A5541'

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, money(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = InOutGame()
        self.bets = self._empty_bets()
        self.last_bet = self.last_game_bet = None
        self.last_win = self.round_return = 0.0
        self.high_bet_mode = False
        self.selected_chip = 10.0
        self.animation_in_progress = False
        self._game_instruction_dialog = self._sequence_window = None
        self._jobs = set()
        self._round_token = 0
        self._closing = self._crediting = False
        self._credited = self._return_persisted = False
        self._restart_job = self._restart_deadline = None
        self._motion_count = self._chip_serial = 0
        self.history_saved = False
        self.visual_chips = {}
        self.last_round_snapshot = None
        self._history_available = False
        self._collected_zones = set()
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self._faded_photos = {}
        self.card_items, self.bet_spots = {}, {}
        self.zone_caption_items = {}
        self.current_status = DEFAULT_BETTING_STATUS
        # 保留原下注变量接口，内部以开局快照结算，发牌中不修改下注。
        self.inner_bet_var = tk.StringVar(self, '0')
        self.outer_bet_var = tk.StringVar(self, '0')
        self.zone_bet_vars = [tk.StringVar(self, '0') for _ in range(10)]
        self._load_assets()
        self._create_widgets()
        self.deal_target_card()
        self._refresh()
        self.bind('<Configure>', self._center_table, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')

    @staticmethod
    def _empty_bets():
        return dict.fromkeys(BET_TYPES, 0)

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    @property
    def betting_enabled(self):
        return not self.game_in_progress and not self._closing

    def _schedule(self, delay, callback, *args):
        token = self._round_token
        job = None

        def run():
            self._jobs.discard(job)
            if not self._closing and token == self._round_token:
                callback(*args)

        job = self.after(delay, run)
        self._jobs.add(job)
        return job

    def _cancel_jobs(self):
        self._round_token += 1
        for job in tuple(self._jobs):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs.clear()
        self._restart_job = None

    def _on_destroy(self, event):
        if event.widget is self:
            self._closing = True
            self._cancel_jobs()
            self._unbind_enter()

    def _unbind_enter(self):
        binding = getattr(self, '_enter_binding', None)
        if binding:
            try:
                self.winfo_toplevel().unbind('<Return>', binding)
            except tk.TclError:
                pass
            self._enter_binding = None

    def _center_table(self, event=None):
        self.canvas.place(x=max(0, (self.winfo_width() - self.WIDTH) // 2),
                          y=max(0, (self.winfo_height() - self.HEIGHT) // 2),
                          width=self.WIDTH, height=self.HEIGHT)

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self.table_canvas = self.bet_canvas = self.canvas
        self.control_buttons = {}
        c = self.canvas
        self._text(187, 44, GAME_NAME, 16, GOLD)
        self._text(957, 44, 'In Or Out', 14, GOLD)
        self._text(575, 45, '单人玩法', 12, PANEL_BG)
        self._text(575, 95, 'IN OR OUT', 22, GOLD)
        self._text(575, 127, '内区 · 外区 · 位置区间', 13, PANEL_BG)
        self.street_item = self._text(575, 161, '下注阶段', 13, PANEL_BG, width=430)
        self._draw_limit_table()
        self._draw_analysis_panel()

        c.create_rectangle(22, 191, 1128, 434, fill=ROOT_BG, outline='#65784B')
        c.create_line(25, 192, 1125, 192, fill='#E0C879', width=2)
        c.create_line(25, 433, 1125, 433, fill='#0C241B', width=2)
        self._text(119, 212, '目标牌', 14, GOLD)
        c.create_rectangle(78, 231, 160, 347, outline='#B59C6A', dash=(3, 3))
        self.position_item = self._text(119, 377, '0', 28, PANEL_BG)
        self._text(119, 408, '当前第几张牌', 11, PANEL_BG)
        for region, title, y in (('inner', '内区\n奇数位置', 198),
                                 ('outer', '外区\n偶数位置', 316)):
            self._rounded_rectangle(257, y, 1117, y + 116, 10,
                                    fill='#234838', outline='#667B55', width=1)
            self._text(218, y + 58, title, 12, PANEL_BG)
            c.create_rectangle(270, y + 2, 350, y + 114,
                               outline='#B59C6A', dash=(3, 3))
        self._draw_bet_table()
        self._draw_bottom_controls()

    def _draw_limit_table(self):
        c, left, right, top = self.canvas, 30, 349, 75
        c.create_rectangle(left, top, right, 181, fill=ROOT_BG, outline=GOLD, width=2,
                           tags='limits')
        self._text((left + right) / 2, top + 14, '下注上限', 13, PANEL_BG, tags='limits')
        c.create_line(left, top + 29, right, top + 29, fill=GOLD, tags='limits')
        self.limit_value_items = []
        for col, title in enumerate(('内区 / 外区', '每项位置区间')):
            x0 = left + col * (right - left) / 2
            x1 = left + (col + 1) * (right - left) / 2
            c.create_rectangle(x0, top + 29, x1, top + 66, outline='#77906B', tags='limits')
            c.create_rectangle(x0, top + 66, x1, 181, outline='#77906B', tags='limits')
            self._text((x0 + x1) / 2, top + 47, title, 11, PANEL_BG, tags='limits')
            self.limit_value_items.append(self._text((x0 + x1) / 2, top + 86, '', 12,
                                                    GOLD, tags='limits'))
        c.tag_bind('limits', '<Button-1>', self.toggle_high_bet_limits)
        c.tag_bind('limits', '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind('limits', '<Leave>', lambda _e: c.configure(cursor=''))

    def _draw_analysis_panel(self):
        self.canvas.create_rectangle(796, 75, 1120, 181, fill=ROOT_BG, outline=GOLD, width=2)
        self.analysis_title_item = self._text(958, 92, '目标点数 · 历史内外区比例', 12, PANEL_BG)
        self.analysis_inner_item = self._text(990, 123, '', 12, '#84BFFC')
        self.analysis_outer_item = self._text(990, 149, '', 12, '#F1AB65')

    def _draw_bet_table(self):
        c = self.canvas
        c.create_rectangle(22, 440, 1128, 617, fill=self.TABLE_GREEN, outline='')
        self._text(172, 459, '玩家下注', 14, PANEL_BG)
        for kind, cx, caption in (('inner', 106, '内区  0.9:1'), ('outer', 240, '外区  1:1')):
            self._text(cx, 494, caption, 11, GOLD)
            tag = 'spot_' + self.PLAYER + '_' + kind
            border = c.create_oval(cx - 40, 507, cx + 40, 587,
                                   fill=self.TABLE_GREEN, outline=PANEL_BG, width=2, tags=tag)
            self._register_spot(self.PLAYER, kind, cx, 547, border, BET_NAMES[kind])
        c.create_line(327, 450, 327, 606, fill='#667B55')
        for index, (name, odds) in enumerate(zip(ZONE_NAMES, ZONE_ODDS_TEXT)):
            kind = f'zone_{index}'
            cx, cy = 413 + (index % 5) * 156, 496 + (index // 5) * 81
            tag = 'spot_' + self.PLAYER + '_' + kind
            self.zone_caption_items[kind] = self._text(cx, cy - 36, f'{name}  {odds}',
                                                      11, GOLD, tags=tag)
            border = c.create_oval(cx - 27, cy - 27, cx + 27, cy + 27,
                                   fill=self.TABLE_GREEN, outline=PANEL_BG, width=2, tags=tag)
            self._register_spot(self.PLAYER, kind, cx, cy, border, name)
            c.itemconfigure(self.bet_spots[(self.PLAYER, kind)]['label'], font=('Arial', 10, 'bold'))

    def card_position(self, side, index):
        if side == 'Target':
            return 79, 233
        return 270 + index * 31, 200 if side == 'inner' else 318

    def _status(self, message):
        self.current_status = message
        if hasattr(self, 'street_item'):
            self.canvas.itemconfigure(self.street_item, text=message)

    def _refresh(self):
        if self._closing:
            return
        c, stage = self.canvas, self.game.stage
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = money(sum(self.bets.values()))
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total
                        else f'上局返还: ${self.last_win:,.2f}')
        for item, kind in zip(self.limit_value_items, ('inner', 'zone_0')):
            c.itemconfigure(item, text=f'${self._bet_limits(kind)[1]:,}')
        self._render_chips()
        betting = stage == 'betting' and self._motion_count == 0
        restarting = stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, stage in ('await_restart', 'credit_pending'))
        caption = {'betting': '下注阶段', 'dealing': '派牌中', 'settling': '派彩中',
                   'await_restart': '已结算', 'returning': '筹码返回中',
                   'credit_pending': '重试保存余额', 'sweeping': '收牌中'}.get(stage, stage)
        if self.game.finished:
            caption += f' · 第 {self.game.match_position} 张 · {BET_NAMES[self.game.match_region]}'
        self._status(caption)
        for kind in BET_TYPES:
            spot = self.bet_spots[(self.PLAYER, kind)]
            result = self.game.results.get(kind)
            won = result is not None and result['qualifies']
            expired = kind in self._collected_zones
            active = (stage == 'dealing' and kind.startswith('zone_')
                      and int(kind.split('_')[1]) == (self.game.current_position - 1) // 5)
            color = GOLD if won else '#84BFFC' if active else '#6C806D' if expired else PANEL_BG
            c.itemconfigure(spot['border'], outline=color, width=3 if won or active else 2)
            c.itemconfigure(spot['label'], fill=color)
            if kind in self.zone_caption_items:
                c.itemconfigure(self.zone_caption_items[kind], fill=color)

    def _bet_limits(self, kind='inner'):
        minimum = 100 if self.high_bet_mode else 10
        maximum = 2500 if kind.startswith('zone_') else 10000
        return minimum, maximum * (5 if self.high_bet_mode else 1)

    def select_chip(self, amount):
        if isinstance(amount, str):
            value = amount.replace('$', '').replace(',', '').upper()
            amount = float(value.rstrip('K')) * (1000 if value.endswith('K') else 1)
        if self.betting_enabled:
            self.selected_chip = float(amount)
            self._draw_chips()

    def _bet_kind(self, seat, kind=None):
        if seat == 'zone' and isinstance(kind, int):
            return self.PLAYER, f'zone_{kind}'
        return (self.PLAYER, seat) if kind is None else (seat, kind)

    def add_chip_to_bet(self, seat, kind=None):
        seat, kind = self._bet_kind(seat, kind)
        if seat != self.PLAYER or kind not in self.bets or not self.betting_enabled:
            return
        new_bets = dict(self.bets)
        _, maximum = self._bet_limits(kind)
        if new_bets[kind] >= maximum:
            return
        new_bets[kind] = int(min(maximum, new_bets[kind] + self.selected_chip))
        self._apply_bet_layout(new_bets)

    def reset_single_bet(self, seat, kind=None, event=None):
        seat, kind = self._bet_kind(seat, kind)
        if seat != self.PLAYER or kind not in self.bets or not self.betting_enabled:
            return
        new_bets = dict(self.bets)
        new_bets[kind] = 0
        self._apply_bet_layout(new_bets)

    def reset_bets(self):
        if self.betting_enabled:
            self._apply_bet_layout(self._empty_bets())

    def apply_last_bet(self):
        if not self.betting_enabled or not self.last_bet:
            return
        restored = {}
        for kind, amount in self.last_bet.items():
            minimum, maximum = self._bet_limits(kind)
            restored[kind] = min(maximum, max(minimum, amount)) if amount else 0
        self._apply_bet_layout(restored)

    def repeat_last_bet(self):
        self.apply_last_bet()

    def toggle_high_bet_limits(self, event=None):
        if not self.betting_enabled:
            return
        if not self.high_bet_mode:
            password = simpledialog.askstring('高额下注', '请输入密码：', parent=self)
            if password is None:
                return
            if password.strip() != time.strftime('%H%M'):
                messagebox.showerror('错误', '密码错误', parent=self)
                return
        self.high_bet_mode = not self.high_bet_mode
        self.last_bet = self.last_game_bet = None
        self.selected_chip = 100 if self.high_bet_mode else 10
        self._draw_chips()
        self.reset_bets()
        self._refresh()

    def _sync_bet_vars(self):
        self.inner_bet_var.set(str(self.bets['inner']))
        self.outer_bet_var.set(str(self.bets['outer']))
        for index, variable in enumerate(self.zone_bet_vars):
            variable.set(str(self.bets[f'zone_{index}']))

    def update_bet_display(self):
        if not self.betting_enabled:
            return
        values = [self.inner_bet_var, self.outer_bet_var, *self.zone_bet_vars]
        self._apply_bet_layout({kind: float(value.get() or 0)
                               for kind, value in zip(BET_TYPES, values)})

    def _apply_bet_layout(self, new_bets):
        previous, self.bets = self.bets, dict(new_bets)
        self._sync_bet_vars()
        transfers = []
        for kind in BET_TYPES:
            old, new = previous[kind], self.bets[kind]
            delta = new - old
            if not delta:
                continue
            center = self.bet_spots[(self.PLAYER, kind)]['center']
            if delta > 0:
                transfers.append(dict(amount=delta, start=self._rack_position(), target=center,
                    arrive=lambda k=kind, a=new: self._set_visual(self.PLAYER, k, 'stake', a)))
            else:
                self._set_visual(self.PLAYER, kind, 'stake', new)
                transfers.append(dict(amount=-delta, start=center, target=self._rack_position(), duration=440))
        self._run_chip_batch(transfers, self._refresh)
        self._refresh()

    def _persist_balance(self):
        try:
            if self.username and self.username != 'Guest':
                update_balance_in_json(self.username, money(self.balance))
        except Exception as exc:
            messagebox.showerror('余额保存失败', str(exc), parent=self)
            return False
        if callable(self.on_balance_change):
            try:
                self.on_balance_change(float(self.balance))
            except Exception as exc:
                print(f'通知余额变更失败: {exc}')
        return True

    def update_balance(self):
        self.balance = money(self.balance)
        self._refresh()
        return self._persist_balance()

    def deal_target_card(self):
        card = self.game.deal_target()
        item = self.canvas.create_image(*self.card_position('Target', 0),
                                        image=self._face_photos[self._card_image_key(card)],
                                        anchor='nw', tags='cards')
        self.card_items[('Target', 0)] = item
        self.canvas.itemconfigure(self.position_item, text='0')
        self.update_analysis(card.rank)

    def update_analysis(self, rank):
        record = load_inout_stats().get('history_record', {}).get('chance_in_or_out', {})
        data = record.get(rank, {})
        self.canvas.itemconfigure(self.analysis_title_item,
                                  text=f'目标 {rank} · 历史内外区比例')
        self.draw_pie_chart(data.get('In', 0), data.get('Out', 0))

    def draw_pie_chart(self, inner_count, outer_count):
        c, total = self.canvas, inner_count + outer_count
        c.delete('analysis_pie')
        box = (811, 109, 874, 172)
        if total:
            for start, extent, color in ((0, 360 * inner_count / total, '#4A90D9'),
                                        (360 * inner_count / total, 360 * outer_count / total, '#E67E22')):
                if extent:
                    if extent >= 360:
                        c.create_oval(*box, fill=color, outline=PANEL_BG, tags='analysis_pie')
                    else:
                        c.create_arc(*box, start=start, extent=extent, fill=color,
                                     outline=PANEL_BG, tags='analysis_pie')
            inner = f'内区 {inner_count / total:.0%} · {inner_count} 次'
            outer = f'外区 {outer_count / total:.0%} · {outer_count} 次'
        else:
            c.create_oval(*box, fill='#667B55', outline=PANEL_BG, tags='analysis_pie')
            self._text(842, 140, '无数据', 9, PANEL_BG, tags='analysis_pie')
            inner, outer = '内区 — · 0 次', '外区 — · 0 次'
        c.itemconfigure(self.analysis_inner_item, text=inner)
        c.itemconfigure(self.analysis_outer_item, text=outer)

    def start_game(self):
        if not self.betting_enabled:
            return
        try:
            # 兼容调用方直接设置原 StringVar 的用法。
            variables = (self.inner_bet_var, self.outer_bet_var, *self.zone_bet_vars)
            bets = {kind: float(variable.get() or 0)
                    for kind, variable in zip(BET_TYPES, variables)}
            for kind, amount in bets.items():
                minimum, maximum = self._bet_limits(kind)
                if (not math.isfinite(amount) or amount < 0 or not amount.is_integer()
                        or (amount and not minimum <= amount <= maximum)):
                    raise ValueError(f'{BET_NAMES[kind]}下注范围为 ${minimum:,}–${maximum:,}，也可不下注')
            total = money(sum(bets.values()))
            if total > self.balance:
                raise ValueError('余额不足以支付所有下注')
            self.game.begin_round(bets)
        except (ValueError, OverflowError) as exc:
            messagebox.showwarning('无法开始游戏', str(exc), parent=self)
            return
        before = self.balance
        self.balance = money(before - total)
        if not self._persist_balance():
            self.balance = before
            self.game.stage = 'betting'
            self.game.bets = self._empty_bets()
            self._refresh()
            return
        self._cancel_jobs()
        self._cancel_restart_timer()
        self._close_card_sequence()
        self.bets = dict(self.game.bets)
        self._sync_bet_vars()
        # 外部直接设置 StringVar 开局时也要同步桌面本金筹码。
        self.visual_chips.clear()
        for kind, amount in self.bets.items():
            self._set_visual(self.PLAYER, kind, 'stake', amount)
        self.last_bet = dict(self.bets)
        self.last_game_bet = dict(inner=self.bets['inner'], outer=self.bets['outer'],
                                  zone=[self.bets[f'zone_{i}'] for i in range(10)])
        self._credited = self._return_persisted = False
        self._history_available = self.history_saved = False
        self.last_round_snapshot = None
        self.round_return = 0.0
        self._collected_zones.clear()
        self.animation_in_progress = True
        self._refresh()
        self._schedule(0, self._deal_next_card)

    def _deal_next_card(self):
        if self.game.stage != 'dealing' or self.game.finished:
            return
        card, region = self.game.deal_next()
        index = len(self.game.inner_cards if region == 'inner' else self.game.outer_cards) - 1
        self.canvas.itemconfigure(self.position_item, text=str(self.game.current_position))
        x, y = self.card_position(region, index)
        item = self.canvas.create_image(575, 52, image=self._face_photos['back'],
                                        anchor='nw', tags=('cards', 'played_cards'))
        self.card_items[(region, index)] = item

        def move(step=0):
            fraction = step / 6
            self.canvas.coords(item, 575 + (x - 575) * fraction, 52 + (y - 52) * fraction)
            if step < 6:
                delay = round(self.DEAL_MOVE_MS * (step + 1) / 6) - round(self.DEAL_MOVE_MS * step / 6)
                self._schedule(delay, move, step + 1)
            else:
                self._flip_card(item, card, x, y, self._after_card_animation)

        self.update_zone_bets_by_position(self.game.current_position)
        move()

    def _flip_card(self, item, card, x, y, complete):
        w, h = self.card_size('Cards')

        def flip(step=0):
            width = max(1, round(w * abs(1 - step / 5)))
            key = 'back' if step < 5 else self._card_image_key(card)
            source = self._pil_cards[key]
            photo = ImageTk.PhotoImage(source.resize((width, h), Image.Resampling.LANCZOS), master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item, image=photo)
            self.canvas.coords(item, x + (w - width) / 2, y)
            if step < 10:
                self._schedule(32, flip, step + 1)
            else:
                self.canvas.itemconfigure(item, image=self._face_photos[self._card_image_key(card)])
                self._flip_photos.pop(item, None)
                complete()

        flip()

    def _after_card_animation(self):
        if self.game.finished:
            item = self.card_items[(self.game.match_region,
                len(self.game.inner_cards if self.game.match_region == 'inner' else self.game.outer_cards) - 1)]
            x, y = self.canvas.coords(item)
            self.canvas.create_rectangle(x - 2, y - 2, x + self.CARD_WIDTH + 2,
                                          y + self.CARD_HEIGHT + 2, outline=GOLD,
                                          width=3, tags='cards')
            self._schedule(800, self._settle_complete)
        else:
            self._schedule(300, self._deal_next_card)
        self._refresh()

    def update_zone_bets_by_position(self, current_pos):
        current_idx = min(10, (current_pos - 1) // 5)
        transfers = []
        for index in range(current_idx):
            kind = f'zone_{index}'
            if kind not in self._collected_zones:
                self._collected_zones.add(kind)
                transfers.extend(self._outcome_transfers(self.PLAYER, kind, self.game.bets[kind], 0))
        if transfers:
            self._run_chip_batch(transfers, self._refresh)
        self._refresh()

    def _persist_round(self):
        if self.history_saved:
            return []
        try:
            add_inout_history(self.game.deck, self.game.target_card, self.game.match_position,
                              self.game.match_card, self.game.net_winnings)
            self.history_saved = True
            return []
        except Exception as exc:
            print(f'历史保存失败: {exc}')
            return ['历史保存失败']

    def _settle_complete(self):
        if self.game.stage != 'dealing':
            return
        self.game.settle_round()
        self.game.stage = 'settling'
        self.last_win = self.round_return = self.game.round_return
        transfers = []
        for kind, result in self.game.results.items():
            if kind not in self._collected_zones:
                transfers.extend(self._outcome_transfers(self.PLAYER, kind,
                                                         result['stake'], result['return']))
        errors = self._persist_round()
        if errors:
            messagebox.showwarning('保存提示', '牌局已结算；' + '、'.join(errors), parent=self)
        self.update_analysis(self.game.target_card.rank)
        self._refresh()
        self._run_chip_batch(transfers, self._await_next_round)

    def settle(self, inner_bet, outer_bet, zone_bets, match_pos, region, match_card):
        """保留旧结算入口；正常流程使用锁定的开局下注与牌序。"""
        if self.game.stage == 'dealing' and self.game.finished:
            self._settle_complete()

    def _await_next_round(self):
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        self.animation_in_progress = False
        deck = self.game.deck
        self.last_round_snapshot = dict(full_deck=tuple(deck.full_deck), start_pos=deck.start_pos,
            match_position=self.game.match_position,
            images={key: image.copy() for key, image in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        self._restart_deadline = time.monotonic() + 30
        self._refresh()
        self._restart_tick()

    def _inspect_completed_round(self, event=None):
        if self.game.stage != 'await_restart':
            return
        self._cancel_restart_timer()
        self.show_card_sequence()

    def _return_all_chips(self):
        if self.game.stage == 'credit_pending':
            self._complete_chip_return()
            return
        if self.game.stage != 'await_restart':
            return
        self._cancel_restart_timer()
        self._history_available = False
        self._close_card_sequence()
        self.game.stage = 'returning'
        chips = list(self.visual_chips.values())
        self.visual_chips.clear()
        transfers = []
        for index, chip in enumerate(chips):
            target = self._rack_position(index, len(chips))

            def arrived(chip=chip, target=target, index=index):
                self._draw_chip(f'returned_chip_{index}', chip['amount'], *target,
                                chip.get('rectangular', False), extra_tags=('returned_chips',))

            transfers.append(dict(amount=chip['amount'], start=chip['xy'], target=target,
                                  duration=600, arrive=arrived))
        self._refresh()
        self._run_chip_batch(transfers, self._complete_chip_return)

    def _credit_round_return(self):
        if self._crediting:
            return False
        if self._return_persisted:
            return True
        self._crediting = True
        try:
            if not self._credited:
                self.balance = money(self.balance + self.last_win)
                self._credited = True
            self._return_persisted = self._persist_balance()
            return self._return_persisted
        finally:
            self._crediting = False

    def _complete_chip_return(self):
        if self.game.stage not in ('returning', 'credit_pending'):
            return
        self.game.stage = 'credit_pending'
        if not self._credit_round_return():
            self._refresh()
            return
        self._persist_round()
        self.game.stage = 'sweeping'
        self._refresh()
        self.canvas.delete('returned_chips')
        self._sweep_all_cards()

    def _sweep_all_cards(self):
        if not self.card_items:
            self._finish_round()
            return
        self._motion_count += 1
        previous = [0.0]
        distance = self.WIDTH + self.CARD_WIDTH

        def frame(index=0):
            fraction = index / 13
            offset = distance * fraction * fraction * (3 - 2 * fraction)
            self.canvas.move('cards', offset - previous[0], 0)
            previous[0] = offset
            if index < 13:
                self._schedule(round(200 * (index + 1) / 13) - round(200 * index / 13), frame, index + 1)
            else:
                self.canvas.delete('cards')
                self.card_items.clear()
                self._flip_photos.clear()
                self._motion_count -= 1
                self._finish_round()

        frame()

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        self.game.reset_game()
        self.bets = self._empty_bets()
        self._sync_bet_vars()
        self.visual_chips.clear()
        self._collected_zones.clear()
        self._faded_photos.clear()
        self.animation_in_progress = self._history_available = False
        self._load_assets()
        self.deal_target_card()
        self._refresh()

    def reset_game(self, auto_reset=False):
        if self.game.stage in ('await_restart', 'credit_pending'):
            self._return_all_chips()
        elif self.betting_enabled:
            self.reset_bets()

    def _settle_before_close(self):
        if self.game.stage == 'betting':
            return self._persist_balance()
        self._cancel_restart_timer()
        self._cancel_jobs()
        self._motion_count = 0
        self.animation_in_progress = False
        self.canvas.delete('moving_chips')
        # 本局牌序已锁定，无后续下注决策；沿相同牌序找到首张匹配牌。
        self.game.finish_round()
        self.last_win = self.round_return = self.game.round_return
        self.game.stage = 'credit_pending'
        self._persist_round()
        if not self._credit_round_return():
            self._refresh()
            return False
        return True

    def on_close(self):
        if self._closing or self._crediting:
            return
        if not self._settle_before_close():
            return
        self._closing = True
        self._cancel_jobs()
        self._unbind_enter()
        self._close_card_sequence()
        self._close_instructions()
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.winfo_toplevel().destroy()

    def destroy(self):
        if not self._closing:
            if not self._settle_before_close():
                return
            self._closing = True
        self._cancel_jobs()
        self._unbind_enter()
        self._close_card_sequence()
        self._close_instructions()
        super().destroy()

    def show_card_sequence(self, event=None):
        if self.game.stage != 'await_restart' or not self._history_available:
            return
        self._cancel_restart_timer()
        snapshot = self.last_round_snapshot
        if not snapshot:
            return
        current = self._sequence_window
        if current is not None and current.winfo_exists():
            current.lift()
            return
        win = tk.Toplevel(self)
        self._sequence_window = win
        win.title('上局牌序')
        win.geometry('730x750')
        win.resizable(False, False)
        win.configure(bg='#f0f0f0')
        cut_pos = snapshot['start_pos']
        tk.Label(win, text=f'上局切牌位置: {cut_pos + 1}  ·  匹配第 {snapshot["match_position"]} 张',
                 font=('Arial', 14, 'bold'), bg='#f0f0f0').pack(pady=10)
        tk.Label(win, text='浅蓝：目标牌 / 切牌位置    绿色：内区    橙色：外区    金色：匹配牌',
                 font=('Arial', 10), bg='#f0f0f0').pack()
        main = tk.Frame(win, bg='#f0f0f0')
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(main)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content = tk.Frame(canvas, bg='#f0f0f0')
        canvas.create_window((0, 0), window=content, anchor='nw')
        win._card_images = {}
        for index, card in enumerate(snapshot['full_deck']):
            key = self._card_image_key(card)
            original = snapshot['images'].get(key, snapshot['images']['back'])
            photo = ImageTk.PhotoImage(original.resize((60, 90), Image.Resampling.LANCZOS), master=win)
            win._card_images[index] = photo
            dealt_index = (index - cut_pos) % 52
            color = '#f0f0f0'
            if dealt_index == 0:
                color = 'light blue'
            elif dealt_index == snapshot['match_position']:
                color = GOLD
            elif dealt_index < snapshot['match_position']:
                color = 'light green' if dealt_index % 2 else '#ffd0a3'
            container = tk.Frame(content, bg=color)
            container.grid(row=index // 9, column=index % 9, padx=5, pady=5)
            tk.Label(container, image=photo, bg=color, borderwidth=1, relief='solid').pack()
            tk.Label(container, text=str(index + 1), bg=color, font=('Arial', 9)).pack()
        content.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox('all'))

    def _instruction_pages(self):
        return [
            ('玩法', '先显示目标牌，交替发牌至首张同点数牌。', [
                ('游戏目标', '', [
                    ('一副标准牌', '每局使用不含大小王的52张牌，先发一张目标牌。'),
                    ('匹配规则', '只比较点数，不比较花色。首张同点数牌出现时结束本局。'),
                    ('交替发牌', '目标牌不计入位置编号。其后第1、3、5等奇数位置属于内区；第2、4、6等偶数位置属于外区。'),
                    ('观看', '可以选择多项下注，也可以全部不下注，仅观看。')], []),
                ('牌桌显示', '', [
                    ('牌的位置', '目标牌在左侧，内区牌在上排，外区牌在下排。数字显示当前发到第几张。命中的牌与区域用金色标记。'),
                    ('历史比例', '右上方统计当前目标点数过去命中内外区的次数和比例。这是历史记录，不是下一局概率。')], [])]),
            ('下注 & 限红', '筹码、重复下注和高额模式沿用 Side Bet City 的交互。', [
                ('下注操作', '', [
                    ('设置金额', '先选下方筹码，再左键点击下注圈增加金额；右键清除该项。金额超过上限时自动调整至上限。'),
                    ('开局与锁定', '点击“开牌”或按Enter，所有下注一次扣除；发牌后不能修改金额。'),
                    ('重复下注', '“重复下注”恢复上一局开局时的金额。即使区间筹码中途被收走，也不会影响上局金额快照。'),
                    ('高额模式', '点击左上下注上限表，按原 Side Bet City 密码方式切换高额模式；切换时清空当前及上局下注。')], [
                        ('每项下注范围', ['项目', '普通模式', '高额模式'], [
                            ['内区 / 外区', '$10–$10,000', '$100–$50,000'],
                            ['每项位置区间', '$10–$2,500', '$100–$12,500']])])]),
            ('获胜条件 & 赔率', '赔率为净赢赔率；中奖返还包含对应本金。', [
                ('区域与位置区间', '', [], [
                    ('In Or Out 赔率', ['下注项目', '获胜条件', '净赢赔率'], [
                        ['内区', '首次匹配出现在奇数位置', '0.9:1'],
                        ['外区', '首次匹配出现在偶数位置', '1:1'],
                        *[[name, f'首次匹配位于 {name}', odds]
                          for name, odds in zip(ZONE_NAMES, ZONE_ODDS_TEXT)]])]),
                ('返还计算', '', [
                    ('中奖项目', '返还＝该项本金×（1＋赔率）。未中奖项目不返还。内外区下注与区间下注分别计算，可同时中奖。'),
                    ('例子', '内区下注$100，命中内区时返还$190。1–5区间下注$100，命中该区间时返还$350。若两项同时命中，总返还$540。'),
                    ('净盈亏', '整局净盈亏＝所有项目返还总额－本局总下注。')], [])]),
            ('判定与牌例', '相同点数即可命中，花色不影响结果。', [
                ('目标与匹配牌', '', [], [
                    ('同点数示例', ['判定', '牌例'], [
                        ['同点数，命中', ('__CARD_IMAGES__', (('♠', '9'), ('♥', '9')))],
                        ['不同点数，不命中', ('__CARD_IMAGES__', (('♠', '9'), ('♥', '10')))]])])]),
            ('特别事项', '返还、自动重置与牌序查看。', [
                ('结算显示', '', [
                    ('筹码动画', '中奖本金留在原位，净赢筹码派至旁边；未中奖筹码飞向结算点。区间已过且未命中时，其筹码会提前收走。'),
                    ('再次开局', '结算后倒计时30秒；点击“再来一局”、按Enter或等待倒计时，筹码回到筹码区后完整返还一次计入余额，再收牌并发新目标牌。'),
                    ('查看牌序', '结算后右键点击“再来一局”可查看上局52张牌的原始牌序和切牌位置，同时暂停倒计时。'),
                    ('中途关闭', '沿本局已锁定牌序完成匹配与结算，保存余额；重复关闭或重试保存不会重复返还。')], []),
                ('历史记录', '', [
                    ('兼容原文件', '继续保存到 In_Or_Out.json，保留最近50局的牌序记录，以及累计内外区、命中位置和点数统计。')], [])])
        ]

    def _outcome_transfers(self, seat, kind, stake, returned):
        """沿用本金留位、净赢派彩；紧凑区间圈的盈利放在左侧。"""
        if not stake:
            return []
        key = (seat, kind, 'stake')
        center = self.bet_spots[(seat, kind)]['center']
        if returned <= 0:
            chip = self.visual_chips.pop(key, None)
            return [dict(amount=chip['amount'], start=chip['xy'], target=self.CASHIER_POS,
                         duration=280)] if chip else []
        profit = money(returned - stake)
        if profit <= 0:
            return []
        target = ((center[0] - 41, center[1] - 5) if kind.startswith('zone_')
                  else (center[0] - 32, center[1] - 30))
        return [dict(amount=profit, start=self.CASHIER_POS, target=target, duration=440,
                     arrive=lambda: self._set_visual(seat, kind, 'profit', profit, target))]

    def _close_instructions(self):
        dialog = self._game_instruction_dialog
        self._game_instruction_dialog = None
        if dialog is not None:
            try:
                if dialog.winfo_exists():
                    dialog.destroy()
            except tk.TclError:
                pass

    def _load_assets(self):
        size = (self.CARD_WIDTH, self.CARD_HEIGHT)
        self.current_poker_folder = ('Poker2' if self.current_poker_folder=='Poker1' else 'Poker1') if hasattr(self,'current_poker_folder') else random.choice(['Poker1','Poker2'])
        folder = self.current_poker_folder
        self.original_images = {}
        base = os.path.join(_PROJECT_ROOT, 'A_Tools', 'Card', folder)
        suits = {'♠':'Spade', '♥':'Heart', '♦':'Diamond', '♣':'Club'}
        try:
            font = ImageFont.truetype('DejaVuSans-Bold.ttf', 23)
        except OSError:
            font = ImageFont.load_default()
        for key in ['back'] + [(s, r) for s in SUITS for r in RANKS]:
            filename = 'Background.png' if key == 'back' else f'{suits[key[0]]}{key[1]}.png'
            try:
                with Image.open(os.path.join(base, filename)) as source:
                    original = source.convert('RGBA')  # 保留 PNG 的 alpha，禁止转 RGB/铺白底。
                    self.original_images[key] = original.copy()
                    im = original.resize(size, Image.Resampling.LANCZOS)
            except (OSError, ValueError):
                im = Image.new('RGBA', size, (0,0,0,0))
                draw = ImageDraw.Draw(im)
                draw.rounded_rectangle((1,1,size[0]-2,size[1]-2), radius=6,
                    fill=DARK_BLUE if key=='back' else '#fffaf0',outline=GOLD,width=2)
                if key == 'back':
                    for y in range(12, 104, 12):
                        draw.line((10,y,70,y), fill=GOLD)
                else:
                    suit, rank = key
                    text = rank + suit
                    try:
                        draw.text((7,10), text, font=font, fill=RED if suit in '♥♦' else BLACK)
                        draw.text((14,62), suit, font=font, fill=RED if suit in '♥♦' else BLACK)
                    except UnicodeEncodeError:
                        draw.text((7,10), rank+suits[suit][0], font=font, fill=BLACK)
            self.original_images.setdefault(key,im.copy())
            self._pil_cards[key] = im
            self._face_photos[key] = ImageTk.PhotoImage(im, master=self)
        self._public_photos = {key:ImageTk.PhotoImage(im.resize(self.card_size('Public'),Image.Resampling.LANCZOS),master=self) for key,im in self._pil_cards.items()}

    def _text(self, x, y, text, size=12, color=TEXT, **kw):
        return self.canvas.create_text(x, y, text=text, fill=color, font=('Arial', size, 'bold'), **kw)

    def _draw_chips(self):
        self.canvas.delete('rack')
        specs=([(100,BLACK),(500,'#FF7DDA'),(1000,TEXT),(5000,RED),(10000,'#00fbff'),(50000,'#00ffae')]
               if self.high_bet_mode else [(10,'#ffa500'),(25,'#00ff00'),(100,BLACK),(500,'#FF7DDA'),(1000,TEXT),(2500,RED)])
        self.chip_specs=specs
        diameter,gap=56,8
        start=(self.WIDTH-(len(specs)*diameter+(len(specs)-1)*gap))/2
        for i,(amount,color) in enumerate(specs):
            x=start+i*(diameter+gap)
            tag='rack_'+str(i)
            self.canvas.create_oval(x,646,x+56,702,fill='#182F25',
                outline=GOLD if amount==self.selected_chip else '#6C7850',width=3,tags=('rack',tag))
            self.canvas.create_oval(x+5,651,x+51,697,fill=color,outline=PANEL_BG,width=2,tags=('rack',tag))
            self._text(x+28,674,self._compact(amount),10,TEXT if color in (BLACK,RED) else BLACK,tags=('rack',tag))
            self.canvas.tag_bind(tag,'<Button-1>',lambda _e,a=amount:self.select_chip(a))

    @staticmethod
    def _compact(amount):
        """K/M筹码取两位有效数字并截断；有省略才加+，不改动真实金额。"""
        from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
        value=Decimal(str(amount)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        if value==Decimal('2.50'):return '2.50'
        if abs(value)>=1000000:
            divisor,suffix=Decimal(1000000),'M'
        elif abs(value)>=1000:
            divisor,suffix=Decimal(1000),'K'
        else:
            label=format(value,'f')
            return label.rstrip('0').rstrip('.') if '.' in label else label
        scaled=value/divisor
        precision=Decimal(1).scaleb(abs(scaled).adjusted()-1)
        shown=scaled.quantize(precision,rounding=ROUND_DOWN)
        label=format(shown,'f')
        if '.' in label:label=label.rstrip('0').rstrip('.')
        return label+suffix+('+' if shown!=scaled else '')

    def _register_spot(self, seat, kind, cx, cy, border, label, angle=0):
        c,tag = self.canvas,'spot_'+seat+'_'+kind
        label_item = self._text(cx,cy,label,14,PANEL_BG,angle=angle,tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border,label=label_item)
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,k=kind:self.add_chip_to_bet(s,k))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat,k=kind:self.reset_single_bet(s,k))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))

    def _rounded_rectangle(self, x0, y0, x1, y1, radius, **options):
        return self.canvas.create_polygon(
            x0+radius, y0, x1-radius, y0, x1, y0, x1, y0+radius,
            x1, y1-radius, x1, y1, x1-radius, y1, x0+radius, y1,
            x0, y1, x0, y1-radius, x0, y0+radius, x0, y0,
            smooth=True, splinesteps=24, **options)

    def _draw_bottom_controls(self):
        c=self.canvas
        c.create_rectangle(0,625,1150,748,fill=ROOT_BG,outline='#6C7850',width=2,tags='controls')
        self.balance_item=self._text(10,665,'',18,TEXT,anchor='w',tags='controls')
        self.total_item=self._text(10,710,'',18,TEXT,anchor='w',tags='controls')
        self.clear_button=self.create_control_button(278,650,344,704,'清除',self.reset_bets,'#9B403A',font_size=11,draw_shadow=False)
        self._draw_chips()
        self.info_button=self.create_control_button(810,650,855,695,'?',self.show_game_instructions,DARK_BLUE,font_size=17,draw_shadow=False)
        self.repeat_button=self.create_control_button(862,638,1000,708,'重复下注',self.apply_last_bet,'#536A43',font_size=11,draw_shadow=False)
        self.start_button=self.create_control_button(1012,628,1138,720,'开牌',self.start_game,HEADER_BG,
            fg=TITLE_FG,font_size=14,subtext='Enter',subtext_font_size=10,draw_shadow=False)
        self.restart_button=self.create_control_button(862,638,1138,708,'再来一局(30)',self._return_all_chips,
            HEADER_BG,fg=TITLE_FG,font_size=17,draw_shadow=False)
        c.tag_bind(self.restart_button,'<Button-3>',self._inspect_completed_round)
        c.itemconfigure(self.restart_button,state='hidden')
        # 筹码区下方不放文字，也没有返回按钮。
        self._enter_binding=self.winfo_toplevel().bind('<Return>',lambda _e:
            self._return_all_chips() if self.game.stage in ('await_restart','credit_pending') else self.start_game(),add='+')

    @staticmethod
    def shade_color(color, factor):
        color = color.lstrip('#')
        if len(color) != 6:
            return '#555555'
        values = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
        values = [max(0, min(255, int(value * factor))) for value in values]
        return '#' + ''.join(f'{value:02x}' for value in values)

    def create_control_button(self, x0, y0, x1, y1, text, command, fill,
                              fg='white', font_size=11, subtext=None,
                              subtext_font_size=10, draw_shadow=True):
        tag = f'control_button_{len(self.control_buttons)}'
        shadow = self.canvas.create_rectangle(x0 + 5, y0 + 6, x1 + 5, y1 + 6,
                                              fill='#070605', outline='#070605',
                                              width=1, tags=(tag, 'controls')) if draw_shadow else None
        rim = self.canvas.create_rectangle(x0, y0, x1, y1,
                                           fill=self.shade_color(fill, 0.55),
                                           outline='#b7a58d', width=2,
                                           tags=(tag, 'controls'))
        face = self.canvas.create_rectangle(x0 + 4, y0 + 4, x1 - 4, y1 - 4,
                                            fill=fill,
                                            outline=self.shade_color(fill, 1.25),
                                            width=2, tags=(tag, 'controls'))
        highlight = self.canvas.create_line(x0 + 8, y0 + 8, x1 - 8, y0 + 8,
                                            fill=self.shade_color(fill, 1.45), width=2,
                                            tags=(tag, 'controls'))
        center_y = (y0 + y1) / 2 - 1
        text_y = center_y - 12 if subtext else center_y
        text_id = self.canvas.create_text((x0 + x1) / 2, text_y, text=text,
                                          font=('Arial', font_size, 'bold'), fill=fg,
                                          tags=(tag, 'controls'))
        subtext_id = None
        subtext_center_y = None
        if subtext:
            subtext_center_y = center_y + 16
            subtext_id = self.canvas.create_text((x0 + x1) / 2, subtext_center_y,
                                                 text=subtext,
                                                 font=('Arial', subtext_font_size, 'bold'),
                                                 fill=fg, tags=(tag, 'controls'))
        self.control_buttons[tag] = {
            'shadow': shadow, 'rim': rim, 'face': face, 'highlight': highlight,
            'text': text_id, 'subtext': subtext_id, 'command': command,
            'fill': fill, 'fg': fg, 'enabled': True, 'pressed': False,
            'center_y': text_y, 'subtext_center_y': subtext_center_y,
        }

        def enter(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfigure(button['face'], fill=self.shade_color(button['fill'], 1.12))

        def leave(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfigure(button['face'], fill=button['fill'])

        def press(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled']:
                return
            button['pressed'] = True
            self.canvas.itemconfigure(button['face'], fill=self.shade_color(button['fill'], 0.72))
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 0.8))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'] + 2)
            if button.get('subtext'):
                sx, _sy = self.canvas.coords(button['subtext'])
                self.canvas.coords(button['subtext'], sx, button['subtext_center_y'] + 2)

        def release(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled'] or not button['pressed']:
                return
            button['pressed'] = False
            self.canvas.itemconfigure(button['face'], fill=button['fill'])
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'])
            if button.get('subtext'):
                sx, _sy = self.canvas.coords(button['subtext'])
                self.canvas.coords(button['subtext'], sx, button['subtext_center_y'])
            button['command']()

        self.canvas.tag_bind(tag, '<Enter>', enter)
        self.canvas.tag_bind(tag, '<Leave>', leave)
        self.canvas.tag_bind(tag, '<ButtonPress-1>', press)
        self.canvas.tag_bind(tag, '<ButtonRelease-1>', release)
        return tag

    def set_control_button_state(self, tag, enabled):
        button = self.control_buttons.get(tag)
        if not button:
            return
        button['enabled'] = bool(enabled)
        button['pressed'] = False
        x, _y = self.canvas.coords(button['text'])
        self.canvas.coords(button['text'], x, button['center_y'])
        if button.get('subtext'):
            sx, _sy = self.canvas.coords(button['subtext'])
            self.canvas.coords(button['subtext'], sx, button['subtext_center_y'])
        if enabled:
            self.canvas.itemconfigure(button['face'], fill=button['fill'])
            self.canvas.itemconfigure(button['rim'], fill=self.shade_color(button['fill'], 0.55))
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            self.canvas.itemconfigure(button['text'], fill=button['fg'])
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill=button['fg'])
        else:
            self.canvas.itemconfigure(button['face'], fill='#4a4743')
            self.canvas.itemconfigure(button['rim'], fill='#262422')
            self.canvas.itemconfigure(button['highlight'], fill='#66615b')
            self.canvas.itemconfigure(button['text'], fill='#9b9690')
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill='#9b9690')

    def _chip_color(self, amount):
        return next((col for value,col in reversed(self.chip_specs) if amount>=value),HEADER_BG)

    @staticmethod
    def _amount_label(amount):
        value=round(float(amount),2)
        if abs(value)>=1000:return InOutGUI._compact(value)
        return f'{value:.0f}' if value.is_integer() else f'{value:.2f}'

    def _draw_chip(self, tag, amount, x, y, rectangular=False, extra_tags=(), show_amount=True):
        c=self.canvas;tags=(tag,*extra_tags)
        if rectangular:
            # 大奖筹码只显示中奖数字，不带货币符号；整数省略 .00。
            label=self._amount_label(amount);width=max(96,10*len(label)+16)
            c.create_rectangle(x-width/2,y-18,x+width/2,y+18,fill='#731D2A',outline='#000000',width=1,tags=tags)
            if show_amount:self._text(x,y,label,11,'#FFF0C3',tags=tags)
        else:
            radius=self.BET_CHIP_RADIUS;color=self._chip_color(amount)
            c.create_oval(x-radius,y-radius,x+radius,y+radius,fill=color,outline='#000000',width=1,tags=tags)
            label=self._compact(amount)
            self._text(x,y,label,10 if len(label)>=5 else 12,TEXT if color in (BLACK,RED) else BLACK,tags=tags)

    def _render_chips(self):
        self.canvas.delete('bet_chips')
        # 本金先画、盈利后画；盈利位于原筹码左上方。
        for key,chip in sorted(self.visual_chips.items(),key=lambda kv:kv[0][2]!='stake'):
            seat,kind,role=key
            if chip['amount']>0:
                self._draw_chip('chip_'+seat+'_'+kind+'_'+role,chip['amount'],*chip['xy'],
                    rectangular=chip.get('rectangular',False),
                    extra_tags=('bet_chips',self.bet_spots[(seat,kind)]['tag']))

    def _rack_position(self, index=None, total=1):
        if index is not None:
            return 575+(index-(total-1)/2)*min(28,140/max(1,total-1)),674
        index=next((i for i,(value,_) in enumerate(self.chip_specs) if value==self.selected_chip),None)
        if index is None:return (575,674)
        width=len(self.chip_specs)*56+(len(self.chip_specs)-1)*8
        return (self.WIDTH-width)/2+index*64+28,674

    def _animate_chip(self, amount, start, target, complete=None, rectangular=False, duration=220):
        if not amount:
            if complete:complete()
            return
        self._motion_count+=1;self._chip_serial+=1
        tag=f'moving_chip_{self._chip_serial}'
        self._draw_chip(tag,amount,*start,rectangular,extra_tags=('moving_chips',))
        self._refresh()
        steps=max(1,round(duration/16));last=list(start)
        def frame(index):
            fraction=index/steps;eased=fraction*fraction*(3-2*fraction)
            x=start[0]+(target[0]-start[0])*eased
            y=start[1]+(target[1]-start[1])*eased
            self.canvas.move(tag,x-last[0],y-last[1]);last[:]=[x,y]
            self.canvas.tag_raise(tag)
            if index<steps:self._schedule(round(duration*(index+1)/steps)-round(duration*index/steps),frame,index+1)
            else:
                self.canvas.delete(tag);self._motion_count-=1
                if complete:complete()
                self._refresh()
        self._schedule(round(duration/steps),frame,1)

    def _run_chip_batch(self, transfers, complete):
        if not transfers:
            complete();return
        pending=[len(transfers)]
        def arrived(transfer):
            if transfer.get('arrive'):transfer['arrive']()
            pending[0]-=1
            if not pending[0]:complete()
        for transfer in transfers:
            self._animate_chip(transfer['amount'],transfer['start'],transfer['target'],
                lambda t=transfer:arrived(t),transfer.get('rectangular',False),transfer.get('duration',220))

    def _set_visual(self, seat, kind, role, amount, xy=None, rectangular=False):
        key=(seat,kind,role)
        if amount:
            self.visual_chips[key]=dict(amount=float(amount),xy=xy or self.bet_spots[(seat,kind)]['center'],rectangular=rectangular)
        else:self.visual_chips.pop(key,None)

    def _cancel_restart_timer(self):
        if self._restart_job is not None:
            try:self.after_cancel(self._restart_job)
            except tk.TclError:pass
            self._jobs.discard(self._restart_job)
            self._restart_job=None
        self._restart_deadline=None
        if hasattr(self,'restart_button'):
            self._restart_caption('再来一局')

    def _restart_caption(self, text):
        self.canvas.itemconfigure(self.control_buttons[self.restart_button]['text'],text=text)

    def _restart_tick(self):
        self._restart_job=None
        if self.game.stage!='await_restart' or self._restart_deadline is None:return
        remaining=max(0,self._restart_deadline-time.monotonic())
        self._restart_caption(f'再来一局({math.ceil(remaining)})')
        if remaining<=0:
            self._return_all_chips()
            return
        self._restart_job=self._schedule(max(1,min(1000,math.ceil(remaining*1000))),self._restart_tick)

    def _close_card_sequence(self):
        current=getattr(self,'_sequence_window',None)
        if current is not None:
            try:
                if current.winfo_exists():current.destroy()
            except tk.TclError:pass
        self._sequence_window=None

    def card_size(self, side):
        return self.CARD_WIDTH,self.CARD_HEIGHT

    @staticmethod
    def _card_image_key(card):
        return card.suit, card.rank

    def _fade_card_item(self, item, source):
        # 用alpha淡化，不破坏牌面原图，也不把透明PNG的边缘铺成白底。
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value:round(value*.45)))
        photo = ImageTk.PhotoImage(faded,master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item,image=photo)

    def show_game_instructions(self):

        """Show the game manual in the shared card-based rules window."""

        import os

        import tkinter.font as tkfont

        from PIL import Image, ImageTk

        parent = self.winfo_toplevel()

        current = getattr(self, '_game_instruction_dialog', None)

        if current is not None:

            try:

                if current.winfo_exists():

                    current.lift()

                    current.focus_force()

                    return

            except tk.TclError:

                pass

        dialog = tk.Toplevel(parent)

        self._game_instruction_dialog = dialog

        instruction_title = f'{GAME_NAME} 游戏规则'
        dialog.title(instruction_title)

        dialog.configure(bg='#faf5e8')

        dialog.resizable(False, False)

        dialog.transient(parent)

        width, height = 1000, 670

        parent.update_idletasks()

        px, py = parent.winfo_rootx(), parent.winfo_rooty()

        pw, ph = max(1, parent.winfo_width()), max(1, parent.winfo_height())

        dialog.geometry(f'{width}x{height}+{px + (pw-width)//2}+{py + (ph-height)//2}')

        manual_pages = self._instruction_pages()

        BG = '#faf5e8'

        HEADER = '#f1e7cd'

        SIDEBAR = '#f2e8d0'

        PANEL = '#fffdf7'

        PANEL_2 = '#f5ecd6'

        BORDER = '#c9b88a'

        GOLD = '#a8842c'

        GOLD_BAR = '#e7d36c'

        TEXT = '#3a2f1e'

        MUTED = '#7a6a50'

        font_name = getattr(self, 'cn_font', 'Microsoft YaHei UI')

        header = tk.Frame(dialog, bg=HEADER, height=76)

        header.pack(fill=tk.X, side=tk.TOP)

        header.pack_propagate(False)

        tk.Label(header, text=instruction_title, font=(font_name, 20, 'bold'),

                 fg=GOLD, bg=HEADER, anchor='w', wraplength=795,

                 justify=tk.LEFT).place(x=24, y=6, width=795, height=41)

        tk.Label(header, text='玩法 · 下注 · 获胜条件 · 判定 · 特别事项',

                 font=(font_name, 14), fg=MUTED, bg=HEADER, anchor='w').place(x=26, y=46)

        def close_dialog():

            try:

                self._game_instruction_dialog = None

            except Exception:

                pass

            try:

                dialog.destroy()

            except tk.TclError:

                pass

        tk.Button(header, text='关闭  ESC', command=close_dialog,

                  font=(font_name, 14, 'bold'), bg='#e8dcc0', fg=TEXT,

                  activebackground='#d9c895', relief=tk.FLAT, bd=0,

                  cursor='hand2').place(x=850, y=17, width=120, height=42)

        tk.Frame(dialog, bg=GOLD_BAR, height=3).pack(fill=tk.X, side=tk.TOP)

        body = tk.Frame(dialog, bg=BG)

        body.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(body, bg=SIDEBAR, width=205)

        sidebar.pack(side=tk.LEFT, fill=tk.Y)

        sidebar.pack_propagate(False)

        tk.Label(sidebar, text='说明目录', font=(font_name, 16, 'bold'),

                 fg=GOLD, bg=SIDEBAR, anchor='w').pack(fill=tk.X, padx=18, pady=(17, 10))

        scroll_host = tk.Frame(body, bg=BG)

        scroll_host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(scroll_host, bg=BG, highlightthickness=0, bd=0, yscrollincrement=36)

        scrollbar = tk.Scrollbar(scroll_host, orient=tk.VERTICAL, command=canvas.yview,

                                 bg='#ded3b7', troughcolor=BG, activebackground=GOLD_BAR,

                                 relief=tk.FLAT, bd=0, width=13)

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=10)

        content = tk.Frame(canvas, bg=BG)

        content_window = canvas.create_window((0, 0), window=content, anchor='nw')

        def sync_scrollregion(_event=None):

            canvas.configure(scrollregion=canvas.bbox('all'))

        def fit_content_width(event):

            canvas.itemconfigure(content_window, width=event.width)

        content.bind('<Configure>', sync_scrollregion)

        canvas.bind('<Configure>', fit_content_width)

        def add_rule(parent_frame, title, detail):

            row = tk.Frame(parent_frame, bg=PANEL)

            row.pack(fill=tk.X, padx=16, pady=5)

            tk.Frame(row, bg=GOLD_BAR, width=5).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 11))

            text_box = tk.Frame(row, bg=PANEL)

            text_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

            if title:
                tk.Label(text_box, text=title, font=(font_name, 15, 'bold'),

                         fg=TEXT, bg=PANEL, anchor='w', justify=tk.LEFT,

                         wraplength=650).pack(fill=tk.X)

            if detail:

                tk.Label(text_box, text=detail, font=(font_name, 14),

                         fg=MUTED, bg=PANEL, anchor='w', justify=tk.LEFT,

                         wraplength=650).pack(fill=tk.X, pady=(3, 0))

        def add_table(parent_frame, title, headers, rows):

            block = tk.Frame(parent_frame, bg=PANEL_2,

                             highlightbackground=BORDER, highlightthickness=1, bd=0)

            block.pack(fill=tk.X, padx=16, pady=8)

            if title:
                tk.Label(block, text=title, font=(font_name, 14, 'bold'),

                         fg=TEXT, bg=GOLD_BAR, anchor='w', justify=tk.LEFT,

                         wraplength=675, padx=11, pady=7).pack(fill=tk.X)

            grid = tk.Frame(block, bg=PANEL_2)

            grid.pack(fill=tk.X)

            count = max([len(headers)] + [len(row) for row in rows]) if rows else len(headers)

            table_font = tkfont.Font(family=font_name, size=14)

            minimums = []

            preferences = []

            for col in range(count):

                picture_width = max((len(row[col][1]) * 74 + 6

                                     for row in rows if col < len(row)

                                     and isinstance(row[col], (tuple, list))

                                     and len(row[col]) == 2 and row[col][0] == '__CARD_IMAGES__'),

                                    default=0)

                minimums.append(max(62, picture_width))

                text_width = max((table_font.measure(str(row[col]))

                                  for row in ([headers] if headers else []) + rows

                                  if col < len(row) and isinstance(row[col], str)), default=0)

                preferences.append(1 if picture_width else max(50, min(text_width, 260)))

            available = 700

            remaining = max(0, available - sum(minimums))

            total_preference = sum(preferences) or 1

            column_widths = [minimums[col] + remaining * preferences[col] // total_preference

                             for col in range(count)]

            if column_widths:

                column_widths[-1] += available - sum(column_widths)

            for col, width in enumerate(column_widths):

                grid.grid_columnconfigure(col, minsize=width)

            matrix = ([headers] if headers else []) + rows

            for r, row in enumerate(matrix):

                for c in range(count):

                    value = row[c] if c < len(row) else ''

                    head = bool(headers) and r == 0

                    bg = GOLD_BAR if head else (PANEL if r % 2 else '#fbf6e9')

                    fg = TEXT if head else MUTED

                    if isinstance(value, (tuple, list)) and len(value) == 2 and value[0] == '__CARD_IMAGES__':

                        image_cell = tk.Frame(grid, bg=bg, borderwidth=1, relief=tk.SOLID)

                        image_cell.grid(row=r, column=c, sticky='nsew')

                        game_dir = os.path.dirname(os.path.abspath(__file__))

                        search_roots = (game_dir, os.path.dirname(game_dir),

                                        os.path.dirname(os.path.dirname(game_dir)))

                        card_dir = next((os.path.join(root, 'A_Tools', 'Card', 'Poker1')

                                         for root in search_roots

                                         if os.path.isdir(os.path.join(root, 'A_Tools', 'Card', 'Poker1'))),

                                        os.path.join(search_roots[1], 'A_Tools', 'Card', 'Poker1'))

                        suits = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club'}

                        for suit, rank in value[1]:

                            filename = 'JOKER-A.png' if suit == 'JOKER' else f'{suits.get(suit, suit)}{rank}.png'

                            path = os.path.join(card_dir, filename)

                            try:

                                with Image.open(path) as source_image:

                                    card_width = 70

                                    card_height = max(1, round(source_image.height * card_width / source_image.width))

                                    small_image = source_image.resize((card_width, card_height), Image.LANCZOS)

                                photo = ImageTk.PhotoImage(small_image, master=dialog)

                                image_label = tk.Label(image_cell, image=photo, bg=bg, bd=0)

                                image_label.image = photo

                                image_label.pack(side=tk.LEFT, padx=2, pady=3)

                            except Exception:

                                # 素材缺失时使用牌桌的后备牌面。

                                source = self.original_images.get((suit, rank), self.original_images['back'])
                                small_image = source.resize((70, 98), Image.Resampling.LANCZOS)
                                photo = ImageTk.PhotoImage(small_image, master=dialog)
                                label = tk.Label(image_cell, image=photo, bg=bg, bd=0)
                                label.image = photo
                                label.pack(side=tk.LEFT, padx=2, pady=3)

                    else:

                        tk.Message(grid, text=value, font=(font_name, 14, 'bold' if head else 'normal'),

                                   fg=fg, bg=bg, anchor='w', justify=tk.LEFT,

                                   width=max(42, column_widths[c] - 16),

                                   padx=7, pady=5, borderwidth=1,

                                   relief=tk.SOLID).grid(row=r, column=c, sticky='nsew')

        def render_page(index):

            for child in content.winfo_children():

                child.destroy()

            for idx, button in enumerate(nav_buttons):

                button.configure(bg='#e6d9b9' if idx == index else SIDEBAR,

                                 fg=GOLD if idx == index else MUTED)

            page_title, subtitle, cards = manual_pages[index]

            top = tk.Frame(content, bg=BG)

            top.pack(fill=tk.X, padx=14, pady=(7, 2))

            tk.Label(top, text=page_title, font=(font_name, 20, 'bold'),

                     fg=GOLD, bg=BG, anchor='w', justify=tk.LEFT,

                     wraplength=690).pack(fill=tk.X)

            if subtitle:

                tk.Label(top, text=subtitle, font=(font_name, 14),

                         fg=MUTED, bg=BG, anchor='w', justify=tk.LEFT,

                         wraplength=690).pack(fill=tk.X, pady=(3, 0))

            for card_title, card_subtitle, rules, tables in cards:

                card = tk.Frame(content, bg=PANEL, highlightbackground=BORDER,

                                highlightcolor=BORDER, highlightthickness=1, bd=0)

                card.pack(fill=tk.X, padx=10, pady=7)

                head = tk.Frame(card, bg=PANEL)

                head.pack(fill=tk.X, padx=16, pady=(12, 5))

                tk.Label(head, text=card_title, font=(font_name, 16, 'bold'),

                         fg=GOLD, bg=PANEL, anchor='w', justify=tk.LEFT,

                         wraplength=680).pack(fill=tk.X)

                if card_subtitle:

                    tk.Label(head, text=card_subtitle, font=(font_name, 14),

                             fg=MUTED, bg=PANEL, anchor='w', justify=tk.LEFT,

                             wraplength=680).pack(fill=tk.X)

                for rule_title, detail in rules:

                    add_rule(card, rule_title, detail)

                for table_title, table_headers, rows in tables:

                    add_table(card, table_title, table_headers, rows)

                tk.Frame(card, bg=PANEL, height=6).pack(fill=tk.X)

            content.update_idletasks()

            canvas.configure(scrollregion=canvas.bbox('all'))

            canvas.yview_moveto(0)

        nav_buttons = []

        for index, (page_title, _subtitle, _cards) in enumerate(manual_pages):

            button = tk.Button(sidebar, text=page_title, command=lambda i=index: render_page(i),

                               font=(font_name, 14), fg=MUTED, bg=SIDEBAR,

                               activebackground='#e8d49a', activeforeground=GOLD,

                               relief=tk.FLAT, bd=0, anchor='w', padx=18, pady=10,

                               cursor='hand2')

            button.pack(fill=tk.X)

            nav_buttons.append(button)

        def on_mousewheel(event):

            canvas.yview_scroll(int(-event.delta / 120), 'units')

            return 'break'

        dialog.bind('<MouseWheel>', on_mousewheel)

        dialog.bind('<Button-4>', lambda _e: (canvas.yview_scroll(-1, 'units'), 'break')[1])

        dialog.bind('<Button-5>', lambda _e: (canvas.yview_scroll(1, 'units'), 'break')[1])

        dialog.bind('<Escape>', lambda _e: close_dialog())

        dialog.protocol('WM_DELETE_WINDOW', close_dialog)

        if nav_buttons:

            render_page(0)

        dialog.after(30, dialog.focus_force)

def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """保持原启动器接口：支持嵌入父窗口或独立运行。"""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        return InOutGUI(parent, actual_balance, actual_user,
                        on_back=on_back, on_balance_change=on_balance_change)
    root = tk.Tk()
    root.title('GAME_NAME')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    page = InOutGUI(root, actual_balance, actual_user)
    page.pack(fill=tk.BOTH, expand=True)
    page.on_back = lambda final_balance: root.destroy()
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance

if __name__ == '__main__':
    final_balance = main()
    print(f'Final balance: {final_balance}')
