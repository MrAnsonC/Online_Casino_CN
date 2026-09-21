from __future__ import annotations
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
import random
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

try:
    from .small_games import EmbeddedGamePage
except ImportError:
    try:
        from small_games import EmbeddedGamePage
    except ImportError:
        EmbeddedGamePage = None


VERSION = "Bingo-R13-close-and-repeat"


# ===== 在 Theme 里面新增这两个颜色 =====

class Theme:
    APP_BG = "#C8C1B7"
    PANEL = "#E7E1D8"
    PANEL_ALT = "#DCD5CB"
    PANEL_HOVER = "#D1C9BE"
    CANVAS_BG = "#BFD0C1"
    BORDER = "#9A9185"
    BORDER_SOFT = "#B9B0A5"
    TEXT = "#252A2E"
    TEXT_MUTED = "#596169"
    TEXT_DIM = "#777E83"

    ACCENT = "#345E73"
    ACCENT_HOVER = "#294A5A"
    ACCENT_SOFT = "#B8CAD2"

    CYAN = "#276E78"
    GREEN = "#4E7355"
    GREEN_HOVER = "#3D5C43"
    RED = "#A84D4D"
    RED_HOVER = "#873D3D"
    AMBER = "#A36B22"

    WIN = "#A9C4A5"
    MISS = "#D7A6A0"
    SELECTED = "#B7CCD5"
    DEFAULT_CELL = "#DDD7CE"

    # 实时赔率表
    ODDS_PROGRESS = "#B9DDEA"   # 已经过的命中格：浅蓝色
    ODDS_CURRENT = "#D9B75B"    # 当前命中格：金色

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"

CHIP_SPECS = [
    (100, '#202020', '100'), (500, '#d780c0', '500'),
    (1000, '#ab0058', '1K'), (5000, '#ba3438', '5K'),
    (10000, '#70439a', '10K'), (50000, '#2e7542', '50K'),
]
CHIP_CONFIGS = tuple((label,str(amount),color,'black' if amount==500 else 'white')
                     for amount,color,label in CHIP_SPECS)
MAX_CARD_BET = 100000


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Account/saving_data.json")


def load_user_data() -> list:
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_user_data(users: list) -> None:
    try:
        with open(get_data_file_path(), "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=4)
    except OSError:
        pass


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{new_balance:.2f}"
            save_user_data(users)
            return






# ===== Bingo rules: pure engine, independent from Tk =====
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import math

# Column ranges follow the requested vertical (打栋) layout.
# Global maximum means two global cells per card; activated values multiply.
LINES = tuple(tuple(r * 5 + c for c in range(5)) for r in range(5)) + \
        tuple(tuple(r * 5 + c for r in range(5)) for c in range(5)) + \
        ((0, 6, 12, 18, 24), (4, 8, 12, 16, 20))
LINE_NAMES = tuple(f'横{n+1}' for n in range(5)) + tuple(f'竖{n+1}' for n in range(5)) + ('左斜', '右斜')
RNG = random.SystemRandom()

# Calibrated for the settlement rules below: approximately 97% RTP per mode.
# Extras exclude the center: six Bernoulli trials, then clamp the count to 2.
# Changing weights, caps, fallback placement, or payouts requires recalibration.
MIN_EXTRA_REWARDS = 2
MAX_EXTRA_REWARDS = 6
EXTRA_REWARD_CHANCE = {'免费': 0.44134, '倍数': 0.54931}
REWARD_WEIGHTS = {'free': 40, 'standard': 35, 'line': 10, 'global': 15}


def money(value):
    result = Decimal(str(value))
    if not result.is_finite() or result < 0 or result != result.quantize(Decimal('0.01')):
        raise ValueError('金额必须是非负数，最多两位小数')
    return result


@dataclass
class BingoCard:
    numbers: tuple
    free: set = field(default_factory=set)
    standard: dict = field(default_factory=dict)
    global_cells: dict = field(default_factory=dict)
    line_bonus: dict = field(default_factory=dict)
    extras_count: int = 0

    @classmethod
    def generate(cls, rng=RNG):
        columns = [rng.sample(range(c * 12 + 1, c * 12 + 13), 5) for c in range(5)]
        return cls(tuple(columns[c][r] for r in range(5) for c in range(5)))

    def decorate(self, option, rng=RNG):
        self.free.clear(); self.standard.clear(); self.global_cells.clear(); self.line_bonus.clear()
        if option == '免费':
            self.free.add(12)
        elif option == '倍数':
            kind, value = rng.choice((('global', 2), ('global', 3), ('standard', 10), ('standard', 20)))
            (self.global_cells if kind == 'global' else self.standard)[12] = value
        else:
            raise ValueError('未知选项')
        rolled_extras = sum(
            rng.random() < EXTRA_REWARD_CHANCE[option]
            for _ in range(MAX_EXTRA_REWARDS)
        )
        self.extras_count = max(MIN_EXTRA_REWARDS, rolled_extras)
        cells = list(range(25)); cells.remove(12)
        rng.shuffle(cells)
        for _ in range(self.extras_count):
            cell = rng.choice([p for p in cells if p not in self.free and p not in self.standard and p not in self.global_cells])
            covered = {p for line in self.line_bonus for p in LINES[line]}
            kinds = ['free']
            if len(self.line_bonus)<4:kinds.append('line')
            if cell not in covered:
                if len(self.standard)<5:kinds.append('standard')
                if len(self.global_cells) < 2:
                    kinds.append('global')
            kind = rng.choices(kinds, weights=[REWARD_WEIGHTS[k] for k in kinds], k=1)[0]
            if kind == 'free' and any(len(set(line) & (self.free | {cell})) > 2 for line in LINES):
                kind = 'line'
            if kind == 'line':
                occupied = set(self.standard) | set(self.global_cells)
                eligible = [i for i, line in enumerate(LINES)
                            if cell in line and i not in self.line_bonus and not occupied.intersection(line)]
                if eligible and len(self.line_bonus)<4:
                    self.line_bonus[rng.choice(eligible)] = rng.choice((20, 50))
                    continue
                # Relocate this reward outside gold lines if its selected cell is unavailable.
                available = [p for p in range(25) if p != 12 and p not in covered
                             and p not in self.free and p not in occupied]
                if available and len(self.standard)<5:
                    self.standard[rng.choice(available)] = rng.choice((10, 20))
                    continue
                eligible_free = [p for p in range(25) if p != 12 and p not in self.free
                                 and p not in occupied and all(len(set(line) & (self.free | {p})) <= 2 for line in LINES)]
                self.free.add(rng.choice(eligible_free))
            elif kind == 'free':
                self.free.add(cell)
            elif kind == 'global':
                self.global_cells[cell] = rng.choice((2, 3))
            else:
                self.standard[cell] = rng.choice((10, 20))

    def marked(self, drawn):
        return self.free | {i for i, n in enumerate(self.numbers) if n in drawn}

    def settle(self, stake, drawn, bonus_number=None, bonus_value=0):
        stake = money(stake)
        drawn = set(drawn)
        marked = self.marked(drawn)
        global_factor = math.prod(v for i, v in self.global_cells.items() if self.numbers[i] in drawn)
        details = []
        for index, line in enumerate(LINES):
            if not set(line) <= marked:
                continue
            standard_factor = 0
            factor = self.line_bonus.get(index, 0)
            if index not in self.line_bonus:
                standard_factor = sum(self.standard.get(i, 0) for i in line if self.numbers[i] in drawn)
                factor += standard_factor
            # Final ball multiplies a designated line bonus; on other lines it is standard.
            if bonus_number is not None and bonus_number in drawn and any(self.numbers[i] == bonus_number and i not in self.free for i in line):
                if index in self.line_bonus:
                    factor *= bonus_value
                else:
                    factor += bonus_value
            factor = factor or 3  # 2:1 includes return of stake => 3x total return.
            applied_global_factor = global_factor
            if standard_factor:
                # Independent rewards ADD the activated global product.
                # With no activated global cell, add zero (not the empty product 1).
                # Examples: 20 + 2 = 22; 20 + (2 * 3) = 26.
                factor += global_factor if global_factor > 1 else 0
                applied_global_factor = 1
            amount = stake * factor * applied_global_factor
            details.append((index, factor, applied_global_factor, amount))
        return sum((d[3] for d in details), Decimal('0')), details


class BingoRoundController:
    WINDOW_WIDTH = 1150
    WINDOW_HEIGHT = 750

    def __init__(self, root, initial_balance, username, on_balance_change=None):
        self.root, self.username = root, username
        self.balance = money(initial_balance)
        self.on_balance_change = on_balance_change
        self.game_active = False
        self.closed = False
        self.jobs = set()
        self.cards = [BingoCard((None,) * 25) for _ in range(4)]
        self.drawn = []
        self.results = []
        self.total_won = Decimal('0')
        self.selected = 0
        self.chip_amount = Decimal('100')
        self.chip_index = 0
        self.motion_count = 0
        self.motion_widgets = set()
        self.phase = 0
        self.reveal_columns = 0
        self.reveal_center = False
        self.reveal_lines = set()
        self.reveal_cells = set()
        self.machine_running = False
        self.exit_ball = None
        self.bonus_number = None
        self.bonus_value = 0
        self.round_stakes = [Decimal('0')] * 4
        self.previous_stakes = (Decimal('0'),) * 4
        self.settled = True
        self.last_return = Decimal('0')
        self.reset_job = None
        self.controls = []
        self.stakes = [tk.StringVar(root, '0') for _ in range(4)]
        self.options = [tk.StringVar(master=root, value=mode)
                        for mode in ('免费', '免费', '倍数', '倍数')]
        if isinstance(root, (tk.Tk, tk.Toplevel)):
            root.title('Bingo 宾果游戏'); root.geometry('1150x750'); root.resizable(False, False)
            root.protocol('WM_DELETE_WINDOW', self.on_closing)
        root.configure(bg=Theme.APP_BG, width=1150, height=750)
        root.bind('<Destroy>', self._destroyed, add='+')
        self.create_widgets()
        self.refresh()

    def later(self, delay, callback):
        holder = []
        def run():
            self.jobs.discard(holder[0])
            if not self.closed:
                callback()
        holder.append(self.root.after(delay, run))
        self.jobs.add(holder[0])
        return holder[0]





    def read_stakes(self):
        return [money(v.get().strip()) for v in self.stakes]





    def clear_bets(self):
        if not self.game_active and not self.motion_count:
            for var in self.stakes:
                var.set('0')
            self.update_bet_spots()


    def start(self):
        if self.game_active or self.motion_count:
            return
        try:
            stakes = self.read_stakes()
            total = sum(stakes)
            if any(stake>MAX_CARD_BET for stake in stakes):
                raise ValueError('每张卡下注上限为100K')
            if total > self.balance:
                raise ValueError('余额不足')
        except (ValueError, InvalidOperation):
            messagebox.showwarning('无法开始', '每张最高100K，且总额不超过余额；可不下注开始。', parent=self.root)
            return
        self.round_stakes = stakes
        self.previous_stakes = tuple(
            stake if stake > 0 else previous
            for stake, previous in zip(stakes, self.previous_stakes)
        )
        self.game_active = True; self.settled = False
        self.drawn = []; self.results = []; self.bonus_number = None; self.bonus_value = 0
        self.sequence = RNG.sample(range(1, 61), 20)
        self.cards = [BingoCard.generate() if stake else BingoCard((None,) * 25)
                      for stake in stakes]
        for card, option in zip(self.cards, self.options):
            card.decorate(option.get())
        self.balance -= total
        self.save_balance()
        for control in self.controls:
            control.configure(state=tk.DISABLED)
        for i, label in enumerate(self.bet_labels):
            label.configure(text=f'下注 ${stakes[i]:.2f}' if stakes[i] else '本局未参与', bg='#284A48', fg='#F8E6B1')
        self.begin_reveal()

    def animate(self):
        if not self.game_active or self.settled or not self.machine_running:
            return
        self.phase += 0.23; self.render_machine()
        self.later(60, self.animate)


    def begin_reveal(self):
        self.reveal_columns=0; self.reveal_center=False
        self.reveal_lines=set(); self.reveal_cells=set()
        self.machine_running=False; self.exit_ball=None
        self.refresh()
        for column in range(1,6):
            self.later(column*120, lambda n=column:self.reveal_column(n))
        self.later(800,self.show_center)
        lines=[(i,line) for i,card in enumerate(self.cards) for line in sorted(card.line_bonus)]
        for j,item in enumerate(lines):
            self.later(1000+round(650*(j+1)/len(lines)),lambda item=item:self.show_line(item))
        cells=[(i,cell) for i,card in enumerate(self.cards)
               for cell in sorted(card.free|set(card.standard)|set(card.global_cells)) if cell!=12]
        for j,item in enumerate(cells):
            self.later(1650+round(350*(j+1)/len(cells)),lambda item=item:self.show_cell(item))
        self.later(2000,self.reveal_complete)

    def reveal_column(self,n):
        self.reveal_columns=n;self.refresh()

    def show_center(self):
        self.reveal_center=True;self.refresh()

    def show_line(self,item):
        self.reveal_lines.add(item);self.refresh()

    def show_cell(self,item):
        self.reveal_cells.add(item);self.refresh()

    def reveal_complete(self):
        self.refresh();self.later(3000,self.begin_drawing)

    def begin_drawing(self):
        self.machine_running=True
        self.animate();self.later(RNG.randint(800,2200),self.draw_next)

    def reveal_bonus(self):
        self.bonus_value=RNG.choice((2,5,10,20))
        self.render_machine();self.later(RNG.randint(2000,4000),self.draw_next)

    def draw_next(self):
        if self.settled or not self.game_active or len(self.drawn)>=20:return
        self.drawn.append(self.sequence[len(self.drawn)])
        if len(self.drawn)==20:
            self.bonus_number=self.drawn[-1]
            self.machine_running=False
        self.refresh();self.animate_exit(self.drawn[-1],0)
        if len(self.drawn)<19:
            self.later(RNG.randint(800,2200),self.draw_next)
        elif len(self.drawn)==19:
            self.later(2000,self.reveal_bonus)
        # Final settlement follows the final ball's 400ms exit animation.

    def animate_exit(self,number,step):
        self.exit_ball=(number,step/10)
        self.render_machine()
        if step<10:
            self.later(40,lambda:self.animate_exit(number,step+1))
        else:
            self.exit_ball=None
            self.render_machine()
            if len(self.drawn)==20:self.finish_round()

    def finish_round(self):
        if self.settled:
            return
        self.settled = True
        self.results = [card.settle(stake, self.drawn, self.bonus_number, self.bonus_value) if stake else (Decimal('0'), [])
                        for card, stake in zip(self.cards, self.round_stakes)]
        self.last_return = sum((r[0] for r in self.results), Decimal('0'))
        self.balance += self.last_return; self.total_won += self.last_return
        self.save_balance()
        self.total_label.configure(text=f'上局获胜  ${self.last_return:,.2f}')
        self.start_button.configure(text='再来一局',state=tk.NORMAL)
        self.canvas.itemconfigure('start',state='normal')
        self.reset_job=self.later(120000,self.next_round)
        self.refresh(); self.flash(0)


    def unlock_after_return(self):
        if self.motion_count:
            self.later(50, self.unlock_after_return)
            return
        # Keep only the balance, session total and explicit repeat-bet snapshot.
        self.cards = [BingoCard((None,) * 25) for _ in range(4)]
        self.drawn = []; self.results = []; self.sequence = []
        self.bonus_number = None; self.bonus_value = 0; self.phase = 0
        self.round_stakes = [Decimal('0')] * 4; self.last_return = Decimal('0')
        self.pending_visual = [Decimal('0')] * 4
        self.returning.clear()
        self.reveal_columns=0; self.reveal_center=False
        self.reveal_lines=set(); self.reveal_cells=set()
        self.machine_running=False; self.exit_ball=None
        for value in self.stakes:
            value.set('0')
        self.canvas.delete('resting_chips')
        self.update_bet_spots(); self.refresh()
        self.game_active = False
        for control in self.controls:
            control.configure(state=tk.NORMAL)
        self.start_button.configure(text='开始抽奖')
        for tag in ('clear','repeat','start'):self.canvas.itemconfigure(tag,state='normal')

    def show_rules(self):
        # Same native information-dialog UI and section/bullet format as Baccarat_Special.
        text = (
            '【基本规则】\n'
            '• 四张5×5卡；横、竖及两条对角线均可中奖。\n'
            '• 五列范围为1–12、13–24、25–36、37–48、49–60。\n'
            '• 开始后仅下注卡显示号码；未下注卡只显示奖励，可零下注观看。\n\n'
            '【奖励与倍数】\n'
            '• 中心选免费则显示∞，选倍数则随机全局或独立倍数。\n'
            '• 中心以外保底2个额外奖励，最多6个；整线奖励按一项计。\n'
            '• 每条横、竖、对角线最多2个免费格，包含中心免费格。\n'
            '• 首次默认卡1/2免费、卡3/4倍数；之后保留玩家选择。\n'
            '• 每卡全局最多2个、整线最多4条、独立最多5个，含中心。\n'
            '• 灰色全局2/3×命中后生效；多个全局先相乘。\n'
            '• 金色独立10/20×：在线内命中才生效，多个独立倍数相加。\n'
            '• 整线20/50×：整线命中生效，不叠加普通独立奖励。\n\n'
            '【返还计算】\n'
            '• 普通线返还下注×3；各中奖线的返还累加。\n'
            '• 最后一球随机2/5/10/20×，只作用于包含该数字的中奖线。\n'
            '• 若最后一球完成带整线倍数的线：下注×整线倍数×最后球倍数。\n'
            '• 例如下注100，20×整线被最后20×球完成：100×20×20＝40,000。\n'
            '• 其他线按独立倍数相加；免费格不领取最后球的加倍。\n'
            '• 有独立奖励的线：先合计独立及最后球奖励，再加已触发的全局倍数。\n'
            '• 例如独立20×遇全局2×返还22倍；全局2×和3×都命中则返还26倍。\n'
            '• 无独立奖励的普通线及整线奖励仍乘全局倍数；普通3×遇全局2×返还6倍。\n'
            '• 所有返还倍数均含本金；未下注卡不产生返还。\n\n'
            '【下注与操作】\n'
            '• 每张卡上限100K；左键下注区累计下注，右键清除该卡下注。\n'
            '• 清除下注清空本局；开始时逐卡记住非零下注，零下注不覆盖记录。\n'
            '• 重复上局下注恢复每张卡最近记录的非零金额。\n'
            '• 结算保留120秒；再来一局可提前清空并进入下注。\n'
            '• K/M为千/百万；“+”表示有未显示尾数，结算金额不截断。'
        )
        messagebox.showinfo('宾果 BINGO 玩法说明', text, parent=self.root.winfo_toplevel())

    def save_balance(self):
        update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def _destroyed(self, event):
        if event.widget is not self.root or self.closed:
            return
        # Host destruction cannot strand an already debited round: settle its committed draw.
        if not self.settled:
            bonus = self.bonus_value or RNG.choice((2,5,10,20))
            credit = sum((c.settle(s, self.sequence, self.sequence[-1], bonus)[0]
                          for c, s in zip(self.cards, self.round_stakes)), Decimal('0'))
            self.balance += credit; self.settled = True
            self.save_balance()
        self.closed = True
        for job in self.jobs:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self.jobs.clear()
        self.motion_widgets.clear()
        self.motion_count = 0

    def on_closing(self):
        # A standalone Tk owns the application event loop. Destroy it immediately;
        # the existing Destroy handler settles any already-debited round once.
        if isinstance(self.root, tk.Tk):
            self.save_balance()
            self.root.destroy()
            return
        if self.game_active:
            messagebox.showinfo('开奖中', '请等待本局开奖及自动结算完成。', parent=self.root)
            return
        self.save_balance()
        finish = getattr(self.root, 'finish', None)
        if callable(finish):
            finish(float(self.balance))
        else:
            self.root.destroy()


class CanvasControl:
    """Canvas-native control: shares a surface with chips, so motion has no opaque box."""
    def __init__(self, canvas, tag, rect, text, command=None):
        self.canvas, self.tag, self.rect, self.text = canvas, tag, rect, text
        self.enabled = True
        if command:
            canvas.tag_bind(tag, '<Button-1>', lambda e: command() if self.enabled else None)
            canvas.tag_bind(tag, '<Enter>', lambda e: canvas.configure(cursor='hand2' if self.enabled else ''))
            canvas.tag_bind(tag, '<Leave>', lambda e: canvas.configure(cursor=''))

    def configure(self, **kw):
        if 'state' in kw:
            self.enabled = kw['state'] != tk.DISABLED
            self.canvas.itemconfigure(self.tag, state='normal' if self.enabled else 'disabled')
        if 'text' in kw:
            self.canvas.itemconfigure(self.text, text=kw['text'])
        if 'fg' in kw:
            self.canvas.itemconfigure(self.text, fill=kw['fg'])
        if 'bg' in kw and self.rect:
            self.canvas.itemconfigure(self.rect, fill=kw['bg'])


class BingoGame(BingoRoundController):
    BG = '#10191E'
    WHITE = '#FFFFFF'
    INK = '#182C36'
    TEAL = '#67DEBF'
    GOLD = '#F1CC66'

    def create_widgets(self):
        self.root.configure(bg=self.BG)
        self.canvas = tk.Canvas(self.root, width=1150, height=750, bg=self.BG, highlightthickness=0)
        self.canvas.pack()
        self.shell = self.canvas
        self.chip_serial = 0
        self.bet_revision = [0]*4
        self.pending_visual = [Decimal('0')]*4
        self.returning = set()
        self.spot_colors = ['#E7F2EE']*4
        self.spot_texts = ['点击下注']*4
        self.card_x = [22+i*282 for i in range(4)]
        self.chip_sources = [(302+i*53,711) for i in range(6)]
        self.spot_positions = [(x+130,611) for x in self.card_x]
        c = self.canvas
        self.round_rect(22,10,64,53,7,'#E6F7F1','bingo_icon')
        c.create_rectangle(27,15,59,23,fill='#278469',outline='',tags='bingo_icon')
        c.create_text(43,19,text='BINGO',fill='white',font=(Theme.FONT,6,'bold'),tags='bingo_icon')
        for row in range(3):
            for col in range(3):
                x,y=32+col*11,29+row*8
                c.create_oval(x-3,y-3,x+3,y+3,fill='#DE454C' if row==col else '#73998F',outline='',tags='bingo_icon')
        c.create_text(78,31,text='宾果 BINGO',anchor='w',fill=self.WHITE,font=(Theme.FONT_CJK,21,'bold'))
        self.balance_label = self.surface_label('balance',804,10,324,44,'',self.BG,self.WHITE,18)
        c.create_line(22,65,1128,65,fill='#29383F')
        c.create_rectangle(22,84,297,190,fill='#192930',outline='#42616F')
        c.create_line(22,130,297,130,fill='#42616F')
        c.create_text(159,107,text='下注上限',fill=self.WHITE,font=(Theme.FONT_CJK,15,'bold'))
        c.create_text(159,160,text='每张卡  100K',fill=self.TEAL,font=(Theme.FONT_CJK,17,'bold'))
        self.bet_labels=[]
        self.option_controls=[]
        for i,x in enumerate(self.card_x):
            self.round_rect(x,253,x+260,650,16,'#FAFCFD',tag=f'card{i}')
            c.create_text(x+17,278,text=f'卡牌 {i+1:02}',anchor='w',fill=self.INK,font=(Theme.FONT_CJK,12,'bold'))
            c.create_text(x+242,278,text='B I N G O',anchor='e',fill='#789099',font=(Theme.FONT,10,'bold'))
            c.create_line(x+16,296,x+244,296,fill='#E2E9EB')
            for j,mode in enumerate(('免费','倍数')):
                btn = self.surface_label(f'opt{i}_{j}',x+16+j*116,546,112,29,mode,'#E7EEF0','#4B626D',10,
                                         lambda i=i,m=mode:self.set_option(i,m),center=True)
                self.controls.append(btn); self.option_controls.append((i,mode,btn))
            spot = self.surface_label(f'bet{i}',x+12,586,236,51,'', '#E7F2EE',self.INK,11,
                                      lambda i=i:self.place_bet(i),center=True)
            self.bet_labels.append(spot)
            c.tag_bind(f'bet{i}', '<Button-3>', lambda e,i=i:self.clear_card_bet(i))
            if sys.platform == 'darwin':
                c.tag_bind(f'bet{i}', '<Button-2>', lambda e,i=i:self.clear_card_bet(i))
        c.create_line(22,673,1128,673,fill='#29383F')
        self.total_label = self.surface_label('total',22,690,252,42,'本局下注  $0.00',self.BG,self.WHITE,16)
        for j,conf in enumerate(CHIP_CONFIGS):
            x,y=self.chip_sources[j]
            tag=f'rack{j}'
            self.draw_chip(x,y,Decimal(conf[1]),tag)
            c.tag_bind(tag,'<Button-1>',lambda e,a=conf[1]:self.choose_chip(a))
        for tag,x,w,text,fn in (
            ('clear',654,112,'清除下注',self.clear_bets),
            ('repeat',776,146,'重复上局下注',self.repeat_bets)):
            btn=self.surface_label(tag,x,690,w,42,text,'#22323B','#D9E6EC',14,fn,center=True)
            self.controls.append(btn)
        btn=self.surface_label('start',932,690,196,42,'开始抽奖',self.TEAL,self.INK,16,self.primary_action,center=True)
        self.controls.append(btn)
        self.start_button=btn
        self.surface_label('instructions',601,688,43,45,'❓','#315b72','white',19,self.show_rules,center=True)
        self.paint_options();self.paint_rack();self.update_bet_spots();self.render_machine()

    def round_rect(self,x1,y1,x2,y2,r,fill,tag):
        return self.canvas.create_polygon(x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,
            x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1,smooth=True,splinesteps=20,
            fill=fill,outline='',tags=tag)

    def surface_label(self,tag,x,y,w,h,text,bg,fg,size,command=None,center=False):
        rect=self.round_rect(x,y,x+w,y+h,8,bg,tag)
        label=self.canvas.create_text(x+w/2 if center else x+2,y+h/2,text=text,
            anchor='center' if center else 'w',fill=fg,font=(Theme.FONT_CJK,size),tags=tag)
        return CanvasControl(self.canvas,tag,rect,label,command)

    @staticmethod
    def compact(amount):
        value=money(amount)
        unit=Decimal('1000000') if value>=1000000 else Decimal('1000') if value>=1000 else None
        if unit:
            tenths=(value*10//unit)/10
            text=format(tenths,'f').rstrip('0').rstrip('.') if '.' in format(tenths,'f') else str(tenths)
            suffix='M' if unit==1000000 else 'K'
            return text+suffix+('+' if value!=tenths*unit else '')
        return format(value,'f').rstrip('0').rstrip('.') if '.' in format(value,'f') else str(value)

    def draw_chip(self,x,y,amount,tag):
        c=self.canvas
        conf=next((conf for conf in reversed(CHIP_CONFIGS) if amount>=Decimal(conf[1])),CHIP_CONFIGS[0])
        # Baccarat: compact centred chip, dark outer rim and denomination-coloured face.
        radius = 20 if isinstance(tag,tuple) and 'resting_chips' in tag else 19
        c.create_oval(x-radius,y-radius,x+radius,y+radius,fill='#292522',outline='#151311',width=1,tags=tag)
        c.create_oval(x-radius+3,y-radius+3,x+radius-3,y+radius-3,fill=conf[2],outline='#E2DDD5',width=1,tags=tag)
        c.create_text(x,y,text=self.compact(amount),font=('Arial',11,'bold'),fill=conf[3],tags=tag)

    def paint_rack(self):
        self.canvas.delete('selected_chip')
        x,y=self.chip_sources[self.chip_index]
        self.canvas.create_oval(x-23,y-23,x+23,y+23,outline=self.TEAL,width=2,tags='selected_chip')

    def paint_options(self):
        for i,mode,btn in self.option_controls:
            active=self.options[i].get()==mode
            btn.configure(text=('✓ ' if active else '')+('加倍' if mode=='倍数' else '免费'),
                          bg='#203F45' if active else '#E7EEF0',fg='white' if active else '#4B626D')

    def set_option(self,index,mode):
        if not self.game_active:
            self.options[index].set(mode);self.paint_options()

    def select(self,index):
        if not self.game_active:self.selected=index

    def choose_chip(self,amount):
        if self.game_active:return
        self.chip_amount=money(amount)
        self.chip_index=next(i for i,v in enumerate(CHIP_CONFIGS) if v[1]==amount)
        self.paint_rack()

    def repeat_bets(self):
        if self.game_active or self.motion_count:
            return
        if not any(self.previous_stakes):
            return
        total = sum(self.previous_stakes)
        if any(v>MAX_CARD_BET for v in self.previous_stakes):
            messagebox.showwarning('下注上限', '每张卡下注上限100K。', parent=self.root);return
        if total > self.balance:
            messagebox.showwarning('余额不足', f'重复上局下注需要 ${total:,.2f}。', parent=self.root)
            return
        # Restore the exact four-card distribution, replacing the current uncommitted bets.
        for i,amount in enumerate(self.previous_stakes):
            self.stakes[i].set(str(amount))
            self.pending_visual[i] = amount
        self.update_bet_spots()
        for i,amount in enumerate(self.previous_stakes):
            if amount:
                self.fly_chip(i, amount)

    def place_bet(self,index):
        if self.game_active:return
        stakes=self.read_stakes()
        if stakes[index]+self.chip_amount>MAX_CARD_BET:
            messagebox.showwarning('下注上限', '每张卡下注上限100K。', parent=self.root);return
        if sum(stakes)+self.chip_amount>self.balance:
            messagebox.showwarning('下注','余额不足',parent=self.root);return
        self.selected=index
        self.stakes[index].set(str(stakes[index]+self.chip_amount))
        self.pending_visual[index]+=self.chip_amount
        self.spot_texts=[f'下注 ${v:,.2f}' if v else '点击下注' for v in self.read_stakes()]
        self.update_bet_spots()
        self.fly_chip(index,self.chip_amount)

    def clear_card_bet(self,index):
        if self.game_active:return 'break'
        # Cancel only this spot's pending visuals; other cards retain their bets and flights.
        self.bet_revision[index]+=1
        self.stakes[index].set('0');self.pending_visual[index]=Decimal('0')
        self.canvas.delete(f'inflight{index}')
        self.update_bet_spots()
        return 'break'

    def update_bet_spots(self):
        self.canvas.delete('resting_chips')
        for i,amount in enumerate(self.read_stakes()):
            visible=max(Decimal(0),amount-self.pending_visual[i])
            self.bet_labels[i].configure(text='' if visible else '点击下注',bg='#E7F2EE',fg=self.INK)
            if visible:self.draw_chip(*self.spot_positions[i],visible,('resting_chips',f'bet{i}'))
        self.total_label.configure(text=f'本局下注  ${sum(self.read_stakes()):,.2f}')

    def fly_chip(self,index,amount,returning=False):
        # Same 38 px diameter, 200 ms / 10 frames and smoothstep as Baccarat_Special.
        self.chip_serial+=1;tag=f'motion{self.chip_serial}'
        start=self.chip_sources[self.chip_index];target=self.spot_positions[index]
        if returning:
            start=target;target=(434+(index-1.5)*24,711)
        revision=self.bet_revision[index]
        self.draw_chip(*start,amount,(tag,f'inflight{index}'))
        self.motion_count+=1
        self.motion_widgets.add(tag)
        last=list(start)
        def frame(step):
            if not returning and revision!=self.bet_revision[index]:
                self.canvas.delete(tag);self.motion_count-=1;self.motion_widgets.discard(tag)
                return
            t=step/10;eased=t*t*(3-2*t)
            x=start[0]+(target[0]-start[0])*eased;y=start[1]+(target[1]-start[1])*eased
            self.canvas.move(tag,x-last[0],y-last[1]);last[:]=[x,y]
            self.canvas.tag_raise(tag)
            if step<10:self.later(20,lambda:frame(step+1))
            else:
                self.canvas.delete(tag);self.motion_count-=1;self.motion_widgets.discard(tag)
                if not returning:
                    self.pending_visual[index]=max(Decimal(0),self.pending_visual[index]-amount)
                    self.update_bet_spots()
        self.later(20,lambda:frame(1))

    def render_machine(self):
        c=self.canvas;c.delete('machine');tag='machine'
        self.round_rect(327,75,1128,202,12,'#192930',tag)
        # Mark Six-inspired acrylic sphere, steel supports, loading rack and discharge tube.
        for x in (350,492):
            c.create_rectangle(x,86,x+5,189,fill='#647D89',outline='#ADC0CA',tags=tag)
        c.create_rectangle(346,185,505,194,fill='#657D87',outline='#C6D6DD',tags=tag)
        c.create_rectangle(378,179,474,187,fill='#314D5C',outline='#8CA6B2',tags=tag)
        c.create_oval(364,91,486,181,fill='#233D4A',outline='#BAD6E3',width=3,tags=tag)
        c.create_oval(370,95,480,177,outline='#5E8394',width=1,tags=tag)
        c.create_oval(399,94,452,179,outline='#466574',width=1,tags=tag)
        c.create_arc(372,95,478,175,start=35,extent=110,style=tk.ARC,outline='#E2F4FC',width=2,tags=tag)
        c.create_rectangle(365,79,485,89,fill='#2E4753',outline='#A1BBC7',tags=tag)
        for j in range(15):
            x=370+j*8
            c.create_oval(x-3,81,x+3,87,fill=('#D84D50','#3F87CE','#44A77D')[j%3],outline='',tags=tag)
        remaining=[n for n in range(1,61) if n not in self.drawn]
        for j,n in enumerate(remaining):
            if self.machine_running:
                a=self.phase*(1+j%4*.17)+j*2.399
                r=9+(j%7)*5
                x=425+math.cos(a)*r*1.16;y=138+math.sin(a)*r*.78
            else:
                x=386+(j%12)*7;y=153+(j//12)*4
            color=('#D84D50','#3F87CE','#44A77D')[n%3]
            c.create_oval(x-4,y-4,x+4,y+4,fill=color,outline='#C0D7D7',width=1,tags=tag)
        c.create_line(475,153,500,153,506,177,547,177,570,155,smooth=True,fill='#758F9D',width=9,tags=tag)
        c.create_line(475,151,500,151,506,175,547,175,570,153,smooth=True,fill='#D7EDF3',width=2,tags=tag)
        if self.exit_ball:
            number,t=self.exit_ball
            x=477+93*t;y=153+23*math.sin(math.pi*t)
            c.create_oval(x-9,y-9,x+9,y+9,fill=self.GOLD if len(self.drawn)==20 else '#E9F1F2',outline='#9CB7BF',tags=tag)
            c.create_text(x,y,text=str(number),fill=self.INK,font=(Theme.FONT,7,'bold'),tags=tag)
        for i in range(20):
            x,y=617+i%10*51,108+i//10*54
            c.create_oval(x-16,y-16,x+16,y+16,fill=self.GOLD if i==19 and i<len(self.drawn) else '#E7EFF1' if i<len(self.drawn) else '#273A43',outline='',tags=tag)
            c.create_text(x,y,text=str(self.drawn[i]) if i<len(self.drawn) else '·',fill=self.INK if i<len(self.drawn) else '#617E8C',font=(Theme.FONT,14,'bold'),tags=tag)
        if self.bonus_value:
            c.create_text(1108,190,text=f'加倍球 {self.bonus_value}×',anchor='e',fill=self.GOLD,font=(Theme.FONT_CJK,9,'bold'),tags=tag)

    def refresh(self):
        self.balance_label.configure(text=f'余额  ${self.balance:,.2f}')
        c=self.canvas;c.delete('numbers')
        for i,full_card in enumerate(self.cards):
            visible={cell for owner,cell in self.reveal_cells if owner==i}
            if self.reveal_center:visible.add(12)
            card=BingoCard(tuple(n if j%5<self.reveal_columns else None for j,n in enumerate(full_card.numbers)),
                full_card.free & visible,
                {k:v for k,v in full_card.standard.items() if k in visible},
                {k:v for k,v in full_card.global_cells.items() if k in visible},
                {k:v for k,v in full_card.line_bonus.items() if (i,k) in self.reveal_lines})
            active=any(n is not None for n in card.numbers)
            marked=card.marked(set(self.drawn)) if active else set()
            def center(index):
                row,col=divmod(index,5)
                return self.card_x[i]+43+col*43,346+row*41
            # White circular wells, with a continuous gold ribbon behind all five numbers.
            for index in range(25):
                x,y=center(index)
                c.create_oval(x-18,y-18,x+18,y+18,fill='white',outline='#E1E6E3',width=1,tags='numbers')
            for line,value in sorted(card.line_bonus.items()):
                first,last=LINES[line][0],LINES[line][-1]
                x1,y1=center(first);x2,y2=center(last)
                c.create_line(x1,y1,x2,y2,fill='#F2D46F',width=32,capstyle=tk.ROUND,tags='numbers')
                c.create_line(x1-7,y1,x2-7,y2,fill='#F8E8A2',width=5,capstyle=tk.ROUND,tags='numbers')
                if line<5:
                    bx,by,angle=self.card_x[i]+247,y2,90
                elif line<10:
                    bx,by,angle=x1,319,0
                else:
                    bx,by,angle=(self.card_x[i]+20,320,45) if line==10 else (self.card_x[i]+240,320,-45)
                # Outlined gold type follows the reference's line-end multiplier placement.
                for dx,dy in ((-1,-1),(1,-1),(-1,1),(1,1)):
                    c.create_text(bx+dx,by+dy,text=f'{value}×',angle=angle,fill='#80631A',font=(Theme.FONT,10,'bold'),tags='numbers')
                c.create_text(bx,by,text=f'{value}×',angle=angle,fill='#FFE895',font=(Theme.FONT,10,'bold'),tags='numbers')
            for index,number in enumerate(card.numbers):
                x,y=center(index)
                hit=index in marked
                if hit:
                    c.create_oval(x-17,y-17,x+17,y+17,fill='#DE454C',outline='#C62E3A',width=1,tags='numbers')
                label='∞' if index in card.free else str(number) if number is not None else ''
                c.create_text(x,y+2,text=label,fill='white' if hit else self.INK,
                              font=(Theme.FONT,16 if label=='∞' else 13,'bold'),tags='numbers')
                is_global=index in card.global_cells
                badge=f'{card.global_cells[index]}×' if is_global else f'{card.standard[index]}×' if index in card.standard else ''
                covered=any(index in LINES[line] for line in card.line_bonus)
                if self.bonus_number is not None and self.bonus_number==number and index not in card.free and not covered and not is_global:
                    badge=f'{card.standard.get(index,0)+self.bonus_value}×'
                if badge:
                    # Small angled badges sit above the number rather than replacing it.
                    bx,by=x-8,y-16
                    c.create_oval(bx-15,by-8,bx+15,by+8,fill='#C6CBD0' if is_global else '#F0CE65',
                                  outline='#7D858B' if is_global else '#A98020',width=1,tags='numbers')
                    c.create_text(bx,by,text=badge,angle=16,fill='#414B55' if is_global else '#694C0B',
                                  font=(Theme.FONT,9,'bold'),tags='numbers')
            # Highlight each still-unmatched number that would complete at least one line.
            if active and self.reveal_columns==5:
                missing_cells=set()
                for line in LINES:
                    missing=set(line)-marked
                    if len(missing)==1:missing_cells.update(missing)
                for index in missing_cells:
                    if card.numbers[index] is not None:
                        x,y=center(index)
                        c.create_rectangle(x-19,y-19,x+19,y+19,outline='#2685EF',width=3,
                                           tags=('numbers','near_win'))
            # Draw only completed winning lines on active cards, including diagonals.
            if active:
                for line in LINES:
                    if set(line) <= marked:
                        x1,y1=center(line[0]);x2,y2=center(line[-1])
                        c.create_line(x1,y1,x2,y2,fill='#111111',width=2,
                                      capstyle=tk.ROUND,tags=('numbers','winning_line'))
        self.render_machine()

    def start(self):
        if self.game_active or self.motion_count:return
        super().start()
        if self.game_active:
            for tag in ('clear','repeat','start'):self.canvas.itemconfigure(tag,state='hidden')
            self.canvas.delete('resting_chips')
            for i,amount in enumerate(self.round_stakes):
                self.bet_labels[i].configure(text='' if amount else '本局未参与',bg='#E7F2EE',fg=self.INK)
                if amount:self.draw_chip(*self.spot_positions[i],amount,('resting_chips',f'bet{i}'))

    def flash(self,step):
        # Only the fixed bet surfaces flash; board cells and all other text remain stable.
        self.canvas.delete('resting_chips')
        for i,(amount,details) in enumerate(self.results):
            bright=bool(amount) and step<6 and step%2==0
            self.bet_labels[i].configure(text='' if amount else '未中奖' if self.round_stakes[i] else '本局未参与',
                                         bg=self.GOLD if bright else '#E7F2EE',fg=self.INK)
            if amount:self.draw_chip(*self.spot_positions[i],amount,('resting_chips',f'bet{i}'))
        if step<6:self.later(450,lambda:self.flash(step+1))
        else:
            self.canvas.delete('resting_chips')
            for i,(amount,_) in enumerate(self.results):
                if amount:
                    self.fly_chip(i,amount,True)
                    count=len(self.results[i][1])
                    self.bet_labels[i].configure(text=f'BINGO！本牌中{count}行',bg='#E7F2EE',fg=self.INK)
            # Results remain visible until the 120-second timer or the replay button.

    def primary_action(self):
        if self.game_active and self.settled:self.next_round()
        elif not self.game_active:self.start()

    def next_round(self):
        if not self.game_active or not self.settled:return
        # Cancel the timeout and every old-round animation before enabling a fresh round.
        for job in tuple(self.jobs):
            try:self.root.after_cancel(job)
            except tk.TclError:pass
        self.jobs.clear();self.reset_job=None
        for tag in tuple(self.motion_widgets):self.canvas.delete(tag)
        self.motion_widgets.clear();self.motion_count=0
        self.unlock_after_return()

    def new_cards(self):
        if self.game_active or self.motion_count:return
        self.cards=[BingoCard((None,) * 25) for _ in range(4)]
        self.drawn=[];self.results=[];self.bonus_number=None;self.bonus_value=0
        self.update_bet_spots();self.refresh()



# Keep the original Keno launcher signature for host integration.
def main(initial_balance=1000.0, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    actual_balance = initial_balance if balance is None else balance
    actual_user = username if user is None else user
    if parent is not None and EmbeddedGamePage is not None:
        page = EmbeddedGamePage(parent, title='宾果游戏', username=actual_user,
                                balance=float(actual_balance), on_back=on_back,
                                on_balance_change=on_balance_change)
        game = BingoGame(page.host, actual_balance, actual_user, on_balance_change)
        page.attach_game(game)
        return page
    if parent is not None:
        frame = tk.Frame(parent)
        def finish(value):
            frame.destroy()
            if callable(on_back):
                on_back(value)
        frame.finish = finish
        frame.game = BingoGame(frame, actual_balance, actual_user, on_balance_change)
        return frame
    root = tk.Tk()
    game = BingoGame(root, actual_balance, actual_user, on_balance_change)
    root.mainloop()
    return float(game.balance)


if __name__ == '__main__':
    main(10000, 'test_user')
