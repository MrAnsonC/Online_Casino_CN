# I Love Flush: Lunar card size, 5+2 player rows, cyclic dealing, 2026-10-04.
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
BET_BLUE = "#326D9C"
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
    return os.path.join(parent_dir, 'A_Tools/Account/saving_data.json')

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
        "player_cards": ({seat:[str(c) for c in hand] for seat,hand in player_cards.items()}
                         if isinstance(player_cards,dict) else [str(c) for c in player_cards]),
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

def dealer_flush_qualifies(hand):
    """只判断张数最多的同花牌组；其他花色中的 9 或高牌不计入资格。"""
    selected, count = get_flush_cards(hand)
    return count >= 3 and bool(selected) and selected[0].value >= 9

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
        return dealer_flush_qualifies(self.dealer_hand)

    def get_settlement(self):
        """纯结算结果；返还包含本金，UI 动画不改变赔率。"""
        details = {'ante':0, 'play':0, 'flush':0, 'straight_flush':0}
        qualifies = self.dealer_qualifies()
        winner = 'fold'
        if not self.folded:
            if not qualifies:
                winner = 'player'
                details['ante'], details['play'] = self.ante*2, self.play_bet
            else:
                compared = compare_flush_hands(self.get_player_flush(), self.get_dealer_flush())
                if compared > 0:
                    winner = 'player'
                    details['ante'], details['play'] = self.ante*2, self.play_bet*2
                elif compared < 0:
                    winner = 'dealer'
                else:
                    winner = 'push'
                    details['ante'], details['play'] = self.ante, self.play_bet
        count = get_flush_cards(self.player_hand)[1]
        length = get_longest_straight_flush(self.player_hand)
        if count in FLUSH_PAYOUT:
            details['flush'] = self.flush_bet*(FLUSH_PAYOUT[count]+1)
        if length in STRAIGHT_FLUSH_PAYOUT:
            details['straight_flush'] = self.straight_flush_bet*(STRAIGHT_FLUSH_PAYOUT[length]+1)
        return winner, details, qualifies

def get_straight_flush_cards(hand):
    """返回与现有同花顺赔率长度相符的实际牌组，仅用于中奖提示。"""
    length = get_longest_straight_flush(hand)
    if length not in STRAIGHT_FLUSH_PAYOUT:return []
    candidates = []
    for suit in SUITS:
        suited = {card.value:card for card in hand if card.suit == suit}
        if 14 in suited:suited[1] = suited[14]
        for high in sorted(suited, reverse=True):
            values = list(range(high, high-length, -1))
            if all(value in suited for value in values):
                cards = [suited[value] for value in values]
                if len({id(card) for card in cards}) == length:candidates.append((high,cards))
    return max(candidates,key=lambda item:item[0])[1] if candidates else []


class ILoveFlushTable:
    """两家独立下注及决策，共用一副牌和一手庄家牌。"""
    SEATS = ('Player1', 'Player2')
    SEAT_NAMES = {'Player1':'玩家1', 'Player2':'玩家2', 'Dealer':'庄家'}
    BET_KINDS = ('ante', 'flush', 'straight_flush', 'play')

    def __init__(self):self.reset_game()

    @classmethod
    def empty_bet(cls):return {kind:0.0 for kind in cls.BET_KINDS}

    def reset_game(self):
        self.deck = Deck()
        self.hands = {seat:[] for seat in self.SEATS}
        self.dealer_hand = []
        self.bets = {seat:self.empty_bet() for seat in self.SEATS}
        self.decisions = {seat:'inactive' for seat in self.SEATS}
        self.play_multipliers = {seat:0 for seat in self.SEATS}
        self.cards_revealed = {side:[False]*7 for side in ('Dealer',*self.SEATS)}
        self.active_seats = ()
        self.deal_sequence = []
        self.stage = 'betting'

    def start_round(self, bets, balance, high_bet_mode=False):
        minimum, maximum, side_limit = (100,50000,12500) if high_bet_mode else (10,10000,2500)
        active = []
        copied = {seat:dict(bets[seat]) for seat in self.SEATS}
        for seat, bet in copied.items():
            if set(bet) != set(self.BET_KINDS):raise ValueError('下注项目无效')
            if any(not math.isfinite(value) or value < 0 for value in bet.values()):raise ValueError('下注金额无效')
            if bet['play']:raise ValueError('加注须看牌后决定')
            name = self.SEAT_NAMES[seat]
            if not bet['ante']:
                if any(bet.values()):raise ValueError(f'{name}须先下前注才能参与边注')
                continue
            if not minimum <= bet['ante'] <= maximum:raise ValueError(f'{name}前注须为 ${minimum:,}–${maximum:,}')
            if any(bet[kind] > side_limit for kind in ('flush','straight_flush')):raise ValueError(f'{name}每项边注最多 ${side_limit:,}')
            active.append(seat)
        if not active:raise ValueError('请至少为一家玩家下前注')
        charged = sum(sum(bet.values()) for bet in copied.values())
        if balance < charged:raise ValueError('余额不足以支付两家的下注')
        self.reset_game()
        self.bets = copied
        self.active_seats = tuple(active)
        for seat in active:
            self.decisions[seat] = 'pending'
        # 实际取牌与动画共用逐轮顺序；未下注的一家不取牌也不占节拍。
        self.deal_sequence = [(side,index) for index in range(7) for side in (*active,'Dealer')]
        for side,index in self.deal_sequence:
            hand = self.dealer_hand if side == 'Dealer' else self.hands[side]
            hand.append(self.deck.deal(1)[0])
        self.stage = 'dealing'
        return charged

    def decide(self, seat, action, balance):
        if self.stage != 'decision' or self.decisions.get(seat) != 'pending':raise ValueError('该家已经完成决定')
        if action == 'fold':
            self.decisions[seat] = 'fold'
            return 0.0
        if action not in (1,2,3):raise ValueError('无效加注倍数')
        count = get_flush_cards(self.hands[seat])[1]
        if count < {1:0,2:5,3:6}[action]:raise ValueError('同花张数不足以选择该加注倍数')
        amount = self.bets[seat]['ante']*action
        if balance < amount:raise ValueError('余额不足支付加注')
        self.decisions[seat] = 'play'
        self.play_multipliers[seat] = action
        self.bets[seat]['play'] = amount
        return amount

    def all_decided(self):return all(self.decisions[seat] != 'pending' for seat in self.active_seats)

    def _round_for(self, seat):
        # 复用原游戏的同花比较、及格线与赔付，不复制一套不同的赔率逻辑。
        round_game = ILoveFlushGame.__new__(ILoveFlushGame)
        round_game.player_hand = self.hands[seat]
        round_game.dealer_hand = self.dealer_hand
        round_game.ante = self.bets[seat]['ante']
        round_game.flush_bet = self.bets[seat]['flush']
        round_game.straight_flush_bet = self.bets[seat]['straight_flush']
        round_game.play_bet = self.bets[seat]['play']
        round_game.folded = self.decisions[seat] == 'fold'
        return round_game

    def dealer_qualifies(self):
        return dealer_flush_qualifies(self.dealer_hand)

    def get_settlement(self, seat):return self._round_for(seat).get_settlement()


class ILoveFlushGUI(tk.Frame):
    """Lunar 原版牌尺寸；庄家七张一排，玩家上五下二。"""
    def _card_size(self, side):
        return (self.DEALER_CARD_WIDTH,self.DEALER_CARD_HEIGHT) if side == 'Dealer' else (self.CARD_WIDTH,self.CARD_HEIGHT)

    def _photos(self, side):
        return self._dealer_face_photos if side == 'Dealer' else self._face_photos

    def _sources(self, side):
        return self._dealer_pil_cards if side == 'Dealer' else self._pil_cards

    def _maybe_showdown(self):
        if self.game.stage != 'decision' or self._motion_count or self._showdown_started or not self.game.all_decided():return
        self._showdown_started = True
        self.game.stage = 'showdown'
        self._status('两家已完成决定，庄家开牌中…')
        self._refresh()
        self._open_dealer_cards()


    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEALER_CARD_WIDTH, DEALER_CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    FIVE_PLUS_ONE_DIAMETER = 122.0 * 2 / 3
    ZONE_COLORS = {'Player1':'#35634B','Player2':'#204536'}
    RULE_TEXT = '庄家须持至少 3 张同花且最大牌 ≥ 9才及格'
    BET_KINDS = ('ante', 'flush', 'straight_flush', 'play')

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = username, float(initial_balance)
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = ILoveFlushTable()
        self.bets = {seat:self.game.empty_bet() for seat in self.game.SEATS}
        self.last_bet, self.last_win = None, 0.0
        self.high_bet_mode = False
        self.selected_chip = 10.0
        self._jobs = set()
        self._closing = self._credited = self._return_persisted = self._crediting = False
        self._restart_job = self._restart_deadline = None
        self._motion_count = self._chip_serial = 0
        self._settlement_started = self._showdown_started = False
        self.visual_chips = {}
        self.last_round_snapshot = None
        self._history_available = False
        self._notice_level = 0.0
        self._notice_target = False
        self._notice_job = self._notice_item = self._notice_source = self._notice_photo = None
        self._sorted_sides = set()
        self._face_photos, self._pil_cards, self._flip_photos, self._faded_photos = {}, {}, {}, {}
        self._dealer_face_photos, self._dealer_pil_cards = {}, {}
        self.card_items, self.bet_spots, self.action_buttons = {}, {}, {}
        self.win_details = {seat:self.game.empty_bet() for seat in self.game.SEATS}
        self.current_status = self.RULE_TEXT
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or self._motion_count > 0

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.control_buttons = {}
        c = self.canvas
        self._text(575,18,'我爱同花  I LOVE FLUSH',16,GOLD)
        c.create_rectangle(272,44,878,197,fill=self.TABLE_GREEN,outline='')
        self.title_items = {'Dealer':self._text(575,57,'庄家',16,PANEL_BG)}
        self._draw_limit_table()
        self._draw_odds_panel()
        c.create_rectangle(22,200,1128,226,fill='#173C2E',outline='#65784B',width=1)
        c.create_line(25,201,1125,201,fill='#E0C879',width=2)
        c.create_line(25,225,1125,225,fill='#0C241B',width=2)
        self.rule_item = self._text(575,213,self.RULE_TEXT,12,GOLD)
        for seat,x0,x1 in (('Player1',22,566),('Player2',582,1128)):
            c.create_rectangle(x0,230,x1,617,fill=self.ZONE_COLORS[seat],outline='')
            self.title_items[seat] = self._text((x0+x1)/2,244,self.game.SEAT_NAMES[seat],16,PANEL_BG)
            self._draw_casino_bets(seat,x0)
            for mult,y,color in ((3,393,'#326D9C'),(2,443,'#8D6741'),(1,493,'#397A48')):
                self.action_buttons[(seat,mult)] = self.create_control_button(
                    x0+413,y,x1-15,y+40,f'下注 {mult}X',lambda s=seat,m=mult:self.set_multiplier(m,s),
                    color,font_size=12,draw_shadow=False)
            self.action_buttons[(seat,'fold')] = self.create_control_button(
                x0+413,543,x1-15,583,'弃牌',lambda s=seat:self.fold_action(s),
                '#9B403A',font_size=12,draw_shadow=False)
        self._draw_bottom_controls()
        for side in ('Dealer',*self.game.SEATS):
            width,height = self._card_size(side)
            for index in range(7):
                x,y = self.card_position(side,index)
                c.create_rectangle(x,y,x+width,y+height,outline='#7B9374',dash=(3,3),tags='card_slots')

    def _draw_limit_table(self):
        c = self.canvas
        x0, x1, y0 = 30, 260, 75
        c.create_rectangle(x0, y0, x1, 181, fill='#183B30', outline=GOLD, width=1, tags='limits')
        c.create_rectangle(x0, y0, x1, y0+29, fill='#40634B', outline=GOLD, tags='limits')
        self._text((x0+x1)/2, y0+14, '下注上限', 13, PANEL_BG, tags='limits')
        self.limit_value_items = []
        for col, title in enumerate(('前注最低', '前注最高', '边注最高')):
            left = x0+col*(x1-x0)/3
            right = x0+(col+1)*(x1-x0)/3
            c.create_rectangle(left, y0+29, right, y0+66, outline='#77906B', tags='limits')
            c.create_rectangle(left, y0+66, right, 181, outline='#77906B', tags='limits')
            self._text((left+right)/2, y0+47, title, 10, PANEL_BG, tags='limits')
            self.limit_value_items.append(self._text((left+right)/2, y0+86, '', 10, GOLD, tags='limits'))
        c.tag_bind('limits', '<Button-1>', self.toggle_high_bet_limits)
        c.tag_bind('limits', '<Enter>', lambda _e:c.configure(cursor='hand2'))
        c.tag_bind('limits', '<Leave>', lambda _e:c.configure(cursor=''))

    def _draw_odds_panel(self):
        # 用同款深绿金框面板显示本游戏赔率；本游戏没有累进大奖注。
        c = self.canvas
        x0, x1, y0, y1 = 890, 1120, 62, 192
        c.create_rectangle(x0, y0, x1, y1, fill='#123C30', outline=GOLD, width=2)
        c.create_rectangle(x0+1, y0+1, x1-1, y0+25, fill='#315C40', outline='')
        self._text((x0+x1)/2, y0+13, '边注赔率', 13, '#F6D675')
        for x, title in ((913, '张数'), (980, '同花'), (1070, '同花顺')):
            self._text(x, y0+37, title, 9, PANEL_BG)
        for row, count in enumerate((7, 6, 5, 4, 3)):
            y = y0+53+row*15
            self._text(913, y, str(count), 9, PANEL_BG)
            self._text(980, y, f'{FLUSH_PAYOUT[count]}:1' if count in FLUSH_PAYOUT else '—', 9, GOLD)
            self._text(1070, y, f'{STRAIGHT_FLUSH_PAYOUT[count]}:1', 9, GOLD)

    def _register_spot(self, seat, kind, cx, cy, border, label, size=14):
        c,tag = self.canvas,'spot_'+seat+'_'+kind
        self._text(cx,cy,label,size,PANEL_BG,tags=tag)
        self.bet_spots[(seat,kind)] = dict(tag=tag,center=(cx,cy),border=border)
        c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,k=kind:self.add_chip_to_bet(s,k))
        c.tag_bind(tag,'<Button-3>',lambda _e,s=seat,k=kind:self.reset_single_bet(s,k))
        c.tag_bind(tag,'<Enter>',lambda _e:c.configure(cursor='hand2'))
        c.tag_bind(tag,'<Leave>',lambda _e:c.configure(cursor=''))

    def _draw_casino_bets(self, seat, x0):
        """第二行左侧为同花顺，其下同花；右侧依次为前注和加注。"""
        c = self.canvas
        radius = self.FIVE_PLUS_ONE_DIAMETER/2
        for kind,cy,label in (('straight_flush',436,'同花顺'),('flush',548,'同花')):
            cx = x0+70
            tag = 'spot_'+seat+'_'+kind
            border = c.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,
                fill=self.ZONE_COLORS[seat],outline=GOLD,width=2,tags=tag)
            self._register_spot(seat,kind,cx,cy,border,label)
        cx,cy = x0+202,548
        tag = 'spot_'+seat+'_ante'
        border = c.create_polygon(cx,cy-26,cx+66,cy,cx,cy+26,cx-66,cy,
            fill=BET_BLUE,outline=GOLD,width=2,tags=tag)
        self._register_spot(seat,'ante',cx,cy,border,'前注')
        cx = x0+338
        tag = 'spot_'+seat+'_play'
        border = c.create_rectangle(cx-63,cy-26,cx+63,cy+26,
            fill=BET_BLUE,outline=GOLD,width=2,tags=tag)
        self._register_spot(seat,'play',cx,cy,border,'加注')

    def _status(self, message):
        # 阶段提示仅记录在状态中；庄家资格条在任何阶段都保持原文字。
        self.current_status = message

    def _limits(self):
        return (100, 50000, 12500) if self.high_bet_mode else (10, 10000, 2500)

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item,text=f'余额: ${self.balance:,.2f}')
        total = sum(sum(bet.values()) for bet in self.bets.values())
        c.itemconfigure(self.total_item,text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        for item,value in zip(self.limit_value_items,self._limits()):c.itemconfigure(item,text=f'${value:,}')
        self._render_chips()
        betting = self.game.stage == 'betting' and self._motion_count == 0
        self.set_control_button_state(self.clear_button,betting)
        self.set_control_button_state(self.repeat_button,betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button,betting)
        restarting = self.game.stage in ('await_restart','returning','credit_pending','sweeping')
        c.itemconfigure(self.repeat_button,state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button,state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button,state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button,self.game.stage in ('await_restart','credit_pending'))
        for (seat,action),button in self.action_buttons.items():
            count = get_flush_cards(self.game.hands[seat])[1]
            enabled = self.game.stage == 'decision' and self._motion_count == 0 and self.game.decisions[seat] == 'pending'
            if action != 'fold':
                enabled = enabled and count >= {1:0,2:5,3:6}[action] and self.balance >= self.bets[seat]['ante']*action
            self.set_control_button_state(button,enabled)

    def select_chip(self, amount):
        if self.game.stage == 'betting' and not self._motion_count:
            if isinstance(amount, str):
                value = amount.replace('$','').replace(',','')
                amount = float(value[:-1])*1000 if value.upper().endswith('K') else float(value)
            self.selected_chip = float(amount)
            self._draw_chips()

    def add_chip_to_bet(self, seat, kind):
        if seat not in self.game.SEATS:return
        if kind == 'play':
            if self.game.stage == 'decision':self.set_multiplier(1,seat)
            return
        if self.game.stage != 'betting' or self._motion_count or kind not in self.BET_KINDS:return
        new = {s:dict(bet) for s,bet in self.bets.items()}
        _,max_ante,max_side = self._limits()
        limit = max_ante if kind == 'ante' else max_side
        if new[seat][kind] >= limit:
            self._status(f'{self.game.SEAT_NAMES[seat]}该下注区域已达上限')
            return
        new[seat][kind] = min(limit,new[seat][kind]+self.selected_chip)
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind, event=None):
        if self.game.stage != 'betting' or self._motion_count or seat not in self.game.SEATS or kind not in self.BET_KINDS:return
        new = {s:dict(bet) for s,bet in self.bets.items()}
        new[seat][kind] = 0.0
        self._apply_bet_layout(new)

    def reset_bets(self):
        if self.game.stage == 'betting' and not self._motion_count:
            self._apply_bet_layout({seat:self.game.empty_bet() for seat in self.game.SEATS})

    def apply_last_bet(self):
        if self.game.stage != 'betting' or self._motion_count or not self.last_bet:return
        minimum,max_ante,max_side = self._limits()
        new = {seat:self.game.empty_bet() for seat in self.game.SEATS}
        for seat,old in self.last_bet.items():
            if not old['ante']:continue
            new[seat]['ante'] = max(minimum,min(max_ante,old['ante']))
            for kind in ('flush','straight_flush'):new[seat][kind] = min(max_side,old[kind])
        self._apply_bet_layout(new)

    def _apply_bet_layout(self, new_bets):
        previous = self.bets
        self.bets = {seat:dict(bet) for seat,bet in new_bets.items()}
        transfers = []
        for seat in self.game.SEATS:
            for kind in self.BET_KINDS:
                old,new = previous[seat][kind],self.bets[seat][kind]
                delta = new-old
                if not delta:continue
                center = self.bet_spots[(seat,kind)]['center']
                if delta > 0:
                    transfers.append(dict(amount=delta,start=self._rack_position(),target=center,
                        arrive=lambda s=seat,k=kind,a=new:self._set_visual(s,k,'stake',a)))
                else:
                    self._set_visual(seat,kind,'stake',new)
                    transfers.append(dict(amount=-delta,start=center,target=self._rack_position(),duration=440))
        self._run_chip_batch(transfers,self._refresh)
        self._refresh()

    def card_position(self, side, index):
        if not 0 <= index < 7:raise ValueError('牌位置须为 0–6')
        width,height = self._card_size(side)
        if side == 'Dealer':
            gap = 6
            return 575-(7*width+6*gap)/2+index*(width+gap),78
        row,column = (0,index) if index < 5 else (1,index-5)
        count,gap = (5 if row == 0 else 2),12
        center = (22 if side == 'Player1' else 582)+254
        return center-(count*width+(count-1)*gap)/2+column*(width+gap),264+row*(height+18)

    def _hand(self, side):
        return self.game.dealer_hand if side == 'Dealer' else self.game.hands[side]

    def start_game(self):
        if self.game.stage != 'betting' or self._motion_count:return
        try:total = self.game.start_round(self.bets,self.balance,self.high_bet_mode)
        except ValueError as exc:
            messagebox.showwarning('无法开始',str(exc),parent=self)
            return
        self._cancel_restart_timer()
        self._close_card_sequence()
        self._history_available = False
        self._fade_dealer_notice(False)
        self.balance = round(self.balance-total,2)
        self.bets = {seat:dict(bet) for seat,bet in self.game.bets.items()}
        self.last_bet = {seat:dict(bet) for seat,bet in self.bets.items()}
        self._credited = self._return_persisted = self._settlement_started = self._showdown_started = False
        self._sorted_sides.clear()
        self.canvas.delete('cards')
        self.card_items.clear()
        self._flip_photos.clear()
        self._faded_photos.clear()
        self._load_assets()
        for side,item in self.title_items.items():
            self.canvas.itemconfigure(item,text=self.game.SEAT_NAMES[side])
        self._status('发牌中…')
        self._persist_balance()
        self._refresh()
        self._deal_next(self.game.deal_sequence,0)

    def _deal_next(self, sequence, offset):
        if offset == len(sequence):
            self._reveal_next([(seat,i) for seat in self.game.active_seats for i in range(7)],0,
                lambda:self._sort_revealed_hands(self.game.active_seats,self._enable_decisions))
            return
        side,index = sequence[offset]
        x,y = self.card_position(side,index)
        item = self.canvas.create_image(575,52,image=self._photos(side)['back'],anchor='nw',tags='cards')
        self.card_items[(side,index)] = item
        def move(step=0):
            p = step/6
            self.canvas.coords(item,575+(x-575)*p,52+(y-52)*p)
            if step < 6:self._schedule(round(self.DEAL_MOVE_MS*(step+1)/6)-round(self.DEAL_MOVE_MS*step/6),move,step+1)
            else:self._schedule(round(self.DEAL_CARD_MS)-round(self.DEAL_MOVE_MS),self._deal_next,sequence,offset+1)
        move()

    def _reveal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side,index = sequence[offset]
        card = self._hand(side)[index]
        item = self.card_items[(side,index)]
        x,y = self.card_position(side,index)
        card_width,card_height = self._card_size(side)
        def flip(step=0):
            width = max(1,round(card_width*abs(1-step/5)))
            source = self._sources(side)['back' if step < 5 else (card.suit,card.rank)]
            photo = ImageTk.PhotoImage(source.resize((width,card_height),Image.Resampling.LANCZOS),master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item,image=photo)
            self.canvas.coords(item,x+(card_width-width)/2,y)
            if step < 10:self._schedule(32,flip,step+1)
            else:
                self.canvas.itemconfigure(item,image=self._photos(side)[(card.suit,card.rank)])
                self._flip_photos.pop(item,None)
                self.game.cards_revealed[side][index] = True
                self._reveal_next(sequence,offset+1,complete)
        flip()

    def _sort_revealed_hands(self, sides, complete):
        motions = []
        for side in sides:
            hand = self._hand(side)
            if not hand or side in self._sorted_sides:continue
            ordered = sort_hand_by_groups(hand)
            flush = get_flush_cards(hand)[0]
            # 同花及中奖同花顺只高亮，全部牌面都保持所属行的原始纵坐标。
            straight = get_straight_flush_cards(hand) if side != 'Dealer' and self.bets[side]['straight_flush'] > 0 else []
            highlighted = set(flush+straight)
            remapped = {}
            for target_index,card in enumerate(ordered):
                original_index = next(i for i,c in enumerate(hand) if c is card)
                item = self.card_items[(side,original_index)]
                x,y = self.card_position(side,target_index)
                motions.append((item,self.canvas.coords(item),(x,y)))
                remapped[(side,target_index)] = item
                if card not in highlighted:self._fade_card_item(item,self._sources(side)[(card.suit,card.rank)])
                self.canvas.tag_raise(item)
            for key in [key for key in self.card_items if key[0] == side]:self.card_items.pop(key)
            self.card_items.update(remapped)
            if side == 'Dealer':self.game.dealer_hand = ordered
            else:self.game.hands[side] = ordered
            self._sorted_sides.add(side)
        def done():
            for side in sides:self._update_hand_title(side)
            complete()
        self._move_card_batch(motions,960,done)

    def _update_hand_title(self, side):
        self.canvas.itemconfigure(self.title_items[side],text=self.game.SEAT_NAMES[side])

    def _enable_decisions(self):
        self.game.stage = 'decision'
        self._status('两家各自选择加注倍数或弃牌；都决定后庄家开牌')
        self._refresh()

    def set_multiplier(self, mult, seat='Player1'):
        if self.game.stage != 'decision' or self._motion_count or self.game.decisions.get(seat) != 'pending':return
        try:amount = self.game.decide(seat,mult,self.balance)
        except ValueError as exc:
            messagebox.showwarning('无法加注',str(exc),parent=self)
            return
        self.balance = round(self.balance-amount,2)
        self.bets[seat]['play'] = amount
        self._persist_balance()
        self._update_hand_title(seat)
        self._refresh()
        def arrived():
            self._set_visual(seat,'play','stake',amount)
            self._refresh()
            self._maybe_showdown()
        self._animate_chip(amount,self._rack_position(),self.bet_spots[(seat,'play')]['center'],complete=arrived)

    def fold_action(self, seat='Player1'):
        if self.game.stage != 'decision' or self._motion_count or self.game.decisions.get(seat) != 'pending':return
        self.game.decide(seat,'fold',self.balance)
        self._update_hand_title(seat)
        self._status(f'{self.game.SEAT_NAMES[seat]}已弃牌，边注仍独立结算')
        # 前注在开牌时已扣款；弃牌只立即收走筹码，结算时不重复收取。
        transfers = self._outcome_transfers(seat,'ante',self.bets[seat]['ante'],0)
        self._refresh()
        self._run_chip_batch(transfers,self._maybe_showdown)

    def _open_dealer_cards(self):
        self._reveal_next([('Dealer',i) for i in range(7)],0,
            lambda:self._sort_revealed_hands(['Dealer'],self._settle))

    def _settle(self):
        if self._settlement_started:return
        self._settlement_started = True
        self.game.stage = 'settling'
        self.last_win = 0.0
        transfers,messages,hands = [],[],{}
        qualifies = self.game.dealer_qualifies()
        for seat in self.game.active_seats:
            winner,details,_ = self.game.get_settlement(seat)
            self.win_details[seat] = details
            returned = round(sum(details.values()),2)
            self.last_win += returned
            outcome = {'fold':'弃牌','player':'胜','dealer':'负','push':'平手'}[winner]
            messages.append(f'{self.game.SEAT_NAMES[seat]}：{outcome}')
            self._update_hand_title(seat)
            hands[seat] = dict(winner=winner,winnings=returned,details=details,bets=dict(self.bets[seat]),
                play_multiplier=self.game.play_multipliers[seat])
            for kind in self.BET_KINDS:
                transfers.extend(self._outcome_transfers(seat,kind,self.bets[seat][kind],details[kind]))
        self.last_win = round(self.last_win,2)
        all_folded = all(self.game.decisions[seat] == 'fold' for seat in self.game.active_seats)
        staked = sum(sum(bet.values()) for bet in self.bets.values())
        winner = 'fold' if all_folded else ('player' if self.last_win > staked else 'dealer' if self.last_win < staked else 'push')
        self._status('；'.join(messages)+f' · 合计返还 ${self.last_win:,.2f}')
        self._fade_dealer_notice(not qualifies and not all_folded)
        self._save_history(dict(winner=winner,winnings=self.last_win,hands=hands,dealer_qualifies=qualifies))
        self._refresh()
        self._run_chip_batch(transfers,self._await_next_round)

    def _await_next_round(self):
        if self.game.stage != 'settling':return
        self.game.stage = 'await_restart'
        deck = self.game.deck
        self.last_round_snapshot = dict(full_deck=tuple(deck.full_deck),start_pos=deck.start_pos,
            images={key:im.copy() for key,im in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        self._restart_deadline = time.monotonic()+30
        self._refresh()
        self._restart_tick()

    def _finish_round(self):
        if self.game.stage != 'sweeping':return
        self._fade_dealer_notice(False,immediate=True)
        self.game.reset_game()
        self._history_available = False
        self.bets = {seat:self.game.empty_bet() for seat in self.game.SEATS}
        self._sorted_sides.clear()
        self._faded_photos.clear()
        for side,item in self.title_items.items():self.canvas.itemconfigure(item,text=self.game.SEAT_NAMES[side])
        self._status(self.RULE_TEXT)
        self._refresh()

    def reset_game(self, auto_reset=False):
        if self.game.stage in ('await_restart','credit_pending'):self._return_all_chips()

    def on_close(self):
        if self._closing or self._crediting:return
        settled = self.game.stage in ('settling','await_restart','returning','credit_pending','sweeping')
        if self.game_in_progress and not settled:
            messagebox.showinfo('牌局进行中', '请先完成本局决定和结算。', parent=self)
            return
        if settled:
            if not self._credit_round_return():return
        elif not self._persist_balance():return
        self._closing = True
        self._cancel_restart_timer()
        self._cancel_jobs()
        self._unbind_enter()
        self._close_card_sequence()
        if callable(self.on_back):self.on_back(float(self.balance))
        else:self.winfo_toplevel().destroy()

    def _schedule(self, delay, callback, *args):
        def run():
            self._jobs.discard(job)
            if not self._closing:
                callback(*args)
        job = self.after(delay, run)
        self._jobs.add(job)
        return job

    def _cancel_jobs(self):
        for job in tuple(self._jobs):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs.clear()

    def _on_destroy(self, event):
        if event.widget is self:
            self._closing = True
            self._cancel_jobs()
            self._unbind_enter()

    def _unbind_enter(self):
        binding=getattr(self,'_enter_binding',None)
        if binding:
            try:
                self.winfo_toplevel().unbind('<Return>',binding)
            except tk.TclError:
                pass
            self._enter_binding=None

    def _load_assets(self):
        size = (self.CARD_WIDTH, self.CARD_HEIGHT)
        self.current_poker_folder = ('Poker2' if self.current_poker_folder=='Poker1' else 'Poker1') if hasattr(self,'current_poker_folder') else random.choice(['Poker1','Poker2'])
        folder = self.current_poker_folder
        self.original_images = {}
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'A_Tools', 'Card', folder)
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

        self._dealer_pil_cards = {key:im.resize((self.DEALER_CARD_WIDTH,self.DEALER_CARD_HEIGHT),Image.Resampling.LANCZOS)
            for key,im in self._pil_cards.items()}
        self._dealer_face_photos = {key:ImageTk.PhotoImage(im,master=self) for key,im in self._dealer_pil_cards.items()}

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

    def toggle_high_bet_limits(self, event=None):
        if self.game.stage != 'betting' or self._motion_count:
            return
        if not self.high_bet_mode:
            password = simpledialog.askstring('高额下注', '请输入密码：', parent=self)
            if password is None:
                return
            if password.strip() != time.strftime('%H%M'):
                messagebox.showerror('错误','密码错误',parent=self)
                return
        self.high_bet_mode = not self.high_bet_mode
        self.reset_bets()
        self.last_bet = None
        self.selected_chip = 100 if self.high_bet_mode else 10
        self._draw_chips()
        self._refresh()

    def _persist_balance(self):
        try:
            if self.username and self.username!='Guest':
                update_balance_in_json(self.username,self.balance)
            if callable(self.on_balance_change):
                self.on_balance_change(float(self.balance))
        except Exception as exc:
            messagebox.showerror('余额保存失败',str(exc),parent=self)
            return False
        return True

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
    def _jackpot_label(amount):
        value=round(float(amount),2)
        if abs(value)>=1000:return ILoveFlushGUI._compact(value)
        return f'{value:.0f}' if value.is_integer() else f'{value:.2f}'

    def _draw_chip(self, tag, amount, x, y, rectangular=False, extra_tags=(), show_amount=True):
        c=self.canvas;tags=(tag,*extra_tags)
        if rectangular:
            # 大奖筹码只显示中奖数字，不带货币符号；整数省略 .00。
            label=self._jackpot_label(amount);width=max(96,10*len(label)+16)
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

    def _outcome_transfers(self, seat, kind, stake, returned):
        """本金留位，盈利放左上角，与 Lunar 原版位置一致。"""
        if not stake:return []
        key=(seat,kind,'stake');center=self.bet_spots[(seat,kind)]['center']
        if returned<=0:
            chip=self.visual_chips.pop(key,None)
            return [dict(amount=chip['amount'],start=chip['xy'],target=self.HOUSE_CHIP_POS,duration=280)] if chip else []
        profit=round(returned-stake,2)
        if profit<=0:return []
        target=(center[0]-32,center[1]-30)
        return [dict(amount=profit,start=self.HOUSE_CHIP_POS,target=target,duration=440,
            arrive=lambda:self._set_visual(seat,kind,'profit',profit,target))]

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

    def _inspect_completed_round(self, event=None):
        if self.game.stage!='await_restart':return
        self._cancel_restart_timer()
        self.show_card_sequence()

    def _return_all_chips(self):
        if self.game.stage=='credit_pending':
            self._complete_chip_return()
            return
        if self.game.stage!='await_restart':return
        self._cancel_restart_timer()
        self._history_available=False
        self._close_card_sequence()
        self.game.stage='returning'
        chips=list(self.visual_chips.values());self.visual_chips.clear();transfers=[]
        for index,chip in enumerate(chips):
            target=self._rack_position(index,len(chips))
            def arrived(chip=chip,target=target,index=index):
                # 筹码先回到筹码区，全部到位后才入账；向右移走的是扑克牌。
                self._draw_chip(f'returned_chip_{index}',chip['amount'],*target,
                    chip.get('rectangular',False),extra_tags=('returned_chips',))
            transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=target,
                rectangular=chip.get('rectangular',False),duration=600,arrive=arrived))
        self._refresh();self._run_chip_batch(transfers,self._complete_chip_return)

    def _credit_round_return(self):
        """动画正常完成或用户关闭时共用；只加钱一次，保存失败可重试。"""
        if self._crediting:return False
        if self._return_persisted:return True
        self._crediting=True
        try:
            if not self._credited:
                self.balance=round(self.balance+self.last_win,2)
                self._credited=True
            self._return_persisted=self._persist_balance()
            return self._return_persisted
        finally:
            self._crediting=False

    def _complete_chip_return(self):
        if self.game.stage not in ('returning','credit_pending'):return
        self.game.stage='credit_pending'
        if not self._credit_round_return():
            self._refresh()
            return
        self.game.stage='sweeping'
        self._refresh()
        self.canvas.delete('returned_chips')
        self._sweep_all_cards()

    def _sweep_all_cards(self):
        """入账后，庄家和玩家的全部已显示扑克牌一起在0.2秒内向右移走。"""
        self._fade_dealer_notice(False)
        if not self.card_items:
            self._finish_round()
            return
        self._motion_count+=1
        distance=self.WIDTH+self.CARD_WIDTH
        previous=[0.0]
        def frame(index=0):
            fraction=index/13
            offset=distance*fraction*fraction*(3-2*fraction)
            self.canvas.move('cards',offset-previous[0],0)
            previous[0]=offset
            if index<13:
                self._schedule(round(200*(index+1)/13)-round(200*index/13),frame,index+1)
            else:
                self.canvas.delete('cards')
                self.card_items.clear();self._flip_photos.clear()
                self._motion_count-=1
                self._finish_round()
        frame()

    def _close_card_sequence(self):
        current=getattr(self,'_sequence_window',None)
        if current is not None:
            try:
                if current.winfo_exists():current.destroy()
            except tk.TclError:pass
        self._sequence_window=None

    def _make_dealer_notice(self):
        """使用透明 RGBA 浮层，在牌桌内淡入，透明部分保留原始牌面。"""
        scale=3;width,height=210,48
        layer=Image.new('RGBA',(width*scale,height*scale),(0,0,0,0))
        draw=ImageDraw.Draw(layer)
        draw.rounded_rectangle((1,1,width*scale-2,height*scale-2),radius=10*scale,
            fill=(45,12,16,238),outline=(225,185,99,255),width=2*scale)
        candidates=['msyhbd.ttc','msyh.ttc','simhei.ttf','Arial Unicode.ttf',
            '/System/Library/Fonts/PingFang.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc']
        # Linux 字体由本机 fontconfig 定位；不下载字体，也不依赖额外素材。
        if sys.platform.startswith('linux'):
            try:
                result=subprocess.run(['fc-list','-f','%{file}\n',':lang=zh'],
                    capture_output=True,text=True,timeout=1,check=False)
                if result.returncode==0:
                    candidates[:0]=[line.strip() for line in result.stdout.splitlines() if line.strip()]
            except (OSError,subprocess.TimeoutExpired):pass
        font=None
        for path in candidates:
            try:font=ImageFont.truetype(path,22*scale);break
            except OSError:continue
        self._notice_text_item=None
        if font is not None:
            text='庄家不及格';box=draw.textbbox((0,0),text,font=font)
            draw.text(((width*scale-(box[2]-box[0]))/2-box[0],
                       (height*scale-(box[3]-box[1]))/2-box[1]),text,font=font,fill='#FFF1D1')
        else:
            # 极少数无可供 Pillow 使用的中文字体的系统，交由 Tk 原生字体回退。
            self._notice_text_item=self._text(575,145,'庄家不及格',16,'#FFF1D1',state='hidden',tags='dealer_notice')
        self._notice_source=layer.resize((width,height),Image.Resampling.LANCZOS)
        self._notice_item=self.canvas.create_image(575,145,state='hidden',tags='dealer_notice')

    def _draw_dealer_notice(self):
        alpha=self._notice_level
        if self._notice_item is None:return
        if alpha<=0:
            self.canvas.itemconfigure('dealer_notice',state='hidden');return
        layer=self._notice_source.copy()
        layer.putalpha(self._notice_source.getchannel('A').point(lambda value:round(value*alpha)))
        self._notice_photo=ImageTk.PhotoImage(layer,master=self)
        self.canvas.itemconfigure(self._notice_item,image=self._notice_photo,state='normal')
        self.canvas.tag_raise('dealer_notice')
        if self._notice_text_item is not None:
            background=(75,30,34);foreground=(255,241,209)
            color='#'+''.join(f'{round(a+(b-a)*alpha):02x}' for a,b in zip(background,foreground))
            self.canvas.itemconfigure(self._notice_text_item,state='normal',fill=color)
            self.canvas.tag_raise(self._notice_text_item)

    def _fade_dealer_notice(self, visible, immediate=False):
        target=1.0 if visible else 0.0
        if not immediate and self._notice_target==visible and (self._notice_job is not None or self._notice_level==target):return
        if self._notice_job is not None:
            try:self.after_cancel(self._notice_job)
            except tk.TclError:pass
            self._jobs.discard(self._notice_job);self._notice_job=None
        self._notice_target=visible
        if self._notice_source is None:
            if not visible:return
            self._make_dealer_notice()
        if immediate:
            self._notice_level=target
            self._draw_dealer_notice()
            return
        start=self._notice_level
        def step(frame):
            self._notice_job=None
            self._notice_level=start+(target-start)*frame/12
            self._draw_dealer_notice()
            if frame<12:self._notice_job=self._schedule(25,step,frame+1)
        step(0)

    def show_card_sequence(self, event=None):
        if self.game.stage!='await_restart' or not self._history_available:return
        snapshot=self.last_round_snapshot
        if not snapshot:
            messagebox.showinfo('提示','尚无已结算牌局的牌序。',parent=self);return
        current=getattr(self,'_sequence_window',None)
        if current is not None and current.winfo_exists():current.lift();return
        # 原加勒比窗口：730×750，九张一排，切牌位置高亮，滚动显示52张原始牌序。
        win=tk.Toplevel(self);self._sequence_window=win
        win.title('上局牌序');win.geometry('730x750');win.resizable(0,0);win.configure(bg='#f0f0f0')
        cut_pos=snapshot['start_pos']
        tk.Label(win,text=f'上局切牌位置: {cut_pos+1}',font=('Arial',14,'bold'),bg='#f0f0f0').pack(pady=10)
        main_frame=tk.Frame(win,bg='#f0f0f0');main_frame.pack(fill=tk.BOTH,expand=True,padx=10,pady=5)
        scrollbar=ttk.Scrollbar(main_frame);scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        canvas=tk.Canvas(main_frame,bg='#f0f0f0',yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT,fill=tk.BOTH,expand=True);scrollbar.config(command=canvas.yview)
        content_frame=tk.Frame(canvas,bg='#f0f0f0');canvas.create_window((0,0),window=content_frame,anchor='nw')
        card_frame=tk.Frame(content_frame,bg='#f0f0f0');card_frame.pack(fill=tk.BOTH,expand=True,padx=20,pady=5)
        small_images={}
        for i,card in enumerate(snapshot['full_deck']):
            original=snapshot['images'][(card.suit,card.rank)]
            small_images[i]=ImageTk.PhotoImage(original.resize((60,90),Image.Resampling.LANCZOS),master=win)
        win._card_images=small_images
        for row in range(6):
            row_frame=tk.Frame(card_frame,bg='#f0f0f0');row_frame.pack(fill=tk.X)
            for col in range(9 if row<5 else 7):
                idx=row*9+col
                if idx>=52:break
                container=tk.Frame(row_frame,bg='#f0f0f0');container.grid(row=0,column=col,padx=5)
                bg='light blue' if idx==cut_pos else '#f0f0f0'
                tk.Label(container,image=small_images[idx],bg=bg,borderwidth=1,relief='solid').pack()
                tk.Label(container,text=str(idx+1),bg=bg,font=('Arial',9)).pack()
        content_frame.update_idletasks();canvas.configure(scrollregion=canvas.bbox('all'))

    def _fade_card_item(self, item, source):
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value:round(value*.45)))
        photo = ImageTk.PhotoImage(faded,master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item,image=photo)

    def _move_card_batch(self, motions, duration, complete):
        if not motions:
            complete()
            return
        self._motion_count += 1
        steps = max(1,round(duration/16))
        def frame(index=0):
            p = index/steps
            eased = p*p*(3-2*p)
            for item,(x,y),(tx,ty) in motions:
                self.canvas.coords(item,x+(tx-x)*eased,y+(ty-y)*eased)
            if index<steps:
                self._schedule(round(duration*(index+1)/steps)-round(duration*index/steps),frame,index+1)
            else:
                self._motion_count -= 1
                complete()
        frame()

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
            fg=TITLE_FG,font_size=14,subtext='ENTER',subtext_font_size=10,draw_shadow=False)
        self.restart_button=self.create_control_button(862,638,1138,708,'再来一局(30)',self._return_all_chips,
            HEADER_BG,fg=TITLE_FG,font_size=17,draw_shadow=False)
        c.tag_bind(self.restart_button,'<Button-3>',self._inspect_completed_round)
        c.itemconfigure(self.restart_button,state='hidden')
        # 筹码区下方不放文字，也没有返回按钮。
        self._enter_binding=self.winfo_toplevel().bind('<Return>',lambda _e:
            self._return_all_chips() if self.game.stage in ('await_restart','credit_pending') else self.start_game(),add='+')

    def compute_side_bet_wins(self, seat='Player1'):
        _,details,_ = self.game.get_settlement(seat)
        return details['flush'],details['straight_flush']

    def _save_history(self, result_info=None):
        try:
            if self.game.deck is None:return
            save_love_flush_history(self.game.deck,
                {seat:self.game.hands[seat] for seat in self.game.active_seats},self.game.dealer_hand,result_info)
        except Exception as exc:print(f'保存历史记录出错: {exc}')

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

        dialog.title('I Love Flush 游戏规则')

        dialog.configure(bg='#faf5e8')

        dialog.resizable(False, False)

        dialog.transient(parent)



        width, height = 1000, 670

        parent.update_idletasks()

        px, py = parent.winfo_rootx(), parent.winfo_rooty()

        pw, ph = max(1, parent.winfo_width()), max(1, parent.winfo_height())

        dialog.geometry(f'{width}x{height}+{px + (pw-width)//2}+{py + (ph-height)//2}')



        manual_pages = [
            (
                '玩法',
                '了解游戏目标，以及一局从下注到结算的完整顺序。',
                [
                    [
                        '游戏目标',
                        '',
                        [
                            ('本局目标', '组成尽可能强的同花牌组并胜过庄家；\n同花边注独立结算。'),
                        ],
                        [],
                    ],
                    [
                        '一局如何进行',
                        '',
                        [
                            ('玩家下注', '两家分别下注前注及可选同花、同花顺边注；\n未下前注的一家不参与发牌。'),
                            ('玩家决策', '两家分别查看七张牌并弃牌或选择可用加注倍数；\n两家都决定后，庄家才开牌。'),
                            ('庄家开牌', '庄家亮出七张牌并排列同花牌。'),
                            ('结算', '先比较同花牌，再独立结算边注。'),
                        ],
                        [],
                    ],
                    [
                        '发牌',
                        '',
                        [
                            ('', '• 参与的玩家与共同庄家各发7张牌\n• 庄家七张一排；玩家第一行5张、第二行2张\n• 按玩家1→玩家2→庄家循环发牌7轮\n• 未下前注的一家不取牌，也不占发牌节拍\n• 玩家牌全部明牌，庄家牌全部暗牌'),
                        ],
                        [],
                    ],
                    [
                        '系统自动对玩家牌排序',
                        '',
                        [
                            ('', '• 按花色分组，组内降序，组间按最大牌降序\n• 同花牌组保持原位，其余牌淡化\n• 中奖同花顺只高亮；任何情况下都不额外下移牌面'),
                        ],
                        [],
                    ],
                    [
                        '决策',
                        '',
                        [
                            ('', '• 弃牌：立即收走前注筹码；同花注和同花顺注仍按牌型赔付\n• 下注1倍（加注 = 前注×1）\n• 下注2倍（需同花牌≥5张）\n• 下注3倍（需同花牌≥6张）'),
                        ],
                        [],
                    ],
                ],
            ),
            (
                '下注 & 限红',
                '各项目限红如下。',
                [
                    [
                        '下注项目',
                        '',
                        [],
                        [
                            (
                                '下注项目与限红',
                                ['项目', '限红', '作用'],
                                [
                                    ['前注', '普通：$10–$10,000\n高额：$100–$50,000', '参与主注比牌。'],
                                    ['同花边注', '普通：每项最高$2,500\n高额：每项最高$12,500', '按玩家同花组合判奖。'],
                                    ['同花顺边注', '普通：每项最高$2,500\n高额：每项最高$12,500', '按玩家同花顺组合判奖。'],
                                ],
                            ),
                        ],
                    ],
                ],
            ),
            (
                '获胜条件 & 赔率',
                '按下列表格核对各项判定条件、胜负结果及赔率。',
                [
                    [
                        '比牌规则',
                        '',
                        [],
                        [
                            (
                                '比牌与及格线',
                                ['判断', '规则'],
                                [
                                    ['庄家及格', '只选张数最多的花色牌组：至少三张，且该组最高牌为 9 或以上。\n其他花色中的高牌不计入资格。'],
                                    ['比大小', '先比同花张数；\n相同再从大到小逐张比点数。'],
                                    ['完全相同', '双方平局。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '结算',
                        '',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['不及格', '前注1:1，加注退还'],
                                    ['及格后比较双方同花牌', '* 先比数量，多者胜'],
                                    ['', '* 数量相同则逐张比大小'],
                                    ['玩家胜', '前注1:1，加注1:1'],
                                    ['庄家胜', '前注和加注全输'],
                                    ['平手', '前注和加注退回'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '边注赔付（按玩家牌型，无论是否弃牌）',
                        '',
                        [],
                        [
                            (
                                '',
                                ['情形／项目', '赔率／结算规则'],
                                [
                                    ['7张', '300:1   6张: 30:1   5张: 6:1   4张: 3:1'],
                                    ['同花边注（按玩家同花张数）', '（赔率表示赢的倍数，返还时包含本金）'],
                                    ['7张', '8000:1  6张: 1000:1  5张: 100:1  4张: 60:1  3张: 7:1'],
                                    ['注', '加注赔率均为1:1，无论牌型。'],
                                ],
                            ),
                        ],
                    ],
                    [
                        '庄家资格与主注结算',
                        '',
                        [],
                        [
                            (
                                '前注 / 加注结算',
                                ['获胜条件', '前注 / Ante', '相关下注'],
                                [
                                    ['庄家不及格', '前注赢 1:1', '加注退还'],
                                    ['庄家及格、玩家胜', '前注赢 1:1', '加注赢 1:1'],
                                    ['庄家及格、平局', '前注退还', '加注退还'],
                                    ['庄家及格、玩家负', '前注输', '加注输'],
                                ],
                            ),
                        ],
                    ],
                ],
            ),
            (
                '牌型等级表',
                '牌型由强到弱排列；\n同级牌型继续比较相关点数。',
                [
                    [
                        '判定与牌例',
                        '下方图片展示牌型示例；\n同一牌型也可能由其他牌面组成。',
                        [],
                        [
                            (
                                '',
                                ['等级', '牌型', '牌例'],
                                [
                                    [
                                        '1',
                                        '七张同花',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♥', 'A'),
                                                ('♥', 'K'),
                                                ('♥', 'Q'),
                                                ('♥', 'J'),
                                                ('♥', '9'),
                                                ('♥', '6'),
                                                ('♥', '3'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '2',
                                        '五张同花',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♠', 'A'),
                                                ('♠', 'J'),
                                                ('♠', '9'),
                                                ('♠', '6'),
                                                ('♠', '3'),
                                            ),
                                        ),
                                    ],
                                    [
                                        '3',
                                        '三张同花',
                                        (
                                            '__CARD_IMAGES__',
                                            (
                                                ('♦', 'A'),
                                                ('♦', '9'),
                                                ('♦', '3'),
                                            ),
                                        ),
                                    ],
                                ],
                            ),
                        ],
                    ],
                ],
            ),
            (
                '特别事项',
                '补充说明特殊牌、模式差异和金额结算方式。',
                [
                    [
                        '特别规则补充',
                        '',
                        [
                            ('需留意的规则', '同花边注与同花顺边注只按玩家手牌判奖；\n是否弃牌及庄家是否及格不影响边注判奖。'),
                        ],
                        [],
                    ],
                    [
                        '特殊下注规则',
                        '',
                        [
                            ('下注阶段', '前注（必须）'),
                            ('', '同花边注（可选）'),
                            ('', '同花顺边注（可选）'),
                        ],
                        [],
                    ],
                ],
            ),
        ]



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

        tk.Label(header, text='I Love Flush 游戏规则', font=(font_name, 20, 'bold'),

                 fg=GOLD, bg=HEADER, anchor='w', wraplength=795,

                 justify=tk.LEFT).place(x=24, y=6, width=795, height=41)

        tk.Label(header, text='玩法 · 下注 · 获胜条件 · 牌型 · 特别事项',

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

                                photo = ImageTk.PhotoImage(small_image)

                                image_label = tk.Label(image_cell, image=photo, bg=bg, bd=0)

                                image_label.image = photo

                                image_label.pack(side=tk.LEFT, padx=2, pady=3)

                            except Exception:

                                # Keep the example cell image-only if an asset is unavailable.

                                tk.Label(image_cell, text='', bg='#fffdf7', width=3, height=2,

                                         borderwidth=1, relief=tk.SOLID).pack(side=tk.LEFT, padx=2, pady=3)

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
    root.title("我爱同花")
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
