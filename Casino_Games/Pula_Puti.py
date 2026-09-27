from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from dataclasses import dataclass
try:
    from PIL import Image, ImageTk, ImageOps
except ImportError:
    Image = ImageTk = None

VERSION = "Pula-Puti-v6.0-8Bets-Physics"
FLAP_REVISION = "2026-09-22-v6-fast-reveal"

class Theme:
    """Shared interface colours and fonts."""

    APP_BG = "#1B3D31"
    PANEL = "#F2E6C9"

    TEXT = "#252A2E"
    TEXT_MUTED = "#596169"
    TEXT_DIM = "#777E83"

    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )


CHIP_CONFIGS = (
    ("$10","10","#FFA500","black"),
    ("$25","25","#00FF00","black"),
    ("$100","100","#000000","white"),
    ("$500","500","#FF7DDA","black"),
    ("$1K","1000","#FFFFFF","black"),
    ("$2.5K","2500","#FF0000","white"),
)

HIGH_CHIP_CONFIGS = (
    ("$100","100","#000000","white"),
    ("$500","500","#FF7DDA","black"),
    ("$1K","1000","#FFFFFF","black"),
    ("$5K","5000","#FF0000","white"),
    ("$10K","10000","#00FBFF","black"),
    ("$50K","50000","#00FFAE","black"),
)

def chip_amount_text(amount):
    value=int(amount)
    if value<1000:return f"{value:,}"
    unit,suffix=((1000000,"M") if value>=1000000 else
                 (10000,"W") if value>=10000 else (1000,"K"))
    tenths,remainder=divmod(value,unit//10)
    whole,decimal=divmod(tenths,10)
    label=str(whole)+(f".{decimal}" if decimal else "")
    return label+suffix+("+" if remainder else "")


class SplitFlapDigit(tk.Frame):
    """A hinged card: old upper half falls, then the new lower half unfolds."""
    WIDTH, HALF, DURATION = 27, 17, .60
    HOLD_MS = 200
    DASH_DURATION = .20
    DASH_HOLD_MS = 70
    SYMBOLS = "0123456789-"

    def __init__(self, master):
        super().__init__(master, width=27, height=34, bg="#FFFFFF",
                         highlightbackground="#C1C1C1", highlightthickness=1)
        self.pack_propagate(False)
        self._value="-"
        self._target="-"
        self._next=None
        self._job=None
        self._dead=False
        self._top=tk.Canvas(self, bg="#FFFFFF", highlightthickness=0)
        self._bottom=tk.Canvas(self, bg="#F8F8F8", highlightthickness=0)
        self._leaf=tk.Canvas(self, bg="#FFFFFF", highlightthickness=0)
        self._top.place(x=0,y=0,width=27,height=17)
        self._bottom.place(x=0,y=17,width=27,height=17)
        self._hinge=tk.Frame(self,bg="#BBBBBB",height=1)
        self._hinge.place(x=0,y=17,width=27,height=1)
        self.bind("<Destroy>",self._on_destroy,add="+")
        self._paint_rest()

    @staticmethod
    def _paint_half(canvas, digit, upper, height=17, shade=None):
        canvas.delete("all")
        if shade is not None:canvas.configure(bg=shade)
        canvas.create_text(13.5,height if upper else 0,text=digit,
                           fill="#000000",font=("Courier",max(1,round(23*height/17)),"bold"))
        canvas.create_line(1,0 if upper else height-1,26,0 if upper else height-1,
                           fill="#DDDDDD")

    def _paint_rest(self):
        self._leaf.place_forget()
        self._paint_half(self._top,self._value,True)
        self._paint_half(self._bottom,self._value,False)
        self._hinge.lift()

    def set(self, value, *, animate=True, delay=0, fast=False):
        value=str(value)
        if value not in self.SYMBOLS or len(value)!=1:
            raise ValueError("翻牌字符必须是 0–9 或 -")
        if not animate:
            self._cancel()
            self._value=self._target=value
            self._next=None
            self._paint_rest()
            return
        if value==self._target:return
        self._target=value
        self._fast=fast
        if self._job is None:
            self._job=self.after(delay,self._advance)

    def is_animating(self):
        return self._job is not None or self._value!=self._target

    def _advance(self):
        self._job=None
        if self._dead or self._value==self._target:return
        self._next=(self._target if getattr(self,"_fast",False) else self.SYMBOLS[(self.SYMBOLS.index(self._value)+1)%len(self.SYMBOLS)])
        self._step_duration=self.DASH_DURATION if self._target=="-" or getattr(self,"_fast",False) else self.DURATION
        self._step_hold_ms=self.DASH_HOLD_MS if self._target=="-" or getattr(self,"_fast",False) else self.HOLD_MS
        self._start=time.monotonic()
        self._tick()

    def _tick(self):
        self._job=None
        if self._dead:return
        progress=max(0.,min(1.,(time.monotonic()-self._start)/self._step_duration))
        if progress>=1:
            self._value=self._next
            self._next=None
            self._paint_rest()
            self._job=self.after(self._step_hold_ms,self._advance)
            return
        self._paint_half(self._top,self._next,True)
        self._paint_half(self._bottom,self._value,False)
        angle=math.pi*progress**.8
        upper=angle<math.pi/2
        height=max(1,round(self.HALF*abs(math.cos(angle))))
        y=self.HALF-height if upper else self.HALF
        tone=round(20+22*abs(math.cos(angle)))
        shade=f"#{210+tone//2:02x}{210+tone//2:02x}{210+tone//2:02x}"
        self._leaf.place(x=0,y=y,width=self.WIDTH,height=height)
        self._paint_half(self._leaf,self._value if upper else self._next,upper,height,shade)
        self._leaf.tk.call("raise",self._leaf._w)
        self._hinge.lift()
        self._job=self.after(16,self._tick)

    def _cancel(self):
        if self._job is not None:
            try:self.after_cancel(self._job)
            except tk.TclError:pass
            self._job=None

    def _on_destroy(self,event):
        if event.widget is self:
            self._dead=True
            self._cancel()


class ModernButton(tk.Button):
    def __init__(self,master,*,text,command=None,background=Theme.PANEL,
                 foreground=Theme.TEXT,font_size=10,bold=False,**kwargs):
        super().__init__(master,text=text,command=command,bg=background,fg=foreground,
                         activebackground=background,activeforeground=foreground,
                         disabledforeground=Theme.TEXT_DIM,
                         font=(Theme.FONT_CJK,font_size,"bold" if bold else "normal"),
                         relief=tk.RAISED,bd=2,overrelief=tk.RAISED,
                         highlightthickness=0,cursor="hand2",**kwargs)
        self.bind("<ButtonPress-1>",self._press,add="+")
        self.bind("<ButtonRelease-1>",self._release,add="+")
        self.bind("<Leave>",self._release,add="+")
    def _press(self,event=None):
        if str(self.cget("state"))!=tk.DISABLED:self.configure(relief=tk.SUNKEN)
    def _release(self,event=None):self.configure(relief=tk.RAISED)


# 8 blue cells, 4 replace red, 4 replace white -> 68 red, 68 white, 8 blue.
# Positions: row 2 col 5, row 2 col 14, row 4 col 5, row 4 col 14,
#            row 6 col 5, row 6 col 14, row 8 col 5, row 8 col 14 (1-based).
BLUE_CELLS = (
    5,    # 第1行第6列（原白）
    34,   # 第2行第17列（原白）
    38,   # 第3行第3列（原红）
    67,   # 第4行第14列（原红）
    80,   # 第5行第9列（原红）
    91,   # 第6行第2列（原红）
    119,  # 第7行第12列（原白）
    130,  # 第8行第5列（原白）
)

BET_LABELS = ('双红', '双白', '三红', '三白', '任意蓝', '双蓝', '红白蓝')
GRID_COLS, GRID_ROWS = 18, 8
GRID_COLORS = tuple('blue' if i in BLUE_CELLS else
                    ('red' if (i // GRID_COLS + i % GRID_COLS) % 2 == 0 else 'white')
                    for i in range(GRID_COLS * GRID_ROWS))
COLOR_HEX = {'red': '#D93C3C', 'white': '#F7F5EF', 'blue': '#163D85'}
COLOR_NAMES = {'red': '红', 'white': '白', 'blue': '蓝'}
BONUS_TIERS = {
    'Mini': ((15, 20, 25, 30), (30, 45, 20, 5), 3),
    'Maxi': ((30, 40, 50, 60), (30, 45, 20, 5), 3),
    'Minor': ((60, 80, 100, 120), (30, 45, 20, 5), 3),
    'Major': ((150, 200, 250, 300), (30, 45, 20, 5), 4),
    'Grand': ((300, 500, 750, 1000), (25, 60, 10, 5), 5),
}
BONUS_ORDER = ('Major', 'Grand', 'Mini', 'Maxi', 'Minor')


def make_bonus_deck(rng, count):
    """Shuffle the exact tier distribution for the blue-ball bonus."""
    if count not in (12, 18):
        raise ValueError('红包数量必须是12或18')
    names = ('Minor', 'Major', 'Grand') if count == 12 else tuple(BONUS_TIERS)
    deck = [name for name in names for _ in range(BONUS_TIERS[name][2])]
    rng.shuffle(deck)
    values = {name: rng.choices(spec[0], weights=spec[1], k=1)[0]
              for name, spec in BONUS_TIERS.items()}
    return tuple(deck), values

CENT = Decimal("0.01")


def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal("1000000000000"):
            raise ValueError("金额必须为有效的非负数，且不超过 1 万亿")
        return result.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("无效金额") from exc


@dataclass(frozen=True)
class TableResult:
    bets: tuple
    stake: Decimal
    outcomes: tuple
    returned: Decimal
    net: Decimal
    final_balance: Decimal
    invalid: bool
    bonus_multiplier: int = 0
    bonus_slot: int = -1
    bonus_values: tuple = ()
    bonus_outcomes: tuple = ()
    bonus_tier: str = ''


def payout_multipliers(outcomes, bonus_multiplier=0):
    """Gross return multipliers (including stake) for the seven bets."""
    colors = [GRID_COLORS[i] for i in outcomes]
    red, white, blue = (colors.count(c) for c in ('red', 'white', 'blue'))
    return (
        2 if red >= 2 else 0,               # 双红 1:1
        2 if white >= 2 else 0,             # 双白 1:1
        9 if red == 3 else 0,               # 三红 8:1
        9 if white == 3 else 0,             # 三白 8:1
        6 if blue else 0,                   # 任意蓝 5:1
        bonus_multiplier if blue >= 2 else 0,  # 双蓝：三球奖励数字之和
        12 if red == white == blue == 1 else 0,  # 红白蓝 11:1
    )


def settle_table(balance, bets, outcomes, *, bonus_multiplier=0, bonus_slot=-1, bonus_values=(), bonus_outcomes=()):
    balance = money(balance)
    bets = tuple(money(v) for v in bets)
    outcomes = tuple(outcomes)
    if len(bets) != len(BET_LABELS) or len(outcomes) != 3 or any(type(i) is not int or not 0 <= i < 144 for i in outcomes):
        raise ValueError('必须有7个下注区和3个有效落点')
    if len(set(outcomes)) != 3:
        raise ValueError('同一个格子不可以重复进入')
    stake = sum(bets, Decimal(0))
    if stake > balance:
        raise ValueError('总下注不能超过余额')
    blue_count = sum(GRID_COLORS[i] == 'blue' for i in outcomes)
    if bonus_multiplier and blue_count < 2:
        raise ValueError('奖励仅在至少两颗蓝球时有效')
    if bonus_multiplier < 0:
        raise ValueError('奖励倍率不能为负')
    bonus_values, bonus_outcomes = tuple(bonus_values), tuple(bonus_outcomes)
    returned = sum((bet * mult for bet, mult in zip(bets, payout_multipliers(outcomes, bonus_multiplier))), Decimal(0))
    return TableResult(bets, stake, outcomes, returned, returned-stake, balance-stake+returned,
                       False, bonus_multiplier, -1, bonus_values, bonus_outcomes)


@dataclass
class PhysicalBall:
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    release: float
    wx: float = 0.0
    wy: float = 0.0
    wz: float = 0.0
    in_funnel: bool = True
    escaped: bool = False


class BallPhysics:
    """World units: metre, second; 18 x 8 single-ball pockets with perimeter ramps; no target-dependent forces."""
    COLS, ROWS = GRID_COLS, GRID_ROWS
    UNIQUE_CELLS = True
    CELL_SIZE = 0.14
    WIDTH, DEPTH = GRID_COLS * CELL_SIZE, GRID_ROWS * CELL_SIZE
    RADIUS = 0.045
    OUTLET = (WIDTH / 2, DEPTH / 2)
    OUTLET_HEIGHT = 0.8
    HEIGHT_SCALE = 160.0
    DT = 1 / 960
    GRAVITY = 9.81
    FLOOR_BOUNCE = 0.88
    WALL_BOUNCE = 0.82
    BALL_BOUNCE = 0.92
    ROLL_DECEL = 0.16
    FRAME_DT = 1 / 60
    RAIL_RADIUS = 0.012
    RAIL_Z = 0.012
    RAIL_X = tuple(i * 0.14 for i in range(1, GRID_COLS))
    RAIL_Y = tuple(i * 0.14 for i in range(1, GRID_ROWS))
    FUNNEL_TOP = 1.70
    FUNNEL_RADIUS = 0.68
    NECK_RADIUS = 0.18
    FUNNEL_SLOPE = (FUNNEL_RADIUS-NECK_RADIUS)/(FUNNEL_TOP-OUTLET_HEIGHT)
    RAMP_WIDTH = 0.25
    FRONT_RAMP_DEPTH = 0.60
    RAMP_HEIGHT = 0.34
    RIM_HEIGHT = 0.035
    ALLOW_ESCAPE = False
    AIR_DRAG = 0.10

    def __init__(self, rng=None, *, allow_escape=None):
        self.allow_escape=self.ALLOW_ESCAPE if allow_escape is None else bool(allow_escape)
        rng = rng or random.SystemRandom()
        self.balls = []
        for i in range(3):
            angle = rng.uniform(0, math.tau) if i==0 else first_angle+i*math.tau/3+rng.uniform(-.25,.25)
            if i==0:first_angle=angle
            radius = rng.uniform(0.30, 0.48)
            tangent = rng.uniform(-.8, .8)
            inward = rng.uniform(0.08, 0.40)
            self.balls.append(PhysicalBall(
                self.OUTLET[0]+radius*math.cos(angle),
                self.OUTLET[1]+radius*math.sin(angle), self.FUNNEL_TOP-0.035,
                -math.sin(angle)*tangent-math.cos(angle)*inward,
                math.cos(angle)*tangent-math.sin(angle)*inward,
                rng.uniform(-.18,-.04), i*.10))
        self.time = 0.0

    @staticmethod
    def _cross(a, b):
        return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

    def _surface_contact(self, b, normal, penetration, restitution, friction):
        for axis,n in zip(("x","y","z"),normal):
            setattr(b,axis,getattr(b,axis)+n*max(0,penetration))
        arm = tuple(-self.RADIUS*n for n in normal)
        spin = self._cross((b.wx,b.wy,b.wz),arm)
        cv = tuple(getattr(b,v)+spin[i] for i,v in enumerate(("vx","vy","vz")))
        vn = sum(cv[i]*normal[i] for i in range(3))
        if vn >= 0:
            return
        e = restitution*min(1.0,max(0.0,(-vn-0.06)/0.30))
        jn = -(1+e)*vn
        tangent = tuple(cv[i]-vn*normal[i] for i in range(3))
        speed = math.sqrt(sum(x*x for x in tangent))
        jt = min(friction*jn, speed/2.5)
        impulse = tuple(jn*normal[i]-(jt*tangent[i]/speed if speed else 0) for i in range(3))
        torque = self._cross(arm,impulse)
        inertia = (2/3)*self.RADIUS**2
        for i,(v,w) in enumerate(zip(("vx","vy","vz"),("wx","wy","wz"))):
            setattr(b,v,getattr(b,v)+impulse[i])
            setattr(b,w,getattr(b,w)+torque[i]/inertia)

    def _funnel_contact(self, b):
        r=self.RADIUS;dx=b.x-self.OUTLET[0];dy=b.y-self.OUTLET[1]
        rho=math.hypot(dx,dy)
        if b.in_funnel and rho>self.FUNNEL_RADIUS+r and b.z>self.FUNNEL_TOP-r:
            b.in_funnel=False
        if b.in_funnel and b.z+r<self.OUTLET_HEIGHT:
            b.in_funnel=False
        if rho<1e-12 or b.z+r<self.OUTLET_HEIGHT or b.z-r>self.FUNNEL_TOP:return
        dr=self.FUNNEL_RADIUS-self.NECK_RADIUS
        dz=self.FUNNEL_TOP-self.OUTLET_HEIGHT
        t=((rho-self.NECK_RADIUS)*dr+(b.z-self.OUTLET_HEIGHT)*dz)/(dr*dr+dz*dz)
        if 0<t<1:
            norm=math.hypot(dr,dz)
            gap=((self.NECK_RADIUS-rho)*dz+(b.z-self.OUTLET_HEIGHT)*dr)/norm
            normal=(-dx/rho*dz/norm,-dy/rho*dz/norm,dr/norm)
            if b.in_funnel and gap<r:
                self._surface_contact(b,normal,r-gap,.62,.065)
            elif not b.in_funnel and -r<gap<0:
                self._surface_contact(b,tuple(-n for n in normal),r+gap,.62,.06)
            elif not b.in_funnel and gap>=r and b.z-r>self.OUTLET_HEIGHT:
                b.in_funnel=True
        else:
            cr,cz=(self.NECK_RADIUS,self.OUTLET_HEIGHT) if t<=0 else (self.FUNNEL_RADIUS,self.FUNNEL_TOP)
            radial,vertical=rho-cr,b.z-cz
            distance=math.hypot(radial,vertical)
            if 1e-12<distance<r:
                normal=(dx/rho*radial/distance,dy/rho*radial/distance,vertical/distance)
                self._surface_contact(b,normal,r-distance,.62,.065)

    def _terrain(self, b):
        w,d=self.WIDTH,self.DEPTH
        distances=(-b.x,b.x-w,-b.y,b.y-d)
        slopes=(self.RAMP_HEIGHT/self.RAMP_WIDTH,)*3+(self.RAMP_HEIGHT/self.FRONT_RAMP_DEPTH,)
        heights=tuple(distance*slope for distance,slope in zip(distances,slopes))
        outside=max(heights)
        if outside<=0:return 0.,(0.,0.,1.)
        index=heights.index(outside);slope=slopes[index]
        norm=math.sqrt(1+slope*slope)
        directions=((slope,0,1),(-slope,0,1),(0,slope,1),(0,-slope,1))
        return outside,tuple(n/norm for n in directions[index])

    def _contain(self, b):
        if b.escaped:return
        self._funnel_contact(b)
        if b.in_funnel:return
        r=self.RADIUS
        w=self.RAMP_WIDTH
        for axis,maximum in (("x",self.WIDTH),("y",self.DEPTH)):
            far=self.FRONT_RAMP_DEPTH if axis=="y" else w
            value=getattr(b,axis)
            if self.allow_escape and (value < -w-r or value > maximum+far+r):
                b.escaped=True
                return
            if not self.allow_escape or b.z-r < self.RAMP_HEIGHT+self.RIM_HEIGHT:
                if value < -w+r or value > maximum+far-r:
                    sign=1 if value < -w+r else -1
                    normal=(sign,0,0) if axis=="x" else (0,sign,0)
                    penetration=(-w+r-value) if sign==1 else (value-(maximum+far-r))
                    self._surface_contact(b,normal,penetration,self.WALL_BOUNCE,.08)
        if -w<=b.x<=self.WIDTH+w and -w<=b.y<=self.DEPTH+self.FRONT_RAMP_DEPTH:
            height,normal=self._terrain(b)
            distance=(b.z-height)*normal[2]
            if distance<=r:
                self._surface_contact(b,normal,r-distance,self.FLOOR_BOUNCE,.12)
        for axis,centres in (("x",self.RAIL_X),("y",self.RAIL_Y)):
            if axis=="x" and not 0<=b.y<=self.DEPTH:continue
            if axis=="y" and not 0<=b.x<=self.WIDTH:continue
            for centre in centres:
                lateral = getattr(b,axis)-centre
                vertical = b.z-self.RAIL_Z
                distance = math.hypot(lateral,vertical)
                reach = r+self.RAIL_RADIUS
                if distance < reach:
                    if distance < 1e-12:
                        normal=(0,0,1)
                    elif axis=="x":
                        normal=(lateral/distance,0,vertical/distance)
                    else:
                        normal=(0,lateral/distance,vertical/distance)
                    self._surface_contact(b,normal,reach-distance,0.78,0.10)

    def _pair_contact(self, a, b):
        delta=(b.x-a.x,b.y-a.y,b.z-a.z)
        distance=math.sqrt(sum(x*x for x in delta))
        if distance >= 2*self.RADIUS:
            return
        n=tuple(x/distance for x in delta) if distance>1e-12 else (1.,0.,0.)
        for axis,c in zip(("x","y","z"),n):
            correction=(2*self.RADIUS-distance+1e-9)*c/2
            setattr(a,axis,getattr(a,axis)-correction)
            setattr(b,axis,getattr(b,axis)+correction)
        ra=tuple(self.RADIUS*c for c in n);rb=tuple(-c for c in ra)
        sa=self._cross((a.wx,a.wy,a.wz),ra);sb=self._cross((b.wx,b.wy,b.wz),rb)
        relative=tuple(getattr(b,v)+sb[i]-getattr(a,v)-sa[i] for i,v in enumerate(("vx","vy","vz")))
        vn=sum(relative[i]*n[i] for i in range(3))
        if vn>=0:
            return
        e=self.BALL_BOUNCE*min(1.0,max(0.0,(-vn-0.06)/0.30))
        jn=-(1+e)*vn/2
        tangent=tuple(relative[i]-vn*n[i] for i in range(3))
        speed=math.sqrt(sum(x*x for x in tangent));jt=min(.12*jn,speed/5)
        impulse=tuple(jn*n[i]-(jt*tangent[i]/speed if speed else 0) for i in range(3))
        ta=self._cross(ra,tuple(-x for x in impulse));tb=self._cross(rb,impulse)
        inertia=(2/3)*self.RADIUS**2
        for i,(v,w) in enumerate(zip(("vx","vy","vz"),("wx","wy","wz"))):
            setattr(a,v,getattr(a,v)-impulse[i]);setattr(b,v,getattr(b,v)+impulse[i])
            setattr(a,w,getattr(a,w)+ta[i]/inertia);setattr(b,w,getattr(b,w)+tb[i]/inertia)

    def step(self):
        dt=self.DT
        self.time+=dt
        active=[b for b in self.balls if self.time>=b.release and (not b.escaped or b.z>-2)]
        for b in active:
            velocity=(b.vx,b.vy,b.vz)
            speed=math.sqrt(sum(v*v for v in velocity))
            acceleration=tuple(-self.AIR_DRAG*speed*v-(self.GRAVITY if i==2 else 0)
                               for i,v in enumerate(velocity))
            midpoint=tuple(v+.5*dt*a for v,a in zip(velocity,acceleration))
            mid_speed=math.sqrt(sum(v*v for v in midpoint))
            for i,(pos,vel) in enumerate(zip(('x','y','z'),('vx','vy','vz'))):
                setattr(b,pos,getattr(b,pos)+midpoint[i]*dt)
                force=-self.AIR_DRAG*mid_speed*midpoint[i]-(self.GRAVITY if i==2 else 0)
                setattr(b,vel,velocity[i]+force*dt)
        for _ in range(4):
            for b in active:self._contain(b)
            for i,a in enumerate(active):
                for b in active[i+1:]:
                    if not a.escaped and not b.escaped:self._pair_contact(a,b)
        for b in active:
            self._contain(b)
            if not b.in_funnel and not b.escaped and b.z<=self.RADIUS+1e-7 and abs(b.vz)<1e-7:
                b.vz=0.0
                speed=math.hypot(b.vx,b.vy)
                slip=math.hypot(b.vx-self.RADIUS*b.wy,b.vy+self.RADIUS*b.wx)
                if slip < 0.03:
                    factor=max(0,1-self.ROLL_DECEL*dt/speed) if speed else 0
                    b.vx*=factor;b.vy*=factor
                    b.wx*=factor;b.wy*=factor
                    b.wz*=max(0,1-3*dt)

    def poses(self):
        return tuple((b.x/self.WIDTH, b.y/self.DEPTH,
                      (b.z-self.RADIUS)*self.HEIGHT_SCALE,
                      2 if b.escaped else (0 if b.in_funnel else 1))
                     if self.time >= b.release else None for b in self.balls)

    def cell_index(self, ball):
        if ball.escaped or not (0 <= ball.x < self.WIDTH and 0 <= ball.y < self.DEPTH):
            return -1
        return int(ball.x / (self.WIDTH / self.COLS)) + self.COLS * int(ball.y / (self.DEPTH / self.ROWS))

    def simulate(self):
        frames = [self.poses()]
        quiet = 0
        for tick in range(round(60/self.DT)):
            self.step()
            if (tick+1) % round(self.FRAME_DT/self.DT) == 0:
                frames.append(self.poses())
            resting = self.time > 0.5 and all(
                b.escaped or (not b.in_funnel and b.z <= self.RADIUS+1e-8
                              and b.vz == 0 and math.hypot(b.vx,b.vy) < 1e-8)
                for b in self.balls)
            quiet = quiet+1 if resting else 0
            if quiet >= round(.25/self.DT):
                frames.append(self.poses())
                outcomes = tuple(self.cell_index(b) for b in self.balls)
                if any(i < 0 for i in outcomes) or (self.UNIQUE_CELLS and len(set(outcomes)) != 3):
                    raise RuntimeError("落球未进入三个不同格子，本轮未扣款。")
                return frames, outcomes
        raise RuntimeError("物理模拟未在时限内停稳，本轮未扣款。")


class BonusBallPhysics(BallPhysics):
    COLS, ROWS = 3, 2
    UNIQUE_CELLS = False
    RAIL_X = (BallPhysics.WIDTH/3, 2*BallPhysics.WIDTH/3)
    RAIL_Y = (BallPhysics.DEPTH/2,)


class AccountStore:
    def __init__(self, username, demo=False):
        self.username, self.demo = username, demo
        self.path = None
        if demo:
            return
        root = next((p for p in Path(__file__).resolve().parents
                     if (p / "A_Tools/Account/secure_json.py").is_file()), None)
        if root is None:
            raise RuntimeError("找不到原项目的加密账户模块。请放回原项目，或用 --demo 体验虚拟积分版。")
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        account_module=importlib.import_module("A_Tools.Account")
        account_module.install_secure_json()
        self.path = root / "A_Tools/Account/saving_data.json"

    def save(self, balance):
        if self.demo:
            return
        with open(str(self.path), "r", encoding="utf-8") as stream:
            users = json.load(stream)
        if not isinstance(users, list):
            raise ValueError("账户数据格式不正确")
        account = next((u for u in users if isinstance(u, dict)
                        and u.get("user_name") == self.username), None)
        if account is None:
            raise ValueError("账户不存在，请从原项目登录后开启游戏")
        account["cash"] = f"{balance:.2f}"
        with open(str(self.path), "w", encoding="utf-8") as stream:
            json.dump(users, stream, ensure_ascii=False, indent=4)


class DropBallHistory:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.data = {'Total': 0, 'Record2': {}}
        if self.path and self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(self.data, dict) or not isinstance(self.data.get('Record2'), dict):
                raise ValueError('Pula-Puti 历史记录格式错误')
        for entry in self.data['Record2'].values():
            entry['colors']=['blue' if c=='green' else c for c in entry['colors']]

    def latest_double(self):
        record=self.data.get('LatestDouble')
        if record is None:
            record=next(({'round':e['round'],'multiplier':e['multiplier']}
                         for e in self.entries() if e.get('multiplier',0)),None)
        if record is None:return None
        return dict(record,rounds_ago=max(1,record.get(
            'rounds_ago',self.data['Total']-record['round']+1)))

    def entries(self):
        return sorted(self.data['Record2'].values(), key=lambda e: e['round'], reverse=True)

    def add(self, result):
        number = self.data['Total'] + 1
        entry = {'round': number, 'outcomes': list(result.outcomes),
                 'colors': [GRID_COLORS[i] for i in result.outcomes],
                 'bets': [str(v) for v in result.bets], 'returned': str(result.returned),
                 'net': str(result.net), 'multiplier': result.bonus_multiplier,
                 'bonus_values':list(result.bonus_values), 'bonus_outcomes':list(result.bonus_outcomes)}
        recent = ([entry] + self.entries())[:1000]
        previous=self.latest_double()
        latest=({'round':number,'multiplier':result.bonus_multiplier,'rounds_ago':1}
                if result.bonus_multiplier else
                dict(previous,rounds_ago=previous['rounds_ago']+1) if previous else None)
        data = {'Total': number, 'Record2': {str(e['round']): e for e in recent}, 'LatestDouble':latest}
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(str(self.path), 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
        self.data = data

    def recent(self):
        def display_colors(entry):
            colors=entry['colors']
            priority=({'blue':0,'red':1,'white':2} if colors.count('blue')>=2
                      else {'red':0,'blue':1,'white':2})
            return tuple(COLOR_NAMES[c] for c in sorted(colors,key=priority.__getitem__))
        return [display_colors(e) for e in self.entries()[:15]]

    def percentages(self, limit=50):
        entries = self.entries()[:limit]
        colors = [color for entry in entries for color in entry['colors']]
        total = len(colors)
        return [100 * colors.count(c) / total if total else 0
                for c in ('red', 'blue', 'white')], len(entries)


HISTORY_STYLES = {'红': (COLOR_HEX['red'], 'white'),
                  '白': ('white', 'black'), '蓝': (COLOR_HEX['blue'], 'white')}


class RedPacketRainGame:
    WINDOW_WIDTH, WINDOW_HEIGHT = 1150, 750

    def __init__(self, root, initial_balance, username, *, demo=False, store=None,
                 manage_window=True):
        self.root, self.username = root, username
        self.balance = money(initial_balance)
        self.store = store if store is not None else AccountStore(username, demo)
        self.demo = demo
        self.bet_per_draw = Decimal("0.00")
        self.selected = None
        self.bets = [Decimal("0.00") for _ in BET_LABELS]
        self.high_bet_mode=False
        self.selected_chip = 0
        self._bet_actions = []
        self._chip_moves = []
        self._chip_job = None
        self.game_active = False
        self._closed = False
        self._job = None
        self._result = None
        self._last_result = None
        self._bonus_active=False
        self._bonus_done=False
        self._bonus_revealed=False
        self._bonus_phase=None
        self._bonus_frames=[]
        self._bonus_pose=None
        self._bonus_model=None
        self._bonus_deck=()
        self._bonus_values={}
        self._bonus_opened={}
        self._bonus_counts={}
        self._bonus_deadline=0
        self._bonus_next_auto=0
        self._bonus_hit=''
        self._packet_opening=None 
        self.stats_limit=50
        self._frames = []
        self._poses = []
        self._rng = random.SystemRandom()
        self.round_count = 0
        self.session_net = Decimal("0.00")
        self.last_win = Decimal("0.00")
        self._new_ticket = True
        self._settled=False
        self._flash_job=None
        self._flash_step=0
        self._flash_active=False
        account_path=getattr(self.store,"path",None)
        log_path=Path(account_path).parents[2]/"A_Logs/Json/Pula_Puti.json" if account_path and not demo else None
        self.history_store=DropBallHistory(log_path)
        self.history=self.history_store.recent()
        self._return_moves=[]
        self._return_started=None
        self._last_bets = None
        self._card_sources = {}
        self._golden_sources = {}
        self._card_cache = {}
        self._bet_image_cache = {}
        self._bet_draw_refs = []
        self._card_draw_refs = []
        self.asset_message = ""
        self.root.configure(bg=Theme.APP_BG)
        self._close_command = None
        if manage_window:
            if isinstance(root, (tk.Tk, tk.Toplevel)):
                root.title("红白落球")
                root.geometry("1150x750")
                root.minsize(1150, 750)
                root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self._window=root.winfo_toplevel()
            self._previous_resizable=self._window.resizable()
            self._window.resizable(False,False)
            self._embedded=not isinstance(root,(tk.Tk,tk.Toplevel))
            self._previous_close_protocol=self._window.protocol("WM_DELETE_WINDOW") if self._embedded else ""
            self._close_command=self._window.register(self.on_closing)
            self._window.tk.call("wm","protocol",self._window._w,"WM_DELETE_WINDOW",self._close_command)
        root.bind("<Destroy>", self._on_destroy, add="+")
        self.create_widgets()
        self.update_display()

    def create_widgets(self):
        self.balance_var=tk.StringVar(master=self.root)
        self.bet_var=tk.StringVar(master=self.root)
        self.last_win_var=tk.StringVar(master=self.root,value='上局获胜: $0')
        self.stage_var=tk.StringVar(master=self.root,value='等待下注')
        self.info_var=tk.StringVar(master=self.root,value='请下注')
        self.result_var=tk.StringVar(master=self.root,value='')
        main=tk.Frame(self.root,bg=Theme.APP_BG);main.pack(fill='both',expand=True,padx=10,pady=10)
        right=tk.Frame(main,bg=Theme.APP_BG,width=400)
        right.pack(side='right',fill='y');right.pack_propagate(False)
        board=tk.Frame(main,bg=Theme.APP_BG,highlightbackground='#D8B46A',highlightthickness=2)
        board.pack(side='left',fill='both',expand=True,padx=(0,10))
        self.canvas=tk.Canvas(board,bg='#263d38',highlightthickness=0);self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda e:self.draw_scene())
        self.canvas.bind('<Button-1>',self._bonus_click)
        self._packet_flaps={name:[SplitFlapDigit(self.canvas) for _ in range(len(str(max(BONUS_TIERS[name][0]))))]
                            for name in BONUS_ORDER}
        self._create_latest_double_panel(board)
        section_y=0
        def section(height,title=None,padding=2):
            nonlocal section_y
            card=tk.Frame(right,bg=Theme.PANEL,bd=1,relief=tk.SOLID)
            card.place(x=0,y=section_y,width=400,height=height)
            section_y+=height+2
            header_height=28 if title else 0
            if title:
                tk.Label(card,text=title,font=('Arial',13,'bold'),bg='#D8B46A',fg='#2A1B08').place(x=0,y=0,relwidth=1,height=28)
            body=tk.Frame(card,bg=Theme.PANEL)
            body.place(x=10,y=header_height+padding,width=376,height=height-header_height-2*padding-2)
            return body
        info=section(40,padding=4)
        tk.Label(info,textvariable=self.balance_var,font=('Arial',16,'bold'),bg=Theme.PANEL,fg='black').pack(side='left')
        tk.Label(info,textvariable=self.stage_var,font=('Arial',14,'bold'),bg=Theme.PANEL,fg='#A88100').pack(side='right')
        limits=section(96,'下注上限',padding=8)
        self.limit_value_labels=[]
        for col,name in enumerate(('下注下限','单区上限','总下注上限')):
            limits.columnconfigure(col,weight=1)
            tk.Label(limits,text=name,bg=Theme.PANEL,fg='#2A1B08',font=('Arial',11,'bold'),bd=1,relief=tk.SOLID).grid(row=0,column=col,sticky='nsew')
            value=tk.Label(limits,bg=Theme.PANEL,fg='#A88100',font=('Arial',12,'bold'),bd=1,relief=tk.SOLID)
            value.grid(row=1,column=col,sticky='nsew');self.limit_value_labels.append(value)
        def bind_limit(widget):
            widget.bind('<Button-1>',self.toggle_high_bet_limits)
            for child in widget.winfo_children():bind_limit(child)
        bind_limit(limits.master);self._update_limits_display()
        combined=section(242,'筹码与下注')
        self.bet_canvas=tk.Canvas(combined,width=376,height=208,bg=Theme.PANEL,highlightthickness=0,cursor='hand2',takefocus=1)
        self.bet_canvas.pack(fill='both',expand=True)
        self.bet_canvas.bind('<Button-1>',self._bet_click)
        self.bet_canvas.bind('<Button-3>',self._bet_clear_click)
        self.bet_canvas.bind('<Key>',self._bet_key);self._bind_start_keys()
        action=section(84,'操作')
        tk.Label(action,textvariable=self.info_var,font=('Arial',10,'bold'),bg=Theme.PANEL,fg='#2A1B08').place(x=0,y=0,width=376,height=20)
        buttons=tk.Frame(action,bg=Theme.PANEL);buttons.place(x=0,y=20,width=376,height=28)
        self.reset_bet_button=ModernButton(buttons,text='清除下注',command=self.reset_bet,background='#C94A4A',foreground='white')
        self.repeat_button=ModernButton(buttons,text='重复上局下注',command=self.repeat_last_bet,background='#4A90E2',foreground='white')
        self.start_button=ModernButton(buttons,text='开始游戏',command=self.start_game,background='#D8B46A',foreground='#2A1B08',bold=True)
        for i,button in enumerate((self.reset_bet_button,self.repeat_button,self.start_button)):
            button.place(x=i*125,y=0,width=123,height=28)
        history=section(109,'最近15局')
        self.history_canvas=tk.Canvas(history,width=376,height=75,bg='white',highlightthickness=0)
        self.history_canvas.pack(fill='both',expand=True);self.draw_history()
        stats=section(70)
        stats.place_configure(y=28,height=40)
        self.stats_button=tk.Button(stats.master,text='50局落球颜色占比',command=self.change_stats_limit,
                                    font=('Arial',13,'bold'),bg='#D8B46A',activebackground='#D8B46A',fg='#2A1B08',
                                    relief=tk.FLAT,bd=0,highlightthickness=0,cursor='hand2')
        self.stats_button.place(x=0,y=0,relwidth=1,height=28)
        self.stats_canvas=tk.Canvas(stats,width=376,height=40,bg='white',highlightthickness=0)
        self.stats_canvas.pack(fill='both',expand=True);self.draw_statistics()
        bottom=section(66,padding=4)
        tk.Label(bottom,textvariable=self.bet_var,font=('Arial',12),bg=Theme.PANEL,fg='black').pack(anchor='w')
        row_last=tk.Frame(bottom,bg=Theme.PANEL);row_last.pack(fill='x',pady=2)
        tk.Label(row_last,textvariable=self.last_win_var,font=('Arial',12),bg=Theme.PANEL,fg='black').pack(side='left')
        tk.Button(row_last,text='ℹ',command=self.show_game_instructions,bg='#4B8BBE',fg='white',font=('Arial',12),width=2,relief=tk.FLAT).pack(side='right')

    def _create_latest_double_panel(self, board):
        self.latest_double_canvas=tk.Canvas(board,width=210,height=144,bg=COLOR_HEX['blue'],
                                           highlightbackground='#D8B46A',highlightthickness=1)
        self.latest_double_canvas.place(relx=1,x=-10,y=10,anchor='ne')
        self._double_flaps={key:[SplitFlapDigit(self.latest_double_canvas) for _ in range(size)]
                            for key,size in (('rounds_ago',4),('multiplier',4))}
        self._draw_latest_double(animate=False)

    def _draw_latest_double(self, animate=True):
        if not hasattr(self,'latest_double_canvas'):return
        c=self.latest_double_canvas;c.delete('all')
        c.create_text(105,16,text='最近双蓝',fill='white',font=(Theme.FONT_CJK,13,'bold'))
        in_bonus=self._bonus_active
        record=({'rounds_ago':0,'multiplier':None} if in_bonus
                else self.history_store.latest_double())
        for y,key,unit,size in ((40,'rounds_ago','局前',4),(85,'multiplier','X',4)):
            value=record[key] if record else None
            digits='-'*size if value is None else f'{min(10**size-1,max(0,int(value))):0{size}d}'
            for i,(cell,digit) in enumerate(zip(self._double_flaps[key],digits)):
                cell.place(x=10+(5-size+i)*29,y=y,width=27,height=34)
                if in_bonus and getattr(self,'_bonus_panel_reset',False) and key=='rounds_ago':
                    cell.set('-',animate=False)
                cell.set(digit,animate=animate,
                         delay=(i+(4 if key=='multiplier' else 0))*300 if in_bonus else i*65,
                         fast=in_bonus)
            c.create_text(10+5*29+3,y+17,text=unit,anchor='w',fill='white',font=(Theme.FONT_CJK,11,'bold'))
        if in_bonus:self._bonus_panel_reset=False
        if record and record['rounds_ago']>9999:
            c.create_text(105,133,text=f"实际 {record['rounds_ago']} 局前",fill='white',font=(Theme.FONT_CJK,8))

    def _bind_start_keys(self):
        self._key_window=self.root.winfo_toplevel()
        self._start_key_bindings=[]
        for sequence in ("<Return>", "<KP_Enter>"):
            command=self._key_window.bind(sequence, self._on_start_key, add="+")
            self._start_key_bindings.append((sequence, command))

    def _on_start_key(self, event):
        if self._closed or not self.root.winfo_ismapped():
            return
        widget=event.widget
        if widget is not self._key_window:
            while widget is not None and widget is not self.root:
                if isinstance(widget, (tk.Tk, tk.Toplevel)):
                    return
                widget=getattr(widget, "master", None)
            if widget is None:
                return
        try:
            if self.root.grab_current() is not None:
                return
            if str(self.start_button.cget("state"))!=tk.DISABLED:
                self.start_button.invoke()
        except tk.TclError:
            return
        return "break"

    def _unbind_start_keys(self):
        for sequence, command in getattr(self, "_start_key_bindings", []):
            try:
                self._key_window.unbind(sequence, command)
            except tk.TclError:
                pass
        self._start_key_bindings=[]

    def show_game_instructions(self):
        window=tk.Toplevel(self.root)
        window.title('红白落球 · 游戏规则')
        window.geometry('650x510')
        window.configure(bg='#173c32')
        cv=tk.Canvas(window,bg='#173c32',highlightthickness=0)
        cv.pack(fill='both',expand=True)
        cv.create_text(325,35,text='红白落球  ·  游戏规则',fill='#f2e6c9',font=(Theme.FONT_CJK,21,'bold'))
        for i,color in enumerate(('#d93c3c','#f7f5ef','#163d85')):
            cv.create_oval(140+i*62,75,178+i*62,113,fill=color,outline='#d8b46a',width=2)
        cv.create_text(455,95,text='三球落在 18 × 8 格子',fill='white',font=(Theme.FONT_CJK,14))
        lines=[
            '双红 / 双白  ≥2同色：2X       三红 / 三白  3同色：9X',
            '任意蓝  ≥1蓝：6X             红白蓝  各1颗：12X',
            '至少2颗蓝球进入红包游戏；2蓝有18封，3蓝有12封。',
            '点选红包，收集同一档至目标张数即可领取该档倍率。',
            '两蓝：18封，Mini 3 / Maxi 3 / Minor 3 / Major 4 / Grand 5。',
            '三蓝：12封，Minor 3 / Major 4 / Grand 5。',
            '每档倍率在当局随机翻出；双蓝下注按获奖倍率结算。',
            '停球后有300秒选择；到时系统每5秒自动开启一封。',
            '左键下注 / 右键清除；数字1–7选择下注区。',
        ]
        for i,line in enumerate(lines):
            y=153+i*36
            cv.create_rectangle(34,y-15,616,y+17,fill='#245344' if i%2==0 else '#21483d',outline='#537969')
            cv.create_text(48,y,text=line,anchor='w',fill='#f6eedc',font=(Theme.FONT_CJK,12))
        tk.Button(window,text='关闭',command=window.destroy,bg='#d8b46a',font=(Theme.FONT_CJK,12,'bold')).place(x=276,y=475,width=100,height=28)

    def update_display(self):
        self._draw_latest_double()
        self.bet_per_draw=sum(self.bets,Decimal(0))
        self.balance_var.set(f"余额: ${self.balance:,.2f}")
        self.stage_var.set(("红包游戏" if self._bonus_active else "落球中") if self.game_active else ("已结算" if self._settled else "下注中"))
        display_stake=self.bet_per_draw if self._new_ticket or self._last_result is None else self._last_result.stake
        self.bet_var.set(f"本局下注: ${int(display_stake):,}")
        self.last_win_var.set(f"上局获胜: ${int(self.last_win):,}")
        state=tk.DISABLED if self.game_active or self._settled else tk.NORMAL
        self.reset_bet_button.configure(state=state)
        ready=not self.game_active and not self._settled and not self._chip_moves and self.valid_bets(self.bets) and self.bet_per_draw<=self.balance
        self.start_button.configure(state=tk.NORMAL if ready else tk.DISABLED,text="开始游戏")
        self.repeat_button.configure(state=tk.NORMAL if not self.game_active and not self._settled and self._last_bets and self.valid_bets(self._last_bets) and sum(self._last_bets)<=self.balance else tk.DISABLED)
        self.draw_betting()

    @staticmethod
    def bet_rect(index):
        if index == 6:return 2, 170, 368, 34
        row=index//2
        return 2 + (index % 2)*186, 57 + row*36 + (5 if row>=2 else 0), 182, 34

    def draw_betting(self):
        c=self.bet_canvas;c.delete('all')
        def chip(x,y,amount,config=None,r=14):
            config=config or self.chip_for_amount(amount)
            c.create_oval(x-r,y-r,x+r,y+r,fill=config[2],outline='#d4af37',width=2)
            c.create_text(x,y,text=chip_amount_text(amount),fill=config[3],font=('Arial',9,'bold'))
        for i,(label,amount,color,fg) in enumerate(self.chip_configs):
            x=31+i*62
            c.create_oval(x-23,4,x+23,50,fill=color,outline='#d4af37' if i==self.selected_chip else 'black',width=3 if i==self.selected_chip else 1)
            c.create_text(x,27,text=label,fill=fg,font=('Arial',10,'bold'))
        patterns=(('red',)*2,('white',)*2,('red',)*3,('white',)*3,('blue',),('blue',)*2,('blue','red','white'))
        odds=('1:1','1:1','8:1','8:1','5:1','三球合计倍率','11:1')
        for i,colors in enumerate(patterns):
            x,y,w,h=self.bet_rect(i)
            won=bool(self._last_result and payout_multipliers(self._last_result.outcomes,self._last_result.bonus_multiplier)[i])
            gold=self._settled and won and (self._flash_step%2 or not self._flash_active)
            lost=self._settled and self._last_result is not None and not won
            c.create_rectangle(x,y,x+w,y+h,fill='#747474' if lost else '#E6B949' if gold else '#FFFFFF',outline='#8E805F',width=1)
            for j,color in enumerate(colors):
                cx=x+14+j*21
                c.create_oval(cx-8,y+4,cx+8,y+20,fill=({'red':'#722020','white':'#858585','blue':'#0C2047'}[color] if lost else COLOR_HEX[color]),outline='#444444')
            c.create_text(x+7,y+27,text=odds[i],anchor='w',fill='#E5E5E5' if lost else '#252A2E',font=(Theme.FONT_CJK,9))
            pending=sum((move[2] for move in self._chip_moves if move[1]==i),Decimal(0))
            visible=Decimal(0) if self._return_started is not None else max(Decimal(0),self.bets[i]-pending)
            if self._settled and not won:visible=Decimal(0)
            if visible:
                shown=self._area_return(i) if self._settled and won and (self._flash_step%2 or not self._flash_active) else visible
                chip(x+w-23,y+h/2,shown)
        now=time.monotonic()
        for started,index,amount,chip_index in self._chip_moves:
            ease=1-(1-min(1,(now-started)/.32))**3
            x,y,w,h=self.bet_rect(index);sx,sy=31+chip_index*62,27
            chip(sx+(x+w-23-sx)*ease,sy+(y+h/2-sy)*ease,amount)
        if self._return_started is not None:
            ease=1-(1-min(1,(now-self._return_started)/.4))**3
            for index,amount,chip_index in self._return_moves:
                x,y,w,h=self.bet_rect(index);sx,sy=x+w-23,y+h/2
                chip(sx+(31+chip_index*62-sx)*ease,sy+(27-sy)*ease,amount)

    def _bet_click(self,event):
        if self.game_active or self._closed or self._settled:return
        self.bet_canvas.focus_set()
        for i in range(len(self.chip_configs)):
            if math.hypot(event.x-(31+i*62),event.y-27)<=25:
                self.selected_chip=i;self.draw_betting();return
        for i in range(len(BET_LABELS)):
            x,y,w,h=self.bet_rect(i)
            if x<=event.x<=x+w and y<=event.y<=y+h:self.place_bet(i);return

    def _bet_clear_click(self,event):
        if self.game_active or self._closed or self._settled:return
        for i in range(len(BET_LABELS)):
            x,y,w,h=self.bet_rect(i)
            if x<=event.x<=x+w and y<=event.y<=y+h:
                self.bets[i]=Decimal(0)
                self._bet_actions=[a for a in self._bet_actions if a[0]!=i]
                self._chip_moves=[a for a in self._chip_moves if a[1]!=i]
                self.update_display();return

    def repeat_last_bet(self):
        if self.game_active or self._closed or self._settled or not self._last_bets:return
        if not self.valid_bets(self._last_bets):return
        if sum(self._last_bets)>self.balance:
            self.info_var.set("余额不足");return
        self._new_ticket=True
        self.bets=list(self._last_bets);self._chip_moves.clear()
        self._bet_actions=[(i,v) for i,v in enumerate(self.bets) if v]
        now=time.monotonic()
        self._chip_moves=[(now,i,v,self.chip_configs.index(self.chip_for_amount(v))) for i,v in self._bet_actions]
        self.info_var.set("请下注")
        self.update_display();self.draw_scene()
        if self._chip_job is None:self._animate_chips()

    def _bet_key(self,event):
        if event.char in "1234567" and event.char:self.place_bet(int(event.char)-1)
        elif event.keysym in ("Left","Right") and not self.game_active:
            self.selected_chip=(self.selected_chip+(1 if event.keysym=="Right" else -1))%len(self.chip_configs);self.draw_betting()

    def place_bet(self,index):
        if self.game_active or self._closed or self._settled or index not in range(len(BET_LABELS)):return
        amount=money(self.chip_configs[self.selected_chip][1])
        proposed=list(self.bets);proposed[index]+=amount
        if not self.valid_bets(proposed):
            self.info_var.set("请下注");return
        if sum(self.bets,Decimal(0))+amount>self.balance:
            self.info_var.set("余额不足");return
        self._new_ticket=True
        self.selected=index;self.bets[index]+=amount;self._bet_actions.append((index,amount))
        self._chip_moves.append((time.monotonic(),index,amount,self.selected_chip))
        self.info_var.set("请下注")
        self.update_display();self.draw_scene()
        if self._chip_job is None:self._animate_chips()

    def _animate_chips(self):
        self._chip_job=None
        if self._closed:return
        now=time.monotonic();self._chip_moves=[m for m in self._chip_moves if now-m[0]<.32]
        self.update_display()
        if self._chip_moves:self._chip_job=self.root.after(16,self._animate_chips)

    def reset_bet(self):
        if self.game_active or self._closed or self._settled:return
        self._new_ticket=True
        self._chip_moves.clear();self._bet_actions.clear();self.bets=[Decimal(0) for _ in BET_LABELS]
        self.update_display();self.draw_scene()

    def start_game(self):
        if self.game_active or self._closed or self._settled:
            return
        if self._chip_moves:return
        self.bet_per_draw=sum(self.bets,Decimal(0))
        if not self.valid_bets(self.bets) or self.bet_per_draw>self.balance:
            self.info_var.set("余额不足" if self.bet_per_draw>self.balance else "请下注")
            return
        try:
            frames, outcomes = BallPhysics(self._rng).simulate()
            blue_count = sum(GRID_COLORS[i] == 'blue' for i in outcomes)
            result = settle_table(self.balance, self.bets, outcomes)
            deck, values = make_bonus_deck(self._rng, 12 if blue_count == 3 else 18) if blue_count >= 2 else ((), {})
        except (RuntimeError, ValueError) as exc:
            self.info_var.set(str(exc))
            return
        try:
            if result.stake:self.store.save(self.balance-result.stake)
        except Exception as exc:
            messagebox.showerror("无法保存账户", f"本轮未开始，当前余额未扣除。\n{exc}", parent=self.root)
            return
        self._bonus_active=False;self._bonus_done=False;self._bonus_revealed=False
        self._bonus_deck=deck;self._bonus_values=values
        self._bonus_opened={};self._bonus_counts={name:0 for name in BONUS_TIERS}
        self._bonus_hit='';self._bonus_phase=None;self._packet_opening=None
        self._new_ticket=False
        if sum(self.bets)>0:self._last_bets=tuple(self.bets)
        self._result = result
        self._last_result = None
        self.game_active = True
        self.balance -= result.stake
        self._frames = frames
        self._started_at = time.monotonic()
        self.result_var.set("三颗球落下中…\n等待全部停稳")
        self.info_var.set("游戏进行中，请稍等")
        self.update_display()
        self._animate()

    def _animate(self):
        self._job = None
        if not self.game_active or self._closed:
            return
        elapsed = time.monotonic() - self._started_at
        frame = int(elapsed / BallPhysics.FRAME_DT)
        if frame >= len(self._frames)-1:
            self._finish_round()
            return
        alpha=elapsed/BallPhysics.FRAME_DT-frame
        self._poses=[]
        for a,b in zip(self._frames[frame],self._frames[frame+1]):
            if a is None or b is None or a[3]!=b[3]:self._poses.append(a)
            else:self._poses.append(tuple(a[i]+(b[i]-a[i])*alpha for i in range(3))+(a[3],))
        self.info_var.set("游戏进行中，请稍等")
        self.draw_scene()
        self._job = self.root.after(16, self._animate)

    def _begin_bonus(self):
        self._job=None
        if self._closed or not self.game_active:return
        self._bonus_active=True;self._bonus_phase='choose'
        self._bonus_panel_reset=True
        self._bonus_deadline=None
        for name,cards in self._packet_flaps.items():
            inactive=len(self._bonus_deck)==12 and name in ('Mini','Maxi')
            digits=f'{self._bonus_values[name]:0{len(cards)}d}'
            for i,card in enumerate(cards):
                card.set('-',animate=False)
                if inactive:card.place_forget()
                else:card.set(digits[i],delay=80+i*45)
        self._bonus_next_auto=None
        self._poses=[]
        self.info_var.set('选择红包，收集同档奖励')
        self.update_display();self.draw_scene()
        self._bonus_tick()

    def _open_packet(self, index):
        if (not self._bonus_active or self._bonus_hit or self._packet_opening
                or index in self._bonus_opened or not 0<=index<len(self._bonus_deck)):
            return
        self._packet_opening=(index,time.monotonic())
        self.draw_scene()

    def _complete_packet(self):
        index,_=self._packet_opening
        self._packet_opening=None
        name=self._bonus_deck[index]
        self._bonus_opened[index]=name
        self._bonus_counts[name]+=1
        if self._bonus_counts[name]>=BONUS_TIERS[name][2]:
            self._bonus_hit=name
            self._bonus_phase='result'
            r=self._result
            mult=self._bonus_values[name]
            self._result=settle_table(self.balance+r.stake,r.bets,r.outcomes,
                                      bonus_multiplier=mult,
                                      bonus_values=tuple(self._bonus_values[n] for n in BONUS_ORDER),
                                      bonus_outcomes=tuple(self._bonus_opened.keys()))
            self._job=self.root.after(2300,self._end_bonus)
        self.draw_scene()

    def _bonus_click(self,event):
        if (not self._bonus_active or self._bonus_hit or self._packet_opening
                or self._bonus_deadline is None or time.monotonic()>=self._bonus_deadline):return
        s,ox,oy=self._viewport()
        x,y=(event.x-ox)/s,(event.y-oy)/s
        count=len(self._bonus_deck)
        for i in range(count):
            col,row=i%6,i//6
            if 72+col*104<=x<=158+col*104 and 330+row*94<=y<=410+row*94:
                self._open_packet(i);return

    def _bonus_tick(self):
        self._job=None
        if self._closed or not self._bonus_active or self._bonus_hit:return
        now=time.monotonic()
        if self._bonus_deadline is None and all(
                not card.is_animating() for cards in self._packet_flaps.values()
                for card in cards):
            self._bonus_deadline=now+300
            self._bonus_next_auto=self._bonus_deadline+5
        if self._packet_opening and now-self._packet_opening[1]>=.76:
            self._complete_packet()
            if self._bonus_hit:return
        if self._bonus_next_auto is not None and now>=self._bonus_next_auto and not self._packet_opening:
            closed=[i for i in range(len(self._bonus_deck)) if i not in self._bonus_opened]
            if closed:self._open_packet(self._rng.choice(closed))
            self._bonus_next_auto+=5
        if not self._bonus_hit:
            self.draw_scene()
            self._job=self.root.after(100,self._bonus_tick)

    def _end_bonus(self):
        self._job=None
        if self._closed or not self.game_active:return
        self._bonus_done=True;self._bonus_active=False;self._bonus_phase=None
        self._finish_round()

    def _finish_round(self,force=False):
        if not self.game_active or self._result is None:return
        if self._bonus_deck and not self._bonus_done and not force:
            if self._bonus_phase is None:
                self._bonus_phase='trigger'
                self._poses=self._frames[-1]
                self.info_var.set('蓝球奖励，即将进入红包游戏')
                self.draw_scene()
                self._job=self.root.after(1000,self._begin_bonus)
            return
        self._bonus_active=False;self._bonus_phase=None
        for cards in self._packet_flaps.values():
            for card in cards:card.place_forget()
        self._cancel_jobs()
        r = self._result
        if r.final_balance != self.balance:
            try:self.store.save(r.final_balance)
            except Exception as exc:
                messagebox.showerror('无法保存账户',str(exc),parent=self.root)
                return
        self.balance = r.final_balance
        self.session_net += r.net
        self.last_win=r.returned if not r.invalid else Decimal(0)
        self.round_count += 1
        self._last_result = r
        self._result = None
        self.game_active = False
        self._poses = self._frames[-1]
        outcome_text=" / ".join(COLOR_NAMES[GRID_COLORS[i]] for i in r.outcomes)
        if r.invalid:
            status="无效";tag="void"
            self.result_var.set(f"本局无效 · 全额退回 {r.stake:,.2f}")
            self.info_var.set("请下注")
        else:
            status="已结算";tag="win" if r.net>=0 else "loss"
            self.result_var.set(f"{outcome_text} · 净赢 {r.net:+,.2f} · 返还 {r.returned:,.2f}" + (f" · 双蓝 {r.bonus_multiplier}X" if r.bonus_multiplier else ""))
            self.info_var.set("你赢啦" if r.net>0 else "下局加油")
        try:self.history_store.add(r)
        except (OSError,ValueError) as exc:
            messagebox.showerror("无法保存游戏记录",f"余额已结算，但历史记录保存失败。\n{exc}",parent=self.root)
        self.history=self.history_store.recent()
        self.draw_statistics()
        self._latest_triple_preview=None
        self._triple_reveal_requested=False
        self._settled=True
        self.draw_history()
        self._flash_step=0
        self._flash_active=not r.invalid
        self.update_display();self.draw_scene()
        if self._flash_active:self._flash_job=self.root.after(750,self._advance_flash)
        else:self._flash_job=self.root.after(1500,self._begin_chip_return)

    @property
    def chip_configs(self):
        return HIGH_CHIP_CONFIGS if self.high_bet_mode else CHIP_CONFIGS

    @property
    def bet_limits(self):
        return (100,50000,250000) if self.high_bet_mode else (10,10000,50000)

    def valid_bets(self,bets):
        minimum,area_max,total_max=self.bet_limits
        return len(bets)==len(BET_LABELS) and all(v==0 or minimum<=v<=area_max for v in bets) and (sum(bets)==0 or minimum<=sum(bets)<=total_max)

    def _update_limits_display(self):
        for label,value in zip(self.limit_value_labels,self.bet_limits):label.configure(text=f"${value:,}")

    def toggle_high_bet_limits(self,event=None):
        if self.game_active or self._settled or self._closed:return
        if not self.high_bet_mode:
            password=simpledialog.askstring("高额下注","请输入密码：",parent=self.root)
            if password is None:return
            if password.strip()!=time.strftime("%H%M"):
                messagebox.showerror("错误","密码错误",parent=self.root);return
        self.high_bet_mode=not self.high_bet_mode
        self.selected_chip=0
        self.reset_bet()
        self._update_limits_display()

    def draw_history(self):
        c=self.history_canvas;c.delete("all")
        c.create_text(18,36,text="最\n新",font=("Arial",10,"bold"),fill="#2A1B08")
        for row in range(3):
            for col in range(15):
                x=37+col*22
                label = self.history[col][row] if col < len(self.history) else ''
                background, foreground = HISTORY_STYLES.get(label, ('white', 'black'))
                c.create_rectangle(x,row*24,x+22,row*24+24,fill=background,outline='black',width=2)
                if label:
                    c.create_text(x+11,row*24+12,text=label,fill=foreground,font=('Arial',9,'bold'))
        c.create_line(37,1,37,73,fill="black",width=2)
        c.create_rectangle(1,1,368,73,outline="black",width=2)

    def _advance_flash(self):
        self._flash_job=None
        if self._closed:return
        self._flash_step+=1
        if self._flash_step>=6:
            self._flash_active=False
            self._begin_chip_return()
            return
        self.draw_betting()
        self._flash_job=self.root.after(750,self._advance_flash)

    def change_stats_limit(self,event=None):
        choices=(50,100,250,500,1000)
        self.stats_limit=choices[(choices.index(self.stats_limit)+1)%len(choices)]
        self.stats_button.configure(text=f"{self.stats_limit}局落球颜色占比")
        self.draw_statistics()

    def chip_for_amount(self,amount):
        return max((c for c in self.chip_configs if money(c[1])<=amount),key=lambda c:money(c[1]),default=self.chip_configs[0])

    def _area_return(self,index):
        r=self._last_result
        if r is None:return Decimal(0)
        return r.bets[index]*payout_multipliers(r.outcomes,r.bonus_multiplier)[index]

    def draw_statistics(self):
        c=self.stats_canvas;c.delete('all')
        values,count=self.history_store.percentages(self.stats_limit)
        c.create_rectangle(139,0,233,17,fill=COLOR_HEX['blue'],outline='')
        c.create_text(186,8,text=f'蓝 {values[1]:.1f}%',fill='white',font=(Theme.FONT_CJK,10,'bold'))
        left,right,top,bottom=4,368,19,39
        c.create_rectangle(left,top,right,bottom,fill='#E3E3E3',outline='#777777')
        x=left
        for color,value in zip(('red','blue','white'),values):
            end=x+(right-left)*value/100
            if value>0:
                c.create_rectangle(x,top,end,bottom,fill=COLOR_HEX[color],outline='')
                if color!='blue':
                    label=f'{value:.1f}%'
                    size=min(12,max(1,int((end-x-2)/(len(label)*.7))))
                    c.create_text((x+end)/2,(top+bottom)/2,text=label,fill='white' if color=='red' else 'black',
                                  font=('Arial',-size,'bold'))
            x=end
        c.create_rectangle(left,top,right,bottom,outline='#777777')
        if not count:c.create_text(186,29,text='暂无记录',fill='#596169',font=(Theme.FONT_CJK,10))

    def _begin_chip_return(self):
        self._flash_job=None
        if self._closed:return
        self._return_started=time.monotonic()
        self._return_moves=[]
        for i,bet in enumerate(self.bets):
            amount=self._area_return(i) if self._last_result else Decimal(0)
            if amount:
                chip_index=self.chip_configs.index(self.chip_for_amount(amount))
                self._return_moves.append((i,amount,chip_index))
        self._animate_chip_return()

    def _animate_chip_return(self):
        self._flash_job=None
        if self._closed:return
        if time.monotonic()-self._return_started>=.4:
            self._return_moves=[];self._return_started=None
            self.new_round()
            return
        self.draw_betting()
        self._flash_job=self.root.after(16,self._animate_chip_return)

    def new_round(self):
        if self.game_active or self._closed or self._flash_active:return
        self._settled=False;self._new_ticket=True;self._last_result=None
        self.bets=[Decimal(0) for _ in BET_LABELS];self._bet_actions.clear();self._chip_moves.clear()
        self._poses=[];self.info_var.set("请下注")
        self.update_display();self.draw_scene()

    def _cancel_jobs(self):
        if self._flash_job is not None:
            try:self.root.after_cancel(self._flash_job)
            except tk.TclError:pass
            self._flash_job=None
        if self._chip_job is not None:
            try:self.root.after_cancel(self._chip_job)
            except tk.TclError:pass
            self._chip_job=None
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def stop_game(self):
        self._finish_round(force=True)

    def _restore_window_close(self):
        window=getattr(self,"_window",None)
        command=getattr(self,"_close_command",None)
        if window is None or not command:return
        try:
            current=window.protocol("WM_DELETE_WINDOW")
            if self._embedded and current==command:
                window.tk.call("wm","protocol",window._w,"WM_DELETE_WINDOW",self._previous_close_protocol)
            if self._embedded:
                window.resizable(*self._previous_resizable)
                window.deletecommand(command)
        except tk.TclError:pass
        self._close_command=None

    def on_closing(self):
        if self._closed:
            return
        self._finish_round(force=True)
        self._cancel_jobs()
        self._closed = True
        self._unbind_start_keys()
        self._restore_window_close()
        finish = getattr(self.root, "finish", None)
        if callable(finish):
            finish(float(self.balance))
        elif callable(getattr(self,"_embedded_return",None)):
            self._embedded_return(float(self.balance))
        else:
            self.root.destroy()

    def _on_destroy(self, event):
        if event.widget is not self.root:
            return
        self._unbind_start_keys()
        self._restore_window_close()
        self._cancel_jobs()
        if self._result is not None:
            self.balance = self._result.final_balance
            self._result = None
        self.game_active = False
        self._closed = True

    @staticmethod
    def project(u, v, z=0):
        v = .5 + (v-.5) * BallPhysics.DEPTH / 2.0
        u = .5 + (u-.5) * BallPhysics.WIDTH / 3.0
        return 380 + (u-.5) * (504+36*v), 310+280*v-z

    def _viewport(self):
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        left,top,right,bottom=32,8,730,694
        scale=min(w/(right-left),h/(bottom-top))
        return scale,(w-(right-left)*scale)/2-left*scale,(h-(bottom-top)*scale)/2-top*scale

    def _draw_packet_scene(self):
        c=self.canvas;s,ox,oy=self._viewport()
        def xy(x,y):return ox+x*s,oy+y*s
        def rect(x1,y1,x2,y2,**kw):return c.create_rectangle(*xy(x1,y1),*xy(x2,y2),**kw)
        def label(x,y,t,size=12,color='white',**kw):
            c.create_text(*xy(x,y),text=t,fill=color,font=(Theme.FONT_CJK,max(7,round(size*s)),'bold'),**kw)
        rect(25,5,735,692,fill='#173c32',outline='#d8b46a',width=2)
        c.create_text(12,oy+12*s,text='红白落球',anchor='nw',fill='#f2e6c9',
                      font=(Theme.FONT_CJK,max(16,round(23*s)),'bold'))
        c.create_text(12,oy+46*s,text='Pula-Puti',anchor='nw',fill='#c5d1c8',
                      font=('Arial',max(10,round(13*s))))
        blue_count=sum(GRID_COLORS[i]=='blue' for i in self._result.outcomes)
        label(365,29,'三蓝奖励' if blue_count==3 else '双蓝奖励',19,color='#f6d887')
        for name,x,y,w in [('Major',90,76,190),('Grand',285,76,190),
                            ('Mini',90,198,190),('Maxi',285,198,190),('Minor',480,198,190)]:
            values,weights,need=BONUS_TIERS[name]
            count=self._bonus_counts[name]
            inactive=len(self._bonus_deck)==12 and name in ('Mini','Maxi')
            won=self._bonus_hit==name
            bg='#9b7629' if won else ('#676d70' if inactive else '#214e43')
            border='#ffe793' if won else ('#aeb5b6' if inactive else '#c9a35e')
            rect(x,y,x+w,y+111,fill=bg,outline=border,width=3 if won else 2)
            label(x+w/2,y+18,name.upper(),15,color='white' if inactive else '#f4d697')
            digit_count=len(str(max(values)))
            start=x+w/2-(digit_count*26+18)/2
            for j,card in enumerate(self._packet_flaps[name]):
                px=start+j*26
                if inactive:
                    card.place_forget()
                    rect(px,y+36,px+24,y+69,fill='#797f81',outline='#d7dddf')
                    label(px+12,y+52,'-',18,color='white')
                else:
                    card.place(x=ox+px*s,y=oy+(y+36)*s,
                               width=max(16,round(24*s)),height=max(22,round(34*s)))
            label(start+digit_count*26+7,y+53,'X',12,color='white')
            for j in range(need):
                cx,cy=xy(x+w/2-(need-1)*12+j*24,y+91)
                c.create_oval(cx-7*s,cy-7*s,cx+7*s,cy+7*s,
                              fill=('#7a8285' if inactive else '#45bdff' if j<count else '#172e4b'),
                              outline='#c2c8c9' if inactive else '#8ccde8')
        for i,name in enumerate(self._bonus_deck):
            col,row=i%6,i//6;x,y=72+col*104,330+row*94
            opened=i in self._bonus_opened
            opening=self._packet_opening and self._packet_opening[0]==i
            t=min(1,(time.monotonic()-self._packet_opening[1])/.76) if opening else 0
            if opening:
                # Lift the seal, open both flaps, then pull the prize card upward.
                lift=min(1,max(0,(t-.20)/.55))
                rect(x+5,y-42*lift,x+81,y+56-42*lift,
                     fill='#f1d9a0',outline='#f8c76c',width=2)
                if t>.45:label(x+43,y+32-42*lift,name.upper(),11,color='#7d2020')
                flap=min(1,t/.48)
                rect(x,y+24*flap,x+86,y+80,fill='#ba292e',outline='#f8c76c',width=2)
                rect(x,y-12*flap,x+86,y+24*(1-flap),fill='#d43a37',outline='#f8c76c',width=2)
                label(x+43,y+48,'福',max(9,round(25*(1-flap))),color='#f9d777')
            else:
                rect(x,y,x+86,y+80,fill='#f1d9a0' if opened else '#ba292e',outline='#f8c76c',width=2)
                if opened:
                    label(x+43,y+42,name.upper(),12,color='#7d2020')
                else:
                    rect(x+8,y+12,x+78,y+17,fill='#e9ac47',outline='')
                    label(x+43,y+47,'福',25,color='#f9d777')
        remain=max(0,self._bonus_deadline-time.monotonic()) if self._bonus_deadline is not None else 300
        label(375,635,'倒计时 300 秒' if remain else '自动开启：每 5 秒一封',13)
        rect(32,664,728,684,fill='white',outline='#e8c77a')
        used=1-remain/300
        if used>0:rect(32,664,32+696*used,684,fill='#d43c3c',outline='')
        # The centre label takes the contrasting colour of the area beneath it.
        label(380,674,f'{math.ceil(remain)} 秒' if remain else '0 秒',10,
              color='white' if used>=.5 else '#202020')

    def draw_scene(self):
        if self._closed:
            return
        c = self.canvas
        c.delete("all")
        if self._bonus_active:
            self._draw_packet_scene()
            return
        self._card_draw_refs = []
        s, ox, oy = self._viewport()

        def coords(points):
            return [
                n for x, y in points
                for n in (ox + x * s, oy + y * s)
            ]

        def poly(points, fill, outline="", width=1):
            c.create_polygon(
                *coords(points),
                fill=fill,
                outline=outline,
                width=max(1, width * s)
            )

        def oval(x1, y1, x2, y2, fill, outline="", width=1):
            c.create_oval(
                *coords([(x1, y1), (x2, y2)]),
                fill=fill,
                outline=outline,
                width=max(1, width * s)
            )

        def text(x, y, label, size=12, fill="#eee8d9", bold=False):
            c.create_text(
                ox + x * s,
                oy + y * s,
                text=label,
                fill=fill,
                font=(
                    Theme.FONT_CJK,
                    max(7, round(size * s)),
                    "bold" if bold else "normal"
                )
            )

        p = self.project

        def world(x, y, z=0):
            return p(
                x / BallPhysics.WIDTH,
                y / BallPhysics.DEPTH,
                z * BallPhysics.HEIGHT_SCALE
            )

        W, D = BallPhysics.WIDTH, BallPhysics.DEPTH
        rw, rh = BallPhysics.RAMP_WIDTH, BallPhysics.RAMP_HEIGHT
        fd = BallPhysics.FRONT_RAMP_DEPTH

        inner = [(0, 0, 0), (W, 0, 0), (W, D, 0), (0, D, 0)]
        outer = [
            (-rw, -rw, rh),
            (W + rw, -rw, rh),
            (W + rw, D + fd, rh),
            (-rw, D + fd, rh)
        ]

        oval(40, 578, 722, 666, "#1b2d29")

        nearleft, nearright = world(*outer[3]), world(*outer[2])
        poly(
            [
                nearleft,
                nearright,
                (nearright[0] - 8, nearright[1] + 28),
                (nearleft[0] + 8, nearleft[1] + 28)
            ],
            "#77553d", "#b99567", 2
        )

        for i in range(4):
            j = (i + 1) % 4
            poly(
                [
                    world(*outer[i]),
                    world(*outer[j]),
                    world(*inner[j]),
                    world(*inner[i])
                ],
                ("#879992", "#708b80", "#58796e", "#769487")[i],
                "#c4d1bd",
                2
            )
            raised_i = world(
                outer[i][0], outer[i][1],
                rh + BallPhysics.RIM_HEIGHT
            )
            raised_j = world(
                outer[j][0], outer[j][1],
                rh + BallPhysics.RIM_HEIGHT
            )
            poly(
                [world(*outer[i]), world(*outer[j]), raised_j, raised_i],
                "#adb6a6", "#e2e5d7", 1
            )

        poly(
            [world(*point) for point in inner],
            "#476352", "#90a48b", 2
        )

        for amount in (.33, .66):
            inset = rw * amount
            height = rh * amount
            ring = [
                (-inset, -inset, height),
                (W + inset, -inset, height),
                (W + inset, D + fd * amount, height),
                (-inset, D + fd * amount, height)
            ]
            for i in range(4):
                c.create_line(
                    *coords([
                        world(*ring[i]),
                        world(*ring[(i + 1) % 4])
                    ]),
                    fill="#a9b9a7",
                    width=max(1, s)
                )

        bonus=self._bonus_active and self._result is not None
        cols,rows=(3,2) if bonus else (GRID_COLS,GRID_ROWS)
        colors=('blue',)*6 if bonus else GRID_COLORS
        for index,color in enumerate(colors):
            col,row=index%cols,index//cols
            u0,u1=col/cols,(col+1)/cols
            v0,v1=row/rows,(row+1)/rows
            quad=[p(u0,v0),p(u1,v0),p(u1,v1),p(u0,v1)]
            poly(quad,COLOR_HEX[color],'white' if bonus else '#435347',2 if bonus else 1)
            if bonus:
                x,y=p((col+.5)/cols,(row+.5)/rows)
                text(x,y,f'{self._result.bonus_values[index]}X',20,'white',True)
        if bonus:
            r=self._result
            label=(' + '.join(str(r.bonus_values[i]) for i in r.bonus_outcomes)+f' = {r.bonus_multiplier}X'
                   if self._bonus_revealed else '双蓝奖励 · 总倍率 ---X')
            text(380,345,label,15,'white',True)
        rail_model=BonusBallPhysics if bonus else BallPhysics
        rails = [
            ((x / BallPhysics.WIDTH, 0), (x / BallPhysics.WIDTH, 1))
            for x in rail_model.RAIL_X
        ]
        rails += [
            ((0, y / BallPhysics.DEPTH), (1, y / BallPhysics.DEPTH))
            for y in rail_model.RAIL_Y
        ]
        height = (
            BallPhysics.RAIL_Z + BallPhysics.RAIL_RADIUS
        ) * BallPhysics.HEIGHT_SCALE

        for start, end in rails:
            a, b = p(*start), p(*end)
            at, bt = p(*start, height), p(*end, height)
            poly([a, b, bt, at], "white" if bonus else "#657269")
            c.create_line(
                *coords([at, bt]),
                fill="white" if bonus else "#b8b6a2",
                width=max(2, 5 * s)
            )
            c.create_line(
                *coords([
                    (at[0] - 1, at[1] - 1),
                    (bt[0] - 1, bt[1] - 1)
                ]),
                fill="white" if bonus else "#eee5c6",
                width=max(1, s)
            )

        poly(
            [
                world(*inner[3]), world(*inner[2]),
                world(*outer[2]), world(*outer[3])
            ],
            "#58796e", "#c4d1bd", 2
        )

        for x in (.5, 1.5, 2.5):
            c.create_line(
                *coords([world(x, D, 0), world(x, D + fd, rh)]),
                fill="#bbcfb6",
                width=max(1, s)
            )

        for y in (.5, 1.5):
            c.create_line(
                *coords([world(W, y, 0), world(W + rw, y, rh)]),
                fill="#bbcfb6",
                width=max(1, s)
            )

        if self.asset_message:
            text(
                380, 684,
                "牌图未齐：请检查 A_Tools/Card/Poker1（需要 Pillow）",
                9, "#edc67f"
            )

        if bonus:
            c.create_line(*coords([p(0,0),p(1,0),p(1,1),p(0,1),p(0,0)]),
                          fill='white',width=max(2,2*s))

        c.create_text(
            12, oy + 12 * s,
            text="红白落球",
            anchor="nw",
            fill="#F2E6C9",
            font=(Theme.FONT_CJK, max(16, round(23 * s)), "bold")
        )
        c.create_text(
            12, oy + 46 * s,
            text="Pula-Puti",
            anchor="nw",
            fill="#C5D1C8",
            font=("Arial", max(10, round(13 * s)))
        )

        poses = self._poses if self._poses else [
            (
                (BallPhysics.OUTLET[0] + (i - 1) * .16) / W,
                BallPhysics.OUTLET[1] / D,
                (BallPhysics.FUNNEL_TOP - BallPhysics.RADIUS)
                * BallPhysics.HEIGHT_SCALE,
                0
            )
            for i in range(3)
        ]

        def ball(pose):
            if pose is None:
                return
            u, v, z, phase = pose
            if phase == 2 and z < -55:
                return

            x, ground = p(u, v)
            radius = max(5, (504 + 36 * (.5+(v-.5)*D/2)) * BallPhysics.RADIUS / 3.0)

            if phase == 1:
                terrain_height = max(
                    0,
                    max(-u * W, (u - 1) * W, -v * D) * rh / rw,
                    (v - 1) * D * rh / fd
                )
                surface_y = ground - terrain_height * BallPhysics.HEIGHT_SCALE
                shadow = radius * (
                    1 + max(
                        0, z - terrain_height * BallPhysics.HEIGHT_SCALE
                    ) / 250
                )
                oval(
                    x - shadow, surface_y - 3,
                    x + shadow, surface_y + 4,
                    "#85917b"
                )

            y = ground - z - radius
            oval(
                x - radius, y - radius,
                x + radius, y + radius,
                "#E4B520", "#9C7612"
            )
            oval(
                x - radius + 1, y - radius + 1,
                x + radius - 2, y + radius - 3,
                "#FFDE35"
            )
            oval(x - 3, y - 5, x + 1, y - 2, "#FFF29B")

        for pose in sorted(
            (b for b in poses if b is not None and b[3] != 0),
            key=lambda b: b[1]
        ):
            ball(pose)

        cx, cy = BallPhysics.OUTLET
        top, bottom = BallPhysics.FUNNEL_TOP, BallPhysics.OUTLET_HEIGHT
        rt, rb = BallPhysics.FUNNEL_RADIUS, BallPhysics.NECK_RADIUS
        segments = 32

        for i in range(segments // 2, segments):
            a = i * math.tau / segments
            b = (i + 1) * math.tau / segments
            poly(
                [
                    world(cx + rt * math.cos(a), cy + rt * math.sin(a), top),
                    world(cx + rt * math.cos(b), cy + rt * math.sin(b), top),
                    world(cx + rb * math.cos(b), cy + rb * math.sin(b), bottom),
                    world(cx + rb * math.cos(a), cy + rb * math.sin(a), bottom)
                ],
                ("#6e8d83", "#91a99d", "#b7c9bb", "#829e91")[i % 4]
            )

        for pose in sorted(
            (b for b in poses if b is not None and b[3] == 0),
            key=lambda b: b[1]
        ):
            ball(pose)

        for i in (0, 8, 16):
            a = i * math.tau / segments
            c.create_line(
                *coords([
                    world(cx + rt * math.cos(a), cy + rt * math.sin(a), top),
                    world(cx + rb * math.cos(a), cy + rb * math.sin(a), bottom)
                ]),
                fill="#d9e3d4",
                width=max(1, 2 * s)
            )

        for radius, height in ((rt, top), (rb, bottom)):
            ring = [
                world(
                    cx + radius * math.cos(i * math.tau / segments),
                    cy + radius * math.sin(i * math.tau / segments),
                    height
                )
                for i in range(segments + 1)
            ]
            c.create_line(
                *coords(ring),
                fill="#dfe8d8",
                width=max(1, 3 * s)
            )


PulaPutiGame = RedPacketRainGame
DropBallGame = RedPacketRainGame


class EmbeddedGamePage(tk.Frame):
    def __init__(self, parent, balance, user, *, demo=False, store=None,
                 on_back=None, on_balance_change=None):
        super().__init__(parent, bg=Theme.APP_BG, width=1150, height=750)
        self.pack_propagate(False)
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self._returned = False
        self.game = None
        try:
            self.game = RedPacketRainGame(
                self, balance, user, demo=demo, store=store, manage_window=False
            )
            top = self.winfo_toplevel()
            top.geometry("1150x750")
            top.resizable(False, False)
        except Exception:
            self.destroy()
            raise

    @property
    def balance(self):
        return self.game.balance

    def finish(self, value):
        if self._returned:
            return
        self._returned = True
        value = float(value)
        if callable(self.on_balance_change):
            self.on_balance_change(value)
        if callable(self.on_back):
            self.on_back(value)
        else:
            self.destroy()

    def on_close(self):
        if self.game is not None:
            self.game.on_closing()

    on_closing = on_close

    def stop_game(self):
        if self.game is not None:
            self.game.stop_game()

    def destroy(self):
        if self.game is not None:
            self.game._cancel_jobs()
        super().destroy()


def main(initial_balance=1000.0, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None, demo=False):
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        store = AccountStore(actual_user, demo)
        return EmbeddedGamePage(
            parent, actual_balance, actual_user, demo=demo, store=store,
            on_back=on_back, on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title('Pula-Puti')
    root.geometry('1150x750+50+10')
    root.resizable(False, False)
    root.configure(bg=Theme.APP_BG)

    store = AccountStore(actual_user, demo)
    page = RedPacketRainGame(root, actual_balance, actual_user, demo=demo, store=store)

    def close_standalone(_balance=None):
        try:
            if callable(on_balance_change):
                on_balance_change(float(page.balance))
        except Exception:
            pass
        try:
            if page._job is not None:
                root.after_cancel(page._job)
        except tk.TclError:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass

    page._embedded_return = close_standalone
    root.protocol('WM_DELETE_WINDOW', page.on_closing)
    root.mainloop()
    return float(page.balance)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pula-Puti")
    parser.add_argument("--demo", action="store_true", help="虚拟积分演示，不读写账户")
    parser.add_argument("--balance", default="10000", help="演示初始积分")
    args = parser.parse_args()
    try:
        final_balance = main(money(args.balance), "test_user", demo=args.demo)
        print(f"Final balance: {final_balance:.2f}")
    except (RuntimeError, ValueError, tk.TclError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)