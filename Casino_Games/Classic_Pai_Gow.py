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
import tkinter as tk
from dataclasses import dataclass
from itertools import product
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk


# ============================================================
# Classic Pai Gow Tiles — 32-tile casino-style game
# ============================================================
# UI: Canvas-based tiles + Canvas controls.
# Dice rendering/animation follows the same approach as the uploaded Sicbo code:
# PIL-rendered dice faces, secrets-based values, 27-41 shake frames,
# ±15px jitter, then settle on the final three dice.
# ============================================================

WINDOW_GEOMETRY = "1150x750+50+10"

BG = "#17120f"
PANEL = "#211811"
PANEL_LINE = "#665240"
FELT = "#0b4540"
FELT_2 = "#0d5149"
GOLD = "#e7d36c"
GOLD_DARK = "#8d742d"
CREAM = "#f1e7cf"
TEXT = "#f7f1e4"
MUTED = "#c8bda9"
RED = "#d44b4f"
GREEN = "#3f9d66"
BLUE = "#426f93"
DISABLED = "#5b5753"

MIN_ANTE = 10
MAX_ANTE = 25000
CHIPS = [
    (10, "#f4a621", "10"),
    (25, "#22d84b", "25"),
    (100, "#181818", "100"),
    (500, "#e66fb1", "500"),
    (1000, "#f2f2e8", "1K"),
    (2500, "#e52929", "2.5K"),
]

# Casino Pai Gow tiles are long, narrow 2.5:1 rectangles (for example,
# 2.5 inches long by 1 inch wide).  Keep every rendered size derived from
# this single proportion so the table, animations, shoe and instructions do
# not silently drift into Western-domino proportions.
CLASSIC_TILE_ASPECT = 2.5


# ============================================================
# Account compatibility
# ============================================================

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


# ============================================================
# Dice — adapted from uploaded Sicbo implementation
# ============================================================

class Dice:
    def __init__(self):
        self.value = 1

    def roll(self):
        self.value = secrets.randbelow(6) + 1
        return self.value


# ============================================================
# Pai Gow tile model
# ============================================================

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


PAIR_RANK_NAMES = {
    1: "至尊 Gee Joon",
    2: "天牌 Teen",
    3: "地牌 Day",
    4: "人牌 Yun",
    5: "鹅牌 Gor",
    6: "梅牌 Mooy",
    7: "长三 Chong",
    8: "板凳 Bon",
    9: "斧头 Foo",
    10: "红头十 Ping",
    11: "长脚七 Tit",
    12: "大头六 Look",
    13: "杂九 Chop Gow",
    14: "杂八 Chop Bot",
    15: "杂七 Chop Chit",
    16: "杂五 Chop Ng",
}


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


# ============================================================
# Two-tile hand evaluation
# ============================================================

@dataclass(frozen=True)
class HandValue:
    category: int
    primary: int
    secondary: int
    name: str
    points_equiv: int

    @property
    def key(self):
        return (self.category, self.primary, self.secondary)


def is_named_pair(t1, t2):
    return t1.group == t2.group


def _gee_options(tile):
    if not tile.is_gee:
        return [(tile.dots, tile.single_rank)]

    # Official Pai Gow convention: separated Gee Joon tiles are semi-wild.
    # 1-2 may count as 3 or 6; 2-4 may count as 6 or 3.
    # If its counted value flips, its individual ranking flips between
    # the official 15th and 17th positions.
    if tile.shape == (1, 2):
        return [(3, 1), (6, 3)]
    return [(6, 3), (3, 1)]


def evaluate_hand(hand):
    if len(hand) != 2:
        raise ValueError("牌九每一道必须恰好2张牌")
    t1, t2 = hand

    # 1) Named pairs — all pairs outrank all non-pairs.
    if is_named_pair(t1, t2):
        rank = min(t1.pair_rank, t2.pair_rank)
        strength = 17 - rank  # Supreme 16 ... Chop Ng 1
        return HandValue(
            5, strength, 0,
            f"对子 · {PAIR_RANK_NAMES[rank]}",
            12,
        )

    groups = {t1.group, t2.group}
    dots = {t1.dots, t2.dots}

    # 2) Wong: Teen/Day + any 9.
    if 9 in dots and ("Teen" in groups or "Day" in groups):
        teen = "Teen" in groups
        return HandValue(4, 2 if teen else 1, 0,
                         "王 Wong（天牌+9）" if teen else "王 Wong（地牌+9）", 11)

    # 3) Gong: Teen/Day + any 8.
    if 8 in dots and ("Teen" in groups or "Day" in groups):
        teen = "Teen" in groups
        return HandValue(3, 2 if teen else 1, 0,
                         "杠 Gong（天牌+8）" if teen else "杠 Gong（地牌+8）", 10)

    # 4) High Nine: Teen/Day + any 7.
    if 7 in dots and ("Teen" in groups or "Day" in groups):
        teen = "Teen" in groups
        return HandValue(2, 2 if teen else 1, 0,
                         "高九（天牌+7）" if teen else "高九（地牌+7）", 9)

    # 5) Ordinary 0–9 point hand.  Gee Joon may be 3 or 6.
    best = None
    for (v1, r1), (v2, r2) in product(_gee_options(t1), _gee_options(t2)):
        pts = (v1 + v2) % 10
        high_tile = max(r1, r2)
        key = (pts, high_tile)
        if best is None or key > best[0]:
            best = (key, pts, high_tile)
    _, pts, high_tile = best
    if pts == 0:
        high_tile = 0
    return HandValue(1, pts, high_tile, f"{pts}点", pts)


def compare_hand_values(a, b):
    if a.key > b.key:
        return 1
    if a.key < b.key:
        return -1
    return 0


def hand_text(hand):
    hv = evaluate_hand(hand)
    return hv.name


# ============================================================
# Split generation + Traditional House Way
# ============================================================

@dataclass
class SplitChoice:
    low: list
    high: list
    low_value: HandValue
    high_value: HandValue


def all_splits(tiles4):
    if len(tiles4) != 4:
        raise ValueError("分牌必须使用4张牌")
    out = []
    # Exactly three unique pairings: lock tile 0 with each other tile.
    for mate in (1, 2, 3):
        a_idx = [0, mate]
        b_idx = [i for i in range(4) if i not in a_idx]
        a = [tiles4[i] for i in a_idx]
        b = [tiles4[i] for i in b_idx]
        av = evaluate_hand(a)
        bv = evaluate_hand(b)
        if av.key <= bv.key:
            low, high, lv, hv = a, b, av, bv
        else:
            low, high, lv, hv = b, a, bv, av
        out.append(SplitChoice(low, high, lv, hv))
    return out


def _contains_group(tiles, group):
    return any(t.group == group for t in tiles)


def _is_low4(tile):
    return tile.group == "Bon"


def _is_low8(tile):
    return tile.group == "Chop Bot"


def _split_separates_two_highest(choice, tiles4):
    ranked = sorted(tiles4, key=lambda t: t.single_rank, reverse=True)
    top_two = {ranked[0].uid, ranked[1].uid}
    low_ids = {t.uid for t in choice.low}
    high_ids = {t.uid for t in choice.high}
    return not (top_two <= low_ids or top_two <= high_ids)


def traditional_house_way(tiles4):
    """Traditional-style Pai Gow Tiles House Way.

    The implementation follows the traditional ordering:
    two pairs -> individual pair rules -> Wong/Gong/High Nine -> balance.
    Because there are only three possible 2+2 partitions, every decision is
    made by evaluating all three legal settings, then applying the rule order.
    """
    candidates = all_splits(tiles4)

    # --- 1. Never split two pairs.
    both_pair = [c for c in candidates
                 if c.low_value.category == 5 and c.high_value.category == 5]
    if both_pair:
        return max(both_pair, key=lambda c: (c.low_value.key, c.high_value.key))

    # Identify named-pair combinations in the four tiles.
    pair_groups = []
    for i in range(4):
        for j in range(i + 1, 4):
            if is_named_pair(tiles4[i], tiles4[j]):
                ids = frozenset((tiles4[i].uid, tiles4[j].uid))
                if ids not in [p[0] for p in pair_groups]:
                    pair_groups.append((ids, tiles4[i].group, tiles4[i].pair_rank))

    # --- 2. Individual pair rules.
    if len(pair_groups) == 1:
        pair_ids, pair_group, pair_rank = pair_groups[0]
        keep = []
        split = []
        for c in candidates:
            high_ids = {t.uid for t in c.high}
            low_ids = {t.uid for t in c.low}
            if pair_ids <= high_ids or pair_ids <= low_ids:
                keep.append(c)
            else:
                split.append(c)

        keep_choice = max(keep, key=lambda c: (c.high_value.key, c.low_value.key)) if keep else None
        split_choice = max(split, key=lambda c: (c.low_value.key, c.high_value.key)) if split else None

        other_tiles = [t for t in tiles4 if t.uid not in pair_ids]
        other_dots = sorted(t.dots for t in other_tiles)
        should_split = False

        if pair_group == "Gee Joon":
            should_split = (
                6 in other_dots and any(v in (4, 5, 6) for v in other_dots)
            )
        elif pair_group in ("Teen", "Day"):
            if split_choice:
                should_split = (
                    split_choice.low_value.points_equiv >= 6
                    and split_choice.high_value.points_equiv >= 8
                ) or (other_dots == [9, 11])
        elif pair_group in ("Tit", "Chop Chit"):  # 7s
            if split_choice:
                should_split = (
                    split_choice.low_value.points_equiv >= 7
                    and split_choice.high_value.points_equiv >= 9
                )
        elif pair_group in ("Yun", "Chop Bot"):  # 8s
            if split_choice:
                lo = split_choice.low_value.points_equiv
                hi = split_choice.high_value.points_equiv
                should_split = ((lo >= 7 and hi >= 9) or (lo >= 8 and hi >= 8))
        elif pair_group == "Chop Gow":  # 9s
            if split_choice:
                should_split = (
                    split_choice.low_value.points_equiv >= 9
                    and split_choice.high_value.points_equiv >= 9
                )
        else:
            # Traditional way: never split 4s, 5s, 6s, 10s, 11s.
            should_split = False

        if should_split and split_choice:
            return split_choice
        if keep_choice:
            return keep_choice

    # --- 3. Wong / Gong / High Nine.
    strong = [c for c in candidates if c.high_value.category in (2, 3, 4)]
    if strong:
        types = {c.high_value.category for c in strong}
        target = None

        # Traditional exceptions.
        has_11 = any(t.dots == 11 for t in tiles4)
        has_low4 = any(_is_low4(t) for t in tiles4)
        has_any4 = any(t.dots == 4 for t in tiles4)
        has_5 = any(t.dots == 5 for t in tiles4)
        has_low8 = any(_is_low8(t) for t in tiles4)

        if 4 in types and has_11:
            target = 4  # Wong over Gong/High Nine
        elif 4 in types and 2 in types and has_low4:
            target = 4  # Wong over High Nine
        elif 3 in types and 2 in types and has_any4:
            target = 3  # Gong over High Nine
        elif 3 in types and 2 in types and has_5 and has_low8:
            target = 3
        elif len(types) == 1:
            target = next(iter(types))
        else:
            # If 2 or 3 strong types are possible, traditional way prefers
            # High Nine, otherwise Gong; Wong is used only when it is the sole type.
            target = 2 if 2 in types else (3 if 3 in types else 4)

        options = [c for c in strong if c.high_value.category == target]
        return max(options, key=lambda c: (c.low_value.key, c.high_value.key))

    # --- 4. All other hands: maximize the low hand unless it becomes too weak.
    best_low = max(candidates, key=lambda c: (c.low_value.key, c.high_value.key))
    best_high = max(candidates, key=lambda c: (c.high_value.key, c.low_value.key))

    point_pairs = [(c.low_value.points_equiv, c.high_value.points_equiv) for c in candidates]

    # Two ways to play 8/9 -> best high hand.
    if sum(1 for p in point_pairs if p == (8, 9)) >= 2:
        return best_high

    # Choice between 8/8 and 7/9 -> best high when it separates top two tiles.
    if (8, 8) in point_pairs and (7, 9) in point_pairs and _split_separates_two_highest(best_high, tiles4):
        return best_high

    # Two ways to 7/8 with both Teen and Day: place Teen (12) in the high hand.
    if sum(1 for p in point_pairs if p == (7, 8)) >= 2 and _contains_group(tiles4, "Teen") and _contains_group(tiles4, "Day"):
        with_teen_high = [c for c in candidates if any(t.group == "Teen" for t in c.high)]
        if with_teen_high:
            return max(with_teen_high, key=lambda c: (c.low_value.key, c.high_value.key))

    # Two ways to selected balanced totals -> use best high if it separates top two tiles.
    special_balances = {(6, 7), (6, 8), (6, 9), (7, 9)}
    if any(sum(1 for p in point_pairs if p == target) >= 2 for target in special_balances):
        if _split_separates_two_highest(best_high, tiles4):
            return best_high

    # Benchmark: 3 points with High-6 (Chong) as high tile.
    benchmark_3_high6 = (1, 3, 12)
    if best_low.low_value.key < benchmark_3_high6 and best_high.high_value.points_equiv >= 7:
        return best_high

    return best_low


# ============================================================
# Main embedded Canvas GUI
# ============================================================
class ClassicPaiGowGUI(tk.Frame):
    """Classic 32-tile Pai Gow with Canvas-rendered tiles and staged animations."""

    TABLE_X0, TABLE_X1 = 10, 810
    RIGHT_X0, RIGHT_X1 = 820, 1140

    DEALER_ZONE = (24, 154, 796, 304)
    SHOE_ZONE = (24, 314, 796, 454)
    PLAYER_ZONE = (24, 464, 796, 696)

    UNSPLIT_W = 62
    UNSPLIT_H = 98
    # Traditional table presentation: low/front = two horizontal tiles stacked like "=".
    LOW_W = 102
    LOW_H = 48
    HIGH_W = 62       # high/back hand remains two vertical tiles side by side
    HIGH_H = 98

    HAND_WIN_BG = "#c8e6c9"
    HAND_LOSE_BG = "#ffcdd2"
    HAND_NEUTRAL_BG = "#173f3a"

    def __init__(self, parent, balance=10000, user="Guest", on_back=None, on_balance_change=None):
        super().__init__(parent, bg=BG, width=1150, height=750)
        self.pack_propagate(False)
        self.username = user or "Guest"
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

        # Dice animation state.  The animation timings intentionally mirror Sicbo.
        self.dice_objects = [Dice(), Dice(), Dice()]
        self.dice_images_animation = []
        self.dice_images_small = []
        self.animation_dice_items = []
        self.animation_dice_base_positions = []
        self.animation_running = False
        self.animation_frames_left = 0
        self.animation_final_dice = None
        self.animation_after_id = None

        # Canvas buttons.
        self.buttons = {}
        self.action_button_tags = []

        # Betting state.
        self.selected_chip = 10
        self.ante = 0
        self.last_ante = 0

        # Round state.
        self.stage = "betting"
        self.status = "下注后点击【开始游戏】。系统会先摇三颗骰子，再按骰子结果派牌。"
        self.last_result = ""
        self.last_return = 0.0
        self.ante_display_amount = None
        self.ante_display_bg = "#f5f0df"
        self.hand_outcomes = {}

        self.full_tiles = []
        self.stacks = []
        self.position_hands = {}
        self.player_tiles = []
        self.dealer_tiles = []
        self.player_low = []
        self.player_high = []
        self.dealer_low = []
        self.dealer_high = []

        # Manual setting order: clicks 1/2 = low/front; 3/4 = high/back.
        self.selection_order = []

        self.dice_result = []
        self.deal_start_index = None
        self.deal_order = []
        # Eight dealing destinations: banker + six selectable seats + one dead hand.
        self.position_names = [
            "庄家", "1号位", "2号位", "3号位",
            "4号位", "5号位", "6号位", "Dead"
        ]
        self.player_position = 1

        # Dealing/reveal/setting animation state.
        self.deal_wall_visible = False
        self.dealer_dealt_visible = False
        self.player_dealt_visible = False
        self.player_face_up = [False] * 4
        self.dealer_face_up = [False] * 4
        self.deal_stack_markers = {}
        self.arrangement_anim = None
        self.flip_anim = None

        self.create_dice_images()
        self.create_static_ui()
        self.update_display()

    # ---------------------------------------------------- dice (Sicbo style)
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

    # ---------------------------------------------------------- static UI
    def create_static_ui(self):
        c = self.canvas
        c.create_rectangle(0, 0, 1150, 750, fill=BG, outline="", tags="static")

        # Main felt table.
        c.create_rectangle(10, 8, 810, 740, fill=FELT, outline=GOLD_DARK, width=3, tags="static")
        c.create_text(410, 27, text="经典牌九", font=("Arial", 19, "bold"),
                      fill=GOLD, tags="static")

        # Dice / deal summary strip.
        c.create_rectangle(24, 48, 796, 144, fill="#123c38", outline="#6e9185", width=1, tags="static")
        c.create_text(38, 62, anchor="w", text="三骰定派牌起手位", font=("Arial", 11, "bold"),
                      fill="#d9efe8", tags="static")
        self.animation_dice_base_positions = [(174, 91), (242, 91), (310, 91)]
        self.animation_dice_items = [
            c.create_image(x, y, image=self.dice_images_animation[5], tags=("dice", "static"))
            for x, y in self.animation_dice_base_positions
        ]
        self.dice_summary_item = c.create_text(
            354, 78, anchor="w", text="等待开始…", width=420,
            font=("Arial", 11, "bold"), fill=TEXT, tags="static"
        )
        self.deal_order_item = c.create_text(
            354, 103, anchor="w", text="派牌顺序：等待摇骰",
            width=420, font=("Arial", 9, "bold"), fill="#d5cba9", tags="static"
        )
        self.status_item = c.create_text(
            354, 128, anchor="w", text="", width=420,
            font=("Arial", 8, "bold"), fill=MUTED, tags="static"
        )

        # Dealer / shoe / player: the Pai Gow shoe is physically between both hands.
        self.draw_hand_zone(*self.DEALER_ZONE, "庄家", dealer=True)
        sx0, sy0, sx1, sy1 = self.SHOE_ZONE
        c.create_rectangle(sx0, sy0, sx1, sy1, fill="#0a3834", outline="#557b70", width=1, tags="static")
        c.create_text(sx0 + 14, sy0 + 16, anchor="w", text="牌九牌靴",
                      font=("Arial", 10, "bold"), fill="#d9efe8", tags="static")
        self.shoe_status_item = c.create_text(
            sx1 - 14, sy0 + 16, anchor="e", text="32张 · 8叠 × 每叠4张",
            font=("Arial", 8, "bold"), fill=MUTED, tags="static"
        )
        self.draw_hand_zone(*self.PLAYER_ZONE, "玩家", dealer=False)

        # Settlement summary only; the previous long game-instruction box under the player is removed.
        self.result_item = c.create_text(
            410, 720, anchor="center", text="", width=760,
            font=("Arial", 12, "bold"), fill=GOLD, tags="static"
        )

        # Right panel.
        c.create_rectangle(820, 8, 1140, 740, fill=PANEL, outline=PANEL_LINE, width=2, tags="static")
        self.draw_info_card()
        self.draw_limit_card()
        self.draw_bet_card()
        self.draw_position_card()
        self.draw_action_card()

    def draw_hand_zone(self, x0, y0, x1, y1, title, dealer=False):
        c = self.canvas
        fill = "#103f39" if dealer else "#134942"
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#5a887a", width=2, tags="static")
        c.create_text(x0 + 14, y0 + 17, anchor="w", text=title,
                      font=("Arial", 14, "bold"), fill=TEXT, tags="static")
        if dealer:
            self.dealer_zone_title = c.create_text(
                x0 + 82, y0 + 17, anchor="w", text="玩家提交后开牌 · 庄家 House Way",
                font=("Arial", 9), fill=MUTED, tags="static"
            )
        else:
            self.player_zone_title = c.create_text(
                x0 + 82, y0 + 17, anchor="w",
                text="①②前道（横牌上下叠） · ③④后道（直牌并排）",
                font=("Arial", 9, "bold"), fill="#e8d892", tags="static"
            )

    def draw_info_card(self):
        c = self.canvas
        x0, y0, x1, y1 = 832, 20, 1128, 100
        self._card_box(x0, y0, x1, y1, "牌桌信息")
        self.balance_item = c.create_text(x0 + 12, y0 + 42, anchor="w", text="",
                                          font=("Arial", 13, "bold"), fill=TEXT, tags="static")
        self.stage_info_item = c.create_text(x0 + 12, y0 + 66, anchor="w", text="下注阶段",
                                             font=("Arial", 10, "bold"), fill="#dfc77a", tags="static")
        self.help_button = self.create_button(
            x1 - 75, y0 + 39, x1 - 10, y0 + 72,
            "玩法", self.show_detailed_rules, "#315b72", font_size=9, group="static"
        )

    def draw_limit_card(self):
        c = self.canvas
        x0, y0, x1, y1 = 832, 110, 1128, 190
        self._card_box(x0, y0, x1, y1, "下注上限")
        mid = (x0 + x1) / 2
        c.create_line(mid, y0 + 31, mid, y1 - 7, fill="#806d58", width=1, tags="static")
        c.create_text((x0 + mid) / 2, y0 + 44, text="底注最低", font=("Arial", 9, "bold"),
                      fill=TEXT, tags="static")
        c.create_text((mid + x1) / 2, y0 + 44, text="底注最高", font=("Arial", 9, "bold"),
                      fill=TEXT, tags="static")
        c.create_text((x0 + mid) / 2, y0 + 64, text="$10", font=("Arial", 11, "bold"),
                      fill="#dfc77a", tags="static")
        c.create_text((mid + x1) / 2, y0 + 64, text="$25,000", font=("Arial", 11, "bold"),
                      fill="#dfc77a", tags="static")

    def draw_bet_card(self):
        c = self.canvas
        x0, y0, x1, y1 = 832, 200, 1128, 342
        self._card_box(x0, y0, x1, y1, "筹码与底注")

        # Chips stay above the ante, matching the original Pai Gow Poker UI hierarchy.
        chip_y = y0 + 55
        start_x = x0 + 9
        gap = 47
        self.chip_items = {}
        for idx, (value, color, label) in enumerate(CHIPS):
            cx = start_x + idx * gap + 20
            tag = f"chip_{value}"
            outer = c.create_oval(cx - 19, chip_y - 19, cx + 19, chip_y + 19,
                                  fill="#2b2825", outline="#6d655d", width=2,
                                  tags=(tag, "static"))
            inner = c.create_oval(cx - 16, chip_y - 16, cx + 16, chip_y + 16,
                                  fill=color, outline="#ddd", width=1,
                                  tags=(tag, "static"))
            fg = "white" if value in (100, 2500) else "black"
            txt = c.create_text(cx, chip_y, text=label, font=("Arial", 8, "bold"),
                                fill=fg, tags=(tag, "static"))
            c.tag_bind(tag, "<Button-1>", lambda _e, v=value: self.select_chip(v))
            c.tag_bind(tag, "<Enter>", lambda _e: c.configure(cursor="hand2" if self.stage == "betting" else "X_cursor"))
            c.tag_bind(tag, "<Leave>", lambda _e: c.configure(cursor=""))
            self.chip_items[value] = (outer, inner, txt)

        c.create_text(x0 + 63, y0 + 108, text="底注", font=("Arial", 14, "bold"),
                      fill=TEXT, tags="static")
        self.ante_box_tag = "ante_box"
        self.ante_box_rect = c.create_rectangle(x0 + 103, y0 + 88, x0 + 243, y0 + 126,
                                                fill="#f5f0df", outline="#b9a97a", width=2,
                                                tags=(self.ante_box_tag, "static"))
        self.ante_amount_item = c.create_text(x0 + 173, y0 + 107, text="0",
                                              font=("Arial", 15, "bold"), fill="#111",
                                              tags=(self.ante_box_tag, "static"))
        c.tag_bind(self.ante_box_tag, "<Button-1>", lambda _e: self.add_ante())
        c.tag_bind(self.ante_box_tag, "<Button-3>", lambda _e: self.clear_ante())
        c.tag_bind(self.ante_box_tag, "<Enter>", lambda _e: c.configure(cursor="hand2" if self.stage == "betting" else "X_cursor"))
        c.tag_bind(self.ante_box_tag, "<Leave>", lambda _e: c.configure(cursor=""))
        c.create_text(x0 + 173, y0 + 134, text="净赢赔率 0.95 : 1",
                      font=("Arial", 8, "bold"), fill=MUTED, tags="static")

    def draw_position_card(self):
        c = self.canvas
        x0, y0, x1, y1 = 832, 352, 1128, 448
        self._card_box(x0, y0, x1, y1, "玩家位置")
        c.create_text(x0 + 12, y0 + 42, anchor="w", text="选择 1–6 任意位置",
                      font=("Arial", 9, "bold"), fill=TEXT, tags="static")
        self.position_items = {}
        gap = 43
        start_x = x0 + 19
        y = y0 + 70
        for seat in range(1, 7):
            cx = start_x + (seat - 1) * gap + 17
            tag = f"seat_{seat}"
            rect = c.create_rectangle(cx - 16, y - 15, cx + 16, y + 15,
                                      fill="#44382d", outline="#86735f", width=1,
                                      tags=(tag, "static"))
            txt = c.create_text(cx, y, text=str(seat), font=("Arial", 10, "bold"),
                                fill=TEXT, tags=(tag, "static"))
            c.tag_bind(tag, "<Button-1>", lambda _e, s=seat: self.select_player_position(s))
            c.tag_bind(tag, "<Enter>", lambda _e: c.configure(cursor="hand2" if self.stage == "betting" else "X_cursor"))
            c.tag_bind(tag, "<Leave>", lambda _e: c.configure(cursor=""))
            self.position_items[seat] = (rect, txt)

    def draw_action_card(self):
        c = self.canvas
        x0, y0, x1, y1 = 832, 458, 1128, 566
        self.action_bounds = (x0, y0, x1, y1)
        self._card_box(x0, y0, x1, y1, "操作")

    def draw_rules_card(self):
        # Removed from the permanent table UI. Detailed rules remain available via the “玩法” button.
        return

    def _card_box(self, x0, y0, x1, y1, title):
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1, fill="#261e17", outline="#806d58", width=1, tags="static")
        c.create_rectangle(x0, y0, x1, y0 + 28, fill="#d8b46a", outline="#806d58", width=1, tags="static")
        c.create_text((x0 + x1) / 2, y0 + 14, text=title, font=("Arial", 11, "bold"),
                      fill="#2a1b08", tags="static")

    # ------------------------------------------------------ Canvas buttons
    def create_button(self, x0, y0, x1, y1, text, command, fill, fg="white", font_size=10,
                      group="action_dynamic", right_command=None, enabled=True):
        tag = f"button_{len(self.buttons)}_{secrets.randbelow(100000)}"
        face = self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill,
                                            outline="#c9bba5", width=2,
                                            tags=(tag, group))
        txt = self.canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2,
                                      text=text, font=("Arial", font_size, "bold"),
                                      fill=fg, tags=(tag, group))
        self.buttons[tag] = {
            "face": face, "text": txt, "command": command,
            "right_command": right_command,
            "fill": fill, "fg": fg, "enabled": bool(enabled),
            "group": group,
        }

        def click(_event=None):
            b = self.buttons.get(tag)
            if b and b["enabled"]:
                b["command"]()

        def right_click(_event=None):
            b = self.buttons.get(tag)
            if b and b["enabled"] and callable(b.get("right_command")):
                b["right_command"]()

        def enter(_event=None):
            b = self.buttons.get(tag)
            if b and b["enabled"]:
                self.canvas.configure(cursor="hand2")
            else:
                try:
                    self.canvas.configure(cursor="no")
                except tk.TclError:
                    self.canvas.configure(cursor="X_cursor")

        self.canvas.tag_bind(tag, "<Button-1>", click)
        self.canvas.tag_bind(tag, "<Button-3>", right_click)
        self.canvas.tag_bind(tag, "<Enter>", enter)
        self.canvas.tag_bind(tag, "<Leave>", lambda _e: self.canvas.configure(cursor=""))
        self.set_button_enabled(tag, enabled)
        return tag

    def set_button_enabled(self, tag, enabled):
        b = self.buttons.get(tag)
        if not b:
            return
        b["enabled"] = bool(enabled)
        if enabled:
            self.canvas.itemconfigure(b["face"], fill=b["fill"], outline="#c9bba5")
            self.canvas.itemconfigure(b["text"], fill=b["fg"])
        else:
            self.canvas.itemconfigure(b["face"], fill=DISABLED, outline="#77716a")
            self.canvas.itemconfigure(b["text"], fill="#a29d97")

    def render_action_buttons(self):
        self.canvas.delete("action_dynamic")
        for tag in self.action_button_tags:
            self.buttons.pop(tag, None)
        self.action_button_tags = []

        x0, y0, x1, y1 = self.action_bounds
        by0, by1 = y0 + 44, y1 - 14

        if self.stage == "betting":
            repeat_ok = self.last_ante >= MIN_ANTE and self.last_ante <= min(MAX_ANTE, self.balance)
            start_ok = self.ante >= MIN_ANTE and self.ante <= self.balance and not self.animation_running
            self.action_button_tags.append(self.create_button(
                x0 + 12, by0, x0 + 140, by1,
                "重复下注", self.repeat_bet, "#5b4938", font_size=10,
                enabled=repeat_ok
            ))
            self.action_button_tags.append(self.create_button(
                x0 + 156, by0, x1 - 12, by1,
                "开始游戏", self.start_round, "#c69c3b", fg="#111", font_size=10,
                enabled=start_ok
            ))
        elif self.stage == "player_set":
            self.action_button_tags.append(self.create_button(
                x0 + 12, by0, x0 + 140, by1,
                "自动分牌", self.use_house_way, "#426f93", font_size=10
            ))
            self.action_button_tags.append(self.create_button(
                x0 + 156, by0, x1 - 12, by1,
                "提交分牌", self.submit_player_split, "#3f8b61", font_size=10,
                enabled=len(self.selection_order) == 4
            ))
        elif self.stage == "settled":
            tag = self.create_button(
                x0 + 70, by0, x1 - 70, by1,
                "再来一局", self.new_round, "#c69c3b", fg="#111", font_size=11,
                right_command=self.show_full_tile_order
            )
            self.action_button_tags.append(tag)
            self.canvas.create_text(
                (x0 + x1) / 2, y1 - 5,
                text="右键“再来一局”查看本局32张牌完整顺序",
                font=("Arial", 7), fill=MUTED, tags="action_dynamic"
            )
        else:
            self.canvas.create_text(
                (x0 + x1) / 2, (by0 + by1) / 2,
                text="动画进行中，请稍候…",
                font=("Arial", 10, "bold"), fill=MUTED, tags="action_dynamic"
            )

    # ------------------------------------------------------------ player position
    def select_player_position(self, seat):
        if self.stage != "betting":
            return
        try:
            seat = int(seat)
        except (TypeError, ValueError):
            return
        if not 1 <= seat <= 6:
            return
        self.player_position = seat
        self.status = f"玩家位置已选择：{seat}号位。\n下注后点击【开始游戏】。"
        self.update_display()

    def position_display_name(self, position_index):
        if position_index == self.player_position:
            return f"{position_index}号位(玩家)"
        return self.position_names[position_index]

    # ------------------------------------------------------------ betting
    def select_chip(self, value):
        if self.stage != "betting":
            return
        self.selected_chip = value
        for chip_value, (outer, _inner, _txt) in self.chip_items.items():
            self.canvas.itemconfigure(outer, outline=GOLD if chip_value == value else "#6d655d",
                                      width=3 if chip_value == value else 2)

    def add_ante(self):
        if self.stage != "betting":
            return
        self.ante = int(min(MAX_ANTE, self.ante + self.selected_chip))
        self.update_display()

    def clear_ante(self):
        if self.stage != "betting":
            return
        self.ante = 0
        self.update_display()

    def repeat_bet(self):
        if self.stage != "betting" or self.last_ante < MIN_ANTE:
            return
        if self.last_ante > self.balance:
            messagebox.showerror("余额不足", "余额不足以重复上局底注", parent=self.winfo_toplevel())
            return
        self.ante = int(min(MAX_ANTE, self.last_ante))
        self.status = f"已重复上局底注 ${self._fmt(self.ante)}。点击【开始游戏】。"
        self.update_display()

    # ------------------------------------------------------------ round flow
    def start_round(self):
        if self.stage != "betting" or self.animation_running:
            return
        if self.ante < MIN_ANTE:
            messagebox.showerror("底注不足", f"底注至少需要 ${MIN_ANTE}", parent=self.winfo_toplevel())
            return
        if self.ante > self.balance:
            messagebox.showerror("余额不足", "余额不足以支付本局底注", parent=self.winfo_toplevel())
            return

        self.last_ante = int(self.ante)
        self.balance -= self.ante
        self._persist_balance()
        self.stage = "rolling"
        self.status = "停止下注。正在摇三颗骰子；总点数会决定第一叠4张牌先派到哪个位置。"
        self.last_result = ""
        self.last_return = 0.0
        self.ante_display_amount = None
        self.ante_display_bg = "#f5f0df"
        self.hand_outcomes = {}
        self.selection_order = []
        self.player_tiles = []
        self.dealer_tiles = []
        self.player_low = []
        self.player_high = []
        self.dealer_low = []
        self.dealer_high = []
        self.player_face_up = [False] * 4
        self.dealer_face_up = [False] * 4
        self.dealer_dealt_visible = False
        self.player_dealt_visible = False
        self.deal_wall_visible = False
        self.deal_stack_markers = {}
        self.arrangement_anim = None
        self.flip_anim = None
        self.update_display()
        self.roll_dice()

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
            current = [secrets.randbelow(6) + 1 for _ in range(3)]
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
        self.animation_after_id = self.after(320, self.prepare_deal)

    def secure_shuffle(self, seq):
        seq = list(seq)
        for i in range(len(seq) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            seq[i], seq[j] = seq[j], seq[i]
        return seq

    def prepare_deal(self):
        self.animation_running = False
        self.dice_result = list(self.animation_final_dice)
        total = sum(self.dice_result)
        self.deal_start_index = (total - 1) % 8
        self.deal_order = [(self.deal_start_index + i) % 8 for i in range(8)]

        self.full_tiles = self.secure_shuffle(build_pai_gow_set())
        self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
        self.position_hands = {}
        for stack_no, pos in enumerate(self.deal_order):
            self.position_hands[pos] = list(self.stacks[stack_no])

        self.dealer_tiles = list(self.position_hands[0])
        self.player_tiles = list(self.position_hands[self.player_position])

        self.stage = "dealing"
        self.deal_wall_visible = True
        self.status = (
            "牌九牌靴已排好16列 × 上下2张（32张）。每相邻2列为一叠4张；"
            "现在按骰子顺序从牌靴逐叠派发。"
        )
        self.update_display()
        self.after(350, lambda: self.animate_deal_stack(0))

    # -------------------------------------------------------- dealing animation
    def wall_geometry(self):
        # 32 tiles in the Pai Gow shoe: 16 columns × 2 rows, between dealer and player.
        x0 = 78
        y0 = 347
        w, h = 32, 38
        gap_x, gap_y = 9, 8
        return x0, y0, w, h, gap_x, gap_y

    def wall_tile_rect(self, tile_index):
        x0, y0, w, h, gap_x, gap_y = self.wall_geometry()
        col = tile_index // 2
        row = tile_index % 2
        return x0 + col * (w + gap_x), y0 + row * (h + gap_y), w, h

    def draw_deal_wall(self):
        self.canvas.delete("deal_wall")
        if not self.deal_wall_visible or not self.full_tiles:
            return
        for idx, tile_obj in enumerate(self.full_tiles):
            x, y, w, h = self.wall_tile_rect(idx)
            stack_no = idx // 4
            if stack_no in self.deal_stack_markers:
                continue
            self.draw_tile(x, y, w, h, tile_obj, face_up=False, tag=f"wall_{idx}",
                           extra_tag="deal_wall", show_name=False, compact=True)

        # Every two columns = one four-tile hand. Keep the source visually clean: no route badges.
        x0, y0, w, h, gap_x, gap_y = self.wall_geometry()
        for s in range(8):
            first_col = s * 2
            sx = x0 + first_col * (w + gap_x) - 3
            ex = x0 + (first_col + 1) * (w + gap_x) + w + 3
            self.canvas.create_rectangle(sx, y0 - 3, ex, y0 + 2*h + gap_y + 3,
                                         outline="#6f8f85", width=1, tags="deal_wall")
            self.canvas.create_text((sx + ex) / 2, y0 - 9, text=str(s + 1),
                                    font=("Arial", 7, "bold"), fill="#bcd0c8", tags="deal_wall")

    def deal_destination(self, position_index):
        # Dealer/player hands travel from the shoe into their visible hand zones.
        if position_index == 0:
            return (410, 233)
        if position_index == self.player_position:
            return (410, 580)

        # Other seats are still consumed in the correct deal order, but no “passed positions” UI is drawn.
        # They slide to alternating edges of the shoe and disappear after arrival.
        sx0, sy0, sx1, sy1 = self.SHOE_ZONE
        other = [p for p in range(1, 8) if p != self.player_position]
        idx = other.index(position_index) if position_index in other else 0
        if idx % 2 == 0:
            return (sx0 + 18, (sy0 + sy1) / 2)
        return (sx1 - 18, (sy0 + sy1) / 2)

    def animate_deal_stack(self, stack_no):
        if self._closing:
            return
        if stack_no >= 8:
            self.after(280, self.finish_dealing_animation)
            return

        pos = self.deal_order[stack_no]
        dest_x, dest_y = self.deal_destination(pos)
        idxs = list(range(stack_no * 4, stack_no * 4 + 4))
        starts = [self.wall_tile_rect(i) for i in idxs]
        # Centre of the 2x2 four-tile stack.
        sx = sum(x + w/2 for x, y, w, h in starts) / 4
        sy = sum(y + h/2 for x, y, w, h in starts) / 4
        frames = 13

        # Mark the source stack as removed from the wall immediately.
        self.deal_stack_markers[stack_no] = pos
        self.draw_deal_wall()

        def frame(step):
            if self._closing:
                return
            self.canvas.delete("moving_stack")
            t = step / frames
            # Smoothstep.
            t2 = t * t * (3 - 2 * t)
            cx = sx + (dest_x - sx) * t2
            cy = sy + (dest_y - sy) * t2
            mini_w, mini_h = 27, 36
            offsets = [(-16, -20), (16, -20), (-16, 20), (16, 20)]
            for tile_obj, (ox, oy) in zip(self.stacks[stack_no], offsets):
                self.draw_tile(cx + ox - mini_w/2, cy + oy - mini_h/2,
                               mini_w, mini_h, tile_obj, face_up=False,
                               tag="moving_stack", extra_tag="moving_stack",
                               show_name=False, compact=True)
            if step < frames:
                self.after(34, lambda: frame(step + 1))
                return

            self.canvas.delete("moving_stack")
            if pos == 0:
                self.dealer_dealt_visible = True
            elif pos == self.player_position:
                self.player_dealt_visible = True
            self.redraw_tiles()
            self.after(115, lambda: self.animate_deal_stack(stack_no + 1))

        frame(0)

    def finish_dealing_animation(self):
        self.deal_wall_visible = False
        self.canvas.delete("deal_wall")
        self.canvas.delete("deal_marker")
        self.stage = "revealing_player"
        self.status = "派牌完成。先打开玩家4张牌；庄家的牌保持盖住，等玩家提交分牌后才打开。"
        self.update_display()
        self.after(250, lambda: self.animate_flip_owner("player", 0, self.finish_player_reveal))

    # ---------------------------------------------------------- flip animation
    def animate_flip_owner(self, owner, index, done_callback):
        if self._closing:
            return
        tiles = self.player_tiles if owner == "player" else self.dealer_tiles
        faces = self.player_face_up if owner == "player" else self.dealer_face_up
        if index >= len(tiles):
            done_callback()
            return

        frames = 10
        self.flip_anim = {"owner": owner, "index": index, "scale": 1.0}

        def frame(step):
            if self._closing:
                return
            if step <= frames // 2:
                scale = max(0.08, 1.0 - (step / (frames / 2)) * 0.92)
            else:
                if not faces[index]:
                    faces[index] = True
                scale = 0.08 + ((step - frames/2) / (frames/2)) * 0.92
            self.flip_anim["scale"] = scale
            self.redraw_tiles()
            if step < frames:
                self.after(35, lambda: frame(step + 1))
            else:
                faces[index] = True
                self.flip_anim = None
                self.redraw_tiles()
                self.after(85, lambda: self.animate_flip_owner(owner, index + 1, done_callback))

        frame(0)

    def finish_player_reveal(self):
        self.stage = "player_set"
        self.status = (
            "摆牌方法：依次点击4张牌。第①②张会成为【前道】并横放；"
            "第③④张会成为【后道】并直放。后道必须不小于前道。"
        )
        self.update_display()

    # ------------------------------------------------------------- player set
    def player_tile_click(self, index):
        if self.stage != "player_set" or index >= len(self.player_tiles):
            return
        if index in self.selection_order:
            self.selection_order.remove(index)
        elif len(self.selection_order) < 4:
            self.selection_order.append(index)
        self._update_setting_status()
        self.update_display()

    def _update_setting_status(self):
        n = len(self.selection_order)
        if n < 2:
            self.status = f"已选 {n}/4：继续选择；第①②张属于【前道】，提交后会横放。"
        elif n < 4:
            self.status = f"已选 {n}/4：前道已经选好；继续选择第③④张作为【后道】，提交后会直放。"
        else:
            low, high = self.current_selected_hands()
            lv, hv = evaluate_hand(low), evaluate_hand(high)
            legal = hv.key >= lv.key
            self.status = (
                f"前道：{lv.name}（横放）｜后道：{hv.name}（直放）｜"
                + ("摆法合法，可以提交。" if legal else "摆法无效：后道比前道小，请重新点牌。")
            )

    def current_selected_hands(self):
        if len(self.selection_order) != 4:
            return [], []
        low = [self.player_tiles[i] for i in self.selection_order[:2]]
        high = [self.player_tiles[i] for i in self.selection_order[2:4]]
        return low, high

    @staticmethod
    def _ordered_pair(hand):
        return sorted(list(hand), key=lambda t: (t.single_rank, t.dots, t.uid), reverse=True)

    def use_house_way(self):
        if self.stage != "player_set" or len(self.player_tiles) != 4:
            return
        choice = traditional_house_way(self.player_tiles)
        low = self._ordered_pair(choice.low)
        high = self._ordered_pair(choice.high)
        uid_to_idx = {t.uid: i for i, t in enumerate(self.player_tiles)}
        self.selection_order = [uid_to_idx[t.uid] for t in low + high]
        self.status = (
            f"自动分牌完成：①②前道 {choice.low_value.name}；③④后道 {choice.high_value.name}。"
            "金色编号1/2会横放，蓝色编号3/4会直放；确认后点【提交分牌】。"
        )
        self.update_display()

    def submit_player_split(self):
        if self.stage != "player_set":
            return
        if len(self.selection_order) != 4:
            self.status = "请把4张牌都点完：①②前道，③④后道。"
            self.update_display()
            return

        low, high = self.current_selected_hands()
        lv, hv = evaluate_hand(low), evaluate_hand(high)
        if hv.key < lv.key:
            self.status = (
                f"不能提交：前道【{lv.name}】比后道【{hv.name}】大。"
                "请重新点击牌的顺序，或使用【自动分牌】。"
            )
            self.update_display()
            return

        self.stage = "player_arranging"
        self.status = "玩家提交：正在把①②前道旋转为横放，并把③④后道摆成直放…"
        self.update_display()
        self.animate_arrangement("player", self._ordered_pair(low), self._ordered_pair(high), self.begin_dealer_reveal)

    # ------------------------------------------------------ arrange animation
    def unsplit_positions(self, owner):
        if owner == "dealer":
            _, y0, _, y1 = self.DEALER_ZONE
        else:
            _, y0, _, y1 = self.PLAYER_ZONE
        center_y = (y0 + y1) / 2 + 8
        total_w = 4 * self.UNSPLIT_W + 3 * 17
        start_x = 410 - total_w / 2
        return [
            (start_x + i * (self.UNSPLIT_W + 17), center_y - self.UNSPLIT_H / 2,
             self.UNSPLIT_W, self.UNSPLIT_H)
            for i in range(4)
        ]

    def split_positions(self, owner):
        if owner == "dealer":
            _, y0, _, y1 = self.DEALER_ZONE
        else:
            _, y0, _, y1 = self.PLAYER_ZONE
        cy = (y0 + y1) / 2 + 18

        # Front/low: two horizontal tiles stacked vertically, literally like an equals sign “=”.
        low_x = 178
        low_gap = 8
        low_total_h = self.LOW_H * 2 + low_gap
        low_top = cy - low_total_h / 2
        low = [
            (low_x, low_top, self.LOW_W, self.LOW_H),
            (low_x, low_top + self.LOW_H + low_gap, self.LOW_W, self.LOW_H),
        ]

        # Back/high: two vertical tiles side by side.
        high_gap = 18
        high_x = 535
        high = [
            (high_x, cy - self.HIGH_H / 2, self.HIGH_W, self.HIGH_H),
            (high_x + self.HIGH_W + high_gap, cy - self.HIGH_H / 2, self.HIGH_W, self.HIGH_H),
        ]
        return low, high

    def animate_arrangement(self, owner, low, high, done_callback):
        original = self.player_tiles if owner == "player" else self.dealer_tiles
        starts_list = self.unsplit_positions(owner)
        start_by_uid = {t.uid: starts_list[i] for i, t in enumerate(original)}
        low_targets, high_targets = self.split_positions(owner)
        target_by_uid = {}
        for tile_obj, rect in zip(low, low_targets):
            target_by_uid[tile_obj.uid] = rect
        for tile_obj, rect in zip(high, high_targets):
            target_by_uid[tile_obj.uid] = rect

        frames = 16
        self.arrangement_anim = {
            "owner": owner,
            "low_ids": {t.uid for t in low},
            "rects": start_by_uid.copy(),
            "low": list(low), "high": list(high),
        }

        def frame(step):
            if self._closing:
                return
            t = step / frames
            t2 = t * t * (3 - 2 * t)
            rects = {}
            for tile_obj in original:
                sx, sy, sw, sh = start_by_uid[tile_obj.uid]
                tx, ty, tw, th = target_by_uid[tile_obj.uid]
                rects[tile_obj.uid] = (
                    sx + (tx-sx)*t2,
                    sy + (ty-sy)*t2,
                    sw + (tw-sw)*t2,
                    sh + (th-sh)*t2,
                )
            self.arrangement_anim["rects"] = rects
            self.redraw_tiles()
            if step < frames:
                self.after(35, lambda: frame(step + 1))
                return

            if owner == "player":
                self.player_low, self.player_high = list(low), list(high)
            else:
                self.dealer_low, self.dealer_high = list(low), list(high)
            self.arrangement_anim = None
            self.redraw_tiles()  # final location first; point/hand labels now appear
            self.after(420, done_callback)

        frame(0)

    # ------------------------------------------------------------- dealer set
    def begin_dealer_reveal(self):
        self.stage = "revealing_dealer"
        self.status = "玩家已摆好。现在打开庄家4张牌；庄家随后自动按传统 House Way 摆牌。"
        self.update_display()
        self.after(180, lambda: self.animate_flip_owner("dealer", 0, self.finish_dealer_reveal))

    def finish_dealer_reveal(self):
        choice = traditional_house_way(self.dealer_tiles)
        low = self._ordered_pair(choice.low)
        high = self._ordered_pair(choice.high)
        self.stage = "dealer_arranging"
        self.status = f"庄家 House Way：前道 {choice.low_value.name}；后道 {choice.high_value.name}。正在摆牌…"
        self.update_display()
        self.animate_arrangement("dealer", low, high, self.settle_round)

    # --------------------------------------------------------------- settle
    def settle_round(self):
        if not (self.player_low and self.player_high and self.dealer_low and self.dealer_high):
            return
        pl = evaluate_hand(self.player_low)
        ph = evaluate_hand(self.player_high)
        dl = evaluate_hand(self.dealer_low)
        dh = evaluate_hand(self.dealer_high)

        low_cmp = compare_hand_values(pl, dl)
        high_cmp = compare_hand_values(ph, dh)

        # Preserve the existing casino rule: Copy belongs to banker; an ordinary player zero hand cannot win.
        low_win = (low_cmp > 0) and not (pl.category == 1 and pl.primary == 0)
        high_win = (high_cmp > 0) and not (ph.category == 1 and ph.primary == 0)

        # Visual outcome is tracked for every corresponding hand area.
        def state_from_cmp(cmp_value, player_side=True):
            if cmp_value == 0:
                return "tie"
            if player_side:
                return "win" if cmp_value > 0 else "lose"
            return "win" if cmp_value < 0 else "lose"

        self.hand_outcomes = {
            ("player", "low"): state_from_cmp(low_cmp, True),
            ("player", "high"): state_from_cmp(high_cmp, True),
            ("dealer", "low"): state_from_cmp(low_cmp, False),
            ("dealer", "high"): state_from_cmp(high_cmp, False),
        }

        if low_win and high_win:
            profit = self.ante * 0.95
            returned = self.ante + profit
            self.balance += returned
            result = "玩家获胜"
            detail = f"两道全胜｜返还 ${self._fmt(returned)}（净赢 ${self._fmt(profit)}）"
            # Match original Pai Gow Poker: win = gold.
            self.ante_display_bg = "gold"
            self.ante_display_amount = returned
        elif (not low_win) and (not high_win):
            returned = 0.0
            result = "庄家获胜"
            detail = "两道均未胜｜底注输"
            self.ante_display_bg = "white"
            self.ante_display_amount = 0.0
        else:
            returned = float(self.ante)
            self.balance += returned
            result = "Push 平局"
            detail = f"一胜一负｜退回底注 ${self._fmt(returned)}"
            # Match original Pai Gow Poker: push = light blue.
            self.ante_display_bg = "light blue"
            self.ante_display_amount = returned

        def line_result(cmp_value, player_won):
            if cmp_value == 0:
                return "Copy／平局（庄家胜）"
            return "玩家胜" if player_won else "庄家胜"

        self.last_return = returned
        self.last_result = f"{result}　{detail}"
        self.status = (
            f"前道：玩家 {pl.name} vs 庄家 {dl.name} → {line_result(low_cmp, low_win)}　｜　"
            f"后道：玩家 {ph.name} vs 庄家 {dh.name} → {line_result(high_cmp, high_win)}"
        )
        self.stage = "settled"
        self._persist_balance()
        self.update_display()

    def new_round(self):
        if self.stage != "settled":
            return
        self.stage = "betting"
        self.ante = 0
        self.status = f"新一局。玩家位置：{self.player_position}号位；可重新下注或重复上局底注。"
        self.last_result = ""
        self.last_return = 0.0
        self.ante_display_amount = None
        self.ante_display_bg = "#f5f0df"
        self.hand_outcomes = {}
        self.player_tiles = []
        self.dealer_tiles = []
        self.player_low = []
        self.player_high = []
        self.dealer_low = []
        self.dealer_high = []
        self.selection_order = []
        self.dice_result = []
        self.deal_start_index = None
        self.deal_order = []
        self.player_face_up = [False] * 4
        self.dealer_face_up = [False] * 4
        self.dealer_dealt_visible = False
        self.player_dealt_visible = False
        self.deal_wall_visible = False
        self.deal_stack_markers = {}
        self.canvas.delete("deal_wall")
        self.canvas.delete("deal_marker")
        self.canvas.delete("moving_stack")
        for item in self.animation_dice_items:
            self.canvas.itemconfigure(item, image=self.dice_images_animation[5])
        self.update_display()

    # ------------------------------------------------------------ display
    def update_display(self):
        self.canvas.itemconfigure(self.balance_item, text=f"余额：${self.balance:,.2f}")
        stage_map = {
            "betting": "下注阶段", "rolling": "摇骰中", "dealing": "派牌中",
            "revealing_player": "玩家开牌", "player_set": "玩家分牌",
            "player_arranging": "玩家摆牌", "revealing_dealer": "庄家开牌",
            "dealer_arranging": "庄家分牌", "settled": "结算完成",
        }
        self.canvas.itemconfigure(self.stage_info_item, text=stage_map.get(self.stage, self.stage))

        ante_value = self.ante if self.ante_display_amount is None else self.ante_display_amount
        self.canvas.itemconfigure(self.ante_amount_item, text=self._fmt(ante_value))
        self.canvas.itemconfigure(self.ante_box_rect, fill=self.ante_display_bg)
        # Keep the table strip concise; detailed setting information is shown next to the tiles.
        status_line = str(self.status).split("\n", 1)[0]
        if len(status_line) > 58:
            status_line = status_line[:57] + "…"
        self.canvas.itemconfigure(self.status_item, text=status_line)
        self.canvas.itemconfigure(self.result_item, text=self.last_result)

        # Ante/chips and player-position selection are locked outside betting.
        self.canvas.itemconfigure(self.ante_amount_item, fill="#111" if self.stage == "betting" or self.stage == "settled" else "#777")
        for chip_value, (outer, _inner, _txt) in self.chip_items.items():
            self.canvas.itemconfigure(
                outer,
                outline=GOLD if (self.stage == "betting" and chip_value == self.selected_chip) else "#6d655d",
                width=3 if (self.stage == "betting" and chip_value == self.selected_chip) else 2,
            )

        for seat, (rect, txt) in getattr(self, "position_items", {}).items():
            selected = seat == self.player_position
            if self.stage == "betting":
                fill = "#d8b46a" if selected else "#44382d"
                fg = "#2a1b08" if selected else TEXT
                outline = GOLD if selected else "#86735f"
            else:
                fill = "#8b7448" if selected else "#39342f"
                fg = "#1f160b" if selected else "#8f8982"
                outline = "#a88d50" if selected else "#5b5753"
            self.canvas.itemconfigure(rect, fill=fill, outline=outline, width=2 if selected else 1)
            self.canvas.itemconfigure(txt, fill=fg)

        self.update_dice_and_order_text()
        self.redraw_tiles()
        self.render_action_buttons()

    def update_dice_and_order_text(self):
        if not self.dice_result:
            self.canvas.itemconfigure(self.dice_summary_item, text="等待开始…")
            self.canvas.itemconfigure(self.deal_order_item, text=f"玩家位置：{self.player_position}号位　｜　派牌顺序：等待摇骰")
            return
        total = sum(self.dice_result)
        start_name = self.position_display_name(self.deal_start_index)
        self.canvas.itemconfigure(
            self.dice_summary_item,
            text=f"{self.dice_result[0]} + {self.dice_result[1]} + {self.dice_result[2]} = {total}点　→　第1叠：{start_name}"
        )
        sequence = " → ".join(
            f"{idx+1}.{self.position_display_name(pos)}"
            for idx, pos in enumerate(self.deal_order)
        )
        self.canvas.itemconfigure(self.deal_order_item, text=f"派牌顺序：{sequence}")

    def redraw_tiles(self):
        self.canvas.delete("tile_dynamic")
        self.draw_deal_wall()

        # Dealer hand.
        if self.dealer_tiles and self.dealer_dealt_visible:
            if self.arrangement_anim and self.arrangement_anim.get("owner") == "dealer":
                self.draw_arrangement_frame("dealer", self.dealer_tiles)
            elif self.dealer_low and self.dealer_high:
                self.draw_split_hand(self.dealer_low, self.dealer_high, owner="dealer")
            else:
                self.draw_unsplit_hand("dealer", self.dealer_tiles, self.dealer_face_up, selectable=False)

        # Player hand.
        if self.player_tiles and self.player_dealt_visible:
            if self.arrangement_anim and self.arrangement_anim.get("owner") == "player":
                self.draw_arrangement_frame("player", self.player_tiles)
            elif self.player_low and self.player_high:
                self.draw_split_hand(self.player_low, self.player_high, owner="player")
            else:
                self.draw_unsplit_hand(
                    "player", self.player_tiles, self.player_face_up,
                    selectable=(self.stage == "player_set")
                )

        if self.stage == "player_set" and self.player_tiles:
            self.draw_selection_guide()

    def draw_unsplit_hand(self, owner, tiles, face_states, selectable=False):
        positions = self.unsplit_positions(owner)
        for i, tile_obj in enumerate(tiles):
            x, y, w, h = positions[i]
            scale = 1.0
            if self.flip_anim and self.flip_anim.get("owner") == owner and self.flip_anim.get("index") == i:
                scale = self.flip_anim.get("scale", 1.0)
            draw_w = max(6, w * scale)
            draw_x = x + (w - draw_w) / 2
            face_up = face_states[i]
            order_no = None
            role = None
            if owner == "player" and i in self.selection_order:
                order_no = self.selection_order.index(i) + 1
                role = "front" if order_no <= 2 else "back"
            tag = f"{owner}_tile_{i}"
            self.draw_tile(draw_x, y, draw_w, h, tile_obj, face_up=face_up,
                           selected=order_no is not None, order_no=order_no,
                           selection_role=role, tag=tag)
            if selectable and owner == "player":
                self.canvas.tag_bind(tag, "<Button-1>", lambda _e, idx=i: self.player_tile_click(idx))
                self.canvas.tag_bind(tag, "<Enter>", lambda _e: self.canvas.configure(cursor="hand2"))
                self.canvas.tag_bind(tag, "<Leave>", lambda _e: self.canvas.configure(cursor=""))

    def draw_selection_guide(self):
        if len(self.selection_order) == 4:
            low, high = self.current_selected_hands()
            lv, hv = evaluate_hand(low), evaluate_hand(high)
            legal = hv.key >= lv.key
            text = f"①② 前道：{lv.name}（横放）　｜　③④ 后道：{hv.name}（直放）　｜　{'合法' if legal else '无效'}"
            color = GOLD if legal else RED
        else:
            next_no = len(self.selection_order) + 1
            role = "前道（横放）" if next_no <= 2 else "后道（直放）"
            text = f"当前已选 {len(self.selection_order)}/4；下一张是第{next_no}张 → {role}"
            color = "#e8d892"
        self.canvas.create_text(410, 573, text=text, font=("Arial", 9, "bold"),
                                fill=color, tags="tile_dynamic")

    def draw_arrangement_frame(self, owner, tiles):
        rects = self.arrangement_anim.get("rects", {})
        low_ids = self.arrangement_anim.get("low_ids", set())
        for tile_obj in tiles:
            rect = rects.get(tile_obj.uid)
            if not rect:
                continue
            x, y, w, h = rect
            role = "front" if tile_obj.uid in low_ids else "back"
            self.draw_tile(x, y, w, h, tile_obj, face_up=True,
                           selected=False, tag=f"{owner}_arr_{tile_obj.uid}")
        self.draw_split_labels(owner)

    def draw_split_labels(self, owner, low_value=None, high_value=None):
        if owner == "dealer":
            _, y0, _, _ = self.DEALER_ZONE
        else:
            _, y0, _, _ = self.PLAYER_ZONE

        low_text = "前道 · 横放"
        high_text = "后道 · 直放"
        if low_value is not None:
            low_text += f"\n{low_value.name}"
        if high_value is not None:
            high_text += f"\n{high_value.name}"

        low_state = self.hand_outcomes.get((owner, "low"))
        high_state = self.hand_outcomes.get((owner, "high"))
        low_fg = "#17331f" if low_state in ("win", "tie") else ("#6b1c1c" if low_state == "lose" else "#e8d892")
        high_fg = "#17331f" if high_state in ("win", "tie") else ("#6b1c1c" if high_state == "lose" else "#e8d892")

        self.canvas.create_text(229, y0 + 36, text=low_text, width=250, justify="center",
                                font=("Arial", 9, "bold"), fill=low_fg, tags="tile_dynamic")
        self.canvas.create_text(584, y0 + 36, text=high_text, width=250, justify="center",
                                font=("Arial", 9, "bold"), fill=high_fg, tags="tile_dynamic")

    def draw_split_hand(self, low, high, owner):
        low_pos, high_pos = self.split_positions(owner)
        lv, hv = evaluate_hand(low), evaluate_hand(high)

        # Settlement colours belong to the corresponding hand area, not to the whole player/dealer row.
        def hand_bg(role, rects):
            state = self.hand_outcomes.get((owner, role))
            if state in ("win", "tie"):
                fill = self.HAND_WIN_BG
            elif state == "lose":
                fill = self.HAND_LOSE_BG
            else:
                fill = self.HAND_NEUTRAL_BG
            min_x = min(r[0] for r in rects) - 18
            min_y = min(r[1] for r in rects) - 9
            max_x = max(r[0] + r[2] for r in rects) + 18
            max_y = max(r[1] + r[3] for r in rects) + 9
            self.canvas.create_rectangle(min_x, min_y, max_x, max_y, fill=fill,
                                         outline="#7d9187", width=1, tags="tile_dynamic")

        hand_bg("low", low_pos)
        hand_bg("high", high_pos)
        self.draw_split_labels(owner, lv, hv)

        for tile_obj, rect in zip(low, low_pos):
            x, y, w, h = rect
            # Horizontal rendering keeps the tile's a/b order and pip matrices unchanged; only the outer aspect changes.
            self.draw_tile(x, y, w, h, tile_obj, face_up=True,
                           tag=f"{owner}_low_{tile_obj.uid}", show_name=False)
        for tile_obj, rect in zip(high, high_pos):
            x, y, w, h = rect
            self.draw_tile(x, y, w, h, tile_obj, face_up=True,
                           tag=f"{owner}_high_{tile_obj.uid}", show_name=False)

    def draw_tile(self, x, y, w, h, tile, face_up=True, selected=False, order_no=None,
                  selection_role=None, tag="tile", extra_tag="tile_dynamic", show_name=True,
                  compact=False, canvas=None):
        c = canvas or self.canvas
        tags = (tag, extra_tag) if extra_tag else (tag,)
        if selected:
            outline = GOLD if selection_role == "front" else "#59a8e5"
            width = 4
        else:
            outline = "#d8ccb5"
            width = max(1, int(min(w, h) / 32))

        shadow = max(1, min(4, int(min(w, h) / 18)))
        c.create_rectangle(x + shadow, y + shadow, x + w + shadow, y + h + shadow,
                           fill="#050505", outline="", tags=tags)
        c.create_rectangle(x, y, x + w, y + h, fill="#111111", outline=outline, width=width, tags=tags)

        if not face_up:
            inset = max(3, min(8, int(min(w, h) / 6)))
            c.create_rectangle(x + inset, y + inset, x + w - inset, y + h - inset,
                               fill="#1f2624", outline=GOLD_DARK, width=1, tags=tags)
            if not compact and w >= 45 and h >= 60:
                c.create_text(x + w / 2, y + h / 2, text="牌\n九", font=("Arial", max(7, int(min(w,h)/5)), "bold"),
                              fill=GOLD, justify="center", tags=tags)
            return

        horizontal = w > h
        inset = max(3, min(8, int(min(w, h) / 6)))
        if horizontal:
            mid = x + w / 2
            c.create_line(mid, y + inset, mid, y + h - inset, fill="#4d4d4d", width=1, tags=tags)
            self.draw_domino_half(c, x + inset, y + inset, w/2 - inset - 2, h - 2*inset,
                                  tile.a, tags, compact)
            self.draw_domino_half(c, mid + 2, y + inset, w/2 - inset - 2, h - 2*inset,
                                  tile.b, tags, compact)
        else:
            mid = y + h / 2
            c.create_line(x + inset, mid, x + w - inset, mid, fill="#4d4d4d", width=1, tags=tags)
            self.draw_domino_half(c, x + inset, y + inset, w - 2*inset, h/2 - inset - 2,
                                  tile.a, tags, compact)
            self.draw_domino_half(c, x + inset, mid + 2, w - 2*inset, h/2 - inset - 2,
                                  tile.b, tags, compact)

        if show_name and not compact and min(w, h) >= 50:
            label = f"{tile.zh_name}·{tile.dots}"
            c.create_text(x + w / 2, y + h + 11, text=label,
                          font=("Arial", 7, "bold"), fill=TEXT, tags=tags)
        if order_no is not None and c is self.canvas:
            badge = "前" if order_no <= 2 else "后"
            badge_color = GOLD if order_no <= 2 else "#59a8e5"
            c.create_rectangle(x + w - 31, y + 3, x + w - 3, y + 21,
                               fill=badge_color, outline="#2d281d", tags=tags)
            c.create_text(x + w - 17, y + 12, text=f"{badge}{order_no if order_no <= 2 else order_no-2}",
                          font=("Arial", 7, "bold"), fill="#111", tags=tags)

    def draw_domino_half(self, canvas, x, y, w, h, number, tags, compact=False):
        positions = {
            1: [(0.5, 0.5)],
            2: [(0.28, 0.28), (0.72, 0.72)],
            3: [(0.28, 0.28), (0.5, 0.5), (0.72, 0.72)],
            4: [(0.28, 0.28), (0.72, 0.28), (0.28, 0.72), (0.72, 0.72)],
            5: [(0.28, 0.25), (0.72, 0.25), (0.5, 0.5), (0.28, 0.75), (0.72, 0.75)],
            6: [(0.28, 0.20), (0.72, 0.20), (0.28, 0.50), (0.72, 0.50),
                (0.28, 0.80), (0.72, 0.80)],
        }
        pip_color = "#e33b3b" if number in (1, 4) else "#f4f1e8"
        r = max(1.5, min(5, min(w, h) / (10 if not compact else 9)))
        for px, py in positions[number]:
            cx, cy = x + px * w, y + py * h
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                               fill=pip_color, outline="#222", width=1, tags=tags)

    # -------------------------------------------------------- full order popup
    def show_full_tile_order(self):
        if not self.stacks or not self.deal_order:
            return

        # =========================================================
        # Window
        # =========================================================
        win = tk.Toplevel(self)
        win.title("本局32张牌完整顺序")

        WIN_W = 700
        WIN_H = 750

        # 居中显示
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        pos_x = max(0, (screen_w - WIN_W) // 2)
        pos_y = max(0, (screen_h - WIN_H) // 2)

        win.geometry(f"{WIN_W}x{WIN_H}+{pos_x}+{pos_y}")
        win.resizable(False, False)

        # 浅色、较舒服的牌谱窗口
        PAGE_BG = "#efe7d4"
        HEADER_BG = "#f5ecd8"
        CARD_BG = "#fffaf0"
        CARD_BORDER = "#c8b99e"

        TEXT_DARK = "#2b2118"
        TEXT_MUTED = "#756858"
        GOLD_TEXT = "#8a6517"

        PLAYER_BG = "#edf5fc"
        PLAYER_BORDER = "#8eb6d5"

        DEALER_BG = "#fff4d9"
        DEALER_BORDER = "#d2aa58"

        DEAD_BG = "#f0efec"
        DEAD_BORDER = "#b9b5ad"

        OTHER_BG = "#fbf7ec"
        OTHER_BORDER = "#d2c5ad"

        win.configure(bg=PAGE_BG)

        # =========================================================
        # Canvas
        # =========================================================
        canvas = tk.Canvas(
            win,
            width=700,
            height=750,
            bg=PAGE_BG,
            highlightthickness=0,
            bd=0
        )
        canvas.pack(fill="both", expand=True)

        # =========================================================
        # Header
        # =========================================================
        canvas.create_rectangle(
            0, 0, WIN_W, 92,
            fill=HEADER_BG,
            outline=""
        )

        canvas.create_text(
            WIN_W / 2,
            25,
            text="本局32张牌",
            font=("Microsoft YaHei", 18, "bold"),
            fill=GOLD_TEXT
        )

        total = sum(self.dice_result) if self.dice_result else 0

        first_dest = (
            self.position_display_name(self.deal_order[0])
            if self.deal_order
            else "—"
        )

        # V9 有黑/白牌色功能时显示；旧版本也不会报错
        try:
            colour_name = self._tile_colour_name()
        except (AttributeError, KeyError):
            colour_name = ""

        info_parts = [
            f"骰子总点：{total}",
            f"玩家：{self.player_position}号位",
            f"第1叠 → {first_dest}",
        ]

        if colour_name:
            info_parts.append(f"{colour_name}牌九")

        canvas.create_text(
            WIN_W / 2,
            57,
            text="　｜　".join(info_parts),
            font=("Microsoft YaHei", 9, "bold"),
            fill=TEXT_DARK
        )

        canvas.create_text(
            WIN_W / 2,
            78,
            text="依洗牌顺序排列 · 每一格为连续4张牌",
            font=("Microsoft YaHei", 8),
            fill=TEXT_MUTED
        )

        # =========================================================
        # Layout: 2 columns × 4 rows
        # =========================================================
        LEFT_MARGIN = 14
        RIGHT_MARGIN = 14
        COLUMN_GAP = 10

        CARD_W = (
            WIN_W
            - LEFT_MARGIN
            - RIGHT_MARGIN
            - COLUMN_GAP
        ) / 2

        CARD_H = 146
        ROW_GAP = 7
        TOP_Y = 101

        # 每张牌在卡片中的横向 cell
        INNER_PAD = 9
        CELL_W = (CARD_W - INNER_PAD * 2) / 4

        TILE_W = 34
        TILE_H = 54

        for stack_index in range(8):

            # 左边4叠，右边4叠
            col = stack_index % 2
            row = stack_index // 2

            x0 = (
                LEFT_MARGIN
                if col == 0
                else LEFT_MARGIN + CARD_W + COLUMN_GAP
            )

            y0 = TOP_Y + row * (CARD_H + ROW_GAP)

            x1 = x0 + CARD_W
            y1 = y0 + CARD_H

            pos = self.deal_order[stack_index]

            # -----------------------------------------------------
            # Different soft colour according to destination
            # -----------------------------------------------------
            if pos == self.player_position:
                card_fill = PLAYER_BG
                card_outline = PLAYER_BORDER
                dest_fill = "#315e83"
                dest_text = "玩家"

            elif pos == 0:
                card_fill = DEALER_BG
                card_outline = DEALER_BORDER
                dest_fill = "#9a711c"
                dest_text = "庄家"

            elif self.position_display_name(pos) == "Dead":
                card_fill = DEAD_BG
                card_outline = DEAD_BORDER
                dest_fill = "#77736c"
                dest_text = "Dead"

            else:
                card_fill = OTHER_BG
                card_outline = OTHER_BORDER
                dest_fill = "#668064"
                dest_text = self.position_display_name(pos)

            # Card shadow
            canvas.create_rectangle(
                x0 + 2,
                y0 + 3,
                x1 + 2,
                y1 + 3,
                fill="#d9d0c0",
                outline=""
            )

            # Main card
            canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=card_fill,
                outline=card_outline,
                width=1
            )

            # -----------------------------------------------------
            # Stack title
            # -----------------------------------------------------
            canvas.create_text(
                x0 + 11,
                y0 + 17,
                anchor="w",
                text=f"{stack_index + 1}叠",
                font=("Microsoft YaHei", 10, "bold"),
                fill=TEXT_DARK
            )

            # Destination badge
            badge_x1 = x1 - 10
            badge_x0 = badge_x1 - 76

            canvas.create_rectangle(
                badge_x0,
                y0 + 7,
                badge_x1,
                y0 + 28,
                fill=dest_fill,
                outline=""
            )

            canvas.create_text(
                (badge_x0 + badge_x1) / 2,
                y0 + 17.5,
                text=f"→ {dest_text}",
                font=("Microsoft YaHei", 8, "bold"),
                fill="white"
            )

            # Divider
            canvas.create_line(
                x0 + 8,
                y0 + 34,
                x1 - 8,
                y0 + 34,
                fill=card_outline,
                width=1
            )

            # -----------------------------------------------------
            # Four tiles
            # -----------------------------------------------------
            stack_tiles = self.stacks[stack_index]

            for j, tile_obj in enumerate(stack_tiles):

                order_no = stack_index * 4 + j + 1

                cell_cx = (
                    x0
                    + INNER_PAD
                    + CELL_W * j
                    + CELL_W / 2
                )

                tile_x = cell_cx - TILE_W / 2
                tile_y = y0 + 41

                # 实际牌面。
                # 继续调用现有 draw_tile，
                # 因此传统点位及黑/白牌色均会自动沿用。
                self.draw_tile(
                    tile_x,
                    tile_y,
                    TILE_W,
                    TILE_H,
                    tile_obj,
                    face_up=True,
                    tag=f"popup_{stack_index}_{j}",
                    extra_tag=None,
                    show_name=False,
                    compact=True,
                    canvas=canvas
                )

                # #01 / #02...
                canvas.create_text(
                    cell_cx,
                    y0 + 101,
                    text=f"#{order_no:02d}",
                    font=("Arial", 7, "bold"),
                    fill=GOLD_TEXT
                )

                # Tile Chinese name
                canvas.create_text(
                    cell_cx,
                    y0 + 116,
                    text=tile_obj.zh_name,
                    font=("Microsoft YaHei", 8, "bold"),
                    fill=TEXT_DARK
                )

                # Physical denomination
                canvas.create_text(
                    cell_cx,
                    y0 + 132,
                    text=f"{tile_obj.a}-{tile_obj.b} · {tile_obj.dots}点",
                    font=("Arial", 7),
                    fill=TEXT_MUTED
                )

        # =========================================================
        # Bottom separator / hint
        # =========================================================
        canvas.create_line(
            20,
            718,
            WIN_W - 20,
            718,
            fill="#c9bca7"
        )

        canvas.create_text(
            WIN_W / 2,
            734,
            text="关闭此窗口不会影响当前牌局",
            font=("Microsoft YaHei", 8),
            fill=TEXT_MUTED
        )

        # Escape closes the popup
        win.bind("<Escape>", lambda _event: win.destroy())

        # Bring popup to front
        try:
            win.transient(self.winfo_toplevel())
            win.lift()
            win.focus_force()
        except tk.TclError:
            pass

    # ------------------------------------------------------------ rules help
    def show_detailed_rules(self):
        win = tk.Toplevel(self)
        win.title("经典牌九完整图解玩法")
        win.geometry("930x710+110+25")
        win.resizable(False, False)
        win.configure(bg="#efe7d4")

        frame = tk.Frame(win, bg="#efe7d4")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(
            frame, wrap="word", yscrollcommand=scrollbar.set,
            font=("Microsoft YaHei", 11), bg="#fffaf0", fg="#22180f",
            padx=16, pady=14, spacing1=2, spacing3=5
        )
        text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text.yview)

        pair_lines = "\n".join(
            f"  {rank:>2}. {PAIR_RANK_NAMES[rank]}"
            for rank in range(1, 17)
        )
        rules = f"""
经典牌九 从零开始看摆法
========================================

一、先记住：4张不是一起比，而是要拆成两道
你拿到4张骨牌后，要做两手，每手2张：

    你只需要从4张牌里选择【2张作为前道 LOW HAND】→ 提交后两张横放
    剩余2张会自动成为【后道 HIGH HAND】→ 提交后两张直放

界面里的手动操作就是：只点2张前道牌。
• 被选中的2张就是前道。
• 没有被选中的另外2张自动成为后道。
• 如果点错，再点一次该牌即可取消。
• 后道必须不小于前道，否则不能提交。
• 不想自己算，就点【自动分牌】，系统按传统 House Way 自动选择前道2张。

这就是“摆牌”。不是把4张从左到右排大小，而是决定哪两张一起组成前道、哪两张一起组成后道。

二、为什么前道横放、后道直放？
传统牌桌会把 High Hand（后道）直放，把 Low Hand（前道）与它垂直摆放。
本程序提交时会做动画：你选中的2张前道旋转成横牌；剩余2张后道保持直牌，所以你能直接看出哪一道是哪一道。

三、什么叫“天牌、地牌”？
它们首先是【单独的一张骨牌名称】：
• 天牌 Teen = 6-6，共12点，是非常高的单张牌。
• 地牌 Day  = 1-1，共2点，也是非常高排名的单张牌。

注意：牌九不能只看骨牌表面的点数；单张牌还有固定排名。

四、王 Wong、杠 Gong、高九 High Nine 是“组合”，不是新骨牌
当天牌或地牌与某些点数的牌配在一起，会形成特殊两张牌组合：

• 王 Wong  = 天牌/地牌 + 任意9点牌
  例：天牌(12) + 杂九(9) → 王 Wong（天牌+9）

• 杠 Gong  = 天牌/地牌 + 任意8点牌
  例：地牌(2) + 杂八(8) → 杠 Gong（地牌+8）

• 高九 High Nine = 天牌/地牌 + 任意7点牌
  例：地牌(2) + 长脚七(7) → 高九（地牌+7）

所以你之前看到“地高九”，它不是一张叫“地高九”的骨牌；意思只是：
【地牌 + 一张7点牌】组成的 High Nine。
现在主界面已经改成“高九（地牌+7）”，不再用容易误解的缩写。

五、两张牌的大小顺序
从强到弱：
  1. 16种对子 Pair
  2. 王 Wong
  3. 杠 Gong
  4. 高九 High Nine
  5. 普通9点、8点、7点……0点

普通点数算法像百家乐：两张牌点数相加，只保留个位。
例如：
• 11 + 8 = 19 → 9点
• 10 + 7 = 17 → 7点
• 6 + 5 = 11 → 1点

六、至尊 Gee Joon 为什么特殊？
至尊由 2-4（六）和 1-2（三）两张不同骨牌组成，是最高对子。
但如果它们被拆开单独使用，每张可以按3或6计算，以得到更有利的普通点数。

七、16对固定对子排名
{pair_lines}

对子不是按表面点数大小排名，而是上面这套固定次序。

八、House Way 到底在做什么？
4张牌只有3种真正不同的“两两配对”方式。
House Way 会检查这3种分法，然后按传统规则依次处理：
• 先看两对、对子是否应该保留或拆开；
• 再看能否形成王、杠、高九；
• 最后才在普通0～9点之间尽量平衡前后两道。

重点不是“把最大两张放后面”。很多牌如果这样摆，前道会弱得完全没有胜算，所以 House Way 会在两道之间平衡。

九、怎么比庄家？
• 你的前道，只跟庄家前道比。
• 你的后道，只跟庄家后道比。
• 玩家必须严格比庄家大才算赢该道。
• 完全一样（Copy）由庄家赢。
• 0点手不能靠单张牌去赢庄家0点。

整局：
• 两道都赢 → 玩家赢。
• 一道赢、一道没赢 → Push，底注退回。
• 两道都没赢 → 庄家赢。

十、下注与赔率
• 只有底注，没有边注。
• 玩家赢净赔率 0.95 : 1，也就是5%佣金。
• 下注$100，赢时总返还$195（本金100 + 净赢95）。

十一、骰子和派牌动画
• 32张牌先洗牌，然后在桌面排成16列、每列上下2张。
• 每相邻2列合起来就是一叠4张，一共8叠。
• 三颗骰子点数相加，从庄家位置开始计数，决定第1叠先给谁。
• 8个位置仍按这个顺序决定各自对应哪一叠，但动画只实际派庄家与当前玩家位置。
• 没有玩家的位置不会播放派牌动作；玩家和庄家的4张仍真正来自对应牌叠。

十二、三个操作阶段
下注阶段：
  【重复下注】 【开始游戏】

派牌和玩家开牌完成：
  【自动分牌】 【提交分牌】

结算完成：
  【再来一局】
  左键 = 新一局；右键 = 查看刚才32张牌的完整洗牌/派牌顺序。
"""
        text.insert("1.0", rules.strip())
        text.config(state="disabled")

    # ------------------------------------------------------------ utility
    @staticmethod
    def _fmt(value):
        value = float(value)
        if abs(value - round(value)) < 1e-9:
            return f"{value:.0f}"
        return f"{value:.2f}"

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



# ============================================================
# V4 UI / dealing refinement
# ============================================================
class ClassicPaiGowGUIV4(ClassicPaiGowGUI):
    """V4: Pai Gow Poker-style right panel + compact dice strip + selective dealing."""

    TABLE_X0, TABLE_X1 = 10, 800
    RIGHT_X0, RIGHT_X1 = 810, 1150

    # More room for the dealer; the shoe remains between dealer and player.
    DEALER_ZONE = (24, 132, 786, 322)
    SHOE_ZONE = (24, 332, 786, 452)
    PLAYER_ZONE = (24, 462, 786, 718)

    ROOT_BG = "#1B3D31"
    PANEL_BG = "#F2E6C9"
    HEADER_BG = "#D8B46A"
    TITLE_FG = "#2A1B08"

    def create_static_ui(self):
        c = self.canvas
        c.create_rectangle(0, 0, 1150, 750, fill=BG, outline="", tags="static")

        # Left table only.  The right side is a real Tk panel matching Pai Gow Poker.
        c.create_rectangle(10, 8, 800, 740, fill=FELT, outline=GOLD_DARK, width=3, tags="static")
        c.create_text(405, 27, text="经典牌九", font=("Arial", 19, "bold"),
                      fill=GOLD, tags="static")

        # Compact dice strip: dice images + total + ordinal only.
        c.create_rectangle(24, 48, 786, 122, fill="#123c38", outline="#6e9185", width=1, tags="static")
        c.create_text(38, 85, anchor="w", text="三骰", font=("Arial", 11, "bold"),
                      fill="#d9efe8", tags="static")
        self.animation_dice_base_positions = [(145, 85), (218, 85), (291, 85)]
        self.animation_dice_items = [
            c.create_image(x, y, image=self.dice_images_animation[5], tags=("dice", "static"))
            for x, y in self.animation_dice_base_positions
        ]
        c.create_text(181, 85, text="+", font=("Arial", 17, "bold"), fill=TEXT, tags="static")
        c.create_text(254, 85, text="+", font=("Arial", 17, "bold"), fill=TEXT, tags="static")
        self.dice_summary_item = c.create_text(
            334, 85, anchor="w", text="= --点　｜　第--个派牌",
            font=("Arial", 13, "bold"), fill=TEXT, tags="static"
        )

        self.draw_hand_zone(*self.DEALER_ZONE, "庄家", dealer=True)
        # The shoe itself is dynamic and is hidden until Start Game is pressed.
        self.draw_hand_zone(*self.PLAYER_ZONE, "玩家", dealer=False)

        self.result_item = c.create_text(
            405, 730, anchor="center", text="", width=750,
            font=("Arial", 12, "bold"), fill=GOLD, tags="static"
        )

        self.create_right_panel_widgets()

    def draw_hand_zone(self, x0, y0, x1, y1, title, dealer=False):
        c = self.canvas
        fill = "#103f39" if dealer else "#134942"
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#5a887a", width=2, tags="static")
        item = c.create_text(
            x0 + 14, y0 + 18, anchor="w", text=title,
            font=("Arial", 15, "bold"), fill=TEXT, tags="static"
        )
        if dealer:
            self.dealer_header_item = item
        else:
            self.player_header_item = item

    # ------------------------------ Pai Gow Poker-style right panel (Tk widgets)
    def create_right_panel_widgets(self):
        panel = tk.Frame(self, bg=self.ROOT_BG, width=340, height=734)
        panel.place(x=810, y=8, width=340, height=734)
        panel.pack_propagate(False)
        self.right_panel = panel

        # 1. Information card.
        info_card = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=3)
        h = tk.Frame(info_card, bg=self.HEADER_BG)
        h.pack(fill=tk.X)
        tk.Label(h, text="经典牌九", font=('Arial', 13, 'bold'),
                 bg=self.HEADER_BG, fg=self.TITLE_FG).pack(pady=3)
        body = tk.Frame(info_card, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=10, pady=5)
        self.balance_label = tk.Label(body, text="余额: $0.00", font=('Arial', 14, 'bold'),
                                      bg=self.PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body, text="下注阶段", font=('Arial', 14, 'bold'),
                                    bg=self.PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        # 2. Limits card — same card language as Pai Gow Poker, only relevant columns retained.
        limit_card = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        h = tk.Frame(limit_card, bg=self.HEADER_BG)
        h.pack(fill=tk.X)
        tk.Label(h, text="下注上限", font=('Arial', 12, 'bold'),
                 bg=self.HEADER_BG, fg=self.TITLE_FG).pack(pady=3)
        body = tk.Frame(limit_card, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=8, pady=5)
        table = tk.Frame(body, bg=self.PANEL_BG)
        table.pack(fill=tk.X)
        for col, title in enumerate(("底注最低", "底注最高")):
            tk.Label(table, text=title, font=('Arial', 9, 'bold'), bg=self.PANEL_BG,
                     relief=tk.SOLID, borderwidth=1).grid(row=0, column=col, sticky='nsew')
        for col, value in enumerate(("$10", "$25,000")):
            tk.Label(table, text=value, font=('Arial', 10, 'bold'), bg=self.PANEL_BG,
                     fg='#A88100', relief=tk.SOLID, borderwidth=1).grid(row=1, column=col, sticky='nsew')
            table.columnconfigure(col, weight=1)

        # 3. Chips + ante, same visual language as the Poker version.
        bet_card = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
        bet_card.pack(fill=tk.X, pady=3)
        h = tk.Frame(bet_card, bg=self.HEADER_BG)
        h.pack(fill=tk.X)
        tk.Label(h, text="筹码与下注", font=('Arial', 12, 'bold'),
                 bg=self.HEADER_BG, fg=self.TITLE_FG).pack(pady=3)
        body = tk.Frame(bet_card, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=7, pady=5)

        chip_row = tk.Frame(body, bg=self.PANEL_BG)
        chip_row.pack(fill=tk.X, pady=(0, 6))
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)
        self.chip_canvases = {}
        display_labels = {10:"$10", 25:"$25", 100:"$100", 500:"$500", 1000:"$1K", 2500:"$2.5K"}
        for col, (value, color, _old_label) in enumerate(CHIPS):
            cell = tk.Frame(chip_row, bg=self.PANEL_BG)
            cell.grid(row=0, column=col, sticky='nsew', padx=1)
            cv = tk.Canvas(cell, width=45, height=45, bg=self.PANEL_BG, highlightthickness=0)
            cv.pack(anchor='center')
            oval = cv.create_oval(2, 2, 43, 43, fill=color, outline='black', width=1)
            fg = 'white' if value in (100, 2500) else 'black'
            cv.create_text(22.5, 22.5, text=display_labels[value], fill=fg,
                           font=('Arial', 9, 'bold'))
            cv.bind('<Button-1>', lambda _e, v=value: self.select_chip(v))
            cv.bind('<Enter>', lambda _e, w=cv: self._bet_cursor(w))
            cv.bind('<Leave>', lambda _e, w=cv: w.config(cursor=''))
            self.chip_canvases[value] = (cv, oval)

        ante_row = tk.Frame(body, bg=self.PANEL_BG)
        ante_row.pack(fill=tk.X, pady=(2, 1))
        inner = tk.Frame(ante_row, bg=self.PANEL_BG)
        inner.pack(anchor='center')
        tk.Label(inner, text="底注:", font=('Arial', 15, 'bold'), bg=self.PANEL_BG).pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(inner, textvariable=self.ante_var, font=('Arial', 15, 'bold'),
                                     bg='white', fg='black', width=11, relief=tk.SUNKEN, anchor='center')
        self.ante_display.pack(side=tk.LEFT, padx=(6, 0))
        self.ante_display.bind('<Button-1>', lambda _e: self.add_ante())
        self.ante_display.bind('<Button-3>', lambda _e: self.clear_ante())
        self.ante_display.bind('<Enter>', lambda _e: self._bet_cursor(self.ante_display))
        self.ante_display.bind('<Leave>', lambda _e: self.ante_display.config(cursor=''))
        tk.Label(body, text="净赢赔率 0.95 : 1", font=('Arial', 8, 'bold'),
                 bg=self.PANEL_BG, fg='#6B6251').pack(pady=(1, 0))

        # 4. Player position card, directly above Action.
        seat_card = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
        seat_card.pack(fill=tk.X, pady=3)
        h = tk.Frame(seat_card, bg=self.HEADER_BG)
        h.pack(fill=tk.X)
        tk.Label(h, text="玩家位置", font=('Arial', 12, 'bold'),
                 bg=self.HEADER_BG, fg=self.TITLE_FG).pack(pady=3)
        body = tk.Frame(seat_card, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=8, pady=6)
        tk.Label(body, text="选择 1–6 任意位置", font=('Arial', 9, 'bold'),
                 bg=self.PANEL_BG, fg=self.TITLE_FG).pack(anchor='w', pady=(0, 4))
        row = tk.Frame(body, bg=self.PANEL_BG)
        row.pack(fill=tk.X)
        self.position_buttons = {}
        for i in range(6):
            row.columnconfigure(i, weight=1)
        for seat in range(1, 7):
            b = tk.Button(row, text=str(seat), font=('Arial', 10, 'bold'), width=3,
                          command=lambda s=seat: self.select_player_position(s),
                          relief=tk.RAISED, bd=1)
            b.grid(row=0, column=seat-1, padx=2, sticky='ew')
            self.position_buttons[seat] = b

        # 5. Fixed-height Action card, same behaviour as Pai Gow Poker.
        action_card = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID, height=134)
        action_card.pack(fill=tk.X, pady=3)
        action_card.pack_propagate(False)
        h = tk.Frame(action_card, bg=self.HEADER_BG, height=26)
        h.pack(fill=tk.X)
        h.pack_propagate(False)
        tk.Label(h, text="操作", font=('Arial', 12, 'bold'),
                 bg=self.HEADER_BG, fg=self.TITLE_FG).pack(expand=True)
        body = tk.Frame(action_card, bg=self.PANEL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=7, pady=4)
        self.status_label = tk.Label(body, text="设置下注金额并开始游戏", font=('Arial', 10, 'bold'),
                                     bg=self.PANEL_BG, fg=self.TITLE_FG,
                                     wraplength=310, justify=tk.CENTER, height=3)
        self.status_label.pack(fill=tk.X, pady=(0, 2))
        self.action_frame = tk.Frame(body, bg=self.PANEL_BG, height=42)
        self.action_frame.pack(fill=tk.X, pady=1)
        self.action_frame.pack_propagate(False)

        # 6. Bottom information card, including the same small info button.
        bottom = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
        bottom.pack(fill=tk.X, pady=3)
        body = tk.Frame(bottom, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=8, pady=4)
        self.current_bet_label = tk.Label(body, text="本局下注: $0.00", font=('Arial', 10),
                                          bg=self.PANEL_BG, fg='black')
        self.current_bet_label.pack(anchor='w')
        row = tk.Frame(body, bg=self.PANEL_BG)
        row.pack(fill=tk.X)
        self.last_win_label = tk.Label(row, text="上局获胜: $0.00", font=('Arial', 10),
                                       bg=self.PANEL_BG, fg='black')
        self.last_win_label.pack(side=tk.LEFT)
        tk.Button(row, text="ℹ️", command=self.show_detailed_rules, bg='#4B8BBE', fg='white',
                  font=('Arial', 9), width=2, relief=tk.FLAT).pack(side=tk.RIGHT)

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

    def render_action_buttons(self):
        for w in self.action_frame.winfo_children():
            w.destroy()

        # In the settled phase the single button occupies the visual centre of the
        # entire Action body.  In all other phases the normal status text remains
        # above the two-button row.
        if self.stage == 'settled':
            self.status_label.pack_forget()
            self.action_frame.pack_forget()
            self.action_frame.pack(fill=tk.BOTH, expand=True, pady=1)
        else:
            self.action_frame.pack_forget()
            if not self.status_label.winfo_manager():
                self.status_label.pack(fill=tk.X, pady=(0, 2))
            self.action_frame.pack(fill=tk.X, pady=1)

        def make_btn(text, command, bg, enabled=True, right_command=None, fg='white'):
            b = tk.Button(self.action_frame, text=text, command=command,
                          font=('Arial', 11, 'bold'), bg=bg, fg=fg,
                          activebackground=bg, relief=tk.RAISED,
                          state=tk.NORMAL if enabled else tk.DISABLED)
            if right_command is not None:
                b.bind('<Button-3>', lambda _e: right_command())
            return b

        if self.stage == 'betting':
            repeat_ok = self.last_ante >= MIN_ANTE and self.last_ante <= min(MAX_ANTE, self.balance)
            start_ok = self.ante >= MIN_ANTE and self.ante <= self.balance and not self.animation_running
            for i in range(2):
                self.action_frame.columnconfigure(i, weight=1)
            make_btn('重复下注', self.repeat_bet, '#FFC107', repeat_ok, fg='black').grid(
                row=0, column=0, sticky='nsew', padx=(0, 3), pady=1)
            make_btn('开始游戏', self.start_round, '#4CAF50', start_ok).grid(
                row=0, column=1, sticky='nsew', padx=(3, 0), pady=1)
        elif self.stage == 'player_set':
            for i in range(2):
                self.action_frame.columnconfigure(i, weight=1)
            make_btn('自动分牌', self.use_house_way, '#4B8BBE').grid(
                row=0, column=0, sticky='nsew', padx=(0, 3), pady=1)
            make_btn('提交分牌', self.submit_player_split, '#4CAF50', len(self.selection_order) == 4).grid(
                row=0, column=1, sticky='nsew', padx=(3, 0), pady=1)
        elif self.stage == 'settled':
            self.action_frame.columnconfigure(0, weight=1)
            make_btn('再来一局', self.new_round, '#FFC107', True,
                     right_command=self.show_full_tile_order, fg='black').grid(
                row=0, column=0, sticky='nsew', padx=45, pady=1)
        else:
            tk.Label(self.action_frame, text='动画进行中，请稍候…', font=('Arial', 10, 'bold'),
                     bg=self.PANEL_BG, fg='#6B6251').pack(expand=True)

    @staticmethod
    def _short_hand_name(value):
        if value.category == 5:
            return value.name.replace('对子 · ', '')
        if value.category == 4:
            return '天9' if value.primary == 2 else '地9'
        if value.category == 3:
            return '天8' if value.primary == 2 else '地8'
        if value.category == 2:
            return '天7' if value.primary == 2 else '地7'
        return f'{value.primary}点'

    def _update_hand_headers(self):
        dealer_text = '庄家'
        player_text = '玩家'
        if self.dealer_low and self.dealer_high:
            dealer_text = f"庄家 - {self._short_hand_name(evaluate_hand(self.dealer_low))} & {self._short_hand_name(evaluate_hand(self.dealer_high))}"
        if self.player_low and self.player_high:
            player_text = f"玩家 - {self._short_hand_name(evaluate_hand(self.player_low))} & {self._short_hand_name(evaluate_hand(self.player_high))}"
        self.canvas.itemconfigure(self.dealer_header_item, text=dealer_text)
        self.canvas.itemconfigure(self.player_header_item, text=player_text)

    def draw_split_labels(self, owner, low_value=None, high_value=None):
        # Combined hand values are shown in the Pai Gow Poker-style owner label.
        # Keep only compact orientation labels above each physical hand.
        _, y0, _, _ = self.DEALER_ZONE if owner == 'dealer' else self.PLAYER_ZONE
        self.canvas.create_text(229, y0 + 46, text='前道 · 横放', width=220, justify='center',
                                font=('Arial', 9, 'bold'), fill='#e8d892', tags='tile_dynamic')
        self.canvas.create_text(584, y0 + 46, text='后道 · 直放', width=220, justify='center',
                                font=('Arial', 9, 'bold'), fill='#e8d892', tags='tile_dynamic')

    # ------------------------------ Shoe / deal changes
    def start_round(self):
        if self.stage != 'betting' or self.animation_running:
            return
        if self.ante < MIN_ANTE:
            messagebox.showerror('底注不足', f'底注至少需要 ${MIN_ANTE}', parent=self.winfo_toplevel())
            return
        if self.ante > self.balance:
            messagebox.showerror('余额不足', '余额不足以支付本局底注', parent=self.winfo_toplevel())
            return

        self.last_ante = int(self.ante)
        self.balance -= self.ante
        self._persist_balance()
        self.stage = 'rolling'
        self.status = '正在摇骰；牌九牌靴已经放出32张牌。'
        self.last_result = ''
        self.last_return = 0.0
        self.ante_display_amount = None
        self.ante_display_bg = 'white'
        self.hand_outcomes = {}
        self.selection_order = []
        self.player_tiles = []
        self.dealer_tiles = []
        self.player_low = []
        self.player_high = []
        self.dealer_low = []
        self.dealer_high = []
        self.player_face_up = [False] * 4
        self.dealer_face_up = [False] * 4
        self.dealer_dealt_visible = False
        self.player_dealt_visible = False
        self.deal_stack_markers = {}
        self.arrangement_anim = None
        self.flip_anim = None

        # Shoe becomes visible immediately when Start Game is pressed.
        self.full_tiles = self.secure_shuffle(build_pai_gow_set())
        self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
        self.deal_wall_visible = True
        self.update_display()
        self.roll_dice()

    def prepare_deal(self):
        self.animation_running = False
        self.dice_result = list(self.animation_final_dice)
        total = sum(self.dice_result)
        self.deal_start_index = (total - 1) % 8
        self.deal_order = [(self.deal_start_index + i) % 8 for i in range(8)]

        # The shoe was already shuffled and displayed at Start Game; do not reshuffle here.
        if not self.full_tiles or len(self.full_tiles) != 32:
            self.full_tiles = self.secure_shuffle(build_pai_gow_set())
            self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]

        self.position_hands = {}
        for stack_no, pos in enumerate(self.deal_order):
            self.position_hands[pos] = list(self.stacks[stack_no])
        self.dealer_tiles = list(self.position_hands[0])
        self.player_tiles = list(self.position_hands[self.player_position])

        self.stage = 'dealing'
        self.status = '按牌靴横向顺序，仅派庄家和当前玩家位置；\n其他牌叠留在牌靴内。'
        self.update_display()
        self.after(280, lambda: self.animate_deal_stack(0))

    def wall_geometry(self):
        x0 = 68
        y0 = 362
        w, h = 32, 34
        gap_x, gap_y = 9, 7
        return x0, y0, w, h, gap_x, gap_y

    def draw_deal_wall(self):
        self.canvas.delete('deal_wall')
        if not self.deal_wall_visible or not self.full_tiles:
            return
        sx0, sy0, sx1, sy1 = self.SHOE_ZONE
        self.canvas.create_rectangle(sx0, sy0, sx1, sy1, fill='#0a3834', outline='#557b70', width=1,
                                     tags='deal_wall')
        self.canvas.create_text(sx0 + 14, sy0 + 16, anchor='w', text='牌九牌靴',
                                font=('Arial', 10, 'bold'), fill='#d9efe8', tags='deal_wall')
        self.canvas.create_text(sx1 - 14, sy0 + 16, anchor='e', text='32张 · 16栋',
                                font=('Arial', 8, 'bold'), fill=MUTED, tags='deal_wall')
        for idx, tile_obj in enumerate(self.full_tiles):
            stack_no = idx // 4
            # Only dealer/player stacks physically leave the shoe.
            if stack_no in self.deal_stack_markers:
                continue
            x, y, w, h = self.wall_tile_rect(idx)
            self.draw_tile(x, y, w, h, tile_obj, face_up=False, tag=f'wall_{idx}',
                           extra_tag='deal_wall', show_name=False, compact=True)

        # A subtle outline every two columns shows the 4-tile grouping without route text.
        x0, y0, w, h, gap_x, gap_y = self.wall_geometry()
        for s in range(8):
            first_col = s * 2
            x_a = x0 + first_col * (w + gap_x) - 3
            x_b = x0 + (first_col + 1) * (w + gap_x) + w + 3
            self.canvas.create_rectangle(x_a, y0 - 3, x_b, y0 + 2*h + gap_y + 3,
                                         outline='#6f8f85', width=1, tags='deal_wall')

    def deal_destination(self, position_index):
        if position_index == 0:
            return (405, (self.DEALER_ZONE[1] + self.DEALER_ZONE[3]) / 2 + 12)
        if position_index == self.player_position:
            return (405, (self.PLAYER_ZONE[1] + self.PLAYER_ZONE[3]) / 2 + 15)
        return (405, (self.SHOE_ZONE[1] + self.SHOE_ZONE[3]) / 2)

    def animate_deal_stack(self, stack_no):
        if self._closing:
            return
        if stack_no >= 8:
            self.after(250, self.finish_dealing_animation)
            return

        pos = self.deal_order[stack_no]
        # No animation and no removal for unused seats. Continue in horizontal shoe order.
        if pos not in (0, self.player_position):
            self.after(35, lambda: self.animate_deal_stack(stack_no + 1))
            return

        dest_x, dest_y = self.deal_destination(pos)
        idxs = list(range(stack_no * 4, stack_no * 4 + 4))
        starts = [self.wall_tile_rect(i) for i in idxs]
        sx = sum(x + w/2 for x, y, w, h in starts) / 4
        sy = sum(y + h/2 for x, y, w, h in starts) / 4
        frames = 14
        self.deal_stack_markers[stack_no] = pos
        self.draw_deal_wall()

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('moving_stack')
            t = step / frames
            t2 = t*t*(3-2*t)
            cx = sx + (dest_x-sx)*t2
            cy = sy + (dest_y-sy)*t2
            mini_w, mini_h = 27, 36
            offsets = [(-16, -20), (16, -20), (-16, 20), (16, 20)]
            for tile_obj, (ox, oy) in zip(self.stacks[stack_no], offsets):
                self.draw_tile(cx + ox - mini_w/2, cy + oy - mini_h/2,
                               mini_w, mini_h, tile_obj, face_up=False,
                               tag='moving_stack', extra_tag='moving_stack',
                               show_name=False, compact=True)
            if step < frames:
                self.after(34, lambda: frame(step + 1))
                return
            self.canvas.delete('moving_stack')
            if pos == 0:
                self.dealer_dealt_visible = True
            else:
                self.player_dealt_visible = True
            self.redraw_tiles()
            self.after(130, lambda: self.animate_deal_stack(stack_no + 1))
        frame(0)

    def finish_dealing_animation(self):
        # Keep the remaining 24 tiles visible in the shoe for the rest of the round.
        self.stage = 'revealing_player'
        self.status = '派牌完成。打开玩家4张；庄家保持盖牌。'
        self.update_display()
        self.after(250, lambda: self.animate_flip_owner('player', 0, self.finish_player_reveal))

    # ------------------------------ concise dice + general display
    def update_dice_and_order_text(self):
        if not self.dice_result:
            self.canvas.itemconfigure(self.dice_summary_item, text='= --点　｜　第--个派牌')
            return
        total = sum(self.dice_result)
        ordinal = self.deal_start_index + 1 if self.deal_start_index is not None else ((total - 1) % 8 + 1)
        self.canvas.itemconfigure(self.dice_summary_item, text=f'= {total}点　｜　第{ordinal}个派牌')

    def redraw_tiles(self):
        super().redraw_tiles()
        self._update_hand_headers()

    def update_display(self):
        stage_map = {
            'betting':'下注阶段', 'rolling':'摇骰中', 'dealing':'派牌中',
            'revealing_player':'玩家开牌', 'player_set':'玩家分牌',
            'player_arranging':'玩家摆牌', 'revealing_dealer':'庄家开牌',
            'dealer_arranging':'庄家分牌', 'settled':'结算完成',
        }
        self.balance_label.config(text=f'余额: ${self.balance:,.2f}')
        self.stage_label.config(text=stage_map.get(self.stage, self.stage))
        ante_value = self.ante if self.ante_display_amount is None else self.ante_display_amount
        self.ante_var.set(self._fmt(ante_value))
        display_bg = 'white' if self.ante_display_bg == '#f5f0df' else self.ante_display_bg
        self.ante_display.config(bg=display_bg, fg='black')
        self.current_bet_label.config(text=f'本局下注: ${self._fmt(self.ante)}')
        self.last_win_label.config(text=f'上局获胜: ${self._fmt(self.last_return)}')

        status_line = str(self.status).split('\n', 1)[0]
        self.status_label.config(text=status_line)

        betting = self.stage == 'betting'
        try:
            self.ante_display.config(cursor='hand2' if betting else 'no')
        except tk.TclError:
            self.ante_display.config(cursor='hand2' if betting else 'X_cursor')
        self._update_chip_ui()

        for seat, button in self.position_buttons.items():
            selected = seat == self.player_position
            if betting:
                button.config(
                    state=tk.NORMAL,
                    bg=self.HEADER_BG if selected else '#E6E0D3',
                    fg=self.TITLE_FG,
                    activebackground=self.HEADER_BG if selected else '#EEE8DC',
                    relief=tk.SUNKEN if selected else tk.RAISED,
                    cursor='hand2',
                )
            else:
                button.config(
                    state=tk.DISABLED,
                    bg='#D0D0D0' if not selected else '#C4B17A',
                    disabledforeground='#555555',
                    relief=tk.SUNKEN if selected else tk.RAISED,
                    cursor='arrow',
                )

        self.update_dice_and_order_text()
        self.canvas.itemconfigure(self.result_item, text=self.last_result)
        self.redraw_tiles()
        self.render_action_buttons()




# ============================================================
# V5 — elongated tiles, physical rotation and cleaner table
# ============================================================
class ClassicPaiGowGUIV5(ClassicPaiGowGUIV4):
    # Give the dealer enough vertical room and use a genuinely elongated domino silhouette.
    DEALER_ZONE = (24, 132, 786, 322)
    SHOE_ZONE = (24, 332, 786, 452)
    PLAYER_ZONE = (24, 462, 786, 728)

    # Classic casino-tile silhouette: length = 2.5 × width.
    UNSPLIT_W = 48
    UNSPLIT_H = int(UNSPLIT_W * CLASSIC_TILE_ASPECT)
    LOW_W = UNSPLIT_H
    LOW_H = UNSPLIT_W
    HIGH_W = UNSPLIT_W
    HIGH_H = UNSPLIT_H

    def create_static_ui(self):
        super().create_static_ui()
        # The bottom-of-player settlement sentence is deliberately removed.
        # Settlement remains visible through hand-area colours, the ante box,
        # and the right-side information/status controls.
        try:
            self.canvas.itemconfigure(self.result_item, state='hidden')
        except tk.TclError:
            pass

    # --------------------------------------------------------- concise hand labels
    @staticmethod
    def _ordinary_tiebreak_tile(hand):
        if not hand:
            return None
        return max(hand, key=lambda t: (t.single_rank, t.dots, t.uid))

    def _header_hand_name(self, hand, opposing_hand=None):
        value = evaluate_hand(hand)
        short = self._short_hand_name(value)
        if not opposing_hand:
            return short
        other = evaluate_hand(opposing_hand)
        # Only expose the tie-break tile when it actually explains an equal-point comparison.
        if (value.category == 1 and other.category == 1 and
                value.primary == other.primary and value.primary != 0):
            high_tile = self._ordinary_tiebreak_tile(hand)
            if high_tile is not None:
                return f'{short}·{high_tile.zh_name}'
        return short

    def _update_hand_headers(self):
        dealer_text = '庄家'
        player_text = '玩家'
        dealer_ready = bool(self.dealer_low and self.dealer_high)
        player_ready = bool(self.player_low and self.player_high)

        if dealer_ready:
            dealer_low_other = self.player_low if player_ready else None
            dealer_high_other = self.player_high if player_ready else None
            dealer_text = (
                f"庄家 - {self._header_hand_name(self.dealer_low, dealer_low_other)}"
                f" & {self._header_hand_name(self.dealer_high, dealer_high_other)}"
            )
        if player_ready:
            player_low_other = self.dealer_low if dealer_ready else None
            player_high_other = self.dealer_high if dealer_ready else None
            player_text = (
                f"玩家 - {self._header_hand_name(self.player_low, player_low_other)}"
                f" & {self._header_hand_name(self.player_high, player_high_other)}"
            )
        self.canvas.itemconfigure(self.dealer_header_item, text=dealer_text)
        self.canvas.itemconfigure(self.player_header_item, text=player_text)

    # --------------------------------------------------------- remove orientation captions
    def draw_split_labels(self, owner, low_value=None, high_value=None):
        # V5: no “前道 · 横放 / 后道 · 直放” captions.
        # The owner header already shows the two hand values.
        return

    def draw_selection_guide(self):
        # Keep manual-setting guidance, but remove redundant orientation wording.
        if len(self.selection_order) == 4:
            low, high = self.current_selected_hands()
            lv, hv = evaluate_hand(low), evaluate_hand(high)
            legal = hv.key >= lv.key
            text = f"①② 前道：{lv.name}　｜　③④ 后道：{hv.name}　｜　{'合法' if legal else '无效'}"
            color = GOLD if legal else RED
        else:
            next_no = len(self.selection_order) + 1
            role = '前道' if next_no <= 2 else '后道'
            text = f'当前已选 {len(self.selection_order)}/4；请选择第{next_no}张 → {role}'
            color = '#e8d892'
        self.canvas.create_text(405, self.PLAYER_ZONE[1] + 82, text=text,
                                font=('Arial', 9, 'bold'), fill=color,
                                tags='tile_dynamic')

    # --------------------------------------------------------- elongated Pai Gow shoe
    def wall_geometry(self):
        # 16 vertical columns × 2 rows.  The tiles remain long and narrow even in the shoe.
        w, h = 25, 48
        gap_x, gap_y = 8, 7
        total_w = 16 * w + 15 * gap_x
        x0 = (self.SHOE_ZONE[0] + self.SHOE_ZONE[2] - total_w) / 2
        y0 = self.SHOE_ZONE[1] + 24
        return x0, y0, w, h, gap_x, gap_y

    # --------------------------------------------------------- physical tile rotation
    @staticmethod
    def _rotate_point(px, py, cx, cy, angle_rad):
        dx, dy = px - cx, py - cy
        ca, sa = math.cos(angle_rad), math.sin(angle_rad)
        return cx + dx * ca - dy * sa, cy + dx * sa + dy * ca

    def _draw_rotated_face_tile(self, cx, cy, base_w, base_h, angle_deg, tile,
                                selected=False, selection_role=None, tag='tile',
                                extra_tag='tile_dynamic', compact=False, canvas=None):
        """Draw one physical upright tile rotated as a whole.

        The pip coordinates rotate with the body.  Nothing is re-laid-out merely to
        make the horizontal hand easier to read, so the former top half stays the
        same physical half throughout the setting animation.
        """
        c = canvas or self.canvas
        tags = (tag, extra_tag) if extra_tag else (tag,)
        angle = math.radians(angle_deg)

        outline = GOLD if selected and selection_role == 'front' else (
            '#59a8e5' if selected else '#d8ccb5'
        )
        width = 4 if selected else max(1, int(min(base_w, base_h) / 32))

        def tr(lx, ly):
            # Local coordinates are measured from the centre of an upright tile.
            ca, sa = math.cos(angle), math.sin(angle)
            return cx + lx * ca - ly * sa, cy + lx * sa + ly * ca

        corners = [
            tr(-base_w/2, -base_h/2), tr(base_w/2, -base_h/2),
            tr(base_w/2, base_h/2), tr(-base_w/2, base_h/2),
        ]
        flat = [v for p in corners for v in p]
        c.create_polygon(*flat, fill='#111111', outline=outline, width=width, tags=tags)
        x1, y1 = tr(-base_w/2 + 5, 0)
        x2, y2 = tr(base_w/2 - 5, 0)
        c.create_line(x1, y1, x2, y2, fill='#4d4d4d', width=1, tags=tags)

        pip_positions = {
            1: [(0.5, 0.5)],
            2: [(0.28, 0.28), (0.72, 0.72)],
            3: [(0.28, 0.28), (0.5, 0.5), (0.72, 0.72)],
            4: [(0.28, 0.28), (0.72, 0.28), (0.28, 0.72), (0.72, 0.72)],
            5: [(0.28, 0.25), (0.72, 0.25), (0.5, 0.5), (0.28, 0.75), (0.72, 0.75)],
            6: [(0.28, 0.20), (0.72, 0.20), (0.28, 0.50), (0.72, 0.50),
                (0.28, 0.80), (0.72, 0.80)],
        }
        half_h = base_h / 2
        inset = max(4, min(8, int(min(base_w, base_h) / 6)))
        inner_w = base_w - 2 * inset
        inner_h = half_h - 2 * inset
        radius = max(1.6, min(5.0, min(inner_w, inner_h) / (10 if not compact else 9)))

        def half_pips(number, top_half):
            colour = '#e33b3b' if number in (1, 4) else '#f4f1e8'
            half_cy = -base_h/4 if top_half else base_h/4
            for ux, uy in pip_positions[number]:
                lx = -inner_w/2 + ux * inner_w
                ly = half_cy - inner_h/2 + uy * inner_h
                px, py = tr(lx, ly)
                c.create_oval(px-radius, py-radius, px+radius, py+radius,
                              fill=colour, outline='#222', width=1, tags=tags)

        half_pips(tile.a, True)
        half_pips(tile.b, False)

    def draw_tile(self, x, y, w, h, tile, face_up=True, selected=False, order_no=None,
                  selection_role=None, tag='tile', extra_tag='tile_dynamic', show_name=True,
                  compact=False, canvas=None):
        # A horizontal front tile is a real 90-degree clockwise rotation of the
        # upright tile.  Pip geometry rotates with it instead of being redrawn in
        # a more convenient orientation.
        if face_up and w > h:
            c = canvas or self.canvas
            self._draw_rotated_face_tile(
                x + w/2, y + h/2,
                h, w, 90, tile,
                selected=selected, selection_role=selection_role,
                tag=tag, extra_tag=extra_tag, compact=compact, canvas=c,
            )
            tags = (tag, extra_tag) if extra_tag else (tag,)
            if show_name and not compact and min(w, h) >= 50:
                c.create_text(x + w/2, y + h + 11, text=f'{tile.zh_name}·{tile.dots}',
                              font=('Arial', 7, 'bold'), fill=TEXT, tags=tags)
            if order_no is not None and c is self.canvas:
                badge = '前' if order_no <= 2 else '后'
                badge_color = GOLD if order_no <= 2 else '#59a8e5'
                c.create_rectangle(x + w - 31, y + 3, x + w - 3, y + 21,
                                   fill=badge_color, outline='#2d281d', tags=tags)
                c.create_text(x + w - 17, y + 12,
                              text=f"{badge}{order_no if order_no <= 2 else order_no-2}",
                              font=('Arial', 7, 'bold'), fill='#111', tags=tags)
            return
        return super().draw_tile(
            x, y, w, h, tile, face_up=face_up, selected=selected,
            order_no=order_no, selection_role=selection_role, tag=tag,
            extra_tag=extra_tag, show_name=show_name, compact=compact, canvas=canvas,
        )

    def animate_arrangement(self, owner, low, high, done_callback):
        """Move hands and physically rotate the front tiles 90 degrees clockwise."""
        original = self.player_tiles if owner == 'player' else self.dealer_tiles
        starts_list = self.unsplit_positions(owner)
        start_by_uid = {t.uid: starts_list[i] for i, t in enumerate(original)}
        low_targets, high_targets = self.split_positions(owner)
        low_ids = {t.uid for t in low}

        target = {}
        for tile_obj, rect in zip(low, low_targets):
            x, y, w, h = rect
            target[tile_obj.uid] = (x + w/2, y + h/2, h, w, 90.0)
        for tile_obj, rect in zip(high, high_targets):
            x, y, w, h = rect
            target[tile_obj.uid] = (x + w/2, y + h/2, w, h, 0.0)

        frames = 18
        self.arrangement_anim = {
            'owner': owner,
            'low_ids': low_ids,
            'states': {},
            'low': list(low),
            'high': list(high),
        }

        def frame(step):
            if self._closing:
                return
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            states = {}
            for tile_obj in original:
                sx, sy, sw, sh = start_by_uid[tile_obj.uid]
                scx, scy = sx + sw/2, sy + sh/2
                tcx, tcy, tbw, tbh, target_angle = target[tile_obj.uid]
                states[tile_obj.uid] = (
                    scx + (tcx-scx)*smooth,
                    scy + (tcy-scy)*smooth,
                    sw + (tbw-sw)*smooth,
                    sh + (tbh-sh)*smooth,
                    target_angle * smooth,
                )
            self.arrangement_anim['states'] = states
            self.redraw_tiles()
            if step < frames:
                self.after(34, lambda: frame(step + 1))
                return

            if owner == 'player':
                self.player_low, self.player_high = list(low), list(high)
            else:
                self.dealer_low, self.dealer_high = list(low), list(high)
            self.arrangement_anim = None
            self.redraw_tiles()
            self.after(380, done_callback)

        frame(0)

    def draw_arrangement_frame(self, owner, tiles):
        states = self.arrangement_anim.get('states', {})
        low_ids = self.arrangement_anim.get('low_ids', set())
        for tile_obj in tiles:
            state = states.get(tile_obj.uid)
            if not state:
                continue
            cx, cy, bw, bh, angle = state
            self._draw_rotated_face_tile(
                cx, cy, bw, bh, angle, tile_obj,
                tag=f'{owner}_arr_{tile_obj.uid}', extra_tag='tile_dynamic'
            )
        # No orientation captions during or after movement.

    # --------------------------------------------------------- elongated moving stacks
    def animate_deal_stack(self, stack_no):
        if self._closing:
            return
        if stack_no >= 8:
            self.after(250, self.finish_dealing_animation)
            return

        pos = self.deal_order[stack_no]
        if pos not in (0, self.player_position):
            self.after(35, lambda: self.animate_deal_stack(stack_no + 1))
            return

        dest_x, dest_y = self.deal_destination(pos)
        idxs = list(range(stack_no * 4, stack_no * 4 + 4))
        starts = [self.wall_tile_rect(i) for i in idxs]
        sx = sum(x + w/2 for x, y, w, h in starts) / 4
        sy = sum(y + h/2 for x, y, w, h in starts) / 4
        frames = 14
        self.deal_stack_markers[stack_no] = pos
        self.draw_deal_wall()

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('moving_stack')
            t = step / frames
            smooth = t*t*(3-2*t)
            cx = sx + (dest_x-sx)*smooth
            cy = sy + (dest_y-sy)*smooth
            mini_w = 20
            mini_h = int(mini_w * CLASSIC_TILE_ASPECT)
            offsets = [(-13, -25), (13, -25), (-13, 25), (13, 25)]
            for tile_obj, (ox, oy) in zip(self.stacks[stack_no], offsets):
                self.draw_tile(cx + ox - mini_w/2, cy + oy - mini_h/2,
                               mini_w, mini_h, tile_obj, face_up=False,
                               tag='moving_stack', extra_tag='moving_stack',
                               show_name=False, compact=True)
            if step < frames:
                self.after(34, lambda: frame(step + 1))
                return
            self.canvas.delete('moving_stack')
            if pos == 0:
                self.dealer_dealt_visible = True
            else:
                self.player_dealt_visible = True
            self.redraw_tiles()
            self.after(130, lambda: self.animate_deal_stack(stack_no + 1))
        frame(0)

    # --------------------------------------------------------- exactly-centred settled button
    def render_action_buttons(self):
        for w in self.action_frame.winfo_children():
            w.destroy()

        # The single settled-phase button is centred in the whole Action body.
        # Other phases retain the status text above their button row.
        if self.stage == 'settled':
            self.status_label.pack_forget()
            self.action_frame.pack_forget()
            self.action_frame.pack(fill=tk.BOTH, expand=True, pady=1)
        else:
            self.action_frame.pack_forget()
            if not self.status_label.winfo_manager():
                self.status_label.pack(fill=tk.X, pady=(0, 2))
            self.action_frame.pack(fill=tk.X, pady=1)

        def make_btn(text, command, bg, enabled=True, right_command=None, fg='white'):
            b = tk.Button(self.action_frame, text=text, command=command,
                          font=('Arial', 11, 'bold'), bg=bg, fg=fg,
                          activebackground=bg, relief=tk.RAISED,
                          state=tk.NORMAL if enabled else tk.DISABLED)
            if right_command is not None:
                b.bind('<Button-3>', lambda _e: right_command())
            return b

        if self.stage == 'betting':
            repeat_ok = self.last_ante >= MIN_ANTE and self.last_ante <= min(MAX_ANTE, self.balance)
            start_ok = self.ante >= MIN_ANTE and self.ante <= self.balance and not self.animation_running
            for i in range(2):
                self.action_frame.columnconfigure(i, weight=1)
            make_btn('重复下注', self.repeat_bet, '#FFC107', repeat_ok, fg='black').grid(
                row=0, column=0, sticky='nsew', padx=(0, 3), pady=1)
            make_btn('开始游戏', self.start_round, '#4CAF50', start_ok).grid(
                row=0, column=1, sticky='nsew', padx=(3, 0), pady=1)
        elif self.stage == 'player_set':
            for i in range(2):
                self.action_frame.columnconfigure(i, weight=1)
            make_btn('自动分牌', self.use_house_way, '#4B8BBE').grid(
                row=0, column=0, sticky='nsew', padx=(0, 3), pady=1)
            make_btn('提交分牌', self.submit_player_split, '#4CAF50', len(self.selection_order) == 4).grid(
                row=0, column=1, sticky='nsew', padx=(3, 0), pady=1)
        elif self.stage == 'settled':
            b = make_btn('再来一局', self.new_round, '#FFC107', True,
                         right_command=self.show_full_tile_order, fg='black')
            # place() centres the single control in both axes of the fixed action frame.
            b.place(relx=0.5, rely=0.5, anchor='center', width=160, height=34)
        else:
            tk.Label(self.action_frame, text='动画进行中，请稍候…', font=('Arial', 10, 'bold'),
                     bg=self.PANEL_BG, fg='#6B6251').pack(expand=True)

    def update_display(self):
        # Reuse V4's Poker-style side panel, then enforce the V5 table cleanup.
        super().update_display()
        try:
            self.canvas.itemconfigure(self.result_item, state='hidden')
        except tk.TclError:
            pass



# ============================================================
# V6 — persistent Pai Gow shoe, two-card manual front selection
# ============================================================
class ClassicPaiGowGUIV6(ClassicPaiGowGUIV5):
    """V6 refinements requested for the casino-style table.

    - The shoe has more height and always uses elongated Pai Gow tiles.
    - After a settled round, the eight live dealer/player tiles return to arbitrary
      locations in the old shoe; that shoe slides right while a fresh shoe slides
      in from the left.
    - Manual setting only requires choosing the two LOW/front tiles.  The other
      two automatically become the HIGH/back hand.
    - Per-hand result areas use pure green/red; exact Copy uses pure white.
    """

    # More vertical room for the shoe while preserving enough space for both hands.
    DEALER_ZONE = (24, 132, 786, 310)
    SHOE_ZONE = (24, 320, 786, 500)
    PLAYER_ZONE = (24, 510, 786, 728)

    HAND_WIN_BG = '#00ff00'
    HAND_LOSE_BG = '#ff0000'
    HAND_NEUTRAL_BG = '#173f3a'
    HAND_COPY_BG = '#ffffff'

    def create_static_ui(self):
        super().create_static_ui()
        # "操作"下面的信息与牌九扑克一样保留，但字号更大、更容易读。
        try:
            self.current_bet_label.config(font=('Arial', 13, 'bold'))
            self.last_win_label.config(font=('Arial', 13, 'bold'))
        except (AttributeError, tk.TclError):
            pass

    # --------------------------------------------------------- right-panel result text size
    def update_display(self):
        super().update_display()
        if self.stage == 'shoe_exchange':
            try:
                self.stage_label.config(text='换牌靴')
                self.status_label.config(text='旧牌九归靴，新牌九牌靴正在进入…')
            except (AttributeError, tk.TclError):
                pass

    # --------------------------------------------------------- manual setting: choose LOW only
    def finish_player_reveal(self):
        self.stage = 'player_set'
        self.selection_order = []
        self.status = '请选择2张作为前道；剩余2张会自动成为后道。也可以直接使用【自动分牌】。'
        self.update_display()

    def player_tile_click(self, index):
        if self.stage != 'player_set' or index >= len(self.player_tiles):
            return
        if index in self.selection_order:
            self.selection_order.remove(index)
        elif len(self.selection_order) < 2:
            self.selection_order.append(index)
        self._update_setting_status()
        self.update_display()

    def _update_setting_status(self):
        if len(self.selection_order) < 2:
            self.status = '请选择2张牌作为前道；其余2张自动作为后道。'
            return
        low, high = self.current_selected_hands()
        lv, hv = evaluate_hand(low), evaluate_hand(high)
        legal = hv.key >= lv.key
        if legal:
            self.status = f'前道：{lv.name}｜后道：{hv.name}。摆法合法，可以提交。'
        else:
            self.status = f'前道：{lv.name}｜后道：{hv.name}。后道较小，请重新选择或使用自动分牌。'

    def current_selected_hands(self):
        if len(self.selection_order) != 2:
            return [], []
        selected = set(self.selection_order)
        low = [self.player_tiles[i] for i in self.selection_order]
        high = [tile for i, tile in enumerate(self.player_tiles) if i not in selected]
        return low, high

    def use_house_way(self):
        if self.stage != 'player_set' or len(self.player_tiles) != 4:
            return
        choice = traditional_house_way(self.player_tiles)
        low = self._ordered_pair(choice.low)
        uid_to_idx = {tile.uid: i for i, tile in enumerate(self.player_tiles)}
        self.selection_order = [uid_to_idx[tile.uid] for tile in low]
        self.status = (
            f'自动分牌：前道 {choice.low_value.name}｜后道 {choice.high_value.name}。'
            '如无修改可直接提交。'
        )
        self.update_display()

    def submit_player_split(self):
        if self.stage != 'player_set':
            return
        if len(self.selection_order) != 2:
            self.status = '请先选择2张牌作为前道。剩余2张会自动成为后道。'
            self.update_display()
            return

        low, high = self.current_selected_hands()
        lv, hv = evaluate_hand(low), evaluate_hand(high)
        if hv.key < lv.key:
            self.status = (
                f'不能提交：前道【{lv.name}】比后道【{hv.name}】大。'
                '请重新选择2张前道，或使用【自动分牌】。'
            )
            self.update_display()
            return

        self.stage = 'player_arranging'
        self.status = '正在摆放玩家前道与后道…'
        self.update_display()
        self.animate_arrangement(
            'player', self._ordered_pair(low), self._ordered_pair(high), self.begin_dealer_reveal
        )

    def draw_selection_guide(self):
        # V6 removes the "当前已选 0/4" line completely.
        # Selection is shown only by the gold outline/badge on the two chosen LOW tiles.
        return

    # --------------------------------------------------------- elongated / taller Pai Gow shoe
    def wall_geometry(self):
        # 16 columns × 2 rows, visibly elongated even at shoe scale.
        w, h = 25, 58
        gap_x, gap_y = 8, 9
        total_w = 16 * w + 15 * gap_x
        x0 = (self.SHOE_ZONE[0] + self.SHOE_ZONE[2] - total_w) / 2
        y0 = self.SHOE_ZONE[1] + 35
        return x0, y0, w, h, gap_x, gap_y

    def draw_deal_wall(self):
        self.canvas.delete('deal_wall')
        if not self.deal_wall_visible or not self.full_tiles:
            return
        sx0, sy0, sx1, sy1 = self.SHOE_ZONE
        self.canvas.create_rectangle(
            sx0, sy0, sx1, sy1,
            fill='#0a3834', outline='#557b70', width=1, tags='deal_wall'
        )
        self.canvas.create_text(
            sx0 + 14, sy0 + 18, anchor='w', text='牌九牌靴',
            font=('Arial', 12, 'bold'), fill='#d9efe8', tags='deal_wall'
        )
        self.canvas.create_text(
            sx1 - 14, sy0 + 18, anchor='e', text='32张牌九 · 16栋',
            font=('Arial', 9, 'bold'), fill=MUTED, tags='deal_wall'
        )

        for idx, tile_obj in enumerate(self.full_tiles):
            stack_no = idx // 4
            if stack_no in self.deal_stack_markers:
                continue
            x, y, w, h = self.wall_tile_rect(idx)
            self.draw_tile(
                x, y, w, h, tile_obj, face_up=False,
                tag=f'wall_{idx}', extra_tag='deal_wall',
                show_name=False, compact=True,
            )

        x0, y0, w, h, gap_x, gap_y = self.wall_geometry()
        for stack_no in range(8):
            first_col = stack_no * 2
            xa = x0 + first_col * (w + gap_x) - 3
            xb = x0 + (first_col + 1) * (w + gap_x) + w + 3
            self.canvas.create_rectangle(
                xa, y0 - 3, xb, y0 + 2 * h + gap_y + 3,
                outline='#6f8f85', width=1, tags='deal_wall'
            )

    # --------------------------------------------------------- exact Copy colouring
    def draw_split_hand(self, low, high, owner):
        low_pos, high_pos = self.split_positions(owner)
        lv, hv = evaluate_hand(low), evaluate_hand(high)

        def hand_bg(role, rects):
            state = self.hand_outcomes.get((owner, role))
            if state == 'win':
                fill = self.HAND_WIN_BG
            elif state == 'lose':
                fill = self.HAND_LOSE_BG
            elif state == 'tie':
                fill = self.HAND_COPY_BG
            else:
                fill = self.HAND_NEUTRAL_BG
            min_x = min(r[0] for r in rects) - 18
            min_y = min(r[1] for r in rects) - 9
            max_x = max(r[0] + r[2] for r in rects) + 18
            max_y = max(r[1] + r[3] for r in rects) + 9
            self.canvas.create_rectangle(
                min_x, min_y, max_x, max_y,
                fill=fill, outline='#7d9187', width=1, tags='tile_dynamic'
            )

        hand_bg('low', low_pos)
        hand_bg('high', high_pos)
        self.draw_split_labels(owner, lv, hv)

        for tile_obj, rect in zip(low, low_pos):
            x, y, w, h = rect
            self.draw_tile(
                x, y, w, h, tile_obj, face_up=True,
                tag=f'{owner}_low_{tile_obj.uid}', extra_tag='tile_dynamic'
            )
        for tile_obj, rect in zip(high, high_pos):
            x, y, w, h = rect
            self.draw_tile(
                x, y, w, h, tile_obj, face_up=True,
                tag=f'{owner}_high_{tile_obj.uid}', extra_tag='tile_dynamic'
            )

    # --------------------------------------------------------- action buttons
    def render_action_buttons(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        if self.stage == 'settled':
            self.status_label.pack_forget()
            self.action_frame.pack_forget()
            self.action_frame.pack(fill=tk.BOTH, expand=True, pady=1)
        else:
            self.action_frame.pack_forget()
            if not self.status_label.winfo_manager():
                self.status_label.pack(fill=tk.X, pady=(0, 2))
            self.action_frame.pack(fill=tk.X, pady=1)

        def make_btn(text, command, bg, enabled=True, right_command=None, fg='white'):
            button = tk.Button(
                self.action_frame, text=text, command=command,
                font=('Arial', 11, 'bold'), bg=bg, fg=fg,
                activebackground=bg, relief=tk.RAISED,
                state=tk.NORMAL if enabled else tk.DISABLED,
            )
            if right_command is not None:
                button.bind('<Button-3>', lambda _event: right_command())
            return button

        if self.stage == 'betting':
            repeat_ok = self.last_ante >= MIN_ANTE and self.last_ante <= min(MAX_ANTE, self.balance)
            start_ok = self.ante >= MIN_ANTE and self.ante <= self.balance and not self.animation_running
            for i in range(2):
                self.action_frame.columnconfigure(i, weight=1)
            make_btn('重复下注', self.repeat_bet, '#FFC107', repeat_ok, fg='black').grid(
                row=0, column=0, sticky='nsew', padx=(0, 3), pady=1
            )
            make_btn('开始游戏', self.start_round, '#4CAF50', start_ok).grid(
                row=0, column=1, sticky='nsew', padx=(3, 0), pady=1
            )
        elif self.stage == 'player_set':
            for i in range(2):
                self.action_frame.columnconfigure(i, weight=1)
            make_btn('自动分牌', self.use_house_way, '#4B8BBE').grid(
                row=0, column=0, sticky='nsew', padx=(0, 3), pady=1
            )
            make_btn(
                '提交分牌', self.submit_player_split, '#4CAF50',
                len(self.selection_order) == 2,
            ).grid(row=0, column=1, sticky='nsew', padx=(3, 0), pady=1)
        elif self.stage == 'settled':
            button = make_btn(
                '再来一局', self.new_round, '#FFC107', True,
                right_command=self.show_full_tile_order, fg='black',
            )
            button.place(relx=0.5, rely=0.5, anchor='center', width=160, height=34)
        else:
            tk.Label(
                self.action_frame, text='动画进行中，请稍候…',
                font=('Arial', 10, 'bold'), bg=self.PANEL_BG, fg='#6B6251'
            ).pack(expand=True)

    # --------------------------------------------------------- retain a prepared shoe on Start
    def start_round(self):
        if self.stage != 'betting' or self.animation_running:
            return
        if self.ante < MIN_ANTE:
            messagebox.showerror('底注不足', f'底注至少需要 ${MIN_ANTE}', parent=self.winfo_toplevel())
            return
        if self.ante > self.balance:
            messagebox.showerror('余额不足', '余额不足以支付本局底注', parent=self.winfo_toplevel())
            return

        self.last_ante = int(self.ante)
        self.balance -= self.ante
        self._persist_balance()
        self.stage = 'rolling'
        self.status = '正在摇骰；牌九牌靴已准备。'
        self.last_result = ''
        self.last_return = 0.0
        self.ante_display_amount = None
        self.ante_display_bg = 'white'
        self.hand_outcomes = {}
        self.selection_order = []
        self.player_tiles = []
        self.dealer_tiles = []
        self.player_low = []
        self.player_high = []
        self.dealer_low = []
        self.dealer_high = []
        self.player_face_up = [False] * 4
        self.dealer_face_up = [False] * 4
        self.dealer_dealt_visible = False
        self.player_dealt_visible = False
        self.deal_stack_markers = {}
        self.arrangement_anim = None
        self.flip_anim = None

        # First-ever round creates a shoe here.  After "再来一局", the new shoe is
        # already sitting on the table, so Start Game uses that exact prepared shoe.
        if not self.full_tiles or len(self.full_tiles) != 32 or not self.deal_wall_visible:
            self.full_tiles = self.secure_shuffle(build_pai_gow_set())
        self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
        self.deal_wall_visible = True
        self.shoe_ready_for_next_round = False
        self.update_display()
        self.roll_dice()

    # --------------------------------------------------------- persistent shoe exchange
    def _snapshot_wall_rect(self, tile_index, offset_x=0.0):
        x0, y0, w, h, gap_x, gap_y = self.wall_geometry()
        col = tile_index // 2
        row = tile_index % 2
        return x0 + col * (w + gap_x) + offset_x, y0 + row * (h + gap_y), w, h

    def _draw_shoe_snapshot(self, tiles, offset_x=0.0, tag='shoe_snapshot', hide_uids=None):
        hide_uids = set(hide_uids or ())
        sx0, sy0, sx1, sy1 = self.SHOE_ZONE
        self.canvas.create_rectangle(
            sx0 + offset_x, sy0, sx1 + offset_x, sy1,
            fill='#0a3834', outline='#557b70', width=1, tags=tag
        )
        self.canvas.create_text(
            sx0 + 14 + offset_x, sy0 + 18, anchor='w', text='牌九牌靴',
            font=('Arial', 12, 'bold'), fill='#d9efe8', tags=tag
        )
        self.canvas.create_text(
            sx1 - 14 + offset_x, sy0 + 18, anchor='e', text='32张牌九 · 16栋',
            font=('Arial', 9, 'bold'), fill=MUTED, tags=tag
        )
        for idx, tile_obj in enumerate(tiles):
            if tile_obj.uid in hide_uids:
                continue
            x, y, w, h = self._snapshot_wall_rect(idx, offset_x)
            self.draw_tile(
                x, y, w, h, tile_obj, face_up=False,
                tag=f'{tag}_{idx}', extra_tag=tag,
                show_name=False, compact=True,
            )

        x0, y0, w, h, gap_x, gap_y = self.wall_geometry()
        x0 += offset_x
        for stack_no in range(8):
            first_col = stack_no * 2
            xa = x0 + first_col * (w + gap_x) - 3
            xb = x0 + (first_col + 1) * (w + gap_x) + w + 3
            self.canvas.create_rectangle(
                xa, y0 - 3, xb, y0 + 2 * h + gap_y + 3,
                outline='#6f8f85', width=1, tags=tag
            )

    def _returning_start_states(self):
        states = {}
        for owner, low, high in (
            ('dealer', self.dealer_low, self.dealer_high),
            ('player', self.player_low, self.player_high),
        ):
            low_rects, high_rects = self.split_positions(owner)
            for tile_obj, rect in zip(low, low_rects):
                x, y, w, h = rect
                states[tile_obj.uid] = (x + w/2, y + h/2, h, w, 90.0, tile_obj)
            for tile_obj, rect in zip(high, high_rects):
                x, y, w, h = rect
                states[tile_obj.uid] = (x + w/2, y + h/2, w, h, 0.0, tile_obj)
        return states

    def new_round(self):
        if self.stage != 'settled' or self.animation_running:
            return

        # If a malformed state somehow reaches settlement, fall back to a clean shoe.
        if len(self.full_tiles) != 32 or not (self.player_low and self.player_high and self.dealer_low and self.dealer_high):
            self._finish_new_shoe_immediately()
            return

        self.stage = 'shoe_exchange'
        self.animation_running = True
        self.status = '当前玩家与庄家牌九正在归还牌靴…'
        try:
            self.stage_label.config(text='换牌靴')
            self.status_label.pack(fill=tk.X, pady=(0, 2))
            self.status_label.config(text='当前牌九归靴…')
        except (AttributeError, tk.TclError):
            pass
        self.render_action_buttons()

        # Reassemble the old shoe in an arbitrary order.  This gives the eight
        # returned tiles arbitrary physical destinations instead of forcing them
        # back into their original gaps.
        old_reassembled = self.secure_shuffle(list(self.full_tiles))
        start_states = self._returning_start_states()
        return_uids = set(start_states)
        target_index = {tile.uid: idx for idx, tile in enumerate(old_reassembled)}

        self.canvas.delete('tile_dynamic')
        self.canvas.delete('deal_wall')
        self.canvas.itemconfigure(self.dealer_header_item, text='庄家')
        self.canvas.itemconfigure(self.player_header_item, text='玩家')
        self._draw_shoe_snapshot(
            old_reassembled, tag='shoe_return_base', hide_uids=return_uids
        )

        frames = 20

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('returning_tiles')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            for uid, (scx, scy, sbw, sbh, sangle, tile_obj) in start_states.items():
                idx = target_index[uid]
                tx, ty, tw, th = self._snapshot_wall_rect(idx)
                tcx, tcy = tx + tw/2, ty + th/2
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
                self.after(34, lambda: frame(step + 1))
                return

            self.canvas.delete('returning_tiles')
            self.canvas.delete('shoe_return_base')
            self.full_tiles = old_reassembled
            self.deal_stack_markers = {}
            self._animate_shoe_swap(old_reassembled)

        frame(0)

    def _animate_shoe_swap(self, old_tiles):
        new_tiles = self.secure_shuffle(build_pai_gow_set())
        frames = 22
        travel = (self.SHOE_ZONE[2] - self.SHOE_ZONE[0]) + 55

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            old_offset = travel * smooth
            new_offset = -travel * (1 - smooth)
            self._draw_shoe_snapshot(old_tiles, old_offset, 'shoe_swap_old')
            self._draw_shoe_snapshot(new_tiles, new_offset, 'shoe_swap_new')
            if step < frames:
                self.after(30, lambda: frame(step + 1))
                return

            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            self.full_tiles = list(new_tiles)
            self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
            self.deal_wall_visible = True
            self.shoe_ready_for_next_round = True
            self._reset_after_shoe_exchange()

        frame(0)

    def _finish_new_shoe_immediately(self):
        self.full_tiles = self.secure_shuffle(build_pai_gow_set())
        self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
        self.deal_wall_visible = True
        self.shoe_ready_for_next_round = True
        self._reset_after_shoe_exchange()

    def _reset_after_shoe_exchange(self):
        self.animation_running = False
        self.stage = 'betting'
        self.ante = 0
        self.status = f'新牌九牌靴已就位。玩家位置：{self.player_position}号位。'
        self.last_result = ''
        self.last_return = 0.0
        self.ante_display_amount = None
        self.ante_display_bg = '#f5f0df'
        self.hand_outcomes = {}
        self.player_tiles = []
        self.dealer_tiles = []
        self.player_low = []
        self.player_high = []
        self.dealer_low = []
        self.dealer_high = []
        self.selection_order = []
        self.dice_result = []
        self.deal_start_index = None
        self.deal_order = []
        self.position_hands = {}
        self.player_face_up = [False] * 4
        self.dealer_face_up = [False] * 4
        self.dealer_dealt_visible = False
        self.player_dealt_visible = False
        self.deal_stack_markers = {}
        self.arrangement_anim = None
        self.flip_anim = None
        self.canvas.delete('tile_dynamic')
        self.canvas.delete('moving_stack')
        for item in self.animation_dice_items:
            self.canvas.itemconfigure(item, image=self.dice_images_animation[5])
        self.canvas.itemconfigure(self.dealer_header_item, text='庄家')
        self.canvas.itemconfigure(self.player_header_item, text='玩家')
        self.update_display()




# ============================================================
# V7 — original-slot shoe return + wider Poker-style panel
# ============================================================
class ClassicPaiGowGUIV7(ClassicPaiGowGUIV6):
    """V7 presentation and shoe-flow refinements.

    - Dealer and player zones have exactly the same height.
    - The Pai Gow shoe has a taller permanent area and every compact back says 牌九.
    - The first shoe slides LEFT into the table on initial load.
    - At New Round, the eight live tiles return to their ORIGINAL 32-tile slots;
      the old shoe then slides right while a fresh shoe simultaneously slides left in.
    - No small tile-name captions or front/back orientation captions are drawn.
    - During manual setting, the chosen LOW tiles are identified only by a light-blue border.
    - The right control panel is 400px wide with proportionally larger typography.
    """

    TABLE_X0, TABLE_X1 = 10, 740
    RIGHT_X0, RIGHT_X1 = 750, 1150

    # Equal dealer/player heights; a taller shoe occupies the centre.
    DEALER_ZONE = (24, 128, 726, 306)   # 178 px
    SHOE_ZONE   = (24, 316, 726, 506)   # 190 px
    PLAYER_ZONE = (24, 516, 726, 694)   # 178 px

    SELECT_BORDER = '#87CEFA'  # light blue

    def __init__(self, parent, balance=10000, user='Guest', on_back=None, on_balance_change=None):
        super().__init__(
            parent, balance=balance, user=user,
            on_back=on_back, on_balance_change=on_balance_change,
        )
        # The very first shoe is prepared immediately and enters from the right,
        # travelling left into its permanent centre-table position.
        self.animation_running = True
        self.shoe_ready_for_next_round = False
        self.status = '新牌九牌靴正在进入…'
        self.update_display()
        self.after(90, self._animate_initial_shoe_left)

    # --------------------------------------------------------- static layout
    def create_static_ui(self):
        c = self.canvas
        c.create_rectangle(0, 0, 1150, 750, fill=BG, outline='', tags='static')

        # Left table leaves exactly 400 px for the Poker-style control panel.
        c.create_rectangle(10, 8, 740, 740, fill=FELT, outline=GOLD_DARK, width=3, tags='static')
        c.create_text(
            375, 27, text='经典牌九',
            font=('Arial', 19, 'bold'), fill=GOLD, tags='static'
        )

        # Compact dice strip: only dice + total + ordinal, as requested.
        c.create_rectangle(24, 48, 726, 118, fill='#123c38', outline='#6e9185', width=1, tags='static')
        c.create_text(38, 83, anchor='w', text='三骰', font=('Arial', 11, 'bold'),
                      fill='#d9efe8', tags='static')
        self.animation_dice_base_positions = [(126, 83), (198, 83), (270, 83)]
        self.animation_dice_items = [
            c.create_image(x, y, image=self.dice_images_animation[5], tags=('dice', 'static'))
            for x, y in self.animation_dice_base_positions
        ]
        c.create_text(162, 83, text='+', font=('Arial', 17, 'bold'), fill=TEXT, tags='static')
        c.create_text(234, 83, text='+', font=('Arial', 17, 'bold'), fill=TEXT, tags='static')
        self.dice_summary_item = c.create_text(
            310, 83, anchor='w', text='= --点　｜　第--个派牌',
            font=('Arial', 13, 'bold'), fill=TEXT, tags='static'
        )

        self.draw_hand_zone(*self.DEALER_ZONE, '庄家', dealer=True)
        self.draw_hand_zone(*self.PLAYER_ZONE, '玩家', dealer=False)

        # Kept for compatibility with inherited display code, but intentionally hidden.
        self.result_item = c.create_text(
            375, 718, text='', width=690,
            font=('Arial', 11, 'bold'), fill=GOLD, state='hidden', tags='static'
        )

        self.create_right_panel_widgets()

    # --------------------------------------------------------- 400px Poker-style panel
    def create_right_panel_widgets(self):
        panel = tk.Frame(self, bg=self.ROOT_BG, width=400, height=734)
        panel.place(x=750, y=8, width=400, height=734)
        panel.pack_propagate(False)
        self.right_panel = panel

        def card(title, title_size=14):
            outer = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
            outer.pack(fill=tk.X, pady=3, padx=(0, 1))
            header = tk.Frame(outer, bg=self.HEADER_BG)
            header.pack(fill=tk.X)
            tk.Label(
                header, text=title, font=('Arial', title_size, 'bold'),
                bg=self.HEADER_BG, fg=self.TITLE_FG
            ).pack(pady=4)
            return outer

        # 1. Table information
        info_card = card('经典牌九')
        body = tk.Frame(info_card, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=12, pady=7)
        self.balance_label = tk.Label(
            body, text='余额: $0.00', font=('Arial', 16, 'bold'),
            bg=self.PANEL_BG, fg='black'
        )
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(
            body, text='下注阶段', font=('Arial', 15, 'bold'),
            bg=self.PANEL_BG, fg='#A88100'
        )
        self.stage_label.pack(side=tk.RIGHT)

        # 2. Limits
        limit_card = card('下注上限', 13)
        body = tk.Frame(limit_card, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=10, pady=6)
        table = tk.Frame(body, bg=self.PANEL_BG)
        table.pack(fill=tk.X)
        for col, title in enumerate(('底注最低', '底注最高')):
            tk.Label(
                table, text=title, font=('Arial', 11, 'bold'), bg=self.PANEL_BG,
                relief=tk.SOLID, borderwidth=1, pady=3
            ).grid(row=0, column=col, sticky='nsew')
        for col, value in enumerate(('$10', '$25,000')):
            tk.Label(
                table, text=value, font=('Arial', 13, 'bold'), bg=self.PANEL_BG,
                fg='#A88100', relief=tk.SOLID, borderwidth=1, pady=3
            ).grid(row=1, column=col, sticky='nsew')
            table.columnconfigure(col, weight=1)

        # 3. Chips + ante
        bet_card = card('筹码与下注', 13)
        body = tk.Frame(bet_card, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=9, pady=6)
        chip_row = tk.Frame(body, bg=self.PANEL_BG)
        chip_row.pack(fill=tk.X, pady=(0, 7))
        for i in range(6):
            chip_row.columnconfigure(i, weight=1)
        self.chip_canvases = {}
        display_labels = {10:'$10', 25:'$25', 100:'$100', 500:'$500', 1000:'$1K', 2500:'$2.5K'}
        for col, (value, color, _old_label) in enumerate(CHIPS):
            cell = tk.Frame(chip_row, bg=self.PANEL_BG)
            cell.grid(row=0, column=col, sticky='nsew', padx=2)
            cv = tk.Canvas(cell, width=50, height=50, bg=self.PANEL_BG, highlightthickness=0)
            cv.pack(anchor='center')
            oval = cv.create_oval(2, 2, 48, 48, fill=color, outline='black', width=1)
            fg = 'white' if value in (100, 2500) else 'black'
            cv.create_text(25, 25, text=display_labels[value], fill=fg,
                           font=('Arial', 10, 'bold'))
            cv.bind('<Button-1>', lambda _e, v=value: self.select_chip(v))
            cv.bind('<Enter>', lambda _e, w=cv: self._bet_cursor(w))
            cv.bind('<Leave>', lambda _e, w=cv: w.config(cursor=''))
            self.chip_canvases[value] = (cv, oval)

        ante_row = tk.Frame(body, bg=self.PANEL_BG)
        ante_row.pack(fill=tk.X, pady=(2, 1))
        inner = tk.Frame(ante_row, bg=self.PANEL_BG)
        inner.pack(anchor='center')
        tk.Label(inner, text='底注:', font=('Arial', 17, 'bold'), bg=self.PANEL_BG).pack(side=tk.LEFT)
        self.ante_var = tk.StringVar(value='0')
        self.ante_display = tk.Label(
            inner, textvariable=self.ante_var, font=('Arial', 17, 'bold'),
            bg='white', fg='black', width=13, relief=tk.SUNKEN, anchor='center'
        )
        self.ante_display.pack(side=tk.LEFT, padx=(8, 0))
        self.ante_display.bind('<Button-1>', lambda _e: self.add_ante())
        self.ante_display.bind('<Button-3>', lambda _e: self.clear_ante())
        self.ante_display.bind('<Enter>', lambda _e: self._bet_cursor(self.ante_display))
        self.ante_display.bind('<Leave>', lambda _e: self.ante_display.config(cursor=''))
        tk.Label(
            body, text='净赢赔率 0.95 : 1', font=('Arial', 10, 'bold'),
            bg=self.PANEL_BG, fg='#6B6251'
        ).pack(pady=(2, 0))

        # 4. Player seat
        seat_card = card('玩家位置', 13)
        body = tk.Frame(seat_card, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=10, pady=7)
        tk.Label(
            body, text='选择 1–6 任意位置', font=('Arial', 11, 'bold'),
            bg=self.PANEL_BG, fg=self.TITLE_FG
        ).pack(anchor='w', pady=(0, 5))
        row = tk.Frame(body, bg=self.PANEL_BG)
        row.pack(fill=tk.X)
        self.position_buttons = {}
        for i in range(6):
            row.columnconfigure(i, weight=1)
        for seat in range(1, 7):
            b = tk.Button(
                row, text=str(seat), font=('Arial', 12, 'bold'),
                command=lambda s=seat: self.select_player_position(s),
                relief=tk.RAISED, bd=1
            )
            b.grid(row=0, column=seat-1, padx=3, sticky='ew', ipady=2)
            self.position_buttons[seat] = b

        # 5. Action — fixed height, larger readable contents.
        action_card = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID, height=150)
        action_card.pack(fill=tk.X, pady=3, padx=(0, 1))
        action_card.pack_propagate(False)
        header = tk.Frame(action_card, bg=self.HEADER_BG, height=30)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text='操作', font=('Arial', 14, 'bold'),
            bg=self.HEADER_BG, fg=self.TITLE_FG
        ).pack(expand=True)
        body = tk.Frame(action_card, bg=self.PANEL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=9, pady=5)
        self.status_label = tk.Label(
            body, text='设置下注金额并开始游戏', font=('Arial', 12, 'bold'),
            bg=self.PANEL_BG, fg=self.TITLE_FG,
            wraplength=365, justify=tk.CENTER, height=3
        )
        self.status_label.pack(fill=tk.X, pady=(0, 2))
        self.action_frame = tk.Frame(body, bg=self.PANEL_BG, height=48)
        self.action_frame.pack(fill=tk.X, pady=1)
        self.action_frame.pack_propagate(False)

        # 6. Content below Action is deliberately larger.
        bottom = tk.Frame(panel, bg=self.PANEL_BG, bd=1, relief=tk.SOLID)
        bottom.pack(fill=tk.X, pady=3, padx=(0, 1))
        body = tk.Frame(bottom, bg=self.PANEL_BG)
        body.pack(fill=tk.X, padx=11, pady=7)
        self.current_bet_label = tk.Label(
            body, text='本局下注: $0.00', font=('Arial', 14, 'bold'),
            bg=self.PANEL_BG, fg='black'
        )
        self.current_bet_label.pack(anchor='w')
        row = tk.Frame(body, bg=self.PANEL_BG)
        row.pack(fill=tk.X, pady=(3, 0))
        self.last_win_label = tk.Label(
            row, text='上局获胜: $0.00', font=('Arial', 14, 'bold'),
            bg=self.PANEL_BG, fg='black'
        )
        self.last_win_label.pack(side=tk.LEFT)
        tk.Button(
            row, text='ℹ️', command=self.show_detailed_rules,
            bg='#4B8BBE', fg='white', font=('Arial', 11, 'bold'),
            width=3, relief=tk.FLAT
        ).pack(side=tk.RIGHT)

    # --------------------------------------------------------- positions for narrower left table
    def unsplit_positions(self, owner):
        _, y0, _, y1 = self.DEALER_ZONE if owner == 'dealer' else self.PLAYER_ZONE
        center_y = (y0 + y1) / 2 + 8
        total_w = 4 * self.UNSPLIT_W + 3 * 16
        center_x = (self.DEALER_ZONE[0] + self.DEALER_ZONE[2]) / 2
        start_x = center_x - total_w / 2
        return [
            (start_x + i * (self.UNSPLIT_W + 16), center_y - self.UNSPLIT_H / 2,
             self.UNSPLIT_W, self.UNSPLIT_H)
            for i in range(4)
        ]

    def split_positions(self, owner):
        _, y0, _, y1 = self.DEALER_ZONE if owner == 'dealer' else self.PLAYER_ZONE
        cy = (y0 + y1) / 2 + 9

        low_gap = 7
        low_total_h = self.LOW_H * 2 + low_gap
        low_x = 132
        low_top = cy - low_total_h / 2
        low = [
            (low_x, low_top, self.LOW_W, self.LOW_H),
            (low_x, low_top + self.LOW_H + low_gap, self.LOW_W, self.LOW_H),
        ]

        high_gap = 18
        high_x = 487
        high = [
            (high_x, cy - self.HIGH_H / 2, self.HIGH_W, self.HIGH_H),
            (high_x + self.HIGH_W + high_gap, cy - self.HIGH_H / 2, self.HIGH_W, self.HIGH_H),
        ]
        return low, high

    # --------------------------------------------------------- no tile-name / orientation captions
    def draw_split_labels(self, owner, low_value=None, high_value=None):
        return

    def draw_tile(self, x, y, w, h, tile, face_up=True, selected=False, order_no=None,
                  selection_role=None, tag='tile', extra_tag='tile_dynamic', show_name=True,
                  compact=False, canvas=None):
        # Selected LOW tiles are indicated ONLY by a light-blue outline.
        c = canvas or self.canvas
        result = super().draw_tile(
            x, y, w, h, tile,
            face_up=face_up,
            selected=selected,
            order_no=None,                         # no 前1/前2 badges
            selection_role='back' if selected else selection_role,  # V5's blue branch
            tag=tag,
            extra_tag=extra_tag,
            show_name=False,                       # removes 天牌·12 etc.
            compact=compact,
            canvas=c,
        )
        # Compact backs in the permanent shoe explicitly carry the two characters 牌九.
        if not face_up and compact:
            tags = (tag, extra_tag) if extra_tag else (tag,)
            font_size = max(5, min(7, int(min(w, h) * 0.24)))
            c.create_text(
                x + w/2, y + h/2, text='牌\n九', justify='center',
                font=('Arial', font_size, 'bold'), fill=GOLD_DARK, tags=tags
            )
        return result

    def draw_split_hand(self, low, high, owner):
        low_pos, high_pos = self.split_positions(owner)

        def hand_bg(role, rects):
            state = self.hand_outcomes.get((owner, role))
            if state == 'win':
                fill = self.HAND_WIN_BG
            elif state == 'lose':
                fill = self.HAND_LOSE_BG
            elif state == 'tie':
                fill = self.HAND_COPY_BG
            else:
                fill = self.HAND_NEUTRAL_BG
            min_x = min(r[0] for r in rects) - 18
            min_y = min(r[1] for r in rects) - 9
            max_x = max(r[0] + r[2] for r in rects) + 18
            max_y = max(r[1] + r[3] for r in rects) + 9
            self.canvas.create_rectangle(
                min_x, min_y, max_x, max_y,
                fill=fill, outline='#7d9187', width=1, tags='tile_dynamic'
            )

        hand_bg('low', low_pos)
        hand_bg('high', high_pos)

        # LOW/front remains visibly selected only by the requested light-blue border.
        for tile_obj, rect in zip(low, low_pos):
            x, y, w, h = rect
            self.draw_tile(
                x, y, w, h, tile_obj, face_up=True,
                selected=True, selection_role='back',
                tag=f'{owner}_low_{tile_obj.uid}', extra_tag='tile_dynamic'
            )
        for tile_obj, rect in zip(high, high_pos):
            x, y, w, h = rect
            self.draw_tile(
                x, y, w, h, tile_obj, face_up=True,
                selected=False,
                tag=f'{owner}_high_{tile_obj.uid}', extra_tag='tile_dynamic'
            )

    # --------------------------------------------------------- simpler setting messages
    def _update_setting_status(self):
        if len(self.selection_order) < 2:
            self.status = '请选择2张牌作为前道；浅蓝色边框表示已选择。'
            return
        low, high = self.current_selected_hands()
        legal = evaluate_hand(high).key >= evaluate_hand(low).key
        self.status = '已选择2张前道，可以提交分牌。' if legal else '此摆法后道较小，请重新选择或使用自动分牌。'

    def use_house_way(self):
        if self.stage != 'player_set' or len(self.player_tiles) != 4:
            return
        choice = traditional_house_way(self.player_tiles)
        low = self._ordered_pair(choice.low)
        uid_to_idx = {tile.uid: i for i, tile in enumerate(self.player_tiles)}
        self.selection_order = [uid_to_idx[tile.uid] for tile in low]
        self.status = '自动分牌完成；浅蓝色边框的2张牌为前道，可直接提交。'
        self.update_display()

    # --------------------------------------------------------- taller shoe geometry
    def wall_geometry(self):
        w = 24
        h = int(w * CLASSIC_TILE_ASPECT)
        gap_x, gap_y = 7, 10
        total_w = 16 * w + 15 * gap_x
        x0 = (self.SHOE_ZONE[0] + self.SHOE_ZONE[2] - total_w) / 2
        y0 = self.SHOE_ZONE[1] + 42
        return x0, y0, w, h, gap_x, gap_y

    # --------------------------------------------------------- larger action buttons
    def render_action_buttons(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        if self.stage == 'settled':
            self.status_label.pack_forget()
            self.action_frame.pack_forget()
            self.action_frame.pack(fill=tk.BOTH, expand=True, pady=1)
        else:
            self.action_frame.pack_forget()
            if not self.status_label.winfo_manager():
                self.status_label.pack(fill=tk.X, pady=(0, 2))
            self.action_frame.pack(fill=tk.X, pady=1)

        def make_btn(text, command, bg, enabled=True, right_command=None, fg='white'):
            button = tk.Button(
                self.action_frame, text=text, command=command,
                font=('Arial', 13, 'bold'), bg=bg, fg=fg,
                activebackground=bg, relief=tk.RAISED,
                state=tk.NORMAL if enabled else tk.DISABLED,
            )
            if right_command is not None:
                button.bind('<Button-3>', lambda _event: right_command())
            return button

        if self.stage == 'betting':
            repeat_ok = self.last_ante >= MIN_ANTE and self.last_ante <= min(MAX_ANTE, self.balance)
            start_ok = self.ante >= MIN_ANTE and self.ante <= self.balance and not self.animation_running
            for i in range(2):
                self.action_frame.columnconfigure(i, weight=1)
            make_btn('重复下注', self.repeat_bet, '#FFC107', repeat_ok, fg='black').grid(
                row=0, column=0, sticky='nsew', padx=(0, 4), pady=1
            )
            make_btn('开始游戏', self.start_round, '#4CAF50', start_ok).grid(
                row=0, column=1, sticky='nsew', padx=(4, 0), pady=1
            )
        elif self.stage == 'player_set':
            for i in range(2):
                self.action_frame.columnconfigure(i, weight=1)
            make_btn('自动分牌', self.use_house_way, '#4B8BBE').grid(
                row=0, column=0, sticky='nsew', padx=(0, 4), pady=1
            )
            make_btn(
                '提交分牌', self.submit_player_split, '#4CAF50',
                len(self.selection_order) == 2,
            ).grid(row=0, column=1, sticky='nsew', padx=(4, 0), pady=1)
        elif self.stage == 'settled':
            button = make_btn(
                '再来一局', self.new_round, '#FFC107', True,
                right_command=self.show_full_tile_order, fg='black',
            )
            button.place(relx=0.5, rely=0.5, anchor='center', width=190, height=42)
        else:
            tk.Label(
                self.action_frame, text='动画进行中，请稍候…',
                font=('Arial', 12, 'bold'), bg=self.PANEL_BG, fg='#6B6251'
            ).pack(expand=True)

    # --------------------------------------------------------- initial shoe slides LEFT on first load
    def _animate_initial_shoe_left(self):
        if self._closing:
            return
        new_tiles = self.secure_shuffle(build_pai_gow_set())
        frames = 24
        travel = (self.SHOE_ZONE[2] - self.SHOE_ZONE[0]) + 45

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('initial_shoe_slide')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            # Positive offset is to the right; decreasing to zero visibly moves LEFT.
            offset = travel * (1 - smooth)
            self._draw_shoe_snapshot(new_tiles, offset, 'initial_shoe_slide')
            if step < frames:
                self.after(28, lambda: frame(step + 1))
                return

            self.canvas.delete('initial_shoe_slide')
            self.full_tiles = list(new_tiles)
            self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
            self.deal_wall_visible = True
            self.shoe_ready_for_next_round = True
            self.animation_running = False
            self.status = f'牌九牌靴已就位。玩家位置：{self.player_position}号位。'
            self.update_display()

        frame(0)

    # --------------------------------------------------------- return to ORIGINAL shoe slots
    def new_round(self):
        if self.stage != 'settled' or self.animation_running:
            return

        if len(self.full_tiles) != 32 or not (self.player_low and self.player_high and self.dealer_low and self.dealer_high):
            self._finish_new_shoe_immediately()
            return

        self.stage = 'shoe_exchange'
        self.animation_running = True
        self.status = '玩家与庄家牌九正在回到原来的牌靴位置…'
        try:
            self.stage_label.config(text='换牌靴')
            self.status_label.pack(fill=tk.X, pady=(0, 2))
            self.status_label.config(text='当前牌九归回原位…')
        except (AttributeError, tk.TclError):
            pass
        self.render_action_buttons()

        old_tiles = list(self.full_tiles)
        start_states = self._returning_start_states()
        return_uids = set(start_states)
        # Critical V7 change: every live tile returns to the exact slot it occupied
        # in this round's original 32-tile shoe.
        target_index = {tile.uid: idx for idx, tile in enumerate(old_tiles)}

        self.canvas.delete('tile_dynamic')
        self.canvas.delete('deal_wall')
        self.canvas.itemconfigure(self.dealer_header_item, text='庄家')
        self.canvas.itemconfigure(self.player_header_item, text='玩家')
        self._draw_shoe_snapshot(old_tiles, tag='shoe_return_base', hide_uids=return_uids)

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
                tcx, tcy = tx + tw/2, ty + th/2
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

    # --------------------------------------------------------- old RIGHT, new LEFT simultaneously
    def _animate_shoe_swap(self, old_tiles):
        new_tiles = self.secure_shuffle(build_pai_gow_set())
        frames = 24
        travel = (self.SHOE_ZONE[2] - self.SHOE_ZONE[0]) + 45

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            old_offset = travel * smooth                 # old shoe -> RIGHT
            new_offset = travel * (1 - smooth)           # new shoe -> LEFT to zero
            self._draw_shoe_snapshot(old_tiles, old_offset, 'shoe_swap_old')
            self._draw_shoe_snapshot(new_tiles, new_offset, 'shoe_swap_new')
            if step < frames:
                self.after(28, lambda: frame(step + 1))
                return

            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            self.full_tiles = list(new_tiles)
            self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
            self.deal_wall_visible = True
            self.shoe_ready_for_next_round = True
            self._reset_after_shoe_exchange()

        frame(0)



# ============================================================
# V8 — clearer hand names, zero-copy banker override, visual instructions
# ============================================================
class ClassicPaiGowGUIV8(ClassicPaiGowGUIV7):
    """V8 rules/presentation refinements requested for clarity.

    - A corresponding ordinary 0-point vs 0-point hand is a banker automatic-win
      trigger for the whole round, so it can never produce a Push.
    - Main hand labels use concise Chinese casino-style notation:
      X点 / 天X / 地X / 天王 / 地王 / 天杠 / 地杠 / 天高九 / 地高九.
    - The instructions window is image-heavy and draws the actual Pai Gow tiles,
      setting directions, special combinations, pair ranking, comparison examples,
      and the dice/shoe flow directly with Tk Canvas graphics.
    """

    PAIR_SHORT_NAMES = {
        'Gee Joon': '至尊对',
        'Teen': '天牌对',
        'Day': '地牌对',
        'Yun': '人牌对',
        'Gor': '鹅牌对',
        'Mooy': '梅牌对',
        'Chong': '长三对',
        'Bon': '板凳对',
        'Foo': '斧头对',
        'Ping': '红头十对',
        'Tit': '长脚七对',
        'Look': '大头六对',
        'Chop Gow': '杂九对',
        'Chop Bot': '杂八对',
        'Chop Chit': '杂七对',
        'Chop Ng': '杂五对',
    }

    # --------------------------------------------------------- hand-name system
    def _display_hand_name(self, hand):
        """Return the compact label shown on the table.

        Ordinary hands:
            7点 / 天7 / 地7
        Special Teen/Day combinations:
            天王 / 地王 / 天杠 / 地杠 / 天高九 / 地高九
        Pairs:
            天牌对 / 地牌对 / ...
        """
        value = evaluate_hand(hand)

        if value.category == 5:
            group = hand[0].group if hand else ''
            return self.PAIR_SHORT_NAMES.get(group, value.name.replace('对子 · ', ''))

        if value.category == 4:
            return '天王' if value.primary == 2 else '地王'
        if value.category == 3:
            return '天杠' if value.primary == 2 else '地杠'
        if value.category == 2:
            return '天高九' if value.primary == 2 else '地高九'

        # Ordinary points.  If a Teen/Day tile is present, expose it directly in
        # the compact label because it is often the part new players care about.
        groups = {tile.group for tile in hand}
        if 'Teen' in groups:
            return f'天{value.primary}'
        if 'Day' in groups:
            return f'地{value.primary}'
        return f'{value.primary}点'

    @staticmethod
    def _ordinary_tiebreak_tile(hand):
        if not hand:
            return None
        return max(hand, key=lambda t: (t.single_rank, t.dots, t.uid))

    def _header_hand_name(self, hand, opposing_hand=None):
        # V8 intentionally keeps the headline compact and uses only the requested
        # X点 / 天X / 地X / 天王... naming system.  Tie-break rules are illustrated
        # in the detailed visual instructions instead of appending English names.
        return self._display_hand_name(hand)

    def _update_hand_headers(self):
        dealer_text = '庄家'
        player_text = '玩家'
        if self.dealer_low and self.dealer_high:
            dealer_text = (
                f"庄家 - {self._display_hand_name(self.dealer_low)}"
                f" & {self._display_hand_name(self.dealer_high)}"
            )
        if self.player_low and self.player_high:
            player_text = (
                f"玩家 - {self._display_hand_name(self.player_low)}"
                f" & {self._display_hand_name(self.player_high)}"
            )
        self.canvas.itemconfigure(self.dealer_header_item, text=dealer_text)
        self.canvas.itemconfigure(self.player_header_item, text=player_text)

    # --------------------------------------------------------------- settlement
    @staticmethod
    def _ordinary_zero_copy(a, b):
        return (
            a.category == 1 and b.category == 1 and
            a.primary == 0 and b.primary == 0
        )

    def settle_round(self):
        if not (self.player_low and self.player_high and self.dealer_low and self.dealer_high):
            return

        pl = evaluate_hand(self.player_low)
        ph = evaluate_hand(self.player_high)
        dl = evaluate_hand(self.dealer_low)
        dh = evaluate_hand(self.dealer_high)

        low_cmp = compare_hand_values(pl, dl)
        high_cmp = compare_hand_values(ph, dh)

        low_zero_copy = self._ordinary_zero_copy(pl, dl)
        high_zero_copy = self._ordinary_zero_copy(ph, dh)

        # Ordinary zero has no individual-tile tie-break value in this ruleset.
        # A player zero can never win a corresponding banker zero.
        low_win = (low_cmp > 0) and not (pl.category == 1 and pl.primary == 0)
        high_win = (high_cmp > 0) and not (ph.category == 1 and ph.primary == 0)

        def state_from_cmp(cmp_value, is_zero_copy=False, player_side=True):
            # Keep a Copy visually white, matching the user's previous colour rule.
            if cmp_value == 0 or is_zero_copy:
                return 'tie'
            if player_side:
                return 'win' if cmp_value > 0 else 'lose'
            return 'win' if cmp_value < 0 else 'lose'

        self.hand_outcomes = {
            ('player', 'low'): state_from_cmp(low_cmp, low_zero_copy, True),
            ('player', 'high'): state_from_cmp(high_cmp, high_zero_copy, True),
            ('dealer', 'low'): state_from_cmp(low_cmp, low_zero_copy, False),
            ('dealer', 'high'): state_from_cmp(high_cmp, high_zero_copy, False),
        }

        # V8 rule override requested by the user:
        # if either corresponding hand is ordinary 0 vs ordinary 0, the banker
        # wins the ROUND immediately.  Do not allow the other hand to turn it
        # into a Push.
        if low_zero_copy or high_zero_copy:
            returned = 0.0
            result = '庄家获胜'
            which = []
            if low_zero_copy:
                which.append('前道普通0点相同')
            if high_zero_copy:
                which.append('后道普通0点相同')
            detail = '、'.join(which) + '｜庄家自动获胜｜底注输'
            self.ante_display_bg = 'white'
            self.ante_display_amount = 0.0
        elif low_win and high_win:
            profit = self.ante * 0.95
            returned = self.ante + profit
            self.balance += returned
            result = '玩家获胜'
            detail = f'两道全胜｜返还 ${self._fmt(returned)}（净赢 ${self._fmt(profit)}）'
            self.ante_display_bg = 'gold'
            self.ante_display_amount = returned
        elif (not low_win) and (not high_win):
            returned = 0.0
            result = '庄家获胜'
            detail = '两道均未胜｜底注输'
            self.ante_display_bg = 'white'
            self.ante_display_amount = 0.0
        else:
            returned = float(self.ante)
            self.balance += returned
            result = 'Push 平局'
            detail = f'一胜一负｜退回底注 ${self._fmt(returned)}'
            self.ante_display_bg = 'light blue'
            self.ante_display_amount = returned

        def line_result(cmp_value, zero_copy, player_won):
            if zero_copy:
                return '普通0点相同（庄家自动胜局）'
            if cmp_value == 0:
                return 'Copy（庄家胜该道）'
            return '玩家胜' if player_won else '庄家胜'

        self.last_return = returned
        self.last_result = f'{result}　{detail}'
        self.status = (
            f"前道：玩家 {self._display_hand_name(self.player_low)} vs "
            f"庄家 {self._display_hand_name(self.dealer_low)} → "
            f"{line_result(low_cmp, low_zero_copy, low_win)}　｜　"
            f"后道：玩家 {self._display_hand_name(self.player_high)} vs "
            f"庄家 {self._display_hand_name(self.dealer_high)} → "
            f"{line_result(high_cmp, high_zero_copy, high_win)}"
        )
        self.stage = 'settled'
        self._persist_balance()
        self.update_display()

    # --------------------------------------------------------- shoe direction continuity
    def _animate_initial_shoe_left(self):
        """First shoe enters from the LEFT and moves right into position."""
        if self._closing:
            return
        new_tiles = self.secure_shuffle(build_pai_gow_set())
        frames = 24
        travel = (self.SHOE_ZONE[2] - self.SHOE_ZONE[0]) + 45

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('initial_shoe_slide')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            offset = -travel * (1 - smooth)  # LEFT -> RIGHT to zero
            self._draw_shoe_snapshot(new_tiles, offset, 'initial_shoe_slide')
            if step < frames:
                self.after(28, lambda: frame(step + 1))
                return

            self.canvas.delete('initial_shoe_slide')
            self.full_tiles = list(new_tiles)
            self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
            self.deal_wall_visible = True
            self.shoe_ready_for_next_round = True
            self.animation_running = False
            self.status = f'牌九牌靴已就位。玩家位置：{self.player_position}号位。'
            self.update_display()

        frame(0)

    def _animate_shoe_swap(self, old_tiles):
        """Old shoe exits to the RIGHT; new shoe enters from the LEFT."""
        new_tiles = self.secure_shuffle(build_pai_gow_set())
        frames = 24
        travel = (self.SHOE_ZONE[2] - self.SHOE_ZONE[0]) + 45

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            old_offset = travel * smooth                 # current -> RIGHT out
            new_offset = -travel * (1 - smooth)          # LEFT -> current
            self._draw_shoe_snapshot(old_tiles, old_offset, 'shoe_swap_old')
            self._draw_shoe_snapshot(new_tiles, new_offset, 'shoe_swap_new')
            if step < frames:
                self.after(28, lambda: frame(step + 1))
                return

            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            self.full_tiles = list(new_tiles)
            self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
            self.deal_wall_visible = True
            self.shoe_ready_for_next_round = True
            self._reset_after_shoe_exchange()

        frame(0)

    # --------------------------------------------------------- visual instructions
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

    def show_detailed_rules(self):
        """
        经典牌九完整图解玩法。

        本版本重点：
        1. 详细说明32张牌如何组成。
        2. 16种对子全部画出来。
        3. 明确显示每种牌只有2张。
        4. 详细解释王 / 杠 / 高九的实际构造。
        5. 解释普通点数、天X、地X。
        6. 解释牌型完整强弱顺序。
        7. 解释同点、Copy、普通0点。
        8. 解释骰子、16栋、8手牌。
        9. 图解House Way的3种配对。
        10. 所有骨牌采用中心坐标，避免说明页走位。
        """

        win = tk.Toplevel(self)
        win.title('经典牌九 · 完整图解玩法与32张骨牌')
        win.geometry('1040x720+55+20')
        win.resizable(False, False)
        win.configure(bg='#efe7d4')

        # =====================================================
        # 可滚动主区域
        # =====================================================
        shell = tk.Frame(
            win,
            bg='#efe7d4'
        )
        shell.pack(
            fill='both',
            expand=True,
            padx=8,
            pady=8
        )

        scroller = tk.Canvas(
            shell,
            bg='#efe7d4',
            highlightthickness=0
        )

        scrollbar = tk.Scrollbar(
            shell,
            orient='vertical',
            command=scroller.yview
        )

        scroller.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side='right',
            fill='y'
        )

        scroller.pack(
            side='left',
            fill='both',
            expand=True
        )

        content = tk.Frame(
            scroller,
            bg='#efe7d4'
        )

        window_id = scroller.create_window(
            (0, 0),
            window=content,
            anchor='nw'
        )

        def resize_inner(_event=None):
            try:
                scroller.itemconfigure(
                    window_id,
                    width=scroller.winfo_width()
                )

                scroller.configure(
                    scrollregion=scroller.bbox('all')
                )

            except tk.TclError:
                pass

        content.bind(
            '<Configure>',
            resize_inner
        )

        scroller.bind(
            '<Configure>',
            resize_inner
        )

        def mousewheel(event):
            delta = -1 if event.delta > 0 else 1
            scroller.yview_scroll(
                delta * 3,
                'units'
            )

        win.bind(
            '<MouseWheel>',
            mousewheel
        )

        # =====================================================
        # UI 配色
        # =====================================================
        PANEL = '#fffaf0'
        GOLD = '#d8b46a'
        INK = '#2a1b08'
        MUTED = '#705f49'
        BLUE = '#2c6e9f'
        BROWN = '#8a5318'
        GREEN = '#0b6b45'
        RED = '#b51f1f'

        title_font = (
            'Microsoft YaHei',
            18,
            'bold'
        )

        section_font = (
            'Microsoft YaHei',
            13,
            'bold'
        )

        body_font = (
            'Microsoft YaHei',
            10
        )

        small_font = (
            'Microsoft YaHei',
            9
        )

        mini_font = (
            'Microsoft YaHei',
            8
        )

        # =====================================================
        # 总标题
        # =====================================================
        tk.Label(
            content,
            text='经典牌九 · 完整图解说明',
            font=(
                'Microsoft YaHei',
                20,
                'bold'
            ),
            bg='#efe7d4',
            fg=INK,
        ).pack(
            fill='x',
            pady=(5, 3)
        )

        tk.Label(
            content,
            text=(
                '先看牌 → 再看两张牌怎样组成牌型 '
                '→ 最后学4张牌怎样分成前道和后道'
            ),
            font=(
                'Microsoft YaHei',
                10,
                'bold'
            ),
            bg='#efe7d4',
            fg=MUTED,
        ).pack(
            fill='x',
            pady=(0, 10)
        )

        # =====================================================
        # Section 创建器
        # =====================================================
        def section(
            title,
            body='',
            height=200
        ):
            outer = tk.Frame(
                content,
                bg=PANEL,
                bd=1,
                relief=tk.SOLID
            )

            outer.pack(
                fill='x',
                padx=8,
                pady=6
            )

            tk.Label(
                outer,
                text=title,
                font=section_font,
                bg=GOLD,
                fg=INK,
                anchor='w',
                padx=10,
                pady=5,
            ).pack(
                fill='x'
            )

            if body:
                tk.Label(
                    outer,
                    text=body,
                    font=body_font,
                    bg=PANEL,
                    fg=INK,
                    justify='left',
                    anchor='w',
                    padx=12,
                    pady=7,
                    wraplength=965,
                ).pack(
                    fill='x'
                )

            viz = tk.Canvas(
                outer,
                width=975,
                height=height,
                bg=PANEL,
                highlightthickness=0,
            )

            viz.pack(
                padx=8,
                pady=(0, 8)
            )

            return viz

        # =====================================================
        # 说明页骰子
        # =====================================================
        def draw_die(
            c,
            cx,
            cy,
            value,
            size=54
        ):
            """
            直接用Canvas画骰子。
            固定中心定位，避免PhotoImage尺寸不同造成走位。
            """

            r = size / 2

            x0 = cx - r
            y0 = cy - r
            x1 = cx + r
            y1 = cy + r

            c.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill='#f0f0e9',
                outline='#222',
                width=2
            )

            positions = {
                1: [
                    (0.50, 0.50)
                ],

                2: [
                    (0.28, 0.28),
                    (0.72, 0.72)
                ],

                3: [
                    (0.28, 0.28),
                    (0.50, 0.50),
                    (0.72, 0.72)
                ],

                4: [
                    (0.28, 0.28),
                    (0.72, 0.28),
                    (0.28, 0.72),
                    (0.72, 0.72)
                ],

                5: [
                    (0.28, 0.28),
                    (0.72, 0.28),
                    (0.50, 0.50),
                    (0.28, 0.72),
                    (0.72, 0.72)
                ],

                6: [
                    (0.28, 0.20),
                    (0.72, 0.20),
                    (0.28, 0.50),
                    (0.72, 0.50),
                    (0.28, 0.80),
                    (0.72, 0.80)
                ],
            }

            pip_r = max(
                3,
                int(size / 11)
            )

            pip_color = (
                '#d21e2b'
                if value in (1, 4)
                else '#111'
            )

            for ux, uy in positions[value]:

                px = x0 + ux * size
                py = y0 + uy * size

                c.create_oval(
                    px - pip_r,
                    py - pip_r,
                    px + pip_r,
                    py + pip_r,
                    fill=pip_color,
                    outline=''
                )

        # =====================================================
        # 简化牌型名称
        # =====================================================
        def hand_name(hand):
            return self._display_hand_name(
                hand
            )

        # =====================================================
        # 自动找普通点数示例
        # =====================================================
        def find_ordinary(
            points,
            require_group=None,
            forbid_groups=()
        ):
            """
            找普通0~9点示例。
            自动排除对子 / 王 / 杠 / 高九。
            """

            for i, a in enumerate(tiles):

                for b in tiles[i + 1:]:

                    groups = {
                        a.group,
                        b.group
                    }

                    if (
                        require_group
                        and require_group not in groups
                    ):
                        continue

                    if (
                        a.group in forbid_groups
                        or b.group in forbid_groups
                    ):
                        continue

                    hv = evaluate_hand(
                        [a, b]
                    )

                    if (
                        hv.category == 1
                        and hv.primary == points
                    ):
                        return a, b

            raise LookupError(
                f'找不到普通{points}点示例'
            )

        # =====================================================
        # 建立牌九牌组
        # =====================================================
        tiles = build_pai_gow_set()

        by_group = {}

        for tile in tiles:
            by_group.setdefault(
                tile.group,
                []
            ).append(tile)

        # =====================================================
        # 指定示例牌
        # =====================================================
        teen = self._instruction_find_tile(
            tiles,
            group='Teen'
        )

        day = self._instruction_find_tile(
            tiles,
            group='Day'
        )

        gee_luk = self._instruction_find_tile(
            tiles,
            group='Gee Joon',
            shape=(2, 4)
        )

        gee_saam = self._instruction_find_tile(
            tiles,
            group='Gee Joon',
            shape=(1, 2)
        )

        # ---------- 9点牌 ----------
        nine_36 = self._instruction_find_tile(
            tiles,
            shape=(3, 6)
        )

        nine_45 = self._instruction_find_tile(
            tiles,
            shape=(4, 5)
        )

        # ---------- 8点牌 ----------
        eight_44 = self._instruction_find_tile(
            tiles,
            shape=(4, 4)
        )

        eight_35 = self._instruction_find_tile(
            tiles,
            shape=(3, 5)
        )

        eight_26 = self._instruction_find_tile(
            tiles,
            shape=(2, 6)
        )

        # ---------- 7点牌 ----------
        seven_16 = self._instruction_find_tile(
            tiles,
            shape=(1, 6)
        )

        seven_34 = self._instruction_find_tile(
            tiles,
            shape=(3, 4)
        )

        seven_25 = self._instruction_find_tile(
            tiles,
            shape=(2, 5)
        )

        # ---------- 其他示例牌 ----------
        five_14 = self._instruction_find_tile(
            tiles,
            shape=(1, 4)
        )

        five_23 = self._instruction_find_tile(
            tiles,
            shape=(3, 2)
        )

        six_15 = self._instruction_find_tile(
            tiles,
            shape=(1, 5)
        )

        # =========================================================
        # 1. 32张牌组成
        # =========================================================
        c = section(
            '1. 一副经典牌九到底有多少张？'
            '—— 32张 = 16种对子 × 每种2张',

            (
                '每一种“牌名”都正好有2张实体骨牌，所以一副共32张。'
                '其中11种对子是两张完全相同的牌；'
                '至尊 + 杂九 / 杂八 / 杂七 / 杂五这5种对子，'
                '是由两张点阵不同但同属一组的牌组成。'
                '下面把整副32张全部画出来。'
            ),

            height=565
        )

        ranked_groups = sorted(
            by_group,
            key=lambda g:
            min(
                t.pair_rank
                for t in by_group[g]
            )
        )

        cell_w = 236
        cell_h = 132

        for idx, group in enumerate(
            ranked_groups
        ):
            row, col = divmod(
                idx,
                4
            )

            x0 = 10 + col * cell_w
            y0 = 10 + row * cell_h

            group_tiles = (
                by_group[group][:2]
            )

            rank = (
                group_tiles[0].pair_rank
            )

            c.create_rectangle(
                x0,
                y0,
                x0 + 224,
                y0 + 120,
                fill='#fbf6e9',
                outline='#d8c69a'
            )

            # 两张牌始终用中心定位
            self._instruction_tile(
                c,
                group_tiles[0],
                x0 + 43,
                y0 + 55,
                scale=.62
            )

            self._instruction_tile(
                c,
                group_tiles[1],
                x0 + 83,
                y0 + 55,
                scale=.62
            )

            c.create_text(
                x0 + 122,
                y0 + 27,
                anchor='w',
                text=(
                    f'{rank:02d}. '
                    f'{self.PAIR_SHORT_NAMES.get(group, group)}'
                ),
                font=(
                    'Microsoft YaHei',
                    9,
                    'bold'
                ),
                fill=INK,
            )

            c.create_text(
                x0 + 122,
                y0 + 53,
                anchor='w',
                text='共2张',
                font=small_font,
                fill=BROWN,
            )

            shape_text = ' + '.join(
                f'{t.a}-{t.b}'
                for t in group_tiles
            )

            identical = (
                group_tiles[0].shape
                ==
                group_tiles[1].shape
            )

            c.create_text(
                x0 + 122,
                y0 + 78,
                anchor='w',
                text=shape_text,
                font=mini_font,
                fill=MUTED,
            )

            c.create_text(
                x0 + 122,
                y0 + 99,
                anchor='w',
                text=(
                    '相同双牌'
                    if identical
                    else '不同点阵也能成对'
                ),
                font=mini_font,
                fill=(
                    MUTED
                    if identical
                    else BLUE
                ),
            )

        c.create_text(
            487,
            545,
            text=(
                '11种相同双牌 = 22张'
                '　＋　'
                '5种不同点阵对子 = 10张'
                '　＝　32张'
            ),
            font=(
                'Microsoft YaHei',
                11,
                'bold'
            ),
            fill=BROWN,
        )

        # =========================================================
        # 2. 点数和身份
        # =========================================================
        c = section(
            '2. 先分清“骨牌点数”和“骨牌身份”',

            (
                '牌面上的点数只是计算普通0～9点的材料；'
                '牌本身还有身份与单牌等级。'
                '天牌虽然是12点、地牌虽然只有2点，'
                '但两张都是很高等级的单牌。'
                '至尊两张更特殊：拆开使用时可以按3或6计算。'
            ),

            height=230
        )

        examples = [
            (
                '天牌',
                teen,
                '6-6 = 12点\n高等级单牌'
            ),

            (
                '地牌',
                day,
                '1-1 = 2点\n高等级单牌'
            ),

            (
                '至尊六',
                gee_luk,
                '2-4\n拆开可按6或3'
            ),

            (
                '至尊三',
                gee_saam,
                '1-2\n拆开可按3或6'
            ),
        ]

        for idx, (
            name,
            tile,
            description
        ) in enumerate(examples):

            cx = (
                125
                +
                idx * 235
            )

            self._instruction_tile(
                c,
                tile,
                cx,
                82,
                scale=.92
            )

            c.create_text(
                cx,
                155,
                text=name,
                font=title_font,
                fill=INK
            )

            c.create_text(
                cx,
                193,
                text=description,
                font=small_font,
                fill=MUTED,
                justify='center'
            )

        # =========================================================
        # 3. 4张怎么分
        # =========================================================
        c = section(
            '3. 4张牌怎样摆？—— 玩家只选2张前道',

            (
                '收到4张后，你只需要点选2张作为前道。'
                '没有被选的另外2张自动成为后道。'
                '提交后，前道两张是同一张骨牌整体旋转90°'
                '后上下摆成“=”；后道两张保持直立并排。'
                '后道必须不小于前道。'
            ),

            height=255
        )

        demo4 = [
            teen,
            five_14,
            six_15,
            seven_16
        ]

        for i, tile in enumerate(
            demo4
        ):
            self._instruction_tile(
                c,
                tile,
                75 + i * 75,
                92,
                scale=.72
            )

        c.create_text(
            190,
            190,
            text='原始4张',
            font=(
                'Microsoft YaHei',
                11,
                'bold'
            ),
            fill=INK
        )

        c.create_text(
            390,
            92,
            text='→ 选择2张前道 →',
            font=title_font,
            fill=BROWN
        )

        # 前道：物理旋转90°
        self._instruction_tile(
            c,
            teen,
            600,
            67,
            horizontal=True,
            scale=.78,
            outline=True
        )

        self._instruction_tile(
            c,
            five_14,
            600,
            129,
            horizontal=True,
            scale=.78,
            outline=True
        )

        c.create_text(
            600,
            195,
            text='前道 LOW',
            font=(
                'Microsoft YaHei',
                10,
                'bold'
            ),
            fill=BLUE
        )

        # 后道
        self._instruction_tile(
            c,
            six_15,
            785,
            92,
            scale=.78
        )

        self._instruction_tile(
            c,
            seven_16,
            855,
            92,
            scale=.78
        )

        c.create_text(
            820,
            195,
            text='后道 HIGH',
            font=(
                'Microsoft YaHei',
                10,
                'bold'
            ),
            fill=BROWN
        )

        # =========================================================
        # 4. 普通点数
        # =========================================================
        c = section(
            '4. 普通牌怎样算？—— 两张点数相加，只取个位',

            (
                '只要没有组成对子、王、杠或高九，'
                '就按普通点数计算。'
                '界面命名规则是：普通手写“X点”；'
                '含天牌写“天X”；含地牌写“地X”。'
                '“天8 / 地8”仍然只是普通8点，'
                '不会高过普通9点。'
            ),

            height=270
        )

        ordinary9 = find_ordinary(
            9,
            forbid_groups=(
                'Teen',
                'Day'
            )
        )

        teen8 = find_ordinary(
            8,
            require_group='Teen'
        )

        day7 = find_ordinary(
            7,
            require_group='Day'
        )

        samples = [
            (
                '普通9点',
                ordinary9,
                '普通9点 > 天8'
            ),

            (
                '天8',
                teen8,
                '有天牌，但仍然只是普通8点'
            ),

            (
                '地7',
                day7,
                '有地牌，但仍然只是普通7点'
            ),
        ]

        for idx, (
            label,
            hand,
            note
        ) in enumerate(samples):

            cx = (
                165
                +
                idx * 315
            )

            self._instruction_tile(
                c,
                hand[0],
                cx - 38,
                90,
                scale=.70
            )

            self._instruction_tile(
                c,
                hand[1],
                cx + 38,
                90,
                scale=.70
            )

            c.create_text(
                cx,
                170,
                text=label,
                font=title_font,
                fill=GREEN
            )

            c.create_text(
                cx,
                205,
                text=note,
                font=small_font,
                fill=MUTED
            )

            c.create_text(
                cx,
                232,
                text=(
                    f'{hand[0].dots}'
                    f' + '
                    f'{hand[1].dots}'
                    f' → '
                    f'{evaluate_hand(hand).primary}点'
                ),
                font=mini_font,
                fill=BROWN,
            )

        # =========================================================
        # 5. 特殊组合构造
        # =========================================================
        c = section(
            '5. 特殊牌型怎样组成？'
            '—— 天牌 / 地牌 + 指定“原始牌点数”',

            (
                '这里最重要：'
                '看的是另一张骨牌本身有几颗点，'
                '不是两张相加后的个位。'
                '天/地 + 9点牌 = 王；'
                '天/地 + 8点牌 = 杠；'
                '天/地 + 7点牌 = 高九。'
                '这些特殊牌型全部高于普通9点。'
            ),

            height=590
        )

        special_rows = [
            (
                '王',
                9,
                [
                    nine_36,
                    nine_45
                ],
                '9点牌只有 3-6、4-5 两种形状'
            ),

            (
                '杠',
                8,
                [
                    eight_44,
                    eight_35,
                    eight_26
                ],
                '8点牌可为 4-4、3-5、2-6'
            ),

            (
                '高九',
                7,
                [
                    seven_16,
                    seven_34,
                    seven_25
                ],
                '7点牌可为 1-6、3-4、2-5'
            ),
        ]

        for row, (
            kind,
            target,
            eligible,
            note
        ) in enumerate(special_rows):

            y0 = (
                18
                +
                row * 188
            )

            c.create_rectangle(
                15,
                y0,
                945,
                y0 + 172,
                fill='#fbf6e9',
                outline='#cfb77d'
            )

            c.create_text(
                35,
                y0 + 24,
                anchor='w',
                text=(
                    f'{kind}：'
                    f'另一张必须是{target}点牌'
                ),
                font=(
                    'Microsoft YaHei',
                    12,
                    'bold'
                ),
                fill=BROWN
            )

            # =========================
            # 天牌组合
            # =========================
            self._instruction_tile(
                c,
                teen,
                92,
                y0 + 88,
                scale=.65
            )

            c.create_text(
                132,
                y0 + 88,
                text='+',
                font=(
                    'Arial',
                    17,
                    'bold'
                ),
                fill=INK
            )

            self._instruction_tile(
                c,
                eligible[0],
                175,
                y0 + 88,
                scale=.65
            )

            c.create_text(
                220,
                y0 + 88,
                text='→',
                font=(
                    'Arial',
                    18,
                    'bold'
                ),
                fill=INK
            )

            c.create_text(
                258,
                y0 + 88,
                anchor='w',
                text=f'天{kind}',
                font=title_font,
                fill=RED
            )

            # =========================
            # 地牌组合
            # =========================
            self._instruction_tile(
                c,
                day,
                395,
                y0 + 88,
                scale=.65
            )

            c.create_text(
                435,
                y0 + 88,
                text='+',
                font=(
                    'Arial',
                    17,
                    'bold'
                ),
                fill=INK
            )

            self._instruction_tile(
                c,
                eligible[-1],
                478,
                y0 + 88,
                scale=.65
            )

            c.create_text(
                523,
                y0 + 88,
                text='→',
                font=(
                    'Arial',
                    18,
                    'bold'
                ),
                fill=INK
            )

            c.create_text(
                560,
                y0 + 88,
                anchor='w',
                text=f'地{kind}',
                font=title_font,
                fill=RED
            )

            # =========================
            # 所有可以搭配的点阵
            # =========================
            c.create_text(
                690,
                y0 + 45,
                anchor='w',
                text='可搭配的牌：',
                font=(
                    'Microsoft YaHei',
                    9,
                    'bold'
                ),
                fill=INK
            )

            for i, tile in enumerate(
                eligible
            ):
                self._instruction_tile(
                    c,
                    tile,
                    720 + i * 57,
                    y0 + 100,
                    scale=.46
                )

            c.create_text(
                690,
                y0 + 148,
                anchor='w',
                text=note,
                font=mini_font,
                fill=MUTED
            )

        c.create_text(
            487,
            578,
            text=(
                '特殊牌型强弱：'
                '王 > 杠 > 高九 > '
                '普通9点 > 普通8点 > … > 普通0点'
            ),
            font=(
                'Microsoft YaHei',
                11,
                'bold'
            ),
            fill=RED
        )

        # =========================================================
        # 6. 总牌型大小
        # =========================================================
        c = section(
            '6. 两张牌的总大小顺序',

            (
                '比较一“道”时先看牌型等级。'
                '所有对子都高于所有非对子。'
                '普通牌只有在双方同点时，'
                '才继续比较该手里最高等级的单张骨牌。'
            ),

            height=205
        )

        bands = [
            (
                '所有对子',
                '#6f4aa8'
            ),

            (
                '天王 / 地王',
                '#a24527'
            ),

            (
                '天杠 / 地杠',
                '#b76427'
            ),

            (
                '天高九 / 地高九',
                '#c98728'
            ),

            (
                '普通9点',
                '#2f7e59'
            ),

            (
                '普通8点',
                '#3f8b67'
            ),

            (
                '…',
                '#7b8b80'
            ),

            (
                '普通0点',
                '#777777'
            ),
        ]

        x = 28

        for label, color in bands:

            w = (
                112
                if label != '…'
                else 50
            )

            c.create_rectangle(
                x,
                45,
                x + w,
                112,
                fill=color,
                outline='#493c2d'
            )

            c.create_text(
                x + w / 2,
                78,
                text=label,
                font=(
                    'Microsoft YaHei',
                    9,
                    'bold'
                ),
                fill='white',
                width=w - 8,
                justify='center'
            )

            x += (
                w
                +
                7
            )

        c.create_text(
            487,
            145,
            text=(
                '强  ←──────────────────────────────→  弱'
            ),
            font=(
                'Microsoft YaHei',
                10,
                'bold'
            ),
            fill=BROWN
        )

        c.create_text(
            487,
            178,
            text=(
                '例：普通9点一定大于天8；'
                '任意合法对子一定大于天高九。'
            ),
            font=body_font,
            fill=INK
        )

        # =========================================================
        # 7. 16种对子排名
        # =========================================================
        c = section(
            '7. 16种对子固定排名——数字越小越强',

            (
                '每一种对子在一副牌里恰好就是2张牌。'
                '至尊以及4种杂牌对子虽然两张点阵不同，'
                '仍然属于同一个对子。'
                '所有16种对子都高于天王。'
            ),

            height=805
        )

        for idx, group in enumerate(
            ranked_groups
        ):
            row, col = divmod(
                idx,
                2
            )

            x0 = (
                18
                +
                col * 472
            )

            y0 = (
                8
                +
                row * 96
            )

            group_tiles = (
                by_group[group][:2]
            )

            rank = (
                group_tiles[0].pair_rank
            )

            c.create_rectangle(
                x0,
                y0,
                x0 + 455,
                y0 + 86,
                fill='#fbf6e9',
                outline='#d8c69a'
            )

            self._instruction_tile(
                c,
                group_tiles[0],
                x0 + 38,
                y0 + 43,
                scale=.55
            )

            self._instruction_tile(
                c,
                group_tiles[1],
                x0 + 75,
                y0 + 43,
                scale=.55
            )

            c.create_text(
                x0 + 112,
                y0 + 28,
                anchor='w',
                text=(
                    f'{rank:02d}. '
                    f'{self.PAIR_SHORT_NAMES.get(group, group)}'
                ),
                font=(
                    'Microsoft YaHei',
                    10,
                    'bold'
                ),
                fill=INK
            )

            shapes = ' / '.join(
                f'{t.a}-{t.b}'
                for t in group_tiles
            )

            c.create_text(
                x0 + 112,
                y0 + 53,
                anchor='w',
                text=f'2张：{shapes}',
                font=small_font,
                fill=MUTED
            )

            if (
                group_tiles[0].shape
                !=
                group_tiles[1].shape
            ):
                c.create_text(
                    x0 + 112,
                    y0 + 72,
                    anchor='w',
                    text='注意：两张点阵不同，仍然是对子',
                    font=mini_font,
                    fill=BLUE
                )

        # =========================================================
        # 8. 同点 / Copy / 0点
        # =========================================================
        c = section(
            '8. 同点怎么比？以及本游戏的“普通0点相同”规则',

            (
                '普通1～9点如果点数相同，'
                '会比较该道最高等级的单张骨牌；'
                '完全相同才是Copy。'
                '本版本按你的规则：'
                '只要任意对应一道出现'
                '“玩家普通0点 vs 庄家普通0点”，'
                '庄家直接赢整局，'
                '不允许另一道把结果变成Push。'
            ),

            height=355
        )

        ordinary8 = find_ordinary(
            8,
            forbid_groups=(
                'Teen',
                'Day'
            )
        )

        teen8_example = find_ordinary(
            8,
            require_group='Teen'
        )

        # =========================
        # 同点示例
        # =========================
        c.create_text(
            165,
            27,
            text='同为8点：再比较最高单张牌',
            font=(
                'Microsoft YaHei',
                11,
                'bold'
            ),
            fill=INK
        )

        self._instruction_tile(
            c,
            teen8_example[0],
            85,
            92,
            scale=.58
        )

        self._instruction_tile(
            c,
            teen8_example[1],
            125,
            92,
            scale=.58
        )

        c.create_text(
            170,
            92,
            text='VS',
            font=(
                'Arial',
                16,
                'bold'
            ),
            fill=INK
        )

        self._instruction_tile(
            c,
            ordinary8[0],
            220,
            92,
            scale=.58
        )

        self._instruction_tile(
            c,
            ordinary8[1],
            260,
            92,
            scale=.58
        )

        c.create_text(
            165,
            156,
            text=(
                f'{hand_name(teen8_example)}'
                f'  vs  '
                f'{hand_name(ordinary8)}'
            ),
            font=small_font,
            fill=BLUE
        )

        # =========================
        # 普通0点示例
        # =========================
        zero_hands = []

        for i, a in enumerate(tiles):

            for b in tiles[i + 1:]:

                hv = evaluate_hand(
                    [a, b]
                )

                if (
                    hv.category == 1
                    and hv.primary == 0
                ):
                    zero_hands.append(
                        (a, b)
                    )

                    if len(zero_hands) == 2:
                        break

            if len(zero_hands) == 2:
                break

        if len(zero_hands) == 2:

            c.create_text(
                615,
                27,
                text='普通0点 vs 普通0点',
                font=(
                    'Microsoft YaHei',
                    11,
                    'bold'
                ),
                fill=RED
            )

            for j, tile in enumerate(
                zero_hands[0]
            ):
                self._instruction_tile(
                    c,
                    tile,
                    505 + j * 42,
                    92,
                    scale=.58
                )

            c.create_text(
                590,
                92,
                text='VS',
                font=(
                    'Arial',
                    16,
                    'bold'
                ),
                fill=INK
            )

            for j, tile in enumerate(
                zero_hands[1]
            ):
                self._instruction_tile(
                    c,
                    tile,
                    640 + j * 42,
                    92,
                    scale=.58
                )

            c.create_text(
                615,
                156,
                text='→ 庄家直接赢整局',
                font=(
                    'Microsoft YaHei',
                    11,
                    'bold'
                ),
                fill=RED
            )

        # =========================
        # 结算颜色
        # =========================
        c.create_rectangle(
            70,
            220,
            285,
            300,
            fill='#00ff00',
            outline='#3d6b40'
        )

        c.create_text(
            177,
            260,
            text='赢该道',
            font=title_font,
            fill='#10210f'
        )

        c.create_rectangle(
            365,
            220,
            580,
            300,
            fill='#ff0000',
            outline='#7d2828'
        )

        c.create_text(
            472,
            260,
            text='输该道',
            font=title_font,
            fill='white'
        )

        c.create_rectangle(
            660,
            220,
            875,
            300,
            fill='#ffffff',
            outline='#777'
        )

        c.create_text(
            767,
            260,
            text='Copy',
            font=title_font,
            fill='#222'
        )

        c.create_text(
            487,
            330,
            text=(
                '整局：'
                '两道都赢 = 玩家赢；'
                '一胜一负 = Push；'
                '两道都没赢 = 庄家赢。'
            ),
            font=body_font,
            fill=INK
        )

        # =========================================================
        # 9. 骰子 / 牌九牌靴
        # =========================================================
        c = section(
            '9. 三骰与32张牌九牌靴',

            (
                '32张牌九在牌靴里排成16栋，'
                '每栋上下2张。'
                '每相邻2栋合起来是一手4张，'
                '因此共有8手。'
                '三颗骰子的总点数决定“第几个位置先派”。'
                '界面只为庄家和你选择的1～6号位置'
                '播放实际移动动画，'
                '没有坐人的位置不会做派牌移动。'
            ),

            height=330
        )

        dice_values = (
            2,
            5,
            6
        )

        dice_x = (
            95,
            175,
            255
        )

        for i, (
            cx,
            value
        ) in enumerate(
            zip(
                dice_x,
                dice_values
            )
        ):
            draw_die(
                c,
                cx,
                70,
                value,
                56
            )

            if i < 2:
                c.create_text(
                    cx + 40,
                    70,
                    text='+',
                    font=(
                        'Arial',
                        18,
                        'bold'
                    ),
                    fill=INK
                )

        c.create_text(
            330,
            70,
            anchor='w',
            text=(
                '= 13点'
                '　｜　'
                '第5个派牌'
            ),
            font=title_font,
            fill=BROWN
        )

        # =========================
        # 32张牌九 / 16栋
        # =========================
        shoe_x0 = 55
        shoe_y0 = 150

        tile_w = 24
        tile_h = int(tile_w * CLASSIC_TILE_ASPECT)

        gap_x = 8
        gap_y = 10

        for col in range(16):

            for row in range(2):

                x0 = (
                    shoe_x0
                    +
                    col * (
                        tile_w
                        +
                        gap_x
                    )
                )

                y0 = (
                    shoe_y0
                    +
                    row * (
                        tile_h
                        +
                        gap_y
                    )
                )

                c.create_rectangle(
                    x0,
                    y0,
                    x0 + tile_w,
                    y0 + tile_h,
                    fill='#151515',
                    outline='#d4af37',
                    width=1
                )

                c.create_text(
                    x0 + tile_w / 2,
                    y0 + tile_h / 2,
                    text='牌\n九',
                    font=(
                        'Microsoft YaHei',
                        6,
                        'bold'
                    ),
                    fill='#c9a23b'
                )

        # 说明放在牌靴右边，
        # 不再压在骨牌上面
        c.create_text(
            610,
            190,
            anchor='w',
            text='16栋 × 每栋2张 = 32张牌九',
            font=(
                'Microsoft YaHei',
                11,
                'bold'
            ),
            fill=INK
        )

        c.create_text(
            610,
            225,
            anchor='w',
            text='相邻2栋 = 4张 = 一个位置的一手牌',
            font=body_font,
            fill=MUTED
        )

        c.create_text(
            610,
            260,
            anchor='w',
            text=(
                '一共8手：'
                '庄家 + 6个玩家位置 + 1个Dead位置'
            ),
            font=body_font,
            fill=MUTED
        )

        # =========================================================
        # 10. House Way
        # =========================================================
        c = section(
            '10. House Way 自动分牌到底在比较什么？',

            (
                '4张牌只有3种不同的“两两配对”。'
                '系统会把3种方案全部计算，'
                '然后按传统House Way优先级决定：'
                '先处理对子，再看王 / 杠 / 高九，'
                '最后才比较普通点数与两道平衡。'
                '所以自动分牌不一定是'
                '“把最大的两张放后道”。'
            ),

            height=390
        )

        demo = [
            teen,
            nine_36,
            five_14,
            six_15
        ]

        for i, tile in enumerate(
            demo
        ):
            self._instruction_tile(
                c,
                tile,
                115 + i * 70,
                72,
                scale=.67
            )

        c.create_text(
            410,
            72,
            anchor='w',
            text='这4张只有下面3种分法：',
            font=title_font,
            fill=BROWN
        )

        pairings = [
            (
                (0, 1),
                (2, 3)
            ),

            (
                (0, 2),
                (1, 3)
            ),

            (
                (0, 3),
                (1, 2)
            ),
        ]

        for row, (
            p1,
            p2
        ) in enumerate(pairings):

            y = (
                155
                +
                row * 72
            )

            hand1 = [
                demo[p1[0]],
                demo[p1[1]]
            ]

            hand2 = [
                demo[p2[0]],
                demo[p2[1]]
            ]

            c.create_rectangle(
                40,
                y - 28,
                935,
                y + 28,
                fill='#fbf6e9',
                outline='#d8c69a'
            )

            c.create_text(
                65,
                y,
                anchor='w',
                text=f'方案 {row + 1}',
                font=(
                    'Microsoft YaHei',
                    10,
                    'bold'
                ),
                fill=INK
            )

            self._instruction_tile(
                c,
                hand1[0],
                175,
                y,
                scale=.40
            )

            self._instruction_tile(
                c,
                hand1[1],
                205,
                y,
                scale=.40
            )

            c.create_text(
                240,
                y,
                anchor='w',
                text=f'→ {hand_name(hand1)}',
                font=small_font,
                fill=BLUE
            )

            c.create_text(
                470,
                y,
                text='｜',
                font=(
                    'Arial',
                    14,
                    'bold'
                ),
                fill=INK
            )

            self._instruction_tile(
                c,
                hand2[0],
                535,
                y,
                scale=.40
            )

            self._instruction_tile(
                c,
                hand2[1],
                565,
                y,
                scale=.40
            )

            c.create_text(
                600,
                y,
                anchor='w',
                text=f'→ {hand_name(hand2)}',
                font=small_font,
                fill=BROWN
            )

        best = traditional_house_way(
            demo
        )

        c.create_text(
            487,
            365,
            text=(
                'House Way示例结果：'
                f'前道 {hand_name(best.low)}'
                '　｜　'
                f'后道 {hand_name(best.high)}'
            ),
            font=(
                'Microsoft YaHei',
                11,
                'bold'
            ),
            fill=RED
        )

        # =========================================================
        # 11. 操作 / 赔率
        # =========================================================
        c = section(
            '11. 实际操作与主注结算',

            (
                '只有底注，没有边注。'
                '玩家整局获胜净赔率0.95:1。'
                '例如底注$100：'
                '赢时返还$195'
                '（本金$100 + 净赢$95）；'
                'Push只退回原底注。'
            ),

            height=150
        )

        steps = [
            '下注阶段：重复下注 / 开始游戏',

            '派牌结束：自动分牌 / 提交分牌',

            (
                '结算阶段：再来一局'
                '（右键查看32张完整顺序）'
            ),
        ]

        for i, line in enumerate(
            steps,
            start=1
        ):
            y = (
                30
                +
                (i - 1) * 38
            )

            c.create_oval(
                35,
                y - 12,
                59,
                y + 12,
                fill=GOLD,
                outline='#806324'
            )

            c.create_text(
                47,
                y,
                text=str(i),
                font=(
                    'Arial',
                    9,
                    'bold'
                ),
                fill=INK
            )

            c.create_text(
                78,
                y,
                anchor='w',
                text=line,
                font=(
                    'Microsoft YaHei',
                    10,
                    'bold'
                ),
                fill=INK
            )

        # =====================================================
        # Footer
        # =====================================================
        footer = tk.Frame(
            content,
            bg='#2b2118'
        )

        footer.pack(
            fill='x',
            padx=8,
            pady=(8, 16)
        )

        tk.Label(
            footer,
            text=(
                '最重要的记法：'
                '对子 > 王 > 杠 > 高九 > '
                '9点 > 8点 > … > 0点；'
                '4张牌只是在3种两两配对里选一种。'
            ),
            font=(
                'Microsoft YaHei',
                11,
                'bold'
            ),
            bg='#2b2118',
            fg='#f3d36c',
            padx=12,
            pady=12,
        ).pack(
            fill='x'
        )

        resize_inner()

# ============================================================
# V9 — traditional physical pip layouts + alternating black/white shoes
# ============================================================
class ClassicPaiGowGUIV9(ClassicPaiGowGUIV8):
    """Traditional tile artwork and alternating shoe colours.

    - The physical pip coordinates follow the traditional Chinese-domino reference
      rather than reusing ordinary dice layouts inside two generic halves.
    - In particular, 长三 uses its characteristic elongated six-pip layout, 板凳 uses
      horizontal 2-pip ends, and 天牌 uses the traditional alternating red/base pips.
    - The first shoe randomly starts as black or ivory-white.  Every shoe exchange
      flips to the opposite colour, while the red pips keep their traditional colour.
    """

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

    # Normalised physical pip coordinates, transcribed from the traditional
    # reference chart supplied with this revision.  "base" means white on the
    # black set and black on the ivory-white set; red stays red on both sets.
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
        # Pick the colour BEFORE the superclass schedules/draws the first shoe.
        self.tile_theme = 'white' if secrets.randbelow(2) == 0 else 'black'
        self._render_tile_theme_override = None
        super().__init__(
            parent, balance=balance, user=user,
            on_back=on_back, on_balance_change=on_balance_change,
        )

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
        # V7/V8 deliberately suppress tile-name captions and selection badges.

    def _draw_shoe_snapshot(self, tiles, offset_x=0.0, tag='shoe_snapshot', hide_uids=None,
                            theme=None):
        previous = self._render_tile_theme_override
        if theme is not None:
            self._render_tile_theme_override = theme
        try:
            return super()._draw_shoe_snapshot(
                tiles, offset_x=offset_x, tag=tag, hide_uids=hide_uids,
            )
        finally:
            self._render_tile_theme_override = previous

    def _animate_initial_shoe_left(self):
        """First shoe enters from the LEFT; its colour is random per game entry."""
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
            self._draw_shoe_snapshot(
                new_tiles, offset, 'initial_shoe_slide', theme=initial_theme,
            )
            if step < frames:
                self.after(28, lambda: frame(step + 1))
                return

            self.canvas.delete('initial_shoe_slide')
            self.full_tiles = list(new_tiles)
            self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
            self.deal_wall_visible = True
            self.shoe_ready_for_next_round = True
            self.animation_running = False
            self.status = (
                f'{self._tile_colour_name(initial_theme)}牌九牌靴已就位。'
                f'玩家位置：{self.player_position}号位。'
            )
            self.update_display()

        frame(0)

    def _animate_shoe_swap(self, old_tiles):
        """Every replacement shoe uses the opposite physical tile colour."""
        old_theme = self.tile_theme
        new_theme = self._opposite_tile_theme(old_theme)
        new_tiles = self.secure_shuffle(build_pai_gow_set())
        frames = 24
        travel = (self.SHOE_ZONE[2] - self.SHOE_ZONE[0]) + 45

        def frame(step):
            if self._closing:
                return
            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            t = step / frames
            smooth = t * t * (3 - 2 * t)
            old_offset = travel * smooth
            new_offset = -travel * (1 - smooth)
            self._draw_shoe_snapshot(
                old_tiles, old_offset, 'shoe_swap_old', theme=old_theme,
            )
            self._draw_shoe_snapshot(
                new_tiles, new_offset, 'shoe_swap_new', theme=new_theme,
            )
            if step < frames:
                self.after(28, lambda: frame(step + 1))
                return

            self.canvas.delete('shoe_swap_old')
            self.canvas.delete('shoe_swap_new')
            self.tile_theme = new_theme
            self.full_tiles = list(new_tiles)
            self.stacks = [self.full_tiles[i * 4:(i + 1) * 4] for i in range(8)]
            self.deal_wall_visible = True
            self.shoe_ready_for_next_round = True
            self._reset_after_shoe_exchange()

        frame(0)

    def _finish_new_shoe_immediately(self):
        # This path is only a recovery path during a shoe exchange; it must obey
        # the same black <-> white alternation rule.
        self.tile_theme = self._opposite_tile_theme(self.tile_theme)
        return super()._finish_new_shoe_immediately()

    def _reset_after_shoe_exchange(self):
        super()._reset_after_shoe_exchange()
        self.status = (
            f'新{self._tile_colour_name()}牌九牌靴已就位。'
            f'玩家位置：{self.player_position}号位。'
        )
        self.update_display()


# ============================================================
# Entry point — embedded or standalone
# ============================================================

def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return ClassicPaiGowGUIV9(
            parent,
            balance=actual_balance,
            user=actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("经典牌九")
    root.geometry(WINDOW_GEOMETRY)
    root.resizable(False, False)
    page = ClassicPaiGowGUIV9(root, balance=actual_balance, user=actual_user)
    page.pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page


if __name__ == "__main__":
    main()
