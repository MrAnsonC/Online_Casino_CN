import copy
import json
import os
import re
import secrets
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageTk


# -----------------------------------------------------------------------------
# Account-data compatibility with the original project
# -----------------------------------------------------------------------------
def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')


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
# Dice and rules
# -----------------------------------------------------------------------------
class Dice:
    def __init__(self):
        self.value = 1

    def roll(self):
        self.value = secrets.randbelow(6) + 1
        return self.value


class CrapsEngine:
    BOX_NUMBERS = (4, 5, 6, 8, 9, 10)
    HARD_NUMBERS = (4, 6, 8, 10)
    CRAP_NUMBERS = (2, 3, 11, 12)

    PLACE_PAYOUT = {4: 9 / 5, 5: 7 / 5, 6: 7 / 6, 8: 7 / 6, 9: 7 / 5, 10: 9 / 5}
    LAY_PAYOUT = {4: 1 / 2, 5: 2 / 3, 6: 5 / 6, 8: 5 / 6, 9: 2 / 3, 10: 1 / 2}
    PASS_ODDS_PAYOUT = {4: 2, 5: 3 / 2, 6: 6 / 5, 8: 6 / 5, 9: 3 / 2, 10: 2}
    DONT_ODDS_PAYOUT = LAY_PAYOUT
    HARD_PAYOUT = {4: 8, 6: 10, 8: 10, 10: 8}
    CRAP_NUMBER_PAYOUT = {2: 30, 3: 15, 11: 15, 12: 30}

    def __init__(self):
        self.point = None
        self.bets = self.new_bets()

    @classmethod
    def new_bets(cls):
        return {
            'pass_line': 0.0,
            'dont_pass': 0.0,
            'pass_odds': 0.0,
            'dont_odds': 0.0,
            'come': 0.0,
            'dont_come': 0.0,
            'come_points': {n: 0.0 for n in cls.BOX_NUMBERS},
            'dont_come_points': {n: 0.0 for n in cls.BOX_NUMBERS},
            'place': {n: 0.0 for n in cls.BOX_NUMBERS},
            'lay': {n: 0.0 for n in cls.BOX_NUMBERS},
            'hard': {n: 0.0 for n in cls.HARD_NUMBERS},
            'field': 0.0,
            'any_seven': 0.0,
            'craps': 0.0,
            'crap_number': {n: 0.0 for n in cls.CRAP_NUMBERS},
            'ce': 0.0,
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
            return False, 0.0, '下注金额必须大于 0。'

        if bet_type in ('pass_line', 'dont_pass') and self.point is not None:
            return False, 0.0, "Point 已建立，不能新增 Pass Line / Don't Pass。"
        if bet_type in ('come', 'dont_come') and self.point is None:
            return False, 0.0, "Come / Don't Come 只能在 Point 建立后下注。"

        if bet_type == 'pass_odds':
            line = self.bets['pass_line']
            if self.point is None or line <= 0:
                return False, 0.0, '必须先有 Pass Line 且建立 Point。'
            amount = min(amount, line * 3 - self.bets['pass_odds'])
            if amount <= 0:
                return False, 0.0, 'Pass Odds 已达到 3 倍上限。'

        if bet_type == 'dont_odds':
            line = self.bets['dont_pass']
            if self.point is None or line <= 0:
                return False, 0.0, "必须先有 Don't Pass 且建立 Point。"
            amount = min(amount, line * 3 - self.bets['dont_odds'])
            if amount <= 0:
                return False, 0.0, "Don't Odds 已达到 3 倍上限。"

        if param is None:
            self.bets[bet_type] += amount
        else:
            self.bets[bet_type][param] += amount
        return True, amount, ''

    def remove_amount(self, bet_type, amount, param=None):
        """Remove one recently placed chip. Contract bets are only locked after a roll."""
        current = self.current_area_bet(bet_type, param)
        removed = min(current, max(0.0, amount))
        if param is None:
            self.bets[bet_type] -= removed
        else:
            self.bets[bet_type][param] -= removed
        return removed

    def clear_removable(self):
        refunded = 0.0
        locked = False

        for bet_type in ('pass_line', 'dont_pass'):
            if self.point is None:
                refunded += self.bets[bet_type]
                self.bets[bet_type] = 0.0
            elif self.bets[bet_type] > 0:
                locked = True

        for bet_type in (
            'pass_odds', 'dont_odds', 'come', 'dont_come', 'field', 'any_seven',
            'craps', 'ce'
        ):
            refunded += self.bets[bet_type]
            self.bets[bet_type] = 0.0

        for bet_type in ('place', 'lay', 'hard', 'crap_number'):
            refunded += sum(self.bets[bet_type].values())
            for key in self.bets[bet_type]:
                self.bets[bet_type][key] = 0.0

        if any(self.bets['come_points'].values()) or any(self.bets['dont_come_points'].values()):
            locked = True
        return refunded, locked

    def resolve_roll(self, dice, number_bets_active=True):
        d1, d2 = dice
        total = d1 + d2
        point_before = self.point
        credit = 0.0
        gross_profit = 0.0
        lost_stake = 0.0
        messages = []
        outcomes = []

        def label_to_key(label):
            if label.startswith('WIN '):
                return ('place', int(label.split()[-1]))
            if label.startswith('LOSE '):
                return ('lay', int(label.split()[-1]))
            if label.startswith('Hard '):
                return ('hard', int(label.split()[-1]))
            if label.startswith('Come ') and label.split()[-1].isdigit():
                return ('come_points', int(label.split()[-1]))
            if label.startswith("Don't Come ") and label.split()[-1].isdigit():
                return ('dont_come_points', int(label.split()[-1]))
            mapping = {
                'Pass Line': ('pass_line', None),
                "Don't Pass": ('dont_pass', None),
                'Pass Odds': ('pass_odds', None),
                "Don't Odds": ('dont_odds', None),
                'Come': ('come', None),
                "Don't Come": ('dont_come', None),
                'Field': ('field', None),
                'Seven': ('any_seven', None),
                'Craps': ('craps', None),
                'C·E': ('ce', None),
            }
            if label in mapping:
                return mapping[label]
            if str(label).isdigit() and int(label) in self.CRAP_NUMBERS:
                return ('crap_number', int(label))
            return None

        def record_outcome(label, status, amount, profit=0.0, keep=False):
            if amount <= 0:
                return
            key = label_to_key(label)
            outcomes.append({
                'label': label,
                'key': key,
                'status': status,
                'stake': float(amount),
                'profit': float(profit),
                'keep': bool(keep),
                'return_amount': float(amount + profit) if status == 'win' else (float(amount) if status == 'push' else 0.0),
            })

        def win_remove(label, amount, payout):
            nonlocal credit, gross_profit
            if amount <= 0:
                return
            profit = amount * payout
            credit += amount + profit
            gross_profit += profit
            record_outcome(label, 'win', amount, profit, keep=False)
            messages.append(f'{label} 赢 {profit:.2f}')

        def win_keep(label, amount, payout):
            nonlocal credit, gross_profit
            if amount <= 0:
                return
            profit = amount * payout
            credit += profit
            gross_profit += profit
            record_outcome(label, 'win', amount, profit, keep=True)
            messages.append(f'{label} 赢 {profit:.2f}（本金保留）')

        def lose(label, amount):
            nonlocal lost_stake
            if amount <= 0:
                return
            lost_stake += amount
            record_outcome(label, 'lose', amount)
            messages.append(f'{label} 输 {amount:.2f}')

        def push(label, amount):
            nonlocal credit
            if amount <= 0:
                return
            credit += amount
            record_outcome(label, 'push', amount)
            messages.append(f'{label} 和局，退回 {amount:.2f}')

        pending_come = self.bets['come']
        pending_dont_come = self.bets['dont_come']
        self.bets['come'] = 0.0
        self.bets['dont_come'] = 0.0

        # Existing Come / Don't Come point bets.
        for number in self.BOX_NUMBERS:
            amount = self.bets['come_points'][number]
            if amount > 0:
                if total == number:
                    win_remove(f'Come {number}', amount, 1)
                    self.bets['come_points'][number] = 0.0
                elif total == 7:
                    lose(f'Come {number}', amount)
                    self.bets['come_points'][number] = 0.0

            amount = self.bets['dont_come_points'][number]
            if amount > 0:
                if total == 7:
                    win_remove(f"Don't Come {number}", amount, 1)
                    self.bets['dont_come_points'][number] = 0.0
                elif total == number:
                    lose(f"Don't Come {number}", amount)
                    self.bets['dont_come_points'][number] = 0.0

        # WIN / LOSE number bets work on every roll while activated.
        # When closed, they are OFF during Come-Out and resume after a Point is established.
        number_bets_working = number_bets_active or point_before is not None
        if number_bets_working:
            if total == 7:
                for number in self.BOX_NUMBERS:
                    amount = self.bets['place'][number]
                    if amount > 0:
                        lose(f'WIN {number}', amount)
                        self.bets['place'][number] = 0.0
            elif total in self.BOX_NUMBERS:
                win_keep(f'WIN {total}', self.bets['place'][total], self.PLACE_PAYOUT[total])

            for number in self.BOX_NUMBERS:
                amount = self.bets['lay'][number]
                if amount <= 0:
                    continue
                if total == 7:
                    win_remove(f'LOSE {number}', amount, self.LAY_PAYOUT[number])
                    self.bets['lay'][number] = 0.0
                elif total == number:
                    lose(f'LOSE {number}', amount)
                    self.bets['lay'][number] = 0.0

        # Hardways.
        for number in self.HARD_NUMBERS:
            amount = self.bets['hard'][number]
            if amount <= 0:
                continue
            if total == 7:
                lose(f'Hard {number}', amount)
                self.bets['hard'][number] = 0.0
            elif total == number:
                if d1 == d2:
                    win_keep(f'Hard {number}', amount, self.HARD_PAYOUT[number])
                else:
                    lose(f'Hard {number}', amount)
                    self.bets['hard'][number] = 0.0

        # One-roll bets.
        one_roll_specs = [
            ('field', 'Field', lambda t: 2 if t in (2, 12) else (1 if t in (3, 4, 9, 10, 11) else None)),
            ('any_seven', 'Seven', lambda t: 5 if t == 7 else None),
            ('craps', 'Craps', lambda t: 8 if t in (2, 3, 12) else None),
            ('ce', 'C·E', lambda t: 7 if t == 11 else (3 if t in (2, 3, 12) else None)),
        ]
        for bet_type, label, payout_fn in one_roll_specs:
            amount = self.bets[bet_type]
            self.bets[bet_type] = 0.0
            if amount <= 0:
                continue
            payout = payout_fn(total)
            if payout is None:
                lose(label, amount)
            else:
                win_remove(label, amount, payout)

        for number in self.CRAP_NUMBERS:
            amount = self.bets['crap_number'][number]
            self.bets['crap_number'][number] = 0.0
            if amount <= 0:
                continue
            if total == number:
                win_remove(str(number), amount, self.CRAP_NUMBER_PAYOUT[number])
            else:
                lose(str(number), amount)

        # Pass / Don't Pass and table point.
        if point_before is None:
            if total in (7, 11):
                win_remove('Pass Line', self.bets['pass_line'], 1)
                lose("Don't Pass", self.bets['dont_pass'])
                self.bets['pass_line'] = self.bets['dont_pass'] = 0.0
            elif total in (2, 3, 12):
                lose('Pass Line', self.bets['pass_line'])
                self.bets['pass_line'] = 0.0
                if total == 12:
                    push("Don't Pass", self.bets['dont_pass'])
                else:
                    win_remove("Don't Pass", self.bets['dont_pass'], 1)
                self.bets['dont_pass'] = 0.0
            else:
                self.point = total
                messages.append(f'Point 建立：{total}')
        else:
            if total == point_before:
                win_remove('Pass Line', self.bets['pass_line'], 1)
                win_remove('Pass Odds', self.bets['pass_odds'], self.PASS_ODDS_PAYOUT[point_before])
                lose("Don't Pass", self.bets['dont_pass'])
                lose("Don't Odds", self.bets['dont_odds'])
                self.bets['pass_line'] = self.bets['pass_odds'] = 0.0
                self.bets['dont_pass'] = self.bets['dont_odds'] = 0.0
                self.point = None
                messages.append(f'命中 Point {point_before}，回到 Come-Out')
            elif total == 7:
                lose('Pass Line', self.bets['pass_line'])
                lose('Pass Odds', self.bets['pass_odds'])
                win_remove("Don't Pass", self.bets['dont_pass'], 1)
                win_remove("Don't Odds", self.bets['dont_odds'], self.DONT_ODDS_PAYOUT[point_before])
                self.bets['pass_line'] = self.bets['pass_odds'] = 0.0
                self.bets['dont_pass'] = self.bets['dont_odds'] = 0.0
                self.point = None
                messages.append('Seven Out，回到 Come-Out')

        # New Come / Don't Come bets.
        if pending_come > 0:
            if total in (7, 11):
                win_remove('Come', pending_come, 1)
            elif total in (2, 3, 12):
                lose('Come', pending_come)
            else:
                self.bets['come_points'][total] += pending_come
                messages.append(f'Come 移至 {total}：{pending_come:.2f}')

        if pending_dont_come > 0:
            if total in (2, 3):
                win_remove("Don't Come", pending_dont_come, 1)
            elif total in (7, 11):
                lose("Don't Come", pending_dont_come)
            elif total == 12:
                push("Don't Come", pending_dont_come)
            else:
                self.bets['dont_come_points'][total] += pending_dont_come
                messages.append(f"Don't Come 移至 {total}：{pending_dont_come:.2f}")

        if not messages:
            messages.append('本轮没有下注结算。')

        return {
            'dice': [d1, d2],
            'total': total,
            'point_before': point_before,
            'point_after': self.point,
            'credit': credit,
            'gross_profit': gross_profit,
            'lost_stake': lost_stake,
            'net': gross_profit - lost_stake,
            'messages': messages,
            'outcomes': outcomes,
        }


# -----------------------------------------------------------------------------
# Evolution-style compact betting interface
# -----------------------------------------------------------------------------
class BubbleCrapsGame(tk.Frame):
    BG = '#17120f'
    FELT = '#0b4540'
    FELT_2 = '#0d5149'
    LINE = '#c3d5ca'
    GOLD = '#e7d36c'
    RED = '#c43b40'

    MIN_BET = 0.5
    MAX_AREA_BET = 100000.0
    MAX_TABLE_BET = 2000000.0
    MAX_RECORDS = 500

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
        self.accept_bets = True
        self.engine = CrapsEngine()
        self.dice_objects = [Dice(), Dice()]
        self.developer_dice = None

        self.selected_chip = 1.0
        self.multiplier = 1
        self.undo_stack = []
        self.bet_spots = {}
        self.chip_selector_items = {}
        self.last_result = None
        self.animation_running = False
        self.animation_final_dice = None
        self.animation_after_id = None
        self.number_bets_active = True
        self.last_round_bets = []
        self.last_win_amount = 0.0
        self.summary_mode = 'bet'
        self.control_buttons = {}
        self.roll_ready = True
        self.settlement_running = False
        self.settlement_after_id = None
        self.roll_cooldown_after_id = None
        self.flash_mode = None
        self.flash_winners = {}
        self.flash_original_amounts = {}
        self.flash_original_text_colors = {}
        self.flash_original_outline_colors = {}
        self.pre_roll_bets = None

        # Betting-cell hover help is optional and disabled by default.
        # Left-clicking the help button opens the full rules window;
        # right-clicking it toggles these compact hover hints.
        self.bet_hover_help_enabled = False
        self.hovered_bet_key = None
        self._closing = False

        # Embedded in the parent application's single Tk root.
        top = self.winfo_toplevel()
        try:
            top.geometry('1150x750+50+10')
            top.resizable(False, False)
            top.title('花摇骰')
        except tk.TclError:
            pass
        self.bind('<Return>', lambda _event: self.roll_dice())
        self.bind('<Control-z>', lambda _event: self.undo_last_bet())
        self.bind('<Shift-R>', lambda _event: self.show_developer_input_dialog())

        self.history_file = self.get_history_file()
        self.history_data = self.load_history_data()
        self.restore_point_from_history()
        self.create_dice_images()
        self.create_ui()
        self.select_chip(1.0)
        self.update_display()
        self.ensure_point_puck_on_top()

    def create_dice_images(self):
        self.dice_images_small = []
        self.dice_images_history = []
        self.dice_images_board = []
        self.dice_images_animation = []

        def make_die(size, number):
            image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            margin = max(1, size // 28)
            radius = max(3, size // 7)
            draw.rounded_rectangle(
                (margin, margin, size - margin - 1, size - margin - 1),
                radius=radius, fill='#f0f0e9', outline='#222', width=max(1, size // 18)
            )
            quarter = size // 4
            half = size // 2
            three_quarter = size - quarter
            pos = {
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
            pip = max(2, size // 12)
            pip_color = '#d21e2b' if number in (1, 4) else '#111'
            for x, y in pos[number]:
                draw.ellipse((x - pip, y - pip, x + pip, y + pip), fill=pip_color)
            return ImageTk.PhotoImage(image)

        for number in range(1, 7):
            self.dice_images_small.append(make_die(38, number))
            self.dice_images_history.append(make_die(25, number))
            self.dice_images_board.append(make_die(20, number))
            self.dice_images_animation.append(make_die(92, number))

    def create_ui(self):
        self.canvas = tk.Canvas(self, width=1150, height=750, bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.create_rectangle(0, 0, 1150, 750, fill='#17120f', outline='', tags='static')

        self.draw_history_panel()
        self.draw_animation_panel()
        self.draw_payout_panel()
        self.draw_board()
        self.draw_bottom_controls()

        # Canvas items with an empty fill are not reliably hit-testable on every
        # Tk build. Use coordinate-based fallback handling so the entire WIN and
        # LOSE strips (including their blank space and text) accept wagers.
        self.canvas.bind('<Button-1>', self.on_canvas_left_click, add='+')
        self.canvas.bind('<Button-3>', self.on_canvas_right_click, add='+')
        self.canvas.bind('<Motion>', self.on_canvas_motion, add='+')
        self.canvas.bind('<Leave>', lambda _event: self.hide_bet_tooltip(), add='+')

    def draw_history_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = 12, 4, 278, 620
        c.create_rectangle(x0, y0, x1, y1, fill='#211811', outline='#665240', width=2, tags='static')
        c.create_text((x0 + x1) / 2, y0 + 24, text='历史记录（最近15局）',
                      font=('Arial', 17, 'bold'), fill='#d4c3a9', tags='static')

        table_x0, table_x1 = x0 + 8, x1 - 8
        header_top = y0 + 72
        header_bottom = header_top + 52
        col1, col2 = table_x0 + 138, table_x0 + 197
        c.create_rectangle(table_x0, header_top, table_x1, y1 - 12,
                           fill='#15110f', outline='#7c6754', width=1, tags='static')
        c.create_line(col1, header_top, col1, y1 - 12, fill='#7c6754', width=1, tags='static')
        c.create_line(col2, header_top, col2, y1 - 12, fill='#7c6754', width=1, tags='static')
        c.create_line(table_x0, header_bottom, table_x1, header_bottom, fill='#7c6754', width=1, tags='static')
        c.create_text((table_x0 + col1) / 2, (header_top + header_bottom) / 2,
                      text='骰子', font=('Arial', 13, 'bold'), fill='white', tags='static')
        c.create_text((col1 + col2) / 2, (header_top + header_bottom) / 2,
                      text='点数', font=('Arial', 13, 'bold'), fill='white', tags='static')
        c.create_text((col2 + table_x1) / 2, (header_top + header_bottom) / 2,
                      text='状态', font=('Arial', 13, 'bold'), fill='white', tags='static')

        row_height = (y1 - 12 - header_bottom) / 15
        for index in range(1, 16):
            y = header_bottom + index * row_height
            c.create_line(table_x0, y, table_x1, y, fill='#514338', tags='static')

        self.history_panel_geometry = {
            'x0': table_x0, 'x1': table_x1, 'col1': col1, 'col2': col2,
            'header_bottom': header_bottom, 'row_height': row_height,
        }

    def draw_animation_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = 286, 4, 876, 315
        c.create_rectangle(x0, y0, x1, y1, fill='#211811', outline='#665240', width=2, tags='static')

        self.animation_panel = (x0, y0, x1, y1)
        self.animation_phase_text = c.create_text(
            (x0 + x1) / 2, y0 + 18, text='花摇骰',
            font=('Arial', 16, 'bold'), fill='#d4c3a9', tags='animation'
        )
        c.create_oval(x0 + 105, y0 + 30, x1 - 105, y1 - 16,
                      fill='#193d35', outline='#f1f1ed', width=4, tags='animation')
        c.create_oval(x0 + 128, y0 + 48, x1 - 128, y1 - 34,
                      fill='#0f5a49', outline='#86b9aa', width=2, tags='animation')

        centre_x = (x0 + x1) / 2
        centre_y = y0 + 138
        self.animation_dice_items = [
            c.create_image(centre_x - 65, centre_y, image=self.dice_images_animation[0],
                           state='hidden', tags='animation_dice'),
            c.create_image(centre_x + 65, centre_y, image=self.dice_images_animation[0],
                           state='hidden', tags='animation_dice'),
        ]

        # A translucent-looking bubble behind the status/result row. Tkinter Canvas
        # has no true alpha fill, so stipple is used to let the felt show through.
        self.animation_status_bubble = c.create_oval(
            x0 + 100, y1 - 68, x1 - 100, y1 - 10,
            fill='#0b2723', stipple='gray50', outline='#c8efe7', width=2,
            tags=('animation', 'status_bubble')
        )
        self.animation_status_text = c.create_text(
            centre_x, y1 - 38, text='按下"转动"按钮以开始本局', width=420,
            font=('Arial', 14, 'bold'), fill='white', tags='animation'
        )
        self.animation_result_dice_items = [
            c.create_image(centre_x - 22, y1 - 38, image=self.dice_images_history[0],
                           state='hidden', tags='animation_result'),
            c.create_image(centre_x + 43, y1 - 38, image=self.dice_images_history[0],
                           state='hidden', tags='animation_result'),
        ]
        self.animation_plus_text = c.create_text(centre_x + 10, y1 - 38, text='+',
                                                  font=('Arial', 14, 'bold'), fill='white',
                                                  state='hidden', tags='animation_result')
        self.animation_equals_text = c.create_text(centre_x + 105, y1 - 38, text='= 0',
                                                    font=('Arial', 14, 'bold'), fill='#f0dc72',
                                                    state='hidden', tags='animation_result')

    def draw_payout_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = 884, 4, 1138, 620
        c.create_rectangle(x0, y0, x1, y1, fill='#211811', outline='#665240', width=2, tags='static')
        c.create_text((x0 + x1) / 2, y0 + 25, text='获胜赔付',
                      font=('Arial', 17, 'bold'), fill='#d4c3a9', tags='static')

        table_x0, table_x1 = x0 + 8, x1 - 8
        header_top = y0 + 52
        header_bottom = header_top + 40
        col1 = table_x0 + 112
        c.create_rectangle(table_x0, header_top, table_x1, y1 - 12,
                           fill='#15110f', outline='#7c6754', width=1, tags='static')
        c.create_line(col1, header_top, col1, y1 - 12, fill='#f1f1ed', width=2, tags='static')
        c.create_line(table_x0, header_bottom, table_x1, header_bottom, fill='#f1f1ed', width=2, tags='static')
        c.create_text((table_x0 + col1) / 2, (header_top + header_bottom) / 2,
                      text='点数', font=('Arial', 13, 'bold'), fill='white', tags='static')
        c.create_text((col1 + table_x1) / 2, (header_top + header_bottom) / 2,
                      text='下局输赢', font=('Arial', 13, 'bold'), fill='white', tags='static')

        row_height = (y1 - 12 - header_bottom) / 11
        for index in range(1, 12):
            y = header_bottom + index * row_height
            c.create_line(table_x0, y, table_x1, y, fill='#f1f1ed', width=2, tags='static')

        self.payout_panel_geometry = {
            'x0': table_x0, 'x1': table_x1, 'col1': col1,
            'header_bottom': header_bottom, 'row_height': row_height,
        }

    def draw_board(self):
        c = self.canvas
        bx, by = 286, 320
        board_width, board_height = 590, 300
        self.board_origin = (bx, by)
        self.board_main_width = 430

        c.create_rectangle(bx, by, bx + board_width, by + board_height,
                           fill=self.FELT, outline=self.LINE, width=2, tags='board')

        main_x0, main_x1 = bx, bx + self.board_main_width
        num_y0, num_y1 = by, by + 100
        dc_x1 = main_x0 + 56
        numbers = (4, 5, 6, 8, 9, 10)
        col_w = (main_x1 - main_x0) / 6

        for idx, number in enumerate(numbers):
            x0 = main_x0 + idx * col_w
            x1 = x0 + col_w
            c.create_rectangle(x0, num_y0, x1, num_y1, fill=self.FELT_2,
                               outline=self.LINE, width=1, tags='board')
            c.create_line(x0, num_y0 + 25, x1, num_y0 + 25, fill=self.LINE, tags='board')
            c.create_line(x0, num_y0 + 74, x1, num_y0 + 74, fill=self.LINE, tags='board')
            lose_tag = self.spot_tag(('lay', number))
            win_tag = self.spot_tag(('place', number))
            c.create_text((x0 + x1) / 2, num_y0 + 13, text='LOSE',
                          font=('Arial', 9, 'bold'), fill='white', tags=('board', lose_tag))
            c.create_text((x0 + x1) / 2, num_y0 + 49, text=str(number),
                          font=('Times New Roman', 22, 'bold'), fill='white', tags='board')
            c.create_text((x0 + x1) / 2, num_y0 + 87, text='WIN',
                          font=('Arial', 9, 'bold'), fill='white', tags=('board', win_tag))
            self.register_rect_spot('lay', number, x0 + 1, num_y0 + 1, x1 - 1, num_y0 + 24,
                                    chip_pos=((x0 + x1) / 2, num_y0 + 13), label=f'LOSE {number}')
            self.register_rect_spot('place', number, x0 + 1, num_y0 + 75, x1 - 1, num_y1 - 1,
                                    chip_pos=((x0 + x1) / 2, num_y0 + 87), label=f'WIN {number}')

        c.create_rectangle(main_x0, by + 100, dc_x1, by + 178,
                           fill='#083b39', outline=self.LINE, tags='board')
        c.create_text((main_x0 + dc_x1) / 2, by + 137, text="DON'T\nCOME\nBAR",
                      font=('Arial', 9, 'bold'), fill='#ff5157', tags='board')
        self.register_rect_spot('dont_come', None, main_x0, by + 100, dc_x1, by + 178,
                                chip_pos=((main_x0 + dc_x1) / 2, by + 150), label="DON'T COME")

        c.create_rectangle(dc_x1, by + 100, main_x1, by + 178,
                           fill=self.FELT, outline=self.LINE, tags='board')
        c.create_text((dc_x1 + main_x1) / 2, by + 128, text='COME',
                      font=('Times New Roman', 27, 'bold'), fill=self.GOLD, tags='board')
        self.register_rect_spot('come', None, dc_x1, by + 100, main_x1, by + 178,
                                chip_pos=((dc_x1 + main_x1) / 2, by + 153), label='COME')

        c.create_rectangle(main_x0, by + 178, main_x1, by + 226,
                           fill=self.FELT, outline=self.LINE, tags='board')
        field_y = by + 197
        c.create_oval(main_x0 + 70, field_y - 16, main_x0 + 102, field_y + 16,
                      outline='#f1edd3', width=2, tags='board')
        c.create_oval(main_x1 - 102, field_y - 16, main_x1 - 70, field_y + 16,
                      outline='#f1edd3', width=2, tags='board')
        c.create_text(main_x0 + 86, field_y, text='2', font=('Times New Roman', 14, 'bold'),
                      fill='#f1edd3', tags='board')
        c.create_text(main_x1 - 86, field_y, text='12', font=('Times New Roman', 14, 'bold'),
                      fill='#f1edd3', tags='board')
        c.create_text((main_x0 + main_x1) / 2, by + 193, text='3·4·9·10·11',
                      font=('Times New Roman', 13, 'bold'), fill='#f1edd3', tags='board')
        c.create_text((main_x0 + main_x1) / 2, by + 216, text='FIELD',
                      font=('Times New Roman', 15, 'bold'), fill='#f1edd3', tags='board')
        self.register_rect_spot('field', None, main_x0, by + 178, main_x1, by + 226,
                                chip_pos=((main_x0 + main_x1) / 2, by + 208), label='FIELD')

        # DON'T PASS BAR + DON'T ODDS
        c.create_rectangle(
            main_x0, by + 226, main_x1, by + 263,
            fill='#083b39', outline=self.LINE, tags='board'
        )

        # ODDS 区域分隔线
        c.create_line(
            main_x1 - 60, by + 226,
            main_x1 - 60, by + 263,
            fill=self.LINE, width=1, tags='board'
        )

        row_center = (main_x0 + main_x1) / 2

        c.create_text(
            row_center - 42, by + 244,
            text="DON'T PASS BAR",
            font=('Arial', 11, 'bold'),
            fill='#ff5157',
            tags='board'
        )

        c.create_image(
            row_center + 50, by + 244,
            image=self.dice_images_history[5],
            tags='board'
        )
        c.create_image(
            row_center + 80, by + 244,
            image=self.dice_images_history[5],
            tags='board'
        )

        # 恢复 DON'T ODDS 文字
        c.create_text(
            main_x1 - 30, by + 244,
            text='ODDS',
            font=('Arial', 8, 'bold'),
            fill='white',
            tags='board'
        )

        self.register_rect_spot(
            'dont_pass', None,
            main_x0, by + 226,
            main_x1 - 60, by + 263,
            chip_pos=(
                (main_x0 + main_x1 + 10) / 2,
                (by + 226 + by + 263) / 2
            ),
            label="DON'T PASS"
        )

        self.register_rect_spot(
            'dont_odds', None,
            main_x1 - 60, by + 226,
            main_x1, by + 263,
            chip_pos=(main_x1 - 30, by + 244),
            label="DON'T ODDS"
        )

        # PASS LINE + PASS ODDS
        c.create_rectangle(
            main_x0, by + 263, main_x1, by + 300,
            fill='#083b39', outline=self.LINE, tags='board'
        )

        # ODDS 区域分隔线
        c.create_line(
            main_x1 - 60, by + 263,
            main_x1 - 60, by + 300,
            fill=self.LINE, width=1, tags='board'
        )

        c.create_text(
            (main_x0 + main_x1 - 60) / 2, by + 282,
            text='PASS LINE',
            font=('Times New Roman', 18, 'bold'),
            fill=self.GOLD,
            tags='board'
        )

        # 恢复 PASS ODDS 文字
        c.create_text(
            main_x1 - 30, by + 282,
            text='ODDS',
            font=('Arial', 8, 'bold'),
            fill='white',
            tags='board'
        )

        self.register_rect_spot(
            'pass_line', None,
            main_x0, by + 263,
            main_x1 - 60, by + 300,
            chip_pos=((main_x0 + main_x1 - 60) / 2 + 35, by + 282),
            label='PASS LINE'
        )

        self.register_rect_spot(
            'pass_odds', None,
            main_x1 - 60, by + 263,
            main_x1, by + 300,
            chip_pos=(main_x1 - 30, by + 282),
            label='PASS ODDS'
        )

        rx0, rx1 = main_x1, bx + board_width
        c.create_rectangle(rx0, by, rx1, by + 300,
                           fill='#0a4844', outline=self.LINE, width=1, tags='board')
        gap = 5
        inner_x0, inner_x1 = rx0 + 6, rx1 - 6
        mid = (inner_x0 + inner_x1) / 2

        hard_specs = [
            (4, inner_x0, by + 8, mid - gap / 2, by + 65, [2, 2], '8:1'),
            (6, mid + gap / 2, by + 8, inner_x1, by + 65, [3, 3], '10:1'),
            (8, inner_x0, by + 69, mid - gap / 2, by + 126, [4, 4], '10:1'),
            (10, mid + gap / 2, by + 69, inner_x1, by + 126, [5, 5], '8:1'),
        ]
        for number, x0, y0, x1, y1, dice_values, payout in hard_specs:
            c.create_rectangle(x0, y0, x1, y1, fill=self.FELT_2,
                               outline=self.LINE, tags='board')
            center_x = (x0 + x1) / 2
            spacing = 20
            start_x = center_x - spacing * (len(dice_values) - 1) / 2
            for index, die_value in enumerate(dice_values):
                c.create_image(start_x + index * spacing, y0 + 22,
                               image=self.dice_images_board[die_value - 1], tags='board')
            c.create_text(center_x, y1 - 10, text=payout,
                          font=('Arial', 8, 'bold'), fill='#d9d9d9', tags='board')
            self.register_rect_spot('hard', number, x0, y0, x1, y1,
                                    chip_pos=(center_x, (y0 + y1) / 2), label=f'HARD {number}')

        ce_y0, ce_y1 = by + 130, by + 163
        c.create_rectangle(inner_x0, ce_y0, inner_x1, ce_y1,
                           fill=self.FELT_2, outline=self.LINE, tags='board')
        c.create_text((inner_x0 + inner_x1) / 2, (ce_y0 + ce_y1) / 2, text='C · E',
                      font=('Times New Roman', 15, 'bold'), fill='#f1edd3', tags='board')
        self.register_rect_spot('ce', None, inner_x0, ce_y0, inner_x1, ce_y1,
                                chip_pos=((inner_x0 + inner_x1) / 2, (ce_y0 + ce_y1) / 2), label='C·E')

        one_y = by + 166
        specs = [
            (2, inner_x0, one_y, mid - gap / 2, one_y + 46, '30:1', (1, 1)),
            (11, mid + gap / 2, one_y, inner_x1, one_y + 46, '15:1', (5, 6)),
            (3, inner_x0, one_y + 49, mid - gap / 2, one_y + 95, '15:1', (1, 2)),
            (12, mid + gap / 2, one_y + 49, inner_x1, one_y + 95, '30:1', (6, 6)),
        ]
        for number, x0, y0, x1, y1, payout, dice_values in specs:
            c.create_rectangle(x0, y0, x1, y1, fill=self.FELT_2,
                               outline=self.LINE, tags='board')
            center_x = (x0 + x1) / 2
            dice_y = y0 + 16
            c.create_image(center_x - 11, dice_y,
                           image=self.dice_images_board[dice_values[0] - 1], tags='board')
            c.create_image(center_x + 11, dice_y,
                           image=self.dice_images_board[dice_values[1] - 1], tags='board')
            c.create_text(center_x, y1 - 9, text=payout,
                          font=('Arial', 8), fill='#d9d9d9', tags='board')
            self.register_rect_spot('crap_number', number, x0, y0, x1, y1,
                                    chip_pos=(center_x, (y0 + y1) / 2), label=str(number))

        bottom_y0, bottom_y1 = by + 264, by + 298
        c.create_rectangle(inner_x0, bottom_y0, mid - gap / 2, bottom_y1,
                           fill=self.FELT_2, outline=self.LINE, tags='board')
        c.create_text((inner_x0 + mid - gap / 2) / 2, bottom_y0 + 12, text='SEVEN',
                      font=('Times New Roman', 12, 'bold'), fill='#f1edd3', tags='board')
        c.create_text((inner_x0 + mid - gap / 2) / 2, bottom_y1 - 8, text='5:1',
                      font=('Arial', 8, 'bold'), fill='white', tags='board')
        self.register_rect_spot('any_seven', None, inner_x0, bottom_y0,
                                mid - gap / 2, bottom_y1,
                                chip_pos=((inner_x0 + mid - gap / 2) / 2, (bottom_y0 + bottom_y1) / 2),
                                label='SEVEN')

        c.create_rectangle(mid + gap / 2, bottom_y0, inner_x1, bottom_y1,
                           fill=self.FELT_2, outline=self.LINE, tags='board')
        c.create_text((mid + gap / 2 + inner_x1) / 2, bottom_y0 + 12, text='CRAPS',
                      font=('Times New Roman', 12, 'bold'), fill='#f1edd3', tags='board')
        c.create_text((mid + gap / 2 + inner_x1) / 2, bottom_y1 - 8, text='8:1',
                      font=('Arial', 8, 'bold'), fill='white', tags='board')
        self.register_rect_spot('craps', None, mid + gap / 2, bottom_y0,
                                inner_x1, bottom_y1,
                                chip_pos=((mid + gap / 2 + inner_x1) / 2, (bottom_y0 + bottom_y1) / 2),
                                label='CRAPS')

        self.number_mode_button = self.create_control_button(
            bx + 2, by - 56, bx + 72, by - 30, '关闭',
            self.toggle_number_bets_active, '#287c4b', fg='white', font_size=10
        )
        self.canvas.tag_raise(self.number_mode_button)

    def canvas_bet_spot_at(self, x, y):
        """Return the smallest registered betting region containing x/y."""
        candidates = []
        for key, spot in self.bet_spots.items():
            x0, y0, x1, y1 = spot['bbox']
            if x0 <= x <= x1 and y0 <= y <= y1:
                candidates.append(((x1 - x0) * (y1 - y0), key))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def get_bet_hover_help_text(self, key):
        """Return the compact win condition and payout for one betting cell."""
        bet_type, param = key

        if bet_type == 'hard':
            dice_value = {4: 2, 6: 3, 8: 4, 10: 5}[param]
            payout = CrapsEngine.HARD_PAYOUT[param]
            return f'在出现软{param}或7前\n出现双{dice_value}赢 {payout}:1'

        if bet_type == 'place':
            payout = {4: '9:5', 5: '7:5', 6: '7:6', 8: '7:6', 9: '7:5', 10: '9:5'}[param]
            return f'{param}在7前出现即赢\n赔率 {payout}；7先出现则输'

        if bet_type == 'lay':
            payout = {4: '1:2', 5: '2:3', 6: '5:6', 8: '5:6', 9: '2:3', 10: '1:2'}[param]
            return f'7在{param}前出现即赢\n赔率 {payout}；{param}先出现则输'

        if bet_type == 'pass_line':
            return 'Come-Out：7或11赢；2、3、12输\n建立点数后，点数先于7出现赢 1:1'
        if bet_type == 'dont_pass':
            return 'Come-Out：2或3赢；7、11输；12和局\n建立点数后，7先于点数出现赢 1:1'
        if bet_type == 'pass_odds':
            return '必须先有 PASS LINE 并建立点数\n按真实赔率赔付，最多为主注3倍'
        if bet_type == 'dont_odds':
            return "必须先有 DON'T PASS 并建立点数\n按真实赔率赔付，最多为主注3倍"
        if bet_type == 'come':
            return '仅在点数建立后下注\n本轮7、11赢；2、3、12输，其余移至对应点数'
        if bet_type == 'dont_come':
            return '仅在点数建立后下注\n本轮2、3赢；7、11输；12和局，其余移至对应点数'
        if bet_type == 'field':
            return '单轮下注\n2、12赢 2:1；3、4、9、10、11赢 1:1'
        if bet_type == 'any_seven':
            return '单轮下注\n本轮点数为7即赢 5:1'
        if bet_type == 'craps':
            return '单轮下注\n本轮点数为2、3或12即赢 8:1'
        if bet_type == 'ce':
            return '单轮下注\n11赢 7:1；2、3、12赢 3:1'
        if bet_type == 'crap_number':
            payout = CrapsEngine.CRAP_NUMBER_PAYOUT[param]
            dice_text = {2: '1+1', 3: '1+2', 11: '5+6', 12: '6+6'}[param]
            return f'单轮下注\n出现 {dice_text}（点数{param}）赢 {payout}:1'
        return ''

    def hide_bet_tooltip(self):
        """Remove the compact betting-cell hover hint."""
        try:
            self.canvas.delete('bet_hover_tooltip')
        except tk.TclError:
            pass
        self.hovered_bet_key = None

    def show_bet_tooltip(self, key, pointer_x, pointer_y):
        """Draw a compact tooltip near the pointer without blocking wagers."""
        text = self.get_bet_hover_help_text(key)
        if not text:
            self.hide_bet_tooltip()
            return

        self.canvas.delete('bet_hover_tooltip')
        padding = 8
        x = pointer_x + 16
        y = pointer_y + 16
        text_id = self.canvas.create_text(
            x + padding, y + padding,
            anchor='nw', text=text, width=245,
            font=('Microsoft YaHei UI', 10, 'bold'),
            fill='#fff8dc', justify=tk.LEFT,
            tags=('bet_hover_tooltip',),
        )
        bbox = self.canvas.bbox(text_id)
        if bbox is None:
            return

        canvas_width = max(self.canvas.winfo_width(), 1150)
        canvas_height = max(self.canvas.winfo_height(), 750)
        tooltip_width = bbox[2] - bbox[0] + padding * 2
        tooltip_height = bbox[3] - bbox[1] + padding * 2

        if x + tooltip_width > canvas_width - 6:
            x = max(6, pointer_x - tooltip_width - 16)
        if y + tooltip_height > canvas_height - 6:
            y = max(6, pointer_y - tooltip_height - 16)

        self.canvas.coords(text_id, x + padding, y + padding)
        bbox = self.canvas.bbox(text_id)
        background_id = self.canvas.create_rectangle(
            bbox[0] - padding, bbox[1] - padding,
            bbox[2] + padding, bbox[3] + padding,
            fill='#1c1713', outline='#e7d36c', width=2,
            tags=('bet_hover_tooltip',),
        )
        self.canvas.tag_lower(background_id, text_id)
        self.canvas.tag_raise('bet_hover_tooltip')
        self.ensure_point_puck_on_top()
        self.hovered_bet_key = key

    def on_canvas_motion(self, event):
        """Show a betting hint only after the player enables the option."""
        if not self.bet_hover_help_enabled:
            if self.hovered_bet_key is not None:
                self.hide_bet_tooltip()
            return None

        current = self.canvas.find_withtag('current')
        if current:
            tags = set(self.canvas.gettags(current[0]))
            if {'controls', 'chip_selector'} & tags:
                self.hide_bet_tooltip()
                return None

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        key = self.canvas_bet_spot_at(canvas_x, canvas_y)
        if key is None:
            self.hide_bet_tooltip()
            return None

        if key != self.hovered_bet_key:
            self.show_bet_tooltip(key, event.x, event.y)
        return None

    def toggle_bet_hover_help(self, _event=None):
        """Right-click the help button to enable or disable cell hover hints."""
        self.bet_hover_help_enabled = not self.bet_hover_help_enabled
        if not self.bet_hover_help_enabled:
            self.hide_bet_tooltip()

        self.update_control_button_style(
            self.info_button,
            text='💡' if self.bet_hover_help_enabled else '❓',
            fill='#3d7850' if self.bet_hover_help_enabled else '#315b72',
            fg='white',
        )
        return 'break'

    def canvas_click_is_already_handled(self):
        """Avoid duplicating clicks handled by chips, controls or selector items."""
        current = self.canvas.find_withtag('current')
        if not current:
            return False
        tags = set(self.canvas.gettags(current[0]))

        # 只有控制按钮和筹码选择器保留自己的点击绑定。下注格、格内文字、
        # 透明 hotspot 与桌面下注筹码都统一交给 Canvas 坐标事件处理一次，
        # 避免筹码重绘后同一鼠标事件再次落到下注格而造成双倍下注。
        return bool({'controls', 'chip_selector'} & tags)

    def on_canvas_left_click(self, event):
        """Place the selected chip anywhere inside a registered betting cell."""
        if self.canvas_click_is_already_handled():
            return None
        key = self.canvas_bet_spot_at(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if key is None:
            return None
        bet_type, param = key
        self.place_bet(bet_type, param)
        return 'break'

    def on_canvas_right_click(self, event):
        """Clear the entire wager from the clicked registered betting cell."""
        if self.canvas_click_is_already_handled():
            return None
        key = self.canvas_bet_spot_at(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if key is None:
            return None
        bet_type, param = key
        self.clear_single_bet(bet_type, param)
        return 'break'

    def register_rect_spot(self, bet_type, param, x0, y0, x1, y1, chip_pos, label):
        key = (bet_type, param)
        self.bet_spots[key] = {'bbox': (x0, y0, x1, y1), 'chip_pos': chip_pos, 'label': label}
        tag = self.spot_tag(key)

        # 所有下注格统一由 Canvas 的坐标事件处理。
        # 不再同时对文字/透明热点绑定 place_bet，否则同一次点击会先触发
        # tag_bind，再冒泡到 Canvas 绑定，造成双倍下注。
        self.canvas.create_rectangle(
            x0, y0, x1, y1,
            fill='', outline='',
            tags=(tag, 'hotspot'),
        )

    @staticmethod
    def spot_tag(key):
        bet_type, param = key
        return f'spot_{bet_type}_{param if param is not None else "none"}'

    def draw_bottom_controls(self):
        c = self.canvas
        y0, y1 = 625, 748
        c.create_rectangle(0, y0, 1150, y1, fill='#17120f', outline='#665240', width=2, tags='controls')

        self.balance_text = c.create_text(10, 665, anchor='w', text='余额: $0.00',
                                          font=('Arial', 18, 'bold'), fill='white', tags=('dynamic', 'controls'))
        self.total_bet_text = c.create_text(10, 710, anchor='w', text='本局下注: $0.00',
                                            font=('Arial', 18, 'bold'), fill='white', tags=('dynamic', 'controls'))

        self.repeat_button = self.create_control_button(
            300, 648, 410, 700, '重复下注', self.repeat_last_bets, '#5b4938', font_size=11
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
        # Left click opens the full rules window. Right click toggles the
        # optional betting-cell hover hints; the option starts disabled.
        self.canvas.tag_bind(self.info_button, '<Button-3>', self.toggle_bet_hover_help)

        self.clear_button = self.create_control_button(
            875, 638, 1005, 708, '清除下注', self.clear_bets, '#7c3b40', font_size=12
        )
        self.roll_button = self.create_control_button(
            1020, 628, 1135, 720, '转动', self.roll_dice, '#d5ad4d', fg='#111', font_size=14
        )

        c.tag_raise('controls')
        c.tag_raise('chip_selector')
        self.update_control_states()

    def show_help_window(self):
        # 在独立 Toplevel 中显示本游戏的玩法说明。
        owner = self.winfo_toplevel()
        win = tk.Toplevel(owner)
        win.title('花旗骰玩法说明')
        win.configure(bg='#17120f')
        win.resizable(False, False)
        win.transient(owner)

        width, height = 720, 620
        try:
            owner.update_idletasks()
            owner_width = max(owner.winfo_width(), 1150)
            owner_height = max(owner.winfo_height(), 750)
            x = owner.winfo_rootx() + max(0, (owner_width - width) // 2)
            y = owner.winfo_rooty() + max(0, (owner_height - height) // 2)
            win.geometry(f'{width}x{height}+{x}+{y}')
        except tk.TclError:
            win.geometry(f'{width}x{height}')

        tk.Label(
            win, text='🎲 花旗骰玩法说明',
            font=('Microsoft YaHei UI', 20, 'bold'),
            bg='#17120f', fg='#e7d36c'
        ).pack(pady=(16, 10))

        body = tk.Frame(win, bg='#17120f')
        body.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 12))
        scrollbar = tk.Scrollbar(body, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(
            body, wrap=tk.WORD, yscrollcommand=scrollbar.set,
            font=('Microsoft YaHei UI', 11), bg='#211811', fg='#f4eee5',
            insertbackground='white', relief=tk.FLAT, padx=14, pady=12,
            spacing1=3, spacing2=2, spacing3=8
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        help_text = (
            '基本流程\n'
            '• 没有 Point 时为花摇骰（Come-Out）。掷出 4、5、6、8、9、10 会建立 Point。\n'
            '• 建立 Point 后，再次掷中 Point，Pass Line 获胜；先掷出 7 则 Don\'t Pass 获胜并 Seven Out。\n'
            '• 没有任何下注时也可以按“转动”。\n\n'
            '主要下注\n'
            '• PASS LINE：Come-Out 的 7、11 赢；2、3、12 输。建立 Point 后，Point 先于 7 出现则赢。\n'
            '• DON\'T PASS：Come-Out 的 2、3 赢；7、11 输；12 和局。建立 Point 后，7 先于 Point 出现则赢。\n'
            '• COME / DON\'T COME：只可在 Point 建立后下注，规则相当于新的 Pass / Don\'t Pass。\n'
            '• WIN 数字：所选数字先于 7 出现即赢。4/10 付 9:5，5/9 付 7:5，6/8 付 7:6。\n'
            '• LOSE 数字：7 先于所选数字出现即赢。4/10 付 1:2，5/9 付 2:3，6/8 付 5:6。\n\n'
            '单次下注\n'
            '• FIELD：2、12 付 2:1；3、4、9、10、11 付 1:1。\n'
            '• SEVEN：掷出 7，付 5:1。\n'
            '• CRAPS：掷出 2、3、12，付 8:1。\n'
            '• C·E：11 付 7:1；2、3、12 付 3:1。\n'
            '• 单独 2 / 12 付 30:1；单独 3 / 11 付 15:1。\n\n'
            'Hardway\n'
            '• HARD 4、10：对子先于软点或 7 出现，付 8:1。\n'
            '• HARD 6、8：对子先于软点或 7 出现，付 10:1。\n\n'
            '桌面操作\n'
            '• 选择筹码后，左键点击下注区域增加当前筹码。\n'
            '• 右键点击下注区域或该区域筹码，清除该格全部可撤下注。\n'
            '• 左键点击右下角“❓”打开完整玩法说明；右键点击该按钮开启或关闭下注格悬停提示。\n'
            '• 下注格悬停提示默认关闭。\n'
            '• “重复下注”会尝试恢复上一局的全部下注。\n'
            '• “激活”状态：WIN / LOSE 数字在任何阶段都结算。\n'
            '• “关闭”状态：Come-Out（OFF）阶段的 WIN / LOSE 暂不结算；Point 建立后恢复。\n'
            '• 结算动画结束后可以下注；“转动”按钮会额外冷却 5 秒。\n\n'
            '显示说明\n'
            '• “上局获胜”显示所有获胜区域的本金加获胜奖金，不包含和局退回。\n'
            '• 白色闪烁表示该区域本轮获胜；ON 圆牌表示当前 Point。'
        )
        text_widget.insert(tk.END, help_text)
        text_widget.config(state=tk.DISABLED)

        tk.Button(
            win, text='关闭说明', command=win.destroy,
            font=('Microsoft YaHei UI', 11, 'bold'),
            bg='#315b72', fg='white', activebackground='#447b99',
            activeforeground='white', relief=tk.RAISED, bd=3,
            padx=24, pady=7, cursor='hand2'
        ).pack(pady=(0, 14))

        win.bind('<Escape>', lambda _event: win.destroy())
        win.focus_set()

    @staticmethod
    def shade_color(color, factor):
        color = color.lstrip('#')
        if len(color) != 6:
            return '#555555'
        values = [int(color[index:index + 2], 16) for index in (0, 2, 4)]
        values = [max(0, min(255, int(value * factor))) for value in values]
        return '#' + ''.join(f'{value:02x}' for value in values)

    def create_control_button(self, x0, y0, x1, y1, text, command, fill, fg='white', font_size=11):
        """Draw a bevelled machine-style button with hover, press and disabled states."""
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
        text_id = self.canvas.create_text(
            (x0 + x1) / 2, (y0 + y1) / 2 - 1, text=text,
            font=('Arial', font_size, 'bold'), fill=fg, tags=(tag, 'controls')
        )
        data = {
            'shadow': shadow,
            'rim': rim,
            'face': face,
            'highlight': highlight,
            'text': text_id,
            'command': command,
            'fill': fill,
            'fg': fg,
            'enabled': True,
            'pressed': False,
            'center_y': (y0 + y1) / 2 - 1,
        }
        self.control_buttons[tag] = data

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

        def release(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled'] or not button['pressed']:
                return
            button['pressed'] = False
            self.canvas.itemconfig(button['face'], fill=button['fill'])
            self.canvas.itemconfig(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'])
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
            self.canvas.itemconfig(button['text'], text=text)
        if fill is not None:
            button['fill'] = fill
        if fg is not None:
            button['fg'] = fg
        if button['enabled']:
            self.canvas.itemconfig(button['face'], fill=button['fill'])
            self.canvas.itemconfig(button['rim'], fill=self.shade_color(button['fill'], 0.55))
            self.canvas.itemconfig(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            self.canvas.itemconfig(button['text'], fill=button['fg'])

    def set_control_button_state(self, tag, enabled):
        button = self.control_buttons.get(tag)
        if not button:
            return
        button['enabled'] = bool(enabled)
        button['pressed'] = False
        x, _y = self.canvas.coords(button['text'])
        self.canvas.coords(button['text'], x, button['center_y'])
        if enabled:
            self.canvas.itemconfig(button['face'], fill=button['fill'])
            self.canvas.itemconfig(button['rim'], fill=self.shade_color(button['fill'], 0.55))
            self.canvas.itemconfig(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            self.canvas.itemconfig(button['text'], fill=button['fg'])
        else:
            self.canvas.itemconfig(button['face'], fill='#4a4743')
            self.canvas.itemconfig(button['rim'], fill='#262422')
            self.canvas.itemconfig(button['highlight'], fill='#66615b')
            self.canvas.itemconfig(button['text'], fill='#9b9690')

    def ensure_point_puck_on_top(self):
        """Keep the white ON puck above every canvas layer."""
        try:
            self.canvas.tag_raise('point_puck')
        except tk.TclError:
            return

    def update_control_states(self):
        betting_enabled = self.accept_bets and not self.animation_running and not self.settlement_running
        for name in ('repeat_button', 'clear_button', 'number_mode_button'):
            tag = getattr(self, name, None)
            if tag:
                self.set_control_button_state(tag, betting_enabled)
        if getattr(self, 'roll_button', None):
            self.set_control_button_state(self.roll_button, betting_enabled and self.roll_ready)
        self.ensure_point_puck_on_top()

    def on_resize(self, event):
        return

    def select_chip(self, value):
        self.selected_chip = float(value)
        for chip_value, items in self.chip_selector_items.items():
            outer, _inner, _text = items
            self.canvas.itemconfig(outer, outline='#ffda42' if chip_value == value else '#544b43',
                                   width=4 if chip_value == value else 2)
        self.canvas.tag_raise('chip_selector')
        self.ensure_point_puck_on_top()

    def toggle_multiplier(self):
        self.multiplier = 1 if self.multiplier == 2 else 2
        for item in self.canvas.find_withtag(self.x2_button):
            if self.canvas.type(item) == 'rectangle':
                self.canvas.itemconfig(item, fill='#9a6b35' if self.multiplier == 2 else '#44343f')

    def restore_point_from_history(self):
        """Restore an unfinished ON point from Craps.json after reopening the game."""
        self.engine.point = None
        if not self.history_data:
            return
        latest = self.history_data[0]
        note = latest.get('note')
        point_after = latest.get('point_after')
        try:
            point_after = int(point_after)
        except (TypeError, ValueError):
            point_after = None
        if note == 'ON' and point_after in CrapsEngine.BOX_NUMBERS:
            self.engine.point = point_after

    def toggle_number_bets_active(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        self.number_bets_active = not self.number_bets_active
        label = '关闭' if self.number_bets_active else '激活'
        fill = '#287c4b' if self.number_bets_active else '#77383b'
        self.update_control_button_style(self.number_mode_button, text=label, fill=fill, fg='white')
        self.update_payout_table()

    def capture_repeatable_bets(self):
        snapshot = []
        for bet_type, value in self.engine.bets.items():
            if bet_type in ('come_points', 'dont_come_points'):
                continue
            if isinstance(value, dict):
                for param, amount in value.items():
                    if amount > 0:
                        snapshot.append((bet_type, param, float(amount)))
            elif value > 0:
                snapshot.append((bet_type, None, float(value)))
        return snapshot

    def repeat_last_bets(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return

        if not self.last_round_bets:
            messagebox.showinfo(
                '没有可重复下注',
                '上一局没有可以重复的下注。'
            )
            return

        simulated = copy.deepcopy(self.engine)
        additions = []
        total_needed = 0.0
        skipped_count = 0

        for bet_type, param, target_amount in self.last_round_bets:
            try:
                current_amount = simulated.current_area_bet(bet_type, param)
            except (KeyError, TypeError):
                skipped_count += 1
                continue

            amount = max(0.0, float(target_amount) - current_amount)
            if amount < self.MIN_BET:
                continue

            # 单格或全桌超过上限时，跳过该下注区域。
            if current_amount + amount > self.MAX_AREA_BET:
                skipped_count += 1
                continue

            if simulated.total_at_risk() + amount > self.MAX_TABLE_BET:
                skipped_count += 1
                continue

            # 使用临时副本测试，避免赔率注被部分加入后才发现不能完整重复。
            trial_engine = copy.deepcopy(simulated)

            try:
                ok, actual, _reason = trial_engine.add_bet(
                    bet_type,
                    amount,
                    param
                )
            except (KeyError, TypeError, ValueError):
                skipped_count += 1
                continue

            # 当前阶段不能下注，或不能完整恢复该区域时，直接跳过。
            if not ok or actual <= 0 or abs(actual - amount) > 0.005:
                skipped_count += 1
                continue

            simulated = trial_engine
            additions.append((bet_type, param, actual))
            total_needed += actual

        if not additions:
            messagebox.showinfo(
                '没有可重复下注',
                '目前没有可重复的可下注区域。'
            )
            return

        if total_needed > self.balance:
            messagebox.showwarning(
                '余额不足',
                '余额不足以重复目前可下注区域的全部下注。'
            )
            return

        self.engine = simulated
        self.balance -= total_needed
        self.undo_stack.extend(additions)
        self.summary_mode = 'bet'
        self.update_display()
        self.save_balance()

        if skipped_count > 0:
            messagebox.showinfo(
                '重复下注',
                f'已完成可下注区域，另有 {skipped_count} 个当前不可下注区域已跳过。'
            )

    def place_bet(self, bet_type, param=None):
        if not self.accept_bets:
            return
        amount = self.selected_chip * self.multiplier
        if amount > self.balance:
            messagebox.showwarning('余额不足', '余额不足以放置该筹码。')
            return

        current = self.engine.current_area_bet(bet_type, param)
        allowed = min(self.MAX_AREA_BET - current, self.MAX_TABLE_BET - self.engine.total_at_risk(), self.balance)
        amount = min(amount, allowed)
        if amount < self.MIN_BET:
            messagebox.showwarning('下注限制', '该下注区或桌面已达到上限。')
            return

        ok, actual, reason = self.engine.add_bet(bet_type, amount, param)
        if not ok:
            messagebox.showwarning('不能下注', reason)
            return

        self.balance -= actual
        self.undo_stack.append((bet_type, param, actual))
        self.summary_mode = 'bet'
        self.update_display()
        self.save_balance()

    def clear_single_bet(self, bet_type, param=None):
        if not self.accept_bets:
            return
        if bet_type in ('pass_line', 'dont_pass') and self.engine.point is not None:
            messagebox.showwarning('不能撤回', 'Point 已建立，该 Line 注属于合约注。')
            return
        current = self.engine.current_area_bet(bet_type, param)
        if current <= 0:
            return
        removed = self.engine.remove_amount(bet_type, current, param)
        self.balance += removed
        self.undo_stack = [entry for entry in self.undo_stack if not (entry[0] == bet_type and entry[1] == param)]
        self.update_display()
        self.save_balance()

    def undo_last_bet(self):
        if not self.accept_bets or not self.undo_stack:
            return
        bet_type, param, amount = self.undo_stack.pop()
        removed = self.engine.remove_amount(bet_type, amount, param)
        self.balance += removed
        self.update_display()
        self.save_balance()

    def double_bets(self):
        if not self.accept_bets:
            return
        snapshot = []
        for bet_type, value in self.engine.bets.items():
            if bet_type in ('come_points', 'dont_come_points'):
                continue
            if isinstance(value, dict):
                for param, amount in value.items():
                    if amount > 0:
                        snapshot.append((bet_type, param, amount))
            elif value > 0:
                snapshot.append((bet_type, None, value))

        total_needed = sum(amount for _, _, amount in snapshot)
        if not snapshot:
            return
        if total_needed > self.balance:
            messagebox.showwarning('余额不足', '余额不足以将全部下注加倍。')
            return

        added = []
        for bet_type, param, amount in snapshot:
            ok, actual, _reason = self.engine.add_bet(bet_type, amount, param)
            if ok and actual > 0:
                self.balance -= actual
                added.append((bet_type, param, actual))
        self.undo_stack.extend(added)
        self.update_display()
        self.save_balance()

    def clear_bets(self):
        if not self.accept_bets:
            return
        refunded, locked = self.engine.clear_removable()
        self.balance += refunded
        self.undo_stack.clear()
        self.update_display()
        self.save_balance()
        if locked:
            messagebox.showinfo('合约注保留', '已退回可撤下注；已锁定的合约注仍留在桌面。')

    def roll_dice(self):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or not self.roll_ready):
            return
        repeatable_bets = self.capture_repeatable_bets()
        if repeatable_bets:
            self.last_round_bets = repeatable_bets
        self.accept_bets = False
        self.roll_ready = False
        self.animation_running = True
        self.undo_stack.clear()
        self.update_control_states()
        fixed = self.developer_dice
        self.developer_dice = None
        self.start_embedded_dice_animation(fixed)

    def start_embedded_dice_animation(self, fixed_dice=None):
        self.animation_fixed_dice = list(fixed_dice) if fixed_dice else None
        self.animation_final_dice = None
        self.animation_start_time = time.time()
        self.animation_duration = (secrets.randbelow(700) + 1900) / 1000.0
        centre_x = (self.animation_panel[0] + self.animation_panel[2]) / 2
        self.canvas.coords(self.animation_status_text, centre_x, self.animation_panel[3] - 38)
        self.canvas.itemconfig(self.animation_status_text, text='骰子转动中，请稍后...', fill='white', anchor='center')
        for item in self.animation_result_dice_items:
            self.canvas.itemconfig(item, state='hidden')
        self.canvas.itemconfig(self.animation_plus_text, state='hidden')
        self.canvas.itemconfig(self.animation_equals_text, state='hidden')
        for item in self.animation_dice_items:
            self.canvas.itemconfig(item, state='normal')
        self.canvas.tag_raise('status_bubble')
        self.canvas.tag_raise(self.animation_status_text)
        self.ensure_point_puck_on_top()
        self.animate_embedded_dice()

    def animate_embedded_dice(self):
        if not self.animation_running:
            return
        elapsed = time.time() - self.animation_start_time
        x0, y0, x1, y1 = self.animation_panel
        centre_x = (x0 + x1) / 2
        centre_y = y0 + 138

        if elapsed < self.animation_duration:
            current = self.animation_fixed_dice or [die.roll() for die in self.dice_objects]
            self.animation_final_dice = list(current)
            bases = (centre_x - 65, centre_x + 65)
            for index, item in enumerate(self.animation_dice_items):
                x = bases[index] + secrets.randbelow(31) - 15
                y = centre_y + secrets.randbelow(31) - 15
                self.canvas.coords(item, x, y)
                self.canvas.itemconfig(item, image=self.dice_images_animation[current[index] - 1], state='normal')
            self.animation_after_id = self.root.after(38, self.animate_embedded_dice)
            return

        if self.animation_final_dice is None:
            self.animation_final_dice = self.animation_fixed_dice or [die.roll() for die in self.dice_objects]
        self.animation_final_dice = sorted(self.animation_final_dice)
        bases = (centre_x - 65, centre_x + 65)
        for index, item in enumerate(self.animation_dice_items):
            self.canvas.coords(item, bases[index], centre_y)
            self.canvas.itemconfig(item, image=self.dice_images_animation[self.animation_final_dice[index] - 1], state='normal')
        total = sum(self.animation_final_dice)
        self.canvas.coords(self.animation_status_text, centre_x - 62, y1 - 38)
        self.canvas.itemconfig(self.animation_status_text, text='本轮结果是:', fill='white', anchor='e')
        for index, item in enumerate(self.animation_result_dice_items):
            self.canvas.itemconfig(item, image=self.dice_images_history[self.animation_final_dice[index] - 1], state='normal')
        self.canvas.itemconfig(self.animation_plus_text, state='normal')
        self.canvas.itemconfig(self.animation_equals_text, text=f'=   {total}', state='normal')
        self.canvas.tag_raise('status_bubble')
        self.canvas.tag_raise(self.animation_status_text)
        self.canvas.tag_raise('animation_result')
        self.animation_after_id = self.root.after(850, self.finish_embedded_dice_animation)

    def finish_embedded_dice_animation(self):
        dice = list(self.animation_final_dice)
        self.animation_running = False
        self.animation_after_id = None
        self.calculate_results(dice)

    @staticmethod
    def snapshot_bet_amount(snapshot, key):
        if not snapshot or not key:
            return 0.0
        bet_type, param = key
        value = snapshot.get(bet_type, 0.0)
        if isinstance(value, dict):
            return float(value.get(param, 0.0))
        return float(value)

    def visual_winning_keys_for_roll(self, result):
        # Every visible winning area flashes, even when no chip was wagered there.
        d1, d2 = result['dice']
        total = result['total']
        point_before = result['point_before']
        keys = set()

        number_bets_working = self.number_bets_active or point_before is not None
        if number_bets_working:
            if total == 7:
                keys.update(('lay', number) for number in CrapsEngine.BOX_NUMBERS)
            elif total in CrapsEngine.BOX_NUMBERS:
                keys.add(('place', total))

        if total in CrapsEngine.HARD_NUMBERS and d1 == d2:
            keys.add(('hard', total))
        if total in (2, 3, 4, 9, 10, 11, 12):
            keys.add(('field', None))
        if total == 7:
            keys.add(('any_seven', None))
        if total in (2, 3, 12):
            keys.add(('craps', None))
        if total in CrapsEngine.CRAP_NUMBERS:
            keys.add(('crap_number', total))
        if total in (2, 3, 11, 12):
            keys.add(('ce', None))

        if point_before is None:
            if total in (7, 11):
                keys.add(('pass_line', None))
            elif total in (2, 3):
                keys.add(('dont_pass', None))
        else:
            if total == point_before:
                keys.add(('pass_line', None))
                keys.add(('pass_odds', None))
            elif total == 7:
                keys.add(('dont_pass', None))
                keys.add(('dont_odds', None))

            if total in (7, 11):
                keys.add(('come', None))
            elif total in (2, 3):
                keys.add(('dont_come', None))

        return keys

    def calculate_results(self, dice):
        self.pre_roll_bets = copy.deepcopy(self.engine.bets)
        result = self.engine.resolve_roll(dice, self.number_bets_active)
        self.balance += result['credit']
        self.last_net = result['net']
        # “上局获胜”统计所有获胜区域的本金 + 获胜奖金；和局退回不计入。
        self.last_win_amount = sum(
            float(outcome.get('return_amount', 0.0))
            for outcome in result.get('outcomes', [])
            if outcome.get('status') == 'win'
        )
        self.last_result = result
        self.summary_mode = 'win'
        self.add_history(result)

        self.flash_winners = {}
        self.flash_original_amounts = {}
        for outcome in result.get('outcomes', []):
            if outcome.get('status') != 'win' or not outcome.get('key'):
                continue
            key = tuple(outcome['key'])
            self.flash_winners[key] = self.flash_winners.get(key, 0.0) + float(outcome.get('return_amount', 0.0))
            self.flash_original_amounts[key] = self.snapshot_bet_amount(self.pre_roll_bets, key)

        for key in self.visual_winning_keys_for_roll(result):
            self.flash_winners.setdefault(key, 0.0)
            self.flash_original_amounts.setdefault(
                key, self.snapshot_bet_amount(self.pre_roll_bets, key)
            )

        # Defensive rule: FIELD never wins on 7 and must never enter the
        # winning-flash collection, even if a future result mapping changes.
        if result.get('total') == 7:
            self.flash_winners.pop(('field', None), None)
            self.flash_original_amounts.pop(('field', None), None)

        self.accept_bets = False
        self.settlement_running = True
        self.flash_mode = None
        self.update_display()
        self.update_control_states()
        self.save_balance()

        if self.flash_winners:
            self.settlement_flash_step = 0
            self.run_settlement_flash()
        else:
            self.settlement_after_id = self.root.after(800, self.finish_settlement)

    def visual_spot_for_key(self, key):
        if key in self.bet_spots:
            return self.bet_spots[key]
        bet_type, param = key
        if bet_type == 'come_points':
            return self.bet_spots.get(('place', param))
        if bet_type == 'dont_come_points':
            return self.bet_spots.get(('lay', param))
        return None

    def run_settlement_flash(self):
        if not self.settlement_running:
            return
        if self.settlement_flash_step >= 6:
            self.finish_settlement()
            return

        self.flash_mode = 'win' if self.settlement_flash_step % 2 == 0 else 'original'
        self.canvas.delete('win_flash_area')

        # 离开白色闪烁阶段时，恢复下注区原有文字颜色。
        if self.flash_mode == 'original':
            self.restore_flash_text_colors()

        if self.flash_mode == 'win':
            flashing_spots = []
            for key in self.flash_winners:
                spot = self.visual_spot_for_key(key)
                if not spot:
                    continue
                x0, y0, x1, y1 = spot['bbox']
                self.canvas.create_rectangle(
                    x0, y0, x1, y1, fill='#ffffff', outline='black', width=2,
                    tags=('win_flash_area', 'settlement_flash')
                )
                flashing_spots.append(spot)

            # 白色闪烁时保留下注区原有文字及骰子图案。
            # 所有原有文字统一改成黑色，骰子图片维持原样。
            for spot in flashing_spots:
                self.raise_spot_content_above_flash(spot)

        self.draw_bet_chips()
        self.canvas.tag_raise('bet_chip')
        self.canvas.tag_raise('controls')
        self.ensure_point_puck_on_top()
        self.settlement_flash_step += 1
        self.settlement_after_id = self.root.after(1000, self.run_settlement_flash)

    def raise_spot_content_above_flash(self, spot):
        """白色闪烁时，将下注区原有文字改成黑色并提升到闪烁层上方。"""
        if not spot:
            return
        x0, y0, x1, y1 = spot['bbox']
        for item_id in self.canvas.find_overlapping(x0 + 1, y0 + 1, x1 - 1, y1 - 1):
            try:
                item_type = self.canvas.type(item_id)
                tags = self.canvas.gettags(item_id)
            except tk.TclError:
                continue

            if 'win_flash_area' in tags or 'bet_chip' in tags or 'hotspot' in tags:
                continue

            # find_overlapping() also returns neighbouring text whose glyph edge
            # barely crosses a shared row border. Only raise/recolour content whose
            # own anchor/centre is inside the flashing betting spot. This prevents
            # the FIELD label from flashing when 7 activates the row below it.
            try:
                coords = self.canvas.coords(item_id)
            except tk.TclError:
                coords = []
            if item_type in ('text', 'image') and len(coords) >= 2:
                item_x, item_y = coords[0], coords[1]
                if not (x0 <= item_x <= x1 and y0 <= item_y <= y1):
                    continue
            elif item_type == 'oval' and len(coords) >= 4:
                item_x = (coords[0] + coords[2]) / 2
                item_y = (coords[1] + coords[3]) / 2
                if not (x0 <= item_x <= x1 and y0 <= item_y <= y1):
                    continue

            if item_type == 'text':
                if item_id not in self.flash_original_text_colors:
                    self.flash_original_text_colors[item_id] = self.canvas.itemcget(item_id, 'fill')
                self.canvas.itemconfig(item_id, fill='black')
                self.canvas.tag_raise(item_id)
            elif item_type == 'oval':
                # FIELD 的 2 和 12 圆圈在白色闪烁时也改为黑色。
                if item_id not in self.flash_original_outline_colors:
                    self.flash_original_outline_colors[item_id] = self.canvas.itemcget(item_id, 'outline')
                self.canvas.itemconfig(item_id, outline='black')
                self.canvas.tag_raise(item_id)
            elif item_type == 'image':
                self.canvas.tag_raise(item_id)

    def restore_flash_text_colors(self):
        """恢复白色闪烁前的下注区文字和 FIELD 圆圈颜色。"""
        for item_id, original_color in list(self.flash_original_text_colors.items()):
            try:
                self.canvas.itemconfig(item_id, fill=original_color)
            except tk.TclError:
                pass
        self.flash_original_text_colors.clear()

        for item_id, original_color in list(self.flash_original_outline_colors.items()):
            try:
                self.canvas.itemconfig(item_id, outline=original_color)
            except tk.TclError:
                pass
        self.flash_original_outline_colors.clear()

    def finish_settlement(self):
        if self.settlement_after_id is not None:
            self.settlement_after_id = None
        self.canvas.delete('win_flash_area')
        self.restore_flash_text_colors()
        self.flash_mode = None
        self.flash_winners = {}
        self.flash_original_amounts = {}
        self.flash_original_text_colors = {}
        self.flash_original_outline_colors = {}
        self.pre_roll_bets = None
        self.settlement_running = False
        self.accept_bets = True
        self.roll_ready = False
        self.update_display()
        self.update_control_states()

        # Betting is open immediately, but the machine keeps the ROLL button
        # disabled for a five-second safety/cool-down period.
        self.roll_cooldown_after_id = self.root.after(2000, self.enable_roll_after_cooldown)

    def enable_roll_after_cooldown(self):
        self.roll_cooldown_after_id = None
        if self.animation_running or self.settlement_running:
            return
        self.roll_ready = True
        self.update_control_states()

    def draw_bet_chips(self):
        c = self.canvas
        c.delete('bet_chip')
        for key, spot in self.bet_spots.items():
            bet_type, param = key
            amount = self.engine.current_area_bet(bet_type, param)
            special_style = None
            if key in self.flash_winners:
                if self.flash_mode == 'win':
                    amount = self.flash_winners[key]
                    special_style = ('#ffffff', '#a51414', '#ffd53d')
                elif self.flash_mode == 'original':
                    amount = self.flash_original_amounts.get(key, amount)
            if amount <= 0:
                continue
            self.draw_chip_stack(
                spot['chip_pos'][0], spot['chip_pos'][1], amount, key,
                override_style=special_style
            )

        # Moved Come and Don't Come chips appear over the number boxes.
        bx, by = self.board_origin
        main_x0, main_x1 = bx, bx + getattr(self, 'board_main_width', 430)
        col_w = (main_x1 - main_x0) / 6
        for idx, number in enumerate(CrapsEngine.BOX_NUMBERS):
            center_x = main_x0 + (idx + 0.5) * col_w
            for key, y, ring in (
                (('come_points', number), by + 52, '#e7d36c'),
                (('dont_come_points', number), by + 15, '#dc4e55'),
            ):
                bet_type, param = key
                amount = self.engine.bets[bet_type][param]
                special_style = None
                if key in self.flash_winners:
                    if self.flash_mode == 'win':
                        amount = self.flash_winners[key]
                        special_style = ('#ffffff', '#a51414', '#ffd53d')
                    elif self.flash_mode == 'original':
                        amount = self.flash_original_amounts.get(key, amount)
                if amount > 0:
                    self.draw_chip_stack(center_x, y, amount, key, ring=ring, override_style=special_style)

        # Point puck above the active number.
        c.delete('point_puck')
        if self.engine.point in CrapsEngine.BOX_NUMBERS:
            idx = CrapsEngine.BOX_NUMBERS.index(self.engine.point)
            center_x = main_x0 + (idx + 0.5) * col_w
            c.create_oval(center_x - 19, by - 31, center_x + 19, by + 7,
                          fill='#f2f2ed', outline='#555', width=2, tags=('point_puck', 'on_puck'))
            c.create_text(center_x, by - 12, text='ON', font=('Arial', 10, 'bold'), fill='#111',
                          tags=('point_puck', 'on_puck'))

        c.tag_raise('controls')
        c.tag_raise('chip_selector')
        c.tag_raise('bet_chip')
        self.ensure_point_puck_on_top()

    def draw_chip_stack(self, x, y, amount, key, ring='#f5d349', override_style=None):
        # A real chip-shaped wager, always drawn above the betting felt.
        if override_style:
            color, text_color, ring = override_style
        else:
            color, text_color = self.amount_chip_style(amount)
        for offset in (5, 2, 0):
            self.canvas.create_oval(x - 18, y - 18 - offset, x + 18, y + 18 - offset,
                                    fill=color, outline='#111', width=2, tags=('bet_chip', f'wager_{key}'))
        self.canvas.create_oval(x - 14, y - 14, x + 14, y + 14, fill=color, outline=ring, width=2,
                                tags=('bet_chip', f'wager_{key}'))
        wager_tag = f'wager_{key}'
        self.canvas.create_text(x, y, text=self.format_chip_amount(amount), font=('Arial', 8, 'bold'),
                                fill=text_color, tags=('bet_chip', wager_tag))
        # 桌面筹码不再单独绑定鼠标事件；由 Canvas 坐标下注入口统一处理。

    @staticmethod
    def format_chip_amount(amount):
        """Format wager/return chips without hiding meaningful fractional values.

        Examples:
            1000      -> 1K
            1200      -> 1.2K
            1250      -> 1.2K+
            1050      -> 1.0K+
            10000     -> 10K
            10500     -> 10K+
            25.5      -> 25.50
        """
        amount = float(amount)
        epsilon = 0.005

        if amount >= 10000:
            whole_k = int(amount // 1000)
            remainder = amount - whole_k * 1000
            suffix = '' if abs(remainder) < epsilon else '+'
            return f'{whole_k}K{suffix}'

        if amount >= 1000:
            whole_k = int(amount // 1000)
            remainder = amount - whole_k * 1000
            if abs(remainder) < epsilon:
                return f'{whole_k}K'

            # 1K 至 10K 以下保留一位 K；无法精确表示时追加 +。
            one_decimal_k = int(amount // 100) / 10.0
            represented_amount = one_decimal_k * 1000
            suffix = '' if abs(amount - represented_amount) < epsilon else '+'
            return f'{one_decimal_k:.1f}K{suffix}'

        if abs(amount - round(amount)) < epsilon:
            return str(int(round(amount)))

        # Any displayed fractional wager/return below 1K keeps two decimal places.
        return f'{amount:.2f}'

    @staticmethod
    def amount_chip_style(amount):
        if amount >= 1000:
            return '#d0a347', 'black'
        if amount >= 500:
            return '#70439a', 'white'
        if amount >= 100:
            return '#202020', 'white'
        if amount >= 25:
            return '#42a95b', 'black'
        if amount >= 5:
            return '#ba3438', 'white'
        if amount >= 1:
            return '#dedede', 'black'
        return '#d8b46a', 'black'

    def update_display(self):
        total_at_risk = self.engine.total_at_risk()
        self.canvas.itemconfig(self.balance_text, text=f'余额: ${self.balance:,.2f}')
        if self.summary_mode == 'win':
            self.canvas.itemconfig(self.total_bet_text, text=f'上局获胜: ${self.last_win_amount:,.2f}')
        else:
            self.canvas.itemconfig(self.total_bet_text, text=f'本局下注: ${total_at_risk:,.2f}')

        phase = '花摇骰' if self.engine.point is None else f'点数: {self.engine.point}'
        self.canvas.itemconfig(self.animation_phase_text, text=phase)

        if not self.animation_running:
            if self.last_result:
                result = self.last_result
                ordered_dice = sorted(result['dice'])
                centre_x = (self.animation_panel[0] + self.animation_panel[2]) / 2
                y1 = self.animation_panel[3]
                self.canvas.coords(self.animation_status_text, centre_x - 62, y1 - 38)
                self.canvas.itemconfig(self.animation_status_text, text='本轮结果是:', fill='white', anchor='e')
                for index, item in enumerate(self.animation_dice_items):
                    self.canvas.itemconfig(item, image=self.dice_images_animation[ordered_dice[index] - 1], state='normal')
                for index, item in enumerate(self.animation_result_dice_items):
                    self.canvas.itemconfig(item, image=self.dice_images_history[ordered_dice[index] - 1], state='normal')
                self.canvas.itemconfig(self.animation_plus_text, state='normal')
            else:
                centre_x = (self.animation_panel[0] + self.animation_panel[2]) / 2
                self.canvas.coords(self.animation_status_text, centre_x, self.animation_panel[3] - 38)
                self.canvas.itemconfig(self.animation_status_text, text='按下"转动"按钮以开始本局', fill='white', anchor='center')
                for item in self.animation_dice_items:
                    self.canvas.itemconfig(item, state='hidden')
                for item in self.animation_result_dice_items:
                    self.canvas.itemconfig(item, state='hidden')
                self.canvas.itemconfig(self.animation_plus_text, state='hidden')
                self.canvas.itemconfig(self.animation_equals_text, state='hidden')

        self.canvas.tag_raise('status_bubble')
        self.canvas.tag_raise(self.animation_status_text)
        self.canvas.tag_raise('animation_result')
        self.update_history_table()
        self.update_payout_table()
        self.draw_bet_chips()
        self.update_control_states()
        self.ensure_point_puck_on_top()

    @staticmethod
    def history_note(point_before, point_after, total):
        if point_before is not None and total == 7 and point_after is None:
            return 'OUT'
        if point_after is not None:
            return 'ON'
        return 'OFF'

    def update_history_table(self):
        self.canvas.delete('history_dynamic')
        geometry = self.history_panel_geometry
        row_height = geometry['row_height']
        for index in range(15):
            y = geometry['header_bottom'] + (index + 0.5) * row_height
            if index >= len(self.history_data):
                for left, right in ((geometry['x0'], geometry['col1']),
                                    (geometry['col1'], geometry['col2']),
                                    (geometry['col2'], geometry['x1'])):
                    self.canvas.create_text((left + right) / 2, y, text='--',
                                            font=('Arial', 11), fill='#7f756d', tags='history_dynamic')
                continue

            record = self.history_data[index]
            dice = record.get('dice', [])
            total = record.get('total', '--')
            note = record.get('note') or self.history_note(
                record.get('point_before'), record.get('point_after'), total if isinstance(total, int) else 0
            )
            left_center = (geometry['x0'] + geometry['col1']) / 2
            if len(dice) == 2 and all(isinstance(value, int) and 1 <= value <= 6 for value in dice):
                self.canvas.create_image(left_center - 30, y, image=self.dice_images_history[dice[0] - 1],
                                         tags='history_dynamic')
                self.canvas.create_text(left_center, y, text='+', font=('Arial', 12, 'bold'),
                                        fill='white', tags='history_dynamic')
                self.canvas.create_image(left_center + 30, y, image=self.dice_images_history[dice[1] - 1],
                                         tags='history_dynamic')
            else:
                self.canvas.create_text(left_center, y, text='-- + --',
                                        font=('Arial', 11), fill='white', tags='history_dynamic')
            self.canvas.create_text((geometry['col1'] + geometry['col2']) / 2, y, text=str(total),
                                    font=('Arial', 12, 'bold'), fill='white', tags='history_dynamic')
            note_color = '#ff6666' if note == 'OUT' else ('#75e795' if note == 'ON' else '#d7d1c8')
            self.canvas.create_text((geometry['col2'] + geometry['x1']) / 2, y, text=note,
                                    font=('Arial', 11, 'bold'), fill=note_color, tags='history_dynamic')

    def calculate_total_outcome_ranges(self):
        """Return possible next-roll totals using gross return (stake + profit) for wins."""
        ranges = {}
        has_bets = self.engine.total_at_risk() > 0
        for total in range(2, 13):
            values = []
            if has_bets:
                for die1 in range(1, 7):
                    die2 = total - die1
                    if not 1 <= die2 <= 6:
                        continue
                    simulated_engine = copy.deepcopy(self.engine)
                    result = simulated_engine.resolve_roll([die1, die2], self.number_bets_active)
                    display_value = 0.0
                    for outcome in result.get('outcomes', []):
                        status = outcome.get('status')
                        if status in ('win', 'push'):
                            display_value += float(outcome.get('return_amount', 0.0))
                        elif status == 'lose':
                            display_value -= float(outcome.get('stake', 0.0))
                    values.append(display_value)
            ranges[total] = (min(values), max(values)) if values else (0.0, 0.0)
        return ranges

    @staticmethod
    def format_signed_money(value):
        if abs(value) < 0.005:
            value = 0.0
        sign = '+' if value >= 0 else '-'
        return f'{sign}${abs(value):,.2f}'

    def update_payout_table(self):
        self.canvas.delete('payout_dynamic')
        geometry = self.payout_panel_geometry
        row_height = geometry['row_height']
        ranges = self.calculate_total_outcome_ranges()
        has_bets = self.engine.total_at_risk() > 0

        for index, total in enumerate(range(2, 13)):
            y = geometry['header_bottom'] + (index + 0.5) * row_height
            self.canvas.create_text((geometry['x0'] + geometry['col1']) / 2, y,
                                    text=str(total), font=('Arial', 18, 'bold'),
                                    fill='white', tags='payout_dynamic')
            _low, high = ranges[total]
            if not has_bets:
                text = '—'
                color = '#8b8178'
            else:
                # When several dice combinations create a range, only show the
                # maximum possible result, including returned principal.
                text = self.format_signed_money(high)
                color = '#76e797' if high > 0 else ('#ff7474' if high < 0 else 'white')
            self.canvas.create_text((geometry['col1'] + geometry['x1']) / 2, y,
                                    text=text, font=('Arial', 13, 'bold'),
                                    fill=color, tags='payout_dynamic')

    def get_history_file(self):
        # Match the original Sicbo path convention: project_root/A_Logs/Json/<game>.json
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        logs_dir = os.path.join(project_root, 'A_Logs', 'Json')
        try:
            os.makedirs(logs_dir, exist_ok=True)
        except OSError:
            # Fallback keeps the game usable if the project parent is read-only.
            logs_dir = os.path.join(current_dir, 'A_Logs', 'Json')
            os.makedirs(logs_dir, exist_ok=True)
        return os.path.join(logs_dir, 'Craps.json')

    def load_history_data(self):
        try:
            with open(self.history_file, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

    def add_history(self, result):
        note = self.history_note(result['point_before'], result['point_after'], result['total'])
        self.history_data.insert(0, {
            'time': datetime.now().isoformat(timespec='seconds'),
            'dice': sorted(result['dice']),
            'total': result['total'],
            'point_before': result['point_before'],
            'point_after': result['point_after'],
            'note': note,
            'net': round(result['net'], 2),
        })
        self.history_data = self.history_data[:self.MAX_RECORDS]
        try:
            with open(self.history_file, 'w', encoding='utf-8') as handle:
                json.dump(self.history_data, handle, ensure_ascii=False, indent=2)
        except OSError as exc:
            print(f'保存 Craps 历史记录失败：{exc}')

    def show_developer_input_dialog(self):
        win = tk.Toplevel(self.root)
        win.title('固定两颗骰子')
        win.geometry('330x140')
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        tk.Label(win, text='输入两个 1–6 的数字；留空恢复随机：', font=('Arial', 11)).pack(pady=(14, 5))
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
                messagebox.showwarning('输入错误', '请输入两个 1 到 6 的整数。', parent=win)
                return
            if len(dice) != 2 or not all(1 <= item <= 6 for item in dice):
                messagebox.showwarning('输入错误', '请输入两个 1 到 6 的整数。', parent=win)
                return
            self.developer_dice = dice
            win.destroy()

        tk.Button(win, text='确定', width=12, command=confirm).pack(pady=10)
        win.bind('<Return>', lambda _event: confirm())
        win.bind('<Escape>', lambda _event: win.destroy())

    def save_balance(self):
        if self.username:
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def cancel_pending_callbacks(self):
        for after_id in (self.animation_after_id, self.settlement_after_id, self.roll_cooldown_after_id):
            if after_id is not None:
                try:
                    self.after_cancel(after_id)
                except (tk.TclError, ValueError):
                    pass
        self.animation_after_id = None
        self.settlement_after_id = None
        self.roll_cooldown_after_id = None

    def on_close(self):
        """保存余额并返回上一个 Tk 页面，行为与 Caribbean Stud Poker 一致。"""
        self.exit_game()

    def exit_game(self):
        """安全结束本游戏页面，并通过 on_back 返回赌场游戏目录。"""
        if self._closing:
            return
        self._closing = True

        # 即使正在摇骰或结算，也允许关闭并返回上一页。
        self.cancel_pending_callbacks()
        self.animation_running = False
        self.settlement_running = False
        self.accept_bets = False
        self.roll_ready = False

        # 清除仍在显示的临时图层。
        try:
            self.hide_bet_tooltip()
            self.canvas.delete('win_flash_area')
            self.restore_flash_text_colors()
        except tk.TclError:
            pass

        # 离开桌面时退回仍留在桌上的本金。
        outstanding_bets = self.engine.total_at_risk()
        if outstanding_bets > 0:
            self.balance += outstanding_bets
        self.engine.bets = self.engine.new_bets()

        self.final_balance = float(self.balance)
        try:
            self.save_balance()
        except Exception:
            pass

        # 嵌入运行时由赌场目录提供 on_back；独立运行时由 main() 关闭窗口。
        if callable(self.on_back):
            self.on_back(self.final_balance)


def main(
    parent=None,
    balance=10000,
    user=None,
    on_back=None,
    on_balance_change=None,
):
    """
    Open Craps either as an embedded Frame or as an independent window.

    Embedded use:
        main(parent=root, balance=10000, user='name', on_back=callback)

    Independent use:
        main(balance=10000, user='name')

    Legacy independent calls such as main(10000, 'name') are also accepted.
    """
    # Backward compatibility for the old independent main(balance, username) form.
    if parent is not None and not isinstance(parent, tk.Misc):
        legacy_balance = parent
        legacy_user = balance if isinstance(balance, str) and user is None else user
        parent = None
        balance = legacy_balance
        user = legacy_user

    if parent is not None:
        return BubbleCrapsGame(
            parent=parent,
            balance=balance,
            user=user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    root.title('花摇骰')

    result = {'balance': float(balance)}

    def close_standalone(final_balance):
        result['balance'] = float(final_balance)
        try:
            root.destroy()
        except tk.TclError:
            pass

    game = BubbleCrapsGame(
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
    print(f'游戏结束，最终余额：${final_balance:,.2f}')