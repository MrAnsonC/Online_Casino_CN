import tkinter as tk
from tkinter import ttk, messagebox
import random
import time
from PIL import Image, ImageTk, ImageDraw, ImageFont
import math

class RouletteSpinWindow:
    def __init__(self, parent, winning_number, callback):
        self.parent = parent
        self.winning_number = winning_number
        self.callback = callback
        self.window = tk.Toplevel(parent)
        self.window.title("轮盘旋转中...")
        self.window.geometry("600x600")
        self.window.configure(bg='#1e3d59')
        self.window.resizable(False, False)
        self.window.grab_set()
        
        # 窗口居中
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent_x + (parent_width - 600) // 2
        y = parent_y + (parent_height - 600) // 2
        self.window.geometry(f"600x600+{x}+{y}")
        
        # 创建轮盘画布
        self.canvas = tk.Canvas(self.window, width=550, height=550, bg='#1e3d59', highlightthickness=0)
        self.canvas.pack(pady=20)
        
        # 初始化轮盘
        self.roulette_wheel = RouletteWheel(self.canvas, 550, 550)
        self.roulette_wheel.set_spin_complete_callback(self.on_spin_complete)
        
        # 状态标签
        self.status_label = tk.Label(self.window, text="轮盘旋转中...", font=("Arial", 16, "bold"), 
                                    fg='white', bg='#1e3d59')
        self.status_label.pack()
        
        # 开始旋转
        self.window.after(100, self.start_spin)
    
    def start_spin(self):
        """开始旋转轮盘"""
        self.roulette_wheel.spin(self.winning_number)
    
    def on_spin_complete(self, winning_number):
        """轮盘旋转完成"""
        # 显示结果
        num_text = "00" if winning_number == 37 else str(winning_number)
        self.status_label.config(text=f"结果: {num_text}")
        
        # 等待2秒后关闭窗口并回调
        self.window.after(2000, self.close_window)
    
    def close_window(self):
        """关闭窗口并回调"""
        self.window.destroy()
        self.callback(self.winning_number)


class RouletteWheel:
    def __init__(self, canvas, width, height):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.center_x = width // 2
        self.center_y = height // 2
        self.radius = min(width, height) * 0.4
        self.ball_radius = 10
        self.wheel_img = None
        self.ball_position = None
        self.ball_angle = 0
        self.spinning = False
        self.target_number = None
        self.on_spin_complete = None
        
        try:
            self.font_small = ImageFont.truetype("arial.ttf", 16)
            self.font_large = ImageFont.truetype("arial.ttf", 20)
        except:
            # 如果Arial不可用，使用默认字体
            self.font_small = ImageFont.load_default()
            self.font_large = ImageFont.load_default()
        
        self.create_wheel()
        
    def create_wheel(self):
        # 创建轮盘图像
        img = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 绘制轮盘外圈
        draw.ellipse([(self.center_x - self.radius, self.center_y - self.radius),
                     (self.center_x + self.radius, self.center_y + self.radius)], 
                     outline='#333', width=5, fill='#2c3e50')
        
        # 美式轮盘数字顺序
        numbers = [
            0, 28, 9, 26, 30, 11, 7, 20, 32, 17, 
            5, 22, 34, 15, 3, 24, 36, 13, 1, 00, 
            27, 10, 25, 29, 12, 8, 19, 31, 18, 6, 
            21, 33, 16, 4, 23, 35, 14, 2
        ]
        
        # 数字颜色定义
        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        
        # 绘制数字槽
        num_slots = len(numbers)
        angle_per_slot = 360 / num_slots
        text_radius = self.radius * 0.7
        
        for i, num in enumerate(numbers):
            angle = math.radians(i * angle_per_slot - 90)
            start_angle = math.radians(i * angle_per_slot)
            end_angle = math.radians((i + 1) * angle_per_slot)
            
            # 确定颜色
            if num == 0 or num == 00:
                color = '#2ecc71'  # 绿色
            elif num in red_numbers:
                color = '#e74c3c'  # 红色
            else:
                color = '#1a1a1a'  # 黑色
                
            # 绘制槽位
            draw.pieslice([(self.center_x - self.radius*0.95, self.center_y - self.radius*0.95),
                          (self.center_x + self.radius*0.95, self.center_y + self.radius*0.95)],
                          i * angle_per_slot, (i + 1) * angle_per_slot, 
                          fill=color, outline='#333')
            
            # 绘制数字
            text_x = self.center_x + text_radius * math.cos(angle)
            text_y = self.center_y + text_radius * math.sin(angle)
            
            text_color = '#ffffff' if color == '#1a1a1a' else '#ffffff'
            
            # 处理00显示
            num_text = "0" if num == 0 else "00" if num == 00 else str(num)
            
            # 使用字体对象
            if num == 0 or num == 00:
                draw.text((text_x - 10, text_y - 10), num_text, 
                         fill=text_color, font=self.font_large)
            else:
                draw.text((text_x - 10, text_y - 10), num_text, 
                         fill=text_color, font=self.font_small)
        
        # 添加中心标志
        draw.ellipse([(self.center_x - self.radius*0.1, self.center_y - self.radius*0.1),
                     (self.center_x + self.radius*0.1, self.center_y + self.radius*0.1)], 
                     fill='#f39c12', outline='#d35400')
        
        self.wheel_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(self.center_x, self.center_y, image=self.wheel_img)
        
    def spin(self, target_number=None):
        if self.spinning:
            return
            
        self.spinning = True
        self.target_number = target_number or random.randint(0, 37)  # 0-36 + 00 (37)
        
        # 重置球位置
        self.ball_angle = 0
        self.draw_ball()
        
        # 开始旋转动画
        self.animate_spin(0)
        
    def animate_spin(self, frame):
        if frame < 100:  # 旋转100帧
            # 增加旋转速度（开始时加速）
            speed = min(20, frame // 5 + 1)
            self.ball_angle = (self.ball_angle + speed) % 360
            
            # 更新球位置
            self.draw_ball()
            
            # 继续动画
            self.canvas.after(30, lambda: self.animate_spin(frame + 1))
        else:
            # 减速到目标位置
            target_angle = self.calculate_target_angle()
            self.decelerate_to_target(target_angle, 100)
    
    def decelerate_to_target(self, target_angle, frames_left):
        if frames_left > 0:
            # 计算当前角度和目标角度之间的差距
            angle_diff = (target_angle - self.ball_angle) % 360
            if angle_diff > 180:
                angle_diff -= 360
                
            # 减速运动
            speed = max(0.5, min(5, abs(angle_diff) / 20))
            
            # 更新球位置
            self.ball_angle = (self.ball_angle + speed * (1 if angle_diff > 0 else -1)) % 360
            self.draw_ball()
            
            # 继续动画
            self.canvas.after(40, lambda: self.decelerate_to_target(target_angle, frames_left - 1))
        else:
            # 最终定位到目标
            self.ball_angle = target_angle
            self.draw_ball()
            self.spinning = False
            # 触发结果回调
            if self.on_spin_complete:
                self.on_spin_complete(self.target_number)
    
    def calculate_target_angle(self):
        """计算目标数字对应的角度"""
        # 美式轮盘数字顺序
        numbers = [
            0, 28, 9, 26, 30, 11, 7, 20, 32, 17, 
            5, 22, 34, 15, 3, 24, 36, 13, 1, 00, 
            27, 10, 25, 29, 12, 8, 19, 31, 18, 6, 
            21, 33, 16, 4, 23, 35, 14, 2
        ]
        
        # 找到目标数字在列表中的索引
        try:
            index = numbers.index(self.target_number if self.target_number != 37 else 00)
        except ValueError:
            index = random.randint(0, len(numbers) - 1)
        
        # 每个槽位角度
        angle_per_slot = 360 / len(numbers)
        
        # 目标角度（加一点随机偏移使结果更自然）
        target_angle = (index * angle_per_slot + random.uniform(-3, 3)) % 360
        
        return target_angle
    
    def draw_ball(self):
        """在轮盘上绘制小球"""
        if self.ball_position:
            self.canvas.delete(self.ball_position)
            
        ball_radius = self.radius * 0.9
        angle_rad = math.radians(self.ball_angle - 90)  # -90使0点在上方
        
        x = self.center_x + ball_radius * math.cos(angle_rad)
        y = self.center_y + ball_radius * math.sin(angle_rad)
        
        self.ball_position = self.canvas.create_oval(
            x - self.ball_radius, y - self.ball_radius,
            x + self.ball_radius, y + self.ball_radius,
            fill='#ffffff', outline='#333'
        )
    
    def set_spin_complete_callback(self, callback):
        self.on_spin_complete = callback


class RouletteGame:
    def __init__(self, root):
        self.root = root
        self.root.title("美式轮盘游戏")
        self.root.geometry("1350x780")
        self.root.configure(bg='#0a5f38')
        
        # 游戏状态
        self.balance = 10000
        self.current_bet = 0
        self.bet_amount = 100
        self.last_win = 0
        self.bets = {}
        self.history = []
        self.accept_bets = True
        
        # 创建主界面
        self.create_widgets()
        
        # 设置默认筹码
        self.set_bet_amount(100)
        
        # 绑定回车键
        self.root.bind('<Return>', lambda event: self.spin_wheel())
        
    def create_widgets(self):
        # 主框架
        main_frame = tk.Frame(self.root, bg='#0a5f38')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧面板 - 下注区域
        left_frame = tk.Frame(main_frame, bg='#0a5f38')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 赌毯框架
        bet_area_frame = tk.LabelFrame(left_frame, text="下注区域", font=("Arial", 14, "bold"), 
                                     bg='#1e3d59', fg='white', padx=10, pady=10)
        bet_area_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建赌毯
        self.create_bet_area(bet_area_frame)
        
        # 右侧面板 - 控制面板
        right_frame = tk.Frame(main_frame, bg='#0a5f38', width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        # 控制面板
        control_frame = tk.LabelFrame(right_frame, text="控制面板", font=("Arial", 14, "bold"), 
                                    bg='#1e3d59', fg='white', padx=10, pady=10)
        control_frame.pack(fill=tk.BOTH, expand=True)
        
        # 余额信息
        info_frame = tk.Frame(control_frame, bg='#1e3d59')
        info_frame.pack(fill=tk.X, pady=10)
        
        self.balance_label = tk.Label(info_frame, text=f"余额: ${self.balance}", 
                                     font=("Arial", 14, "bold"), fg='white', bg='#1e3d59')
        self.balance_label.pack(side=tk.LEFT, padx=10)
        
        # 下注信息
        bet_info_frame = tk.Frame(control_frame, bg='#1e3d59')
        bet_info_frame.pack(fill=tk.X, pady=5)
        
        self.current_bet_label = tk.Label(bet_info_frame, text=f"本局下注: ${self.current_bet}", 
                                        font=("Arial", 12), fg='white', bg='#1e3d59')
        self.current_bet_label.pack(side=tk.LEFT, padx=10)
        
        self.last_win_label = tk.Label(bet_info_frame, text=f"上局获胜: ${self.last_win}", 
                                     font=("Arial", 12), fg='white', bg='#1e3d59')
        self.last_win_label.pack(side=tk.LEFT, padx=10)
        
        # 筹码选择
        chip_frame = tk.Frame(control_frame, bg='#1e3d59')
        chip_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(chip_frame, text="筹码选择", font=("Arial", 12, "bold"), 
                fg='white', bg='#1e3d59').pack(anchor=tk.W, pady=5)
        
        # 筹码值
        self.chip_values = [10, 25, 50, 100, 500, 1000, 5000]
        self.chip_buttons = []
        
        chips_frame = tk.Frame(chip_frame, bg='#1e3d59')
        chips_frame.pack(fill=tk.X)
        
        for value in self.chip_values:
            btn = tk.Button(chips_frame, text=f"${value}", font=("Arial", 10, "bold"),
                          command=lambda v=value: self.set_bet_amount(v),
                          bg='#f39c12', fg='black', width=6, height=1)
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)
        
        # 旋转按钮
        spin_btn = tk.Button(control_frame, text="旋转轮盘 (Enter)", font=("Arial", 14, "bold"),
                           bg='#27ae60', fg='white', command=self.spin_wheel)
        spin_btn.pack(fill=tk.X, pady=10)
        
        # 清除按钮
        clear_btn = tk.Button(control_frame, text="清除下注", font=("Arial", 14, "bold"),
                            bg='#e74c3c', fg='white', command=self.clear_bets)
        clear_btn.pack(fill=tk.X, pady=5)
        
        # 历史记录
        history_frame = tk.LabelFrame(control_frame, text="历史记录", font=("Arial", 12, "bold"),
                                    bg='#1e3d59', fg='white')
        history_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.history_canvas = tk.Canvas(history_frame, bg='#1e3d59', highlightthickness=0)
        self.history_canvas.pack(fill=tk.BOTH, expand=True)
        
        self.history_container = tk.Frame(self.history_canvas, bg='#1e3d59')
        self.history_canvas.create_window((0, 0), window=self.history_container, anchor=tk.NW)
        
        # 添加滚动条
        scrollbar = tk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定事件
        self.history_container.bind("<Configure>", self.on_frame_configure)
    
    def on_frame_configure(self, event):
        """更新滚动区域"""
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
    
    def create_bet_area(self, parent):
        """创建标准轮盘下注区域布局"""
        # 创建主要下注区域框架
        bet_area = tk.Canvas(parent, bg='#2c3e50', highlightthickness=0)
        bet_area.pack(fill=tk.BOTH, expand=True)
        
        # 内场区域 - 数字格
        inner_field = tk.Frame(bet_area, bg='#2c3e50', padx=10, pady=10)
        inner_field.place(relx=0.5, rely=0.3, anchor=tk.CENTER, width=800, height=400)
        
        # 0和00区域 - 顶部
        zero_frame = tk.Frame(inner_field, bg='#2c3e50')
        zero_frame.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0, 5))
        
        # 0按钮
        zero_btn = tk.Button(zero_frame, text="0", font=("Arial", 14, "bold"),
                           bg='#2ecc71', fg='white', width=4,
                           command=lambda: self.place_bet("直注", 35, 0))
        zero_btn.pack(side=tk.LEFT, padx=(0, 2))
        
        # 00按钮
        dzero_btn = tk.Button(zero_frame, text="00", font=("Arial", 14, "bold"),
                            bg='#2ecc71', fg='white', width=4,
                            command=lambda: self.place_bet("直注", 35, 00))
        dzero_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        # 0和00分注 - 在0和00之间
        split_frame = tk.Frame(zero_frame, bg='#2c3e50', width=10, height=40)
        split_frame.pack(side=tk.LEFT, fill=tk.Y)
        split_frame.bind("<Button-1>", lambda e: self.place_bet("分注", 17, "0-00"))
        split_label = tk.Label(split_frame, text="", bg='#3498db', cursor="hand2")
        split_label.pack(fill=tk.BOTH, expand=True)
        split_label.bind("<Button-1>", lambda e: self.place_bet("分注", 17, "0-00"))
        
        # 数字网格
        grid_frame = tk.Frame(inner_field, bg='#2c3e50')
        grid_frame.grid(row=1, column=0, columnspan=3, sticky='nsew')
        
        # 列标题
        col_frame = tk.Frame(grid_frame, bg='#2c3e50')
        col_frame.pack(fill=tk.X)
        
        # 数字布局 - 三列
        columns = [
            [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],  # 第一列
            [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],  # 第二列
            [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]   # 第三列
        ]
        
        # 红黑数字定义
        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        
        # 创建数字网格
        for col_idx, col_nums in enumerate(columns):
            col_frame = tk.Frame(grid_frame, bg='#2c3e50')
            col_frame.pack(side=tk.LEFT, fill=tk.Y, padx=1)
            
            for row_idx, num in enumerate(col_nums):
                color = '#e74c3c' if num in red_numbers else '#1a1a1a'  # 红/黑
                
                num_frame = tk.Frame(col_frame, bg=color, width=30, height=30)
                num_frame.grid(row=row_idx, column=0, sticky='nsew', padx=1, pady=1)
                
                num_btn = tk.Button(num_frame, text=str(num), font=("Arial", 10, "bold"),
                                  bg=color, fg='white', width=3, height=1, relief='flat',
                                  command=lambda n=num: self.place_bet("直注", 35, n))
                num_btn.pack(fill=tk.BOTH, expand=True)
                
                # 添加分注区域 (数字之间)
                if row_idx < len(col_nums) - 1:
                    split_frame = tk.Frame(col_frame, bg='#2c3e50', width=30, height=5)
                    split_frame.grid(row=row_idx, column=1, sticky='ew', pady=1)
                    split_frame.bind("<Button-1>", lambda e, n1=num, n2=col_nums[row_idx+1]: 
                                    self.place_bet("分注", 17, f"{n1}-{n2}"))
                
                # 添加街注区域 (行之间)
                if col_idx < len(columns) - 1 and row_idx < len(col_nums):
                    street_frame = tk.Frame(grid_frame, bg='#2c3e50', width=5, height=30)
                    street_frame.place(x=col_idx*60 + 55, y=row_idx*30 + 40)
                    street_frame.bind("<Button-1>", lambda e, r=row_idx: 
                                     self.place_bet("街注", 11, f"行{r+1}"))
        
        # 五数注 (0,00,1,2,3) - 在0/00行和第一行之间
        five_num_frame = tk.Frame(inner_field, bg='#9b59b6', width=100, height=20)
        five_num_frame.place(relx=0.5, rely=0.2, anchor=tk.CENTER)
        five_num_btn = tk.Button(five_num_frame, text="五数注 (0,00,1,2,3)", font=("Arial", 10),
                               bg='#9b59b6', fg='white', relief='flat',
                               command=lambda: self.place_bet("五数注", 6, "0-00-1-2-3"))
        five_num_btn.pack(fill=tk.BOTH, expand=True)
        
        # 外场区域 - 底部
        outer_field = tk.Frame(bet_area, bg='#2c3e50')
        outer_field.place(relx=0.5, rely=0.75, anchor=tk.CENTER, width=800, height=100)
        
        # 左侧外场区域
        left_outer = tk.Frame(outer_field, bg='#2c3e50')
        left_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # 1-18 / 19-36
        low_high_frame = tk.Frame(left_outer, bg='#2c3e50')
        low_high_frame.pack(fill=tk.X, pady=5)
        
        low_btn = tk.Button(low_high_frame, text="1-18", font=("Arial", 12, "bold"),
                          bg='#f39c12', fg='white', width=10,
                          command=lambda: self.place_bet("大小", 1, "小"))
        low_btn.pack(side=tk.LEFT, padx=5)
        
        high_btn = tk.Button(low_high_frame, text="19-36", font=("Arial", 12, "bold"),
                           bg='#f39c12', fg='white', width=10,
                           command=lambda: self.place_bet("大小", 1, "大"))
        high_btn.pack(side=tk.LEFT, padx=5)
        
        # 单/双
        odd_even_frame = tk.Frame(left_outer, bg='#2c3e50')
        odd_even_frame.pack(fill=tk.X, pady=5)
        
        odd_btn = tk.Button(odd_even_frame, text="单", font=("Arial", 12, "bold"),
                          bg='#3498db', fg='white', width=10,
                          command=lambda: self.place_bet("单/双", 1, "单"))
        odd_btn.pack(side=tk.LEFT, padx=5)
        
        even_btn = tk.Button(odd_even_frame, text="双", font=("Arial", 12, "bold"),
                           bg='#3498db', fg='white', width=10,
                           command=lambda: self.place_bet("单/双", 1, "双"))
        even_btn.pack(side=tk.LEFT, padx=5)
        
        # 中间外场区域
        middle_outer = tk.Frame(outer_field, bg='#2c3e50')
        middle_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # 打数
        dozen_frame = tk.Frame(middle_outer, bg='#2c3e50')
        dozen_frame.pack(fill=tk.BOTH, expand=True)
        
        for i, text in enumerate(["1-12", "13-24", "25-36"]):
            btn = tk.Button(dozen_frame, text=text, font=("Arial", 12, "bold"),
                          bg='#9b59b6', fg='white', width=10,
                          command=lambda d=i+1: self.place_bet("打数", 2, f"第{d}打"))
            btn.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        # 列注
        column_frame = tk.Frame(middle_outer, bg='#2c3e50')
        column_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        for i, text in enumerate(["2:1", "2:1", "2:1"]):
            btn = tk.Button(column_frame, text=text, font=("Arial", 12, "bold"),
                          bg='#34495e', fg='white', width=10,
                          command=lambda c=i+1: self.place_bet("列注", 2, f"第{c}列"))
            btn.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        # 右侧外场区域
        right_outer = tk.Frame(outer_field, bg='#2c3e50')
        right_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # 红/黑
        red_black_frame = tk.Frame(right_outer, bg='#2c3e50')
        red_black_frame.pack(fill=tk.BOTH, expand=True)
        
        red_btn = tk.Button(red_black_frame, text="红", font=("Arial", 12, "bold"),
                          bg='#e74c3c', fg='white', height=3,
                          command=lambda: self.place_bet("红/黑", 1, "红"))
        red_btn.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        
        black_btn = tk.Button(red_black_frame, text="黑", font=("Arial", 12, "bold"),
                            bg='#1a1a1a', fg='white', height=3,
                            command=lambda: self.place_bet("红/黑", 1, "黑"))
        black_btn.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
    
    def set_bet_amount(self, amount):
        """设置当前下注金额"""
        self.bet_amount = amount
        
        # 更新按钮状态
        for btn in self.chip_buttons:
            if int(btn['text'].replace('$', '')) == amount:
                btn.config(bg='#f1c40f', relief=tk.SUNKEN)
            else:
                btn.config(bg='#f39c12', relief=tk.RAISED)
    
    def place_bet(self, bet_type, odds, param):
        """放置下注"""
        if not self.accept_bets:
            messagebox.showinfo("提示", "本轮下注已结束，请等待轮盘停止")
            return
            
        if self.bet_amount > self.balance:
            messagebox.showwarning("余额不足", "您的余额不足以进行此次下注")
            return
            
        # 创建下注记录键
        bet_key = f"{bet_type}-{param}"
        
        # 更新下注金额
        if bet_key in self.bets:
            self.bets[bet_key] += self.bet_amount
        else:
            self.bets[bet_key] = self.bet_amount
            
        # 更新余额和下注总额
        self.balance -= self.bet_amount
        self.current_bet += self.bet_amount
        self.update_display()
        
        # 显示下注确认
        bet_name = f"{bet_type} ({param})" if param else bet_type
        # messagebox.showinfo("下注成功", f"您已下注 ${self.bet_amount} 于 {bet_name}")
    
    def clear_bets(self):
        """清除所有下注"""
        if not self.accept_bets:
            return
            
        # 返还所有下注金额
        total_bet = sum(self.bets.values())
        self.balance += total_bet
        self.current_bet = 0
        self.bets = {}
        self.update_display()
        
        messagebox.showinfo("清除成功", "所有下注已被清除")
    
    def spin_wheel(self):
        """旋转轮盘"""
        if not self.bets:
            messagebox.showwarning("无法旋转", "请先下注")
            return
            
        if not self.accept_bets:
            return
            
        self.accept_bets = False
        
        # 随机生成中奖数字
        winning_number = random.randint(0, 37)  # 0-36和00(用37表示)
        
        # 创建旋转窗口
        RouletteSpinWindow(self.root, winning_number, self.on_spin_complete)
    
    def on_spin_complete(self, winning_number):
        """轮盘旋转完成，计算结果"""
        # 确定赢家
        winnings = self.calculate_winnings(winning_number)
        
        # 更新余额
        self.balance += winnings
        self.last_win = winnings - self.current_bet if winnings > 0 else 0
        
        # 重置下注
        self.current_bet = 0
        self.bets = {}
        
        # 更新显示
        self.update_display()
        
        # 添加历史记录
        self.add_to_history(winning_number)
        
        # 显示结果
        num_text = "00" if winning_number == 37 else str(winning_number)
        result_text = f"本轮结果: {num_text}\n"
        
        if winnings > 0:
            result_text += f"恭喜您赢得 ${winnings - self.current_bet}!"
            messagebox.showinfo("游戏结果", result_text)
        else:
            result_text += "很遗憾，本轮您没有赢钱。"
            messagebox.showinfo("游戏结果", result_text)
        
        # 允许下一轮下注
        self.accept_bets = True
    
    def calculate_winnings(self, winning_number):
        """计算赢得的金额"""
        winnings = 0
        num_text = "00" if winning_number == 37 else str(winning_number)
        
        # 红黑数字定义
        red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
        
        # 检查每个下注
        for bet_key, amount in self.bets.items():
            bet_type, param = bet_key.split('-', 1)
            
            # 直注
            if bet_type == "直注":
                if (winning_number == 0 and param == "0") or (winning_number == 37 and param == "00"):
                    winnings += amount * 36  # 35:1 + 本金
                elif str(winning_number) == param:
                    winnings += amount * 36
            
            # 分注 (0/00)
            elif bet_type == "分注" and param == "0-00":
                if winning_number == 0 or winning_number == 37:
                    winnings += amount * 18  # 17:1 + 本金
                    
            # 分注 (数字之间)
            elif bet_type == "分注" and '-' in param:
                nums = param.split('-')
                if (winning_number == int(nums[0]) or winning_number == int(nums[1])):
                    winnings += amount * 18
                    
            # 街注 (一行三个数字)
            elif bet_type == "街注" and param.startswith("行"):
                row = int(param[1:])
                start_num = (row-1)*3 + 1
                if winning_number in [start_num, start_num+1, start_num+2]:
                    winnings += amount * 12  # 11:1 + 本金
            
            # 五数注 (0,00,1,2,3)
            elif bet_type == "五数注" and param == "0-00-1-2-3":
                if winning_number in [0, 37, 1, 2, 3]:
                    winnings += amount * 7  # 6:1 + 本金
            
            # 列注
            elif bet_type == "列注":
                col = int(param[1])  # 第1列, 第2列, 第3列
                if winning_number > 0 and winning_number <= 36:
                    # 确定数字属于哪一列
                    if col == 1 and winning_number % 3 == 1:  # 1,4,7,...
                        winnings += amount * 3  # 2:1 + 本金
                    elif col == 2 and winning_number % 3 == 2:  # 2,5,8,...
                        winnings += amount * 3
                    elif col == 3 and winning_number % 3 == 0:  # 3,6,9,...
                        winnings += amount * 3
            
            # 红/黑
            elif bet_type == "红/黑" and winning_number > 0 and winning_number <= 36:
                if param == "红" and winning_number in red_numbers:
                    winnings += amount * 2  # 1:1 + 本金
                elif param == "黑" and winning_number not in red_numbers:
                    winnings += amount * 2
            
            # 单/双
            elif bet_type == "单/双" and winning_number > 0 and winning_number <= 36:
                if param == "单" and winning_number % 2 == 1:
                    winnings += amount * 2
                elif param == "双" and winning_number % 2 == 0:
                    winnings += amount * 2
            
            # 大小
            elif bet_type == "大小" and winning_number > 0 and winning_number <= 36:
                if param == "小" and 1 <= winning_number <= 18:
                    winnings += amount * 2
                elif param == "大" and 19 <= winning_number <= 36:
                    winnings += amount * 2
            
            # 打数
            elif bet_type == "打数" and winning_number > 0 and winning_number <= 36:
                dozen = int(param[1])  # 第1打, 第2打, 第3打
                if dozen == 1 and 1 <= winning_number <= 12:
                    winnings += amount * 3  # 2:1 + 本金
                elif dozen == 2 and 13 <= winning_number <= 24:
                    winnings += amount * 3
                elif dozen == 3 and 25 <= winning_number <= 36:
                    winnings += amount * 3
        
        return winnings
    
    def add_to_history(self, winning_number):
        """添加历史记录"""
        # 创建历史记录框架
        frame = tk.Frame(self.history_container, bg='#2c3e50', padx=5, pady=5, relief=tk.RIDGE, bd=1)
        frame.pack(fill=tk.X, padx=2, pady=2)
        
        # 显示数字
        num_text = "00" if winning_number == 37 else str(winning_number)
        num_label = tk.Label(frame, text=num_text, font=("Arial", 14, "bold"), 
                           bg='#2ecc71' if winning_number in [0, 37] else 
                              '#e74c3c' if winning_number in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36] else 
                              '#1a1a1a',
                           fg='white', width=4)
        num_label.pack(side=tk.LEFT, padx=10)
        
        # 显示红/黑
        if winning_number in [0, 37]:
            color_text = "绿"
            color_bg = '#2ecc71'
        elif winning_number in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]:
            color_text = "红"
            color_bg = '#e74c3c'
        else:
            color_text = "黑"
            color_bg = '#1a1a1a'
            
        color_label = tk.Label(frame, text=color_text, font=("Arial", 12), 
                             bg=color_bg, fg='white', width=4)
        color_label.pack(side=tk.LEFT, padx=10)
        
        # 显示单/双
        if winning_number in [0, 37]:
            parity_text = "-"
            parity_bg = '#2c3e50'
        elif winning_number % 2 == 0:
            parity_text = "双"
            parity_bg = '#3498db'
        else:
            parity_text = "单"
            parity_bg = '#3498db'
            
        parity_label = tk.Label(frame, text=parity_text, font=("Arial", 12), 
                              bg=parity_bg, fg='white', width=4)
        parity_label.pack(side=tk.LEFT, padx=10)
        
        # 显示大小
        if winning_number in [0, 37]:
            size_text = "-"
            size_bg = '#2c3e50'
        elif winning_number <= 18:
            size_text = "小"
            size_bg = '#f39c12'
        else:
            size_text = "大"
            size_bg = '#f39c12'
            
        size_label = tk.Label(frame, text=size_text, font=("Arial", 12), 
                            bg=size_bg, fg='white', width=4)
        size_label.pack(side=tk.LEFT, padx=10)
        
        # 更新历史记录容器
        self.history_container.update_idletasks()
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
        
        # 保存记录
        self.history.append({
            "number": winning_number,
            "color": color_text,
            "parity": parity_text,
            "size": size_text
        })
    
    def update_display(self):
        """更新显示信息"""
        self.balance_label.config(text=f"余额: ${self.balance}")
        self.current_bet_label.config(text=f"本局下注: ${self.current_bet}")
        self.last_win_label.config(text=f"上局获胜: ${self.last_win}")


def main():
    root = tk.Tk()
    game = RouletteGame(root)
    root.mainloop()

if __name__ == "__main__":
    main()