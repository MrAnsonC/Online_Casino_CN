import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time

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

class GuessNumberGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("猜数字游戏")
        self.root.geometry("1050x700+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.balance = float(initial_balance)
        self.username = username
        self.current_bet = 0.0
        self.target_number = 0
        self.min_guess = 1
        self.max_guess = 100
        self.attempt = 0
        self.game_active = False
        self.last_win = 0.0
        self.odds = [196.00, 48.10, 14.24, 3.80, 1.85]
        self.chinese_numbers = ['一', '二', '三', '四', '五']
        
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 游戏区域
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="猜数字游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        # 游戏显示区域
        self.game_canvas = tk.Canvas(left_frame, bg="#0f3460", bd=0, highlightthickness=0)
        self.game_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
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
        
        # 下注金额显示
        bet_frame = tk.Frame(right_frame, bg="#16213e")
        bet_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(bet_frame, text="下注金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.bet_var = tk.StringVar()
        self.bet_var.set("$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 上局获胜金额
        win_frame = tk.Frame(right_frame, bg="#16213e")
        win_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(win_frame, text="上局获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")
        tk.Label(win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 游戏按钮
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        self.start_button = tk.Button(
            button_frame, text="开始游戏", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_game
        )
        self.start_button.pack(pady=5)
        
        self.reset_bet_button = tk.Button(
            button_frame, text="重设下注金额", font=("Arial", 12),
            bg="#3498db", fg="white", width=12, command=self.reset_bet
        )
        self.reset_bet_button.pack(pady=5)
        
        # 游戏信息
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 输入下注金额并开始游戏",
            "2. 系统随机生成1-100之间的数字",
            "3. 你有5次机会猜测这个数字",
            "4. 每次猜测后系统会提示范围",
            f"5. 赔率: 第1次猜中:{self.odds[0]:.2f}X, 第2次:{self.odds[1]:.2f}X",
            f"    第3次:{self.odds[2]:.2f}X, 第4次:{self.odds[3]:.2f}X, 第5次:{self.odds[4]:.2f}X"
        ]
        
        for rule in rules:
            tk.Label(info_frame, text=rule, font=("Arial", 10), 
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=2)
    
    def add_chip(self, amount):
        try:
            if amount == "1K":
                amount_val = 1000.0
            else:
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
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.draw_game_screen()
    
    def draw_game_screen(self):
        self.game_canvas.delete("all")
        
        if not self.game_active:
            # 显示欢迎信息
            self.game_canvas.create_text(300, 250, text="猜数字游戏", 
                                        font=("Arial", 28, "bold"), fill="#e94560")
            self.game_canvas.create_text(300, 300, text="选择下注金额后点击开始游戏", 
                                        font=("Arial", 14), fill="#bdc3c7")
            return
        
        # 绘制游戏界面
        self.game_canvas.create_text(300, 50, text=f"第{self.chinese_numbers[self.attempt]}次猜测", 
                                    font=("Arial", 40, "bold"), fill="#ffd369")
        
        # 显示当前赔率
        self.game_canvas.create_text(300, 100, text=f"当前赔率: {self.odds[self.attempt]:.2f}X", 
                                    font=("Arial", 30), fill="#4cc9f0")
        
        # 显示范围
        self.game_canvas.create_text(300, 170, text=f"范围: {self.min_guess} - {self.max_guess}", 
                                    font=("Arial", 40), fill="#ffffff")
        
        # 输入框
        self.game_canvas.create_text(300, 250, text="输入你的猜测:", 
                                    font=("Arial", 30), fill="#f1f1f1")
        
        # 创建输入框
        if not hasattr(self, 'guess_entry'):
            self.guess_entry = tk.Entry(self.game_canvas, font=("Arial", 40), width=10)
            self.guess_entry.bind("<Return>", lambda event: self.make_guess())
        
        # 放置输入框（位置在输入提示下方）
        self.game_canvas.create_window(300, 300, window=self.guess_entry)
        
        # 提交按钮
        if not hasattr(self, 'submit_button'):
            self.submit_button = tk.Button(self.game_canvas, text="猜!", 
                                        font=("Arial", 30, "bold"),
                                        bg="#27ae60", fg="white",
                                        command=self.make_guess)
        # 放置提交按钮（在输入框下方）
        self.game_canvas.create_window(300, 380, window=self.submit_button)
    
    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先设置下注金额")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("错误", "余额不足")
            return
        
        # 扣除下注金额
        self.balance -= self.current_bet
        update_balance_in_json(self.username, self.balance)
        
        # 初始化游戏状态 - 确保范围是1-100
        self.target_number = random.randint(1, 100)
        self.min_guess = 1
        self.max_guess = 100
        self.attempt = 0
        self.game_active = True
        self.history = []
        
        # 更新UI状态
        self.start_button.config(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 聚焦输入框
        if hasattr(self, 'guess_entry'):
            self.guess_entry.delete(0, tk.END)
            self.guess_entry.focus_set()
        
        self.update_display()
    
    def make_guess(self):
        if not self.game_active:
            return
        
        # 获取用户输入
        try:
            guess = int(self.guess_entry.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            return
        
        # 检查范围
        if guess < self.min_guess or guess > self.max_guess:
            messagebox.showerror("错误", f"请输入 {self.min_guess}-{self.max_guess} 之间的数字")
            return
        
        # 记录历史
        self.history.append(guess)
        
        # 检查猜测
        if guess == self.target_number:
            self.win_game()
            return
        elif guess < self.target_number:
            self.min_guess = guess + 1
        else:
            self.max_guess = guess - 1
        
        # 增加尝试次数
        self.attempt += 1
        
        # 检查是否还有尝试次数
        if self.attempt >= 5:
            self.lose_game()
            return
        
        # 清除输入框
        self.guess_entry.delete(0, tk.END)
        self.guess_entry.focus_set()
        self.update_display()
    
    def win_game(self):
        # 计算赢得的金额
        win_amount = self.current_bet * self.odds[self.attempt]
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 显示胜利信息
        self.draw_game_screen()
        self.game_canvas.create_text(300, 400, 
                                   text=f"恭喜！你猜中了数字 {self.target_number}！",
                                   font=("Arial", 16, "bold"), fill="#27ae60")
        self.game_canvas.create_text(300, 450, 
                                   text=f"赢得金额: ${win_amount:.2f}",
                                   font=("Arial", 14), fill="#ffd369")
        
        # 重置UI状态
        self.reset_ui_state()
        
        # 显示胜利弹窗
        messagebox.showinfo("胜利", f"恭喜！你猜中了数字 {self.target_number}！\n赢得金额: ${win_amount:.2f}")
    
    def lose_game(self):
        self.last_win = 0.0
        self.game_active = False
        
        # 显示失败信息
        self.draw_game_screen()
        self.game_canvas.create_text(300, 400, 
                                   text=f"很遗憾，游戏结束！",
                                   font=("Arial", 16, "bold"), fill="#e74c3c")
        self.game_canvas.create_text(300, 450, 
                                   text=f"正确答案是: {self.target_number}",
                                   font=("Arial", 14), fill="#f1f1f1")
        
        # 重置UI状态
        self.reset_ui_state()
        
        # 显示失败弹窗
        messagebox.showinfo("游戏结束", f"很遗憾，你没有猜中数字！\n正确答案是: {self.target_number}")
    
    def reset_ui_state(self):
        self.start_button.config(state=tk.NORMAL)
        self.reset_bet_button.config(state=tk.NORMAL)
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
    
    def on_closing(self):
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    root = tk.Tk()
    game = GuessNumberGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = GuessNumberGame(root, 1000.0, "test_user")
    root.mainloop()