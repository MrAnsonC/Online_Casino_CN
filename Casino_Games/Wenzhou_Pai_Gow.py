"""Wenzhou Pai Gow with the supplied Classic Pai Gow UI.

Run: python Wenzhou_Pai_Gow.py
Requires Python 3, Tkinter and Pillow. Guest mode works standalone;
named accounts use the original encrypted A_Tools account storage.
The main(...), build_pai_gow_page(...) and start_pai_gow_gui(...) APIs are retained.
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
import math
import tkinter as tk
from tkinter import messagebox, simpledialog
from dataclasses import dataclass
import time
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
GD_DICE_COLORS = ((47, 127, 235), (224, 64, 59))  # Blue die, red die.

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
    RADIUS = .085 * GD_BOWL_SCALE
    HEIGHT = .128 * GD_BOWL_SCALE

    def __init__(self, values=None, rng=None):
        self.rng = rng or random.SystemRandom()
        values = values or [self.rng.randint(1, 6) for _ in range(2)]
        self.dice = [GoldenRigidDie(-GoldenRigidDie.EDGE*.7, values[0]),
                     GoldenRigidDie(GoldenRigidDie.EDGE*.7, values[1])]
        self.color = (239, 187, 57)
        self.origin = self.velocity = (0., 0., 0.)
        self.collision_count = 0
        self.durations = []
        self.randomize_positions()

    def randomize_positions(self):
        """Place both cubes flat with independent positions and headings."""
        for _ in range(256):
            for die in self.dice:
                angle = self.rng.uniform(0, math.tau)
                radius = math.sqrt(self.rng.random())*(self.RADIUS-die.EDGE)
                die.p = (radius*math.cos(angle), radius*math.sin(angle), die.HALF)
                die.q = _gd_rotate(die.q, (0., 0., 1.), self.rng.uniform(0, math.tau))
                die.v = die.omega = (0., 0., 0.)
            if self.landing_error() is None and _gd_overlap(*self.dice) is None:
                return
        # A bounded fallback still has random heading and preserves rolled faces.
        heading = self.rng.uniform(0, math.tau)
        for die, sign in zip(self.dice, (-1, 1)):
            die.p = (sign*.032, 0., die.HALF)
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
        a, b = self.dice
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
            if not _gd_collide_dice(*self.dice):
                break
            self.collision_count += 1
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
        """Only restore a complete, flat, non-overlapping pair of saved bodies."""
        try:
            if state.get('version') != 1 or len(state['dice']) != 2:
                return None
            bowl = cls.__new__(cls)
            bowl.rng, bowl.color = random.SystemRandom(), (239, 187, 57)
            bowl.origin = bowl.velocity = (0.,0.,0.)
            bowl.collision_count, bowl.durations = 0, []
            bowl.dice = [GoldenRigidDie(0), GoldenRigidDie(0)]
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
    """Golden Dice dome and ceramic dish, with one blue die and one red die."""
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
    for die, color in zip(bowl.dice, GD_DICE_COLORS):
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
                face(dot, (250, 247, 238, 255), paint_depth=face_depth)
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



class Dice:
    def __init__(self):
        self.value = 1

    def roll(self):
        self.value = secrets.randbelow(6) + 1
        return self.value

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

def is_named_pair(t1, t2):
    return t1.group == t2.group

@dataclass(frozen=True)
class WenzhouHandValue:
    """Two-tile Wenzhou Pai Gow value.

    named_rank:
        1..13 for the traditional Wenzhou named combinations, where 1 is best.
        None for an ordinary 0..9 point hand.
    points:
        Fixed dot total modulo 10.  Gee Joon tiles are NOT semi-wild here.
    high_single_rank:
        1..7 according to the Wenzhou single-tile ranking, where 1 is best.
        Ordinary zero has no single-tile rank and therefore uses 0.
    """
    name: str
    named_rank: int | None
    points: int
    high_single_rank: int

    @property
    def key(self):
        # Every named combination outranks every ordinary point hand.
        if self.named_rank is not None:
            return (1, 14 - self.named_rank, 8 - self.high_single_rank)
        if self.points == 0:
            return (0, 0, 0)
        return (0, self.points, 8 - self.high_single_rank)

WENZHOU_SINGLE_RANK = {
    # 1 = strongest.  Several physical tiles intentionally share one level.
    'Teen': 1,
    'Day': 2,
    'Yun': 3,
    'Gor': 4,
    'Mooy': 5,
    'Chong': 5,
    'Bon': 5,
    'Foo': 6,
    'Ping': 6,
    'Tit': 6,
    'Look': 6,
    'Chop Gow': 7,
    'Chop Bot': 7,
    'Chop Chit': 7,
    'Chop Ng': 7,
    'Gee Joon': 7,
}

WENZHOU_PAIR_RANK = {
    # Wenzhou grouping: equal numeric rank means equal pair class.
    'Teen': (1, '双天'),
    'Day': (2, '双地'),
    'Gee Joon': (3, '至尊'),
    'Yun': (4, '双人'),
    'Gor': (5, '双鹅'),
    'Mooy': (6, '双梅'),
    'Chong': (6, '双长三'),
    'Bon': (6, '双板凳'),
    'Foo': (7, '双斧头'),
    'Ping': (7, '双红头十'),
    'Tit': (7, '双高脚七'),
    'Look': (7, '双零霖六'),
    'Chop Gow': (8, '双杂九'),
    'Chop Bot': (8, '双杂八'),
    'Chop Chit': (8, '双杂七'),
    'Chop Ng': (8, '双杂五'),
}

def wenzhou_single_rank(tile):
    return WENZHOU_SINGLE_RANK[tile.group]

def ordered_wenzhou_hand(hand):
    """Put the stronger single tile first; ties keep a deterministic order."""
    return sorted(
        hand,
        key=lambda t: (wenzhou_single_rank(t), -t.dots, t.uid),
    )

def evaluate_wenzhou_hand(hand):
    """Evaluate one two-tile Wenzhou Pai Gow hand.

    Wenzhou rules used here:
      * Big Chicken 6 / Small Chicken 3 are fixed; no Gee Joon wild conversion.
      * Named combinations outrank ordinary point hands.
      * Wenzhou pair ranking starts 双天, 双地, 至尊.
      * The Wenzhou table uses 天九王, 天杠, 地杠, 天九, 地九.
      * Ordinary hands compare points first, then the strongest single-tile level.
      * Ordinary 0 has no single-tile level.
    """
    if len(hand) != 2:
        raise ValueError('温州牌九每门必须恰好2张牌')

    t1, t2 = hand
    groups = {t1.group, t2.group}
    dots = {t1.dots, t2.dots}
    high_rank = min(wenzhou_single_rank(t1), wenzhou_single_rank(t2))

    if is_named_pair(t1, t2):
        rank, name = WENZHOU_PAIR_RANK[t1.group]
        return WenzhouHandValue(name, rank, (t1.dots + t2.dots) % 10, high_rank)

    # Traditional Wenzhou named combinations.  Note that the published Wenzhou
    # ranking uses 天九王 but does not insert a separate 地王 class.
    if 'Teen' in groups and 9 in dots:
        return WenzhouHandValue('天九王', 9, 1, high_rank)
    if 'Teen' in groups and 8 in dots:
        return WenzhouHandValue('天杠', 10, 0, high_rank)
    if 'Day' in groups and 8 in dots:
        return WenzhouHandValue('地杠', 11, 0, high_rank)
    if 'Teen' in groups and 7 in dots:
        return WenzhouHandValue('天九', 12, 9, high_rank)
    if 'Day' in groups and 7 in dots:
        return WenzhouHandValue('地九', 13, 9, high_rank)

    points = (t1.dots + t2.dots) % 10
    if points == 0:
        high_rank = 0
    return WenzhouHandValue(f'{points}点', None, points, high_rank)

def compare_wenzhou_hands(player_hand, dealer_hand):
    """Return 1 if player is larger, -1 if smaller, 0 if the comparison ties.

    A returned tie is settled as 惜败 (banker advantage).  Ordinary 0 vs 0 is
    also a banker win and intentionally has no single-tile tie break.
    """
    p = evaluate_wenzhou_hand(player_hand)
    d = evaluate_wenzhou_hand(dealer_hand)
    if p.key > d.key:
        return 1
    if p.key < d.key:
        return -1
    return 0


class WenzhouArtwork:
    SELECT_BORDER = GOLD

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
        """温州牌九图解玩法说明（奶油白配色，固定 1000×650）。"""
        parent = self.winfo_toplevel()

        existing = getattr(self, '_wenzhou_instruction_window', None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass

        dialog = tk.Toplevel(parent)
        self._wenzhou_instruction_window = dialog
        dialog.title('温州牌九 · 完整图解玩法与32张骨牌')
        dialog.configure(bg='#faf5e8')
        dialog.resizable(False, False)
        dialog.transient(parent)

        # ================================================================
        # 固定窗口尺寸
        # ================================================================
        win_w = 1000
        win_h = 650

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

        font_name = 'Microsoft YaHei UI'

        # ================================================================
        # 配色：奶油白体系
        # ================================================================
        BG = '#faf5e8'          # 主背景（奶油白）
        HEADER = '#f1e7cd'      # 顶栏（深一档奶油）
        SIDEBAR = '#f2e8d0'     # 左侧栏
        PANEL = '#fffdf7'       # 卡片底（近白）
        PANEL_2 = '#f5ecd6'     # 卡片内嵌
        ROW_ALT = '#faf3e3'     # 表格隔行
        BORDER = '#c9b88a'      # 柔和金线

        GOLD_BAR = '#e7d36c'    # 表头亮金
        GOLD = '#a8842c'        # 深金（浅底可见）
        TEXT = '#3a2f1e'        # 主文字（深棕）
        MUTED = '#7a6a50'       # 次要文字

        GREEN = '#2f7d3a'
        RED = '#b83a3a'
        BLUE = '#2c6e9f'

        FONT_SMALL = 11
        FONT_NORMAL = 12
        FONT_MEDIUM = 13
        FONT_LARGE = 15
        FONT_TITLE = 17

        # ================================================================
        # 顶部标题栏
        # ================================================================
        header = tk.Frame(dialog, bg=HEADER, height=76)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header, text='温州牌九 · 完整图解说明',
            font=(font_name, FONT_TITLE, 'bold'), fg=GOLD, bg=HEADER,
        ).place(x=22, y=8)
        tk.Label(
            header, text='32张骨牌 · 两骰四门 · 牌型大小 · 鸡牌固定 · 下注赔率',
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

        def _scroll_units(event):
            try:
                return int(-1 * (event.delta / 120))
            except Exception:
                return 0

        def _on_mousewheel(event):
            units = _scroll_units(event)
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
                font=(font_name, FONT_MEDIUM, 'bold'),
                fg=TEXT, bg=PANEL, anchor='w', justify=tk.LEFT,
            ).pack(fill=tk.X)
            tk.Label(
                text_box, text=body,
                font=(font_name, FONT_SMALL),
                fg=MUTED, bg=PANEL, anchor='w',
                justify=tk.LEFT, pady=5,
            ).pack(fill=tk.X)

        def table_block(parent_frame, title, rows):
            block = tk.Frame(
                parent_frame, bg=PANEL_2,
                highlightbackground=BORDER, highlightthickness=1, bd=0,
            )
            tk.Label(
                block, text=title,
                font=(font_name, FONT_SMALL, 'bold'),
                fg=TEXT, bg=GOLD_BAR, anchor='w', padx=14, pady=7,
            ).pack(fill=tk.X)

            grid = tk.Frame(block, bg=PANEL_2)
            grid.pack(fill=tk.BOTH, expand=True)
            grid.grid_columnconfigure(0, weight=1)
            grid.grid_columnconfigure(1, minsize=150)

            for i, (cond, val) in enumerate(rows):
                bg_row = ROW_ALT if i % 2 == 0 else PANEL_2
                tk.Label(
                    grid, text=cond,
                    font=(font_name, FONT_SMALL),
                    fg=TEXT, bg=bg_row,
                    anchor='w', justify=tk.LEFT, padx=16, pady=8,
                ).grid(row=i, column=0, sticky='nsew', padx=(0, 1), pady=(0, 1))
                tk.Label(
                    grid, text=val,
                    font=(font_name, FONT_SMALL, 'bold'),
                    fg=GOLD, bg=bg_row,
                    anchor='center', padx=8, pady=8,
                ).grid(row=i, column=1, sticky='nsew', pady=(0, 1))
            return block

        def preview_canvas(parent_frame, width, height):
            cv = tk.Canvas(
                parent_frame, width=width, height=height,
                bg=PANEL, highlightthickness=0,
            )
            cv.pack(padx=12, pady=(4, 12))
            return cv

        # 奶油白底上用黑色牌面更醒目
        def draw_tile_on(canvas, tile, cx, cy, scale=0.62):
            old = self._render_tile_theme_override
            self._render_tile_theme_override = 'black'
            try:
                self._instruction_tile(canvas, tile, cx, cy, scale=scale)
            finally:
                self._render_tile_theme_override = old

        # ================================================================
        # 数据准备
        # ================================================================
        tiles = build_pai_gow_set()
        by_group = {}
        for _t in tiles:
            by_group.setdefault(_t.group, []).append(_t)

        def find_pair(group):
            return by_group[group][:2]

        def find_named(name):
            for i, a in enumerate(tiles):
                for b in tiles[i + 1:]:
                    if evaluate_wenzhou_hand([a, b]).name == name:
                        return [a, b]
            raise LookupError(name)

        def find_ordinary(points, avoid=()):
            for i, a in enumerate(tiles):
                for b in tiles[i + 1:]:
                    if a.group in avoid or b.group in avoid:
                        continue
                    v = evaluate_wenzhou_hand([a, b])
                    if v.named_rank is None and v.points == points:
                        return [a, b]
            raise LookupError(points)

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
        # 各主题页面
        # ================================================================
        def page_rules():
            section_title('玩法与流程', '两骰 · 四门 · 每门2张')

            card = make_card(title='基本流程')
            add_rule(
                card, '1. 下注',
                '顺门、出门、到门各有两个下注格：获胜 / 惜败。\n'
                '同一门只能选一边下注，不能同时下两边。'
            )
            add_rule(
                card, '2. 摇骰定门',
                '按下「开牌」或 Enter 后摇两颗骰子，取总点数除以 4 的余数：\n'
                '余1 → 庄家先派；余2 → 顺门先派；余3 → 出门先派；\n'
                '整除（余0，等同余4）→ 到门先派。'
            )
            add_rule(
                card, '3. 派牌顺序',
                '从起始门开始按「庄家 → 顺门 → 出门 → 到门」循环。\n'
                '每次从牌靴最左侧取 2 张作为一个门的手牌。\n'
                '一门派完立即逐张翻牌，再派下一门。'
            )
            add_rule(
                card, '4. 结算',
                '顺门、出门、到门分别与庄家比较大小。\n'
                '严格大于庄家 → 该门手牌背景变绿（获胜）；\n'
                '小于或等于庄家 → 背景变红（惜败，庄家占优）。\n'
                '对应下注格按赔率派彩：获胜 0.99:1，惜败 0.93:1。'
            )
            add_rule(
                card, '5. 换牌靴',
                '点击「再来一局」后，返还筹码先回到底栏，余额入账，再将本局牌向右收走；\n'
                '旧牌靴向右退出，同时一副全新 32 张牌从左进入，\n'
                '牌面颜色在黑色 / 白色之间交替。'
            )

        def page_dice():
            section_title('两骰定门', '总点数 ÷ 4 取余')

            card = make_card(title='两骰余数决定先派哪一门')
            # 上下结构：上部两骰 + 结果，下部四门
            cv = preview_canvas(card, CANVAS_W, 330)

            # ---- 上半区：两骰 + 计算 ----
            draw_die(cv, 300, 55, 3)
            draw_die(cv, 380, 55, 4)
            cv.create_text(340, 118, text='3 + 4 = 7',
                        font=(font_name, FONT_LARGE, 'bold'), fill=TEXT)
            cv.create_text(340, 148,
                        text='7 ÷ 4 余 3 → 出门先派',
                        font=(font_name, FONT_MEDIUM, 'bold'), fill=BLUE)

            # 分隔线
            cv.create_line(80, 172, 600, 172, fill=BORDER, width=1)

            # ---- 下半区：四门 ----
            doors = [('庄家', '余 1'), ('顺门', '余 2'),
                    ('出门', '余 3'), ('到门', '余 0 / 余 4')]
            cell_w = 92
            gap = 15
            total_w = len(doors) * cell_w + (len(doors) - 1) * gap
            start_x = (CANVAS_W - total_w) / 2
            row_y0 = 195
            row_y1 = 255

            for i, (name, cond) in enumerate(doors):
                x0 = start_x + i * (cell_w + gap)
                highlight = (i == 2)
                fill = '#f6e2a8' if highlight else '#faf3e0'
                edge = '#a8842c' if highlight else '#8b7658'
                cv.create_rectangle(x0, row_y0, x0 + cell_w, row_y1,
                                    fill=fill, outline=edge, width=2)
                cv.create_text(x0 + cell_w / 2, row_y0 + 18, text=name,
                            font=(font_name, FONT_SMALL, 'bold'), fill='#3a2f1e')
                cv.create_text(x0 + cell_w / 2, row_y0 + 42, text=cond,
                            font=(font_name, 9), fill='#7a6a50')
                if i < 3:
                    cv.create_text(x0 + cell_w + gap / 2, (row_y0 + row_y1) / 2,
                                text='→', font=('Arial', 14, 'bold'), fill=GOLD)

            # ---- 底部提示 ----
            cv.create_text(CANVAS_W / 2, 282,
                        text='示例起手顺序：出门 → 到门 → 庄家 → 顺门',
                        font=(font_name, FONT_NORMAL, 'bold'), fill=GREEN)
            cv.create_text(CANVAS_W / 2, 308,
                        text='每派完一门：牌背缩窄 → 翻成牌面 → 展开 → 再派下一门',
                        font=(font_name, FONT_SMALL), fill=MUTED)

        def page_tiles():
            section_title('一副温州牌九 · 32张骨牌', '16组 × 每组2张')

            card = make_card()
            groups = sorted(
                by_group,
                key=lambda g: (WENZHOU_PAIR_RANK[g][0], WENZHOU_PAIR_RANK[g][1], g),
            )
            cols = 3
            cell_w = 222
            cell_h = 140
            rows = (len(groups) + cols - 1) // cols
            cv = preview_canvas(card, cols * cell_w + 10, rows * cell_h + 10)

            for idx, group in enumerate(groups):
                row, col = divmod(idx, cols)
                x0 = 5 + col * cell_w
                y0 = 5 + row * cell_h

                pair = find_pair(group)
                rank, name = WENZHOU_PAIR_RANK[group]

                cv.create_rectangle(x0, y0, x0 + cell_w - 10, y0 + cell_h - 10,
                                    fill=PANEL_2, outline=BORDER)

                draw_tile_on(cv, pair[0], x0 + 42, y0 + 74, scale=0.58)
                draw_tile_on(cv, pair[1], x0 + 82, y0 + 74, scale=0.58)

                cv.create_text(x0 + 112, y0 + 28, anchor='w', text=name,
                            font=(font_name, FONT_SMALL, 'bold'), fill=GOLD)
                cv.create_text(x0 + 112, y0 + 52, anchor='w',
                            text=f'牌型级别 {rank}',
                            font=(font_name, 9), fill=MUTED)
                cv.create_text(x0 + 112, y0 + 76, anchor='w',
                            text=' + '.join(f'{t.a}-{t.b}' for t in pair),
                            font=(font_name, 9), fill=MUTED)
                cv.create_text(x0 + 112, y0 + 100, anchor='w',
                            text='共2张实体牌',
                            font=(font_name, 9), fill=GREEN)

            note = make_card(title='牌面构成')
            add_rule(
                note, '21 种牌面 · 32 张实体牌',
                '11 种牌面各出现 2 次（文牌对）；\n'
                '10 种牌面各出现 1 次（武牌对，含至尊的两张不同形状）。'
            )

        def page_ranks():
            section_title('经典牌型大小', '完整 21 级 · 由高到低')

            # ================================================================
            # 完整牌型表（21 级）
            # group=None 时按命名组合查找，否则用该组的两个实体牌
            # ================================================================
            row_data = [
                # (级别, group,  牌型名,   说明)
                (1,  'Teen',       '双天',     '两张天牌，最高牌型'),
                (2,  'Day',        '双地',     '两张地牌'),
                (3,  'Gee Joon',   '至尊',     '大鸡六 + 小鸡'),
                (4,  'Yun',        '双人',     '两张人牌'),
                (5,  'Gor',        '双鹅',     '两张鹅牌'),
                (6,  'Mooy',       '双梅',     '两张梅牌'),
                (6,  'Chong',      '双长三',   '两张长三'),
                (6,  'Bon',        '双板凳',   '两张板凳'),
                (7,  'Foo',        '双斧头',   '两张斧头'),
                (7,  'Ping',       '双红头十', '两张红头十'),
                (7,  'Tit',        '双高脚七', '两张高脚七'),
                (7,  'Look',       '双零霖六', '两张零霖六'),
                (8,  'Chop Gow',   '双杂九',   '3-6 与 4-5 各一张'),
                (8,  'Chop Bot',   '双杂八',   '3-5 与 2-6 各一张'),
                (8,  'Chop Chit',  '双杂七',   '3-4 与 2-5 各一张'),
                (8,  'Chop Ng',    '双杂五',   '1-4 与 3-2 各一张'),
                (9,  None,         '天九王',   '天牌 + 任意 9 点'),
                (10, None,         '天杠',     '天牌 + 任意 8 点'),
                (11, None,         '地杠',     '地牌 + 任意 8 点'),
                (12, None,         '天九',     '天牌 + 任意 7 点'),
                (13, None,         '地九',     '地牌 + 任意 7 点'),
            ]

            card = make_card(title='完整牌型表（按大小排序）')

            # ================================================================
            # 表格几何
            # ================================================================
            row_h = 36
            header_h = 36
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

            # ================================================================
            # 表头
            # ================================================================
            headers = ['级别', '牌型', '示例', '组成', '说明']
            for i, h in enumerate(headers):
                x0 = col_x[i]
                x1 = x0 + col_w[i]
                cv.create_rectangle(x0, table_y0, x1, table_y0 + header_h,
                                    fill=GOLD_BAR, outline=BORDER)
                cv.create_text((x0 + x1) / 2, table_y0 + header_h / 2,
                            text=h, font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)

            # ================================================================
            # 数据行
            # ================================================================
            old_theme = self._render_tile_theme_override
            self._render_tile_theme_override = 'black'
            try:
                for idx, (rank, group, name, note) in enumerate(row_data):
                    y0 = table_y0 + header_h + idx * row_h
                    y1 = y0 + row_h
                    cy = (y0 + y1) / 2
                    bg = ROW_ALT if idx % 2 == 0 else PANEL

                    # 单元格背景
                    for i, w in enumerate(col_w):
                        cv.create_rectangle(col_x[i], y0, col_x[i] + w, y1,
                                            fill=bg, outline=BORDER)

                    # 级别
                    cv.create_text(col_x[0] + col_w[0] / 2, cy, text=str(rank),
                                font=(font_name, FONT_SMALL, 'bold'), fill=GOLD)

                    # 牌型名
                    cv.create_text(col_x[1] + col_w[1] / 2, cy, text=name,
                                font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)

                    # 取该行的两张实体牌
                    if group is not None:
                        hand = by_group[group][:2]
                    else:
                        hand = find_named(name)

                    # 示例：两张水平迷你骨牌
                    sample_cx = col_x[2] + col_w[2] / 2
                    gap = 72
                    self._instruction_tile(cv, hand[0], sample_cx - gap / 2, cy,
                                        horizontal=True, scale=0.14)
                    self._instruction_tile(cv, hand[1], sample_cx + gap / 2, cy,
                                        horizontal=True, scale=0.14)

                    # 组成
                    comp_text = ' + '.join(f'{t.a}-{t.b}' for t in hand)
                    cv.create_text(col_x[3] + col_w[3] / 2, cy, text=comp_text,
                                font=(font_name, FONT_SMALL), fill=MUTED)

                    # 说明
                    cv.create_text(col_x[4] + 8, cy, anchor='w', text=note,
                                font=(font_name, FONT_SMALL), fill=MUTED)
            finally:
                self._render_tile_theme_override = old_theme

            # ================================================================
            # 底部提示
            # ================================================================
            note_card = make_card(title='牌型说明')
            add_rule(
                note_card, '固定牌型 vs 普通点数',
                '固定牌型（双天 ~ 地九）一定大于普通 0～9 点。\n'
                '玩家必须先按牌型级别比较，再考虑普通点数。'
            )
            add_rule(
                note_card, '同级别比较',
                '同名级别内（例如 双梅 / 双长三 / 双板凳 同为 6 级），\n'
                '两张牌的点数分布相同，视为同级；如需再分，则看最大单张级别。'
            )
            add_rule(
                note_card, '天九王没有地王',
                '温州牌九只有 天九王，没有单独设立的 地王 级别。\n'
                '地牌与 9 点组合归入普通点数，按 9 点比较。'
            )

        def page_chicken():
            section_title('鸡牌固定点数', '大鸡六 = 6；小鸡 = 3')

            card = make_card(title='温州牌九的鸡牌不使用百搭')
            big = self._instruction_find_tile(tiles, group='Gee Joon', shape=(2, 4))
            small = self._instruction_find_tile(tiles, group='Gee Joon', shape=(1, 2))

            cv = preview_canvas(card, CANVAS_W, 210)
            draw_tile_on(cv, big, 150, 92, scale=0.82)
            draw_tile_on(cv, small, 330, 92, scale=0.82)

            cv.create_text(150, 178, text='大鸡六 = 固定 6 点',
                        font=(font_name, FONT_NORMAL, 'bold'), fill=GREEN)
            cv.create_text(330, 178, text='小鸡 = 固定 3 点',
                        font=(font_name, FONT_NORMAL, 'bold'), fill=GREEN)
            cv.create_text(535, 68,
                        text='例：小鸡 3 + 高脚七 7 = 10 → 普通 0 点',
                        font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)
            cv.create_text(535, 105,
                        text='不会把小鸡从 3 改成 6\n去制造别的点数',
                        font=(font_name, FONT_SMALL), fill=MUTED)

            note = make_card()
            add_rule(
                note, '固定点数',
                '至尊拆开后，大鸡六永远按 6 点计，小鸡永远按 3 点计。\n'
                '这里不使用赌场大牌九中「3 / 6 半百搭」的规则。'
            )
            add_rule(
                note, '统一算法',
                '牌桌与图解采用相同的温州牌型和比牌顺序。'
            )

        def page_points():
            section_title('普通点数与同点比较', '固定牌型 > 普通点数')

            samples = [
                (find_ordinary(9), '普通 9 点'),
                (find_ordinary(7), '普通 7 点'),
                (find_ordinary(0), '普通 0 点'),
            ]

            card = make_card(title='普通 0～9 点')
            cv = preview_canvas(card, CANVAS_W, 220)

            for i, (hand, label) in enumerate(samples):
                cx = 115 + i * 225
                draw_tile_on(cv, hand[0], cx - 25, 84, scale=0.62)
                draw_tile_on(cv, hand[1], cx + 25, 84, scale=0.62)
                cv.create_text(cx, 158, text=label,
                            font=(font_name, FONT_NORMAL, 'bold'), fill=GOLD)
                cv.create_text(cx, 182,
                            text=evaluate_wenzhou_hand(hand).name,
                            font=(font_name, FONT_SMALL), fill=MUTED)

            note = make_card(title='比较顺序')
            add_rule(
                note, '第一步：看牌型',
                '先看是否形成固定牌型（双天、双地、至尊、天九王、天杠、\n'
                '地杠、天九、地九等）。固定牌型一定大于普通 0～9 点。'
            )
            add_rule(
                note, '第二步：比点数',
                '无固定牌型时，两张牌点数相加保留个位，先比点数大小。'
            )
            add_rule(
                note, '第三步：比最大单张',
                '点数相同时，比较两张牌中级别最高的那一张（1 = 最强）。\n'
                '单张级别：天 > 地 > 人 > 鹅 > 梅 / 长三 / 板凳 >\n'
                '斧头 / 红头十 / 高脚七 / 零霖六 >\n'
                '杂九 / 杂八 / 杂七 / 杂五 / 至尊。'
            )
            add_rule(
                note, '庄家占优',
                '若牌型相同、点数相同、最大单张级别也相同，视为庄家占优，\n'
                '玩家归「惜败」。普通 0 点对普通 0 点不再比单张，直接判惜败。',
                accent=RED,
            )

        def page_betting():
            section_title('下注区与赔率', '每门两格：获胜 / 惜败')

            card = make_card(title='下注区示意')
            cv = preview_canvas(card, CANVAS_W, 260)

            for column, door in enumerate((1, 2, 3)):
                x0 = 12 + column * 224
                cv.create_rectangle(x0, 15, x0 + 208, 240,
                                    fill=PANEL_2, outline=BORDER)
                cv.create_text(x0 + 104, 40, text=self.POSITION_NAMES[door],
                               font=(font_name, FONT_MEDIUM, 'bold'), fill=GOLD)
                for center, title, odds in ((x0 + 54, '获胜', '0.99 : 1'),
                                             (x0 + 154, '惜败', '0.93 : 1')):
                    cv.create_text(center, 109, text=title + '\n' + odds,
                                   font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)
                    cv.create_oval(center - 30, 142, center + 30, 202,
                                   fill=PANEL, outline=GOLD, width=2)
                    cv.create_oval(center - 26, 146, center + 26, 198,
                                   outline=BORDER)
                    cv.create_text(center, 172, text=title,
                                   font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)

            note = make_card(title='赔率与限额')
            add_rule(
                note, '返还倍数',
                f'获胜格总返还 = 本金 × {self.WIN_MULTIPLIER:.2f}（净盈利 0.99）\n'
                f'惜败格总返还 = 本金 × {self.LOSE_MULTIPLIER:.2f}（净盈利 0.93）'
            )
            add_rule(
                note, '限红',
                f'正常模式：${self.NORMAL_MIN_BET:,} – ${self.NORMAL_MAX_BET:,}\n'
                f'高额模式：${self.HIGH_MIN_BET:,} – ${self.HIGH_MAX_BET:,}\n'
                '$0 空注仍可开局。'
            )
            add_rule(
                note, '操作',
                '左键点击下注圆圈或上方赔率文字 → 投入当前选中筹码\n'
                '右键点击下注圆圈或上方赔率文字 → 清除该侧下注\n'
                '「清除」 → 清空本局所有下注\n'
                '「重复下注」 → 按上局金额重新下注'
            )

        def page_settle():
            section_title('结算颜色与换牌靴', '绿 = 获胜；红 = 惜败')

            card = make_card(title='手牌颜色说明')
            add_rule(
                card, '绿色手牌背景',
                '该门手牌严格大于庄家 → 手牌背景变绿（获胜）。',
                accent='#33cc33',
            )
            add_rule(
                card, '红色手牌背景',
                '该门手牌小于或等于庄家 → 手牌背景变红（惜败，庄家占优）。',
                accent='#e74c3c',
            )
            add_rule(
                card, '颜色与下注无关',
                '手牌颜色只表示该门与庄家的牌面比较结果，与有没有下注无关。'
            )

            flow = make_card(title='「再来一局」换牌靴流程')
            add_rule(
                flow, '步骤 1',
                '返还的本金与盈利筹码先回到底栏，并计入余额；\n'
                '随后本局 8 张活牌向右收走。'
            )
            add_rule(
                flow, '步骤 2',
                '旧牌靴向右退出屏幕，同时下一副完整 32 张牌从左进入。'
            )
            add_rule(
                flow, '步骤 3',
                '新牌靴就位后重新开放下注；牌面颜色在黑色 / 白色之间交替。'
            )

            op = make_card(title='一局操作顺序')
            add_rule(
                op, '完整流程',
                '下注 → 开牌（Enter）→ 摇两骰 → 四门依序派牌 / 开牌 →\n'
                '与庄家比较 → 派彩结算 → 再来一局换新牌靴。'
            )

        # ================================================================
        # 左侧主题按钮
        # ================================================================
        themes = [
            ('玩法与流程',     page_rules),
            ('两骰定门',       page_dice),
            ('32张骨牌图鉴',   page_tiles),
            ('牌型大小',       page_ranks),
            ('鸡牌固定点数',   page_chicken),
            ('普通点数与比牌', page_points),
            ('下注与赔率',     page_betting),
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
                self._wenzhou_instruction_window = None
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


def money(value):
    """Use the Classic table's cent rounding for bets and returns."""
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


POSITION_NAMES = {0: '庄家', 1: '顺门', 2: '出门', 3: '到门'}
BET_SIDES = ('win', 'lose')
NORMAL_MIN_BET, NORMAL_MAX_BET = 10, 25000
HIGH_MIN_BET, HIGH_MAX_BET = 100, 100000
WIN_MULTIPLIER, LOSE_MULTIPLIER = 1.99, 1.93
HIGH_CHIPS = [(100, BLACK), (500, '#FF7DDA'), (1000, TEXT),
              (5000, RED), (10000, '#00fbff'), (50000, '#00ffae')]


def settle_wenzhou_hand(hand, dealer_hand, win_stake=0, lose_stake=0):
    """A tie belongs to 惜败; the winning side receives stake plus profit."""
    comparison = compare_wenzhou_hands(hand, dealer_hand)
    side = 'win' if comparison > 0 else 'lose'
    multiplier = WIN_MULTIPLIER if side == 'win' else LOSE_MULTIPLIER
    winning_stake = win_stake if side == 'win' else lose_stake
    returned = money(Decimal(str(winning_stake)) * Decimal(str(multiplier)))
    return dict(comparison=comparison, side=side, returned=returned,
                net=money(returned - win_stake - lose_stake))


class WenzhouTableGame:
    """Original Wenzhou rules, kept separate from the Classic table artwork."""
    SEATS = (1, 2, 3)
    POSITIONS = (0, 1, 2, 3)
    BET_KEYS = tuple((door, side) for door in (1, 2, 3) for side in BET_SIDES)

    def __init__(self):
        self.stage = 'betting'
        self.high_bet_mode = False
        self.bets = self.empty_bets()
        self.last_bets = None
        self.last_return = 0.0
        self.reset_hands()
        self.new_shoe()

    @classmethod
    def empty_bets(cls):
        return {key: 0.0 for key in cls.BET_KEYS}

    @staticmethod
    def shuffled_tiles():
        tiles = build_pai_gow_set()
        for i in range(len(tiles) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            tiles[i], tiles[j] = tiles[j], tiles[i]
        return tiles

    @property
    def min_bet(self):
        return HIGH_MIN_BET if self.high_bet_mode else NORMAL_MIN_BET

    @property
    def max_bet(self):
        return HIGH_MAX_BET if self.high_bet_mode else NORMAL_MAX_BET

    @property
    def total_bet(self):
        return money(sum(self.bets.values()))

    def reset_hands(self):
        self.hands, self.results = {}, {}
        self.dice, self.deal_order = [], []
        self.round_bets = self.empty_bets()
        self.bet_returns = self.empty_bets()
        self.winning_cells = set()
        self.credited = self.resolved = False

    def new_shoe(self):
        self.tiles = self.shuffled_tiles()
        self.stacks = [self.tiles[i * 2:i * 2 + 2] for i in range(16)]

    def side_blocked(self, door, side):
        opposite = 'lose' if side == 'win' else 'win'
        return self.bets.get((door, opposite), 0) > 0

    def validate_bets(self, layout, balance, *, require_min=False):
        if set(layout) != set(self.BET_KEYS):
            raise ValueError('下注须包含顺门、出门、到门的获胜／惜败六格。')
        if any(not math.isfinite(float(value)) or value < 0 for value in layout.values()):
            raise ValueError('下注金额必须为有效的非负数。')
        for door in self.SEATS:
            if layout[(door, 'win')] > 0 and layout[(door, 'lose')] > 0:
                raise ValueError(f'{POSITION_NAMES[door]}不能同时下注获胜与惜败。')
        total = money(sum(layout.values()))
        if total > self.max_bet:
            raise ValueError(f'本局下注合计最高 ${self.max_bet:,}。')
        if require_min and total and total < self.min_bet:
            raise ValueError(f'本局下注合计须在 ${self.min_bet:,} 至 ${self.max_bet:,} 之间，或为 $0。')
        if total > balance:
            raise ValueError('余额不足以支付本局全部门注。')
        return {key: money(layout[key]) for key in self.BET_KEYS}

    def add_bet(self, door, side, amount, balance):
        if self.stage != 'betting' or (door, side) not in self.bets:
            return False
        if self.side_blocked(door, side):
            return False
        if not math.isfinite(float(amount)) or amount <= 0:
            raise ValueError('筹码金额必须大于零。')
        layout = dict(self.bets)
        layout[(door, side)] = money(layout[(door, side)] + amount)
        self.bets = self.validate_bets(layout, balance)
        return True

    def start(self, balance):
        if self.stage != 'betting':
            raise ValueError('请先完成本局。')
        self.bets = self.validate_bets(self.bets, balance, require_min=True)
        self.reset_hands()
        self.round_bets = dict(self.bets)
        self.last_bets = dict(self.bets)
        self.last_return = 0.0
        self.stage = 'rolling'
        return money(balance - self.total_bet)

    def deal(self, dice):
        if self.stage != 'rolling':
            raise ValueError('请先开局摇骰。')
        if len(dice) != 2 or any(type(n) is not int or n not in range(1, 7) for n in dice):
            raise ValueError('温州牌九需要两颗有效骰子。')
        self.dice = list(dice)
        start = (sum(dice) - 1) % 4
        self.deal_order = [(start + i) % 4 for i in range(4)]
        self.hands = {door: ordered_wenzhou_hand(self.stacks[i])
                      for i, door in enumerate(self.deal_order)}
        self.stage = 'dealing'

    def settle(self):
        if self.resolved:
            return self.last_return
        if self.stage != 'dealing' or any(len(self.hands.get(pos, [])) != 2 for pos in self.POSITIONS):
            raise ValueError('庄家与三门都须派齐两张牌。')
        self.bet_returns = self.empty_bets()
        self.winning_cells = set()
        self.results = {}
        for door in self.SEATS:
            result = settle_wenzhou_hand(self.hands[door], self.hands[0],
                                        self.round_bets[(door, 'win')],
                                        self.round_bets[(door, 'lose')])
            self.results[door] = result
            key = (door, result['side'])
            self.winning_cells.add(key)
            self.bet_returns[key] = result['returned']
        self.last_return = money(sum(self.bet_returns.values()))
        self.resolved = True
        self.stage = 'settling'
        return self.last_return

    def next_round(self):
        if self.stage != 'sweeping' or not self.credited:
            return False
        self.reset_hands()
        self.bets = self.empty_bets()
        self.new_shoe()
        self.stage = 'betting'
        return True


class WenzhouPaiGowGUI(tk.Frame, WenzhouArtwork):
    """Classic Pai Gow table layout with the original two-tile Wenzhou game."""
    WIDTH, HEIGHT = 1150, 750
    ROOT_BG, PANEL_BG, HEADER_BG, TITLE_FG = ROOT_BG, PANEL_BG, HEADER_BG, TITLE_FG
    ZONE_COLORS = ('#2A5541', '#204536')
    POSITION_NAMES, BET_SIDES = POSITION_NAMES, BET_SIDES
    WIN_MULTIPLIER, LOSE_MULTIPLIER = WIN_MULTIPLIER, LOSE_MULTIPLIER
    NORMAL_MIN_BET, NORMAL_MAX_BET = NORMAL_MIN_BET, NORMAL_MAX_BET
    HIGH_MIN_BET, HIGH_MAX_BET = HIGH_MIN_BET, HIGH_MAX_BET
    SEAT_LEFT, SEAT_PITCH, SEAT_WIDTH = 22, 377, 352
    BET_CHIP_SCALE = 0.8

    def __init__(self, parent, balance=10000, user='Guest', on_back=None, on_balance_change=None):
        tk.Frame.__init__(self, parent, bg=ROOT_BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username, self.balance = user or 'Guest', money(balance)
        if self.username != 'Guest' and _ACCOUNT_ROOT is None:
            raise RuntimeError('请把此文件放回原项目内：正式账户需要 A_Tools/Account/secure_json.py。')
        self.on_back, self.on_balance_change = on_back, on_balance_change
        self.game = WenzhouTableGame()
        self.tile_theme = 'white' if secrets.randbelow(2) == 0 else 'black'
        self._render_tile_theme_override = None
        self.selected_chip = 10
        self._closing, self._jobs = False, set()
        self._dealt, self._wall_removed, self._face_up = set(), set(), set()
        self._moving, self._motion_count, self._chip_serial = False, 0, 0
        self._flip_state = None
        self.visual_chips, self.control_buttons = {}, {}
        self._restart_job, self._restart_seconds = None, 30
        self._round_credited = self._return_persisted = False
        self.golden_dice_bowl = None
        self._golden_dice_cup_photo = self._golden_dice_cup_item = None
        self._golden_dice_phase = 'idle'
        self._golden_dice_time = self._golden_dice_stable_time = 0.
        self._golden_dice_rest_anchor = None
        self.status = '选择筹码，点击获胜／惜败下注；Enter 开牌。'
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=ROOT_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0, width=self.WIDTH, height=self.HEIGHT)
        self._create_widgets()
        self._refresh()
        self.bind('<Configure>', self._center_table, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')
        self._enter_binding = self.winfo_toplevel().bind('<Return>', self._enter_action, add='+')

    @property
    def stage(self):
        return self.game.stage

    @property
    def bets(self):
        return self.game.bets

    @property
    def high_bet_mode(self):
        return self.game.high_bet_mode

    @property
    def game_in_progress(self):
        return self.game.stage != 'betting' or not self._idle()

    def _idle(self):
        return not self._moving and self._motion_count == 0

    def on_close(self):
        if self._closing:
            return
        self._cancel_restart()
        self._cancel_jobs()
        g = self.game
        # Closing during dice/deal animation must not discard a paid round.
        try:
            if g.stage not in ('betting', 'shoe_exchange'):
                if not g.resolved:
                    if not g.hands:
                        g.deal([secrets.randbelow(6) + 1 for _ in range(2)])
                    g.settle()
                self._credit_round_return()
            else:
                self._persist_balance()
        except Exception as exc:
            self.status = '余额保存失败，请重试关闭。'
            messagebox.showerror('余额保存失败', str(exc), parent=self)
            return
        self._closing = True
        dialog = getattr(self, '_wenzhou_instruction_window', None)
        if dialog is not None:
            try:
                dialog.destroy()
            except tk.TclError:
                pass
        try:
            self.winfo_toplevel().unbind('<Return>', self._enter_binding)
        except (tk.TclError, AttributeError):
            pass
        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            self.winfo_toplevel().destroy()

    def _create_widgets(self):
        c = self.canvas
        self._text(187, 44, '温州牌九', 16, GOLD)
        self._text(957, 44, 'Wenzhou Pai Gow', 14, GOLD)
        limit_tag = 'bet_limits'
        c.create_rectangle(22, 69, 349, 178, fill=ROOT_BG, outline=GOLD, width=2, tags=limit_tag)
        self.limit_title = self._text(185, 84, '下注上限', 12, PANEL_BG, tags=limit_tag)
        self.limit_values = []
        for i, title in enumerate(('合计最低', '合计最高', '每门张数')):
            x = 22 + i * 109
            c.create_rectangle(x, 101, x + 109, 137, outline='#77906B', tags=limit_tag)
            c.create_rectangle(x, 137, x + 109, 178, outline='#77906B', tags=limit_tag)
            self._text(x + 54.5, 119, title, 11, PANEL_BG, tags=limit_tag)
            self.limit_values.append(self._text(x + 54.5, 158, '', 12, GOLD, tags=limit_tag))
        c.tag_bind(limit_tag, '<Button-1>', self.toggle_high_bet_limits)
        c.tag_bind(limit_tag, '<Enter>', lambda _e: self._limit_hover())
        c.tag_bind(limit_tag, '<Leave>', lambda _e: self._bet_leave())
        c.create_rectangle(797, 69, 1128, 178, fill=ROOT_BG, outline=GOLD, width=2)
        self._text(962, 86, '门注赔率', 13, PANEL_BG)
        for y, title, odds in ((113, '获胜', '0.99 : 1'), (138, '惜败', '0.93 : 1')):
            self._text(816, y, title, 11, PANEL_BG, anchor='w')
            self._text(1108, y, odds, 12, GOLD, anchor='e')
        self._text(962, 163, '同牌庄家胜 · 每门仅可押一侧', 10, '#CDD5BF')
        c.create_rectangle(384, 10, 764, 181, fill='#4b1e22', outline='#6B4544')
        self.dealer_title = self._text(574, 28, '庄家', 16, PANEL_BG)
        self._create_shoe_panel()

        self.player_panels, self.player_titles, self.bet_labels, self.bet_headings = {}, {}, {}, {}
        for door in self.game.SEATS:
            x, cx = self.seat_x(door), self.seat_x(door) + self.SEAT_WIDTH / 2
            fill = self.ZONE_COLORS[(door - 1) % 2]
            self.player_panels[door] = c.create_rectangle(x, 317, x + self.SEAT_WIDTH, 614, fill=fill, outline='')
            self.player_titles[door] = self._text(cx, 335, self.POSITION_NAMES[door], 18, PANEL_BG)
            for side in self.BET_SIDES:
                key, tag = (door, side), f'bet_{door}_{side}'
                bx, by = self._bet_center(key)
                heading = '获胜  0.99 : 1' if side == 'win' else '惜败  0.93 : 1'
                self.bet_headings[key] = self._text(bx, by - 45, heading, 11, PANEL_BG, tags=tag)
                c.create_oval(bx - 32, by - 32, bx + 32, by + 32, fill=fill, outline=GOLD, width=2, tags=tag)
                c.create_oval(bx - 28, by - 28, bx + 28, by + 28, outline='#77906B', tags=tag)
                self.bet_labels[key] = self._text(bx, by, '获胜' if side == 'win' else '惜败', 11, PANEL_BG, tags=tag)
                c.tag_bind(tag, '<Button-1>', lambda _e, d=door, s=side: self.add_bet_cell(d, s))
                c.tag_bind(tag, '<Button-3>', lambda _e, d=door, s=side: self.clear_bet_cell(d, s))
                c.tag_bind(tag, '<Enter>', lambda _e, k=key: self._bet_hover(k))
                c.tag_bind(tag, '<Leave>', lambda _e: self._bet_leave())

        # Same bottom bar, chip rack, bevelled buttons and Enter shortcut as Classic.
        c.create_rectangle(0, 625, 1150, 749, fill=ROOT_BG, outline='#6C7850', width=2)
        self.balance_item = self._text(10, 665, '', 18, TEXT, anchor='w')
        self.total_item = self._text(10, 710, '', 18, TEXT, anchor='w')
        self.clear_button = self.create_control_button(278, 650, 344, 704, '清除',
            self.reset_bets, '#9B403A', font_size=11, draw_shadow=False)
        self.info_button = self.create_control_button(810, 650, 855, 695, '?',
            self.show_detailed_rules, DARK_BLUE, font_size=17, draw_shadow=False)
        self.repeat_button = self.create_control_button(862, 638, 1000, 708, '重复下注',
            self.repeat_bet, '#536A43', font_size=11, draw_shadow=False)
        self.start_button = self.create_control_button(1012, 628, 1138, 720, '开牌',
            self.primary_action, HEADER_BG, fg=TITLE_FG, font_size=14,
            subtext='Enter', subtext_font_size=14, draw_shadow=False)
        self.restart_button = self.create_control_button(862, 638, 1138, 708, '再来一局(30)',
            self._return_all_chips, HEADER_BG, fg=TITLE_FG, font_size=17, draw_shadow=False)
        c.itemconfigure(self.restart_button, state='hidden')
        self._update_limits_display()
        self._draw_chips()

    def seat_x(self, door):
        return self.SEAT_LEFT + (door - 1) * self.SEAT_PITCH

    def _chip_configs(self):
        return HIGH_CHIPS if self.high_bet_mode else CHIPS

    def _draw_chips(self):
        self.canvas.delete('rack')
        for i, (amount, _) in enumerate(self._chip_configs()):
            tag = f'rack_{i}'
            self._draw_chip(tag, amount, 415 + i * 64, 674, ('rack',), amount == self.selected_chip)
            self.canvas.tag_bind(tag, '<Button-1>', lambda _e, a=amount: self.select_chip(a))

    def select_chip(self, amount):
        if self.game.stage == 'betting' and self._idle() and amount in dict(self._chip_configs()):
            self.selected_chip = amount
            self._draw_chips()

    def _bet_center(self, key):
        door, side = key
        return self.seat_x(door) + self.SEAT_WIDTH / 2 + (-90 if side == 'win' else 90), 542

    @staticmethod
    def _bet_tag(key):
        return f'bet_{key[0]}_{key[1]}'

    def _bet_hover(self, key):
        cursor = ''
        if self.stage == 'betting' and self._idle():
            cursor = 'X_cursor' if self.game.side_blocked(*key) else 'hand2'
        self.canvas.configure(cursor=cursor)

    def _bet_leave(self):
        self.canvas.configure(cursor='')

    def _limit_hover(self):
        self.canvas.configure(cursor='hand2' if self.stage == 'betting' and self._idle() else '')

    def _render_bet_chips(self):
        self.canvas.delete('bet_chips')
        for (key, role), chip in sorted(self.visual_chips.items(), key=lambda item: item[0][1] != 'stake'):
            self._draw_chip(f'chip_{key[0]}_{key[1]}_{role}', chip['amount'], *chip['xy'],
                            ('bet_chips', self._bet_tag(key)), scale=self.BET_CHIP_SCALE)

    def add_bet_cell(self, door, side):
        if not self._idle() or self.stage != 'betting':
            return
        previous = dict(self.game.bets)
        try:
            changed = self.game.add_bet(door, side, self.selected_chip, self.balance)
        except ValueError as exc:
            messagebox.showwarning('下注', str(exc), parent=self)
            return
        if not changed:
            return
        layout = dict(self.game.bets)
        self.game.bets = previous
        self._apply_bet_layout(layout)

    def clear_bet_cell(self, door, side):
        if self.stage == 'betting' and self._idle() and (door, side) in self.game.bets:
            layout = dict(self.game.bets)
            layout[(door, side)] = 0.0
            self._apply_bet_layout(layout)

    def reset_bets(self):
        if self.stage == 'betting' and self._idle():
            self._apply_bet_layout(self.game.empty_bets())

    def repeat_bet(self):
        if not self._idle() or self.stage != 'betting' or not self.game.last_bets:
            return
        try:
            layout = self.game.validate_bets(self.game.last_bets, self.balance, require_min=True)
        except ValueError as exc:
            messagebox.showwarning('重复下注', str(exc), parent=self)
            return
        self._apply_bet_layout(layout)

    def secondary_action(self):
        self.repeat_bet()

    def _apply_bet_layout(self, new_bets):
        previous = dict(self.game.bets)
        self.game.bets = dict(new_bets)
        transfers = []
        for key in self.game.BET_KEYS:
            delta = money(new_bets[key] - previous[key])
            if delta > 0:
                transfers.append(dict(amount=delta, start=self._rack_position(), target=self._bet_center(key),
                    arrive=lambda k=key, a=new_bets[key]: self._set_visual(k, 'stake', a)))
            elif delta < 0:
                self._set_visual(key, 'stake', new_bets[key])
                transfers.append(dict(amount=-delta, start=self._bet_center(key), target=self._rack_position(), duration=440))
        self._run_chip_batch(transfers, self._refresh)
        self._refresh()

    def _current_min_bet(self):
        return self.game.min_bet

    def _current_max_bet(self):
        return self.game.max_bet

    def toggle_high_bet_limits(self, event=None):
        if self.stage != 'betting' or not self._idle():
            return
        if not self.high_bet_mode:
            current_password = time.strftime('%H%M')
            password = simpledialog.askstring('高额下注', '请输入密码：', parent=self.winfo_toplevel())
            if password is None:
                return
            if password.strip() != current_password:
                messagebox.showerror('错误', '密码错误', parent=self.winfo_toplevel())
                return
        self.game.high_bet_mode = not self.game.high_bet_mode
        self.selected_chip = 100 if self.high_bet_mode else 10
        self._draw_chips()
        self._update_limits_display()
        self.status = '已切换为高额下注模式。' if self.high_bet_mode else '已切换为正常下注模式。'
        self._apply_bet_layout(self.game.empty_bets())

    def _update_limits_display(self):
        self.canvas.itemconfigure(self.limit_title, text='下注上限 · 高额' if self.high_bet_mode else '下注上限')
        for item, text in zip(self.limit_values, (f'${self.game.min_bet:,}', f'${self.game.max_bet:,}', '2 张')):
            self.canvas.itemconfigure(item, text=text)

    def primary_action(self):
        if not self._idle():
            return
        if self.stage == 'betting':
            self.start_round()
        elif self.stage in ('await_restart', 'credit_pending'):
            self._return_all_chips()

    def _refresh(self):
        c, g = self.canvas, self.game
        c.itemconfigure(self.balance_item, text=f'余额: ${self.balance:,.2f}')
        c.itemconfigure(self.total_item, text=f'本局下注: ${g.total_bet:,.2f}' if g.total_bet else f'上局返还: ${g.last_return:,.2f}')
        betting = g.stage == 'betting' and self._idle()
        restarting = g.stage in ('settling', 'await_restart', 'returning', 'credit_pending', 'sweeping')
        self.set_control_button_state(self.clear_button, betting)
        self.set_control_button_state(self.repeat_button, betting and bool(g.last_bets and sum(g.last_bets.values())))
        self.set_control_button_state(self.start_button, betting)
        self.set_control_button_state(self.restart_button, g.stage in ('await_restart', 'credit_pending') and self._idle())
        c.itemconfigure(self.repeat_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.start_button, state='hidden' if restarting else 'normal')
        c.itemconfigure(self.restart_button, state='normal' if restarting else 'hidden')
        self._render_bet_headings()
        self._render_bet_chips()
        self._draw_hands()
        self._draw_wall()
        self._draw_dice(g.dice or [1, 1])

    def _render_bet_headings(self):
        c, g = self.canvas, self.game
        for key, heading in self.bet_headings.items():
            c.itemconfigure(heading, fill=GOLD if g.resolved and key in g.winning_cells else PANEL_BG)

    def _hand_positions(self, door):
        if door == 0:
            return [(527, 48, 38, 95), (583, 48, 38, 95)]
        center = self.seat_x(door) + self.SEAT_WIDTH / 2
        return [(center - 44, 354, 36, 90), (center + 8, 354, 36, 90)]

    def _draw_hands(self):
        c, g = self.canvas, self.game
        c.delete('table_tiles')
        for door in g.POSITIONS:
            positions = self._hand_positions(door)
            if door not in self._dealt:
                for x, y, w, h in positions:
                    c.create_rectangle(x, y, x + w, y + h, outline='#7B9374', dash=(3, 3), tags='table_tiles')
            else:
                result = g.results.get(door)
                if result:
                    shade = '#54A96B' if result['side'] == 'win' else '#AE4945'
                    for x, y, w, h in positions:
                        c.create_rectangle(x - 3, y - 3, x + w + 4, y + h + 4,
                                           fill=shade, outline=shade, tags='table_tiles')
                for index, (tile, (x, y, w, h)) in enumerate(zip(g.hands[door], positions)):
                    if self._flip_state == (door, index):
                        continue
                    self.draw_tile(x, y, w, h, tile, face_up=(door, index) in self._face_up,
                                   tag=f'table_tile_{door}_{index}', extra_tag='table_tiles',
                                   show_name=False, compact=True)
            revealed = door in self._dealt and all((door, i) in self._face_up for i in range(2))
            label = evaluate_wenzhou_hand(g.hands[door]).name if revealed else ''
            if door == 0:
                c.itemconfigure(self.dealer_title, text='庄家' + (f' · {label}' if label else ''),
                                fill=GOLD if label else PANEL_BG)
            else:
                title = self.POSITION_NAMES[door] + (f' · {label}' if label else '')
                color = PANEL_BG
                if door in g.results:
                    won = g.results[door]['side'] == 'win'
                    color = '#FFE18A' if won else TEXT
                c.itemconfigure(self.player_titles[door], text=title, fill=color)

    def _wall_origin(self, index):
        column, local = divmod(index, 2)
        layer = 1 - local
        return 108 + column * 38 + layer * 2, 246 - layer * 12

    def _wall_snapshot(self, tiles, tag='wall', offset=0, theme=None, removed=None, clip_bounds=None):
        removed = removed or set()
        # Each physical column is a two-tile Wenzhou hand, bottom then top.
        for local in (1, 0):
            for column in reversed(range(len(tiles) // 2)):
                index = column * 2 + local
                if index not in removed:
                    x, y = self._wall_origin(index)
                    self._prism_tile(x + offset, y, tag=tag, theme=theme, clip_bounds=clip_bounds)

    def _draw_wall(self):
        self.canvas.delete('wall')
        if self._moving or self.stage in ('sweeping', 'shoe_exchange'):
            return
        self._wall_snapshot(self.game.tiles, removed=self._wall_removed)
        self.canvas.itemconfigure(self.shoe_label, text=f'{32 - len(self._wall_removed)} / 32')

    def _create_shoe_panel(self):
        c = self.canvas
        c.delete('shoe_panel')
        c.create_rectangle(22, 190, 1128, 309, fill=ROOT_BG, outline='#65784B', tags='shoe_panel')
        c.create_line(25, 191, 1125, 191, fill='#E0C879', width=2, tags='shoe_panel')
        c.create_line(25, 308, 1125, 308, fill='#0C241B', width=2, tags='shoe_panel')
        self._text(52, 209, '牌靴', 13, GOLD, anchor='w', tags='shoe_panel')
        self.shoe_label = self._text(790, 209, '32 / 32', 12, PANEL_BG, anchor='e', tags='shoe_panel')
        self.dice_label = self._text(1073, 272, '', 10, PANEL_BG, tags='shoe_panel')
        self._dice_equation_items = [
            self._text(x, 244, text, 12, color, tags='shoe_panel')
            for x, text, color in (
                (1028, '1', '#%02x%02x%02x' % GD_DICE_COLORS[0]),
                (1046, '+', PANEL_BG),
                (1064, '1', '#%02x%02x%02x' % GD_DICE_COLORS[1]),
                (1082, '=', PANEL_BG),
                (1107, '2', GOLD))]

    def _draw_dice(self, values=None):
        c = self.canvas
        if self.golden_dice_bowl is None:
            self.golden_dice_bowl = GoldenDiceBowl(values or [1, 1])
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
        if self.stage == 'rolling':
            terms = ('…', '+', '…', '=', '…')
        else:
            blue, red = self.golden_dice_bowl.values()
            terms = (str(blue), '+', str(red), '=', str(blue + red))
        for item, text in zip(self._dice_equation_items, terms):
            self.canvas.itemconfigure(item, text=text)

    def start_round(self):
        if not self._idle() or self.stage != 'betting':
            return
        try:
            self.balance = self.game.start(self.balance)
        except ValueError as exc:
            messagebox.showwarning('开牌', str(exc), parent=self)
            return
        self._persist_balance()
        self._dealt.clear()
        self._wall_removed.clear()
        self._face_up.clear()
        self._round_credited = self._return_persisted = False
        self.status = '停止下注，正在摇两颗骰子。'
        self._refresh()
        self._start_golden_dice_roll()

    def _start_golden_dice_roll(self):
        if self._closing or self.stage != 'rolling':
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
        if self._closing or self.stage != 'rolling':
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
        start, total = self.game.deal_order[0], sum(dice)
        self.canvas.itemconfigure(self.dice_label, text=f'{total} 点 · {self.POSITION_NAMES[start]}先派')
        self.status = f'骰子共{total}点，{self.POSITION_NAMES[start]}先派。'
        self._refresh()
        self._schedule(220, self._deal_stack, 0)

    def _deal_stack(self, stack_index):
        if stack_index == 4:
            self._schedule(350, self._settle_round)
            return
        door = self.game.deal_order[stack_index]
        self._wall_removed.update(range(stack_index * 2, stack_index * 2 + 2))
        self._draw_wall()
        targets = self._hand_positions(door)
        source_indices = {tile.uid: stack_index * 2 + i for i, tile in enumerate(self.game.stacks[stack_index])}
        starts = [self._wall_origin(source_indices[tile.uid]) for tile in self.game.hands[door]]
        self.status = f'正在派牌：{self.POSITION_NAMES[door]}。'
        self._refresh()

        def frame(step):
            self.canvas.delete('flight')
            t = step / 15
            smooth = t * t * (3 - 2 * t)
            for index, ((sx, sy), (tx, ty, tw, th)) in enumerate(zip(starts, targets)):
                x, y = sx + (tx - sx) * smooth, sy + (ty - sy) * smooth - 30 * math.sin(math.pi * t)
                if step < 5:
                    self._prism_tile(x, y, tag='flight')
                else:
                    w, h = 27 + (tw - 27) * smooth, 44 + (th - 44) * smooth
                    self.draw_tile(x, y, w, h, self.game.hands[door][index], face_up=False,
                                   tag='flight', extra_tag=None, compact=True)
            if step < 15:
                self._schedule(16, frame, step + 1)
            else:
                self.canvas.delete('flight')
                self._dealt.add(door)
                self._draw_hands()
                self._schedule(120, self._flip_next, [(door, 0), (door, 1)], 0,
                               lambda: self._schedule(200, self._deal_stack, stack_index + 1))
        frame(0)

    def _flip_next(self, sequence, offset, complete):
        if offset == len(sequence):
            self._flip_state = None
            self.canvas.delete('flip_tile')
            complete()
            return
        door, index = sequence[offset]
        x, y, w, h = self._hand_positions(door)[index]
        tile = self.game.hands[door][index]
        self._flip_state = (door, index)
        self._draw_hands()

        def frame(step):
            self.canvas.delete('flip_tile')
            width = max(1, w * abs(1 - step / 5))
            self.draw_tile(x + (w - width) / 2, y, width, h, tile, face_up=step >= 5,
                           tag='flip_tile', extra_tag=None, show_name=False, compact=True)
            if step < 10:
                self._schedule(32, frame, step + 1)
            else:
                self._face_up.add((door, index))
                self._flip_state = None
                self.canvas.delete('flip_tile')
                self._draw_hands()
                self._flip_next(sequence, offset + 1, complete)
        frame(0)

    def _settle_round(self):
        if self.game.resolved:
            return
        self.game.settle()
        self.status = f'结算完成 · 本局返还 ${self.game.last_return:,.2f}。'
        transfers = []
        for key in self.game.BET_KEYS:
            stake = self.game.round_bets[key]
            if not stake:
                continue
            returned = self.game.bet_returns[key]
            if returned <= 0:
                chip = self.visual_chips.pop((key, 'stake'), None)
                if chip:
                    transfers.append(dict(amount=chip['amount'], start=chip['xy'], target=(575, 43), duration=280))
            else:
                profit = money(returned - stake)
                center = self._bet_center(key)
                target = (center[0] - 54, center[1])
                transfers.append(dict(amount=profit, start=(575, 43), target=target, duration=440,
                    arrive=lambda k=key, a=profit, p=target: self._set_visual(k, 'profit', a, p)))
        self._refresh()
        self._run_chip_batch(transfers, self._await_next_round)

    def settle_wenzhou_round(self):
        self._settle_round()

    def _complete_chip_return(self):
        if self.stage not in ('returning', 'credit_pending'):
            return
        self.game.stage = 'credit_pending'
        try:
            self._credit_round_return()
        except Exception as exc:
            messagebox.showerror('余额保存失败', str(exc), parent=self)
            self._refresh()
            return
        self.canvas.delete('returned_chips')
        self.game.stage = 'sweeping'
        self._moving = True
        self.status = '正在收牌并更换牌靴。'
        self._refresh()

        def frame(step):
            self.canvas.move('table_tiles', 1250 / 13, 0)
            if step < 13:
                self._schedule(16, frame, step + 1)
            else:
                self._dealt.clear()
                self._face_up.clear()
                self.canvas.delete('table_tiles')
                self._swap_shoe()
        frame(1)

    def _swap_shoe(self):
        old_tiles, old_theme = self.game.tiles[:], self.tile_theme
        old_removed = set(self._wall_removed)
        if not self.game.next_round():
            return
        self._dealt.clear()
        self._face_up.clear()
        self._flip_state = None
        self.game.stage = 'shoe_exchange'
        self.tile_theme = self._opposite_tile_theme(self.tile_theme)
        self._wall_removed.clear()
        self._moving = True
        self._refresh()
        shoe_bounds = (22, self.canvas.coords(self.shoe_label)[0])

        def frame(step):
            self.canvas.delete('shoe_swap')
            t = step / 24
            t = t * t * (3 - 2 * t)
            self._wall_snapshot(old_tiles, tag='shoe_swap', offset=1200 * t,
                                theme=old_theme, removed=old_removed, clip_bounds=shoe_bounds)
            self._wall_snapshot(self.game.tiles, tag='shoe_swap', offset=-1200 * (1 - t),
                                clip_bounds=shoe_bounds)
            if step < 24:
                self._schedule(20, frame, step + 1)
            else:
                self.canvas.delete('shoe_swap')
                self.game.stage = 'betting'
                self._round_credited = self._return_persisted = False
                self._moving = False
                self.canvas.itemconfigure(self.dice_label, text='')
                self.status = '选择筹码，点击获胜／惜败下注；Enter 开牌。'
                self._refresh()
        frame(0)

    def new_round(self):
        self._return_all_chips()

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

    def _enter_action(self, event=None):
        if event is not None and event.widget.winfo_toplevel() is not self.winfo_toplevel():
            return
        self.primary_action()
        return 'break'

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

    def _draw_chip(self, tag, amount, x, y, extra_tags=(), selected=False, scale=1.0):
        # Rack remains 56px; betting/profit chips use 80% size, including rims and text.
        c, tags = self.canvas, (tag, *extra_tags)
        color = next((col for value, col in reversed(self._chip_configs()) if amount >= value), HEADER_BG)
        outer, inner = 28*scale, 23*scale
        c.create_oval(x-outer, y-outer, x+outer, y+outer, fill='#182F25',
                      outline=GOLD if selected else '#6C7850', width=3*scale, tags=tags)
        c.create_oval(x-inner, y-inner, x+inner, y+inner, fill=color, outline=PANEL_BG, width=2*scale, tags=tags)
        self._text(x, y, self._compact(amount), max(8, round(10*scale)),
                   TEXT if color in (BLACK, RED) else BLACK, tags=tags)

    def _rack_position(self, index=None, total=1):
        if index is not None:
            return 575+(index-(total-1)/2)*min(28, 140/max(1, total-1)), 674
        index = next((i for i, (value, _) in enumerate(self._chip_configs()) if value == self.selected_chip), 0)
        return 415+index*64, 674

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


def build_pai_gow_page(parent, balance=10000, user='Guest', on_back=None, on_balance_change=None):
    return WenzhouPaiGowGUI(parent, balance=balance, user=user,
                           on_back=on_back, on_balance_change=on_balance_change)


def start_pai_gow_gui(balance=10000, user='Guest', on_back=None, on_balance_change=None):
    root = tk.Tk()
    root.title('温州牌九')
    root.geometry(WINDOW_GEOMETRY)
    root.resizable(False, False)
    page = build_pai_gow_page(root, balance=balance, user=user,
                             on_back=on_back, on_balance_change=on_balance_change)
    page.pack(fill='both', expand=True)
    root.protocol('WM_DELETE_WINDOW', page.on_close)
    root.mainloop()
    return page


def main(initial_balance=10000, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    if parent is not None:
        return build_pai_gow_page(parent, balance=actual_balance, user=actual_user,
                                 on_back=on_back, on_balance_change=on_balance_change)
    return start_pai_gow_gui(balance=actual_balance, user=actual_user,
                            on_back=on_back, on_balance_change=on_balance_change)


if __name__ == '__main__':
    main()
