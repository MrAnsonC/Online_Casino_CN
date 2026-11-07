"""百家宝：百家乐版式、双层点数下注与 Sicbo 双骰物理。"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal
from itertools import combinations
from pathlib import Path
import json
import re
import random
import math
import time
import tkinter as tk
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    Image = ImageDraw = ImageTk = None

# The host's encrypted account hook must run before account JSON is opened.
_ROOT = Path(__file__).resolve().parent
_ACCOUNT_ROOT = next((p for p in (_ROOT, *_ROOT.parents)
                      if (p / 'A_Tools/Account/secure_json.py').is_file()), None)
if _ACCOUNT_ROOT is not None:
    import sys
    if str(_ACCOUNT_ROOT) not in sys.path:
        sys.path.insert(0, str(_ACCOUNT_ROOT))
    from A_Tools.Account import install_secure_json
    install_secure_json()

CENT = Decimal('0.01')
BET_ROWS = (
    ('Small', 'ThreeOfKind', 'FourOfKind', 'Large'),
    ('Odd', 'PlayerPair', 'BankerPair', 'Even'),
    ('Player', 'Tie', 'Banker'),
)
BET_LABELS = {
    'Small': '小 2–8', 'ThreeOfKind': '三个一样', 'FourOfKind': '四个一样',
    'Large': '大 9–12', 'Odd': '单', 'Even': '双',
    'PlayerPair': '闲家对子', 'BankerPair': '庄家对子',
    'Player': '闲家', 'Tie': '和局', 'Banker': '庄家',
}
BET_ODDS = {
    'Small': '1:1', 'ThreeOfKind': '9:1', 'FourOfKind': '205:1',
    'Large': '0.92:1', 'Odd': '0.97:1', 'Even': '0.97:1',
    'PlayerPair': '4.8:1', 'BankerPair': '4.8:1',
    'Player': '1:1', 'Tie': '最高 88:1', 'Banker': '1:1',
}
BET_COLORS = {
    'Small': '#235782', 'ThreeOfKind': '#7b5b23', 'FourOfKind': '#703467',
    'Large': '#832f3b', 'Odd': '#443879', 'Even': '#624285',
    'PlayerPair': '#25649b', 'BankerPair': '#9b3649',
    'Player': '#2368bd', 'Tie': '#208452', 'Banker': '#c43c4c',
}
TIE_PROFIT_ODDS = {4: 88, 24: 88, 6: 25, 22: 25, 8: 10,
                   20: 10, 10: 6, 18: 6, 12: 4, 14: 4, 16: 4}
# Exact-point bets use net odds; only a tie at the selected winning point pushes.
# A total of 2 cannot strictly beat the other side, so there is no Win 2 market.
WIN_POINT_PROFIT_ODDS = {
    3: Decimal('310'), 4: Decimal('67'), 5: Decimal('24'),
    6: Decimal('11'), 7: Decimal('5.6'), 8: Decimal('4.7'),
    9: Decimal('4.8'), 10: Decimal('5.8'), 11: Decimal('8.3'),
    12: Decimal('17'),
}
TIE_POINT_PROFIT_ODDS = {
    2: Decimal('1200'), 3: Decimal('310'), 4: Decimal('140'),
    5: Decimal('76'), 6: Decimal('48'), 7: Decimal('33'),
    8: Decimal('48'), 9: Decimal('76'), 10: Decimal('140'),
    11: Decimal('310'), 12: Decimal('1200'),
}
# Separate light-to-dark palettes distinguish winning points from tie points.
WIN_POINT_COLORS = (
    '#d6eaff', '#bedcff', '#a6cefa', '#8ebff2', '#76aee7', '#5d9bd9',
    '#4686c6', '#3470ad', '#255990', '#1b4471', '#123253',
)
TIE_POINT_COLORS = (
    '#c9efd4', '#b5e6c5', '#a0ddb6', '#8bd4a6', '#76c997', '#61bd87',
    '#4cab77', '#398d63', '#286f50', '#18513b', '#103e2d',
)
POINT_BETS = {
    **{f'Win {point}': ('win', point, odds)
       for point, odds in WIN_POINT_PROFIT_ODDS.items()},
    **{f'Tie {point}': ('tie', point, odds)
       for point, odds in TIE_POINT_PROFIT_ODDS.items()},
}
BET_LABELS.update({key: f'{"获胜" if kind == "win" else "和局"}点数 {point}'
                   for key, (kind, point, odds) in POINT_BETS.items()})
BET_ODDS.update({key: f'{odds}:1' for key, (kind, point, odds) in POINT_BETS.items()})
BET_COLORS.update({key: (WIN_POINT_COLORS if kind == 'win' else TIE_POINT_COLORS)[point - 2]
                   for key, (kind, point, odds) in POINT_BETS.items()})
PIPS = {
    1: ((0, 0),), 2: ((-1, -1), (1, 1)),
    3: ((-1, -1), (0, 0), (1, 1)),
    4: ((-1, -1), (1, -1), (-1, 1), (1, 1)),
    5: ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)),
    6: ((-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)),
}


def money(value):
    return f'{Decimal(str(value)):,.2f}'


def account_path():
    return (_ROOT / '../A_Tools/Account/saving_data.json').resolve()


def update_balance_in_json(username, balance):
    if not username or username == 'Guest':
        return
    path = account_path()
    try:
        with open(str(path), encoding='utf-8') as stream:
            users = json.load(stream)
        if not isinstance(users, list):
            return
        for user in users:
            if user.get('user_name') == username:
                user['cash'] = money(balance).replace(',', '')
                with open(str(path), 'w', encoding='utf-8') as stream:
                    json.dump(users, stream, ensure_ascii=False, indent=4)
                return
    except (OSError, ValueError, TypeError):
        return


def return_factor(bet_type, result):
    """Gross payout including stake; a lost wager returns zero."""
    player, banker = result['player_dice'], result['banker_dice']
    ps, bs = sum(player), sum(banker)
    winner = result['winner']
    if bet_type in POINT_BETS:
        kind, point, odds = POINT_BETS[bet_type]
        if kind == 'tie':
            return odds + 1 if ps == bs == point else Decimal(0)
        if ps == bs:
            return Decimal(1) if ps == point else Decimal(0)
        return odds + 1 if max(ps, bs) == point else Decimal(0)
    values = player + banker
    counts = Counter(values)
    winning_score = ps if winner == 'Player' else bs if winner == 'Banker' else 0
    size_score = ps if winner == 'Player' else bs if winner == 'Banker' else ps + bs
    factors = {
        'Player': Decimal('2') if winner == 'Player' else Decimal('.5') if winner == 'Tie' else Decimal(0),
        'Banker': Decimal('2') if winner == 'Banker' else Decimal('.5') if winner == 'Tie' else Decimal(0),
        'Tie': Decimal(1 + TIE_PROFIT_ODDS.get(ps + bs, 4)) if winner == 'Tie' else Decimal(0),
        'Small': Decimal(2) if 2 <= size_score <= 8 else Decimal(0),
        'Large': Decimal('1.92') if 9 <= size_score <= 12 else Decimal(0),
        'ThreeOfKind': Decimal(10) if max(counts.values()) >= 3 else Decimal(0),
        'FourOfKind': Decimal(206) if max(counts.values()) == 4 else Decimal(0),
        'Odd': Decimal('1.97') if winner != 'Tie' and winning_score % 2 else Decimal(0),
        'Even': Decimal('1.97') if winner != 'Tie' and winning_score % 2 == 0 else Decimal(0),
        'PlayerPair': Decimal('5.8') if player[0] == player[1] else Decimal(0),
        'BankerPair': Decimal('5.8') if banker[0] == banker[1] else Decimal(0),
    }
    return factors[bet_type]


def settle_bets(bets, result):
    return {key: (Decimal(str(amount)) * return_factor(key, result)).quantize(CENT)
            for key, amount in bets.items()}


def valid_dice(data):
    return (isinstance(data, list) and len(data) == 4
            and all(type(v) is int and 1 <= v <= 6 for v in data))


class BacBoHistory:
    """Keep the existing Baccarat_Dice.json 01_Data ... 60_Data format."""
    def __init__(self, path=None):
        self.path = Path(path) if path else (_ROOT / '../A_Logs/Json/Baccarat_Dice.json').resolve()
        self.records = []  # newest first
        try:
            with open(str(self.path), encoding='utf-8') as stream:
                data = json.load(stream)
            if isinstance(data, dict):
                for index in range(1, 2001):
                    dice = data.get(f'{index:02d}_Data')
                    if valid_dice(dice):
                        self.records.append(self.from_dice(dice))
        except (OSError, ValueError, TypeError):
            pass

    @staticmethod
    def from_dice(dice):
        player, banker = list(dice[:2]), list(dice[2:])
        ps, bs = sum(player), sum(banker)
        return {'player_dice': player, 'banker_dice': banker,
                'player_score': ps, 'banker_score': bs,
                'winner': 'Player' if ps > bs else 'Banker' if bs > ps else 'Tie',
                'player_pair': player[0] == player[1],
                'banker_pair': banker[0] == banker[1]}

    def add(self, result):
        new_records = [result] + self.records
        # Preserve BacBo's original batch trim: when 60 is full, remove six.
        if len(new_records) > 2000:
            new_records = new_records[:2000]
        data = {f'{index:02d}_Data': record['player_dice'] + record['banker_dice']
                for index, record in enumerate(new_records, 1)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.tmp')
        with open(str(temporary), 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        temporary.replace(self.path)
        self.records = new_records

class TempSavingHistory:
    """Bead Plate 专用历史：最多 72 条，满 73 时删除最旧 6 条。"""
    def __init__(self, path=None):
        self.path = Path(path) if path else (_ROOT / '../A_Logs/Json/temp_saving.json').resolve()
        self.records = []  # newest first
        try:
            with open(str(self.path), encoding='utf-8') as stream:
                data = json.load(stream)
            if isinstance(data, dict):
                for index in range(1, 73):
                    dice = data.get(f'{index:02d}_Data')
                    if valid_dice(dice):
                        self.records.append(BacBoHistory.from_dice(dice))
        except (OSError, ValueError, TypeError):
            pass

    def add(self, result):
        new_records = [result] + self.records
        if len(new_records) > 72:
            # 删除最旧的 6 条（最新在前，末尾最旧）
            new_records = new_records[:-6]
        data = {f'{index:02d}_Data': record['player_dice'] + record['banker_dice']
                for index, record in enumerate(new_records, 1)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.tmp')
        with open(str(temporary), 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        temporary.replace(self.path)
        self.records = new_records

# World-space rigid cubes; geometry is shared by collision, rendering and scoring.
SCENE_UNIT = 600.0
DICE_EDGE_PX = 38.0 * .75
BOWL_SCALE = 1.55
BOWL_HEIGHT_SCALE = .80
DOME_HEIGHT_SCALE = 1.00
BOWL_DISPLAY_SIZE = (274, 193)
# Reduce the visible dish diameter by 10px without scaling dice or dome height.
BOWL_RADIUS_SCALE = 1.35 - 10.0 / (
    2 * .094 * BOWL_SCALE * 680 * BOWL_DISPLAY_SIZE[0] / round(196 * BOWL_SCALE))
DOME_EXTRA_HEIGHT_PX = 15
BOWL_DROP_PX = 20
VIEW_DEPTH = .28 / math.hypot(.28, .70)
VIEW_UP = .70 / math.hypot(.28, .70)
def view_projection():
    return VIEW_DEPTH, VIEW_UP, 96., (0., VIEW_UP, VIEW_DEPTH)


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _add(a, b):
    return tuple(x+y for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _scale(a, amount):
    return tuple(x*amount for x in a)


def _length(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    length = _length(a)
    return _scale(a, 1/length) if length > 1e-12 else (0., 0., 0.)


def _rotate(q, omega, dt):
    speed = _length(omega)
    if speed < 1e-12:
        return q
    a = speed*dt/2
    dw = math.cos(a)
    dx, dy, dz = _scale(omega, math.sin(a)/speed)
    w, x, y, z = q
    r = (dw*w-dx*x-dy*y-dz*z, dw*x+dx*w+dy*z-dz*y,
         dw*y-dx*z+dy*w+dz*x, dw*z+dx*y-dy*x+dz*w)
    norm = math.sqrt(sum(v*v for v in r))
    return tuple(v/norm for v in r)


def _qvector(q, v):
    xyz = q[1:]
    t = _scale(_cross(xyz, v), 2)
    return _add(v, _add(_scale(t, q[0]), _cross(xyz, t)))


# Standard six-sided dice: 1 opposite 6, 2 opposite 5, 3 opposite 4.
# Fixed standard pip layouts rotate with the cube; the result is its upward face.
CUBE_FACES = (
    (1, (0., 0., 1.), (1., 0., 0.), (0., 1., 0.)),
    (6, (0., 0., -1.), (1., 0., 0.), (0., -1., 0.)),
    (3, (1., 0., 0.), (0., 1., 0.), (0., 0., 1.)),
    (4, (-1., 0., 0.), (0., -1., 0.), (0., 0., 1.)),
    (2, (0., 1., 0.), (-1., 0., 0.), (0., 0., 1.)),
    (5, (0., -1., 0.), (1., 0., 0.), (0., 0., 1.)),
)


class RigidDie:
    EDGE = DICE_EDGE_PX / SCENE_UNIT
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
        normal = next(face[1] for face in CUBE_FACES if face[0] == top)
        axis = _cross(normal, (0., 0., 1.))
        if _length(axis) > 1e-10:
            self.q = _rotate(self.q, _unit(axis), math.acos(normal[2]))
        elif normal[2] < 0:
            self.q = _rotate(self.q, (1., 0., 0.), math.pi)

    def axes(self):
        return tuple(_qvector(self.q, axis) for axis in
                     ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)))

    def vertices(self):
        axes = self.axes()
        return [_add(self.p, _scale(_add(_scale(axes[0], x),
                         _add(_scale(axes[1], y), _scale(axes[2], z))), self.HALF))
                for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]

    def support(self, normal):
        point = self.p
        for axis in self.axes():
            projection = _dot(axis, normal)
            if abs(projection) > 1e-9:
                point = _add(point, _scale(axis, math.copysign(self.HALF, projection)))
        return point

    def impulse(self, impulse, point):
        self.v = _add(self.v, impulse)
        self.omega = _add(self.omega, _scale(_cross(_sub(point, self.p), impulse),
                                            self.INVERSE_INERTIA))

    def top_face(self):
        candidates = [(number, _qvector(self.q, normal)[2])
                      for number, normal, _u, _v in CUBE_FACES]
        number, alignment = max(candidates, key=lambda item: item[1])
        return number if alignment >= self.LANDING_ALIGNMENT-1e-12 else None

    def settled(self):
        floor = min(point[2] for point in self.vertices())
        return (self.top_face() is not None and abs(floor) <= self.CONTACT_TOLERANCE
                and _length(self.v) < .005 and _length(self.omega) < .12)

    def stabilize_contact(self):
        """Remove contact chatter only when a face is already almost flat."""
        face = max(CUBE_FACES, key=lambda f: _qvector(self.q, f[1])[2])
        normal = _qvector(self.q, face[1])
        if (normal[2] > .999 and self.p[2] < self.HALF+self.EDGE*.04
                and _length(self.v) < .08 and _length(self.omega) < 12.):
            axis = _cross(normal, (0., 0., 1.))
            if _length(axis) > 1e-12:
                self.q = _rotate(self.q, _unit(axis), math.acos(min(1., normal[2])))
            self.p = (self.p[0], self.p[1], self.HALF)
            self.v = self.omega = (0., 0., 0.)


def _overlap(a, b):
    """Read-only OBB contact query for physics and initial placement."""
    aa, ba = a.axes(), b.axes()
    axes = list(aa)+list(ba)+[_cross(x, y) for x in aa for y in ba]
    delta = _sub(b.p, a.p)
    normal, penetration = None, float('inf')
    for axis in axes:
        if _length(axis) < 1e-8:
            continue
        axis = _unit(axis)
        ra = a.HALF*sum(abs(_dot(axis, v)) for v in aa)
        rb = b.HALF*sum(abs(_dot(axis, v)) for v in ba)
        overlap = ra+rb-abs(_dot(delta, axis))
        if overlap <= 0:
            return None
        if overlap < penetration:
            penetration = overlap
            normal = axis if _dot(delta, axis) >= 0 else _scale(axis, -1)
    return normal, penetration


def collide_dice(a, b):
    """OBB contact, friction impulses and angular response from BacBo."""
    contact_info = _overlap(a, b)
    if contact_info is None:
        return False
    normal, penetration = contact_info
    contact = _scale(_add(a.support(normal), b.support(_scale(normal, -1))), .5)
    ra, rb = _sub(contact, a.p), _sub(contact, b.p)
    av = _add(a.v, _cross(a.omega, ra))
    bv = _add(b.v, _cross(b.omega, rb))
    relative = _sub(bv, av)
    speed = _dot(relative, normal)
    if speed < 0:
        effective = 2+a.INVERSE_INERTIA*(_dot(_cross(ra, normal), _cross(ra, normal))
                                       + _dot(_cross(rb, normal), _cross(rb, normal)))
        amount = -(1.4 if speed < -.08 else 1.)*speed/effective
        impulse = _scale(normal, amount)
        a.impulse(_scale(impulse, -1), contact)
        b.impulse(impulse, contact)
        tangent = _sub(relative, _scale(normal, speed))
        if _length(tangent) > 1e-9:
            direction = _unit(tangent)
            effective = 2+a.INVERSE_INERTIA*(
                _length(_cross(ra, direction))**2+_length(_cross(rb, direction))**2)
            friction = min(.35*amount, _length(tangent)/effective)
            a.impulse(_scale(direction, friction), contact)
            b.impulse(_scale(direction, -friction), contact)
    correction = _scale(normal, (penetration+.000002)*.5)
    a.p = _sub(a.p, correction)
    b.p = _add(b.p, correction)
    return True


class DiceBowl:
    DICE_COUNT = 2
    RADIUS = .085 * BOWL_SCALE * BOWL_RADIUS_SCALE
    HEIGHT = (.128 * BOWL_SCALE * DOME_HEIGHT_SCALE
              + DOME_EXTRA_HEIGHT_PX
              / (680 * VIEW_UP * BOWL_DISPLAY_SIZE[1] / round(138 * BOWL_SCALE)))

    def __init__(self, values=None, rng=None):
        self.rng = rng or random.SystemRandom()
        values = values or [self.rng.randint(1, 6) for _ in range(self.DICE_COUNT)]
        if len(values) != self.DICE_COUNT or any(type(n) is not int or n not in range(1, 7) for n in values):
            raise ValueError('百家宝每边需要两颗有效骰子。')
        self.dice = [RigidDie((index - (self.DICE_COUNT - 1) / 2) * RigidDie.EDGE * 1.4, value)
                     for index, value in enumerate(values)]
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
                die.q = _rotate(die.q, (0., 0., 1.), self.rng.uniform(0, math.tau))
                die.v = die.omega = (0., 0., 0.)
            if (self.landing_error() is None
                    and all(_overlap(a, b) is None for a, b in combinations(self.dice, 2))):
                return
        # A bounded fallback still has random heading and preserves rolled faces.
        heading = self.rng.uniform(0, math.tau)
        for index, die in enumerate(self.dice):
            angle = heading + index * math.tau / self.DICE_COUNT
            radius = min(self.RADIUS-die.EDGE, die.EDGE*2.6)
            die.p = (radius * math.cos(angle), radius * math.sin(angle), die.HALF)
            die.q = _rotate(die.q, (0., 0., 1.), heading)

    def has_elevated_die(self):
        """Inspect floor contact independently of a possibly tilted top face."""
        return any(min(self.local(p)[2] for p in die.vertices()) > die.CONTACT_TOLERANCE
                   for die in self.dice)

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
        return _add(self.origin, local)

    def local(self, world):
        return _sub(world, self.origin)

    def wall_contact(self, die, point, normal, penetration):
        die.p = _add(die.p, _scale(normal, penetration+.0000005))
        point = _add(point, _scale(normal, penetration))
        radius = _sub(point, die.p)
        surface = self.velocity
        relative = _sub(_add(die.v, _cross(die.omega, radius)), surface)
        speed = _dot(relative, normal)
        if speed >= 0:
            return
        rn = _cross(radius, normal)
        impulse = -(1.25 if speed < -.2 else 1.)*speed/(1+die.INVERSE_INERTIA*_dot(rn, rn))
        die.impulse(_scale(normal, impulse), point)
        relative = _sub(_add(die.v, _cross(die.omega, radius)), surface)
        tangent = _sub(relative, _scale(normal, _dot(relative, normal)))
        if _length(tangent) > 1e-10:
            direction = _unit(tangent)
            effective = 1+die.INVERSE_INERTIA*_length(_cross(radius, direction))**2
            friction = min(.48*impulse, _length(tangent)/effective)
            die.impulse(_scale(direction, -friction), point)

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
                    depth = (level-1)/(2*_length(gradient))
                    normal = _scale(_unit(gradient), -1)
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
        travel = _length(_sub(target, self.origin))
        speed = max(_length(die.v)+_length(die.omega)*die.HALF for die in self.dice)
        # Smaller contact steps when fast motion could cross a significant cube width.
        steps = max(1, min(8, math.ceil((travel+speed*dt)/(RigidDie.EDGE*.22))))
        h = dt/steps
        for index in range(steps):
            self._step_once(h, t-dt+(index+1)*h, shaking)

    def _step_once(self, dt, t, shaking=True):
        old_origin = self.origin
        if shaking:
            self.origin = self.motion(t)
        else:
            self.origin = (0., 0., 0.)
        self.velocity = _scale(_sub(self.origin, old_origin), 1/dt)
        for die in self.dice:
            die.v = _add(die.v, (0., 0., -9.81*dt))
            die.p = _add(die.p, _scale(die.v, dt))
            die.q = _rotate(die.q, die.omega, dt)
            touching = self.contain(die)
            die.omega = _scale(die.omega, math.exp(-(2.8 if touching else .1)*dt))
            if touching and not shaking:
                die.v = _scale(die.v, math.exp(-4*dt))
        for _ in range(2):
            collided = False
            for a, b in combinations(self.dice, 2):
                if collide_dice(a, b):
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
            bowl.dice = [RigidDie(0) for _ in range(cls.DICE_COUNT)]
            for die, data in zip(bowl.dice, state['dice']):
                die.p, die.q = tuple(map(float,data['p'])), tuple(map(float,data['q']))
                if (len(die.p) != 3 or len(die.q) != 4
                        or not all(math.isfinite(v) for v in die.p+die.q)
                        or abs(sum(v*v for v in die.q)-1) > 1e-6):
                    return None
            return bowl if bowl.settled() and bowl.landing_error() is None else None
        except (KeyError, ValueError, TypeError, AttributeError):
            return None


def bowl_mesh(bowl):
    """Sicbo dome and dish, with two same-colour BacBo dice."""
    solids, glass = [], []
    _depth, _up, _center, camera = view_projection()
    def face(points, color, line=None, width=.7, transparent=False, paint_depth=None):
        if len(points) >= 3:
            n = _cross(_sub(points[1], points[0]), _sub(points[2], points[0]))
            if not transparent and _dot(n, camera) <= 0:
                return
        depth = (sum(_dot(point, camera) for point in points)/len(points)
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
    profile = [(radius * BOWL_SCALE * BOWL_RADIUS_SCALE,
                z * BOWL_SCALE * BOWL_HEIGHT_SCALE) for radius, z in
               ((.083, 0.), (.088, .005), (.093, .002), (.094, -.007),
                (.092, -.014), (.083, -.020))]
    rings = [ring(radius, z) for radius, z in profile]
    for k in range(32):
        j = (k+1)%32
        face([bowl.world(p) for p in ((0.,0.,0.), rings[0][k], rings[0][j])], (248,234,197,255))
        face([bowl.world(p) for p in ((0.,0.,-.020*BOWL_SCALE*BOWL_HEIGHT_SCALE), rings[-1][j], rings[-1][k])], (142,111,70,255))
    for a,b,color in zip(rings,rings[1:],((187,151,99),(255,231,176),(191,158,107),(243,215,156),(148,117,75))):
        band(a,b,color)
    # The dish is below the bodies. Sorting its large triangles against the
    # small cube faces by average depth can paint the dish over a resting die.
    # Keep the whole support surface behind the dice, with glass in front.
    dish = sorted(solids,key=lambda f:f[0])
    solids = []
    for die in bowl.dice:
        color, pip_color = bowl.color, (250, 247, 238, 255)
        for number, normal, u, v in CUBE_FACES:
            n = _qvector(die.q, normal)
            if _dot(n, camera) <= 0:
                continue
            def cube_point(x, y, z=die.HALF):
                return _add(die.p, _qvector(die.q, _add(_scale(normal,z),
                             _add(_scale(u,x), _scale(v,y)))))
            corners = [cube_point(x*die.HALF,y*die.HALF) for x,y in ((-1,-1),(1,-1),(1,1),(-1,1))]
            lighting = .72+.28*max(0., _dot(n, _unit((-.4,.5,1.))))
            shade = lighting
            rgb = tuple(round(channel*shade) for channel in color)+(255,)
            rim = tuple(round(channel*.55) for channel in color)+(255,)
            face_depth = face(corners, rgb, rim, .35)
            for px, py in PIPS[number]:
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
                                (raised+.002*BOWL_SCALE*BOWL_HEIGHT_SCALE,
                                 .086*BOWL_SCALE*BOWL_RADIUS_SCALE,(168,207,194,185),.6)):
        rim = ring(radius,z)
        for k in range(32):
            face([bowl.world(rim[k]),bowl.world(rim[(k+1)%32])],None,color,width,True)
    for azimuth,color,width in ((-2.4,(242,255,249,220),1.2),(.55,(219,246,235,160),.8)):
        curve = []
        for k in range(22):
            a = .10+1.28*k/21
            curve.append(bowl.world((bowl.RADIUS*math.cos(a)*math.cos(azimuth),
                                     bowl.RADIUS*math.cos(a)*math.sin(azimuth),
                                     bowl.HEIGHT*math.sin(a)+raised+.0005*BOWL_SCALE*BOWL_HEIGHT_SCALE)))
        for k in range(len(curve)-1):
            face(curve[k:k+2],None,color,width,True)
    return dish + sorted(solids,key=lambda f:f[0]), sorted(glass,key=lambda f:f[0])


def project_bowl_point(point, bowl):
    # The real bowl translation drives physics. Its screen travel is reduced to
    # fit the betting area, applied identically to glass, dish and dice.
    point = _sub(point, _scale(bowl.origin, .78))
    return (98*BOWL_SCALE+point[0]*680,
            96*BOWL_SCALE+(point[1]*VIEW_DEPTH-point[2]*VIEW_UP)*680)


def render_bowl(bowl):
    """Antialiased image of the same geometry used by contact and scoring."""
    # Extra headroom extends the dome without scaling the dice or the dish.
    width, height = BOWL_DISPLAY_SIZE
    size, aa = (width, height + DOME_EXTRA_HEIGHT_PX), 3
    scale_x = width / round(196 * BOWL_SCALE)
    scale_y = height / round(138 * BOWL_SCALE)
    picture = Image.new('RGBA', (size[0]*aa, size[1]*aa))
    for meshes in bowl_mesh(bowl):
        layer = Image.new('RGBA', picture.size)
        draw = ImageDraw.Draw(layer)
        for _depth, points, color, line, width in meshes:
            projected = [(x*scale_x*aa, (y*scale_y+DOME_EXTRA_HEIGHT_PX)*aa)
                         for x,y in (project_bowl_point(p,bowl) for p in points)]
            if color:
                draw.polygon(projected, fill=color)
            if line:
                draw.line(projected+([projected[0]] if len(points)>2 else []),
                          fill=line,width=max(1,round(width*scale_y*aa)))
        picture.alpha_composite(layer)
    return picture.resize(size, Image.Resampling.LANCZOS)


class BetState:
    def __init__(self):
        self.bets = {}

    def total_at_risk(self):
        return sum(float(value) for value in self.bets.values())

    def current_area_bet(self, bet_type):
        return float(self.bets.get(bet_type, 0.0))

    def conflicting_main_bet(self, bet_type):
        opposite = {'Player': 'Banker', 'Banker': 'Player'}.get(bet_type)
        if opposite and self.current_area_bet(opposite) > 0:
            return opposite
        return None

    def add_bet(self, bet_type, amount):
        if amount <= 0 or self.conflicting_main_bet(bet_type):
            return False
        self.bets[bet_type] = self.current_area_bet(bet_type) + float(amount)
        return True


    def clear_area(self, bet_type):
        return float(self.bets.pop(bet_type, 0.0))

    def clear_all(self):
        amount = self.total_at_risk()
        self.bets.clear()
        return amount


class BacBoGame(tk.Frame):
    WIDTH, HEIGHT = 1150, 750
    BG, PANEL, FELT, GOLD = '#12202c', '#192b38', '#174a4c', '#f0d48b'
    CHIP_SPECS = [
        (100, '#202020', '100'), (500, '#d780c0', '500'),
        (1000, '#ab0058', '1K'), (5000, '#ba3438', '5K'),
        (10000, '#70439a', '10K'), (50000, '#2e7542', '50K'),
        (250000, '#ffffff', '250K'),
    ]
    CHIP_MOVE_DURATION_MS = 200
    CHIP_MOVE_STEPS = 10
    M_CHIP_COLOR = '#102d47'
    MAX_TABLE_BET = 2_000_000.0
    BOARD_INNER_X0, BOARD_INNER_X1 = 22, 760
    PLAYER_ZONE_BASE, PLAYER_ZONE_LIGHT = '#102d47', '#83cfff'
    BANKER_ZONE_BASE, BANKER_ZONE_LIGHT = '#4b1e22', '#ff9ca2'
    TIE_FLASH_LIGHT = '#78e49a'
    HISTORY_X0, HISTORY_X1 = 778, 1138
    PANEL_LINE = '#665240'
    PLAYER_BLUE, BANKER_RED, TIE_GREEN = '#3d67d8', '#d94a4e', '#43a665'
    MAX_RECORDS = 300
    BETTING_BOUNDS = (22, 362, 760, 606)
    DICE_RESULT_TIMEOUT_MS = 8000
    DICE_RECOVERY_SHAKE_SECONDS = 1.0
    DICE_ZONE_EDGE_GAP = 15
    SCORE_FONT = ('Arial', 86, 'bold')

    def __init__(self, parent, balance=10000, user=None, on_back=None,
                 on_balance_change=None):
        super().__init__(parent, bg=self.BG, width=self.WIDTH, height=self.HEIGHT)
        self.pack_propagate(False)
        self.username = user
        self.balance = Decimal(str(balance)).quantize(CENT)
        self.final_balance = float(self.balance)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.history = BacBoHistory()     
        self.temp_history = TempSavingHistory()
        self.bet_state = BetState()
        self.last_round_bets = []
        self.bet_spots = {}
        self.chip_selector_items = {}
        self.control_buttons = {}
        self.accept_bets = True
        self.animation_running = False
        self.settlement_running = False
        self.summary_mode = 'bet'
        self.last_win_amount = Decimal(0)
        self.chip_motion_after_ids = set()
        self.chip_motion_serial = 0
        self.pending_bet_visual_amounts = {}
        self.settlement_return_animating = False
        self.settlement_return_keys = set()
        self.settlement_profit_tags = {}
        self.settlement_chip_moves_started = False
        self.settlement_after_id = None
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.flash_original_text_colors = {}
        self.pre_deal_bets = None
        self.settlement_flash_step = 0
        self.settlement_hold_amounts = {}
        self.push_return_amounts = {}
        self.result_panel_flash_winner = None
        self.selected_chip = 1000
        self.running = False
        self.closed = False
        self.jobs = set()
        self.current_result = None
        self.history_panel_mode = 'roads'
        self.big_road_scroll_col = 0
        self.big_road_auto_follow = True
        self.big_road_virtual_cols = 50
        self.big_road_view_cols = 14
        self.bead_show_scores = False
        self.history_data = list(reversed(self.history.records))
        self.bead_data = list(reversed(self.temp_history.records))
        values = ([1, 1, 1, 1] if not self.history.records else
                  self.history.records[0]['player_dice']+self.history.records[0]['banker_dice'])
        self.bowls = [DiceBowl(values[:2]), DiceBowl(values[2:])]
        self.bowls[0].color = (32, 117, 217)
        self.bowls[1].color = (206, 51, 71)
        self._phase = 'idle'
        self._dice_recovering = False
        self._dice_round_voided = False
        self._dice_result_deadline = None
        self._dice_result_timeout_id = None
        self._dice_rest_anchor = None
        self._dice_stable_time = 0.
        self._photos = []
        self._bowl_image_items = []
        self._bowl_home_centers = {}
        self.canvas = tk.Canvas(self, width=self.WIDTH, height=self.HEIGHT,
                                bg=self.BG, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        parent.winfo_toplevel().bind('<Return>', self.handle_enter_deal, add='+')
        self.draw_static()
        self.select_chip(self.selected_chip)
        self.draw_scene()
        self.draw_bets()
        self.refresh_history()
        self.update_display()

    def schedule(self, delay, callback):
        job = None
        def run():
            self.jobs.discard(job)
            if not self.closed:
                callback()
        job = self.after(delay, run)
        self.jobs.add(job)

    def draw_static(self):
        c = self.canvas
        c.create_rectangle(10, 8, 770, 312, fill=self.PANEL, outline='#66808b', width=2)
        self.animation_phase_text = c.create_text(385, 25, text='百家宝  ·  BAC BO',
                                                  fill=self.GOLD, font=('Arial', 17, 'bold'))
        c.create_rectangle(10, 318, 770, 621, fill=self.FELT, outline='#86a8a2', width=2)
        c.create_text(30, 336, anchor='w', text='每边2颗标准骰子，更大方获胜',
                      fill=self.GOLD, font=('Arial', 14, 'bold'))
        self.draw_history_panel()
        self.draw_bottom_controls()
        c.bind('<Button-1>', self._handle_bead_click, add='+')


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
            278, 650, 344, 704, '清除', self.clear_bets, '#7c3b40', font_size=11)

        # Larger chips, with the whole seven-chip rack centred at x=575.
        chip_diameter = 56
        chip_gap = 8
        chip_total_width = len(self.CHIP_SPECS) * chip_diameter + (len(self.CHIP_SPECS) - 1) * chip_gap
        chip_x = (self.WIDTH - chip_total_width) / 2
        chip_y = 646
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
            810, 650, 855, 695, '❓', self.show_game_instructions, '#315b72',
            fg='white', font_size=17)
        self.repeat_button = self.create_control_button(
            862, 638, 1000, 708, '重复下注', self.repeat_last_bets, '#5b4938', font_size=11)
        self.deal_button = self.create_control_button(
            1012, 628, 1138, 720, '摇碗', self.deal, '#d5ad4d',
            fg='#111', font_size=14, subtext='ENTER', subtext_font_size=10)
        c.tag_raise('controls')
        c.tag_raise('chip_selector')
        self.update_control_states()


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
        for attr in ('clear_button', 'repeat_button', 'deal_button'):
            tag = getattr(self, attr, None)
            if tag:
                self.set_control_button_state(tag, enabled)


    def _schedule_chip_motion(self, delay_ms, callback):
        """Schedule one chip-motion frame and keep its after-id cancellable."""
        holder = {}

        def run():
            after_id = holder.get('id')
            if after_id is not None:
                self.chip_motion_after_ids.discard(after_id)
            if self.closed:
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


    def _animate_amount_chip(self, amount, start_xy, target_xy, on_complete=None,
                             radius=19.0, role='wager', duration_ms=None,
                             keep_at_target=False):
        """Move a chip, optionally leaving a separate profit chip at its target."""
        if self.closed:
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
        radius = max(6.0, float(radius))
        font_size = 9 if radius >= 18 else max(6, round(radius * .45))
        chip_color = self.bet_chip_color(amount)
        text_color = self.contrast_text_color(chip_color)
        motion_tags = (tag, 'chip_motion', f'settlement_{role}')

        outer = self.canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill='#292522', outline='#151311', width=1,
            tags=motion_tags)
        inner = self.canvas.create_oval(
            x - radius + 3, y - radius + 3, x + radius - 3, y + radius - 3,
            fill=chip_color, outline='#e2ddd5', width=1,
            tags=motion_tags)
        text = self.canvas.create_text(
            x, y, text=self._compact_amount(amount),
            font=('Arial', font_size, 'bold'), fill=text_color,
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
            if self.closed:
                return
            ratio = min(1.0, max(0.0, step / steps))
            eased = ratio * ratio * (3.0 - 2.0 * ratio)
            cx = x + (tx - x) * eased
            cy = y + (ty - y) * eased
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


    @staticmethod
    def _settlement_motion_radius(spot):
        return min(19.0, spot.get('chip_radius', 20.0))


    @classmethod
    def _settlement_profit_position(cls, spot):
        x, y = spot['chip_pos']
        # Baccarat's left/up rule: both radii plus a 4px gap, 8px upwards.
        return (x - spot.get('chip_radius', 20.0)
                - cls._settlement_motion_radius(spot) - 4, y - 8)


    def _start_settlement_chip_movements(self):
        if self.settlement_chip_moves_started:
            return
        self.settlement_chip_moves_started = True
        bank = tuple(self.canvas.coords(self.animation_phase_text)[:2])
        for key, profit in self.flash_winner_amounts.items():
            spot = self.bet_spots.get(key)
            if spot and profit > 0:
                self.settlement_profit_tags[key] = self._animate_amount_chip(
                    profit, bank, self._settlement_profit_position(spot),
                    radius=self._settlement_motion_radius(spot), role='profit',
                    duration_ms=500, keep_at_target=True)


    def _complete_pending_bet_visual(self, key, amount):
        pending = max(0.0, float(self.pending_bet_visual_amounts.get(key, 0.0))
                      - float(amount))
        if pending > 1e-9:
            self.pending_bet_visual_amounts[key] = pending
        else:
            self.pending_bet_visual_amounts.pop(key, None)
        if not self.closed:
            self.update_bet_chips()
            self.canvas.tag_raise('controls')


    def _start_winning_chip_return(self):
        """Return the centre stake and upper-left profit as two separate chips."""
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
            if remaining['count'] <= 0 and not self.closed:
                self.settlement_return_animating = False
                self.settlement_return_keys.clear()
                self.finish_settlement()

        for index, (key, amount, start) in enumerate(returning):
            target = self._chip_rack_return_position(index, len(returning))
            self._animate_amount_chip(amount, start, target, on_complete=one_finished,
                                      radius=self._settlement_motion_radius(self.bet_spots[key]),
                                      role='return')
        return True


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
        if bet_type in ('Player', 'Banker'):
            return 500_000.0
        if bet_type == 'Tie':
            return 100_000.0
        return 30_000.0


    def _on_bet_enter(self, bet_type):
        self._hovered_bet_type = bet_type
        self._update_main_bet_availability()


    def _on_bet_leave(self):
        self._hovered_bet_type = None
        self.canvas.configure(cursor='')


    def _update_main_bet_availability(self):
        bet_type = getattr(self, '_hovered_bet_type', None)
        if bet_type is None:
            return
        if not self.bet_state.conflicting_main_bet(bet_type):
            self.canvas.configure(cursor='hand2')
            return
        # Match Baccarat's forbidden-cursor feedback on every supported OS.
        for cursor in ('no', 'notallowed', 'X_cursor'):
            try:
                self.canvas.configure(cursor=cursor)
                return
            except tk.TclError:
                continue


    def place_bet(self, bet_type, amount=None):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return False
        if (bet_type, None) not in self.bet_spots:
            return False
        if self.bet_state.conflicting_main_bet(bet_type):
            return False
        requested = float(amount if amount is not None else self.selected_chip)

        if requested < 100.0 or abs(requested / 100.0 - round(requested / 100.0)) > 1e-9:
            messagebox.showwarning('下注单位', '下注只接受100及100的倍数。',
                                   parent=self.winfo_toplevel())
            return False

        area_current = self.bet_state.current_area_bet(bet_type)
        table_current = self.bet_state.total_at_risk()
        raw_allowed = min(
            requested,
            self.bet_limit_for(bet_type) - area_current,
            self.MAX_TABLE_BET - table_current,
            float(self.balance),
        )
        allowed = float(int(max(0.0, raw_allowed) // 100.0) * 100)
        if allowed < 100.0:
            return False
        if allowed < requested:
            area_remaining = max(0.0, self.bet_limit_for(bet_type) - area_current)
            table_remaining = max(0.0, self.MAX_TABLE_BET - table_current)
            clipped_by_area_limit = (
                area_remaining + 1e-9 < requested
                and area_remaining <= table_remaining + 1e-9
                and area_remaining <= float(self.balance) + 1e-9
            )
            if not clipped_by_area_limit:
                messagebox.showwarning(
                    '下注限制', f'下注已自动调整为 {self.format_money(allowed)}。',
                    parent=self.winfo_toplevel())

        if not self.bet_state.add_bet(bet_type, allowed):
            return False
        key = (bet_type, None)
        self.pending_bet_visual_amounts[key] = (
            self.pending_bet_visual_amounts.get(key, 0.0) + allowed)
        self.balance -= Decimal(str(allowed))
        self.summary_mode = 'bet'
        self.update_display()

        source = self._chip_rack_source_position()
        target = tuple(self.bet_spots[key]['chip_pos'])
        self._animate_amount_chip(
            allowed, source, target,
            on_complete=lambda k=key, a=allowed: self._complete_pending_bet_visual(k, a),
            radius=self.bet_spots[key].get('chip_radius', 19))
        self.save_balance()
        return True


    def clear_single_bet(self, bet_type):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.bet_state.clear_area(bet_type)
        if refunded <= 0:
            return
        self.balance += Decimal(str(refunded))
        self.pending_bet_visual_amounts.pop((bet_type, None), None)
        self.update_display()
        self.save_balance()


    def clear_bets(self):
        if not self.accept_bets or self.animation_running or self.settlement_running:
            return
        refunded = self.bet_state.clear_all()
        if refunded <= 0:
            return
        self.balance += Decimal(str(refunded))
        self.pending_bet_visual_amounts.clear()
        self.update_display()
        self.save_balance()


    def snapshot_bets(self):
        return [(bet_type, None, float(amount))
                for bet_type, amount in self.bet_state.bets.items() if amount > 0]


    def repeat_last_bets(self):
        if (not self.accept_bets or self.animation_running or self.settlement_running
                or not self.last_round_bets):
            return

        self.clear_bets()
        active = {key[0] for key in self.bet_spots}
        repeatable = [(bt, p, amt) for bt, p, amt in self.last_round_bets if bt in active]
        required = sum(amt for _bt, _p, amt in repeatable)
        if float(self.balance) + 1e-9 < required:
            messagebox.showwarning(
                '余额不足',
                f'重复上局下注需要 {self.format_money(required)}，当前余额为 {self.format_money(self.balance)}。',
                parent=self.winfo_toplevel())
            return
        for bet_type, _param, amount in repeatable:
            self.place_bet(bet_type, amount=amount)


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
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'上局返还: {self.format_money(self.last_win_amount)}')
        else:
            self.canvas.itemconfigure(
                self.total_bet_text,
                text=f'本局下注: {self.format_money(self.bet_state.total_at_risk())}')
        self.update_bet_chips()
        self.update_history_table()
        self.update_control_states()
        self._update_main_bet_availability()


    def update_bet_chips(self):
        self.canvas.delete('bet_chip_dynamic')
        for key, spot in self.bet_spots.items():
            amount = self.bet_state.current_area_bet(key[0])
            # While a new wager is flying in, show only the amount that had
            # already reached this betting spot.
            pending_in = float(self.pending_bet_visual_amounts.get(key, 0.0))
            if pending_in > 0 and not self.settlement_running:
                amount = max(0.0, amount - pending_in)
            # The original stake stays centred; profit is a separate chip at
            # its upper left. Push stakes have no accompanying profit chip.
            if self.settlement_running and key in self.settlement_hold_amounts:
                amount = self.settlement_hold_amounts[key]
            # The moving copy itself is the winning chip during the 0.2-second
            # return flight, so do not leave a duplicate static chip underneath.
            if self.settlement_return_animating and key in self.settlement_return_keys:
                continue
            if amount <= 0:
                continue
            x0, y0, x1, y1 = spot['bounds']
            # Keep the wager chip in the geometric centre of its betting area.
            x, y = (x0 + x1) / 2, (y0 + y1) / 2
            radius = spot.get('chip_radius', 20)
            font_size = 9 if radius >= 18 else max(6, round(radius * .45))
            chip_color = self.bet_chip_color(amount)
            text_color = self.contrast_text_color(chip_color)
            self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius,
                                    fill='#292522', outline='#151311', width=1,
                                    tags=('bet_chip_dynamic', spot['tag']))
            self.canvas.create_oval(x - radius + 3, y - radius + 3,
                                    x + radius - 3, y + radius - 3,
                                    fill=chip_color, outline='#e2ddd5', width=1,
                                    tags=('bet_chip_dynamic', spot['tag']))
            self.canvas.create_text(x, y, text=self._compact_amount(amount),
                                    font=('Arial', font_size, 'bold'), fill=text_color,
                                    tags=('bet_chip_dynamic', spot['tag']))


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


    def handle_enter_deal(self, _event=None):
        button = self.control_buttons.get(getattr(self, 'deal_button', None))
        if button and button['enabled']:
            button['command']()
        return 'break'


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
        fill = BET_COLORS[bet_type]
        text_color = 'white'
        rect_id = c.create_rectangle(
            x0 + 2, y0 + 2, x1 - 2, y1 - 2,
            fill=fill, outline='#d5cbbd', width=1,
            tags=('board_dynamic', tag))

        label = BET_LABELS.get(bet_type, bet_type)
        if main:
            label_item = c.create_text(
                (x0 + x1) / 2, y0 + 27, text=label,
                font=('Arial', 23, 'bold'), fill=text_color,
                tags=('board_dynamic', tag))
            odds_item = c.create_text(
                (x0 + x1) / 2, y1 - 15, text=odds_text,
                font=('Arial', 18, 'bold'), fill=text_color,
                tags=('board_dynamic', tag))
            odds_y = y1 - 15
        else:
            label_item = c.create_text(
                (x0 + x1) / 2, y0 + 23, text=label,
                font=('Arial', 15, 'bold'), fill=text_color,
                tags=('board_dynamic', tag))
            odds_item = c.create_text(
                (x0 + x1) / 2, y1 - 13, text=odds_text,
                font=('Arial', 11, 'bold'), fill=text_color,
                tags=('board_dynamic', tag))
            odds_y = y1 - 13

        chip_y = (y0 + y1) / 2
        self.register_spot(
            bet_type, x0 + 2, y0 + 2, x1 - 2, y1 - 2,
            ((x0 + x1) / 2, chip_y), label)
        spot = self.bet_spots[(bet_type, None)]
        spot.update({
            'rect_id': rect_id, 'label_item': label_item, 'odds_item': odds_item,
            'base_odds': odds_text, 'odds_y': odds_y,
            'odds_base_x': (x0 + x1) / 2, 'main': bool(main),
            'normal_outline': '#d5cbbd', 'normal_outline_width': 1,
        })
        c.tag_bind(tag, '<Button-1>', lambda _e, bt=bet_type: self.place_bet(bt))
        c.tag_bind(tag, '<Button-3>', lambda _e, bt=bet_type: self.clear_single_bet(bt))
        c.tag_bind(tag, '<Enter>', lambda _e: c.configure(cursor='hand2'))
        c.tag_bind(tag, '<Leave>', lambda _e: c.configure(cursor=''))


    def run_settlement_flash(self):
        if self.closed or not self.settlement_running:
            return
        if self.settlement_flash_step == 0:
            self._start_settlement_chip_movements()
        if self.settlement_flash_step >= 6:
            self.settlement_after_id = None
            if not self._start_winning_chip_return():
                self.finish_settlement()
            return
        self.flash_mode = 'win' if self.settlement_flash_step % 2 == 0 else 'original'
        self.flash_result_panels(self.settlement_flash_step % 2 == 0)
        self.canvas.delete('win_flash_area')
        if self.flash_mode == 'original':
            self.restore_flash_text_colors()
        else:
            for key in self.flash_winning_keys:
                spot = self.bet_spots.get(key)
                if not spot:
                    continue
                x0, y0, x1, y1 = spot['bounds']

                flash_fill, flash_outline, flash_text = '#ffffff', '#111111', 'black'

                self.canvas.create_polygon(
                    *spot['classic_shape_coords'], smooth=True,
                    fill=flash_fill, outline=flash_outline, width=2,
                    tags=('win_flash_area', 'settlement_flash'))
                self.raise_spot_content_above_flash(spot, flash_text)
        self.update_bet_chips()
        self.canvas.tag_raise('bet_chip_dynamic')
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


    def raise_spot_content_above_flash(self, spot, flash_text_color='black'):
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
                self.canvas.itemconfigure(item_id, fill=flash_text_color)
                self.canvas.tag_raise(item_id)


    def restore_flash_text_colors(self):
        for item_id, color in list(self.flash_original_text_colors.items()):
            try:
                self.canvas.itemconfigure(item_id, fill=color)
            except tk.TclError:
                pass
        self.flash_original_text_colors.clear()


    def finish_settlement(self):
        if self.closed:
            return
        self.settlement_after_id = None
        self.canvas.delete('win_flash_area')
        self.restore_flash_text_colors()
        self.restore_result_panel_colors()
        self.flash_mode = None
        self.flash_winning_keys = set()
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.canvas.delete('settlement_profit')
        self.settlement_profit_tags.clear()
        self.settlement_chip_moves_started = False
        self.settlement_hold_amounts = {}
        self.push_return_amounts = {}
        self.settlement_return_animating = False
        self.settlement_return_keys.clear()
        self.pending_bet_visual_amounts.clear()
        self.pre_deal_bets = None
        self.settlement_running = False
        self.animation_running = False
        self.canvas.itemconfigure(self.animation_phase_text, text='百家宝  ·  BAC BO')
        self.accept_bets = True
        self.running = False
        self._phase = 'idle'
        self.bet_state.bets.clear()
        self.update_display()

    def draw_bets(self):
        self.canvas.delete('board_dynamic')
        self.bet_spots.clear()
        self.draw_betting_board()
        self.update_bet_chips()

    def draw_betting_board(self, canvas=None, bounds=None, interactive=True):
        """Baccarat frame with two live exact-point rows above size/parity bets."""
        c = self.canvas if canvas is None else canvas
        bx0, by0, bx1, by1 = self.BETTING_BOUNDS if bounds is None else bounds
        sx, sy = (bx1 - bx0) / 738.0, (by1 - by0) / 234.0
        scale = min(sx, sy)
        cream, ink = '#f8ecd3', '#110b07'
        blue, red = '#01479a', '#a80909'
        spots = {}

        def xy(x, y):
            return bx0 + x * sx, by0 + y * sy

        def coords(points):
            return tuple(v for x, y in zip(points[::2], points[1::2]) for v in xy(x, y))

        def text(x, y, value, size, color, tag, family='Arial'):
            return c.create_text(*xy(x, y), text=value, fill=color,
                font=(family, -max(6, round(size * scale)), 'bold'),
                anchor='center', justify='center', tags=('board_dynamic', tag))

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
                             smooth=True, fill='', outline=blue if key == 'ThreeOfKind'
                             else red if key == 'FourOfKind' else fill, width=.7,
                             tags=tags + ('bet_board_frame',))
            spot = dict(tag=tag, rect_id=rect, bounds=coords(box),
                        chip_pos=xy((x0 + x1) / 2, (y0 + y1) / 2),
                        base_odds=BET_ODDS[key], main=main, normal_outline=outline,
                        normal_outline_width=1.2, classic_shape_coords=shape,
                        label=BET_LABELS[key],
                        chip_radius=20 * scale)
            spots[key] = spot
            if interactive:
                self.register_spot(key, *spot['bounds'], spot['chip_pos'], spot['label'])
                self.bet_spots[(key, None)].update(spot)
                spots[key] = self.bet_spots[(key, None)]
                c.tag_bind(tag, '<Button-1>', lambda _e, bt=key: self.place_bet(bt))
                c.tag_bind(tag, '<Button-3>', lambda _e, bt=key: self.clear_single_bet(bt))
                c.tag_bind(tag, '<Enter>', lambda _e, bt=key: self._on_bet_enter(bt))
                c.tag_bind(tag, '<Leave>', lambda _e: self._on_bet_leave())
            return tag

        c.create_rectangle(*coords((-8, -2, 746, 244)), fill=self.FELT,
                           outline='', tags=('board_dynamic', 'bet_board_background'))
        for key, box, chinese, english, color, condition in (
                ('ThreeOfKind', (0, 0, 116, 156), '三个一样', 'THREE OF\nA KIND', blue, '至少3颗同点数'),
                ('FourOfKind', (622, 0, 738, 156), '四个一样', 'FOUR OF\nA KIND', red, '4颗均为同点数')):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, cream)
            spots[key]['label_item'] = text(cx, 23, chinese, 19, color, tag, 'Microsoft YaHei UI')
            text(cx, 57, english, 15, color, tag)
            spots[key]['odds_item'] = text(cx, 101, BET_ODDS[key], 22, color, tag)
            text(cx, 138, condition, 10, color, tag, 'Microsoft YaHei UI')

        # One shared heading, a left row label, and aligned point columns.
        # Win 2 remains disabled because two cannot strictly beat another sum.
        c.create_polygon(*rounded(122, 0, 616, 110), smooth=True,
                         fill='#000000', outline='#7794aa',
                         width=max(1, 2 * scale), tags=('board_dynamic', 'point_panel'))
        text(369, 12, '点数', 16, cream, 'point_heading', 'Microsoft YaHei UI')
        gap = 1
        cell_width = (612 - 162 - gap * 10) / 11
        for prefix, heading, top, palette, accent in (
                ('Win', '获胜', 26, WIN_POINT_COLORS, '#568bc7'),
                ('Tie', '和局', 68, TIE_POINT_COLORS, self.TIE_GREEN)):
            c.create_polygon(*rounded(126, top, 158, top + 40), smooth=True,
                             fill=palette[-1], outline=accent, width=1,
                             tags=('board_dynamic', f'{prefix.lower()}_point_row_label'))
            text(142, top + 20, heading, 14, palette[0],
                 f'{prefix.lower()}_point_heading', 'Microsoft YaHei UI')
            for point in range(2, 13):
                key = f'{prefix} {point}'
                left = 162 + (point - 2) * (cell_width + gap)
                cx = left + cell_width / 2
                box = (left, top, left + cell_width, top + 40)
                if key not in POINT_BETS:
                    tag = 'win_point_2_disabled'
                    c.create_polygon(*rounded(*box), smooth=True, fill='#303844',
                                     outline='#536174', width=1,
                                     tags=('board_dynamic', tag))
                    text(cx, top + 12, '2', 16, '#94a3b8', tag)
                    text(cx, top + 28, '—', 10, '#94a3b8', tag)
                    continue
                fill = palette[point - 2]
                foreground = ('black' if key in ('Win 7', 'Win 8', 'Tie 8')
                              else self.contrast_text_color(fill))
                tag = panel(key, box, fill, outline=accent, shadow=False)
                spots[key]['label_item'] = text(cx, top + 12, str(point), 16, foreground, tag)
                spots[key]['odds_item'] = text(cx, top + 28, BET_ODDS[key], 10, foreground, tag)

        # Size and parity have moved below the two point rows.
        for key, box, fill, color, chinese in (
                ('Small', (122, 116, 241, 156), '#f3d180', '#503809', '小 2–8'),
                ('Odd', (247, 116, 366, 156), '#97d3c5', '#103d36', '单'),
                ('Even', (372, 116, 491, 156), '#9fc7e8', '#153b60', '双'),
                ('Large', (497, 116, 616, 156), '#e9b1bf', '#5b2339', '大 9–12')):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, fill)
            spots[key]['label_item'] = text(cx, 129, chinese, 17, color, tag, 'Microsoft YaHei UI')
            spots[key]['odds_item'] = text(cx, 148, BET_ODDS[key], 14, color, tag)

        for key, box, fill, chinese, english in (
                ('PlayerPair', (0, 162, 122, 232), '#334458', '闲对', 'PLAYER PAIR'),
                ('Player', (128, 162, 306, 232), '#0046a0', '闲家', 'PLAYER'),
                ('Tie', (312, 162, 426, 232), '#006a35', '和', 'TIE'),
                ('Banker', (432, 162, 610, 232), '#bf0711', '庄家', 'BANKER'),
                ('BankerPair', (616, 162, 738, 232), '#673c4a', '庄对', 'BANKER PAIR')):
            cx = (box[0] + box[2]) / 2
            tag = panel(key, box, fill, main=key in ('Player', 'Tie', 'Banker'))
            spots[key]['label_item'] = text(cx, 181, chinese,
                23 if key in ('Player', 'Banker') else 18, cream, tag, 'Microsoft YaHei UI')
            text(cx, 199, english, 11, cream, tag)
            spots[key]['odds_item'] = text(cx, 218, BET_ODDS[key], 14, cream, tag)
        return spots

    def save_balance(self):
        update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))


    def deal(self):
        if self.closed or not self.accept_bets or self.animation_running or self.settlement_running:
            return
        self.running = True
        self.accept_bets = False
        self.animation_running = True
        self.pending_bet_visual_amounts.clear()
        current_bets = self.snapshot_bets()
        if current_bets:
            self.last_round_bets = current_bets
        self.pre_deal_bets = dict(self.bet_state.bets)
        self.result_panel_flash_winner = None
        self.restore_result_panel_colors()
        self.update_control_states()
        self.current_result = None
        self._settled_round = False
        self._dice_recovering = False
        self._dice_round_voided = False
        self.canvas.itemconfigure(self.animation_phase_text, text='百家宝  ·  摇骰中')
        self._start_dice_roll()

    def _start_dice_roll(self, duration=None):
        self._cancel_dice_result_timeout()
        for bowl in self.bowls:
            bowl.begin(duration=duration)
        self._phase = 'shake'
        self._physics_time = self._dice_stable_time = 0.
        self._dice_rest_anchor = None
        self._tick()

    def _cancel_dice_result_timeout(self):
        if self._dice_result_timeout_id is not None:
            try:
                self.after_cancel(self._dice_result_timeout_id)
            except tk.TclError:
                pass
        self._dice_result_timeout_id = None
        self._dice_result_deadline = None

    def _arm_dice_result_timeout(self):
        self._cancel_dice_result_timeout()
        self._dice_result_deadline = time.monotonic() + self.DICE_RESULT_TIMEOUT_MS / 1000
        self._dice_result_timeout_id = self.after(
            self.DICE_RESULT_TIMEOUT_MS, self._dice_result_timed_out)

    def _dice_result_timed_out(self):
        if (self.closed or not self.running or self._phase != 'settle'
                or self._dice_result_deadline is None):
            return
        remaining = self._dice_result_deadline - time.monotonic()
        if remaining > 0:
            self._dice_result_timeout_id = self.after(
                max(1, math.ceil(remaining * 1000)), self._dice_result_timed_out)
            return
        self._cancel_dice_result_timeout()
        if self._dice_recovering:
            self._queue_dice_recovery()
        else:
            self._void_dice_round()

    def _dice_are_motionless(self, dt):
        pose = tuple(point for bowl in self.bowls for die in bowl.dice for point in die.vertices())
        anchor = self._dice_rest_anchor
        if anchor is None or any(_length(_sub(p, q)) > .00005 for p, q in zip(pose, anchor)):
            self._dice_rest_anchor = pose
            self._dice_stable_time = 0.
            return False
        self._dice_stable_time += dt
        return self._dice_stable_time >= .65

    def _void_dice_round(self):
        """Refund an invalid round once; both recovery rolls remain unrecorded."""
        if (self.closed or self._settled_round or self._dice_round_voided
                or self._dice_recovering):
            return
        self._dice_round_voided = True
        self._dice_recovering = True
        self._cancel_dice_result_timeout()
        refunded = self.bet_state.clear_all()
        self.balance += Decimal(str(refunded))
        self.pre_deal_bets = None
        self.current_result = None
        self.pending_bet_visual_amounts.clear()
        self.summary_mode = 'bet'
        self.accept_bets = False
        self.canvas.itemconfigure(self.animation_phase_text, text='本局作废，下注已退还 · 双方重摇 1 秒')
        self.update_display()
        self.save_balance()
        self._queue_dice_recovery()

    def _queue_dice_recovery(self):
        if self.closed or not self._dice_recovering or self._phase == 'recovery_wait':
            return
        self._cancel_dice_result_timeout()
        # A timeout can fire between physics frames. Cancel the old frame so
        # it cannot start a second animation loop during the new shake.
        for job in tuple(self.jobs):
            self.after_cancel(job)
        self.jobs.clear()
        self._phase = 'recovery_wait'
        self.current_result = None
        self.schedule(0, self._start_dice_recovery)

    def _start_dice_recovery(self):
        if (self.closed or not self._dice_recovering or not self._dice_round_voided
                or self._phase != 'recovery_wait'):
            return
        for index, previous in enumerate(self.bowls):
            bowl = DiceBowl(rng=previous.rng)
            bowl.color = previous.color
            self.bowls[index] = bowl
        self._start_dice_roll(duration=self.DICE_RECOVERY_SHAKE_SECONDS)

    def _finish_dice_recovery(self):
        if self.closed or not self._dice_recovering:
            return
        if any(not bowl.settled() or bowl.landing_error() for bowl in self.bowls):
            self._queue_dice_recovery()
            return
        self._cancel_dice_result_timeout()
        self._dice_recovering = False
        self.current_result = None
        self._phase = 'idle'
        self.running = self.animation_running = self.settlement_running = False
        self.accept_bets = True
        self.canvas.itemconfigure(self.animation_phase_text, text='百家宝  ·  BAC BO')
        self.draw_scene()
        self.update_display()

    def _tick(self):
        if self.closed or not self.running or self._phase not in ('shake', 'settle'):
            return
        started = time.monotonic()
        if (self._phase == 'settle' and self._dice_result_deadline is not None
                and started >= self._dice_result_deadline):
            self._dice_result_timed_out()
            return
        dt = 1 / 480
        for _ in range(16):
            if self._phase == 'shake':
                self._physics_time += dt
                for bowl in self.bowls:
                    bowl.step(dt, self._physics_time, self._physics_time < bowl.duration)
                if self._physics_time >= max(bowl.duration for bowl in self.bowls):
                    self._phase = 'settle'
                    self._arm_dice_result_timeout()
            else:
                for bowl in self.bowls:
                    bowl.step(dt, 0., False)
                if not self._dice_are_motionless(dt):
                    continue
                errors = [bowl.landing_error() for bowl in self.bowls]
                if any(errors):
                    # Only judge an elevated die after the bodies stop; normal
                    # airborne dice during a roll must not void a valid round.
                    if self._dice_recovering:
                        self._queue_dice_recovery()
                        return
                    if any(bowl.has_elevated_die() for bowl in self.bowls):
                        self._void_dice_round()
                        return
                    continue
                if time.monotonic() >= self._dice_result_deadline:
                    self._dice_result_timed_out()
                    return
                for bowl in self.bowls:
                    for die in bowl.dice:
                        die.v = die.omega = (0., 0., 0.)
                if self._dice_recovering:
                    self._finish_dice_recovery()
                    return
                try:
                    values = self.bowls[0].values() + self.bowls[1].values()
                except ValueError:
                    continue
                self._cancel_dice_result_timeout()
                self.current_result = BacBoHistory.from_dice(values)
                self._phase = 'landed'
                self._finish_round()
                return
        self.draw_scene()
        delay = max(1, 33 - round((time.monotonic() - started) * 1000))
        self.schedule(delay, self._tick)

    def _finish_round(self):
        if (self.closed or self._settled_round or self._dice_round_voided
                or self._dice_recovering or self.current_result is None
                or self.pre_deal_bets is None):
            return
        self._cancel_dice_result_timeout()
        values = self.bowls[0].values()+self.bowls[1].values()
        result = BacBoHistory.from_dice(values)
        self.current_result = result
        self._settled_round = True
        self._phase = 'flash'
        returns = settle_bets(self.pre_deal_bets, result)
        credit = sum(returns.values(), Decimal(0))
        self.balance += credit
        self.last_win_amount = credit
        self.flash_winning_keys = {(bet_type, None) for bet_type in BET_LABELS
                                   if return_factor(bet_type, result) > 1}
        self.flash_winner_amounts = {}
        self.flash_original_amounts = {}
        self.push_return_amounts = {}
        self.settlement_hold_amounts = {}
        self.settlement_profit_tags = {}
        self.settlement_chip_moves_started = False
        for bet_type, returned in returns.items():
            key = (bet_type, None)
            stake = self.pre_deal_bets[bet_type]
            if return_factor(bet_type, result) > 1:
                self.flash_winner_amounts[key] = float(returned - Decimal(str(stake)))
                self.flash_original_amounts[key] = float(stake)
                self.settlement_hold_amounts[key] = float(stake)
            elif returned > 0:
                # 和局时闲/庄主注直接减半，不参与闪烁和飞回动画
                if result['winner'] == 'Tie' and bet_type in ('Player', 'Banker'):
                    continue
                self.push_return_amounts[bet_type] = float(returned)
                self.settlement_hold_amounts[key] = float(stake)
        self.bet_state.bets.clear()
        self.summary_mode = 'win'
        self.result_panel_flash_winner = result['winner']
        self.accept_bets = False
        self.settlement_running = True
        self.animation_running = False
        self.flash_mode = None
        try:
            self.history.add(result)
            self.temp_history.add(result)
            self.big_road_auto_follow = True
        except OSError as exc:
            messagebox.showerror('历史记录', f'保存历史记录失败：{exc}', parent=self)
        self.save_balance()
        self.refresh_history()
        self.draw_scene()
        self.update_display()
        self.settlement_flash_step = 0
        self.run_settlement_flash()


    def _bowl_center_in_zone(self, index, picture=None):
        """Align the resting bowl's visible outer edge, ignoring image padding."""
        if index in self._bowl_home_centers:
            return self._bowl_home_centers[index]
        width = BOWL_DISPLAY_SIZE[0]
        if picture is not None:
            left, _top, right, _bottom = picture.getbbox()
        else:
            # The vector renderer uses the same outer dish radius/projection.
            sx = width / round(196 * BOWL_SCALE)
            radius = .094 * BOWL_SCALE * BOWL_RADIUS_SCALE * 680
            left = (98 * BOWL_SCALE - radius) * sx
            right = (98 * BOWL_SCALE + radius) * sx
        zone = self.player_zone_rect if index == 0 else self.banker_zone_rect
        x0, _y0, x1, _y1 = self.canvas.coords(zone)
        center = (x1 - self.DICE_ZONE_EDGE_GAP - right + width / 2 if index == 0
                  else x0 + self.DICE_ZONE_EDGE_GAP - left + width / 2)
        self._bowl_home_centers[index] = center
        return center

    def draw_scene(self):
        c = self.canvas
        if not hasattr(self, 'player_zone_rect'):
            self.player_zone_rect = c.create_rectangle(28, 48, 378, 303,
                fill=self.PLAYER_ZONE_BASE, outline='#6386a5', width=2, tags='scene')
            self.banker_zone_rect = c.create_rectangle(394, 48, 752, 303,
                fill=self.BANKER_ZONE_BASE, outline='#a56a6d', width=2, tags='scene')
            self.player_zone_label = c.create_text(160, 70, text='闲 PLAYER',
                fill='#93b9ff', font=('Arial', 21, 'bold'), tags='scene')
            self.banker_zone_label = c.create_text(530, 70, text='庄 BANKER',
                fill='#ffaaaa', font=('Arial', 21, 'bold'), tags='scene')
            self.player_score_text = c.create_text(42, 151, anchor='w', text='—',
                fill='white', font=self.SCORE_FONT, tags='scene')
            self.banker_score_text = c.create_text(738, 151, anchor='e', text='—',
                fill='white', font=self.SCORE_FONT, tags='scene')
        photos = []
        if ImageTk is None:
            c.delete('scene_bowls')
        for index, bowl in enumerate(self.bowls):
            if ImageTk is not None:
                picture = render_bowl(bowl)
                cx = self._bowl_center_in_zone(index, picture)
                photo = ImageTk.PhotoImage(picture, master=c)
                photos.append(photo)
                if index < len(self._bowl_image_items):
                    c.itemconfigure(self._bowl_image_items[index], image=photo)
                    c.coords(self._bowl_image_items[index], cx, 92)
                else:
                    self._bowl_image_items.append(c.create_image(
                        cx, 92, image=photo, anchor='n', tags=('scene', 'scene_bowls')))
            else:
                self._draw_bowl_vectors(bowl, self._bowl_center_in_zone(index))
        self._photos = photos
        for bowl, item in zip(self.bowls, (self.player_score_text, self.banker_score_text)):
            readable = self._phase in ('idle', 'landed', 'flash') and bowl.settled() and not bowl.landing_error()
            c.itemconfigure(item, text=str(sum(bowl.values())) if readable else '—')
            c.tag_raise(item)


    def _draw_bowl_vectors(self, bowl, cx):
        # Pillow is optional; Tk uses Sicbo's identical geometry and projection.
        width, height = BOWL_DISPLAY_SIZE
        sx, sy = width / round(196 * BOWL_SCALE), height / round(138 * BOWL_SCALE)
        for meshes in bowl_mesh(bowl):
            for _depth, points, color, line, line_width in meshes:
                projected = [(cx - width / 2 + x * sx, 92 + y * sy + DOME_EXTRA_HEIGHT_PX)
                             for x, y in (project_bowl_point(p, bowl) for p in points)]
                if color and color[3] > 100:
                    self.canvas.create_polygon(*[v for p in projected for v in p],
                        fill='#%02x%02x%02x' % color[:3], outline='', tags=('scene', 'scene_bowls'))
                if line:
                    closed = projected + ([projected[0]] if len(projected) > 2 else [])
                    self.canvas.create_line(*[v for p in closed for v in p],
                        fill='#%02x%02x%02x' % line[:3], width=line_width * sy,
                        tags=('scene', 'scene_bowls'))


    def refresh_history(self):
        self.history_data = list(reversed(self.history.records))
        self.bead_data = list(reversed(self.temp_history.records))
        self.update_history_table()

    def draw_history_panel(self):
        """Right-side history panel with Roads/Data tabs."""
        c = self.canvas
        x0, y0, x1, y1 = self.HISTORY_X0, 4, self.HISTORY_X1, 620
        c.create_rectangle(x0, y0, x1, y1, fill='#211811',
                           outline=self.PANEL_LINE, width=2, tags='static')
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
        bead_cell = 27
        bead_cols = 12
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
        self._update_road_summary(self._marker_road_records())

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
            p, b = record.get('player_dice') or [], record.get('banker_dice') or []
            player_pair = p[0] == p[1] if len(p) >= 2 else bool(record.get('player_pair'))
            banker_pair = b[0] == b[1] if len(b) >= 2 else bool(record.get('banker_pair'))
            counts['Pair Player'] += int(player_pair)
            counts['Pair Banker'] += int(banker_pair)
            # Same definition as the bead plate: four equal dice.
            counts['Twin Pair'] += int(player_pair and banker_pair and len(p) >= 2
                                       and len(b) >= 2 and p[0] == b[0])
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
        c.create_text(x0, 82, anchor='w', text='本轮统计',
                      font=('Arial', 12, 'bold'), fill='#e7d36c',
                      tags='history_panel_content')
        self.base_stats_geometry = self._draw_stats_grid(x0, 98, x1, 306, 6)


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

    def _marker_road_records(self):
        """Exactly the 12 x 6 bead window, advancing by complete columns."""
        records = list(self.bead_data)
        rows, capacity = 6, 72
        overflow = max(0, len(records) - capacity)
        start = ((overflow + rows - 1) // rows) * rows
        return records[start:start + capacity]

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
                text = {'Player': '闲', 'Banker': '庄', 'Tie': '和'}.get(winner, '')
            self.canvas.create_text(cx, cy, text=text, font=('Arial', 12, 'bold'),
                                    fill='white', tags='history_dynamic')

            # Pair markers remain dots only (never text), with stronger colour,
            # a larger radius and a white rim so they remain visible on the bead.
            pair_r = max(4.0, cell * 0.155)
            inset = radius * 0.76
            dice = (record.get('player_dice') or []) + (record.get('banker_dice') or [])
            twin_pair = len(dice) == 4 and len(set(dice)) == 1
            if record.get('player_pair'):
                px, py = cx - inset, cy - inset
                self.canvas.create_oval(px - pair_r, py - pair_r, px + pair_r, py + pair_r,
                                        fill='#000000' if twin_pair else '#145dff', outline='#ffffff', width=2,
                                        tags='history_dynamic')
            if record.get('banker_pair'):
                px, py = cx + inset, cy + inset
                self.canvas.create_oval(px - pair_r, py - pair_r, px + pair_r, py + pair_r,
                                        fill='#000000' if twin_pair else '#ff2238', outline='#ffffff', width=2,
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
                if ties > 1:
                    self.canvas.create_text(
                        cx + radius * 0.45, cy - radius * 0.45, text=str(ties),
                        font=('Arial', 6, 'bold'), fill=self.TIE_GREEN,
                        tags='history_dynamic')

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


    def update_history_table(self):
        if not hasattr(self, 'canvas'):
            return
        self.canvas.delete('history_dynamic')
        records = list(self.history_data[-self.MAX_RECORDS:])
        if self.history_panel_mode == 'data':
            self._draw_round_statistics(records)
            return
        big_cells = self._build_big_road(records)
        self._draw_big_road(big_cells)
        self._draw_derived_road('eye', self._derive_road(records, 1), 'ring')
        self._draw_derived_road('cockroach', self._derive_road(records, 3), 'slash')
        bead_records = self._marker_road_records()
        self._draw_bead_plate(bead_records)
        self._update_road_summary(bead_records)
        self._draw_derived_road('small', self._derive_road(records, 2), 'dot')
        self._draw_next_round_indicator(records)

    def _next_road_color(self, records, candidate, offset):
        simulated = list(records) + [{
            'winner': candidate, 'player_pair': False, 'banker_pair': False,
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

    @classmethod
    def result_color(cls, winner):
        return {'Player': cls.PLAYER_BLUE, 'Banker': cls.BANKER_RED,
                'Tie': cls.TIE_GREEN}.get(winner, '#888888')


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

        dialog.title('百家宝 · 游戏说明')
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
            text='百家宝  BAC BO',
            font=(font_name, FONT_TITLE, 'bold'),
            fg=GOLD, bg=HEADER
        ).place(x=24, y=10)

        tk.Label(
            header,
            text='玩法 · 摇碗流程 · 下注区域 · 限红 · 赔付表',
            font=(font_name, FONT_SMALL),
            fg=MUTED, bg=HEADER
        ).place(x=25, y=48)

        close_btn = tk.Button(
            header,
            text='关闭  ESC',
            command=dialog.destroy,
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
        # 主体：左 sidebar + 右 content（grid 布局，滚动条与内容互不重叠）
        # ================================================================
        body = tk.Frame(dialog, bg=BG)
        body.pack(fill=tk.BOTH, expand=True)

        # ---------------- 左侧 sidebar ----------------
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

        # ---------------- 右侧 content（用 grid 分隔 canvas / scrollbar）----------------
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

        # 关键：画布固定在列 0 并占满，滚动条固定在列 1 仅占自身宽度
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

        # ---------------- 鼠标滚轮（右区独立滚动） ----------------
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

        # 关键改动：body 里允许用 \n 显式换行，不再使用 wraplength 自动折行
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
            grid.grid_columnconfigure(1, minsize=150)

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
        # 各主题页面（长文本使用 \n 显式换行）
        # ================================================================
        def page_rules():
            section_title('玩法与摇碗流程', '每边 2 颗标准六面骰 · 更大方获胜')

            card = make_card()
            add_rule(
                card, '基本规则',
                '每边各有 2 颗标准六面骰子，点数总和较大的一方获胜。\n'
                '每局同时摇动两个透明骰盅，骰子自然翻滚和碰撞；\n'
                '两边均停稳后，只取真实朝上的点数作为最终结果。'
            )
            add_rule(
                card, '和局处理',
                '双方点数总和相同时判为和局。\n'
                '下注闲家或庄家的主注，在和局时退还一半本金；\n'
                '和局独立下注的赔付按双方各自总点数决定。'
            )
            add_rule(
                card, '异常重摇',
                '确认骰子静止后仍上下重叠，或停止摇动后8秒内未确定结果，\n'
                '本局作废并退还全部下注，随后双方同时重摇1秒。\n'
                '重摇结果不计入任何历史记录JSON，恢复完成后可再次下注。'
            )

            flow_card = make_card(title='摇骰流程')
            for title, body in (
                ('① 摇骰', '两个骰盅各摇动5–8秒，骰子在盅内自然翻滚并碰撞。'),
                ('② 停稳', '骰子落地且朝上，在连续静止0.65秒后读取点数。'),
                ('③ 显示', '原位显示闲、庄两边总点数，朝向和点数保持一致。'),
                ('④ 结算', '按桌面所示赔率派彩，中奖区域闪烁，返还筹码飞回筹码架。'),
            ):
                add_rule(flow_card, title, body, accent='#7cc8aa')

        def page_board():
            section_title('下注区示意图', f'{len(BET_LABELS)} 个下注区 · 左键下注 / 右键清除单区')

            card = make_card()
            bet_cv = tk.Canvas(card, width=680, height=360,
                               bg=PANEL, highlightthickness=0)
            bet_cv.pack(padx=14, pady=(6, 16))

            bet_cv.create_rectangle(6, 6, 674, 354,
                                    fill='#0e3d3d', outline='#3d6a68', width=2)

            bet_cv.create_text(
                24, 26, anchor='w', text='下注区示意',
                font=(font_name, FONT_SMALL, 'bold'), fill=TEXT)
            bet_cv.create_text(
                656, 26, anchor='e', text='最低 $100 · 100 的倍数',
                font=(font_name, 12), fill='#a8c2c0')

            self.draw_betting_board(canvas=bet_cv, bounds=(22, 66, 658, 330),
                                    interactive=False)

            tip_card = make_card()
            add_rule(tip_card, '左键下注',
                     '点击任意下注区，投入当前选中的筹码面额。')
            add_rule(tip_card, '闲 / 庄二选一',
                     '同一局只可选择闲家或庄家其中一边主注；\n'
                     '清除已选主注后可换边，双方对子及其他边注仍可独立下注。')
            add_rule(tip_card, '右键清除',
                     '右键点击某个下注区，退还该区域的全部下注。')
            add_rule(tip_card, '全清 / 重复',
                     '底部「清除」退还本局所有下注；\n'
                     '「重复下注」按上一局金额重新下注。')

        def page_main_payout():
            section_title('主注与和局赔率', '赔率表示利润赔率；和局闲庄主注退一半本金')

            card = make_card()
            main_table = table_block(card, '主注', [
                ('闲家获胜',          '1:1'),
                ('庄家获胜',          '1:1'),
                ('和局 · 闲家主注',   '退还一半本金'),
                ('和局 · 庄家主注',   '退还一半本金'),
            ])
            main_table.pack(fill=tk.X, padx=16, pady=(6, 12))

            tie_table = table_block(card, '和局独立下注 · 按双方各自总点数', [
                ('双方点数 2 或 12',   '88:1'),
                ('双方点数 3 或 11',   '25:1'),
                ('双方点数 4 或 10',   '10:1'),
                ('双方点数 5 或 9',    '6:1'),
                ('双方点数 6 / 7 / 8', '4:1'),
            ])
            tie_table.pack(fill=tk.X, padx=16, pady=(0, 16))

            point_card = make_card(title='获胜点数 / 和局点数')
            add_rule(point_card, '获胜点数',
                     '仅较高一方的总点数命中；平局时，仅对应点数的获胜注退还全部本金。\n'
                     '例如6比5：「6点获胜」中奖；6比6：「6点获胜」Push，其他点数获胜注输。\n'
                     '2点无法单独获胜，因此该格置灰，不接受下注。')
            add_rule(point_card, '和局点数',
                     '必须双方总点数相同，且等于所选点数才中奖。\n'
                     '例如6比6：「6点和局」中奖；6比5：「6点和局」输。\n'
                     '所有点数均按每边两颗骰子的总点数判定，不把双方点数相加。')
            for caption, prefix, odds in (
                    ('获胜点数净赔率', 'Win', WIN_POINT_PROFIT_ODDS),
                    ('和局点数净赔率', 'Tie', TIE_POINT_PROFIT_ODDS)):
                point_table = table_block(point_card, caption,
                    [(f'{point}点', BET_ODDS[f'{prefix} {point}']) for point in odds])
                point_table.pack(fill=tk.X, padx=16, pady=(0, 16))

        def page_side_payout():
            section_title('边注赔率表', '大小 / 单双按胜方点数 · 对子按任意一边')

            card = make_card()
            grid = tk.Frame(card, bg=PANEL)
            grid.pack(fill=tk.X, padx=16, pady=16)
            grid.grid_columnconfigure(0, weight=1, uniform='payout')
            grid.grid_columnconfigure(1, weight=1, uniform='payout')

            tables = [
                ('大小 / 单双', [
                    ('小 2–8',  '1:1'),
                    ('大 9–12', '0.92:1'),
                    ('单',      '0.97:1'),
                    ('双',      '0.97:1'),
                ]),
                ('点数 / 对子', [
                    ('三个一样',  '9:1'),
                    ('四个一样',  '205:1'),
                    ('闲家对子',  '4.8:1'),
                    ('庄家对子',  '4.8:1'),
                ]),
            ]

            for idx, (title, rows) in enumerate(tables):
                block = table_block(grid, title, rows)
                block.grid(
                    row=idx // 2, column=idx % 2, sticky='nsew',
                    padx=((0, 8) if idx % 2 == 0 else (8, 0)),
                    pady=6
                )

            notes = make_card(title='判定说明')
            add_rule(notes, '大小判定',
                     '按「胜方」的点数判定；\n'
                     '和局时按四颗骰子的总点数判定。')
            add_rule(notes, '单双判定',
                     '按「胜方」的点数判定；\n'
                     '和局不中奖。')
            add_rule(notes, '对子判定',
                     '只要任意一边的两颗骰子点数相同，即判定为该边的对子；\n'
                     '闲家对子、庄家对子分别独立结算。')
            add_rule(notes, '三个 / 四个一样',
                     '四颗骰子中任意三颗点数相同即中「三个一样」；\n'
                     '四颗全部相同才中「四个一样」。两者可同时中奖。')

        def page_limits():
            section_title('下注限制与操作', '每局总下注上限 $2,000,000')

            card = make_card()
            limits_table = table_block(card, '限红', [
                ('下注单位',           '100 及其倍数'),
                ('闲家 / 庄家 各上限', '$500,000'),
                ('和局 上限',          '$100,000'),
                ('每个边注 上限',      '$30,000'),
                ('每局总下注 上限',    '$2,000,000'),
            ])
            limits_table.pack(fill=tk.X, padx=16, pady=(6, 12))

            op_card = make_card()
            add_rule(op_card, '闲 / 庄二选一',
                     '闲家与庄家主注不可同时下注；先清除原主注即可换边。')
            add_rule(op_card, '左键下注',
                     '点击任意下注区，投入当前选中的筹码面额。')
            add_rule(op_card, '右键清除',
                     '右键点击某个下注区，退还该区域的全部下注。')
            add_rule(op_card, '清除本局',
                     '点击底部「清除」按钮，退还本局所有下注。')
            add_rule(op_card, '重复下注',
                     '点击「重复下注」按钮，按上一局的下注金额重新下注。')
            add_rule(op_card, 'Enter 摇碗',
                     '按 Enter 键或点击「摇碗」按钮开始本局。')

        def page_history():
            section_title('历史记录说明', '右侧面板 · 道路图 / 珠盘路 / 预测指示')

            overview = make_card(title='右侧历史记录面板总览')
            add_rule(
                overview, '面板结构',
                '右侧历史记录面板分为「道路」和「数据」两个标签页：\n'
                '「道路」显示各种路单图，用于观察走势；\n'
                '「数据」显示本轮统计的各类结果数量。'
            )
            add_rule(
                overview, '打开与切换',
                '点击顶部标签即可在「道路」与「数据」之间切换。\n'
                '「道路」标签下会同时显示大路、大眼仔、小路、蟑螂路\n'
                '以及珠盘路和下局预测指示。'
            )

            road_card = make_card(title='道路图说明')
            add_rule(
                road_card, '大路 BIG ROAD',
                '每局按顺序记录胜方：蓝圈 = 闲家获胜，红圈 = 庄家获胜。\n'
                '相同结果向下连成一条龙，换边则向右另起一列。\n'
                '和局不单独占格，而是在当前格子上画绿色斜线；\n'
                '若一局内出现多次和局，斜线角上会标注累计次数。\n'
                '闲对 / 庄对分别以蓝色、红色小圆点标在对应格子上。'
            )
            add_rule(
                road_card, '珠盘路 BEAD PLATE',
                '按时间顺序每局占一格，蓝 = 闲胜，红 = 庄胜，绿 = 和局。\n'
                '格内文字默认显示「闲 / 庄 / 和」，点击珠盘路区域后\n'
                '切换为显示该局胜方点数；再点一次切回文字。\n'
                '珠盘路只保存最近 72 局，每写入第 73 局时会自动删除\n'
                '最旧的 6 局，再写入最新 1 局，因此始终显示最新结果。\n'
                '底部#数字为当前珠盘局数；两行依次统计闲、庄、和及闲对、庄对、\n'
                '四个一样。四个一样的珠盘标记使用两个黑点。'
            )
            add_rule(
                road_card, '大眼仔 BIG EYE BOY',
                '由大路的走势推导出来的衍生路，用空心圈表示。\n'
                '红圈 = 顺势，蓝圈 = 逆势，用来判断大路是否延续。'
            )
            add_rule(
                road_card, '小路 SMALL ROAD',
                '同样由大路推导的衍生路，用实心圆表示。\n'
                '红 = 顺势，蓝 = 逆势，观察角度比大眼仔更靠后一步。'
            )
            add_rule(
                road_card, '蟑螂路 COCKROACH PIG',
                '第三条衍生路，用斜线表示。\n'
                '红 = 顺势，蓝 = 逆势，观察角度又比小路靠后一步。\n'
                '三条衍生路同时观察，可以互相印证走势。'
            )

            predict_card = make_card(title='下局预测指示')
            add_rule(
                predict_card, '预测位置',
                '位于面板右下方，分为「闲」和「庄」两列。\n'
                '三行分别对应：大眼仔、小路、蟑螂路。'
            )
            add_rule(
                predict_card, '符号含义',
                '每一格的符号代表：如果下一局开出该方（闲或庄），\n'
                '对应的那条衍生路将会出现什么颜色。\n'
                '符号颜色与衍生路一致：红 = 顺势，蓝 = 逆势。\n'
                '若显示「—」则表示该路暂不产生新标记。'
            )

            data_card = make_card(title='数据页说明')
            add_rule(
                data_card, '统计内容',
                '「数据」标签页统计本轮（当前保存记录范围内）的：\n'
                '总局数、闲胜局数、庄胜局数、和局数、\n'
                '闲家对子次数、庄家对子次数。'
            )

            nav_card = make_card(title='操作提示')
            add_rule(
                nav_card, '大路滚动',
                '大路最多可容纳 50 列，使用大路下方的横向滚动条\n'
                '可以左右拖动查看较早的记录。\n'
                '新结果出现时会自动跟随到最新位置。'
            )
            add_rule(
                nav_card, '珠盘路切换',
                '在珠盘路区域内单击，可在「文字」与「点数」之间切换显示。'
            )

        def page_notes():
            section_title('重要提示')

            card = make_card()
            add_rule(
                card, '和局主注退一半',
                '和局时，已选的闲家或庄家主注会立即退还一半本金，\n'
                '不参与中奖闪烁动画。\n'
                '退还金额直接计入余额。'
            )
            add_rule(
                card, '获胜筹码',
                '本金筹码留在下注区中央，净赢额筹码显示在本金左上侧。\n'
                '闪烁结束后，本金与净赢额分别飞回筹码架；\n'
                '点数区与其他下注区使用相同大小的筹码。'
            )
            add_rule(
                card, '大小 / 单双的结算依据',
                '大小按「胜方」的点数判定（和局按四颗总点数）。\n'
                '单双按「胜方」的点数判定，和局不中奖。'
            )
            add_rule(
                card, '对子判定',
                '只要任意一边的两颗骰子点数相同，即判定为该边的对子。\n'
                '闲家对子、庄家对子分别独立结算。'
            )
            add_rule(
                card, '三个一样 / 四个一样',
                '四颗骰子中任意三颗点数相同即中「三个一样」；\n'
                '四颗点数全部相同才中「四个一样」。\n'
                '两者为独立下注区，可同时中奖。'
            )
            add_rule(
                card, '结果读取时机',
                '只有在碗盖完全展开、画面完全转为俯视 2D 之后，\n'
                '系统才会读取朝上的点数并显示比分与结算结果。'
            )

        # ================================================================
        # 左侧主题按钮
        # ================================================================
        themes = [
            ('玩法与摇碗流程', page_rules),
            ('下注区示意图',   page_board),
            ('主注与和局赔率', page_main_payout),
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

    def exit_game(self):
        if self.closed:
            return
        self.closed = True
        self.accept_bets = False
        self._cancel_dice_result_timeout()
        for job in tuple(self.jobs)+tuple(self.chip_motion_after_ids):
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self.jobs.clear()
        self.chip_motion_after_ids.clear()
        if self.settlement_after_id is not None:
            try:
                self.after_cancel(self.settlement_after_id)
            except tk.TclError:
                pass
            self.settlement_after_id = None
        self.canvas.delete('chip_motion')
        self.balance += Decimal(str(self.bet_state.clear_all()))
        self.final_balance = float(self.balance)
        self.save_balance()
        if callable(self.on_back):
            self.on_back(self.final_balance)


    on_close = exit_game


class BacboGUI(BacBoGame):
    """Compatibility with the original BacBo class name (embedded Tk frame)."""
    def __init__(self, root, username=None, initial_balance=10000,
                 on_back=None, on_balance_change=None):
        super().__init__(root, initial_balance, username, on_back, on_balance_change)
        self.pack(fill='both', expand=True)


def main(initial_balance=1000000, username='Guest', *, parent=None, balance=None,
         user=None, on_back=None, on_balance_change=None):
    if balance is not None:
        initial_balance = balance
    if user is not None:
        username = user
    if parent is not None:
        return BacboGUI(parent, username, initial_balance, on_back, on_balance_change)
    root = tk.Tk()
    root.title('百家宝')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    game = BacboGUI(root, username, initial_balance, on_back or (lambda _value: root.destroy()),
                     on_balance_change)
    root.protocol('WM_DELETE_WINDOW', game.exit_game)
    root.mainloop()
    return game.final_balance


if __name__ == '__main__':
    main()
