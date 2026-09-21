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

import json
import os
import secrets
import math
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, simpledialog

from PIL import Image, ImageDraw, ImageTk


# ============================================================
# 温州牌九 — 32张牌、两张制、四门制
# ============================================================
WINDOW_GEOMETRY = "1150x750+50+10"

BG = "#17120f"
FELT = "#0b4540"
GOLD = "#e7d36c"
GOLD_DARK = "#8d742d"
TEXT = "#f7f1e4"
MUTED = "#c8bda9"
CLASSIC_TILE_ASPECT = 2.5


def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, "A_Tools/Account/saving_data.json")

def load_user_data():
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []

def save_user_data(users):
    try:
        with open(get_data_file_path(), "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
    except OSError:
        pass

def update_balance_in_json(username, new_balance):
    if not username or username == "Guest":
        return
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{float(new_balance):.2f}"
            break
    save_user_data(users)

class Dice:
    def __init__(self):
        self.value = 1

    def roll(self):
        self.value = secrets.randbelow(6) + 1
        return self.value

@dataclass(frozen=True)
class PaiGowTile:
    uid: str
    a: int
    b: int
    group: str
    zh_name: str
    en_name: str
    pair_rank: int       # 1 = best pair; 16 = lowest pair
    single_rank: int     # 17 = highest individual tile; 1 = lowest

    @property
    def dots(self):
        return self.a + self.b

    @property
    def shape(self):
        return (self.a, self.b)

    @property
    def is_gee(self):
        return self.group == "Gee Joon"

    def short_name(self):
        return f"{self.zh_name} {self.dots}"

def _tile(uid, a, b, group, zh, en, pair_rank, single_rank):
    return PaiGowTile(uid, a, b, group, zh, en, pair_rank, single_rank)

def build_pai_gow_set():
    """Build the traditional 32-tile Chinese domino set."""
    tiles = []

    # Gee Joon: two different tiles form the supreme pair.
    tiles.append(_tile("GJ-LUK", 2, 4, "Gee Joon", "至尊六", "Luk", 1, 3))
    tiles.append(_tile("GJ-SAAM", 1, 2, "Gee Joon", "至尊三", "Saam", 1, 1))

    # Eleven matched pairs, two identical physical tiles each.
    matched = [
        ((6, 6), "Teen", "天牌", "Teen", 2, 17),
        ((1, 1), "Day", "地牌", "Day", 3, 16),
        ((4, 4), "Yun", "人牌", "Yun", 4, 15),
        ((1, 3), "Gor", "鹅牌", "Gor", 5, 14),
        ((5, 5), "Mooy", "梅牌", "Mooy", 6, 13),
        ((3, 3), "Chong", "长三", "Chong", 7, 12),
        ((2, 2), "Bon", "板凳", "Bon", 8, 11),
        ((5, 6), "Foo", "斧头", "Foo", 9, 10),
        ((4, 6), "Ping", "红头十", "Ping", 10, 9),
        ((1, 6), "Tit", "长脚七", "Tit", 11, 8),
        ((1, 5), "Look", "大头六", "Look", 12, 7),
    ]
    for shape, group, zh, en, pair_rank, single_rank in matched:
        for copy_no in (1, 2):
            tiles.append(_tile(
                f"{group}-{copy_no}", shape[0], shape[1], group,
                zh, en, pair_rank, single_rank
            ))

    # Four mixed pairs; each consists of two different tile shapes.
    mixed = [
        ("Chop Gow", "杂九", "Chop Gow", 13, 6, [(3, 6), (4, 5)]),
        ("Chop Bot", "杂八", "Chop Bot", 14, 5, [(3, 5), (2, 6)]),
        ("Chop Chit", "杂七", "Chop Chit", 15, 4, [(3, 4), (2, 5)]),
        ("Chop Ng", "杂五", "Chop Ng", 16, 2, [(1, 4), (3, 2)]),
    ]
    for group, zh, en, pair_rank, single_rank, shapes in mixed:
        for idx, shape in enumerate(shapes, start=1):
            tiles.append(_tile(
                f"{group}-{idx}", shape[0], shape[1], group,
                zh, en, pair_rank, single_rank
            ))

    if len(tiles) != 32:
        raise RuntimeError(f"牌九牌组应为32张，实际为{len(tiles)}张")

    # A classic Chinese-domino set has 21 distinct faces: eleven faces occur
    # twice (the civil pairs) and the remaining ten occur once (the five
    # mixed/military pairs, including Gee Joon).  Validate the physical set,
    # rather than only its total, so a duplicated or omitted face cannot still
    # pass merely because the list happens to contain 32 entries.
    face_counts = {}
    for tile in tiles:
        face_counts[tile.shape] = face_counts.get(tile.shape, 0) + 1
    multiplicities = sorted(face_counts.values())
    if len(face_counts) != 21 or multiplicities != ([1] * 10 + [2] * 11):
        raise RuntimeError("牌九牌组必须由11种成对牌面和10种单张牌面组成")
    if len({tile.group for tile in tiles}) != 16:
        raise RuntimeError("牌九牌组必须构成16组传统对牌")
    return tiles

def is_named_pair(t1, t2):
    return t1.group == t2.group

@dataclass(frozen=True)
class WenzhouHandValue:
    """Two-tile Wenzhou Pai Gow value.

    named_rank:
        1..13 for the traditional Wenzhou named combinations, where 1 is best.
        None for an ordinary 0..9 point hand.
    points:
        Fixed dot total modulo 10.  Gee Joon tiles are NOT semi-wild here.
    high_single_rank:
        1..7 according to the Wenzhou single-tile ranking, where 1 is best.
        Ordinary zero has no single-tile rank and therefore uses 0.
    """
    name: str
    named_rank: int | None
    points: int
    high_single_rank: int

    @property
    def key(self):
        # Every named combination outranks every ordinary point hand.
        if self.named_rank is not None:
            return (1, 14 - self.named_rank, 8 - self.high_single_rank)
        if self.points == 0:
            return (0, 0, 0)
        return (0, self.points, 8 - self.high_single_rank)

WENZHOU_SINGLE_RANK = {
    # 1 = strongest.  Several physical tiles intentionally share one level.
    'Teen': 1,
    'Day': 2,
    'Yun': 3,
    'Gor': 4,
    'Mooy': 5,
    'Chong': 5,
    'Bon': 5,
    'Foo': 6,
    'Ping': 6,
    'Tit': 6,
    'Look': 6,
    'Chop Gow': 7,
    'Chop Bot': 7,
    'Chop Chit': 7,
    'Chop Ng': 7,
    'Gee Joon': 7,
}

WENZHOU_PAIR_RANK = {
    # Wenzhou grouping: equal numeric rank means equal pair class.
    'Teen': (1, '双天'),
    'Day': (2, '双地'),
    'Gee Joon': (3, '至尊'),
    'Yun': (4, '双人'),
    'Gor': (5, '双鹅'),
    'Mooy': (6, '双梅'),
    'Chong': (6, '双长三'),
    'Bon': (6, '双板凳'),
    'Foo': (7, '双斧头'),
    'Ping': (7, '双红头十'),
    'Tit': (7, '双高脚七'),
    'Look': (7, '双零霖六'),
    'Chop Gow': (8, '双杂九'),
    'Chop Bot': (8, '双杂八'),
    'Chop Chit': (8, '双杂七'),
    'Chop Ng': (8, '双杂五'),
}

def wenzhou_single_rank(tile):
    return WENZHOU_SINGLE_RANK[tile.group]

def ordered_wenzhou_hand(hand):
    """Put the stronger single tile first; ties keep a deterministic order."""
    return sorted(
        hand,
        key=lambda t: (wenzhou_single_rank(t), -t.dots, t.uid),
    )

def evaluate_wenzhou_hand(hand):
    """Evaluate one two-tile Wenzhou Pai Gow hand.

    Wenzhou rules used here:
      * Big Chicken 6 / Small Chicken 3 are fixed; no Gee Joon wild conversion.
      * Named combinations outrank ordinary point hands.
      * Wenzhou pair ranking starts 双天, 双地, 至尊.
      * The Wenzhou table uses 天九王, 天杠, 地杠, 天九, 地九.
      * Ordinary hands compare points first, then the strongest single-tile level.
      * Ordinary 0 has no single-tile level.
    """
    if len(hand) != 2:
        raise ValueError('温州牌九每门必须恰好2张牌')

    t1, t2 = hand
    groups = {t1.group, t2.group}
    dots = {t1.dots, t2.dots}
    high_rank = min(wenzhou_single_rank(t1), wenzhou_single_rank(t2))

    if is_named_pair(t1, t2):
        rank, name = WENZHOU_PAIR_RANK[t1.group]
        return WenzhouHandValue(name, rank, (t1.dots + t2.dots) % 10, high_rank)

    # Traditional Wenzhou named combinations.  Note that the published Wenzhou
    # ranking uses 天九王 but does not insert a separate 地王 class.
    if 'Teen' in groups and 9 in dots:
        return WenzhouHandValue('天九王', 9, 1, high_rank)
    if 'Teen' in groups and 8 in dots:
        return WenzhouHandValue('天杠', 10, 0, high_rank)
    if 'Day' in groups and 8 in dots:
        return WenzhouHandValue('地杠', 11, 0, high_rank)
    if 'Teen' in groups and 7 in dots:
        return WenzhouHandValue('天九', 12, 9, high_rank)
    if 'Day' in groups and 7 in dots:
        return WenzhouHandValue('地九', 13, 9, high_rank)

    points = (t1.dots + t2.dots) % 10
    if points == 0:
        high_rank = 0
    return WenzhouHandValue(f'{points}点', None, points, high_rank)

def compare_wenzhou_hands(player_hand, dealer_hand):
    """Return 1 if player is larger, -1 if smaller, 0 if the comparison ties.

    A returned tie is settled as 惜败 (banker advantage).  Ordinary 0 vs 0 is
    also a banker win and intentionally has no single-tile tie break.
    """
    p = evaluate_wenzhou_hand(player_hand)
    d = evaluate_wenzhou_hand(dealer_hand)
    if p.key > d.key:
        return 1
    if p.key < d.key:
        return -1
    return 0



class WenzhouPaiGowGUI(tk.Frame):
    ROOT_BG = "#1B3D31"
    PANEL_BG = "#F2E6C9"
    HEADER_BG = "#D8B46A"
    TITLE_FG = "#2A1B08"
    SELECT_BORDER = "#87CEFA"
    HAND_WIN_BG = "#00ff00"
    HAND_LOSE_BG = "#ff0000"
    HAND_NEUTRAL_BG = "#173f3a"

    DEALER_ZONE = (24, 128, 726, 303)
    SHOE_ZONE = (24, 313, 726, 505)
    DOOR_ZONES = {
        1: (24, 515, 250, 719),
        2: (262, 515, 488, 719),
        3: (500, 515, 726, 719),
    }
    POSITION_NAMES = {0: '庄家', 1: '顺门', 2: '出门', 3: '到门'}
    BET_SIDES = ('win', 'lose')
    WIN_MULTIPLIER = 1.99
    LOSE_MULTIPLIER = 1.93
    HAND_W = 50
    HAND_H = 125

    NORMAL_MIN_BET = 10
    NORMAL_MAX_BET = 25000
    HIGH_MIN_BET = 100
    HIGH_MAX_BET = 100000


    TILE_THEMES = {
        'black': {
            'face': '#101010',
            'back': '#161918',
            'outline': '#d8ccb5',
            'shadow': '#050505',
            'base_pip': '#f4f1e8',
            'pip_outline': '#242424',
            'back_text': GOLD_DARK,
        },
        'white': {
            'face': '#f3eee2',
            'back': '#e7dfcf',
            'outline': '#6b6258',
            'shadow': '#6a645c',
            'base_pip': '#151515',
            'pip_outline': '#403a34',
            'back_text': '#6f5421',
        },
    }
    TRADITIONAL_PIP_PATTERNS = {
        ('Gee Joon', (2, 4)): [
            (0.304, 0.122, 'base'), (0.697, 0.122, 'base'),
            (0.707, 0.726, 'red'), (0.304, 0.727, 'red'),
            (0.304, 0.887, 'red'), (0.707, 0.887, 'red'),
        ],
        ('Gee Joon', (1, 2)): [
            (0.507, 0.115, 'red'),
            (0.305, 0.885, 'base'), (0.702, 0.885, 'base'),
        ],
        ('Teen', (6, 6)): [
            (0.320, 0.116, 'base'), (0.709, 0.118, 'red'),
            (0.321, 0.270, 'base'), (0.710, 0.273, 'red'),
            (0.321, 0.425, 'base'), (0.710, 0.426, 'red'),
            (0.323, 0.577, 'red'),  (0.711, 0.581, 'base'),
            (0.322, 0.733, 'red'),  (0.710, 0.733, 'base'),
            (0.323, 0.887, 'red'),  (0.711, 0.889, 'base'),
        ],
        ('Day', (1, 1)): [
            (0.502, 0.115, 'red'), (0.502, 0.886, 'red'),
        ],
        ('Yun', (4, 4)): [
            (0.698, 0.120, 'red'), (0.301, 0.122, 'red'),
            (0.698, 0.372, 'red'), (0.299, 0.375, 'red'),
            (0.697, 0.633, 'red'), (0.301, 0.636, 'red'),
            (0.697, 0.884, 'red'), (0.301, 0.886, 'red'),
        ],
        ('Gor', (1, 3)): [
            (0.510, 0.115, 'red'),
            (0.281, 0.571, 'base'), (0.501, 0.731, 'base'),
            (0.700, 0.884, 'base'),
        ],
        ('Mooy', (5, 5)): [
            (0.320, 0.118, 'base'), (0.712, 0.119, 'base'),
            (0.515, 0.276, 'base'),
            (0.320, 0.427, 'base'), (0.711, 0.427, 'base'),
            (0.321, 0.580, 'base'), (0.711, 0.582, 'base'),
            (0.516, 0.743, 'base'),
            (0.321, 0.889, 'base'), (0.711, 0.891, 'base'),
        ],
        ('Chong', (3, 3)): [
            (0.510, 0.118, 'base'), (0.511, 0.318, 'base'),
            (0.733, 0.499, 'base'), (0.308, 0.502, 'base'),
            (0.509, 0.684, 'base'), (0.510, 0.889, 'base'),
        ],
        ('Bon', (2, 2)): [
            (0.321, 0.118, 'base'), (0.715, 0.118, 'base'),
            (0.322, 0.889, 'base'), (0.715, 0.891, 'base'),
        ],
        ('Foo', (5, 6)): [
            (0.321, 0.118, 'base'), (0.713, 0.118, 'base'),
            (0.517, 0.276, 'base'),
            (0.321, 0.427, 'base'), (0.713, 0.427, 'base'),
            (0.321, 0.580, 'base'), (0.713, 0.583, 'base'),
            (0.713, 0.736, 'base'), (0.321, 0.738, 'base'),
            (0.321, 0.889, 'base'), (0.714, 0.891, 'base'),
        ],
        ('Ping', (4, 6)): [
            (0.308, 0.119, 'red'), (0.712, 0.119, 'red'),
            (0.309, 0.279, 'red'), (0.711, 0.280, 'red'),
            (0.314, 0.580, 'base'), (0.707, 0.582, 'base'),
            (0.707, 0.736, 'base'), (0.315, 0.738, 'base'),
            (0.313, 0.889, 'base'), (0.708, 0.891, 'base'),
        ],
        ('Tit', (1, 6)): [
            (0.516, 0.119, 'red'),
            (0.319, 0.580, 'base'), (0.711, 0.583, 'base'),
            (0.712, 0.736, 'base'), (0.320, 0.738, 'base'),
            (0.320, 0.889, 'base'), (0.712, 0.892, 'base'),
        ],
        ('Look', (1, 5)): [
            (0.516, 0.117, 'red'),
            (0.322, 0.578, 'base'), (0.712, 0.580, 'base'),
            (0.511, 0.736, 'base'),
            (0.321, 0.887, 'base'), (0.713, 0.889, 'base'),
        ],
        ('Chop Gow', (4, 5)): [
            (0.314, 0.115, 'red'), (0.718, 0.115, 'red'),
            (0.717, 0.275, 'red'), (0.315, 0.276, 'red'),
            (0.319, 0.576, 'base'), (0.712, 0.578, 'base'),
            (0.527, 0.734, 'base'),
            (0.320, 0.885, 'base'), (0.712, 0.888, 'base'),
        ],
        ('Chop Gow', (3, 6)): [
            (0.305, 0.119, 'base'), (0.495, 0.258, 'base'),
            (0.714, 0.409, 'base'),
            (0.318, 0.579, 'base'), (0.707, 0.581, 'base'),
            (0.318, 0.732, 'base'), (0.701, 0.734, 'base'),
            (0.318, 0.888, 'base'), (0.707, 0.889, 'base'),
        ],
        ('Chop Bot', (2, 6)): [
            (0.319, 0.117, 'base'), (0.710, 0.119, 'base'),
            (0.320, 0.579, 'base'), (0.709, 0.581, 'base'),
            (0.710, 0.735, 'base'), (0.318, 0.737, 'base'),
            (0.319, 0.890, 'base'), (0.710, 0.891, 'base'),
        ],
        ('Chop Bot', (3, 5)): [
            (0.321, 0.119, 'base'), (0.511, 0.258, 'base'),
            (0.731, 0.409, 'base'),
            (0.321, 0.578, 'base'), (0.711, 0.581, 'base'),
            (0.522, 0.736, 'base'),
            (0.321, 0.887, 'base'), (0.712, 0.890, 'base'),
        ],
        ('Chop Chit', (2, 5)): [
            (0.316, 0.118, 'base'), (0.708, 0.121, 'base'),
            (0.316, 0.578, 'base'), (0.708, 0.581, 'base'),
            (0.508, 0.737, 'base'),
            (0.317, 0.888, 'base'), (0.710, 0.890, 'base'),
        ],
        ('Chop Chit', (3, 4)): [
            (0.292, 0.117, 'base'), (0.475, 0.270, 'base'),
            (0.682, 0.427, 'base'),
            (0.285, 0.726, 'red'), (0.687, 0.726, 'red'),
            (0.283, 0.886, 'red'), (0.687, 0.886, 'red'),
        ],
        ('Chop Ng', (1, 4)): [
            (0.506, 0.124, 'red'),
            (0.690, 0.723, 'red'), (0.285, 0.724, 'red'),
            (0.287, 0.884, 'red'), (0.689, 0.884, 'red'),
        ],
        ('Chop Ng', (3, 2)): [
            (0.288, 0.112, 'base'), (0.490, 0.265, 'base'),
            (0.680, 0.423, 'base'),
            (0.289, 0.880, 'base'), (0.680, 0.883, 'base'),
        ],
    }

    def __init__(self, parent, balance=10000, user='Guest', on_back=None, on_balance_change=None):
        super().__init__(parent, bg=BG, width=1150, height=750)
        self.pack_propagate(False)
        self.username = user or 'Guest'
        self.balance = float(balance)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self._closing = False

        top = self.winfo_toplevel()
        try:
            top.geometry(WINDOW_GEOMETRY)
            top.resizable(False, False)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(self, width=1150, height=750, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.tile_theme = 'white' if secrets.randbelow(2) == 0 else 'black'
        self._render_tile_theme_override = None

        self.dice_objects = [Dice(), Dice()]
        self.dice_images_animation = []
        self.dice_images_small = []
        self.animation_dice_items = []
        self.animation_dice_base_positions = []
        self.animation_running = True
        self.animation_frames_left = 0
        self.animation_final_dice = None
        self.animation_after_id = None

        self.selected_chip = 10
        self.high_bet_mode = False
        self.stage = 'betting'
        self.status = '新温州牌九牌靴正在进入…'
        self.last_result = ''
        self.last_return = 0.0
        self.ante = 0.0

        self.full_tiles = []
        self.stacks = []
        self.pair_stacks = []
        self.position_hands = {}
        self.deal_wall_visible = False
        self.shoe_ready_for_next_round = False
        self.deal_stack_markers = {}
        self.deal_start_index = None
        self.deal_order = []
        self.dice_result = []
        self.flip_anim = None

        self.bets = {(door, side): 0.0 for door in (1, 2, 3) for side in self.BET_SIDES}
        self.last_bets = dict(self.bets)
        self.round_bets = dict(self.bets)
        self.bet_result_values = {}
        self.winning_cells = set()
        self.door_hands = {0: [], 1: [], 2: [], 3: []}
        self.door_dealt_visible = {0: False, 1: False, 2: False, 3: False}
        self.door_face_up = {0: False, 1: False, 2: False, 3: False}
        self.door_tile_face_up = {pos: [False, False] for pos in (0, 1, 2, 3)}
        self.door_outcomes = {1: None, 2: None, 3: None}
        self.door_result_text = {1: '', 2: '', 3: ''}
        self.bet_cell_labels = {}
        self.door_header_items = {}
        self.door_result_items = {}
        self.round_total_bet = 0.0
        self.limit_card_widgets = []
        self.chip_container = None
        self.chip_canvases = {}

        self.create_dice_images()
        self.create_static_ui()
        self.update_display()
        self.after(90, self._animate_initial_shoe_left)


    def create_dice_images(self):
        self.dice_images_animation = []
        self.dice_images_small = []

        def make_die(size, number):
            image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            margin = max(1, size // 28)
            radius = max(3, size // 6)
            die_fill = "#f0f0e9"
            die_outline = "#222"
            pip_color = "#d21e2b" if number in (1, 4) else "#111"
            draw.rounded_rectangle(
                (margin, margin, size - margin - 1, size - margin - 1),
                radius=radius,
                fill=die_fill,
                outline=die_outline,
                width=max(1, size // 18),
            )
            quarter = size // 4
            half = size // 2
            three_quarter = size - quarter
            positions = {
                1: [(half, half)],
                2: [(quarter, quarter), (three_quarter, three_quarter)],
                3: [(quarter, quarter), (half, half), (three_quarter, three_quarter)],
                4: [(quarter, quarter), (three_quarter, quarter),
                    (quarter, three_quarter), (three_quarter, three_quarter)],
                5: [(quarter, quarter), (three_quarter, quarter), (half, half),
                    (quarter, three_quarter), (three_quarter, three_quarter)],
                6: [(quarter, size // 5), (three_quarter, size // 5),
                    (quarter, half), (three_quarter, half),
                    (quarter, size - size // 5), (three_quarter, size - size // 5)],
            }
            pip = max(1, size // 11)
            for x, y in positions[number]:
                draw.ellipse((x - pip, y - pip, x + pip, y + pip), fill=pip_color)
            return ImageTk.PhotoImage(image)

        for number in range(1, 7):
            self.dice_images_animation.append(make_die(62, number))
            self.dice_images_small.append(make_die(24, number))

    def secure_shuffle(self, seq):
        seq = list(seq)
        for i in range(len(seq) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            seq[i], seq[j] = seq[j], seq[i]
        return seq

    def _bet_cursor(self, widget):
        try:
            widget.config(cursor='hand2' if self.stage == 'betting' else 'no')
        except tk.TclError:
            widget.config(cursor='hand2' if self.stage == 'betting' else 'X_cursor')

    def select_chip(self, value):
        if self.stage != 'betting':
            return
        self.selected_chip = value
        self._update_chip_ui()

    def _update_chip_ui(self):
        for value, (cv, oval) in getattr(self, 'chip_canvases', {}).items():
            selected = self.stage == 'betting' and value == self.selected_chip
            cv.itemconfigure(oval, outline='#2f00ff' if selected else 'black', width=3 if selected else 1)
            try:
                cv.config(cursor='hand2' if self.stage == 'betting' else 'no')
            except tk.TclError:
                cv.config(cursor='hand2' if self.stage == 'betting' else 'X_cursor')

    @staticmethod
    def _fmt(value):
        value = float(value)
        if abs(value - round(value)) < 1e-9:
            return f"{value:,.0f}"
        return f"{value:,.2f}"

    def _persist_balance(self):
        update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def on_close(self):
        self._closing = True
        if self.animation_after_id:
            try:
                self.after_cancel(self.animation_after_id)
            except tk.TclError:
                pass
        self._persist_balance()
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            try:
                self.winfo_toplevel().destroy()
            except tk.TclError:
                pass


    def _active_tile_theme(self):
        name = self._render_tile_theme_override or self.tile_theme
        return self.TILE_THEMES[name]

    def _tile_colour_name(self, theme=None):
        return '白色' if (theme or self.tile_theme) == 'white' else '黑色'

    @staticmethod
    def _opposite_tile_theme(theme):
        return 'black' if theme == 'white' else 'white'

    def _traditional_pattern(self, tile):
        key = (tile.group, tuple(tile.shape))
        pattern = self.TRADITIONAL_PIP_PATTERNS.get(key)
        if pattern is not None:
            return pattern

        # Defensive fallback only.  Every tile in build_pai_gow_set() should have
        # an explicit physical pattern above.
        positions = {
            1: [(0.50, 0.23)],
            2: [(0.31, 0.23), (0.70, 0.23)],
            3: [(0.31, 0.18), (0.50, 0.29), (0.70, 0.41)],
            4: [(0.31, 0.16), (0.70, 0.16), (0.31, 0.39), (0.70, 0.39)],
            5: [(0.31, 0.15), (0.70, 0.15), (0.50, 0.28), (0.31, 0.41), (0.70, 0.41)],
            6: [(0.31, 0.14), (0.70, 0.14), (0.31, 0.28), (0.70, 0.28),
                (0.31, 0.42), (0.70, 0.42)],
        }
        out = []
        for half_index, number in enumerate(tile.shape):
            y_offset = 0.0 if half_index == 0 else 0.50
            for px, py in positions[number]:
                colour = 'red' if number in (1, 4) else 'base'
                out.append((px, py * 0.5 + y_offset, colour))
        return out

    def _draw_face_pips(self, canvas, tile, point_transform, base_w, base_h, tags, compact=False):
        theme = self._active_tile_theme()
        base_colour = theme['base_pip']
        red_colour = '#e43838'
        radius = max(1.5, min(6.2, min(base_w, base_h) / (10.5 if not compact else 8.5)))

        for ux, uy, colour_kind in self._traditional_pattern(tile):
            # Pattern coordinates are expressed from the top-left of an upright tile.
            lx = (ux - 0.5) * base_w
            ly = (uy - 0.5) * base_h
            px, py = point_transform(lx, ly)
            fill = red_colour if colour_kind == 'red' else base_colour
            canvas.create_oval(
                px - radius, py - radius, px + radius, py + radius,
                fill=fill, outline=theme['pip_outline'], width=1, tags=tags,
            )

    def _draw_rotated_face_tile(self, cx, cy, base_w, base_h, angle_deg, tile,
                                selected=False, selection_role=None, tag='tile',
                                extra_tag='tile_dynamic', compact=False, canvas=None):
        c = canvas or self.canvas
        tags = (tag, extra_tag) if extra_tag else (tag,)
        angle = math.radians(angle_deg)
        theme = self._active_tile_theme()
        outline = self.SELECT_BORDER if selected else theme['outline']
        width = 4 if selected else max(1, int(min(base_w, base_h) / 32))

        def tr(lx, ly):
            ca, sa = math.cos(angle), math.sin(angle)
            return cx + lx * ca - ly * sa, cy + lx * sa + ly * ca

        corners = [
            tr(-base_w / 2, -base_h / 2), tr(base_w / 2, -base_h / 2),
            tr(base_w / 2, base_h / 2), tr(-base_w / 2, base_h / 2),
        ]
        flat = [v for point in corners for v in point]
        c.create_polygon(*flat, fill=theme['face'], outline=outline, width=width, tags=tags)
        # Traditional Pai Gow tiles have no visible divider line between the two ends.
        self._draw_face_pips(c, tile, tr, base_w, base_h, tags, compact=compact)

    def draw_tile(self, x, y, w, h, tile, face_up=True, selected=False, order_no=None,
                  selection_role=None, tag='tile', extra_tag='tile_dynamic', show_name=True,
                  compact=False, canvas=None):
        c = canvas or self.canvas
        tags = (tag, extra_tag) if extra_tag else (tag,)
        theme = self._active_tile_theme()

        if face_up and w > h:
            self._draw_rotated_face_tile(
                x + w / 2, y + h / 2, h, w, 90, tile,
                selected=selected, selection_role=selection_role,
                tag=tag, extra_tag=extra_tag, compact=compact, canvas=c,
            )
            return

        outline = self.SELECT_BORDER if selected else theme['outline']
        width = 4 if selected else max(1, int(min(w, h) / 32))
        shadow = max(1, min(4, int(min(w, h) / 18)))
        c.create_rectangle(
            x + shadow, y + shadow, x + w + shadow, y + h + shadow,
            fill=theme['shadow'], outline='', tags=tags,
        )
        body_fill = theme['face'] if face_up else theme['back']
        c.create_rectangle(x, y, x + w, y + h, fill=body_fill,
                           outline=outline, width=width, tags=tags)

        if not face_up:
            inset = max(3, min(8, int(min(w, h) / 6)))
            # A restrained inset keeps the back readable without changing its set colour.
            c.create_rectangle(
                x + inset, y + inset, x + w - inset, y + h - inset,
                fill=theme['back'], outline=theme['back_text'], width=1, tags=tags,
            )
            if compact or (w >= 45 and h >= 60):
                font_size = max(5, min(10, int(min(w, h) * (0.24 if compact else 0.20))))
                c.create_text(
                    x + w / 2, y + h / 2, text='牌\n九', justify='center',
                    font=('Arial', font_size, 'bold'), fill=theme['back_text'], tags=tags,
                )
            return

        cx = x + w / 2
        cy = y + h / 2

        def tr(lx, ly):
            return cx + lx, cy + ly

        self._draw_face_pips(c, tile, tr, w, h, tags, compact=compact)

    def wall_tile_rect(self, tile_index):
        x0, y0, w, h, gap_x, gap_y = self.wall_geometry()
        col = tile_index // 2
        row = tile_index % 2
        return x0 + col * (w + gap_x), y0 + row * (h + gap_y), w, h

    def _snapshot_wall_rect(self, tile_index, offset_x=0.0):
        x, y, w, h = self.wall_tile_rect(tile_index)
        return x + offset_x, y, w, h


    def _instruction_tile(
        self,
        canvas,
        tile,
        cx,
        cy,
        horizontal=False,
        scale=1.0,
        outline=False
    ):
        """
        说明页专用骨牌绘制。

        重要：
        - cx / cy 永远表示“骨牌中心点”，不是左上角。
        - 因此无论缩放、直放、横放，骨牌中心不会走位。
        - horizontal=True 时不是重新排列点阵，
        而是把原本直立的同一张骨牌整体顺时针旋转90°。
        """

        base_w = max(24, int(round(46 * scale)))
        base_h = int(round(base_w * CLASSIC_TILE_ASPECT))

        # =========================
        # 横牌：整张物理旋转90°
        # =========================
        if horizontal:
            self._draw_rotated_face_tile(
                cx,
                cy,
                base_w,
                base_h,
                90,
                tile,
                selected=outline,
                selection_role='back',
                tag='instruction_tile',
                extra_tag=None,
                compact=False,
                canvas=canvas,
            )

            # 返回最终可视宽高
            return base_h, base_w

        # =========================
        # 直牌
        # =========================
        self.draw_tile(
            cx - base_w / 2,
            cy - base_h / 2,
            base_w,
            base_h,
            tile,
            face_up=True,
            selected=outline,
            selection_role='back',
            tag='instruction_tile',
            extra_tag=None,
            show_name=False,
            compact=False,
            canvas=canvas,
        )

        return base_w, base_h

    @staticmethod
    def _instruction_find_tile(
        tiles,
        *,
        group=None,
        dots=None,
        shape=None,
        exclude_groups=()
    ):
        """
        说明页寻找指定骨牌。

        支持：
        group='Teen'
        dots=9
        shape=(3, 6)

        可以精确指定点阵，方便说明：
        9点牌 = 3-6 / 4-5
        8点牌 = 4-4 / 3-5 / 2-6
        7点牌 = 1-6 / 3-4 / 2-5
        """
        for tile in tiles:

            if group is not None and tile.group != group:
                continue

            if dots is not None and tile.dots != dots:
                continue

            if shape is not None and tuple(tile.shape) != tuple(shape):
                continue

            if tile.group in exclude_groups:
                continue

            return tile

        raise LookupError(
            f'找不到牌九示例牌 '
            f'group={group!r}, dots={dots!r}, shape={shape!r}'
        )

    def create_static_ui(self):
        c = self.canvas
        c.create_rectangle(0, 0, 1150, 750, fill=BG, outline='', tags='static')
        c.create_rectangle(10, 8, 740, 740, fill=FELT, outline=GOLD_DARK, width=3, tags='static')
        c.create_text(375, 27, text='温州牌九', font=('Arial', 19, 'bold'), fill=GOLD, tags='static')

        # Two-dice strip.
        c.create_rectangle(24, 48, 726, 118, fill='#123c38', outline='#6e9185', width=1, tags='static')
        c.create_text(38, 83, anchor='w', text='两骰', font=('Arial', 11, 'bold'),
                      fill='#d9efe8', tags='static')
        self.animation_dice_base_positions = [(142, 83), (218, 83)]
        self.animation_dice_items = [
            c.create_image(x, y, image=self.dice_images_animation[5], tags=('dice', 'static'))
            for x, y in self.animation_dice_base_positions
        ]
        c.create_text(180, 83, text='+', font=('Arial', 17, 'bold'), fill=TEXT, tags='static')
        self.dice_summary_item = c.create_text(
            270, 83, anchor='w', text='= --点　｜　等待摇骰',
            font=('Arial', 13, 'bold'), fill=TEXT, tags='static'
        )

        # Dealer zone.
        x0, y0, x1, y1 = self.DEALER_ZONE
        c.create_rectangle(x0, y0, x1, y1, fill='#103f39', outline='#5a887a', width=2, tags='static')
        self.dealer_header_item = c.create_text(
            x0 + 14, y0 + 18, anchor='w', text='庄家',
            font=('Arial', 14, 'bold'), fill=TEXT, tags='static'
        )
        # Hidden compatibility item for inherited code paths that still expect it.
        self.player_header_item = c.create_text(0, 0, text='', state='hidden', tags='static')

        # Shoe base.  Live wall is redrawn on top.
        sx0, sy0, sx1, sy1 = self.SHOE_ZONE
        c.create_rectangle(sx0, sy0, sx1, sy1, fill='#0a3834', outline='#557b70', width=1, tags='static')

        # Three player doors.
        for pos in (1, 2, 3):
            x0, y0, x1, y1 = self.DOOR_ZONES[pos]
            c.create_rectangle(x0, y0, x1, y1, fill='#134942', outline='#5a887a', width=2, tags='static')
            self.door_header_items[pos] = c.create_text(
                x0 + 12, y0 + 18, anchor='w', text=self.POSITION_NAMES[pos],
                font=('Arial', 13, 'bold'), fill=TEXT, tags='static'
            )
            self.door_result_items[pos] = c.create_text(
                (x0 + x1) / 2, y1 - 15, text='', width=(x1 - x0 - 18),
                font=('Arial', 9, 'bold'), fill=GOLD, state='hidden', tags='static'
            )

        self.result_item = c.create_text(375, 718, text='', state='hidden', tags='static')
        self.create_right_panel_widgets()

    def create_right_panel_widgets(self):
        panel = tk.Frame(self, bg=self.ROOT_BG, width=400, height=734)
        panel.place(x=750, y=8, width=400, height=734)
        panel.pack_propagate(False)
        self.right_panel = panel

        def card(title, title_size=13):
            outer = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
            outer.pack(fill=tk.X, pady=3, padx=(0, 1))
            header = tk.Frame(outer, bg=self.HEADER_BG)
            header.pack(fill=tk.X)
            title_label = tk.Label(header, text=title, font=('Arial', title_size, 'bold'),
                                   bg=self.HEADER_BG, fg=self.TITLE_FG)
            title_label.pack(pady=3)
            return outer, header, title_label

        info, _, _ = card('温州牌九', 14)
        body = tk.Frame(info, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=11, pady=5)
        self.balance_label = tk.Label(body, text='余额: $0.00', font=('Arial', 15, 'bold'),
                                      bg=self.PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body, text='下注阶段', font=('Arial', 13, 'bold'),
                                    bg=self.PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # Clickable limit card, following the uploaded Three Card Poker interaction.
        limit, limit_header, limit_title = card('下注上限', 12)
        limit_body = tk.Frame(limit, bg=self.PANEL_BG)
        limit_body.pack(fill=tk.X, padx=10, pady=6)
        limit_grid = tk.Frame(limit_body, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
        limit_grid.pack(fill=tk.X)
        for col in range(2):
            limit_grid.columnconfigure(col, weight=1)
        limit_headers = []
        for col, title in enumerate(('下注最低', '下注最高')):
            lbl = tk.Label(limit_grid, text=title, font=('Arial', 10, 'bold'),
                           bg=self.PANEL_BG, fg=self.TITLE_FG,
                           borderwidth=1, relief=tk.SOLID, pady=3)
            lbl.grid(row=0, column=col, sticky='nsew')
            limit_headers.append(lbl)
        self.min_bet_label = tk.Label(
            limit_grid, text='$10', font=('Arial', 11, 'bold'),
            bg=self.PANEL_BG, fg='#A88100', borderwidth=1, relief=tk.SOLID, pady=3
        )
        self.min_bet_label.grid(row=1, column=0, sticky='nsew')
        self.max_bet_label = tk.Label(
            limit_grid, text='$25,000', font=('Arial', 11, 'bold'),
            bg=self.PANEL_BG, fg='#A88100', borderwidth=1, relief=tk.SOLID, pady=3
        )
        self.max_bet_label.grid(row=1, column=1, sticky='nsew')
        self.limit_card_widgets = [limit, limit_header, limit_title, limit_body, limit_grid,
                                   *limit_headers, self.min_bet_label, self.max_bet_label]
        for w in self.limit_card_widgets:
            w.bind('<Button-1>', self.toggle_high_bet_limits)
            try:
                w.config(cursor='hand2')
            except tk.TclError:
                pass

        # Chips and the unchanged door-bet grid share one card.
        combined, _, _ = card('筹码与下注', 12)
        body = tk.Frame(combined, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=8, pady=5)

        chip_row = tk.Frame(body, bg=self.PANEL_BG)
        chip_row.pack(fill=tk.X, pady=(0, 7))
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)
        self.chip_container = chip_row
        self.chip_canvases = {}
        self._rebuild_chips()

        grid = tk.Frame(body, bg=self.PANEL_BG)
        # Fixed pixel geometry: payout text can grow, but the six betting cells never do.
        # 64 + 158 + 158 = 380px, matching the previous visual footprint inside this card.
        grid.pack(anchor='center')
        grid.configure(width=380, height=160)
        grid.grid_propagate(False)
        grid.columnconfigure(0, weight=0, minsize=64)
        grid.columnconfigure(1, weight=0, minsize=158)
        grid.columnconfigure(2, weight=0, minsize=158)
        grid.rowconfigure(0, weight=0, minsize=36)
        for fixed_row in (1, 2, 3):
            grid.rowconfigure(fixed_row, weight=0, minsize=39)
        headers = ('', '获胜\n0.99 : 1', '惜败\n0.93 : 1')
        for col, text in enumerate(headers):
            tk.Label(grid, text=text, font=('Arial', 10, 'bold'), bg=self.PANEL_BG,
                     fg=self.TITLE_FG, relief=tk.SOLID, bd=1, pady=3).grid(
                row=0, column=col, sticky='nsew'
            )

        for row_no, pos in enumerate((1, 2, 3), start=1):
            tk.Label(grid, text=self.POSITION_NAMES[pos], font=('Arial', 11, 'bold'),
                     bg=self.PANEL_BG, fg=self.TITLE_FG, relief=tk.SOLID, bd=1,
                     pady=8).grid(row=row_no, column=0, sticky='nsew')
            for col, side in ((1, 'win'), (2, 'lose')):
                # Width/height are fixed through the grid cell, so values such as
                # $193000.00 cannot resize the betting table.  Cursor/bind behaviour
                # below the limit card is intentionally left unchanged.
                lbl = tk.Label(grid, text='$0', font=('Arial', 12, 'bold'),
                               bg='white', fg='black', relief=tk.SUNKEN, bd=2,
                               anchor='center', cursor='hand2', width=1, height=1)
                lbl.grid(row=row_no, column=col, sticky='nsew', padx=1, pady=1)
                lbl.bind('<Button-1>', lambda _e, p=pos, s=side: self.add_bet_cell(p, s))
                lbl.bind('<Button-3>', lambda _e, p=pos, s=side: self.clear_bet_cell(p, s))
                lbl.bind('<Enter>', lambda _e, p=pos, s=side, w=lbl: self._update_bet_cell_cursor(p, s, w))
                lbl.bind('<Leave>', lambda _e, w=lbl: w.config(cursor=''))
                self.bet_cell_labels[(pos, side)] = lbl

        action = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID, height=133)
        action.pack(fill=tk.X, pady=3, padx=(0, 1))
        action.pack_propagate(False)
        header = tk.Frame(action, bg=self.HEADER_BG, height=28)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text='操作', font=('Arial', 13, 'bold'),
                 bg=self.HEADER_BG, fg=self.TITLE_FG).pack(expand=True)
        body = tk.Frame(action, bg=self.PANEL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.status_label = tk.Label(
            body, text='选择门注后开始游戏', font=('Arial', 10, 'bold'),
            bg=self.PANEL_BG, fg=self.TITLE_FG, wraplength=370,
            justify=tk.CENTER, height=3,
        )
        self.status_label.pack(fill=tk.X)
        self.action_frame = tk.Frame(body, bg=self.PANEL_BG, height=40)
        self.action_frame.pack(fill=tk.X)
        self.action_frame.pack_propagate(False)

        summary = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
        summary.pack(fill=tk.X, pady=3, padx=(0, 1))
        body = tk.Frame(summary, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=10, pady=5)
        self.current_bet_label = tk.Label(body, text='本局下注: $0', font=('Arial', 11, 'bold'),
                                          bg=self.PANEL_BG, fg='black')
        self.current_bet_label.pack(anchor='w')
        row = tk.Frame(body, bg=self.PANEL_BG)
        row.pack(fill=tk.X, pady=(2, 0))
        self.last_win_label = tk.Label(row, text='上局返还: $0', font=('Arial', 11, 'bold'),
                                       bg=self.PANEL_BG, fg='black')
        self.last_win_label.pack(side=tk.LEFT)
        tk.Button(row, text='ℹ️', command=self.show_detailed_rules,
                  bg='#4B8BBE', fg='white', font=('Arial', 9, 'bold'),
                  width=3, relief=tk.FLAT).pack(side=tk.RIGHT)

        self._update_limits_display()

    def _current_min_bet(self):
        return self.HIGH_MIN_BET if self.high_bet_mode else self.NORMAL_MIN_BET

    def _current_max_bet(self):
        return self.HIGH_MAX_BET if self.high_bet_mode else self.NORMAL_MAX_BET

    def _bets_fit_limits(self, source):
        total = self._bet_total(source)
        if total == 0:
            return True
        return self._current_min_bet() <= total <= self._current_max_bet()

    def toggle_high_bet_limits(self, event=None):
        if self.stage != 'betting' or self.animation_running:
            return
        if not self.high_bet_mode:
            current_password = time.strftime('%H%M')
            pwd = simpledialog.askstring('高额下注', '请输入密码：', parent=self.winfo_toplevel())
            if pwd is None:
                return
            if pwd.strip() != current_password:
                messagebox.showerror('错误', '密码错误', parent=self.winfo_toplevel())
                return
            self.high_bet_mode = True
        else:
            self.high_bet_mode = False

        self.bets = {(door, side): 0.0 for door in (1, 2, 3) for side in self.BET_SIDES}
        self.ante = 0.0
        self.bet_result_values = {}
        self.winning_cells = set()
        self._update_limits_display()
        self._rebuild_chips()
        mode_name = '高额下注' if self.high_bet_mode else '正常下注'
        self.status = f'已切换为{mode_name}模式。'
        self.update_display()

    def _update_limits_display(self):
        if not hasattr(self, 'min_bet_label'):
            return
        self.min_bet_label.config(text=f'${self._current_min_bet():,}')
        self.max_bet_label.config(text=f'${self._current_max_bet():,}')

    def _rebuild_chips(self):
        if self.chip_container is None:
            return
        for widget in self.chip_container.winfo_children():
            widget.destroy()
        self.chip_canvases = {}

        if self.high_bet_mode:
            chip_configs = [
                (100, '$100', '#181818', 'white'),
                (500, '$500', '#e66fb1', 'black'),
                (1000, '$1K', '#f2f2e8', 'black'),
                (5000, '$5K', '#e52929', 'white'),
                (10000, '$10K', '#00fbff', 'black'),
                (50000, '$50K', '#00ffae', 'black'),
            ]
            default = 100
        else:
            chip_configs = [
                (10, '$10', '#f4a621', 'black'),
                (25, '$25', '#22d84b', 'black'),
                (100, '$100', '#181818', 'white'),
                (500, '$500', '#e66fb1', 'black'),
                (1000, '$1K', '#f2f2e8', 'black'),
                (2500, '$2.5K', '#e52929', 'white'),
            ]
            default = 10

        for col, (value, text, colour, fg) in enumerate(chip_configs):
            cell = tk.Frame(self.chip_container, bg=self.PANEL_BG)
            cell.grid(row=0, column=col, sticky='nsew', padx=2)
            cv = tk.Canvas(cell, width=48, height=48, bg=self.PANEL_BG, highlightthickness=0)
            cv.pack(anchor='center')
            oval = cv.create_oval(2, 2, 46, 46, fill=colour, outline='black', width=1)
            cv.create_text(24, 24, text=text, fill=fg, font=('Arial', 9, 'bold'))
            cv.bind('<Button-1>', lambda _e, v=value: self.select_chip(v))
            cv.bind('<Enter>', lambda _e, w=cv: self._bet_cursor(w))
            cv.bind('<Leave>', lambda _e, w=cv: w.config(cursor=''))
            self.chip_canvases[value] = (cv, oval)

        self.selected_chip = default
        self._update_chip_ui()

    def _bet_total(self, source=None):
        source = self.bets if source is None else source
        return float(sum(source.values()))

    @staticmethod
    def _opposite_bet_side(side):
        return 'lose' if side == 'win' else 'win'

    def _bet_side_blocked(self, door, side):
        opposite = self._opposite_bet_side(side)
        return float(self.bets.get((door, opposite), 0.0)) > 0.0

    def _update_bet_cell_cursor(self, door, side, widget=None):
        widget = widget or self.bet_cell_labels.get((door, side))
        if widget is None:
            return
        if self.stage != 'betting' or self.animation_running:
            cursor = 'arrow'
        elif self._bet_side_blocked(door, side):
            cursor = 'no'
        else:
            cursor = 'hand2'
        try:
            widget.config(cursor=cursor)
        except tk.TclError:
            widget.config(cursor='X_cursor' if cursor == 'no' else cursor)

    def reset_bets(self):
        """Clear all six CURRENT-round bet cells without changing last-round bets."""
        if self.stage != 'betting' or self.animation_running:
            return
        self.bets = {(door, side): 0.0 for door in (1, 2, 3) for side in self.BET_SIDES}
        self.ante = 0.0
        self.bet_result_values = {}
        self.winning_cells = set()
        self.status = '已重设本局下注金额。'
        self.update_display()

    def add_bet_cell(self, door, side):
        if self.stage != 'betting' or self.animation_running:
            return
        # A single door may be backed on only one side.  If the opposite side
        # already has money, this click is intentionally ignored.
        if self._bet_side_blocked(door, side):
            return
        key = (door, side)
        chip = float(self.selected_chip)
        maximum = self._current_max_bet()
        if self._bet_total() + chip > maximum:
            messagebox.showerror('超过上限', f'本局下注最高 ${maximum:,}', parent=self.winfo_toplevel())
            return
        if self._bet_total() + chip > self.balance:
            messagebox.showerror('余额不足', '余额不足以增加该笔门注', parent=self.winfo_toplevel())
            return
        self.bets[key] += chip
        self.ante = self._bet_total()
        self.update_display()

    def clear_bet_cell(self, door, side):
        if self.stage != 'betting' or self.animation_running:
            return
        self.bets[(door, side)] = 0.0
        self.ante = self._bet_total()
        self.update_display()

    def repeat_bet(self):
        if self.stage != 'betting' or self.animation_running:
            return
        for door in (1, 2, 3):
            if float(self.last_bets.get((door, 'win'), 0.0)) > 0 and float(self.last_bets.get((door, 'lose'), 0.0)) > 0:
                messagebox.showerror('下注限制', f'{self.POSITION_NAMES[door]}不能同时下注获胜与惜败', parent=self.winfo_toplevel())
                return
        total = self._bet_total(self.last_bets)
        if not self._bets_fit_limits(self.last_bets):
            messagebox.showerror(
                '下注限制',
                f'上局下注合计不符合当前 ${self._current_min_bet():,}–${self._current_max_bet():,} 限额',
                parent=self.winfo_toplevel(),
            )
            return
        if total > self.balance:
            messagebox.showerror('余额不足', '余额不足以重复上局全部门注', parent=self.winfo_toplevel())
            return
        self.bets = dict(self.last_bets)
        self.ante = total
        self.status = f'已重复上局门注，总计 ${self._fmt(total)}。'
        self.update_display()

    def _refresh_bet_cells(self):
        for key, lbl in self.bet_cell_labels.items():
            if self.stage == 'settled':
                value = self.bet_result_values.get(key, 0.0)
                lbl.config(
                    text=f'${self._fmt(value)}',
                    bg='#D8B46A' if key in self.winning_cells else 'white',
                    fg='black',
                )
                try:
                    lbl.config(cursor='arrow')
                except tk.TclError:
                    pass
            else:
                value = self.bets.get(key, 0.0)
                lbl.config(text=f'${self._fmt(value)}', bg='white', fg='black')
                self._update_bet_cell_cursor(key[0], key[1], lbl)

    def roll_dice(self):
        if self.animation_running:
            return
        self.animation_running = True
        self.animation_final_dice = [die.roll() for die in self.dice_objects]
        self.animation_frames_left = secrets.randbelow(15) + 27
        self.animate_dice()

    def animate_dice(self):
        if self._closing:
            return
        if self.animation_frames_left > 0:
            current = [secrets.randbelow(6) + 1 for _ in range(2)]
            for index, (item, value) in enumerate(zip(self.animation_dice_items, current)):
                base_x, base_y = self.animation_dice_base_positions[index]
                shake_x = secrets.randbelow(31) - 15
                shake_y = secrets.randbelow(31) - 15
                self.canvas.coords(item, base_x + shake_x, base_y + shake_y)
                self.canvas.itemconfigure(item, image=self.dice_images_animation[value - 1])
            self.animation_frames_left -= 1
            delay = 45 if self.animation_frames_left > 10 else 70
            self.animation_after_id = self.after(delay, self.animate_dice)
            return

        for index, (item, value) in enumerate(zip(self.animation_dice_items, self.animation_final_dice)):
            base_x, base_y = self.animation_dice_base_positions[index]
            self.canvas.coords(item, base_x, base_y)
            self.canvas.itemconfigure(item, image=self.dice_images_animation[value - 1])
        self.animation_after_id = self.after(300, self.prepare_deal)

    def start_round(self):
        if self.stage != 'betting' or self.animation_running:
            return
        total_bet = self._bet_total()
        if not self._bets_fit_limits(self.bets):
            messagebox.showerror(
                '下注限制',
                f'本局下注合计必须在 ${self._current_min_bet():,}–${self._current_max_bet():,} 之间，或为 $0',
                parent=self.winfo_toplevel(),
            )
            return
        if total_bet > self.balance:
            messagebox.showerror('余额不足', '余额不足以支付本局全部门注', parent=self.winfo_toplevel())
            return
        if not self.full_tiles or len(self.full_tiles) != 32 or not self.deal_wall_visible:
            messagebox.showerror('牌靴未就绪', '新牌靴尚未准备完成', parent=self.winfo_toplevel())
            return

        self.round_bets = dict(self.bets)
        self.last_bets = dict(self.bets)
        self.round_total_bet = total_bet
        self.ante = total_bet
        self.last_ante = total_bet
        self.balance -= total_bet
        self._persist_balance()

        self.stage = 'rolling'
        self.status = '停止下注。正在摇两颗骰子决定第一门。'
        self.last_result = ''
        self.last_return = 0.0
        self.bet_result_values = {}
        self.winning_cells = set()
        self.door_result_text = {1: '', 2: '', 3: ''}
        self.door_hands = {0: [], 1: [], 2: [], 3: []}
        self.door_dealt_visible = {0: False, 1: False, 2: False, 3: False}
        self.door_face_up = {0: False, 1: False, 2: False, 3: False}
        self.door_tile_face_up = {pos: [False, False] for pos in (0, 1, 2, 3)}
        self.door_outcomes = {1: None, 2: None, 3: None}
        self.flip_anim = None
        self.deal_stack_markers = {}
        self.deal_order = []
        self.position_hands = {}
        self.shoe_ready_for_next_round = False
        self.update_display()
        self.roll_dice()

    def prepare_deal(self):
        self.animation_running = False
        self.dice_result = list(self.animation_final_dice)
        total = sum(self.dice_result)
        remainder = total % 4
        start_pos = {1: 0, 2: 1, 3: 2, 0: 3}[remainder]
        self.deal_start_index = start_pos
        self.deal_order = [(start_pos + i) % 4 for i in range(4)]

        # One physical column (top+bottom) is one two-tile pair.  Deal the four
        # leftmost pairs in order, assigning them according to the dice rotation.
        self.pair_stacks = [self.full_tiles[i * 2:(i + 1) * 2] for i in range(16)]
        self.position_hands = {}
        for pair_no, pos in enumerate(self.deal_order):
            hand = ordered_wenzhou_hand(self.pair_stacks[pair_no])
            self.position_hands[pos] = hand
            self.door_hands[pos] = hand

        self.stage = 'dealing'
        first_name = self.POSITION_NAMES[start_pos]
        self.status = f'骰子共{total}点，余{4 if remainder == 0 else remainder}：{first_name}先派。'
        self.update_display()
        self.after(260, lambda: self.animate_deal_pair(0))

    def wall_geometry(self):
        w = 24
        h = int(w * CLASSIC_TILE_ASPECT)
        gap_x, gap_y = 7, 10
        total_w = 16 * w + 15 * gap_x
        x0 = (self.SHOE_ZONE[0] + self.SHOE_ZONE[2] - total_w) / 2
        y0 = self.SHOE_ZONE[1] + 42
        return x0, y0, w, h, gap_x, gap_y

    def draw_deal_wall(self):
        self.canvas.delete('deal_wall')
        if not self.deal_wall_visible or not self.full_tiles:
            return
        sx0, sy0, sx1, sy1 = self.SHOE_ZONE
        self.canvas.create_rectangle(sx0, sy0, sx1, sy1, fill='#0a3834',
                                     outline='#557b70', width=1, tags='deal_wall')
        self.canvas.create_text(sx0 + 14, sy0 + 18, anchor='w', text='牌九牌靴',
                                font=('Arial', 12, 'bold'), fill='#d9efe8', tags='deal_wall')
        self.canvas.create_text(sx1 - 14, sy0 + 18, anchor='e', text='32张 · 16副 × 2张',
                                font=('Arial', 9, 'bold'), fill=MUTED, tags='deal_wall')

        for idx, tile_obj in enumerate(self.full_tiles):
            pair_no = idx // 2
            if pair_no in self.deal_stack_markers:
                continue
            x, y, w, h = self.wall_tile_rect(idx)
            self.draw_tile(x, y, w, h, tile_obj, face_up=False,
                           tag=f'wall_{idx}', extra_tag='deal_wall',
                           show_name=False, compact=True)

        x0, y0, w, h, gap_x, gap_y = self.wall_geometry()
        for pair_no in range(16):
            x = x0 + pair_no * (w + gap_x)
            self.canvas.create_rectangle(x - 2, y0 - 3, x + w + 2,
                                         y0 + 2 * h + gap_y + 3,
                                         outline='#6f8f85', width=1, tags='deal_wall')

    def _draw_shoe_snapshot(self, tiles, offset_x=0.0, tag='shoe_snapshot', hide_uids=None,
                            theme=None):
        hide_uids = set(hide_uids or ())
        previous = self._render_tile_theme_override
        if theme is not None:
            self._render_tile_theme_override = theme
        try:
            sx0, sy0, sx1, sy1 = self.SHOE_ZONE
            self.canvas.create_rectangle(sx0 + offset_x, sy0, sx1 + offset_x, sy1,
                                         fill='#0a3834', outline='#557b70', width=1, tags=tag)
            self.canvas.create_text(sx0 + 14 + offset_x, sy0 + 18, anchor='w', text='牌九牌靴',
                                    font=('Arial', 12, 'bold'), fill='#d9efe8', tags=tag)
            self.canvas.create_text(sx1 - 14 + offset_x, sy0 + 18, anchor='e',
                                    text='32张 · 16副 × 2张', font=('Arial', 9, 'bold'),
                                    fill=MUTED, tags=tag)
            x0, y0, w, h, gap_x, gap_y = self.wall_geometry()
            for idx, tile_obj in enumerate(tiles):
                if tile_obj.uid in hide_uids:
                    continue
                col = idx // 2
                row = idx % 2
                x = x0 + col * (w + gap_x) + offset_x
                y = y0 + row * (h + gap_y)
                self.draw_tile(x, y, w, h, tile_obj, face_up=False,
                               tag=f'{tag}_{idx}', extra_tag=tag,
                               show_name=False, compact=True)
            for pair_no in range(16):
                x = x0 + pair_no * (w + gap_x) + offset_x
                self.canvas.create_rectangle(x - 2, y0 - 3, x + w + 2,
                                             y0 + 2 * h + gap_y + 3,
                                             outline='#6f8f85', width=1, tags=tag)
        finally:
            self._render_tile_theme_override = previous

    def hand_positions(self, pos):
        if pos == 0:
            x0, y0, x1, y1 = self.DEALER_ZONE
        else:
            x0, y0, x1, y1 = self.DOOR_ZONES[pos]
        gap = 18 if pos == 0 else 12
        total_w = 2 * self.HAND_W + gap
        cx = (x0 + x1) / 2
        start_x = cx - total_w / 2
        # Nudge all dealt hands 6px downward relative to the previous layout.
        if pos == 0:
            top = y0 + 24
        else:
            top = y0 + 43
        return [
            (start_x, top, self.HAND_W, self.HAND_H),
            (start_x + self.HAND_W + gap, top, self.HAND_W, self.HAND_H),
        ]

    def deal_destination(self, pos):
        rects = self.hand_positions(pos)
        cx = sum(x + w / 2 for x, y, w, h in rects) / 2
        cy = sum(y + h / 2 for x, y, w, h in rects) / 2
        return cx, cy

    def animate_deal_pair(self, pair_no):
        if self._closing:
            return
        if pair_no >= 4:
            self.after(350, self.settle_wenzhou_round)
            return

        pos = self.deal_order[pair_no]
        tiles = self.pair_stacks[pair_no]
        source_rects = [self.wall_tile_rect(pair_no * 2), self.wall_tile_rect(pair_no * 2 + 1)]
        target_rects = self.hand_positions(pos)
        frames = 13
        self.deal_stack_markers[pair_no] = pos
        self.draw_deal_wall()

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('moving_stack')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            for tile_obj, src, dst in zip(tiles, source_rects, target_rects):
                sx, sy, sw, sh = src
                tx, ty, tw, th = dst
                x = sx + (tx - sx) * smooth
                y = sy + (ty - sy) * smooth
                w = sw + (tw - sw) * smooth
                h = sh + (th - sh) * smooth
                self.draw_tile(x, y, w, h, tile_obj, face_up=False,
                               tag='moving_stack', extra_tag='moving_stack', compact=True)
            if step < frames:
                self.after(34, lambda: frame(step + 1))
                return

            self.canvas.delete('moving_stack')
            self.door_dealt_visible[pos] = True
            self.door_face_up[pos] = False
            self.status = f'派牌2张中，到位后立即开牌。'
            self.redraw_tiles()
            self.update_display(redraw=False)
            self.after(120, lambda: self.reveal_position(pos, pair_no))

        frame(0)

    def reveal_position(self, pos, pair_no):
        """逐张翻开刚派到该门的两张牌。"""
        if self._closing:
            return
        self.update_display(redraw=False)
        self.after(40, lambda: self.animate_flip_position(pos, 0, lambda: self.finish_position_reveal(pos, pair_no)))

    def animate_flip_position(self, pos, index, done_callback):
        """牌九 flip: shrink horizontally, switch face, expand, then next tile."""
        if self._closing:
            return
        hand = self.door_hands.get(pos, [])
        states = self.door_tile_face_up.setdefault(pos, [False, False])
        if index >= len(hand):
            self.door_face_up[pos] = True
            done_callback()
            return

        frames = 10
        self.flip_anim = {'pos': pos, 'index': index, 'scale': 1.0}

        def frame(step):
            if self._closing:
                return
            if step <= frames // 2:
                scale = max(0.08, 1.0 - (step / (frames / 2)) * 0.92)
            else:
                if not states[index]:
                    states[index] = True
                scale = 0.08 + ((step - frames / 2) / (frames / 2)) * 0.92
            self.flip_anim['scale'] = scale
            self.redraw_tiles()
            if step < frames:
                self.after(35, lambda: frame(step + 1))
            else:
                states[index] = True
                self.flip_anim = None
                self.redraw_tiles()
                self.after(85, lambda: self.animate_flip_position(pos, index + 1, done_callback))

        frame(0)

    def finish_position_reveal(self, pos, pair_no):
        if self._closing:
            return
        self.door_face_up[pos] = True
        self.door_tile_face_up[pos] = [True, True]
        value = evaluate_wenzhou_hand(self.door_hands[pos])
        self.redraw_tiles()
        self.update_display(redraw=False)
        self.after(420, lambda: self.animate_deal_pair(pair_no + 1))

    def redraw_tiles(self):
        self.canvas.delete('tile_dynamic')
        self.draw_deal_wall()

        # Match 牌九 result presentation: the corresponding PLAYER door
        # receives a pure green/red hand background after comparison with the dealer.
        if self.stage == 'settled':
            for pos in (1, 2, 3):
                outcome = self.door_outcomes.get(pos)
                if outcome not in ('win', 'lose'):
                    continue
                rects = self.hand_positions(pos)
                min_x = min(r[0] for r in rects) - 14
                min_y = min(r[1] for r in rects) - 8
                max_x = max(r[0] + r[2] for r in rects) + 14
                max_y = max(r[1] + r[3] for r in rects) + 8
                fill = self.HAND_WIN_BG if outcome == 'win' else self.HAND_LOSE_BG
                self.canvas.create_rectangle(
                    min_x, min_y, max_x, max_y,
                    fill=fill, outline='#7d9187', width=1, tags='tile_dynamic'
                )

        for pos in (0, 1, 2, 3):
            if not self.door_dealt_visible.get(pos):
                continue
            hand = self.door_hands.get(pos, [])
            if len(hand) != 2:
                continue
            rects = self.hand_positions(pos)
            face_states = self.door_tile_face_up.setdefault(pos, [False, False])
            for index, (tile_obj, rect) in enumerate(zip(hand, rects)):
                x, y, w, h = rect
                scale = 1.0
                if self.flip_anim and self.flip_anim.get('pos') == pos and self.flip_anim.get('index') == index:
                    scale = self.flip_anim.get('scale', 1.0)
                draw_w = max(6, w * scale)
                draw_x = x + (w - draw_w) / 2
                self.draw_tile(
                    draw_x, y, draw_w, h, tile_obj,
                    face_up=bool(face_states[index]),
                    tag=f'pos_{pos}_{tile_obj.uid}', extra_tag='tile_dynamic'
                )

        dealer_text = '庄家'
        if self.door_face_up.get(0) and len(self.door_hands.get(0, [])) == 2:
            dealer_text = f"庄家 - {evaluate_wenzhou_hand(self.door_hands[0]).name}"
        self.canvas.itemconfigure(self.dealer_header_item, text=dealer_text)

        for pos in (1, 2, 3):
            title = self.POSITION_NAMES[pos]
            if self.door_face_up.get(pos) and len(self.door_hands.get(pos, [])) == 2:
                title += f" - {evaluate_wenzhou_hand(self.door_hands[pos]).name}"
            self.canvas.itemconfigure(self.door_header_items[pos], text=title)
            self.canvas.itemconfigure(self.door_result_items[pos], text=self.door_result_text.get(pos, ''))

    def settle_wenzhou_round(self):
        dealer = self.door_hands.get(0, [])
        if len(dealer) != 2 or any(len(self.door_hands.get(pos, [])) != 2 for pos in (1, 2, 3)):
            return

        returned = 0.0
        self.winning_cells = set()
        self.bet_result_values = {(door, side): 0.0 for door in (1, 2, 3) for side in self.BET_SIDES}
        for pos in (1, 2, 3):
            hand = self.door_hands[pos]
            cmp_value = compare_wenzhou_hands(hand, dealer)
            # Ties, including identical hand type + identical strongest-tile level,
            # belong to 惜败.  Ordinary 0 vs 0 therefore also goes to 惜败.
            winner_side = 'win' if cmp_value > 0 else 'lose'
            loser_side = 'lose' if winner_side == 'win' else 'win'
            # Door-hand background is green only for a strict player win; any
            # smaller/equal result (惜败, including ordinary 0 vs 0) is red.
            self.door_outcomes[pos] = 'win' if cmp_value > 0 else 'lose'
            self.winning_cells.add((pos, winner_side))

            multiplier = self.WIN_MULTIPLIER if winner_side == 'win' else self.LOSE_MULTIPLIER
            stake = float(self.round_bets.get((pos, winner_side), 0.0))
            payout = stake * multiplier
            self.bet_result_values[(pos, winner_side)] = payout
            self.bet_result_values[(pos, loser_side)] = 0.0
            returned += payout

            # No per-door sentence below the cards; the green/red hand background
            # already communicates 获胜 / 惜败.
            self.door_result_text[pos] = ''

        self.balance += returned
        self.last_return = returned
        net = returned - self.round_total_bet
        self.last_result = f'游戏结束'
        self.status = self.last_result
        self.stage = 'settled'
        self.animation_running = False
        self._persist_balance()
        self.update_display()

    def render_action_buttons(self):
        if not hasattr(self, 'action_frame'):
            return
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        for i in range(3):
            self.action_frame.columnconfigure(i, weight=1)

        def btn(text, command, bg, enabled=True, fg='white'):
            return tk.Button(
                self.action_frame, text=text, command=command,
                font=('Arial', 11, 'bold'), bg=bg, fg=fg,
                activebackground=bg, relief=tk.RAISED,
                state=tk.NORMAL if enabled else tk.DISABLED,
            )

        if self.stage == 'betting':
            repeat_ok = (self._bet_total(self.last_bets) > 0 and self._bet_total(self.last_bets) <= self.balance and self._bets_fit_limits(self.last_bets))
            start_ok = not self.animation_running and self._bet_total() <= self.balance
            btn('重设金额', self.reset_bets, '#F44336', True, 'white').grid(
                row=0, column=0, sticky='nsew', padx=(0, 3), pady=1
            )
            btn('重复上局下注', self.repeat_bet, '#FFC107', repeat_ok, 'black').grid(
                row=0, column=1, sticky='nsew', padx=3, pady=1
            )
            btn('开始游戏', self.start_round, '#4CAF50', start_ok).grid(
                row=0, column=2, sticky='nsew', padx=(3, 0), pady=1
            )
        elif self.stage == 'settled':
            btn('再来一局', self.new_round, '#FFC107', True, 'black').grid(
                row=0, column=0, columnspan=3, sticky='nsew', padx=105, pady=1
            )
        else:
            tk.Label(self.action_frame, text='动画进行中…', font=('Arial', 11, 'bold'),
                     bg=self.PANEL_BG, fg='#6B6251').grid(
                row=0, column=0, columnspan=3, sticky='nsew'
            )

    def update_dice_and_order_text(self):
        if not self.dice_result:
            self.canvas.itemconfigure(self.dice_summary_item, text='= --点　｜　等待摇骰')
            return
        total = sum(self.dice_result)
        rem = total % 4
        display_rem = 4 if rem == 0 else rem
        start_pos = {1: 0, 2: 1, 3: 2, 0: 3}[rem]
        self.canvas.itemconfigure(
            self.dice_summary_item,
            text=f'= {total}点　｜　余{display_rem} · {self.POSITION_NAMES[start_pos]}先派',
        )

    def update_display(self, redraw=True):
        if not hasattr(self, 'balance_label'):
            return
        stage_map = {
            'betting': '下注阶段', 'rolling': '摇骰中', 'dealing': '派牌中',
            'settled': '结算完成', 'shoe_exchange': '换牌靴',
        }
        self.balance_label.config(text=f'余额: ${self.balance:,.2f}')
        self.stage_label.config(text=stage_map.get(self.stage, self.stage))
        self.current_bet_label.config(text=f'本局下注: ${self._fmt(self._bet_total())}')
        self.last_win_label.config(text=f'上局返还: ${self._fmt(self.last_return)}')
        self.status_label.config(text=str(self.status).split('\n', 1)[0])
        self._update_chip_ui()
        self._refresh_bet_cells()
        self.update_dice_and_order_text()
        self.render_action_buttons()
        if redraw:
            self.redraw_tiles()

    def _animate_initial_shoe_left(self):
        if self._closing:
            return
        new_tiles = self.secure_shuffle(build_pai_gow_set())
        frames = 24
        travel = (self.SHOE_ZONE[2] - self.SHOE_ZONE[0]) + 45
        initial_theme = self.tile_theme

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('initial_shoe_slide')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            offset = -travel * (1 - smooth)
            self._draw_shoe_snapshot(new_tiles, offset, 'initial_shoe_slide', theme=initial_theme)
            if step < frames:
                self.after(28, lambda: frame(step + 1))
                return
            self.canvas.delete('initial_shoe_slide')
            self.full_tiles = list(new_tiles)
            self.pair_stacks = [self.full_tiles[i * 2:(i + 1) * 2] for i in range(16)]
            self.stacks = list(self.pair_stacks)
            self.deal_wall_visible = True
            self.shoe_ready_for_next_round = True
            self.animation_running = False
            self.status = f'{self._tile_colour_name(initial_theme)}温州牌九牌靴已就位。'
            self.update_display()

        frame(0)

    def _returning_start_states(self):
        """Return all eight live Wenzhou tiles from their door positions to the shoe."""
        states = {}
        for pos in (0, 1, 2, 3):
            hand = self.door_hands.get(pos, [])
            rects = self.hand_positions(pos)
            for tile_obj, rect in zip(hand, rects):
                x, y, w, h = rect
                states[tile_obj.uid] = (x + w / 2, y + h / 2, w, h, 0.0, tile_obj)
        return states

    def new_round(self):
        if self.stage != 'settled' or self.animation_running:
            return

        start_states = self._returning_start_states()
        if len(self.full_tiles) != 32 or len(start_states) != 8:
            self._finish_new_shoe_immediately()
            return

        self.stage = 'shoe_exchange'
        self.animation_running = True
        self.status = '庄家、顺门、出门、到门牌九正在回到原来的牌靴位置…'
        self.render_action_buttons()

        old_tiles = list(self.full_tiles)
        return_uids = set(start_states)
        # Same rule as Classic final UI: every live tile goes back to the exact slot
        # it occupied in this round's original 32-tile shoe.
        target_index = {tile.uid: idx for idx, tile in enumerate(old_tiles)}

        self.canvas.delete('tile_dynamic')
        self.canvas.delete('deal_wall')
        self.canvas.itemconfigure(self.dealer_header_item, text='庄家')
        for pos in (1, 2, 3):
            self.canvas.itemconfigure(self.door_header_items[pos], text=self.POSITION_NAMES[pos])
            self.canvas.itemconfigure(self.door_result_items[pos], text='')
        self._draw_shoe_snapshot(old_tiles, tag='shoe_return_base', hide_uids=return_uids, theme=self.tile_theme)

        frames = 22

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('returning_tiles')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            for uid, (scx, scy, sbw, sbh, sangle, tile_obj) in start_states.items():
                idx = target_index[uid]
                tx, ty, tw, th = self._snapshot_wall_rect(idx)
                tcx, tcy = tx + tw / 2, ty + th / 2
                cx = scx + (tcx - scx) * smooth
                cy = scy + (tcy - scy) * smooth
                bw = sbw + (tw - sbw) * smooth
                bh = sbh + (th - sbh) * smooth
                angle = sangle * (1 - smooth)
                self._draw_rotated_face_tile(
                    cx, cy, bw, bh, angle, tile_obj,
                    tag=f'return_{uid}', extra_tag='returning_tiles', compact=True,
                )
            if step < frames:
                self.after(32, lambda: frame(step + 1))
                return

            self.canvas.delete('returning_tiles')
            self.canvas.delete('shoe_return_base')
            self.deal_stack_markers = {}
            self._animate_shoe_swap(old_tiles)

        frame(0)

    def _animate_shoe_swap(self, old_tiles):
        old_theme = self.tile_theme
        new_theme = self._opposite_tile_theme(old_theme)
        new_tiles = self.secure_shuffle(build_pai_gow_set())
        frames = 24
        travel = (self.SHOE_ZONE[2] - self.SHOE_ZONE[0]) + 45

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('deal_wall')
            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            self._draw_shoe_snapshot(old_tiles, travel * smooth, 'shoe_swap_old', theme=old_theme)
            self._draw_shoe_snapshot(new_tiles, -travel * (1 - smooth), 'shoe_swap_new', theme=new_theme)
            if step < frames:
                self.after(28, lambda: frame(step + 1))
                return

            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            self.tile_theme = new_theme
            self.full_tiles = list(new_tiles)
            self.pair_stacks = [self.full_tiles[i * 2:(i + 1) * 2] for i in range(16)]
            self.stacks = list(self.pair_stacks)
            self.deal_wall_visible = True
            self.shoe_ready_for_next_round = True
            self._reset_after_shoe_exchange()

        frame(0)

    def _finish_new_shoe_immediately(self):
        self.tile_theme = self._opposite_tile_theme(self.tile_theme)
        self.full_tiles = self.secure_shuffle(build_pai_gow_set())
        self.pair_stacks = [self.full_tiles[i * 2:(i + 1) * 2] for i in range(16)]
        self.stacks = list(self.pair_stacks)
        self.deal_wall_visible = True
        self.shoe_ready_for_next_round = True
        self._reset_after_shoe_exchange()

    def _reset_after_shoe_exchange(self):
        self.animation_running = False
        self.stage = 'betting'
        self.bets = {(door, side): 0.0 for door in (1, 2, 3) for side in self.BET_SIDES}
        self.round_bets = dict(self.bets)
        self.ante = 0.0
        self.status = f'新{self._tile_colour_name()}温州牌九牌靴已就位。'
        self.last_result = ''
        self.bet_result_values = {}
        self.winning_cells = set()
        self.door_hands = {0: [], 1: [], 2: [], 3: []}
        self.door_dealt_visible = {0: False, 1: False, 2: False, 3: False}
        self.door_face_up = {0: False, 1: False, 2: False, 3: False}
        self.door_tile_face_up = {pos: [False, False] for pos in (0, 1, 2, 3)}
        self.door_outcomes = {1: None, 2: None, 3: None}
        self.flip_anim = None
        self.door_result_text = {1: '', 2: '', 3: ''}
        self.dice_result = []
        self.deal_start_index = None
        self.deal_order = []
        self.position_hands = {}
        self.deal_stack_markers = {}
        self.canvas.delete('tile_dynamic')
        self.canvas.delete('moving_stack')
        for item in self.animation_dice_items:
            self.canvas.itemconfigure(item, image=self.dice_images_animation[5])
        self.update_display()

    def show_detailed_rules(self):
        """温州牌九图解玩法说明。"""
        win = tk.Toplevel(self)
        win.title('温州牌九 · 完整图解玩法与32张骨牌')
        win.geometry('1040x720+55+20')
        win.resizable(False, False)
        win.configure(bg='#efe7d4')

        shell = tk.Frame(win, bg='#efe7d4')
        shell.pack(fill='both', expand=True, padx=8, pady=8)
        scroller = tk.Canvas(shell, bg='#efe7d4', highlightthickness=0)
        scrollbar = tk.Scrollbar(shell, orient='vertical', command=scroller.yview)
        scroller.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        scroller.pack(side='left', fill='both', expand=True)
        content = tk.Frame(scroller, bg='#efe7d4')
        window_id = scroller.create_window((0, 0), window=content, anchor='nw')

        def resize_inner(_event=None):
            try:
                scroller.itemconfigure(window_id, width=scroller.winfo_width())
                scroller.configure(scrollregion=scroller.bbox('all'))
            except tk.TclError:
                pass

        content.bind('<Configure>', resize_inner)
        scroller.bind('<Configure>', resize_inner)

        def mousewheel(event):
            scroller.yview_scroll((-1 if event.delta > 0 else 1) * 3, 'units')

        win.bind('<MouseWheel>', mousewheel)

        PANEL = '#fffaf0'
        GOLD_BAR = '#d8b46a'
        INK = '#2a1b08'
        MUTED_INK = '#705f49'
        BLUE = '#2c6e9f'
        BROWN = '#8a5318'
        GREEN = '#0b6b45'
        RED_INK = '#b51f1f'
        section_font = ('Microsoft YaHei', 13, 'bold')
        body_font = ('Microsoft YaHei', 10)
        small_font = ('Microsoft YaHei', 9)
        mini_font = ('Microsoft YaHei', 8)

        tk.Label(
            content, text='温州牌九 · 完整图解说明',
            font=('Microsoft YaHei', 20, 'bold'), bg='#efe7d4', fg=INK,
        ).pack(fill='x', pady=(5, 3))
        tk.Label(
            content,
            text='先认32张牌 → 看两骰四门 → 学两张牌型 → 最后看下注、比较与换牌靴',
            font=('Microsoft YaHei', 10, 'bold'), bg='#efe7d4', fg=MUTED_INK,
        ).pack(fill='x', pady=(0, 10))

        def section(title, body='', height=210):
            outer = tk.Frame(content, bg=PANEL, bd=1, relief=tk.SOLID)
            outer.pack(fill='x', padx=8, pady=6)
            tk.Label(
                outer, text=title, font=section_font, bg=GOLD_BAR, fg=INK,
                anchor='w', padx=10, pady=5,
            ).pack(fill='x')
            if body:
                tk.Label(
                    outer, text=body, font=body_font, bg=PANEL, fg=INK,
                    justify='left', anchor='w', padx=12, pady=7, wraplength=965,
                ).pack(fill='x')
            viz = tk.Canvas(outer, width=975, height=height, bg=PANEL, highlightthickness=0)
            viz.pack(padx=8, pady=(0, 8))
            return viz

        def draw_die(c, cx, cy, value, size=54):
            r = size / 2
            x0, y0, x1, y1 = cx-r, cy-r, cx+r, cy+r
            c.create_rectangle(x0, y0, x1, y1, fill='#f0f0e9', outline='#222', width=2)
            positions = {
                1: [(0.50, 0.50)],
                2: [(0.28, 0.28), (0.72, 0.72)],
                3: [(0.28, 0.28), (0.50, 0.50), (0.72, 0.72)],
                4: [(0.28, 0.28), (0.72, 0.28), (0.28, 0.72), (0.72, 0.72)],
                5: [(0.28, 0.28), (0.72, 0.28), (0.50, 0.50), (0.28, 0.72), (0.72, 0.72)],
                6: [(0.28, 0.20), (0.72, 0.20), (0.28, 0.50), (0.72, 0.50), (0.28, 0.80), (0.72, 0.80)],
            }
            pip_r = max(3, int(size / 11))
            pip_color = '#d21e2b' if value in (1, 4) else '#111'
            for ux, uy in positions[value]:
                px, py = x0 + ux * size, y0 + uy * size
                c.create_oval(px-pip_r, py-pip_r, px+pip_r, py+pip_r, fill=pip_color, outline='')

        tiles = build_pai_gow_set()
        by_group = {}
        for tile in tiles:
            by_group.setdefault(tile.group, []).append(tile)

        def find_hand(name):
            for i, a in enumerate(tiles):
                for b in tiles[i+1:]:
                    if evaluate_wenzhou_hand([a, b]).name == name:
                        return [a, b]
            raise LookupError(name)

        def find_ordinary(points, avoid_groups=()):
            for i, a in enumerate(tiles):
                for b in tiles[i+1:]:
                    if a.group in avoid_groups or b.group in avoid_groups:
                        continue
                    value = evaluate_wenzhou_hand([a, b])
                    if value.named_rank is None and value.points == points:
                        return [a, b]
            raise LookupError(points)

        def draw_hand(c, hand, cx, cy, label='', scale=.70, label_y=82):
            gap = 48 * scale + 15
            self._instruction_tile(c, hand[0], cx-gap/2, cy, scale=scale)
            self._instruction_tile(c, hand[1], cx+gap/2, cy, scale=scale)
            if label:
                c.create_text(cx, cy+label_y, text=label, font=small_font, fill=INK)

        # 1. Dice and four-door dealing
        c = section(
            '1. 两颗骰子与四门派牌',
            '两骰总点数除以4：余1庄家、余2顺门、余3出门、整除（界面显示余4）到门。确定第一门后，按“庄 → 顺 → 出 → 到”循环。每次从牌靴最左侧拿2张；一门派完立即逐张翻牌，再派下一门。',
            height=245,
        )
        draw_die(c, 90, 72, 3)
        draw_die(c, 165, 72, 4)
        c.create_text(128, 126, text='3 + 4 = 7；7 ÷ 4 余3 → 出门先派', font=('Microsoft YaHei', 10, 'bold'), fill=BLUE)
        doors = [('庄家', 0), ('顺门', 1), ('出门', 2), ('到门', 3)]
        start_x = 310
        for i, (name, pos) in enumerate(doors):
            x0 = start_x + i * 155
            fill = '#f5e7b8' if pos == 2 else '#f8f1df'
            c.create_rectangle(x0, 48, x0+125, 105, fill=fill, outline='#8b7658', width=2)
            c.create_text(x0+62, 66, text=name, font=('Microsoft YaHei', 11, 'bold'), fill=INK)
            c.create_text(x0+62, 89, text='每门2张', font=small_font, fill=MUTED_INK)
            if i < 3:
                c.create_text(x0+140, 77, text='→', font=('Arial', 20, 'bold'), fill=BROWN)
        c.create_text(486, 155, text='示例起手顺序：出门 → 到门 → 庄家 → 顺门', font=('Microsoft YaHei', 11, 'bold'), fill=GREEN)
        c.create_text(486, 190, text='每派完一门：牌背缩窄 → 翻成牌面 → 展开 → 再派下一门', font=body_font, fill=INK)

        # 2. Full 32-tile set
        c = section(
            '2. 一副温州牌九：32张 = 16组 × 每组2张',
            '游戏使用传统32张牌九骨牌。下图由程序直接绘制实际牌面，因此说明页和牌桌显示一致。',
            height=565,
        )
        groups = sorted(by_group, key=lambda g: (WENZHOU_PAIR_RANK[g][0], WENZHOU_PAIR_RANK[g][1], g))
        cell_w, cell_h = 236, 132
        for idx, group in enumerate(groups):
            row, col = divmod(idx, 4)
            x0, y0 = 10 + col*cell_w, 10 + row*cell_h
            pair = by_group[group][:2]
            rank, name = WENZHOU_PAIR_RANK[group]
            c.create_rectangle(x0, y0, x0+224, y0+120, fill='#fbf6e9', outline='#d8c69a')
            self._instruction_tile(c, pair[0], x0+42, y0+55, scale=.58)
            self._instruction_tile(c, pair[1], x0+83, y0+55, scale=.58)
            c.create_text(x0+120, y0+25, anchor='w', text=f'{name}', font=('Microsoft YaHei', 9, 'bold'), fill=INK)
            c.create_text(x0+120, y0+49, anchor='w', text=f'牌型级别 {rank}', font=mini_font, fill=BROWN)
            c.create_text(x0+120, y0+72, anchor='w', text=' + '.join(f'{t.a}-{t.b}' for t in pair), font=mini_font, fill=MUTED_INK)
            c.create_text(x0+120, y0+94, anchor='w', text='共2张实体牌', font=mini_font, fill=GREEN)

        # 3. Main ranking and special combinations
        c = section(
            '3. 经典温州牌型大小：先看牌型，再看普通点数',
            '最高三档固定是“双天 > 双地 > 至尊”。随后是其余成对牌，再到天九王、天杠、地杠、天九、地九；普通0～9点位于这些固定牌型之后。这里用真实骨牌画出代表牌型。',
            height=500,
        )
        examples = [
            ('双天', find_hand('双天')), ('双地', find_hand('双地')), ('至尊', find_hand('至尊')),
            ('天九王', find_hand('天九王')), ('天杠', find_hand('天杠')), ('地杠', find_hand('地杠')),
            ('天九', find_hand('天九')), ('地九', find_hand('地九')),
        ]
        for idx, (label, hand) in enumerate(examples):
            row, col = divmod(idx, 4)
            cx = 125 + col*240
            cy = 80 + row*210
            c.create_rectangle(cx-108, cy-64, cx+108, cy+104, fill='#fbf6e9', outline='#d8c69a')
            draw_hand(c, hand, cx, cy-8, label=f'{label} · {evaluate_wenzhou_hand(hand).name}', scale=.66, label_y=88)
        c.create_text(487, 455, text='固定牌型不能只用“表面总点数”判断；必须先按牌型级别比较。', font=('Microsoft YaHei', 10, 'bold'), fill=RED_INK)

        # 4. Chicken fixed values
        c = section(
            '4. 鸡牌固定：大鸡六=6点，小鸡=3点，不变点',
            '温州牌九里，至尊拆开后不使用赌场大牌九的3/6半百搭规则。大鸡六永远按6，小鸡永远按3。',
            height=250,
        )
        big_chicken = self._instruction_find_tile(tiles, group='Gee Joon', shape=(2, 4))
        small_chicken = self._instruction_find_tile(tiles, group='Gee Joon', shape=(1, 2))
        self._instruction_tile(c, big_chicken, 185, 95, scale=.82)
        self._instruction_tile(c, small_chicken, 385, 95, scale=.82)
        c.create_text(185, 190, text='大鸡六 = 固定6点', font=('Microsoft YaHei', 11, 'bold'), fill=GREEN)
        c.create_text(385, 190, text='小鸡 = 固定3点', font=('Microsoft YaHei', 11, 'bold'), fill=GREEN)
        c.create_text(665, 82, text='例：小鸡3 + 高脚七7 = 10 → 普通0点', font=('Microsoft YaHei', 10, 'bold'), fill=INK)
        c.create_text(665, 122, text='不会把小鸡从3改成6去制造别的点数。', font=body_font, fill=RED_INK)
        c.create_text(665, 160, text='牌桌比较和说明页都调用同一个 evaluate_wenzhou_hand()。', font=small_font, fill=MUTED_INK)

        # 5. Ordinary points and tie break
        c = section(
            '5. 普通0～9点与同点比较',
            '没有形成固定牌型时，两张牌点数相加只保留个位。点数先比大小；点数相同再比两张牌中级别最高的那一张。若牌型相同且最大单张级别也相同，庄家占优，玩家归“惜败”。普通0点对普通0点直接归庄家。',
            height=340,
        )
        hand9 = find_ordinary(9)
        hand7 = find_ordinary(7)
        hand0 = find_ordinary(0)
        draw_hand(c, hand9, 165, 95, label='普通9点', scale=.72, label_y=92)
        draw_hand(c, hand7, 485, 95, label='普通7点', scale=.72, label_y=92)
        draw_hand(c, hand0, 805, 95, label='普通0点', scale=.72, label_y=92)
        c.create_text(487, 225, text='比较顺序：固定牌型 > 普通点数；普通点数相同 → 最大单张级别；仍相同 → 庄家占优', font=('Microsoft YaHei', 10, 'bold'), fill=BLUE)
        c.create_rectangle(300, 258, 675, 318, fill='#fff0f0', outline='#c77')
        c.create_text(487, 278, text='0点 vs 0点', font=('Microsoft YaHei', 11, 'bold'), fill=RED_INK)
        c.create_text(487, 302, text='不再比较单张；玩家直接判惜败', font=small_font, fill=INK)

        # 6. Betting table
        c = section(
            '6. 三门 × 两格：获胜 / 惜败',
            f'顺门、出门、到门各有两个独立下注格。获胜格总返还=本金×{self.WIN_MULTIPLIER:.2f}；惜败格总返还=本金×{self.LOSE_MULTIPLIER:.2f}。六个格子的尺寸固定，结算数字再长也不会拉宽格子。$0空注仍可开局，真正中奖的格子仍会变金色。',
            height=270,
        )
        x0, y0, left_w, cell_w, row_h = 225, 28, 110, 205, 52
        headers = ['', '获胜 0.99 : 1', '惜败 0.93 : 1']
        widths = [left_w, cell_w, cell_w]
        xx=x0
        for text_, w in zip(headers, widths):
            c.create_rectangle(xx, y0, xx+w, y0+row_h, fill='#ead7a6', outline='#806d58')
            c.create_text(xx+w/2, y0+row_h/2, text=text_, font=('Microsoft YaHei', 10, 'bold'), fill=INK)
            xx += w
        for r, pos in enumerate((1,2,3), start=1):
            yy=y0+r*row_h
            c.create_rectangle(x0, yy, x0+left_w, yy+row_h, fill='#f4ead3', outline='#806d58')
            c.create_text(x0+left_w/2, yy+row_h/2, text=self.POSITION_NAMES[pos], font=('Microsoft YaHei', 10, 'bold'), fill=INK)
            for cc in range(2):
                bx=x0+left_w+cc*cell_w
                c.create_rectangle(bx, yy, bx+cell_w, yy+row_h, fill='white', outline='#806d58', width=2)
                c.create_text(bx+cell_w/2, yy+row_h/2, text='$0', font=('Arial', 11, 'bold'), fill='black')
        c.create_text(487, 245, text=f'正常：${self.NORMAL_MIN_BET:,}–${self.NORMAL_MAX_BET:,}　｜　高额：${self.HIGH_MIN_BET:,}–${self.HIGH_MAX_BET:,}　｜　$0可空注', font=('Microsoft YaHei', 10, 'bold'), fill=BROWN)

        # 7. Comparison colours
        c = section(
            '7. 手牌与庄家比较后的颜色',
            '除庄家外，顺门／出门／到门各自与庄家比较。严格大于庄家：该门手牌背景变绿色；小于或等于庄家（惜败）：背景变红色。这个颜色与有没有下注无关。',
            height=330,
        )
        dealer_sample = find_ordinary(7)
        win_sample = find_ordinary(9)
        lose_sample = find_ordinary(5)
        c.create_rectangle(65, 40, 285, 270, fill='#173f3a', outline='#7d9187')
        c.create_text(175, 60, text='庄家', font=('Microsoft YaHei', 11, 'bold'), fill='white')
        draw_hand(c, dealer_sample, 175, 135, label=evaluate_wenzhou_hand(dealer_sample).name, scale=.68, label_y=88)
        c.create_rectangle(370, 40, 590, 270, fill=self.HAND_WIN_BG, outline='#7d9187')
        c.create_text(480, 60, text='顺门 · 获胜', font=('Microsoft YaHei', 11, 'bold'), fill='black')
        draw_hand(c, win_sample, 480, 135, label=evaluate_wenzhou_hand(win_sample).name, scale=.68, label_y=88)
        c.create_rectangle(675, 40, 895, 270, fill=self.HAND_LOSE_BG, outline='#7d9187')
        c.create_text(785, 60, text='出门 · 惜败', font=('Microsoft YaHei', 11, 'bold'), fill='white')
        draw_hand(c, lose_sample, 785, 135, label=evaluate_wenzhou_hand(lose_sample).name, scale=.68, label_y=88)
        c.create_text(487, 305, text='绿色 / 红色只表示该门与庄家的牌面比较结果。', font=small_font, fill=MUTED_INK)

        # 8. Round-end return animation
        c = section(
            '8. 结算后【再来一局】：先归靴，再换整副新牌',
            '桌上的8张活牌先沿平滑轨迹回到本局原来32张牌靴的位置；旧牌靴向右退出，同时下一副完整32张牌从左进入。新牌靴就位后重新开放下注。',
            height=230,
        )
        boxes = [
            (55, '结算完成', '#f6e7bd'),
            (280, '8张牌回原位', '#e8f0f6'),
            (505, '旧牌靴 → 右侧', '#f6dddd'),
            (730, '新牌靴 ← 左侧', '#dff3e8'),
        ]
        for idx,(x,text_,fill) in enumerate(boxes):
            c.create_rectangle(x, 65, x+170, 135, fill=fill, outline='#806d58', width=2)
            c.create_text(x+85, 100, text=text_, font=('Microsoft YaHei', 10, 'bold'), fill=INK)
            if idx < len(boxes)-1:
                c.create_text(x+197, 100, text='→', font=('Arial', 20, 'bold'), fill=BROWN)
        c.create_text(487, 175, text='每局结算后更换下一副完整牌靴。', font=('Microsoft YaHei', 10, 'bold'), fill=BLUE)
        c.create_text(487, 205, text='操作：下注 → 开始游戏 → 两骰 → 四门依序派/开 → 结算 → 再来一局', font=small_font, fill=INK)

        resize_inner()
        win.bind('<Escape>', lambda _event: win.destroy())
        try:
            win.transient(self.winfo_toplevel())
            win.lift()
            win.focus_force()
        except tk.TclError:
            pass



def build_pai_gow_page(parent, balance=10000, user='Guest', on_back=None, on_balance_change=None):
    return WenzhouPaiGowGUI(
        parent, balance=balance, user=user,
        on_back=on_back, on_balance_change=on_balance_change,
    )


def start_pai_gow_gui(balance=10000, user='Guest'):
    root = tk.Tk()
    root.title('温州牌九')
    root.geometry(WINDOW_GEOMETRY)
    root.resizable(False, False)
    page = WenzhouPaiGowGUI(root, balance=balance, user=user)
    page.pack(fill='both', expand=True)
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page


def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        return build_pai_gow_page(
            parent, balance=actual_balance, user=actual_user,
            on_back=on_back, on_balance_change=on_balance_change,
        )
    return start_pai_gow_gui(balance=actual_balance, user=actual_user)


if __name__ == '__main__':
    main()
