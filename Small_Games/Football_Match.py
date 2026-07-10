import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import math
import time

# ================== 数据存取 ==================
def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')

def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    try:
        with open(get_data_file_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    else:
        users.append({'user_name': username, 'cash': f"{new_balance:.2f}"})
    save_user_data(users)

def format_money(amount):
    """将金额格式化为整数（如果是整数）或两位小数"""
    if amount.is_integer():
        return str(int(amount))
    else:
        return f"{amount:.2f}"

# ================== 弹珠足球游戏主类 ==================
class FootballPachinko(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("足球弹珠")
        self.geometry("950x750+50+10")
        self.resizable(0,0)
        self.configure(bg='#2a4a3c')

        self.username = username
        self.balance = float(initial_balance)

        # 游戏状态
        self.match_in_progress = False

        # === 原有下注金额 ===
        self.bet_home = 0.0
        self.bet_draw = 0.0
        self.bet_away = 0.0

        # === 新增：总入球下注金额 ===
        self.total_goal_options = ["0/1", "2", "3", "4", "5", "6+"]
        self.total_goal_bets = {opt: 0.0 for opt in self.total_goal_options}
        self.total_goal_odds = {
            "0/1": 19.60,
            "2":   7.40,
            "3":   4.55,
            "4":   4.00,
            "5":   4.60,
            "6+":  4.65
        }

        # === 新增：入球大小下注金额 ===
        self.over_under_options = ["under4.5", "over4.5", "under3.5", "over3.5"]
        self.over_under_bets = {opt: 0.0 for opt in self.over_under_options}
        self.over_under_odds = {
            "under4.5": 1.60,
            "over4.5":  2.15,
            "under3.5": 2.50,
            "over3.5":  1.50
        }

        # 赔率（原有）
        self.odds = {"home": 2.6, "away": 2.6, "draw": 3.15}

        # 比赛得分
        self.home_score = 0
        self.away_score = 0
        self.current_round = 0
        self.balls_in_round = 0
        self.rounds_total = 5

        # 弹珠物理
        self.gravity = 0.5
        self.damping = 0.8
        self.elasticity = 0.8
        self.pegs = []
        self.balls = []
        self.active_balls = 0
        self.animation_running = False
        self.after_id = None

        # UI组件
        self.selected_chip = None
        self.chip_buttons = []
        self.chip_texts = {}
        self.bet_displays = {}          # 原有三个下注显示
        self.last_win = 0.0

        # 新增UI组件的引用存储
        self.total_goal_labels = {}     # 总入球各选项的显示Label
        self.over_under_labels = {}     # 大小球各选项的显示Label

        self._create_widgets()
        self.update_balance_display()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ---------- UI 构建 ----------
    def _create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧游戏板
        left_frame = tk.Frame(main_frame, bg='#35654d', width=500)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        left_frame.pack_propagate(False)
        self.board_canvas = tk.Canvas(left_frame, bg='#35654d', highlightthickness=0)
        self.board_canvas.pack(fill=tk.BOTH, expand=True)
        self.board_canvas.bind("<Configure>", self.on_canvas_resize)

        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=400)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10,10), pady=(5,5))
        control_frame.pack_propagate(False)

        # 余额与轮次显示（同一行）
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        self.balance_label = tk.Label(info_frame, text=f"余额: ${self.balance:.2f}",
                                    font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)
        self.round_label = tk.Label(info_frame, text="第 0 / 5 轮", font=('Arial', 16),
                                    bg='#2a4a3c', fg='white')
        self.round_label.pack(side=tk.RIGHT, padx=20, pady=10)

        # 筹码选择区
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(anchor='w', padx=10, pady=5)
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(pady=5)
        chip_configs = [('$10', '#ffa500', 'black'), ('$25', '#00ff00', 'black'),
                        ('$100', '#000000', 'white'), ('$500', '#FF7DDA', 'black'),
                        ('$1K', '#ffffff', 'black'), ('$2.5K', '#ff0000', 'white')]
        for text, bg, fg in chip_configs:
            chip_canvas = tk.Canvas(chip_row, width=55, height=55, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2,2,54,54, fill=bg, outline='black')
            chip_canvas.create_text(27.5, 27.5, text=text, fill=fg, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=3)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        self.select_chip("$10")

        # 每注限制
        minmax_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        minmax_frame.pack(fill=tk.X, pady=5)
        
        # 标题行
        header_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        
        tk.Label(header_frame, text="每注最低", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="每注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="总注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        
        # 数值行
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$10,000", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$100,000", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)

        # ========== 原有下注区（主队、和局、客队）==========
        bet_container = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_container.pack(fill=tk.X, pady=5)

        self.bet_table = tk.Frame(bet_container, bg='#2a4a3c')
        self.bet_table.pack(pady=5)

        tk.Label(self.bet_table, text="主(1.6:1)", font=('Arial', 14, 'bold'), bg='#2a4a3c', fg='white', width=10).grid(row=0, column=0, padx=5, pady=2)
        tk.Label(self.bet_table, text="和(2.15:1)", font=('Arial', 14, 'bold'), bg='#2a4a3c', fg='white', width=10).grid(row=0, column=1, padx=5, pady=2)
        tk.Label(self.bet_table, text="客(1.6:1)", font=('Arial', 14, 'bold'), bg='#2a4a3c', fg='white', width=10).grid(row=0, column=2, padx=5, pady=2)

        self.bet_home_display = tk.Label(self.bet_table, text="0", font=('Arial', 14),
                                        bg='white', width=8, relief=tk.SUNKEN)
        self.bet_home_display.grid(row=1, column=0, padx=3, pady=2)
        self.bet_home_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("home"))
        self.bet_home_display.bind("<Button-3>", lambda e: self.reset_single_bet("home"))
        self.bet_displays["home"] = self.bet_home_display

        self.bet_draw_display = tk.Label(self.bet_table, text="0", font=('Arial', 14),
                                        bg='white', width=8, relief=tk.SUNKEN)
        self.bet_draw_display.grid(row=1, column=1, padx=5, pady=2)
        self.bet_draw_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("draw"))
        self.bet_draw_display.bind("<Button-3>", lambda e: self.reset_single_bet("draw"))
        self.bet_displays["draw"] = self.bet_draw_display

        self.bet_away_display = tk.Label(self.bet_table, text="0", font=('Arial', 14),
                                        bg='white', width=8, relief=tk.SUNKEN)
        self.bet_away_display.grid(row=1, column=2, padx=5, pady=2)
        self.bet_away_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("away"))
        self.bet_away_display.bind("<Button-3>", lambda e: self.reset_single_bet("away"))
        self.bet_displays["away"] = self.bet_away_display

        # ========== 新增：总入球下注区 ==========
        total_goals_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        total_goals_frame.pack(fill=tk.X, pady=5)
        tk.Label(total_goals_frame, text="总入球", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='white').pack(anchor='w', padx=10)

        goals_row = tk.Frame(total_goals_frame, bg='#2a4a3c')
        goals_row.pack(pady=5)
        for opt in self.total_goal_options:
            sub_frame = tk.Frame(goals_row, bg='#2a4a3c')
            sub_frame.pack(side=tk.LEFT, padx=4)
            tk.Label(sub_frame, text=opt, font=('Arial', 12), bg='#2a4a3c', fg='white').pack()
            lbl = tk.Label(sub_frame, text="0", font=('Arial', 10), bg='white', width=6, relief=tk.SUNKEN)
            lbl.pack(pady=2)
            lbl.bind("<Button-1>", lambda e, o=opt: self.add_bet_to_total_goal(o))
            lbl.bind("<Button-3>", lambda e, o=opt: self.reset_total_goal_single(o))
            self.total_goal_labels[opt] = lbl

        # ========== 入球大小下注区 ==========
        over_under_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        over_under_frame.pack(fill=tk.X, pady=5)
        tk.Label(over_under_frame, text="入球大小", font=('Arial', 12, 'bold'),
                bg='#2a4a3c', fg='white').pack(anchor='w', padx=10, pady=2)


        row2 = tk.Frame(over_under_frame, bg='#2a4a3c')
        row2.pack(pady=2)

        left_small_frame2 = tk.Frame(row2, bg='#2a4a3c')
        left_small_frame2.pack(side=tk.LEFT, padx=10)
        small_35_lbl = tk.Label(left_small_frame2, text="0", font=('Arial', 12), bg='white', width=6, relief=tk.SUNKEN)
        small_35_lbl.pack(pady=2)
        small_35_lbl.bind("<Button-1>", lambda e: self.add_bet_to_over_under("under3.5"))
        small_35_lbl.bind("<Button-3>", lambda e: self.reset_over_under_single("under3.5"))
        self.over_under_labels["under3.5"] = small_35_lbl

        tk.Label(row2, text="小 <= 3.5 => 大", font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='#FFD700').pack(side=tk.LEFT, padx=15)

        right_big_frame2 = tk.Frame(row2, bg='#2a4a3c')
        right_big_frame2.pack(side=tk.LEFT, padx=10)
        big_35_lbl = tk.Label(right_big_frame2, text="0", font=('Arial', 12), bg='white', width=6, relief=tk.SUNKEN)
        big_35_lbl.pack(pady=2)
        big_35_lbl.bind("<Button-1>", lambda e: self.add_bet_to_over_under("over3.5"))
        big_35_lbl.bind("<Button-3>", lambda e: self.reset_over_under_single("over3.5"))
        self.over_under_labels["over3.5"] = big_35_lbl
        
        row1 = tk.Frame(over_under_frame, bg='#2a4a3c')
        row1.pack(pady=5)

        left_small_frame = tk.Frame(row1, bg='#2a4a3c')
        left_small_frame.pack(side=tk.LEFT, padx=10)
        small_45_lbl = tk.Label(left_small_frame, text="0", font=('Arial', 12), bg='white', width=6, relief=tk.SUNKEN)
        small_45_lbl.pack(pady=2)
        small_45_lbl.bind("<Button-1>", lambda e: self.add_bet_to_over_under("under4.5"))
        small_45_lbl.bind("<Button-3>", lambda e: self.reset_over_under_single("under4.5"))
        self.over_under_labels["under4.5"] = small_45_lbl

        tk.Label(row1, text="小 <= 4.5 => 大", font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='#FFD700').pack(side=tk.LEFT, padx=15)

        right_big_frame = tk.Frame(row1, bg='#2a4a3c')
        right_big_frame.pack(side=tk.LEFT, padx=10)
        big_45_lbl = tk.Label(right_big_frame, text="0", font=('Arial', 12), bg='white', width=6, relief=tk.SUNKEN)
        big_45_lbl.pack(pady=2)
        big_45_lbl.bind("<Button-1>", lambda e: self.add_bet_to_over_under("over4.5"))
        big_45_lbl.bind("<Button-3>", lambda e: self.reset_over_under_single("over4.5"))
        self.over_under_labels["over4.5"] = big_45_lbl

        # 操作按钮行
        action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        action_frame.pack(fill=tk.X, pady=5)

        button_container = tk.Frame(action_frame, bg='#2a4a3c')
        button_container.pack(expand=True)

        self.reset_bets_button = tk.Button(
            button_container, text="重设金额", 
            command=self.reset_all_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)

        self.start_button = tk.Button(
            button_container, text="开始游戏", 
            command=self.start_match, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.play_again_button = tk.Button(
            button_container, text="再来一局", font=('Arial', 14),
            bg='#2196F3', fg='white', command=self.play_again, width=10
        )
        self.play_again_button.pack(side=tk.LEFT, padx=5)
        self.play_again_button.pack_forget()

        # 状态栏
        self.status_label = tk.Label(control_frame, text="请下注并开始比赛",
                                    font=('Arial', 12), bg='#2a4a3c', fg='white', wraplength=280)
        self.status_label.pack(pady=5, fill=tk.X)

        # 底部信息
        info2_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info2_frame.pack(fill=tk.X, pady=5, side=tk.BOTTOM)
        self.current_bet_label = tk.Label(info2_frame, text="本局下注: $0.00", font=('Arial', 12),
                                        bg='#2a4a3c', fg='white')
        self.current_bet_label.pack(pady=2, anchor='w', padx=10)

        last_win_row = tk.Frame(info2_frame, bg='#2a4a3c')
        last_win_row.pack(fill=tk.X, pady=2, padx=10)
        self.last_win_label = tk.Label(last_win_row, text="上局获胜: $0.00", font=('Arial', 12),
                                    bg='#2a4a3c', fg='#FFD700')
        self.last_win_label.pack(side=tk.LEFT)
        info_btn = tk.Button(last_win_row, text="ℹ️", command=self.show_game_instructions,
                            bg='#4B8BBE', fg='white', font=('Arial', 10), width=2, relief=tk.FLAT)
        info_btn.pack(side=tk.RIGHT)

    def _create_over_under_item(self, parent, display_text, bet_key, side):
        """创建大小球的一个选项（左侧或右侧）"""
        frame = tk.Frame(parent, bg='#2a4a3c')
        if side == "left":
            frame.pack(side=tk.LEFT, padx=20, expand=True)
        else:
            frame.pack(side=tk.RIGHT, padx=20, expand=True)
        tk.Label(frame, text=display_text, font=('Arial', 10), bg='#2a4a3c', fg='white').pack()
        lbl = tk.Label(frame, text="0", font=('Arial', 12), bg='white', width=6, relief=tk.SUNKEN)
        lbl.pack(pady=2)
        lbl.bind("<Button-1>", lambda e, k=bet_key: self.add_bet_to_over_under(k))
        lbl.bind("<Button-3>", lambda e, k=bet_key: self.reset_over_under_single(k))
        self.over_under_labels[bet_key] = lbl

    # ---------- 辅助方法 ----------
    def update_balance_display(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)

    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            for item in chip.find_all():
                if chip.type(item) == 'oval':
                    chip.itemconfig(item, outline='black', width=2)
                elif chip.type(item) == 'text' and chip.itemcget(item, 'text') == chip_text:
                    for oval in chip.find_all():
                        if chip.type(oval) == 'oval':
                            chip.itemconfig(oval, outline='gold', width=3)
                            break

    def get_chip_value(self):
        """将筹码文本转换为数值"""
        if not self.selected_chip:
            return 0
        chip_val_str = self.selected_chip.replace('$', '')
        if 'K' in chip_val_str:
            return float(chip_val_str.replace('K', '')) * 1000
        else:
            return float(chip_val_str)

    # ---------- 原有下注操作 ----------
    def add_chip_to_bet(self, bet_type):
        if self.match_in_progress:
            return
        chip_value = self.get_chip_value()
        if chip_value == 0:
            return

        total_bet = self.calc_total_bet()
        if total_bet + chip_value > self.balance:
            messagebox.showerror("余额不足", "下注总额超过余额")
            return

        if bet_type == "home":
            self.bet_home += chip_value
            self.bet_home_display.config(text=format_money(self.bet_home))
        elif bet_type == "draw":
            self.bet_draw += chip_value
            self.bet_draw_display.config(text=format_money(self.bet_draw))
        elif bet_type == "away":
            self.bet_away += chip_value
            self.bet_away_display.config(text=format_money(self.bet_away))
        self.update_total_bet_display()

    def add_bet_to_total_goal(self, option):
        if self.match_in_progress:
            return
        chip_value = self.get_chip_value()
        if chip_value == 0:
            return

        new_bet = self.total_goal_bets[option] + chip_value
        # 限制单项最高10000
        if new_bet > 10000:
            messagebox.showerror("下注超限", f"单个下注项最高 $10000！")
            return

        total_bet = self.calc_total_bet() + chip_value
        if total_bet > 100000:
            messagebox.showerror("总下注超限", f"总下注最高 $100000！")
            return

        if total_bet > self.balance:
            messagebox.showerror("余额不足", "下注总额超过余额")
            return

        self.total_goal_bets[option] = new_bet
        self.total_goal_labels[option].config(text=format_money(new_bet))
        self.update_total_bet_display()

    def reset_single_bet(self, bet_type):
        if self.match_in_progress:
            return
        if bet_type == "home":
            self.bet_home = 0
            self.bet_home_display.config(text="0")
        elif bet_type == "draw":
            self.bet_draw = 0
            self.bet_draw_display.config(text="0")
        elif bet_type == "away":
            self.bet_away = 0
            self.bet_away_display.config(text="0")
        self.update_total_bet_display()

    # ---------- 新增：总入球下注操作 ----------
    def add_chip_to_bet(self, bet_type):
        if self.match_in_progress:
            return
        chip_value = self.get_chip_value()
        if chip_value == 0:
            return

        # 计算单项新下注额
        if bet_type == "home":
            new_bet = self.bet_home + chip_value
        elif bet_type == "draw":
            new_bet = self.bet_draw + chip_value
        else:  # away
            new_bet = self.bet_away + chip_value

        # 限制单项最高10000
        if new_bet > 10000:
            messagebox.showerror("下注超限", f"单个下注项最高 $10000！")
            return

        total_bet = self.calc_total_bet() + chip_value
        if total_bet > 100000:
            messagebox.showerror("总下注超限", f"总下注最高 $100000！")
            return

        # 扣除余额检查（原有逻辑）
        if total_bet > self.balance:
            messagebox.showerror("余额不足", "下注总额超过余额")
            return

        # 执行下注
        if bet_type == "home":
            self.bet_home = new_bet
            self.bet_home_display.config(text=format_money(self.bet_home))
        elif bet_type == "draw":
            self.bet_draw = new_bet
            self.bet_draw_display.config(text=format_money(self.bet_draw))
        else:
            self.bet_away = new_bet
            self.bet_away_display.config(text=format_money(self.bet_away))
        self.update_total_bet_display()

    def reset_total_goal_single(self, option):
        if self.match_in_progress:
            return
        self.total_goal_bets[option] = 0
        self.total_goal_labels[option].config(text="0")
        self.update_total_bet_display()

    # ---------- 新增：大小球下注操作 ----------
    def add_bet_to_over_under(self, bet_key):
        if self.match_in_progress:
            return
        chip_value = self.get_chip_value()
        if chip_value == 0:
            return

        new_bet = self.over_under_bets[bet_key] + chip_value
        # 限制单项最高10000
        if new_bet > 10000:
            messagebox.showerror("下注超限", f"单个下注项最高 $10000！")
            return

        total_bet = self.calc_total_bet() + chip_value
        if total_bet > 100000:
            messagebox.showerror("总下注超限", f"总下注最高 $100000！")
            return

        if total_bet > self.balance:
            messagebox.showerror("余额不足", "下注总额超过余额")
            return

        self.over_under_bets[bet_key] = new_bet
        self.over_under_labels[bet_key].config(text=format_money(new_bet))
        self.update_total_bet_display()

    def reset_over_under_single(self, bet_key):
        if self.match_in_progress:
            return
        self.over_under_bets[bet_key] = 0
        self.over_under_labels[bet_key].config(text="0")
        self.update_total_bet_display()

    # ---------- 通用下注管理 ----------
    def reset_all_bets(self):
        if self.match_in_progress:
            return
        # 重置原有下注
        self.bet_home = 0
        self.bet_draw = 0
        self.bet_away = 0
        for display in self.bet_displays.values():
            display.config(text="0")
        # 重置总入球下注
        for opt in self.total_goal_options:
            self.total_goal_bets[opt] = 0
            self.total_goal_labels[opt].config(text="0")
        # 重置大小球下注
        for key in self.over_under_options:
            self.over_under_bets[key] = 0
            self.over_under_labels[key].config(text="0")
        self.update_total_bet_display()
        self.status_label.config(text="所有下注已清空")

    def calc_total_bet(self):
        """计算所有下注总额"""
        total = self.bet_home + self.bet_draw + self.bet_away
        total += sum(self.total_goal_bets.values())
        total += sum(self.over_under_bets.values())
        return total

    def update_total_bet_display(self):
        total = self.calc_total_bet()
        self.current_bet_label.config(text=f"本局下注: ${total:.2f}")

    # ---------- 规则弹窗 ----------
    def show_game_instructions(self):
        """显示游戏规则说明（滚动窗口+表格）"""
        win = tk.Toplevel(self)
        win.title("游戏规则 - 足球弹珠")
        win.geometry("800x650")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')

        # 主框架
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)

        # 内容框架
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')

        # ========== 游戏规则说明 ==========
        rules_text = """
        足球弹珠 游戏规则

        【基础玩法】
        共进行5轮，每轮同时落下蓝色(主队)和红色(客队)两颗弹珠。
        弹珠经过钉板后落入底部三个区域：
        • 蓝色弹珠落入中间【入球区】→ 主队+1分
        • 红色弹珠落入中间【入球区】→ 客队+1分
        • 落入左右两侧不得分

        【胜负判定】
        最终主队得分 > 客队得分 → 主队胜
        主队得分 < 客队得分 → 客队胜
        得分相等 → 和局
        """

        rules_label = tk.Label(
            content_frame,
            text=rules_text,
            font=('微软雅黑', 11),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        rules_label.pack(fill=tk.X, padx=10, pady=5)

        # ========== 胜负赔率表 ==========
        tk.Label(
            content_frame,
            text="胜负赔率",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        odds_frame1 = tk.Frame(content_frame, bg='#F0F0F0')
        odds_frame1.pack(fill=tk.X, padx=20, pady=5)

        headers1 = ["下注类型", "赔率"]
        odds_data1 = [
            ("主队胜", "1.6:1"),
            ("客队胜", "1.6:1"),
            ("和局", "2.15:1")
        ]

        for col, h in enumerate(headers1):
            tk.Label(
                odds_frame1,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        for r, row_data in enumerate(odds_data1, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    odds_frame1,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        for c in range(len(headers1)):
            odds_frame1.columnconfigure(c, weight=1)

        # ========== 总入球赔率表 ==========
        tk.Label(
            content_frame,
            text="总入球赔率",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        odds_frame2 = tk.Frame(content_frame, bg='#F0F0F0')
        odds_frame2.pack(fill=tk.X, padx=20, pady=5)

        headers2 = ["总进球数区间", "赔率"]
        odds_data2 = [
            ("0/1 球", "18.60:1"),
            ("2 球", "6.40:1"),
            ("3 球", "3.55:1"),
            ("4 球", "3.00:1"),
            ("5 球", "3.60:1"),
            ("6+ 球", "3.65:1")
        ]

        for col, h in enumerate(headers2):
            tk.Label(
                odds_frame2,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        for r, row_data in enumerate(odds_data2, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    odds_frame2,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        for c in range(len(headers2)):
            odds_frame2.columnconfigure(c, weight=1)

        # ========== 入球大小赔率表 ==========
        tk.Label(
            content_frame,
            text="入球大小赔率",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')

        odds_frame3 = tk.Frame(content_frame, bg='#F0F0F0')
        odds_frame3.pack(fill=tk.X, padx=20, pady=5)

        headers3 = ["盘口", "条件", "赔率"]
        odds_data3 = [
            ("小3.5", "总进球 ≤ 3", "1.50:1"),
            ("大3.5", "总进球 ≥ 4", "0.50:1"),
            ("小4.5", "总进球 ≤ 4", "0.60:1"),
            ("大4.5", "总进球 ≥ 4", "1.15:1")
        ]

        for col, h in enumerate(headers3):
            tk.Label(
                odds_frame3,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        for r, row_data in enumerate(odds_data3, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    odds_frame3,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        for c in range(len(headers3)):
            odds_frame3.columnconfigure(c, weight=1)

        # ========== 注意事项 ==========
        notes_text = """
        注意事项：
        • 总入球和大小球可任意组合下注
        • 所有下注项独立结算，互不影响
        • 比赛开始后无法修改下注
        • 每轮弹珠落下会有得分特效提示
        """

        notes_label = tk.Label(
            content_frame,
            text=notes_text,
            font=('微软雅黑', 10),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        notes_label.pack(fill=tk.X, padx=10, pady=5)

        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        # 关闭按钮
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

        # 鼠标滚轮支持
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ---------- 弹珠板绘制 ----------
    def on_canvas_resize(self, event):
        self.draw_board()

    def _get_bottom_region_bounds(self, width):
        start_x = 80
        end_x = width - 80
        if end_x <= start_x:
            end_x = start_x + 3
        total_w = end_x - start_x
        b1 = start_x + total_w // 3
        b2 = start_x + (2 * total_w) // 3
        return [start_x, b1, b2, end_x]

    def draw_board(self):
        self.board_canvas.delete("all")
        w = self.board_canvas.winfo_width()
        h = self.board_canvas.winfo_height()
        if w < 100 or h < 100:
            return

        top_y = 40
        bottom_y = h - 60
        top_w = 30
        bottom_w = w - 160
        self.board_canvas.create_polygon(
            w // 2 - top_w // 2, top_y,
            w // 2 + top_w // 2, top_y,
            w // 2 + bottom_w // 2, bottom_y,
            w // 2 - bottom_w // 2, bottom_y,
            fill="#35654d", outline="#2d4059", width=2
        )

        rows = 11
        pegs_per_row = [1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11]
        self.pegs = []
        for row in range(rows):
            progress = row / (rows - 1)
            cur_w = top_w + (bottom_w - top_w) * progress
            y = top_y + (bottom_y - top_y) * progress
            cnt = pegs_per_row[row]
            for i in range(cnt):
                spacing = cur_w / (cnt + 1)
                x = w // 2 - cur_w // 2 + spacing * (i + 1)
                self.pegs.append((x, y))
                self.board_canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill='white', outline='gray')

        bottom_y = h - 60
        bounds = self._get_bottom_region_bounds(w)
        regions = [
            ("这边不是入球区=>", "#e74c3c"),
            ("⚽ !!入球区!! ⚽", "#ffff00"),
            ("<=这边不是入球区", "#e74c3c")
        ]
        for i, (name, color) in enumerate(regions):
            x0 = bounds[i]
            x1 = bounds[i + 1]
            self.board_canvas.create_rectangle(x0, bottom_y, x1, bottom_y + 40,
                                            fill=color, outline='black')
            self.board_canvas.create_text((x0 + x1) // 2, bottom_y + 20,
                                        text=name, fill='black', font=('Arial', 9, 'bold'))

        self.board_canvas.create_text(20, 30, text=f"主\n {self.home_score}",
                                    fill='#3498db', font=('Arial', 96, 'bold'), anchor='nw')
        self.board_canvas.create_text(w - 20, 30, text=f"客\n {self.away_score}",
                                    fill='#e74c3c', font=('Arial', 96, 'bold'), anchor='ne')

    def update_game_display(self):
        self.round_label.config(text=f"第 {self.current_round} / {self.rounds_total} 轮")
        self.draw_board()

    # ---------- 比赛流程 ----------
    def start_match(self):
        if self.match_in_progress:
            return
        
        total_bet = self.calc_total_bet()
        if total_bet > self.balance:
            messagebox.showerror("余额不足", "下注总额超过余额")
            return

        if self.animation_running:
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
            self.animation_running = False
            self.balls.clear()
            self.active_balls = 0

        # 清空所有高亮样式
        self._reset_all_bet_styles()

        # 扣除下注金额
        self.balance -= total_bet
        self.update_balance_display()
        self.update_total_bet_display()

        # 重置比赛数据
        self.match_in_progress = True
        self.home_score = 0
        self.away_score = 0
        self.current_round = 0
        self.balls_in_round = 0
        self.balls.clear()
        self.active_balls = 0
        self.status_label.config(text="游戏开始，祝你好运！")

        # 禁用所有下注交互
        self.start_button.config(state=tk.DISABLED)
        self.reset_bets_button.config(state=tk.DISABLED)
        self._set_bet_interaction_enabled(False)

        self.update_game_display()
        self.launch_round()
        if not self.animation_running:
            self.animation_running = True
            self.animate_balls()

    def _reset_all_bet_styles(self):
        """恢复所有下注选项的默认样式（白色背景，显示下注金额）"""
        # 原有三个
        self.bet_home_display.config(bg='white', text=format_money(self.bet_home))
        self.bet_draw_display.config(bg='white', text=format_money(self.bet_draw))
        self.bet_away_display.config(bg='white', text=format_money(self.bet_away))
        # 总入球
        for opt in self.total_goal_options:
            self.total_goal_labels[opt].config(bg='white', text=format_money(self.total_goal_bets[opt]))
        # 大小球
        for key in self.over_under_options:
            self.over_under_labels[key].config(bg='white', text=format_money(self.over_under_bets[key]))

    def _set_bet_interaction_enabled(self, enabled):
        """启用/禁用所有下注选项的点击事件"""
        if enabled:
            # 原有绑定
            self.bet_home_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("home"))
            self.bet_home_display.bind("<Button-3>", lambda e: self.reset_single_bet("home"))
            self.bet_draw_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("draw"))
            self.bet_draw_display.bind("<Button-3>", lambda e: self.reset_single_bet("draw"))
            self.bet_away_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("away"))
            self.bet_away_display.bind("<Button-3>", lambda e: self.reset_single_bet("away"))
            # 总入球绑定
            for opt in self.total_goal_options:
                lbl = self.total_goal_labels[opt]
                lbl.bind("<Button-1>", lambda e, o=opt: self.add_bet_to_total_goal(o))
                lbl.bind("<Button-3>", lambda e, o=opt: self.reset_total_goal_single(o))
            # 大小球绑定
            for key in self.over_under_options:
                lbl = self.over_under_labels[key]
                lbl.bind("<Button-1>", lambda e, k=key: self.add_bet_to_over_under(k))
                lbl.bind("<Button-3>", lambda e, k=key: self.reset_over_under_single(k))
            # 筹码绑定
            for chip in self.chip_buttons:
                text = self.chip_texts[chip]
                chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        else:
            # 解绑所有下注选项
            for display in self.bet_displays.values():
                display.unbind("<Button-1>")
                display.unbind("<Button-3>")
            for lbl in self.total_goal_labels.values():
                lbl.unbind("<Button-1>")
                lbl.unbind("<Button-3>")
            for lbl in self.over_under_labels.values():
                lbl.unbind("<Button-1>")
                lbl.unbind("<Button-3>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")

    def launch_round(self):
        if self.current_round >= self.rounds_total:
            return

        self.current_round += 1
        self.balls_in_round = 0

        w = self.board_canvas.winfo_width()
        if w < 100:
            w = 600

        start_x = w // 2
        start_y = 60
        now = time.time()

        self.balls.append({
            'x': start_x + random.uniform(-5, 5),
            'y': start_y,
            'vx': random.uniform(-0.5, 0.5),
            'vy': 0.0,
            'color': '#3498db',
            'finished': False,
            'team': 'home',
            'last_move_time': now,
            'last_x': start_x,
            'last_y': start_y
        })

        self.balls.append({
            'x': start_x + random.uniform(-5, 5),
            'y': start_y,
            'vx': random.uniform(-0.5, 0.5),
            'vy': 0.0,
            'color': '#e74c3c',
            'finished': False,
            'team': 'away',
            'last_move_time': now,
            'last_x': start_x,
            'last_y': start_y
        })

        self.active_balls += 2
        self.update_game_display()

    def determine_region(self, x, width):
        left_edge, b1, b2, right_edge = self._get_bottom_region_bounds(width)
        if x < b1:
            return "home"
        elif x < b2:
            return "draw"
        else:
            return "away"

    def update_ball_position(self, ball, width, height):
        if ball['finished']:
            return

        now = time.time()

        # 兼容旧球体数据：如果没有“卡住检测”字段，就补上
        if 'last_move_time' not in ball:
            ball['last_move_time'] = now
        if 'last_x' not in ball:
            ball['last_x'] = ball.get('x', 0)
        if 'last_y' not in ball:
            ball['last_y'] = ball.get('y', 0)

        ball['vy'] += self.gravity
        new_x = ball['x'] + ball['vx']
        new_y = ball['y'] + ball['vy']

        top_y = 60
        bottom_y = height - 60
        radius = 8

        bounds = self._get_bottom_region_bounds(width)
        min_x = bounds[0] + radius
        max_x = bounds[3] - radius

        progress = max(0, min(1, (new_y - top_y) / (bottom_y - top_y))) if bottom_y > top_y else 0
        top_w = 40
        bottom_w = width - 180
        cur_w = top_w + (bottom_w - top_w) * progress
        center_min_x = width // 2 - cur_w // 2 + radius
        center_max_x = width // 2 + cur_w // 2 - radius

        min_x = max(min_x, center_min_x)
        max_x = min(max_x, center_max_x)

        # 左右边界反弹
        if new_x < min_x:
            new_x = min_x
            ball['vx'] = -ball['vx'] * self.damping
        elif new_x > max_x:
            new_x = max_x
            ball['vx'] = -ball['vx'] * self.damping

        # 钉子碰撞
        for (px, py) in self.pegs:
            dx = new_x - px
            dy = new_y - py
            dist = math.hypot(dx, dy)

            if dist < radius + 5:
                if dx == 0 and dy == 0:
                    continue

                nx, ny = dx / dist, dy / dist
                dot = ball['vx'] * nx + ball['vy'] * ny

                ball['vx'] -= 2 * dot * nx
                ball['vy'] -= 2 * dot * ny
                ball['vx'] *= self.damping
                ball['vy'] *= self.damping

                overlap = (radius + 5) - dist
                new_x += nx * overlap * 1.1
                new_y += ny * overlap * 1.1
                ball['vx'] += random.uniform(-0.3, 0.3)

        # 处理“卡住”：5 秒内几乎没有位置变化，就轻微往上跳一下
        moved = math.hypot(new_x - ball['last_x'], new_y - ball['last_y'])

        if moved > 0.35:
            ball['last_move_time'] = now
            ball['last_x'] = new_x
            ball['last_y'] = new_y
        elif now - ball['last_move_time'] >= 5.0:
            new_y = max(top_y + radius + 1, new_y - 12)
            new_x += random.uniform(-1.0, 1.0)

            # 给一点向上和横向扰动，帮助脱离死角
            ball['vy'] = -abs(ball['vy']) * 0.6 - random.uniform(0.8, 1.5)
            ball['vx'] = random.uniform(-1.2, 1.2)

            # 重新限制横向范围
            new_x = max(min_x, min(max_x, new_x))

            ball['last_move_time'] = now
            ball['last_x'] = new_x
            ball['last_y'] = new_y

        ball['x'] = new_x
        ball['y'] = new_y

        if new_y >= bottom_y - radius:
            ball['finished'] = True
            ball['y'] = bottom_y - radius
            region = self.determine_region(new_x, width)

            if region == "draw":
                if ball['team'] == 'home':
                    self.home_score += 1
                    self.show_score_effect(new_x, bottom_y - radius, "主队 +1", "#2ecc71")
                else:
                    self.away_score += 1
                    self.show_score_effect(new_x, bottom_y - radius, "客队 +1", "#e74c3c")
            else:
                self.show_score_effect(new_x, bottom_y - radius, "不得分", "gray")

            self.update_game_display()

    def show_score_effect(self, x, y, text, color):
        tid = self.board_canvas.create_text(x, y-20, text=text, fill=color, font=('Arial',12,'bold'))
        self.after(1200, lambda: self.board_canvas.delete(tid))

    def animate_balls(self):
        if not self.match_in_progress and not self.balls:
            self.animation_running = False
            return
        w = self.board_canvas.winfo_width()
        h = self.board_canvas.winfo_height()
        if w < 100 or h < 100:
            self.after_id = self.after(30, self.animate_balls)
            return

        finished_indices = []
        for idx, ball in enumerate(self.balls):
            if not ball['finished']:
                self.update_ball_position(ball, w, h)
                if ball['finished']:
                    finished_indices.append(idx)

        self.draw_board()
        for ball in self.balls:
            if not ball['finished']:
                x, y = ball['x'], ball['y']
                self.board_canvas.create_oval(x-8, y-8, x+8, y+8, fill=ball['color'], outline='white', width=2)
            else:
                x, y = ball['x'], ball['y']
                self.board_canvas.create_oval(x-8, y-8, x+8, y+8, fill=ball['color'], outline='white', width=2)

        if finished_indices:
            for idx in sorted(finished_indices, reverse=True):
                self.balls.pop(idx)
            self.balls_in_round += len(finished_indices)
            self.active_balls = len(self.balls)

            if self.balls_in_round >= 2 and self.current_round < self.rounds_total:
                self.launch_round()
            elif self.current_round >= self.rounds_total and self.active_balls == 0:
                self.finish_match()
                return

        if any(not ball['finished'] for ball in self.balls):
            self.after_id = self.after(30, self.animate_balls)
        else:
            self.animation_running = False
            if not self.match_in_progress:
                self._set_bet_interaction_enabled(True)

    def finish_match(self):
        self.match_in_progress = False
        self.animation_running = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None

        # 判定胜负（原有）
        if self.home_score > self.away_score:
            result = "home"
            result_text = "主队获胜！"
        elif self.home_score < self.away_score:
            result = "away"
            result_text = "客队获胜！"
        else:
            result = "draw"
            result_text = "和局！"

        win_amount = 0.0
        # 原有胜负结算
        if result == "home":
            win_amount += self.bet_home * self.odds["home"]
        elif result == "away":
            win_amount += self.bet_away * self.odds["away"]
        else:
            win_amount += self.bet_draw * self.odds["draw"]

        # 总入球结算
        total_goals = self.home_score + self.away_score
        for opt, bet in self.total_goal_bets.items():
            # 判断该选项是否获胜
            win = False
            if opt == "0/1" and total_goals in (0, 1):
                win = True
            elif opt == "2" and total_goals == 2:
                win = True
            elif opt == "3" and total_goals == 3:
                win = True
            elif opt == "4" and total_goals == 4:
                win = True
            elif opt == "5" and total_goals == 5:
                win = True
            elif opt == "6+" and total_goals >= 6:
                win = True

            if win:
                # 如果获胜，累加赢额（下注金额 × 赔率）
                win_amount += bet * self.total_goal_odds[opt]
                # 背景设为金色，显示应得金额（未下注则显示 0）
                self.total_goal_labels[opt].config(
                    bg='gold',
                    text=format_money(bet * self.total_goal_odds[opt])
                )
            else:
                # 未获胜：背景白色，显示 0
                self.total_goal_labels[opt].config(bg='white', text="0")

        # 大小球结算
        for key, bet in self.over_under_bets.items():
            win = False
            if key == "under4.5" and total_goals <= 4:
                win = True
            elif key == "over4.5" and total_goals >= 5:
                win = True
            elif key == "under3.5" and total_goals <= 3:
                win = True
            elif key == "over3.5" and total_goals >= 4:
                win = True

            if win:
                win_amount += bet * self.over_under_odds[key]
                self.over_under_labels[key].config(
                    bg='gold',
                    text=format_money(bet * self.over_under_odds[key])
                )
            else:
                self.over_under_labels[key].config(bg='white', text="0")

        self.balance += win_amount
        self.update_balance_display()

        # 高亮显示赢额并重置下注金额
        total_bet_old = self.bet_home + self.bet_draw + self.bet_away
        if total_bet_old > 0:
            if result == "home":
                self.bet_home_display.config(bg='gold', text=format_money(self.bet_home * self.odds["home"]))
                self.bet_draw_display.config(bg='white', text="0")
                self.bet_away_display.config(bg='white', text="0")
            elif result == "away":
                self.bet_away_display.config(bg='gold', text=format_money(self.bet_away * self.odds["away"]))
                self.bet_home_display.config(bg='white', text="0")
                self.bet_draw_display.config(bg='white', text="0")
            else:
                self.bet_draw_display.config(bg='gold', text=format_money(self.bet_draw * self.odds["draw"]))
                self.bet_home_display.config(bg='white', text="0")
                self.bet_away_display.config(bg='white', text="0")
        else:
            self.bet_home_display.config(bg='white', text="0")
            self.bet_draw_display.config(bg='white', text="0")
            self.bet_away_display.config(bg='white', text="0")

        # 清空所有下注变量（准备下一局）
        self.bet_home = self.bet_draw = self.bet_away = 0
        for opt in self.total_goal_options:
            self.total_goal_bets[opt] = 0
        for key in self.over_under_options:
            self.over_under_bets[key] = 0
        self.update_total_bet_display()

        self.draw_board()
        self.last_win = win_amount
        self.last_win_label.config(text=f"上局获胜: ${format_money(win_amount)}")

        # 进入结算模式，隐藏开始/重置，显示再来一局
        self.start_button.pack_forget()
        self.reset_bets_button.pack_forget()
        self.play_again_button.pack(side=tk.LEFT, padx=5)

        self.status_label.config(text=f"比赛结束，比分 {self.home_score}:{self.away_score}，{result_text}")

    def play_again(self):
        """重置所有状态，恢复交互"""
        if self.animation_running:
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
            self.animation_running = False
        self.balls.clear()
        self.active_balls = 0

        # 重置所有下注显示为白色背景和0
        self.bet_home_display.config(bg='white', text="0")
        self.bet_draw_display.config(bg='white', text="0")
        self.bet_away_display.config(bg='white', text="0")
        for opt in self.total_goal_options:
            self.total_goal_labels[opt].config(bg='white', text="0")
        for key in self.over_under_options:
            self.over_under_labels[key].config(bg='white', text="0")

        # 重置比赛数据
        self.home_score = 0
        self.away_score = 0
        self.current_round = 0
        self.match_in_progress = False

        # 清空下注变量（再次确保）
        self.bet_home = self.bet_draw = self.bet_away = 0
        for opt in self.total_goal_options:
            self.total_goal_bets[opt] = 0
        for key in self.over_under_options:
            self.over_under_bets[key] = 0
        self.update_total_bet_display()

        # 恢复按钮布局，使用与初始一致的 pack 参数
        self.play_again_button.pack_forget()
        self.reset_bets_button.pack(side=tk.LEFT, padx=5)
        self.start_button.pack(side=tk.LEFT, padx=5)

        # 启用按钮
        self.start_button.config(state=tk.NORMAL)
        self.reset_bets_button.config(state=tk.NORMAL)

        # 重新启用所有下注交互
        self._set_bet_interaction_enabled(True)

        self.status_label.config(text="请下注并开始比赛")
        self.update_game_display()

    def on_close(self):
        if self.after_id:
            self.after_cancel(self.after_id)
        self.destroy()


# ================== 外部调用接口 ==================
def main(initial_balance, username):
    app = FootballPachinko(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    main(10000000.0, "test_user")