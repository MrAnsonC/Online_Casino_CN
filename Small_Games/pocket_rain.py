import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import math

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

class CircleButton(tk.Canvas):
    """自定义圆形按钮（筹码按钮）"""
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
                        font=("Arial", 18, "bold"))
        self.bind("<Button-1>", self.on_click)

    def on_click(self, event):
        if self.command:
            self.command()

class RedPacketRainGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("红包雨游戏")
        self.root.geometry("1000x700+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_per_draw = 0.0        # 单次下注金额（每个红包消耗的金额）
        self.difficulty = "1"          # 1简单 2中等 3地狱
        self.game_active = False       # 游戏是否进行中（红包雨活动状态）
        self.stop_generate = False     # 停止生成红包标志
        self.animation_running = False # 动画循环是否运行
        self.redpackets = []           # 存储红包数据 {id, multiplier, opened, y, can_click, text_id}
        self.generate_after_id = None
        self.move_after_id = None

        # 本轮统计
        self.round_total_win = 0.0
        self.round_open_count = 0

        # 难度对应的返奖率（期望倍数）和倍数范围
        self.difficulty_params = {
            "1": {"rtp": 0.95, "min_mul": 0.7, "max_mul": 5.0},
            "2": {"rtp": 0.93, "min_mul": 0.5, "max_mul": 10.0},
            "3": {"rtp": 0.91, "min_mul": 0.3, "max_mul": 15.0}
        }

        # 预计算每个难度的幂指数k，使得连续分布的期望等于rtp
        # 分布：mul = min_mul + (max_mul - min_mul) * (u ** k), u~U(0,1)
        # 期望 = min_mul + (max_mul - min_mul)/(k+1)
        # 解得 k = (max_mul - min_mul)/(期望 - min_mul) - 1
        self.difficulty_k = {}
        for diff, params in self.difficulty_params.items():
            min_mul = params["min_mul"]
            max_mul = params["max_mul"]
            rtp = params["rtp"]
            if rtp <= min_mul:
                k = 0.0  # 全为最小值
            else:
                k = (max_mul - min_mul) / (rtp - min_mul) - 1
            self.difficulty_k[diff] = max(k, 0.01)  # 确保正数

        # 下落速度 (px/帧)
        self.fall_speed = 3

        # 创建UI
        self.create_widgets()
        self.update_display()

    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 左侧 - 红包雨画布
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Label(left_frame, text="红包雨", font=("Arial", 20, "bold"),
                bg="#16213e", fg="#e94560").pack(pady=10)

        self.canvas = tk.Canvas(left_frame, bg="#2d1b2e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        # 右侧 - 控制面板
        right_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        # 余额显示
        balance_frame = tk.Frame(right_frame, bg="#16213e")
        balance_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(balance_frame, text="余额:", font=("Arial", 14),
                bg="#16213e", fg="#f1f1f1").pack(side=tk.LEFT)
        self.balance_var = tk.StringVar()
        self.balance_var.set(f"${self.balance:.2f}")
        tk.Label(balance_frame, textvariable=self.balance_var, font=("Arial", 14, "bold"),
                bg="#16213e", fg="#ffd369").pack(side=tk.LEFT, padx=(5, 0))

        # 筹码按钮
        chips_frame = tk.Frame(right_frame, bg="#16213e")
        chips_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        chips = [
            ("$5", '#ff0000', 'white'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black')
        ]
        self.chip_buttons = []
        for text, bg_color, fg_color in chips:
            btn = CircleButton(chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                               command=lambda t=text: self.add_chip(t))
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)

        # 难度选择
        difficulty_frame = tk.Frame(right_frame, bg="#16213e")
        difficulty_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(difficulty_frame, text="难度:", font=("Arial", 12),
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        self.difficulty_var = tk.StringVar()
        self.difficulty_var.set("1")
        difficulties = [("简单", "1"), ("中等", "2"), ("地狱", "3")]
        self.difficulty_buttons = []
        for text, value in difficulties:
            btn = tk.Button(difficulty_frame, text=text, font=("Arial", 10),
                            bg="#4e9de0" if value == "1" else "#2d4059", fg="white",
                            width=6, height=1, relief=tk.RAISED,
                            command=lambda v=value: self.set_difficulty(v))
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self.difficulty_buttons.append(btn)

        # 游戏控制按钮
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        self.start_button = tk.Button(button_frame, text="开始游戏", font=("Arial", 12, "bold"),
                                      bg="#27ae60", fg="white", width=10, command=self.start_game)
        self.start_button.pack(side=tk.LEFT, padx=2)

        self.stop_button = tk.Button(button_frame, text="停止红包雨", font=("Arial", 12, "bold"),
                                     bg="#e74c3c", fg="white", width=10, command=self.stop_game, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=2)

        self.reset_bet_button = tk.Button(button_frame, text="重设下注", font=("Arial", 12),
                                          bg="#3498db", fg="white", width=10, command=self.reset_bet)
        self.reset_bet_button.pack(side=tk.LEFT, padx=2)

        # 本轮统计信息
        stats_frame = tk.Frame(right_frame, bg="#16213e")
        stats_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(stats_frame, text="本轮统计:", font=("Arial", 12, "bold"),
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        self.open_count_var = tk.StringVar(value="打开红包: 0")
        tk.Label(stats_frame, textvariable=self.open_count_var, font=("Arial", 11),
                bg="#16213e", fg="#bdc3c7").pack(anchor=tk.W)
        self.round_win_var = tk.StringVar(value="本轮赢得: $0.00")
        tk.Label(stats_frame, textvariable=self.round_win_var, font=("Arial", 11),
                bg="#16213e", fg="#ffd369").pack(anchor=tk.W)

        # 下注金额显示
        bet_frame = tk.Frame(right_frame, bg="#16213e")
        bet_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(bet_frame, text="单次下注金额:", font=("Arial", 12),
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        self.bet_var = tk.StringVar(value="$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"),
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))

        # 最后奖励显示
        self.last_win_var = tk.StringVar(value="$0.00")
        tk.Label(right_frame, text="最后红包奖励:", font=("Arial", 12),
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, padx=10)
        tk.Label(right_frame, textvariable=self.last_win_var, font=("Arial", 18, "bold"),
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, padx=10, pady=(0, 10))

        # 状态信息
        self.status_var = tk.StringVar(value="请设置下注金额并点击[开始游戏]")
        status_label = tk.Label(right_frame, textvariable=self.status_var,
                               font=("Arial", 10), bg="#16213e", fg="#ffd369", wraplength=250)
        status_label.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 游戏说明
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"),
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        rules = [
            "1. 设置单次下注金额和难度",
            "2. 点击[开始游戏]开始红包雨",
            "3. 点击下落的红包打开它",
            "4. 每个红包消耗一次下注金额",
            "5. 打开红包获得随机倍数奖励",
            "6. 红包落到红线以下不可再点",
            "7. 点击[停止红包雨]结束本轮"
        ]
        for rule in rules:
            tk.Label(info_frame, text=rule, font=("Arial", 9),
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=1)

    def add_chip(self, amount_text):
        """增加单次下注金额"""
        if self.game_active:
            messagebox.showinfo("提示", "请先停止当前游戏再调整下注金额")
            return
        try:
            if amount_text == "$1K":
                amount_val = 1000.0
            else:
                amount_val = float(amount_text[1:])
            new_bet = self.bet_per_draw + amount_val
            if new_bet <= self.balance:
                self.bet_per_draw = new_bet
                self.bet_var.set(f"${self.bet_per_draw:.2f}")
                self.update_status()
            else:
                messagebox.showwarning("余额不足", "下注金额不能超过当前余额")
        except ValueError:
            pass

    def reset_bet(self):
        if self.game_active:
            messagebox.showinfo("提示", "请先停止当前游戏")
            return
        self.bet_per_draw = 0.0
        self.bet_var.set("$0.00")
        self.update_status()

    def set_difficulty(self, difficulty):
        if self.game_active:
            messagebox.showinfo("提示", "请先停止当前游戏再更改难度")
            return
        self.difficulty = difficulty
        for i, (text, value) in enumerate([("简单", "1"), ("中等", "2"), ("地狱", "3")]):
            if value == difficulty:
                self.difficulty_buttons[i].configure(bg="#4e9de0")
            else:
                self.difficulty_buttons[i].configure(bg="#2d4059")
        self.update_status()

    def update_status(self):
        if self.game_active:
            self.status_var.set("红包雨中... 点击红包打开")
        elif self.bet_per_draw <= 0:
            self.status_var.set("请设置下注金额")
        else:
            diff_name = {"1":"简单","2":"中等","3":"地狱"}[self.difficulty]
            self.status_var.set(f"已设置: 下注 ${self.bet_per_draw:.2f} | {diff_name}模式 | 点击开始")

    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.round_total_win:.2f}")
        self.open_count_var.set(f"打开红包: {self.round_open_count}")
        self.round_win_var.set(f"本轮赢得: ${self.round_total_win:.2f}")

    def on_canvas_click(self, event):
        """处理画布点击，找出点击的红包"""
        if not self.game_active:
            return
        item = self.canvas.find_closest(event.x, event.y)
        if not item:
            return
        item_id = item[0]
        for rp in self.redpackets:
            if rp['id'] == item_id or rp['text_id'] == item_id:
                self.open_redpacket(rp)
                break

    def generate_multiplier(self):
        """根据当前难度生成符合返奖率期望的随机倍数"""
        params = self.difficulty_params[self.difficulty]
        min_mul = params["min_mul"]
        max_mul = params["max_mul"]
        k = self.difficulty_k[self.difficulty]
        u = random.random()
        multiplier = min_mul + (max_mul - min_mul) * (u ** k)
        return round(multiplier, 1)

    def open_redpacket(self, rp):
        """打开一个红包"""
        if not self.game_active:
            return
        if rp['opened']:
            return
        if not rp['can_click']:
            self.show_multiplier_on_redpacket(rp)
            return
        if self.balance < self.bet_per_draw:
            messagebox.showwarning("余额不足", "余额不足以继续打开红包，游戏将停止")
            self.stop_game()
            return

        # 扣除下注金额
        self.balance -= self.bet_per_draw
        win_amount = self.bet_per_draw * rp['multiplier']
        self.balance += win_amount
        self.round_total_win += win_amount
        self.round_open_count += 1

        self.update_display()
        update_balance_in_json(self.username, self.balance)

        rp['opened'] = True
        rp['can_click'] = False
        self.canvas.itemconfig(rp['text_id'], text=f"{rp['multiplier']:.1f}x", fill="#ffd700")
        self.canvas.itemconfig(rp['id'], fill="#8b0000")
        self.status_var.set(f"打开红包获得 {win_amount:.2f} (倍数 {rp['multiplier']:.2f})")

    def show_multiplier_on_redpacket(self, rp):
        """强制显示红包倍数（不可点击时）"""
        if rp['opened']:
            return
        rp['opened'] = True
        rp['can_click'] = False
        self.canvas.itemconfig(rp['text_id'], text=f"{rp['multiplier']:.1f}x", fill="#ffd700")
        self.canvas.itemconfig(rp['id'], fill="#555555")

    def generate_redpacket(self):
        """生成一个红包（在画布顶部随机x位置）"""
        if not self.game_active:
            return
        if self.stop_generate:
            return
        if not self.canvas.winfo_exists():
            return

        width = self.canvas.winfo_width()
        if width < 100:
            self.generate_after_id = self.root.after(500, self.generate_redpacket)
            return

        r_width = 60
        r_height = 80
        x = random.randint(20, width - r_width - 20)
        y = 5

        multiplier = self.generate_multiplier()

        rp_id = self.canvas.create_rectangle(x, y, x + r_width, y + r_height,
                                              fill="#ff4500", outline="#ffcc00", width=2, tags="redpacket")
        text_id = self.canvas.create_text(x + r_width//2, y + r_height//2,
                                          text="?", font=("Arial", 16, "bold"),
                                          fill="white", tags="redpacket")
        rp_data = {
            'id': rp_id,
            'text_id': text_id,
            'multiplier': multiplier,
            'opened': False,
            'y': y,
            'height': r_height,
            'can_click': True,
            'x': x,
            'width': r_width
        }
        self.redpackets.append(rp_data)

        # 生成间隔 0.45~1.2 秒
        delay = random.randint(450, 1200)
        self.generate_after_id = self.root.after(delay, self.generate_redpacket)

    def move_redpackets(self):
        """移动所有红包下落，每帧移动 self.fall_speed 像素"""
        if not self.game_active:
            return
        if not self.canvas.winfo_exists():
            return

        canvas_height = self.canvas.winfo_height()
        bottom_limit = canvas_height - 20   # 底部禁区起始线
        to_remove = []

        for rp in self.redpackets:
            # 计算新位置（实际移动距离 = self.fall_speed）
            new_y = rp['y'] + self.fall_speed

            # 禁区判断：红包底部触碰到禁区线，且未被打开且仍可点击
            if (new_y + rp['height'] >= bottom_limit) and rp['can_click'] and not rp['opened']:
                rp['can_click'] = False
                self.show_multiplier_on_redpacket(rp)

            # 执行画面移动
            self.canvas.move(rp['id'], 0, self.fall_speed)
            self.canvas.move(rp['text_id'], 0, self.fall_speed)
            rp['y'] = new_y   # 同步记录坐标

            # 超出画布底部则标记移除
            if rp['y'] > canvas_height:
                to_remove.append(rp)

        # 移除超出画布的红包
        for rp in to_remove:
            self.canvas.delete(rp['id'])
            self.canvas.delete(rp['text_id'])
            self.redpackets.remove(rp)

        # 继续循环（每 10ms 移动一次）
        self.move_after_id = self.root.after(10, self.move_redpackets)

    def start_game(self):
        """开始红包雨游戏"""
        if self.game_active:
            messagebox.showinfo("提示", "游戏正在进行中")
            return
        if self.bet_per_draw <= 0:
            messagebox.showwarning("错误", "请先设置单次下注金额")
            return
        if self.balance < self.bet_per_draw:
            messagebox.showwarning("余额不足", "余额不足以进行单次下注")
            return

        self.canvas.delete("all")
        self.redpackets.clear()
        self.round_total_win = 0.0
        self.round_open_count = 0
        self.update_display()

        self.game_active = True
        self.stop_generate = False

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)

        self.generate_redpacket()
        self.move_redpackets()
        self.update_status()

    def stop_game(self):
        """停止红包雨，显示所有剩余红包的倍数"""
        if not self.game_active:
            return

        self.game_active = False
        self.stop_generate = True
        if self.generate_after_id:
            self.root.after_cancel(self.generate_after_id)
            self.generate_after_id = None
        if self.move_after_id:
            self.root.after_cancel(self.move_after_id)
            self.move_after_id = None

        for rp in self.redpackets:
            if not rp['opened']:
                self.show_multiplier_on_redpacket(rp)

        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.NORMAL)
        self.reset_bet_button.config(state=tk.NORMAL)

        self.status_var.set("红包雨已停止")
        update_balance_in_json(self.username, self.balance)

    def on_closing(self):
        """窗口关闭时保存余额"""
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    """供外部调用的入口"""
    root = tk.Tk()
    game = RedPacketRainGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = RedPacketRainGame(root, 1000.0, "test_user")
    root.mainloop()