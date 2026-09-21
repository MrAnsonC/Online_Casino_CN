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
import threading
import queue
import tkinter as tk
from tkinter import messagebox, simpledialog
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from dataclasses import dataclass

VERSION = "ColorGame-ScreenTray-R10"

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


COLOR_NAMES = ("红", "蓝", "黄", "绿", "白", "粉")
# Display order only; keep stored outcome and betting indices unchanged.
HISTORY_ORDER = (0, 2, 1, 4, 3, 5)
HISTORY_RANK = {index: rank for rank, index in enumerate(HISTORY_ORDER)}
SUITS = ("♠", "♣", "♥", "♥", "♦", "♣")
PROFIT_ODDS = (0, 1, 2, 3)
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
    bonus_points: tuple = ()


def bonus_multiplier(points):
    # Existing rule: up to three valid point rolls; three triples double the sum.
    groups=[points[i:i+3] for i in range(0,len(points),3)]
    return sum(points)*(2 if len(groups)==3 and all(len(set(g))==1 for g in groups) else 1)


def settle_table(balance,bets,outcomes,bonus_points=()):
    balance=money(balance);bets=tuple(money(v) for v in bets);outcomes=tuple(outcomes)
    if len(bets)!=6 or len(outcomes)!=3 or any(i not in range(-1,6) for i in outcomes):
        raise ValueError("下注区域或骰子数量无效")
    stake=sum(bets,Decimal(0))
    if not 0<=stake<=balance:raise ValueError("总下注不能超过余额")
    invalid=-1 in outcomes
    returned=stake if invalid else sum((bet*(1+PROFIT_ODDS[outcomes.count(i)])
                 for i,bet in enumerate(bets) if outcomes.count(i)),Decimal(0))
    bonus_points=tuple(bonus_points)
    if not invalid and len(set(outcomes))==1:
        if len(bonus_points) not in (3,6,9) or any(type(n) is not int or n not in range(1,7) for n in bonus_points):
            raise ValueError("三颗同色必须完成三颗点数骰子结算")
        groups=[bonus_points[i:i+3] for i in range(0,len(bonus_points),3)]
        if any(len(set(g))!=1 for g in groups[:-1]) or (len(groups)<3 and len(set(groups[-1]))==1):
            raise ValueError("点数豹子必须继续掷骰，最多三次")
        returned=bets[outcomes[0]]*bonus_multiplier(bonus_points)
    elif bonus_points:raise ValueError("点数骰子只用于三颗同色")
    return TableResult(bets,stake,outcomes,returned,returned-stake,balance-stake+returned,invalid,bonus_points)


def vadd(a,b):return tuple(x+y for x,y in zip(a,b))
def vmul(a,s):return tuple(x*s for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def norm(a):return math.sqrt(dot(a,a))
def unit(a):return vmul(a,1/max(1e-12,norm(a)))
def qmul(a,b):
    w,x,y,z=a;v,i,j,k=b
    return (w*v-x*i-y*j-z*k,w*i+x*v+y*k-z*j,w*j-x*k+y*v+z*i,w*k+x*j-y*i+z*v)
def rotate(q,p):return qmul(qmul(q,(0,)+tuple(p)),(q[0],-q[1],-q[2],-q[3]))[1:]

DICE_NORMALS=((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
DICE_VERTICES=tuple((x,y,z) for x in (-1,1) for y in (-1,1) for z in (-1,1))
DICE_FACES=((4,6,7,5),(0,1,3,2),(2,3,7,6),(0,4,5,1),(1,5,7,3),(0,2,6,4))

DICE_POINTS=(1,6,2,5,3,4)  # Opposite faces sum to seven.
PIP_LAYOUT={1:((0,0),),2:((-.45,-.45),(.45,.45)),
            3:((-.45,-.45),(0,0),(.45,.45)),
            4:((-.45,-.45),(-.45,.45),(.45,-.45),(.45,.45)),
            5:((-.45,-.45),(-.45,.45),(0,0),(.45,-.45),(.45,.45)),
            6:tuple((x,y) for x in (-.45,.45) for y in (-.45,0,.45))}

def top_quaternion(face,yaw):
    n=DICE_NORMALS[face];z=(0,0,1)
    q=(0,1,0,0) if dot(n,z)<-.999 else unit((1+dot(n,z),)+cross(n,z))
    return qmul((math.cos(yaw/2),0,0,math.sin(yaw/2)),q)

def result_multiplier(result,index):
    hits=result.outcomes.count(index)
    return bonus_multiplier(result.bonus_points) if hits==3 and result.bonus_points else (1+hits if hits else 0)

@dataclass
class ColorDie:
    p: tuple
    v: tuple
    q: tuple
    w: tuple

class DicePhysics:
    """Self-contained cube contact solver; rendering uses the same geometry."""
    TOP_UPRIGHT_MIN=.98  # About 11 degrees of tolerance for settling jitter.
    SIZE=.30
    HALF=SIZE/2
    ROUNDING=.018
    MASS=.008
    SIDE_BUMPS=tuple(1.04+.32*i for i in range(9))
    TOOTH_REACH,TOOTH_HALF,TOOTH_HEIGHT=.20,.14,.25
    WIDTH,DEPTH=2.4,5.6
    TRAY_Y,TRAY_RADIUS=4.4,1.5
    RAMP_END,SLOPE=3.8,.85
    BUMPS=(1.05,1.85,2.65,3.45)
    BUMP_RADIUS=.075
    GATE_Y,GATE_HEIGHT=.72,.12
    GATE_DELAY,GATE_RAISE=.18,.65
    DT,FRAME_DT=1/240,1/60
    def __init__(self,rng=None,top_colors=(0,1,2)):
        rng=rng or random.SystemRandom();self.dice=[]
        for i,face in enumerate(top_colors):
            q=top_quaternion(face,rng.uniform(0,math.tau))
            x=.4+.8*i+rng.uniform(-.025,.025);y=.34+rng.uniform(-.025,.025)
            offsets=[rotate(q,vmul(v,self.HALF-self.ROUNDING)) for v in DICE_VERTICES]
            z=max(self.height(y+v[1])-v[2] for v in offsets)+self.ROUNDING
            self.dice.append(ColorDie((x,y,z),(0,0,0),q,(0,0,0)))
        self.initial=self.poses()
    @classmethod
    def height(cls,y):return max(0,(cls.RAMP_END-max(cls.GATE_Y,y))*cls.SLOPE)
    @classmethod
    def gate_lift(cls,elapsed,return_at=None):
        lift=.50*max(0,min(1,(elapsed-cls.GATE_DELAY)/cls.GATE_RAISE))
        if return_at is not None:lift*=max(0.,1-(elapsed-return_at)/.45)
        return lift
    @classmethod
    def gate_return_time(cls,frames):
        for i,frame in enumerate(frames):
            if all(p[1]-cls.HALF*math.sqrt(3)>cls.GATE_Y+.08 for p in frame):return i*cls.FRAME_DT
        return None
    @classmethod
    def vertices(cls,d):return [vadd(d.p,rotate(d.q,vmul(v,cls.HALF))) for v in DICE_VERTICES]
    @staticmethod
    def top(d):return max(range(6),key=lambda i:rotate(d.q,DICE_NORMALS[i])[2])
    def poses(self):return tuple(d.p+d.q for d in self.dice)
    @staticmethod
    def _impulse(d, r, impulse):
        d.v=vadd(d.v,vmul(impulse,1/DicePhysics.MASS))
        d.w=vadd(d.w,vmul(cross(r,impulse),6/(DicePhysics.MASS*DicePhysics.SIZE**2)))

    def _contacts(self, elapsed):
        contacts=[]
        for d in self.dice:
            vertices=[vadd(d.p,rotate(d.q,vmul(v,self.HALF-self.ROUNDING))) for v in DICE_VERTICES]
            for p in vertices:
                y=p[1];h=self.height(y);slope=-self.SLOPE if self.GATE_Y<y<self.RAMP_END else 0.
                if y<self.GATE_Y:
                    tilt=1.12*min(1.,self.gate_lift(elapsed,getattr(self,"_gate_return_at",None))/.5)
                    h+=(self.GATE_Y-y)*tilt;slope=-tilt
                for seam in self.BUMPS:
                    delta=y-seam;radius=self.BUMP_RADIUS*2
                    if abs(delta)<radius:
                        h+=self.BUMP_RADIUS*(1+math.cos(math.pi*delta/radius))/2
                        slope-=self.BUMP_RADIUS*.5*math.pi/radius*math.sin(math.pi*delta/radius)
                n=unit((0,-slope,1));depth=(h-p[2])*n[2]+self.ROUNDING
                contact=vadd(p,vmul(n,-self.ROUNDING))
                if depth>-.001:contacts.append([d,None,vadd(contact,vmul(d.p,-1)),(0,0,0),n,depth,0.,(0,0,0)])
            planes=[((1,0,0),0),((-1,0,0),-self.WIDTH),((0,1,0),0),((0,-1,0),-self.DEPTH)]
            if elapsed<self.GATE_DELAY+self.GATE_RAISE and d.p[1]<self.GATE_Y:
                gate_bottom=self.height(self.GATE_Y)+self.gate_lift(elapsed,getattr(self,"_gate_return_at",None))
                if max(p[2] for p in vertices)>gate_bottom:
                    planes.append(((0,-1,0),-self.GATE_Y))
            for n,offset in planes:
                for p in vertices:
                    depth=offset-dot(p,n)+self.ROUNDING
                    contact=vadd(p,vmul(n,-self.ROUNDING))
                    if depth>-.001:
                        contacts.append([d,None,vadd(contact,vmul(d.p,-1)),(0,0,0),n,depth,0.,(0,0,0)])
            for p in vertices:
                if p[1]<=self.RAMP_END:continue
                radial=(p[0]-self.WIDTH/2,p[1]-self.TRAY_Y,0)
                depth=norm(radial)+self.ROUNDING-self.TRAY_RADIUS
                if depth>-.001:
                    n=vmul(unit(radial),-1);contact=vadd(p,vmul(n,-self.ROUNDING))
                    contacts.append([d,None,vadd(contact,vmul(d.p,-1)),(0,0,0),n,depth,0.,(0,0,0)])
            side_samples=vertices+[vadd(d.p,rotate(d.q,vmul(v,self.HALF-self.ROUNDING)))
                for v in DICE_NORMALS+tuple((x,y,z) for x in (-1,0,1) for y in (-1,0,1) for z in (-1,0,1) if abs(x)+abs(y)+abs(z)==2)]
            for side in (0,self.WIDTH):
                sign=1 if side==0 else -1
                for y in self.SIDE_BUMPS:
                    for p in side_samples:
                        dy=p[1]-y
                        if abs(dy)>self.TOOTH_HALF:continue
                        reach=self.TOOTH_REACH*(1-abs(dy)/self.TOOTH_HALF)
                        derivative=-self.TOOTH_REACH/self.TOOTH_HALF*(1 if dy>=0 else -1)
                        n=unit((sign,-derivative,0))
                        depth=(reach-sign*(p[0]-side))*abs(n[0])+self.ROUNDING
                        if depth>0 and p[2]<self.height(p[1])+self.TOOTH_HEIGHT:
                            contact=vadd(p,vmul(n,-self.ROUNDING))
                            contacts.append([d,None,vadd(contact,vmul(d.p,-1)),(0,0,0),n,depth,0.,(0,0,0)])
        for i,a in enumerate(self.dice):
            for b in self.dice[i+1:]:
                delta=vadd(a.p,vmul(b.p,-1))
                if norm(delta)>self.SIZE*math.sqrt(3):continue
                aa=[rotate(a.q,n) for n in ((1,0,0),(0,1,0),(0,0,1))]
                bb=[rotate(b.q,n) for n in ((1,0,0),(0,1,0),(0,0,1))]
                axes=aa+bb+[unit(cross(x,y)) for x in aa for y in bb if norm(cross(x,y))>1e-6]
                best=None
                for n in axes:
                    radius=(self.HALF-self.ROUNDING)*sum(abs(dot(n,x)) for x in aa+bb)+2*self.ROUNDING
                    overlap=radius-abs(dot(delta,n))
                    if overlap<0:best=None;break
                    if best is None or overlap<best[0]:best=(overlap,n if dot(delta,n)>=0 else vmul(n,-1))
                if best:
                    depth,n=best
                    va=[vadd(vadd(a.p,rotate(a.q,vmul(v,self.HALF-self.ROUNDING))),vmul(n,-self.ROUNDING)) for v in DICE_VERTICES]
                    vb=[vadd(vadd(b.p,rotate(b.q,vmul(v,self.HALF-self.ROUNDING))),vmul(n,self.ROUNDING)) for v in DICE_VERTICES]
                    low=min(dot(p,n) for p in va);high=max(dot(p,n) for p in vb)
                    pa=[p for p in va if dot(p,n)<low+.002];pb=[p for p in vb if dot(p,n)>high-.002]
                    ca=tuple(sum(p[k] for p in pa)/len(pa) for k in range(3))
                    cb=tuple(sum(p[k] for p in pb)/len(pb) for k in range(3))
                    point=vmul(vadd(ca,cb),.5)
                    contacts.append([a,b,vadd(point,vmul(a.p,-1)),vadd(point,vmul(b.p,-1)),n,depth,0.,(0,0,0)])
        return contacts

    def _solve(self, contacts):
        inverse_mass=1/self.MASS
        inertia=6/(self.MASS*self.SIZE**2)
        targets=[]
        for a,b,ra,rb,n,depth,_,__ in contacts:
            speed=dot(vadd(a.v,cross(a.w,ra)),n)
            if b:speed-=dot(vadd(b.v,cross(b.w,rb)),n)
            targets.append(max(0.,min(.5,.16*max(0.,depth-.0005)/self.DT),-.25*speed if speed<-.5 else 0.))
        for _ in range(10):
            for c,target in zip(contacts,targets):
                a,b,ra,rb,n,depth,accum,friction=c
                relative=vadd(a.v,cross(a.w,ra))
                if b:relative=vadd(relative,vmul(vadd(b.v,cross(b.w,rb)),-1))
                k=inverse_mass+inertia*dot(cross(ra,n),cross(ra,n))
                if b:k+=inverse_mass+inertia*dot(cross(rb,n),cross(rb,n))
                new=max(0.,accum+(target-dot(relative,n))/k);j=new-accum;c[6]=new
                impulse=vmul(n,j);self._impulse(a,ra,impulse)
                if b:self._impulse(b,rb,vmul(impulse,-1))
                relative=vadd(a.v,cross(a.w,ra))
                if b:relative=vadd(relative,vmul(vadd(b.v,cross(b.w,rb)),-1))
                tangent=vadd(relative,vmul(n,-dot(relative,n)));speed=norm(tangent)
                if speed<1e-10:continue
                t=vmul(tangent,1/speed)
                kt=inverse_mass+inertia*dot(cross(ra,t),cross(ra,t))
                if b:kt+=inverse_mass+inertia*dot(cross(rb,t),cross(rb,t))
                candidate=vadd(friction,vmul(t,-speed/kt));limit=(.06 if abs(n[2])<.1 else (.65 if a.p[1]<self.RAMP_END else .34))*new
                if norm(candidate)>limit:candidate=vmul(unit(candidate),limit)
                change=vadd(candidate,vmul(friction,-1));c[7]=candidate
                self._impulse(a,ra,change)
                if b:self._impulse(b,rb,vmul(change,-1))

    def simulate(self):
        self.dice=[ColorDie(p[:3],(0,0,0),p[3:],(0,0,0)) for p in self.initial]
        frames=[self.initial];quiet=0;self._gate_return_at=None
        for tick in range(round(20/self.DT)):
            for d in self.dice:
                d.v=vadd(vmul(d.v,math.exp(-.025*self.DT)),(0,0,-9.81*self.DT))
                d.w=vmul(d.w,math.exp(-.04*self.DT))
            if self._gate_return_at is None and all(d.p[1]-self.HALF*math.sqrt(3)>self.GATE_Y+.08 for d in self.dice):
                self._gate_return_at=(tick+1)*self.DT
            self._solve(self._contacts((tick+1)*self.DT))
            for d in self.dice:
                d.p=vadd(d.p,vmul(d.v,self.DT))
                dq=qmul((0,)+d.w,d.q)
                d.q=unit(tuple(q+.5*self.DT*v for q,v in zip(d.q,dq)))
                if not all(math.isfinite(v) for v in d.p+d.q+d.v+d.w) or d.p[2]<-.5:
                    raise RuntimeError("骰子模拟异常，本轮未扣款。")
            if (tick+1)%4==0:frames.append(self.poses())
            stopped=all(d.p[1]>self.RAMP_END-self.HALF and norm(d.v)<.035 and norm(d.w)<.12 for d in self.dice)
            quiet=quiet+1 if stopped else 0
            if quiet>=round(.35/self.DT):
                frames.append(self.poses())
                order=sorted(range(len(self.dice)),key=lambda i:self.dice[i].p[0])
                outcomes=tuple(self.top(self.dice[i]) for i in order)
                cocked=any(rotate(self.dice[i].q,DICE_NORMALS[self.top(self.dice[i])])[2]<self.TOP_UPRIGHT_MIN
                           for i in range(len(self.dice)))
                return frames,outcomes,cocked
        raise RuntimeError("骰子未完全停稳，本轮未扣款；请重新开始。")


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


class ColorHistory:
    """Color Game log, separate from the former card game."""
    def __init__(self, path=None):
        self.path=Path(path) if path else None
        self.data={"Total":0,"Record1":{},"Record2":{}}
        if self.path and self.path.exists():
            with open(str(self.path),encoding="utf-8") as f:data=json.load(f)
            if not isinstance(data,dict) or not isinstance(data.get("Record2"),dict):
                raise ValueError("Color Game 历史记录格式错误")
            self.data=data

    def entries(self):
        return sorted(self.data["Record2"].values(),key=lambda e:e["round"],reverse=True)

    def add(self,result):
        if result.invalid:return  # Invalid/cocked rounds never enter the JSON log.
        number=self.data["Total"]+1
        entry={"round":number,"outcomes":list(result.outcomes),"invalid":result.invalid,
               "bets":[str(v) for v in result.bets],"returned":str(result.returned),"net":str(result.net),"bonus_points":list(result.bonus_points)}
        recent=([entry]+self.entries())[:1000]
        data={"Total":number,"Record1":{f"{e['round']}_Data":e for e in recent[:15]},
              "Record2":{f"{e['round']}_Data":e for e in recent}}
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with open(str(self.path),"w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False,indent=4)
        self.data=data

    def recent(self):
        return [tuple("出界" if i<0 else COLOR_NAMES[i] for i in sorted(e["outcomes"],key=lambda i:HISTORY_RANK.get(i,6)))
                for e in self.entries()[:15]]

    def latest_points(self):
        for entry in self.entries():
            points=entry.get("bonus_points",[])
            if len(points) in (3,6,9) and all(type(n) is int and 1<=n<=6 for n in points):return tuple(points[-3:])
        return (1,3,5)

    def percentages(self,limit=50):
        entries=[e for e in self.entries()[:limit] if not e["invalid"]]
        dice=[i for e in entries for i in e["outcomes"] if i in range(6)]
        return [100*dice.count(i)/len(dice) if dice else 0 for i in range(6)],len(entries)


COLOR_HEX=("#E34B4F","#347BD1","#F4D747","#32A36A","#FFFFFF","#E987BB")
HISTORY_COLORS={name: COLOR_HEX[i] for i, name in enumerate(COLOR_NAMES)}
HISTORY_TEXT={name:("black" if name in ("黄","白","粉") else "white") for name in COLOR_NAMES}


def _darken(color, amount=0.45):
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    r = int(r * (1 - amount))
    g = int(g * (1 - amount))
    b = int(b * (1 - amount))
    return f"#{r:02x}{g:02x}{b:02x}"


def _lighten(color, amount=0.55):
    if color == "#FFFFFF":
        return "#F4F2E9"
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


class ColorGame:
    """Color Game; original host class name retained for integration."""
    WINDOW_WIDTH, WINDOW_HEIGHT = 1150, 750

    def __init__(self, root, initial_balance, username, *, demo=False, store=None,
                 manage_window=True):
        self.root, self.username = root, username
        self.balance = money(initial_balance)
        self.store = store if store is not None else AccountStore(username, demo)
        self.demo = demo
        self.bet_per_draw = Decimal("0.00")
        self.selected = None
        self.bets = [Decimal("0.00") for _ in COLOR_NAMES]
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
        self._cocked_display=False
        self._point_cocked_idx=set()
        self._show_cocked_overlay=False
        account_path=getattr(self.store,"path",None)
        log_path=Path(account_path).parents[2]/"A_Logs/Json/Color_Game.json" if account_path and not demo else None
        self.history_store=ColorHistory(log_path)
        self.history=self.history_store.recent()
        self._return_moves=[]
        self._return_started=None
        self._next_tops=tuple(self.history_store.entries()[0]["outcomes"]) if self.history_store.entries() else (0,1,2)
        if len(self._next_tops)!=3 or any(i not in range(6) for i in self._next_tops):self._next_tops=(0,1,2)
        self._point_frames=[];self._dice_kind="color";self._gate_elapsed=0.
        self._ready_model=DicePhysics(self._rng,self._next_tops)
        self._point_ready=DicePhysics(self._rng,tuple(DICE_POINTS.index(n) for n in self.history_store.latest_points())).initial
        self._side_points=[self._parking_pose(i,v) for i,v in enumerate(self._point_ready)]
        self._extra_dice=[]
        self._ready_poses=self._ready_model.poses()
        self._last_bets = None
        self._bet_draw_refs = []
        self.root.configure(bg=Theme.APP_BG)
        # Embedded pages leave the shared root close protocol to the host.
        self._close_command = None
        if manage_window:
            if isinstance(root, (tk.Tk, tk.Toplevel)):
                root.title("颜色游戏")
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
        dialog.title("Color Game · 游戏说明");dialog.resizable(False,False);dialog.transient(parent)
        bg,header,panel,border,gold,text,muted="#0f1311","#151b18","#18201c","#43534a","#e7d36c","#f4f4ee","#c1cbc6"
        font=Theme.FONT_CJK;dialog.configure(bg=bg)
        x=parent.winfo_rootx()+(parent.winfo_width()-1000)//2
        y=parent.winfo_rooty()+(parent.winfo_height()-650)//2
        dialog.geometry(f"1000x650+{max(0,x)}+{max(0,y)}")
        head=tk.Frame(dialog,bg=header,height=82);head.pack(fill="x");head.pack_propagate(False)
        tk.Label(head,text="COLOR GAME · 六色彩骰",font=(font,20,"bold"),fg=gold,bg=header).place(x=24,y=10)
        tk.Label(head,text="六色下注 · 斜坡掷骰 · 派奖 · 记录",font=(font,14),fg=muted,bg=header).place(x=25,y=48)
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
        box=card("01  六色下注")
        rule(box,"选择筹码 → 点击颜色 → 开始游戏","可以多区下注，也可以零下注试玩。重复上局下注会恢复最近一次有下注的金额。")
        box=card("02  派奖（含本金）")
        for i,(condition,value) in enumerate((("1 颗同色","该颜色下注 × 2"),("2 颗同色","该颜色下注 × 3"),("3 颗同色","三颗点数相加 × 该颜色下注"),("没有命中","不返还"))):
            row=tk.Frame(box,bg="#202923" if i%2 else "#1b241f");row.pack(fill="x",padx=18,pady=1)
            tk.Label(row,text=condition,font=(font,14),fg=text,bg=row.cget("bg"),padx=12,pady=7).pack(side="left")
            tk.Label(row,text=value,font=(font,14,"bold"),fg=gold,bg=row.cget("bg"),padx=12).pack(side="right")
        box=card("03  大斜坡 · 彩骰示意")
        diagram=tk.Canvas(box,width=920,height=440,bg=panel,highlightthickness=0)
        diagram.pack(fill="x",padx=18,pady=(0,12));self._draw_color_guide(diagram)
        rule(box,"三颗骰子全部停稳后结算","以每颗骰子朝上的颜色为准。三颗同色时彩骰左移，再投三颗点数骰；点数之和是含本金返还倍数。")
        box=card("04  最近记录与分布")
        rule(box,"颜色记录与分布","彩色背景、白色文字表示骰子结果；白色、黄色与粉色用黑字显示。点击分布标题切换统计局数。")

    @staticmethod
    def _draw_color_guide(c):
        def project(x,y,z):return 190+(x-1.2)*(55+8*y),135+40*y-30*z
        def poly(points,fill):
            c.create_polygon(*[v for point in points for v in project(*point)],fill=fill,outline="#d8b46a",width=2)
        top=DicePhysics.height(0)
        poly([(0,0,top),(2.4,0,top),(2.4,3.8,0),(0,3.8,0)],"#AA653F")
        poly([(0,3.8,0),(2.4,3.8,0),(2.4,5.1,0),(0,5.1,0)],"#A86A45")
        for i in range(3):
            y=1+i*1.4
            q=unit((1,.15*i,.2,.1))
            ColorGame._draw_cube(c,(.4+i*.8,y,DicePhysics.height(y)+.3)+q,project)
        for y,title,body in ((60,"① 三颗六色骰子","右侧拉绳升起挡栏，起始台倾斜释放骰子。"),
                             (175,"② 滚入底部区域","骰子会与斜坡、边框及其他骰子碰撞。"),
                             (290,"③ 看朝上的颜色","一颗同色返还 2X，两颗返还 3X。")):
            c.create_text(410,y,text=title,anchor="nw",fill="#e7d36c",font=(Theme.FONT_CJK,16,"bold"))
            c.create_text(410,y+35,text=body,anchor="nw",width=465,fill="#c1cbc6",font=(Theme.FONT_CJK,14))
        for i,color in enumerate(COLOR_HEX):
            x=30+i*53
            c.create_rectangle(x,378,x+46,410,fill=color,outline="#e7d36c")
            c.create_text(x+23,394,text=COLOR_NAMES[i],fill="#18201c",font=(Theme.FONT_CJK,12,"bold"))

    def update_display(self):
        self.bet_per_draw=sum(self.bets,Decimal(0))
        self.balance_var.set(f"余额: ${self.balance:,.2f}")
        self.stage_var.set("掷骰中" if self.game_active else ("已结算" if self._settled else "下注中"))
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
        settled = self._settled and self._last_result is not None
        invalid = settled and self._last_result.invalid
        for column,i in enumerate(HISTORY_ORDER):
            x=2+column*62;y=63
            base_color = COLOR_HEX[i]
            outline_color = "#162d24"
            text_color = "black" if i in (2,4,5) else "white"
            if settled and not invalid:
                hit = i in self._last_result.outcomes
                # Keep the result styling through chip return and dice return.
                if hit:
                    if self._flash_active:
                        dark_phase = self._flash_step % 2 == 1
                        fill_color = _darken(base_color, .55) if dark_phase else _lighten(base_color, .60)
                        text_color = "white" if dark_phase else "black"
                    else:
                        fill_color = base_color
                else:
                    fill_color = _darken(base_color, .68)
                    outline_color = "#26352F"
                    text_color = "#D1D5D3"
            else:
                fill_color = base_color
            c.create_rectangle(x,y,x+58,y+86,fill=fill_color,outline=outline_color,width=2)
            c.create_text(x+29,y+12,text=COLOR_NAMES[i],fill=text_color,font=(Theme.FONT_CJK,11,"bold"))
            pending=sum((move[2] for move in self._chip_moves if move[1]==i),Decimal(0))
            visible=Decimal(0) if self._return_started is not None else max(Decimal(0),self.bets[i]-pending)
            lost=(settled and not invalid and i not in self._last_result.outcomes)
            if lost:visible=Decimal(0)
            if visible:
                shown=visible
                if settled and not invalid and self._last_result.outcomes.count(i):
                    if self._flash_step%2 or not self._flash_active:shown=self._area_return(i)
                config=self.chip_for_amount(shown)
                c.create_oval(x+10,y+24,x+48,y+62,fill=config[2],outline="#d4af37",width=2)
                c.create_text(x+29,y+43,text=chip_amount_text(shown),fill=config[3],font=("Arial",9,"bold"))
            if settled and not invalid:
                # Show the same return multiplier used by settlement.
                if hit:
                    c.create_text(x+29,y+73,text=f"{result_multiplier(self._last_result,i)}X",
                                  fill=text_color,font=("Arial",10,"bold"))
        now=time.monotonic()
        for started,index,amount,chip in self._chip_moves:
            t=min(1,(now-started)/.32);ease=1-(1-t)**3
            sx,sy=31+chip*62,27;tx=31+HISTORY_RANK[index]*62;ty=106
            x=sx+(tx-sx)*ease;y=sy+(ty-sy)*ease
            color,fg=self.chip_for_amount(amount)[2:]
            c.create_oval(x-19,y-19,x+19,y+19,fill=color,outline="#d4af37",width=2)
            c.create_text(x,y,text=chip_amount_text(amount),fill=fg,font=("Arial",9,"bold"))

        if self._return_started is not None:
            t=min(1,(now-self._return_started)/.4);ease=1-(1-t)**3
            for index,amount,chip in self._return_moves:
                column=HISTORY_RANK[index]
                x=(31+column*62)+(chip-column)*62*ease;y=106-79*ease
                color,fg=self.chip_for_amount(amount)[2:]
                c.create_oval(x-19,y-19,x+19,y+19,fill=color,outline="#d4af37",width=2)
                c.create_text(x,y,text=chip_amount_text(amount),fill=fg,font=("Arial",9,"bold"))

    def _bet_click(self,event):
        if self.game_active or self._closed or self._settled:return
        self.bet_canvas.focus_set()
        for i in range(len(self.chip_configs)):
            if math.hypot(event.x-(31+i*62),event.y-27)<=25:
                self.selected_chip=i;self.draw_betting();return
        for column,i in enumerate(HISTORY_ORDER):
            x=2+column*62;y=63
            if x<=event.x<=x+58 and y<=event.y<=y+86:self.place_bet(i);return

    def _bet_clear_click(self,event):
        if self.game_active or self._closed or self._settled:return
        for column,i in enumerate(HISTORY_ORDER):
            x=2+column*62;y=63
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
        if event.char in "123456" and event.char:self.place_bet(HISTORY_ORDER[int(event.char)-1])
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
        self._chip_moves.clear();self._bet_actions.clear();self.bets=[Decimal(0) for _ in COLOR_NAMES]
        self.update_display();self.draw_scene()

    def start_game(self):
        if self.game_active or self._closed or self._settled:
            return
        if self._chip_moves:return
        self.bet_per_draw=sum(self.bets,Decimal(0))
        if not self.valid_bets(self.bets) or self.bet_per_draw>self.balance:
            self.info_var.set("余额不足" if self.bet_per_draw>self.balance else "请下注")
            return
        self.game_active=True
        self.info_var.set("游戏进行中，请稍等")
        self.update_display()
        pending=queue.Queue(maxsize=1)
        model=self._ready_model

        def compute():
            try:
                frames,outcomes,cocked=model.simulate()
                if cocked:
                    pending.put((None,(frames,outcomes,[],(),'color_cocked',set(),[])))
                    return
                point_frames=[];point_cocked_idx=set();point_timeline=[]
                bonus_points=()
                if len(set(outcomes))==1:
                    point_frames,bonus_points,point_cocked_idx,point_timeline=self._simulate_point_rolls()
                pending.put((None,(frames,outcomes,point_frames,bonus_points,'ok',point_cocked_idx,point_timeline)))
            except Exception as exc:
                pending.put((exc,None))
        threading.Thread(target=compute,daemon=True).start()
        self._job=self.root.after(30,lambda:self._poll_simulation(pending))

    def _simulate_point_rolls(self):
        frames=[];points=[];cocked_indices=set();timeline=[]
        total=0
        def append(poses,shown,clock=0.,gate=None,cocked=False):
            if cocked:cocked_indices.add(len(frames))
            frames.append(poses);timeline.append((shown,clock,gate))
        for attempt in range(3):
            while True:
                if self._closed:raise RuntimeError("窗口已关闭")
                ready_faces=tuple(max(range(6),key=lambda i:rotate(pose[3:],DICE_NORMALS[i])[2])
                                  for pose in self._point_ready)
                # Fresh yaw/positions are essential: identical initial poses replay the same physics.
                model=DicePhysics(random.SystemRandom(),ready_faces)
                pf,faces,cocked=model.simulate()
                if frames:
                    source=frames[-1]
                    for step in range(1,49):
                        append(self._move_poses(source,pf[0],step/48),total)
                gate=DicePhysics.gate_return_time(pf)
                for index,poses in enumerate(pf):
                    append(poses,total,index*DicePhysics.FRAME_DT,gate,
                           cocked and index==len(pf)-1)
                if cocked:
                    # Show the stopped, tilted dice and overlay before returning for a retry.
                    for _ in range(72):append(pf[-1],total,cocked=True)
                    continue
                values=tuple(DICE_POINTS[i] for i in faces)
                points.extend(values);total=sum(points)
                if len(set(values))!=1 or attempt==2:
                    return frames,tuple(points),cocked_indices,timeline
                for _ in range(48):append(pf[-1],total)
                break

    def _poll_simulation(self,pending):
        self._job=None
        if self._closed:return
        try:error,payload=pending.get_nowait()
        except queue.Empty:
            self._job=self.root.after(30,lambda:self._poll_simulation(pending));return
        if error is not None:
            self.game_active=False
            messagebox.showerror("本轮未开始",str(error),parent=self.root)
            self.info_var.set("请下注");self.update_display();return
        frames,outcomes,point_frames,bonus_points,status,point_cocked_idx,point_timeline=payload
        color_cocked=status=='color_cocked'
        result=settle_table(self.balance,self.bets,(-1,-1,-1) if color_cocked else outcomes,bonus_points)
        try:
            if result.stake and not result.invalid:self.store.save(result.final_balance)
        except Exception as exc:
            self.game_active=False
            self.info_var.set("请下注");self.update_display()
            messagebox.showerror("无法保存账户",f"本轮未开始，当前余额未扣除。\n{exc}",parent=self.root)
            return
        self._new_ticket=False
        if sum(self.bets)>0:self._last_bets=tuple(self.bets)
        self._result=result
        self._last_result=None
        self.game_active=True
        self.balance-=result.stake
        self._parked_poses=[];self._extra_dice=[]
        self._color_gate_return=DicePhysics.gate_return_time(frames)
        self._point_gate_return=DicePhysics.gate_return_time(point_frames) if point_frames else None
        self._frames=frames
        self._point_frames=point_frames;self._dice_kind="color";self._gate_elapsed=0.
        self._started_at=time.monotonic()
        self._cocked_display=color_cocked
        self._point_timeline=point_timeline
        self._display_point_total=0
        self._point_cocked_idx=point_cocked_idx
        self._show_cocked_overlay=False
        self.result_var.set("三颗骰子滚动中…\n等待全部停稳")
        self.info_var.set("游戏进行中，请稍等")
        self.update_display()
        self._animate()

    @staticmethod
    def _parking_pose(index,pose):
        offsets=[rotate(pose[3:],vmul(v,DicePhysics.HALF-DicePhysics.ROUNDING)) for v in DICE_VERTICES]
        return (-.72,3.05+index*.62,DicePhysics.ROUNDING-min(v[2] for v in offsets))+pose[3:]

    @staticmethod
    def _move_poses(source,target,t):
        t=max(0.,min(1.,t));e=t*t*(3-2*t);poses=[]
        for a,b in zip(source,target):
            sign=1 if dot(a[3:],b[3:])>=0 else -1
            q=unit(tuple(a[k]+(sign*b[k]-a[k])*e for k in range(3,7)))
            xyz=tuple(a[k]+(b[k]-a[k])*e for k in range(3))
            poses.append((xyz[0],xyz[1],xyz[2]+.65*math.sin(math.pi*t))+q)
        return poses

    def _animate(self):
        self._job=None
        if not self.game_active or self._closed:
            return
        elapsed=time.monotonic()-self._started_at
        duration=(len(self._frames)-1)*DicePhysics.FRAME_DT
        frames=self._frames;clock=elapsed;self._dice_kind="color"
        self._extra_dice=[]
        self._show_cocked_overlay=False
        if elapsed>=duration:
            if not self._point_frames:self._finish_round();return
            transfer=elapsed-duration
            self._gate_elapsed=0.
            if transfer<.9:
                self._poses=self._frames[-1]
                self._side_points=[]
                self._extra_dice=[(v,True) for v in self._move_poses(
                    [self._parking_pose(i,v) for i,v in enumerate(self._point_frames[0])],self._point_frames[0],transfer/.9)]
                self.draw_scene();self._job=self.root.after(16,self._animate);return
            if transfer<1.8:
                self._extra_dice=[(v,True) for v in self._point_frames[0]]
                self._poses=self._move_poses(self._frames[-1],
                    [self._parking_pose(i,v) for i,v in enumerate(self._frames[-1])],(transfer-.9)/.9)
                self.draw_scene();self._job=self.root.after(16,self._animate);return
            self._side_points=[]
            self._parked_poses=[self._parking_pose(i,v) for i,v in enumerate(self._frames[-1])]
            frames=self._point_frames;clock=elapsed-duration-1.8;self._dice_kind="points"
        self._gate_elapsed=clock
        self._gate_return_at=self._point_gate_return if self._dice_kind=="points" else self._color_gate_return
        frame=int(clock/DicePhysics.FRAME_DT)
        if frame>=len(frames)-1:self._finish_round();return
        if self._dice_kind=="points":
            self._show_cocked_overlay=frame in self._point_cocked_idx
            self._display_point_total,self._gate_elapsed,self._gate_return_at=self._point_timeline[frame]
        alpha=clock/DicePhysics.FRAME_DT-frame
        self._poses=[]
        for a,b in zip(frames[frame],frames[frame+1]):
            sign=1 if dot(a[3:],b[3:])>=0 else -1
            q=unit(tuple(a[i]+(sign*b[i]-a[i])*alpha for i in range(3,7)))
            self._poses.append(tuple(a[i]+(b[i]-a[i])*alpha for i in range(3))+q)
        self.info_var.set("游戏进行中，请稍等")
        self.draw_scene()
        self._job=self.root.after(16,self._animate)

    def _finish_round(self,force=False):
        if not self.game_active or self._result is None:return
        self._cancel_jobs()
        r=self._result
        self.balance=r.final_balance
        self.session_net+=r.net
        self.last_win=r.returned if not r.invalid else Decimal(0)
        self.round_count+=1
        self._last_result=r
        self._result=None
        self.game_active=False
        self._poses=self._point_frames[-1] if self._point_frames else self._frames[-1]
        self._dice_kind="points" if self._point_frames else "color"
        if self._point_frames:self._parked_poses=[self._parking_pose(i,v) for i,v in enumerate(self._frames[-1])]
        self._extra_dice=[]
        self._gate_elapsed=0.
        self._next_tops=tuple(max(range(6),key=lambda i:rotate(v[3:],DICE_NORMALS[i])[2])
                              for v in self._frames[-1]) if r.invalid else r.outcomes
        self._show_cocked_overlay=r.invalid and self._cocked_display
        if r.invalid:
            if getattr(self,'_cocked_display',False):
                self.result_var.set("斜骰\nCocked Dice")
            else:
                self.result_var.set(f"本局无效 · 全额退回 {r.stake:,.2f}")
            self.info_var.set(f"本局无效 · 全部下注已退回 {r.stake:,.2f} · 无输赢")
        else:
            self.result_var.set(f"净赢 {r.net:+,.2f} · 返还 {r.returned:,.2f}")
            self.info_var.set("你赢啦" if r.net>0 else "下局加油")
        # 无效轮不写入历史记录
        if not r.invalid:
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

    def draw_history(self):
        c=self.history_canvas;c.delete("all")
        c.create_text(18,36,text="最\n新",font=("Arial",10,"bold"),fill="#2A1B08")
        for row in range(3):
            for col in range(15):
                x=37+col*22
                fill = HISTORY_COLORS.get(self.history[col][row],"white") if col<len(self.history) else "white"
                c.create_rectangle(x,row*24,x+22,row*24+24,fill=fill,outline="black",width=2)
                if col<len(self.history):
                    c.create_text(x+11,row*24+12,text=self.history[col][row],fill=HISTORY_TEXT[self.history[col][row]],font=("Arial",9,"bold"))

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
        self.stats_button.configure(text=f"{self.stats_limit}局的分布")
        self.draw_statistics()

    def chip_for_amount(self,amount):
        return max((c for c in self.chip_configs if money(c[1])<=amount),key=lambda c:money(c[1]),default=self.chip_configs[0])

    def _area_return(self,index):
        r=self._last_result
        if r is None or r.invalid:return Decimal(0)
        hits=r.outcomes.count(index)
        if not hits:return Decimal(0)
        return r.bets[index]*result_multiplier(r,index)

    def draw_statistics(self):
        c=self.stats_canvas;c.delete("all")
        values,count=self.history_store.percentages(self.stats_limit)
        for column,index in enumerate(HISTORY_ORDER):
            card,value=COLOR_NAMES[index],values[index]
            x=2+column*62
            c.create_rectangle(x,1,x+62,37,fill=HISTORY_COLORS[card],outline="black",width=2)
            c.create_line(x,19,x+62,19,fill="black",width=2)
            c.create_text(x+31,9,text=card,fill=HISTORY_TEXT[card],font=("Arial",10,"bold"))
            c.create_text(x+31,28,text=f"{value:.1f}%",fill=HISTORY_TEXT[card],font=("Arial",10))
        c.create_rectangle(2,1,374,37,outline="black",width=2)

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
            self._begin_dice_return()
            return
        self.draw_betting()
        self._flash_job=self.root.after(16,self._animate_chip_return)

    def _begin_dice_return(self):
        self._ready_model=DicePhysics(self._rng,self._next_tops)
        self._ready_poses=self._ready_model.poses()
        self._return_colors=self._parked_poses if self._point_frames else self._frames[-1]
        self._return_points=self._point_frames[-1] if self._point_frames else None
        if self._return_points:
            faces=tuple(max(range(6),key=lambda i:rotate(v[3:],DICE_NORMALS[i])[2]) for v in self._return_points)
            self._point_ready=DicePhysics(self._rng,faces).initial
        self._dice_return_started=time.monotonic()
        self._animate_dice_return()

    def _animate_dice_return(self):
        self._flash_job=None
        if self._closed:return
        t=min(1.,(time.monotonic()-self._dice_return_started)/1.1)
        self._parked_poses=[];self._extra_dice=[];self._dice_kind="color";self._gate_elapsed=0.
        self._poses=self._move_poses(self._return_colors,self._ready_poses,t)
        if self._return_points:
            self._side_points=self._move_poses(self._return_points,
                [self._parking_pose(i,v) for i,v in enumerate(self._point_ready)],t)
        self.draw_scene()
        if t>=1:self.new_round();return
        self._flash_job=self.root.after(16,self._animate_dice_return)

    def new_round(self):
        if self.game_active or self._closed or self._flash_active:return
        self._settled=False;self._new_ticket=True;self._last_result=None;self._parked_poses=[]
        self.bets=[Decimal(0) for _ in COLOR_NAMES];self._bet_actions.clear();self._chip_moves.clear()
        self._ready_poses=self._ready_model.poses();self._dice_kind="color";self._gate_elapsed=0.
        self._poses=[];self._extra_dice=[]
        self._cocked_display=False
        self._show_cocked_overlay=False
        self._point_cocked_idx=set()
        self._point_timeline=[];self._display_point_total=0
        self._side_points=[self._parking_pose(i,v) for i,v in enumerate(self._point_ready)]
        self.info_var.set("请下注")
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
            self._job=None

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
        self._closed=True
        self._restore_window_close()
        finish=getattr(self.root,"finish",None)
        if callable(finish):
            finish(float(self.balance))
        elif callable(getattr(self,"_embedded_return",None)):
            self._embedded_return(float(self.balance))
        else:
            self.root.destroy()

    def _on_destroy(self,event):
        if event.widget is not self.root:
            return
        self._restore_window_close()
        self._cancel_jobs()
        if self._result is not None:
            self.balance=self._result.final_balance
            self._result=None
        self.game_active=False
        self._closed=True

    @staticmethod
    def _draw_cube(c,pose,project,numbered=False):
        position=pose[:3];q=pose[3:]
        vertices=[vadd(position,rotate(q,vmul(v,DicePhysics.HALF))) for v in DICE_VERTICES]
        faces=[]
        for i,indices in enumerate(DICE_FACES):
            normal=rotate(q,DICE_NORMALS[i])
            if dot(normal,(1.2-position[0],8.5-position[1],5.2-position[2]))<=0:continue
            depth=sum(vertices[j][1]*.803+vertices[j][2]*.596 for j in indices)/4
            faces.append((depth,i,indices,normal))
        for _,i,indices,normal in sorted(faces):
            brightness=.70+.30*max(0,dot(normal,unit((-.3,.4,1))))
            def shade(color):return '#'+''.join(f'{int(int(color[j:j+2],16)*brightness):02x}' for j in (1,3,5))
            face=[vertices[j] for j in indices]
            def at(u,v):
                return tuple((1-u)*(1-v)*face[0][k]+u*(1-v)*face[1][k]+u*v*face[2][k]+(1-u)*v*face[3][k] for k in range(3))
            def polygon(points,fill,outline,width=1):
                c.create_polygon(*[v for pt in points for v in project(*pt)],fill=fill,outline=outline,width=width)
            rounded=[]
            r=DicePhysics.ROUNDING/DicePhysics.SIZE
            for u,v,start in ((r,r,math.pi),(1-r,r,1.5*math.pi),(1-r,1-r,0),(r,1-r,.5*math.pi)):
                for j in range(5):
                    angle=start+j*math.pi/8
                    rounded.append(at(u+r*math.cos(angle),v+r*math.sin(angle)))
            polygon(rounded,shade("#EDE5D3"),"#665A45")
            margin=.085
            inset=[at(margin,margin),at(1-margin,margin),at(1-margin,1-margin),at(margin,1-margin)]
            polygon(inset,shade("#FAF8ED" if numbered else COLOR_HEX[i]),"")
            if numbered:
                for x,y in PIP_LAYOUT[DICE_POINTS[i]]:
                    u,v=.5+x*.70,.5+y*.70
                    ring=[at(u+.080*math.cos(t*math.tau/16),v+.080*math.sin(t*math.tau/16)) for t in range(16)]
                    polygon(ring,"#A62622" if DICE_POINTS[i]==1 else "#171717","")

    def draw_scene(self):
        if self._closed:return
        c=self.canvas;c.delete("all")
        w,h=max(1,c.winfo_width()),max(1,c.winfo_height())
        scale=min(w/720,h/710);ox=(w-720*scale)/2;oy=(h-710*scale)/2
        camera=(1.2,9.0,5.5);forward=unit((0,-6.2,-4.6));up=(0,forward[2],-forward[1])
        def p(x,y,z):
            delta=(x-camera[0],y-camera[1],z-camera[2]);depth=max(.5,dot(delta,forward))
            return ox+(360+660*delta[0]/depth)*scale-10,oy+(365-735*dot(delta,up)/depth)*scale
        def p_side(x,y,z):
            sx,sy=p(x,y,z)
            return sx-25,sy
        def dice_projection(pose):
            # Keep parked dice fixed; blend the offset as dice travel to/from the main tray.
            offset=25*max(0.,min(1.,-pose[0]/.72))
            def project(x,y,z):
                sx,sy=p(x,y,z)
                return sx-offset,sy
            return project
        def poly(points,fill,outline="#A77832",width=1,project=p):
            c.create_polygon(*[v for xyz in points for v in project(*xyz)],fill=fill,outline=outline,width=width)
        def side_poly(points,fill,outline="#A77832",width=1):
            poly(points,fill,outline,width,project=p_side)
        W,D,end=DicePhysics.WIDTH,DicePhysics.DEPTH,DicePhysics.RAMP_END;top=DicePhysics.height(0)
        c.create_text(12,oy+12*scale,text="颜色游戏",anchor="nw",fill="#F2E6C9",
                      font=(Theme.FONT_CJK,max(16,round(23*scale)),"bold"))
        c.create_text(12,oy+46*scale,text="Color Game",anchor="nw",fill="#C5D1C8",
                      font=("Arial",max(10,round(13*scale))))
        poly([(-.18,0,top-.12),(W+.18,0,top-.12),(W+.22,D+.15,-.12),(-.22,D+.15,-.12)],"#1d3029","")
        poly([(0,0,top),(W,0,top),(W,0,top+.42),(0,0,top+.42)],"#784125","#DBAF52",2)
        ring=[(W/2+DicePhysics.TRAY_RADIUS*math.cos(i*math.tau/64),
               DicePhysics.TRAY_Y+DicePhysics.TRAY_RADIUS*math.sin(i*math.tau/64),0) for i in range(64)]
        poly(ring,"#A86A45","#E1B85D",2)
        for i,a in enumerate(ring):
            b=ring[(i+1)%64]
            poly([(a[0],a[1],-.12),(b[0],b[1],-.12),b,a],"#754021","#BE9349")
        poly([(0,DicePhysics.GATE_Y,top),(W,DicePhysics.GATE_Y,top),(W,end,0),(0,end,0)],"#AA653F","#E1B85D",2)
        lift=DicePhysics.gate_lift(self._gate_elapsed,getattr(self,"_gate_return_at",None))
        tilt=1.12*min(1.,lift/.5)
        gy=DicePhysics.GATE_Y
        poly([(0,0,top+gy*tilt),(W,0,top+gy*tilt),(W,gy,top),(0,gy,top)],"#955332","#E1B85D",2)
        for y in DicePhysics.BUMPS:
            r=DicePhysics.BUMP_RADIUS
            for j in range(16):
                y0=y-2*r+j*r/4;y1=y0+r/4
                z0=DicePhysics.height(y0)+r*(1+math.cos(math.pi*(y0-y)/(2*r)))/2
                z1=DicePhysics.height(y1)+r*(1+math.cos(math.pi*(y1-y)/(2*r)))/2
                poly([(0,y0,z0),(W,y0,z0),(W,y1,z1),(0,y1,z1)],"#"+"".join(f"{round(v*(.75+.25*math.sin((j+.5)*math.pi/16))):02x}" for v in (205,143,89)),"")
            c.create_line(*p(0,y,DicePhysics.height(y)+r),*p(W,y,DicePhysics.height(y)+r),fill="#E5B976",width=max(1,1.4*scale))
            c.create_line(*p(0,y+2*r,DicePhysics.height(y+2*r)),*p(W,y+2*r,DicePhysics.height(y+2*r)),fill="#60351F",width=max(1,2*scale))
        def screen_rect(x0,y0,x1,y1,color,outline=""):
            points=[(x0,y0,DicePhysics.height(y0)+.006),(x1,y0,DicePhysics.height(y0)+.006),
                    (x1,y1,DicePhysics.height(y1)+.006),(x0,y1,DicePhysics.height(y1)+.006)]
            poly(points,color,outline,2)
        screen_rect(.10,2.04,W-.10,2.48,"#101918","#D5B466")
        result=self._last_result if self._settled else None
        if result is None and self.game_active and self._point_frames and time.monotonic()-self._started_at>=(len(self._frames)-1)*DicePhysics.FRAME_DT:
            result=self._result
        labels=("","","")
        total=(bonus_multiplier(result.bonus_points) if result and result.bonus_points and self._settled
               else getattr(self,"_display_point_total",0) if result else 0)
        if total:
            if total<10:
                labels=("0",str(total),"X")
            elif total<100:
                labels=(str(total//10),str(total%10),"X")
            else:
                labels=(str(total//10),str(total%10),"X")
        # 电视提示
        if getattr(self,'_show_cocked_overlay',False):
            tv_x,tv_y=p((.10+W-.10)/2,2.26,DicePhysics.height(2.26)+.01)
            c.create_text(tv_x,tv_y-14*scale,text="斜骰",fill="#F2E6C9",
                          font=(Theme.FONT_CJK,max(14,round(20*scale)),"bold"))
            c.create_text(tv_x,tv_y+14*scale,text="Cocked Dice",fill="#F2E6C9",
                          font=(Theme.FONT_CJK,max(12,round(15*scale))))
        elif result is None:
            if self.game_active:
                tv_text="掷骰中"
            else:
                tv_text="请下注"
            tv_x,tv_y=p((.10+W-.10)/2,2.26,DicePhysics.height(2.26)+.01)
            c.create_text(tv_x,tv_y,text=tv_text,fill="#F2E6C9",
                          font=(Theme.FONT_CJK,max(16,round(24*scale)),"bold"))
        elif result.invalid and getattr(self,'_cocked_display',False):
            tv_x,tv_y=p((.10+W-.10)/2,2.26,DicePhysics.height(2.26)+.01)
            c.create_text(tv_x,tv_y-14*scale,text="斜骰",fill="#F2E6C9",
                          font=(Theme.FONT_CJK,max(14,round(20*scale)),"bold"))
            c.create_text(tv_x,tv_y+14*scale,text="Cocked Dice",fill="#F2E6C9",
                          font=(Theme.FONT_CJK,max(12,round(15*scale))))
        if result and not result.invalid and not self._show_cocked_overlay:
            for i,color in enumerate(result.outcomes):
                if color not in range(6):continue
                x0=.16+i*.70;x1=x0+.66
                screen_rect(x0,2.08,x1,2.44,COLOR_HEX[color])
                dark="#"+"".join(f"{int(COLOR_HEX[color][j:j+2],16)*4//5:02x}" for j in (1,3,5))
                for line in range(12):
                    yy=2.09+line*.028
                    c.create_line(*p(x0,yy,DicePhysics.height(yy)+.008),*p(x1,yy,DicePhysics.height(yy)+.008),fill=dark,width=1)
                if labels[i]:
                    xx,yy=p((x0+x1)/2,2.26,DicePhysics.height(2.26)+.013)
                    c.create_text(xx,yy,text=labels[i],fill="black" if color in (2,4,5) else "white",font=("Arial",max(15,round(23*scale)),"bold"))
        c.create_line(*p(.17,2.07,DicePhysics.height(2.07)+.01),*p(W-.17,2.07,DicePhysics.height(2.07)+.01),fill="#B7C7C1",width=1)
        for x in (0,W):
            poly([(x,0,top),(x,end,0),(x,end,.20),(x,0,top+.20)],"#C99542","#F3D480")
        for side in (0,W):
            sign=1 if side==0 else -1
            for y in DicePhysics.SIDE_BUMPS:
                base=[(side,y-DicePhysics.TOOTH_HALF),(side+sign*DicePhysics.TOOTH_REACH,y),(side,y+DicePhysics.TOOTH_HALF)]
                lower=[(x,yy,DicePhysics.height(yy)) for x,yy in base]
                upper=[(x,yy,z+DicePhysics.TOOTH_HEIGHT) for x,yy,z in lower]
                for i in range(3):
                    j=(i+1)%3
                    poly([lower[i],lower[j],upper[j],upper[i]],"#AD8138","#D8B25D")
                poly(upper,"#F7DE90","#FFF0BA")
        cord=[(W,gy,top+lift+DicePhysics.GATE_HEIGHT),
              (W+.23,gy,top+lift+DicePhysics.GATE_HEIGHT+.12),
              (W+.28,1.45,DicePhysics.height(1.45)+.28+lift*.35),
              (W+.32,2.5,DicePhysics.height(2.5)+.22+lift*.35)]
        c.create_line(*[v for point in cord for v in p(*point)],fill="#E6CA80",width=max(2,2.5*scale),smooth=True)
        # 左侧骰子收集桌（左移并新增桌腿）
        # 桌腿（先画，位于桌面下）
        side_poly([(-1.13,2.70,-.12),(-1.08,2.70,-.12),(-1.08,2.70,-.55),(-1.13,2.70,-.55)],"#3a2415","#241408")
        side_poly([(-.34,2.70,-.12),(-.29,2.70,-.12),(-.29,2.70,-.55),(-.34,2.70,-.55)],"#3a2415","#241408")
        side_poly([(-1.13,2.70,-.55),(-1.08,2.70,-.55),(-1.08,4.55,-.55),(-1.13,4.55,-.55)],"#2a1a10","#1a0e08")
        side_poly([(-.34,2.70,-.55),(-.29,2.70,-.55),(-.29,4.55,-.55),(-.34,4.55,-.55)],"#2a1a10","#1a0e08")
        # 桌面
        side_poly([(-1.16,2.68,0),(-.26,2.68,0),(-.26,4.63,0),(-1.16,4.63,0)],"#593820","#DEB65F",2)
        side_poly([(-1.16,4.63,0),(-.26,4.63,0),(-.26,4.63,-.12),(-1.16,4.63,-.12)],"#352416","#B78741",2)
        for pose in getattr(self,"_parked_poses",[]):self._draw_cube(c,pose,dice_projection(pose),numbered=False)
        for pose in getattr(self,"_side_points",[]):self._draw_cube(c,pose,dice_projection(pose),numbered=True)
        for pose,numbered in getattr(self,"_extra_dice",[]):self._draw_cube(c,pose,dice_projection(pose),numbered=numbered)
        poses=self._poses or self._ready_poses
        for pose in sorted(poses,key=lambda v:v[1]*.803+v[2]*.596):
            x,y,z=pose[:3];sx,sy=dice_projection(pose)(x,y,DicePhysics.height(y))
            c.create_oval(sx-13*scale,sy-3*scale,sx+13*scale,sy+5*scale,fill="#75462E",outline="")
            self._draw_cube(c,pose,dice_projection(pose),numbered=self._dice_kind=="points")
        gy=DicePhysics.GATE_Y;base=DicePhysics.height(gy)+lift
        poly([(0,gy,base),(W,gy,base),(W,gy,base+DicePhysics.GATE_HEIGHT),(0,gy,base+DicePhysics.GATE_HEIGHT)],"#CDA451","#F8DD91",1)
        for i,a in enumerate(ring):
            b=ring[(i+1)%64]
            if a[1]>DicePhysics.TRAY_Y and b[1]>DicePhysics.TRAY_Y:
                poly([a,b,(b[0],b[1],.12),(a[0],a[1],.12)],"#C49A4C","#E6C579")


RedPacketRainGame = ColorGame
DropBallGame = ColorGame


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
            self.game = ColorGame(
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


def main(initial_balance=1000.0, username="Guest", *, parent=None, balance=None,
         user=None, on_back=None, on_balance_change=None, demo=False):
    """
    Parent 嵌入接口：
        main(parent=..., balance=..., user=..., on_back=..., on_balance_change=...)

    未传 parent 时仍可独立运行。
    """
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user
    store = AccountStore(actual_user, demo)

    if parent is not None:
        return EmbeddedGamePage(
            parent, actual_balance, actual_user, demo=demo, store=store,
            on_back=on_back, on_balance_change=on_balance_change,
        )

    root = tk.Tk()
    root.title("颜色游戏")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    root.configure(bg=Theme.APP_BG)

    game = ColorGame(root, actual_balance, actual_user, demo=demo, store=store)

    def close_standalone(_balance=None):
        try:
            game._finish_round(force=True)
        except Exception:
            pass
        game._cancel_jobs()
        game._closed = True
        try:
            root.destroy()
        except tk.TclError:
            pass

    game._embedded_return = close_standalone
    root.protocol("WM_DELETE_WINDOW", game.on_closing)
    root.mainloop()
    return float(game.balance)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="2.5D Color Game；独立体验请使用 --demo")
    parser.add_argument("--demo", action="store_true", help="虚拟积分演示，不读写账户")
    parser.add_argument("--balance", default="10000", help="演示初始积分")
    args = parser.parse_args()
    try:
        final_balance = main(money(args.balance), "test_user", demo=args.demo)
        print(f"Final balance: {final_balance:.2f}")
    except (RuntimeError, ValueError, tk.TclError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)