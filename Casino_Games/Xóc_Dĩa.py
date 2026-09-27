"""越南色碟 Xóc đĩa：四碗、四枚双面硬币的桌面游戏。"""
from __future__ import annotations

import argparse
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import importlib
import json
import math
from pathlib import Path
import random
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk
except ImportError:
    Image = ImageDraw = ImageFilter = ImageTk = None

VERSION = 'Xoc-Dia-v1.16'
CENT = Decimal('0.01')
RED, WHITE = '#D83E40', '#F9F7EF'
VIEW_DEPTH=.28/math.hypot(.28,.70)
VIEW_UP=.70/math.hypot(.28,.70)
SCENE_UNIT=872.
TABLE_POSITIONS=((201,306),(509,306),(201,620),(509,620))
PROGRESS_POSITIONS=((201,86),(509,86),(201,403),(509,403))
PROGRESS_SEGMENTS=12
BET_LABELS = ('小', '单', '双', '大', '3红1白', '3白1红', '4红', '4白', '2红2白')
# 净赢赔率；命中时还要返还本金。
PROFITS = (Decimal('.95'), Decimal('.95'), Decimal('.95'), Decimal('.95'),
           Decimal('2.5'), Decimal('2.5'), Decimal('14'), Decimal('14'), Decimal('1.5'))
CHIPS = ((10, '#FFA500'), (25, '#00FF00'), (100, '#000000'),
         (500, '#FF7DDA'), (1000, '#FFFFFF'), (2500, '#FF0000'))
HIGH_CHIPS = ((100, '#000000'), (500, '#FF7DDA'), (1000, '#FFFFFF'),
              (5000, '#FF0000'), (10000, '#00FBFF'), (50000, '#00FFAE'))
FONT = 'Microsoft YaHei UI' if sys.platform.startswith('win') else (
    'PingFang SC' if sys.platform == 'darwin' else 'Noto Sans CJK SC')


def chip_amount_text(amount):
    number=Decimal(str(amount))
    value=int(number)
    if number<1000 and number!=value:
        return f'{number:,.2f}'.rstrip('0').rstrip('.')
    if value<1000:return f'{value:,}'
    unit,suffix=((1000000,'M') if value>=1000000 else
                 (10000,'W') if value>=10000 else (1000,'K'))
    tenths,remainder=divmod(value,unit//10)
    whole,decimal=divmod(tenths,10)
    label=str(whole)+(f'.{decimal}' if decimal else '')
    return label+suffix+('+' if remainder else '')


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > Decimal('1000000000000'):
            raise ValueError('金额必须是 0 到 1 万亿之间的有效数字')
        return number.quantize(CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError('无效金额') from exc


@dataclass(frozen=True)
class TableResult:
    bets: tuple
    stake: Decimal
    outcomes: tuple  # 'red', 'white' or 'edge', one for each dish
    returned: Decimal
    net: Decimal
    final_balance: Decimal
    invalid: bool


def payout_multipliers(outcomes):
    """各下注区的含本金返还倍率；2 红时小/大均退还 1 倍。"""
    if len(outcomes) != 4 or any(c not in ('red', 'white') for c in outcomes):
        raise ValueError('需要四枚平放硬币的颜色')
    red = outcomes.count('red')
    matches = (red <= 1, red % 2 == 1, red % 2 == 0, red >= 3,
               red == 3, red == 1, red == 4, red == 0, red == 2)
    return tuple(Decimal(1) if red == 2 and i in (0, 3) else
                 Decimal(1) + PROFITS[i] if matches[i] else Decimal(0)
                 for i in range(len(BET_LABELS)))


def settle_table(balance, bets, outcomes):
    balance = money(balance)
    bets = tuple(money(v) for v in bets)
    outcomes = tuple(outcomes)
    if len(bets) != len(BET_LABELS) or len(outcomes) != 4 or any(
            c not in ('red', 'white', 'edge') for c in outcomes):
        raise ValueError('需要九个下注区及四枚硬币的结果')
    stake = sum(bets, Decimal(0))
    if stake > balance:
        raise ValueError('总下注不能超过余额')
    invalid = 'edge' in outcomes
    returned = stake if invalid else sum(
        (v * m for v, m in zip(bets, payout_multipliers(outcomes))), Decimal(0))
    returned = money(returned)
    return TableResult(bets, stake, outcomes, returned, returned - stake,
                       balance - stake + returned, invalid)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _normal(q):
    w,x,y,z=q
    return (2*(x*z+w*y), 2*(y*z-w*x), 1-2*(x*x+y*y))


def _rotate(q, omega, dt):
    speed=math.sqrt(sum(v*v for v in omega))
    if speed < 1e-9:return q
    a=speed*dt/2
    s=math.sin(a)/speed
    dw,dx,dy,dz=math.cos(a),omega[0]*s,omega[1]*s,omega[2]*s
    w,x,y,z=q
    r=(dw*w-dx*x-dy*y-dz*z, dw*x+dx*w+dy*z-dz*y,
       dw*y-dx*z+dy*w+dz*x, dw*z+dx*y-dy*x+dz*w)
    norm=math.sqrt(sum(v*v for v in r))
    return tuple(v/norm for v in r)


def _body_vector(v,axis,angle):
    """Rotate a dish-space vector into the table frame."""
    x,y,z=v;c=math.cos(angle);s=math.sin(angle)
    if axis=='x':return x,y*c-z*s,y*s+z*c
    if axis=='y':return x*c+z*s,y,-x*s+z*c
    return v


def _half_turn(u,duration,direction,returning=False):
    """A complete 180-degree rotation uses the entire requested duration."""
    v=max(0.,min(1.,u))
    base=direction*math.pi if returning else 0.
    travel=(-1 if returning else 1)*direction*math.pi
    smooth=v*v*v*(10-15*v+6*v*v)
    angle=base+travel*smooth
    rate=travel*30*v*v*(1-v)**2/duration
    acceleration=travel*60*v*(1-v)*(1-2*v)/duration**2
    return angle,rate,acceleration


def _sprite_projection(axis,angle):
    """Oblique projection of a rotating x/z surface, including its height."""
    cosine=math.cos(angle);sine=math.sin(angle)
    if axis=='x':
        vertical=cosine+.88*sine
        if abs(vertical)<.065:vertical=math.copysign(.065,vertical)
        return 1.,0.,0.,vertical
    if axis=='y':return cosine,-1.56*sine,sine/1.56,cosine
    return 1.,0.,0.,1.


def _orbit_motion(t,duration,parameters):
    """Smooth O-shaped displacement and its exact second derivative.

    One trajectory spans outbound turn, inverted hold and return turn, so
    neither position nor acceleration jumps at a 180-degree boundary.
    """
    if t<=0. or t>=duration:return (0.,)*6
    radius,phase,direction,cycles,heading=parameters
    u=t/duration;s=math.sin(math.pi*u);c=math.cos(math.pi*u)
    envelope=s**4
    velocity=4*math.pi*s**3*c/duration
    acceleration=4*math.pi**2*s*s*(3-4*s*s)/duration**2
    speed=direction*math.tau*cycles/duration
    angle=phase+speed*t
    co,si=math.cos(angle),math.sin(angle)
    a,b=co-math.cos(phase),si-math.sin(phase)
    horizontal=radius*envelope*a;vertical=radius*envelope*b
    ah=radius*(acceleration*a-2*velocity*speed*si-envelope*speed*speed*co)
    av=radius*(acceleration*b+2*velocity*speed*co-envelope*speed*speed*si)
    # A mostly frontal vertical circle, with a little depth for dealer motion.
    x,y=math.cos(heading),math.sin(heading)
    return horizontal*x,horizontal*y,vertical,ah*x,ah*y,av


class Coin:
    """Disk in a circular dish; metre and second units, rigid body orientation."""
    RADIUS=.018
    HALF_THICK=.0012
    DISH_RADIUS=.085
    BOWL_HEIGHT=.128

    def __init__(self,rng):
        self.rng=rng
        self.x=rng.uniform(-.012,.012);self.y=rng.uniform(-.012,.012)
        self.z=self.HALF_THICK
        self.vx=self.vy=self.vz=0.
        # A new table begins with a known face. Later rounds keep the actual
        # previous orientation until the dealer's motion turns the coin.
        self.q=(1.,0.,0.,0.)
        self.omega=[0.,0.,0.]
        self.shake_x=self.shake_y=self.lift=0.
        self.tilt_axis=None;self.tilt_angle=0.
        self._frame_axis=None;self._frame_angle=0.

    def normal(self):return _normal(self.q)

    def step(self,dt,ax,ay,az,rotation=None):
        # Linear/angular velocities live in the nonrotating table frame.
        # Only contacts transfer the dealer's rotation to the coin. Gravity
        # is ALWAYS vertically down, including when the dish is upside down.
        axis,angle,rate,_=rotation or (None,0.,0.,0.)
        old_axis,old_angle=self._frame_axis,self._frame_angle
        pivot=self.BOWL_HEIGHT/2
        p=_body_vector((self.x,self.y,self.z-pivot),old_axis,old_angle)
        old_spin=(old_angle,0.,0.) if old_axis=='x' else (
                 (0.,old_angle,0.) if old_axis=='y' else (0.,0.,0.))
        q=_rotate(self.q,old_spin,1.)
        v=[self.vx,self.vy,self.vz]
        omega=list(self.omega)
        # Four small steps reduce penetration and resolve multiple contacts.
        steps=max(1,math.ceil(dt*480));h=dt/steps
        dot=lambda a,b:sum(x*y for x,y in zip(a,b))
        def inertia_inverse(torque,normal):
            along=dot(torque,normal)
            it=.25*self.RADIUS**2+self.HALF_THICK**2/3
            iz=.5*self.RADIUS**2
            return tuple(torque[k]/it+normal[k]*along*(1/iz-1/it) for k in range(3))
        for sub in range(steps):
            theta=old_angle+(angle-old_angle)*(sub+1)/steps if axis==old_axis else angle
            body_spin=(rate,0.,0.) if axis=='x' else ((0.,rate,0.) if axis=='y' else (0.,0.,0.))
            v=[v[k]+((0.,0.,-9.81)[k]-(ax,ay,az)[k])*h for k in range(3)]
            p=tuple(p[k]+v[k]*h for k in range(3))
            q=_rotate(q,omega,h)
            normal=_normal(q)
            local_n=_body_vector(normal,axis,-theta)
            # Exact support point of a finite disk in a requested direction.
            def support(direction):
                along=dot(direction,local_n)
                tangent=tuple(direction[k]-along*local_n[k] for k in range(3))
                length=math.sqrt(dot(tangent,tangent))
                return tuple((tangent[k]*self.RADIUS/length if length>1e-10 else 0.)+
                             math.copysign(self.HALF_THICK,along)*local_n[k] for k in range(3))
            touching=False
            for _ in range(4):
                local=_body_vector(p,axis,-theta)
                center=(local[0],local[1],local[2]+pivot)
                contact=support((0.,0.,-1.))
                depth=-(center[2]+contact[2]);inward=(0.,0.,1.)
                # A curved ellipsoidal inner dome, in the same dimensions
                # as the rendered bowl, rather than an invisible low ceiling.
                r2=self.DISH_RADIUS**2;h2=self.BOWL_HEIGHT**2
                direction=(center[0]/r2,center[1]/r2,max(0.,center[2])/h2)
                for _ in range(3):
                    rim=support(direction)
                    point=tuple(center[k]+rim[k] for k in range(3))
                    direction=(point[0]/r2,point[1]/r2,max(0.,point[2])/h2)
                level=(point[0]**2+point[1]**2)/r2+max(0.,point[2])**2/h2
                gradient=math.sqrt(dot(direction,direction))
                dome_depth=(level-1)/(2*gradient) if gradient>1e-10 else -1.
                if dome_depth>depth:
                    depth=dome_depth;contact=rim
                    inward=tuple(-d/gradient for d in direction)
                if depth<=0:break
                touching=True
                n=_body_vector(inward,axis,theta)
                r=_body_vector(contact,axis,theta)
                p=tuple(p[k]+n[k]*depth for k in range(3))
                surface=_cross(body_spin,tuple(p[k]+r[k] for k in range(3)))
                spin=_cross(omega,r)
                relative=tuple(v[k]+spin[k]-surface[k] for k in range(3))
                speed=dot(relative,n)
                if speed>=0:continue
                rn=_cross(r,n)
                inverse=inertia_inverse(rn,normal)
                effective=1+dot(n,_cross(inverse,r))
                impulse=-(1.12 if speed<-.20 else 1.)*speed/effective
                v=[v[k]+impulse*n[k] for k in range(3)]
                omega=[omega[k]+impulse*inverse[k] for k in range(3)]
                spin=_cross(omega,r)
                relative=tuple(v[k]+spin[k]-surface[k] for k in range(3))
                tangent=tuple(relative[k]-dot(relative,n)*n[k] for k in range(3))
                slip=math.sqrt(dot(tangent,tangent))
                if slip>1e-9:
                    direction=tuple(-t/slip for t in tangent)
                    inverse=inertia_inverse(_cross(r,direction),normal)
                    friction=min(.42*impulse,slip/(1+dot(direction,_cross(inverse,r))))
                    v=[v[k]+friction*direction[k] for k in range(3)]
                    omega=[omega[k]+friction*inverse[k] for k in range(3)]
            # Dissipation models air drag and rolling resistance, without
            # assigning a random face or forcing the coin to follow the lid.
            decay=math.exp(-(1.8 if touching else .12)*h)
            omega=[o*decay for o in omega]
            if touching and not rate:
                v=[v[k]*math.exp(-2*h) for k in range(3)]
        local=_body_vector(p,axis,-angle)
        self.x,self.y,self.z=local[0],local[1],local[2]+pivot
        spin=(-angle,0.,0.) if axis=='x' else ((0.,-angle,0.) if axis=='y' else (0.,0.,0.))
        self.q=_rotate(q,spin,1.)
        self.vx,self.vy,self.vz=v;self.omega=omega
        self._frame_axis,self._frame_angle=axis,angle
        # Broad, nearly flat face contacts form a resting contact manifold.
        # Remove numerical chatter only at low energy; preserve the same face.
        n=self.normal()
        if (axis is None and max(abs(ax),abs(ay),abs(az))<1e-8 and
                abs(n[2])>.9995 and self.z<.0025 and
                math.sqrt(sum(v*v for v in (self.vx,self.vy,self.vz)))<.065 and
                math.sqrt(sum(v*v for v in self.omega))<3.):
            target=(0.,0.,math.copysign(1.,n[2]))
            axis_flat=_cross(n,target);length=math.sqrt(sum(v*v for v in axis_flat))
            if length>1e-12:
                correction=math.asin(min(1.,length))
                self.q=_rotate(self.q,tuple(v/length for v in axis_flat),correction)
            self.z=self.HALF_THICK
            self.vx=self.vy=self.vz=0.;self.omega=[0.,0.,0.]

    def snapshot(self):
        return {'x':self.x,'y':self.y,'z':self.z,'q':list(self.q),
                'face':self.result()}

    def restore(self,state):
        try:
            x,y,z=(float(state[k]) for k in ('x','y','z'))
            q=tuple(float(v) for v in state['q'])
            if len(q)!=4 or not all(math.isfinite(v) for v in (x,y,z,*q)):
                return False
            if (math.hypot(x,y)>self.DISH_RADIUS or not 0<=z<=self.BOWL_HEIGHT or
                    abs(sum(v*v for v in q)-1)>1e-5):return False
        except (KeyError,TypeError,ValueError):return False
        self.x,self.y,self.z,self.q=x,y,z,q
        self.vx=self.vy=self.vz=0.;self.omega=[0.,0.,0.]
        self._frame_axis=None;self._frame_angle=0.
        return True

    def settled(self):
        nz=abs(self.normal()[2])
        resting_shape=(self.z<.004 and nz>.998) or nz<.25
        return (resting_shape and abs(self.vz)<.04 and
                math.hypot(self.vx,self.vy)<.035 and
                math.hypot(self.omega[0],self.omega[1])<.25)

    def result(self):
        nz=self.normal()[2]
        return 'edge' if abs(nz)<.25 else ('red' if nz>0 else 'white')


# Legacy embedded artwork; vector rendering supplies the animated fallback.
SCENE_DISH_PNG = (
    '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'
 )
SCENE_BOWL_PNG = (
    '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'
    'z29Z8J+XgD/xiN4KAI/i0as+M7ui22Mf0UdsLzDFwF95wCeIRwEKBro6azYMcj/+oZ/4qbtuva377Pnz/tLxUydqE9NPBPlw483v'
    'fMsHi/09XeWJcpUNKxNYjWSCXmZvaKCrYaqUyzEcsOc9d767o7/nHa6WHBs9ceaZ0fGLTlTlf/vnv/ojvb19d/cU8mfzQdhVkWgG'
    '0PIlROdyyP0tADyAB/w1BzwAjGBEiUgF8kmB9wCFCo37i50PDnR3/k9VjH74Iz/+S//4F37hzkqS4Gt/+td/N3Nx/Gu2kFu/fveO'
    'h7bes/cuiYTKE+Wqi8WpEcrAn9kbCeTGMHnxWp2qRnG5HA9u27Jx29tv+4lif9d9cTV+5Zmv/t0Xjhx+duyHfugHNv1vv/IrP9vf'
    '339bNYo+tXPd8J0M7gYjziEsKfQzPUTjj+gj9mrpPLAKqt8j+oh9kB50oxr9206E/9cUojGG6bLgZ89Pj//MsYsj7y7lwvdPz8wc'
    'eeq73/vmZz7zR8duvXPvwKZbdtyV68zvES/laKZ2bOLsuZemR8Ym1SVew5y1IVsjTJ5ZKcv1M7sBTA1TQxRLvPeuHDsAKHV1FXq3'
    'D28vdnftMjk77KP47PjZ8089+bVvHH/7O97W/4M/+N57hgcH3+VBx0enJ/7z+2+7558J5FcTJGMWQZ9D8twMcvf/AQ7EB3BAX1fA'
    'qyo9ikfNA3hARxF9vITcP5hBNMHC3QGbVy34f//K89+72Fkq/RwRD124cOFbX//a1779lS9/dWTHHbf2b79j9z2FztItAJDEyYVo'
    'qnx86uLIqemRsUmtJJ6KgYExJgyCWTaSiX2ZXW8A9140qTmvvuoBIN/dU+rZNLy+o7tzuy0WNhqmooviMxdeO/nEs48+cXz7ru2F'
    'D7z//bfv3Lnz+4Ig7JwuV/7k1k0bXurv6P5/E/jHYkTjFkGvQF5m2Pf2AK+h3sK+kte8KtRZVekADtBBOiijGn8iQPALCeIZBWyA'
    'IE+g3zs7OfrpYxfOrSvmix9SL12TU1MvPv/i89/90z/602ODN63v3bp7145Sd+dODsJ1ClXv3Pl4euZEZXz64vT41HitPFNDEsOE'
    'OYYxxrCZ07CQOYHMrhW4ASBOEhFV0Zr3zE4plw+7+7q78j09A/mezs25fLiZyRREZKI2M3383Gtnj7703SNnHnzPO3vf/q533js0'
    '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'
    '6gwaguFOoFMw7hUdtxnwhgSaKCRH0PcqkEMaBQMF3lFPHeqUXwfbOYgr4zfg4CCQqH3xXhugUBVdqhO5+uclSgTk0gbI9nX1lGpr'
    'ECLHtOD2ugxgh+RC6khIGWQF8j0GLgBA2oDlHjeg0x4wDEQhco8LJvwIvOxqEc6WAGptOKI3OrAzwF+dM5hNDxrO4FE8Sg/Sg26p'
    'P2tEtdNiwqTbvEcVyW2MYL2DcwJvAKgB3c/grQKf1Ok8M0gEWMfgO+u91zRfTF2aE1lBbG8B5zxfpSmNlnMEPNf0HhpkP1LQl1NN'
    'ZJbBxCFyj/t6fa83negysYx1Mo/i0aY3fJmGv5lBnQF+7RzCFQyh2ZbCFpbwu3rGMa5Ab7vFIwVanciqCncmPdzAreC80sbRi156'
    'CijfS5Ss5NlejsrzgzkDdAb4G8E5LOggmh3Fo3iUHsAD/kbc1I/oI/ZKwLZ5ly0AzkCcAT5zGEu7InhRJ7Iyaw/OeTdVBtrMMsss'
    's8wyyyyzzDLLLLPMMssss8wyyyyzzDLLLLPMMssss8wyyyyzzDLLLLPMMssss8wyyyyzzDLLLLPMMssss8wyyyyzzDLLLLPMMsss'
    's8wyyyyzzDLLLLPMMssss8wyyyyzzDK7ce3/D2VV6GBzyDgHAAAAAElFTkSuQmCC'
 )

def make_table_art():
    """Transparent, antialiased 2.5D dish and glass bowl sprites."""
    if Image is None:return None
    s=3
    def box(*values):return tuple(round(v*s) for v in values)
    def ellipse(draw,bounds,fill,outline=None,width=1):
        draw.ellipse(box(*bounds),fill=fill,outline=outline,width=max(1,round(width*s)))

    dish=Image.new('RGBA',(252*s,116*s))
    shadow=Image.new('RGBA',dish.size)
    ellipse(ImageDraw.Draw(shadow),(9,42,243,112),(0,0,0,115))
    dish.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6*s)))
    d=ImageDraw.Draw(dish)
    ellipse(d,(12,43,240,109),'#5C4834','#3C3027',2)
    ellipse(d,(9,32,243,99),'#9B774C','#E7CA91',2)
    ellipse(d,(12,24,240,90),'#B99563','#F8E5B4',3)
    ellipse(d,(17,23,235,88),'#D7B987','#8F6942',2)
    ellipse(d,(23,28,229,84),'#FFF0D0','#F8E8BB',2)
    d.arc(box(13,27,239,104),0,180,fill='#F2DA9E',width=round(3*s))
    d.arc(box(19,25,233,88),185,350,fill='#917249',width=round(2*s))

    bowl=Image.new('RGBA',(252*s,190*s))
    b=ImageDraw.Draw(bowl)
    ellipse(b,(19,115,233,163),(77,117,110,55),(190,224,218,155),2)
    # The transparent surface is brighter at its curved silhouette and lip.
    for yy in range(17*s,133*s):
        y=yy/s
        t=(y-17)/116
        radius=30+81*math.sqrt(max(0.,1-(1-t)**2))
        left=round((126-radius)*s);right=round((126+radius)*s)
        for xx in range(left,right+1):
            edge=abs(xx/s-126)/max(1,radius)
            alpha=round(13+22*t+79*edge**7)
            bowl.putpixel((xx,yy),(155,212,205,min(125,alpha)))
    b=ImageDraw.Draw(bowl)
    ellipse(b,(96,8,156,35),(220,246,237,80),(238,255,249,170),2)
    b.arc(box(17,15,235,154),188,268,fill=(243,255,250,215),width=round(3*s))
    b.arc(box(17,15,235,154),279,352,fill=(183,224,216,180),width=round(2*s))
    b.arc(box(30,22,221,146),187,253,fill=(255,255,255,100),width=round(8*s))
    b.arc(box(17,119,235,166),0,180,fill=(235,255,249,245),width=round(4*s))
    b.arc(box(26,125,226,158),0,180,fill=(113,170,159,145),width=round(2*s))
    resample=getattr(Image,'Resampling',Image).LANCZOS
    return (dish.resize((252,116),resample),
            bowl.resize((252,190),resample))


class AccountStore:
    def __init__(self, username, demo=False):
        self.username,self.demo=username,demo
        self.path=None
        if demo:return
        root=next((p for p in Path(__file__).resolve().parents
                   if (p/'A_Tools/Account/secure_json.py').is_file()),None)
        if root is None:
            raise RuntimeError('找不到原项目的加密账户模块。请放回原项目，或用 --demo 体验虚拟积分版。')
        if str(root) not in sys.path:sys.path.insert(0,str(root))
        importlib.import_module('A_Tools.Account').install_secure_json()
        self.path=root/'A_Tools/Account/saving_data.json'

    def save(self,balance):
        if self.demo:return
        # The host's secure_json module intercepts builtins.open; Path.open
        # bypasses that hook and can expose the encrypted envelope instead.
        with open(str(self.path),'r',encoding='utf-8') as stream:users=json.load(stream)
        # secure_json installations use both a top-level list and dictionaries
        # containing the same account records. Keep the original envelope intact.
        def find_account(node,depth=0):
            if depth>8:return None
            if isinstance(node,dict):
                if node.get('user_name')==self.username and 'cash' in node:
                    return node
                direct=node.get(self.username)
                if isinstance(direct,dict) and 'cash' in direct:
                    return direct
                for child in node.values():
                    found=find_account(child,depth+1)
                    if found is not None:return found
            elif isinstance(node,list):
                for child in node:
                    found=find_account(child,depth+1)
                    if found is not None:return found
            return None
        user=find_account(users)
        if user is None:raise ValueError('账户不存在')
        user['cash']=f'{balance:.2f}'
        with open(str(self.path),'w',encoding='utf-8') as stream:
            json.dump(users,stream,ensure_ascii=False,indent=4)


class XocDiaHistory:
    def __init__(self,path=None):
        self.path=Path(path) if path else None
        self.records=[];self.last_coin_states=[]
        if self.path and self.path.exists():
            try:
                payload=json.loads(self.path.read_text(encoding='utf-8'))
                self.last_coin_states=payload.get('last_coin_states',[])
                self.records=[{'colors':list(r['colors']),'time':(
                                  datetime.fromtimestamp(r['time']).strftime('%H:%M %d/%m/%Y')
                                  if isinstance(r.get('time'),(int,float)) else r.get('time',''))}
                              for r in payload.get('rounds',[]) if isinstance(r,dict) and
                              len(r.get('colors',[]))==4 and
                              all(c in ('red','white','edge') for c in r['colors'])][:2000]
            except (OSError,ValueError,TypeError,AttributeError):self.records=[];self.last_coin_states=[]

    def add(self,result,coins):
        self.last_coin_states=[coin.snapshot() for coin in coins]
        self.records.insert(0,{'colors':list(result.outcomes),
                               'time':datetime.now().strftime('%H:%M %d/%m/%Y')})
        self.records=self.records[:2000]
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'schema_version':2,'last_coin_states':self.last_coin_states,
                                             'rounds':self.records},ensure_ascii=False,indent=2),encoding='utf-8')
            temporary.replace(self.path)

    def recent(self):return self.records[:15]

    def percentages(self,limit):
        rows=[r for r in self.records[:limit] if 'edge' not in r['colors']]
        counts=[sum(r['colors'].count('red') in (0,1) for r in rows),
                sum(r['colors'].count('red') in (3,4) for r in rows),
                sum(r['colors'].count('red')%2==1 for r in rows),
                sum(r['colors'].count('red')%2==0 for r in rows)]
        return counts,len(rows)


class XocDiaGame:
    WINDOW_WIDTH,WINDOW_HEIGHT=1150,750

    def __init__(self,root,initial_balance,username,*,demo=False,store=None,manage_window=True):
        self.root,self.username=root,username
        self.balance=money(initial_balance)
        self.store=store if store is not None else AccountStore(username,demo)
        self.demo=demo;self._closed=False;self.game_active=False
        self._job=None;self._settled=False;self._result=None
        self._round_balance=None;self._debited_stake=Decimal(0)
        self._rng=random.Random(random.SystemRandom().getrandbits(128))
        self.high_bet_mode=False;self.selected_chip=0
        self.bets=[Decimal(0)]*len(BET_LABELS);self._last_bets=None
        self._scene_art_cache={}
        self._scene_scaled_source={};self._rotated_scene_cache={}
        self.stats_limit=50;self.coins=[Coin(self._rng) for _ in range(4)]
        self.shake_counts=[];self.durations=[];self._step_index=0
        self._phase='idle';self._phase_start=0.;self._last_tick=0.
        self._physics_time=0.;self._reveal=0.;self._direction=[];self._final_orbits=[]
        self._accumulator=0.;self._shake_end=0.;self._settle_time=0.;self._stable_time=0.
        self._flash_job=None;self._flash_step=0;self._flash_winners=();self._flash_invalid=False
        self._chip_job=None;self._chip_moves=[];self._pending_start=False
        self._return_moves=[];self._hidden_bets=set();self._close_started=0.
        # 日志固定写入脚本所在目录的上一级：../A_Logs/Json/Xóc_Dĩa.json
        log_path=(Path(__file__).resolve().parent/'..'/'A_Logs'/'Json'/'Xóc_Dĩa.json').resolve()
        legacy_name='Xoc_Dia.json'
        legacy_path=log_path.with_name(legacy_name)
        if not log_path.exists() and legacy_path.exists():
            try:legacy_path.replace(log_path)
            except OSError:pass
        self.history_store=XocDiaHistory(log_path)
        if isinstance(self.history_store.last_coin_states,list) and len(self.history_store.last_coin_states)==4:
            restored=[Coin(self._rng) for _ in range(4)]
            if all(c.restore(state) for c,state in zip(restored,self.history_store.last_coin_states)):
                self.coins=restored
        self._window=root.winfo_toplevel()
        self._embedded=not isinstance(root,(tk.Tk,tk.Toplevel))
        self._previous_close_protocol=self._window.protocol('WM_DELETE_WINDOW') if self._embedded else ''
        self._previous_resizable=self._window.resizable()
        self._close_command=None
        if manage_window:
            self._window.title('越南色碟 · Xóc đĩa')
            self._window.geometry('1150x750')
            self._window.minsize(1150,750)
            self._window.resizable(False,False)
            self._close_command=self._window.register(self.on_closing)
            self._window.tk.call('wm','protocol',self._window._w,'WM_DELETE_WINDOW',self._close_command)
        root.configure(bg='#183B32')
        root.bind('<Destroy>',self._on_destroy,add='+')
        self.create_widgets();self.update_display()

    @property
    def chip_configs(self):return HIGH_CHIPS if self.high_bet_mode else CHIPS

    @property
    def bet_limits(self):
        return (100,50000,250000) if self.high_bet_mode else (10,10000,50000)

    def valid_bets(self,bets):
        minimum,per,total=self.bet_limits
        return len(bets)==9 and all(v==0 or minimum<=v<=per for v in bets) and \
               sum(bets,Decimal(0))<=total

    def chip_for_amount(self,amount):
        return max((chip for chip in self.chip_configs if amount>=chip[0]),
                   key=lambda chip:chip[0],default=self.chip_configs[0])

    def create_widgets(self):
        self.balance_var=tk.StringVar(master=self.root)
        self.bet_var=tk.StringVar(master=self.root)
        self.last_win_var=tk.StringVar(master=self.root,value='上局获胜: $0')
        self.stage_var=tk.StringVar(master=self.root,value='下注中')
        self.info_var=tk.StringVar(master=self.root,value='请下注')
        self.result_var=tk.StringVar(master=self.root,value='')
        main=tk.Frame(self.root,bg='#183B32');main.pack(fill='both',expand=True,padx=10,pady=10)
        left=tk.Frame(main,bg='#254D42',highlightbackground='#D6B669',highlightthickness=2)
        left.pack(side='left',fill='both',expand=True,padx=(0,10))
        self.canvas=tk.Canvas(left,bg='#254D42',highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda _:self.draw_scene())
        right=tk.Frame(main,bg='#183B32',width=400);right.pack(side='right',fill='y')
        right.pack_propagate(False)
        section_y=0
        def section(height,title=None,padding=2):
            nonlocal section_y
            card=tk.Frame(right,bg='#F2E6CA',bd=1,relief=tk.SOLID)
            card.place(x=0,y=section_y,width=400,height=height)
            section_y+=height+2
            header=28 if title else 0
            if title:
                tk.Label(card,text=title,bg='#D8B46A',fg='#2A1B08',
                         font=(FONT,13,'bold')).place(x=0,y=0,relwidth=1,height=28)
            body=tk.Frame(card,bg='#F2E6CA')
            body.place(x=10,y=header+padding,width=376,height=height-header-2*padding-2)
            return body
        top=section(40,padding=4)
        tk.Label(top,textvariable=self.balance_var,bg='#F2E6CA',font=(FONT,16,'bold')).pack(side='left')
        tk.Label(top,textvariable=self.stage_var,bg='#F2E6CA',fg='#A88100',font=(FONT,14,'bold')).pack(side='right')
        limits=section(96,'下注上限',padding=8)
        self.limit_labels=[]
        for i,name in enumerate(('下注下限','单区上限','总下注上限')):
            limits.columnconfigure(i,weight=1)
            tk.Label(limits,text=name,bg='#F2E6CA',font=(FONT,11,'bold'),
                     bd=1,relief=tk.SOLID).grid(row=0,column=i,sticky='nsew')
            item=tk.Label(limits,bg='#F2E6CA',fg='#A88100',font=(FONT,12,'bold'),
                          bd=1,relief=tk.SOLID)
            item.grid(row=1,column=i,sticky='ew');self.limit_labels.append(item)
        for widget in (limits,limits.master,*limits.winfo_children()):
            widget.bind('<Button-1>',self.toggle_high_bet_limits)
        self._update_limits_display()
        bet=section(242,'筹码与下注')
        self.bet_canvas=tk.Canvas(bet,width=376,height=208,bg='#F2E6CA',highlightthickness=0)
        self.bet_canvas.pack(fill='both',expand=True)
        self.bet_canvas.bind('<Button-1>',self._bet_click)
        self.bet_canvas.bind('<Button-3>',self._bet_clear_click)
        self.bet_canvas.bind('<Configure>',lambda _:self.draw_betting())
        action=section(84,'操作')
        tk.Label(action,textvariable=self.info_var,bg='#F2E6CA',fg='#34291B',
                 font=(FONT,10,'bold')).place(x=0,y=0,width=376,height=20)
        row=tk.Frame(action,bg='#F2E6CA');row.place(x=0,y=20,width=376,height=28)
        self.reset_button=tk.Button(row,text='清除下注',command=self.reset_bet,bg='#CB4A4A',fg='white')
        self.repeat_button=tk.Button(row,text='重复上局下注',command=self.repeat_last_bet,bg='#4A90B6',fg='white')
        self.start_button=tk.Button(row,text='开始游戏',command=self.start_game,bg='#D8B46A',fg='#292015')
        for i,widget in enumerate((self.reset_button,self.repeat_button,self.start_button)):
            widget.place(x=i*125,y=0,width=123,height=28)
        history=section(109,'最近15局')
        self.history_canvas=tk.Canvas(history,width=376,height=75,bg='#FFFFFF',highlightthickness=0)
        self.history_canvas.pack(fill='both',expand=True)
        self.history_canvas.bind('<Configure>',lambda _:self.draw_history())
        stats=section(70)
        stats.place_configure(y=28,height=40)
        self.stats_button=tk.Button(stats.master,text='50 局的大小单数占比',command=self.change_stats_limit,
                                    bg='#D8B46A',relief='flat',font=(FONT,13,'bold'))
        self.stats_button.place(x=0,y=0,relwidth=1,height=28)
        self.stats_canvas=tk.Canvas(stats,width=376,height=40,bg='#FFFFFF',highlightthickness=0)
        self.stats_canvas.pack(fill='both',expand=True)
        self.stats_canvas.bind('<Configure>',lambda _:self.draw_statistics())
        bottom=section(66,padding=4)
        tk.Label(bottom,textvariable=self.bet_var,bg='#F2E6CA',font=(FONT,12)).pack(anchor='w')
        last=tk.Frame(bottom,bg='#F2E6CA');last.pack(fill='x',pady=2)
        tk.Label(last,textvariable=self.last_win_var,bg='#F2E6CA',font=(FONT,12)).pack(side='left')
        tk.Button(last,text='ℹ',command=self.show_game_instructions,bg='#4B8BBE',fg='white',
                  font=(FONT,12),width=2,relief='flat').pack(side='right')
        self.root.winfo_toplevel().bind('<Return>',self._on_start_key,add='+')

    def _update_limits_display(self):
        for label,value in zip(self.limit_labels,self.bet_limits):label.configure(text=f'${value:,}')

    def update_display(self):
        if self._closed:return
        self.reset_button.configure(state=tk.DISABLED if self.game_active else tk.NORMAL)
        self.start_button.configure(state=tk.DISABLED if self.game_active else tk.NORMAL)
        has_repeat=bool(self._last_bets and sum(self._last_bets,Decimal(0))>0)
        self.repeat_button.configure(state=tk.DISABLED if self.game_active or not has_repeat else tk.NORMAL)
        self.balance_var.set(f'余额 ${self.balance:,.2f}')
        self.bet_var.set(f'本局下注 ${int(sum(self.bets,Decimal(0))):,}')
        self.stage_var.set('摇碗中' if self._phase in ('starting','shake') else
                           '静置中' if self._phase=='settle' else
                           '开碗中' if self._phase=='reveal' else
                           '结算中' if self._phase in ('flash','closing') else
                           '已结算' if self._settled else '下注中')
        self.draw_betting();self.draw_scene()

    def _layout(self):
        w=max(100,self.bet_canvas.winfo_width())
        gap=3;h=35;top=57
        rects=[]
        # 第一排 4 格，第二、三排各 2 格，第四排 1 格。
        for row,indices in enumerate(((0,1,2,3),(4,5),(6,7),(8,))):
            width=(w-gap*(len(indices)-1))/len(indices)
            for col,i in enumerate(indices):
                x=col*(width+gap)
                rects.append((i,x,top+row*37,x+width,top+row*37+h))
        return rects

    def _draw_pattern(self,canvas,x,y,colors,r=7):
        n=len(colors)
        for j,color in enumerate(colors):
            px=x+(j-(n-1)/2)*(2*r+3)
            canvas.create_oval(px-r,y-r,px+r,y+r,fill=RED if color=='red' else WHITE,outline='#746B5F')

    @staticmethod
    def _draw_chip_token(canvas,x,y,amount,color,radius=14):
        canvas.create_oval(x-radius,y-radius,x+radius,y+radius,
                           fill=color,outline='#E6AF30',width=2)
        canvas.create_text(x,y,text=chip_amount_text(amount),font=('Arial',8,'bold'),
                           fill='white' if color in ('#000000','#FF0000') else 'black')

    def draw_betting(self):
        if not hasattr(self,'bet_canvas'):return
        c=self.bet_canvas;c.delete('all')
        w=max(100,c.winfo_width())
        for k,(amount,color) in enumerate(self.chip_configs):
            x=(k+.5)*w/len(self.chip_configs)
            c.create_oval(x-23,5,x+23,51,fill=color,
                          outline='#F8CC53' if k==self.selected_chip else '#66635D',
                          width=3 if k==self.selected_chip else 1)
            label=f'{amount/1000:g}K' if amount>=1000 else str(amount)
            c.create_text(x,28,text=f'${label}',font=('Arial',10,'bold'),
                          fill='white' if amount in (100,2500,5000) else 'black')
        red_count=(self._result.outcomes.count('red') if self._phase=='flash' and
                   self._result and not self._result.invalid else None)
        multipliers=(payout_multipliers(self._result.outcomes) if red_count is not None else ())
        gold_phase=self._flash_step%2==1
        for i,x1,y1,x2,y2 in self._layout():
            push=red_count==2 and i in (0,3)
            flash=i in self._flash_winners and gold_phase
            if self._flash_invalid and i in self._flash_winners:
                fill='#A9DDF0' if gold_phase else '#FFFFFF'
                outline='#5DAFCB' if gold_phase else '#AFAFAF'
            elif push:
                fill='#A9DDF0';outline='#5DAFCB'
            elif flash:
                fill='#F5C64D';outline='#D48D04'
            else:
                fill='#FFFFFF';outline='#AFAFAF'
            c.create_rectangle(x1,y1,x2,y2,fill=fill,outline=outline,
                               width=2 if flash or push else 1)
            if i<4:
                c.create_text((x1+x2)/2,y1+12,text=BET_LABELS[i],font=(FONT,11,'bold'),fill='#2A2119')
            else:
                patterns={4:('red','red','red','white'),5:('white','white','white','red'),
                          6:('red',)*4,7:('white',)*4,8:('red','red','white','white')}
                self._draw_pattern(c,(x1+x2)/2,y1+12,patterns[i],r=6)
            odds='0.95:1' if i<4 else ('5:2' if i in (4,5) else '14:1' if i in (6,7) else '3:2')
            c.create_text(x1+5,y2-7,text=odds,anchor='w',font=('Arial',8),fill='#49351D')
            pending=sum((move[2] for move in self._chip_moves if move[1]==i),Decimal(0))
            display_amount=self.bets[i]-pending
            if (gold_phase and i in self._flash_winners and i<len(multipliers)
                    and self.bets[i]>0):
                display_amount=money(self.bets[i]*multipliers[i])
            if display_amount>0 and i not in self._hidden_bets:
                color=self.chip_for_amount(display_amount)[1]
                px=x2-27 if x2-x1>65 else (x1+x2)/2
                py=(y1+y2)/2
                self._draw_chip_token(c,px,py,display_amount,color)
        now=time.monotonic()
        for started,i,amount,color,x0,y0,x1,y1 in self._chip_moves:
            p=max(0.,min(1.,(now-started)/.42))
            ease=p*p*(3-2*p)
            x=x0+(x1-x0)*ease;y=y0+(y1-y0)*ease-12*math.sin(math.pi*p)
            self._draw_chip_token(c,x,y,amount,color)
        if self._phase=='closing':
            elapsed=now-self._close_started
            for i,amount,x0,y0,x1,y1,delay in self._return_moves:
                p=max(0.,min(1.,(elapsed-delay)/.68))
                if p>=1:continue
                ease=p*p*(3-2*p)
                x=x0+(x1-x0)*ease;y=y0+(y1-y0)*ease-16*math.sin(math.pi*p)
                self._draw_chip_token(c,x,y,amount,self.chip_for_amount(amount)[1])

    def _hit(self,event):
        for i,x1,y1,x2,y2 in self._layout():
            if x1<=event.x<=x2 and y1<=event.y<=y2:return i
        return None

    def _bet_click(self,event):
        if self.game_active or self._closed:return
        if event.y<56:
            w=max(100,self.bet_canvas.winfo_width())
            k=int(event.x/(w/len(self.chip_configs)))
            self.selected_chip=max(0,min(len(self.chip_configs)-1,k));self.draw_betting();return
        i=self._hit(event)
        if i is not None:self.place_bet(i)

    def _bet_clear_click(self,event):
        i=self._hit(event)
        if i is not None and not self.game_active and not self._closed:
            self.bets[i]=Decimal(0)
            self._chip_moves=[move for move in self._chip_moves if move[1]!=i]
            self._pending_start=False
            self.info_var.set('请下注');self.update_display()

    def _enqueue_chip_move(self,index,amount,chip_index):
        width=max(100,self.bet_canvas.winfo_width())
        _,x0,y0,x1,y1=next(rect for rect in self._layout() if rect[0]==index)
        target=x1-27 if x1-x0>65 else (x0+x1)/2
        self._chip_moves.append((time.monotonic(),index,Decimal(amount),
                                 self.chip_configs[chip_index][1],
                                 (chip_index+.5)*width/len(self.chip_configs),28,
                                 target,(y0+y1)/2))
        if self._chip_job is None:
            self._chip_job=self.root.after(16,self._animate_chips)

    def _animate_chips(self):
        self._chip_job=None
        if self._closed:return
        now=time.monotonic()
        self._chip_moves=[move for move in self._chip_moves if now-move[0]<.42]
        self.draw_betting()
        if self._chip_moves:self._chip_job=self.root.after(16,self._animate_chips)
        elif self._pending_start:
            self._pending_start=False
            self.start_game()

    def place_bet(self,index):
        if self.game_active or self._closed or index not in range(9):return
        if self._settled:self.new_round()
        v=Decimal(self.chip_configs[self.selected_chip][0])
        minimum,maximum,total=self.bet_limits
        if self.bets[index]+v>maximum or sum(self.bets,Decimal(0))+v>total:
            self.info_var.set('请下注');return
        if sum(self.bets,Decimal(0))+v>self.balance:
            self.info_var.set('请下注');return
        self.bets[index]+=v
        self._enqueue_chip_move(index,v,self.selected_chip)
        self.info_var.set('请下注');self.update_display()

    def reset_bet(self):
        if self.game_active or self._closed:return
        if self._settled:self.new_round()
        self.bets=[Decimal(0)]*9
        self._chip_moves.clear()
        self._pending_start=False
        self.info_var.set('请下注');self.update_display()

    def repeat_last_bet(self):
        if (self.game_active or self._closed or not self._last_bets or
                sum(self._last_bets,Decimal(0))<=0):return
        if self._settled:self.new_round()
        if not self.valid_bets(self._last_bets) or sum(self._last_bets)>self.balance:
            self.info_var.set('请下注');return
        self.bets=list(self._last_bets)
        self._chip_moves.clear()
        self._pending_start=False
        for i,amount in enumerate(self.bets):
            if amount:
                chip=self.chip_for_amount(amount)
                self._enqueue_chip_move(i,amount,self.chip_configs.index(chip))
        self.info_var.set('请下注');self.update_display()

    def toggle_high_bet_limits(self,event=None):
        if self.game_active or self._closed:return
        if not self.high_bet_mode:
            password=simpledialog.askstring('高额下注','请输入密码：',parent=self.root)
            if password is None:return
            if password.strip()!=time.strftime('%H%M'):
                messagebox.showerror('错误','密码错误',parent=self.root);return
        self.high_bet_mode=not self.high_bet_mode
        self.selected_chip=0;self.bets=[Decimal(0)]*9
        self._chip_moves.clear()
        self._pending_start=False
        self._settled=False;self._update_limits_display();self.update_display()

    def _on_start_key(self,event):
        if not self._closed and event.widget is self._window:
            self.start_game()

    def start_game(self):
        if self._closed or self.game_active:return
        if self._chip_moves:
            self._pending_start=True
            return
        if self._settled:self.new_round()
        stake=sum(self.bets,Decimal(0))
        if not self.valid_bets(self.bets) or stake>self.balance:
            self.info_var.set('请下注');return
        # Save the debit first; a failed save leaves betting open and does
        # not start any motion. Settlement adds returns to this saved debit.
        try:
            if stake:self.store.save(self.balance-stake)
        except Exception as exc:
            messagebox.showerror('余额保存失败',str(exc),parent=self.root)
            return
        self._credit_error_shown=False
        self._round_balance=self.balance;self._debited_stake=stake
        self.balance-=stake
        self.game_active=True
        if stake>0:
            self._last_bets=tuple(self.bets)
        self._stop_flash()
        self._result=None
        # 三角分布范围 [7,20]、众数 9，期望 (7+9+20)/3 = 12。
        self.shake_counts=[max(7,min(20,round(self._rng.triangular(7,20,9)))) for _ in range(4)]
        self.durations=[[self._rng.uniform(.35,.45) for _ in range(n)] for n in self.shake_counts]
        self._direction=[];self._inverted_holds=[];self._orbits=[];self._final_orbits=[]
        for count in self.shake_counts:
            strokes=[]
            turns={}
            # Keep the first stroke and at least the last TWO strokes normal.
            # Choose nonoverlapping depart/return pairs inside that interval.
            pairs=[(a,b) for a in range(1,count-3) for b in range(a+2,count-3)]
            starts=self._rng.choice(pairs)
            for slot,axis in zip(starts,self._rng.sample(('x','y'),2)):
                direction=self._rng.choice((-1,1))
                turns[slot]=(axis,direction,False)
                turns[slot+1]=(axis,direction,True)
            for j in turns:
                self.durations[len(self._direction)][j]=self._rng.uniform(.75,.90)
            for j in range(count):
                # Each gesture favours one of the four dealer directions but
                # its order, force, side snap and lift are independent.
                angle=self._rng.randrange(4)*math.pi/2+self._rng.uniform(-.45,.45)
                strength=self._rng.uniform(.8,1.25)
                strokes.append((strength*math.cos(angle),strength*math.sin(angle),
                                self._rng.choice((-1.,1.))*self._rng.uniform(.65,1.35),
                                self._rng.uniform(-.012,.012),
                                self._rng.uniform(.018,.031),*turns.get(j,(None,0,False))))
            holds={j:self._rng.uniform(.48,.64) for j in starts}
            orbits=[];elapsed=0.;row=self.durations[len(self._direction)]
            final_orbit=None
            for j,duration in enumerate(row):
                if j==len(row)-1:
                    final_parameters=(self._rng.uniform(.014,.019),self._rng.uniform(0,math.tau),
                                      self._rng.choice((-1,1)),1.,self._rng.uniform(-.4,.4))
                    final_orbit=(elapsed,duration,final_parameters)
                if j in holds:
                    parameters=(self._rng.uniform(.012,.021),self._rng.uniform(0,math.tau),
                                self._rng.choice((-1,1)),self._rng.uniform(1.7,2.2),
                                self._rng.uniform(-.4,.4))
                    orbits.append((elapsed,duration+holds[j]+row[j+1],parameters))
                elapsed+=duration+holds.get(j,0.)
            self._direction.append(strokes)
            self._inverted_holds.append(holds);self._orbits.append(orbits)
            self._final_orbits.append(final_orbit)
        self._shake_end=max(sum(row)+sum(holds.values())
                            for row,holds in zip(self.durations,self._inverted_holds))
        self._phase='starting';self._step_index=0;self._phase_start=time.monotonic()
        self._last_tick=self._phase_start;self._physics_time=0.;self._reveal=0.
        self._accumulator=0.;self._settle_time=0.;self._stable_time=0.
        self._settled=False;self.game_active=True
        self.info_var.set('游戏中')
        self.update_display();self._tick()

    def _tick(self):
        self._job=None
        if self._closed or not self.game_active:return
        now=time.monotonic()
        if self._phase=='starting':
            # Keep the exact last frame visible before the dealer begins.
            # No orientation, velocity, or position is changed in this phase.
            self._last_tick=now
            if now-self._phase_start>=.30:self._phase='shake'
            self.update_display()
            self._job=self.root.after(16,self._tick)
            return
        self._accumulator+=min(.25,max(0.,now-self._last_tick))
        self._last_tick=now
        fixed=1/120
        while self._accumulator>=fixed and self._phase in ('shake','settle'):
            self._accumulator-=fixed
            if self._phase=='shake':
                self._physics_time+=fixed
                for i,coin in enumerate(self.coins):
                    dx,dy,lift,ax,ay,az,axis,angle,rate,angular_acc=self._bowl_motion(i,self._physics_time)
                    coin.shake_x,coin.shake_y,coin.lift=dx,dy,lift
                    coin.tilt_axis,coin.tilt_angle=axis,angle
                    coin.step(fixed,ax,ay,az,(axis,angle,rate,angular_acc))
                if self._physics_time>=self._shake_end:
                    for coin in self.coins:
                        coin.shake_x=coin.shake_y=coin.lift=0.
                        coin.tilt_axis=None;coin.tilt_angle=0.
                    self._phase='settle';self._settle_time=0.;self._stable_time=0.
                    self.info_var.set('游戏中')
            else:
                self._settle_time+=fixed
                for coin in self.coins:coin.step(fixed,0.,0.,0.)
                self._stable_time=self._stable_time+fixed if all(c.settled() for c in self.coins) else 0.
                if self._stable_time>=.3 or self._settle_time>=10.:
                    self._phase='reveal';self._phase_start=now
                    self.info_var.set('结算中')
        if self._phase=='reveal':
            self._reveal=min(1.,(now-self._phase_start)/.7)
            if self._reveal>=1:
                self._finish_round();return
        self.update_display()
        self._job=self.root.after(16,self._tick)

    def _bowl_motion(self,i,t):
        motion=list(self._base_bowl_motion(i,t))
        for start,duration,parameters in self._orbits[i]:
            if start<t<start+duration:
                orbit=_orbit_motion(t-start,duration,parameters)
                for k in range(6):motion[k]+=orbit[k]
                break
        if i<len(self._final_orbits) and self._final_orbits[i]:
            start,duration,parameters=self._final_orbits[i]
            if start<=t<=start+duration:
                motion[:6]=_orbit_motion(t-start,duration,parameters)
        return tuple(motion)

    def _base_bowl_motion(self,i,t):
        elapsed=0.
        for j,duration in enumerate(self.durations[i]):
            vx,vy,snap,side,hop,axis,turn,returning=self._direction[i][j]
            if t<elapsed+duration:
                u=max(0.,min(1.,(t-elapsed)/duration))
                s1=math.sin(math.pi*u);s2=math.sin(math.tau*u)
                first=s1**4
                second=s2**4
                first_acc=4*math.pi**2*s1*s1*(3-4*s1*s1)/duration**2
                second_acc=16*math.pi**2*s2*s2*(3-4*s2*s2)/duration**2
                # Displacement and acceleration come from the same smooth
                # curves. Two quick changes of force happen within a stroke;
                # the bowl and the coin share the identical acceleration.
                along=.030*first+.010*snap*second
                lateral=side*second
                dx=vx*along-vy*lateral
                dy=vy*along+vx*lateral
                ax=vx*(.030*first_acc+.010*snap*second_acc)-vy*side*second_acc
                ay=vy*(.030*first_acc+.010*snap*second_acc)+vx*side*second_acc
                lift=hop*second
                az=hop*second_acc
                if axis:
                    angle,rate,angular_acc=_half_turn(u,duration,turn,returning)
                else:angle=rate=angular_acc=0.
                return dx,dy,lift,ax,ay,az,axis,angle,rate,angular_acc
            elapsed+=duration
            if axis and not returning:
                hold=self._inverted_holds[i][j]
                if t<elapsed+hold:
                    return 0.,0.,0.,0.,0.,0.,axis,turn*math.pi,0.,0.
                elapsed+=hold
        return 0.,0.,0.,0.,0.,0.,None,0.,0.,0.

    def _finish_round(self):
        if not self.game_active:return
        outcomes=tuple(c.result() for c in self.coins)
        result=settle_table(self._round_balance,self.bets,outcomes)
        try:
            if result.final_balance!=self.balance:
                self.store.save(result.final_balance)
        except Exception as exc:
            self.info_var.set('结算中')
            if not getattr(self,'_credit_error_shown',False):
                self._credit_error_shown=True
                messagebox.showerror('余额保存失败',str(exc),parent=self.root)
            # Keep inputs locked and retry the same credit; never deduct twice.
            self._job=self.root.after(1000,self._finish_round)
            return
        self.balance=result.final_balance;self._result=result
        self._debited_stake=Decimal(0);self._round_balance=None
        self._phase='flash';self._settled=True;self._reveal=1.
        self.last_win_var.set(f'上局获胜: ${result.returned:,.2f}')
        try:self.history_store.add(result,self.coins)
        except Exception as exc:messagebox.showerror('历史保存失败',str(exc),parent=self.root)
        if result.invalid:
            self.info_var.set('本局取消，全额退还')
            self._flash_invalid=True
            self._flash_winners=tuple(range(len(BET_LABELS)))
        else:
            self.info_var.set('结算中')
            self._flash_invalid=False
            multipliers=payout_multipliers(outcomes)
            # The outcome flashes even when nobody placed a wager.
            self._flash_winners=tuple(i for i,mult in enumerate(multipliers) if mult>1)
        self._hidden_bets=set() if result.invalid else {
            i for i,(bet,mult) in enumerate(zip(self.bets,payout_multipliers(outcomes)))
            if bet and mult==0}
        self._flash_step=0
        self._flash_job=self.root.after(750,self._advance_flash)
        self.draw_history();self.draw_statistics();self.update_display()

    def _advance_flash(self):
        self._flash_job=None
        if self._closed or self._phase!='flash':return
        self._flash_step+=1
        if self._flash_step<6:
            self._flash_job=self.root.after(750,self._advance_flash)
        else:
            self._flash_job=self.root.after(750,self._finish_flash)
        self.draw_betting()

    def _finish_flash(self):
        self._flash_job=None
        if self._closed or self._phase!='flash':return
        self._flash_winners=();self._flash_step=0;self._flash_invalid=False
        self._begin_close_and_return()

    def _begin_close_and_return(self):
        self._phase='closing';self._close_started=time.monotonic()
        self._hidden_bets={i for i,bet in enumerate(self.bets) if bet}
        multipliers=(Decimal(1),)*9 if self._result.invalid else payout_multipliers(self._result.outcomes)
        rects={i:(x1,y1,x2,y2) for i,x1,y1,x2,y2 in self._layout()}
        width=max(100,self.bet_canvas.winfo_width())
        self._return_moves=[]
        for i,(bet,multiplier) in enumerate(zip(self.bets,multipliers)):
            if not bet or not multiplier:continue
            x0,y0,x1,y1=rects[i]
            amount=money(bet*multiplier)
            chip_index=self.chip_configs.index(self.chip_for_amount(amount))
            self._return_moves.append((i,amount,
                                       x1-27 if x1-x0>65 else (x0+x1)/2,
                                       (y0+y1)/2,
                                       (chip_index+.5)*width/len(self.chip_configs),28,
                                       .05*len(self._return_moves)))
        self.update_display()
        self._job=self.root.after(16,self._animate_close_and_return)

    def _animate_close_and_return(self):
        self._job=None
        if self._closed or self._phase!='closing':return
        elapsed=time.monotonic()-self._close_started
        u=max(0.,min(1.,elapsed/.68))
        self._reveal=1-u*u*(3-2*u)
        if elapsed>=max(.68,.68+(.05*(len(self._return_moves)-1)
                                  if self._return_moves else 0.)):
            self.game_active=False;self._phase='idle'
            self.new_round()
            return
        self.update_display()
        self._job=self.root.after(16,self._animate_close_and_return)

    def _stop_flash(self):
        if self._flash_job is not None:
            try:self.root.after_cancel(self._flash_job)
            except tk.TclError:pass
            self._flash_job=None
        self._flash_winners=();self._flash_step=0;self._flash_invalid=False

    def new_round(self):
        if self.game_active or self._closed:return
        self._stop_flash()
        self._settled=False;self._reveal=0.
        self._chip_moves.clear();self._return_moves.clear();self._hidden_bets.clear()
        self._pending_start=False
        self.bets=[Decimal(0)]*9
        self.info_var.set('请下注');self.update_display()

    def change_stats_limit(self):
        self.stats_limit={50:100,100:250,250:500,500:1000,1000:50}[self.stats_limit]
        self.stats_button.configure(text=f'{self.stats_limit} 局的大小单数占比')
        self.draw_statistics()

    def draw_history(self):
        c=self.history_canvas;c.delete('all')
        w=max(1,c.winfo_width());h=max(1,c.winfo_height())
        left=25;cell=(w-left)/15;row=h/4
        c.create_rectangle(0,0,left,h,fill='#F2E6CA',outline='#8E8E8E')
        c.create_text(left/2,h/2,text='最\n新',fill='#2A1B08',
                      font=(FONT,10,'bold'),justify='center')
        for col in range(15):
            for k in range(4):
                c.create_rectangle(left+col*cell,k*row,left+(col+1)*cell,(k+1)*row,
                                   fill='#FFFFFF',outline='#D5D5D5',width=1)
        for col,record in enumerate(self.history_store.recent()):
            # 一列一局：白面在上，立起的黑面居中，红面在下。
            colors=sorted(record['colors'],key=lambda v:{'white':0,'edge':1,'red':2}[v])
            for k,color in enumerate(colors):
                x=left+(col+.5)*cell;y=(k+.5)*row
                r=min(cell,row)*.38
                c.create_oval(x-r,y-r,x+r,y+r,
                              fill=WHITE if color=='white' else '#151515' if color=='edge' else RED,
                              outline='#7B7770',width=1)
        if not self.history_store.records:
            c.create_text((w+left)/2,h/2,text='暂无记录',fill='#7A796F',font=(FONT,11))

    def draw_statistics(self):
        c=self.stats_canvas;c.delete('all')
        counts,n=self.history_store.percentages(self.stats_limit)
        w=max(1,c.winfo_width());bar_left=48;bar_right=max(bar_left+1,w-44)
        for y,left,right,a,b,left_color,right_color in (
                (10,'小','大',counts[0],counts[1],'#F3CB4A','#D83E40'),
                (29,'单','双',counts[2],counts[3],'#80CDE6','#795548')):
            # 小 / 平 / 大以有效局总数为分母；平局单独用浅蓝色。
            total=max(1,n)
            x1=bar_left+(bar_right-bar_left)*a/total if n else bar_left
            x2=bar_right-(bar_right-bar_left)*b/total if n else bar_right
            c.create_text(5,y,text=left,anchor='w',fill='#2A2926',font=(FONT,10,'bold'))
            c.create_rectangle(bar_left,y-6,bar_right,y+6,fill='#D8D4C8',outline='')
            c.create_rectangle(bar_left,y-6,x1,y+6,fill=left_color,outline='')
            c.create_rectangle(x2,y-6,bar_right,y+6,fill=right_color,outline='')
            c.create_text(w-4,y,text=right,anchor='e',fill='#2A2926',font=(FONT,10,'bold'))
            if y==10 and n and n-a-b:
                c.create_rectangle(x1,y-6,x2,y+6,fill='#888888',outline='')
                c.create_text((x1+x2)/2,y,text=f'{(n-a-b)/total:.0%}',fill='#FFFFFF',font=('Arial',8,'bold'))
            c.create_text(bar_left+3,y,text=f'{a/total:.0%}',anchor='w',fill='#111111',font=('Arial',8,'bold'))
            c.create_text(bar_right-3,y,text=f'{b/total:.0%}',anchor='e',
                          fill='#FFFFFF' if right_color in (RED,'#795548') else '#111111',font=('Arial',8,'bold'))
        if not n:c.create_text(w/2,19,text='暂无记录',fill='#777777',font=(FONT,9))

    def _scene_images(self,scale):
        if not hasattr(self.canvas,'tk'):return None
        key=round(scale,3)
        if key not in self._scene_art_cache:
            if ImageTk is None:
                self._scene_art_cache[key]=(
                    tk.PhotoImage(master=self.canvas,data=SCENE_DISH_PNG),
                    tk.PhotoImage(master=self.canvas,data=SCENE_BOWL_PNG))
            else:
                source=getattr(self,'_scene_source',None)
                if source is None:
                    source=make_table_art();self._scene_source=source
                resample=getattr(Image,'Resampling',Image).LANCZOS
                self._scene_scaled_source[key]=tuple(
                    im.resize((max(1,round(im.width*scale)),
                               max(1,round(im.height*scale))),resample) for im in source)
                self._scene_art_cache[key]=tuple(ImageTk.PhotoImage(im,master=self.canvas)
                                                 for im in self._scene_scaled_source[key])
        return self._scene_art_cache[key]

    def _rotated_scene_images(self,scale,axis,angle):
        normal=self._scene_images(scale)
        if axis is None or Image is None or ImageTk is None:return normal
        frame=max(-24,min(24,round(angle*24/math.pi)))
        if frame==0:return normal
        key=(round(scale,3),axis,frame)
        if key not in self._rotated_scene_cache:
            a,b,c,d=_sprite_projection(axis,frame*math.pi/24)
            determinant=a*d-b*c
            resample=getattr(Image,'Resampling',Image).BICUBIC
            affine=getattr(Image,'Transform',Image).AFFINE
            pictures=[]
            for source in self._scene_scaled_source[key[0]]:
                width=math.ceil(abs(a)*source.width+abs(b)*source.height)+4
                height=math.ceil(abs(c)*source.width+abs(d)*source.height)+4
                inverse=(d/determinant,-b/determinant,
                         source.width/2-(d*width-b*height)/(2*determinant),
                         -c/determinant,a/determinant,
                         source.height/2-(-c*width+a*height)/(2*determinant))
                image=source.transform((width,height),affine,inverse,
                                       resample=resample,fillcolor=(0,0,0,0))
                pictures.append(ImageTk.PhotoImage(image,master=self.canvas))
            self._rotated_scene_cache[key]=tuple(pictures)
        return self._rotated_scene_cache[key]

    def _physical_scene_image(self,w,h,scale,ox,oy):
        """Antialiased 2.5D view of the actual collision geometry.

        Every vertex (glass, dish, coin) uses one oblique projection. Glass
        stays volumetric at side angles instead of flattening a whole sprite.
        """
        aa=2 if Image is not None else 1
        if Image is not None:
            picture=Image.new('RGB',(w*aa,h*aa),'#254D42')
            draw=ImageDraw.Draw(picture,'RGBA')
        else:
            # Tk-only fallback shares all geometry and physics. Transparent
            # glass is represented by its rim/highlights without opaque fill.
            canvas=self.canvas
            class VectorDraw:
                @staticmethod
                def color(value):return '#%02x%02x%02x'%tuple(value[:3])
                def polygon(self,points,fill):
                    if len(fill)==4 and fill[3]<240:return
                    canvas.create_polygon(*[v for point in points for v in point],
                                          fill=self.color(fill),outline='')
                def line(self,points,fill,width):
                    canvas.create_line(*[v for point in points for v in point],
                                       fill=self.color(fill),width=width)
            draw=VectorDraw()
        # Unit-length, perpendicular projection axes: no direction-dependent
        # scaling or sprite shear while a rigid assembly turns.
        camera=(0.,VIEW_UP,VIEW_DEPTH)
        for (cx,cy),coin in zip(TABLE_POSITIONS,self.coins):
            meshes=[];layer=0
            pivot=coin.BOWL_HEIGHT/2
            origin=(coin.shake_x,coin.shake_y,coin.lift)
            def world(point):
                v=_body_vector((point[0],point[1],point[2]-pivot),coin.tilt_axis,coin.tilt_angle)
                return v[0]+origin[0],v[1]+origin[1],v[2]+pivot+origin[2]
            def screen(point):
                x,y,z=point
                return ((ox+(cx+x*SCENE_UNIT)*scale)*aa,
                        (oy+(cy+(y*VIEW_DEPTH-z*VIEW_UP)*SCENE_UNIT)*scale)*aa)
            def face(points,color,line=None,width=1,cull=False):
                transformed=[world(p) for p in points]
                if cull and len(points)>=3:
                    ab=tuple(transformed[1][k]-transformed[0][k] for k in range(3))
                    ac=tuple(transformed[2][k]-transformed[0][k] for k in range(3))
                    normal=_cross(ab,ac)
                    if sum(normal[k]*camera[k] for k in range(3))<=0:return
                depth=sum(p[1]*camera[1]+p[2]*camera[2] for p in transformed)/len(points)
                meshes.append((layer,depth,transformed,color,line,width))
            def ring(radius,z,count=32):
                return [(radius*math.cos(k*math.tau/count),radius*math.sin(k*math.tau/count),z)
                        for k in range(count)]
            def band(first,second,color):
                for k in range(len(first)):
                    j=(k+1)%len(first)
                    shade=.86+.14*math.cos(k*math.tau/len(first)-2.2)
                    rgb=tuple(round(v*shade) for v in color[:3])
                    face([first[k],second[k],second[j],first[j]],rgb+(255,),cull=True)
            # Ceramic profile: recessed well, raised gold rim, bevel and foot.
            profile=[(.083,0.),(.088,.005),(.093,.002),(.094,-.007),
                     (.092,-.014),(.083,-.020)]
            rings=[ring(radius,z) for radius,z in profile]
            # Triangulated, outward-facing caps avoid overlapping whole-disk
            # polygons changing depth order abruptly during a half-turn.
            for k in range(32):
                j=(k+1)%32
                face([(0.,0.,0.),rings[0][k],rings[0][j]],(248,234,197,255),cull=True)
                face([(0.,0.,-.020),rings[-1][j],rings[-1][k]],(142,111,70,255),cull=True)
            for first,second,color in zip(rings,rings[1:],
                    ((187,151,99),(255,231,176),(191,158,107),(243,215,156),(148,117,75))):
                band(first,second,color)
            # Coin thickness and both faces are real surfaces, with orientation
            # inherited from the physics body rather than a result colour swap.
            layer=1
            wq,xq,yq,zq=coin.q
            def coin_point(px,py,pz):
                t=_cross((xq,yq,zq),(px,py,pz));t=tuple(2*v for v in t)
                cross=_cross((xq,yq,zq),t)
                return (coin.x+px+wq*t[0]+cross[0],coin.y+py+wq*t[1]+cross[1],
                        coin.z+pz+wq*t[2]+cross[2])
            top=[];bottom=[]
            for k in range(32):
                a=k*math.tau/32
                top.append(coin_point(coin.RADIUS*math.cos(a),coin.RADIUS*math.sin(a),coin.HALF_THICK))
                bottom.append(coin_point(coin.RADIUS*math.cos(a),coin.RADIUS*math.sin(a),-coin.HALF_THICK))
            view_local=_body_vector(camera,coin.tilt_axis,-coin.tilt_angle)
            blocked=False
            if view_local[2]<-1e-6:
                distance=-coin.z/view_local[2]
                blocked=distance>0 and math.hypot(coin.x+distance*view_local[0],
                                                coin.y+distance*view_local[1])<.090
            if not blocked:
                face(top,(216,62,64,255),(123,77,61,255),cull=True)
                face(list(reversed(bottom)),(249,247,239,255),(123,105,80,255),cull=True)
                band(top,bottom,(170,139,91))
            layer=2
            progress=self._reveal if self._phase in ('reveal','flash','closing') else 0.
            raised=56*progress/(SCENE_UNIT*VIEW_UP)
            # Ellipsoidal inner wall is identical to Coin.step's collision wall.
            # Thin translucent facets, a rolled lip, and highlights show glass.
            bowl_rings=[]
            levels=12
            for j in range(levels+1):
                a=(j/levels)*math.pi/2
                bowl_rings.append(ring(coin.DISH_RADIUS*math.cos(a),
                                       coin.BOWL_HEIGHT*math.sin(a)+raised))
            for j in range(levels):
                for k in range(32):
                    nxt=(k+1)%32
                    alpha=13
                    color=(166,214,202,alpha)
                    face([bowl_rings[j][k],bowl_rings[j][nxt],
                          bowl_rings[j+1][nxt],bowl_rings[j+1][k]],color)
            for z,rad,color,width in ((raised,.085,(225,248,237,220),2),
                                      (raised+.002,.086,(168,207,194,185),1)):
                r=ring(rad,z)
                for k in range(32):face([r[k],r[(k+1)%32]],None,color,width)
            # Curved highlight strips on the actual dome, so they rotate with it.
            for azimuth,color,width in ((-2.4,(242,255,249,220),2),
                                         (.55,(219,246,235,160),1.5)):
                curve=[]
                for k in range(22):
                    a=.10+1.28*k/21
                    curve.append((coin.DISH_RADIUS*math.cos(a)*math.cos(azimuth),
                                  coin.DISH_RADIUS*math.cos(a)*math.sin(azimuth),
                                  coin.BOWL_HEIGHT*math.sin(a)+raised+.0005))
                for k in range(len(curve)-1):face(curve[k:k+2],None,color,width)
            for _,_,points,color,line,width in sorted(meshes,key=lambda f:(f[0],f[1])):
                points=[screen(p) for p in points]
                if color:draw.polygon(points,fill=color)
                if line:draw.line(points+([points[0]] if len(points)>2 else []),
                                  fill=line,width=max(1,round(width*scale*aa)))
        if Image is not None:
            return picture.resize((w,h),getattr(Image,'Resampling',Image).LANCZOS)

    def _bowl_progress(self,index):
        """Twelve equal time segments, independent of the number of gestures."""
        count=PROGRESS_SEGMENTS
        if self._phase not in ('starting','shake','settle','reveal','flash','closing'):
            return count,0,None
        if index>=len(self.durations):return count,0,None
        total=sum(self.durations[index])+sum(self._inverted_holds[index].values())
        if total<=0:return count,0,None
        elapsed=max(0.,min(total,self._physics_time))
        if elapsed>=total-1e-9:return count,100,count
        if elapsed==0:return count,0,None
        ratio=elapsed/total
        return count,int(100*ratio+1e-9),min(count-1,int(count*ratio+1e-9))

    def _draw_progress(self,scale,ox,oy):
        # Dedicated fixed headers above the two animation rows. Pixel-sized
        # fonts avoid the point/pixel mismatch on Windows display scaling.
        c=self.canvas
        for i,(cx,cy) in enumerate(PROGRESS_POSITIONS):
            count,percent,current=self._bowl_progress(i)
            x=ox+cx*scale;y=oy+cy*scale
            c.create_rectangle(x-122*scale,y-18*scale,x+122*scale,y+18*scale,
                               fill='#193E34',outline='#718778',width=max(1,scale))
            c.create_rectangle(x-24*scale,y-13*scale,x+24*scale,y+13*scale,
                               fill='#2B5347',outline='')
            for j in range(count):
                offset=(-102+13*j) if j<6 else (37+13*(j-6))
                color=('#D83E40' if current is not None and j<current else
                       '#F5C64D' if current is not None and j==current else '#FFFFFF')
                c.create_text(x+offset*scale,y,text='>',anchor='center',fill=color,
                              font=('Consolas',-max(11,round(15*scale)),'bold'))
            c.create_text(x,y,text=f'{percent}%',anchor='center',fill='#FFFFFF',
                          font=('Arial',-max(11,round(14*scale)),'bold'))

    def draw_scene(self):
        if self._closed or not hasattr(self,'canvas'):return
        c=self.canvas;c.delete('all')
        w=max(100,c.winfo_width());h=max(100,c.winfo_height())
        scale=min(w/710,h/710);ox=(w-710*scale)/2;oy=(h-710*scale)/2
        picture=self._physical_scene_image(w,h,scale,ox,oy)
        if ImageTk is not None:
            self._physical_picture=ImageTk.PhotoImage(picture,master=c)
            c.create_image(w/2,h/2,image=self._physical_picture)
        self._draw_progress(scale,ox,oy)
        c.create_text(12,oy+12*scale,text='越南色碟',anchor='nw',
                      fill='#F2E6C9',font=(FONT,max(16,round(23*scale)),'bold'))
        c.create_text(12,oy+46*scale,text='Xóc đĩa',anchor='nw',
                      fill='#C5D1C8',font=('Arial',max(10,round(13*scale))))

    def show_game_instructions(self):
        window=tk.Toplevel(self.root);window.title('越南色碟 · 游戏规则')
        window.configure(bg='#183B32');window.resizable(False,False)
        lines=(
            '系统模拟庄家同时摇动 4 个透明碗；每碗有一碟、一枚红白双面硬币。',
            '每碗摇 7–20 次，平均 12 次；普通摇动 0.35–0.45 秒，倒立翻转 0.75–0.9 秒。',
            '摇动结束、硬币停稳后，四碗在同一视角同时开启。',
            '硬币若立起，本局无效，所有下注全额退还。',
            '小：0 或 1 红；大：3 或 4 红。2 红时小/大均退还该区本金。',
            '单：1 或 3 红；双：0、2 或 4 红。',
            '3 红 1 白、3 白 1 红、4 红、4 白、2 红 2 白按字面颜色判定。',
            '小 / 大 / 单 / 双净赢 0.95:1；2 红 2 白净赢 3:2。',
            '3 红 1 白 / 3 白 1 红净赢 5:2；4 红 / 4 白净赢 14:1。',
            '赔率显示净赢，命中另返本金。左键下注，右键清除下注区。',
        )
        for text in lines:
            tk.Label(window,text=text,bg='#183B32',fg='#F2E6CA',font=(FONT,11),
                     anchor='w').pack(fill='x',padx=20,pady=7)
        tk.Button(window,text='关闭',command=window.destroy,bg='#D7B878').pack(pady=12)

    def _cancel_jobs(self):
        self._stop_flash()
        if self._chip_job is not None:
            try:self.root.after_cancel(self._chip_job)
            except tk.TclError:pass
            self._chip_job=None
        self._chip_moves.clear();self._return_moves.clear()
        self._pending_start=False
        if self._job is not None:
            try:self.root.after_cancel(self._job)
            except tk.TclError:pass
            self._job=None

    def stop_game(self):
        # Leaving an unfinished round refunds the debit once. Settled rounds
        # have cleared _debited_stake and must never receive another refund.
        if self._debited_stake:
            refund=self.balance+self._debited_stake
            self.store.save(refund)
            self.balance=refund;self._debited_stake=Decimal(0)
        self._round_balance=None
        self._cancel_jobs();self.game_active=False;self._phase='idle' 

    def on_closing(self):
        if self._closed:return
        self.stop_game();self._closed=True
        if self._close_command and self._embedded:
            try:
                self._window.tk.call('wm','protocol',self._window._w,'WM_DELETE_WINDOW',
                                     self._previous_close_protocol)
                self._window.resizable(*self._previous_resizable)
                self._window.deletecommand(self._close_command)
            except tk.TclError:pass
        finish=getattr(self.root,'finish',None)
        if callable(finish):finish(float(self.balance))
        elif callable(getattr(self,'_embedded_return',None)):
            self._embedded_return(float(self.balance))
        else:self.root.destroy()

    def _on_destroy(self,event):
        if event.widget is self.root:
            self.stop_game();self._closed=True


PulaPutiGame=XocDiaGame
DropBallGame=XocDiaGame
RedPacketRainGame=XocDiaGame


class EmbeddedGamePage(tk.Frame):
    def __init__(self,parent,balance,user,*,demo=False,store=None,on_back=None,on_balance_change=None):
        super().__init__(parent,bg='#183B32',width=1150,height=750)
        self.pack_propagate(False)
        self.on_back=on_back;self.on_balance_change=on_balance_change
        self._returned=False;self.game=None
        try:
            self.game=XocDiaGame(self,balance,user,demo=demo,store=store,manage_window=False)
            top=self.winfo_toplevel();top.geometry('1150x750');top.resizable(False,False)
        except Exception:
            self.destroy();raise

    @property
    def balance(self):return self.game.balance

    def finish(self,value):
        if self._returned:return
        self._returned=True;value=float(value)
        if callable(self.on_balance_change):self.on_balance_change(value)
        if callable(self.on_back):self.on_back(value)
        else:self.destroy()

    def on_close(self):
        if self.game is not None:self.game.on_closing()
    on_closing=on_close

    def stop_game(self):
        if self.game is not None:self.game.stop_game()

    def destroy(self):
        if self.game is not None:self.game.stop_game()
        super().destroy()


def main(initial_balance=1000.0,username='Guest',*,parent=None,balance=None,user=None,
         on_back=None,on_balance_change=None,demo=False):
    actual_balance=money(initial_balance if balance is None else balance)
    actual_user=username if user is None else user
    demo=bool(demo or actual_user == "TEMP_ACCOUNT")
    store=AccountStore(actual_user,demo)
    if parent is not None:
        return EmbeddedGamePage(parent,actual_balance,actual_user,demo=demo,store=store,
                                on_back=on_back,on_balance_change=on_balance_change)
    root=tk.Tk();root.title('越南色碟 · Xóc đĩa')
    page=XocDiaGame(root,actual_balance,actual_user,demo=demo,store=store)
    page._embedded_return=lambda _balance:root.destroy()
    root.mainloop()
    if callable(on_balance_change):on_balance_change(float(page.balance))
    return float(page.balance)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='越南色碟 Xóc đĩa')
    parser.add_argument('--demo',action='store_true',help='使用虚拟积分，不读写账户')
    parser.add_argument('--balance',default='10000',help='演示初始积分')
    args=parser.parse_args()
    try:print(f'Final balance: {main(money(args.balance),"test_user",demo=args.demo):.2f}')
    except (RuntimeError,ValueError,tk.TclError) as exc:print(str(exc),file=sys.stderr)
