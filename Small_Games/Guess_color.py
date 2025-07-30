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

class ColorGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("抽颜色游戏")
        self.root.geometry("1000x670+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.board = []
        self.revealed_cells = set()
        self.game_active = False
        self.last_win = 0.0
        self.chip_buttons = []  # 存储筹码按钮的引用
        self.current_bet = 0.0  # 当前下注金额
        self.current_odds = 1.0
        self.cell_buttons = []  # 存储格子按钮
        self.color_counts = {'🔴': 0, '🔵': 0, '🟢': 0}  # 跟踪每种颜色被揭示的数量
        
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
        
        tk.Label(left_frame, text="抽颜色游戏", font=("Arial", 20, "bold"), 
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
        
        # 颜色计数筹码显示
        color_chips_frame = tk.Frame(right_frame, bg="#16213e")
        color_chips_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(color_chips_frame, text="已揭示颜色:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        # 创建三个颜色计数筹码
        self.color_chip_red = CircleButton(color_chips_frame, text="0", bg_color="#e74c3c", fg_color="white", radius=25)
        self.color_chip_red.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.color_chip_blue = CircleButton(color_chips_frame, text="0", bg_color="#3498db", fg_color="white", radius=25)
        self.color_chip_blue.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.color_chip_green = CircleButton(color_chips_frame, text="0", bg_color="#2ecc71", fg_color="white", radius=25)
        self.color_chip_green.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 游戏按钮 - 平行排列
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        # 创建子框架来容纳两个按钮
        buttons_row = tk.Frame(button_frame, bg="#16213e")
        buttons_row.pack(fill=tk.X, pady=5)
        
        # 左侧 - 重设下注金额按钮
        self.reset_bet_button = tk.Button(
            buttons_row, text="重设下注金额", font=("Arial", 14),
            bg="#3498db", fg="white", width=12, command=self.reset_bet
        )
        self.reset_bet_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 右侧 - 开始游戏按钮
        self.game_button = tk.Button(
            buttons_row, text="开始游戏", font=("Arial", 14, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_game
        )
        self.game_button.pack(side=tk.RIGHT)
                
        # 游戏信息
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 选择下注金额并开始游戏",
            "2. 点击格子揭示颜色",
            "3. 揭示12个格子后自动结算",
            "4. 颜色组合决定胜负:",
            "   - 非3-4-5组合: 赢1.95倍",
            "   - 3-4-5组合: 输掉下注",
            "5. 颜色分布: 红: 8个, 蓝: 8个, 绿: 8个"
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
                # 中心位置为空
                if row == 2 and col == 2:
                    btn = SquareButton(
                        self.board_frame, text="", 
                        bg_color="#0f3460", fg_color="white",
                        command=None,  # 中心位置不可点击
                        size=cell_size
                    )
                    btn.is_revealed = True  # 标记为已揭示
                    btn.configure(bg="#0f3460")
                else:
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
        if self.game_active:
            return
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
    
    def update_color_chips(self):
        """更新颜色计数筹码显示"""
        self.color_chip_red.itemconfig(2, text=str(self.color_counts['🔴']))  # 更新红色计数
        self.color_chip_blue.itemconfig(2, text=str(self.color_counts['🔵']))  # 更新蓝色计数
        self.color_chip_green.itemconfig(2, text=str(self.color_counts['🟢']))  # 更新绿色计数
    
    def generate_board(self):
        """生成游戏板，包含24个格子（红、蓝、绿各8个）"""
        # 创建颜色列表：8红，8蓝，8绿
        colors = ['🔴'] * 8 + ['🔵'] * 8 + ['🟢'] * 8
        random.shuffle(colors)
        
        # 初始化游戏板
        self.board = [['' for _ in range(5)] for _ in range(5)]
        
        # 填充颜色（跳过中心位置）
        color_index = 0
        for row in range(5):
            for col in range(5):
                # 跳过中心位置
                if row == 2 and col == 2:
                    self.board[row][col] = ''
                    continue
                
                self.board[row][col] = colors[color_index]
                color_index += 1
        
        # 重置游戏状态
        self.revealed_cells = set()
        self.game_active = True
        self.color_counts = {'🔴': 0, '🔵': 0, '🟢': 0}
        self.update_color_chips()
        
        # 重置游戏板显示
        self.create_game_board()
    
    def start_game(self):
        if self.current_bet <= 0:
            messagebox.showinfo("提示", "请先设置下注金额！")
            return
        if self.current_bet > self.balance:
            messagebox.showinfo("错误", "下注金额不能超过余额！")
            return
        
        if self.current_bet > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
            return
        
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.generate_board()
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 更新UI状态
        self.game_button.config(text="游戏中...", state=tk.DISABLED)
        
        # 修改：在游戏开始时将"重设下注金额"按钮改为"随机抽取"
        self.reset_bet_button.config(text="随机抽取", command=self.random_reveal, state=tk.NORMAL)
        
        # 禁用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        self.update_display()
    
    def random_reveal(self):
        """随机揭示一个未被揭示的格子"""
        if not self.game_active:
            return
        
        # 获取所有未被揭示的格子（排除中心位置）
        unrevealed = []
        for row in range(5):
            for col in range(5):
                if (row != 2 or col != 2) and not self.cell_buttons[row][col].is_revealed:
                    unrevealed.append((row, col))
        
        if unrevealed:
            # 随机选择一个未被揭示的格子
            row, col = random.choice(unrevealed)
            self.select_cell(row, col)
    
    def select_cell(self, row, col):
        if not self.game_active:
            return
        
        # 如果已经揭示过这个格子，忽略
        if self.cell_buttons[row][col].is_revealed:
            return
        
        # 标记为已揭示
        self.revealed_cells.add((row, col))
        cell_value = self.board[row][col]
        
        # 更新颜色计数
        self.color_counts[cell_value] += 1
        self.update_color_chips()
        
        # 设置格子颜色
        bg_color = {
            '🔴': '#e74c3c',  # 红色
            '🔵': '#3498db',  # 蓝色
            '🟢': '#2ecc71'   # 绿色
        }[cell_value]
        
        self.cell_buttons[row][col].reveal(cell_value, bg_color, 'white')
        
        # 检查是否达到12个格子
        if len(self.revealed_cells) == 12:
            self.check_game_result()
    
    def check_game_result(self):
        """检查游戏结果"""
        # 检查是否是3-4-5组合
        counts = sorted(self.color_counts.values())
        if counts == [3, 4, 5]:
            # 3-4-5组合，游戏失败
            self.game_active = False
            self.last_win = 0.0
            self.end_game()
            messagebox.showinfo("游戏结束", "你抽到了3-4-5组合！游戏结束。")
        else:
            # 非3-4-5组合，游戏胜利
            self.game_active = False
            win_amount = self.bet_amount * 1.95
            self.balance += win_amount
            self.last_win = win_amount
            
            # 更新JSON余额
            update_balance_in_json(self.username, self.balance)
            
            self.end_game()
            messagebox.showinfo("游戏胜利", f"恭喜！你赢得了 ${win_amount:.2f}！")
    
    def reveal_all_cells(self):
        """揭示所有格子"""
        for row in range(5):
            for col in range(5):
                if row == 2 and col == 2:  # 跳过中心位置
                    continue
                    
                if not self.cell_buttons[row][col].is_revealed:
                    cell_value = self.board[row][col]
                    bg_color = {
                        '🔴': '#e74c3c',  # 红色
                        '🔵': '#3498db',  # 蓝色
                        '🟢': '#2ecc71'   # 绿色
                    }[cell_value]
                    self.cell_buttons[row][col].reveal(cell_value, bg_color, 'white')
    
    def end_game(self):
        """结束游戏，重置UI状态"""
        self.game_button.config(text="开始游戏", state=tk.NORMAL)
        
        # 修改：在游戏结束时将"随机抽取"按钮改回"重设下注金额"
        self.reset_bet_button.config(text="重设下注金额", command=self.reset_bet, state=tk.NORMAL)
        
        # 启用筹码按钮
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
        
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
    game = ColorGame(root, balance, username)
    root.mainloop()
    # 返回更新后的余额
    return game.balance

if __name__ == "__main__":
    # 单独运行时的测试代码
    root = tk.Tk()
    # 使用测试余额和用户名
    game = ColorGame(root, 1000.0, "test_user")
    root.mainloop()