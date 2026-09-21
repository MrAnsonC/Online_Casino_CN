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
import time
import tkinter as tk
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from tkinter import messagebox


# BUILD: CLEAN_SINGLE_GUI_LAYOUT_LIMITS_HISTORY_2026-09-02
# Consolidated from the uploaded original: one GUI class, no V7..V16 inheritance stack.
# Includes physical bowl/counting animations, JSON history, auto_data test mode, and clearer help.

# ============================================================
# Classic Fan Tan — Pai Gow shell + Baccarat-style bet motion
# ============================================================
WINDOW_GEOMETRY = "1150x750+50+10"

BG = "#17120f"
FELT = "#0b4540"
GOLD = "#e7d36c"
GOLD_DARK = "#8d742d"
TEXT = "#f7f1e4"
MUTED = "#c8bda9"

ROOT_BG = "#1B3D31"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"

SIMPLE_MIN_BET = 10.0
SIMPLE_MAX_AREA_BET = 50_000.0
SIMPLE_MAX_TABLE_BET = 200_000.0

TRADITIONAL_SIDE_MAX_AREA_BET = 10_000.0
TRADITIONAL_MAIN_MAX_AREA_BET = 50_000.0
TRADITIONAL_MAX_TABLE_BET = 300_000.0

# Backward-compatible names retain the simple-layout defaults for callers that
# imported the original module-level constants.
MIN_BET = SIMPLE_MIN_BET
MAX_AREA_BET = SIMPLE_MAX_AREA_BET
MAX_TABLE_BET = SIMPLE_MAX_TABLE_BET

CHIPS = [
    (10, "#f4a621", "10"),
    (25, "#22d84b", "25"),
    (100, "#181818", "100"),
    (500, "#e66fb1", "500"),
    (1000, "#f2f2e8", "1K"),
    (2500, "#e52929", "2.5K"),
]


# ============================================================
# Account compatibility — same contract as the original project
# ============================================================

def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, "A_Tools/Account/saving_data.json")


def load_user_data():
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def save_user_data(users):
    try:
        with open(get_data_file_path(), "w", encoding="utf-8") as handle:
            json.dump(users, handle, ensure_ascii=False, indent=4)
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
# Fan Tan rules / bet model
# ============================================================

@dataclass(frozen=True)
class BetSpec:
    key: str
    label: str
    kind: str
    win_numbers: tuple
    push_numbers: tuple
    profit_odds: Decimal
    odds_text: str
    color: str
    description: str = ""


class FanTanEngine:
    """Pure Fan Tan bet-resolution logic.

    The GUI determines the round result from the physical bowl geometry and
    the number of covered white buttons.  This class only defines bet types,
    winning / push conditions, odds, and settlement arithmetic.
    """

    @staticmethod
    def build_specs():
        specs = {}

        fan_colors = {
            1: "#8e2223",
            2: "#8e2223",
            3: "#8e2223",
            4: "#8e2223",
        }
        for n in range(1, 5):
            specs[f"fan_{n}"] = BetSpec(
                key=f"fan_{n}",
                label=str(n),
                kind="fan",
                win_numbers=(n,),
                push_numbers=(),
                profit_odds=Decimal("2.85"),
                odds_text="2.85 : 1",
                color=fan_colors[n],
                description=f"番 {n}：开 {n} 赢。",
            )

        simple_pairs = {
            "small": ("小", (1, 2), "0.95 : 1"),
            "big": ("大", (3, 4), "0.95 : 1"),
            "odd": ("单", (1, 3), "0.95 : 1"),
            "even": ("双", (2, 4), "0.95 : 1"),
        }
        for key, (label, wins, odds_text) in simple_pairs.items():
            specs[key] = BetSpec(
                key=key,
                label=label,
                kind="simple",
                win_numbers=wins,
                push_numbers=(),
                profit_odds=Decimal("0.95"),
                odds_text=odds_text,
                color="#7c2020",
                description=f"{label}：开 {wins[0]} / {wins[1]} 赢。",
            )

        # Original board NIM — every ordered pair exists on the uploaded table.
        for primary in range(1, 5):
            for push in range(1, 5):
                if primary == push:
                    continue
                key = f"nim_{primary}_{push}"
                specs[key] = BetSpec(
                    key=key,
                    label=f"{primary} 念 {push}",
                    kind="nim",
                    win_numbers=(primary,),
                    push_numbers=(push,),
                    profit_odds=Decimal("1.90"),
                    odds_text="1.90 : 1",
                    color="#7c2020",
                    description=f"{primary}念{push}：开{primary}赢；开{push}退回。",
                )

        # The uploaded original board shows four outer Kwok cells only.
        for a, b in ((1, 2), (4, 1), (2, 3), (3, 4)):
            key = f"kwok_{a}_{b}"
            specs[key] = BetSpec(
                key=key,
                label=f"角 {a}-{b}",
                kind="kwok",
                win_numbers=(a, b),
                push_numbers=(),
                profit_odds=Decimal("0.95"),
                odds_text="0.95 : 1",
                color="#7c2020",
                description=f"角 {a}-{b}：开 {a} / {b} 赢。",
            )

        for nums in ((3, 2, 1), (2, 1, 4), (4, 3, 2), (1, 4, 3)):
            key = f"ssh_{nums[0]}_{nums[1]}_{nums[2]}"
            specs[key] = BetSpec(
                key=key,
                label=f"三门 {nums[0]}-{nums[1]}-{nums[2]}",
                kind="ssh",
                win_numbers=nums,
                push_numbers=(),
                profit_odds=Decimal("0.316667"),
                odds_text="0.316667 : 1",
                color="#7c2020",
                description=f"三门 {'-'.join(map(str, nums))}：开这三个号码任一都赢。",
            )

        return specs


    @staticmethod
    def bet_status(spec, result):
        if result in spec.win_numbers:
            return "win"
        if result in spec.push_numbers:
            return "push"
        return "lose"

    @staticmethod
    def _money_decimal(value):
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def resolve_bets(cls, bets, specs, result):
        outcomes = []
        credit = Decimal("0.00")
        total_stake = Decimal("0.00")

        for key, amount in bets.items():
            spec = specs.get(key)
            if not spec:
                continue
            stake = cls._money_decimal(amount)
            if stake <= 0:
                continue
            total_stake += stake
            status = cls.bet_status(spec, result)

            if status == "win":
                profit = (stake * spec.profit_odds).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                returned = stake + profit
            elif status == "push":
                profit = Decimal("0.00")
                returned = stake
            else:
                profit = Decimal("0.00")
                returned = Decimal("0.00")

            credit += returned
            outcomes.append({
                "key": key,
                "label": spec.label,
                "status": status,
                "stake": float(stake),
                "profit": float(profit),
                "return_amount": float(returned),
            })

        net = credit - total_stake
        return {
            "outcomes": outcomes,
            "credit": float(credit),
            "stake": float(total_stake),
            "net": float(net),
        }


class FanTanBetState:
    """Baccarat-style multi-area betting state."""

    def __init__(self):
        self.bets = {}

    def total_at_risk(self):
        return sum(float(value) for value in self.bets.values())

    def current_area_bet(self, key):
        return float(self.bets.get(key, 0.0))

    def add_bet(self, key, amount):
        amount = float(amount)
        if amount <= 0:
            return False
        self.bets[key] = self.current_area_bet(key) + amount
        return True

    def remove_amount(self, key, amount):
        current = self.current_area_bet(key)
        removed = min(current, max(0.0, float(amount)))
        left = current - removed
        if left > 1e-9:
            self.bets[key] = left
        else:
            self.bets.pop(key, None)
        return removed

    def clear_area(self, key):
        return float(self.bets.pop(key, 0.0))

    def clear_all(self):
        total = self.total_at_risk()
        self.bets.clear()
        return total


# ============================================================
# Main GUI — Pai Gow shell, revised to the uploaded Fan Tan art
# ============================================================


class ClassicFanTanGUI(tk.Frame):
    """Consolidated Fan Tan GUI.

    The uploaded file had a long V7→V16 inheritance chain that repeatedly
    overrode the same methods.  This clean build keeps only the final effective
    behaviour in one GUI class, making stage flow and future edits traceable.
    """

    WIDTH = 1150
    HEIGHT = 750
    TABLE_X0, TABLE_X1 = 10, 740
    RIGHT_X0, RIGHT_X1 = 750, 1150
    COUNTER_ZONE = (24, 48, 726, 330)
    BOARD_ZONE = (24, 338, 726, 726)
    BEAD_FIELD = (40, 82, 710, 250)

    BEAD_DIAMETER = 12.0
    BEAD_RADIUS = BEAD_DIAMETER / 2.0
    ROUND_BEAD_COUNT = 400
    MAX_OVERLAP_FRACTION = 0.25

    COUNT_FRAMES = 36
    COUNT_FRAME_MS = 55
    FINAL_FRAMES = 38
    FINAL_FRAME_MS = 55

    SIMPLE_KEYS = (
        'fan_1', 'fan_2', 'fan_3', 'fan_4',
        'small', 'big', 'odd', 'even',
    )
    TRAD_KEYS = (
        'kwok_1_2', 'nim_1_2', 'nim_1_3', 'nim_1_4', 'kwok_4_1',
        'nim_2_1', 'nim_2_3', 'nim_2_4',
        'nim_4_1', 'nim_4_2', 'nim_4_3',
        'kwok_2_3', 'nim_3_1', 'nim_3_2', 'nim_3_4', 'kwok_3_4',
        'ssh_3_2_1', 'ssh_2_1_4', 'ssh_4_3_2', 'ssh_1_4_3',
        'fan_1', 'fan_2', 'fan_3', 'fan_4',
        'small', 'big', 'odd', 'even',
    )

    def __init__(self, parent, balance=10000, user="Guest", on_back=None, on_balance_change=None, auto_data=False):
        super().__init__(parent, bg=BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)

        # Test-data mode. False = normal manual play. True = automatically
        # performs the same action as pressing Enter whenever Enter is valid.
        self.auto_data = bool(auto_data)
        self._auto_enter_pending_stage = None

        # Historical-ratio view. The buttons switch how many of the newest
        # stored results are included in the statistics.
        self.history_ratio_limit = 1000
        self.history_ratio_buttons = {}

        self.username = user or "Guest"
        self.balance = float(balance)
        self.on_back = on_back
        self.on_balance_change = on_balance_change

        self.engine = FanTanEngine()
        self.specs = self.engine.build_specs()
        self.bet_state = FanTanBetState()
        self.display_bets = None

        self.selected_chip = 100.0
        self.undo_stack = []
        self.last_round_bets = []
        self.bet_spots = {}
        self.chip_canvases = {}
        self.layout_buttons = {}
        self.chip_widget_centers = {}
        self.pending_bet_visual_amounts = {}
        self.chip_motion_serial = 0

        self.bet_layout = "simple"
        self.stage = "preparing"

        self.next_result_number = None
        self.next_round_total_buttons = 0
        self.result_number = None
        self.round_total_buttons = 0
        self.count_removed = 0
        self.bowl_offset = 0
        self.outer_buttons_total = 0
        self.outer_removed = 0
        self.bead_positions = []
        self.bowl_center = (350.0, 172.0)
        self.bowl_radius = 50.0
        self.inside_indices = []
        self.outside_indices = []
        self.count_order = []
        self.history = []
        self.last_return = 0.0
        self.last_net = 0.0

        self.bet_outcomes = {}
        self.flash_winning_keys = set()
        self.static_winning_keys = set()
        self.flash_on = False
        self.settlement_queue = []
        self.flash_mode = None
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.push_return_amounts = {}
        self.settlement_return_keys = set()
        self.settlement_return_animating = False
        self.round_stake_display = 0.0
        self.flash_text_original_colors = {}

        self.runtime_json_dir = self.get_runtime_json_dir()
        self.runtime_data_file = os.path.join(self.runtime_json_dir, 'FanTan.json')
        self.runtime_store = self.load_result_store()
        self.history = self.history_from_store()

        self._closing = False
        self._after_ids = set()
        self._return_bind_id = None

        top = self.winfo_toplevel()
        try:
            top.geometry(WINDOW_GEOMETRY)
            top.resizable(False, False)
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT, bg=BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        try:
            self._return_bind_id = top.bind("<Return>", self._on_enter, add="+")
        except tk.TclError:
            pass

        self.create_static_ui()
        self.prepare_next_round_seed()
        self.redraw_counter_zone()
        self.draw_betting_board()
        self.select_chip(self.selected_chip)
        self.update_display()
        # Each round is physically prepared before betting opens.
        # 400 white buttons -> 100px bowl -> bowl settles -> outside sweep -> betting/counting.
        self._schedule(700, self._begin_prebet_cover)

    def _schedule(self, delay_ms, callback, *args):
        holder = {}

        def runner():
            ident = holder.get("id")
            if ident is not None:
                self._after_ids.discard(ident)
            if self._closing:
                return
            callback(*args)

        ident = self.after(delay_ms, runner)
        holder["id"] = ident
        self._after_ids.add(ident)
        return ident

    @staticmethod
    def _round_money(value):
        return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    @staticmethod
    def format_money(value):
        value = float(value)
        if abs(value - round(value)) < 0.005:
            return f"${value:,.0f}"
        return f"${value:,.2f}"

    @classmethod
    def format_signed_money(cls, value):
        value = float(value)
        if value > 0.004:
            return "+" + cls.format_money(value)
        if value < -0.004:
            return "-" + cls.format_money(abs(value))
        return "$0.00"

    @staticmethod
    def contrast_text_color(color):
        value = color.lstrip("#")
        if len(value) != 6:
            return "black"
        r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return "black" if lum >= 150 else "white"

    @staticmethod
    def compact_amount(amount):
        amount = float(amount)
        if amount >= 1000:
            k = amount / 1000.0
            return f"{k:.0f}K" if abs(k - round(k)) < 0.01 else f"{k:.1f}K"
        return str(int(round(amount))) if abs(amount - round(amount)) < 0.01 else f"{amount:.1f}"

    @classmethod
    def bet_chip_color(cls, amount):
        color = CHIPS[0][1]
        for threshold, chip_color, _ in CHIPS:
            if amount >= threshold:
                color = chip_color
            else:
                break
        return color

    def visible_keys(self, layout=None):
        layout = self.bet_layout if layout is None else layout
        return list(self.SIMPLE_KEYS if layout == "simple" else self.TRAD_KEYS)

    def _bet_limits_for(self, key):
        """Return minimum, per-area maximum, and table maximum for this bet."""
        if self.bet_layout == 'simple':
            return SIMPLE_MIN_BET, SIMPLE_MAX_AREA_BET, SIMPLE_MAX_TABLE_BET

        # In the traditional layout, the four large 番 regions are the main
        # areas; every surrounding combination/pair area is a side area.
        spec = self.specs.get(key)
        area_max = (
            TRADITIONAL_MAIN_MAX_AREA_BET
            if spec is not None and spec.kind == 'fan'
            else TRADITIONAL_SIDE_MAX_AREA_BET
        )
        return SIMPLE_MIN_BET, area_max, TRADITIONAL_MAX_TABLE_BET

    def visible_bet_amount(self, key):
        if self.display_bets is None:
            return float(self.bet_state.bets.get(key, 0.0))
        return float(self.display_bets.get(key, 0.0))

    def get_runtime_json_dir(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        target = os.path.join(project_root, 'A_Logs', 'Json')
        try:
            os.makedirs(target, exist_ok=True)
            return target
        except OSError:
            target = os.path.join(current_dir, 'A_Logs', 'Json')
            os.makedirs(target, exist_ok=True)
            return target

    @staticmethod
    def new_result_store():
        return {
            'total': {'1': 0, '2': 0, '3': 0, '4': 0},
            '1000_result': [],
        }

    def load_result_store(self):
        store = self.new_result_store()
        try:
            with open(self.runtime_data_file, 'r', encoding='utf-8') as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                total = raw.get('total', {})
                if isinstance(total, dict):
                    for key in ('1','2','3','4'):
                        try:
                            store['total'][key] = max(0, int(total.get(key, 0)))
                        except (TypeError, ValueError):
                            pass
                records = raw.get('1000_result', [])
                if isinstance(records, list):
                    clean = []
                    for record in records:
                        if not isinstance(record, dict):
                            continue
                        try:
                            rid = int(record.get('ID', 0))
                            result_obj = record.get('结果', {})
                            bowl_total = int(result_obj.get('总共碗内的数量', 0))
                            final = int(result_obj.get('最终', 0))
                        except (TypeError, ValueError, AttributeError):
                            continue
                        if not (1 <= rid <= 1000 and bowl_total >= 1 and final in (1,2,3,4)):
                            continue
                        clean.append({
                            'ID': rid,
                            'Date': str(record.get('Date', '')),
                            '结果': {'总共碗内的数量': bowl_total, '最终': final},
                        })
                    clean.sort(key=lambda item: item['ID'])
                    store['1000_result'] = clean[:1000]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return store

    def _acquire_result_lock(self, timeout=8.0, poll_interval=0.025):
        """Acquire a cross-process lock for FanTan.json.

        ``O_CREAT | O_EXCL`` makes lock-file creation atomic on the local
        filesystem, so two game windows cannot enter the read-modify-write
        section at the same time.  A stale lock older than 30 seconds is removed
        as a crash-recovery safeguard.
        """
        lock_path = self.runtime_data_file + '.lock'
        deadline = time.monotonic() + float(timeout)
        os.makedirs(os.path.dirname(self.runtime_data_file), exist_ok=True)

        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    os.write(fd, f'{os.getpid()}\n'.encode('ascii', errors='ignore'))
                except OSError:
                    pass
                return lock_path, fd
            except FileExistsError:
                # Recover from a lock left behind by an abnormal process exit.
                try:
                    if time.time() - os.path.getmtime(lock_path) > 30.0:
                        os.remove(lock_path)
                        continue
                except (FileNotFoundError, OSError):
                    pass

                if time.monotonic() >= deadline:
                    raise TimeoutError('等待 FanTan.json 文件锁超时')
                time.sleep(float(poll_interval))

    @staticmethod
    def _release_result_lock(lock_path, fd):
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def _write_result_store(self, store=None):
        """Atomically replace FanTan.json with ``store``.

        The caller that performs a read-modify-write must hold the result lock.
        A PID-specific temporary filename prevents temporary-file collisions if
        an old build or another writer happens to be running at the same time.
        """
        data = self.runtime_store if store is None else store
        try:
            os.makedirs(os.path.dirname(self.runtime_data_file), exist_ok=True)
            temp_path = f'{self.runtime_data_file}.{os.getpid()}.tmp'
            with open(temp_path, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, indent=4)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            os.replace(temp_path, self.runtime_data_file)
        except OSError as exc:
            print(f'保存 FanTan 失败：{exc}')
            raise

    def sync_result_store_from_disk(self):
        """Refresh this window's history/statistics from the shared JSON file."""
        self.runtime_store = self.load_result_store()
        self.history = self.history_from_store()

    def save_round_result(self):
        """Merge this round into the latest on-disk data without lost updates.

        Important for multi-open use: never modify the copy loaded when this
        window started.  Instead lock -> reload latest disk state -> append this
        round -> atomic replace -> unlock.
        """
        final = int(self.result_number)
        bowl_total = int(self.round_total_buttons)
        lock_path = None
        lock_fd = None

        try:
            lock_path, lock_fd = self._acquire_result_lock()

            # Critical fix: reload AFTER the lock is acquired, so this is always
            # the newest data written by every other running game instance.
            latest = self.load_result_store()

            total = latest.setdefault('total', {'1':0,'2':0,'3':0,'4':0})
            for key in ('1', '2', '3', '4'):
                try:
                    total[key] = max(0, int(total.get(key, 0)))
                except (TypeError, ValueError):
                    total[key] = 0
            total[str(final)] += 1

            old_records = latest.get('1000_result', [])
            shifted = []
            if isinstance(old_records, list):
                for record in old_records:
                    if not isinstance(record, dict):
                        continue
                    try:
                        new_id = int(record.get('ID', 0)) + 1
                    except (TypeError, ValueError):
                        continue
                    if new_id > 1000:
                        continue
                    item = dict(record)
                    item['ID'] = new_id
                    shifted.append(item)

            new_record = {
                'ID': 1,
                'Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '结果': {
                    '总共碗内的数量': bowl_total,
                    '最终': final,
                },
            }
            latest['1000_result'] = [new_record] + shifted[:999]

            self._write_result_store(latest)
            self.runtime_store = latest
            self.history = self.history_from_store()

        except (OSError, TimeoutError) as exc:
            print(f'同步保存 FanTan 失败：{exc}')
            # Do not overwrite the disk with the stale in-memory copy.
            self.sync_result_store_from_disk()
        finally:
            if lock_path is not None and lock_fd is not None:
                self._release_result_lock(lock_path, lock_fd)

    def _refresh_chip_widget_centers(self):
        self.update_idletasks()
        try:
            base_x = self.winfo_rootx()
            base_y = self.winfo_rooty()
        except tk.TclError:
            return
        self.chip_widget_centers = {}
        for value, (widget, _outer) in self.chip_canvases.items():
            try:
                cx = widget.winfo_rootx() - base_x + widget.winfo_width() / 2
                cy = widget.winfo_rooty() - base_y + widget.winfo_height() / 2
                self.chip_widget_centers[float(value)] = (cx, cy)
            except tk.TclError:
                pass

    def _chip_home_position(self, amount=None):
        self._refresh_chip_widget_centers()
        if amount is None:
            return self.chip_widget_centers.get(float(self.selected_chip), (920, 250))
        amount = float(amount)
        candidate = float(CHIPS[0][0])
        for threshold, _color, _label in CHIPS:
            if amount >= threshold:
                candidate = float(threshold)
            else:
                break
        return self.chip_widget_centers.get(candidate, self.chip_widget_centers.get(float(self.selected_chip), (920, 250)))

    def _animate_chip_motion(self, amount, start_xy, end_xy, *, duration_ms=200, steps=10, on_finish=None):
        c = self.canvas
        color = self.bet_chip_color(amount)
        is_25_style = color.lower() == '#22d84b'
        fg = 'black' if is_25_style else self.contrast_text_color(color)
        radius = 16
        x0, y0 = start_xy
        x1, y1 = end_xy
        outer = c.create_oval(x0-radius, y0-radius, x0+radius, y0+radius, fill='#292522', outline='#151311', width=1, tags='flight_chip')
        inner = c.create_oval(x0-radius+2, y0-radius+2, x0+radius-2, y0+radius-2, fill=color, outline='#e2ddd5', width=1, tags='flight_chip')
        text = c.create_text(x0, y0, text=self.compact_amount(amount), font=('Arial',8,'bold'), fill=fg, tags='flight_chip')
        items = [outer, inner, text]

        def frame(step=0):
            if self._closing:
                for item in items:
                    try: c.delete(item)
                    except tk.TclError: pass
                return
            t = step / float(steps)
            smooth = t*t*(3-2*t)
            x = x0 + (x1-x0)*smooth
            y = y0 + (y1-y0)*smooth
            c.coords(outer, x-radius, y-radius, x+radius, y+radius)
            c.coords(inner, x-radius+2, y-radius+2, x+radius-2, y+radius-2)
            c.coords(text, x, y)
            if step < steps:
                self._schedule(max(1,duration_ms//steps), frame, step+1)
                return
            for item in items:
                try: c.delete(item)
                except tk.TclError: pass
            if callable(on_finish):
                on_finish()
        frame(0)

    def _draw_bowl(self, cx, cy):
        # Top-down 100px bowl/cup.
        c = self.canvas
        r = 50.0
        c.create_oval(cx-r+4, cy-r+5, cx+r+4, cy+r+5, fill='#3a2112', outline='', tags='counter_dynamic')
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill='#b47a37', outline='#f1d18b', width=3, tags='counter_dynamic')
        c.create_oval(cx-r+8, cy-r+8, cx+r-8, cy+r-8, fill='#8a5727', outline='#e1b96d', width=2, tags='counter_dynamic')
        c.create_oval(cx-12, cy-12, cx+12, cy+12, fill='#c9934f', outline='#5d3516', width=2, tags='counter_dynamic')

    def draw_betting_board(self):
        c = self.canvas
        c.delete('board_dynamic')
        c.delete('bet_chip_dynamic')
        c.delete('win_flash_area')
        self.bet_spots = {}

        if self.bet_layout == 'simple':
            self._draw_simple_board()
        else:
            self._draw_traditional_board()

        self.update_bet_chips()
        self._apply_outcome_styles()

    def _bind_spot(self, key):
        tag = f"spot_{key}"
        self.canvas.tag_bind(tag, "<Button-1>", lambda _e, k=key: self.place_bet(k))
        self.canvas.tag_bind(tag, "<Button-3>", lambda _e, k=key: self.clear_single_bet(k))
        self.canvas.tag_bind(tag, "<Button-2>", lambda _e, k=key: self.clear_single_bet(k))
        self.canvas.tag_bind(tag, "<Enter>", lambda _e: self.canvas.configure(cursor="hand2" if self.stage == "betting" else "X_cursor"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _e: self.canvas.configure(cursor=""))
        return tag

    def _draw_simple_spot_rect(self, key, x0, y0, x1, y1, *, label, odds, angle=0,
                               label_font=14, odds_font=10, chip_pos=None, tag=None):
        c = self.canvas
        tag = tag or self._bind_spot(key)
        content_tag = f'content_{key}'
        rect = c.create_rectangle(x0, y0, x1, y1, fill='#641719', outline='#d9b57a', width=2,
                                  tags=('board_dynamic', tag))
        c.create_text((x0+x1)/2, y0+(y1-y0)*0.36, text=label,
                      font=('Arial', label_font, 'bold'), fill='#eac47d', angle=angle,
                      tags=('board_dynamic', tag, content_tag))
        c.create_text((x0+x1)/2, y0+(y1-y0)*0.68, text=odds,
                      font=('Arial', odds_font, 'bold'), fill='#e6d4b1', angle=angle,
                      tags=('board_dynamic', tag, content_tag))
        if chip_pos is None:
            chip_pos = ((x0+x1)/2, (y0+y1)/2)
        self._register_spot(key, rect, chip_pos,
                            geometry=('rectangle', (x0,y0,x1,y1)), content_tag=content_tag)

    def _draw_simple_board(self):
        x0, y0, x1, y1 = self.BOARD_ZONE
        left = x0 + 18
        right = x1 - 18
        top = y0 + 12
        bottom = y1 - 12
        side_w = 60
        strip_h = 58
        inner_gap = 7

        for cx, cy, sx, sy in ((left, top, 1, 1), (right, top, -1, 1),
                               (left, bottom, 1, -1), (right, bottom, -1, -1)):
            self.canvas.create_line(cx, cy+20*sy, cx, cy, cx+20*sx, cy,
                                    fill='#b99158', width=3, tags='board_dynamic')
            self.canvas.create_line(cx+10*sx, cy+20*sy, cx+10*sx, cy+10*sy,
                                    cx+20*sx, cy+10*sy, fill='#b99158', width=3,
                                    tags='board_dynamic')

        top_y0, top_y1 = top, top + strip_h
        bottom_y0, bottom_y1 = bottom - strip_h, bottom
        left_x0, left_x1 = left, left + side_w
        right_x0, right_x1 = right - side_w, right
        center_x0, center_x1 = left_x1 + inner_gap, right_x0 - inner_gap
        center_y0, center_y1 = top_y1 + inner_gap, bottom_y0 - inner_gap
        mid_x, mid_y = (center_x0+center_x1)/2, (center_y0+center_y1)/2

        self._draw_simple_spot_rect('small', center_x0, top_y0, center_x1, top_y1,
                                   label='小', odds='0.95 : 1', label_font=17,
                                   chip_pos=((center_x0+center_x1)/2, top_y1-16))
        self._draw_simple_spot_rect('big', center_x0, bottom_y0, center_x1, bottom_y1,
                                   label='大', odds='0.95 : 1', label_font=17,
                                   chip_pos=((center_x0+center_x1)/2, bottom_y0+16))
        self._draw_simple_spot_rect('odd', left_x0, center_y0, left_x1, center_y1,
                                   label='单', odds='0.95 : 1', angle=90, label_font=16,
                                   chip_pos=(left_x1-18, (center_y0+center_y1)/2))
        self._draw_simple_spot_rect('even', right_x0, center_y0, right_x1, center_y1,
                                   label='双', odds='0.95 : 1', angle=270, label_font=16,
                                   chip_pos=(right_x0+18, (center_y0+center_y1)/2))

        fan_cells = {
            'fan_1': (center_x0, center_y0, mid_x, mid_y),
            'fan_2': (mid_x, center_y0, center_x1, mid_y),
            'fan_3': (center_x0, mid_y, mid_x, center_y1),
            'fan_4': (mid_x, mid_y, center_x1, center_y1),
        }
        for key, (bx0,by0,bx1,by1) in fan_cells.items():
            tag = self._bind_spot(key)
            content_tag = f'content_{key}'
            rect = self.canvas.create_rectangle(bx0,by0,bx1,by1, fill='#641719',
                                                outline='#c59f61', width=2,
                                                tags=('board_dynamic', tag))
            n=self.specs[key].label
            self.canvas.create_text((bx0+bx1)/2, by0+(by1-by0)*0.45, text=n,
                                    font=('Times New Roman',42,'bold'), fill='#f1cd84',
                                    tags=('board_dynamic',tag,content_tag))
            odds_x = bx0+36 if key in ('fan_1','fan_3') else bx1-36
            anchor = 'w' if key in ('fan_1','fan_3') else 'e'
            self.canvas.create_text(odds_x, by1-17, anchor=anchor, text='2.85 : 1',
                                    font=('Arial',10,'bold'), fill='#f1dfc0',
                                    tags=('board_dynamic',tag,content_tag))
            self._register_spot(key, rect, ((bx0+bx1)/2, by0+(by1-by0)*0.70),
                                geometry=('rectangle',(bx0,by0,bx1,by1)), content_tag=content_tag)

    def _draw_text_rect_spot(self, key, x0, y0, x1, y1, *, lines, chip_pos=None,
                             label_font=10, odds_font=10, fill='#641719'):
        tag = self._bind_spot(key)
        content_tag = f'content_{key}'
        rect = self.canvas.create_rectangle(x0,y0,x1,y1, fill=fill, outline='#b98c53', width=2,
                                            tags=('board_dynamic',tag))
        self.canvas.create_text((x0+x1)/2, y0+(y1-y0)*0.40, text=lines[0],
                                font=('Arial',label_font,'bold'), fill='#f0d394',
                                tags=('board_dynamic',tag,content_tag))
        if len(lines)>1 and lines[1]:
            self.canvas.create_text((x0+x1)/2, y0+(y1-y0)*0.73, text=lines[1],
                                    font=('Arial',odds_font,'bold'), fill='#ead6ba',
                                    tags=('board_dynamic',tag,content_tag))
        if chip_pos is None:
            chip_pos=((x0+x1)/2,(y0+y1)/2)
        self._register_spot(key, rect, chip_pos,
                            geometry=('rectangle',(x0,y0,x1,y1)), content_tag=content_tag)

    def _draw_traditional_board(self):
        x0,y0,x1,y1 = self.BOARD_ZONE
        left, right = x0+8, x1-8
        top, bottom = y0+8, y1-8
        total_w = right-left

        top_h = 62
        bottom_h = 62
        ssh_h = 56
        # The reference layout is a five-column grid: every top/bottom cell,
        # including the four 角 cells, has exactly the same width.  The two
        # side columns use that same width so their borders meet the diagonal
        # fan regions cleanly.
        outer_cell_w = total_w / 5.0
        side_w = outer_cell_w
        center_top = top + top_h
        center_bottom = bottom - ssh_h - bottom_h
        bottom_row_top = center_bottom
        ssh_top = bottom - ssh_h

        # Top / side / bottom rectangles copied from the uploaded traditional board.
        top_keys=('kwok_1_2','nim_1_2','nim_1_3','nim_1_4','kwok_4_1')
        bx=left
        for i,key in enumerate(top_keys):
            bx1 = right if i==len(top_keys)-1 else left + (i+1)*outer_cell_w
            spec=self.specs[key]
            self._draw_text_rect_spot(key,bx,top,bx1,top+top_h,
                                      lines=(spec.label,spec.odds_text),
                                      chip_pos=((bx+bx1)/2,top+top_h-13),label_font=10)
            bx=bx1

        side_h=(center_bottom-center_top)/3
        for i,key in enumerate(('nim_2_1','nim_2_3','nim_2_4')):
            by0=center_top+i*side_h; by1=center_top+(i+1)*side_h
            spec=self.specs[key]
            self._draw_text_rect_spot(key,left,by0,left+side_w,by1,
                                      lines=(spec.label,spec.odds_text),
                                      chip_pos=(left+side_w-18,(by0+by1)/2),label_font=10)
        for i,key in enumerate(('nim_4_1','nim_4_2','nim_4_3')):
            by0=center_top+i*side_h; by1=center_top+(i+1)*side_h
            spec=self.specs[key]
            self._draw_text_rect_spot(key,right-side_w,by0,right,by1,
                                      lines=(spec.label,spec.odds_text),
                                      chip_pos=(right-side_w+18,(by0+by1)/2),label_font=10)

        bottom_keys=('kwok_2_3','nim_3_1','nim_3_2','nim_3_4','kwok_3_4')
        bx=left
        for i,key in enumerate(bottom_keys):
            bx1 = right if i==len(bottom_keys)-1 else left + (i+1)*outer_cell_w
            spec=self.specs[key]
            self._draw_text_rect_spot(key,bx,bottom_row_top,bx1,bottom_row_top+bottom_h,
                                      lines=(spec.label,spec.odds_text),
                                      chip_pos=((bx+bx1)/2,bottom_row_top+13),label_font=10)
            bx=bx1

        ssh_keys=('ssh_3_2_1','ssh_2_1_4','ssh_4_3_2','ssh_1_4_3')
        ssh_w=total_w/4
        for i,key in enumerate(ssh_keys):
            bx0=left+i*ssh_w; bx1=left+(i+1)*ssh_w
            spec=self.specs[key]
            self._draw_text_rect_spot(key,bx0,ssh_top,bx1,bottom,
                                      lines=(spec.label,spec.odds_text),
                                      chip_pos=((bx0+bx1)/2,ssh_top+14),label_font=10,odds_font=9)

        # Exact centre geometry from the uploaded image: four fan regions are
        # trapezoids surrounding the 2x2 Small/Big/Odd/Even box.
        cx0, cx1 = left+side_w, right-side_w
        cy0, cy1 = center_top, center_bottom
        inner_w = (cx1-cx0)*0.50
        inner_h = (cy1-cy0)*0.47
        icx0=(cx0+cx1)/2-inner_w/2; icx1=icx0+inner_w
        icy0=(cy0+cy1)/2-inner_h/2; icy1=icy0+inner_h

        fan_polys={
            'fan_1': (cx0,cy0, cx1,cy0, icx1,icy0, icx0,icy0),
            'fan_2': (cx0,cy0, icx0,icy0, icx0,icy1, cx0,cy1),
            'fan_4': (cx1,cy0, cx1,cy1, icx1,icy1, icx1,icy0),
            'fan_3': (cx0,cy1, icx0,icy1, icx1,icy1, cx1,cy1),
        }
        for key, pts in fan_polys.items():
            tag=self._bind_spot(key); content_tag=f'content_{key}'
            poly=self.canvas.create_polygon(*pts, fill='#641719', outline='#c59f61', width=2,
                                            tags=('board_dynamic',tag))
            xs=pts[0::2]; ys=pts[1::2]; mx=sum(xs)/4; my=sum(ys)/4
            n=self.specs[key].label
            if key in ('fan_1','fan_3'):
                # Reference: odds sit immediately to the RIGHT of 1 and 3.
                self.canvas.create_text(mx-22,my,text=n,font=('Times New Roman',36,'bold'),
                                        fill='#f0cd84',tags=('board_dynamic',tag,content_tag))
                self.canvas.create_text(mx+35,my+3,anchor='w',text='2.85 : 1',
                                        font=('Arial',9,'bold'),fill='#ead6ba',
                                        tags=('board_dynamic',tag,content_tag))
                chip_pos=(mx+76,my-8)
            else:
                self.canvas.create_text(mx,my-4,text=n,font=('Times New Roman',36,'bold'),
                                        fill='#f0cd84',tags=('board_dynamic',tag,content_tag))
                self.canvas.create_text(mx,my+28,text='2.85 : 1',font=('Arial',9,'bold'),
                                        fill='#ead6ba',tags=('board_dynamic',tag,content_tag))
                chip_pos=(mx,my+45)
            self._register_spot(key,poly,chip_pos,
                                geometry=('polygon',pts),content_tag=content_tag)

        # The diagonal polygon edges above are the visible side connection lines.
        halfx=(icx0+icx1)/2; halfy=(icy0+icy1)/2
        self._draw_text_rect_spot('small',icx0,icy0,halfx,halfy,
                                  lines=('小','0.95 : 1'),chip_pos=(icx0+24,icy0+18),
                                  label_font=11,odds_font=9)
        self._draw_text_rect_spot('big',halfx,icy0,icx1,halfy,
                                  lines=('大','0.95 : 1'),chip_pos=(icx1-24,icy0+18),
                                  label_font=11,odds_font=9)
        self._draw_text_rect_spot('odd',icx0,halfy,halfx,icy1,
                                  lines=('单','0.95 : 1'),chip_pos=(icx0+24,icy1-18),
                                  label_font=11,odds_font=9)
        self._draw_text_rect_spot('even',halfx,halfy,icx1,icy1,
                                  lines=('双','0.95 : 1'),chip_pos=(icx1-24,icy1-18),
                                  label_font=11,odds_font=9)

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        for key, spot in self.bet_spots.items():
            amount = self.bet_state.current_area_bet(key)
            pending_in = float(self.pending_bet_visual_amounts.get(key,0.0))
            if pending_in > 0 and self.stage == 'betting':
                amount = max(0.0, amount-pending_in)

            outcome = self.bet_outcomes.get(key)
            if self.stage in ('settling','settled') and outcome:
                if outcome['status']=='lose':
                    amount=0.0
                elif outcome['status']=='push':
                    amount=float(outcome['stake'])
                elif outcome['status']=='win':
                    if self.flash_mode=='win':
                        amount=float(outcome['return_amount'])
                    else:
                        amount=float(outcome['stake'])

            if self.settlement_return_animating and key in self.settlement_return_keys:
                continue
            if self.stage=='settled':
                amount=0.0
            if amount <= 0:
                continue

            x,y=spot['chip_pos']
            radius = 20 if self.bet_layout == 'simple' else 17
            color=self.bet_chip_color(amount)
            is_25_style = color.lower() == '#22d84b'
            fg='black' if is_25_style else self.contrast_text_color(color)
            tag=f'spot_{key}'
            self.canvas.create_oval(x-radius,y-radius,x+radius,y+radius,
                                    fill='#292522',outline='#151311',width=1,
                                    tags=('bet_chip_dynamic',tag))
            self.canvas.create_oval(x-radius+2,y-radius+2,x+radius-2,y+radius-2,
                                    fill=color,outline='#e2ddd5',width=1,
                                    tags=('bet_chip_dynamic',tag))
            self.canvas.create_text(x,y,text=self.compact_amount(amount),
                                    font=('Arial',max(10,int(radius*0.48)),'bold'),fill=fg,
                                    tags=('bet_chip_dynamic',tag))

    def _complete_pending_bet_visual(self, key, amount):
        pending=max(0.0,float(self.pending_bet_visual_amounts.get(key,0.0))-float(amount))
        if pending>1e-9:
            self.pending_bet_visual_amounts[key]=pending
        else:
            self.pending_bet_visual_amounts.pop(key,None)
        if not self._closing:
            self.update_bet_chips()
            self.canvas.tag_raise('bet_chip_dynamic')

    def place_bet(self, key, amount=None, record_undo=True):
        if self.stage!='betting' or key not in self.visible_keys() or key not in self.bet_spots:
            return False
        requested=float(self.selected_chip if amount is None else amount)
        if requested<=0:
            return False
        minimum_bet, area_maximum, table_maximum = self._bet_limits_for(key)
        area_current=self.bet_state.current_area_bet(key)
        table_current=self.bet_state.total_at_risk()
        allowed=min(requested,area_maximum-area_current,table_maximum-table_current,self.balance)
        allowed=max(0.0,allowed)
        if allowed<minimum_bet-1e-9:
            return False
        if allowed<requested-1e-9:
            messagebox.showwarning('下注限制',f'下注已自动调整为 {self.format_money(allowed)}。',parent=self.winfo_toplevel())

        # Baccarat behaviour: logically add now, but keep this newly-added amount
        # OFF the static destination chip until the flying chip actually arrives.
        self.pending_bet_visual_amounts[key]=self.pending_bet_visual_amounts.get(key,0.0)+allowed
        self.bet_state.add_bet(key,allowed)
        self.balance=self._round_money(self.balance-allowed)
        if record_undo:
            self.undo_stack.append((key,allowed))
        self._persist_balance()
        self.update_display()
        self._animate_chip_motion(
            allowed,self._chip_home_position(allowed),self.bet_spots[key]['chip_pos'],
            on_finish=lambda k=key,a=allowed:self._complete_pending_bet_visual(k,a))
        return True

    def clear_single_bet(self, key):
        if self.stage != "betting":
            return
        refunded = self.bet_state.clear_area(key)
        if refunded <= 0:
            return
        self.balance = self._round_money(self.balance + refunded)
        self.undo_stack = [item for item in self.undo_stack if item[0] != key]
        self.pending_bet_visual_amounts.pop(key, None)
        self._persist_balance()
        start_xy = self.bet_spots.get(key, {}).get("chip_pos", self._chip_home_position(refunded))
        self.display_bets = None
        self.update_display()
        self._animate_chip_motion(refunded, start_xy, self._chip_home_position(refunded))

    def undo_last_bet(self):
        if self.stage != "betting":
            return
        while self.undo_stack:
            key, amount = self.undo_stack.pop()
            removed = self.bet_state.remove_amount(key, amount)
            if removed > 0:
                pending=max(0.0,self.pending_bet_visual_amounts.get(key,0.0)-removed)
                if pending>1e-9:
                    self.pending_bet_visual_amounts[key]=pending
                else:
                    self.pending_bet_visual_amounts.pop(key,None)
                self.balance = self._round_money(self.balance + removed)
                self._persist_balance()
                start_xy = self.bet_spots.get(key, {}).get("chip_pos", self._chip_home_position(removed))
                self.display_bets = None
                self.update_display()
                self._animate_chip_motion(removed, start_xy, self._chip_home_position(removed))
                return

    def clear_bets(self):
        if self.stage != "betting":
            return
        existing = [(key, amount) for key, amount in self.bet_state.bets.items() if amount > 0]
        refunded = self.bet_state.clear_all()
        if refunded <= 0:
            return
        self.balance = self._round_money(self.balance + refunded)
        self.undo_stack.clear()
        self.pending_bet_visual_amounts.clear()
        self._persist_balance()
        self.display_bets = None
        self.update_display()
        for i, (key, amount) in enumerate(existing):
            start_xy = self.bet_spots.get(key, {}).get("chip_pos", self._chip_home_position(amount))
            self._schedule(i * 35, self._animate_chip_motion, amount, start_xy, self._chip_home_position(amount))

    def snapshot_bets(self):
        return [(key, float(amount)) for key, amount in self.bet_state.bets.items() if amount > 0]

    def repeat_last_bets(self):
        if self.stage != "betting" or not self.last_round_bets:
            return
        self.clear_bets()
        converted = []
        skipped = 0
        for old_key, amount in self.last_round_bets:
            if old_key not in self.visible_keys():
                skipped += 1
                continue
            converted.append((old_key, amount))
        required = sum(amount for _key, amount in converted)
        if required <= 0:
            messagebox.showinfo("重复下注", "上局下注在当前版式没有可重复项目。", parent=self.winfo_toplevel())
            return
        if required > self.balance + 1e-9:
            messagebox.showwarning("余额不足", f"重复上局下注需要 {self.format_money(required)}，当前余额为 {self.format_money(self.balance)}。", parent=self.winfo_toplevel())
            return
        for key, amount in converted:
            self.place_bet(key, amount=amount, record_undo=True)
        self.update_display()

    def _collect_outer_buttons(self):
        if self._closing or self.stage != 'collecting':
            return
        if self.outer_removed >= len(self.outside_indices):
            self.outer_removed = len(self.outside_indices)
            self.stage = 'betting'
            self.round_stake_display = 0.0
            self.update_display()
            self.redraw_counter_zone()
            return
        # Take away the outside buttons in visible batches.
        self.outer_removed = min(len(self.outside_indices), self.outer_removed + 25)
        self.redraw_counter_zone()
        self._schedule(70, self._collect_outer_buttons)

    def _count_next_group(self):
        if self._closing or self.stage != "counting":
            return
        remaining = self.round_total_buttons - self.count_removed
        if remaining <= 4:
            self.result_number = remaining
            self.redraw_counter_zone()
            self._schedule(450, self.begin_settlement)
            return
        self.count_removed += 4
        self.redraw_counter_zone()
        remaining_after = self.round_total_buttons - self.count_removed
        delay = 32 if remaining_after > 80 else (55 if remaining_after > 24 else 105)
        self._schedule(delay, self._count_next_group)

    def begin_settlement(self):
        if self.stage!='counting' or self.result_number not in (1,2,3,4):
            return
        resolved=self.engine.resolve_bets(self.bet_state.bets,self.specs,self.result_number)
        self.balance=self._round_money(self.balance+resolved['credit'])
        self.last_return=resolved['credit']
        self.last_net=resolved['net']
        self.bet_outcomes={item['key']:item for item in resolved['outcomes']}
        self.save_round_result()

        self.flash_winning_keys={
            key for key in self.visible_keys()
            if self.engine.bet_status(self.specs[key],self.result_number)=='win'
        }
        self.flash_winner_amounts={}
        self.flash_original_amounts={}
        self.push_return_amounts={}
        for outcome in resolved['outcomes']:
            key=outcome['key']
            if outcome['status']=='win':
                self.flash_winner_amounts[key]=float(outcome['return_amount'])
                self.flash_original_amounts[key]=float(outcome['stake'])
            elif outcome['status']=='push':
                self.push_return_amounts[key]=float(outcome['stake'])

        self.stage='settling'
        self.flash_mode=None
        self.settlement_return_animating=False
        self.settlement_return_keys=set()
        self._persist_balance()
        self.redraw_counter_zone()
        self.update_display()
        self._settlement_flash(0)

    def _set_flash_text_black(self, key):
        spot = self.bet_spots.get(key)
        if not spot:
            return
        tag = spot.get('content_tag')
        if not tag:
            return
        for item in self.canvas.find_withtag(tag):
            try:
                if self.canvas.type(item) != 'text':
                    continue
                if item not in self.flash_text_original_colors:
                    self.flash_text_original_colors[item] = self.canvas.itemcget(item, 'fill')
                self.canvas.itemconfigure(item, fill='#111111')
            except tk.TclError:
                pass

    def _restore_flash_text_colors(self):
        for item, color in list(self.flash_text_original_colors.items()):
            try:
                self.canvas.itemconfigure(item, fill=color)
            except tk.TclError:
                pass
        self.flash_text_original_colors.clear()

    def _settlement_flash(self, step):
        if self._closing or self.stage!='settling':
            return
        if step>=6:
            self.canvas.delete('win_flash_area')
            self._restore_flash_text_colors()
            self.flash_mode='original'
            self.update_bet_chips()
            if not self._start_winning_chip_return():
                self._finish_settlement()
            return

        self.flash_mode='win' if step%2==0 else 'original'
        self.canvas.delete('win_flash_area')
        self._restore_flash_text_colors()
        if self.flash_mode=='win':
            for key in self.flash_winning_keys:
                spot=self.bet_spots.get(key)
                if not spot:
                    continue
                geometry=spot.get('geometry')
                if not geometry:
                    continue
                kind,data=geometry
                if kind=='polygon':
                    self.canvas.create_polygon(*data,fill='#ffffff',outline='#111111',width=2,
                                               tags=('win_flash_area','settlement_flash'))
                else:
                    self.canvas.create_rectangle(*data,fill='#ffffff',outline='#111111',width=2,
                                                 tags=('win_flash_area','settlement_flash'))
                content_tag=spot.get('content_tag')
                if content_tag:
                    self._set_flash_text_black(key)
                    self.canvas.tag_raise(content_tag)
        self.update_bet_chips()
        self.canvas.tag_raise('bet_chip_dynamic')
        self._schedule(450,self._settlement_flash,step+1)

    def _start_winning_chip_return(self):
        returning=[]
        for key,amount in self.flash_winner_amounts.items():
            spot=self.bet_spots.get(key)
            if spot and amount>0:
                returning.append((key,amount,spot))
        for key,amount in self.push_return_amounts.items():
            spot=self.bet_spots.get(key)
            if spot and amount>0:
                returning.append((key,amount,spot))
        if not returning:
            return False

        self.settlement_return_animating=True
        self.settlement_return_keys={key for key,_amount,_spot in returning}
        self.update_bet_chips()
        remaining={'count':len(returning)}

        def one_finished():
            remaining['count']-=1
            if remaining['count']<=0 and not self._closing:
                self.settlement_return_animating=False
                self.settlement_return_keys.clear()
                self._finish_settlement()

        for index,(key,amount,spot) in enumerate(returning):
            start=tuple(spot['chip_pos'])
            target=self._chip_home_position(amount)
            # spread simultaneous returns slightly so they do not merge perfectly
            target=(target[0]+(index-(len(returning)-1)/2)*10,target[1])
            self._animate_chip_motion(amount,start,target,on_finish=one_finished)
        return True

    def _finish_settlement(self):
        self.canvas.delete('win_flash_area')
        self._restore_flash_text_colors()
        self.bet_state.bets.clear()
        self.pending_bet_visual_amounts.clear()
        self.stage = 'settled'
        self.flash_mode = None
        # update_display() also queues the Enter-equivalent new-round action when
        # auto_data=True.  No unconditional test callback is left in normal mode.
        self.update_display()

    def new_round(self):
        if self.stage != 'settled':
            return
        # Other game windows may have completed rounds while this window was
        # animating.  Refresh shared history/statistics before preparing the next round.
        self.sync_result_store_from_disk()
        self.bet_state.bets.clear()
        self.display_bets = None
        self.pending_bet_visual_amounts.clear()
        self.undo_stack.clear()
        self.bet_outcomes = {}
        self.flash_winning_keys = set()
        self.static_winning_keys = set()
        self.result_number = None
        self.round_total_buttons = 0
        self.last_return = 0
        self.count_removed = 0
        self.bowl_offset = 0
        self.round_stake_display = 0.0
        self.prepare_next_round_seed()
        self.stage = 'preparing'
        self.draw_betting_board()
        self.redraw_counter_zone()
        self.update_display()
        self._schedule(700, self._begin_prebet_cover)

    def _reset_spot_styles(self):
        for spot in self.bet_spots.values():
            try:
                self.canvas.itemconfigure(spot['shape_id'],outline=spot['base_outline'],
                                          width=spot['base_width'])
            except tk.TclError:
                pass

    def _apply_outcome_styles(self):
        self._reset_spot_styles()
        # Baccarat-style winning indication is handled by white flash overlays,
        # not permanent green/red borders. Push never flashes.

    def show_detailed_rules(self):
        """Open a concise, current description of this implementation."""
        win = tk.Toplevel(self)
        win.title('经典番摊 — 游戏说明')
        win.geometry('900x700+120+30')
        win.resizable(False, False)
        win.configure(bg='#efe7d4')

        frame = tk.Frame(win, bg='#efe7d4')
        frame.pack(fill='both', expand=True, padx=10, pady=10)
        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side='right', fill='y')
        text = tk.Text(
            frame, wrap='word', yscrollcommand=scrollbar.set,
            font=('Microsoft YaHei', 11), bg='#fffaf0', fg='#22180f',
            padx=18, pady=16, spacing1=2, spacing3=6,
        )
        text.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=text.yview)

        rules = """
    经典番摊 — 游戏说明
    ========================================

    一、本局结果怎样产生
    • 每局先在浅蓝色开摊区生成 400 颗白钮。
    • 白钮直径 12px；初始摆放允许轻微重叠，但两颗白钮最多重叠其直径的 25%。
    • 直径 100px 的碗落下后，会作数次短距离移动；碗真正停下后才固定碗内白钮。
    • 本局结果不是另外抽取：程序直接计算“实际碗内白钮数量 ÷ 4”的余数。
    • 余数 1 / 2 / 3 对应结果 1 / 2 / 3；能被 4 整除时，结果为 4。

    二、一局的完整流程
    1. 铺钮：400 颗白钮随机放入浅蓝色区域。
    2. 盖碗：碗落下并随机移动，停止后固定碗内范围。
    3. 开放下注：玩家可以下注；与此同时，碗外白钮会整体向右推出，并避开碗。
    4. 开摊：碗外白钮全部推出后，按【开摊】或 Enter。
    5. 数钮：竹棒从指定侧最外围开始，每次处理 4 颗。竹棒先靠近，接触前白钮不动；接触后才推动白钮，并保持移动中的白钮不重叠。
    6. 最后余下 1–4 颗后确定结果并结算。
    7. 结算完成后，可按【再来一局】或 Enter 开始下一局。

    三、怎样下注
    • 先在右侧选择筹码，再左键点击下注格。
    • 可以同时在多个下注格下注。
    • 筹码会从筹码区飞到下注区域的中心。
    • 右键点击某下注格：清除该格全部下注并退回余额。
    • 【清除】：清除本局全部下注。
    • 【重复上局下注】：按上局下注内容重新下注；余额或版式不允许的部分不会强行下注。
    • 有下注时不可切换“简易版 / 原版”；全部清除后可再次切换。

    四、简易版下注
    • 1 / 2 / 3 / 4：押中指定余数，净赢赔率 2.85 : 1。
    • 小：结果 1 或 2，净赢赔率 0.95 : 1。
    • 大：结果 3 或 4，净赢赔率 0.95 : 1。
    • 单：结果 1 或 3，净赢赔率 0.95 : 1。
    • 双：结果 2 或 4，净赢赔率 0.95 : 1。
    • 限额：每格最低 $10；每格最高 $50,000；全台最高 $200,000。

    五、原版下注
    • 番 1 / 2 / 3 / 4：规则与简易版相同。
    • 念（例如“1念2”）：开前一个号码为赢；开后一个号码为和，只退本金；其他结果输。
    • 角：标示的两个号码任一开出即赢，净赢赔率 0.95 : 1。
    • 三门：标示的三个号码任一开出即赢，净赢赔率 0.316667 : 1。
    • 原版中央仍保留 小 / 大 / 单 / 双。
    • 限额：偏格最高 $10,000；主格最高 $50,000；全台最高 $300,000。

    六、结算画面
    • 客观上获胜的下注区域会白色闪烁；即使该格没有下注，也会显示本局哪些区域获胜。
    • 赢注：返还本金 + 净赢金额。
    • 和注：不作获胜闪烁，只退回本金。
    • 输注：不返还筹码。
    • “上局获胜”显示的是实际返还金额，包含获胜下注的本金及赢利，也包含和注退回的本金。

    七、历史统计
    • 最近结果显示最近 20 局；最左边是最新一局，越往右越旧。
    • “历史开出比例”可选择最近 50 / 100 / 250 / 500 / 1000 局。
    • 单 / 双、小 / 大、1 / 2 / 3 / 4 三组比例都会按当前所选历史范围重新计算。
    • 1 / 2 / 3 / 4 的彩色比例图内部只显示百分比；对应号码显示在比例图上方。
    • 如果现有历史少于所选数量，就使用当前已有的全部历史记录。
    • 统计不会改变下一局结果；下一局仍由新的白钮位置与碗最终位置决定。
    """
        text.insert('1.0', rules.strip())
        text.config(state='disabled')

    def _persist_balance(self):
        self.balance = self._round_money(self.balance)
        update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def on_close(self):
        if self._closing:
            return
        self._closing = True
        for ident in list(self._after_ids):
            try:
                self.after_cancel(ident)
            except tk.TclError:
                pass
        self._after_ids.clear()

        top = self.winfo_toplevel()
        try:
            if self._return_bind_id:
                top.unbind("<Return>", self._return_bind_id)
        except tk.TclError:
            pass

        self._persist_balance()
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            try:
                top.destroy()
            except tk.TclError:
                pass

    def _clamp_bowl_center(self, x, y):
        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        r = float(self.bowl_radius)
        x = max(fx0 + r + 3, min(fx1 - r - 3, x))
        y = max(fy0 + r + 3, min(fy1 - r - 3, y))
        return float(x), float(y)

    def _draw_bead_indices(self, indices, *, final=False):
        for idx in indices:
            if 0 <= idx < len(self.bead_positions):
                x, y = self.bead_positions[idx]
                self._draw_bead_at(x, y, final=final)

    def _final_targets(self, count):
        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        cx = (fx0 + fx1) / 2
        cy = (fy0 + fy1) / 2
        spacing = 16
        return [(cx + (j - (count - 1) / 2) * spacing, cy) for j in range(count)]

    def _draw_bamboo_stick(self, start_xy, end_xy):
        x0, y0 = start_xy
        x1, y1 = end_xy
        self.canvas.create_line(x0, y0, x1, y1, fill='#e4c477', width=7,
                                capstyle=tk.ROUND, tags='counter_dynamic')
        self.canvas.create_line(x0, y0 - 1, x1, y1 - 1, fill='#7a5b28', width=1,
                                tags='counter_dynamic')

    def _register_spot(self, key, shape_id, chip_pos, base_outline='#d9b57a', base_width=2,
                       geometry=None, content_tag=None):
        """Register a betting spot and force the chip to its geometric centre."""
        centered = chip_pos
        if geometry:
            kind, data = geometry
            if kind == 'rectangle':
                x0, y0, x1, y1 = data
                centered = ((x0 + x1) / 2, (y0 + y1) / 2)
            elif kind == 'polygon':
                xs = data[0::2]
                ys = data[1::2]
                centered = (sum(xs) / len(xs), sum(ys) / len(ys))
        self.bet_spots[key] = {
            'shape_id': shape_id,
            'chip_pos': centered,
            'base_outline': base_outline,
            'base_width': base_width,
            'geometry': geometry,
            'content_tag': content_tag or f'content_{key}',
        }

    def select_chip(self, value):
        if self.stage != 'betting':
            return
        self.selected_chip = float(value)
        for chip_value, (cv, outer) in self.chip_canvases.items():
            selected = float(chip_value) == self.selected_chip
            cv.itemconfigure(outer, outline=GOLD if selected else '#6d655d',
                             width=4 if selected else 2)
        self._refresh_chip_widget_centers()

    def _begin_prebet_cover(self):
        if self._closing or self.stage != 'preparing':
            return
        self.stage = 'covering'
        self.bowl_cover_progress = 0.0
        self.update_display()
        self.redraw_counter_zone()
        self._animate_bowl_cover(0)

    def _animate_bowl_cover(self, step):
        if self._closing or self.stage != 'covering':
            return
        frames = 18
        self.bowl_cover_progress = min(1.0, step / frames)
        self.redraw_counter_zone()
        if step < frames:
            self._schedule(42, self._animate_bowl_cover, step + 1)
            return
        self.stage = 'shifting'
        self._build_bowl_settle_segments()
        self.update_display()
        self._schedule(120, self._animate_next_bowl_segment)

    def _animate_next_bowl_segment(self):
        if self._closing or self.stage != 'shifting':
            return
        if self.bowl_settle_segment_index >= len(self.bowl_settle_segments):
            self._finalize_bowl_selection()
            # Requirement: betting opens exactly when the bowl stops, while the
            # dealer begins taking all outside buttons away.
            self.stage = 'betting'
            self.round_stake_display = 0.0
            self.update_display()
            self.redraw_counter_zone()
            self._schedule(80, self._start_outer_take_batch)
            return
        start, end = self.bowl_settle_segments[self.bowl_settle_segment_index]
        self.bowl_segment_start = start
        self.bowl_segment_end = end
        self.bowl_settle_progress = 0.0
        self._animate_bowl_segment_frame(0)

    def _animate_bowl_segment_frame(self, step):
        if self._closing or self.stage != 'shifting':
            return
        frames = 8
        t = min(1.0, step / frames)
        smooth = t * t * (3 - 2 * t)
        sx, sy = self.bowl_segment_start
        ex, ey = self.bowl_segment_end
        self.bowl_center = (sx + (ex - sx) * smooth, sy + (ey - sy) * smooth)
        self.redraw_counter_zone()
        if step < frames:
            self._schedule(34, self._animate_bowl_segment_frame, step + 1)
            return
        self.bowl_center = tuple(self.bowl_segment_end)
        self.bowl_settle_segment_index += 1
        self._schedule(55, self._animate_next_bowl_segment)

    def _animate_bowl_depart(self, step):
        if self._closing or self.stage != 'opening':
            return
        self.last_win_label.config(text=f'上局获胜: $0')
        frames = 15
        self.bowl_offset = int(22 * step)
        self.redraw_counter_zone()
        if step < frames:
            self._schedule(38, self._animate_bowl_depart, step + 1)
            return
        self.stage = 'counting'
        self.count_removed = 0
        self.counted_groups = []
        self.active_count_group = []
        self.final_line_indices = []
        self.update_display()
        self._schedule(180, self._start_next_count_group)

    def _build_bowl_settle_segments(self):
        cx, cy = self.bowl_center
        segments = []
        diagonals = ((1, 1), (1, -1), (-1, 1), (-1, -1))
        move_count = 3 + secrets.randbelow(4)  # 3..6 moves
        last_dir = None
        for _ in range(move_count):
            choices = [d for d in diagonals if d != last_dir]
            dx_sign, dy_sign = choices[secrets.randbelow(len(choices))]
            dx = 8 + secrets.randbelow(17)   # 8..24px
            dy = 7 + secrets.randbelow(16)   # 7..22px
            nx, ny = self._clamp_bowl_center(cx + dx_sign * dx, cy + dy_sign * dy)
            # If a boundary cancels too much of the requested move, try opposite diagonal.
            if abs(nx - cx) < 3 or abs(ny - cy) < 3:
                dx_sign, dy_sign = -dx_sign, -dy_sign
                nx, ny = self._clamp_bowl_center(cx + dx_sign * dx, cy + dy_sign * dy)
            segments.append(((cx, cy), (nx, ny)))
            cx, cy = nx, ny
            last_dir = (dx_sign, dy_sign)
        self.bowl_settle_segments = segments
        self.bowl_settle_segment_index = 0
        self.bowl_settle_progress = 0.0

    def _draw_bead_at(self, x, y, *, final=False, tag='counter_dynamic'):
        r = self.BEAD_RADIUS
        self.canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill='#ffffff', outline='#000000', width=2,
            tags=tag,
        )
        # A very small centre mark keeps the physical button readable at 15px.
        inner_r = 1.5
        self.canvas.create_oval(
            x - inner_r, y - inner_r, x + inner_r, y + inner_r,
            fill='#dedede' if not final else '#f0cf6c', outline='', tags=tag,
        )

    def _final_displaced_positions(self, indices, progress=1.0):
        """Translate the final 1..4 as one rigid group; do not re-arrange them."""
        if not indices:
            return []
        starts = [self.bead_positions[idx] for idx in indices]
        sx = sum(p[0] for p in starts) / len(starts)
        sy = sum(p[1] for p in starts) / len(starts)
        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        # Result target is central-low enough to be clear of sorted rows.
        tx = (fx0 + fx1) / 2
        ty = (fy0 + fy1) / 2
        smooth = progress * progress * (3 - 2 * progress)
        dx = (tx - sx) * smooth
        dy = (ty - sy) * smooth
        return [(x + dx, y + dy) for x, y in starts]

    def _start_outer_take_batch(self):
        if self._closing or self.stage != 'betting':
            return
        if self.outer_removed >= len(self.outside_indices):
            self.outer_take_batch = []
            self.outer_take_progress = 0.0
            self.update_display()
            self.redraw_counter_zone()
            return
        # All outside buttons move at the same time; no batch-by-batch disappearance.
        self.outer_take_batch = list(self.outside_indices[self.outer_removed:])
        self.outer_take_progress = 0.0
        self._animate_outer_take_frame(0)

    def _animate_outer_take_frame(self, step):
        if self._closing or self.stage != 'betting':
            return
        frames = 18
        self.outer_take_progress = min(1.0, step / frames)
        self.redraw_counter_zone()
        if step < frames:
            self._schedule(28, self._animate_outer_take_frame, step + 1)
            return
        self.outer_removed = len(self.outside_indices)
        self.outer_take_batch = []
        self.outer_take_progress = 0.0
        self.update_display()
        self.redraw_counter_zone()

    @staticmethod
    def _lerp(a, b, t):
        return a + (b - a) * t

    def _outer_sweep_position(self, idx, progress):
        """Move one outside bead to the right while avoiding the covered bowl.

        All outside beads share the same progress clock, so the motion remains one
        simultaneous sweep.  A bead whose straight horizontal path would cross the
        bowl follows a 3-leg polyline: vertical detour -> horizontal pass -> exit.
        """
        sx, sy = self.bead_positions[idx]
        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        cx, cy = self.bowl_center
        clearance = float(self.bowl_radius) + self.BEAD_RADIUS + 5.0
        target_x = fx1 + 42.0 + max(0.0, (sx - fx0) * 0.06)
        p = max(0.0, min(1.0, float(progress)))
        smooth = p*p*(3-2*p)

        # A straight rightward line crosses the bowl only when starting left of it
        # and within the bowl's vertical clearance band.
        crosses = sx < cx + clearance and abs(sy - cy) < clearance
        if not crosses:
            return sx + (target_x - sx) * smooth, sy

        # Choose the shorter safe side (up or down), respecting field boundaries.
        top_y = cy - clearance
        bottom_y = cy + clearance
        room_top = top_y - (fy0 + self.BEAD_RADIUS)
        room_bottom = (fy1 - self.BEAD_RADIUS) - bottom_y
        if sy <= cy and room_top >= -1:
            detour_y = max(fy0 + self.BEAD_RADIUS, top_y)
        elif sy > cy and room_bottom >= -1:
            detour_y = min(fy1 - self.BEAD_RADIUS, bottom_y)
        elif room_top >= room_bottom:
            detour_y = max(fy0 + self.BEAD_RADIUS, top_y)
        else:
            detour_y = min(fy1 - self.BEAD_RADIUS, bottom_y)

        pass_x = cx + clearance + 8.0
        # Three simultaneous path phases.  There is no teleporting through the bowl.
        if smooth < 0.28:
            q = smooth / 0.28
            q = q*q*(3-2*q)
            return sx, sy + (detour_y - sy) * q
        if smooth < 0.72:
            q = (smooth - 0.28) / 0.44
            q = q*q*(3-2*q)
            return sx + (pass_x - sx) * q, detour_y
        q = (smooth - 0.72) / 0.28
        q = q*q*(3-2*q)
        return pass_x + (target_x - pass_x) * q, detour_y + (sy - detour_y) * q

    def _draw_sweep_bar_avoiding_bowl(self, progress):
        """Dealer pushing edge: split around the cup so it never visually cuts through it."""
        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        cx, cy = self.bowl_center
        p = max(0.0, min(1.0, float(progress)))
        smooth = p*p*(3-2*p)
        sweep_x = fx0 - 18 + (fx1 - fx0 + 78) * smooth
        gap = float(self.bowl_radius) + 7.0
        # Only split the pusher while its x-position overlaps the bowl body.
        if abs(sweep_x - cx) <= float(self.bowl_radius) + 8:
            c = self.canvas
            c.create_line(sweep_x, fy0-2, sweep_x, max(fy0-2, cy-gap),
                          fill='#d7b36a', width=7, tags='counter_dynamic')
            c.create_line(sweep_x, min(fy1+2, cy+gap), sweep_x, fy1+2,
                          fill='#d7b36a', width=7, tags='counter_dynamic')
            c.create_line(sweep_x-2, fy0-2, sweep_x-2, max(fy0-2, cy-gap),
                          fill='#715323', width=1, tags='counter_dynamic')
            c.create_line(sweep_x-2, min(fy1+2, cy+gap), sweep_x-2, fy1+2,
                          fill='#715323', width=1, tags='counter_dynamic')
        else:
            self.canvas.create_line(sweep_x, fy0-2, sweep_x, fy1+2,
                                    fill='#d7b36a', width=7, tags='counter_dynamic')
            self.canvas.create_line(sweep_x-2, fy0-2, sweep_x-2, fy1+2,
                                    fill='#715323', width=1, tags='counter_dynamic')

    def prepare_next_round_seed(self):
        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        bead_r = float(self.BEAD_RADIUS)
        diameter = float(self.BEAD_DIAMETER)
        min_distance = diameter * (1.0 - self.MAX_OVERLAP_FRACTION)  # 12 * .75 = 9px
        min_distance_sq = min_distance * min_distance
        min_x, max_x = int(fx0 + bead_r + 1), int(fx1 - bead_r - 1)
        min_y, max_y = int(fy0 + bead_r + 1), int(fy1 - bead_r - 1)

        points = []
        for bead_no in range(self.ROUND_BEAD_COUNT):
            placed = False
            for _attempt in range(4000):
                x = float(min_x + secrets.randbelow(max_x - min_x + 1))
                y = float(min_y + secrets.randbelow(max_y - min_y + 1))
                if all((x-px)*(x-px) + (y-py)*(y-py) >= min_distance_sq
                       for px, py in points):
                    points.append((x, y))
                    placed = True
                    break
            if not placed:
                # Deterministic scan fallback.  It keeps the same 9px separation
                # guarantee instead of silently allowing a deeper overlap.
                step = max(1, int(min_distance + 1))
                offset = bead_no % step
                for gy in range(min_y + offset, max_y + 1, step):
                    for gx in range(min_x + (bead_no * 3) % step, max_x + 1, step):
                        x, y = float(gx), float(gy)
                        if all((x-px)*(x-px) + (y-py)*(y-py) >= min_distance_sq
                               for px, py in points):
                            points.append((x, y))
                            placed = True
                            break
                    if placed:
                        break
            if not placed:
                raise RuntimeError('无法在演示区内生成400颗满足25%重叠限制的白钮。')

        radius = 50.0  # 100px bowl diameter
        cx_min, cx_max = int(fx0 + radius + 3), int(fx1 - radius - 3)
        cy_min, cy_max = int(fy0 + radius + 3), int(fy1 - radius - 3)
        cx = cx_min + secrets.randbelow(max(1, cx_max - cx_min + 1))
        cy = cy_min + secrets.randbelow(max(1, cy_max - cy_min + 1))

        self.bead_positions = points
        self.bowl_center = (float(cx), float(cy))
        self.bowl_radius = radius
        self.inside_indices = []
        self.outside_indices = []
        self.count_order = []
        self.outer_buttons_total = 0
        self.outer_removed = 0
        self.next_round_total_buttons = 0
        self.next_result_number = None
        self.bowl_cover_progress = 0.0

        self.bowl_settle_segments = []
        self.bowl_settle_segment_index = 0
        self.bowl_settle_progress = 0.0
        self.bowl_segment_start = self.bowl_center
        self.bowl_segment_end = self.bowl_center

        self.outer_take_batch = []
        self.outer_take_progress = 0.0

        self.counted_groups = []
        self.active_count_group = []
        self.active_count_progress = 0.0
        self.final_line_indices = []
        self.final_line_progress = 0.0
        self.count_removed = 0

    def create_static_ui(self):
        c = self.canvas
        c.create_rectangle(0, 0, self.WIDTH, self.HEIGHT, fill=BG, outline='', tags='static')
        c.create_rectangle(10, 8, 740, 740, fill=FELT, outline=GOLD_DARK, width=3, tags='static')
        c.create_text(375, 27, text='经典番摊', font=('Arial', 19, 'bold'), fill=GOLD, tags='static')

        x0, y0, x1, y1 = self.COUNTER_ZONE
        c.create_rectangle(x0, y0, x1, y1, fill='#103f39', outline='#5a887a', width=2, tags='static')
        c.create_text(x0 + 14, y0 + 18, anchor='w', text='开摊区 · 每4粒一拨',
                      font=('Arial', 13, 'bold'), fill=TEXT, tags='static')

        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        c.create_rectangle(fx0, fy0, fx1, fy1, fill='#14a6d9', outline='#8fd7ec', width=1,
                           tags=('static', 'bead_field'))

        bx0, by0, bx1, by1 = self.BOARD_ZONE
        c.create_rectangle(bx0, by0, bx1, by1, fill='#5b1214', outline='#ad8852', width=2, tags='static')

        self.create_right_panel_widgets()
        self.redraw_counter_zone()

    def _history_counts(self, limit=None):
        """Count results from the newest selected history window.

        FanTan.json keeps newest record first (ID 1), so slicing [:limit]
        directly represents the latest 50/100/250/500/1000 valid records.
        """
        allowed = (50, 100, 250, 500, 1000)
        if limit is None:
            limit = getattr(self, 'history_ratio_limit', 1000)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 1000
        if limit not in allowed:
            limit = 1000

        counts = {1: 0, 2: 0, 3: 0, 4: 0}
        records = self.runtime_store.get('1000_result', []) if isinstance(self.runtime_store, dict) else []
        valid = 0
        for record in list(records)[:limit]:
            try:
                result = int(record['结果']['最终'])
            except (KeyError, TypeError, ValueError):
                continue
            if result in counts:
                counts[result] += 1
                valid += 1
        return counts, valid

    def set_history_ratio_limit(self, limit):
        """Read the latest shared history, switch window, and redraw."""
        if limit not in (50, 100, 250, 500, 1000):
            return
        # In multi-open use another table may have written new results since this
        # window last refreshed. A history-range click means "read latest", so
        # refresh the shared JSON before slicing the requested newest records.
        self.sync_result_store_from_disk()
        self.history_ratio_limit = int(limit)
        self._update_history_ratio_buttons()
        self._update_ratio_bar()

    def _update_history_ratio_buttons(self):
        selected = getattr(self, 'history_ratio_limit', 1000)
        for limit, button in getattr(self, 'history_ratio_buttons', {}).items():
            active = limit == selected
            try:
                button.config(
                    bg=HEADER_BG if active else '#E6E0D3',
                    fg=TITLE_FG,
                    activebackground=HEADER_BG if active else '#EEE8DC',
                    relief=tk.SUNKEN if active else tk.RAISED,
                    bd=2 if active else 1,
                )
            except tk.TclError:
                pass

    def history_from_store(self):
        values = []
        records = self.runtime_store.get('1000_result', [])
        for record in records[:20]:
            try:
                values.append(int(record['结果']['最终']))
            except (KeyError, TypeError, ValueError):
                pass
        return values

    def _draw_history_strip(self):
        c = self.canvas
        values = list(self.history[:20])
        y = 305
        # Roughly twice the old text scale, while remaining inside the 702px table width.
        c.create_text(116, y, anchor='w', text='最新',
                      font=('Arial', 13, 'bold'), fill='#f3d478', tags='counter_dynamic')
        start_x = 164
        spacing = 24
        color_map = {1:'#b73835', 2:'#2f7f4b', 3:'#315c9c', 4:'#343434'}
        for idx, n in enumerate(values):
            x = start_x + idx * spacing
            c.create_oval(x-10, y-10, x+10, y+10,
                          fill=color_map.get(n, '#343434'), outline='#ddd1b8', width=1,
                          tags='counter_dynamic')
            c.create_text(x, y, text=str(n), font=('Arial', 12, 'bold'), fill='white',
                          tags='counter_dynamic')
        if values:
            oldest_x = start_x + (len(values)-1) * spacing
            c.create_text(min(self.BEAD_FIELD[2]-4, oldest_x+18), y, anchor='w', text='最旧',
                          font=('Arial', 13, 'bold'), fill='#aebfb8', tags='counter_dynamic')
        else:
            c.create_text(start_x, y, anchor='w', text='暂无记录',
                          font=('Arial', 12, 'bold'), fill='#aebfb8', tags='counter_dynamic')

    def update_display(self):
        stage_map = {
            'preparing': '铺钮中',
            'covering': '盖碗中',
            'shifting': '定碗中',
            'betting': '下注阶段',
            'opening': '开盅中',
            'counting': '计数中',
            'settling': '结算中',
            'settled': '结算完成',
        }
        self.balance_label.config(text=f'余额: {self.format_money(self.balance)}')
        self.stage_label.config(text=stage_map.get(self.stage, self.stage))
        current_stake = self.bet_state.total_at_risk() if self.stage == 'betting' else self.round_stake_display
        self.current_bet_label.config(text=f'本局下注: {self.format_money(current_stake)}')
        self.last_win_label.config(text=f'上局获胜: {self.format_money(self.last_return)}')
        self._update_limit_display()
        self._update_layout_buttons()
        self._render_action_buttons()
        self.update_bet_chips()
        self._apply_outcome_styles()
        self._update_ratio_bar()
        self._queue_auto_enter()

    def _queue_auto_enter(self):
        """Schedule one Enter-equivalent action when auto_data permits it.

        This does not skip physical animations. It only replaces the player's Enter
        press at the two legal points: after the outside sweep is complete, and after
        settlement is complete.
        """
        if not self.auto_data or self._closing:
            return

        stage = self.stage
        if stage == 'betting':
            if self.outer_removed < len(self.outside_indices):
                return
        elif stage != 'settled':
            return

        if self._auto_enter_pending_stage == stage:
            return
        self._auto_enter_pending_stage = stage
        self._schedule(120, self._auto_enter_once, stage)


    def _auto_enter_once(self, expected_stage):
        if self._auto_enter_pending_stage == expected_stage:
            self._auto_enter_pending_stage = None
        if not self.auto_data or self._closing or self.stage != expected_stage:
            return
        if expected_stage == 'betting' and self.outer_removed < len(self.outside_indices):
            return
        self._on_enter()

    @staticmethod
    def _integer_percentages_total_100(counts, total):
        """Nearest practical integer percentages, apportioned to sum exactly 100."""
        if total <= 0:
            return {1: 0, 2: 0, 3: 0, 4: 0}
        raw = {n: (float(counts.get(n, 0)) * 100.0 / float(total)) for n in (1, 2, 3, 4)}
        base = {n: int(raw[n]) for n in (1, 2, 3, 4)}
        remaining = 100 - sum(base.values())
        # Largest-remainder apportionment: preserves the closest integer split
        # while guaranteeing that the displayed total is exactly 100%.
        order = sorted((1, 2, 3, 4), key=lambda n: (raw[n] - base[n], counts.get(n, 0), -n), reverse=True)
        for n in order[:max(0, remaining)]:
            base[n] += 1
        return base

    def _layout_switch_allowed(self):
        # Once a new round is requested, players may choose the layout while the
        # 400-button / bowl pre-bet demonstration is running.
        if self.stage in ('preparing', 'covering', 'shifting'):
            return True
        # During betting, the selector locks as soon as ANY wager exists and
        # immediately unlocks again after all wagers are cleared.
        if self.stage == 'betting':
            return self.bet_state.total_at_risk() <= 1e-9
        return False

    def switch_bet_layout(self, layout):
        if layout not in ('simple', 'traditional') or layout == self.bet_layout:
            return
        if not self._layout_switch_allowed():
            return
        self.bet_layout = layout
        self.draw_betting_board()
        self.update_display()

    def _update_limit_display(self):
        """Show only the three limits that apply to the selected layout."""
        if self.bet_layout == 'simple':
            headers = ('每格最低', '每格最高', '全台最高')
            values = ('$10', '$50,000', '$200,000')
        else:
            headers = ('偏格最高', '主格最高', '全台最高')
            values = ('$10,000', '$50,000', '$300,000')

        for label, text in zip(getattr(self, 'limit_header_labels', ()), headers):
            label.config(text=text)
        for label, text in zip(getattr(self, 'limit_value_labels', ()), values):
            label.config(text=text)

    def _update_layout_buttons(self):
        enabled = self._layout_switch_allowed()
        for mode, button in self.layout_buttons.items():
            selected = mode == self.bet_layout
            button.config(
                bg=HEADER_BG if selected else '#E6E0D3',
                fg=TITLE_FG,
                activebackground=HEADER_BG if selected else '#EEE8DC',
                relief=tk.SUNKEN if selected else tk.RAISED,
                state=tk.NORMAL if enabled else tk.DISABLED,
            )

    @staticmethod
    def _world_to_axes(point, ux, uy, px, py):
        x, y = point
        return x*ux + y*uy, x*px + y*py

    @staticmethod
    def _axes_to_world(ucoord, pcoord, ux, uy, px, py):
        return ucoord*ux + pcoord*px, ucoord*uy + pcoord*py

    @staticmethod
    def _spread_offsets_min_gap(values, gap):
        """Preserve order/mean while enforcing a minimum spacing along the stick."""
        if len(values) <= 1:
            return list(values)
        order = sorted(range(len(values)), key=lambda i: values[i])
        sorted_vals = [float(values[i]) for i in order]
        adjusted = list(sorted_vals)
        for i in range(1, len(adjusted)):
            adjusted[i] = max(adjusted[i], adjusted[i-1] + gap)
        # Re-centre to the original mean so the line does not teleport sideways.
        original_mean = sum(sorted_vals) / len(sorted_vals)
        adjusted_mean = sum(adjusted) / len(adjusted)
        shift = original_mean - adjusted_mean
        adjusted = [v + shift for v in adjusted]
        result = [0.0] * len(values)
        for idx, value in zip(order, adjusted):
            result[idx] = value
        return result

    def _finalize_bowl_selection(self):
        """Freeze the actual bowl-covered set after the bowl finishes moving."""
        cx, cy = self.bowl_center
        radius = float(self.bowl_radius)
        inside = [
            i for i, (px, py) in enumerate(self.bead_positions)
            if (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2
        ]
        if not inside:
            nearest = min(
                range(len(self.bead_positions)),
                key=lambda i: (self.bead_positions[i][0] - cx) ** 2
                              + (self.bead_positions[i][1] - cy) ** 2,
            )
            inside = [nearest]

        inside_set = set(inside)
        self.inside_indices = list(inside)
        self.outside_indices = [i for i in range(len(self.bead_positions)) if i not in inside_set]

        # Outermost-first baseline; the live counter later chooses the corresponding
        # left/right edge seed and its nearest three neighbours for each physical group.
        self.count_order = sorted(
            self.inside_indices,
            key=lambda i: (
                -((self.bead_positions[i][0] - cx) ** 2 + (self.bead_positions[i][1] - cy) ** 2),
                self.bead_positions[i][1],
                self.bead_positions[i][0],
            ),
        )
        self.outer_buttons_total = len(self.outside_indices)
        self.outer_removed = 0
        self.next_round_total_buttons = len(inside)
        rem = len(inside) % 4
        self.next_result_number = rem if rem else 4
        self.counted_groups = []
        self.active_count_group = []
        self.final_line_indices = []

    def _on_enter(self, _event=None):
        # Enter == 开摊 during betting; Enter == 再来一局 after settlement.
        if self.stage == 'betting':
            self.start_round()
        elif self.stage == 'settled':
            self.new_round()

    def _resolve_non_overlap_axes(self, u_values, p_values, movable, desired_order, min_distance=None):
        """Adjust only the perpendicular-axis coordinates to prevent overlap.

        Beads keep their along-stick coordinate ``u`` so the movement still looks
        like a real push.  Only the sideways coordinate ``p`` is relaxed, and
        only for beads that are allowed to move in the current frame.
        """
        n = len(p_values)
        if n <= 1:
            return list(p_values)
        u = [float(v) for v in u_values]
        p = [float(v) for v in p_values]
        movable = [bool(v) for v in movable]
        desired = list(desired_order) if desired_order is not None else list(range(n))
        rank = {idx: order for order, idx in enumerate(desired)}
        min_d = float(self.BEAD_DIAMETER + 0.25 if min_distance is None else min_distance)

        for _ in range(28):
            changed = False
            for i in range(n):
                for j in range(i + 1, n):
                    du = abs(u[j] - u[i])
                    if du >= min_d:
                        continue
                    req = (max(0.0, min_d * min_d - du * du)) ** 0.5 + 0.02
                    dp = p[j] - p[i]
                    if abs(dp) >= req:
                        continue
                    # Preserve intended ordering along the line whenever possible.
                    if abs(dp) > 1e-6:
                        sign = 1.0 if dp > 0 else -1.0
                    else:
                        sign = 1.0 if rank.get(j, j) >= rank.get(i, i) else -1.0
                    adjust = req - abs(dp)
                    if movable[i] and movable[j]:
                        p[i] -= sign * adjust / 2.0
                        p[j] += sign * adjust / 2.0
                        changed = True
                    elif movable[i]:
                        p[i] -= sign * adjust
                        changed = True
                    elif movable[j]:
                        p[j] += sign * adjust
                        changed = True
            if not changed:
                break
        return p

    def _build_spaced_targets(self, starts, targets):
        if not starts:
            return []
        scx = sum(x for x, _ in starts) / len(starts)
        scy = sum(y for _, y in starts) / len(starts)
        tcx = sum(x for x, _ in targets) / len(targets)
        tcy = sum(y for _, y in targets) / len(targets)

        vx, vy = tcx - scx, tcy - scy
        mag = max(1.0, (vx * vx + vy * vy) ** 0.5)
        ux, uy = vx / mag, vy / mag
        px, py = -uy, ux

        start_axes = [self._world_to_axes(pt, ux, uy, px, py) for pt in starts]
        target_axes = [self._world_to_axes(pt, ux, uy, px, py) for pt in targets]
        start_p = [p for _u, p in start_axes]
        ordered_target_p = sorted(p for _u, p in target_axes)
        ordered_target_p = self._spread_offsets_min_gap(ordered_target_p, self.BEAD_DIAMETER + 0.5)

        source_order = sorted(range(len(start_p)), key=lambda i: start_p[i])
        p_targets = [0.0] * len(starts)
        for src_idx, target_p in zip(source_order, ordered_target_p):
            p_targets[src_idx] = target_p
        return p_targets

    def start_round(self):
        """Close betting and start the bowl-opening/counting sequence."""
        self._count_stick_last_pose = None
        self._count_stick_entry_pose = None

        if self.stage != 'betting':
            return
        # Betting opens while the outside beads are still being pushed away, but
        # opening the bowl is not allowed until that sweep is physically complete.
        if self.outer_removed < len(self.outside_indices):
            return

        self.counted_groups = []
        self.active_count_group = []
        self.active_count_progress = 0.0
        self.final_line_indices = []
        self.final_line_progress = 0.0

        self.last_round_bets = self.snapshot_bets()
        self.round_stake_display = self.bet_state.total_at_risk()
        self.result_number = int(self.next_result_number)
        self.round_total_buttons = int(self.next_round_total_buttons)
        self.count_removed = 0
        self.bowl_offset = 0
        self.bet_outcomes = {}
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.push_return_amounts = {}
        self.flash_mode = None
        self.pending_bet_visual_amounts.clear()
        self.stage = 'opening'
        self.update_display()
        self.redraw_counter_zone()
        self._schedule(120, self._animate_bowl_depart, 0)

    def _stable_push_axes(self, starts, target_center):
        scx = sum(x for x, _ in starts) / len(starts)
        scy = sum(y for _, y in starts) / len(starts)
        dx = target_center[0] - scx
        dy = target_center[1] - scy
        dist = (dx * dx + dy * dy) ** 0.5

        if dist >= 22.0:
            ux, uy = dx / dist, dy / dist
            return ux, uy, -uy, ux

        # If the final pile is already close to centre, source->target becomes
        # numerically unstable.  Use the pile's natural long axis for the stick
        # direction instead of letting the bar spin or collapse.
        if len(starts) >= 2:
            mx, my = scx, scy
            cxx = sum((x - mx) ** 2 for x, _ in starts) / len(starts)
            cyy = sum((y - my) ** 2 for _, y in starts) / len(starts)
            cxy = sum((x - mx) * (y - my) for x, y in starts) / len(starts)
            if cxx + cyy > 1e-6:
                import math
                theta = 0.5 * math.atan2(2.0 * cxy, cxx - cyy)
                # p-axis follows the pile's natural line; u-axis is the push normal.
                px, py = math.cos(theta), math.sin(theta)
                ux, uy = -py, px
                # Pick a deterministic direction; if a small target vector exists,
                # prefer the normal that points generally toward the centre.
                if dist > 1e-6:
                    if ux * dx + uy * dy < 0:
                        ux, uy = -ux, -uy
                        px, py = -px, -py
                elif ux < -1e-6 or (abs(ux) <= 1e-6 and uy < 0):
                    ux, uy = -ux, -uy
                    px, py = -px, -py
                return ux, uy, px, py

        # Single final bead or near-perfect circular cluster: use one stable
        # left-to-right push rather than a degenerate zero-length vector.
        return 1.0, 0.0, 0.0, 1.0

    @staticmethod
    def _interp_point(a, b, t):
        return (a[0] + (b[0] - a[0]) * t,
                a[1] + (b[1] - a[1]) * t)

    def _interp_stick(self, start_pose, end_pose, t):
        if start_pose is None:
            return end_pose
        return (
            self._interp_point(start_pose[0], end_pose[0], t),
            self._interp_point(start_pose[1], end_pose[1], t),
        )

    def _stick_pose(self, bar_u, bar_p, half_len, ux, uy, px, py):
        cx, cy = self._axes_to_world(bar_u, bar_p, ux, uy, px, py)
        return (
            (cx - px * half_len, cy - py * half_len),
            (cx + px * half_len, cy + py * half_len),
        )

    def _resolve_world_moving_collisions(self, positions, movable, min_distance=None):
        """Prevent overlap for every bead that has begun moving.

        Untouched beads are allowed to retain the small pre-existing overlap from
        the initial random pile.  As soon as either bead in a pair is moving, the
        pair is separated to at least one bead diameter.
        """
        import math
        pts = [[float(x), float(y)] for x, y in positions]
        movable = [bool(v) for v in movable]
        min_d = float(self.BEAD_DIAMETER + 0.25 if min_distance is None else min_distance)
        for _ in range(28):
            changed = False
            for i in range(len(pts)):
                for j in range(i + 1, len(pts)):
                    if not (movable[i] or movable[j]):
                        continue
                    dx = pts[j][0] - pts[i][0]
                    dy = pts[j][1] - pts[i][1]
                    d = math.hypot(dx, dy)
                    if d >= min_d - 1e-6:
                        continue
                    if d < 1e-6:
                        # Deterministic sideways separation for an exact overlap.
                        nx, ny = 0.0, 1.0
                    else:
                        nx, ny = dx / d, dy / d
                    overlap = min_d - d + 0.02
                    if movable[i] and movable[j]:
                        pts[i][0] -= nx * overlap / 2.0
                        pts[i][1] -= ny * overlap / 2.0
                        pts[j][0] += nx * overlap / 2.0
                        pts[j][1] += ny * overlap / 2.0
                    elif movable[i]:
                        pts[i][0] -= nx * overlap
                        pts[i][1] -= ny * overlap
                    else:
                        pts[j][0] += nx * overlap
                        pts[j][1] += ny * overlap
                    changed = True
            if not changed:
                break
        return [(x, y) for x, y in pts]

    def _physical_group_to_targets(self, indices, targets, progress):
        starts = [self.bead_positions[idx] for idx in indices]
        if not starts:
            return [], None
        if not targets:
            targets = list(starts)

        scx = sum(x for x, _ in starts) / len(starts)
        scy = sum(y for _, y in starts) / len(starts)
        tcx = sum(x for x, _ in targets) / len(targets)
        tcy = sum(y for _, y in targets) / len(targets)
        ux, uy, px, py = self._stable_push_axes(starts, (tcx, tcy))

        start_axes = [self._world_to_axes(pt, ux, uy, px, py) for pt in starts]
        target_axes = [self._world_to_axes(pt, ux, uy, px, py) for pt in targets]
        start_u = [u for u, _ in start_axes]
        start_p = [pv for _, pv in start_axes]

        # Ordinary counted rows may still use the established rack coordinates.
        ordered_target_p = sorted(pv for _u, pv in target_axes)
        ordered_target_p = self._spread_offsets_min_gap(
            ordered_target_p, self.BEAD_DIAMETER + 0.5
        )
        source_order = sorted(range(len(start_p)), key=lambda i: start_p[i])
        p_targets = [0.0] * len(starts)
        for src_idx, target_p in zip(source_order, ordered_target_p):
            p_targets[src_idx] = target_p
        desired_order = sorted(range(len(start_p)), key=lambda i: p_targets[i])

        min_u = min(start_u)
        max_u = max(start_u)
        target_u = sum(u for u, _pv in target_axes) / len(target_axes)
        # A physical one-sided push cannot reverse after collecting the row.
        # Keep the destination at or beyond the final contact line.
        target_u = max(target_u, max_u + 1.0)
        mean_start_p = sum(start_p) / len(start_p)
        mean_target_p = sum(p_targets) / len(p_targets)
        contact_gap = self.BEAD_RADIUS + 5.0
        pmin, pmax = min(p_targets), max(p_targets)
        half_len = max(34.0, (pmax - pmin) / 2.0 + 18.0)

        approach_start_u = min_u - contact_gap - 64.0
        approach_contact_u = min_u - contact_gap
        relocation_pose = self._stick_pose(
            approach_start_u, mean_start_p, half_len, ux, uy, px, py
        )
        contact_pose = self._stick_pose(
            approach_contact_u, mean_start_p, half_len, ux, uy, px, py
        )

        p = max(0.0, min(1.0, float(progress)))
        # 0..18% relocate the stick from the previous group; beads do not move.
        # 18..38% approach the new group; beads still do not move.
        # 38..72% contact/sweep; only touched beads move.
        # 72..100% push the formed row to its rack.
        if p < 0.18:
            q = p / 0.18
            s = q * q * (3 - 2 * q)
            bead_positions = list(starts)
            stick = self._interp_stick(
                getattr(self, '_count_stick_entry_pose', None), relocation_pose, s
            )
            return bead_positions, stick

        if p < 0.38:
            q = (p - 0.18) / 0.20
            s = q * q * (3 - 2 * q)
            bead_positions = list(starts)
            stick = self._interp_stick(relocation_pose, contact_pose, s)
            return bead_positions, stick

        if p < 0.72:
            q = (p - 0.38) / 0.34
            s = q * q * (3 - 2 * q)
            front_u = self._lerp(min_u, max_u, s)
            bar_u = front_u - contact_gap
            current_u = []
            current_p = []
            movable = []
            for su, sp, tp in zip(start_u, start_p, p_targets):
                if front_u <= su:
                    current_u.append(su)
                    current_p.append(sp)
                    movable.append(False)
                    continue
                local = max(0.0, min(1.0,
                    (front_u - su) / max(1e-6, max_u - su)))
                ls = local * local * (3 - 2 * local)
                current_u.append(front_u)
                current_p.append(self._lerp(sp, tp, ls))
                movable.append(True)
            current_p = self._resolve_non_overlap_axes(
                current_u, current_p, movable, desired_order,
                min_distance=self.BEAD_DIAMETER + 0.25,
            )
            bead_positions = [
                self._axes_to_world(u0, p0, ux, uy, px, py)
                for u0, p0 in zip(current_u, current_p)
            ]
            bead_positions = self._resolve_world_moving_collisions(
                bead_positions, movable, self.BEAD_DIAMETER + 0.25
            )
            stick = self._stick_pose(
                bar_u,
                self._lerp(mean_start_p, mean_target_p, s),
                half_len, ux, uy, px, py,
            )
            return bead_positions, stick

        q = (p - 0.72) / 0.28
        s = q * q * (3 - 2 * q)
        line_u = self._lerp(max_u, target_u, s)
        current_u = [line_u] * len(starts)
        current_p = list(p_targets)
        movable = [True] * len(starts)
        current_p = self._resolve_non_overlap_axes(
            current_u, current_p, movable, desired_order,
            min_distance=self.BEAD_DIAMETER + 0.25,
        )
        bead_positions = [
            self._axes_to_world(u0, p0, ux, uy, px, py)
            for u0, p0 in zip(current_u, current_p)
        ]
        bead_positions = self._resolve_world_moving_collisions(
            bead_positions, movable, self.BEAD_DIAMETER + 0.25
        )
        stick = self._stick_pose(
            line_u - contact_gap, mean_target_p,
            half_len, ux, uy, px, py,
        )
        return bead_positions, stick

    def _active_group_visuals(self, active, progress):
        targets = self._group_targets(len(self.counted_groups), len(active))
        positions, stick = self._physical_group_to_targets(active, targets, progress)
        if stick is not None:
            self._count_stick_last_pose = stick
        return positions, stick

    def _final_group_visuals(self, indices, progress):
        starts = [self.bead_positions[idx] for idx in indices]
        if not starts:
            return [], None

        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        centre = ((fx0 + fx1) / 2.0, (fy0 + fy1) / 2.0)
        ux, uy, px, py = self._stable_push_axes(starts, centre)
        axes = [self._world_to_axes(pt, ux, uy, px, py) for pt in starts]
        start_u = [u for u, _ in axes]
        start_p = [pv for _, pv in axes]
        min_u = min(start_u)
        max_u = max(start_u)

        # Preserve the pile's natural sideways order/spacing.  Only separate
        # beads enough to prevent overlap; do NOT force a horizontal layout.
        p_targets = self._spread_offsets_min_gap(
            start_p, self.BEAD_DIAMETER + 1.0
        )
        # Keep the row centred on its original lateral centre so the bamboo never
        # walks sideways while it pushes.
        original_mean_p = sum(start_p) / len(start_p)
        adjusted_mean_p = sum(p_targets) / len(p_targets)
        p_targets = [v + (original_mean_p - adjusted_mean_p) for v in p_targets]
        desired_order = sorted(range(len(start_p)), key=lambda i: p_targets[i])
        mean_p = sum(p_targets) / len(p_targets)

        centre_u, _centre_p = self._world_to_axes(centre, ux, uy, px, py)
        # Never make the stick reverse just to hit an exact mathematical centre.
        # If the source already straddles the centre, finish slightly beyond it in
        # the push direction—the row still visually occupies the centre area.
        target_u = max(centre_u, max_u + 2.0)

        contact_gap = self.BEAD_RADIUS + 5.0
        pmin, pmax = min(p_targets), max(p_targets)
        half_len = max(32.0, (pmax - pmin) / 2.0 + 17.0)
        approach_start_u = min_u - contact_gap - 62.0
        approach_contact_u = min_u - contact_gap
        relocation_pose = self._stick_pose(
            approach_start_u, original_mean_p, half_len, ux, uy, px, py
        )
        contact_pose = self._stick_pose(
            approach_contact_u, original_mean_p, half_len, ux, uy, px, py
        )

        p = max(0.0, min(1.0, float(progress)))
        if p < 0.18:
            q = p / 0.18
            s = q * q * (3 - 2 * q)
            positions = list(starts)
            stick = self._interp_stick(
                getattr(self, '_count_stick_entry_pose', None), relocation_pose, s
            )
        elif p < 0.38:
            q = (p - 0.18) / 0.20
            s = q * q * (3 - 2 * q)
            positions = list(starts)
            stick = self._interp_stick(relocation_pose, contact_pose, s)
        elif p < 0.72:
            q = (p - 0.38) / 0.34
            s = q * q * (3 - 2 * q)
            front_u = self._lerp(min_u, max_u, s)
            current_u = []
            current_p = []
            movable = []
            for su, sp, tp in zip(start_u, start_p, p_targets):
                if front_u <= su:
                    current_u.append(su)
                    current_p.append(sp)
                    movable.append(False)
                    continue
                local = max(0.0, min(1.0,
                    (front_u - su) / max(1e-6, max_u - su)))
                ls = local * local * (3 - 2 * local)
                current_u.append(front_u)
                current_p.append(self._lerp(sp, tp, ls))
                movable.append(True)
            current_p = self._resolve_non_overlap_axes(
                current_u, current_p, movable, desired_order,
                min_distance=self.BEAD_DIAMETER + 0.25,
            )
            positions = [
                self._axes_to_world(u0, p0, ux, uy, px, py)
                for u0, p0 in zip(current_u, current_p)
            ]
            positions = self._resolve_world_moving_collisions(
                positions, movable, self.BEAD_DIAMETER + 0.25
            )
            stick = self._stick_pose(
                front_u - contact_gap, original_mean_p,
                half_len, ux, uy, px, py,
            )
        else:
            q = (p - 0.72) / 0.28
            s = q * q * (3 - 2 * q)
            line_u = self._lerp(max_u, target_u, s)
            current_u = [line_u] * len(starts)
            current_p = list(p_targets)
            movable = [True] * len(starts)
            current_p = self._resolve_non_overlap_axes(
                current_u, current_p, movable, desired_order,
                min_distance=self.BEAD_DIAMETER + 0.25,
            )
            positions = [
                self._axes_to_world(u0, p0, ux, uy, px, py)
                for u0, p0 in zip(current_u, current_p)
            ]
            positions = self._resolve_world_moving_collisions(
                positions, movable, self.BEAD_DIAMETER + 0.25
            )
            stick = self._stick_pose(
                line_u - contact_gap, mean_p,
                half_len, ux, uy, px, py,
            )

        if stick is not None:
            self._count_stick_last_pose = stick
        return positions, stick

    def _animate_count_group(self, step):
        if self._closing or self.stage != 'counting' or not self.active_count_group:
            return
        frames = self.COUNT_FRAMES
        self.active_count_progress = min(1.0, step / frames)
        self.redraw_counter_zone()
        if step < frames:
            self._schedule(self.COUNT_FRAME_MS, self._animate_count_group, step + 1)
            return
        # Capture the final pose before the active group disappears.
        _positions, stick = self._active_group_visuals(self.active_count_group, 1.0)
        if stick is not None:
            self._count_stick_last_pose = stick
        self.counted_groups.append(list(self.active_count_group))
        self.count_removed += len(self.active_count_group)
        self.active_count_group = []
        self.active_count_progress = 0.0
        self.redraw_counter_zone()
        self._schedule(220, self._start_next_count_group)

    def _animate_final_line(self, step):
        if self._closing or self.stage != 'counting':
            return
        frames = self.FINAL_FRAMES
        self.final_line_progress = min(1.0, step / frames)
        self.redraw_counter_zone()
        if step < frames:
            self._schedule(self.FINAL_FRAME_MS, self._animate_final_line, step + 1)
            return
        self.final_line_progress = 1.0
        self.redraw_counter_zone()
        self._schedule(650, self.begin_settlement)

    def _group_targets(self, group_index, count=4):
        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        field_mid_x = (fx0 + fx1) / 2.0
        field_mid_y = (fy0 + fy1) / 2.0

        # Resolve the real bead group so the target line can follow the actual
        # approach direction instead of an arbitrary screen-horizontal row.
        group = None
        if 0 <= group_index < len(getattr(self, 'counted_groups', [])):
            group = list(self.counted_groups[group_index])
        elif group_index == len(getattr(self, 'counted_groups', [])):
            active = list(getattr(self, 'active_count_group', []) or [])
            if active:
                group = active

        # Lay completed fours at the side opposite the bowl.  Successive groups
        # step inward horizontally, keeping them away from the odd top corners.
        right_side = self.bowl_center[0] <= field_mid_x
        edge_margin = 40.0
        column_gap = self.BEAD_DIAMETER + 10.0
        # If many groups are required, start a second centred bank instead of
        # climbing into the upper/lower corner.
        cols_per_bank = 10
        bank = group_index // cols_per_bank
        col = group_index % cols_per_bank
        bank_y_offset = (bank - 0.5 * max(0, (group_index // cols_per_bank))) * 46.0 if bank else 0.0
        target_cy = max(fy0 + 31.0, min(fy1 - 31.0, field_mid_y + bank_y_offset))
        if right_side:
            target_cx = fx1 - edge_margin - col * column_gap
        else:
            target_cx = fx0 + edge_margin + col * column_gap

        if group:
            starts = [self.bead_positions[i] for i in group[:count]]
            scx = sum(x for x, _ in starts) / len(starts)
            scy = sum(y for _, y in starts) / len(starts)
            dx = target_cx - scx
            dy = target_cy - scy
            mag = max(1.0, (dx*dx + dy*dy) ** 0.5)
            ux, uy = dx/mag, dy/mag
            # The counted four sits in the cradle line of the stick: its row is
            # perpendicular to the actual push, not forcibly horizontal.
            px, py = -uy, ux
        else:
            # Stable fallback: sideward push gives a vertical quartet.
            ux = 1.0 if right_side else -1.0
            uy = 0.0
            px, py = 0.0, 1.0

        spacing = self.BEAD_DIAMETER + 1.5
        offsets = [(j - (count - 1) / 2.0) * spacing for j in range(count)]
        return [(target_cx + px*off, target_cy + py*off) for off in offsets]

    def create_right_panel_widgets(self):
        panel = tk.Frame(self, bg=ROOT_BG, width=400, height=734)
        panel.place(x=750, y=8, width=400, height=734)
        panel.pack_propagate(False)
        self.right_panel = panel

        def card(title, title_size=13):
            outer = tk.Frame(panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
            outer.pack(fill=tk.X, pady=3, padx=(0, 1))
            header = tk.Frame(outer, bg=HEADER_BG)
            header.pack(fill=tk.X)
            tk.Label(header, text=title, font=('Arial', title_size, 'bold'),
                     bg=HEADER_BG, fg=TITLE_FG).pack(pady=3)
            return outer

        info_card = card('经典番摊', 14)
        body = tk.Frame(info_card, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=12, pady=6)
        self.balance_label = tk.Label(body, text='余额: $0.00', font=('Arial', 15, 'bold'),
                                      bg=PANEL_BG, fg='black')
        self.balance_label.pack(side=tk.LEFT)
        self.stage_label = tk.Label(body, text='下注阶段', font=('Arial', 14, 'bold'),
                                    bg=PANEL_BG, fg='#A88100')
        self.stage_label.pack(side=tk.RIGHT)

        limit_card = card('下注上限', 12)
        body = tk.Frame(limit_card, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=10, pady=5)
        table = tk.Frame(body, bg=PANEL_BG)
        table.pack(fill=tk.X)
        self.limit_header_labels = []
        self.limit_value_labels = []
        for col in range(3):
            header_label = tk.Label(
                table, text='', font=('Arial', 9, 'bold'), bg=PANEL_BG,
                relief=tk.SOLID, borderwidth=1, pady=2,
            )
            header_label.grid(row=0, column=col, sticky='nsew')
            value_label = tk.Label(
                table, text='', font=('Arial', 10, 'bold'), bg=PANEL_BG,
                fg='#A88100', relief=tk.SOLID, borderwidth=1, pady=2,
            )
            value_label.grid(row=1, column=col, sticky='nsew')
            self.limit_header_labels.append(header_label)
            self.limit_value_labels.append(value_label)
            table.columnconfigure(col, weight=1)
        self._update_limit_display()

        # Chips + bet-layout selection are one card now.
        bet_card = card('筹码与版本', 12)
        body = tk.Frame(bet_card, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=9, pady=5)
        chip_row = tk.Frame(body, bg=PANEL_BG)
        chip_row.pack(fill=tk.X)
        for i in range(len(CHIPS)):
            chip_row.columnconfigure(i, weight=1)
        display_labels = {10:'$10', 25:'$25', 100:'$100', 500:'$500', 1000:'$1K', 2500:'$2.5K'}
        self.chip_canvases = {}
        for col, (value, color, _label) in enumerate(CHIPS):
            cell = tk.Frame(chip_row, bg=PANEL_BG)
            cell.grid(row=0, column=col, sticky='nsew', padx=2)
            cv = tk.Canvas(cell, width=49, height=49, bg=PANEL_BG, highlightthickness=0)
            cv.pack(anchor='center')
            outer = cv.create_oval(2, 2, 47, 47, fill='#2b2825', outline='#6d655d', width=2)
            cv.create_oval(6, 6, 43, 43, fill=color, outline='#ddd', width=1)
            fg = 'black' if value == 25 else self.contrast_text_color(color)
            cv.create_text(24.5, 24.5, text=display_labels[value], fill=fg, font=('Arial', 9, 'bold'))
            cv.bind('<Button-1>', lambda _e, v=value: self.select_chip(v))
            cv.bind('<Enter>', lambda _e, w=cv: w.config(cursor='hand2' if self.stage == 'betting' else 'X_cursor'))
            cv.bind('<Leave>', lambda _e, w=cv: w.config(cursor=''))
            self.chip_canvases[value] = (cv, outer)

        mode_row = tk.Frame(body, bg=PANEL_BG)
        mode_row.pack(fill=tk.X, pady=(5, 0))
        for i in range(2):
            mode_row.columnconfigure(i, weight=1)
        self.layout_buttons = {}
        for col, (mode, label) in enumerate((('simple', '简易版'), ('traditional', '原版'))):
            b = tk.Button(mode_row, text=label, font=('Arial', 10, 'bold'),
                          command=lambda m=mode: self.switch_bet_layout(m),
                          relief=tk.RAISED, bd=1)
            b.grid(row=0, column=col, padx=3, sticky='ew', ipady=1)
            self.layout_buttons[mode] = b

        # Caribbean Stud-style action card: one horizontal row of three buttons.
        action_card = tk.Frame(panel, bg=PANEL_BG, bd=1, relief=tk.SOLID, height=88)
        action_card.pack(fill=tk.X, pady=3, padx=(0, 1))
        action_card.pack_propagate(False)
        header = tk.Frame(action_card, bg=HEADER_BG, height=28)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text='操作', font=('Arial', 13, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(expand=True)
        body = tk.Frame(action_card, bg=PANEL_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=7, pady=6)
        self.action_frame = tk.Frame(body, bg=PANEL_BG)
        self.action_frame.pack(fill=tk.BOTH, expand=True)

        # Historical result ratio card with selectable newest-record window.
        ratio_card = card('历史开出比例', 12)
        ratio_body = tk.Frame(ratio_card, bg=PANEL_BG)
        ratio_body.pack(fill=tk.X, padx=10, pady=4)

        history_button_row = tk.Frame(ratio_body, bg=PANEL_BG)
        history_button_row.pack(fill=tk.X, pady=(0, 4))
        self.history_ratio_buttons = {}
        for col, limit in enumerate((50, 100, 250, 500, 1000)):
            history_button_row.columnconfigure(col, weight=1)
            button = tk.Button(
                history_button_row, text=str(limit),
                command=lambda n=limit: self.set_history_ratio_limit(n),
                font=('Arial', 9, 'bold'),
                bg='#E6E0D3', fg=TITLE_FG,
                activebackground='#EEE8DC', activeforeground=TITLE_FG,
                relief=tk.RAISED, bd=1, cursor='hand2',
            )
            button.grid(row=0, column=col, sticky='ew', padx=2, ipady=1)
            self.history_ratio_buttons[limit] = button

        self.ratio_canvas = tk.Canvas(
            ratio_body, width=360, height=132,
            bg=PANEL_BG, highlightthickness=0,
        )
        self.ratio_canvas.pack(anchor='center')
        self._update_history_ratio_buttons()

        # The requested panel order places history statistics where the action
        # card used to be, with the action card immediately below it.
        ratio_card.pack_configure(before=action_card)

        summary = card('下注摘要', 12)
        body = tk.Frame(summary, bg=PANEL_BG)
        body.pack(fill=tk.X, padx=11, pady=5)
        self.current_bet_label = tk.Label(body, text='本局下注: $0.00', font=('Arial', 12, 'bold'),
                                          bg=PANEL_BG, fg='black')
        self.current_bet_label.pack(anchor='w')
        row = tk.Frame(body, bg=PANEL_BG)
        row.pack(fill=tk.X, pady=(2, 0))
        self.last_win_label = tk.Label(row, text='上局获胜: $0', font=('Arial', 12, 'bold'),
                                       bg=PANEL_BG, fg='black')
        self.last_win_label.pack(side=tk.LEFT)
        tk.Button(row, text='ℹ️', command=self.show_detailed_rules,
                  bg='#4B8BBE', fg='white', font=('Arial', 10, 'bold'), width=3, relief=tk.FLAT).pack(side=tk.RIGHT)

        self.selected_chip_label = None
        self.update_idletasks()
        self._refresh_chip_widget_centers()
        self._update_ratio_bar()

    def _groups_placed_to_right(self):
        fx0, _fy0, fx1, _fy1 = self.BEAD_FIELD
        field_mid_x = (fx0 + fx1) / 2.0
        return self.bowl_center[0] <= field_mid_x

    def _start_next_count_group(self):
        if self._closing or self.stage != 'counting':
            return

        remaining = list(self.count_order[self.count_removed:])
        if len(remaining) <= 4:
            self.result_number = len(remaining) if remaining else 4
            self.final_line_indices = list(remaining)
            self.final_line_progress = 0.0
            self._count_stick_entry_pose = getattr(self, '_count_stick_last_pose', None)
            self._animate_final_line(0)
            return

        rightward_rack = self._groups_placed_to_right()
        cx, cy = self.bowl_center

        def seed_key(i):
            x, y = self.bead_positions[i]
            radial = (x - cx) ** 2 + (y - cy) ** 2
            if rightward_rack:
                return (x, radial, -abs(y - cy))
            return (-x, radial, -abs(y - cy))

        seed = max(remaining, key=seed_key)
        sx, sy = self.bead_positions[seed]

        # Grow the quartet step-by-step outward from the side seed.
        def neighbour_key(i):
            x, y = self.bead_positions[i]
            dist2 = (x - sx) ** 2 + (y - sy) ** 2
            side_progress = -(x - sx) if rightward_rack else (x - sx)
            return (dist2, side_progress, abs(y - sy))

        neighbours = sorted((i for i in remaining if i != seed), key=neighbour_key)[:3]
        group = [seed] + neighbours

        prefix = list(self.count_order[:self.count_removed])
        selected = set(group)
        tail = [i for i in remaining if i not in selected]
        self.count_order = prefix + group + tail

        self.active_count_group = list(group)
        self.active_count_progress = 0.0
        self._count_stick_entry_pose = getattr(self, '_count_stick_last_pose', None)
        self._animate_count_group(0)

    def redraw_counter_zone(self):
        c = self.canvas
        c.delete('counter_dynamic')
        fx0, fy0, fx1, fy1 = self.BEAD_FIELD
        cx, cy = self.bowl_center

        if self.stage == 'preparing':
            self._draw_bead_indices(range(len(self.bead_positions)))

        elif self.stage == 'covering':
            self._draw_bead_indices(range(len(self.bead_positions)))
            start_y = fy0 - 70
            bowl_y = start_y + (cy - start_y) * float(self.bowl_cover_progress)
            self._draw_bowl(cx, bowl_y)

        elif self.stage == 'shifting':
            self._draw_bead_indices(range(len(self.bead_positions)))
            self._draw_bowl(cx, cy)

        elif self.stage == 'betting':
            moving = set(getattr(self, 'outer_take_batch', []) or [])
            moved_set = set(self.outside_indices[:self.outer_removed])
            for idx in self.outside_indices:
                if idx in moved_set or idx in moving:
                    continue
                x, y = self.bead_positions[idx]
                self._draw_bead_at(x, y)
            p = float(getattr(self, 'outer_take_progress', 0.0))
            for idx in moving:
                x, y = self._outer_sweep_position(idx, p)
                self._draw_bead_at(x, y)
            self._draw_bowl(cx, cy)
            if moving and p < 1.0:
                self._draw_sweep_bar_avoiding_bowl(p)

        elif self.stage == 'opening':
            self._draw_bead_indices(self.inside_indices)
            bowl_x = cx + self.bowl_offset
            bowl_y = cy - self.bowl_offset * 0.35
            self._draw_bowl(bowl_x, bowl_y)

        elif self.stage == 'counting':
            for group_index, group in enumerate(self.counted_groups):
                for x, y in self._group_targets(group_index, len(group)):
                    self._draw_bead_at(x, y)

            active = list(getattr(self, 'active_count_group', []) or [])
            final_set = set(self.final_line_indices or [])
            remaining_start = self.count_removed + len(active)
            for idx in self.count_order[remaining_start:]:
                if idx in final_set:
                    continue
                x, y = self.bead_positions[idx]
                self._draw_bead_at(x, y)

            if active:
                bead_positions, stick = self._active_group_visuals(active, float(self.active_count_progress))
                for x, y in bead_positions:
                    self._draw_bead_at(x, y)
                self._draw_bamboo_stick(stick[0], stick[1])

            if self.final_line_indices:
                bead_positions, stick = self._final_group_visuals(
                    self.final_line_indices, float(self.final_line_progress))
                for x, y in bead_positions:
                    self._draw_bead_at(x, y, final=(self.final_line_progress >= 0.999))
                if stick is not None:
                    self._draw_bamboo_stick(stick[0], stick[1])
            elif not getattr(self, 'active_count_group', None):
                pose = getattr(self, '_count_stick_last_pose', None)
                if pose is not None:
                    self._draw_bamboo_stick(pose[0], pose[1])

        elif self.stage in ('settling', 'settled'):
            for group_index, group in enumerate(self.counted_groups):
                for x, y in self._group_targets(group_index, len(group)):
                    self._draw_bead_at(x, y)
            final_indices = self.final_line_indices or self.count_order[-int(self.result_number or 0):]
            bead_positions, _stick = self._final_group_visuals(final_indices, 1.0)
            for x, y in bead_positions:
                self._draw_bead_at(x, y, final=True)

            field_mid_x = (fx0 + fx1) / 2.0
            field_mid_y = (fy0 + fy1) / 2.0
            x_shift = 0.25 * (fx1 - fx0)
            if self._groups_placed_to_right():
                badge_x = field_mid_x - x_shift
            else:
                badge_x = field_mid_x + x_shift
            badge_y = field_mid_y
            c.create_oval(badge_x - 31, badge_y - 31, badge_x + 31, badge_y + 31,
                          fill='#d8b46a', outline='#ffe494', width=3, tags='counter_dynamic')
            c.create_text(badge_x, badge_y - 11, text='结果', font=('Arial', 8, 'bold'),
                          fill='#2a1b08', tags='counter_dynamic')
            c.create_text(badge_x, badge_y + 13, text=str(self.result_number),
                          font=('Arial', 23, 'bold'), fill='#2a1b08', tags='counter_dynamic')

        self._draw_history_strip()

    def _render_action_buttons(self):
        for w in self.action_frame.winfo_children():
            w.destroy()

        if self.stage == 'settled':
            b = tk.Button(self.action_frame, text='再来一局', command=self.new_round,
                          font=('Arial', 12, 'bold'), bg='#FFC107', fg='black',
                          activebackground='#FFC107', relief=tk.RAISED, bd=2, cursor='hand2')
            b.pack(expand=True, fill=tk.X, padx=55, pady=1)
            return

        for col in range(3):
            self.action_frame.columnconfigure(col, weight=1)
        self.action_frame.rowconfigure(0, weight=1)

        if self.stage == 'betting':
            total = self.bet_state.total_at_risk()
            outside_done = self.outer_removed >= len(self.outside_indices)
            states = (
                ('清除', self.clear_bets, '#F44336', 'white', total > 0),
                ('重复上局下注', self.repeat_last_bets, '#FFC107', 'black', bool(self.last_round_bets)),
                ('开摊', self.start_round, '#4CAF50', 'white', outside_done),
            )
        else:
            states = (
                ('清除', self.clear_bets, '#F44336', 'white', False),
                ('重复上局下注', self.repeat_last_bets, '#FFC107', 'black', False),
                ('开摊', self.start_round, '#4CAF50', 'white', False),
            )

        for col, (label, command, bg, fg, enabled) in enumerate(states):
            b = tk.Button(
                self.action_frame, text=label, command=command,
                font=('Arial', 12, 'bold'), bg=bg, fg=fg,
                activebackground=bg, activeforeground=fg,
                relief=tk.RAISED, bd=2, cursor='hand2',
                state=tk.NORMAL if enabled else tk.DISABLED,
            )
            b.grid(row=0, column=col, sticky='nsew', padx=4, pady=2, ipady=9)

    def _update_ratio_bar(self):
        """Draw statistics for the selected newest-history window.

        Rows:
          1) 单 / 双   -> 单 = 1+3, 双 = 2+4
          2) 小 / 大   -> 小 = 1+2, 大 = 3+4
          3) 1/2/3/4 labels above the individual result-proportion bar

        The four coloured result segments show percentage text only. Their
        1/2/3/4 identities are shown in a separate legend row above the bar.
        """
        canvas = getattr(self, 'ratio_canvas', None)
        if canvas is None:
            return

        canvas.delete('all')
        counts, total = self._history_counts()
        perc = self._integer_percentages_total_100(counts, total)

        x0, x1 = 4.0, 356.0
        full_width = x1 - x0
        result_colors = {
            1: '#b73835',
            2: '#2f7f4b',
            3: '#315c9c',
            4: '#343434',
        }

        def pair_percent(first_count, second_count):
            if total <= 0:
                return 0, 0
            first_pct = int(round(first_count * 100.0 / total))
            first_pct = max(0, min(100, first_pct))
            return first_pct, 100 - first_pct

        def draw_pair_bar(y0, y1, left_label, right_label,
                          left_count, right_count, left_color, right_color):
            if total > 0:
                left_width = full_width * left_count / float(total)
            else:
                left_width = full_width / 2.0
            right_width = full_width - left_width
            left_pct, right_pct = pair_percent(left_count, right_count)

            canvas.create_rectangle(
                x0, y0, x1, y1,
                fill='#efe5cf', outline='#6f6254', width=1,
            )
            if left_width > 0.5:
                canvas.create_rectangle(
                    x0, y0, x0 + left_width, y1,
                    fill=left_color, outline='#f4ead8', width=1,
                )
            if right_width > 0.5:
                canvas.create_rectangle(
                    x0 + left_width, y0, x1, y1,
                    fill=right_color, outline='#f4ead8', width=1,
                )

            # Put each percentage label at the geometric centre of its actual
            # proportional segment rather than at fixed quarter points.
            canvas.create_text(
                x0 + left_width / 2.0, (y0 + y1) / 2.0,
                text=f'{left_label}({left_pct}%)',
                font=('Arial', 9, 'bold'), fill='white',
            )
            canvas.create_text(
                x0 + left_width + right_width / 2.0, (y0 + y1) / 2.0,
                text=f'{right_label}({right_pct}%)',
                font=('Arial', 9, 'bold'), fill='white',
            )

        # 单 / 双
        odd_count = counts[1] + counts[3]
        even_count = counts[2] + counts[4]
        draw_pair_bar(
            2.0, 24.0,
            '单', '双', odd_count, even_count,
            '#7b394f', '#315c78',
        )

        # 小 / 大
        small_count = counts[1] + counts[2]
        big_count = counts[3] + counts[4]
        draw_pair_bar(
            31.0, 53.0,
            '小', '大', small_count, big_count,
            '#8b6a2d', '#6d3b62',
        )

        # 1 / 2 / 3 / 4 proportional segments.
        # Leave 10px after the 小/大 row before the separate number legend.
        legend_y = 69.0
        bar_y0, bar_y1 = 80.0, 104.0
        count_y = 119.0

        if total <= 0:
            widths = {n: full_width / 4.0 for n in (1, 2, 3, 4)}
        else:
            widths = {
                n: full_width * counts[n] / float(total)
                for n in (1, 2, 3, 4)
            }

        # Use the REAL proportional segment centres for all three rows:
        #   number legend -> percentage text -> round count.
        # This keeps 1 / 2 / 3 / 4 vertically aligned with the percentage
        # displayed inside its own coloured segment.
        cursor = x0
        segment_bounds = {}
        segment_centres = {}
        for n in (1, 2, 3, 4):
            width = widths[n]
            nx = cursor + width
            segment_bounds[n] = (cursor, nx)
            segment_centres[n] = (cursor + nx) / 2.0
            cursor = nx

        # Separate number legend directly above each proportional segment.
        for n in (1, 2, 3, 4):
            canvas.create_text(
                segment_centres[n], legend_y,
                text=str(n), font=('Arial', 9, 'bold'),
                fill=result_colors[n],
            )

        canvas.create_rectangle(
            x0, bar_y0, x1, bar_y1,
            fill='#efe5cf', outline='#6f6254', width=1,
        )

        for n in (1, 2, 3, 4):
            sx0, sx1 = segment_bounds[n]
            width = sx1 - sx0
            if width > 0.5:
                canvas.create_rectangle(
                    sx0, bar_y0, sx1, bar_y1,
                    fill=result_colors[n], outline='#f4ead8', width=1,
                )
            # Percentage only inside the proportional segment. Very small/zero
            # segments cannot physically contain text, so their percentage is
            # omitted rather than overlapping a neighbouring segment.
            if width >= 28.0:
                canvas.create_text(
                    segment_centres[n], (bar_y0 + bar_y1) / 2.0,
                    text=f'{perc[n]}%',
                    font=('Arial', 9, 'bold'), fill='white',
                )
            canvas.create_text(
                segment_centres[n], count_y,
                text=f'{counts[n]}局',
                font=('Arial', 9, 'bold'), fill=result_colors[n],
            )


# ============================================================
# Entry point — embedded or standalone
# ============================================================
def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None, auto_data=False):
    """Create the Fan Tan table.

    auto_data=False -> normal manual play.
    auto_data=True  -> automatically performs the two legal Enter actions each round.
    """
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        return ClassicFanTanGUI(
            parent, balance=actual_balance, user=actual_user,
            on_back=on_back, on_balance_change=on_balance_change,
            auto_data=auto_data,
        )

    root = tk.Tk()
    root.title('经典番摊')
    root.geometry(WINDOW_GEOMETRY)
    root.resizable(False, False)
    page = ClassicFanTanGUI(
        root, balance=actual_balance, user=actual_user, auto_data=auto_data,
    )
    page.pack(fill='both', expand=True)
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page


if __name__ == '__main__':
    main(auto_data=False)
