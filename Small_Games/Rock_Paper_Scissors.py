"""Rock Paper Scissors — ChickenCrossing-style warm fixed HMI.

R2 payout model: win returns 1.95x total, draw returns 1.00x total,
loss returns 0. This gives a 98.33% theoretical RTP under uniform outcomes. The UI follows ChickenCrossing_tk.py and supports the project's
single-Tk EmbeddedGamePage mode.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

try:
    from .small_games import EmbeddedGamePage
except ImportError:
    from small_games import EmbeddedGamePage

VERSION = "RPS-ChickenStyle-R2"


class Theme:
    APP_BG = "#C8C1B7"; PANEL = "#E7E1D8"; PANEL_ALT = "#DCD5CB"
    PANEL_HOVER = "#D1C9BE"; CANVAS_BG = "#BFD0C1"
    BORDER = "#9A9185"; BORDER_SOFT = "#B9B0A5"
    TEXT = "#252A2E"; TEXT_MUTED = "#596169"; TEXT_DIM = "#777E83"
    ACCENT = "#345E73"; ACCENT_HOVER = "#294A5A"; ACCENT_SOFT = "#B8CAD2"
    CYAN = "#276E78"; GREEN = "#4E7355"; GREEN_HOVER = "#3D5C43"
    RED = "#A84D4D"; RED_HOVER = "#873D3D"; AMBER = "#A36B22"
    ROCK = "#6C7F8A"; PAPER = "#D7CBAA"; SCISSORS = "#B8756E"
    WIN = "#A9C4A5"; DRAW = "#D7C98F"; LOSS = "#D3A39E"
    TABLE = "#AFC4B1"; TABLE_DARK = "#7C997F"
    FONT = "Segoe UI"
    FONT_CJK = "Microsoft YaHei UI" if sys.platform.startswith("win") else (
        "PingFang SC" if sys.platform == "darwin" else "Noto Sans CJK SC"
    )
    FONT_EMOJI = "Segoe UI Emoji"


CHIP_CONFIGS = (
    ("$5", "5", "#D75A54", "white"),
    ("$25", "25", "#67B56A", "black"),
    ("$100", "100", "#292929", "white"),
    ("$500", "500", "#D47AB7", "black"),
    ("$1K", "1000", "#F4F1EA", "black"),
)
CHOICES = (("✊", "石头", Theme.ROCK), ("✋", "布", Theme.PAPER), ("✌", "剪刀", Theme.SCISSORS))


def get_data_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "../saving_data.json")


def load_user_data() -> list:
    try:
        with open(get_data_file_path(), "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []


def save_user_data(users: list) -> None:
    try:
        with open(get_data_file_path(), "w", encoding="utf-8") as file:
            json.dump(users, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


def update_balance_in_json(username: str, new_balance: float) -> None:
    users = load_user_data()
    for user in users:
        if user.get("user_name") == username:
            user["cash"] = f"{float(new_balance):.2f}"
            save_user_data(users)
            return


class ModernButton(tk.Button):
    def __init__(self, master, *, text: str, command=None, background=Theme.PANEL_HOVER,
                 hover_background=Theme.BORDER, foreground=Theme.TEXT, font_size=12,
                 bold=False, **kwargs):
        self.normal_background = background
        self.hover_background = hover_background
        self.normal_foreground = foreground
        super().__init__(master, text=text, command=command, bg=background, fg=foreground,
                         activebackground=hover_background, activeforeground=foreground,
                         disabledforeground=Theme.TEXT_DIM,
                         font=(Theme.FONT_CJK, font_size, "bold" if bold else "normal"),
                         relief=tk.FLAT, bd=0, highlightthickness=0, cursor="hand2", **kwargs)
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")

    def _enter(self, _event):
        if str(self.cget("state")) != tk.DISABLED:
            super().configure(bg=self.hover_background)

    def _leave(self, _event):
        super().configure(bg=self.normal_background)


class ChipButton(tk.Canvas):
    def __init__(self, master, *, label, amount, chip_color, text_color, command, width=57, height=50):
        super().__init__(master, width=width, height=height, bg=Theme.PANEL, bd=0,
                         highlightthickness=0, cursor="hand2")
        self.label, self.amount, self.chip_color, self.text_color = label, amount, chip_color, text_color
        self.command, self.control_width, self.control_height = command, width, height
        self._state = tk.NORMAL; self._hovered = False; self._pressed = False; self._flash = False
        self._flash_job = None
        self.bind("<Enter>", self._on_enter); self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press); self.bind("<ButtonRelease-1>", self._on_release)
        self.draw()

    @staticmethod
    def _shade(color, factor):
        if not color.startswith("#") or len(color) != 7: return "#4A4A4A"
        rgb = [int(color[i:i+2], 16) for i in (1, 3, 5)]
        rgb = [max(0, min(255, round(v * factor))) for v in rgb]
        return "#%02x%02x%02x" % tuple(rgb)

    def draw(self):
        self.delete("all")
        oy = 3 if self._pressed else 0
        outer = self._shade(self.chip_color, .68); inner = self._shade(self.chip_color, .86)
        outline = Theme.ACCENT if self._flash else (Theme.TEXT if self._hovered else outer)
        ow = 3 if (self._flash or self._hovered) else 2
        self.create_oval(6, 7, self.control_width-5, self.control_height-1, fill="#8E877E", outline="")
        self.create_oval(5, 3+oy, self.control_width-6, self.control_height-5+oy, fill=outer, outline=outline, width=ow)
        self.create_oval(9, 7+oy, self.control_width-10, self.control_height-9+oy, fill=self.chip_color, outline=inner, width=2)
        self.create_oval(14, 12+oy, self.control_width-15, self.control_height-14+oy, fill=self.chip_color, outline=outer, width=1)
        cx = self.control_width/2; cy = (self.control_height-2)/2 + oy
        for x1,y1,x2,y2 in ((cx-3,4+oy,cx+3,10+oy),(cx-3,self.control_height-12+oy,cx+3,self.control_height-6+oy),
                            (6,cy-3,12,cy+3),(self.control_width-13,cy-3,self.control_width-7,cy+3)):
            self.create_rectangle(x1,y1,x2,y2,fill=self.text_color,outline="")
        self.create_text(cx, cy, text=self.label, fill=self.text_color,
                         font=(Theme.FONT, 10 if len(self.label)<=4 else 9, "bold"))
        if self._state == tk.DISABLED:
            self.create_oval(5,3+oy,self.control_width-6,self.control_height-5+oy,
                             fill="#C9C2B8",outline=Theme.BORDER_SOFT,width=1,stipple="gray50")

    def _on_enter(self,_e):
        if self._state != tk.DISABLED: self._hovered=True; self.draw()
    def _on_leave(self,_e): self._hovered=False; self._pressed=False; self.draw()
    def _on_press(self,_e):
        if self._state != tk.DISABLED: self._pressed=True; self.draw()
    def _on_release(self,e):
        if self._state == tk.DISABLED: return
        pressed=self._pressed; self._pressed=False
        if pressed and 0<=e.x<self.control_width and 0<=e.y<self.control_height:
            self._flash=True; self.draw(); self.command(self.amount)
            self._flash_job=self.after(150,self._clear_flash)
        else: self.draw()
    def _clear_flash(self): self._flash=False; self.draw()
    def configure(self, cnf=None, **kwargs):
        state=kwargs.pop("state",None)
        if state is not None:
            self._state=state; self._hovered=False; self._pressed=False
            super().configure(cursor="" if state==tk.DISABLED else "hand2"); self.draw()
        if cnf is not None or kwargs: return super().configure(cnf, **kwargs)
        return None
    config=configure


class MetricTile(tk.Frame):
    def __init__(self, master, label, variable, accent, *, width, height):
        super().__init__(master,width=width,height=height,bg=Theme.PANEL_ALT,
                         highlightthickness=1,highlightbackground=Theme.BORDER_SOFT)
        self.pack_propagate(False); self.grid_propagate(False)
        tk.Label(self,text=label,bg=Theme.PANEL_ALT,fg=Theme.TEXT_MUTED,
                 font=(Theme.FONT_CJK,9),anchor=tk.W).place(x=12,y=8,width=width-24,height=18)
        tk.Label(self,textvariable=variable,bg=Theme.PANEL_ALT,fg=accent,
                 font=(Theme.FONT,15,"bold"),anchor=tk.W).place(x=12,y=29,width=width-24,height=28)


class GestureButton(tk.Canvas):
    def __init__(self, master, *, symbol, label, accent, command, width=226, height=104):
        super().__init__(master,width=width,height=height,bg=Theme.PANEL,bd=0,highlightthickness=0,cursor="hand2")
        self.symbol=symbol; self.label=label; self.accent=accent; self.command=command
        self.control_width=width; self.control_height=height; self.selected=False; self.enabled=True; self.hovered=False
        self.bind("<Enter>",self._enter); self.bind("<Leave>",self._leave); self.bind("<Button-1>",self._click); self.draw()
    def draw(self):
        self.delete("all")
        bg=Theme.ACCENT_SOFT if self.selected else (Theme.PANEL_HOVER if self.hovered and self.enabled else Theme.PANEL_ALT)
        outline=Theme.ACCENT if self.selected else Theme.BORDER_SOFT
        self.create_rectangle(2,2,self.control_width-2,self.control_height-2,fill=bg,outline=outline,width=3 if self.selected else 1)
        self.create_oval(15,14,81,80,fill=self.accent,outline="")
        self.create_text(48,47,text=self.symbol,fill="#FFFFFF",font=(Theme.FONT_EMOJI,30))
        self.create_text(98,34,text=self.label,fill=Theme.TEXT,font=(Theme.FONT_CJK,15,"bold"),anchor=tk.W)
        self.create_text(98,61,text="已选择" if self.selected else "点击选择",
                         fill=Theme.ACCENT if self.selected else Theme.TEXT_MUTED,font=(Theme.FONT_CJK,10,"bold"),anchor=tk.W)
        if not self.enabled:
            self.create_rectangle(2,2,self.control_width-2,self.control_height-2,fill=Theme.PANEL_ALT,
                                  outline=Theme.BORDER_SOFT,stipple="gray50")
    def _enter(self,_e):
        if self.enabled: self.hovered=True; self.draw()
    def _leave(self,_e): self.hovered=False; self.draw()
    def _click(self,_e):
        if self.enabled: self.command(self.symbol)
    def set_selected(self,v): self.selected=v; self.draw()
    def set_enabled(self,v): self.enabled=v; self.configure(cursor="hand2" if v else ""); self.draw()


class RPSGame:
    WINDOW_WIDTH=1150; WINDOW_HEIGHT=750; SHELL_WIDTH=1110; SHELL_HEIGHT=714
    HEADER_HEIGHT=75; BODY_TOP=84; BODY_HEIGHT=630; GAME_PANEL_WIDTH=748; SIDEBAR_WIDTH=348; PANEL_GAP=14
    ACTION_BUTTON_WIDTH=322; ACTION_BUTTON_HEIGHT=30

    def __init__(self, root, initial_balance, username):
        self.root=root; self._configure_root(); self.balance=float(initial_balance); self.username=username
        self.bet_amount=0.0; self.current_bet=0.0; self.last_win=0.0; self.user_choice=None; self.computer_choice=None
        self.game_active=False; self.animation_running=False; self.animation_start_time=0.0; self.animation_duration=0
        self.final_result=None; self.result_hold_job=None
        self.choice_map={"✊":"石头","✌":"剪刀","✋":"布"}
        self.chip_buttons=[]; self.gesture_buttons=[]
        self.balance_var=tk.StringVar(); self.bet_var=tk.StringVar(); self.last_win_var=tk.StringVar()
        self.stage_var=tk.StringVar(value="选择手势"); self.selection_var=tk.StringVar(value="未选择")
        self.computer_var=tk.StringVar(value="等待"); self.spin_time_var=tk.StringVar(value="—")
        self.result_var=tk.StringVar(value="请选择手势并下注")
        self.create_widgets(); self.update_display()

    def _configure_root(self):
        if isinstance(self.root,(tk.Tk,tk.Toplevel)):
            self.root.title("剪刀石头布"); self.root.geometry("1150x750+50+10"); self.root.resizable(False,False)
            self.root.protocol("WM_DELETE_WINDOW",self.on_closing)
        else:
            self.root.configure(width=self.WINDOW_WIDTH,height=self.WINDOW_HEIGHT)
            try: self.root.pack_propagate(False); self.root.grid_propagate(False)
            except tk.TclError: pass
        self.root.configure(bg=Theme.APP_BG)

    @staticmethod
    def _card(master, *, width, height, padding=12):
        outer=tk.Frame(master,width=width,height=height,bg=Theme.PANEL,highlightthickness=1,highlightbackground=Theme.BORDER_SOFT)
        outer.pack_propagate(False); outer.grid_propagate(False)
        inner=tk.Frame(outer,bg=Theme.PANEL); inner.place(x=padding,y=padding,width=max(1,width-padding*2),height=max(1,height-padding*2))
        outer.inner=inner; return outer

    @staticmethod
    def _section_title(master,text):
        return tk.Label(master,text=text,bg=Theme.PANEL,fg=Theme.TEXT,font=(Theme.FONT_CJK,11,"bold"),anchor=tk.W)

    def create_widgets(self):
        shell=tk.Frame(self.root,width=self.SHELL_WIDTH,height=self.SHELL_HEIGHT,bg=Theme.APP_BG)
        shell.pack(padx=20,pady=18); shell.pack_propagate(False)
        self._build_header(shell)
        body=tk.Frame(shell,width=self.SHELL_WIDTH,height=self.BODY_HEIGHT,bg=Theme.APP_BG)
        body.place(x=0,y=self.BODY_TOP,width=self.SHELL_WIDTH,height=self.BODY_HEIGHT)
        self._build_game_panel(body); self._build_control_panel(body)

    def _build_header(self,shell):
        header=tk.Frame(shell,width=self.SHELL_WIDTH,height=self.HEADER_HEIGHT,bg=Theme.PANEL,highlightthickness=1,highlightbackground=Theme.BORDER_SOFT)
        header.place(x=0,y=0,width=self.SHELL_WIDTH,height=self.HEADER_HEIGHT)
        icon=tk.Canvas(header,width=48,height=48,bg=Theme.PANEL,bd=0,highlightthickness=0); icon.place(x=14,y=11)
        icon.create_oval(2,2,46,46,fill=Theme.ACCENT_SOFT,outline=Theme.ACCENT,width=2); icon.create_text(24,23,text="✊",font=(Theme.FONT_EMOJI,20),fill=Theme.ACCENT)
        tk.Label(header,text="ROCK · PAPER · SCISSORS",bg=Theme.PANEL,fg=Theme.TEXT,font=(Theme.FONT,18,"bold"),anchor=tk.W).place(x=74,y=10,width=470,height=27)
        tk.Label(header,text="剪刀石头布",bg=Theme.PANEL,fg=Theme.TEXT_MUTED,font=(Theme.FONT_CJK,11,"bold"),anchor=tk.W).place(x=74,y=39,width=250,height=20)
        box=tk.Frame(header,width=206,height=46,bg=Theme.PANEL_ALT,highlightthickness=1,highlightbackground=Theme.BORDER_SOFT); box.place(x=self.SHELL_WIDTH-220,y=12,width=206,height=46)
        tk.Label(box,text="账户余额",bg=Theme.PANEL_ALT,fg=Theme.TEXT_MUTED,font=(Theme.FONT_CJK,9),anchor=tk.W).place(x=12,y=4,width=90,height=17)
        tk.Label(box,textvariable=self.balance_var,bg=Theme.PANEL_ALT,fg=Theme.ACCENT,font=(Theme.FONT,15,"bold"),anchor=tk.E).place(x=12,y=20,width=182,height=22)

    def _build_game_panel(self,master):
        panel=self._card(master,width=self.GAME_PANEL_WIDTH,height=self.BODY_HEIGHT,padding=0); panel.place(x=0,y=0,width=self.GAME_PANEL_WIDTH,height=self.BODY_HEIGHT)
        tk.Label(panel,text="对战桌",bg=Theme.PANEL,fg=Theme.TEXT,font=(Theme.FONT_CJK,12,"bold"),anchor=tk.W).place(x=16,y=10,width=100,height=24)
        tk.Label(panel,textvariable=self.stage_var,bg=Theme.ACCENT_SOFT,fg=Theme.ACCENT,font=(Theme.FONT_CJK,10,"bold"),anchor=tk.CENTER).place(x=590,y=10,width=140,height=24)
        self.game_canvas=tk.Canvas(panel,width=716,height=338,bg=Theme.CANVAS_BG,bd=0,highlightthickness=0); self.game_canvas.place(x=16,y=43,width=716,height=338)
        tk.Label(panel,text="选择你的手势",bg=Theme.PANEL,fg=Theme.TEXT,font=(Theme.FONT_CJK,11,"bold"),anchor=tk.W).place(x=16,y=395,width=180,height=22)
        gf=tk.Frame(panel,bg=Theme.PANEL); gf.place(x=16,y=426,width=716,height=106)
        for i,(symbol,label,accent) in enumerate(CHOICES):
            b=GestureButton(gf,symbol=symbol,label=label,accent=accent,command=self.set_choice,width=226,height=104)
            b.place(x=i*245,y=0,width=226,height=104); self.gesture_buttons.append(b)
        rb=tk.Frame(panel,bg=Theme.PANEL_ALT,highlightthickness=1,highlightbackground=Theme.BORDER_SOFT); rb.place(x=16,y=547,width=716,height=66)
        tk.Label(rb,text="本局结果",bg=Theme.PANEL_ALT,fg=Theme.TEXT_MUTED,font=(Theme.FONT_CJK,9),anchor=tk.W).place(x=12,y=7,width=80,height=18)
        self.result_label=tk.Label(rb,textvariable=self.result_var,bg=Theme.PANEL_ALT,fg=Theme.TEXT,font=(Theme.FONT_CJK,14,"bold"),anchor=tk.W)
        self.result_label.place(x=12,y=28,width=690,height=27)

    def _build_control_panel(self,master):
        sidebar=tk.Frame(master,width=self.SIDEBAR_WIDTH,height=self.BODY_HEIGHT,bg=Theme.APP_BG); sidebar.place(x=self.GAME_PANEL_WIDTH+self.PANEL_GAP,y=0,width=self.SIDEBAR_WIDTH,height=self.BODY_HEIGHT)
        MetricTile(sidebar,"当前下注",self.bet_var,Theme.CYAN,width=169,height=68).place(x=0,y=0,width=169,height=68)
        MetricTile(sidebar,"上局获胜",self.last_win_var,Theme.GREEN,width=169,height=68).place(x=179,y=0,width=169,height=68)
        chips=self._card(sidebar,width=348,height=101); chips.place(x=0,y=78,width=348,height=101); self._section_title(chips.inner,"下注筹码").place(x=0,y=0,width=120,height=20)
        for i,(label,amount,color,text_color) in enumerate(CHIP_CONFIGS):
            b=ChipButton(chips.inner,label=label,amount=amount,chip_color=color,text_color=text_color,command=self.add_chip,width=57,height=50)
            b.place(x=i*62,y=24,width=57,height=50); self.chip_buttons.append(b)
        payout=self._card(sidebar,width=348,height=107); payout.place(x=0,y=189,width=348,height=107); self._section_title(payout.inner,"结算赔率").place(x=0,y=0,width=120,height=20)
        self._build_payout_table(payout.inner)
        state=self._card(sidebar,width=348,height=86); state.place(x=0,y=306,width=348,height=86); self._section_title(state.inner,"本局状态").place(x=0,y=0,width=120,height=20)
        tk.Label(state.inner,text="你的选择",bg=Theme.PANEL,fg=Theme.TEXT_MUTED,font=(Theme.FONT_CJK,9),anchor=tk.W).place(x=0,y=29,width=72,height=18)
        tk.Label(state.inner,textvariable=self.selection_var,bg=Theme.PANEL,fg=Theme.ACCENT,font=(Theme.FONT_CJK,10,"bold"),anchor=tk.E).place(x=76,y=29,width=88,height=18)
        tk.Label(state.inner,text="剩余时间",bg=Theme.PANEL,fg=Theme.TEXT_MUTED,font=(Theme.FONT_CJK,9),anchor=tk.W).place(x=178,y=29,width=72,height=18)
        tk.Label(state.inner,textvariable=self.spin_time_var,bg=Theme.PANEL,fg=Theme.RED,font=(Theme.FONT_CJK,10,"bold"),anchor=tk.E).place(x=252,y=29,width=70,height=18)
        actions=self._card(sidebar,width=348,height=92); actions.place(x=0,y=402,width=348,height=92)
        self.reset_bet_button=ModernButton(actions.inner,text="清空全部筹码",command=self.reset_bet,background=Theme.RED,hover_background=Theme.RED_HOVER,foreground="#FFFFFF",font_size=12,bold=True)
        self.reset_bet_button.place(x=0,y=0,width=self.ACTION_BUTTON_WIDTH,height=self.ACTION_BUTTON_HEIGHT)
        self.play_button=ModernButton(actions.inner,text="开始游戏",command=self.play_game,background=Theme.GREEN,hover_background=Theme.GREEN_HOVER,foreground="#FFFFFF",font_size=12,bold=True)
        self.play_button.place(x=0,y=42,width=self.ACTION_BUTTON_WIDTH,height=self.ACTION_BUTTON_HEIGHT)
        rules=self._card(sidebar,width=348,height=126); rules.place(x=0,y=504,width=348,height=126); self._section_title(rules.inner,"玩法说明").place(x=0,y=0,width=120,height=20)
        tk.Label(rules.inner,text="先下注并选择石头、布或剪刀，再开始游戏。\n电脑将快速轮换手势 3–7 秒，倒计时归零立即锁定。\n石头胜剪刀 · 剪刀胜布 · 布胜石头。\n获胜返还 1.95×；平局退回 1.00×；失败不返还。",
                 bg=Theme.PANEL,fg=Theme.TEXT_MUTED,font=(Theme.FONT_CJK,9),justify=tk.LEFT,anchor=tk.NW).place(x=0,y=27,width=322,height=82)

    def _build_payout_table(self, master):
        table_border_color = Theme.ACCENT
        table_bg = Theme.PANEL_ALT

        header_frame = tk.Frame(master, bg=table_border_color)
        header_frame.place(x=0, y=27, width=322, height=25)
        for txt in ("获胜返还", "平局返还", "失败返还"):
            tk.Label(
                header_frame, text=txt,
                font=(Theme.FONT_CJK, 12, "bold"),
                bg=table_border_color, fg="#FFFFFF", width=9, pady=2,
            ).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        content_frame = tk.Frame(master, bg=table_bg)
        content_frame.place(x=0, y=52, width=322, height=29)
        for txt in ("1.95×", "1.00×", "0.00×"):
            tk.Label(
                content_frame, text=txt,
                font=(Theme.FONT, 12, "bold"),
                bg=table_bg, fg=Theme.TEXT, width=9, pady=2,
                highlightthickness=1, highlightbackground=Theme.BORDER_SOFT,
            ).pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def add_chip(self,amount):
        if self.game_active: return
        try: amount_value=float(amount)
        except (TypeError,ValueError): return
        if self.current_bet+amount_value<=self.balance:
            self.current_bet+=amount_value; self.update_display()
        else: messagebox.showwarning("余额不足","账户余额不足以加入这个筹码。",parent=self.root)

    def reset_bet(self):
        if not self.game_active: self.current_bet=0.0; self.update_display()

    def set_choice(self,choice):
        if self.game_active: return
        self.user_choice=choice; self.final_result=None; self.result_label.configure(fg=Theme.TEXT)
        self.result_var.set(f"已选择 {self.choice_map[choice]}，设置下注后即可开始。"); self.stage_var.set("准备开始"); self.update_display()

    def determine_winner(self,user_choice,computer_choice):
        if user_choice==computer_choice: return "和局"
        if ((user_choice=="✊" and computer_choice=="✌") or (user_choice=="✌" and computer_choice=="✋") or (user_choice=="✋" and computer_choice=="✊")): return "你赢了"
        return "你输了"

    def play_game(self):
        if self.game_active: return
        if self.current_bet<=0: messagebox.showwarning("尚未下注","请先选择下注筹码。",parent=self.root); return
        if self.user_choice is None: messagebox.showwarning("尚未选择","请选择石头、布或剪刀。",parent=self.root); return
        if self.current_bet>self.balance: messagebox.showwarning("余额不足","余额不足以进行此下注。",parent=self.root); return
        self.bet_amount=self.current_bet; self.balance-=self.bet_amount; update_balance_in_json(self.username,self.balance)
        self.game_active=True; self.animation_running=True; self.animation_duration=random.randint(3000,7000); self.animation_start_time=time.monotonic()*1000.0
        self.computer_choice=random.choice(("✊","✌","✋")); self.final_result=None
        self.spin_time_var.set(f"{self.animation_duration / 1000.0:.1f} 秒")
        self.result_var.set("电脑正在出拳…"); self.stage_var.set("电脑出拳中")
        self._set_round_controls(False); self.update_display(); self.animate_computer_choice()

    def _next_computer_choice(self):
        choices=[symbol for symbol in ("✊","✌","✋") if symbol != self.computer_choice]
        return random.choice(choices)

    def animate_computer_choice(self):
        if not self.animation_running or not self.game_active: return
        elapsed=time.monotonic()*1000.0-self.animation_start_time
        remaining=max(0.0,self.animation_duration-elapsed)
        self.spin_time_var.set(f"{remaining / 1000.0:.1f} 秒")

        if remaining <= 0:
            # Deadline reached: keep the exact emoji currently visible and lock it.
            self.animation_running=False
            self.spin_time_var.set("0.0 秒")
            self.final_result=self.determine_winner(self.user_choice,self.computer_choice)
            self.finish_game()
            return

        # Never repeat the previous animation emoji. This avoids a false visual pause.
        self.computer_choice=self._next_computer_choice()
        self.computer_var.set(self.choice_map[self.computer_choice])
        self.draw_game_area()
        self.root.after(max(1,min(75,int(remaining))),self.animate_computer_choice)

    def finish_game(self):
        if not self.game_active or self.final_result is None: return
        if self.final_result=="你赢了":
            total=self.bet_amount*1.95; self.balance+=total; self.last_win=total; self.result_var.set(f"本金您获胜了！"); self.result_label.configure(fg=Theme.GREEN)
        elif self.final_result=="和局":
            total=self.bet_amount*1.00; self.balance+=total; self.last_win=total; self.result_var.set(f"本局和局，本金退还"); self.result_label.configure(fg=Theme.AMBER)
        else:
            self.last_win=0.0; self.result_var.set(f"本局您失败了"); self.result_label.configure(fg=Theme.RED)
        update_balance_in_json(self.username,self.balance); self.stage_var.set("结算中"); self.computer_var.set(self.choice_map[self.computer_choice])
        # Keep game_active=True throughout the result-hold period so Start/Bet/Choice
        # controls cannot become active before settlement finishes.
        self._set_round_controls(False); self.update_display()
        if self.result_hold_job is not None:
            try: self.root.after_cancel(self.result_hold_job)
            except tk.TclError: pass
        self.result_hold_job=self.root.after(1800,self._ready_next_round)

    def _ready_next_round(self):
        self.result_hold_job=None; self.game_active=False; self.user_choice=None; self.computer_choice=None; self.final_result=None
        self.spin_time_var.set("—"); self.stage_var.set("选择手势"); self.result_label.configure(fg=Theme.TEXT); self.result_var.set("请选择手势并下注")
        self._set_round_controls(True); self.update_display()

    def _set_round_controls(self,enabled):
        state=tk.NORMAL if enabled else tk.DISABLED
        self.play_button.configure(state=state); self.reset_bet_button.configure(state=state)
        for b in self.chip_buttons: b.configure(state=state)
        for b in self.gesture_buttons: b.set_enabled(enabled)

    def update_display(self):
        self.balance_var.set(f"${self.balance:,.2f}"); self.bet_var.set(f"${self.current_bet:,.2f}"); self.last_win_var.set(f"${self.last_win:,.2f}")
        self.selection_var.set("未选择" if self.user_choice is None else self.choice_map[self.user_choice])
        if not self.game_active and self.computer_choice is None: self.computer_var.set("等待")
        elif self.computer_choice is not None: self.computer_var.set(self.choice_map[self.computer_choice])
        for b in self.gesture_buttons: b.set_selected(b.symbol==self.user_choice)
        self.play_button.configure(state=tk.NORMAL if (not self.game_active and self.current_bet>0 and self.user_choice is not None) else tk.DISABLED)
        if self.game_active:
            self.reset_bet_button.configure(state=tk.DISABLED)
            for b in self.chip_buttons: b.configure(state=tk.DISABLED)
            for b in self.gesture_buttons: b.set_enabled(False)
        self.draw_game_area()

    def draw_game_area(self):
        c=self.game_canvas; c.delete("all"); w=716; h=338
        c.create_rectangle(0,0,w,h,fill=Theme.TABLE,outline="")
        for y in range(42,h,58): c.create_line(0,y,w,y,fill=Theme.TABLE_DARK,width=1,stipple="gray50")
        c.create_rectangle(22,21,w-22,h-21,outline=Theme.BORDER,width=2); c.create_line(w/2,54,w/2,256,fill=Theme.BORDER,width=2,dash=(6,6))
        c.create_oval(w/2-34,122,w/2+34,190,fill=Theme.PANEL,outline=Theme.ACCENT,width=3); c.create_text(w/2,156,text="VS",fill=Theme.ACCENT,font=(Theme.FONT,18,"bold"))
        self._draw_fighter(c,178,"你的选择",self.user_choice,Theme.ACCENT); self._draw_fighter(c,538,"电脑选择",self.computer_choice,Theme.RED)
        fill=Theme.PANEL_ALT; text="等待选择"; fg=Theme.TEXT_MUTED
        if self.game_active and self.animation_running: fill=Theme.ACCENT_SOFT; text="电脑正在快速出拳"; fg=Theme.ACCENT
        elif self.final_result=="你赢了": fill=Theme.WIN; text="本局获胜"; fg=Theme.GREEN
        elif self.final_result=="和局": fill=Theme.DRAW; text="本局和局"; fg=Theme.AMBER
        elif self.final_result=="你输了": fill=Theme.LOSS; text="本局失败"; fg=Theme.RED
        elif self.user_choice: text=f"已锁定 {self.choice_map[self.user_choice]}"
        c.create_rectangle(118,276,598,316,fill=fill,outline=Theme.BORDER_SOFT,width=1); c.create_text(w/2,296,text=text,fill=fg,font=(Theme.FONT_CJK,12,"bold"))

    def _draw_fighter(self,c,x,title,choice,accent):
        c.create_text(x,54,text=title,fill=Theme.TEXT_MUTED,font=(Theme.FONT_CJK,11,"bold")); c.create_oval(x-76,84,x+76,236,fill=Theme.PANEL,outline=Theme.BORDER_SOFT,width=2)
        c.create_oval(x-62,98,x+62,222,fill=Theme.PANEL_ALT,outline=accent if choice else Theme.BORDER_SOFT,width=3 if choice else 1)
        c.create_text(x,147,text=choice or "?",fill=accent if choice else Theme.TEXT_DIM,font=(Theme.FONT_EMOJI if choice else Theme.FONT,52,"bold"))
        label=self.choice_map.get(choice,"未选择" if title.startswith("你") else "等待中")
        c.create_text(x,202,text=label,fill=accent if choice else Theme.TEXT_MUTED,font=(Theme.FONT_CJK,12,"bold"))

    def on_closing(self):
        update_balance_in_json(self.username,self.balance); finish=getattr(self.root,"finish",None)
        if callable(finish): finish(self.balance)
        else: self.root.destroy()


def main(initial_balance=10000.0, username="Guest", *, parent=None, balance=None, user=None, on_back=None, on_balance_change=None):
    actual_balance=float(initial_balance if balance is None else balance); actual_user=username if user is None else user
    if parent is not None:
        page=EmbeddedGamePage(parent,title="剪刀石头布",username=actual_user,balance=actual_balance,on_back=on_back,on_balance_change=on_balance_change)
        page.set_requested_size(1150,750); game=RPSGame(page.host,actual_balance,actual_user); page.attach_game(game); return page
    root=tk.Tk(); game=RPSGame(root,actual_balance,actual_user); root.mainloop(); return game.balance


if __name__ == "__main__":
    final_balance=main(10000.0,"test_user"); print(f"Final balance: {final_balance:.2f}")