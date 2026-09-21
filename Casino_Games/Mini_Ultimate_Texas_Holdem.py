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
from collections import Counter
from itertools import combinations
import math
import time
import secrets
import subprocess
import sys

# =========================================================
# 迷你终极德州扑克 / Mini Ultimate Texas Hold'em
# =========================================================

ROOT_BG = "#1B3D31"
TEXT = "#ffffff"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
TABLE_PANEL = "#2a4a3c"

# 扑克牌最终显示尺寸保持 100x140。Label 本身不留边框/内边距，
# 避免把已经缩放到 100x140 的 PNG 再裁掉边缘。
CARD_WIDTH = 100
CARD_HEIGHT = 140
CARD_SIZE = (CARD_WIDTH, CARD_HEIGHT)
try:
    CARD_RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    CARD_RESAMPLE = Image.LANCZOS

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}

# Three Card Poker 顺序：
# 迷你皇家同花顺 > 同花顺 > 三条 > 顺子 > 同花 > 对子 > 高牌
THREE_CARD_HAND_NAMES = {
    6: "迷你皇家同花顺",
    5: "同花顺",
    4: "三条",
    3: "顺子",
    2: "同花",
    1: "对子",
    0: "高牌",
}

# Blind：只有玩家主游戏胜庄时才按牌型处理；同花/对子/高牌为 Push。
BLIND_PAYOUT = {
    6: 40,  # 迷你皇家同花顺 40:1
    5: 8,   # 同花顺 8:1
    4: 5,   # 三条 5:1
    3: 1,   # 顺子 1:1
    2: 0,   # 同花 Push
    1: 0,   # 对子 Push
    0: 0,   # 高牌 Push
}

# “公牌三张”副注：只根据三张公共牌结算。
COMMUNITY_THREE_PAYOUT = {
    6: 50,   # Q-K-A 同花 / 迷你皇家同花顺 50:1
    5: 40,   # 同花顺
    4: 30,   # 三条
    3: 6,    # 顺子
    2: 3,    # 同花
    1: 1,    # 对子
    # 高牌不赔
}

# “同花+”副注：按玩家最终最佳3张牌结算；主游戏输赢或弃牌均不影响。
FLUSH_PLUS_PAYOUT = {
    6: 200,  # 迷你皇家同花顺 200:1
    5: 40,   # 同花顺 40:1
    4: 10,   # 三条 10:1
    3: 2,    # 顺子 2:1
    2: 1,    # 同花 1:1
    # 对子 / 高牌不赔
}

# Progressive 赔率保持原程序不变（5张牌标准扑克）：
# 皇家同花顺 100% 奖池；同花顺 10%；四条 $1,250；葫芦 $375；同花 $250。
JACKPOT_FLOOR = 271288.59
JACKPOT_ENTRY_FEE = 2.50


def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_path() -> str:
    return os.path.join(project_root(), "A_Tools/Account/saving_data.json")


def uth_log_path() -> str:
    log_dir = os.path.join(project_root(), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Mini_Ultimate_Texas_Holdem.json")


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
        if user.get('user_name') == username:
            user['cash'] = f"{new_balance:,.2f}"
            break
    save_user_data(users)


# =========================================================
# Progressive 文件
# =========================================================

def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    if not os.path.exists(path):
        return True, JACKPOT_FLOOR
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for item in data:
            if item.get('Games') == 'Progressive_2.50':
                return False, float(item.get('jackpot', JACKPOT_FLOOR))
    except Exception:
        return True, JACKPOT_FLOOR
    return True, JACKPOT_FLOOR


def save_progressive(jackpot):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
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
        json.dump(data, f, ensure_ascii=False, indent=4)


# =========================================================
# 扑克牌 / 牌堆
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
                timeout=30,
            )
            shuffle_data = json.loads(result.stdout)
            if "deck" not in shuffle_data or "cut_position" not in shuffle_data:
                raise ValueError("Invalid shuffle data format")
            self.full_deck = [Card(d["suit"], d["rank"]) for d in shuffle_data["deck"]]
            self.cut_position = int(shuffle_data["cut_position"])
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                json.JSONDecodeError, ValueError, KeyError, OSError) as e:
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
        if self.pointer + n > 52:
            raise RuntimeError("牌堆剩余牌数不足")
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt


# =========================================================
# Three Card Poker 牌型评估
# =========================================================

def _three_card_straight_high(values):
    """返回三张牌构成顺子的最高点数；A-2-3 返回 3，否则不是顺子返回 None。"""
    unique = sorted(set(values))
    if len(unique) != 3:
        return None
    if unique == [2, 3, 14]:
        return 3
    if unique[1] == unique[0] + 1 and unique[2] == unique[1] + 1:
        return unique[2]
    return None


def evaluate_three_card_hand(cards):
    """
    精确评估 3 张牌，返回可直接比较的 tuple。
    顺序：迷你皇家同花顺 > 同花顺 > 三条 > 顺子 > 同花 > 对子 > 高牌。
    """
    if len(cards) != 3:
        raise ValueError("Three Card Poker 评估必须正好 3 张牌")

    values = sorted((c.value for c in cards), reverse=True)
    suits = [c.suit for c in cards]
    counts = Counter(values)
    flush = len(set(suits)) == 1
    straight_high = _three_card_straight_high(values)

    # Q-K-A 同花 = 迷你皇家同花顺
    if flush and set(values) == {12, 13, 14}:
        return (6, 14)

    if flush and straight_high is not None:
        return (5, straight_high)

    if 3 in counts.values():
        trip_rank = max(v for v, cnt in counts.items() if cnt == 3)
        return (4, trip_rank)

    if straight_high is not None:
        return (3, straight_high)

    if flush:
        return (2, *values)

    pair_ranks = [v for v, cnt in counts.items() if cnt == 2]
    if pair_ranks:
        pair_rank = max(pair_ranks)
        kicker = max(v for v in values if v != pair_rank)
        return (1, pair_rank, kicker)

    return (0, *values)


def find_best_3(cards):
    """从 3 张或更多牌中取最佳 3 张 Three Card Poker 组合。"""
    if len(cards) < 3:
        return None, None
    best_eval = None
    best_hand = None
    for combo in combinations(cards, 3):
        ev = evaluate_three_card_hand(combo)
        if best_eval is None or ev > best_eval:
            best_eval = ev
            best_hand = combo
    return best_eval, best_hand


def dealer_qualifies(dealer_eval):
    """庄家最少 Q 高牌合格；任何对子或以上自动合格。"""
    if not dealer_eval:
        return False
    if dealer_eval[0] >= 1:
        return True
    return dealer_eval[1] >= 12


# =========================================================
# Progressive 仍使用标准 5 张牌扑克牌型
# rank: 9皇家同花顺, 8同花顺, 7四条, 6葫芦, 5同花, 4顺子,
#       3三条, 2两对, 1对子, 0高牌
# =========================================================

def evaluate_five_card_hand(cards):
    if len(cards) != 5:
        raise ValueError("Progressive 评估必须正好 5 张牌")

    values = sorted((c.value for c in cards), reverse=True)
    suits = [c.suit for c in cards]
    counts = Counter(values)
    flush = len(set(suits)) == 1

    unique = sorted(set(values))
    straight_high = None
    if len(unique) == 5:
        if unique == [2, 3, 4, 5, 14]:
            straight_high = 5
        elif all(unique[i] + 1 == unique[i + 1] for i in range(4)):
            straight_high = unique[-1]

    if flush and straight_high is not None:
        if set(values) == {10, 11, 12, 13, 14}:
            return (9, 14)
        return (8, straight_high)

    count_items = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if count_items[0][1] == 4:
        quad = count_items[0][0]
        kicker = max(v for v in values if v != quad)
        return (7, quad, kicker)

    trips = sorted([v for v, cnt in counts.items() if cnt == 3], reverse=True)
    pairs = sorted([v for v, cnt in counts.items() if cnt == 2], reverse=True)
    if trips and pairs:
        return (6, trips[0], pairs[0])

    if flush:
        return (5, *values)

    if straight_high is not None:
        return (4, straight_high)

    if trips:
        kickers = sorted([v for v in values if v != trips[0]], reverse=True)
        return (3, trips[0], *kickers)

    if len(pairs) >= 2:
        kicker = max(v for v in values if v not in pairs[:2])
        return (2, pairs[0], pairs[1], kicker)

    if len(pairs) == 1:
        kickers = sorted([v for v in values if v != pairs[0]], reverse=True)
        return (1, pairs[0], *kickers)

    return (0, *values)


# 兼容旧代码中可能使用的函数名；仅用于 5 张牌 Progressive。
def evaluate_hand(cards):
    return evaluate_five_card_hand(cards)


def progressive_prize(progressive_eval, jackpot_amount):
    rank = progressive_eval[0]
    if rank == 9:
        return jackpot_amount, "皇家同花顺! 赢得累进大奖 ${amount:,.2f}!"
    if rank == 8:
        return jackpot_amount * 0.10, "同花顺! 赢得累进大奖 ${amount:,.2f}!"
    if rank == 7:
        return 1250.0, "四条! 赢得累进大奖 $1,250!"
    if rank == 6:
        return 375.0, "葫芦! 赢得累进大奖 $375!"
    if rank == 5:
        return 250.0, "同花! 赢得累进大奖 $250!"
    return 0.0, ""


# =========================================================
# 历史记录
# =========================================================

def save_uth_history(deck, player_cards, dealer_cards, community_cards,
                     progressive_card=None, result_info=None):
    log_path = uth_log_path()
    data = {
        "history_record": {
            "player_win": 0,
            "dealer_win": 0,
            "push": 0,
            "fold": 0,
            "game": 0,
        },
        "history": [],
    }

    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                if isinstance(loaded.get("history_record"), dict):
                    for key in data["history_record"]:
                        data["history_record"][key] = int(loaded["history_record"].get(key, 0))
                if isinstance(loaded.get("history"), list):
                    data["history"] = loaded["history"]
        except Exception as e:
            print(f"读取历史文件出错: {e}，将使用全新记录")

    max_id = max((rec.get("game_id", 0) for rec in data["history"]
                  if isinstance(rec, dict) and isinstance(rec.get("game_id", 0), int)), default=0)

    stats = data["history_record"]
    stats["game"] += 1
    result_info = dict(result_info or {})

    if result_info.get("fold"):
        winner = "fold"
        stats["fold"] += 1
    else:
        winner = result_info.get("winner")
        if winner in ("player", "dealer", "push"):
            stats[{"player": "player_win", "dealer": "dealer_win", "push": "push"}[winner]] += 1

    record = {
        "game_id": max_id + 1,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "game": "Mini Ultimate Texas Holdem",
        "deck_order": [str(c) for c in deck.full_deck],
        "cut_position": deck.cut_position,
        "player_cards": [str(c) for c in player_cards],
        "dealer_cards": [str(c) for c in dealer_cards],
        "community_cards": [str(c) for c in community_cards],
        "progressive_card": str(progressive_card) if progressive_card else None,
        "result": result_info,
    }
    if winner is not None:
        record["result"]["winner"] = winner

    data["history"].append(record)
    data["history"] = data["history"][-50:]

    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# =========================================================
# 游戏状态
# =========================================================

class UTHGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.dealer_hole = []
        self.progressive_card = None

        self.ante = 0
        self.blind = 0
        self.community_bet = 0
        self.flush_plus_bet = 0
        self.play_bet = 0
        self.participate_jackpot = False

        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False],
            "dealer": [False],
            "community": [False, False, False],
            "progressive": [False],
        }

        self.jackpot_initial, self.progressive_amount = load_jackpot()
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence

    def deal_initial(self):
        # 发牌顺序：公共牌3张 -> 累进大奖1张 -> 玩家1张 -> 庄家1张。
        self.community_cards = self.deck.deal(3)
        self.progressive_card = self.deck.deal(1)[0]
        self.player_hole = self.deck.deal(1)
        self.dealer_hole = self.deck.deal(1)

    def evaluate_hands(self):
        player_eval, player_best = find_best_3(self.player_hole + self.community_cards)
        dealer_eval, dealer_best = find_best_3(self.dealer_hole + self.community_cards)
        return player_eval, player_best, dealer_eval, dealer_best

    def evaluate_current_hand(self, hole_cards, community_revealed_count):
        revealed = self.community_cards[:community_revealed_count]
        if len(hole_cards) + len(revealed) < 3:
            return None
        best_eval, _ = find_best_3(hole_cards + revealed)
        return best_eval

    def evaluate_community_three(self):
        if len(self.community_cards) != 3:
            return None
        return evaluate_three_card_hand(self.community_cards)

    def evaluate_progressive(self):
        if not self.progressive_card or len(self.player_hole) != 1 or len(self.community_cards) != 3:
            return None
        cards = self.player_hole + [self.progressive_card] + self.community_cards
        return evaluate_five_card_hand(cards)


# =========================================================
# GUI
# =========================================================

class UTHGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.username = username
        self.balance = float(initial_balance)

        self.game = UTHGame()
        self.card_images = {}
        self.original_images = {}
        self.active_card_labels = []
        self.animation_queue = []
        self.card_positions = {}
        self.animation_in_progress = False

        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.bet_widgets = {}

        self.last_win = 0.0
        self.current_bet_multiplier = 0
        self.auto_reset_timer = None
        self.reset_status_timer = None
        self.reset_in_progress = False
        self.buttons_disabled = False
        self.last_jackpot_selection = False
        self.last_game_bet = None
        self.auto_showdown = False

        self.win_details = {
            "ante": 0.0,
            "blind": 0.0,
            "bet": 0.0,
            "community": 0.0,
            "flush_plus": 0.0,
            "jackpot": 0.0,
        }

        self._load_assets()
        self._create_widgets()

    # -----------------------------------------------------
    # 规则说明
    # -----------------------------------------------------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("迷你终极德州扑克 - 游戏规则")
        win.geometry("820x700")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')

        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set, highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content = tk.Frame(canvas, bg='#F0F0F0')
        canvas.create_window((0, 0), window=content, anchor='nw')

        rules_text = """
迷你终极德州扑克 游戏规则

1. 发牌
   - 玩家：1张手牌
   - 庄家：1张手牌
   - 公共牌：3张
   - 累进大奖区域：1张牌

2. 主游戏牌型
   - 玩家：自己的1张手牌 + 3张公共牌，共4张中选最佳3张。
   - 庄家：自己的1张手牌 + 3张公共牌，共4张中选最佳3张。
   - 牌型顺序：迷你皇家同花顺 > 同花顺 > 三条 > 顺子 > 同花 > 对子 > 高牌。
   - 庄家最少 Q 高牌合格；对子或以上自动合格。

3. 下注流程
   - 底注 Ante 与盲注 Blind 金额相同。
   - 开始前：加注可选择不下注或下注 3倍。
   - 发牌顺序：公共牌3张 → 累进大奖1张 → 玩家1张 → 庄家1张。
   - 若开始前未加注：打开玩家1张，可过牌或下注3倍。
   - 若再次过牌：先打开前2张公共牌，可过牌或下注2倍。
   - 若再次过牌：打开第3张公共牌，最终可弃牌或下注1倍。

4. 副注
   - 同花+：玩家1张手牌 + 3张公共牌，从4张中选最终最佳3张；主游戏输赢或弃牌都不影响。
   - 公牌三张：只使用3张公共牌判断，主游戏输赢或弃牌都不影响。

5. Progressive
   - 使用：玩家1张 + 累进大奖区域1张 + 公共牌3张，共5张。
   - Progressive 赔率保持原程序不变。

6. 庄家不合格
   - Ante 退回本金（Push）。
   - Play 与 Blind 仍按玩家/庄家最终牌力比较结算。
"""
        tk.Label(content, text=rules_text, font=('微软雅黑', 11), bg='#F0F0F0',
                 justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X)

        tk.Label(content, text="Blind 赔率", font=('微软雅黑', 12, 'bold'),
                 bg='#F0F0F0').pack(anchor='w', padx=10, pady=(10, 5))
        self._make_odds_table(content, ["牌型", "Blind"], [
            ("迷你皇家同花顺", "40:1"),
            ("同花顺", "8:1"),
            ("三条", "5:1"),
            ("顺子", "1:1"),
            ("同花", "Push"),
            ("对子", "Push"),
            ("高牌", "Push"),
        ])

        tk.Label(content, text="公牌三张副注赔率", font=('微软雅黑', 12, 'bold'),
                 bg='#F0F0F0').pack(anchor='w', padx=10, pady=(15, 5))
        self._make_odds_table(content, ["牌型", "公牌三张"], [
            ("迷你皇家同花顺 (Q-K-A同花)", "50:1"),
            ("同花顺", "40:1"),
            ("三条", "30:1"),
            ("顺子", "6:1"),
            ("同花", "3:1"),
            ("对子", "1:1"),
            ("高牌", "输"),
        ])

        tk.Label(content, text="同花+副注赔率", font=('微软雅黑', 12, 'bold'),
                 bg='#F0F0F0').pack(anchor='w', padx=10, pady=(15, 5))
        self._make_odds_table(content, ["牌型", "同花+"], [
            ("迷你皇家同花顺", "200:1"),
            ("同花顺", "40:1"),
            ("三条", "10:1"),
            ("顺子", "2:1"),
            ("同花", "1:1"),
            ("对子", "输"),
            ("高牌", "输"),
        ])

        tk.Label(content, text="Progressive 赔率（保持原版）", font=('微软雅黑', 12, 'bold'),
                 bg='#F0F0F0').pack(anchor='w', padx=10, pady=(15, 5))
        self._make_odds_table(content, ["牌型", "Progressive"], [
            ("皇家同花顺", "100% 奖池"),
            ("同花顺", "10% 奖池"),
            ("四条", "$1,250"),
            ("葫芦", "$375"),
            ("同花", "$250"),
        ])

        content.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=8)

    @staticmethod
    def _make_odds_table(parent, headers, rows):
        frame = tk.Frame(parent, bg='#F0F0F0')
        frame.pack(fill=tk.X, padx=20, pady=5)
        for c, h in enumerate(headers):
            tk.Label(frame, text=h, font=('微软雅黑', 10, 'bold'), bg='#4B8BBE', fg='white',
                     padx=10, pady=5).grid(row=0, column=c, sticky='nsew', padx=1, pady=1)
        for r, row in enumerate(rows, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, text in enumerate(row):
                tk.Label(frame, text=text, font=('微软雅黑', 10), bg=bg, padx=10, pady=5).grid(
                    row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(headers)):
            frame.columnconfigure(c, weight=1)

    def on_close(self):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except tk.TclError:
                pass
        if self.reset_status_timer:
            try:
                self.after_cancel(self.reset_status_timer)
            except tk.TclError:
                pass
        try:
            if self.username != 'Guest':
                update_balance_in_json(self.username, self.balance)
        except Exception:
            pass
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))
        if callable(self.on_back):
            self.on_back(float(self.balance))

    # -----------------------------------------------------
    # 图片
    # -----------------------------------------------------
    def _load_assets(self):
        # 最终尺寸仍为 100x140；保留 PNG 透明通道，并用高质量缩放。
        card_size = CARD_SIZE
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
        self.card_images = {}

        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path).copy()
            self.original_images['back'] = back_img_orig
            back_img = back_img_orig.resize(card_size, CARD_RESAMPLE)
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception as e:
            print(f"Error loading back image: {e}")
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images['back'] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)

        for suit in SUITS:
            for rank in RANKS:
                suit_name = suit_mapping.get(suit, suit)
                filename = f"{suit_name}{rank}.png"
                path = os.path.join(card_dir, filename)
                try:
                    if os.path.exists(path):
                        img = Image.open(path).copy()
                        self.original_images[(suit, rank)] = img
                        img_resized = img.resize(card_size, CARD_RESAMPLE)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype('arial.ttf', 20)
                        except Exception:
                            font = ImageFont.load_default()
                        try:
                            bbox = draw.textbbox((0, 0), text, font=font)
                            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                        except Exception:
                            text_width, text_height = 40, 20
                        x = (card_size[0] - text_width) / 2
                        y = (card_size[1] - text_height) / 2
                        draw.text((x, y), text, fill='white', font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading card image {path}: {e}")
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    draw.text((25, 55), 'Error', fill='white')
                    self.original_images[(suit, rank)] = img_orig
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)

    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
        raw = self.selected_chip.replace('$', '')
        chip_value = float(raw.replace('K', '')) * 1000 if 'K' in raw else float(raw)

        if bet_type == 'ante':
            current = float(self.ante_var.get())
            max_bet = 10000
            chip_value = min(chip_value, max_bet - current)
            if chip_value <= 0:
                messagebox.showwarning("下注限制", "底注已满，不能再下注！")
                return
            new_ante = int(current + chip_value)
            self.ante_var.set(str(new_ante))
            self.blind_var.set(str(new_ante))
            if self.current_bet_multiplier > 0:
                self.bet_var.set(str(new_ante * self.current_bet_multiplier))
            else:
                self.bet_var.set("0")

        elif bet_type in ('flush_plus', 'community'):
            var = self.flush_plus_var if bet_type == 'flush_plus' else self.community_var
            bet_name = '同花+' if bet_type == 'flush_plus' else '公牌三张'
            current = float(var.get())
            max_bet = 2500
            chip_value = min(chip_value, max_bet - current)
            if chip_value <= 0:
                messagebox.showwarning("下注限制", f"{bet_name}副注已满，不能再下注！")
                return
            var.set(str(int(current + chip_value)))

    def reset_single_bet(self, bet_type, event=None):
        if bet_type == 'ante':
            self.ante_var.set('0')
            self.blind_var.set('0')
            self.bet_var.set('0')
            self.current_bet_multiplier = 0
        elif bet_type == 'flush_plus':
            self.flush_plus_var.set('0')
        elif bet_type == 'community':
            self.community_var.set('0')
        elif bet_type == 'bet':
            self.bet_var.set('0')
            self.current_bet_multiplier = 0

        widget = self.bet_widgets.get(bet_type)
        if widget:
            old = widget.cget('bg')
            widget.config(bg='#FFCDD2')
            self.after(500, lambda w=widget, b=old: w.winfo_exists() and w.config(bg=b))

    def cycle_bet_amount(self, event=None):
        try:
            ante = int(self.ante_var.get())
        except ValueError:
            ante = 0
        if ante <= 0:
            self.bet_var.set('0')
            self.current_bet_multiplier = 0
            return

        try:
            current = int(self.bet_var.get())
        except ValueError:
            current = 0

        if current == 0:
            self.current_bet_multiplier = 3
            self.bet_var.set(str(ante * 3))
        else:
            self.current_bet_multiplier = 0
            self.bet_var.set('0')

    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0, width=725, height=720)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_canvas.create_rectangle(0, 0, 725, 720, fill=ROOT_BG, outline=GOLD, width=5)

        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg=TABLE_PANEL, bd=2, relief=tk.RAISED)
        dealer_frame.place(x=105, y=5, width=300, height=210)
        self.dealer_label = tk.Label(dealer_frame, text='庄家', font=('Arial', 18), bg=TABLE_PANEL, fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg=TABLE_PANEL)
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=10)

        # 累进大奖区域（庄家手牌右侧）
        progressive_zone = tk.Frame(table_canvas, bg=TABLE_PANEL, bd=2, relief=tk.RAISED)
        progressive_zone.place(x=430, y=5, width=190, height=210)
        self.progressive_zone_label = tk.Label(progressive_zone, text='累进大奖区域', font=('Arial', 16),
                                               bg=TABLE_PANEL, fg='#FFD700')
        self.progressive_zone_label.pack(side=tk.TOP, anchor='center', pady=5)
        self.progressive_cards_frame = tk.Frame(progressive_zone, bg=TABLE_PANEL)
        self.progressive_cards_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=10)

        self.ante_info_label0 = tk.Label(table_canvas, text='庄家最少 Q 高牌合格', font=('Arial', 22),
                                         bg=ROOT_BG, fg='#FFD700')
        self.ante_info_label0.place(x=360, y=215, anchor='n')

        # 公共牌 3 张
        community_frame = tk.Frame(table_canvas, bg=TABLE_PANEL, bd=2, relief=tk.RAISED)
        community_frame.place(x=125, y=250, width=475, height=210)
        tk.Label(community_frame, text='公共牌', font=('Arial', 18), bg=TABLE_PANEL, fg='white').pack(
            side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg=TABLE_PANEL)
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=10)

        self.ante_info_label = tk.Label(table_canvas, text='庄家不合格 底注退还', font=('Arial', 22),
                                        bg=ROOT_BG, fg='#FFD700')
        self.ante_info_label.place(x=360, y=460, anchor='n')

        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg=TABLE_PANEL, bd=2, relief=tk.RAISED)
        player_frame.place(x=210, y=500, width=300, height=210)
        self.player_label = tk.Label(player_frame, text='玩家', font=('Arial', 18), bg=TABLE_PANEL, fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg=TABLE_PANEL)
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=10)

        # 右侧控制面板
        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        info_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=3)
        body_info = tk.Frame(info_card, bg=PANEL_BG)
        body_info.pack(fill=tk.X, padx=10, pady=8)
        self.balance_label = tk.Label(body_info, text=f"余额: ${self.balance:,.2f}", font=('Arial', 16, 'bold'),
                                      bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body_info, text='翻牌前', font=('Arial', 16, 'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        progressive_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        progressive_card.pack(fill=tk.X, pady=3)
        header_prog = tk.Frame(progressive_card, bg=HEADER_BG)
        header_prog.pack(fill=tk.X)
        tk.Label(header_prog, text='累进大奖', font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_prog = tk.Frame(progressive_card, bg=PANEL_BG)
        body_prog.pack(fill=tk.X, padx=10, pady=8)
        self.progressive_amount_var = tk.StringVar(value=f"${self.game.progressive_amount:,.2f}")
        self.progressive_display = tk.Label(body_prog, textvariable=self.progressive_amount_var,
                                            font=('Arial', 20, 'bold'), bg=PANEL_BG, fg='#A88100')
        self.progressive_display.pack(anchor='center')

        limit_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        header_limit = tk.Frame(limit_card, bg=HEADER_BG)
        header_limit.pack(fill=tk.X)
        tk.Label(header_limit, text='下注上限', font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)
        body_limit = tk.Frame(limit_card, bg=PANEL_BG)
        body_limit.pack(fill=tk.X, padx=10, pady=8)
        limit_table = tk.Frame(body_limit, bg=PANEL_BG, bd=2, relief=tk.SOLID)
        limit_table.pack(fill=tk.X)
        for col, title in enumerate(['底注最低', '底注最高', '边注最高']):
            tk.Label(limit_table, text=title, font=('Arial', 11, 'bold'), bg=PANEL_BG, borderwidth=1,
                     relief=tk.SOLID, padx=5, pady=5).grid(row=0, column=col, sticky='nsew')
        for col, value in enumerate(['$10', '$10,000', '$2,500']):
            tk.Label(limit_table, text=value, font=('Arial', 12, 'bold'), bg=PANEL_BG, fg='#A88100',
                     borderwidth=1, relief=tk.SOLID, padx=5, pady=5).grid(row=1, column=col, sticky='nsew')
            limit_table.columnconfigure(col, weight=1)

        combined = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined.pack(fill=tk.X, pady=3)
        header_combined = tk.Frame(combined, bg=HEADER_BG)
        header_combined.pack(fill=tk.X)
        tk.Label(header_combined, text='筹码与下注', font=('Arial', 13, 'bold'), bg=HEADER_BG,
                 fg=TITLE_FG).pack(pady=4)
        body = tk.Frame(combined, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=10, pady=8)

        chip_row = tk.Frame(body, bg=PANEL_BG)
        chip_row.pack(fill=tk.X, pady=(0, 8))
        chip_configs = [
            ('$10', '#ffa500', 'black'), ('$25', '#00ff00', 'black'),
            ('$100', '#000000', 'white'), ('$500', '#FF7DDA', 'black'),
            ('$1K', '#ffffff', 'black'), ('$2.5K', '#ff0000', 'white'),
        ]
        for i, (text, bg_color, fg_color) in enumerate(chip_configs):
            chip_row.columnconfigure(i, weight=1)
            canvas_chip = tk.Canvas(chip_row, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            canvas_chip.grid(row=0, column=i, padx=2)
            canvas_chip.create_oval(2, 2, 49, 49, fill=bg_color, outline='black')
            canvas_chip.create_text(25.5, 25.5, text=text, fill=fg_color, font=('Arial', 12, 'bold'))
            canvas_chip.bind('<Button-1>', lambda e, t=text: self.select_chip(t))
            self.chip_buttons.append(canvas_chip)
            self.chip_texts[canvas_chip] = text
        self.select_chip('$10')

        self.progressive_var = tk.IntVar(value=0)
        self.progressive_cb = tk.Checkbutton(body, text='累进大奖 ($2.50)', variable=self.progressive_var,
                                             font=('Arial', 12, 'bold'), bg=PANEL_BG, fg='black',
                                             selectcolor=PANEL_BG)
        self.progressive_cb.pack(anchor='w', padx=90, pady=(2, 4))

        row_side = tk.Frame(body, bg=PANEL_BG)
        row_side.pack(fill=tk.X, pady=2)

        # 同花+ 放在公牌三张左边；两者都是独立副注，单项最高 $2,500。
        tk.Label(row_side, text='同花+:', font=('Arial', 12, 'bold'), bg=PANEL_BG).pack(side=tk.LEFT, padx=(15, 0))
        self.flush_plus_var = tk.StringVar(value='0')
        self.flush_plus_display = tk.Label(row_side, textvariable=self.flush_plus_var, font=('Arial', 12),
                                           bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.flush_plus_display.pack(side=tk.LEFT, padx=(5, 10))
        self.flush_plus_display.bind('<Button-1>', lambda e: self.add_chip_to_bet('flush_plus'))
        self.flush_plus_display.bind('<Button-3>', lambda e: self.reset_single_bet('flush_plus', e))
        self.bet_widgets['flush_plus'] = self.flush_plus_display

        tk.Label(row_side, text='公牌三张:', font=('Arial', 12, 'bold'), bg=PANEL_BG).pack(side=tk.LEFT)
        self.community_var = tk.StringVar(value='0')
        self.community_display = tk.Label(row_side, textvariable=self.community_var, font=('Arial', 12),
                                          bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.community_display.pack(side=tk.LEFT, padx=5)
        self.community_display.bind('<Button-1>', lambda e: self.add_chip_to_bet('community'))
        self.community_display.bind('<Button-3>', lambda e: self.reset_single_bet('community', e))
        self.bet_widgets['community'] = self.community_display

        row_ante = tk.Frame(body, bg=PANEL_BG)
        row_ante.pack(fill=tk.X, pady=2)
        tk.Label(row_ante, text='      底注:', font=('Arial', 12, 'bold'), bg=PANEL_BG).pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value='0')
        self.ante_display = tk.Label(row_ante, textvariable=self.ante_var, font=('Arial', 12),
                                     bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind('<Button-1>', lambda e: self.add_chip_to_bet('ante'))
        self.ante_display.bind('<Button-3>', lambda e: self.reset_single_bet('ante', e))
        self.bet_widgets['ante'] = self.ante_display

        tk.Label(row_ante, text='=', font=('Arial', 12, 'bold'), bg=PANEL_BG).pack(side=tk.LEFT, padx=4)
        self.blind_var = tk.StringVar(value='0')
        self.blind_display = tk.Label(row_ante, textvariable=self.blind_var, font=('Arial', 12),
                                      bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.blind_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets['blind'] = self.blind_display
        tk.Label(row_ante, text=': 盲注', font=('Arial', 12, 'bold'), bg=PANEL_BG).pack(side=tk.LEFT)

        row_bet = tk.Frame(body, bg=PANEL_BG)
        row_bet.pack(fill=tk.X, pady=2)
        tk.Label(row_bet, text='      加注:', font=('Arial', 12, 'bold'), bg=PANEL_BG).pack(side=tk.LEFT)
        self.bet_var = tk.StringVar(value='0')
        self.bet_display = tk.Label(row_bet, textvariable=self.bet_var, font=('Arial', 12),
                                    bg='white', fg='black', width=7, relief=tk.SUNKEN)
        self.bet_display.pack(side=tk.LEFT, padx=5)
        self.bet_display.bind('<Button-1>', self.cycle_bet_amount)
        self.bet_display.bind('<Button-3>', lambda e: self.reset_single_bet('bet', e))
        self.bet_widgets['bet'] = self.bet_display

        # 操作区域使用固定高度。动态按钮只在 action_frame 内切换，
        # 因此无论当前有没有操作按钮，整张“操作”卡片都不会上下跳动。
        action_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID, height=116)
        action_card.pack(fill=tk.X, pady=3)
        action_card.pack_propagate(False)

        header_action = tk.Frame(action_card, bg=HEADER_BG, height=34)
        header_action.pack(fill=tk.X)
        header_action.pack_propagate(False)
        tk.Label(header_action, text='操作', font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=4)

        body_action = tk.Frame(action_card, bg=PANEL_BG)
        body_action.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        body_action.pack_propagate(False)

        self.status_label = tk.Label(body_action, text='设置下注金额并开始游戏', font=('Arial', 12, 'bold'),
                                     bg=PANEL_BG, fg=TITLE_FG, height=1, anchor='center')
        self.status_label.pack(fill=tk.X, pady=(1, 2))

        self.action_frame = tk.Frame(body_action, bg=PANEL_BG, height=42)
        self.action_frame.pack(fill=tk.X, pady=(0, 1))
        self.action_frame.pack_propagate(False)
        self._create_start_buttons()

        bottom = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        bottom.pack(fill=tk.X, pady=3)
        body_bottom = tk.Frame(bottom, bg=PANEL_BG)
        body_bottom.pack(fill=tk.X, padx=10, pady=8)
        self.current_bet_label = tk.Label(body_bottom, text='本局下注: $0.00', font=('Arial', 12),
                                          bg=PANEL_BG, fg='black')
        self.current_bet_label.pack(anchor='w')
        row_last = tk.Frame(body_bottom, bg=PANEL_BG)
        row_last.pack(fill=tk.X, pady=2)
        self.last_win_label = tk.Label(row_last, text='上局获胜: $0.00', font=('Arial', 12),
                                       bg=PANEL_BG, fg='black')
        self.last_win_label.pack(side=tk.LEFT)
        tk.Button(row_last, text='ℹ️', command=self.show_game_instructions, bg='#4B8BBE', fg='white',
                  font=('Arial', 12), width=2, relief=tk.FLAT).pack(side=tk.RIGHT)

    def _create_start_buttons(self):
        frame = tk.Frame(self.action_frame, bg=PANEL_BG)
        frame.pack(pady=5)
        self.reset_bets_button = tk.Button(frame, text='重设金额', command=self.reset_bets,
                                           font=('Arial', 12, 'bold'), bg='#F44336', fg='white', width=10)
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)
        self.repeat_bet_button = tk.Button(frame, text='重复上局下注', command=self.repeat_last_bet,
                                           font=('Arial', 12, 'bold'), bg='#FFC107', fg='black', width=12,
                                           state=tk.NORMAL if self.last_game_bet else tk.DISABLED)
        self.repeat_bet_button.pack(side=tk.LEFT, padx=5)
        self.start_button = tk.Button(frame, text='开始游戏', command=self.start_game,
                                      font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white', width=10)
        self.start_button.pack(side=tk.LEFT, padx=5)

    def _clear_dynamic_action_widgets(self):
        for widget in list(self.action_frame.winfo_children()):
            widget.destroy()

    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete('highlight')
            text_id = None
            oval_id = None
            for item_id in chip.find_all():
                if chip.type(item_id) == 'text':
                    text_id = item_id
                elif chip.type(item_id) == 'oval' and oval_id is None:
                    oval_id = item_id
            if text_id and oval_id and chip.itemcget(text_id, 'text') == chip_text:
                x1, y1, x2, y2 = chip.coords(oval_id)
                chip.create_oval(x1, y1, x2, y2, outline='#2f00ff', width=3, tags='highlight')

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != 'Guest':
            try:
                update_balance_in_json(self.username, self.balance)
            except Exception:
                pass

    def update_hand_labels(self):
        revealed_count = sum(self.game.cards_revealed['community'])
        p_eval = self.game.evaluate_current_hand(self.game.player_hole, revealed_count)
        p_name = THREE_CARD_HAND_NAMES[p_eval[0]] if p_eval else ''
        self.player_label.config(text=f"玩家 - {p_name}" if p_name else '玩家')

        if self.game.stage == 'showdown' or self.game.folded or any(self.game.cards_revealed['dealer']):
            d_eval = self.game.evaluate_current_hand(self.game.dealer_hole, revealed_count)
            d_name = THREE_CARD_HAND_NAMES[d_eval[0]] if d_eval else ''
            self.dealer_label.config(text=f"庄家 - {d_name}" if d_name else '庄家')
        else:
            self.dealer_label.config(text='庄家')

    # -----------------------------------------------------
    # 游戏开始 / 发牌
    # -----------------------------------------------------
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.blind = int(self.blind_var.get())
            self.flush_plus_bet = int(self.flush_plus_var.get())
            self.community_bet = int(self.community_var.get())
            self.bet = int(self.bet_var.get())
        except ValueError:
            messagebox.showerror('错误', '下注金额格式不正确。')
            return

        self.participate_jackpot = bool(self.progressive_var.get())
        self.last_jackpot_selection = self.participate_jackpot

        if self.ante < 10:
            messagebox.showerror('错误', '底注至少需要 $10。')
            return
        if self.blind != self.ante:
            self.blind = self.ante
            self.blind_var.set(str(self.ante))
        if self.bet not in (0, self.ante * 3):
            messagebox.showerror('错误', '开始前的加注只能是不下注或底注3倍。')
            return

        total_bet = self.ante + self.blind + self.flush_plus_bet + self.community_bet + self.bet
        if self.participate_jackpot:
            total_bet += JACKPOT_ENTRY_FEE
        if total_bet > self.balance:
            messagebox.showerror('错误', '余额不足以支付所有下注！')
            return

        self.balance -= total_bet
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total_bet:,.2f}")

        self.last_game_bet = {
            'ante': self.ante,
            'blind': self.blind,
            'flush_plus': self.flush_plus_bet,
            'community': self.community_bet,
            'bet': self.bet,
            'progressive': self.participate_jackpot,
        }

        self.game.reset_game()
        self.game.deal_initial()
        self.game.ante = self.ante
        self.game.blind = self.blind
        self.game.flush_plus_bet = self.flush_plus_bet
        self.game.community_bet = self.community_bet
        self.game.play_bet = self.bet
        self.game.participate_jackpot = self.participate_jackpot

        self.auto_showdown = self.bet > 0
        self._clear_table_cards()
        self._prepare_deal_queue()
        self._set_betting_controls_enabled(False)
        self._clear_dynamic_action_widgets()

        if self.auto_showdown:
            # 开始前已经选择 3X：发牌完成后直接摊牌结算。
            self.game.stage = 'showdown'
            self.stage_label.config(text='摊牌')
            self.status_label.config(text=f"已预先下注 ${self.bet}，发牌完成后进入结算。")
        else:
            self.game.stage = 'pre_flop'
            self.stage_label.config(text='玩家决定')
            self.status_label.config(text='发牌中，请稍后。')
            self._show_preflop_actions(disabled=True)

        self.animate_deal()

    def _clear_table_cards(self):
        for frame in (self.dealer_cards_frame, self.community_cards_frame,
                      self.player_cards_frame, self.progressive_cards_frame):
            for widget in frame.winfo_children():
                widget.destroy()
        self.active_card_labels = []
        self.animation_queue = []
        self.card_positions = {}

    def _prepare_deal_queue(self):
        # 发牌顺序：公共3 -> Progressive1 -> 玩家1 -> 庄家1。
        # 每一张牌都从“所属扑克区域”的最左方 x=0 滑到最终位置。
        # 牌本身保持原版 100x140，不通过缩小牌图来规避裁切。
        deal_start = (0, 0)

        # 这些目标位置按各牌区完整宽度居中设计：
        # 公共牌区约 471px，3张牌以 10px 间隔居中；
        # 庄家/玩家约 296px；Progressive 约 186px。
        community_targets = (75, 185, 295)
        for i, target_x in enumerate(community_targets):
            card_id = f'community_{i}'
            self.card_positions[card_id] = {'current': deal_start, 'target': (target_x, 0)}
            self.animation_queue.append(card_id)

        single_targets = {
            'progressive': 43,
            'player': 98,
            'dealer': 98,
        }
        for prefix in ('progressive', 'player', 'dealer'):
            card_id = f'{prefix}_0'
            self.card_positions[card_id] = {'current': deal_start, 'target': (single_targets[prefix], 0)}
            self.animation_queue.append(card_id)

    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            if self.auto_showdown:
                self.after(500, self.show_showdown)
            else:
                self.after(500, self.reveal_player_cards)
            return

        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        idx = int(card_id.rsplit('_', 1)[1])

        if card_id.startswith('community'):
            frame = self.community_cards_frame
            card = self.game.community_cards[idx]
        elif card_id.startswith('player'):
            frame = self.player_cards_frame
            card = self.game.player_hole[idx]
        elif card_id.startswith('dealer'):
            frame = self.dealer_cards_frame
            card = self.game.dealer_hole[idx]
        else:
            frame = self.progressive_cards_frame
            card = self.game.progressive_card

        label = tk.Label(
            frame,
            image=self.back_image,
            bg=TABLE_PANEL,
            bd=0,
            borderwidth=0,
            highlightthickness=0,
            padx=0,
            pady=0,
        )
        label.place(
            x=self.card_positions[card_id]['current'][0],
            y=self.card_positions[card_id]['current'][1],
            width=CARD_WIDTH,
            height=CARD_HEIGHT,
        )
        label.card_id = card_id
        label.card = card
        label.is_face_up = False
        label.is_moving = True
        label.target_pos = self.card_positions[card_id]['target']
        self.active_card_labels.append(label)
        self.animate_card_move(label)

    def animate_card_move(self, card_label):
        if not hasattr(card_label, 'target_pos') or card_label not in self.active_card_labels:
            return
        try:
            current_x, current_y = card_label.winfo_x(), card_label.winfo_y()
            target_x, target_y = card_label.target_pos
            dx, dy = target_x - current_x, target_y - current_y
            if math.sqrt(dx * dx + dy * dy) < 5:
                card_label.place(x=target_x, y=target_y, width=CARD_WIDTH, height=CARD_HEIGHT)
                card_label.is_moving = False
                self.after(20, self.animate_deal)
                return
            card_label.place(x=current_x + dx * 0.2, y=current_y + dy * 0.2, width=CARD_WIDTH, height=CARD_HEIGHT)
            self.after(20, lambda: self.animate_card_move(card_label))
        except tk.TclError:
            return

    # -----------------------------------------------------
    # 翻牌动画
    # -----------------------------------------------------
    def flip_card_animation(self, card_label):
        if not getattr(card_label, 'card', None):
            return
        front = self.card_images.get((card_label.card.suit, card_label.card.rank), self.back_image)
        self.animate_flip(card_label, front, 0)

    def animate_flip(self, card_label, front_img, step):
        steps = 12
        orig_w, orig_h = CARD_WIDTH, CARD_HEIGHT
        if not card_label.winfo_exists():
            return
        if step > steps:
            card_label.is_face_up = True
            tx, ty = card_label.target_pos
            card_label.place(x=tx, y=ty, width=orig_w, height=orig_h)
            card_label.config(image=front_img, bd=0, borderwidth=0, highlightthickness=0, padx=0, pady=0)
            return

        half = steps // 2
        if step <= half:
            ratio = 1 - step / float(half)
            source = self.original_images['back']
        else:
            ratio = (step - half) / float(half)
            source = self.original_images.get((card_label.card.suit, card_label.card.rank), self.original_images['back'])

        w = max(1, int(orig_w * ratio))
        scaled = ImageTk.PhotoImage(source.resize((w, orig_h), CARD_RESAMPLE))
        if not hasattr(self, '_temp_flip_images'):
            self._temp_flip_images = {}
        self._temp_flip_images[card_label] = scaled
        tx, ty = card_label.target_pos
        card_label.config(image=scaled)
        card_label.place(x=tx + (orig_w - w) // 2, y=ty, width=w, height=orig_h)
        self.after(30, lambda: self.animate_flip(card_label, front_img, step + 1))

    def reveal_player_cards(self):
        for i, label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(label, 'card') and not label.is_face_up:
                self.flip_card_animation(label)
                self.game.cards_revealed['player'][i] = True
        self.status_label.config(text='玩家手牌已打开：下注3倍或过牌。')
        self.after(1200, self.enable_preflop_buttons)

    def _reveal_community_range(self, start_index, end_index, callback=None):
        changed = False
        children = list(self.community_cards_frame.winfo_children())
        for i in range(start_index, min(end_index, len(children))):
            label = children[i]
            if hasattr(label, 'card') and not label.is_face_up:
                self.flip_card_animation(label)
                self.game.cards_revealed['community'][i] = True
                changed = True
        self.after(700, self.update_hand_labels)
        if callback:
            self.after(1500 if changed else 100, callback)

    def reveal_first_two_community(self, callback=None):
        self._reveal_community_range(0, 2, callback)

    def reveal_final_community(self, callback=None):
        self._reveal_community_range(2, 3, callback)

    def reveal_community_cards(self, callback=None):
        self._reveal_community_range(0, 3, callback)

    def reveal_dealer_cards(self):
        for i, label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(label, 'card') and not label.is_face_up:
                self.flip_card_animation(label)
                self.game.cards_revealed['dealer'][i] = True

    def reveal_progressive_card(self):
        for i, label in enumerate(self.progressive_cards_frame.winfo_children()):
            if hasattr(label, 'card') and not label.is_face_up:
                self.flip_card_animation(label)
                self.game.cards_revealed['progressive'][i] = True

    # -----------------------------------------------------
    # 动作按钮 / 流程
    # -----------------------------------------------------
    def _show_preflop_actions(self, disabled=False):
        self._clear_dynamic_action_widgets()
        frame = tk.Frame(self.action_frame, bg=PANEL_BG)
        frame.pack(pady=5)
        state = tk.DISABLED if disabled else tk.NORMAL
        self.check_button = tk.Button(frame, text='过牌', command=lambda: self.play_action(0), state=state,
                                      font=('Arial', 12, 'bold'), bg='#2196F3', fg='white', width=10)
        self.check_button.pack(side=tk.LEFT, padx=5)
        self.bet_3x_button = tk.Button(frame, text='下注3倍', command=lambda: self.play_action(3), state=state,
                                       font=('Arial', 12, 'bold'), bg='#FF9800', fg='white', width=10)
        self.bet_3x_button.pack(side=tk.LEFT, padx=5)

    def enable_preflop_buttons(self):
        if not hasattr(self, 'check_button') or not self.check_button.winfo_exists():
            return
        self.check_button.config(state=tk.NORMAL)
        self.bet_3x_button.config(state=tk.NORMAL if self.balance >= self.game.ante * 3 else tk.DISABLED)

    def _show_community_actions(self):
        self._clear_dynamic_action_widgets()
        self.status_label.config(text='已打开前2张公共牌：下注2倍或过牌。')
        frame = tk.Frame(self.action_frame, bg=PANEL_BG)
        frame.pack(pady=5)
        self.check_button = tk.Button(frame, text='过牌', command=lambda: self.play_action(0),
                                      font=('Arial', 12, 'bold'), bg='#2196F3', fg='white', width=10)
        self.check_button.pack(side=tk.LEFT, padx=5)
        self.bet_2x_button = tk.Button(frame, text='下注2倍', command=lambda: self.play_action(2),
                                       font=('Arial', 12, 'bold'), bg='#FF9800', fg='white', width=10,
                                       state=tk.NORMAL if self.balance >= self.game.ante * 2 else tk.DISABLED)
        self.bet_2x_button.pack(side=tk.LEFT, padx=5)

    def _show_final_actions(self):
        self._clear_dynamic_action_widgets()
        self.status_label.config(text='已打开第3张公共牌：下注1倍或弃牌。')
        frame = tk.Frame(self.action_frame, bg=PANEL_BG)
        frame.pack(pady=5)
        self.fold_button = tk.Button(frame, text='弃牌', command=self.fold_action,
                                     font=('Arial', 12, 'bold'), bg='#F44336', fg='white', width=10)
        self.fold_button.pack(side=tk.LEFT, padx=5)
        self.bet_1x_button = tk.Button(frame, text='下注1倍', command=lambda: self.play_action(1),
                                       font=('Arial', 12, 'bold'), bg='#4CAF50', fg='white', width=10,
                                       state=tk.NORMAL if self.balance >= self.game.ante else tk.DISABLED)
        self.bet_1x_button.pack(side=tk.LEFT, padx=5)

    def _disable_current_action_buttons(self):
        # 玩家一旦作出本阶段选择，当前两个按钮立刻锁定，避免双击/重复下注。
        for name in ('check_button', 'bet_3x_button', 'bet_2x_button', 'fold_button', 'bet_1x_button'):
            btn = getattr(self, name, None)
            if btn is not None:
                try:
                    if btn.winfo_exists():
                        btn.config(state=tk.DISABLED)
                except tk.TclError:
                    pass

    def play_action(self, bet_multiplier):
        # 每个阶段只允许对应的倍数，防止旧按钮/重复事件造成错误下注。
        valid = {
            'pre_flop': (0, 3),
            'community': (0, 2),
            'final': (1,),
        }
        if self.game.stage in valid and bet_multiplier not in valid[self.game.stage]:
            return

        if bet_multiplier > 0:
            bet_amount = bet_multiplier * self.game.ante
            if bet_amount > self.balance:
                messagebox.showerror('错误', '余额不足。')
                return

        # 有效选择一按下，当前阶段的两个按钮马上 disabled。
        self._disable_current_action_buttons()

        if bet_multiplier > 0:
            self.balance -= bet_amount
            self.update_balance()
            self.game.play_bet = bet_amount
            self.bet_var.set(str(int(bet_amount)))
            total = (self.game.ante + self.game.blind + self.game.flush_plus_bet +
                     self.game.community_bet + bet_amount)
            if self.game.participate_jackpot:
                total += JACKPOT_ENTRY_FEE
            self.current_bet_label.config(text=f"本局下注: ${total:,.2f}")

        if self.game.stage == 'pre_flop':
            if bet_multiplier == 3:
                # 已完成加注，进入摊牌结算。
                self.game.stage = 'showdown'
                self.stage_label.config(text='摊牌')
                self.status_label.config(text='已下注3倍，准备摊牌。')
                self.after(400, self.show_showdown)
            else:
                # 打开公共牌前2张，再决定 2X / 过牌。
                self.game.stage = 'community'
                self.stage_label.config(text='公共牌 2张')
                self.status_label.config(text='正在打开前2张公共牌。')
                # 当前两个按钮保持显示但已 disabled；等新阶段按钮出现时再替换。
                self.reveal_first_two_community(self._show_community_actions)

        elif self.game.stage == 'community':
            if bet_multiplier == 2:
                # 已完成加注，进入摊牌结算。
                self.game.stage = 'showdown'
                self.stage_label.config(text='摊牌')
                self.status_label.config(text='已下注2倍，准备摊牌。')
                self.after(400, self.show_showdown)
            else:
                # 打开最后1张公共牌，再决定 1X / 弃牌。
                self.game.stage = 'final'
                self.stage_label.config(text='公共牌 3张')
                self.status_label.config(text='正在打开第3张公共牌。')
                # 当前两个按钮保持显示但已 disabled；等最终阶段按钮出现时再替换。
                self.reveal_final_community(self._show_final_actions)

        elif self.game.stage == 'final' and bet_multiplier == 1:
            # 已完成加注，进入摊牌结算。
            self.game.stage = 'showdown'
            self.stage_label.config(text='摊牌')
            self.status_label.config(text='已下注1倍，准备摊牌。')
            self.after(400, self.show_showdown)

    def fold_action(self):
        if self.game.stage != 'final':
            return
        self._disable_current_action_buttons()
        self.game.folded = True
        self.game.stage = 'folded'
        self.stage_label.config(text='弃牌')
        # 弃牌/1X 两个按钮已经立即 disabled，保留到结算完成再由“再来一局”替换。
        self.status_label.config(text='已弃牌，正在打开全部扑克并结算副注。')

        # 弃牌后仍打开全部扑克。
        # 最终决定阶段玩家牌和3张公共牌通常已经打开，但这里仍统一检查，
        # 同时补开庄家牌与 Progressive 牌，避免任何状态下存在未翻开的牌。
        self.reveal_community_cards()
        for i, label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(label, 'card') and not label.is_face_up:
                self.flip_card_animation(label)
                self.game.cards_revealed['player'][i] = True
        self.reveal_dealer_cards()
        self.reveal_progressive_card()
        self.after(800, self.update_hand_labels)

        # 弃牌路径不结算底注 / 盲注 / 加注，只结算副注并更新 Progressive 底池。
        self.after(2000, self.settle_side_bets_after_fold)

    def _calculate_flush_plus_side_bet(self):
        if self.game.flush_plus_bet <= 0:
            return 0.0
        player_eval, _ = find_best_3(self.game.player_hole + self.game.community_cards)
        if not player_eval:
            return 0.0
        odds = FLUSH_PLUS_PAYOUT.get(player_eval[0])
        if odds is None:
            return 0.0
        return self.game.flush_plus_bet * (1 + odds)

    def _calculate_community_side_bet(self):
        if self.game.community_bet <= 0:
            return 0.0
        ev = self.game.evaluate_community_three()
        odds = COMMUNITY_THREE_PAYOUT.get(ev[0])
        if odds is None:
            return 0.0
        return self.game.community_bet * (1 + odds)

    def _calculate_progressive(self, show_message=True):
        if not self.game.participate_jackpot:
            return 0.0
        ev = self.game.evaluate_progressive()
        if not ev:
            return 0.0
        amount, msg = progressive_prize(ev, self.game.progressive_amount)
        if amount > 0:
            amount = min(amount, self.game.progressive_amount)
            self.game.progressive_amount -= amount
            self.progressive_display.config(bg='gold')
            if show_message:
                messagebox.showinfo('恭喜您获得累进大奖！', msg.format(amount=amount))
        return amount

    def _update_progressive_pool(self):
        total_bet = (self.game.ante + self.game.blind + self.game.flush_plus_bet +
                     self.game.community_bet + self.game.play_bet)
        increase = total_bet * 0.001
        if self.game.participate_jackpot:
            increase += 2.21
        self.game.progressive_amount += increase
        if self.game.progressive_amount < JACKPOT_FLOOR:
            self.game.progressive_amount = JACKPOT_FLOOR
        save_progressive(self.game.progressive_amount)
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")

    def settle_side_bets_after_fold(self):
        # 弃牌后同花+ / 公牌三张 / Progressive 仍独立结算。
        flush_plus_win = self._calculate_flush_plus_side_bet()
        community_win = self._calculate_community_side_bet()
        jackpot_win = self._calculate_progressive(show_message=True)
        side_total = flush_plus_win + community_win + jackpot_win
        self._update_progressive_pool()

        self.win_details = {
            'ante': 0.0,
            'blind': 0.0,
            'bet': 0.0,
            'flush_plus': flush_plus_win,
            'community': community_win,
            'jackpot': jackpot_win,
        }
        self.last_win = side_total
        self.balance += side_total
        self.update_balance()

        self.ante_var.set('0')
        self.blind_var.set('0')
        self.bet_var.set('0')
        self.flush_plus_var.set(self._fmt_amount(flush_plus_win))
        if flush_plus_win > self.game.flush_plus_bet:
            self.flush_plus_display.config(bg='gold')
        else:
            self.flush_plus_display.config(bg='white')

        self.community_var.set(self._fmt_amount(community_win))
        if community_win > self.game.community_bet:
            self.community_display.config(bg='gold')
        elif community_win == self.game.community_bet and self.game.community_bet > 0:
            self.community_display.config(bg='light blue')
        else:
            self.community_display.config(bg='white')

        self.status_label.config(text='游戏结束')
        self.stage_label.config(text='游戏结束')
        self.last_win_label.config(text=f"上局获胜: ${side_total:,.2f}")
        self._save_history({
            'fold': True,
            'total_winnings': side_total,
            'flush_plus_winnings': flush_plus_win,
            'community_winnings': community_win,
            'jackpot_winnings': jackpot_win,
        })
        self._show_restart_button()

    def show_showdown(self):
        # 打开所有尚未打开的牌，然后进行主游戏结算。
        self.game.stage = 'showdown'
        self.stage_label.config(text='摊牌')
        self._clear_dynamic_action_widgets()
        self.status_label.config(text='正在打开所有未打开的牌。')
        self.reveal_community_cards()
        for i, label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(label, 'card') and not label.is_face_up:
                self.flip_card_animation(label)
                self.game.cards_revealed['player'][i] = True
        self.reveal_dealer_cards()
        self.reveal_progressive_card()
        self.after(800, self.update_hand_labels)
        self.after(2000, self.final_reveal)

    def final_reveal(self):
        player_eval, player_best, dealer_eval, dealer_best = self.game.evaluate_hands()
        main_winnings = self.calculate_winnings(player_eval, dealer_eval)
        self.balance += main_winnings
        self.update_balance()

        self.ante_var.set(self._fmt_amount(self.win_details['ante']))
        self.blind_var.set(self._fmt_amount(self.win_details['blind']))
        self.bet_var.set(self._fmt_amount(self.win_details['bet']))

        principals = {
            'ante': self.game.ante,
            'blind': self.game.blind,
            'bet': self.game.play_bet,
        }
        for key in ('ante', 'blind', 'bet'):
            widget = self.bet_widgets.get(key)
            if not widget:
                continue
            amount = self.win_details.get(key, 0.0)
            if amount <= 0:
                widget.config(bg='white')
            elif abs(amount - principals.get(key, 0.0)) < 1e-9:
                widget.config(bg='light blue')
            else:
                widget.config(bg='gold')

        if player_eval > dealer_eval:
            winner, result = 'player', '玩家胜'
        elif dealer_eval > player_eval:
            winner, result = 'dealer', '庄家胜'
        else:
            winner, result = 'push', '平局'

        qualified = dealer_qualifies(dealer_eval)
        self.status_label.config(text='游戏结束')

        context = {
            'winner': winner,
            'result': result,
            'qualified': qualified,
            'player_eval': player_eval,
            'dealer_eval': dealer_eval,
            'player_best': player_best,
            'dealer_best': dealer_best,
            'main_winnings': main_winnings,
        }
        self.after(500, lambda c=context: self._settle_side_bets_after_showdown(c))

    def _settle_side_bets_after_showdown(self, context):
        # 同花+ / 公牌三张 / Progressive 均独立于主游戏结果结算。
        flush_plus_win = self._calculate_flush_plus_side_bet()
        community_win = self._calculate_community_side_bet()
        jackpot_win = self._calculate_progressive(show_message=True)
        side_total = flush_plus_win + community_win + jackpot_win
        self.win_details['flush_plus'] = flush_plus_win
        self.win_details['community'] = community_win
        self.win_details['jackpot'] = jackpot_win
        self._update_progressive_pool()

        self.balance += side_total
        total_winnings = context['main_winnings'] + side_total
        self.last_win = total_winnings
        self.update_balance()

        self.flush_plus_var.set(self._fmt_amount(flush_plus_win))
        if flush_plus_win > self.game.flush_plus_bet:
            self.flush_plus_display.config(bg='gold')
        else:
            self.flush_plus_display.config(bg='white')

        self.community_var.set(self._fmt_amount(community_win))
        if community_win > self.game.community_bet:
            self.community_display.config(bg='gold')
        elif community_win == self.game.community_bet and self.game.community_bet > 0:
            self.community_display.config(bg='light blue')
        else:
            self.community_display.config(bg='white')

        self.status_label.config(text='游戏结束')
        self.stage_label.config(text='游戏结束')
        self.last_win_label.config(text=f"上局获胜: ${total_winnings:,.2f}")
        self._save_history({
            'winner': context['winner'],
            'dealer_qualified': context['qualified'],
            'winnings': total_winnings,
            'main_winnings': context['main_winnings'],
            'flush_plus_winnings': flush_plus_win,
            'community_winnings': community_win,
            'jackpot_winnings': jackpot_win,
            'player_hand': THREE_CARD_HAND_NAMES[context['player_eval'][0]],
            'dealer_hand': THREE_CARD_HAND_NAMES[context['dealer_eval'][0]],
            'player_best': [str(c) for c in context['player_best']],
            'dealer_best': [str(c) for c in context['dealer_best']],
        })
        self._show_restart_button()

    @staticmethod
    def _fmt_amount(value):
        value = float(value)
        return str(int(value)) if value.is_integer() else f"{value:.2f}"

    def calculate_winnings(self, player_eval, dealer_eval):
        # 主游戏只结算底注 / 盲注 / 加注；副注随后独立结算。
        self.win_details = {
            'ante': 0.0,
            'blind': 0.0,
            'bet': 0.0,
            'flush_plus': 0.0,
            'community': 0.0,
            'jackpot': 0.0,
        }
        total = 0.0
        player_wins = player_eval > dealer_eval
        tie = player_eval == dealer_eval
        dealer_is_qualified = dealer_qualifies(dealer_eval)

        # Ante：庄家不合格 Push；庄家合格时玩家胜 1:1、平局 Push、玩家输 Lose。
        if not dealer_is_qualified:
            self.win_details['ante'] = float(self.game.ante)
        elif player_wins:
            self.win_details['ante'] = self.game.ante * 2.0
        elif tie:
            self.win_details['ante'] = float(self.game.ante)
        total += self.win_details['ante']

        # Blind：玩家胜时按 Blind 表；同花/对子/高牌为 Push。平局 Push；玩家输 Lose。
        if player_wins:
            odds = BLIND_PAYOUT[player_eval[0]]
            if odds == 0:
                self.win_details['blind'] = float(self.game.blind)
            else:
                self.win_details['blind'] = self.game.blind * (1.0 + odds)
        elif tie:
            self.win_details['blind'] = float(self.game.blind)
        total += self.win_details['blind']

        # Play：玩家胜 1:1；平局 Push；玩家输 Lose。
        if player_wins:
            self.win_details['bet'] = self.game.play_bet * 2.0
        elif tie:
            self.win_details['bet'] = float(self.game.play_bet)
        total += self.win_details['bet']
        return total

    def _save_history(self, result_info=None):
        try:
            save_uth_history(
                deck=self.game.deck,
                player_cards=self.game.player_hole,
                dealer_cards=self.game.dealer_hole,
                community_cards=self.game.community_cards,
                progressive_card=self.game.progressive_card,
                result_info=result_info or {},
            )
        except Exception as e:
            print(f"保存历史记录时出错: {e}")

    def _show_restart_button(self):
        self._clear_dynamic_action_widgets()
        restart = tk.Button(self.action_frame, text='再来一局', command=self.reset_game,
                            font=('Arial', 12, 'bold'), bg='#2196F3', fg='white', width=10)
        restart.pack(pady=5)
        restart.bind('<Button-3>', self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def _set_betting_controls_enabled(self, enabled):
        if enabled:
            self.ante_display.bind('<Button-1>', lambda e: self.add_chip_to_bet('ante'))
            self.flush_plus_display.bind('<Button-1>', lambda e: self.add_chip_to_bet('flush_plus'))
            self.community_display.bind('<Button-1>', lambda e: self.add_chip_to_bet('community'))
            self.bet_display.bind('<Button-1>', self.cycle_bet_amount)
            self.progressive_cb.config(state=tk.NORMAL)
            for chip in self.chip_buttons:
                chip.bind('<Button-1>', lambda e, t=self.chip_texts[chip]: self.select_chip(t))
        else:
            self.ante_display.unbind('<Button-1>')
            self.flush_plus_display.unbind('<Button-1>')
            self.community_display.unbind('<Button-1>')
            self.bet_display.unbind('<Button-1>')
            self.progressive_cb.config(state=tk.DISABLED)
            for chip in self.chip_buttons:
                chip.unbind('<Button-1>')

    def reset_bets(self):
        self.ante_var.set('0')
        self.blind_var.set('0')
        self.flush_plus_var.set('0')
        self.community_var.set('0')
        self.bet_var.set('0')
        self.current_bet_multiplier = 0
        self.status_label.config(text='已重置所有下注金额')
        for widget in self.bet_widgets.values():
            widget.config(bg='white')

    def _animate_cards_out(self, callback, duration_ms=500):
        # 所有已发出的牌同时在 0.5 秒内向各自扑克区域右侧移出。
        labels = [lbl for lbl in list(self.active_card_labels)
                  if getattr(lbl, 'winfo_exists', lambda: False)()]
        if not labels:
            callback()
            return

        frames = max(1, duration_ms // 20)
        starts = {}
        ends = {}
        for lbl in labels:
            try:
                frame = lbl.master
                frame.update_idletasks()
                starts[lbl] = (lbl.winfo_x(), lbl.winfo_y())
                # 完全越过本牌区右边界。
                ends[lbl] = frame.winfo_width() + CARD_WIDTH + 10
                lbl.is_moving = True
            except tk.TclError:
                pass

        def step(n=0):
            if n >= frames:
                for lbl in labels:
                    try:
                        if lbl.winfo_exists():
                            lbl.place(x=ends.get(lbl, lbl.winfo_x()), y=starts.get(lbl, (0, 0))[1],
                                      width=CARD_WIDTH, height=CARD_HEIGHT)
                    except tk.TclError:
                        pass
                callback()
                return

            t = (n + 1) / float(frames)
            # ease-in：开始柔和，随后加速离桌。
            eased = t * t
            for lbl in labels:
                if lbl not in starts:
                    continue
                try:
                    if lbl.winfo_exists():
                        x0, y0 = starts[lbl]
                        x1 = ends[lbl]
                        x = x0 + (x1 - x0) * eased
                        lbl.place(x=x, y=y0, width=CARD_WIDTH, height=CARD_HEIGHT)
                except tk.TclError:
                    pass
            self.after(20, lambda: step(n + 1))

        step(0)

    def reset_game(self, auto_reset=False):
        if self.reset_in_progress:
            return
        self.reset_in_progress = True

        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except tk.TclError:
                pass
            self.auto_reset_timer = None
        if self.reset_status_timer:
            try:
                self.after_cancel(self.reset_status_timer)
            except tk.TclError:
                pass
            self.reset_status_timer = None

        if auto_reset:
            # 从30秒触发这一刻开始显示提示；1.5秒后固定恢复待下注提示。
            self.status_label.config(text='30秒已到，已自动重置新游戏')
            self.reset_status_timer = self.after(1500, self._restore_ready_status)

        def finish_reset():
            self._do_reset(auto_reset=auto_reset, preserve_status=auto_reset)
            self.reset_in_progress = False

        self._animate_cards_out(finish_reset, duration_ms=100)

    def _restore_ready_status(self):
        self.reset_status_timer = None
        if self.reset_in_progress:
            self.reset_status_timer = self.after(50, self._restore_ready_status)
            return
        if self.game.stage == 'pre_flop':
            self.status_label.config(text='设置下注金额并开始游戏')

    def _do_reset(self, auto_reset=False, preserve_status=False):
        self._load_assets()
        self.game.reset_game()
        self._clear_table_cards()

        self.stage_label.config(text='翻牌前')
        self.player_label.config(text='玩家')
        self.dealer_label.config(text='庄家')
        self.progressive_zone_label.config(text='累进大奖区域')

        self.ante_var.set('0')
        self.blind_var.set('0')
        self.flush_plus_var.set('0')
        self.community_var.set('0')
        self.bet_var.set('0')
        self.current_bet_multiplier = 0
        self.progressive_var.set(1 if self.last_jackpot_selection else 0)
        self.progressive_display.config(bg=PANEL_BG)
        self.progressive_amount_var.set(f"${self.game.progressive_amount:,.2f}")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')

        self._set_betting_controls_enabled(True)
        self._clear_dynamic_action_widgets()
        if not preserve_status:
            self.status_label.config(text='设置下注金额并开始游戏')
        self._create_start_buttons()
        self.current_bet_label.config(text='本局下注: $0.00')

    def repeat_last_bet(self):
        if not self.last_game_bet:
            return
        self.ante_var.set(str(self.last_game_bet['ante']))
        self.blind_var.set(str(self.last_game_bet['blind']))
        self.flush_plus_var.set(str(self.last_game_bet.get('flush_plus', 0)))
        self.community_var.set(str(self.last_game_bet['community']))
        self.bet_var.set(str(self.last_game_bet['bet']))
        ante = int(self.last_game_bet['ante'])
        bet = int(self.last_game_bet['bet'])
        self.current_bet_multiplier = 3 if ante and bet == ante * 3 else 0
        self.progressive_var.set(1 if self.last_game_bet['progressive'] else 0)
        self.status_label.config(text='已重复上局下注')

    def show_card_sequence(self, event=None):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except tk.TclError:
                pass
            self.auto_reset_timer = None

        win = tk.Toplevel(self)
        win.title('本局牌序')
        win.geometry('730x750')
        win.resizable(False, False)
        win.configure(bg='#f0f0f0')
        tk.Label(win, text=f"本局切牌位置: {self.game.deck.start_pos + 1}",
                 font=('Arial', 14, 'bold'), bg='#f0f0f0').pack(pady=10)

        main = tk.Frame(win, bg='#f0f0f0')
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(main)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content = tk.Frame(canvas, bg='#f0f0f0')
        canvas.create_window((0, 0), window=content, anchor='nw')

        small_size = (60, 90)
        images = {}
        for i, card in enumerate(self.game.deck.full_deck):
            orig = self.original_images.get((card.suit, card.rank))
            if orig is None:
                orig = Image.new('RGB', small_size, 'navy')
            images[i] = ImageTk.PhotoImage(orig.resize(small_size, Image.LANCZOS))

        for row in range(6):
            row_frame = tk.Frame(content, bg='#f0f0f0')
            row_frame.pack(fill=tk.X)
            count = 9 if row < 5 else 7
            for col in range(count):
                index = row * 9 + col
                if index >= 52:
                    break
                holder = tk.Frame(row_frame, bg='#f0f0f0')
                holder.grid(row=0, column=col, padx=5)
                bg = 'light blue' if index == self.game.deck.start_pos else '#f0f0f0'
                lbl = tk.Label(holder, image=images[index], bg=bg, borderwidth=1, relief='solid')
                lbl.image = images[index]
                lbl.pack()
                tk.Label(holder, text=str(index + 1), bg=bg, font=('Arial', 9)).pack()

        content._images = images
        content.update_idletasks()
        canvas.config(scrollregion=canvas.bbox('all'))


# =========================================================
# 入口：保持原程序可嵌入调用方式
# =========================================================

def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return UTHGUI(parent, actual_balance, actual_user,
                      on_back=on_back, on_balance_change=on_balance_change)

    root = tk.Tk()
    root.title('迷你终极德州扑克')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    page = UTHGUI(root, actual_balance, actual_user)
    page.pack(fill='both', expand=True)

    def close_standalone():
        try:
            if page.username != 'Guest':
                update_balance_in_json(page.username, page.balance)
        except Exception:
            pass
        root.destroy()

    page.on_back = lambda final_balance: close_standalone()
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance


if __name__ == '__main__':
    final_balance = main()
    print(f"Final balance: {final_balance}")
