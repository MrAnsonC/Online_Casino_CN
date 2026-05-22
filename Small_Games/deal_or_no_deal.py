import tkinter as tk
from tkinter import messagebox, simpledialog
import random
import json
import os
import statistics

# ---------------------------- 数据文件操作 ----------------------------
def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

# ---------------------------- 圆形筹码按钮 ----------------------------
class CircleButton(tk.Canvas):
    def __init__(self, master, text, bg_color, fg_color, command=None, radius=30, *args, **kwargs):
        super().__init__(master, width=radius*2, height=radius*2,
                         highlightthickness=0, bg="#16213e", *args, **kwargs)
        self.radius = radius
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text = text
        self.command = command

        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)
        self.create_text(radius, radius, text=text, fill=fg_color,
                         font=("Arial", 12, "bold"))
        self.bind("<Button-1>", self.on_click)

    def on_click(self, event):
        if self.command:
            self.command()

# ---------------------------- 手绘风格箱子按钮 ----------------------------
class CaseButton(tk.Canvas):
    """手绘风格箱子按钮"""
    def __init__(self, master, idx, command=None, **kwargs):
        super().__init__(master, width=90, height=90, highlightthickness=1,
                         highlightbackground="#555", bg="#0f3460", **kwargs)
        self.idx = idx
        self.command = command
        self.is_open = False
        self.is_selected = False
        self.amount_text = ""
        self.bind("<Button-1>", self._on_click)
        self.draw_closed()

    def draw_closed(self, is_selected=False):
        """绘制关闭状态的箱子，如果 is_selected=True 则箱体为金色"""
        self.delete("all")
        if is_selected:
            color = "#FFD700"      # 金色（选中）
        else:
            color = "#8B4513"      # 棕色（普通）
        handle_color = "#654321"
        # 箱体
        self.create_rectangle(10, 15, 80, 75, fill=color, outline="black", width=2, tags="box")
        self.create_rectangle(10, 15, 80, 32, fill=handle_color, outline="black", width=2, tags="lid")
        self.create_arc(38, 7, 52, 20, start=0, extent=180, fill=handle_color, outline="black", tags="handle")
        # 木纹
        for i in range(2):
            y = 45 + i * 15
            self.create_line(18, y, 72, y, fill="#3d2b1f", width=2, tags="wood")
        # 锁孔
        self.create_oval(40, 55, 50, 65, fill="#2c3e50", outline="gold", tags="lock")
        # 问号
        self.create_text(45, 45, text="?", font=("Arial", 16, "bold"), fill="#FFD700", tags="question")

    def draw_open(self, color=None):
        """打开箱子，可自定义背景色（默认浅棕色）"""
        self.delete("all")
        fill_color = color if color else "#F5DEB3"
        handle_color = "#654321"
        self.create_rectangle(10, 15, 80, 75, fill=fill_color, outline="black", width=2)
        self.create_rectangle(10, 15, 80, 32, fill=handle_color, outline="black", width=2)
        self.create_arc(38, 7, 52, 20, start=0, extent=180, fill=handle_color, outline="black")
        self.create_oval(40, 55, 50, 65, fill="#2c3e50", outline="gold")
        if self.amount_text:
            font_size = 11 if len(self.amount_text) <= 8 else 9
            self.create_text(45, 45, text=self.amount_text, font=("Arial", font_size, "bold"),
                            fill="#8B4513", tags="amount")

    def set_open(self, amount, custom_color=None):
        """打开箱子，可指定自定义背景色"""
        self.is_open = True
        self.amount_text = amount
        self.draw_open(custom_color)
        self.unbind("<Button-1>")
        self.config(cursor="arrow")

    def set_closed(self):
        """重置为关闭状态（未选中，未打开）"""
        self.is_open = False
        self.is_selected = False
        self.amount_text = ""
        self.draw_closed(False)
        self.bind("<Button-1>", self._on_click)

    def set_selected(self, selected=True):
        """设置选中状态（箱体变金色）"""
        self.is_selected = selected
        if not self.is_open:
            self.draw_closed(selected)

    def enable(self):
        """启用点击"""
        if not self.is_open:
            self.bind("<Button-1>", self._on_click)
            self.config(cursor="hand2")

    def disable(self):
        """禁用点击"""
        self.unbind("<Button-1>")
        self.config(cursor="arrow")

    def _on_click(self, event):
        if self.is_open:
            return
        if self.command:
            self.command(self.idx)


# ---------------------------- 箱子基础价值（n=1时）------------------------
BASE_VALUES = [
    0.01, 0.1, 0.5, 1, 2, 5, 10, 15,
    20, 25, 35, 50, 60, 75, 100, 125,
    150, 175, 200, 250, 300, 350, 400, 500,
    650, 800, 1000, 1500,
    2500, 5000, 10000, 12000
]

# ---------------------------- 游戏主类 ----------------------------
class DealOrNoDealGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("Deal or No Deal")
        self.root.geometry("1400x760+50+10")
        self.root.resizable(0, 0)
        self.root.configure(bg="#1a1a2e")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 游戏状态变量
        self.username = username
        self.balance = float(initial_balance)
        self.bet_amount = 0
        self.n = 1
        self.box_values = []
        self.player_box_index = -1
        self.player_box_value = 0
        self.opened_indices = set()
        self.rounds = [7, 6, 5, 4, 3, 2, 1, 1, 1]   # 共9轮
        self.current_round = 0
        self.to_open_this_round = 0
        self.game_active = False
        self.waiting_for_decision = False
        self.lost_quote_right = False
        self.last_win = 0.0
        self.current_offer = 0.0

        # 历史报价列表
        self.offer_history = []  # 存储每次报价的字符串，例如 "首次报价: $100,000.11"

        # UI 引用
        self.box_buttons = []
        self.chip_buttons = []
        self.remaining_labels = []
        self.sorted_amounts = []

        # 右侧动态按钮区域
        self.action_frame = None
        self.reset_bets_button = None
        self.start_button = None
        self.decision_frame = None
        self.continue_btn = None
        self.accept_btn = None
        self.offer_btn = None
        self.newgame_btn = None

        # 历史报价显示标签列表
        self.history_labels = []

        self.create_widgets()
        self.update_balance_display()

    # ---------------------------- UI 构建 ----------------------------
    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 左侧区域：箱子（左） + 剩余奖金面板（右）
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # ----- 左边：箱子区域 (5列7行，共35格，只显示前32个) -----
        boxes_container = tk.Frame(left_frame, bg="#0f3460", padx=10, pady=10)
        boxes_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.create_boxes(boxes_container)

        # ----- 右边：剩余奖金面板 (4列8行，显示32个金额) -----
        remaining_frame = tk.LabelFrame(left_frame, text="剩余奖金", font=("Arial", 12, "bold"),
                                        bg="#16213e", fg="#f1f1f1", bd=2, relief=tk.RIDGE)
        remaining_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5, pady=5, expand=True)
        self.create_remaining_panel(remaining_frame)

        # 右侧控制面板
        right_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE, width=380)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_frame.pack_propagate(False)

        # 余额显示
        balance_frame = tk.Frame(right_frame, bg="#16213e")
        balance_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(balance_frame, text="余额:", font=("Arial", 18),
                 bg="#16213e", fg="#f1f1f1").pack(side=tk.LEFT)
        self.balance_var = tk.StringVar(value=f"${self.balance:.2f}")
        tk.Label(balance_frame, textvariable=self.balance_var, font=("Arial", 18, "bold"),
                 bg="#16213e", fg="#ffd369").pack(side=tk.LEFT, padx=5)

        # 筹码区域
        chip_frame = tk.Frame(right_frame, bg="#16213e")
        chip_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(chip_frame, text="选择下注金额:", font=("Arial", 16),
                 bg="#16213e", fg="white").pack(anchor=tk.W)
        chip_btn_frame = tk.Frame(chip_frame, bg="#16213e")
        chip_btn_frame.pack(pady=5)

        chips = [("1K", 1000), ("5K", 5000), ("10K", 10000), ("25K", 25000), ("100K", 100000)]
        colors = [("#ff0000", "white"), ("#00ff00", "black"), ("#000000", "white"),
                  ("#FF7DDA", "black"), ("#ffffff", "black")]
        for (text, val), (bg, fg) in zip(chips, colors):
            btn = CircleButton(chip_btn_frame, text=text, bg_color=bg, fg_color=fg,
                               command=lambda v=val: self.add_chip(v), radius=25)
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)

        # 下注总额显示
        bet_show_frame = tk.Frame(right_frame, bg="#16213e")
        bet_show_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(bet_show_frame, text="下注总额:", font=("Arial", 16),
                 bg="#16213e", fg="white").pack(side=tk.LEFT)
        self.bet_var = tk.StringVar(value="$0")
        tk.Label(bet_show_frame, textvariable=self.bet_var, font=("Arial", 14, "bold"),
                 bg="#16213e", fg="#4cc9f0").pack(side=tk.LEFT, padx=5)

        # 上局获胜显示
        last_win_frame = tk.Frame(right_frame, bg="#16213e")
        last_win_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(last_win_frame, text="上局获胜:", font=("Arial", 16),
                 bg="#16213e", fg="white").pack(side=tk.LEFT)
        self.last_win_var = tk.StringVar(value="$0.00")
        tk.Label(last_win_frame, textvariable=self.last_win_var, font=("Arial", 16, "bold"),
                 bg="#16213e", fg="#4cc9f0").pack(side=tk.LEFT, padx=5)

        # 游戏信息
        self.round_info_var = tk.StringVar(value="未开始游戏")
        tk.Label(right_frame, textvariable=self.round_info_var, font=("Arial", 14, "bold"),
                 bg="#16213e", fg="#f39c12").pack(pady=5)
        self.need_open_var = tk.StringVar(value="")
        tk.Label(right_frame, textvariable=self.need_open_var, font=("Arial", 14),
                 bg="#16213e", fg="#f1f1f1").pack()

        # 动态按钮区域
        self.action_frame = tk.Frame(right_frame, bg="#16213e")
        self.action_frame.pack(fill=tk.X, padx=10, pady=10)
        self.show_start_buttons()

        # 历史报价面板（替换原来的游戏规则）
        history_frame = tk.LabelFrame(right_frame, text="历史报价", font=("Arial", 18, "bold"),
                                    bg="#16213e", fg="#f1f1f1", bd=2, relief=tk.RIDGE)
        history_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)  # 固定底部
        self.create_history_panel(history_frame)

    def create_history_panel(self, parent):
        """创建历史报价显示区域，两列布局：左列首次~四次，右列五次~八次，底部居中显示最终报价，字体14"""
        self.history_labels = []  # 仍按顺序存储9个标签：[0首次,1二次,2三次,3四次,4五次,5六次,6七次,7八次,8最终]

        # 左侧列：首次到四次
        left_frame = tk.Frame(parent, bg="#16213e")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # 右侧列：五到八次
        right_frame = tk.Frame(parent, bg="#16213e")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        # 左列标签
        left_titles = ["首次:", "二次:", "三次:", "四次:"]
        for i, title in enumerate(left_titles):
            frame = tk.Frame(left_frame, bg="#16213e")
            frame.pack(fill=tk.X, pady=5)
            lbl_title = tk.Label(frame, text=title, font=("Arial", 14),
                                bg="#16213e", fg="#bdc3c7", anchor=tk.W)
            lbl_title.pack(side=tk.LEFT)
            lbl_value = tk.Label(frame, text="$ ------", font=("Arial", 14, "bold"),
                                bg="#16213e", fg="#ffd369", anchor=tk.W)
            lbl_value.pack(side=tk.LEFT, padx=5)
            self.history_labels.append(lbl_value)

        # 右列标签
        right_titles = ["五次:", "六次:", "七次:", "八次:"]
        for i, title in enumerate(right_titles):
            frame = tk.Frame(right_frame, bg="#16213e")
            frame.pack(fill=tk.X, pady=5)
            lbl_title = tk.Label(frame, text=title, font=("Arial", 14),
                                bg="#16213e", fg="#bdc3c7", anchor=tk.W)
            lbl_title.pack(side=tk.LEFT)
            lbl_value = tk.Label(frame, text="$ ------", font=("Arial", 14, "bold"),
                                bg="#16213e", fg="#ffd369", anchor=tk.W)
            lbl_value.pack(side=tk.LEFT, padx=5)
            self.history_labels.append(lbl_value)

    def update_history_display(self):
        """根据 self.offer_history 更新历史报价显示（保持不变，按索引顺序填充）"""
        # 清空显示为 "$ ------"
        for lbl in self.history_labels:
            lbl.config(text="$ ------")
        # 填充已有记录
        for i, offer_str in enumerate(self.offer_history):
            if i < len(self.history_labels):
                self.history_labels[i].config(text=offer_str)

    def update_history_display(self):
        """根据 self.offer_history 更新历史报价显示"""
        # 清空显示为 "$ ------"
        for lbl in self.history_labels:
            lbl.config(text="$ ------")
        # 填充已有记录
        for i, offer_str in enumerate(self.offer_history):
            if i < len(self.history_labels):
                self.history_labels[i].config(text=offer_str)

    def add_offer_to_history(self, offer_amount):
        """添加一条报价记录到历史列表，并刷新显示"""
        offer_text = self.format_money(offer_amount)
        full_text = f"{offer_text}"
        self.offer_history.append(full_text)
        self.update_history_display()

    def clear_history(self):
        """清空历史报价（新游戏时调用）"""
        self.offer_history.clear()
        self.update_history_display()

    def show_start_buttons(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        btn_frame = tk.Frame(self.action_frame, bg='#16213e')
        btn_frame.pack()
        self.reset_bets_button = tk.Button(
            btn_frame, text="重置金额", font=('Arial', 14),
            command=self.reset_bet, bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
        self.start_button = tk.Button(
            btn_frame, text="开始游戏", font=('Arial', 14),
            command=self.start_game, bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        self.start_button.config(state=tk.DISABLED)

    def show_decision_buttons(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        self.decision_frame = tk.Frame(self.action_frame, bg="#16213e")
        self.decision_frame.pack(fill=tk.X)

        self.offer_label = tk.Label(self.decision_frame, text="", font=("Arial", 14, "bold"),
                                    bg="#16213e", fg="#ffd369")
        self.offer_label.pack(pady=2)

        # 水平按钮容器
        btn_frame = tk.Frame(self.decision_frame, bg="#16213e")
        btn_frame.pack(pady=5)

        self.continue_btn = tk.Button(btn_frame, text="继续游戏", font=("Arial", 14),
                                    bg="#3498db", fg="white", command=self.continue_game,
                                    width=8)
        self.continue_btn.pack(side=tk.LEFT, padx=5)

        self.accept_btn = tk.Button(btn_frame, text="接受报价", font=("Arial", 14),
                                    bg="#e74c3c", fg="white", command=self.accept_offer,
                                    state=tk.DISABLED, width=8)
        self.accept_btn.pack(side=tk.LEFT, padx=5)

        self.offer_btn = tk.Button(btn_frame, text="反向报价", font=("Arial", 14),
                                bg="#f39c12", fg="white", command=self.counter_offer,
                                width=8)
        self.offer_btn.pack(side=tk.LEFT, padx=5)

        self.decision_frame.pack_forget()

    def show_newgame_button(self):
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        self.newgame_btn = tk.Button(self.action_frame, text="再来一局", font=('Arial', 12, 'bold'),
                                     bg='#8e44ad', fg='white', command=self.reset_for_newgame)
        self.newgame_btn.pack()

    # ---------------------------- 创建箱子(5列7行，只显示前32个) ----------------------------
    def create_boxes(self, parent):
        """5列7行网格，第4行只有2个箱子（列0和列2）"""
        self.box_buttons = []
        box_idx = 0
        for row in range(7):
            for col in range(5):
                if row == 3 and col not in (1, 3):
                    # 占位空白（与箱子等大）
                    spacer = tk.Frame(parent, width=90, height=90, bg="#0f3460")
                    spacer.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
                    continue
                # 创建箱子
                case = CaseButton(parent, box_idx, command=self.on_box_click)
                case.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
                self.box_buttons.append(case)
                box_idx += 1
        # 让各列等宽
        for col in range(5):
            parent.grid_columnconfigure(col, weight=1)

    # ---------------------------- 剩余奖金面板（排序显示）------------------------
    def create_remaining_panel(self, parent):
        """创建3列的剩余奖金面板，金额从小到大排序（紧凑风格，降低高度）"""
        self.remaining_labels = []
        # 总共32个金额，3列共11行（33格），最后一格留空
        for i in range(32):
            lbl = tk.Label(parent, text="", font=("Arial", 18),   # 字体10号更紧凑
                        bg="#2c3e50", fg="#ecf0f1", relief=tk.RIDGE,
                        width=8, height=2)   # height=1 单行文本高度最小
            row = i // 3
            col = i % 3
            lbl.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
            self.remaining_labels.append(lbl)
        # 关键修改：不设置行权重（或 weight=0），避免行高被拉伸
        for i in range(3):
            parent.grid_columnconfigure(i, weight=1)
        # 可选：设置整个面板禁止自动扩展高度（保留原有大小）
        parent.pack_propagate(False)  # 如果希望完全固定高度，可启用；但一般不需要

    def update_remaining_panel(self):
        if not self.box_values:
            return
        sorted_values = sorted(self.box_values)
        self.sorted_amounts = sorted_values
        opened_amounts = {self.box_values[i] for i in self.opened_indices}
        for i, amount in enumerate(sorted_values):
            lbl = self.remaining_labels[i]
            lbl.config(text=self.format_money(amount))
            if amount in opened_amounts:
                lbl.config(bg="#34495e", fg="#7f8c8d")
            else:
                lbl.config(bg="#2c3e50", fg="#ecf0f1")

    # ---------------------------- 下注逻辑 ----------------------------
    def add_chip(self, amount):
        if not self.game_active and not self.waiting_for_decision and self.start_button:
            new_bet = self.bet_amount + amount
            if new_bet <= self.balance and new_bet <= 1000000:
                self.bet_amount = new_bet
                self.bet_var.set(f"${self.bet_amount}")
            else:
                messagebox.showwarning("下注限制", f"下注不能超过1,000,000")

    def reset_bet(self):
        if not self.game_active and not self.waiting_for_decision and self.start_button:
            self.bet_amount = 0
            self.bet_var.set("$0")

    # ---------------------------- 选箱与开箱 ----------------------------
    def on_box_click(self, idx):
        if self.game_active and not self.waiting_for_decision:
            self.open_box(idx)
        elif not self.game_active and not self.waiting_for_decision and self.start_button:
            self.select_box(idx)

    def select_box(self, idx):
        """允许重复选箱：清除所有箱子的选中状态，然后高亮新选中的箱子"""
        # 清除所有箱子的选中
        for case in self.box_buttons:
            case.set_selected(False)
        # 设置新选中的箱子为金色
        self.box_buttons[idx].set_selected(True)
        self.player_box_index = idx
        self.start_button.config(state=tk.NORMAL)

    def open_box(self, idx):
        if idx == self.player_box_index:
            return
        if idx in self.opened_indices:
            return
        if self.to_open_this_round <= 0:
            messagebox.showinfo("提示", "本轮开箱数量已满，请等待报价")
            return

        self.opened_indices.add(idx)
        self.to_open_this_round -= 1
        val = self.box_values[idx]
        formatted = self.format_money(val)
        self.box_buttons[idx].set_open(formatted)
        self.update_remaining_panel()
        self.need_open_var.set(f"本轮剩余开箱: {self.to_open_this_round}")

        if self.to_open_this_round == 0:
            self.enter_offer_phase()

    # ---------------------------- 开始游戏 ----------------------------
    def start_game(self):
        if self.bet_amount <= 0:
            messagebox.showinfo("提示", "请先下注")
            return
        if self.bet_amount % 1000 != 0:
            messagebox.showinfo("提示", "下注金额必须是1000的倍数")
            return
        if self.bet_amount > self.balance:
            messagebox.showinfo("错误", "下注超过余额")
            return
        if self.player_box_index == -1:
            messagebox.showinfo("提示", "请先点击一个箱子作为你的宝箱")
            return

        self.balance -= self.bet_amount
        update_balance_in_json(self.username, self.balance)
        self.update_balance_display()

        # 新游戏，清空历史报价
        self.clear_history()

        self.n = self.bet_amount / 1000
        self.box_values = [round(v * self.n, 2) for v in BASE_VALUES]
        random.shuffle(self.box_values)
        self.player_box_value = self.box_values[self.player_box_index]

        self.opened_indices = set()
        self.current_round = 0
        self.to_open_this_round = self.rounds[0]
        self.game_active = True
        self.waiting_for_decision = False
        self.lost_quote_right = False

        self.need_open_var.set(f"本轮剩余开箱: {self.to_open_this_round}")
        self.round_info_var.set(f"第{self.current_round + 1}轮 | 需开{self.rounds[self.current_round]}个箱")
        self.show_decision_buttons()

        for btn in self.chip_buttons:
            btn.config(state=tk.DISABLED)

        # 刷新所有箱子状态
        for i, case in enumerate(self.box_buttons):
            if i == self.player_box_index:
                # 玩家箱子：禁用点击，保持金色选中状态，不打开
                case.disable()
                case.set_selected(True)
                case.draw_closed(True)   # 重新绘制为金色关闭状态
            else:
                case.enable()
                case.set_closed()        # 重置为未选中棕色关闭状态

        self.update_remaining_panel()

    # ---------------------------- 报价阶段 ----------------------------
    def enter_offer_phase(self):
        self.game_active = False
        self.waiting_for_decision = True

        remaining_indices = [i for i in range(len(self.box_values)) if i not in self.opened_indices]
        remaining_values = [self.box_values[i] for i in remaining_indices]
        offer = self.calculate_banker_offer(self.current_round, remaining_values)
        self.current_offer = offer

        # 记录报价到历史
        self.add_offer_to_history(offer)

        self.offer_label.config(text=f"银行家报价: {self.format_money(offer)}")
        self.decision_frame.pack(fill=tk.X, pady=5)

        self.accept_btn.config(state=tk.NORMAL)
        self.offer_btn.config(state=tk.DISABLED if self.lost_quote_right else tk.NORMAL)

    def calculate_banker_offer(self, round_idx, remaining_values):
        if not remaining_values:
            return 0.0
        ev = sum(remaining_values) / len(remaining_values)
        if ev <= 0:
            return 0.0

        progress = round_idx / max(1, len(self.rounds) - 1)
        remaining_ratio = len(remaining_values) / len(self.box_values)
        std = statistics.pstdev(remaining_values) if len(remaining_values) > 1 else 0.0
        std_ratio = std / ev if ev > 0 else 0.0
        top_value = max(remaining_values)
        top_ratio = top_value / max(BASE_VALUES)
        high_count = sum(1 for v in remaining_values if v >= ev * 2)
        low_count = sum(1 for v in remaining_values if v <= ev * 0.20)

        factor = 0.16 + 0.74 * (progress ** 1.35)
        factor *= 0.95 + 0.08 * (1.0 - remaining_ratio)
        factor *= 1.0 - min(0.16, 0.06 * std_ratio)
        factor += min(0.05, 0.01 * high_count)
        factor -= min(0.03, 0.004 * low_count)
        if top_ratio <= 0.20:
            factor += 0.03
        elif top_ratio <= 0.40:
            factor += 0.015

        jitter = random.uniform(0.985, 1.015)
        offer = ev * factor * jitter
        offer = min(offer, ev * 0.97)
        return round(max(0.0, offer), 2)

    def _advance_to_next_round(self):
        self.waiting_for_decision = False
        self.decision_frame.pack_forget()

        self.current_round += 1
        if self.current_round >= len(self.rounds):
            self.final_two_boxes_choice()
            return False

        self.to_open_this_round = self.rounds[self.current_round]
        self.game_active = True
        self.round_info_var.set(f"第{self.current_round + 1}轮 | 需开{self.rounds[self.current_round]}个箱")
        self.need_open_var.set(f"本轮剩余开箱: {self.to_open_this_round}")

        for i, case in enumerate(self.box_buttons):
            if i == self.player_box_index:
                case.disable()
            elif i not in self.opened_indices:
                case.enable()
            else:
                case.disable()

        self.accept_btn.config(state=tk.DISABLED)
        self.offer_btn.config(state=tk.DISABLED if self.lost_quote_right else tk.NORMAL)
        return True

    # ---------------------------- 决策逻辑 ----------------------------
    def continue_game(self):
        if not self.waiting_for_decision:
            return
        self._advance_to_next_round()

    def accept_offer(self):
        if not self.waiting_for_decision:
            return
        win_amount = self.current_offer
        self.balance += win_amount
        self.last_win = win_amount
        update_balance_in_json(self.username, self.balance)
        self.update_balance_display()
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.reveal_all_boxes()
        messagebox.showinfo("游戏结束", f"你接受了银行家报价 ${win_amount:,.2f}，赢得奖金！")
        self.end_game()

    def counter_offer(self):
        if not self.waiting_for_decision or self.lost_quote_right:
            return
        try:
            player_offer = simpledialog.askfloat(
                "报价",
                "请输入你的报价金额 (美元):",
                minvalue=0,
                maxvalue=1e9
            )
            if player_offer is None:
                return

            remaining_indices = [i for i in range(len(self.box_values)) if i not in self.opened_indices]
            remaining_values = [self.box_values[i] for i in remaining_indices]
            ev = sum(remaining_values) / len(remaining_values) if remaining_values else 0.0
            progress = self.current_round / max(1, len(self.rounds) - 1)

            accept_limit = max(
                self.current_offer * (1.10 + 0.08 * progress),
                ev * (0.22 + 0.42 * progress)
            )

            if player_offer <= accept_limit:
                self.balance += player_offer
                self.last_win = player_offer
                update_balance_in_json(self.username, self.balance)
                self.update_balance_display()
                self.last_win_var.set(f"${self.last_win:.2f}")
                self.reveal_all_boxes()
                messagebox.showinfo("报价成功", f"银行家接受了你的报价 ${player_offer:,.2f}，游戏结束！")
                self.end_game()
            else:
                self.lost_quote_right = True
                messagebox.showwarning(
                    "报价被拒",
                    "银行家拒绝了你的报价，你将失去反报价权力，并自动进入下一轮。"
                )
                self._advance_to_next_round()
        except Exception:
            pass

    # ---------------------------- 游戏结束与二选一 ----------------------------
    def final_two_boxes_choice(self):
        all_indices = set(range(len(self.box_values)))
        unopened = list(all_indices - self.opened_indices)
        if len(unopened) != 2:
            unopened = unopened[:2]

        player_idx = self.player_box_index
        other_idx = unopened[0] if unopened[0] != player_idx else unopened[1]

        player_value = self.box_values[player_idx]
        other_value = self.box_values[other_idx]

        # 创建自定义弹窗
        choice_win = tk.Toplevel(self.root)
        choice_win.title("最终抉择")
        choice_win.geometry("600x400")
        choice_win.resizable(False, False)
        choice_win.configure(bg="#2c3e50")
        choice_win.transient(self.root)
        choice_win.grab_set()
        choice_win.focus_set()

        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 600) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 400) // 2
        choice_win.geometry(f"+{x}+{y}")

        # 提示文字
        tk.Label(
            choice_win,
            text="现在你可以2选1，你是选择打开你的箱子还是打开场上剩下的那个？",
            font=("Arial", 12, "bold"),
            bg="#2c3e50",
            fg="#ffffff"
        ).pack(pady=10)

        # 左右两个箱子的框架
        frame = tk.Frame(choice_win, bg="#2c3e50")
        frame.pack(expand=True, fill=tk.BOTH, padx=30, pady=10)

        # 左侧：你的箱子
        left_frame = tk.Frame(frame, bg="#2c3e50")
        left_frame.pack(side=tk.LEFT, expand=True)
        left_label = tk.Label(left_frame, text="你的箱子", font=("Arial", 12, "bold"),
                              bg="#2c3e50", fg="#ffffff")
        left_label.pack()
        left_canvas = tk.Canvas(left_frame, width=120, height=120, bg="#2c3e50",
                                highlightthickness=2, highlightbackground="#555")
        left_canvas.pack(pady=5)

        # 右侧：场上的箱子
        right_frame = tk.Frame(frame, bg="#2c3e50")
        right_frame.pack(side=tk.RIGHT, expand=True)
        right_label = tk.Label(right_frame, text="场上的箱子", font=("Arial", 12, "bold"),
                               bg="#2c3e50", fg="#ffffff")
        right_label.pack()
        right_canvas = tk.Canvas(right_frame, width=120, height=120, bg="#2c3e50",
                                 highlightthickness=2, highlightbackground="#555")
        right_canvas.pack(pady=5)

        # 绘制关闭的箱子（带纹理和问号）
        def draw_closed_box(canvas):
            canvas.delete("all")
            # 箱体（棕色）
            canvas.create_rectangle(10, 20, 110, 100, fill="#8B4513", outline="black", width=2)
            canvas.create_rectangle(10, 20, 110, 35, fill="#654321", outline="black", width=2)
            canvas.create_arc(50, 10, 70, 25, start=0, extent=180, fill="#654321", outline="black")
            # 木纹线（纹理）
            canvas.create_line(20, 50, 100, 50, fill="#3d2b1f", width=2)
            canvas.create_line(20, 70, 100, 70, fill="#3d2b1f", width=2)
            canvas.create_oval(55, 75, 65, 85, fill="#2c3e50", outline="gold")
            canvas.create_text(60, 45, text="?", font=("Arial", 18, "bold"), fill="#FFD700")

        draw_closed_box(left_canvas)
        draw_closed_box(right_canvas)

        # 状态变量
        chosen = [None]  # "player" 或 "other"
        selected_amount = [0.0]
        confirm_btn = tk.Button(choice_win, text="确认", font=("Arial", 12, "bold"),
                                bg="#4CAF50", fg="white", state=tk.DISABLED,
                                command=lambda: on_confirm())
        confirm_btn.pack(pady=10)

        auto_click_id = [None]

        def enable_confirm():
            confirm_btn.config(state=tk.NORMAL)
            auto_click_id[0] = choice_win.after(30000, lambda: confirm_btn.invoke())

        def disable_auto_click():
            if auto_click_id[0]:
                choice_win.after_cancel(auto_click_id[0])
                auto_click_id[0] = None

        # 打开箱子并显示金额（移除纹理，背景色自定义）
        def open_box_with_amount(canvas, amount, bg_color):
            canvas.delete("all")
            # 箱体（无木纹线）
            canvas.create_rectangle(10, 20, 110, 100, fill=bg_color, outline="black", width=2)
            canvas.create_rectangle(10, 20, 110, 35, fill="#654321", outline="black", width=2)
            canvas.create_arc(50, 10, 70, 25, start=0, extent=180, fill="#654321", outline="black")
            canvas.create_oval(55, 75, 65, 85, fill="#2c3e50", outline="gold")
            # 显示金额
            canvas.create_text(60, 60, text=self.format_money(amount), font=("Arial", 10, "bold"),
                               fill="#8B4513")

        def choose_box(box_type):
            if chosen[0] is not None:
                return
            chosen[0] = box_type
            if box_type == "player":
                selected_amount[0] = player_value
                # 被点击的箱子变白色，另一个变粉红色
                open_box_with_amount(left_canvas, player_value, "white")
                open_box_with_amount(right_canvas, other_value, "#FFC0CB")  # 粉红
            else:
                selected_amount[0] = other_value
                open_box_with_amount(left_canvas, player_value, "#FFC0CB")
                open_box_with_amount(right_canvas, other_value, "white")

            # 解除点击绑定
            left_canvas.unbind("<Button-1>")
            right_canvas.unbind("<Button-1>")

            # 显示提示
            tk.Label(choice_win, text="已选择，3秒后可点击确认", font=("Arial", 10),
                     bg="#2c3e50", fg="#ffd369").pack(pady=2)

            choice_win.after(3000, enable_confirm)

        def on_confirm():
            if chosen[0] is None:
                return
            disable_auto_click()
            choice_win.destroy()
            # 更新余额
            win_amount = selected_amount[0]
            self.balance += win_amount
            self.last_win = win_amount
            update_balance_in_json(self.username, self.balance)
            self.update_balance_display()
            self.last_win_var.set(f"${self.last_win:.2f}")

            # 在主窗口中打开两个未开的箱子，并上色
            if chosen[0] == "player":
                chosen_idx = player_idx
                unchosen_idx = other_idx
            else:
                chosen_idx = other_idx
                unchosen_idx = player_idx

            self.box_buttons[chosen_idx].set_open(self.format_money(self.box_values[chosen_idx]),
                                                  custom_color="white")
            self.box_buttons[unchosen_idx].set_open(self.format_money(self.box_values[unchosen_idx]),
                                                    custom_color="#FFC0CB")

            self.end_game()

        # 绑定点击事件
        left_canvas.bind("<Button-1>", lambda e: choose_box("player"))
        right_canvas.bind("<Button-1>", lambda e: choose_box("other"))

        def on_close():
            if chosen[0] is None:
                messagebox.showwarning("尚未选择", "请选择一个箱子以继续游戏！", parent=choice_win)
            else:
                disable_auto_click()
                choice_win.destroy()

        choice_win.protocol("WM_DELETE_WINDOW", on_close)
        self.root.wait_window(choice_win)

    def format_money(self, value):
        if float(value).is_integer():
            return f"${int(value):,}"
        else:
            return f"${value:,.2f}"

    def reveal_all_boxes(self):
        for i, case in enumerate(self.box_buttons):
            val = self.box_values[i]
            formatted = self.format_money(val)
            if i == self.player_box_index:
                case.set_open(formatted, custom_color="white")
            else:
                case.set_open(formatted)   # 默认浅棕色

    def end_game(self):
        self.game_active = False
        self.waiting_for_decision = False
        self.decision_frame.pack_forget()
        self.show_newgame_button()
        self.round_info_var.set("游戏结束")
        for btn in self.chip_buttons:
            btn.config(state=tk.NORMAL)

    def reset_for_newgame(self):
        self.bet_amount = 0
        self.player_box_index = -1
        self.opened_indices.clear()
        self.current_round = 0
        self.to_open_this_round = 0
        self.game_active = False
        self.waiting_for_decision = False
        self.lost_quote_right = False
        self.bet_var.set("$0")
        self.need_open_var.set("")
        self.round_info_var.set("未开始游戏")
        self.show_start_buttons()
        for btn in self.chip_buttons:
            btn.config(state=tk.NORMAL)
        for case in self.box_buttons:
            case.set_closed()
            case.enable()
        for lbl in self.remaining_labels:
            lbl.config(text="", bg="#2c3e50", fg="#ecf0f1")
        self.update_balance_display()
        # 清空历史报价
        self.clear_history()

    def update_balance_display(self):
        self.balance_var.set(f"${self.balance:.2f}")

    def on_closing(self):
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()


# ---------------------------- 外部调用 ----------------------------
def main(balance, username):
    root = tk.Tk()
    game = DealOrNoDealGame(root, balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = DealOrNoDealGame(root, 10000.0, "test")
    root.mainloop()