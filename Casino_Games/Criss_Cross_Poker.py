import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import secrets
import subprocess
import sys
import time
from collections import Counter

# =========================================================
# 纵横交叉扑克 (Criss Cross Poker) - V9
# =========================================================
ROOT_BG = "#1B3D31"
TEXT = "#ffffff"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
TABLE_PANEL = "#2a4a3c"

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {rank: value for value, rank in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    10: '皇家同花顺',
    9: '同花顺',
    8: '四条',
    7: '葫芦',
    6: '同花',
    5: '顺子',
    4: '三条',
    3: '两对',
    2: '对子J+',
    1: '对子10-',
    0: '高牌',
}

# 加注（横／纵／中）赔率。返回金额 = 本金 + 赔率利润。
MAIN_BET_PAYOUT = {
    10: 500,
    9: 100,
    8: 40,
    7: 12,
    6: 8,
    5: 5,
    4: 3,
    3: 2,
    2: 1,
}

# 五牌红利：只看五张公共牌，即使玩家弃牌仍独立结算。
FIVE_CARD_BONUS_PAYOUT = {
    10: 250,
    9: 100,
    8: 40,
    7: 15,
    6: 10,
    5: 6,
    4: 4,
    3: 3,
    2: 1,
    1: 1,
}

CARD_W = 100
CARD_H = 140

# V7：Middle 初始牌位下移，并恢复原始代码的透明牌角显示方式。
# 开局五张公共牌横排在 Middle；最终 0、1、4 组成横线，2、4、3 组成纵线。
MIDDLE_POSITIONS = {
    0: (0, 260),
    1: (100, 260),
    2: (200, 260),
    3: (300, 260),
    4: (400, 260),
}
HORIZONTAL_POSITIONS = {
    0: (90, 140),
    1: (310, 140),
    4: (200, 140),
}
VERTICAL_POSITIONS = {
    2: (200, 0),
    3: (200, 280),
    4: (200, 140),
}
PLAYER_POSITIONS = {
    0: (55, 10),
    1: (175, 10),
}


# =========================================================
# 用户余额文件
# =========================================================
def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')


def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def load_user_data():
    path = get_data_file_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception:
        return []


def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user.get('user_name') == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)


# =========================================================
# Progressive 文件（沿用原 Progressive_2.50 逻辑）
# =========================================================
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    default_jackpot = 271288.59
    if not os.path.exists(path):
        return True, default_jackpot
    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        for item in data:
            if item.get('Games') == 'Progressive_2.50':
                return False, float(item.get('jackpot', default_jackpot))
    except Exception:
        pass
    return True, default_jackpot


def save_jackpot(jackpot):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception:
            data = []

    found = False
    for item in data:
        if item.get('Games') == 'Progressive_2.50':
            item['jackpot'] = jackpot
            found = True
            break
    if not found:
        data.append({'Games': 'Progressive_2.50', 'jackpot': jackpot})

    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# =========================================================
# 历史记录
# =========================================================
def criss_cross_log_path():
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'A_Logs',
        'Json',
    )
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, 'Criss_Cross_Poker.json')


def save_criss_cross_history(
    deck,
    community_cards,
    player_cards,
    total_return,
    horizontal_eval,
    vertical_eval,
    five_bonus_eval,
    folded,
):
    path = criss_cross_log_path()
    data = {'history_record': {'game': 0, 'win': 0, 'fold': 0, 'lose': 0}, 'history': []}
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as file:
                loaded = json.load(file)
            if isinstance(loaded, dict):
                data['history_record'].update(loaded.get('history_record', {}))
                data['history'] = loaded.get('history', [])
        except Exception as exc:
            print(f'读取 Criss Cross 历史记录失败: {exc}')

    stats = data['history_record']
    stats['game'] = int(stats.get('game', 0)) + 1
    if folded:
        stats['fold'] = int(stats.get('fold', 0)) + 1
    elif horizontal_eval[0] >= 2 or vertical_eval[0] >= 2:
        stats['win'] = int(stats.get('win', 0)) + 1
    else:
        stats['lose'] = int(stats.get('lose', 0)) + 1

    next_id = max(
        (record.get('game_id', 0) for record in data['history'] if isinstance(record, dict)),
        default=0,
    ) + 1
    data['history'].append({
        'game_id': next_id,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'deck_order': [str(card) for card in deck.full_deck],
        'cut_position': deck.cut_position,
        'community_cards': [str(card) for card in community_cards],
        'player_cards': [str(card) for card in player_cards],
        'horizontal_hand': HAND_RANK_NAMES.get(horizontal_eval[0], '高牌'),
        'vertical_hand': HAND_RANK_NAMES.get(vertical_eval[0], '高牌'),
        'five_card_bonus_hand': HAND_RANK_NAMES.get(five_bonus_eval[0], '高牌'),
        'total_return': total_return,
        'folded': folded,
    })
    data['history'] = data['history'][-50:]

    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)


# =========================================================
# 扑克牌与牌堆
# =========================================================
class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]

    def __repr__(self):
        return f'{self.rank}{self.suit}'


class Deck:
    def __init__(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        try:
            result = subprocess.run(
                [sys.executable, shuffle_script, 'false', '1'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30,
            )
            shuffle_data = json.loads(result.stdout)
            if 'deck' not in shuffle_data or 'cut_position' not in shuffle_data:
                raise ValueError('Invalid shuffle data format')
            self.full_deck = [Card(item['suit'], item['rank']) for item in shuffle_data['deck']]
            self.cut_position = int(shuffle_data['cut_position'])
        except Exception as exc:
            print(f'Error calling shuffle.py: {exc}. Using fallback shuffle.')
            self.full_deck = [Card(suit, rank) for suit in SUITS for rank in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)

        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + index) % 52 for index in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[index] for index in self.indexes]

    def _secure_shuffle(self):
        for index in range(len(self.full_deck) - 1, 0, -1):
            other = secrets.randbelow(index + 1)
            self.full_deck[index], self.full_deck[other] = self.full_deck[other], self.full_deck[index]

    def deal(self, count=1):
        if self.pointer + count > len(self.indexes):
            raise RuntimeError('牌堆已没有足够的牌。')
        cards = [self.full_deck[self.indexes[self.pointer + offset]] for offset in range(count)]
        self.pointer += count
        return cards


# =========================================================
# 五张牌评估
# =========================================================
def evaluate_hand(cards):
    if len(cards) != 5:
        raise ValueError(f'evaluate_hand 需要正好 5 张牌，实际收到 {len(cards)} 张。')

    values = sorted((card.value for card in cards), reverse=True)
    counts = Counter(values)
    suits = [card.suit for card in cards]
    flush = len(set(suits)) == 1

    unique_values = sorted(set(values), reverse=True)
    if unique_values == [14, 5, 4, 3, 2]:
        straight_high = 5
    elif len(unique_values) == 5 and unique_values[0] - unique_values[4] == 4:
        straight_high = unique_values[0]
    else:
        straight_high = None

    if flush and straight_high:
        if straight_high == 14:
            return 10, [14, 13, 12, 11, 10]
        return 9, [straight_high]

    grouped = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    if grouped[0][1] == 4:
        quad = grouped[0][0]
        kicker = max(value for value in values if value != quad)
        return 8, [quad, kicker]

    triples = sorted((value for value, count in counts.items() if count == 3), reverse=True)
    pairs = sorted((value for value, count in counts.items() if count == 2), reverse=True)
    if triples and pairs:
        return 7, [triples[0], pairs[0]]

    if flush:
        return 6, values
    if straight_high:
        return 5, [straight_high]
    if triples:
        kickers = sorted((value for value in values if value != triples[0]), reverse=True)
        return 4, [triples[0]] + kickers
    if len(pairs) >= 2:
        kicker = max(value for value in values if value not in pairs[:2])
        return 3, [pairs[0], pairs[1], kicker]
    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((value for value in values if value != pair), reverse=True)
        if pair >= 11:
            return 2, [pair] + kickers
        # 所有 10 或以下对子统一显示为“对子10-”。
        # 主注仍不获胜；五牌红利是否赔付会另外检查对子点数是否至少为 6。
        return 1, [pair] + kickers
    return 0, values


def calculate_criss_cross_returns(
    *,
    ante_horizontal,
    ante_vertical,
    raise_horizontal,
    raise_vertical,
    raise_middle,
    five_card_bonus,
    horizontal_eval,
    vertical_eval,
    five_bonus_eval,
    folded,
):
    """纯规则函数：计算除 Progressive 以外的所有返还金额。"""
    details = {
        'ante_horizontal': 0.0,
        'ante_vertical': 0.0,
        'raise_horizontal': 0.0,
        'raise_vertical': 0.0,
        'raise_middle': 0.0,
        'five_card_bonus': 0.0,
    }

    if not folded:
        horizontal_rank = horizontal_eval[0]
        vertical_rank = vertical_eval[0]

        if horizontal_rank in MAIN_BET_PAYOUT:
            details['ante_horizontal'] = ante_horizontal * 2
            details['raise_horizontal'] = raise_horizontal * (1 + MAIN_BET_PAYOUT[horizontal_rank])

        if vertical_rank in MAIN_BET_PAYOUT:
            details['ante_vertical'] = ante_vertical * 2
            details['raise_vertical'] = raise_vertical * (1 + MAIN_BET_PAYOUT[vertical_rank])

        qualifying = [
            hand_eval
            for hand_eval in (horizontal_eval, vertical_eval)
            if hand_eval[0] in MAIN_BET_PAYOUT
        ]
        if qualifying:
            best_eval = max(qualifying)
            details['raise_middle'] = raise_middle * (1 + MAIN_BET_PAYOUT[best_eval[0]])

    five_bonus_rank = five_bonus_eval[0]
    if five_bonus_rank == 1:
        # “对子10-”只在对子点数为 6 至 10 时符合五牌红利 1:1。
        pair_value = five_bonus_eval[1][0] if five_bonus_eval[1] else 0
        if pair_value >= 6:
            details['five_card_bonus'] = five_card_bonus * (1 + FIVE_CARD_BONUS_PAYOUT[1])
    elif five_bonus_rank in FIVE_CARD_BONUS_PAYOUT:
        details['five_card_bonus'] = five_card_bonus * (1 + FIVE_CARD_BONUS_PAYOUT[five_bonus_rank])

    return sum(details.values()), details


# =========================================================
# 游戏状态
# =========================================================
class CrissCrossPokerGame:
    def __init__(self):
        self.progressive_amount = load_jackpot()[1]
        self.min_progressive = 271288.59
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.ante_horizontal = 0
        self.ante_vertical = 0
        self.five_card_bonus = 0
        self.raise_horizontal = 0
        self.raise_vertical = 0
        self.raise_middle = 0
        self.jackpot_bet = 0
        self.stage = 'pre_flop'
        self.folded = False
        self.cards_revealed = {
            'player': [False, False],
            'community': [False, False, False, False, False],
        }
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence

    def deal_initial(self):
        # 按需求：先把 5 张公共牌派到 Middle，再派玩家 2 张牌。
        self.community_cards = self.deck.deal(5)
        self.player_hole = self.deck.deal(2)

    def horizontal_cards(self):
        return self.player_hole + [
            self.community_cards[0],
            self.community_cards[1],
            self.community_cards[4],
        ]

    def vertical_cards(self):
        return self.player_hole + [
            self.community_cards[2],
            self.community_cards[3],
            self.community_cards[4],
        ]

    def progressive_cards(self):
        # Progressive 规则不变，但牌组改为玩家 2 张 + 公共牌 0、1、2。
        return self.player_hole + self.community_cards[0:3]

    def evaluate_horizontal(self):
        return evaluate_hand(self.horizontal_cards())

    def evaluate_vertical(self):
        return evaluate_hand(self.vertical_cards())

    def evaluate_five_card_bonus(self):
        return evaluate_hand(self.community_cards)


# =========================================================
# GUI
# =========================================================
class CrissCrossPokerGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.username = username
        self.balance = float(initial_balance)
        self.game = CrissCrossPokerGame()

        self.card_images = {}
        self.original_images = {}
        self.back_image = None
        self.current_poker_folder = None
        self.animation_queue = []
        self.animation_in_progress = False
        self.active_card_labels = []
        self.community_card_labels = {}
        self.player_card_labels = {}
        self._temp_flip_images = {}

        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.bet_widgets = {}
        self.last_bet = None
        self.last_win = 0.0
        self.repeat_bet_btn = None
        self.auto_reset_timer = None
        self.last_jackpot_state = 0
        self.game_in_progress = False
        self.high_bet_mode = False

        self.jackpot_bet_var = tk.IntVar(value=0)
        self.ante_horizontal_var = tk.StringVar(value='0')
        self.ante_vertical_var = tk.StringVar(value='0')
        self.five_card_bonus_var = tk.StringVar(value='0')
        self.raise_horizontal_var = tk.StringVar(value='0')
        self.raise_vertical_var = tk.StringVar(value='0')
        self.raise_middle_var = tk.StringVar(value='0')

        self._load_assets()
        self._create_widgets()

    # ---------- 生命周期 ----------
    def on_close(self):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
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

    # ---------- 牌图 ----------
    def _load_assets(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if self.current_poker_folder is None:
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        suit_mapping = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club'}
        self.card_images = {}
        self.original_images = {}

        # 与原始 Mississippi Stud 代码一致：直接保留 PNG 原始模式。
        # 不转换为 RGB，避免透明圆角被白色背景填充。
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_original = Image.open(back_path)
        except Exception:
            back_original = Image.new('RGB', (CARD_W, CARD_H), '#111111')
            draw = ImageDraw.Draw(back_original)
            draw.rectangle((5, 5, CARD_W - 6, CARD_H - 6), outline='white', width=2)
        self.original_images['back'] = back_original
        self.back_image = ImageTk.PhotoImage(back_original.resize((CARD_W, CARD_H)))

        for suit in SUITS:
            for rank in RANKS:
                filename = f"{suit_mapping[suit]}{rank}.png"
                path = os.path.join(card_dir, filename)
                try:
                    if not os.path.exists(path):
                        raise FileNotFoundError(path)
                    original = Image.open(path)
                except Exception:
                    original = self._make_placeholder_card(suit, rank)
                self.original_images[(suit, rank)] = original
                self.card_images[(suit, rank)] = ImageTk.PhotoImage(
                    original.resize((CARD_W, CARD_H))
                )

    def _make_placeholder_card(self, suit, rank):
        image = Image.new('RGB', (CARD_W, CARD_H), 'white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((1, 1, CARD_W - 2, CARD_H - 2), outline='black', width=2)
        try:
            font = ImageFont.truetype('arial.ttf', 18)
        except Exception:
            font = ImageFont.load_default()
        color = 'red' if suit in ('♥', '♦') else 'black'
        draw.text((8, 8), f'{rank}{suit}', fill=color, font=font)
        return image

    # ---------- UI ----------
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # =====================================================
        # 左侧牌桌：沿用原版 Mississippi Stud 的整体布局。
        # 唯一结构性变化是公共牌区域改为十字形牌位。
        # =====================================================
        table_canvas = tk.Canvas(main_frame, bg=ROOT_BG, highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_canvas.create_rectangle(0, 0, 725, 720, fill=ROOT_BG, outline=GOLD, width=5)

        community_frame = tk.Frame(table_canvas, bg=TABLE_PANEL, bd=2, relief=tk.RAISED)
        community_frame.place(x=105, y=5, width=520, height=470)
        self.community_label = tk.Label(
            community_frame,
            text='公共牌',
            font=('Arial', 18),
            bg=TABLE_PANEL,
            fg='white',
        )
        self.community_label.place(x=12, y=10)

        self.community_cards_frame = tk.Frame(
            community_frame,
            bg=TABLE_PANEL,
            width=500,
            height=420,
        )
        self.community_cards_frame.place(x=8, y=20)
        self.community_label.lift()
        self.community_cards_frame.pack_propagate(False)

        # 十字形目标牌位。卡牌移动到目标后会覆盖这些轮廓。
        self.cross_slot_widgets = []
        slot_specs = [
            (2, VERTICAL_POSITIONS[2], '2\n纵'),
            (0, HORIZONTAL_POSITIONS[0], '0\n横'),
            (4, HORIZONTAL_POSITIONS[4], '4\n中'),
            (1, HORIZONTAL_POSITIONS[1], '1\n横'),
            (3, VERTICAL_POSITIONS[3], '3\n纵'),
        ]
        for _index, (slot_x, slot_y), slot_text in slot_specs:
            slot = tk.Frame(
                self.community_cards_frame,
                bg='#315748',
                highlightbackground=GOLD,
                highlightcolor=GOLD,
                highlightthickness=2,
                width=CARD_W,
                height=CARD_H,
            )
            slot.place(x=slot_x, y=slot_y, width=CARD_W, height=CARD_H)
            slot.pack_propagate(False)
            tk.Label(
                slot,
                text=slot_text,
                font=('Arial', 12, 'bold'),
                bg='#315748',
                fg='#E8D38A',
                justify=tk.CENTER,
            ).place(relx=0.5, rely=0.5, anchor='center')
            self.cross_slot_widgets.append(slot)


        # 玩家区域下移 30px，并加宽以容纳更大的牌间距。
        player_frame = tk.Frame(table_canvas, bg=TABLE_PANEL, bd=2, relief=tk.RAISED)
        player_frame.place(x=180, y=480, width=370, height=230)
        self.player_label = tk.Label(
            player_frame,
            text='玩家',
            font=('Arial', 18),
            bg=TABLE_PANEL,
            fg='white',
        )
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg=TABLE_PANEL)
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=10)

        # =====================================================
        # 右侧控制面板：恢复原版卡片、尺寸、字体与间距。
        # =====================================================
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

        self.balance_label = tk.Label(
            body_info,
            text=f'余额: ${self.balance:,.2f}',
            font=('Arial', 16, 'bold'),
            bg=PANEL_BG,
            fg='black',
        )
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(
            body_info,
            text='下注阶段',
            font=('Arial', 16, 'bold'),
            bg=PANEL_BG,
            fg='#A88100',
        )
        self.stage_label.pack(side=tk.RIGHT)

        # 累进大奖卡片
        progressive_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        progressive_card.pack(fill=tk.X, pady=3)
        header_prog = tk.Frame(progressive_card, bg=HEADER_BG)
        header_prog.pack(fill=tk.X)
        tk.Label(
            header_prog,
            text='累进大奖',
            font=('Arial', 13, 'bold'),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack(pady=4)
        body_prog = tk.Frame(progressive_card, bg=PANEL_BG)
        body_prog.pack(fill=tk.X, padx=10, pady=8)
        self.progressive_amount_var = tk.StringVar(value=f'${self.game.progressive_amount:,.2f}')
        self.progressive_display = tk.Label(
            body_prog,
            textvariable=self.progressive_amount_var,
            font=('Arial', 20, 'bold'),
            bg=PANEL_BG,
            fg='#A88100',
        )
        self.progressive_display.pack(anchor='center')

        # 下注上限卡片
        limit_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        header_limit = tk.Frame(limit_card, bg=HEADER_BG)
        header_limit.pack(fill=tk.X)
        tk.Label(
            header_limit,
            text='下注上限',
            font=('Arial', 13, 'bold'),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack(pady=4)
        body_limit = tk.Frame(limit_card, bg=PANEL_BG)
        body_limit.pack(fill=tk.X, padx=10, pady=8)

        table_frame = tk.Frame(body_limit, bg=PANEL_BG, bd=2, relief=tk.SOLID)
        table_frame.pack(fill=tk.X)
        for column, title in enumerate(('底注最低', '底注最高', '边注最高')):
            tk.Label(
                table_frame,
                text=title,
                font=('Arial', 11, 'bold'),
                bg=PANEL_BG,
                fg=TITLE_FG,
                borderwidth=1,
                relief=tk.SOLID,
                padx=5,
                pady=5,
            ).grid(row=0, column=column, sticky='nsew')
        self.min_ante_label = tk.Label(
            table_frame,
            text='$10',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
            fg='#A88100',
            borderwidth=1,
            relief=tk.SOLID,
            padx=5,
            pady=5,
        )
        self.max_ante_label = tk.Label(
            table_frame,
            text='$10,000',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
            fg='#A88100',
            borderwidth=1,
            relief=tk.SOLID,
            padx=5,
            pady=5,
        )
        self.max_side_label = tk.Label(
            table_frame,
            text='$2,500',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
            fg='#A88100',
            borderwidth=1,
            relief=tk.SOLID,
            padx=5,
            pady=5,
        )
        self.min_ante_label.grid(row=1, column=0, sticky='nsew')
        self.max_ante_label.grid(row=1, column=1, sticky='nsew')
        self.max_side_label.grid(row=1, column=2, sticky='nsew')
        for column in range(3):
            table_frame.columnconfigure(column, weight=1)
        for widget in (
            limit_card,
            header_limit,
            body_limit,
            table_frame,
            self.min_ante_label,
            self.max_ante_label,
            self.max_side_label,
        ):
            widget.bind('<Button-1>', self.toggle_high_bet_limits)

        # 筹码与下注卡片
        combined_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        combined_card.pack(fill=tk.X, pady=3)
        header_combined = tk.Frame(combined_card, bg=HEADER_BG)
        header_combined.pack(fill=tk.X)
        tk.Label(
            header_combined,
            text='筹码与下注',
            font=('Arial', 13, 'bold'),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack(pady=4)
        body_combined = tk.Frame(combined_card, bg=PANEL_BG)
        body_combined.pack(fill=tk.X, padx=10, pady=8)
        for column in range(5):
            body_combined.columnconfigure(column, weight=1 if column in (0, 4) else 0)

        self.chip_container = tk.Frame(body_combined, bg=PANEL_BG)
        self.chip_container.grid(row=0, column=0, columnspan=5, pady=(0, 8), sticky='ew')
        for column in range(6):
            self.chip_container.columnconfigure(column, weight=1)
        self._rebuild_chips()

        # 第一行：累进大奖（左） | 五牌红利（右）
        self.jackpot_check = tk.Checkbutton(
            body_combined,
            text='累进大奖($2.50)',
            variable=self.jackpot_bet_var,
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
            fg='black',
            selectcolor=PANEL_BG,
            anchor='w',
        )
        self.jackpot_check.grid(row=1, column=0, columnspan=3, sticky='w', padx=(4, 0), pady=2)
        tk.Label(
            body_combined,
            text='五牌红利 :',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
        ).grid(row=1, column=3, sticky='e', padx=(0, 4), pady=2)
        self.five_card_bonus_display = tk.Label(
            body_combined,
            textvariable=self.five_card_bonus_var,
            font=('Arial', 12),
            bg='white',
            fg='black',
            width=8,
            relief=tk.SUNKEN,
        )
        self.five_card_bonus_display.grid(row=1, column=4, sticky='e', padx=(2, 4), pady=2)
        self.five_card_bonus_display.bind(
            '<Button-1>', lambda event: self.add_chip_to_bet('five_card_bonus')
        )
        self.five_card_bonus_display.bind(
            '<Button-3>', lambda event: self.reset_single_bet('five_card_bonus', event)
        )
        self.bet_widgets['five_card_bonus'] = self.five_card_bonus_display

        # 第二行：【格子】底注(横) = 底注(纵)【格子】
        self.ante_horizontal_display = tk.Label(
            body_combined,
            textvariable=self.ante_horizontal_var,
            font=('Arial', 12),
            bg='white',
            fg='black',
            width=8,
            relief=tk.SUNKEN,
        )
        self.ante_horizontal_display.grid(row=2, column=0, sticky='w', padx=(4, 2), pady=2)
        tk.Label(
            body_combined,
            text=': 底注(横)',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
        ).grid(row=2, column=1, sticky='e', pady=2)
        tk.Label(
            body_combined,
            text=' = ',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
            fg='#8A5A00',
        ).grid(row=2, column=2, pady=2)
        tk.Label(
            body_combined,
            text='底注(纵) :',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
        ).grid(row=2, column=3, sticky='w', pady=2)
        self.ante_vertical_display = tk.Label(
            body_combined,
            textvariable=self.ante_vertical_var,
            font=('Arial', 12),
            bg='white',
            fg='black',
            width=8,
            relief=tk.SUNKEN,
        )
        self.ante_vertical_display.grid(row=2, column=4, sticky='e', padx=(2, 4), pady=2)
        for display in (self.ante_horizontal_display, self.ante_vertical_display):
            display.bind('<Button-1>', lambda event: self.add_chip_to_bet('ante'))
            display.bind('<Button-3>', lambda event: self.reset_single_bet('ante', event))
        self.bet_widgets['ante_horizontal'] = self.ante_horizontal_display
        self.bet_widgets['ante_vertical'] = self.ante_vertical_display

        # 第三行：【格子】加注(横)   加注(纵)【格子】
        self.raise_horizontal_display = tk.Label(
            body_combined,
            textvariable=self.raise_horizontal_var,
            font=('Arial', 12),
            bg='white',
            fg='black',
            width=8,
            relief=tk.SUNKEN,
        )
        self.raise_horizontal_display.grid(row=3, column=0, sticky='w', padx=(4, 2), pady=2)
        tk.Label(
            body_combined,
            text=': 加注(横)',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
        ).grid(row=3, column=1, sticky='e', pady=2)
        tk.Label(body_combined, text='   ', font=('Arial', 12), bg=PANEL_BG).grid(row=3, column=2)
        tk.Label(
            body_combined,
            text='加注(纵) :',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
        ).grid(row=3, column=3, sticky='w', pady=2)
        self.raise_vertical_display = tk.Label(
            body_combined,
            textvariable=self.raise_vertical_var,
            font=('Arial', 12),
            bg='white',
            fg='black',
            width=8,
            relief=tk.SUNKEN,
        )
        self.raise_vertical_display.grid(row=3, column=4, sticky='e', padx=(2, 4), pady=2)
        self.bet_widgets['raise_horizontal'] = self.raise_horizontal_display
        self.bet_widgets['raise_vertical'] = self.raise_vertical_display

        # 第四行：【格子】加注(中)
        self.raise_middle_display = tk.Label(
            body_combined,
            textvariable=self.raise_middle_var,
            font=('Arial', 12),
            bg='white',
            fg='black',
            width=8,
            relief=tk.SUNKEN,
        )
        self.raise_middle_display.grid(row=4, column=0, sticky='w', padx=(4, 2), pady=2)
        tk.Label(
            body_combined,
            text=': 加注(中)',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
        ).grid(row=4, column=1, sticky='e', pady=2)
        self.bet_widgets['raise_middle'] = self.raise_middle_display

        # 操作卡片
        action_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        action_card.pack(fill=tk.X, pady=3)
        header_action = tk.Frame(action_card, bg=HEADER_BG)
        header_action.pack(fill=tk.X)
        tk.Label(
            header_action,
            text='操作',
            font=('Arial', 13, 'bold'),
            bg=HEADER_BG,
            fg=TITLE_FG,
        ).pack(pady=4)
        body_action = tk.Frame(action_card, bg=PANEL_BG)
        body_action.pack(fill=tk.X, padx=10, pady=8)
        self.status_label = tk.Label(
            body_action,
            text='设置下注金额并开始游戏',
            font=('Arial', 12, 'bold'),
            bg=PANEL_BG,
            fg=TITLE_FG,
            height=1,
            width=30,
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
            body_bottom,
            text='本局下注: $0.00',
            font=('Arial', 12),
            bg=PANEL_BG,
            fg='black',
        )
        self.current_bet_label.pack(anchor='w')
        row_last = tk.Frame(body_bottom, bg=PANEL_BG)
        row_last.pack(fill=tk.X, pady=2)
        self.last_win_label = tk.Label(
            row_last,
            text='上局返还: $0.00',
            font=('Arial', 12),
            bg=PANEL_BG,
            fg='black',
        )
        self.last_win_label.pack(side=tk.LEFT)
        self.info_button = tk.Button(
            row_last,
            text='ℹ️',
            command=self.show_game_instructions,
            bg='#4B8BBE',
            fg='white',
            font=('Arial', 12),
            width=2,
            height=1,
            relief=tk.FLAT,
        )
        self.info_button.pack(side=tk.RIGHT)

    def _make_bet_row(self, parent, left_text, left_var, left_key, right_text, right_var, right_key):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=left_text, width=10, anchor='e', font=('Arial', 11, 'bold'), bg=PANEL_BG).pack(side=tk.LEFT)
        left_display = tk.Label(row, textvariable=left_var, width=8, bg='white', relief=tk.SUNKEN)
        left_display.pack(side=tk.LEFT, padx=(2, 8))
        tk.Label(row, text=right_text, width=10, anchor='e', font=('Arial', 11, 'bold'), bg=PANEL_BG).pack(side=tk.LEFT)
        right_display = tk.Label(row, textvariable=right_var, width=8, bg='white', relief=tk.SUNKEN)
        right_display.pack(side=tk.LEFT, padx=2)
        self.bet_widgets[left_key] = left_display
        self.bet_widgets[right_key] = right_display

        if left_key in ('ante_horizontal', 'ante_vertical'):
            left_display.bind('<Button-1>', lambda event: self.add_chip_to_bet('ante'))
            left_display.bind('<Button-3>', lambda event: self.reset_single_bet('ante', event))
        elif left_key == 'five_card_bonus':
            left_display.bind('<Button-1>', lambda event: self.add_chip_to_bet('five_card_bonus'))
            left_display.bind('<Button-3>', lambda event: self.reset_single_bet('five_card_bonus', event))

    # ---------- 筹码与下注 ----------
    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete('highlight')
            if self.chip_texts.get(chip) == chip_text:
                chip.create_oval(2, 2, 49, 49, outline='#2f00ff', width=3, tags='highlight')

    def _chip_value(self):
        if not self.selected_chip:
            return 0.0
        text = self.selected_chip.replace('$', '')
        if 'K' in text:
            return float(text.replace('K', '')) * 1000
        return float(text)

    def add_chip_to_bet(self, bet_type):
        if self.game_in_progress:
            return
        chip_value = self._chip_value()
        if chip_value <= 0:
            return

        if bet_type == 'ante':
            current = float(self.ante_horizontal_var.get())
            limit = 50000 if self.high_bet_mode else 10000
            new_amount = min(current + chip_value, limit)
            if current >= limit:
                messagebox.showwarning('下注限制', '两份底注已达到上限。')
                return
            self.ante_horizontal_var.set(self._format_amount(new_amount))
            self.ante_vertical_var.set(self._format_amount(new_amount))
        elif bet_type == 'five_card_bonus':
            current = float(self.five_card_bonus_var.get())
            limit = 12500 if self.high_bet_mode else 2500
            new_amount = min(current + chip_value, limit)
            if current >= limit:
                messagebox.showwarning('下注限制', '五牌红利已达到上限。')
                return
            self.five_card_bonus_var.set(self._format_amount(new_amount))

    def reset_single_bet(self, bet_type, _event=None):
        if self.game_in_progress:
            return
        if bet_type == 'ante':
            self.ante_horizontal_var.set('0')
            self.ante_vertical_var.set('0')
            widgets = [self.bet_widgets['ante_horizontal'], self.bet_widgets['ante_vertical']]
        else:
            self.five_card_bonus_var.set('0')
            widgets = [self.bet_widgets['five_card_bonus']]
        for widget in widgets:
            widget.config(bg='#FFCDD2')
            self.after(500, lambda current=widget: current.config(bg='white'))

    @staticmethod
    def _format_amount(amount):
        amount = float(amount)
        return str(int(amount)) if amount.is_integer() else f'{amount:.2f}'

    def _rebuild_chips(self):
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_buttons = []
        self.chip_texts = {}
        if self.high_bet_mode:
            configs = [
                ('$100', '#000000', 'white'),
                ('$500', '#FF7DDA', 'black'),
                ('$1K', '#ffffff', 'black'),
                ('$5K', '#ff0000', 'white'),
                ('$10K', '#00fbff', 'black'),
                ('$50K', '#00ffae', 'black'),
            ]
            default = '$100'
        else:
            configs = [
                ('$10', '#ffa500', 'black'),
                ('$25', '#00ff00', 'black'),
                ('$100', '#000000', 'white'),
                ('$500', '#FF7DDA', 'black'),
                ('$1K', '#ffffff', 'black'),
                ('$2.5K', '#ff0000', 'white'),
            ]
            default = '$10'

        for column, (text, background, foreground) in enumerate(configs):
            chip = tk.Canvas(self.chip_container, width=50, height=50, bg=PANEL_BG, highlightthickness=0)
            chip.grid(row=0, column=column, padx=2)
            chip.create_oval(2, 2, 49, 49, fill=background, outline='black')
            chip.create_text(25.5, 25.5, text=text, fill=foreground, font=('Arial', 11, 'bold'))
            chip.bind('<Button-1>', lambda event, value=text: self.select_chip(value))
            self.chip_buttons.append(chip)
            self.chip_texts[chip] = text
        self.select_chip(default)

    def toggle_high_bet_limits(self, _event=None):
        if self.game_in_progress:
            return
        if not self.high_bet_mode:
            password = simpledialog.askstring('高额下注', '请输入密码：', parent=self)
            if password is None:
                return
            if password.strip() != time.strftime('%H%M'):
                messagebox.showerror('错误', '密码错误')
                return
            self.high_bet_mode = True
        else:
            self.high_bet_mode = False
        self.reset_bets()
        self._update_limits_display()
        self._rebuild_chips()

    def _update_limits_display(self):
        if self.high_bet_mode:
            self.min_ante_label.config(text='$100')
            self.max_ante_label.config(text='$50,000')
            self.max_side_label.config(text='$12,500')
        else:
            self.min_ante_label.config(text='$10')
            self.max_ante_label.config(text='$10,000')
            self.max_side_label.config(text='$2,500')

    # ---------- 主按钮 ----------
    def clear_btn_frame(self):
        for widget in self.btn_frame.winfo_children():
            widget.destroy()

    def add_main_buttons(self):
        self.clear_btn_frame()

        # 三个按钮使用等宽网格，并在操作区内平均、居中显示。
        button_row = tk.Frame(self.btn_frame, bg=PANEL_BG)
        button_row.pack(fill=tk.X, expand=True)
        for column in range(3):
            button_row.columnconfigure(column, weight=1, uniform='main_action_buttons')

        reset_button = tk.Button(
            button_row,
            text='重设金额',
            command=self.reset_bets,
            font=('Arial', 11, 'bold'),
            bg='#F44336',
            fg='white',
        )
        reset_button.grid(row=0, column=0, padx=4, sticky='ew')

        self.repeat_bet_btn = tk.Button(
            button_row,
            text='重复上局下注',
            command=self.apply_last_bet,
            font=('Arial', 11, 'bold'),
            bg='#FFC107',
            fg='black',
            state=tk.NORMAL if self.last_bet is not None else tk.DISABLED,
        )
        self.repeat_bet_btn.grid(row=0, column=1, padx=4, sticky='ew')

        start_button = tk.Button(
            button_row,
            text='开始游戏',
            command=self.start_game,
            font=('Arial', 11, 'bold'),
            bg='#4CAF50',
            fg='white',
        )
        start_button.grid(row=0, column=2, padx=4, sticky='ew')

    # ---------- 游戏开始与发牌 ----------
    def start_game(self):
        try:
            ante_horizontal = float(self.ante_horizontal_var.get())
            ante_vertical = float(self.ante_vertical_var.get())
            five_card_bonus = float(self.five_card_bonus_var.get())
        except ValueError:
            messagebox.showerror('错误', '请输入有效的下注金额。')
            return

        if abs(ante_horizontal - ante_vertical) > 0.001:
            ante_vertical = ante_horizontal
            self.ante_vertical_var.set(self._format_amount(ante_vertical))

        minimum = 100 if self.high_bet_mode else 10
        maximum = 50000 if self.high_bet_mode else 10000
        max_bonus = 12500 if self.high_bet_mode else 2500
        if ante_horizontal < minimum:
            messagebox.showerror('错误', f'每份底注至少需要 ${minimum}。')
            return
        if ante_horizontal > maximum:
            ante_horizontal = ante_vertical = maximum
            self.ante_horizontal_var.set(self._format_amount(maximum))
            self.ante_vertical_var.set(self._format_amount(maximum))
        if five_card_bonus > max_bonus:
            five_card_bonus = max_bonus
            self.five_card_bonus_var.set(self._format_amount(max_bonus))

        jackpot = int(self.jackpot_bet_var.get())
        jackpot_cost = 2.5 if jackpot else 0.0
        initial_total = ante_horizontal + ante_vertical + five_card_bonus + jackpot_cost
        if initial_total > self.balance:
            messagebox.showerror('错误', f'余额不足！初始下注需要 ${initial_total:,.2f}。')
            return

        self.balance -= initial_total
        self.game_in_progress = True
        self.update_balance()
        self.last_jackpot_state = jackpot
        self.last_bet = {
            'ante': ante_horizontal,
            'five_card_bonus': five_card_bonus,
            'jackpot': jackpot,
        }

        self.game.reset_game()
        self.game.ante_horizontal = ante_horizontal
        self.game.ante_vertical = ante_vertical
        self.game.five_card_bonus = five_card_bonus
        self.game.jackpot_bet = jackpot
        self.game.deal_initial()

        self.raise_horizontal_var.set('0')
        self.raise_vertical_var.set('0')
        self.raise_middle_var.set('0')
        self.current_bet_label.config(text=f'本局下注: ${initial_total:,.2f}')
        self.last_win_label.config(text='上局返还: $0.00')
        self.progressive_display.config(bg=PANEL_BG)

        self._clear_cards()
        self._disable_bet_inputs()
        self.clear_btn_frame()
        self.stage_label.config(text='发牌')
        self.status_label.config(text='5张公共牌和2张玩家牌发牌中...')

        self.animation_queue = [
            ('community', index, MIDDLE_POSITIONS[index]) for index in range(5)
        ] + [
            ('player', index, PLAYER_POSITIONS[index]) for index in range(2)
        ]
        self.animate_deal()

    def _clear_cards(self):
        for widget in self.community_cards_frame.winfo_children():
            if hasattr(widget, 'card'):
                widget.destroy()
        for widget in self.player_cards_frame.winfo_children():
            if hasattr(widget, 'card'):
                widget.destroy()
        self.active_card_labels = []
        self.community_card_labels = {}
        self.player_card_labels = {}

    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(300, self.reveal_player_cards)
            return

        self.animation_in_progress = True
        area, index, target = self.animation_queue.pop(0)
        if area == 'community':
            frame = self.community_cards_frame
            card = self.game.community_cards[index]
            start = (255, -CARD_H)
        else:
            frame = self.player_cards_frame
            card = self.game.player_hole[index]
            start = (145, -CARD_H)

        label = tk.Label(frame, image=self.back_image, bg=TABLE_PANEL)
        label.card = card
        label.card_index = index
        label.is_face_up = False
        label.place(x=start[0], y=start[1], width=CARD_W, height=CARD_H)
        self.active_card_labels.append(label)
        if area == 'community':
            self.community_card_labels[index] = label
        else:
            self.player_card_labels[index] = label

        self.animate_label_move(label, target, lambda: self.after(40, self.animate_deal))

    def animate_label_move(self, label, target, callback=None):
        try:
            current_x = label.winfo_x()
            current_y = label.winfo_y()
            delta_x = target[0] - current_x
            delta_y = target[1] - current_y
            distance = math.hypot(delta_x, delta_y)
            if distance < 4:
                label.place(x=target[0], y=target[1], width=CARD_W, height=CARD_H)
                if callback:
                    callback()
                return
            label.place(
                x=current_x + delta_x * 0.22,
                y=current_y + delta_y * 0.22,
                width=CARD_W,
                height=CARD_H,
            )
            self.after(18, lambda: self.animate_label_move(label, target, callback))
        except tk.TclError:
            if callback:
                callback()

    def reveal_player_cards(self):
        labels = [self.player_card_labels[index] for index in range(2)]

        def reveal_next(position=0):
            if position >= len(labels):
                self.game.stage = 'horizontal'
                self.stage_label.config(text='加注(横)')
                self.status_label.config(text='玩家牌已打开。请选择加注(横) 1X–3X，或弃牌。')
                self.show_raise_buttons()
                return
            index = position
            self.flip_card_animation(
                labels[position],
                callback=lambda: (
                    self.game.cards_revealed['player'].__setitem__(index, True),
                    reveal_next(position + 1),
                ),
            )

        reveal_next()

    def flip_card_animation(self, label, callback=None):
        if label.is_face_up:
            if callback:
                callback()
            return

        # V4 修正：翻牌动画必须始终围绕翻牌前的固定中心展开。
        # V3 每一帧都从已缩窄且已移动的 Label 重新计算中心，
        # 因而牌面会在翻转期间持续向右漂移。
        label.update_idletasks()
        label._flip_origin_x = label.winfo_x()
        label._flip_origin_y = label.winfo_y()
        card = label.card
        self._animate_flip(label, card, 0, callback)

    def _animate_flip(self, label, card, step, callback):
        steps = 10
        half = steps // 2
        origin_x = getattr(label, '_flip_origin_x', label.winfo_x())
        origin_y = getattr(label, '_flip_origin_y', label.winfo_y())
        fixed_center_x = origin_x + CARD_W // 2

        if step > steps:
            label.is_face_up = True
            label.config(image=self.card_images[(card.suit, card.rank)])
            label.place(x=origin_x, y=origin_y, width=CARD_W, height=CARD_H)
            self._temp_flip_images.pop(label, None)
            for attribute in ('_flip_origin_x', '_flip_origin_y'):
                try:
                    delattr(label, attribute)
                except AttributeError:
                    pass
            if callback:
                callback()
            return

        if step <= half:
            ratio = 1 - step / half
            source = self.original_images['back']
        else:
            ratio = (step - half) / half
            source = self.original_images[(card.suit, card.rank)]
        width = max(1, int(CARD_W * ratio))
        image = ImageTk.PhotoImage(source.resize((width, CARD_H)))
        self._temp_flip_images[label] = image
        label.config(image=image)
        label.place(
            x=fixed_center_x - width // 2,
            y=origin_y,
            width=width,
            height=CARD_H,
        )
        self.after(25, lambda: self._animate_flip(label, card, step + 1, callback))

    # ---------- 三轮决策 ----------
    def show_raise_buttons(self):
        self.clear_btn_frame()
        row = tk.Frame(self.btn_frame, bg=PANEL_BG)
        row.pack()
        ante = self.game.ante_horizontal
        for multiplier in (1, 2, 3):
            button = tk.Button(
                row,
                text=f'{multiplier}倍',
                command=lambda value=multiplier: self.place_cross_bet(value),
                font=('Arial', 11, 'bold'),
                bg='#4CAF50',
                fg='white',
                width=7,
            )
            button.pack(side=tk.LEFT, padx=4)
            if self.balance < ante * multiplier:
                button.config(state=tk.DISABLED)
        tk.Button(
            row,
            text='弃牌',
            command=self.fold_game,
            font=('Arial', 11, 'bold'),
            bg='#F44336',
            fg='white',
            width=7,
        ).pack(side=tk.LEFT, padx=4)

    def place_cross_bet(self, multiplier):
        if self.game.stage not in ('horizontal', 'vertical', 'middle'):
            return
        amount = self.game.ante_horizontal * multiplier
        if amount > self.balance:
            messagebox.showerror('错误', '余额不足！')
            self.show_raise_buttons()
            return

        self.clear_btn_frame()
        self.balance -= amount
        self.update_balance()

        if self.game.stage == 'horizontal':
            self.game.raise_horizontal = amount
            self.raise_horizontal_var.set(self._format_amount(amount))
            self._update_current_total()
            self.status_label.config(text='庄家正在移动公共牌到 横 并打开。')
            self.move_and_reveal(
                [0, 1],
                HORIZONTAL_POSITIONS,
                self._after_horizontal_reveal,
            )
        elif self.game.stage == 'vertical':
            self.game.raise_vertical = amount
            self.raise_vertical_var.set(self._format_amount(amount))
            self._update_current_total()
            self.status_label.config(text='庄家正在移动公共牌到 纵 并打开。')
            self.move_and_reveal(
                [2, 3],
                VERTICAL_POSITIONS,
                self._after_vertical_reveal,
            )
        else:
            self.game.raise_middle = amount
            self.raise_middle_var.set(self._format_amount(amount))
            self._update_current_total()
            self.status_label.config(text='庄家正在移动公共牌到 中 并打开。')
            self.move_and_reveal([4], HORIZONTAL_POSITIONS, lambda: self.after(500, self.show_showdown))

    def _after_horizontal_reveal(self):
        self.game.stage = 'vertical'
        self.stage_label.config(text='加注(纵)')
        self.status_label.config(text='请选择加注(纵) 1X–3X，或弃牌。')
        self.show_raise_buttons()

    def _after_vertical_reveal(self):
        self.game.stage = 'middle'
        self.stage_label.config(text='加注(中)')
        self.status_label.config(text='请选择加注(中) 1X–3X，或弃牌。')
        self.show_raise_buttons()

    def move_and_reveal(self, indices, target_map, callback):
        queue = list(indices)

        def next_card():
            if not queue:
                self.update_hand_labels()
                callback()
                return
            index = queue.pop(0)
            label = self.community_card_labels[index]
            target = target_map[index]

            def after_move():
                def after_flip():
                    self.game.cards_revealed['community'][index] = True
                    next_card()

                self.flip_card_animation(label, after_flip)

            self.animate_label_move(label, target, after_move)

        next_card()

    def fold_game(self):
        if self.game.stage not in ('horizontal', 'vertical', 'middle'):
            return
        self.clear_btn_frame()
        self.game.folded = True
        self.status_label.config(text='玩家已经弃牌；正在自动打开公共牌结算。')
        self.stage_label.config(text='弃牌开牌')

        if not self.game.cards_revealed['community'][0]:
            self.move_and_reveal([0, 1], HORIZONTAL_POSITIONS, self._fold_reveal_vertical)
        elif not self.game.cards_revealed['community'][2]:
            self._fold_reveal_vertical()
        else:
            self._fold_reveal_center()

    def _fold_reveal_vertical(self):
        self.move_and_reveal([2, 3], VERTICAL_POSITIONS, self._fold_reveal_center)

    def _fold_reveal_center(self):
        self.move_and_reveal([4], HORIZONTAL_POSITIONS, lambda: self.after(500, self.show_showdown))

    # ---------- 结算 ----------
    def show_showdown(self):
        if self.game.stage == 'settled':
            return
        self.game.stage = 'settled'
        self.stage_label.config(text='结算')

        horizontal_eval = self.game.evaluate_horizontal()
        vertical_eval = self.game.evaluate_vertical()
        five_bonus_eval = self.game.evaluate_five_card_bonus()

        total_return, details = calculate_criss_cross_returns(
            ante_horizontal=self.game.ante_horizontal,
            ante_vertical=self.game.ante_vertical,
            raise_horizontal=self.game.raise_horizontal,
            raise_vertical=self.game.raise_vertical,
            raise_middle=self.game.raise_middle,
            five_card_bonus=self.game.five_card_bonus,
            horizontal_eval=horizontal_eval,
            vertical_eval=vertical_eval,
            five_bonus_eval=five_bonus_eval,
            folded=self.game.folded,
        )

        progressive_return = 0.0
        if self.game.jackpot_bet:
            progressive_return = self.calculate_progressive_bonus()
            if progressive_return > 0:
                total_return += progressive_return
                messagebox.showinfo(
                    '恭喜获得累进大奖！',
                    f'您赢得了 ${progressive_return:,.2f} 累进大奖奖金！',
                )
                self.progressive_display.config(bg='gold')

        self.update_jackpot()
        self.balance += total_return
        self.update_balance()
        self.last_win = total_return
        self.last_win_label.config(text=f'上局返还: ${total_return:,.2f}')

        variable_map = {
            'ante_horizontal': self.ante_horizontal_var,
            'ante_vertical': self.ante_vertical_var,
            'raise_horizontal': self.raise_horizontal_var,
            'raise_vertical': self.raise_vertical_var,
            'raise_middle': self.raise_middle_var,
            'five_card_bonus': self.five_card_bonus_var,
        }
        wager_map = {
            'ante_horizontal': self.game.ante_horizontal,
            'ante_vertical': self.game.ante_vertical,
            'raise_horizontal': self.game.raise_horizontal,
            'raise_vertical': self.game.raise_vertical,
            'raise_middle': self.game.raise_middle,
            'five_card_bonus': self.game.five_card_bonus,
        }
        for key, variable in variable_map.items():
            variable.set(self._format_amount(details[key]))
            widget = self.bet_widgets[key]
            if details[key] > wager_map[key] and wager_map[key] > 0:
                widget.config(bg='gold')
            elif details[key] == wager_map[key] and wager_map[key] > 0:
                widget.config(bg='light blue')
            else:
                widget.config(bg='white')

        horizontal_name = HAND_RANK_NAMES[horizontal_eval[0]]
        vertical_name = HAND_RANK_NAMES[vertical_eval[0]]
        self.player_label.config(
            text=f'玩家 - {horizontal_name}(横) & {vertical_name}(纵)'
        )
        if total_return == 0:
            temp_state = '本局您输了，送你好运！'
        else:
            temp_state = '恭喜您，你赢啦！'
        self.status_label.config(
            text = temp_state
        )

        self.clear_btn_frame()
        restart = tk.Button(
            self.btn_frame,
            text='再来一局',
            command=self.reset_game,
            font=('Arial', 11, 'bold'),
            bg='#2196F3',
            fg='white',
            width=12,
        )
        restart.pack()
        restart.bind('<Button-3>', self.show_card_sequence)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
        self.game_in_progress = False

        save_criss_cross_history(
            deck=self.game.deck,
            community_cards=self.game.community_cards,
            player_cards=self.game.player_hole,
            total_return=total_return,
            horizontal_eval=horizontal_eval,
            vertical_eval=vertical_eval,
            five_bonus_eval=five_bonus_eval,
            folded=self.game.folded,
        )

    def calculate_progressive_bonus(self):
        rank_eval, _ = evaluate_hand(self.game.progressive_cards())
        jackpot = self.game.progressive_amount
        bonus = 0.0
        if rank_eval == 10:
            bonus = max(jackpot, 10000.0)
            self.game.progressive_amount -= bonus
        elif rank_eval == 9:
            bonus = max(jackpot * 0.1, 1000.0)
            self.game.progressive_amount -= bonus
        elif rank_eval == 8:
            bonus = 1250.0
            self.game.progressive_amount -= bonus
        elif rank_eval == 7:
            bonus = 375.0
            self.game.progressive_amount -= bonus
        elif rank_eval == 6:
            bonus = 250.0
            self.game.progressive_amount -= bonus

        if self.game.progressive_amount < self.game.min_progressive:
            self.game.progressive_amount = self.game.min_progressive
        self.progressive_amount_var.set(f'${self.game.progressive_amount:,.2f}')
        save_jackpot(self.game.progressive_amount)
        return bonus

    def update_jackpot(self):
        jackpot_cost = 2.5 if self.game.jackpot_bet else 0.0
        total_wagers = (
            self.game.ante_horizontal
            + self.game.ante_vertical
            + self.game.five_card_bonus
            + self.game.raise_horizontal
            + self.game.raise_vertical
            + self.game.raise_middle
        )
        self.game.progressive_amount += total_wagers * 0.001 + jackpot_cost * 0.95
        if self.game.progressive_amount < self.game.min_progressive:
            self.game.progressive_amount = self.game.min_progressive
        self.progressive_amount_var.set(f'${self.game.progressive_amount:,.2f}')
        save_jackpot(self.game.progressive_amount)

    # ---------- 辅助显示 ----------
    def update_hand_labels(self):
        # 牌局进行期间不在玩家标题显示中间牌型；最终结算由
        # show_showdown() 统一设置为：玩家 - {横牌型}(横) & {纵牌型}(纵)。
        if self.game.stage != 'showdown':
            self.player_label.config(text='玩家')

    def _update_current_total(self):
        jackpot_cost = 2.5 if self.game.jackpot_bet else 0.0
        total = (
            self.game.ante_horizontal
            + self.game.ante_vertical
            + self.game.five_card_bonus
            + self.game.raise_horizontal
            + self.game.raise_vertical
            + self.game.raise_middle
            + jackpot_cost
        )
        self.current_bet_label.config(text=f'本局下注: ${total:,.2f}')

    def update_balance(self):
        self.balance_label.config(text=f'余额: ${self.balance:,.2f}')
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def _disable_bet_inputs(self):
        for key in ('ante_horizontal', 'ante_vertical', 'five_card_bonus'):
            self.bet_widgets[key].unbind('<Button-1>')
        self.jackpot_check.config(state=tk.DISABLED)
        for chip in self.chip_buttons:
            chip.unbind('<Button-1>')

    def _enable_bet_inputs(self):
        for key in ('ante_horizontal', 'ante_vertical'):
            self.bet_widgets[key].bind('<Button-1>', lambda event: self.add_chip_to_bet('ante'))
            self.bet_widgets[key].bind('<Button-3>', lambda event: self.reset_single_bet('ante', event))
        self.bet_widgets['five_card_bonus'].bind(
            '<Button-1>', lambda event: self.add_chip_to_bet('five_card_bonus')
        )
        self.bet_widgets['five_card_bonus'].bind(
            '<Button-3>', lambda event: self.reset_single_bet('five_card_bonus', event)
        )
        self.jackpot_check.config(state=tk.NORMAL)
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind('<Button-1>', lambda event, value=text: self.select_chip(value))

    # ---------- 重置与重复下注 ----------
    def reset_bets(self):
        if self.game_in_progress:
            return
        self.ante_horizontal_var.set('0')
        self.ante_vertical_var.set('0')
        self.five_card_bonus_var.set('0')
        self.raise_horizontal_var.set('0')
        self.raise_vertical_var.set('0')
        self.raise_middle_var.set('0')
        self.jackpot_bet_var.set(0)
        self.status_label.config(text='已重置所有下注金额。')
        for widget in self.bet_widgets.values():
            widget.config(bg='white')

    def apply_last_bet(self):
        if self.last_bet is None or self.game_in_progress:
            return
        minimum = 100 if self.high_bet_mode else 10
        maximum = 50000 if self.high_bet_mode else 10000
        max_bonus = 12500 if self.high_bet_mode else 2500
        ante = min(max(float(self.last_bet['ante']), minimum), maximum)
        bonus = min(float(self.last_bet['five_card_bonus']), max_bonus)
        self.ante_horizontal_var.set(self._format_amount(ante))
        self.ante_vertical_var.set(self._format_amount(ante))
        self.five_card_bonus_var.set(self._format_amount(bonus))
        self.jackpot_bet_var.set(int(self.last_bet['jackpot']))
        self.status_label.config(text='已应用上次下注金额')

    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except tk.TclError:
                pass
            self.auto_reset_timer = None

        self._load_assets()
        self.game.reset_game()
        self._clear_cards()
        self.stage_label.config(text='下注阶段')
        self.player_label.config(text='玩家')
        self.community_label.config(text='公共牌')
        self.ante_horizontal_var.set('0')
        self.ante_vertical_var.set('0')
        self.five_card_bonus_var.set('0')
        self.raise_horizontal_var.set('0')
        self.raise_vertical_var.set('0')
        self.raise_middle_var.set('0')
        self.jackpot_bet_var.set(self.last_jackpot_state)
        self.current_bet_label.config(text='本局下注: $0.00')
        self.progressive_display.config(bg=PANEL_BG)
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self._enable_bet_inputs()
        self.add_main_buttons()
        self.status_label.config(
            text='30秒已到，已重置新一局。' if auto_reset else '设置下注金额并开始游戏。'
        )
        self.game_in_progress = False

    # ---------- 规则 ----------
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title('纵横交叉扑克 游戏规则')
        win.geometry('850x750')
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
        canvas.create_window((0, 0), window=content_frame, anchor='nw')

        # 规则文本：沿用原始代码的分段说明格式。
        rules_text = """
        纵横交叉扑克 游戏规则

        1. 下注阶段:
        - 底注(横)与底注(纵): 必须下注，两者金额自动同步
        - 五牌红利: 可选下注，根据5张公共牌的最终牌型赔付
        - 累进大奖: 可选 $2.50 下注，根据玩家2张牌与公共牌0、1、2组成的牌型赔付

        2. 游戏流程:
        a. 设置两份同步底注，选择是否下注五牌红利与累进大奖
        b. 点击「开始游戏」→ 先将5张公共牌面朝下派至中间区域，再派玩家2张牌并打开
        c. 玩家选择加注(横)1X/2X/3X或弃牌；随后公共牌0、1移至横向牌位并打开
        d. 玩家选择加注(纵)1X/2X/3X或弃牌；随后公共牌2、3移至纵向牌位并打开
        e. 玩家选择加注(中)1X/2X/3X或弃牌；最后公共牌4移至交叉中心并打开
        f. 玩家弃牌后仍会完成全部公共牌开牌，并独立结算五牌红利与累进大奖

        3. 结算规则:
        - 横牌组 = 玩家2张牌 + 公共牌0、1、4
        - 纵牌组 = 玩家2张牌 + 公共牌2、3、4
        - 横牌组达到对子J+或更好时，底注(横)按1:1获胜，加注(横)按下方赔率表赔付
        - 纵牌组达到对子J+或更好时，底注(纵)按1:1获胜，加注(纵)按下方赔率表赔付
        - 加注(中)只要横或纵至少一组获胜，即按两组中较高牌型的赔率赔付
        - 五牌红利只根据5张公共牌判定，与玩家手牌及弃牌决定无关
        - 累进大奖使用玩家2张牌与公共牌0、1、2判定，弃牌后仍可获奖

        4. 赔率表:
        """
        tk.Label(
            content_frame,
            text=rules_text,
            font=('微软雅黑', 11),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10,
        ).pack(fill=tk.X, padx=10, pady=5)

        # 创建统一赔率表格，格式与原始代码一致。
        table_frame = tk.Frame(content_frame, bg='#F0F0F0')
        table_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ['牌型', '横／纵／中加注', '五牌红利', '累进大奖']
        header_bg = '#4B8BBE'
        header_fg = 'white'
        for column, header in enumerate(headers):
            label = tk.Label(
                table_frame,
                text=header,
                font=('微软雅黑', 10, 'bold'),
                bg=header_bg,
                fg=header_fg,
                padx=8,
                pady=5,
                anchor='center',
            )
            label.grid(row=0, column=column, sticky='nsew', padx=1, pady=1)

        payout_data = [
            ('皇家同花顺', '500:1', '250:1', '100% 奖池'),
            ('同花顺', '100:1', '100:1', '10% 奖池'),
            ('四条', '40:1', '40:1', '$1,250'),
            ('葫芦', '12:1', '15:1', '$375'),
            ('同花', '8:1', '10:1', '$250'),
            ('顺子', '5:1', '6:1', '-'),
            ('三条', '3:1', '4:1', '-'),
            ('两对', '2:1', '3:1', '-'),
            ('对子J+', '1:1', '-', '-'),
            ('6点或更好对子', '-', '1:1', '-'),
            ('其他', '输', '输', '-'),
        ]

        for row_index, row_data in enumerate(payout_data, start=1):
            background = '#E0E0E0' if row_index % 2 == 0 else '#F0F0F0'
            for column_index, cell_text in enumerate(row_data):
                label = tk.Label(
                    table_frame,
                    text=cell_text,
                    font=('微软雅黑', 10),
                    bg=background,
                    padx=8,
                    pady=5,
                    anchor='center',
                )
                label.grid(
                    row=row_index,
                    column=column_index,
                    sticky='nsew',
                    padx=1,
                    pady=1,
                )

        for column in range(len(headers)):
            table_frame.columnconfigure(column, weight=1)

        notes = """
        注:
        • 底注(横)与底注(纵)不采用牌型倍数；达到对子J+或更好时均按1:1赔付。
        • 加注(中)采用横、纵两组中较高且符合获胜条件的牌型赔率。
        • 五牌红利与累进大奖均独立结算，玩家弃牌后仍然有效。
        """
        tk.Label(
            content_frame,
            text=notes,
            font=('微软雅黑', 10),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10,
        ).pack(fill=tk.X, padx=10, pady=5)

        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox('all'))
        ttk.Button(win, text='关闭', command=win.destroy).pack(pady=10)
        win.bind(
            '<MouseWheel>',
            lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units'),
        )

    @staticmethod
    def _build_payout_table(parent, column, title, rows):
        frame = tk.Frame(parent, bg='#F0F0F0', bd=1, relief=tk.SOLID)
        frame.grid(row=0, column=column, padx=8, sticky='nsew')
        tk.Label(frame, text=title, bg='#4B8BBE', fg='white', font=('微软雅黑', 11, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky='nsew', pady=1
        )
        for row_index, (hand, payout) in enumerate(rows, start=1):
            background = '#E0E0E0' if row_index % 2 == 0 else '#F7F7F7'
            tk.Label(frame, text=hand, bg=background, padx=8, pady=4).grid(
                row=row_index, column=0, sticky='nsew', padx=1, pady=1
            )
            tk.Label(frame, text=payout, bg=background, padx=8, pady=4).grid(
                row=row_index, column=1, sticky='nsew', padx=1, pady=1
            )
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    # ---------- 牌序 ----------
    def show_card_sequence(self, _event=None):
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except tk.TclError:
                pass
            self.auto_reset_timer = None
        if not getattr(self.game, 'deck', None):
            messagebox.showinfo('提示', '没有牌序信息。')
            return

        window = tk.Toplevel(self)
        window.title('本局牌序')
        window.geometry('730x750')
        window.resizable(False, False)
        window.configure(bg='#f0f0f0')
        tk.Label(
            window,
            text=f'本局切牌位置: {self.game.deck.start_pos + 1}',
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0',
        ).pack(pady=10)

        main_frame = tk.Frame(window, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content = tk.Frame(canvas, bg='#f0f0f0')
        canvas.create_window((0, 0), window=content, anchor='nw')

        small_images = {}
        for index, card in enumerate(self.game.deck.full_deck):
            original = self.original_images[(card.suit, card.rank)]
            small_images[index] = ImageTk.PhotoImage(original.resize((60, 84)))

        for row in range(6):
            row_frame = tk.Frame(content, bg='#f0f0f0')
            row_frame.pack(fill=tk.X)
            for column in range(9 if row < 5 else 7):
                index = row * 9 + column
                if index >= 52:
                    break
                background = 'light blue' if index == self.game.deck.start_pos else '#f0f0f0'
                cell = tk.Frame(row_frame, bg=background)
                cell.grid(row=0, column=column, padx=5, pady=3)
                label = tk.Label(cell, image=small_images[index], bg=background, relief=tk.SOLID)
                label.image = small_images[index]
                label.pack()
                tk.Label(cell, text=str(index + 1), bg=background, font=('Arial', 9)).pack()

        content.update_idletasks()
        canvas.config(scrollregion=canvas.bbox('all'))

# =========================================================
# 主入口
# =========================================================
def main(
    initial_balance=10000,
    username='Guest',
    *,
    parent=None,
    balance=None,
    user=None,
    on_back=None,
    on_balance_change=None,
):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return CrissCrossPokerGUI(
            parent,
            actual_balance,
            actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title('纵横交叉扑克')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    page = CrissCrossPokerGUI(root, actual_balance, actual_user)
    page.pack(fill='both', expand=True)

    def close_standalone():
        try:
            update_balance_in_json(page.username, page.balance)
        except Exception:
            pass
        root.destroy()

    page.on_back = lambda _final_balance: close_standalone()
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page.balance


if __name__ == '__main__':
    final_balance = main()
    print(f'Final balance: {final_balance}')