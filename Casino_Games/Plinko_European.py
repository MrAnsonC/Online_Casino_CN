"""欧式落球轮盘（手动版，电机相位随机化修订）。

运行：python Plinko_European.py；打开后等待 Enter／按钮，不会自动落球。
投注、赔率、碰撞与回球流程沿用原版。落球同时独立抽取电机计划，
前2秒平滑完成一个均匀随机的整格转角；没有瞬移、改号或按下注选结果。
若球在该固定区间内提前接近移动槽壁，先取消并全额退款，再按物理流程回球。
该校验与随机转角、号码、下注金额、账户和历史输赢无关。
默认 Guest 可独立运行；实名账户沿用原项目加密存储。
"""

import sys as _account_sys
from pathlib import Path as _AccountPath
_account_root = next((p for p in (_AccountPath(__file__).resolve().parent,
                     *_AccountPath(__file__).resolve().parents)
                     if (p / "A_Tools" / "Account" / "secure_json.py").is_file()), None)
_SECURE_ACCOUNTS = _account_root is not None
if _SECURE_ACCOUNTS:
    if str(_account_root) not in _account_sys.path:
        _account_sys.path.insert(0, str(_account_root))
    from A_Tools.Account import install_secure_json as _install_secure_json
    _install_secure_json()
    del _install_secure_json
del _account_root, _AccountPath, _account_sys

import json
import math
import os
import uuid
import secrets
from collections import OrderedDict
from datetime import date
import time
import tkinter as tk
from tkinter import messagebox, ttk, font as tkfont

try:
    from PIL import ImageColor
except Exception:
    ImageColor = None

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:
    Image = ImageDraw = ImageFont = ImageTk = None

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
BOARD_SCALE = 1.2                     # Fit the betting board within the 540px left column.
BOARD_W = 508
BOARD_H = 272  # Extra 7px for the lowered neighbour controls.

# =========================================================
# Paths / persistence
# =========================================================

def project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_path() -> str:
    return os.path.join(project_root(), "A_Tools/Account/saving_data.json")


def plinko_log_path() -> str:
    log_dir = os.path.join(project_root(), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Plinko_European.json")


def ensure_json_file(path: str, default_obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_obj, f, ensure_ascii=False, indent=4)


def load_user_data():
    if not _SECURE_ACCOUNTS:
        raise RuntimeError("实名账户需要原项目的 A_Tools/Account/secure_json.py；独立运行请使用 Guest。")
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
    if not _SECURE_ACCOUNTS:
        raise RuntimeError("实名账户需要原项目的 A_Tools/Account/secure_json.py；独立运行请使用 Guest。")
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

ROULETTE_SEQUENCE = [
    "0", "32", "15", "19", "4", "21", "2", "25", "17", "34",
    "6", "27", "13", "36", "11", "30", "8", "23", "10", "5",
    "24", "16", "33", "1", "20", "14", "31", "9", "22", "18",
    "29", "7", "28", "12", "35", "3", "26",
]
assert len(ROULETTE_SEQUENCE) == 37, f"Wheel sequence must have 37 items, got {len(ROULETTE_SEQUENCE)}"
assert set(ROULETTE_SEQUENCE) == {str(i) for i in range(37)}

def pocket_index(ball_angle: float, wheel_angle: float) -> int:
    """将球与转盘的相对角度映射到等宽的欧式单零槽位。"""
    return int(((ball_angle - wheel_angle) % 360.0) // (360.0 / len(ROULETTE_SEQUENCE)))

# Vertical board renderer scale (pixels per metre).
WHEEL_METRE_SCALE = 465.0
WHEEL_CARD_OFF = {'Red':'#943538','Black':'#263342','Green':'#126752'}
WHEEL_CARD_ON = {'Red':'#F44336','Black':'#526F83','Green':'#10B58A'}
WHEEL_CUP_ON = {'Red':'#944443','Black':'#4A687A','Green':'#24866D'}
RESULT_FLASH_PERIOD_MS = 1500
RESULT_FLASH_COUNT = 3

NUMBER_STROKES = {
    "0": (((.25,0),(.75,0),(1,.2),(1,.8),(.75,1),(.25,1),(0,.8),(0,.2),(.25,0)),),
    "1": (((.1,.2),(.55,0),(.55,1)),((.1,1),(1,1))),
    "2": (((0,.2),(.2,0),(.8,0),(1,.2),(1,.35),(0,1),(1,1)),),
    "3": (((0,0),(1,0),(.5,.45),(.85,.5),(1,.65),(1,.8),(.8,1),(.15,1),(0,.85)),),
    "4": (((.8,1),(.8,0),(0,.65),(1,.65)),),
    "5": (((1,0),(0,0),(0,.45),(.75,.45),(1,.65),(1,.8),(.8,1),(.2,1),(0,.85)),),
    "6": (((1,.05),(.75,0),(.25,0),(0,.25),(0,.8),(.2,1),(.8,1),(1,.8),(1,.65),(.8,.45),(0,.45)),),
    "7": (((0,0),(1,0),(.3,1)),),
    "8": (((.2,.5),(0,.3),(0,.15),(.2,0),(.8,0),(1,.15),(1,.3),(.8,.5),(.2,.5),(0,.7),(0,.85),(.2,1),(.8,1),(1,.85),(1,.7),(.8,.5)),),
    "9": (((1,.55),(.2,.55),(0,.35),(0,.15),(.2,0),(.8,0),(1,.2),(1,.75),(.75,1),(.1,1)),),
}


class PlinkoPhysics:
    """Fixed-step gravity/contact model with horizontal metal obstacles.

    The same obstacle polygons and guard arc feed collisions and the 2D view.
    The side frame guides the ball down to an opening at the very bottom,
    below the last obstacle row. Wheel contacts may bounce it before it seats.
    Gravity, the outer race and moving pocket dividers determine its landing;
    the pocket that actually holds it carries it back to the launcher. All launch
    and motor variation is independent of bets, account data and past results.
    """
    TAU = 2 * math.pi
    STEP = TAU / len(ROULETTE_SEQUENCE)
    # A fast ball must not cross a thin moving divider within one contact step.
    DT = 1 / 480
    G = 9.81
    BOARD_R = .300
    GUARD_HALF = .0025
    BALL_R = .009
    LAUNCH_Y = -.274
    POCKET_OUTER = .350
    POCKET_CENTRE = POCKET_OUTER - BALL_R
    DIVIDER_INNER = .304
    DIVIDER_HALF = .0012
    BAR_THICK = .009
    SIDE_BAR_SLOPE = math.tan(math.radians(3))
    REVERSE_CHANCE = .75
    STALL_SECONDS = 15.0
    STALL_MOVE_DISTANCE = BALL_R*.5
    OBSTACLE_RESET_SECONDS = 2.0
    FAST_SPEED = math.radians(69.3)
    DROP_SPEED_MIN = math.radians(32.6)
    DROP_SPEED_MAX = math.radians(54.9)
    SLOWDOWN_DELAY_MIN = .1
    SLOWDOWN_DELAY_MAX = .4
    SLOWDOWN_SECONDS = 2.5
    BRAKE_SECONDS = .65
    # A full numbered phase is randomized continuously before contact.
    PHASE_MIX_SECONDS = 2.0
    RETURN_SPEED = 2.0
    LAUNCH_HALF = .018
    LAUNCH_MOUTH_HALF = .032
    LAUNCH_TOP = -.354
    LAUNCH_SHOULDER = -.305
    LAUNCH_FLOOR = LAUNCH_Y+BALL_R

    @classmethod
    def obstacles(cls):
        """Staggered horizontal ledges, clipped to the circular backplate."""
        result = []
        for row in range(11):
            y = -.228 + row*.043
            extent = math.sqrt(max(0.0, (cls.BOARD_R-.045)**2-y*y))
            shift = .058 if row % 2 else 0
            for col in range(-3, 4):
                centre = col*.116+shift
                left, right = max(-extent, centre-.040), min(extent, centre+.040)
                if right-left >= .026:
                    result.append(((left+right)/2, y, (right-left)/2))
        return tuple(result)

    @classmethod
    def obstacle_polygon(cls, obstacle):
        x, y, half = obstacle
        # Only the first/last ledge in each row incline towards the centre.
        # A lone ledge and every intermediate ledge are exactly horizontal.
        row = [o for o in cls.obstacles() if abs(o[1]-y)<1e-12]
        slope = (cls.SIDE_BAR_SLOPE if len(row)>1 and abs(x-row[0][0])<1e-12
                 else -cls.SIDE_BAR_SLOPE if len(row)>1 and abs(x-row[-1][0])<1e-12
                 else 0.0)
        rise = half*slope
        return ((x-half, y-rise), (x+half, y+rise),
                (x+half, y+rise+cls.BAR_THICK), (x-half, y-rise+cls.BAR_THICK))

    @classmethod
    def bottom_deflectors(cls):
        # The two solid guides in the reference, with a clear central opening.
        # Bury the outer tip in the frame; an exposed tip could catch a sphere
        # between the curved frame and the guide instead of directing it in.
        left = ((-.176,.240),(-.070,.250),(-.070,.264),(-.100,.282))
        return (left, tuple((-x,y) for x,y in reversed(left)))

    @staticmethod
    def _bounds(points):
        return (min(x for x,y in points),min(y for x,y in points),
                max(x for x,y in points),max(y for x,y in points))

    def __init__(self, rng=None, *, initial_angle=None, initial_speed=None):
        self.rng = rng if rng is not None else secrets.SystemRandom()
        self.wheel_angle = (self.rng.random()*self.TAU if initial_angle is None
                            else initial_angle % self.TAU)
        self.wheel_speed = self.FAST_SPEED if initial_speed is None else initial_speed
        self.direction = -1 if self.wheel_speed<0 else 1
        self.next_direction = None
        self.reversed_next_round = None
        self.t = self.remainder = 0.0
        self.obstacle_layout = self.obstacles()
        bars = tuple(self.obstacle_polygon(o) for o in self.obstacle_layout)
        self.base_polygons = bars+self.bottom_deflectors()
        self.polygons = list(self.base_polygons)
        self.polygon_bounds = [self._bounds(p) for p in self.polygons]
        self.last_row_bottom_y = max(y for polygon in bars for _, y in polygon)
        self.exit_min_y = max(self.last_row_bottom_y,
                              self.BOARD_R-2*self.BALL_R-self.GUARD_HALF)
        self.exit_angle = math.acos(-self.exit_min_y/self.BOARD_R)
        self.mode = 'waiting'
        self.x, self.y = 0.0, self.LAUNCH_Y
        self.vx = self.vy = 0.0
        self.spin = 0.0
        self.pocket = self.result_index = None
        self.drop_started_at = self.captured_at = self.settled_at = None
        self.drop_slowdown_delay = None
        self.obstacle_hits = 0
        self._contacting = set()
        self._seat_pocket = None
        self._seat_time = 0.0
        self.exit_position = None
        self.wheel_contact_at = None
        self.round_cancelled = False
        self.cancelled_at = None
        self.cancel_reason = None
        self.phase_offset_slots = None
        self.phase_offset = 0.0
        self.first_rotor_approach_at = None
        self.rotating_obstacle = None
        self.obstacle_rotation_angle = 0.0
        self.obstacle_angular_speed = 0.0
        self.rotations_completed = 0
        self._stall_anchor = (self.x,self.y)
        self._stall_since = self.t
        self._loading_rest = 0.0
        half, mouth, floor = self.LAUNCH_HALF,self.LAUNCH_MOUTH_HALF,self.LAUNCH_FLOOR
        top, shoulder, wall = self.LAUNCH_TOP,self.LAUNCH_SHOULDER,.003
        left_funnel = ((-mouth-wall,top),(-mouth,top),(-half,shoulder),(-half-wall,shoulder))
        left_neck = ((-half-wall,shoulder),(-half,shoulder),(-half,floor+.009),(-half-wall,floor+.009))
        walls = (left_funnel,left_neck)
        self.launcher_polygons = (walls+tuple(tuple((-x,y) for x,y in reversed(p)) for p in walls)
                                 +(((-half,floor),(half,floor),(half,floor+.009),(-half,floor+.009)),))
        self._previous = (self.x, self.y, self.wheel_angle, self.wheel_speed)

    def prepare_next_round(self):
        if self.mode != 'waiting':
            raise RuntimeError('The ball must return to the launcher before betting opens')
        self.pocket = self.result_index = None
        self.drop_started_at = self.captured_at = self.settled_at = None
        self.drop_slowdown_delay = None
        self.next_direction = None
        self.reversed_next_round = None
        self.obstacle_hits = 0
        self._contacting.clear()
        self._seat_pocket = None
        self._seat_time = 0.0
        self.exit_position = None
        self.wheel_contact_at = None
        self.round_cancelled = False
        self.cancelled_at = None
        self.cancel_reason = None
        self.phase_offset_slots = None
        self.phase_offset = 0.0
        self.first_rotor_approach_at = None
        self.rotations_completed = 0
        self.obstacle_rotation_angle = 0.0
        self._stall_anchor = (self.x,self.y)
        self._stall_since = self.t
        self._previous = (self.x, self.y, self.wheel_angle, self.wheel_speed)

    def release(self):
        if self.mode != 'waiting':
            return False
        self.drop_started_at = self.t
        self.drop_angle = self.wheel_angle
        self.drop_start_speed = self.wheel_speed
        # Uniform independent phase, sampled only after betting is locked.
        self.phase_offset_slots = self.rng.randrange(len(ROULETTE_SEQUENCE))
        self.phase_offset = self.direction * self.phase_offset_slots * self.STEP
        self.drop_end_speed = self.direction*self.rng.uniform(self.DROP_SPEED_MIN, self.DROP_SPEED_MAX)
        self.drop_slowdown_delay = self.rng.uniform(self.SLOWDOWN_DELAY_MIN, self.SLOWDOWN_DELAY_MAX)
        self.vx = self.rng.choice((-1,1))*self.rng.uniform(.09,.16)
        self.vy = max(self.vy,.025)
        self.spin = self.vx/self.BALL_R
        self._stall_anchor = (self.x,self.y)
        self._stall_since = self.t
        self.mode = 'drop'
        self._previous = (self.x, self.y, self.wheel_angle, self.wheel_speed)
        return True

    @staticmethod
    def _smooth(u):
        u = max(0.0, min(1.0, u))
        return u*u*(3-2*u)

    @staticmethod
    def _ease(u):
        """Motor position with zero velocity AND acceleration at either end."""
        u = max(0.0, min(1.0, u))
        return u*u*u*(10+u*(-15+6*u))

    @staticmethod
    def _ease_velocity(u):
        u = max(0.0, min(1.0, u))
        return 30*u*u*(1-u)*(1-u)

    def _obstacle_contact(self, index):
        return self._polygon_contact(self.polygons[index],self.polygon_bounds[index],
                                     self.obstacle_angular_speed if index==self.rotating_obstacle else 0.0,
                                     self._rotation_pivot if index==self.rotating_obstacle else None)

    def _contact_friction(self, nx, ny, surface_x, surface_y, limit):
        """Coulomb impulse for a rolling solid sphere (I = 2/5 m r²).

        Keep angular momentum rather than silently losing it at ledge corners.
        A sphere can then roll along an exactly horizontal central obstacle.
        """
        tx,ty = -ny,nx
        slip = ((self.vx-surface_x)*tx+(self.vy-surface_y)*ty
                -self.BALL_R*self.spin)
        impulse = max(-limit,min(limit,-slip/3.5))
        self.vx += impulse*tx
        self.vy += impulse*ty
        self.spin -= 2.5*impulse/self.BALL_R

    def _polygon_contact(self, points, bounds, angular_speed=0.0, pivot=None):
        r = self.BALL_R
        x1,y1,x2,y2 = bounds
        if self.x < x1-r or self.x > x2+r or self.y < y1-r or self.y > y2+r:
            return False
        inside, best = True, None
        for a, b in zip(points, points[1:]+points[:1]):
            dx, dy = b[0]-a[0], b[1]-a[1]
            if dx*(self.y-a[1])-dy*(self.x-a[0]) < -1e-12:
                inside = False
            u = max(0.0, min(1.0, ((self.x-a[0])*dx+(self.y-a[1])*dy)/(dx*dx+dy*dy)))
            qx, qy = a[0]+u*dx, a[1]+u*dy
            d2 = (self.x-qx)**2+(self.y-qy)**2
            if best is None or d2 < best[0]:
                best = (d2, qx, qy, dx, dy)
        d2, qx, qy, ex, ey = best
        if not inside and d2 >= r*r:
            return False
        distance = math.sqrt(d2)
        if inside or distance < 1e-12:
            length = math.hypot(ex, ey)
            nx, ny = ey/length, -ex/length
        else:
            nx, ny = (self.x-qx)/distance, (self.y-qy)/distance
        self.x, self.y = qx+nx*(r+1e-6), qy+ny*(r+1e-6)
        surface_x = -angular_speed*(qy-pivot[1]) if pivot is not None else 0.0
        surface_y = angular_speed*(qx-pivot[0]) if pivot is not None else 0.0
        vn = (self.vx-surface_x)*nx+(self.vy-surface_y)*ny
        if vn < 0:
            restitution = .55 if vn < -.14 else 0.0
            impulse = -(1+restitution)*vn
            self.vx += impulse*nx
            self.vy += impulse*ny
            self._contact_friction(nx,ny,surface_x,surface_y,.12*impulse)
        return True

    def _launcher_contact(self):
        if self.mode not in {'loading','waiting'}:
            return
        for polygon in self.launcher_polygons:
            self._polygon_contact(polygon,self._bounds(polygon))
        if abs(self.y-self.LAUNCH_Y)<.001 and abs(self.vy)<.10:
            # Friction in the supported launch cradle, not a frozen position.
            self.vx *= math.exp(-8*self.DT)
            self.spin *= math.exp(-8*self.DT)

    def _inner_gate_contact(self):
        if self.mode not in {'result','returning','recovery_ready'}:
            return
        radius = math.hypot(self.x,self.y)
        limit = self.DIVIDER_INNER+self.BALL_R
        if radius >= limit:
            return
        nx,ny = self.x/radius,self.y/radius
        self.x,self.y = nx*limit,ny*limit
        vn = self.vx*nx+self.vy*ny
        if vn < 0:
            restitution = .15 if vn < -.14 else 0.0
            impulse = -(1+restitution)*vn
            self.vx += impulse*nx
            self.vy += impulse*ny
            self._contact_friction(nx,ny,-self.wheel_speed*self.DIVIDER_INNER*ny,
                                   self.wheel_speed*self.DIVIDER_INNER*nx,.08*impulse)

    def _outer_contact(self):
        radius = math.hypot(self.x, self.y)
        limit = self.POCKET_CENTRE
        if radius < limit:
            return
        if self.exit_position is not None and self.wheel_contact_at is None:
            self.wheel_contact_at = self.t
        nx, ny = self.x/radius, self.y/radius
        self.x, self.y = nx*limit, ny*limit
        vn = self.vx*nx+self.vy*ny
        if vn > 0:
            restitution = .28 if vn > .14 else 0.0
            impulse = (1+restitution)*vn
            self.vx -= impulse*nx
            self.vy -= impulse*ny
            self._contact_friction(-nx,-ny,-self.wheel_speed*self.POCKET_OUTER*ny,
                                   self.wheel_speed*self.POCKET_OUTER*nx,.14*impulse)

    def guard_arc(self):
        """Side frame with rounded ends flanking the bottom opening."""
        start, end = self.TAU-self.exit_angle, self.TAU+self.exit_angle
        count = math.ceil((end-start)/math.radians(2))
        return tuple((self.BOARD_R*math.sin(start+(end-start)*i/count),
                      -self.BOARD_R*math.cos(start+(end-start)*i/count))
                     for i in range(count+1))

    def _guard_contact(self):
        if self.mode in {'loading','waiting'} and self.y < -.245 and abs(self.x)<self.LAUNCH_HALF+self.BALL_R:
            return  # The top transfer hatch is open into the physical cradle.
        radius = math.hypot(self.x,self.y)
        clearance = self.BALL_R+self.GUARD_HALF
        if radius < self.BOARD_R-clearance:
            return
        angle = math.atan2(self.x,-self.y) % self.TAU
        if self.exit_angle <= angle <= self.TAU-self.exit_angle:
            # The lower arc is open. Only the rounded end caps can touch here.
            end = self.exit_angle if self.x >= 0 else self.TAU-self.exit_angle
            qx, qy = self.BOARD_R*math.sin(end), self.exit_min_y
        else:
            qx, qy = self.BOARD_R*self.x/radius, self.BOARD_R*self.y/radius
        dx, dy = self.x-qx, self.y-qy
        distance = math.hypot(dx,dy)
        if distance >= clearance:
            return
        if distance < 1e-12:
            nx, ny = -qx/self.BOARD_R, -qy/self.BOARD_R
        else:
            nx, ny = dx/distance, dy/distance
        self.x, self.y = qx+nx*(clearance+1e-6), qy+ny*(clearance+1e-6)
        vn = self.vx*nx+self.vy*ny
        if vn < 0:
            restitution = .30 if vn < -.14 else 0.0
            impulse = -(1+restitution)*vn
            self.vx += impulse*nx
            self.vy += impulse*ny
            self._contact_friction(nx,ny,0.,0.,.035*impulse)

    def _divider_contact(self, index):
        angle = self.wheel_angle+index*self.STEP
        nx, ny = math.sin(angle), -math.cos(angle)
        along = max(self.DIVIDER_INNER,
                    min(self.POCKET_OUTER, self.x*nx+self.y*ny))
        qx, qy = along*nx, along*ny
        dx, dy = self.x-qx, self.y-qy
        distance = math.hypot(dx, dy)
        clearance = self.BALL_R+self.DIVIDER_HALF
        if distance >= clearance:
            return
        if self.exit_position is not None and self.wheel_contact_at is None:
            self.wheel_contact_at = self.t
        if distance < 1e-12:
            dx, dy, distance = -ny, nx, 1.0
        cx, cy = dx/distance, dy/distance
        self.x, self.y = qx+cx*clearance, qy+cy*clearance
        surface_x, surface_y = -self.wheel_speed*qy, self.wheel_speed*qx
        rvx, rvy = self.vx-surface_x, self.vy-surface_y
        vn = rvx*cx+rvy*cy
        if vn < 0:
            restitution = .25 if vn < -.14 else 0.0
            impulse = -(1+restitution)*vn
            self.vx += impulse*cx
            self.vy += impulse*cy
            self._contact_friction(cx,cy,surface_x,surface_y,.18*impulse)

    def _step_ball(self):
        dt = self.DT
        self.vy += self.G*dt
        # Neglect air drag over this short metal board. Contact impulses handle
        # friction, so a rolling ball does not artificially fade to a stop on
        # an exactly level central ledge.
        self.x += self.vx*dt
        self.y += self.vy*dt
        touching = set()
        for i in range(len(self.polygons)):
            if self._obstacle_contact(i):
                touching.add(i)
                if i not in self._contacting:
                    self.obstacle_hits += 1
        self._contacting = touching
        self._launcher_contact()
        self._inner_gate_contact()
        self._guard_contact()
        self._check_phase_clearance()
        # The lower opening spans an arc, rather than a funnel to screen X=0.
        if math.hypot(self.x,self.y) >= self.DIVIDER_INNER-self.BALL_R-self.DIVIDER_HALF:
            for _ in range(3):
                self._outer_contact()
                angle = math.atan2(self.x,-self.y)
                index = int(((angle-self.wheel_angle) % self.TAU)/self.STEP)
                self._divider_contact(index)
                self._divider_contact(index+1)
                self._inner_gate_contact()
                self._guard_contact()
            self._outer_contact()
        if (self.mode in {'drop','storage','recovery','recovery_drop'} and math.hypot(self.x,self.y) >= self.BOARD_R
                and self.exit_position is None):
            self.exit_position = (self.x,self.y)

    def _seat_state(self):
        radius = math.hypot(self.x,self.y)
        if self.exit_position is None or self.wheel_contact_at is None:
            return None, False
        # A side-facing cup can support the sphere on a divider before it
        # reaches the outer floor. This is still a real, stable pocket seat.
        if radius < self.DIVIDER_INNER+self.BALL_R:
            return None, False
        angle = math.atan2(self.x,-self.y)
        index = int(((angle-self.wheel_angle) % self.TAU)/self.STEP)
        radial = (self.x*self.vx+self.y*self.vy)/radius
        tangent = (-self.y*self.vx+self.x*self.vy)/radius-self.wheel_speed*radius
        return index, abs(radial) < .12 and abs(tangent) < .18

    def _drop_motor_state(self, elapsed):
        """Prescribed smooth motion, sampled once at release and never retargeted.

        An independent uniform whole-pocket offset is completed over the same
        fixed interval for EVERY offset, including zero. Before rotor contact,
        this changes the numbered phase without changing the falling ball.
        At completion, extra angular velocity/acceleration are both zero.
        The equal divider geometry is invariant under whole-pocket rotations.
        """
        delay, duration = self.drop_slowdown_delay, self.SLOWDOWN_SECONDS
        delta = self.drop_end_speed - self.drop_start_speed
        if elapsed <= delay:
            travel, speed = self.drop_start_speed * elapsed, self.drop_start_speed
        else:
            slowing = elapsed - delay
            u = min(1.0, slowing / duration)
            travel = (self.drop_start_speed * delay + self.drop_start_speed * duration * u
                      + delta * duration * (u**3 - .5*u**4)
                      + self.drop_end_speed * max(0.0, slowing - duration))
            speed = self.drop_start_speed + delta * self._smooth(u)
        mix_u = min(1.0, max(0.0, elapsed / self.PHASE_MIX_SECONDS))
        travel += self.phase_offset * self._ease(mix_u)
        speed += self.phase_offset * self._ease_velocity(mix_u) / self.PHASE_MIX_SECONDS
        return travel, speed

    def _check_phase_clearance(self):
        """Refund before any rotor-dependent contact if mixing is not complete.

        This test is after static guards but BEFORE moving dividers. Its radius
        depends only on equal physical geometry, never the offset, number,
        stake, account or previous results. The same fixed interval applies
        to offset zero, so cancellation cannot select which offsets survive.
        The ball keeps moving physically and follows the normal return path.
        """
        if self.mode != 'drop' or self.drop_started_at is None:
            return
        safe_radius = self.DIVIDER_INNER - self.BALL_R - self.DIVIDER_HALF - 1e-6
        if math.hypot(self.x, self.y) < safe_radius:
            return
        if self.first_rotor_approach_at is None:
            self.first_rotor_approach_at = self.t
        elapsed = self.t - self.drop_started_at
        if elapsed < self.PHASE_MIX_SECONDS and not self.round_cancelled:
            self.round_cancelled = True
            self.cancelled_at = self.t
            self.cancel_reason = 'phase_clearance'
            self.result_index = None
            self.next_direction = self.reversed_next_round = None

    def _step_drop(self):
        self._step_ball()
        if self._watch_stall():
            return
        index, seated = self._seat_state()
        if seated and index == self._seat_pocket:
            self._seat_time += self.DT
        else:
            self._seat_pocket, self._seat_time = index, 0.0
        if self._seat_time >= .06:
            self._capture_storage()

    def _capture_storage(self):
        if self.mode not in {'drop','recovery_drop'}:
            return
        self.captured_at = self.t
        self.capture_angle, self.capture_speed = self.wheel_angle, self.wheel_speed
        self.brake_started_at = max(self.t, self.drop_started_at+self.drop_slowdown_delay)
        self.pocket = self._seat_pocket
        # One independent draw per completed drop; no streak correction and
        # no dependence on bets, balance, winning number or earlier draws.
        if not self.round_cancelled:
            self.reversed_next_round = self.rng.random()<self.REVERSE_CHANCE
            self.next_direction = -self.direction if self.reversed_next_round else self.direction
        self._seat_time = 0.0
        self.mode = 'storage'

    def _watch_stall(self):
        if (math.hypot(self.vx,self.vy)>=self.STALL_MOVE_DISTANCE/self.STALL_SECONDS
                or math.dist((self.x,self.y),self._stall_anchor)>=self.STALL_MOVE_DISTANCE):
            self._stall_anchor = (self.x,self.y)
            self._stall_since = self.t
            return False
        if self.t-self._stall_since<self.STALL_SECONDS or not self._contacting:
            return False
        if not self.round_cancelled:
            self.round_cancelled = True
            self.cancelled_at = self.t
            self.result_index = None
            self.next_direction = self.reversed_next_round = None
        # Only the obstacle actually touching the stalled sphere is reset.
        support = min(self._contacting,key=lambda i: abs(self.polygon_bounds[i][1]-self.y-self.BALL_R))
        self.rotating_obstacle = support
        points = self.base_polygons[support]
        self._rotation_pivot = (sum(x for x,y in points)/len(points),sum(y for x,y in points)/len(points))
        self._recovery_started_at = self.t
        self._recovery_wheel_angle,self._recovery_wheel_speed = self.wheel_angle,self.wheel_speed
        self.obstacle_rotation_angle = self.obstacle_angular_speed = 0.0
        self._seat_pocket,self._seat_time = None,0.0
        self.mode = 'recovery'
        return True

    def _step_recovery(self):
        elapsed = self.t-self._recovery_started_at
        brake = min(1.0,elapsed/self.BRAKE_SECONDS)
        self.wheel_angle = (self._recovery_wheel_angle+self._recovery_wheel_speed*self.BRAKE_SECONDS*
                            (brake-brake**3+.5*brake**4)) % self.TAU
        self.wheel_speed = self._recovery_wheel_speed*(1-self._smooth(brake))
        u = min(1.0,elapsed/self.OBSTACLE_RESET_SECONDS)
        self.obstacle_rotation_angle = self.TAU*self._ease(u)
        self.obstacle_angular_speed = self.TAU*self._ease_velocity(u)/self.OBSTACLE_RESET_SECONDS
        sine,cosine = math.sin(self.obstacle_rotation_angle),math.cos(self.obstacle_rotation_angle)
        px,py = self._rotation_pivot
        index = self.rotating_obstacle
        self.polygons[index] = tuple((px+(x-px)*cosine-(y-py)*sine,
                                      py+(x-px)*sine+(y-py)*cosine)
                                     for x,y in self.base_polygons[index])
        self.polygon_bounds[index] = self._bounds(self.polygons[index])
        self._step_ball()
        if u>=1:
            self.polygons[index] = self.base_polygons[index]
            self.polygon_bounds[index] = self._bounds(self.polygons[index])
            self.rotating_obstacle = None
            self.obstacle_angular_speed = 0.0
            self.rotations_completed += 1
            self._stall_anchor,self._stall_since = (self.x,self.y),self.t
            self.mode = 'recovery_drop'

    def _step_storage(self):
        hold = self.brake_started_at-self.captured_at
        held = min(hold, self.t-self.captured_at)
        elapsed = min(self.BRAKE_SECONDS, max(0.0,self.t-self.brake_started_at))
        u = elapsed/self.BRAKE_SECONDS
        self.wheel_angle = (self.capture_angle+self.capture_speed*held
                            +self.capture_speed*self.BRAKE_SECONDS*(u-u**3+.5*u**4)) % self.TAU
        self.wheel_speed = self.capture_speed*(1-self._smooth(u))
        # Keep integrating contacts throughout braking. Neither the ball nor
        # the winning pocket is pulled towards an imposed result position.
        self._step_ball()
        index, seated = self._seat_state()
        self.pocket = index
        resting = u >= 1 and seated and math.hypot(self.vx,self.vy) < .065
        if resting and index == self._seat_pocket:
            self._seat_time += self.DT
        else:
            self._seat_pocket, self._seat_time = index, 0.0
        if self._seat_time >= .14:
            self.wheel_speed = 0.0
            self.settled_at = self.t
            if self.round_cancelled:
                self.mode = 'recovery_ready'
            else:
                self.result_index = self.pocket
                self.mode = 'result'

    def begin_return(self):
        if self.mode not in {'result','recovery_ready'} or self.pocket is None:
            return False
        self.return_started_at = self.t
        self.return_angle = self.wheel_angle
        if self.next_direction is not None:
            self.direction = self.next_direction
        pocket_angle = (self.wheel_angle+(self.pocket+.5)*self.STEP) % self.TAU
        self.return_travel = ((-pocket_angle) % self.TAU if self.direction>0
                              else -(pocket_angle % self.TAU))
        self.return_seconds = max(1.6, 1.875*abs(self.return_travel)/self.RETURN_SPEED)
        self.mode = 'returning'
        return True

    def _step_return(self):
        u = min(1.0, (self.t-self.return_started_at)/self.return_seconds)
        travel = self.return_travel*self._ease(u)
        self.wheel_angle = (self.return_angle+travel) % self.TAU
        self.wheel_speed = self.return_travel*self._ease_velocity(u)/self.return_seconds
        self._step_ball()
        if u >= 1:
            self.wheel_speed = 0.0
            self.load_started_at = self.t
            self._loading_rest = 0.0
            self.mode = 'loading'

    def _step_loading(self):
        self._step_ball()
        if abs(self.y-self.LAUNCH_Y)<.001 and math.hypot(self.vx,self.vy)<.025:
            self._loading_rest += self.DT
        else:
            self._loading_rest = 0.0
        if self._loading_rest >= .20:
            self.mode = 'waiting'

    def advance(self, seconds):
        self.remainder += max(0.0, seconds)
        while self.remainder+1e-12 >= self.DT:
            self.remainder = max(0.0, self.remainder-self.DT)
            self._previous = (self.x, self.y, self.wheel_angle, self.wheel_speed)
            self.t += self.DT
            if self.mode == 'waiting':
                old = self.wheel_speed
                change = self.direction*self.FAST_SPEED-old
                self.wheel_speed = old+max(-5*self.DT,min(5*self.DT,change))
                self.wheel_angle = (self.wheel_angle+(old+self.wheel_speed)*self.DT/2) % self.TAU
                self._step_ball()
            elif self.mode == 'drop':
                elapsed = self.t - self.drop_started_at
                travel, self.wheel_speed = self._drop_motor_state(elapsed)
                self.wheel_angle = (self.drop_angle + travel) % self.TAU
                self._step_drop()
            elif self.mode == 'storage':
                self._step_storage()
            elif self.mode == 'recovery':
                self._step_recovery()
            elif self.mode == 'recovery_drop':
                self._step_drop()
            elif self.mode in {'result','recovery_ready'}:
                self._step_ball()
            elif self.mode == 'returning':
                self._step_return()
            elif self.mode == 'loading':
                self._step_loading()

    def render_state(self):
        alpha = min(1.0, self.remainder/self.DT)
        px, py, pw, ps = self._previous
        x, y = px+(self.x-px)*alpha, py+(self.y-py)*alpha
        delta = (self.wheel_angle-pw+math.pi) % self.TAU-math.pi
        wheel = (pw+delta*alpha) % self.TAU
        speed = ps+(self.wheel_speed-ps)*alpha
        return wheel, speed, math.atan2(x, -y) % self.TAU, 0.0, math.hypot(x, y), 0.0

    @property
    def stopped(self):
        return self.mode in {'result', 'loading'} and abs(self.wheel_speed) < 1e-9

    @property
    def occupied_pocket(self):
        """Live cup occupancy, including bounces before the final result."""
        return self.occupied_pocket_at(math.atan2(self.x,-self.y),math.hypot(self.x,self.y),self.wheel_angle)

    def occupied_pocket_at(self, angle, radius, wheel):
        """Use the same slot boundaries for simulation and interpolated frames."""
        if self.exit_position is None or radius<self.DIVIDER_INNER:
            return None
        if self.mode == 'waiting':
            return None
        return int(((angle-wheel) % self.TAU)/self.STEP)


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
}

# Standard announced bets: (table type, covered numbers, unit-chip count).
# Source: Spielbanken Bayern, Roulette rules, March 2023, series bets table.
# https://www.spielbanken-bayern.de/storage/filemanager/files/shares/Spielregeln/Englisch/Spielregeln_Roulette_2023_eng.pdf
FRENCH_BETS = {
    "voisins": {
        "label": "Voisins du Zéro", "title": "Voisins\ndu Zéro", "zh": "零旁注板",
        "legs": (("street", (0, 2, 3), 2), ("split", (4, 7), 1),
                 ("split", (12, 15), 1), ("split", (18, 21), 1),
                 ("split", (19, 22), 1), ("corner", (25, 26, 28, 29), 2),
                 ("split", (32, 35), 1)),
    },
    "tiers": {
        "label": "Tiers du Cylindre", "title": "Tiers du\nCylindre", "zh": "三分之一轮板",
        "legs": tuple(("split", pair, 1) for pair in
                      ((5, 8), (10, 11), (13, 16), (23, 24), (27, 30), (33, 36))),
    },
    "orphelins": {
        "label": "Orphelins", "title": "Orphelins", "zh": "孤儿序列",
        "legs": (("straight", (1,), 1), ("split", (6, 9), 1),
                 ("split", (14, 17), 1), ("split", (17, 20), 1),
                 ("split", (31, 34), 1)),
    },
    "zero": {
        "label": "Jeu Zéro", "title": "Jeu Zéro", "zh": "零号游戏",
        "legs": (("split", (0, 3), 1), ("split", (12, 15), 1),
                 ("straight", (26,), 1), ("split", (32, 35), 1)),
    },
}
CHIP_TRANSFER_SECONDS = 0.75
# Rotate only the racetrack display; retain European wheel order.
# Racetrack betting selector follows the European wheel order.
# Start at 33 to center the seven-number zero shortcut on the right cap.
# Wheel physics keep ROULETTE_SEQUENCE.
_track_start = ROULETTE_SEQUENCE.index("33")
RACETRACK_SEQUENCE = ROULETTE_SEQUENCE[_track_start:] + ROULETTE_SEQUENCE[:_track_start]
del _track_start
RACETRACK_REGION_ORDER = ("tiers", "orphelins", "voisins", "zero")
RACETRACK_LEFT, RACETRACK_RIGHT, RACETRACK_CY = 106.0, 402.0, 108.0
RACETRACK_OUTER_R, RACETRACK_INNER_R = 94.0, 50.0
RACETRACK_NUMBER_R, RACETRACK_CHIP_R = 83.0, 61.0
# Preserve each region's normal fill; hover uses a shared light-blue fill,
# dark text and a dark-blue outline with a light halo for clear state contrast.
RACETRACK_REGION_COLORS = {
    "tiers": ("#164E63", "#B9E1EE"),
    "orphelins": ("#312E81", "#B9E1EE"),
    "voisins": ("#065F46", "#B9E1EE"),
    "zero": ("#78350F", "#B9E1EE"),
}
RACETRACK_REGION_TEXT = "#FFFFFF"
RACETRACK_REGION_HOVER_TEXT = "#102A38"
RACETRACK_REGION_FOCUS = "#0B4A6B"
RACETRACK_REGION_EDGE = "#CBD5E1"
RACETRACK_FOCUS_HALO = "#E0F2FE"

OUTCOME_COLORS = {
    "0": "#008A68",
}

OUTCOME_TEXT_COLORS = {
    "0": "#ffffff",
}

for n in range(1, 37):
    s = str(n)
    if n in RED_NUMBERS:
        OUTCOME_COLORS[s] = "#ff2a23"
    else:
        OUTCOME_COLORS[s] = "#050505"
    OUTCOME_TEXT_COLORS[s] = "#ffffff"

COLOR_GROUPS = {
    "Red": {"results": {str(n) for n in RED_NUMBERS}},
    "Black": {"results": {str(n) for n in range(1, 37)} - {str(n) for n in RED_NUMBERS}},
    "Green": {"results": {"0"}},
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
}


# =========================================================
# History store
# =========================================================

class PlinkoHistory:
    ORDERED_TOP_KEYS = ["Total", "Red", "Black", "Green", "Record1", "Record2"]

    RECORD1_KEY = "Record1"
    RECORD2_KEY = "Record2"
    LEGACY_RECORD_KEY = "Record"

    RECORD1_MAX = 54
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

        # 兼容旧版：旧的 Record 自动并入 Record1
        legacy_record1 = data.get(self.RECORD1_KEY)
        if not isinstance(legacy_record1, dict):
            legacy_record1 = data.get(self.LEGACY_RECORD_KEY, {})
        payload[self.RECORD1_KEY] = self._clean_record(legacy_record1)
        payload[self.RECORD2_KEY] = self._clean_record(data.get(self.RECORD2_KEY, {}))
        return payload

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
        # 获取当前 Record1 的所有条目（长度为 54，空位为 {"result":"","color":""}）
        existing = self._record_to_ordered_list(self.RECORD1_KEY, self.RECORD1_MAX)

        # 统计实际非空记录的数量
        actual_count = sum(1 for entry in existing if entry["result"])

        # 只有当已经达到 54 条记录，需要添加第 55 条时，才删除最后 6 条（49_Data ~ 54_Data）
        if actual_count >= self.RECORD1_MAX:
            # 保留前 48 条，丢弃索引 48~53（即 49_Data ~ 54_Data）
            existing = existing[:48]

        # 将新结果插入头部，然后拼接上所有非空旧记录（已过滤空位）
        new_entries = [{"result": result, "color": color}] + [e for e in existing if e["result"]]

        # 确保总数不超过 RECORD1_MAX（54）
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
RACETRACK_CONTROLS_BG = "#C6E9F5"
# Symmetric distance from the hovered number: centre retains the accepted
# blue; each outward step is lighter, with a blue tint even at distance five.
RACETRACK_NEIGHBOR_HOVER_FILLS = (
    "#B9E1EE", "#C3E6F1", "#CDEBF4", "#D7EFF6", "#E1F3F9", "#EAF6FB",
)
RACETRACK_NEIGHBOR_HOVER_FILL = RACETRACK_NEIGHBOR_HOVER_FILLS[0]
RACETRACK_NEIGHBOR_HOVER_TEXT = "#102A38"
RACETRACK_NEIGHBOR_HOVER_EDGE = "#0B4A6B"
RACETRACK_NEIGHBOR_COLORS = (
    "#F5D68A",  # centre: gold
    "#40B8E0",  # +/-1: cyan-blue, then progressively lighter
    "#70CBEA",
    "#9FDCF2",
    "#C7EBF8",
    "#EAF8FD",
)
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

    layout = get_board_layout(scale)
    x0 = layout["x0"]
    y0 = layout["y0"]
    num_w = layout["num_w"]
    num_h = layout["num_h"]
    zero_w = layout["zero_w"]
    zero_h = layout["zero_h"]
    dozen_h = layout["dozen_h"]
    outer_h = layout["outer_h"]
    col_w = layout["col_w"]
    zero_x1 = layout["zero_x1"]
    zero_x2 = layout["zero_x2"]
    grid_x1 = layout["grid_x1"]
    col_x1 = layout["col_x1"]
    col_x2 = layout["col_x2"]
    rows = layout["rows"]

    dozen_y1 = y0 + 3 * num_h
    dozen_y2 = dozen_y1 + dozen_h
    outer_y1 = dozen_y2
    outer_y2 = outer_y1 + outer_h

    # European single zero
    zero_height = 2 * zero_h
    canvas.create_rectangle(
        int(zero_x1), int(y0),
        int(zero_x2), int(y0 + zero_height),
        fill=TEAL,
        outline=CYAN,
        width=1
    )
    canvas.create_text(
        int(zero_x1 + zero_w / 2),
        int(y0 + zero_height / 2),
        text="0",
        fill=TEXT,
        font=("Arial", 11, "bold"),
        angle=90
    )

    for r in range(3):
        y1 = y0 + r * num_h
        y2 = y1 + num_h
        for c in range(12):
            x1 = grid_x1 + c * num_w
            x2 = x1 + num_w
            n = rows[r][c]
            fill = RED if n in RED_NUMBERS else BLACK
            canvas.create_rectangle(
                int(x1), int(y1), int(x2), int(y2),
                fill=fill, outline=CYAN, width=2
            )
            canvas.create_text(
                int((x1 + x2) / 2),
                int((y1 + y2) / 2),
                text=str(n),
                fill=TEXT,
                font=("Arial", 11, "bold"),
                angle=90
            )

    for r in range(3):
        y1 = y0 + r * num_h
        y2 = y1 + num_h
        draw_cell(
            canvas,
            int(col_x1), int(y1), int(col_x2), int(y2),
            fill=DARK_BLUE,
            text="2:1",
            text_font=("Arial", 11, "bold"),
            text_angle=90,
            outline=CYAN
        )

    dozen_w = 4 * num_w
    draw_cell(
        canvas,
        int(grid_x1), int(dozen_y1), int(grid_x1 + dozen_w), int(dozen_y2),
        fill=DARK_BLUE, text="1st 12",
        text_font=("Arial", 11, "bold")
    )
    draw_cell(
        canvas,
        int(grid_x1 + dozen_w), int(dozen_y1), int(grid_x1 + 2 * dozen_w), int(dozen_y2),
        fill=DARK_BLUE, text="2nd 12",
        text_font=("Arial", 11, "bold")
    )
    draw_cell(
        canvas,
        int(grid_x1 + 2 * dozen_w), int(dozen_y1), int(grid_x1 + 3 * dozen_w), int(dozen_y2),
        fill=DARK_BLUE, text="3rd 12",
        text_font=("Arial", 11, "bold")
    )

    outer_y1 = dozen_y2
    outer_y2 = outer_y1 + outer_h

    grid_x2 = layout["grid_x2"]
    seg_w = (grid_x2 - grid_x1) / 6
    for idx, (label, fill) in enumerate((
            ("1 to 18", DARK_BLUE), ("EVEN", DARK_BLUE), ("RED", RED),
            ("BLACK", BLACK), ("ODD", DARK_BLUE), ("19 to 36", DARK_BLUE))):
        x1 = grid_x1 + idx * seg_w
        x2 = grid_x2 if idx == 5 else grid_x1 + (idx + 1) * seg_w
        draw_cell(canvas, int(x1), int(outer_y1), int(x2), int(outer_y2),
                  fill=fill, text=label, text_font=("Arial", 11, "bold"))

    # Street bet lines: 12 个横线下注位
    street_y = int(round(dozen_y1))
    for col in range(12):
        x1 = int(round(grid_x1 + col * num_w))
        x2 = int(round(x1 + num_w))
        canvas.create_line(
            x1 + 2, street_y, x2 - 2, street_y,
            fill="#33624b",
            width=4,
            capstyle=tk.ROUND
        )


def roulette_color(result: str) -> str:
    if result in {"0"}:
        return "Green"
    try:
        n = int(result)
    except Exception:
        return "Green"
    return "Red" if n in RED_NUMBERS else "Black"


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


class PlinkoGameGUI(tk.Frame):
    RESULT_DISPLAY_MS = 6000
    TOP_READY_SECONDS = 4.0

    def __init__(self, parent, initial_balance=1_000_000, username="Guest",
                 on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=1150, height=757)
        self.pack_propagate(False)
        self.parent = parent
        self.root = self.winfo_toplevel()
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self._embedded = not bool(getattr(self.root, "_plinko_european_standalone", False))
        self._previous_title = self.root.title()
        self._previous_geometry = self.root.geometry()
        self._previous_close_protocol = self.root.protocol("WM_DELETE_WINDOW")
        self.root.title("欧式落球轮盘")
        self.root.geometry("1150x757+50+10")
        self.root.resizable(False, False)
        self.root.configure(bg=ROOT_BG)

        self.username = username
        self.balance = float(load_balance(username, float(initial_balance)))
        self.history = PlinkoHistory(plinko_log_path())

        self.geometry_model = RouletteBoardGeometry(scale=BOARD_SCALE)
        self.marker_results = []
        self.marker_rows = 6
        self.marker_cols = 9

        self.bet_multiplier = 1
        self.selected_bet_amount = 25
        self.selected_chip_color = "#ffffff"
        self.selected_chip = None
        self.chip_buttons = []

        self.round_state = "betting"
        self._spin_job = None
        self._closing = False
        self._enter_down = False
        self._enter_bindings = {}
        self._locked_numbers = set()
        self._round_settled = True
        self.physics = None
        self.ball_height = 0.0
        self.ball_visible = False
        self.ball_radius = 192.0
        self.ball_pocket_index = None

        self.last_bets = {}
        self.last_bet_colors = {}
        self.betting_view = "table"
        self.last_betting_view = "table"
        self.racetrack_neighbors = 2
        self.racetrack_hover = None
        self.region_hover = None
        # Table stakes are charged once; regions retain their origin only.
        self.region_bets = {}
        self.last_region_bets = {}
        self._chip_transfer_job = None
        self._chip_transfer_active = False
        self._chip_transfer_items = []

        self.current_wheel_offset = (secrets.randbelow(len(ROULETTE_SEQUENCE)) + secrets.randbits(53)/2**53)*360/len(ROULETTE_SEQUENCE)
        self.wheel_velocity = 0.0
        self.wheel_acceleration = 0.0
        self._last_physics_time = None
        self.is_spinning = False

        self.pointer_angle = 0.0
        self.pointer_velocity = 0.0
        self.pointer_acceleration = 0.0
        self.is_pointer_spinning = False

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
        self._result_finish_job = None
        self._launch_ready_at = None
        self._round_refund_handled = False
        self._locked_stake = 0
        self._result_flash_state = False
        self._result_flash_spot_ids = set()

        self.distribution_display_count = 50   # 默认分析最近50局
        self.distribution_frame = None         # 分布面板主框架
        self.distribution_labels = {}          # 存储各统计标签的引用

        # 用于存储最后一局的开奖物理数据
        self.last_spin_data = None
        # 结果弹窗防重复
        self.detail_window = None

        # 饼图模式: "sector" 区间分布(1-12/13-24/25-36/0) 或 "row" 每行分布
        self.pie_mode = "sector"

        self._build_ui()
        self._sync_marker_from_history()
        self._start_new_round()
        self._start_startup_rotation()

        self.focus_force()                         # 确保窗口获得焦点
        # Intercept before Button's platform-specific Return binding (Windows
        # may otherwise invoke the button and then advance the game twice).
        self._enter_tag = f"PlinkoEnter_{id(self)}"
        for key in ("Return", "KP_Enter"):
            for action, callback in (("KeyPress", self._handle_enter), ("KeyRelease", self._release_enter)):
                sequence = f"<{action}-{key}>"
                self._enter_bindings[sequence] = self.root.bind_class(self._enter_tag, sequence, callback)
        self._enter_bindings['<FocusOut>'] = self.root.bind_class(
            self._enter_tag, '<FocusOut>', self._cancel_held_enter)
        widgets = [self]
        while widgets:
            widget = widgets.pop()
            widget.bindtags((self._enter_tag, *widget.bindtags()))
            widgets.extend(widget.winfo_children())
        self.root.bindtags((self._enter_tag, *self.root.bindtags()))

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        main = tk.Frame(self, bg=ROOT_BG)
        main.pack(fill=tk.BOTH, expand=True)

        # 左右整体重新分配宽度，给右侧统计区留更多空间
        left_frame = tk.Frame(main, bg=ROOT_BG, width=540)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=0)
        left_frame.pack_propagate(False)

        right_frame = tk.Frame(main, bg=ROOT_BG, width=594)
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
            height=420,
            bg=ROOT_BG,
            highlightthickness=0,
            bd=0
        )
        self.wheel_canvas.pack(fill=tk.X)

        # Joined selectors sit between the wheel and the active betting board.
        view_bar = tk.Frame(parent, bg="#D8B46A", bd=1, relief=tk.SOLID)
        view_bar.pack(pady=(0, 4))
        self.betting_view_buttons = {}
        for mode, label in (("table", "轮盘布局 Roulette Layout"), ("racetrack", "跑道盘 Racetrack")):
            button = tk.Button(
                view_bar, text=label, width=26, font=("Arial", 10, "bold"),
                relief=tk.FLAT, bd=0, pady=3, cursor="hand2",
                command=lambda selected=mode: self._switch_betting_view(selected))
            button.pack(side=tk.LEFT, fill=tk.Y)
            self.betting_view_buttons[mode] = button

        betting_area = tk.Frame(parent, bg=ROOT_BG)
        betting_area.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        betting_left = tk.Frame(betting_area, bg=ROOT_BG)
        betting_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self._populate_betting_area(betting_left)

    def _populate_betting_area(self, parent):
        self.board_canvas = tk.Canvas(
            parent,
            width=BOARD_W,
            height=BOARD_H,
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

        self.racetrack_canvas = tk.Canvas(
            parent, width=BOARD_W, height=BOARD_H, bg=ROOT_BG,
            highlightthickness=0, bd=0)
        self.racetrack_canvas.bind("<Button-1>", self._on_racetrack_click)
        self.racetrack_canvas.bind("<Button-3>", self._on_racetrack_right_click)
        self.racetrack_canvas.bind("<Motion>", self._on_racetrack_motion)
        self.racetrack_canvas.bind("<Leave>", self._on_racetrack_leave)

        self.racetrack_controls = tk.Frame(self.racetrack_canvas, bg=RACETRACK_CONTROLS_BG)
        tk.Label(self.racetrack_controls, text="邻号: ", bg=RACETRACK_CONTROLS_BG,
                 fg="#173F58", font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        choices = tk.Frame(self.racetrack_controls, bg=RACETRACK_CONTROLS_BG)
        choices.pack(side=tk.LEFT)
        self.racetrack_neighbor_buttons = {}
        for count in range(6):
            button = tk.Button(
                choices, text=str(count), width=3, bd=0, pady=2,
                font=("Arial", 13, "bold"), cursor="hand2",
                relief=tk.FLAT, highlightthickness=1,
                highlightbackground="#99C6DA", highlightcolor="#2F759B",
                activebackground="#D4EAF6", activeforeground="#173F58",
                disabledforeground="#718795",
                command=lambda n=count: self._set_racetrack_neighbors(n))
            button.pack(side=tk.LEFT, padx=2)
            self.racetrack_neighbor_buttons[count] = button
        self._draw_racetrack()
        self._update_betting_view_controls()

    def _can_switch_betting_view(self):
        return self.round_state == "betting" and not self._chip_transfer_active

    def _switch_betting_view(self, mode):
        if mode not in ("table", "racetrack"):
            return
        if not self._can_switch_betting_view():
            return
        self.betting_view = mode
        self.racetrack_hover = None
        self.region_hover = None
        self.board_canvas.pack_forget()
        self.racetrack_canvas.pack_forget()
        active = self.board_canvas if mode == "table" else self.racetrack_canvas
        active.pack(anchor="n")
        self._repaint_all_chips()
        self._update_betting_view_controls()
        self._update_repeat_button_state()

    def _update_betting_view_controls(self):
        locked = not self._can_switch_betting_view()
        for mode, button in self.betting_view_buttons.items():
            selected = mode == self.betting_view
            button.config(
                state=tk.DISABLED if locked else tk.NORMAL,
                bg="#D8B46A" if selected else "#284C40",
                fg="#2A1B08" if selected else "white",
                disabledforeground="#65502B" if selected else "#9AA99F",
                activebackground="#E8C67F", cursor="arrow" if locked else "hand2")
        for count, button in self.racetrack_neighbor_buttons.items():
            button.config(state=tk.NORMAL if self.round_state == "betting" else tk.DISABLED,
                          bg="#438EB7" if count == self.racetrack_neighbors else "#E8F5FB",
                          fg="white" if count == self.racetrack_neighbors else "#173F58",
                          disabledforeground="white" if count == self.racetrack_neighbors else "#718795",
                          activebackground="#438EB7" if count == self.racetrack_neighbors else "#D4EAF6",
                          activeforeground="white" if count == self.racetrack_neighbors else "#173F58",
                          highlightbackground="#2F759B" if count == self.racetrack_neighbors else "#99C6DA",
                          cursor="hand2" if self.round_state == "betting" else "arrow")

    def _set_racetrack_neighbors(self, count):
        if self.round_state != "betting" or count not in range(6):
            return
        self.racetrack_neighbors = count
        self._update_betting_view_controls()
        self._draw_racetrack()

    def _racetrack_numbers(self, number):
        index = ROULETTE_SEQUENCE.index(number)
        return [ROULETTE_SEQUENCE[(index + offset) % len(ROULETTE_SEQUENCE)]
                for offset in range(-self.racetrack_neighbors, self.racetrack_neighbors + 1)]

    @staticmethod
    def _racetrack_distance(number, center):
        distance = abs(ROULETTE_SEQUENCE.index(number) - ROULETTE_SEQUENCE.index(center))
        return min(distance, len(ROULETTE_SEQUENCE) - distance)

    def _racetrack_amount(self, numbers):
        # Same base-unit limits as the main board; cap every leg equally.
        remaining = [self._bet_limit_for_spot(self._find_spot_by_id("straight_" + number))
                     - self.current_bets.get("straight_" + number, 0) for number in numbers]
        return max(0, min(int(self.selected_bet_amount), *remaining))

    @staticmethod
    def _racetrack_point(fraction, radius):
        """Sample matching boundaries of a stadium-shaped ring, clockwise."""
        left, right, cy = RACETRACK_LEFT, RACETRACK_RIGHT, RACETRACK_CY
        mid_radius = (RACETRACK_OUTER_R + RACETRACK_INNER_R) / 2
        straight = right - left
        arc = math.pi * mid_radius
        distance = (fraction % 1.0) * (2 * straight + 2 * arc)
        if distance < straight:
            return left + distance, cy - radius
        distance -= straight
        if distance < arc:
            angle = -math.pi / 2 + distance / mid_radius
            return right + radius * math.cos(angle), cy + radius * math.sin(angle)
        distance -= arc
        if distance < straight:
            return right - distance, cy + radius
        angle = math.pi / 2 + (distance - straight) / mid_radius
        return left + radius * math.cos(angle), cy + radius * math.sin(angle)

    def _draw_racetrack(self):
        canvas = self.racetrack_canvas
        canvas.delete("track")
        region_selected = self.region_hover in FRENCH_BETS and self.round_state == "betting"
        number_selected = (not region_selected and self.racetrack_hover in ROULETTE_SEQUENCE
                           and self.round_state == "betting")
        hovered = ({str(n) for _, numbers, _ in FRENCH_BETS[self.region_hover]["legs"] for n in numbers}
                   if region_selected else set(self._racetrack_numbers(self.racetrack_hover))
                   if number_selected else set())
        # Region stakes stay grouped on this view, including during spin/result.
        pending = self._region_contributions()
        highlights = []
        for index, number in enumerate(RACETRACK_SEQUENCE):
            fractions = [(index + step / 6) / len(RACETRACK_SEQUENCE) for step in range(7)]
            points = [self._racetrack_point(t, RACETRACK_OUTER_R) for t in fractions]
            points += [self._racetrack_point(t, RACETRACK_INNER_R) for t in reversed(fractions)]
            tags = ("track", "track_number:" + number)
            winning = self.round_state == "result" and self.center_display_result == number
            flashing = winning and self._result_flash_state
            neighbor_hover = number_selected and number in hovered
            primary = number_selected and number == self.racetrack_hover
            # A region can cover numbers far beyond the five neighbour colours.
            # Only number-neighbour selection uses distance-based colours.
            distance = self._racetrack_distance(number, self.racetrack_hover) if number_selected and number in hovered else 0
            color_index = min(max(0, distance), len(RACETRACK_NEIGHBOR_COLORS) - 1)
            highlight_color = (RACETRACK_NEIGHBOR_HOVER_EDGE if neighbor_hover else
                               RACETRACK_REGION_FOCUS if region_selected else RACETRACK_NEIGHBOR_COLORS[color_index])
            canvas.create_polygon(
                *[coord for point in points for coord in point],
                fill="#ffffff" if flashing else (RACETRACK_NEIGHBOR_HOVER_FILLS[min(distance, 5)] if neighbor_hover else OUTCOME_COLORS[number]),
                outline=RACETRACK_NEIGHBOR_HOVER_EDGE if neighbor_hover else "#CFD6D0", width=2, tags=tags)
            if number in hovered or winning:
                highlights.append((primary or winning, points, highlight_color, tags))
            center = (index + 0.5) / len(RACETRACK_SEQUENCE)
            x, y = self._racetrack_point(center, RACETRACK_NUMBER_R)
            # Neighbour hover changes only the selected pockets; result flashing stays unchanged.
            text_color = "black" if flashing else (RACETRACK_NEIGHBOR_HOVER_TEXT if neighbor_hover else "white")
            canvas.create_text(x, y, text=number, fill=text_color,
                               font=("Arial", 10, "bold"), tags=tags)
            spot_id = "straight_" + number
            amount = self.current_bets.get(spot_id, 0) - pending.get(spot_id, 0)
            if amount > 0:
                fill = self._chip_fill_color_for_amount(amount)
                text_color = self._spot_text_color(fill)
                info = self.result_chip_display.get(spot_id)
                if self.round_state == "result" and info and self._result_flash_state:
                    amount = amount * (BET_ODDS["straight"] + 1)
                    fill, text_color = self._result_chip_style(amount)
                x, y = self._racetrack_point(center, RACETRACK_CHIP_R)
                canvas.create_oval(x - 10, y - 9, x + 10, y + 9,
                                   fill=fill, outline="#D8B46A", width=1, tags=tags)
                canvas.create_text(x, y, text=self._format_win_amount(amount), fill=text_color,
                                   font=("Arial", 7, "bold"), tags=tags)
        # Paint outlines after the pockets, with the central selection on top.
        for primary, points, color, tags in sorted(highlights, key=lambda entry: entry[0]):
            if region_selected:
                canvas.create_line(
                    *[coord for point in points + [points[0]] for coord in point],
                    fill=RACETRACK_FOCUS_HALO, width=6, joinstyle=tk.ROUND, tags=tags)
            canvas.create_line(
                *[coord for point in points + [points[0]] for coord in point],
                fill=color, width=3, joinstyle=tk.ROUND, tags=tags)
        x1, y1, x2, y2, radius = BOARD_W / 2 - 190, 214, BOARD_W / 2 + 190, 266, 10
        canvas.create_polygon(
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
            smooth=True, splinesteps=12,
            fill=RACETRACK_CONTROLS_BG, outline="#9DCFE3", width=1,
            tags=("track", "neighbor_background"))
        if not hasattr(self, "racetrack_controls_item"):
            self.racetrack_controls_item = canvas.create_window(
                BOARD_W / 2, 239, window=self.racetrack_controls)
        self._add_help_button_on_racetrack()
        self._draw_french_regions()

    def _add_help_button_on_racetrack(self):
        canvas = self.racetrack_canvas
        cx, cy, radius = 34, 239, 10
        tags = ("track", "racetrack_help")
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                           fill="#F5E6B8", outline="#D4AF37", width=2, tags=tags)
        canvas.create_text(cx, cy, text="?", font=("Arial", 12, "bold"),
                           fill="#2A1B08", tags=tags)
        canvas.tag_bind("racetrack_help", "<Enter>", lambda e: canvas.config(cursor="hand2"))
        canvas.tag_bind("racetrack_help", "<Leave>", lambda e: canvas.config(cursor=""))
        canvas.tag_bind("racetrack_help", "<Button-1>", lambda e: self.show_game_instructions())

    def _racetrack_number_at(self, x, y):
        for index, number in enumerate(RACETRACK_SEQUENCE):
            fractions = [(index + step / 6) / len(RACETRACK_SEQUENCE) for step in range(7)]
            points = [self._racetrack_point(t, RACETRACK_OUTER_R) for t in fractions]
            points += [self._racetrack_point(t, RACETRACK_INNER_R) for t in reversed(fractions)]
            inside = False
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
                cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
                if (abs(cross) < 1e-7 and min(x1, x2) - 1e-7 <= x <= max(x1, x2) + 1e-7
                        and min(y1, y2) - 1e-7 <= y <= max(y1, y2) + 1e-7):
                    return number
                if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                    inside = not inside
            if inside:
                return number
        return None

    def _on_racetrack_motion(self, event):
        region = self._racetrack_region_at(event.x, event.y)
        # At shared edges, a sector takes precedence over an underlying pocket tag.
        number = None if region is not None else self._racetrack_number_at(event.x, event.y)
        if number != self.racetrack_hover or region != self.region_hover:
            self.racetrack_hover, self.region_hover = number, region
            self.racetrack_canvas.config(cursor="hand2" if number or region else "")
            self._draw_racetrack()

    def _on_racetrack_leave(self, event):
        self.racetrack_hover = None
        self.region_hover = None
        self._draw_racetrack()

    def _on_racetrack_click(self, event):
        region = self._racetrack_region_at(event.x, event.y)
        if region is not None:
            self._place_region_bet(region)
            return
        number = self._racetrack_number_at(event.x, event.y)
        if number is not None:
            self._place_racetrack_bet(number)

    def _on_racetrack_right_click(self, event):
        if self.round_state != "betting" or self.betting_view != "racetrack":
            return
        region = self._racetrack_region_at(event.x, event.y)
        if region is not None:
            self._clear_region_bet(region)
            return
        number = self._racetrack_number_at(event.x, event.y)
        if number is not None:
            self.clear_single_bet("straight_" + number)

    def _place_racetrack_bet(self, number):
        if self.round_state != "betting" or self.betting_view != "racetrack":
            return
        numbers = self._racetrack_numbers(number)
        selected_amount = int(self.selected_bet_amount)
        if selected_amount <= 0:
            return
        # 计算每个号码实际可增加的金额
        additions = {}
        total_base = 0
        for num in numbers:
            spot_id = "straight_" + num
            spot = self._find_spot_by_id(spot_id)
            if not spot:
                continue
            limit = self._bet_limit_for_spot(spot)
            existing = self.current_bets.get(spot_id, 0)
            remaining = limit - existing
            if remaining <= 0:
                continue
            add = min(selected_amount, remaining)
            additions[spot_id] = add
            total_base += add
        if total_base <= 0:
            messagebox.showwarning("下注上限", "组合中所有号码均已达到下注上限。")
            return
        total_cost = total_base * self.bet_multiplier
        if self.balance < total_cost:
            messagebox.showwarning("余额不足", f"整组下注需要 ${total_cost:,.0f}，余额不足。")
            return
        self.balance -= total_cost
        for spot_id, add in additions.items():
            self.current_bets[spot_id] = self.current_bets.get(spot_id, 0) + add
            self.current_bet_colors[spot_id] = self._chip_fill_color_for_amount(self.current_bets[spot_id])
        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

    def _region_polygon(self, region):
        """Tile the capsule using the *same* inner edges as the number pockets.

        Cut endpoints are derived from European number transitions, never from
        guessed x coordinates. Jeu Zero is the displayed subset of Voisins;
        selecting Voisins still bets all 17 numbers, including that subset.
        """
        count = len(RACETRACK_SEQUENCE)
        boundary = {number: i for i, number in enumerate(RACETRACK_SEQUENCE)}

        def arc(first, stop):
            start = boundary[first]
            end = boundary[stop]
            if end <= start:
                end += count
            # Identical six subdivisions per pocket to _draw_racetrack.
            return [self._racetrack_point((step / 6) / count, RACETRACK_INNER_R)
                    for step in range(start * 6, end * 6 + 1)]

        if region == "tiers":
            # 6|27 ... 33|1: the twelve-number arc opposite zero.
            return arc("27", "1")
        if region == "orphelins":
            # Two disjoint wheel arcs joined across the inner capsule.
            return arc("1", "22") + arc("17", "27")
        if region == "voisins":
            # The remaining Voisins arcs, with the Jeu Zero shortcut cut out.
            return arc("22", "12") + [(RACETRACK_RIGHT - 40, RACETRACK_CY)] + arc("19", "17")
        if region == "zero":
            # 28|12 ... 15|19: seven pockets around zero, including both ends.
            # Share a short inward point with Voisins to fit both fixed label
            # lines. Outer endpoints still meet 28|12 and 15|19 exactly.
            return arc("12", "19") + [(RACETRACK_RIGHT - 40, RACETRACK_CY)]
        raise KeyError(region)

    def _region_center(self, region):
        """Area centroid: chip origins follow the real curved/slanted region."""
        points = self._region_polygon(region)
        twice_area = cx = cy = 0.0
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
            cross = x1 * y2 - x2 * y1
            twice_area += cross
            cx += (x1 + x2) * cross
            cy += (y1 + y2) * cross
        return cx / (3 * twice_area), cy / (3 * twice_area)

    def _region_legs(self, region):
        legs = []
        for kind, numbers, units in FRENCH_BETS[region]["legs"]:
            covered = {str(n) for n in numbers}
            spot = next(s for s in self.bet_spots if s["type"] == kind and s["numbers"] == covered)
            legs.append((spot, units))
        return legs

    def _region_contributions(self):
        amounts = {}
        for region, unit_amount in self.region_bets.items():
            for spot, units in self._region_legs(region):
                amounts[spot["id"]] = amounts.get(spot["id"], 0) + unit_amount * units
        return amounts

    def _draw_french_regions(self):
        canvas = self.racetrack_canvas
        for region in RACETRACK_REGION_ORDER:
            info = FRENCH_BETS[region]
            points = self._region_polygon(region)
            cx, cy = self._region_center(region)
            tags = ("track", "track_region:" + region)
            selected = self.region_hover == region and self.round_state == "betting"
            winning_region = self.round_state == "result" and any(
                self.center_display_result in spot["numbers"]
                for spot, _ in self._region_legs(region))
            flashing = winning_region and self._result_flash_state
            region_fill = "#E0F2FE" if flashing else RACETRACK_REGION_COLORS[region][int(selected)]
            label_fill = "#0F172A" if flashing else (RACETRACK_REGION_HOVER_TEXT if selected else RACETRACK_REGION_TEXT)
            edge_fill = "#0F172A" if flashing else (RACETRACK_REGION_FOCUS if selected else RACETRACK_REGION_EDGE)
            canvas.create_polygon(*[v for point in points for v in point],
                                  fill=region_fill, outline=edge_fill, width=2, tags=tags)
            # Fixed bilingual labels: chips are intentionally painted over them.
            # Fixed offsets keep the two wider labels inside the slanted edges.
            # Neither placement nor font size depends on the presence of a chip.
            dx, dy = {"tiers": (-6, 9), "voisins": (-8, -8)}.get(region, (0, 0))
            label_x, label_y = cx + dx, cy + dy
            canvas.create_text(label_x, label_y - 9, text=info["label"], fill=label_fill,
                               font=("Arial", 9, "bold"), tags=tags)
            canvas.create_text(label_x, label_y + 10, text=info["zh"], fill=label_fill,
                               font=("Microsoft YaHei", 9), tags=tags)
            unit_amount = self.region_bets.get(region, 0)
            amount = unit_amount * sum(leg[2] for leg in info["legs"])
            if self.round_state in {"result", "returning"} and amount:
                payout = sum(unit_amount * units * (spot["payout"] + 1)
                             for spot, units in self._region_legs(region)
                             if self.center_display_result in spot["numbers"])
                if not payout:
                    amount = 0
                elif self._result_flash_state:
                    amount = payout
            if amount:
                fill = self._chip_fill_color_for_amount(amount)
                text_color = self._spot_text_color(fill)
                if self.round_state == "result" and self._result_flash_state:
                    fill, text_color = self._result_chip_style(amount)
                canvas.create_oval(cx - 14, cy - 12, cx + 14, cy + 12,
                                   fill=fill, outline="#D8B46A", width=2, tags=tags)
                canvas.create_text(cx, cy, text=self._format_win_amount(amount),
                                   fill=text_color, font=("Arial", 8, "bold"), tags=tags)
        # Draw focus last so adjacent sectors cannot overpaint its shared edge.
        if self.region_hover in FRENCH_BETS and self.round_state == "betting":
            points = self._region_polygon(self.region_hover)
            coords = [v for point in points + points[:1] for v in point]
            tags = ("track", "track_region:" + self.region_hover)
            canvas.create_line(*coords, fill=RACETRACK_FOCUS_HALO, width=6,
                               joinstyle=tk.ROUND, tags=tags)
            canvas.create_line(*coords, fill=RACETRACK_REGION_FOCUS, width=3,
                               joinstyle=tk.ROUND, tags=tags)

    def _racetrack_region_at(self, x, y):
        # Ray casting follows the same polygons as drawing, including the diagonal
        # and both curved ends; number pockets outside the capsule stay separate.
        for region in RACETRACK_REGION_ORDER:
            points = self._region_polygon(region)
            inside = False
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
                if (y1 > y) != (y2 > y):
                    edge_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                    if x < edge_x:
                        inside = not inside
            if inside:
                return region
        return None

    def _place_region_bet(self, region):
        if self.round_state != "betting" or self.betting_view != "racetrack":
            return
        unit_amount = int(self.selected_bet_amount)
        if unit_amount <= 0 or region not in FRENCH_BETS:
            return
        legs = self._region_legs(region)
        # Cap the unit stake at the tightest remaining table leg. Preserve the
        # standard 2:1 legs and account for direct bets and overlapping regions.
        remaining_units = min(max(0, (self._bet_limit_for_spot(spot)
                              - self.current_bets.get(spot["id"], 0)) // units)
                              for spot, units in legs)
        unit_amount = min(unit_amount, int(remaining_units))
        if unit_amount <= 0:
            return
        total = unit_amount * sum(units for _, units in legs) * self.bet_multiplier
        if total > self.balance:
            return
        self.balance -= total
        self.region_bets[region] = self.region_bets.get(region, 0) + unit_amount
        for spot, units in legs:
            key = spot["id"]
            self.current_bets[key] = self.current_bets.get(key, 0) + unit_amount * units
            self.current_bet_colors[key] = self._chip_fill_color_for_amount(self.current_bets[key])
        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

    def _clear_region_bet(self, region):
        if self.round_state != "betting":
            return
        amount = self.region_bets.pop(region, 0)
        for spot, units in self._region_legs(region):
            key = spot["id"]
            remaining = self.current_bets.get(key, 0) - amount * units
            self.balance += amount * units * self.bet_multiplier
            if remaining > 0:
                self.current_bets[key] = remaining
                self.current_bet_colors[key] = self._chip_fill_color_for_amount(remaining)
            else:
                self.current_bets.pop(key, None)
                self.current_bet_colors.pop(key, None)
        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

    def _animate_chips_to_table(self):
        """Visual-only transfer: stakes were already charged once when accepted."""
        self._cancel_chip_transfer()
        pending = self._region_contributions()
        transfers = []
        for region, amount in self.region_bets.items():
            for spot, units in self._region_legs(region):
                transfers.append((self._region_center(region), spot, amount * units))
        if self.betting_view == "racetrack":
            for index, number in enumerate(RACETRACK_SEQUENCE):
                key = "straight_" + number
                amount = self.current_bets.get(key, 0) - pending.get(key, 0)
                if amount > 0:
                    origin = self._racetrack_point((index + 0.5) / len(RACETRACK_SEQUENCE), RACETRACK_CHIP_R)
                    transfers.append((origin, self._find_spot_by_id(key), amount))
        # Preserve the player's chosen view. Table coordinates/animation still
        # update the shared board without replacing the visible racetrack.
        self.racetrack_hover = None
        self.region_hover = None
        self._draw_racetrack()
        self._update_betting_view_controls()
        if not transfers:
            self._repaint_all_chips()
            return
        self._chip_transfer_active = True
        moving = {}
        for _, spot, amount in transfers:
            moving[spot["id"]] = moving.get(spot["id"], 0) + amount
        self.board_canvas.delete("chips")
        self.placed_chip_items = {}
        for key, amount in self.current_bets.items():
            stationary = amount - moving.get(key, 0)
            if stationary > 0:
                self._draw_chip_on_spot(self._find_spot_by_id(key), stationary)
        for origin, spot, amount in transfers:
            x, y = origin
            radius = self._chip_radius_for_spot(spot)
            fill = self._chip_fill_color_for_amount(amount)
            oval = self.board_canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                        fill=fill, outline="#D4AF37", width=2, tags="chip_transfer")
            label = self.board_canvas.create_text(x, y, text=self._format_win_amount(amount),
                        fill=self._spot_text_color(fill), font=("Arial", 7, "bold"), tags="chip_transfer")
            self._chip_transfer_items.append((oval, label, origin, spot["center"], radius))
        self._chip_transfer_started = time.perf_counter()
        self._chip_transfer_tick()

    def _chip_transfer_tick(self):
        self._chip_transfer_job = None
        if not self._chip_transfer_active:
            return
        elapsed = time.perf_counter() - self._chip_transfer_started
        progress = min(1.0, elapsed / CHIP_TRANSFER_SECONDS)
        eased = progress * progress * (3.0 - 2.0 * progress)
        for oval, label, (sx, sy), (tx, ty), radius in self._chip_transfer_items:
            x, y = sx + (tx - sx) * eased, sy + (ty - sy) * eased
            self.board_canvas.coords(oval, x-radius, y-radius, x+radius, y+radius)
            self.board_canvas.coords(label, x, y)
        if progress >= 1.0:
            self._cancel_chip_transfer()
            self._repaint_all_chips()
        else:
            remaining_ms = max(1, int(math.ceil((CHIP_TRANSFER_SECONDS - elapsed) * 1000)))
            self._chip_transfer_job = self.after(min(16, remaining_ms), self._chip_transfer_tick)

    def _cancel_chip_transfer(self):
        if self._chip_transfer_job is not None:
            self.after_cancel(self._chip_transfer_job)
            self._chip_transfer_job = None
        self._chip_transfer_active = False
        self._chip_transfer_items = []
        if hasattr(self, "board_canvas"):
            self.board_canvas.delete("chip_transfer")

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

        panel = tk.Frame(parent, bg=ROOT_BG, width=280, height=408)
        panel.pack(fill=tk.Y, expand=False)
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
        chips_frame.pack(pady=8, padx=4)
        chip_grid = tk.Frame(chips_frame, bg=panel_bg)
        chip_grid.pack(side=tk.LEFT)
        multiplier_frame = tk.Frame(chips_frame, bg=panel_bg)
        multiplier_frame.pack(side=tk.RIGHT, padx=(4, 0))
        tk.Label(multiplier_frame, text="倍数", bg=panel_bg,
                 font=("Arial", 12, "bold")).pack(pady=(0, 8))
        self.multiplier_var = tk.StringVar(value="1")
        self.multiplier_display = tk.Label(
            multiplier_frame, text="×1", bg="#193C30", fg="#F5D68A",
            font=("Arial", 17, "bold"), width=4, pady=7)
        self.multiplier_display.pack(fill=tk.X)
        step_controls = tk.Frame(multiplier_frame, bg=panel_bg)
        step_controls.pack(fill=tk.X, pady=(4, 0))
        self.multiplier_buttons = []
        for symbol, direction in (("−", -1), ("+", 1)):
            button = tk.Button(
                step_controls, text=symbol, command=lambda d=direction: self._step_multiplier(d),
                bg="#D8B46A", fg="#2A1B08", activebackground="#E8C67F",
                relief=tk.FLAT, bd=0, font=("Arial", 12, "bold"),
                cursor="hand2", width=2, takefocus=True)
            button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)
            self.multiplier_buttons.append(button)

        chips = [
            ("1", "#ffffff"),
            ("5", "#9e9e9e"),
            ("10", "#0000ff"),
            ("25", "#00ff00"),
            ("100", "#A8ECFF"),
            ("500", "#FF7DDA"),
        ]

        for i in range(0, len(chips), 3):
            row_frame = tk.Frame(chip_grid, bg=panel_bg)
            row_frame.pack(pady=5)
            for text, bg_color in chips[i:i + 3]:
                canvas = self._create_chip_button(row_frame, text, bg_color)
                canvas.pack(side=tk.LEFT, padx=3)

        self.current_chip_label = tk.Label(
            card,
            text="本局下注金额\n$0 * 1 = $0",
            font=("Arial", 12, "bold"),
            bg=panel_bg,
            fg="black"
        )
        self.current_chip_label.pack(pady=(3, 0))


        self.balance_label_side = tk.Label(
            card,
            text=f"余额: ${self.balance:,.2f}",
            font=("Arial", 12, "bold"),
            bg=panel_bg,
            fg="black"
        )
        self.balance_label_side.pack(pady=(0, 5))

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
        self.reset_button.pack(side=tk.TOP, fill=tk.X, pady=0)

        # 重复上局下注
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
        self.repeat_last_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 开始游戏按钮
        self.deal_button = tk.Button(
            btn_frame,
            text="开始落球 (Enter)",
            command=self.start_game,
            bg="#D8B46A",
            fg="#2A1B08",
            activebackground="#C8A455",
            activeforeground="#2A1B08",
            font=("微软雅黑", 12, "bold"),
            relief=tk.RAISED,
            bd=3,
            cursor="hand2"
        )
        self.deal_button.pack(side=tk.TOP, fill=tk.X, pady=0)

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
            self.last_region_bets = self.region_bets.copy()
            self.last_betting_view = self.betting_view
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
        total_last = sum(self.last_bets.values()) * self.bet_multiplier
        if total_last > self.balance + sum(self.current_bets.values()) * self.bet_multiplier:
            self.repeat_last_btn.config(state=tk.DISABLED)
        else:
            self.repeat_last_btn.config(state=tk.NORMAL)

    def _repeat_last_bet(self):
        if self.round_state != "betting" or not self.last_bets:
            return
        total = sum(self.last_bets.values()) * self.bet_multiplier
        if total > self.balance + sum(self.current_bets.values()) * self.bet_multiplier:
            messagebox.showwarning("余额不足", f"重复上局下注需要 ${total:,.0f}。")
            return
        self.clear_bets()
        self.balance -= total
        self.current_bets = self.last_bets.copy()
        self.current_bet_colors = self.last_bet_colors.copy()
        self.region_bets = self.last_region_bets.copy()
        self._switch_betting_view("racetrack" if self.region_bets else self.last_betting_view)
        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()


    def _create_chip_button(self, parent, text, bg_color):
        size = 52
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

        canvas.create_text(size / 2, size / 2, text=text, fill=text_color, font=("Arial", 16, "bold"))
        canvas.bind("<Button-1>", lambda e, t=text, c=canvas, cid=chip_id, bg=bg_color: self._set_bet_amount(t, c, cid, bg))
        self.chip_buttons.append({"canvas": canvas, "chip_id": chip_id, "text": text, "bg_color": bg_color})
        return canvas


    def _set_bet_amount(self, chip_text, clicked_canvas, clicked_chip_id, bg_color=None):
        for chip in self.chip_buttons:
            chip["canvas"].itemconfig(chip["chip_id"], outline="", width=0)
            chip["canvas"].delete("glow")
        clicked_canvas.itemconfig(clicked_chip_id, outline="yellow", width=4)
        self.selected_chip = next((c for c in self.chip_buttons if c["canvas"] == clicked_canvas), None)
        if bg_color is None and self.selected_chip:
            bg_color = self.selected_chip.get("bg_color", "#ffffff")
        self.selected_chip_color = bg_color or "#ffffff"

        # chip_text is like "1","5","10","25","100","500"
        amount = int(chip_text)
        self.selected_bet_amount = amount
        self._refresh_bet_totals()

    def _set_default_chip(self):
        # default to chip "25"
        for chip in self.chip_buttons:
            if chip["text"] == "25":
                chip["canvas"].itemconfig(chip["chip_id"], outline="yellow", width=4)
                self.selected_chip = chip
                self.selected_chip_color = chip.get("bg_color", "#ffffff")
                self.selected_bet_amount = 25
                self._refresh_bet_totals()
                break

    # =====================================================
    # Right side: marker road + history proportion + pie chart
    # =====================================================

    def _build_right_side(self, parent):
        # 左侧筹码区、右侧统计区：贴合显示，没有任何缝隙
        root = tk.Frame(parent, bg=ROOT_BG)
        root.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=0, minsize=280)
        root.grid_columnconfigure(1, weight=1, minsize=300)

        chip_frame = tk.Frame(root, bg=ROOT_BG, width=280)
        chip_frame.grid(row=0, column=0, sticky="ns", padx=0, pady=0)
        chip_frame.grid_propagate(False)

        # 饼图放在筹码区顶部，取代原来的 top_spacer
        self._create_pie_chart(chip_frame)

        # 筹码区面板
        self._populate_chips(chip_frame)

        stats_frame = tk.Frame(root, bg=ROOT_BG)
        stats_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        self._create_marker_road(stats_frame)
        self._create_distribution_panel(stats_frame)
        self._create_hot_cold_panel(stats_frame)

    # ---------- 新增饼图相关方法（欧式单零） ----------
    def _create_pie_chart(self, parent):
        """创建可切换的饼图：区间分布/每行分布，居中显示，下方动态显示颜色+说明+次数"""
        card_bg = "#F2E6C9"
        header_bg = "#D8B46A"
        title_fg = "#2A1B08"

        outer = tk.Frame(parent, bg=ROOT_BG)
        outer.pack(fill=tk.X, pady=(8, 0))

        card = tk.Frame(outer, bg=card_bg, bd=1, relief=tk.SOLID, highlightthickness=0)
        card.pack(fill=tk.X)

        # 标题栏 - 可点击切换模式
        title_bar = tk.Frame(card, bg=header_bg)
        title_bar.pack(fill=tk.X)

        self.pie_title_btn = tk.Button(
            title_bar,
            text="最新50局的区间分布",
            font=("Arial", 13, "bold"),
            bg=header_bg,
            fg=title_fg,
            activebackground=header_bg,
            activeforeground=title_fg,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._toggle_pie_chart_type
        )
        self.pie_title_btn.pack(anchor=tk.CENTER, padx=10, pady=6)

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

        # 饼图下方统计表格容器
        self.pie_stats_frame = tk.Frame(card, bg=card_bg)
        self.pie_stats_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 预定义颜色
        self.pie_colors = {
            "sector1": "#5F9F4F",   # 1-12
            "sector2": "#AF4900",   # 13-24
            "sector3": "#4A90E2",   # 25-36
            "zero": TEAL,           # 0
            "row1": RED,            # 行1
            "row2": BLACK,          # 行2
            "row3": "#8B4513",      # 行3
        }

    def _toggle_pie_chart_type(self):
        """切换饼图模式（区间分布 或 每行分布）并更新界面"""
        if self.pie_mode == "sector":
            self.pie_mode = "row"
            self.pie_title_btn.config(text="最新50局的每行分布")
        else:
            self.pie_mode = "sector"
            self.pie_title_btn.config(text="最新50局的区间分布")
        self._update_pie_chart()

    def _get_sector_data_from_recent(self, limit=50):
        """从 Record2 中获取最近 limit 条结果，统计各区间（1-12,13-24,25-36,0）出现的次数"""
        all_results = self.history.recent_results2(limit=2000)
        recent = [entry.get("result", "") for entry in all_results if entry.get("result", "")][:limit]
        counts = {"1-12": 0, "13-24": 0, "25-36": 0, "0": 0}
        for res in recent:
            if res == "0":
                counts["0"] += 1
            else:
                try:
                    num = int(res)
                    if 1 <= num <= 12:
                        counts["1-12"] += 1
                    elif 13 <= num <= 24:
                        counts["13-24"] += 1
                    elif 25 <= num <= 36:
                        counts["25-36"] += 1
                except ValueError:
                    pass
        total = sum(counts.values())
        return counts, total

    def _get_row_data_from_recent(self, limit=50):
        """统计最近 limit 条结果中属于 Row1/Row2/Row3/0 的次数"""
        row1_set = {1,4,7,10,13,16,19,22,25,28,31,34}
        row2_set = {2,5,8,11,14,17,20,23,26,29,32,35}
        row3_set = {3,6,9,12,15,18,21,24,27,30,33,36}

        all_results = self.history.recent_results2(limit=2000)
        recent = [entry.get("result", "") for entry in all_results if entry.get("result", "")][:limit]
        counts = {"row1": 0, "row2": 0, "row3": 0, "0": 0}
        for res in recent:
            if res == "0":
                counts["0"] += 1
            else:
                try:
                    num = int(res)
                    if num in row1_set:
                        counts["row1"] += 1
                    elif num in row2_set:
                        counts["row2"] += 1
                    elif num in row3_set:
                        counts["row3"] += 1
                except ValueError:
                    pass
        total = sum(counts.values())
        return counts, total

    def _update_pie_chart(self):
        """根据当前模式，动态绘制饼图（仅绘制计数>0的扇形），下方以表格显示分类与次数，0始终在最上方且永远显示（即使0次）"""
        if not hasattr(self, "pie_canvas"):
            return

        limit = 50
        if self.pie_mode == "sector":
            counts, total = self._get_sector_data_from_recent(limit)
            all_keys = ["1-12", "13-24", "25-36", "0"]
            display_names = {"1-12": "1-12", "13-24": "13-24", "25-36": "25-36", "0": "0"}
            color_keys = {"1-12": "sector1", "13-24": "sector2", "25-36": "sector3", "0": "zero"}
        else:
            counts, total = self._get_row_data_from_recent(limit)
            all_keys = ["row1", "row2", "row3", "0"]
            display_names = {"row1": "直行1(1/4/7...)", "row2": "直行2(2/5/8...)", "row3": "直行3(3/6/9...)", "0": "0"}
            color_keys = {"row1": "row1", "row2": "row2", "row3": "row3", "0": "zero"}

        if total == 0:
            total = 1

        # 构建用于饼图扇形的有效数据（计数>0）
        valid_for_pie = [(key, counts[key]) for key in all_keys if counts[key] > 0]

        # 构建用于统计显示的数据：包含所有计数>0的分类 + 始终包含0（即使计数为0）
        zero_count = counts.get("0", 0)
        other_items = [(key, counts[key]) for key in all_keys if key != "0" and counts[key] > 0]
        # 始终把0放在最前面（即使计数为0）
        valid_for_stats = [("0", zero_count)] + other_items

        # 如果没有扇形数据（只有0且0次），则清空饼图
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
                if key == "0":
                    label = "0"
                elif key.startswith("row"):
                    label = key[-1]
                else:
                    label = key
                text_color = "white"
                self.pie_canvas.create_text(tx, ty, text=label, fill=text_color, font=("Arial", 9, "bold"))
                start_angle += angle

        # 以紧凑表格显示统计，保留与饼图对应的分类颜色。
        for widget in self.pie_stats_frame.winfo_children():
            widget.destroy()

        self.pie_stats_frame.grid_columnconfigure(0, weight=0, minsize=188)
        self.pie_stats_frame.grid_columnconfigure(1, weight=0, minsize=70)
        heading = "区间" if self.pie_mode == "sector" else "直行"
        for column, title in enumerate((heading, "次数")):
            tk.Label(
                self.pie_stats_frame, text=title, bg="#D8B46A", fg="#2A1B08",
                font=("Arial", 14, "bold"), width=1, bd=1, relief=tk.SOLID,
                padx=4, pady=0
            ).grid(row=0, column=column, sticky="nsew")

        table_names = {"row1": "直行1", "row2": "直行2", "row3": "直行3"}
        for row, (key, cnt) in enumerate(valid_for_stats, start=1):
            row_bg = "#FFF7E6" if row % 2 else "#F2E6C9"
            tk.Label(
                self.pie_stats_frame, text=f"●  {table_names.get(key, display_names[key])}",
                bg=row_bg, fg=self.pie_colors[color_keys[key]],
                font=("Arial", 14, "bold"), width=1, anchor="w",
                bd=1, relief=tk.SOLID, padx=6, pady=0
            ).grid(row=row, column=0, sticky="nsew")
            tk.Label(
                self.pie_stats_frame, text=str(cnt), bg=row_bg, fg="#1A1A1A",
                font=("Arial", 14, "bold"), width=1, anchor="center",
                bd=1, relief=tk.SOLID, padx=6, pady=0
            ).grid(row=row, column=1, sticky="nsew")

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
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=(8, 10))

        self.marker_canvas = tk.Canvas(
            content,
            bg=card_bg,
            highlightthickness=0,
            bd=0
        )
        self.marker_canvas.pack(fill=tk.BOTH, expand=True)

        self._draw_marker_grid()
        self._update_marker_road()


    def _update_distribution(self):
        """从 Record2 读取最近 N 条结果，更新：
        1) 小/0/大
        2) 单/0/双
        3) 红/绿/黑
        """
        if not hasattr(self, 'history'):
            return

        all_results = self.history.recent_results2(limit=2000)
        if not all_results:
            return

        n = min(self.distribution_display_count, len(all_results))
        recent = all_results[:n] if n > 0 else []

        # 统计第一组（小/0/大）
        small_cnt = big_cnt = zero_cnt = 0
        # 第二组（单/0/双）
        odd_cnt = even_cnt = 0   # zero_cnt 共用
        # 第三组（红/绿/黑）
        red_cnt = green_cnt = black_cnt = 0

        for entry in recent:
            result = entry.get("result", "")
            if result == "0":
                zero_cnt += 1
                green_cnt += 1      # 绿色（0）
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
        min_zero_width = 30    # 0 最小宽度

        # ========== 第一组：小 / 0 / 大 ==========
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

        # ========== 第二组：单 / 0 / 双 ==========
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

        # ========== 第三组：红 / 绿(0) / 黑 ==========
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

        # 第一组：小 / 0 / 大
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

        # 第二组：单 / 0 / 双
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
            font=("Arial", 11, "bold"),
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
                row_frame = tk.Frame(outer_card, bg=body_bg, height=38)
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
        if not hasattr(self, 'history'):
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
        all_numbers = [str(i) for i in range(1, 37)] + ["0"]
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
                color_name = roulette_color(num)
                if color_name == "Red":
                    ball_color = RED
                elif color_name == "Black":
                    ball_color = BLACK
                else:
                    ball_color = TEAL
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
        cell_size = 30

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
        cell_size = 30
        max_display = rows * cols
        start_idx = max(0, len(self.marker_results) - max_display)
        results_to_show = self.marker_results[start_idx:]

        for idx, entry in enumerate(results_to_show):
            if idx >= max_display:
                break
            result = entry["result"]
            color = roulette_color(result)
            if color == "Red":
                fill = RED
                text_fill = "white"
            elif color == "Black":
                fill = BLACK
                text_fill = "white"
            else:
                fill = TEAL
                text_fill = "white"

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
            font = ("Arial", 11, "bold")
            self.marker_canvas.create_text(
                cx, cy,
                text=result,
                fill=text_fill,
                font=font,
                tags="dot"
            )

    def _sync_marker_from_history(self):
        raw_hist = self.history.recent_results(limit=54)
        reversed_hist = [entry for entry in reversed(raw_hist) if entry["result"]]
        self.marker_results = reversed_hist
        self._update_marker_road()
        self._update_pie_chart()
        self._update_distribution() 
        self._update_hot_cold_display()

    def add_marker_result(self, result):
        self._sync_marker_from_history()
        self._update_pie_chart()
        self._update_distribution() 
        self._update_hot_cold_display()

    # =====================================================
    # Flat 2D wheel and obstacle field
    # =====================================================


    def _wheel_point(self, cx, cy, radius, angle):
        a = math.radians(angle)
        return cx+radius*math.sin(a), cy-radius*math.cos(a)

    def _wheel_polygon(self, cx, cy, points, **style):
        style.setdefault('tags', self._wheel_layer)
        return self.wheel_canvas.create_polygon(
            *[v for x,y in points for v in (cx+x,cy+y)], **style)

    def _wheel_disc(self, cx, cy, radius, **style):
        style.setdefault('tags', self._wheel_layer)
        return self.wheel_canvas.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,**style)

    def _wheel_band(self, cx, cy, inner, outer, start, end, **style):
        style.setdefault('tags', self._wheel_layer)
        divisions = max(2, int(abs(end-start)/3))
        points = []
        for radius, steps in ((outer, range(divisions+1)), (inner, range(divisions, -1, -1))):
            for j in steps:
                points.extend(self._wheel_point(cx, cy, radius, start+(end-start)*j/divisions))
        return self.wheel_canvas.create_polygon(*points, **style)

    @staticmethod
    def _number_cell_radii():
        # The number band starts exactly at the end of the pocket posts.
        return PlinkoPhysics.POCKET_OUTER*WHEEL_METRE_SCALE+3,187.0

    def _prepare_wheel_number_font(self):
        """Use a real bold face; Pillow improves smoothing but stays optional."""
        self._wheel_number_masks={}
        self._wheel_number_images=OrderedDict()
        self._wheel_number_font=None
        families=set(tkfont.families(self.root))
        family=next((f for f in ('Arial','Liberation Sans','DejaVu Sans') if f in families),'Arial')
        self._wheel_native_number_font=tkfont.Font(root=self.root,family=family,size=-16,weight='bold')
        if ImageFont is None:
            return
        candidates=(os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'Fonts','arialbd.ttf'),
                    'arialbd.ttf','/System/Library/Fonts/Supplemental/Arial Bold.ttf',
                    'DejaVuSans-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
        for path in candidates:
            try:
                self._wheel_number_font=ImageFont.truetype(path,72)
                break
            except (OSError,ValueError):
                continue

    def _wheel_number_image(self, symbol, angle, lit):
        """Optically centred, supersampled solid glyphs with a bounded cache."""
        if not hasattr(self,'_wheel_number_masks'):
            self._prepare_wheel_number_font()
        if self._wheel_number_font is None:
            return None
        # Half a degree is under a tenth of a pixel at this font size; reuse
        # those images rather than rebuilding 37 PhotoImages every frame.
        degrees=(round(math.degrees(angle)*2)/2)%360
        key=(symbol,degrees,lit)
        cache=self._wheel_number_images
        if key in cache:
            cache.move_to_end(key)
            return cache[key]
        scale=4
        resampling=getattr(Image,'Resampling',Image)
        if symbol not in self._wheel_number_masks:
            bounds=self._wheel_number_font.getbbox(symbol)
            mask=Image.new('L',(bounds[2]-bounds[0]+8,bounds[3]-bounds[1]+8),0)
            ImageDraw.Draw(mask).text((4-bounds[0],4-bounds[1]),symbol,
                                      font=self._wheel_number_font,fill=255)
            mask=mask.crop(mask.getbbox())
            height=13*scale
            width=min(round(17.5*scale),max(1,round(mask.width*height/mask.height*.90)))
            mask=mask.resize((width,height),resampling.LANCZOS)
            # A small transparent margin protects curved terminals on rotation.
            padded=Image.new('L',(width+8,height+8),0)
            padded.paste(mask,(4,4))
            self._wheel_number_masks[symbol]=padded
        mask=self._wheel_number_masks[symbol].rotate(-degrees,resample=resampling.BICUBIC,expand=True)
        # Preserve the rotation pivot. Recropping rotated ink would make
        # asymmetric numerals drift sideways within an otherwise aligned cell.
        size=(max(1,math.ceil(mask.width/scale)),max(1,math.ceil(mask.height/scale)))
        mask=mask.resize(size,resampling.LANCZOS)
        sprite=Image.new('RGBA',size,'#FFFBE9' if lit else '#EEF3F6')
        sprite.putalpha(mask)
        photo=ImageTk.PhotoImage(sprite,master=self.wheel_canvas)
        cache[key]=photo
        while len(cache)>512:
            cache.popitem(last=False)
        return photo

    def _draw_wheel_numeral(self, cx, cy, symbol, mid, lit, radius):
        a = math.radians(mid)
        sine, cosine = math.sin(a), math.cos(a)
        # The baseline follows the cell's tangent: upright at the top, then
        # carried around with that cell. Unwrap the angle so crossing the top
        # keeps the same gradual turn instead of reversing or flipping 360°.
        angles = self._wheel_text_angles
        previous = angles.get(symbol,a)
        change = (a-previous+math.pi) % (2*math.pi)-math.pi
        angle = previous+change
        angles[symbol] = angle
        text_sine,text_cosine = math.sin(angle),math.cos(angle)
        centre_x,centre_y = cx+radius*sine,cy-radius*cosine
        tags=(self._wheel_layer,'number_text:'+symbol)
        photo=self._wheel_number_image(symbol,angle,lit)
        if photo is not None:
            self._wheel_text_frame_images.append(photo)
            self.wheel_canvas.create_image(centre_x,centre_y,image=photo,tags=tags)
        else:
            # Keep standalone Tkinter installations working without Pillow.
            # A small metric correction centres capital numerals optically.
            offset=self._wheel_native_number_font.metrics('descent')*.30
            self.wheel_canvas.create_text(centre_x-offset*text_sine,centre_y+offset*text_cosine,
                                          text=symbol,font=self._wheel_native_number_font,
                                          fill='#FFFBE9' if lit else '#EEF3F6',
                                          angle=-math.degrees(angle),anchor='center',tags=tags)

    def _draw_horizontal_obstacle(self, cx, cy, obstacle, light):
        scale = WHEEL_METRE_SCALE
        polygon = [(x*scale, y*scale) for x, y in PlinkoPhysics.obstacle_polygon(obstacle)]
        self._wheel_polygon(cx,cy,polygon,fill='#94ABB8',outline=light,width=.7)

    def _draw_exit_guard(self, cx, cy, light):
        s=WHEEL_METRE_SCALE
        points=[v for x,y in self.physics.guard_arc() for v in (cx+x*s,cy+y*s)]
        self.wheel_canvas.create_line(*points,fill=light,
                                     width=2*self.physics.GUARD_HALF*s,
                                     capstyle='round',joinstyle='round',tags=self._wheel_layer)

    def _draw_receiver(self, cx, cy, light):
        """Front-on round receiving cup, tapered guides and a supported neck."""
        c=self.wheel_canvas
        s=WHEEL_METRE_SCALE
        centre_y=cy-.320*s
        radius=.033*s
        tags=self._wheel_layer
        c.create_oval(cx-radius,centre_y-radius,cx+radius,centre_y+radius,
                      fill='#405869',outline='#7A909F',width=1.2,tags=tags)
        c.create_oval(cx-radius+3,centre_y-radius+3,cx+radius-3,centre_y+radius-3,
                      fill='#07121D',outline='#253B4C',width=1,tags=tags)
        half=PlinkoPhysics.LAUNCH_HALF
        mouth=PlinkoPhysics.LAUNCH_MOUTH_HALF
        shoulder=PlinkoPhysics.LAUNCH_SHOULDER
        floor=PlinkoPhysics.LAUNCH_FLOOR
        neck=[(-(half+.004)*s,(shoulder-.006)*s),((half+.004)*s,(shoulder-.006)*s),
              ((half+.004)*s,(floor+.012)*s),(-(half+.004)*s,(floor+.012)*s)]
        self._wheel_polygon(cx,cy,neck,fill='#304B5E',outline='#7893A4',width=.7)
        channel=[(-mouth*s,PlinkoPhysics.LAUNCH_TOP*s),(mouth*s,PlinkoPhysics.LAUNCH_TOP*s),
                 (half*s,shoulder*s),(half*s,floor*s),(-half*s,floor*s),(-half*s,shoulder*s)]
        self._wheel_polygon(cx,cy,channel,fill='#07121D',outline='')
        for polygon in self.physics.launcher_polygons[:-1]:
            self._wheel_polygon(cx,cy,[(x*s,y*s) for x,y in polygon],
                                fill='#A5BCC8',outline='')
        c.create_arc(cx-radius+1,centre_y-radius+1,cx+radius-1,centre_y+radius-1,
                     start=-55,extent=290,style='arc',outline=light,width=1.5,tags=tags)
        for sign in (-1,1):
            x=cx+sign*(radius+1.5)
            c.create_oval(x-1.2,centre_y-1.2,x+1.2,centre_y+1.2,
                          fill='#B5C5CD',outline='',tags=tags)

    def _draw_storage_cell(self, cx, cy, start, end, selected, lit, kind, number):
        """A real rotating |-| pocket, drawn from the collision dimensions."""
        s=WHEEL_METRE_SCALE
        inner=PlinkoPhysics.DIVIDER_INNER*s
        floor=PlinkoPhysics.POCKET_OUTER*s
        self._wheel_band(cx,cy,inner,floor,start,end,
                         fill='#C7922A' if selected else WHEEL_CUP_ON[kind] if lit else '#15283A',
                         outline='#FFE3A0' if selected else '#F0E2AE' if lit else '#526B7B',width=.7,
                         tags=(self._wheel_layer,'cup_cell:'+number))
        self._wheel_band(cx,cy,floor,floor+2,start,end,
                         fill='#FFE7A0' if selected else '#F9E6A4' if lit else '#8AABB8',outline='')
        self._draw_pocket_divider(cx,cy,start,'#8AABB8')
        if selected and self.physics.mode in {'result','returning','recovery_ready'}:
            # A physical inner latch keeps the returning ball in its cup while
            # gravity moves it against the floor, dividers or latch itself.
            self._wheel_band(cx,cy,inner-2,inner,start,end,fill='#FFE7A0',outline='')

    def _draw_pocket_divider(self, cx, cy, start, color):
        s=WHEEL_METRE_SCALE
        inner=PlinkoPhysics.DIVIDER_INNER*s
        floor=PlinkoPhysics.POCKET_OUTER*s
        angle=math.radians(start)
        nx,ny=math.sin(angle),-math.cos(angle)
        tx,ty=-ny,nx
        half=PlinkoPhysics.DIVIDER_HALF*s
        # The side posts extend a little beyond the floor crossbar. Their inner
        # end and thickness are the same capsule used by divider collisions.
        cap=[]
        for radius,base in ((inner,math.pi),(floor+3,0)):
            for i in range(7):
                a=base-math.pi/2+i*math.pi/6
                cap.append((nx*radius+half*(nx*math.cos(a)+tx*math.sin(a)),
                            ny*radius+half*(ny*math.cos(a)+ty*math.sin(a))))
        self._wheel_polygon(cx,cy,cap,fill=color,outline='')

    def _draw_ball(self, cx, cy, bx, by):
        """A flat disc, using the solver's exact position and radius."""
        r=PlinkoPhysics.BALL_R*WHEEL_METRE_SCALE
        self.wheel_canvas.create_oval(cx+bx-r,cy+by-r,cx+bx+r,cy+by+r,
                                      fill='#FFFFFF',outline='#5DB9CD',width=.7,
                                      tags=(self._wheel_layer,'ball_disc'))

    def _draw_wheel(self):
        c=self.wheel_canvas
        width,height=c.winfo_width(),c.winfo_height()
        if width <= 10 or height <= 10:
            return
        cx,cy=width/2,height/2-1
        s=WHEEL_METRE_SCALE
        light=('#FC5ADE' if self.round_state=='betting' and not self._launch_ready_remaining()
               else '#59E6FA')
        rotating=self.physics.rotating_obstacle
        static_key=(width,height,light,rotating)
        rebuild=getattr(self,'_wheel_static_key',None)!=static_key
        if rebuild:
            c.delete('all')
            c.configure(bg=ROOT_BG)
            self._wheel_layer='wheel_background'
            self._wheel_disc(cx,cy,194,fill='#101B2C',outline='#637B91',width=1)
            for inner,outer,color in ((190,194,'#124E77'),(191,192,light),(187,190,'#526C83')):
                self._wheel_band(cx,cy,inner,outer,0,360,fill=color,outline='')
        else:
            c.delete('wheel_rotor')
        self._wheel_layer='wheel_rotor'
        self._wheel_text_frame_images=[]
        if not hasattr(self,'_wheel_text_angles'):
            self._wheel_text_angles={}
        lit=self._covered_wheel_numbers()
        self._wheel_lit_numbers=lit
        pulse=.5+.5*math.sin(self.physics.t*4) if self.physics else .5
        step=math.degrees(PlinkoPhysics.STEP)
        number_inner,number_outer=self._number_cell_radii()
        number_radius=(number_inner+number_outer)/2
        illuminated=[]
        for i,number in enumerate(ROULETTE_SEQUENCE):
            start=self.current_wheel_offset+i*step
            end=start+step
            mid=(start+end)/2
            active=number in lit
            kind='Green' if number in {'0'} else 'Red' if int(number) in RED_NUMBERS else 'Black'
            number_color=(WHEEL_CARD_ON if active else WHEEL_CARD_OFF)[kind]
            selected=self.ball_pocket_index==i
            self._draw_storage_cell(cx,cy,start,end,selected,active,kind,number)
            if active:
                self._wheel_band(cx,cy,number_inner-.65,number_outer+.65,start+.15,end-.15,
                                 fill='#D8C783',outline='')
            self._wheel_band(cx,cy,number_inner,number_outer,start,end,fill=number_color,
                             outline='#FFF6BB' if active else '#7C939F',width=1.05 if active else .65,
                             tags=(self._wheel_layer,'number_cell:'+number))
            if active:
                for inner,outer in ((number_inner,number_inner+1.1),(number_outer-1.1,number_outer)):
                    self._wheel_band(cx,cy,inner,outer,start+.6,end-.6,
                                     fill='#FFF4B8' if pulse>.35 else '#E2D393',outline='')
            self._draw_wheel_numeral(cx,cy,number,mid,active,number_radius)
            if active:
                illuminated.append(start)
        # Shared dividers are lit after all cup backgrounds, with occupied
        # gold walls taking priority over the neighbouring betting lamps.
        for start in illuminated:
            for edge in (start,start+step):
                self._draw_pocket_divider(cx,cy,edge,'#F9E6A4')
        if self.ball_pocket_index is not None:
            start=self.current_wheel_offset+self.ball_pocket_index*step
            for edge in (start,start+step):
                self._draw_pocket_divider(cx,cy,edge,'#FFE7A0')
        if rebuild:
            self._wheel_layer='wheel_plate'
            self._wheel_disc(cx,cy,PlinkoPhysics.BOARD_R*s,fill='#102C41',outline='')
            for i,obstacle in enumerate(self.physics.obstacle_layout):
                if i!=rotating:
                    self._draw_horizontal_obstacle(cx,cy,obstacle,light)
            for i,polygon in enumerate(PlinkoPhysics.bottom_deflectors(),len(self.physics.obstacle_layout)):
                if i!=rotating:
                    self._wheel_polygon(cx,cy,[(x*s,y*s) for x,y in polygon],
                                        fill='#94ABB8',outline=light,width=.7)
            self._draw_exit_guard(cx,cy,light)
            self._draw_receiver(cx,cy,light)
            self._wheel_static_key=static_key
        c.tag_raise('wheel_plate')
        c.delete('wheel_moving_obstacle')
        if rotating is not None:
            self._wheel_layer='wheel_moving_obstacle'
            self._wheel_polygon(cx,cy,[(x*s,y*s) for x,y in self.physics.polygons[rotating]],
                                fill='#94ABB8',outline='#FFD36B',width=1.2)
        c.delete('wheel_ball')
        self._wheel_layer='wheel_ball'
        if self.physics.mode in {'waiting','loading'}:
            self._wheel_polygon(cx,cy,[(x*s,y*s) for x,y in self.physics.launcher_polygons[-1]],
                                fill=light,outline='')
        # Ball, bars and pocket walls all use the same unprojected 2D axes.
        angle=math.radians(self.pointer_angle)
        bx,by=self.ball_radius*math.sin(angle),-self.ball_radius*math.cos(angle)
        self._draw_ball(cx,cy,bx,by)
        self._draw_wheel_title(width,height)
        self._draw_wheel_status()

    def _draw_wheel_title(self, width, height):
        """A small gold sign with a Chinese headline and a serif subtitle."""
        c=self.wheel_canvas
        key=(width,height)
        if getattr(self,'_wheel_label_key',None)==key and c.find_withtag('wheel_labels'):
            c.tag_raise('wheel_labels')
            return
        if not hasattr(self,'_wheel_title_fonts'):
            families=set(tkfont.families(self.root))
            chinese=next((name for name in ('KaiTi','楷体','STKaiti','华文楷体','DFKai-SB','標楷體','Kaiti SC',
                         'Noto Serif CJK SC','Source Han Serif SC','Microsoft YaHei','微软雅黑','SimSun','宋体')
                         if name in families),'serif')
            english=next((name for name in ('Georgia','Palatino Linotype','Times New Roman',
                         'DejaVu Serif') if name in families),'serif')
            headline=tkfont.Font(root=self.root,family=chinese,size=-22,weight='bold')
            subtitle=tkfont.Font(root=self.root,family=english,size=-12,slant='italic')
            # Keep the sign clear of both the circular rim and the right edge,
            # including Windows machines whose CJK fallback font is wider.
            for font,text,maximum in ((headline,'欧式落球轮盘',136),
                                       (subtitle,'Plinko European',126)):
                while font.measure(text)>maximum and font.cget('size') < -10:
                    font.configure(size=font.cget('size')+1)
            self._wheel_title_fonts=(headline,subtitle)
            self._wheel_title_photo=self._make_wheel_title_lettering()
        headline,subtitle=self._wheel_title_fonts
        c.delete('wheel_labels')
        tags=('wheel_labels',)
        x=width-77
        gold,muted,cream='#D3AE61','#8D783F','#FFE4A0'
        # Fine paired rules and a diamond give the title its own visual frame
        # without painting a rectangular panel over the green table felt.
        for side in (-1,1):
            c.create_line(x+side*11,10,x+side*55,10,fill=gold,width=1,tags=tags)
            c.create_line(x+side*11,13,x+side*40,13,fill=muted,width=1,tags=tags)
        c.create_polygon(x,6,x+4,10,x,14,x-4,10,
                         fill=gold,outline=cream,width=.7,tags=tags)
        if self._wheel_title_photo is not None:
            c.create_image(x,42,image=self._wheel_title_photo,tags=(*tags,'wheel_title_lettering'))
        else:
            c.create_text(x+1,33,text='欧式落球轮盘',font=headline,fill='#71521F',tags=tags)
            c.create_text(x,32,text='欧式落球轮盘',font=headline,fill=cream,
                          tags=(*tags,'wheel_title_main'))
            c.create_text(x,54,text='Plinko European',font=subtitle,fill='#DCC58C',
                          tags=(*tags,'wheel_title_subtitle'))
        c.create_line(x-29,68,x+29,68,fill=muted,width=1,tags=tags)
        for tip in (x-34,x+34):
            c.create_polygon(tip,66,tip+2,68,tip,70,tip-2,68,
                             fill=gold,outline='',tags=tags)
        c.create_line(x+64,24,x+68,24,x+68,61,x+60,61,
                      fill=muted,width=1,tags=tags)
        self._wheel_label_key=key
        c.tag_raise('wheel_labels')

    def _make_wheel_title_lettering(self):
        """Smooth gold headline lettering when optional Pillow/fonts exist."""
        if ImageFont is None:
            return None
        scale=4
        font_dir=os.path.join(os.environ.get('WINDIR',r'C:\Windows'),'Fonts')
        chinese_paths=tuple(os.path.join(font_dir,name) for name in
                            ('simkai.ttf','kaiu.ttf','msyhbd.ttc','simsun.ttc'))+(
                            'simkai.ttf','kaiu.ttf','STKaiti.ttf',
                            '/System/Library/Fonts/STKaiti.ttc',
                            'NotoSerifSC.ttf','NotoSerifCJK-Regular.ttc',
                            'NotoSansSC.ttf','NotoSansCJK-Regular.ttc')
        english_paths=(os.path.join(font_dir,'georgiai.ttf'),'georgiai.ttf',
                       'DejaVuSerif-Italic.ttf','LiberationSerif-Italic.ttf',
                       'NimbusRoman-Italic.otf',
                       '/usr/share/fonts/opentype/urw-base35/NimbusRoman-Italic.otf')
        def load(paths,size):
            for path in paths:
                try:
                    return ImageFont.truetype(path,size*scale)
                except (OSError,ValueError):
                    continue
            return None
        headline,subtitle=load(chinese_paths,22),load(english_paths,12)
        if headline is None or subtitle is None:
            return None
        try:
            headline.set_variation_by_name('SemiBold')
        except (AttributeError,OSError,ValueError):
            pass
        resampling=getattr(Image,'Resampling',Image)
        lettering=Image.new('RGBA',(144*scale,50*scale),(0,0,0,0))
        for text,font,centre_y,max_width,is_title in (
                ('欧式落球轮盘',headline,15,136,True),
                ('Plinko European',subtitle,37,126,False)):
            bounds=font.getbbox(text)
            mask=Image.new('L',(bounds[2]-bounds[0]+12,bounds[3]-bounds[1]+12),0)
            ImageDraw.Draw(mask).text((6-bounds[0],6-bounds[1]),text,font=font,fill=255,
                                      stroke_width=1 if is_title else 0)
            mask=mask.crop(mask.getbbox())
            if mask.width>max_width*scale:
                mask=mask.resize((max_width*scale,round(mask.height*max_width*scale/mask.width)),
                                 resampling.LANCZOS)
            left=(lettering.width-mask.width)//2
            top=round(centre_y*scale-mask.height/2)
            if is_title:
                shadow=Image.new('RGBA',mask.size,'#71521F')
                shadow.putalpha(mask)
                lettering.alpha_composite(shadow,(left+2,top+3))
                ink=Image.new('RGBA',mask.size)
                brush=ImageDraw.Draw(ink)
                stops=((255,242,205),(248,218,147),(201,152,66))
                for row in range(mask.height):
                    position=row/max(1,mask.height-1)*2
                    band=min(1,int(position))
                    blend=position-band
                    color=tuple(round(a+(b-a)*blend) for a,b in zip(stops[band],stops[band+1]))
                    brush.line((0,row,mask.width,row),fill=(*color,255))
            else:
                ink=Image.new('RGBA',mask.size,'#DCC58C')
            ink.putalpha(mask)
            lettering.alpha_composite(ink,(left,top))
        lettering=lettering.resize((144,50),resampling.LANCZOS)
        return ImageTk.PhotoImage(lettering,master=self.wheel_canvas)

    def _draw_wheel_status(self):
        c=self.wheel_canvas
        bg,fg='#122C40','#E1F9FF'
        if self.round_state=='result':
            title,text='结果',str(self.center_display_result)
            bg=OUTCOME_COLORS.get(text,'#17273A')
        elif self.round_state=='dropping':
            title,text=('入槽减速','…') if self.physics.mode=='storage' else ('落球中','↓')
        elif self.round_state=='returning':
            title,text='返回顶部','↑'
        elif self.round_state=='recovering':
            title,text='本局取消','退款'
            bg='#795018'
        else:
            title,text='开放下注','准备中' if self._launch_ready_remaining() else 'Enter'
        key=(title,text,bg,fg)
        if getattr(self,'_wheel_hud_key',None)==key and c.find_withtag('wheel_hud'):
            c.tag_raise('wheel_hud')
            return
        c.delete('wheel_hud')
        self._wheel_hud_key=key
        tags=('wheel_hud',)
        c.create_rectangle(5,12,89,74,fill=bg,outline='#548CA6',width=1,tags=tags)
        c.create_text(47,26,text=title,fill=fg,font=('Arial',10,'bold'),tags=tags)
        self.wheel_timer_id=c.create_text(47,52,text=text,fill=fg,font=('Arial',20,'bold'),tags=tags)


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

        # European single zero – merged straight spot
        zero_height = 2 * g.zero_h   # total height = 3 * num_h
        add_spot(
            "straight_0",
            "straight",
            "0",
            {"0"},
            BET_ODDS["straight"],
            (g.zero_x1, g.grid_y1, g.zero_x2, g.grid_y1 + zero_height),
            ((g.zero_x1 + g.zero_x2) / 2, g.grid_y1 + zero_height / 2),
            kind="cell",
        )

        for row in range(3):
            for col in range(12):
                num = str(g.rows[row][col])
                x1, y1, x2, y2 = g.cell_bounds(row, col)
                add_spot(
                    f"straight_{num}",
                    "straight",
                    num,
                    {num},
                    BET_ODDS["straight"],
                    (x1, y1, x2, y2),
                    ((x1 + x2) / 2, (y1 + y2) / 2),
                    kind="cell",
                    extra={"row": row, "col": col},
                )

        # Dozens
        dozen_w = 4 * g.num_w
        for idx, label in enumerate(["1st 12", "2nd 12", "3rd 12"]):
            x1 = g.grid_x1 + idx * dozen_w
            x2 = x1 + dozen_w
            add_spot(
                f"dozen_{idx + 1}",
                "dozen",
                label,
                g.doze_numbers(idx),
                BET_ODDS["dozen"],
                (x1, g.dozen_y1, x2, g.dozen_y2),
                ((x1 + x2) / 2, (g.dozen_y1 + g.dozen_y2) / 2),
                kind="rectangle",
            )

        # Column bets
        column_labels = ["3rd Column", "2nd Column", "1st Column"]
        column_sets = [
            [str(n) for n in range(3, 37, 3)],
            [str(n) for n in range(2, 36, 3)],
            [str(n) for n in range(1, 35, 3)],
        ]
        for row in range(3):
            y1 = g.grid_y1 + row * g.num_h
            y2 = y1 + g.num_h
            add_spot(
                f"column_{row}",
                "column",
                column_labels[row],
                column_sets[row],
                BET_ODDS["column"],
                (g.col_x1, y1, g.col_x2, y2),
                ((g.col_x1 + g.col_x2) / 2, (y1 + y2) / 2),
                kind="rectangle",
            )

        # Outside bets
        seg_w = (g.grid_x2 - g.grid_x1) / 6
        outer_labels = [
            ("1-18", set(str(n) for n in range(1, 19))),
            ("Even", set(str(n) for n in range(1, 37) if n % 2 == 0)),
            ("Red", set(str(n) for n in RED_NUMBERS)),
            ("Black", set(str(n) for n in range(1, 37) if n not in RED_NUMBERS)),
            ("Odd", set(str(n) for n in range(1, 37) if n % 2 == 1)),
            ("19-36", set(str(n) for n in range(19, 37))),
        ]
        for idx, (label, numbers) in enumerate(outer_labels):
            x1 = g.grid_x1 + idx * seg_w
            x2 = x1 + seg_w
            spot_type = "color" if label in {"Red", "Black"} else ("odd_even" if label in {"Odd", "Even"} else "high_low")
            payout = BET_ODDS["color"] if label in {"Red", "Black"} else BET_ODDS["odd_even"]
            add_spot(
                f"outside_{idx}",
                spot_type,
                label,
                numbers,
                payout,
                (x1, g.outer_y1, x2, g.outer_y2),
                ((x1 + x2) / 2, (g.outer_y1 + g.outer_y2) / 2),
                kind="rectangle",
            )

        # Special zero-area split / intersection bets (European style)
        # split 0-1
        add_spot(
            "split_0_1",
            "split",
            "0-1",
            {"0", "1"},
            BET_ODDS["split"],
            (g.zero_x2 - 9, g.grid_y1 + 2 * g.num_h + 8, g.zero_x2 + 9, g.grid_y1 + 3 * g.num_h - 8),
            (g.zero_x2, g.grid_y1 + 2.5 * g.num_h),
            kind="line",
        )
        # split 0-2
        add_spot(
            "split_0_2",
            "split",
            "0-2",
            {"0", "2"},
            BET_ODDS["split"],
            (g.zero_x2 - 9, g.grid_y1 + g.num_h + 8, g.zero_x2 + 9, g.grid_y1 + 2 * g.num_h - 8),
            (g.zero_x2, g.grid_y1 + 1.5 * g.num_h),
            kind="line",
        )
        # split 0-3
        add_spot(
            "split_0_3",
            "split",
            "0-3",
            {"0", "3"},
            BET_ODDS["split"],
            (g.zero_x2 - 9, g.grid_y1 + 8, g.zero_x2 + 9, g.grid_y1 + g.num_h - 8),
            (g.zero_x2, g.grid_y1 + g.num_h / 2),
            kind="line",
        )
        # street 0-1-2
        add_spot(
            "triple_0_1_2",
            "street",
            "0-1-2",
            {"0", "1", "2"},
            BET_ODDS["street"],
            (g.zero_x2 - 10, g.grid_y1 + 2 * g.num_h - 10, g.zero_x2 + 10, g.grid_y1 + 2 * g.num_h + 10),
            (g.zero_x2, g.grid_y1 + 2 * g.num_h),
            kind="point",
        )
        # Zero-area trio 0-2-3, also used by Voisins du Zero.
        add_spot(
            "triple_0_2_3",
            "street",
            "0-2-3",
            {"0", "2", "3"},
            BET_ODDS["street"],
            (g.zero_x2 - 10, g.grid_y1 + g.num_h - 10, g.zero_x2 + 10, g.grid_y1 + g.num_h + 10),
            (g.zero_x2, g.grid_y1 + g.num_h),
            kind="point",
        )

        # Split spots: vertical and horizontal
        for row in range(3):
            for col in range(11):
                n1 = str(g.rows[row][col])
                n2 = str(g.rows[row][col + 1])
                x1, y1, x2, y2 = g.cell_bounds(row, col)
                _, _, nx2, _ = g.cell_bounds(row, col + 1)
                cx = x2
                cy = (y1 + y2) / 2
                add_spot(
                    f"split_v_{row}_{col}",
                    "split",
                    f"{n1}-{n2}",
                    {n1, n2},
                    BET_ODDS["split"],
                    (cx - 8, y1 + 6, cx + 8, y2 - 6),
                    (cx, cy),
                    kind="line",
                    extra={"orientation": "v"},
                )

        for col in range(12):
            for row in range(2):
                n1 = str(g.rows[row][col])
                n2 = str(g.rows[row + 1][col])
                x1, y1, x2, y2 = g.cell_bounds(row, col)
                cx = (x1 + x2) / 2
                cy = y2
                add_spot(
                    f"split_h_{row}_{col}",
                    "split",
                    f"{n1}-{n2}",
                    {n1, n2},
                    BET_ODDS["split"],
                    (x1 + 6, cy - 8, x2 - 6, cy + 8),
                    (cx, cy),
                    kind="line",
                    extra={"orientation": "h"},
                )

        # Corner spots: give them a larger square around the intersection
        for row in range(2):
            for col in range(11):
                nums = {
                    str(g.rows[row][col]),
                    str(g.rows[row][col + 1]),
                    str(g.rows[row + 1][col]),
                    str(g.rows[row + 1][col + 1]),
                }
                x1, y1, x2, y2 = g.cell_bounds(row, col)
                ix = x2
                iy = y2
                add_spot(
                    f"corner_{row}_{col}",
                    "corner",
                    ",".join(sorted(nums, key=lambda s: (len(s), s))),
                    nums,
                    BET_ODDS["corner"],
                    (ix - 10, iy - 10, ix + 10, iy + 10),
                    (ix, iy),
                    kind="point",
                )

        # Street spots: horizontal line under each column, between grid and dozens
        street_y = g.dozen_y1
        for col in range(12):
            numbers = {str(g.rows[r][col]) for r in range(3)}
            x1, y1, x2, y2 = g.cell_bounds(0, col)
            add_spot(
                f"street_{col}",
                "street",
                "-".join(sorted(numbers, key=lambda s: int(s))),
                numbers,
                BET_ODDS["street"],
                (x1 + 4, street_y - 8, x2 - 4, street_y + 8),
                ((x1 + x2) / 2, street_y),
                kind="line",
                extra={"col": col},
            )

        # Six line spots: intersection between two streets and the dozen line
        for col in range(11):
            numbers = {str(g.rows[r][col]) for r in range(3)} | {str(g.rows[r][col + 1]) for r in range(3)}
            x1, y1, x2, y2 = g.cell_bounds(0, col)
            nx1, ny1, nx2, ny2 = g.cell_bounds(2, col + 1)
            bx = x2
            add_spot(
                f"six_line_{col}_{col+1}",
                "six_line",
                f"{col+1}/{col+2}",
                numbers,
                BET_ODDS["six_line"],
                (bx - 10, g.dozen_y1 - 10, bx + 10, g.dozen_y1 + 10),
                (bx, g.dozen_y1),
                kind="point",
            )

        return spots

    def _spot_numbers(self, spot):
        return set(spot.get("numbers", set()))

    def _chip_fill_color_for_amount(self, amount: int) -> str:
        try:
            amt = int(amount)
        except Exception:
            amt = 0

        if amt <= 4:
            return "#ffffff"
        if amt <= 9:
            return "#9e9e9e"
        if amt <= 24:
            return "#0000ff"
        if amt <= 99:
            return "#00ff00"
        if amt <= 499:
            return "#A8ECFF"
        return "#FF7DDA"

    def _bet_limit_for_spot(self, spot):
        inside_types = {"straight", "split", "street", "corner", "six_line"}
        if spot.get("type") in inside_types:
            return 200
        return 500
    
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

        if 1 <= amount <= 4:
            return "#ffffff", "black"
        if 5 <= amount <= 9:
            return "#9e9e9e", "black"
        if 10 <= amount <= 24:
            return "#0000ff", "white"
        if 25 <= amount <= 99:
            return "#00ff00", "black"
        if 100 <= amount <= 499:
            return "#A8ECFF", "black"
        if 500 <= amount <= 999:
            return "#FF7DDA", "black"
        return "#9400b6", "white"

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

        # 内围投注
        if spot["type"] in (
            "straight",
            "split",
            "corner",
            "street",
            "six_line",
        ):
            return 10

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

        if spot["type"] in ("straight", "split", "corner", "street"):
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

        txt = self.board_canvas.create_text(
            center_x,
            center_y,
            text=self._format_win_amount(display_amount),
            fill=display_text_color,
            font=("Arial", 7, "bold"),
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
        if self._chip_transfer_active:
            return
        pending = self._region_contributions() if self.round_state == "betting" else {}
        self.board_canvas.delete("chips")
        self.placed_chip_items = {}
        for spot_id, amount in self.current_bets.items():
            amount -= pending.get(spot_id, 0)
            if amount > 0:
                spot = self._find_spot_by_id(spot_id)
                if spot:
                    fill = self.current_bet_colors.get(spot_id, self._chip_fill_color_for_amount(amount))
                    self._draw_chip_on_spot(spot, amount, fill)
        self.board_canvas.delete("pending_regions")
        if pending:
            self.board_canvas.create_text(BOARD_W / 2, 256,
                text="当前在跑道盘中有下注，开局时自动拆分", fill="#F5D68A",
                font=("Arial", 9), tags="pending_regions")
        self._draw_racetrack()
        self._update_betting_view_controls()

    # =====================================================
    # Board click handling
    # =====================================================

    def on_board_click(self, event):
        if self.round_state != "betting" or self.betting_view != "table":
            return
        spot = self._spot_by_point(event.x, event.y)
        if not spot:
            return
        self.place_bet(spot["id"])

    def on_board_right_click(self, event):
        if self.round_state != "betting" or self.betting_view != "table":
            return
        spot = self._spot_by_point(event.x, event.y)
        if not spot:
            return
        self.clear_single_bet(spot["id"])

    # =====================================================
    # Betting / settlement
    # =====================================================

    def place_bet(self, spot_id: str):
        if self.round_state != "betting" or self.betting_view != "table":
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
            return

        actual_amount = min(amount, remaining_limit)
        if self.balance < actual_amount * self.bet_multiplier:
            messagebox.showwarning("余额不足", f"余额不足，无法下注 ${actual_amount * self.bet_multiplier:,.0f}。")
            return

        self.balance -= actual_amount * self.bet_multiplier
        self.current_bets[spot_id] = existing + actual_amount
        self.current_bet_colors[spot_id] = self._chip_fill_color_for_amount(self.current_bets[spot_id])

        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        total_bet = sum(self.current_bets.values()) * self.bet_multiplier
        self._show_round_amount("本局下注金额", sum(self.current_bets.values()))

    def clear_bets(self):
        """清除当前所有下注，并退还金额"""
        if self.round_state != "betting":
            return

        refund = sum(self.current_bets.values()) * self.bet_multiplier

        if refund > 0:
            self.balance += refund

        self.region_bets.clear()
        self.current_bets.clear()
        self.current_bet_colors.clear()

        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        self._show_round_amount("本局下注金额", 0)

    def clear_single_bet(self, spot_id: str):
        if self.round_state != "betting":
            return
        pending = self._region_contributions().get(spot_id, 0)
        amount = self.current_bets.get(spot_id, 0) - pending
        if amount > 0:
            self.balance += amount * self.bet_multiplier
            if pending:
                self.current_bets[spot_id] = pending
                self.current_bet_colors[spot_id] = self._chip_fill_color_for_amount(pending)
            else:
                self.current_bets.pop(spot_id, None)
                self.current_bet_colors.pop(spot_id, None)
            self._refresh_balance_display()
            self._refresh_bet_totals()
            self._repaint_all_chips()
        elif pending:
            messagebox.showinfo("区域下注", "请在跑道盘对应区域按右键，撤销完整区域下注。")

    def _show_round_amount(self, title, base_amount):
        total = base_amount * self.bet_multiplier
        self.current_chip_label.config(
            text=f"{title}\n${base_amount:,.0f} * {self.bet_multiplier} = ${total:,.0f}")

    def _step_multiplier(self, direction):
        options = (1, 2, 5, 10, 20, 50, 100)
        index = options.index(self.bet_multiplier)
        index = max(0, min(len(options) - 1, index + direction))
        self.multiplier_var.set(str(options[index]))
        self._change_multiplier()

    def _change_multiplier(self, event=None):
        """Keep table bets in base units; charge/refund the cash difference."""
        if self.round_state != "betting":
            self.multiplier_var.set(str(self.bet_multiplier))
            return
        new_multiplier = int(self.multiplier_var.get())
        base_total = sum(self.current_bets.values())
        difference = base_total * (new_multiplier - self.bet_multiplier)
        if difference > self.balance:
            self.multiplier_var.set(str(self.bet_multiplier))
            messagebox.showwarning("余额不足", f"调整倍数还需 ${difference:,.0f}。")
            return
        self.balance -= difference
        self.bet_multiplier = new_multiplier
        self.multiplier_display.config(text=f"×{new_multiplier}")
        self._refresh_balance_display()
        self._refresh_bet_totals()

    def _refresh_bet_totals(self):
        self._update_betting_view_controls()
        base_total = sum(self.current_bets.values())
        if self.round_state == "betting":
            self._show_round_amount("本局下注金额", base_total)
        total_bet = sum(self.current_bets.values()) * self.bet_multiplier
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
                win_amount = amount * multiplier * self.bet_multiplier
                total_payout += win_amount
                self.balance += win_amount

        if self.username != "Guest":
            update_balance_in_json(self.username, self.balance)

        self.last_win_amount = int(total_payout)

        self._show_round_amount("本局获胜金额", total_payout / self.bet_multiplier)
        return total_payout

    # =====================================================
    # Game flow
    # =====================================================
    def _start_new_round(self, *, launch_delay=0.0):
        """Open betting only after the single ball has reached its launcher."""
        self._cancel_chip_transfer()
        self.region_bets.clear()
        self.racetrack_hover = self.region_hover = None
        if self.physics is None:
            self.physics = PlinkoPhysics(initial_angle=math.radians(self.current_wheel_offset))
        self.physics.prepare_next_round()
        self._launch_ready_at = self.physics.t+launch_delay if launch_delay>0 else None
        self._round_refund_handled = False
        self._locked_stake = 0
        self._round_settled = True
        self.ball_visible = True
        self.last_spin_data = None
        self._stop_result_flash()
        self.result_chip_display = {}
        self.current_bets = {}
        self.current_bet_colors = {}
        self._locked_numbers = set()
        self.center_display_result = None
        self.current_round_result = self.current_round_index = None
        self.round_state = "betting"
        self._sync_physics_display()
        self._enable_amount_buttons()
        self._set_control_buttons_state(tk.NORMAL)
        self._refresh_bet_totals()
        self._redraw_board_for_result_flash(flash_on=False)
        self._add_help_button_on_board()
        self._draw_wheel()


    def _covered_wheel_numbers(self):
        if self.round_state != "betting":
            return set(self._locked_numbers)
        numbers = set()
        for spot_id, amount in self.current_bets.items():
            if amount > 0:
                spot = self._find_spot_by_id(spot_id)
                if spot:
                    numbers.update(spot["numbers"])
        return numbers

    def _lock_bets_and_spin(self):
        """One player action freezes all bets and releases the waiting ball."""
        if self.round_state != "betting" or self._launch_ready_remaining():
            return
        if self.detail_window and self.detail_window.winfo_exists():
            self.detail_window.destroy()
            self.detail_window = None
        self._store_current_bets_as_last()
        self._locked_numbers = self._covered_wheel_numbers()
        self._locked_stake = sum(self.current_bets.values())*self.bet_multiplier
        self.round_state = "dropping"
        self._disable_amount_buttons()
        self._set_control_buttons_state(tk.DISABLED)
        self.board_canvas.delete("pending_regions")
        self._animate_chips_to_table()
        self._start_physical_spin()

    def _launch_ready_remaining(self):
        """Betting opens at the top; only the next release waits four seconds."""
        if self._launch_ready_at is None or self.physics is None:
            return 0.0
        return max(0.0,self._launch_ready_at-self.physics.t)

    def _update_action_button(self):
        if self.round_state == "betting" and self._launch_ready_remaining():
            text, state = "可下注 · 落球准备中…", tk.DISABLED
        elif self.round_state == "betting":
            text, state = "开始落球 (Enter)", tk.NORMAL
        elif self.round_state == "dropping":
            text, state = "落球中…", tk.DISABLED
        elif self.round_state == "returning":
            text, state = "小球返回顶部…", tk.DISABLED
        elif self.round_state == "recovering":
            text, state = "本局已退款 · 挡板复位／回球中…", tk.DISABLED
        else:
            text, state = "显示结果", tk.DISABLED
        self.deal_button.config(text=text, state=state)

    def _handle_enter(self, event=None):
        # Repeated key presses share the same one-ball-per-round state guard.
        # The frame loop also remembers a held key across result/return phases.
        self._enter_down = True
        self.start_game()
        return "break"

    def _release_enter(self, event=None):
        self._cancel_held_enter()
        return "break"

    def _cancel_held_enter(self, event=None):
        # A key released outside this window may never send us KeyRelease.
        self._enter_down = False

    def _start_startup_rotation(self):
        self._last_physics_time = time.monotonic()
        if self._spin_job is None:
            self._physics_update()

    def _sync_physics_display(self):
        wheel, speed, theta, omega, radius, height = self.physics.render_state()
        self.current_wheel_offset = math.degrees(wheel) % 360
        self.wheel_velocity = math.degrees(speed)
        self.pointer_angle = math.degrees(theta) % 360
        self.pointer_velocity = math.degrees(omega)
        self.ball_radius = radius*WHEEL_METRE_SCALE
        self.ball_height = height
        self.ball_pocket_index = self.physics.occupied_pocket_at(theta,radius,wheel)

    def _start_physical_spin(self):
        if self.round_state != "dropping" or self.physics.mode != "waiting":
            return
        now = time.monotonic()
        self.physics.advance(max(0.0, now-self._last_physics_time))
        self._last_physics_time = now
        if not self.physics.release():
            return
        self._round_settled = False
        self.round_state = "dropping"
        self.is_pointer_spinning = self.ball_visible = True
        self._sync_physics_display()
        self._update_action_button()
        self._draw_wheel()

    def _advance_game_animation(self, seconds):
        """One time-driven state transition path, shared by UI and verification."""
        self.physics.advance(seconds)
        self._sync_physics_display()
        if self.physics.round_cancelled and not self._round_refund_handled:
            self._refund_cancelled_round()
        if (self.round_state == "dropping" and self.physics.result_index is not None
                and not self._round_settled):
            self._finish_physical_spin()
        if self.round_state == 'recovering' and self.physics.mode == 'recovery_ready':
            self.physics.begin_return()
        if self.round_state in {'returning','recovering'} and self.physics.mode == "waiting":
            self._start_new_round(launch_delay=self.TOP_READY_SECONDS)
        if (self.round_state == "betting" and self._launch_ready_at is not None
                and not self._launch_ready_remaining()):
            self._launch_ready_at = None
            self._update_action_button()

    def _refund_cancelled_round(self):
        """Credit the locked cash stake once, without recording an outcome."""
        if self._round_refund_handled:
            return
        self._round_refund_handled = True
        self._round_settled = True
        self._cancel_chip_transfer()
        self.region_bets.clear()
        self.balance += self._locked_stake
        self._stop_result_flash()
        self.current_bets.clear()
        self.current_bet_colors.clear()
        self._locked_numbers.clear()
        self.result_chip_display = {}
        self.last_spin_data = None
        self.last_win_amount = 0
        self.current_round_result = self.current_round_index = None
        self.center_display_result = None
        self.round_state = 'recovering'
        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._show_round_amount('本局取消 · 已退还下注',self._locked_stake/self.bet_multiplier)
        self._redraw_board_for_result_flash(flash_on=False)
        self._set_control_buttons_state(tk.DISABLED)

    def _finish_result_flash(self):
        """The original six-second result display finishes before ball return."""
        self._result_finish_job = None
        if self._closing or self.round_state != 'result':
            return
        self._stop_result_flash()
        self._redraw_board_for_result_flash(flash_on=False)
        if self.physics.begin_return():
            self.round_state = 'returning'
            self._update_action_button()

    def _physics_update(self):
        self._spin_job = None
        if self._closing or not self.winfo_exists():
            return
        now = time.monotonic()
        self._advance_game_animation(max(0.0, now-self._last_physics_time))
        self._last_physics_time = now
        # Continue a held Enter only when betting is open and the existing
        # four-second preparation is over. No OS key-repeat timing is needed.
        if self._enter_down and self.round_state == 'betting':
            self.start_game()
        self.is_spinning = abs(self.physics.wheel_speed) > 1e-9
        self._draw_wheel()
        # Include rendering time in the frame budget instead of adding a full
        # 16 ms pause after every drawing pass.
        render_ms=(time.monotonic()-now)*1000
        self._spin_job = self.after(max(1,16-int(render_ms)), self._physics_update)

    def _finish_physical_spin(self):
        if self.physics.round_cancelled:
            self._refund_cancelled_round()
            return
        if self._round_settled or self.physics.result_index is None:
            return
        self._round_settled = True
        self.is_pointer_spinning = False
        self.current_round_index = self.physics.result_index
        self.current_round_result = ROULETTE_SEQUENCE[self.current_round_index]
        self._finish_round(self.current_round_result)
        self._update_action_button()


    def _get_winning_spot_ids(self, result: str):
        """
        Only straight up bets and outside bets flash.
        不闪的类型：
        split / corner / street / six_line
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
        if self._result_finish_job is not None:
            try:
                self.after_cancel(self._result_finish_job)
            except tk.TclError:
                pass
            self._result_finish_job = None
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
            text = spot["label"]  # 0 / 1-36
            font = ("Arial", 11, "bold")
            angle = 90

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

                self.board_canvas.create_rectangle(
                    int(x1), int(y1), int(x2), int(y2),
                    fill="#ffffff",
                    outline="#000000",
                    width=2,
                    tags=("result_flash",)
                )
                self._draw_flash_label(spot, fill="#000000")

        self._repaint_all_chips()

    def _finish_round(self, result):
        if self.physics.round_cancelled:
            self._refund_cancelled_round()
            return
        self._cancel_chip_transfer()
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
        self._result_finish_job = self.after(self.RESULT_DISPLAY_MS,self._finish_result_flash)

        self.last_spin_data = {
            "result": result,
            "pointer_angle": self.pointer_angle,               # 指针最终角度（0~360）
            "wheel_offset": self.current_wheel_offset,         # 轮盘最终偏移角度
            "drop_seconds": round(self.physics.captured_at-self.physics.drop_started_at, 4),
            "obstacle_hits": self.physics.obstacle_hits,
            "result_index": self.current_round_index,          # 在 ROULETTE_SEQUENCE 中的索引
            "release_angle": math.degrees(self.physics.drop_angle) % 360,
            "release_speed": math.degrees(self.physics.drop_start_speed),
            "motor_phase_slots": self.physics.phase_offset_slots,
            "phase_mix_seconds": self.physics.PHASE_MIX_SECONDS,
        }

    # =====================================================
    # Misc / controls
    # =====================================================

    def _set_bet_buttons_state(self, state):
        pass

    def _enable_amount_buttons(self):
        for chip in self.chip_buttons:
            chip["canvas"].config(state=tk.NORMAL)
            chip["canvas"].bind("<Button-1>", lambda e, t=chip["text"], c=chip["canvas"], cid=chip["chip_id"], bg=chip.get("bg_color", "#ffffff"): self._set_bet_amount(t, c, cid, bg))

    def _disable_amount_buttons(self):
        for chip in self.chip_buttons:
            chip["canvas"].config(state=tk.DISABLED)
            chip["canvas"].unbind("<Button-1>")

    def _set_control_buttons_state(self, state):
        """
        控制游戏相关按钮的状态（清除下注、重复上局下注、开始落球）
        state: tk.NORMAL 或 tk.DISABLED
        """
        for button in self.multiplier_buttons:
            button.config(state=state)
        self._update_action_button()
        self.reset_button.config(state=state)
        self.repeat_last_btn.config(state=state)
        self._update_betting_view_controls()
        
        # 如果是在投注阶段启用按钮，重复按钮还需要根据余额和上一局数据单独控制
        if state == tk.NORMAL:
            self._update_repeat_button_state()

    def _refresh_balance_display(self):
        self.balance_label_side.config(text=f"余额: ${self.balance:,.2f}")
        if self.username != "Guest":
            update_balance_in_json(self.username, self.balance)
        self._update_repeat_button_state()

    def on_close(self):
        if self._closing:
            return
        self._closing = True
        self._cancel_chip_transfer()
        self._cancel_held_enter()
        for sequence, binding in self._enter_bindings.items():
            self.root.unbind_class(self._enter_tag, sequence)
            self.root.deletecommand(binding)
        self._enter_bindings.clear()
        self.root.bindtags(tuple(tag for tag in self.root.bindtags() if tag != self._enter_tag))
        # Unreleased bets are refunded; a released ball is settled exactly once.
        if self.round_state == "betting":
            self.balance += sum(self.current_bets.values()) * self.bet_multiplier
            self.current_bets.clear()
        elif self.round_state == "dropping" and not self._round_settled:
            while self.physics.result_index is None and not self.physics.round_cancelled:
                self.physics.advance(.25)
            self._sync_physics_display()
            if self.physics.round_cancelled:
                self._refund_cancelled_round()
            else:
                self._finish_physical_spin()
        # 父窗口继续运行时，取消属于当前游戏页面的所有定时回调。
        for job in self.tk.splitlist(self.tk.call("after", "info")):
            try:
                script = self.tk.call("after", "info", job)[0]
                command = self.tk.splitlist(script)[0]
                if command in (self._tclCommands or ()):
                    self.after_cancel(job)
            except (tk.TclError, IndexError):
                pass
        self._wheel_text_frame_images=[]
        getattr(self,'_wheel_number_images',{}).clear()
        self._wheel_title_photo=None
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

    def _draw_instruction_layout(self, canvas, bet_type):
        """Use the actual board and bet-spot geometry in the illustrated guide."""
        draw_roulette_static(canvas, scale=BOARD_SCALE)
        dx, dy = 146, 35
        canvas.move("all", dx, dy)
        canvas.create_text(400, 16, text="选择注型，查看筹码应放在哪里", fill="#F5D68A",
                           font=("Arial", 15, "bold"))
        spot = next(s for s in self.bet_spots if s["type"] == bet_type)
        x1, y1, x2, y2 = spot["bounds"]
        canvas.create_rectangle(x1 + dx, y1 + dy, x2 + dx, y2 + dy,
                                outline="#F5D68A", width=3)
        cx, cy = spot["center"]
        canvas.create_oval(cx + dx - 11, cy + dy - 11, cx + dx + 11, cy + dy + 11,
                           fill="#F5D68A", outline="white", width=2)
        canvas.create_text(cx + dx, cy + dy, text="25", fill="#173F58", font=("Arial", 9, "bold"))
        canvas.create_text(400, 320, text=f"{spot['label']}  ·  覆盖 {len(spot['numbers'])} 个号码",
                           fill="white", font=("Arial", 16, "bold"))
        for x, title, value in ((70, "净赔率", f"{spot['payout']}:1"),
                                (415, "押中时返还（含该注本金）", f"25 × {spot['payout'] + 1} = ${25 * (spot['payout'] + 1):,}")):
            canvas.create_rectangle(x, 360, x + 315, 454, fill="#284C40", outline="#5A8271")
            canvas.create_text(x + 157, 384, text=title, fill="#F5D68A", font=("Arial", 12, "bold"))
            canvas.create_text(x + 157, 423, text=value, fill="white", font=("Arial", 20, "bold"))
        canvas.create_text(400, 493, text="金色筹码 = 下注位置    ·    金色边框 = 可点击的下注位",
                           fill="#F5D68A", font=("Arial", 12))
        canvas.create_text(400, 531, text="示例使用基础筹码 25、倍数 1。左键下注；右键清除该下注位并退款。",
                           fill="white", font=("Arial", 11))

    def _draw_instruction_racetrack(self, canvas, neighbors):
        canvas.delete("all")
        canvas.create_text(400, 18, text="鼠标指向 0：中心浅蓝、邻号向外逐级变浅；深色文字、深蓝描边",
                           fill="#F5D68A", font=("Arial", 14, "bold"))
        outlines = []
        for index, number in enumerate(RACETRACK_SEQUENCE):
            fractions = [(index + step / 6) / len(RACETRACK_SEQUENCE) for step in range(7)]
            points = [self._racetrack_point(t, 94) for t in fractions]
            points += [self._racetrack_point(t, 50) for t in reversed(fractions)]
            points = [(x * 1.35 + 57, y * 1.35 + 40) for x, y in points]
            distance = self._racetrack_distance(number, "0")
            selected = distance <= neighbors
            canvas.create_polygon(*[v for point in points for v in point],
                                   fill=RACETRACK_NEIGHBOR_HOVER_FILLS[min(distance, 5)] if selected else OUTCOME_COLORS[number],
                                   outline=RACETRACK_NEIGHBOR_HOVER_EDGE if selected else "#3A8064", width=1)
            if distance <= neighbors:
                outlines.append((distance, points))
            x, y = self._racetrack_point((index + 0.5) / len(RACETRACK_SEQUENCE), 72)
            canvas.create_text(x * 1.35 + 57, y * 1.35 + 40, text=number,
                               fill=RACETRACK_NEIGHBOR_HOVER_TEXT if selected else "white", font=("Arial", 12, "bold"))
        for distance, points in sorted(outlines, reverse=True):
            canvas.create_line(*[v for point in points + [points[0]] for v in point],
                                fill=RACETRACK_NEIGHBOR_HOVER_EDGE, width=4, joinstyle=tk.ROUND)
        count = neighbors * 2 + 1
        canvas.create_text(400, 171, text="欧式落球轮盘", fill="#F5D68A",
                           font=("Georgia", 25, "bold italic"))
        canvas.create_text(400, 215, text=f"左右各 {neighbors} 个邻号  =  共 {count} 个直注",
                           fill="white", font=("Arial", 13, "bold"))
        for distance in range(6):
            x = 73 + distance * 110
            canvas.create_rectangle(x, 335, x + 100, 374,
                                    fill=RACETRACK_NEIGHBOR_HOVER_FILLS[distance], outline=RACETRACK_NEIGHBOR_HOVER_EDGE, width=3)
            canvas.create_text(x + 50, 354, text="中心" if distance == 0 else f"左右 {distance}",
                               fill=RACETRACK_NEIGHBOR_HOVER_TEXT, font=("Arial", 11, "bold"))
        stake = 25 * count
        for x, title, value in ((30, "整组扣款", f"${stake:,}"),
                                (292, "0 中奖：含本金返还", "$900"),
                                (554, "扣除整组下注后净赢", f"${900 - stake:,}")):
            canvas.create_rectangle(x, 408, x + 216, 486, fill="#284C40", outline="#5A8271")
            canvas.create_text(x + 108, 429, text=title, fill="#F5D68A", font=("Arial", 11, "bold"))
            canvas.create_text(x + 108, 465, text=value, fill="white", font=("Arial", 20, "bold"))
        canvas.create_text(400, 517, text="示例：每号 25、倍数 1，开出 0。中奖直注返还 25 × 36，其余直注输掉。",
                           fill="white", font=("Arial", 11))
        canvas.create_text(400, 547, text="邻号 0 = 单押一个号码；邻号 5 = 共押 11 个号码。右键只清除一个号码。",
                           fill="#F5D68A", font=("Arial", 11))

    def _draw_instruction_flow(self, canvas):
        canvas.delete("all")
        def card(x, y, w, h, title, value):
            canvas.create_rectangle(x, y, x + w, y + h, fill="#284C40", outline="#5A8271", width=2)
            canvas.create_text(x + w / 2, y + 23, text=title, fill="#F5D68A", font=("Arial", 12, "bold"))
            canvas.create_text(x + w / 2, y + h / 2 + 14, text=value, fill="white",
                               font=("Arial", 13, "bold"), width=w - 18)
        def arrow(x1, y1, x2, y2):
            canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill="#F5D68A", width=3)
        canvas.create_text(400, 18, text="一局流程与筹码计算", fill="#F5D68A", font=("Arial", 16, "bold"))
        card(25, 48, 225, 90, "1 下注", "不限时间\n轮盘持续快速转动")
        arrow(258, 92, 282, 92)
        card(288, 48, 225, 90, "2 手动落球", "按 Enter 或开始落球\n同时关闭下注")
        arrow(521, 92, 545, 92)
        card(551, 48, 224, 90, "3 结算与回球", "回到顶部 → 即可下注\n准备 4 秒 → 可再次落球")
        card(70, 165, 250, 95, "輪盤布局 Roulette Layout", "Straight Up 直注筹码")
        arrow(332, 205, 466, 205); arrow(466, 224, 332, 224)
        card(480, 165, 250, 95, "Racetrack", "同一号码、同一金额")
        canvas.create_text(400, 281, text="下注阶段两种视图共享下注；筹码转移 / 落球 / 结果展示 / 回球时锁定切换。",
                           fill="white", font=("Arial", 11))
        card(25, 310, 225, 83, "内围每个下注位", "基础上限 200")
        card(288, 310, 225, 83, "外围每个下注位", "基础上限 500")
        card(551, 310, 224, 83, "实际扣款", "基础下注总和 × 倍数")
        canvas.create_text(400, 420, text="结算示例：直注基础 25 × 倍数 10，押中一个号码", fill="#F5D68A",
                           font=("Arial", 12, "bold"))
        card(25, 445, 225, 81, "扣款", "$250")
        card(288, 445, 225, 81, "含本金返还", "25 × 36 × 10 = $9,000")
        card(551, 445, 224, 81, "净赢", "$8,750")
        canvas.create_text(400, 551, text="邻号按每号剩余额度加注；区域组合保持拆注比例，余额不足则整组不下注。",
                           fill="white", font=("Arial", 11))

    def show_game_instructions(self):
        """参考卡片式说明布局；所有赔率、返还与结算示例均用表格显示。"""
        import tkinter as tk
        import tkinter.font as tkfont

        current = getattr(self, '_instruction_window', None)
        if current is not None:
            try:
                if current.winfo_exists():
                    current.lift()
                    current.focus_set()
                    return
            except tk.TclError:
                pass

        parent = self.winfo_toplevel()
        parent.update_idletasks()
        dialog = tk.Toplevel(parent)
        self._instruction_window = dialog
        title = '欧式落球轮盘 · 完整图解玩法'
        dialog.title(title)
        dialog.transient(parent)
        BG, HEADER, SIDEBAR = '#faf5e8', '#f1e7cd', '#f2e8d0'
        PANEL, PANEL_2, BORDER = '#fffdf7', '#f5ecd6', '#c9b88a'
        GOLD, GOLD_BAR, TEXT, MUTED = '#a8842c', '#e7d36c', '#3a2f1e', '#7a6a50'
        font_name = getattr(self, 'cn_font', 'Microsoft YaHei UI')
        dialog.configure(bg=BG)
        screen_w, screen_h = parent.winfo_screenwidth(), parent.winfo_screenheight()
        width, height = min(1000, screen_w - 30), min(670, screen_h - 50)
        x = max(0, min(screen_w - width, parent.winfo_rootx() + (parent.winfo_width() - width) // 2))
        y = max(0, min(screen_h - height, parent.winfo_rooty() + (parent.winfo_height() - height) // 2))
        dialog.geometry(f'{width}x{height}+{x}+{y}')
        dialog.resizable(False, False)

        # 从实际下注位读取赔率及限额，图解与本游戏可用落点保持一致。
        type_names = {
            'straight': '直注', 'split': '分注', 'street': '街注 / 零区三号注',
            'corner': '角注', 'six_line': '六线注',
            'dozen': '打注', 'column': '列注', 'color': '红 / 黑',
            'odd_even': '单 / 双', 'high_low': '大 / 小',
        }
        groups = [
            ('直注', {'straight'}, '点击号码格中心，包括0。'),
            ('分注', {'split'}, '点击两个号码的共用边。\n零区可用组合：0/1、0/2、0/3。'),
            ('街注与零区三号注', {'street'},
             '街注覆盖同一竖排的三个号码。\n零区三号注：0/1/2、0/2/3。'),
            ('角注', {'corner'}, '点击四个相邻号码的交点，一次覆盖四个号码。'),
            ('六线注', {'six_line'}, '点击两条街的共用端点，一次覆盖六个号码。'),
            ('打注', {'dozen'}, '第一打：1—12；第二打：13—24；第三打：25—36。'),
            ('列注', {'column'}, '点击右侧列注格，每格覆盖对应横排的十二个号码。'),
            ('大小、单双、红黑', {'high_low', 'odd_even', 'color'},
             '小：1—18；大：19—36。\n六个外围位置均不含0。'),
        ]

        payout_rows, limit_rows = [], []
        for kind, name in type_names.items():
            spots = [spot for spot in self.bet_spots if spot['type'] == kind]
            if not spots:
                continue
            spot = spots[0]
            payout_rows.append([name, str(len(spot['numbers'])),
                                f"{spot['payout']} : 1", f"实付下注 × {spot['payout'] + 1}"])
            limit_rows.append([name, f"${self._bet_limit_for_spot(spot):,}",
                               f"${self._bet_limit_for_spot(spot):,} × 当前倍数"])
        payout_rows.append(['未命中的下注', '—', '不获奖', '$0（本金不退回）'])
        zero_index = ROULETTE_SEQUENCE.index('0')
        neighbors = [ROULETTE_SEQUENCE[(zero_index + offset) % len(ROULETTE_SEQUENCE)]
                     for offset in range(-2, 3)]
        neighbor_text = '、'.join(neighbors)
        straight_return = 25 * (BET_ODDS['straight'] + 1)

        # 每张卡片依次为：标题、说明、规则、表格、图解类型 / 数据。
        manual_pages = [
            ('玩法', '选择下注位置，观看挡板落球，按外围轮盘的入槽号码结算。', [
                ('一局如何进行', '', [
                    ('① 选择筹码与倍数',
                     '下注阶段没有时间限制。\n'
                     '下注时轮盘高速转动，小球停在顶部。选择筹码和倍数后，左键点击下注位置；可重复加注或押多个位置。'),
                    ('② 按键或按钮落球',
                     '按一次 Enter 或点击“开始落球”，立即锁定下注与倍数并落球。\n'
                     '持续按住 Enter，可在回球后的 4 秒准备结束时自动开始下一局；松开按键或切换窗口即停止连续落球。\n'
                     '落球同时独立抽取电机计划：前 2 秒完成平滑随机转角，再沿预定曲线运行。\n'
                     '小球经过横向挡板。落球、结果展示及回球期间不能加注、撤注或调整倍数。'),
                    ('③ 结算并自动返回',
                     '两侧边框会挡住小球，使其继续下落到最底一行挡板下方的底部开口。\n'
                     '球与转动中的轮盘槽壁、槽底发生实际碰撞，可反弹；稳定进入 |-| 形槽位后按所在号码结算。\n'
                     '所有覆盖该号码的下注分别判定。沿用原版的每秒闪烁、共 6 秒结果展示，结束后同一颗球由轮盘送回顶部。\n'
                     '小球回到顶部后立即开放下注；准备 4 秒后可按 Enter 或按钮再次落球。'),
                ], [], None),
                ('自由落体轮盘与零号', '', [
                    ('模拟方式', '正面 2D 圆盘：每行只有最左、最右两块挡板向中央下斜 3°；中间挡板保持水平，单块的一行也保持水平。\n底部设导流障碍，外围号码环旋转。所有阶段都计算重力；球由挡板、槽壁、回球内闸或圆形接收器的收窄导槽支撑。\n本程序为独立本地模拟，并非商业机台的官方版本。'),
                    ('号码构成', '共 37 个号码：0 及 1—36。\n0不属于大小、单双、红黑、打注或列注。'),
                    ('号码与小仓亮灯', '号码格与对应小仓共用分界线，常态保持清晰可读；本局下注覆盖时一起亮灯，保留红、黑、绿分类。\n小球所在的小仓优先显示金色，球离开后恢复相应灯色。'),
                    ('数字朝向', '数字与对应小仓一起转动，字底沿小仓切线排列；经过顶部时自然回正，不再固定朝下。'),
                    ('卡球取消与退款', '落球时连续 15 秒没有明显位移，本局立即取消，全部实际下注退还。\n支撑球的那块挡板转动 360° 后复位，球继续落下并返回接收器。取消局的落入号码不结算，也不计入游戏 JSON 记录。'),
                    ('电机准备校验', '如果球在电机准备区间结束前提前接近移动槽壁，本局取消并全额退款。\n同一颗球继续按物理过程回到顶部；该校验独立于下注、号码和输赢。'),
                    ('每局转向', '球入仓时独立抽取一次：75% 反转上一局方向，25% 沿用。\n闪烁结束后按抽中的方向回球，并沿用到下一局；每局抽取与之前结果无关。'),
                    ('说明窗口', '可在下注阶段随时阅读说明。\n关闭说明后继续下注，或按 Enter 开始落球。'),
                ], [], None),
            ]),
            ('下注图解', '金色空心圆标记该类型的全部合法落点；图解不可下注。', [
                (name, hint, [], [], ('board', kinds)) for name, kinds, hint in groups
            ]),
            ('邻号下注', '邻号依照轮盘顺序排列，并非按数字大小排列。', [
                ('跑道盘与邻号', f'示例：以 0 为中心，左右各 2 个邻号。\n覆盖 {neighbor_text}。',
                 [], [], ('track', '0')),
                ('加注与撤注', '', [
                    ('邻号数量', '左右各选 0—5 个邻号，连同中心共覆盖 1、3、5、7、9、11 个号码。\n每个号码都是独立直注。'),
                    ('逐号限额与余额', '每个号码分别按剩余额度加注；已满额号码跳过。\n因此各号实际加注金额可能不同。余额不足以支付整组实际加注时，整组不下注。'),
                    ('右键清除', '跑道号码上右键只清除该号码的直注，不会清除整组邻号。'),
                ], [], None),
                ('邻号结算示例', '以下使用倍数 1，且所有号码均有足够下注额度。', [], [
                    ('每号下注 $25，左右各 2 个邻号',
                     ['开奖结果', '总下注', '总返还\n（含中奖本金）', '本局净盈亏'],
                     [['命中任一覆盖号码', '$125', f'${straight_return:,}', f'+${straight_return - 125:,}'],
                      ['未命中覆盖号码', '$125', '$0', '−$125']]),
                ], None),
            ]),
            ('赔率 & 限红', '赔付、计算口径及下注限额统一列于下表。', [
                ('全部下注赔付', '', [], [
                    ('标准赔付表', ['下注类型', '覆盖\n号码数', '净赢赔率\n（不含本金）', '命中总返还\n（含该注本金）'], payout_rows),
                    ('结算口径', ['项目', '计算 / 处理方式'], [
                        ['实付下注', '基础下注金额 × 当前倍数'],
                        ['单笔中奖返还', '基础下注金额 ×（净赢赔率 + 1）× 当前倍数'],
                        ['本局总返还', '所有中奖下注返还之和'],
                        ['本局净盈亏', '本局总返还 − 本局全部实付下注'],
                        ['界面“本局获胜金额”', '显示本局总返还，包含中奖下注本金。\n并非本局净利润。'],
                        ['零号开出', '0仅使覆盖该号码的下注中奖。\n外围下注无半退或留注处理。'],
                        ['下注期撤注', '退回被清除下注的基础金额 × 当前倍数'],
                    ]),
                ], None),
                ('下注限额', '每个下注位独立累计；实际扣款仍受可用余额限制。', [], [
                    ('单个下注位上限', ['下注类型', '基础金额上限', '实付金额上限'], limit_rows),
                ], None),
            ]),
            ('操作 & 记录', '下注阶段管理筹码，结算阶段查看结果。', [
                ('常用操作', '', [
                    ('加注与清除', '主盘左键加注；右键清除所选下注位；“清除下注”清除全部下注。\n接近上限时仅补至该下注位剩余额度。'),
                    ('主盘 / 跑道切换', '下注阶段且筹码转移动画未进行时可切换；两种视图共享下注。'),
                    ('调整倍数', '下注阶段可选 1、2、5、10、20、50、100 倍。\n调整后按现有基础下注补扣或退回差额；余额不足时保留原倍数。'),
                    ('重复上局下注', '按当前倍数检查余额，计入清除当前下注后可退回的金额。\n检查通过后恢复上局组合。'),
                    ('结果与历史', '结果展示阶段自动更新中奖号码、返还金额及记录。\n历史记录和统计仅反映已经发生的结果。'),
                    ('阅读与关闭', '点击左侧目录切换页面；滚轮或右侧滚动条浏览。\n按 Esc 或右上角按钮关闭说明。'),
                ], [], None),
            ]),
            ('结算示例', '示例均使用倍数 1；本局净盈亏须扣除全部下注。', [
                ('单注与多注', '', [], [
                    ('直注 1：下注 $25，开出 1', ['总下注', '总返还（含本金）', '净盈亏'],
                     [['$25', f'${straight_return:,}', f'+${straight_return - 25:,}']]),
                    ('直注 1 与黑色各下注 $25，开出红色 1', ['下注', '实付金额', '返还（含本金）'],
                     [['直注 1（命中）', '$25', f'${straight_return:,}'], ['黑色（未命中）', '$25', '$0'],
                      ['合计', '$50', f'${straight_return:,}']]),
                    ('多注净盈亏', ['总返还', '总下注', '净盈亏'],
                     [[f'${straight_return:,}', '$50', f'+${straight_return - 50:,}']]),
                    ('仅直注 1：下注 $25，开出 2', ['总下注', '总返还', '净盈亏'],
                     [['$25', '$0', '−$25']]),
                ], None),
            ]),
        ]
        region_cards = [
            ('四个区域', '区域按钮把一个单位金额拆分到多个主盘下注位。', [], [], ('track', None)),
            ('组合操作', '', [
                ('区域加注', '左键点击区域，以所选筹码为一个单位。\n已有主盘下注与重叠区域共用各下注位限额。'),
                ('比例与限额', '任何子注剩余额度不足时，按完整组合比例缩小本次单位金额。\n无可用完整单位或余额不足时不下注。'),
                ('区域撤注', '右键点击区域，只撤销该区域贡献的下注。\n其他区域或直接下注的剩余金额保留。'),
                ('开局动画', '开局保留当前视图，展示组合筹码拆分到主盘的动画。'),
            ], [], None),
        ]
        for region in RACETRACK_REGION_ORDER:
            info = FRENCH_BETS[region]
            legs = self._region_legs(region)
            units = sum(units for _, units in legs)
            covered = set().union(*(spot['numbers'] for spot, _ in legs))
            leg_rows = [[type_names[spot['type']], ' / '.join(sorted(spot['numbers'], key=int)),
                         str(unit_count), f'${25 * unit_count:,}'] for spot, unit_count in legs]
            outcomes = {}
            for number in sorted(covered, key=int):
                returned = sum(25 * unit_count * (spot['payout'] + 1)
                               for spot, unit_count in legs if number in spot['numbers'])
                outcomes.setdefault(returned, []).append(number)
            return_rows = [['、'.join(numbers), f'${25 * units:,}', f'${returned:,}',
                            f'{returned - 25 * units:+,}'] for returned, numbers in sorted(outcomes.items())]
            return_rows.append(['未覆盖号码', f'${25 * units:,}', '$0', f'−{25 * units:,}'])
            region_cards.append((
                info['zh'], f"{info['label']}\n{units} 单位 · {len(legs)} 个落点 · 覆盖 {len(covered)} 个号码。\n"
                '图中筹码为下注金额；每单位 $25，倍数 1。', [], [
                    ('组合拆分', ['下注类型', '覆盖号码', '单位数', '基础下注'], leg_rows),
                    ('组合赔付示例', ['开出号码', '总下注', '总返还\n（含中奖本金）', '净盈亏（$）'], return_rows),
                ], ('region', region)))
        region_cards.append(('组合结算口径', '', [], [
            ('同时命中多笔子注', ['情况', '计算 / 处理方式'], [
                ['区域返还', '先拆为主盘子注，再合计所有中奖子注的返还。'],
                ['孤儿序列开出 17', '同时命中 14 / 17 与 17 / 20 两笔分注。\n两笔中奖返还均计入总返还。'],
                ['重叠区域 / 主盘下注', '同一下注位金额合并计算；不额外重复派彩。'],
                ['实际倍数', '示例的下注、返还及净盈亏均乘以实际倍数。'],
            ]),
        ], None))
        manual_pages.insert(3, ('欧式组合', '四个区域的落点、单位拆分及赔付分别列示。', region_cards))
        def close_dialog():
            if getattr(self, '_instruction_window', None) is dialog:
                self._instruction_window = None
            dialog.destroy()

        header = tk.Frame(dialog, bg=HEADER)
        header.pack(fill=tk.X)
        tk.Button(header, text='关闭  ESC', command=close_dialog,
                  font=(font_name, 13, 'bold'), bg='#e8dcc0', fg=TEXT,
                  activebackground=GOLD_BAR, relief=tk.FLAT, bd=0,
                  padx=14, pady=10, cursor='hand2').pack(side=tk.RIGHT, padx=20)
        title_box = tk.Frame(header, bg=HEADER)
        title_box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=24, pady=10)
        tk.Label(title_box, text=title, font=(font_name, 20, 'bold'),
                 fg=GOLD, bg=HEADER, anchor='w').pack(fill=tk.X)
        tk.Label(title_box, text='玩法 · 下注 · 派奖 · 图解 · 结算示例',
                 font=(font_name, 12), fg=MUTED, bg=HEADER, anchor='w').pack(fill=tk.X, pady=(4, 0))
        tk.Frame(dialog, bg=GOLD_BAR, height=3).pack(fill=tk.X)
        body = tk.Frame(dialog, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)
        sidebar = tk.Frame(body, bg=SIDEBAR, width=180)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='说明目录', font=(font_name, 16, 'bold'),
                 fg=GOLD, bg=SIDEBAR, anchor='w').pack(fill=tk.X, padx=18, pady=(17, 10))
        host = tk.Frame(body, bg=BG)
        host.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(host, bg=BG, highlightthickness=0, yscrollincrement=28)
        ys = tk.Scrollbar(host, orient=tk.VERTICAL, command=canvas.yview)
        xs = tk.Scrollbar(host, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        canvas.grid(row=0, column=0, sticky='nsew')
        ys.grid(row=0, column=1, sticky='ns')
        xs.grid(row=1, column=0, sticky='ew')
        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)
        content = tk.Frame(canvas, bg=BG)
        content_window = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(content_window, width=max(760, event.width)))

        def label(parent_frame, value, size=13, bold=False, color=MUTED, bg=PANEL):
            widget = tk.Label(parent_frame, text=value, font=(font_name, size, 'bold' if bold else 'normal'),
                              fg=color, bg=bg, anchor='w', justify=tk.LEFT, wraplength=700)
            widget.pack(fill=tk.X)
            return widget

        def add_rule(parent_frame, heading, detail):
            row = tk.Frame(parent_frame, bg=PANEL)
            row.pack(fill=tk.X, padx=16, pady=7)
            tk.Frame(row, bg=GOLD_BAR, width=5).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 11))
            box = tk.Frame(row, bg=PANEL)
            box.pack(side=tk.LEFT, fill=tk.X, expand=True)
            label(box, heading, 14, True, TEXT)
            label(box, detail)

        def add_table(parent_frame, heading, headers, rows):
            block = tk.Frame(parent_frame, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
            block.pack(fill=tk.X, padx=16, pady=8)
            tk.Label(block, text=heading, font=(font_name, 14, 'bold'),
                     fg=TEXT, bg=GOLD_BAR, anchor='w', justify=tk.LEFT,
                     wraplength=670, padx=10, pady=8).pack(fill=tk.X)
            grid = tk.Frame(block, bg=BORDER)
            grid.pack(fill=tk.X)
            matrix = [headers] + rows
            count = len(headers)
            table_font = tkfont.Font(family=font_name, size=12)
            preferences = [max(55, min(260, max(table_font.measure(line)
                           for row in matrix for line in str(row[col]).split('\n'))))
                           for col in range(count)]
            available = 694
            remainder = available - 70 * count
            widths = [70 + remainder * value // sum(preferences) for value in preferences]
            widths[-1] += available - sum(widths)
            for col, column_width in enumerate(widths):
                grid.grid_columnconfigure(col, minsize=column_width, weight=1)
            for r, row in enumerate(matrix):
                for col, value in enumerate(row):
                    bg = GOLD_BAR if r == 0 else (PANEL if r % 2 else '#fbf6e9')
                    tk.Label(grid, text=value, font=(font_name, 12, 'bold' if r == 0 else 'normal'),
                             fg=TEXT if r == 0 else MUTED, bg=bg, anchor='w', justify=tk.LEFT,
                             wraplength=widths[col] - 16, padx=7, pady=7,
                             relief=tk.SOLID, borderwidth=1).grid(row=r, column=col, sticky='nsew')

        def draw_illustration(parent_frame, illustration):
            kind, data = illustration
            cv = tk.Canvas(parent_frame, width=704, height=355 if kind != 'track' else 310,
                           bg=PANEL, highlightthickness=0)
            cv.pack(padx=12, pady=(5, 10))
            INK, GREEN, BLUE = TEXT, '#24463B', '#B9E1EE'
            FONT = font_name

            def text(x, y, value, size=12, color=TEXT, bold=False, anchor='nw', wrap=None):
                return cv.create_text(x, y, text=value, fill=color, anchor=anchor,
                                      justify='center' if anchor == 'center' else 'left',
                                      font=(FONT, size, 'bold' if bold else 'normal'), width=wrap or 0)

            outside = dict(zip(('outside_' + str(i) for i in range(6)), ('小', '双', '红', '黑', '单', '大')))
            dozens = {'dozen_1': '第一打 1—12', 'dozen_2': '第二打 13—24', 'dozen_3': '第三打 25—36'}
            def table(left, top, marks=(), legs=()):
                """使用游戏实际投注坐标，绘制全部指定落点。"""
                scale = 1.3
                covered = (
                    set().union(*(s["numbers"] for s, _ in legs))
                    if legs else set()
                )
    
                for s in self.bet_spots:
                    kind = s["type"]
                    if kind not in {
                        "straight", "dozen", "column",
                        "color", "odd_even", "high_low",
                    }:
                        continue
    
                    x1, y1, x2, y2 = s["bounds"]
                    box = (
                        left + x1 * scale,
                        top + y1 * scale,
                        left + x2 * scale,
                        top + y2 * scale,
                    )
    
                    fill, ink = GREEN, "white"
    
                    if kind == "straight":
                        label = next(iter(s["numbers"]))
                        if label == "0":
                            fill = "#096B57"
                        elif int(label) in RED_NUMBERS:
                            fill = "#B43B44"
                        else:
                            fill = "#17211C"
    
                        if label in covered:
                            fill, ink = BLUE, "#102A38"
    
                    elif kind == "dozen":
                        label = dozens[s["id"]]
    
                    elif kind == "column":
                        label = "列注"
    
                    else:
                        label = outside[s["id"]]
                        if s["id"] == "outside_2":
                            fill = "#B43B44"
                        elif s["id"] == "outside_3":
                            fill = "#17211C"
    
                    cv.create_rectangle(
                        *box,
                        fill=fill,
                        outline="#92AA9F",
                        width=1,
                    )
                    text(
                        (box[0] + box[2]) / 2,
                        (box[1] + box[3]) / 2,
                        label,
                        10 if kind == "dozen" else 11,
                        ink,
                        True,
                        "center",
                    )
    
                # 空心圆保留原有文字位置。
                # 此类型的所有合法落点一次画出。
                for s in marks:
                    sx, sy = s["center"]
                    x = left + sx * scale
                    y = top + sy * scale
    
                    if s["type"] == "straight":
                        radius = 13
                    elif s["type"] in {
                        "dozen", "column", "color",
                        "odd_even", "high_low",
                    }:
                        radius = 17
                    else:
                        radius = 6
    
                    cv.create_oval(
                        x - radius, y - radius,
                        x + radius, y + radius,
                        fill="",
                        outline=GOLD_BAR,
                        width=2,
                    )
    
                # 跑道区域示例：每单位25。
                for s, units in legs:
                    sx, sy = s["center"]
                    x = left + sx * scale
                    y = top + sy * scale
    
                    cv.create_oval(
                        x - 12, y - 12,
                        x + 12, y + 12,
                        fill=GOLD,
                        outline=INK,
                        width=1,
                    )
                    text(
                        x, y, str(25 * units),
                        9, INK, True, "center",
                    )
            def track(top, neighbor_center=None, count=2):
                """保留游戏原有数字顺序、分区边界和跑道几何算法。"""
                ox, oy, scale = 12, top, 1.3
    
                def coords(points):
                    return [
                        value
                        for x, yy in points
                        for value in (
                            ox + x * scale,
                            oy + yy * scale,
                        )
                    ]
    
                for i, number in enumerate(RACETRACK_SEQUENCE):
                    fractions = [
                        (i + j / 6) / len(RACETRACK_SEQUENCE)
                        for j in range(7)
                    ]
                    points = [
                        self._racetrack_point(t, RACETRACK_OUTER_R)
                        for t in fractions
                    ]
                    points += [
                        self._racetrack_point(t, RACETRACK_INNER_R)
                        for t in reversed(fractions)
                    ]
    
                    if number == "0":
                        fill = "#096B57"
                    elif int(number) in RED_NUMBERS:
                        fill = "#B43B44"
                    else:
                        fill = "#17211C"
    
                    ink, edge = "white", "#92AA9F"
    
                    if neighbor_center is not None:
                        distance = self._racetrack_distance(
                            number, neighbor_center
                        )
                        if distance <= count:
                            fills = RACETRACK_NEIGHBOR_HOVER_FILLS
                            fill = fills[
                                min(distance, len(fills) - 1)
                            ]
                            ink, edge = "#102A38", BORDER
    
                    cv.create_polygon(
                        *coords(points),
                        fill=fill,
                        outline=edge,
                        width=2,
                    )
    
                    xx, yy = self._racetrack_point(
                        (i + 0.5) / len(RACETRACK_SEQUENCE),
                        73,
                    )
                    text(
                        ox + xx * scale,
                        oy + yy * scale,
                        number,
                        11, ink, True, "center",
                    )
    
                # 先画底色，再画文字。
                for region in RACETRACK_REGION_ORDER:
                    cv.create_polygon(
                        *coords(self._region_polygon(region)),
                        fill=RACETRACK_REGION_COLORS[region][0],
                        outline="#92AA9F",
                        width=2,
                    )
    
                for region in RACETRACK_REGION_ORDER:
                    cx, cy = self._region_center(region)
                    dx, dy = {
                        "tiers": (-6, 9),
                        "voisins": (-8, -8),
                    }.get(region, (0, 0))
    
                    xx = ox + (cx + dx) * scale
                    yy = oy + (cy + dy) * scale
    
                    text(
                        xx, yy - 15,
                        FRENCH_BETS[region]["title"],
                        10, "white", True, "center",
                    )
                    text(
                        xx, yy + 17,
                        FRENCH_BETS[region]["zh"],
                        10, "white", True, "center",
                    )
            if kind == 'track':
                track(4, neighbor_center=data)
            elif kind == 'board':
                table(12, 8, marks=[s for s in self.bet_spots if s['type'] in data])
            else:
                table(12, 8, legs=self._region_legs(data))

        def render_page(index):
            for child in content.winfo_children():
                child.destroy()
            for idx, button in enumerate(nav_buttons):
                button.configure(bg='#e6d9b9' if idx == index else SIDEBAR,
                                 fg=GOLD if idx == index else MUTED)
            page_title, subtitle, cards = manual_pages[index]
            top = tk.Frame(content, bg=BG)
            top.pack(fill=tk.X, padx=18, pady=(16, 7))
            label(top, page_title, 20, True, GOLD, BG)
            label(top, subtitle, bg=BG)
            for card_title, card_subtitle, rules, tables, illustration in cards:
                card = tk.Frame(content, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
                card.pack(fill=tk.X, padx=10, pady=7)
                head = tk.Frame(card, bg=PANEL)
                head.pack(fill=tk.X, padx=16, pady=(12, 6))
                label(head, card_title, 16, True, GOLD)
                if card_subtitle:
                    label(head, card_subtitle)
                if illustration:
                    draw_illustration(card, illustration)
                for heading, detail in rules:
                    add_rule(card, heading, detail)
                for heading, headers, rows in tables:
                    add_table(card, heading, headers, rows)
                tk.Frame(card, bg=PANEL, height=8).pack(fill=tk.X)
            content.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox('all'))
            canvas.yview_moveto(0)
            canvas.xview_moveto(0)

        nav_buttons = []
        for index, (page_title, _subtitle, _cards) in enumerate(manual_pages):
            button = tk.Button(sidebar, text=page_title, command=lambda i=index: render_page(i),
                               font=(font_name, 14), fg=MUTED, bg=SIDEBAR,
                               activebackground='#e8d49a', activeforeground=GOLD,
                               relief=tk.FLAT, bd=0, anchor='w', padx=18, pady=10, cursor='hand2')
            button.pack(fill=tk.X)
            nav_buttons.append(button)

        def on_mousewheel(event):
            number = getattr(event, 'num', None)
            delta = getattr(event, 'delta', 0)
            if number in (4, 5):
                steps = -1 if number == 4 else 1
            elif delta:
                steps = max(1, int(abs(delta) / 120)) * (-1 if delta > 0 else 1)
            else:
                return
            canvas.yview_scroll(steps, 'units')
            return 'break'

        dialog.bind('<MouseWheel>', on_mousewheel)
        dialog.bind('<Button-4>', on_mousewheel)
        dialog.bind('<Button-5>', on_mousewheel)
        dialog.bind('<Escape>', lambda _e: close_dialog())
        dialog.protocol('WM_DELETE_WINDOW', close_dialog)
        render_page(0)
        dialog.focus_set()

    def start_game(self):
        """Enter or the action button closes betting and drops one ball."""
        if self._closing:
            return
        if self.round_state == "betting":
            self._lock_bets_and_spin()

# Backward-compatible entry point for existing launchers.
RouletteGameGUI = PlinkoGameGUI

def main(initial_balance=1_000_000, username="Guest", *, parent=None,
         balance=None, user=None, on_back=None, on_balance_change=None):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        page = PlinkoGameGUI(
            parent, initial_balance=actual_balance, username=actual_user,
            on_back=on_back, on_balance_change=on_balance_change
        )
        page.place(x=0, y=0, relwidth=1, relheight=1)
        page.tkraise()
        return page

    root = tk.Tk()
    root._plinko_european_standalone = True
    page = PlinkoGameGUI(root, initial_balance=actual_balance, username=actual_user)
    page.pack(fill=tk.BOTH, expand=True)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")
