# Auto Texas Holdem — UTH Canvas interface
# Wagers, limits and net payout odds: supplied Auto Texas Holdem.
# After the five board cards, deal alternating Player1/Player2 for two rounds.
# Table composition, controls, cards/chips, manual and inspection: supplied UTH.
# Keep this file in the original casino project; A_Tools.Account remains required.

import sys as _account_sys
from pathlib import Path as _AccountPath
_account_root = next((p for p in (_AccountPath(__file__).resolve().parent, *_AccountPath(__file__).resolve().parents) if (p / "A_Tools" / "Account" / "secure_json.py").is_file()), None)
if _account_root is None:
    raise RuntimeError("Cannot locate encrypted account storage")
if str(_account_root) not in _account_sys.path:
    _account_sys.path.insert(0, str(_account_root))
from A_Tools.Account import install_secure_json as _install_secure_json
_install_secure_json()
PROJECT_ROOT = str(_account_root)
del _install_secure_json, _account_root, _AccountPath, _account_sys


import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
from collections import Counter
from itertools import combinations
from decimal import Decimal, ROUND_HALF_UP
import math
import time
import secrets
import subprocess, sys


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
    9: '皇家同花顺', 8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花',
    4: '顺子', 3: '三条', 2: '两对', 1: '对子', 0: '高牌'
}


BET_PAYOUT = {
    # 胜负平
    "cowboy_win": 1,
    "tie": 19,
    "bull_win": 1,
    
    # 手牌组合
    "any_suited_connector": 0.66,
    "any_pair": 7.5,
    "any_ace_pair": 99,
    
    # 赢家牌型
    "high_card": 1.2,
    "two_pair": 2.1,
    "three_kind_straight": 3.7,
    "full_house": 19,
    "four_kind_flush": 247
}

# 每个下注项目的独立上限。
BET_LIMITS = {
    "cowboy_win": 50000,
    "bull_win": 50000,
    "tie": 10000,
    "any_suited_connector": 25000,
    "any_pair": 25000,
    "any_ace_pair": 25000,
    "high_card": 25000,
    "two_pair": 25000,
    "three_kind_straight": 25000,
    "full_house": 25000,
    "four_kind_flush": 25000,
}


BET_LABELS = {
    'cowboy_win': '玩家1胜', 'tie': '平局', 'bull_win': '玩家2胜',
    'any_suited_connector': '同花 / 连牌', 'any_pair': '任意对子',
    'any_ace_pair': '任意 AA', 'high_card': '高牌 / 对子',
    'two_pair': '两对', 'three_kind_straight': '三条 / 顺子 / 同花',
    'full_house': '葫芦', 'four_kind_flush': '四条 / 同花顺 / 皇家',
}
BET_SEATS = {kind: ('Player1' if kind in (
    'cowboy_win', 'tie', 'bull_win', 'any_suited_connector', 'any_pair', 'any_ace_pair'
) else 'Player2') for kind in BET_PAYOUT}


def money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def project_root():
    return PROJECT_ROOT


def get_data_file_path():
    return os.path.join(project_root(), 'A_Tools', 'Account', 'saving_data.json')


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


def format_money(amount):
    """格式化金额显示，使用逗号分隔"""
    if amount >= 0:
        return "${:,.2f}".format(amount)
    else:
        return "-${:,.2f}".format(abs(amount))


class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]
    def __repr__(self):
        return f"{self.rank}{self.suit}"


class Deck:
    def __init__(self):
        # 获取当前脚本所在目录的上一级目录
        parent_dir = project_root()
        # 新的Card文件夹路径
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        
        # 保证 Python 输出为 UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        try:
            # 调用外部 shuffle.py，超时 30 秒
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
            
            # 用本模块的 Card 类实例化
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
            # fallback：标准顺序+安全乱序
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)
        
        # 通用的洗牌后索引 & 发牌序列逻辑
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]
    
    def _secure_shuffle(self):
        """Fisher–Yates 洗牌，用 secrets 保证随机性"""
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
                return (9, seq2[:5]) if seq2[0] == 14 else (8, seq2[:5])

    counts_list = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if counts_list[0][1] == 4:
        quad = counts_list[0][0]
        kicker = max(v for v in values if v != quad)
        return (7, [quad, kicker])
    if counts_list[0][1] == 3 and counts_list[1][1] >= 2:
        return (6, [counts_list[0][0], counts_list[1][0]])
    if flush_suit:
        top5 = sorted((c.value for c in flush_cards), reverse=True)[:5]
        return (5, top5)
    if straight_vals:
        return (4, straight_vals)
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, [three] + kickers)
    pairs = [v for v, cnt in counts_list if cnt == 2]
    if len(pairs) >= 2:
        high, low = pairs[0], pairs[1]
        kicker = max(v for v in values if v not in (high, low))
        return (2, [high, low, kicker])
    if counts_list[0][1] == 2:
        pair = counts_list[0][0]
        kickers = [v for v in values if v != pair][:3]
        return (1, [pair] + kickers)
    return (0, values[:5])


def find_best_5(cards):
    best_eval = None
    best_hand = None
    for combo in combinations(cards, 5):
        ev = evaluate_hand(combo)
        if best_eval is None or ev > best_eval:
            best_eval = ev
            best_hand = combo
    return best_eval, best_hand


class TexasHoldemGame:
    SEATS = ('Player1', 'Player2')

    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.cowboy_hole = []  # 玩家1手牌
        self.bull_hole = []    # 玩家2手牌
        self.bets = {bet_type: 0 for bet_type in BET_PAYOUT}
        self.stage = "betting"  # betting, dealing, showdown
        self.cards_revealed = {
            "cowboy": [False, False],
            "bull": [False, False],
            "community": [False, False, False, False, False]
        }
        # 新增：记录牌序信息
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence
        self.settlement = None
        self.deal_sequence = ([('Public', i) for i in range(5)]
                              + [(seat, i) for i in range(2) for seat in self.SEATS])
    
    def deal_initial(self):
        """发初始牌：先发5张公共牌，再按玩家1、玩家2的顺序交替各发1张，发两轮。"""
        self.community_cards = self.deck.deal(5)
        self.cowboy_hole, self.bull_hole = [], []
        for _ in range(2):
            self.cowboy_hole.extend(self.deck.deal(1))
            self.bull_hole.extend(self.deck.deal(1))
    
    def evaluate_hands(self):
        """评估玩家1和玩家2的手牌"""
        cowboy_cards = self.cowboy_hole + self.community_cards
        bull_cards = self.bull_hole + self.community_cards
        
        cowboy_eval, cowboy_best = find_best_5(cowboy_cards)
        bull_eval, bull_best = find_best_5(bull_cards)
        
        return cowboy_eval, cowboy_best, bull_eval, bull_best
    
    def evaluate_current_hand(self, cards, community_revealed_count):
        """评估当前手牌（只考虑已翻开的牌）"""
        if community_revealed_count == 0:
            return None
        
        # 只使用已翻开的公共牌
        revealed_community = self.community_cards[:community_revealed_count]
        all_cards = cards + revealed_community
        
        # 至少需要2张牌才能评估
        if len(all_cards) < 2:
            return None
            
        best_eval, _ = find_best_5(all_cards)
        return best_eval
    
    def check_hand_combinations(self):
        """检查手牌组合"""
        results = {
            "any_suited_connector": False,
            "any_pair": False,
            "any_ace_pair": False
        }
        
        # 检查玩家1手牌
        c1, c2 = self.cowboy_hole
        # 同花
        if c1.suit == c2.suit:
            results["any_suited_connector"] = True
        # 连牌
        elif abs(c1.value - c2.value) == 1 or (c1.value == 14 and c2.value == 2) or (c1.value == 2 and c2.value == 14):
            results["any_suited_connector"] = True
        # 对子
        if c1.rank == c2.rank:
            results["any_pair"] = True
            if c1.rank == "A":
                results["any_ace_pair"] = True
        
        # 检查玩家2手牌
        b1, b2 = self.bull_hole
        # 同花
        if b1.suit == b2.suit:
            results["any_suited_connector"] = True
        # 连牌
        elif abs(b1.value - b2.value) == 1 or (b1.value == 14 and b2.value == 2) or (b1.value == 2 and b2.value == 14):
            results["any_suited_connector"] = True
        # 对子
        if b1.rank == b2.rank:
            results["any_pair"] = True
            if b1.rank == "A":
                results["any_ace_pair"] = True
        
        return results
    
    def get_winner_hand_type(self, cowboy_eval, bull_eval):
        """确定赢家的牌型"""
        # 比较牌力确定赢家
        if cowboy_eval > bull_eval:
            winner_eval = cowboy_eval
        elif bull_eval > cowboy_eval:
            winner_eval = bull_eval
        else:
            # 相同牌型比较具体牌值
            for i in range(len(cowboy_eval[1])):
                if cowboy_eval[1][i] > bull_eval[1][i]:
                    winner_eval = cowboy_eval
                    break
                elif bull_eval[1][i] > cowboy_eval[1][i]:
                    winner_eval = bull_eval
                    break
            else:
                winner_eval = cowboy_eval  # or bull_eval，两者相同
                hand_rank = winner_eval[0]
                if hand_rank in [9, 8, 7]:      # 皇家同花顺、同花顺、四条
                    return "four_kind_flush", winner_eval
                elif hand_rank == 6:            # 葫芦
                    return "full_house", winner_eval
                elif hand_rank in [5, 4, 3]:     # 同花、顺子、三条
                    return "three_kind_straight", winner_eval
                elif hand_rank == 2:            # 两对
                    return "two_pair", winner_eval
                elif hand_rank in [1, 0]:       # 对子、高牌
                    return "high_card", winner_eval
        
        # 映射到我们的下注类别
        hand_rank = winner_eval[0]
        if hand_rank in [9, 8, 7]:  # 皇家同花顺、同花顺、四条
            return "four_kind_flush", winner_eval
        elif hand_rank == 6:  # 葫芦
            return "full_house", winner_eval
        elif hand_rank in [5, 4, 3]:  # 同花、顺子、三条
            return "three_kind_straight", winner_eval
        elif hand_rank == 2:  # 两对 
            return "two_pair", winner_eval
        elif hand_rank in [1, 0]:  # 对子、高牌
            return "high_card", winner_eval


    @property
    def hands(self):
        return {'Player1': self.cowboy_hole, 'Player2': self.bull_hole}

    @property
    def public_cards(self):
        return self.community_cards

    def pool(self, side):
        return self.hands[side] + self.public_cards

    def lock_bets(self, bets, balance):
        if self.stage != 'betting':
            raise ValueError('当前不在下注阶段。')
        if set(bets) - set(BET_PAYOUT):
            raise ValueError('未知下注项目。')
        if not math.isfinite(float(balance)) or balance < 0:
            raise ValueError('余额无效。')
        prepared = {}
        for kind in BET_PAYOUT:
            value = float(bets.get(kind, 0))
            if not math.isfinite(value) or value < 0 or value > BET_LIMITS[kind]:
                raise ValueError(f'{BET_LABELS[kind]}须为 0 至 ${BET_LIMITS[kind]:,} 的有限金额。')
            prepared[kind] = money(value)
        total = money(sum(prepared.values()))
        if total > money(balance):
            raise ValueError('下注总额超过余额。')
        self.bets, self.stage = prepared, 'showdown'
        return total

    def settle(self):
        if self.settlement is not None:
            return self.settlement
        if self.stage != 'showdown':
            raise ValueError('请先完成下注和开牌。')
        cowboy_eval, cowboy_best, bull_eval, bull_best = self.evaluate_hands()
        winner = ('cowboy' if cowboy_eval > bull_eval else
                  'bull' if bull_eval > cowboy_eval else 'tie')
        combinations_hit = self.check_hand_combinations()
        category, _ = self.get_winner_hand_type(cowboy_eval, bull_eval)
        hit_bets = {kind: False for kind in BET_PAYOUT}
        hit_bets[{'cowboy': 'cowboy_win', 'bull': 'bull_win', 'tie': 'tie'}[winner]] = True
        hit_bets.update(combinations_hit)
        hit_bets[category] = True
        details = {
            kind: money(Decimal(str(self.bets[kind])) *
                        (Decimal('1') + Decimal(str(BET_PAYOUT[kind])))) if hit_bets[kind] else 0.0
            for kind in BET_PAYOUT
        }
        self.settlement = dict(
            winner=winner, winner_hand_type=category, hit_bets=hit_bets,
            hand_combinations=combinations_hit, details=details,
            returned=money(sum(details.values())), total_bet=money(sum(self.bets.values())),
            evaluations={'Player1': cowboy_eval, 'Player2': bull_eval},
            best_hands={'Player1': cowboy_best, 'Player2': bull_best},
        )
        self.stage = 'settled'
        return self.settlement


def save_auto_history(game, username):
    """UTH-style cumulative statistics and the latest 50 completed rounds."""
    folder = os.path.join(project_root(), 'A_Logs', 'Json')
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, 'Auto_Texas_Holdem.json')
    data = {'history_record': {'cowboy_win': 0, 'bull_win': 0, 'tie': 0, 'game': 0}, 'history': []}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict) or not isinstance(loaded.get('history'), list):
            raise ValueError('Auto 历史记录格式无效，原记录未被覆盖。')
        data['history'] = loaded['history']
        data['history_record'].update(loaded.get('history_record', {}))
    result = game.settlement
    if result is None:
        raise ValueError('不能记录未结算牌局。')
    stats = data['history_record']
    stats['game'] += 1
    stats[{'cowboy': 'cowboy_win', 'bull': 'bull_win', 'tie': 'tie'}[result['winner']]] += 1
    data['history'].append(dict(
        game_id=stats['game'], timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
        username=username, deck_order=[str(c) for c in game.deck.full_deck],
        cut_position=game.deck.cut_position,
        player1_cards=[str(c) for c in game.cowboy_hole],
        player2_cards=[str(c) for c in game.bull_hole],
        community_cards=[str(c) for c in game.community_cards],
        bets=dict(game.bets), result={key: result[key] for key in (
            'winner', 'winner_hand_type', 'hit_bets', 'details', 'returned', 'total_bet')},
    ))
    data['history'] = data['history'][-50:]
    # Never truncate the existing record if serialization or a write fails.
    import tempfile
    descriptor, temporary = tempfile.mkstemp(prefix='.auto_holdem_', suffix='.json', dir=folder)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=4)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class TexasHoldemGUI(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    CARD_WIDTH, CARD_HEIGHT = 80, 112
    DEAL_CARD_MS = 224 / .85
    DEAL_MOVE_MS = (128 / .75) / .85
    BET_CHIP_RADIUS = 16 * 4 / 3
    HOUSE_CHIP_POS = (575, 43)
    TABLE_GREEN = '#4b1e22'
    ZONE_COLORS = {'Player1': '#2A5541', 'Player2': '#204536'}
    PLAYER_HAND_BG = '#254C59'
    PLAYER_HAND_BETS = ('any_suited_connector', 'any_pair', 'any_ace_pair')
    SEAT_NAMES = {'Player1': '玩家1', 'Player2': '玩家2'}

    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.parent = parent
        self.username, self.balance = username, money(initial_balance)
        if not math.isfinite(self.balance) or self.balance < 0:
            raise ValueError('余额须为有限的非负数。')
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = TexasHoldemGame()
        self.bets = {kind: 0.0 for kind in BET_PAYOUT}
        self.last_bet, self.last_win = None, 0.0
        self.high_bet_mode, self.selected_chip = False, 10.0
        self._jobs, self._closing = set(), False
        self._credited = self._return_persisted = self._crediting = False
        self._restart_job = self._restart_deadline = None
        self._bet_job = self._bet_deadline = None
        self._start_requested = False
        self._settlement_started = False
        self._motion_count = self._chip_serial = 0
        self._game_instruction_dialog = None
        self.last_round_snapshot = None
        self._history_available = False
        self.visual_chips = {}
        self._face_photos, self._pil_cards, self._flip_photos = {}, {}, {}
        self.card_items, self.bet_spots = {}, {}
        self._load_assets()
        self._create_widgets()
        self._refresh()
        self.bind('<Configure>', self._center_table, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')

    @property
    def game_in_progress(self):
        return self.game.stage not in ('betting', 'dealing') or self._motion_count > 0


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
        base = os.path.join(project_root(), 'A_Tools', 'Card', folder)
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


    def select_chip(self, amount):
        if self.game.stage == 'betting':
            self.selected_chip = amount
            self._draw_chips()


    def _status(self, message):
        # 记录阶段供调试，不在筹码下方绘制说明文字。
        self.current_status=message


    def _rounded_rectangle(self, x0, y0, x1, y1, radius, **options):
        return self.canvas.create_polygon(
            x0+radius, y0, x1-radius, y0, x1, y0, x1, y0+radius,
            x1, y1-radius, x1, y1, x1-radius, y1, x0+radius, y1,
            x0, y1, x0, y1-radius, x0, y0+radius, x0, y0,
            smooth=True, splinesteps=24, **options)


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
        if abs(value)>=1000:return TexasHoldemGUI._compact(value)
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
        """本金留位，盈利派至左上；输注立即飞向统一庄家收筹码点，平局不动。"""
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
        remaining=min(30.0,max(0,self._restart_deadline-time.monotonic()))
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
            key=self._card_image_key(card)
            original=(snapshot['images'].get(key) or snapshot['images'].get((card.suit,card.rank))
                or self.original_images.get(key) or self.original_images['back'])
            small_images[i]=ImageTk.PhotoImage(original.resize((60,90),Image.Resampling.LANCZOS),master=win)
        win._card_images=small_images
        for row in range(math.ceil(len(snapshot['full_deck'])/9)):
            row_frame=tk.Frame(card_frame,bg='#f0f0f0');row_frame.pack(fill=tk.X)
            for col in range(9):
                idx=row*9+col
                if idx>=len(snapshot['full_deck']):break
                container=tk.Frame(row_frame,bg='#f0f0f0');container.grid(row=0,column=col,padx=5)
                bg='light blue' if idx==cut_pos else '#f0f0f0'
                tk.Label(container,image=small_images[idx],bg=bg,borderwidth=1,relief='solid').pack()
                tk.Label(container,text=str(idx+1),bg=bg,font=('Arial',9)).pack()
        content_frame.update_idletasks();canvas.configure(scrollregion=canvas.bbox('all'))


    def card_size(self, side):
        return self.CARD_WIDTH,self.CARD_HEIGHT


    def _fade_card_item(self, item, source):
        # 用alpha淡化，不破坏牌面原图，也不把透明PNG的边缘铺成白底。
        faded = source.convert('RGBA').copy()
        faded.putalpha(faded.getchannel('A').point(lambda value:round(value*.45)))
        photo = ImageTk.PhotoImage(faded,master=self)
        self._faded_photos[item] = photo
        self.canvas.itemconfigure(item,image=photo)


    def _center_table(self, event=None):
        # Keep the original 1150×750 composition centered when embedded.
        self.canvas.place(x=max(0, (self.winfo_width()-self.WIDTH)//2),
                          y=max(0, (self.winfo_height()-self.HEIGHT)//2),
                          width=self.WIDTH, height=self.HEIGHT)


    @staticmethod
    def _card_image_key(card):
        return card.suit, card.rank


    def _apply_hand_usage(self, owner):
        """只淡化当前查看者未采用的牌，其他手牌恢复原有不透明度。"""
        used = self._hand_usage_keys.get(owner, set())
        for key, item in self.card_items.items():
            faded = key[0] in (owner, 'Public') and key not in used
            photos = self._faded_photos if faded else self._settled_card_photos
            self.canvas.itemconfigure(item, image=photos[item])
        self._usage_owner = owner


    def _on_hand_usage_hover(self, event=None):
        if (self.game.settlement is None or not self._hand_usage_keys
                or self.game.stage not in ('settled', 'settling', 'await_restart')):
            return
        current = set(self.canvas.find_withtag('current'))
        seat = next((side for (side, _), item in self.card_items.items()
                     if item in current and side in self.game.SEATS
                     and self.game.hands[side]), None)
        owner = seat or self._default_usage_owner
        if owner != self._usage_owner:
            self._apply_hand_usage(owner)


    def _on_hand_usage_leave(self, event=None):
        if (self.game.settlement is not None and self._hand_usage_keys
                and self.game.stage in ('settled', 'settling', 'await_restart')
                and self._usage_owner != self._default_usage_owner):
            self._apply_hand_usage(self._default_usage_owner)


    def _persist_balance(self):
        try:
            if self.username and self.username != 'Guest':
                update_balance_in_json(self.username, self.balance)
        except Exception as exc:
            messagebox.showerror('余额保存失败', str(exc), parent=self)
            return False
        if callable(self.on_balance_change):
            try:
                self.on_balance_change(float(self.balance))
            except Exception as exc:
                messagebox.showwarning('余额通知失败', str(exc), parent=self)
        return True

    def _cancel_betting_timer(self):
        if self._bet_job is not None:
            try:
                self.after_cancel(self._bet_job)
            except tk.TclError:
                pass
            self._jobs.discard(self._bet_job)
        self._bet_job = self._bet_deadline = None

    def _betting_tick(self):
        self._bet_job = None
        if self.game.stage != 'betting' or self._bet_deadline is None:
            return
        remaining = min(15.0, max(0, self._bet_deadline - time.monotonic()))
        self.canvas.itemconfigure(self.timer_item, text=f'{math.ceil(remaining):02d}',
                                  fill=RED if remaining <= 5 else '#FFE29A')
        if remaining <= 0:
            self.start_game()
        else:
            self._bet_job = self._schedule(max(1, min(1000, math.ceil(remaining * 1000))), self._betting_tick)

    def _apply_bet_layout(self, new_bets):
        previous, self.bets = self.bets, {k: money(new_bets.get(k, 0)) for k in BET_PAYOUT}
        transfers = []
        for kind in BET_PAYOUT:
            old, new = previous[kind], self.bets[kind]
            delta = money(new - old)
            if not delta:
                continue
            seat = BET_SEATS[kind]
            center = self.bet_spots[(seat, kind)]['center']
            if delta > 0:
                transfers.append(dict(amount=delta, start=self._rack_position(), target=center,
                    arrive=lambda s=seat, k=kind, a=new: self._set_visual(s, k, 'stake', a)))
            else:
                self._set_visual(seat, kind, 'stake', new)
                transfers.append(dict(amount=-delta, start=center, target=self._rack_position(), duration=440))
        self._run_chip_batch(transfers, self._refresh)
        self._refresh()

    def add_chip_to_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or self._start_requested:
            return
        old = self.bets[kind]
        remaining = max(0, money(self.balance - sum(self.bets.values())))
        amount = money(min(old + self.selected_chip, BET_LIMITS[kind], old + remaining))
        if amount <= old:
            messagebox.showwarning('无法下注', '已达项目上限或余额不足。', parent=self)
            return
        new = dict(self.bets)
        new[kind] = amount
        self._apply_bet_layout(new)

    def reset_single_bet(self, seat, kind):
        if self.game.stage != 'betting' or self._motion_count or self._start_requested:
            return
        new = dict(self.bets)
        new[kind] = 0.0
        self._apply_bet_layout(new)

    def reset_bets(self):
        if self.game.stage == 'betting' and not self._motion_count and not self._start_requested:
            self._apply_bet_layout({kind: 0.0 for kind in BET_PAYOUT})

    def apply_last_bet(self):
        if self.game.stage != 'betting' or self._motion_count or self._start_requested or not self.last_bet:
            return
        remaining, applied = self.balance, {}
        for kind in BET_PAYOUT:
            applied[kind] = money(min(self.last_bet.get(kind, 0), BET_LIMITS[kind], remaining))
            remaining = money(remaining - applied[kind])
        self._apply_bet_layout(applied)

    def toggle_high_bet_limits(self, event=None):
        # UTH's protected chip rack switch; Auto's limits remain authoritative.
        if self.game.stage != 'betting' or self._motion_count or self._start_requested:
            return
        if not self.high_bet_mode:
            password = simpledialog.askstring('大额筹码', '请输入密码：', parent=self)
            if password is None:
                return
            if password.strip() != time.strftime('%H%M'):
                messagebox.showerror('错误', '密码错误', parent=self)
                return
            if self.game.stage != 'betting' or self._start_requested:
                return
        self.high_bet_mode = not self.high_bet_mode
        self.selected_chip = 100 if self.high_bet_mode else 10
        self._draw_chips()
        self._refresh()

    def on_enter_key(self, event=None):
        if self.game.stage in ('await_restart', 'credit_pending'):
            self._return_all_chips()
        elif self.game.stage == 'betting':
            self.start_game()
        return 'break'

    def start_game(self):
        if self._closing or self.game.stage != 'betting':
            return
        # A timer may expire while a chip is moving. Freeze wagers immediately,
        # then wait for the existing animation before locking/charging once.
        if self._motion_count:
            if not self._start_requested:
                self._start_requested = True
                self._cancel_betting_timer()
                self._schedule(20, self._start_after_motion)
                self._refresh()
            return
        self._start_requested = True
        self._cancel_betting_timer()
        old_balance = self.balance
        try:
            charged = self.game.lock_bets(self.bets, self.balance)
        except (ValueError, TypeError, OverflowError) as exc:
            self._start_requested = False
            messagebox.showwarning('无法开始', str(exc), parent=self)
            self._bet_deadline = time.monotonic() + 15
            self._betting_tick()
            self._refresh()
            return
        self.balance = money(old_balance - charged)
        if not self._persist_balance():
            self.balance, self.game.stage = old_balance, 'betting'
            self._start_requested = False
            self._bet_deadline = time.monotonic() + 15
            self._betting_tick()
            self._refresh()
            return
        self.bets = dict(self.game.bets)
        if charged:
            self.last_bet = dict(self.bets)
        self._credited = self._return_persisted = self._settlement_started = False
        self._history_available = False
        self._close_card_sequence()
        self.canvas.itemconfigure(self.timer_item, text='00', fill=GOLD)
        self._refresh()
        self._schedule(300, self.reveal_all_cards)

    def _start_after_motion(self):
        if self.game.stage != 'betting':
            return
        if self._motion_count:
            self._schedule(20, self._start_after_motion)
        else:
            self.start_game()

    def _deal_next(self, sequence, offset):
        if offset == len(sequence):
            self._reveal_next([('Public', 0)], 0, self.begin_betting_phase)
            return
        side, index = sequence[offset]
        x, y = self.card_position(side, index)
        photo = self._public_photos['back'] if side == 'Public' else self._face_photos['back']
        item = self.canvas.create_image(575, 52, image=photo, anchor='nw', tags='cards')
        self.card_items[(side, index)] = item
        def move(step=0):
            fraction = step / 6
            self.canvas.coords(item, 575 + (x - 575) * fraction, 52 + (y - 52) * fraction)
            if step < 6:
                self._schedule(round(self.DEAL_MOVE_MS * (step + 1) / 6) -
                               round(self.DEAL_MOVE_MS * step / 6), move, step + 1)
            else:
                self._schedule(round(self.DEAL_CARD_MS) - round(self.DEAL_MOVE_MS),
                               self._deal_next, sequence, offset + 1)
        move()

    def _reveal_next(self, sequence, offset, complete):
        if offset == len(sequence):
            complete()
            return
        side, index = sequence[offset]
        hand = self.game.public_cards if side == 'Public' else self.game.hands[side]
        card, item = hand[index], self.card_items[(side, index)]
        x, y = self.card_position(side, index)
        width, height = self.card_size(side)
        def flip(step=0):
            narrow = max(1, round(width * abs(1 - step / 5)))
            source = self._pil_cards['back' if step < 5 else self._card_image_key(card)]
            photo = ImageTk.PhotoImage(source.resize((narrow, height), Image.Resampling.LANCZOS), master=self)
            self._flip_photos[item] = photo
            self.canvas.itemconfigure(item, image=photo)
            self.canvas.coords(item, x + (width - narrow) / 2, y)
            if step < 10:
                self._schedule(32, flip, step + 1)
            else:
                photos = self._public_photos if side == 'Public' else self._face_photos
                self.canvas.itemconfigure(item, image=photos[self._card_image_key(card)])
                self._flip_photos.pop(item, None)
                revealed = 'community' if side == 'Public' else 'cowboy' if side == 'Player1' else 'bull'
                self.game.cards_revealed[revealed][index] = True
                self._reveal_next(sequence, offset + 1, complete)
        flip()

    def begin_betting_phase(self):
        if self._closing or self.game.stage != 'dealing':
            return
        self.game.stage = 'betting'
        self._start_requested = False
        self._revealed_public = 1
        self._bet_deadline = time.monotonic() + 15
        self._refresh()
        self._betting_tick()

    def reveal_all_cards(self):
        if self.game.stage != 'showdown':
            return
        holes = [(seat, index) for seat in self.game.SEATS for index in range(2)]
        self._reveal_next(holes, 0, lambda: self._schedule(220,
            self._reveal_next, [('Public', i) for i in range(1, 5)], 0, self._all_revealed))

    def _all_revealed(self):
        self._revealed_public = 5
        self._update_visible_titles()
        self._schedule(1000, self._settle)

    def _update_visible_titles(self):
        all_open = all(all(flags) for flags in self.game.cards_revealed.values())
        for side, item in self.title_items.items():
            caption = self.SEAT_NAMES[side]
            if all_open:
                caption += ' - ' + HAND_RANK_NAMES[find_best_5(self.game.pool(side))[0][0]]
            self.canvas.itemconfigure(item, text=caption)

    def _settle(self):
        if self._settlement_started or self.game.stage != 'showdown':
            return
        self._settlement_started = True
        result = self.game.settle()
        self.game.stage, self.last_win = 'settling', result['returned']
        self._update_visible_titles()
        self._render_hand_usage()
        transfers = []
        for kind in BET_PAYOUT:
            seat = BET_SEATS[kind]
            transfers.extend(self._outcome_transfers(seat, kind, self.game.bets[kind], result['details'][kind]))
            self.canvas.itemconfigure(self.bet_spots[(seat, kind)]['border'],
                outline=GOLD if result['hit_bets'][kind] else TEXT,
                width=4 if result['hit_bets'][kind] else 2)
        try:
            save_auto_history(self.game, self.username)
        except Exception as exc:
            messagebox.showerror('历史记录保存失败', str(exc), parent=self)
        self._refresh()
        self._run_chip_batch(transfers, self._await_next_round)

    def _await_next_round(self):
        if self.game.stage != 'settling':
            return
        self.game.stage = 'await_restart'
        deck = self.game.deck
        self.last_round_snapshot = dict(full_deck=tuple(deck.full_deck), start_pos=deck.start_pos,
            images={key: im.copy() for key, im in self.original_images.items()})
        self._history_available = True
        self._cancel_restart_timer()
        self._restart_deadline = time.monotonic() + 30
        self._refresh()
        self._restart_tick()

    def _finish_round(self):
        if self.game.stage != 'sweeping':
            return
        self._prepare_round()

    def _prepare_round(self, reset_engine=True):
        self._cancel_betting_timer()
        self._cancel_restart_timer()
        self._close_card_sequence()
        if reset_engine:
            self.game.reset_game()
        self.game.deal_initial()
        self.game.stage = 'dealing'
        self.bets = {kind: 0.0 for kind in BET_PAYOUT}
        self.visual_chips.clear()
        self.canvas.delete('cards')
        self.canvas.delete('hand_usage')
        self.canvas.delete('returned_chips')
        self.card_items.clear()
        self._flip_photos.clear()
        self._faded_photos.clear()
        self._settled_card_photos.clear()
        self._hand_usage_keys.clear()
        self._usage_owner = None
        self._history_available = False
        self._start_requested = self._settlement_started = False
        self._credited = self._return_persisted = False
        self._revealed_public = 0
        self.canvas.itemconfigure(self.timer_item, text='--', fill=GOLD)
        for spot in self.bet_spots.values():
            self.canvas.itemconfigure(spot['border'], outline=TEXT, width=2)
        self._load_assets()
        self._update_visible_titles()
        self._refresh()
        self._schedule(150, self._deal_next, self.game.deal_sequence, 0)

    def reset_game(self, auto_reset=False):
        # Public entry point used by the existing parent launcher.
        if self.game.stage == 'betting' and not self.card_items and not self._jobs:
            self._prepare_round(reset_engine=False)
        elif self.game.stage == 'betting':
            self.reset_bets()

    def on_close(self):
        if self._closing or self._crediting:
            return
        settled = self.game.settlement is not None
        if self.game.stage == 'showdown':
            messagebox.showinfo('牌局进行中', '请等待已下注牌局开牌和结算。', parent=self)
            return
        if settled:
            if not self._credit_round_return():
                return
        elif not self._persist_balance():
            return
        self._closing = True
        self._cancel_betting_timer()
        self._cancel_restart_timer()
        self._cancel_jobs()
        self._unbind_enter()
        for attr in ('_game_instruction_dialog', '_sequence_window'):
            window = getattr(self, attr, None)
            if window is not None:
                try:
                    window.destroy()
                except tk.TclError:
                    pass
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.destroy()

    def _render_hand_usage(self):
        result = self.game.settlement
        if result is None:
            return
        self._hand_usage_keys.clear()
        for owner in self.game.SEATS:
            used = set()
            for card in result['best_hands'][owner]:
                public_index = next((i for i, c in enumerate(self.game.public_cards) if c is card), None)
                if public_index is not None:
                    used.add(('Public', public_index))
                else:
                    used.add((owner, next(i for i, c in enumerate(self.game.hands[owner]) if c is card)))
            self._hand_usage_keys[owner] = used
        self._default_usage_owner = 'Player2' if result['winner'] == 'bull' else 'Player1'
        self._faded_photos.clear()
        self._settled_card_photos.clear()
        for (side, index), item in self.card_items.items():
            hand = self.game.public_cards if side == 'Public' else self.game.hands[side]
            source = self._pil_cards[self._card_image_key(hand[index])].convert('RGBA').resize(
                self.card_size(side), Image.Resampling.LANCZOS)
            self._settled_card_photos[item] = ImageTk.PhotoImage(source, master=self)
            self._fade_card_item(item, source)
        self._usage_owner = None
        self._apply_hand_usage(self._default_usage_owner)

    def _draw_limit_table(self):
        c = self.canvas
        x0, x1, y0 = 30, 349, 75
        c.create_rectangle(x0, y0, x1, 181, fill=ROOT_BG, outline=GOLD, width=2, tags='limits')
        c.create_rectangle(x0, y0, x1, y0 + 29, fill=ROOT_BG, outline=GOLD, tags='limits')
        self._text((x0 + x1) / 2, y0 + 14, '下注上限 · 点击切换筹码', 12, PANEL_BG, tags='limits')
        for col, (title, limit) in enumerate((('双方胜注', 50000), ('平局', 10000), ('其他各项', 25000))):
            left, right = x0 + col * (x1 - x0) / 3, x0 + (col + 1) * (x1 - x0) / 3
            c.create_rectangle(left, y0 + 29, right, y0 + 66, outline='#77906B', tags='limits')
            c.create_rectangle(left, y0 + 66, right, 181, outline='#77906B', tags='limits')
            self._text((left + right) / 2, y0 + 47, title, 11, PANEL_BG, tags='limits')
            self._text((left + right) / 2, y0 + 86, f'${limit:,}', 12, GOLD, tags='limits')
        c.tag_bind('limits', '<Button-1>', self.toggle_high_bet_limits)
        c.tag_bind('limits', '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind('limits', '<Leave>', lambda _e: c.configure(cursor=''))

    def _draw_countdown_panel(self):
        # One timer fills the former return display and the instructions below.
        self.canvas.create_rectangle(810, 75, 1128, 309, fill=ROOT_BG, outline=GOLD, width=2)
        self._text(969, 107, '下注倒计时', 20, PANEL_BG)
        self.timer_item = self._text(969, 189, '--', 76, '#FFE29A')
        self._text(969, 274, '秒', 17, PANEL_BG)

    def _draw_centered_label(self, x, y, label, radius, font_size, tag):
        """Center the complete label, including intentional two-line names."""
        while True:
            metrics = tkfont.Font(root=self, font=('Arial', font_size, 'bold'))
            widest = max((metrics.measure(line) for line in label.splitlines()), default=0)
            if widest <= radius * 2 - 18 or font_size <= 9:
                break
            font_size -= 1
        return (self._text(x, y, label, font_size, TEXT, justify='center', tags=tag),)

    def _draw_bet_spot(self, kind, x, y, label, radius=55, font_size=14):
        seat, c = BET_SEATS[kind], self.canvas
        tag = 'spot_' + seat + '_' + kind
        background = self.PLAYER_HAND_BG if kind in self.PLAYER_HAND_BETS else self.ZONE_COLORS[seat]
        border = c.create_oval(x - radius, y - radius, x + radius, y + radius,
            fill=background, outline=TEXT, width=2, tags=tag)
        labels = self._draw_centered_label(x, y, label, radius, font_size, tag)
        odds = self._text(x, y + radius - 13, f'{BET_PAYOUT[kind]:g} : 1', 12, GOLD, tags=tag)
        self.bet_spots[(seat, kind)] = dict(tag=tag, center=(x, y), radius=radius,
            border=border, labels=labels, odds=odds)
        c.tag_bind(tag, '<Button-1>', lambda _e, s=seat, k=kind: self.add_chip_to_bet(s, k))
        c.tag_bind(tag, '<Button-3>', lambda _e, s=seat, k=kind: self.reset_single_bet(s, k))
        c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))

    def _draw_bottom_controls(self):
        c = self.canvas
        c.create_rectangle(0, 625, 1150, 748, fill=ROOT_BG, outline='#6C7850', width=2, tags='controls')
        self.balance_item = self._text(10, 665, '', 16, TEXT, anchor='w', tags='controls')
        self.total_item = self._text(10, 710, '', 16, TEXT, anchor='w', tags='controls')
        self.clear_button = self.create_control_button(278, 650, 344, 704, '清除', self.reset_bets,
            '#9B403A', font_size=11, draw_shadow=False)
        self._draw_chips()
        self.info_button = self.create_control_button(810, 650, 855, 695, '?', self.show_game_instructions,
            DARK_BLUE, font_size=17, draw_shadow=False)
        self.repeat_button = self.create_control_button(862, 638, 1000, 708, '重复下注', self.apply_last_bet,
            '#536A43', font_size=11, draw_shadow=False)
        self.start_button = self.create_control_button(1012, 628, 1138, 720, '开牌', self.start_game,
            HEADER_BG, fg=TITLE_FG, font_size=14, subtext='Enter', subtext_font_size=10, draw_shadow=False)
        self.restart_button = self.create_control_button(862, 638, 1138, 708, '再来一局(30)', self._return_all_chips,
            HEADER_BG, fg=TITLE_FG, font_size=17, draw_shadow=False)
        c.tag_bind(self.restart_button, '<Button-3>', self._inspect_completed_round)
        c.itemconfigure(self.restart_button, state='hidden')
        self._enter_binding = self.winfo_toplevel().bind('<Return>', self.on_enter_key, add='+')

    def _create_widgets(self):
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT, bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self.control_buttons = {}
        self._faded_photos, self._settled_card_photos = {}, {}
        self._hand_usage_keys, self._usage_owner = {}, None
        self._default_usage_owner = 'Player1'
        self._revealed_public = 0
        self.canvas.bind('<Motion>', self._on_hand_usage_hover, add='+')
        self.canvas.bind('<Leave>', self._on_hand_usage_leave, add='+')
        c = self.canvas
        self._text(187, 44, '自动德州扑克', 16, GOLD)
        self._text(957, 44, 'Auto Texas Hold’em', 14, GOLD)
        self._draw_limit_table()
        # Both players occupy the upper-center area that previously held the timer.
        c.create_rectangle(356, 10, 794, 165, fill=self.TABLE_GREEN, outline='')
        self.title_items = {
            'Player1': self._text(449, 24, '玩家1', 14, PANEL_BG),
            'Player2': self._text(701, 24, '玩家2', 14, PANEL_BG),
        }
        self._text(575, 100, 'VS', 18, GOLD)
        c.create_rectangle(22, 191, 1128, 309, fill=ROOT_BG, outline='#65784B')
        c.create_line(25, 192, 1125, 192, fill='#E0C879', width=2)
        c.create_line(25, 308, 1125, 308, fill='#0C241B', width=2)
        self._text(182, 229, '先翻首张公共牌\n再开放 15 秒下注', 17, GOLD, justify='center')
        self.street_item = self._text(182, 279, '发牌中', 14, PANEL_BG)
        c.create_polygon(366, 173, 784, 173, 798, 173, 798, 187, 798, 287, 798, 301,
            784, 301, 366, 301, 352, 301, 352, 287, 352, 187, 352, 173,
            smooth=True, splinesteps=16, fill='#234838', outline='#667B55', width=1)
        self._draw_countdown_panel()
        c.create_rectangle(22, 316, 566, 469, fill=self.ZONE_COLORS['Player1'], outline='')
        c.create_rectangle(22, 469, 566, 617, fill=self.PLAYER_HAND_BG, outline='')
        c.create_line(22, 469, 566, 469, fill='#72816B', width=1)
        c.create_rectangle(582, 316, 1128, 617, fill=self.ZONE_COLORS['Player2'], outline='')
        self._text(294, 334, '头VS头', 17, GOLD)
        self._text(294, 481, '玩家手牌', 17, GOLD)
        self._text(855, 334, '获胜牌型', 17, GOLD)
        for kind, x, y, label in (
            ('cowboy_win', 126, 412, '玩家1胜'), ('tie', 294, 412, '平局'),
            ('bull_win', 462, 412, '玩家2胜'),
            ('any_suited_connector', 126, 552, '同花 / 连牌'),
            ('any_pair', 294, 552, '任意对子'), ('any_ace_pair', 462, 552, '任意AA'),
            ('high_card', 686, 412, '高牌 / 对子'), ('two_pair', 855, 412, '两对'),
            ('three_kind_straight', 1024, 412, '三条\n顺子 / 同花'),
            ('full_house', 770, 552, '葫芦'), ('four_kind_flush', 940, 552, '四条 / 同花顺\n皇家同花顺')):
            self._draw_bet_spot(kind, x, y, label)
        self._draw_bottom_controls()
        for side in (*self.game.SEATS, 'Public'):
            for index in range(5 if side == 'Public' else 2):
                x, y = self.card_position(side, index)
                width, height = self.card_size(side)
                c.create_rectangle(x, y, x + width, y + height,
                    outline='#B59C6A' if side == 'Public' else '#7B9374', dash=(3, 3), tags='card_slots')

    def card_position(self, side, index):
        if side == 'Public':
            return 363 + index * 86, 181
        return (365 if side == 'Player1' else 617) + index * 88, 42

    def _refresh(self):
        c = self.canvas
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        total = money(sum(self.bets.values()))
        c.itemconfigure(self.total_item, text=f'本局下注: ${total:,.2f}' if total else f'上局返还: ${self.last_win:,.2f}')
        self._render_chips()
        betting = self.game.stage == 'betting' and not self._motion_count and not self._start_requested
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(self.last_bet))
        self.set_control_button_state(self.start_button, betting)
        restarting = self.game.stage in ('await_restart', 'returning', 'credit_pending', 'sweeping')
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self.set_control_button_state(self.restart_button, self.game.stage in ('await_restart', 'credit_pending'))
        if self.game.settlement is not None:
            result = {'cowboy': '玩家1胜', 'bull': '玩家2胜', 'tie': '平局'}[self.game.settlement['winner']]
            caption = f'{result} · 已结算'
        else:
            caption = {'dealing': '发牌中', 'betting': '下注中', 'showdown': '开牌中'}.get(self.game.stage, '准备中')
        c.itemconfigure(self.street_item, text=caption)
        self._status(caption)


    def _instruction_pages(self):
        payout_rows = [[BET_LABELS[k], f'{BET_PAYOUT[k]:g} : 1', f'${BET_LIMITS[k]:,}'] for k in BET_PAYOUT]
        return [
            ('游戏流程', 'Auto 原玩法 · UTH 风格牌桌', [
                ['每局顺序', '', [
                    ('发牌', '先发五张公共牌，再依次发玩家1第1张、玩家2第1张、玩家1第2张、玩家2第2张，全部背面朝上。'),
                    ('下注', '只翻开首张公共牌，开放 15 秒下注；Enter 或开牌按钮可提前结束。到时即自动开牌，零下注亦可观看。'),
                    ('开牌', '先翻开两位玩家的手牌，再依次翻开其余四张公共牌，最后比较各自最佳五张。'),
                    ('结算', '赔率表示净盈利；命中项目返还本金加盈利。筹码返回筹码区后，返还额只入账一次。'),
                    ('下一局', '结算后可按 Enter 或再来一局；30 秒后自动继续。右键再来一局可查看上局牌序，并停止此倒计时。'),
                ], []],
            ]),
            ('下注 & 赔率', '11 项投注、原有赔率与独立上限。金额精确至分。', [
                ['投注表', '点击下注上限表可切换 UTH 大额筹码；各项目上限始终按下表执行。', [],
                    [('', ['投注项目', '净盈利赔率', '独立上限'], payout_rows)]],
                ['操作', '', [
                    ('下注', '先选筹码，左键点投注圈增加金额；右键清除该项。清除按钮清空全部，重复下注按上局金额回填并受余额、上限约束。'),
                    ('筹码', '普通筹码为 10、25、100、500、1,000、2,500；大额筹码沿用 UTH 的密码切换方式，启用密码为本机当前 HHMM。'),
                ], []],
            ]),
            ('获胜条件', '严格沿用 Auto 的判断方式。', [
                ['胜负与手牌组合', '', [], [('', ['项目', '判定条件'], [
                    ['玩家1胜 / 玩家2胜', '从各自两张手牌加五张公共牌选最佳五张；依牌型、牌点与踢脚比较。只有严格胜出才中奖。'],
                    ['平局', '双方最佳五张完全相同才中奖；双方胜注不退本金。'],
                    ['同花 / 连牌', '任一方两张手牌同花，或点数相连即可（包含 A-2、A-K）。不是必须同时满足同花及连牌。'],
                    ['任意对子 / 任意 AA', '任一方两张手牌为对子 / AA 即命中；两方同时满足也只派一次。AA 可与任意对子同时命中。'],
                ])]],
                ['赢家牌型', '平局同样按共同牌型派彩；五组中仅命中一组。', [], [('', ['项目', '包含牌型'], [
                    ['高牌 / 对子', '高牌、一对'], ['两对', '两对'],
                    ['三条 / 顺子 / 同花', '三条、顺子、同花'], ['葫芦', '葫芦'],
                    ['四条 / 同花顺 / 皇家', '四条、同花顺、皇家同花顺'],
                ])]],
            ]),
            ('牌型 & 查阅', '牌型由高至低；结算后可检查双方采用的五张牌。', [
                ['牌型顺序', '', [], [('', ['等级', '牌型'], [[str(rank), HAND_RANK_NAMES[rank]] for rank in range(9, -1, -1)])]],
                ['查看牌局', '', [
                    ('最佳五张', '结算后默认显示赢家使用的牌；鼠标移到另一方手牌可查看该方用牌。未采用的牌会淡化，牌面保持透明边缘。'),
                    ('牌序', '右键再来一局，显示已结算牌局的 52 张原始牌序与切牌位置。当前未结算牌序不可查看。'),
                    ('历史', '沿用 UTH 的记录方式，累计统计胜负，并保留最近 50 局的牌序、下注与返还。'),
                ], []],
            ]),
        ]


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

        instruction_title = '自动德州扑克 · 玩法说明'
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


def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """Same launcher contract as the supplied Auto: embedded or standalone."""
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        page = TexasHoldemGUI(parent, actual_balance, actual_user,
            on_back=on_back, on_balance_change=on_balance_change)
        page.reset_game()
        return page
    root = tk.Tk()
    root.title('自动德州扑克')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    root.configure(bg=ROOT_BG)
    page = TexasHoldemGUI(root, actual_balance, actual_user, on_balance_change=on_balance_change)
    page.pack(fill='both', expand=True)
    page.reset_game()
    page.on_back = lambda final_balance: root.destroy()
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance


if __name__ == '__main__':
    final_balance = main()
