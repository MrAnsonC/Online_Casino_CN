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
import uuid
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from PIL import ImageColor
except Exception:
    ImageColor = None

def uuid_uniform(a: float, b: float) -> float:
    """使用 uuid4 的随机位生成 [a, b) 范围内的浮点数"""
    # uuid4 返回 128 位随机整数，取高 64 位足够了
    rand_int = uuid.uuid4().int >> 64   # 取高 64 位
    # 映射到 [0, 1) 区间
    rand_float = rand_int / (1 << 64)
    return a + (b - a) * rand_float


# =========================================================
# Constants for scaling the betting board (shrink to 75%)
# =========================================================
ORIGINAL_SCALE = 2.0
BOARD_SCALE = 1.5                     # 75% of original scale (since 1.5 / 2 = 0.75)
BOARD_W = 618
BOARD_H = 340

# =========================================================
# Paths / persistence
# =========================================================

def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_path() -> str:
    return os.path.join(project_root(), "A_Tools/Account/saving_data.json")


def roulette_log_path() -> str:
    log_dir = os.path.join(project_root(), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Lucky_6.json")


def ensure_json_file(path: str, default_obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_obj, f, ensure_ascii=False, indent=4)


def load_user_data():
    path = user_data_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_user_data(users):
    path = user_data_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)


def load_balance(username: str, default_balance: float = 1_000_000.0) -> float:
    if username == "Guest":
        return default_balance

    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            try:
                return float(user.get("cash", default_balance))
            except Exception:
                return default_balance

    users.append({"user_name": username, "cash": f"{default_balance:.2f}"})
    save_user_data(users)
    return default_balance


def update_balance_in_json(username: str, new_balance: float):
    if username == "Guest":
        return

    users = load_user_data()
    found = False
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{float(new_balance):.2f}"
            found = True
            break
    if not found:
        users.append({"user_name": username, "cash": f"{float(new_balance):.2f}"})
    save_user_data(users)


# =========================================================
# Roulette rules / constants
# =========================================================

WHEEL_SEQUENCE = [
    "1", "3", "1", "6", "1", "3", "1", "👑",
    "1", "3", "1", "6", "3", "1", "12", "1",
    "6", "1", "3", "1", "25", "1", "3", "1",
    "6", "1", "3", "1", "12", "1", "6", "1",
    "3", "1", "💵", "3", "1", "3", "1", "3",
    "1", "12", "1", "6", "1", "3", "1", "25",
    "1", "3", "1", "6", "1", "12"
]
ROULETTE_SEQUENCE = WHEEL_SEQUENCE  # 保留旧变量名，原有轮盘动画无需改写
BET_OPTIONS = ("1", "3", "6", "12", "25", "👑", "💵")
SPECIAL_NET_ODDS = {"👑": 50, "💵": 50}
CHIP_SPECS = [
    (100, '#202020', '100'),
    (500, '#d780c0', '500'),
    (1000, '#ab0058', '1K'),
    (5000, '#ba3438', '5K'),
    (10000, '#70439a', '10K'),
    (50000, '#2e7542', '50K'),
]
assert len(WHEEL_SEQUENCE) == 54, f"Wheel sequence must have 54 items, got {len(WHEEL_SEQUENCE)}"


def fixed_flapper_winning_index(wheel_offset: float) -> int:
    """顶部 0° 固定判定线；扇区采用 [起始边界, 结束边界) 区间。"""
    step = 360.0 / len(ROULETTE_SEQUENCE)
    position = ((-wheel_offset) % 360.0) / step
    nearest = round(position)
    if abs(position - nearest) < 1e-10:
        position = float(nearest)
    return math.floor(position) % len(ROULETTE_SEQUENCE)


class FlapperPhysics:
    """与 Lightning Storm 相同的固定拨片：销钉推动 + 阻尼弹簧回弹。

    支点始终固定在 12 点，angle 只表示拨片绕支点的弹性偏转，
    不表示绕轮盘旋转的位置，也不参与开奖判定。
    """

    # 销钉半径和金属拨片宽度共同占用的角度范围；停位必须在其余间隙内。
    PIN_CLEARANCE = 0.43

    def __init__(self):
        self.step = 360.0 / len(ROULETTE_SEQUENCE)
        self.reset()

    def reset(self):
        self.angle = 0.0
        self.velocity = 0.0
        self.clicks = 0
        self._last_cell = None
        self._contact_pin = None
        self.direction = 1
        self.sway_angle = 0.0
        self.sway_velocity = 0.0
        self._has_contact = False
        self._settling_started = False
        self._settling_elapsed = 0.0
        self._quiet_elapsed = 0.0

    def begin_settling(self):
        """轮盘停住时释放支架余振，保留小幅欠阻尼摆动，而非立刻归零。"""
        if self._settling_started or not self._has_contact:
            return
        self._settling_started = True
        self._settling_elapsed = 0.0
        self._quiet_elapsed = 0.0
        impulse = min(11.0, max(8.0, abs(self.velocity) * 0.1 + abs(self.angle) * 0.4))
        self.sway_velocity = self.direction * impulse

    @property
    def display_angle(self):
        return max(-30.0, min(30.0, self.angle + self.sway_angle))

    def contact_fraction(self, offset, direction=1):
        """形变量与轮盘势能对应：接近钉顶压弯，远离钉顶释放。"""
        distance = ((offset / self.step + 0.5) % 1.0 - 0.5) * self.step
        span = self.PIN_CLEARANCE * self.step
        if abs(distance) < span:
            return math.cos(math.pi * distance / (2.0 * span))
        return None

    def pin_clear(self, offset):
        phase = (offset / self.step) % 1.0
        return self.PIN_CLEARANCE <= phase <= 1.0 - self.PIN_CLEARANCE

    def advance(self, previous: float, current: float, dt: float, moving: bool = True):
        if dt <= 0:
            return
        steps = max(1, math.ceil(dt / 0.004))
        h = dt / steps
        for index in range(steps):
            offset = previous + (current - previous) * (index + 1) / steps
            cell = math.floor(offset / self.step)
            if self._last_cell is not None and cell != self._last_cell and moving:
                self.clicks += abs(cell - self._last_cell)
            self._last_cell = cell
            fraction = self.contact_fraction(offset, self.direction) if moving else None
            if fraction is not None:
                pin = math.floor(offset / self.step + 0.5)
                if pin != self._contact_pin:
                    # 入钉时记录接触侧；未越钉就退回时，拨片在原侧逐步复位。
                    if current != previous:
                        self.direction = -1 if current < previous else 1
                    self._contact_pin = pin
                self._has_contact = True
                required = 25.0 * max(0.0, min(1.0, fraction))
                if self.direction * self.angle < required:
                    impulse = (required - self.direction * self.angle) / h
                    self.velocity = self.direction * min(500.0, max(self.direction * self.velocity, impulse))
                    self.angle = self.direction * required
            else:
                self._contact_pin = None
            acceleration = -1050.0 * self.angle - 28.0 * self.velocity
            self.velocity += acceleration * h
            self.angle += self.velocity * h
            if self.angle > 30.0:
                self.angle, self.velocity = 30.0, min(0.0, self.velocity)
            if self.angle < -30.0:
                self.angle, self.velocity = -30.0, max(0.0, self.velocity)
            if self._settling_started:
                # 约 1.5Hz 的支架余振，逐步衰减；支点和开奖判定线仍固定。
                sway_acceleration = -85.0 * self.sway_angle - 3.2 * self.sway_velocity
                self.sway_velocity += sway_acceleration * h
                self.sway_angle += self.sway_velocity * h
                self._settling_elapsed += h
                quiet = (abs(self.angle) < 0.15 and abs(self.velocity) < 1.2
                         and abs(self.sway_angle) < 0.03 and abs(self.sway_velocity) < 0.2)
                self._quiet_elapsed = self._quiet_elapsed + h if quiet else 0.0

    @property
    def settled(self):
        blade_quiet = abs(self.angle) < 0.15 and abs(self.velocity) < 1.2
        if not self._settling_started:
            return blade_quiet
        return blade_quiet and self._settling_elapsed >= 1.2 and self._quiet_elapsed >= 0.35


class WheelPhysics:
    """双向摩擦与销钉弹力，按惯性决定越过销钉或退回相邻间隙。

    角速度采用 °/s，阻力采用 °/s²。销钉接触的势能在钉顶最高、
    间隙中为零：上坡消耗惯性，下坡释放弹力；另计轴承、空气和
    拨片阻尼损失。低速接触时可以自然反向，不预设终点或结果，
    不把停位移动到扇区中心。接触采用离散势能梯度积分，惯性与
    弹性势能互换，摩擦及阻尼只耗能；每个子步不超过 1ms。
    """

    SUBSTEP = 0.001

    def __init__(self, angle, velocity, flapper, bearing=22.0,
                 viscous=0.07, air_drag=0.00016, pin_energy=45.0, pin_damping=0.028):
        self.angle = float(angle)
        self.velocity = float(velocity)
        self.flapper = flapper
        self.bearing = float(bearing)
        self.viscous = float(viscous)
        self.air_drag = float(air_drag)
        self.pin_energy = float(pin_energy)
        self.pin_damping = float(pin_damping)
        self.spin_direction = -1 if self.velocity < 0.0 else 1
        self.flapper.direction = self.spin_direction
        self.acceleration = self._acceleration(self.angle, self.velocity)
        self.elapsed = 0.0
        self.result_locked_at = None
        self.result_locked_index = None
        self._update_result_lock()

    @property
    def at_rest(self):
        return self.velocity == 0.0 and (self.pin_energy <= 0.0 or self.flapper.pin_clear(self.angle))

    @property
    def mechanical_energy(self):
        return 0.5 * self.velocity ** 2 + self._pin_potential(self.angle)

    def _pin_potential(self, angle):
        distance = self._pin_contact(angle)
        if distance is not None:
            span = self.flapper.PIN_CLEARANCE * self.flapper.step
            return self.pin_energy * math.cos(math.pi * distance / (2.0 * span)) ** 2
        return 0.0

    @property
    def result_is_locked(self):
        # 每枚销钉的势垒均为 pin_energy；低于两侧势垒就不能离开当前格。
        # 留 2% 积分余量，避免在钉顶附近的临界状态过早结算。
        return self.pin_energy > 0.0 and self.mechanical_energy < 0.98 * self.pin_energy

    def _update_result_lock(self):
        """记录首次确定无法离开当前销钉间隙的模拟时间，不改角度或速度。"""
        if not self.result_is_locked:
            self.result_locked_at = None
            self.result_locked_index = None
            return
        index = fixed_flapper_winning_index(self.angle)
        if self.result_locked_at is None or self.result_locked_index != index:
            self.result_locked_at = self.elapsed
            self.result_locked_index = index

    def _pin_contact(self, angle):
        if self.pin_energy <= 0.0:
            return None
        step = self.flapper.step
        distance = ((angle / step + 0.5) % 1.0 - 0.5) * step
        span = self.flapper.PIN_CLEARANCE * step
        return distance if abs(distance) < span else None

    def _pin_effects(self, angle):
        distance = self._pin_contact(angle)
        if distance is None:
            return 0.0, 0.0
        span = self.flapper.PIN_CLEARANCE * self.flapper.step
        phase = math.pi * distance / span
        # E(θ)=pin_energy*cos²(πθ/2span)，弹力矩为 -dE/dθ。
        torque = self.pin_energy * math.pi / (2.0 * span) * math.sin(phase)
        damping = self.pin_damping * math.cos(phase / 2.0) ** 2
        return torque, damping

    def _acceleration(self, angle, velocity):
        contact = self._pin_contact(angle)
        torque, pin_damping = self._pin_effects(angle)
        if contact is not None:
            # 接触时使用连续的摩擦近似；摩擦只耗散能量。
            axle = self.bearing * math.tanh(velocity / 3.0)
        else:
            axle = math.copysign(self.bearing, velocity) if velocity else 0.0
        return (torque - axle - (self.viscous + pin_damping) * velocity
                - self.air_drag * abs(velocity) * velocity)

    def _resistance(self, angle, velocity):
        _, pin_damping = self._pin_effects(angle)
        speed = abs(velocity)
        return self.bearing + (self.viscous + pin_damping) * speed + self.air_drag * speed ** 2

    def _advance_contact(self, h):
        """以离散势能梯度求弹力，不让数值积分给临界越钉补充能量。"""
        angle, velocity = self.angle, self.velocity
        potential = self._pin_potential(angle)
        next_velocity = velocity + self._acceleration(angle, velocity) * h
        for _ in range(12):
            mean_velocity = (velocity + next_velocity) / 2.0
            next_angle = angle + mean_velocity * h
            displacement = next_angle - angle
            middle_angle = (angle + next_angle) / 2.0
            if abs(displacement) < 1e-8:
                torque, damping = self._pin_effects(middle_angle)
            else:
                torque = (potential - self._pin_potential(next_angle)) / displacement
                _, damping = self._pin_effects(middle_angle)
            resistance = (self.bearing * math.tanh(mean_velocity / 3.0)
                          + (self.viscous + damping) * mean_velocity
                          + self.air_drag * abs(mean_velocity) * mean_velocity)
            candidate = velocity + (torque - resistance) * h
            difference = abs(candidate - next_velocity)
            next_velocity = candidate
            if difference < 1e-12:
                break
        self.angle = angle + (velocity + next_velocity) * h / 2.0
        self.velocity = next_velocity
        self.acceleration = (next_velocity - velocity) / h

    def advance(self, dt):
        if dt <= 0:
            return
        if self.at_rest:
            self.flapper.begin_settling()
            self.flapper.advance(self.angle, self.angle, dt, moving=False)
            self.acceleration = 0.0
            self.elapsed += dt
            self._update_result_lock()
            return
        steps = max(1, math.ceil(dt / self.SUBSTEP))
        h = dt / steps
        for _ in range(steps):
            previous = self.angle
            velocity = self.velocity
            speed = abs(velocity)
            if (self._pin_contact(previous) is not None
                    or self._pin_contact(previous + velocity * h / 2.0) is not None
                    or self._pin_contact(previous + velocity * h) is not None):
                self._advance_contact(h)
            elif speed > 0.0:
                direction = math.copysign(1.0, velocity)
                resistance = self._resistance(previous, velocity)
                middle_speed = max(0.0, speed - resistance * h / 2.0)
                middle_angle = previous + direction * middle_speed * h / 2.0
                resistance = self._resistance(middle_angle, middle_speed)
                active_time = min(h, speed / resistance) if resistance else h
                next_speed = 0.0 if speed <= resistance * h else speed - resistance * h
                self.velocity = direction * next_speed
                self.angle += direction * (speed + next_speed) * active_time / 2.0
                self.acceleration = -direction * resistance if next_speed > 0.0 else 0.0
            else:
                self.acceleration = 0.0
            if self.at_rest:
                self.flapper.begin_settling()
            self.flapper.advance(previous, self.angle, h, moving=abs(self.angle - previous) > 1e-12)
            self.elapsed += h
            self._update_result_lock()


def draw_wheel_pins(canvas, cx, cy, outer_r, offset_deg):
    """销钉位于扇区分隔边界，随转盘移动；与拨片接触相位使用同一轮序。"""
    step = 360.0 / len(ROULETTE_SEQUENCE)
    for index in range(len(ROULETTE_SEQUENCE)):
        angle = math.radians(offset_deg + index * step)
        ux, uy = math.sin(angle), -math.cos(angle)
        canvas.create_line(
            cx + (outer_r + 2) * ux, cy + (outer_r + 2) * uy,
            cx + (outer_r + 10) * ux, cy + (outer_r + 10) * uy,
            fill="#C9A24A", width=2, tags=("wheel_pins",)
        )
        px, py = cx + (outer_r + 5) * ux, cy + (outer_r + 5) * uy
        canvas.create_oval(px - 2.4, py - 2.4, px + 2.4, py + 2.4,
                           fill="#F2DFB1", outline="#83683E", tags=("wheel_pins",))


def draw_fixed_flapper(canvas, cx, cy, outer_r, angle=0.0):
    """沿用 Lightning Storm 的金属长拨片、支架、轴销与固定判定线。

    按轮盘顶部可用高度缩放，使主轮盘和玩法插图都能完整显示支架。
    """
    scale = min(1.0, max(0.5, (cy - outer_r - 2.0) / 43.0))
    hinge_y = cy - outer_r - 23.0 * scale
    length = 41.0 * scale
    canvas.create_rectangle(cx - 20 * scale, hinge_y - 20 * scale,
                             cx + 20 * scale, hinge_y + 2 * scale,
                             fill="#4A5662", outline="#BCC5CA", width=2,
                             tags=("flapper_mount",))
    for dx in (-13 * scale, 13 * scale):
        canvas.create_oval(cx + dx - 2 * scale, hinge_y - 12 * scale,
                           cx + dx + 2 * scale, hinge_y - 8 * scale,
                           fill="#DDDFCF", outline="#5B6367", tags=("flapper_mount",))
    theta = math.radians(angle)

    def point(x, y):
        return (cx + x * math.cos(theta) + y * math.sin(theta),
                hinge_y - x * math.sin(theta) + y * math.cos(theta))

    outline = [point(x * scale, y * scale) for x, y in
               ((-7, 0), (7, 0), (6, 34), (3, 41), (-3, 41), (-6, 34))]
    coords = [value for p in outline for value in p]
    canvas.create_polygon([value + 2 * scale for value in coords],
                           fill="#02060C", outline="", tags=("flapper_shadow",))
    canvas.create_polygon(coords, fill="#E0E5DF", outline="#657777", width=2,
                           tags=("flapper",))
    canvas.create_line(*point(-2 * scale, 8 * scale), *point(-2 * scale, length - 6 * scale),
                       fill="#FFFFFF", width=2, tags=("flapper",))
    canvas.create_line(*point(4 * scale, 7 * scale), *point(3 * scale, length - 7 * scale),
                       fill="#A6B1B0", width=1, tags=("flapper",))
    canvas.create_oval(cx - 7 * scale, hinge_y - 7 * scale,
                       cx + 7 * scale, hinge_y + 7 * scale,
                       fill="#A18A56", outline="#F7E6B4", width=2,
                       tags=("flapper_hinge",))
    canvas.create_oval(cx - 2 * scale, hinge_y - 2 * scale,
                       cx + 2 * scale, hinge_y + 2 * scale,
                       fill="#37484B", outline="", tags=("flapper_hinge",))

RED_NUMBERS = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36,
}

NUMBERS_1_TO_36 = [str(i) for i in range(1, 37)]

BET_ODDS = {
    "straight": 35,
    "split": 17,
    "street": 11,
    "corner": 8,
    "six_line": 5,
    "dozen": 2,
    "column": 2,
    "color": 1,
    "odd_even": 1,
    "high_low": 1,
    "five_number": 6,
}

OUTCOME_COLORS = {
    "1": "#E9C46A", "3": "#2A9D8F", "6": "#3A86FF",
    "12": "#8338EC", "25": "#E63946", "👑": "#2B9348", "💵": "#6A0DAD",
}

OUTCOME_TEXT_COLORS = {key: ("#2A1B08" if key == "1" else "#ffffff") for key in BET_OPTIONS}

def lucky_net_odds(result: str) -> int:
    return SPECIAL_NET_ODDS[result] if result in SPECIAL_NET_ODDS else int(result)


def lucky_board_bounds():
    """上排五个数字、下排两个特殊图案；完整容纳在固定窗口内。"""
    cell_w, cell_h, gap = 108, 100, 12
    top_y, bottom_y = 36, 156
    bounds = {}
    left = (BOARD_W - (5 * cell_w + 4 * gap)) / 2
    for index, result in enumerate(BET_OPTIONS[:5]):
        x1 = left + index * (cell_w + gap)
        bounds[result] = (x1, top_y, x1 + cell_w, top_y + cell_h)
    special_w, special_gap = 234, 18
    left = (BOARD_W - (2 * special_w + special_gap)) / 2
    for index, result in enumerate(BET_OPTIONS[5:]):
        x1 = left + index * (special_w + special_gap)
        bounds[result] = (x1, bottom_y, x1 + special_w, bottom_y + cell_h)
    return bounds


def lucky_bet_content_center(bounds):
    """沿用原来的内容高度，数字、图案与筹码共同在水平方向居中。"""
    x1, y1, x2, _ = bounds
    return (x1 + x2) / 2, y1 + 33


def draw_bet_card_shape(canvas, x1, y1, x2, y2, radius=10, **kwargs):
    """使用 Canvas 原生多边形画圆角卡片，普通态与中奖态共用。"""
    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    points = []
    for cx, cy, start in ((x2 - radius, y1 + radius, -90),
                          (x2 - radius, y2 - radius, 0),
                          (x1 + radius, y2 - radius, 90),
                          (x1 + radius, y1 + radius, 180)):
        for index in range(7):
            angle = math.radians(start + 15 * index)
            points.extend((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return canvas.create_polygon(points, **kwargs)


def draw_lucky_bet_cell(canvas, result, bounds, fill=None, text_fill=None, tag=None):
    """统一绘制普通下注格与开奖闪烁格，确保文字大小和方位完全一致。"""
    x1, y1, x2, y2 = bounds
    tags = (tag,) if tag else ()
    bg = fill or OUTCOME_COLORS[result]
    fg = text_fill or OUTCOME_TEXT_COLORS[result]
    if fill is None:
        draw_bet_card_shape(canvas, x1 + 3, y1 + 3, x2 + 3, y2 + 3,
                            fill="#071713", outline="", tags=tags)
    draw_bet_card_shape(canvas, x1, y1, x2, y2, fill=bg,
                        outline="#D4AF37", width=2, tags=tags)
    special = result in {"👑", "💵"}
    text_x, text_y = lucky_bet_content_center(bounds)
    canvas.create_text(
        text_x, text_y, text=result, fill=fg,
        font=("Segoe UI Emoji" if special else "Arial", 36, "bold"), angle=0, tags=tags
    )
    band_fill = "#D4AF37" if fill is not None else "#143B32"
    band_text = "#000000" if fill is not None else "#FFE6A3"
    draw_bet_card_shape(canvas, x1 + 7, y2 - 32, x2 - 7, y2 - 6, radius=6,
                        fill=band_fill, outline="", tags=tags)
    canvas.create_text(
        (x1 + x2) / 2, y2 - 19, text=f"{lucky_net_odds(result)} : 1", fill=band_text,
        font=("Arial", 15, "bold"), angle=0, tags=tags
    )

COLOR_GROUPS = {
    "Red": {"results": {str(n) for n in RED_NUMBERS}},
    "Black": {"results": {str(n) for n in range(1, 37)} - {str(n) for n in RED_NUMBERS}},
    "Green": {"results": {"0", "00"}},
}

ROULETTE_BET_TYPES = {
    "straight",
    "split",
    "street",
    "corner",
    "six_line",
    "dozen",
    "column",
    "color",
    "odd_even",
    "high_low",
    "five_number",
}


# =========================================================
# History store
# =========================================================

class RouletteHistory:
    ORDERED_TOP_KEYS = ["Total", "Red", "Black", "Green", "WheelSpin", "Record1", "Record2"]

    RECORD1_KEY = "Record1"
    RECORD2_KEY = "Record2"
    LEGACY_RECORD_KEY = "Record"

    RECORD1_MAX = 120
    RECORD2_MAX = 2000

    def __init__(self, path: str):
        self.path = path
        self.data = self._load_or_create()
        self._reorder_and_save()

    def _default_payload(self):
        return {
            "Total": 0,
            "Red": 0,
            "Black": 0,
            "Green": 0,
            "WheelSpin": {
                "next_direction": "left",
                "last_direction": None,
                "spins_started": 0,
                "last_initial_speed_m_s": None,
            },
            "Record1": {},
            "Record2": {},
        }

    def _clean_record(self, record_obj):
        """
        只保留符合 xx_Data 格式的资料，并把值统一成：
        {"result": "...", "color": "..."}
        """
        if not isinstance(record_obj, dict):
            return {}

        cleaned = {}
        for key, entry in record_obj.items():
            if not isinstance(key, str) or not key.endswith("_Data"):
                continue

            if isinstance(entry, dict):
                cleaned[key] = {
                    "result": str(entry.get("result", "")),
                    "color": str(entry.get("color", "")),
                }
            else:
                cleaned[key] = {"result": "", "color": ""}
        return cleaned

    def _load_or_create(self):
        ensure_json_file(self.path, self._default_payload())
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return self._default_payload()
        except Exception:
            return self._default_payload()

        payload = self._default_payload()
        for key in ("Total", "Red", "Black", "Green"):
            try:
                payload[key] = int(data.get(key, 0))
            except Exception:
                payload[key] = 0

        spin_state = data.get("WheelSpin", {})
        if isinstance(spin_state, dict):
            clean_state = payload["WheelSpin"]
            if spin_state.get("next_direction") in ("left", "right"):
                clean_state["next_direction"] = spin_state["next_direction"]
            elif spin_state.get("last_direction") in ("left", "right"):
                clean_state["next_direction"] = "right" if spin_state["last_direction"] == "left" else "left"
            if spin_state.get("last_direction") in ("left", "right"):
                clean_state["last_direction"] = spin_state["last_direction"]
            try:
                clean_state["spins_started"] = max(0, int(spin_state.get("spins_started", 0)))
            except (TypeError, ValueError, OverflowError):
                pass
            try:
                speed = float(spin_state.get("last_initial_speed_m_s"))
                if math.isfinite(speed) and speed > 0.0:
                    clean_state["last_initial_speed_m_s"] = speed
            except (TypeError, ValueError, OverflowError):
                pass

        # 兼容旧版：旧的 Record 自动并入 Record1
        legacy_record1 = data.get(self.RECORD1_KEY)
        if not isinstance(legacy_record1, dict):
            legacy_record1 = data.get(self.LEGACY_RECORD_KEY, {})
        cleaned_record1 = self._clean_record(legacy_record1)
        payload[self.RECORD1_KEY] = {
            f"{i:02d}_Data": cleaned_record1[f"{i:02d}_Data"]
            for i in range(1, self.RECORD1_MAX + 1)
            if f"{i:02d}_Data" in cleaned_record1
        }
        payload[self.RECORD2_KEY] = self._clean_record(data.get(self.RECORD2_KEY, {}))
        return payload

    def begin_wheel_spin(self, initial_speed_m_s):
        """开转时即保存下一局来向；关闭或重新进入后仍然左右交替。"""
        speed = float(initial_speed_m_s)
        if not math.isfinite(speed) or speed <= 0.0:
            raise ValueError("Initial wheel speed must be positive and finite")
        self.data = self._load_or_create()
        state = self.data["WheelSpin"]
        direction = state["next_direction"]
        state.update({
            "last_direction": direction,
            "next_direction": "right" if direction == "left" else "left",
            "spins_started": state["spins_started"] + 1,
            "last_initial_speed_m_s": speed,
        })
        self._reorder_and_save()
        return -1 if direction == "left" else 1

    def _reorder_and_save(self):
        new_data = {}
        for key in self.ORDERED_TOP_KEYS:
            if key in self.data:
                new_data[key] = self.data[key]
        for key, value in self.data.items():
            if key not in new_data:
                new_data[key] = value
        self.data = new_data
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def _record_to_ordered_list(self, record_name: str, limit: int):
        record = self.data.get(record_name, {})
        ordered = []

        for i in range(1, limit + 1):
            key = f"{i:02d}_Data"
            entry = record.get(key)
            if isinstance(entry, dict):
                ordered.append({
                    "result": str(entry.get("result", "")),
                    "color": str(entry.get("color", "")),
                })
            else:
                ordered.append({"result": "", "color": ""})
        return ordered

    def _ordered_list_to_record(self, entries):
        new_record = {}
        for idx, entry in enumerate(entries, start=1):
            new_record[f"{idx:02d}_Data"] = {
                "result": str(entry.get("result", "")),
                "color": str(entry.get("color", "")),
            }
        return new_record

    def recent_results(self, limit: int = 54, record_name: str = "Record1"):
        record_key = record_name
        if record_key not in self.data:
            record_key = self.LEGACY_RECORD_KEY if self.LEGACY_RECORD_KEY in self.data else self.RECORD1_KEY

        return self._record_to_ordered_list(record_key, limit)

    def recent_results2(self, limit: int = 500):
        return self._record_to_ordered_list(self.RECORD2_KEY, limit)

    def _append_result_to_record1(self, result: str, color: str):
        # 获取当前 Record1 的所有条目（长度为 120，空位为 {"result":"","color":""}）
        existing = self._record_to_ordered_list(self.RECORD1_KEY, self.RECORD1_MAX)

        # 统计实际非空记录的数量
        actual_count = sum(1 for entry in existing if entry["result"])

        # 标记路独立保存最多 120 局；写入第 121 局前删除最旧的 6 局。
        if actual_count >= self.RECORD1_MAX:
            existing = existing[:self.RECORD1_MAX - 6]

        # 将新结果插入头部，然后拼接上所有非空旧记录（已过滤空位）
        new_entries = [{"result": result, "color": color}] + [e for e in existing if e["result"]]

        # 写入触发清理后的记录数为 115，之后重新逐局增长至 120。
        new_entries = new_entries[:self.RECORD1_MAX]

        # 写回 data
        self.data[self.RECORD1_KEY] = self._ordered_list_to_record(new_entries)

    def _append_result_to_record2(self, result: str, color: str):
        existing = self._record_to_ordered_list(self.RECORD2_KEY, self.RECORD2_MAX)
        new_entries = [{"result": result, "color": color}] + [e for e in existing if e["result"]]
        new_entries = new_entries[:self.RECORD2_MAX]
        self.data[self.RECORD2_KEY] = self._ordered_list_to_record(new_entries)

    def add_result(self, result: str):
        color = roulette_color(result)
        self.data = self._load_or_create()

        self._append_result_to_record1(result, color)
        self._append_result_to_record2(result, color)

        self.data["Total"] = int(self.data.get("Total", 0)) + 1
        if color == "Red":
            self.data["Red"] = int(self.data.get("Red", 0)) + 1
        elif color == "Black":
            self.data["Black"] = int(self.data.get("Black", 0)) + 1
        else:
            self.data["Green"] = int(self.data.get("Green", 0)) + 1

        self._reorder_and_save()

    def counts(self):
        return {
            "Red": int(self.data.get("Red", 0)),
            "Black": int(self.data.get("Black", 0)),
            "Green": int(self.data.get("Green", 0)),
        }

    def total(self):
        return int(self.data.get("Total", 0))


# =========================================================
# Board geometry / drawing (scaled)
# =========================================================

ROOT_BG = "#1B3D31"
CYAN = "#007502"
TEXT = "#ffffff"
RED = "#ff2a23"
BLACK = "#050505"
DARK_BLUE = "#173f66"
TEAL = "#188a8e"

def draw_center_text(canvas, x1, y1, x2, y2, text, font=("Arial", 12, "bold"), angle=0, fill=TEXT):
    canvas.create_text(
        (x1 + x2) / 2,
        (y1 + y2) / 2,
        text=text,
        fill=fill,
        font=font,
        angle=angle
    )


def draw_cell(canvas, x1, y1, x2, y2, fill, text=None, text_font=("Arial", 12, "bold"),
              text_angle=0, text_fill=TEXT, outline=CYAN, width=2):
    canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width)
    if text is not None:
        draw_center_text(canvas, x1, y1, x2, y2, text, font=text_font, angle=text_angle, fill=text_fill)



def get_board_layout(scale=BOARD_SCALE):
    x0 = 12 * scale
    y0 = 17 * scale
    num_w = 29 * scale
    num_h = 38 * scale
    zero_w = num_w 
    zero_h = (3 * num_h) // 2
    dozen_h = 39 * scale
    outer_h = 38 * scale
    col_w = 14 * scale + 20

    zero_x1 = x0
    zero_x2 = zero_x1 + zero_w
    grid_x1 = zero_x2
    grid_x2 = grid_x1 + 12 * num_w
    col_x1 = grid_x2
    col_x2 = col_x1 + col_w

    rows = [
        [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],
        [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
        [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
    ]
    return {
        "x0": x0,
        "y0": y0,
        "num_w": num_w,
        "num_h": num_h,
        "zero_w": zero_w,
        "zero_h": zero_h,
        "dozen_h": dozen_h,
        "outer_h": outer_h,
        "col_w": col_w,
        "zero_x1": zero_x1,
        "zero_x2": zero_x2,
        "grid_x1": grid_x1,
        "grid_x2": grid_x2,
        "col_x1": col_x1,
        "col_x2": col_x2,
        "rows": rows,
    }


def draw_roulette_static(canvas, scale=BOARD_SCALE):
    canvas.delete("all")
    canvas.configure(bg=ROOT_BG)

    draw_bet_card_shape(canvas, 4, 4, BOARD_W - 4, 278, radius=14,
                        fill="#0D3027", outline="#315F51", width=1)
    for result, (x1, y1, x2, y2) in lucky_board_bounds().items():
        draw_lucky_bet_cell(canvas, result, (x1, y1, x2, y2))
    return


def roulette_color(result: str) -> str:
    # 历史存储仍沿用原 UI 的三组统计键，结果本身则完整保存在 Record 中。
    if result in {"1", "12", "👑"}:
        return "Red"
    if result in {"3", "25", "💵"}:
        return "Black"
    return "Green"


# =========================================================
# Roulette board interaction (geometry with scaling)
# =========================================================


class RouletteBoardGeometry:
    def __init__(self, scale=BOARD_SCALE):
        self.scale = scale
        layout = get_board_layout(scale)

        self.x0 = layout["x0"]
        self.y0 = layout["y0"]
        self.num_w = layout["num_w"]
        self.num_h = layout["num_h"]
        self.zero_w = layout["zero_w"]
        self.zero_h = layout["zero_h"]
        self.dozen_h = layout["dozen_h"]
        self.outer_h = layout["outer_h"]
        self.col_w = layout["col_w"]

        self.zero_x1 = layout["zero_x1"]
        self.zero_x2 = layout["zero_x2"]
        self.grid_x1 = layout["grid_x1"]
        self.grid_x2 = layout["grid_x2"]
        self.col_x1 = layout["col_x1"]
        self.col_x2 = layout["col_x2"]

        self.grid_y1 = self.y0
        self.grid_y2 = self.y0 + 3 * self.num_h

        self.dozen_y1 = self.grid_y2
        self.dozen_y2 = self.dozen_y1 + self.dozen_h
        self.outer_y1 = self.dozen_y2
        self.outer_y2 = self.outer_y1 + self.outer_h

        self.rows = layout["rows"]
        self.number_to_rc = {}
        for r in range(3):
            for c in range(12):
                self.number_to_rc[self.rows[r][c]] = (r, c)

    def cell_bounds(self, row: int, col: int):
        x1 = self.grid_x1 + col * self.num_w
        y1 = self.grid_y1 + row * self.num_h
        return x1, y1, x1 + self.num_w, y1 + self.num_h

    def center_of_cell(self, row: int, col: int):
        x1, y1, x2, y2 = self.cell_bounds(row, col)
        return (x1 + x2) / 2, (y1 + y2) / 2

    def get_number(self, row: int, col: int) -> str:
        return str(self.rows[row][col])

    def column_numbers(self, col: int):
        return [str(self.rows[r][col]) for r in range(3)]

    def doze_numbers(self, idx: int):
        start = idx * 12 + 1
        return [str(n) for n in range(start, start + 12)]

    def column_bet_numbers(self, idx: int):
        col_map = {0: 0, 1: 1, 2: 2}
        c = col_map[idx]
        return self.column_numbers(c)

    def color_bet_numbers(self, bet: str):
        if bet == "Red":
            return [str(n) for n in sorted(RED_NUMBERS)]
        if bet == "Black":
            return [str(n) for n in range(1, 37) if n not in RED_NUMBERS]
        return []

    def odd_even_numbers(self, bet: str):
        if bet == "Odd":
            return [str(n) for n in range(1, 37) if n % 2 == 1]
        if bet == "Even":
            return [str(n) for n in range(1, 37) if n % 2 == 0]
        return []

    def high_low_numbers(self, bet: str):
        if bet == "1-18":
            return [str(n) for n in range(1, 19)]
        if bet == "19-36":
            return [str(n) for n in range(19, 37)]
        return []

    def five_number_numbers(self):
        return ["0", "00", "1", "2", "3"]


class RouletteGameGUI(tk.Frame):
    BETTING_SECONDS = 30  #时间
    TIMER_TICK_MS = 250
    RESULT_SETTLEMENT_DELAY_SECONDS = 1.0
    WHEEL_CENTER_X_OFFSET = 0
    WHEEL_CENTER_Y_OFFSET = 5.0
    LEFT_CONTENT_Y_OFFSET = 5
    DISTRIBUTION_PANEL_WIDTH = 215
    RIGHT_CONTROLS_MIN_WIDTH = 268
    RIGHT_TOP_ROW_HEIGHT = 418
    SUMMARY_CARD_HEIGHT = 92
    # 画布加高 5px，使轮盘与其下方下注区一起下移，保留原版固定窗口。
    WHEEL_CANVAS_HEIGHT = 438 + LEFT_CONTENT_Y_OFFSET
    WHEEL_OUTER_RADIUS = 174.0 * 1.05
    WHEEL_INNER_RADIUS = 70.0 * 1.05
    WHEEL_SECTOR_INNER_RADIUS = 94.0 * 1.05
    BOARD_VISIBLE_HEIGHT = 290
    # 用 1m 等效物理半径把边缘线速度换算为画布角速度；不使用像素当米。
    WHEEL_PHYSICAL_RADIUS_M = 1.0
    INITIAL_SPEED_BASE_M_S = 15.0
    INITIAL_SPEED_VARIATION_M_S = 5.0

    def __init__(self, parent, initial_balance=1_000_000, username="Guest",
                 on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=1150, height=750)
        self.pack_propagate(False)
        self.parent = parent
        self.root = self.winfo_toplevel()
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self._embedded = not bool(getattr(self.root, "_lucky_wheel_standalone", False))
        self._previous_title = self.root.title()
        self._previous_geometry = self.root.geometry()
        self._previous_close_protocol = self.root.protocol("WM_DELETE_WINDOW")
        self.root.title("大六之轮")
        self.root.geometry("1150x750+50+10")
        self.root.resizable(False, False)
        self.root.configure(bg=ROOT_BG)

        self.username = username
        self.balance = float(load_balance(username, float(initial_balance)))
        self.history = RouletteHistory(roulette_log_path())

        self.geometry_model = RouletteBoardGeometry(scale=BOARD_SCALE)
        self.marker_results = []
        self.marker_rows = 6
        self.marker_cols = 20

        self.selected_bet_amount = 100
        self.selected_chip_color = "#ffffff"
        self.selected_chip = None
        self.chip_buttons = []

        self.round_state = "betting"
        self.betting_deadline = None
        self._countdown_job = None
        self._spin_job = None

        self.last_bets = {}
        self.last_bet_colors = {}
        self.timer_paused = False
        self.paused_remaining = 0

        self.current_wheel_offset = (-180.0 / len(ROULETTE_SEQUENCE)) % 360.0
        self.wheel_velocity = 0.0
        self.wheel_acceleration = 0.0
        self._last_physics_time = None
        self.is_spinning = False

        self.pointer_angle = 0.0
        self.pointer_velocity = 0.0
        self.pointer_acceleration = 0.0
        self.is_pointer_spinning = False
        self.flapper = FlapperPhysics()
        self._wheel_unwrapped = self.current_wheel_offset
        self._wheel_physics = None

        self.current_round_result = None
        self.current_round_index = None
        self.center_display_result = None
        self.wheel_timer_id = None

        self.current_bets = {}
        self.current_bet_colors = {}
        self.bet_spots = self._build_bet_spots()
        self.placed_chip_items = {}
        self.result_chip_display = {}
        self._result_flash_job = None
        self._result_flash_state = False
        self._result_flash_spot_ids = set()

        self.distribution_display_count = 50   # 默认分析最近50局
        self.distribution_frame = None         # 分布面板主框架
        self.distribution_labels = {}          # 存储各统计标签的引用

        # 用于存储最后一局的开奖物理数据
        self.last_spin_data = None
        # 结果弹窗防重复
        self.detail_window = None

        # 饼图模式: "sector" 区间分布(1-12/13-24/25-36/0+00) 或 "row" 每行分布
        self.pie_mode = "sector"

        self._build_ui()
        self._sync_marker_from_history()
        self._start_new_round()

        self.focus_force()                         # 确保窗口获得焦点
        self.bind("<Return>", lambda event: self.start_game())
        self.bind("<KP_Enter>", lambda event: self.start_game())

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        main = tk.Frame(self, bg=ROOT_BG)
        main.pack(fill=tk.BOTH, expand=True)

        # 左右整体重新分配宽度，给右侧统计区留更多空间
        left_frame = tk.Frame(main, bg=ROOT_BG, width=650)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=0)
        left_frame.pack_propagate(False)

        right_frame = tk.Frame(main, bg=ROOT_BG, width=492)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=0)
        right_frame.pack_propagate(False)

        self._build_left_side(left_frame)
        self._build_right_side(right_frame)

    def _build_left_side(self, parent):
        top_frame = tk.Frame(parent, bg=ROOT_BG)
        top_frame.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.wheel_canvas = tk.Canvas(
            top_frame,
            width=910,
            height=self.WHEEL_CANVAS_HEIGHT,
            bg=ROOT_BG,
            highlightthickness=0,
            bd=0
        )
        self.wheel_canvas.pack(fill=tk.X)

        betting_area = tk.Frame(parent, bg=ROOT_BG)
        betting_area.pack(fill=tk.BOTH, expand=True, padx=8,
                          pady=(0, 8 - self.LEFT_CONTENT_Y_OFFSET))

        betting_left = tk.Frame(betting_area, bg=ROOT_BG)
        betting_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self._populate_betting_area(betting_left)

    def _populate_betting_area(self, parent):
        self.board_canvas = tk.Canvas(
            parent,
            width=BOARD_W,
            height=self.BOARD_VISIBLE_HEIGHT,
            highlightthickness=0,
            bd=0,
            bg=ROOT_BG
        )
        self.board_canvas.pack(anchor='n')
        draw_roulette_static(self.board_canvas, scale=BOARD_SCALE)

        # 添加帮助按钮
        self._add_help_button_on_board()

        self.board_canvas.bind("<Button-1>", self.on_board_click)
        self.board_canvas.bind("<Button-3>", self.on_board_right_click)

    def _add_help_button_on_board(self):
        """在棋盘上0格子下方、1-18格子左侧添加一个帮助按钮"""
        if not hasattr(self, "board_canvas"):
            return

        # 获取布局参数
        g = self.geometry_model
        # 0格子区域：zero_x1, y0 到 zero_x2, y0 + 2*zero_h
        zero_bottom_y = g.y0 + 2 * g.zero_h   # 0格子的底部Y坐标
        # 外围第一行（1-18）的Y范围
        outer_y1 = g.outer_y1
        # 按钮放置在0格子正下方、且在外围第一行上方（如果空间足够）
        btn_y1 = zero_bottom_y + 5
        btn_y2 = outer_y1 - 5
        if btn_y2 - btn_y1 < 20:
            # 如果空间太小，则放在0格子内部底部
            btn_y1 = zero_bottom_y - 20
            btn_y2 = zero_bottom_y - 2

        # 按钮宽度：与0格子同宽，或更小
        btn_width = (g.zero_x2 - g.zero_x1) - 8
        btn_x1 = g.zero_x1 + 4
        btn_x2 = btn_x1 + btn_width

        # 绘制圆形背景
        cx = (btn_x1 + btn_x2) / 2
        cy = (btn_y1 + btn_y2) / 2
        radius = min((btn_x2 - btn_x1) / 2, (btn_y2 - btn_y1) / 2) * 0.7

        # 先删除旧的帮助按钮（如果有）
        self.board_canvas.delete("help_button")

        # 绘制按钮底圆
        self.board_canvas.create_oval(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            fill="#F5E6B8",
            outline="#D4AF37",
            width=2,
            tags="help_button"
        )
        # 绘制问号文字
        self.board_canvas.create_text(
            cx, cy,
            text="?",
            font=("Arial", int(radius * 1.2), "bold"),
            fill="#2A1B08",
            tags="help_button"
        )

        # 绑定鼠标进入/离开事件，实现手型光标
        self.board_canvas.tag_bind("help_button", "<Enter>", self._on_help_enter)
        self.board_canvas.tag_bind("help_button", "<Leave>", self._on_help_leave)
        
        # 绑定点击事件（使用tag绑定）
        self.board_canvas.tag_bind("help_button", "<Button-1>", lambda e: self.show_game_instructions())
    
    def _on_help_enter(self, event):
        """鼠标进入帮助按钮区域时，将画布光标改为手型"""
        if hasattr(self, "board_canvas"):
            self.board_canvas.config(cursor="hand2")

    def _on_help_leave(self, event):
        """鼠标离开帮助按钮区域时，恢复默认光标"""
        if hasattr(self, "board_canvas"):
            self.board_canvas.config(cursor="")

    def _populate_chips(self, parent):
        panel_bg = "#F2E6C9"
        header_bg = "#D8B46A"

        panel = tk.Frame(parent, bg=ROOT_BG, width=270, height=410)
        panel.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        panel.pack_propagate(False)

        card = tk.Frame(panel, bg=panel_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            card,
            text="筹码",
            font=("Arial", 15, "bold"),
            bg=header_bg,
            fg="#2A1B08",
            pady=8
        ).pack(fill=tk.X)

        chips_frame = tk.Frame(card, bg=panel_bg)
        chips_frame.pack(pady=6, padx=6)

        for i in range(0, len(CHIP_SPECS), 3):
            row_frame = tk.Frame(chips_frame, bg=panel_bg)
            row_frame.pack(pady=2)
            for amount, bg_color, label in CHIP_SPECS[i:i + 3]:
                canvas = self._create_chip_button(row_frame, amount, bg_color, label)
                canvas.pack(side=tk.LEFT, padx=5)

        self.current_chip_label = tk.Label(
            card,
            text="筹码: $100",
            font=("Arial", 14, "bold"),
            bg=panel_bg,
            fg="black"
        )
        self.current_chip_label.pack(pady=(3, 2))

        self.balance_label_side = tk.Label(
            card,
            text=f"余额: ${self.balance:,.2f}",
            font=("Arial", 13, "bold"),
            bg=panel_bg,
            fg="black"
        )
        self.balance_label_side.pack(pady=(0, 10))

        self._set_default_chip()

        btn_frame = tk.Frame(card, bg=panel_bg)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 6))

        # 清除下注按钮
        self.reset_button = tk.Button(
            btn_frame,
            text="清除下注",
            command=self.clear_bets,
            bg="#C94A4A",
            fg="white",
            activebackground="#B73C3C",
            activeforeground="white",
            font=("微软雅黑", 14, "bold"),
            relief=tk.RAISED,      # 3D凸起效果
            bd=3,
            cursor="hand2"
        )
        self.reset_button.pack(side=tk.TOP, fill=tk.X, pady=4)

        # 两个按钮水平排列
        button_row = tk.Frame(btn_frame, bg=panel_bg)
        button_row.pack(fill=tk.X, pady=4)

        # 重复上局下注按钮
        self.repeat_last_btn = tk.Button(
            button_row,
            text="重复上局下注",
            command=self._repeat_last_bet,
            bg="#4A90E2",
            fg="white",
            activebackground="#3A7BC8",
            activeforeground="white",
            font=("微软雅黑", 12, "bold"),
            relief=tk.RAISED,
            bd=3,
            state=tk.DISABLED
        )
        self.repeat_last_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        # 暂停/开始倒计时按钮
        self.pause_timer_btn = tk.Button(
            button_row,
            text="暂停倒计时",
            command=self._toggle_pause_timer,
            bg="#F5A623",
            fg="white",
            activebackground="#E09512",
            activeforeground="white",
            font=("微软雅黑", 12, "bold"),
            relief=tk.RAISED,
            bd=3,
            cursor="hand2"
        )
        self.pause_timer_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0))

        # 开始游戏按钮
        self.deal_button = tk.Button(
            btn_frame,
            text="开始游戏 (Enter)",
            command=self.start_game,
            bg="#D8B46A",
            fg="#2A1B08",
            activebackground="#C8A455",
            activeforeground="#2A1B08",
            font=("微软雅黑", 14, "bold"),
            relief=tk.RAISED,
            bd=3,
            cursor="hand2"
        )
        self.deal_button.pack(side=tk.TOP, fill=tk.X, pady=4)

    def _store_current_bets_as_last(self):
        """
        将当前下注数据存储为“上一局下注”。
        - 只有当前下注非空时，才更新 last_bets 和 last_bet_colors。
        - 如果当前下注为空，则保留原有的 last_bets 不变（不清空）。
        - 最后根据当前余额和保留的 last_bets 更新按钮状态。
        """
        if self.current_bets:
            # 有下注：存储新的记录
            self.last_bets = self.current_bets.copy()
            self.last_bet_colors = self.current_bet_colors.copy()
        else:
            # 没有下注：保持原有 last_bets 不变（不清空）
            pass

        # 根据现有的 last_bets 和余额更新按钮状态
        self._update_repeat_button_state()

    def _update_repeat_button_state(self):
        """
        根据存储的上一局数据和当前余额，更新重复下注按钮的可用性。
        注意：如果当前不在投注阶段，按钮应保持禁用（由 _set_control_buttons_state 控制）。
        """
        if self.round_state != "betting":
            return  # 非投注阶段，按钮已被禁用，无需额外处理
        if not self.last_bets:
            self.repeat_last_btn.config(state=tk.DISABLED)
            return
        total_last = sum(self.last_bets.values())
        if total_last > self.balance:
            self.repeat_last_btn.config(state=tk.DISABLED)
        else:
            self.repeat_last_btn.config(state=tk.NORMAL)

    def _repeat_last_bet(self):
        """重复上一局的下注（复制到当前局）"""
        if self.round_state != "betting":
            messagebox.showwarning("提示", "只能在投注阶段重复上局下注")
            return
        if not self.last_bets:
            messagebox.showwarning("提示", "没有上一局下注记录")
            return

        total_last = sum(self.last_bets.values())
        if total_last > self.balance:
            messagebox.showwarning("提示", f"余额不足，重复上局下注需要 ${total_last:,.0f}")
            return

        # 清除当前下注
        self.clear_bets()

        # 复制上局下注
        for spot_id, amount in self.last_bets.items():
            spot = self._find_spot_by_id(spot_id)
            if not spot:
                continue

            limit = self._bet_limit_for_spot(spot)
            existing = self.current_bets.get(spot_id, 0)
            remaining_limit = limit - existing
            actual_amount = min(amount, remaining_limit)

            if actual_amount <= 0:
                continue
            if self.balance < actual_amount:
                break

            self.balance -= actual_amount
            self.current_bets[spot_id] = existing + actual_amount
            self.current_bet_colors[spot_id] = self._chip_fill_color_for_amount(self.current_bets[spot_id])

        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        total_bet = sum(self.current_bets.values())
        self.current_chip_label.config(text=f"本局下注金额: ${total_bet:,}")

    def _toggle_pause_timer(self):
        """暂停/继续倒计时"""
        if self.round_state != "betting":
            return

        if not self.timer_paused:
            # 暂停倒计时
            if self._countdown_job is not None:
                try:
                    self.after_cancel(self._countdown_job)
                except Exception:
                    pass
                self._countdown_job = None
            # 计算剩余时间
            self.paused_remaining = max(0, self.betting_deadline - time.time())
            self.timer_paused = True
            self.pause_timer_btn.config(text="开始倒计时", bg="#4A90E2")
            # 显示暂停剩余时间
            if hasattr(self, "wheel_timer_id") and self.wheel_timer_id:
                try:
                    self.wheel_canvas.itemconfig(self.wheel_timer_id, text=f"{int(self.paused_remaining)}s (暂停)")
                except Exception:
                    pass
        else:
            # 继续倒计时
            if self.paused_remaining <= 0:
                # 如果剩余时间为0，直接结束下注
                self._lock_bets_and_spin()
                return
            # 重新设置截止时间
            self.betting_deadline = time.time() + self.paused_remaining
            self.timer_paused = False
            self.pause_timer_btn.config(text="暂停倒计时", bg="#F5A623")
            # 重新启动倒计时更新
            self._update_countdown()

    def _create_chip_button(self, parent, amount, bg_color, label):
        size = 54
        canvas = tk.Canvas(
            parent,
            width=size,
            height=size,
            highlightthickness=0,
            bd=0,
            bg="#F2E6C9"
        )
        chip_id = canvas.create_oval(2, 2, size - 2, size - 2, fill=bg_color, outline="", width=0)

        try:
            if ImageColor is not None:
                rgb = ImageColor.getrgb(bg_color)
                luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                text_color = "white" if luminance < 140 else "black"
            else:
                text_color = "black"
        except Exception:
            text_color = "black"

        canvas.create_text(size / 2, size / 2, text=label, fill=text_color, font=("Arial", 13, "bold"))
        canvas.bind("<Button-1>", lambda e, v=amount, c=canvas, cid=chip_id, bg=bg_color: self._set_bet_amount(v, c, cid, bg))
        self.chip_buttons.append({"canvas": canvas, "chip_id": chip_id, "amount": amount, "label": label, "bg_color": bg_color})
        return canvas


    def _set_bet_amount(self, amount, clicked_canvas, clicked_chip_id, bg_color=None):
        for chip in self.chip_buttons:
            chip["canvas"].itemconfig(chip["chip_id"], outline="", width=0)
            chip["canvas"].delete("glow")
        clicked_canvas.itemconfig(clicked_chip_id, outline="yellow", width=4)
        self.selected_chip = next((c for c in self.chip_buttons if c["canvas"] == clicked_canvas), None)
        if bg_color is None and self.selected_chip:
            bg_color = self.selected_chip.get("bg_color", "#ffffff")
        self.selected_chip_color = bg_color or "#ffffff"

        amount = int(amount)
        self.selected_bet_amount = amount
        self.current_chip_label.config(text=f"筹码: ${amount:,}")

    def _set_default_chip(self):
        # 默认选择 100 筹码
        for chip in self.chip_buttons:
            if chip["amount"] == 100:
                chip["canvas"].itemconfig(chip["chip_id"], outline="yellow", width=4)
                self.selected_chip = chip
                self.selected_chip_color = chip.get("bg_color", "#ffffff")
                self.selected_bet_amount = 100
                self.current_chip_label.config(text="筹码: $100")
                break

    # =====================================================
    # Right side: marker road + history proportion + pie chart
    # =====================================================

    def _build_right_side(self, parent):
        # 上排：左侧独立圆饼、右侧筹码；下排：6×20 标记路横跨两栏。
        root = tk.Frame(parent, bg=ROOT_BG)
        root.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(0, weight=0, minsize=self.DISTRIBUTION_PANEL_WIDTH)
        root.grid_columnconfigure(1, weight=1, minsize=self.RIGHT_CONTROLS_MIN_WIDTH)

        pie_frame = tk.Frame(root, bg=ROOT_BG, width=self.DISTRIBUTION_PANEL_WIDTH,
                             height=self.RIGHT_TOP_ROW_HEIGHT)
        pie_frame.grid(row=0, column=0, sticky="nsew")
        pie_frame.pack_propagate(False)
        self._create_pie_chart(pie_frame)

        chip_frame = tk.Frame(root, bg=ROOT_BG, width=self.RIGHT_CONTROLS_MIN_WIDTH,
                              height=self.RIGHT_TOP_ROW_HEIGHT)
        chip_frame.grid(row=0, column=1, sticky="nsew")
        chip_frame.pack_propagate(False)
        self._populate_chips(chip_frame)

        summary_frame = tk.Frame(root, bg=ROOT_BG)
        summary_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._create_summary_cards(summary_frame)

        marker_frame = tk.Frame(root, bg=ROOT_BG)
        marker_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self._create_marker_road(marker_frame)

    def _create_bet_limit_table(self, right_panel):
        """替代最新一局固定指针卡片：标题栏 + 三列两行的下注上限。"""
        values = tuple(f"${self._bet_limit_for_spot({'label': result}):,}"
                       for result in ("1", "12", "👑"))
        card, _ = self._create_summary_table(
            right_panel, "下注上限", ("1 / 3 / 6", "12 / 25", "👑 / 💵"), values,
            panel_bg="#F2E6C9", header_bg="#D8B46A", title_fg="#2A1B08", value_fg="#A88100")
        return card

    def _create_summary_table(self, parent, title, columns, values,
                              panel_bg, header_bg, title_fg, value_fg):
        """两张统计卡共用相同边框、字号、留白和三列两行表格。"""
        card = tk.Frame(parent, bg=panel_bg, bd=1, relief=tk.SOLID)
        card.pack(fill=tk.X, pady=3)
        header = tk.Frame(card, bg=header_bg)
        header.pack(fill=tk.X)
        card.title_label = tk.Label(header, text=title, font=('Arial', 12, 'bold'),
                                    bg=header_bg, fg=title_fg)
        card.title_label.pack(fill=tk.X, pady=3)
        body = tk.Frame(card, bg=panel_bg)
        body.pack(fill=tk.X, padx=8, pady=5)
        table = tk.Frame(body, bg=panel_bg)
        table.pack(fill=tk.X)
        value_labels = []
        for c, column in enumerate(columns):
            tk.Label(table, text=column, font=('Arial', 9, 'bold'), bg=panel_bg,
                     relief=tk.SOLID, borderwidth=1).grid(row=0, column=c, sticky='nsew')
        for c, value in enumerate(values):
            label = tk.Label(table, text=value, font=('Arial', 10, 'bold'), bg=panel_bg,
                             fg=value_fg, relief=tk.SOLID, borderwidth=1)
            label.grid(row=1, column=c, sticky='nsew')
            table.columnconfigure(c, weight=1)
            value_labels.append(label)
        return card, value_labels

    def _create_summary_cards(self, parent):
        """特殊标记与结果分布共用统计局数；右侧显示下注上限。"""
        parent.grid_columnconfigure(0, weight=0, minsize=self.DISTRIBUTION_PANEL_WIDTH)
        parent.grid_columnconfigure(1, weight=1, minsize=self.RIGHT_CONTROLS_MIN_WIDTH)
        special_holder = tk.Frame(parent, bg=ROOT_BG, width=self.DISTRIBUTION_PANEL_WIDTH,
                                  height=self.SUMMARY_CARD_HEIGHT)
        special_holder.grid(row=0, column=0, sticky="nsew")
        special_holder.pack_propagate(False)
        special_card, labels = self._create_summary_table(
            special_holder, f"近{self.distribution_display_count}局特殊标记",
            ("👑", "💵", "合计"), ("--", "--", "--"),
            panel_bg="#EEE5F7", header_bg="#79539C", title_fg="white", value_fg="#6A0DAD")
        self.special_marker_title = special_card.title_label
        self.summary_value_labels = dict(zip(("👑", "💵", "special"), labels))
        limit_holder = tk.Frame(parent, bg=ROOT_BG, width=self.RIGHT_CONTROLS_MIN_WIDTH - 3,
                                height=self.SUMMARY_CARD_HEIGHT)
        limit_holder.grid(row=0, column=1, sticky="nsew", padx=(3, 0))
        limit_holder.pack_propagate(False)
        self._create_bet_limit_table(limit_holder)
        self._update_summary_cards()

    def _update_summary_cards(self):
        if "summary_value_labels" not in self.__dict__:
            return
        display_count = self.distribution_display_count
        self.special_marker_title.config(text=f"近{display_count}局特殊标记")
        recent = [
            entry.get("result", "") for entry in self.history.recent_results2(limit=display_count)
            if entry.get("result", "") in BET_OPTIONS
        ][:display_count]
        counts = {result: recent.count(result) for result in BET_OPTIONS}
        for result in ("👑", "💵"):
            self.summary_value_labels[result].config(text=f"{counts[result]}次")
        special_count = counts["👑"] + counts["💵"]
        self.summary_value_labels["special"].config(text=f"{special_count}次")

    # ---------- 新增饼图相关方法（移植自欧洲版，适配双零） ----------
    def _create_pie_chart(self, parent):
        """创建可切换的饼图：区间分布/每行分布，居中显示，下方动态显示颜色+说明+次数"""
        card_bg = "#F2E6C9"
        header_bg = "#D8B46A"
        title_fg = "#2A1B08"

        outer = tk.Frame(parent, bg=ROOT_BG)
        outer.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        card = tk.Frame(outer, bg=card_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.BOTH, expand=True)

        # 标题栏 - 可点击切换模式
        title_bar = tk.Frame(card, bg=header_bg)
        title_bar.pack(fill=tk.X)

        self.pie_title_btn = tk.Button(
            title_bar,
            text=f"最新{self.distribution_display_count}局的结果分布",
            font=("Arial", 13, "bold"),
            bg=header_bg,
            fg=title_fg,
            activebackground=header_bg,
            activeforeground=title_fg,
            relief=tk.FLAT,
            bd=0,
            padx=2,
            pady=0,
            wraplength=self.DISTRIBUTION_PANEL_WIDTH - 20,
            cursor="hand2",
            command=self._toggle_pie_chart_type
        )
        self.pie_title_btn.pack(fill=tk.X, padx=6, pady=6)

        # 主体内容区
        body = tk.Frame(card, bg=card_bg)
        body.pack(fill=tk.X, padx=6)

        # 饼图容器 - 居中显示
        pie_container = tk.Frame(body, bg=card_bg)
        pie_container.pack(expand=True, fill=tk.BOTH)
        self.pie_canvas = tk.Canvas(
            pie_container,
            width=150,
            height=150,
            bg=card_bg,
            highlightthickness=0,
            bd=0
        )
        self.pie_canvas.pack(anchor=tk.CENTER)

        # 饼图下方统计容器（颜色+说明+次数）
        self.pie_stats_frame = tk.Frame(card, bg=card_bg)
        self.pie_stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 8))

        # 预定义颜色
        self.pie_colors = {
            "sector1": "#5F9F4F",   # 1-12
            "sector2": "#AF4900",   # 13-24
            "sector3": "#4A90E2",   # 25-36
            "zero": TEAL,           # 0/00
            "row1": RED,            # 行1
            "row2": BLACK,          # 行2
            "row3": "#8B4513",      # 行3
        }

    def _toggle_pie_chart_type(self):
        """顺序切换结果分布统计局数：50/100/250/500/1000。"""
        options = [50, 100, 250, 500, 1000]
        current = self.distribution_display_count
        self.distribution_display_count = options[(options.index(current) + 1) % len(options)]
        self._update_pie_chart()
        self._update_summary_cards()

    def _get_sector_data_from_recent(self, limit=50):
        """从 Record2 中获取最近 limit 条结果，统计各区间（1-12,13-24,25-36,0+00）出现的次数"""
        all_results = self.history.recent_results2(limit=2000)
        recent = [entry.get("result", "") for entry in all_results if entry.get("result", "")][:limit]
        counts = {"1-12": 0, "13-24": 0, "25-36": 0, "0/00": 0}
        for res in recent:
            if res == "1": counts["1-12"] += 1
            elif res == "3": counts["13-24"] += 1
            elif res == "6": counts["25-36"] += 1
            elif res in {"12", "25", "👑", "💵"}: counts["0/00"] += 1
        total = sum(counts.values())
        return counts, total

    def _get_row_data_from_recent(self, limit=50):
        """统计最近 limit 条结果中属于 Row1/Row2/Row3/0+00 的次数"""
        row1_set = {1,4,7,10,13,16,19,22,25,28,31,34}
        row2_set = {2,5,8,11,14,17,20,23,26,29,32,35}
        row3_set = {3,6,9,12,15,18,21,24,27,30,33,36}

        all_results = self.history.recent_results2(limit=2000)
        recent = [entry.get("result", "") for entry in all_results if entry.get("result", "")][:limit]
        counts = {"row1": 0, "row2": 0, "row3": 0, "0/00": 0}
        for res in recent:
            if res == "12": counts["row1"] += 1
            elif res == "25": counts["row2"] += 1
            elif res == "👑": counts["row3"] += 1
            elif res == "💵": counts["0/00"] += 1
        total = sum(counts.values())
        return counts, total

    def _update_pie_chart(self):
        """根据当前模式，动态绘制饼图（仅绘制计数>0的扇形），下方显示颜色+说明+次数，0/00始终在最上方且永远显示（即使0次）"""
        if not hasattr(self, "pie_canvas"):
            return

        display_count = self.distribution_display_count
        self.pie_title_btn.config(text=f"最新{display_count}局的结果分布")
        recent = [
            entry.get("result", "") for entry in self.history.recent_results2(limit=2000)
            if entry.get("result", "")
        ][:display_count]
        items = [
            ("1", recent.count("1"), OUTCOME_COLORS["1"]),
            ("3", recent.count("3"), OUTCOME_COLORS["3"]),
            ("6", recent.count("6"), OUTCOME_COLORS["6"]),
            ("12", recent.count("12"), OUTCOME_COLORS["12"]),
            ("25", recent.count("25"), OUTCOME_COLORS["25"]),
            ("👑/💵", recent.count("👑") + recent.count("💵"), OUTCOME_COLORS["👑"]),
        ]
        total = max(1, len(recent))
        self.pie_canvas.delete("all")
        start_angle = 0.0
        for label, count, color in items:
            if count <= 0:
                continue
            angle = 360.0 * count / total
            self.pie_canvas.create_arc(
                10, 10, 140, 140, start=start_angle, extent=angle,
                fill=color, outline="white", width=1.5
            )
            start_angle += angle

        for widget in self.pie_stats_frame.winfo_children():
            widget.destroy()
        headers = ("结果", "次数", "概率")
        for column, header in enumerate(headers):
            self.pie_stats_frame.grid_columnconfigure(column, weight=2 if column == 0 else 1)
            tk.Label(
                self.pie_stats_frame, text=header, bg="#D8B46A", fg="#2A1B08",
                font=("Microsoft YaHei", 12, "bold"), bd=1, relief=tk.SOLID, pady=2
            ).grid(row=0, column=column, sticky="nsew")
        for row in range(len(items) + 1):
            self.pie_stats_frame.grid_rowconfigure(row, weight=1, uniform="result_rows")
        for row_index, (label, count, color) in enumerate(items, start=1):
            percent = count / total * 100 if recent else 0.0
            tk.Label(
                self.pie_stats_frame, text=label, bg=color,
                fg=OUTCOME_TEXT_COLORS.get(label, "white"),
                font=("Segoe UI Emoji", 12, "bold"), bd=1, relief=tk.SOLID, pady=2
            ).grid(row=row_index, column=0, sticky="nsew")
            tk.Label(
                self.pie_stats_frame, text=str(count), bg="#F7ECD3", fg="#1A1A1A",
                font=("Arial", 12, "bold"), bd=1, relief=tk.SOLID, pady=2
            ).grid(row=row_index, column=1, sticky="nsew")
            tk.Label(
                self.pie_stats_frame, text=f"{percent:.1f}%", bg="#F7ECD3", fg="#1A1A1A",
                font=("Arial", 12, "bold"), bd=1, relief=tk.SOLID, pady=2
            ).grid(row=row_index, column=2, sticky="nsew")
        return

        limit = 50
        if self.pie_mode == "sector":
            counts, total = self._get_sector_data_from_recent(limit)
            all_keys = ["1-12", "13-24", "25-36", "0/00"]
            display_names = {"1-12": "1", "13-24": "3", "25-36": "6", "0/00": "12/25/符号"}
            color_keys = {"1-12": "sector1", "13-24": "sector2", "25-36": "sector3", "0/00": "zero"}
        else:
            counts, total = self._get_row_data_from_recent(limit)
            all_keys = ["row1", "row2", "row3", "0/00"]
            display_names = {"row1": "12", "row2": "25", "row3": "👑", "0/00": "💵"}
            color_keys = {"row1": "row1", "row2": "row2", "row3": "row3", "0/00": "zero"}

        if total == 0:
            total = 1

        # 构建用于饼图扇形的有效数据（计数>0）
        valid_for_pie = [(key, counts[key]) for key in all_keys if counts[key] > 0]

        # 构建用于统计显示的数据：包含所有计数>0的分类 + 始终包含0/00（即使计数为0）
        zero_count = counts.get("0/00", 0)
        other_items = [(key, counts[key]) for key in all_keys if key != "0/00" and counts[key] > 0]
        # 始终把0/00放在最前面（即使计数为0）
        valid_for_stats = [("0/00", zero_count)] + other_items

        # 如果没有扇形数据（只有0/00且0次），则清空饼图
        if not valid_for_pie:
            self.pie_canvas.delete("all")
        else:
            # 绘制饼图扇形
            self.pie_canvas.delete("all")
            cx, cy = 75, 75
            radius = 65
            start_angle = 0
            values = [cnt for _, cnt in valid_for_pie]
            angles = [360 * (v / total) for v in values]

            for (key, _), angle in zip(valid_for_pie, angles):
                color = self.pie_colors[color_keys[key]]
                self.pie_canvas.create_arc(
                    cx - radius, cy - radius,
                    cx + radius, cy + radius,
                    start=start_angle,
                    extent=angle,
                    fill=color,
                    outline="white",
                    width=1.5
                )
                # 添加扇区中央文字（短名称）
                mid_angle = start_angle + angle / 2
                rad = math.radians(mid_angle)
                text_r = radius * 0.65
                tx = cx + text_r * math.cos(rad)
                ty = cy - text_r * math.sin(rad)
                if key == "0/00":
                    label = "高倍" if self.pie_mode == "sector" else "💵"
                elif key.startswith("row"):
                    label = key[-1]
                else:
                    label = key
                text_color = "black" if label == "0/00" else "white"
                self.pie_canvas.create_text(tx, ty, text=label, fill=text_color, font=("Arial", 9, "bold"))
                start_angle += angle

        # 更新下方统计信息：颜色 + 说明 + 次数（0/00永远显示）
        for widget in self.pie_stats_frame.winfo_children():
            widget.destroy()

        for key, cnt in valid_for_stats:
            row_frame = tk.Frame(self.pie_stats_frame, bg=self.pie_stats_frame["bg"])
            row_frame.pack(fill=tk.X, pady=2)

            color_block = tk.Canvas(row_frame, width=16, height=16, bg=self.pie_stats_frame["bg"],
                                    highlightthickness=0, bd=0)
            color_block.pack(side=tk.LEFT, padx=(0, 6))
            # 即使次数为0，也显示色块（颜色正常）
            color_block.create_oval(2, 2, 14, 14, fill=self.pie_colors[color_keys[key]], outline="")

            lbl_text = tk.Label(row_frame, text=f"{display_names[key]}: {cnt}次",
                                bg=self.pie_stats_frame["bg"], fg="#1A1A1A",
                                font=("Arial", 10, "bold"), anchor="w")
            lbl_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ---------- 原有统计面板 ----------
    def _create_marker_road(self, parent):
        card_bg = "#F2E6C9"
        header_bg = "#D8B46A"
        title_fg = "#2A1B08"

        outer = tk.Frame(parent, bg=ROOT_BG)
        outer.pack(fill=tk.X, pady=(8, 0))

        card = tk.Frame(outer, bg=card_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.X)

        title_bar = tk.Frame(card, bg=header_bg)
        title_bar.pack(fill=tk.X)

        tk.Label(
            title_bar,
            text="标记路",
            font=("Arial", 15, "bold"),
            bg=header_bg,
            fg=title_fg,
            pady=5
        ).pack()

        content = tk.Frame(card, bg=card_bg)
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 10))

        self.marker_canvas = tk.Canvas(
            content,
            bg=card_bg,
            highlightthickness=0,
            bd=0
        )
        self.marker_canvas.pack(anchor=tk.CENTER)

        self._draw_marker_grid()
        self._update_marker_road()


    def _update_distribution(self):
        """从 Record2 读取最近 N 条结果，更新：
        1) 小/0&00/大
        2) 单/0&00/双
        3) 红/绿/黑
        """
        if "history" not in self.__dict__ or "small_progress" not in self.__dict__:
            return

        all_results = self.history.recent_results2(limit=2000)
        if not all_results:
            return

        n = min(self.distribution_display_count, len(all_results))
        recent = all_results[:n] if n > 0 else []

        # 统计第一组（小/0&00/大）
        small_cnt = big_cnt = zero_cnt = 0
        # 第二组（单/0&00/双）
        odd_cnt = even_cnt = 0   # zero_cnt 共用
        # 第三组（红/绿/黑）
        red_cnt = green_cnt = black_cnt = 0

        for entry in recent:
            result = entry.get("result", "")
            if result in ("0", "00"):
                zero_cnt += 1
                green_cnt += 1      # 绿色（0/00）
            else:
                try:
                    num = int(result)
                    # 第一组
                    if 1 <= num <= 18:
                        small_cnt += 1
                    elif 19 <= num <= 36:
                        big_cnt += 1
                    # 第二组
                    if num % 2 == 1:
                        odd_cnt += 1
                    else:
                        even_cnt += 1
                    # 第三组：红/黑
                    if num in RED_NUMBERS:
                        red_cnt += 1
                    else:
                        black_cnt += 1
                except ValueError:
                    pass

        total = n
        if total == 0:
            return

        # 计算百分比
        small_pct = (small_cnt / total) * 100
        big_pct   = (big_cnt / total) * 100
        zero_pct  = (zero_cnt / total) * 100
        odd_pct   = (odd_cnt / total) * 100
        even_pct  = (even_cnt / total) * 100
        red_pct   = (red_cnt / total) * 100
        green_pct = (green_cnt / total) * 100
        black_pct = (black_cnt / total) * 100

        total_width = 235      # 进度条总宽度
        height = 30
        min_zero_width = 30    # 0/00 最小宽度

        # ========== 第一组：小 / 0&00 / 大 ==========
        small_w = int(total_width * small_pct / 100)
        zero_w  = int(total_width * zero_pct / 100)
        big_w   = total_width - small_w - zero_w

        if zero_cnt > 0 and zero_w < min_zero_width:
            needed = min_zero_width - zero_w
            if big_w >= needed // 2 and small_w >= needed - needed // 2:
                big_w -= needed // 2
                small_w -= needed - (needed // 2)
            elif big_w >= needed:
                big_w -= needed
            elif small_w >= needed:
                small_w -= needed
            else:
                total_available = big_w + small_w
                if total_available > 0:
                    big_w -= int(needed * big_w / total_available)
                    small_w -= needed - int(needed * big_w / total_available)
            zero_w = min_zero_width

        small_w = max(small_w, 8 if small_cnt > 0 else 0)
        big_w   = max(big_w,   8 if big_cnt   > 0 else 0)
        if small_w + zero_w + big_w != total_width:
            diff = total_width - (small_w + zero_w + big_w)
            if diff != 0:
                if big_cnt > 0:
                    big_w += diff
                elif small_cnt > 0:
                    small_w += diff
                else:
                    zero_w += diff

        self.small_progress.place(x=0, y=0, width=small_w, height=height)
        self.zero_progress1.place(x=small_w, y=0, width=zero_w, height=height)
        self.big_progress.place(x=small_w + zero_w, y=0, width=big_w, height=height)

        if self.distribution_display_count in [50, 100]:
            sp_display = f"{int(round(small_pct))}" if small_pct > 0 else "0"
            zp_display = f"{int(round(zero_pct))}" if zero_pct > 0 else "0"
            bp_display = f"{int(round(big_pct))}" if big_pct > 0 else "0"
        else:
            sp_display = f"{small_pct:.1f}"
            zp_display = f"{zero_pct:.1f}"
            bp_display = f"{big_pct:.1f}"
        self.small_progress.config(text=f"{sp_display}%")
        self.zero_progress1.config(text=f"{zp_display}%")
        self.big_progress.config(text=f"{bp_display}%")

        # ========== 第二组：单 / 0&00 / 双 ==========
        odd_w = int(total_width * odd_pct / 100)
        zero_w2 = int(total_width * zero_pct / 100)
        even_w = total_width - odd_w - zero_w2

        if zero_cnt > 0 and zero_w2 < min_zero_width:
            needed = min_zero_width - zero_w2
            if even_w >= needed // 2 and odd_w >= needed - needed // 2:
                even_w -= needed // 2
                odd_w -= needed - (needed // 2)
            elif even_w >= needed:
                even_w -= needed
            elif odd_w >= needed:
                odd_w -= needed
            else:
                total_available = even_w + odd_w
                if total_available > 0:
                    even_w -= int(needed * even_w / total_available)
                    odd_w -= needed - int(needed * even_w / total_available)
            zero_w2 = min_zero_width

        odd_w = max(odd_w, 8 if odd_cnt > 0 else 0)
        even_w = max(even_w, 8 if even_cnt > 0 else 0)
        if odd_w + zero_w2 + even_w != total_width:
            diff = total_width - (odd_w + zero_w2 + even_w)
            if diff != 0:
                if even_cnt > 0:
                    even_w += diff
                elif odd_cnt > 0:
                    odd_w += diff
                else:
                    zero_w2 += diff

        self.odd_progress.place(x=0, y=0, width=odd_w, height=height)
        self.zero_progress2.place(x=odd_w, y=0, width=zero_w2, height=height)
        self.even_progress.place(x=odd_w + zero_w2, y=0, width=even_w, height=height)

        if self.distribution_display_count in [50, 100]:
            op_display = f"{int(round(odd_pct))}" if odd_pct > 0 else "0"
            zp2_display = f"{int(round(zero_pct))}" if zero_pct > 0 else "0"
            ep_display = f"{int(round(even_pct))}" if even_pct > 0 else "0"
        else:
            op_display = f"{odd_pct:.1f}"
            zp2_display = f"{zero_pct:.1f}"
            ep_display = f"{even_pct:.1f}"
        self.odd_progress.config(text=f"{op_display}%")
        self.zero_progress2.config(text=f"{zp2_display}%")
        self.even_progress.config(text=f"{ep_display}%")

        # ========== 第三组：红 / 绿(0/00) / 黑 ==========
        red_w   = int(total_width * red_pct / 100)
        green_w = int(total_width * green_pct / 100)
        black_w = total_width - red_w - green_w

        min_green_width = 30   # 绿色区域最小宽度
        if green_cnt > 0 and green_w < min_green_width:
            needed = min_green_width - green_w
            if black_w >= needed // 2 and red_w >= needed - needed // 2:
                black_w -= needed // 2
                red_w -= needed - (needed // 2)
            elif black_w >= needed:
                black_w -= needed
            elif red_w >= needed:
                red_w -= needed
            else:
                total_available = black_w + red_w
                if total_available > 0:
                    black_w -= int(needed * black_w / total_available)
                    red_w -= needed - int(needed * black_w / total_available)
            green_w = min_green_width

        red_w   = max(red_w,   8 if red_cnt   > 0 else 0)
        black_w = max(black_w, 8 if black_cnt > 0 else 0)
        if red_w + green_w + black_w != total_width:
            diff = total_width - (red_w + green_w + black_w)
            if diff != 0:
                if black_cnt > 0:
                    black_w += diff
                elif red_cnt > 0:
                    red_w += diff
                else:
                    green_w += diff

        self.red_progress.place(x=0, y=0, width=red_w, height=height)
        self.green_progress.place(x=red_w, y=0, width=green_w, height=height)
        self.black_progress.place(x=red_w + green_w, y=0, width=black_w, height=height)

        if self.distribution_display_count in [50, 100]:
            rp_display = f"{int(round(red_pct))}" if red_pct > 0 else "0"
            gp_display = f"{int(round(green_pct))}" if green_pct > 0 else "0"
            bp_display = f"{int(round(black_pct))}" if black_pct > 0 else "0"
        else:
            rp_display = f"{red_pct:.1f}"
            gp_display = f"{green_pct:.1f}"
            bp_display = f"{black_pct:.1f}"
        self.red_progress.config(text=f"{rp_display}%")
        self.green_progress.config(text=f"{gp_display}%")
        self.black_progress.config(text=f"{bp_display}%")


    def _create_distribution_panel(self, parent):
        card_bg = "#F2E6C9"
        header_bg = "#D8B46A"
        title_fg = "#2A1B08"

        outer = tk.Frame(parent, bg=ROOT_BG)
        outer.pack(fill=tk.X, pady=(0, 0))

        card = tk.Frame(outer, bg=card_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.X)

        header = tk.Frame(card, bg=header_bg)
        header.pack(fill=tk.X)

        self.dist_title_btn = tk.Button(
            header,
            text=f"最新{self.distribution_display_count}局的获胜分布",
            font=("Arial", 13, "bold"),
            bg=header_bg,
            fg=title_fg,
            activebackground=header_bg,
            activeforeground=title_fg,
            relief=tk.FLAT,
            bd=0,
            command=self._toggle_distribution_count
        )
        self.dist_title_btn.pack(anchor=tk.CENTER, padx=10, pady=6)

        body = tk.Frame(card, bg=card_bg)
        body.pack(fill=tk.X, padx=10, pady=(8, 10))

        # 第一组：小 / 0&00 / 大
        group1_frame = tk.Frame(body, bg=card_bg)
        group1_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(group1_frame, text="小", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="w").pack(side=tk.LEFT)

        progress_container1 = tk.Frame(group1_frame, bg=card_bg, height=30)
        progress_container1.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        self.small_progress = tk.Label(progress_container1, text="0.0%", bg="#5F9F4F",
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.zero_progress1 = tk.Label(progress_container1, text="0.0%", bg=TEAL,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.big_progress = tk.Label(progress_container1, text="0.0%", bg="#AF4900",
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))

        tk.Label(group1_frame, text="大", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="e").pack(side=tk.RIGHT)

        # 第二组：单 / 0&00 / 双
        group2_frame = tk.Frame(body, bg=card_bg)
        group2_frame.pack(fill=tk.X, pady=(0, 6))

        tk.Label(group2_frame, text="单", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="w").pack(side=tk.LEFT)

        progress_container2 = tk.Frame(group2_frame, bg=card_bg, height=30)
        progress_container2.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        self.odd_progress = tk.Label(progress_container2, text="0.0%", bg="#91FF00",
                                    fg="black", anchor="center", font=("Arial", 10, "bold"))
        self.zero_progress2 = tk.Label(progress_container2, text="0.0%", bg=TEAL,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.even_progress = tk.Label(progress_container2, text="0.0%", bg="#FF6B93",
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))

        tk.Label(group2_frame, text="双", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="e").pack(side=tk.RIGHT)

        # 第三组：红 / 绿 / 黑
        group3_frame = tk.Frame(body, bg=card_bg)
        group3_frame.pack(fill=tk.X, pady=(0, 2))

        tk.Label(group3_frame, text="红", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="w").pack(side=tk.LEFT)

        progress_container3 = tk.Frame(group3_frame, bg=card_bg, height=30)
        progress_container3.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)

        self.red_progress = tk.Label(progress_container3, text="0.0%", bg=RED,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.green_progress = tk.Label(progress_container3, text="0.0%", bg=TEAL,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))
        self.black_progress = tk.Label(progress_container3, text="0.0%", bg=BLACK,
                                    fg="white", anchor="center", font=("Arial", 10, "bold"))

        tk.Label(group3_frame, text="黑", font=("Arial", 10, "bold"),
                bg=card_bg, fg="black", width=2, anchor="e").pack(side=tk.RIGHT)

        self._update_distribution()


    def _toggle_distribution_count(self):
        """循环切换分析局数：50 -> 100 -> 250 -> 500 -> 50"""
        options = [50, 100, 250, 500, 1000, 1500, 2000]
        current_index = options.index(self.distribution_display_count)
        next_index = (current_index + 1) % len(options)
        self.distribution_display_count = options[next_index]
        self.dist_title_btn.config(text=f"最新{self.distribution_display_count}局的获胜分布")
        self._update_distribution()
        self._update_summary_cards()

    def _create_hot_cold_panel(self, parent):
        """最热/最冷数字卡片化，支持循环切换统计局数（500/1000/1500/2000）"""
        card_bg = "#F2E6C9"
        header_bg = "#D8B46A"
        title_fg = "#2A1B08"

        outer = tk.Frame(parent, bg=ROOT_BG)
        outer.pack(fill=tk.X, pady=(0, 0))

        card = tk.Frame(outer, bg=card_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.X)

        header = tk.Frame(card, bg=header_bg)
        header.pack(fill=tk.X)

        # 初始局数（可点击切换）
        self.hot_cold_limit = 500
        self.hot_cold_title_btn = tk.Button(
            header,
            text=f"最新{self.hot_cold_limit}局的最热/最冷数字",
            font=("Arial", 13, "bold"),
            bg=header_bg,
            fg=title_fg,
            activebackground=header_bg,
            activeforeground=title_fg,
            relief=tk.FLAT,
            bd=0,
            command=self._toggle_hot_cold_count
        )
        self.hot_cold_title_btn.pack(anchor=tk.CENTER, padx=10, pady=6)

        content_frame = tk.Frame(card, bg=card_bg)
        content_frame.pack(fill=tk.X, pady=(8, 10))

        def create_table(parent, title, title_color, body_bg):
            outer_card = tk.Frame(parent, bg=body_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
            outer_card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=4)

            tk.Label(
                outer_card,
                text=title,
                font=("微软雅黑", 12, "bold"),
                fg=title_color,
                bg=body_bg
            ).pack(pady=(5, 3))

            rows = []
            for _ in range(6):
                row_frame = tk.Frame(outer_card, bg=body_bg, height=42)
                row_frame.pack(fill=tk.X, padx=6, pady=0)
                row_frame.pack_propagate(False)

                canvas = tk.Canvas(
                    row_frame,
                    width=36,
                    height=36,
                    bg=body_bg,
                    highlightthickness=0,
                    bd=0
                )
                canvas.pack(side=tk.LEFT, padx=(2, 0))

                count_label = tk.Label(
                    row_frame,
                    text="",
                    font=("Arial", 18, "bold"),
                    bg=body_bg,
                    fg="#333333",
                    width=4,
                    relief=tk.FLAT
                )
                count_label.pack(side=tk.RIGHT, padx=(0, 4))

                rows.append((canvas, count_label))

            return rows

        self.hot_canvases = create_table(content_frame, "🔥 最热数字", "#E67E22", "#FFF7EE")
        self.cold_canvases = create_table(content_frame, "❄ 最冷数字", "#3498DB", "#EEF7FF")

        self._update_hot_cold_display()   # 初始绘制

    def _toggle_hot_cold_count(self):
        """循环切换统计局数：500 -> 1000 -> 1500 -> 2000 -> 500"""
        options = [500, 1000, 1500, 2000]
        current_index = options.index(self.hot_cold_limit)
        next_index = (current_index + 1) % len(options)
        self.hot_cold_limit = options[next_index]
        self.hot_cold_title_btn.config(text=f"最新{self.hot_cold_limit}局的最热/最冷数字")
        self._update_hot_cold_display()

    def _update_hot_cold_display(self):
        """根据 self.hot_cold_limit 从历史中取最近 N 条结果，更新热冷数字"""
        if "history" not in self.__dict__ or "hot_canvases" not in self.__dict__:
            return

        # 获取足够多的历史（从 Record2 中取，最多 2000 条）
        all_results = self.history.recent_results2(limit=2000)
        # 只取最近 self.hot_cold_limit 条
        results = [
            entry.get("result", "")
            for entry in all_results
            if entry.get("result", "")
        ][:self.hot_cold_limit]

        # 统计
        all_numbers = list(BET_OPTIONS)
        counts = {num: 0 for num in all_numbers}
        for res in results:
            if res in counts:
                counts[res] += 1

        # 最热（按次数降序，同次数按数字升序）
        hot_items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:6]
        # 最冷（按次数升序，同次数按数字升序）取前6再反转
        cold_items = sorted(counts.items(), key=lambda x: (x[1], x[0]))[:6][::-1]

        def draw_ball(canvas, number, color):
            canvas.delete("all")
            canvas.create_oval(3, 4, 33, 34, fill="#999999", outline="")
            canvas.create_oval(2, 2, 32, 32, fill=color, outline="#111111", width=1)
            canvas.create_text(17, 17, text=number, fill="white", font=("Arial", 12, "bold"))

        def update_group(items, widgets, row_bg):
            for i, (num, cnt) in enumerate(items):
                canvas, count_lbl = widgets[i]
                ball_color = OUTCOME_COLORS.get(num, TEAL)
                draw_ball(canvas, num, ball_color)
                count_lbl.config(text=str(cnt), bg=row_bg, fg="#222222")
            # 清空多余行
            for i in range(len(items), len(widgets)):
                canvas, count_lbl = widgets[i]
                canvas.delete("all")
                count_lbl.config(text="", bg=canvas["bg"])

        update_group(hot_items, self.hot_canvases, "#FFF7EE")
        update_group(cold_items, self.cold_canvases, "#EEF7FF")

    def _draw_marker_grid(self):
        self.marker_canvas.delete("all")

        rows = self.marker_rows
        cols = self.marker_cols
        cell_size = 23

        width = cols * cell_size + 2
        height = rows * cell_size + 2

        self.marker_canvas.config(
            width=width,
            height=height,
            scrollregion=(0, 0, width, height)
        )

        for col in range(cols):
            for row in range(rows):
                x1 = col * cell_size
                y1 = row * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size

                self.marker_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline="#7B6441",
                    fill="#F7ECD3",
                    width=1
                )

    def _update_marker_road(self):
        self._draw_marker_grid()
        rows, cols = self.marker_rows, self.marker_cols
        cell_size = 23
        max_display = rows * cols
        start_idx = max(0, len(self.marker_results) - max_display)
        results_to_show = self.marker_results[start_idx:]

        for idx, entry in enumerate(results_to_show):
            if idx >= max_display:
                break
            result = entry["result"]
            fill = OUTCOME_COLORS.get(result, TEAL)
            text_fill = OUTCOME_TEXT_COLORS.get(result, "white")

            col = idx // rows
            row = idx % rows
            x1 = col * cell_size
            y1 = row * cell_size
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            radius = cell_size * 0.40

            self.marker_canvas.create_oval(
                cx - radius, cy - radius,
                cx + radius, cy + radius,
                fill=fill,
                outline="#000000",
                width=2,
                tags="dot"
            )
            font = ("Segoe UI Emoji", 9, "bold") if result in {"👑", "💵"} else ("Arial", 9, "bold")
            self.marker_canvas.create_text(
                cx, cy,
                text=result,
                fill=text_fill,
                font=font,
                tags="dot"
            )

    def _sync_marker_from_history(self):
        raw_hist = self.history.recent_results(limit=120)
        reversed_hist = [entry for entry in reversed(raw_hist) if entry["result"]]
        self.marker_results = reversed_hist
        self._update_marker_road()
        self._update_pie_chart()
        self._update_summary_cards()

    def add_marker_result(self, result):
        self._sync_marker_from_history()

    # =====================================================
    # Wheel drawing / fixed mechanical flapper
    # =====================================================
    def _wheel_geometry(self):
        """绘制与中心点击共同使用的轮盘尺寸；为支架与金属外圈预留空间。"""
        width = self.wheel_canvas.winfo_width()
        height = self.wheel_canvas.winfo_height()
        outer_r = max(80.0, min(self.WHEEL_OUTER_RADIUS, width / 2.0 - 32.0,
                                height / 2.0 - 35.0))
        cx = width / 2.0 + self.WHEEL_CENTER_X_OFFSET
        cy = height / 2.0 + self.WHEEL_CENTER_Y_OFFSET + self.LEFT_CONTENT_Y_OFFSET / 2.0
        # 中央圆盘与扇区内边缘分别控制，缩短扇区不会放大中央圆盘。
        inner_r = outer_r * (self.WHEEL_INNER_RADIUS / self.WHEEL_OUTER_RADIUS)
        return cx, cy, outer_r, inner_r

    def _draw_wheel(self):
        # 强制处理 pending 的布局事件，确保能获取到正确的画布尺寸
        self.update_idletasks()

        canvas_w = max(int(self.wheel_canvas.winfo_width()), 1)
        canvas_h = max(int(self.wheel_canvas.winfo_height()), 1)

        # 如果画布尺寸过小（通常窗口尚未完全映射），延迟重试
        if canvas_w <= 10 or canvas_h <= 10:
            self.after(50, self._draw_wheel)
            return

        self.wheel_canvas.delete("all")

        # ===== 背景：赌场风格深色舞台 + 轻微渐层感 =====
        self.wheel_canvas.create_rectangle(
            0, 0, canvas_w, canvas_h,
            fill=ROOT_BG,
            outline="",
            tags=("wheel_bg",)
        )

        # 轻微装饰光圈
        cx, cy, outer_r, inner_r = self._wheel_geometry()
        wheel_scale = outer_r / 174.0

        for r, fill, width in [
            (outer_r + 46, "#173F66", 2),
            (outer_r + 31, "#0E241E", 2),
        ]:
            self.wheel_canvas.create_oval(
                cx - r, cy - r,
                cx + r, cy + r,
                fill="",
                outline=fill,
                width=width,
                tags=("wheel_bg",)
            )

        # 外围金属底座
        self.wheel_canvas.create_oval(
            cx - outer_r - 28, cy - outer_r - 28,
            cx + outer_r + 28, cy + outer_r + 28,
            fill="#2D2214",
            outline="#D4AF37",
            width=6,
            tags=("wheel",)
        )
        self.wheel_canvas.create_oval(
            cx - outer_r - 18, cy - outer_r - 18,
            cx + outer_r + 18, cy + outer_r + 18,
            fill="",
            outline="#8B6B24",
            width=2,
            tags=("wheel",)
        )

        # 轮盘转盘阴影层
        self.wheel_canvas.create_oval(
            cx - outer_r - 8, cy - outer_r - 8,
            cx + outer_r + 8, cy + outer_r + 8,
            fill="#1A1A1A",
            outline="",
            tags=("wheel",)
        )

        # 轮盘扇区
        sector_inner_r = outer_r * (self.WHEEL_SECTOR_INNER_RADIUS / self.WHEEL_OUTER_RADIUS)
        self._draw_wheel_segments(cx, cy, outer_r, sector_inner_r, self.current_wheel_offset)

        # 轮盘外圈细金边
        self.wheel_canvas.create_oval(
            cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r,
            outline="#E6C15A",
            width=3,
            tags=("wheel",)
        )
        self.wheel_canvas.create_oval(
            cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r,
            outline="#E6C15A",
            width=2,
            tags=("wheel",)
        )

        # 54 枚分隔销钉随转盘一起移动，顶部支架保持固定。
        draw_wheel_pins(self.wheel_canvas, cx, cy, outer_r, self.current_wheel_offset)

        # 中心金属盘
        self.wheel_canvas.create_oval(
            cx - inner_r - 15, cy - inner_r - 15,
            cx + inner_r + 15, cy + inner_r + 15,
            fill="#6B4D1B",
            outline="#E6C15A",
            width=3,
            tags=("wheel",)
        )
        self.wheel_canvas.create_oval(
            cx - inner_r - 7, cy - inner_r - 7,
            cx + inner_r + 7, cy + inner_r + 7,
            fill="#F3E8C9",
            outline="#1A1A1A",
            width=2,
            tags=("wheel",)
        )

        # 中心显示
        if self.center_display_result is not None:
            result = self.center_display_result
            bg_color = OUTCOME_COLORS.get(result, "#FFFFFF")
            inner_bg_r = inner_r - 10
            self.wheel_canvas.create_oval(
                cx - inner_bg_r, cy - inner_bg_r,
                cx + inner_bg_r, cy + inner_bg_r,
                fill=bg_color,
                outline="#111111",
                width=2,
                tags=("wheel",)
            )
            font_size = int(round((34 if len(result) == 2 else 36) * wheel_scale))
            font = ("Segoe UI Emoji", font_size, "bold") if result in {"👑", "💵"} else ("Arial", font_size, "bold")
            self.wheel_canvas.create_text(
                cx, cy,
                text=result,
                fill=OUTCOME_TEXT_COLORS.get(result, "white"),
                font=font,
                tags=("wheel",)
            )
        else:
            self.wheel_canvas.create_text(
                cx, cy - 10,
                text="大六之轮",
                font=("Arial", int(round(24 * wheel_scale)), "bold"),
                fill="#2A1B08",
                tags=("wheel",)
            )

            if self.round_state == "betting" and self.betting_deadline is not None:
                remaining = max(0, int(math.ceil(self.betting_deadline - time.time())))
                timer_text = f"{remaining:02d}s"
            elif self.round_state == "spinning":
                timer_text = "开奖中"
            else:
                timer_text = "等待开奖"

            self.wheel_timer_id = self.wheel_canvas.create_text(
                cx, cy + 28 * wheel_scale,
                text=timer_text,
                font=("Arial", int(round(16 * wheel_scale)), "bold"),
                fill="#2A1B08",
                tags=("timer",)
            )

        self._draw_fixed_flapper(cx, cy, outer_r)

    def _draw_wheel_segments(self, cx, cy, outer_r, inner_r, offset_deg):
        self.wheel_canvas.delete("wheel_segments")

        n = len(ROULETTE_SEQUENCE)
        step = 360.0 / n

        # 先画一层底色，避免扇区之间露出空隙
        self.wheel_canvas.create_oval(
            cx - outer_r, cy - outer_r,
            cx + outer_r, cy + outer_r,
            fill="#1A1A1A",
            outline="",
            tags=("wheel_segments",)
        )

        for i, symbol in enumerate(ROULETTE_SEQUENCE):
            start = (offset_deg + i * step) % 360.0
            end = start + step

            # 环形扇区只占用缩短后的径向长度，内侧留出独立中央圆盘空间。
            points = []
            for radius, ang in ((inner_r, start), (outer_r, start),
                                (outer_r, end), (inner_r, end)):
                rad = math.radians(ang)
                x = cx + radius * math.sin(rad)
                y = cy - radius * math.cos(rad)
                points.extend([x, y])

            fill_color = OUTCOME_COLORS[symbol]
            outline_color = "#2A2A2A"

            self.wheel_canvas.create_polygon(
                points,
                fill=fill_color,
                outline=outline_color,
                width=1,
                smooth=False,
                tags=("wheel_segments",)
            )

            # 扇区高光线，增加层次感
            rad1 = math.radians(start)
            x1 = cx + inner_r * math.sin(rad1)
            y1 = cy - inner_r * math.cos(rad1)
            x2 = cx + outer_r * math.sin(rad1)
            y2 = cy - outer_r * math.cos(rad1)
            self.wheel_canvas.create_line(
                x1, y1, x2, y2,
                fill="#F6F1D0",
                width=1,
                tags=("wheel_segments",)
            )

            # 号码文字
            mid = (start + end) / 2.0
            rad = math.radians(mid)
            text_r = outer_r * 0.83
            tx = cx + text_r * math.sin(rad)
            ty = cy - text_r * math.cos(rad)

            # 54 格较窄，数字适度放大，保留两位数之间的间距。
            font_size = max(11, min(13, int(round(11 * outer_r / 174.0))))
            text_font = ("Segoe UI Emoji", font_size, "bold") if symbol in {"👑", "💵"} else ("Arial", font_size, "bold")
            text_fill = OUTCOME_TEXT_COLORS[symbol]

            # 轻微文字阴影
            self.wheel_canvas.create_text(
                tx + 1, ty + 1,
                text=symbol,
                font=text_font,
                fill="#000000",
                tags=("wheel_segments",)
            )
            self.wheel_canvas.create_text(
                tx, ty,
                text=symbol,
                font=text_font,
                fill=text_fill,
                tags=("wheel_segments",)
            )

        # 最内圈边界
        self.wheel_canvas.create_oval(
            cx - inner_r, cy - inner_r,
            cx + inner_r, cy + inner_r,
            outline="#F3E8C9",
            width=2,
            tags=("wheel_segments",)
        )

        # 外圈边界
        self.wheel_canvas.create_oval(
            cx - outer_r, cy - outer_r,
            cx + outer_r, cy + outer_r,
            outline="#F3E8C9",
            width=2,
            tags=("wheel_segments",)
        )

        # 让轮盘层在最上面
        self.wheel_canvas.tag_raise("wheel_segments")

    # =====================================================
    # Bet spots / hit testing / centered chips
    # =====================================================

    def _build_bet_spots(self):
        g = self.geometry_model
        spots = []

        def add_spot(spot_id, spot_type, label, numbers, payout, bounds, center, kind="point", extra=None):
            payload = {
                "id": spot_id,
                "type": spot_type,
                "label": label,
                "numbers": set(numbers),
                "payout": payout,
                "kind": kind,
                "bounds": bounds,
                "center": center,
            }
            if extra:
                payload.update(extra)
            spots.append(payload)

        # 大六之轮只有七种单项下注。继续使用原来的 spot/chip/click/flash 体系。
        for result, bounds in lucky_board_bounds().items():
            x1, y1, x2, y2 = bounds
            add_spot(
                f"straight_{result}", "straight", result, {result},
                lucky_net_odds(result), bounds,
                ((x1 + x2) / 2, (y1 + y2) / 2), kind="cell"
            )
        return spots

    def _spot_numbers(self, spot):
        return set(spot.get("numbers", set()))

    def _chip_fill_color_for_amount(self, amount: int) -> str:
        try:
            amt = int(amount)
        except Exception:
            amt = 0

        selected = CHIP_SPECS[0][1]
        for value, color, _label in CHIP_SPECS:
            if amt >= value:
                selected = color
        return selected

    def _bet_limit_for_spot(self, spot):
        result = str(spot.get("label", ""))
        if result in {"1", "3", "6"}:
            return 500_000
        if result in {"12", "25"}:
            return 300_000
        return 100_000
    
    def _format_win_amount(self, value):
        value = int(value)

        if value < 1000:
            return str(value)

        k = value / 1000

        if value % 1000 == 0:
            return f"{int(k)}K"

        if value % 100 == 0:
            return f"{k:.1f}K"

        return f"{k:.1f}K+"

    def _result_chip_style(self, amount):
        amount = int(amount)
        fill = self._chip_fill_color_for_amount(amount)
        return fill, self._spot_text_color(fill)

    def _find_spot_by_id(self, spot_id: str):
        for spot in self.bet_spots:
            if spot["id"] == spot_id:
                return spot
        return None

    def _spot_by_point(self, x: float, y: float):
        def inside(bounds):
            x1, y1, x2, y2 = bounds
            return x1 <= x <= x2 and y1 <= y <= y2

        # 优先匹配更精确的非直注区域
        priority = {
            "street": 0,
            "six_line": 1,
            "corner": 2,
            "split": 3,
            "five_number": 4,
            "dozen": 5,
            "column": 6,
            "color": 7,
            "odd_even": 8,
            "high_low": 9,
        }

        matches = []
        for idx, spot in enumerate(self.bet_spots):
            bounds = spot.get("bounds")
            if not bounds or not inside(bounds):
                continue

            x1, y1, x2, y2 = bounds
            area = max(0.0, float(x2 - x1)) * max(0.0, float(y2 - y1))
            spot_type = spot.get("type", "")
            matches.append((priority.get(spot_type, 99), area, idx, spot))

        if not matches:
            return None

        matches.sort(key=lambda item: (item[0], item[1], item[2]))
        return matches[0][3]

    def _spot_display_label(self, spot):
        if spot["type"] == "straight":
            return spot["label"]
        return spot["label"]

    def _spot_text_color(self, fill_color):
        try:
            if ImageColor is not None:
                rgb = ImageColor.getrgb(fill_color)
                luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                return "white" if luminance < 140 else "black"
        except Exception:
            pass
        return "black"

    def _chip_radius_for_spot(self, spot):
        """
        内围投注统一筹码大小
        外围投注统一筹码大小
        """

        # 当前 52px 直径缩小三分之一。
        if spot["type"] == "straight":
            return 26 * (2 / 3)

        # 内围投注
        if spot["type"] in (
            "straight", "split", "corner", "street", "six_line", "five_number",
        ):
            return 13

        # 外围投注
        if spot["type"] in (
            "dozen",
            "column",
            "color",
            "odd_even",
            "high_low",
        ):
            return 14

        return 14

    def _draw_placed_chips(self):
        if not hasattr(self, "board_canvas"):
            return

        self.board_canvas.delete("chips")
        for spot_id, amount in self.current_bets.items():
            if amount <= 0:
                continue
            spot = self._find_spot_by_id(spot_id)
            if not spot:
                continue
            fill = self.current_bet_colors.get(spot_id, self._chip_fill_color_for_amount(amount))
            self._draw_chip_on_spot(spot, amount, fill)

    def _draw_chip_on_spot(self, spot, amount, fill=None):
        cx, cy = spot["center"]
        radius = self._chip_radius_for_spot(spot)

        spot_id = spot["id"]
        base_fill = fill or self._chip_fill_color_for_amount(amount)
        base_text_color = self._spot_text_color(base_fill)
        display_amount = int(amount)
        display_fill = base_fill
        display_text_color = base_text_color

        # 开奖后的中奖筹码：原色/派奖色 轮流显示
        if self.round_state == "result" and spot_id in self.result_chip_display:
            info = self.result_chip_display[spot_id]
            if self._result_flash_state:
                display_amount = int(info["win_amount"])
                display_fill = info["win_fill"]
                display_text_color = info["win_text_color"]
            else:
                display_amount = int(info["original_amount"])
                display_fill = info["original_fill"]
                display_text_color = info["original_text_color"]

        if spot["type"] == "straight":
            offset_list = [(0, 0)]
        elif spot["type"] in ("split", "corner", "street"):
            offset_list = [(0, 0), (10, 0), (-10, 0), (0, 10), (0, -10)]
        elif spot["type"] == "six_line":
            offset_list = [(0, 0), (10, 0), (-10, 0)]
        else:
            offset_list = [(0, 0)]

        existing_count = sum(
            1 for key in self.placed_chip_items
            if key.startswith(spot_id + "_")
        )
        ox, oy = offset_list[min(existing_count, len(offset_list) - 1)]

        center_x = int(round(cx + ox))
        center_y = int(round(cy + oy))

        cid = self.board_canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            fill=display_fill,
            outline="#d4af37",
            width=2,
            tags=("chips",)
        )

        amount_text = self._format_win_amount(display_amount)
        amount_font_size = 7
        if spot["type"] == "straight":
            amount_font_size = 10 if len(amount_text) <= 3 else max(6, 36 // len(amount_text))
        txt = self.board_canvas.create_text(
            center_x,
            center_y,
            text=amount_text,
            fill=display_text_color,
            font=("Arial", amount_font_size, "bold"),
            tags=("chips",)
        )

        self.placed_chip_items[f"{spot_id}_{existing_count}"] = (cid, txt)

    def _remove_chip_items(self, spot_id):
        keys = [k for k in self.placed_chip_items if k.startswith(spot_id + "_")]
        for key in keys:
            items = self.placed_chip_items.pop(key, None)
            if items:
                for item in items:
                    try:
                        self.board_canvas.delete(item)
                    except Exception:
                        pass

    def _repaint_all_chips(self):
        if not hasattr(self, "board_canvas"):
            return
        self.board_canvas.delete("chips")
        self.placed_chip_items = {}
        for spot_id, amount in self.current_bets.items():
            if amount > 0:
                spot = self._find_spot_by_id(spot_id)
                if spot:
                    fill = self.current_bet_colors.get(spot_id, self._chip_fill_color_for_amount(amount))
                    self._draw_chip_on_spot(spot, amount, fill)

    # =====================================================
    # Board click handling
    # =====================================================

    def on_board_click(self, event):
        if self.round_state != "betting":
            return
        spot = self._spot_by_point(event.x, event.y)
        if not spot:
            return
        self.place_bet(spot["id"])

    def on_board_right_click(self, event):
        if self.round_state != "betting":
            return
        spot = self._spot_by_point(event.x, event.y)
        if not spot:
            return
        self.clear_single_bet(spot["id"])

    # =====================================================
    # Betting / settlement
    # =====================================================

    def place_bet(self, spot_id: str):
        if self.round_state != "betting":
            return
        spot = self._find_spot_by_id(spot_id)
        if not spot:
            return

        amount = int(self.selected_bet_amount)
        if amount <= 0:
            return

        limit = self._bet_limit_for_spot(spot)
        existing = self.current_bets.get(spot_id, 0)
        remaining_limit = limit - existing
        if remaining_limit <= 0:
            messagebox.showwarning("投注上限", f"{spot['label']} 已达到最高限红 ${limit:,}")
            return

        actual_amount = min(amount, remaining_limit)
        if self.balance < actual_amount:
            messagebox.showwarning("余额不足", f"余额不足，无法下注 ${actual_amount:,.0f}。")
            return

        self.balance -= actual_amount
        self.current_bets[spot_id] = existing + actual_amount
        self.current_bet_colors[spot_id] = self._chip_fill_color_for_amount(self.current_bets[spot_id])

        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        total_bet = sum(self.current_bets.values())
        self.current_chip_label.config(text=f"本局下注金额: ${total_bet:,}")

    def clear_bets(self):
        """清除当前所有下注，并退还金额"""
        if self.round_state != "betting":
            return

        refund = sum(self.current_bets.values())

        if refund > 0:
            self.balance += refund

        self.current_bets.clear()
        self.current_bet_colors.clear()

        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        self.current_chip_label.config(
            text=f"上局获胜金额: ${int(getattr(self, 'last_win_amount', 0)):,}"
        )

    def clear_single_bet(self, spot_id: str):
        if self.round_state != "betting":
            return
        amount = self.current_bets.get(spot_id, 0)
        if amount > 0:
            self.balance += amount
            self.current_bets.pop(spot_id, None)
            self.current_bet_colors.pop(spot_id, None)
            self._refresh_balance_display()
            self._refresh_bet_totals()
            self._repaint_all_chips()

    def _refresh_bet_totals(self):
        total_bet = sum(self.current_bets.values())
        if hasattr(self, "current_bet_label"):
            self.current_bet_label.config(text=f"${total_bet:,}")

    def _settle_bets(self, result: str) -> float:
        total_payout = 0.0

        for spot_id, amount in list(self.current_bets.items()):
            spot = self._find_spot_by_id(spot_id)
            if not spot or amount <= 0:
                continue

            if result in spot["numbers"]:
                multiplier = spot["payout"] + 1
                win_amount = amount * multiplier
                total_payout += win_amount
                self.balance += win_amount

        if self.username != "Guest":
            update_balance_in_json(self.username, self.balance)

        self.last_win_amount = int(total_payout)

        self.current_chip_label.config(
            text=f"本局获胜金额: ${self.last_win_amount:,}"
        )
        return total_payout

    # =====================================================
    # Game flow
    # =====================================================
    def _start_new_round(self):
        # 新局不能中断上一局尚未结束的回落或余振动画。
        if self.is_spinning and self.round_state == "result":
            self.after(100, self._start_new_round)
            return
        # 重新添加帮助按钮（因为上面delete了all）
        self._add_help_button_on_board()

        # 清除上一局的数据，避免在新局点击依然弹出旧数据
        self.last_spin_data = None
        self._stop_result_flash()

        # 重置暂停相关标志
        self.timer_paused = False
        self.paused_remaining = 0
        if hasattr(self, "pause_timer_btn"):
            self.pause_timer_btn.config(text="暂停倒计时", bg="#F5A623")

        self.result_chip_display = {}
        self.current_bets = {}
        self.current_bet_colors = {}
        self.center_display_result = None

        if self._countdown_job is not None:
            try:
                self.after_cancel(self._countdown_job)
            except Exception:
                pass
            self._countdown_job = None

        if self._spin_job is not None:
            try:
                self.after_cancel(self._spin_job)
            except Exception:
                pass
            self._spin_job = None

        self.round_state = "betting"
        self.current_round_result = None
        self.current_round_index = None

        # 支点一直在顶部；新一局仅重置拨片的弹性偏转与回弹速度。
        self.pointer_angle = 0.0
        self.pointer_velocity = 0.0
        self.pointer_acceleration = 0.0
        self.is_pointer_spinning = False
        self.flapper.reset()
        self.is_spinning = False
        self._wheel_unwrapped = self.current_wheel_offset

        self._enable_amount_buttons()
        self._set_control_buttons_state(tk.NORMAL)
        self._set_bet_buttons_state(tk.NORMAL)

        self._refresh_bet_totals()

        self._draw_wheel()
        self._repaint_all_chips()

        self.betting_deadline = time.time() + self.BETTING_SECONDS
        self._update_countdown()
        
    def _update_countdown(self):
        if self.timer_paused:
            # 暂停时不更新倒计时，也不自动结束
            return

        remaining = int(math.ceil(self.betting_deadline - time.time()))
        if remaining < 0:
            remaining = 0

        if hasattr(self, "wheel_timer_id") and self.wheel_timer_id:
            try:
                self.wheel_canvas.itemconfig(self.wheel_timer_id, text=f"{remaining:02d}s")
            except Exception:
                pass

        if remaining <= 0:
            self._countdown_job = None
            self._lock_bets_and_spin()
            return

        self._countdown_job = self.after(self.TIMER_TICK_MS, self._update_countdown)

    def _lock_bets_and_spin(self):
        # 如果弹窗还开着，关掉它（可选）
        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.destroy()
            self.detail_window = None
        # 存储当前下注数据作为上一局记录（若无下注则保留旧记录）
        self._store_current_bets_as_last()

        # 重置暂停相关状态
        self.timer_paused = False
        self.paused_remaining = 0
        self.pause_timer_btn.config(text="暂停倒计时", bg="#F5A623")

        self.round_state = "spinning"
        self._set_bet_buttons_state(tk.DISABLED)
        self._disable_amount_buttons()
        self._set_control_buttons_state(tk.DISABLED)   # 禁用所有游戏按钮
        self._start_physical_spin()

    def _start_physical_spin(self):
        # 初速在基准 ±5m/s 内波动；左 / 右来向由 JSON 保存并逐局交替。
        self.initial_wheel_speed_m_s = uuid_uniform(
            self.INITIAL_SPEED_BASE_M_S - self.INITIAL_SPEED_VARIATION_M_S,
            self.INITIAL_SPEED_BASE_M_S + self.INITIAL_SPEED_VARIATION_M_S)
        self.wheel_direction = self.history.begin_wheel_spin(self.initial_wheel_speed_m_s)
        self._result_resolved = False
        self.wheel_velocity = self.wheel_direction * math.degrees(
            self.initial_wheel_speed_m_s / self.WHEEL_PHYSICAL_RADIUS_M)

        self.pointer_angle = 0.0
        self.pointer_velocity = 0.0
        self.pointer_acceleration = 0.0
        self.is_pointer_spinning = False
        self.flapper.reset()

        self._wheel_unwrapped = self.current_wheel_offset % 360.0
        self._wheel_physics = WheelPhysics(
            self._wheel_unwrapped, self.wheel_velocity, self.flapper,
            bearing=uuid_uniform(18.0, 25.0),
            viscous=uuid_uniform(0.055, 0.09),
            air_drag=uuid_uniform(0.00013, 0.00020),
            pin_energy=uuid_uniform(35.0, 65.0),
        )
        self.wheel_acceleration = self._wheel_physics.acceleration

        self.is_spinning = True
        self._last_physics_time = time.monotonic()
        self._physics_update()

    def _physics_update(self):
        if not self.is_spinning:
            return
        self._spin_job = None
        now = time.monotonic()
        dt = max(0.0, now - self._last_physics_time)
        self._last_physics_time = now

        # 使用完整真实经过时间，在模型内部进行 1ms 子步积分，卡顿时不丢弃时间。
        self._wheel_physics.advance(dt)
        self._wheel_unwrapped = self._wheel_physics.angle
        self.current_wheel_offset = self._wheel_unwrapped % 360.0
        self.wheel_velocity = self._wheel_physics.velocity
        self.wheel_acceleration = self._wheel_physics.acceleration
        self.pointer_angle = 0.0

        self._draw_wheel()

        # 确定无法越过相邻销钉满 1 秒即派彩，随后继续播放剩余物理运动。
        self._resolve_spin_result()
        if self._result_resolved and self.last_spin_data is not None:
            self.last_spin_data.update(
                wheel_offset=self.current_wheel_offset,
                flapper_angle=self.flapper.display_angle,
                flapper_clicks=self.flapper.clicks)
        if self._result_resolved and self._wheel_physics.at_rest and self.flapper.settled:
            self._finish_physical_spin()
            return

        self._spin_job = self.after(16, self._physics_update)

    def _finish_physical_spin(self):
        if not self.is_spinning:
            return
        self._resolve_spin_result()
        if (not self._result_resolved or not self._wheel_physics.at_rest or not self.flapper.settled
                or not self.flapper.pin_clear(self._wheel_physics.angle)
                or not self._wheel_physics.result_is_locked):
            return
        self.is_spinning = False
        self.is_pointer_spinning = False
        self.wheel_velocity = 0.0
        self.pointer_velocity = 0.0
        self.pointer_acceleration = 0.0
        self.current_wheel_offset %= 360.0
        self.pointer_angle = 0.0

        if self._spin_job is not None:
            try:
                self.after_cancel(self._spin_job)
            except Exception:
                pass
            self._spin_job = None

        self._draw_wheel()

        if self.last_spin_data is not None:
            self.last_spin_data.update(
                animation_finished=True,
                wheel_offset=self.current_wheel_offset,
                flapper_angle=self.flapper.display_angle,
                flapper_clicks=self.flapper.clicks)

    def _resolve_spin_result(self):
        if self._result_resolved:
            return
        physics = self._wheel_physics
        if (not physics.result_is_locked or physics.result_locked_at is None
                or physics.elapsed - physics.result_locked_at < self.RESULT_SETTLEMENT_DELAY_SECONDS
                or physics.result_locked_index != fixed_flapper_winning_index(physics.angle)):
            return
        self._result_resolved = True
        # 中奖格由顶部固定 0° 读取；拨片的弹性偏转和余振不参与判定。
        self.current_round_index = physics.result_locked_index
        self.current_round_result = ROULETTE_SEQUENCE[self.current_round_index]
        self._finish_round(self.current_round_result)

    def _draw_fixed_flapper(self, cx, cy, outer_r):
        # 补偿轮盘下移的坐标；支架、轴销和拨片保留原来的绝对位置与尺寸。
        draw_fixed_flapper(self.wheel_canvas, cx,
                           cy - self.WHEEL_CENTER_Y_OFFSET - self.LEFT_CONTENT_Y_OFFSET,
                           outer_r, self.flapper.display_angle)
        for tag in ("flapper_mount", "flapper_shadow", "flapper", "flapper_hinge"):
            self.wheel_canvas.tag_raise(tag)
    
    def _get_winning_spot_ids(self, result: str):
        """
        Only straight up bets and outside bets flash.
        不闪的类型：
        split / corner / street / six_line / five_number
        """
        flashing_types = {
            "straight",
            "dozen",
            "column",
            "color",
            "odd_even",
            "high_low",
        }

        winning = set()
        for spot in self.bet_spots:
            if spot.get("type") not in flashing_types:
                continue
            if result in spot.get("numbers", set()):
                winning.add(spot["id"])
        return winning

    def _stop_result_flash(self):
        if self._result_flash_job is not None:
            try:
                self.after_cancel(self._result_flash_job)
            except Exception:
                pass
            self._result_flash_job = None
        self._result_flash_state = False
        self._result_flash_spot_ids = set()

    def _redraw_board_for_result_flash(self, flash_on=False):
        if not hasattr(self, "board_canvas"):
            return

        self.board_canvas.delete("all")
        draw_roulette_static(self.board_canvas, scale=BOARD_SCALE)

        if flash_on and self._result_flash_spot_ids:
            for spot_id in self._result_flash_spot_ids:
                spot = self._find_spot_by_id(spot_id)
                if not spot:
                    continue
                x1, y1, x2, y2 = spot["bounds"]
                self.board_canvas.create_rectangle(
                    int(x1), int(y1), int(x2), int(y2),
                    fill="#ffffff",
                    outline="#000000",
                    width=2,
                    tags=("result_flash",)
                )
                self._draw_flash_label(spot, fill="#000000")

        self._repaint_all_chips()

    def _result_flash_tick(self):
        if self.round_state != "result":
            self._stop_result_flash()
            return

        self._result_flash_state = not self._result_flash_state
        self._redraw_board_for_result_flash(flash_on=self._result_flash_state)
        self._result_flash_job = self.after(1000, self._result_flash_tick)

    def _is_flashable_spot(self, spot):
        return spot and spot.get("type") in {
            "straight",      # 单个数字注
            "dozen",         # 外围投注
            "column",
            "color",
            "odd_even",
            "high_low",
        }


    def _get_flashable_winning_spot_ids(self, result: str):
        flash_ids = set()
        for spot_id, amount in self.current_bets.items():
            if amount <= 0:
                continue
            spot = self._find_spot_by_id(spot_id)
            if not spot:
                continue
            if result in spot["numbers"] and self._is_flashable_spot(spot):
                flash_ids.add(spot_id)
        return flash_ids


    def _stop_result_flash(self):
        if self._result_flash_job is not None:
            try:
                self.after_cancel(self._result_flash_job)
            except Exception:
                pass
            self._result_flash_job = None
        self._result_flash_state = False
        self._result_flash_spot_ids = set()

    def _draw_flash_label(self, spot, fill="#ffffff"):
        """
        白色闪烁层上的文字，按原始桌面显示内容重画。
        """
        x1, y1, x2, y2 = spot["bounds"]
        cx, cy = spot["center"]
        t = spot["type"]

        if t == "straight":
            draw_lucky_bet_cell(
                self.board_canvas, spot["label"], spot["bounds"],
                fill="#ffffff", text_fill=fill, tag="result_flash"
            )
            return

        elif t == "column":
            text = "2:1"
            font = ("Arial", 11, "bold")
            angle = 90

        elif t == "dozen":
            text = spot["label"]  # 1st 12 / 2nd 12 / 3rd 12
            font = ("Arial", 11, "bold")
            angle = 0

        elif t in {"color", "odd_even"}:
            text = str(spot["label"]).upper()
            font = ("Arial", 11, "bold")
            angle = 0

        elif t == "high_low":
            # 统一显示桌面文字
            if spot["label"] in {"1-18", "1 to 18"}:
                text = "1 to 18"
            else:
                text = "19 to 36"
            font = ("Arial", 11, "bold")
            angle = 0

        else:
            return

        self.board_canvas.create_text(
            cx, cy,
            text=text,
            fill=fill,
            font=font,
            angle=angle,
            tags=("result_flash",)
        )

    def _redraw_board_for_result_flash(self, flash_on=False):
        if not hasattr(self, "board_canvas"):
            return

        self.board_canvas.delete("all")
        draw_roulette_static(self.board_canvas, scale=BOARD_SCALE)

        if flash_on and self._result_flash_spot_ids:
            for spot_id in self._result_flash_spot_ids:
                spot = self._find_spot_by_id(spot_id)
                if not spot:
                    continue

                x1, y1, x2, y2 = spot["bounds"]
                if spot["type"] != "straight":
                    self.board_canvas.create_rectangle(
                        int(x1), int(y1), int(x2), int(y2), fill="#ffffff",
                        outline="#000000", width=2, tags=("result_flash",))
                self._draw_flash_label(spot, fill="#000000")

        self._repaint_all_chips()

    def _finish_round(self, result):
        payout = self._settle_bets(result)

        self.history.add_result(result)
        self.add_marker_result(result)
        self._refresh_balance_display()

        winning_spots = self._get_winning_spot_ids(result)

        # 只保留中奖筹码；没中的全部删掉
        winning_bets = {}
        winning_colors = {}
        self.result_chip_display = {}

        for spot_id, amount in self.current_bets.items():
            spot = self._find_spot_by_id(spot_id)
            if not spot or amount <= 0:
                continue

            if result in spot["numbers"]:
                win_amount = int(amount * (spot["payout"] + 1))
                win_fill, win_text_color = self._result_chip_style(win_amount)

                winning_bets[spot_id] = int(amount)
                winning_colors[spot_id] = self._chip_fill_color_for_amount(amount)

                self.result_chip_display[spot_id] = {
                    "original_amount": int(amount),
                    "original_fill": self._chip_fill_color_for_amount(amount),
                    "original_text_color": self._spot_text_color(self._chip_fill_color_for_amount(amount)),
                    "win_amount": win_amount,
                    "win_fill": win_fill,
                    "win_text_color": win_text_color,
                }

        self.current_bets = winning_bets
        self.current_bet_colors = winning_colors
        self._refresh_bet_totals()

        self.round_state = "result"
        self.center_display_result = result

        # 立即绘制轮盘显示中奖结果（背景色+数字）
        self._draw_wheel()

        self._stop_result_flash()
        self._result_flash_spot_ids = winning_spots
        self._result_flash_state = True

        # 先显示“原色”，下一秒切到白色，再循环
        self._redraw_board_for_result_flash(flash_on=True)
        self._result_flash_job = self.after(1000, self._result_flash_tick)

        self.last_spin_data = {
            "result": result,
            "spin_direction": "left" if self.wheel_direction < 0 else "right",
            "initial_speed_m_s": self.initial_wheel_speed_m_s,
            "animation_finished": not self.is_spinning,
            "pointer_angle": 0.0,                              # 顶部固定判定线
            "wheel_offset": self.current_wheel_offset,         # 动画中的角度，最终停稳时更新
            "result_index": self.current_round_index,          # 在 ROULETTE_SEQUENCE 中的索引
            "flapper_angle": self.flapper.display_angle,       # 结算时的偏转及余振，随后逐帧更新
            "flapper_clicks": self.flapper.clicks,              # 本局经过支点的销钉数
        }
        # 绑定中心点击事件（如果尚未绑定）
        if not hasattr(self, "_center_click_bound"):
            self.wheel_canvas.bind("<Button-1>", self._on_wheel_click)
            self._center_click_bound = True

        self.after(6000, self._start_new_round)

    def _on_wheel_click(self, event):
        """点击轮盘画布时，判断是否点中中心区域，且处于结果展示阶段"""
        if self.round_state != "result":
            return
        if not self.last_spin_data:
            return

        # 获取画布上轮盘中心坐标
        cx, cy, _outer_r, inner_r = self._wheel_geometry()
        dx = event.x - cx
        dy = event.y - cy
        if (dx * dx + dy * dy) <= inner_r * inner_r:
            self._show_result_details()

    def _show_result_details(self):
        """弹出新窗口，显示本局的技术数据"""
        if self.detail_window is not None and self.detail_window.winfo_exists():
            self.detail_window.lift()
            return

        data = self.last_spin_data
        result = data["result"]
        pointer = data["pointer_angle"]
        offset = data["wheel_offset"]
        idx = data["result_index"]

        step = 360.0 / len(ROULETTE_SEQUENCE)   # 每个扇区角度跨度
        # 扇区边界算法：假设轮盘上第 i 个扇区的起始边界（相对于轮盘自身0点）为 i * step
        # 绝对坐标下的起始边界 = (i * step + offset) % 360
        def sector_range(i):
            start = (i * step + offset) % 360
            end = (start + step) % 360
            return start, end

        cur_start, cur_end = sector_range(idx)
        prev_idx = (idx - 1) % len(ROULETTE_SEQUENCE)
        prev_start, prev_end = sector_range(prev_idx)
        next_idx = (idx + 1) % len(ROULETTE_SEQUENCE)
        next_start, next_end = sector_range(next_idx)

        # 构建弹窗
        self.detail_window = tk.Toplevel(self)
        self.detail_window.title("开奖详情")
        self.detail_window.geometry("500x420")
        self.detail_window.resizable(False, False)

        text = f"""
    【本局开奖结果】: {result}

    【旋转方向】: {"向左" if data["spin_direction"] == "left" else "向右"}
    【初速度】: {data["initial_speed_m_s"]:.2f} m/s

    【固定拨片判定线】: {pointer:.4f}°（正上方）

    【上一个数字】: {ROULETTE_SEQUENCE[prev_idx]}
        角度范围: {prev_start:.4f}° ～ {prev_end:.4f}°

    【中奖数字扇区】: {result}
        角度范围: {cur_start:.4f}° ～ {cur_end:.4f}°

    【下一个数字】: {ROULETTE_SEQUENCE[next_idx]}
        角度范围: {next_start:.4f}° ～ {next_end:.4f}°

    说明:
    - 角度以正上方为 0°，顺时针增加。
    - 拨片支点固定在顶部，销钉推动时仅弹性偏转。
    - 确定无法越过相邻销钉后，等待 1 秒结算，剩余回弹继续播放。
    - 扇区范围是轮盘上该数字占据的绝对角度区间。
    - 扇区边界采用 [起点, 终点)，跨 0° 时包含接缝。
        """

        frm = tk.Frame(self.detail_window)
        frm.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        txt = tk.Text(frm, font=("Consolas", 12), wrap=tk.WORD)
        txt.insert(tk.END, text)
        txt.config(state=tk.DISABLED)
        txt.pack(fill=tk.BOTH, expand=True)
        tk.Button(self.detail_window, text="关闭", command=self.detail_window.destroy, font=("Arial", 10)).pack(pady=8)

        # 窗口关闭时清空引用
        self.detail_window.protocol("WM_DELETE_WINDOW", self._close_detail_window)

    def _close_detail_window(self):
        if self.detail_window:
            self.detail_window.destroy()
            self.detail_window = None

    # =====================================================
    # Misc / controls
    # =====================================================

    def _set_bet_buttons_state(self, state):
        pass

    def _enable_amount_buttons(self):
        for chip in self.chip_buttons:
            chip["canvas"].config(state=tk.NORMAL)
            chip["canvas"].bind("<Button-1>", lambda e, v=chip["amount"], c=chip["canvas"], cid=chip["chip_id"], bg=chip.get("bg_color", "#ffffff"): self._set_bet_amount(v, c, cid, bg))

    def _disable_amount_buttons(self):
        for chip in self.chip_buttons:
            chip["canvas"].config(state=tk.DISABLED)
            chip["canvas"].unbind("<Button-1>")

    def _set_control_buttons_state(self, state):
        """
        控制游戏相关按钮的状态（清除下注、重复上局下注、暂停倒计时、开始游戏）
        state: tk.NORMAL 或 tk.DISABLED
        """
        self.deal_button.config(state=state)
        self.reset_button.config(state=state)
        self.repeat_last_btn.config(state=state)
        self.pause_timer_btn.config(state=state)
        
        # 如果是在投注阶段启用按钮，重复按钮还需要根据余额和上一局数据单独控制
        if state == tk.NORMAL:
            self._update_repeat_button_state()

    def _refresh_balance_display(self):
        self.balance_label_side.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != "Guest":
            update_balance_in_json(self.username, self.balance)
        self._update_repeat_button_state()

    def on_close(self):
        try:
            if self.username != "Guest":
                update_balance_in_json(self.username, self.balance)
        except Exception:
            pass
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

        if self._embedded:
            try:
                self.root.title(self._previous_title)
                self.root.geometry(self._previous_geometry)
                self.root.tk.call(
                    "wm", "protocol", self.root._w,
                    "WM_DELETE_WINDOW", self._previous_close_protocol
                )
            except tk.TclError:
                pass
            self.destroy()
            if callable(self.on_back):
                self.on_back(float(self.balance))
            try:
                self.root.deiconify()
                self.root.lift()
            except tk.TclError:
                pass
        else:
            self.root.destroy()

    def show_game_instructions(self):
        """按本次参考的卡片式布局显示大六之轮图解；赔付统一以表格呈现。"""
        import tkinter as tk
        import tkinter.font as tkfont
        import math
        owner = self if isinstance(self, tk.Misc) else self.root
        parent = owner.winfo_toplevel()
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
        dialog.title('大六之轮 · 完整图解玩法')
        dialog.configure(bg='#faf5e8')
        dialog.resizable(False, False)
        dialog.transient(parent)
        width, height = 1000, 670
        parent.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = max(1, parent.winfo_width()), max(1, parent.winfo_height())
        dialog.geometry(f'{width}x{height}+{max(0, px + (pw-width)//2)}+{max(0, py + (ph-height)//2)}')
        # 赔率、限红和扇区分布直接复用本游戏的规则。
        names = {key: key for key in BET_OPTIONS}
        names.update({'👑': '皇冠', '💵': '钞票'})
        payout_rows = [
            [names[result], f'{lucky_net_odds(result)} : 1',
             f'该区下注 × {lucky_net_odds(result) + 1}']
            for result in BET_OPTIONS
        ]
        payout_rows.append(['未命中区域', '不获奖', '0（本金不退回）'])
        limit_rows = [
            [names[result], f'${self._bet_limit_for_spot({"label": result}):,}']
            for result in BET_OPTIONS
        ]
        distribution_rows = [
            [names[result], str(WHEEL_SEQUENCE.count(result))]
            for result in BET_OPTIONS
        ]
        manual_pages = [
            (
                '玩法',
                '确定无法越过相邻销钉后，等待 1 秒，再按顶部固定判定线结算；剩余回弹继续播放。',
                [
                    (
                        '一局如何进行', '',
                        [
                            ('① 选择下注区域',
                             '每局有 30 秒下注时间。\n'
                             '选定下注金额后，左键点击下注区；可重复加注，也可押多个区域。'),
                            ('② 锁定下注并旋转',
                             '倒计时结束，或点击“开始游戏”，即锁定下注并旋转。\n'
                             '旋转期间不能加注、撤注或重复下注。'),
                            ('③ 读取结果',
                             '同名扇区对应同一个下注区。\n'
                             '皇冠与钞票为两个独立结果，分别判定。'),
                        ],
                        [],
                    ),
                    (
                        '轮盘判定图解',
                        '按实际扇区顺序绘制；拨片支点固定在顶部。',
                        [],
                        [],
                    ),
                ],
            ),
            (
                '下注图解',
                '七个下注区与主界面排列一致。',
                [
                    (
                        '七区下注示意',
                        '上排四区，下排三区；图中下注仅作示例。',
                        [],
                        [],
                    ),
                    (
                        '加注与撤注', '',
                        [
                            ('左键加注 / 右键清除',
                             '左键每次加入当前选中的下注金额。\n'
                             '右键清除该区全部下注；“清除下注”清除全部区域。'),
                            ('余额与上限',
                             '下注时立即扣除余额。\n'
                             '接近单区上限时，仅加入剩余可下注金额。\n'
                             '余额不足以支付该次实际加注金额时，不下注。'),
                        ],
                        [],
                    ),
                ],
            ),
            (
                '赔率 & 限红',
                '净赢赔率不含本金；总返还包含中奖区域本金。',
                [
                    (
                        '赔付规则', '',
                        [],
                        [
                            (
                                '七区赔付表',
                                ['下注区域', '净赢赔率', '命中总返还\n（含该区本金）'],
                                [
                                    ['1', '1 : 1', '该区下注 × 2'],
                                    ['3', '3 : 1', '该区下注 × 4'],
                                    ['6', '6 : 1', '该区下注 × 7'],
                                    ['12', '12 : 1', '该区下注 × 13'],
                                    ['25', '25 : 1', '该区下注 × 26'],
                                    ['皇冠', '50 : 1', '该区下注 × 51'],
                                    ['钞票', '50 : 1', '该区下注 × 51'],
                                    ['未命中区域', '不获奖', '0（本金不退回）'],
                                ],
                            ),
                            (
                                '结算口径',
                                ['项目', '计算 / 处理方式'],
                                [
                                    ['命中区域返还', '该区下注 ×（净赢赔率 + 1）'],
                                    ['本局总返还', '所有中奖下注的返还合计'],
                                    ['本局净盈亏', '本局总返还 − 所有区域的总下注'],
                                    ['下注期清除单区', '退回该区全部下注金额'],
                                    ['下注期清除全部', '退回本局全部下注金额'],
                                    ['界面“获胜金额”',
                                     '显示总返还，包含中奖区域本金。\n并非本局净利润。'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '下注限额',
                        '每个区域独立计算上限；实际下注仍受可用余额限制。',
                        [],
                        [
                            (
                                '单区最高下注',
                                ['下注区域', '累计下注上限'],
                                [
                                    ['1 / 3 / 6', '每区 $500,000'],
                                    ['12 / 25', '每区 $300,000'],
                                    ['皇冠 / 钞票', '每区 $100,000'],
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            (
                '操作 & 记录',
                '下注阶段可管理下注；结算阶段可查看本局结果。',
                [
                    (
                        '常用操作', '',
                        [
                            ('暂停 / 恢复倒计时',
                             '仅下注阶段可用；暂停后仍可调整下注。\n'
                             '点击“开始倒计时”恢复剩余时间。'),
                            ('重复上局下注',
                             '恢复最近一次有下注的组合，会先清除当前下注。\n'
                             '按钮按当前可用余额检查能否支付上局总下注；恢复时仍受单区限红限制。'),
                            ('查看结果详情',
                             '在结果展示阶段，点击轮盘中心查看本局详情。\n'
                             '打开说明窗口不会自动暂停游戏倒计时。'),
                            ('阅读与关闭',
                             '点击左侧目录切换页面；使用鼠标滚轮或右侧滚动条浏览。\n'
                             '按 Esc 或点击右上角按钮关闭。'),
                        ],
                        [],
                    ),
                    (
                        '轮盘构成',
                        '下表统计实际轮盘扇区，不代表历史开奖记录。',
                        [],
                        [
                            (
                                '扇区数量',
                                ['结果', '扇区数'],
                                [
                                    [
                                        {'👑': '皇冠', '💵': '钞票'}.get(result, result),
                                        str(WHEEL_SEQUENCE.count(result)),
                                    ]
                                    for result in BET_OPTIONS
                                ] + [['合计', str(len(WHEEL_SEQUENCE))]],
                            ),
                        ],
                    ),
                ],
            ),
            (
                '结算示例',
                '以下均为示例下注；净盈亏须扣除本局全部下注。',
                [
                    (
                        '示例一：单区命中', '',
                        [],
                        [
                            (
                                '在 6 区下注，开出 6',
                                ['项目', '金额 / 计算'],
                                [
                                    ['6 区下注 / 总下注', '$100'],
                                    ['总返还（含本金）', '$100 × 7 = $700'],
                                    ['本局净盈亏', '$700 − $100 = +$600'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '示例二：多区下注', '',
                        [],
                        [
                            (
                                '在 1、6 区各下注，开出 6',
                                ['区域', '下注', '返还（含本金）'],
                                [
                                    ['1（未命中）', '$100', '$0'],
                                    ['6（命中）', '$100', '$700'],
                                    ['合计', '$200', '$700'],
                                ],
                            ),
                            (
                                '本局净盈亏',
                                ['总返还', '总下注', '净盈亏'],
                                [
                                    ['$700', '$200', '+$500'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '示例三：特殊图案', '',
                        [],
                        [
                            (
                                '在皇冠、钞票区各下注，开出皇冠',
                                ['区域', '下注', '返还（含本金）'],
                                [
                                    ['皇冠（命中）', '$100', '$5,100'],
                                    ['钞票（未命中）', '$100', '$0'],
                                    ['合计', '$200', '$5,100'],
                                ],
                            ),
                            (
                                '本局净盈亏',
                                ['总返还', '总下注', '净盈亏'],
                                [
                                    ['$5,100', '$200', '+$4,900'],
                                ],
                            ),
                        ],
                    ),
                    (
                        '示例四：全部未命中', '',
                        [],
                        [
                            (
                                '仅在 6 区下注，开出 3',
                                ['总下注', '总返还', '净盈亏'],
                                [
                                    ['$100', '$0', '−$100'],
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ]
        illustration_cards = {'轮盘判定图解': 'wheel', '七区下注示意': 'board'}
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
        tk.Label(header, text='大六之轮 · 完整图解玩法', font=(font_name, 20, 'bold'),
                 fg=GOLD, bg=HEADER, anchor='w', wraplength=795,
                 justify=tk.LEFT).place(x=24, y=6, width=795, height=41)
        tk.Label(header, text='玩法 · 下注 · 派奖 · 图解 · 结算示例',
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
            tk.Label(block, text=title, font=(font_name, 14, 'bold'),
                     fg=TEXT, bg=GOLD_BAR, anchor='w', justify=tk.LEFT,
                     wraplength=675, padx=11, pady=7).pack(fill=tk.X)
            grid = tk.Frame(block, bg=PANEL_2)
            grid.pack(fill=tk.X)
            count = max([len(headers)] + [len(row) for row in rows]) if rows else len(headers)
            table_font = tkfont.Font(family=font_name, size=14)
            matrix = ([headers] if headers else []) + rows
            minimums = [62] * count
            preferences = []
            for col in range(count):
                text_width = max((table_font.measure(line)
                                  for row in matrix if col < len(row)
                                  for line in str(row[col]).split('\n')), default=0)
                preferences.append(max(50, min(text_width, 260)))
            available = 680
            remaining = max(0, available - sum(minimums))
            total_preference = sum(preferences) or 1
            column_widths = [minimums[col] + remaining * preferences[col] // total_preference
                             for col in range(count)]
            if column_widths:
                column_widths[-1] += available - sum(column_widths)
            for col, width in enumerate(column_widths):
                grid.grid_columnconfigure(col, minsize=width)
            for r, row in enumerate(matrix):
                for c in range(count):
                    value = row[c] if c < len(row) else ''
                    head = bool(headers) and r == 0
                    bg = GOLD_BAR if head else (PANEL if r % 2 else '#fbf6e9')
                    fg = TEXT if head else MUTED
                    tk.Message(grid, text=value, font=(font_name, 14, 'bold' if head else 'normal'),
                               fg=fg, bg=bg, anchor='w', justify=tk.LEFT,
                               width=max(42, column_widths[c] - 16),
                               padx=7, pady=5, borderwidth=1,
                               relief=tk.SOLID).grid(row=r, column=c, sticky='nsew')
        def draw_illustration(parent_frame, kind):
            # Canvas 矢量示意，无外部图片文件依赖；图中不展示赔付数字。
            c = tk.Canvas(parent_frame, width=680, height=360 if kind == 'wheel' else 315,
                          bg=PANEL, highlightthickness=0)
            c.pack(padx=12, pady=(5, 10))
            if kind == 'wheel':
                cx, cy, radius = 178, 169, 145
                step = 360 / len(WHEEL_SEQUENCE)
                for index, result in enumerate(WHEEL_SEQUENCE):
                    # 第一个扇区中心对准顶部，与游戏初始停位一致。
                    angle = 90 + step / 2 - index * step
                    c.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                                 start=angle-step, extent=step, style=tk.PIESLICE,
                                 fill=OUTCOME_COLORS[result], outline=PANEL, width=1)
                c.create_oval(cx-98, cy-98, cx+98, cy+98, fill=PANEL_2, outline=BORDER)
                c.create_text(cx, cy, text=f'{len(WHEEL_SEQUENCE)} 个扇区\n7 种结果',
                              fill=TEXT, font=(font_name, 18, 'bold'), justify=tk.CENTER)
                draw_wheel_pins(c, cx, cy, radius, -step / 2)
                draw_fixed_flapper(c, cx, cy, radius)
                c.create_text(354, 26, text='① 先看固定拨片', anchor='nw', fill=GOLD,
                              font=(font_name, 15, 'bold'))
                c.create_text(354, 60, text='销钉推动拨片，拨片随后回弹。\n确定无法越钉后 1 秒结算。',
                              anchor='nw', fill=MUTED, font=(font_name, 14))
                c.create_text(354, 124, text='② 再找对应下注区', anchor='nw', fill=GOLD,
                              font=(font_name, 15, 'bold'))
                c.create_text(354, 158, text=f'图中指向“{names[WHEEL_SEQUENCE[0]]}”。\n'
                              '同名扇区都对应同一个下注区。',
                              anchor='nw', fill=MUTED, font=(font_name, 14))
                c.create_text(354, 222, text='③ 区分两种特殊图案', anchor='nw', fill=GOLD,
                              font=(font_name, 15, 'bold'))
                c.create_text(354, 256, text='皇冠与钞票互不通用。\n赔付详见“赔率 & 限红”表格。',
                              anchor='nw', fill=MUTED, font=(font_name, 14))
                c.create_text(26, 330, text='颜色与游戏轮盘一致；此图为静态判定示意。', anchor='nw',
                              fill=MUTED, font=(font_name, 12))
            else:
                for result, (x1, y1, x2, y2) in lucky_board_bounds().items():
                    y1, y2 = y1-35, y2-35
                    c.create_rectangle(x1, y1, x2, y2, fill=OUTCOME_COLORS[result],
                                       outline=BORDER, width=2)
                    c.create_text((x1+x2)/2, y1+30, text=names[result],
                                  fill=OUTCOME_TEXT_COLORS[result], font=(font_name, 20, 'bold'))
                    if result == '6':
                        x, y = (x1+x2)/2, y2-23
                        c.create_oval(x-24, y-18, x+24, y+18, fill=TEXT, outline=GOLD_BAR, width=2)
                        c.create_text(x, y, text='$100', fill=PANEL, font=(font_name, 11, 'bold'))
                c.create_text(30, 254, text='示例：先选 $100 筹码，再左键点击 6 区。\n'
                              '继续左键可加注；右键清除该区全部下注。',
                              anchor='nw', fill=TEXT, font=(font_name, 14))

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
                if card_title in illustration_cards:
                    draw_illustration(card, illustration_cards[card_title])
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
            if event.delta:
                steps = max(1, int(abs(event.delta) / 120))
                canvas.yview_scroll(-steps if event.delta > 0 else steps, 'units')
            return 'break'
        dialog.bind('<MouseWheel>', on_mousewheel)
        dialog.bind('<Button-4>', lambda _e: (canvas.yview_scroll(-1, 'units'), 'break')[1])
        dialog.bind('<Button-5>', lambda _e: (canvas.yview_scroll(1, 'units'), 'break')[1])
        dialog.bind('<Escape>', lambda _e: close_dialog())
        dialog.protocol('WM_DELETE_WINDOW', close_dialog)
        if nav_buttons:
            render_page(0)
        dialog.focus_set()

    def start_game(self):
        """强制开始游戏：下注阶段立即旋转，结果阶段跳转到新的一局"""
        if self.round_state == "betting":
            # 取消倒计时，立即开始旋转
            if self._countdown_job is not None:
                try:
                    self.after_cancel(self._countdown_job)
                except Exception:
                    pass
                self._countdown_job = None
            self._lock_bets_and_spin()

def main(initial_balance=1_000_000, username="Guest", *, parent=None,
         balance=None, user=None, on_back=None, on_balance_change=None):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        page = RouletteGameGUI(
            parent, initial_balance=actual_balance, username=actual_user,
            on_back=on_back, on_balance_change=on_balance_change
        )
        page.place(x=0, y=0, relwidth=1, relheight=1)
        page.tkraise()
        return page

    root = tk.Tk()
    root._lucky_wheel_standalone = True
    page = RouletteGameGUI(root, initial_balance=actual_balance, username=actual_user)
    page.pack(fill=tk.BOTH, expand=True)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")
