import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time
import math
import threading

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
    """自定义圆形按钮"""
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

class RocketGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("飞天数字")
        self.root.geometry("1000x700+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.balance = float(initial_balance)
        self.username = username
        self.current_bet = 0.0
        self.game_active = False
        self.last_win = 0.0
        self.game_running = False
        self.boom_multiplier = 0.0
        self.current_multiplier = 1.0
        self.target_multiplier = 1000000.0  # 默认不设置自动兑现
        
        self.create_widgets()
        self.update_display()
        
        # 使用after延迟绘制，确保画布尺寸已确定
        self.root.after(100, self.draw_launch_pad)
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 火箭显示区
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="飞天数字", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        self.rocket_canvas = tk.Canvas(left_frame, bg="#0f3460", bd=0, highlightthickness=0)
        self.rocket_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
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
            btn = CircleButton(
                chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda t=text: self.add_chip(t[1:])
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)
        
        # 下注金额
        bet_frame = tk.Frame(right_frame, bg="#16213e")
        bet_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(bet_frame, text="下注金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.bet_var = tk.StringVar()
        self.bet_var.set("$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 自动兑现倍数
        auto_cash_frame = tk.Frame(right_frame, bg="#16213e")
        auto_cash_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(auto_cash_frame, text="自动兑现倍数:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.auto_cash_var = tk.StringVar()
        self.auto_cash_var.set("")
        self.auto_cash_entry = tk.Entry(auto_cash_frame, textvariable=self.auto_cash_var, 
                                  font=("Arial", 14), bg="#2d4059", fg="white")
        self.auto_cash_entry.pack(fill=tk.X, pady=(5, 0))
        tk.Label(auto_cash_frame, text="(留空表示不设置自动兑现)", font=("Arial", 10), 
                bg="#16213e", fg="#bdc3c7").pack(anchor=tk.W)
        
        # 游戏按钮
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        self.start_button = tk.Button(
            button_frame, text="开始游戏", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_game
        )
        self.start_button.pack(pady=5)
        
        self.cash_out_button = tk.Button(
            button_frame, text="兑现", font=("Arial", 12),
            bg="#e74c3c", fg="white", width=12, command=self.cash_out
        )
        self.cash_out_button.pack(pady=5)
        self.cash_out_button.pack_forget()
        
        self.reset_bet_button = tk.Button(
            button_frame, text="重设下注", font=("Arial", 12),
            bg="#3498db", fg="white", width=12, command=self.reset_bet
        )
        self.reset_bet_button.pack(pady=5)
        
        # 游戏信息
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 设置下注金额和自动兑现倍数",
            "2. 点击开始游戏按钮",
            "3. 火箭开始飞行，倍数不断上升",
            "4. 随时点击兑现按钮结束游戏",
            "5. 如果达到自动兑现倍数，自动兑现",
            "6. 如果倍数达到爆炸倍数，游戏结束"
        ]
        
        for rule in rules:
            tk.Label(info_frame, text=rule, font=("Arial", 10), 
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=2)
    
    def draw_launch_pad(self):
        """绘制火箭准备发射的画面"""
        # 确保画布尺寸已确定
        if self.rocket_canvas.winfo_width() < 10 or self.rocket_canvas.winfo_height() < 10:
            self.root.after(100, self.draw_launch_pad)
            return
            
        self.rocket_canvas.delete("all")
        width = self.rocket_canvas.winfo_width()
        height = self.rocket_canvas.winfo_height()
        
        # 绘制星空背景
        for _ in range(100):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(1, 3)
            self.rocket_canvas.create_oval(x, y, x+size, y+size, fill="white", outline="")
        
        # 绘制发射台
        launch_pad_height = height * 0.2
        launch_pad_width = width * 0.6
        launch_pad_x = width // 2 - launch_pad_width // 2
        launch_pad_y = height * 0.8 - launch_pad_height
        
        # 发射台底座
        self.rocket_canvas.create_rectangle(
            launch_pad_x, launch_pad_y + launch_pad_height * 0.7,
            launch_pad_x + launch_pad_width, height,
            fill="#555555", outline="#333333", width=2
        )
        
        # 发射塔结构
        self.rocket_canvas.create_rectangle(
            launch_pad_x + launch_pad_width * 0.3, launch_pad_y,
            launch_pad_x + launch_pad_width * 0.35, launch_pad_y + launch_pad_height * 0.7,
            fill="#777777", outline="#555555", width=2
        )
        self.rocket_canvas.create_rectangle(
            launch_pad_x + launch_pad_width * 0.65, launch_pad_y,
            launch_pad_x + launch_pad_width * 0.7, launch_pad_y + launch_pad_height * 0.7,
            fill="#777777", outline="#555555", width=2
        )
        
        # 火箭
        rocket_width = width * 0.15
        rocket_height = height * 0.3
        rocket_x = width // 2 - rocket_width // 2
        rocket_y = launch_pad_y + launch_pad_height * 0.7 - rocket_height
        
        # 火箭主体
        self.rocket_canvas.create_rectangle(
            rocket_x, rocket_y, 
            rocket_x + rocket_width, rocket_y + rocket_height,
            fill="#cccccc", outline="white", width=2
        )
        
        # 火箭顶部
        self.rocket_canvas.create_polygon(
            rocket_x, rocket_y,
            rocket_x + rocket_width, rocket_y,
            rocket_x + rocket_width // 2, rocket_y - rocket_height * 0.2,
            fill="#ff6600", outline="white", width=2
        )
        
        # 火箭窗口
        self.rocket_canvas.create_oval(
            rocket_x + rocket_width // 2 - rocket_width * 0.15, rocket_y + rocket_height * 0.2,
            rocket_x + rocket_width // 2 + rocket_width * 0.15, rocket_y + rocket_height * 0.4,
            fill="#4cc9f0", outline="white", width=2
        )
        
        # 火箭推进器
        self.rocket_canvas.create_rectangle(
            rocket_x - rocket_width * 0.05, rocket_y + rocket_height,
            rocket_x + rocket_width * 0.05, rocket_y + rocket_height + rocket_height * 0.1,
            fill="#ff0000", outline="white", width=2
        )
        self.rocket_canvas.create_rectangle(
            rocket_x + rocket_width - rocket_width * 0.05, rocket_y + rocket_height,
            rocket_x + rocket_width + rocket_width * 0.05, rocket_y + rocket_height + rocket_height * 0.1,
            fill="#ff0000", outline="white", width=2
        )
        
        # 显示准备发射文本
        self.rocket_canvas.create_text(
            width // 2, height * 0.15, 
            text="火箭准备发射", 
            font=("Arial", 28, "bold"), 
            fill="#ffd369"
        )
        self.rocket_canvas.create_text(
            width // 2, height * 0.25, 
            text="设置下注金额后点击'开始游戏'", 
            font=("Arial", 16), 
            fill="#4cc9f0"
        )
    
    def draw_rocket(self):
        """绘制飞行中的火箭"""
        self.rocket_canvas.delete("all")
        width = self.rocket_canvas.winfo_width()
        height = self.rocket_canvas.winfo_height()
        
        # 绘制星空背景
        for _ in range(100):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(1, 3)
            self.rocket_canvas.create_oval(x, y, x+size, y+size, fill="white", outline="")
        
        # 绘制火箭
        rocket_width = 80
        rocket_height = 150
        rocket_x = width // 2 - rocket_width // 2
        rocket_y = height * 0.7 - rocket_height // 2
        
        # 火箭主体
        self.rocket_canvas.create_rectangle(
            rocket_x, rocket_y, 
            rocket_x + rocket_width, rocket_y + rocket_height,
            fill="#cccccc", outline="white", width=2
        )
        
        # 火箭顶部
        self.rocket_canvas.create_polygon(
            rocket_x, rocket_y,
            rocket_x + rocket_width, rocket_y,
            rocket_x + rocket_width // 2, rocket_y - 30,
            fill="#ff6600", outline="white", width=2
        )
        
        # 火箭窗口
        self.rocket_canvas.create_oval(
            rocket_x + rocket_width // 2 - 15, rocket_y + 30,
            rocket_x + rocket_width // 2 + 15, rocket_y + 60,
            fill="#4cc9f0", outline="white", width=2
        )
        
        # 火箭推进器
        self.rocket_canvas.create_rectangle(
            rocket_x - 10, rocket_y + rocket_height,
            rocket_x + 10, rocket_y + rocket_height + 20,
            fill="#ff0000", outline="white", width=2
        )
        self.rocket_canvas.create_rectangle(
            rocket_x + rocket_width - 10, rocket_y + rocket_height,
            rocket_x + rocket_width + 10, rocket_y + rocket_height + 20,
            fill="#ff0000", outline="white", width=2
        )
        
        # 火焰
        self.rocket_canvas.create_polygon(
            rocket_x - 10, rocket_y + rocket_height + 20,
            rocket_x + 10, rocket_y + rocket_height + 20,
            rocket_x, rocket_y + rocket_height + 60,
            fill="#ff9900", outline=""
        )
        self.rocket_canvas.create_polygon(
            rocket_x + rocket_width - 10, rocket_y + rocket_height + 20,
            rocket_x + rocket_width + 10, rocket_y + rocket_height + 20,
            rocket_x + rocket_width, rocket_y + rocket_height + 60,
            fill="#ff9900", outline=""
        )
        
        # 显示倍数
        self.rocket_canvas.create_text(
            width // 2, 50, 
            text=f"当前倍数: {self.current_multiplier:.2f}x", 
            font=("Arial", 24, "bold"), fill="#ffd369"
        )
        
        # 显示目标倍数
        if self.target_multiplier < 1000000:
            self.rocket_canvas.create_text(
                width // 2, 100, 
                text=f"目标倍数: {self.target_multiplier:.2f}x", 
                font=("Arial", 18), fill="#4cc9f0"
            )
    
    def add_chip(self, amount):
        try:
            amount_val = float(amount)
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")
        except ValueError:
            pass
    
    def reset_bet(self):
        self.current_bet = 0.0
        self.bet_var.set("$0.00")
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        
    def generate_probability_table(self, max_multiplier, C=100, k=1.5):
        probability_table = []
        multiplier = 1.01
        while multiplier <= max_multiplier:
            prob = C / (multiplier ** k)
            probability_table.append((round(multiplier, 2), prob))
            multiplier += 0.01 if multiplier < 2 else 0.1 if multiplier < 10 else 1
        total_prob = sum(prob for _, prob in probability_table)
        probability_table = [(m, (p / total_prob) * 100) for m, p in probability_table]
        return probability_table
    
    def generate_boom_multiplier(self, probability_table):
        random_number = random.uniform(0, 100)
        cumulative_probability = 0
        for multiplier, prob in probability_table:
            cumulative_probability += prob
            if random_number <= cumulative_probability:
                return multiplier
        return probability_table[-1][0]
    
    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        
        # 获取自动兑现倍数
        auto_cash = self.auto_cash_var.get()
        if auto_cash:
            try:
                self.target_multiplier = float(auto_cash)
                if self.target_multiplier < 1.01:
                    messagebox.showwarning("错误", "自动兑现倍数必须大于1.01")
                    return
            except ValueError:
                messagebox.showwarning("错误", "请输入有效的自动兑现倍数")
                return
        else:
            self.target_multiplier = 1000000.0  # 很大的数字表示不自动兑现
        
        # 禁用自动兑现输入框
        self.auto_cash_entry.config(state=tk.DISABLED)
        
        # 扣除下注金额
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        update_balance_in_json(self.username, self.balance)
        
        # 生成爆炸倍数
        probability_table = self.generate_probability_table(1000000)
        self.boom_multiplier = self.generate_boom_multiplier(probability_table)
        
        # 重置游戏状态
        self.current_multiplier = 1.0
        self.game_active = True
        self.game_running = True
        
        # 更新UI
        self.start_button.config(state=tk.DISABLED)
        self.reset_bet_button.pack_forget()
        self.cash_out_button.pack(pady=5)
        
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 开始游戏线程
        threading.Thread(target=self.run_game, daemon=True).start()
    
    def run_game(self):
        """运行游戏的主循环"""
        # 倒计时
        self.countdown()
        
        # 初始设置
        time_to_increase = 0.4
        self.current_multiplier = 0.95
        
        # 游戏主循环
        while self.game_running and self.current_multiplier < self.boom_multiplier:
            time.sleep(time_to_increase)
            
            # 增加倍数
            self.current_multiplier += 0.01
            
            # 更新UI
            self.root.after(0, self.update_rocket_display)
            
            # 根据当前倍数调整时间间隔
            if time_to_increase > 0.15:
                time_to_increase *= 0.999
            
            # 检查是否达到自动兑现倍数
            if self.current_multiplier >= self.target_multiplier:
                self.root.after(0, self.auto_cash_out)
                break
            
            # 检查是否达到爆炸倍数
            if self.current_multiplier >= self.boom_multiplier:
                self.root.after(0, self.explode)
                break
        
        # 如果玩家手动退出
        if not self.game_running and self.game_active:
            self.root.after(0, self.manual_cash_out)
    
    def countdown(self):
        """显示倒计时"""
        for i in range(3, 0, -1):
            self.rocket_canvas.delete("all")
            self.rocket_canvas.create_text(
                self.rocket_canvas.winfo_width() // 2,
                self.rocket_canvas.winfo_height() // 2,
                text=f"倒计时: {i}", 
                font=("Arial", 36, "bold"), 
                fill="#ffd369"
            )
            self.root.update()
            time.sleep(1)
        
        self.rocket_canvas.delete("all")
        self.rocket_canvas.create_text(
            self.rocket_canvas.winfo_width() // 2,
            self.rocket_canvas.winfo_height() // 2,
            text="开始!", 
            font=("Arial", 36, "bold"), 
            fill="#27ae60"
        )
        self.root.update()
        time.sleep(1)
    
    def update_rocket_display(self):
        """更新火箭显示"""
        self.draw_rocket()
        
        # 添加火箭尾迹
        width = self.rocket_canvas.winfo_width()
        height = self.rocket_canvas.winfo_height()
        for i in range(5):
            y_pos = height * 0.7 + 60 + i * 10
            size = random.randint(5, 15)
            x_offset = random.randint(-10, 10)
            self.rocket_canvas.create_oval(
                width // 2 - size + x_offset, y_pos,
                width // 2 + size + x_offset, y_pos + size * 2,
                fill="#ff9900", outline=""
            )
    
    def cash_out(self):
        """手动兑现"""
        if self.game_active:
            self.game_running = False
    
    def manual_cash_out(self):
        """处理手动兑现"""
        win_amount = self.bet_amount * self.current_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        
        update_balance_in_json(self.username, self.balance)
        
        # 显示结果
        self.show_result(
            f"手动兑现成功!\n兑现倍数: {self.current_multiplier:.2f}x\n"
            f"最高倍数: {self.boom_multiplier:.2f}x\n"
            f"获得金额: ${win_amount:.2f}"
        )
        self.end_game()
    
    def auto_cash_out(self):
        """自动兑现"""
        win_amount = self.bet_amount * self.target_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        
        update_balance_in_json(self.username, self.balance)
        
        # 显示结果
        self.show_result(
            f"自动兑现成功!\n目标倍数: {self.target_multiplier:.2f}x\n"
            f"最高倍数: {self.boom_multiplier:.2f}x\n"
            f"获得金额: ${win_amount:.2f}"
        )
        self.end_game()
    
    def explode(self):
        """爆炸处理"""
        self.game_active = False
        self.last_win = 0.0
        
        # 显示爆炸效果
        width = self.rocket_canvas.winfo_width()
        height = self.rocket_canvas.winfo_height()
        
        # 绘制爆炸
        for i in range(20):
            angle = random.uniform(0, 2 * math.pi)
            distance = random.randint(20, 100)
            x = width // 2 + math.cos(angle) * distance
            y = height * 0.7 + math.sin(angle) * distance
            size = random.randint(5, 15)
            self.rocket_canvas.create_oval(
                x - size, y - size,
                x + size, y + size,
                fill=random.choice(["#ff0000", "#ff9900", "#ffff00"]), outline=""
            )
        
        # 显示爆炸文本
        self.rocket_canvas.create_text(
            width // 2, height // 2,
            text=f"💥 爆炸! 💥\n最高倍数: {self.boom_multiplier:.2f}x", 
            font=("Arial", 24, "bold"), 
            fill="#e94560"
        )
        self.root.update()
        
        time.sleep(2)
        self.end_game()
    
    def show_result(self, message):
        """显示结果消息"""
        width = self.rocket_canvas.winfo_width()
        height = self.rocket_canvas.winfo_height()
        
        self.rocket_canvas.delete("all")
        self.rocket_canvas.create_text(
            width // 2, height // 2,
            text=message, 
            font=("Arial", 20), 
            fill="#27ae60",
            justify=tk.CENTER
        )
        self.root.update()
        time.sleep(3)
    
    def end_game(self):
        """结束游戏，重置UI"""
        self.start_button.config(state=tk.NORMAL)
        self.cash_out_button.pack_forget()
        self.reset_bet_button.pack(pady=5)
        
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 重新启用自动兑现输入框
        self.auto_cash_entry.config(state=tk.NORMAL)
        
        self.update_display()
        
        # 返回准备发射画面
        self.root.after(100, self.draw_launch_pad)
    
    def on_closing(self):
        """窗口关闭事件处理"""
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    """供small_games.py调用的主函数"""
    root = tk.Tk()
    game = RocketGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = RocketGame(root, 1000.0, "test_user")
    root.mainloop()