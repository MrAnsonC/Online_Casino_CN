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

from A_Tools.Progressive.secure_json import (
    DATA_PATH as _progressive_file,
    install_secure_json as _install_progressive_secure_json,
)
_install_progressive_secure_json()
del _install_progressive_secure_json

import copy
import importlib.util
import json
import math
import os
import random
import re
import secrets
import sys
import time
import tkinter as tk
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from tkinter import messagebox, ttk

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageChops, ImageFilter
except ImportError:  # external artwork fallback still works with Canvas primitives
    Image = None
    ImageTk = None
    ImageDraw = None
    ImageFont = None
    ImageChops = None
    ImageFilter = None


# -----------------------------------------------------------------------------
# Account-data compatibility with the original project
# -----------------------------------------------------------------------------
def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../A_Tools/Account/saving_data.json')


def format_two_decimals(value):
    """赔率四舍五入到两位小数；整数省略小数部分。"""
    rounded = Decimal(str(value)).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP
    )

    if rounded == rounded.to_integral_value():
        return str(int(rounded))

    return f'{rounded:.2f}'


def round_two_decimals_value(value):
    """Round an actual settlement odds value to 2 decimals using ROUND_HALF_UP."""
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


GD_PIPS = {
    1: ((0, 0),), 2: ((-1, -1), (1, 1)),
    3: ((-1, -1), (0, 0), (1, 1)),
    4: ((-1, -1), (1, -1), (-1, 1), (1, 1)),
    5: ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)),
    6: ((-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)),
}

# World-space rigid cubes; geometry is shared by collision, rendering and scoring.
GD_SCENE_UNIT = 600.0
GD_DICE_EDGE_PX = 22.0
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
    RADIUS = .085
    HEIGHT = .128

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
    """BacBo's transparent dome and ceramic dish, with standard gold dice."""
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
    profile = [(.083, 0.), (.088, .005), (.093, .002), (.094, -.007),
               (.092, -.014), (.083, -.020)]
    rings = [ring(radius, z) for radius, z in profile]
    for k in range(32):
        j = (k+1)%32
        face([bowl.world(p) for p in ((0.,0.,0.), rings[0][k], rings[0][j])], (248,234,197,255))
        face([bowl.world(p) for p in ((0.,0.,-.020), rings[-1][j], rings[-1][k])], (142,111,70,255))
    for a,b,color in zip(rings,rings[1:],((187,151,99),(255,231,176),(191,158,107),(243,215,156),(148,117,75))):
        band(a,b,color)
    # The dish is below the bodies. Sorting its large triangles against the
    # small cube faces by average depth can paint the dish over a resting die.
    # Keep the whole support surface behind the dice, with glass in front.
    dish = sorted(solids,key=lambda f:f[0])
    solids = []
    for die in bowl.dice:
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
            rgb = tuple(round(channel*shade) for channel in bowl.color)+(255,)
            rim = tuple(round(channel*.55) for channel in bowl.color)+(255,)
            face_depth = face(corners, rgb, rim, .35)
            for px, py in GD_PIPS[number]:
                centerx, centery = px*die.EDGE*.27, py*die.EDGE*.27
                dot = [cube_point(centerx+math.cos(k*math.tau/10)*die.EDGE*.085,
                                  centery+math.sin(k*math.tau/10)*die.EDGE*.085,
                                  die.HALF+.00008) for k in range(10)]
                # Keep a face and all its pips in one stable paint group. Sorting
                # each pip by its own centre lets the parent face cover far pips
                # as the cube turns, incorrectly changing the apparent number.
                face(dot, (53, 33, 8, 255), paint_depth=face_depth)
    raised = 0.
    levels = 12
    rings = [ring(bowl.RADIUS*math.cos(j/levels*math.pi/2),
                  bowl.HEIGHT*math.sin(j/levels*math.pi/2)+raised) for j in range(levels+1)]
    for j in range(levels):
        for k in range(32):
            n = (k+1)%32
            face([bowl.world(p) for p in (rings[j][k],rings[j][n],rings[j+1][n],rings[j+1][k])],
                 (166,214,202,18), transparent=True)
    for z,radius,color,width in ((raised,.085,(225,248,237,220),1.2),
                                (raised+.002,.086,(168,207,194,185),.6)):
        rim = ring(radius,z)
        for k in range(32):
            face([bowl.world(rim[k]),bowl.world(rim[(k+1)%32])],None,color,width,True)
    for azimuth,color,width in ((-2.4,(242,255,249,220),1.2),(.55,(219,246,235,160),.8)):
        curve = []
        for k in range(22):
            a = .10+1.28*k/21
            curve.append(bowl.world((bowl.RADIUS*math.cos(a)*math.cos(azimuth),
                                     bowl.RADIUS*math.cos(a)*math.sin(azimuth),
                                     bowl.HEIGHT*math.sin(a)+raised+.0005)))
        for k in range(len(curve)-1):
            face(curve[k:k+2],None,color,width,True)
    return dish + sorted(solids,key=lambda f:f[0]), sorted(glass,key=lambda f:f[0])


def _gd_project(point, bowl):
    # The real bowl translation drives physics. Its screen travel is reduced to
    # fit the betting area, applied identically to glass, dish and dice.
    point = _gd_sub(point, _gd_scale(bowl.origin, .78))
    return (98+point[0]*680, 96+(point[1]*GD_VIEW_DEPTH-point[2]*GD_VIEW_UP)*680)


def _gd_render_bowl(bowl):
    """Antialiased image of the same geometry used by contact and scoring."""
    size, aa = (196, 138), 3
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



def load_user_data():
    try:
        with open(get_data_file_path(), 'r', encoding='utf-8') as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
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
# Baccarat rules / shoe / bet settlement
# -----------------------------------------------------------------------------
class BaccaratEngine:
    SUITS = ('Club', 'Diamond', 'Heart', 'Spade')
    RANKS = ('A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K')
    ALWAYS_MODES = ('always6', 'always7', 'always8', 'always9')
    SPECIAL_MODES = ('one_deck',) + ALWAYS_MODES
    SPECIAL_PREFIXES = {'one_deck': 'One_Deck', 'always6': 'Always6',
                        'always7': 'Always7', 'always8': 'Always8', 'always9': 'Always9'}
    ALWAYS_MAIN_PROFIT_ODDS = {
        'always6': {'Player': 1.02, 'Banker': .91, 'Tie': 8},
        'always7': {'Player': 1.18, 'Banker': .78, 'Tie': 8},
        'always8': {'Player': 1.48, 'Banker': .62, 'Tie': 9},
        'always9': {'Player': 1.65, 'Banker': .56, 'Tie': 9},
    }
    # Reuse the two Dragon spot keys for Always-mode-only side wagers.
    ALWAYS_SIDE_PROFIT_ODDS = {
        'always6': {'Dragon P': 7, 'Dragon B': 2.4},
        'always7': {'Dragon P': 5, 'Dragon B': 2.5},
        'always8': {'Dragon P': 3.5, 'Dragon B': 2.5},
        'always9': {'Dragon P': 3, 'Dragon B': 2.5},
    }
    ALWAYS_TIE_PROFIT_ODDS = {
        'always6': {0:235, 1:275, 2:295, 3:275, 4:165, 5:150, 6:18, 7:55, 8:105, 9:100},
        'always7': {0:250, 1:300, 2:310, 3:275, 4:165, 5:150, 6:60, 7:17, 8:108, 9:105},
        'always8': {0:250, 1:300, 2:310, 3:275, 4:165, 5:150, 6:62, 7:55, 8:30, 9:105},
        'always9': {0:250, 1:300, 2:310, 3:275, 4:165, 5:150, 6:60, 7:57, 8:110, 9:30},
    }
    BANKER_RULES = ('classic', 'no_commission', 'ez')
    FORCED_BANKER_RULES = {
        'classic': 'classic', 'goldendice': 'classic',
        'treasure': 'classic', 'xxx': 'classic', 'ez': 'ez',
    }
    DISALLOWED_BANKER_RULES = {'tiger': ('ez',), 'lucky7': ('ez',)}
    DEFAULT_BANKER_RULES = {
        'classic': 'classic', 'goldendice': 'classic',
        'treasure': 'classic', 'xxx': 'classic', 'ez': 'ez',
        'tiger': 'no_commission', 'lucky7': 'no_commission',
        'monkey': 'ez', '2to1': 'classic', 'one_deck': 'classic',
    }
    BANKER_RULE_ODDS_TEXT = {
        'classic': '0.95:1',
        'no_commission': '1:1 (6点赔半)',
        'ez': '1:1 (3张7点退水)',
    }

    MODE_NAMES = {
        'always6': '固定6 · Always 6', 'always7': '固定7 · Always 7',
        'always8': '固定8 · Always 8', 'always9': '固定9 · Always 9',
        'classic': '经典百家乐',
        'tiger': '老虎百家乐',
        'ez': 'EZ 五宝百家乐',
        '2to1': '1赔2百家乐',
        'lucky7': '幸运7百家乐',
        'monkey': '猴子百家乐',
        'goldendice': '黄金骰子',
        'treasure': '聚宝盆',
        'xxx': 'XXX',
        'one_deck': '单副版',
    }

    DISPLAY_NAMES = {
        **{f'Tie {point}': f'和局{point}点' for point in range(10)},
        'Player': '闲家',
        'Tie': '和局',
        'Banker': '庄家',
        'Pair Player': '闲家对子',
        'Pair Banker': '庄家对子',
        'Any Pair': '任意对子',
        'Dragon P': '闲家龙宝',
        'Dragon B': '庄家龙宝',
        'Perfect Pair': '完美对子',
        'Small': '小',
        'Big': '大',
        'Odd': '单',
        'Even': '双',
        '9/7': '9/7',
        '9/1': '9/1',
        'N9/N7': 'N9/N7',
        '8/6': '8/6',
        'Golden Hunter': '黄金猎手',
        'Golden Present': '有黄金扑克',
        'Golden Absent': '没黄金扑克',
        'Golden Count 4-5': '4-5张黄金扑克',
        'Golden Count 7-8': '7-8张黄金扑克',
        'Golden Duel': '黄金对决',
        'Super Dice': '超级骰子',
        'Dice Points': '骰子点数',
        'Small Tiger': '小老虎',
        'Tiger Tie': '老虎和',
        'Big Tiger': '大老虎',
        'Tiger': '老虎',
        'Tiger Pair': '虎对子',
        'Panda 8': '熊猫8点',
        'Divine 9': '神之9点',
        'Dragon 7': '金龙7点',
        'Fortune 7': '财运亨通7',
        'Golden 8': '金甲神将8',
        'Heavenly 9': '天上人间9',
        'Blazing 7s': '龙凤呈祥7',
        'Cover All': '五宝全包',
        'Small Lucky 6': '小幸运6',
        'Lucky 6': '幸运6',
        'Big Lucky 6': '大幸运6',
        'Lucky 7': '幸运7',
        'Super 7': '超级幸运7',
        'Monkey 6': '猴老六',
        'Monkey Tie': '猴老六和',
        'Big Monkey': '猴子六仙',
        'Monkey 7': '猴7点',
        'Lucky Monkey': '幸运猴子',
        'All Monkeys': '全猴',
        'No Monkeys': '无猴',
    }

    # XXX golden-card payout rule: once a winning wager is hit by a golden
    # card, its printed PROFIT odds are multiplied directly by the integer
    # multiplier shown on that card.  No hidden payout-side RTP scale is used.

    # XXX Golden Duel pays only the highest of four matching conditions and
    # is exempt from the normal XXX 50% fee.
    GOLDEN_DUEL_PROFIT_ODDS = {
        1: 15,       # both Player and Banker receive >=1 golden card
        2: 35,       # condition 1 + Tie result
        3: 100,      # at least one side has a golden Pair
        4: 3000,     # both sides have golden Pairs
    }
    GOLDEN_DUEL_TARGET_RTP = 0.95

    # V24 Super Dice is one six-tier side wager.  Tiers are mutually exclusive:
    # the highest matching row is paid once.  It is exempt from the Golden Dice
    # mode's usual 20% wager fee.
    SUPER_DICE_PROFIT_ODDS = {
        1: 2600,  # dice total 9 + both sides Pair + Tie
        2: 2100,  # dice total 8 + both sides Pair + Tie
        3: 325,   # dice total 9 + both sides Pair
        4: 260,   # dice total 8 + both sides Pair
        5: 11,    # dice total 9 + either side Pair (higher tiers excluded)
        6: 9,     # dice total 8 + either side Pair (higher tiers excluded)
    }
    SUPER_DICE_TARGET_RTP = 0.95

    # User-specified fixed PROFIT odds. Dice 10 -> 0, 11 -> 1; 12 always loses.
    DICE_POINTS_PROFIT_ODDS = {
        2: 44, 3: 30, 4: 16, 5: 12, 6: 6.2,
        7: 4.5, 8: 3.3, 9: 2.9, 10: 170, 11: 70,
    }

    # Copied from Baccarat_Special's single-deck exact-tie paytable.
    ONE_DECK_TIE_PROFIT_ODDS = {
        0: 180, 1: 230, 2: 245, 3: 210, 4: 130,
        5: 115, 6: 50, 7: 45, 8: 90, 9: 80,
    }

    ODDS_TEXT = {
        'one_deck': {
            **{f'Tie {point}': f'{odds}:1'
               for point, odds in ONE_DECK_TIE_PROFIT_ODDS.items()},
            'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
            'Pair Player': '15:1', 'Any Pair': '7:1', 'Pair Banker': '15:1',
            'Small': '1:2', 'Big': '1.6:1',
            'Player': '1:1', 'Tie': '9:1', 'Banker': '0.95:1',
        },
        'classic': {
            'Dragon P': '1–30:1', 'Perfect Pair': '25/250:1', 'Dragon B': '1–30:1',
            'Pair Player': '11:1', 'Any Pair': '5:1', 'Pair Banker': '11:1',
            'Small': '3:2', 'Big': '0.54:1', 'Odd': '1:1', 'Even': '1:1',
            'Player': '1:1', 'Tie': '8:1', 'Banker': '0.95:1',
        },
        'tiger': {
            'Small Tiger': '22:1', 'Tiger Tie': '35:1', 'Big Tiger': '50:1',
            'Tiger': '12/20:1', 'Tiger Pair': '4/20/100:1',
            'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
            'Player': '1:1', 'Tie': '8:1', 'Banker': '1:1*',
        },
        'ez': {
            'Fortune 7': '40:1', 'Golden 8': '25:1', 'Heavenly 9': '10/75:1',
            'Blazing 7s': '60/125:1', 'Cover All': '6:1', 'Pair Player': '11:1',
            'Pair Banker': '11:1', 'Player': '1:1', 'Tie': '8:1', 'Banker': '1:1*',
            'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
        },
        '2to1': {
            'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
            'Pair Player': '11:1', 'Any Pair': '5:1', 'Pair Banker': '11:1',
            'Small': '3:2', 'Big': '0.54:1',
            '9/7': '200:1', '9/1': '150:1', 'N9/N7': '50:1', '8/6': '25:1',
            'Player': '1:1', 'Tie': '8:1', 'Banker': '1:1*',
        },
        'lucky7': {
            'Small Lucky 6': '22:1', 'Lucky 6': '12/20:1', 'Big Lucky 6': '50:1',
            'Pair Player': '11:1', 'Lucky 7': '6/15:1', 'Super 7': '30/40/100:1#',
            'Pair Banker': '11:1', 'Player': '1:1', 'Tie': '8:1', 'Banker': '1:1*',
            'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
        },
        'monkey': {
            'Monkey 6': '12:1', 'Monkey Tie': '150:1', 'Big Monkey': '5000:1',
            'Pair Player': '11:1', 'Lucky Monkey': '1–75:1', 'Monkey 7': '40:1',
            'All Monkeys': '50:1', 'No Monkeys': '1:1',
            'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
            'Pair Banker': '11:1', 'Player': '1:1', 'Tie': '8:1', 'Banker': '1:1*',
        },
        'goldendice': {
            'Super Dice': '9–2600:1',
            'Dice Points': '2.9-170:1',
            'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
            'Pair Player': '10:1', 'Pair Banker': '10:1',
            'Player': '1:1', 'Tie': '5:1', 'Banker': '0.95:1',
        },
        'treasure': {
            'Golden Hunter': '3–51000:1',
            'Golden Present': '3:2', 'Golden Absent': '0.55:1',
            'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
            'Pair Player': '9:1', 'Pair Banker': '9:1',
            'Player': '1:1', 'Tie': '5:1', 'Banker': '0.95:1',
        },
        'xxx': {
            'Golden Duel': '15-3000:1',
            'Golden Count 4-5': '2.15:1', 'Golden Count 7-8': '5.25:1',
            'Dragon P': '1–30:1', 'Dragon B': '1–30:1',
            'Pair Player': '8:1', 'Pair Banker': '8:1',
            'Player': '1:1', 'Tie': '2.85:1', 'Banker': '0.95:1',
        },
    }

    MODE_ROWS = {
        'one_deck': (
            ('Dragon P',) + tuple(f'Tie {point}' for point in range(10)) + ('Dragon B',),
            ('Small', 'Any Pair', 'Big'),
            ('Pair Player', 'Player', 'Tie', 'Banker', 'Pair Banker'),
        ),
        'classic': (
            ('Dragon P', 'Small', 'Odd', 'Even', 'Big', 'Dragon B'),
            ('Any Pair', 'Perfect Pair'),
            ('Pair Player', 'Player', 'Tie', 'Banker', 'Pair Banker'),
        ),
        'tiger': (
            ('Dragon P', 'Tiger Pair', 'Tiger Tie', 'Dragon B'),
            ('Small Tiger', 'Tiger', 'Big Tiger'),
        ),
        'ez': (
            ('Dragon P', 'Fortune 7', 'Golden 8', 'Heavenly 9', 'Blazing 7s', 'Cover All', 'Dragon B'),
            ('Pair Player', 'Player', 'Tie', 'Banker', 'Pair Banker'),
        ),
        '2to1': (
            ('Dragon P', 'N9/N7', '9/7', '9/1', '8/6', 'Dragon B'),
            ('Small', 'Any Pair', 'Big'),
            ('Pair Player', 'Player', 'Tie', 'Banker', 'Pair Banker'),
        ),
        'lucky7': (
            ('Dragon P', 'Lucky 7', 'Super 7', 'Dragon B'),
            ('Small Lucky 6', 'Lucky 6', 'Big Lucky 6'),
        ),
        'monkey': (
            ('Dragon P', 'All Monkeys', 'Monkey 6', 'Monkey Tie', 'No Monkeys', 'Dragon B'),
            ('Monkey 7', 'Big Monkey', 'Lucky Monkey'),
            ('Pair Player', 'Player', 'Tie', 'Banker', 'Pair Banker'),
        ),
        'goldendice': (
            ('Dragon P', 'Super Dice', 'Dice Points', 'Dragon B'),
            ('Pair Player', 'Player', 'Tie', 'Banker', 'Pair Banker'),
        ),
        'treasure': (
            ('Dragon P', 'Golden Hunter', 'Golden Present', 'Golden Absent', 'Dragon B'),
            ('Pair Player', 'Player', 'Tie', 'Banker', 'Pair Banker'),
        ),
        'xxx': (
            ('Dragon P', 'Golden Duel', 'Golden Count 4-5', 'Golden Count 7-8', 'Dragon B'),
            ('Pair Player', 'Player', 'Tie', 'Banker', 'Pair Banker'),
        ),
    }

    def __init__(self, decks=8):
        self.decks = int(decks)
        self.deck = []
        self.current_index = 0
        self.cut_threshold = random.SystemRandom().randint(50, 70)
        self.shuffle_count = 0
        self.new_shoe()

    def new_shoe(self, deck=None):
        if deck is None:
            deck = [
                (suit, rank)
                for _ in range(self.decks)
                for suit in self.SUITS
                for rank in self.RANKS
            ]
            random.SystemRandom().shuffle(deck)
        self.deck = [tuple(card) for card in deck]
        self.current_index = 0
        self.cut_threshold = random.SystemRandom().randint(50, 70)
        self.shuffle_count += 1

    def set_shoe_state(self, deck, current_index=0, cut_threshold=None):
        self.deck = [tuple(card) for card in deck]
        self.current_index = max(0, min(int(current_index), len(self.deck)))
        if cut_threshold is None:
            cut_threshold = random.SystemRandom().randint(50, 70)
        self.cut_threshold = max(50, min(80, int(cut_threshold)))

    def cut_shoe(self, cut_position, cut_threshold=None):
        if not self.deck:
            self.new_shoe()
        cut_position = max(0, min(int(cut_position), len(self.deck) - 1))
        self.deck = self.deck[cut_position:] + self.deck[:cut_position]
        self.current_index = 0
        self.cut_threshold = (random.SystemRandom().randint(50, 70)
                              if cut_threshold is None
                              else max(50, min(80, int(cut_threshold))))

    def remaining_cards(self):
        return max(0, len(self.deck) - self.current_index)

    def needs_shuffle(self):
        return self.remaining_cards() <= self.cut_threshold

    @staticmethod
    def card_value(card):
        rank = card[1]
        if rank == 'A':
            return 1
        if rank in ('10', 'J', 'Q', 'K'):
            return 0
        return int(rank)

    @classmethod
    def score(cls, hand):
        return sum(cls.card_value(card) for card in hand) % 10

    def draw_card(self):
        if self.current_index >= len(self.deck):
            raise RuntimeError('牌靴已用完，请重新切牌。')
        card = self.deck[self.current_index]
        self.current_index += 1
        return card

    def deal_round(self):
        if self.remaining_cards() < 6:
            raise RuntimeError('剩余牌不足，请重新切牌。')
        reshuffled = False

        player = [self.draw_card()]
        banker = [self.draw_card()]
        player.append(self.draw_card())
        banker.append(self.draw_card())

        p_initial = self.score(player)
        b_initial = self.score(banker)
        natural = p_initial >= 8 or b_initial >= 8

        player_third = None
        if not natural and p_initial <= 5:
            player_third = self.draw_card()
            player.append(player_third)

        if not natural:
            b_score = self.score(banker[:2])
            if player_third is None:
                if b_score <= 5:
                    banker.append(self.draw_card())
            else:
                third = self.card_value(player_third)
                draw = (
                    b_score <= 2
                    or (b_score == 3 and third != 8)
                    or (b_score == 4 and 2 <= third <= 7)
                    or (b_score == 5 and 4 <= third <= 7)
                    or (b_score == 6 and 6 <= third <= 7)
                )
                if draw:
                    banker.append(self.draw_card())

        p_score = self.score(player)
        b_score = self.score(banker)
        if p_score > b_score:
            winner = 'Player'
        elif b_score > p_score:
            winner = 'Banker'
        else:
            winner = 'Tie'

        return {
            'player_hand': player,
            'banker_hand': banker,
            'player_score': p_score,
            'banker_score': b_score,
            'winner': winner,
            'natural': natural,
            'reshuffled': reshuffled,
            'shoe_remaining': self.remaining_cards(),
        }

    @classmethod
    def display_name(cls, bet_type, mode=None):
        if mode in cls.ALWAYS_MODES:
            if bet_type == 'Dragon P':
                return f'庄家以{mode[-1]}点获胜'
            if bet_type == 'Dragon B':
                return '庄家需要补第三张'
        return cls.DISPLAY_NAMES.get(bet_type, bet_type)

    @staticmethod
    def _pair_flags(result):
        p = result['player_hand']
        b = result['banker_hand']
        return p[0][1] == p[1][1], b[0][1] == b[1][1]

    @classmethod
    def side_return_factors(cls, result, mode, current_bets=None):
        """Return winning side-bet total-return multipliers.

        A value of 12 means 11:1 profit plus original stake. A value of 1 is a
        push. This mirrors the payout behaviour of the supplied Baccarat.py.
        """
        factors = {}
        p = result['player_hand']
        b = result['banker_hand']
        winner = result['winner']
        ps = result['player_score']
        bs = result['banker_score']
        player_pair, banker_pair = cls._pair_flags(result)

        if mode == 'tiger':
            if player_pair ^ banker_pair:
                factors['Tiger Pair'] = 5
            elif player_pair and banker_pair and p[0][1] != b[0][1]:
                factors['Tiger Pair'] = 21
            elif player_pair and banker_pair and p[0][1] == b[0][1]:
                factors['Tiger Pair'] = 101

            if winner == 'Banker' and bs == 6:
                factors['Tiger'] = 13 if len(b) == 2 else 21
                if len(b) == 2:
                    factors['Small Tiger'] = 23
                else:
                    factors['Big Tiger'] = 51
            if winner == 'Tie' and bs == 6:
                factors['Tiger Tie'] = 36
            cls._add_dragon_factors(factors, result)

        elif mode == 'ez':
            # Five Treasures, photo paytable: Blazing 7s = 60/125:1.
            # Multipliers below include the returned stake. Cover All pays
            # once for any qualifying treasure, whether or not it was bet.
            if winner == 'Banker' and len(b) == 3 and bs == 7:
                factors['Fortune 7'] = 41
            if winner == 'Player' and len(p) == 3 and ps == 8:
                factors['Golden 8'] = 26
            player_nine = len(p) == 3 and ps == 9
            banker_nine = len(b) == 3 and bs == 9
            if player_nine and banker_nine:
                factors['Heavenly 9'] = 76
            elif player_nine or banker_nine:
                factors['Heavenly 9'] = 11
            if ps == 7 and bs == 7 and len(p) == len(b):
                if len(p) == 3:
                    factors['Blazing 7s'] = 126
                elif len(p) == 2:
                    factors['Blazing 7s'] = 61
            if factors:
                factors['Cover All'] = 7
            # Pairs are independent of the five treasures; a pair alone
            # must never trigger Cover All.
            if player_pair:
                factors['Pair Player'] = 12
            if banker_pair:
                factors['Pair Banker'] = 12
            # Dragon Bonus is separate from Five Treasures and never
            # qualifies Cover All, including a natural-tie refund.
            cls._add_dragon_factors(factors, result)

        elif mode == 'monkey':
            monkey_ranks = {'J', 'Q', 'K'}
            # These wagers inspect only the four opening cards; third cards
            # do not change either outcome. Mixed openings lose both bets.
            opening_cards = p[:2] + b[:2]
            if len(opening_cards) == 4:
                if all(card[1] in monkey_ranks for card in opening_cards):
                    factors['All Monkeys'] = 51
                elif all(card[1] not in monkey_ranks for card in opening_cards):
                    factors['No Monkeys'] = 2
            pt = p[2] if len(p) >= 3 else None
            bt = b[2] if len(b) >= 3 else None
            if pt and bt and pt[1] not in monkey_ranks and bt[1] in monkey_ranks:
                factors['Monkey 6'] = 13
                if winner == 'Tie':
                    factors['Monkey Tie'] = 151
            if len(p) == 3 and len(b) == 3 and all(card[1] in monkey_ranks for card in p + b):
                factors['Big Monkey'] = 5001
            if len(b) == 3 and bs == 7 and winner == 'Banker':
                factors['Monkey 7'] = 41

            player_monkey = bool(pt and pt[1] in monkey_ranks)
            banker_monkey = bool(bt and bt[1] in monkey_ranks)
            if pt and bt:
                if player_monkey and banker_monkey and pt == bt:
                    factors['Lucky Monkey'] = 76
                elif player_monkey and banker_monkey and pt[1] == bt[1]:
                    factors['Lucky Monkey'] = 26
                elif player_monkey and banker_monkey:
                    factors['Lucky Monkey'] = 11
                elif player_monkey ^ banker_monkey:
                    factors['Lucky Monkey'] = 2
            elif pt and player_monkey:
                factors['Lucky Monkey'] = 4
            elif bt and banker_monkey:
                factors['Lucky Monkey'] = 9

            if player_pair:
                factors['Pair Player'] = 12
            if banker_pair:
                factors['Pair Banker'] = 12
            cls._add_dragon_factors(factors, result)

        elif mode in cls.ALWAYS_MODES:
            if player_pair:
                factors['Pair Player'] = 12
            if banker_pair:
                factors['Pair Banker'] = 11
            if player_pair or banker_pair:
                factors['Any Pair'] = 6.5
            total_cards = len(p) + len(b)
            if total_cards == 4:
                factors['Small'] = 2.5 if mode in ('always6', 'always7') else 1.8
            elif total_cards in (5, 6):
                factors['Big'] = 1.55 if mode in ('always6', 'always7') else 2.1
            if winner == 'Tie' and ps in cls.ALWAYS_TIE_PROFIT_ODDS[mode]:
                factors[f'Tie {ps}'] = cls.ALWAYS_TIE_PROFIT_ODDS[mode][ps] + 1
            # The two replacement wagers are independent: a third-card draw
            # wins even if Banker loses or ties, and may win alongside X points.
            side_odds = cls.ALWAYS_SIDE_PROFIT_ODDS[mode]
            if winner == 'Banker' and bs == int(mode[-1]):
                factors['Dragon P'] = side_odds['Dragon P'] + 1
            if len(b) == 3:
                factors['Dragon B'] = side_odds['Dragon B'] + 1

        elif mode == 'one_deck':
            if player_pair:
                factors['Pair Player'] = 16
            if banker_pair:
                factors['Pair Banker'] = 16
            if player_pair or banker_pair:
                factors['Any Pair'] = 8
            total_cards = len(p) + len(b)
            if total_cards in (4, 5):
                factors['Small'] = 1.5  # Stake 2 returns 3: profit 1.
            elif total_cards == 6:
                factors['Big'] = 2.6
            if winner == 'Tie' and ps in cls.ONE_DECK_TIE_PROFIT_ODDS:
                factors[f'Tie {ps}'] = cls.ONE_DECK_TIE_PROFIT_ODDS[ps] + 1
            cls._add_dragon_factors(factors, result)

        elif mode in ('classic', '2to1'):
            if player_pair:
                factors['Pair Player'] = 12
            if banker_pair:
                factors['Pair Banker'] = 12
            if player_pair or banker_pair:
                factors['Any Pair'] = 6
            cls._add_dragon_factors(factors, result)
            total_cards = len(p) + len(b)
            if total_cards == 4:
                factors['Small'] = 2.5  # 3:2 profit plus stake.
            elif total_cards in (5, 6):
                factors['Big'] = 1.54
            if mode == 'classic':
                # Perfect Pair is retained only in Classic.
                player_perfect = len(p) >= 2 and p[0] == p[1]
                banker_perfect = len(b) >= 2 and b[0] == b[1]
                if player_perfect and banker_perfect:
                    factors['Perfect Pair'] = 251
                elif player_perfect or banker_perfect:
                    factors['Perfect Pair'] = 26
                # Add the two final scores, then keep only the units digit.
                # Both 0+0 and sums of 10 lose BOTH parity wagers.
                points_sum = (ps + bs) % 10
                if points_sum > 0:
                    factors['Odd' if points_sum % 2 else 'Even'] = 2
            else:
                # 1-pays-2 copies Classic's size wagers, but replaces parity
                # and Perfect Pair with four direction-independent score bets.
                scores = {ps, bs}
                if len(p) == len(b) == 3:
                    if scores == {9, 7}:
                        factors['9/7'] = 201
                    elif scores == {9, 1}:
                        factors['9/1'] = 151
                if len(p) == len(b) == 2 and scores == {9, 7}:
                    factors['N9/N7'] = 51
                if scores == {8, 6}:
                    factors['8/6'] = 26

        elif mode == 'goldendice':
            cls._add_dragon_factors(factors, result)
            # Golden Dice pairs use 10:1 base profit odds.  Their profit odds are
            # later multiplied only when the two dice total 8 or 9.
            if player_pair:
                factors['Pair Player'] = 11
            if banker_pair:
                factors['Pair Banker'] = 11
            tier = cls.super_dice_tier(result)
            profit_odds = cls.SUPER_DICE_PROFIT_ODDS.get(tier)
            if profit_odds is not None:
                factors['Super Dice'] = float(profit_odds) + 1.0
            dice_total = int(result.get('_golden_dice_total', 0))
            if (dice_total in cls.DICE_POINTS_PROFIT_ODDS
                    and max(ps, bs) == dice_total % 10):
                factors['Dice Points'] = cls.DICE_POINTS_PROFIT_ODDS[dice_total] + 1.0

        elif mode in ('treasure', 'xxx'):
            # Treasure and XXX share the golden-card multiplier engine but keep
            # different dedicated side bets and pair prices.
            pair_factor = 10 if mode == 'treasure' else 9
            if player_pair:
                factors['Pair Player'] = pair_factor
            if banker_pair:
                factors['Pair Banker'] = pair_factor
            cls._add_dragon_factors(factors, result)

            if mode == 'treasure':
                # Presence includes every actually dealt card on either side,
                # including third cards; only the selected suit+rank matches.
                golden_count = cls.golden_hit_count(result)
                factors['Golden Present' if golden_count else 'Golden Absent'] = (
                    2.5 if golden_count else 1.55)
                hunter_profit_odds = {2: 3, 3: 25, 4: 155, 5: 3150, 6: 51000}
                if golden_count in hunter_profit_odds:
                    factors['Golden Hunter'] = hunter_profit_odds[golden_count] + 1
            else:
                # Count the system's selected DISTINCT faces, not dealt hits.
                selected_count = cls.golden_selection_count(result)
                if selected_count in (4, 5):
                    factors['Golden Count 4-5'] = 3.15
                elif selected_count in (7, 8):
                    factors['Golden Count 7-8'] = 6.25
                # XXX-only four-tier Golden Duel. Exactly one (highest) tier is
                # paid per round, so overlapping conditions never stack.
                tier = cls.golden_duel_tier(result)
                profit_odds = cls.GOLDEN_DUEL_PROFIT_ODDS.get(tier)
                if profit_odds is not None:
                    factors['Golden Duel'] = float(profit_odds) + 1.0

        elif mode == 'lucky7':
            if winner == 'Banker' and bs == 6:
                if len(b) == 2:
                    factors['Small Lucky 6'] = 23
                    factors['Lucky 6'] = 13
                else:
                    factors['Big Lucky 6'] = 51
                    factors['Lucky 6'] = 21
            if player_pair:
                factors['Pair Player'] = 12
            if banker_pair:
                factors['Pair Banker'] = 12
            if winner == 'Player' and ps == 7:
                factors['Lucky 7'] = 7 if len(p) == 2 else 16
            if ps == 7 and bs == 6:
                total_cards = len(p) + len(b)
                factors['Super 7'] = {4: 31, 5: 41, 6: 101}.get(total_cards, 0)
            cls._add_dragon_factors(factors, result)

        return {key: factor for key, factor in factors.items() if factor > 0}

    @classmethod
    def _add_dragon_factors(cls, factors, result):
        p = result['player_hand']
        b = result['banker_hand']
        ps = result['player_score']
        bs = result['banker_score']
        winner = result['winner']
        total_cards = len(p) + len(b)
        factor_map = {4: 2, 5: 3, 6: 5, 7: 7, 8: 11, 9: 31}

        if winner == 'Tie' and total_cards == 4 and ps in (8, 9):
            factors['Dragon P'] = 1
            factors['Dragon B'] = 1
            return

        if winner == 'Player':
            if total_cards == 4 and ps in (8, 9):
                factors['Dragon P'] = 2
            elif total_cards != 4:
                factors['Dragon P'] = factor_map.get(ps - bs, 0)
        elif winner == 'Banker':
            if total_cards == 4 and bs in (8, 9):
                factors['Dragon B'] = 2
            elif total_cards != 4:
                factors['Dragon B'] = factor_map.get(bs - ps, 0)

    @staticmethod
    def _golden_map(result):
        mapping = result.get('_golden_multiplier_map', {}) if isinstance(result, dict) else {}
        if isinstance(mapping, dict):
            return mapping
        return {}

    @classmethod
    def golden_hit_count(cls, result):
        mapping = cls._golden_map(result)
        if not mapping:
            return 0
        cards = list(result.get('player_hand', [])) + list(result.get('banker_hand', []))
        return sum(1 for card in cards if tuple(card) in mapping)

    @classmethod
    def golden_selection_count(cls, result):
        mapping = cls._golden_map(result)
        if mapping:
            return len(mapping)
        try:
            return int(result.get('golden_selection_count', 0))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def golden_duel_tier(cls, result):
        """Return the highest winning XXX Golden Duel tier (0..4).

        A golden Pair means the normal baccarat Pair condition is met and both
        of that side's first two cards are golden.
        """
        mapping = cls._golden_map(result)
        if not mapping:
            return 0
        p = list(result.get('player_hand', []))
        b = list(result.get('banker_hand', []))

        def golden_pair(hand):
            return (len(hand) >= 2
                    and hand[0][1] == hand[1][1]
                    and tuple(hand[0]) in mapping
                    and tuple(hand[1]) in mapping)

        player_golden_pair = golden_pair(p)
        banker_golden_pair = golden_pair(b)
        if player_golden_pair and banker_golden_pair:
            return 4
        if player_golden_pair or banker_golden_pair:
            return 3

        player_has_gold = any(tuple(card) in mapping for card in p)
        banker_has_gold = any(tuple(card) in mapping for card in b)
        if player_has_gold and banker_has_gold:
            if result.get('winner') == 'Tie':
                return 2
            return 1
        return 0

    @classmethod
    def super_dice_tier(cls, result):
        """Return the highest payable Golden Dice / Super Dice tier (0..6)."""
        try:
            dice_total = int(result.get('_golden_dice_total', 0))
        except (TypeError, ValueError, AttributeError):
            return 0
        if dice_total not in (8, 9):
            return 0
        player_pair, banker_pair = cls._pair_flags(result)
        both_pair = player_pair and banker_pair
        any_pair = player_pair or banker_pair
        is_tie = result.get('winner') == 'Tie'
        if dice_total == 9 and both_pair and is_tie:
            return 1
        if dice_total == 8 and both_pair and is_tie:
            return 2
        if dice_total == 9 and both_pair:
            return 3
        if dice_total == 8 and both_pair:
            return 4
        if dice_total == 9 and any_pair:
            return 5
        if dice_total == 8 and any_pair:
            return 6
        return 0

    @classmethod
    def golden_multiplier_for_cards(cls, cards, result):
        mapping = cls._golden_map(result)
        multiplier = 1
        for card in cards:
            multiplier *= int(mapping.get(tuple(card), 1))
        return max(1, int(multiplier))

    @classmethod
    def golden_multiplier_for_bet(cls, bet_type, result):
        if not cls._golden_map(result):
            return 1
        p = list(result.get('player_hand', []))
        b = list(result.get('banker_hand', []))
        if bet_type == 'Player':
            return cls.golden_multiplier_for_cards(p, result)
        if bet_type == 'Banker':
            return cls.golden_multiplier_for_cards(b, result)
        if bet_type == 'Tie':
            return cls.golden_multiplier_for_cards(p + b, result)
        if bet_type == 'Pair Player':
            return cls.golden_multiplier_for_cards(p[:2], result)
        if bet_type == 'Pair Banker':
            return cls.golden_multiplier_for_cards(b[:2], result)
        return 1

    @classmethod
    def banker_rules_for_mode(cls, mode):
        forced = cls.FORCED_BANKER_RULES.get(mode)
        if forced is not None:
            return (forced,)
        excluded = cls.DISALLOWED_BANKER_RULES.get(mode, ())
        return tuple(rule for rule in cls.BANKER_RULES if rule not in excluded)

    @classmethod
    def banker_rule_for_mode(cls, mode, preferred=None):
        allowed = cls.banker_rules_for_mode(mode)
        if preferred in allowed:
            return preferred
        default = cls.DEFAULT_BANKER_RULES.get(mode, 'no_commission')
        return default if default in allowed else allowed[0]

    @staticmethod
    def banker_profit_odds(rule, result=None):
        """Base Banker profit, before any mode-specific golden multiplier."""
        if rule == 'classic':
            return 0.95
        if result is not None and result.get('winner') == 'Banker':
            if rule == 'no_commission' and result['banker_score'] == 6:
                return 0.5
            if rule == 'ez' and len(result['banker_hand']) == 3 and result['banker_score'] == 7:
                return 0.0
        return 1.0

    @classmethod
    def main_return_factor(cls, bet_type, result, mode):
        winner = result['winner']
        if mode in cls.ALWAYS_MODES:
            if bet_type not in ('Player', 'Banker', 'Tie'):
                return 0.0
            if winner == 'Tie' and bet_type in ('Player', 'Banker'):
                return 1.0
            return (1.0 + cls.ALWAYS_MAIN_PROFIT_ODDS[mode][bet_type]
                    if winner == bet_type else 0.0)

        if bet_type == 'Tie':
            if winner != 'Tie':
                return 0.0
            if mode in ('treasure', 'goldendice'):
                return 6.0
            if mode == 'xxx':
                return 3.85
            if mode == 'one_deck':
                return 10.0
            return 9.0

        if bet_type in ('Player', 'Banker'):
            if winner == 'Tie':
                return 0.0 if mode == '2to1' else 1.0
            if winner != bet_type:
                return 0.0

        if bet_type == 'Banker':
            rule = cls.banker_rule_for_mode(mode, result.get('_banker_rule'))
            profit = cls.banker_profit_odds(rule, result)
            # Keep 1-pays-2's natural-card bonus, applied to the selected base price.
            if mode == '2to1' and len(result['banker_hand']) == 2 and result['banker_score'] in (8, 9):
                profit *= 2
            return 1.0 + profit

        if mode == '2to1' and bet_type == 'Player':
            hand = result['player_hand']
            # Only a winning two-card natural earns 2:1 profit (3x with stake).
            return 3.0 if len(hand) == 2 and cls.score(hand) in (8, 9) else 2.0

        if bet_type == 'Player':
            return 2.0

        return 0.0

    @classmethod
    def resolve_bets(cls, bets, result, mode, jackpot_amount=0.0):
        side_factors = cls.side_return_factors(result, mode, bets)
        outcomes = []
        credit = 0.0
        gross_profit = 0.0
        lost_stake = 0.0

        for bet_type, stake in bets.items():
            stake = float(stake)
            if stake <= 0:
                continue
            if bet_type in ('Player', 'Tie', 'Banker'):
                factor = cls.main_return_factor(bet_type, result, mode)
            else:
                factor = float(side_factors.get(bet_type, 0.0))

            # Only these five wagers receive golden-card multipliers. Presence,
            # absence, Hunter/Duel and Dragon wagers retain their fixed odds.
            if (mode in ('treasure', 'xxx') and bet_type in
                    ('Player', 'Banker', 'Tie', 'Pair Player', 'Pair Banker')
                    and factor > 1.0):
                gold_mult = cls.golden_multiplier_for_bet(bet_type, result)
                # Multiply the wager's PROFIT odds directly by the golden-card
                # multiplier.  Example in XXX: Player 1:1 hit by 4X -> 4.00:1.
                # Banker starts from the selected rule; longer decimals are rounded
                # to two decimal places with ROUND_HALF_UP before settlement.
                amplified_profit_odds = (factor - 1.0) * float(gold_mult)
                factor = 1.0 + round_two_decimals_value(amplified_profit_odds)

            # Golden Dice uses one pre-drawn multiplier per normal wager type.
            # It activates only when the two golden dice total 8 or 9.  The
            # multiplier applies to PROFIT odds, never to the original stake.
            if (mode == 'goldendice' and bet_type in
                    ('Player', 'Banker', 'Tie', 'Pair Player', 'Pair Banker')
                    and factor > 1.0 and bool(result.get('_golden_dice_active'))):
                multipliers = result.get('_golden_dice_multipliers', {})
                try:
                    dice_mult = int(multipliers.get(bet_type, 1))
                except (TypeError, ValueError, AttributeError):
                    dice_mult = 1
                amplified_profit_odds = (factor - 1.0) * max(1, dice_mult)
                factor = 1.0 + round_two_decimals_value(amplified_profit_odds)

            returned = stake * factor
            if factor > 1.0:
                status = 'win'
                profit = returned - stake
                gross_profit += profit
            elif abs(factor - 1.0) < 1e-9:
                status = 'push'
                profit = 0.0
            else:
                status = 'lose'
                profit = 0.0
                lost_stake += stake

            credit += returned
            outcomes.append({
                'key': (bet_type, None),
                'label': cls.display_name(bet_type, mode),
                'status': status,
                'stake': stake,
                'return_factor': factor,
                'profit': profit,
                'return_amount': returned,
            })

        jackpot_win = 0.0
        if mode == 'lucky7' and 'Super 7' in side_factors:
            super_bet = float(bets.get('Super 7', 0.0))
            if super_bet >= 1000:
                p = result['player_hand']
                b = result['banker_hand']
                if (len(p) == 3 and result['player_score'] == 7
                        and all(card[0] == 'Diamond' for card in p)
                        and len(b) == 3 and result['banker_score'] == 6
                        and all(card[0] == 'Spade' for card in b)):
                    jackpot_win = float(jackpot_amount)
                elif (len(p) == 3 and result['player_score'] == 7
                      and all(card[0] in ('Diamond', 'Heart') for card in p)
                      and len(b) == 3 and result['banker_score'] == 6
                      and all(card[0] in ('Spade', 'Club') for card in b)):
                    jackpot_win = float(jackpot_amount) * 0.03

        credit += jackpot_win
        gross_profit += jackpot_win
        return {
            'credit': credit,
            'gross_profit': gross_profit,
            'lost_stake': lost_stake,
            'net': gross_profit - lost_stake,
            'outcomes': outcomes,
            'side_factors': side_factors,
            'jackpot_win': jackpot_win,
        }


# Fixed-mode prices come from Baccarat_Special, with the requested size/pair overrides.
for _always_mode in BaccaratEngine.ALWAYS_MODES:
    BaccaratEngine.FORCED_BANKER_RULES[_always_mode] = 'classic'
    BaccaratEngine.DEFAULT_BANKER_RULES[_always_mode] = 'classic'
    BaccaratEngine.ODDS_TEXT[_always_mode] = {
        **{f'Tie {point}': f'{price}:1' for point, price in
           BaccaratEngine.ALWAYS_TIE_PROFIT_ODDS[_always_mode].items()},
        **{bet: f'{format_two_decimals(price)}:1' for bet, price in
           BaccaratEngine.ALWAYS_MAIN_PROFIT_ODDS[_always_mode].items()},
        **{bet: f'{price:g}:1' for bet, price in
           BaccaratEngine.ALWAYS_SIDE_PROFIT_ODDS[_always_mode].items()},
        'Pair Player': '11:1', 'Pair Banker': '10:1', 'Any Pair': '5.5:1',
        'Small': '3:2' if _always_mode in ('always6', 'always7') else '0.8:1',
        'Big': '0.55:1' if _always_mode in ('always6', 'always7') else '1.1:1',
    }
    BaccaratEngine.MODE_ROWS[_always_mode] = BaccaratEngine.MODE_ROWS['one_deck']
del _always_mode


class AlwaysBaccaratEngine(BaccaratEngine):
    """Special's CSM lease/draw/recycle flow, independent of the 8-deck shoe."""

    VALID_MODES = CSM_MODES = BaccaratEngine.ALWAYS_MODES

    def __init__(self, mode='always6', csm_factory=None):
        self.mode = mode if mode in self.CSM_MODES else 'always6'
        self.csm = None
        self._csm_factory = csm_factory
        self.game_id = 'BACCARAT-ALWAYS-' + secrets.token_hex(12)
        self._batches = []
        self._active_round_id = None
        self._used_by_batch = {}
        # These empty fields retain compatibility with Special's release routine.
        self._one_deck_cards = []
        self._one_deck_index = 0
        self._one_deck_round_active = False

    @staticmethod
    def _load_csm_factory():
        current = os.path.dirname(os.path.abspath(__file__))
        candidates = [os.path.abspath(path) for path in (
            os.path.join(current, '..', 'A_Tools', 'Card'),
            os.path.join(current, '..', 'Card'),
            os.path.join(current, 'A_Tools', 'Card'), current)]
        directory = next((p for p in candidates if os.path.isfile(
            os.path.join(p, 'CSM_Shuffler.py'))), None)
        if directory is None:
            raise ModuleNotFoundError('找不到固定牌模式所需的 CSM_Shuffler.py，已检查：' + '; '.join(candidates))
        if directory not in sys.path:
            sys.path.insert(0, directory)
        # Use the canonical project module, sharing its warehouse semantics.
        return importlib.import_module('CSM_Shuffler').ContinuousShuffleMachine

    def _ensure_csm(self):
        if self.csm is None:
            factory = self._csm_factory or self._load_csm_factory()
            self.csm = factory()
        return self.csm

    def needs_shuffle(self):
        return False

    def prepare_mode(self, mode):
        self.set_mode(mode)
        self.fresh_lease()

    def deal_round(self):
        try:
            return self._deal_csm_round()
        except Exception:
            # A failed partial draw must release its lease before a retry.
            try:
                self.release_all_cards(force_shuffle=False)
            except Exception:
                pass
            raise

    def set_mode(self, mode):
        if mode not in self.VALID_MODES:
            raise ValueError('Unsupported special baccarat mode')
        self.mode = mode
        if mode in self.CSM_MODES:
            self._ensure_csm()

    def _clear_local_csm_state(self):
        self._batches = []
        self._active_round_id = None
        self._used_by_batch = {}

    def _request_fresh_cards(self):
        if self.mode == 'one_deck':
            self._one_deck_cards = []
            self._one_deck_index = 0
            self._one_deck_round_active = False
            return
        csm = self._ensure_csm()
        self.release_all_cards(force_shuffle=False)
        rid = None
        try:
            rid = csm.begin_round(self.game_id)
            packet = csm.acquire_chamber(self.game_id, rid)
            self._batches = [self._packet_to_local(packet)]
            csm.end_round(self.game_id, rid)
        except Exception:
            try:
                csm.release_game(self.game_id, force_shuffle=False)
            except Exception:
                pass
            self._clear_local_csm_state()
            raise

    @staticmethod
    def _packet_to_local(packet):
        return {
            'batch_id': packet['batch_id'],
            'warehouse_id': packet['warehouse_id'],
            'cards': list(packet.get('cards', [])),
            'index': 0,
        }

    def fresh_lease(self):
        if self.mode in self.CSM_MODES:
            self._request_fresh_cards()
        else:
            # 单副版在每局真正开始时才调用 shuffle.py，确保每局都是全新一副牌。
            self._one_deck_cards = []
            self._one_deck_index = 0
            self._one_deck_round_active = False

    def release_all_cards(self, force_shuffle=False):
        if self.csm is not None:
            try:
                self.csm.release_game(self.game_id, force_shuffle=force_shuffle)
            except Exception:
                if self._batches:
                    raise
            finally:
                self._clear_local_csm_state()
        else:
            self._clear_local_csm_state()
        self._one_deck_cards = []
        self._one_deck_index = 0
        self._one_deck_round_active = False

    def remaining_cards(self):
        if self.mode == 'one_deck':
            return max(0, len(self._one_deck_cards) - self._one_deck_index)
        return sum(max(0, len(b['cards']) - b['index']) for b in self._batches)

    def _acquire_extra_batch(self):
        if not self._active_round_id:
            raise RuntimeError('No active CSM round')
        packet = self.csm.acquire_chamber(self.game_id, self._active_round_id)
        self._batches.append(self._packet_to_local(packet))

    def _prefetch_at_six(self):
        if not self._batches:
            self._acquire_extra_batch()
            return
        current = self._batches[0]
        remaining = max(0, len(current['cards']) - current['index'])
        if remaining <= 6 and len(self._batches) < 2:
            self._acquire_extra_batch()

    def draw_card(self):
        if self.mode == 'one_deck':
            return self._draw_one_deck_card()
        if not self._active_round_id:
            raise RuntimeError('No active CSM round')
        self._prefetch_at_six()
        while self._batches and self._batches[0]['index'] >= len(self._batches[0]['cards']):
            self._batches.pop(0)
        if not self._batches:
            self._acquire_extra_batch()
        batch = self._batches[0]
        item = batch['cards'][batch['index']]
        batch['index'] += 1
        self._used_by_batch.setdefault(batch['batch_id'], []).append(item['card_id'])
        return (item['suit'], item['rank'])

    def _fixed_banker_card(self):
        if self.mode not in self.CSM_MODES:
            raise RuntimeError('单副版没有固定庄家首张牌。')
        rank = {
            'always6': '6',
            'always7': '7',
            'always8': '8',
            'always9': '9',
        }[self.mode]
        return ('Spade', rank)

    def _complete_baccarat_draws(self, player, banker):
        p_initial = self.score(player)
        b_initial = self.score(banker)
        natural = p_initial >= 8 or b_initial >= 8

        player_third = None
        if not natural and p_initial <= 5:
            player_third = self.draw_card()
            player.append(player_third)

        if not natural:
            b_score = self.score(banker[:2])
            if player_third is None:
                if b_score <= 5:
                    banker.append(self.draw_card())
            else:
                third = self.card_value(player_third)
                draw = (
                    b_score <= 2
                    or (b_score == 3 and third != 8)
                    or (b_score == 4 and 2 <= third <= 7)
                    or (b_score == 5 and 4 <= third <= 7)
                    or (b_score == 6 and 6 <= third <= 7)
                )
                if draw:
                    banker.append(self.draw_card())

        p_score = self.score(player)
        b_score = self.score(banker)
        winner = 'Player' if p_score > b_score else ('Banker' if b_score > p_score else 'Tie')
        return p_score, b_score, winner, natural

    def _deal_csm_round(self):
        if self._active_round_id is not None:
            raise RuntimeError('上一局尚未完成。')
        csm = self._ensure_csm()
        buffered = self._batches[0]['batch_id'] if self._batches else None
        self._active_round_id = csm.begin_round(self.game_id, buffered_batch=buffered)
        self._used_by_batch = {}
        if not self._batches:
            self._acquire_extra_batch()
        self._prefetch_at_six()

        # 永6/永7/永8/永9保留特殊规则：庄家首张固定，其他牌来自CSM。
        player = [self.draw_card()]
        banker = [self._fixed_banker_card()]
        player.append(self.draw_card())
        banker.append(self.draw_card())
        p_score, b_score, winner, natural = self._complete_baccarat_draws(player, banker)
        self._prefetch_at_six()
        return {
            'player_hand': player, 'banker_hand': banker,
            'player_score': p_score, 'banker_score': b_score,
            'winner': winner, 'natural': natural, 'reshuffled': False,
            'shoe_remaining': self.remaining_cards(),
        }

    def finish_round(self):
        if self.mode == 'one_deck':
            # 本局结束即丢弃整副牌；下一局会重新由 shuffle.py 生成并洗牌。
            self._one_deck_round_active = False
            self._one_deck_cards = []
            self._one_deck_index = 0
            return

        rid = self._active_round_id
        if rid is None:
            return
        csm = self._ensure_csm()
        try:
            for batch_id, card_ids in list(self._used_by_batch.items()):
                if card_ids:
                    csm.return_cards(self.game_id, batch_id, card_ids)
        except Exception:
            self._clear_local_csm_state()
            raise
        else:
            try:
                csm.end_round(self.game_id, rid)
            finally:
                self._active_round_id = None
                self._used_by_batch = {}
                self._batches = [b for b in self._batches if b['index'] < len(b['cards'])]

class OneDeckBaccaratEngine(BaccaratEngine):
    """One fresh 52-card deck per round, independent of the normal shoe."""

    _SHUFFLE_SUIT_MAP = {
        '♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club',
        'Spade': 'Spade', 'Heart': 'Heart', 'Diamond': 'Diamond', 'Club': 'Club',
    }

    def __init__(self):
        self.decks = 1
        self.deck = []
        self.current_index = 0
        self.cut_threshold = 0
        self.shuffle_count = 0
        self._shuffler = None

    @staticmethod
    def _load_shuffler():
        # Same project paths and shuffle.py API as Baccarat_Special. Import
        # lazily so the other modes do not acquire a new startup dependency.
        current_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [os.path.abspath(path) for path in (
            os.path.join(current_dir, '..', 'A_Tools', 'Card'),
            os.path.join(current_dir, '..', 'Card'),
            os.path.join(current_dir, 'A_Tools', 'Card'),
            current_dir,
        )]
        tools_dir = next((path for path in candidates
                          if os.path.isfile(os.path.join(path, 'shuffle.py'))), None)
        if tools_dir is None:
            raise ModuleNotFoundError('找不到单副版所需的 shuffle.py，已检查：' + '; '.join(candidates))
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        # Load the discovered file explicitly. This avoids unresolved static
        # imports and cannot accidentally reuse an unrelated cached "shuffle".
        module_name = '_baccarat_one_deck_shuffle'
        module_path = os.path.join(tools_dir, 'shuffle.py')
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f'无法加载单副版洗牌模块：{module_path}')
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            shuffler = getattr(module, 'generate_shuffled_deck', None)
            if not callable(shuffler):
                raise ImportError(f'{module_path} 未提供 generate_shuffled_deck 函数。')
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        return shuffler

    def _prepare_one_deck(self):
        if self._shuffler is None:
            self._shuffler = self._load_shuffler()
        raw_cards, warnings = self._shuffler(
            has_joker=False, deck_count=1, algorithm='fisher')
        if warnings:
            print('shuffle.py：' + '; '.join(str(item) for item in warnings))
        if len(raw_cards) != 52:
            raise RuntimeError(f'单副版洗牌结果应为52张，实际为{len(raw_cards)}张。')
        cards = []
        for item in raw_cards:
            if not isinstance(item, dict):
                raise RuntimeError(f'shuffle.py 返回无效扑克牌：{item!r}')
            suit = self._SHUFFLE_SUIT_MAP.get(str(item.get('suit', '')))
            rank = str(item.get('rank', ''))
            if suit not in self.SUITS or rank not in self.RANKS:
                raise RuntimeError(f'shuffle.py 返回无效扑克牌：{item!r}')
            cards.append((suit, rank))
        if len(set(cards)) != 52:
            raise RuntimeError('单副版洗牌结果必须是52张不重复的完整扑克牌。')
        self.deck = cards
        self.current_index = 0
        self.shuffle_count += 1

    def needs_shuffle(self):
        # Never enter the eight-deck cut/burn path. deal_round shuffles itself.
        return False

    def deal_round(self):
        self._prepare_one_deck()
        result = super().deal_round()
        # Match Special's physical order: Player[1], Banker[0], Player[0], Banker[1].
        player = result['player_hand']
        player[0], player[1] = player[1], player[0]
        result['reshuffled'] = True
        return result

    def finish_round(self):
        self.deck = []
        self.current_index = 0


class BaccaratBetState:
    def __init__(self):
        self.bets = {}

    def total_at_risk(self):
        return sum(float(value) for value in self.bets.values())

    def current_area_bet(self, bet_type, _param=None):
        return float(self.bets.get(bet_type, 0.0))

    def conflicting_main_bet(self, bet_type):
        opposite = {'Player': 'Banker', 'Banker': 'Player'}.get(bet_type)
        if opposite and self.current_area_bet(opposite) > 0:
            return opposite
        return None

    def add_bet(self, bet_type, amount, _param=None):
        if amount <= 0 or self.conflicting_main_bet(bet_type):
            return False
        self.bets[bet_type] = self.current_area_bet(bet_type) + float(amount)
        return True

    def remove_amount(self, bet_type, amount, _param=None):
        current = self.current_area_bet(bet_type)
        removed = min(current, max(0.0, float(amount)))
        left = current - removed
        if left > 1e-9:
            self.bets[bet_type] = left
        else:
            self.bets.pop(bet_type, None)
        return removed

    def clear_area(self, bet_type, _param=None):
        return float(self.bets.pop(bet_type, 0.0))

    def clear_all(self):
        amount = self.total_at_risk()
        self.bets.clear()
        return amount


# -----------------------------------------------------------------------------
# Projected card packets for the cut-table animation
# -----------------------------------------------------------------------------
class BaccaratCutScene:
    """A small 2.5D scene; all visible faces share the same world projection.

    Cards stand along X, so the long faces show paper edges, not stretched
    card backs. Only the actual end faces receive the background.png texture.
    The two opaque separator cards never enter the playable 416-card deck.
    """

    WIDTH, HEIGHT = 900, 460
    LENGTH, DEPTH, CARD_H = 330.0, 140.0, 144.0
    ORIGIN_X, ORIGIN_Y = 360.0, 335.0
    PHASES = (('插入黄色切牌', .40), ('双手移开透明牌架', .70),
              ('双手扶稳前后两段', .80), ('后段移至前方', .75), ('错位调换前后段', 1.05),
              ('换手后合拢牌叠', 1.75), ('双手整理牌叠', .30),
              ('抽出黑色挡牌', 1.05), ('黑色挡牌移至牌尾', .60), ('放好黑色挡牌', .50),
              ('取出牌尾黄色切牌', 1.05), ('黄色切牌移至尾部位置', .50),
              ('插入尾部黄色切牌', .60), ('双手放回透明牌架', 1.10), ('整理完成', .25))
    SEPARATOR_GAP = 8.0
    CUT_MIN, CUT_MAX, CARD_COUNT = 65, 349, 416
    TRANSFER_CLEARANCE = 110.0
    HAND_CLEARANCE = 76.0
    HOLDER_TRAVEL = 172.0

    def __init__(self, back):
        self.back = back
        self._background = None
        self._hand_images = None
        self._hand_sprite_cache = {}
        self._finger_image_cache = {}
        self._finger_parts = None

    @staticmethod
    def project(x, y, z=0):
        return (BaccaratCutScene.ORIGIN_X+x-.52*y,
                BaccaratCutScene.ORIGIN_Y-.32*y-z)

    @classmethod
    def pose(cls, split, phase, progress, marker_final=None):
        """Keep the dealer's hands independent of the player's yellow tab.

        B first clears A and the supporting hand by a full card depth. A then
        slides right while B moves left in a separate lane. Both packets rest
        on the table during the handover; the left hand releases A, goes above
        the cards, and grips B before pushing it back. No hand is left at the
        seam, and even extreme cuts stay inside the viewport.
        """
        t = cls.ease(progress)
        front = -cls.DEPTH-cls.TRANSFER_CLEARANCE
        rear, gap = cls.LENGTH-split, cls.SEPARATOR_GAP
        marker_final = cls.LENGTH*.85 if marker_final is None else marker_final
        pose = dict(a_x=0, a_y=0, a_z=0, b_x=split, b_y=0, b_z=0,
                    marker_x=split, marker_y=0, marker_raise=24,
                    black_x=cls.LENGTH+2, black_y=0, black_z=0,
                    holder_shift=1, left_grip=0, right_grip=0,
                    left_open=0, right_open=0)
        if phase == 0:
            pose.update(marker_raise=32-8*t, holder_shift=0)
        elif phase == 1:
            pose.update(holder_shift=t)
        elif phase == 2:
            # Regrip first; only then open a small gap between the packets.
            separate = cls.ease((progress-.72)/.28)
            pose.update(b_x=split+20*separate)
        elif phase == 3:
            pose.update(b_x=split+20, b_y=front*t)
        elif phase == 4:
            pose.update(a_x=(rear+gap)*t, b_x=(split+20)*(1-t), b_y=front)
        elif phase == 5:
            # Park both packets until both hands have reached their new ends.
            join = cls.ease((progress-.72)/.28)
            pose.update(a_x=rear+gap, b_x=0, b_y=front*(1-join))
        else:
            pose.update(a_x=rear+gap, b_x=0)

        # The two separators follow their own packets through the entire cut.
        pose.update(marker_x=pose['a_x']+split,
                    black_x=pose['b_x']+rear+2,
                    black_y=pose['b_y'], black_z=pose['b_z'])
        if phase == 7:
            pose.update(black_y=front*cls.ease((progress-.48)/.52))
        elif phase == 8:
            # Close the seam only once the whole black card is outside it.
            pose.update(a_x=rear+gap*(1-t), marker_x=cls.LENGTH+gap*(1-t),
                        black_x=rear+2+(split+4)*t, black_y=front)
        elif phase >= 9:
            pose.update(a_x=rear, marker_x=cls.LENGTH,
                        black_x=cls.LENGTH+6, black_y=0)
            if phase == 9:
                pose.update(black_y=front*(1-t))
            elif phase == 10:
                pose.update(marker_y=front*cls.ease((progress-.48)/.52))
            elif phase == 11:
                pose.update(marker_x=cls.LENGTH+(marker_final-cls.LENGTH)*t,
                            marker_y=front)
            elif phase == 12:
                pose.update(marker_x=marker_final, marker_y=front*(1-t))
            else:
                pose.update(marker_x=marker_final,
                            holder_shift=1-cls.ease((progress-.50)/.50) if phase == 13 else 0)

        def separator_grip(x, y, top):
            return (x, y, top-8)
        def travel(first, last, amount):
            # Open before leaving; arrive before closing. The travelling
            # part is one continuous arc, not three stop/start movements.
            return cls.clear_hand_path(first, last, (amount-.16)/.68)
        def opening(amount):
            return cls.ease(amount/.16)*(1-cls.ease((amount-.84)/.16))
        a, b = pose['a_x'], pose['b_x']
        left = cls.packet_contact(0, a, pose['a_y'], pose['a_z'])
        right = cls.packet_contact(1, b+rear, pose['b_y'], pose['b_z'])
        yellow_grip = separator_grip(pose['marker_x'], pose['marker_y'],
                                     cls.CARD_H+pose['marker_raise'])
        black_grip = separator_grip(pose['black_x'], pose['black_y'],
                                    pose['black_z']+cls.CARD_H+8)
        if phase == 0:
            left, right = cls.holder_contact(0, 0), cls.holder_contact(0, 1)
        elif phase == 1:
            left = cls.holder_contact(pose['holder_shift'], 0)
            right = cls.holder_contact(pose['holder_shift'], 1)
        elif phase == 2:
            amount = max(0, min(1, progress/.72))
            left = travel(cls.holder_contact(1, 0), left, amount)
            right = travel(cls.holder_contact(1, 1), right, amount)
            pose.update(left_open=opening(amount), right_open=opening(amount))
        elif phase == 5:
            amount = max(0, min(1, progress/.72))
            left = travel(cls.packet_contact(0, rear+gap),
                          cls.packet_contact(0, b, pose['b_y']), amount)
            right = travel(cls.packet_contact(1, rear, front),
                           cls.packet_contact(1, cls.LENGTH+gap), amount)
            pose.update(left_open=opening(amount), right_open=opening(amount))
        elif phase == 6:
            left = cls.packet_contact(0, b)
            right = cls.packet_contact(1, a+split)
        elif phase >= 7:
            left = cls.packet_contact(0, 0)
            if phase == 7:
                regrip = max(0, min(1, progress/.48))
                right = travel(cls.packet_contact(1, cls.LENGTH+gap), black_grip, regrip)
                pose['right_grip'] = cls.ease(regrip)
                pose['right_open'] = opening(regrip)
            elif phase in (8, 9):
                right, pose['right_grip'] = black_grip, 1
            elif phase == 10:
                regrip = max(0, min(1, progress/.48))
                right = travel(black_grip, yellow_grip, regrip)
                pose['right_grip'] = 1
                pose['right_open'] = opening(regrip)
            elif phase in (11, 12):
                right, pose['right_grip'] = yellow_grip, 1
            elif phase == 13:
                regrip = max(0, min(1, progress/.50))
                left = travel(left, cls.holder_contact(pose['holder_shift'], 0), regrip)
                right = travel(yellow_grip, cls.holder_contact(pose['holder_shift'], 1), regrip)
                pose['right_grip'] = 1-cls.ease(regrip)
                pose.update(left_open=opening(regrip), right_open=opening(regrip))
            else:
                left, right = cls.holder_contact(0, 0), cls.holder_contact(0, 1)
        pose.update(left_hand=left, right_hand=right)
        return pose

    @classmethod
    def holder_contact(cls, shift=0, side=0):
        """Opposed finger/thumb contacts on the two clear side panels."""
        x = -8 if side == 0 else cls.LENGTH+cls.SEPARATOR_GAP+10
        y = cls.DEPTH+6 if side == 0 else 0
        return (x, y+cls.HOLDER_TRAVEL*shift, cls.CARD_H+10)

    @classmethod
    def packet_contact(cls, side, x, y=0, z=0):
        # The supporting left hand stays on the far upper corner, away from
        # the foreground transfer lane. The right hand presses the outer end.
        return (x+(-3 if side == 0 else 3),
                y+(cls.DEPTH-4 if side == 0 else -4), z+cls.CARD_H+3)

    @classmethod
    def clear_hand_path(cls, first, last, progress):
        """A raised cubic arc with continuous direction and soft endpoints."""
        ceiling = max(first[2], last[2], cls.CARD_H)+cls.HAND_CLEARANCE
        # The parked holder is already behind the deck. Do not lift a hand
        # there out of the viewport; rise further while coming forward.
        def raised_height(point):
            visible_top = cls.ORIGIN_Y-.32*point[1]-76
            return max(point[2], min(ceiling, visible_top))
        start_top, end_top = raised_height(first), raised_height(last)
        t = max(0., min(1., progress))
        t = t*t*t*(10+t*(-15+6*t))
        u = 1-t
        c1, c2 = (first[0], first[1], start_top), (last[0], last[1], end_top)
        return tuple(u*u*u*a+3*u*u*t*b+3*u*t*t*c+t*t*t*d
                     for a, b, c, d in zip(first, c1, c2, last))

    @staticmethod
    def ease(value):
        value = max(0.0, min(1.0, value))
        return value*value*(3.0 - 2.0*value)

    @staticmethod
    def texture_quad(target, texture, corners):
        """Map an image onto a projected card without an extra dependency."""
        if texture is None:
            return
        x0 = math.floor(min(p[0] for p in corners))
        y0 = math.floor(min(p[1] for p in corners))
        x1 = math.ceil(max(p[0] for p in corners))
        y1 = math.ceil(max(p[1] for p in corners))
        if x1 <= x0 or y1 <= y0:
            return
        source = ((0, 0), (texture.width, 0),
                  (texture.width, texture.height), (0, texture.height))
        rows = []
        for (px, py), (u, v) in zip(corners, source):
            x, y = px-x0, py-y0
            rows.extend(([x, y, 1, 0, 0, 0, -u*x, -u*y, u],
                         [0, 0, 0, x, y, 1, -v*x, -v*y, v]))
        for column in range(8):
            pivot = max(range(column, 8), key=lambda r: abs(rows[r][column]))
            rows[column], rows[pivot] = rows[pivot], rows[column]
            divisor = rows[column][column]
            if abs(divisor) < 1e-9:
                return
            rows[column] = [v/divisor for v in rows[column]]
            for r in range(8):
                if r != column:
                    factor = rows[r][column]
                    rows[r] = [a-factor*b for a, b in zip(rows[r], rows[column])]
        warped = texture.convert('RGBA').transform(
            (x1-x0, y1-y0), getattr(Image, 'Transform', Image).PERSPECTIVE,
            tuple(row[-1] for row in rows),
            resample=getattr(Image, 'Resampling', Image).BICUBIC)
        mask = Image.new('L', warped.size)
        ImageDraw.Draw(mask).polygon([(x-x0, y-y0) for x, y in corners], fill=255)
        warped.putalpha(ImageChops.multiply(warped.getchannel('A'), mask))
        target.paste(warped, (x0, y0), warped)

    @staticmethod
    def _bezier(start, segments, steps=10):
        points, current = [start], start
        for c1, c2, end in segments:
            for i in range(1, steps+1):
                t, u = i/steps, 1-i/steps
                points.append(tuple(u*u*u*current[k]+3*u*u*t*c1[k]
                                    +3*u*t*t*c2[k]+t*t*t*end[k] for k in (0, 1)))
            current = end
        return points

    HAND_SIZE = (224, 160)
    HAND_ANCHOR = (174, 78)
    _HAND_PNGS = (
        (
            'iVBORw0KGgoAAAANSUhEUgAAAOAAAACgCAYAAAAVdWCNAAA8T0lEQVR42u29eZRl+VHf+Y2I3+/e+97LzNq6q9Xq1opoSVUSQrSE'
            'LbxUixkbRiNsw0zWIGRgZmQkG5CNjYSxwc5KNmM8moPHPmDhsfECNq4cD8cgMyzG6sJGYCTZCNQlqRFaWlur9srM99699/eLiPnj'
            'd19WtRCgFVU193NOnu7Ofpn5lhs34hfxjQhgZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRk'
            'ZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZGRkZOQPGhrfgk/pvfLx7Rj5TMDjW/AJMxrdyMjIyMjIeGQYGRkZbzbjGXBk'
            'ZDS+kZGRkZGRkZGRMfQb3/CR24KtrS1+AOAHzpxRInIA8LNn5cGHHqIHAKPtbbvFrtexHjty++MOOru5KY8xxt8lKffGra3gvsU+'
            '3rBHDzjyGTC+s5tCp3cUAH7xu/7iMzema19Th/gnm/W1O6u66ZnpPe2y++Ue9nPPecV3nH+s4W7xgw+CH7h40vHQQ44zZxwg0I0r'
            'afRQowGOfFzD29pinDnjROQ//tdeecc9x6bfEWHfcMfabIZsqGZTTGZT1JMGEMFe23Uu9N9y0p9Tw88uHrXf/MLXvnb++3tXL9fV'
            'mTOEkyfpwYceIgB44OQNo6VisT4a4MgfinPemZPnaeX1/uP3fcvLg9l316Cn9SnpdDpN0+mEq6bmqqngRG5tZwbEyaTmatJgv08A'
            '83sd9OvZ9Fch4Te7lB9JWS8+stzfb4+c704Pv/+TuSHsnDxPmwAefOjEwbX4IGDbt9bZczTAkU/lnOeEnR2m06cVAH7h+/7yCycx'
            'flcN+vJrV6+h6/tufToNa2tTmkwbzA4fAksEiGDzuSvgCAFS1WaqEqNIVQVIjOhUsVimDOHrAF039wUzelVbZrUsMAPJwkDXVNNH'
            'GeH9HPi9jPzInMOHn4+7r6ye18fj7NlN+WQNejTAkVvI452k1QX+hq2/9PRDG7PXRqJXiHq8ePlqr0w8W5vwJArqEFHFiGYyQagi'
            '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'
            'K7wBq116N57/OSvrvz7uRUibm5u8euzx48f9xImdYV3YY0J62lpdA1u/85ecPw8CNrH6PTf93d/xvm2eOFGFQ/z0nOmLiO1FMDuR'
            'U3paHatjsRIilpzNO3Ms3a1VQwtQR+aZma2KoXezfc26724dCe9D5Dq5d6GSjyLyW//5L7z512/ljObj2QAJgK+trd2Zkj+X2T4f'
            'wH1wPNfdn01E98CdVskZM9PSUEsX9ufzkwCu/x4Hcdra2qLzw4H+woULdPz4cb/J69zqHzZ9DpINVLK55YbwMe/XAa986UunVy99'
            '4Eg2ozBpco++vYZrLfD+fO4cPulwfphq5ngc9QnS7f4CDuHQ4X7S3wfDFzHjBea430zvi7GaVrH6zivXrnzvKoT9FN+bP/RjEz4Z'
            'o3zw1GM24ton8h47gDMAYQs4f37z4EZ48wN/N8878gd/w5DBoAJ+l+Uy69X6M9en619/5MjTDw0/Q+Nb9zkzSt4qLYyEx36NzuVx'
            'cmHSYIirUFHH635k5HNvkGH0fCMjIyMjIyMjIyMjIyMjIyMjI7cmY+JuZGRkZGRkZGRkZGRkZDxwjnzWPvdRcP45gse3YGR0EiMj'
            'IyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMj'
            'IyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMj'
            'IyMjIyMjIyMjIyMjIyMjIyMjIyMjI59p/n/AfGE2upyWEQAAAABJRU5ErkJggg=='
        ),
        (
            'iVBORw0KGgoAAAANSUhEUgAAAOAAAACgCAYAAAAVdWCNAAA7U0lEQVR42u29e5Sl11Uf+Nv7nO+799az35KtpxVbhm4TJzFgCAkt'
            'hwAhcZg1QPUMDAOYBSjDguHhQDxAXF0LCAHbIeEtGE9iiI2naxIPYDw2kIU6DNgGy+BHN7YRlsGSLfWzqu693+Ocs/eeP853q1sT'
            '22BLliX7/NbS6lKXVHXvd88++/Xbvw0UFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQU'
            'FBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFDzRoPIICj5J58nK4/irweURFHwSUIyvoKCgoKCkFQUF5VAWlBywGGFBQUFB'
            'QUFBQUFBCYULymH4ZLynJ00fyjY3+V6A7zpxwujUKQEAM6N7T5929wK6tbWl5RgWFDxeBgeQ2Sb/7uam/0jf3/z/Fb7ObGw4s+IV'
            'iwcs+LiemdlgbqdPE06coHuPnqO77oISPdqjvfuVP3q8Bn/5eDL6IlW7I/Rd3U1nF/sU/+teM3vNl7z0F94LAHZmw9GpbSmPtxjg'
            'Z+RzMLvOmM6dIwC468QJw7lzhtOnDQCI6K8Mbf/kZS9bXrqRP8cx/pGv3JeT2N9eHY9GEEHfdmjnDcK8ATzj0mw+j+Bfeuhy86P/'
            '07/5xUtmRjh9mqiEpcUAP92wubnJd10X/t114rxtA9g4d9w+3gN/5syGG189Prp1srJSeXd0VPlbIelzPLsvINjfguozVuoKoe3Q'
            'tr0yEHk8YjKj0AWErtemabVpmqquKtfDHkjM//If/MC/ffXCG54+d9xKflgM8NMCZ85suFMfI7yzM2fcH+PDh5Y1PV3hb9Wkz1Ck'
            '25yrbmDYAZgsCZi9Y+8cT1RRM9ESYOsQXV+aVH7kHCRGhJAQowg7JxJ6RkpwAPHyMsEMKhHznV20TYfZrLFp06RRXY8OHDyAHvbG'
            'NsaXfukP/NQfLV4XNjb0r+N5C4oBPvkKIgYCDERkb/7Jzdsrb/9Emf6G9/WySlplxyvseZX96Eg1qm9wTIeXJhVXzg0FFYOpQcxg'
            'kkBEMCJoUoAJaoCoKAFC7AxmRCAiMyYQYApoAkk0GJGKIIWIrm0RYkSfItoomM9adWp69PDBWhzFaPbK3b35y1649fPvXxji6XPn'
            'ikcsBvjUCjlPn94yItgf/fTm6cl49L0jX606B3A9QgwBPK5BMLjJEsAeplFgpkyk5D0k9GSmOflThUoE2C2aHGRQYudB7IhBYBiM'
            'cpRLqjBRSBRI7M0IZGRg7yEpQUJCCAF96BFTQtcHaJA0ZnZrq0uuTbLTm/7clVZ+5qt/6N9++Pow+t7SvigG+El8PY853LIzZxyd'
            'OiUbGxvu+//+Z/3SjUcPv6jpo4Y+RD+ZADACM3hcwzuCqydMTGSaYJJgqiDnYUkIBEiKMBGoKrKPA8gMAMF5B0oJBgPIwcDwxPAg'
            'EACJEdJ31jUdOkmUmOCXxuDKwzkHNUVMCSn2CH2P2PUWuiiTuqoPrC1h2odHZiH96m7QV/6PP/hT777+ggGAYojFAB/v1/JYDJDe'
            'ds+3+c+9+xfjH/zS5qHaql89MBl/WWeuZ668aQKxg/YNeDKGqx3AnpzzMBUQM4gATYKUIpgIpgJNCWYKU4WZAkYwTSACzAyIPcZL'
            'a/C+QsUOo/ES3HgEECPMp+j39ix2AaEPaNsOPYRQefiVZfjxCMRAEoEkQUo9JIeqpjFJ5X29Mq6wM+v6ztzv96pvIgtv+ur/7Wfe'
            'schvNzbOlDyxGOBj9niPyQBtc5MX1cw337P1/Loev3KJ6cR81oQYgidiMAOUzJz34MkYNKqJvQcxw1IEDDBTqAjMLOd8poAqzAwq'
            'CRIDzBQMoJ4sYTwZYzKeYFSNwADMCGACgaApIbU92lmDMJ1Z37UwzxACmSeodyDvwHUFMMD1GFEN7Xyac0ciRIGSQohQMTGLJszb'
            'PqYkbwhkP/J1P/Szb1sY4rlSOS0G+BhfwydmfEPIec+3fVv1RS94zotNwksd8URUe1ZU0vVIMSGZAGCYqqkpzBEx55dgZjnEVB26'
            '7AYRyeEoAOc9mIFqVGOytILllVWMx2MQDEgC7TqoKEQs/9kHgAhmhCSGGALadoaUIkIfoClh6eBq9sLOQR2BHaGarCC6GlcvX4LG'
            'FuNRBZBDSmKhbcUTrB7V3vna7czb0Af5ORZ6xVdv/fSDQGbWYAM4dWpbUaQhigF+ssPPhfG967WveO6ontwzGY+eP5vO1VSFckWE'
            'JET08waxaxFTQowRIgkqClWBEWBgMBGq2mM0GaMaj1BVFerRCNV4DO89qlGNqh6BRQBTWIzQmJAGAwcRTA0pKVQUIIKKgqsKooIY'
            'I7pmjnbeoJ01IADjyQhLa8tWrdREnqGSUE2WkPwYl69eRexajGsPJkMURYoJjoDaOXGeHajinXl7JRpejYSf/pqX/tSfLZ7N725u'
            '+s+ggs1TUhDqKVsFNTMCThPRlv7JL//EN6ysrPzseHl5pW27YKpOYiKZzS30PfXNDO3uDH3ToOt6COVPyFU1ltZXsLy2jOWVVZus'
            'LFM9mcBVHkwMqGUPZ4CJAN6BzEDEUBVoUqghG15KgBpUBCKWPSk76KJ9YQYJASH0aNo5ulmLrg/wzmNpZdn8iMhVDs5RNvSVVQR4'
            'fOihB8Gxx/LyGCICECAKpBjBRDYZj4SJaxBjZ97OktJvJOD/0Lc/9LuntnPv89PEKy7OKm1sbNCFCxf2z+7Zs2cVgD7Vb42nDK5v'
            'rL/jl1/+8kOHDrw4gg1iSVVcmM/QNy3CfIr51Sli16GqPaqlJZgJ/HiE0fIyqsphaWUVfjyCZzZyDDXAxMjMQDBTVTJVEJNZNlsC'
            'M8x5mBlMhLiqDZIgIcDSUKghhgGQmHIhJ0SoCJIp+r5F3/WQJGB2xuzga6K6quA8g9nBVQwar+DKtMHuxQ9hbVKhqmuwc9AUETV7'
            'RCKGY5iDKZirytWY9hFdSu8A0a8sVfX2l373j//lddVTf/r0aXkSFW3o5MmT7qN989ixY7a9/VdfHCdPnvSzmR5daXl69vzZWTHA'
            'T5rxnXGnTp2Sf7/5jePPe9ZzfunQoUNf30aNpsqp7Sj1HbrZHrpZg6sXLoOZ8fRn3IrReAKYwlUesZujWlkFmYJ8BXYOvq7B3uXS'
            'ixoMBlUxCQEpChkTiCkbliqIPbiqcv5IueVgZoPBKcCcWxdJoClCQoCIIsYAMUHsexAR2DGIDN47VHUN5yoQAc4xqBohVSNcvHAB'
            '88uP4NCBNVSVB8FgKjByEBWIGUQNUDMGhInJeVcJCNM27JjZbyvkVaF95LdPbW2Hp2LR5uTJkx7ASt/3R1KiYxC9xaDPBNxNML3D'
            'TG903t9hZN/0tre99T9vbGy47e0nP7ndP6WMb2PDnTp1Sn7rx7/7c284cvRnD66tfX7TdiFF9anvEZs5+maObt5g59JVjA8dwK23'
            '3QZngIJgsYeKwbgC+RpI0dzSEkhBxgw1IlWFLYwmJRIViOYKKDGDnAfMwIioiHKel/IZJp+9k4hCBy+YDTBBAIQUkPoOYIJRbnmA'
            'CH40gneUw10NIF9BVUEq4NRjdWUZoV1B00dMhgvAkYG9wRGhcgwFQUQohOhjSnDmExPZxNkBZrfRKW+45ZvP/fqPf9ervOmv/uNT'
            'uWhjm5u8feI8bZzaVnrs4SkN1WPLKUL+u+3tbdrY2MC9996bSe533YX77ruPptOpvfzlL1/duTL970PoRzAkkHMEnbBzh5PIMQKO'
            'MtENfZsOpaTrMDsAsjE7hhnlwpkZcjWNEKN4ALg+RC0G+HgZ3/a2/L+veMk/XpvU/9fyeDyZ7s5CFPGSBH0zR2xbzHf2sHtlB4du'
            'vQnHbno6DJT7azGCR0MIZ4aYDMwOrADYZw8VemAINFMIkBgBxyAQzABNCYQEdh7Oe1jbgYigcHDewUJE7DqoASmGzIphBzOg71uk'
            'EHLRRwBy+cAw0ZDTEsh7OM8AMYgZTAA0YXnkYUeOYu/yRaQUUVUVxAwpRDATWCjnjo5RTcYwUyRRTiIgmIhErcihcnzC2P9EF9O/'
            '+PUf/19fIya/RC/Zetf1RZu7AP1EpjHMjIjIaHg/14W4H9Oov/D5X/SvVO2fxZjAzgEa8+cCAnO+wIQMDEA1QVWVgBTNNKfWCgOR'
            'h1MFjdjsKSU09pQwQNvcZGxt6Rt/9Ds+a0J4Te38uO9DH6JUfd9CYkJoO0yv7CKI4qa/eQKra6sI0xmc9/DLa7Chua5dgLlcrax9'
            'hXbWAMOhSX2AWq6MppQgKYIoh51EDEgCALjKgJC/x2aAq+EcIUn2nAaAfQWViBQTVFNmxEhm0ogqEAJ8XcG5Cmq2z6wBudzcN4MS'
            '5RyPCEtLy+i7Ft18iomrzHmilBxENIegMYFIwUxwjuGZ4ECg2lFM4kJMkKQJ5NSzO1x5/51Nb3f/xsu/5/Wq6Zc/MMIbX/BdW/31'
            'xggAF0+ct41zx+308Penh9EsgEB0zbgWBnfPPfdUd999d3zDG94wuvPOO9cBrDOPDiHpuhAOOMcHUtJDRHpgeXn14Ld+yzd/zf3v'
            '+7NYj2oVSaSm5tgj5WdPqoMnpUXAQKQiZCDPxPmR5eg7kQmpii8G+Djnqdvnz9MGYGPnf35c+/Wm7UPqQxVigvY9uukcs90Zlo8c'
            'xG2f/SxUVY12OgV8hWZvF+nyZXBVA0QgcuDKozIgzGYwNYBgSiBRhaSIFGPO8yi3BA0AmYKHnM2adsjzCL6qQNRBY8h5nxnAlD2R'
            'ArHvYapQCJJq/n0YQiazoTBjIOcgIEAsN/qVQJy5o5YSAMF4soSU1PoUaOIqVFUNX2cWTQr5xQoMEhKYAWYGiaIiwNcOCsdJlEVV'
            'QkziCX5S+a8C/Fc9O6bzb/yJ73oNkf+1L/++V7z7BVtb6SN9GFtbW/9NGwjnztmHvumb7nTjlf/Yh7D0l3/54cY5tw7YYQIvOe9G'
            '3mfqHQ2XSr4oPNbXDiClpFVVOQPgnTczI1XNlx8MMNq/JEUEGEj2BjMQw0xR+woGQyItBvi4er8zG0yntuU3T3/7t960vHxXKwgx'
            'Rd/3PVIUNDsz9CHgps++A8duuxWaBCaCydIyUt/D+8PoZ9Pc/FYDE1tILbVNAzOQJTMjJZUEMYUOjXSYgtjBLBslmcLVIxAMqe3g'
            'nAeIUI1GkCTQvkO9ugxLAqo8YkpgZsSYIClBORuIGcCO4cc1AIIqADLEJPn7vgIzQQAgCUg1h6PeYzwe5TyvE3QxYlQTKldlTwwb'
            'Lg7LYbNzmdGjAFs+zI4JTIA40GRp4vsg1jZNdK7CuHLHl5dHP9LGdPrsT3/ffSr4fYH9MYgeErWrh5dGU3LjNHKpv6JBdlI9/8q7'
            't5qFzs2H7v5fvuLYDUee9/DDl7C0tAQzQ0oJqmpEJCJiImLZa+a2TFXVWF1bdcRMgzlBDZSjjuHyM8PCDhdG6atqIE7kZ8bMSJqG'
            'VEGoGODj1usD4fRxu+fbNtY98Ut7MU0pcj/vkELElYcvwhzjxBd/AdaPHoGEBLBBxcDIJXpYgqtqICo0JvR9HgVSWDaMJJRPheW2'
            'gi4YMZY9liSYRDjvQS6gm06RYsTqocMwFfC8HQzSYcIeZgqvBo4DV5QYxoDEbNQ8qiAwWNfDOYdqNIIhH640NPJJYg51nQeDADWY'
            'CAg85H/LSH2DmASW7W3fu9hwKI0YogojQBbEcMmpHRPgCJiMmBy8I18hxJSmbaveu2qlnjy/qqrnGwhBBCkGTSqB0ck8al8D+jSK'
            'e2/9+R/cYeemXTOLl//sT+4cL9+VYKZ93zMzQ1WJB4sbsAhXoSLwlcfa6trAPMrfUxUQMbx3meCOHCmICDjTliASjYhhmT6RK9Gq'
            'MCiGzLkY4OOBX7z72/zdv7gVz/yLb/mG5Xp0c9OEEJvWd02Pvd09LB9Yw7M/77lYXl9HCglMBNKBTN226NsOfd+hm83RNT3aTIam'
            'hHzD5qa5gJmGg+xgTLmKKYKYMtMFBIAdYt/rdOcqLa+vk80aEFPO7ZoGa0ePgdSsco7gakyvXoYkwWR9NTNtTPOtLgLnHaq6AlRQ'
            '0eKWZwzuYTAUharCoc7FCMneEMQYj2o0KSDFHmoGD8BXDkwMy9kRJMTcyiBAYj68xASuRyAgj2Mx5VyRFeOlmlNKrEYaxFQsqHNM'
            'tXNUUcUgGoEZzLxs2bsfcapwVYUxjzFiAxEEML8wMubMLtJFGHl9N50JVeVx5OjRTPnL1VNyzGaLUBND6wc54GRetICyITr2EE2w'
            'lN9f/n50xQAfv35ffP2/e8ULRmHnX6W+jykGN92doel63HjH03HL7TejrmtISDBNFhUkbYe+bdFN99A3LfqmR9P16LqA2bzBfLqH'
            'kBQ8GsE53g9zQAxfeejw4YuphRABVSIijUl0Op3W8/kenra8HKVtnQHoZjNjzh4ldT3WVlcB59FFgUrChBiqCUYwJibHDE0JGI2A'
            'wdgd01CIGUqG7HKJPVsPQPXQfzSwAxwxqnqEPnsnKLJxD3PEcOTgaoIORSMbPErOvygfYOeQYoD3HhABO4fRqEYSJU9gU7AmgUAh'
            'QVCNvABGZAYjA6AmEJixpRitlsTsHC1+xxDBwBggo4WUFWy/8ktwzDh27Bh0YBARs7FzuaeqBmLsG9x+/jh8ZszXopZFSJu/RvGA'
            'jxWbm5t86tQpef3mS+5Y9/RaE7/S9bO0e+UywROedeI2HDh8BEweJorUzRBDohgiQtegb1s0V/fQzOeYtxFt36MXQRci7c0am+1N'
            'bby8JOPxGGBHw6mBNTnsJJhJSpoyMdsb4M0SLu3uvC+qrq637dNmTdulKBxDR2BH6h6mlbUVqHPm5w2aLpBzOfwbZgjJzLKhOY/Q'
            '9VaPKlIWMOc8DkyLQwRwbkXko46hEAMQMSQlOF+DXa7UiuRGPDuAifd7ls45QA08Huf8z7kcosJA3sG5TE5gygUbM0XlPZiJWNkk'
            'JRiDyAMxRkICkqhx5UlgRMRwkhBDgxSCMfvcQtgPNZGDX1pQBwdBOdUh7AZuvPEGVN6TqJqja3kyDTkzEZNjZ2qSR8VykpjD1SEs'
            'J8dDFJOnMosBPpa8D6DTAM5sbtTrRw69dqWiY1euzuPe5asuQvDsZ96Gka9gAhgUfcihZkwJsevQTWdo2w7zeYPZdIbpvEUTAqIC'
            '0czamORqH7wP0S2v5J7aYibKrks+kwhEFb0kNdB7VG376oRfdqRaefbVtvtPNdGtEiOSKjw77M3mwQiIfWDpOzJJdvDYjQiqiCFh'
            'VDtiGNg7MDvLOd7IDEqqkiu0ajDkkJc0ey5ihgI5PLWct/qqyi6qrsDRwcTMEiCsBJdzJmiCUTY6dg7OeZhEEHP2ulUNRwa6Vt/P'
            'RiNmxkzODbxX7w0VqJnNwEKmZtAU8ymnLLthADRl9QDK1pxDT9FrF8p1U2eLr1KKOHr0KCbLE+v7kPPglFMJHtoxRGpmg96AXfsZ'
            'Mvxs57NCgYrCOYZjrooBPgZsnznDW6dOye+8/Ie/+9DayuddfuTBMHvkkp/OZ/isv3k7RszQmKDWQgyIMeZ/QkQ/azDbm2LedmhD'
            'xGzeYtp0aJIgwVQ1ou+6Kpp1veof9PPmfufcrUR2hIxqI4gZggGXDfYBmL3b4P6om8s7t8+fD8NLfNvXnnze85ZV/ruk+kUq+hyu'
            '7NlEWEt9j6t7e7Z39Uqol5fdsdv/BrXzFn3fQWqP0biCJ4KvK2Ijc54BGNjlP1WGfJN48EoeKpkZY6LZe5HLbJrhgFpmfwAesKgA'
            'HNj5wTCyByUiwGQghQ8Fm8GbOuehqQexX4joZMNzRK7ylsnfCfV4BFMlpMHHKKCWw0Nfj8CDh6Kh4LMIOBfyHfs322DwZoYYIw4e'
            'OozDh47goQ89lNsvzLmHqrmnCQNiiqi832e9aL598+WkBiYiNQXEkCSVHPATr3oaEZG8+sdectBV8t2z2QUN0ylfunIFR2+9ASuT'
            'ZTMjqCNKSdGHgBQjQhNy2DmfY69pMW9bdCFh2vcIotbFICKpVhM0ffw1ePoXv/q2973343ltA7dQNwHaOnvfJQCvHP7BN/39E7eE'
            'uX7ZZDT6SpL0glkXVp9+49NgSWS2e5UEBtUaIIOva5AZ2DvKE7zDyJJzWIRmxABV1VC8MUByS0RTALmcL5pkFoyrKgRuSaFwxIt6'
            'PdQU7BlkChiD2IGYYAKw8zCNYM5KAOxqmMZc9KhrgqShoJMnughAXdWZYeNof+qDNVPhyPncHx1ev5k9Kgw1gxHRED7mK8EMllLC'
            '2voajh47igcfehDMLofYQ1EmG2s26BjjfghumgtUZJmOljR7ciVARCbFAD/Rjvvwob3vPR9uJzdSSFVllx+8ZG7kcOTgWk5fHCPE'
            'iK7pEKNitrODZtagF0UfI6ZNg3nXo4/J2hAkplirJNfG+IFkeOmvvP29vzL8Ot7Y2KDj29u29ehRFtoE6N6TJxkA7rrrrG5twRbE'
            '3q2hL3/y5Ek3MPXlP/zeuQ8uDPLbT/7tZ8aqvmttde07Utd+Ttv1GlNkVcNoVA+DvZk6RkOh3YZJ/HxIFW74jqY0TOMHwNww4GtD'
            'f09h5MHk4OsRLPVZWMoAozwO5QYLMBWQzyo1PMpDxCbD5L4iG/+CdSAJGFQBnK+gKsi5HUMV8K4GPENiD+IRvPPQ2AEpKwXQ0FJZ'
            'tAxUB1bPItQdWgYY3utoPMaRI0cgKYHrUe7t0WBo1/X+clqcNXSYr4WjkobwHQTvHURSCUEfW999w5161au6n/n6f/KfllL63is7'
            'u/o5n/t3zCsjRkWKudjS7jVo2h5XLl/BxUcuQNghkWkbRINEDiJeUnRtkktKuMdgP/krb3vP5cVuhi1At7e3H2X/i1RwCzDkGTOc'
            'PfuRX+fZs2f3mSKbAJ/f2KDjx4/b1tbW/QDu//znPueOytNzzSx2feKqCkihh4QAjHKxwkRB3i28/z6p2IBcSNEI4uH7MQ7smTzu'
            'ZPn0ZYN1LttNSjDvhgqjW3ib7FKRQzYa8k12LodwqQV8lQs4gzYOzHJoV1VAIhgErhrD+ga+qgEAVV1DYwRUhzA2PsoDmum+F1s8'
            '2fyvNrzd3HP1vsLTnvZ0pJRQ1RWSKLzz+8aqmgZjNEgSOMdIQzSrIsPQs6DyNXQQzioG+BhwantbNzfB732r/ABdfmDnc7/wC39w'
            '/cAhJl8jpoRm3qGdzTGbNWi6DtOmw04fMZ1fNvLeGzsEEUSVP09mrzWufuHVf/iuBxdh5NZHH1H5hCcBtgDFYMz3PO951WtWVix0'
            '8U8xHmNUVdT7hBhi1gkFoFEgLoGcy/KFlo0IoNy/qzzAFQABD2JR2WPk3AfM+31CZgwUOZ9DTqbBE2U5jKoeZW+kCjaYmRF5j0Ev'
            'FewqwAyuqsHsMvkgWytk6IHyEH6a5a8hKR9+AH40giRGiv2+dqpqNmAz7F8CWcwqf81MCwogzIye/vSbjIiGnmwesVJVOO/3Wwy5'
            'nYIcftu1SqiIwDsHwCCquSVTDPCxecHTJ84wbZ3q3/oLPz3Xbs+p9KbK3DUtmlljO3tTzGdzmjcdZvMWyVSamKqm7R8YLU/+DUDn'
            'rujSW19/333N9fnbEzEf9qEXvlDObm3pl3zVP3xL7GO7urI61qTati1ZFDBR9oJMcBUbJJJqglVV9kimQFST2AOcx3qr8Xi/0qdm'
            '4EWON1Qh2ddgx2AYeOidLTiskgLU1WAzKAnY+Uz8pmG6YwgVYUAM/dACcFCJUGNY7OF8PfwflAtAQ9+UhykREENjRAz9UBzSodpp'
            'g7zOcPGYgpRxvQaPpGS3P+N21PUIBoWogClfJAs1gYVRmxlk8OS5d5t7iQswEaAo0xCPBb+7uenp1Kn0X35864fWV1d/+GqcJQtE'
            'ze5lNG2Dnfkc0+kMzWyOWdth3nbSx94lpXkQ/pr/8w/Pv/36wsmZ7W2lJ3AwczHg+q7//Dvv/+IXfdX7lyp/IninqCrnuIKGCHgG'
            'YoSZwY9GuZIZepgRuKqglqBQ8uyN6xohBDIFGGSiiWyRY3kHHqqBzjmYxDxpAcqexHIeSUkyadwWxLCsApeJ4x6+qhBCQAoduBoD'
            'g6FDelgyC10DkKJeWoa0DdhX8FUNg0FSzFVXNUgMoGpyrd2gizA0+1QDYCJmpjk3RK5wHrvhGA4cWMOly5ezUXk35MQ57zSTITwx'
            'OPbXEdozOV5EMl0PAC2UkYsBfiLslw33glNb6U0/9gP/9Mjhwz/chTZoitzs7WHn6lVcne3ZdNagaVo0TWNt6LVPwp0IEtnXvu49'
            'f/72jePHa5w4L9vb0O3t7U8JM3cxu/jFKZ33YzpRVZURk62trlJuNThYvNZvXISDcAyJEcxMzAyFUkohN++JkERocaAzQZlgqEjE'
            'wN6bOQfTFiYC5jzO5L3PlVAVZCU4P9DiKPNcAURhhK6FxggKKcvudyH3zplhomAPoGtzY4PzuJZ3DgSyFAMZKP//bgxNMngtgRoe'
            '1ZYwydVLHQo2oQ9YXz+Ao8eO4cLFi3DsEGOEdx5gRRp+FgA45qF9QvuhaNZoNcs0IEVahKBniwF+AuyXLX319939rJWl1X/PBNm5'
            '/CC3u1PevbJrV6ZTu3J1F23fo21bNH0vIYnvTTWYfd1r33n/b5w8Cb999nzA+U/tezl3PE9jj8ejhyfjMfZ2pra0vIIjR47Yzt4V'
            'NH0PzwxWQ9s15usao7oe6B02DOtmYvKikki0GMUx1JUHLWYUTUxjj5Q1MbLUPjO8ZxAM3jGYa9BQzLh+gtwyvxVp3sLULMWeTNkM'
            'QtL1ROTMeZ+LLAYz66ga1VkVCglpMTQrihDnSLFHPVkdxKNyTjcYy7Vhe+Lr2i2EGCPG4wluuukWvPOd74If+n2iAmgOp3nRA8zd'
            '0mt5oQJiWZU8xizxYSLL2f7OFgP8eHAXwFtAOnTTse9bXxsf3t292Lc7V6srD13E1emcdtseO9MZ2raxpBaDpHErMhfo1732XX/+'
            '6ydPnvTXVyafDHBVlZk2KWJ5fBC183Bw8OMJFIp2OsVoeQXsHEKIVleeaJDCZ+f2OaKSEiTpINi0KGBoTq0Gepn23cCyyRMT47o2'
            'NSVmzkPD9RgSuiyj2Id9DxJDROySqWlmdyaAoRBReG+o2UNM8qS+AZwEEAHGE8S+BwZm6Hw6Q7t3FdXa0dyzWww5S9o3GAaZQfbn'
            '/NTycDIx4eabboakBKurfRW5BUNnMT843E85JB0uJVPaJ7Pn9sQiBzz5lHCDT6IQ9F4AwM5ffmC2+vQZ5k2nFx96RC9e2qO9tsWs'
            '63Xe9dbH6Ihp3Ej6QFL9+jPn3v/7J0/iSWV8d+XKKKDWwgQVJRw9cgjdzg6NlpatHlW4dPERjCYTq0c1QQVgIhExX3taFFdyRyDP'
            '9BEASwJUDm7YTcHEILVcNTWD9x7eMbz3YOeIkWloBEBCDzXOrJyY2xd918PASEnRd23eJMVZGjELVjElS/CuApgNjiEDwya03X7f'
            'Rs3QTGdo9nawPDTJVYd5ykW1UxTRbEGAJx1ev5mZiuL2Zzwj9/E0F5eub8Tr0NJYqI3j+jB04dEpv+8k8SkVg/onj/ndpcBZfOiB'
            '979q98KFb3eikwsXdnSvCdak5KKYSwZ0pr2q/Yeu9v/ydfe958PZ+PCk8nz3Lh6ur5rZ1R0sHziI8fKE2j5gsryM+XwXBw6sw49q'
            'auZT0EBUZp+n23iYgyPmPGQrg5EhT05wXn42DNhy5kNq/p7zNVxVgbwHVAZWjEGMIJKQBn2clARRFCJqMQmiDqRsFXLOA95DTVE5'
            'B1e77DlDlrsQz5DQZ9W3oRIaYkJom2HhzDBSJfvVWhMVooHDiaEzkSx/bH0IuOnmm7GysoJ502AYRNr36FmqwmCqlkNvGvJgHsgC'
            'ihj7nGWqPaV0T580Bri1taWbAL/4db//ju/84ud+RZXkx9oQn9NFGyfDngD3g+i3EvjVZ97xnncvGuBbTzLjux4xdDPpe9x257PQ'
            'tZ0tr69hsrYKQ6A+9KZ9h+XxGJbFKABkVbbcJHc553HDTovBe3g39NFSAmk2DpIFqVwBCaAsY2HGHgomSEQSRcraKRAhi2KU9xsq'
            'gcnYOXiXJxn8KB+LapS3R+VRIZCkBK4mkJil9UUBkZhbEs6h3buSFcKHAVrRHCouGCxuKOgsUjhTAZgR+oCDhw9jdW0Ns3mzP9mg'
            'KlnEyoYG5iDjgYHTqppnNnPYXQ+e9ynVBnxyVUG3AN3cBG9tveN3AXzBNz7/2bdHo9XWydXX/eH9D+63FwC3DejWk1UNeXCBl69c'
            'vnj7TTeDTMjYYWV1GX07w2g8xtLKMhYvP6YOsQ8AXGZDe0ciAkkJlfP7ZBIyGOf4DPUwYpSJ1bw/zc8gpBQhIULYE1VjqBgkASka'
            'kmQZDObKxAKRI3jnyI9qePaGXEElG/ZkiGW+KUxBg8wEVAb+J0GZs/pb6NHsXhmMIBsOgZBSArECBhOkwZj2U8TsJUUxHk9www03'
            '4gMf+ADG4/FAz1tMEJItNFeZM791sTxVLXtUSYMCObSQsR+bJ4Rubm7y1taWvuqt7/3A9d87efKkv+vsWd0CntSCqyeOHbPNzU0+'
            '8Mh7Hjh4YB1RQasH1+E9oTpykExS5lySQWE0tgpxEiFqlELKJXpjcFUNEhmSmTJmBDX4usotgEGKImuTxtyshiJpj5SEkgbEaZNn'
            'EpH7dDAyYiZHg1oq535bnqljAvJwrmrmgsIUrq5hg8yiwXKDHgyz3Ng3Yrh6nGUyQoeYYh68BUMk80v36XPZ62Yhies4nUtLy7j5'
            'ppvxlkGVzob/eGGs188IynV8UAINnnafS1tC0Mermb3gbS6849mzZ9OTPbW2zU0+B7hTW1vh917+Q/9zDYJWjLUDq5RXxQwyggaC'
            'd6gp98SceogBCb0lTSQ+634aZdGXgUEJBuCdg3cEOJ91X9SQkmQxKeY8siSKPiSEKNaFOGz7zXGuH1Vgz2QxDXmTYrQ0hjJQ0aBX'
            'WtXDSu7MclmMOAEM1QgVG34XZb5qVWG6exVdFrtCSgLvMXhD2/+TOZOwY56Ah0gaRqQ8nn7TzYNRMYmmPDRhBs/XGvOikqVEgH3C'
            'dxr0YkwFYirFAB/HkPQp8AzJNjfpXoDvOg0l2lIA4bd++MUvWp1U38r1KDnHzlHWBFWJeU8FqkHUNzenEyQ3vJ0j7wnWR/BC1AmL'
            'kaSFWK8CXEOSIIRcUAldty9boSCkpOi6iESEEDrErssFkKF6iOHAes5TBJMQUHuHpaUJUHk4smHoVcE1Dz04GjRPPcgTQgiZ16oJ'
            'bR8wm0fEvoVxlbV4OjyKoA1kjuhiYkIX+i5m6LoOt9x6W5YYUbmmC2NAGsJWqO5XPUUFznh/PGnRV4QUYd6nHAyg05ubdPr6vzy9'
            'ZSDg+r/fPnGeNrCBe8+dyxLrg8HR1pYBUGwBb/7J7//spcnqt/uqursejwXMZCqAA8gRqB4ZD3N+IiDHBMGCSmX7K87yTsI63/gx'
            '7XsgoixD3847pBjRzNthu26+q2QI8QxA1wWkoYKoiwkFzR4jtwEAG9gllndLQFThNE+XG4B6VGcCtg3MmUEyMIaIpouYzxq0XUAU'
            'wcUru7hy8QJWDt2Adt6A98nUMpDDc862MKI8qpSFlzj0WFlZxoEDB/Dww4+gqvJUUS62PDqqXOR9w/qcTMI2BQkA2FNqHIk+E40N'
            'C4914oTh1KnHtBNh8yT8V7zwxXeOxit/z3l6YT1Z/ocHDq5P2pg0dm32IJUHKBOlXeVtwUiJUUhEEGNCEkXoulxM8HnzkibJIVou'
            'kOYVaWYISRB6saZpKISw72EWhOWkiqQ2qHvnCQMaFLMNtF85ZGYYFCPHmEwmcDCMliaovMuG5wYxpGHNWgoRbUxo2oA+BEznDWbz'
            'Fl2ICCK4dPEyvuwbvhO3H38eprs7Q5cwr3ITEWJiE9XrBm4xjA8NLQXH+Kl/9wq85a1vwdJkCQBBNBe5mRfMHxv4rtcEmVQSnPMJ'
            'hNpMfv7K1SvfPjiXVDzgk8Tots+c4Q0AdOqUYOGxBrzpZS9eriUcFKnXapAXdOHiXvjwube8d/6CL3nuMwA3RkWefLU6GddHGXSz'
            'Y38HObqNiO+sRvUz19dWK1fV6JJYE0NQEw8eKMScJfUocydhakM9hRBCQt910KgWJWUNIxkCvkGXxcwQ+4AYsnR+CIK2D+hjMkhm'
            'u9jQe4uSF4HqoBy2mBZw3sN7PxjfsM0JgxLuKDsNch4KQkyCkLrMS3WZidL1AUkMbddjOp9j1gc0XY++jzlEBGM6n2Pn8sW8Wjum'
            'fS3PQYzKJAVSzb3HxVAuc6asqRGWlya47dbb8La33Td4vjSMV+VZQOJh7+LwqeoQNeSQVoZp+qfW+sNPawM0M7r39GlHW1sJg4Lz'
            'G77zH43GR+98zqiafIFz7vOYcCeIbuJqdAA1LTExmY10qUoXnvlVX7wH5juYnQODq6ri8WiEuq7hRzXgXG5wA9anFK1rYSasKt5s'
            'mCgggJLAOBsdnCdTQ4wJ7XSGvutyAUVB5BhuNMrSiCmi75rcOE8J3byFqGYZelUIMjWMhl0TZoPxJYE6NlIQce7PLWr6XdflvGoY'
            '9RFVeOfgYt4W7CsPi8lS21EcZv6cy1MVfUhoQvZ8bUjoYqI+JFvoOfm6RlDBXzxwP45/fouU4nApyPD+ZPDQCpHMHzPss2GgRui6'
            'Hk972tPgfa7CWo4398MTFVm0JTK7ZqDiLNgyZAZiKqpoTwbDw/Y2E5EASGe+53smtz598g88+xcSu7vU6Nmry0tUVT7vZ2eCQqEh'
            '5OkJx45gNzmmmxKzkqkRs4JMUNem4wnCoqyvxmAiicHtT2gPec41+QQFJQVYoS4fqPnOLpq9KRRu0H9RSFIEaZFiQN/3aJseoe9h'
            'lPtpWBgbZdaM9xWZ5Z2DuamOxUIXAuXRVM19DNIk6GPMuSAMknIvraorSJfzQpFofdeTSNbkVMveJ4nmEDkJ+iRI2ZhswdMkECTm'
            '4uPOxQ+jmTdo23bga+alNTGGfTk0kcUAsiEsKqOiME1YWVnD6soydnb39r0jDeEnDW2JhREuVqbqYvgxz0KWIsynEmc2NtxgePKG'
            '7/+Wmw+uHXpRPRl//crK2p31ZBmRHGKmE4tylrBnNiIjcuMRkQnMxNQg4p2RJqhEMiWiqiKNkUSGffB5NRZMkplmSSkMN/eCA5nH'
            'izInEyCEtkM3n+cwkR1SSJA+Qix7t67rEfqAPmUP5bwDUd62RC5LSgw1CRLL7Yck2aMmHRSwwdBcWYEEoSQJMQSkoUCzGG8iInRt'
            'ro5qSpayt7Jk11YfmRliSkg6LH5ZNPwHOX+VnL+aAV0SXLr4MJr5HiQp+r6/vlZsKSbKExKLgVoAgxSdqaBtI3zlcfjwIVy+ehVm'
            'uc3Bw2gTEdk1qachL97ngg5iUU+tLsSnlwEu5vBe/b1fe+TZNz/zn9eTlW89uH7wUBcVPTgmZlNTDl3LKQZPZPBkqCo27wh+XBOp'
            'QqPkw9t2ROxMRKCeCTFkCYeYcu9rKKFLDGQYxI2GUn/O9yx7NzMkM0jfo53N0c7mw3ZbQ9d0CH1EFEEwRdd1UAUUhqr2cPUo53CO'
            'Bw+Wb/yUBDF2+57RLOdwhmwwymSkoBATuhiQJBcuRPfFh2EKdCEipoQsdpYNKVne+ZVXn+XGeFRdVFhNREGAMQFMef5dFWRgXL18'
            'GVcvX0A9OUCiiSTGvPuQAYBNkhCx7lPN3FAgypVcQVXVuOGGG3D+/J+iGo32Nw/nHuLClHPvcxjBvbZFiRg6SOMXA/wUGd/v/evv'
            '/dK1ycorl/z4lmnT4kPTWYhBOIbk4H1W9EoJSSNGS2NMlsfDwQXiNII0wo/GMHjMLz8CV43hV9YQu4CszuzgJxMgycDhpLwixOW9'
            'EmqDCNJCqiHk9dT9bIbQdgghQYzQzvYQRU1BZJzznxADDITJ8gTVeJTzupSgRoghoG3bnEcNYW3fhywr6D2883DIUwe57UAkKaGL'
            '2bhVcu/MkPuAi8qrDq2LXm0YwdA8JjRkVUkEQdRgQqpgM3OLoVjvhgFZ2JBbOvTtHB/6iwf0lmc+xyTGYRyJQZrbEUkSSAnMw9QE'
            'DTOPQ2hsajh08HDWgzHL40fDq1EhWux6wUInZlB7ylzTrNBfDPCJzvk2N5m2tuTsv/7+v3twffU3oDZ6+MIH+/l05pt58skYfYgQ'
            'M4wmEywdOIBqUkE0oZvvQVJNTs0YZBI7qiYJEIG6EWaXL1Eteb+fOYLzFeLQGFYRuLqGr/IyTpEEIgeNEZoiUt9DRdE3Dbp5h7aL'
            'CHEYVjWDMtOi2R1jhK8qTFaWUY9HSCqYz1t0XYc+9IgGpGFjr3cecRAuqn3eZ5FU80bf4VB2fRym3bPnUgBRDEY534tiiKJDX940'
            'SGIVdaaSi7CL9dv7khJ5l70ZWoNNo+osiLQEzERECDQBsBRSWrn4yINHn3b7nW7eNAZTct4PAk8EYjKT/TuKzMxUM9GckC+GA+sH'
            'cGB9DTt70yFKpeyS83OnxUT/QuD3+s1KZqbFAJ/ovt7p0/Y67BwYV/5XUPlRmKyH8fKxyvcJa84jKNAFwe6FR9BeegCu2YXKBKkH'
            'fM3gtoF3FRwRLEU0sy4zGWuPSBUu3P9+HLzpRigMfgKkvRnI1yAmUB/gHCEO+wdBjNB30KRIXUAOAWNmrMTsgTIDJksP9ilaUsXq'
            '2jqNV1dAVYVZ2+HqzlWEEBBSQhciFpsVRksT9H0Pg2F5aXlovts12XYzJAPCUGQxIiTN1UglQlLNxqcqkiID8KKaPWWSDqCGgMYI'
            'jRkuEPSDarhfjd5DsD9Piodj8nsrN7XNm954f7y+nbO5uVn/9mt/ZnTw8JEXTnevviYXbBOFvhukERf6hINEIsGSCKmaOXb7315a'
            'XsL6+houX7m6UPG2PMB7ncz9gh2DYfPUkBOqFS7oE4p7NzfdC4jS//PSu/8Hr6M7Hrm0F9J81/NoDDFBEkVMuUBAkyWMnnYLdu5/'
            'h01Gy1RNRqCOYMxWjUZwOU+z2EWMJ0tw0UMN2J02pJf24KoKNu2zXAJRLtunYWlIPuhmKZGoIMXcYO9jGpZw7h8daEp5zg8G5yta'
            'WV1GPR6j6QP2Ll7ErO3QhR4yVB/9qEIKEfV4jCiKtu2wsr6GZIYUs7IZO95XTRNRCAaj01woCjEB7ND2USRFgqEKSdHH+Ecq6f8W'
            '5jfD4YNGbm9CfftQv9Ldd9998aM++Hf9N4QO29raCgDCVx4+9oa2bS4T+8Oh64SIiNkP1eE8ngTab8KbqMKzRxKFaC5IHT58CPf/'
            '+QN5/nDR+xuk+Bfk7NyM16EtkaNSJr4mQVMM8BMG/XUf4MUT5w0A+nn3gsvGtjuNYFSmfUNBBNIn9EEQ1bB09AjMAU1IFLorqG3V'
            'wExKDj4JSBSxawAx1KpZCHY0hltexpVLl1Gvr0M0H+4svz40hocbPQ3jMSkliBpEhnEZ5JVgWT8l5XfmXC7U1DU6Sdi9fAnzrsN8'
            '1qCPuQGtpqhHtYW+h/ceo6UxZjt75EcjKAh70zlcVcETw0Ia9grmbbtqOjSvGV3XGYg1ZGZO1ccEBX5TBT/xm29913/9WJ/Dxgb4'
            'woWTBADHjp217e1H77HBo/fa0MbGBr/kJS/Z3fyhl/6JY/mSEKMC5kBhIF5fIwfkFkP+qAMwtEaylOLBAwcwGo1Mhga7qtL+wdg3'
            'vjxzsf91LiQVMvYTiXPnjhsA7Mxnh1oF7ewE+FEN62BigAShEPPktjZ7EDF0xtB2jlFVgSufc5AUQUqU+gg2xc6sQQyCpdUlW1pa'
            'xlwUbdOj69osEJtS3po7yKgPVXDqUzRdtCcAqBoltX2tTucY3jsjANob4u4uQozah5iLJAQyNUpR4OsKbduAmTFaWsLu5augqgI5'
            'j73dKcAMR7lFEPtuULZWhJgsSTIGa1ChlGLFzK7rA0Tt9wLhR974B+/4rcUzPHnypD927Kwd3x5Uwa8zru1tyMch72DHjx8nAGjn'
            '8/9Sj0ZfEkKwLDfP++2CNNDRdDGiNFxouaBD6ENnS0sTrK4s4crOXhYLt0XV8/phQtvXHt1fJ6/7OSAVA3xMqd1fDyfOnycA2J01'
            'HxobWRsElBIRI3uhlIsN0YA4I6gx5k2Etj2WXAVfeyJiUBQQO0iKefMPeagjdH1EjHuYzqbQtkcfIrzPu/NcVcE5BphMRS1vkk4m'
            'Q7GAmElMWcX2R3IWG9AJBhVly4rOTgbGh2TJdSGGaq/K3sNVI7p65SpcXdO4Zkx394i9AxuZxIQ+dSZqMAsQA8UYq0URJeY97Vei'
            'hN+B4T++/i3v/A1gIacP2t6GPM56OgoAXdf8Zh/DD5uRU01Qsf12gaQENbPMihEzM2PHRpQlg0PXEQNYXVvhCxcvYzQeAZSX/y4q'
            'pQupQlw3Lzj86tKG+FRgOp//mjr/jfNgRi4L4S12HIRk1AdBYwKuazQxIXUdejGqxiM47+F8hapSOCL0fYfJZBmAWjPvkWKyvm9B'
            'owmCKKKyphSNRM05ZjBVCxaMDJJ6NvTr9peT5K/NslwnYIgg6xWYmuqHk2hnREcAutGga05dVdUV4Bz6vs1itSBMp7MsWZEAlbDv'
            'PRb/RBGEJDMjut9M30rs7u2Jz77pzX/84cWz2tiA29qGYPvx/xyGWU46eOzYuy8+/KE/9q7+OyoSUoo8FD1J86XkVGXoIhrMhpEn'
            'U8QQABiOHj6c3v/AX2QK2iLuzN33faFeyjODdG0pGuyplAN+WkxDbG5uMra20P3Tv/e6Sb30lV0nkTyrDaM9IoauTxSSwo1r9LGn'
            'NL+EmglVNYGrK/K1zyEpAAkRta/Qz6fYnc6Nq9pSSsajEQnB85DEkGOEpBC1XYM9aGQPmNn7YPgLU7qgqleIbVfyJi5jImOz5Bxr'
            'SBQcWVPrfPrqP7x/bxEKHtLZUagcI/JH1eRWielZVe1vMeA2U10G8QoT+eF0daa6J2YXiOwvAHp/MrwP4He/4c1//JfXH8KNjQ0H'
            'AE+EPP/myZN+6+zZ9M3f8PX/fDJZelnX9Rj2IyEtuKGmnSbZMdMPA/ZBVfugGT6QRB5xzA++69y5L7x8+fKPpiQxpsT7xJnFGmpa'
            'HOBh6y6QABvB9J4uhH+G3A+UYoBPUCuCAHzz3332ymT94M9ptK8lIwfn95dSxiSIfciNagCqOdfzlYer8mKTapg+YFXAFDEKptMZ'
            'qqVJbhQTIwG9Ej6gsD+pnHuzJXtnVLwPt7zj4ZwvfXILTxvHj9cX5nPG7bcDQPpY4eN1RqdPsEcgAPaiF20cjS3eKGK1iJw30DkA'
            '71WiD3ovj6hWl7a3t3c/ys+oHfP7JuPJLSIqaso07JbPncHM584L1swMiAAmMP3fuxDuxlNkHOnTaR5w/wB/45d+3t9C1OelIDcY'
            '0Qgi6ya6QsQj590KMa+EmGpVZWPygI0cY0zEYyZMPNPIVHwMYn0Ml31VPQDm86b8Zu/t7WlX33/dxtzrPDH43ntP7pOBjx07ZsA2'
            'jh//CId/a/+PR1URh59D589v0IULF2jxcz6GEdHmJmjxe48dO2YfYefhpwzPe97zqvvuu0/wMV7P5uYm33vvvfuv/9y5c+78+fNh'
            'XNffV1XVT6SkQU0dUZ4tzuktOQL8fii6aMbDfrbruu8oHvBT9H42N0FbWx//4Tt5Eh64zR/AgXGNepzazntmO3jklqu/+PrXNx/J'
            'u1y4cIGuO/D2BHkZ+kQLVp/KS/H65wUAwy7Fj/bMFu9xfWV5+ZyqHRMRYmaXQ1Fb6MU8RER/CsK7ALxPlf+squhds9ns4sfTyioG'
            '+LjnhI/2RNe8EXD8+LZhCzg9jJP9dQ7xJsD7G3OzKpvhKZLkP4nO2Mf7vDyAdOjAoR8MMfxIjKFhdu9jwn2qeBsYb6/b+n272N0p'
            'j/jT46JYJBhkeU01D6psVB7/p+wzp4MH71hfXVr9xtV69dkf5b/jwVj9EHZSOdgFBZ88uOvCyye6uFRQ8BnpCT1KNFJQUFBQUFBQ'
            'UFBQUFBQ8HEn1AUFBQUFBQUFBQUFBQUFBQWfcShFkSfX8y+0qs8w8GfYAS8oKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgo'
            'KCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgo'
            'KCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoeALw/wHE'
            'AmFCrnTS5gAAAABJRU5ErkJggg=='
        ),
        (
            'iVBORw0KGgoAAAANSUhEUgAAAOAAAACgCAYAAAAVdWCNAAA6bUlEQVR42u29ebxlWVUm+K219z7nDm+KeBkROSeQgkgiIghaKmai'
            'ZVcXDlXd7QuHqm7EAZRCaaUUu7T75bPpLlu0bNuqtrDp1p+2WsZTqy0pRbAlo0UcSgTRDEZJkpwjMiJexHt3OGfvtVb/sfe9ESSg'
            'kAw57e/3Y4jIm2+496y91vrWt74NVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRU'
            'VFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFRUVFR8YqDyn8fb70OP'
            '0Pf+eO8rPYZ+j0f0w6u/b4bVs+kz8j7bw/xsnhCfB9dnpeJREHwf67VPiGzonsAPiT3MD/gJVyY9zAC0T2Mg1wCsWD4Q9Bgvj8jM'
            'CADfdvIkdj5zh9unemDVQ67i4wbgYw7b29tsJ0581IFrJ0648vf0GXrPPpX3rQZhxWO/BD1xYstdHohvf/3/cvU7fvY11/zOT39P'
            '+1HBmLPjo7WnfFw3zI/1fu6x1uN8xmFmhFtvJdrZ0f/3ta+6YcOH72odf007Gl0XRiOQ6YMg/jPy7peuP/7K31v8TnbihMPW7Ua0'
            'o0/Az7cGYMWnJ+sdP74rAPAHO6/43mHw24dXx4fJObgQzHmP4JkGgyGSKhLsz0H8ujkGuzcef9mFxdd5y1u2/Zkzp2xr64QSUR3V'
            '1ACs+FuzHkC3bd/sXrhzMr3hx19+ZTu1n2qJv8kHbysrK/1gOGBiR5oS2JGx9wqAB00IoW0wS+kuNf41gv7qk77p+//iozLq7i7f'
            'duR2OnPmJtva2qpBWQOwYpn1trbc8d2c9W57zSv/YZL4byWm69n7bnVlxbWDluAdaZ8w8s4GK2M0q2N4YqiY9bEzg4V2ZYyDeacG'
            'vAPAb2tKvz+b0e1f+JLv2/tYZe5tt97qztx0yraO7ypVQUMNwCdc1jPQbbduuxfu7KRffNWrxlcfjj+qkr6vF6N2MOjacRsAAjqx'
            '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'
            'qG1M5Z/8xzf97olnPWvo7r//jemywPpkTlB6mKcubW1t8enTp+mWkyf107BYupyj1aCrJMzf3gNmx10sbonFZSMDs8wWXmJJFxmx'
            'jC1MEJqAQ4cOISXBbD5dLqtiwXyWUUFWz6D4aGrxDzVj5pAO5tMA+6OTJ0+mW27Z1p/5mTc+3AB4uA/6ctB8chmQ4EXmvJw9XDAm'
            'APBQZvJjzdEqagb8WzPgYDB4PYG+HYYOhJBD0QzL9duH/qR0OSuKKzYP21d95VfS+vqhJVHDjpdETN74cSXbLR3X4Jy3EBphR02K'
            '3Vt/7Cde+4LHsrFrRc2AD5OEMb/IalRMc5f8KGhJYVnZ51vY5uU7ENQ21tdAUJtOJ+C85a75RiG38B6kMjynxfiBAKgKEcE8HGaz'
            '6e8AwK3b2w47OzVzVDxxApDyfdHLLfClXwRwycNz4Yq93ILP1Z7zjI21VcymE8euR9O2ed7GDFZeKl/yug6Ld6zErDAjdowYe8dM'
            'c1L99WXUV1Q8kQIQgOatHRMiJpDx4oq+Bf1yGS2zyJowGIIPuP2976P9yfSbnvr0G98XJ+kaH/hJMH4KEa5n5usIOGbAYWZeNQvO'
            'l7sjRBnDAaObd7/1cz//8+9/PN03XlED8BPPgEaemZwRRpdukDU1s1Ru78pXPyw1KLpgOwSEcHF//83vuv32X3vX7bcDwDse+vW/'
            '+qu/eryx0W661F6VklxHwOcY0ucwhRtj312h2v9PAOjUqVNUH4OKJxIJQwBstWmeKsxfAqJnm+ELiPA0AFcD5ABcdrUzJQBqZkTE'
            'zAQlohAl/cP5fP57N910U7jpppvkcinVJ0DBP6bdlCtqAH4msDYajZ7siW5KIs83s+ca6OlMdMVy/wyUmIiJ6T8dTCZfVv7y45WP'
            'tL29vcxwi6XOEydOKOVWswZhxRM6ABmXrsjWjxVI4/H4KBI+35x9GcxuMbPneu/XBsPhN5w5c+Y3UEYaDzcL14+/ouIjg4JLX+o/'
            '1uGw1rY3rq6ufh0eYTOpiorHYwn6twXlwtalZq2Kike4bHX1baiHekVFRQ3AioqKioqKioqKioqKioqKioqKioqKioqKioqKioqK'
            'ioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqK'
            'ioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKioqKiopHN/5/3YwUuU28'
            'KsIAAAAASUVORK5CYII='
        ),
        (
            'iVBORw0KGgoAAAANSUhEUgAAAOAAAACgCAYAAAAVdWCNAAA61UlEQVR42u29e7SlWVUf+ptzre/79j6POqcep/oN3XSLUA3yaMHH'
            'xdENgYRcRePjlDcaNRivxBuNMUQTb4inT4IOwVcgaoSLIZiRmFEHx71XEa5PugQV0FZprQoBoaG76aaqu6rOa+/vsdac8/6x1t5V'
            '3bEDdGM3dK/fGDW669TZe5+9zze/Oedv/uZvAQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUF'
            'BQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFnx50'
            'yZ/P9nEPfY6/6t8+39/HF8Lv5kl3QT5Z36s9gscZCh6La+9J8znzkyjrPdJfsD1Jb1gFjwH8k+i92qN8bAm+zyyj2aP4fEuF8STJ'
            'gI/0cfTXcFegjY0NNrMnQg9EpVIo+Fz0ufTXTAyQnTjh7MQJ9z8E5IkTbmNjg0sAFjxZg++vrwY2o4cG3Tvf8H3Nn/771151+1te'
            'd+WlgXfixLp7klQa5QJ9gr8/e/wDb4OxdSPR8eMy+7nuOvGGv2VRvg2mLzTiI2E6RT+d3t2L/vp2DL/wN37wpz5hGxuMW281IrIv'
            'oGvJnmy/3xKAn2cwM9raOs5ra8foxS/ejLOvf/TEm1ZG6NZh+ioP+lLPjK5rEaKaxAgJgUwE5/cm59sQN1+y8bNvnGXD48e3pHyy'
            'JQMW/JXBtsVra6folvtvNKyv60Mz1sf/608/38B/l0m/eez9NaEf0A0hAFCNkVWM2HuYinVtp/v7+3UMkXrT/9ov0A98zQ/9/Kfe'
            'vXGzv2XzpFBhCksAPqkDDqCtE+u8duoY3XLrrfJXlYd/+tafWR2P7Ub2/qUAXkHA85ZGDff7ExAo1FVD7IiiKYa9Cbr9CaZRiGsP'
            'RLG+621vf180xsZV/i7vqn94y2ve8C4AOLG+7o5vlWxYAvBJF3QneG3t1INKSgD4k1/80TVX+2fUjp9X1c1zFHgGmK5zzl2x2NQI'
            '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'
        ),
    )

    # Shoulder/elbow motion is solved in 3D, then projected. A planar IK
    # elbow has only two possible positions and produced the conspicuous
    # right-angle bends. The swivel plane here stays mostly in depth.
    ARM_LENGTHS = (340.0, 240.0)
    ARM_SHOULDERS = ((-60.0, 80.0, 190.0), (960.0, 80.0, 190.0))
    OPEN_HAND_CONTACT = (164, 67)
    PINCH_HAND_CONTACT = (175, 79)

    @classmethod
    def hand_rig(cls, side, contact, grip=0, opening=0):
        anchor = cls.project(*contact)
        grip, opening = (max(0., min(1., value)) for value in (grip, opening))
        upper, fore = cls.ARM_LENGTHS
        sx, sy, sz = cls.ARM_SHOULDERS[0]
        local_anchor = (anchor[0] if side == 0 else cls.WIDTH-anchor[0], anchor[1])
        reach, wrist_y = 99+11*grip, 6-12*grip
        wrist_depth = .28*(contact[1]-cls.DEPTH)

        def solve(wrist):
            delta = (wrist[0]-sx, wrist[1]-sy, wrist[2]-sz)
            distance = math.sqrt(sum(v*v for v in delta))
            direction = tuple(v/max(.001, distance) for v in delta)
            safe = max(abs(upper-fore)+.001, min(upper+fore-.001, distance))
            along = (upper*upper-fore*fore+safe*safe)/(2*safe)
            radius = math.sqrt(max(0., upper*upper-along*along))
            screen_length = max(.001, math.hypot(delta[0], delta[1]))
            normal = (-delta[1]/screen_length, delta[0]/screen_length, 0.)
            depth_axis = (direction[1]*normal[2]-direction[2]*normal[1],
                          direction[2]*normal[0]-direction[0]*normal[2],
                          direction[0]*normal[1]-direction[1]*normal[0])
            # Ten percent of the elbow swivel is visible in the image; the
            # rest bends away from the viewer. No branch switch or elbow pop.
            bend = tuple(.10*a-math.sqrt(.99)*b for a, b in zip(normal, depth_axis))
            return tuple(a+b*along+c*radius for a, b, c in
                         zip((sx, sy, sz), direction, bend))

        angle = 0.
        for _ in range(10):
            co, si = math.cos(angle), math.sin(angle)
            wrist = (local_anchor[0]-reach*co-wrist_y*si,
                     local_anchor[1]-reach*si+wrist_y*co, wrist_depth)
            elbow = solve(wrist)
            fore_angle = math.atan2(wrist[1]-elbow[1], wrist[0]-elbow[0])
            # Independent wrist flexion; use a soft limit instead of suddenly
            # hitting the previous +/-31 degree clamp.
            desired = .82*fore_angle-.055*opening
            angle = .45*math.tanh(desired/.45)
        co, si = math.cos(angle), math.sin(angle)
        wrist = (local_anchor[0]-reach*co-wrist_y*si,
                 local_anchor[1]-reach*si+wrist_y*co, wrist_depth)
        elbow = solve(wrist)
        def mirror(point):
            return (point[0] if side == 0 else cls.WIDTH-point[0], point[1], point[2])
        joints = tuple(mirror(p) for p in ((sx, sy, sz), elbow, wrist))
        return dict(anchor=anchor, shoulder=joints[0][:2], elbow=joints[1][:2],
                    wrist=joints[2][:2], joints_3d=joints,
                    angle=angle if side == 0 else -angle, side=side,
                    grip=grip, opening=opening)

    @classmethod
    def arm_polygons(cls, rig):
        """One tailored sleeve outline with a rounded elbow and fixed widths."""
        shoulder, elbow, wrist = (rig[k] for k in ('shoulder', 'elbow', 'wrist'))
        def normal(start, end):
            dx, dy = end[0]-start[0], end[1]-start[1]
            length = max(.001, math.hypot(dx, dy))
            return (-dy/length, dx/length)
        n1, n2 = normal(shoulder, elbow), normal(elbow, wrist)
        n = (n1[0]+n2[0], n1[1]+n2[1])
        norm = max(.001, math.hypot(*n))
        n = (n[0]/norm, n[1]/norm)
        def offset(point, axis, width):
            return (point[0]+axis[0]*width, point[1]+axis[1]*width)
        def mix(a, b, t):
            return tuple(x+(y-x)*t for x, y in zip(a, b))
        tangent = (wrist[0]-shoulder[0], wrist[1]-shoulder[1])
        tangent_length = max(.001, math.hypot(*tangent))
        tangent = tuple(v/tangent_length for v in tangent)
        rounding = min(14., math.dist(shoulder, elbow)*.18, math.dist(elbow, wrist)*.18)
        outline = []
        for sign in (1, -1):
            first = offset(shoulder, n1, sign*29)
            bend = offset(elbow, n, sign*25)
            last = offset(wrist, n2, sign*20)
            points = cls._bezier(first, [
                (mix(first, bend, .55), offset(bend, tangent, -rounding), bend),
                (offset(bend, tangent, rounding), mix(bend, last, .60), last)], steps=8)
            outline.extend(points if sign == 1 else reversed(points))
        return (outline,)

    @staticmethod
    def sleeve_details(rig):
        """A quiet seam and short elbow folds, not a long centre-line wire."""
        ex, ey = rig['elbow']
        wx, wy = rig['wrist']
        dx, dy = wx-ex, wy-ey
        length = max(.001, math.hypot(dx, dy))
        nx, ny = -dy/length, dx/length
        seam = [(ex+nx*13, ey+ny*13),
                (wx+nx*13-dx*.06, wy+ny*13-dy*.06)]
        folds = [[(ex+dx*t-nx*10, ey+dy*t-ny*10),
                  (ex+dx*(t+.04)+nx*6, ey+dy*(t+.04)+ny*6)] for t in (.04, .08)]
        return [seam]+folds

    @classmethod
    def holder_rails(cls, shift):
        p = cls.project
        y, end = cls.HOLDER_TRAVEL*shift, cls.LENGTH+cls.SEPARATOR_GAP+10
        near, far, top = y-4, y+cls.DEPTH+10, cls.CARD_H+10
        # An actual U-shaped case: both end panels have a rim to clamp.
        return ([p(-8, far), p(end, far), p(end, far, top), p(-8, far, top)],
                [p(-8, near), p(-8, far), p(-8, far, top), p(-8, near, top)],
                [p(end, near), p(end, far), p(end, far, top), p(end, near, top)])

    @classmethod
    def finger_point(cls, x, y, grip, opening):
        """Local joint motion shared by the raster and Canvas hand paths."""
        pinch = grip*(1-opening)
        upper = y < 74
        pivot = (134., 54.) if upper else (132., 81.)
        angle = (.28*pinch-.16*opening) if upper else (-.12*pinch+.20*opening)
        weight = cls.ease((x-128)/16)
        xx, yy = x-pivot[0], y-pivot[1]
        co, si = math.cos(angle), math.sin(angle)
        return (x+(xx*co-yy*si-xx)*weight,
                y+(xx*si+yy*co-yy)*weight)

    def _finger_image(self, grip, opening):
        """Move the index and thumb as separate pieces of the same hand.

        Overlapping joint roots stay under the palm. Rigid finger rotations
        preserve rounded fingertips and skin detail; no photo cross-fade or
        inverse warp can leave a floating fingertip or a pointed skin tear.
        """
        key = (round(grip*24), round(opening*20))
        if key not in self._finger_image_cache:
            if self._hand_images is None:
                self._hand_images = self._make_hand_images()
            source = self._hand_images[0]
            grip, opening = key[0]/24, key[1]/20
            if not key[0] and not key[1]:
                posed = source
            else:
                if self._finger_parts is None:
                    parts = []
                    for box in ((0, 0, 140, 160), (128, 0, 224, 74), (128, 74, 224, 160)):
                        mask = Image.new('L', source.size)
                        ImageDraw.Draw(mask).rectangle(box, fill=255)
                        part = source.copy()
                        part.putalpha(ImageChops.multiply(source.getchannel('A'), mask))
                        parts.append(part)
                    self._finger_parts = tuple(parts)
                palm, index, thumb = self._finger_parts
                pinch = grip*(1-opening)
                resample = getattr(Image, 'Resampling', Image)
                index = index.rotate(-math.degrees(.28*pinch-.16*opening),
                                     resample=resample.BICUBIC, center=(134, 54))
                thumb = thumb.rotate(-math.degrees(-.12*pinch+.20*opening),
                                     resample=resample.BICUBIC, center=(132, 81))
                posed = Image.new('RGBA', source.size)
                posed.alpha_composite(index)
                posed.alpha_composite(thumb)
                posed.alpha_composite(palm)
            if len(self._finger_image_cache) >= 96:
                self._finger_image_cache.pop(next(iter(self._finger_image_cache)))
            self._finger_image_cache[key] = posed
        return self._finger_image_cache[key]

    def _hand_sprite(self, rig, scale):
        """Articulated fingers, a rigid palm, and an independently flexing wrist."""
        angle = round(math.degrees(rig['angle'])*2)/2
        amount, opened = round(rig['grip']*24), round(rig['opening']*20)
        key = (rig['side'], angle, amount, opened, scale)
        if key not in self._hand_sprite_cache:
            resample = getattr(Image, 'Resampling', Image)
            source = self._finger_image(amount/24, opened/20)
            cx = self.OPEN_HAND_CONTACT[0]+(self.PINCH_HAND_CONTACT[0]-self.OPEN_HAND_CONTACT[0])*amount/24
            cy = self.OPEN_HAND_CONTACT[1]+(self.PINCH_HAND_CONTACT[1]-self.OPEN_HAND_CONTACT[1])*amount/24
            if rig['side']:
                source = source.transpose(getattr(Image, 'Transpose', Image).FLIP_LEFT_RIGHT)
                cx = source.width-1-cx
            layer = Image.new('RGBA', (360, 360))
            layer.alpha_composite(source, (round(180-cx), round(180-cy)))
            sprite = layer.rotate(-angle, resample=resample.BICUBIC)
            bounds = sprite.getbbox()
            sprite = sprite.crop(bounds)
            sprite = sprite.resize((round(sprite.width*scale), round(sprite.height*scale)),
                                   resample.LANCZOS)
            offset = ((bounds[0]-180)*scale, (bounds[1]-180)*scale)
            if len(self._hand_sprite_cache) >= 160:
                self._hand_sprite_cache.pop(next(iter(self._hand_sprite_cache)))
            self._hand_sprite_cache[key] = (sprite, offset)
        return self._hand_sprite_cache[key]

    @classmethod
    def fallback_hand(cls, rig):
        """Fixed local hand silhouette for installations without Pillow."""
        shape = cls._bezier((-111, -16), [
            ((-88, -16), (-72, -34), (-49, -33)),
            ((-24, -34), (12, -24), (17, -6)),
            ((18, -1), (10, 1), (7, -5)),
            ((-1, -18), (-29, -17), (-38, -13)),
            ((-44, -9), (-44, 5), (-35, 9)),
            ((-21, 13), (-2, 7), (1, 12)),
            ((8, 26), (-33, 27), (-48, 21)),
            ((-70, 14), (-93, 22), (-111, 20))])
        co, si = math.cos(rig['angle']), math.sin(rig['angle'])
        direction = 1 if rig['side'] == 0 else -1
        points = []
        for x, y in shape:
            x, y = cls.finger_point(x+164, y+67, rig['grip'], rig['opening'])
            x -= 164+11*rig['grip']
            y -= 67+12*rig['grip']
            points.append((rig['anchor'][0]+direction*x*co-y*si,
                           rig['anchor'][1]+direction*x*si+y*co))
        return points

    def _make_hand_images(self):
        """Load the two natural grip poses embedded in this standalone file."""
        import base64
        from io import BytesIO
        return tuple(Image.open(BytesIO(base64.b64decode(data))).convert('RGBA')
                     for data in self._HAND_PNGS)

    @classmethod
    def separator_quads(cls, x, y, z, packets):
        """Clip a separator against every packet along the actual viewing ray.

        Projecting a box onto this card's plane accounts for packets in front
        of the card as well as the packet containing it. Painting order alone
        cannot hide the inserted area of an upright card reliably.
        """
        def cross(a, b, p):
            return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
        def hull(points):
            points = sorted(set(points))
            lower, upper = [], []
            for point in points:
                while len(lower) > 1 and cross(lower[-2], lower[-1], point) <= 1e-8:
                    lower.pop()
                lower.append(point)
            for point in reversed(points):
                while len(upper) > 1 and cross(upper[-2], upper[-1], point) <= 1e-8:
                    upper.pop()
                upper.append(point)
            return lower[:-1]+upper[:-1]
        def half_plane(points, a, b, inside):
            output = []
            if not points:
                return output
            previous = points[-1]
            prev_side = cross(a, b, previous)
            prev_keep = prev_side >= -1e-8 if inside else prev_side <= 1e-8
            for point in points:
                side = cross(a, b, point)
                keep = side >= -1e-8 if inside else side <= 1e-8
                if keep != prev_keep:
                    ratio = prev_side/(prev_side-side)
                    output.append(tuple(v+(w-v)*ratio for v, w in zip(previous, point)))
                if keep:
                    output.append(point)
                previous, prev_side, prev_keep = point, side, keep
            return output
        def area(points):
            return abs(sum(a[0]*b[1]-b[0]*a[1]
                           for a, b in zip(points, points[1:]+points[:1])))*.5

        visible = [[(y, z), (y+cls.DEPTH, z),
                    (y+cls.DEPTH, z+cls.CARD_H+8), (y, z+cls.CARD_H+8)]]
        for px, py, length, pz in packets:
            if px > x+1e-8:
                continue
            projected = []
            for xx in (px, min(px+length, x)):
                distance = (x-xx)/.52
                for yy in (py, py+cls.DEPTH):
                    for zz in (pz, pz+cls.CARD_H):
                        projected.append((yy+distance, zz-.32*distance))
            occluder = hull(projected)
            remaining = []
            for polygon in visible:
                inner = polygon
                for start, end in zip(occluder, occluder[1:]+occluder[:1]):
                    outer = half_plane(inner, start, end, False)
                    if len(outer) >= 3 and area(outer) > 1e-6:
                        remaining.append(outer)
                    inner = half_plane(inner, start, end, True)
                    if len(inner) < 3 or area(inner) <= 1e-6:
                        break
            visible = remaining
        return [[cls.project(x, yy, zz) for yy, zz in polygon] for polygon in visible]

    @classmethod
    def cut_limits(cls):
        return cls.LENGTH*cls.CUT_MIN/cls.CARD_COUNT, cls.LENGTH*cls.CUT_MAX/cls.CARD_COUNT

    @staticmethod
    def contains_point(polygon, x, y):
        signs = [(b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])
                 for a, b in zip(polygon, polygon[1:]+polygon[:1])]
        return bool(signs) and (min(signs) >= -1e-6 or max(signs) <= 1e-6)

    @classmethod
    def top_cut_position(cls, screen_x, screen_y):
        """Invert the same projection used to draw the closed deck's top."""
        depth = (cls.ORIGIN_Y-cls.CARD_H-screen_y)/.32
        world_x = screen_x-cls.ORIGIN_X+.52*depth
        low, high = cls.cut_limits()
        if not -1e-7 <= depth <= cls.DEPTH+1e-7 or not low-1e-7 <= world_x <= high+1e-7:
            return None
        return max(cls.CUT_MIN, min(cls.CUT_MAX, round(world_x/cls.LENGTH*cls.CARD_COUNT)))

    def render(self, split, a_x=0, a_z=0, b_x=None, b_z=0,
               marker_x=None, marker_y=0, marker_raise=32, hands=True,
               a_y=0, b_y=0, black_x=None, black_y=0, black_z=0,
               holder_shift=0, left_hand=None, right_hand=None,
               left_grip=0, right_grip=0, left_open=0, right_open=0):
        if Image is None or ImageDraw is None:
            return None
        scale = 1.25
        size = (int(self.WIDTH*scale), int(self.HEIGHT*scale))
        resample = getattr(Image, 'Resampling', Image)
        if self._background is None:
            self._background = Image.new('RGBA', size, '#0b4038')
            glow = Image.new('RGBA', (300, 154))
            gd = ImageDraw.Draw(glow)
            gd.ellipse((25, 35, 280, 147), fill=(29, 102, 75, 72))
            glow = glow.filter(ImageFilter.GaussianBlur(18)).resize(size, resample.BILINEAR)
            self._background.alpha_composite(glow)
        image = self._background.copy()
        draw = ImageDraw.Draw(image)
        b_x = split if b_x is None else b_x
        marker_x = split if marker_x is None else marker_x
        black_x = self.LENGTH+2 if black_x is None else black_x
        parts = ((a_x, a_y, split, a_z), (b_x, b_y, self.LENGTH-split, b_z))
        p = self.project
        xy = lambda point: tuple(v*scale for v in point)

        def poly(points, fill, outline=None, width=1):
            points = [xy(q) for q in points]
            draw.polygon(points, fill=fill)
            if outline:
                draw.line(points+[points[0]], fill=outline, width=max(1, round(width*scale)))

        def line(points, fill, width=1):
            draw.line([xy(q) for q in points], fill=fill, width=max(1, round(width*scale)))

        # Contact shadows follow the footprint, not a huge oval under a flying box.
        shadow = Image.new('RGBA', (self.WIDTH//2, self.HEIGHT//2))
        sd = ImageDraw.Draw(shadow)
        for x, y, length, z in ((a_x, a_y, split, a_z),
                                (b_x, b_y, self.LENGTH-split, b_z)):
            footprint = [p(x, y), p(x+length, y), p(x+length, y+self.DEPTH), p(x, y+self.DEPTH)]
            sd.polygon([((px+3)/2, (py+6)/2) for px, py in footprint], fill=(0, 20, 16, 95))
        image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)).resize(size, resample.BILINEAR))

        # The player's yellow tab never drives either dealer hand.
        left_world = left_hand or self.holder_contact(holder_shift, 0)
        right_world = right_hand or self.holder_contact(holder_shift, 1)
        rigs = [self.hand_rig(side, world, grip, opening) for side, world, grip, opening in
                ((0, left_world, left_grip, left_open), (1, right_world, right_grip, right_open))]

        # Clear, open-front holder: the far rail and rear plate slide away
        # sideways before cutting, then return around the squared B+A stack.
        rails = self.holder_rails(holder_shift)
        glass = Image.new('RGBA', size)
        gd = ImageDraw.Draw(glass)
        for rail in rails:
            gd.polygon([xy(q) for q in rail], fill=(190, 222, 222, 25))
            gd.line([xy(q) for q in rail+[rail[0]]], fill=(183, 215, 216, 155), width=2)
        image.alpha_composite(glass)

        def packet(x, y, length, z):
            d, h = self.DEPTH, self.CARD_H
            front = [p(x, y, z), p(x+length, y, z), p(x+length, y, z+h), p(x, y, z+h)]
            top = [p(x, y, z+h), p(x+length, y, z+h),
                   p(x+length, y+d, z+h), p(x, y+d, z+h)]
            poly(front, '#dfddcf', '#a9ab9b', .7)
            poly(top, '#f2f0e4', '#c1c4b3', .7)
            # Subtle grouped paper edges avoid the thick pinstripe/moire pattern.
            count = max(5, round(length/3.0))
            for i in range(1, count):
                edge_x = x+length*i/count
                line([p(edge_x, y, z+1), p(edge_x, y, z+h-1)],
                     '#c8c9bb' if i % 4 else '#bfc1b2', .6)
                line([p(edge_x, y, z+h), p(edge_x, y+d, z+h)], '#dedfd0', .6)
            face = [p(x, y+d, z+h), p(x, y, z+h), p(x, y, z), p(x, y+d, z)]
            poly(face, '#fbf7eb', '#d4d3c2', .7)
            inner = [p(x-.1, y+d-3, z+h-3), p(x-.1, y+3, z+h-3),
                     p(x-.1, y+3, z+3), p(x-.1, y+d-3, z+3)]
            self.texture_quad(image, self.back, [xy(q) for q in inner])
            line([p(x, y, z), p(x+length, y, z)], '#959f8d', 1)
            line([p(x, y+d, z+h), p(x+length, y+d, z+h)], '#f9f8ef', 1)

        def separator(x, y, z, yellow=False):
            for corners in self.separator_quads(x, y, z, parts):
                poly(corners, '#eccd42' if yellow else '#1e2124')

        # Occlusion is already resolved geometrically for the separators.
        objects = [(a_y+.32*(a_x+split/2)-a_z*.5,
                    lambda: packet(a_x, a_y, split, a_z)),
                   (b_y+.32*(b_x+(self.LENGTH-split)/2)-b_z*.5,
                    lambda: packet(b_x, b_y, self.LENGTH-split, b_z)),
                   (-1000+.001*(black_y+.32*black_x-black_z*.5),
                    lambda: separator(black_x, black_y, black_z)),
                   (-1000+.001*(marker_y+.32*marker_x-(marker_raise-8)*.5),
                    lambda: separator(marker_x, marker_y, marker_raise-8, True))]
        if hands:
            def paint_hand(index):
                rig = rigs[index]
                # Keep each wrist, cuff and forearm in the same layer. A
                # foreground hand must never be detached from its sleeve by
                # drawing the intervening packet between those two pieces.
                for points in self.arm_polygons(rig):
                    poly(points, '#182a2d', '#263b3c', .7)
                for detail in self.sleeve_details(rig):
                    line(detail, '#213639', .8)
                anchor = rig['anchor']
                sprite, offset = self._hand_sprite(rig, scale)
                pos = (round(anchor[0]*scale+offset[0]), round(anchor[1]*scale+offset[1]))
                image.alpha_composite(sprite, pos)

            for index, world in enumerate((left_world, right_world)):
                # Fingers wrap around the exposed rim/end. Clearance is
                # guaranteed by the path, not by changing depth mid-motion.
                objects.append((-1002-index*.01, lambda index=index: paint_hand(index)))
        for _, paint in sorted(objects, key=lambda entry: entry[0], reverse=True):
            paint()

        return image.resize((self.WIDTH, self.HEIGHT), resample.BICUBIC)



# -----------------------------------------------------------------------------
# Sicbo-style embedded Canvas interface, adapted for Baccarat
# -----------------------------------------------------------------------------
class BaccaratCanvas(tk.Canvas):
    """Keep EZ's board layers ordered and squeeze cards above every other item."""

    def __init__(self, master, game=None, **kwargs):
        self._baccarat_game = master if game is None else game
        super().__init__(master, **kwargs)

    def _keep_ez_cover_layers(self):
        if self._baccarat_game.game_mode == 'ez':
            # Call the base method directly to avoid recursively entering
            # our tag_raise override. A missing tag during redraw is harmless.
            # Fixed border and arrows share one outline layer. Static stakes
            # and all wager/profit/loss/return flights stay above that layer.
            for tag in ('ez_cover_outline', 'bet_chip_dynamic', 'chip_motion'):
                tk.Canvas.tag_raise(self, tag)
        # Every create/raise/lower restores this order, including chip flights
        # and EZ's automatic chip raises. Card images sit above their controls.
        for tag in ('mode_transition_overlay', 'mode_selector', 'banker_selector',
                    'squeeze_selector', 'fixed_selector'):
            tk.Canvas.tag_raise(self, tag)
        for tag in ('squeeze_backdrop', 'squeeze_overlay', 'squeeze_card',
                    'cut_card_notice', 'cut_card_popup'):
            tk.Canvas.tag_raise(self, tag)

    def _create(self, itemType, args, kw):
        item_id = super()._create(itemType, args, kw)
        self._keep_ez_cover_layers()
        return item_id

    def tag_raise(self, tagOrId, aboveThis=None):
        result = super().tag_raise(tagOrId, aboveThis)
        self._keep_ez_cover_layers()
        return result

    lift = tkraise = tag_raise

    def tag_lower(self, tagOrId, belowThis=None):
        result = super().tag_lower(tagOrId, belowThis)
        self._keep_ez_cover_layers()
        return result

    lower = tag_lower


class BubbleBaccaratGame(tk.Frame):
    # Embedded variants of the supplied tiger artwork: no external asset path.
    TIGER_SYMBOL_NORMAL_PNG = (
        'iVBORw0KGgoAAAANSUhEUgAAAFQAAABUCAYAAAAcaxDBAAA6W0lEQVR4nMWdd5hVxf3/X3PK7fdub7C0haUsTZCOFEHFihVjr9Fg'
        '7C2WRBFbRGM3sfeoKBbsQUREQIr0uvRlge19bz9lfn+cuwsqGMzX5DfPc5/dvXvO3Jn3mfnU92eu4P9PU1IvCViHuigN0qVzHQAC'
        'pATRAg2/0LfqXIqdev1Pm/gff1YbiAdOVPV6KVBstY8lxRCB7A6iM6BKKAG01D2i7adAbgMRloJmJOsEcr2KWhpOJsuB6EE+007d'
        '+19v/wtA2ybVvhK9Xgqx1GEo4hSkHAGiixB4nYtFO3QSiTwIDEK0dXzAtVLaUrJPCFaA+FSRYlk4mdx0wG0qP3+Yv3n7bwIqcCZh'
        'pv52e13qJCnE5cDRAoKqItpHYNvStm1s25aYthSKAFUViqoIFEVg2w6yihBIKW3TBsuysW2kqgqhKkJVFFAVp0NbYtm2vUygvCY0'
        '45NIhOrUOP6rwP7mgEoQyCmKosyypAS/nzzbVK8CfieE6H3AirNiCUuCVAChKIrwuVX8XpWMkE7CsGlsMWiNmliWja6pCAFJw0IR'
        'CkGfRkZIx+dVaWw2CMdMGUtY0rRSyCNUr9u5R0qqEfJTxVKejBjGhtTnq/wXRMFvDWibvALI83v1qyxLTlUEeSnh1zYBxbYRg3qn'
        'UdTRS6+uAboX+umU58XnVcgMuUgkLRpbTSpr4/zr+1o++64a07KZNCqXE0bn0rXAS3pIx+9VaWg2iMQtquribCuPsKUsws59Ebmq'
        'tFlKiVQVoQKYtkyCfEuxlMcihrFBUQTWzLNUcfasQyrGX9t+M0DHjUNb+J0wLfsKvXnx3qlTbvrhz3OX1+YFvDqmLU1VEYph2opp'
        'SrwehXjS5ounh3Ps8GyicQtVFWip7W3ZEiFAUxVQwEjYlJaFMS1JSVEAt0dz9rSz5VFUgZQS05LYNrh0werSFiZcuYRo3MKWtgQs'
        'r1vTUis2qani+daocT9Qw35l+X9erdr/tYNp01CmT4fvvsOUUg7//rWNT44amjP8oev7sOmGsFnTmFTdLkWLRE2y0lzkZrrZVRHF'
        'smxWbW7muNG5xJMG4YjJtj0RVm1uYV9NDCEEpmUzuE86xw7PpkcnP0JAXZPBtysqWbahqW07U5Dt5oheafTs4ic9oOPzutiyO0w4'
        'ZtCve4gzJhSIsoqo9t7XFVLa2LqmuFqjxrWnjy8489V7B96cPvZfM1N9qfyCGfdfb+9NmaK2/R4KuKYpQhiTxxXIum8mmZHvT7I/'
        'fWK49LhUqSqKHNQrXa54a6ysmjtJvvvQEJmT4ZZ9i0LyitO7ysnjCmRhrq9thRzwErJDjleed3yhfOPewfLtB4+Ul07uLDvn+6Qi'
        'lJ9dn5PhkSeMzpNXntFV9ukWlAN7psnyL4+ViWUnS2vFKXLGdSVSU1UJ2L+b1NGo/eZ4KVdPlj+8OfadYJCslD5TfzrPX9P+4y0/'
        'DrQFYK54c0zBuXeufnV3VXySSxOEY4Z179Te6s0XFWFZ8MKHu5n23Ba+eX4kA4pDNLYY5Ge7uf/Fbdz9XGl7f32LQgzoGaKkKEDv'
        'rgHysz14XAp5mW4M0yYat0CAz63idinUNCSJxi3qmpJs3hWmtCzMuq0trN7S1N7nYzf3449TulJdn8DjVhAChl6wiCElabzwlwGo'
        'qpD1zUn7snvWqt+vbdjm9iiXhsPm4mnTxmnTpy8wDzLtf9v+oy3f9oFyy2nDdm5pnW1assCybFNqqup1a+pfX93OwF4hjhuRwwUn'
        'FdK/OETXDj6aws4Yo3GLzgVeMkJubjivGycelUv3Qh8CgaKCZTn2p64pxJMOkB1DLgTQEjFRVYUenfyYlo2UcPTQLGwbpJSUV8X5'
        'dkUdj/1zJyGfhm1LdF0gpWNSvXDXAHp18eN2KVTXJ8V5d65Wl21oMP1evdgy5Lc+t/7H6dMXvMh/aAX8J4Bq99/3nQlcdtcjm544'
        '6ai84K6KqOn3qpptSxQhMEyby6evZfZjQxncO40je6dhmDZCcdS8qghqG5NIKYnFLT5fWIMiIBK3kBIShk1L2GRvdYzSslYG907n'
        '9fuOAOCPD61n1eYmencN0jHXQ1aaC10XKAI8LhVNFSRNiWHarN7SzAUndcSyJEKDhCEZ0icNj1ulsjbOeXeuYvnGRoI+XbNsaRmm'
        'rXYv9L8w+/GjSgads+DG2+6wlenT4deA+mu3vAaYPrd+hWXbL3jcKl0KvPbW3ZF2f1tVBQKIJSw65np45Z4jGDsok3DMxLQcwD1u'
        'hfG/X0JlXZwzJhYw/sgs+hQFCPq09kElDEltU4K1W1vICOpMHJaNBL5ZXkddU5IBxSFyM934PCoyZdzGEjZbyyMsWl3P+19XICUs'
        'fWMMQZ9K0pBoqsCWknnL67j1ic1s3R0m4NVSaElicUt26+i3Sz86Wn3w5a0vTntuy5XyvSmqOHvWYa/UXwNoO5gS+YIAy5JSmKZU'
        'AII+DdOWhKMGPo+GIgSxhEXAp3HtOV05+7gOpPk1vG6Vp98tY/ueCI/eVEJBngdpOiaPZaW8IUUQT9rYtsTjVrBMSTjmbP2A11mF'
        '8aSNADxudb8XpQh0TSBUQWNTkruf3cq6bS1cd0430oI6uyuizP62innL60gkbedhAJGYiaoIvB6VRNLmpDG5xqLVDXo4ar4YT1pX'
        'puZuHQ6ohwuoA6ZHuVhK5bVU54qqCBFLWEwYms0jN/YhGrd47dO9vPhBOV6P4pg+pk3CsMjJ8JCf5aaxNcmZEwp44rZ+bCuL0Bw2'
        '2FMVp64pwe7KGNvKI0TiFtlpLq7+XVe6dfRhGDaq6gzVsiWqIqhvTvLU27vYXRUj6NPo0sFL90I/mSGdrh18+L0qJcUhbn98EzNe'
        '24bfoxOJm4DE63YeOAIiMYOxg7O57txuFHX08cDL2/hgXgVel2YIBd225fPxpDUVDs+kOhxAFcD2atowVOYDngPeB+CLp4cxvF8G'
        '0bhFWkDj1ic288TbO/F7NaQtUVWBYUriSUcpHTM8F7eusH57C60Rk1jCbv9fyK9zwYmFXHRyIUWFPmz580FKQBGwrybOO/+q4JWP'
        'y6lrSgCgayohv4bPo9KnKIDHpfDJgipAEPBqCAGm5TyUSNxk3OAs3nv4SLxuFVtKKmoTHHfVUqrrE2iaMCVoSKbGEubzhwPqvwNU'
        'AaQfci23tk5ALo7mUxRFEI2ZHNknne9eHoVpS2xLkjBsdE0w+YYVLF5bj9+jYVqShGEx5dgOTByajRCCHp19dMzxcPHda1i6voHu'
        'hQEuOaWQKcd2oFtHH0kjZSodoknA61bwulV2V8b4fGE1b3y2l1WlTQzqnc5bDwymqSXJjr1R4kmbBSvrmTmnAlV1PDDDsMkI6Xz9'
        '3AgK87xIKXHpKl63wqQ/LuPr5bX4vZq0bWkBmo08LpGw5v47UP8doCpge13aHATH4kSONCAlI02O6JXObZd25/VP9zC0JJ1rzumK'
        'W1dZsq6RU65f3q6kHr25hAtP6oSuCVxelS3bW3ni7Z0sWFnPBScWctYxBfTo5MeWkmjMoqHFwO1SUIRoD9e1gykdQOMJi5BfI+TX'
        'UVVnxX6yoJqXZpfTv0eQP13cg749QyTjFrYteWdOBdc+tB6EIBIzmHFdCdee041owuKb5XXMW17HcSNy+NubO1i2vhGvR8O2pQ0I'
        'CTVqwhwYcVzVtgD2rwI0JTe1acA9Uu4H88Bm286qBImuqSx4aRTFnRw775oZG3jjs3Juv6SY+67uRXOrSUOLwbOzynjl43JOG1/A'
        'rRd3p2+PIIZhs2F7K0vWNbJ5V5izjilIiRETw5I/GqiiCII+lY07wvzzi710yvMwYkAmA3uG8PlUdu+L8tQ7u3j90z2cNbEDN15Q'
        'RHa6i1BA474Xt3Hfi1s4omcanz41DF1VsG3J0VcuYcvuVjRFQdeVn07TAlQkc2NJ8zh+YZX+7M4D3jd9uj5ISv4sZarDg12oCIJ+'
        'HV1T6N8jSIccN163gsslyMt04fdoXHhyIfGETU1jgjNvWcHjb+3gmdv689oDg+jZ2c+8pXVccd86jpm6lPtf2sbpR+fTtYOXzxZW'
        'sXlXGF11DHMpQVMFu/ZFmT2/ioBP5dzjO/L0u2Uce9USLp22ho+/qSIn3cWjt/bjvRlD+HB+JZNvXE5VfYJ4wub8EzoS8DqKKyfd'
        'hc+j4nIpFBX6UBUFn/egprkT1xUc63VrV7cDfJiAti0GzVbslwH9J+//rFmWjWHa3HZJD7p08PH5ohom37CCR97Yzvgh2RTmejBM'
        'yS2Pb2L99mY+/NtQLjirC8vXNjD1wXWcdtMPvP7pHhpaEnTK87B1d5inZ5YhhKBjrqc9+iQcW438LDdBv8arn+xhxaYmenb2E4mZ'
        'zPq6kil/Wsnl09fy7bI6JhyVy9fPjWRvdZxrZqzHtCQFOR6OGZ7N7G8rOf3mFXyxqIb0gM7tl/ZA1wRJw/qZiDkAVAv4q9tNESld'
        'cjiAOlrdrf1BIAb90tMAZ4XG4hY3nt+dE47K5bJ71vC721cyd2ktAENK0ghlunnhw918saiaN+8bzKnj87n/6VJOun45r3xcTtJw'
        'xFHHHC/9egTpVujj1ou7c9yInJThvv/zJOB2KRw1KJNbL+pO3+5B+heH6NbB327gz/yqglNuWM6tD2+geycfHz8+lG9X1PPE2zsJ'
        'ZbgY1DsNgH99X8s5d6zkwrtW0784xN1X9iSetBAHR7TtzaBAm8H+PNdBL/rR30HINNzaNgFpqfcO/gkCkoakINvN838ZwF9f2c7C'
        '1XX4vTqaKmgOJ3nrgSMZ3j+dwed+R49Ofl64awB3PFXK3GU1uHWNhGGRleZi6lld+MOZXejUyQemJBI1nRSngEjsx+LK52mPxBPw'
        'aeBSqK6M8vLsPfxjVhn7amJ43BrxhMmQkgyevq0fj7y2g88XV7P6nbFs2hnmrFt/IOR3YduScMxgSEk6M64r4ebHN7FuWwtel4J9'
        'cDPeAlQbeXQiYX3LT+TpT4FSAcvrVu8RQkw7lCL6aVMVx6WLJ2x8XtXxnQUkDZtrfteN0rIwc5bUkJXmImlIWiJJ0gIukobNiUfl'
        '8thNfcnPdrN0fSPLNzSxryZOVX2C5laDnEw3M67rjaoILCnxuFT++sp2Vpc2kZnmJj/LRUGOhyN6hRg9MJOEYXP3s1t49eM9uHSF'
        '5rCBz6MS8uvUNsYZOSCTwX3SeHbWbkc248jlcMxq98JiCftQ274NUAXJgljSPJofZyl+BKgACECW6dZKBWQeAvT9Nwhny5uWJJm0'
        '212/tpss27E/AXweDcuSKIrArSs0hZMM6pXOWw8MYuZXFXy5qIbNu5yg8P6MMdx7VW+uPrsrhimROIDOnLOP6x/eSNK02q/1ujW6'
        'F/qZNCqHSyd34rYnN/P5oirSg86DM0yJS1OIxA0AXLoDXtsuMFPur0tX0DUna3CwjGuq2YBiIyckEtZ8DlilB4L1UzPp38pOZ6AW'
        'XpdGt44+ELB1dwRddVZTZkjn9AkFVNcn+GJRDYoiSCQdm/CIXmnkZLhYsamZhpZEe79Bv45pSrLSXbx6z0DGH5lFXVMSJRX9tSxJ'
        'duq+8/+8ioqaOG6XSkskub8Pn86A4hDRuMWaLc0gBH6PSsKwGDMoi5KiILPnV1HdkEDXnBXZvdDnWBAVURJJC01VcLv2xwl+0trM'
        'qPmxpDmBA1ZpG6BtPz1el7YBQbfUEjmoWSWEIBo3Kcz1cuFJHTlmeA5FhT4CXpUP5lVx/SMbSBg2z905gD9M6UI8bnH59LW8/a+9'
        '9OoS5K4rivndpA7MeG0Hf/n7Zjpke5k0KofcTDdPzdyFadrMengIx4/KoaHFwOdWiSedXeVxK8QTNgGfyqrNzUy+8QeiMZMrz+xK'
        'LGHxr8U17KuN8fvTuvDMHf2ZPb+Kv76yjbVbmxnSJ4NPnxxGfq6HWXP2cf6fV2Pbknuv6sWlp3YiFrfYsS/KotUNvPHZXsoqoj9T'
        'igc0CViKLY6IGMbGNlDbAFMA6XOpExEU/TKYYFo2w/qm8/nTw7j3j70YUpKG36Pi92ns2BvFtGyKOwU48ahcquviJA2b+maDjrle'
        'PvjbEM4/pRPXP7yRac9u4daLejD3uRE8cmMJiaRNLG5y2eTOTBqZQ0vEJJm02biz1fGwdMH67a00tRokkjbD+2dw8wXdSZo28aTF'
        'g9f0Zt7zI7ntkmLe/nIfVz2wjrOPLeCTJ4ZR3DlAMuUWV9XEmDA0m0G90rBsmz3VcdKDOkG/xvC+6fzl98XM/ccIThidi2naKAcX'
        'epYQaLZiX3YAhu2gSQApxNQD/z5YUxXHVrv6d13p2z1IZW2C1qiJ16ty25ObeeSNbVi2ZOTAdDJCOgGvxt9n7WbOkmoeuLo3ffum'
        '89BL23j1k3Lef2QIM67vg9etcsI1y3ji7R0EfToXnlzoyEwJF9y1mtWlzXjcqhNlakpy6T1raGo1SSRtzjwmn465Xl76aDdHXfo9'
        'piV56Po+fPrkMN7/uoI7nymlc2c/j9xQwrrtzfz11e34vBpej8qYQY6aeO79Mm54ZCM+j0o4ZlFVl6BLBy9XnN6ZpGm3i5ufQuE4'
        'G+LcLAjiuOVCIeWXeqGDhLEHov3TpiiCcNRkcO90BvdOo7HFQFEEeVlunn1vN0/P3EnAq5MRcjGkJN0R+kAsbpGT4WbisGxqKqK8'
        'PLucR2/qy2kT89lVEcPnUbjzsh64dJUhJen07hpA1wT3vbiNvkVBLp3cmZaISSRuccLoXM6aWMDtT23GlpLOeV6OHZ6DqircenER'
        'mSGdrWVhxg3J4p/3D+atL/exc1eY8UOyKOoYoK4xiZqa3YCeIUJ+HZ9H5YUPy3jgpW1kpumoqqA5bNKzS4ChJRm0Rs2DgSoAWwgK'
        'oi51fDtEtCkerzpcOEi3qc4fgykcJdS5wMub9w+iSwcfiaRFZkjjo2+quO/FrQBccUZn3n5wMNvLIyRNSTRu8YczO3PlGV3weVT2'
        '1cQ5fmQOF5/SiR/WN/HDxkZCfp2BPdPQNYXRR2SQmeni25X1LFrTwIPX9iFuOMFkVRE0tRpcc043quoTfDCvEn9IZ1jfdDRV4eih'
        '2WSlu9i8K8ziNQ2cMCaPs4/pwM69ETwuhTMm5nPbpd2JJ2xsKdm+J8JLdw/kunO6AfDIGzuY+a8KMoI6iaRF53wvb/91MH26BUgk'
        'rYOBaqc8uIkHAuo0i1NSttdBt7tQwDAtbrmoB8Wd/TS3Gvg9GtvKo9z46EZaowYj+mdyx2U9GDUwg7rmJK9+XE5ujofVpS3kZrpx'
        'uxQ65HiYflUvVEWweE0DlbUJvD6VHXsjJJIWRR19CF3hnX/tY9SADDJDOvVNCRTFkd/NYRNdExw3Mpt351SAhIIcD5Zls2ZLM5oq'
        '8HlUvl/biGna3Pn7HvTrEWwnSWzaESYry81H86r4YWMT447M4i9XFHPy2HxMy+aWlGEf9Gk0hQ0653v58++LsQ6u7RUpwUYcj+Oi'
        'm22sOBdCHJXSZj/b7m12WprfxbC+6URilpMUcys8/Pp29tXEyAi5eOCa3rh0BduSTBqRy1GDMmkNG7zycTlH9AqhqaLd4AfIz3Zy'
        'QrYNz7xbhmnZ6LpCrMXgmx/qCfo1bn1iE699upegTyPg1Zg9v4prZmwg5NdZtr6Jsj2Rdn//qZllmJazK9KDOoqARNJOhQAFfYuC'
        'vPBROQ2NCY4sCXH60fkoihP8vu+qXhRke6lvTnDfi9sA0FVBa8RkWN8MOuR4SRo/M/gVQAro7nI5lpECSC/kSujUht/BHoVh2uRk'
        'usjLcgxlv09j8dpGPltYA8DksfmMGpCBogg+WVBNS9TkyN7p7NobZfa31bz95T6HgxSzSBiSprBB1w4+tpRF2L47zNJ1jQC4dYXt'
        'eyI0thg8/tZO/vbGDvp1D2KYTphwcO80Xvt4D7c+vonmiMGOvRHCMRMhBCs2NrGlLMyaLS0UFfoIRy1MUxJLWLRGDGbPr+KrJdX8'
        'sKGJkuIQHpfCzDn7UBVB764Bzj2+IwBzl9Xy7cp6/D4Ny5Z4XAo+j3Iom9QGNBW1X/tqtN1qX+GkNuxDAQq022MyNfH121poDicJ'
        '+HQuOKkjtoSa+gTfrqxn8rhcGlqS5Ga6+fypYeRluZmzpIZVpc2U7mpl885W9lbHWb2lmWOnLiWSis43tRrUNxtEYiYuTeHjx4Yy'
        'eVw+kZhJPGExYkA6X/59OBkhvT361NhsYNs2igKn3byCuUtriURNtpVH2F0VY/ueKPNX1GPZMPOhIfQvDlFXn2TSqFzWbW1hd2UU'
        'W0rOmdSB7HQ3ScNiybrGdk/KQeTQsAgBtmQwpPx0IUV/oYCUBw9JHfSxSKioTSCAkm4BSoqCaKrglY/3MLBnGp07B9ixs5WQX2Ps'
        '4EyOHpLV7iP7PCqtURMkTBqZw9MzdzH9BUeprdvWSmGuF5BcemonThqTR1V9HF1zhtXYYjD6iExuv7QHNz66ge17ou1bMRq3OOmo'
        'XO6Z2hNpOw8+6HOcAsuSnDY+H1tCNGbSEjYo6hrgqEFZvPzxHh68pjfdC30MLUnny++rqaiNY6fChpblENMO4d8LHBLFgPYVKqDP'
        '4YC4vwentUZNJNCra4CMoE5lbZwdeyOcMjaPy/+8iife2kXIr9HY4tANbVtS25jkpY/KaY2YSCnZXRnlqilduf2SHgB8/G0VNz22'
        'ESEERx2RSTxp4XU7hoiU4HWrRGIWg3qnoWsqj/1zJ39/rwwpYepZXXnwmt5U1iYwLYfs8PpneymviiGlE7VqbEkS8Gk8+c4uzr11'
        'JROHZVNVl2Dn3igBn0ZhvhdwrJq2JiWHijyBkx5BQlEheNtWY9eUbv/FHFNbLqdtF2SGnNhzhxwPXq/Khh2tlJaFWby2gaKOfly6'
        'I9R1TeGb5XUoCuyriXHnM6WoqiA70835f17NKx+Xc9cfejKkJIM91VHKKmNIKalvTqKrCuu2tWBLiarCtj0RTHN/Am9vdYwdeyJ0'
        'KfAzfWpP5i2v44ybV+DzqGSlubjnua0sXddE0K8x74e6FNCS7HQXPTr5WLOlmV37IqwubcblURlYHHTm2jZnHFtIVTiUCypS2HRo'
        'SQEq+AXP6MCmawJVCGxLYtmS3Ew3AL26+EEVbC2PsHZrMxt3tPLnm0vIzXSztTxCZpqLHXsjrN3awsiBGZw8Jo8Zr27nwZe30b9H'
        'kDMmFmCaNjec1w1VUXDrTnLu84U1PP72Th54eTu5mW6ys7289vEeHnptOx/Mq8Q0LbwpssJ153Yjza8ztG86E4Zl89TMXdz/4jYG'
        '9U7jjAn5bC0Ps2lHK1lpLvbWxLAsuO+WftQ3J1m2oZGVm5sBhzgB4Peo2BJM0ybo0+iQ402JgEMnLmxQtTRIT0C/1JsH95CEwLJt'
        'hvZNJzNNJ56wCKS5CPnbQqUCJJTuCiOEo7ASdQnGDMpEpgZ1+oQCPvuumuLOfp77c3++X9uIlJKpZ3ZxtmPUYli/DPKy3NQ2JvC4'
        'Vb5eVscXi2vIy3Lx/Pu78XlUvlpay66KKG5dSQWRbUJ+jdFHZBBNWOia4KHrerN0XSOtUZPrz+uGEDB3SS2njM3DpSu0REyG90sj'
        '2eJEsYSA3ZUxR4mkllZRoY9gusOk9nlUjuyTxsLVdQfbwgJHMWUZbnWAluIR/GIQ2bYlbpfKxacUogjB5l0RvvugnA++rmwPloBj'
        '8wkhiCYsLFPSt3uQR9/YgdetMrBniEmjclmwsoGeXfwM75eOx63SEjGcWKWu4HUrhPwaVfUJXDjbzOdWaWgy+ONf16V2idpOoCBl'
        '03bM9ZGf5cayJKYpsW2b8UOyMS2b3ZUxVm5qZmjfDPr1CLK3OsbbX+7jTxd3x7YljS0GQgi0tlKGFEavf7qXeMJm3JFZHNErxLkn'
        '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'
    )
    TIGER_SYMBOL_WIN_PNG = (
        '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'
        '/qa7RMSqjdr+3ESZikdWXXS16B0dIiKiB4PhSDPvA8i8ef/jzRctUEVsaCoi8pqIiBEKhURE9PYOWXHuOJkelxkrPRQR2fHyX2UK'
        'cbL2mluk/NFnZZqaItXf/FPW33S3TLUlS8vy1Raeui5mOCximlL+2LOy6JhTZMU542S6I0Pm5JTI9ucmSsuS5dK2bqNUf/OD1Hw/'
        'RfyVu6VlxWrZ9vSLMrdwsExTU2X5mZfI8jMuli1/ekLEMMQM65ECWBHfpnKZHpchq393vdR8P1mmaSmy+f7HZf0Nd8hkbFL+2LMx'
        'vuumzpTShFxZetr5EmhsDltgh5cKRDdl+BeWY48OqCITJtgAjHD4fRGRcJs3tOTkc6Q0KU9alqyIMVX1ydfyE/Gyetz1UvXZ1zLN'
        'liq73/tIdF+7lHq6y+pxVq16dFhFj21rN8jcnoNkVnqRlCbkypzcvrL6d9fJ4pFjrMo3d7bMiM+WWWmFsnj0GbL26ltkbuEQmZGQ'
        'Y9WBZvWS+hlzDtv2hlv+INMcqeLftUeqPv1afsIju97+QNbdcIdMwSV73v8kxn/L8tUyM60gvH70meLbVrFCWltTJ4AqEyb8Z7cZ'
        'li5bQoTafO9vPe8KmZPfT29bt9GMDt/W1etkRnyWLB49VhrnLZTSxFzZ8Pt7Y1I7lUSpmzYzJp0xigz9ju07ZNuzL8naa26VhcNP'
        'kZkpPaU0Mc8q7c7pI3NySmR2Vm+ZmZgnpQk5snDYSbLmyvGy+Y+PSuuKNQe01fUeLctWyjRbipQ/8pSIiGx94nmZ4e4m9dNmyfIz'
        'L5ZpthRpnBvbFCFsVtfK8tFnrHgHUgD+42AeAOqkSRrAomEnvycNTSIiuhEMGrrfL4tGnS6zMgukcc58WXjMSbL0lHPF1HUxQmFZ'
        'dOwYWXz8GWKGwodfozrMd/XTZ0upJ1fm5PSJ7eYwJ7evzHB3k4oXXjm0icOscUWrm1deeJXMLxkuers1P6666GpZ0G+ktCxdIT/3'
        'HCDz+o4wg03N0TlzkYikYEWZ/iUw/6WLFUURxo0zRUQ7oXzFbaSn3gZoqsOh7njlLaN52UIGvPUaNf/8CX9FJUM+ex9F0/BX7MC3'
        'oYzcqy5DsdsOn8ygKLG1KjMUpn5qKVWffY2iarF0xmiQQrXbaVmygsbZ8zBD4f1bDR9uySQSx8y9ehwdkT1KAQZ/8i5hr49d7/yd'
        'gR++bfq2lNHyyts24IP5p5xyiqIoLfL44/+eefTvUHQncBE5s3XZquoFjkwpf/TZcO20meYUXFL747SY5G1/5iWZ071frGr4qDsr'
        'mKYYwaCsvfoWmZnSQ+bk9omsoGbLDHe2Nb9ml8jMpB6y/MxLRO/wH20nm8i+FKYYnQGZ3+9YKbv7wdippl+WyI84ww2fT5K9r74T'
        '/snmuTfSPeV/bZgfjaLD/3vIXnHyeaWyr1bmFwyWtdfdpovs32piyfFnyvqb7z7isDwSde6tEm/ZZqn9cZpUffqVVH36tdT+MFXa'
        '1qyXjp27jlR2fSimkeu2PPikLBhwnIhhiGEYhogY1RP+Iot7H7NVRI6PCMh/Tpv/W6BG9tvQkpPY+sCTdy8uGdEqHf4ow3qouUV+'
        'zh8gdVNLD79HyRFR+PW9S34rRR9i85LlMjunxGjftXs/E4HgX/9mBYKYd/L/0Gj/T5GIKBMi83Hb5s3FIvJVlN/a6bOM+SXH6HqH'
        'P2YN/GYyTDENw7JXu34Mw9rE5be2ZZoihmEYYV1fMXKM+KeUiogsk86wFfezvMH/996+MK+LJyHh8FgRmeWbPV/2PBPZeErXw/Jr'
        'O+38Zym6G1jsnrsnvrlx3RXjx4tVjo2IaPJrBW//N0kmTFC7Pm3x+caKrs+SA1N8ou/9OPpGW/8eRds+eG5ZL7o+XqxSdou3/+EW'
        '6/9VEhFtQhdNKSKDRORlEdl7GBC6viQlCvLRgI6ej777I/rbg3/TJiKfisjYruDJpEn/K+8B+a/QwcyLSKKIXCgir4v1wpWjqX3z'
        'CJ+j0R4R+YeI3CjWa4bocu//dSD/a09JIm/5UhRF7/KdhrUgWIxVbz4CayOELCwll3aYpsAqtAgBPqwUoo1YOa6bgU0HvaQqKpn/'
        'lZdU/dfFXva/hUvpCm6X8xqWGaNh1fEfkDuAxfNWLDCDiqJ0HKaN6G/+669R+z+F7mSofj6ytAAAAABJRU5ErkJggg=='
    )

    WIDTH = 1150
    HEIGHT = 750

    # V12 layout: column-scrolling bead plate and 70% larger Big Road viewport.
    GAME_X0 = 12
    GAME_X1 = 770
    HISTORY_X0 = 778
    HISTORY_X1 = 1138
    BOARD_INNER_X0 = 22
    BOARD_INNER_X1 = 760
    # All modes share these three fixed vertical bands. The 44px header
    # accommodates Lucky 7's two-line pool without moving the mode rail.
    CARD_AREA_BOUNDS = (GAME_X0, 4, GAME_X1, 310)
    BOARD_BOUNDS = (GAME_X0, 316, GAME_X1, 620)
    MODE_SELECTOR_BOUNDS = (18, 322, 764, 350)
    BOARD_HEADER_TOP = 354
    BOARD_HEADER_HEIGHT = 44
    BOARD_HEADER_Y = BOARD_HEADER_TOP + BOARD_HEADER_HEIGHT / 2
    BETTING_BOUNDS = (BOARD_INNER_X0, BOARD_HEADER_TOP+BOARD_HEADER_HEIGHT,
                     BOARD_INNER_X1, 608)
    BETTING_TRANSITION_BOUNDS = (GAME_X0+2, MODE_SELECTOR_BOUNDS[3]+2, GAME_X1-2, 618)
    HEADER_MIDDLE_X = (BOARD_INNER_X0 + BOARD_INNER_X1) / 2
    HEADER_RIGHT_X = BOARD_INNER_X1 - 6

    # Only genuinely mode-specific results belong in the special-data page.
    # Dragon Bonus and Perfect Pair are normal side bets, so they are deliberately
    # excluded from this table and from bead-plate special markers.
    SPECIAL_STATS = {
        'classic': (),
        'tiger': ('Small Tiger', 'Tiger Tie', 'Big Tiger', 'Tiger Pair'),
        'ez': ('Fortune 7', 'Golden 8', 'Heavenly 9', 'Blazing 7s', 'Cover All'),
        '2to1': (),
        'lucky7': ('Small Lucky 6', 'Lucky 6', 'Big Lucky 6', 'Lucky 7', 'Super 7'),
        'monkey': ('Monkey 6', 'Monkey Tie', 'Big Monkey', 'Monkey 7', 'Lucky Monkey'),
        'goldendice': (),
        'treasure': (),
        'xxx': (),
        'one_deck': (),
    }

    BG = '#17120f'
    PANEL = '#211811'
    PANEL_LINE = '#665240'
    FELT = '#083f38'
    FELT_2 = '#0c5148'
    LINE = '#c3d5ca'
    GOLD = '#e7d36c'
    PLAYER_BLUE = '#3d67d8'
    BANKER_RED = '#d94a4e'
    TIE_GREEN = '#43a665'

    # Same exact-point palette as Baccarat_Special: 0 is lightest, 9 darkest.
    TIE_POINT_COLORS = {
        'Tie 0': '#c9efd4',
        'Tie 1': '#b5e6c5',
        'Tie 2': '#a0ddb6',
        'Tie 3': '#8bd4a6',
        'Tie 4': '#76c997',
        'Tie 5': '#61bd87',
        'Tie 6': '#4cab77',
        'Tie 7': '#398d63',
        'Tie 8': '#286f50',
        'Tie 9': '#18513b',
    }

    # Result-area flash palette.  The dealing panels flash independently from
    # the betting spots so the winning hand is obvious even with no wager.
    PLAYER_ZONE_BASE = '#102d47'
    PLAYER_ZONE_BLUE = '#2469c9'
    PLAYER_ZONE_LIGHT = '#83cfff'
    BANKER_ZONE_BASE = '#4b1e22'
    BANKER_ZONE_RED = '#c93643'
    BANKER_ZONE_LIGHT = '#ff9ca2'
    TIE_FLASH_DARK = '#23874b'
    TIE_FLASH_LIGHT = '#78e49a'

    MIN_BET = 100.0
    MAX_TABLE_BET = 2_000_000.0
    MAX_RECORDS = 500
    ONE_DECK_BEAD_RECORDS = 72
    ONE_DECK_BEAD_TRIM_BATCH = 6

    # V23 chip-motion timing. Every wager chip and Treasure/XXX fee chip reaches
    # its destination in 0.2 seconds; winning return chips use the same timing.
    CHIP_MOVE_DURATION_MS = 200
    CHIP_MOVE_STEPS = 10
    MODE_TRANSITION_MS = 360
    MODE_FRAME_MS = 16

    GOLDEN_RETURN_DURATION_MS = 1500

    # XXX uses probability-only RTP tuning.  RTP is NOT calculated or corrected
    # hand-by-hand.  At the start of each round the game independently chooses:
    #   1) how many distinct golden faces exist this round (4..8), and
    #   2) an integer multiplier (2X..10X) for EACH chosen face.
    # Every one of the 52 card faces is equally likely to become golden.
    # The weights below are fixed long-run probabilities chosen to roughly offset
    # XXX's 50% fee and lower base odds while keeping every round genuinely random.
    # Extreme combinations remain possible: e.g. 8 golden faces can all roll 10X,
    # and 4 golden faces can all roll 2X.
    XXX_COUNT_VALUES = (4, 5, 6, 7, 8)
    # Probabilities: 10%, 20%, 55%, 10%, 5%
    XXX_COUNT_WEIGHTS = (10, 20, 55, 10, 5)

    # XXX 每张黄金牌独立随机倍率
    # 2X / 3X 最常见，之后倍率越高，出现概率逐渐降低。
    XXX_MULTIPLIER_VALUES = (2, 3, 4, 5, 8, 10)

    # 2X 27%
    # 3X 27%
    # 4X 19%
    # 5X 12%
    # 8X  9%
    # 10X 6%
    XXX_MULTIPLIER_WEIGHTS = (30, 24, 19, 12, 9, 6)

    # V24 Golden Dice probability-only RTP tuning.  A multiplier is always drawn
    # but is paid only when the two dice total 8 or 9 (9/36 = 25% trigger rate).
    # Weight means were chosen using standard 8-deck Baccarat frequencies and the
    # mode's 20% fee: Player/Banker ~=98.6%, Tie ~=95%, Pair ~=97% long-run RTP.
    GOLDEN_DICE_MULTIPLIER_VALUES = (2, 3, 5, 10, 20, 50, 100)
    GOLDEN_DICE_MULTIPLIER_WEIGHTS = {
        'Player': (4800, 4800, 300, 60, 25, 10, 5),
        'Banker': (4600, 5000, 300, 60, 25, 10, 5),
        'Tie': (426, 460, 50, 20, 10, 10, 24),
        'Pair Player': (4400, 5200, 300, 60, 25, 10, 5),
        'Pair Banker': (4400, 5200, 300, 60, 25, 10, 5),
    }
    GOLDEN_DICE_BASE_PROFIT_ODDS = {
        'Player': 1.0, 'Banker': 0.95, 'Tie': 5.0,
        'Pair Player': 10.0, 'Pair Banker': 10.0,
    }

    CHIP_SPECS = [
        (100, '#202020', '100'),
        (500, '#d780c0', '500'),
        (1000, '#ab0058', '1K'),
        (5000, '#ba3438', '5K'),
        (10000, '#70439a', '10K'),
        (50000, '#2e7542', '50K'),
        (250000, '#ffffff', '250K'),
    ]
    M_CHIP_COLOR = '#102d47'  # 墨蓝色；金额以 M 显示时使用白字
    WAGER_CHIP_RADIUS = 23  # Original radius 20: diameter increased by 6px.
    MOTION_CHIP_RADIUS = 22  # Original radius 19: same 6px diameter increase.
    SELECTOR_CHIP_DIAMETER = 62  # Original diameter 56.

    MODE_ORDER = ('classic', 'lucky7', 'tiger', 'ez', 'monkey', '2to1', 'goldendice', 'treasure', 'xxx', 'one_deck') + BaccaratEngine.ALWAYS_MODES
    MODE_TABS = MODE_ORDER[:-4] + ('always',)
    MODE_SHORT = {
        'always': '固定牌', 'always6': '固定6', 'always7': '固定7',
        'always8': '固定8', 'always9': '固定9',
        'classic': '经典', 'lucky7': '幸运7', 'tiger': '老虎', 'ez': '简单',
        'monkey': '猴子', '2to1': '1赔2', 'goldendice': '黄金骰', 'treasure': '聚宝盆', 'xxx': 'XXX',
        'one_deck': '单副版',
    }
    MODE_HEADER_TITLES = {
        'always6': '固定牌 · Always', 'always7': '固定牌 · Always',
        'always8': '固定牌 · Always', 'always9': '固定牌 · Always',
        'classic': '经典 · Classic', 'lucky7': '幸运7 · Lucky 7',
        'tiger': '老虎 · Tiger', 'ez': '简单 · EZ', 'monkey': '猴子 · Monkey',
        '2to1': '1赔2 · 2 to 1', 'goldendice': '黄金骰 · Golden Dice',
        'treasure': '聚宝盆 · Treasure Pot', 'xxx': 'XXX',
        'one_deck': '单副版 · Single Deck',
    }

    BET_COLORS = {
        'Player': '#345fc4', 'Tie': '#43a665', 'Banker': '#c94349',
        'Dragon P': '#6658a6', 'Dragon B': '#aa5142', 'Perfect Pair': '#b87930',
        'Golden Hunter': '#9b7725', 'Golden Duel': '#8c6a23', 'Super Dice': '#b88720',
        'Dice Points': '#173f50', 'Golden Present': '#856724', 'Golden Absent': '#28615e',
        'Golden Count 4-5': '#856724', 'Golden Count 7-8': '#28615e',
        'Pair Player': '#a943a6', 'Any Pair': '#36959b', 'Pair Banker': '#a943a6',
        'Small Tiger': '#b260ad', 'Tiger Tie': '#3e9c52', 'Big Tiger': '#3b9ca6',
        'Tiger': '#ba7730', 'Tiger Pair': '#a943a6',
        'Panda 8': '#d6d6d6', 'Divine 9': '#55a966', 'Dragon 7': '#bb692b',
        'Small Lucky 6': '#b260ad', 'Lucky 6': '#b97732', 'Big Lucky 6': '#3f9aa0',
        'Lucky 7': '#b8a82d', 'Super 7': '#279b70',
        'Monkey 6': '#ba8848', 'Monkey Tie': '#aaa536', 'Big Monkey': '#b76d87',
        'Monkey 7': '#bb692b', 'Lucky Monkey': '#b64c8b',
    }

    def __init__(self, parent, balance=10000, user=None, on_back=None,
                 on_balance_change=None, game_mode='classic'):
        super().__init__(parent, bg=self.BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.root = self
        self.username = user
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.balance = float(balance)
        self.final_balance = float(balance)
        self.summary_mode = 'bet'
        self.last_win_amount = 0.0
        self.last_net = 0.0

        game_mode = 'always6' if game_mode == 'always' else game_mode
        self.game_mode = game_mode if game_mode in self.MODE_ORDER else 'classic'
        self._always_selected_mode = (self.game_mode if self.game_mode in BaccaratEngine.ALWAYS_MODES
                                      else 'always6')
        self._segmented_controls = {}
        self._mode_transition = None
        self._mode_transition_after = None
        self._mode_transition_item = None
        self._mode_transition_photo = None
        self._mode_fee_visuals = []
        self._mode_pending_cut = None
        # Session-only, independent choices: first entry uses each mode's preset.
        self._banker_rule_preferences = dict(BaccaratEngine.DEFAULT_BANKER_RULES)
        self.banker_rule = self._current_banker_rule()
        self._round_banker_rule = self.banker_rule
        self.standard_engine = BaccaratEngine()
        self.one_deck_engine = OneDeckBaccaratEngine()
        self.fixed_engine = AlwaysBaccaratEngine(self._always_selected_mode)
        self.engine = (self.fixed_engine if self.game_mode in BaccaratEngine.ALWAYS_MODES else
                       self.one_deck_engine if self.game_mode == 'one_deck' else self.standard_engine)
        if self.game_mode in BaccaratEngine.ALWAYS_MODES:
            self.fixed_engine.prepare_mode(self.game_mode)
        self.bet_state = BaccaratBetState()
        self.selected_chip = 1000.0
        self.undo_stack = []
        self.last_round_bets = []
        self.bet_spots = {}
        self.chip_selector_items = {}
        self.control_buttons = {}
        self.mode_button_items = {}
        self.squeeze_enabled = tk.BooleanVar(master=self, value=False)
        self._round_squeeze_enabled = False
        self._squeeze_hands = set()
        self._squeeze_batch = None
        self._squeeze_bindings = []
        self._squeeze_backdrop_photo = None
        self._card_face_turns = {}
        self._turned_card_images = {}

        self.accept_bets = True
        self.animation_running = False
        self.settlement_running = False
        self.animation_after_ids = []
        self._cut_dialog = None
        self._pending_cut_threshold = None
        self._cut_notice_popup = None
        self._cut_notice_active = False
        self._cut_notice_seen = False
        self._round_cut_card_offset = None
        self._round_dealt_card_count = 0
        # V23 keeps short wager/fee/return chip flights separate from the card
        # animation queue so they can be cancelled cleanly on exit.
        self.chip_motion_after_ids = set()
        self.chip_motion_serial = 0
        self.pending_bet_visual_amounts = {}
        self.pending_fee_visuals = {}
        self._fee_visual_serial = 0
        self.settlement_return_animating = False
        self.settlement_return_keys = set()
        self.settlement_profit_tags = {}
        self.settlement_losing_amounts = {}
        self.settlement_chip_moves_started = False
        self.settlement_after_id = None
        self.reshuffle_confirm_after_id = None
        self.reshuffle_confirm_armed = False
        self.reshuffle_button_rect = None
        self.reshuffle_button_text = None
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.flash_original_text_colors = {}
        self.pre_deal_bets = None
        self.current_result = None
        self.settlement_flash_step = 0
        # Keep Push wager chips visible until their return animation starts.
        self.settlement_hold_amounts = {}
        self.push_return_amounts = {}
        self.result_panel_flash_winner = None
        self._closing = False

        # Treasure/XXX round state. Treasure uses five unique faces; XXX uses
        # 4-8 unique faces. Duplicate physical copies in the 8-deck shoe may
        # therefore produce repeated matching hits in one hand.
        self.current_golden_cards = []
        self.current_golden_map = {}
        self._golden_activated_slots = {}
        self.treasure_panel_active = False
        self.treasure_panel_images = []
        self.treasure_animation_refs = {}
        self.treasure_panel_card_items = []
        self.treasure_panel_multiplier_items = []
        # The remaining XXX Golden Duel rule cells flash in sync with
        # their betting area during settlement.  Each entry stores the right-side
        # odds-cell background and odds-text Canvas item for one payable tier.
        self.treasure_panel_rule_cells = {}
        # Golden Dice stays on the betting board; the history panel remains live.
        self.golden_dice_bowl = None
        self.current_golden_dice = None
        self.golden_dice_active = False
        self.golden_dice_multipliers = {key: 2 for key in self.GOLDEN_DICE_BASE_PROFIT_ODDS}
        self._golden_dice_reels_ready = set()
        self._golden_dice_cup_photo = None
        self._golden_dice_cup_item = None
        self.golden_dice_multiplier_text_items = {}
        self.golden_dice_status_text = None
        self._golden_dice_fee_collected = False
        self._golden_dice_roll_ready = False
        self._golden_dice_rest_anchor = None
        self._golden_dice_stable_time = 0.
        self.bet_fee_state = {}
        self.pre_deal_fee_total = 0.0

        self.history_panel_mode = 'roads'
        # V12: Big Road is a 50-column logical board viewed through a
        # horizontally scrollable window.  New results follow the right edge
        # until the player manually moves the scrollbar.
        self.big_road_scroll_col = 0
        self.big_road_auto_follow = True
        self.big_road_virtual_cols = 50
        # V12: 14 visible columns makes each Big Road cell ~71% larger than V11's 24-column viewport.
        self.big_road_view_cols = 14
        self.runtime_json_dir = self.get_runtime_json_dir()
        # V14: shoe state, current-shoe finished hands, and lifetime statistics
        # live in ONE JSON document.  Only the two temporary sections are reset
        # when the player cuts a new shoe; statistic_data is never deleted.
        self.runtime_data_file = os.path.join(self.runtime_json_dir, 'Baccarat.json')
        # Keep the three One_Deck sections in Special's original JSON file.
        self.one_deck_data_file = os.path.abspath(os.path.join(
            os.path.dirname(__file__), '..', 'A_Logs', 'Json', 'Baccarat_Special.json'))
        self.legacy_temp_data_file = os.path.join(self.runtime_json_dir, 'temp_data.json')
        self.legacy_temp_finish_data_file = os.path.join(self.runtime_json_dir, 'temp_finish_data.json')
        self.legacy_statistic_data_file = os.path.join(self.runtime_json_dir, 'statistic_data.json')
        self.runtime_store = self.load_runtime_store()
        self.one_deck_store = self.new_one_deck_runtime_store()
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            self.one_deck_store = self.load_one_deck_runtime_store()
        self.history_file = self.get_history_file()
        self.shoe_resumed = self.load_temp_data()
        self.history_store = self.load_history_store()
        self.history_data = self.history_records_from_store()
        self.bead_store = self.load_bead_store()
        self.bead_data = self.bead_records_from_store()
        self.statistic_data = self.load_statistic_data()
        self.treasure_pot_amount = 0.0  # V19: current-round fee only; never persisted

        # Bead Plate text can be toggled between result labels/special marks and
        # the winning point value by clicking anywhere on the bead grid.
        self.bead_show_scores = False

        self.jackpot_file = self.get_jackpot_file()
        self.jackpot_amount = self.load_jackpot()

        # Prefer the original Baccarat external card artwork. If the project
        # assets are unavailable, draw the temporary V4-style cards instead.
        self.external_card_images = {}
        self.external_card_images_rotated = {}
        self.external_back_image = None
        self.card_asset_dir = None
        self.golden_card_pil = {}
        self.golden_card_images = {}
        self.golden_card_images_rotated = {}
        self.load_original_card_assets()
        self.load_golden_card_assets()
        self.load_always_card_assets()

        top = self.winfo_toplevel()
        # Embedded games must leave the parent window's size/state policy alone.
        # The standalone main() configures its own Tk window below.
        self._enter_window = top
        self._previous_enter_binding = top.bind('<Return>')
        self._enter_binding_id = top.bind('<Return>', self.handle_enter_deal)
        self.bind('<Destroy>', self._restore_enter_binding, add='+')
        self.bind('<Destroy>', self._on_mode_transition_destroy, add='+')
        self.bind('<Escape>', lambda _event: self.exit_game())

        self.create_ui()
        self.select_chip(self.selected_chip)
        self.update_display()
        if self.game_mode in BaccaratEngine.ALWAYS_MODES:
            self._draw_fixed_banker_card(preview=True)
        if not self.shoe_resumed and self.game_mode not in BaccaratEngine.SPECIAL_MODES:
            self.after(180, lambda: self.start_new_shoe_cut(False))

    # ------------------------------------------------------------------ UI base
    def create_ui(self):
        self.canvas = BaccaratCanvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_rectangle(0, 0, self.WIDTH, self.HEIGHT,
                                     fill=self.BG, outline='', tags='static')
        self.draw_history_panel()
        self.draw_animation_panel()
        self.draw_board()
        self.draw_bottom_controls()
        self.canvas.bind('<Button-1>', self._handle_bead_click, add='+')

    def draw_history_panel(self):
        """Right-side history panel with Roads/Data tabs."""
        c = self.canvas
        x0, y0, x1, y1 = self.HISTORY_X0, 4, self.HISTORY_X1, 620
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
        self.history_panel_bounds = (x0, y0, x1, y1)
        c.create_text((x0 + x1) / 2, 18, text='历史记录',
                      font=('Arial', 15, 'bold'), fill='#d4c3a9', tags='static')

        self.history_tab_items = {}
        tab_y0, tab_y1 = 34, 62
        mid = (x0 + x1) / 2
        for mode, bx0, bx1, label in (
            ('roads', x0 + 8, mid - 4, '道路'),
            ('data', mid + 4, x1 - 8, '数据'),
        ):
            tag = f'history_tab_{mode}'
            rect = c.create_rectangle(bx0, tab_y0, bx1, tab_y1, fill='#30271f',
                                      outline='#8d765e', width=1,
                                      tags=('static', tag))
            txt = c.create_text((bx0 + bx1) / 2, (tab_y0 + tab_y1) / 2,
                                text=label, font=('Arial', 10, 'bold'),
                                fill='#d9c8af', tags=('static', tag))
            self.history_tab_items[mode] = (rect, txt)
            c.tag_bind(tag, '<Button-1>', lambda _e, m=mode: self.switch_history_panel(m))
            c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
            c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))
        self._draw_history_content()

    def switch_history_panel(self, mode):
        if mode not in ('roads', 'data') or mode == self.history_panel_mode:
            return
        self.history_panel_mode = mode
        if mode == 'roads':
            self.big_road_auto_follow = True
        self._draw_history_content()
        self.update_history_table()

    def _update_history_tab_style(self):
        for mode, (rect, txt) in getattr(self, 'history_tab_items', {}).items():
            selected = mode == self.history_panel_mode
            self.canvas.itemconfigure(rect,
                                      fill='#a57e38' if selected else '#30271f',
                                      outline='#f2d77c' if selected else '#8d765e',
                                      width=2 if selected else 1)
            self.canvas.itemconfigure(txt, fill='#111111' if selected else '#d9c8af')

    def _draw_history_content(self):
        self.canvas.delete('history_panel_content')
        self.canvas.delete('history_dynamic')
        self._road_summary_items = {}
        self._update_history_tab_style()
        if self.history_panel_mode == 'data':
            self._draw_data_page()
        else:
            self._draw_roads_page()

    def _draw_roads_page(self):
        """Draw the V14 road page with symmetric section boundaries.

        Layout:
          1) Big Road: logical 50 x 6 board with a horizontal scrollbar.
          2) Big Eye Boy / Cockroach Pig: equal left/right halves.
          3) Bead Plate: 12 x 6, using cells 25% smaller than V10.
          4) Small Road / Next-hand indicator: 5/8 and 3/8 widths.

        Road-name captions are intentionally omitted from the grid area.
        """
        c = self.canvas
        panel_x0, panel_x1 = 786, 1130
        panel_w = panel_x1 - panel_x0

        # ----- Row 1: Big Road.  The logical board is 50 columns wide, while
        # a 14-column viewport enlarges each Big Road mark by about 70% vs V11.
        big_x0 = panel_x0
        big_y0 = 72
        big_cell = panel_w / self.big_road_view_cols
        self.road_geometries = {
            'big': (big_x0, big_y0, big_cell, 6, self.big_road_view_cols),
        }
        self._draw_road_grid(*self.road_geometries['big'])
        self._draw_big_road_scrollbar(big_x0, big_y0 + 6 * big_cell + 5, panel_w)

        # ----- Row 2: exact equal halves, with one centred gutter.
        row2_y = 240
        gutter = 6
        half_w = (panel_w - gutter) / 2
        derived_cols = 14
        derived_cell = half_w / derived_cols
        self.road_geometries['eye'] = (
            panel_x0, row2_y, derived_cell, 6, derived_cols)
        self.road_geometries['cockroach'] = (
            panel_x0 + half_w + gutter, row2_y, derived_cell, 6, derived_cols)
        self._draw_road_grid(*self.road_geometries['eye'])
        self._draw_road_grid(*self.road_geometries['cockroach'])

        # ----- Row 3: Bead Plate.  V10 used 36 px cells; V11 uses 27 px
        # cells (25% smaller) and expands the logical width from 9 to 12.
        bead_cols = 12
        bead_cell = 27
        bead_w = bead_cell * bead_cols
        bead_x0 = panel_x0 + (panel_w - bead_w) / 2
        bead_y0 = 320
        self.road_geometries['bead'] = (bead_x0, bead_y0, bead_cell, 6, bead_cols)
        self._draw_road_grid(*self.road_geometries['bead'])

        # ----- Row 4: Small Road 5/8 | Next indicator 3/8.
        row4_y = 490
        row4_h = 66
        row4_gutter = 6
        usable = panel_w - row4_gutter
        small_w = usable * 5 / 8
        next_w = usable - small_w
        small_cols = 20
        small_cell = small_w / small_cols
        self.road_geometries['small'] = (
            panel_x0, row4_y, small_cell, 6, small_cols)
        self._draw_road_grid(*self.road_geometries['small'])

        nx0 = panel_x0 + small_w + row4_gutter
        nx1 = panel_x1
        ny0, ny1 = row4_y, row4_y + row4_h
        c.create_rectangle(nx0, ny0, nx1, ny1, fill='#15110f', outline='#7c6754',
                           width=1, tags='history_panel_content')
        # No "大眼仔 / 小路 / 蟑螂路" explanatory labels.  Only Player and
        # Banker headers remain; the three symbol rows follow the standard order.
        mid_x = (nx0 + nx1) / 2
        header_h = 18
        c.create_line(mid_x, ny0, mid_x, ny1, fill='#514338',
                      tags='history_panel_content')
        c.create_line(nx0, ny0 + header_h, nx1, ny0 + header_h,
                      fill='#7c6754', tags='history_panel_content')
        body_h = ny1 - ny0 - header_h
        row_h = body_h / 3
        for i in range(1, 3):
            y = ny0 + header_h + i * row_h
            c.create_line(nx0, y, nx1, y, fill='#514338', tags='history_panel_content')
        c.create_text((nx0 + mid_x) / 2, ny0 + header_h / 2, text='闲',
                      font=('Arial', 8, 'bold'), fill=self.PLAYER_BLUE,
                      tags='history_panel_content')
        c.create_text((mid_x + nx1) / 2, ny0 + header_h / 2, text='庄',
                      font=('Arial', 8, 'bold'), fill=self.BANKER_RED,
                      tags='history_panel_content')
        self.next_indicator_geometry = {
            'x0': nx0, 'x1': nx1, 'mid_x': mid_x,
            'top': ny0 + header_h, 'row_h': row_h,
        }

        self._draw_road_summary(panel_x0, panel_x1, row4_y + row4_h + 32)

    def _draw_road_summary(self, x0, x1, y):
        """Two aligned statistic rows, with the round total centred at the left."""
        c = self.canvas
        c.delete('road_summary')
        tags = ('history_panel_content', 'road_summary')
        self._road_summary_items = {
            'round': c.create_text(x0+36, y, text='#0',
                font=('Arial', -20, 'bold'), fill='white', tags=tags),
        }
        group_width = (x1-x0-72)/3
        for index, (key, caption, color, dots) in enumerate((
                ('Player', '闲', self.PLAYER_BLUE, ()),
                ('Banker', '庄', self.BANKER_RED, ()),
                ('Tie', '和', self.TIE_GREEN, ()),
                ('Pair Player', '', '#8c918e', ((-1,-1,'#145dff'),)),
                ('Pair Banker', '', '#8c918e', ((1,1,'#ff2238'),)),
                ('Twin Pair', '', '#8c918e', ((-1,-1,'#000000'),(1,1,'#000000'))))):
            row, column = divmod(index, 3)
            cy = y-14 if row == 0 else y+14
            cx = x0+72+(column+.5)*group_width-22
            icon_tags = tags+(f'road_summary_{key.replace(" ", "_")}',)
            c.create_oval(cx-12, cy-12, cx+12, cy+12,
                fill=color, outline='#eadfc9', width=1, tags=icon_tags)
            if caption:
                c.create_text(cx, cy, text=caption, font=('Arial', -15, 'bold'),
                    fill='white', tags=icon_tags)
            for dx, dy, dot_color in dots:
                px, py = cx+dx*9, cy+dy*9
                c.create_oval(px-4, py-4, px+4, py+4, fill=dot_color,
                    outline='white', width=1, tags=icon_tags)
            self._road_summary_items[key] = c.create_text(cx+20, cy,
                text='0', anchor='w', font=('Arial', -18, 'bold'),
                fill='white', tags=tags)
        records = self._history_records_for_display()
        self._update_road_summary(self._marker_road_records(records)
                                  if self.game_mode == 'one_deck' else records)

    def _update_road_summary(self, records):
        items = getattr(self, '_road_summary_items', {})
        if not items:
            return
        counts = {'Player': 0, 'Banker': 0, 'Tie': 0,
                  'Pair Player': 0, 'Pair Banker': 0, 'Twin Pair': 0}
        for record in records:
            winner = record.get('winner')
            if winner not in ('Player', 'Banker', 'Tie'):
                continue
            counts[winner] += 1
            p, b = record.get('player_hand') or [], record.get('banker_hand') or []
            player_pair = p[0][1] == p[1][1] if len(p) >= 2 else bool(record.get('player_pair'))
            banker_pair = b[0][1] == b[1][1] if len(b) >= 2 else bool(record.get('banker_pair'))
            counts['Pair Player'] += int(player_pair)
            counts['Pair Banker'] += int(banker_pair)
            # Same definition as the bead plate: four equal opening ranks.
            counts['Twin Pair'] += int(player_pair and banker_pair and len(p) >= 2
                                       and len(b) >= 2 and p[0][1] == b[0][1])
        total = counts['Player']+counts['Banker']+counts['Tie']
        self.canvas.itemconfigure(items['round'], text=f'#{total}')
        for winner, count in counts.items():
            self.canvas.itemconfigure(items[winner], text=str(count))

    def _draw_big_road_scrollbar(self, x0, y0, width):
        """Draw a functional horizontal scrollbar for the 50-column Big Road."""
        c = self.canvas
        self.big_road_scroll_track = (x0, y0, x0 + width, y0 + 10)
        c.create_rectangle(*self.big_road_scroll_track, fill='#30271f',
                           outline='#7c6754', width=1,
                           tags=('history_panel_content', 'bigroad_scroll'))
        # The thumb represents the visible fraction of the 50-column logical road.
        ratio = min(1.0, self.big_road_view_cols / self.big_road_virtual_cols)
        thumb_w = max(28, width * ratio)
        self.big_road_scroll_thumb_width = thumb_w
        self.big_road_scroll_thumb = c.create_rectangle(
            x0, y0 + 1, x0 + thumb_w, y0 + 9,
            fill='#a57e38', outline='#f2d77c', width=1,
            tags=('history_panel_content', 'bigroad_scroll'))
        c.tag_bind('bigroad_scroll', '<Button-1>', self._set_big_road_scroll_from_event)
        c.tag_bind('bigroad_scroll', '<B1-Motion>', self._set_big_road_scroll_from_event)
        c.tag_bind('bigroad_scroll', '<Enter>', lambda _e: c.configure(cursor='sb_h_double_arrow'))
        c.tag_bind('bigroad_scroll', '<Leave>', lambda _e: c.configure(cursor=''))
        self._update_big_road_scroll_thumb()

    def _set_big_road_scroll_from_event(self, event):
        track = getattr(self, 'big_road_scroll_track', None)
        if not track:
            return
        x0, _y0, x1, _y1 = track
        width = x1 - x0
        thumb_w = getattr(self, 'big_road_scroll_thumb_width', width)
        movable = max(1.0, width - thumb_w)
        # Centre the thumb under the pointer for both click and drag.
        thumb_left = min(max(event.x - thumb_w / 2, x0), x1 - thumb_w)
        fraction = (thumb_left - x0) / movable
        max_start = max(0, self.big_road_virtual_cols - self.big_road_view_cols)
        self.big_road_scroll_col = int(round(fraction * max_start))
        self.big_road_auto_follow = False
        self._update_big_road_scroll_thumb()
        self.update_history_table()

    def _update_big_road_scroll_thumb(self):
        if not getattr(self, 'big_road_scroll_thumb', None):
            return
        track = getattr(self, 'big_road_scroll_track', None)
        if not track:
            return
        x0, y0, x1, _y1 = track
        width = x1 - x0
        thumb_w = getattr(self, 'big_road_scroll_thumb_width', width)
        max_start = max(0, self.big_road_virtual_cols - self.big_road_view_cols)
        start = min(max(0, int(self.big_road_scroll_col)), max_start)
        fraction = (start / max_start) if max_start else 0.0
        left = x0 + fraction * max(0.0, width - thumb_w)
        try:
            self.canvas.coords(self.big_road_scroll_thumb,
                               left, y0 + 1, left + thumb_w, y0 + 9)
        except tk.TclError:
            pass

    def _draw_stats_grid(self, x0, y0, x1, y1, rows):
        c = self.canvas
        value_x = x1 - 92
        c.create_rectangle(x0, y0, x1, y1, fill='#15110f', outline='#7c6754',
                           width=1, tags='history_panel_content')
        c.create_line(value_x, y0, value_x, y1, fill='#514338',
                      tags='history_panel_content')
        row_h = (y1 - y0) / max(1, rows)
        for row in range(1, rows):
            y = y0 + row * row_h
            c.create_line(x0, y, x1, y, fill='#3e352f', tags='history_panel_content')
        return {'x0': x0, 'x1': x1, 'value_x': value_x, 'top': y0, 'row_h': row_h}

    def _draw_data_page(self):
        c = self.canvas
        x0, x1 = 786, 1130
        c.create_text(x0, 82, anchor='w',
                      text='最近500局统计' if self.game_mode in BaccaratEngine.SPECIAL_MODES else '本轮统计',
                      font=('Arial', 12, 'bold'), fill=self.GOLD,
                      tags='history_panel_content')
        self.base_stats_geometry = self._draw_stats_grid(x0, 98, x1, 306, 6)

        mode_name = self.MODE_SHORT.get(self.game_mode, self.game_mode)
        self.history_special_title = c.create_text(
            x0, 334, anchor='w', text=f'{mode_name}特殊数据',
            font=('Arial', 12, 'bold'), fill=self.GOLD,
            tags='history_panel_content')
        # Mode-specific special data never exceeds five entries.  Keep exactly
        # five rows and reuse the old sixth-row space for a guarded reshuffle.
        self.special_stats_geometry = self._draw_stats_grid(x0, 350, x1, 550, 5)
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            self.reshuffle_button_rect = None
            self.reshuffle_button_text = None
            c.create_text((x0 + x1) / 2, 574, text=(f'CSM 连续洗牌 · 庄家首张固定{self.game_mode[-1]}'
                                if self.game_mode in BaccaratEngine.ALWAYS_MODES else '单副52张 · 每局重新洗牌'),
                          font=('Arial', 11, 'bold'), fill=self.GOLD,
                          tags='history_panel_content')
        else:
            self._draw_manual_reshuffle_button(x0, 558, x1, 590)

    def _draw_manual_reshuffle_button(self, x0, y0, x1, y1):
        c = self.canvas
        tag = 'manual_reshuffle_button'
        label = '确认再按' if self.reshuffle_confirm_armed else '重新洗牌'
        armed = self.reshuffle_confirm_armed
        self.reshuffle_button_rect = c.create_rectangle(
            x0, y0, x1, y1,
            fill='#d8bd4b' if armed else '#30271f',
            outline='#f2d77c' if armed else '#8d765e', width=2 if armed else 1,
            tags=('history_panel_content', tag))
        self.reshuffle_button_text = c.create_text(
            (x0 + x1) / 2, (y0 + y1) / 2, text=label,
            font=('Arial', 11, 'bold'), fill='#15110d' if armed else '#e7d36c',
            tags=('history_panel_content', tag))
        c.tag_bind(tag, '<Button-1>', self._manual_reshuffle_click)
        c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))

    def _set_manual_reshuffle_button_state(self):
        label = '确认再按' if self.reshuffle_confirm_armed else '重新洗牌'
        armed = self.reshuffle_confirm_armed
        try:
            if self.reshuffle_button_rect is not None:
                self.canvas.itemconfigure(
                    self.reshuffle_button_rect,
                    fill='#d8bd4b' if armed else '#30271f',
                    outline='#f2d77c' if armed else '#8d765e',
                    width=2 if armed else 1)
            if self.reshuffle_button_text is not None:
                self.canvas.itemconfigure(
                    self.reshuffle_button_text, text=label,
                    fill='#15110d' if armed else '#e7d36c')
        except tk.TclError:
            pass

    def _reset_manual_reshuffle_confirm(self):
        self.reshuffle_confirm_after_id = None
        self.reshuffle_confirm_armed = False
        self._set_manual_reshuffle_button_state()

    def _manual_reshuffle_click(self, _event=None):
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            return 'break'
        if self._closing or self.animation_running or self.settlement_running or not self.accept_bets:
            return 'break'

        if not self.reshuffle_confirm_armed:
            self.reshuffle_confirm_armed = True
            self._set_manual_reshuffle_button_state()
            if self.reshuffle_confirm_after_id is not None:
                try:
                    self.after_cancel(self.reshuffle_confirm_after_id)
                except (tk.TclError, ValueError):
                    pass
            # The second click must arrive within ten seconds.
            self.reshuffle_confirm_after_id = self.after(10_000, self._reset_manual_reshuffle_confirm)
            return 'break'

        # Confirmed second click inside the ten-second window.
        if self.reshuffle_confirm_after_id is not None:
            try:
                self.after_cancel(self.reshuffle_confirm_after_id)
            except (tk.TclError, ValueError):
                pass
            self.reshuffle_confirm_after_id = None
        self.reshuffle_confirm_armed = False
        self._set_manual_reshuffle_button_state()
        self._perform_manual_reshuffle()
        return 'break'

    def _perform_manual_reshuffle(self):
        # Return any un-dealt wagers/fees before replacing the shoe, matching
        # the automatic end-of-shoe path so a manual reshuffle cannot consume
        # a pending stake.
        outstanding = self.bet_state.clear_all()
        fee_refund = sum(float(v) for v in self.bet_fee_state.values())
        self.bet_fee_state.clear()
        self._cancel_fee_visuals()
        if outstanding > 0 or fee_refund > 0:
            self.balance += outstanding + fee_refund
            if fee_refund > 0:
                self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee_refund)
        self.undo_stack.clear()
        self.update_display()
        self.start_new_shoe_cut(True)

    def _draw_road_grid(self, x0, y0, cell, rows, cols):
        c = self.canvas
        x1, y1 = x0 + cols * cell, y0 + rows * cell
        c.create_rectangle(x0, y0, x1, y1, fill='#f3efe7', outline='#8d8377',
                           width=1, tags='history_panel_content')
        for r in range(1, rows):
            y = y0 + r * cell
            c.create_line(x0, y, x1, y, fill='#d2cbc1', tags='history_panel_content')
        for col in range(1, cols):
            x = x0 + col * cell
            c.create_line(x, y0, x, y1, fill='#d2cbc1', tags='history_panel_content')

    @staticmethod
    def _place_road_sequence(sequence, rows=6):
        """Lay a logical streak sequence onto a six-row baccarat road.

        ``sequence`` contains ``(value, payload)`` pairs.  Equal consecutive
        values continue downward until the next cell is blocked or the sixth
        row is reached; the streak then turns right on the same row (the
        standard dragon-tail rule).  A changed value starts a new logical
        column at the top.
        """
        placed = []
        occupied = set()
        last_value = None
        row = col = 0
        streak_start_col = -1

        for value, payload in sequence:
            if last_value is None:
                streak_start_col = 0
                row, col = 0, 0
            elif value == last_value:
                below = (row + 1, col)
                if row + 1 < rows and below not in occupied:
                    row += 1
                else:
                    # Dragon tail, or a collision with an earlier tail.
                    next_col = col + 1
                    while (row, next_col) in occupied:
                        next_col += 1
                    col = next_col
            else:
                # A new Player/Banker (or red/blue derived-road) streak starts
                # one logical column to the right of the previous streak.
                streak_start_col += 1
                row, col = 0, streak_start_col
                while (row, col) in occupied:
                    col += 1
                    streak_start_col = col

            occupied.add((row, col))
            placed.append({
                'row': row, 'col': col, 'value': value, 'payload': payload
            })
            last_value = value

        return placed

    def _build_big_road(self, records):
        """Build the standard Baccarat Big Road from chronological hands.

        Ties never advance the road.  They are drawn as green diagonal marks
        on the latest Player/Banker cell.  If a shoe starts with ties, those
        ties occupy the top-left cell until the first non-tie result arrives.
        Pair flags from a Tie hand are also retained on that same Big-Road
        cell, matching the normal scoreboard convention.
        """
        sequence = []
        pending_ties = 0
        pending_player_pair = False
        pending_banker_pair = False

        for record in records:
            winner = record.get('winner')
            player_pair = bool(record.get('player_pair', False))
            banker_pair = bool(record.get('banker_pair', False))

            if winner == 'Tie':
                if sequence:
                    payload = sequence[-1][1]
                    payload['ties'] += 1
                    payload['player_pair'] = payload['player_pair'] or player_pair
                    payload['banker_pair'] = payload['banker_pair'] or banker_pair
                else:
                    pending_ties += 1
                    pending_player_pair = pending_player_pair or player_pair
                    pending_banker_pair = pending_banker_pair or banker_pair
                continue

            if winner not in ('Player', 'Banker'):
                continue

            payload = {
                'record': record,
                'ties': pending_ties,
                'player_pair': player_pair or pending_player_pair,
                'banker_pair': banker_pair or pending_banker_pair,
            }
            pending_ties = 0
            pending_player_pair = False
            pending_banker_pair = False
            sequence.append((winner, payload))

        cells = self._place_road_sequence(sequence)

        # A shoe may currently contain only one or more opening ties.  Standard
        # electronic roads show the green tie slash in the top-left cell even
        # before the first Player/Banker circle exists.
        if not cells and pending_ties:
            return [{
                'row': 0, 'col': 0, 'value': 'TieOnly',
                'payload': {
                    'record': None, 'ties': pending_ties,
                    'player_pair': pending_player_pair,
                    'banker_pair': pending_banker_pair,
                    'tie_only': True,
                },
            }]
        return cells

    def _record_specials_for_mode(self, record, mode):
        if mode == 'ez':
            # Re-evaluate stored hands so historical EZ names and newly
            # introduced Blazing 7s/Cover All stay consistent after upgrading.
            p = record.get('player_hand', [])
            b = record.get('banker_hand', [])
            if len(p) >= 2 and len(b) >= 2:
                ps, bs = BaccaratEngine.score(p), BaccaratEngine.score(b)
                result = dict(record, player_score=ps, banker_score=bs,
                              winner='Player' if ps > bs else 'Banker' if bs > ps else 'Tie')
                return list(BaccaratEngine.side_return_factors(result, 'ez'))
            by_mode = record.get('special_by_mode', {})
            values = by_mode.get('ez', []) if isinstance(by_mode, dict) else []
            if not values and record.get('mode', 'classic') == 'ez':
                values = record.get('specials', [])
            if isinstance(values, list):
                aliases = {'Dragon 7': 'Fortune 7', 'Panda 8': 'Golden 8',
                           'Divine 9': 'Heavenly 9'}
                values = [aliases.get(value, value) for value in values]
                if any(value in ('Fortune 7', 'Golden 8', 'Heavenly 9', 'Blazing 7s')
                       for value in values) and 'Cover All' not in values:
                    values.append('Cover All')
                return values
            return []
        by_mode = record.get('special_by_mode', {})
        if isinstance(by_mode, dict) and mode in by_mode:
            values = by_mode.get(mode, [])
            if isinstance(values, list):
                return values
        # Backward compatibility with older records that only stored the mode
        # in which the hand was originally played.
        if record.get('mode', 'classic') == mode:
            values = record.get('specials', [])
            return values if isinstance(values, list) else []
        return []

    def _special_marker(self, record):
        """Compact marker used by the Bead Plate only.

        The marker is intentionally mode-specific.  Switching from Lucky 7 to
        Tiger therefore re-renders the same historical hand with the marker
        for the newly selected mode instead of leaking another mode's symbol.
        """
        selected = set(self._record_specials_for_mode(record, self.game_mode))
        if self.game_mode == 'lucky7' and ('Super 7' in selected or
                (record.get('player_score') == 7 and record.get('banker_score') == 6)):
            return '7-6'
        if self.game_mode == 'ez':
            for name, marker in (('Blazing 7s', '7'), ('Fortune 7', '7'),
                                 ('Golden 8', '8'), ('Heavenly 9', '9')):
                if name in selected:
                    return marker
            return ''
        priority = (
            ('Super 7', '7'), ('Lucky 7', '7'), ('Dragon 7', '7'),
            ('Big Lucky 6', '6'), ('Small Lucky 6', '6'), ('Lucky 6', '6'),
            ('Big Tiger', '大'), ('Small Tiger', '小'), ('Tiger Tie', '虎'),
            # Pair outcomes never replace the bead text; pair dots are enough.
            ('Panda 8', '8'),
            ('Big Monkey', '猴'), ('Monkey 7', '7'), ('Monkey 6', '6'),
            ('Lucky Monkey', '猴'),
        )
        for name, marker in priority:
            if name in selected:
                return marker
        return ''

    def _derive_road(self, records, offset):
        """Build Big-Eye Boy / Small Road / Cockroach Pig correctly.

        ``offset`` is 1, 2 or 3 respectively.  The calculation uses the
        *logical* Big-Road streak columns with unlimited depth, not the
        six-row rendered cells.  This distinction is essential when a streak
        forms a dragon tail.

        For a new Big-Road column, compare the depth of the immediately
        previous streak with the streak ``offset + 1`` columns back.  For a
        continuation within the same streak, compare the two cells reached by
        moving ``offset`` logical columns left and then one row up.  In the
        unlimited-depth representation that comparison is blue only when the
        reference streak length is exactly one less than the current streak
        length; otherwise it is red.
        """
        if offset not in (1, 2, 3):
            raise ValueError('derived-road offset must be 1, 2 or 3')

        streaks = []
        derived_sequence = []

        for record in records:
            winner = record.get('winner')
            if winner not in ('Player', 'Banker'):
                # Ties do not create marks in any derived road.
                continue

            if not streaks or streaks[-1]['winner'] != winner:
                streaks.append({'winner': winner, 'length': 1})
                column = len(streaks) - 1

                # Big Eye starts on the first hand of column 3 when column 2
                # has only one hand; Small Road on column 4; Cockroach on 5.
                if column < offset + 1:
                    continue

                previous_depth = streaks[column - 1]['length']
                comparison_depth = streaks[column - offset - 1]['length']
                color = 'red' if previous_depth == comparison_depth else 'blue'
            else:
                streaks[-1]['length'] += 1
                column = len(streaks) - 1
                current_depth = streaks[-1]['length']

                # The other possible starting point is row 2 of the minimum
                # required column: col2 for Big Eye, col3 for Small, col4 for
                # Cockroach.
                if column < offset:
                    continue

                reference_depth = streaks[column - offset]['length']
                color = 'blue' if reference_depth == current_depth - 1 else 'red'

            derived_sequence.append((color, {'source': record}))

        return self._place_road_sequence(derived_sequence)

    def _visible_road_cells(self, cells, cols):
        if not cells:
            return [], 0
        max_col = max(cell['col'] for cell in cells)
        shift = max(0, max_col - cols + 1)
        return [cell for cell in cells if shift <= cell['col'] < shift + cols], shift

    def _handle_bead_click(self, event):
        """Toggle Bead Plate labels between result text and winning points."""
        if getattr(self, 'history_panel_mode', None) != 'roads':
            return
        geometry = getattr(self, 'road_geometries', {}).get('bead')
        if not geometry:
            return
        x0, y0, cell, rows, cols = geometry
        x1, y1 = x0 + cols * cell, y0 + rows * cell
        if x0 <= event.x <= x1 and y0 <= event.y <= y1:
            self.bead_show_scores = not bool(getattr(self, 'bead_show_scores', False))
            self.update_history_table()

    def _history_records_for_display(self):
        """Big/derived roads and Data use the chosen mode's 500-hand section."""
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            history = self.one_deck_store[self._mode_storage_key('temp_finish_data')]
            return list(history['records'][-self.MAX_RECORDS:])
        return list(self.history_data[-self._history_limit():])

    def _marker_road_records(self, records):
        """The exact records visible in the Marker Road / Bead Plate grid."""
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            # Only Marker Road and its bottom counters consume this section.
            return list(self.one_deck_store[self._mode_storage_key('72_games')]['records'])
        rows, capacity = 6, 72

        # V12: a real bead plate scrolls by a complete 6-hand column, not by
        # one hand.  With a 12 x 6 board, hands 1..72 fill the board.  Hand 73
        # hides hands 1..6, shifts hands 7..72 one column left, and enters at
        # the top of the newest column.  The next shift occurs at hand 79.
        total = len(records)
        if total <= capacity:
            start = 0
        else:
            overflow = total - capacity
            hidden_columns = (overflow + rows - 1) // rows  # ceil(overflow / 6)
            start = hidden_columns * rows
        return list(records[start:start + capacity])

    def _draw_bead_plate(self, records):
        x0, y0, cell, rows, cols = self.road_geometries['bead']

        for index, record in enumerate(records):
            row = index % rows
            col = index // rows
            cx = x0 + col * cell + cell / 2
            cy = y0 + row * cell + cell / 2
            winner = record.get('winner')
            color = self.result_color(winner)
            radius = max(6, cell * 0.39)
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                    fill=color, outline='#ffffff', width=1,
                                    tags='history_dynamic')
            if getattr(self, 'bead_show_scores', False):
                if winner == 'Player':
                    text = str(int(record.get('player_score', 0)))
                elif winner == 'Banker':
                    text = str(int(record.get('banker_score', 0)))
                elif winner == 'Tie':
                    # A tie has the same score on both sides; use that tied value.
                    text = str(int(record.get('player_score', record.get('banker_score', 0))))
                else:
                    text = ''
            else:
                marker = self._special_marker(record)
                text = marker or {'Player': '闲', 'Banker': '庄', 'Tie': '和'}.get(winner, '')
            self.canvas.create_text(cx, cy, text=text, font=('Arial', 10 if text == '7-6' else 12, 'bold'),
                                    fill='white', tags='history_dynamic')

            # Pair markers remain dots only (never text), with stronger colour,
            # a larger radius and a white rim so they remain visible on the bead.
            pair_r = max(4.0, cell * 0.155)
            inset = radius * 0.76
            p = record.get('player_hand') or []
            b = record.get('banker_hand') or []
            # Twin pairs require the same rank on all four opening cards;
            # suits and any third cards are irrelevant. Old records without
            # card details keep their ordinary pair colours.
            twin_pair = (len(p) >= 2 and len(b) >= 2
                         and p[0][1] == p[1][1] == b[0][1] == b[1][1])
            if record.get('player_pair'):
                px, py = cx - inset, cy - inset
                self.canvas.create_oval(px - pair_r, py - pair_r, px + pair_r, py + pair_r,
                                        fill='#000000' if twin_pair else '#145dff',
                                        outline='#ffffff', width=2,
                                        tags='history_dynamic')
            if record.get('banker_pair'):
                px, py = cx + inset, cy + inset
                self.canvas.create_oval(px - pair_r, py - pair_r, px + pair_r, py + pair_r,
                                        fill='#000000' if twin_pair else '#ff2238',
                                        outline='#ffffff', width=2,
                                        tags='history_dynamic')

    def _draw_big_road(self, cells):
        x0, y0, cell, rows, _view_cols = self.road_geometries['big']
        virtual_cols = self.big_road_virtual_cols
        view_cols = self.big_road_view_cols

        # A shoe virtually owns 50 columns.  In the unlikely event the logical
        # road exceeds 50 columns, retain the newest 50 rather than drawing over
        # neighbouring panels.
        max_data_col = max((item['col'] for item in cells), default=-1)
        base_col = max(0, max_data_col - virtual_cols + 1)
        local_cells = []
        for item in cells:
            local_col = item['col'] - base_col
            if 0 <= local_col < virtual_cols:
                copied = dict(item)
                copied['local_col'] = local_col
                local_cells.append(copied)

        latest_local = max((item['local_col'] for item in local_cells), default=0)
        max_start = max(0, virtual_cols - view_cols)
        if self.big_road_auto_follow:
            self.big_road_scroll_col = min(max_start, max(0, latest_local - view_cols + 1))
        else:
            self.big_road_scroll_col = min(max_start, max(0, int(self.big_road_scroll_col)))
        start_col = self.big_road_scroll_col
        self._update_big_road_scroll_thumb()

        for item in local_cells:
            if not (start_col <= item['local_col'] < start_col + view_cols):
                continue
            row = item['row']
            col = item['local_col'] - start_col
            cx = x0 + col * cell + cell / 2
            cy = y0 + row * cell + cell / 2
            payload = item['payload']
            ties = int(payload.get('ties', 0))
            winner = item['value']
            radius = cell * 0.37

            if winner in ('Player', 'Banker'):
                color = self.PLAYER_BLUE if winner == 'Player' else self.BANKER_RED
                self.canvas.create_oval(
                    cx - radius, cy - radius, cx + radius, cy + radius,
                    fill='', outline=color, width=2, tags='history_dynamic')

            if ties:
                self.canvas.create_line(
                    cx - radius + 1, cy + radius - 1,
                    cx + radius - 1, cy - radius + 1,
                    fill=self.TIE_GREEN, width=2, tags='history_dynamic')

            # Big Road has no special-play marker; only standard pair dots.
            pair_r = max(1.7, cell * 0.12)
            if payload.get('player_pair'):
                px, py = cx - radius * 0.78, cy - radius * 0.78
                self.canvas.create_oval(px-pair_r, py-pair_r, px+pair_r, py+pair_r,
                                        fill=self.PLAYER_BLUE, outline='',
                                        tags='history_dynamic')
            if payload.get('banker_pair'):
                px, py = cx + radius * 0.78, cy + radius * 0.78
                self.canvas.create_oval(px-pair_r, py-pair_r, px+pair_r, py+pair_r,
                                        fill=self.BANKER_RED, outline='',
                                        tags='history_dynamic')

            if ties > 1:
                # Match the road display: a large dark count is centred on
                # the ring and layered over the green slash. Fit longer
                # counts inside the same circle without changing cell size.
                count = str(ties)
                count_size = max(8, round(cell * min(0.68, 1.05 / len(count))))
                self.canvas.create_text(
                    cx, cy, text=count, anchor='center',
                    font=('Arial', -count_size, 'bold'),
                    fill='#222222', tags='history_dynamic')

    def _draw_derived_road(self, key, cells, style):
        x0, y0, cell, rows, cols = self.road_geometries[key]
        visible, shift = self._visible_road_cells(cells, cols)
        for item in visible:
            row, col = item['row'], item['col'] - shift
            cx = x0 + col * cell + cell / 2
            cy = y0 + row * cell + cell / 2
            color = '#d83838' if item['value'] == 'red' else '#2766c5'
            radius = max(2.5, cell * 0.32)
            if style == 'ring':
                self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                        fill='', outline=color, width=2, tags='history_dynamic')
            elif style == 'dot':
                # Small Road uses a true solid circle (not a diamond/square).
                dot_r = max(3.0, cell * 0.30)
                self.canvas.create_oval(cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r,
                                        fill=color, outline=color, width=1,
                                        tags='history_dynamic')
            else:
                self.canvas.create_line(cx - radius, cy + radius, cx + radius, cy - radius,
                                        fill=color, width=2, tags='history_dynamic')

    def _draw_round_statistics(self, records):
        c = self.canvas
        counts = {'Player': 0, 'Banker': 0, 'Tie': 0, 'player_pair': 0, 'banker_pair': 0}
        for record in records:
            winner = record.get('winner')
            if winner in ('Player', 'Banker', 'Tie'):
                counts[winner] += 1
            if record.get('player_pair'):
                counts['player_pair'] += 1
            if record.get('banker_pair'):
                counts['banker_pair'] += 1

        geo = self.base_stats_geometry
        base_items = [
            ('总局', len(records)), ('闲', counts['Player']), ('庄', counts['Banker']),
            ('和', counts['Tie']), ('闲对', counts['player_pair']), ('庄对', counts['banker_pair']),
        ]
        base_colors = ['#d4c3a9', self.PLAYER_BLUE, self.BANKER_RED,
                       self.TIE_GREEN, '#77a2ff', '#ff898d']
        for row, ((label, value), color) in enumerate(zip(base_items, base_colors)):
            y = geo['top'] + geo['row_h'] * (row + 0.5)
            c.create_text(geo['x0'] + 10, y, anchor='w', text=label,
                          font=('Arial', 10, 'bold'), fill=color, tags='history_dynamic')
            c.create_text((geo['value_x'] + geo['x1']) / 2, y, text=str(value),
                          font=('Arial', 11, 'bold'), fill='#f2eadf', tags='history_dynamic')

        # Every completed hand is evaluated against every game mode when saved,
        # so switching modes reveals that mode's special results even if the hand
        # was originally dealt while another mode was selected.
        special_counts = {}
        for record in records:
            for name in self._record_specials_for_mode(record, self.game_mode):
                special_counts[name] = special_counts.get(name, 0) + 1

        mode_name = self.MODE_SHORT.get(self.game_mode, self.game_mode)
        if getattr(self, 'history_special_title', None):
            try:
                c.itemconfigure(self.history_special_title, text=f'{mode_name}特殊数据')
            except tk.TclError:
                pass
        specials = self.SPECIAL_STATS.get(self.game_mode, ())
        short_names = {
            'Fortune 7': '财运7', 'Golden 8': '金甲8', 'Heavenly 9': '天上9',
            'Blazing 7s': '双7', 'Cover All': '五宝全包',
            'Small Tiger': '小老虎', 'Tiger Tie': '老虎和', 'Big Tiger': '大老虎',
            'Tiger Pair': '虎对子', 'Panda 8': '熊猫8', 'Divine 9': '神之9',
            'Dragon 7': '金龙7', 'Small Lucky 6': '小幸运6', 'Lucky 6': '幸运6',
            'Big Lucky 6': '大幸运6', 'Lucky 7': '幸运7', 'Super 7': '超级7',
            'Monkey 6': '猴6', 'Monkey Tie': '猴和', 'Big Monkey': '大猴',
            'Monkey 7': '猴7', 'Lucky Monkey': '幸运猴',
        }
        geo = self.special_stats_geometry
        if not specials:
            y = geo['top'] + geo['row_h'] * 0.5
            c.create_text(geo['x0'] + 10, y, anchor='w', text='无特殊数据',
                          font=('Arial', 10, 'bold'), fill='#8e877f', tags='history_dynamic')
            c.create_text((geo['value_x'] + geo['x1']) / 2, y, text='—',
                          font=('Arial', 11, 'bold'), fill='#8e877f', tags='history_dynamic')
        else:
            for row in range(5):
                y = geo['top'] + geo['row_h'] * (row + 0.5)
                if row < len(specials):
                    name = specials[row]
                    c.create_text(geo['x0'] + 10, y, anchor='w', text=short_names.get(name, name),
                                  font=('Arial', 9, 'bold'), fill='#e7dfd5', tags='history_dynamic')
                    c.create_text((geo['value_x'] + geo['x1']) / 2, y,
                                  text=str(special_counts.get(name, 0)),
                                  font=('Arial', 11, 'bold'), fill='#f2eadf', tags='history_dynamic')

    def update_history_table(self):
        if not hasattr(self, 'canvas'):
            return
        self.canvas.delete('history_dynamic')
        # temp_finish_data records are stored oldest -> newest.  Roadmaps must
        # be built in that same chronological order (V8 accidentally reversed
        # them, which made every road structurally wrong).
        history_records = self._history_records_for_display()
        if self.history_panel_mode == 'data':
            self._draw_round_statistics(history_records)
            return
        marker_records = self._marker_road_records(history_records)
        big_cells = self._build_big_road(history_records)
        self._draw_big_road(big_cells)
        self._draw_derived_road('eye', self._derive_road(history_records, 1), 'ring')
        self._draw_derived_road('cockroach', self._derive_road(history_records, 3), 'slash')
        self._draw_bead_plate(marker_records)
        self._draw_derived_road('small', self._derive_road(history_records, 2), 'dot')
        self._draw_next_round_indicator(history_records)
        self._update_road_summary(marker_records if self.game_mode in BaccaratEngine.SPECIAL_MODES
                                  else history_records)

    def _next_road_color(self, records, candidate, offset):
        simulated = list(records) + [{
            'winner': candidate, 'player_pair': False, 'banker_pair': False,
            'mode': self.game_mode, 'specials': [],
        }]
        before = self._derive_road(records, offset)
        after = self._derive_road(simulated, offset)
        if len(after) <= len(before):
            return None
        return after[-1]['value']

    def _draw_indicator_symbol(self, cx, cy, color_name, style):
        if color_name not in ('red', 'blue'):
            self.canvas.create_text(cx, cy, text='—', font=('Arial', 9), fill='#766d64',
                                    tags='history_dynamic')
            return
        color = '#d83838' if color_name == 'red' else '#2766c5'
        radius = 5
        if style == 'ring':
            self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                    fill='', outline=color, width=2, tags='history_dynamic')
        elif style == 'dot':
            self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                                    fill=color, outline=color, width=1,
                                    tags='history_dynamic')
        else:
            self.canvas.create_line(cx-radius, cy+radius, cx+radius, cy-radius,
                                    fill=color, width=2, tags='history_dynamic')

    def _draw_next_round_indicator(self, records):
        geo = self.next_indicator_geometry
        # Fixed row order: Big Eye Boy, Small Road, Cockroach Pig.  V11 omits
        # their text labels; the user sees only the predicted symbols under 闲/庄.
        specs = [(1, 'ring'), (2, 'dot'), (3, 'slash')]
        player_cx = (geo['x0'] + geo['mid_x']) / 2
        banker_cx = (geo['mid_x'] + geo['x1']) / 2
        for row, (offset, style) in enumerate(specs):
            cy = geo['top'] + geo['row_h'] * (row + 0.5)
            self._draw_indicator_symbol(player_cx, cy,
                                        self._next_road_color(records, 'Player', offset), style)
            self._draw_indicator_symbol(banker_cx, cy,
                                        self._next_road_color(records, 'Banker', offset), style)

    def find_original_card_asset_dir(self):
        """Locate the original Baccarat.py A_Tools/Card/Poker1 directory."""
        current = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(current, 'A_Tools', 'Card', 'Poker1'),
            os.path.join(os.path.dirname(current), 'A_Tools', 'Card', 'Poker1'),
            os.path.join(os.path.dirname(os.path.dirname(current)), 'A_Tools', 'Card', 'Poker1'),
        ]
        for directory in candidates:
            if os.path.isdir(directory):
                return directory
        return None

    def load_original_card_assets(self):
        """Load faces independently, preserving a supplied background.png back."""
        self.external_card_pil = {}
        self.external_back_pil = None
        self.card_back_path = None
        if Image is None or ImageTk is None:
            return
        card_size = (100, 140)
        directory = self.find_original_card_asset_dir()
        self.card_asset_dir = directory
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        # A back next to this script may override the project's shared artwork.
        # Lower-case spelling is checked first on case-sensitive filesystems.
        back_dirs = [os.path.dirname(os.path.abspath(__file__))]
        if directory and directory not in back_dirs:
            back_dirs.append(directory)
        for back_dir in back_dirs:
            if self.external_back_pil is not None:
                break
            for name in ('background.png', 'Background.png'):
                path = os.path.join(back_dir, name)
                if not os.path.isfile(path):
                    continue
                try:
                    with Image.open(path) as source:
                        self.external_back_pil = source.convert('RGBA').resize(card_size, resample)
                    self.card_back_path = path
                    break
                except (OSError, ValueError):
                    continue
        if self.external_back_pil is None:
            self.external_back_pil = self._make_fallback_card_pil(None, face_up=False)
        self.external_back_image = ImageTk.PhotoImage(self.external_back_pil, master=self)
        self._rotated_back_image = None
        for suit in BaccaratEngine.SUITS:
            for rank in BaccaratEngine.RANKS:
                card = (suit, rank)
                base = None
                path = os.path.join(directory, f'{suit}{rank}.png') if directory else ''
                if os.path.isfile(path):
                    try:
                        with Image.open(path) as source:
                            base = source.convert('RGBA').resize(card_size, resample)
                    except (OSError, ValueError):
                        pass
                if base is None:
                    base = self._make_fallback_card_pil(card, face_up=True)
                self.external_card_pil[card] = base
                self.external_card_images[card] = ImageTk.PhotoImage(base, master=self)
                self.external_card_images_rotated[card] = ImageTk.PhotoImage(
                    base.rotate(90, expand=True), master=self)

    def load_always_card_assets(self):
        """CSM art is exclusively Poker2; fixed-card art may also live in Card/."""
        self.poker2_card_pil = {}
        self.poker2_card_images = {}
        self.poker2_card_images_rotated = {}
        self.poker2_back_pil = None
        self.poker2_back_image = None
        self._poker2_rotated_back_image = None
        self.always_card_pil = {}
        self.always_card_images = {}
        current = os.path.dirname(os.path.abspath(__file__))
        candidates = [os.path.join(base, 'A_Tools', 'Card', 'Poker2')
                      for base in (current, os.path.dirname(current),
                                   os.path.dirname(os.path.dirname(current)))]
        if self.card_asset_dir:
            candidates.insert(0, os.path.join(os.path.dirname(self.card_asset_dir), 'Poker2'))
        candidates.extend((os.path.join(current, 'Poker2'),
                           os.path.join(current, '..', 'Card', 'Poker2')))
        self.poker2_asset_dir = next((p for p in candidates if os.path.isdir(p)), None)
        if Image is None or ImageTk is None:
            return
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        directory = self.poker2_asset_dir

        def read(path):
            if path and os.path.isfile(path):
                try:
                    with Image.open(path) as source:
                        return source.convert('RGBA').resize((100, 140), resample)
                except (OSError, ValueError):
                    pass
            return None

        for suit in BaccaratEngine.SUITS:
            for rank in BaccaratEngine.RANKS:
                card = (suit, rank)
                base = read(os.path.join(directory, f'{suit}{rank}.png') if directory else None)
                if base is None:
                    base = self._make_fallback_card_pil(card)
                self.poker2_card_pil[card] = base
                self.poker2_card_images[card] = ImageTk.PhotoImage(base, master=self)
                self.poker2_card_images_rotated[card] = ImageTk.PhotoImage(base.rotate(90, expand=True), master=self)
        for name in ('background.png', 'Background.png'):
            self.poker2_back_pil = read(os.path.join(directory, name) if directory else None)
            if self.poker2_back_pil is not None:
                break
        if self.poker2_back_pil is None:
            self.poker2_back_pil = self._make_fallback_card_pil(None, face_up=False)
        self.poker2_back_image = ImageTk.PhotoImage(self.poker2_back_pil, master=self)
        for mode in BaccaratEngine.ALWAYS_MODES:
            filename = f'Always{mode[-1]}.png'
            paths = ([os.path.join(directory, filename),
                      os.path.join(os.path.dirname(directory), filename)] if directory else [])
            paths.append(os.path.join(current, filename))
            base = next((art for path in paths if (art := read(path)) is not None), None)
            if base is None:
                base = self.poker2_card_pil[('Spade', mode[-1])]
            self.always_card_pil[mode] = base
            self.always_card_images[mode] = ImageTk.PhotoImage(base, master=self)

    def _card_back_pil(self):
        return (getattr(self, 'poker2_back_pil', None) if self.game_mode in BaccaratEngine.ALWAYS_MODES
                else getattr(self, 'external_back_pil', None))

    def _draw_fixed_banker_card(self, preview=False):
        if self.game_mode not in BaccaratEngine.ALWAYS_MODES:
            return
        card = ('Spade', self.game_mode[-1])
        if not preview and self.current_result:
            card = tuple(self.current_result['banker_hand'][0])
        self._card_face_turns[('Banker', 0)] = 0
        self.draw_card('Banker', 0, card, face_up=True)
        self.revealed_cards['Banker'] = [card]
        self.canvas.itemconfigure(self.banker_score_text, text=str(BaccaratEngine.card_value(card)))


    def load_golden_card_assets(self):
        """Load A_Tools/Card/Poker1/Golden face art for Treasure Pot.

        The Golden directory is expected to use the same ``SuitRank.png`` names
        as Poker1.  If it is absent during development, generate a visibly gold
        fallback so the game remains testable without project assets.
        """
        if Image is None or ImageTk is None:
            return
        self.golden_card_pil = {}
        self.golden_card_images = {}
        self.golden_card_images_rotated = {}
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        golden_dir = os.path.join(self.card_asset_dir, 'Golden') if self.card_asset_dir else None
        for suit in BaccaratEngine.SUITS:
            for rank in BaccaratEngine.RANKS:
                card = (suit, rank)
                base = None
                if golden_dir:
                    path = os.path.join(golden_dir, f'{suit}{rank}.png')
                    if os.path.exists(path):
                        try:
                            base = Image.open(path).convert('RGBA').resize((100, 140), resample)
                        except Exception:
                            base = None
                if base is None:
                    normal = self.external_card_pil.get(card)
                    if normal is not None:
                        base = normal.copy()
                        draw = ImageDraw.Draw(base) if ImageDraw is not None else None
                        if draw is not None:
                            draw.rounded_rectangle((2, 2, 97, 137), radius=8,
                                                   outline='#f5cf35', width=6)
                            draw.rounded_rectangle((7, 7, 92, 132), radius=6,
                                                   outline='#fff2a0', width=2)
                            draw.ellipse((69, 6, 94, 31), fill='#e6b820',
                                         outline='#fff0a3', width=2)
                            try:
                                font = ImageFont.truetype('DejaVuSans-Bold.ttf', 10)
                            except Exception:
                                font = None
                            draw.text((81.5, 18.5), 'G', fill='#3d2c00',
                                      font=font, anchor='mm')
                if base is None:
                    continue
                self.golden_card_pil[card] = base
                self.golden_card_images[card] = ImageTk.PhotoImage(base, master=self)
                self.golden_card_images_rotated[card] = ImageTk.PhotoImage(
                    base.rotate(90, expand=True), master=self)

    def _is_current_golden(self, card):
        return self.game_mode in ('treasure', 'xxx') and tuple(card) in self.current_golden_map

    def _make_fallback_card_pil(self, card, face_up=True):
        image = Image.new('RGBA', (100, 140), '#f4efe4' if face_up else '#253e66')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((2, 2, 97, 137), radius=8,
                               outline='#d7cbb9' if face_up else '#d7c46a', width=3)
        if not face_up:
            draw.rectangle((12, 12, 87, 127), outline='#e4d490', width=2)
            draw.line((16, 16, 83, 123), fill='#e4d490', width=2)
            draw.line((83, 16, 16, 123), fill='#e4d490', width=2)
            return image
        suit, rank = card
        suit_map = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}
        color = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
        try:
            font_big = ImageFont.truetype('DejaVuSans-Bold.ttf', 30)
            font_suit = ImageFont.truetype('DejaVuSans.ttf', 28)
        except Exception:
            font_big = None
            font_suit = None
        draw.text((8, 6), str(rank), fill=color, font=font_big)
        draw.text((9, 42), suit_map.get(suit, suit[:1]), fill=color, font=font_suit)
        draw.text((50, 88), suit_map.get(suit, suit[:1]), fill=color, font=font_suit,
                  anchor='mm')
        return image

    def card_position(self, hand_type, index):
        """100x140 layout: first two cards have a 10px edge gap; third card is centred over them."""
        x0, y0, _x1, _y1 = self.animation_panel
        normal_y = y0 + 82
        rotated_y = y0 + 172
        if hand_type == 'Player':
            # P0 is the right card; P1 sits 10px to its left.
            p0_x = x0 + 246
            p1_x = p0_x - 110
            mid_centre = ((p0_x + 50) + (p1_x + 50)) / 2
            positions = {
                0: (p0_x, normal_y),
                1: (p1_x, normal_y),
                2: (mid_centre - 70, rotated_y),
            }
        else:
            # B0 is the left card; B1 sits 10px to its right.
            b0_x = x0 + 402
            b1_x = b0_x + 110
            mid_centre = ((b0_x + 50) + (b1_x + 50)) / 2
            positions = {
                0: (b0_x, normal_y),
                1: (b1_x, normal_y),
                2: (mid_centre - 70, rotated_y),
            }
        return positions.get(index, positions[0])

    def draw_animation_panel(self):
        c = self.canvas
        x0, y0, x1, y1 = self.CARD_AREA_BOUNDS
        c.create_rectangle(x0, y0, x1, y1, fill=self.PANEL,
                           outline=self.PANEL_LINE, width=2, tags='static')
        self.animation_panel = (x0, y0, x1, y1)
        self.animation_phase_text = c.create_text(
            (x0 + x1) / 2, y0 + 18, text='百家乐 BACCARAT',
            font=('Arial', 16, 'bold'), fill='#d4c3a9', tags='animation')

        self.player_zone_rect = c.create_rectangle(
            x0 + 10, y0 + 38, x0 + 366, y1 - 7,
            fill=self.PLAYER_ZONE_BASE, outline='#6386a5', width=2, tags='animation')
        self.banker_zone_rect = c.create_rectangle(
            x0 + 382, y0 + 38, x1 - 10, y1 - 7,
            fill=self.BANKER_ZONE_BASE, outline='#a56a6d', width=2, tags='animation')
        self.player_zone_label = c.create_text(
            x0 + 24, y0 + 53, anchor='w', text='闲 PLAYER',
            font=('Arial', 24, 'bold'), fill='#93b9ff', tags='animation')
        self.banker_zone_label = c.create_text(
            x0 + 396, y0 + 53, anchor='w', text='庄 BANKER',
            font=('Arial', 24, 'bold'), fill='#ffaaaa', tags='animation')

        p1_x, p1_y = self.card_position('Player', 1)
        b1_x, b1_y = self.card_position('Banker', 1)
        self.player_score_text = c.create_text(
            p1_x - 12, p1_y + 70, anchor='e', text='0',
            font=('Arial', 86, 'bold'), fill='white', tags='animation')
        self.banker_score_text = c.create_text(
            b1_x + 112, b1_y + 70, anchor='w', text='0',
            font=('Arial', 86, 'bold'), fill='white', tags='animation')
        # Retained only as an invisible compatibility item for older helper calls.
        # V17 keeps the Tie strip disabled; Tie is shown only by flashing both card zones.
        self.tie_flash_rect = c.create_rectangle(
            0, 0, 0, 0, fill=self.TIE_FLASH_DARK, outline='',
            state='hidden', tags='animation')
        self.card_item_ids = []
        self.revealed_cards = {'Player': [], 'Banker': []}
        self._temp_flip_images = {}

    def clear_card_display(self):
        self._clear_squeeze_display()
        for item in self.card_item_ids:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self.card_item_ids = []
        self._temp_flip_images = {}
        self._card_face_turns = {}
        self._turned_card_images = {}
        self.canvas.delete('dealt_golden_multiplier')
        self.canvas.delete('golden_light')
        self._golden_activated_slots = {}
        self.revealed_cards = {'Player': [], 'Banker': []}
        self.canvas.itemconfigure(self.player_score_text, text='0')
        self.canvas.itemconfigure(self.banker_score_text, text='0')

    @staticmethod
    def card_text(card):
        suit, rank = card
        suit_map = {'Club': '♣', 'Diamond': '♦', 'Heart': '♥', 'Spade': '♠'}
        return f'{rank}\n{suit_map.get(suit, suit[:1])}'

    def draw_card(self, hand_type, index, card, face_up=True):
        """Draw one card at the Baccarat 100x140 display size."""
        x, y = self.card_position(hand_type, index)
        rotated = index == 2
        image = None
        if face_up:
            image = self._face_photo(card, rotated=rotated, hand_type=hand_type, index=index)
        else:
            image = self._back_photo(rotated)
        if image is not None:
            item = self.canvas.create_image(x, y, image=image, anchor='nw',
                                            tags=('animation_card', 'animation'))
            self.card_item_ids.append(item)
            return item

        # Last resort if Pillow is unavailable.
        w, h = (140, 100) if rotated else (100, 140)
        fill = '#f4efe4' if face_up else '#253e66'
        outline = '#d7cbb9' if face_up else '#d7c46a'
        rect = self.canvas.create_rectangle(x, y, x + w, y + h, fill=fill,
                                            outline=outline, width=2,
                                            tags=('animation_card', 'animation'))
        if face_up:
            suit, _rank = card
            fg = '#c22631' if suit in ('Diamond', 'Heart') else '#111111'
            text = self.card_text(card)
        else:
            fg, text = '#e4d490', '◆\\n◆'
        tid = self.canvas.create_text(x + w / 2, y + h / 2, text=text,
                                      font=('Arial', 20, 'bold'), fill=fg,
                                      justify='center',
                                      angle=((90 if rotated else 0) +
                                             (self._card_face_turn(hand_type, index) if face_up else 0)) % 360,
                                      tags=('animation_card', 'animation'))
        self.card_item_ids.extend((rect, tid))
        return rect

    def draw_board(self):
        c = self.canvas
        c.create_rectangle(*self.BOARD_BOUNDS, fill=self.FELT,
                           outline=self.LINE, width=2, tags='static')
        self.draw_mode_selector()
        self.draw_mode_betting_board()
        self.draw_banker_selector()
        self.draw_squeeze_selector()

    def _current_banker_rule(self, mode=None):
        mode = mode or self.game_mode
        preferred = getattr(self, '_banker_rule_preferences', {}).get(mode)
        return BaccaratEngine.banker_rule_for_mode(mode, preferred)

    def _board_odds(self, mode=None):
        mode = mode or self.game_mode
        odds = dict(BaccaratEngine.ODDS_TEXT[mode])
        if mode in BaccaratEngine.ALWAYS_MODES:
            return odds
        rule = self._current_banker_rule(mode)
        odds['Banker'] = BaccaratEngine.BANKER_RULE_ODDS_TEXT[rule]
        return odds

    def draw_banker_selector(self):
        """Use the same rounded rail and gold sliding thumb as game modes."""
        y = self.BOARD_HEADER_Y
        self._banker_selector_y = y
        self._draw_sliding_selector('banker_selector',
            list(zip(BaccaratEngine.BANKER_RULES, ('经典', '免佣', 'EZ'))),
            (522, y-16, 670, y+16), self._current_banker_rule(),
            self._select_banker_rule, font_size=12)
        self._update_banker_selector(animate=False)

    def _update_banker_selector(self, enabled=None, animate=True):
        control = self.__dict__.get('_segmented_controls', {}).get('banker_selector')
        if control is None:
            return
        allowed = BaccaratEngine.banker_rules_for_mode(self.game_mode)
        control['allowed'] = set(allowed)
        hidden = self.game_mode in BaccaratEngine.ALWAYS_MODES
        if enabled is None:
            enabled = self.accept_bets and not self.animation_running and not self.settlement_running
        self._banker_selector_enabled = bool(enabled and len(allowed) > 1 and not hidden and not self._closing)
        self._set_sliding_selector('banker_selector', self._current_banker_rule(),
            enabled=self._banker_selector_enabled, animate=animate and not hidden)
        self.canvas.itemconfigure('banker_selector', state='hidden' if hidden else 'normal')

    def _select_banker_rule(self, rule):
        allowed = BaccaratEngine.banker_rules_for_mode(self.game_mode)
        if (self._closing or not self.accept_bets or self.animation_running or self.settlement_running
                or len(allowed) < 2 or rule not in allowed):
            return 'break'
        if not hasattr(self, '_banker_rule_preferences'):
            self._banker_rule_preferences = dict(BaccaratEngine.DEFAULT_BANKER_RULES)
        self._banker_rule_preferences[self.game_mode] = rule
        self.banker_rule = self._current_banker_rule()
        self._update_banker_selector()
        self._refresh_banker_bet_odds()
        self.update_history_table()
        return 'break'

    def _refresh_banker_bet_odds(self, result=None):
        spot = self.bet_spots.get(('Banker', None))
        if not spot:
            return
        if self.game_mode in BaccaratEngine.ALWAYS_MODES:
            spot['base_odds'] = BaccaratEngine.ODDS_TEXT[self.game_mode]['Banker']
            self.canvas.itemconfigure(spot['odds_item'], text=spot['base_odds'])
            return
        rule = self._current_banker_rule()
        spot['base_odds'] = BaccaratEngine.BANKER_RULE_ODDS_TEXT[rule]
        if self.game_mode == '2to1':
            self._update_2to1_multiplier_ribbon(result)
            return
        self.canvas.itemconfigure(spot['odds_item'], text=spot['base_odds'])
        if self.game_mode in ('goldendice', 'treasure', 'xxx'):
            self.update_golden_bet_visuals()

    def draw_squeeze_selector(self):
        """Draw the checkbox on the table, so cards can pass above it.

        A native Canvas window always covers drawn images regardless of tag
        order; Canvas items share the same stacking order as the burn cards.
        """
        c = self.canvas
        centre = self.HEADER_RIGHT_X - 39
        left, y = centre - 30, self.BOARD_HEADER_Y
        tags = ('squeeze_selector', 'static')
        c.create_rectangle(centre - 39, y - 16, centre + 39, y + 16,
                           fill=self.FELT, outline='', tags=tags)
        box = c.create_rectangle(left, y - 11, left + 22, y + 11,
                                 fill=self.PANEL, outline=self.GOLD, tags=tags)
        mark = c.create_text(left + 11, y, text='✓', font=('Arial', 14, 'bold'),
                             fill=self.GOLD, tags=tags)
        label = c.create_text(left + 30, y, anchor='w', text='咪牌',
                              font=('Arial', 14, 'bold'), fill=self.GOLD, tags=tags)
        self.squeeze_checkbox_items = (box, mark, label)
        self._update_squeeze_selector()
        c.tag_bind('squeeze_selector', '<Button-1>', self._toggle_squeeze_selector)
        c.tag_bind('squeeze_selector', '<Key-space>', self._toggle_squeeze_selector)
        c.tag_bind('squeeze_selector', '<Enter>',
                   lambda _event: c.configure(cursor='hand2' if self._squeeze_selector_enabled else ''))
        c.tag_bind('squeeze_selector', '<Leave>', lambda _event: c.configure(cursor=''))

    def _update_squeeze_selector(self, enabled=None):
        if enabled is None:
            enabled = self.accept_bets and not self.animation_running and not self.settlement_running
        self._squeeze_selector_enabled = enabled
        box, mark, label = self.squeeze_checkbox_items
        color = self.GOLD if enabled else '#8e9d91'
        self.canvas.itemconfigure(box, outline=color)
        self.canvas.itemconfigure(mark, fill=color,
                                  state='normal' if self.squeeze_enabled.get() else 'hidden')
        self.canvas.itemconfigure(label, fill=color)

    def _toggle_squeeze_selector(self, _event=None):
        if self._squeeze_selector_enabled and not self._closing:
            self.squeeze_enabled.set(not self.squeeze_enabled.get())
            self._update_squeeze_selector()
            self.canvas.focus_set()
            self.canvas.focus(self.squeeze_checkbox_items[2])
        return 'break'

    @staticmethod
    def _mode_round_points(x0, y0, x1, y1, radius):
        return (x0+radius,y0, x1-radius,y0, x1,y0, x1,y0+radius,
                x1,y1-radius, x1,y1, x1-radius,y1, x0+radius,y1,
                x0,y1, x0,y1-radius, x0,y0+radius, x0,y0)

    @staticmethod
    def _mode_mix_color(start, target, amount):
        a = tuple(int(start[i:i+2], 16) for i in (1, 3, 5))
        b = tuple(int(target[i:i+2], 16) for i in (1, 3, 5))
        return '#' + ''.join(f'{round(x+(y-x)*amount):02x}' for x, y in zip(a, b))

    def _draw_sliding_selector(self, name, choices, bounds, value, command, font_size=10):
        """Match UTH's rounded green rail and gold sliding selection."""
        c = self.canvas
        controls = self.__dict__.setdefault('_segmented_controls', {})
        previous = controls.get(name)
        if previous and previous.get('after'):
            previous['generation'] += 1
            self.after_cancel(previous['after'])
        c.delete(name)
        x0, y0, x1, y1 = bounds
        width = (x1-x0)/len(choices)
        control = dict(choices=tuple(choices), bounds=bounds, width=width,
                       value=value, target=value, x=x0+(next(i for i, v in enumerate(choices)
                       if v[0] == value)+.5)*width, enabled=True, press=None,
                       generation=0, after=None, slots={}, labels={}, thumb=None, hover=None)
        control['allowed'] = {key for key, _caption in choices}
        controls[name] = control
        tags = (name, 'static')
        c.create_polygon(*self._mode_round_points(x0,y0,x1,y1,min(12,(y1-y0)/2)),
                         smooth=True, splinesteps=24, fill='#102C22',
                         outline='#627652', width=1, tags=tags)
        for i, (key, caption) in enumerate(choices):
            left, right = x0+i*width, x0+(i+1)*width
            control['slots'][key] = c.create_polygon(
                *self._mode_round_points(left+3,y0+3,right-3,y1-3,min(8,(y1-y0-6)/2)),
                smooth=True, splinesteps=24, fill='#16372A', outline='', tags=tags)
        control['thumb'] = c.create_polygon(0,0,1,0,1,1,0,1, smooth=True,
            splinesteps=24, fill='#D8B46A', outline='#F0D18D', width=1, tags=tags)
        for i, (key, caption) in enumerate(choices):
            control['labels'][key] = c.create_text(x0+(i+.5)*width, (y0+y1)/2,
                text=caption, font=('Arial', font_size, 'bold'), fill='#CCD4BF', tags=tags)

        def hover(event):
            x, y = c.canvasx(event.x), c.canvasy(event.y)
            index = int((x-x0)//width)
            control['hover'] = (choices[index][0] if control['enabled'] and
                                0 <= index < len(choices) and y0 <= y <= y1 and
                                choices[index][0] in control['allowed'] else None)
            c.configure(cursor='hand2' if control['hover'] is not None else '')
            self._paint_sliding_selector(name)

        def leave(_event):
            control['hover'] = None
            c.configure(cursor='')
            self._paint_sliding_selector(name)

        def press(event):
            if control['enabled']:
                x, y = c.canvasx(event.x), c.canvasy(event.y)
                index = int((x-x0)//width)
                control['press'] = (x if 0 <= index < len(choices) and y0 <= y <= y1
                                    and choices[index][0] in control['allowed'] else None)
                self._paint_sliding_selector(name)

        def release(event):
            start, control['press'] = control['press'], None
            if start is None or not control['enabled']:
                return 'break'
            x, y = c.canvasx(event.x), c.canvasy(event.y)
            if not (x0 <= x < x1 and y0 <= y <= y1):
                self._paint_sliding_selector(name)
                return 'break'
            index = int((x-x0)//width)
            old_index = max(0, min(len(choices)-1, int((start-x0)//width)))
            if index == old_index and abs(x-start) > min(20, width*.4):
                index = max(0, min(len(choices)-1, index+(1 if x > start else -1)))
            self._paint_sliding_selector(name)
            if choices[index][0] in control['allowed']:
                command(choices[index][0])
            return 'break'

        c.tag_bind(name, '<ButtonPress-1>', press)
        c.tag_bind(name, '<ButtonRelease-1>', release)
        c.tag_bind(name, '<Enter>', hover)
        c.tag_bind(name, '<Motion>', hover)
        c.tag_bind(name, '<Leave>', leave)
        self._paint_sliding_selector(name)
        return control

    def _paint_sliding_selector(self, name):
        c = self.canvas
        control = self._segmented_controls[name]
        x0, y0, x1, y1 = control['bounds']
        left, right = control['x']-control['width']/2, control['x']+control['width']/2
        fill = '#D8B46A'
        if control['enabled'] and control['hover'] == control['target']:
            fill = '#BD9A58' if control['press'] is not None else '#E2C37D'
        c.coords(control['thumb'], *self._mode_round_points(
            left+3,y0+3,right-3,y1-3,min(8,(y1-y0-6)/2)))
        c.itemconfigure(control['thumb'], fill=fill)
        for index, (key, _caption) in enumerate(control['choices']):
            selectable = control['enabled'] and key in control['allowed']
            selected = max(0.0, 1-abs(control['x']-(x0+(index+.5)*control['width']))/control['width'])
            foreground = self._mode_mix_color('#CCD4BF' if selectable else '#8B9C8E',
                                              '#2A1B08', selected)
            c.itemconfigure(control['labels'][key], fill=foreground)
            c.itemconfigure(control['slots'][key], fill=(
                '#2E513C' if selectable and control['hover'] == key else
                '#16372A' if key in control['allowed'] else '#102C22'))
        c.tag_raise(name)

    def _set_sliding_selector(self, name, value, enabled=None, animate=True):
        control = self.__dict__.get('_segmented_controls', {}).get(name)
        if control is None:
            return
        if enabled is None:
            transition = self._mode_transition
            enabled = ((self.accept_bets or transition is not None and transition['phase'] in ('out', 'in'))
                       and not self.animation_running and not self.settlement_running)
        control['enabled'] = bool(enabled and not self._closing)
        if not control['enabled']:
            control['press'] = None
            control['hover'] = None
        self._paint_sliding_selector(name)
        index = next(i for i, choice in enumerate(control['choices']) if choice[0] == value)
        target = control['bounds'][0]+(index+.5)*control['width']
        if control['target'] == value and animate:
            return
        control['target'] = control['value'] = value
        control['generation'] += 1
        generation, start = control['generation'], control['x']
        started = time.monotonic()
        if control['after'] is not None:
            self.after_cancel(control['after'])
            control['after'] = None
        def move():
            control['after'] = None
            if self._closing or generation != control['generation']:
                return
            ratio = min(1.0, (time.monotonic()-started)*1000/self.MODE_TRANSITION_MS) if animate else 1.0
            control['x'] = start+(target-start)*BaccaratCutScene.ease(ratio)
            self._paint_sliding_selector(name)
            if ratio < 1:
                control['after'] = self.after(self.MODE_FRAME_MS, move)
        move()

    def draw_mode_selector(self):
        choices = [(mode, self.MODE_SHORT[mode]) for mode in self.MODE_TABS]
        selected = 'always' if self.game_mode in BaccaratEngine.ALWAYS_MODES else self.game_mode
        control = self._draw_sliding_selector('mode_selector', choices, self.MODE_SELECTOR_BOUNDS,
                                               selected, self.change_game_mode)
        self.mode_button_items = {key:(control['slots'][key], control['labels'][key]) for key,_ in choices}
        self.update_mode_selector_style()

    def update_mode_selector_style(self):
        mode = self._mode_transition['target'] if self._mode_transition is not None else self.game_mode
        selected = 'always' if mode in BaccaratEngine.ALWAYS_MODES else mode
        self._set_sliding_selector('mode_selector', selected)

    def _update_fixed_selector(self):
        controls = self.__dict__.setdefault('_segmented_controls', {})
        if self.game_mode not in BaccaratEngine.ALWAYS_MODES:
            self.canvas.itemconfigure('fixed_selector', state='hidden')
            if 'fixed_selector' in controls:
                controls['fixed_selector']['enabled'] = False
                controls['fixed_selector']['press'] = None
            return
        if 'fixed_selector' not in controls:
            middle = self.HEADER_MIDDLE_X
            self._draw_sliding_selector('fixed_selector',
                [(mode, self.MODE_SHORT[mode]) for mode in BaccaratEngine.ALWAYS_MODES],
                (middle-125,self.BOARD_HEADER_Y-15,middle+125,self.BOARD_HEADER_Y+15),
                self.game_mode, self.change_game_mode, font_size=12)
        self.canvas.itemconfigure('fixed_selector',state='normal')
        target = self.game_mode
        if self._mode_transition is not None and self._mode_transition['target'] in BaccaratEngine.ALWAYS_MODES:
            target = self._mode_transition['target']
        self._set_sliding_selector('fixed_selector', target)


    def change_game_mode(self, mode):
        """Fade out, commit the latest requested mode once, then reveal its board."""
        if mode == 'always':
            mode = self._always_selected_mode
        transition = self._mode_transition
        if (self._closing or mode not in self.MODE_ORDER or self.animation_running
                or self.settlement_running or not self.accept_bets and transition is None):
            return
        if transition is not None:
            if transition['phase'] == 'apply' or mode == transition['target']:
                return
            transition['target'] = mode
            if transition['phase'] == 'in':
                transition.update(phase='out', started=time.monotonic(), start=transition['level'])
            self.update_control_states()
            return
        if mode == self.game_mode:
            return
        self._mode_transition = dict(target=mode, phase='out', started=time.monotonic(),
                                     start=0.0, level=0.0)
        # Existing wager/deal guards lock the table while it is covered. The main
        # mode selector remains available so quick clicks can retarget the fade.
        self.accept_bets = False
        self.update_control_states()
        self._step_mode_transition()

    def _paint_mode_overlay(self, level):
        c = self.canvas
        tag = 'mode_transition_overlay'
        x0, y0, x1, y1 = self.BETTING_TRANSITION_BOUNDS
        if Image is not None and ImageTk is not None:
            rgb = tuple(int(self.FELT[i:i+2], 16) for i in (1, 3, 5))
            layer = Image.new('RGBA', (x1-x0, y1-y0), rgb+(round(level*255),))
            self._mode_transition_photo = ImageTk.PhotoImage(layer, master=self)
            if self._mode_transition_item is None:
                self._mode_transition_item = c.create_image(x0, y0, anchor='nw', tags=tag)
            c.itemconfigure(self._mode_transition_item, image=self._mode_transition_photo)
        else:
            # Keep a smooth cover/reveal on installations without Pillow.
            if self._mode_transition_item is None:
                self._mode_transition_item = c.create_rectangle(x0,y0,x0,y1,
                    fill=self.FELT, outline='', width=0, tags=tag)
            c.coords(self._mode_transition_item, x0, y0, x0+(x1-x0)*level, y1)
            c.itemconfigure(self._mode_transition_item, state='normal' if level > 0 else 'hidden')
        c.tag_raise(tag)
        for selector in ('mode_selector', 'banker_selector', 'squeeze_selector', 'fixed_selector'):
            c.tag_raise(selector)

    def _step_mode_transition(self):
        self._mode_transition_after = None
        transition = self._mode_transition
        if self._closing or transition is None:
            return
        progress = min(1.0, (time.monotonic()-transition['started'])*2000/self.MODE_TRANSITION_MS)
        eased = progress*progress*(3-2*progress)
        goal = 1.0 if transition['phase'] == 'out' else 0.0
        transition['level'] = transition['start']+(goal-transition['start'])*eased
        self._paint_mode_overlay(transition['level'])
        if progress >= 1.0:
            if transition['phase'] == 'out':
                transition['phase'] = 'apply'
                self.update_control_states()
                try:
                    self._apply_game_mode(transition['target'])
                except Exception as exc:
                    messagebox.showerror('模式切换失败', str(exc), parent=self.winfo_toplevel())
                if self._closing or self._mode_transition is not transition:
                    return
                transition.update(target=self.game_mode, phase='in', started=time.monotonic(), start=1.0)
                self.update_control_states()
            else:
                self._finish_mode_transition()
                return
        self._mode_transition_after = self.after(self.MODE_FRAME_MS, self._step_mode_transition)

    def _finish_mode_transition(self):
        fees, cut = self._mode_fee_visuals, self._mode_pending_cut
        self._cancel_mode_transition()
        if self._closing:
            return
        self.accept_bets = not self.animation_running and not self.settlement_running
        self.update_display()
        for token in fees:
            self._start_fee_visual(token)
        if cut is not None and self.game_mode not in BaccaratEngine.SPECIAL_MODES:
            self.start_new_shoe_cut(cut)

    def _cancel_mode_transition(self):
        if self._mode_transition_after is not None:
            try:
                self.after_cancel(self._mode_transition_after)
            except (tk.TclError, ValueError):
                pass
        self._mode_transition_after = None
        self._mode_transition = None
        self._mode_transition_item = None
        self._mode_transition_photo = None
        self._mode_fee_visuals = []
        self._mode_pending_cut = None
        try:
            self.canvas.delete('mode_transition_overlay')
        except tk.TclError:
            pass

    def _on_mode_transition_destroy(self, event):
        if event.widget is not self:
            return
        self._closing = True
        self._cancel_mode_transition()
        for control in self._segmented_controls.values():
            control['generation'] += 1
            if control['after'] is not None:
                try:
                    self.after_cancel(control['after'])
                except (tk.TclError, ValueError):
                    pass
                control['after'] = None

    def _apply_game_mode(self, mode):
        """Switch mode while preserving Player/Banker/Tie wagers.

        Side wagers are refunded. Any old mode fee is refunded first, then the
        destination mode fee (Treasure 20%, XXX 50%) is charged on retained
        main wagers. This also handles Treasure <-> XXX correctly.
        """
        if mode == 'always':
            mode = self._always_selected_mode
        if mode == self.game_mode:
            return
        if self._closing or self.animation_running or self.settlement_running:
            return
        if mode not in self.MODE_ORDER:
            return

        old_mode = self.game_mode
        keep_types = {'Player', 'Banker', 'Tie'}
        side_refund = sum(float(amount) for bt, amount in self.bet_state.bets.items()
                          if bt not in keep_types)
        all_fee_refund = sum(float(v) for v in self.bet_fee_state.values())

        fee_needed = sum(float(self.bet_state.bets.get(bt, 0.0)) * self._wager_fee_rate(mode, bt)
                         for bt in keep_types)
        projected_balance = self.balance + side_refund + all_fee_refund
        if fee_needed > projected_balance + 1e-9:
            messagebox.showwarning(
                '模式手续费',
                f'保留闲/庄/和下注需要额外手续费 {self.format_money(fee_needed)}，\n'
                f'当前可用余额不足，无法切换模式。',
                parent=self.winfo_toplevel())
            return

        context_changed = (old_mode in BaccaratEngine.SPECIAL_MODES or mode in BaccaratEngine.SPECIAL_MODES)
        old_store = self.one_deck_store
        if context_changed:
            # Always remove the previous table FIRST, before loading a fixed
            # card or another mode's roads. No stale synthetic Banker survives.
            self.clear_card_display()
            self.current_result = None
        try:
            if mode in BaccaratEngine.SPECIAL_MODES:
                self.one_deck_store = self.load_one_deck_runtime_store(mode)
            if mode in BaccaratEngine.ALWAYS_MODES:
                self.fixed_engine.prepare_mode(mode)
            elif old_mode in BaccaratEngine.ALWAYS_MODES:
                self.fixed_engine.release_all_cards(force_shuffle=False)
        except Exception as exc:
            self.one_deck_store = old_store
            if old_mode in BaccaratEngine.ALWAYS_MODES:
                self.fixed_engine.mode = old_mode
                self._draw_fixed_banker_card(preview=True)
            messagebox.showerror('模式切换失败', str(exc), parent=self.winfo_toplevel())
            return

        # Refund all side wagers and every fee charged by the old mode.
        self._cancel_fee_visuals()
        for bet_type in list(self.bet_state.bets):
            if bet_type not in keep_types:
                self.balance += self.bet_state.clear_area(bet_type)
        self.balance += all_fee_refund
        self.bet_fee_state.clear()
        self.treasure_pot_amount = 0.0

        # Charge destination fee on retained main wagers.
        fee_visuals = []
        for bet_type in keep_types:
            amount = float(self.bet_state.bets.get(bet_type, 0.0))
            rate = self._wager_fee_rate(mode, bet_type)
            if amount <= 0 or rate <= 0:
                continue
            fee = amount * rate
            self.balance -= fee
            self.bet_fee_state[bet_type] = fee
            self.treasure_pot_amount += fee
            fee_visuals.append(self._register_fee_visual(bet_type, fee))

        self.game_mode = mode
        if mode in BaccaratEngine.ALWAYS_MODES:
            self._always_selected_mode = mode
        if context_changed:
            self.engine = (self.fixed_engine if mode in BaccaratEngine.ALWAYS_MODES else
                           self.one_deck_engine if mode == 'one_deck' else self.standard_engine)
            self.history_file = self.get_history_file()
            self.history_store = self.load_history_store()
            self.history_data = self.history_records_from_store()
            self.bead_store = self.load_bead_store()
            self.bead_data = self.bead_records_from_store()
            self.statistic_data = self.load_statistic_data()
            self.big_road_scroll_col = 0
            self.big_road_auto_follow = True
            self._reset_manual_reshuffle_confirm()
            self.clear_card_display()
            self.current_result = None
            self.canvas.delete('multiplier_ribbon')
            self._draw_history_content()
        self.banker_rule = self._current_banker_rule()
        self._golden_dice_roll_ready = False
        self.golden_dice_active = False
        self._golden_dice_fee_collected = False
        self.golden_dice_multipliers = {key: 2 for key in self.GOLDEN_DICE_BASE_PROFIT_ODDS}
        self._golden_dice_reels_ready = set()
        self.undo_stack.clear()
        self.pending_bet_visual_amounts.clear()
        self.summary_mode = 'bet'
        self.draw_mode_betting_board()
        if mode in BaccaratEngine.ALWAYS_MODES:
            self._draw_fixed_banker_card(preview=True)
        self.update_mode_selector_style()
        self._update_deal_button_label()
        self.update_display()
        self._mode_fee_visuals = fee_visuals
        self.save_balance()
        if old_mode in BaccaratEngine.SPECIAL_MODES and mode not in BaccaratEngine.SPECIAL_MODES and not self.shoe_resumed:
            self._mode_pending_cut = False

    def _draw_mode_header(self, mode, canvas=None, y=None):
        """Use one compact bilingual title at the left of every live board."""
        c = self.canvas if canvas is None else canvas
        if y is None:
            y = self.BOARD_HEADER_Y
        return c.create_text(30, y, anchor='w', text=self.MODE_HEADER_TITLES[mode],
                             font=('Arial', 16, 'bold'), fill=self.GOLD,
                             tags='board_dynamic')

    def draw_mode_betting_board(self):
        self._draw_mode_betting_board()
        self._refresh_banker_bet_odds()
        self._update_banker_selector()
        self._update_fixed_selector()
        self.canvas.tag_raise('mode_selector')
        self.canvas.tag_raise('banker_selector')
        self.canvas.tag_raise('squeeze_selector')
        self.canvas.tag_raise('fixed_selector')

    def _draw_mode_betting_board(self):
        c = self.canvas
        if self.__dict__.get('_tiger_symbol_after_id') is not None:
            self._cancel_tiger_symbol_transition()
        if self.__dict__.get('_lucky6_pop_after_id') is not None:
            self._cancel_lucky6_pop()
        if self.__dict__.get('_lucky7_jackpot_after_id') is not None:
            self._cancel_lucky7_jackpot_counter()
        c.delete('board_dynamic')
        c.delete('bet_chip_dynamic')
        self._sync_board_header_controls()
        self.bet_spots = {}
        self.treasure_pool_display = None
        if self.game_mode == 'goldendice':
            self.draw_goldendice_betting_board()
            self._refresh_treasure_pool_text()
            self._update_golden_dice_board_odds()
            self.update_bet_chips()
            self._update_main_bet_availability()
            return
        if self.game_mode in ('treasure', 'xxx'):
            if self.game_mode == 'xxx':
                self.draw_xxx_betting_board()
            else:
                self.draw_treasure_betting_board()
            self._refresh_treasure_pool_text()
            self.update_golden_bet_visuals()
            self.update_bet_chips()
            self._update_main_bet_availability()
            return
        if self.game_mode == 'classic':
            self.draw_classic_betting_board()
            self.update_bet_chips()
            self._update_main_bet_availability()
            return
        if self.game_mode in ('2to1', 'one_deck') + BaccaratEngine.ALWAYS_MODES:
            self._draw_standard_betting_board(self.game_mode)
            self.update_bet_chips()
            self._update_main_bet_availability()
            return
        if self.game_mode == 'monkey':
            self.draw_monkey_betting_board()
            self.update_bet_chips()
            self._update_main_bet_availability()
            return
        if self.game_mode == 'ez':
            self.draw_ez_betting_board()
            self.update_bet_chips()
            self._update_main_bet_availability()
            return
        if self.game_mode == 'tiger':
            self.draw_tiger_betting_board()
            self.update_bet_chips()
            self._update_main_bet_availability()
            return
        if self.game_mode == 'lucky7':
            self.draw_lucky7_betting_board()
            self.update_bet_chips()
            self._update_main_bet_availability()
            return
        rows = BaccaratEngine.MODE_ROWS[self.game_mode]
        odds = self._board_odds()

        self._draw_mode_header(self.game_mode, c)
        if self.game_mode in ('treasure', 'xxx'):
            pool_name = '聚宝盆' if self.game_mode == 'treasure' else 'XXX'
            self.treasure_pool_display = c.create_text(self.HEADER_MIDDLE_X, self.BOARD_HEADER_Y, anchor='center',
                          text=f'{pool_name} 手续费 ${self.treasure_pot_amount:,.0f}',
                          font=('Arial', 11, 'bold'), fill='#ffd84a',
                          tags=('board_dynamic', 'treasure_pool_display'))

        # Give the two side-bet bands more breathing room and larger text.
        # The main Player/Tie/Banker band is intentionally shorter so the board
        # reads as two information-rich side-bet rows over one compact main row.
        top, bottom = self.BETTING_BOUNDS[1], self.BETTING_BOUNDS[3]
        scale_y = (bottom-top)/234
        self.draw_bet_row(rows[0], self.BOARD_INNER_X0, top, top+68*scale_y, odds)
        self.draw_bet_row(rows[1], self.BOARD_INNER_X0, top+72*scale_y, top+140*scale_y, odds)

        main = ('Player', 'Tie', 'Banker')
        x0, x1 = self.BOARD_INNER_X0, self.BOARD_INNER_X1
        y0, y1 = top+144*scale_y, top+228*scale_y
        widths = (0.4, 0.2, 0.4)
        cursor = x0
        for index, bet_type in enumerate(main):
            width = (x1 - x0) * widths[index]
            bx0 = cursor
            bx1 = x1 if index == len(main) - 1 else cursor + width
            self.draw_bet_spot(
                bet_type, bx0, y0, bx1, y1, odds.get(bet_type, ''), main=True)
            cursor = bx1
        self.update_bet_chips()
        self._update_main_bet_availability()

    def draw_tiger_betting_board(self, canvas=None, bounds=None, interactive=True):
        """Tiger-only photo layout; Dragon Bonus remains a live side wager."""
        c = self.canvas if canvas is None else canvas
        if bounds is None:
            bounds = self.BETTING_BOUNDS
        bx0, by0, bx1, by1 = bounds
        sx, sy = (bx1 - bx0) / 738.0, (by1 - by0) / 234.0
        scale = min(sx, sy)
        cream, ink, gold = '#f8ecd3', '#090704', '#e9bc47'
        blue, red = '#01479a', '#a80909'
        # Muted categorical colours with dark, high-contrast text. Names,
        # conditions and odds remain visible so colour is never the only cue.
        pair_ink, tie_ink = '#342400', '#103d36'
        odds, spots = self._board_odds('tiger'), {}

        def xy(x, y):
            return bx0 + x * sx, by0 + y * sy

        def box_coords(box):
            return (*xy(box[0], box[1]), *xy(box[2], box[3]))

        def text(x, y, value, size, color, tag, chinese=False, extra=()):
            return c.create_text(*xy(x, y), text=value, fill=color,
                                 font=('Microsoft YaHei UI' if chinese else 'Arial',
                                       -max(6, round(size * scale)), 'bold'),
                                 justify='center', tags=('board_dynamic', tag) + extra)

        def panel(key, box, fill, main=False, oval=False):
            tag = self.spot_tag((key, None))
            tags = ('board_dynamic', tag) + (('tiger_symbol',) if oval else ())
            draw = c.create_oval if oval else c.create_rectangle
            draw(*box_coords((box[0] - 2, box[1] - 1, box[2] + 2, box[3] + 2)),
                 fill=ink, outline=ink, width=2, tags=tags)
            rect = draw(*box_coords(box), fill=fill, outline=gold if oval else cream,
                        width=2 if oval else 1.2, tags=tags)
            if not oval:
                # Keep the photo's frame independent of the flashing fill.
                draw(*box_coords(box), fill='', outline=cream, width=1.2,
                     tags=tags + ('bet_board_frame',))
            if not oval:
                c.create_rectangle(*box_coords((box[0] + 2, box[1] + 2,
                                                box[2] - 2, box[3] - 2)),
                                   fill='', outline=blue if key == 'Dragon P'
                                   else red if key == 'Dragon B' else fill,
                                   width=.7,
                                   tags=tags + ('bet_board_frame', 'bet_board_inner_frame'))
            spot = dict(tag=tag, rect_id=rect, bounds=box_coords(box),
                        chip_pos=xy((box[0] + box[2]) / 2, (box[1] + box[3]) / 2),
                        base_odds=odds[key], main=main, normal_outline=gold if oval else cream,
                        normal_outline_width=2 if oval else 1.2,
                        label=BaccaratEngine.DISPLAY_NAMES.get(key, key))
            spots[key] = spot
            if interactive:
                self.register_spot(key, *spot['bounds'], spot['chip_pos'], spot['label'])
                self.bet_spots[(key, None)].update(spot)
                spots[key] = self.bet_spots[(key, None)]
                for event, callback in (
                        ('<Button-1>', lambda _e, bt=key: self.place_bet(bt)),
                        ('<Button-3>', lambda _e, bt=key: self.clear_single_bet(bt)),
                        ('<Enter>', lambda _e, bt=key: self._set_bet_hover(bt)),
                        ('<Leave>', lambda _e: self._set_bet_hover(None))):
                    c.tag_bind(tag, event, callback)
            return tag

        def title(key, x, y, chinese, english, color):
            tag = spots[key]['tag']
            spots[key]['label_item'] = text(x, y, chinese, 20, color, tag, True)
            text(x, y + 15, english, 11, color, tag)

        c.create_rectangle(*box_coords((-8, -2, 746, 244)), fill=self.FELT,
                           outline='', tags=('board_dynamic', 'bet_board_background'))
        if interactive:
            self._draw_mode_header('tiger', c)

        for key, box, name, english, color in (
                ('Dragon P', (0, 0, 116, 156), '闲家龙宝', 'PLAYER\nDRAGON', blue),
                ('Dragon B', (622, 0, 738, 156), '庄家龙宝', 'BANKER\nDRAGON', red)):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, cream)
            spots[key]['label_item'] = text(cx, 23, name, 19, color, tag, True)
            text(cx, 57, english, 15, color, tag)
            spots[key]['odds_item'] = text(cx, 94, odds[key], 20, color, tag)
            text(cx, 138, '自然点 / 点差4–9', 10, color, tag, True)

        tag = panel('Tiger Pair', (122, 0, 366, 76), '#f2d58a')
        title('Tiger Pair', 244, 13, '老虎对子', 'Tiger Pair', pair_ink)
        for index, (name, rate) in enumerate((('单一对子', '4:1'),
                                             ('双双对子', '20:1'),
                                             ('孪生对子', '100:1'))):
            x = 163 + index * 81
            text(x, 48, name, 12, pair_ink, tag, True)
            item = text(x, 65, rate, 16, pair_ink, tag)
            if index == 0:
                spots['Tiger Pair']['odds_item'] = item
            if index < 2:
                c.create_line(*xy(x + 40, 42), *xy(x + 40, 72), fill='#000000',
                              width=1, tags=('board_dynamic', tag, 'tiger_pair_divider'))

        tag = panel('Tiger Tie', (372, 0, 616, 76), '#b7d9ce')
        title('Tiger Tie', 494, 13, '老虎和局', 'Tiger Tie', tie_ink)
        text(494, 48, '闲家庄家均为6点', 12, tie_ink, tag, True)
        spots['Tiger Tie']['odds_item'] = text(494, 65, '35:1', 17, tie_ink, tag)

        for key, box, fill, name, english, color, condition in (
                ('Small Tiger', (122, 80, 366, 156), '#cce3f5', '小老虎',
                 'Small Tiger', '#163a5f', '庄家2张牌6点获胜'),
                ('Big Tiger', (372, 80, 616, 156), '#e9d5ea', '大老虎',
                 'Big Tiger', '#4a2457', '庄家3张牌6点获胜')):
            # Leave the seam clear for the independent, circular Tiger wager.
            cx = 235 if key == 'Small Tiger' else 503
            tag = panel(key, box, fill)
            title(key, cx, 95, name, english, color)
            text(cx, 131, condition, 12, color, tag, True)
            spots[key]['odds_item'] = text(cx, 148, odds[key], 17, color, tag)

        for key, box, fill, name in (
                ('Player', (0, 162, 242, 232), '#0046a0', '闲家'),
                ('Tie', (248, 162, 490, 232), '#006a35', '和'),
                ('Banker', (496, 162, 738, 232), '#bf0711', '庄家')):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, fill, main=True)
            spots[key]['label_item'] = text(cx, 180, name, 23, cream, tag, True)
            text(cx, 199, key.upper(), 12, cream, tag)
            spots[key]['odds_item'] = text(cx, 218, odds[key], 19, cream, tag)

        tag = panel('Tiger', (327, 76, 411, 160), ink, oval=True)
        symbol_tags = ('board_dynamic', tag, 'tiger_symbol')
        # Two integrated pointed wings form <O>, entirely inside the second
        # row. Both labelled wings belong to the independent Tiger wager.
        for side, value, rate_tag in ((-1, '12:1', 'tiger_small_odds'),
                                       (1, '20:1', 'tiger_big_odds')):
            wing = ((369 + side * 25, 81), (369 + side * 78, 118),
                    (369 + side * 25, 155), (369, 118))
            points = [v for x, y in wing for v in xy(x, y)]
            c.create_polygon(*points, fill=ink, outline=gold, width=1.2,
                             tags=symbol_tags + ('tiger_outer_tip',))
            item = text(369 + side * 58, 118, value, 11, gold, tag,
                        extra=('tiger_symbol', 'tiger_outer_odds', rate_tag))
            spots['Tiger']['label_item' if side < 0 else 'odds_item'] = item
        frames = self._build_tiger_symbol_frames(c, max(1, round(84 * sx)),
                                                max(1, round(84 * sy)), interactive)
        image_item = c.create_image(*xy(369, 118), image=frames[0], tags=symbol_tags)
        c.create_oval(*box_coords((327, 76, 411, 160)), fill='', outline=gold,
                      width=2, tags=symbol_tags)
        if interactive:
            self._tiger_symbol_frames = frames
            self._tiger_symbol_image = image_item
            self._tiger_symbol_captions = []
            self._tiger_symbol_frame = 0
            self._tiger_symbol_after_id = None
            self._raise_tiger_symbol()
        else:
            # Tk images are retained by Python objects, not by Canvas items.
            c._tiger_symbol_preview_frames = frames
        return spots

    LUCKY6_BADGE_COLOURS = {
        'normal': '#6b2234', 'win': '#c42c3d', 'numeral': '#fff0c4',
        'stroke': '#a87124', 'rim': '#e1b854',
        'heading': '#ffe1a1', 'heading_shadow': '#3e1421',
    }

    def _sync_board_header_controls(self):
        """Keep mode, Banker and squeeze controls at the same height in every mode."""
        c = self.canvas
        top = self.MODE_SELECTOR_BOUNDS[1]
        control = self.__dict__.get('_segmented_controls', {}).get('mode_selector')
        if control is not None:
            old_top = control['bounds'][1]
            c.move('mode_selector', 0, top-old_top)
            control['bounds'] = self.MODE_SELECTOR_BOUNDS
        checkbox = self.__dict__.get('squeeze_checkbox_items')
        if checkbox:
            coords = c.coords(checkbox[1])
            if len(coords) >= 2:
                centre = self.BOARD_HEADER_Y
                if centre != coords[1]:
                    c.move('squeeze_selector', 0, centre - coords[1])
        banker = self.__dict__.get('_segmented_controls', {}).get('banker_selector')
        if banker is not None:
            x0, top, x1, bottom = banker['bounds']
            delta = self.BOARD_HEADER_Y-(top+bottom)/2
            if delta:
                c.move('banker_selector', 0, delta)
                banker['bounds'] = (x0, top+delta, x1, bottom+delta)
            self._banker_selector_y = self.BOARD_HEADER_Y

    def draw_lucky7_betting_board(self, canvas=None, bounds=None, interactive=True):
        """Lucky 7-only board: Tiger side layout and EZ five-wager main row."""
        c = self.canvas if canvas is None else canvas
        if bounds is None:
            bounds = self.BETTING_BOUNDS
        bx0, by0, bx1, by1 = bounds
        sx, sy = (bx1 - bx0) / 738.0, (by1 - by0) / 234.0
        scale = min(sx, sy)
        cream, ink, gold = '#f8ecd3', '#090704', '#e9bc47'
        badge = self.LUCKY6_BADGE_COLOURS
        blue, red = '#01479a', '#a80909'
        # Muted categorical colours with dark, high-contrast text. Names,
        # conditions and odds remain visible so colour is never the only cue.
        pair_ink, tie_ink = '#342400', '#103d36'
        odds, spots = self._board_odds('lucky7'), {}

        def xy(x, y):
            return bx0 + x * sx, by0 + y * sy

        def box_coords(box):
            return (*xy(box[0], box[1]), *xy(box[2], box[3]))

        def text(x, y, value, size, color, tag, chinese=False, extra=()):
            return c.create_text(*xy(x, y), text=value, fill=color,
                                 font=('Microsoft YaHei UI' if chinese else 'Arial',
                                       -max(6, round(size * scale)), 'bold'),
                                 justify='center', tags=('board_dynamic', tag) + extra)

        def panel(key, box, fill, main=False, oval=False):
            tag = self.spot_tag((key, None))
            tags = ('board_dynamic', tag) + (('lucky6_symbol',) if oval else ())
            draw = c.create_oval if oval else c.create_rectangle
            draw(*box_coords((box[0] - 2, box[1] - 1, box[2] + 2, box[3] + 2)),
                 fill=ink, outline=ink, width=2, tags=tags)
            rect = draw(*box_coords(box), fill=fill, outline=gold if oval else cream,
                        width=2 if oval else 1.2, tags=tags)
            if not oval:
                # Keep the photo's frame independent of the flashing fill.
                draw(*box_coords(box), fill='', outline=cream, width=1.2,
                     tags=tags + ('bet_board_frame',))
            if not oval:
                c.create_rectangle(*box_coords((box[0] + 2, box[1] + 2,
                                                box[2] - 2, box[3] - 2)),
                                   fill='', outline=blue if key == 'Dragon P'
                                   else red if key == 'Dragon B' else fill,
                                   width=.7,
                                   tags=tags + ('bet_board_frame', 'bet_board_inner_frame'))
            spot = dict(tag=tag, rect_id=rect, bounds=box_coords(box),
                        chip_pos=xy((box[0] + box[2]) / 2, (box[1] + box[3]) / 2),
                        base_odds=odds[key], main=main, normal_outline=gold if oval else cream,
                        normal_outline_width=2 if oval else 1.2,
                        label=BaccaratEngine.DISPLAY_NAMES.get(key, key))
            spots[key] = spot
            if interactive:
                self.register_spot(key, *spot['bounds'], spot['chip_pos'], spot['label'])
                self.bet_spots[(key, None)].update(spot)
                spots[key] = self.bet_spots[(key, None)]
                for event, callback in (
                        ('<Button-1>', lambda _e, bt=key: self.place_bet(bt)),
                        ('<Button-3>', lambda _e, bt=key: self.clear_single_bet(bt)),
                        ('<Enter>', lambda _e, bt=key: self._set_bet_hover(bt)),
                        ('<Leave>', lambda _e: self._set_bet_hover(None))):
                    c.tag_bind(tag, event, callback)
            return tag

        def title(key, x, y, chinese, english, color):
            tag = spots[key]['tag']
            spots[key]['label_item'] = text(x, y, chinese, 20, color, tag, True)
            text(x, y + 15, english, 11, color, tag)

        c.create_rectangle(*box_coords((-8, -2, 746, 244)), fill=self.FELT,
                           outline='', tags=('board_dynamic', 'bet_board_background'))
        if interactive:
            # Keep the pool header inside the same fixed band as every mode.
            c.create_rectangle(self.GAME_X0+2, self.BOARD_HEADER_TOP,
                               self.GAME_X1-2, self.BETTING_BOUNDS[1],
                               fill=self.FELT, outline='',
                               tags=('board_dynamic', 'lucky7_header_band'))
            c.tag_raise('mode_selector')
            c.tag_raise('banker_selector')
            c.tag_raise('squeeze_selector')
            self._draw_mode_header('lucky7', c)
            self._draw_lucky7_jackpot_header()

        for key, box, name, english, color in (
                ('Dragon P', (0, 0, 116, 156), '闲家龙宝', 'PLAYER\nDRAGON', blue),
                ('Dragon B', (622, 0, 738, 156), '庄家龙宝', 'BANKER\nDRAGON', red)):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, cream)
            spots[key]['label_item'] = text(cx, 23, name, 19, color, tag, True)
            text(cx, 57, english, 15, color, tag)
            spots[key]['odds_item'] = text(cx, 94, odds[key], 20, color, tag)
            text(cx, 138, '自然点 / 点差4–9', 10, color, tag, True)

        tag = panel('Lucky 7', (122, 0, 366, 83), '#f2d58a')
        title('Lucky 7', 244, 19, '幸运7', 'Lucky 7', pair_ink)
        for index, (x, condition, rate) in enumerate((
                (183, '闲家两张牌7点获胜', '6:1'),
                (305, '闲家三张牌7点获胜', '15:1'))):
            text(x, 51, condition, 9, pair_ink, tag, True)
            item = text(x, 66, rate, 16, pair_ink, tag)
            if index == 0:
                spots['Lucky 7']['odds_item'] = item
        c.create_line(*xy(244, 44), *xy(244, 73), fill='#000000', width=1,
                      tags=('board_dynamic', tag, 'lucky7_divider'))

        tag = panel('Super 7', (372, 0, 616, 83), '#b7d9ce')
        title('Super 7', 494, 19, '超级幸运7', 'Super Lucky 7', tie_ink)
        text(494, 48, '闲家7点庄家6点结束', 11, tie_ink, tag, True)
        c.create_line(*xy(376, 56), *xy(612, 56), fill='#000000', width=.7,
                      tags=('board_dynamic', tag, 'lucky7_divider'))
        for index, (x, value) in enumerate(((413, '4张牌30:1'),
                                           (494, '5张牌40:1'),
                                           (575, '6张牌100:1#'))):
            item = text(x, 67, value, 11, tie_ink, tag, True)
            if index == 0:
                spots['Super 7']['odds_item'] = item
            if index < 2:
                c.create_line(*xy(x + 40, 57), *xy(x + 40, 74), fill='#000000',
                              width=1, tags=('board_dynamic', tag, 'lucky7_divider'))

        for key, box, fill, name, english, color, condition in (
                ('Small Lucky 6', (122, 87, 366, 156), '#cce3f5', '小幸运6',
                 'Small Lucky 6', '#163a5f', '庄家2张牌6点获胜'),
                ('Big Lucky 6', (372, 87, 616, 156), '#e9d5ea', '大幸运6',
                 'Big Lucky 6', '#4a2457', '庄家3张牌6点获胜')):
            # Leave the seam clear for the independent, circular Lucky 6 wager.
            cx = 235 if key == 'Small Lucky 6' else 503
            tag = panel(key, box, fill)
            title(key, cx, 100, name, english, color)
            text(cx, 132, condition, 12, color, tag, True)
            spots[key]['odds_item'] = text(cx, 147, odds[key], 17, color, tag)

        for key, box, fill, fg, chinese, english in (
                ('Pair Player', (0, 162, 122, 232), '#334458', cream, '闲对', 'PLAYER PAIR'),
                ('Player', (128, 162, 306, 232), '#0046a0', cream, '闲家', 'PLAYER'),
                ('Tie', (312, 162, 426, 232), '#006a35', cream, '和', 'TIE'),
                ('Banker', (432, 162, 610, 232), '#bf0711', cream, '庄家', 'BANKER'),
                ('Pair Banker', (616, 162, 738, 232), '#673c4a', cream, '庄对', 'BANKER PAIR')):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, fill, main=key in ('Player', 'Tie', 'Banker'))
            spots[key]['label_item'] = text(cx, 181, chinese, 23 if key in ('Player', 'Banker') else 18,
                                             fg, tag, True)
            text(cx, 199, english, 11, fg, tag)
            spots[key]['odds_item'] = text(cx, 218, odds[key], 14, fg, tag)

        tag = panel('Lucky 6', (327, 80, 411, 164), badge['normal'], oval=True)
        spots['Lucky 6']['normal_outline'] = badge['rim']
        c.itemconfigure(spots['Lucky 6']['rect_id'], outline=badge['rim'])
        symbol_tags = ('board_dynamic', tag, 'lucky6_symbol')

        def gradient_colour(progress):
            stops = ((195, 28, 44), (242, 148, 31), (255, 225, 90))
            half = 0 if progress < .55 else 1
            amount = progress / .55 if half == 0 else (progress - .55) / .45
            return '#%02x%02x%02x' % tuple(round(a + (b - a) * amount)
                                            for a, b in zip(stops[half], stops[half + 1]))

        for side, value in ((-1, '12:1'), (1, '20:1')):
            wing = ((369 + side * 25, 88), (369 + side * 84, 122),
                    (369 + side * 25, 155), (369, 122))
            # Clipped native polygons give both pointed wings a continuous
            # red/orange/gold gradient without any external image dependency.
            def edges(y):
                amount = (y - 88) / 34 if y <= 122 else (155 - y) / 33
                return (369 + side * (25 + 59 * amount),
                        369 + side * 25 * (1 - amount))

            for stripe in range(48):
                y0, y1 = 88 + 67 * stripe / 48, 88 + 67 * (stripe + 1) / 48
                outer0, inner0 = edges(y0)
                outer1, inner1 = edges(y1)
                points = ((outer0, y0), (outer1, y1), (inner1, y1), (inner0, y0))
                colour = gradient_colour((stripe + .5) / 48)
                c.create_polygon(*(v for x, y in points for v in xy(x, y)),
                                 fill=colour, outline=colour, width=.2,
                                 tags=symbol_tags + ('lucky6_outer_tip', 'lucky6_gradient'))
            c.create_polygon(*(v for x, y in wing for v in xy(x, y)),
                             fill='', outline='#f5d26a', width=1.2,
                             tags=symbol_tags + ('lucky6_outer_tip',))
            text(369 + side * 58, 122, value, 11, '#651322', tag,
                 extra=('lucky6_symbol', 'lucky6_outer_odds'))
        # The opaque circle covers the inward halves of the two wings.
        c.tag_raise(spots['Lucky 6']['rect_id'])

        # Burgundy face, warm gold double rim and an ivory-gold numeral.
        # The curved heading stays fixed while the complete outlined 6 grows.
        for letter, degrees in zip('LUCKY', (142, 116, 90, 64, 38)):
            angle = math.radians(degrees)
            px, py = xy(369 + 34 * math.cos(angle), 122 - 34 * math.sin(angle))
            for dx, dy in ((-.8, 0), (.8, 0), (0, -.8), (0, .8), (0, 0)):
                c.create_text(px + dx * scale, py + dy * scale, text=letter,
                              fill=badge['heading'] if dx == dy == 0 else badge['heading_shadow'],
                              font=('Arial', -max(6, round(9 * scale)), 'bold'),
                              angle=degrees - 90,
                              tags=symbol_tags + ('lucky6_badge_heading',))
        base_size = max(6, round(72 * scale))
        glyph_layers = []
        for dx, dy in ((-2.5, -2.5), (0, -2.5), (2.5, -2.5),
                       (-2.5, 0), (2.5, 0), (-2.5, 2.5), (0, 2.5), (2.5, 2.5)):
            item = c.create_text(*xy(369 + dx, 122 + dy), text='6', fill=badge['stroke'],
                                 font=('Arial', -base_size, 'bold'),
                                 tags=symbol_tags + ('lucky6_numeral_outline',))
            glyph_layers.append((item, dx * sx, dy * sy))
        numeral = c.create_text(*xy(369, 122), text='6', fill=badge['numeral'],
                                font=('Arial', -base_size, 'bold'),
                                tags=symbol_tags + ('lucky6_numeral',))
        spots['Lucky 6']['label_item'] = numeral
        c.create_oval(*box_coords((327, 80, 411, 164)), fill='', outline=badge['rim'],
                      width=3, tags=symbol_tags)
        c.create_oval(*box_coords((329, 82, 409, 162)), fill='', outline=badge['numeral'],
                      width=.8, tags=symbol_tags)
        if interactive:
            # The win signal lives in the annulus outside a centred 20px chip.
            # It never covers the wager or relies on seeing the numeral below it.
            self._lucky6_halo_items = tuple(
                c.create_oval(*box_coords((345, 98, 393, 146)), fill='',
                              outline=badge['numeral'], width=3, state='hidden',
                              tags=symbol_tags + ('lucky6_win_halo',))
                for _ in range(2))
            self._lucky6_circle = spots['Lucky 6']['rect_id']
            self._lucky6_numeral = numeral
            self._lucky6_base_size = base_size
            self._lucky6_glyph_layers = glyph_layers
            self._lucky6_glyph_centre = xy(369, 122)
            self._lucky6_pop_after_id = None
            self._lucky6_pop_step = 0
            self._raise_lucky6_symbol()
        return spots

    def _draw_lucky7_jackpot_header(self):
        """Compact progressive display with room for $1,000,000,000.00."""
        c = self.canvas
        tags = ('board_dynamic', 'lucky7_jackpot_card')
        left, right = self.HEADER_MIDDLE_X - 125, self.HEADER_MIDDLE_X + 125
        top = self.BOARD_HEADER_TOP
        bottom = top + self.BOARD_HEADER_HEIGHT
        middle = self.BOARD_HEADER_Y
        c.create_polygon(left + 6, top, right - 6, top, right, top, right, top+6,
                         right, bottom-6, right, bottom, right - 6, bottom, left + 6, bottom,
                         left, bottom, left, bottom-6, left, top+6, left, top,
                         smooth=True, fill='#20362e', outline='#d6ae53', width=1,
                         tags=tags)
        c.create_text(left + 8, top+11, anchor='w', text='大奖',
                      font=('Microsoft YaHei UI', -14, 'bold'), fill='#ffe7a1',
                      tags=tags + ('lucky7_jackpot_label',))
        c.create_text(left + 8, bottom-10, anchor='w', text='次奖',
                      font=('Microsoft YaHei UI', -14, 'bold'), fill='#d6e9f2',
                      tags=tags + ('lucky7_jackpot_label',))
        c.create_text(right - 12, top+11, anchor='e', text='', font=('Consolas', -19, 'bold'),
                      fill='#ffe7a1', tags=tags + ('lucky7_jackpot_primary', 'jackpot_display'))
        c.create_line(left + 8, middle, right - 8, middle, fill='#667657', width=.5, tags=tags)
        c.create_text(right - 12, bottom-10, anchor='e', text='',
                      font=('Consolas', -17, 'bold'), fill='#d6e9f2',
                      tags=tags + ('lucky7_jackpot_secondary',))
        self._lucky7_jackpot_displayed = None
        self._lucky7_jackpot_target = None
        self._refresh_lucky7_jackpot_info()

    @staticmethod
    def _format_lucky7_jackpot_amount(value):
        """保持原显示样式；隐藏前置零，固定两位小数。"""
        amount = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        sign = '-' if amount < 0 else ''
        integer, fraction = format(abs(amount), '.2f').split('.')
        groups = [integer[max(0, i-3):i] for i in range(len(integer), 0, -3)]
        return '$' + sign + ','.join(reversed(groups)) + '.' + fraction

    def _paint_lucky7_jackpot_amounts(self, amount):
        # Display-only interpolation: never change the real pool or payouts.
        self._lucky7_jackpot_displayed = amount
        primary = self._format_lucky7_jackpot_amount(amount)
        secondary = self._format_lucky7_jackpot_amount(amount * .03)
        self.canvas.itemconfigure('lucky7_jackpot_primary', text=primary,
                                  font=('Consolas', -min(19, max(8, 320 // len(primary))), 'bold'))
        self.canvas.itemconfigure('lucky7_jackpot_secondary', text=secondary,
                                  font=('Consolas', -min(17, max(8, 320 // len(secondary))), 'bold'))

    def _cancel_lucky7_jackpot_counter(self):
        self._lucky7_jackpot_generation = self.__dict__.get('_lucky7_jackpot_generation', 0) + 1
        after_id = self.__dict__.get('_lucky7_jackpot_after_id')
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
        self._lucky7_jackpot_after_id = None

    def _refresh_lucky7_jackpot_info(self):
        if self.game_mode != 'lucky7' or not self.canvas.find_withtag('lucky7_jackpot_card'):
            return
        amount = max(0.0, float(self.jackpot_amount))
        displayed = self.__dict__.get('_lucky7_jackpot_displayed')
        if displayed is None:
            self._lucky7_jackpot_target = amount
            self._paint_lucky7_jackpot_amounts(amount)
            return
        if amount == self.__dict__.get('_lucky7_jackpot_target'):
            return
        self._cancel_lucky7_jackpot_counter()
        self._lucky7_jackpot_target = amount
        generation = self._lucky7_jackpot_generation
        start = float(displayed)

        def count(step):
            if (self._closing or self.game_mode != 'lucky7'
                    or generation != self._lucky7_jackpot_generation
                    or not self.canvas.find_withtag('lucky7_jackpot_card')):
                return
            self._lucky7_jackpot_after_id = None
            value = amount if step == 45 else start + (amount - start) * step / 45.0
            self._paint_lucky7_jackpot_amounts(value)
            if step < 45:
                self._lucky7_jackpot_after_id = self.after(33, lambda: count(step + 1))

        # Increment the monospaced display at about 30 fps over 1.5 seconds.
        # A new target continues from the visible value instead of jumping.
        self._lucky7_jackpot_after_id = self.after(33, lambda: count(1))

    def _set_lucky6_glyph(self, size, visible=True):
        state = 'normal' if visible else 'hidden'
        x, y = self._lucky6_glyph_centre
        ratio = size / self._lucky6_base_size
        for item, dx, dy in self._lucky6_glyph_layers:
            self.canvas.coords(item, x + dx * ratio, y + dy * ratio)
            self.canvas.itemconfigure(item, state=state, fill=self.LUCKY6_BADGE_COLOURS['stroke'],
                                      font=('Arial', -size, 'bold'))
        self.canvas.itemconfigure(self._lucky6_numeral, state=state,
                                  fill=self.LUCKY6_BADGE_COLOURS['numeral'],
                                  font=('Arial', -size, 'bold'))

    def _raise_lucky6_symbol(self):
        if self.game_mode == 'lucky7':
            for tag in ('bet_board_frame', 'lucky7_divider', 'lucky6_symbol',
                        'bet_chip_dynamic', 'chip_motion'):
                self.canvas.tag_raise(tag)

    def _paint_lucky6_win_halo(self, progress):
        """Pulse outside the chip, within the existing 42px badge radius."""
        x, y = self._lucky6_glyph_centre
        scale = self._lucky6_base_size / 72.0
        for index, item in enumerate(self._lucky6_halo_items):
            phase = (progress * 3 + index * .5) % 1.0
            if progress >= 1:
                phase = 1.0 if index == 0 else .55
            radius = (24 + 15 * phase) * scale
            self.canvas.coords(item, x - radius, y - radius, x + radius, y + radius)
            colour = '#%02x%02x%02x' % tuple(round(a + (b - a) * phase)
                for a, b in zip((255, 244, 177), (233, 178, 65)))
            self.canvas.itemconfigure(item, state='normal', outline=colour,
                                      width=(3.2 - 1.2 * phase) * scale)

    def _cancel_lucky6_pop(self, reset=False):
        self._lucky6_pop_generation = self.__dict__.get('_lucky6_pop_generation', 0) + 1
        after_id = self.__dict__.get('_lucky6_pop_after_id')
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
        self._lucky6_pop_after_id = None
        self.canvas.itemconfigure('lucky6_win_halo', state='hidden')
        if reset and self.__dict__.get('_lucky6_numeral') is not None:
            self._lucky6_pop_step = 0
            self.canvas.itemconfigure(self._lucky6_circle, fill=self.LUCKY6_BADGE_COLOURS['normal'])
            self._set_lucky6_glyph(self._lucky6_base_size)
            self.canvas.itemconfigure('lucky6_badge_heading', state='normal')
            self._raise_lucky6_symbol()

    def _start_lucky6_pop(self):
        self._cancel_lucky6_pop(reset=True)
        if not any((key, None) in self.flash_winning_keys
                   for key in ('Small Lucky 6', 'Big Lucky 6', 'Lucky 6')):
            return
        generation = self._lucky6_pop_generation
        self.canvas.itemconfigure(self._lucky6_circle, fill=self.LUCKY6_BADGE_COLOURS['win'])
        self.canvas.itemconfigure('lucky6_badge_heading', state='hidden')
        self._paint_lucky6_win_halo(0)
        self._raise_lucky6_symbol()

        def pulse(step):
            if (self._closing or self.game_mode != 'lucky7' or not self.settlement_running
                    or generation != self._lucky6_pop_generation):
                return
            self._lucky6_pop_after_id = None
            self._lucky6_pop_step = step
            self._paint_lucky6_win_halo(step / 45.0)
            self._raise_lucky6_symbol()
            if step < 45:
                self._lucky6_pop_after_id = self.after(30, lambda: pulse(step + 1))

        # Three gold waves over 1.35s remain visible around a stationary chip.
        # The two rims hold their winning colour until settlement resets them.
        self._lucky6_pop_after_id = self.after(30, lambda: pulse(1))

    def _build_tiger_symbol_frames(self, canvas, width, height, animated=True):
        """Precompute a top-to-bottom wipe without making Pillow mandatory."""
        import base64
        import io

        def photo(payload):
            if Image is not None and ImageTk is not None:
                with Image.open(io.BytesIO(base64.b64decode(payload))) as source:
                    art = source.convert('RGBA').resize((width, height), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(art, master=canvas)
            return tk.PhotoImage(master=canvas, data=payload, format='png')

        normal = photo(self.TIGER_SYMBOL_NORMAL_PNG)
        if not animated:
            return [normal]
        winning = photo(self.TIGER_SYMBOL_WIN_PNG)
        width, height = normal.width(), normal.height()
        frames = [normal]
        for step in range(1, 31):
            frame = tk.PhotoImage(master=canvas, width=width, height=height)
            frame.tk.call(str(frame), 'copy', str(normal), '-compositingrule', 'set')
            cut = round(height * step / 30)
            frame.tk.call(str(frame), 'copy', str(winning), '-from', 0, 0, width, cut,
                          '-to', 0, 0, '-compositingrule', 'set')
            frames.append(frame)
        return frames

    def _raise_tiger_symbol(self):
        if self.game_mode == 'tiger':
            # Pair tier dividers must survive the white winning overlay.
            self.canvas.tag_raise('tiger_pair_divider')
            self.canvas.tag_raise('tiger_symbol')
            self.canvas.tag_raise('bet_chip_dynamic')
            self.canvas.tag_raise('chip_motion')

    def _show_tiger_symbol_frame(self, step):
        frames = self.__dict__.get('_tiger_symbol_frames', ())
        if not frames:
            return
        step = min(step, len(frames) - 1)
        self._tiger_symbol_frame = step
        self.canvas.itemconfigure(self._tiger_symbol_image, image=frames[step])
        progress = step / max(1, len(frames) - 1)
        for item, threshold in self._tiger_symbol_captions:
            self.canvas.itemconfigure(item, fill='#bb1725' if progress >= threshold else '#e9bc47')
        self._raise_tiger_symbol()

    def _cancel_tiger_symbol_transition(self, reset=False):
        after_id = self.__dict__.get('_tiger_symbol_after_id')
        self._tiger_symbol_generation = self.__dict__.get('_tiger_symbol_generation', 0) + 1
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
        self._tiger_symbol_after_id = None
        if reset:
            self._show_tiger_symbol_frame(0)

    def _start_tiger_symbol_transition(self):
        self._cancel_tiger_symbol_transition(reset=True)
        if not any((key, None) in self.flash_winning_keys
                   for key in ('Small Tiger', 'Big Tiger', 'Tiger')):
            return
        if not self.__dict__.get('_tiger_symbol_frames'):
            return
        generation = self._tiger_symbol_generation
        last_step = len(self._tiger_symbol_frames) - 1

        def advance(step):
            if (self._closing or self.game_mode != 'tiger' or not self.settlement_running
                    or generation != self._tiger_symbol_generation):
                return
            self._tiger_symbol_after_id = None
            self._show_tiger_symbol_frame(step)
            if step < last_step:
                self._tiger_symbol_after_id = self.after(60, lambda: advance(step + 1))

        # Begin at flash time zero, independently of the 450 ms flash phases.
        advance(1)

    def draw_ez_betting_board(self, canvas=None, bounds=None, interactive=True):
        """Draw the photo's Five Treasures layout using native Canvas artwork.

        The renderer is EZ-only. The same drawing is reused by the rules
        preview, without registering live wagers on that preview canvas.
        No image files or new third-party dependencies are required.
        """
        c = self.canvas if canvas is None else canvas
        if bounds is None:
            bounds = self.BETTING_BOUNDS
        bx0, by0, bx1, by1 = bounds
        sx, sy = (bx1 - bx0) / 738.0, (by1 - by0) / 234.0
        font_scale = min(sx, sy)
        cream, ink, felt = '#f8ecd3', '#110b07', self.FELT
        player_ink, banker_ink = '#01479a', '#a80909'
        treasure_ink = '#800600'
        odds = self._board_odds('ez')
        spots = {}

        def xy(x, y):
            return bx0 + x * sx, by0 + y * sy

        def coords(points):
            return tuple(v for x, y in zip(points[::2], points[1::2]) for v in xy(x, y))

        def text(x, y, value, size, color, tag, family='Arial', anchor='center',
                 bold=True, angle=0):
            return c.create_text(*xy(x, y), text=value, fill=color,
                                 font=(family, -max(6, round(size * font_scale)),
                                       'bold' if bold else 'normal'),
                                 anchor=anchor, justify='center', angle=angle,
                                 tags=('board_dynamic', tag))

        def rounded(x0, y0, x1, y1, radius=7):
            return coords((x0 + radius, y0, x1 - radius, y0, x1, y0,
                           x1, y0 + radius, x1, y1 - radius, x1, y1,
                           x1 - radius, y1, x0 + radius, y1, x0, y1,
                           x0, y1 - radius, x0, y0 + radius, x0, y0))

        def panel(key, box, fill, main=False, oval=False):
            x0, y0, x1, y1 = box
            tag = self.spot_tag((key, None))
            tags = ('board_dynamic', tag)
            if oval:
                shape = coords(box)
                c.create_oval(*coords((x0 - 3, y0 - 3, x1 + 3, y1 + 3)),
                              fill=ink, outline=ink, width=2, tags=tags)
                rect = c.create_oval(*shape, fill=fill, outline='#ffe59a', width=2, tags=tags)
                # Outline-only artwork can be raised over labels and flashes
                # without covering the circle fill or its Chinese text.
                c.create_oval(*coords((x0 - 2, y0 - 2, x1 + 2, y1 + 2)),
                              fill='', outline=ink, width=4,
                              tags=tags + ('ez_cover_border', 'ez_cover_outline'))
            else:
                c.create_polygon(*rounded(x0 - 2, y0 - 1, x1 + 2, y1 + 2),
                                 smooth=True, fill=ink, outline=ink,
                                 width=2, tags=tags)
                shape = rounded(x0, y0, x1, y1)
                rect = c.create_polygon(*shape, smooth=True, fill=fill,
                                        outline=cream, width=1.2, tags=tags)
                c.create_polygon(*shape, smooth=True, fill='', outline=cream,
                                 width=1.2, tags=tags + ('bet_board_frame',))
                c.create_polygon(*rounded(x0 + 2, y0 + 2, x1 - 2, y1 - 2),
                                 smooth=True, fill='', outline=player_ink if key == 'Dragon P'
                                 else banker_ink if key == 'Dragon B' else fill,
                                 width=0.7,
                                 tags=tags + ('bet_board_frame', 'bet_board_inner_frame'))
            spot = {'tag': tag, 'rect_id': rect, 'bounds': coords(box),
                    'chip_pos': xy((x0 + x1) / 2, (y0 + y1) / 2),
                    'base_odds': odds[key], 'main': main,
                    'normal_outline': '#ffe59a' if oval else cream,
                    'normal_outline_width': 2 if oval else 1.2,
                    'ez_shape': 'oval' if oval else 'polygon', 'ez_shape_coords': shape,
                    'label': BaccaratEngine.DISPLAY_NAMES.get(key, key)}
            spots[key] = spot
            if interactive:
                self.register_spot(key, *spot['bounds'], spot['chip_pos'], spot['label'])
                self.bet_spots[(key, None)].update(spot)
                spots[key] = self.bet_spots[(key, None)]
                c.tag_bind(tag, '<Button-1>', lambda _e, bt=key: self.place_bet(bt))
                c.tag_bind(tag, '<Button-3>', lambda _e, bt=key: self.clear_single_bet(bt))
                c.tag_bind(tag, '<Enter>', lambda _e, bt=key: self._set_bet_hover(bt))
                c.tag_bind(tag, '<Leave>', lambda _e: self._set_bet_hover(None))
            return tag

        def title(key, x, y, english, chinese, color=treasure_ink):
            tag = spots[key]['tag']
            # Reference format: large Chinese heading, small English below.
            # Text anchors stay fixed when a centred chip is placed over them.
            spots[key]['label_item'] = text(x, y, chinese, 20, color, tag, 'Microsoft YaHei UI')
            text(x, y + 15, english, 11, color, tag)

        c.create_rectangle(*coords((-8, -2, 746, 244)), fill=felt,
                           outline='', tags=('board_dynamic', 'bet_board_background'))
        if interactive:
            self._draw_mode_header('ez', c)

        # The old Pair / Tie / Pair top band is removed. Two tall Dragon
        # Bonus spots flank the four shorter Five Treasures panels.
        for key, box, chinese, english, color in (
                ('Dragon P', (0, 0, 116, 156), '闲家龙宝', 'PLAYER\nDRAGON', player_ink),
                ('Dragon B', (622, 0, 738, 156), '庄家龙宝', 'BANKER\nDRAGON', banker_ink)):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, cream)
            spots[key]['label_item'] = text(cx, 23, chinese, 19, color, tag, 'Microsoft YaHei UI')
            text(cx, 57, english, 15, color, tag)
            spots[key]['odds_item'] = text(cx, 94, odds[key], 20, color, tag)
            text(cx, 138, '自然点 / 点差4–9', 10, color, tag, 'Microsoft YaHei UI')

        tag = panel('Fortune 7', (122, 0, 366, 76), '#fbc021')
        title('Fortune 7', 244, 13, 'FORTUNE 7', '财运亨通7')
        text(244, 47, '庄家三张牌7点获胜', 11, treasure_ink, tag, 'Microsoft YaHei UI')
        spots['Fortune 7']['odds_item'] = text(244, 64, '40:1', 16, treasure_ink, tag)

        tag = panel('Golden 8', (372, 0, 616, 76), '#a1bd55')
        title('Golden 8', 494, 13, 'GOLDEN 8', '金甲神将8')
        text(494, 47, '闲家三张牌8点获胜', 11, treasure_ink, tag, 'Microsoft YaHei UI')
        spots['Golden 8']['odds_item'] = text(494, 64, '25:1', 16, treasure_ink, tag)

        tag = panel('Heavenly 9', (122, 80, 366, 156), '#b6e1f6')
        title('Heavenly 9', 244, 94, 'HEAVENLY 9', '天上人间9', color=player_ink)
        c.create_line(*coords((244, 120, 244, 152)), fill=player_ink, width=1,
                      tags=('board_dynamic', tag))
        text(187, 130, '闲庄均为三张牌9点', 9, player_ink, tag, 'Microsoft YaHei UI')
        text(301, 130, '闲家或庄家三张牌9点', 9, player_ink, tag, 'Microsoft YaHei UI')
        spots['Heavenly 9']['odds_item'] = text(187, 147, '75:1', 14, player_ink, tag)
        text(301, 147, '10:1', 14, player_ink, tag)

        tag = panel('Blazing 7s', (372, 80, 616, 156), '#dd3a20')
        title('Blazing 7s', 494, 94, 'BLAZING 7s', '龙凤呈祥7s', color=cream)
        c.create_line(*coords((494, 120, 494, 152)), fill=cream, width=1,
                      tags=('board_dynamic', tag))
        text(437, 130, '闲庄均为三张牌7点', 9, cream, tag, 'Microsoft YaHei UI')
        text(551, 130, '闲庄均为两张牌7点', 9, cream, tag, 'Microsoft YaHei UI')
        spots['Blazing 7s']['odds_item'] = text(437, 147, '125:1', 14, cream, tag)
        text(551, 147, '60:1', 14, cream, tag)

        # One bottom band, left to right: Pair Player / Player / Tie /
        # Banker / Pair Banker. Each wager is registered exactly once.
        for key, box, fill, fg, chinese, english in (
                ('Pair Player', (0, 162, 122, 232), '#334458', cream, '闲对', 'PLAYER PAIR'),
                ('Player', (128, 162, 306, 232), '#0046a0', cream, '闲家', 'PLAYER'),
                ('Tie', (312, 162, 426, 232), '#006a35', cream, '和', 'TIE'),
                ('Banker', (432, 162, 610, 232), '#bf0711', cream, '庄家', 'BANKER'),
                ('Pair Banker', (616, 162, 738, 232), '#673c4a', cream, '庄对', 'BANKER PAIR')):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, fill, main=key in ('Player', 'Tie', 'Banker'))
            spots[key]['label_item'] = text(cx, 181, chinese, 23 if key in ('Player', 'Banker') else 18,
                                             fg, tag, 'Microsoft YaHei UI')
            text(cx, 199, english, 11, fg, tag)
            spots[key]['odds_item'] = text(cx, 218, odds[key], 14, fg, tag)

        tag = panel('Cover All', (334, 43, 404, 113), '#fbc021', oval=True)
        # Two curved arrows identify the four qualifying panels, as in the photo.
        # Start at the lower circle rim, leaving its labels and odds clear.
        for points in ((338, 94, 332, 106, 318, 115, 304, 115),
                       (400, 94, 406, 106, 420, 115, 434, 115)):
            c.create_line(*coords(points), smooth=True, fill='#ffd83d', width=10 * font_scale,
                          arrow='last', arrowshape=(13 * font_scale, 15 * font_scale, 7 * font_scale),
                          tags=('board_dynamic', tag, 'ez_cover_arrows', 'ez_cover_outline'))
            c.create_line(*coords(points), smooth=True, fill=ink, width=6 * font_scale,
                          arrow='last', arrowshape=(10 * font_scale, 12 * font_scale, 5 * font_scale),
                          tags=('board_dynamic', tag, 'ez_cover_arrows', 'ez_cover_outline'))
        spots['Cover All']['label_item'] = text(369, 69, '覆盖\n全部', 16, treasure_ink,
                                               tag, 'Microsoft YaHei UI')
        spots['Cover All']['odds_item'] = text(369, 95, '6:1', 14, treasure_ink, tag)
        return spots

    def draw_classic_betting_board(self, canvas=None, bounds=None, interactive=True):
        return self._draw_standard_betting_board('classic', canvas, bounds, interactive)

    def draw_2to1_betting_board(self, canvas=None, bounds=None, interactive=True):
        return self._draw_standard_betting_board('2to1', canvas, bounds, interactive)

    def draw_one_deck_betting_board(self, canvas=None, bounds=None, interactive=True):
        return self._draw_standard_betting_board('one_deck', canvas, bounds, interactive)

    def draw_monkey_betting_board(self, canvas=None, bounds=None, interactive=True):
        return self._draw_standard_betting_board('monkey', canvas, bounds, interactive)

    def draw_goldendice_betting_board(self, canvas=None, bounds=None, interactive=True):
        return self._draw_standard_betting_board('goldendice', canvas, bounds, interactive)

    def draw_treasure_betting_board(self, canvas=None, bounds=None, interactive=True):
        return self._draw_standard_betting_board('treasure', canvas, bounds, interactive)

    def draw_xxx_betting_board(self, canvas=None, bounds=None, interactive=True):
        return self._draw_standard_betting_board('xxx', canvas, bounds, interactive)

    def _draw_standard_betting_board(self, mode, canvas=None, bounds=None, interactive=True):
        """Shared frame, hit areas and preview rendering for Classic-style boards."""
        c = self.canvas if canvas is None else canvas
        if bounds is None:
            bounds = self.BETTING_BOUNDS
        bx0, by0, bx1, by1 = bounds
        sx, sy = (bx1 - bx0) / 738.0, (by1 - by0) / 234.0
        scale = min(sx, sy)
        cream, ink, felt = '#f8ecd3', '#110b07', self.FELT
        blue, red = '#01479a', '#a80909'
        odds, spots = self._board_odds(mode), {}

        def xy(x, y):
            return bx0 + x * sx, by0 + y * sy

        def coords(points):
            return tuple(v for x, y in zip(points[::2], points[1::2]) for v in xy(x, y))

        def text(x, y, value, size, color, tag, family='Arial'):
            return c.create_text(*xy(x, y), text=value, fill=color,
                                 font=(family, -max(6, round(size * scale)), 'bold'),
                                 anchor='center', justify='center', angle=0,
                                 tags=('board_dynamic', tag))

        def rounded(x0, y0, x1, y1, radius=7):
            return coords((x0 + radius, y0, x1 - radius, y0, x1, y0,
                           x1, y0 + radius, x1, y1 - radius, x1, y1,
                           x1 - radius, y1, x0 + radius, y1, x0, y1,
                           x0, y1 - radius, x0, y0 + radius, x0, y0))

        def panel(key, box, fill, main=False, outline=None, shadow=True):
            x0, y0, x1, y1 = box
            outline = cream if outline is None else outline
            tag = self.spot_tag((key, None))
            tags = ('board_dynamic', tag)
            if shadow:
                c.create_polygon(*rounded(x0 - 2, y0 - 1, x1 + 2, y1 + 2),
                                 smooth=True, fill=ink, outline=ink, width=2, tags=tags)
            shape = rounded(*box)
            rect = c.create_polygon(*shape, smooth=True, fill=fill,
                                    outline=outline, width=1.2, tags=tags)
            c.create_polygon(*shape, smooth=True, fill='', outline=outline,
                             width=1.2, tags=tags + ('bet_board_frame',))
            c.create_polygon(*rounded(x0 + 2, y0 + 2, x1 - 2, y1 - 2),
                             smooth=True, fill='', outline=blue if key == 'Dragon P'
                             else red if key == 'Dragon B' else fill, width=.7,
                             tags=tags + ('bet_board_frame', 'bet_board_inner_frame'))
            spot = dict(tag=tag, rect_id=rect, bounds=coords(box),
                        chip_pos=xy((x0 + x1) / 2, (y0 + y1) / 2),
                        base_odds=odds[key], main=main, normal_outline=outline,
                        normal_outline_width=1.2, classic_shape_coords=shape,
                        label=BaccaratEngine.display_name(key, mode))
            spots[key] = spot
            if interactive:
                self.register_spot(key, *spot['bounds'], spot['chip_pos'], spot['label'])
                self.bet_spots[(key, None)].update(spot)
                spots[key] = self.bet_spots[(key, None)]
                c.tag_bind(tag, '<Button-1>', lambda _e, bt=key: self.place_bet(bt))
                c.tag_bind(tag, '<Button-3>', lambda _e, bt=key: self.clear_single_bet(bt))
                c.tag_bind(tag, '<Enter>', lambda _e, bt=key: self._set_bet_hover(bt))
                c.tag_bind(tag, '<Leave>', lambda _e: self._set_bet_hover(None))
            return tag

        def title(key, x, y, chinese, english, color):
            tag = spots[key]['tag']
            spots[key]['label_item'] = text(x, y, chinese, 20, color, tag, 'Microsoft YaHei UI')
            text(x, y + 15, english, 11, color, tag)

        c.create_rectangle(*coords((-8, -2, 746, 244)), fill=felt,
                           outline='', tags=('board_dynamic', 'bet_board_background'))
        if interactive:
            self._draw_mode_header(mode, c)
            if mode == '2to1':
                c.create_text(self.HEADER_MIDDLE_X, self.BOARD_HEADER_Y,
                    text='自然点赢赔2:1', font=('Microsoft YaHei UI', 16, 'bold'),
                    fill=self.GOLD, anchor='center',
                    tags=('board_dynamic', 'two_to_one_natural_note'))

        # Always modes reuse these two live side areas with their own rules.
        for key, box, chinese, english, color in (
                ('Dragon P', (0, 0, 116, 156), '闲家龙宝', 'PLAYER\nDRAGON', blue),
                ('Dragon B', (622, 0, 738, 156), '庄家龙宝', 'BANKER\nDRAGON', red)):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, cream)
            if mode in BaccaratEngine.ALWAYS_MODES:
                chinese = (f'庄家以{mode[-1]}点\n获胜' if key == 'Dragon P'
                           else '庄家需要\n补第三张')
                english = (f'BANKER WINS\nWITH {mode[-1]} POINTS' if key == 'Dragon P'
                           else 'BANKER DRAWS\nTHIRD CARD')
                condition = (f'最终点数为{mode[-1]}\n且庄家获胜' if key == 'Dragon P'
                             else '不论输赢或和局\n补牌即中奖')
                spots[key]['label_item'] = text(cx, 28, chinese, 17, color, tag,
                                                 'Microsoft YaHei UI')
                text(cx, 65, english, 11, color, tag)
                spots[key]['odds_item'] = text(cx, 101, odds[key], 22, color, tag)
                text(cx, 137, condition, 10, color, tag, 'Microsoft YaHei UI')
                continue
            spots[key]['label_item'] = text(cx, 23, chinese, 19, color, tag, 'Microsoft YaHei UI')
            text(cx, 57, english, 15, color, tag)
            spots[key]['odds_item'] = text(cx, 94, odds[key], 20, color, tag)
            if mode in ('goldendice', 'treasure', 'xxx'):
                text(cx, 117, '免手续费', 10, color, tag, 'Microsoft YaHei UI')
            text(cx, 138, '自然点 / 点差4–9', 10, color, tag, 'Microsoft YaHei UI')

        if mode == 'classic':
            # Split each former top treasure into two independently clickable spots.
            for key, box, fill, color, chinese, english, condition in (
                    ('Small', (122, 0, 241, 76), '#f3d180', '#503809', '小', 'SMALL', '共4张牌结束'),
                    ('Odd', (247, 0, 366, 76), '#97d3c5', '#103d36', '单', 'ODD', '合计点数个位为单'),
                    ('Even', (372, 0, 491, 76), '#9fc7e8', '#153b60', '双', 'EVEN', '合计点数个位为双'),
                    ('Big', (497, 0, 616, 76), '#e9b1bf', '#5b2339', '大', 'BIG', '共5或6张牌结束')):
                cx = (box[0] + box[2]) / 2
                tag = panel(key, box, fill)
                title(key, cx, 13, chinese, english, color)
                text(cx, 47, condition, 10, color, tag, 'Microsoft YaHei UI')
                spots[key]['odds_item'] = text(cx, 64, odds[key], 16, color, tag)

            tag = panel('Any Pair', (122, 80, 366, 156), '#b6e1f6')
            title('Any Pair', 244, 94, '任意对子', 'ANY PAIR', blue)
            text(244, 130, '任一方前两张牌同点数', 11, blue, tag, 'Microsoft YaHei UI')
            spots['Any Pair']['odds_item'] = text(244, 147, odds['Any Pair'], 16, blue, tag)

            tag = panel('Perfect Pair', (372, 80, 616, 156), '#dd3a20')
            title('Perfect Pair', 494, 94, '完美对子', 'PERFECT PAIR', cream)
            c.create_line(*coords((494, 120, 494, 152)), fill='#000000', width=1,
                          tags=('board_dynamic', tag, 'bet_board_frame', 'classic_divider'))
            for index, (x, caption, rate) in enumerate(((433, '单方完美对子', '25:1'),
                                                      (555, '双方完美对子', '250:1'))):
                text(x, 130, caption, 10, cream, tag, 'Microsoft YaHei UI')
                item = text(x, 147, rate, 14, cream, tag)
                if index == 0:
                    spots['Perfect Pair']['odds_item'] = item

        elif mode == 'goldendice':
            for key, box, chinese, english, condition in (
                    ('Super Dice', (122, 0, 241, 156), '超级骰子', 'SUPER DICE', '骰8/9 + 对子'),
                    ('Dice Points', (497, 0, 616, 156), '骰子点数', 'DICE POINTS', '骰点 = 闲庄最大点数')):
                cx = (box[0] + box[2]) / 2
                tag = panel(key, box, self.BET_COLORS[key] if key == 'Dice Points' else '#544019')
                accent = '#c3f0ed' if key == 'Dice Points' else '#ffe69b'
                title(key, cx, 24, chinese, english, accent)
                text(cx, 65, condition, 10, cream, tag, 'Microsoft YaHei UI')
                spots[key]['odds_item'] = text(cx, 91, odds[key], 13, accent, tag)
                text(cx, 117, '免手续费', 11, cream, tag, 'Microsoft YaHei UI')
                text(cx, 141, '六档 · 最高档优先' if key == 'Super Dice'
                     else '10→0 · 11→1 · 12输', 9, cream, tag, 'Microsoft YaHei UI')
                spots[key]['chip_pos'] = xy(cx, 77)
            self._draw_golden_dice_cup(c, bounds, interactive)

        elif mode in ('treasure', 'xxx'):
            is_xxx = mode == 'xxx'
            dedicated = 'Golden Duel' if is_xxx else 'Golden Hunter'
            tag = panel(dedicated, (122, 0, 241, 156), '#544019')
            title(dedicated, 181.5, 19, '黄金对决' if is_xxx else '黄金猎手',
                  'GOLDEN DUEL' if is_xxx else 'GOLDEN HUNTER', '#ffe69b')
            spots[dedicated]['odds_item'] = text(
                181.5, 53, odds[dedicated], 13, '#ffe69b', tag)
            if is_xxx:
                for row, caption in enumerate(('双方有金 15:1', '双方有金+和 35:1',
                        '黄金对子 100:1', '双方金对 3000:1')):
                    text(181.5, 73+row*17, caption, 11, cream, tag,
                         'Microsoft YaHei UI')
            else:
                text(181.5, 76, '2张 3:1 · 3张 25:1', 10, cream, tag)
                text(181.5, 94, '4张 155:1', 10, cream, tag)
                text(181.5, 112, '5张3150 · 6张51000', 9, cream, tag)
            text(181.5, 141, '免手续费', 10, cream, tag, 'Microsoft YaHei UI')
            spots[dedicated]['chip_pos'] = xy(181.5, 85)
            side_specs = (
                    ('Golden Count 4-5', (497, 0, 616, 76), '#856724',
                     '4-5张黄金扑克', '系统选出牌面数'),
                    ('Golden Count 7-8', (497, 80, 616, 156), '#28615e',
                     '7-8张黄金扑克', '系统选出牌面数')) if is_xxx else (
                    ('Golden Present', (497, 0, 616, 76), '#856724',
                     '有黄金扑克', '任意1张或以上'),
                    ('Golden Absent', (497, 80, 616, 156), '#28615e',
                     '没黄金扑克', '全部没有黄金牌'))
            for key, box, fill, caption, condition in side_specs:
                cy = box[1]
                tag = panel(key, box, fill)
                spots[key]['label_item'] = text(556.5, cy + 13, caption, 14 if is_xxx else 17,
                                                cream, tag, 'Microsoft YaHei UI')
                text(556.5, cy + 31, condition, 10, cream, tag, 'Microsoft YaHei UI')
                spots[key]['odds_item'] = text(556.5, cy + 48, odds[key], 15, '#ffe69b', tag)
                text(556.5, cy + 66, '免手续费', 9, cream, tag, 'Microsoft YaHei UI')
                spots[key]['chip_pos'] = xy(556.5, cy + 39)
            self._draw_treasure_card_area(c, bounds, interactive, mode=mode)

        elif mode in ('2to1', 'one_deck') + BaccaratEngine.ALWAYS_MODES:
            if mode in BaccaratEngine.SPECIAL_MODES:
                # Green outer frame on black, with Special's light-to-dark
                # green wager cells. The first row remains plain heading text.
                c.create_polygon(*rounded(122, 0, 616, 76), smooth=True,
                                 fill='#000000', outline=self.TIE_GREEN,
                                 width=max(1, 2 * scale),
                                 tags=('board_dynamic', 'one_deck_tie_panel'))
                text(369, 11, '和局点数', 17, self.TIE_POINT_COLORS['Tie 1'],
                     'one_deck_tie_heading',
                     'Microsoft YaHei UI')
                gap = 3
                width = (612 - 126 - gap * 9) / 10
                for point in range(10):
                    key = f'Tie {point}'
                    left = 126 + point * (width + gap)
                    cx = left + width / 2
                    fill = self.TIE_POINT_COLORS[key]
                    foreground = self.contrast_text_color(fill)
                    tag = panel(key, (left, 27, left + width, 70), fill,
                                outline=self.TIE_GREEN, shadow=False)
                    spots[key]['label_item'] = text(cx, 41, str(point), 20, foreground, tag)
                    spots[key]['odds_item'] = text(cx, 61, odds[key], 11, foreground, tag)
            else:
                # Split each former top treasure into two independently clickable spots.
                for key, box, fill, color, chinese, english, condition in (
                        ('N9/N7', (122, 0, 241, 76), '#c8afe0', '#3f2359', 'N9/N7', '2-CARD 9 VS 7', '双方均为2张牌'),
                        ('9/7', (247, 0, 366, 76), '#97d3c5', '#103d36', '9/7', '3-CARD 9 VS 7', '双方均为3张牌'),
                        ('9/1', (372, 0, 491, 76), '#9fc7e8', '#153b60', '9/1', '3-CARD 9 VS 1', '双方均为3张牌'),
                        ('8/6', (497, 0, 616, 76), '#f1b17b', '#5a2d12', '8/6', '8 BEATS 6', '不限双方牌数')):
                    cx = (box[0] + box[2]) / 2
                    tag = panel(key, box, fill)
                    title(key, cx, 13, chinese, english, color)
                    text(cx, 47, condition, 10, color, tag, 'Microsoft YaHei UI')
                    spots[key]['odds_item'] = text(cx, 64, odds[key], 16, color, tag)

            tag = panel('Any Pair', (247, 80, 491, 156), '#b6e1f6')
            title('Any Pair', 369, 94, '任意对子', 'ANY PAIR', blue)
            text(369, 130, '任一方前两张牌同点数', 11, blue, tag, 'Microsoft YaHei UI')
            spots['Any Pair']['odds_item'] = text(369, 147, odds['Any Pair'], 16, blue, tag)

            # Size wagers sit below the outer score-combination wagers.
            for key, box, fill, color, chinese, english, condition in (
                    ('Small', (122, 80, 241, 156), '#f3d180', '#503809', '小', 'SMALL', '共4或5张牌结束' if mode == 'one_deck' else '共4张牌结束'),
                    ('Big', (497, 80, 616, 156), '#e9b1bf', '#5b2339', '大', 'BIG', '共6张牌结束' if mode == 'one_deck' else '共5或6张牌结束')):
                cx = (box[0] + box[2]) / 2
                tag = panel(key, box, fill)
                title(key, cx, 94, chinese, english, color)
                text(cx, 130, condition, 10, color, tag, 'Microsoft YaHei UI')
                spots[key]['odds_item'] = text(cx, 147, odds[key], 16, color, tag)

        else:  # monkey
            # Replace the two upper EZ treasures with four independent wagers.
            for key, box, fill, color, chinese, english, condition in (
                    ('All Monkeys', (122, 0, 241, 76), '#f3d180', '#503809',
                     '全猴', 'ALL MONKEYS', '前4张全为J/Q/K'),
                    ('Monkey 6', (247, 0, 366, 76), '#97d3c5', '#103d36',
                     '猴老六', 'MONKEY 6', '闲补非猴，庄补猴'),
                    ('Monkey Tie', (372, 0, 491, 76), '#9fc7e8', '#153b60',
                     '猴老六和', 'MONKEY 6 TIE', '猴老六条件且和局'),
                    ('No Monkeys', (497, 0, 616, 76), '#e9b1bf', '#5b2339',
                     '无猴', 'NO MONKEYS', '前4张均非J/Q/K')):
                cx = (box[0] + box[2]) / 2
                tag = panel(key, box, fill)
                title(key, cx, 13, chinese, english, color)
                text(cx, 47, condition, 10, color, tag, 'Microsoft YaHei UI')
                spots[key]['odds_item'] = text(cx, 64, odds[key], 16, color, tag)

            # Three lower wagers share the former Heavenly 9 / Blazing 7s band.
            for key, box, fill, color, chinese, english, condition in (
                    ('Monkey 7', (122, 80, 283, 156), '#c8afe0', '#3f2359',
                     '猴7点', 'MONKEY 7', '庄家3张牌7点获胜'),
                    ('Big Monkey', (289, 80, 449, 156), '#f1b17b', '#5a2d12',
                     '猴子六仙', 'SIX MONKEYS', '六张牌全为J/Q/K'),
                    ('Lucky Monkey', (455, 80, 616, 156), '#cbdba3', '#31451d',
                     '幸运猴子', 'LUCKY MONKEY', '按补牌猴子组合派彩')):
                cx = (box[0] + box[2]) / 2
                tag = panel(key, box, fill)
                title(key, cx, 94, chinese, english, color)
                text(cx, 130, condition, 10, color, tag, 'Microsoft YaHei UI')
                spots[key]['odds_item'] = text(cx, 147, odds[key], 16, color, tag)

        # Shared main row; each mode retains its own odds.
        for key, box, fill, chinese, english in (
                ('Pair Player', (0, 162, 122, 232), '#334458', '闲对', 'PLAYER PAIR'),
                ('Player', (128, 162, 306, 232), '#0046a0', '闲家', 'PLAYER'),
                ('Tie', (312, 162, 426, 232), '#006a35', '和', 'TIE'),
                ('Banker', (432, 162, 610, 232), '#bf0711', '庄家', 'BANKER'),
                ('Pair Banker', (616, 162, 738, 232), '#673c4a', '庄对', 'BANKER PAIR')):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, fill, main=key in ('Player', 'Tie', 'Banker'))
            spots[key]['label_item'] = text(cx, 181, chinese,
                23 if key in ('Player', 'Banker') else 18, cream, tag, 'Microsoft YaHei UI')
            text(cx, 199, english, 11, cream, tag)
            spots[key]['odds_item'] = text(cx, 218, odds[key], 14, cream, tag)
        return spots

    def draw_bet_row(self, bet_types, x0, y0, y1, odds):
        count = len(bet_types)
        if count <= 0:
            return
        width = (self.BOARD_INNER_X1 - x0) / count
        for index, bet_type in enumerate(bet_types):
            bx0 = x0 + index * width
            bx1 = self.BOARD_INNER_X1 if index == count - 1 else bx0 + width
            self.draw_bet_spot(bet_type, bx0, y0, bx1, y1, odds.get(bet_type, ''), main=False)

    @staticmethod
    def spot_tag(key):
        bet_type, param = key
        safe = 'none' if param is None else re.sub(r'[^0-9A-Za-z]+', '_', str(param))
        safe_type = re.sub(r'[^0-9A-Za-z]+', '_', str(bet_type))
        return f'betspot_{safe_type}_{safe}'

    def register_spot(self, bet_type, x0, y0, x1, y1, chip_pos, label):
        key = (bet_type, None)
        self.bet_spots[key] = {
            'bounds': (x0, y0, x1, y1), 'chip_pos': chip_pos,
            'label': label, 'tag': self.spot_tag(key),
        }

    def draw_bet_spot(self, bet_type, x0, y0, x1, y1, odds_text, main=False):
        c = self.canvas
        tag = self.spot_tag((bet_type, None))
        fill = self.BET_COLORS.get(bet_type, '#45665c')
        fg = '#111111' if bet_type == 'Panda 8' else 'white'
        golden_side = bet_type in ('Golden Hunter', 'Golden Duel', 'Super Dice')
        outline = '#f0cf54' if golden_side else '#d5cbbd'
        outline_width = 2 if golden_side else 1
        rect_id = c.create_rectangle(
            x0 + 2, y0 + 2, x1 - 2, y1 - 2,
            fill=fill, outline=outline, width=outline_width,
            tags=('board_dynamic', tag))

        label = BaccaratEngine.display_name(bet_type, self.game_mode)
        if main:
            label_item = c.create_text(
                (x0 + x1) / 2, y0 + 27, text=label,
                font=('Arial', 23, 'bold'), fill=fg,
                tags=('board_dynamic', tag))
            odds_item = c.create_text(
                (x0 + x1) / 2, y1 - 15, text=odds_text,
                font=('Arial', 18, 'bold'), fill=fg,
                tags=('board_dynamic', tag))
            odds_y = y1 - 15
        else:
            label_item = c.create_text(
                (x0 + x1) / 2, y0 + 23, text=label,
                font=('Arial', 15, 'bold'), fill=fg,
                tags=('board_dynamic', tag))
            odds_item = c.create_text(
                (x0 + x1) / 2, y1 - 13, text=odds_text,
                font=('Arial', 11, 'bold'), fill=fg,
                tags=('board_dynamic', tag))
            odds_y = y1 - 13

        chip_y = (y0 + y1) / 2
        self.register_spot(
            bet_type, x0 + 2, y0 + 2, x1 - 2, y1 - 2,
            ((x0 + x1) / 2, chip_y), label)
        spot = self.bet_spots[(bet_type, None)]
        spot.update({
            'rect_id': rect_id, 'label_item': label_item, 'odds_item': odds_item,
            'base_odds': odds_text, 'odds_y': odds_y, 'odds_base_x': (x0 + x1) / 2, 'main': bool(main),
            'normal_outline': outline, 'normal_outline_width': outline_width,
        })
        c.tag_bind(tag, '<Button-1>', lambda _e, bt=bet_type: self.place_bet(bt))
        c.tag_bind(tag, '<Button-3>', lambda _e, bt=bet_type: self.clear_single_bet(bt))
        c.tag_bind(tag, '<Enter>', lambda _e, bt=bet_type: self._set_bet_hover(bt))
        c.tag_bind(tag, '<Leave>', lambda _e: self._set_bet_hover(None))

    def _set_bet_hover(self, bet_type):
        self._hovered_bet_type = bet_type
        if bet_type is None:
            self.canvas.configure(cursor='')
        else:
            self._update_main_bet_availability()

    def _golden_dice_has_base_bet(self):
        return any(self.bet_state.current_area_bet(key) > 0
                   for key in self.GOLDEN_DICE_BASE_PROFIT_ODDS)

    def _has_fee_bearing_bet(self):
        return any(amount > 0 and self._wager_fee_rate(self.game_mode, bet) > 0
                   for bet, amount in self.bet_state.bets.items())

    def _bet_is_blocked(self, bet_type):
        return (self.bet_state.conflicting_main_bet(bet_type)
                or (self.game_mode == 'goldendice'
                    and bet_type not in self.GOLDEN_DICE_BASE_PROFIT_ODDS
                    and not self._golden_dice_has_base_bet())
                or (self.game_mode in ('treasure', 'xxx')
                    and self._wager_fee_rate(self.game_mode, bet_type) == 0
                    and not self._has_fee_bearing_bet()))

    def _refund_unqualified_golden_dice_sides(self):
        """Removing the last base wager also refunds its dependent side bets."""
        if self.game_mode == 'goldendice':
            if self._golden_dice_has_base_bet():
                return
            dependent = lambda bet: bet not in self.GOLDEN_DICE_BASE_PROFIT_ODDS
        elif self.game_mode in ('treasure', 'xxx'):
            if self._has_fee_bearing_bet():
                return
            dependent = lambda bet: self._wager_fee_rate(self.game_mode, bet) == 0
        else:
            return
        for bet in list(self.bet_state.bets):
            if dependent(bet):
                self.balance += self.bet_state.clear_area(bet)
                self.pending_bet_visual_amounts.pop((bet,None), None)
        self.undo_stack = [item for item in self.undo_stack
                           if not dependent(item[0])]

    def _update_main_bet_availability(self):
        bet_type = getattr(self, '_hovered_bet_type', None)
        if bet_type is None:
            return
        if not self._bet_is_blocked(bet_type):
            self.canvas.configure(cursor='hand2')
            return
        # Native forbidden cursors differ between Windows and macOS; X_cursor
        # is the portable fallback for Tk installations without either name.
        for cursor in ('no', 'notallowed', 'X_cursor'):
            try:
                self.canvas.configure(cursor=cursor)
                return
            except tk.TclError:
                continue

    # ------------------------------------------------------------- bottom controls
    def draw_bottom_controls(self):
        c = self.canvas
        y0, y1 = 625, 748
        c.create_rectangle(0, y0, 1150, y1, fill=self.BG,
                           outline=self.PANEL_LINE, width=2, tags='controls')
        self.balance_text = c.create_text(10, 665, anchor='w', text='余额: $0.00',
                                          font=('Arial', 18, 'bold'), fill='white',
                                          tags=('dynamic', 'controls'))
        self.total_bet_text = c.create_text(10, 710, anchor='w', text='本局下注: $0.00',
                                            font=('Arial', 18, 'bold'), fill='white',
                                            tags=('dynamic', 'controls'))

        # Compact stacked utility buttons leave the true centre of the 1150px
        # table free for the chip rack.
        self.clear_button = self.create_control_button(
            278, 650, 326, 704, '清除', self.clear_bets, '#7c3b40', font_size=11)

        # Larger chips, with the whole seven-chip rack centred at x=575.
        chip_diameter = self.SELECTOR_CHIP_DIAMETER
        chip_gap = 8
        chip_total_width = len(self.CHIP_SPECS) * chip_diameter + (len(self.CHIP_SPECS) - 1) * chip_gap
        chip_x = (self.WIDTH - chip_total_width) / 2
        chip_y = 643
        for value, color, label in self.CHIP_SPECS:
            tag = f'chip_select_{value}'
            outer = c.create_oval(chip_x, chip_y, chip_x + chip_diameter, chip_y + chip_diameter,
                                  fill='#292522', outline='#6d6259', width=3,
                                  tags=(tag, 'chip_selector', 'controls'))
            inner = c.create_oval(chip_x + 5, chip_y + 5,
                                  chip_x + chip_diameter - 5, chip_y + chip_diameter - 5,
                                  fill=color, outline='#eee3d6', width=2,
                                  tags=(tag, 'chip_selector', 'controls'))
            text_color = self.contrast_text_color(color)
            label_id = c.create_text(chip_x + chip_diameter / 2,
                                     chip_y + chip_diameter / 2, text=label,
                                     font=('Arial', 10, 'bold'), fill=text_color,
                                     tags=(tag, 'chip_selector', 'controls'))
            c.tag_bind(tag, '<Button-1>', lambda _e, v=value: self.select_chip(v))
            self.chip_selector_items[value] = (outer, inner, label_id)
            chip_x += chip_diameter + chip_gap

        self.info_button = self.create_control_button(
            822, 650, 855, 695, '❓', self.show_game_instructions, '#315b72',
            fg='white', font_size=17)
        self.repeat_button = self.create_control_button(
            862, 638, 1000, 708, '重复下注', self.repeat_last_bets, '#5b4938', font_size=11)
        self.deal_button = self.create_control_button(
            1012, 628, 1138, 720, '开始' if self.game_mode == 'goldendice' else '开牌', self.deal_cards, '#d5ad4d',
            fg='#111', font_size=14, subtext='ENTER', subtext_font_size=10)
        c.tag_raise('controls')
        c.tag_raise('chip_selector')
        self.update_control_states()

    def _update_deal_button_label(self):
        button = self.control_buttons.get(getattr(self, 'deal_button', None))
        if not button:
            return
        try:
            self.canvas.itemconfigure(
                button['text'], text='开始' if self.game_mode == 'goldendice' else '开牌')
        except tk.TclError:
            pass

    def show_game_instructions(self):
        parent = self.winfo_toplevel()

        existing = getattr(self, '_instruction_window', None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass

        dialog = tk.Toplevel(parent)
        self._instruction_window = dialog

        mode = self.game_mode
        mode_title = BaccaratEngine.MODE_NAMES.get(mode, mode)
        dialog.title(f'百家乐 · 游戏说明 · {mode_title}')
        dialog.configure(bg='#0a1414')
        dialog.resizable(False, False)
        dialog.transient(parent)

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

        font_name = getattr(self, 'cn_font', 'Microsoft YaHei UI')

        # ================================================================
        # 配色
        # ================================================================
        BG = '#0a1414'
        HEADER = '#0f1c1c'
        SIDEBAR = '#0e1a1a'
        PANEL = '#132020'
        PANEL_2 = '#1a2a2a'
        ROW_ALT = '#162424'
        BORDER = '#3d5a55'

        GOLD = '#f0d48b'
        TEXT = '#eef4f4'
        MUTED = '#a8bdbd'

        BLACK = '#111111'
        WHITE = '#ffffff'

        FONT_SMALL = 14
        FONT_NORMAL = 15
        FONT_MEDIUM = 16
        FONT_LARGE = 18
        FONT_TITLE = 20

        # ================================================================
        # 顶部标题栏
        # ================================================================
        header = tk.Frame(dialog, bg=HEADER, height=82)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f'百家乐  {mode_title}',
            font=(font_name, FONT_TITLE, 'bold'),
            fg=GOLD, bg=HEADER
        ).place(x=24, y=10)

        tk.Label(
            header,
            text='玩法 · 补牌规则 · 下注区 · 限红 · 赔率表',
            font=(font_name, FONT_SMALL),
            fg=MUTED, bg=HEADER
        ).place(x=25, y=48)

        close_btn = tk.Button(
            header,
            text='关闭  ESC',
            command=lambda: self._close_instruction_window(),
            font=(font_name, FONT_SMALL, 'bold'),
            bg='#2a3330',
            fg=TEXT,
            activebackground='#3a4644',
            activeforeground=WHITE,
            relief=tk.FLAT,
            bd=0,
            cursor='hand2'
        )
        close_btn.place(x=850, y=20, width=120, height=42)

        tk.Frame(dialog, bg=GOLD, height=3).pack(fill=tk.X, side=tk.TOP)

        # ================================================================
        # 主体：左 sidebar + 右 content
        # ================================================================
        body = tk.Frame(dialog, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        sidebar_w = 220
        sidebar = tk.Frame(body, bg=SIDEBAR, width=sidebar_w)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Frame(body, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(
            sidebar,
            text='主题',
            font=(font_name, FONT_SMALL, 'bold'),
            fg=GOLD, bg=SIDEBAR, anchor='w'
        ).pack(fill=tk.X, padx=16, pady=(18, 10))

        right_wrap = tk.Frame(body, bg=BG)
        right_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_wrap.grid_rowconfigure(0, weight=1)
        right_wrap.grid_columnconfigure(0, weight=1)
        right_wrap.grid_columnconfigure(1, weight=0)

        content_canvas = tk.Canvas(
            right_wrap,
            bg=BG,
            highlightthickness=0,
            bd=0,
            yscrollincrement=40
        )

        content_scrollbar = tk.Scrollbar(
            right_wrap,
            orient=tk.VERTICAL,
            command=content_canvas.yview,
            bg='#1f2a29',
            troughcolor='#0d1515',
            activebackground=GOLD,
            relief=tk.FLAT,
            bd=0,
            width=12
        )

        content_canvas.configure(yscrollcommand=content_scrollbar.set)

        content_canvas.grid(row=0, column=0, sticky='nsew',
                            padx=(0, 4), pady=(6, 6))
        content_scrollbar.grid(row=0, column=1, sticky='ns',
                               padx=(0, 8), pady=(6, 6))

        content = tk.Frame(content_canvas, bg=BG)
        content_window = content_canvas.create_window(
            (0, 0), window=content, anchor='nw')

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

        def _on_mousewheel_linux_up(_event):
            content_canvas.yview_scroll(-1, 'units')
            return 'break'

        def _on_mousewheel_linux_down(_event):
            content_canvas.yview_scroll(1, 'units')
            return 'break'

        dialog.bind('<MouseWheel>', _on_mousewheel)
        dialog.bind('<Button-4>', _on_mousewheel_linux_up)
        dialog.bind('<Button-5>', _on_mousewheel_linux_down)

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
            block.pack(fill=tk.X, padx=24, pady=(14, 0))

            tk.Label(
                block, text=text,
                font=(font_name, FONT_LARGE, 'bold'),
                fg=GOLD, bg=BG, anchor='w'
            ).pack(side=tk.LEFT)

            if subtitle:
                tk.Label(
                    block, text=subtitle,
                    font=(font_name, FONT_SMALL),
                    fg=MUTED, bg=BG, anchor='e'
                ).pack(side=tk.RIGHT)

            tk.Frame(content, bg=BORDER, height=1).pack(
                fill=tk.X, padx=24, pady=(10, 16))

        def make_card(title=None, subtitle=None, pady=(0, 16)):
            card = tk.Frame(
                content, bg=PANEL,
                highlightbackground=BORDER, highlightcolor=BORDER,
                highlightthickness=1, bd=0
            )
            card.pack(fill=tk.X, padx=24, pady=pady)

            if title:
                head = tk.Frame(card, bg=PANEL)
                head.pack(fill=tk.X, padx=22, pady=(16, 10))

                tk.Label(
                    head, text=title,
                    font=(font_name, FONT_MEDIUM, 'bold'),
                    fg=GOLD, bg=PANEL, anchor='w'
                ).pack(side=tk.LEFT)

                if subtitle:
                    tk.Label(
                        head, text=subtitle,
                        font=(font_name, FONT_SMALL),
                        fg=MUTED, bg=PANEL, anchor='e'
                    ).pack(side=tk.RIGHT)

            return card

        def add_rule(parent_frame, title, body, accent=GOLD):
            row_wrap = tk.Frame(parent_frame, bg=PANEL)
            row_wrap.pack(fill=tk.X, padx=22, pady=(0, 14))

            row = tk.Frame(row_wrap, bg=PANEL)
            row.pack(fill=tk.X)

            tk.Frame(row, bg=accent, width=4).pack(
                side=tk.LEFT, fill=tk.Y, padx=(0, 16))

            text_box = tk.Frame(row, bg=PANEL)
            text_box.pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Label(
                text_box, text=title,
                font=(font_name, FONT_MEDIUM, 'bold'),
                fg=TEXT, bg=PANEL, anchor='w', justify=tk.LEFT
            ).pack(fill=tk.X)

            tk.Label(
                text_box, text=body,
                font=(font_name, FONT_SMALL),
                fg=MUTED, bg=PANEL, anchor='w',
                justify=tk.LEFT, pady=6
            ).pack(fill=tk.X)

        def table_block(parent_frame, title, rows):
            block = tk.Frame(
                parent_frame, bg=PANEL_2,
                highlightbackground='#2b3d3d',
                highlightthickness=1, bd=0
            )

            tk.Label(
                block, text=title,
                font=(font_name, FONT_SMALL, 'bold'),
                fg=BLACK, bg=GOLD, anchor='w',
                padx=16, pady=8
            ).pack(fill=tk.X)

            grid = tk.Frame(block, bg=PANEL_2)
            grid.pack(fill=tk.BOTH, expand=True)
            grid.grid_columnconfigure(0, weight=1)
            grid.grid_columnconfigure(1, minsize=160)

            for i, (condition, payout) in enumerate(rows):
                row_bg = ROW_ALT if i % 2 == 0 else PANEL_2

                tk.Label(
                    grid, text=condition,
                    font=(font_name, FONT_SMALL),
                    fg=TEXT, bg=row_bg,
                    anchor='w', justify=tk.LEFT,
                    padx=18, pady=10
                ).grid(row=i, column=0, sticky='nsew',
                       padx=(0, 1), pady=(0, 1))

                tk.Label(
                    grid, text=payout,
                    font=(font_name, FONT_SMALL, 'bold'),
                    fg=GOLD, bg=row_bg,
                    anchor='center', padx=10, pady=10
                ).grid(row=i, column=1, sticky='nsew', pady=(0, 1))

            return block

        # ================================================================
        # 模式相关的数据准备
        # ================================================================
        # 主注赔率（含特殊规则说明）
        main_rows_by_mode = {
            'classic': [
                ('闲家获胜', '1:1'),
                ('庄家获胜', '0.95:1（抽水5%）'),
                ('和局', '8:1'),
                ('和局 · 闲/庄主注', '退还本金'),
            ],
            'tiger': [
                ('闲家获胜', '1:1'),
                ('庄家获胜 · 非6点', '1:1'),
                ('庄家以6点获胜', '0.5:1（半赔）'),
                ('和局', '8:1'),
                ('和局 · 闲/庄主注', '退还本金'),
            ],
            'ez': [
                ('闲家获胜', '1:1'),
                ('庄家获胜 · 非3张7点', '1:1'),
                ('庄家3张牌7点获胜 · 仅庄主注', '退还本金'),
                ('庄家3张牌7点获胜 · 闲注/和注', '输注'),
                ('和局', '8:1'),
                ('和局 · 闲/庄主注', '退还本金'),
            ],
            '2to1': [
                ('闲家获胜', '1:1'),
                ('庄家获胜', '1:1'),
                ('闲/庄以前两张天牌8或9点获胜', '当前基础盈利赔率 × 2'),
                ('和局', '8:1（主注视为输）'),
            ],
            'lucky7': [
                ('闲家获胜', '1:1'),
                ('庄家获胜 · 非6点', '1:1'),
                ('庄家以6点获胜', '0.5:1（半赔）'),
                ('和局', '8:1'),
                ('和局 · 闲/庄主注', '退还本金'),
            ],
            'monkey': [
                ('闲家获胜', '1:1'),
                ('庄家获胜', '1:1'),
                ('和局', '8:1'),
                ('和局 · 闲/庄主注', '退还本金'),
            ],
            'goldendice': [
                ('闲家获胜', '1:1'),
                ('庄家获胜', '0.95:1'),
                ('和局', '5:1'),
                ('和局 · 闲/庄主注', '退还本金'),
            ],
            'treasure': [
                ('闲家获胜', '1:1'),
                ('庄家获胜', '0.95:1'),
                ('和局', '5:1'),
                ('和局 · 闲/庄主注', '退还本金'),
            ],
            'xxx': [
                ('闲家获胜', '1:1'),
                ('庄家获胜', '0.97:1'),
                ('和局', '2.85:1'),
                ('和局 · 闲/庄主注', '退还本金'),
            ],
        }

        main_rows_by_mode['one_deck'] = [
            ('闲家获胜', '1:1'),
            ('庄家获胜', '按当前庄家拨片'),
            ('和局', '9:1'),
            ('和局 · 闲/庄主注', '退还本金'),
        ]

        for fixed_mode in BaccaratEngine.ALWAYS_MODES:
            fixed_odds = BaccaratEngine.ODDS_TEXT[fixed_mode]
            main_rows_by_mode[fixed_mode] = [
                ('闲家获胜', fixed_odds['Player']), ('庄家获胜', fixed_odds['Banker']),
                ('和局', fixed_odds['Tie']), ('和局 · 闲/庄主注', '退还本金')]

        # Describe the selected Banker rule rather than the mode's old default.
        selected_rule = self._current_banker_rule(mode)
        banker_rows = {
            'classic': [('庄家获胜', '0.95:1')],
            'no_commission': [('庄家获胜 · 非6点', '1:1'),
                              ('庄家以任何牌数6点获胜', '0.5:1')],
            'ez': [('庄家获胜 · 非3张7点', '1:1'),
                   ('庄家3张牌7点获胜 · 仅庄主注', '退还本金'),
                   ('庄家3张牌7点获胜 · 闲注/和注', '输注')],
        }[selected_rule]
        if mode in BaccaratEngine.ALWAYS_MODES:
            banker_rows = [('庄家获胜', BaccaratEngine.ODDS_TEXT[mode]['Banker'])]
        rows = [row for row in main_rows_by_mode[mode] if not row[0].startswith('庄家')]
        main_rows_by_mode[mode] = rows[:1] + banker_rows + rows[1:]

        # 边注赔率表（每个模式可能有不同数量的边注）
        # 边注赔率表（按分组上下堆叠；同类型边注合并到同一表格）
        side_groups_by_mode = {
            'classic': [
                ('对子', [
                    ('闲家对子', '11:1'),
                    ('庄家对子', '11:1'),
                    ('任意对子', '5:1'),
                    ('完美对子 · 单方', '25:1'),
                    ('完美对子 · 双方', '250:1'),
                ]),
                ('大小 · 本局总牌数', [
                    ('小 · 共4张牌结束', '3:2'),
                    ('大 · 共5或6张牌结束', '0.54:1'),
                ]),
                ('单双 · 闲庄点数合计取个位', [
                    ('单 · 个位为奇数', '1:1'),
                    ('双 · 个位为非零偶数', '1:1'),
                    ('个位为0（合计0或10点）', '单、双均输'),
                ]),
                ('龙宝', [
                    ('自然点赢', '1:1'),
                    ('点数差 4 点', '1:1'),
                    ('点数差 5 点', '2:1'),
                    ('点数差 6 点', '4:1'),
                    ('点数差 7 点', '6:1'),
                    ('点数差 8 点', '10:1'),
                    ('点数差 9 点', '30:1'),
                    ('自然点和', '退还本金'),
                ]),
            ],
            'tiger': [
                ('老虎系列', [
                    ('小老虎 · 庄2张牌6点获胜', '22:1'),
                    ('大老虎 · 庄3张牌6点获胜', '50:1'),
                    ('老虎和 · 和局且庄6点', '35:1'),
                    ('老虎 · 庄2张牌6点获胜', '12:1'),
                    ('老虎 · 庄3张牌6点获胜', '20:1'),
                ]),
                ('虎对子', [
                    ('单方对子', '4:1'),
                    ('双方不同对子', '20:1'),
                    ('双方相同对子', '100:1'),
                ]),
                ('闲家龙宝 / 庄家龙宝', [
                    ('自然点赢 / 点差4点', '1:1'),
                    ('点差5点 / 6点 / 7点', '2:1 / 4:1 / 6:1'),
                    ('点差8点 / 9点', '10:1 / 30:1'),
                    ('自然点和', '退还本金'),
                ]),
            ],
            'ez': [
                ('对子', [
                    ('闲家对子', '11:1'),
                    ('庄家对子', '11:1'),
                ]),
                ('Five Treasures · 五宝边注', [
                    ('Fortune 7 · 庄3张牌7点获胜', '40:1'),
                    ('Golden 8 · 闲3张牌8点获胜', '25:1'),
                    ('Heavenly 9 · 恰有一方3张牌9点', '10:1'),
                    ('Heavenly 9 · 双方各3张牌9点', '75:1'),
                    ('Blazing 7s · 双方各2张牌7点', '60:1'),
                    ('Blazing 7s · 双方各3张牌7点', '125:1'),
                    ('Cover All · 上述四种任一种命中', '6:1'),
                ]),
                ('闲家龙宝 / 庄家龙宝', [
                    ('自然点赢', '1:1'),
                    ('点数差 4 点', '1:1'),
                    ('点数差 5 点', '2:1'),
                    ('点数差 6 点', '4:1'),
                    ('点数差 7 点', '6:1'),
                    ('点数差 8 点', '10:1'),
                    ('点数差 9 点', '30:1'),
                    ('自然点和', '退还本金'),
                ]),
            ],
            '2to1': [
                ('对子', [
                    ('闲家对子', '11:1'),
                    ('庄家对子', '11:1'),
                    ('任意对子', '5:1'),
                ]),
                ('大小 · 本局总牌数', [
                    ('小 · 共4张牌结束', '3:2'),
                    ('大 · 共5或6张牌结束', '0.54:1'),
                ]),
                ('点数组合 · 闲庄任一方获胜', [
                    ('9/7 · 3张9点胜3张7点', '200:1'),
                    ('9/1 · 3张9点胜3张1点', '150:1'),
                    ('N9/N7 · 2张9点胜2张7点', '50:1'),
                    ('8/6 · 8点胜6点，不限牌数', '25:1'),
                ]),
                ('龙宝', [
                    ('自然点赢', '1:1'),
                    ('点数差 4 点', '1:1'),
                    ('点数差 5 点', '2:1'),
                    ('点数差 6 点', '4:1'),
                    ('点数差 7 点', '6:1'),
                    ('点数差 8 点', '10:1'),
                    ('点数差 9 点', '30:1'),
                    ('自然点和', '退还本金'),
                ]),
            ],
            'lucky7': [
                ('幸运6', [
                    ('小幸运6 · 庄2张牌6点获胜', '22:1'),
                    ('大幸运6 · 庄3张牌6点获胜', '50:1'),
                    ('幸运6 · 庄2张牌6点', '12:1'),
                    ('幸运6 · 庄3张牌6点', '20:1'),
                ]),
                ('幸运7', [
                    ('幸运7 · 闲2张牌7点获胜', '6:1'),
                    ('幸运7 · 闲3张牌7点获胜', '15:1'),
                ]),
                ('超级幸运7 · 闲7点且庄6点', [
                    ('总牌数 4 张', '30:1'),
                    ('总牌数 5 张', '40:1'),
                    ('总牌数 6 张', '100:1#'),
                ]),
                ('闲家龙宝 / 庄家龙宝', [
                    ('自然点赢 / 点差4点', '1:1'),
                    ('点差5点 / 6点 / 7点', '2:1 / 4:1 / 6:1'),
                    ('点差8点 / 9点', '10:1 / 30:1'),
                    ('自然点和', '退还本金'),
                ]),
                ('对子', [
                    ('闲家对子', '11:1'),
                    ('庄家对子', '11:1'),
                ]),
            ],
            'monkey': [
                ('猴子边注', [
                    ('全猴 · 闲庄前4张全为J/Q/K', '50:1'),
                    ('无猴 · 闲庄前4张均非J/Q/K', '1:1'),
                    ('猴老六', '12:1'),
                    ('猴老六和', '150:1'),
                    ('猴子六仙', '5000:1'),
                    ('猴7点', '40:1'),
                ]),
                ('幸运猴子', [
                    ('双方都补 · 一方是猴', '1:1'),
                    ('仅闲补 · 补牌是猴', '3:1'),
                    ('仅庄补 · 补牌是猴', '8:1'),
                    ('双方都补 · 双方都是猴', '10:1'),
                    ('双方都是猴 · 点数相同', '25:1'),
                    ('双方猴子牌完全相同', '75:1'),
                ]),
                ('闲家龙宝 / 庄家龙宝', [
                    ('自然点赢 / 点差4点', '1:1'),
                    ('点差5点 / 6点 / 7点', '2:1 / 4:1 / 6:1'),
                    ('点差8点 / 9点', '10:1 / 30:1'),
                    ('自然点和', '退还本金'),
                ]),
                ('对子', [
                    ('闲家对子', '11:1'),
                    ('庄家对子', '11:1'),
                ]),
            ],
            'goldendice': [
                ('闲家龙宝 / 庄家龙宝 · 免手续费、不加倍', [
                    ('自然点赢 / 点差4点', '1:1'),
                    ('点差5点 / 6点 / 7点', '2:1 / 4:1 / 6:1'),
                    ('点差8点 / 9点', '10:1 / 30:1'),
                    ('自然点和', '退还本金'),
                ]),
                ('对子', [
                    ('闲家对子', '10:1'),
                    ('庄家对子', '10:1'),
                ]),
                ('超级骰子', [
                    ('骰9 + 双方对子 + 和局', '2600:1'),
                    ('骰8 + 双方对子 + 和局', '2100:1'),
                    ('骰9 + 双方对子', '325:1'),
                    ('骰8 + 双方对子', '260:1'),
                    ('骰9 + 任一方对子', '11:1'),
                    ('骰8 + 任一方对子', '9:1'),
                ]),
                ('骰子点数 · 单一下注、免手续费、不加倍', [
                    (f'骰{total} · 闲庄最大{total % 10}点' if total != 10
                     else '骰10 · 双方0点和局', f'{format_two_decimals(odds)}:1')
                    for total, odds in BaccaratEngine.DICE_POINTS_PROFIT_ODDS.items()
                ] + [('骰12', '必输'), ('和局', '按双方相同点数判定')]),
            ],
            'treasure': [
                ('对子', [
                    ('闲家对子', '9:1'),
                    ('庄家对子', '9:1'),
                ]),
                ('有 / 没黄金扑克 · 免手续费、不加倍', [
                    ('闲庄全部牌中至少 1 张黄金牌', '3:2'),
                    ('闲庄全部牌中没有黄金牌', '0.55:1'),
                ]),
                ('闲家 / 庄家龙宝 · 免手续费、不加倍', [
                    ('自然8/9点获胜', '1:1'),
                    ('自然点和局', '退还本金'),
                    ('非自然点赢4/5/6/7/8/9点', '1/2/4/6/10/30:1'),
                ]),
                ('黄金猎手', [
                    ('实际发出 2 张黄金牌', '3:1'),
                    ('实际发出 3 张黄金牌', '25:1'),
                    ('实际发出 4 张黄金牌', '155:1'),
                    ('实际发出 5 张黄金牌', '3150:1'),
                    ('实际发出 6 张黄金牌', '51000:1'),
                ]),
            ],
            'xxx': [
                ('对子', [
                    ('闲家对子', '8:1'),
                    ('庄家对子', '8:1'),
                ]),
                ('系统选出的黄金牌面数量 · 免手续费、不加倍', [
                    ('系统选出4或5种黄金牌面', '2.15:1'),
                    ('系统选出7或8种黄金牌面', '5.25:1'),
                    ('系统选出6种黄金牌面', '两项均输'),
                ]),
                ('闲家 / 庄家龙宝 · 免手续费、不加倍', [
                    ('自然8/9点获胜', '1:1'),
                    ('自然点和局', '退还本金'),
                    ('非自然点赢4/5/6/7/8/9点', '1/2/4/6/10/30:1'),
                ]),
                ('黄金对决', [
                    ('双方各有黄金牌', '15:1'),
                    ('双方各有黄金牌且和局', '35:1'),
                    ('任一方有黄金对子', '100:1'),
                    ('双方都有黄金对子', '3000:1'),
                ]),
            ],
        }

        side_groups_by_mode['one_deck'] = [
            ('对子', [('闲家对子', '15:1'), ('庄家对子', '15:1'), ('任意对子', '7:1')]),
            ('大小 · 本局总牌数', [
                ('小 · 共4或5张牌结束', '1:2（下注2，净赢1，返还3）'),
                ('大 · 共6张牌结束', '1.6:1'),
            ]),
            ('和局点数 · 双方最终点数相同且命中所选点数', [
                (f'和局{point}点', f'{odds}:1')
                for point, odds in BaccaratEngine.ONE_DECK_TIE_PROFIT_ODDS.items()
            ]),
            ('闲家龙宝 / 庄家龙宝', [
                ('自然点赢 / 点差4点', '1:1'),
                ('点差5点 / 6点 / 7点', '2:1 / 4:1 / 6:1'),
                ('点差8点 / 9点', '10:1 / 30:1'),
                ('自然点和', '退还本金'),
            ]),
        ]

        for fixed_mode in BaccaratEngine.ALWAYS_MODES:
            fixed_odds = BaccaratEngine.ODDS_TEXT[fixed_mode]
            side_groups_by_mode[fixed_mode] = [
                ('对子', [('闲家对子', '11:1'), ('庄家对子', '10:1'), ('任意对子', '5.5:1')]),
                ('大小 · 本局总牌数', [('小 · 共4张牌结束', fixed_odds['Small']),
                                      ('大 · 共5或6张牌结束', fixed_odds['Big'])]),
                ('和局点数', [(f'和局{point}点', f'{price}:1') for point, price in
                             BaccaratEngine.ALWAYS_TIE_PROFIT_ODDS[fixed_mode].items()]),
                ('固定模式边注', [
                    (BaccaratEngine.display_name('Dragon P', fixed_mode), fixed_odds['Dragon P']),
                    (BaccaratEngine.display_name('Dragon B', fixed_mode), fixed_odds['Dragon B']),
                ])]

        # 各模式的特殊说明（重要提示页）
        notes_by_mode = {
            'classic': (
                ('庄家佣金', '选择经典档时，庄家获胜按0.95:1结算，相当于收取5%佣金。'),
                ('大小', '本局双方共4张牌结束时，小按3:2赔付；共5或6张牌结束时，大按0.54:1赔付。'),
                ('单双', '将闲庄双方最终点数相加，只取个位数；1/3/5/7/9为单，2/4/6/8为双，均赔1:1；个位为0（合计0或10）时，单、双均输。'),
                ('龙宝判定', '龙宝按赢方与输方的点数差赔付；双方均为自然点且和局时退还本金。'),
                ('完美对子', '只检查前两张牌；单方同点同花 25:1，双方均同点同花 250:1。'),
                ('对子结算', '对子只看前两张牌是否点数相同，与花色无关。'),
                ('经典版面', '左右为闲庄龙宝，上方为小、大、单、双，中间为任意对子和完美对子；本模式没有覆盖全部下注。'),
            ),
            'tiger': (
                ('庄家6点半赔', '庄家以6点获胜时，主注按 0.5:1 赔付。'),
                ('小/大老虎', '小老虎：庄2张牌6点获胜；大老虎：庄3张牌6点获胜。'),
                ('圆圈老虎', '中央圆圈为独立老虎边注：庄2张6点获胜12:1，庄3张6点获胜20:1。'),
                ('老虎图标', '小/大老虎命中时，从闪烁第0秒开始由上往下连续变为白底红图案；图标不交替闪烁。'),
                ('闲家龙宝 / 庄家龙宝', '两侧为可下注的龙宝边注，按自然点及点差4–9结算，自然点和局退本。'),
                ('老虎和', '和局且庄家点数为6点时触发。'),
                ('虎对子', '按双方对子情况分三档：单方4:1，双方不同对子20:1，双方相同对子100:1。'),
            ),
            'ez': (
                ('EZ免佣', '选择EZ档时，庄家3张7点获胜仅庄主注退本，闲注和和注输；Fortune 7照付40:1。'),
                ('Fortune 7 / Golden 8', '分别要求庄3张7点获胜、闲3张8点获胜；和局不触发。'),
                ('Heavenly 9', '恰有一方3张9点付10:1；双方各3张9点付75:1。只按最高档赔付一次。'),
                ('Blazing 7s', '双方必须同为2张7点（60:1）或同为3张7点（125:1）；一方2张、另一方3张不中奖。'),
                ('Cover All', '可单独下注；四种五宝边注任一种命中即付6:1，一局只付一次。对子、龙宝或普通和局不触发。'),
                ('闲家龙宝 / 庄家龙宝', '左右两侧独立下注；沿用原有自然点及点差4–9的1–30:1结算，自然点和退本。'),
                ('点数与本金', '3张7/8/9点指百家乐合计点数，不是三张相同牌。所有赔率为净赢赔率，本金另退。'),
            ),
            '2to1': (
                ('天牌8/9点加倍', '闲家或庄家翻开两张牌为8或9点时，该方立即显示左上角X2倍数带及加倍赔率，不论胜负或和局；双方都是自然点时双方均显示。闲家显示2:1，庄家经典档显示1.9:1，免佣或EZ档显示2:1并保留括号说明。仅获胜主注按加倍赔率派彩，结算后恢复原赔率并移除带子。'),
                ('和局主注输', '本模式下，闲家或庄家下注在和局时视为输注，不退还本金。'),
                ('9/7与9/1', '双方均须为3张牌；任一方9点打败另一方7点赔200:1，打败1点赔150:1。'),
                ('N9/N7', '双方均为2张牌，任一方自然9点打败另一方自然7点，赔50:1。'),
                ('8/6', '任一方8点打败另一方6点，双方牌数不限，赔25:1。'),
                ('大小', '沿用经典规则：本局共4张牌，小赔3:2；共5或6张牌，大赔0.54:1。'),
                ('对子与龙宝', '保留闲对、庄对、任意对子及闲庄龙宝；本模式没有单、双、完美对子或覆盖全部下注。'),
            ),
            'lucky7': (
                ('庄家6点半赔', '庄家以6点获胜时，主注按 0.5:1 赔付。'),
                ('小幸运6 / 大幸运6', '分别为庄家2张牌6点获胜22:1、庄家3张牌6点获胜50:1。'),
                ('中央幸运6', '独立下注：庄家2张牌6点获胜12:1、3张牌6点获胜20:1；命中后红底白色6从中心放大。'),
                ('幸运7 / 超级幸运7', '幸运7要求闲家7点获胜；超级幸运7还要求庄家6点结束，双方总牌数4/5/6张分别30/40/100:1。'),
                ('龙宝', '左右两侧独立下注，自然点及点差4–9照原龙宝规则结算，自然点和退本。'),
                ('超级7大奖', '下注超级7 且金额 ≥ 1000 时自动参与累进大奖。'),
                ('头奖条件', '闲家3张方片♢共7点 + 庄家3张黑桃♠共6点，中 100% 大奖。'),
                ('次奖条件', '闲家3张红色7点 + 庄家3张黑色6点，赢得奖池3%。'),
            ),
            'monkey': (
                ('猴子牌定义', 'J、Q、K 均为猴子牌，不分花色。'),
                ('全猴 / 无猴', '只检查闲庄各自前两张、共4张牌。全为J/Q/K时，全猴赔50:1；全都不是J/Q/K时，无猴赔1:1；混合开局两项皆输，补牌不影响判定。10属于非猴子牌。'),
                ('猴老六', '闲家补牌不是猴子牌，且庄家补牌是猴子牌时触发。'),
                ('猴老六和', '满足猴老六条件且本局为和局时触发。'),
                ('猴子六仙', '双方6张牌（闲3 + 庄3）都是猴子牌时触发。'),
                ('猴7点', '庄家以3张牌组成7点并获胜时触发。'),
                ('幸运猴子', '按双方补牌是否为猴子牌分级，最高 75:1。'),
                ('闲庄龙宝', '两侧独立下注，按自然点及点差4–9赔1–30:1；自然点和局退本。'),
                ('猴子版面', '上排为全猴、猴老六、猴老六和、无猴；下排为猴7点、猴子六仙、幸运猴子；底排为闲对、闲家、和、庄家、庄对，没有中央圆圈下注。'),
            ),
            'goldendice': (
                ('骰子激活', '按「开始」后，骰盅右侧的手续费筹码化为金光注入骰盅，再摇骰；两骰总和为8或9才使用加强倍数。'),
                ('重骰', '持续确认两骰已静止后才判定。8°以内的轻微倾斜及对应接触误差不重骰，单纯画面投影重叠也不重骰；超过容差或明显架空、重叠、超出底盘才重骰。重骰不发牌、不重复收手续费，点数读取朝上的一面。'),
                ('底排先下注', '先在闲对、闲家、和、庄家、庄对任一区域下注，才可下注龙宝、超级骰子和骰子点数；清除最后一笔底排下注时，上方边注一并退还。'),
                ('倍率范围', '倍率只会从 2X / 3X / 5X / 10X / 20X / 50X / 100X 中按权重随机。每项随机确定后先显示左上角倍数带，骰子结果出来后仅8/9点保留生效，结算后移除。'),
                ('倍率作用', '只放大闲、庄、和、闲对、庄对的盈利赔率，不改变本金；龙宝和两个骰子边注不加倍。'),
                ('手续费', '仅闲、庄、和、闲对、庄对收取20%；两侧龙宝、超级骰子、骰子点数均免手续费。'),
                ('超级骰子', '六档，最高档优先，只赔一档；免20%手续费；最高下注 5000。'),
                ('骰子点数', '只下一个区域，闲庄最终最大点数须等于骰子总和。10只中双方0点和局，11代表1点，12必输。最高下注5000。'),
                ('固定赔率', '下注区固定显示2.9-170:1，各骰点按边注赔率表结算；不随每局骰点更改显示赔率。'),
            ),
            'treasure': (
                ('黄金扑克', '每局从52张牌面中随机抽5种不重复的黄金牌面。'),
                ('下注条件', '免手续费选项须先下注任意含手续费选项；取消最后一笔含手续费下注时，免手续费下注一并退回。'),
                ('每张黄金牌倍率', '每张黄金牌独立随机获得 2X / 3X / 5X / 8X 之一。'),
                ('倍率作用', '只放大闲、庄、和及对子的盈利赔率；左上角显示倍数带，赔率同步更新。'),
                ('开牌动画', '先以普通牌完全翻开，再从对应小黄金牌中心飞入光点；注入后同步变金与落下倍率。'),
                ('有 / 没黄金扑克', '统计闲庄全部实际发出的牌，任意1张命中即有，否则为没；各上限30K、免手续费、不加倍。'),
                ('同一牌面重复', '8副牌中同一牌面可能出现多张，每张实际发出的黄金牌都乘一次倍数。'),
                ('手续费', '仅闲、庄、和、闲对、庄对收取20%；龙宝、黄金猎手及有/没黄金扑克均免手续费。'),
                ('黄金猎手', '免20%手续费，最高下注 5000；按实际发出的黄金牌张数结算。'),
            ),
            'xxx': (
                ('黄金牌数量', '每局按固定概率随机抽取 4–8 张互不重复的黄金牌面。'),
                ('八个牌位', '预设上四下四8个虚线框；4/5/6/7/8张分别按2+2、2+3、2+4、3+4、4+4排列。全部牌加载完后，将三张行居中并移除多余的右侧框。'),
                ('下注条件', '免手续费选项须先下注任意含手续费选项；取消最后一笔含手续费下注时，免手续费下注一并退回。'),
                ('数量边注', '只按系统选出的黄金牌面数量结算，与闲庄实际发牌及命中张数无关；4–5张赔2.15:1，7–8张赔5.25:1，6张两项均输。各上限30K、免手续费、不加倍。'),
                ('每张倍率', '每张黄金牌独立随机获得 2X / 3X / 4X / 5X / 8X / 10X。'),
                ('倍率作用', '只放大获胜投注的盈利赔率；下注区显示与实际结算统一保留2位小数。'),
                ('手续费', '仅闲、庄、和、闲对、庄对收取50%；龙宝、黄金对决及两个数量边注均免手续费。'),
                ('黄金对决', '四档只赔最高档；黄金对子指起手两张同点数且都是黄金牌；免手续费。'),
            ),
        }

        notes_by_mode['one_deck'] = (
            ('单副52张', '每局重新洗一副完整52张牌，无鬼牌，不沿用上一局余牌，也不切牌或烧牌。'),
            ('主注', '闲家1:1、和局9:1；和局时闲庄主注退本。天牌按普通单副版主注赔率结算。'),
            ('庄家规则', '经典、免佣、EZ三档均可选择，默认经典；各档条件以庄家赔付拨片说明为准。'),
            ('对子与大小', '闲对、庄对15:1，任意对子7:1；小为4或5张、赔1:2，大为6张、赔1.6:1。'),
            ('和局点数', '上排0–9点分别下注，仅双方最终同为所选点数时中奖，采用原单副版赔率。'),
            ('独立历史', '单副版与普通模式分别记录；大路、衍生路、下局指示和数据页使用最新500局记录。'),
            ('Marker Road统计', '12列×6行，格子大小与其他模式相同；写入第73局时删除最旧6局，再写入新局，剩67局。底部总局、闲、庄、和及对子数量均统计当前图内记录。'),
        )

        for fixed_mode in BaccaratEngine.ALWAYS_MODES:
            notes_by_mode[fixed_mode] = (
                ('固定庄家首张', f'庄家首张为固定黑桃{fixed_mode[-1]}，其余牌由CSM发出，结算后归还。'),
                ('固定选择器', '在固定6、固定7、固定8、固定9之间切换；不使用佣金拨片。'),
                ('对子与大小', '任意对子5.5:1；小为共4张，大为共5或6张，赔率以当前下注区为准。'),
                (BaccaratEngine.display_name('Dragon P', fixed_mode),
                 f'庄家最终为{fixed_mode[-1]}点且获胜时中奖，牌数不限；赔{BaccaratEngine.ODDS_TEXT[fixed_mode]["Dragon P"]}。和局或庄家未获胜均输。'),
                (BaccaratEngine.display_name('Dragon B', fixed_mode),
                 f'庄家按补牌规则补第三张即中奖，不论输赢或和局；赔{BaccaratEngine.ODDS_TEXT[fixed_mode]["Dragon B"]}。未补第三张则输。'),
                ('两侧边注', '两项独立结算，可以同时中奖；盈利赔率不含本金，本金另退。'),
                ('独立路单', '每个固定点数独立记录：大路、衍生路和数据页使用最近500局；Marker Road独立保留72格并按6局滚动。'),
            )

        selector_note = (
            '经典：庄家任何获胜均赔0.95:1；免佣：庄家任何6点获胜赔0.5:1，其余赔1:1；'
            'EZ：庄家3张7点获胜退本，其余赔1:1。'
            '经典、黄金骰、聚宝盆、XXX锁定经典，简单锁定EZ。'
            '老虎和幸运7仅可选经典、免佣，不能选EZ；猴子、1赔2和单副版三档均可选择。'
            '本次加载首次进入老虎、幸运7时预设免佣，猴子预设EZ，1赔2和单副版预设经典；后续各模式分别记住本次选择。'
        )
        if mode not in BaccaratEngine.ALWAYS_MODES:
            notes_by_mode[mode] = (('庄家赔付拨片', selector_note),) + tuple(
                row for row in notes_by_mode[mode] if row[0] not in ('庄家6点半赔',))

        # ================================================================
        # 各主题页面
        # ================================================================
        def page_rules():
            section_title('玩法与补牌规则', 'A=1，10/J/Q/K=0；只取总点数个位')

            intro_card = make_card(title='基本流程')
            if mode == 'one_deck':
                add_rule(intro_card, '单副52张', '每局重新洗一副完整52张牌，无鬼牌；无需切牌、烧牌。')
            add_rule(
                intro_card, '发牌顺序',
                '闲、庄各发 2 张牌；若一方前两张为 8 或 9 点（天牌），双方都不补牌；\n'
                '否则按补牌规则决定闲、庄是否补第 3 张，最后比较点数大小。'
            )
            add_rule(
                intro_card, '点数计算',
                'A = 1 点；2–9 按牌面；10 / J / Q / K = 0 点；\n'
                '两张或三张牌点数相加后，只取个位数（如 7+8=15 → 5 点）。'
            )

            # ---------- 闲家补牌 ----------
            player_card = make_card(title='闲家补牌规则')
            player_table = table_block(player_card, '闲家初始点数 · 补牌', [
                ('0 – 5 点', '补一张牌'),
                ('6 – 7 点', '不补牌（停牌）'),
                ('8 – 9 点', '天牌 · 双方均不补牌'),
            ])
            player_table.pack(fill=tk.X, padx=16, pady=(6, 16))

            # ---------- 庄家补牌（闲家未补牌） ----------
            banker_no_draw_card = make_card(title='庄家补牌 · 闲家未补牌')
            banker_no_draw_table = table_block(banker_no_draw_card, '庄家初始点数 · 补牌', [
                ('0 – 5 点', '补一张牌'),
                ('6 – 7 点', '不补牌（停牌）'),
                ('8 – 9 点', '天牌 · 不补牌'),
            ])
            banker_no_draw_table.pack(fill=tk.X, padx=16, pady=(6, 16))

            # ---------- 庄家补牌（闲家已补牌） ----------
            banker_draw_card = make_card(title='庄家补牌 · 闲家已补牌')
            banker_draw_table = table_block(
                banker_draw_card,
                '庄家点数 · 闲家第三张牌条件 · 补牌',
                [
                    ('0 – 2 点', '任何牌 → 补牌'),
                    ('3 点', '闲家第三张 ≠ 8 → 补牌'),
                    ('4 点', '闲家第三张 2 – 7 → 补牌'),
                    ('5 点', '闲家第三张 4 – 7 → 补牌'),
                    ('6 点', '闲家第三张 6 – 7 → 补牌'),
                    ('7 点', '任何牌 → 不补牌（停牌）'),
                ])
            banker_draw_table.pack(fill=tk.X, padx=16, pady=(6, 16))

            note_card = make_card(title='说明')
            add_rule(
                note_card, '天牌优先',
                '任意一方前两张牌点数为 8 或 9 点时，双方都不补牌，直接比较点数。'
            )
            add_rule(
                note_card, '庄家第三张',
                '庄家补牌与否只在闲家已补牌时使用上表；闲家未补牌时按「闲家未补牌」表执行。'
            )

        def page_board():
            section_title('下注区示意', '左键下注 · 右键清除单区 · 底部清除/重复/开牌')

            card = make_card()
            bet_cv = BaccaratCanvas(card, game=self, width=680, height=360,
                               bg=PANEL, highlightthickness=0)
            bet_cv.pack(padx=14, pady=(6, 16))

            bet_cv.create_rectangle(6, 6, 674, 354,
                                    fill='#0e3d3d', outline='#3d6a68', width=2)

            bet_cv.create_text(
                24, 26, anchor='w', text=f'{mode_title} · 下注区',
                font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)
            bet_cv.create_text(
                656, 26, anchor='e', text='最低 $100 · 100 的倍数',
                font=(font_name, 12), fill='#a8c2c0')

            if mode == 'classic':
                self.draw_classic_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                                interactive=False)
            elif mode == '2to1':
                self.draw_2to1_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                             interactive=False)
            elif mode == 'one_deck':
                self.draw_one_deck_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                                interactive=False)
            elif mode in BaccaratEngine.ALWAYS_MODES:
                self._draw_standard_betting_board(mode, canvas=bet_cv, bounds=(22,46,658,340), interactive=False)
            elif mode == 'monkey':
                self.draw_monkey_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                              interactive=False)
            elif mode == 'goldendice':
                self.draw_goldendice_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                                  interactive=False)
            elif mode == 'treasure':
                self.draw_treasure_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                                interactive=False)
            elif mode == 'xxx':
                self.draw_xxx_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                           interactive=False)
            elif mode == 'ez':
                self.draw_ez_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                           interactive=False)
            elif mode == 'tiger':
                self.draw_tiger_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                              interactive=False)
            elif mode == 'lucky7':
                self.draw_lucky7_betting_board(canvas=bet_cv, bounds=(22, 46, 658, 340),
                                               interactive=False)
            else:
                # 用真实的下注区布局绘制示意图
                rows = BaccaratEngine.MODE_ROWS.get(mode, ())
                odds_text = self._board_odds(mode)

                board_x0, board_x1 = 22, 658
                band_total = board_x1 - board_x0

                # 顶部两行（side bets）
                band_y = 46
                band_h = 66
                gap = 6
                for row_idx, row_bets in enumerate(rows[:2]):
                    y0 = band_y + row_idx * (band_h + gap)
                    y1 = y0 + band_h
                    n = len(row_bets)
                    if n <= 0:
                        continue
                    w = band_total / n
                    for i, bet_type in enumerate(row_bets):
                        x0 = board_x0 + i * w
                        x1 = x0 + w
                        color = self.BET_COLORS.get(bet_type, '#45665c')
                        bet_cv.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2,
                                                fill=color, outline='#d5cbbd', width=1)
                        label = BaccaratEngine.display_name(bet_type, mode)
                        bet_cv.create_text((x0 + x1) / 2, y0 + 26, text=label,
                                           font=(font_name, 12, 'bold'), fill=WHITE)
                        bet_cv.create_text((x0 + x1) / 2, y1 - 16,
                                           text=odds_text.get(bet_type, ''),
                                           font=(font_name, 10, 'bold'), fill='#f6e6b8')

                # 主注行
                main_y0, main_y1 = 200, 340
                main_widths = (0.4, 0.2, 0.4)
                cur_x = board_x0
                main_specs = [
                    ('Player', '闲家 PLAYER', '#2368bd'),
                    ('Tie', '和局 TIE', '#208452'),
                    ('Banker', '庄家 BANKER', '#c43c4c'),
                ]
                for idx, (key, label, color) in enumerate(main_specs):
                    x0 = cur_x
                    x1 = board_x1 if idx == len(main_specs) - 1 else cur_x + band_total * main_widths[idx]
                    cur_x = x1
                    bet_cv.create_rectangle(x0 + 2, main_y0 + 2, x1 - 2, main_y1 - 2,
                                            fill=color, outline='#d5cbbd', width=2)
                    bet_cv.create_text((x0 + x1) / 2, main_y0 + 36, text=label,
                                       font=(font_name, 15, 'bold'), fill=WHITE)
                    bet_cv.create_text((x0 + x1) / 2, main_y1 - 26,
                                       text=odds_text.get(key, ''),
                                       font=(font_name, 13, 'bold'), fill='#f6e6b8')

            tip_card = make_card()
            add_rule(tip_card, '左键下注', '点击任意下注区，投入当前选中的筹码面额。')
            if mode in ('treasure', 'xxx'):
                add_rule(tip_card, '免手续费选项', '先下注任意含手续费选项，才能下注免手续费选项；取消最后一笔含手续费下注时，对应免手续费下注自动退回。')
            add_rule(tip_card, '主注互斥', '闲家与庄家主注只能选择一方；清除或完全撤销该主注后可改下另一方。和局及边注照常下注。')
            add_rule(tip_card, '右键清除', '右键点击某个下注区，退还该区域的全部下注。')
            add_rule(tip_card, '清除 / 重复', '底部「清除」退还本局所有下注；「重复下注」按上一局金额重新下注。')
            add_rule(tip_card, '开牌', '点击「开牌」或按 Enter 开始发牌与结算。')
            add_rule(tip_card, '庄家赔付拨片', selector_note)

        def page_main_payout():
            section_title('主注与和局赔率', '赔率表示利润赔率 · 不含本金')
            card = make_card()
            main_table = table_block(card, f'{mode_title} · 主注赔率',
                                     main_rows_by_mode.get(mode, []))
            main_table.pack(fill=tk.X, padx=16, pady=(6, 16))

            if mode in ('treasure', 'xxx'):
                note_card = make_card()
                if mode == 'treasure':
                    add_rule(
                        note_card, '黄金牌放大',
                        '闲/庄/和/对子命中的获胜盈利赔率会乘以对应实际发出黄金牌的倍率。'
                    )
                    add_rule(
                        note_card, '20% 手续费',
                        '仅闲、庄、和、闲对、庄对收取20%；龙宝、黄金猎手及有/没黄金扑克均免手续费。'
                    )
                else:
                    add_rule(
                        note_card, '黄金牌放大',
                        '闲/庄/和/对子命中的获胜盈利赔率会乘以对应实际发出黄金牌的倍率；\n'
                        '计算结果按 ROUND_HALF_UP 四舍五入到 2 位小数。'
                    )
                    add_rule(
                        note_card, '50% 手续费',
                        '仅闲、庄、和、闲对、庄对收取50%；龙宝、黄金对决及两个数量边注均免手续费。'
                    )
            elif mode == 'goldendice':
                note_card = make_card()
                add_rule(
                    note_card, '骰子激活',
                    '两骰总和为 8 或 9 时，闲/庄/和/对子的盈利赔率乘以对应随机倍率。'
                )
                add_rule(
                    note_card, '20% 手续费',
                    '仅闲、庄、和、闲对、庄对收取20%；龙宝、超级骰子、骰子点数均免手续费。'
                )

        def page_side_payout():
            section_title('边注赔率表', '按模式显示对应边注 · 赔率为利润赔率')
            groups = side_groups_by_mode.get(mode, [])
            card = make_card()

            if not groups:
                add_rule(card, '本模式无额外边注',
                         '该模式仅提供主注与和局下注。')
            else:
                # 同类型边注合并为一张表；多张表时按上下结构依次堆叠。
                for idx, (group_title, rows) in enumerate(groups):
                    block = table_block(card, group_title, rows)
                    top_pad = 8 if idx == 0 else 0
                    bottom_pad = 18 if idx == len(groups) - 1 else 10
                    block.pack(fill=tk.X, padx=16, pady=(top_pad, bottom_pad))

            if mode in ('goldendice', 'treasure', 'xxx'):
                note_card = make_card(title='附加说明')
                if mode == 'goldendice':
                    add_rule(note_card, '超级骰子',
                             '六档按最高命中条件结算，只赔一档；免 20% 手续费；\n'
                             '最高下注 5000。')
                    add_rule(note_card, '骰子点数',
                             '和局按双方相同点数判定；10只中0点和局，11代表1点，12必输。\n'
                             '免手续费，不加倍，最高下注5000。')
                    add_rule(note_card, '闲庄龙宝', '沿用经典龙宝规则；免手续费，不加倍。')
                elif mode == 'treasure':
                    add_rule(note_card, '黄金猎手',
                             '按下注后实际发出的黄金牌张数结算；免 20% 手续费；\n'
                             '最高下注 5000。')
                    add_rule(note_card, '有 / 没黄金扑克',
                             '包含闲庄两边及补牌；至少1张黄金牌则有获胜，否则没获胜。\n'
                             '分别赔3:2、0.55:1；各上限30K，免手续费，不加倍。')
                    add_rule(note_card, '闲庄龙宝', '沿用经典龙宝赔率；免手续费，不参与黄金牌倍数。')
                else:
                    add_rule(note_card, '黄金对决',
                             '四档只赔最高档，免手续费。\n'
                             '黄金对子：起手两张同点数，且都是黄金牌。')
                    add_rule(note_card, '4–5 / 7–8张黄金扑克',
                             '按系统本局选出的黄金牌面数量结算，分别赔2.15:1、5.25:1。\n'
                             '6张时两项均输；各上限30K，免手续费，不加倍。')
                    add_rule(note_card, '闲庄龙宝', '沿用经典龙宝赔率；免手续费，不参与黄金牌倍数。')

        def page_limits():
            section_title('下注限制与操作', '每局总下注上限 $2,000,000')
            card = make_card()
            limit_rows = [
                ('下注单位', '100 及其倍数'),
                ('闲家 / 庄家 各上限', '$500,000'),
                ('和局 上限', '$100,000'),
                ('每个边注 上限', '$30,000'),
                ('每局总下注 上限', '$2,000,000'),
            ]
            if mode in ('goldendice', 'treasure', 'xxx'):
                limit_rows.append(('黄金猎手上限' if mode == 'treasure' else
                                   '黄金对决上限' if mode == 'xxx' else '本模式专属边注上限',
                                   '$5,000'))
                if mode == 'treasure':
                    limit_rows.append(('有 / 没黄金扑克 各上限', '$30,000 · 免手续费'))
                elif mode == 'xxx':
                    limit_rows.append(('4–5 / 7–8张黄金扑克 各上限', '$30,000 · 免手续费'))
                fee_pct = {'goldendice': '20%', 'treasure': '20%', 'xxx': '50%'}[mode]
                limit_rows.append(('本模式手续费', fee_pct))
            limits_table = table_block(card, '限红', limit_rows)
            limits_table.pack(fill=tk.X, padx=16, pady=(6, 12))

            op_card = make_card()
            add_rule(op_card, '左键下注', '点击任意下注区，投入当前选中的筹码面额。')
            add_rule(op_card, '右键清除', '右键点击某个下注区，退还该区域的全部下注。')
            add_rule(op_card, '清除本局', '点击底部「清除」按钮，退还本局所有下注。')
            add_rule(op_card, '重复下注', '点击「重复下注」按钮，按上一局的下注金额重新下注。')
            add_rule(op_card, 'Enter 开牌', '按 Enter 键或点击「开始 / 开牌」按钮开始本局。')
            if mode in BaccaratEngine.ALWAYS_MODES:
                add_rule(op_card, '连续洗牌', '固定牌由CSM发牌、回收，不使用普通牌靴的切牌或烧牌。')
            elif mode == 'one_deck':
                add_rule(op_card, '每局洗牌', '每局自动重新洗一副52张牌，无需手动切牌。')
            else:
                add_rule(op_card, '切牌', '开新牌靴时按 Enter 随机切牌；也可拖动黄色切牌卡。')

        def page_history():
            section_title('历史记录说明', '右侧面板 · 道路 / 数据 两个标签页')

            overview = make_card(title='历史记录面板总览')
            add_rule(
                overview, '标签切换',
                '右侧面板分「道路」和「数据」两个标签页；点击顶部标签即可切换。'
            )
            add_rule(
                overview, '道路页结构',
                '大路 → 大眼仔 / 蟑螂路 → 珠盘路 → 小路 / 下局预测指示。'
            )

            road_card = make_card(title='道路图说明')
            add_rule(
                road_card, '大路 BIG ROAD',
                '按顺序记录胜方：蓝圈 = 闲胜，红圈 = 庄胜。\n'
                '相同结果向下连成一条龙，换边向右另起一列。\n'
                '和局不单独占格，在当前格子上画绿色斜线；多次和局斜线角上标注次数。\n'
                '闲对 / 庄对分别用蓝色、红色小圆点标在对应格子上。'
            )
            add_rule(
                road_card, '珠盘路 BEAD PLATE',
                '每局占一格：蓝 = 闲胜，红 = 庄胜，绿 = 和局。\n'
                '默认显示「闲 / 庄 / 和」，点击珠盘路区域后可切换显示该局胜方点数。\n'
                + ('12 列 × 6 行，共 72 格；写入第73局时删除最旧6局，加入新局后剩67局。底部计数使用当前 Marker Road 的记录。'
                   if mode == 'one_deck' else '12 列 × 6 行，共 72 格，超出后按 6 格一列滚动。')
            )
            add_rule(
                road_card, '大眼仔 / 小路 / 蟑螂路',
                '由大路推导的衍生路：空心圈、实心圆、斜线三种符号。\n'
                '红 = 顺势，蓝 = 逆势，分别比前一路向后推一步观察。'
            )

            predict_card = make_card(title='下局预测指示')
            add_rule(
                predict_card, '位置',
                '位于面板右下方，分「闲」「庄」两列；\n'
                '三行分别对应大眼仔、小路、蟑螂路。'
            )
            add_rule(
                predict_card, '符号含义',
                '代表若下一局开出该方，对应衍生路将出现的颜色：\n'
                '红 = 顺势，蓝 = 逆势，"—" 表示暂不产生新标记。'
            )

            data_card = make_card(title='数据页说明')
            add_rule(
                data_card, '统计内容',
                ('单副版统计最新500局的总局数、闲胜、庄胜、和局、\n'
                 if mode == 'one_deck' else '统计本轮（当前记录范围内）的总局数、闲胜、庄胜、和局、\n') +
                '闲家对子次数、庄家对子次数，以及本模式的特殊数据。'
            )

            nav_card = make_card(title='操作提示')
            add_rule(
                nav_card, '大路滚动',
                '大路最多容纳 50 列，使用下方横向滚动条查看早期记录；\n'
                '新结果出现时自动跟随到最新位置。'
            )
            add_rule(
                nav_card, '珠盘路切换',
                '在珠盘路区域内单击，可在「文字」与「点数」之间切换显示。'
            )

        def page_notes():
            section_title('重要提示', f'{mode_title} 专属说明')
            card = make_card()
            notes = notes_by_mode.get(mode, (
                ('通用规则', '按当前模式显示的主注与边注赔率结算。'),
            ))
            for title, body in notes:
                add_rule(card, title, body)

        # ================================================================
        # 左侧主题按钮
        # ================================================================
        themes = [
            ('玩法与补牌规则', page_rules),
            ('下注区示意',     page_board),
            ('主注赔率',       page_main_payout),
            ('边注赔率表',     page_side_payout),
            ('下注限制与操作', page_limits),
            ('历史记录说明',   page_history),
            ('重要提示',       page_notes),
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
                    bg='#1e3433' if active else SIDEBAR,
                    fg=GOLD if active else MUTED,
                    activebackground='#24403e',
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
                activebackground='#24403e',
                activeforeground=GOLD,
                relief=tk.FLAT,
                bd=0,
                anchor='w',
                padx=20,
                pady=12,
                cursor='hand2'
            )
            btn.pack(fill=tk.X)
            theme_buttons[name] = btn

        select_theme(themes[0][0])

        # ================================================================
        # 关闭事件
        # ================================================================
        def _close_instruction():
            try:
                self._instruction_window = None
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
                              subtext_font_size=10):
        tag = f'control_button_{len(self.control_buttons)}'
        shadow = self.canvas.create_rectangle(x0 + 5, y0 + 6, x1 + 5, y1 + 6,
                                              fill='#070605', outline='#070605',
                                              width=1, tags=(tag, 'controls'))
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

    def update_control_states(self):
        enabled = self.accept_bets and not self.animation_running and not self.settlement_running
        self.update_mode_selector_style()
        self._update_fixed_selector()
        self._update_main_bet_availability()
        if hasattr(self, 'squeeze_checkbox_items'):
            self._update_squeeze_selector(enabled)
        self._update_banker_selector(enabled)
        for attr in ('clear_button', 'repeat_button', 'deal_button'):
            tag = getattr(self, attr, None)
            if tag:
                self.set_control_button_state(tag, enabled)

    # ---------------------------------------------------------- V23 chip motion
    def _schedule_chip_motion(self, delay_ms, callback):
        """Schedule one chip-motion frame and keep its after-id cancellable."""
        holder = {}

        def run():
            after_id = holder.get('id')
            if after_id is not None:
                self.chip_motion_after_ids.discard(after_id)
            if self._closing:
                return
            callback()

        after_id = self.after(max(0, int(delay_ms)), run)
        holder['id'] = after_id
        self.chip_motion_after_ids.add(after_id)
        return after_id

    def _chip_rack_source_position(self):
        """Return the centre of the currently selected physical chip in the rack."""
        items = self.chip_selector_items.get(self.selected_chip)
        if items:
            try:
                coords = self.canvas.coords(items[1])
                if len(coords) >= 4:
                    return ((coords[0] + coords[2]) / 2.0,
                            (coords[1] + coords[3]) / 2.0)
            except tk.TclError:
                pass
        # Seven-chip rack is centred in the lower control area.
        return (self.WIDTH / 2.0, 674.0)

    def _chip_rack_return_position(self, index=0, total=1):
        """Spread simultaneous winning returns slightly across the chip-rack centre."""
        total = max(1, int(total))
        index = max(0, min(int(index), total - 1))
        if total <= 1:
            offset = 0.0
        else:
            spacing = min(34.0, 150.0 / max(1, total - 1))
            offset = (index - (total - 1) / 2.0) * spacing
        return (self.WIDTH / 2.0 + offset, 674.0)

    def _fee_chip_target_position(self):
        """Collect fees beside the dice/cards or at the active mode header."""
        if getattr(self, 'game_mode', None) == 'goldendice':
            return self._golden_dice_geometry['fee']
        if getattr(self, 'game_mode', None) in ('treasure', 'xxx'):
            return self._treasure_board_geometry['fee']
        return (self.HEADER_MIDDLE_X, self.BOARD_HEADER_Y)

    def _animate_amount_chip(self, amount, start_xy, target_xy, on_complete=None,
                             role='wager', duration_ms=None, keep_at_target=False):
        """Move one chip; wager/return flights default to 200 ms."""
        if self._closing:
            if callable(on_complete):
                on_complete()
            return

        amount = float(amount)
        if amount <= 0:
            if callable(on_complete):
                on_complete()
            return

        self.chip_motion_serial += 1
        tag = f'chip_motion_{self.chip_motion_serial}'
        x, y = map(float, start_xy)
        tx, ty = map(float, target_xy)
        radius = float(self.MOTION_CHIP_RADIUS)
        chip_color = self.bet_chip_color(amount)
        text_color = self.contrast_text_color(chip_color)
        outline = '#ffd84a' if role == 'fee' else '#e2ddd5'
        motion_tags = ((tag, 'chip_motion', f'settlement_{role}') if role in ('profit', 'loss')
                       else (tag, 'chip_motion'))

        outer = self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill='#292522', outline='#151311', width=1,
            tags=motion_tags)
        inner = self.canvas.create_oval(
            x - radius + 3, y - radius + 3, x + radius - 3, y + radius - 3,
            fill=chip_color, outline=outline, width=2 if role == 'fee' else 1,
            tags=motion_tags)
        text = self.canvas.create_text(
            x, y, text=self._compact_amount(amount),
            font=('Arial', 9, 'bold'), fill=text_color,
            tags=motion_tags)
        duration = self.CHIP_MOVE_DURATION_MS if duration_ms is None else max(1, int(duration_ms))
        steps = max(1, round(self.CHIP_MOVE_STEPS * duration / self.CHIP_MOVE_DURATION_MS))
        frame_ms = max(1, int(round(duration / steps)))

        def place_items(cx, cy):
            try:
                if not self.canvas.type(outer):
                    return False
                self.canvas.coords(outer, cx - radius, cy - radius,
                                   cx + radius, cy + radius)
                self.canvas.coords(inner, cx - radius + 3, cy - radius + 3,
                                   cx + radius - 3, cy + radius - 3)
                self.canvas.coords(text, cx, cy)
                self.canvas.tag_raise(tag)
            except tk.TclError:
                return False
            return True

        def frame(step):
            if self._closing:
                return
            ratio = min(1.0, max(0.0, step / steps))
            # Smoothstep keeps the motion quick but avoids a mechanical stop.
            eased = ratio * ratio * (3.0 - 2.0 * ratio)
            cx = x + (tx - x) * eased
            cy = y + (ty - y) * eased
            if step >= steps:
                cx, cy = tx, ty
            if not place_items(cx, cy):
                return
            if step >= steps:
                if not keep_at_target:
                    try:
                        self.canvas.delete(tag)
                    except tk.TclError:
                        pass
                if callable(on_complete):
                    on_complete()
                return
            self._schedule_chip_motion(frame_ms, lambda: frame(step + 1))

        place_items(x, y)
        self._schedule_chip_motion(frame_ms, lambda: frame(1))
        return tag

    def _settlement_bank_position(self):
        coords = self.canvas.coords(self.animation_phase_text)
        return tuple(coords[:2])

    @classmethod
    def _settlement_profit_position(cls, spot):
        x, y = spot['chip_pos']
        # Preserve the visible gap after enlarging both neighbouring chips.
        return (x - cls.WAGER_CHIP_RADIUS - cls.MOTION_CHIP_RADIUS - 4, y - 8)

    def _start_settlement_chip_movements(self):
        if self.settlement_chip_moves_started:
            return
        self.settlement_chip_moves_started = True
        bank = self._settlement_bank_position()
        for key, profit in self.flash_winner_amounts.items():
            spot = self.bet_spots.get(key)
            if not spot or profit <= 0:
                continue
            self.settlement_profit_tags[key] = self._animate_amount_chip(
                profit, bank, self._settlement_profit_position(spot), role='profit',
                duration_ms=500, keep_at_target=True)
        for key, stake in self.settlement_losing_amounts.items():
            spot = self.bet_spots.get(key)
            if not spot or stake <= 0:
                continue
            # The moving loss chip replaces the unchanged stake at time zero.
            self.settlement_hold_amounts.pop(key, None)
            self._animate_amount_chip(stake, spot['chip_pos'], bank,
                                      role='loss', duration_ms=500)
        self.update_bet_chips()

    def _complete_pending_bet_visual(self, key, amount):
        pending = max(0.0, float(self.pending_bet_visual_amounts.get(key, 0.0))
                      - float(amount))
        if pending > 1e-9:
            self.pending_bet_visual_amounts[key] = pending
        else:
            self.pending_bet_visual_amounts.pop(key, None)
        if not self._closing:
            self.update_bet_chips()
            self.canvas.tag_raise('controls')

    def _register_fee_visual(self, bet_type, amount):
        """Reserve a fee visually until its chip reaches the collection tray."""
        self._fee_visual_serial += 1
        token = self._fee_visual_serial
        self.pending_fee_visuals[token] = {
            'bet_type': bet_type, 'amount': float(amount), 'motion_tag': None}
        return token

    def _start_fee_visual(self, token):
        transfer = self.pending_fee_visuals.get(token)
        if transfer is None or self._closing:
            return
        spot = self.bet_spots.get((transfer['bet_type'], None))
        if not spot:
            self._complete_fee_visual(token)
            return
        tag = self._animate_amount_chip(
            transfer['amount'], tuple(spot['chip_pos']), self._fee_chip_target_position(),
            on_complete=lambda: self._complete_fee_visual(token), role='fee')
        # A synchronous completion (including reduced-animation callers) may
        # already have removed this transfer.
        if token in self.pending_fee_visuals:
            transfer['motion_tag'] = tag

    def _complete_fee_visual(self, token):
        if self.pending_fee_visuals.pop(token, None) is not None and not self._closing:
            self._refresh_treasure_pool_text()

    def _visible_fee_amount(self):
        pending = sum(item['amount'] for item in self.pending_fee_visuals.values())
        return max(0.0, float(self.treasure_pot_amount) - pending)

    def _cancel_fee_visuals(self, bet_type=None, amount=None):
        """Refund newest pending fees first without leaving a flying copy."""
        remaining = None if amount is None else max(0.0, float(amount))
        for token, transfer in reversed(tuple(self.pending_fee_visuals.items())):
            if bet_type is not None and transfer['bet_type'] != bet_type:
                continue
            if remaining is not None and remaining <= 1e-9:
                break
            removed = transfer['amount'] if remaining is None else min(remaining, transfer['amount'])
            left = transfer['amount'] - removed
            tag = transfer['motion_tag']
            if left <= 1e-9:
                self.pending_fee_visuals.pop(token)
                if tag:
                    self.canvas.delete(tag)
            else:
                transfer['amount'] = left
                # A partial refund keeps the chip on its current flight path.
                if tag:
                    color = self.bet_chip_color(left)
                    for index, item in enumerate(self.canvas.find_withtag(tag)):
                        if self.canvas.type(item) == 'text':
                            self.canvas.itemconfigure(item, text=self._compact_amount(left),
                                                      fill=self.contrast_text_color(color))
                        elif index == 1:
                            self.canvas.itemconfigure(item, fill=color)
            if remaining is not None:
                remaining -= removed

    def _start_winning_chip_return(self):
        """After flashing, return each stake and its separate profit to the rack."""
        if self.settlement_return_animating:
            return True

        returning = []
        for key, profit in self.flash_winner_amounts.items():
            spot = self.bet_spots.get(key)
            if spot and float(profit) > 0:
                stake = float(self.settlement_hold_amounts.get(key, 0.0))
                if stake > 0:
                    returning.append((key, stake, tuple(spot['chip_pos'])))
                returning.append((key, float(profit), self._settlement_profit_position(spot)))
        for bet_type, amount in self.push_return_amounts.items():
            key = (bet_type, None)
            spot = self.bet_spots.get(key)
            if spot and float(amount) > 0:
                returning.append((key, float(amount), tuple(spot['chip_pos'])))
        if not returning:
            return False

        self.settlement_return_animating = True
        self.settlement_return_keys = {key for key, _amount, _start in returning}
        for tag in self.settlement_profit_tags.values():
            if tag:
                self.canvas.delete(tag)
        self.settlement_profit_tags.clear()
        self.update_bet_chips()

        remaining = {'count': len(returning)}

        def one_finished():
            remaining['count'] -= 1
            if remaining['count'] <= 0 and not self._closing:
                self.settlement_return_animating = False
                self.settlement_return_keys.clear()
                self.finish_settlement()

        for index, (_key, amount, start) in enumerate(returning):
            target = self._chip_rack_return_position(index, len(returning))
            self._animate_amount_chip(amount, start, target,
                                      on_complete=one_finished, role='return')
        return True

    # --------------------------------------------------------------- bet actions
    def select_chip(self, amount):
        self.selected_chip = float(amount)
        for value, items in self.chip_selector_items.items():
            outer, _inner, _text = items
            selected = float(value) == float(amount)
            self.canvas.itemconfigure(outer,
                                      outline='#ffda42' if selected else '#6d6259',
                                      width=5 if selected else 3)
        self.canvas.tag_raise('chip_selector')

    def bet_limit_for(self, bet_type):
        if bet_type in ('Golden Present', 'Golden Absent', 'Golden Count 4-5', 'Golden Count 7-8'):
            return 30_000.0
        if bet_type in ('Golden Hunter', 'Golden Duel', 'Super Dice', 'Dice Points'):
            return 5_000.0
        if bet_type in ('Player', 'Banker'):
            return 500_000.0
        if bet_type == 'Tie':
            return 100_000.0
        return 30_000.0

    @staticmethod
    def _wager_fee_rate(mode, bet_type):
        if mode in ('goldendice', 'treasure', 'xxx'):
            # Only the five bottom-row wagers carry a fee; both Dragons and
            # every mode-specific side wager are exempt.
            if bet_type in ('Player', 'Banker', 'Tie', 'Pair Player', 'Pair Banker'):
                return 0.50 if mode == 'xxx' else 0.20
        return 0.0

    def _treasure_fee_rate(self, bet_type):
        return self._wager_fee_rate(self.game_mode, bet_type)

    def _refresh_treasure_pool_text(self):
        item = getattr(self, 'treasure_pool_display', None)
        if item:
            try:
                name = ('50%' if self.game_mode == 'xxx' else
                        '20%' if self.game_mode in ('goldendice', 'treasure') else '')
                value = f'${self._visible_fee_amount():,.0f}'
                self.canvas.itemconfigure(item, text=value if self.game_mode in ('goldendice', 'treasure', 'xxx')
                                          else f'{name}手续费 {value}')
            except tk.TclError:
                pass
        if self.game_mode in ('goldendice', 'treasure', 'xxx'):
            self._draw_golden_dice_fee_chips()

    def _current_round_total_cost(self):
        """Visible current-round outlay = wagers + active-mode fees."""
        return float(self.bet_state.total_at_risk()) + sum(
            float(v) for v in self.bet_fee_state.values())

    def place_bet(self, bet_type, amount=None, record_undo=True):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return False
        if (bet_type, None) not in self.bet_spots:
            return False
        if self._bet_is_blocked(bet_type):
            return False
        requested = float(amount if amount is not None else self.selected_chip)

        # V20: every wager must be exactly 100 or a multiple of 100.
        if requested < 100.0 or abs(requested / 100.0 - round(requested / 100.0)) > 1e-9:
            messagebox.showwarning('下注单位', '下注只接受100及100的倍数。',
                                   parent=self.winfo_toplevel())
            return False

        area_current = self.bet_state.current_area_bet(bet_type)
        table_current = self.bet_state.total_at_risk()
        fee_rate = self._treasure_fee_rate(bet_type)
        balance_capacity = self.balance / (1.0 + fee_rate) if fee_rate else self.balance
        raw_allowed = min(requested,
                          self.bet_limit_for(bet_type) - area_current,
                          self.MAX_TABLE_BET - table_current,
                          balance_capacity)
        raw_allowed = max(0.0, raw_allowed)

        # Auto-adjustment must also remain on a 100-unit boundary.  We floor
        # rather than round upward so the adjusted bet never exceeds balance,
        # area limit, or table limit.
        allowed = float(int(raw_allowed // 100.0) * 100)
        if allowed < 100.0:
            return False
        if allowed < requested:
            # If the selected chip is larger than the remaining limit for this
            # betting area, silently place only the maximum amount allowed.
            # Other clipping reasons (for example balance/table capacity) keep
            # the existing warning so they remain visible to the player.
            area_remaining = max(0.0, self.bet_limit_for(bet_type) - area_current)
            table_remaining = max(0.0, self.MAX_TABLE_BET - table_current)
            clipped_by_area_limit = (
                area_remaining + 1e-9 < requested
                and area_remaining <= table_remaining + 1e-9
                and area_remaining <= balance_capacity + 1e-9
            )
            if not clipped_by_area_limit:
                messagebox.showwarning('下注限制', f'下注已自动调整为 {self.format_money(allowed)}。',
                                       parent=self.winfo_toplevel())
        fee = allowed * fee_rate
        key = (bet_type, None)
        if not self.bet_state.add_bet(bet_type, allowed):
            return False
        # Keep the newly added amount off the static destination chip until the
        # 0.2-second flying chip actually arrives there. Existing chips remain.
        self.pending_bet_visual_amounts[key] = (
            self.pending_bet_visual_amounts.get(key, 0.0) + allowed)
        self.balance -= allowed + fee
        if fee > 0:
            self.bet_fee_state[bet_type] = self.bet_fee_state.get(bet_type, 0.0) + fee
            self.treasure_pot_amount += fee
        fee_visual = self._register_fee_visual(bet_type, fee) if fee > 0 else None
        if record_undo:
            self.undo_stack.append((bet_type, None, allowed))
        self.summary_mode = 'bet'
        self._refresh_treasure_pool_text()
        self.update_display()

        source = self._chip_rack_source_position()
        target = tuple(self.bet_spots[key]['chip_pos'])

        def wager_arrived():
            self._complete_pending_bet_visual(key, allowed)
            if fee_visual is not None:
                self._start_fee_visual(fee_visual)

        self._animate_amount_chip(
            allowed, source, target,
            on_complete=wager_arrived,
            role='wager')

        self.save_balance()
        return True

    def clear_single_bet(self, bet_type, _param=None):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.bet_state.clear_area(bet_type)
        if refunded <= 0:
            return
        fee = float(self.bet_fee_state.pop(bet_type, 0.0))
        self._cancel_fee_visuals(bet_type)
        self.balance += refunded + fee
        if fee > 0:
            self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee)
        self.undo_stack = [item for item in self.undo_stack if item[0] != bet_type]
        self.pending_bet_visual_amounts.pop((bet_type, None), None)
        self._refund_unqualified_golden_dice_sides()
        self._refresh_treasure_pool_text()
        self.update_display()
        self.save_balance()

    def undo_last_bet(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        while self.undo_stack:
            bet_type, _param, amount = self.undo_stack.pop()
            removed = self.bet_state.remove_amount(bet_type, amount)
            if removed > 0:
                key = (bet_type, None)
                pending = max(0.0, self.pending_bet_visual_amounts.get(key, 0.0) - removed)
                if pending > 1e-9:
                    self.pending_bet_visual_amounts[key] = pending
                else:
                    self.pending_bet_visual_amounts.pop(key, None)
                fee_rate = self._treasure_fee_rate(bet_type)
                fee = min(float(self.bet_fee_state.get(bet_type, 0.0)), removed * fee_rate)
                if fee > 0:
                    left = self.bet_fee_state.get(bet_type, 0.0) - fee
                    if left > 1e-9:
                        self.bet_fee_state[bet_type] = left
                    else:
                        self.bet_fee_state.pop(bet_type, None)
                    self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee)
                    self._cancel_fee_visuals(bet_type, fee)
                self.balance += removed + fee
                self._refund_unqualified_golden_dice_sides()
                self._refresh_treasure_pool_text()
                self.update_display()
                self.save_balance()
                return

    def clear_bets(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.bet_state.clear_all()
        fee = sum(float(v) for v in self.bet_fee_state.values())
        if refunded <= 0 and fee <= 0:
            return
        self.balance += refunded + fee
        if fee > 0:
            self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee)
        self.bet_fee_state.clear()
        self._cancel_fee_visuals()
        self.undo_stack.clear()
        self.pending_bet_visual_amounts.clear()
        self._refresh_treasure_pool_text()
        self.update_display()
        self.save_balance()

    def snapshot_bets(self):
        return [(bet_type, None, float(amount))
                for bet_type, amount in self.bet_state.bets.items() if amount > 0]

    def repeat_last_bets(self):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or not self.last_round_bets):
            return

        active = {key[0] for key in self.bet_spots}
        repeatable = [(bt, p, amt) for bt, p, amt in self.last_round_bets if bt in active]
        if self.game_mode == 'goldendice':
            # Restore the prerequisite before its dependent side wagers, even
            # when an older snapshot stored the entries in a different order.
            if not any(bt in self.GOLDEN_DICE_BASE_PROFIT_ODDS and amt > 0
                       for bt, _p, amt in repeatable):
                return
            repeatable.sort(key=lambda item: item[0] not in self.GOLDEN_DICE_BASE_PROFIT_ODDS)
        elif self.game_mode in ('treasure', 'xxx'):
            if not any(amt > 0 and self._wager_fee_rate(self.game_mode, bt) > 0
                       for bt, _p, amt in repeatable):
                return
            repeatable.sort(key=lambda item: self._wager_fee_rate(self.game_mode, item[0]) == 0)
        main_hands = self._squeeze_wager_hands(
            {bt: amt for bt, _p, amt in repeatable})
        if len(main_hands) > 1:
            messagebox.showwarning(
                '主注互斥', '上局记录同时包含闲、庄主注，无法重复。请重新选择其中一方下注。',
                parent=self.winfo_toplevel())
            return

        # Refund the current wagers only after validating an older snapshot.
        self.clear_bets()
        required = sum(amt * (1.0 + self._treasure_fee_rate(bt))
                       for bt, _p, amt in repeatable)
        if self.balance + 1e-9 < required:
            messagebox.showwarning('余额不足',
                                   f'重复上局下注需要 {self.format_money(required)}，当前余额为 {self.format_money(self.balance)}。',
                                   parent=self.winfo_toplevel())
            return
        for bet_type, _param, amount in repeatable:
            self.place_bet(bet_type, amount=amount, record_undo=True)

    # ------------------------------------------------------------ display update
    @staticmethod
    def format_money(value):
        if abs(value - round(value)) < 0.005:
            return f'${value:,.0f}'
        return f'${value:,.2f}'

    @staticmethod
    def contrast_text_color(color):
        value = color.lstrip('#')
        if len(value) != 6:
            return 'black'
        red, green, blue = (int(value[i:i + 2], 16) for i in (0, 2, 4))
        luminance = 0.299 * red + 0.587 * green + 0.114 * blue
        return 'black' if luminance >= 150 else 'white'

    @staticmethod
    def _compact_amount(amount):
        if amount >= 1_000_000:
            # Winning chips are compacted in M once they reach 1000K.
            # Exact 100K steps have an exact one-decimal M representation;
            # smaller residuals are intentionally truncated and marked with +.
            hundred_k = 100_000.0
            exact_step = abs(amount / hundred_k - round(amount / hundred_k)) < 1e-9
            truncated_tenths = int(amount // hundred_k) / 10.0
            text = (f'{truncated_tenths:.0f}M' if abs(truncated_tenths - round(truncated_tenths)) < 1e-9
                    else f'{truncated_tenths:.1f}M')
            return text if exact_step else text + '+'
        if amount >= 1000:
            value = amount / 1000
            return f'{value:.0f}K' if abs(value - round(value)) < 0.01 else f'{value:.1f}K'
        return str(int(round(amount))) if abs(amount - round(amount)) < 0.01 else f'{amount:.1f}'

    def update_display(self):
        self.canvas.itemconfigure(self.balance_text, text=f'余额: {self.format_money(self.balance)}')
        if self.summary_mode == 'win':
            self.canvas.itemconfigure(self.total_bet_text,
                                      text=f'上局返还: {self.format_money(self.last_win_amount)}')
        else:
            self.canvas.itemconfigure(self.total_bet_text,
                                      text=f'本局下注: {self.format_money(self._current_round_total_cost())}')
        self.update_bet_chips()
        self._refresh_treasure_pool_text()
        if self.game_mode == 'lucky7':
            self._refresh_lucky7_jackpot_info()
        self.update_history_table()
        self.update_control_states()

    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        for key, spot in self.bet_spots.items():
            amount = self.bet_state.current_area_bet(key[0])
            # While a new wager is flying in, show only the amount that had
            # already reached this betting spot.
            pending_in = float(self.pending_bet_visual_amounts.get(key, 0.0))
            if pending_in > 0 and not self.settlement_running:
                amount = max(0.0, amount - pending_in)
            # Winning and Push stakes retain their original amount until
            # the flash ends. Losing stakes leave at flash time zero.
            if self.settlement_running and key in self.settlement_hold_amounts:
                amount = self.settlement_hold_amounts[key]
            # The moving copy replaces the stake during its return flight.
            if self.settlement_return_animating and key in self.settlement_return_keys:
                continue
            if amount <= 0:
                continue
            x0, y0, x1, y1 = spot['bounds']
            # Keep the wager chip in the geometric centre of its betting area.
            x, y = (x0 + x1) / 2, (y0 + y1) / 2
            radius = (min(self.WAGER_CHIP_RADIUS, (x1 - x0) / 2 - 2)
                      if self.game_mode in BaccaratEngine.SPECIAL_MODES and key[0].startswith('Tie ')
                      else self.WAGER_CHIP_RADIUS)
            x = max(x0 + radius + 1, min(x1 - radius - 1, x))
            y = max(y0 + radius + 1, min(y1 - radius - 1, y))
            self._draw_amount_chip(amount, x, y, ('bet_chip_dynamic', spot['tag']), radius=radius)
        self.canvas.tag_raise('squeeze_backdrop')
        self.canvas.tag_raise('squeeze_overlay')

    def _draw_amount_chip(self, amount, x, y, tags, radius=None):
        """Use identical denomination colours and labels for wagers and fees."""
        radius = self.WAGER_CHIP_RADIUS if radius is None else radius
        color = self.bet_chip_color(amount)
        self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                               fill='#292522', outline='#151311', width=1, tags=tags)
        self.canvas.create_oval(x-radius+3, y-radius+3, x+radius-3, y+radius-3,
                               fill=color, outline='#e2ddd5', width=1, tags=tags)
        self.canvas.create_text(x, y, text=self._compact_amount(amount),
                               font=('Arial', 9, 'bold'),
                               fill=self.contrast_text_color(color), tags=tags)

    @classmethod
    def bet_chip_color(cls, amount):
        # _compact_amount() switches to M at 1,000,000; mirror that visual state
        # with a dark-navy chip. contrast_text_color() then yields white text.
        if amount >= 1_000_000:
            return cls.M_CHIP_COLOR

        color = cls.CHIP_SPECS[0][1]
        for threshold, chip_color, _label in cls.CHIP_SPECS:
            if amount >= threshold:
                color = chip_color
            else:
                break
        return color

    # ------------------------------------------------------- Golden Dice mode
    def _ensure_golden_dice_bowl(self):
        if self.golden_dice_bowl is None:
            state = getattr(self, 'runtime_store', {}).get('temp_data', {}).get('golden_dice_state')
            self.golden_dice_bowl = GoldenDiceBowl.restore(state) or GoldenDiceBowl()
            self.current_golden_dice = self.golden_dice_bowl.values()
            self._remember_golden_dice_state()
        return self.golden_dice_bowl

    def _remember_golden_dice_state(self):
        if hasattr(self, 'runtime_store'):
            self.runtime_store.setdefault('temp_data', {})['golden_dice_state'] = self.golden_dice_bowl.snapshot()
            self._write_runtime_store()

    def _draw_golden_dice_cup(self, canvas, bounds, interactive=True):
        x0, y0, x1, y1 = bounds
        sx, sy = (x1-x0)/738, (y1-y0)/234
        scale = min(sx, sy)
        def xy(x, y):
            return x0+x*sx, y0+y*sy
        canvas.create_rectangle(*xy(247,0), *xy(491,156), fill='#211811',
                                outline='#856a32', tags='board_dynamic')
        bowl = self._ensure_golden_dice_bowl() if interactive else GoldenDiceBowl((4,5), random.Random(7))
        geometry = dict(origin=xy(247,0), scale=(sx,sy), fee=xy(463,94), cup=xy(345,75))
        self._paint_golden_dice_bowl(canvas, bowl, geometry, interactive)
        def label(x, y, text, size=10, color='#e6d9b6'):
            return canvas.create_text(*xy(x,y), text=text, fill=color,
                font=('Arial', -max(7,round(size*scale)), 'bold'),
                anchor='center', justify='center', tags='board_dynamic')
        status = label(369, 147, '8/9点使用加强倍数', 13)
        self._draw_golden_fee_placeholder(canvas, bounds, mode='goldendice')
        if interactive:
            self._golden_dice_geometry = geometry
            self.golden_dice_status_text = status
            self.treasure_pool_display = None

    def _paint_golden_dice_bowl(self, canvas, bowl, geometry, interactive=True):
        x, y = geometry['origin']
        sx, sy = geometry['scale']
        tags = ('board_dynamic','golden_dice_cup_art')
        if Image is not None and ImageTk is not None:
            picture = _gd_render_bowl(bowl)
            size = (max(1,round(196*sx)), max(1,round(138*sy)))
            if picture.size != size:
                picture = picture.resize(size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(picture, master=canvas)
            if interactive and canvas.find_withtag('golden_dice_cup_art'):
                canvas.itemconfigure(self._golden_dice_cup_item, image=photo)
            else:
                item = canvas.create_image(x,y, anchor='nw', image=photo, tags=tags)
                if interactive:
                    self._golden_dice_cup_item = item
            if interactive:
                self._golden_dice_cup_photo = photo
            else:
                canvas._golden_dice_preview_photo = photo
        else:
            # Keep the same geometry and top faces without the optional PIL package.
            canvas.delete('golden_dice_cup_art')
            for meshes in _gd_bowl_mesh(bowl):
                for _depth, points, color, line, width in meshes:
                    projected = [value for point in points for value in
                                 (x+_gd_project(point,bowl)[0]*sx, y+_gd_project(point,bowl)[1]*sy)]
                    if color and color[3] > 100:
                        canvas.create_polygon(*projected, fill='#%02x%02x%02x'%color[:3], outline='', tags=tags)
                    if line:
                        canvas.create_line(*projected, fill='#%02x%02x%02x'%line[:3], width=width, tags=tags)

    def _draw_golden_fee_placeholder(self, canvas, bounds, mode=None):
        """Shared fee-chip tray, with the active mode's original fee rate."""
        mode = mode or self.game_mode
        x0, y0, x1, y1 = bounds
        sx, sy = (x1 - x0) / 738.0, (y1 - y0) / 234.0
        scale = min(sx, sy)
        fx, fy = x0 + 463 * sx, y0 + 94 * sy
        canvas.create_oval(fx-25*sx, fy-33*sy, fx+25*sx, fy+42*sy,
            fill='', outline='#a89465', width=1.5, dash=(4,3),
            tags=('board_dynamic', 'golden_dice_fee_placeholder'))
        for y, caption, size in ((36, '手续费', 14), (124, '50%' if mode == 'xxx' else '20%', 12)):
            canvas.create_text(fx, y0 + y * sy, text=caption, fill='#ffe69b',
                font=('Arial', -max(7, round(size * scale)), 'bold'),
                anchor='center', justify='center', tags='board_dynamic')

    def _draw_golden_dice_fee_chips(self):
        """Show only the fees whose moving chips have reached the tray."""
        self.canvas.delete('golden_dice_fee_chips')
        amount = self._visible_fee_amount()
        if amount <= 0 or self._golden_dice_fee_collected:
            return
        x, y = self._fee_chip_target_position()
        self._draw_amount_chip(amount, x, y,
                              ('board_dynamic','golden_dice_fee_chips'))

    def _animate_golden_dice_fee_light(self, on_complete, step=0):
        """Consume the fee chip, then send its light into the cup or card slots."""
        if self._closing or self.game_mode not in ('goldendice', 'treasure', 'xxx'):
            return
        if step == 0 and self.pending_fee_visuals:
            # An immediate Deal click must still let every fee arrive before
            # the accumulated chip is consumed by the round-start light.
            self._queue_animation(20, self._animate_golden_dice_fee_light, on_complete, 0)
            return
        if step == 0:
            self._golden_dice_fee_collected = True
            self.canvas.delete('golden_dice_fee_chips')
        self.canvas.delete('golden_dice_fee_light')
        if self.treasure_pot_amount <= 0 or step > 22:
            on_complete()
            return
        sx, sy = self._fee_chip_target_position()
        tx, ty = (self._treasure_board_geometry['cards_center']
                  if self.game_mode in ('treasure', 'xxx') else self._golden_dice_geometry['cup'])
        t = max(0, min(1, (step-4)/14))
        x, y = sx+(tx-sx)*t, sy+(ty-sy)*t-18*math.sin(math.pi*t)
        tags = ('board_dynamic', 'golden_dice_fee_light')
        if 0 < t < 1:
            self.canvas.create_line(sx, sy, x, y, fill='#ad7516', width=5, tags=tags)
            self.canvas.create_line(sx, sy, x, y, fill='#ffe68a', width=2, tags=tags)
        radius = 16-step*1.5 if step < 5 else (7 if step < 18 else 7+(step-18)*3)
        for r, color in ((radius+5, '#865b16'), (radius, '#f4c64a'), (max(2, radius-4), '#fff4bd')):
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=color, outline='', tags=tags)
        self._queue_animation(25, self._animate_golden_dice_fee_light, on_complete, step+1)

    def _draw_golden_dice_multiplier(self, bet_type):
        weights = self.GOLDEN_DICE_MULTIPLIER_WEIGHTS[bet_type]
        return int(random.SystemRandom().choices(
            self.GOLDEN_DICE_MULTIPLIER_VALUES, weights=weights, k=1)[0])

    def _prepare_golden_dice_round(self, on_complete=None):
        """Fees enter once; retries shake the same bodies without charging again."""
        self.current_golden_map = {}
        self.current_golden_cards = []
        self.golden_dice_active = False
        self._golden_dice_roll_ready = False
        self.golden_dice_multipliers = {
            bet_type: self._draw_golden_dice_multiplier(bet_type)
            for bet_type in self.GOLDEN_DICE_BASE_PROFIT_ODDS
        }
        self._golden_dice_reels_ready = set()
        self._refresh_golden_dice_ribbons()
        self._show_golden_dice_panel_shell()

        def start_roll():
            for index, bet_type in enumerate(self.GOLDEN_DICE_BASE_PROFIT_ODDS):
                self._queue_animation(index*150, self._animate_golden_dice_multiplier_row, bet_type, 0)
            self._start_golden_dice_roll(on_complete)

        self._animate_golden_dice_fee_light(start_roll)

    def _start_golden_dice_roll(self, on_complete=None):
        if self._closing or self.game_mode != 'goldendice':
            return
        self._ensure_golden_dice_bowl().begin()
        self._golden_dice_phase = 'shake'
        self._golden_dice_time = 0.
        self._golden_dice_stable_time = 0.
        self._golden_dice_rest_anchor = None
        self._animate_golden_dice_roll(on_complete)

    def _reroll_golden_dice(self, reason, on_complete):
        self._golden_dice_phase = 'reroll'
        self.canvas.itemconfigure(self.animation_phase_text, text=f'重骰 · {reason}')
        self._queue_animation(600, self._start_golden_dice_roll, on_complete)

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

    def _show_golden_dice_panel_shell(self):
        """Use the inline cup and existing odds labels, keeping history visible."""
        self.golden_dice_multiplier_text_items = {
            bet: self.bet_spots[(bet, None)]['odds_item']
            for bet in self.GOLDEN_DICE_BASE_PROFIT_ODDS
        }
        self.canvas.itemconfigure(self.golden_dice_status_text,
                                  text='8/9点使用加强倍数', fill='#e6d9b6')

    def _animate_golden_dice_multiplier_row(self, bet_type, step=0):
        if self._closing or self.game_mode != 'goldendice':
            return
        item = self.golden_dice_multiplier_text_items.get(bet_type)
        if item is None:
            return
        if step < 9:
            value = self.GOLDEN_DICE_MULTIPLIER_VALUES[
                secrets.randbelow(len(self.GOLDEN_DICE_MULTIPLIER_VALUES))]
            try:
                self.canvas.itemconfigure(item, text=f'×{value}', fill='#fff2a3')
            except tk.TclError:
                return
            self._queue_animation(40, self._animate_golden_dice_multiplier_row,
                                  bet_type, step + 1)
            return
        value = int(self.golden_dice_multipliers.get(bet_type, 2))
        try:
            self.canvas.itemconfigure(item, text=f'×{value}', fill='#ffd84a')
        except tk.TclError:
            return
        self._golden_dice_reels_ready.add(bet_type)
        self._refresh_golden_dice_ribbons()

    def _animate_golden_dice_roll(self, on_complete=None):
        if self._closing or self.game_mode != 'goldendice':
            return
        started = time.monotonic()
        bowl = self.golden_dice_bowl
        valid_result = False
        # 480 Hz contact integration, 30 Hz rendering; schedule the remaining
        # frame time instead of adding rendering cost to each animation delay.
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
                    # Sleep the confirmed static bodies before reading geometry
                    # or announcing a retry; the displayed resting pose stays fixed.
                    for die in bowl.dice:
                        die.v = die.omega = (0.,0.,0.)
                    error = bowl.landing_error()
                    if error:
                        self._paint_golden_dice_bowl(self.canvas, bowl, self._golden_dice_geometry)
                        self._reroll_golden_dice(error, on_complete)
                        return
                    valid_result = True
                    break
        self._paint_golden_dice_bowl(self.canvas, bowl, self._golden_dice_geometry)
        if not valid_result:
            delay = max(1, 33-round((time.monotonic()-started)*1000))
            self._queue_animation(delay, self._animate_golden_dice_roll, on_complete)
            return

        self.current_golden_dice = bowl.values()
        self._remember_golden_dice_state()
        self._golden_dice_phase = 'idle'
        total = sum(self.current_golden_dice)
        self._golden_dice_roll_ready = True
        self.golden_dice_active = total in (8,9)
        self.canvas.itemconfigure(self.golden_dice_status_text,
            text='8/9点使用加强倍数', fill='#ffd84a' if self.golden_dice_active else '#e6d9b6')
        self._update_golden_dice_board_odds()
        if callable(on_complete):
            self._queue_animation(250, on_complete)

    def _update_golden_dice_board_odds(self):
        if self.game_mode != 'goldendice':
            return
        points_spot = self.bet_spots.get(('Dice Points', None))
        if points_spot:
            self.canvas.itemconfigure(points_spot['odds_item'], text=points_spot['base_odds'])
        for bet_type, base_profit in self.GOLDEN_DICE_BASE_PROFIT_ODDS.items():
            if bet_type == 'Banker':
                base_profit = BaccaratEngine.banker_profit_odds(self._current_banker_rule())
            spot = self.bet_spots.get((bet_type, None))
            if not spot:
                continue
            if self.golden_dice_active:
                mult = int(self.golden_dice_multipliers.get(bet_type, 1))
                text = f'{format_two_decimals(base_profit * mult)}:1'
                outline, width = '#ffd42a', 4
            else:
                text = spot.get('base_odds', f'{format_two_decimals(base_profit)}:1')
                outline, width = spot.get('normal_outline', '#d5cbbd'), spot.get('normal_outline_width', 1)
            try:
                self.canvas.itemconfigure(spot.get('odds_item'), text=text, state='normal',
                                          fill='#ffd84a' if self.golden_dice_active else '#f8ecd3')
                self.canvas.itemconfigure(spot.get('rect_id'), outline=outline, width=width)
            except tk.TclError:
                pass
        self._refresh_golden_dice_ribbons()

    def _refresh_golden_dice_ribbons(self):
        if self.game_mode != 'goldendice':
            return
        self.canvas.delete('golden_dice_ribbon')
        ready = getattr(self, '_golden_dice_reels_ready', ())
        for bet in self.GOLDEN_DICE_BASE_PROFIT_ODDS:
            spot = self.bet_spots.get((bet,None))
            preview = not self._golden_dice_roll_ready and bet in ready
            multiplier = int(self.golden_dice_multipliers.get(bet,1))
            if spot and multiplier > 1 and (self.golden_dice_active or preview):
                self._draw_multiplier_ribbon(spot,multiplier)
        self.canvas.tag_raise('multiplier_ribbon')
        self.canvas.tag_raise('bet_chip_dynamic')

    def _update_2to1_multiplier_ribbon(self, result=None, *, use_revealed=False):
        """Show each two-card natural immediately, independently of its outcome."""
        if self.game_mode != '2to1':
            return
        self.canvas.delete('two_to_one_ribbon')
        for bet in ('Player','Banker'):
            spot = self.bet_spots.get((bet,None))
            if not spot:
                continue
            if use_revealed:
                hand = self.revealed_cards.get(bet, [])
            else:
                # No result means reset, even while last round's cards remain.
                hand = (result.get('player_hand' if bet == 'Player' else 'banker_hand', [])
                        if result else [])
            doubled = len(hand) == 2 and BaccaratEngine.score(hand) in (8, 9)
            odds_text = spot['base_odds']
            if doubled:
                # Display the doubled base price even on a losing/tied natural;
                # settlement still decides whether the actual wager pays.
                base = (BaccaratEngine.banker_profit_odds(self._current_banker_rule())
                        if bet == 'Banker' else 1.0)
                note = odds_text.partition(':1')[2].strip()
                odds_text = f'{base * 2:g}:1 {note}'
            self.canvas.itemconfigure(spot['odds_item'],
                text=odds_text,
                fill='#ffd84a' if doubled else '#f8ecd3')
            if doubled:
                self._draw_multiplier_ribbon(spot,2)
        self.canvas.tag_raise('multiplier_ribbon')
        self.canvas.tag_raise('bet_chip_dynamic')
        self.canvas.tag_raise('squeeze_backdrop')
        self.canvas.tag_raise('squeeze_overlay')

    def _draw_multiplier_ribbon(self, spot, multiplier):
        """Shared gold corner band for Golden Dice, Treasure and 1-pays-2."""
        x0,y0,x1,y1 = spot['bounds']
        outer = min(52., (y1-y0)-10., (x1-x0)*.4)
        inner = outer*.47
        x,y = x0+3,y0+3
        mode_tag = {'goldendice': 'golden_dice_ribbon',
                    'treasure': 'treasure_ribbon', 'xxx': 'treasure_ribbon'}.get(self.game_mode, 'two_to_one_ribbon')
        tags = ('board_dynamic','multiplier_ribbon',mode_tag,spot['tag'])
        self.canvas.create_polygon(x,y+inner, x+inner,y, x+outer,y, x,y+outer,
            fill='#ffd13c', outline='#60430b', width=.8, tags=tags)
        self.canvas.create_line(x+2,y+outer-4, x+outer-4,y+2,
            fill='#fff0a0', width=1, tags=tags)
        caption = (f'X{int(multiplier)}' if self.game_mode == '2to1'
                   else f'{int(multiplier)}X')
        # Keep exact multipliers readable even when they have several digits.
        font_size = max(7,min(12,int((outer+inner)*.8/math.sqrt(2)/(len(caption)*.67))))
        middle = (inner+outer)/4
        self.canvas.create_text(x+middle,y+middle, text=caption, angle=45,
            anchor='center', font=('Arial',-font_size,'bold'), fill='#171006', tags=tags)

    # ------------------------------------------------------- Treasure Pot mode
    def _draw_treasure_card_area(self, canvas, bounds, interactive=True, mode=None):
        """Five slots for Treasure (2+3), eight for XXX (4+4)."""
        mode = mode or self.game_mode
        x0, y0, x1, y1 = bounds
        sx, sy = (x1 - x0) / 738.0, (y1 - y0) / 234.0
        scale = min(sx, sy)

        def xy(x, y):
            return x0 + x * sx, y0 + y * sy

        canvas.create_rectangle(*xy(247, 0), *xy(491, 156), fill='#211811',
                                outline='#856a32', tags='board_dynamic')
        canvas.create_text(*xy(345, 9), text='黄金扑克', fill='#ffe69b',
            font=('Arial', -max(7, round(12 * scale)), 'bold'), tags='board_dynamic')
        if mode == 'xxx':
            positions = [xy(x, y) for y in (22, 88) for x in (254, 300, 346, 392)]
        else:
            positions = [xy(x, y) for x, y in
                         ((300, 22), (346, 22), (277, 88), (323, 88), (369, 88))]
        card_w, card_h = 44, 62
        geometry = dict(positions=positions, size=(card_w * sx, card_h * sy),
                        scale=scale, fee=xy(463, 94),
                        cards_center=xy(345, 86))
        self._draw_treasure_placeholders(canvas, geometry)
        self._draw_golden_fee_placeholder(canvas, bounds, mode=mode)
        if interactive:
            self._treasure_board_geometry = geometry
            self._treasure_round_slots = None
            self._treasure_round_positions = None
            self.treasure_pool_display = None

    def _draw_treasure_placeholders(self, canvas, geometry):
        width, height = geometry['size']
        for index, (px, py) in enumerate(geometry['positions']):
            canvas.create_rectangle(px, py, px + width, py + height,
                fill='', outline='#a78948', width=1, dash=(4, 3),
                tags=('board_dynamic', 'treasure_card_placeholder',
                      f'treasure_card_placeholder_{index}'))

    def _treasure_card_size(self):
        return tuple(max(1, round(v)) for v in self._treasure_board_geometry['size'])

    def _treasure_panel_tags(self):
        return ('treasure_panel', 'board_dynamic')

    def _weighted_sample_without_replacement(self, items, weights, count, rng):
        pool = list(items)
        pool_weights = [float(w) for w in weights]
        chosen = []
        for _ in range(min(int(count), len(pool))):
            pick = rng.choices(range(len(pool)), weights=pool_weights, k=1)[0]
            chosen.append(pool.pop(pick))
            pool_weights.pop(pick)
        return chosen

    def _prepare_treasure_round(self, on_complete=None):
        """Prepare Treasure or XXX random-card panel before the real deal."""
        faces = [(suit, rank) for suit in BaccaratEngine.SUITS for rank in BaccaratEngine.RANKS]
        rng = random.SystemRandom()

        if self.game_mode == 'xxx':
            # Probability-only randomisation: choose the count first, then sample
            # that many DISTINCT faces uniformly from the 52-face vocabulary.
            # Each chosen face independently rolls 2X, 3X, 4X, 5X, 8X or 10X.
            # No wager type, outcome, bankroll or current RTP is consulted here.
            count = rng.choices(self.XXX_COUNT_VALUES,
                                weights=self.XXX_COUNT_WEIGHTS, k=1)[0]
            chosen = rng.sample(faces, int(count))
            self.current_golden_cards = [
                (card, rng.choices(self.XXX_MULTIPLIER_VALUES,
                                   weights=self.XXX_MULTIPLIER_WEIGHTS, k=1)[0])
                for card in chosen
            ]
        else:
            chosen = rng.sample(faces, 5)
            multiplier_values = (2, 3, 5, 8)
            multiplier_weights = (55, 25, 14, 6)
            self.current_golden_cards = [
                (card, rng.choices(multiplier_values, weights=multiplier_weights, k=1)[0])
                for card in chosen
            ]

        self.current_golden_map = {tuple(card): int(mult) for card, mult in self.current_golden_cards}
        self._show_treasure_panel_shell()

        def show_cards():
            self.update_golden_bet_visuals()
            self._animate_treasure_card_fade(0, on_complete)

        if self.game_mode in ('treasure', 'xxx'):
            self._animate_golden_dice_fee_light(show_cards)
        else:
            show_cards()

    def _show_treasure_panel_shell(self):
        """Prepare the selected cards while retaining every unfilled guide."""
        self.treasure_panel_active = True
        self.canvas.delete('treasure_panel')
        self.treasure_panel_images = []
        self.treasure_animation_refs = {}
        self.treasure_panel_card_items = []
        self.treasure_panel_multiplier_items = []
        self.treasure_panel_rule_cells = {}
        count = len(self.current_golden_cards)
        slots = {
            4: (1, 2, 5, 6),
            5: (1, 2, 4, 5, 6),
            6: (1, 2, 4, 5, 6, 7),
            7: (0, 1, 2, 4, 5, 6, 7),
            8: (0, 1, 2, 3, 4, 5, 6, 7),
        }.get(count) if self.game_mode == 'xxx' else tuple(range(count))
        self._treasure_round_slots = slots
        self._treasure_round_positions = (
            [self._treasure_board_geometry['positions'][slot] for slot in slots]
            if slots is not None else None)

    def _treasure_panel_positions(self):
        positions = getattr(self, '_treasure_round_positions', None)
        return list(positions if positions is not None else self._treasure_board_geometry['positions'])

    def _treasure_small_pil(self, card):
        if Image is None:
            return None
        base = self.golden_card_pil.get(tuple(card))
        if base is None:
            base = self.external_card_pil.get(tuple(card))
        if base is None:
            return None
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        return base.convert('RGBA').resize(self._treasure_card_size(), resample)

    def _animate_treasure_card_fade(self, index, on_complete):
        if self._closing or not self.treasure_panel_active:
            return
        if index >= len(self.current_golden_cards):
            self._finish_treasure_card_layout(on_complete)
            return

        card, _mult = self.current_golden_cards[index]
        px, py = self._treasure_panel_positions()[index]
        c = self.canvas
        base = self._treasure_small_pil(card)
        card_w, card_h = self._treasure_card_size()
        card_tags = self._treasure_panel_tags()+(f'treasure_selected_card_{index}',)
        steps = 20                 # 20 * 25ms = 0.50 seconds
        frame_ms = 25

        def card_ready():
            if self._closing or not self.treasure_panel_active:
                return
            if self.game_mode in ('treasure', 'xxx'):
                slots = getattr(self, '_treasure_round_slots', None)
                slot = slots[index] if slots is not None else index
                c.delete(f'treasure_card_placeholder_{slot}')
            self._queue_animation(0, self._animate_treasure_card_fade, index + 1, on_complete)

        if base is None or ImageTk is None:
            # Pillow-less fallback: approximate the 0.5s fade with a staged
            # outline, while preserving the same sequencing duration.
            rect = c.create_rectangle(px, py, px+card_w, py+card_h, fill='#f8efd1',
                                      outline='#ffd84a', width=3,
                                      stipple='gray75', tags=card_tags)
            txt = c.create_text(px+card_w/2, py+card_h/2, text=self.card_text(card),
                                font=('Arial',max(8, round(card_w/5)),'bold'), fill='#222',
                                tags=card_tags)
            self.treasure_panel_card_items.extend((rect, txt))
            self._queue_animation(500, card_ready)
            return

        # Create one canvas image and replace its PhotoImage every frame.  The
        # references dictionary prevents Tk from garbage-collecting the active
        # frame during the animation.
        first = base.copy()
        first.putalpha(0)
        photo = ImageTk.PhotoImage(first, master=self)
        item = c.create_image(px, py, image=photo, anchor='nw', tags=card_tags)
        self.treasure_animation_refs[item] = photo
        self.treasure_panel_card_items.append(item)

        def fade_step(step=0):
            if self._closing or not self.treasure_panel_active:
                return
            alpha = max(0, min(255, int(round(255 * step / steps))))
            frame = base.copy()
            # Golden card artwork is opaque in normal use; applying a global
            # alpha gives a clean true fade without changing its RGB colours.
            frame.putalpha(alpha)
            frame_photo = ImageTk.PhotoImage(frame, master=self)
            self.treasure_animation_refs[item] = frame_photo
            try:
                c.itemconfigure(item, image=frame_photo)
            except tk.TclError:
                return
            if step < steps:
                self._queue_animation(frame_ms, fade_step, step + 1)
            else:
                # Keep a stable final image reference and only then start the
                # next card. No overlap between the per-card 0.5-second fades.
                final_photo = ImageTk.PhotoImage(base, master=self)
                self.treasure_animation_refs[item] = final_photo
                c.itemconfigure(item, image=final_photo)
                card_ready()

        fade_step(0)

    def _finish_treasure_card_layout(self, on_complete):
        """After all cards load, clear unused guides and centre a row of 3."""
        count = len(self.current_golden_cards)
        if self.game_mode == 'xxx':
            self.canvas.delete('treasure_card_placeholder')
        if self.game_mode != 'xxx' or count not in (5, 7):
            self._queue_animation(20, self._animate_treasure_multiplier_drop, on_complete)
            return
        indices = (2, 3, 4) if count == 5 else (0, 1, 2)
        initial = self._treasure_panel_positions()
        fixed = self._treasure_board_geometry['positions']
        offset = (fixed[1][0]-fixed[0][0])/2

        def centre(step=0):
            if self._closing or not self.treasure_panel_active:
                return
            t = step/8.0
            eased = t*t*(3-2*t)
            for index in indices:
                x, y = initial[index]
                target_x = x+offset*eased
                old_x, _old_y = self._treasure_round_positions[index]
                self.canvas.move(f'treasure_selected_card_{index}', target_x-old_x, 0)
                self._treasure_round_positions[index] = (target_x, y)
            if step < 8:
                self._queue_animation(16, centre, step+1)
            else:
                self._queue_animation(20, self._animate_treasure_multiplier_drop, on_complete)
        centre()

    def _animate_treasure_multiplier_drop(self, on_complete):
        """Drop all current multiplier badges simultaneously over 0.5 seconds."""
        if self._closing or not self.treasure_panel_active:
            return
        c = self.canvas
        positions = self._treasure_panel_positions()
        self.treasure_panel_multiplier_items = []
        card_w, _card_h = self._treasure_card_size()
        compact = self.game_mode in ('treasure', 'xxx')
        radius = max(7, round(card_w * .23)) if compact else 14
        font_size = max(6, round(card_w * .19)) if compact else 9
        badge_inset = radius if compact else 8
        finals = []
        for (_card, mult), (px, py) in zip(self.current_golden_cards, positions):
            cx = px + card_w - badge_inset
            final_y = py + (radius if compact else 7)
            start_y = final_y - radius if compact else 72
            oval = c.create_oval(cx-radius, start_y-radius, cx+radius, start_y+radius,
                                 fill='#ffffff', outline='#d6d6d6', width=2,
                                 tags=self._treasure_panel_tags())
            text = c.create_text(cx, start_y, text=f'{int(mult)}X', font=('Arial',font_size,'bold'),
                                 fill='#000000', tags=self._treasure_panel_tags())
            self.treasure_panel_multiplier_items.extend((oval, text))
            finals.append((oval, text, cx, start_y, final_y))
        c.tag_raise('treasure_panel')

        steps = 20                 # 20 * 25ms = 0.50 seconds
        frame_ms = 25
        def drop_step(step=0):
            if self._closing or not self.treasure_panel_active:
                return
            ratio = min(1.0, step / float(steps))
            # Ease-out cubic: fast initial fall, gentle landing.
            eased = 1.0 - (1.0 - ratio) ** 3
            for oval, text, cx, start_y, final_y in finals:
                cy = start_y + (final_y - start_y) * eased
                c.coords(oval, cx-radius, cy-radius, cx+radius, cy+radius)
                c.coords(text, cx, cy)
            if step < steps:
                self._queue_animation(frame_ms, drop_step, step + 1)
            elif callable(on_complete):
                # The very first Player card may only be dealt after all current
                # multiplier badges have landed.
                self._queue_animation(0, on_complete)
        drop_step(0)

    def _hide_treasure_panel(self):
        self.treasure_panel_active = False
        self.canvas.delete('treasure_panel')
        self.treasure_panel_images = []
        self.treasure_animation_refs = {}
        self.treasure_panel_card_items = []
        self.treasure_panel_multiplier_items = []
        self.treasure_panel_rule_cells = {}
        self._treasure_round_slots = None
        self._treasure_round_positions = None
        self.canvas.delete('treasure_card_placeholder')
        self._draw_treasure_placeholders(self.canvas, self._treasure_board_geometry)

    def _gold_multiplier_for_revealed(self, bet_type):
        mapping = self.current_golden_map
        if self.game_mode in ('treasure', 'xxx'):
            # A face-up card activates only after its light has been injected.
            # Slot keys keep repeated faces and simultaneous squeeze returns distinct.
            multiplier = 1
            for (hand, index), card in self._golden_activated_slots.items():
                applies = (bet_type == 'Tie' or bet_type == hand
                           or (bet_type == f'Pair {hand}' and index < 2))
                if applies:
                    multiplier *= int(mapping.get(tuple(card), 1))
            return max(1, multiplier)
        p = list(self.revealed_cards.get('Player', []))
        b = list(self.revealed_cards.get('Banker', []))
        if bet_type == 'Player': cards = p
        elif bet_type == 'Banker': cards = b
        elif bet_type == 'Tie': cards = p + b
        elif bet_type == 'Pair Player': cards = p[:2]
        elif bet_type == 'Pair Banker': cards = b[:2]
        else: return 1
        m = 1
        for card in cards:
            m *= int(mapping.get(tuple(card), 1))
        return max(1, m)

    def _base_profit_odds_for_treasure(self, bet_type):
        if bet_type == 'Banker':
            return BaccaratEngine.banker_profit_odds(self._current_banker_rule())
        if self.game_mode == 'xxx':
            return {'Player':1.0, 'Tie':2.85,
                    'Pair Player':8.0, 'Pair Banker':8.0}.get(bet_type)
        return {'Player':1.0, 'Tie':5.0,
                'Pair Player':9.0, 'Pair Banker':9.0}.get(bet_type)

    def _effective_golden_multiplier(self, bet_type, raw_multiplier):
        # XXX no longer applies a hidden RTP scale to payout odds.  The integer
        # multiplier shown on the falling golden badge is the multiplier used
        # by both the betting-area odds and settlement calculation.
        _ = bet_type
        return float(raw_multiplier)

    def update_golden_bet_visuals(self):
        """Both card modes use the same gold upper-left multiplier ribbons."""
        self.canvas.delete('golden_bet_dynamic')
        if self.game_mode in ('treasure', 'xxx'):
            self._update_treasure_board_odds()
        elif self.game_mode == 'goldendice':
            self._update_golden_dice_board_odds()

    def _update_treasure_board_odds(self):
        """Use Golden Dice's upper-left bands with Treasure's original odds."""
        self.canvas.delete('treasure_ribbon')
        for bet in ('Player', 'Banker', 'Tie', 'Pair Player', 'Pair Banker'):
            spot = self.bet_spots.get((bet, None))
            if not spot:
                continue
            multiplier = self._gold_multiplier_for_revealed(bet)
            base = self._base_profit_odds_for_treasure(bet)
            price = round_two_decimals_value(base * multiplier)
            self.canvas.itemconfigure(spot['odds_item'], state='normal',
                text=f'{format_two_decimals(price)}:1' if multiplier > 1 else spot['base_odds'],
                fill='#ffd84a' if multiplier > 1 else '#f8ecd3')
            if multiplier > 1:
                self._draw_multiplier_ribbon(spot, multiplier)
        self.canvas.tag_raise('multiplier_ribbon')
        self.canvas.tag_raise('bet_chip_dynamic')
        self.canvas.tag_raise('squeeze_backdrop')
        self.canvas.tag_raise('squeeze_overlay')

    # ---------------------------------------------------------- shoe / cut / burn
    def _show_cut_dialog(self, second=False):
        """Cut B before A, move black to the tail, then reinsert yellow."""
        dialog = tk.Toplevel(self.winfo_toplevel())
        self._cut_dialog = dialog
        dialog.title('切牌')
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.configure(bg='#0b4038')
        self.update_idletasks()
        width, height = BaccaratCutScene.WIDTH, BaccaratCutScene.HEIGHT+68
        x = max(0, self.winfo_rootx()+(self.winfo_width()-width)//2)
        y = max(0, self.winfo_rooty()+(self.winfo_height()-height)//2)
        dialog.geometry(f'{width}x{height}+{x}+{y}')
        cv = tk.Canvas(dialog, width=width, height=BaccaratCutScene.HEIGHT,
                       bg='#0b4038', highlightthickness=0, cursor='arrow')
        cv.pack(fill=tk.X, side=tk.TOP)
        scene = BaccaratCutScene(getattr(self, 'external_back_pil', None))
        rng = random.SystemRandom()
        selected = {'value': rng.randint(120, 300)}
        state = {'running': False, 'photo': None, 'image': None, 'closed': False,
                 'dragging': False, 'drag_x': 0, 'drag_value': None, 'confirmed': None}
        pending = set()
        result = [None]
        total = float(scene.CARD_COUNT)
        tail_count = self._pending_cut_threshold or self.engine.cut_threshold
        marker_final = scene.LENGTH*(total-tail_count)/total

        def schedule(delay, callback):
            holder = {}
            def run():
                pending.discard(holder.get('id'))
                if not state['closed'] and not self._closing:
                    callback()
            holder['id'] = dialog.after(delay, run)
            pending.add(holder['id'])

        def close_dialog():
            if state['closed']:
                return
            state['closed'] = True
            for after_id in list(pending):
                try:
                    dialog.after_cancel(after_id)
                except tk.TclError:
                    pass
            pending.clear()
            try:
                dialog.grab_release()
                dialog.destroy()
            except tk.TclError:
                pass
            if self._cut_dialog is dialog:
                self._cut_dialog = None

        # The exit path also cancels this dialog's own timers before destruction.
        dialog._close_cut_scene = close_dialog

        def polygon(points, fill, outline='#aaa48e'):
            cv.create_polygon(*[v for point in points for v in point],
                              fill=fill, outline=outline, tags='cut_scene_fallback')

        def render(**pose):
            split = scene.LENGTH*selected['value']/total
            frame = scene.render(split, **pose)
            if frame is not None and ImageTk is not None:
                state['photo'] = ImageTk.PhotoImage(frame, master=cv)
                if state['image'] is None:
                    state['image'] = cv.create_image(0, 0, anchor='nw', image=state['photo'])
                    cv.tag_lower(state['image'])
                else:
                    cv.itemconfigure(state['image'], image=state['photo'])
            else:
                # Share separator geometry with the Pillow path.
                cv.delete('cut_scene_fallback')
                p = scene.project
                a, ay, az = pose.get('a_x', 0), pose.get('a_y', 0), pose.get('a_z', 0)
                b, by, bz = pose.get('b_x', split), pose.get('b_y', 0), pose.get('b_z', 0)
                d, h = scene.DEPTH, scene.CARD_H
                parts = ((a, ay, split, az), (b, by, scene.LENGTH-split, bz))
                black_x, black_y, black_z = (pose.get('black_x', scene.LENGTH+2),
                                        pose.get('black_y', 0), pose.get('black_z', 0))
                mx, my, raised = pose.get('marker_x', split), pose.get('marker_y', 0), pose.get('marker_raise', 32)
                shift = pose.get('holder_shift', 0)
                left = pose.get('left_hand', scene.holder_contact(shift, 0))
                right = pose.get('right_hand', scene.holder_contact(shift, 1))
                grips = (pose.get('left_grip', 0), pose.get('right_grip', 0))
                openings = (pose.get('left_open', 0), pose.get('right_open', 0))
                rigs = [scene.hand_rig(side, world, grips[side], openings[side])
                        for side, world in enumerate((left, right))]
                for rail in scene.holder_rails(shift):
                    polygon(rail, '', '#b7d7d8')

                def packet(xx, yy, length, zz):
                    polygon([p(xx, yy, zz), p(xx+length, yy, zz),
                             p(xx+length, yy, zz+h), p(xx, yy, zz+h)], '#e8e3d5')
                    polygon([p(xx, yy, zz+h), p(xx+length, yy, zz+h),
                             p(xx+length, yy+d, zz+h), p(xx, yy+d, zz+h)], '#faf6e8')
                    polygon([p(xx, yy+d, zz+h), p(xx, yy, zz+h),
                             p(xx, yy, zz), p(xx, yy+d, zz)], '#f5eee1')
                    for i in range(1, max(2, int(length/4))):
                        edge = xx+i*4
                        cv.create_line(*p(edge, yy, zz), *p(edge, yy, zz+h),
                                       fill='#b8b6a8', tags='cut_scene_fallback')

                def separator(xx, yy, zz, yellow=False):
                    for corners in scene.separator_quads(xx, yy, zz, parts):
                        color = '#eccd42' if yellow else '#1e2124'
                        polygon(corners, color, color)

                def hand(side):
                    rig = rigs[side]
                    for points in scene.arm_polygons(rig):
                        polygon(points, '#182a2d', '#263b3c')
                    for detail in scene.sleeve_details(rig):
                        cv.create_line(*[v for p in detail for v in p], fill='#213639',
                                       width=1, tags='cut_scene_fallback')
                    polygon(scene.fallback_hand(rigs[side]), '#c68f73', '#825c4c')

                objects = [(yy+.32*(xx+length/2)-zz*.5,
                            lambda part=part: packet(*part))
                           for part in parts for xx, yy, length, zz in (part,)]
                objects.append((-1000+.001*(black_y+.32*black_x-black_z*.5),
                                lambda: separator(black_x, black_y, black_z)))
                objects.append((-1000+.001*(my+.32*mx-(raised-8)*.5),
                                lambda: separator(mx, my, raised-8, True)))
                for side in (0, 1):
                    objects.append((-1002-side*.01, lambda side=side: hand(side)))
                for _, paint in sorted(objects, key=lambda item: item[0], reverse=True):
                    paint()
            cv.tag_raise('cut_prompt')

        render()
        prompt = cv.create_text(scene.WIDTH/2, 26, text='拖动黄色卡片选择位置，确认后由庄家切牌',
                                font=('微软雅黑', 16, 'bold'), fill='#fff0b8', tags='cut_prompt')
        for limit in (scene.CUT_MIN, scene.CUT_MAX):
            world_x = scene.LENGTH*limit/total
            cv.create_line(*scene.project(world_x, 0, scene.CARD_H+1),
                           *scene.project(world_x, scene.DEPTH, scene.CARD_H+1),
                           fill='#c89667', width=2, dash=(4, 3), tags='cut_bounds')

        def select(value):
            selected['value'] = max(scene.CUT_MIN, min(scene.CUT_MAX, round(value)))
            render()

        def start_drag(event):
            if state['running']:
                return 'break'
            state['dragging'] = False
            split = scene.LENGTH*selected['value']/total
            tab = scene.separator_quads(split, 0, 32-8,
                                        ((0, 0, split, 0), (split, 0, scene.LENGTH-split, 0)))
            if not any(scene.contains_point(face, event.x, event.y) for face in tab):
                return 'break'
            # Keep the grabbed point attached to the cursor. Neither dealer
            # hand follows the pointer, and pressing the deck does not cut it.
            state.update(dragging=True, drag_x=event.x, drag_value=selected['value'])
            cv.configure(cursor='sb_h_double_arrow')
            return 'break'

        def move_cut(event):
            if not state['running'] and state['dragging']:
                select(state['drag_value']+(event.x-state['drag_x'])/scene.LENGTH*total)
            return 'break'

        def stop_drag(_event=None):
            state['dragging'] = False
            cv.configure(cursor='arrow')
            return 'break'

        def hover(event):
            if state['running'] or state['dragging']:
                return
            split = scene.LENGTH*selected['value']/total
            tab = scene.separator_quads(split, 0, 24,
                                        ((0, 0, split, 0), (split, 0, scene.LENGTH-split, 0)))
            over_tab = any(scene.contains_point(face, event.x, event.y) for face in tab)
            cv.configure(cursor='sb_h_double_arrow' if over_tab else 'arrow')

        def finish():
            result[0] = state['confirmed']
            schedule(320, close_dialog)

        def begin(value=None):
            if state['running'] or self._closing:
                return 'break'
            if value is not None:
                selected['value'] = max(scene.CUT_MIN, min(scene.CUT_MAX, int(value)))
            state.update(running=True, dragging=False, confirmed=int(selected['value']))
            cv.itemconfigure(prompt, text='稍等，很快就完成了')
            confirm_btn.config(state=tk.DISABLED)
            cv.configure(cursor='arrow')
            cv.delete('cut_bounds')
            split = scene.LENGTH*state['confirmed']/total

            def phase(index=0):
                if index == len(scene.PHASES):
                    finish()
                    return
                _, duration = scene.PHASES[index]
                started = time.monotonic()
                def frame():
                    frame_start = time.monotonic()
                    progress = min(1.0, (frame_start-started)/duration)
                    render(**scene.pose(split, index, progress, marker_final))
                    if progress < 1:
                        work_ms = (time.monotonic()-frame_start)*1000
                        schedule(max(1, round(1000/30-work_ms)), frame)
                    else:
                        phase(index+1)
                frame()
            phase()
            return 'break'

        def random_confirm(_event=None):
            return begin(rng.randint(scene.CUT_MIN, scene.CUT_MAX))

        cv.bind('<Button-1>', start_drag)
        cv.bind('<B1-Motion>', move_cut)
        cv.bind('<ButtonRelease-1>', stop_drag)
        cv.bind('<Motion>', hover)
        confirm_btn = tk.Button(dialog, text='确定切牌', command=begin, width=18,
                                font=('微软雅黑', 13, 'bold'), bg='#d8bd4b', fg='#15110d',
                                activebackground='#ead56f', relief=tk.FLAT, bd=0, pady=8)
        confirm_btn.pack(pady=(4, 12))
        dialog.bind('<Return>', random_confirm)
        dialog.bind('<KP_Enter>', random_confirm)
        schedule(20, dialog.focus_force)
        dialog.protocol('WM_DELETE_WINDOW', begin)
        try:
            self.wait_window(dialog)
        finally:
            close_dialog()
        return int(result[0] if result[0] is not None else
                   state['confirmed'] if state['confirmed'] is not None else selected['value'])


    CUT_NOTICE_HOLD_MS = 3000
    CUT_NOTICE_FADE_MS = 360

    def _cut_card_notice_due(self):
        offset = self._round_cut_card_offset
        return (self.game_mode not in BaccaratEngine.SPECIAL_MODES and offset is not None
                and not self._cut_notice_seen
                and self._round_dealt_card_count >= offset)

    def _clear_cut_card_notice(self):
        popup = self._cut_notice_popup
        self._cut_notice_popup = None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass
        self.canvas.delete('cut_card_notice')
        self.canvas.delete('cut_card_popup')
        self._cut_notice_active = False

    def _show_cut_card_notice(self, on_complete):
        """Withdraw marker, fade in, hold 3s, fade out, slide down, resume.

        The continuation is the only way back into the paused deal, so neither
        settlement nor squeeze bindings can run while this sequence is active.
        """
        if self._closing or self._cut_notice_active:
            return
        self._cut_notice_seen = True
        self._cut_notice_active = True
        self.accept_bets = False
        self.update_control_states()
        c = self.canvas
        previous_phase = c.itemcget(self.animation_phase_text, 'text')
        c.itemconfigure(self.animation_phase_text, text='取出黄色切牌')
        x0, y0, x1, y1 = self.animation_panel
        centre_x, centre_y = (x0+x1)/2, (y0+y1)/2+10
        tag = ('cut_card_notice', 'animation')
        shadow = c.create_oval(0, 0, 0, 0, fill='#090f13', outline='', tags=tag)
        side = c.create_polygon(0, 0, 0, 0, fill='#a77f0b', outline='#84650b', tags=tag)
        face = c.create_polygon(0, 0, 0, 0, fill='#f4d640', outline='#b18c18', width=2, tags=tag)
        shine = c.create_line(0, 0, 0, 0, fill='#fff4a3', width=3, tags=tag)
        inner = c.create_polygon(0, 0, 0, 0, fill='', outline='#dfb727', width=1, tags=tag)

        def paint(cy, amount=1.0):
            half_w, half_h = 51*(.32+.68*amount), 76
            skew = 13*(1-amount)+4
            points = [(centre_x-half_w, cy-half_h+skew),
                      (centre_x+half_w, cy-half_h),
                      (centre_x+half_w, cy+half_h-skew),
                      (centre_x-half_w, cy+half_h)]
            flatten = lambda pts: [v for p in pts for v in p]
            c.coords(side, *flatten([(x+5, y+4) for x, y in points]))
            c.coords(face, *flatten(points))
            c.coords(shine, *flatten(points[:2]))
            c.coords(inner, *flatten([(centre_x+(x-centre_x)*.87,
                                       cy+(y-cy)*.90) for x, y in points]))
            c.coords(shadow, centre_x-half_w-6, cy+half_h+7,
                     centre_x+half_w+12, cy+half_h+20)

        def animate(duration, callback, completed):
            steps = max(1, int(duration/16))
            def frame(step=0):
                if self._closing or not self._cut_notice_active:
                    return
                callback(BaccaratCutScene.ease(step/steps))
                if step < steps:
                    self._queue_animation(round(duration/steps), frame, step+1)
                else:
                    completed()
            frame()

        def resume():
            if self._closing:
                return
            self._clear_cut_card_notice()
            c.itemconfigure(self.animation_phase_text, text=previous_phase)
            on_complete()

        def slide_away():
            if self._closing:
                return
            popup = self._cut_notice_popup
            self._cut_notice_popup = None
            if popup is not None:
                popup.destroy()
            c.delete('cut_card_popup')
            animate(560, lambda t: paint(centre_y+(self.HEIGHT+100-centre_y)*t), resume)

        def show_popup():
            if self._closing:
                return
            popup = tk.Toplevel(self.winfo_toplevel())
            self._cut_notice_popup = popup
            popup.withdraw()
            popup.overrideredirect(True)
            popup.transient(self.winfo_toplevel())
            popup.configure(bg='#d2b766')
            tk.Label(popup, text='下轮更换牌靴', font=('微软雅黑', 17, 'bold'),
                     bg='#163c37', fg='#fff0b8', padx=24, pady=17).pack(padx=1, pady=1)
            popup.update_idletasks()
            pw, ph = popup.winfo_reqwidth(), popup.winfo_reqheight()
            px = int(c.winfo_rootx()+centre_x-pw/2)
            py = int(c.winfo_rooty()+centre_y-ph/2)
            popup.geometry(f'{pw}x{ph}+{max(0, px)}+{max(0, py)}')
            native_alpha = True
            try:
                popup.attributes('-alpha', 0.0)
            except tk.TclError:
                native_alpha = False
            if native_alpha:
                popup.deiconify()
                popup.lift()
            else:
                # Some Tk window managers lack per-window opacity.
                popup.destroy()
                self._cut_notice_popup = None
                c.create_rectangle(centre_x-145, centre_y-34, centre_x+145, centre_y+34,
                                   fill='#f4d640', outline='', tags='cut_card_popup')
                c.create_text(centre_x, centre_y, text='下轮更换牌靴',
                              font=('微软雅黑', 17, 'bold'), fill='#f4d640',
                              tags=('cut_card_popup', 'cut_notice_text'))

            def opacity(amount):
                if native_alpha:
                    popup.attributes('-alpha', amount)
                else:
                    # A color fade keeps the fallback nonblocking and readable.
                    def blend(a, b):
                        av, bv = c.winfo_rgb(a), c.winfo_rgb(b)
                        return '#'+''.join(f'{round((x+(y-x)*amount)/257):02x}'
                                           for x, y in zip(av, bv))
                    plate = c.find_withtag('cut_card_popup')[0]
                    c.itemconfigure(plate, fill=blend('#f4d640', '#163c37'))
                    c.itemconfigure('cut_notice_text', fill=blend('#f4d640', '#fff0b8'))

            def fade_out():
                animate(self.CUT_NOTICE_FADE_MS, lambda t: opacity(1-t), slide_away)

            # The full three seconds start AFTER the popup is fully visible.
            animate(self.CUT_NOTICE_FADE_MS, opacity,
                    lambda: self._queue_animation(self.CUT_NOTICE_HOLD_MS, fade_out))

        # Use the same centre-top shoe origin as normal card entrances.
        paint(-160, 0)
        animate(560, lambda t: paint(-160+(centre_y+160)*t, t), show_popup)


    def start_new_shoe_cut(self, second=False):
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            return
        if self._mode_transition is not None:
            self._mode_pending_cut = bool(second)
            return
        if self._closing or self.animation_running or self.settlement_running:
            return
        self.accept_bets = False
        self.animation_running = True
        self.update_control_states()
        # The animation and the actual marker must use the SAME tail position.
        self._pending_cut_threshold = random.SystemRandom().randint(50, 70)
        cut_position = self._show_cut_dialog(second)
        if self._closing:
            return
        # Cutting a new shoe completely resets the two temporary sections in
        # Baccarat.json, while lifetime statistic_data is preserved.
        self.clear_shoe_temp_sections()
        self.engine.new_shoe()
        self.engine.cut_shoe(cut_position, self._pending_cut_threshold)
        self._pending_cut_threshold = None
        self._cut_notice_seen = False
        self._round_cut_card_offset = None
        self._round_dealt_card_count = 0
        self.save_temp_data(burn_complete=False)
        self.clear_card_display()
        self.canvas.itemconfigure(self.animation_phase_text, text='切牌完成 · 烧牌')
        self._start_initial_burn_animation()

    def _burn_card_position(self, total, index=0):
        """Keep the face-up indicator and fanned backs inside the card panel."""
        x0, y0, x1, _y1 = self.animation_panel
        spread = 20
        width = 224 + max(0, total - 1) * spread
        left = (x0 + x1 - width) / 2
        return (left if index == 0 else left + 124 + (index - 1) * spread,
                y0 + 82)

    def _start_initial_burn_animation(self):
        if self.engine.remaining_cards() <= 0:
            self._finish_initial_burn()
            return
        first_card = self.engine.draw_card()
        self.save_temp_data(burn_complete=False)
        burn_value = min(10, BaccaratEngine.card_value(first_card) or 10)
        target_x, target_y = self._burn_card_position(burn_value)
        start_x = (self.GAME_X0 + self.GAME_X1) / 2 - 50
        back = self._back_photo(False)
        card_id = self.canvas.create_image(start_x, -150,
                                           image=back, anchor='nw',
                                           tags=('burn_card', 'animation'))
        self.card_item_ids.append(card_id)
        info = ('Burn', card_id, 0)
        def arrive():
            self._flip_burn_card(info, first_card, 0)
        def move(step=0):
            ratio = min(1.0, step / 30.0)
            x = start_x + (target_x - start_x) * ratio
            y = -150 + (target_y + 150) * ratio
            self.canvas.coords(card_id, x, y)
            if step < 30:
                self._queue_animation(10, move, step + 1)
            else:
                arrive()
        move()

    def _flip_burn_card(self, card_info, card, step=0):
        _hand, card_id, _index = card_info
        steps = 12
        # 10/J/Q/K burn 10, A burns 1, numbered cards burn their face value.
        burn_value = min(10, BaccaratEngine.card_value(card) or 10)
        base_x, base_y = self._burn_card_position(burn_value)
        if step > steps:
            image = self._face_photo(card, False)
            if image is not None:
                self.canvas.itemconfigure(card_id, image=image)
            self.canvas.coords(card_id, base_x, base_y)
            self._temp_flip_images.pop(card_id, None)
            self._queue_animation(500, self._burn_back_cards, burn_value, 0, [])
            return
        half = steps // 2
        if step <= half:
            ratio, use_back = 1 - step / float(half), True
        else:
            ratio, use_back = (step - half) / float(half), False
        width = max(1, int(100 * ratio))
        image = self._create_scaled_flip_image(card, width, 140, use_back=use_back, rotated=False)
        if image is not None:
            self._temp_flip_images[card_id] = image
            self.canvas.itemconfigure(card_id, image=image)
            self.canvas.coords(card_id, base_x + (100 - width) / 2, base_y)
        self._queue_animation(20, self._flip_burn_card, card_info, card, step + 1)

    def _burn_back_cards(self, total, index, ids):
        if index >= total or self.engine.remaining_cards() <= 0:
            self._queue_animation(700, self._finish_initial_burn)
            return
        self.engine.draw_card()
        self.save_temp_data(burn_complete=False)
        start_x = (self.GAME_X0 + self.GAME_X1) / 2 - 50
        start_y = -150
        target_x, target_y = self._burn_card_position(total, index + 1)
        card_id = self.canvas.create_image(start_x, start_y, image=self._back_photo(False),
                                           anchor='nw', tags=('burn_card', 'animation'))
        self.card_item_ids.append(card_id)
        ids.append(card_id)
        def move(step=0):
            ratio = min(1.0, step / 24.0)
            self.canvas.coords(card_id,
                               start_x + (target_x - start_x) * ratio,
                               start_y + (target_y - start_y) * ratio)
            if step < 24:
                self._queue_animation(10, move, step + 1)
            else:
                self._queue_animation(100, self._burn_back_cards, total, index + 1, ids)
        move()

    def _finish_initial_burn(self):
        self.canvas.delete('burn_card')
        self.card_item_ids = [item for item in self.card_item_ids
                              if self.canvas.type(item)]
        self.clear_card_display()
        self.save_temp_data(burn_complete=True)
        self.shoe_resumed = True
        self.animation_running = False
        self.accept_bets = True
        self.canvas.itemconfigure(self.animation_phase_text, text='百家乐 BACCARAT')
        self.update_display()

    # ------------------------------------------------------------ dealing/settle
    def handle_enter_deal(self, _event=None):
        button = self.control_buttons.get(getattr(self, 'deal_button', None))
        if button and button['enabled']:
            button['command']()
        return 'break'

    def deal_cards(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        if (self.game_mode == 'goldendice' and self.bet_state.total_at_risk() > 0
                and not self._golden_dice_has_base_bet()):
            return
        if (self.game_mode in ('treasure', 'xxx') and self.bet_state.total_at_risk() > 0
                and not self._has_fee_bearing_bet()):
            return
        if self.engine.needs_shuffle():
            outstanding = self.bet_state.clear_all()
            fee_refund = sum(float(v) for v in self.bet_fee_state.values())
            self.bet_fee_state.clear()
            self._cancel_fee_visuals()
            self.pending_bet_visual_amounts.clear()
            if outstanding > 0 or fee_refund > 0:
                self.balance += outstanding + fee_refund
                if fee_refund > 0:
                    self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee_refund)
            self.update_display()
            self.start_new_shoe_cut(True)
            return

        self.accept_bets = False
        self.animation_running = True
        self.pending_bet_visual_amounts.clear()
        current_bets = self.snapshot_bets()
        if current_bets:
            self.last_round_bets = current_bets
        self.undo_stack.clear()
        self.pre_deal_bets = copy.deepcopy(self.bet_state.bets)
        self._round_banker_rule = self._current_banker_rule()
        # Only Player/Banker main wagers grant control of that side. Snapshot
        # once, so fees, side bets and later settlement cannot change control.
        self._squeeze_hands = self._squeeze_wager_hands(self.pre_deal_bets)
        self._round_squeeze_enabled = bool(
            self.squeeze_enabled.get() and self._squeeze_hands
            and Image is not None and ImageTk is not None)
        self.pre_deal_fee_total = sum(float(v) for v in self.bet_fee_state.values())
        self.bet_fee_state.clear()
        self.clear_card_display()
        self.current_result = None
        self.result_panel_flash_winner = None
        self.restore_result_panel_colors()
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')
        self.update_control_states()

        if self.game_mode == 'goldendice':
            self.canvas.itemconfigure(self.animation_phase_text, text='黄金骰子…')
            self._prepare_golden_dice_round(on_complete=self._begin_actual_round_deal)
        elif self.game_mode in ('treasure', 'xxx'):
            phase = '聚宝盆…' if self.game_mode == 'treasure' else 'XXX…'
            self.canvas.itemconfigure(self.animation_phase_text, text=phase)
            self._prepare_treasure_round(on_complete=self._begin_actual_round_deal)
        else:
            self.current_golden_cards = []
            self.current_golden_map = {}
            self._begin_actual_round_deal()

    def _begin_actual_round_deal(self):
        if self._closing:
            return
        start_index = getattr(self.engine, 'current_index', 0)
        try:
            self.current_result = self.engine.deal_round()
        except Exception as exc:
            if self.game_mode not in BaccaratEngine.SPECIAL_MODES:
                raise
            # A missing/invalid project shuffler must leave queued stakes
            # available to retry or clear, rather than lock the betting UI.
            self.animation_running = False
            self.accept_bets = True
            self.pre_deal_bets = None
            title = '固定牌发牌失败' if self.game_mode in BaccaratEngine.ALWAYS_MODES else '单副版洗牌失败'
            self.canvas.itemconfigure(self.animation_phase_text, text=title)
            self.update_display()
            messagebox.showerror(title, str(exc), parent=self.winfo_toplevel())
            return
        # The engine resolves a whole hand at once. Its marker is visualized
        # only when the corresponding physical card entrance is reached.
        self._round_dealt_card_count = 0
        self._cut_notice_seen = False
        self._round_cut_card_offset = None
        if self.game_mode not in BaccaratEngine.SPECIAL_MODES:
            marker = len(self.engine.deck)-self.engine.cut_threshold
            if start_index <= marker <= self.engine.current_index:
                self._round_cut_card_offset = marker-start_index
        self.current_result['_banker_rule'] = self._round_banker_rule
        if self.game_mode in ('treasure', 'xxx'):
            self.current_result['_golden_multiplier_map'] = dict(self.current_golden_map)
            self.current_result['golden_selection_count'] = len(self.current_golden_cards)
            self.current_result['golden_cards'] = [
                {'card': list(card), 'multiplier': int(mult)}
                for card, mult in self.current_golden_cards
            ]
        elif self.game_mode == 'goldendice':
            self.current_result['_golden_dice'] = list(self.current_golden_dice)
            self.current_result['_golden_dice_total'] = int(sum(self.current_golden_dice))
            self.current_result['_golden_dice_active'] = bool(self.golden_dice_active)
            self.current_result['_golden_dice_multipliers'] = dict(self.golden_dice_multipliers)
        self.save_temp_data()
        self.canvas.itemconfigure(self.animation_phase_text, text='发牌中…')

        # Preserve V17/V18's physical table order: Player-left, Banker-left,
        # Player-right, Banker-right, with each entrance + flip fully complete
        # before the next card. Treasure/XXX reaches here only after all current
        # multiplier badges have landed.
        if self._round_squeeze_enabled:
            self.initial_card_ids = []
            sequence = (('Player', 1), ('Banker', 0), ('Player', 0), ('Banker', 1))
            if self.game_mode in BaccaratEngine.ALWAYS_MODES:
                self._draw_fixed_banker_card()
                sequence = (('Player', 1), ('Player', 0), ('Banker', 1))
            self._deal_squeeze_batch(
                sequence,
                self._process_squeeze_extra_cards)
        else:
            self._deal_initial_sequence_original()

    def _queue_animation(self, delay, callback, *args):
        after_id = self.after(delay, callback, *args)
        self.animation_after_ids.append(after_id)
        return after_id

    def _back_photo(self, rotated=False):
        if self.game_mode in BaccaratEngine.ALWAYS_MODES:
            if not rotated:
                return self.poker2_back_image
            if self._poker2_rotated_back_image is None and self.poker2_back_pil is not None and ImageTk is not None:
                self._poker2_rotated_back_image = ImageTk.PhotoImage(
                    self.poker2_back_pil.rotate(90, expand=True), master=self)
            return self._poker2_rotated_back_image or self.poker2_back_image
        if not rotated:
            return self.external_back_image
        image = getattr(self, '_rotated_back_image', None)
        if image is None and self.external_back_pil is not None and ImageTk is not None:
            self._rotated_back_image = ImageTk.PhotoImage(
                self.external_back_pil.rotate(90, expand=True), master=self)
            image = self._rotated_back_image
        return image or self.external_back_image

    def _card_face_turn(self, hand_type, index):
        """Keep a slot's face orientation stable, including after a squeeze return."""
        if self.game_mode in BaccaratEngine.ALWAYS_MODES and (hand_type, index) == ('Banker', 0):
            return 0
        turns = getattr(self, '_card_face_turns', None)
        if turns is None:
            turns = self._card_face_turns = {}
        key = (hand_type, index)
        if key not in turns:
            turns[key] = random.SystemRandom().choice((0, 180))
        return turns[key]

    def _face_pil(self, card, hand_type=None, index=None, use_golden=True):
        card = tuple(card)
        if self.game_mode in BaccaratEngine.ALWAYS_MODES:
            base = (self.always_card_pil.get(self.game_mode) if (hand_type, index) == ('Banker', 0)
                    else self.poker2_card_pil.get(card))
            if base is not None and hand_type is not None and index is not None and self._card_face_turn(hand_type, index):
                base = base.rotate(180)
            return base
        base = (self.golden_card_pil.get(card)
                if use_golden and self._is_current_golden(card) else None)
        if base is None:
            base = getattr(self, 'external_card_pil', {}).get(card)
        if base is not None and hand_type is not None and index is not None:
            if self._card_face_turn(hand_type, index):
                base = base.rotate(180)
        return base

    def _face_photo(self, card, rotated=False, hand_type=None, index=None,
                    use_golden=True):
        card = tuple(card)
        if self.game_mode in BaccaratEngine.ALWAYS_MODES:
            if (hand_type, index) == ('Banker', 0) and not rotated:
                return self.always_card_images.get(self.game_mode)
            if hand_type is not None and index is not None and self._card_face_turn(hand_type, index):
                key = (self.game_mode, card, rotated, 180)
                if key not in self._turned_card_images:
                    base = self._face_pil(card, hand_type, index)
                    if base is not None:
                        if rotated:
                            base = base.rotate(90, expand=True)
                        self._turned_card_images[key] = ImageTk.PhotoImage(base, master=self)
                return self._turned_card_images.get(key)
            return (self.poker2_card_images_rotated.get(card) if rotated else self.poker2_card_images.get(card))
        is_golden = use_golden and self._is_current_golden(card)
        if hand_type is not None and index is not None:
            turn = self._card_face_turn(hand_type, index)
            if turn and ImageTk is not None:
                base = self._face_pil(card, hand_type, index, use_golden=use_golden)
                if base is not None:
                    cache = getattr(self, '_turned_card_images', None)
                    if cache is None:
                        cache = self._turned_card_images = {}
                    key = (card, rotated, is_golden, turn)
                    if key not in cache:
                        if rotated:
                            base = base.rotate(90, expand=True)
                        cache[key] = ImageTk.PhotoImage(base, master=self)
                    return cache[key]
        if is_golden:
            image = self.golden_card_images_rotated.get(card) if rotated else self.golden_card_images.get(card)
            if image is not None:
                return image
        return self.external_card_images_rotated.get(card) if rotated else self.external_card_images.get(card)

    def _deal_initial_sequence_original(self):
        """Deal and reveal the four initial cards strictly one-by-one."""
        self.initial_card_ids = []
        sequence = (('Player', 1), ('Banker', 0), ('Player', 0), ('Banker', 1))
        if self.game_mode in BaccaratEngine.ALWAYS_MODES:
            self._draw_fixed_banker_card()
            sequence = (('Player', 1), ('Player', 0), ('Banker', 1))

        def deal_step(position=0):
            if self._closing or not self.current_result:
                return
            if position >= len(sequence):
                self._queue_animation(160, self._process_extra_cards_original)
                return

            hand_type, index = sequence[position]
            hand_key = 'player_hand' if hand_type == 'Player' else 'banker_hand'
            real_card = self.current_result[hand_key][index]

            def arrived(info):
                self._flip_card_original(
                    info, real_card,
                    on_complete=lambda: self._queue_animation(80, deal_step, position + 1)
                )

            self._animate_card_entrance_original(
                hand_type, index, rotated=False, on_arrive=arrived
            )

        deal_step(0)

    def _deal_initial_cards_original(self):
        # Backward-compatible helper retained for callers outside the main flow.
        self.initial_card_ids = []
        for hand_type in ('Player', 'Banker'):
            for index in (0, 1):
                self._animate_card_entrance_original(hand_type, index, rotated=False)

    def _animate_card_entrance_original(self, hand_type, index, rotated=False, on_arrive=None):
        if self._closing:
            return
        if self._cut_card_notice_due():
            self._show_cut_card_notice(lambda: self._animate_card_entrance_original(
                hand_type, index, rotated=rotated, on_arrive=on_arrive))
            return
        self._round_dealt_card_count += 1
        self._card_face_turn(hand_type, index)
        target_x, target_y = self.card_position(hand_type, index)
        base_w = 140 if rotated else 100
        start_x = (self.GAME_X0 + self.GAME_X1) / 2 - base_w / 2
        start_y = -110 if rotated else -150
        back = self._back_photo(rotated=rotated)
        card_id = self.canvas.create_image(start_x, start_y, image=back, anchor='nw',
                                           tags=('animation_card', 'animation'))
        self.card_item_ids.append(card_id)
        info = (hand_type, card_id, index)
        self.initial_card_ids.append(info)

        def move_step(step=0):
            if self._closing:
                return
            ratio = min(1.0, step / 30.0)
            x = start_x + (target_x - start_x) * ratio
            y = start_y + (target_y - start_y) * ratio
            self.canvas.coords(card_id, x, y)
            if step < 30:
                self._queue_animation(10, move_step, step + 1)
            elif callable(on_arrive):
                on_arrive(info)

        move_step(0)
        return info

    def _reveal_initial_phase1_original(self):
        if not self.current_result or len(self.initial_card_ids) < 4:
            return
        # Player opens card #1 first.
        self._flip_card_original(self.initial_card_ids[1], self.current_result['player_hand'][1])
        self._queue_animation(500, self._reveal_initial_phase3_original)

    def _reveal_initial_phase2_original(self):
        # Player opens card #0 second.
        self._flip_card_original(self.initial_card_ids[0], self.current_result['player_hand'][0])
        self._queue_animation(500, self._reveal_initial_phase4_original)

    def _reveal_initial_phase3_original(self):
        self._flip_card_original(self.initial_card_ids[2], self.current_result['banker_hand'][0])
        self._queue_animation(500, self._reveal_initial_phase2_original)

    def _reveal_initial_phase4_original(self):
        self._flip_card_original(self.initial_card_ids[3], self.current_result['banker_hand'][1])
        self._queue_animation(160, self._process_extra_cards_original)

    def _create_scaled_flip_image(self, card, width, height, use_back=False, rotated=False,
                                  hand_type=None, index=None, use_golden=True):
        if Image is None or ImageTk is None:
            return (self._back_photo(rotated) if use_back else
                    self._face_photo(card, rotated, hand_type=hand_type, index=index,
                                     use_golden=use_golden))
        if use_back:
            base = self._card_back_pil()
        else:
            base = self._face_pil(card, hand_type, index, use_golden=use_golden)
        if base is None:
            return (self._back_photo(rotated) if use_back else
                    self._face_photo(card, rotated, hand_type=hand_type, index=index,
                                     use_golden=use_golden))
        if rotated:
            base = base.rotate(90, expand=True)
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        image = base.resize((max(1, int(width)), max(1, int(height))), resample)
        return ImageTk.PhotoImage(image, master=self)

    @staticmethod
    def _squeeze_fold_geometry(width, height, progress, direction):
        """Shared physical fold geometry for rendering and regrab hit testing."""
        nx, ny = {
            'left': (1, 0), 'right': (-1, 0),
            'top': (0, 1), 'bottom': (0, -1),
            'top_left': (1, 1), 'top_right': (-1, 1),
            'bottom_left': (1, -1), 'bottom_right': (-1, -1),
        }[direction]
        length = math.hypot(nx / width, ny / height)
        nx, ny = nx / width / length, ny / height / length
        tx, ty = -ny, nx
        corners = ((0, 0), (width, 0), (width, height), (0, height))
        qs = [nx * x + ny * y for x, y in corners]
        ts = [tx * x + ty * y for x, y in corners]
        p = max(0.0, min(1.0, progress))
        fraction = p
        if nx and ny:
            fraction = (math.sqrt(2 * p) / 2 if p <= .5 else
                        1 - math.sqrt(2 * (1 - p)) / 2)
        lift = math.sin(math.pi * p) ** .7
        return {
            'normal': (nx, ny), 'tangent': (tx, ty),
            't_bounds': (min(ts), max(ts)), 'q_min': min(qs),
            'front': min(qs) + (max(qs) - min(qs)) * fraction,
            'lift': lift, 'bow': min(width, height) * .035 * lift,
            'lip': max(.5, min(width, height) * .075 * lift),
        }

    @staticmethod
    def _render_squeeze_frame(face, back, progress, direction='bottom', with_mask=False):
        """A shallow curved fold, with locally bent texture and a soft shadow.

        The flat face keeps its original proportions. Only the narrow raised
        lip is warped; fingers are composited separately after this renderer.
        """
        p = max(0.0, min(1.0, progress))
        w, h = face.size
        if p <= 0 or p >= 1:
            frame = back.copy() if p <= 0 else face.copy()
            mask = Image.new('L', (w, h), 0 if p <= 0 else 255)
            return (frame, mask) if with_mask else frame
        geometry = BubbleBaccaratGame._squeeze_fold_geometry(w, h, p, direction)
        nx, ny = geometry['normal']
        tx, ty = geometry['tangent']
        t0, t1 = geometry['t_bounds']
        q0, lift = geometry['front'], geometry['lift']
        bow, lip = geometry['bow'], geometry['lip']
        samples = [t0 + (t1 - t0) * i / 32 for i in range(33)]

        def fold(t):
            along = 2 * (t - t0) / max(1, t1 - t0) - 1
            return q0 + bow * (1 - along * along)

        def point(t, offset=0):
            q = fold(t) + offset
            return nx * q + tx * t, ny * q + ty * t

        # Warp the back locally around the raised lip, in the fold's own axes.
        # A mesh avoids stretching the whole card or repeating texture strips.
        def source(x, y):
            t = tx * x + ty * y
            u = (nx * x + ny * y - fold(t)) / lip
            shift = lip * (math.sin(u * math.pi / 2) - u) if 0 < u < 1 else 0
            return x + nx * shift, y + ny * shift

        mesh = []
        for y in range(0, h, 8):
            for x in range(0, w, 8):
                right, bottom = min(w, x + 8), min(h, y + 8)
                quad = [source(px, py) for px, py in
                        ((x, y), (x, bottom), (right, bottom), (right, y))]
                mesh.append(((x, y, right, bottom),
                             tuple(value for pair in quad for value in pair)))
        warped_back = back.transform(
            (w, h), getattr(Image, 'Transform', Image).MESH, mesh,
            getattr(Image, 'Resampling', Image).BICUBIC)
        scale = 2
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        boundary = [point(t) for t in samples]
        behind = geometry['q_min'] - max(w, h)
        polygon = boundary + [(nx * behind + tx * t, ny * behind + ty * t)
                              for t in (t1, t0)]
        mask = Image.new('L', (w * scale, h * scale), 0)
        ImageDraw.Draw(mask).polygon(
            [(round(x * scale), round(y * scale)) for x, y in polygon], fill=255)
        mask = mask.resize((w, h), resample)
        frame = Image.composite(face, warped_back, mask)
        shade = Image.new('RGBA', (w * scale, h * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(shade)

        def ribbon(start, end, color):
            points = ([point(t, start) for t in samples] +
                      [point(t, end) for t in reversed(samples)])
            draw.polygon([(round(x * scale), round(y * scale)) for x, y in points],
                         fill=color)

        # The lifted paper casts a short, fading shadow onto the remaining back.
        for i in range(8, 0, -1):
            ribbon(lip + i - 1, lip + i, (0, 0, 0, round((9 - i) * 7 * lift)))
        for i in range(12):
            u = (i + .5) / 12
            if u < .55:
                color = (255, 251, 235, round(90 * (1 - u / .55) * lift))
            else:
                color = (20, 17, 13, round(68 * (u - .55) / .45 * lift))
            ribbon(lip * i / 12, lip * (i + 1) / 12, color)
        ribbon(-1.0, 0, (255, 253, 241, 185))
        ribbon(0, .65, (85, 74, 60, 100))
        alpha = frame.getchannel('A')
        frame.alpha_composite(shade.resize((w, h), resample))
        frame.putalpha(alpha)
        return (frame, mask) if with_mask else frame

    @staticmethod
    def _squeeze_wager_hands(bets):
        """Tie and side wagers do not confer control of either main hand."""
        return {hand for hand in ('Player', 'Banker')
                if float((bets or {}).get(hand, 0.0)) > 0}

    def _deal_squeeze_batch(self, sequence, on_complete):
        """Deal every back in a group before installing any mouse bindings."""
        self._clear_squeeze_display(keep_backdrop=True)
        batch = {'entries': {}, 'ready': False, 'continuing': False,
                 'on_complete': on_complete, 'panels': {}}
        self._squeeze_batch = batch
        self.canvas.itemconfigure(self.animation_phase_text, text='发牌中…')

        def deal_next(position=0):
            if self._closing or self._squeeze_batch is not batch:
                return
            if position == len(sequence):
                self._enable_squeeze_batch(batch)
                return
            hand, index = sequence[position]
            hand_key = 'player_hand' if hand == 'Player' else 'banker_hand'
            card = self.current_result[hand_key][index]

            def arrived(info):
                if self._closing or self._squeeze_batch is not batch:
                    return
                batch['entries'][(hand, index)] = {
                    'info': info, 'card': card, 'status': 'hidden',
                    'squeeze': hand in self._squeeze_hands,
                    'progress': 0.0, 'pull': 0.0, 'direction': 'bottom',
                    'dragging': False, 'press_kind': None, 'resume_point': None,
                }
                self._queue_animation(60, deal_next, position + 1)

            self._animate_card_entrance_original(
                hand, index, rotated=index == 2, on_arrive=arrived)

        deal_next()

    def _bind_squeeze_control(self, target, sequence, callback):
        binding = self.canvas.tag_bind(target, sequence, callback)
        self._squeeze_bindings.append((target, sequence, binding))

    def _show_squeeze_backdrop(self):
        """Keep one light betting-board shade alive for the whole round."""
        if getattr(self, '_squeeze_backdrop_photo', None) is not None:
            return
        left, top, right, _bottom = self.BETTING_BOUNDS
        bottom = self.BETTING_TRANSITION_BOUNDS[3]
        shade = Image.new('RGBA',
                          (right-left, bottom-top),
                          (0, 0, 0, 12))
        self._squeeze_backdrop_photo = ImageTk.PhotoImage(shade, master=self)
        self.canvas.create_image(left, top,
                                 image=self._squeeze_backdrop_photo, anchor='nw',
                                 tags='squeeze_backdrop')

    def _clear_squeeze_backdrop(self):
        if hasattr(self, 'canvas'):
            try:
                self.canvas.delete('squeeze_backdrop')
            except tk.TclError:
                pass
        self._squeeze_backdrop_photo = None

    def _enable_squeeze_batch(self, batch):
        if self._closing or self._squeeze_batch is not batch:
            return
        self.canvas.itemconfigure(
            self.animation_phase_text, text='咪牌 · 轻点牌中央开牌')
        controlled_hands = {key[0] for key, entry in batch['entries'].items()
                            if entry['squeeze']}
        if controlled_hands:
            # PhotoImage's alpha keeps the actual betting labels and chips
            # visible through this very light shade, without an opaque panel.
            self._show_squeeze_backdrop()
        for hand in ('Player', 'Banker'):
            keys = [key for key, entry in batch['entries'].items()
                    if key[0] == hand and entry['squeeze']]
            if not keys:
                continue
            # The normal one-hand view floats in the middle of the existing
            # board, leaving both main-wager chips exposed at either side.
            if len(controlled_hands) == 1:
                left, right = self.BOARD_INNER_X0, self.BOARD_INNER_X1
            else:
                left, right = ((self.BOARD_INNER_X0, 378) if hand == 'Player'
                               else (394, self.BOARD_INNER_X1))
            batch['panels'][hand] = (left, self.BETTING_BOUNDS[1], right,
                                     self.BETTING_TRANSITION_BOUNDS[3])
            # Match the existing table's left-to-right order (P1, P0 / B0, B1).
            keys.sort(key=lambda key: self.card_position(*key)[0])
            centre = (left + right) / 2
            for position, key in enumerate(keys):
                rotated = key[1] == 2
                size = (224, 160) if rotated else (130, 182)
                if len(keys) == 1:
                    cx = centre
                elif len(controlled_hands) == 1:
                    cx = centre + (position * 2 - 1) * 108
                else:
                    cx = left + 92 + position * 172
                top = 415 if rotated else 404
                self._create_squeeze_card_view(key, cx - size[0] / 2, top, size)
            self._draw_squeeze_hand_controls(hand, keys, centre, batch)

        for key, entry in batch['entries'].items():
            if not entry['squeeze']:
                self._bind_squeeze_control(
                    entry['info'][1], '<Button-1>',
                    lambda _event, k=key, b=batch: self._open_squeeze_entry(k, b))
        self._enter_squeeze_cards(batch)

    def _enter_squeeze_cards(self, batch):
        """Bring each controlled back from its table slot into the larger view."""
        if self._closing or self._squeeze_batch is not batch:
            return
        batch['entering'] = True
        moving = []
        self.canvas.itemconfigure('squeeze_controls', state='hidden')
        for key, entry in batch['entries'].items():
            if not entry['squeeze']:
                continue
            x, y = self.card_position(*key)
            start_w, start_h = (140, 100) if key[1] == 2 else (100, 140)
            left, top, width, height = entry['bounds']
            entry['table_hidden'] = True
            self.canvas.itemconfigure(entry['info'][1], state='hidden')
            moving.append((entry, (x + start_w / 2, y + start_h / 2),
                           (left + width / 2, top + height / 2),
                           (start_w, start_h), (width, height)))

        def ready():
            batch['entering'] = False
            batch['ready'] = True
            self.canvas.itemconfigure('squeeze_controls', state='normal')
            self._refresh_squeeze_hand_controls(batch)
            self._advance_squeeze_batch(batch)

        if not moving:
            ready()
            return
        resample = getattr(Image, 'Resampling', Image).LANCZOS

        def move(step=0):
            if self._closing or self._squeeze_batch is not batch:
                return
            t = step / 14.0
            eased = t * t * (3 - 2 * t)
            for entry, start, end, start_size, end_size in moving:
                size = tuple(max(1, round(a + (b - a) * eased))
                             for a, b in zip(start_size, end_size))
                frame = entry['table_back'].resize(size, resample)
                cx = start[0] + (end[0] - start[0]) * eased
                cy = start[1] + (end[1] - start[1]) * eased
                entry['photo'] = ImageTk.PhotoImage(frame, master=self)
                self.canvas.itemconfigure(entry['item'], image=entry['photo'])
                self.canvas.coords(entry['item'], cx - size[0] / 2, cy - size[1] / 2)
            if step < 14:
                self._queue_animation(20, move, step + 1)
            else:
                ready()

        move()

    def _create_squeeze_card_view(self, key, left, top, size):
        batch = self._squeeze_batch
        entry = batch['entries'][key]
        card = tuple(entry['card'])
        # A golden match is revealed only after this normal-colour card returns
        # to its table slot; peeling, rotating and flying all use original art.
        face = self._face_pil(card, key[0], key[1], use_golden=False)
        asset_dir = (getattr(self, 'poker2_asset_dir', None) if self.game_mode in BaccaratEngine.ALWAYS_MODES
                     else getattr(self, 'card_asset_dir', None))
        fallback = face is None or asset_dir is None
        if face is None:
            face = self._make_fallback_card_pil(card)
            if self._card_face_turn(*key):
                face = face.rotate(180)
        back = self._card_back_pil()
        if back is None:
            back = self._make_fallback_card_pil(None, face_up=False)
        rotated = key[1] == 2
        if rotated:
            face, back = face.rotate(90, expand=True), back.rotate(90, expand=True)
        table_back = back.convert('RGBA')
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        face = face.convert('RGBA').resize(size, resample)
        back = back.convert('RGBA').resize(size, resample)
        covered, grips = self._make_squeeze_grip_layers(
            face, rotated, fallback=fallback, rank=card[1])
        entry.update(face=face, back=back, table_back=table_back, bounds=(left, top, *size),
                     covered_face=covered, base_face=face, base_back=back,
                     base_covered_face=covered, rotation=0,
                     grips=grips, base_grips=grips, grip_retreat=0.0,
                     grip_angle=90 if rotated else 0,
                     centre=(left + size[0] / 2, top + size[1] / 2),
                     view_box=(240, 182) if rotated else (160, 182))
        c = self.canvas
        entry['photo'] = ImageTk.PhotoImage(back, master=self)
        entry['item'] = c.create_image(
            left, top, image=entry['photo'], anchor='nw',
            tags=('squeeze_overlay', 'squeeze_card'))
        for sequence, handler in (
                ('<ButtonPress-1>', self._squeeze_press),
                ('<B1-Motion>', self._squeeze_drag),
                ('<ButtonRelease-1>', self._squeeze_release)):
            self._bind_squeeze_control(
                entry['item'], sequence,
                lambda event, k=key, b=batch, fn=handler: fn(event, k, b))

    def _draw_squeeze_hand_controls(self, hand, keys, centre_x, batch):
        """One ↻ / ✔ / ⟲ row for each controlled side, in visual card order."""
        y = batch['panels'][hand][3] - 17
        actions = (
            ('↻', lambda: self._rotate_squeeze_entry(keys[0], batch, 90)),
            ('✔', lambda: self._open_squeeze_hand(hand, batch)),
            ('⟲', lambda: self._rotate_squeeze_entry(keys[-1], batch, -90)),
        )
        positions = ((batch['entries'][keys[0]]['centre'][0], centre_x,
                      batch['entries'][keys[-1]]['centre'][0]) if len(keys) > 1
                     else (centre_x - 64, centre_x, centre_x + 64))
        controls = []
        for index, (symbol, action) in enumerate(actions):
            x = positions[index]
            tag = f'squeeze_control_{hand}_{index}'
            targets = tuple(keys) if index == 1 else (keys[0] if index == 0 else keys[-1],)
            controls.append((tag, targets))
            self.canvas.create_rectangle(
                x - 27, y - 12, x + 27, y + 12, fill='#a57e38',
                outline='#f2d77c', width=1,
                tags=('squeeze_overlay', 'squeeze_chrome', 'squeeze_controls', tag))
            self.canvas.create_text(
                x, y, text=symbol, fill='#111111', font=('Segoe UI Symbol', 15, 'bold'),
                tags=('squeeze_overlay', 'squeeze_chrome', 'squeeze_controls', tag))
            self._bind_squeeze_control(
                tag, '<Button-1>', lambda _event, fn=action: fn())
        batch.setdefault('controls', {})[hand] = controls

    def _refresh_squeeze_hand_controls(self, batch):
        if self._closing or self._squeeze_batch is not batch:
            return
        for controls in batch.get('controls', {}).values():
            for tag, keys in controls:
                visible = (batch['ready'] and not batch.get('entering') and
                           any(batch['entries'][key]['status'] == 'hidden' for key in keys))
                self.canvas.itemconfigure(tag, state='normal' if visible else 'hidden')

    def _rotate_squeeze_entry(self, key, batch, degrees):
        if (self._closing or self._squeeze_batch is not batch
                or not batch['ready'] or batch['continuing']):
            return
        entry = batch['entries'].get(key)
        if (entry is None or not entry['squeeze'] or entry['status'] == 'opening'
                or entry.get('returned')):
            return
        entry['rotation'] = (entry['rotation'] + degrees) % 360
        entry['dragging'] = False
        entry['press_kind'] = None
        entry['resume_point'] = None
        if entry['status'] == 'hidden':
            entry['progress'] = 0.0
            entry['pull'] = 0.0
        angle = -entry['rotation']  # Pillow positive angles are counterclockwise.
        face = entry['base_face'].rotate(angle, expand=True)
        width, height = face.size
        max_w, max_h = entry['view_box']
        ratio = min(1.0, max_w / width, max_h / height)
        size = (max(1, round(width * ratio)), max(1, round(height * ratio)))
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        entry['face'] = face.resize(size, resample)
        entry['back'] = entry['base_back'].rotate(angle, expand=True).resize(size, resample)
        entry['covered_face'] = entry['base_covered_face'].rotate(
            angle, expand=True).resize(size, resample)
        entry['grips'] = tuple(layer.rotate(angle, expand=True).resize(size, resample)
                               for layer in entry['base_grips'])
        entry['grip_angle'] = (90 if key[1] == 2 else 0) - entry['rotation']
        cx, cy = entry['centre']
        left, top = cx - size[0] / 2, cy - size[1] / 2
        entry['bounds'] = (left, top, *size)
        self.canvas.coords(entry['item'], left, top)
        self._paint_squeeze_entry(entry)

    def _open_squeeze_hand(self, hand, batch):
        if self._closing or self._squeeze_batch is not batch:
            return
        keys = [key for key, entry in batch['entries'].items()
                if key[0] == hand and entry['squeeze'] and entry['status'] == 'hidden']
        for key in keys:
            self._open_squeeze_entry(key, batch)

    @staticmethod
    def _make_squeeze_grip_layers(face, rotated=False, fallback=False, rank=None):
        """Short fingertips protect the rank, leaving the suit/pips visible.

        Keep the fingertips separate from the paper so they never bend with
        its texture. A matching paper patch protects the rank under the curl.
        """
        upright = face.rotate(-90, expand=True) if rotated else face.copy()
        w, h = upright.size
        scale = 3
        # External art uses compact corner ranks. The emergency font is wider.
        width_ratio = (.53 if str(rank) == '10' else .40) if fallback else .29
        height_ratio = .25 if fallback else .22
        fw, fh = round(w * width_ratio * scale), round(h * height_ratio * scale)
        layer = Image.new('RGBA', (w * scale, h * scale), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        radius = round(fw * .43)
        draw.rounded_rectangle((-6 * scale, -fh, fw + 2 * scale, fh + 2 * scale),
                               radius=radius, fill=(60, 32, 18, 70))
        draw.rounded_rectangle((-6 * scale, -fh, fw, fh), radius=radius,
                               fill='#b77c59')
        for inset in range(1, 6):
            pad = inset * scale / 2
            draw.rounded_rectangle((-6 * scale, -fh, fw - pad, fh - pad),
                                   radius=max(scale, radius - pad),
                                   fill=(193 + inset * 4, 133 + inset * 5, 99 + inset * 5))
        draw.rounded_rectangle((fw * .20, fh * .36, fw * .79, fh * .79),
                               radius=max(scale, fw * .16), fill='#f0d1b9',
                               outline='#bd896a', width=scale)
        draw.arc((fw * .19, fh * .02, fw * .81, fh * .27),
                 15, 165, fill='#c99574', width=scale)
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        top = layer.resize((w, h), resample)
        bottom = top.rotate(180)
        # Erase only the opaque area beneath the pads before bending the paper.
        # Sampling the blank top margin also works with off-white card stock.
        stock = upright.getpixel((round(w * .5), max(1, round(h * .09))))
        paper = Image.new('RGBA', (w, h), stock)
        protection = ImageChops.lighter(top.getchannel('A'), bottom.getchannel('A'))
        protection = protection.point(lambda alpha: 255 if alpha > 220 else 0)
        covered = Image.composite(paper, upright, protection)
        covered.putalpha(upright.getchannel('A'))
        if rotated:
            return covered.rotate(90, expand=True), tuple(
                grip.rotate(90, expand=True) for grip in (top, bottom))
        return covered, (top, bottom)

    def _paint_squeeze_entry(self, entry):
        if self._closing:
            return
        if entry['status'] == 'open':
            frame = entry['face']
        else:
            # Ranks become visible only after the deliberate opening completes
            # the fold; the fingers then slide outward over the flat face.
            face = entry['face'] if entry['progress'] >= 1 else entry['covered_face']
            frame, exposed = self._render_squeeze_frame(
                face, entry['back'], entry['progress'], entry['direction'], with_mask=True)
            angle = math.radians(entry.get('grip_angle', 0))
            distance = max(frame.size) * .32 * entry.get('grip_retreat', 0.0)
            for index, grip in enumerate(entry['grips']):
                sign = -1 if index == 0 else 1
                dx = round(sign * distance * math.sin(angle))
                dy = round(sign * distance * math.cos(angle))
                overlay = Image.new('RGBA', frame.size, (0, 0, 0, 0))
                overlay.paste(grip, (dx, dy))
                alpha = ImageChops.multiply(overlay.getchannel('A'), exposed)
                overlay.putalpha(ImageChops.multiply(alpha, frame.getchannel('A')))
                frame.alpha_composite(overlay)
        entry['photo'] = ImageTk.PhotoImage(frame, master=self)
        self.canvas.itemconfigure(entry['item'], image=entry['photo'])

    def _interactive_squeeze_entry(self, key, batch):
        if (self._closing or self._squeeze_batch is not batch
                or not batch['ready'] or batch['continuing']):
            return None
        entry = batch['entries'].get(key)
        return entry if entry and entry['status'] == 'hidden' and entry['squeeze'] else None

    def _squeeze_can_resume(self, entry, x, y):
        if entry['progress'] <= 0:
            return False
        left, top, width, height = entry['bounds']
        last = entry.get('resume_point')
        tolerance = max(12, min(width, height) * .09)
        if last and math.hypot(x - last[0], y - last[1]) <= tolerance:
            return True
        geometry = self._squeeze_fold_geometry(
            width, height, entry['progress'], entry['direction'])
        nx, ny = geometry['normal']
        tx, ty = geometry['tangent']
        t0, t1 = geometry['t_bounds']
        px, py = x - left, y - top
        along = 2 * (tx * px + ty * py - t0) / max(1, t1 - t0) - 1
        front = geometry['front'] + geometry['bow'] * (1 - along * along)
        return abs(nx * px + ny * py - front) <= tolerance + geometry['lip']

    def _squeeze_press(self, event, key, batch):
        entry = self._interactive_squeeze_entry(key, batch)
        if entry is None:
            return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        left, top, width, height = entry['bounds']
        u, v = (x - left) / width, (y - top) / height
        entry.update(origin=(x, y), moved=False, press_kind='centre', dragging=False)
        # A held fold often crosses the central click zone. Regrab it before
        # considering centre clicks or a fresh edge/corner direction.
        if self._squeeze_can_resume(entry, x, y):
            entry.update(dragging=True, press_kind='edge', start_pull=entry['pull'])
            return
        if .30 <= u <= .70 and .30 <= v <= .70:
            # Press alone never opens a card. Release must remain a short click.
            return
        distances = {'left': abs(x - left), 'right': abs(x - left - width),
                     'top': abs(y - top), 'bottom': abs(y - top - height)}
        if (u < .32 or u > .68) and (v < .32 or v > .68):
            direction = ('top' if v < .5 else 'bottom') + ('_left' if u < .5 else '_right')
        else:
            direction = min(distances, key=distances.get)
        if direction != entry['direction']:
            entry.update(direction=direction, progress=0.0, pull=0.0, resume_point=None)
        entry.update(dragging=True, press_kind='edge', start_pull=entry['pull'])
        self._paint_squeeze_entry(entry)

    def _squeeze_drag(self, event, key, batch):
        entry = self._interactive_squeeze_entry(key, batch)
        if entry is None or entry.get('press_kind') is None:
            return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        ox, oy = entry['origin']
        if math.hypot(x - ox, y - oy) > 5:
            entry['moved'] = True
        if not entry['dragging'] or not entry['moved']:
            return
        direction = entry['direction']
        width, height = entry['bounds'][2:]
        dx, dy = (x - ox) / width, (y - oy) / height
        delta = {'bottom': -dy, 'top': dy, 'left': dx, 'right': -dx,
                 'top_left': (dx + dy) / 2, 'top_right': (-dx + dy) / 2,
                 'bottom_left': (dx - dy) / 2, 'bottom_right': (-dx - dy) / 2}[direction]
        pull = max(0.0, min(1.0, entry['start_pull'] + delta))
        entry['pull'] = pull
        # Slow initial travel allows fine inspection. Keeping raw pull makes
        # reverse dragging and resuming a held fold continuous.
        entry['progress'] = min(.99, pull * pull * (3 - 2 * pull))
        self._paint_squeeze_entry(entry)

    def _squeeze_release(self, event, key, batch):
        entry = self._interactive_squeeze_entry(key, batch)
        if entry is None or entry.get('press_kind') is None:
            return
        if entry['press_kind'] == 'edge':
            # Include the final pointer position even if its motion event was
            # coalesced before release, then retain it as the next grip point.
            self._squeeze_drag(event, key, batch)
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        left, top, width, height = entry['bounds']
        u, v = (x - left) / width, (y - top) / height
        ox, oy = entry['origin']
        click = (entry['press_kind'] == 'centre' and not entry['moved']
                 and math.hypot(x - ox, y - oy) <= 5
                 and .30 <= u <= .70 and .30 <= v <= .70)
        threshold = .40 if entry['card'][1] in ('J', 'Q', 'K') else .60
        auto_open = entry['press_kind'] == 'edge' and entry['progress'] >= threshold
        if entry['press_kind'] == 'edge':
            entry['resume_point'] = (x, y)
        entry.update(dragging=False, press_kind=None)
        if click or auto_open:
            self._open_squeeze_entry(key, batch)
        # An incomplete edge drag stays exactly where the user left it.

    def _open_squeeze_entry(self, key, batch):
        if (self._closing or self._squeeze_batch is not batch
                or not batch['ready'] or batch['continuing']):
            return
        entry = batch['entries'].get(key)
        if entry is None or entry['status'] != 'hidden':
            return
        entry['status'] = 'opening'  # lock before any callback or repeated click
        self._refresh_squeeze_hand_controls(batch)
        entry['dragging'] = False
        entry['press_kind'] = None
        entry['resume_point'] = None

        def opened():
            if self._closing or self._squeeze_batch is not batch:
                return
            entry['status'] = 'open'
            self._advance_squeeze_batch(batch)

        if not entry['squeeze']:
            self._flip_card_original(entry['info'], entry['card'], on_complete=opened)
            return

        start = entry['progress']

        def arrived():
            if self._closing or self._squeeze_batch is not batch:
                return
            # Reveal the table card and commit its score only when the opened
            # moving card reaches its slot; golden hits then fade while their
            # multiplier badges drop over the same 1.5-second interval.
            self._flip_card_original(entry['info'], entry['card'], step=13,
                                     on_complete=opened, golden_return=True)

        def unfold(step=0):
            if self._closing or self._squeeze_batch is not batch:
                return
            t = step / 12.0
            fold_t = min(1.0, t / .65)
            eased = fold_t * fold_t * (3 - 2 * fold_t)
            entry['progress'] = start + (1 - start) * eased
            retreat = max(0.0, min(1.0, (t - .55) / .45))
            entry['grip_retreat'] = retreat * retreat * (3 - 2 * retreat)
            self._paint_squeeze_entry(entry)
            if step < 12:
                self._queue_animation(20, unfold, step + 1)
            else:
                self._return_squeeze_cards(batch, arrived, keys=(key,))

        unfold()

    def _advance_squeeze_batch(self, batch):
        if (self._closing or self._squeeze_batch is not batch
                or not batch['ready'] or batch['continuing']):
            return
        entries = batch['entries']
        if any(e['squeeze'] and e['status'] != 'open' for e in entries.values()):
            return
        if any(e['status'] == 'opening' for e in entries.values()):
            return
        # Once the controlled cards are open, reveal any untouched opponent
        # cards sequentially, waiting for golden-multiplier drops as well.
        hidden = next((k for k, e in entries.items() if e['status'] == 'hidden'), None)
        if hidden is not None:
            self._open_squeeze_entry(hidden, batch)
            return
        batch['continuing'] = True

        def complete():
            if self._closing or self._squeeze_batch is not batch:
                return
            callback = batch['on_complete']
            self._clear_squeeze_display(keep_backdrop=True)
            callback()

        self._queue_animation(80, self._return_squeeze_cards, batch, complete)

    def _return_squeeze_cards(self, batch, on_complete, keys=None):
        """Return to the nearest upright/inverted pose, hiding table copies in flight."""
        if self._closing or self._squeeze_batch is not batch:
            return
        moving = []
        # Single-card returns leave the controls available for the unopened
        # cards. Hide the buttons when the whole batch is being removed;
        # the independent backdrop remains until settlement finishes.
        if keys is None:
            self.canvas.itemconfigure('squeeze_chrome', state='hidden')
        for key in (keys if keys is not None else batch['entries']):
            entry = batch['entries'][key]
            if (not entry['squeeze'] or entry.get('returned')
                    or entry['status'] not in ('opening', 'open') or entry['progress'] < 1):
                continue
            left, top, width, height = entry['bounds']
            x, y = self.card_position(*key)
            target_w, target_h = (140, 100) if key[1] == 2 else (100, 140)
            rotation = entry['rotation'] % 360
            # Either 0 or 180 degrees fits the same table slot. Keep an
            # inverted card inverted; quarter turns travel at most 90 degrees.
            target_rotation = min((0, 180, 360), key=lambda angle: abs(angle - rotation))
            source_w = entry['base_face'].rotate(-rotation, expand=True).width
            entry['table_turn'] = (self._card_face_turn(*key) + target_rotation) % 360
            entry['returning'] = True
            self.canvas.tag_raise(entry['item'])
            moving.append((key, entry, (left + width / 2, top + height / 2),
                           (x + target_w / 2, y + target_h / 2),
                           width / source_w, target_w / entry['base_face'].width,
                           rotation, target_rotation))
        if not moving:
            on_complete()
            return
        resample = getattr(Image, 'Resampling', Image)

        def move(step=0):
            if self._closing or self._squeeze_batch is not batch:
                return
            t = step / 14.0
            eased = t * t * (3 - 2 * t)
            for key, entry, start, end, start_scale, end_scale, rotation, target_rotation in moving:
                angle = -(rotation + (target_rotation - rotation) * eased)
                frame = entry['base_face'].rotate(angle, resample=resample.BICUBIC,
                                                   expand=True)
                scale = start_scale + (end_scale - start_scale) * eased
                size = (max(1, round(frame.width * scale)),
                        max(1, round(frame.height * scale)))
                frame = frame.resize(size, resample.LANCZOS)
                cx = start[0] + (end[0] - start[0]) * eased
                cy = start[1] + (end[1] - start[1]) * eased
                entry['photo'] = ImageTk.PhotoImage(frame, master=self)
                self.canvas.itemconfigure(entry['item'], image=entry['photo'])
                self.canvas.coords(entry['item'], cx - size[0] / 2, cy - size[1] / 2)
            if step < 14:
                self._queue_animation(20, move, step + 1)
            else:
                for key, entry, *_rest in moving:
                    # The normal/golden table images must use the same pose
                    # as the arriving card, including later redraws and fades.
                    self._card_face_turns[key] = entry['table_turn']
                    entry.update(returned=True, returning=False, table_hidden=False)
                    self.canvas.itemconfigure(entry['item'], state='hidden')
                    self.canvas.itemconfigure(entry['info'][1], state='normal')
                on_complete()

        move()

    def _process_squeeze_extra_cards(self):
        if self._closing or not self.current_result:
            return
        p = self.current_result['player_hand']
        b = self.current_result['banker_hand']
        if len(p) > 2:
            if BaccaratEngine.score(b[:2]) <= 2 and len(b) > 2:
                # Banker 0/1/2 always draws: both backs must arrive before
                # either side becomes interactive. Do not reveal Player first.
                self._deal_squeeze_batch(
                    (('Player', 2), ('Banker', 2)), self.finish_deal)
            else:
                self._deal_squeeze_batch(
                    (('Player', 2),), self._process_banker_squeeze_extra)
        else:
            self._process_banker_squeeze_extra()

    def _process_banker_squeeze_extra(self):
        if self._closing or not self.current_result:
            return
        if len(self.current_result['banker_hand']) > 2:
            self._deal_squeeze_batch((('Banker', 2),), self.finish_deal)
        else:
            self.finish_deal()

    def _clear_squeeze_display(self, keep_backdrop=False):
        batch = self._squeeze_batch
        self._squeeze_batch = None
        if hasattr(self, 'canvas'):
            if batch:
                for key, entry in batch['entries'].items():
                    if entry.get('table_hidden') or entry.get('returning'):
                        try:
                            self.canvas.itemconfigure(entry['info'][1], state='normal')
                            self.canvas.itemconfigure(
                                f'golden_card_{key[0]}_{key[1]}', state='normal')
                        except tk.TclError:
                            pass
            # Tk needs the item to exist while tag_unbind reads its bindings.
            # Release callbacks BEFORE deleting the corresponding card items.
            bindings = self._squeeze_bindings
            self._squeeze_bindings = []
            for target, sequence, binding in bindings:
                try:
                    self.canvas.tag_unbind(target, sequence, binding)
                except tk.TclError:
                    # A reset/window close may have already removed the item;
                    # still release its registered Python callback if present.
                    if binding:
                        try:
                            self.canvas.deletecommand(binding)
                        except (tk.TclError, ValueError):
                            pass
            try:
                self.canvas.delete('squeeze_overlay')
            except tk.TclError:
                pass  # Canvas was already destroyed during window teardown.
        if not keep_backdrop:
            self._clear_squeeze_backdrop()

    def _flip_card_original(self, card_info, real_card, step=0, on_complete=None,
                            golden_return=False):
        if self._closing:
            return
        hand_type, card_id, index = card_info
        rotated = index == 2
        steps = 12
        orig_w, orig_h = ((140, 100) if rotated else (100, 140))

        if step > steps:
            fade_golden = (golden_return or self.game_mode in ('treasure', 'xxx')) and self._is_current_golden(real_card)
            final_image = self._face_photo(real_card, rotated=rotated,
                                           hand_type=hand_type, index=index,
                                           use_golden=not fade_golden)
            if final_image is not None:
                self.canvas.itemconfigure(card_id, image=final_image)
            self.revealed_cards.setdefault(hand_type, []).append(real_card)
            score = BaccaratEngine.score(self.revealed_cards[hand_type])
            target = self.player_score_text if hand_type == 'Player' else self.banker_score_text
            self.canvas.itemconfigure(target, text=str(score))
            target_x, target_y = self.card_position(hand_type, index)
            self.canvas.coords(card_id, target_x, target_y)
            self._temp_flip_images.pop(card_id, None)
            if self.game_mode == '2to1':
                self._update_2to1_multiplier_ribbon(use_revealed=True)

            # In Treasure Pot, a matched target card must finish its multiplier
            # drop at the card's current top-right position before the dealing
            # sequence is allowed to continue.
            if self.game_mode in ('treasure', 'xxx') and tuple(real_card) in self.current_golden_map:
                def transform():
                    self._animate_dealt_golden_multiplier(
                        hand_type, index, real_card, on_complete=on_complete,
                        fade_card_id=card_id if fade_golden else None)
                if self.game_mode in ('treasure', 'xxx'):
                    self._animate_treasure_light(hand_type, index, real_card, card_id, transform)
                else:
                    transform()
            elif callable(on_complete):
                on_complete()
            return

        half = steps // 2
        if step <= half:
            ratio = 1 - (step / float(half))
            use_back = True
        else:
            ratio = (step - half) / float(half)
            use_back = False
        # Upright cards flip by collapsing their width.  The third card is
        # physically rotated 90 degrees, so its flip axis must rotate with it:
        # collapse/expand HEIGHT instead, keeping the card centred vertically.
        if rotated:
            width = orig_w
            height = max(1, int(orig_h * ratio))
        else:
            width = max(1, int(orig_w * ratio))
            height = orig_h

        image = self._create_scaled_flip_image(real_card, width, height,
                                               use_back=use_back, rotated=rotated,
                                               hand_type=hand_type, index=index,
                                               use_golden=not golden_return and self.game_mode not in ('treasure', 'xxx'))
        if image is not None:
            self._temp_flip_images[card_id] = image
            self.canvas.itemconfigure(card_id, image=image)
            target_x, target_y = self.card_position(hand_type, index)
            if rotated:
                self.canvas.coords(card_id, target_x, target_y + (orig_h - height) / 2)
            else:
                self.canvas.coords(card_id, target_x + (orig_w - width) / 2, target_y)
        self._queue_animation(20, self._flip_card_original, card_info, real_card,
                              step + 1, on_complete, golden_return)

    def _animate_treasure_light(self, hand_type, index, card, card_id, on_complete):
        """Gather at the matching small card, fly to the open card, then inject."""
        source_index = next((i for i, (face, _mult) in enumerate(self.current_golden_cards)
                             if tuple(face) == tuple(card)), None)
        if source_index is None:
            on_complete()
            return
        px, py = self._treasure_panel_positions()[source_index]
        small_w, small_h = self._treasure_card_size()
        source = (px + small_w / 2, py + small_h / 2)
        tx, ty = self.card_position(hand_type, index)
        target = (tx + (70 if index == 2 else 50), ty + (50 if index == 2 else 70))
        control = ((source[0] + target[0]) / 2, min(source[1], target[1]) - 55)
        c = self.canvas
        tag = f'golden_light_{hand_type}_{index}'
        tags = ('animation', 'golden_light', tag)
        trail = c.create_line(*source, *source, fill='#e6ad27', width=4,
                              capstyle='round', tags=tags)
        halo = c.create_oval(0, 0, 1, 1, fill='', outline='#ffd65b', width=3, tags=tags)
        core = c.create_oval(0, 0, 1, 1, fill='#fff8d4', outline='#fff2a0', width=1, tags=tags)

        def path(t):
            return tuple((1-t)**2 * source[i] + 2*(1-t)*t*control[i] + t*t*target[i]
                         for i in (0, 1))

        def frame(step=0):
            if self._closing or not c.type(card_id) or not self.current_golden_map:
                c.delete(tag)
                return
            if step <= 6:
                # Gather light from the selected small card's centre.
                cx, cy = source
                radius = 17 - 11 * step / 6
                core_radius = 2 + 3 * step / 6
            elif step <= 28:
                t = (step - 6) / 22.0
                eased = t*t*(3-2*t)
                cx, cy = path(eased)
                tail = path(max(0.0, eased - .14))
                c.coords(trail, *tail, cx, cy)
                radius, core_radius = 8, 4
            else:
                # Contract into the original face before any gold is revealed.
                t = (step - 28) / 10.0
                cx, cy = target
                radius = 20 * (1-t)
                core_radius = 6 * (1-t)
                c.itemconfigure(trail, state='hidden')
            c.coords(halo, cx-radius, cy-radius, cx+radius, cy+radius)
            c.coords(core, cx-core_radius, cy-core_radius, cx+core_radius, cy+core_radius)
            c.tag_raise(tag)
            if step < 38:
                self._queue_animation(20, frame, step + 1)
            else:
                c.delete(tag)
                on_complete()

        frame()

    def _animate_dealt_golden_multiplier(self, hand_type, index, card, on_complete=None,
                                        fade_card_id=None):
        """Drop the multiplier and fade the fully opened card on the same clock."""
        multiplier = int(self.current_golden_map.get(tuple(card), 1))
        if self.game_mode not in ('treasure', 'xxx') or multiplier <= 1:
            if callable(on_complete):
                on_complete()
            return

        if self.game_mode in ('treasure', 'xxx'):
            self._golden_activated_slots[(hand_type, index)] = tuple(card)
            self.update_golden_bet_visuals()

        x, y = self.card_position(hand_type, index)
        rotated = index == 2
        card_w = 140 if rotated else 100

        # 相对 V1 版最终位置：
        # 向右移动 20px，向上移动 20px。
        base_end_x = x + card_w - 18
        base_end_y = y + 18

        end_x = base_end_x + 20
        end_y = base_end_y - 20

        # 第三张补牌是 90° 横向牌。
        # 如果补牌命中黄金牌，倍数圆的最终跌落位置额外向下移动 100px。
        if rotated:
            end_y += 100

        start_y = end_y - 48
        radius = 18

        card_tag = f'golden_card_{hand_type}_{index}'
        oval = self.canvas.create_oval(
            end_x - radius,
            start_y - radius,
            end_x + radius,
            start_y + radius,
            fill='white',
            outline='black',
            width=3,
            tags=('dealt_golden_multiplier', 'animation', card_tag)
        )

        text = self.canvas.create_text(
            end_x,
            start_y,
            text=f'{int(multiplier)}X',
            font=('Arial', 12, 'bold'),
            fill='black',
            tags=('dealt_golden_multiplier', 'animation', card_tag)
        )

        self.canvas.tag_raise(oval)
        self.canvas.tag_raise(text)

        steps = 18
        normal_face = golden_face = None
        if fade_card_id is not None and Image is not None and ImageTk is not None:
            normal_face = self._face_pil(card, hand_type, index, use_golden=False)
            golden_face = self._face_pil(card, hand_type, index)
            if normal_face is not None and golden_face is not None:
                if rotated:
                    normal_face = normal_face.rotate(90, expand=True)
                    golden_face = golden_face.rotate(90, expand=True)
                normal_face = normal_face.convert('RGBA')
                golden_face = golden_face.convert('RGBA')
                if golden_face.size != normal_face.size:
                    resample = getattr(Image, 'Resampling', Image).LANCZOS
                    golden_face = golden_face.resize(normal_face.size, resample)

        # The fade and badge share elapsed time, so rendering cost cannot make
        # their 1.5-second return animation drift apart or extend frame by frame.
        started_at = time.monotonic() if fade_card_id is not None else None

        def drop_step(step=0):
            if self._closing:
                return

            if fade_card_id is not None:
                elapsed_ms = (time.monotonic() - started_at) * 1000 if step else 0.0
                ratio = min(1.0, elapsed_ms / self.GOLDEN_RETURN_DURATION_MS)
            else:
                ratio = min(1.0, step / float(steps))

            if (fade_card_id is not None and normal_face is not None
                    and golden_face is not None):
                frame = Image.blend(normal_face, golden_face, ratio)
                photo = ImageTk.PhotoImage(frame, master=self)
                self._temp_flip_images[fade_card_id] = photo
                self.canvas.itemconfigure(fade_card_id, image=photo)

            # Ease-out：
            # 开始跌落较快，接近最终位置时逐渐减速。
            eased = 1.0 - (1.0 - ratio) ** 3
            cy = start_y + (end_y - start_y) * eased

            self.canvas.coords(
                oval,
                end_x - radius,
                cy - radius,
                end_x + radius,
                cy + radius
            )
            self.canvas.coords(text, end_x, cy)

            self.canvas.tag_raise(oval)
            self.canvas.tag_raise(text)

            if ratio < 1.0:
                delay = 20
                if fade_card_id is not None:
                    delay = max(1, min(delay, math.ceil(
                        self.GOLDEN_RETURN_DURATION_MS - elapsed_ms)))
                self._queue_animation(delay, drop_step, step + 1)
            else:
                if fade_card_id is not None:
                    final_image = self._face_photo(
                        card, rotated=rotated, hand_type=hand_type, index=index)
                    if final_image is not None:
                        self.canvas.itemconfigure(fade_card_id, image=final_image)
                    self._temp_flip_images.pop(fade_card_id, None)
                if callable(on_complete):
                    self._queue_animation(60, on_complete)

        drop_step(0)

    def _process_extra_cards_original(self):
        if self.current_result and len(self.current_result['player_hand']) > 2:
            self._deal_extra_card_original(
                'Player', 2,
                on_complete=lambda: self._queue_animation(80, self._process_banker_extra_original))
        else:
            self._process_banker_extra_original()

    def _process_banker_extra_original(self):
        if self.current_result and len(self.current_result['banker_hand']) > 2:
            self._deal_extra_card_original(
                'Banker', 2,
                on_complete=lambda: self._queue_animation(80, self.finish_deal))
        else:
            self.finish_deal()

    def _deal_extra_card_original(self, hand_type, index, on_complete=None):
        hand_key = 'player_hand' if hand_type == 'Player' else 'banker_hand'
        card = self.current_result[hand_key][index]

        def arrived(info):
            self._flip_card_original(info, card, on_complete=on_complete)

        self._animate_card_entrance_original(hand_type, index, rotated=True,
                                             on_arrive=arrived)

    def reveal_card(self, hand_type, index, card):
        """Compatibility helper; the main deal now uses the original animation."""
        if self._closing:
            return
        self.draw_card(hand_type, index, card, face_up=True)
        self.revealed_cards.setdefault(hand_type, []).append(card)
        score = BaccaratEngine.score(self.revealed_cards[hand_type])
        target = self.player_score_text if hand_type == 'Player' else self.banker_score_text
        self.canvas.itemconfigure(target, text=str(score))
        if self.game_mode == '2to1':
            self._update_2to1_multiplier_ribbon(use_revealed=True)

    def finish_deal(self):
        if self._closing or not self.current_result:
            return
        # A marker immediately behind the LAST card still needs its notice
        # before settlement, even though there is no further entrance to gate.
        if self._cut_card_notice_due():
            self._show_cut_card_notice(self.finish_deal)
            return
        self.animation_after_ids.clear()
        result = self.current_result
        self.canvas.itemconfigure(self.player_score_text, text=str(result['player_score']))
        self.canvas.itemconfigure(self.banker_score_text, text=str(result['banker_score']))

        # Lucky7 jackpot contribution follows the old project convention (0.8%).
        if self.game_mode == 'lucky7':
            self.jackpot_amount += sum(self.pre_deal_bets.values()) * 0.008
            self.save_jackpot()

        settle = BaccaratEngine.resolve_bets(
            self.pre_deal_bets, result, self.game_mode, self.jackpot_amount)
        self.balance += settle['credit']
        if settle['jackpot_win'] > 0:
            self.jackpot_amount = max(5_000_000.0, self.jackpot_amount - settle['jackpot_win'])
            self.save_jackpot()

        self.last_win_amount = settle['credit']
        self.last_net = settle['net'] - float(self.pre_deal_fee_total or 0.0)
        self.add_history(result)
        self.update_statistic_data(result)

        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.push_return_amounts = {}
        self.settlement_losing_amounts = {}
        self.settlement_profit_tags = {}
        self.settlement_chip_moves_started = False
        for outcome in settle['outcomes']:
            key = tuple(outcome['key'])
            if outcome['return_factor'] > 1.0:
                self.flash_winning_keys.add(key)
                self.flash_winner_amounts[key] = float(outcome['profit'])
                self.flash_original_amounts[key] = float(self.pre_deal_bets.get(key[0], 0.0))
            elif outcome['status'] == 'push':
                self.push_return_amounts[key[0]] = float(outcome['stake'])
            else:
                self.settlement_losing_amounts[key] = float(outcome['stake'])
        if settle['jackpot_win'] > 0:
            key = ('Super 7', None)
            self.flash_winner_amounts[key] = self.flash_winner_amounts.get(key, 0.0) + settle['jackpot_win']

        # Flash every objectively winning active side area too, even without a chip.
        for bet_type, factor in settle['side_factors'].items():
            key = (bet_type, None)
            if factor > 1.0 and key in self.bet_spots:
                self.flash_winning_keys.add(key)

        main_factor = BaccaratEngine.main_return_factor(result['winner'], result, self.game_mode)
        _ = main_factor  # compatibility no-op; winner area is handled explicitly below
        winner_key = (result['winner'], None)
        if result['winner'] in ('Player', 'Tie', 'Banker') and winner_key in self.bet_spots:
            factor = BaccaratEngine.main_return_factor(result['winner'], result, self.game_mode)
            if factor > 1.0:
                self.flash_winning_keys.add(winner_key)

        self._refresh_banker_bet_odds(result)

        # Every original stake keeps its amount. Losses depart at flash time
        # zero; winning and Push stakes remain until the final return flight.
        self.settlement_hold_amounts = {
            (bet_type, None): float(amount)
            for bet_type, amount in self.pre_deal_bets.items()
            if amount > 0
        }

        self.bet_state.bets.clear()
        self.summary_mode = 'win'
        self.result_panel_flash_winner = result['winner']
        self.canvas.itemconfigure(self.animation_phase_text, text='百家乐 BACCARAT')
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')

        self.accept_bets = False
        self.settlement_running = True
        self.animation_running = False
        self.flash_mode = None
        self.update_display()
        self.save_balance()

        if settle['jackpot_win'] > 0:
            messagebox.showinfo('累进大奖',
                                f"恭喜！获得大奖 {self.format_money(settle['jackpot_win'])}",
                                parent=self.winfo_toplevel())

        # Always flash the winning card zone, even when the player placed no
        # wager on the winning outcome. Betting areas still flash when applicable.
        self.settlement_flash_step = 0
        self.run_settlement_flash()

    def _sync_golden_badges_for_flash(self, light_phase):
        """Make Treasure golden odds badges flash with their winning areas."""
        if self.game_mode not in ('treasure', 'xxx'):
            return
        for key in self.flash_winning_keys:
            spot = self.bet_spots.get(key)
            if not spot:
                continue
            tag = spot.get('tag')
            if not tag:
                continue
            for item_id in self.canvas.find_withtag(tag):
                try:
                    tags = self.canvas.gettags(item_id)
                    if 'golden_bet_dynamic' not in tags:
                        continue
                    item_type = self.canvas.type(item_id)
                    if item_type == 'oval':
                        self.canvas.itemconfigure(
                            item_id,
                            fill='#fff8cf' if light_phase else '#e3b51d',
                            outline='#111111' if light_phase else '#fff2a3',
                            width=3 if light_phase else 2)
                    elif item_type == 'text':
                        self.canvas.itemconfigure(
                            item_id, fill='#000000' if light_phase else '#201700')
                    self.canvas.tag_raise(item_id)
                except tk.TclError:
                    pass

    def _sync_treasure_rule_table_flash(self, light_phase):
        """Flash the winning Golden Hunter / Golden Duel odds cell.

        The temporary rule table follows the exact same settlement phase as the
        corresponding betting area.  Normal phase = original dark background and
        gold odds text; highlight phase = gold background and black odds text.
        """
        cells = getattr(self, 'treasure_panel_rule_cells', {})
        if not cells or not getattr(self, 'treasure_panel_active', False):
            return

        # Restore every row first so only the highest/actual payable row flashes.
        for bg_item, text_item in cells.values():
            try:
                self.canvas.itemconfigure(bg_item, fill='#211811')
                self.canvas.itemconfigure(text_item, fill='#ffd84a')
            except tk.TclError:
                pass

        if self.game_mode == 'treasure':
            bet_type = 'Golden Hunter'
            tier = BaccaratEngine.golden_hit_count(self.current_result or {})
        elif self.game_mode == 'xxx':
            bet_type = 'Golden Duel'
            tier = BaccaratEngine.golden_duel_tier(self.current_result or {})
        else:
            return

        # Match the betting-area flash exactly: no table flash unless that side-bet
        # area is part of this settlement's winning flash set.
        if (bet_type, None) not in self.flash_winning_keys:
            return
        cell = cells.get(int(tier or 0))
        if not cell:
            return
        bg_item, text_item = cell
        try:
            self.canvas.itemconfigure(
                bg_item, fill='#ffd84a' if light_phase else '#211811')
            self.canvas.itemconfigure(
                text_item, fill='#000000' if light_phase else '#ffd84a')
            self.canvas.tag_raise(text_item)
        except tk.TclError:
            pass

    def run_settlement_flash(self):
        if self._closing or not self.settlement_running:
            return
        if self.settlement_flash_step == 0:
            self._start_settlement_chip_movements()
            if self.game_mode == 'tiger':
                self._start_tiger_symbol_transition()
            elif self.game_mode == 'lucky7':
                self._start_lucky6_pop()
        if self.settlement_flash_step >= 6:
            self.settlement_after_id = None
            # V23: after the final flash, actual winning-return chips visibly
            # travel back to the bottom chip rack before settlement is cleared.
            if not self._start_winning_chip_return():
                self.finish_settlement()
            return
        self.flash_mode = 'win' if self.settlement_flash_step % 2 == 0 else 'original'
        self.flash_result_panels(self.settlement_flash_step % 2 == 0)
        self.canvas.delete('win_flash_area')
        if self.flash_mode == 'original':
            self.restore_flash_text_colors()
            if self.game_mode in ('classic', '2to1', 'monkey', 'ez', 'tiger', 'lucky7', 'goldendice', 'treasure', 'xxx', 'one_deck') + BaccaratEngine.ALWAYS_MODES:
                self.canvas.tag_raise('bet_board_frame')
                if self.game_mode == 'ez':
                    cover = self.bet_spots.get(('Cover All', None))
                    if cover:
                        self.canvas.tag_raise(cover['tag'])
            self._sync_golden_badges_for_flash(False)
            self._sync_treasure_rule_table_flash(False)
        else:
            for key in self.flash_winning_keys:
                spot = self.bet_spots.get(key)
                if not spot:
                    continue
                if self.game_mode == 'tiger' and key[0] == 'Tiger':
                    # The central icon has its own continuous downward wipe;
                    # it never participates in the alternating white flashes.
                    continue
                if self.game_mode == 'lucky7' and key[0] == 'Lucky 6':
                    # Gold rings pulse outside the chip on a red face,
                    # independently of the rectangular wager flashes.
                    continue
                x0, y0, x1, y1 = spot['bounds']
                if self.game_mode == 'ez' and 'ez_shape' in spot:
                    flash_tags = ('win_flash_area', 'settlement_flash')
                    if key[0] == 'Cover All':
                        flash_tags += ('ez_cover_win_flash',)
                    shape = spot['ez_shape_coords']
                    if spot['ez_shape'] == 'oval':
                        self.canvas.create_oval(*shape, fill='#ffffff', outline='#111111',
                                                width=2, tags=flash_tags)
                    else:
                        self.canvas.create_polygon(*shape, smooth=True, fill='#ffffff',
                                                   outline='', width=0, tags=flash_tags)
                elif 'classic_shape_coords' in spot:
                    self.canvas.create_polygon(*spot['classic_shape_coords'], smooth=True,
                                               fill='#ffffff', outline='', width=0,
                                               tags=('win_flash_area', 'settlement_flash'))
                elif self.game_mode in ('tiger', 'lucky7'):
                    self.canvas.create_rectangle(x0, y0, x1, y1, fill='#ffffff',
                                                 outline='', width=0,
                                                 tags=('win_flash_area', 'settlement_flash'))
                else:
                    self.canvas.create_rectangle(x0, y0, x1, y1, fill='#ffffff',
                                                 outline='#111111', width=2,
                                                 tags=('win_flash_area', 'settlement_flash'))
                self.raise_spot_content_above_flash(spot)
            # One-deck uses the same frame layers as Classic: keep both the
            # outer outline and inner ornament above the white flash overlay.
            if self.game_mode in ('classic', '2to1', 'monkey', 'ez', 'tiger', 'lucky7', 'goldendice', 'treasure', 'xxx', 'one_deck') + BaccaratEngine.ALWAYS_MODES:
                self.canvas.tag_raise('bet_board_frame')
            if self.game_mode == 'ez':
                # The centre medal must remain above adjacent panel flashes.
                cover = self.bet_spots.get(('Cover All', None))
                if cover:
                    self.canvas.tag_raise(cover['tag'])
                    if ('Cover All', None) in self.flash_winning_keys:
                        self.canvas.tag_raise('ez_cover_win_flash')
                        # Only the round medal flashes. The fixed black border
                        # and arrowheads stay over its text but below chips.
                        self.canvas.tag_raise('ez_cover_outline')
                        self.raise_spot_content_above_flash(cover)
            # Re-style + raise the golden badges after the white flash layer is
            # created, so the badge itself visibly participates in the flash.
            self._sync_golden_badges_for_flash(True)
            self._sync_treasure_rule_table_flash(True)
        if self.game_mode == 'tiger':
            self._raise_tiger_symbol()
        elif self.game_mode == 'lucky7':
            self._raise_lucky6_symbol()
        self.update_bet_chips()
        if self.game_mode in ('goldendice', '2to1', 'treasure', 'xxx'):
            # Re-raise the complete bands after the white settlement flash,
            # then keep wager chips and squeeze cards above them.
            self.canvas.tag_raise('multiplier_ribbon')
        self.canvas.tag_raise('bet_chip_dynamic')
        self.canvas.tag_raise('squeeze_backdrop')
        self.canvas.tag_raise('chip_motion')
        self.canvas.tag_raise('controls')
        self.settlement_flash_step += 1
        self.settlement_after_id = self.after(450, self.run_settlement_flash)

    def _set_zone_text_colors(self, player_color=None, banker_color=None):
        """Set title + score colors together for each dealing zone."""
        if player_color is not None:
            for item in (getattr(self, 'player_zone_label', None),
                         getattr(self, 'player_score_text', None)):
                if item is not None:
                    self.canvas.itemconfigure(item, fill=player_color)
        if banker_color is not None:
            for item in (getattr(self, 'banker_zone_label', None),
                         getattr(self, 'banker_score_text', None)):
                if item is not None:
                    self.canvas.itemconfigure(item, fill=banker_color)

    def flash_result_panels(self, light_phase):
        """Flash winner card zones without ever hiding the point values.

        Highlight phase:
          * Player win -> pale blue, black title + black score.
          * Banker win -> pale red, black title + black score.
          * Tie -> both pale green, black titles + black scores.

        Normal phase:
          * Restore the original dark Player/Banker panel colours.
          * Restore the normal Player/Banker title colours.
          * Scores are always WHITE on the normal table.
        """
        winner = self.result_panel_flash_winner
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')

        # Every frame begins from the real normal-table appearance.
        self.canvas.itemconfigure(self.player_zone_rect, fill=self.PLAYER_ZONE_BASE,
                                  outline='#6386a5')
        self.canvas.itemconfigure(self.banker_zone_rect, fill=self.BANKER_ZONE_BASE,
                                  outline='#a56a6d')
        self._set_zone_text_colors('#93b9ff', '#ffaaaa')
        self.canvas.itemconfigure(self.player_score_text, fill='white')
        self.canvas.itemconfigure(self.banker_score_text, fill='white')

        # Only the highlight frame overrides the winning zone.  The normal
        # frame intentionally needs no extra override, so the large score
        # never disappears between flashes.
        if winner == 'Player' and light_phase:
            self.canvas.itemconfigure(self.player_zone_rect, fill=self.PLAYER_ZONE_LIGHT,
                                      outline='#e3f6ff')
            self._set_zone_text_colors(player_color='black')

        elif winner == 'Banker' and light_phase:
            self.canvas.itemconfigure(self.banker_zone_rect, fill=self.BANKER_ZONE_LIGHT,
                                      outline='#ffe8ea')
            self._set_zone_text_colors(banker_color='black')

        elif winner == 'Tie' and light_phase:
            self.canvas.itemconfigure(self.player_zone_rect, fill=self.TIE_FLASH_LIGHT,
                                      outline='#dcffe6')
            self.canvas.itemconfigure(self.banker_zone_rect, fill=self.TIE_FLASH_LIGHT,
                                      outline='#dcffe6')
            self._set_zone_text_colors('black', 'black')

    def restore_result_panel_colors(self):
        """Restore the normal dark Player/Banker dealing-zone palette."""
        if hasattr(self, 'player_zone_rect'):
            self.canvas.itemconfigure(self.player_zone_rect, fill=self.PLAYER_ZONE_BASE,
                                      outline='#6386a5')
        if hasattr(self, 'banker_zone_rect'):
            self.canvas.itemconfigure(self.banker_zone_rect, fill=self.BANKER_ZONE_BASE,
                                      outline='#a56a6d')
        if hasattr(self, 'player_zone_label'):
            self.canvas.itemconfigure(self.player_zone_label, fill='#93b9ff')
        if hasattr(self, 'banker_zone_label'):
            self.canvas.itemconfigure(self.banker_zone_label, fill='#ffaaaa')
        if hasattr(self, 'player_score_text'):
            self.canvas.itemconfigure(self.player_score_text, fill='white')
        if hasattr(self, 'banker_score_text'):
            self.canvas.itemconfigure(self.banker_score_text, fill='white')
        if hasattr(self, 'tie_flash_rect'):
            self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')

    def raise_spot_content_above_flash(self, spot):
        tag = spot.get('tag')
        if not tag:
            return
        for item_id in self.canvas.find_withtag(tag):
            try:
                item_type = self.canvas.type(item_id)
                tags = self.canvas.gettags(item_id)
            except tk.TclError:
                continue
            if 'win_flash_area' in tags or 'bet_chip_dynamic' in tags:
                continue
            if item_type == 'text':
                if item_id not in self.flash_original_text_colors:
                    self.flash_original_text_colors[item_id] = self.canvas.itemcget(item_id, 'fill')
                self.canvas.itemconfigure(item_id, fill='black')
                self.canvas.tag_raise(item_id)

    def restore_flash_text_colors(self):
        for item_id, color in list(self.flash_original_text_colors.items()):
            try:
                self.canvas.itemconfigure(item_id, fill=color)
            except tk.TclError:
                pass
        self.flash_original_text_colors.clear()

    def finish_settlement(self):
        if self._closing:
            return
        if self.game_mode == 'one_deck':
            self.one_deck_engine.finish_round()
        elif self.game_mode in BaccaratEngine.ALWAYS_MODES:
            self.fixed_engine.finish_round()
        if self.game_mode == 'tiger':
            self._cancel_tiger_symbol_transition(reset=True)
        elif self.game_mode == 'lucky7':
            self._cancel_lucky6_pop(reset=True)
        self._clear_squeeze_backdrop()
        self.settlement_after_id = None
        self.canvas.delete('win_flash_area')
        self.restore_flash_text_colors()
        self.restore_result_panel_colors()
        self.canvas.itemconfigure(self.tie_flash_rect, state='hidden')
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.canvas.delete('settlement_profit')
        self.settlement_profit_tags.clear()
        self.settlement_losing_amounts = {}
        self.settlement_chip_moves_started = False
        self.settlement_hold_amounts = {}
        self.push_return_amounts = {}
        self.settlement_return_animating = False
        self.settlement_return_keys.clear()
        self.pending_bet_visual_amounts.clear()
        self.pre_deal_bets = None
        self.settlement_running = False
        self.animation_running = False
        self.canvas.itemconfigure(self.animation_phase_text, text='百家乐 BACCARAT')
        self.canvas.delete('multiplier_ribbon')
        if self.game_mode == '2to1':
            self._update_2to1_multiplier_ribbon()
        if self.game_mode in ('treasure', 'xxx', 'goldendice'):
            if self.game_mode != 'goldendice':
                self._hide_treasure_panel()
            self.current_golden_cards = []
            self.current_golden_map = {}
            if self.game_mode in ('goldendice', 'treasure', 'xxx'):
                self._golden_dice_fee_collected = False
            if self.game_mode == 'goldendice':
                self.golden_dice_active = False
                self._golden_dice_roll_ready = False
                self._golden_dice_reels_ready = set()
                # Keep the last valid positions and upward faces for the next
                # round and for leaving/re-entering this mode.
                self.canvas.itemconfigure(self.golden_dice_status_text,
                                          text='8/9点使用加强倍数', fill='#e6d9b6')
            self.treasure_pot_amount = 0.0
            self.update_golden_bet_visuals()
            self._refresh_treasure_pool_text()
        if self.engine.needs_shuffle():
            self.accept_bets = False
            self.update_display()
            self.after(350, lambda: self.start_new_shoe_cut(True))
        else:
            self.accept_bets = True
            self.update_display()
        self._refresh_banker_bet_odds()

    @classmethod
    def result_color(cls, winner):
        return {'Player': cls.PLAYER_BLUE, 'Banker': cls.BANKER_RED,
                'Tie': cls.TIE_GREEN}.get(winner, '#888888')

    @staticmethod
    def result_description(result):
        winner_text = {'Player': '闲胜', 'Banker': '庄胜', 'Tie': '和局'}.get(result['winner'], result['winner'])
        natural = ' · 天牌' if result.get('natural') else ''
        return f"{winner_text}  闲{result['player_score']} : 庄{result['banker_score']}{natural}"

    # ------------------------------------------------------------------ history
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
    def _default_statistic_data():
        return {'total_game': 0, 'player_win': 0, 'banker_win': 0, 'tie_win': 0}

    @classmethod
    def new_runtime_store(cls):
        return {
            'temp_data': {},
            'temp_finish_data': cls.new_history_store(),
            'statistic_data': cls._default_statistic_data(),
        }

    def _write_runtime_store(self):
        """Persist the normal modes in Baccarat.json; single-deck data stays in Special."""
        try:
            os.makedirs(os.path.dirname(self.runtime_data_file), exist_ok=True)
            temp_path = self.runtime_data_file + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as handle:
                json.dump(self.runtime_store, handle, ensure_ascii=False, indent=4)
            os.replace(temp_path, self.runtime_data_file)
        except OSError as exc:
            print(f'保存 Baccarat 失败：{exc}')

    def load_runtime_store(self):
        """Load the single V14 runtime JSON, migrating the three legacy files once.

        Structure::
            {
              "temp_data": {...416-card shoe/current_index...},
              "temp_finish_data": {"records": [...]},
              "statistic_data": {"total_game": ..., ...}
            }
        """
        store = self.new_runtime_store()
        loaded_combined = False
        raw = {}
        try:
            with open(self.runtime_data_file, 'r', encoding='utf-8') as handle:
                raw = json.load(handle)
            if isinstance(raw, dict):
                # Preserve unknown/old sections, but never use old One_Deck
                # copies here in preference to Baccarat_Special.json.
                for key, value in raw.items():
                    if key not in store or isinstance(value, dict):
                        store[key] = value
                loaded_combined = True
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

        if not loaded_combined:
            # Preserve existing V13 data by importing the old three-file format.
            legacy_specs = (
                ('temp_data', self.legacy_temp_data_file),
                ('temp_finish_data', self.legacy_temp_finish_data_file),
                ('statistic_data', self.legacy_statistic_data_file),
            )
            migrated = False
            for key, path in legacy_specs:
                try:
                    with open(path, 'r', encoding='utf-8') as handle:
                        value = json.load(handle)
                    if isinstance(value, dict):
                        store[key] = value
                        migrated = True
                except (FileNotFoundError, json.JSONDecodeError, OSError):
                    pass
            try:
                os.makedirs(os.path.dirname(self.runtime_data_file), exist_ok=True)
                with open(self.runtime_data_file, 'w', encoding='utf-8') as handle:
                    json.dump(store, handle, ensure_ascii=False, indent=4)
                # Once safely migrated, remove the obsolete split files so only
                # the single combined JSON remains in active use.
                if migrated:
                    for _key, path in legacy_specs:
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                        except OSError:
                            pass
            except OSError as exc:
                print(f'建立 Baccarat 失败：{exc}')
        return store

    @classmethod
    def new_one_deck_runtime_store(cls, mode='one_deck'):
        prefix = BaccaratEngine.SPECIAL_PREFIXES[mode]
        return {prefix+'_temp_finish_data': cls.new_history_store(),
                prefix+'_72_games': cls.new_history_store(),
                prefix+'_statistic_data': cls._default_statistic_data()}

    def _read_one_deck_document(self):
        try:
            with open(self.one_deck_data_file, 'r', encoding='utf-8') as handle:
                document = json.load(handle)
        except FileNotFoundError:
            return {}
        if not isinstance(document, dict):
            raise ValueError('Baccarat_Special.json 的顶层数据必须是对象。')
        return document

    def load_one_deck_runtime_store(self, mode=None):
        """Load only the chosen Special mode's independent 500/72/stat sections."""
        mode = mode or self.game_mode
        if mode not in BaccaratEngine.SPECIAL_MODES:
            mode = 'one_deck'
        prefix = BaccaratEngine.SPECIAL_PREFIXES[mode]
        document = self._read_one_deck_document()
        store = self.new_one_deck_runtime_store(mode)
        store[prefix+'_temp_finish_data'] = self.normalize_one_deck_history_store(
            document.get(prefix+'_temp_finish_data'), mode)
        store[prefix+'_72_games'] = self.normalize_one_deck_bead_store(
            document.get(prefix+'_72_games'), mode)
        stats = self._default_statistic_data()
        raw_stats = document.get(prefix+'_statistic_data')
        if isinstance(raw_stats, dict):
            for key in stats:
                try:
                    stats[key] = max(0, int(raw_stats.get(key, 0)))
                except (TypeError, ValueError):
                    pass
        else:
            records = store[prefix+'_temp_finish_data']['records']
            stats['total_game'] = len(records)
            for winner, key in (('Player', 'player_win'), ('Banker', 'banker_win'), ('Tie', 'tie_win')):
                stats[key] = sum(record['winner'] == winner for record in records)
        store[prefix+'_statistic_data'] = stats
        self.one_deck_store = store
        if any(value != document.get(key) for key, value in store.items()):
            self._write_one_deck_runtime_store()
        return store

    def _write_one_deck_runtime_store(self, sections=None):
        """Update only requested selected Special sections, preserving all other Special data."""
        try:
            # Re-read before writing so an unrelated Special mode's latest
            # saved sections are not overwritten by our earlier snapshot.
            document = self._read_one_deck_document()
            keys = tuple(self.one_deck_store) if sections is None else sections
            for key in keys:
                document[key] = copy.deepcopy(self.one_deck_store[key])
            os.makedirs(os.path.dirname(self.one_deck_data_file), exist_ok=True)
            temp_path = self.one_deck_data_file + '.baccarat.tmp'
            with open(temp_path, 'w', encoding='utf-8') as handle:
                json.dump(document, handle, ensure_ascii=False, indent=4)
            os.replace(temp_path, self.one_deck_data_file)
            return True
        except (OSError, ValueError) as exc:
            print(f'保存 Baccarat_Special 独立模式数据失败：{exc}')
            return False

    def _mode_storage_key(self, section):
        prefix = BaccaratEngine.SPECIAL_PREFIXES.get(self.game_mode)
        return (prefix+'_' if prefix else '') + section

    def _mode_runtime_store(self):
        return (self.one_deck_store if self.game_mode in BaccaratEngine.SPECIAL_MODES
                else self.runtime_store)

    def _history_limit(self):
        return self.MAX_RECORDS

    @classmethod
    def _trim_one_deck_bead_records(cls, records):
        """Only Marker Road drops complete columns: hand 73 leaves hands 7..73."""
        overflow = len(records) - cls.ONE_DECK_BEAD_RECORDS
        if overflow > 0:
            batch = cls.ONE_DECK_BEAD_TRIM_BATCH
            del records[:((overflow + batch - 1) // batch) * batch]

    @classmethod
    def normalize_one_deck_history_store(cls, data, mode='one_deck'):
        normalized = cls.normalize_history_store(data, cls.MAX_RECORDS)
        for record in normalized['records']:
            record['mode'] = mode
            for side in ('player', 'banker'):
                hand = record.get(side + '_hand') or []
                if (isinstance(hand, (list, tuple)) and len(hand) >= 2
                        and all(isinstance(card, (list, tuple)) and len(card) == 2
                                for card in hand[:2])):
                    record[side + '_pair'] = hand[0][1] == hand[1][1]
        return normalized

    @classmethod
    def normalize_one_deck_bead_store(cls, data, mode='one_deck'):
        normalized = cls.normalize_one_deck_history_store(data, mode)
        cls._trim_one_deck_bead_records(normalized['records'])
        return normalized

    def load_bead_store(self):
        if self.game_mode not in BaccaratEngine.SPECIAL_MODES:
            return self.new_history_store()
        return self.normalize_one_deck_bead_store(
            self.one_deck_store.get(self._mode_storage_key('72_games')), self.game_mode)

    def bead_records_from_store(self):
        return list(self.bead_store.get('records', []))

    def get_history_file(self):
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            return self.one_deck_data_file
        return self.runtime_data_file

    def load_temp_data(self):
        try:
            data = self.runtime_store.get('temp_data', {})
            if not isinstance(data, dict):
                return False
            deck = data.get('deck', [])
            index = int(data.get('current_index', 0))
            threshold = int(data.get('cut_threshold', 60))
            burn_complete = bool(data.get('burn_complete', False))
            if (not isinstance(deck, list) or len(deck) != 416 or not burn_complete
                    or not (0 <= index <= 416) or not (50 <= threshold <= 80)):
                return False
            normalized = []
            for card in deck:
                if not isinstance(card, (list, tuple)) or len(card) != 2:
                    return False
                suit, rank = str(card[0]), str(card[1])
                if suit not in BaccaratEngine.SUITS or rank not in BaccaratEngine.RANKS:
                    return False
                normalized.append((suit, rank))
            self.standard_engine.set_shoe_state(normalized, index, threshold)
            return self.standard_engine.remaining_cards() > self.standard_engine.cut_threshold
        except (TypeError, ValueError):
            return False

    def save_temp_data(self, burn_complete=True):
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            return
        golden_state = self.runtime_store.get('temp_data', {}).get('golden_dice_state')
        self.runtime_store['temp_data'] = {
            'deck': [list(card) for card in self.engine.deck],
            'current_index': int(self.engine.current_index),
            'cut_threshold': int(self.engine.cut_threshold),
            'remaining_cards': int(self.engine.remaining_cards()),
            'burn_complete': bool(burn_complete),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        if golden_state is not None:
            self.runtime_store['temp_data']['golden_dice_state'] = golden_state
        self._write_runtime_store()

    @classmethod
    def new_history_store(cls):
        return {'records': []}

    @classmethod
    def normalize_history_store(cls, data, limit=None):
        normalized = cls.new_history_store()
        if not isinstance(data, dict):
            return normalized
        raw_records = data.get('records', [])
        if not isinstance(raw_records, list):
            return normalized
        for record in raw_records[-(cls.MAX_RECORDS if limit is None else limit):]:
            if not isinstance(record, dict):
                continue
            winner = record.get('winner')
            if winner not in ('Player', 'Tie', 'Banker'):
                continue
            try:
                ps = int(record.get('player_score', 0))
                bs = int(record.get('banker_score', 0))
            except (TypeError, ValueError):
                continue
            item = copy.deepcopy(record)
            item['player_score'] = ps
            item['banker_score'] = bs
            normalized['records'].append(item)
        return normalized

    def load_history_store(self):
        raw = self._mode_runtime_store().get(self._mode_storage_key('temp_finish_data'), self.new_history_store())
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            return self.normalize_one_deck_history_store(raw, self.game_mode)
        return self.normalize_history_store(raw, self._history_limit())

    def save_history_store(self):
        self._mode_runtime_store()[self._mode_storage_key('temp_finish_data')] = copy.deepcopy(self.history_store)
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            self.one_deck_store[self._mode_storage_key('72_games')] = copy.deepcopy(self.bead_store)
            self._write_one_deck_runtime_store((self._mode_storage_key('temp_finish_data'),
                                               self._mode_storage_key('72_games')))
        else:
            self._write_runtime_store()

    def history_records_from_store(self):
        return list(self.history_store.get('records', []))

    def clear_temp_finish_data(self):
        """Clear current-shoe completed hands but preserve shoe/statistic sections."""
        self.history_store = self.new_history_store()
        self.history_data = []
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            self.bead_store = self.new_history_store()
            self.bead_data = []
        self.save_history_store()
        self.update_history_table()

    def clear_shoe_temp_sections(self):
        """Player cut: delete BOTH temporary sections, never lifetime statistics."""
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            return
        self.runtime_store['temp_data'] = {}
        self.runtime_store['temp_finish_data'] = self.new_history_store()
        self.history_store = self.new_history_store()
        self.history_data = []
        self.big_road_scroll_col = 0
        self.big_road_auto_follow = True
        self._write_runtime_store()
        self.update_history_table()

    def add_history(self, result):
        player_pair, banker_pair = BaccaratEngine._pair_flags(result)
        special_by_mode = {}
        modes = (self.game_mode,) if self.game_mode in BaccaratEngine.SPECIAL_MODES else tuple(
            mode for mode in self.MODE_ORDER if mode not in BaccaratEngine.SPECIAL_MODES)
        for mode in modes:
            factors = BaccaratEngine.side_return_factors(result, mode)
            special_by_mode[mode] = [name for name, factor in factors.items() if factor > 1.0]
        record = {
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'winner': result['winner'],
            'player_score': int(result['player_score']),
            'banker_score': int(result['banker_score']),
            'natural': bool(result.get('natural', False)),
            'mode': self.game_mode,
            'banker_rule': result.get('_banker_rule', self._current_banker_rule()),
            'golden_selection_count': BaccaratEngine.golden_selection_count(result),
            'player_pair': bool(player_pair),
            'banker_pair': bool(banker_pair),
            'specials': special_by_mode.get(self.game_mode, []),
            'special_by_mode': special_by_mode,
            'player_hand': [list(card) for card in result.get('player_hand', [])],
            'banker_hand': [list(card) for card in result.get('banker_hand', [])],
        }
        records = self.history_store.setdefault('records', [])
        records.append(record)
        # A new result always brings Big Road navigation back to the newest data.
        self.big_road_auto_follow = True
        limit = self._history_limit()
        if len(records) > limit:
            del records[:-limit]
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            bead_records = self.bead_store.setdefault('records', [])
            bead_records.append(copy.deepcopy(record))
            self._trim_one_deck_bead_records(bead_records)
            self.bead_data = self.bead_records_from_store()
        self.save_history_store()
        self.history_data = self.history_records_from_store()

    def load_statistic_data(self):
        defaults = self._default_statistic_data()
        storage_key = self._mode_storage_key('statistic_data')
        store = self._mode_runtime_store()
        raw = store.get(storage_key, {})
        if isinstance(raw, dict):
            for key in ('total_game', 'player_win', 'banker_win', 'tie_win'):
                try:
                    defaults[key] = max(0, int(raw.get(key, 0)))
                except (TypeError, ValueError):
                    defaults[key] = 0
        had_legacy_treasure_value = isinstance(raw, dict) and 'treasure_pot' in raw
        store[storage_key] = dict(defaults)
        if had_legacy_treasure_value:
            # V20 migration: Treasure Pot is a per-round UI amount, not a
            # lifetime statistic. Remove the obsolete stored key immediately.
            if self.game_mode in BaccaratEngine.SPECIAL_MODES:
                self._write_one_deck_runtime_store((storage_key,))
            else:
                self._write_runtime_store()
        return defaults

    def save_statistic_data(self):
        # Lifetime statistics only. Treasure Pot fees are strictly per-round
        # display state and must never enter the JSON store.
        storage_key = self._mode_storage_key('statistic_data')
        store = self._mode_runtime_store()
        store[storage_key] = {
            'total_game': max(0, int(self.statistic_data.get('total_game', 0))),
            'player_win': max(0, int(self.statistic_data.get('player_win', 0))),
            'banker_win': max(0, int(self.statistic_data.get('banker_win', 0))),
            'tie_win': max(0, int(self.statistic_data.get('tie_win', 0))),
        }
        self.statistic_data = dict(store[storage_key])
        if self.game_mode in BaccaratEngine.SPECIAL_MODES:
            self._write_one_deck_runtime_store((storage_key,))
        else:
            self._write_runtime_store()

    def update_statistic_data(self, result):
        self.statistic_data['total_game'] = int(self.statistic_data.get('total_game', 0)) + 1
        if result['winner'] == 'Player':
            self.statistic_data['player_win'] = int(self.statistic_data.get('player_win', 0)) + 1
        elif result['winner'] == 'Banker':
            self.statistic_data['banker_win'] = int(self.statistic_data.get('banker_win', 0)) + 1
        else:
            self.statistic_data['tie_win'] = int(self.statistic_data.get('tie_win', 0)) + 1
        self.save_statistic_data()

    def get_jackpot_file(self):
        return str(_progressive_file)

    def load_jackpot(self):
        try:
            with open(self.jackpot_file, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get('Games') == 'BCT':
                        return max(5_000_000.0, float(item.get('jackpot', 5_000_000)))
            elif isinstance(data, dict) and data.get('Games') == 'BCT':
                return max(5_000_000.0, float(data.get('jackpot', 5_000_000)))
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
        return 5_000_000.0

    def save_jackpot(self):
        try:
            if os.path.exists(self.jackpot_file):
                with open(self.jackpot_file, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
            else:
                data = []
            if not isinstance(data, list):
                data = []
            found = False
            for item in data:
                if isinstance(item, dict) and item.get('Games') == 'BCT':
                    item['jackpot'] = float(self.jackpot_amount)
                    found = True
                    break
            if not found:
                data.append({'Games': 'BCT', 'jackpot': float(self.jackpot_amount)})
            with open(self.jackpot_file, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, indent=4)
        except (OSError, json.JSONDecodeError):
            pass

    # ---------------------------------------------------------------- lifecycle
    def _restore_enter_binding(self, event):
        if event.widget is not self:
            return
        binding_id = getattr(self, '_enter_binding_id', None)
        if not binding_id:
            return
        self._enter_binding_id = None
        top = self._enter_window
        try:
            if binding_id in (top.bind('<Return>') or ''):
                top.bind('<Return>', self._previous_enter_binding)
            top.deletecommand(binding_id)
        except tk.TclError:
            pass

    def save_balance(self):
        if self.username:
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

    def cancel_pending_callbacks(self):
        self._cancel_mode_transition()
        for control in self.__dict__.get('_segmented_controls', {}).values():
            control['generation'] += 1
            if control.get('after') is not None:
                try:
                    self.after_cancel(control['after'])
                except (tk.TclError, ValueError):
                    pass
                control['after'] = None
        dialog = self._cut_dialog
        if dialog is not None:
            close_scene = getattr(dialog, '_close_cut_scene', None)
            if close_scene is not None:
                close_scene()
        self._clear_cut_card_notice()
        if self.__dict__.get('_tiger_symbol_after_id') is not None:
            self._cancel_tiger_symbol_transition()
        if self.__dict__.get('_lucky6_pop_after_id') is not None:
            self._cancel_lucky6_pop()
        if self.__dict__.get('_lucky7_jackpot_after_id') is not None:
            self._cancel_lucky7_jackpot_counter()
        self._clear_squeeze_display()
        for after_id in list(self.animation_after_ids):
            try:
                self.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
        self.animation_after_ids.clear()
        for after_id in list(self.chip_motion_after_ids):
            try:
                self.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
        self.chip_motion_after_ids.clear()
        self._cancel_fee_visuals()
        try:
            self.canvas.delete('chip_motion')
        except (tk.TclError, AttributeError):
            pass
        if self.settlement_after_id is not None:
            try:
                self.after_cancel(self.settlement_after_id)
            except (tk.TclError, ValueError):
                pass
            self.settlement_after_id = None
        if self.reshuffle_confirm_after_id is not None:
            try:
                self.after_cancel(self.reshuffle_confirm_after_id)
            except (tk.TclError, ValueError):
                pass
            self.reshuffle_confirm_after_id = None
        self.reshuffle_confirm_armed = False

    def on_close(self):
        self.exit_game()

    def exit_game(self):
        if self._closing:
            return
        self._closing = True
        self.cancel_pending_callbacks()
        self.animation_running = False
        self.accept_bets = False
        outstanding = self.bet_state.total_at_risk()
        fee_refund = sum(float(v) for v in self.bet_fee_state.values())
        if outstanding > 0 or fee_refund > 0:
            self.balance += outstanding + fee_refund
            if fee_refund > 0:
                self.treasure_pot_amount = max(0.0, self.treasure_pot_amount - fee_refund)
        self.bet_fee_state.clear()
        self.bet_state.bets.clear()
        self.final_balance = float(self.balance)
        try:
            self.save_balance()
        except Exception:
            pass
        try:
            self.fixed_engine.release_all_cards(force_shuffle=False)
        except Exception as exc:
            print(f'固定牌 CSM 退出归还失败：{exc}')
        if callable(self.on_back):
            self.on_back(self.final_balance)


# Backward-style wrapper for projects that expect a game class taking root.
class BaccaratGame(BubbleBaccaratGame):
    def __init__(self, root, username=None, initial_balance=10000,
                 on_back=None, on_balance_change=None, game_mode='classic'):
        super().__init__(
            parent=root,
            balance=initial_balance,
            user=username,
            on_back=on_back,
            on_balance_change=on_balance_change,
            game_mode=game_mode,
        )
        self.pack(fill=tk.BOTH, expand=True)

def main(parent=None, balance=10000, user=None, on_back=None,
         on_balance_change=None, username=None, game_mode='classic'):
    if username is not None and user is None:
        user = username

    # Compatibility with legacy main(balance, username) style calls.
    if parent is not None and not isinstance(parent, tk.Misc):
        legacy_balance = parent
        legacy_user = balance if isinstance(balance, str) and user is None else user
        parent = None
        balance = legacy_balance
        user = legacy_user

    if parent is not None:
        return BubbleBaccaratGame(
            parent=parent,
            balance=balance,
            user=user,
            on_back=on_back,
            on_balance_change=on_balance_change,
            game_mode=game_mode,
        )

    root = tk.Tk()
    root.title('百家乐')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)

    def close_standalone(final_balance):
        _ = final_balance
        try:
            root.destroy()
        except tk.TclError:
            pass

    game = BubbleBaccaratGame(
        parent=root,
        balance=balance,
        user=user,
        on_back=on_back or close_standalone,
        on_balance_change=on_balance_change,
        game_mode=game_mode,
    )
    game.pack(fill=tk.BOTH, expand=True)
    root.protocol('WM_DELETE_WINDOW', game.exit_game)
    root.mainloop()
    return game


if __name__ == '__main__':
    # Standalone launch starts with a fixed 10,000,000 balance.
    # Embedded/parent launches continue to use the balance supplied by Parent.
    main(balance=10_000_000)
