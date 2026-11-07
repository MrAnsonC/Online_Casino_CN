"""Plinko: full-width 15-slot board with real-time physical collisions.

Retains the original chip betting, debit-per-ball, concurrent launches and
slot-based payouts. Outcomes are assigned ONLY when a ball physically rests
inside a bin. Seven motor-driven pinwheels run continuously, arranged 2-3-2.
Pegs, complete rotating blades, walls, dividers and other balls all collide.

Three fixed payout tables target 95% RTP using 120,000 sampled physical
landings from this seven-rotor layout. This is a statistical calibration,
not an exact theoretical guarantee for arbitrary launch timing or concurrency.
There is no payout feedback, outcome steering or precomputed ball trajectory.

The sidebar history lies below active balls and above rules, with 24
chevron cells showing actual historical multipliers across three rows.
Older slot-only logs are migrated with the previous payout tables. Account
encryption, embedding and 15-slot disk logging are preserved.
"""

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
import math
import os
import random
import sys
import time
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


VERSION = "Plinko-15Slots-7Rotors-Calibrated-R5"


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

    BOARD = "#AFC4B1"
    BOARD_DARK = "#839E86"
    BOARD_EDGE = "#718C75"
    PEG = "#EEE8DE"
    PEG_BORDER = "#8C857B"
    SLOT = "#D5CEC3"
    SLOT_EDGE = "#9C9388"
    SLOT_GOOD = "#A9C4A5"
    SLOT_NEUTRAL = "#D8C994"
    SLOT_BAD = "#D1A09B"
    BALL_OUTLINE = "#F7F3EC"

    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


# (amount, chip_colour, label). Text colour is auto-derived from luminance.
CHIP_CONFIGS = (
    (5,    "#ba3438", "5"),
    (25,   "#42a95b", "25"),
    (100,  "#202020", "100"),
    (500,  "#70439a", "500"),
    (1000, "#d0a347", "1K"),
)

RISK_CONFIGS = (
    ("简单", "1", "easy"),
    ("中等", "2", "medium"),
    ("困难", "3", "hard"),
)

SLOT_COUNT = 15
# Previous paid multipliers are retained only to migrate existing slot-only logs.
LEGACY_PAYOUT_CENTS = {
    "1": (574, 409, 227, 170, 125, 113, 80, 57, 80, 113, 125, 170, 227, 409, 574),
    "2": (3679, 1685, 648, 389, 168, 90, 53, 25, 53, 90, 168, 389, 648, 1685, 3679),
    "3": (42834, 5612, 1804, 501, 190, 30, 20, 0, 20, 30, 190, 501, 1804, 5612, 42834),
}
# Seven-rotor calibration: 60,000 independent balls + 60,000 balls launched
# in groups of 15 at 0.2-second intervals; initial rotor phase uniform over
# a full revolution, x uniform in centre +/-5, vx uniform in [-24, 24].
# Fit symmetrical cent-precision tables against their pooled slot frequencies.
# Each table returns exactly 95% on that calibration sample. Actual long-run
# RTP is an estimate, not a guarantee: release timing and ball collisions can
# change the distribution. No paths/results are selected to enforce an RTP.
RTP_CALIBRATION = {
    "target": 0.95,
    "sample_balls": 120000,
    "board_size": (716, 570),
    "rotor_layout": "2-3-2",
    "single_seed": 20260929,
    "multi_seed": 20260930,
    "counts": (844, 1537, 3359, 4807, 5197, 13588, 16582, 19080,
               19444, 18541, 6133, 4916, 3512, 1613, 847),
    "single_counts": (422, 798, 1665, 2444, 2636, 6808, 8198, 9551,
                      9663, 9160, 3099, 2531, 1784, 809, 432),
    "multi_counts": (422, 739, 1694, 2363, 2561, 6780, 8384, 9529,
                     9781, 9381, 3034, 2385, 1728, 804, 415),
    # Nominal pooled Monte Carlo standard errors in RTP fraction units.
    # Multi-ball samples are clustered; these are descriptive estimates,
    # not confidence guarantees or independent holdout validation.
    "nominal_standard_error": {"1": 0.001923, "2": 0.006156, "3": 0.015081},
}
PAYOUT_CENTS = {
    '1': (453, 324, 179, 133, 99, 89, 63, 44, 63, 89, 99, 133, 179, 324, 453),
    '2': (1541, 714, 277, 166, 71, 38, 22, 11, 22, 38, 71, 166, 277, 714, 1541),
    '3': (4387, 568, 188, 52, 20, 3, 2, 0, 2, 3, 20, 52, 188, 568, 4387),
}
PAYOUTS = {mode: tuple(value / 100 for value in values)
           for mode, values in PAYOUT_CENTS.items()}
if any(len(values) != SLOT_COUNT for values in PAYOUT_CENTS.values()):
    raise ValueError("Every risk mode must define exactly 15 payouts")


def format_multiplier(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".") + "×"


def _format_history_value(value: float) -> str:
    """Compact multiplier text that fits in the narrow history cell."""
    if value >= 100:
        return f"{value:.0f}"
    if value >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _pick_text_colour(hex_colour: str) -> str:
    """Return black or white depending on the background's perceived luminance."""
    try:
        r = int(hex_colour[1:3], 16)
        g = int(hex_colour[3:5], 16)
        b = int(hex_colour[5:7], 16)
    except (ValueError, IndexError):
        return "#FFFFFF"
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return "#111111" if luminance >= 140 else "#FFFFFF"


RISK_KEY = {"1": "easy", "2": "medium", "3": "hard"}
RISK_LABEL = {"1": "简单", "2": "中等", "3": "困难"}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../A_Tools/Account/saving_data.json")


def get_plinko_log_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "../A_Logs/Json/Plinko_15.json",
    )


def load_user_data() -> list:
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []


def save_user_data(users: list) -> None:
    try:
        path = get_data_file_path()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(users, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{float(new_balance):.2f}"
            save_user_data(users)
            return
    users.append({"user_name": username, "cash": f"{float(new_balance):.2f}"})
    save_user_data(users)


def _empty_landing_log() -> dict:
    return {
        "easy": [{}],
        "medium": [{}],
        "hard": [{}],
        "_paid_multipliers": {"easy": [], "medium": [], "hard": []},
    }


def _extract_mode_values(data: dict, mode: str) -> list[int]:
    """Return stored landing values in chronological order."""
    try:
        block = data.get(mode, [])
        if not isinstance(block, list) or not block or not isinstance(block[0], dict):
            return []
        record = block[0]
        pairs = []
        for key, value in record.items():
            if not isinstance(key, str) or not key.startswith("game_"):
                continue
            try:
                index = int(key.split("_", 1)[1])
                landing = int(value)
            except (ValueError, TypeError):
                continue
            if 1 <= landing <= SLOT_COUNT:
                pairs.append((index, landing))
        pairs.sort(key=lambda pair: pair[0])
        return [landing for _, landing in pairs][-20:]
    except Exception:
        return []


def load_landing_log() -> dict:
    base = _empty_landing_log()
    try:
        with open(get_plinko_log_path(), "r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            return base
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return base

    for mode in ("easy", "medium", "hard"):
        values = _extract_mode_values(raw, mode)
        base[mode] = [{
            f"game_{index:02d}": value
            for index, value in enumerate(values, start=1)
        }]
        stored = raw.get("_paid_multipliers", {})
        paid = stored.get(mode, []) if isinstance(stored, dict) else []
        valid = (isinstance(paid, list) and len(paid) == len(values) and
                 all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0
                     for v in paid))
        risk = {"easy": "1", "medium": "2", "hard": "3"}[mode]
        # Older files stored only slots; recover their original paid values
        # using the previous fixed tables, not the newly calibrated tables.
        base["_paid_multipliers"][mode] = (
            list(paid) if valid else
            [LEGACY_PAYOUT_CENTS[risk][slot-1] / 100 for slot in values]
        )
    return base


def record_landing(mode: str, slot: int, multiplier: Optional[float] = None) -> None:
    """Append one landing slot and keep the newest 24 for the selected mode."""
    if mode not in ("easy", "medium", "hard"):
        return
    slot = int(slot)
    if not 1 <= slot <= SLOT_COUNT:
        return

    data = load_landing_log()
    risk = {"easy": "1", "medium": "2", "hard": "3"}[mode]
    paid = float(PAYOUTS[risk][slot-1] if multiplier is None else multiplier)
    if not math.isfinite(paid) or paid < 0:
        return
    data["_paid_multipliers"][mode] = (data["_paid_multipliers"][mode] + [paid])[-24:]
    values = _extract_mode_values(data, mode)
    values.append(slot)
    values = values[-24:]

    data[mode] = [{
        f"game_{index:02d}": value
        for index, value in enumerate(values, start=1)
    }]

    # Normalize the untouched modes too, so the file always has all 3 groups.
    for other in ("easy", "medium", "hard"):
        if other == mode:
            continue
        other_values = _extract_mode_values(data, other)
        data[other] = [{
            f"game_{index:02d}": value
            for index, value in enumerate(other_values, start=1)
        }]

    path = get_plinko_log_path()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


class PlinkoPhysics:
    """Real-time circle/capsule collisions in the same pixel space as the canvas.

    No target slot, route, payout-dependent force or simulated trajectory cache.
    All balls and seven motor-driven rotors share one fixed-step simulation clock.
    """
    DT = 1.0 / 240.0
    GRAVITY = 660.0
    BALL_RADIUS = 5.5
    PEG_RADIUS = 3.5
    ROTOR_RADIUS = 3.0
    ROTOR_LENGTH = 24.0
    ROTOR_SPEED = 2.6

    PEG_ROW_COUNT = 13

    def __init__(self, width: float, height: float):
        self.left, self.right = 5.0, width - 5.0
        self.top, self.bottom = 5.0, height - 5.0
        self.floor = self.bottom - 34.0
        self.divider_top = self.floor - 66.0
        self.slot_width = (self.right - self.left) / SLOT_COUNT
        self.centre = (self.left + self.right) / 2
        self.time = 0.0
        # 2-3-2 layout. The two outermost middle-row rotors spin opposite to
        # their previous direction (left rotor now clockwise, right rotor now
        # counter-clockwise) as requested.
        self.rotors = tuple((self.left + (self.right-self.left)*fx,
                             self.top + (self.floor-self.top)*fy, direction)
                            for fx, fy, direction in
                            ((.33, .30, 1), (.67, .30, -1),
                             (.20, .50, 1), (.50, .50, 1), (.80, .50, -1),
                             (.34, .71, 1), (.66, .71, -1)))
        self.funnel = ((self.centre-24, self.top+12, self.left, self.top+80),
                       (self.centre+24, self.top+12, self.right, self.top+80))
        self.peg_rows = []
        rows = self.PEG_ROW_COUNT
        base_spacing = (self.right - self.left) / 23
        for row in range(rows):
            y = self.top + 99 + row * (self.divider_top - self.top - 143) / (rows - 1)
            if row == rows - 1:
                # Bottom row: shortened central span so the lowest pegs sit
                # higher than the side pegs, leaving more open space below.
                count = 15
                start = 4.5
            elif row % 2 == 0:
                count = 23
                start = 0.5
            else:
                count = 22
                start = 1.0
            xs = [self.left + (j + start) * base_spacing for j in range(count)]
            clearance = self.ROTOR_LENGTH + self.ROTOR_RADIUS + self.PEG_RADIUS + 5
            self.peg_rows.append([(x, y) for x in xs
                                  if all(math.hypot(x-rx, y-ry) > clearance
                                         for rx, ry, _ in self.rotors)])
        self.pegs = [p for row in self.peg_rows for p in row]

    def rotor_segments(self):
        for cx, cy, direction in self.rotors:
            omega = direction * self.ROTOR_SPEED
            for blade in range(4):
                angle = omega * self.time + blade * math.pi / 2
                yield (cx, cy, cx+self.ROTOR_LENGTH*math.cos(angle),
                       cy+self.ROTOR_LENGTH*math.sin(angle), omega)

    @staticmethod
    def _contact(ball, nx, ny, penetration, restitution=.55,
                 friction=.10, surface_vx=0.0, surface_vy=0.0):
        ball['x'] += nx * max(0.0, penetration)
        ball['y'] += ny * max(0.0, penetration)
        rvx, rvy = ball['vx']-surface_vx, ball['vy']-surface_vy
        normal_speed = rvx*nx + rvy*ny
        if normal_speed >= 0:
            return
        # Remove restitution at tiny impacts to permit physical resting contact.
        bounce = restitution if normal_speed < -12.0 else 0.0
        impulse = -(1+bounce)*normal_speed
        # A solid disk rolls instead of being artificially glued to a peg by
        # translational friction. Inertia I = m*r*r/2, inverse contact mass = 3.
        radius = PlinkoPhysics.BALL_RADIUS
        slip = -rvx*ny + rvy*nx - ball.get('spin', 0.0)*radius
        tangent_impulse = max(-friction*impulse, min(friction*impulse, -slip/3.0))
        ball['vx'] += impulse*nx - tangent_impulse*ny
        ball['vy'] += impulse*ny + tangent_impulse*nx
        ball['spin'] = ball.get('spin', 0.0) - 2*tangent_impulse/radius

    def _capsule(self, ball, ax, ay, bx, by, radius, *, omega=0.0,
                 restitution=.55):
        dx, dy = bx-ax, by-ay
        length2 = dx*dx + dy*dy
        u = max(0.0, min(1.0, ((ball['x']-ax)*dx+(ball['y']-ay)*dy)/length2)) if length2 else 0.0
        px, py = ax+u*dx, ay+u*dy
        nx, ny = ball['x']-px, ball['y']-py
        distance = math.hypot(nx, ny)
        separation = self.BALL_RADIUS+radius
        if distance >= separation:
            return
        if distance > 1e-9:
            nx, ny = nx/distance, ny/distance
        else:
            length = math.sqrt(length2) or 1.0
            nx, ny = (-dy/length, dx/length) if length2 else (0.0, -1.0)
        self._contact(ball, nx, ny, separation-distance, restitution,
                      surface_vx=-omega*(py-ay), surface_vy=omega*(px-ax))

    def _terrain(self, ball, segments):
        r = self.BALL_RADIUS
        if ball['x'] < self.left+r:
            self._contact(ball, 1, 0, self.left+r-ball['x'])
        if ball['x'] > self.right-r:
            self._contact(ball, -1, 0, ball['x']-(self.right-r))
        if ball['y'] < self.top+r:
            self._contact(ball, 0, 1, self.top+r-ball['y'])
        if ball['y'] > self.floor-r:
            self._contact(ball, 0, -1, ball['y']-(self.floor-r), .20, .25)
        if ball['y'] < self.top+90:
            for segment in self.funnel:
                self._capsule(ball, *segment, 1.5, restitution=.4)
        separation = r+self.PEG_RADIUS
        for row in self.peg_rows:
            if not row or abs(ball['y']-row[0][1]) >= separation:
                continue
            for px, py in row:
                dx, dy = ball['x']-px, ball['y']-py
                if abs(dx) >= separation:
                    continue
                distance = math.hypot(dx, dy)
                if distance < separation:
                    nx, ny = (dx/distance, dy/distance) if distance > 1e-9 else (0., -1.)
                    self._contact(ball, nx, ny, separation-distance, .62)
        reach = self.ROTOR_LENGTH+self.ROTOR_RADIUS+r
        for cx, cy, px, py, omega in segments:
            if abs(ball['x']-cx) < reach and abs(ball['y']-cy) < reach:
                self._capsule(ball, cx, cy, px, py, self.ROTOR_RADIUS, omega=omega)
        if ball['y'] > self.divider_top-r-1:
            # Only adjacent dividers can touch a ball, all use the drawn geometry.
            cell = int((ball['x']-self.left)/self.slot_width)
            for wall in (cell, cell+1):
                if 1 <= wall < SLOT_COUNT:
                    x = self.left+wall*self.slot_width
                    self._capsule(ball, x, self.divider_top, x, self.floor, 1.0, restitution=.35)

    def _ball_pairs(self, balls):
        diameter = 2*self.BALL_RADIUS
        for i, a in enumerate(balls):
            for b in balls[i+1:]:
                dx, dy = b['x']-a['x'], b['y']-a['y']
                if abs(dx) >= diameter or abs(dy) >= diameter:
                    continue
                distance = math.hypot(dx, dy)
                if distance >= diameter:
                    continue
                nx, ny = (dx/distance, dy/distance) if distance > 1e-9 else (1., 0.)
                correction = (diameter-distance)/2
                a['x'] -= nx*correction; a['y'] -= ny*correction
                b['x'] += nx*correction; b['y'] += ny*correction
                relative = (b['vx']-a['vx'])*nx+(b['vy']-a['vy'])*ny
                if relative < 0:
                    impulse = -(1+.65)*relative/2
                    a['vx'] -= impulse*nx; a['vy'] -= impulse*ny
                    b['vx'] += impulse*nx; b['vy'] += impulse*ny

    def step(self, balls, dt=None):
        dt = self.DT if dt is None else dt
        self.time += dt
        live = [ball for ball in balls if not ball.get('finished')]
        if not live:
            return
        segments = tuple(self.rotor_segments())
        for ball in live:
            drag = 1/(1+.0007*math.hypot(ball['vx'], ball['vy'])*dt)
            ball['vx'] *= drag; ball['vy'] *= drag
            ball['x'] += ball['vx']*dt
            ball['y'] += ball['vy']*dt+.5*self.GRAVITY*dt*dt
            ball['vy'] += self.GRAVITY*dt
        for _ in range(3):
            self._ball_pairs(live)
            for ball in live:
                self._terrain(ball, segments)
        for ball in live:
            grounded = ball['y'] >= self.floor-self.BALL_RADIUS-1e-5
            if grounded:
                ball['vx'] *= max(0., 1-12*dt)
                ball['spin'] = ball.get('spin', 0.)*max(0., 1-12*dt)
            resting = grounded and abs(ball['vy']) < 1.0 and abs(ball['vx']) < 2.0
            ball['rest_time'] = ball.get('rest_time', 0.)+dt if resting else 0.
            if ball['rest_time'] >= .12:
                # The ONLY place an outcome is assigned: the actual resting x.
                ball['slot'] = min(SLOT_COUNT, max(1, int((ball['x']-self.left)/self.slot_width)+1))
                ball['finished'] = True


# ---------------------------------------------------------------------------
# Reusable Chicken-style controls
# ---------------------------------------------------------------------------

class ModernButton(tk.Button):
    def __init__(
        self,
        master,
        *,
        text: str,
        command: Optional[Callable[[], None]] = None,
        background: str = Theme.PANEL_HOVER,
        hover_background: str = Theme.BORDER,
        foreground: str = Theme.TEXT,
        font_size: int = 12,
        bold: bool = False,
        **kwargs,
    ) -> None:
        self.normal_background = background
        self.hover_background = hover_background
        self.normal_foreground = foreground
        super().__init__(
            master,
            text=text,
            command=command,
            bg=background,
            fg=foreground,
            activebackground=hover_background,
            activeforeground=foreground,
            disabledforeground=Theme.TEXT_DIM,
            font=(Theme.FONT_CJK, font_size, "bold" if bold else "normal"),
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self.bind("<Enter>", self._on_enter, add="+")
        self.bind("<Leave>", self._on_leave, add="+")

    def _on_enter(self, _event) -> None:
        if str(self.cget("state")) != tk.DISABLED:
            super().configure(bg=self.hover_background)

    def _on_leave(self, _event) -> None:
        super().configure(bg=self.normal_background)

    def set_colors(
        self,
        background: str,
        hover_background: Optional[str] = None,
        foreground: Optional[str] = None,
    ) -> None:
        self.normal_background = background
        self.hover_background = hover_background or background
        if foreground is not None:
            self.normal_foreground = foreground
        super().configure(
            bg=self.normal_background,
            fg=self.normal_foreground,
            activebackground=self.hover_background,
            activeforeground=self.normal_foreground,
        )


class ChipButton(tk.Canvas):
    def __init__(
        self,
        master,
        *,
        label: str,
        amount: str,
        chip_color: str,
        command: Callable[[str], None],
        width: int = 57,
        height: int = 50,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=Theme.PANEL,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.label = label
        self.amount = amount
        self.chip_color = chip_color
        self.text_color = _pick_text_colour(chip_color)
        self.command = command
        self.control_width = width
        self.control_height = height
        self._state = tk.NORMAL
        self._hovered = False
        self._pressed = False
        self._flash = False
        self._flash_job = None
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Key-space>", self._on_keyboard_activate)
        self.bind("<Return>", self._on_keyboard_activate)
        self.draw()

    @staticmethod
    def _shade(hex_color: str, factor: float) -> str:
        if not hex_color.startswith("#") or len(hex_color) != 7:
            return "#4A4A4A"
        rgb = [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
        rgb = [max(0, min(255, round(channel * factor))) for channel in rgb]
        return "#%02x%02x%02x" % tuple(rgb)

    def draw(self) -> None:
        self.delete("all")
        offset_y = 3 if self._pressed else 0
        disabled = self._state == tk.DISABLED
        outer = self._shade(self.chip_color, 0.68)
        inner = self._shade(self.chip_color, 0.86)
        outline = Theme.ACCENT if self._flash else (Theme.TEXT if self._hovered else outer)
        outline_width = 3 if (self._flash or self._hovered) else 2

        self.create_oval(6, 7, self.control_width - 5, self.control_height - 1,
                         fill="#8E877E", outline="")
        self.create_oval(5, 3 + offset_y, self.control_width - 6,
                         self.control_height - 5 + offset_y,
                         fill=outer, outline=outline, width=outline_width)
        self.create_oval(9, 7 + offset_y, self.control_width - 10,
                         self.control_height - 9 + offset_y,
                         fill=self.chip_color, outline=inner, width=2)
        self.create_oval(14, 12 + offset_y, self.control_width - 15,
                         self.control_height - 14 + offset_y,
                         fill=self.chip_color, outline=outer, width=1)

        cx = self.control_width / 2
        cy = (self.control_height - 2) / 2 + offset_y
        inserts = (
            (cx - 3, 4 + offset_y, cx + 3, 10 + offset_y),
            (cx - 3, self.control_height - 12 + offset_y, cx + 3,
             self.control_height - 6 + offset_y),
            (6, cy - 3, 12, cy + 3),
            (self.control_width - 13, cy - 3, self.control_width - 7, cy + 3),
        )
        for x1, y1, x2, y2 in inserts:
            self.create_rectangle(x1, y1, x2, y2, fill=self.text_color, outline="")

        self.create_text(
            cx, cy, text=self.label, fill=self.text_color,
            font=(Theme.FONT, 11 if len(self.label) <= 3 else 9, "bold")
        )
        if disabled:
            self.create_oval(
                5, 3 + offset_y, self.control_width - 6,
                self.control_height - 5 + offset_y,
                fill="#C9C2B8", outline=Theme.BORDER_SOFT,
                width=1, stipple="gray50",
            )

    def _on_enter(self, _event) -> None:
        if self._state != tk.DISABLED:
            self._hovered = True
            self.draw()

    def _on_leave(self, _event) -> None:
        self._hovered = False
        self._pressed = False
        self.draw()

    def _on_press(self, _event) -> None:
        if self._state != tk.DISABLED:
            self.focus_set()
            self._pressed = True
            self.draw()

    def _on_release(self, event) -> None:
        if self._state == tk.DISABLED:
            return
        was_pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.control_width and 0 <= event.y < self.control_height
        if was_pressed and inside:
            self._activate()
        else:
            self.draw()

    def _on_keyboard_activate(self, _event) -> str:
        if self._state != tk.DISABLED:
            self._activate()
        return "break"

    def _activate(self) -> None:
        self._flash = True
        self.draw()
        self.command(self.amount)
        if self._flash_job is not None:
            try:
                self.after_cancel(self._flash_job)
            except tk.TclError:
                pass
        self._flash_job = self.after(150, self._clear_flash)

    def _clear_flash(self) -> None:
        self._flash = False
        self._flash_job = None
        self.draw()

    def configure(self, cnf=None, **kwargs):
        state = kwargs.pop("state", None)
        if state is not None:
            self._state = state
            if state == tk.DISABLED:
                self._hovered = False
                self._pressed = False
                self._flash = False
            super().configure(cursor="" if state == tk.DISABLED else "hand2")
            self.draw()
        if cnf is not None or kwargs:
            return super().configure(cnf, **kwargs)
        return None

    config = configure


class MetricTile(tk.Frame):
    def __init__(
        self,
        master,
        label: str,
        variable: tk.StringVar,
        accent: str,
        *,
        width: int,
        height: int,
    ) -> None:
        super().__init__(
            master,
            width=width,
            height=height,
            bg=Theme.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        self.pack_propagate(False)
        tk.Label(
            self, text=label, bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9), anchor=tk.W,
        ).place(x=12, y=8, width=width - 24, height=18)
        tk.Label(
            self, textvariable=variable, bg=Theme.PANEL_ALT, fg=accent,
            font=(Theme.FONT, 15, "bold"), anchor=tk.W,
        ).place(x=12, y=29, width=width - 24, height=28)


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class PlinkoGame:
    WINDOW_WIDTH = 1150
    WINDOW_HEIGHT = 750
    SHELL_WIDTH = 1110
    SHELL_HEIGHT = 714
    HEADER_HEIGHT = 70
    BODY_TOP = 84
    BODY_HEIGHT = 630
    GAME_PANEL_WIDTH = 748
    SIDEBAR_WIDTH = 348
    PANEL_GAP = 14

    BOARD_WIDTH = 716
    BOARD_HEIGHT = 570

    HISTORY_COLS = 8
    HISTORY_ROWS = 3
    HISTORY_VISIBLE = HISTORY_COLS * HISTORY_ROWS  # 24

    def __init__(self, root, initial_balance: float, username: str):
        self.root = root
        self._configure_root()

        self.balance = float(initial_balance)
        self.username = username
        self.risk_level = "1"
        self.current_bet = 0.0
        self.last_win = 0.0
        self.balls: list[dict] = []
        self.pegs: list[tuple[float, float]] = []
        self.peg_rows: list[list[tuple[float, float]]] = []
        self.animation_running = False
        self.active_balls = 0
        self.last_result_text = "等待发射"

        self.physics = PlinkoPhysics(self.BOARD_WIDTH, self.BOARD_HEIGHT)
        self.ball_radius = self.physics.BALL_RADIUS
        self.peg_radius = self.physics.PEG_RADIUS
        self.frame_interval_ms = 16
        self._last_frame_time = time.monotonic()
        self._physics_accumulator = 0.0
        self._animation_job = None
        self._closed = False

        # History strip state: newest first, 24 values.
        self._history_values: list[Optional[float]] = [None] * self.HISTORY_VISIBLE

        self.chip_buttons: list[ChipButton] = []
        self.risk_buttons: list[ModernButton] = []

        self.balance_var = tk.StringVar()
        self.bet_var = tk.StringVar()
        self.last_win_var = tk.StringVar()
        self.active_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self.create_widgets()
        self._reload_history()
        self.update_display()
        self.root.bind("<Destroy>", self._on_destroy, add="+")
        self.animation_running = True
        self._animation_job = self.root.after(self.frame_interval_ms, self.animate_balls)

    def _configure_root(self) -> None:
        if isinstance(self.root, (tk.Tk, tk.Toplevel)):
            self.root.title("Plinko")
            self.root.geometry("1150x750+50+10")
            self.root.resizable(False, False)
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        else:
            self.root.configure(width=self.WINDOW_WIDTH, height=self.WINDOW_HEIGHT)
            try:
                self.root.pack_propagate(False)
                self.root.grid_propagate(False)
            except tk.TclError:
                pass
        self.root.configure(bg=Theme.APP_BG)

    @staticmethod
    def _card(master, *, width: int, height: int, padding: int = 12) -> tk.Frame:
        outer = tk.Frame(
            master,
            width=width,
            height=height,
            bg=Theme.PANEL,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        outer.pack_propagate(False)
        outer.grid_propagate(False)
        inner = tk.Frame(outer, bg=Theme.PANEL)
        inner.place(
            x=padding, y=padding,
            width=max(1, width - padding * 2),
            height=max(1, height - padding * 2),
        )
        outer.inner = inner
        outer.content = inner
        return outer

    @staticmethod
    def _section_title(master, text: str) -> tk.Label:
        return tk.Label(
            master,
            text=text,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 11, "bold"),
            anchor=tk.W,
        )

    def create_widgets(self) -> None:
        shell = tk.Frame(
            self.root,
            width=self.SHELL_WIDTH,
            height=self.SHELL_HEIGHT,
            bg=Theme.APP_BG,
        )
        shell.pack(padx=20, pady=18)
        shell.pack_propagate(False)

        self._build_header(shell)

        body = tk.Frame(
            shell,
            width=self.SHELL_WIDTH,
            height=self.BODY_HEIGHT,
            bg=Theme.APP_BG,
        )
        body.place(x=0, y=self.BODY_TOP, width=self.SHELL_WIDTH, height=self.BODY_HEIGHT)

        self._build_game_panel(body)
        self._build_sidebar(body)

    def _build_header(self, shell: tk.Frame) -> None:
        header = tk.Frame(
            shell,
            width=self.SHELL_WIDTH,
            height=self.HEADER_HEIGHT,
            bg=Theme.PANEL,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        header.place(x=0, y=0, width=self.SHELL_WIDTH, height=self.HEADER_HEIGHT)

        icon = tk.Canvas(header, width=48, height=48, bg=Theme.PANEL, bd=0, highlightthickness=0)
        icon.place(x=14, y=11)
        icon.create_oval(2, 2, 46, 46, fill=Theme.ACCENT_SOFT, outline=Theme.ACCENT, width=2)
        icon.create_oval(16, 10, 32, 26, fill=Theme.AMBER, outline=Theme.TEXT, width=1)
        icon.create_line(24, 27, 24, 39, fill=Theme.ACCENT, width=2)
        icon.create_line(17, 38, 31, 38, fill=Theme.ACCENT, width=2)

        tk.Label(
            header,
            text="PLINKO",
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT, 18, "bold"),
            anchor=tk.W,
        ).place(x=74, y=10, width=300, height=27)
        tk.Label(
            header,
            text="弹珠落点",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 11, "bold"),
            anchor=tk.W,
        ).place(x=74, y=39, width=240, height=20)

        balance_box = tk.Frame(
            header,
            width=206,
            height=46,
            bg=Theme.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=Theme.BORDER_SOFT,
        )
        balance_box.place(x=self.SHELL_WIDTH - 220, y=12, width=206, height=46)
        tk.Label(
            balance_box, text="账户余额",
            bg=Theme.PANEL_ALT, fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9), anchor=tk.W,
        ).place(x=12, y=4, width=90, height=17)
        tk.Label(
            balance_box, textvariable=self.balance_var,
            bg=Theme.PANEL_ALT, fg=Theme.ACCENT,
            font=(Theme.FONT, 15, "bold"), anchor=tk.E,
        ).place(x=12, y=20, width=182, height=22)

    def _build_game_panel(self, master: tk.Frame) -> None:
        panel = self._card(master, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT, padding=0)
        panel.place(x=0, y=0, width=self.GAME_PANEL_WIDTH, height=self.BODY_HEIGHT)

        self.board_canvas = tk.Canvas(
            panel,
            width=self.BOARD_WIDTH,
            height=self.BOARD_HEIGHT,
            bg=Theme.CANVAS_BG,
            bd=0,
            highlightthickness=0,
        )
        self.board_canvas.place(x=16, y=30, width=self.BOARD_WIDTH, height=self.BOARD_HEIGHT)

    def _build_sidebar(self, master: tk.Frame) -> None:
        sidebar = tk.Frame(
            master,
            width=self.SIDEBAR_WIDTH,
            height=self.BODY_HEIGHT,
            bg=Theme.APP_BG,
        )
        sidebar.place(
            x=self.GAME_PANEL_WIDTH + self.PANEL_GAP,
            y=0,
            width=self.SIDEBAR_WIDTH,
            height=self.BODY_HEIGHT,
        )

        MetricTile(
            sidebar, "当前下注", self.bet_var, Theme.CYAN,
            width=169, height=68,
        ).place(x=0, y=0, width=169, height=68)
        MetricTile(
            sidebar, "上局返还", self.last_win_var, Theme.GREEN,
            width=169, height=68,
        ).place(x=179, y=0, width=169, height=68)

        chips = self._card(sidebar, width=348, height=96)
        chips.place(x=0, y=74, width=348, height=96)
        self._section_title(chips.inner, "下注筹码").place(x=0, y=0, width=120, height=20)
        for index, (amount, chip_color, label) in enumerate(CHIP_CONFIGS):
            chip = ChipButton(
                chips.inner,
                label=label,
                amount=str(amount),
                chip_color=chip_color,
                command=self.add_chip,
                width=57,
                height=50,
            )
            chip.place(x=index * 62, y=24, width=57, height=50)
            self.chip_buttons.append(chip)

        risk = self._card(sidebar, width=348, height=76)
        risk.place(x=0, y=176, width=348, height=76)
        self._section_title(risk.inner, "风险模式").place(x=0, y=0, width=120, height=20)
        for index, (label, value, _mode) in enumerate(RISK_CONFIGS):
            btn = ModernButton(
                risk.inner,
                text=label,
                command=lambda v=value: self.set_risk(v),
                background=Theme.PANEL_ALT,
                hover_background=Theme.PANEL_HOVER,
                foreground=Theme.TEXT,
                font_size=11,
                bold=True,
            )
            btn.place(x=index * 107, y=28, width=100, height=32)
            self.risk_buttons.append(btn)

        # Clear bet and launch share a single row.
        actions = self._card(sidebar, width=348, height=60)
        actions.place(x=0, y=258, width=348, height=60)
        self.reset_bet_button = ModernButton(
            actions.inner,
            text="清空",
            command=self.reset_bet,
            background=Theme.RED,
            hover_background=Theme.RED_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.reset_bet_button.place(x=0, y=0, width=156, height=36)

        self.launch_button = ModernButton(
            actions.inner,
            text="发射弹珠",
            command=self.launch_ball,
            background=Theme.GREEN,
            hover_background=Theme.GREEN_HOVER,
            foreground="#FFFFFF",
            font_size=12,
            bold=True,
        )
        self.launch_button.place(x=168, y=0, width=156, height=36)

        state = self._card(sidebar, width=348, height=60, padding=9)
        state.place(x=0, y=324, width=348, height=60)
        tk.Label(
            state.inner,
            text="活动弹珠",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.W,
        ).place(x=0, y=0, width=86, height=18)
        tk.Label(
            state.inner,
            textvariable=self.active_var,
            bg=Theme.PANEL,
            fg=Theme.ACCENT,
            font=(Theme.FONT, 11, "bold"),
            anchor=tk.W,
        ).place(x=0, y=20, width=86, height=20)

        tk.Label(
            state.inner,
            text="最近结果",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 9),
            anchor=tk.E,
        ).place(x=92, y=0, width=230, height=18)
        tk.Label(
            state.inner,
            textvariable=self.status_var,
            bg=Theme.PANEL,
            fg=Theme.TEXT,
            font=(Theme.FONT_CJK, 10, "bold"),
            anchor=tk.E,
        ).place(x=92, y=20, width=230, height=20)

        # History card: 3 rows of 8 chevron cells.
        history = self._card(sidebar, width=348, height=174, padding=9)
        history.place(x=0, y=390, width=348, height=174)
        self._section_title(history.inner, "最近 24 球 · 当前模式").place(
            x=0, y=0, width=225, height=19)
        tk.Label(history.inner, text="最新在左上", bg=Theme.PANEL,
                 fg=Theme.TEXT_MUTED, font=(Theme.FONT_CJK, 8)).place(
            x=230, y=0, width=100, height=19)
        self.history_canvas = tk.Canvas(
            history.inner, width=328, height=135, bg=Theme.PANEL,
            bd=0, highlightthickness=0,
        )
        self.history_canvas.place(x=0, y=23, width=328, height=135)

        rules = self._card(sidebar, width=348, height=60, padding=9)
        rules.place(x=0, y=570, width=348, height=60)
        tk.Label(
            rules.inner,
            text="规则：每次发射按当前下注扣款，可连续多球。弹珠通过物理碰撞自然落槽，按底部固定赔率返还；目标返还率 95%（统计校准）。",
            bg=Theme.PANEL,
            fg=Theme.TEXT_MUTED,
            font=(Theme.FONT_CJK, 8),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=322,
        ).place(x=0, y=0, width=322, height=44)

    # ------------------------------------------------------------------
    # UI state
    # ------------------------------------------------------------------

    def add_chip(self, amount: str) -> None:
        if self.active_balls > 0:
            return
        try:
            value = float(amount)
        except (TypeError, ValueError):
            return
        new_bet = self.current_bet + value
        if new_bet <= self.balance:
            self.current_bet = new_bet
            self.update_display()
        else:
            messagebox.showwarning("余额不足", "账户余额不足以加入这个筹码。", parent=self.root)

    def reset_bet(self) -> None:
        if self.active_balls > 0:
            return
        self.current_bet = 0.0
        self.update_display()

    def set_risk(self, risk: str) -> None:
        if self.active_balls > 0 or risk not in PAYOUTS:
            return
        self.risk_level = risk
        self._reload_history()
        self.update_display()

    def update_display(self) -> None:
        self.balance_var.set(f"${self.balance:,.2f}")
        self.bet_var.set(f"${self.current_bet:,.2f}")
        self.last_win_var.set(f"${self.last_win:,.2f}")
        self.active_var.set(str(self.active_balls))
        self.status_var.set(self.last_result_text)

        locked = self.active_balls > 0
        state = tk.DISABLED if locked else tk.NORMAL
        for chip in self.chip_buttons:
            chip.configure(state=state)
        self.reset_bet_button.configure(state=state)

        for index, button in enumerate(self.risk_buttons):
            button.configure(state=state)
            selected = RISK_CONFIGS[index][1] == self.risk_level
            button.set_colors(
                Theme.ACCENT if selected else Theme.PANEL_ALT,
                Theme.ACCENT_HOVER if selected else Theme.PANEL_HOVER,
                "#FFFFFF" if selected else Theme.TEXT,
            )

        launch_enabled = self.current_bet > 0 and self.current_bet <= self.balance
        self.launch_button.configure(state=tk.NORMAL if launch_enabled else tk.DISABLED)

        self.draw_board()
        self.draw_landing_history()

    # ------------------------------------------------------------------
    # History strip (3 rows of 8, newest on the top-left)
    # ------------------------------------------------------------------

    def _reload_history(self) -> None:
        mode = RISK_KEY[self.risk_level]
        try:
            values = load_landing_log()["_paid_multipliers"][mode][-self.HISTORY_VISIBLE:]
        except Exception:
            values = []
        # Newest first.
        values = list(reversed(values))
        self._history_values = values + [None] * (self.HISTORY_VISIBLE - len(values))

    def draw_landing_history(self) -> None:
        """3 rows of 8 chevrons. Newest in the top-left, oldest in the bottom-right."""
        c = self.history_canvas
        c.delete("all")
        w = 41
        h = 45
        indent_x = 8
        indent_y = 8

        for i, value in enumerate(self._history_values):
            if i >= self.HISTORY_VISIBLE:
                break
            row = i // self.HISTORY_COLS
            col = i % self.HISTORY_COLS
            x = col * w
            y = row * h
            x1 = x + 1
            y1 = y + 1
            x2 = x + w - 1
            y2 = y + h - 1
            mid_y = y1 + h / 2

            if value is None:
                fill = Theme.PANEL_ALT
                outline = Theme.BORDER_SOFT
                text = "--"
                text_color = Theme.TEXT_DIM
            elif value > 1:
                fill = Theme.SLOT_GOOD
                outline = Theme.GREEN
                text = _format_history_value(value)
                text_color = "#1B3320"
            elif value < 1:
                fill = Theme.SLOT_BAD
                outline = Theme.RED
                text = _format_history_value(value)
                text_color = "#3D1213"
            else:
                fill = Theme.SLOT_NEUTRAL
                outline = Theme.AMBER
                text = "1"
                text_color = "#3D2D10"

            # Right-pointing chevron shape.
            c.create_polygon(
                x1, mid_y,
                x1 + indent_x, y1,
                x2 - indent_x, y1,
                x2, mid_y,
                x2 - indent_x, y2,
                x1 + indent_x, y2,
                fill=fill, outline=outline, width=1,
            )
            c.create_text(
                x1 + w / 2 - 2, mid_y,
                text=text,
                fill=text_color,
                font=(Theme.FONT, 9, "bold"),
            )

    # ------------------------------------------------------------------
    # Shared rendering / collision geometry
    # ------------------------------------------------------------------

    def _board_geometry(self, width: int, height: int) -> dict:
        p = self.physics
        return {"start_x": p.left, "top_y": p.top, "bottom_y": p.bottom,
                "bottom_width": p.right-p.left, "slot_width": p.slot_width}

    def draw_board(self) -> None:
        c, p = self.board_canvas, self.physics
        c.delete("all")
        c.create_rectangle(0, 0, self.BOARD_WIDTH, self.BOARD_HEIGHT,
                           fill=Theme.BOARD, outline="")
        c.create_rectangle(p.left, p.top, p.right, p.bottom,
                           fill="#15332e", outline="#D8B46A", width=2)
        for segment in p.funnel:
            c.create_line(*segment, fill="#D8B46A", width=3, capstyle=tk.ROUND)
        c.create_rectangle(p.centre-20, p.top+7, p.centre+20, p.top+16,
                           fill="#FFDE35", outline="#B8860B", width=2)
        self.pegs = p.pegs
        self.peg_rows = p.peg_rows
        for x, y in p.pegs:
            r = p.PEG_RADIUS
            c.create_oval(x-r, y-r, x+r, y+r, fill=Theme.PEG,
                          outline=Theme.PEG_BORDER, width=1)
        for i, payout in enumerate(PAYOUTS[self.risk_level]):
            x = p.left+i*p.slot_width
            c.create_rectangle(x, p.floor, x+p.slot_width, p.bottom,
                               fill="#426658" if payout >= 1 else "#654B43",
                               outline="#D8B46A")
            c.create_text(x+p.slot_width/2, p.floor+9, text=str(i+1),
                          fill="#DFDBC6", font=(Theme.FONT, 7))
            c.create_text(x+p.slot_width/2, p.floor+23,
                          text=format_multiplier(payout),
                          fill="white", font=(Theme.FONT, 8, "bold"))
            if i:
                c.create_line(x, p.divider_top, x, p.floor,
                              fill="#D8B46A", width=2, capstyle=tk.ROUND)
        # Only the stake amount (as an integer) at the top-left of the board.
        c.create_text(p.left+14, p.top+16,
                      text=f"${int(round(self.current_bet))}",
                      anchor=tk.W, fill="#F2E6C9",
                      font=(Theme.FONT_CJK, 16, "bold"))
        self._draw_ball_layer(clear_existing=False)

    def _draw_rotors(self) -> None:
        c, p = self.board_canvas, self.physics
        c.delete("rotor_dynamic")
        r = p.ROTOR_RADIUS
        for cx, cy, px, py, _ in p.rotor_segments():
            c.create_line(cx, cy, px, py, fill="#FFD46B", width=2*r,
                          capstyle=tk.ROUND, tags=("rotor_dynamic",))
        for x, y, _ in p.rotors:
            c.create_oval(x-r, y-r, x+r, y+r, fill="#704F2A",
                          outline="#FFE5A1", width=1, tags=("rotor_dynamic",))

    def _draw_ball_layer(self, *, clear_existing: bool = True) -> None:
        c = self.board_canvas
        if clear_existing:
            c.delete("ball_dynamic")
        self._draw_rotors()
        r = self.ball_radius
        for ball in self.balls:
            if ball.get("finished"):
                continue
            x, y = ball["x"], ball["y"]
            c.create_oval(x-r, y-r, x+r, y+r, fill=ball["color"],
                          outline=Theme.BALL_OUTLINE, width=1, tags=("ball_dynamic",))

    # ------------------------------------------------------------------
    # Betting and continuous physical simulation
    # ------------------------------------------------------------------

    def launch_ball(self) -> None:
        if self.current_bet <= 0:
            messagebox.showwarning("尚未下注", "请先选择下注筹码。", parent=self.root)
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "账户余额不足以发射这颗弹珠。", parent=self.root)
            return

        stake = float(self.current_bet)
        risk = self.risk_level

        self.balance -= stake
        update_balance_in_json(self.username, self.balance)

        self._add_ball(stake=stake, risk=risk)
        self.update_display()

    def _add_ball(self, *, stake: float, risk: str) -> None:
        # Initial release variation only. No further randomness or outcome steering.
        self.balls.append({
            "x": self.physics.centre+random.uniform(-5., 5.),
            "y": self.physics.top+30.,
            "vx": random.uniform(-24., 24.), "vy": 0., "spin": 0.,
            "color": random.choice(("#F5D25B", "#8CBEE0", "#EAA09A", "#B8D49C")),
            "finished": False, "slot": None, "rest_time": 0.,
            "stake": float(stake), "risk": risk, "start_time": time.monotonic(),
        })
        self.active_balls += 1

    def animate_balls(self) -> None:
        self._animation_job = None
        if self._closed:
            return
        now = time.monotonic()
        frame_dt = min(.10, max(0., now - self._last_frame_time))
        # Fixed small substeps avoid frame-rate-dependent collisions. A stalled
        # GUI pauses excess simulation time instead of teleporting falling balls.
        self._physics_accumulator += frame_dt
        self._last_frame_time = now
        while self._physics_accumulator >= self.physics.DT:
            self.physics.step(self.balls)
            self._physics_accumulator -= self.physics.DT
        finished = [i for i, b in enumerate(self.balls) if b.get("finished")]
        self.active_balls = sum(not b.get("finished") for b in self.balls)
        if finished:
            self._process_finished_balls(finished)
            self.update_display()
        else:
            self.active_var.set(str(self.active_balls))
            self._draw_ball_layer()
        # Keep ticking with zero balls so all SEVEN rotors always rotate.
        self._animation_job = self.root.after(self.frame_interval_ms, self.animate_balls)

    def _process_finished_balls(self, indices: list[int]) -> None:
        valid = sorted(
            {i for i in indices if 0 <= i < len(self.balls)},
            key=lambda i: self.balls[i]["start_time"],
        )

        for index in valid:
            ball = self.balls[index]
            slot = int(ball["slot"])
            slot_index = slot - 1
            risk = ball["risk"]
            stake = float(ball["stake"])
            payout = float(PAYOUTS[risk][slot_index])
            winnings = stake * payout

            self.balance += winnings
            self.last_win = winnings
            update_balance_in_json(self.username, self.balance)

            mode = RISK_KEY[risk]
            record_landing(mode, slot, payout)

            payout_text = format_multiplier(payout)
            self.last_result_text = f"槽 {slot} · {payout_text} · ${winnings:,.2f}"
            self._show_ball_result(slot, payout_text, winnings)

        for index in sorted(valid, reverse=True):
            self.balls.pop(index)

        self.active_balls = sum(1 for ball in self.balls if not ball.get("finished"))

        if valid:
            self._reload_history()

    def _show_ball_result(self, slot: int, payout_text: str, winnings: float) -> None:
        c = self.board_canvas
        geo = self._board_geometry(self.BOARD_WIDTH, self.BOARD_HEIGHT)
        x = geo["start_x"] + (slot - 0.5) * geo["slot_width"]
        y = geo["bottom_y"] - 15
        result_id = c.create_text(
            x, y,
            text=f"{payout_text}\n${winnings:,.2f}",
            fill=Theme.AMBER,
            font=(Theme.FONT, 9, "bold"),
            justify=tk.CENTER,
        )
        try:
            self.root.after(1800, lambda item=result_id: c.delete(item))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Closing / embedding
    # ------------------------------------------------------------------

    def stop_game(self) -> None:
        self._closed = True
        self.animation_running = False
        if self._animation_job is not None:
            try:
                self.root.after_cancel(self._animation_job)
            except tk.TclError:
                pass
            self._animation_job = None

    def _on_destroy(self, event) -> None:
        if event.widget is self.root:
            self.stop_game()

    def on_closing(self) -> None:
        self.stop_game()
        update_balance_in_json(self.username, self.balance)
        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(self.balance)
        else:
            self.root.destroy()


def main(
    initial_balance=1000.0,
    username="Guest",
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
        if EmbeddedGamePage is None:
            raise RuntimeError(
                "EmbeddedGamePage is unavailable. Place plinko.py inside the Small_Games package "
                "or make small_games.py importable before using embedded mode."
            )
        page = EmbeddedGamePage(
            parent,
            title="Plinko",
            username=actual_user,
            balance=actual_balance,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.set_requested_size(1150, 750)
        game = PlinkoGame(page.host, actual_balance, actual_user)
        page.attach_game(game)
        return page

    root = tk.Tk()
    game = PlinkoGame(root, actual_balance, actual_user)
    root.mainloop()
    return game.balance


if __name__ == "__main__":
    final_balance = main(10000.0, "test_user")
    print(f"Final balance: {final_balance:.2f}")