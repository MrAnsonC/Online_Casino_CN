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
import math
import random
import time
from itertools import combinations
import json
import os
import re
import secrets
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageEnhance, ImageTk


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
GD_DICE_EDGE_PX = 38.0 * .75
GD_BOWL_SCALE = 1.55
GD_BOWL_RADIUS_SCALE = 1.35
GD_BOWL_HEIGHT_SCALE = .80
GD_DOME_HEIGHT_SCALE = 1.00
GD_BOWL_DISPLAY_SIZE = (274, 193)
GD_DOME_EXTRA_HEIGHT_PX = 15
GD_BOWL_DROP_PX = 20
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
    """Read-only OBB contact query for physics and initial placement."""
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
    RADIUS = .085 * GD_BOWL_SCALE * GD_BOWL_RADIUS_SCALE
    HEIGHT = (.128 * GD_BOWL_SCALE * GD_DOME_HEIGHT_SCALE
              + GD_DOME_EXTRA_HEIGHT_PX
              / (680 * GD_VIEW_UP * GD_BOWL_DISPLAY_SIZE[1] / round(138 * GD_BOWL_SCALE)))

    def __init__(self, values=None, rng=None):
        self.rng = rng or random.SystemRandom()
        values = values or [self.rng.randint(1, 6) for _ in range(self.DICE_COUNT)]
        if len(values) != self.DICE_COUNT or any(type(n) is not int or n not in range(1, 7) for n in values):
            raise ValueError('骰宝需要三颗有效骰子。')
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
            radius = min(self.RADIUS-die.EDGE, die.EDGE*2.6)
            die.p = (radius * math.cos(angle), radius * math.sin(angle), die.HALF)
            die.q = _gd_rotate(die.q, (0., 0., 1.), heading)

    def landing_error(self):
        """Accept faces within 8 degrees when every die rests on the floor."""
        for die in self.dice:
            vertices = [self.local(p) for p in die.vertices()]
            if die.top_face() is None:
                return '骰子未平放'
            # Overlap means vertical stacking, not side contact or occlusion
            # from the camera. A stacked die's bottom is above the floor.
            floor = min(p[2] for p in vertices)
            if floor > die.CONTACT_TOLERANCE:
                return '骰子上下重叠或未落地'
            if floor < -die.CONTACT_TOLERANCE:
                return '骰子未落地'
            if any((x*x+y*y)/self.RADIUS**2 + max(0.,z)**2/self.HEIGHT**2 > 1.0001
                   for x,y,z in vertices):
                return '骰子超出底盘'
        return None

    def begin(self, duration=None):
        # Fast upright directional shakes. No bowl flips or inverted holds.
        # Continuous 5–8 second shakes, centred near 7, to microsecond precision.
        if duration is None:
            while True:
                seconds = self.rng.normalvariate(7., .5)
                if 5. <= seconds <= 8.:
                    self.duration = round(seconds, 6)
                    break
        else:
            self.duration = float(duration)
        count = round(self.duration / .145)
        self.durations = []
        remaining = self.duration
        for strokes_left in range(count, 1, -1):
            low = max(.12, remaining - (strokes_left-1)*.17)
            high = min(.17, remaining - (strokes_left-1)*.12)
            seconds = self.rng.uniform(low, high)
            self.durations.append(seconds)
            remaining -= seconds
        self.durations.append(remaining)
        # Draw each movement from the system RNG only when it starts. Future
        # shake directions and the final upward faces are never precomputed.
        self.strokes = [None] * count
        self.collision_count = 0

    def motion(self, t):
        elapsed = 0.
        for index, duration in enumerate(self.durations):
            if t < elapsed+duration:
                stroke = self.strokes[index]
                if stroke is None:
                    heading = self.rng.randrange(4)*math.pi/2+self.rng.uniform(-.45, .45)
                    strength = self.rng.uniform(1.2, 1.8)
                    stroke = (strength*math.cos(heading), strength*math.sin(heading),
                              self.rng.choice((-1, 1))*self.rng.uniform(1.0, 1.8),
                              self.rng.uniform(-.012, .012), self.rng.uniform(.013, .026))
                    self.strokes[index] = stroke
                u = max(0., (t-elapsed)/duration)
                first = math.sin(math.pi*u)**4
                second = math.sin(math.tau*u)**4
                vx, vy, snap, side, hop = stroke
                along, lateral = .045*first+.014*snap*second, side*second*1.8
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
        """Restore complete saved bodies within 8 degrees and on the floor."""
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
    """Transparent Sic Bo dome and dish, with blue, red and gold dice."""
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
    profile = [(radius * GD_BOWL_SCALE * GD_BOWL_RADIUS_SCALE,
                z * GD_BOWL_SCALE * GD_BOWL_HEIGHT_SCALE) for radius, z in
               ((.083, 0.), (.088, .005), (.093, .002), (.094, -.007),
                (.092, -.014), (.083, -.020))]
    rings = [ring(radius, z) for radius, z in profile]
    for k in range(32):
        j = (k+1)%32
        face([bowl.world(p) for p in ((0.,0.,0.), rings[0][k], rings[0][j])], (248,234,197,255))
        face([bowl.world(p) for p in ((0.,0.,-.020*GD_BOWL_SCALE*GD_BOWL_HEIGHT_SCALE), rings[-1][j], rings[-1][k])], (142,111,70,255))
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
                                (raised+.002*GD_BOWL_SCALE*GD_BOWL_HEIGHT_SCALE,
                                 .086*GD_BOWL_SCALE*GD_BOWL_RADIUS_SCALE,(168,207,194,185),.6)):
        rim = ring(radius,z)
        for k in range(32):
            face([bowl.world(rim[k]),bowl.world(rim[(k+1)%32])],None,color,width,True)
    for azimuth,color,width in ((-2.4,(242,255,249,220),1.2),(.55,(219,246,235,160),.8)):
        curve = []
        for k in range(22):
            a = .10+1.28*k/21
            curve.append(bowl.world((bowl.RADIUS*math.cos(a)*math.cos(azimuth),
                                     bowl.RADIUS*math.cos(a)*math.sin(azimuth),
                                     bowl.HEIGHT*math.sin(a)+raised+.0005*GD_BOWL_SCALE*GD_BOWL_HEIGHT_SCALE)))
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
    # Extra headroom extends the dome without scaling the dice or the dish.
    width, height = GD_BOWL_DISPLAY_SIZE
    size, aa = (width, height + GD_DOME_EXTRA_HEIGHT_PX), 3
    scale_x = width / round(196 * GD_BOWL_SCALE)
    scale_y = height / round(138 * GD_BOWL_SCALE)
    picture = Image.new('RGBA', (size[0]*aa, size[1]*aa))
    for meshes in _gd_bowl_mesh(bowl):
        layer = Image.new('RGBA', picture.size)
        draw = ImageDraw.Draw(layer)
        for _depth, points, color, line, width in meshes:
            projected = [(x*scale_x*aa, (y*scale_y+GD_DOME_EXTRA_HEIGHT_PX)*aa)
                         for x,y in (_gd_project(p,bowl) for p in points)]
            if color:
                draw.polygon(projected, fill=color)
            if line:
                draw.line(projected+([projected[0]] if len(points)>2 else []),
                          fill=line,width=max(1,round(width*scale_y*aa)))
        picture.alpha_composite(layer)
    return picture.resize(size, Image.Resampling.LANCZOS)



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

    TOTAL_PAYOUT = {
        4: 62, 5: 31, 6: 18, 7: 12, 8: 8, 9: 7, 10: 6,
        11: 6, 12: 7, 13: 8, 14: 12, 15: 18, 16: 31, 17: 62,
    }
    PAIRS = tuple(f'{a}&{b}' for a in range(1, 7) for b in range(a + 1, 7))
    GROUPS = ('1234', '2345', '2356', '3456')
    # AAB keeps the repeated face first; ABC is ascending. String keys remain
    # compatible with bet snapshots, repeat bets and JSON serialization.
    EXACT_AAB = tuple(f'{a}{a}{b}' for a in range(1, 7)
                      for b in range(1, 7) if a != b)
    EXACT_ABC = tuple(''.join(map(str, values))
                      for values in combinations(range(1, 7), 3))

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
            'exact_aab': {key: 0.0 for key in cls.EXACT_AAB},
            'exact_abc': {key: 0.0 for key in cls.EXACT_ABC},
        }

    @staticmethod
    def exact_combination_key(dice):
        """Return the matching exact market, regardless of the dice order."""
        values = sorted(dice)
        distinct = set(values)
        if len(distinct) == 2:
            repeated = next(value for value in distinct if values.count(value) == 2)
            other = next(value for value in distinct if value != repeated)
            return 'exact_aab', f'{repeated}{repeated}{other}'
        if len(distinct) == 3:
            return 'exact_abc', ''.join(map(str, values))
        return None  # Triples retain their existing, separate markets.

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

    def resolve_roll(self, dice, triple_mode=False):
        dice = list(dice)
        total = sum(dice)
        is_triple = dice[0] == dice[1] == dice[2]
        outcomes = []
        credit = 0.0
        gross_profit = 0.0
        lost_stake = 0.0

        def settle(label, key, stake, won, payout=0.0):
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

        settle('任何围骰', ('all_triples', None), self.bets['all_triples'], is_triple, 31)

        for number, amount in self.bets['double'].items():
            settle(f'对子 {number}', ('double', number), amount, dice.count(number) >= 2, 11)

        for point, amount in self.bets['total_points'].items():
            settle(f'总点 {point}', ('total_points', point), amount,
                   total == point, self.TOTAL_PAYOUT[point])

        for pair, amount in self.bets['pairs'].items():
            a, b = map(int, pair.split('&'))
            settle(f'组合 {a}+{b}', ('pairs', pair), amount,
                   dice.count(a) >= 1 and dice.count(b) >= 1, 6)

        for number, amount in self.bets['triple'].items():
            settle(f'围骰 {number}', ('triple', number), amount,
                   dice.count(number) == 3, 190)

        for number, amount in self.bets['guess_num'].items():
            count = dice.count(number)
            payout = {1: 1, 2: 2, 3: 12}.get(count, 0)
            settle(f'单骰 {number}', ('guess_num', number), amount, count > 0, payout)

        unique_dice = set(dice)
        for group, amount in self.bets['number_group'].items():
            group_set = {int(value) for value in group}
            settle(f'四数组合 {group}', ('number_group', group), amount,
                   len(unique_dice) == 3 and unique_dice.issubset(group_set), 7)

        exact_key = self.exact_combination_key(dice)
        for bet_type, payout in (('exact_aab', 60), ('exact_abc', 30)):
            for combination, amount in self.bets[bet_type].items():
                key = (bet_type, combination)
                settle(f'骰子组合 {"·".join(combination)}', key, amount,
                       key == exact_key, payout)

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
    BG = '#17120f'
    PANEL = '#211811'
    PANEL_LINE = '#665240'
    FELT = '#0b4540'
    FELT_2 = '#0d5149'
    LINE = '#c3d5ca'
    GOLD = '#e7d36c'
    RED = '#c43b40'

    BIG_RED = '#ff4d4f'
    TRIPLE_GREEN = '#55d66b'
    SMALL_YELLOW = '#f2d35f'
    BOARD_CREAM = '#f7f3ea'

    SINGLE_NUMBER_ODDS_TEXT = '1次1:1 / 2次2:1 / 3次12:1'
    SINGLE_NUMBER_TITLES = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六'}

    MIN_BET = 0.5
    MAX_AREA_BET = 100000.0
    MAX_TABLE_BET = 2000000.0
    MAX_RECORDS = 500
    BET_CHIP_RADIUS = 19
    CHIP_MOVE_MS = 200
    SETTLEMENT_FLASH_MS = 450
    SETTLEMENT_GOLD = '#e5b94b'
    SETTLEMENT_WHITE = '#ffffff'
    DICE_RESULT_TIMEOUT_MS = 8000
    DICE_RECOVERY_SHAKE_SECONDS = 1.0

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
        self.triple_mode = False

        self.selected_chip = 1.0
        self.multiplier = 1
        self.undo_stack = []
        self.last_round_bets = []
        self.bet_spots = {}
        self.chip_selector_items = {}
        self.control_buttons = {}
        self.animation_running = False
        self.animation_after_id = None
        self.animation_frames_left = 0
        self.animation_final_dice = None
        self._sicbo_bowl = None
        self._sicbo_cup_item = self._sicbo_cup_photo = None
        self._sicbo_dice_phase = 'idle'
        self._sicbo_dice_time = self._sicbo_dice_stable_time = 0.
        self._sicbo_dice_rest_anchor = None
        self._sicbo_result_timeout_id = self._sicbo_result_deadline = None
        self._sicbo_recovering = self._sicbo_round_voided = False
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
        self._settlement_spot_styles = {}
        self._settlement_dim_images = {}
        self._chip_motion_jobs = set()
        self._chip_motion_count = self._chip_serial = 0
        self._pending_bet_amounts = {}
        self._settlement_chips_returning = False
        self.pre_roll_bets = None
        self._closing = False

        top = self.winfo_toplevel()

        top.bind('<Return>', self.handle_enter_roll)
        self.bind('<Control-z>', lambda _event: self.undo_last_bet())

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
        self.dice_images_board_sizes = {size: [] for size in (19, 20, 21, 25)}
        self.dice_images_animation = []
        self.dice_images_triple_info = []
        self.dice_images_status = []

        def make_die(size, number, board_style=False, raw=False):
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
            return image if raw else ImageTk.PhotoImage(image)

        for number in range(1, 7):
            self.dice_images_history.append(make_die(23, number))
            board_die = make_die(23, number, board_style=True, raw=True)
            self.dice_images_board.append(ImageTk.PhotoImage(board_die))
            for size, images in self.dice_images_board_sizes.items():
                images.append(ImageTk.PhotoImage(board_die.resize(
                    (size, size), Image.Resampling.LANCZOS)))
            self.dice_images_animation.append(make_die(86, number))
            self.dice_images_triple_info.append(make_die(38, number))
            self.dice_images_status.append(make_die(30, number))

    # ---------------------------------------------------------------------- UI
    def create_ui(self):
        self.canvas = tk.Canvas(self, width=1150, height=750, bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_rectangle(0, 0, 1150, 750, fill=self.BG, outline='', tags='static')

        self.draw_history_panel()
        self.draw_animation_panel()
        self.draw_board()
        self.draw_bottom_controls()

    def draw_history_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = 872, 4, 1138, 620
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
        x0, y0, x1, y1 = 12, 4, 864, 246
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
        self.animation_panel = (x0, y0, x1, y1)
        centre_x = (x0 + x1) / 2
        self._sicbo_title_position = (centre_x, y0 + 18)
        c.create_text(*self._sicbo_title_position, text='骰宝 SIC BO',
                      font=('Arial', 16, 'bold'), fill='#d4c3a9', tags='animation')

        # Last triple sits directly above the existing insurance control.
        triple_panel_x0, triple_panel_x1 = x0 + 12, x0 + 170
        triple_panel_y0, triple_panel_y1 = y0 + 34, y0 + 176
        self._sicbo_triple_panel_bounds = (
            triple_panel_x0, triple_panel_y0, triple_panel_x1, triple_panel_y1)
        c.create_rectangle(
            triple_panel_x0, triple_panel_y0, triple_panel_x1, triple_panel_y1,
            fill='#15110f', outline='#7c6754', width=1, tags='animation')
        triple_centre_x = (triple_panel_x0 + triple_panel_x1) / 2
        self.last_triple_text = c.create_text(
            triple_centre_x, triple_panel_y0 + 38, text='围骰\n暂无记录',
            width=140, justify='center', font=('Arial', 22, 'bold'),
            fill='#d4c3a9', tags='animation')
        self.last_triple_dice_items = [
            c.create_image(triple_centre_x - 48 + index * 48, triple_panel_y0 + 112,
                           image=self.dice_images_triple_info[5], state='hidden',
                           tags=('animation', 'last_triple'))
            for index in range(3)]

        initial_dice = self.initial_animation_dice()
        self._sicbo_bowl = GoldenDiceBowl(initial_dice)
        self._sicbo_cup_position = (
            centre_x, y0 + 20 + GD_BOWL_DROP_PX - GD_DOME_EXTRA_HEIGHT_PX)
        self._draw_sicbo_dice()

        self._draw_sicbo_status_panel(x1 - 224, y0 + 34, x1 - 12, y0 + 224)

    def _draw_sicbo_status_panel(self, x0, y0, x1, y1):
        c = self.canvas
        centre_x = (x0 + x1) / 2
        tags = ('animation', 'sicbo_status')

        def rounded_rect(left, top, right, bottom, radius=9, **kw):
            return c.create_polygon(
                left+radius, top, right-radius, top, right, top, right, top+radius,
                right, bottom-radius, right, bottom, right-radius, bottom,
                left+radius, bottom, left, bottom, left, bottom-radius,
                left, top+radius, left, top, smooth=True, splinesteps=20, **kw)

        rounded_rect(x0+3, y0+4, x1+3, y1+4, fill='#100d0b', outline='', tags=tags)
        self._sicbo_status_frame = rounded_rect(
            x0, y0, x1, y1, fill='#dceef8', outline='#9b8663', width=1, tags=tags)
        self.animation_status_bubble = rounded_rect(
            x0+1, y0+40, x1-1, y1-1, radius=8,
            fill=self.BOARD_CREAM, outline='', tags=tags)
        self._sicbo_status_body_top = c.create_rectangle(
            x0+1, y0+40, x1-1, y0+49,
            fill=self.BOARD_CREAM, outline='', tags=tags)
        self._sicbo_status_dot = c.create_oval(
            x0+16, y0+17, x0+22, y0+23, fill='#376543', outline='', tags=tags)
        self._sicbo_status_title = c.create_text(
            x0+30, y0+20, anchor='w', text='状态',
            font=('Arial', 12, 'bold'), fill='#4b3a28', tags=tags)
        self._sicbo_status_badge = rounded_rect(
            x1-81, y0+10, x1-16, y0+30, radius=6,
            fill='#e5eddf', outline='', tags=tags)
        self._sicbo_status_badge_text = c.create_text(
            x1-48.5, y0+20, text='可下注', font=('Arial', 10, 'bold'),
            fill='#376543', tags=tags)
        c.create_line(x0+16, y0+40, x1-16, y0+40, fill='#c9bba5', tags=tags)
        self._sicbo_status_caption = c.create_text(
            centre_x, y0+58, text='本局点数', font=('Arial', 10),
            fill='#76634d', tags=tags)
        self.animation_status_text = c.create_text(
            centre_x, y0+91, text='—', font=('Arial', 28, 'bold'),
            fill='#766853', tags=tags)

        result_y = y0 + 136
        result_xs = (centre_x-56, centre_x, centre_x+56)
        self._sicbo_status_unknown_items = []
        self.animation_result_dice_items = []
        for x in result_xs:
            face = rounded_rect(x-15, result_y-15, x+15, result_y+15,
                                radius=5, fill='#f0f0e9', outline='#222', tags=tags)
            mark = c.create_text(x, result_y, text='?', font=('Arial', 13, 'bold'),
                                 fill='#111', tags=tags)
            self._sicbo_status_unknown_items.extend((face, mark))
            self.animation_result_dice_items.append(c.create_image(
                x, result_y, image=self.dice_images_status[0], state='hidden',
                tags=('animation', 'animation_result', 'sicbo_status')))
        self.animation_result_plus_items = [
            c.create_text(centre_x+offset, result_y, text='+',
                          font=('Arial', 11, 'bold'), fill='#81725e',
                          tags=('animation', 'animation_result', 'sicbo_status'))
            for offset in (-28, 28)]
        self.animation_phase_text = c.create_text(
            centre_x, y1-18, text='等待开局', width=180,
            font=('Arial', 11, 'bold'), fill='#b7a486', tags=tags)
        self.animation_result_suffix = c.create_text(
            centre_x, y1-18, text='', width=180, font=('Arial', 12, 'bold'),
            fill='#e7d36c', state='hidden',
            tags=('animation', 'animation_result', 'sicbo_status'))
        self._set_sicbo_status('ready')

    def _set_sicbo_status(self, state, result=None):
        c = self.canvas
        finished = state == 'result' and result is not None
        big_result = finished and result['result_color'] == self.BIG_RED
        result_text_color = 'black' if big_result else '#2f2b27'
        if finished:
            background = result['result_color']
            badge = '已开点'
            caption, phase, total = '本局点数', '', f"{result['total']} 点"
        elif state == 'rolling':
            background = self.BOARD_CREAM
            badge = '摇动中'
            caption, phase, total = '点数未定', '摇动中 · 停止下注', '—'
        elif state == 'recovering':
            background = self.BOARD_CREAM
            badge = '整理中'
            caption, phase, total = '本局无效 · 已全额退款', '整理骰子 · 暂停下注', '—'
        else:
            background = self.BOARD_CREAM
            badge = '可下注'
            caption, phase, total = '本局点数', '等待开局', '—'

        c.itemconfigure(self.animation_status_bubble, fill=background)
        c.itemconfigure(self._sicbo_status_body_top, fill=background)
        c.itemconfigure(self._sicbo_status_badge_text, text=badge)
        c.itemconfigure(self._sicbo_status_caption, text=caption,
                        fill='black' if big_result else '#76634d')
        c.itemconfigure(self.animation_status_text, text=total, state='normal',
                        fill=result_text_color if finished else '#766853',
                        font=('Arial', 29 if finished else 28, 'bold'))
        c.itemconfigure(self.animation_phase_text, text=phase,
                        state='hidden' if finished else 'normal',
                        fill='#76520f' if state == 'rolling' else '#76634d')
        for item in self._sicbo_status_unknown_items:
            c.itemconfigure(item, state='hidden' if finished else 'normal')
        for item in self.animation_result_plus_items:
            c.itemconfigure(item, state='normal', fill='black' if big_result else '#574532')
        shown_dice = sorted(int(value) for value in result['dice']) if finished else []
        for index, item in enumerate(self.animation_result_dice_items):
            if finished:
                value = shown_dice[index]
                c.itemconfigure(item, image=self.dice_images_status[value-1], state='normal')
            else:
                c.itemconfigure(item, state='hidden')
        if finished:
            if result['is_triple']:
                description = '围骰'
            else:
                description = ('大' if result['total'] >= 11 else '小') + ' · ' + (
                    '双' if result['total'] % 2 == 0 else '单')
            c.itemconfigure(self.animation_result_suffix, text=description,
                            fill=result_text_color, state='normal')
        else:
            c.itemconfigure(self.animation_result_suffix, state='hidden')

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
        """Draw all 106 markets inside the original 852 by 368 betting area."""
        c = self.canvas
        self.board_bounds = (12, 252, 864, 620)
        colors = {
            'felt': '#322128', 'header': '#5e3039', 'header_text': '#f1dfb7',
            'light': '#dceef8', 'dark': '#dfc59c', 'ink': '#3d2928',
        }
        alternating = (colors['light'], colors['dark'])
        self.basic_payout_text_items = []
        self.basic_rule_text_items = []
        self._board_dice_item_images = {}

        def rect(bounds, fill, outline='', radius=0, tag=None):
            tags = ('board', tag) if tag else ('board',)
            x0, y0, x1, y1 = bounds
            if not radius:
                return c.create_rectangle(*bounds, fill=fill, outline=outline,
                                          width=1, tags=tags)
            r = radius
            return c.create_polygon(
                x0+r, y0, x1-r, y0, x1, y0, x1, y0+r,
                x1, y1-r, x1, y1, x1-r, y1, x0+r, y1,
                x0, y1, x0, y1-r, x0, y0+r, x0, y0,
                smooth=True, fill=fill, outline=outline, width=1, tags=tags)

        def label(x, y, text, size=12, color=None, bold=False,
                  anchor='center', tag=None):
            # Pixel sizes keep these compact headers independent of screen DPI.
            font = ('Arial', -size, 'bold') if bold else ('Arial', -size)
            return c.create_text(x, y, text=text, font=font,
                                 fill=color or colors['ink'], anchor=anchor,
                                 tags=('board', tag) if tag else ('board',))

        def bet(kind, param, bounds, fill, title, radius=2):
            x0, y0, x1, y1 = bounds
            tag = self.spot_tag((kind, param))
            self.register_spot(kind, param, *bounds,
                               ((x0+x1)/2, (y0+y1)/2), title)
            rect((x0+.5, y0+.5, x1-.5, y1-.5), fill, radius=radius, tag=tag)
            c.tag_bind(tag, '<Button-1>',
                       lambda _event, bt=kind, p=param: self.place_bet(bt, p))
            c.tag_bind(tag, '<Button-3>',
                       lambda _event, bt=kind, p=param: self.clear_single_bet(bt, p))
            return tag

        def dice(cx, cy, values, size=23, pitch=None, vertical=False, tag=None):
            pitch = pitch or size+4
            images = (self.dice_images_board if size == 23
                      else self.dice_images_board_sizes[size])
            for index, value in enumerate(values):
                delta = (index-(len(values)-1)/2)*pitch
                x, y = (cx, cy+delta) if vertical else (cx+delta, cy)
                photo = images[int(value)-1]
                item = c.create_image(x, y, image=photo,
                                      tags=('board', tag) if tag else ('board',))
                self._board_dice_item_images[item] = photo

        def section_header(x0, y0, x1, y1, title, odds, parts=None):
            rect((x0, y0, x1, y1), colors['header'])
            cy = (y0+y1)/2
            label(x0+8, cy, title, 12, colors['header_text'],
                  bold=True, anchor='w')
            fragments = parts or [(odds, 15)]
            items, widths = [], []
            for text, size in fragments:
                item = label(0, cy, text, size, colors['header_text'], bold=True)
                bounds = c.bbox(item)
                items.append(item)
                widths.append(bounds[2]-bounds[0])
            gap = 6
            x = (x0+x1-sum(widths)-gap*(len(items)-1))/2
            for item, width in zip(items, widths):
                c.coords(item, x+width/2, cy)
                x += width+gap

        def side_market(kind, title, bounds, range_text='', dark=False):
            x0, y0, x1, y1 = bounds
            fill = '#713441' if dark else colors['light']
            ink = '#fff3dc' if dark else '#56383a'
            secondary = '#dfbf83' if dark else '#82694b'
            tag = bet(kind, None, bounds, fill, title, radius=5)
            rect((x0+4, y0+4, x1-4, y1-4), '', '#b8955c', radius=3, tag=tag)
            cx = (x0+x1)/2
            label(cx, y0+31, title, 35, ink, bold=True, tag=tag)
            if range_text:
                item = label(cx, y0+59, range_text, 13, secondary, bold=True, tag=tag)
                if kind == 'small':
                    self.small_range_text = item
                else:
                    self.big_range_text = item
            payout = label(cx, y0+(81 if range_text else 72), '1:1',
                           20, ink, bold=True, tag=tag)
            rule = label(cx, y1-11, '围骰通杀', 9, secondary, tag=tag)
            self.basic_payout_text_items.append(payout)
            self.basic_rule_text_items.append(rule)

        rect(self.board_bounds, colors['felt'])

        # The existing insurance control stays centred below the last triple.
        triple_x0, _y0, triple_x1, triple_y1 = self._sicbo_triple_panel_bounds
        insurance_x = (triple_x0+triple_x1)/2
        self.insurance_mode_button = self.create_control_button(
            insurance_x-45, triple_y1+16, insurance_x+45, triple_y1+42,
            '保险~关', self.toggle_triple_mode, '#77383b', fg='white', font_size=10)
        c.tag_raise(self.insurance_mode_button)

        side_market('small', '小', (12, 252, 112, 360), '4—10', dark=True)
        side_market('odd', '单', (12, 364, 112, 472))
        side_market('big', '大', (764, 252, 864, 360), '11—17', dark=True)
        side_market('even', '双', (764, 364, 864, 472))

        section_header(116, 252, 356, 266, '对子', '11:1')
        section_header(444, 252, 760, 266, '指定围骰', '190:1')
        for number in range(1, 7):
            fill = alternating[(number-1) % 2]
            x0, x1 = 116+(number-1)*40, 116+number*40
            tag = bet('double', number, (x0, 266, x1, 310), fill, f'对子{number}')
            dice((x0+x1)/2, 288, (number, number), 20, 22, vertical=True, tag=tag)
            x0, x1 = 444+(number-1)*316/6, 444+number*316/6
            tag = bet('triple', number, (x0, 266, x1, 310), fill, f'围骰{number}')
            # 品: one die above two, preserving room for a full-size bet chip.
            dice((x0+x1)/2, 277, (number,), 20, tag=tag)
            dice((x0+x1)/2, 299, (number, number), 20, 22, tag=tag)
        tag = bet('all_triples', None, (360, 252, 440, 310),
                  '#d4b576', '任何围骰', radius=4)
        label(400, 269, '任何围骰', 15, '#4a3035', bold=True, tag=tag)
        label(400, 294, '31:1', 20, '#4a3035', bold=True, tag=tag)

        rect((116, 314, 144, 358), colors['header'], radius=2)
        label(130, 336, '总\n点', 12, colors['header_text'])
        for index, value in enumerate(range(4, 18)):
            x0, x1 = 144+index*44, 144+(index+1)*44
            tag = bet('total_points', value, (x0, 314, x1, 358),
                      alternating[index % 2], f'总点{value}')
            label((x0+x1)/2, 328, str(value), 20, bold=True, tag=tag)
            label((x0+x1)/2, 348, f'{self.engine.TOTAL_PAYOUT[value]}:1',
                  12, '#875c30', bold=True, tag=tag)

        rect((116, 362, 156, 410), colors['header'], radius=2)
        label(136, 377, '双骰', 12, colors['header_text'])
        label(136, 396, '6:1', 18, colors['header_text'], bold=True)
        for index, pair in enumerate(self.engine.PAIRS):
            x0, x1 = 156+index*604/15, 156+(index+1)*604/15
            tag = bet('pairs', pair, (x0, 362, x1, 410),
                      alternating[index % 2], f'组合{pair}')
            dice((x0+x1)/2, 386, tuple(map(int, pair.split('&'))),
                 21, 23, vertical=True, tag=tag)

        section_header(116, 414, 388, 428, '四数组合', '7:1')
        section_header(392, 414, 760, 428, '单骰', '', parts=[
            ('1颗', 11), ('1:1', 15), ('·', 11),
            ('2颗', 11), ('2:1', 15), ('·', 11),
            ('3颗', 11), ('12:1', 15)])
        for index, group in enumerate(self.engine.GROUPS):
            x0, x1 = 116+index*68, 116+(index+1)*68
            tag = bet('number_group', group, (x0, 428, x1, 472),
                      alternating[index % 2], f'四数组合{group}')
            values = tuple(map(int, group))
            dice((x0+x1)/2, 439, values[:2], 19, 23, tag=tag)
            dice((x0+x1)/2, 461, values[2:], 19, 23, tag=tag)
        for number, chinese in enumerate('一二三四五六', start=1):
            x0, x1 = 392+(number-1)*368/6, 392+number*368/6
            tag = bet('guess_num', number, (x0, 428, x1, 472),
                      alternating[(number-1) % 2], f'单骰{number}')
            dice((x0+x1)/2-10, 450, (number,), 25, tag=tag)
            label((x0+x1)/2+19, 450, chinese, 15, tag=tag)

        # AAB: 30 choices in ten columns. ABC: 7, 7, 6 choices. Every
        # 41px-high cell fits the unchanged 38px chip with no overlap.
        aab_right = 12+(852-4)*10/17
        left_centre = (12+aab_right)/2
        right_centre = (aab_right+4+864)/2
        rect((12, 476, 864, 497), colors['header'])
        label(left_centre, 486.5, '60:1', 18, colors['dark'], bold=True)
        label((left_centre+right_centre)/2, 486.5,
              '骰子组合', 16, colors['header_text'], bold=True)
        label(right_centre, 486.5, '30:1', 18, colors['light'], bold=True)
        exact_panels = (
            ('exact_aab', 12, aab_right, (10, 10, 10), self.engine.EXACT_AAB,
             colors['dark'], '#6b3640', '#bea17a'),
            ('exact_abc', aab_right+4, 864, (7, 7, 6), self.engine.EXACT_ABC,
             colors['light'], '#344d5b', '#c6b58f'),
        )
        for kind, x0, x1, row_counts, values, fill, ink, grid in exact_panels:
            index = 0
            for row, columns in enumerate(row_counts):
                width = (x1-x0)/columns
                for col in range(columns):
                    combination = values[index]
                    left, top = x0+col*width, 497+row*41
                    bounds = (left, top, left+width, top+41)
                    title = '·'.join(combination)
                    tag = bet(kind, combination, bounds, fill,
                              f'骰子组合{title}', radius=0)
                    rect(bounds, '', grid, tag=tag)
                    label(left+width/2, top+20.5, title, 15, ink, bold=True, tag=tag)
                    index += 1

        # One overall outline, with no additional frames around sections.
        c.create_rectangle(*self.board_bounds, fill='', outline='#a68c60',
                           width=1, tags=('board', 'board_outer_frame'))


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
        """Keep the existing help-button callback compatible."""
        return self.show_game_instructions()

    def showgameinstruction(self):
        """Compatibility entry point for the instruction UI."""
        return self.show_game_instructions()

    def show_game_instructions(self):
        """按原版卡片式布局显示本游戏的图解说明。"""
        import tkinter as tk
        import tkinter.font as tkfont

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
        dialog = tk.Toplevel(owner)
        self._game_instruction_dialog = dialog
        dialog.title('骰宝 · 完整图解玩法')
        dialog.configure(bg='#faf5e8')
        dialog.resizable(False, False)
        dialog.transient(parent)
        width, height = 1000, min(670, max(400, parent.winfo_screenheight() - 80))
        parent.update_idletasks()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = max(1, parent.winfo_width()), max(1, parent.winfo_height())
        dialog.geometry(f'{width}x{height}+{max(0, px + (pw-width)//2)}+{max(0, py + (ph-height)//2)}')

        manual_pages = [('玩法',
          '摇动三颗骰子，按点数、总和及组合逐项结算。',
          [('一局如何进行',
            '',
            [('① 选择筹码与下注', '左键点击下注区域加注，可同时下注多项；右键点击区域清除该项。\n下注时立即扣除余额，清除尚未开局的下注会退回筹码。'),
             ('② 转动三颗骰子', '点击“转动”或在游戏窗口按 Enter 开局，也可零下注试玩。\n转动与结算期间暂停下注、清除、重复下注及切换保险。'),
             ('③ 逐项结算', '同一结果可命中多项下注；中奖项返还本金及盈利，未中奖项不返还。')],
            []),
           ('三骰结果示意', '', [], []),
           ('赔率如何阅读', '', [('盈利与返还', '本说明中的 x:1 均为盈利赔率，不包含本金。\n中奖返还＝该项下注 ×（赔率＋1）；净盈亏＝总返还－总下注。')], [])]),
         ('下注 & 赔率',
          '赔率为盈利倍数；各中奖项目独立计算。',
          [('下注项目',
            '',
            [],
            [('基础赔率',
              ['项目', '中奖条件', '盈利赔率'],
              [['小 / 大', '小 4–10；大 11–17。保险关闭时围骰不中奖。', '1:1'],
               ['单 / 双', '按三骰总点数的奇偶判断。保险关闭时围骰不中奖。', '1:1'],
               ['对子', '指定点数出现至少两颗；三颗相同也中奖。', '11:1'],
               ['指定围骰', '三颗骰子全部为指定点数。', '190:1'],
               ['任何围骰', '任意三颗骰子点数相同。', '31:1'],
               ['两骰组合', '指定的两种不同点数同时出现，第三颗不限。', '6:1'],
               ['四数组合', '三颗互不重复，且全部属于所选四个点数。', '7:1'],
               ['单骰', '所选点数出现 1 / 2 / 3 颗；未出现则输。', '1:1 / 2:1 / 12:1']])]),
           ('总点数',
            '',
            [('猜中三骰总和', '可押 4 至 17 点；三骰总和等于所押点数即中奖，围骰也计入。')],
            [('总点数赔率',
              ['总点数', '基础盈利赔率'],
              [['4 / 17', '62:1'],
               ['5 / 16', '31:1'],
               ['6 / 15', '18:1'],
               ['7 / 14', '12:1'],
               ['8 / 13', '8:1'],
               ['9 / 12', '7:1'],
               ['10 / 11', '6:1']])]),
           ('四数组合示意', '', [], []),
           ('下注限额',
            '',
            [('限额与余额', '下注受单区上限、全台上限及余额限制。若剩余额度不足，系统会提示并自动缩减本次金额。')],
            [('当前限额', ['单次请求最低', '单区最高', '全台最高'], [['{MIN_BET}', '{MAX_AREA_BET}', '{MAX_TABLE_BET}']])])]),
         ('保险模式',
          '保险只改变小、大、单、双的中奖规则与赔率。',
          [('保险开关',
            '',
            [('何时切换', '开局前点击“保险~开 / 保险~关”切换；转动或结算期间不可切换。\n开关状态适用于本局全部小、大、单、双下注。')],
            [('规则对照',
              ['项目', '保险关闭', '保险开启'],
              [['小', '4–10 点；围骰输', '3–10 点；围骰按总点判断'],
               ['大', '11–17 点；围骰输', '11–18 点；围骰按总点判断'],
               ['单 / 双', '按总点奇偶；围骰输', '按总点奇偶；包含围骰'],
               ['盈利赔率', '1:1', '0.95:1']])]),
           ('围骰与保险示意', '', [], []),
           ('其他下注',
            '',
            [('规则保持一致', '对子、指定围骰、任何围骰、两骰组合、总点数、四数组合与单骰，均按各自规则结算。\n保险不会让所有下注都获赔，也不会增加其他项目的赔率。')],
            [])]),
         ('操作 & 记录',
          '下注阶段可调整筹码；历史面板可切换记录和统计。',
          [('常用操作',
            '',
            [],
            [('操作对照',
              ['操作', '作用'],
              [['筹码按钮 + 左键', '选择金额后，点击下注区域逐次加注。'],
               ['右键下注区域', '清除该区全部未开奖下注并退回金额。'],
               ['清除下注', '清空本局全部未开奖下注并退回金额。'],
               ['Ctrl+Z', '游戏框架获得键盘焦点时，撤销最近一笔加注。'],
               ['重复下注', '把最近一次有下注的金额追加到当前下注；不会先清空。余额须足够，仍受限额限制。'],
               ['转动 / Enter', '开始本局；动画与结算中不可再次开局。'],
               ['关闭 / Esc', '关闭本说明窗口。']])]),
           ('历史记录',
            '',
            [('记录与统计切换', '点击历史面板标题，切换最近 15 局记录与最近最多 500 局统计。'),
             ('围骰单独归类', '统计中的小 / 大 / 围、单 / 双 / 围会把围骰单独计数；即使开启保险，也仍显示为围骰。')],
            [])]),
         ('结算示例',
          '以下金额均区分盈利与含本金返还。',
          [('多个项目同时中奖',
            '',
            [('结果：1、2、3；保险关闭', '“小”下注 $10，“两骰组合 1+2”下注 $10。\n小返还 $20；组合以 6:1 返还 $70。\n总返还 $90；总下注 $20；净赢 $70。')],
            []),
           ('围骰与保险',
            '',
            [('结果：2、2、2；只在“小”下注 $10', '保险关闭：围骰不赔，返还 $0，净亏 $10。\n保险开启：总点 6 属于小，按 0.95:1 返还 $19.50，净赢 $9.50。')],
            []),
           ('单骰三颗结算',
            '',
            [('结果：3、3、3；只在号码 3 下注 $10',
              '单骰出现 3 颗的赔率为 12:1。\n返还 $10 ×（12＋1）＝$130；净赢 $120。\n如同时下注指定围骰或任何围骰，各项另行计算。')],
            [])])]
        # Read limit values from the game so the manual stays in sync.
        limit_text = {
            '{MIN_BET}': f'${self.MIN_BET:,.2f}',
            '{MAX_AREA_BET}': f'${self.MAX_AREA_BET:,.2f}',
            '{MAX_TABLE_BET}': f'${self.MAX_TABLE_BET:,.2f}',
        }
        for _title, _subtitle, cards in manual_pages:
            for _card_title, _card_subtitle, _rules, tables in cards:
                for _table_title, _headers, rows in tables:
                    for row in rows:
                        row[:] = [limit_text.get(value, value) for value in row]
        illustration_cards = {
            '三骰结果示意': 'result',
            '四数组合示意': 'group',
            '围骰与保险示意': 'insurance',
            '三军金色示意': 'super',
        }

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
        tk.Label(header, text='骰宝 · 完整图解玩法', font=(font_name, 20, 'bold'),
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
            available = 700
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
            # Draw actual dice pips; no image assets or extra dependencies needed.
            examples = {
                'result': [((1, 2, 3), '总点 6 · 小 · 双', '可同时命中小、双、总点 6、两骰组合等项目。')],
                'group': [((1, 2, 4), '四数组合 1234：中奖', '三颗不同，且全部属于 1、2、3、4。'),
                          ((1, 1, 4), '四数组合 1234：不中奖', '虽在所选范围内，但点数重复。')],
                'insurance': [((2, 2, 2), '围骰 · 总点 6', '保险关：小、双均输。保险开：小、双均按 0.95:1 赔。')],
                'super': [((3, 3, 3), '号码 3 金色：2颗 12:1', '实际出现 3 颗，按较高的 12:1 结算。')],
            }
            rows = examples[kind]
            c = tk.Canvas(parent_frame, width=700, height=132 * len(rows),
                          bg=PANEL, highlightthickness=0)
            c.pack(padx=16, pady=(5, 10))
            pips = {
                1: ((1, 1),),
                2: ((0, 0), (2, 2)),
                3: ((0, 0), (1, 1), (2, 2)),
                4: ((0, 0), (2, 0), (0, 2), (2, 2)),
                5: ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)),
                6: ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2)),
            }
            for row, (dice, title, detail) in enumerate(rows):
                y = row * 132 + 10
                for index, number in enumerate(dice):
                    x = 10 + index * 68
                    c.create_rectangle(x, y, x + 56, y + 56,
                                       fill='#fffaf0', outline=BORDER, width=2)
                    for col, line in pips[number]:
                        px, py = x + 13 + col * 15, y + 13 + line * 15
                        c.create_oval(px - 4, py - 4, px + 4, py + 4,
                                      fill='#b13d35' if number in (1, 4) else TEXT, outline='')
                c.create_text(225, y + 25, text=title, anchor='w', width=455,
                              fill=GOLD, font=(font_name, 16, 'bold'))
                c.create_text(10, y + 77, text=detail, anchor='nw', width=680,
                              fill=MUTED, font=(font_name, 14))

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
        enabled = (self.accept_bets and not self.animation_running
                   and not self.settlement_running and not self._chips_moving())
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
        key = (bet_type, param)
        spot = self.bet_spots.get(key)
        if spot:
            self._pending_bet_amounts[key] = self._pending_bet_amounts.get(key, 0.0) + allowed
        self.update_display()
        self.save_balance()
        if spot:
            def arrived():
                remaining = self._pending_bet_amounts.get(key, 0.0) - allowed
                if remaining > 1e-9:
                    self._pending_bet_amounts[key] = remaining
                else:
                    self._pending_bet_amounts.pop(key, None)
                self.update_bet_chips()
            self._animate_sicbo_chip(
                allowed, self._chip_rack_position(allowed), self._bet_chip_position(spot),
                arrived, start_radius=27)
        return True

    def clear_single_bet(self, bet_type, param=None):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or self._chips_moving()):
            return
        refunded = self.engine.clear_area(bet_type, param)
        if refunded <= 0:
            return
        self.balance += refunded
        self.undo_stack = [item for item in self.undo_stack if item[:2] != (bet_type, param)]
        self.update_display()
        self.save_balance()
        self._return_bet_chips([((bet_type, param), refunded)])

    def undo_last_bet(self):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or self._chips_moving()):
            return
        while self.undo_stack:
            bet_type, param, amount = self.undo_stack.pop()
            removed = self.engine.remove_amount(bet_type, amount, param)
            if removed > 0:
                self.balance += removed
                self.update_display()
                self.save_balance()
                self._return_bet_chips([((bet_type, param), removed)])
                return

    def clear_bets(self):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or self._chips_moving()):
            return
        refunded = self.engine.total_at_risk()
        if refunded <= 0:
            return
        self.balance += refunded
        returning = [((bet_type, param), amount)
                     for bet_type, param, amount in self.snapshot_bets()]
        self.engine.bets = self.engine.new_bets()
        self.undo_stack.clear()
        self.update_display()
        self.save_balance()
        self._return_bet_chips(returning)

    def repeat_last_bets(self):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or self._chips_moving() or not self.last_round_bets):
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
        payout_label = '0.95:1' if self.triple_mode else '1:1'
        for item_id in getattr(self, 'basic_payout_text_items', []):
            self.canvas.itemconfigure(item_id, text=payout_label)
        rule_label = '围骰赔付' if self.triple_mode else '围骰通杀'
        for item_id in getattr(self, 'basic_rule_text_items', []):
            self.canvas.itemconfigure(item_id, text=rule_label)
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
            settled_winner = self.settlement_running and key in self.flash_original_amounts
            if settled_winner and self._settlement_chips_returning:
                continue
            amount = (self.flash_original_amounts[key] if settled_winner else
                      self.engine.current_area_bet(*key) - self._pending_bet_amounts.get(key, 0.0))
            if settled_winner and self.flash_mode == 'win':
                amount = self.flash_winner_amounts.get(key, amount)
            if amount <= 0:
                continue
            tags = ('bet_chip_dynamic', spot['tag'])
            self._draw_sicbo_chip(amount, *self._bet_chip_position(spot), (*tags, 'stake_chip'))
        self.canvas.tag_raise('bet_chip_label')

    def _bet_chip_position(self, spot):
        x, y = spot['chip_pos']
        x0, y0, x1, y1 = spot['bounds']
        inset_x = min(self.BET_CHIP_RADIUS + 1, (x1-x0)/2)
        inset_y = min(self.BET_CHIP_RADIUS + 1, (y1-y0)/2)
        x = max(x0+inset_x, min(x1-inset_x, x))
        y = max(y0+inset_y, min(y1-inset_y, y))
        return x, y

    def _draw_sicbo_chip(self, amount, x, y, tags, radius=None):
        radius = self.BET_CHIP_RADIUS if radius is None else radius
        color = self.bet_chip_color(amount)
        self.canvas.create_oval(
            x-radius, y-radius, x+radius, y+radius,
            fill='#292522', outline='#151311', width=1, tags=tags)
        inner = radius-3
        self.canvas.create_oval(
            x-inner, y-inner, x+inner, y+inner,
            fill=color, outline='#e2ddd5', width=1, tags=tags)
        text = self._compact_amount(amount)
        font_size = max(6, min(9, 13-len(text)))
        self.canvas.create_text(
            x, y, text=text, font=('Arial', font_size, 'bold'),
            fill=self.contrast_text_color(color), tags=(*tags, 'bet_chip_label'))

    def _chips_moving(self):
        return bool(getattr(self, '_chip_motion_count', 0))

    def _chip_rack_position(self, amount):
        index = 0
        for candidate, (threshold, _color, _label) in enumerate(self.CHIP_SPECS):
            if amount >= threshold:
                index = candidate
            else:
                break
        return 447 + index*57, 672

    def _animate_sicbo_chip(self, amount, start, target, complete=None,
                            start_radius=None, end_radius=None):
        if amount <= 0 or self._closing:
            if complete and not self._closing:
                complete()
            return
        self._chip_motion_count += 1
        self._chip_serial += 1
        tag = f'chip_motion_{self._chip_serial}'
        start_radius = self.BET_CHIP_RADIUS if start_radius is None else start_radius
        end_radius = self.BET_CHIP_RADIUS if end_radius is None else end_radius
        steps = max(1, math.ceil(self.CHIP_MOVE_MS/16))
        self.update_control_states()

        def frame(index):
            if self._closing:
                return
            self.canvas.delete(tag)
            t = index/steps
            t = t*t*(3-2*t)
            self._draw_sicbo_chip(
                amount, start[0]+(target[0]-start[0])*t,
                start[1]+(target[1]-start[1])*t,
                (tag, 'chip_motion'), radius=start_radius+(end_radius-start_radius)*t)
            self.canvas.tag_raise('chip_motion')
            self.canvas.tag_raise('bet_chip_label')
            if index < steps:
                delay = round((index+1)*self.CHIP_MOVE_MS/steps)-round(index*self.CHIP_MOVE_MS/steps)
                job_id = None
                def tick():
                    self._chip_motion_jobs.discard(job_id)
                    frame(index+1)
                job_id = self.after(delay, tick)
                self._chip_motion_jobs.add(job_id)
            else:
                self.canvas.delete(tag)
                self._chip_motion_count -= 1
                if complete:
                    complete()
                self.update_control_states()
        frame(0)

    def _run_sicbo_chip_batch(self, transfers, complete=None):
        transfers = [transfer for transfer in transfers if transfer['amount'] > 0]
        if not transfers:
            if complete:
                complete()
            return
        pending = len(transfers)
        def arrived(transfer):
            nonlocal pending
            if transfer.get('arrive'):
                transfer['arrive']()
            pending -= 1
            if pending == 0 and complete:
                complete()
        for transfer in transfers:
            self._animate_sicbo_chip(
                transfer['amount'], transfer['start'], transfer['target'],
                lambda transfer=transfer: arrived(transfer),
                start_radius=transfer.get('start_radius'), end_radius=transfer.get('end_radius'))

    def _return_bet_chips(self, entries):
        transfers = []
        for key, amount in entries:
            spot = self.bet_spots.get(key)
            if spot and amount > 0:
                transfers.append(dict(amount=amount, start=self._bet_chip_position(spot),
                                      target=self._chip_rack_position(amount), end_radius=27))
        self._run_sicbo_chip_batch(transfers)

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
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or self._chips_moving()):
            return
        self.accept_bets = False
        self.animation_running = True
        self._sicbo_recovering = self._sicbo_round_voided = False
        current_round_bets = self.snapshot_bets()
        if current_round_bets:
            self.last_round_bets = current_round_bets
        self.undo_stack.clear()

        self.animation_final_dice = None
        self.animation_frames_left = 0
        self._set_sicbo_status('rolling')
        self.update_control_states()
        self._start_sicbo_dice_roll()

    def _draw_sicbo_dice(self):
        picture = _gd_render_bowl(self._sicbo_bowl)
        photo = ImageTk.PhotoImage(picture, master=self.canvas)
        if self._sicbo_cup_item is not None and self.canvas.find_withtag('animation_dice'):
            self.canvas.itemconfigure(self._sicbo_cup_item, image=photo)
        else:
            self._sicbo_cup_item = self.canvas.create_image(
                *self._sicbo_cup_position, anchor='n', image=photo,
                tags=('animation', 'animation_dice'))
        self._sicbo_cup_photo = photo
        self.animation_dice_items = [self._sicbo_cup_item]

    def _start_sicbo_dice_roll(self):
        if (self._closing or not self.animation_running or self.settlement_running
                or self.animation_final_dice is not None or self._sicbo_recovering):
            return
        self._cancel_sicbo_result_timeout()
        self._sicbo_bowl.begin()
        self._sicbo_dice_phase = 'shake'
        self._sicbo_dice_time = self._sicbo_dice_stable_time = 0.
        self._sicbo_dice_rest_anchor = None
        self.animate_dice()

    def _sicbo_dice_is_motionless(self, dt):
        pose = tuple(point for die in self._sicbo_bowl.dice for point in die.vertices())
        anchor = self._sicbo_dice_rest_anchor
        if anchor is None or any(_gd_length(_gd_sub(p, q)) > .00005 for p, q in zip(pose, anchor)):
            self._sicbo_dice_rest_anchor = pose
            self._sicbo_dice_stable_time = 0.
            return False
        self._sicbo_dice_stable_time += dt
        return self._sicbo_dice_stable_time >= .65


    def animate_dice(self):
        if (self._closing or not self.animation_running
                or self._sicbo_dice_phase not in ('shake', 'settle')):
            return
        if (self._sicbo_dice_phase == 'settle' and self._sicbo_result_deadline is not None
                and time.monotonic() >= self._sicbo_result_deadline):
            self._sicbo_result_timed_out()
            return
        started = time.monotonic()
        bowl = self._sicbo_bowl
        valid_result = False
        dt = 1/480
        for _ in range(16):
            if self._sicbo_dice_phase == 'shake':
                self._sicbo_dice_time += dt
                bowl.step(dt, self._sicbo_dice_time, self._sicbo_dice_time < bowl.duration)
                if self._sicbo_dice_time >= bowl.duration:
                    self._sicbo_dice_phase = 'settle'
                    self._arm_sicbo_result_timeout()
            else:
                bowl.step(dt, 0., False)
                if self._sicbo_dice_is_motionless(dt):
                    if bowl.landing_error():
                        if self._sicbo_recovering:
                            self._draw_sicbo_dice()
                            self._queue_sicbo_recovery()
                            return
                        continue
                    for die in bowl.dice:
                        die.v = die.omega = (0., 0., 0.)
                    valid_result = True
                    break
        if valid_result:
            if (self._sicbo_result_deadline is not None
                    and time.monotonic() >= self._sicbo_result_deadline):
                self._sicbo_result_timed_out()
                return
            if self._sicbo_recovering:
                self._cancel_sicbo_result_timeout()
                self._draw_sicbo_dice()
                self._finish_sicbo_recovery()
                return
            # Read the three upward faces only after the bodies have stopped.
            # From here on, rendering and settlement never change their poses.
            try:
                final_dice = bowl.values()
            except ValueError:
                valid_result = False
            else:
                self._cancel_sicbo_result_timeout()
                self.animation_final_dice = final_dice
                self.animation_frames_left = 0
                self._sicbo_dice_phase = 'landed'
        self._draw_sicbo_dice()
        if not valid_result:
            delay = max(1, 33-round((time.monotonic()-started)*1000))
            self.animation_after_id = self.after(delay, self.animate_dice)
            return
        self.animation_after_id = self.after(0, self.finish_roll)

    def _cancel_sicbo_result_timeout(self):
        if self._sicbo_result_timeout_id is not None:
            try:
                self.after_cancel(self._sicbo_result_timeout_id)
            except (tk.TclError, ValueError):
                pass
        self._sicbo_result_timeout_id = self._sicbo_result_deadline = None

    def _arm_sicbo_result_timeout(self):
        self._cancel_sicbo_result_timeout()
        self._sicbo_result_deadline = time.monotonic()+self.DICE_RESULT_TIMEOUT_MS/1000
        self._sicbo_result_timeout_id = self.after(
            self.DICE_RESULT_TIMEOUT_MS, self._sicbo_result_timed_out)

    def _sicbo_result_timed_out(self):
        if (self._closing or not self.animation_running
                or self._sicbo_dice_phase != 'settle'
                or self.animation_final_dice is not None
                or self._sicbo_result_deadline is None):
            return
        remaining = self._sicbo_result_deadline-time.monotonic()
        if remaining>0:
            self._sicbo_result_timeout_id = self.after(
                max(1, math.ceil(remaining*1000)), self._sicbo_result_timed_out)
            return
        self._cancel_sicbo_result_timeout()
        if self._sicbo_recovering:
            self._queue_sicbo_recovery()
        else:
            self._void_sicbo_round()

    def _queue_sicbo_recovery(self):
        if self._closing or not self._sicbo_recovering:
            return
        self._cancel_sicbo_result_timeout()
        if self.animation_after_id is not None:
            try:
                self.after_cancel(self.animation_after_id)
            except (tk.TclError, ValueError):
                pass
        self._sicbo_dice_phase = 'recovery_wait'
        self.animation_final_dice = None
        self.animation_after_id = self.after(0, self._start_sicbo_recovery)

    def _void_sicbo_round(self):
        if (self._closing or self._sicbo_round_voided or self.settlement_running
                or not self.animation_running or self.animation_final_dice is not None):
            return
        self._sicbo_round_voided = self._sicbo_recovering = True
        refunds = [((kind,param),amount) for kind,param,amount in self.snapshot_bets()]
        refunded = self.engine.total_at_risk()
        # Clear paid stakes before crediting them so close/repeated callbacks cannot refund twice.
        self.engine.bets = self.engine.new_bets()
        self.balance += refunded
        self.undo_stack.clear()
        self.pre_roll_bets = None
        self.cancel_pending_callbacks()
        self.canvas.delete('win_flash_area')
        self.restore_flash_text_colors()
        self.flash_mode = None
        self.flash_winning_keys.clear()
        self.flash_winner_amounts.clear()
        self.flash_original_amounts.clear()
        self._settlement_chips_returning = False
        self.summary_mode = 'bet'
        self.accept_bets = False
        self._set_sicbo_status('recovering')
        self.update_display()
        self.save_balance()
        self._return_bet_chips(refunds)
        self._queue_sicbo_recovery()

    def _start_sicbo_recovery(self):
        if self._closing or not self._sicbo_recovering or not self._sicbo_round_voided:
            return
        self.animation_after_id = None
        self._cancel_sicbo_result_timeout()
        # A fresh, separated physical starting pose prevents a bad stack persisting.
        self._sicbo_bowl = GoldenDiceBowl(rng=self._sicbo_bowl.rng)
        self._sicbo_bowl.begin(duration=self.DICE_RECOVERY_SHAKE_SECONDS)
        self._sicbo_dice_phase = 'shake'
        self._sicbo_dice_time = self._sicbo_dice_stable_time = 0.
        self._sicbo_dice_rest_anchor = None
        self.animation_final_dice = None
        self.animate_dice()

    def _finish_sicbo_recovery(self):
        if self._closing or not self._sicbo_recovering:
            return
        if not self._sicbo_bowl.settled() or self._sicbo_bowl.landing_error():
            self._queue_sicbo_recovery()
            return
        self._cancel_sicbo_result_timeout()
        if self._chips_moving():
            self._sicbo_dice_phase = 'recovery_ready'
            self.animation_after_id = self.after(16, self._finish_sicbo_recovery)
            return
        self.animation_after_id = None
        self._sicbo_dice_phase = 'idle'
        self._sicbo_recovering = False
        self.animation_running = self.settlement_running = False
        self.animation_final_dice = None
        self.accept_bets = True
        self._set_sicbo_status('ready')
        self.update_display()

    def finish_roll(self):
        if (self._closing or not self.animation_running or self.settlement_running
                or self._sicbo_recovering or self._sicbo_round_voided
                or self._sicbo_dice_phase != 'landed' or self.animation_final_dice is None):
            return
        self._sicbo_dice_phase = 'result'
        # Retain the stake and total return for the alternating win display.
        self.pre_roll_bets = copy.deepcopy(self.engine.bets)
        result = self.engine.resolve_roll(self.animation_final_dice, self.triple_mode)
        self.balance += result['credit']
        self.last_win_amount = result['credit']
        self.last_net = result['net']
        self.add_history(result)

        # Every objectively winning betting area flashes, even if no chip was placed.
        self.flash_winning_keys = self.winning_keys_for_result(result)
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self._settlement_chips_returning = False
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

        # Clear one-roll bets; a single result chip remains at each winning spot.
        self.engine.bets = self.engine.new_bets()
        self.summary_mode = 'win'
        self._set_sicbo_status('result', result)

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

        # Lost stakes leave their betting spots and disappear at the title.
        transfers = []
        for outcome in result.get('outcomes', []):
            if outcome.get('status') != 'lose' or not outcome.get('key'):
                continue
            spot = self.bet_spots.get(tuple(outcome['key']))
            amount = float(outcome.get('stake', 0.0))
            if spot and amount > 0:
                transfers.append(dict(amount=amount, start=self._bet_chip_position(spot),
                                      target=self._sicbo_title_position))
        self._run_sicbo_chip_batch(transfers)

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

        exact_key = SicboEngine.exact_combination_key(dice)
        if exact_key is not None:
            keys.add(exact_key)

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
        """Dim non-winners and alternate winning cells between gold and white."""
        if self._closing or not self.settlement_running:
            return
        if self.settlement_flash_step >= 6:
            self.settlement_after_id = None
            self._return_settlement_chips()
            return

        self.flash_mode = 'win' if self.settlement_flash_step % 2 == 0 else 'original'
        self.canvas.delete('win_flash_area')
        if not self._settlement_spot_styles:
            self._prepare_settlement_board()
        for key in self.flash_winning_keys:
            self._paint_settlement_spot(key, 'gold' if self.flash_mode == 'win' else 'white')

        self.update_bet_chips()
        self.canvas.tag_raise('bet_chip_dynamic')
        self.canvas.tag_raise('controls')
        if getattr(self, 'insurance_mode_button', None):
            self.canvas.tag_raise(self.insurance_mode_button)

        self.settlement_flash_step += 1
        self.settlement_after_id = self.after(self.SETTLEMENT_FLASH_MS, self.run_settlement_flash)

    def _prepare_settlement_board(self):
        """Remember the real shapes, borders, text and dice before any shading."""
        for key, spot in self.bet_spots.items():
            items = []
            for item in self.canvas.find_withtag(spot['tag']):
                if 'board' not in self.canvas.gettags(item):
                    continue
                kind = self.canvas.type(item)
                style = {}
                if kind == 'image':
                    image = self._board_dice_item_images.get(item)
                    if image is not None:
                        style['image'] = image
                else:
                    for option in ('fill', 'outline'):
                        try:
                            style[option] = self.canvas.itemcget(item, option)
                        except tk.TclError:
                            pass
                items.append((item, kind, style))
            self._settlement_spot_styles[key] = items
        for key in self.bet_spots:
            if key not in self.flash_winning_keys:
                self._paint_settlement_spot(key, 'dim')

    def _paint_settlement_spot(self, key, mode):
        """Recolour existing items so rounded corners and decorative borders stay."""
        for item, kind, original in self._settlement_spot_styles.get(key, []):
            style = dict(original)
            if mode == 'dim':
                for option in ('fill', 'outline'):
                    if style.get(option):
                        style[option] = self.shade_color(style[option], .42)
                image = style.get('image')
                if image is not None:
                    cache_key = id(image)
                    if cache_key not in self._settlement_dim_images:
                        picture = image if isinstance(image, Image.Image) else ImageTk.getimage(image)
                        self._settlement_dim_images[cache_key] = ImageTk.PhotoImage(
                            ImageEnhance.Brightness(picture).enhance(.42))
                    style['image'] = self._settlement_dim_images[cache_key]
            elif mode in ('gold', 'white'):
                if kind == 'text':
                    style['fill'] = '#211608'
                elif kind != 'image':
                    if style.get('fill'):
                        style['fill'] = self.SETTLEMENT_GOLD if mode == 'gold' else self.SETTLEMENT_WHITE
                    if style.get('outline'):
                        style['outline'] = '#79551b'
            if style:
                self.canvas.itemconfigure(item, **style)

    def _restore_settlement_board(self):
        for key in self._settlement_spot_styles:
            self._paint_settlement_spot(key, 'original')
        self._settlement_spot_styles.clear()
        self._settlement_dim_images.clear()

    def _return_settlement_chips(self):
        if self._closing or self._settlement_chips_returning:
            return
        self._settlement_chips_returning = True
        self.canvas.delete('win_flash_area')
        self.restore_flash_text_colors()
        for key in self.flash_winning_keys:
            self._paint_settlement_spot(key, 'white')
        transfers = []
        for key, amount in self.flash_winner_amounts.items():
            spot = self.bet_spots.get(key)
            if not spot:
                continue
            if amount > 0:
                transfers.append(dict(amount=amount, start=self._bet_chip_position(spot),
                                      target=self._chip_rack_position(amount), end_radius=27))
        self.update_bet_chips()
        self._run_sicbo_chip_batch(transfers, self.finish_settlement)

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
        self.restore_flash_text_colors()
        self._restore_settlement_board()
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self._settlement_chips_returning = False
        self.pre_roll_bets = None
        self.settlement_running = False
        self.animation_running = False
        self._sicbo_dice_phase = 'idle'
        self.accept_bets = True
        self._set_sicbo_status('ready')
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




    # ---------------------------------------------------------------- lifecycle
    def save_balance(self):
        if self.username:
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def cancel_pending_callbacks(self):
        self._cancel_sicbo_result_timeout()
        for after_id in (
            self.animation_after_id, self.result_after_id,
            self.flash_after_id, self.settlement_after_id,
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
        for job_id in tuple(self._chip_motion_jobs):
            try:
                self.after_cancel(job_id)
            except (tk.TclError, ValueError):
                pass
        self._chip_motion_jobs.clear()
        self._chip_motion_count = 0
        self._pending_bet_amounts.clear()
        self.canvas.delete('chip_motion')

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


# Backward-compatible class name used by the original Sicbo module.
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
    """Open Sic Bo as an embedded Frame or as an independent window.

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
    root.title('骰宝')
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
