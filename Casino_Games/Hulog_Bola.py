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

VERSION = "PocketRain-DropBall-2.5D-R16"

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
    if value<10000:return f"{value:,}"
    unit,suffix=(1000000,"M") if value>=1000000 else (10000,"W")
    tenths,remainder=divmod(value,unit//10)
    whole,decimal=divmod(tenths,10)
    label=str(whole)+(f".{decimal}" if decimal else "")
    return label+suffix+("+" if remainder else "")


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






CARDS = ("9", "10", "J", "Q", "K", "A")
SUITS = ("♠", "♣", "♥", "♥", "♦", "♣")
PROFIT_ODDS = (0, 1, 2, 12)
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


def settle_table(balance, bets, outcomes, *, bonus_multiplier=0, bonus_slot=-1, bonus_values=()):
    balance=money(balance);bets=tuple(money(v) for v in bets);outcomes=tuple(outcomes)
    if len(bets)!=6 or len(outcomes)!=3 or any(i not in range(-1,6) for i in outcomes):
        raise ValueError("下注区域或球数无效")
    stake=sum(bets,Decimal(0))
    if not 0<=stake<=balance:raise ValueError("总下注不能超过余额")
    invalid=-1 in outcomes
    returned=stake if invalid else sum((bet*(1+PROFIT_ODDS[outcomes.count(i)])
                 for i,bet in enumerate(bets) if outcomes.count(i)),Decimal(0))
    if bonus_multiplier:
        if invalid or len(set(outcomes))!=1 or not 4<=bonus_multiplier<=100:
            raise ValueError("Plinko 仅适用于三球同格，倍数必须为 4–100")
        returned=bets[outcomes[0]]*bonus_multiplier
    return TableResult(bets,stake,outcomes,returned,returned-stake,balance-stake+returned,invalid,
                       bonus_multiplier,bonus_slot,tuple(bonus_values))


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
    """World units: metre, second; open 3 x 2 tray with perimeter ramps; no target-dependent forces."""
    WIDTH, DEPTH = 3.0, 2.0
    RADIUS = 0.045
    OUTLET = (WIDTH / 2, DEPTH / 2)
    OUTLET_HEIGHT = 0.8  # height above the table, at the bottom of the ball
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
    RAIL_X = (1.0, 2.0)
    RAIL_Y = (1.0,)
    FUNNEL_TOP = 1.70
    FUNNEL_RADIUS = 0.68
    NECK_RADIUS = 0.18
    FUNNEL_SLOPE = (FUNNEL_RADIUS-NECK_RADIUS)/(FUNNEL_TOP-OUTLET_HEIGHT)
    RAMP_WIDTH = 0.25
    FRONT_RAMP_DEPTH = 0.60
    RAMP_HEIGHT = 0.34
    RIM_HEIGHT = 0.035
    ALLOW_ESCAPE = False  # Default enclosure; opt in explicitly for open-rim rounds.
    AIR_DRAG = 0.10  # acceleration coefficient for v*|v|, tune for the table


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
            # Initial conditions are randomized at the mouth. Nothing is reset
            # at the outlet: cone contacts and other balls determine exit speed.
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
        """Unit mass thin-shell sphere: contact impulse includes angular velocity."""
        for axis,n in zip(("x","y","z"),normal):
            setattr(b,axis,getattr(b,axis)+n*max(0,penetration))
        arm = tuple(-self.RADIUS*n for n in normal)
        spin = self._cross((b.wx,b.wy,b.wz),arm)
        cv = tuple(getattr(b,v)+spin[i] for i,v in enumerate(("vx","vy","vz")))
        vn = sum(cv[i]*normal[i] for i in range(3))
        if vn >= 0:
            return
        # Resting contacts absorb tiny impacts instead of continually rebounding.
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
        """Finite cone + rounded lip contact; never extend the cone below its hole."""
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
            # Closest point on the circular rim. Below the lip its normal points
            # DOWN, so a falling ball exits instead of sticking to an infinite cone.
            cr,cz=(self.NECK_RADIUS,self.OUTLET_HEIGHT) if t<=0 else (self.FUNNEL_RADIUS,self.FUNNEL_TOP)
            radial,vertical=rho-cr,b.z-cz
            distance=math.hypot(radial,vertical)
            if 1e-12<distance<r:
                normal=(dx/rho*radial/distance,dy/rho*radial/distance,vertical/distance)
                self._surface_contact(b,normal,r-distance,.62,.065)

    def _terrain(self, b):
        """Height and inward normal of the flat bed / four surrounding ramps."""
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
        # Default enclosure reflects at every height; optional open mode retains a finite lip.
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
        # Rounded low rails between cards; the top and side share one smooth
        # collision surface. A low ball can bounce sideways or climb the ridge.
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
            # Quadratic air resistance for a lightweight hollow ball.
            speed=math.sqrt(b.vx*b.vx+b.vy*b.vy+b.vz*b.vz)
            drag=max(0,1-self.AIR_DRAG*speed*dt)
            b.vx*=drag;b.vy*=drag;b.vz*=drag
            b.z+=b.vz*dt-0.5*self.GRAVITY*dt*dt
            b.vz-=self.GRAVITY*dt
            b.x+=b.vx*dt;b.y+=b.vy*dt
        # Repeated contact resolution handles a ball trapped between rail and ball.
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

    def simulate(self):
        """Integrate until every ball rests; never steer, snap to a card or reroll."""
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
                outcomes = tuple(-1 if b.escaped else min(2,max(0,int(b.x/(self.WIDTH/3)))) +
                                 3*min(1,max(0,int(b.y/(self.DEPTH/2)))) for b in self.balls)
                return frames, outcomes
        raise RuntimeError("物理模拟未在时限内停稳，本轮未扣款。")


class PlinkoPhysics:
    """One 2D hollow ball, fixed pegs and 18 physical bins. Only release is random."""
    WIDTH,HEIGHT=18.,20.
    RADIUS,PEG_RADIUS=.18,.12
    DT,FRAME_DT=1/480,1/60
    GRAVITY=9.81
    def __init__(self,rng=None):
        rng=rng or random.SystemRandom()
        total=rng.randint(180,220)
        base,remainder=divmod(total,18)
        values=[base+(i<remainder) for i in range(18)]
        # Preserve the sum while keeping all bins near the board average.
        # No small group of large awards surrounded by minimum-value bins.
        low=max(4,base-3);high=min(100,base+4)
        for _ in range(180):
            a,b=rng.sample(range(18),2)
            if values[a]>low and values[b]<high:
                values[a]-=1;values[b]+=1
        rng.shuffle(values)
        self.multipliers=tuple(values)
        self.launch_duration=rng.uniform(2.,3.)
        self.launch_phase=rng.uniform(0.,32.8)
        self.launch_speed=28.
        self.x=self.launcher_x(self.launch_duration);self.y=1.1
        self.vx=0.;self.vy=0.;self.spin=0.
        self.pegs=[(j+(.5 if row%2==0 else 1),3+row*1.1)
                   for row in range(12) for j in range(18 if row%2==0 else 17)]
        self.contacts=0

    def launcher_x(self,elapsed):
        distance=(self.launch_phase+self.launch_speed*max(0,min(elapsed,self.launch_duration)))%32.8
        return .8+(distance if distance<=16.4 else 32.8-distance)

    def contact(self,nx,ny,penetration,restitution=.65,friction=.08):
        self.x+=nx*max(0,penetration);self.y+=ny*max(0,penetration)
        vn=self.vx*nx+self.vy*ny
        if vn>=0:return
        restitution*=min(1,max(0,(-vn-.04)/.2))
        impulse=-(1+restitution)*vn
        # Tangential speed at the contact includes the sphere's spin.
        tx,ty=-ny,nx
        slip=self.vx*tx+self.vy*ty-self.spin*self.RADIUS
        jt=max(-friction*impulse,min(friction*impulse,-slip/2.5))
        self.vx+=impulse*nx+jt*tx;self.vy+=impulse*ny+jt*ty
        self.spin-=jt*self.RADIUS/((2/3)*self.RADIUS**2)
        self.contacts+=1

    def step(self):
        dt=self.DT;r=self.RADIUS
        drag=1/(1+.035*math.hypot(self.vx,self.vy)*dt)
        self.vx*=drag;self.vy*=drag
        self.x+=self.vx*dt;self.y+=self.vy*dt+.5*self.GRAVITY*dt*dt
        self.vy+=self.GRAVITY*dt
        for _ in range(3):
            if self.x<r:self.contact(1,0,r-self.x,.55)
            if self.x>18-r:self.contact(-1,0,self.x-(18-r),.55)
            if self.y<r:self.contact(0,1,r-self.y,.55)
            for px,py in self.pegs:
                if abs(self.y-py)>.31:continue
                dx,dy=self.x-px,self.y-py;d=math.hypot(dx,dy)
                if d<r+self.PEG_RADIUS:
                    nx,ny=(dx/d,dy/d) if d>1e-10 else (0,-1)
                    self.contact(nx,ny,r+self.PEG_RADIUS-d)
            # Capsules forming the bin dividers: same geometry used for drawing.
            if self.y>16.7:
                for wall in range(1,18):
                    dx=self.x-wall;dy=self.y-max(17.,min(20.,self.y));d=math.hypot(dx,dy)
                    if d<r+.025:
                        nx,ny=(dx/d,dy/d) if d>1e-10 else (1,0)
                        self.contact(nx,ny,r+.025-d,.35)
            if self.y>20-r:self.contact(0,-1,self.y-(20-r),.25,.25)
        if self.y>=20-r-1e-8 and abs(self.vy)<1e-7:
            self.vx*=max(0,1-5*dt);self.spin*=max(0,1-5*dt)

    def simulate(self):
        frames=[(self.x,self.y)];quiet=0
        for tick in range(round(45/self.DT)):
            self.step()
            if (tick+1)%8==0:frames.append((self.x,self.y))
            resting=self.y>=20-self.RADIUS-1e-7 and abs(self.vy)<1e-7 and abs(self.vx)<.01
            quiet=quiet+1 if resting else 0
            if quiet>=120:
                frames.append((self.x,self.y))
                return frames,min(17,max(0,int(self.x)))
        raise RuntimeError("Plinko 未停稳，本轮未扣款。")


class AccountStore:
    """Use the supplied project's encrypted storage; never fall back to plaintext."""
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
        # Do not silently replace malformed/missing account storage or create users.
        with open(str(self.path), "r", encoding="utf-8") as stream:
            users = json.load(stream)
        if not isinstance(users, list):
            raise ValueError("账户数据格式不正确")
        account = next((u for u in users if isinstance(u, dict)
                        and u.get("user_name") == self.username), None)
        if account is None:
            raise ValueError("账户不存在，请从原项目登录后开启游戏")
        account["cash"] = f"{balance:.2f}"
        # Use the exact filename expected by the project's secure_json wrapper.
        with open(str(self.path), "w", encoding="utf-8") as stream:
            json.dump(users, stream, ensure_ascii=False, indent=4)


class DropBallHistory:
    """Roulette-style project log; Record1 is 15 rounds, Record2 is 1000 rounds."""
    def __init__(self, path=None):
        self.path=Path(path) if path else None
        self.data={"Total":0,"Record1":{},"Record2":{}}
        if self.path and self.path.exists():
            with open(str(self.path),encoding="utf-8") as f:data=json.load(f)
            if not isinstance(data,dict) or not isinstance(data.get("Record2"),dict):
                raise ValueError("落球历史记录格式错误")
            self.data=data

    def entries(self):
        return sorted(self.data["Record2"].values(),key=lambda e:e["round"],reverse=True)

    def add(self,result):
        number=self.data["Total"]+1
        entry={"round":number,"outcomes":list(result.outcomes),"invalid":result.invalid,
               "bets":[str(v) for v in result.bets],"returned":str(result.returned),"net":str(result.net),
               "plinko":{"multiplier":result.bonus_multiplier,"slot":result.bonus_slot,"values":list(result.bonus_values)}}
        recent=([entry]+self.entries())[:1000]
        data={"Total":number,"Record1":{f"{e['round']}_Data":e for e in recent[:15]},
              "Record2":{f"{e['round']}_Data":e for e in recent}}
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            # Exact project filename preserves the installed secure-json routing.
            with open(str(self.path),"w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=4)
        self.data=data

    def recent(self):
        return [tuple("出界" if i<0 else CARDS[i] for i in sorted(e["outcomes"],key=lambda i:6 if i<0 else i))
                for e in self.entries()[:15]]

    def percentages(self,limit=50):
        entries=[e for e in self.entries()[:limit] if not e["invalid"]]
        balls=[i for e in entries for i in e["outcomes"] if i in range(6)]
        return [100*balls.count(i)/len(balls) if balls else 0 for i in range(6)],len(entries)


HISTORY_COLORS={"9":"#174A8B","10":"#17603B","J":"#982D33","Q":"#663399","K":"#875017","A":"#000000"}

CARD_ASSET_NAMES=("Spade9.png","Club10.png","DiamondJ.png","HeartQ.png","DiamondK.png","ClubA.png")


def card_asset_candidates(script_file):
    current=Path(script_file).resolve().parent
    return [base/"A_Tools"/"Card"/"Poker1" for base in (current,current.parent,current.parent.parent)]


def perspective_coefficients(destination, source):
    """Solve inverse homography: destination canvas -> source image coordinates."""
    rows=[]
    for (x,y),(u,v) in zip(destination,source):
        rows.append([x,y,1,0,0,0,-u*x,-u*y,u])
        rows.append([0,0,0,x,y,1,-v*x,-v*y,v])
    for col in range(8):
        pivot=max(range(col,8),key=lambda i:abs(rows[i][col]))
        rows[col],rows[pivot]=rows[pivot],rows[col]
        divisor=rows[col][col]
        if abs(divisor)<1e-12:raise ValueError("退化牌面投影")
        rows[col]=[value/divisor for value in rows[col]]
        for i in range(8):
            if i!=col:
                factor=rows[i][col]
                rows[i]=[value-factor*other for value,other in zip(rows[i],rows[col])]
    return tuple(rows[i][8] for i in range(8))


class RedPacketRainGame:
    """Compatibility class name; the gameplay is now six-card Drop Ball."""
    WINDOW_WIDTH, WINDOW_HEIGHT = 1150, 750

    def __init__(self, root, initial_balance, username, *, demo=False, store=None,
                 manage_window=True):
        self.root, self.username = root, username
        self.balance = money(initial_balance)
        self.store = store if store is not None else AccountStore(username, demo)
        self.demo = demo
        self.bet_per_draw = Decimal("0.00")
        self.selected = None
        self.bets = [Decimal("0.00") for _ in CARDS]
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
        self._bonus_frames=[]
        self._bonus_pose=None
        self._bonus_model=None
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
        log_path=Path(account_path).parents[2]/"A_Logs/Json/Pocket_Rain.json" if account_path and not demo else None
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
        self.load_card_assets()
        self.root.configure(bg=Theme.APP_BG)
        # Embedded pages leave the shared root close protocol to the host.
        self._close_command = None
        if manage_window:
            if isinstance(root, (tk.Tk, tk.Toplevel)):
                root.title("乒乓落球")
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

    def load_card_assets(self):
        candidates=card_asset_candidates(__file__)
        directory=next((p for p in candidates if p.is_dir() and (p/"Background.png").is_file()),None)
        if directory is None:
            directory=next((p for p in candidates if any((p/name).is_file() for name in CARD_ASSET_NAMES)),None)
        missing=[]
        for i,name in enumerate(CARD_ASSET_NAMES):
            path=directory/name if directory else None
            if Image is not None and path and path.is_file():
                try:
                    with Image.open(path) as image:self._card_sources[i]=image.convert("RGBA")
                    continue
                except (OSError,ValueError):pass
            missing.append(name)
        if Image is not None and directory:
            for i,name in enumerate(CARD_ASSET_NAMES):
                golden=directory/"Golden"/name
                if golden.is_file():
                    try:
                        with Image.open(golden) as image:self._golden_sources[i]=image.convert("RGBA")
                    except (OSError,ValueError):pass
        if Image is None:self.asset_message="显示原项目牌图需要 Pillow：pip install Pillow"
        elif missing:self.asset_message="缺少牌图："+", ".join(missing)+"；目录 A_Tools/Card/Poker1"

    def _draw_card_asset(self,index,quad,scale,ox,oy):
        """Project artwork onto the exact landing-cell polygon without extra width reduction."""
        minx=min(x for x,y in quad);maxx=max(x for x,y in quad)
        miny=min(y for x,y in quad);maxy=max(y for x,y in quad)
        centre=(minx+maxx)/2
        left=minx
        width=max(1,round((maxx-minx)*scale));height=max(1,round((maxy-miny)*scale))
        if index not in self._card_sources:
            self.canvas.create_text(ox+centre*scale,oy+(miny+maxy)/2*scale,
                text=CARDS[index]+" · 缺少图片\n"+CARD_ASSET_NAMES[index],fill=Theme.TEXT_MUTED,
                font=(Theme.FONT_CJK,max(7,round(9*scale))))
            return
        destination=[((x-left)*scale,(y-miny)*scale) for x,y in quad]
        key=(index,width,height,tuple(round(v,3) for point in destination for v in point))
        if key not in self._card_cache:
            source=self._card_sources[index];iw,ih=source.size
            coefficients=perspective_coefficients(destination,[(0,0),(iw,0),(iw,ih),(0,ih)])
            warped=source.transform((width,height),Image.Transform.PERSPECTIVE,coefficients,
                                    Image.Resampling.BICUBIC,fillcolor=(0,0,0,0))
            if len(self._card_cache)>36:self._card_cache.clear()
            self._card_cache[key]=ImageTk.PhotoImage(warped,master=self.root)
        photo=self._card_cache[key];self._card_draw_refs.append(photo)
        self.canvas.create_image(ox+left*scale,oy+miny*scale,image=photo,anchor="nw")

    def create_widgets(self):
        self.balance_var=tk.StringVar(master=self.root)
        self.bet_var=tk.StringVar(master=self.root)
        self.last_win_var=tk.StringVar(master=self.root,value="上局获胜: $0")
        self.stage_var=tk.StringVar(master=self.root,value="等待下注")
        self.info_var=tk.StringVar(master=self.root,value="请下注")
        self.result_var=tk.StringVar(master=self.root,value="")
        main=tk.Frame(self.root,bg=Theme.APP_BG);main.pack(fill="both",expand=True,padx=10,pady=10)
        right=tk.Frame(main,bg=Theme.APP_BG,width=400)
        right.pack(side="right",fill="y");right.pack_propagate(False)
        board=tk.Frame(main,bg=Theme.APP_BG,highlightbackground="#D8B46A",highlightthickness=2)
        board.pack(side="left",fill="both",expand=True,padx=(0,10))
        self.canvas=tk.Canvas(board,bg="#263d38",highlightthickness=0);self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.draw_scene())
        # Caribbean's distinct bordered cards, gold section headers and inset bodies.
        def section(title=None,padding=2):
            card=tk.Frame(right,bg=Theme.PANEL,bd=1,relief=tk.SOLID)
            card.pack(fill="x",pady=1)
            if title:
                header=tk.Frame(card,bg="#D8B46A");header.pack(fill="x")
                tk.Label(header,text=title,font=("Arial",13,"bold"),bg="#D8B46A",fg="#2A1B08").pack(pady=2)
            body=tk.Frame(card,bg=Theme.PANEL);body.pack(fill="x",padx=10,pady=padding)
            return body
        info=section(padding=4)
        tk.Label(info,textvariable=self.balance_var,font=("Arial",16,"bold"),bg=Theme.PANEL,fg="black").pack(side="left")
        tk.Label(info,textvariable=self.stage_var,font=("Arial",14,"bold"),bg=Theme.PANEL,fg="#A88100").pack(side="right")
        limits=section("下注上限",padding=8)
        self.limit_value_labels=[]
        for col,name in enumerate(("下注下限","单区上限","总下注上限")):
            limits.columnconfigure(col,weight=1)
            title=tk.Label(limits,text=name,bg=Theme.PANEL,fg="#2A1B08",font=("Arial",11,"bold"),bd=1,relief=tk.SOLID)
            title.grid(row=0,column=col,sticky="nsew")
            value=tk.Label(limits,bg=Theme.PANEL,fg="#A88100",font=("Arial",12,"bold"),bd=1,relief=tk.SOLID)
            value.grid(row=1,column=col,sticky="nsew")
            self.limit_value_labels.append(value)
        def bind_limit(widget):
            widget.bind("<Button-1>",self.toggle_high_bet_limits)
            for child in widget.winfo_children():bind_limit(child)
        bind_limit(limits.master)
        self._update_limits_display()
        combined=section("筹码与下注",padding=2)
        self.bet_canvas=tk.Canvas(combined,width=376,height=154,bg=Theme.PANEL,highlightthickness=0,cursor="hand2",takefocus=1)
        self.bet_canvas.pack(fill="x")
        self.bet_canvas.bind("<Button-1>",self._bet_click)
        self.bet_canvas.bind("<Button-3>",self._bet_clear_click)
        self.bet_canvas.bind("<Key>",self._bet_key)
        self.root.bind("<Return>",lambda e:self.start_game(),add="+")
        action=section("操作",padding=2)
        tk.Label(action,textvariable=self.info_var,font=("Arial",10,"bold"),bg=Theme.PANEL,fg="#2A1B08",wraplength=370,height=1).pack(fill="x",pady=(0,3))
        buttons=tk.Frame(action,bg=Theme.PANEL);buttons.pack(fill="x")
        self.reset_bet_button=ModernButton(buttons,text="清除下注",command=self.reset_bet,background="#C94A4A",foreground="white",pady=4)
        self.repeat_button=ModernButton(buttons,text="重复上局下注",command=self.repeat_last_bet,background="#4A90E2",foreground="white",pady=4)
        self.start_button=ModernButton(buttons,text="开始游戏",command=self.start_game,background="#D8B46A",foreground="#2A1B08",bold=True,pady=4)
        for i,button in enumerate((self.reset_bet_button,self.repeat_button,self.start_button)):
            button.grid(row=0,column=i,sticky="ew",padx=2,pady=1)
            buttons.columnconfigure(i,weight=1,uniform="actions")
        buttons.columnconfigure(0,weight=1);buttons.columnconfigure(1,weight=1)
        history=section("最近15局",padding=2)
        self.history_canvas=tk.Canvas(history,width=376,height=75,bg="white",highlightthickness=0)
        self.history_canvas.pack(fill="x")
        self.draw_history()
        stats=section(padding=2)
        self.stats_button=tk.Button(stats.master,text="50局的分布",command=self.change_stats_limit,
                                    font=("Arial",13,"bold"),bg="#D8B46A",activebackground="#D8B46A",
                                    fg="#2A1B08",relief=tk.FLAT,overrelief=tk.FLAT,bd=0,highlightthickness=0,cursor="hand2")
        self.stats_button.pack(fill="x",before=stats)
        self.stats_canvas=tk.Canvas(stats,width=376,height=39,bg="white",highlightthickness=0)
        self.stats_canvas.pack(fill="x")
        self.draw_statistics()
        bottom=section(padding=4)
        tk.Label(bottom,textvariable=self.bet_var,font=("Arial",12),bg=Theme.PANEL,fg="black").pack(anchor="w")
        row_last=tk.Frame(bottom,bg=Theme.PANEL);row_last.pack(fill="x",pady=2)
        tk.Label(row_last,textvariable=self.last_win_var,font=("Arial",12),bg=Theme.PANEL,fg="black").pack(side="left")
        tk.Button(row_last,text="ℹ️",command=self.show_game_instructions,bg="#4B8BBE",fg="white",
                  font=("Arial",12),width=2,relief=tk.FLAT).pack(side="right")

    def show_game_instructions(self):
        existing=getattr(self,"_instruction_window",None)
        if existing is not None:
            try:
                if existing.winfo_exists():existing.lift();existing.focus_force();return
            except tk.TclError:pass
        parent=self.root.winfo_toplevel();parent.update_idletasks()
        dialog=tk.Toplevel(parent);self._instruction_window=dialog
        dialog.title("乒乓落球 · 游戏说明");dialog.resizable(False,False);dialog.transient(parent)
        bg,header,panel,border,gold,text,muted="#0f1311","#151b18","#18201c","#43534a","#e7d36c","#f4f4ee","#c1cbc6"
        font=Theme.FONT_CJK;dialog.configure(bg=bg)
        x=parent.winfo_rootx()+(parent.winfo_width()-1000)//2
        y=parent.winfo_rooty()+(parent.winfo_height()-650)//2
        dialog.geometry(f"1000x650+{max(0,x)}+{max(0,y)}")
        head=tk.Frame(dialog,bg=header,height=82);head.pack(fill="x");head.pack_propagate(False)
        tk.Label(head,text="乒乓落球  HULOG-BOLA",font=(font,20,"bold"),fg=gold,bg=header).place(x=24,y=10)
        tk.Label(head,text="玩法 · 派奖 · 乒乓落球 · 记录",font=(font,14),fg=muted,bg=header).place(x=25,y=48)
        def close(event=None):
            self._instruction_window=None;dialog.destroy()
        tk.Button(head,text="关闭  ESC",command=close,font=(font,14,"bold"),bg="#2a332e",fg=text,
                  activebackground="#3a463f",activeforeground="white",relief=tk.FLAT,bd=0,cursor="hand2").place(x=850,y=20,width=120,height=42)
        dialog.protocol("WM_DELETE_WINDOW",close);dialog.bind("<Escape>",close)
        tk.Frame(dialog,bg=gold,height=3).pack(fill="x")
        host=tk.Frame(dialog,bg=bg);host.pack(fill="both",expand=True)
        scrollbar=tk.Scrollbar(host);scrollbar.pack(side="right",fill="y")
        canvas=tk.Canvas(host,bg=bg,highlightthickness=0,yscrollcommand=scrollbar.set)
        canvas.pack(side="left",fill="both",expand=True);scrollbar.configure(command=canvas.yview)
        content=tk.Frame(canvas,bg=bg);item=canvas.create_window((0,0),window=content,anchor="nw")
        canvas.bind("<Configure>",lambda e:canvas.itemconfigure(item,width=e.width))
        content.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        dialog.bind("<MouseWheel>",lambda e:canvas.yview_scroll(-1 if e.delta>0 else 1,"units"))
        dialog.bind("<Button-4>",lambda e:canvas.yview_scroll(-1,"units"))
        dialog.bind("<Button-5>",lambda e:canvas.yview_scroll(1,"units"))
        def card(title):
            box=tk.Frame(content,bg=panel,highlightbackground=border,highlightthickness=1)
            box.pack(fill="x",padx=10,pady=8)
            tk.Label(box,text=title,font=(font,18,"bold"),fg=gold,bg=panel,anchor="w").pack(fill="x",padx=18,pady=(15,10))
            return box
        def rule(box,title,body):
            row=tk.Frame(box,bg=panel);row.pack(fill="x",padx=18,pady=(0,14))
            tk.Frame(row,bg=gold,width=5).pack(side="left",fill="y",padx=(0,12))
            words=tk.Frame(row,bg=panel);words.pack(side="left",fill="x",expand=True)
            tk.Label(words,text=title,font=(font,16,"bold"),fg=text,bg=panel,anchor="w").pack(fill="x")
            tk.Label(words,text=body,font=(font,14),fg=muted,bg=panel,justify="left",anchor="w",wraplength=850).pack(fill="x",pady=(4,0))
        box=card("01  下注与落球")
        rule(box,"选择筹码 → 点击牌面 → 开始游戏","可以多区下注，也可以零下注试玩。重复上局下注会恢复最近一次有下注的金额。")
        box=card("02  派奖（含本金）")
        for i,(condition,value) in enumerate((("同格 1 球","该格下注 × 2"),("同格 2 球","该格下注 × 3"),("同格 3 球","进入 BALL DROP"),("没有命中","不返还"))):
            row=tk.Frame(box,bg="#202923" if i%2 else "#1b241f");row.pack(fill="x",padx=18,pady=1)
            tk.Label(row,text=condition,font=(font,14),fg=text,bg=row.cget("bg"),padx=12,pady=7).pack(side="left")
            tk.Label(row,text=value,font=(font,14,"bold"),fg=gold,bg=row.cget("bg"),padx=12).pack(side="right")
        box=card("03  BALL DROP · Plinko 示意")
        diagram=tk.Canvas(box,width=920,height=440,bg=panel,highlightthickness=0)
        diagram.pack(fill="x",padx=18,pady=(0,12));self._draw_plinko_guide(diagram)
        rule(box,"三球同格，即可进入","未下注也会播放。派奖＝三球所在格子的下注 × 奖励球最终落点倍数。")
        box=card("04  最近记录与分布")
        rule(box,"对子浅黄 · 三同浅粉蓝","对子只标记重复的两个格子。点击分布标题，可切换 50／100／250／500／1000 局。")

    @staticmethod
    def _draw_plinko_guide(c):
        scale=18;ox=22;oy=32
        c.create_rectangle(ox,oy,ox+18*scale,oy+20*scale,fill="#15332e",outline="#e7d36c",width=2)
        c.create_line(ox+18,oy+12,ox+18*scale-18,oy+12,fill="#e7d36c",arrow=tk.BOTH,width=2)
        c.create_rectangle(ox+7.3*scale,oy+5,ox+8.7*scale,oy+15,fill="#FFDE35",outline="#B8860B")
        for row in range(12):
            for col in range(18 if row%2==0 else 17):
                x=ox+(col+(.5 if row%2==0 else 1))*scale;y=oy+(3+row*1.1)*scale
                c.create_oval(x-2,y-2,x+2,y+2,fill="#dfdbc6",outline="")
        for i in range(18):
            x=ox+i*scale
            c.create_line(x,oy+17*scale,x,oy+20*scale,fill="#D8B46A",width=1)
            c.create_rectangle(x,oy+19*scale,x+scale,oy+20*scale,fill="#426658",outline="#D8B46A")
            c.create_text(x+scale/2,oy+19.5*scale,text=str(10+i%3),fill="white",font=("Arial",8,"bold"))
        c.create_oval(ox+8*scale-4,oy+1.4*scale-4,ox+8*scale+4,oy+1.4*scale+4,fill="#FFDE35",outline="#B8860B")
        for y,title,body in ((70,"① 黄色长条左右移动","快速往返随机 2–3 秒，停止后原位放球。"),
                             (180,"② 小球碰撞钉板","球按重力与碰撞反弹，向底部落下。"),
                             (290,"③ 落入 18 个出口之一","该出口数字就是本次派奖倍数。")):
            c.create_text(400,y,text=title,anchor="nw",fill="#e7d36c",font=(Theme.FONT_CJK,16,"bold"))
            c.create_text(400,y+35,text=body,anchor="nw",width=475,fill="#c1cbc6",font=(Theme.FONT_CJK,14))
        c.create_text(ox,oy+20*scale+20,text="示意图，出口倍数每局随机",anchor="nw",fill="#c1cbc6",font=(Theme.FONT_CJK,12))

    def update_display(self):
        self.bet_per_draw=sum(self.bets,Decimal(0))
        self.balance_var.set(f"余额: ${self.balance:,.2f}")
        self.stage_var.set(("Ball Drop" if self._bonus_active else "落球中") if self.game_active else ("已结算" if self._settled else "下注中"))
        display_stake=self.bet_per_draw if self._new_ticket or self._last_result is None else self._last_result.stake
        self.bet_var.set(f"本局下注: ${int(display_stake):,}")
        self.last_win_var.set(f"上局获胜: ${int(self.last_win):,}")
        state=tk.DISABLED if self.game_active or self._settled else tk.NORMAL
        self.reset_bet_button.configure(state=state)
        ready=not self.game_active and not self._settled and not self._chip_moves and self.valid_bets(self.bets) and self.bet_per_draw<=self.balance
        self.start_button.configure(state=tk.NORMAL if ready else tk.DISABLED,text="开始游戏")
        self.repeat_button.configure(state=tk.NORMAL if not self.game_active and not self._settled and self._last_bets and self.valid_bets(self._last_bets) and sum(self._last_bets)<=self.balance else tk.DISABLED)
        self.draw_betting()

    def draw_betting(self):
        c=self.bet_canvas;c.delete("all");self._bet_draw_refs=[]
        for i,(label,amount,color,fg) in enumerate(self.chip_configs):
            x=31+i*62;y=27
            c.create_oval(x-23,y-23,x+23,y+23,fill=color,outline="#d4af37" if i==self.selected_chip else "black",width=3 if i==self.selected_chip else 1)
            c.create_text(x,y,text=label,fill=fg,font=("Arial",10,"bold"))
        for i in range(6):
            x=2+i*62;y=63
            # Whole image fills the whole flat betting cell; no green letterboxing.
            c.create_rectangle(x,y,x+58,y+86,fill="white",outline="#9C8B59",width=1)
            image_key,card_source=self._bet_image_source(i)
            if card_source is not None:
                if image_key not in self._bet_image_cache:
                    image=ImageOps.fit(card_source,(56,84),Image.Resampling.LANCZOS)
                    self._bet_image_cache[image_key]=ImageTk.PhotoImage(image,master=self.root)
                photo=self._bet_image_cache[image_key];self._bet_draw_refs.append(photo)
                c.create_image(x+29,y+43,image=photo)
            else:
                c.create_text(x+29,y+43,text=CARD_ASSET_NAMES[i],fill="#596169",font=("Arial",9))
            pending=sum((move[2] for move in self._chip_moves if move[1]==i),Decimal(0))
            visible=Decimal(0) if self._return_started is not None else max(Decimal(0),self.bets[i]-pending)
            lost=(self._settled and self._last_result and not self._last_result.invalid and i not in self._last_result.outcomes)
            if lost:visible=Decimal(0)
            if visible:
                shown=visible
                if self._settled and self._last_result and not self._last_result.invalid and self._last_result.outcomes.count(i):
                    if self._flash_step%2 or not self._flash_active:shown=self._area_return(i)
                config=self.chip_for_amount(shown)
                c.create_oval(x+10,y+24,x+48,y+62,fill=config[2],outline="#d4af37",width=2)
                c.create_text(x+29,y+43,text=chip_amount_text(shown),fill=config[3],font=("Arial",9,"bold"))
            if self._settled and self._last_result and not self._last_result.invalid and i not in self._last_result.outcomes:
                c.create_rectangle(x+1,y+1,x+57,y+85,fill="#16241c",outline="",stipple="gray50")
        now=time.monotonic()
        for started,index,amount,chip in self._chip_moves:
            t=min(1,(now-started)/.32);ease=1-(1-t)**3
            sx,sy=31+chip*62,27;tx=31+index*62;ty=106
            x=sx+(tx-sx)*ease;y=sy+(ty-sy)*ease
            color,fg=self.chip_for_amount(amount)[2:]
            c.create_oval(x-19,y-19,x+19,y+19,fill=color,outline="#d4af37",width=2)
            c.create_text(x,y,text=chip_amount_text(amount),fill=fg,font=("Arial",9,"bold"))

        if self._return_started is not None:
            t=min(1,(now-self._return_started)/.4);ease=1-(1-t)**3
            for index,amount,chip in self._return_moves:
                x=(31+index*62)+(chip-index)*62*ease;y=106-79*ease
                color,fg=self.chip_for_amount(amount)[2:]
                c.create_oval(x-19,y-19,x+19,y+19,fill=color,outline="#d4af37",width=2)
                c.create_text(x,y,text=chip_amount_text(amount),fill=fg,font=("Arial",9,"bold"))

    def _bet_click(self,event):
        if self.game_active or self._closed or self._settled:return
        self.bet_canvas.focus_set()
        for i in range(len(self.chip_configs)):
            if math.hypot(event.x-(31+i*62),event.y-27)<=25:
                self.selected_chip=i;self.draw_betting();return
        for i in range(6):
            x=2+i*62;y=63
            if x<=event.x<=x+58 and y<=event.y<=y+86:self.place_bet(i);return

    def _bet_clear_click(self,event):
        if self.game_active or self._closed or self._settled:return
        for i in range(6):
            x=2+i*62;y=63
            if x<=event.x<=x+58 and y<=event.y<=y+86:
                self.bets[i]=Decimal(0)
                self._bet_actions=[a for a in self._bet_actions if a[0]!=i]
                self._chip_moves=[a for a in self._chip_moves if a[1]!=i]
                self.update_display();self.draw_scene();return

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
        if event.char in "123456" and event.char:self.place_bet(int(event.char)-1)
        elif event.keysym in ("Left","Right") and not self.game_active:
            self.selected_chip=(self.selected_chip+(1 if event.keysym=="Right" else -1))%len(self.chip_configs);self.draw_betting()

    def place_bet(self,index):
        if self.game_active or self._closed or self._settled or index not in range(6):return
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
        self._chip_moves.clear();self._bet_actions.clear();self.bets=[Decimal(0) for _ in CARDS]
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
            bonus_model=None;bonus_frames=[];bonus_slot=-1
            if -1 not in outcomes and len(set(outcomes))==1:
                bonus_model=PlinkoPhysics(self._rng)
                bonus_frames,bonus_slot=bonus_model.simulate()
        except RuntimeError as exc:
            self.info_var.set("请下注")
            return
        result = settle_table(self.balance, self.bets, outcomes,
                              bonus_multiplier=bonus_model.multipliers[bonus_slot] if bonus_model else 0,
                              bonus_slot=bonus_slot,bonus_values=bonus_model.multipliers if bonus_model else ())
        try:
            if result.stake:self.store.save(result.final_balance)
        except Exception as exc:
            messagebox.showerror("无法保存账户", f"本轮未开始，当前余额未扣除。\n{exc}", parent=self.root)
            return
        self._bonus_model=bonus_model;self._bonus_frames=bonus_frames
        self._bonus_active=False;self._bonus_done=False;self._bonus_pose=None
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

    def _finish_round(self,force=False):
        if not self.game_active or self._result is None:return
        if self._result.bonus_multiplier and not self._bonus_done and not force:
            if not self._bonus_active:
                self._bonus_active=True;self._bonus_started=time.monotonic()
                self._poses=self._frames[-1]
                self.update_display();self._animate_plinko()
            return
        self._bonus_active=False
        self._cancel_jobs()
        r = self._result
        self.balance = r.final_balance
        self.session_net += r.net
        self.last_win=r.returned if not r.invalid else Decimal(0)
        self.round_count += 1
        self._last_result = r
        self._result = None
        self.game_active = False
        self._poses = self._frames[-1]
        outcome_text=" / ".join("出界" if i<0 else CARDS[i] for i in r.outcomes)
        if r.invalid:
            status="无效";tag="void"
            self.result_var.set(f"本局无效 · 全额退回 {r.stake:,.2f}")
            self.info_var.set("请下注")
        else:
            status="已结算";tag="win" if r.net>=0 else "loss"
            self.result_var.set(f"净赢 {r.net:+,.2f} · 返还 {r.returned:,.2f}")
            self.info_var.set("你赢啦" if r.net>0 else "下局加油")
        try:self.history_store.add(r)
        except (OSError,ValueError) as exc:
            messagebox.showerror("无法保存游戏记录",f"余额已结算，但历史记录保存失败。\n{exc}",parent=self.root)
        self.history=self.history_store.recent()
        self.draw_statistics()
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
        return len(bets)==6 and all(v==0 or minimum<=v<=area_max for v in bets) and (sum(bets)==0 or minimum<=sum(bets)<=total_max)

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

    def _bet_image_source(self,index):
        payout_face=(self._settled and self._last_result and not self._last_result.invalid
                     and self._last_result.outcomes.count(index)
                     and (self._flash_step%2 or not self._flash_active))
        golden=bool(payout_face and index in self._golden_sources)
        return (index,golden),(self._golden_sources if golden else self._card_sources).get(index)

    def draw_history(self):
        c=self.history_canvas;c.delete("all")
        c.create_text(18,36,text="最\n新",font=("Arial",10,"bold"),fill="#2A1B08")
        for row in range(3):
            for col in range(15):
                x=37+col*22
                triple=col<len(self.history) and len(set(self.history[col]))==1 and self.history[col][0] in CARDS
                pair=col<len(self.history) and len(set(self.history[col]))==2 and all(v in CARDS for v in self.history[col]) and self.history[col].count(self.history[col][row])==2
                c.create_rectangle(x,row*24,x+22,row*24+24,fill="#DCEEF8" if triple else ("#FFF2BF" if pair else "white"),outline="black",width=2)
                if col<len(self.history):
                    c.create_text(x+11,row*24+12,text=self.history[col][row],fill=HISTORY_COLORS.get(self.history[col][row],"#555555"),font=("Arial",9,"bold"))

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

    def _animate_plinko(self):
        self._job=None
        if self._closed or not self._bonus_active:return
        elapsed=time.monotonic()-self._bonus_started
        if elapsed<self._bonus_model.launch_duration:
            self._bonus_pose=None
            self.draw_plinko();self._job=self.root.after(16,self._animate_plinko)
            return
        progress=(elapsed-self._bonus_model.launch_duration)/PlinkoPhysics.FRAME_DT
        frame=int(progress)
        if frame>=len(self._bonus_frames)-1:
            self._bonus_pose=self._bonus_frames[-1];self._bonus_done=True
            self.draw_plinko()
            self._job=self.root.after(1200,self._finish_round)
            return
        a,b=self._bonus_frames[frame:frame+2];alpha=progress-frame
        self._bonus_pose=tuple(x+(y-x)*alpha for x,y in zip(a,b))
        self.draw_plinko();self._job=self.root.after(16,self._animate_plinko)

    def draw_plinko(self):
        c=self.canvas;c.delete("all")
        w,h=c.winfo_width(),c.winfo_height()
        scale=min((w-32)/18,(h-100)/20);ox=(w-18*scale)/2;oy=60
        c.create_text(w/2,24,text="BALL DROP · 三球同格奖励",fill="#F2E6C9",font=(Theme.FONT_CJK,18,"bold"))
        c.create_rectangle(ox,oy,ox+18*scale,oy+20*scale,fill="#15332e",outline="#D8B46A",width=2)
        for x,y in self._bonus_model.pegs:
            r=PlinkoPhysics.PEG_RADIUS*scale
            c.create_oval(ox+x*scale-r,oy+y*scale-r,ox+x*scale+r,oy+y*scale+r,fill="#dfdbc6",outline="")
        selected=self._result.bonus_slot if self._bonus_done or (self._bonus_pose and self._bonus_pose[1]>19.7) else -1
        for i,value in enumerate(self._bonus_model.multipliers):
            x=ox+i*scale
            c.create_rectangle(x,oy+19*scale,x+scale,oy+20*scale,fill="#F0C452" if i==selected else "#426658",outline="#D8B46A")
            c.create_text(x+scale/2,oy+19.5*scale,text=str(value),fill="black" if i==selected else "white",font=("Arial",max(7,int(scale*.28)),"bold"))
            if i:c.create_line(x,oy+17*scale,x,oy+20*scale,fill="#D8B46A",width=max(1,.05*scale))
        elapsed=max(0,time.monotonic()-self._bonus_started)
        launch_x=self._bonus_model.launcher_x(elapsed)
        c.create_rectangle(ox+(launch_x-.7)*scale,oy+.3*scale,
                           ox+(launch_x+.7)*scale,oy+.7*scale,
                           fill="#FFDE35",outline="#B8860B",width=2)
        if elapsed>=self._bonus_model.launch_duration:
            x,y=self._bonus_pose or self._bonus_frames[0];r=PlinkoPhysics.RADIUS*scale
            c.create_oval(ox+x*scale-r,oy+y*scale-r,ox+x*scale+r,oy+y*scale+r,fill="#FFDE35",outline="#B8860B")
        if self._bonus_done:
            c.create_text(w/2,h-20,text=f"{self._result.bonus_multiplier} 倍 · 获胜 ${self._result.returned:,.2f}",fill="#F2E6C9",font=(Theme.FONT_CJK,13,"bold"))

    def change_stats_limit(self,event=None):
        choices=(50,100,250,500,1000)
        self.stats_limit=choices[(choices.index(self.stats_limit)+1)%len(choices)]
        self.stats_button.configure(text=f"{self.stats_limit}局的分布")
        self.draw_statistics()

    def chip_for_amount(self,amount):
        return max((c for c in self.chip_configs if money(c[1])<=amount),key=lambda c:money(c[1]),default=self.chip_configs[0])

    def _area_return(self,index):
        r=self._last_result
        hits=r.outcomes.count(index)
        if not hits:return Decimal(0)
        return r.bets[index]*(r.bonus_multiplier if r.bonus_multiplier else 1+PROFIT_ODDS[hits])

    def draw_statistics(self):
        c=self.stats_canvas;c.delete("all")
        values,count=self.history_store.percentages(self.stats_limit)
        for i,(card,value) in enumerate(zip(CARDS,values)):
            x=2+i*62
            c.create_rectangle(x,1,x+62,37,fill="white",outline="black",width=2)
            c.create_line(x,19,x+62,19,fill="black",width=2)
            c.create_text(x+31,9,text=card,font=("Arial",10,"bold"))
            c.create_text(x+31,28,text=f"{value:.1f}%",font=("Arial",10))

    def _begin_chip_return(self):
        self._flash_job=None
        if self._closed:return
        self._return_started=time.monotonic()
        self._return_moves=[]
        for i,bet in enumerate(self.bets):
            if not bet:continue
            if self._last_result and not self._last_result.invalid and not self._last_result.outcomes.count(i):continue
            amount=bet
            if self._last_result and not self._last_result.invalid:
                hits=self._last_result.outcomes.count(i)
                if hits:amount=self._area_return(i)
            chip=self.chip_configs.index(self.chip_for_amount(amount))
            self._return_moves.append((i,amount,chip))
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
        self.bets=[Decimal(0) for _ in CARDS];self._bet_actions.clear();self._chip_moves.clear()
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
        # Host compatibility: stopping reveals and completes an already paid round.
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
        self._restore_window_close()
        self._cancel_jobs()
        if self._result is not None:
            self.balance = self._result.final_balance
            self._result = None
        self.game_active = False
        self._closed = True

    # Perspective plane maps [0,1] x [0,1] onto a trapezoid, far to near.
    @staticmethod
    def project(u, v, z=0):
        return 380 + (u - 0.5) * (504 + 36 * v), 310 + 280 * v - z


    def _viewport(self):
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        # Fit the full visible scene tightly, without cropping the rim or title.
        left,top,right,bottom=32,8,730,694
        scale=min(w/(right-left),h/(bottom-top))
        return scale,(w-(right-left)*scale)/2-left*scale,(h-(bottom-top)*scale)/2-top*scale

    def draw_scene(self):
        if self._closed:
            return
        if self._bonus_active:
            self.draw_plinko()
            return

        c = self.canvas
        c.delete("all")
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

        for index, card in enumerate(CARDS):
            col, row = index % 3, index // 3
            u0, u1 = col / 3 + .009, (col + 1) / 3 - .009
            v0, v1 = row / 2 + .016, (row + 1) / 2 - .016
            is_selected = False
            fill = "#f8edc9" if is_selected else "#e6e9dc"
            outline = "#e7ba5f" if is_selected else "#849d8b"
            quad = [p(u0, v0), p(u1, v0), p(u1, v1), p(u0, v1)]
            poly(quad, fill, outline, 4 if is_selected else 1)
            self._draw_card_asset(index, quad, s, ox, oy)

        rails = [
            ((x / BallPhysics.WIDTH, 0), (x / BallPhysics.WIDTH, 1))
            for x in BallPhysics.RAIL_X
        ]
        rails += [
            ((0, y / BallPhysics.DEPTH), (1, y / BallPhysics.DEPTH))
            for y in BallPhysics.RAIL_Y
        ]
        height = (
            BallPhysics.RAIL_Z + BallPhysics.RAIL_RADIUS
        ) * BallPhysics.HEIGHT_SCALE

        for start, end in rails:
            a, b = p(*start), p(*end)
            at, bt = p(*start, height), p(*end, height)
            poly([a, b, bt, at], "#657269")
            c.create_line(
                *coords([at, bt]),
                fill="#b8b6a2",
                width=max(2, 5 * s)
            )
            c.create_line(
                *coords([
                    (at[0] - 1, at[1] - 1),
                    (bt[0] - 1, bt[1] - 1)
                ]),
                fill="#eee5c6",
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

        # 左上角主标题、副标题
        c.create_text(
            12, oy + 12 * s,
            text="落球游戏",
            anchor="nw",
            fill="#F2E6C9",
            font=(Theme.FONT_CJK, max(16, round(23 * s)), "bold")
        )
        c.create_text(
            12, oy + 46 * s,
            text="Hulog-Bola",
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
            radius = max(5, (504 + 36 * v) * BallPhysics.RADIUS / W)

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

        if self._settled and self._last_result and not self._last_result.invalid:
            for index in set(self._last_result.outcomes):
                hits = self._last_result.outcomes.count(index)
                multiple = (
                    self._last_result.bonus_multiplier
                    if hits == 3 else 1 + PROFIT_ODDS[hits]
                )
                label = f"{multiple}X" if multiple else "--X"
                x, y = p((index % 3 + .5) / 3, (index // 3 + .5) / 2)
                x = ox + x * s
                y = oy + y * s
                font = ("Arial", max(14, round(26 * s)), "bold")
                for dx, dy in (
                    (-2, -2), (-2, 0), (-2, 2),
                    (0, -2), (0, 2),
                    (2, -2), (2, 0), (2, 2)
                ):
                    c.create_text(
                        x + dx, y + dy,
                        text=label, fill="black", font=font
                    )
                c.create_text(
                    x, y,
                    text=label, fill="#FFE135", font=font
                )


DropBallGame = RedPacketRainGame


class EmbeddedGamePage(tk.Frame):
    """A real page for casino_games.main(parent=...) and replace_page()."""

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
        # Cancel callbacks before Tk destroys their page-local command objects.
        if self.game is not None:
            self.game._cancel_jobs()
        super().destroy()


def main(initial_balance=1000.0, username='Guest', *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None, demo=False):
    """
    Parent 嵌入接口：
        main(parent=..., balance=..., user=..., on_back=..., on_balance_change=...)

    未传 parent 时仍可独立运行。
    """
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        store = AccountStore(actual_user, demo)
        return EmbeddedGamePage(
            parent, actual_balance, actual_user, demo=demo, store=store,
            on_back=on_back, on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title('乒乓落球')
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
    parser = argparse.ArgumentParser(description="乒乓落球")
    parser.add_argument("--demo", action="store_true", help="虚拟积分演示，不读写账户")
    parser.add_argument("--balance", default="10000", help="演示初始积分")
    args = parser.parse_args()
    try:
        final_balance = main(money(args.balance), "test_user", demo=args.demo)
        print(f"Final balance: {final_balance:.2f}")
    except (RuntimeError, ValueError, tk.TclError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)