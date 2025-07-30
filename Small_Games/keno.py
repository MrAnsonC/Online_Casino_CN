import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time
import math

def get_data_file_path():
    # 用于获取保存数据的文件路径
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
    
def update_balance_in_json(username, new_balance):
    users = load_user_data()  # 先加载现有用户数据
    for user in users:
        if user['user_name'] == username:  # 查找当前用户
            user['cash'] = f"{new_balance:.2f}"  # 更新余额
            break
    save_user_data(users)  # 保存更新后的数据

# 赔率表
odds_easy = {
    1: [0.70, 1.85],
    2: [0, 2, 3.80],
    3: [0, 1.10, 1.38, 26],
    4: [0, 0, 2.2, 7.9, 90],
    5: [0, 0, 1.5, 4.2, 13, 300],
    6: [0, 0, 1.1, 2, 6.2, 100, 700],
    7: [0, 0, 1.1, 1.6, 3.5, 15, 225, 700],
    8: [0, 0, 1.1, 1.5, 2, 5.5, 39, 100, 800],
    9: [0, 0, 1.1, 1.3, 1.7, 2.5, 7.5, 50, 250, 1000],
    10: [0, 0, 1.1, 1.2, 1.3, 1.8, 3.5, 13, 50, 250, 1000]
}

odds_medium = {
    1: [0.4, 2.75],
    2: [0, 1.8, 5.1],
    3: [0, 0, 2.8, 50],
    4: [0, 0, 1.7, 10, 100],
    5: [0, 0, 1.4, 4, 14, 390],
    6: [0, 0, 0, 3, 9, 180, 710],
    7: [0, 0, 0, 2, 7, 30, 400, 800],
    8: [0, 0, 0, 2, 4, 11, 67, 400, 900],
    9: [0, 0, 0, 2, 2.5, 5, 15, 100, 500, 1000],
    10: [0, 0, 0, 1.6, 2, 4, 7, 26, 100, 500, 1000]
}

odds_difficult = {
    1: [0, 3.96],
    2: [0, 0, 17.10],
    3: [0, 0, 0, 81.50],
    4: [0, 0, 0, 10, 259],
    5: [0, 0, 0, 4.50, 48, 450],
    6: [0, 0, 0, 0, 11, 350, 710],
    7: [0, 0, 0, 0, 7, 90, 400, 800],
    8: [0, 0, 0, 0, 5, 20, 270, 600, 900],
    9: [0, 0, 0, 0, 4, 11, 56, 500, 800, 1000],
    10: [0, 0, 0, 0, 3.5, 8, 13, 63, 500, 800, 1000]
}

class CircleButton(tk.Canvas):
    """自定义圆形按钮"""
    def __init__(self, master, text, bg_color, fg_color, command=None, radius=30, *args, **kwargs):
        super().__init__(master, width=radius*2, height=radius*2, 
                         highlightthickness=0, bg="#16213e", *args, **kwargs)  # 背景色与父容器一致
        self.radius = radius
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text = text
        self.command = command
        
        # 绘制圆形按钮
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)
        # 修改字体大小为18
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))  # 字体大小从10改为18
        
        # 绑定点击事件
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if self.command:
            self.command()

class KenoGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("基诺游戏")
        self.root.geometry("1000x700+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.difficulty = "1"
        self.user_numbers = []
        self.winning_numbers = []
        self.game_active = False  # 添加游戏状态标志
        self.last_win = 0.0
        self.chip_buttons = []  # 存储筹码按钮的引用
        self.current_bet = 0.0  # 当前下注金额
        self.number_buttons = []  # 存储数字按钮的引用
        self.matches = 0  # 匹配的数字数量
        self.multiplier = 0.0  # 赔率倍数
        
        # 创建UI
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 数字选择区域
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="基诺游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        # 数字网格框架
        numbers_frame = tk.Frame(left_frame, bg="#0f3460")
        numbers_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建1-50的数字按钮
        self.create_number_buttons(numbers_frame)
        
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
            # 创建时传递完整的文本
            btn = CircleButton(
                chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda t=text: self.add_chip(t)  # 传递完整的文本
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)
        
        # 难度选择
        difficulty_frame = tk.Frame(right_frame, bg="#16213e")
        difficulty_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(difficulty_frame, text="难度:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.difficulty_var = tk.StringVar()
        self.difficulty_var.set("1")
        
        difficulties = [
            ("简单", "1"),
            ("中等", "2"),
            ("地狱", "3")
        ]
        
        self.difficulty_buttons = []  # 存储所有难度按钮
        for text, value in difficulties:
            btn = tk.Button(
                difficulty_frame, text=text, font=("Arial", 10),
                bg="#4e9de0" if value == "1" else "#2d4059", fg="white", 
                width=6, height=1, relief=tk.RAISED,
                command=lambda v=value: self.set_difficulty(v)
            )
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            self.difficulty_buttons.append(btn)
        
        # 游戏按钮 - 使用两行布局
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 第一行按钮
        row1_frame = tk.Frame(button_frame, bg="#16213e")
        row1_frame.pack(fill=tk.X, pady=5)
        
        self.start_button = tk.Button(
            row1_frame, text="开始游戏", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_game
        )
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.lucky_button = tk.Button(
            row1_frame, text="幸运数字", font=("Arial", 12),
            bg="#9b59b6", fg="white", width=12, command=self.add_lucky_number
        )
        self.lucky_button.pack(side=tk.RIGHT)
        
        # 第二行按钮
        row2_frame = tk.Frame(button_frame, bg="#16213e")
        row2_frame.pack(fill=tk.X, pady=5)
        
        self.clear_button = tk.Button(
            row2_frame, text="清空选择", font=("Arial", 12),
            bg="#e67e22", fg="white", width=12, command=self.clear_selection
        )
        self.clear_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.reset_bet_button = tk.Button(
            row2_frame, text="重设下注金额", font=("Arial", 12),
            bg="#3498db", fg="white", width=12, command=self.reset_bet
        )
        self.reset_bet_button.pack(side=tk.RIGHT)
                
        # 游戏信息
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 选择下注金额和难度",
            "2. 点击开始游戏按钮",
            "3. 选择1-10个数字(1-50)",
            "4. 点击'幸运数字'随机添加",
            "5. 系统将随机抽取10个中奖数字",
            "6. 根据匹配数量和难度获得奖金"
        ]
        
        for rule in rules:
            tk.Label(info_frame, text=rule, font=("Arial", 10), 
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=2)
            
        # 下注金额和上局获胜金额显示
        bet_win_frame = tk.Frame(right_frame, bg="#16213e")
        bet_win_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 下注金额
        bet_frame = tk.Frame(bet_win_frame, bg="#16213e")
        bet_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        tk.Label(bet_frame, text="下注金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.bet_var = tk.StringVar()
        self.bet_var.set("$0.00")  # 初始显示格式
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 上局获胜金额
        win_frame = tk.Frame(bet_win_frame, bg="#16213e")
        win_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        tk.Label(win_frame, text="上局获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")  # 初始显示格式
        tk.Label(win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 状态信息
        self.status_var = tk.StringVar()
        self.status_var.set("请选择下注金额和难度")
        status_label = tk.Label(right_frame, textvariable=self.status_var, 
                               font=("Arial", 12), bg="#16213e", fg="#ffd369")
        status_label.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 匹配信息
        self.matches_var = tk.StringVar()
        self.matches_var.set("匹配: 0 | 倍数: 0.0x")
        matches_label = tk.Label(right_frame, textvariable=self.matches_var, 
                               font=("Arial", 12, "bold"), bg="#16213e", fg="#4cc9f0")
        matches_label.pack(fill=tk.X, padx=10, pady=(0, 10))
    
    def create_number_buttons(self, parent):
        """创建1-50的数字按钮网格"""
        # 创建框架来容纳数字按钮
        grid_frame = tk.Frame(parent, bg="#0f3460")
        grid_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建10x5的网格
        self.number_buttons = []
        for row in range(10):
            grid_frame.rowconfigure(row, weight=1)
            for col in range(5):
                grid_frame.columnconfigure(col, weight=1)
                num = row * 5 + col + 1
                btn = tk.Button(
                    grid_frame, text=str(num), font=("Arial", 10, "bold"),
                    bg="#2d4059", fg="white", width=4, height=2,  # 正方形按钮
                    command=lambda n=num: self.toggle_number(n)
                )
                btn.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
                self.number_buttons.append(btn)
    
    def toggle_number(self, number):
        """切换数字的选中状态"""
        if number in self.user_numbers:
            self.user_numbers.remove(number)
            self.number_buttons[number-1].config(bg="#2d4059", fg="white")
        elif len(self.user_numbers) < 10:  # 最多选择10个数字
            self.user_numbers.append(number)
            self.number_buttons[number-1].config(bg="#4e9de0", fg="white")
        
        self.update_status()
    
    def add_chip(self, amount_text):
        """添加筹码金额（处理$1K的特殊情况）"""
        if self.game_active:
            return
            
        try:
            # 处理特殊格式（如$1K）
            if amount_text == "$1K":
                amount_val = 1000.0
            else:
                # 去掉$符号并转换为浮点数
                amount_val = float(amount_text[1:])
            
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")  # 格式化为两位小数
                self.update_status()
        except ValueError:
            pass
    
    def reset_bet(self):
        self.current_bet = 0.0
        self.bet_var.set("$0.00")  # 格式化为两位小数
        self.update_status()
    
    def set_difficulty(self, difficulty):
        self.difficulty = difficulty
        # 更新按钮样式
        for i, (text, value) in enumerate([("简单", "1"), ("中等", "2"), ("地狱", "3")]):
            if value == difficulty:
                self.difficulty_buttons[i].configure(bg="#4e9de0")
            else:
                self.difficulty_buttons[i].configure(bg="#2d4059")
        
        self.update_status()
    
    def update_status(self):
        """更新状态信息"""
        if self.current_bet <= 0:
            self.status_var.set("请选择下注金额")
        elif not self.user_numbers:
            self.status_var.set("请选择1-10个数字")
        else:
            difficulty_text = { "1": "简单", "2": "中等", "3": "地狱" }[self.difficulty]
            self.status_var.set(f"已选 {len(self.user_numbers)} 个数字 | {difficulty_text}模式 | 下注 ${self.current_bet:.2f}")
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")  # 格式化为两位小数
    
    def add_lucky_number(self):
        """添加幸运数字"""
        if len(self.user_numbers) >= 10:
            return
        
        # 找到所有未选择的数字
        available_numbers = [n for n in range(1, 51) if n not in self.user_numbers]
        
        if available_numbers:
            lucky_num = random.choice(available_numbers)
            self.user_numbers.append(lucky_num)
            self.number_buttons[lucky_num-1].config(bg="#4e9de0", fg="white")
            self.update_status()
    
    def clear_selection(self):
        """清空选择的数字"""
        self.user_numbers = []
        for btn in self.number_buttons:
            btn.config(bg="#2d4059", fg="white", state=tk.NORMAL)
        self.update_status()
    
    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        if not self.user_numbers:
            messagebox.showwarning("错误", "请至少选择一个数字")
            return
        
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        
        # 设置游戏状态为进行中
        self.game_active = True
        
        # 扣除下注金额
        self.balance -= self.current_bet
        self.update_display()
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 禁用按钮
        self.start_button.config(state=tk.DISABLED)
        self.lucky_button.config(state=tk.DISABLED)
        self.clear_button.config(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.DISABLED)
        for btn in self.number_buttons:
            btn.config(state=tk.DISABLED)
        
        # 重置匹配信息
        self.matches = 0
        self.multiplier = 0.0
        self.matches_var.set(f"匹配: 0 | 倍数: 0.0x")
        
        # 生成中奖号码
        self.winning_numbers = []
        while len(self.winning_numbers) < 10:
            num = random.randint(1, 50)
            if num not in self.winning_numbers:
                self.winning_numbers.append(num)
        
        # 开始抽奖动画
        self.draw_index = 0
        self.draw_numbers()
    
    def draw_numbers(self):
        """逐个显示中奖号码"""
        if self.draw_index >= 10:
            self.finish_game()
            return
        
        # 获取当前抽出的数字
        num = self.winning_numbers[self.draw_index]
        
        # 高亮显示该数字
        btn = self.number_buttons[num-1]
        if num in self.user_numbers:
            btn.config(bg="#27ae60", fg="white")  # 匹配成功 - 绿色
            self.matches += 1
        else:
            btn.config(bg="#e74c3c", fg="white")  # 未匹配 - 红色
        
        # 更新状态
        self.status_var.set(f"第 {self.draw_index+1} 个中奖数字: {num}")
        
        # 更新匹配信息
        num_choices = len(self.user_numbers)
        if self.difficulty == "1":
            odds_table = odds_easy
        elif self.difficulty == "2":
            odds_table = odds_medium
        else:
            odds_table = odds_difficult
        
        if num_choices in odds_table and self.matches < len(odds_table[num_choices]):
            self.multiplier = odds_table[num_choices][self.matches]
            self.matches_var.set(f"匹配: {self.matches} | 倍数: {self.multiplier:.2f}x")
        
        # 准备下一个数字
        self.draw_index += 1
        self.root.after(500, self.draw_numbers)  # 0.75秒后显示下一个数字

    def auto_clear(self):
        """自动清空选择"""
        self.clear_selection()
        # 重置匹配信息显示
        self.matches_var.set("匹配: 0 | 倍数: 0.0x")
    
    def finish_game(self):
        """完成游戏，计算奖金"""
        # 计算匹配数量
        matches = len(set(self.user_numbers) & set(self.winning_numbers))
        
        # 根据难度和选择数量获取赔率
        num_choices = len(self.user_numbers)
        if self.difficulty == "1":
            odds_table = odds_easy
        elif self.difficulty == "2":
            odds_table = odds_medium
        else:
            odds_table = odds_difficult
        
        if num_choices in odds_table and matches < len(odds_table[num_choices]):
            multiplier = odds_table[num_choices][matches]
        else:
            multiplier = 0.0
        
        # 计算奖金
        winnings = self.current_bet * multiplier
        self.balance += winnings
        self.last_win = winnings
        self.update_display()
        
        # 更新状态信息
        difficulty_text = { "1": "简单", "2": "中等", "3": "地狱" }[self.difficulty]
        self.status_var.set(
            f"匹配了 {matches} 个数字! 获得奖金 ${winnings:.2f} ({multiplier:.2f}X)"
        )
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)

        # 重置游戏状态
        self.game_active = False
        
        # 5秒后自动清空选择
        self.root.after(5000, self.auto_clear)
        
        # 启用按钮
        time.sleep(5)
        self.start_button.config(state=tk.NORMAL)
        self.lucky_button.config(state=tk.NORMAL)
        self.clear_button.config(state=tk.NORMAL)
        self.reset_bet_button.config(state=tk.NORMAL)

        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.NORMAL)
        for btn in self.number_buttons:
            btn.config(state=tk.NORMAL)
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 更新余额到JSON
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    """供small_games.py调用的主函数"""
    root = tk.Tk()
    game = KenoGame(root, initial_balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = KenoGame(root, 1000.0, "test_user")
    root.mainloop()