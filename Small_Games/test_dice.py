import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time
import math

def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

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
        self.enabled = True  # 添加启用状态标志
        
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))
        
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        # 只在启用状态下响应点击
        if self.enabled and self.command:
            self.command()
    
    def configure(self, state=None, **kwargs):
        """重写configure方法以支持状态改变"""
        if state is not None:
            self.enabled = (state == tk.NORMAL)
        super().configure(**kwargs)

class DiceGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("骰子游戏")
        self.root.geometry("1200x700+50+10")  # 增加宽度以适应三部分布局
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.selected_number = 7  # 默认选择的数字
        self.bet_type = "over"    # over/under
        self.dice_result = [1, 1] # 两个骰子的结果
        self.selected_cup = -1  # 玩家选择的杯子
        self.game_active = False
        self.animation_active = False
        self.last_win = 0.0
        self.chip_buttons = []
        self.current_bet = 0.0
        self.animation_id = None  # 用于存储动画ID
        self.game_state = "idle"  # idle, rolling, result
        
        # 赔率表
        self.odds_table = {
            1: 33.56,  # 1个数字的赔率
            2: 10.52,
            3: 4.76,
            4: 2.46,
            5: 1.3,
            6: 0.65,
            7: 0.33,
            8: 0.15,
            9: 0.05
        }
        
        # 创建UI
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧面板 - 投注选择 (宽度缩小1/3)
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE, width=180)  # 宽度减小
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
        
        tk.Label(left_frame, text="投注选择", font=("Arial", 14, "bold"),  # 字体减小
                bg="#16213e", fg="#e94560", pady=8).pack(fill=tk.X)  # 内边距减小
        
        # 超过/低于选择
        bet_type_frame = tk.Frame(left_frame, bg="#16213e", padx=8, pady=8)  # 内边距减小
        bet_type_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(bet_type_frame, text="选择:", font=("Arial", 10, "bold"),  # 字体减小
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 3))  # 内边距减小
        
        self.bet_type_var = tk.StringVar()
        self.bet_type_var.set("over")
        
        # 创建两个按钮框架
        buttons_frame = tk.Frame(bet_type_frame, bg="#16213e")
        buttons_frame.pack(fill=tk.X, pady=3)  # 内边距减小
        
        self.over_btn = tk.Radiobutton(
            buttons_frame, text="超过(不包括)", variable=self.bet_type_var, value="over",
            font=("Arial", 10), bg="#16213e", fg="#4cc9f0", selectcolor="#2d4059",  # 字体减小
            indicatoron=0, width=12, height=1, command=self.set_bet_type  # 宽度和高度减小
        )
        self.over_btn.pack(side=tk.LEFT, padx=(0, 3))  # 内边距减小
        
        self.under_btn = tk.Radiobutton(
            buttons_frame, text="低于(不包括)", variable=self.bet_type_var, value="under",
            font=("Arial", 10), bg="#16213e", fg="#bdc3c7", selectcolor="#2d4059",  # 字体减小
            indicatoron=0, width=12, height=1, command=self.set_bet_type  # 宽度和高度减小
        )
        self.under_btn.pack(side=tk.RIGHT, padx=(3, 0))  # 内边距减小
        
        # 数字选择器
        number_frame = tk.Frame(left_frame, bg="#16213e", padx=8, pady=8)  # 内边距减小
        number_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(number_frame, text="选择数字:", font=("Arial", 10, "bold"),  # 字体减小
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 3))  # 内边距减小
        
        number_control_frame = tk.Frame(number_frame, bg="#16213e")
        number_control_frame.pack(fill=tk.X, pady=5)
        
        # 数字显示
        number_display_frame = tk.Frame(number_control_frame, bg="#0f3460", bd=2, relief=tk.SUNKEN)
        number_display_frame.pack(side=tk.LEFT, padx=(0, 5))  # 内边距减小
        
        self.number_display = tk.Label(
            number_display_frame, text=str(self.selected_number), 
            font=("Arial", 36, "bold"), bg="#0f3460", fg="#ffd369",  # 字体减小
            width=3, height=1  # 宽度和高度减小
        )
        self.number_display.pack(padx=10, pady=5)  # 内边距减小
        
        # 加减按钮
        button_frame = tk.Frame(number_control_frame, bg="#16213e")
        button_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.plus_btn = tk.Button(
            button_frame, text="+", font=("Arial", 14, "bold"),  # 字体减小
            bg="#27ae60", fg="white", width=3, height=1, command=self.increase_number  # 宽度减小
        )
        self.plus_btn.pack(pady=(0, 3))  # 内边距减小
        
        self.minus_btn = tk.Button(
            button_frame, text="-", font=("Arial", 14, "bold"),  # 字体减小
            bg="#e74c3c", fg="white", width=3, height=1, command=self.decrease_number  # 宽度减小
        )
        self.minus_btn.pack()
        
        # 赔率显示
        odds_frame = tk.Frame(left_frame, bg="#16213e", padx=8, pady=8)  # 内边距减小
        odds_frame.pack(fill=tk.X, pady=(0, 8))  # 内边距减小
        
        tk.Label(odds_frame, text="赔率:", font=("Arial", 12, "bold"),  # 字体减小
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))  # 内边距减小
        
        self.odds_var = tk.StringVar()
        self.odds_var.set(self.get_odds_display())
        
        odds_display_frame = tk.Frame(odds_frame, bg="#0f3460", bd=2, relief=tk.SUNKEN)
        odds_display_frame.pack(fill=tk.X, pady=3)  # 内边距减小
        
        tk.Label(odds_display_frame, textvariable=self.odds_var, font=("Arial", 18, "bold"),  # 字体减小
                bg="#0f3460", fg="#ffd369", pady=5).pack()  # 内边距减小
        
        # 赔率说明
        odds_info = tk.Label(
            odds_frame, text=f"赔率显示为总倍数，例如选择6个数字时赔率为1.65X", 
            font=("Arial", 8), bg="#16213e", fg="#bdc3c7", justify=tk.LEFT  # 字体减小
        )
        odds_info.pack(anchor=tk.W, pady=(5, 0))  # 内边距减小
        
        # 中间面板 - 骰子显示 (占据更多空间)
        center_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(center_frame, text="骰子游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560", pady=10).pack(fill=tk.X)
        
        self.game_canvas = tk.Canvas(center_frame, bg="#0f3460", bd=0, highlightthickness=0)
        self.game_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 骰子显示区域
        self.dice_frame = tk.Frame(self.game_canvas, bg="#0f3460")
        self.dice_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        self.dice_labels = []
        for i in range(2):
            lbl = tk.Label(self.dice_frame, text="⚀", font=("Arial", 100), 
                          bg="#0f3460", fg="white")
            lbl.pack(side=tk.LEFT, padx=20)
            self.dice_labels.append(lbl)
        
        self.status_label = tk.Label(self.game_canvas, text="选择下注金额和数字后点击开始游戏", 
                                   font=("Arial", 14), bg="#0f3460", fg="#bdc3c7")
        self.status_label.place(relx=0.5, rely=0.85, anchor=tk.CENTER)
        
        # 右侧面板 - 控制区域
        right_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        # 余额显示
        balance_frame = tk.Frame(right_frame, bg="#16213e", padx=10, pady=10)
        balance_frame.pack(fill=tk.X)
        
        tk.Label(balance_frame, text="余额:", font=("Arial", 14), 
                bg="#16213e", fg="#f1f1f1").pack(side=tk.LEFT)
        
        self.balance_var = tk.StringVar()
        self.balance_var.set(f"${self.balance:.2f}")
        tk.Label(balance_frame, textvariable=self.balance_var, font=("Arial", 14, "bold"), 
                bg="#16213e", fg="#ffd369").pack(side=tk.LEFT, padx=(5, 0))
        
        # 筹码按钮
        chips_frame = tk.Frame(right_frame, bg="#16213e", padx=10, pady=10)
        chips_frame.pack(fill=tk.X)
        
        tk.Label(chips_frame, text="筹码:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        chips = [
            ("$5", '#ff0000', 'white'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black')
        ]
        
        chips_grid = tk.Frame(chips_frame, bg="#16213e")
        chips_grid.pack(fill=tk.X)
        
        self.chip_buttons = []
        for i, (text, bg_color, fg_color) in enumerate(chips):
            row = i // 3
            col = i % 3
            
            btn = CircleButton(
                chips_grid, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda t=text: self.add_chip(t[1:]), radius=25
            )
            btn.grid(row=row, column=col, padx=5, pady=5)
            self.chip_buttons.append(btn)
        
        # 游戏按钮
        button_frame = tk.Frame(right_frame, bg="#16213e", padx=10, pady=10)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_button = tk.Button(
            button_frame, text="开始游戏", font=("Arial", 14, "bold"),
            bg="#27ae60", fg="white", height=2, command=self.start_game
        )
        self.start_button.pack(fill=tk.X, pady=5)
        
        self.reset_bet_button = tk.Button(
            button_frame, text="重设下注金额", font=("Arial", 12),
            bg="#3498db", fg="white", height=2, command=self.reset_bet
        )
        self.reset_bet_button.pack(fill=tk.X, pady=5)
                
        # 下注金额和上局获胜金额显示
        bet_win_frame = tk.Frame(right_frame, bg="#16213e", padx=10, pady=10)
        bet_win_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 下注金额
        bet_frame = tk.Frame(bet_win_frame, bg="#16213e")
        bet_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(bet_frame, text="下注金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.bet_var = tk.StringVar()
        self.bet_var.set("$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 上局获胜金额
        win_frame = tk.Frame(bet_win_frame, bg="#16213e")
        win_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(win_frame, text="上局获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")
        tk.Label(win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 游戏规则
        rules_frame = tk.Frame(right_frame, bg="#16213e", padx=10, pady=10)
        rules_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(rules_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 选择下注金额和数字(3-11)",
            "2. 选择'超过'或'低于'",
            "3. 点击开始游戏按钮",
            "4. 骰子停止后显示结果",
            "5. 如果结果符合选择，赢得下注金额×赔率",
            "6. 赔率根据覆盖的数字数量确定"
        ]
        
        for rule in rules:
            tk.Label(rules_frame, text=rule, font=("Arial", 10), 
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=2)
    
    def get_odds(self):
        """根据选择的数字和投注类型计算赔率"""
        if self.bet_type == "over":
            # 超过时覆盖的数字数量 = 12 - selected_number
            num_covered = 12 - self.selected_number
        else:  # under
            # 低于时覆盖的数字数量 = selected_number - 2
            num_covered = self.selected_number - 2
        
        # 确保覆盖的数字数量在有效范围内
        num_covered = max(1, min(9, num_covered))
        return self.odds_table.get(num_covered, 1.0)
    
    def get_odds_display(self):
        """获取赔率显示文本"""
        odds = self.get_odds()
        # 显示为总倍数 (赔率 + 1)
        return f"{odds + 1:.2f}X"
    
    def increase_number(self):
        """增加选择的数字"""
        if self.selected_number < 11:
            self.selected_number += 1
            self.number_display.config(text=str(self.selected_number))
            self.odds_var.set(self.get_odds_display())
    
    def decrease_number(self):
        """减少选择的数字"""
        if self.selected_number > 3:
            self.selected_number -= 1
            self.number_display.config(text=str(self.selected_number))
            self.odds_var.set(self.get_odds_display())
    
    def set_bet_type(self):
        """设置投注类型（超过/低于）"""
        self.bet_type = self.bet_type_var.get()
        self.odds_var.set(self.get_odds_display())
        
        # 更新按钮样式
        if self.bet_type == "over":
            self.over_btn.config(fg="#4cc9f0", font=("Arial", 10, "bold"))  # 字体减小
            self.under_btn.config(fg="#bdc3c7", font=("Arial", 10))  # 字体减小
        else:
            self.over_btn.config(fg="#bdc3c7", font=("Arial", 10))  # 字体减小
            self.under_btn.config(fg="#4cc9f0", font=("Arial", 10, "bold"))  # 字体减小
    
    def add_chip(self, amount):
        # 只有在游戏空闲状态下才能添加筹码
        if self.game_state != "idle":
            return
            
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
        self.last_win_var.set(f"${self.last_win:.2f}")
    
    def roll_dice(self):
        """掷骰子并返回结果"""
        return [random.randint(1, 6), random.randint(1, 6)]
    
    def dice_to_symbol(self, value):
        """将骰子值转换为Unicode符号"""
        symbols = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        return symbols[value - 1] if 1 <= value <= 6 else "⚀"
    
    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
            
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.game_state = "rolling"
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 禁用所有按钮
        self.disable_all_buttons()
        
        # 重置状态
        self.dice_result = [1, 1]
        for lbl in self.dice_labels:
            lbl.config(text=self.dice_to_symbol(1))
        
        # 开始动画
        self.animation_start_time = time.time()
        self.animate_dice()
    
    def disable_all_buttons(self):
        """禁用所有按钮"""
        self.start_button.config(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)
        self.over_btn.config(state=tk.DISABLED)
        self.under_btn.config(state=tk.DISABLED)
        self.plus_btn.config(state=tk.DISABLED)
        self.minus_btn.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
    
    def enable_all_buttons(self):
        """启用所有按钮"""
        self.start_button.config(state=tk.NORMAL)
        self.reset_bet_button.config(state=tk.NORMAL)
        self.over_btn.config(state=tk.NORMAL)
        self.under_btn.config(state=tk.NORMAL)
        self.plus_btn.config(state=tk.NORMAL)
        self.minus_btn.config(state=tk.NORMAL)
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
    
    def animate_dice(self):
        elapsed = time.time() - self.animation_start_time
        
        if elapsed < 3:  # 3秒快速变化
            # 随机显示骰子值
            for lbl in self.dice_labels:
                v = random.randint(1, 6)
                lbl.config(text=self.dice_to_symbol(v))
            self.status_label.config(text="骰子转动中...")
            self.root.after(100, self.animate_dice)
        elif elapsed < 4:  # 1秒减速
            # 慢速变化
            for lbl in self.dice_labels:
                v = random.randint(1, 6)
                lbl.config(text=self.dice_to_symbol(v))
            self.status_label.config(text="骰子即将停止...")
            self.root.after(200, self.animate_dice)
        else:
            # 生成最终结果
            self.dice_result = self.roll_dice()
            total = sum(self.dice_result)
            
            # 显示最终结果
            for i, lbl in enumerate(self.dice_labels):
                lbl.config(text=self.dice_to_symbol(self.dice_result[i]))
            
            # 检查结果
            win = False
            if self.bet_type == "over" and total > self.selected_number:
                win = True
            elif self.bet_type == "under" and total < self.selected_number:
                win = True
            
            # 计算赢得的金额
            if win:
                odds = self.get_odds()
                win_amount = self.bet_amount * odds
                self.balance += win_amount
                self.last_win = win_amount
                self.status_label.config(text=f"骰子结果: {self.dice_result[0]} + {self.dice_result[1]} = {total} (赢了 ${win_amount:.2f}!)")
            else:
                self.last_win = 0.0
                self.status_label.config(text=f"骰子结果: {self.dice_result[0]} + {self.dice_result[1]} = {total} (未中奖)")
            
            # 更新JSON余额
            update_balance_in_json(self.username, self.balance)
            
            # 启用所有按钮
            self.enable_all_buttons()
            
            # 重置游戏状态
            self.game_state = "idle"
            
            # 更新显示
            self.update_display()
    
    def on_closing(self):
        # 停止任何进行中的动画
        if self.animation_id:
            self.root.after_cancel(self.animation_id)
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    root = tk.Tk()
    game = DiceGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = DiceGame(root, 1000.0, "test_user")
    root.mainloop()