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

import copy
import json
import math
import os
import re
import secrets
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk


SUPER_SICBO_VERSION = 'v6'


# -----------------------------------------------------------------------------
# Account-data compatibility with the original project
# -----------------------------------------------------------------------------
def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../A_Tools/Account/saving_data.json')


def load_user_data():
    try:
        with open(get_data_file_path(), 'r', encoding='utf-8') as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_user_data(users):
    try:
        with open(get_data_file_path(), 'w', encoding='utf-8') as handle:
            json.dump(users, handle, ensure_ascii=False, indent=4)
    except OSError:
        pass


def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user.get('user_name') == username:
            user['cash'] = f'{new_balance:.2f}'
            break
    save_user_data(users)


# -----------------------------------------------------------------------------
# Dice and Sic Bo rules
# -----------------------------------------------------------------------------
class Dice:
    def __init__(self):
        self.value = 1

    def roll(self):
        self.value = secrets.randbelow(6) + 1
        return self.value


class SicboEngine:
    """Pure Sic Bo bet state and settlement logic.

    Payout numbers are profit multipliers. The returned credit includes the
    original stake, matching the legacy Sicbo.py behaviour.
    """

    # Super Sic Bo base profit odds.  The enhanced gold odds are generated
    # after betting closes and are independent of both wagers and dice results.
    TARGET_RTP = 35 / 36  # 97.2222...%
    SUPER_MIN_COUNT = 3
    SUPER_MAX_COUNT = 7
    SUPER_ELIGIBLE_CELLS = 52
    # N is uniform on 3..10 and cells are sampled uniformly without replacement.
    SUPER_SELECTION_PROBABILITY = ((SUPER_MIN_COUNT + SUPER_MAX_COUNT) / 2) / SUPER_ELIGIBLE_CELLS
    DOUBLE_PAYOUT = 8
    EXACT_TRIPLE_PAYOUT = 150
    ANY_TRIPLE_PAYOUT = 30
    PAIR_PAYOUT = 5
    NUMBER_GROUP_PAYOUT = 6
    SINGLE_NUMBER_PAYOUT = {1: 1, 2: 2, 3: 3}
    TOTAL_PAYOUT = {
        4: 50, 5: 20, 6: 15, 7: 12, 8: 8, 9: 6, 10: 6,
        11: 6, 12: 6, 13: 8, 14: 12, 15: 15, 16: 20, 17: 50,
    }
    TOTAL_COMBINATIONS = {
        4: 3, 5: 6, 6: 10, 7: 15, 8: 21, 9: 25, 10: 27,
        11: 27, 12: 25, 13: 21, 14: 15, 15: 10, 16: 6, 17: 3,
    }
    SUPER_MAX_PAYOUT = {
        'double': 8,
        'triple': 999,
        'all_triples': 88,
        'pairs': 24,
        'guess_num_2': 19,
        'guess_num_3': 88,
        'number_group': 39,
    }
    TOTAL_MAX_PAYOUT = {
        4: 499, 5: 249, 6: 88, 7: 29, 8: 24, 9: 49, 10: 24,
        11: 24, 12: 49, 13: 24, 14: 29, 15: 88, 16: 249, 17: 499,
    }

    # v6: Super odds are no longer arbitrary integers.  Every displayed gold
    # payout is drawn from one of these fixed, player-friendly pools.  The
    # sampler applies calibrated weights so each pool keeps the exact
    # conditional mean required by the 35/36 (~97.22%) RTP model.
    SUPER_PAYOUT_POOLS = {
        'double': (10, 20, 30, 40, 50, 60, 66, 80, 88),
        'triple': (200, 300, 500, 600, 666, 800, 888, 999),
        'all_triples': (40, 50, 60, 66, 70, 77, 80, 88),
        'pairs': (6, 8, 10, 12, 15, 18, 20, 24),
        'guess_num_2': (3, 5, 6, 8, 10, 12, 15, 18, 19),
        'guess_num_3': (66, 77, 80, 88),
        'number_group': (10, 15, 20, 25, 30, 33, 39),
    }
    TOTAL_PAYOUT_POOLS = {
        4: (80, 99, 100, 150, 200, 250, 300, 399, 499),
        5: (30, 50, 80, 99, 100, 120, 150, 180, 200, 249),
        6: (20, 30, 40, 50, 60, 66, 70, 77, 80, 88),
        7: (15, 18, 20, 22, 25, 29),
        8: (10, 12, 15, 18, 20, 24),
        9: (8, 10, 12, 15, 18, 20, 25, 30, 33, 39, 49),
        10: (8, 10, 12, 15, 18, 20, 24),
        11: (8, 10, 12, 15, 18, 20, 24),
        12: (8, 10, 12, 15, 18, 20, 25, 30, 33, 39, 49),
        13: (10, 12, 15, 18, 20, 24),
        14: (15, 18, 20, 22, 25, 29),
        15: (20, 30, 40, 50, 60, 66, 70, 77, 80, 88),
        16: (30, 50, 80, 99, 100, 120, 150, 180, 200, 249),
        17: (80, 99, 100, 150, 200, 250, 300, 399, 499),
    }
    PAIRS = tuple(f'{a}&{b}' for a in range(1, 7) for b in range(a + 1, 7))
    GROUPS = ('1234', '2345', '2356', '3456')

    def __init__(self):
        self.bets = self.new_bets()

    @classmethod
    def new_bets(cls):
        return {
            'small': 0.0,
            'big': 0.0,
            'odd': 0.0,
            'even': 0.0,
            'all_triples': 0.0,
            'double': {number: 0.0 for number in range(1, 7)},
            'total_points': {total: 0.0 for total in range(4, 18)},
            'pairs': {pair: 0.0 for pair in cls.PAIRS},
            'triple': {number: 0.0 for number in range(1, 7)},
            'guess_num': {number: 0.0 for number in range(1, 7)},
            'number_group': {group: 0.0 for group in cls.GROUPS},
        }

    def total_at_risk(self):
        total = 0.0
        for value in self.bets.values():
            total += sum(value.values()) if isinstance(value, dict) else value
        return total

    def current_area_bet(self, bet_type, param=None):
        value = self.bets[bet_type]
        return value[param] if isinstance(value, dict) else value

    def add_bet(self, bet_type, amount, param=None):
        if amount <= 0:
            return False
        if param is None:
            self.bets[bet_type] += amount
        else:
            self.bets[bet_type][param] += amount
        return True

    def remove_amount(self, bet_type, amount, param=None):
        current = self.current_area_bet(bet_type, param)
        removed = min(current, max(0.0, amount))
        if param is None:
            self.bets[bet_type] -= removed
        else:
            self.bets[bet_type][param] -= removed
        return removed

    def clear_area(self, bet_type, param=None):
        amount = self.current_area_bet(bet_type, param)
        if param is None:
            self.bets[bet_type] = 0.0
        else:
            self.bets[bet_type][param] = 0.0
        return amount

    def resolve_roll(self, dice, triple_mode=False, payout_overrides=None):
        dice = list(dice)
        total = sum(dice)
        is_triple = dice[0] == dice[1] == dice[2]
        outcomes = []
        payout_overrides = payout_overrides or {}
        credit = 0.0
        gross_profit = 0.0
        lost_stake = 0.0

        def payout_for(key, default, count=None):
            override = payout_overrides.get(key)
            if override is None:
                return float(default)
            if isinstance(override, dict):
                return float(override.get(count, default))
            return float(override)

        def settle(label, key, stake, won, payout=0.0, super_applied=None):
            nonlocal credit, gross_profit, lost_stake
            if stake <= 0:
                return
            if won:
                profit = stake * payout
                returned = stake + profit
                credit += returned
                gross_profit += profit
                outcomes.append({
                    'label': label,
                    'key': key,
                    'status': 'win',
                    'stake': stake,
                    'profit': profit,
                    'return_amount': returned,
                    'payout': payout,
                    'is_super': (key in payout_overrides) if super_applied is None else bool(super_applied),
                })
            else:
                lost_stake += stake
                outcomes.append({
                    'label': label,
                    'key': key,
                    'status': 'lose',
                    'stake': stake,
                    'profit': 0.0,
                    'return_amount': 0.0,
                })

        size_payout = 0.95 if triple_mode else 1.0
        basic_specs = (
            ('small', '小', (3 <= total <= 10) if triple_mode else (not is_triple and 4 <= total <= 10)),
            ('big', '大', (11 <= total <= 18) if triple_mode else (not is_triple and 11 <= total <= 17)),
            ('odd', '单', (total % 2 == 1) if triple_mode else (not is_triple and total % 2 == 1)),
            ('even', '双', (total % 2 == 0) if triple_mode else (not is_triple and total % 2 == 0)),
        )
        for bet_type, label, won in basic_specs:
            settle(label, (bet_type, None), self.bets[bet_type], won, size_payout)

        settle('任何围骰', ('all_triples', None), self.bets['all_triples'], is_triple,
               payout_for(('all_triples', None), self.ANY_TRIPLE_PAYOUT))

        for number, amount in self.bets['double'].items():
            settle(f'对子 {number}', ('double', number), amount, dice.count(number) >= 2,
                   payout_for(('double', number), self.DOUBLE_PAYOUT))

        for point, amount in self.bets['total_points'].items():
            settle(f'总点 {point}', ('total_points', point), amount,
                   total == point, payout_for(('total_points', point), self.TOTAL_PAYOUT[point]))

        for pair, amount in self.bets['pairs'].items():
            a, b = map(int, pair.split('&'))
            settle(f'组合 {a}+{b}', ('pairs', pair), amount,
                   dice.count(a) >= 1 and dice.count(b) >= 1,
                   payout_for(('pairs', pair), self.PAIR_PAYOUT))

        for number, amount in self.bets['triple'].items():
            settle(f'围骰 {number}', ('triple', number), amount,
                   dice.count(number) == 3,
                   payout_for(('triple', number), self.EXACT_TRIPLE_PAYOUT))

        for number, amount in self.bets['guess_num'].items():
            count = dice.count(number)
            key = ('guess_num', number)
            base_payout = self.SINGLE_NUMBER_PAYOUT.get(count, 0)
            payout = payout_for(key, base_payout, count=count)
            override = payout_overrides.get(key)
            super_applied = (
                isinstance(override, dict)
                and count in override
                and payout > base_payout
            )
            settle(
                f'单骰 {number}', key, amount, count > 0, payout,
                super_applied=super_applied,
            )

        unique_dice = set(dice)
        for group, amount in self.bets['number_group'].items():
            group_set = {int(value) for value in group}
            settle(f'四数组合 {group}', ('number_group', group), amount,
                   len(unique_dice) == 3 and unique_dice.issubset(group_set),
                   payout_for(('number_group', group), self.NUMBER_GROUP_PAYOUT))

        description, result_color = self.describe_result(dice)
        return {
            'dice': sorted(dice),
            'total': total,
            'is_triple': is_triple,
            'description': description,
            'result_color': result_color,
            'credit': credit,
            'gross_profit': gross_profit,
            'lost_stake': lost_stake,
            'net': gross_profit - lost_stake,
            'outcomes': outcomes,
        }

    @staticmethod
    def describe_result(dice):
        total = sum(dice)
        if dice[0] == dice[1] == dice[2]:
            return '围骰', BubbleSicboGame.TRIPLE_GREEN
        size = '大' if total >= 11 else '小'
        parity = '单' if total % 2 else '双'
        color = BubbleSicboGame.BIG_RED if size == '大' else BubbleSicboGame.SMALL_YELLOW
        return f'{size} & {parity}', color


# -----------------------------------------------------------------------------
# Craps-style embedded Canvas interface
# -----------------------------------------------------------------------------
class BubbleSicboGame(tk.Frame):
    VERSION = SUPER_SICBO_VERSION
    BG = '#17120f'
    PANEL = '#211811'
    PANEL_LINE = '#665240'
    FELT = '#0b4540'
    FELT_2 = '#0d5149'
    LINE = '#c3d5ca'
    GOLD = '#e7d36c'
    SUPER_GOLD = '#e0ad1a'
    SUPER_GOLD_OUTLINE = '#8a5a00'
    SUPER_FLASH_OUTLINE = '#000000'
    SUPER_LABEL_GOLD = '#f2ce67'
    RED = '#c43b40'

    BIG_RED = '#ff4d4f'
    TRIPLE_GREEN = '#55d66b'
    SMALL_YELLOW = '#f2d35f'

    SINGLE_NUMBER_ODDS_TEXT = '1颗1:1 / 2颗2:1 / 3颗3:1'
    SINGLE_NUMBER_TITLES = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六'}

    MIN_BET = 0.5
    MAX_AREA_BET = 100000.0
    MAX_TABLE_BET = 2000000.0
    MAX_RECORDS = 500
    FIXED_POOL_DISTRIBUTION_CACHE = {}

    CHIP_SPECS = [
        (0.5, '#d8b46a', '0.50'),
        (1, '#dedede', '1'),
        (5, '#ba3438', '5'),
        (25, '#42a95b', '25'),
        (100, '#202020', '100'),
        (500, '#70439a', '500'),
        (1000, '#d0a347', '1K'),
    ]

    def __init__(
        self,
        parent,
        balance=10000,
        user=None,
        on_back=None,
        on_balance_change=None,
    ):
        super().__init__(parent, bg=self.BG, width=1150, height=750)
        self.pack_propagate(False)
        self.root = self
        self.username = user
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.balance = float(balance)
        self.final_balance = float(balance)
        self.last_net = 0.0
        self.last_win_amount = 0.0
        self.summary_mode = 'bet'
        self.accept_bets = True
        self.engine = SicboEngine()
        self.dice_objects = [Dice(), Dice(), Dice()]
        self.developer_dice = None
        self.triple_mode = False
        self.super_odds = {}
        self.super_hit_keys = set()
        self.super_reveal_order = []
        self.super_reveal_index = 0
        self.super_reveal_step = 0
        self.super_reveal_active = False
        self.super_reveal_after_id = None

        self.selected_chip = 1.0
        self.multiplier = 1
        self.undo_stack = []
        self.last_round_bets = []
        self.bet_spots = {}
        self.chip_selector_items = {}
        self.control_buttons = {}
        self.animation_running = False
        self.animation_after_id = None
        self.animation_frames_left = 0  # kept for legacy compatibility; v3 is time-based
        self.animation_started_at = 0.0
        self.animation_duration_ms = 0
        self.animation_final_dice = None
        self.result_after_id = None
        self.flash_after_id = None
        self.settlement_running = False
        self.settlement_after_id = None
        self.settlement_flash_step = 0
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.flash_original_text_colors = {}
        self.pre_roll_bets = None
        self._closing = False

        top = self.winfo_toplevel()
        try:
            top.geometry('1150x750+50+10')
            top.resizable(False, False)
        except tk.TclError:
            pass

        top.bind('<Return>', self.handle_enter_roll)
        self.bind('<Control-z>', lambda _event: self.undo_last_bet())
        self.bind('<Shift-R>', lambda _event: self.show_developer_input_dialog())

        self.history_panel_mode = 'history'
        self.history_file = self.get_history_file()
        self.history_data = self.load_history_data()
        self.create_dice_images()
        self.create_ui()
        self.select_chip(1.0)
        self.update_display()

    # ------------------------------------------------------------------ images
    def create_dice_images(self):
        self.dice_images_history = []
        self.dice_images_board = []
        self.dice_images_animation = []
        self.dice_images_triple_info = []

        def make_die(size, number, board_style=False):
            image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            margin = max(1, size // 28)
            radius = max(3, size // 6)
            if board_style:
                die_fill = '#b80f1d'
                die_outline = '#840812'
                pip_color = '#fff8ec'
            else:
                die_fill = '#f0f0e9'
                die_outline = '#222'
                pip_color = '#d21e2b' if number in (1, 4) else '#111'
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
            self.dice_images_history.append(make_die(23, number))
            self.dice_images_board.append(make_die(23, number, board_style=True))
            self.dice_images_animation.append(make_die(86, number))
            self.dice_images_triple_info.append(make_die(38, number))

    # ---------------------------------------------------------------------- UI
    def create_ui(self):
        self.canvas = tk.Canvas(self, width=1150, height=750, bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_rectangle(0, 0, 1150, 750, fill=self.BG, outline='', tags='static')

        self.draw_history_panel()
        self.draw_animation_panel()
        self.draw_board()
        self.capture_spot_visuals()
        self.draw_bottom_controls()

    def draw_history_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = 12, 4, 278, 620
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')

        # The heading itself is an invisible button: no border or button chrome.
        c.create_rectangle(
            x0 + 2, y0 + 2, x1 - 2, y0 + 54,
            fill=self.PANEL, outline='', tags=('static', 'history_toggle')
        )
        self.history_title_item = c.create_text(
            (x0 + x1) / 2, y0 + 24,
            text='历史记录（最近15局）',
            font=('Arial', 17, 'bold'), fill='#d4c3a9',
            tags=('static', 'history_toggle')
        )
        c.tag_bind('history_toggle', '<Button-1>', self.toggle_history_panel)
        c.tag_bind('history_toggle', '<Enter>',
                   lambda _event: c.configure(cursor='hand2'))
        c.tag_bind('history_toggle', '<Leave>',
                   lambda _event: c.configure(cursor=''))

        self.history_panel_bounds = (x0, y0, x1, y1)
        self.draw_history_table_layout()

    def draw_history_table_layout(self):
        c = self.canvas
        x0, y0, x1, y1 = self.history_panel_bounds
        table_x0, table_x1 = x0 + 8, x1 - 8
        header_top = y0 + 72
        header_bottom = header_top + 52
        col1 = table_x0 + 128
        col2 = col1 + 48
        tags = ('history_panel_content',)

        c.create_rectangle(table_x0, header_top, table_x1, y1 - 12,
                           fill='#15110f', outline='#7c6754', width=1, tags=tags)
        c.create_line(col1, header_top, col1, y1 - 12,
                      fill='#7c6754', tags=tags)
        c.create_line(col2, header_top, col2, y1 - 12,
                      fill='#7c6754', tags=tags)
        c.create_line(table_x0, header_bottom, table_x1, header_bottom,
                      fill='#7c6754', tags=tags)
        c.create_text((table_x0 + col1) / 2, (header_top + header_bottom) / 2,
                      text='骰子', font=('Arial', 13, 'bold'),
                      fill='white', tags=tags)
        c.create_text((col1 + col2) / 2, (header_top + header_bottom) / 2,
                      text='点数', font=('Arial', 13, 'bold'),
                      fill='white', tags=tags)
        c.create_text((col2 + table_x1) / 2, (header_top + header_bottom) / 2,
                      text='结果', font=('Arial', 13, 'bold'),
                      fill='white', tags=tags)

        row_height = (y1 - 12 - header_bottom) / 15
        for index in range(1, 16):
            y = header_bottom + index * row_height
            c.create_line(table_x0, y, table_x1, y,
                          fill='#514338', tags=tags)

        self.history_panel_geometry = {
            'x0': table_x0,
            'x1': table_x1,
            'col1': col1,
            'col2': col2,
            'header_bottom': header_bottom,
            'row_height': row_height,
        }

    def toggle_history_panel(self, _event=None):
        self.history_panel_mode = (
            'statistics' if self.history_panel_mode == 'history' else 'history'
        )
        self.canvas.delete('history_panel_content')
        self.canvas.delete('history_dynamic')

        if self.history_panel_mode == 'statistics':
            self.canvas.itemconfigure(
                self.history_title_item, text='历史数据统计'
            )
        else:
            self.canvas.itemconfigure(
                self.history_title_item, text='历史记录（最近15局）'
            )
            self.draw_history_table_layout()
        self.update_history_table()

    def recent_history_dice(self, limit=500):
        dice_rows = []
        for record in self.history_data[:limit]:
            dice = record.get('dice', [])
            if not isinstance(dice, list) or len(dice) != 3:
                continue
            try:
                values = [int(value) for value in dice]
            except (TypeError, ValueError):
                continue
            if all(1 <= value <= 6 for value in values):
                dice_rows.append(values)
        return dice_rows

    def draw_history_statistics(self):
        c = self.canvas
        x0, y0, x1, y1 = self.history_panel_bounds
        dice_rows = self.recent_history_dice(500)
        round_count = len(dice_rows)

        face_counts = [0] * 6
        size_counts = {'小': 0, '大': 0, '围': 0}
        parity_counts = {'单': 0, '双': 0, '围': 0}
        for dice in dice_rows:
            for value in dice:
                face_counts[value - 1] += 1
            total = sum(dice)
            is_triple = dice[0] == dice[1] == dice[2]
            if is_triple:
                size_counts['围'] += 1
                parity_counts['围'] += 1
            else:
                size_counts['小' if total <= 10 else '大'] += 1
                parity_counts['单' if total % 2 else '双'] += 1

        # Pie charts are displayed first, above the bar chart.
        self.draw_statistics_pie(
            centre=(x0 + 72, y0 + 128), radius=43,
            title='小 / 大 / 围', counts=size_counts,
            colors={'小': self.SMALL_YELLOW,
                    '大': self.BIG_RED,
                    '围': self.TRIPLE_GREEN},
            legend_x=x0 + 130, legend_y=y0 + 101
        )
        self.draw_statistics_pie(
            centre=(x0 + 72, y0 + 280), radius=43,
            title='单 / 双 / 围', counts=parity_counts,
            colors={'单': '#53a9d8',
                    '双': '#e7d36c',
                    '围': self.TRIPLE_GREEN},
            legend_x=x0 + 130, legend_y=y0 + 253
        )

        c.create_text(
            (x0 + x1) / 2, y0 + 365,
            text=f'近 {round_count} 局的数量',
            font=('Arial', 11, 'bold'), fill='white',
            tags='history_dynamic'
        )

        chart_x0, chart_x1 = x0 + 24, x1 - 16
        chart_y0, chart_y1 = y0 + 390, y1 - 34
        c.create_line(chart_x0, chart_y0, chart_x0, chart_y1,
                      fill='#8f7a65', tags='history_dynamic')
        c.create_line(chart_x0, chart_y1, chart_x1, chart_y1,
                      fill='#8f7a65', tags='history_dynamic')

        maximum = max(face_counts, default=0)
        scale_max = max(1, maximum)
        plot_width = chart_x1 - chart_x0
        slot_width = plot_width / 6
        bar_width = min(24, slot_width * 0.62)
        bar_colors = ('#e7d36c', '#e98b57', '#c43b40',
                      '#55d66b', '#53a9d8', '#9b72cf')
        for index, count in enumerate(face_counts):
            centre_x = chart_x0 + slot_width * (index + 0.5)
            bar_height = (chart_y1 - chart_y0 - 20) * count / scale_max
            top = chart_y1 - bar_height
            c.create_rectangle(
                centre_x - bar_width / 2, top,
                centre_x + bar_width / 2, chart_y1,
                fill=bar_colors[index], outline='', tags='history_dynamic'
            )
            c.create_text(
                centre_x, max(chart_y0 + 8, top - 9), text=str(count),
                font=('Arial', 9, 'bold'), fill='white', tags='history_dynamic'
            )
            c.create_text(
                centre_x, chart_y1 + 13, text=str(index + 1),
                font=('Arial', 10, 'bold'), fill='#d4c3a9',
                tags='history_dynamic'
            )

    def draw_statistics_pie(self, centre, radius, title, counts,
                            colors, legend_x, legend_y):
        c = self.canvas
        cx, cy = centre
        total = sum(counts.values())
        c.create_text(
            (self.history_panel_bounds[0] + self.history_panel_bounds[2]) / 2,
            cy - radius - 24, text=title,
            font=('Arial', 12, 'bold'), fill='white',
            tags='history_dynamic'
        )

        bounds = (cx - radius, cy - radius, cx + radius, cy + radius)
        if total <= 0:
            c.create_oval(*bounds, fill='#3d342d', outline='#8f7a65',
                          tags='history_dynamic')
        else:
            start = 90.0
            items = list(counts.items())
            for index, (label, count) in enumerate(items):
                extent = 360.0 * count / total
                # Let the final slice close the circle exactly.
                if index == len(items) - 1:
                    extent = 270.0 + start
                c.create_arc(
                    *bounds, start=start, extent=-extent,
                    fill=colors[label], outline=self.PANEL, width=1,
                    tags='history_dynamic'
                )
                start -= extent

        for index, (label, count) in enumerate(counts.items()):
            y = legend_y + index * 27
            c.create_rectangle(
                legend_x, y - 7, legend_x + 14, y + 7,
                fill=colors[label], outline='', tags='history_dynamic'
            )
            percentage = (count / total * 100) if total else 0.0
            c.create_text(
                legend_x + 21, y, anchor='w',
                text=f'{label} {count}  ({percentage:.1f}%)',
                font=('Arial', 9, 'bold'), fill='#d4c3a9',
                tags='history_dynamic'
            )

    def draw_animation_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = 286, 4, 1138, 246
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
        self.animation_panel = (x0, y0, x1, y1)
        self.animation_phase_text = c.create_text(
            (x0 + x1) / 2, y0 + 18, text='超级骰宝 SUPER SIC BO',
            font=('Arial', 16, 'bold'), fill='#d4c3a9', tags='animation'
        )
        c.create_oval(x0 + 186, y0 + 31, x1 - 186, y1 - 14,
                      fill='#193d35', outline='#f1f1ed', width=4, tags='animation')
        c.create_oval(x0 + 210, y0 + 48, x1 - 210, y1 - 31,
                      fill='#0f5a49', outline='#86b9aa', width=2, tags='animation')

        # Latest triple information at the upper-right of the dice-cup area.
        triple_panel_x0 = x1 - 170
        triple_panel_y0 = y0 + 34
        triple_panel_x1 = x1 - 12
        triple_panel_y1 = y0 + 176
        c.create_rectangle(
            triple_panel_x0, triple_panel_y0, triple_panel_x1, triple_panel_y1,
            fill='#15110f', outline='#7c6754', width=1, tags='animation'
        )
        self.last_triple_text = c.create_text(
            (triple_panel_x0 + triple_panel_x1) / 2,
            triple_panel_y0 + 38,
            text='围骰\n暂无记录',
            width=140, justify='center',
            font=('Arial', 22, 'bold'), fill='#d4c3a9', tags='animation'
        )
        triple_dice_y = triple_panel_y0 + 112
        triple_dice_centre_x = (triple_panel_x0 + triple_panel_x1) / 2
        self.last_triple_dice_items = [
            c.create_image(
                triple_dice_centre_x - 48 + index * 48,
                triple_dice_y,
                image=self.dice_images_triple_info[5],
                state='hidden',
                tags=('animation', 'last_triple')
            )
            for index in range(3)
        ]

        centre_x = (x0 + x1) / 2
        centre_y = y0 + 111
        self.animation_dice_base_positions = (
            (centre_x - 104, centre_y),
            (centre_x, centre_y),
            (centre_x + 104, centre_y),
        )
        initial_dice = self.initial_animation_dice()
        self.animation_dice_items = [
            c.create_image(x, y, image=self.dice_images_animation[value - 1],
                           state='normal', tags='animation_dice')
            for (x, y), value in zip(self.animation_dice_base_positions, initial_dice)
        ]
        self.animation_status_bubble = c.create_rectangle(
            x0 + 178, y1 - 48, x1 - 178, y1 - 12,
            fill='#0b2723', outline='#c8efe7', width=2, tags='animation'
        )
        self.animation_status_text = c.create_text(
            centre_x, y1 - 30, text='选择筹码并点击下注区域，然后按“转动”',
            width=500, font=('Arial', 13, 'bold'), fill='white', tags='animation'
        )
        result_y = y1 - 30
        result_xs = (centre_x - 150, centre_x - 100, centre_x - 50)
        self.animation_result_dice_items = [
            c.create_image(x, result_y, image=self.dice_images_history[0],
                           state='hidden', tags=('animation', 'animation_result'))
            for x in result_xs
        ]
        self.animation_result_plus_items = [
            c.create_text(centre_x - 125, result_y, text='+', font=('Arial', 12, 'bold'),
                          fill='white', state='hidden', tags=('animation', 'animation_result')),
            c.create_text(centre_x - 75, result_y, text='+', font=('Arial', 12, 'bold'),
                          fill='white', state='hidden', tags=('animation', 'animation_result')),
        ]
        self.animation_result_suffix = c.create_text(
            centre_x - 25, result_y, anchor='w', text='',
            font=('Arial', 13, 'bold'), fill='white',
            state='hidden', tags=('animation', 'animation_result')
        )

    def update_last_triple_display(self):
        """Display Last_Triple exactly as stored in Sicbo.json."""
        last_triple = getattr(self, 'history_store', {}).get('Last_Triple', [0, 0])
        try:
            triple_value = int(last_triple[0])
            rounds_ago = max(0, int(last_triple[1]))
        except (TypeError, ValueError, IndexError):
            triple_value = 0
            rounds_ago = 0

        if not 1 <= triple_value <= 6:
            self.canvas.itemconfigure(self.last_triple_text, text='围骰\n暂无记录')
            for item in self.last_triple_dice_items:
                self.canvas.itemconfigure(item, state='hidden')
            return

        self.canvas.itemconfigure(
            self.last_triple_text,
            text=f'围骰\n{rounds_ago+1}局前'
        )
        for item in self.last_triple_dice_items:
            self.canvas.itemconfigure(
                item,
                image=self.dice_images_triple_info[triple_value - 1],
                state='normal'
            )

    def initial_animation_dice(self):
        """Return the latest saved dice result, or three sixes for a new table."""
        if self.history_data:
            dice = self.history_data[0].get('dice', [])
            if isinstance(dice, list) and len(dice) == 3:
                try:
                    values = [int(value) for value in dice]
                except (TypeError, ValueError):
                    values = []
                if len(values) == 3 and all(1 <= value <= 6 for value in values):
                    return sorted(values)
        return [6, 6, 6]

    def draw_board(self):
        """Draw a Chinese Sic Bo layout based on the supplied casino-table reference.

        The layout follows the reference's visual hierarchy: gold payout bands,
        red dice tiles, paired double/triple columns, total bets, two-dice
        combinations and a six-cell single-number row. No third-party logos or
        external artwork are embedded.
        """
        c = self.canvas
        bx, by, bw, bh = 286, 252, 852, 368
        self.board_bounds = (bx, by, bx + bw, by + bh)

        border = '#9b8663'
        grid = '#c9bba5'
        cream = '#f7f3ea'
        cream_alt = '#eee5d5'
        gold_band = '#e5cf9e'
        gold_dark = '#7a5a22'
        title_color = '#2f2b27'
        red_text = '#9f2b16'

        c.create_rectangle(
            bx, by, bx + bw, by + bh,
            fill='#e9dfcd', outline=border, width=2, tags='board'
        )

        # Craps-style mode button, positioned above the betting board.
        self.insurance_mode_button = self.create_control_button(
            bx + 2, by - 56, bx + 92, by - 30, '保险~关',
            self.toggle_triple_mode, '#77383b', fg='white', font_size=10
        )
        self.canvas.tag_raise(self.insurance_mode_button)

        def draw_dice(cx, cy, numbers, gap=28, tag='board'):
            if not numbers:
                return
            start_x = cx - gap * (len(numbers) - 1) / 2
            for offset, number in enumerate(numbers):
                c.create_image(
                    start_x + offset * gap, cy,
                    image=self.dice_images_board[int(number) - 1],
                    tags=('board', tag)
                )

        def draw_dice_vertical(cx, cy, numbers, gap=29, tag='board'):
            if not numbers:
                return
            start_y = cy - gap * (len(numbers) - 1) / 2
            for offset, number in enumerate(numbers):
                c.create_image(
                    cx, start_y + offset * gap,
                    image=self.dice_images_board[int(number) - 1],
                    tags=('board', tag)
                )

        def register_rect(bet_type, param, x0, y0, x1, y1, label, chip_y=None):
            tag = self.spot_tag((bet_type, param))
            self.register_spot(
                bet_type, param, x0, y0, x1, y1,
                ((x0 + x1) / 2, chip_y if chip_y is not None else (y0 + y1) / 2),
                label,
            )
            c.tag_bind(tag, '<Button-1>',
                       lambda _event, bt=bet_type, p=param: self.place_bet(bt, p))
            c.tag_bind(tag, '<Button-3>',
                       lambda _event, bt=bet_type, p=param: self.clear_single_bet(bt, p))
            return tag

        def draw_simple_cell(x0, y0, x1, y1, bet_type, param, title, subtitle='',
                             fill=cream, title_size=13, subtitle_size=9,
                             chip_y=None, title_y=None, subtitle_y=None):
            tag = register_rect(bet_type, param, x0, y0, x1, y1, title, chip_y)
            c.create_rectangle(
                x0, y0, x1, y1, fill=fill, outline=grid, width=1,
                tags=('board', tag)
            )
            c.create_text(
                (x0 + x1) / 2,
                title_y if title_y is not None else y0 + (y1 - y0) * 0.39,
                text=title, font=('Arial', title_size, 'bold'), fill=title_color,
                tags=('board', tag)
            )
            if subtitle:
                subtitle_item = c.create_text(
                    (x0 + x1) / 2,
                    subtitle_y if subtitle_y is not None else y0 + (y1 - y0) * 0.73,
                    text=subtitle, font=('Arial', subtitle_size, 'bold'), fill=red_text,
                    tags=('board', tag)
                )
                if bet_type == 'small':
                    self.small_range_text = subtitle_item
                elif bet_type == 'big':
                    self.big_range_text = subtitle_item
            return tag

        y = by

        # Gold payout band above the main bet row.
        odds_h = 18
        c.create_rectangle(bx, y, bx + bw, y + odds_h,
                           fill=gold_band, outline=border, width=1, tags='board')

        # 13 visual groups: small, odd, three doubles, a three-row triple group,
        # any triple, a three-row triple group, three doubles, even and big.
        weights = [1.16, 1.10, 0.74, 0.74, 0.74, 2.25, 1.25,
                   2.25, 0.74, 0.74, 0.74, 1.10, 1.16]
        total_weight = sum(weights)
        bounds = [bx]
        cursor = bx
        for weight in weights:
            cursor += bw * weight / total_weight
            bounds.append(cursor)

        self.basic_payout_text_items = []
        payout_groups = [
            (0, 2, '1:1｜围骰通杀'),
            (2, 5, '8:1'),
            (5, 6, '150:1'),
            (6, 7, '30:1'),
            (7, 8, '150:1'),
            (8, 11, '8:1'),
            (11, 13, '1:1｜围骰通杀'),
        ]
        for start_index, end_index, label in payout_groups:
            x0, x1 = bounds[start_index], bounds[end_index]
            c.create_line(x0, y, x0, y + odds_h, fill=border, tags='board')
            payout_text_id = c.create_text(
                (x0 + x1) / 2, y + odds_h / 2,
                text=label, font=('Arial', 10, 'bold'), fill=gold_dark, tags='board'
            )
            if start_index in (0, 11):
                self.basic_payout_text_items.append(payout_text_id)
        c.create_line(bounds[-1], y, bounds[-1], y + odds_h, fill=border, tags='board')
        y += odds_h

        top_h = 118
        draw_simple_cell(bounds[0], y, bounds[1], y + top_h,
                         'small', None, '小', '4–10',
                         title_size=15, subtitle_size=10,
                         chip_y=y + top_h * 0.52)
        draw_simple_cell(bounds[1], y, bounds[2], y + top_h,
                         'odd', None, '单', '', title_size=15,
                         chip_y=y + top_h * 0.52)

        # Left doubles: two identical dice stacked vertically, no text.
        for slot, number in enumerate((1, 2, 3), start=2):
            x0, x1 = bounds[slot], bounds[slot + 1]
            tag = register_rect('double', number, x0, y, x1, y + top_h,
                                f'对子{number}', chip_y=y + top_h * 0.52)
            c.create_rectangle(x0, y, x1, y + top_h,
                               fill=cream_alt, outline=grid, width=1,
                               tags=('board', tag))
            draw_dice_vertical((x0 + x1) / 2, y + top_h * 0.48,
                               [number, number], gap=30, tag=tag)

        # Left exact triples: three horizontal identical dice, displayed in 3 rows.
        triple_x0, triple_x1 = bounds[5], bounds[6]
        row_h = top_h / 3
        for row, number in enumerate((1, 2, 3)):
            y0 = y + row * row_h
            y1 = y + (row + 1) * row_h
            tag = register_rect('triple', number, triple_x0, y0, triple_x1, y1,
                                f'围骰{number}', chip_y=(y0 + y1) / 2)
            c.create_rectangle(triple_x0, y0, triple_x1, y1,
                               fill=cream_alt, outline=grid, width=1,
                               tags=('board', tag))
            draw_dice((triple_x0 + triple_x1) / 2, (y0 + y1) / 2,
                      [number, number, number], gap=28, tag=tag)

        # Any triple: text only, with no dice below it.
        any_x0, any_x1 = bounds[6], bounds[7]
        any_tag = register_rect('all_triples', None, any_x0, y, any_x1, y + top_h,
                                '任何围骰', chip_y=y + top_h * 0.58)
        c.create_rectangle(any_x0, y, any_x1, y + top_h,
                           fill='#f1eadb', outline=grid, width=1,
                           tags=('board', any_tag))
        c.create_text((any_x0 + any_x1) / 2, y + top_h * 0.40,
                      text='任何\n围骰', font=('Arial', 11, 'bold'),
                      fill=title_color, justify='center', tags=('board', any_tag))

        # Right exact triples: three horizontal identical dice, displayed in 3 rows.
        triple_x0, triple_x1 = bounds[7], bounds[8]
        for row, number in enumerate((4, 5, 6)):
            y0 = y + row * row_h
            y1 = y + (row + 1) * row_h
            tag = register_rect('triple', number, triple_x0, y0, triple_x1, y1,
                                f'围骰{number}', chip_y=(y0 + y1) / 2)
            c.create_rectangle(triple_x0, y0, triple_x1, y1,
                               fill=cream_alt, outline=grid, width=1,
                               tags=('board', tag))
            draw_dice((triple_x0 + triple_x1) / 2, (y0 + y1) / 2,
                      [number, number, number], gap=28, tag=tag)

        # Right doubles: two identical dice stacked vertically, no text.
        for slot, number in enumerate((4, 5, 6), start=8):
            x0, x1 = bounds[slot], bounds[slot + 1]
            tag = register_rect('double', number, x0, y, x1, y + top_h,
                                f'对子{number}', chip_y=y + top_h * 0.52)
            c.create_rectangle(x0, y, x1, y + top_h,
                               fill=cream_alt, outline=grid, width=1,
                               tags=('board', tag))
            draw_dice_vertical((x0 + x1) / 2, y + top_h * 0.48,
                               [number, number], gap=30, tag=tag)

        draw_simple_cell(bounds[11], y, bounds[12], y + top_h,
                         'even', None, '双', '', title_size=15,
                         chip_y=y + top_h * 0.52)
        draw_simple_cell(bounds[12], y, bounds[13], y + top_h,
                         'big', None, '大', '11–17',
                         title_size=15, subtitle_size=10,
                         chip_y=y + top_h * 0.52)
        y += top_h

        # Total points 4-17.
        totals_h = 48
        total_w = bw / 14
        for index, point in enumerate(range(4, 18)):
            x0 = bx + index * total_w
            x1 = bx + (index + 1) * total_w
            draw_simple_cell(
                x0, y, x1, y + totals_h,
                'total_points', point, str(point), f'{SicboEngine.TOTAL_PAYOUT[point]}:1',
                fill=cream, title_size=15, subtitle_size=8,
                chip_y=y + totals_h * 0.48,
                title_y=y + 17, subtitle_y=y + 36,
            )
        y += totals_h

        # Fifteen two-dice combinations. A right-pointing payout wedge is
        # placed to the left of 1+2, and a matching right-pointing “双骰”
        # wedge is placed immediately after 5+6.
        pairs_h = 62
        left_wedge_w = 50
        right_wedge_w = 50
        pairs_x0 = bx + left_wedge_w
        pair_w = (bw - left_wedge_w - right_wedge_w) / 15

        wedge_tag = 'pairs_payout_wedge'
        c.create_polygon(
            bx, y,
            bx + left_wedge_w - 12, y,
            bx + left_wedge_w, y + pairs_h / 2,
            bx + left_wedge_w - 12, y + pairs_h,
            bx, y + pairs_h,
            fill=gold_band, outline=grid, width=1, tags=('board', wedge_tag)
        )
        c.create_text(
            bx + 19, y + pairs_h * 0.46,
            text='赔付\n5:1', font=('Arial', 9, 'bold'),
            fill=red_text, justify='center', tags=('board', wedge_tag)
        )

        for index, pair in enumerate(SicboEngine.PAIRS):
            x0 = pairs_x0 + index * pair_w
            x1 = pairs_x0 + (index + 1) * pair_w
            a, b = [int(value) for value in pair.split('&')]
            tag = register_rect('pairs', pair, x0, y, x1, y + pairs_h,
                                f'{a}+{b}', chip_y=y + pairs_h * 0.50)
            c.create_rectangle(x0, y, x1, y + pairs_h,
                               fill=cream, outline=grid, width=1,
                               tags=('board', tag))
            draw_dice_vertical((x0 + x1) / 2, y + pairs_h * 0.50,
                               [a, b], gap=29, tag=tag)

        right_x0 = pairs_x0 + 15 * pair_w
        right_x1 = bx + bw
        right_tag = 'pairs_label_wedge'
        c.create_polygon(
            right_x0, y + pairs_h / 2,
            right_x0 + 12, y,
            right_x1, y,
            right_x1, y + pairs_h,
            right_x0 + 12, y + pairs_h,
            fill=gold_band, outline=grid, width=1, tags=('board', right_tag)
        )
        c.create_text(
            right_x0 + 12 + (right_wedge_w - 12) / 2, y + pairs_h / 2,
            text='双骰', font=('Arial', 10, 'bold'),
            fill=title_color, tags=('board', right_tag)
        )
        y += pairs_h

        # Four-number groups: win only when all three rolled dice are distinct
        # and all three belong to the selected four-number set. Base payout 6:1.
        group_h = 48
        group_w = bw / 4
        for index, group in enumerate(SicboEngine.GROUPS):
            x0 = bx + index * group_w
            x1 = bx + (index + 1) * group_w
            tag = register_rect('number_group', group, x0, y, x1, y + group_h,
                                f'四数组合{group}', chip_y=y + group_h * 0.50)
            c.create_rectangle(x0, y, x1, y + group_h,
                               fill=cream_alt, outline=grid, width=1,
                               tags=('board', tag))
            group_numbers = [int(value) for value in group]
            draw_dice((x0 + x1) / 2, y + 16, group_numbers, gap=28, tag=tag)
            c.create_text((x0 + x1) / 2, y + 39,
                          text='6:1', font=('Arial', 8, 'bold'),
                          fill=red_text, tags=('board', tag))
        y += group_h

        # Single-number bets.
        single_h = 44
        single_w = bw / 6
        chinese_numbers = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六'}
        for index, number in enumerate(range(1, 7)):
            x0 = bx + index * single_w
            x1 = bx + (index + 1) * single_w
            tag = register_rect('guess_num', number, x0, y, x1, y + single_h,
                                f'单骰{number}', chip_y=y + single_h * 0.50)
            c.create_rectangle(x0, y, x1, y + single_h,
                               fill=cream, outline=grid, width=1,
                               tags=('board', tag))
            centre_x = (x0 + x1) / 2
            draw_dice(centre_x - 14, y + single_h / 2, [number], tag=tag)
            c.create_text(centre_x + 3, y + single_h / 2,
                          anchor='w', text=chinese_numbers[number],
                          font=('Arial', 14, 'bold'), fill=title_color,
                          tags=('board', tag))
        y += single_h

        # Bottom payout legend mirrors the reference's profit-only notation.
        footer_h = by + bh - y
        c.create_rectangle(bx, y, bx + bw, y + footer_h,
                           fill=gold_band, outline=border, width=1, tags='board')
        footer_texts = (
            ('出现 1 颗：1:1', bx + bw * 0.17),
            ('出现 2 颗：2:1', bx + bw * 0.50),
            ('出现 3 颗：3:1', bx + bw * 0.83),
        )
        for label, x in footer_texts:
            c.create_text(x, y + footer_h / 2,
                          text=label, font=('Arial', 10, 'bold'),
                          fill=gold_dark, tags='board')

    def draw_bottom_controls(self):
        c = self.canvas
        y0, y1 = 625, 748
        c.create_rectangle(0, y0, 1150, y1, fill='#17120f', outline='#665240', width=2, tags='controls')

        self.balance_text = c.create_text(10, 665, anchor='w', text='余额: $0.00',
                                          font=('Arial', 18, 'bold'), fill='white', tags=('dynamic', 'controls'))
        self.total_bet_text = c.create_text(10, 710, anchor='w', text='本局下注: $0.00',
                                            font=('Arial', 18, 'bold'), fill='white', tags=('dynamic', 'controls'))

        self.clear_button = self.create_control_button(
            300, 638, 410, 708, '清除下注', self.clear_bets, '#7c3b40', font_size=12
        )

        chip_x = 420
        for value, color, label in self.CHIP_SPECS:
            tag = f'chip_select_{value}'
            outer = c.create_oval(chip_x, 645, chip_x + 54, 699, fill='#292522',
                                  outline='#544b43', width=2, tags=(tag, 'chip_selector', 'controls'))
            inner = c.create_oval(chip_x + 5, 650, chip_x + 49, 694, fill=color,
                                  outline='#ddd', width=1, tags=(tag, 'chip_selector', 'controls'))
            text_color = 'white' if value in (5, 100, 500) else 'black'
            label_id = c.create_text(chip_x + 27, 672, text=label,
                                     font=('Arial', 10, 'bold'), fill=text_color,
                                     tags=(tag, 'chip_selector', 'controls'))
            c.tag_bind(tag, '<Button-1>', lambda _event, v=value: self.select_chip(v))
            self.chip_selector_items[value] = (outer, inner, label_id)
            chip_x += 57

        self.info_button = self.create_control_button(
            821, 650, 866, 695, '❓', self.show_help_window,
            '#315b72', fg='white', font_size=18
        )

        self.repeat_button = self.create_control_button(
            875, 638, 1005, 708, '重复下注', self.repeat_last_bets, '#5b4938', font_size=11
        )
        self.roll_button = self.create_control_button(
            1020, 628, 1135, 720, '转动', self.roll_dice, '#d5ad4d',
            fg='#111', font_size=14, subtext='ENTER', subtext_font_size=10
        )

        c.tag_raise('controls')
        c.tag_raise('chip_selector')
        self.update_control_states()

    def show_help_window(self):
        messagebox.showinfo(
            '超级骰宝玩法说明',
            '• 小：保险关闭时为 4–10；保险开启时为 3–10。\n'
            '• 大：保险关闭时为 11–17；保险开启时为 11–18。\n'
            '• 单 / 双：按总点数计算；保险关闭时任何围骰不中奖。\n'
            '• 保险模式：小、大、单、双遇围骰也可中奖，赔付改为 0.95:1；围骰类下注赔率不变。\n'
            '• 对子：指定点数至少出现两颗，基础赔付 8:1，金色最高 88:1。\n'
            '• 指定围骰：三颗指定点数相同，基础赔付 150:1，金色最高 999:1。\n'
            '• 任何围骰：任意三颗相同，基础赔付 30:1，金色最高 88:1。\n'
            '• 两骰组合：指定两种点数同时出现，基础赔付 5:1，金色最高 24:1。\n'
            '• 四数组合：三颗骰子必须互不重复，且全部属于所选四个点数，基础赔付 6:1，金色最高 39:1。\n'
            '• 三军：出现一颗、两颗、三颗时基础赔付 1:1、2:1、3:1。\n'
            '• 三军金色赔率：每个被选中的号码只增强“2颗”或“3颗”其中一种。\n'
            '• 若增强的是2颗，而实际出现3颗，则按增强2颗赔率与基础3:1中较高者结算。\n'
            '• 按下“转动”后，每局随机出现3–7个金色赔率，并以每格0.2秒渐变显示；抽取与下注及开奖结果无关。\n'
            '• 支持超级赔率的下注，长期理论 RTP 校准为 35/36（约 97.22%）。',
            parent=self.winfo_toplevel(),
        )

    @staticmethod
    def shade_color(color, factor):
        color = color.lstrip('#')
        if len(color) != 6:
            return '#555555'
        values = [int(color[index:index + 2], 16) for index in (0, 2, 4)]
        values = [max(0, min(255, int(value * factor))) for value in values]
        return '#' + ''.join(f'{value:02x}' for value in values)

    def create_control_button(self, x0, y0, x1, y1, text, command, fill,
                              fg='white', font_size=11, subtext=None,
                              subtext_font_size=10):
        tag = f'control_button_{len(self.control_buttons)}'
        shadow = self.canvas.create_rectangle(
            x0 + 5, y0 + 6, x1 + 5, y1 + 6,
            fill='#070605', outline='#070605', width=1, tags=(tag, 'controls')
        )
        rim = self.canvas.create_rectangle(
            x0, y0, x1, y1, fill=self.shade_color(fill, 0.55),
            outline='#b7a58d', width=2, tags=(tag, 'controls')
        )
        face = self.canvas.create_rectangle(
            x0 + 4, y0 + 4, x1 - 4, y1 - 4, fill=fill,
            outline=self.shade_color(fill, 1.25), width=2, tags=(tag, 'controls')
        )
        highlight = self.canvas.create_line(
            x0 + 8, y0 + 8, x1 - 8, y0 + 8,
            fill=self.shade_color(fill, 1.45), width=2, tags=(tag, 'controls')
        )
        center_y = (y0 + y1) / 2 - 1
        text_y = center_y - 12 if subtext else center_y
        text_id = self.canvas.create_text(
            (x0 + x1) / 2, text_y, text=text,
            font=('Arial', font_size, 'bold'), fill=fg, tags=(tag, 'controls')
        )
        subtext_id = None
        subtext_center_y = None
        if subtext:
            subtext_center_y = center_y + 16
            subtext_id = self.canvas.create_text(
                (x0 + x1) / 2, subtext_center_y, text=subtext,
                font=('Arial', subtext_font_size, 'bold'), fill=fg,
                tags=(tag, 'controls')
            )
        self.control_buttons[tag] = {
            'shadow': shadow,
            'rim': rim,
            'face': face,
            'highlight': highlight,
            'text': text_id,
            'subtext': subtext_id,
            'command': command,
            'fill': fill,
            'fg': fg,
            'enabled': True,
            'pressed': False,
            'center_y': text_y,
            'subtext_center_y': subtext_center_y,
        }

        def enter(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfig(button['face'], fill=self.shade_color(button['fill'], 1.12))

        def leave(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfig(button['face'], fill=button['fill'])

        def press(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled']:
                return
            button['pressed'] = True
            self.canvas.itemconfig(button['face'], fill=self.shade_color(button['fill'], 0.72))
            self.canvas.itemconfig(button['highlight'], fill=self.shade_color(button['fill'], 0.8))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'] + 2)
            if button.get('subtext'):
                sub_x, _sub_y = self.canvas.coords(button['subtext'])
                self.canvas.coords(
                    button['subtext'], sub_x, button['subtext_center_y'] + 2
                )

        def release(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled'] or not button['pressed']:
                return
            button['pressed'] = False
            self.canvas.itemconfig(button['face'], fill=button['fill'])
            self.canvas.itemconfig(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'])
            if button.get('subtext'):
                sub_x, _sub_y = self.canvas.coords(button['subtext'])
                self.canvas.coords(
                    button['subtext'], sub_x, button['subtext_center_y']
                )
            button['command']()

        self.canvas.tag_bind(tag, '<Enter>', enter)
        self.canvas.tag_bind(tag, '<Leave>', leave)
        self.canvas.tag_bind(tag, '<ButtonPress-1>', press)
        self.canvas.tag_bind(tag, '<ButtonRelease-1>', release)
        return tag

    def update_control_button_style(self, tag, text=None, fill=None, fg=None):
        button = self.control_buttons.get(tag)
        if not button:
            return
        if text is not None:
            self.canvas.itemconfigure(button['text'], text=text)
        if fill is not None:
            button['fill'] = fill
            self.canvas.itemconfigure(button['rim'], fill=self.shade_color(fill, 0.55))
            self.canvas.itemconfigure(button['face'], fill=fill)
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(fill, 1.45))
        if fg is not None:
            button['fg'] = fg
            self.canvas.itemconfigure(button['text'], fill=fg)
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill=fg)

    def set_control_button_state(self, tag, enabled):
        button = self.control_buttons.get(tag)
        if not button:
            return
        button['enabled'] = bool(enabled)
        button['pressed'] = False
        x, _y = self.canvas.coords(button['text'])
        self.canvas.coords(button['text'], x, button['center_y'])
        if button.get('subtext'):
            sub_x, _sub_y = self.canvas.coords(button['subtext'])
            self.canvas.coords(
                button['subtext'], sub_x, button['subtext_center_y']
            )
        if enabled:
            self.canvas.itemconfig(button['face'], fill=button['fill'])
            self.canvas.itemconfig(button['rim'], fill=self.shade_color(button['fill'], 0.55))
            self.canvas.itemconfig(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            self.canvas.itemconfig(button['text'], fill=button['fg'])
            if button.get('subtext'):
                self.canvas.itemconfig(button['subtext'], fill=button['fg'])
        else:
            self.canvas.itemconfig(button['face'], fill='#4a4743')
            self.canvas.itemconfig(button['rim'], fill='#262422')
            self.canvas.itemconfig(button['highlight'], fill='#66615b')
            self.canvas.itemconfig(button['text'], fill='#9b9690')
            if button.get('subtext'):
                self.canvas.itemconfig(button['subtext'], fill='#9b9690')

    def handle_enter_roll(self, _event=None):
        """Make Enter behave exactly like an enabled Roll button."""
        roll_tag = getattr(self, 'roll_button', None)
        button = self.control_buttons.get(roll_tag)
        if button and button['enabled']:
            button['command']()
        return 'break'

    def update_control_states(self):
        enabled = self.accept_bets and not self.animation_running and not self.settlement_running
        for name in ('repeat_button', 'clear_button', 'insurance_mode_button'):
            tag = getattr(self, name, None)
            if tag:
                self.set_control_button_state(tag, enabled)
        if getattr(self, 'roll_button', None):
            self.set_control_button_state(self.roll_button, enabled)

    # -------------------------------------------------------------- spot helpers
    @staticmethod
    def spot_tag(key):
        bet_type, param = key
        safe = 'none' if param is None else re.sub(r'[^0-9A-Za-z]+', '_', str(param))
        return f'betspot_{bet_type}_{safe}'

    def register_spot(self, bet_type, param, x0, y0, x1, y1, chip_pos, label):
        key = (bet_type, param)
        self.bet_spots[key] = {
            'bounds': (x0, y0, x1, y1),
            'chip_pos': chip_pos,
            'label': label,
            'tag': self.spot_tag(key),
        }

    @staticmethod
    def _secure_choice(values):
        values = tuple(values)
        return values[secrets.randbelow(len(values))]

    @staticmethod
    def _secure_unit():
        return secrets.randbits(53) / float(1 << 53)

    @classmethod
    def sample_fixed_pool_with_mean(cls, pool, target_mean):
        """Weighted draw from a fixed payout pool with a calibrated mean.

        The only possible outputs are the values explicitly listed in *pool*.
        An exponential tilt supplies stable positive weights while binary search
        chooses the tilt that makes the weighted average equal target_mean.
        This keeps the familiar/auspicious displayed odds without changing the
        long-run RTP calibration.
        """
        values = tuple(sorted({int(value) for value in pool}))
        if not values:
            raise ValueError('fixed payout pool must not be empty')
        if len(values) == 1:
            return values[0]

        minimum, maximum = values[0], values[-1]
        target_mean = max(float(minimum), min(float(maximum), float(target_mean)))
        if abs(target_mean - minimum) < 1e-12:
            return minimum
        if abs(target_mean - maximum) < 1e-12:
            return maximum

        cache_key = (values, round(target_mean, 12))
        cached = cls.FIXED_POOL_DISTRIBUTION_CACHE.get(cache_key)
        if cached is None:
            centre = (minimum + maximum) / 2.0

            def weights_and_mean(rate):
                logs = [rate * (value - centre) for value in values]
                peak = max(logs)
                weights = [math.exp(log_value - peak) for log_value in logs]
                total_weight = sum(weights)
                mean = sum(value * weight for value, weight in zip(values, weights)) / total_weight
                return weights, total_weight, mean

            low_rate, high_rate = -20.0, 20.0
            for _ in range(90):
                rate = (low_rate + high_rate) / 2.0
                _weights, _total, mean = weights_and_mean(rate)
                if mean < target_mean:
                    low_rate = rate
                else:
                    high_rate = rate

            weights, total_weight, _mean = weights_and_mean((low_rate + high_rate) / 2.0)
            cached = (values, tuple(weights), total_weight)
            cls.FIXED_POOL_DISTRIBUTION_CACHE[cache_key] = cached

        values, weights, total_weight = cached
        needle = cls._secure_unit() * total_weight
        cumulative = 0.0
        for value, weight in zip(values, weights):
            cumulative += weight
            if needle <= cumulative:
                return value
        return values[-1]

    @classmethod
    def fair_profit_odds(cls, win_combinations):
        probability = float(win_combinations) / 216.0
        return SicboEngine.TARGET_RTP / probability - 1.0

    @staticmethod
    def blend_color(first, second, ratio):
        """Blend two #RRGGBB colours; used for the 0.2-second gold fade."""
        ratio = max(0.0, min(1.0, float(ratio)))
        try:
            a = first.lstrip('#')
            b = second.lstrip('#')
            if len(a) != 6 or len(b) != 6:
                return second
            av = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
            bv = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
        except (AttributeError, ValueError):
            return second
        values = [round(x + (y - x) * ratio) for x, y in zip(av, bv)]
        return '#' + ''.join(f'{value:02x}' for value in values)

    def capture_spot_visuals(self):
        """Remember each betting cell's real background and any in-cell odds text.

        Super Sic Bo v6 changes the existing cell itself to gold.  This avoids a
        gold overlay covering dice/text and lets settlement restore losing gold
        cells exactly to their original appearance.
        """
        for key, spot in self.bet_spots.items():
            x0, y0, x1, y1 = spot['bounds']
            background_item = None
            background_error = float('inf')
            odds_text_item = None

            for item_id in self.canvas.find_withtag(spot['tag']):
                try:
                    item_type = self.canvas.type(item_id)
                    coords = self.canvas.coords(item_id)
                except tk.TclError:
                    continue

                if item_type == 'rectangle' and len(coords) == 4:
                    error = max(abs(a - b) for a, b in zip(coords, (x0, y0, x1, y1)))
                    if error < background_error:
                        background_error = error
                        background_item = item_id
                elif item_type == 'text':
                    text = self.canvas.itemcget(item_id, 'text')
                    if ':1' in text:
                        odds_text_item = item_id

            if background_item is not None:
                spot['background_item'] = background_item
                spot['original_fill'] = self.canvas.itemcget(background_item, 'fill')
                spot['original_outline'] = self.canvas.itemcget(background_item, 'outline')
                spot['original_width'] = self.canvas.itemcget(background_item, 'width')

            # Totals and four-number groups already carry a per-cell odds label.
            # Their gold value replaces that label directly; other categories use
            # a temporary compact odds band.
            if key[0] in ('total_points', 'number_group') and odds_text_item is not None:
                spot['odds_text_item'] = odds_text_item
                spot['odds_original_text'] = self.canvas.itemcget(odds_text_item, 'text')
                spot['odds_original_fill'] = self.canvas.itemcget(odds_text_item, 'fill')
            else:
                spot['odds_text_item'] = None
            spot['super_dynamic_items'] = []
            spot['super_shifted_items'] = {}

    @staticmethod
    def _secure_sample(values, count):
        values = list(values)
        count = max(0, min(int(count), len(values)))
        # Partial Fisher-Yates using secrets keeps the selection independent of bets.
        for index in range(count):
            swap_index = index + secrets.randbelow(len(values) - index)
            values[index], values[swap_index] = values[swap_index], values[index]
        return values[:count]

    @classmethod
    def all_super_eligible_keys(cls):
        keys = []
        keys.extend(('double', number) for number in range(1, 7))
        keys.extend(('triple', number) for number in range(1, 7))
        keys.append(('all_triples', None))
        keys.extend(('pairs', pair) for pair in SicboEngine.PAIRS)
        keys.extend(('guess_num', number) for number in range(1, 7))
        keys.extend(('total_points', point) for point in range(4, 18))
        keys.extend(('number_group', group) for group in SicboEngine.GROUPS)
        return keys

    def generate_super_odds(self):
        """Select 3-10 gold cells and draw only from fixed pretty payout pools.

        Cells are still sampled uniformly without replacement from all 52
        eligible locations.  For every category, weighted pool sampling is
        calibrated to the exact conditional mean required for ~97.22% RTP.
        Payout generation remains independent of wagers and dice results.
        """
        q = SicboEngine.SUPER_SELECTION_PROBABILITY
        count = SicboEngine.SUPER_MIN_COUNT + secrets.randbelow(
            SicboEngine.SUPER_MAX_COUNT - SicboEngine.SUPER_MIN_COUNT + 1
        )
        selected = self._secure_sample(self.all_super_eligible_keys(), count)
        odds = {}
        pools = SicboEngine.SUPER_PAYOUT_POOLS

        for key in selected:
            bet_type, param = key

            if bet_type == 'double':
                base = SicboEngine.DOUBLE_PAYOUT
                fair = self.fair_profit_odds(16)
                target = base + (fair - base) / q
                odds[key] = self.sample_fixed_pool_with_mean(pools['double'], target)

            elif bet_type == 'triple':
                base = SicboEngine.EXACT_TRIPLE_PAYOUT
                fair = self.fair_profit_odds(1)
                target = base + (fair - base) / q
                odds[key] = self.sample_fixed_pool_with_mean(pools['triple'], target)

            elif bet_type == 'all_triples':
                base = SicboEngine.ANY_TRIPLE_PAYOUT
                fair = self.fair_profit_odds(6)
                target = base + (fair - base) / q
                odds[key] = self.sample_fixed_pool_with_mean(pools['all_triples'], target)

            elif bet_type == 'pairs':
                base = SicboEngine.PAIR_PAYOUT
                fair = self.fair_profit_odds(30)
                target = base + (fair - base) / q
                odds[key] = self.sample_fixed_pool_with_mean(pools['pairs'], target)

            elif bet_type == 'total_points':
                point = int(param)
                base = SicboEngine.TOTAL_PAYOUT[point]
                fair = self.fair_profit_odds(SicboEngine.TOTAL_COMBINATIONS[point])
                target = base + (fair - base) / q
                odds[key] = self.sample_fixed_pool_with_mean(
                    SicboEngine.TOTAL_PAYOUT_POOLS[point], target
                )

            elif bet_type == 'number_group':
                # Four-number group: base 6:1, gold values come only from the
                # fixed 10/15/20/25/30/33/39 pool.  Mean 20:1 preserves RTP.
                base = SicboEngine.NUMBER_GROUP_PAYOUT
                fair = self.fair_profit_odds(24)
                target = base + (fair - base) / q
                odds[key] = self.sample_fixed_pool_with_mean(
                    pools['number_group'], target
                )

            elif bet_type == 'guess_num':
                # A selected 三军 cell enhances EITHER the 2-dice line OR the
                # 3-dice line.  The two modes remain 50/50.  If the 2-dice line
                # is enhanced and three matching dice appear, the same enhanced
                # payout applies because it is higher than the normal 3:1.
                mode = 2 if secrets.randbelow(2) == 0 else 3

                if mode == 2:
                    enhanced = self.sample_fixed_pool_with_mean(
                        pools['guess_num_2'],
                        12.0
                    )

                    odds[key] = {
                        'mode': 2,
                        2: enhanced,

                        # 如果开出3颗，而当前增强的是2颗，
                        # 继续按较高赔率结算。
                        3: max(
                            enhanced,
                            SicboEngine.SINGLE_NUMBER_PAYOUT[3]
                        ),
                    }

                else:
                    enhanced = self.sample_fixed_pool_with_mean(
                        pools['guess_num_3'],
                        72.8
                    )

                    odds[key] = {
                        'mode': 3,
                        3: enhanced,
                    }

        self.super_odds = odds
        return odds

    def super_odds_text(self, key, payout):
        """Return only the changed odds; v2 intentionally omits SUPER/Super text."""
        if key[0] == 'guess_num':
            mode = int(payout.get('mode', 2))
            return f"{mode}颗 {int(payout[mode])}:1"
        return f"{int(payout)}:1"

    def _reserve_super_label_space(self, key):
        """Move red dice only when needed so the odds band never covers them.

        v2 placed the temporary odds at y1-10.  In short red-dice cells that point
        lies directly on top of the lower die.  v4 reserves a compact bottom band
        and reflows only the dice images for pair/triple/single-number cells.
        """
        spot = self.bet_spots.get(key)
        if not spot or spot.get('super_shifted_items'):
            return
        bet_type = key[0]
        if bet_type not in ('pairs', 'triple', 'guess_num'):
            return

        x0, y0, x1, y1 = spot['bounds']
        images = []
        for item_id in self.canvas.find_withtag(spot['tag']):
            try:
                if self.canvas.type(item_id) != 'image':
                    continue
                coords = self.canvas.coords(item_id)
            except tk.TclError:
                continue
            if len(coords) == 2 and x0 - 1 <= coords[0] <= x1 + 1 and y0 - 1 <= coords[1] <= y1 + 1:
                images.append((item_id, coords))

        if not images:
            return
        original = {}
        if bet_type == 'pairs':
            images.sort(key=lambda row: row[1][1])
            target_ys = (y0 + 12.0, y0 + 36.5)
            for (item_id, coords), target_y in zip(images[:2], target_ys):
                original[item_id] = list(coords)
                self.canvas.coords(item_id, coords[0], target_y)
        elif bet_type == 'triple':
            target_y = y0 + 12.0
            for item_id, coords in images:
                original[item_id] = list(coords)
                self.canvas.coords(item_id, coords[0], target_y)
        elif bet_type == 'guess_num':
            # One die plus the Chinese number title; moving only the die upward is
            # enough to leave a clean 12px odds band at the bottom.
            for item_id, coords in images:
                original[item_id] = list(coords)
                self.canvas.coords(item_id, coords[0], y0 + 15.5)
        spot['super_shifted_items'] = original

    def _ensure_super_dynamic_label(self, key, ratio=1.0):
        spot = self.bet_spots.get(key)
        if not spot or spot.get('odds_text_item'):
            return None
        existing = spot.get('super_dynamic_items', [])
        if existing:
            return existing

        self._reserve_super_label_space(key)
        x0, y0, x1, y1 = spot['bounds']
        band_height = 12 if key[0] in ('pairs', 'triple', 'guess_num') else 14
        band_y0 = y1 - band_height
        band_fill = self.blend_color(spot['original_fill'], self.SUPER_LABEL_GOLD, ratio)
        band_id = self.canvas.create_rectangle(
            x0 + 1, band_y0, x1 - 1, y1 - 1,
            fill=band_fill, outline='',
            tags=(spot['tag'], 'super_multiplier', 'super_label_band'),
        )
        text_id = self.canvas.create_text(
            (x0 + x1) / 2, (band_y0 + y1) / 2 - 0.5,
            text=self.super_odds_text(key, self.super_odds[key]),
            font=('Arial', 8, 'bold'), fill='#3d2400',
            tags=(spot['tag'], 'super_multiplier', 'super_label'),
        )
        spot['super_dynamic_items'] = [band_id, text_id]
        return spot['super_dynamic_items']

    def apply_super_visual(self, key, ratio=1.0):
        spot = self.bet_spots.get(key)
        if not spot or 'background_item' not in spot:
            return
        ratio = max(0.0, min(1.0, float(ratio)))
        background = spot['background_item']
        fill = self.blend_color(spot['original_fill'], self.SUPER_GOLD, ratio)
        outline = self.blend_color(
            spot['original_outline'] or '#000000', self.SUPER_GOLD_OUTLINE, ratio
        )
        self.canvas.itemconfigure(background, fill=fill, outline=outline,
                                  width=3 if ratio >= 1.0 else 2)

        odds_item = spot.get('odds_text_item')
        label_color = self.blend_color(fill, '#3d2400', ratio)
        if odds_item:
            self.canvas.itemconfigure(
                odds_item,
                text=self.super_odds_text(key, self.super_odds[key]),
                fill=label_color,
            )
            self.canvas.tag_raise(odds_item)
        else:
            dynamic_items = self._ensure_super_dynamic_label(key, ratio)
            if dynamic_items:
                band_id, label_item = dynamic_items
                band_fill = self.blend_color(spot['original_fill'], self.SUPER_LABEL_GOLD, ratio)
                self.canvas.itemconfigure(band_id, fill=band_fill)
                self.canvas.itemconfigure(label_item, fill=label_color)

        # Preserve dice, titles and chips above the changed background, then place
        # the dedicated odds band/text at the very top so the number stays legible.
        for item_id in self.canvas.find_withtag(spot['tag']):
            try:
                if item_id != background:
                    self.canvas.tag_raise(item_id)
            except tk.TclError:
                pass
        for item_id in spot.get('super_dynamic_items', []):
            try:
                self.canvas.tag_raise(item_id)
            except tk.TclError:
                pass
        self.canvas.tag_raise('bet_chip_dynamic')
        self.canvas.tag_raise('controls')

    def restore_super_spot_visual(self, key):
        spot = self.bet_spots.get(key)
        if not spot:
            return
        background = spot.get('background_item')
        if background:
            try:
                self.canvas.itemconfigure(
                    background,
                    fill=spot.get('original_fill', ''),
                    outline=spot.get('original_outline', ''),
                    width=spot.get('original_width', 1),
                )
            except tk.TclError:
                pass

        odds_item = spot.get('odds_text_item')
        if odds_item:
            try:
                self.canvas.itemconfigure(
                    odds_item,
                    text=spot.get('odds_original_text', ''),
                    fill=spot.get('odds_original_fill', '#9f2b16'),
                )
            except tk.TclError:
                pass

        for item_id, coords in list(spot.get('super_shifted_items', {}).items()):
            try:
                self.canvas.coords(item_id, *coords)
            except tk.TclError:
                pass
        spot['super_shifted_items'] = {}

        for item_id in list(spot.get('super_dynamic_items', [])):
            try:
                self.canvas.delete(item_id)
            except tk.TclError:
                pass
        spot['super_dynamic_items'] = []

    def restore_all_super_visuals(self):
        for key in list(self.super_odds):
            self.restore_super_spot_visual(key)

    def start_super_odds_reveal(self):
        """Fade one selected cell to gold every 0.2 seconds."""
        if self.super_reveal_after_id is not None:
            try:
                self.after_cancel(self.super_reveal_after_id)
            except (tk.TclError, ValueError):
                pass
            self.super_reveal_after_id = None

        self.restore_all_super_visuals()
        self.super_reveal_order = self._secure_sample(
            list(self.super_odds.keys()), len(self.super_odds)
        )
        self.super_reveal_index = 0
        self.super_reveal_step = 0
        self.super_reveal_active = bool(self.super_reveal_order)
        if self.super_reveal_active:
            self._advance_super_reveal()

    def _advance_super_reveal(self):
        if self._closing or not self.super_reveal_active:
            self.super_reveal_after_id = None
            return
        if self.super_reveal_index >= len(self.super_reveal_order):
            self.super_reveal_active = False
            self.super_reveal_after_id = None
            return

        key = self.super_reveal_order[self.super_reveal_index]
        # Five visual states over 0.20 s: 20%, 40%, 60%, 80%, 100%.
        ratio = (self.super_reveal_step + 1) / 5.0
        self.apply_super_visual(key, ratio)
        if self.super_reveal_step < 4:
            self.super_reveal_step += 1
            self.super_reveal_after_id = self.after(50, self._advance_super_reveal)
        else:
            self.super_reveal_index += 1
            self.super_reveal_step = 0
            if self.super_reveal_index >= len(self.super_reveal_order):
                self.super_reveal_active = False
                self.super_reveal_after_id = None
            else:
                self.super_reveal_after_id = self.after(0, self._advance_super_reveal)

    def super_hit_keys_for_result(self, result):
        dice = [int(value) for value in result['dice']]
        total = int(result['total'])
        is_triple = bool(result['is_triple'])
        hits = set()
        for key, payout in self.super_odds.items():
            bet_type, param = key
            hit = False
            if bet_type == 'double':
                hit = dice.count(int(param)) >= 2
            elif bet_type == 'triple':
                hit = dice.count(int(param)) == 3
            elif bet_type == 'all_triples':
                hit = is_triple
            elif bet_type == 'pairs':
                first, second = (int(value) for value in str(param).split('&'))
                hit = first in dice and second in dice
            elif bet_type == 'total_points':
                hit = total == int(param)
            elif bet_type == 'guess_num':
                count = dice.count(int(param))
                mode = int(payout.get('mode', 0))
                hit = (count >= 2) if mode == 2 else (count == 3)
            elif bet_type == 'number_group':
                group_set = {int(value) for value in str(param)}
                hit = len(set(dice)) == 3 and set(dice).issubset(group_set)
            if hit:
                hits.add(key)
        return hits

    def prepare_super_settlement_visuals(self, result):
        """Restore non-hit gold cells; keep hit gold cells gold with black borders."""
        self.super_hit_keys = self.super_hit_keys_for_result(result)
        for key in self.super_odds:
            if key not in self.super_hit_keys:
                self.restore_super_spot_visual(key)
                continue
            spot = self.bet_spots.get(key)
            if not spot:
                continue
            background = spot.get('background_item')
            if background:
                self.canvas.itemconfigure(
                    background,
                    fill=self.SUPER_GOLD,
                    outline=self.SUPER_FLASH_OUTLINE,
                    width=spot.get('original_width', 1),
                )

    # --------------------------------------------------------------- bet actions
    def select_chip(self, amount):
        self.selected_chip = float(amount)
        for value, items in self.chip_selector_items.items():
            outer, _inner, _text = items
            selected = value == amount
            self.canvas.itemconfigure(outer,
                                      outline='#ffda42' if selected else '#544b43',
                                      width=4 if selected else 2)
        self.canvas.tag_raise('chip_selector')

    def select_multiplier(self, multiplier):
        self.multiplier = 1

    def place_bet(self, bet_type, param=None, amount=None, record_undo=True):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return False
        requested = float(amount if amount is not None else self.selected_chip * self.multiplier)
        if requested < self.MIN_BET:
            return False

        area_current = self.engine.current_area_bet(bet_type, param)
        table_current = self.engine.total_at_risk()
        allowed = min(
            requested,
            self.MAX_AREA_BET - area_current,
            self.MAX_TABLE_BET - table_current,
            self.balance,
        )
        if allowed <= 0:
            return False
        if allowed < requested:
            messagebox.showwarning('下注限制', f'下注已自动调整为 ${allowed:,.2f}。', parent=self.winfo_toplevel())

        self.engine.add_bet(bet_type, allowed, param)
        self.balance -= allowed
        if record_undo:
            self.undo_stack.append((bet_type, param, allowed))
        self.summary_mode = 'bet'
        self.update_display()
        self.save_balance()
        return True

    def clear_single_bet(self, bet_type, param=None):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.engine.clear_area(bet_type, param)
        if refunded <= 0:
            return
        self.balance += refunded
        self.undo_stack = [item for item in self.undo_stack if item[:2] != (bet_type, param)]
        self.update_display()
        self.save_balance()

    def undo_last_bet(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        while self.undo_stack:
            bet_type, param, amount = self.undo_stack.pop()
            removed = self.engine.remove_amount(bet_type, amount, param)
            if removed > 0:
                self.balance += removed
                self.update_display()
                self.save_balance()
                return

    def clear_bets(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.engine.total_at_risk()
        if refunded <= 0:
            return
        self.balance += refunded
        self.engine.bets = self.engine.new_bets()
        self.undo_stack.clear()
        self.update_display()
        self.save_balance()

    def repeat_last_bets(self):
        if not self.accept_bets or self.animation_running or self.settlement_running or not self.last_round_bets:
            return

        required_balance = sum(float(amount) for _bet_type, _param, amount in self.last_round_bets)
        if self.balance + 1e-9 < required_balance:
            messagebox.showwarning(
                '余额不足',
                f'重复上局下注需要 {self.format_money(required_balance)}，'
                f'当前余额为 {self.format_money(self.balance)}。',
                parent=self.winfo_toplevel(),
            )
            return

        for bet_type, param, amount in self.last_round_bets:
            self.place_bet(bet_type, param, amount=amount, record_undo=True)

    def toggle_triple_mode(self):
        if self.animation_running or self.settlement_running:
            return
        self.triple_mode = not self.triple_mode
        label = '保险~开' if self.triple_mode else '保险~关'
        fill = '#287c4b' if self.triple_mode else '#77383b'
        self.update_control_button_style(
            self.insurance_mode_button, text=label, fill=fill, fg='white'
        )
        payout_label = ('0.95:1｜围骰赔付'
                        if self.triple_mode else '1:1｜围骰通杀')
        for item_id in getattr(self, 'basic_payout_text_items', []):
            self.canvas.itemconfigure(item_id, text=payout_label)
        if hasattr(self, 'small_range_text'):
            self.canvas.itemconfigure(
                self.small_range_text, text='3–10' if self.triple_mode else '4–10'
            )
        if hasattr(self, 'big_range_text'):
            self.canvas.itemconfigure(
                self.big_range_text, text='11–18' if self.triple_mode else '11–17'
            )

    # ------------------------------------------------------------ display update
    @staticmethod
    def format_money(value):
        if abs(value - round(value)) < 0.005:
            return f'${value:,.0f}'
        return f'${value:,.2f}'

    def update_display(self):
        self.canvas.itemconfigure(
            self.balance_text, text=f'余额: {self.format_money(self.balance)}'
        )
        if self.summary_mode == 'win':
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'上局获胜: {self.format_money(self.last_win_amount)}'
            )
        else:
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'本局下注: {self.format_money(self.engine.total_at_risk())}'
            )
        self.update_bet_chips()
        self.update_history_table()
        self.update_last_triple_display()
        self.update_control_states()

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        for key, spot in self.bet_spots.items():
            amount = self.engine.current_area_bet(*key)
            if key in self.flash_winner_amounts:
                if self.flash_mode == 'win':
                    amount = self.flash_winner_amounts[key]
                elif self.flash_mode == 'original':
                    amount = self.flash_original_amounts.get(key, amount)
            if amount <= 0:
                continue
            x, chip_y = spot['chip_pos']
            x0, y0, x1, y1 = spot['bounds']

            # All table chips use one compact minimum size and remain centered
            # in their registered betting cells.
            radius = 14
            x = max(x0 + radius + 1, min(x1 - radius - 1, x))
            chip_y = max(y0 + radius + 1, min(y1 - radius - 1, chip_y))
            chip_color = self.bet_chip_color(amount)
            text_color = self.contrast_text_color(chip_color)

            self.canvas.create_oval(
                x - radius, chip_y - radius, x + radius, chip_y + radius,
                fill='#292522', outline='#151311', width=1,
                tags=('bet_chip_dynamic', spot['tag'])
            )
            inner_radius = radius - 3
            self.canvas.create_oval(
                x - inner_radius, chip_y - inner_radius,
                x + inner_radius, chip_y + inner_radius,
                fill=chip_color, outline='#e2ddd5', width=1,
                tags=('bet_chip_dynamic', spot['tag'])
            )
            text = self._compact_amount(amount)
            self.canvas.create_text(
                x, chip_y, text=text, font=('Arial', 8, 'bold'),
                fill=text_color, tags=('bet_chip_dynamic', spot['tag'])
            )

    @classmethod
    def bet_chip_color(cls, amount):
        """Use the same denomination colors as the bottom chip selector."""
        selected_color = cls.CHIP_SPECS[0][1]
        for threshold, color, _label in cls.CHIP_SPECS:
            if amount >= threshold:
                selected_color = color
            else:
                break
        return selected_color

    @staticmethod
    def contrast_text_color(color):
        value = color.lstrip('#')
        if len(value) != 6:
            return 'black'
        red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))
        luminance = 0.299 * red + 0.587 * green + 0.114 * blue
        return 'black' if luminance >= 150 else 'white'

    @staticmethod
    def _compact_amount(amount):
        if amount >= 1000:
            value = amount / 1000
            return f'{value:.0f}K' if abs(value - round(value)) < 0.01 else f'{value:.1f}K'
        if abs(amount - round(amount)) < 0.01:
            return str(int(round(amount)))
        return f'{amount:.1f}'

    # ------------------------------------------------------------ roll/animation
    def roll_dice(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        self.accept_bets = False
        self.animation_running = True

        # v6: the dice clock starts at the button press.  Gold-cell generation and
        # the 0.2-second reveal animation run concurrently inside this same window.
        self.animation_started_at = time.monotonic()
        self.animation_duration_ms = 2400 + secrets.randbelow(601)

        current_round_bets = self.snapshot_bets()
        if current_round_bets:
            self.last_round_bets = current_round_bets
        self.undo_stack.clear()

        # Generation never inspects bets or dice, preserving the RTP calculation.
        self.generate_super_odds()
        self.start_super_odds_reveal()

        if self.developer_dice:
            final_dice = list(self.developer_dice)
            self.developer_dice = None
        else:
            final_dice = [die.roll() for die in self.dice_objects]
        self.animation_final_dice = final_dice
        self.canvas.itemconfigure(self.animation_phase_text, text='骰子摇动中…')
        self.canvas.itemconfigure(self.animation_status_text, text='请停止下注', state='normal')
        for item in self.animation_result_dice_items:
            self.canvas.itemconfigure(item, state='hidden')
        for item in self.animation_result_plus_items:
            self.canvas.itemconfigure(item, state='hidden')
        self.canvas.itemconfigure(self.animation_result_suffix, state='hidden')
        self.update_control_states()
        self.animate_dice()

    def animate_dice(self):
        if self._closing:
            return
        elapsed_ms = (time.monotonic() - self.animation_started_at) * 1000.0
        remaining_ms = self.animation_duration_ms - elapsed_ms
        if remaining_ms > 0:
            current = [secrets.randbelow(6) + 1 for _ in range(3)]
            for index, (item, value) in enumerate(zip(self.animation_dice_items, current)):
                base_x, base_y = self.animation_dice_base_positions[index]
                shake_x = secrets.randbelow(31) - 15
                shake_y = secrets.randbelow(31) - 15
                self.canvas.coords(item, base_x + shake_x, base_y + shake_y)
                self.canvas.itemconfigure(
                    item,
                    image=self.dice_images_animation[value - 1],
                    state='normal',
                )
            delay = 45 if remaining_ms > 700 else 70
            self.animation_after_id = self.after(
                max(1, min(delay, int(remaining_ms))), self.animate_dice
            )
            return

        # The final dice are exposed according to the timer that began at Roll, not
        # according to when the last gold cell appeared.  The maximum 10-cell gold
        # reveal is ~2.0s, while the dice timer is 2.4-3.0s.
        for index, (item, value) in enumerate(zip(self.animation_dice_items, self.animation_final_dice)):
            base_x, base_y = self.animation_dice_base_positions[index]
            self.canvas.coords(item, base_x, base_y)
            self.canvas.itemconfigure(
                item,
                image=self.dice_images_animation[value - 1],
                state='normal',
            )
        self.animation_after_id = self.after(250, self.finish_roll)

    def finish_roll(self):
        # Under normal timing all gold cells are already fully revealed.  If the UI
        # event loop was unusually delayed, keep the final dice visible and wait only
        # for settlement; do not restart or extend the dice-shaking animation.
        if self.super_reveal_active:
            self.animation_after_id = self.after(25, self.finish_roll)
            return

        # Preserve the exact pre-roll stakes so the winning chip can alternate
        # between the original bet and the total returned amount, as in Craps.
        self.pre_roll_bets = copy.deepcopy(self.engine.bets)
        result = self.engine.resolve_roll(
            self.animation_final_dice, self.triple_mode, self.super_odds
        )
        self.balance += result['credit']
        self.last_win_amount = result['credit']
        self.last_net = result['net']
        self.add_history(result)

        # Every objectively winning betting area flashes, even if no chip was placed.
        self.flash_winning_keys = self.winning_keys_for_result(result)
        # v6 settlement visual: non-hit gold cells immediately revert to their
        # original background/label; only actually enhanced winners stay gold.
        # During flashing, enhanced winners alternate GOLD <-> WHITE settlement.
        # A 三军 cell that only wins its base 1:1/2:1 line but misses its selected
        # enhanced 2颗/3颗 condition is therefore treated as a normal winner.
        self.prepare_super_settlement_visuals(result)
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        for outcome in result.get('outcomes', []):
            if outcome.get('status') != 'win' or not outcome.get('key'):
                continue
            key = tuple(outcome['key'])
            self.flash_winner_amounts[key] = (
                self.flash_winner_amounts.get(key, 0.0)
                + float(outcome.get('return_amount', 0.0))
            )
            self.flash_original_amounts[key] = self.snapshot_bet_amount(
                self.pre_roll_bets, key
            )

        # Sic Bo wagers are one-roll bets. Clear the live table immediately;
        # the flash layer below temporarily renders winning original/return chips.
        self.engine.bets = self.engine.new_bets()
        self.summary_mode = 'win'
        sorted_dice = sorted(result['dice'])
        if result['is_triple']:
            result_suffix = f"= {result['total']}点，围骰"
        else:
            size_text = '大' if result['total'] >= 11 else '小'
            parity_text = '双' if result['total'] % 2 == 0 else '单'
            result_suffix = f"= {result['total']}点{size_text}，{parity_text}"

        self.canvas.itemconfigure(self.animation_phase_text, text='本局结果')
        self.canvas.itemconfigure(
            self.animation_status_bubble,
            fill=self._darken_result_color(result['result_color']),
            outline=result['result_color'],
        )
        self.canvas.itemconfigure(self.animation_status_text, state='hidden')
        for item, value in zip(self.animation_result_dice_items, sorted_dice):
            self.canvas.itemconfigure(item, image=self.dice_images_history[int(value) - 1], state='normal')
        for item in self.animation_result_plus_items:
            self.canvas.itemconfigure(item, fill='white', state='normal')
        self.canvas.itemconfigure(
            self.animation_result_suffix,
            text=result_suffix,
            fill=result['result_color'],
            state='normal',
        )

        self.animation_after_id = None
        self.accept_bets = False
        self.settlement_running = True
        self.flash_mode = None
        self.update_display()
        self.save_balance()

        if self.flash_winning_keys:
            self.settlement_flash_step = 0
            self.run_settlement_flash()
        else:
            self.result_after_id = self.after(1600, self.finish_settlement)

    def winning_keys_for_result(self, result):
        """Return every table area that wins for this roll, independent of wagers."""
        dice = [int(value) for value in result['dice']]
        total = int(result['total'])
        is_triple = bool(result['is_triple'])
        keys = set()

        if self.triple_mode:
            if 3 <= total <= 10:
                keys.add(('small', None))
            if 11 <= total <= 18:
                keys.add(('big', None))
            keys.add(('even' if total % 2 == 0 else 'odd', None))
        elif not is_triple:
            if 4 <= total <= 10:
                keys.add(('small', None))
            if 11 <= total <= 17:
                keys.add(('big', None))
            keys.add(('even' if total % 2 == 0 else 'odd', None))

        if is_triple:
            keys.add(('all_triples', None))
            keys.add(('triple', dice[0]))

        for number in range(1, 7):
            count = dice.count(number)
            if count >= 2:
                keys.add(('double', number))
            if count >= 1:
                keys.add(('guess_num', number))

        if 4 <= total <= 17:
            keys.add(('total_points', total))

        for pair in SicboEngine.PAIRS:
            first, second = (int(value) for value in pair.split('&'))
            if first in dice and second in dice:
                keys.add(('pairs', pair))

        unique_dice = set(dice)
        if len(unique_dice) == 3:
            for group in SicboEngine.GROUPS:
                if unique_dice.issubset({int(value) for value in group}):
                    keys.add(('number_group', group))

        return keys

    def snapshot_bet_amount(self, bets, key):
        if not bets:
            return 0.0
        bet_type, param = key
        value = bets.get(bet_type, 0.0)
        if isinstance(value, dict):
            return float(value.get(param, 0.0))
        return float(value)

    def run_settlement_flash(self):
        """Alternate winners between their table state and a white settlement state.

        Normal winners flash ORIGINAL <-> WHITE.  A winner that actually hit its
        selected Super condition flashes GOLD <-> WHITE.  The white settlement
        state deliberately keeps the current in-cell layout above the white layer:
        shifted dice, the enhanced odds text, and the returned winning chip (if a
        wager was placed).
        """
        if self._closing or not self.settlement_running:
            return
        if self.settlement_flash_step >= 6:
            self.finish_settlement()
            return

        # 'win' is the white settlement phase.  update_bet_chips() also uses this
        # phase to show the returned/winning chip amount.  'original' exposes the
        # underlying table state: normal cells are normal; true Super hits remain
        # gold with their black outline from prepare_super_settlement_visuals().
        self.flash_mode = 'win' if self.settlement_flash_step % 2 == 0 else 'original'
        self.canvas.delete('win_flash_area')

        if self.flash_mode == 'original':
            self.restore_flash_text_colors()

        if self.flash_mode == 'win':
            for key in self.flash_winning_keys:
                spot = self.bet_spots.get(key)
                if not spot:
                    continue
                x0, y0, x1, y1 = spot['bounds']
                # White is always the settlement frame, including for genuine
                # Super winners.  When this rectangle disappears on the next
                # phase, a true Super hit reveals its preserved gold background;
                # a base-only 三军 win reveals the restored normal background.
                self.canvas.create_rectangle(
                    x0, y0, x1, y1,
                    fill='#ffffff',
                    outline='#111111',
                    width=2,
                    tags=('win_flash_area', 'settlement_flash'),
                )
                self.raise_spot_content_above_flash(spot)

        # Enhanced odds stay visible in the white settlement frame.  The gold
        # label band itself remains below the white rectangle, so only the odds
        # text appears over white; shifted dice are raised by the helper above.
        self.canvas.tag_raise('super_label')
        self.update_bet_chips()
        self.canvas.tag_raise('bet_chip_dynamic')
        self.canvas.tag_raise('controls')
        if getattr(self, 'insurance_mode_button', None):
            self.canvas.tag_raise(self.insurance_mode_button)

        self.settlement_flash_step += 1
        self.settlement_after_id = self.after(1000, self.run_settlement_flash)

    def raise_spot_content_above_flash(self, spot):
        """Keep a cell's dice/text visible over the white flash layer."""
        tag = spot.get('tag')
        if not tag:
            return
        for item_id in self.canvas.find_withtag(tag):
            try:
                item_type = self.canvas.type(item_id)
                item_tags = self.canvas.gettags(item_id)
            except tk.TclError:
                continue
            if 'win_flash_area' in item_tags or 'bet_chip_dynamic' in item_tags:
                continue
            if item_type == 'text':
                if item_id not in self.flash_original_text_colors:
                    self.flash_original_text_colors[item_id] = self.canvas.itemcget(item_id, 'fill')
                self.canvas.itemconfigure(item_id, fill='black')
                self.canvas.tag_raise(item_id)
            elif item_type == 'image':
                self.canvas.tag_raise(item_id)

    def restore_flash_text_colors(self):
        for item_id, original_color in list(self.flash_original_text_colors.items()):
            try:
                self.canvas.itemconfigure(item_id, fill=original_color)
            except tk.TclError:
                pass
        self.flash_original_text_colors.clear()

    def finish_settlement(self):
        if self._closing:
            return
        if self.settlement_after_id is not None:
            self.settlement_after_id = None
        if self.result_after_id is not None:
            self.result_after_id = None
        self.canvas.delete('win_flash_area')
        self.restore_all_super_visuals()
        self.canvas.delete('super_multiplier')
        self.super_odds = {}
        self.super_hit_keys = set()
        self.restore_flash_text_colors()
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.pre_roll_bets = None
        self.settlement_running = False
        self.animation_running = False
        self.accept_bets = True
        self.canvas.itemconfigure(self.animation_phase_text, text='超级骰宝')
        self.canvas.itemconfigure(
            self.animation_status_bubble, fill='#0b2723', outline='#c8efe7'
        )
        self.canvas.itemconfigure(
            self.animation_status_text,
            text='选择筹码并点击下注区域，然后按“转动”', fill='white', state='normal'
        )
        for item in self.animation_result_dice_items:
            self.canvas.itemconfigure(item, state='hidden')
        for item in self.animation_result_plus_items:
            self.canvas.itemconfigure(item, state='hidden')
        self.canvas.itemconfigure(self.animation_result_suffix, state='hidden')
        self.update_display()

    def ready_next_round(self):
        # Retained for compatibility with older callbacks.
        self.finish_settlement()

    @staticmethod
    def _darken_result_color(color):
        return {
            BubbleSicboGame.BIG_RED: '#4f2022',
            BubbleSicboGame.TRIPLE_GREEN: '#204e2c',
            BubbleSicboGame.SMALL_YELLOW: '#50491f',
        }.get(color, '#0b2723')

    @staticmethod
    def format_signed(value):
        sign = '+' if value >= 0 else '-'
        return f'{sign}${abs(value):,.2f}'

    def snapshot_bets(self):
        result = []
        for bet_type, value in self.engine.bets.items():
            if isinstance(value, dict):
                for param, amount in value.items():
                    if amount > 0:
                        result.append((bet_type, param, float(amount)))
            elif value > 0:
                result.append((bet_type, None, float(value)))
        return result

    # ------------------------------------------------------------------ history
    def get_history_file(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        logs_dir = os.path.join(project_root, 'A_Logs', 'Json')
        try:
            os.makedirs(logs_dir, exist_ok=True)
        except OSError:
            # Fallback keeps the game usable if the project parent is read-only.
            logs_dir = os.path.join(current_dir, 'A_Logs', 'Json')
            os.makedirs(logs_dir, exist_ok=True)
        return os.path.join(logs_dir, 'Sicbo.json')

    @classmethod
    def new_history_store(cls):
        store = {
            '500_Record': {
                f'{index:02d}_Data': []
                for index in range(1, cls.MAX_RECORDS + 1)
            },
            'Last_Triple': [0, 0],
            'H_Small': 0,
            'H_Triple': 0,
            'H_Big': 0,
        }
        for total in range(4, 18):
            store[f'H_{total}'] = 0
        for number in range(1, 7):
            store[f'H_T{number}'] = 0
        return store

    @classmethod
    def normalize_history_store(cls, data):
        """Return the exact 500_Record/statistics structure used by Sicbo.json."""
        normalized = cls.new_history_store()
        if not isinstance(data, dict):
            return normalized

        source_block = data.get('500_Record', {})
        if isinstance(source_block, dict):
            for index in range(1, cls.MAX_RECORDS + 1):
                key = f'{index:02d}_Data'
                dice = source_block.get(key, [])
                if not isinstance(dice, list) or len(dice) != 3:
                    continue
                try:
                    values = sorted(int(value) for value in dice)
                except (TypeError, ValueError):
                    continue
                if all(1 <= value <= 6 for value in values):
                    normalized['500_Record'][key] = values

        last_triple = data.get('Last_Triple', [0, 0])
        if isinstance(last_triple, list) and len(last_triple) >= 2:
            try:
                triple_value = int(last_triple[0])
                rounds_ago = max(0, int(last_triple[1]))
            except (TypeError, ValueError):
                triple_value, rounds_ago = 0, 0
            if 1 <= triple_value <= 6:
                normalized['Last_Triple'] = [triple_value, rounds_ago]

        counter_keys = ['H_Small', 'H_Triple', 'H_Big']
        counter_keys.extend(f'H_{total}' for total in range(4, 18))
        counter_keys.extend(f'H_T{number}' for number in range(1, 7))
        for key in counter_keys:
            try:
                normalized[key] = max(0, int(data.get(key, 0)))
            except (TypeError, ValueError):
                normalized[key] = 0

        return normalized

    def history_records_from_store(self):
        """Convert 01_Data..500_Data into records used by the current Canvas UI."""
        records = []
        block = self.history_store.get('500_Record', {})
        for index in range(1, self.MAX_RECORDS + 1):
            dice = block.get(f'{index:02d}_Data', [])
            if not isinstance(dice, list) or len(dice) != 3:
                continue
            try:
                values = sorted(int(value) for value in dice)
            except (TypeError, ValueError):
                continue
            if not all(1 <= value <= 6 for value in values):
                continue
            total = sum(values)
            description, color = self.result_description(values)
            records.append({
                'time': '',
                'dice': values,
                'total': total,
                'description': description,
                'color': color,
                'net': 0.0,
            })
        return records

    def load_history_data(self):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as handle:
                raw_data = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            raw_data = self.new_history_store()

        self.history_store = self.normalize_history_store(raw_data)
        # Write a normalized file if it was absent, damaged or used invalid values.
        self.save_history_store()
        return self.history_records_from_store()

    def save_history_store(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as handle:
                json.dump(self.history_store, handle, ensure_ascii=False, indent=4)
        except OSError as exc:
            print(f'保存 Sicbo 历史记录失败：{exc}')

    def add_history(self, result):
        """Insert the latest roll and update all counters in Sicbo.json."""
        try:
            dice = sorted(int(value) for value in result['dice'])
        except (KeyError, TypeError, ValueError):
            return
        if len(dice) != 3 or not all(1 <= value <= 6 for value in dice):
            return

        block = self.history_store.setdefault(
            '500_Record',
            {f'{index:02d}_Data': [] for index in range(1, self.MAX_RECORDS + 1)}
        )
        for index in range(self.MAX_RECORDS, 1, -1):
            current_key = f'{index:02d}_Data'
            previous_key = f'{index - 1:02d}_Data'
            block[current_key] = list(block.get(previous_key, []))
        block['01_Data'] = dice

        total = sum(dice)
        is_triple = dice[0] == dice[1] == dice[2]

        if is_triple:
            triple_value = dice[0]
            self.history_store['H_Triple'] = int(self.history_store.get('H_Triple', 0)) + 1
            triple_key = f'H_T{triple_value}'
            self.history_store[triple_key] = int(self.history_store.get(triple_key, 0)) + 1
            self.history_store['Last_Triple'] = [triple_value, 0]
        else:
            size_key = 'H_Small' if total <= 10 else 'H_Big'
            self.history_store[size_key] = int(self.history_store.get(size_key, 0)) + 1
            total_key = f'H_{total}'
            if 4 <= total <= 17:
                self.history_store[total_key] = int(self.history_store.get(total_key, 0)) + 1

            last_triple = self.history_store.get('Last_Triple', [0, 0])
            try:
                triple_value = int(last_triple[0])
                rounds_ago = max(0, int(last_triple[1]))
            except (TypeError, ValueError, IndexError):
                triple_value, rounds_ago = 0, 0
            if 1 <= triple_value <= 6:
                self.history_store['Last_Triple'] = [triple_value, rounds_ago + 1]

        self.save_history_store()
        self.history_data = self.history_records_from_store()

    @staticmethod
    def result_description(dice):
        total = sum(dice)
        if dice[0] == dice[1] == dice[2]:
            return '围骰', BubbleSicboGame.TRIPLE_GREEN
        size = '大' if total >= 11 else '小'
        parity = '单' if total % 2 else '双'
        color = BubbleSicboGame.BIG_RED if size == '大' else BubbleSicboGame.SMALL_YELLOW
        return f'{size} & {parity}', color

    def update_history_table(self):
        self.canvas.delete('history_dynamic')
        if self.history_panel_mode == 'statistics':
            self.draw_history_statistics()
            return
        geometry = self.history_panel_geometry
        row_height = geometry['row_height']
        for index, record in enumerate(self.history_data[:15]):
            dice = record.get('dice', [])
            if len(dice) != 3:
                continue
            y = geometry['header_bottom'] + (index + 0.5) * row_height
            total = int(record.get('total', sum(dice)))

            # Triple history rows use green behind the three dice.
            try:
                dice_values = [int(value) for value in dice]
            except (TypeError, ValueError):
                dice_values = []
            is_triple = (
                len(dice_values) == 3
                and dice_values[0] == dice_values[1] == dice_values[2]
            )

            if is_triple:
                dice_bg = self.TRIPLE_GREEN
            elif total >= 11:
                dice_bg = self.BIG_RED
            else:
                dice_bg = self.SMALL_YELLOW

            row_top = y - row_height / 2 + 1
            row_bottom = y + row_height / 2 - 1
            self.canvas.create_rectangle(
                geometry['x0'] + 1, row_top, geometry['col1'] - 1, row_bottom,
                fill=dice_bg, outline='', tags='history_dynamic'
            )

            dice_left = geometry['x0'] + 18
            centres = (dice_left + 12, dice_left + 50, dice_left + 88)
            for die_index, (x, value) in enumerate(zip(centres, dice)):
                self.canvas.create_image(
                    x, y, image=self.dice_images_history[int(value) - 1],
                    tags='history_dynamic'
                )
                if die_index < 2:
                    self.canvas.create_text(
                        x + 19, y, text='+', font=('Arial', 10, 'bold'),
                        fill='black', tags='history_dynamic'
                    )

            description = record.get('description')
            color = record.get('color')
            if not description or not color:
                description, color = self.result_description(dice)
            self.canvas.create_text(
                (geometry['col1'] + geometry['col2']) / 2, y,
                text=str(total), font=('Arial', 12, 'bold'),
                fill=color, tags='history_dynamic'
            )
            self.canvas.create_text(
                (geometry['col2'] + geometry['x1']) / 2, y,
                text=description, font=('Arial', 10, 'bold'),
                fill=color, tags='history_dynamic'
            )

    # ----------------------------------------------------------- developer mode
    def arm_developer_mode(self):
        self._developer_armed = True

    def open_developer_after_arm(self):
        if getattr(self, '_developer_armed', False):
            self._developer_armed = False
            self.show_developer_input_dialog()

    def show_developer_input_dialog(self):
        win = tk.Toplevel(self.winfo_toplevel())
        win.title('固定三颗骰子')
        win.geometry('350x145')
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        tk.Label(win, text='输入三个 1–6 的数字；留空恢复随机：',
                 font=('Arial', 11)).pack(pady=(14, 5))
        entry = tk.Entry(win, font=('Arial', 16), justify=tk.CENTER)
        entry.pack(fill=tk.X, padx=28)
        entry.focus_set()

        def confirm():
            value = entry.get().strip()
            if not value:
                self.developer_dice = None
                win.destroy()
                return
            parts = re.split(r'[\s,;]+', value)
            try:
                dice = [int(item) for item in parts]
            except ValueError:
                messagebox.showwarning('输入错误', '请输入三个 1 到 6 的整数。', parent=win)
                return
            if len(dice) != 3 or not all(1 <= item <= 6 for item in dice):
                messagebox.showwarning('输入错误', '请输入三个 1 到 6 的整数。', parent=win)
                return
            self.developer_dice = dice
            win.destroy()

        tk.Button(win, text='确定', width=12, command=confirm).pack(pady=10)
        win.bind('<Return>', lambda _event: confirm())
        win.bind('<Escape>', lambda _event: win.destroy())

    # ---------------------------------------------------------------- lifecycle
    def save_balance(self):
        if self.username:
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def cancel_pending_callbacks(self):
        for after_id in (
            self.animation_after_id, self.result_after_id,
            self.flash_after_id, self.settlement_after_id,
            self.super_reveal_after_id,
        ):
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except (tk.TclError, ValueError):
                    pass
        self.animation_after_id = None
        self.result_after_id = None
        self.flash_after_id = None
        self.settlement_after_id = None
        self.super_reveal_after_id = None
        self.super_reveal_active = False

    def on_close(self):
        self.exit_game()

    def exit_game(self):
        if self._closing:
            return
        self._closing = True
        self.cancel_pending_callbacks()
        self.animation_running = False
        self.accept_bets = False

        outstanding = self.engine.total_at_risk()
        if outstanding > 0:
            self.balance += outstanding
        self.engine.bets = self.engine.new_bets()
        self.final_balance = float(self.balance)
        try:
            self.save_balance()
        except Exception:
            pass

        if callable(self.on_back):
            self.on_back(self.final_balance)


# Backward-compatible names used by the original Sicbo module.
SuperSicboGame = BubbleSicboGame


class SicboGame(BubbleSicboGame):
    def __init__(self, root, username=None, initial_balance=10000,
                 on_back=None, on_balance_change=None):
        super().__init__(
            parent=root,
            balance=initial_balance,
            user=username,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        self.pack(fill=tk.BOTH, expand=True)


def main(
    parent=None,
    balance=10000,
    user=None,
    on_back=None,
    on_balance_change=None,
    username=None,
):
    """Open Super Sic Bo as an embedded Frame or as an independent window.

    Embedded use:
        main(parent=root, balance=10000, user='name', on_back=callback)

    Independent use:
        main(balance=10000, user='name')

    Legacy calls such as main(10000, 'name') and main(balance=..., username=...)
    remain supported.
    """
    if username is not None and user is None:
        user = username

    if parent is not None and not isinstance(parent, tk.Misc):
        legacy_balance = parent
        legacy_user = balance if isinstance(balance, str) and user is None else user
        parent = None
        balance = legacy_balance
        user = legacy_user

    if parent is not None:
        return BubbleSicboGame(
            parent=parent,
            balance=balance,
            user=user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    root.title('超级骰宝')
    result = {'balance': float(balance)}

    def close_standalone(final_balance):
        result['balance'] = float(final_balance)
        try:
            root.destroy()
        except tk.TclError:
            pass

    game = BubbleSicboGame(
        parent=root,
        balance=balance,
        user=user,
        on_back=close_standalone,
        on_balance_change=on_balance_change,
    )
    game.pack(fill=tk.BOTH, expand=True)
    root.protocol('WM_DELETE_WINDOW', game.on_close)
    root.mainloop()
    return result['balance']


if __name__ == '__main__':
    final_balance = main()