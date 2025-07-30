import tkinter as tk
from tkinter import ttk
import random
import json
import os
import time
import math
from PIL import Image, ImageTk
import sys

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
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()  # 先加载现有用户数据
    for user in users:
        if user['user_name'] == username:  # 查找当前用户
            user['cash'] = f"{new_balance:.2f}"  # 更新余额
            break
    save_user_data(users)  # 保存更新后的数据 

class DiceGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("骰子游戏")
        self.root.geometry("1000x700")
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.current_bet = 0.0
        self.target_number = 50
        self.bet_type = "above"  # "above" or "below"
        self.game_active = False
        self.last_win = 0.0
        
        # 定义赔率
        self.payouts = {
            "above": {
                1: 99.00, 5: 19.00, 10: 9.00, 15: 5.66, 20: 4.00,
                25: 3.00, 30: 2.33, 35: 1.85, 40: 1.50, 45: 1.22,
                50: 1.00, 55: 0.82, 60: 0.66, 65: 0.53, 70: 0.42,
                75: 0.33, 80: 0.25, 85: 0.17, 90: 0.11, 95: 0.05, 99: 0.01
            },
            "below": {
                1: 0.01, 5: 0.05, 10: 0.11, 15: 0.17, 20: 0.25,
                25: 0.33, 30: 0.42, 35: 0.53, 40: 0.66, 45: 0.82,
                50: 1.00, 55: 1.22, 60: 1.50, 65: 1.85, 70: 2.33,
                75: 3.00, 80: 4.00, 85: 5.66, 90: 9.00, 95: 19.00, 99: 99.00
            }
        }
        
        # 创建UI
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 骰子显示和结果区域
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="骰子游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        # 骰子显示区域
        self.dice_frame = tk.Frame(left_frame, bg="#0f3460", bd=0)
        self.dice_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 骰子画布
        self.dice_canvas = tk.Canvas(self.dice_frame, bg="#0f3460", highlightthickness=0)
        self.dice_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 结果标签
        self.result_var = tk.StringVar()
        self.result_var.set("请下注并开始游戏")
        result_label = tk.Label(self.dice_frame, textvariable=self.result_var, 
                              font=("Arial", 16, "bold"), bg="#0f3460", fg="#4cc9f0")
        result_label.pack(pady=10)
        
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
            ("$1", '#ff0000', 'white'),    # 红色背景，白色文字
            ("$5", '#00ff00', 'black'),    # 绿色背景，黑色文字
            ("$10", '#000000', 'white'),   # 黑色背景，白色文字
            ("$25", "#FF7DDA", 'black'),   # 粉色背景，黑色文字
            ("$100", '#ffffff', 'black')   # 白色背景，黑色文字
        ]
        
        self.chip_buttons = []  # 存储所有筹码按钮
        for text, bg_color, fg_color in chips:
            btn = tk.Button(
                chips_frame, text=text, font=("Arial", 10, "bold"),
                bg=bg_color, fg=fg_color, width=5, height=1, relief=tk.RAISED,
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
        
        # 目标数字选择
        target_frame = tk.Frame(right_frame, bg="#16213e")
        target_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(target_frame, text="目标数字 (1-99):", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.target_var = tk.IntVar()
        self.target_var.set(self.target_number)
        target_scale = tk.Scale(target_frame, from_=1, to=99, orient=tk.HORIZONTAL,
                               variable=self.target_var, command=self.update_target,
                               bg="#16213e", fg="#f1f1f1", highlightthickness=0,
                               sliderrelief=tk.RAISED, sliderlength=30, length=300)
        target_scale.pack(pady=5)
        
        # 下注类型选择
        bet_type_frame = tk.Frame(right_frame, bg="#16213e")
        bet_type_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(bet_type_frame, text="下注类型:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.bet_type_var = tk.StringVar()
        self.bet_type_var.set("above")
        
        above_btn = tk.Radiobutton(bet_type_frame, text="高于目标", variable=self.bet_type_var, 
                                  value="above", bg="#16213e", fg="#f1f1f1", selectcolor="#2d4059",
                                  command=self.update_bet_type)
        above_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        below_btn = tk.Radiobutton(bet_type_frame, text="低于目标", variable=self.bet_type_var, 
                                  value="below", bg="#16213e", fg="#f1f1f1", selectcolor="#2d4059",
                                  command=self.update_bet_type)
        below_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 赔率显示
        odds_frame = tk.Frame(right_frame, bg="#16213e")
        odds_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(odds_frame, text="当前赔率:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.odds_var = tk.StringVar()
        self.odds_var.set("1.00x")
        tk.Label(odds_frame, textvariable=self.odds_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#ffd369").pack(anchor=tk.W, pady=(5, 0))
        
        # 潜在赢利显示
        win_frame = tk.Frame(right_frame, bg="#16213e")
        win_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(win_frame, text="潜在赢利:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.win_var = tk.StringVar()
        self.win_var.set("$0.00")
        tk.Label(win_frame, textvariable=self.win_var, font=("Arial", 20, "bold"), 
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
        
        # 上局获胜金额
        last_win_frame = tk.Frame(right_frame, bg="#16213e")
        last_win_frame.pack(fill=tk.X, padx=10, pady=(10, 20))
        
        tk.Label(last_win_frame, text="上局获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")
        tk.Label(last_win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 更新赔率和赢利显示
        self.update_odds()
    
    def add_chip(self, amount):
        try:
            amount_val = float(amount)
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")
                self.update_win_amount()
        except ValueError:
            pass
    
    def reset_bet(self):
        self.current_bet = 0.0
        self.bet_var.set("$0.00")
        self.update_win_amount()
    
    def update_target(self, value):
        self.target_number = int(value)
        self.update_odds()
    
    def update_bet_type(self):
        self.bet_type = self.bet_type_var.get()
        self.update_odds()
    
    def update_odds(self):
        # 获取当前赔率
        payout = self.payouts[self.bet_type][self.target_number]
        self.odds_var.set(f"{payout:.2f}x")
        
        # 更新潜在赢利
        self.update_win_amount()
    
    def update_win_amount(self):
        payout = self.payouts[self.bet_type][self.target_number]
        win_amount = self.current_bet * payout
        self.win_var.set(f"${win_amount:.2f}")
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.draw_dice()
    
    def draw_dice(self):
        self.dice_canvas.delete("all")
        
        # 绘制骰子背景
        width = self.dice_canvas.winfo_width()
        height = self.dice_canvas.winfo_height()
        
        # 绘制目标区域
        target_x = width // 2
        target_y = height // 2 - 50
        
        # 绘制目标线
        self.dice_canvas.create_line(50, target_y, width-50, target_y, fill="#4e9de0", width=2, dash=(5, 3))
        
        # 绘制目标文本
        self.dice_canvas.create_text(target_x, target_y - 20, 
                                    text=f"目标: {self.target_number}", 
                                    font=("Arial", 14, "bold"), 
                                    fill="#ffd369")
        
        # 绘制结果区域（如果有结果）
        if hasattr(self, 'dice_result'):
            result_x = width // 2
            result_y = height // 2 + 50
            
            # 绘制结果圆
            self.dice_canvas.create_oval(result_x-50, result_y-50, result_x+50, result_y+50, 
                                        fill="#e94560" if self.dice_result < self.target_number else "#27ae60", 
                                        outline="#f1f1f1", width=2)
            
            # 绘制结果数字
            self.dice_canvas.create_text(result_x, result_y, text=str(self.dice_result), 
                                        font=("Arial", 24, "bold"), fill="#ffffff")
            
            # 绘制结果指示器
            if self.bet_type == "above":
                self.dice_canvas.create_polygon(
                    result_x, result_y-70,
                    result_x-15, result_y-40,
                    result_x+15, result_y-40,
                    fill="#27ae60" if self.dice_result > self.target_number else "#e94560"
                )
            else:  # below
                self.dice_canvas.create_polygon(
                    result_x, result_y+70,
                    result_x-15, result_y+40,
                    result_x+15, result_y+40,
                    fill="#27ae60" if self.dice_result < self.target_number else "#e94560"
                )
    
    def start_game(self):
        if self.current_bet <= 0:
            self.result_var.set("请先下注！")
            return
        if self.current_bet > self.balance:
            self.result_var.set("余额不足！")
            return
        
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.game_active = True
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新UI状态
        self.start_button.config(state=tk.DISABLED)
        
        # 禁用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 禁用目标滑块
        self.target_var.trace_add("write", lambda *args: None)  # 临时禁用
        
        # 开始掷骰子动画
        self.roll_dice()
    
    def roll_dice(self):
        # 模拟掷骰子动画
        self.dice_result = random.randint(1, 100)
        self.result_var.set("掷骰子中...")
        
        # 显示随机数字动画
        self.roll_animation(10)
    
    def roll_animation(self, count):
        if count > 0:
            # 显示随机数字
            temp_result = random.randint(1, 100)
            self.dice_result = temp_result
            self.draw_dice()
            
            # 继续动画
            self.root.after(100, lambda: self.roll_animation(count-1))
        else:
            # 动画结束，显示最终结果
            self.finish_roll()
    
    def finish_roll(self):
        # 确定结果
        win = False
        if self.bet_type == "above" and self.dice_result > self.target_number:
            win = True
        elif self.bet_type == "below" and self.dice_result < self.target_number:
            win = True
        
        # 计算赢利
        payout = self.payouts[self.bet_type][self.target_number]
        win_amount = self.bet_amount * payout
        
        if win:
            self.balance += win_amount
            self.last_win = win_amount
            self.result_var.set(f"恭喜！你赢了 ${win_amount:.2f}")
        else:
            self.last_win = 0.0
            self.result_var.set(f"很遗憾，没有赢。")
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新UI状态
        self.start_button.config(state=tk.NORMAL)
        
        # 启用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 启用目标滑块
        self.target_var.trace_add("write", lambda *args: self.update_target(self.target_var.get()))
        
        # 更新显示
        self.update_display()
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 更新余额到JSON
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    """供small_games.py调用的主函数"""
    root = tk.Tk()
    game = DiceGame(root, initial_balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = DiceGame(root, 1000.0, "test_user")
    root.mainloop()