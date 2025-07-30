import tkinter as tk
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
    if not os.path.exists(file_path):
        return []
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
                        font=("Arial", 10, "bold"))
        
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if self.command:
            self.command()

class SmallMaryGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("小玛丽游戏")
        self.root.geometry("1000x700+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 游戏数据
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.current_bet = 0.0
        self.last_win = 0.0
        self.spinning = False
        self.animation_speed = 100  # 动画速度(毫秒)
        self.animation_steps = 20   # 动画步数
        
        # 游戏图案 - 每个转轴包含所有图案
        self.symbols = ['🍒', '🍊', '🍋', '🍉', '🔔', '⭐', '7']
        
        # 每个转轴的图案序列
        self.reel_symbols = [
            ['🍒', '🍊', '🍋', '🍉', '🔔', '⭐', '7'],
            ['🍋', '🍉', '🔔', '⭐', '7', '🍒', '🍊'],
            ['🔔', '⭐', '7', '🍒', '🍊', '🍋', '🍉']
        ]
        
        # 当前显示的图案位置
        self.reel_positions = [0, 0, 0]
        
        # 赔率表
        self.payouts = {
            ('7', '7', '7'): 100,  # 777
            ('🔔', '🔔', '🔔'): 50,     # 三个铃铛
            ('⭐', '⭐', '⭐'): 30,      # 三个星星
            ('🍉', '🍉', '🍉'): 20,    # 三个西瓜
            ('🍋', '🍋', '🍋'): 15,    # 三个柠檬
            ('🍊', '🍊', '🍊'): 10,    # 三个橙子
            ('🍒', '🍒', '🍒'): 5,     # 三个樱桃
            ('🍒', '🍒', None): 2,     # 两个樱桃
            ('🍒', None, None): 1      # 一个樱桃
        }
        
        # 创建UI
        self.create_widgets()
        self.update_display()
        self.generate_reels()  # 初始生成转轴
    
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧 - 转轴显示
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="小玛丽游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        self.reels_canvas = tk.Canvas(left_frame, bg="#0f3460", bd=0, highlightthickness=0)
        self.reels_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
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
        
        # 游戏按钮
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        self.spin_button = tk.Button(
            button_frame, text="开始旋转", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_spin
        )
        self.spin_button.pack(pady=5)
        
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
            "1. 选择下注金额",
            "2. 点击开始旋转按钮",
            "3. 转轴停止后计算奖金",
            "4. 相同图案组合获得对应奖励",
            "5. 777组合获得最高100倍奖励",
            "6. 樱桃组合获得基础奖励"
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
        
        # 添加结果显示标签
        self.result_var = tk.StringVar()
        self.result_var.set("等待开始...")
        self.result_label = tk.Label(
            right_frame, textvariable=self.result_var, font=("Arial", 14, "bold"),
            bg="#16213e", fg="#ffd369")
        self.result_label.pack(pady=10)
    
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
        self.last_win_var.set(f"${self.last_win:.2f}")
        self.draw_reels()
    
    def generate_reels(self):
        # 随机初始化转轴位置
        self.reel_positions = [
            random.randint(0, len(self.reel_symbols[0]) - 1),
            random.randint(0, len(self.reel_symbols[1]) - 1),
            random.randint(0, len(self.reel_symbols[2]) - 1)
        ]
    
    def get_visible_symbols(self):
        # 获取当前可见的图案
        visible = []
        for i in range(3):
            reel = self.reel_symbols[i]
            pos = self.reel_positions[i]
            visible.append(reel[pos])
        return visible
    
    def draw_reels(self):
        self.reels_canvas.delete("all")
        
        # 绘制转轴框架
        self.reels_canvas.create_rectangle(50, 50, 750, 550, fill="#1a1a2e", outline="#e94560", width=3)
        
        # 绘制三个转轴
        for i in range(3):
            # 转轴背景
            self.reels_canvas.create_rectangle(150 + i*200, 100, 150 + i*200 + 150, 500, 
                                             fill="#0f3460", outline="#4cc9f0", width=2)
            
            # 绘制转轴上的图案
            reel = self.reel_symbols[i]
            pos = self.reel_positions[i]
            reel_size = len(reel)
            
            # 显示当前行和前后的图案，创建连续效果
            for j in range(-1, 2):  # 显示当前行、上一行和下一行
                index = (pos + j) % reel_size
                symbol = reel[index]
                
                # 计算y位置
                y_pos = 250 + j * 100  # 中心位置是250，上下各100像素
                
                # 绘制图案
                self.reels_canvas.create_text(225 + i*200, y_pos, 
                                             text=symbol, 
                                             font=("Arial", 36 if j == 0 else 24), 
                                             fill="white")
        
        # 绘制中奖线
        self.reels_canvas.create_line(100, 250, 700, 250, fill="#ffd369", width=3, dash=(4, 2))
        
        # 标题
        self.reels_canvas.create_text(400, 30, text="小玛丽水果机", 
                                     font=("Arial", 24, "bold"), fill="#e94560")
    
    def start_spin(self):
        if self.spinning:
            return
            
        if self.current_bet <= 0:
            self.result_var.set("请先下注!")
            return
        if self.current_bet > self.balance:
            self.result_var.set("余额不足!")
            return
            
        self.bet_amount = self.current_bet
        self.balance -= self.bet_amount
        self.spinning = True
        self.result_var.set("旋转中...")
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        # 禁用按钮
        self.spin_button.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)
        
        # 设置动画速度随机变化
        self.animation_speed = 100
        self.animation_steps = random.randint(15, 25)
        self.current_step = 0
        
        # 开始旋转动画
        self.spin_animation()
    
    def spin_animation(self):
        if self.current_step < self.animation_steps:
            # 移动转轴位置
            for i in range(3):
                # 第一个转轴转得最快，第三个最慢
                if i == 0 or (self.current_step > self.animation_steps / 3 and i == 1) or (self.current_step > 2 * self.animation_steps / 3 and i == 2):
                    self.reel_positions[i] = (self.reel_positions[i] + 1) % len(self.reel_symbols[i])
            
            # 随着动画进行，逐渐减慢速度
            if self.current_step > self.animation_steps / 2:
                self.animation_speed += 10
            
            self.draw_reels()
            self.current_step += 1
            self.root.after(self.animation_speed, self.spin_animation)
        else:
            # 完成旋转
            self.spinning = False
            self.spin_button.config(state=tk.NORMAL)
            
            # 启用按钮
            for btn in self.chip_buttons:
                btn.configure(state=tk.NORMAL)
            self.reset_bet_button.config(state=tk.NORMAL)
            
            # 计算奖金
            self.calculate_payout()
    
    def calculate_payout(self):
        # 获取结果
        result = self.get_visible_symbols()
        
        # 检查所有可能的组合
        win_amount = 0
        win_message = "未中奖"
        
        # 检查三个相同
        if result[0] == result[1] == result[2]:
            for combo, payout in self.payouts.items():
                if combo[0] == result[0]:
                    win_amount = self.bet_amount * payout
                    win_message = f"恭喜! {result[0]}x3 获得 {payout}倍奖励!"
                    break
        else:
            # 检查樱桃组合
            cherry_count = sum(1 for symbol in result if symbol == '🍒')
            if cherry_count >= 1:
                for combo, payout in self.payouts.items():
                    if combo[0] == '🍒' and combo[1] == ('🍒' if cherry_count >= 2 else None):
                        win_amount = self.bet_amount * payout
                        win_message = f"樱桃组合! 获得 {payout}倍奖励!"
                        break
        
        # 更新余额和显示
        self.balance += win_amount
        self.last_win = win_amount
        self.result_var.set(win_message)
        
        # 更新JSON余额
        update_balance_in_json(self.username, self.balance)
        
        self.update_display()
    
    def on_closing(self):
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    root = tk.Tk()
    game = SmallMaryGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = SmallMaryGame(root, 1000.0, "test_user")
    root.mainloop()