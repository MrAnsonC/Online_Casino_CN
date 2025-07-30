import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time

# 获取数据文件的路径
def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

# 保存用户数据
def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# 读取用户数据
def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 更新余额到JSON文件
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
        
        # 绘制圆形按钮
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))
        
        # 绑定点击事件
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if self.command:
            self.command()

class RPSGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("剪刀石头布")
        self.root.geometry("1000x675+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.current_bet = 0.0
        self.last_win = 0.0
        self.user_choice = None
        self.computer_choice = None
        self.game_active = False
        self.chip_buttons = []
        self.animation_running = False
        self.animation_start_time = 0
        self.animation_duration = 0
        self.final_result = None
        
        # 选择映射
        self.choice_map = {
            "✊": "石头",
            "✌": "剪刀",
            "✋": "布"
        }
        
        # 创建UI
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 游戏区域
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="剪刀石头布", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        # 游戏显示区域
        self.game_canvas = tk.Canvas(left_frame, bg="#0f3460", height=400, bd=0, highlightthickness=0)
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
            ("$5", '#ff0000', 'white'),    # 红色背景，白色文字
            ("$25", '#00ff00', 'black'),    # 绿色背景，黑色文字
            ("$100", '#000000', 'white'),   # 黑色背景，白色文字
            ("$500", "#FF7DDA", 'black'),   # 粉色背景，黑色文字
            ("$1K", '#ffffff', 'black')     # 白色背景，黑色文字
        ]
        
        self.chip_buttons = []  # 存储所有筹码按钮
        for text, bg_color, fg_color in chips:
            btn = CircleButton(
                chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda t=text: self.add_chip(t[1:])  # 去掉$符号
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
        
        self.play_button = tk.Button(
            button_frame, text="开始游戏", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.play_game,
            state=tk.DISABLED  # 初始禁用
        )
        self.play_button.pack(pady=5)
        
        self.reset_bet_button = tk.Button(
            button_frame, text="重设下注金额", font=("Arial", 12),
            bg="#3498db", fg="white", width=12, command=self.reset_bet
        )
        self.reset_bet_button.pack(pady=5)
        
        # 游戏规则
        rules_frame = tk.Frame(right_frame, bg="#16213e")
        rules_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(rules_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 选择下注金额",
            "2. 点击'开始游戏'按钮",
            "3. 选择剪刀、石头或布",
            "4. 赢: 2.00倍下注",
            "5. 平局: 0.99倍下注",
            "6. 输: 无奖励"
        ]
        
        for rule in rules:
            tk.Label(rules_frame, text=rule, font=("Arial", 10), 
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
    
    def set_choice(self, choice):
        self.user_choice = choice
        self.play_button.config(state=tk.NORMAL)
        self.update_display()
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.draw_game_area()
    
    def draw_game_area(self):
        self.game_canvas.delete("all")
        
        # 绘制用户选择区域标题
        self.game_canvas.create_text(100, 80, text="你的选择:", 
                                   font=("Arial", 16), fill="#f1f1f1")
        
        # 绘制电脑选择区域标题
        self.game_canvas.create_text(400, 80, text="电脑选择:", 
                                   font=("Arial", 16), fill="#f1f1f1")
        
        # 绘制用户选择图案
        if self.user_choice:
            # 图案
            self.game_canvas.create_text(100, 150, text=self.user_choice, 
                                       font=("Arial", 40), fill="#3498db")
            # 图案文字
            self.game_canvas.create_text(100, 200, text=self.choice_map[self.user_choice], 
                                       font=("Arial", 16, "bold"), fill="#3498db")
        else:
            self.game_canvas.create_text(100, 150, text="?", 
                                       font=("Arial", 40, "bold"), fill="#bdc3c7")
            self.game_canvas.create_text(100, 200, text="未选择", 
                                       font=("Arial", 16), fill="#bdc3c7")
        
        # 绘制电脑选择图案
        if self.computer_choice:
            # 图案
            self.game_canvas.create_text(400, 150, text=self.computer_choice, 
                                       font=("Arial", 40), fill="#e74c3c")
            # 图案文字
            self.game_canvas.create_text(400, 200, text=self.choice_map[self.computer_choice], 
                                       font=("Arial", 16, "bold"), fill="#e74c3c")
        else:
            self.game_canvas.create_text(400, 150, text="?", 
                                       font=("Arial", 40, "bold"), fill="#bdc3c7")
            self.game_canvas.create_text(400, 200, text="等待中", 
                                       font=("Arial", 16), fill="#bdc3c7")
        
        # 绘制结果区域 - 只在结算时显示
        if self.final_result:
            self.game_canvas.create_text(250, 280, text=self.final_result, 
                                       font=("Arial", 20, "bold"), fill="#ffd369")
            
            # 只在赢的时候显示赢得的金额
            if "赢了" in self.final_result:
                win_amount = self.current_bet * 2.00
                self.game_canvas.create_text(250, 320, text=f"赢得 ${win_amount:.2f}", 
                                           font=("Arial", 18), fill="#27ae60")
        
        # 在结果文本下方添加选择按钮
        self.add_choice_buttons()
    
    def add_choice_buttons(self):
        """在画布下方添加选择按钮"""
        # 创建选择按钮框架
        choices_frame = tk.Frame(self.game_canvas, bg="#0f3460")
        
        # 在画布底部添加按钮框架
        self.game_canvas.create_window(250, 400, window=choices_frame)
        
        # 创建选择按钮
        rock_btn = tk.Button(
            choices_frame, text="✊ 石头", font=("Arial", 14), 
            bg="#3498db", fg="white", width=8, height=2,
            command=lambda: self.set_choice("✊")
        )
        rock_btn.pack(side=tk.LEFT, padx=5)
        
        paper_btn = tk.Button(
            choices_frame, text="✋ 布", font=("Arial", 14), 
            bg="#2ecc71", fg="white", width=8, height=2,
            command=lambda: self.set_choice("✋")
        )
        paper_btn.pack(side=tk.LEFT, padx=5)
        
        scissors_btn = tk.Button(
            choices_frame, text="✌ 剪刀", font=("Arial", 14), 
            bg="#e74c3c", fg="white", width=8, height=2,
            command=lambda: self.set_choice("✌")
        )
        scissors_btn.pack(side=tk.LEFT, padx=5)
    
    def determine_winner(self, user_choice, computer_choice):
        if user_choice == computer_choice:
            return "和局"
        elif (user_choice == '✊' and computer_choice == '✌') or \
             (user_choice == '✌' and computer_choice == '✋') or \
             (user_choice == '✋' and computer_choice == '✊'):
            return "你赢了！ 赔率是2.00X!"
        else:
            return "你输了，下局加油！"
    
    def play_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        
        if self.user_choice is None:
            messagebox.showwarning("错误", "请选择剪刀、石头或布")
            return
        
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        
        # 禁用游戏按钮
        self.play_button.config(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 扣除下注金额
        self.balance -= self.current_bet
        update_balance_in_json(self.username, self.balance)
        
        # 设置随机动画时间 (3000-7000毫秒)
        self.animation_duration = random.randint(3000, 7000)
        self.animation_start_time = time.time() * 1000  # 转换为毫秒
        self.animation_running = True
        self.final_result = None  # 重置最终结果
        
        # 开始动画
        self.animate_computer_choice()
    
    def animate_computer_choice(self):
        if not self.animation_running:
            return
        
        # 计算已过去的时间
        current_time = time.time() * 1000
        elapsed = current_time - self.animation_start_time
        
        if elapsed < self.animation_duration:
            # 随机选择一个手势
            choices = ['✊', '✌', '✋']
            self.computer_choice = random.choice(choices)
            
            # 更新显示
            self.update_display()
            
            # 尽可能快地继续动画
            self.root.after(20, self.animate_computer_choice)
        else:
            # 动画结束，确定最终选择
            self.animation_running = False
            self.final_result = self.determine_winner(self.user_choice, self.computer_choice)
            self.finish_game()
    
    def finish_game(self):
        # 确定结果并更新余额
        if "赢了" in self.final_result:
            win_amount = self.current_bet * 2.00
            self.balance += win_amount
            self.last_win = win_amount
        elif "和" in self.final_result:
            win_amount = self.current_bet * 0.99
            self.balance += win_amount
            self.last_win = win_amount
        else:
            self.last_win = 0.0
        
        # 更新余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新显示
        self.update_display()
        
        # 启用按钮
        self.play_button.config(state=tk.NORMAL)
        self.reset_bet_button.config(state=tk.NORMAL)
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 重置用户选择，准备下一轮
        self.user_choice = None
        self.computer_choice = None
        self.final_result = None
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 更新余额到JSON
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    """供small_games.py调用的主函数"""
    root = tk.Tk()
    game = RPSGame(root, initial_balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = RPSGame(root, 1000.0, "test_user")
    root.mainloop()