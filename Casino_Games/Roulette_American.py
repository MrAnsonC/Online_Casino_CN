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
import secrets
from datetime import date
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


def roulette_log_path() -> str:
    log_dir = os.path.join(project_root(), "A_Logs", "Json")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "Roulette_American.json")


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

ROULETTE_SEQUENCE = [
    "0", "28", "9", "26", "30", "11", "7", "20", "32", "17",
    "5", "22", "34", "15", "3", "24", "36", "13", "1", "00",
    "27", "10", "25", "29", "12", "8", "19", "31", "18", "6",
    "21", "33", "16", "4", "23", "35", "14", "2",
]
assert len(ROULETTE_SEQUENCE) == 38, f"Wheel sequence must have 38 items, got {len(ROULETTE_SEQUENCE)}"

def pocket_index(ball_angle: float, wheel_angle: float) -> int:
    """将球与转盘的相对角度映射到等宽的美式双零槽位。"""
    return int(((ball_angle - wheel_angle) % 360.0) // (360.0 / len(ROULETTE_SEQUENCE)))

# SI units: metres, radians and seconds. The renderer alone converts to pixels.
# Ideal level wheel: equal pockets/materials, no number-dependent parameters.
WHEEL_RUN_MIN_SECONDS = 125.0
WHEEL_RUN_MAX_SECONDS = 150.0
WHEEL_ACCEL_SECONDS = 4.0
WHEEL_TILT = 0.80
WHEEL_METRE_SCALE = 465.0
RESULT_FLASH_PERIOD_MS = 1500
RESULT_FLASH_COUNT = 3


def startup_date_pocket(local_date=None):
    """Initial display only: use the day from the computer's local calendar."""
    return ROULETTE_SEQUENCE.index(str((local_date or date.today()).day))


# Monoline digit outlines in local glyph coordinates (x right, y down).
WHEEL_DIGIT_STROKES = {
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

# Outline lettering uses the same rigid plane projection as the number ring.
# Coordinates are local to each glyph (x right, y down); no rotated Tk font
# bounding boxes or screen-space bevel offsets change as the rotor turns.
WHEEL_TITLE_STROKES = {
    "M": (((0,1),(0,0),(.5,.55),(1,0),(1,1)),),
    "I": (((0,0),(1,0)),((.5,0),(.5,1)),((0,1),(1,1))),
    "C": (((1,.15),(.8,0),(.2,0),(0,.2),(0,.8),(.2,1),(.8,1),(1,.85)),),
    "美": (((.27,.02),(.39,.16)),((.74,.02),(.61,.16)),
           ((.12,.2),(.88,.2)),((.2,.37),(.8,.37)),((.5,.2),(.5,.54)),
           ((.05,.54),(.95,.54)),((.1,.7),(.9,.7)),
           ((.5,.57),(.47,.76),(.32,.9),(.06,.99)),
           ((.5,.73),(.68,.9),(.95,.99))),
    "式": (((.06,.28),(.95,.28)),((.63,.02),(.66,.52),(.79,.84),(.94,.97),(.98,.78)),
           ((.77,.04),(.9,.16)),((.13,.49),(.53,.49)),((.33,.49),(.33,.86)),
           ((.06,.92),(.59,.81))),
    "E": (((1,0),(0,0),(0,1),(1,1)),((0,.5),(.8,.5))),
    "U": (((0,0),(0,.8),(.2,1),(.8,1),(1,.8),(1,0)),),
    "R": (((0,1),(0,0),(.8,0),(1,.2),(1,.35),(.8,.5),(0,.5)),((.5,.5),(1,1))),
    "O": (((.2,0),(.8,0),(1,.2),(1,.8),(.8,1),(.2,1),(0,.8),(0,.2),(.2,0)),),
    "P": (((0,1),(0,0),(.8,0),(1,.2),(1,.35),(.8,.5),(0,.5)),),
    "A": (((0,1),(.5,0),(1,1)),((.2,.6),(.8,.6))),
    "N": (((0,1),(0,0),(1,1),(1,0)),),
    "L": (((0,0),(0,1),(1,1)),),
    "T": (((0,0),(1,0)),((.5,0),(.5,1))),
    "欧": (((.05,.12),(.54,.12)),((.07,.12),(.07,.9),(.55,.9)),
           ((.18,.28),(.45,.7)),((.46,.26),(.18,.73)),
           ((.72,.05),(.57,.38)),((.65,.25),(.96,.25),(.86,.43)),
           ((.76,.37),(.73,.65),(.61,.84),(.5,.96)),
           ((.75,.59),(.85,.83),(.98,.95))),
    "洲": (((.06,.12),(.19,.23)),((.02,.4),(.16,.49)),
           ((.05,.94),(.2,.64)),((.3,.35),(.26,.56)),
           ((.39,.08),(.39,.65),(.35,.83),(.27,.97)),
           ((.48,.35),(.53,.55)),((.63,.12),(.63,.92)),
           ((.72,.35),(.77,.55)),((.88,.05),(.88,.97))),
    "轮": (((.02,.2),(.46,.2)),((.28,.05),(.09,.52),(.47,.52)),
           ((.01,.75),(.48,.68)),((.3,.36),(.3,.98)),
           ((.72,.05),(.59,.27),(.47,.4)),((.72,.05),(.85,.28),(.98,.4)),
           ((.61,.43),(.61,.88),(.67,.95),(.91,.95),(.96,.86),(.96,.76)),
           ((.91,.46),(.77,.61),(.61,.68))),
    "盘": (((.45,.03),(.36,.15)),((.2,.66),(.26,.5),(.26,.16),(.79,.16),(.79,.59),(.7,.65)),
           ((.1,.4),(.94,.4)),((.44,.24),(.55,.32)),((.44,.47),(.55,.56)),
           ((.18,.91),(.18,.72),(.83,.72),(.83,.91)),
           ((.39,.72),(.39,.91)),((.61,.72),(.61,.91)),((.06,.94),(.96,.94))),
}


def wheel_title_paths(cx, cy, text, angle, radius, char_w, char_h, gap):
    """Project lettering fixed to the central plate, including foreshortening."""
    a = math.radians(angle)
    sine, cosine = math.sin(a), math.cos(a)
    width = len(text)*char_w+(len(text)-1)*gap
    paths = []
    for index, char in enumerate(text):
        for stroke in WHEEL_TITLE_STROKES.get(char, ()):
            points = []
            for u,v in stroke:
                tangent = -width/2+index*(char_w+gap)+u*char_w
                radial = radius+(.5-v)*char_h
                points.extend((cx+radial*sine+tangent*cosine,
                               cy-WHEEL_TILT*(radial*cosine-tangent*sine)-2))
            paths.append(points)
    return paths


def wheel_number_paths(cx, cy, symbol, angle):
    """Continuous plane projection of digits, rigidly fixed to a numbered sector."""
    a = math.radians(angle)
    sine, cosine = math.sin(a), math.cos(a)
    char_w, char_h, gap = 6.4, 14.0, 1.6
    width = len(symbol)*char_w+(len(symbol)-1)*gap
    paths = []
    for digit_index,digit in enumerate(symbol):
        for stroke in WHEEL_DIGIT_STROKES[digit]:
            points = []
            for u,v in stroke:
                tangent = -width/2+digit_index*(char_w+gap)+u*char_w
                radius = 152.0-(v-.5)*char_h
                points.extend((cx+radius*sine+tangent*cosine,
                               cy-WHEEL_TILT*(radius*cosine-tangent*sine)
                               -RoulettePhysics.surface_height(math.hypot(radius,tangent)/WHEEL_METRE_SCALE)*WHEEL_METRE_SCALE))
            paths.append(points)
    return paths


class RoulettePhysics:
    """Reduced rigid-contact model with a driven rotor and dissipative ball.

    The rotor accelerates under constant torque, then coasts under constant
    friction torque for a randomly chosen total of 125–150 seconds per spin.
    A rolling sphere leaves the
    rim when centripetal support is insufficient, rolls down the conical bowl,
    collides with fixed deflectors and drops into a moving pocket. Pocket
    contacts use restitution and damping. This is an idealised simulation,
    not a calibrated replica of any particular manufacturer's wheel.

    Equal pocket geometry and contact constants are shared by every number.
    Launch conditions use an independent system RNG. The rotor can be driven
    again from its current angle and speed without a discontinuity; the
    dynamics never use colour, stake, balance or previous winning numbers.
    """
    TAU = 2 * math.pi
    STEP = TAU / len(ROULETTE_SEQUENCE)
    DT = 1.0 / 240.0
    G = 9.81
    RIM = 0.423
    POCKET_OUTER = 0.300
    BALL_R = 0.010
    POCKET_INNER = 109.0 / WHEEL_METRE_SCALE
    POCKET_CENTRE = POCKET_INNER + BALL_R + 0.0015
    POCKET_DEPTH = 0.018
    DEFLECTOR_R = 0.383
    DEFLECTOR_LENGTH = 0.018  # half length of alternating radial/tangential diamonds
    DEFLECTOR_WIDTH = 0.0045
    DEFLECTOR_HEIGHT = 0.004  # low, bevelled diamond; height above the bowl
    SLOPE = math.radians(15.0)
    DEFLECTORS = tuple(i * math.pi / 4 + math.pi / 8 for i in range(8))

    def __init__(self, rng=None, *, initial_angle=None, initial_speed=0.0):
        rng = rng if rng is not None else secrets.SystemRandom()
        self.run_seconds = rng.uniform(WHEEL_RUN_MIN_SECONDS, WHEEL_RUN_MAX_SECONDS)
        self.initial_phase = ((rng.randrange(len(ROULETTE_SEQUENCE)) + rng.random()) * self.STEP
                              if initial_angle is None else initial_angle % self.TAU)
        self.start_speed = max(0.0, initial_speed)
        # Slower drive, capped at 65 deg/s across repeated rounds. Preserve an
        # inherited speed without a jump, even if a caller supplies a faster one.
        self.peak_speed = max(self.start_speed, min(math.radians(65.0),
                              max(math.radians(rng.uniform(45.0,60.0)),
                                  self.start_speed+math.radians(4.0))))
        self.t = 0.0
        self.remainder = 0.0
        self.wheel_angle = self.initial_phase
        self.wheel_speed = self.start_speed
        self.theta = rng.random() * self.TAU
        self.omega = -rng.uniform(10.5, 12.5)
        self.r = self.RIM
        self.vr = 0.0
        self.z = 0.0
        self.vz = 0.0
        self.mode = "rim"
        self.pocket = None
        self.result_index = None
        self.settled_at = None
        self.relative_angle = 0.0
        self.relative_speed = 0.0
        self.deflector_hits = 0
        self.divider_hits = 0
        self.vertical_bounces = 0
        self.last_deflector_at = None
        self.scatter_entered_at = None
        self._display_previous = None

    def _display_state(self):
        return (self.theta,self.omega,self.r,self.surface_height(self.r)+self.z)

    def render_state(self):
        """Interpolate fixed physics steps for smooth, irregular UI frames."""
        current = self._display_state()
        if self._display_previous is None:
            return (self.wheel_angle,self.wheel_speed,self.theta,self.omega,self.r,self.z)
        previous = self._display_previous
        alpha = min(1.0,max(0.0,self.remainder/self.DT))
        delta = (current[0]-previous[0]+math.pi)%self.TAU-math.pi
        theta = (previous[0]+alpha*delta)%self.TAU
        omega,radius,height = (previous[i]+alpha*(current[i]-previous[i]) for i in (1,2,3))
        wheel,speed = self.rotor_at(max(0.0,self.t-self.DT+self.remainder))
        return wheel,speed,theta,omega,radius,max(0.0,height-self.surface_height(radius))

    def rotor_at(self, elapsed):
        t = min(max(0.0, elapsed), self.run_seconds)
        a = WHEEL_ACCEL_SECONDS
        if t < a:
            acceleration = (self.peak_speed-self.start_speed)/a
            speed = self.start_speed + acceleration*t
            travel = self.start_speed*t + acceleration*t*t/2
        else:
            coast = self.run_seconds - a
            u = t - a
            speed = self.peak_speed * max(0.0, 1.0 - u / coast)
            travel = ((self.start_speed+self.peak_speed)*a/2
                      + self.peak_speed*(u-u*u/(2*coast)))
        return (self.initial_phase + travel) % self.TAU, speed

    def advance(self, seconds):
        """Fixed-step contacts; accumulated time is never discarded on slow frames."""
        self.remainder += max(0.0, seconds)
        while self.remainder + 1e-12 >= self.DT:
            # Once captured, only analytic rotor motion remains.
            if self.result_index is not None or self.mode == "display":
                self._display_previous = None
                self.t += self.remainder
                self.remainder = 0.0
                self.wheel_angle, self.wheel_speed = self.rotor_at(self.t)
                self.theta = (self.wheel_angle + (self.pocket + .5)*self.STEP
                              + self.relative_angle) % self.TAU
                self.omega = self.wheel_speed
                break
            self.remainder = max(0.0, self.remainder - self.DT)
            self._display_previous = self._display_state()
            self.t += self.DT
            self.wheel_angle, self.wheel_speed = self.rotor_at(self.t)
            if self.mode == "pocket":
                self._step_pocket(self.DT)
            elif self.mode == "scatter":
                self._step_scatter(self.DT)
            else:
                self._step_bowl(self.DT)

    @classmethod
    def surface_height(cls, radius):
        """One continuous support surface for both motion and drawing (metres).

        The pocket floor slopes to its inner end. A Hermite join matches the
        bowl slope at the entrance, so crossing it never changes world height.
        """
        if radius >= cls.POCKET_OUTER:
            return (radius-cls.POCKET_OUTER)*math.tan(cls.SLOPE)
        span = cls.POCKET_OUTER-cls.POCKET_CENTRE
        u = max(0.0,min(1.0,(radius-cls.POCKET_CENTRE)/span))
        return (-cls.POCKET_DEPTH + cls.POCKET_DEPTH*(3*u*u-2*u*u*u)
                + span*math.tan(cls.SLOPE)*(u*u*u-u*u))

    @classmethod
    def surface_slope(cls, radius):
        if radius >= cls.POCKET_OUTER:
            return math.tan(cls.SLOPE)
        span = cls.POCKET_OUTER-cls.POCKET_CENTRE
        u = max(0.0,min(1.0,(radius-cls.POCKET_CENTRE)/span))
        return (cls.POCKET_DEPTH*(6*u-6*u*u)/span
                + math.tan(cls.SLOPE)*(3*u*u-2*u))

    def _horizontal_velocity(self):
        sine,cosine = math.sin(self.theta),math.cos(self.theta)
        return (self.vr*sine+self.r*self.omega*cosine,
                -self.vr*cosine+self.r*self.omega*sine)

    def _set_horizontal(self, x, y, vx, vy):
        self.r = math.hypot(x,y)
        self.theta = math.atan2(x,-y) % self.TAU
        self.vr = vx*math.sin(self.theta)-vy*math.cos(self.theta)
        self.omega = (vx*math.cos(self.theta)+vy*math.sin(self.theta))/self.r

    def _step_bowl(self, dt):
        """Continuous rolling/flight integration across bowl and pocket apron."""
        support = self.surface_height(self.r)
        world_height = support+self.z
        slope = self.surface_slope(self.r)
        airborne = self.z > 1e-7 or self.vz-slope*self.vr > .015
        if airborne:
            vx,vy = self._horizontal_velocity()
            x = self.r*math.sin(self.theta)+vx*dt
            y = -self.r*math.cos(self.theta)+vy*dt
            self._set_horizontal(x,y,vx,vy)
            world_height += self.vz*dt-.5*self.G*dt*dt
            self.vz -= self.G*dt
        else:
            self._step_rolling_bowl(dt)
            world_height = self.surface_height(self.r)
            self.vz = self.surface_slope(self.r)*self.vr
        # Real inner/outer rails; no invisible outer scatter boundary.
        for boundary,sign in ((self.POCKET_INNER+self.BALL_R,1),(self.RIM,-1)):
            if (self.r-boundary)*sign < 0:
                self.r = boundary
                if self.vr*sign < 0:
                    self.vr = -self.vr*.24
        floor = self.surface_height(self.r)
        self.z = max(0.0,world_height-floor)
        if world_height <= floor and airborne:
            # Resolve landing against the sloped floor normal. Tangential
            # velocity is preserved instead of abruptly resetting the ball.
            slope = self.surface_slope(self.r)
            norm = math.sqrt(1+slope*slope)
            vn = (self.vz-slope*self.vr)/norm
            if vn < 0:
                restitution = .24 if -vn > .16 else 0.0
                impulse = -(1+restitution)*vn
                self.vr -= impulse*slope/norm
                self.vz += impulse/norm
                if restitution:
                    self.vertical_bounces += 1
        self._collide_deflectors()
        self._collide_separators()
        if self.mode != "rim":
            self.mode = "scatter" if self.r <= self.POCKET_OUTER else "bowl"
        if self.mode == "scatter":
            if self.scatter_entered_at is None:
                self.scatter_entered_at = self.t
            self._try_capture()

    def _step_rolling_bowl(self, dt):
        in_pockets = self.r < self.POCKET_OUTER
        target_speed = self.wheel_speed if in_pockets else 0.0
        relative = self.omega-target_speed
        drag = 1.8 if in_pockets else (.19 if self.mode == "rim" else .12)
        resistance = 0.0 if in_pockets else (.22 if self.mode == "rim" else .14)
        relative *= math.exp(-drag*dt)
        if resistance:
            relative = math.copysign(max(0.0,abs(relative)-resistance*dt),relative)
        self.omega = target_speed+relative
        slope = self.surface_slope(self.r)
        if self.mode == "rim" and self.r*self.omega**2 < self.G*slope:
            self.mode = "bowl"
        if self.mode != "rim":
            ar = (self.r*self.omega**2-self.G*slope)/(1+slope*slope)/1.4
            self.vr = (self.vr+ar*dt)*math.exp(-(3.5 if in_pockets else 1.6)*dt)
            old_r = self.r
            self.r += self.vr*dt
            # Radial motion transports angular momentum continuously.
            self.omega *= (old_r/self.r)**2
        self.theta = (self.theta+self.omega*dt) % self.TAU

    @classmethod
    def deflector_vertices(cls, index):
        """Shared physical/render geometry: one radial, one tangential."""
        angle = cls.DEFLECTORS[index]
        radial = (math.sin(angle),-math.cos(angle))
        tangent = (math.cos(angle),math.sin(angle))
        u,v = (radial,tangent) if index % 2 == 0 else (tangent,radial)
        cx,cy = cls.DEFLECTOR_R*radial[0],cls.DEFLECTOR_R*radial[1]
        return tuple((cx+u[0]*a+v[0]*b,cy+u[1]*a+v[1]*b)
                     for a,b in ((cls.DEFLECTOR_LENGTH,0),(0,cls.DEFLECTOR_WIDTH),
                                 (-cls.DEFLECTOR_LENGTH,0),(0,-cls.DEFLECTOR_WIDTH)))

    @staticmethod
    def _closest_triangle(point, a, b, c):
        """Closest point on a finite 3-D face, including its edges and tip."""
        def sub(u,v):
            return tuple(x-y for x,y in zip(u,v))
        def dot(u,v):
            return sum(x*y for x,y in zip(u,v))
        ab, ac, ap = sub(b,a), sub(c,a), sub(point,a)
        aa, bb, cc = dot(ab,ab), dot(ab,ac), dot(ac,ac)
        d, e = dot(ap,ab), dot(ap,ac)
        denominator = aa*cc-bb*bb
        u, v = (cc*d-bb*e)/denominator, (aa*e-bb*d)/denominator
        if u >= 0 and v >= 0 and u+v <= 1:
            return tuple(a[i]+u*ab[i]+v*ac[i] for i in range(3))
        candidates = []
        for start,end in ((a,b),(b,c),(c,a)):
            edge = sub(end,start)
            t = max(0.0,min(1.0,dot(sub(point,start),edge)/dot(edge,edge)))
            candidates.append(tuple(start[i]+t*edge[i] for i in range(3)))
        return min(candidates,key=lambda q: dot(sub(point,q),sub(point,q)))

    def _collide_deflectors(self):
        # z is the sphere's underside above the bowl, not its centre height.
        # Once the underside clears the tip there is no invisible tall wall.
        if self.z > self.DEFLECTOR_HEIGHT:
            return
        if abs(self.r-self.DEFLECTOR_R) > self.DEFLECTOR_LENGTH+self.BALL_R:
            return
        x,y = self.r*math.sin(self.theta),-self.r*math.cos(self.theta)
        vx = self.vr*math.sin(self.theta)+self.r*self.omega*math.cos(self.theta)
        vy = -self.vr*math.cos(self.theta)+self.r*self.omega*math.sin(self.theta)
        for index in range(len(self.DEFLECTORS)):
            polygon = self.deflector_vertices(index)
            apex = (sum(p[0] for p in polygon)/4,
                    sum(p[1] for p in polygon)/4,
                    self.surface_height(self.DEFLECTOR_R)+self.DEFLECTOR_HEIGHT)
            centre = (x,y,self.surface_height(math.hypot(x,y))+self.z+self.BALL_R)
            closest = None
            for a,b in zip(polygon,polygon[1:]+polygon[:1]):
                q = self._closest_triangle(centre,
                    (*a,self.surface_height(math.hypot(*a))),
                    (*b,self.surface_height(math.hypot(*b))),apex)
                distance = math.sqrt(sum((p-r)**2 for p,r in zip(centre,q)))
                if closest is None or distance < closest[0]:
                    closest = (distance,q)
            distance,q = closest
            if 1e-12 < distance < self.BALL_R:
                nx,ny,nz = ((p-r)/distance for p,r in zip(centre,q))
                correction = self.BALL_R-distance+1e-8
                x, y = x+nx*correction, y+ny*correction
                self.z = max(0.0,centre[2]+nz*correction-self.BALL_R
                             -self.surface_height(math.hypot(x,y)))
                vn = vx*nx+vy*ny+self.vz*nz
                if vn < 0:
                    # One restitution impulse along the sloped 3-D normal:
                    # horizontal motion can become lift without adding energy.
                    vx -= 1.60*vn*nx
                    vy -= 1.60*vn*ny
                    self.vz -= 1.60*vn*nz
                    self.deflector_hits += 1
                    self.last_deflector_at = self.t
        self.r = math.hypot(x,y)
        self.theta = math.atan2(x,-y) % self.TAU
        self.vr = vx*math.sin(self.theta)-vy*math.cos(self.theta)
        self.omega = (vx*math.cos(self.theta)+vy*math.sin(self.theta))/self.r

    def _collide_separators(self):
        """Sphere contact with finite rotating rails, including their top edges.

        A ball above a rail can cross it; a low ball meets its actual wall.
        Closest-point contacts replace the old sector-centre angle clamps.
        """
        if self.r > self.POCKET_OUTER+self.BALL_R:
            return
        x,y = self.r*math.sin(self.theta),-self.r*math.cos(self.theta)
        height = self.surface_height(self.r)+self.z+self.BALL_R
        if height > self.BALL_R:
            return
        vx,vy = self._horizontal_velocity()
        sector = int(((self.theta-self.wheel_angle)%self.TAU)/self.STEP)
        for boundary in (sector,sector+1):
            angle = self.wheel_angle+boundary*self.STEP
            sine,cosine = math.sin(angle),math.cos(angle)
            radius = max(self.POCKET_INNER,min(self.POCKET_OUTER,x*sine-y*cosine))
            qx,qy = radius*sine,-radius*cosine
            qz = max(self.surface_height(radius),min(0.0,height))
            dx,dy,dz = x-qx,y-qy,height-qz
            distance = math.sqrt(dx*dx+dy*dy+dz*dz)
            if 1e-10 < distance < self.BALL_R:
                nx,ny,nz = dx/distance,dy/distance,dz/distance
                correction = self.BALL_R-distance+1e-8
                x,y,height = x+nx*correction,y+ny*correction,height+nz*correction
                rail_vx,rail_vy = -self.wheel_speed*qy,self.wheel_speed*qx
                vn = (vx-rail_vx)*nx+(vy-rail_vy)*ny+self.vz*nz
                if vn < 0:
                    impulse = -1.28*vn
                    vx,vy = vx+impulse*nx,vy+impulse*ny
                    self.vz += impulse*nz
                    self.divider_hits += 1
        self._set_horizontal(x,y,vx,vy)
        self.z = max(0.0,height-self.BALL_R-self.surface_height(self.r))

    def _step_scatter(self, dt):
        self._step_bowl(dt)

    def _try_capture(self):
        local = ((self.theta-self.wheel_angle)%self.STEP)-self.STEP/2
        limit = self.STEP/2-self.BALL_R/self.r
        if (self.r < self.POCKET_CENTRE+.012 and self.z < .0001
                and abs(self.vz)<.05 and abs(self.vr)<.06
                and abs(self.omega-self.wheel_speed)*self.r<.055
                and abs(local)<limit):
            self.mode = "pocket"
            self.pocket = int(((self.theta-self.wheel_angle)%self.TAU)/self.STEP)
            self.relative_angle = local
            self.relative_speed = self.omega-self.wheel_speed

    def _step_pocket(self, dt):
        """Damped seating at the inner, lowest end of the captured groove."""
        # Near-critical damping eases into the bottom, preserving incoming
        # velocity. Tight settlement tolerances avoid the former visible snap.
        self.vr += (-55*(self.r-self.POCKET_CENTRE)-15*self.vr)*dt
        self.r += self.vr*dt
        self.r = max(self.POCKET_INNER+self.BALL_R,min(self.POCKET_OUTER,self.r))
        self.relative_speed += (-42*self.relative_angle-13*self.relative_speed)*dt
        self.relative_angle += self.relative_speed*dt
        limit = self.STEP/2-self.BALL_R/self.r
        if abs(self.relative_angle)>limit:
            self.relative_angle = math.copysign(limit,self.relative_angle)
            if self.relative_speed*self.relative_angle > 0:
                self.relative_speed *= -.16
                self.divider_hits += 1
        self.z = 0.0
        self.vz = self.surface_slope(self.r)*self.vr
        self.theta = (self.wheel_angle+(self.pocket+.5)*self.STEP
                      +self.relative_angle) % self.TAU
        self.omega = self.wheel_speed+self.relative_speed
        if (abs(self.relative_speed)<.003 and abs(self.relative_angle)<.0003
                and abs(self.vr)<.001 and abs(self.r-self.POCKET_CENTRE)<.00015):
            self.result_index = self.pocket
            self.mode = "settled"
            self.settled_at = self.t
            self.r = self.POCKET_CENTRE
            self.relative_angle = self.relative_speed = 0.0
            self.theta = (self.wheel_angle+(self.pocket+.5)*self.STEP) % self.TAU
            self.omega = self.wheel_speed
            self.vr = self.vz = self.z = 0.0

    @property
    def stopped(self):
        return self.t >= self.run_seconds - 1e-9


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
    "0": "TEAL",
    "00": "TEAL",
}

OUTCOME_TEXT_COLORS = {
    "0": "#ffffff",
    "00": "#ffffff",
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

    canvas.create_rectangle(
        int(zero_x1), int(y0),
        int(zero_x2), int(y0 + zero_h),
        fill=TEAL,
        outline=CYAN,
        width=1
    )
    canvas.create_text(
        int(zero_x1 + zero_w / 2),
        int(y0 + zero_h / 2),
        text="00",
        fill=TEXT,
        font=("Segoe UI Emoji", 11, "bold"),
        angle=90
    )

    canvas.create_rectangle(
        int(zero_x1), int(y0 + zero_h),
        int(zero_x2), int(y0 + 2 * zero_h),
        fill=TEAL,
        outline=CYAN,
        width=1
    )
    canvas.create_text(
        int(zero_x1 + zero_w / 2),
        int(y0 + zero_h + zero_h / 2),
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
    if result in {"0", "00"}:
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

    def five_number_numbers(self):
        return ["0", "00", "1", "2", "3"]


class RouletteGameGUI(tk.Frame):
    BETTING_SECONDS = 30  #时间
    TIMER_TICK_MS = 250

    def __init__(self, parent, initial_balance=1_000_000, username="Guest",
                 on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG, width=1150, height=757)
        self.pack_propagate(False)
        self.parent = parent
        self.root = self.winfo_toplevel()
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self._embedded = not bool(getattr(self.root, "_roulette_american_standalone", False))
        self._previous_title = self.root.title()
        self._previous_geometry = self.root.geometry()
        self._previous_close_protocol = self.root.protocol("WM_DELETE_WINDOW")
        self.root.title("美式轮盘")
        self.root.geometry("1150x757+50+10")
        self.root.resizable(False, False)
        self.root.configure(bg=ROOT_BG)

        self.username = username
        self.balance = float(load_balance(username, float(initial_balance)))
        self.history = RouletteHistory(roulette_log_path())

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
        self.betting_deadline = None
        self._countdown_job = None
        self._spin_job = None
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
        self.timer_paused = False
        self.paused_remaining = 0

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
        self._start_startup_rotation()

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
        """Both layouts share straight-up bets; other bet types require the table."""
        if self.round_state != "betting":
            return False
        for spot_id, amount in self.current_bets.items():
            if amount <= 0:
                continue
            spot = self._find_spot_by_id(spot_id)
            if not spot or spot.get("type") != "straight":
                return False
        return True

    def _switch_betting_view(self, mode):
        if mode not in ("table", "racetrack"):
            return
        if not self._can_switch_betting_view():
            return
        self.betting_view = mode
        self.racetrack_hover = None
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
        left, right, cy, mid_radius = 106.0, 402.0, 108.0, 72.0
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
        hovered = set(self._racetrack_numbers(self.racetrack_hover)) if (
            self.racetrack_hover is not None and self.round_state == "betting") else set()
        highlights = []
        for index, number in enumerate(ROULETTE_SEQUENCE):
            fractions = [(index + step / 6) / len(ROULETTE_SEQUENCE) for step in range(7)]
            points = [self._racetrack_point(t, 94) for t in fractions]
            points += [self._racetrack_point(t, 50) for t in reversed(fractions)]
            tags = ("track", "track_number:" + number)
            winning = self.round_state == "result" and self.center_display_result == number
            flashing = winning and self._result_flash_state
            neighbor_hover = number in hovered
            primary = number in hovered and number == self.racetrack_hover
            distance = self._racetrack_distance(number, self.racetrack_hover) if number in hovered else 0
            highlight_color = RACETRACK_NEIGHBOR_HOVER_EDGE if neighbor_hover else RACETRACK_NEIGHBOR_COLORS[distance]
            canvas.create_polygon(
                *[coord for point in points for coord in point],
                fill="#ffffff" if flashing else (RACETRACK_NEIGHBOR_HOVER_FILLS[min(distance, 5)] if neighbor_hover else OUTCOME_COLORS[number]),
                outline=RACETRACK_NEIGHBOR_HOVER_EDGE if neighbor_hover else "#3A8064", width=1, tags=tags)
            if number in hovered or winning:
                highlights.append((primary or winning, points, highlight_color, tags))
            center = (index + 0.5) / len(ROULETTE_SEQUENCE)
            x, y = self._racetrack_point(center, 83)
            # Neighbour hover changes only the selected pockets; result flashing stays unchanged.
            text_color = "black" if flashing else (RACETRACK_NEIGHBOR_HOVER_TEXT if neighbor_hover else "white")
            canvas.create_text(x, y, text=number, fill=text_color,
                               font=("Arial", 10, "bold"), tags=tags)
            spot_id = "straight_" + number
            amount = self.current_bets.get(spot_id, 0)
            if amount > 0:
                fill = self._chip_fill_color_for_amount(amount)
                text_color = self._spot_text_color(fill)
                info = self.result_chip_display.get(spot_id)
                if self.round_state == "result" and info and self._result_flash_state:
                    amount, fill, text_color = info["win_amount"], info["win_fill"], info["win_text_color"]
                x, y = self._racetrack_point(center, 61)
                canvas.create_oval(x - 10, y - 9, x + 10, y + 9,
                                   fill=fill, outline="#D8B46A", width=1, tags=tags)
                canvas.create_text(x, y, text=self._format_win_amount(amount), fill=text_color,
                                   font=("Arial", 7, "bold"), tags=tags)
        # Paint outlines after the pockets, with the central selection on top.
        for primary, points, color, tags in sorted(highlights, key=lambda entry: entry[0]):
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
        canvas.create_text(BOARD_W / 2, 108, text="American Roulette",
                           fill="#F5D68A", font=("Georgia", 24, "bold italic"), tags="track")

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
        for item in reversed(self.racetrack_canvas.find_overlapping(x, y, x, y)):
            for tag in self.racetrack_canvas.gettags(item):
                if tag.startswith("track_number:"):
                    return tag.split(":", 1)[1]
        return None

    def _on_racetrack_motion(self, event):
        number = self._racetrack_number_at(event.x, event.y)
        if number != self.racetrack_hover:
            self.racetrack_hover = number
            self._draw_racetrack()

    def _on_racetrack_leave(self, event):
        self.racetrack_hover = None
        self._draw_racetrack()

    def _on_racetrack_click(self, event):
        number = self._racetrack_number_at(event.x, event.y)
        if number is not None:
            self._place_racetrack_bet(number)

    def _on_racetrack_right_click(self, event):
        if self.betting_view != "racetrack":
            return
        number = self._racetrack_number_at(event.x, event.y)
        if number is not None:
            self.clear_single_bet("straight_" + number)

    def _place_racetrack_bet(self, number):
        if self.round_state != "betting" or self.betting_view != "racetrack":
            return
        numbers = self._racetrack_numbers(number)
        amount = self._racetrack_amount(numbers)
        if amount <= 0:
            messagebox.showwarning("下注上限", "组合中有号码已达下注上限，请调整邻号或清除该号码下注。")
            return
        total = amount * len(numbers) * self.bet_multiplier
        if self.balance < total:
            messagebox.showwarning("余额不足", f"整组下注需要 ${total:,.0f}，余额不足。")
            return
        # Commit the whole group only after all limits and funds are checked.
        self.balance -= total
        for selected in numbers:
            spot_id = "straight_" + selected
            self.current_bets[spot_id] = self.current_bets.get(spot_id, 0) + amount
            self.current_bet_colors[spot_id] = self._chip_fill_color_for_amount(self.current_bets[spot_id])
        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

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
        if self.last_betting_view != self.betting_view and not self._can_switch_betting_view():
            self.repeat_last_btn.config(state=tk.DISABLED)
            return
        total_last = sum(self.last_bets.values()) * self.bet_multiplier
        if total_last > self.balance + sum(self.current_bets.values()) * self.bet_multiplier:
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

        if self.last_betting_view != self.betting_view and not self._can_switch_betting_view():
            messagebox.showwarning("提示", "请先清除非 Straight Up 下注，再重复另一种布局的上局下注。")
            return

        total_last = sum(self.last_bets.values()) * self.bet_multiplier
        if total_last > self.balance + sum(self.current_bets.values()) * self.bet_multiplier:
            messagebox.showwarning("提示", f"余额不足，重复上局下注需要 ${total_last:,.0f}")
            return

        # Restore the previous layout when the current bets allow switching.
        if self.last_betting_view != self.betting_view:
            self._switch_betting_view(self.last_betting_view)

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
            if self.balance < actual_amount * self.bet_multiplier:
                break

            self.balance -= actual_amount * self.bet_multiplier
            self.current_bets[spot_id] = existing + actual_amount
            self.current_bet_colors[spot_id] = self._chip_fill_color_for_amount(self.current_bets[spot_id])

        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        total_bet = sum(self.current_bets.values()) * self.bet_multiplier
        self._show_round_amount("本局下注金额", sum(self.current_bets.values()))

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
            self._draw_wheel_status()
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

    # ---------- 新增饼图相关方法（移植自欧洲版，适配双零） ----------
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
            "zero": TEAL,           # 0/00
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
        """从 Record2 中获取最近 limit 条结果，统计各区间（1-12,13-24,25-36,0+00）出现的次数"""
        all_results = self.history.recent_results2(limit=2000)
        recent = [entry.get("result", "") for entry in all_results if entry.get("result", "")][:limit]
        counts = {"1-12": 0, "13-24": 0, "25-36": 0, "0/00": 0}
        for res in recent:
            if res in ("0", "00"):
                counts["0/00"] += 1
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
        """统计最近 limit 条结果中属于 Row1/Row2/Row3/0+00 的次数"""
        row1_set = {1,4,7,10,13,16,19,22,25,28,31,34}
        row2_set = {2,5,8,11,14,17,20,23,26,29,32,35}
        row3_set = {3,6,9,12,15,18,21,24,27,30,33,36}

        all_results = self.history.recent_results2(limit=2000)
        recent = [entry.get("result", "") for entry in all_results if entry.get("result", "")][:limit]
        counts = {"row1": 0, "row2": 0, "row3": 0, "0/00": 0}
        for res in recent:
            if res in ("0", "00"):
                counts["0/00"] += 1
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
        """根据当前模式，动态绘制饼图（仅绘制计数>0的扇形），下方以表格显示分类与次数，0/00始终在最上方且永远显示（即使0次）"""
        if not hasattr(self, "pie_canvas"):
            return

        limit = 50
        if self.pie_mode == "sector":
            counts, total = self._get_sector_data_from_recent(limit)
            all_keys = ["1-12", "13-24", "25-36", "0/00"]
            display_names = {"1-12": "1-12", "13-24": "13-24", "25-36": "25-36", "0/00": "0/00"}
            color_keys = {"1-12": "sector1", "13-24": "sector2", "25-36": "sector3", "0/00": "zero"}
        else:
            counts, total = self._get_row_data_from_recent(limit)
            all_keys = ["row1", "row2", "row3", "0/00"]
            display_names = {"row1": "直行1(1/4/7...)", "row2": "直行2(2/5/8...)", "row3": "直行3(3/6/9...)", "0/00": "0/00"}
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
                    label = "0/00"
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
        1) 小/0&00/大
        2) 单/0&00/双
        3) 红/绿/黑
        """
        if not hasattr(self, 'history'):
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
        all_numbers = [str(i) for i in range(1, 37)] + ["0", "00"]
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
            font = ("Segoe UI Emoji", 11, "bold") if result == "00" else ("Arial", 11, "bold")
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
    # Wheel drawing (unchanged)
    # =====================================================


    # =====================================================
    # Bet spots / hit testing / chips (chip radius enlarged by 20%)
    # =====================================================

    def _wheel_point(self, cx, cy, radius, angle, z=0):
        a = math.radians(angle)
        return cx+radius*math.sin(a), cy-WHEEL_TILT*radius*math.cos(a)-z

    def _wheel_band(self, cx, cy, inner, outer, start, end, z=0, **style):
        points = []
        divisions = max(2, int(abs(end-start)/3))
        for j in range(divisions+1):
            points.extend(self._wheel_point(cx, cy, outer,
                          start+(end-start)*j/divisions, z(outer) if callable(z) else z))
        for j in range(divisions, -1, -1):
            points.extend(self._wheel_point(cx, cy, inner,
                          start+(end-start)*j/divisions, z(inner) if callable(z) else z))
        return self.wheel_canvas.create_polygon(*points, **style)

    def _wheel_oval(self, cx, cy, r, z=0, **style):
        return self.wheel_canvas.create_oval(cx-r, cy-WHEEL_TILT*r-z,
                         cx+r, cy+WHEEL_TILT*r-z, **style)

    @staticmethod
    def _surface_pixels(radius):
        return RoulettePhysics.surface_height(radius/WHEEL_METRE_SCALE)*WHEEL_METRE_SCALE

    def _draw_wheel(self):
        c = self.wheel_canvas
        width, height = c.winfo_width(), c.winfo_height()
        if width <= 10 or height <= 10:
            self.after(50, self._draw_wheel)
            return
        cx, cy = width/2, height/2-1
        self.wheel_timer_id = None
        if getattr(self, "_wheel_static_size", None) != (width,height):
            c.delete("all")
            self._wheel_static_size = (width,height)
            static = {"tags": ("wheel_static",)}
            c.create_rectangle(0,0,width,height,fill="#073B25",outline="",**static)
            # Graphite shell and satin-steel rims, without grain or wood sectors.
            for z, colour in ((-19,"#080F16"),(-13,"#192630"),(-7,"#354651")):
                self._wheel_oval(cx,cy,216,z,fill=colour,outline="#647681",width=1,**static)
            self._wheel_oval(cx,cy,216,self._surface_pixels(216),
                             fill="#8A9CA8",outline="#DBE5EB",width=2,**static)
            for outer,inner,colour in ((213,205,"#344855"),(205,197,"#293D4A"),
                    (197,187,"#223440"),(187,175,"#1D2F3A"),(175,164,"#192B36")):
                self._wheel_band(cx,cy,inner,outer,0,360,self._surface_pixels,
                                 fill=colour,outline="",**static)
            for r,col,w in ((212,"#E0E8ED",1.5),(205,"#879CA9",1),
                            (197,"#526875",1),(164,"#C9D5DC",2)):
                self._wheel_oval(cx,cy,r,self._surface_pixels(r),
                                 fill="",outline=col,width=w,**static)
            # Low bevelled diamonds share the finite 3-D collision geometry.
            for index in range(len(RoulettePhysics.DEFLECTORS)):
                points = [(cx+x*WHEEL_METRE_SCALE,
                           cy+y*WHEEL_METRE_SCALE*WHEEL_TILT
                           -self._surface_pixels(math.hypot(x,y)*WHEEL_METRE_SCALE))
                          for x,y in RoulettePhysics.deflector_vertices(index)]
                apex = self._wheel_point(cx,cy,
                    RoulettePhysics.DEFLECTOR_R*WHEEL_METRE_SCALE,
                    math.degrees(RoulettePhysics.DEFLECTORS[index]),
                    self._surface_pixels(RoulettePhysics.DEFLECTOR_R*WHEEL_METRE_SCALE)
                    +RoulettePhysics.DEFLECTOR_HEIGHT*WHEEL_METRE_SCALE)
                for j in range(4):
                    c.create_polygon(*points[j],*points[(j+1)%4],*apex,
                        fill=("#BEC4C7","#8F999F","#D9DEE0","#E9ECEC")[j],
                        outline="#B6BDC1",width=.5,**static)
        c.delete("wheel_rotor","wheel_ball","wheel_hud","wheel_fixed")
        self._draw_wheel_segments(cx,cy,164,107,self.current_wheel_offset)
        self._draw_orbiting_pointer(cx,cy,164)
        self._draw_pocket_occlusion(cx,cy)
        self._draw_wheel_status()

    def _draw_center_title(self, cx, cy, offset_deg):
        """Engrave the permanent title into the rotating metal plate above 0.

        The title is rotor geometry, not a screen-fixed HUD element: its position
        and orientation follow the same metal plate as the 0 pocket.
        """
        c = self.wheel_canvas
        step = 360.0 / len(ROULETTE_SEQUENCE)
        zero_index = ROULETTE_SEQUENCE.index("0")
        zero_mid = offset_deg + (zero_index + .5) * step
        for radius, text, char_w, char_h, gap, weight in (
                (85,"美式轮盘",18.0,20.0,3.5,1.45),
                (69,"AMERICAN ROULETTE",3.2,7.5,1.0,.95)):
            for points in wheel_title_paths(cx,cy,text,zero_mid,radius,char_w,char_h,gap):
                c.create_line(*points,fill="#DCE8EF",width=weight,
                              capstyle="round",joinstyle="round",tags=("wheel_rotor",))

    def _draw_wheel_status(self):
        """One fixed top-left display: 30-second betting timer or winning number."""
        c = self.wheel_canvas
        c.delete("wheel_hud")
        bg, fg = "#14222D", "#E0EBF2"
        if self.round_state == "result":
            title, text = "结果", str(self.center_display_result)
            bg = OUTCOME_COLORS.get(text,"#171B20")
            fg = "#FFFFFF"
        elif self.round_state == "spinning":
            title, text = "开奖", "…"
        else:
            title = "暂停" if self.timer_paused else "下注"
            remaining = (self.paused_remaining if self.timer_paused else
                         max(0.0,(self.betting_deadline or time.time())-time.time()))
            text = f"{math.ceil(remaining):02d}s"
        tags = ("wheel_hud",)
        c.create_rectangle(10,8,96,69,fill=bg,outline="#91AABA",width=2,tags=tags)
        c.create_text(53,20,text=title,fill=fg,font=("Arial",10,"bold"),tags=tags)
        self.wheel_timer_id = c.create_text(53,47,text=text,fill=fg,
                                font=("Arial",23,"bold"),tags=tags)

    def _draw_wheel_number(self, cx, cy, symbol, mid, style):
        # Vector digits use the SAME world-to-screen transform as the rotor.
        # No per-frame rotated-font bounding box, pixel baseline or text anchor.
        for points in wheel_number_paths(cx,cy,symbol,mid):
            self.wheel_canvas.create_line(*points,fill="#EDF3F7",width=1.45,
                                           capstyle="round",joinstyle="round",**style)

    def _draw_wheel_segments(self, cx, cy, outer_r, inner_r, offset_deg):
        c = self.wheel_canvas
        style = {"tags": ("wheel_rotor",)}
        self._wheel_oval(cx,cy,164,self._surface_pixels(164),
                         fill="#182832",outline="#D0DCE3",width=2,**style)
        step = 360/len(ROULETTE_SEQUENCE)
        # One shared sloping pocket floor, lowest at the inner end.
        floor_radii = (109,115,122,130,139.5)
        floor_colours = ("#17232D","#202F3B","#2A3B47","#354955")
        for i,symbol in enumerate(ROULETTE_SEQUENCE):
            start,end = offset_deg+i*step,offset_deg+(i+1)*step
            colour = "#117A5A" if symbol in {"0", "00"} else ("#A92835" if int(symbol) in RED_NUMBERS else "#101A24")
            self._wheel_band(cx,cy,140,163,start,end,self._surface_pixels,
                             fill=colour,outline="#A9BAC5",width=.8,**style)
            self._draw_wheel_number(cx,cy,symbol,(start+end)/2,style)
            for j in range(len(floor_radii)-1):
                self._wheel_band(cx,cy,floor_radii[j],floor_radii[j+1],start,end,
                                 self._surface_pixels,fill=floor_colours[j],outline="",**style)
            # Inner rail wall connects the deep bed to the top rim.
            points = [self._wheel_point(cx,cy,109,a,z) for a,z in
                      ((start,0),(end,0),(end,self._surface_pixels(109)),
                       (start,self._surface_pixels(109)))]
            c.create_polygon(*[v for pt in points for v in pt],
                             fill="#617784",outline="",**style)
        # Paint every identical silver separator after all pocket floors.
        boundaries = [offset_deg+i*step for i in range(len(ROULETTE_SEQUENCE))]
        boundaries.sort(key=lambda a: self._wheel_point(cx,cy,124,a)[1])
        for start in boundaries:
            top = [self._wheel_point(cx,cy,r,start,0) for r in (109,139.5)]
            bottom = [self._wheel_point(cx,cy,r,start,self._surface_pixels(r))
                      for r in reversed(floor_radii)]
            c.create_polygon(*[v for pt in top+bottom for v in pt],
                             fill="#687F8D",outline="",**style)
            c.create_line(*top[0],*top[1],fill="#DDE7ED",width=1.8,**style)
        # Smooth graphite central plate: no rotating wedge colours or grain.
        for radius,colour in ((107,"#849AA8"),(105,"#203340"),(98,"#1E313E"),
                              (83,"#1D303D"),(64,"#1C2F3C")):
            self._wheel_oval(cx,cy,radius,2,fill=colour,outline="",**style)
        self._wheel_oval(cx,cy,106,2,fill="",outline="#B6C8D3",width=1.5,**style)
        self._draw_center_title(cx,cy,offset_deg)
        for j in range(4):
            angle = offset_deg+45+j*90
            tip = self._wheel_point(cx,cy,76,angle,14)
            left = self._wheel_point(cx,cy,15,angle-30,17)
            right = self._wheel_point(cx,cy,15,angle+30,17)
            c.create_line(cx+3,cy-8,tip[0]+3,tip[1]+6,fill="#0B1720",width=7,**style)
            c.create_polygon(*left,*tip,*right,fill="#AEBFCB",outline="#E4EDF2",width=1,**style)
            c.create_line(cx,cy-17,*tip,fill="#F1F6F9",width=1.5,**style)
            x,y = tip
            c.create_oval(x-3.5,y-2.5,x+3.5,y+2.5,fill="#DAE5EC",outline="#728B9C",**style)
        self._wheel_oval(cx,cy,14,19,fill="#6C8596",outline="#D1DFE8",width=2,**style)
        self._wheel_oval(cx,cy,9,22,fill="#C1D2DD",outline="#EDF4F8",width=1,**style)

    def _draw_pocket_occlusion(self, cx, cy):
        """Draw only walls in front of the ball, so it sits inside the groove."""
        if not self.ball_visible or self.ball_radius>RoulettePhysics.POCKET_OUTER*WHEEL_METRE_SCALE:
            return
        if self._surface_pixels(self.ball_radius)+self.ball_height*WHEEL_METRE_SCALE > 1:
            return
        c = self.wheel_canvas
        step = 360/len(ROULETTE_SEQUENCE)
        index = self.ball_pocket_index
        if index is None:
            index = pocket_index(self.pointer_angle,self.current_wheel_offset)
        start = self.current_wheel_offset+index*step
        mid = start+step/2
        style = {"tags": ("wheel_ball",)}
        # The inner wall is foreground only on the far half of the wheel.
        if math.cos(math.radians(mid))>0:
            pts = [self._wheel_point(cx,cy,109,a,z) for a,z in
                   ((start,0),(start+step,0),(start+step,self._surface_pixels(109)),
                    (start,self._surface_pixels(109)))]
            c.create_polygon(*[v for pt in pts for v in pt],fill="#617784",outline="",**style)
            self._wheel_band(cx,cy,107,109,start,start+step,0,
                             fill="#A7BAC6",outline="#DDE7ED",width=.7,**style)
        # One side separator is in front of the sphere; the opposite stays behind.
        ball_ground_y = self._wheel_point(cx,cy,self.ball_radius,self.pointer_angle)[1]
        for a in (start,start+step):
            if self._wheel_point(cx,cy,self.ball_radius,a)[1] <= ball_ground_y:
                continue
            top = [self._wheel_point(cx,cy,r,a,0) for r in (109,139.5)]
            bottom = [self._wheel_point(cx,cy,r,a,self._surface_pixels(r))
                      for r in (139.5,130,122,115,109)]
            c.create_polygon(*[v for pt in top+bottom for v in pt],fill="#687F8D",outline="",**style)
            c.create_line(*top[0],*top[1],fill="#DDE7ED",width=1.8,**style)

    def _draw_orbiting_pointer(self, cx, cy, outer_r):
        """Draw the ball above the bowl, or inside the independent recessed bed."""
        if not getattr(self,"ball_visible",True):
            return
        c = self.wheel_canvas
        radius = self.ball_radius
        # Always use the same continuous support as the solver, even in flight.
        in_grooves = radius <= RoulettePhysics.POCKET_OUTER*WHEEL_METRE_SCALE
        surface = self._surface_pixels(radius)
        x,ground_y = self._wheel_point(cx,cy,radius,self.pointer_angle,surface)
        height = getattr(self,"ball_height",0.0)*WHEEL_METRE_SCALE
        ball_r = RoulettePhysics.BALL_R*WHEEL_METRE_SCALE
        y = ground_y-ball_r-height
        style = {"tags": ("wheel_ball",)}
        shadow_r = 6+min(4,height*.10)
        shadow_colour = "#344753" if height > 6 else "#080F16"
        if in_grooves and height < 2:
            shadow_r = ball_r*.90
        c.create_oval(x-shadow_r,ground_y-1.5,x+shadow_r,ground_y+2,
                      fill=shadow_colour,outline="",**style)
        c.create_oval(x-ball_r,y-ball_r,x+ball_r,y+ball_r,
                      fill="#CBD4DA",outline="#F4F8FB",width=1,**style)
        # A broad, soft oval highlight reads as specular reflection at wheel
        # scale; tiny near-square spots rasterise as hard white pixels.
        c.create_oval(x-ball_r*.68,y-ball_r*.72,
                      x-ball_r*.08,y-ball_r*.24,
                      fill="#E2EAF0",outline="",**style)
        c.create_oval(x-ball_r*.55,y-ball_r*.68,
                      x-ball_r*.20,y-ball_r*.43,
                      fill="#F4F7F9",outline="",**style)


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

        # Straight up spots: 0, 00, 1-36
        add_spot(
            "straight_00",
            "straight",
            "00",
            {"00"},
            BET_ODDS["straight"],
            (g.zero_x1, g.grid_y1, g.zero_x2, g.grid_y1 + g.zero_h),
            ((g.zero_x1 + g.zero_x2) / 2, g.grid_y1 + g.zero_h / 2),
            kind="cell",
        )

        add_spot(
            "straight_0",
            "straight",
            "0",
            {"0"},
            BET_ODDS["straight"],
            (g.zero_x1, g.grid_y1 + g.zero_h, g.zero_x2, g.grid_y1 + 2 * g.zero_h),
            ((g.zero_x1 + g.zero_x2) / 2, g.grid_y1 + 1.5 * g.zero_h),
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

        # Five-number top line: 0/00/1/2/3
        add_spot(
            "five_number",
            "five_number",
            "0/00/1/2/3",
            g.five_number_numbers(),
            BET_ODDS["five_number"],
            (g.grid_x1 - 10, g.dozen_y1 - 10, g.grid_x1 + 10, g.dozen_y1 + 10),
            (g.grid_x1, g.dozen_y1),
            kind="point",
        )

        # Special zero-area split / intersection bets
        add_spot(
            "split_0_00",
            "split",
            "0-00",
            {"0", "00"},
            BET_ODDS["split"],
            (g.zero_x1 + 8, g.grid_y1 + g.zero_h - 9, g.zero_x2 - 8, g.grid_y1 + g.zero_h + 9),
            ((g.zero_x1 + g.zero_x2) / 2, g.grid_y1 + g.zero_h),
            kind="line",
        )

        add_spot(
            "split_00_3",
            "split",
            "00-3",
            {"00", "3"},
            BET_ODDS["split"],
            (g.zero_x2 - 9, g.grid_y1 + 8, g.zero_x2 + 9, g.grid_y1 + g.num_h - 8),
            (g.zero_x2, g.grid_y1 + g.num_h / 2),
            kind="line",
        )

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

        add_spot(
            "triple_00_2_3",
            "street",
            "00-2-3",
            {"00", "2", "3"},
            BET_ODDS["street"],
            (g.zero_x2 - 10, g.grid_y1 + g.num_h - 10, g.zero_x2 + 10, g.grid_y1 + g.num_h + 10),
            (g.zero_x2, g.grid_y1 + g.num_h),
            kind="point",
        )

        add_spot(
            "triple_0_00_2",
            "street",
            "0-00-2",
            {"0", "00", "2"},
            BET_ODDS["street"],
            (g.zero_x2 - 10, g.grid_y1 + g.zero_h - 10, g.zero_x2 + 10, g.grid_y1 + g.zero_h + 10),
            (g.zero_x2, g.grid_y1 + g.zero_h),
            kind="point",
        )

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
        inside_types = {"straight", "split", "street", "corner", "six_line", "five_number"}
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

        # 内围投注
        if spot["type"] in (
            "straight",
            "split",
            "corner",
            "street",
            "six_line",
            "five_number",
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
        self.board_canvas.delete("chips")
        self.placed_chip_items = {}
        for spot_id, amount in self.current_bets.items():
            if amount > 0:
                spot = self._find_spot_by_id(spot_id)
                if spot:
                    fill = self.current_bet_colors.get(spot_id, self._chip_fill_color_for_amount(amount))
                    self._draw_chip_on_spot(spot, amount, fill)

        self._draw_racetrack()

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

        self.current_bets.clear()
        self.current_bet_colors.clear()

        self._refresh_balance_display()
        self._refresh_bet_totals()
        self._repaint_all_chips()

        self._show_round_amount("本局下注金额", 0)

    def clear_single_bet(self, spot_id: str):
        if self.round_state != "betting":
            return
        amount = self.current_bets.get(spot_id, 0)
        if amount > 0:
            self.balance += amount * self.bet_multiplier
            self.current_bets.pop(spot_id, None)
            self.current_bet_colors.pop(spot_id, None)
            self._refresh_balance_display()
            self._refresh_bet_totals()
            self._repaint_all_chips()

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
    def _start_new_round(self):
        self.ball_visible = self.physics is not None
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

        self.round_state = "betting"
        self._refresh_bet_totals()
        self.current_round_result = None
        self.current_round_index = None

        # Keep the captured ball and coasting rotor through the next betting round.
        self.is_pointer_spinning = False
        if self.physics is not None:
            self._sync_physics_display()

        self._enable_amount_buttons()
        self._set_control_buttons_state(tk.NORMAL)
        self._set_bet_buttons_state(tk.NORMAL)

        self._refresh_bet_totals()

        self._draw_wheel()
        self._redraw_board_for_result_flash(flash_on=False)
        self._add_help_button_on_board()

        self.betting_deadline = time.time() + self.BETTING_SECONDS
        self._update_countdown()
        
    def _update_countdown(self):
        if self.timer_paused:
            # 暂停时不更新倒计时，也不自动结束
            return

        remaining = int(math.ceil(self.betting_deadline - time.time()))
        if remaining < 0:
            remaining = 0

        self._draw_wheel_status()

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

    def _start_startup_rotation(self):
        """Decorative loading motion: date pocket, with no result or payout."""
        if self._spin_job is not None:
            self.after_cancel(self._spin_job)
        self._spin_job = None
        p = RoulettePhysics(initial_angle=math.radians(self.current_wheel_offset),
                            initial_speed=math.radians(18.0))
        p.pocket = startup_date_pocket()
        p.mode = "display"
        p.r = p.POCKET_CENTRE
        p.theta = (p.wheel_angle+(p.pocket+.5)*p.STEP) % p.TAU
        p.omega = p.wheel_speed
        p.vr = p.z = p.vz = 0.0
        self.physics = p
        self._round_settled = True
        self.ball_visible = True
        self.is_pointer_spinning = False
        self._last_physics_time = time.monotonic()
        self._physics_update()

    def _sync_physics_display(self):
        p = self.physics
        wheel,speed,theta,omega,radius,height = p.render_state()
        self.current_wheel_offset = math.degrees(wheel) % 360
        self.wheel_velocity = math.degrees(speed)
        self.pointer_angle = math.degrees(theta) % 360
        self.pointer_velocity = math.degrees(omega)
        self.ball_radius = radius*WHEEL_METRE_SCALE
        self.ball_height = height
        self.ball_pocket_index = p.pocket

    def _start_physical_spin(self):
        # Continue the moving rotor at the exact current angle and velocity.
        now = time.monotonic()
        if self._spin_job is not None:
            self.after_cancel(self._spin_job)
        self._spin_job = None
        if self.physics is not None:
            self.physics.advance(max(0.0,now-self._last_physics_time))
            angle, speed = self.physics.wheel_angle, self.physics.wheel_speed
        else:
            angle, speed = math.radians(self.current_wheel_offset), 0.0
        self.physics = RoulettePhysics(initial_angle=angle, initial_speed=speed)
        self._round_settled = False
        self.is_spinning = True
        self.is_pointer_spinning = True
        self.ball_visible = True
        self._last_physics_time = now
        self._physics_update()

    def _physics_update(self):
        self._spin_job = None
        now = time.monotonic()
        self.physics.advance(max(0.0,now-self._last_physics_time))
        self._last_physics_time = now
        self._sync_physics_display()
        if (self.round_state == "spinning" and self.physics.result_index is not None
                and not self._round_settled):
            self._finish_physical_spin()
        self.is_spinning = not self.physics.stopped
        self._draw_wheel()
        # Betting/settlement never stop the rotor. Only its own coast curve does.
        if (self.physics.stopped and
                (self.physics.result_index is not None or self.physics.mode == "display")):
            return
        self._spin_job = self.after(16,self._physics_update)

    def _finish_physical_spin(self):
        """Settle the captured ball exactly once; keep rotor animation running."""
        if self._round_settled or self.physics.result_index is None:
            return
        self._round_settled = True
        self.is_pointer_spinning = False
        self.current_round_index = self.physics.result_index
        self.current_round_result = ROULETTE_SEQUENCE[self.current_round_index]
        self._finish_round(self.current_round_result)

    
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
            text = spot["label"]  # 0 / 00 / 1-36
            font = ("Segoe UI Emoji", 11, "bold") if text == "00" else ("Arial", 11, "bold")
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
            "pointer_angle": self.pointer_angle,               # 指针最终角度（0~360）
            "wheel_offset": self.current_wheel_offset,         # 轮盘最终偏移角度
            "result_index": self.current_round_index,          # 在 ROULETTE_SEQUENCE 中的索引
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
        cx = self.wheel_canvas.winfo_width() / 2
        cy = self.wheel_canvas.winfo_height() / 2 - 1   # 与 _draw_wheel 中的 cy 一致
        dx = event.x - cx
        dy = event.y - cy
        # 内圆半径大约 70（从 _draw_wheel 中 inner_r = 70）
        inner_r = 70
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

        step = 360.0 / 38   # 每个扇区角度跨度
        # 扇区边界算法：假设轮盘上第 i 个扇区的起始边界（相对于轮盘自身0点）为 i * step
        # 绝对坐标下的起始边界 = (i * step + offset) % 360
        def sector_range(i):
            start = (i * step + offset) % 360
            end = (start + step) % 360
            return start, end

        cur_start, cur_end = sector_range(idx)
        prev_idx = (idx - 1) % 38
        prev_start, prev_end = sector_range(prev_idx)
        next_idx = (idx + 1) % 38
        next_start, next_end = sector_range(next_idx)

        # 构建弹窗
        self.detail_window = tk.Toplevel(self)
        self.detail_window.title("开奖详情")
        self.detail_window.geometry("500x420")
        self.detail_window.resizable(False, False)

        text = f"""
    【本局开奖结果】: {result}

    【指针最终角度】: {pointer:.4f}°

    【上一个数字】: {ROULETTE_SEQUENCE[prev_idx]}
        角度范围: {prev_start:.4f}° ～ {prev_end:.4f}°

    【中奖数字扇区】: {result}
        角度范围: {cur_start:.4f}° ～ {cur_end:.4f}°

    【下一个数字】: {ROULETTE_SEQUENCE[next_idx]}
        角度范围: {next_start:.4f}° ～ {next_end:.4f}°

    说明:
    - 角度以正上方为 0°，顺时针增加。
    - 指针角度是它的绝对方向
    - 扇区范围是轮盘上该数字占据的绝对角度区间。
    - 若结果落在指针指向的扇区内，即为中奖。
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
            chip["canvas"].bind("<Button-1>", lambda e, t=chip["text"], c=chip["canvas"], cid=chip["chip_id"], bg=chip.get("bg_color", "#ffffff"): self._set_bet_amount(t, c, cid, bg))

    def _disable_amount_buttons(self):
        for chip in self.chip_buttons:
            chip["canvas"].config(state=tk.DISABLED)
            chip["canvas"].unbind("<Button-1>")

    def _set_control_buttons_state(self, state):
        """
        控制游戏相关按钮的状态（清除下注、重复上局下注、暂停倒计时、开始游戏）
        state: tk.NORMAL 或 tk.DISABLED
        """
        for button in self.multiplier_buttons:
            button.config(state=state)
        self.deal_button.config(state=state)
        self.reset_button.config(state=state)
        self.repeat_last_btn.config(state=state)
        self.pause_timer_btn.config(state=state)
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
        # 父窗口继续运行时，取消属于当前游戏页面的所有定时回调。
        for job in self.tk.splitlist(self.tk.call("after", "info")):
            try:
                script = self.tk.call("after", "info", job)[0]
                command = self.tk.splitlist(script)[0]
                if command in (self._tclCommands or ()):
                    self.after_cancel(job)
            except (tk.TclError, IndexError):
                pass
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
        for index, number in enumerate(ROULETTE_SEQUENCE):
            fractions = [(index + step / 6) / len(ROULETTE_SEQUENCE) for step in range(7)]
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
            x, y = self._racetrack_point((index + 0.5) / len(ROULETTE_SEQUENCE), 72)
            canvas.create_text(x * 1.35 + 57, y * 1.35 + 40, text=number,
                               fill=RACETRACK_NEIGHBOR_HOVER_TEXT if selected else "white", font=("Arial", 12, "bold"))
        for distance, points in sorted(outlines, reverse=True):
            canvas.create_line(*[v for point in points + [points[0]] for v in point],
                                fill=RACETRACK_NEIGHBOR_HOVER_EDGE, width=4, joinstyle=tk.ROUND)
        count = neighbors * 2 + 1
        canvas.create_text(400, 171, text="American Roulette", fill="#F5D68A",
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
        card(25, 48, 225, 90, "1 下注", f"{self.BETTING_SECONDS} 秒\n可暂停 / 提前开始")
        arrow(258, 92, 282, 92)
        card(288, 48, 225, 90, "2 旋转", "锁定下注与倍数")
        arrow(521, 92, 545, 92)
        card(551, 48, 224, 90, "3 开奖", "中奖返还 → 下一局")
        card(70, 165, 250, 95, "輪盤布局 Roulette Layout", "Straight Up 直注筹码")
        arrow(332, 205, 466, 205); arrow(466, 224, 332, 224)
        card(480, 165, 250, 95, "Racetrack", "同一号码、同一金额")
        canvas.create_text(400, 281, text="有非直注 → 锁定切换；清除非直注 → 恢复切换。旋转 / 开奖时仍锁定。",
                           fill="white", font=("Arial", 11))
        card(25, 310, 225, 83, "内围每个下注位", "基础上限 200")
        card(288, 310, 225, 83, "外围每个下注位", "基础上限 500")
        card(551, 310, 224, 83, "实际扣款", "基础下注总和 × 倍数")
        canvas.create_text(400, 420, text="结算示例：直注基础 25 × 倍数 10，押中一个号码", fill="#F5D68A",
                           font=("Arial", 12, "bold"))
        card(25, 445, 225, 81, "扣款", "$250")
        card(288, 445, 225, 81, "含本金返还", "25 × 36 × 10 = $9,000")
        card(551, 445, 224, 81, "净赢", "$8,750")
        canvas.create_text(400, 551, text="邻号按整组检查余额及每号限额；超限等额缩减，余额不足则整组不下注。",
                           fill="white", font=("Arial", 11))

    def show_game_instructions(self):
        """一次展示全部美式主盘落点及邻号说明。"""
        import tkinter as tk
        from tkinter import ttk

        old = getattr(self, "_instruction_window", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.lift()
                    old.focus_set()
                    return
            except tk.TclError:
                pass

        root = self.winfo_toplevel()
        root.update_idletasks()

        win = tk.Toplevel(root)
        self._instruction_window = win
        win.title("美式轮盘 · 下注图解")
        win.transient(root)
        win.configure(bg="#EDF2F7")

        width = min(1100, root.winfo_screenwidth() - 40)
        height = min(680, root.winfo_screenheight() - 30)

        # 根据当前 Tk 窗口的位置和尺寸计算居中坐标。
        x = root.winfo_rootx() + (root.winfo_width() - width) // 2
        y = root.winfo_rooty() + (root.winfo_height() - height) // 2

        win.geometry(f"{width}x{height}+{x}+{y}")

        FONT = "Microsoft YaHei UI"
        INK, MUTED = "#173247", "#526477"
        BLUE, BORDER = "#B9E1EE", "#0B4A6B"
        GOLD, GREEN = "#FFE08A", "#24463B"

        def close():
            if getattr(self, "_instruction_window", None) is win:
                self._instruction_window = None
            win.destroy()

        # ==================== 固定标题栏 ====================
        header = tk.Frame(win, bg="#142D40")
        header.pack(fill="x")

        title_box = tk.Frame(header, bg="#142D40")
        title_box.pack(side="left", padx=24, pady=15)

        tk.Label(
            title_box,
            text="美式轮盘  /  下注图解",
            bg="#142D40",
            fg="white",
            font=(FONT, 20, "bold"),
        ).pack(anchor="w")

        tk.Label(
            title_box,
            text="全部落点直接展示 · 向下滚动查看跑道盘",
            bg="#142D40",
            fg="#C7D9E8",
            font=(FONT, 11),
        ).pack(anchor="w", pady=(5, 0))

        tk.Button(
            header,
            text="关闭  Esc",
            command=close,
            bg="#29485F",
            fg="white",
            activebackground="#3A617C",
            activeforeground="white",
            relief="flat",
            font=(FONT, 11),
            padx=14,
            pady=8,
        ).pack(side="right", padx=24)

        # ==================== 连续滚动页面 ====================
        host = tk.Frame(win, bg="#EDF2F7")
        host.pack(fill="both", expand=True)

        cv = tk.Canvas(
            host,
            bg="#EDF2F7",
            highlightthickness=0,
            yscrollincrement=28,
        )
        ys = ttk.Scrollbar(
            host, orient="vertical", command=cv.yview
        )
        xs = ttk.Scrollbar(
            host, orient="horizontal", command=cv.xview
        )

        cv.configure(
            yscrollcommand=ys.set,
            xscrollcommand=xs.set,
        )
        cv.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")

        host.grid_rowconfigure(0, weight=1)
        host.grid_columnconfigure(0, weight=1)

        # ==================== 共用绘图工具 ====================
        def text(
            x, y, value, size=12, color=INK,
            bold=False, anchor="nw", wrap=None
        ):
            opts = {
                "text": value,
                "fill": color,
                "anchor": anchor,
                "justify": "center" if anchor == "center" else "left",
                "font": (FONT, size, "bold" if bold else "normal"),
            }
            if wrap:
                opts["width"] = wrap
            return cv.create_text(x, y, **opts)

        def card(x, y, w, h):
            cv.create_rectangle(
                x, y, x + w, y + h,
                fill="white",
                outline="#D5DFE8",
            )
            cv.create_rectangle(
                x, y, x + w, y + 4,
                fill=BORDER,
                outline="",
            )

        def section(y, number, title, subtitle):
            cv.create_rectangle(
                24, y, 63, y + 34,
                fill=BORDER,
                outline="",
            )
            text(
                43, y + 17, number,
                13, "white", True, "center",
            )
            text(77, y - 1, title, 19, INK, True)
            text(24, y + 46, subtitle, 12, MUTED)
            return y + 86

        outside = {
            "outside_0": "小",
            "outside_1": "双",
            "outside_2": "红",
            "outside_3": "黑",
            "outside_4": "单",
            "outside_5": "大",
        }
        dozens = {
            "dozen_1": "第一打 1—12",
            "dozen_2": "第二打 13—24",
            "dozen_3": "第三打 25—36",
        }

        def table(left, top, marks=(), legs=()):
            """使用游戏实际投注坐标，绘制全部指定落点。"""
            scale = 0.95
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
                    if label in {"0", "00"}:
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
                    label = "2:1"

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
                    outline=GOLD,
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

        # ==================== 01 主盘全部落点 ====================
        groups = [
            (
                "直注", {"straight"}, "35:1",
                "每个号码格中心，包括0和00。",
            ),
            (
                "分注", {"split"}, "17:1",
                "两个相邻号码的共用边，包括零区分注。",
            ),
            (
                "街注与零区三号注", {"street"}, "11:1",
                "12条街注，以及0/1/2、00/2/3两个三号注。",
            ),
            (
                "角注", {"corner"}, "8:1",
                "四个号码的交点；一次覆盖四个号码。",
            ),
            (
                "六线注", {"six_line"}, "5:1",
                "两条街的共用端点；一次覆盖六个号码。",
            ),
            (
                "打注", {"dozen"}, "2:1",
                "第一打1—12；第二打13—24；第三打25—36。",
            ),
            (
                "列注", {"column"}, "2:1",
                "右侧三个位置，每个位置覆盖对应一列的12个号码。",
            ),
            (
                "大小、单双、红黑",
                {"high_low", "odd_even", "color"},
                "1:1",
                "小1—18，大19—36；六个外围位置均不含0和00。",
            ),
        ]

        groups.append((
            "五数注", {"five_number"}, "6:1",
            "覆盖0、00、1、2、3；金色空心圆为五数注落点。",
        ))

        total = sum(
            1 for s in self.bet_spots
            if any(s["type"] in group[1] for group in groups)
        )

        y = section(
            24,
            "01",
            "主投注盘 · 全部下注位置",
            f"共 {total} 个合法落点。金色空心圆就是下注中心；"
            f"下列{len(groups)}张图同时展示，无须切换。",
        )

        for i, (name, kinds, odds, hint) in enumerate(groups):
            x = 24 + (i % 2) * 536
            top = y + (i // 2) * 386
            marks = [
                s for s in self.bet_spots
                if s["type"] in kinds
            ]

            card(x, top, 516, 366)

            text(x + 18, top + 20, name, 15, INK, True)
            text(
                x + 18, top + 53,
                f"{len(marks)}个落点   ·   净赢赔率 {odds}",
                11, MUTED,
            )

            table(x + 12, top + 76, marks=marks)

            text(
                x + 18, top + 323,
                hint, 11, MUTED, wrap=478,
            )

        y += ((len(groups) + 1) // 2) * 386 + 4

        # ==================== 跑道共用绘图 ====================
        def track(top, neighbor_center=None, count=2):
            """保留游戏原有数字顺序、分区边界和跑道几何算法。"""
            ox, oy, scale = 66, top, 1.9

            def coords(points):
                return [
                    value
                    for x, yy in points
                    for value in (
                        ox + x * scale,
                        oy + yy * scale,
                    )
                ]

            for i, number in enumerate(ROULETTE_SEQUENCE):
                fractions = [
                    (i + j / 6) / len(ROULETTE_SEQUENCE)
                    for j in range(7)
                ]
                points = [
                    self._racetrack_point(t, 94)
                    for t in fractions
                ]
                points += [
                    self._racetrack_point(t, 50)
                    for t in reversed(fractions)
                ]

                if number in {"0", "00"}:
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
                    (i + 0.5) / len(ROULETTE_SEQUENCE),
                    73,
                )
                text(
                    ox + xx * scale,
                    oy + yy * scale,
                    number,
                    14, ink, True, "center",
                )

            text(ox + 254 * scale, oy + 108 * scale,
                 "American Roulette", 24, GREEN, True, "center")

        # ==================== 03 邻号说明 ====================
        y = section(
            y,
            "02",
            "邻号下注 · 按轮盘顺序覆盖",
            "跑道上的38个号码都可作为中心。中心加左右各0—5个邻号，"
            "分别形成1、3、5、7、9、11个直注。",
        )

        card(24, y, 1052, 482)
        text(
            44, y + 20,
            "示例：以0为中心，左右各2个邻号",
            15, INK, True,
        )

        track(y + 55, neighbor_center="0", count=2)

        text(
            44, y + 448,
            "覆盖14、2、0、28、9；每号25，总下注125。"
            "命中任一号返还900，本局净赢775。",
            11, MUTED,
        )
        y += 506

        # ==================== 04 操作与赔付 ====================
        y = section(
            y,
            "03",
            "下注与赔付须知",
            "图解仅用于说明，打开此窗口不会改变你的下注或余额。",
        )

        notes = [
            (
                "标准赔率",
                "赔率均为净赢赔率。"
                "中奖返还＝中奖子注金额×（赔率＋1）×倍数；"
                "本局净额＝全部返还－全部下注。",
            ),
            (
                "邻号下注",
                "每个选中号码分别作为直注结算；左右各0—5个邻号。"
                "邻号按整组检查余额及每号限额；超限等额缩减，余额不足则整组不下注。",
            ),
            (
                "下注限额与操作",
                "内围每个下注位基础上限200，外围每个下注位基础上限500。"
                "左键下注；右键清除该下注位并退款。跑道盘右键只清除一个号码。",
            ),
            (
                "视图与开局",
                "主盘与跑道盘共享直注筹码；有非直注时锁定视图切换。"
                "倒计时结束或点击开始后锁定下注与倍数，开奖结果按现有赔率结算。",
            ),
            (
                "零与倒计时",
                "0和00不属于大小、单双、红黑、打注或列注。"
                "说明窗口不会暂停倒计时，需要时请先暂停游戏。",
            ),
        ]

        for title, body in notes:
            card(24, y, 1052, 102)
            text(44, y + 18, title, 14, INK, True)
            text(
                44, y + 49,
                body, 12, MUTED, wrap=1008,
            )
            y += 116

        text(
            24, y + 4,
            "金额示例统一使用倍数1；实际游戏按当前倍数结算。",
            11, MUTED,
        )

        cv.configure(scrollregion=(0, 0, 1100, y + 60))

        # ==================== 滚轮与关闭 ====================
        def wheel(event):
            if getattr(event, "num", None) in (4, 5):
                steps = -3 if event.num == 4 else 3
            else:
                delta = getattr(event, "delta", 0)
                if not delta:
                    return
                steps = max(1, int(abs(delta) / 120))
                if delta > 0:
                    steps = -steps

            cv.yview_scroll(steps, "units")
            return "break"

        win.bind("<MouseWheel>", wheel)
        win.bind("<Button-4>", wheel)
        win.bind("<Button-5>", wheel)
        win.bind("<Escape>", lambda event: close())
        win.protocol("WM_DELETE_WINDOW", close)
        win.after_idle(win.focus_set)

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
    root._roulette_american_standalone = True
    page = RouletteGameGUI(root, initial_balance=actual_balance, username=actual_user)
    page.pack(fill=tk.BOTH, expand=True)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")
