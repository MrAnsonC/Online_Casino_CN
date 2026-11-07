"""Classic Pai Gow · UTH UI · V7 (7 players + banker).

Run: python Classic_Pai_Gow_UTH_V7.py
Requires Python 3, Tkinter and Pillow. Original main(...) embedding API retained.
Guest mode works without A_Tools; named accounts require original encrypted storage.
"""
import sys
from pathlib import Path
_ACCOUNT_ROOT = next((p for p in (Path(__file__).resolve().parent,
    *Path(__file__).resolve().parents)
    if (p / 'A_Tools' / 'Account' / 'secure_json.py').is_file()), None)
if _ACCOUNT_ROOT is not None:
    if str(_ACCOUNT_ROOT) not in sys.path:
        sys.path.insert(0, str(_ACCOUNT_ROOT))
    from A_Tools.Account import install_secure_json
    install_secure_json()

import json
import os
import secrets
import random
import time
import math
import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass
from itertools import combinations, product
from decimal import Decimal, ROUND_HALF_UP
from PIL import Image, ImageDraw, ImageTk

WINDOW_GEOMETRY = '1150x750+50+10'
ROOT_BG = '#1B3D31'
TEXT = '#ffffff'
RED = '#ff2a23'
BLACK = '#050505'
DARK_BLUE = '#173f66'
GOLD = '#D4AF37'
GOLD_DARK = '#8d742d'
PANEL_BG = '#F2E6C9'
HEADER_BG = '#D8B46A'
TITLE_FG = '#2A1B08'
MIN_ANTE, MAX_ANTE = 10, 25000
CLASSIC_TILE_ASPECT = 2.5
CHIPS = [(10, '#ffa500'), (25, '#00ff00'), (100, BLACK),
         (500, '#FF7DDA'), (1000, TEXT), (2500, RED)]


def get_data_file_path():
    if _ACCOUNT_ROOT is None:
        raise RuntimeError('Named accounts require A_Tools/Account/secure_json.py')
    return str(_ACCOUNT_ROOT / 'A_Tools' / 'Account' / 'saving_data.json')

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


GD_PIPS = {
    1: ((0, 0),), 2: ((-1, -1), (1, 1)),
    3: ((-1, -1), (0, 0), (1, 1)),
    4: ((-1, -1), (1, -1), (-1, 1), (1, 1)),
    5: ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)),
    6: ((-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)),
}
GD_DICE_COLORS = ((47, 127, 235), (224, 64, 59), (239, 187, 57))
GD_DICE_PIP_COLORS = ((250, 247, 238, 255), (250, 247, 238, 255), (53, 33, 8, 255))

# World-space rigid cubes; geometry is shared by collision, rendering and scoring.
GD_SCENE_UNIT = 600.0
GD_DICE_EDGE_PX = 22.0
GD_BOWL_SCALE = 1.55
GD_VIEW_DEPTH = .28 / math.hypot(.28, .70)
GD_VIEW_UP = .70 / math.hypot(.28, .70)
def _gd_view_projection():
    return GD_VIEW_DEPTH, GD_VIEW_UP, 96., (0., GD_VIEW_UP, GD_VIEW_DEPTH)


def _gd_dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _gd_cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _gd_add(a, b):
    return tuple(x+y for x, y in zip(a, b))


def _gd_sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _gd_scale(a, amount):
    return tuple(x*amount for x in a)


def _gd_length(a):
    return math.sqrt(_gd_dot(a, a))


def _gd_unit(a):
    length = _gd_length(a)
    return _gd_scale(a, 1/length) if length > 1e-12 else (0., 0., 0.)


def _gd_rotate(q, omega, dt):
    speed = _gd_length(omega)
    if speed < 1e-12:
        return q
    a = speed*dt/2
    dw = math.cos(a)
    dx, dy, dz = _gd_scale(omega, math.sin(a)/speed)
    w, x, y, z = q
    r = (dw*w-dx*x-dy*y-dz*z, dw*x+dx*w+dy*z-dz*y,
         dw*y-dx*z+dy*w+dz*x, dw*z+dx*y-dy*x+dz*w)
    norm = math.sqrt(sum(v*v for v in r))
    return tuple(v/norm for v in r)


def _gd_qvector(q, v):
    xyz = q[1:]
    t = _gd_scale(_gd_cross(xyz, v), 2)
    return _gd_add(v, _gd_add(_gd_scale(t, q[0]), _gd_cross(xyz, t)))


# Standard six-sided dice: 1 opposite 6, 2 opposite 5, 3 opposite 4.
# Fixed standard pip layouts rotate with the cube; the result is its upward face.
GD_CUBE_FACES = (
    (1, (0., 0., 1.), (1., 0., 0.), (0., 1., 0.)),
    (6, (0., 0., -1.), (1., 0., 0.), (0., -1., 0.)),
    (3, (1., 0., 0.), (0., 1., 0.), (0., 0., 1.)),
    (4, (-1., 0., 0.), (0., -1., 0.), (0., 0., 1.)),
    (2, (0., 1., 0.), (-1., 0., 0.), (0., 0., 1.)),
    (5, (0., -1., 0.), (1., 0., 0.), (0., 0., 1.)),
)


class GoldenRigidDie:
    EDGE = GD_DICE_EDGE_PX / GD_SCENE_UNIT
    HALF = EDGE/2
    INVERSE_INERTIA = 6/(EDGE*EDGE)  # unit mass, uniform solid cube
    LANDING_ANGLE_DEGREES = 8.0
    LANDING_ALIGNMENT = math.cos(math.radians(LANDING_ANGLE_DEGREES))
    CONTACT_TOLERANCE = EDGE*math.sin(math.radians(LANDING_ANGLE_DEGREES))

    def __init__(self, x, top=1):
        self.p = (x, 0., self.HALF)
        self.v = (0., 0., 0.)
        self.omega = (0., 0., 0.)
        self.q = (1., 0., 0., 0.)
        # This initialization restores saved top faces only; rounds never assign faces.
        normal = next(face[1] for face in GD_CUBE_FACES if face[0] == top)
        axis = _gd_cross(normal, (0., 0., 1.))
        if _gd_length(axis) > 1e-10:
            self.q = _gd_rotate(self.q, _gd_unit(axis), math.acos(normal[2]))
        elif normal[2] < 0:
            self.q = _gd_rotate(self.q, (1., 0., 0.), math.pi)

    def axes(self):
        return tuple(_gd_qvector(self.q, axis) for axis in
                     ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)))

    def vertices(self):
        axes = self.axes()
        return [_gd_add(self.p, _gd_scale(_gd_add(_gd_scale(axes[0], x),
                         _gd_add(_gd_scale(axes[1], y), _gd_scale(axes[2], z))), self.HALF))
                for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]

    def support(self, normal):
        point = self.p
        for axis in self.axes():
            projection = _gd_dot(axis, normal)
            if abs(projection) > 1e-9:
                point = _gd_add(point, _gd_scale(axis, math.copysign(self.HALF, projection)))
        return point

    def impulse(self, impulse, point):
        self.v = _gd_add(self.v, impulse)
        self.omega = _gd_add(self.omega, _gd_scale(_gd_cross(_gd_sub(point, self.p), impulse),
                                            self.INVERSE_INERTIA))

    def top_face(self):
        candidates = [(number, _gd_qvector(self.q, normal)[2])
                      for number, normal, _u, _v in GD_CUBE_FACES]
        number, alignment = max(candidates, key=lambda item: item[1])
        return number if alignment >= self.LANDING_ALIGNMENT-1e-12 else None

    def settled(self):
        floor = min(point[2] for point in self.vertices())
        return (self.top_face() is not None and abs(floor) <= self.CONTACT_TOLERANCE
                and _gd_length(self.v) < .005 and _gd_length(self.omega) < .12)

    def stabilize_contact(self):
        """Remove contact chatter only when a face is already almost flat."""
        face = max(GD_CUBE_FACES, key=lambda f: _gd_qvector(self.q, f[1])[2])
        normal = _gd_qvector(self.q, face[1])
        if (normal[2] > .999 and self.p[2] < self.HALF+self.EDGE*.04
                and _gd_length(self.v) < .08 and _gd_length(self.omega) < 12.):
            axis = _gd_cross(normal, (0., 0., 1.))
            if _gd_length(axis) > 1e-12:
                self.q = _gd_rotate(self.q, _gd_unit(axis), math.acos(min(1., normal[2])))
            self.p = (self.p[0], self.p[1], self.HALF)
            self.v = self.omega = (0., 0., 0.)


def _gd_overlap(a, b):
    """Read-only OBB contact query shared by physics and final validation."""
    aa, ba = a.axes(), b.axes()
    axes = list(aa)+list(ba)+[_gd_cross(x, y) for x in aa for y in ba]
    delta = _gd_sub(b.p, a.p)
    normal, penetration = None, float('inf')
    for axis in axes:
        if _gd_length(axis) < 1e-8:
            continue
        axis = _gd_unit(axis)
        ra = a.HALF*sum(abs(_gd_dot(axis, v)) for v in aa)
        rb = b.HALF*sum(abs(_gd_dot(axis, v)) for v in ba)
        overlap = ra+rb-abs(_gd_dot(delta, axis))
        if overlap <= 0:
            return None
        if overlap < penetration:
            penetration = overlap
            normal = axis if _gd_dot(delta, axis) >= 0 else _gd_scale(axis, -1)
    return normal, penetration


def _gd_collide_dice(a, b):
    """OBB contact, friction impulses and angular response from BacBo."""
    contact_info = _gd_overlap(a, b)
    if contact_info is None:
        return False
    normal, penetration = contact_info
    contact = _gd_scale(_gd_add(a.support(normal), b.support(_gd_scale(normal, -1))), .5)
    ra, rb = _gd_sub(contact, a.p), _gd_sub(contact, b.p)
    av = _gd_add(a.v, _gd_cross(a.omega, ra))
    bv = _gd_add(b.v, _gd_cross(b.omega, rb))
    relative = _gd_sub(bv, av)
    speed = _gd_dot(relative, normal)
    if speed < 0:
        effective = 2+a.INVERSE_INERTIA*(_gd_dot(_gd_cross(ra, normal), _gd_cross(ra, normal))
                                       + _gd_dot(_gd_cross(rb, normal), _gd_cross(rb, normal)))
        amount = -(1.4 if speed < -.08 else 1.)*speed/effective
        impulse = _gd_scale(normal, amount)
        a.impulse(_gd_scale(impulse, -1), contact)
        b.impulse(impulse, contact)
        tangent = _gd_sub(relative, _gd_scale(normal, speed))
        if _gd_length(tangent) > 1e-9:
            direction = _gd_unit(tangent)
            effective = 2+a.INVERSE_INERTIA*(
                _gd_length(_gd_cross(ra, direction))**2+_gd_length(_gd_cross(rb, direction))**2)
            friction = min(.35*amount, _gd_length(tangent)/effective)
            a.impulse(_gd_scale(direction, friction), contact)
            b.impulse(_gd_scale(direction, -friction), contact)
    correction = _gd_scale(normal, (penetration+.000002)*.5)
    a.p = _gd_sub(a.p, correction)
    b.p = _gd_add(b.p, correction)
    return True


class GoldenDiceBowl:
    DICE_COUNT = 3
    RADIUS = .085 * GD_BOWL_SCALE
    HEIGHT = .128 * GD_BOWL_SCALE

    def __init__(self, values=None, rng=None):
        self.rng = rng or random.SystemRandom()
        values = values or [self.rng.randint(1, 6) for _ in range(self.DICE_COUNT)]
        if len(values) != self.DICE_COUNT or any(type(n) is not int or n not in range(1, 7) for n in values):
            raise ValueError('经典牌九需要三颗有效骰子。')
        self.dice = [GoldenRigidDie((index - 1) * GoldenRigidDie.EDGE * 1.4, value)
                     for index, value in enumerate(values)]
        self.color = (239, 187, 57)
        self.origin = self.velocity = (0., 0., 0.)
        self.collision_count = 0
        self.durations = []
        self.randomize_positions()

    def randomize_positions(self):
        """Place all three cubes flat with independent positions and headings."""
        for _ in range(256):
            for die in self.dice:
                angle = self.rng.uniform(0, math.tau)
                radius = math.sqrt(self.rng.random())*(self.RADIUS-die.EDGE)
                die.p = (radius*math.cos(angle), radius*math.sin(angle), die.HALF)
                die.q = _gd_rotate(die.q, (0., 0., 1.), self.rng.uniform(0, math.tau))
                die.v = die.omega = (0., 0., 0.)
            if (self.landing_error() is None
                    and all(_gd_overlap(a, b) is None for a, b in combinations(self.dice, 2))):
                return
        # A bounded fallback still has random heading and preserves rolled faces.
        heading = self.rng.uniform(0, math.tau)
        for index, die in enumerate(self.dice):
            angle = heading + index * math.tau / self.DICE_COUNT
            radius = die.EDGE * 1.3
            die.p = (radius * math.cos(angle), radius * math.sin(angle), die.HALF)
            die.q = _gd_rotate(die.q, (0., 0., 1.), heading)

    def landing_error(self):
        """Accept up to 8 degrees and the corresponding small contact errors.

        Screen-space overlap is a camera effect, not a failed physical landing.
        Keep genuine stacks and deep intersections distinct from tiny contacts.
        """
        for die in self.dice:
            vertices = [self.local(p) for p in die.vertices()]
            if die.top_face() is None or abs(min(p[2] for p in vertices)) > die.CONTACT_TOLERANCE:
                return '骰子未平放'
            if any((x*x+y*y)/self.RADIUS**2 + max(0.,z)**2/self.HEIGHT**2 > 1.0001
                   for x,y,z in vertices):
                return '骰子超出底盘'
        for a, b in combinations(self.dice, 2):
            contact = _gd_overlap(a, b)
            if contact is not None and contact[1] > min(a.CONTACT_TOLERANCE,b.CONTACT_TOLERANCE):
                return '骰子重叠'
        return None

    def begin(self):
        # Fast upright directional shakes. No bowl flips or inverted holds.
        count = self.rng.randint(10, 14)
        self.durations = [self.rng.uniform(.18, .25) for _ in range(count)]
        self.strokes = []
        for _ in range(count):
            heading = self.rng.randrange(4)*math.pi/2+self.rng.uniform(-.45, .45)
            strength = self.rng.uniform(1.2, 1.8)
            self.strokes.append((strength*math.cos(heading), strength*math.sin(heading),
                                 self.rng.choice((-1, 1))*self.rng.uniform(1.0, 1.8),
                                 self.rng.uniform(-.012, .012), self.rng.uniform(.010, .020)))
        self.duration = sum(self.durations)
        self.collision_count = 0

    def motion(self, t):
        elapsed = 0.
        for duration, stroke in zip(self.durations, self.strokes):
            if t < elapsed+duration:
                u = max(0., (t-elapsed)/duration)
                first = math.sin(math.pi*u)**4
                second = math.sin(math.tau*u)**4
                vx, vy, snap, side, hop = stroke
                along, lateral = .030*first+.010*snap*second, side*second*1.5
                return vx*along-vy*lateral, vy*along+vx*lateral, hop*second
            elapsed += duration
        return (0., 0., 0.)

    def world(self, local):
        return _gd_add(self.origin, local)

    def local(self, world):
        return _gd_sub(world, self.origin)

    def wall_contact(self, die, point, normal, penetration):
        die.p = _gd_add(die.p, _gd_scale(normal, penetration+.0000005))
        point = _gd_add(point, _gd_scale(normal, penetration))
        radius = _gd_sub(point, die.p)
        surface = self.velocity
        relative = _gd_sub(_gd_add(die.v, _gd_cross(die.omega, radius)), surface)
        speed = _gd_dot(relative, normal)
        if speed >= 0:
            return
        rn = _gd_cross(radius, normal)
        impulse = -(1.25 if speed < -.2 else 1.)*speed/(1+die.INVERSE_INERTIA*_gd_dot(rn, rn))
        die.impulse(_gd_scale(normal, impulse), point)
        relative = _gd_sub(_gd_add(die.v, _gd_cross(die.omega, radius)), surface)
        tangent = _gd_sub(relative, _gd_scale(normal, _gd_dot(relative, normal)))
        if _gd_length(tangent) > 1e-10:
            direction = _gd_unit(tangent)
            effective = 1+die.INVERSE_INERTIA*_gd_length(_gd_cross(radius, direction))**2
            friction = min(.48*impulse, _gd_length(tangent)/effective)
            die.impulse(_gd_scale(direction, -friction), point)

    def contain(self, die):
        touching = False
        # Iterated vertex contacts give flat cubes a four-point floor manifold.
        for _ in range(4):
            vertices = die.vertices()
            contacts = []
            for point in vertices:
                local = self.local(point)
                if local[2] < 0:
                    normal = (0., 0., 1.)
                    contacts.append((-local[2], point, normal))
                level = (local[0]**2+local[1]**2)/self.RADIUS**2+max(0., local[2])**2/self.HEIGHT**2
                if level > 1:
                    gradient = (local[0]/self.RADIUS**2, local[1]/self.RADIUS**2,
                                max(0., local[2])/self.HEIGHT**2)
                    depth = (level-1)/(2*_gd_length(gradient))
                    normal = _gd_scale(_gd_unit(gradient), -1)
                    contacts.append((depth, point, normal))
            if not contacts:
                break
            depth, point, normal = max(contacts, key=lambda item: item[0])
            self.wall_contact(die, point, normal, depth)
            touching = True
        return touching

    def step(self, dt, t, shaking=True):
        if dt <= 0:
            return
        target = self.motion(t) if shaking else (0., 0., 0.)
        travel = _gd_length(_gd_sub(target, self.origin))
        speed = max(_gd_length(die.v)+_gd_length(die.omega)*die.HALF for die in self.dice)
        # Smaller contact steps when fast motion could cross a significant cube width.
        steps = max(1, min(8, math.ceil((travel+speed*dt)/(GoldenRigidDie.EDGE*.22))))
        h = dt/steps
        for index in range(steps):
            self._step_once(h, t-dt+(index+1)*h, shaking)

    def _step_once(self, dt, t, shaking=True):
        old_origin = self.origin
        if shaking:
            self.origin = self.motion(t)
        else:
            self.origin = (0., 0., 0.)
        self.velocity = _gd_scale(_gd_sub(self.origin, old_origin), 1/dt)
        for die in self.dice:
            die.v = _gd_add(die.v, (0., 0., -9.81*dt))
            die.p = _gd_add(die.p, _gd_scale(die.v, dt))
            die.q = _gd_rotate(die.q, die.omega, dt)
            touching = self.contain(die)
            die.omega = _gd_scale(die.omega, math.exp(-(2.8 if touching else .1)*dt))
            if touching and not shaking:
                die.v = _gd_scale(die.v, math.exp(-4*dt))
        for _ in range(2):
            collided = False
            for a, b in combinations(self.dice, 2):
                if _gd_collide_dice(a, b):
                    self.collision_count += 1
                    collided = True
            if not collided:
                break
            for die in self.dice:
                self.contain(die)
        if not shaking:
            for die in self.dice:
                die.stabilize_contact()

    def settled(self):
        return all(die.settled() for die in self.dice)

    def values(self):
        if not self.settled() or self.landing_error():
            raise ValueError('骰子尚未平稳朝上，不能读取结果')
        return [die.top_face() for die in self.dice]

    def snapshot(self):
        return {'version': 1, 'dice': [{'p': list(d.p), 'q': list(d.q)} for d in self.dice]}

    @classmethod
    def restore(cls, state):
        """Only restore three complete, flat, non-overlapping saved bodies."""
        try:
            if state.get('version') != 1 or len(state['dice']) != cls.DICE_COUNT:
                return None
            bowl = cls.__new__(cls)
            bowl.rng, bowl.color = random.SystemRandom(), (239, 187, 57)
            bowl.origin = bowl.velocity = (0.,0.,0.)
            bowl.collision_count, bowl.durations = 0, []
            bowl.dice = [GoldenRigidDie(0) for _ in range(cls.DICE_COUNT)]
            for die, data in zip(bowl.dice, state['dice']):
                die.p, die.q = tuple(map(float,data['p'])), tuple(map(float,data['q']))
                if (len(die.p) != 3 or len(die.q) != 4
                        or not all(math.isfinite(v) for v in die.p+die.q)
                        or abs(sum(v*v for v in die.q)-1) > 1e-6):
                    return None
            return bowl if bowl.settled() and bowl.landing_error() is None else None
        except (KeyError, ValueError, TypeError, AttributeError):
            return None


def _gd_bowl_mesh(bowl):
    """Current Wenzhou dome and dish, with blue, red and original gold dice."""
    solids, glass = [], []
    _depth, _up, _center, camera = _gd_view_projection()
    def face(points, color, line=None, width=.7, transparent=False, paint_depth=None):
        if len(points) >= 3:
            n = _gd_cross(_gd_sub(points[1], points[0]), _gd_sub(points[2], points[0]))
            if not transparent and _gd_dot(n, camera) <= 0:
                return
        depth = (sum(_gd_dot(point, camera) for point in points)/len(points)
                 if paint_depth is None else paint_depth)
        (glass if transparent else solids).append((depth, points, color, line, width))
        return depth
    def ring(radius, z):
        return [(radius*math.cos(k*math.tau/32), radius*math.sin(k*math.tau/32), z)
                for k in range(32)]
    def band(a, b, color):
        for k in range(32):
            j = (k+1)%32
            shade = .86+.14*math.cos(k*math.tau/32-2.2)
            rgb = tuple(round(v*shade) for v in color)+(255,)
            face([bowl.world(p) for p in (a[k], b[k], b[j], a[j])], rgb)
    profile = [(radius * GD_BOWL_SCALE, z * GD_BOWL_SCALE) for radius, z in
               ((.083, 0.), (.088, .005), (.093, .002), (.094, -.007),
                (.092, -.014), (.083, -.020))]
    rings = [ring(radius, z) for radius, z in profile]
    for k in range(32):
        j = (k+1)%32
        face([bowl.world(p) for p in ((0.,0.,0.), rings[0][k], rings[0][j])], (248,234,197,255))
        face([bowl.world(p) for p in ((0.,0.,-.020*GD_BOWL_SCALE), rings[-1][j], rings[-1][k])], (142,111,70,255))
    for a,b,color in zip(rings,rings[1:],((187,151,99),(255,231,176),(191,158,107),(243,215,156),(148,117,75))):
        band(a,b,color)
    # The dish is below the bodies. Sorting its large triangles against the
    # small cube faces by average depth can paint the dish over a resting die.
    # Keep the whole support surface behind the dice, with glass in front.
    dish = sorted(solids,key=lambda f:f[0])
    solids = []
    for die, color, pip_color in zip(bowl.dice, GD_DICE_COLORS, GD_DICE_PIP_COLORS):
        for number, normal, u, v in GD_CUBE_FACES:
            n = _gd_qvector(die.q, normal)
            if _gd_dot(n, camera) <= 0:
                continue
            def cube_point(x, y, z=die.HALF):
                return _gd_add(die.p, _gd_qvector(die.q, _gd_add(_gd_scale(normal,z),
                             _gd_add(_gd_scale(u,x), _gd_scale(v,y)))))
            corners = [cube_point(x*die.HALF,y*die.HALF) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))]
            lighting = .72+.28*max(0., _gd_dot(n, _gd_unit((-.4,.5,1.))))
            shade = lighting
            rgb = tuple(round(channel*shade) for channel in color)+(255,)
            rim = tuple(round(channel*.55) for channel in color)+(255,)
            face_depth = face(corners, rgb, rim, .35)
            for px, py in GD_PIPS[number]:
                centerx, centery = px*die.EDGE*.27, py*die.EDGE*.27
                dot = [cube_point(centerx+math.cos(k*math.tau/10)*die.EDGE*.085,
                                  centery+math.sin(k*math.tau/10)*die.EDGE*.085,
                                  die.HALF+.00008) for k in range(10)]
                # Keep a face and all its pips in one stable paint group. Sorting
                # each pip by its own centre lets the parent face cover far pips
                # as the cube turns, incorrectly changing the apparent number.
                face(dot, pip_color, paint_depth=face_depth)
    raised = 0.
    levels = 12
    rings = [ring(bowl.RADIUS*math.cos(j/levels*math.pi/2),
                  bowl.HEIGHT*math.sin(j/levels*math.pi/2)+raised) for j in range(levels+1)]
    for j in range(levels):
        for k in range(32):
            n = (k+1)%32
            face([bowl.world(p) for p in (rings[j][k],rings[j][n],rings[j+1][n],rings[j+1][k])],
                 (166,214,202,18), transparent=True)
    for z,radius,color,width in ((raised,bowl.RADIUS,(225,248,237,220),1.2),
                                (raised+.002*GD_BOWL_SCALE,.086*GD_BOWL_SCALE,(168,207,194,185),.6)):
        rim = ring(radius,z)
        for k in range(32):
            face([bowl.world(rim[k]),bowl.world(rim[(k+1)%32])],None,color,width,True)
    for azimuth,color,width in ((-2.4,(242,255,249,220),1.2),(.55,(219,246,235,160),.8)):
        curve = []
        for k in range(22):
            a = .10+1.28*k/21
            curve.append(bowl.world((bowl.RADIUS*math.cos(a)*math.cos(azimuth),
                                     bowl.RADIUS*math.cos(a)*math.sin(azimuth),
                                     bowl.HEIGHT*math.sin(a)+raised+.0005*GD_BOWL_SCALE)))
        for k in range(len(curve)-1):
            face(curve[k:k+2],None,color,width,True)
    return dish + sorted(solids,key=lambda f:f[0]), sorted(glass,key=lambda f:f[0])


def _gd_project(point, bowl):
    # The real bowl translation drives physics. Its screen travel is reduced to
    # fit the betting area, applied identically to glass, dish and dice.
    point = _gd_sub(point, _gd_scale(bowl.origin, .78))
    return (98*GD_BOWL_SCALE+point[0]*680,
            96*GD_BOWL_SCALE+(point[1]*GD_VIEW_DEPTH-point[2]*GD_VIEW_UP)*680)


def _gd_render_bowl(bowl):
    """Antialiased image of the same geometry used by contact and scoring."""
    size, aa = (round(196*GD_BOWL_SCALE), round(138*GD_BOWL_SCALE)), 3
    picture = Image.new('RGBA', (size[0]*aa, size[1]*aa))
    for meshes in _gd_bowl_mesh(bowl):
        layer = Image.new('RGBA', picture.size)
        draw = ImageDraw.Draw(layer)
        for _depth, points, color, line, width in meshes:
            projected = [(x*aa,y*aa) for x,y in (_gd_project(p,bowl) for p in points)]
            if color:
                draw.polygon(projected, fill=color)
            if line:
                draw.line(projected+([projected[0]] if len(points)>2 else []),
                          fill=line,width=max(1,round(width*aa)))
        picture.alpha_composite(layer)
    return picture.resize(size, Image.Resampling.LANCZOS)



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
class PaiGowArtwork:
    SELECT_BORDER = GOLD
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
    def _ordinary_zero_copy(a, b):
        return (
            a.category == 1 and b.category == 1 and
            a.primary == 0 and b.primary == 0
        )


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
        """经典牌九图解玩法说明（对齐温州最新风格：奶油白 + 左导航 + 右内容 + 固定 1000×650）。"""
        parent = self.winfo_toplevel()

        existing = getattr(self, '_classic_instruction_window', None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass

        dialog = tk.Toplevel(parent)
        self._classic_instruction_window = dialog
        dialog.title('经典牌九 · 完整图解玩法与32张骨牌')
        dialog.configure(bg='#faf5e8')
        dialog.resizable(False, False)
        dialog.transient(parent)

        # ================================================================
        # 固定窗口尺寸
        # ================================================================
        win_w, win_h = 1000, 650

        parent.update_idletasks()
        pw = max(1, parent.winfo_width())
        ph = max(1, parent.winfo_height())
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pos_x = px + (pw - win_w) // 2
        pos_y = py + (ph - win_h) // 2

        dialog.geometry(f'{win_w}x{win_h}+{pos_x}+{pos_y}')
        dialog.minsize(win_w, win_h)
        dialog.maxsize(win_w, win_h)

        font_name = 'Arial'

        # ================================================================
        # 配色：奶油白体系
        # ================================================================
        BG = '#faf5e8'
        HEADER = '#f1e7cd'
        SIDEBAR = '#f2e8d0'
        PANEL = '#fffdf7'
        PANEL_2 = '#f5ecd6'
        ROW_ALT = '#faf3e3'
        BORDER = '#c9b88a'

        GOLD_BAR = '#e7d36c'
        GOLD = '#a8842c'
        TEXT = '#3a2f1e'
        MUTED = '#7a6a50'

        GREEN = '#2f7d3a'
        RED = '#b83a3a'
        BLUE = '#2c6e9f'

        FONT_SMALL = 14
        FONT_NORMAL = 14
        FONT_MEDIUM = 16
        FONT_LARGE = 20
        FONT_TITLE = 20

        # ================================================================
        # 顶部标题栏
        # ================================================================
        header = tk.Frame(dialog, bg=HEADER, height=76)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header, text='经典牌九 · 完整图解说明',
            font=(font_name, FONT_TITLE, 'bold'), fg=GOLD, bg=HEADER,
        ).place(x=22, y=8)
        tk.Label(
            header, text='32张骨牌 · 三骰八手 · 对子排名 · 特殊组合 · House Way',
            font=(font_name, FONT_SMALL), fg=MUTED, bg=HEADER,
        ).place(x=23, y=44)

        close_btn = tk.Button(
            header, text='关闭  ESC',
            font=(font_name, FONT_SMALL, 'bold'),
            bg='#e5d9b8', fg=TEXT,
            activebackground='#d4c090', activeforeground='#3a2f1e',
            relief=tk.FLAT, bd=0, cursor='hand2',
        )
        close_btn.place(x=860, y=17, width=118, height=42)

        tk.Frame(dialog, bg=GOLD_BAR, height=3).pack(fill=tk.X, side=tk.TOP)

        # ================================================================
        # 主体：左 sidebar + 右 content
        # ================================================================
        body = tk.Frame(dialog, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        sidebar_w = 200
        sidebar = tk.Frame(body, bg=SIDEBAR, width=sidebar_w)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Frame(body, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(
            sidebar, text='主题',
            font=(font_name, FONT_SMALL, 'bold'),
            fg=GOLD, bg=SIDEBAR, anchor='w',
        ).pack(fill=tk.X, padx=16, pady=(16, 8))

        right_wrap = tk.Frame(body, bg=BG)
        right_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_wrap.grid_rowconfigure(0, weight=1)
        right_wrap.grid_columnconfigure(0, weight=1)
        right_wrap.grid_columnconfigure(1, weight=0)

        content_canvas = tk.Canvas(
            right_wrap, bg=BG, highlightthickness=0, bd=0, yscrollincrement=40,
        )
        content_scrollbar = tk.Scrollbar(
            right_wrap, orient=tk.VERTICAL,
            command=content_canvas.yview,
            bg='#e5d9b8', troughcolor='#f0e6cc',
            activebackground=GOLD_BAR, relief=tk.FLAT, bd=0, width=11,
        )
        content_canvas.configure(yscrollcommand=content_scrollbar.set)
        content_canvas.grid(row=0, column=0, sticky='nsew', padx=(0, 4), pady=(6, 6))
        content_scrollbar.grid(row=0, column=1, sticky='ns', padx=(0, 8), pady=(6, 6))

        content = tk.Frame(content_canvas, bg=BG)
        content_window = content_canvas.create_window((0, 0), window=content, anchor='nw')

        def _sync_scrollregion(_event=None):
            content_canvas.configure(scrollregion=content_canvas.bbox('all'))

        def _fit_content_width(event):
            content_canvas.itemconfigure(content_window, width=event.width)

        content.bind('<Configure>', _sync_scrollregion)
        content_canvas.bind('<Configure>', _fit_content_width)

        def _on_mousewheel(event):
            try:
                units = int(-1 * (event.delta / 120))
            except Exception:
                units = 0
            if units:
                content_canvas.yview_scroll(units, 'units')
            return 'break'

        dialog.bind('<MouseWheel>', _on_mousewheel)
        dialog.bind('<Button-4>', lambda _e: content_canvas.yview_scroll(-1, 'units'))
        dialog.bind('<Button-5>', lambda _e: content_canvas.yview_scroll(1, 'units'))

        # ================================================================
        # 排版辅助
        # ================================================================
        def clear_content():
            for child in content.winfo_children():
                child.destroy()

        def reset_scroll():
            try:
                content_canvas.yview_moveto(0.0)
            except tk.TclError:
                pass

        def section_title(text, subtitle=None):
            block = tk.Frame(content, bg=BG)
            block.pack(fill=tk.X, padx=16, pady=(12, 0))
            tk.Label(
                block, text=text,
                font=(font_name, FONT_LARGE, 'bold'),
                fg=GOLD, bg=BG, anchor='w',
            ).pack(side=tk.LEFT)
            if subtitle:
                tk.Label(
                    block, text=subtitle,
                    font=(font_name, FONT_SMALL),
                    fg=MUTED, bg=BG, anchor='e',
                ).pack(side=tk.RIGHT)
            tk.Frame(content, bg=BORDER, height=1).pack(fill=tk.X, padx=16, pady=(8, 12))

        def make_card(title=None, subtitle=None, pady=(0, 14)):
            card = tk.Frame(
                content, bg=PANEL,
                highlightbackground=BORDER, highlightcolor=BORDER,
                highlightthickness=1, bd=0,
            )
            card.pack(fill=tk.X, padx=16, pady=pady)
            if title:
                head = tk.Frame(card, bg=PANEL)
                head.pack(fill=tk.X, padx=16, pady=(12, 8))
                tk.Label(
                    head, text=title,
                    font=(font_name, FONT_MEDIUM, 'bold'),
                    fg=GOLD, bg=PANEL, anchor='w',
                ).pack(side=tk.LEFT)
                if subtitle:
                    tk.Label(
                        head, text=subtitle,
                        font=(font_name, FONT_SMALL),
                        fg=MUTED, bg=PANEL, anchor='e',
                    ).pack(side=tk.RIGHT)
            return card

        def add_rule(parent_frame, title, body, accent=GOLD):
            row_wrap = tk.Frame(parent_frame, bg=PANEL)
            row_wrap.pack(fill=tk.X, padx=16, pady=(0, 12))
            row = tk.Frame(row_wrap, bg=PANEL)
            row.pack(fill=tk.X)
            tk.Frame(row, bg=accent, width=4).pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
            text_box = tk.Frame(row, bg=PANEL)
            text_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(
                text_box, text=title,
                font=(font_name, 15, 'bold'),
                fg=TEXT, bg=PANEL, anchor='w', justify=tk.LEFT,
            ).pack(fill=tk.X)
            tk.Label(
                text_box, text=body,
                font=(font_name, FONT_SMALL),
                fg=MUTED, bg=PANEL, anchor='w',
                justify=tk.LEFT, pady=5,
            ).pack(fill=tk.X)

        def preview_canvas(parent_frame, width, height):
            cv = tk.Canvas(
                parent_frame, width=width, height=height,
                bg=PANEL, highlightthickness=0,
            )
            cv.pack(padx=12, pady=(4, 12))
            return cv

        # 奶油白底上用黑色牌面
        def draw_tile_on(canvas, tile, cx, cy, scale=0.55, horizontal=False, outline=False):
            old = self._render_tile_theme_override
            self._render_tile_theme_override = 'black'
            try:
                return self._instruction_tile(
                    canvas, tile, cx, cy,
                    horizontal=horizontal, scale=scale, outline=outline,
                )
            finally:
                self._render_tile_theme_override = old

        def draw_die(cv, cx, cy, value, size=52):
            r = size / 2
            x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
            cv.create_rectangle(x0, y0, x1, y1, fill='#faf8f0', outline='#4a3c20', width=2)
            positions = {
                1: [(0.50, 0.50)],
                2: [(0.28, 0.28), (0.72, 0.72)],
                3: [(0.28, 0.28), (0.50, 0.50), (0.72, 0.72)],
                4: [(0.28, 0.28), (0.72, 0.28), (0.28, 0.72), (0.72, 0.72)],
                5: [(0.28, 0.28), (0.72, 0.28), (0.50, 0.50),
                    (0.28, 0.72), (0.72, 0.72)],
                6: [(0.28, 0.20), (0.72, 0.20), (0.28, 0.50),
                    (0.72, 0.50), (0.28, 0.80), (0.72, 0.80)],
            }
            pip_r = max(3, int(size / 11))
            pip_color = '#c0392b' if value in (1, 4) else '#2a2218'
            for ux, uy in positions[value]:
                ppx, ppy = x0 + ux * size, y0 + uy * size
                cv.create_oval(ppx - pip_r, ppy - pip_r, ppx + pip_r, ppy + pip_r,
                            fill=pip_color, outline='')

        CANVAS_W = 680

        # ================================================================
        # 数据准备
        # ================================================================
        tiles = build_pai_gow_set()
        by_group = {}
        for _t in tiles:
            by_group.setdefault(_t.group, []).append(_t)

        ranked_groups = sorted(
            by_group,
            key=lambda g: min(t.pair_rank for t in by_group[g]),
        )

        def find_ordinary(points, exclude_teen_day=True):
            for i, a in enumerate(tiles):
                for b in tiles[i + 1:]:
                    v = evaluate_hand([a, b])
                    if v.category != 1 or v.primary != points:
                        continue
                    if exclude_teen_day and (a.group in ('Teen', 'Day') or b.group in ('Teen', 'Day')):
                        continue
                    return [a, b]
            if exclude_teen_day:
                return find_ordinary(points, exclude_teen_day=False)
            return None

        # ================================================================
        # 各主题页面
        # ================================================================
        def page_rules():
            section_title('玩法与流程', '下注 → 摇骰 → 派牌 → 分牌 → 结算')

            card = make_card(title='一局完整流程')
            add_rule(
                card, '1. 下注',
                '只有底注，没有边注。每席底注最低 $10，最高 $25,000。\n'
                '七席共用账户余额；全胜净赔率0.95 : 1（抽水5%）。'
            )
            add_rule(
                card, '2. 摇三骰',
                '按下【开牌】后摇三颗骰子。\n'
                '三骰总点数 - 1，再 mod 8，得到第 0~7 个起始位置。\n'
                '8 个位置 = 庄家 + 玩家1至玩家7，全部参与派牌。'
            )
            add_rule(
                card, '3. 派牌',
                '牌靴共 32 张，排成 16 栋 × 每栋 2 张。\n'
                '每相邻 2 栋合成一手 4 张。\n'
                '32张牌全部派往八个位置，每席四张；\n'
                '未下注席位照常发牌，任何阶段都不翻开，也不计结算。'
            )
            add_rule(
                card, '4. 玩家分牌',
                '每个下注席收到4张后，点击两张作为【前道】。\n'
                '剩余 2 张自动成为【后道】。\n'
                '先点【全部自动分牌】，再点【全部确定分牌】提交。前道横放在上方；\n'
                '后道 2 张保持直立并排。后道必须 ≥ 前道。'
            )
            add_rule(
                card, '5. 庄家分牌',
                '庄家保持盖牌，等全部下注席确认后才开牌。\n'
                '庄家自动按传统 House Way 分牌。'
            )
            add_rule(
                card, '6. 结算',
                '玩家前道 vs 庄家前道；玩家后道 vs 庄家后道。\n'
                '每道必须严格大于庄家才算赢。\n'
                '两道全赢 → 玩家赢（赢 0.95 : 1）；\n'
                '一胜一负 → Push 平局（退回底注）；\n'
                '两道都没赢 → 庄家赢（底注输）。'
            )
            add_rule(
                card, '7. 换牌靴',
                '点击【再来一局】后，先收回本金与盈利，全部到位后入账；\n'
                '桌面骨牌向右收走，再更换新的32张牌靴。\n'
                '牌面颜色在黑色 / 白色之间交替。'
            )

        def page_dice():
            section_title('三骰与派牌位置', '总点数决定第几个位置先派')

            card = make_card(title='三骰定派牌起手位')
            # 上下结构：上部三骰 + 结果，下部 8 个位置
            cv = preview_canvas(card, CANVAS_W, 360)

            # ---- 上半区：三骰 + 计算 ----
            draw_die(cv, 280, 55, 2)
            draw_die(cv, 340, 55, 5)
            draw_die(cv, 400, 55, 6)

            cv.create_text(340, 118, text='2 + 5 + 6 = 13点',
                        font=(font_name, FONT_LARGE, 'bold'), fill=TEXT)
            cv.create_text(340, 148,
                        text='(13 - 1) mod 8 = 4 → 第 5 个位置先派',
                        font=(font_name, FONT_NORMAL, 'bold'), fill=BLUE)

            # 分隔线
            cv.create_line(60, 178, 620, 178, fill=BORDER, width=1)

            # ---- 下半区：8 个位置分两排 ----
            positions = ['庄家', '1号位', '2号位', '3号位',
                        '4号位', '5号位', '6号位', '7号位']
            cell_w = 140
            gap = 10
            for i, name in enumerate(positions):
                row = i // 4
                col = i % 4
                x0 = 40 + col * (cell_w + gap)
                y0 = 205 + row * 72
                highlight = (i == 4)  # 5号位先派
                fill = '#f6e2a8' if highlight else '#faf3e0'
                edge = GOLD if highlight else BORDER
                cv.create_rectangle(x0, y0, x0 + cell_w, y0 + 58,
                                    fill=fill, outline=edge,
                                    width=2 if highlight else 1)
                cv.create_text(x0 + cell_w / 2, y0 + 20, text=name,
                            font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)
                cv.create_text(x0 + cell_w / 2, y0 + 42, text=f'序号 {i + 1}',
                            font=(font_name, 14), fill=MUTED)

        def page_tiles():
            section_title('一副经典牌九 · 32张骨牌', '16种对子 × 每种2张')

            card = make_card()
            cols = 3
            cell_w = 230
            cell_h = 165
            rows = (len(ranked_groups) + cols - 1) // cols
            cv = preview_canvas(card, cols * cell_w + 10, rows * cell_h + 10)

            for idx, group in enumerate(ranked_groups):
                row, col = divmod(idx, cols)
                x0 = 5 + col * cell_w
                y0 = 5 + row * cell_h

                pair = by_group[group][:2]
                rank = pair[0].pair_rank

                cv.create_rectangle(x0, y0, x0 + cell_w - 10, y0 + cell_h - 10,
                                    fill=PANEL_2, outline=BORDER)

                draw_tile_on(cv, pair[0], x0 + 45, y0 + 85, scale=0.62)
                draw_tile_on(cv, pair[1], x0 + 90, y0 + 85, scale=0.62)

                short = self.PAIR_SHORT_NAMES.get(group, group)
                cv.create_text(x0 + 130, y0 + 28, anchor='w',
                            text=f'{rank:02d}. {short}',
                            font=(font_name, FONT_SMALL, 'bold'), fill=GOLD)
                cv.create_text(x0 + 130, y0 + 58, anchor='w',
                            text='共2张', font=(font_name, 14), fill=MUTED)
                shapes = ' + '.join(f'{t.a}-{t.b}' for t in pair)
                cv.create_text(x0 + 130, y0 + 86, anchor='w',
                            text=shapes, font=(font_name, 14), fill=MUTED)
                identical = pair[0].shape == pair[1].shape
                cv.create_text(x0 + 130, y0 + 114, anchor='w',
                            text='相同双牌' if identical else '不同点阵成对',
                            font=(font_name, 14),
                            fill=GREEN if identical else BLUE)

            note = make_card(title='牌面构成')
            add_rule(
                note, '21 种牌面 · 32 张实体牌',
                '11 种牌面各出现 2 次（文牌对）；\n'
                '10 种牌面各出现 1 次（武牌对，含至尊的两张不同形状）。\n'
                '所以是 11×2 + 10×1 = 32 张。'
            )

        def page_ranks():
            section_title('完整牌型表', '由高到低 · 32 级')

            # ============================================================
            # 构造完整 32 级行数据
            # ============================================================
            row_data = []

            # 1~16 级：16 种对子
            for group in ranked_groups:
                pair = by_group[group][:2]
                rank = pair[0].pair_rank
                short = self.PAIR_SHORT_NAMES.get(group, group)
                identical = pair[0].shape == pair[1].shape
                row_data.append({
                    'rank': rank,
                    'name': short,
                    'hand': pair,
                    'comp': ' + '.join(f'{t.a}-{t.b}' for t in pair),
                    'note': '两张相同' if identical else '两张点阵不同',
                    'kind': 'pair',
                })

            # 17~22 级：6 种特殊组合
            teen = self._instruction_find_tile(tiles, group='Teen')
            day = self._instruction_find_tile(tiles, group='Day')
            nine = self._instruction_find_tile(tiles, dots=9)
            eight = self._instruction_find_tile(tiles, dots=8)
            seven = self._instruction_find_tile(tiles, dots=7)

            specials = [
                ('天王', teen, nine, '天牌 + 9 点牌'),
                ('地王', day, nine, '地牌 + 9 点牌'),
                ('天杠', teen, eight, '天牌 + 8 点牌'),
                ('地杠', day, eight, '地牌 + 8 点牌'),
                ('天高九', teen, seven, '天牌 + 7 点牌'),
                ('地高九', day, seven, '地牌 + 7 点牌'),
            ]
            for idx, (name, base, other, note) in enumerate(specials):
                row_data.append({
                    'rank': 17 + idx,
                    'name': name,
                    'hand': [base, other],
                    'comp': f'{base.a}-{base.b} + {other.a}-{other.b}',
                    'note': note,
                    'kind': 'special',
                })

            # 23~32 级：普通 9 → 0 点
            for pts in range(9, -1, -1):
                hand = find_ordinary(pts)
                if not hand:
                    continue
                row_data.append({
                    'rank': 23 + (9 - pts),
                    'name': f'普通 {pts} 点',
                    'hand': hand,
                    'comp': f'{hand[0].dots} + {hand[1].dots}',
                    'note': '两张点数相加取个位',
                    'kind': 'ordinary',
                })

            # ============================================================
            # 绘制表格
            # ============================================================
            card = make_card(title='完整牌型表（32 级 · 由高到低）')

            row_h = 34
            header_h = 34
            table_w = 640
            table_x = (CANVAS_W - table_w) / 2
            table_y0 = 10

            canvas_h = table_y0 + header_h + len(row_data) * row_h + 16
            cv = preview_canvas(card, CANVAS_W, canvas_h)

            # 列宽：级别 / 牌型 / 示例 / 组成 / 说明
            col_w = [46, 92, 138, 132, 232]
            col_x = [table_x]
            for w in col_w[:-1]:
                col_x.append(col_x[-1] + w)

            # 表头
            headers = ['级别', '牌型', '示例', '组成', '说明']
            for i, h in enumerate(headers):
                x0 = col_x[i]
                x1 = x0 + col_w[i]
                cv.create_rectangle(x0, table_y0, x1, table_y0 + header_h,
                                    fill=GOLD_BAR, outline=BORDER)
                cv.create_text((x0 + x1) / 2, table_y0 + header_h / 2,
                            text=h, font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)

            # 数据行
            old_theme = self._render_tile_theme_override
            self._render_tile_theme_override = 'black'
            try:
                for idx, row in enumerate(row_data):
                    y0 = table_y0 + header_h + idx * row_h
                    y1 = y0 + row_h
                    cy = (y0 + y1) / 2
                    bg = ROW_ALT if idx % 2 == 0 else PANEL

                    # 单元格背景
                    for i, w in enumerate(col_w):
                        cv.create_rectangle(col_x[i], y0, col_x[i] + w, y1,
                                            fill=bg, outline=BORDER)

                    # 级别
                    cv.create_text(col_x[0] + col_w[0] / 2, cy, text=str(row['rank']),
                                font=(font_name, FONT_SMALL, 'bold'), fill=GOLD)

                    # 牌型名
                    kind_color = {'pair': GOLD, 'special': RED, 'ordinary': TEXT}
                    cv.create_text(col_x[1] + col_w[1] / 2, cy, text=row['name'],
                                font=(font_name, FONT_SMALL, 'bold'),
                                fill=kind_color.get(row['kind'], TEXT))

                    # 示例：两张水平旋转的迷你骨牌
                    sample_cx = col_x[2] + col_w[2] / 2
                    gap = 70
                    self._instruction_tile(
                        cv, row['hand'][0], sample_cx - gap / 2, cy,
                        horizontal=True, scale=0.14,
                    )
                    self._instruction_tile(
                        cv, row['hand'][1], sample_cx + gap / 2, cy,
                        horizontal=True, scale=0.14,
                    )

                    # 组成
                    cv.create_text(col_x[3] + col_w[3] / 2, cy, text=row['comp'],
                                font=(font_name, FONT_SMALL), fill=MUTED)

                    # 说明
                    cv.create_text(col_x[4] + 8, cy, anchor='w', text=row['note'],
                                font=(font_name, FONT_SMALL), fill=MUTED)
            finally:
                self._render_tile_theme_override = old_theme

            # 底部说明
            note = make_card(title='牌型说明')
            add_rule(
                note, '固定牌型 vs 普通点数',
                '级别 1~16 为 16 种对子，级别 17~22 为王 / 杠 / 高九。\n'
                '这两大类都固定大于所有普通点数（级别 23~32）。'
            )
            add_rule(
                note, '同类型内部比较',
                '同为对子时按 1~16 的顺序；同为特殊组合时，\n'
                '天王 > 地王，天杠 > 地杠，天高九 > 地高九。'
            )
            add_rule(
                note, '普通点数同点',
                '点数相同时比较该道中单张等级最高的骨牌；\n'
                '仍相同则本道判 Copy（庄家胜该道）。',
                accent=RED,
            )

        def page_special():
            section_title('特殊组合', '天牌 / 地牌 + 9 / 8 / 7')

            teen = self._instruction_find_tile(tiles, group='Teen')
            day = self._instruction_find_tile(tiles, group='Day')
            nine = self._instruction_find_tile(tiles, dots=9)
            eight = self._instruction_find_tile(tiles, dots=8)
            seven = self._instruction_find_tile(tiles, dots=7)

            card = make_card(title='王 / 杠 / 高九 是怎样组成的')
            cv = preview_canvas(card, CANVAS_W, 500)

            rows = [
                ('天王', teen, nine, '天牌 + 任意 9 点牌'),
                ('天杠', teen, eight, '天牌 + 任意 8 点牌'),
                ('天高九', teen, seven, '天牌 + 任意 7 点牌'),
                ('地王', day, nine, '地牌 + 任意 9 点牌'),
                ('地杠', day, eight, '地牌 + 任意 8 点牌'),
                ('地高九', day, seven, '地牌 + 任意 7 点牌'),
            ]

            for i, (name, base, other, desc) in enumerate(rows):
                row, col = divmod(i, 2)
                x0 = 10 + col * 330
                y0 = 10 + row * 162

                cv.create_rectangle(x0, y0, x0 + 320, y0 + 152,
                                    fill=PANEL_2, outline=BORDER)

                cv.create_text(x0 + 160, y0 + 24, text=name,
                            font=(font_name, FONT_LARGE, 'bold'), fill=RED)

                draw_tile_on(cv, base, x0 + 55, y0 + 82, scale=0.55)
                cv.create_text(x0 + 100, y0 + 82, text='+',
                            font=('Arial', 16, 'bold'), fill=TEXT)
                draw_tile_on(cv, other, x0 + 150, y0 + 82, scale=0.55)
                cv.create_text(x0 + 200, y0 + 82, text='=',
                            font=('Arial', 16, 'bold'), fill=TEXT)
                cv.create_text(x0 + 262, y0 + 82, text=name,
                            font=(font_name, FONT_MEDIUM, 'bold'), fill=RED)

                cv.create_text(x0 + 160, y0 + 132, text=desc,
                            font=(font_name, 14), fill=MUTED)

            note = make_card(title='重要提示')
            add_rule(
                note, '9 / 8 / 7 是原始点数',
                '这里指另一张骨牌本身的原始点数和（如 3-6 = 9 点）。\n'
                '不是两张相加后取个位的结果。'
            )
            add_rule(
                note, '至尊不能组成王 / 杠 / 高九',
                '至尊的两张牌（2-4 = 6 点，1-2 = 3 点）虽然可单独使用，\n'
                '但不能与天牌 / 地牌搭配成特殊组合。'
            )

        def page_points():
            section_title('普通点数与比牌', '相加取个位 · 同点比单张')

            card = make_card(title='普通 0～9 点')
            cv = preview_canvas(card, CANVAS_W, 230)

            for i, pts in enumerate((9, 7, 0)):
                hand = find_ordinary(pts)
                if not hand:
                    continue
                cx = 115 + i * 225
                draw_tile_on(cv, hand[0], cx - 25, 84, scale=0.58)
                draw_tile_on(cv, hand[1], cx + 25, 84, scale=0.58)
                cv.create_text(cx, 162, text=f'普通 {pts} 点',
                            font=(font_name, FONT_NORMAL, 'bold'), fill=GOLD)
                cv.create_text(cx, 190,
                            text=f'{hand[0].dots} + {hand[1].dots} → {pts}点',
                            font=(font_name, FONT_SMALL), fill=MUTED)

            note = make_card(title='天X / 地X 命名')
            add_rule(
                note, '含天牌或地牌的普通点数',
                '普通手写「X点」；含天牌写「天X」；含地牌写「地X」。\n'
                '例：「天8」= 天牌 + 一张组成 8 点的牌；\n'
                '    「地7」= 地牌 + 一张组成 7 点的牌。\n'
                '「天8 / 地8」仍然只是普通 8 点，不会高过普通 9 点。'
            )
            add_rule(
                note, '天X 也仍然只是普通点数',
                '天8 与 天9 都是普通点数；只有满足特定 7 / 8 / 9 原始\n'
                '点数的搭配，才会升级成高九 / 杠 / 王。'
            )

            note2 = make_card(title='同点比较顺序')
            add_rule(note2, '第一步：比点数',
                    '普通点数先比大小。')
            add_rule(note2, '第二步：比最大单张',
                    '点数相同时，比较该道中单张等级最高的骨牌。\n'
                    '单张等级（高 → 低）：天 > 地 > 人 > 鹅 >\n'
                    '梅 / 长三 / 板凳 > 斧头 / 红头十 / 长脚七 / 大头六 >\n'
                    '杂九 / 杂八 / 杂七 / 杂五。')
            add_rule(note2, '第三步：Copy',
                    '点数相同、最大单张等级也相同时，本道判 Copy（庄家胜该道）。',
                    accent=RED)
            add_rule(note2, '特殊：普通 0 点相同',
                    '只要有一道出现「玩家普通0点 vs 庄家普通0点」，\n'
                    '庄家直接赢整局，不允许另一道把结果变成 Push。',
                    accent=RED)

        def page_houseway():
            section_title('House Way', '4张只有 3 种两两配对')

            card = make_card(title='3 种可能的分法')
            cv = preview_canvas(card, CANVAS_W, 330)

            teen = self._instruction_find_tile(tiles, group='Teen')
            nine = self._instruction_find_tile(tiles, dots=9)
            eight = self._instruction_find_tile(tiles, dots=8)
            seven = self._instruction_find_tile(tiles, dots=7)

            demo = [teen, nine, eight, seven]

            cv.create_text(50, 30, anchor='w', text='原始 4 张：',
                        font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)
            for i, t in enumerate(demo):
                draw_tile_on(cv, t, 130 + i * 68, 60, scale=0.55)

            cv.create_text(CANVAS_W / 2, 108,
                        text='↓  4 张牌分成 2+2，只有 3 种分法  ↓',
                        font=(font_name, FONT_SMALL, 'bold'), fill=BLUE)

            pairings = [
                ((0, 1), (2, 3), '方案 1'),
                ((0, 2), (1, 3), '方案 2'),
                ((0, 3), (1, 2), '方案 3'),
            ]

            for i, (p1, p2, label) in enumerate(pairings):
                y = 158 + i * 56
                x0 = 40
                x1 = CANVAS_W - 40

                cv.create_rectangle(x0, y - 25, x1, y + 25,
                                    fill=PANEL_2, outline=BORDER)

                cv.create_text(x0 + 25, y, anchor='w', text=label,
                            font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)

                hand1 = [demo[p1[0]], demo[p1[1]]]
                hand2 = [demo[p2[0]], demo[p2[1]]]

                draw_tile_on(cv, hand1[0], x0 + 105, y, scale=0.32)
                draw_tile_on(cv, hand1[1], x0 + 130, y, scale=0.32)
                cv.create_text(x0 + 160, y, anchor='w',
                            text=f'→ {self._display_hand_name(hand1)}',
                            font=(font_name, FONT_SMALL), fill=BLUE)

                cv.create_text(x0 + 340, y, text='｜',
                            font=('Arial', 14, 'bold'), fill=TEXT)

                draw_tile_on(cv, hand2[0], x0 + 385, y, scale=0.32)
                draw_tile_on(cv, hand2[1], x0 + 410, y, scale=0.32)
                cv.create_text(x0 + 440, y, anchor='w',
                            text=f'→ {self._display_hand_name(hand2)}',
                            font=(font_name, FONT_SMALL), fill=GOLD)

            note = make_card(title='House Way 优先级')
            add_rule(
                note, '1. 先处理对子',
                '两组对子 → 不拆；一组对子 → 按传统规则决定是否拆。'
            )
            add_rule(
                note, '2. 再看王 / 杠 / 高九',
                '如果 3 种方案里有能组成王、杠、高九的，优先选择这些组合。'
            )
            add_rule(
                note, '3. 最后平衡两道',
                '普通牌之间，尽量兼顾前道和后道的强度；\n'
                '不是简单地把最大的两张放后道。'
            )

        def page_settle():
            section_title('结算与换牌靴', '绿 = 赢；红 = 输；白 = Copy')

            card = make_card(title='每道独立的颜色')
            cv = preview_canvas(card, CANVAS_W, 150)

            colors = [
                ('赢该道', '#00ff00', '#10210f', 50),
                ('输该道', '#ff0000', 'white', 240),
                ('Copy', '#ffffff', '#222', 430),
            ]
            for label, fill, fg, x in colors:
                cv.create_rectangle(x, 30, x + 160, 120,
                                    fill=fill, outline='#666', width=2)
                cv.create_text(x + 80, 75, text=label,
                            font=(font_name, FONT_LARGE, 'bold'), fill=fg)

            note = make_card(title='整局结果')
            add_rule(
                note, '玩家赢',
                '两道全胜 → 底注 × 1.95 返还（本金 + 0.95 利润）。\n'
                '例：底注 $100，总返还 $195。',
                accent=GREEN,
            )
            add_rule(
                note, 'Push 平局',
                '一胜一负 → 只退回原底注。',
                accent=BLUE,
            )
            add_rule(
                note, '庄家赢',
                '两道都没赢 → 底注输。',
                accent=RED,
            )
            add_rule(
                note, '特殊：普通 0 点相同',
                '只要有一道出现「玩家普通0点 vs 庄家普通0点」，\n'
                '庄家直接赢整局，不允许另一道把结果变成 Push。',
                accent=RED,
            )

            flow = make_card(title='「再来一局」换牌靴流程')
            add_rule(
                flow, '步骤 1',
                '输注飞向庄家；赢注本金留位，盈利另派至本金水平左侧；\n'
                'Push保留本金。点击再来一局后，筹码全部回到筹码区才入账。'
            )
            add_rule(
                flow, '步骤 2',
                '入账后骨牌整体向右收走，再展开牌靴区域并换靴。'
            )
            add_rule(
                flow, '步骤 3',
                '新牌靴就位后重新开放下注；\n'
                '牌面颜色在黑色 / 白色之间交替。'
            )

        # ================================================================
        # 左侧主题按钮
        # ================================================================
        themes = [
            ('玩法与流程',     page_rules),
            ('三骰与派牌位置', page_dice),
            ('32张骨牌图鉴',   page_tiles),
            ('完整牌型表',     page_ranks),
            ('特殊组合',       page_special),
            ('点数与比牌',     page_points),
            ('House Way',     page_houseway),
            ('结算与换牌靴',   page_settle),
        ]

        theme_buttons = {}
        current_theme = {'name': None}

        def select_theme(name):
            if current_theme['name'] == name:
                return
            current_theme['name'] = name

            for theme_name, btn in theme_buttons.items():
                active = theme_name == name
                btn.configure(
                    bg='#f0e0b8' if active else SIDEBAR,
                    fg=GOLD if active else MUTED,
                    activebackground='#e8d49a',
                    activeforeground=GOLD,
                )

            clear_content()
            for theme_name, builder in themes:
                if theme_name == name:
                    builder()
                    break

            content_canvas.update_idletasks()
            reset_scroll()

        for name, _builder in themes:
            btn = tk.Button(
                sidebar,
                text=name,
                command=lambda n=name: select_theme(n),
                font=(font_name, FONT_SMALL),
                fg=MUTED, bg=SIDEBAR,
                activebackground='#e8d49a',
                activeforeground=GOLD,
                relief=tk.FLAT,
                bd=0,
                anchor='w',
                padx=18,
                pady=10,
                cursor='hand2',
            )
            btn.pack(fill=tk.X)
            theme_buttons[name] = btn

        select_theme(themes[0][0])

        # ================================================================
        # 关闭事件
        # ================================================================
        def _close_instruction():
            try:
                self._classic_instruction_window = None
            except Exception:
                pass
            try:
                dialog.destroy()
            except tk.TclError:
                pass

        close_btn.configure(command=_close_instruction)
        dialog.protocol('WM_DELETE_WINDOW', _close_instruction)
        dialog.bind('<Escape>', lambda _e: _close_instruction())

        dialog.after(30, dialog.focus_force)


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



# ============================================================
# Seven-seat state; each player compares only with the banker.
# ============================================================
def money(value):
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def settle_pai_gow(low, high, dealer_low, dealer_high, stake):
    """Same payout and zero-copy rule as the supplied Classic Pai Gow V9."""
    pl, ph, dl, dh = map(evaluate_hand, (low, high, dealer_low, dealer_high))
    comparisons = (compare_hand_values(pl, dl), compare_hand_values(ph, dh))
    zero_copy = (PaiGowArtwork._ordinary_zero_copy(pl, dl),
                 PaiGowArtwork._ordinary_zero_copy(ph, dh))
    wins = (comparisons[0] > 0 and not (pl.category == 1 and pl.primary == 0),
            comparisons[1] > 0 and not (ph.category == 1 and ph.primary == 0))
    if any(zero_copy):
        result, returned, detail = 'lose', 0.0, '普通0点相同 · 庄家胜局'
    elif all(wins):
        result, returned, detail = 'win', money(Decimal(str(stake)) * Decimal('1.95')), '两道全胜 · 抽佣5%'
    elif any(wins):
        result, returned, detail = 'push', money(stake), '一胜一负 · 退回底注'
    else:
        result, returned, detail = 'lose', 0.0, '两道未胜 · 底注输'
    return dict(result=result, returned=returned, net=money(returned-stake),
                comparisons=comparisons, zero_copy=zero_copy, detail=detail)


class PaiGowTableGame:
    SEATS = tuple(range(1, 8))

    def __init__(self):
        self.stage = 'betting'
        self.bets = {s: 0.0 for s in self.SEATS}
        self.last_bets = None
        self.last_return = 0.0
        self.reset_hands()
        self.new_shoe()

    @staticmethod
    def shuffled_tiles():
        tiles = build_pai_gow_set()
        for i in range(len(tiles)-1, 0, -1):
            j = secrets.randbelow(i+1)
            tiles[i], tiles[j] = tiles[j], tiles[i]
        return tiles

    def reset_hands(self):
        self.hands, self.splits, self.results = {}, {}, {}
        self.selected = {s: [] for s in self.SEATS}
        self.confirmed = set()
        self.dice = []
        self.deal_order = []
        self.credited = False
        self.resolved = False

    def new_shoe(self):
        self.tiles = self.shuffled_tiles()
        self.stacks = [self.tiles[i*4:i*4+4] for i in range(8)]

    @property
    def total_bet(self):
        return money(sum(self.bets.values()))

    @property
    def active_seats(self):
        return [s for s in self.SEATS if self.bets[s] > 0]

    def add_bet(self, seat, amount, balance):
        if self.stage != 'betting' or seat not in self.SEATS:
            return False
        if amount <= 0 or self.bets[seat]+amount > MAX_ANTE:
            raise ValueError(f'每席底注上限 ${MAX_ANTE:,}')
        if self.total_bet+amount > balance:
            raise ValueError('余额不足以支付七席的合计下注。')
        self.bets[seat] = money(self.bets[seat]+amount)
        return True

    def start(self, balance):
        if self.stage != 'betting':
            raise ValueError('请先完成本局。')
        if not self.active_seats:
            raise ValueError('请先在至少一个玩家席位下注。')
        if any(not MIN_ANTE <= self.bets[s] <= MAX_ANTE for s in self.active_seats):
            raise ValueError(f'每席底注须在 ${MIN_ANTE:,} 至 ${MAX_ANTE:,} 之间。')
        if self.total_bet > balance:
            raise ValueError('余额不足。')
        self.reset_hands()
        self.last_bets = dict(self.bets)
        self.stage = 'rolling'
        return money(balance-self.total_bet)

    def deal(self, dice):
        if len(dice) != 3 or any(n not in range(1, 7) for n in dice):
            raise ValueError('需要三颗有效骰子。')
        self.dice = list(dice)
        start = (sum(dice)-1) % 8
        self.deal_order = [(start+i) % 8 for i in range(8)]
        self.hands = {seat: list(self.stacks[i]) for i, seat in enumerate(self.deal_order)}
        self.stage = 'dealing'

    def suggest(self, seat):
        if self.stage != 'setting' or seat not in self.active_seats or seat in self.confirmed:
            return
        choice = traditional_house_way(self.hands[seat])
        low_uids = {t.uid for t in choice.low}
        self.selected[seat] = [i for i, tile in enumerate(self.hands[seat]) if tile.uid in low_uids]

    def selected_split(self, seat):
        selected = self.selected[seat]
        if len(selected) != 2:
            return None
        hand = self.hands[seat]
        low = [hand[i] for i in selected]
        high = [t for i, t in enumerate(hand) if i not in selected]
        return low, high

    def confirm(self, seat):
        if self.stage != 'setting' or seat not in self.active_seats or seat in self.confirmed:
            return False
        split = self.selected_split(seat)
        if split is None:
            raise ValueError(f'玩家{seat}：请选择两张牌作为前道。')
        low, high = split
        if evaluate_hand(low).key > evaluate_hand(high).key:
            raise ValueError(f'玩家{seat}：后道必须大于或等于前道。')
        self.splits[seat] = (low, high)
        self.confirmed.add(seat)
        return True

    def ready(self):
        return bool(self.active_seats) and all(s in self.confirmed for s in self.active_seats)

    def settle(self):
        if self.resolved:
            return 0.0
        if not self.ready() or self.stage not in ('setting', 'revealing'):
            raise ValueError('所有下注席位必须先完成分牌。')
        for seat in (0, *self.active_seats):
            if seat not in self.splits:
                choice = traditional_house_way(self.hands[seat])
                self.splits[seat] = (choice.low, choice.high)
        dl, dh = self.splits[0]
        self.results = {s: settle_pai_gow(*self.splits[s], dl, dh, self.bets[s])
                        for s in self.active_seats}
        self.last_return = money(sum(r['returned'] for r in self.results.values()))
        self.resolved = True
        self.stage = 'settling'
        return self.last_return

    def next_round(self):
        if self.stage != 'sweeping' or not self.credited:
            return False
        self.reset_hands()
        self.bets = {s: 0.0 for s in self.SEATS}
        self.new_shoe()
        self.stage = 'betting'
        return True


class ClassicPaiGowGUI(tk.Frame, PaiGowArtwork):
    """UTH table shell, seven live player seats, physical two-layer tile wall."""
    WIDTH, HEIGHT = 1150, 750
    ZONE_COLORS = ('#2A5541', '#204536')
    SEAT_LEFT = 22
    SEAT_PITCH = 159
    SEAT_WIDTH = 152
    BET_CHIP_SCALE = 0.8
    PROFIT_CHIP_GAP = 10

    def __init__(self, parent, balance=10000, user='Guest', on_back=None, on_balance_change=None):
        tk.Frame.__init__(self, parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = user or 'Guest', money(balance)
        if self.username != 'Guest' and _ACCOUNT_ROOT is None:
            raise RuntimeError('请把此文件放回原项目内：正式账户需要 A_Tools/Account/secure_json.py。')
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = PaiGowTableGame()
        self.tile_theme = 'white' if secrets.randbelow(2) == 0 else 'black'
        self._render_tile_theme_override = None
        self.selected_chip = 10
        self._closing, self._jobs = False, set()
        self._dealt, self._wall_removed = set(), set()
        self._dealer_face = False
        self._moving = False
        self.golden_dice_bowl = None
        self._golden_dice_cup_photo = self._golden_dice_cup_item = None
        self._golden_dice_phase = 'idle'
        self._golden_dice_time = self._golden_dice_stable_time = 0.
        self._golden_dice_rest_anchor = None
        self._init_v2()
        self.control_buttons = {}
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self._create_widgets()
        self._refresh()
        self.bind('<Configure>', self._center_table, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')
        self._enter_binding = self.winfo_toplevel().bind('<Return>', self._enter_action, add='+')


    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or not self._idle()


    def _center_table(self, event=None):
        self.canvas.place(x=max(0, (self.winfo_width()-self.WIDTH)//2),
                          y=max(0, (self.winfo_height()-self.HEIGHT)//2),
                          width=self.WIDTH, height=self.HEIGHT)

    def _text(self, x, y, text, size=12, color=TEXT, **kw):
        return self.canvas.create_text(x, y, text=text, fill=color,
                                       font=('Arial', size, 'bold'), **kw)

    def _schedule(self, delay, callback, *args):
        def run():
            self._jobs.discard(job)
            if not self._closing:
                callback(*args)
        job = self.after(delay, run)
        self._jobs.add(job)
        return job

    def _cancel_jobs(self):
        for job in tuple(self._jobs):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._jobs.clear()

    def _on_destroy(self, event):
        if event.widget is self:
            self._closing = True
            self._cancel_jobs()
            try:
                self.winfo_toplevel().unbind('<Return>', self._enter_binding)
            except (tk.TclError, AttributeError):
                pass

    def _persist_balance(self):
        update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def on_close(self):
        if self._closing: return
        g = self.game
        self._cancel_restart()
        self._cancel_jobs()
        if g.stage != 'betting':
            if not g.resolved:
                if not g.hands: g.deal([secrets.randbelow(6)+1 for _ in range(3)])
                g.stage = 'setting'
                for seat in g.active_seats:
                    if seat not in g.confirmed:
                        g.suggest(seat)
                        g.confirm(seat)
                g.settle()
            self._credit_round_return()
        else: self._persist_balance()
        self._closing = True
        dialog = getattr(self,'_classic_instruction_window',None)
        if dialog is not None:
            try: dialog.destroy()
            except tk.TclError: pass
        try: self.winfo_toplevel().unbind('<Return>',self._enter_binding)
        except (tk.TclError,AttributeError): pass
        if callable(self.on_back): self.on_back(float(self.balance))
        else: self.winfo_toplevel().destroy()


    def _create_widgets(self):
        c = self.canvas
        self._text(187, 44, '经典牌九', 16, GOLD)
        self._text(957, 44, 'Classic Pai Gow', 14, GOLD)
        c.create_rectangle(22, 69, 349, 178, fill=ROOT_BG, outline=GOLD, width=2)
        self._text(185, 84, '下注上限', 12, PANEL_BG)
        for i, (title, value) in enumerate((('底注最低', '$10'), ('底注最高', '$25,000'), ('玩家席位', '7 席'))):
            x = 22+i*109
            c.create_rectangle(x, 101, x+109, 137, outline='#77906B')
            c.create_rectangle(x, 137, x+109, 178, outline='#77906B')
            self._text(x+54.5, 119, title, 11, PANEL_BG)
            self._text(x+54.5, 158, value, 12, GOLD)
        c.create_rectangle(797, 69, 1128, 178, fill=ROOT_BG, outline=GOLD, width=2)
        self._text(962, 86, '底注赔率', 13, PANEL_BG)
        self._text(816, 113, '两道全胜', 11, PANEL_BG, anchor='w')
        self._text(1108, 113, '0.95 : 1', 12, GOLD, anchor='e')
        self._text(816, 138, '一胜一负', 11, PANEL_BG, anchor='w')
        self._text(1108, 138, '退回底注', 11, PANEL_BG, anchor='e')
        self._text(962, 163, 'Copy 庄家胜 · 普通0点相同庄家胜局', 10, '#CDD5BF')
        c.create_rectangle(384, 10, 764, 181, fill='#4b1e22', outline='#6B4544')
        self._text(574, 28, '庄家', 16, PANEL_BG)
        self._create_shoe_panel()
        self.player_panels, self.player_titles = {}, {}
        self.seat_labels, self.bet_labels, self.seat_actions = {}, {}, {}
        for seat in self.game.SEATS:
            x = self.seat_x(seat)
            fill = self.ZONE_COLORS[(seat-1) % 2]
            self.player_panels[seat] = c.create_rectangle(x, 317, x+self.SEAT_WIDTH, 614, fill=fill, outline='')
            self.player_titles[seat] = self._text(x+76, 335, f'玩家{seat}', 18, PANEL_BG)
            self.seat_labels[seat] = self._text(x+76, 442, '', 11, '#C9D4BD')
            tag = f'bet_{seat}'
            c.create_oval(x+44, 464, x+108, 528, fill=fill, outline=GOLD, width=2, tags=tag)
            c.create_oval(x+48, 468, x+104, 524, outline='#77906B', tags=tag)
            self.bet_labels[seat] = self._text(x+76, 497, '底注', 11, PANEL_BG, tags=tag)
            c.tag_bind(tag, '<Button-1>', lambda _e, s=seat: self.add_bet(s))
            c.tag_bind(tag, '<Button-3>', lambda _e, s=seat: self.clear_bet(s))
            c.tag_bind(tag, '<Enter>', lambda _e, s=seat: self._bet_hover(s))
            c.tag_bind(tag, '<Leave>', lambda _e: self._bet_leave())
            auto = self.create_control_button(x+8, 539, x+144, 570, '自动分牌',
                lambda s=seat: self.use_house_way(s), DARK_BLUE, font_size=14, draw_shadow=False)
            confirm = self.create_control_button(x+8, 576, x+144, 607, '确认',
                lambda s=seat: self.confirm_seat(s), '#397A48', font_size=14, draw_shadow=False)
            self.seat_actions[seat] = (auto, confirm)
        # UTH bottom bar, chip rack, bevelled controls and Enter shortcut.
        c.create_rectangle(0, 625, 1150, 749, fill=ROOT_BG, outline='#6C7850', width=2)
        self.balance_item = self._text(10, 665, '', 18, TEXT, anchor='w')
        self.total_item = self._text(10, 710, '', 18, TEXT, anchor='w')
        self.clear_button = self.create_control_button(278, 650, 344, 704, '清除',
            self.reset_bets, '#9B403A', font_size=11, draw_shadow=False)
        self.info_button = self.create_control_button(810, 650, 855, 695, '?',
            self.show_detailed_rules, DARK_BLUE, font_size=17, draw_shadow=False)
        self.repeat_button = self.create_control_button(862, 638, 1000, 708, '重复下注',
            self.secondary_action, '#536A43', font_size=11, draw_shadow=False)
        self.start_button = self.create_control_button(1012, 628, 1138, 720, '开牌',
            self.primary_action, HEADER_BG, fg=TITLE_FG, font_size=14,
            subtext='Enter', subtext_font_size=14, draw_shadow=False)
        self.restart_button = self.create_control_button(862,638,1138,708,'再来一局(30)',
            self._return_all_chips,HEADER_BG,fg=TITLE_FG,font_size=17,draw_shadow=False)
        self.canvas.itemconfigure(self.restart_button,state='hidden')
        self._draw_chips()


    def seat_x(self, seat):
        return self.SEAT_LEFT+(seat-1)*self.SEAT_PITCH

    def _draw_chips(self):
        self.canvas.delete('rack')
        for i, (amount, _) in enumerate(CHIPS):
            tag = f'rack_{i}'
            self._draw_chip(tag, amount, 415+i*64, 674, ('rack',), amount == self.selected_chip)
            self.canvas.tag_bind(tag, '<Button-1>', lambda _e, a=amount: self.select_chip(a))


    def select_chip(self, amount):
        if self.game.stage == 'betting' and self._idle():
            self.selected_chip = amount
            self._draw_chips()


    def _bet_hover(self, seat):
        self.canvas.configure(cursor='hand2' if self.game.stage == 'betting' and self._idle() else '')


    def _bet_leave(self):
        self.canvas.configure(cursor='')


    def _render_bet_chips(self):
        self.canvas.delete('bet_chips')
        for (seat, role), chip in sorted(self.visual_chips.items(), key=lambda kv: kv[0][1] != 'stake'):
            self._draw_chip(f'chip_{seat}_{role}', chip['amount'], *chip['xy'], ('bet_chips', f'bet_{seat}'), scale=self.BET_CHIP_SCALE)


    def add_bet(self, seat):
        if not self._idle() or self.game.stage != 'betting': return
        previous = dict(self.game.bets)
        try:
            self.game.add_bet(seat, self.selected_chip, self.balance)
        except ValueError as exc:
            messagebox.showwarning('下注', str(exc), parent=self)
            return
        new_bets = dict(self.game.bets)
        self.game.bets = previous
        self._apply_bet_layout(new_bets)


    def clear_bet(self, seat):
        if self.game.stage == 'betting' and self._idle():
            new_bets = dict(self.game.bets)
            new_bets[seat] = 0.0
            self._apply_bet_layout(new_bets)


    def reset_bets(self):
        if self.game.stage == 'betting' and self._idle():
            self._apply_bet_layout({s: 0.0 for s in self.game.SEATS})


    def secondary_action(self):
        if not self._idle(): return
        if self.game.stage == 'setting':
            seats = [s for s in self.game.active_seats if s not in self.game.confirmed]
            if not self._all_auto_prepared:
                for seat in seats:
                    self.game.suggest(seat)
                self._all_auto_prepared = True
                self._refresh()
                return
            # Validate every pending seat before confirming any of them.
            for seat in seats:
                split = self.game.selected_split(seat)
                if split is None or evaluate_hand(split[0]).key > evaluate_hand(split[1]).key:
                    messagebox.showwarning('确定分牌',f'玩家{seat}：请选择两张前道，且后道不能小于前道。',parent=self)
                    return
            for seat in seats:
                self.game.confirm(seat)
            if seats:
                pending = [len(seats)]
                def done():
                    pending[0] -= 1
                    if not pending[0]: self._maybe_reveal()
                for seat in seats: self._animate_arrangement(seat, done)
            self._refresh()
        elif self.game.stage == 'betting' and self.game.last_bets:
            if sum(self.game.last_bets.values()) > self.balance:
                messagebox.showwarning('重复下注', '余额不足。', parent=self)
            else:
                self._apply_bet_layout(self.game.last_bets)


    def primary_action(self):
        if not self._idle(): return
        if self.game.stage == 'betting': self.start_round()
        elif self.game.stage in ('await_restart', 'credit_pending'): self._return_all_chips()


    def _enter_action(self, event=None):
        if event is not None and event.widget.winfo_toplevel() is not self.winfo_toplevel():
            return
        self.primary_action()
        return 'break'

    def _refresh(self):
        c, g = self.canvas, self.game
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        c.itemconfigure(self.total_item, text=f'本局下注: ${g.total_bet:,.2f}' if g.total_bet else f'上局返还: ${g.last_return:,.2f}')
        betting = g.stage == 'betting' and self._idle()
        setting = g.stage == 'setting' and self._idle()
        restarting = g.stage in ('settling', 'await_restart', 'returning', 'credit_pending', 'sweeping')
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, setting or (betting and bool(g.last_bets)))
        self.set_control_button_state(self.start_button, betting)
        self.set_control_button_state(self.restart_button, g.stage in ('await_restart', 'credit_pending') and self._idle())
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        c.itemconfigure(self.control_buttons[self.repeat_button]['text'], text=('全部确定分牌' if self._all_auto_prepared else '全部自动分牌') if setting else '重复下注')
        for seat in g.SEATS:
            ready = setting and seat in g.active_seats and seat not in g.confirmed
            for tag in self.seat_actions[seat]:
                self.set_control_button_state(tag, ready)
                c.itemconfigure(tag, state='hidden' if seat in g.confirmed else 'normal')
            c.itemconfigure(self.control_buttons[self.seat_actions[seat][1]]['text'],
                            text='已确认' if seat in g.confirmed else '确认')
            label, color = '', PANEL_BG
            if ready:
                split = g.selected_split(seat)
                label = '选择两张前道'
                if split:
                    label = '确认' if evaluate_hand(split[1]).key >= evaluate_hand(split[0]).key else '后道较小'
            if seat in g.results:
                r = g.results[seat]
                label = {'win':'玩家获胜', 'push':'Push', 'lose':'庄家获胜'}[r['result']]
                color = {'win':'#FFE18A', 'push':'#9CDBF1', 'lose':TEXT}[r['result']]
            c.itemconfigure(self.seat_labels[seat], text=label, fill=color, state='hidden')
            c.itemconfigure(self.player_titles[seat], fill=color)
            c.itemconfigure(self.bet_labels[seat], text='底注', fill=PANEL_BG)
        self._render_hand_tables()
        self._render_bet_chips()
        self._draw_hands()
        self._draw_wall()
        self._draw_dice(g.dice or [1, 1, 1])


    def _render_hand_tables(self):
        """One row, front/back cells; colour each corresponding hand at settlement."""
        c, g = self.canvas, self.game
        c.delete('hand_tables')
        for seat in g.SEATS:
            if seat not in g.confirmed or not g.bets[seat] or seat not in g.splits:
                continue
            x0, y0, x1, y1 = self.seat_x(seat)+8, 539, self.seat_x(seat)+144, 607
            middle = (x0+x1)/2
            for index, (title, hand) in enumerate(zip(('前道','后道'), g.splits[seat])):
                left, right = (x0,middle) if index == 0 else (middle,x1)
                background, foreground = ROOT_BG, PANEL_BG
                if seat in g.results:
                    comparison = g.results[seat]['comparisons'][index]
                    if comparison == 0:
                        background, foreground = '#ADD8E6', TITLE_FG
                    elif comparison > 0:
                        background, foreground = GOLD, TITLE_FG
                    else:
                        background, foreground = '#D64545', TEXT
                c.create_rectangle(left,y0,right,y1,fill=background,outline='',tags='hand_tables')
                cx = (left+right)/2
                self._text(cx,y0+17,title,11,foreground,tags='hand_tables')
                self._text(cx,y0+46,self._display_hand_name(hand),12,foreground,tags='hand_tables')
            c.create_rectangle(x0,y0,x1,y1,outline=GOLD,width=2,tags='hand_tables')
            both_won = g.results.get(seat, {}).get('result') == 'win'
            c.create_line(middle,y0,middle,y1,fill='#000000' if both_won else GOLD,
                          width=1,tags='hand_tables')

    def _hand_positions(self, seat, split=False):
        if seat == 0:
            if split:
                return [(440, 55, 95, 38), (440, 99, 95, 38),
                        (574, 48, 38, 95), (622, 48, 38, 95)]
            return [(477+i*49, 48, 38, 95) for i in range(4)]
        x = self.seat_x(seat)
        compact = [(x+9+i*35, 354, 28, 70) for i in range(4)]
        if split:
            # The same 36x90 physical tile: front rotated, back upright.
            expanded = [(x+31, 235, 90, 36), (x+31, 277, 90, 36),
                        (x+34, 334, 36, 90), (x+82, 334, 36, 90)]
        else:
            expanded = [(x+34, 237, 36, 90), (x+82, 237, 36, 90),
                        (x+34, 337, 36, 90), (x+82, 337, 36, 90)]
        t = self._layout_progress
        return [tuple(a+(b-a)*t for a,b in zip(old,new)) for old,new in zip(compact,expanded)]


    def _draw_hands(self):
        c, g = self.canvas, self.game
        c.delete('table_tiles')
        for seat in (0, *g.SEATS):
            if seat in self._arranging: continue
            if seat not in self._dealt:
                for x,y,w,h in self._hand_positions(seat):
                    c.create_rectangle(x,y,x+w,y+h,outline='#7B9374',dash=(3,3),tags='table_tiles')
                continue
            # Stake eligibility gates all front faces and hand labels, in every phase.
            eligible = seat == 0 or g.bets[seat] > 0
            split = g.splits.get(seat) if eligible else None
            positions = self._hand_positions(seat, bool(split))
            tiles = [*split[0], *split[1]] if split else g.hands[seat]
            if split:
                if seat == 0:
                    c.create_rectangle(418,147,688,176,fill='#4b1e22',
                                       outline=GOLD,width=1,tags='table_tiles')
                    c.create_line(553,147,553,176,fill=GOLD,width=1,tags='table_tiles')
                    labels = [(485.5,161.5,'前道 '+self._display_hand_name(split[0])),
                              (620.5,161.5,'后道 '+self._display_hand_name(split[1]))]
                else:
                    labels = []  # Player hand values live in the 1x2 table below.
                for lx,ly,label in labels: self._text(lx,ly,label,11,PANEL_BG,tags='table_tiles')
            for i,(tile,(x,y,w,h)) in enumerate(zip(tiles,positions)):
                if self._flip_state and (seat,i) == self._flip_state[:2]: continue
                tag = f'table_tile_{seat}_{i}'
                original_index = next(j for j,t in enumerate(g.hands[seat]) if t.uid == tile.uid)
                face = eligible and (seat,original_index) in self._face_up
                selected = bool(seat and eligible and not split and i in g.selected[seat])
                result = g.results.get(seat)
                if split and result:
                    cmp = result['comparisons'][i//2]
                    shade = '#E2DFD1' if cmp == 0 else '#54A96B' if cmp > 0 else '#AE4945'
                    c.create_rectangle(x-2,y-2,x+w+3,y+h+3,fill=shade,outline=shade,tags='table_tiles')
                self.draw_tile(x, y-5 if selected else y, w,h,tile,face_up=face,selected=selected,
                               tag=tag,extra_tag='table_tiles',show_name=False,compact=True)
                if seat and eligible and not split:
                    c.tag_bind(tag,'<Button-1>',lambda _e,s=seat,n=i:self.tile_click(s,n))


    def tile_click(self, seat, index):
        g = self.game
        if g.stage != 'setting' or seat not in g.active_seats or seat in g.confirmed or not self._idle():
            return
        selected = g.selected[seat]
        if index in selected:
            selected.remove(index)
        elif len(selected) < 2:
            selected.append(index)
        self._refresh()


    def use_house_way(self, seat):
        if self.game.stage != 'setting' or not self._idle():
            return
        self.game.suggest(seat)
        self._refresh()


    def confirm_seat(self, seat):
        if not self._idle(): return
        try:
            if not self.game.confirm(seat): return
        except ValueError as exc:
            messagebox.showwarning('分牌', str(exc), parent=self)
            return
        self._animate_arrangement(seat,self._maybe_reveal)


    # Orthographic 2.5D wall: actual thickness, two visible layers, side shading.
    # Tile index -> two adjacent columns per four-tile deal; no hidden dead hand.
    def _wall_origin(self, index):
        stack, local = divmod(index, 4)
        column = stack*2 + local % 2
        layer = local//2
        return 108+column*38+layer*2, 246-layer*12

    def _prism_tile(self, x, y, scale=1.0, tag='wall', theme=None, clip_bounds=None):
        c = self.canvas
        def polygon(*coords, **kw):
            if clip_bounds is None:
                return c.create_polygon(*coords, **kw)
            points = list(zip(coords[::2], coords[1::2]))
            for edge, direction in ((clip_bounds[0], 1), (clip_bounds[1], -1)):
                if not points:
                    return
                clipped = []
                previous = points[-1]
                previous_inside = (previous[0] - edge) * direction >= 0
                for point in points:
                    inside = (point[0] - edge) * direction >= 0
                    if inside != previous_inside:
                        fraction = (edge - previous[0]) / (point[0] - previous[0])
                        clipped.append((edge, previous[1] + fraction * (point[1] - previous[1])))
                    if inside:
                        clipped.append(point)
                    previous, previous_inside = point, inside
                points = clipped
            if len(points) >= 3:
                return c.create_polygon(*(value for point in points for value in point), **kw)

        def line(x0, y0, x1, y1, **kw):
            if clip_bounds is not None:
                dx, dy = x1 - x0, y1 - y0
                if abs(dx) < 1e-12:
                    if not clip_bounds[0] <= x0 <= clip_bounds[1]:
                        return
                else:
                    limits = sorted((edge - x0) / dx for edge in clip_bounds)
                    start, end = max(0., limits[0]), min(1., limits[1])
                    if start > end:
                        return
                    x0, y0, x1, y1 = (x0 + start * dx, y0 + start * dy,
                                      x0 + end * dx, y0 + end * dy)
            return c.create_line(x0, y0, x1, y1, **kw)

        theme = theme or self.tile_theme
        white = theme == 'white'
        top, side, front = (('#ECE3CF', '#B2A38D', '#CFC1AA') if white else
                            ('#293832', '#101B16', '#182820'))
        def p(u, v): return (x+u*scale, y+v*scale)
        a, b, d = p(0, 0), p(27, 0), p(-12, 36)
        e = p(15, 36)
        thick = 8*scale
        # Cast shadow, right side, front edge, then upper face.
        polygon(*p(-10, 42), *p(19, 43), *p(34, 5), *p(29, 0),
                         fill='#0D281D', outline='', tags=tag)
        polygon(*b, *e, e[0], e[1]+thick, b[0], b[1]+thick,
                         fill=side, outline='#746B56' if white else '#415246', tags=tag)
        polygon(*d, *e, e[0], e[1]+thick, d[0], d[1]+thick,
                         fill=front, outline='#8B806B' if white else '#415246', tags=tag)
        polygon(*a, *b, *e, *d, fill=top,
                         outline='#F7F0DD' if white else '#7B8976', width=1, tags=tag)
        polygon(*p(3, 5), *p(21, 5), *p(12, 30), *p(-5, 30),
                         fill=top, outline='#AB9160' if white else '#8F804D', tags=tag)
        line(*p(4, 16), *p(14, 16), fill='#A58D59', tags=tag)
        line(*p(2, 21), *p(12, 21), fill='#A58D59', tags=tag)

    def _wall_snapshot(self, tiles, tag='wall', offset=0, theme=None, removed=None, clip_bounds=None):
        removed = removed or set()
        # Back-to-front drawing avoids incorrect intersections between columns.
        for layer in (0, 1):
            for col in reversed(range(16)):
                index = (col//2)*4+(col % 2)+2*layer
                if index in removed:
                    continue
                x, y = self._wall_origin(index)
                self._prism_tile(x+offset, y, tag=tag, theme=theme, clip_bounds=clip_bounds)

    def _draw_wall(self):
        self.canvas.delete('wall')
        if self._layout_progress > 0 or (self._moving and self.game.stage == 'betting'): return
        self._wall_snapshot(self.game.tiles,removed=self._wall_removed)
        self.canvas.itemconfigure(self.shoe_label,text=f'{32-len(self._wall_removed)} / 32')


    def _draw_dice(self, values=None):
        c = self.canvas
        if self._layout_progress > 0:
            c.delete('dice')
            self._golden_dice_cup_item = self._golden_dice_cup_photo = None
            return
        if self.golden_dice_bowl is None:
            self.golden_dice_bowl = GoldenDiceBowl(values or [1, 1, 1])
        # Enlarge the bowl while keeping the cube edge and pixel scale unchanged.
        picture = _gd_render_bowl(self.golden_dice_bowl)
        size = (round(124*GD_BOWL_SCALE), round(87*GD_BOWL_SCALE))
        picture = picture.resize(size, Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(picture, master=c)
        if self._golden_dice_cup_item is not None and c.find_withtag('dice'):
            c.itemconfigure(self._golden_dice_cup_item, image=photo)
        else:
            self._golden_dice_cup_item = c.create_image(953, 180, anchor='n', image=photo, tags='dice')
        self._golden_dice_cup_photo = photo
        self._update_dice_equation()

    def _update_dice_equation(self):
        if self.game.stage == 'rolling':
            terms = ('…', '+', '…', '+', '…', '=', '…')
        else:
            blue, red, gold = self.golden_dice_bowl.values()
            terms = (str(blue), '+', str(red), '+', str(gold), '=', str(blue + red + gold))
        for item, text in zip(self._dice_equation_items, terms):
            self.canvas.itemconfigure(item, text=text)


    def start_round(self):
        if not self._idle() or self.game.stage != 'betting':
            return
        try:
            self.balance = self.game.start(self.balance)
        except ValueError as exc:
            messagebox.showwarning('开牌', str(exc), parent=self)
            return
        self._persist_balance()
        self._dealt.clear()
        self._wall_removed.clear()
        self._dealer_face = False
        self._face_up.clear()
        self._round_credited = self._return_persisted = False
        self._all_auto_prepared = False
        self._refresh()
        self._start_golden_dice_roll()


    def _start_golden_dice_roll(self):
        if self._closing or self.game.stage != 'rolling':
            return
        self.golden_dice_bowl.begin()
        self._golden_dice_phase = 'shake'
        self._golden_dice_time = 0.
        self._golden_dice_stable_time = 0.
        self._golden_dice_rest_anchor = None
        self._roll_frame()

    def _reroll_golden_dice(self, reason):
        self._golden_dice_phase = 'reroll'
        self.status = f'重骰 · {reason}'
        self._schedule(600, self._start_golden_dice_roll)

    def _golden_dice_is_motionless(self, dt):
        """Require an unchanged rigid pose for 0.65 s, including invalid landings.

        A slow frame or a momentary zero velocity is not a stop. Compare every
        vertex with the start of the observation window so creeping motion
        cannot accumulate unnoticed. The tolerance is under 0.04 screen pixels.
        """
        pose = tuple(point for die in self.golden_dice_bowl.dice for point in die.vertices())
        anchor = self._golden_dice_rest_anchor
        if anchor is None or any(_gd_length(_gd_sub(p,q)) > .00005 for p,q in zip(pose,anchor)):
            self._golden_dice_rest_anchor = pose
            self._golden_dice_stable_time = 0.
            return False
        self._golden_dice_stable_time += dt
        return self._golden_dice_stable_time >= .65

    def _roll_frame(self):
        if self._closing or self.game.stage != 'rolling':
            return
        started = time.monotonic()
        bowl = self.golden_dice_bowl
        valid_result = False
        # Use the same 480 Hz physics and 30 Hz drawing as Golden Dice.
        dt = 1/480
        for _ in range(16):
            if self._golden_dice_phase == 'shake':
                self._golden_dice_time += dt
                bowl.step(dt, self._golden_dice_time, self._golden_dice_time < bowl.duration)
                if self._golden_dice_time >= bowl.duration:
                    self._golden_dice_phase = 'settle'
            else:
                bowl.step(dt, 0., False)
                if self._golden_dice_is_motionless(dt):
                    for die in bowl.dice:
                        die.v = die.omega = (0.,0.,0.)
                    error = bowl.landing_error()
                    if error:
                        self._draw_dice()
                        self._reroll_golden_dice(error)
                        return
                    valid_result = True
                    break
        self._draw_dice()
        if not valid_result:
            delay = max(1, 33-round((time.monotonic()-started)*1000))
            self._schedule(delay, self._roll_frame)
            return

        dice = bowl.values()
        self._golden_dice_phase = 'idle'
        self.game.deal(dice)
        start = self.game.deal_order[0]
        self.canvas.itemconfigure(self.dice_label,
            text=f'{sum(dice)} 点 · '+('庄家' if start == 0 else f'玩家{start}')+'先派')
        self._refresh()
        self._schedule(220, self._deal_stack, 0)

    def _deal_stack(self, stack_index):
        if stack_index == 8:
            self._finish_deal()
            return
        seat = self.game.deal_order[stack_index]
        self._wall_removed.update(range(stack_index*4, stack_index*4+4))
        self._draw_wall()
        targets = self._hand_positions(seat)
        starts = [self._wall_origin(stack_index*4+i) for i in range(4)]
        def frame(step):
            self.canvas.delete('flight')
            t = step/15
            smooth = t*t*(3-2*t)
            for i, ((sx, sy), (tx, ty, tw, th)) in enumerate(zip(starts, targets)):
                x, y = sx+(tx-sx)*smooth, sy+(ty-sy)*smooth-30*math.sin(math.pi*t)
                if step < 5:
                    self._prism_tile(x, y, tag='flight')
                else:
                    w, h = 27+(tw-27)*smooth, 44+(th-44)*smooth
                    self.draw_tile(x, y, w, h, self.game.hands[seat][i], face_up=False,
                                   tag='flight', extra_tag=None, compact=True)
            if step < 15:
                self._schedule(16, frame, step+1)
            else:
                self.canvas.delete('flight')
                self._dealt.add(seat)
                self._draw_hands()
                self._schedule(70, self._deal_stack, stack_index+1)
        frame(0)


    def _maybe_reveal(self):
        if self.game.stage != 'setting' or not self.game.ready() or self._arranging: return
        self.game.stage = 'revealing'
        self._refresh()
        self._schedule(350,self._reveal_dealer)


    def _reveal_dealer(self):
        def revealed():
            self._dealer_face = True
            choice = traditional_house_way(self.game.hands[0])
            self.game.splits[0] = (choice.low,choice.high)
            self._animate_arrangement(0,lambda:self._schedule(350,self._settle_round))
        self._flip_next([(0,i) for i in range(4)],0,revealed)


    def _settle_round(self):
        if self.game.resolved: return
        self.game.settle()
        transfers = []
        for seat,r in self.game.results.items():
            center = self._bet_center(seat)
            if r['returned'] <= 0:
                chip = self.visual_chips.pop((seat,'stake'),None)
                if chip: transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=(575,43),duration=280))
            elif r['returned'] > self.game.bets[seat]:
                profit = money(r['returned']-self.game.bets[seat])
                target = (center[0]-(56+3)*self.BET_CHIP_SCALE-self.PROFIT_CHIP_GAP+15, center[1])
                transfers.append(dict(amount=profit,start=(575,43),target=target,duration=440,
                    arrive=lambda s=seat,a=profit,p=target:self._set_visual(s,'profit',a,p)))
        # Push leaves the original stake exactly where it is, like UTH.
        self._refresh()
        self._run_chip_batch(transfers,self._await_next_round)


    def new_round(self):
        self._return_all_chips()


    def _swap_shoe(self):
        old_tiles,old_theme = self.game.tiles[:],self.tile_theme
        old_removed = set(self._wall_removed)
        self.game.next_round()
        self._dealer_face = False
        self._round_credited = self._return_persisted = False
        self._all_auto_prepared = False
        self.tile_theme = self._opposite_tile_theme(self.tile_theme)
        self._wall_removed.clear()
        self._moving = True
        self._refresh()
        shoe_bounds = (22, self.canvas.coords(self.shoe_label)[0])
        def frame(step):
            self.canvas.delete('shoe_swap')
            t = step/24
            t = t*t*(3-2*t)
            self._wall_snapshot(old_tiles, tag='shoe_swap', offset=1200*t, theme=old_theme,
                                removed=old_removed, clip_bounds=shoe_bounds)
            self._wall_snapshot(self.game.tiles, tag='shoe_swap', offset=-1200*(1-t),
                                clip_bounds=shoe_bounds)
            if step < 24: self._schedule(20,frame,step+1)
            else:
                self.canvas.delete('shoe_swap')
                self._moving = False
                self._refresh()
        frame(0)


    @staticmethod
    def _compact(amount):
        """K/M筹码取两位有效数字并截断；有省略才加+，不改动真实金额。"""
        from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
        value=Decimal(str(amount)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        if value==Decimal('2.50'):return '2.50'
        if abs(value)>=1000000:
            divisor,suffix=Decimal(1000000),'M'
        elif abs(value)>=1000:
            divisor,suffix=Decimal(1000),'K'
        else:
            label=format(value,'f')
            return label.rstrip('0').rstrip('.') if '.' in label else label
        scaled=value/divisor
        precision=Decimal(1).scaleb(abs(scaled).adjusted()-1)
        shown=scaled.quantize(precision,rounding=ROUND_DOWN)
        label=format(shown,'f')
        if '.' in label:label=label.rstrip('0').rstrip('.')
        return label+suffix+('+' if shown!=scaled else '')


    def _rounded_rectangle(self, x0, y0, x1, y1, radius, **options):
        return self.canvas.create_polygon(
            x0+radius, y0, x1-radius, y0, x1, y0, x1, y0+radius,
            x1, y1-radius, x1, y1, x1-radius, y1, x0+radius, y1,
            x0, y1, x0, y1-radius, x0, y0+radius, x0, y0,
            smooth=True, splinesteps=24, **options)


    @staticmethod
    def shade_color(color, factor):
        color = color.lstrip('#')
        if len(color) != 6:
            return '#555555'
        values = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
        values = [max(0, min(255, int(value * factor))) for value in values]
        return '#' + ''.join(f'{value:02x}' for value in values)


    def create_control_button(self, x0, y0, x1, y1, text, command, fill,
                              fg='white', font_size=11, subtext=None,
                              subtext_font_size=10, draw_shadow=True):
        tag = f'control_button_{len(self.control_buttons)}'
        shadow = self.canvas.create_rectangle(x0 + 5, y0 + 6, x1 + 5, y1 + 6,
                                              fill='#070605', outline='#070605',
                                              width=1, tags=(tag, 'controls')) if draw_shadow else None
        rim = self.canvas.create_rectangle(x0, y0, x1, y1,
                                           fill=self.shade_color(fill, 0.55),
                                           outline='#b7a58d', width=2,
                                           tags=(tag, 'controls'))
        face = self.canvas.create_rectangle(x0 + 4, y0 + 4, x1 - 4, y1 - 4,
                                            fill=fill,
                                            outline=self.shade_color(fill, 1.25),
                                            width=2, tags=(tag, 'controls'))
        highlight = self.canvas.create_line(x0 + 8, y0 + 8, x1 - 8, y0 + 8,
                                            fill=self.shade_color(fill, 1.45), width=2,
                                            tags=(tag, 'controls'))
        center_y = (y0 + y1) / 2 - 1
        text_y = center_y - 12 if subtext else center_y
        text_id = self.canvas.create_text((x0 + x1) / 2, text_y, text=text,
                                          font=('Arial', font_size, 'bold'), fill=fg,
                                          tags=(tag, 'controls'))
        subtext_id = None
        subtext_center_y = None
        if subtext:
            subtext_center_y = center_y + 16
            subtext_id = self.canvas.create_text((x0 + x1) / 2, subtext_center_y,
                                                 text=subtext,
                                                 font=('Arial', subtext_font_size, 'bold'),
                                                 fill=fg, tags=(tag, 'controls'))
        self.control_buttons[tag] = {
            'shadow': shadow, 'rim': rim, 'face': face, 'highlight': highlight,
            'text': text_id, 'subtext': subtext_id, 'command': command,
            'fill': fill, 'fg': fg, 'enabled': True, 'pressed': False,
            'center_y': text_y, 'subtext_center_y': subtext_center_y,
        }

        def enter(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfigure(button['face'], fill=self.shade_color(button['fill'], 1.12))

        def leave(_event=None):
            button = self.control_buttons.get(tag)
            if button and button['enabled'] and not button['pressed']:
                self.canvas.itemconfigure(button['face'], fill=button['fill'])

        def press(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled']:
                return
            button['pressed'] = True
            self.canvas.itemconfigure(button['face'], fill=self.shade_color(button['fill'], 0.72))
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 0.8))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'] + 2)
            if button.get('subtext'):
                sx, _sy = self.canvas.coords(button['subtext'])
                self.canvas.coords(button['subtext'], sx, button['subtext_center_y'] + 2)

        def release(_event=None):
            button = self.control_buttons.get(tag)
            if not button or not button['enabled'] or not button['pressed']:
                return
            button['pressed'] = False
            self.canvas.itemconfigure(button['face'], fill=button['fill'])
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            x, _y = self.canvas.coords(button['text'])
            self.canvas.coords(button['text'], x, button['center_y'])
            if button.get('subtext'):
                sx, _sy = self.canvas.coords(button['subtext'])
                self.canvas.coords(button['subtext'], sx, button['subtext_center_y'])
            button['command']()

        self.canvas.tag_bind(tag, '<Enter>', enter)
        self.canvas.tag_bind(tag, '<Leave>', leave)
        self.canvas.tag_bind(tag, '<ButtonPress-1>', press)
        self.canvas.tag_bind(tag, '<ButtonRelease-1>', release)
        return tag


    def set_control_button_state(self, tag, enabled):
        button = self.control_buttons.get(tag)
        if not button:
            return
        button['enabled'] = bool(enabled)
        button['pressed'] = False
        x, _y = self.canvas.coords(button['text'])
        self.canvas.coords(button['text'], x, button['center_y'])
        if button.get('subtext'):
            sx, _sy = self.canvas.coords(button['subtext'])
            self.canvas.coords(button['subtext'], sx, button['subtext_center_y'])
        if enabled:
            self.canvas.itemconfigure(button['face'], fill=button['fill'])
            self.canvas.itemconfigure(button['rim'], fill=self.shade_color(button['fill'], 0.55))
            self.canvas.itemconfigure(button['highlight'], fill=self.shade_color(button['fill'], 1.45))
            self.canvas.itemconfigure(button['text'], fill=button['fg'])
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill=button['fg'])
        else:
            self.canvas.itemconfigure(button['face'], fill='#4a4743')
            self.canvas.itemconfigure(button['rim'], fill='#262422')
            self.canvas.itemconfigure(button['highlight'], fill='#66615b')
            self.canvas.itemconfigure(button['text'], fill='#9b9690')
            if button.get('subtext'):
                self.canvas.itemconfigure(button['subtext'], fill='#9b9690')

    def _init_v2(self):
        self._layout_progress = 0.0
        self._all_auto_prepared = False
        self._motion_count = 0
        self._chip_serial = 0
        self.visual_chips = {}
        self._face_up = set()
        self._flip_state = None
        self._arranging = set()
        self._restart_job = None
        self._restart_seconds = 30
        self._round_credited = False
        self._return_persisted = False


    def _idle(self):
        return not self._moving and self._motion_count == 0 and not self._arranging


    def _draw_chip(self, tag, amount, x, y, extra_tags=(), selected=False, scale=1.0):
        # Rack remains 56px; betting/profit chips use 80% size, including rims and text.
        c, tags = self.canvas, (tag, *extra_tags)
        color = next((col for value, col in reversed(CHIPS) if amount >= value), HEADER_BG)
        outer, inner = 28*scale, 23*scale
        c.create_oval(x-outer, y-outer, x+outer, y+outer, fill='#182F25',
                      outline=GOLD if selected else '#6C7850', width=3*scale, tags=tags)
        c.create_oval(x-inner, y-inner, x+inner, y+inner, fill=color, outline=PANEL_BG, width=2*scale, tags=tags)
        self._text(x, y, self._compact(amount), max(8, round(10*scale)),
                   TEXT if color in (BLACK, RED) else BLACK, tags=tags)


    def _rack_position(self, index=None, total=1):
        if index is not None:
            return 575+(index-(total-1)/2)*min(28, 140/max(1, total-1)), 674
        index = next((i for i, (value, _) in enumerate(CHIPS) if value == self.selected_chip), 0)
        return 415+index*64, 674


    def _bet_center(self, seat):
        return self.seat_x(seat)+76, 497


    def _set_visual(self, seat, role, amount, xy=None):
        key = (seat, role)
        if amount:
            self.visual_chips[key] = dict(amount=float(amount), xy=xy or self._bet_center(seat))
        else:
            self.visual_chips.pop(key, None)


    def _animate_chip(self, amount, start, target, complete=None, duration=220):
        if not amount:
            if complete: complete()
            return
        self._motion_count += 1
        self._chip_serial += 1
        tag = f'moving_chip_{self._chip_serial}'
        start_scale = 1.0 if start[1] == 674 else self.BET_CHIP_SCALE
        end_scale = 1.0 if target[1] == 674 else self.BET_CHIP_SCALE
        steps = max(1, round(duration/16))
        self._refresh()
        def frame(index):
            self.canvas.delete(tag)
            t = index/steps
            t = t*t*(3-2*t)
            self._draw_chip(tag, amount, start[0]+(target[0]-start[0])*t,
                            start[1]+(target[1]-start[1])*t, ('moving_chips',),
                            scale=start_scale+(end_scale-start_scale)*t)
            if index < steps:
                self._schedule(round(duration/steps), frame, index+1)
            else:
                self.canvas.delete(tag)
                self._motion_count -= 1
                if complete: complete()
                self._refresh()
        frame(0)


    def _run_chip_batch(self, transfers, complete):
        if not transfers:
            complete()
            return
        pending = [len(transfers)]
        def arrived(transfer):
            if transfer.get('arrive'): transfer['arrive']()
            pending[0] -= 1
            if not pending[0]: complete()
        for transfer in transfers:
            self._animate_chip(transfer['amount'], transfer['start'], transfer['target'],
                               lambda t=transfer: arrived(t), transfer.get('duration', 220))


    def _apply_bet_layout(self, new_bets):
        previous = dict(self.game.bets)
        self.game.bets = dict(new_bets)
        transfers = []
        for seat in self.game.SEATS:
            delta = money(new_bets[seat]-previous[seat])
            if delta > 0:
                transfers.append(dict(amount=delta, start=self._rack_position(), target=self._bet_center(seat),
                    arrive=lambda s=seat, a=new_bets[seat]: self._set_visual(s, 'stake', a)))
            elif delta < 0:
                self._set_visual(seat, 'stake', new_bets[seat])
                transfers.append(dict(amount=-delta, start=self._bet_center(seat), target=self._rack_position(), duration=440))
        self._run_chip_batch(transfers, self._refresh)
        self._refresh()


    def _expand_table(self, target, complete):
        self._moving = True
        start = self._layout_progress
        if target:
            for tag in ('shoe_panel','wall','dice'): self.canvas.delete(tag)
        def frame(step):
            t = step/15
            t = t*t*(3-2*t)
            self._layout_progress = start+(target-start)*t
            for seat in self.game.SEATS:
                x = self.seat_x(seat)
                top = 317-127*self._layout_progress
                self.canvas.coords(self.player_panels[seat],x,top,x+self.SEAT_WIDTH,614)
                self.canvas.coords(self.player_titles[seat],x+76,335-124*self._layout_progress)
            self._draw_hands()
            if step < 15: self._schedule(20,frame,step+1)
            else:
                self._moving = False
                if not target: self._create_shoe_panel()
                complete()
        frame(0)


    def _finish_deal(self):
        self.game.stage = 'expanding'
        self._refresh()
        def expanded():
            self.game.stage = 'revealing_players'
            sequence = [(s,i) for s in self.game.active_seats for i in range(4)]
            self._flip_next(sequence,0,self._finish_player_reveal)
        self._expand_table(1.0, expanded)


    def _flip_next(self, sequence, offset, complete):
        if offset == len(sequence):
            self._flip_state = None
            self.canvas.delete('flip_tile')
            complete()
            return
        seat,index = sequence[offset]
        if seat and not self.game.bets[seat]:
            self._flip_next(sequence,offset+1,complete)
            return
        x,y,w,h = self._hand_positions(seat)[index]
        tile = self.game.hands[seat][index]
        self._flip_state = (seat,index)
        self._draw_hands()
        def frame(step):
            self.canvas.delete('flip_tile')
            width = max(1, w*abs(1-step/5))
            self.draw_tile(x+(w-width)/2,y,width,h,tile,face_up=step>=5,
                           tag='flip_tile',extra_tag=None,show_name=False,compact=True)
            if step < 10: self._schedule(32,frame,step+1)
            else:
                self._face_up.add((seat,index))
                self._flip_state = None
                self.canvas.delete('flip_tile')
                self._draw_hands()
                self._flip_next(sequence,offset+1,complete)
        frame(0)


    def _finish_player_reveal(self):
        self.game.stage = 'setting'
        self._refresh()


    def _animate_arrangement(self, seat, complete):
        split = self.game.splits[seat]
        self._arranging.add(seat)
        start_positions = self._hand_positions(seat)
        targets = self._hand_positions(seat, True)
        tiles = [*split[0], *split[1]]
        uid_index = {t.uid:i for i,t in enumerate(self.game.hands[seat])}
        tag = f'arrange_{seat}'
        self._refresh()
        def frame(step):
            self.canvas.delete(tag)
            t = step/18
            t = t*t*(3-2*t)
            for i,(tile,(tx,ty,tw,th)) in enumerate(zip(tiles,targets)):
                sx,sy,sw,sh = start_positions[uid_index[tile.uid]]
                cx = sx+sw/2+(tx+tw/2-sx-sw/2)*t
                cy = sy+sh/2+(ty+th/2-sy-sh/2)*t
                bw = sw+((th if i<2 else tw)-sw)*t
                bh = sh+((tw if i<2 else th)-sh)*t
                self._draw_rotated_face_tile(cx,cy,bw,bh,90*t if i<2 else 0,tile,
                                             tag=tag,extra_tag=None,compact=True)
            if step < 18: self._schedule(18,frame,step+1)
            else:
                self.canvas.delete(tag)
                self._arranging.discard(seat)
                self._refresh()
                complete()
        frame(0)


    def _await_next_round(self):
        self.game.stage = 'await_restart'
        self._restart_seconds = 30
        self._refresh()
        self._restart_tick()


    def _restart_tick(self):
        self._restart_job = None
        if self.game.stage != 'await_restart': return
        self.canvas.itemconfigure(self.control_buttons[self.restart_button]['text'],
                                  text=f'再来一局({self._restart_seconds})')
        if self._restart_seconds <= 0:
            self._return_all_chips()
        else:
            self._restart_seconds -= 1
            self._restart_job = self._schedule(1000,self._restart_tick)


    def _cancel_restart(self):
        if self._restart_job is not None:
            try: self.after_cancel(self._restart_job)
            except tk.TclError: pass
            self._jobs.discard(self._restart_job)
            self._restart_job = None


    def _return_all_chips(self):
        if not self._idle(): return
        if self.game.stage == 'credit_pending':
            self._complete_chip_return()
            return
        if self.game.stage != 'await_restart': return
        self._cancel_restart()
        self.game.stage = 'returning'
        chips = list(self.visual_chips.values())
        self.visual_chips.clear()
        transfers = []
        for index,chip in enumerate(chips):
            target = self._rack_position(index,len(chips))
            transfers.append(dict(amount=chip['amount'],start=chip['xy'],target=target,duration=600,
                arrive=lambda a=chip['amount'],p=target,n=index:self._draw_chip(f'returned_{n}',a,*p,('returned_chips',))))
        self._refresh()
        self._run_chip_batch(transfers,self._complete_chip_return)


    def _credit_round_return(self):
        if not self._round_credited:
            self.balance = money(self.balance+self.game.last_return)
            self._round_credited = True
        if not self._return_persisted:
            self._persist_balance()
            self._return_persisted = True
        self.game.credited = True


    def _complete_chip_return(self):
        if self.game.stage not in ('returning','credit_pending'): return
        self.game.stage = 'credit_pending'
        try: self._credit_round_return()
        except Exception as exc:
            messagebox.showerror('余额保存失败',str(exc),parent=self)
            self._refresh()
            return
        self.canvas.delete('returned_chips')
        self.game.stage = 'sweeping'
        self._moving = True
        self._refresh()
        # UTH: credit only after the chips arrive, then sweep all cards right.
        def frame(step):
            self.canvas.move('table_tiles', (1150+100)/13, 0)
            if step < 13: self._schedule(16,frame,step+1)
            else:
                self._dealt.clear()
                self._face_up.clear()
                self.canvas.delete('table_tiles')
                self._expand_table(0.0,self._swap_shoe)
        frame(1)


    def _create_shoe_panel(self):
        c = self.canvas
        c.delete('shoe_panel')
        c.create_rectangle(22, 190, 1128, 309, fill=ROOT_BG, outline='#65784B', tags='shoe_panel')
        c.create_line(25, 191, 1125, 191, fill='#E0C879', width=2, tags='shoe_panel')
        c.create_line(25, 308, 1125, 308, fill='#0C241B', width=2, tags='shoe_panel')
        self._text(52, 209, '牌靴', 13, GOLD, anchor='w', tags='shoe_panel')
        self.shoe_label = self._text(790, 209, '32 / 32', 12, PANEL_BG, anchor='e', tags='shoe_panel')
        self.dice_label = self._text(1073, 272, '', 9, PANEL_BG, tags='shoe_panel')
        self._dice_equation_items = [
            self._text(x, 244, text, 11, color, tags='shoe_panel')
            for x, text, color in (
                (1023, '1', '#%02x%02x%02x' % GD_DICE_COLORS[0]),
                (1037, '+', PANEL_BG),
                (1051, '1', '#%02x%02x%02x' % GD_DICE_COLORS[1]),
                (1065, '+', PANEL_BG),
                (1079, '1', '#%02x%02x%02x' % GD_DICE_COLORS[2]),
                (1093, '=', PANEL_BG),
                (1115, '3', GOLD))]




# Compatibility aliases for launchers importing a previous class name.
ClassicPaiGowGUIV9 = ClassicPaiGowGUI
ClassicPaiGowGUIV10 = ClassicPaiGowGUI


def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        return ClassicPaiGowGUI(parent, balance=actual_balance, user=actual_user,
                               on_back=on_back, on_balance_change=on_balance_change)
    root = tk.Tk()
    root.title('经典牌九')
    root.geometry(WINDOW_GEOMETRY)
    root.resizable(False, False)
    page = ClassicPaiGowGUI(root, balance=actual_balance, user=actual_user,
                           on_back=on_back, on_balance_change=on_balance_change)
    page.pack(fill='both', expand=True)
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page


if __name__ == '__main__':
    main()
