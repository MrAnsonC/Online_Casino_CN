import tkinter as tk
from tkinter import ttk
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
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)  # 外框使用背景色
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 10, "bold"))
        
        # 绑定点击事件
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if self.command:
            self.command()

class TowerGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("上塔游戏")
        self.root.geometry("1000x700")
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.difficulty = "1"
        self.board = []
        self.revealed_rows = []
        self.current_round = 0
        self.game_active = False
        self.last_win = 0.0
        self.chip_buttons = []  # 存储筹码按钮的引用
        self.current_bet = 0.0  # 当前下注金额
        
        # 定义赔率和骷髅分布
        self.odds = {
            "1": [1.28, 1.64, 2.10, 2.68, 3.44, 4.40, 5.63, 7.21],
            "2": [1.44, 2.07, 2.99, 4.30, 6.19, 8.92, 12.84, 18.49],
            "3": [1.92, 3.69, 7.08, 13.59, 26.09, 50.10, 96.19, 184.68],
            "4": [2.88, 8.29, 23.89, 68.80, 198.14, 570.63, 1643.42, 4733.04],
            "5": [3.84, 14.75, 56.62, 217.43, 834.94, 3206.18, 12311.72, 47276.99],
        }
        
        self.skull_distribution = {
            "1": (1, 3),
            "2": (1, 2),
            "3": (1, 1),
            "4": (2, 1),
            "5": (3, 1),
        }
        
        # 创建UI
        self.create_widgets()
        self.update_display()
        self.generate_board()  # 初始生成游戏板
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 塔显示
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="上塔游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        self.tower_canvas = tk.Canvas(left_frame, bg="#0f3460", bd=0, highlightthickness=0)
        self.tower_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
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
        
        # 难度选择
        difficulty_frame = tk.Frame(right_frame, bg="#16213e")
        difficulty_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(difficulty_frame, text="难度:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.difficulty_var = tk.StringVar()
        self.difficulty_var.set("1")
        
        difficulties = [
            ("入门", "1"),
            ("简单", "2"),
            ("中等", "3"),
            ("困难", "4"),
            ("地狱", "5")
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
        
        # 游戏按钮
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        self.start_button = tk.Button(
            button_frame, text="开始游戏", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_game
        )
        self.start_button.pack(pady=5)
        
        self.cash_out_button = tk.Button(
            button_frame, text="兑现奖金", font=("Arial", 12),
            bg="#e74c3c", fg="white", width=12, command=self.cash_out
        )
        self.cash_out_button.pack(pady=5)
        self.cash_out_button.pack_forget()  # 初始隐藏兑现按钮
        
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
            "1. 选择下注金额和难度",
            "2. 点击开始游戏按钮",
            "3. 选择塔中的位置",
            "4. 找到宝石继续，遇到骷髅游戏结束",
            "5. 随时可以兑现奖金结束游戏",
            "6. 成功通关所有8层获得最大奖励"
        ]
        
        for rule in rules:
            tk.Label(info_frame, text=rule, font=("Arial", 10), 
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=2)
            
        # 下注金额和上局获胜金额显示 - 移动到游戏规则下方
        bet_win_frame = tk.Frame(right_frame, bg="#16213e")
        bet_win_frame.pack(fill=tk.X, padx=10, pady=(0, 10))  # 调整位置到规则下方
        
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
    
    def add_chip(self, amount):
        try:
            amount_val = float(amount)
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")  # 格式化为两位小数
        except ValueError:
            pass
    
    def reset_bet(self):
        self.current_bet = 0.0
        self.bet_var.set("$0.00")  # 格式化为两位小数
    
    def set_difficulty(self, difficulty):
        self.difficulty = difficulty
        # 更新按钮样式
        for i, (text, value) in enumerate([("入门", "1"), ("简单", "2"), ("中等", "3"), ("困难", "4"), ("地狱", "5")]):
            if value == difficulty:
                self.difficulty_buttons[i].configure(bg="#4e9de0")
            else:
                self.difficulty_buttons[i].configure(bg="#2d4059")
        
        # 生成新游戏板并更新显示
        self.generate_board()
        self.update_display()
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")  # 格式化为两位小数
        self.draw_tower()
    
    def draw_tower(self):
        self.tower_canvas.delete("all")
        
        if not self.board:
            # 显示欢迎信息
            self.tower_canvas.create_text(300, 250, text="上塔游戏", 
                                         font=("Arial", 28, "bold"), fill="#e94560")
            self.tower_canvas.create_text(300, 300, text="选择下注金额和难度后点击开始游戏", 
                                         font=("Arial", 14), fill="#bdc3c7")
            return
        
        # 绘制塔
        cell_size = 50
        padding = 20
        start_x = 150
        start_y = 500
        
        for i in range(len(self.board)-1, -1, -1):
            row = self.board[i]
            y = start_y - (i * (cell_size + 10))
            
            # 绘制行号和赔率
            self.tower_canvas.create_text(start_x - 60, y + cell_size//2, 
                                         text=f"{i+1}", font=("Arial", 12, "bold"), 
                                         fill="#f1f1f1")
            
            self.tower_canvas.create_text(start_x + len(row)*(cell_size+10) + 60, y + cell_size//2, 
                                         text=f"X{self.odds[self.difficulty][i]:.2f}", 
                                         font=("Arial", 12), fill="#ffd369")
            
            for j in range(len(row)):
                x = start_x + j * (cell_size + 10)
                
                # 绘制单元格
                if (i, j) in self.revealed_rows:  # 已揭示的位置
                    if self.board[i][j] == "💎":  # 宝石
                        self.tower_canvas.create_rectangle(x, y, x+cell_size, y+cell_size, 
                                                          fill="#27ae60", outline="#1a1a2e")
                        self.tower_canvas.create_text(x+cell_size//2, y+cell_size//2, 
                                                     text="💎", font=("Arial", 20))
                    else:  # 骷髅
                        self.tower_canvas.create_rectangle(x, y, x+cell_size, y+cell_size, 
                                                          fill="#cd1500", outline="#1a1a2e")
                        self.tower_canvas.create_text(x+cell_size//2, y+cell_size//2, 
                                                     text="💀", font=("Arial", 20))
                elif not self.game_active:  # 游戏结束，显示所有内容
                    if row[j] == "☠":
                        # 如果是当前踩中的格子，显示骷髅
                        if hasattr(self, 'exploded_cell') and self.exploded_cell == (i, j):
                            self.tower_canvas.create_rectangle(x, y, x+cell_size, y+cell_size, 
                                                              fill="#e74c3c", outline="#1a1a2e")
                            self.tower_canvas.create_text(x+cell_size//2, y+cell_size//2, 
                                                         text="☠", font=("Arial", 20))
                        else:
                            self.tower_canvas.create_rectangle(x, y, x+cell_size, y+cell_size, 
                                                              fill="#e74c3c", outline="#1a1a2e")
                            self.tower_canvas.create_text(x+cell_size//2, y+cell_size//2, 
                                                         text="💣", font=("Arial", 20))
                    else:
                        self.tower_canvas.create_rectangle(x, y, x+cell_size, y+cell_size, 
                                                          fill="#3498db", outline="#1a1a2e")
                        self.tower_canvas.create_text(x+cell_size//2, y+cell_size//2, 
                                                     text="💰", font=("Arial", 20))
                else:  # 未揭示的单元格
                    self.tower_canvas.create_rectangle(x, y, x+cell_size, y+cell_size, 
                                                      fill="#2d4059", outline="#1a1a2e")
                    
                    # 添加可点击区域
                    if i == self.current_round:
                        tag_name = f"cell_{i}_{j}"
                        self.tower_canvas.create_rectangle(x, y, x+cell_size, y+cell_size, 
                                                          fill="#4e9de0", outline="#1a1a2e", tags=tag_name)
                        self.tower_canvas.create_text(x+cell_size//2, y+cell_size//2, 
                                                     text="?", font=("Arial", 20, "bold"), 
                                                     fill="#f1f1f1", tags=tag_name)
                        self.tower_canvas.tag_bind(tag_name, "<Button-1>", 
                                                  lambda e, row=i, col=j: self.select_cell(row, col))
    
    def generate_board(self):
        skull_count, gem_count = self.skull_distribution[self.difficulty]
        board = []
        
        for _ in range(8):
            row = ["💎"] * gem_count + ["☠"] * skull_count
            random.shuffle(row)
            board.append(row)
        
        self.board = board
        self.revealed_rows = []
        self.current_round = 0
        self.game_active = False
        if hasattr(self, 'exploded_cell'):
            del self.exploded_cell
    
    def start_game(self):
        if self.current_bet <= 0:
            return
        if self.current_bet > self.balance:
            return
        
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.generate_board()
        self.current_round = 0
        self.game_active = True
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新UI状态
        self.start_button.config(state=tk.DISABLED)
        self.reset_bet_button.pack_forget()  # 隐藏重设按钮
        self.cash_out_button.pack(pady=5)  # 显示兑现按钮
        
        # 禁用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 禁用难度按钮
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.DISABLED)
        
        self.update_display()
    
    def select_cell(self, row, col):
        if not self.game_active or row != self.current_round:
            return
        
        # 检查选择
        if self.board[row][col] == "☠":  # 遇到骷髅
            self.game_active = False
            self.revealed_rows.append((row, col))
            self.exploded_cell = (row, col)  # 保存爆炸的格子位置
            
            # 显示爆炸效果
            self.show_explosion(row, col)
            self.last_win = 0.0
        else:  # 找到宝石
            self.revealed_rows.append((row, col))
            self.current_round += 1
            
            if self.current_round >= 8:  # 完成所有回合
                self.complete_game()
            else:
                self.update_display()
    
    def show_explosion(self, row, col):
        # 获取爆炸位置
        cell_size = 50
        padding = 20
        start_x = 150
        start_y = 500
        y = start_y - (row * (cell_size + 10))
        x = start_x + col * (cell_size + 10)
        
        # 绘制爆炸效果
        self.tower_canvas.create_rectangle(x, y, x+cell_size, y+cell_size, 
                                         fill="#ff0000", outline="#1a1a2e", tags="explosion")
        explosion = self.tower_canvas.create_text(x+cell_size//2, y+cell_size//2, 
                                                text="💥", font=("Arial", 30), 
                                                fill="#ffffff", tags="explosion")
        
        # 更新显示
        self.tower_canvas.update()
        
        # 短暂延迟后更新完整板
        self.tower_canvas.after(1000, self.finish_explosion)
    
    def finish_explosion(self):
        # 移除爆炸效果
        self.tower_canvas.delete("explosion")
        
        # 结束游戏
        self.end_game()
    
    def cash_out(self):
        if not self.game_active or self.current_round == 0:
            return
        
        # 计算赢得的金额
        win_multiplier = self.odds[self.difficulty][self.current_round - 1]
        win_amount = self.bet_amount * win_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 结束游戏
        self.end_game()
    
    def complete_game(self):
        # 计算赢得的金额
        win_multiplier = self.odds[self.difficulty][7]
        win_amount = self.bet_amount * win_multiplier
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 结束游戏
        self.end_game()
    
    def end_game(self):
        # 更新UI状态
        self.start_button.config(state=tk.NORMAL)
        self.cash_out_button.pack_forget()  # 隐藏兑现按钮
        self.reset_bet_button.pack(pady=5)  # 显示重设按钮
        
        # 启用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 启用难度按钮
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.NORMAL)
        
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
    game = TowerGame(root, initial_balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = TowerGame(root, 1000.0, "test_user")
    root.mainloop()