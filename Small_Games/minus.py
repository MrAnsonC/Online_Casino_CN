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

# 不同地雷数量对应的赔率
odds_dict = {
    1: [1, 1, 1.04, 1.09, 1.14, 1.20, 1.26, 1.33, 1.41, 1.50, 1.60, 1.71, 1.85, 2.00, 2.18, 2.40, 2.67, 3.00, 3.43, 4.00, 4.80, 6.00, 8.00, 12.00, 24.00],
    3: [1, 1.09, 1.25, 1.43, 1.66, 1.94, 2.28, 2.71, 3.25, 3.94, 4.85, 6.07, 7.72, 10.04, 13.38, 18.40, 26.29, 39.43, 63.09, 110.40, 220.80, 552.00, 2208.00],
    5: [1, 1.20, 1.52, 1.94, 2.51, 3.29, 4.39, 5.95, 8.24, 11.68, 16.98, 25.48, 39.63, 64.40, 110.40, 202.40, 404.80, 910.80, 2428.80, 8500.80, 51004.80],
    10: [1, 1.60, 2.74, 4.85, 8.90, 16.98, 33.97, 71.71, 161.35, 391.86, 1044.96, 3134.87, 10972.06, 47545.60, 285273.60, 3138009.60]
}

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
                        font=("Arial", 10, "bold"))
        
        # 绑定点击事件
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if self.command:
            self.command()

class SquareButton(tk.Canvas):
    """自定义正方形按钮"""
    def __init__(self, master, text, bg_color, fg_color, command=None, size=100, *args, **kwargs):
        super().__init__(master, width=size, height=size, 
                         highlightthickness=0, bg="#0f3460", *args, **kwargs)
        self.size = size
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text = text
        self.command = command
        self.is_revealed = False
        
        # 绘制正方形按钮
        self.create_rectangle(0, 0, size, size, fill=bg_color, outline="#1a1a2e", width=2)
        self.text_id = self.create_text(size/2, size/2, text=text, 
                                       fill=fg_color, font=("Arial", 24, "bold"))
        
        # 绑定点击事件
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if not self.is_revealed and self.command:
            self.command()
    
    def reveal(self, content, bg_color, fg_color):
        """揭示格子内容"""
        self.is_revealed = True
        self.itemconfig(self.text_id, text=content, fill=fg_color)
        self.configure(bg=bg_color)
        self.itemconfig(1, fill=bg_color)  # 更新矩形填充色

class MinesGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("扫雷游戏")
        self.root.geometry("1000x700")
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.mines_count = 1
        self.board = []
        self.revealed_cells = set()
        self.game_active = False
        self.last_win = 0.0
        self.chip_buttons = []  # 存储筹码按钮的引用
        self.current_bet = 0.0  # 当前下注金额
        self.current_odds = 1.0
        self.next_odds = 1.0
        self.cell_buttons = []  # 存储格子按钮
        
        # 创建UI
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 游戏板（占更大空间）
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="扫雷游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        # 游戏板框架 - 增加内边距以放大格子
        self.board_frame = tk.Frame(left_frame, bg="#0f3460", padx=20, pady=20)
        self.board_frame.pack(fill=tk.BOTH, expand=True)
        
        # 初始化游戏板
        self.create_game_board()
        
        # 右侧 - 控制面板
        right_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE, width=300)
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
            ("$25", '#00ff00', 'black'),   # 绿色背景，黑色文字
            ("$100", '#000000', 'white'),  # 黑色背景，白色文字
            ("$500", "#FF7DDA", 'black'),  # 粉色背景，黑色文字
            ("$1K", '#ffffff', 'black')    # 白色背景，黑色文字
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
        
        self.mines_count_var = tk.StringVar()
        self.mines_count_var.set("1")
        
        difficulties = [
            ("1颗雷", "1"),
            ("3颗雷", "3"),
            ("5颗雷", "5"),
            ("10颗雷", "10")
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
        
        # 开始游戏/随机打开按钮
        self.game_button = tk.Button(
            button_frame, text="开始游戏", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_game
        )
        self.game_button.pack(pady=5)
        
        # 兑现按钮
        self.cash_out_button = tk.Button(
            button_frame, text="兑现: $0.00", font=("Arial", 12),
            bg="#e74c3c", fg="white", width=12, command=self.cash_out
        )
        self.cash_out_button.pack(pady=(5, 0))
        self.cash_out_button.pack_forget()  # 初始隐藏兑现按钮
        
        # 下个赔率显示
        self.next_odds_var = tk.StringVar()
        self.next_odds_var.set("下个赔率: 1.00")
        tk.Label(button_frame, textvariable=self.next_odds_var, font=("Arial", 11),
                bg="#16213e", fg="#4cc9f0").pack(pady=(0, 5))
        
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
            "1. 选择下注金额和难度(地雷数量)",
            "2. 点击开始游戏按钮",
            "3. 选择游戏板中的位置或使用随机打开",
            "4. 找到宝石继续，遇到地雷游戏结束",
            "5. 随时可以兑现奖金结束游戏",
            "6. 成功揭示所有宝石获得最大奖励"
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
        self.bet_var.set("$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 上局获胜金额
        win_frame = tk.Frame(bet_win_frame, bg="#16213e")
        win_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        tk.Label(win_frame, text="上局获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")
        tk.Label(win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
    
    def create_game_board(self):
        """创建5x5的游戏板 - 使用正方形按钮"""
        # 清除现有的按钮
        for widget in self.board_frame.winfo_children():
            widget.destroy()
        
        self.cell_buttons = []
        cell_size = 90  # 正方形尺寸
        
        for row in range(5):
            row_buttons = []
            for col in range(5):
                btn = SquareButton(
                    self.board_frame, text="?", 
                    bg_color="#2d4059", fg_color="white",
                    command=lambda r=row, c=col: self.select_cell(r, c),
                    size=cell_size
                )
                btn.grid(row=row, column=col, padx=5, pady=5)
                row_buttons.append(btn)
            self.cell_buttons.append(row_buttons)
    
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
    
    def set_difficulty(self, mines_count):
        self.mines_count = int(mines_count)
        # 更新按钮样式
        for i, (text, value) in enumerate([("1颗雷", "1"), ("3颗雷", "3"), ("5颗雷", "5"), ("10颗雷", "10")]):
            if value == mines_count:
                self.difficulty_buttons[i].configure(bg="#4e9de0")
            else:
                self.difficulty_buttons[i].configure(bg="#2d4059")
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
    
    def generate_board(self):
        """生成游戏板，包含指定数量的地雷"""
        total_cells = 25
        positions = random.sample(range(total_cells), self.mines_count)
        
        # 初始化游戏板（全部为安全格子）
        self.board = [['💎' for _ in range(5)] for _ in range(5)]
        
        # 放置地雷
        for pos in positions:
            row = pos // 5
            col = pos % 5
            self.board[row][col] = '💣'
        
        # 重置游戏状态
        self.revealed_cells = set()
        self.game_active = True
        self.current_odds = 1.0
        self.update_odds_display()
        
        # 重置游戏板显示
        self.create_game_board()
    
    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showinfo("提示", "请先设置下注金额！")
            return
        if self.current_bet > self.balance:
            messagebox.showinfo("错误", "下注金额不能超过余额！")
            return
        
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.generate_board()
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新UI状态
        self.game_button.config(text="随机打开", command=self.random_reveal)
        self.reset_bet_button.pack_forget()  # 隐藏重设按钮
        self.cash_out_button.pack(pady=(5, 0))  # 显示兑现按钮
        
        # 禁用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        # 禁用难度按钮
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.DISABLED)
        
        self.update_display()
    
    def random_reveal(self):
        """随机揭示一个未被揭示的格子"""
        if not self.game_active:
            return
        
        # 获取所有未被揭示的格子
        unrevealed = []
        for row in range(5):
            for col in range(5):
                if not self.cell_buttons[row][col].is_revealed:
                    unrevealed.append((row, col))
        
        if unrevealed:
            # 随机选择一个未被揭示的格子
            row, col = random.choice(unrevealed)
            self.select_cell(row, col)
        else:
            # 所有格子都已被揭示
            messagebox.showinfo("提示", "所有格子都已被揭示！")
    
    def select_cell(self, row, col):
        if not self.game_active:
            return
        
        # 如果已经揭示过这个格子，忽略
        if self.cell_buttons[row][col].is_revealed:
            return
        
        # 标记为已揭示
        self.revealed_cells.add((row, col))
        cell_value = self.board[row][col]
        
        if cell_value == '💣':  # 踩到地雷
            self.game_active = False
            # 使用自定义方法揭示地雷，保持明亮显示
            self.cell_buttons[row][col].reveal('💣', '#e74c3c', 'white')
            self.reveal_all_cells()
            self.last_win = 0.0
            self.end_game()
            messagebox.showinfo("游戏结束", "你踩到了地雷！游戏结束。")
        else:  # 安全格子
            # 使用自定义方法揭示宝石，保持明亮显示
            self.cell_buttons[row][col].reveal('💎', '#27ae60', 'white')
            
            # 更新赔率
            odds_index = len(self.revealed_cells)
            if self.mines_count in odds_dict and odds_index < len(odds_dict[self.mines_count]):
                self.current_odds = odds_dict[self.mines_count][odds_index]
            
            self.update_odds_display()
            
            # 检查是否获胜
            if len(self.revealed_cells) == 25 - self.mines_count:
                self.complete_game()
    
    def update_odds_display(self):
        """更新赔率显示"""
        # 计算可兑现金额
        cash_out_amount = self.bet_amount * self.current_odds
        self.cash_out_button.config(text=f"兑现: ${cash_out_amount:.2f}")
        
        # 计算下一个赔率
        next_index = len(self.revealed_cells) + 1
        if self.mines_count in odds_dict and next_index < len(odds_dict[self.mines_count]):
            next_odds = odds_dict[self.mines_count][next_index]
            self.next_odds_var.set(f"下个赔率: {next_odds:.2f}")
        else:
            self.next_odds_var.set(f"下个赔率: --")
    
    def reveal_all_cells(self):
        """揭示所有格子 - 使用自定义方法保持颜色明亮"""
        for row in range(5):
            for col in range(5):
                if not self.cell_buttons[row][col].is_revealed:
                    cell_value = self.board[row][col]
                    if cell_value == '💣':
                        self.cell_buttons[row][col].reveal('💣', '#e74c3c', 'white')
                    else:
                        self.cell_buttons[row][col].reveal('💎', '#27ae60', 'white')
    
    def cash_out(self):
        if not self.game_active:
            return
        
        # 计算赢得的金额
        win_amount = self.bet_amount * self.current_odds
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 揭示所有格子
        self.reveal_all_cells()
        
        # 结束游戏
        self.end_game()
        
        messagebox.showinfo("兑现成功", f"你成功兑现了 ${win_amount:.2f}！")
    
    def complete_game(self):
        """完成所有安全格子的揭示"""
        win_amount = self.bet_amount * self.current_odds
        self.balance += win_amount
        self.last_win = win_amount
        self.game_active = False
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 结束游戏
        self.end_game()
        
        messagebox.showinfo("游戏胜利", f"恭喜！你发现了所有宝石，赢得 ${win_amount:.2f}！")
    
    def end_game(self):
        """结束游戏，重置UI状态"""
        self.game_button.config(text="开始游戏", command=self.start_game)
        self.cash_out_button.pack_forget()  # 隐藏兑现按钮
        self.reset_bet_button.pack(pady=5)  # 显示重设按钮
        
        # 启用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 启用难度按钮
        for btn in self.difficulty_buttons:
            btn.configure(state=tk.NORMAL)
        
        # 重置赔率显示
        self.next_odds_var.set("下个赔率: --")
        
        # 更新显示
        self.update_display()
    
    def on_closing(self):
        """窗口关闭事件处理"""
        # 更新余额到JSON
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(balance, username):
    """供small_games.py调用的主函数"""
    root = tk.Tk()
    game = MinesGame(root, balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = MinesGame(root, 1000.0, "test_user")
    root.mainloop()