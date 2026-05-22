import tkinter as tk
from tkinter import ttk, messagebox
import secrets
import time
from PIL import Image, ImageTk, ImageDraw
import os, json, sys
import random

# 获取当前文件所在目录并定位到A_Tools文件夹
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # 上一级目录
a_tools_dir = os.path.join(parent_dir, 'A_Tools')

# 将A_Tools目录添加到系统路径
if a_tools_dir not in sys.path:
    sys.path.append(a_tools_dir)

def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')

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

class Dice:
    """骰子类，生成1-6的随机数（保留用于初始随机种子）"""
    def __init__(self):
        pass

    def roll(self):
        return secrets.randbelow(6) + 1

class DiceAnimationWindow:
    @staticmethod
    def next_dice_value(current):
        """根据当前骰子点数，生成下一个骰子点数（排除当前值和对面值）"""
        opposite = 7 - current
        candidates = [x for x in range(1, 7) if x != current and x != opposite]
        return secrets.choice(candidates)

    def __init__(self, game, callback, init_dice1, init_dice2):
        self.game = game
        self.callback = callback
        self.cur_dice1 = init_dice1
        self.cur_dice2 = init_dice2

        self.window = tk.Toplevel(game.root)
        self.window.title("骰子摇动中...")
        self.window.geometry("500x400")
        self.window.resizable(0, 0)
        self.window.configure(bg='#1e3d59')
        self.window.grab_set()

        self.window.protocol("WM_DELETE_WINDOW", self.do_nothing)

        # 窗口居中
        parent_x = game.root.winfo_x()
        parent_y = game.root.winfo_y()
        parent_width = game.root.winfo_width()
        parent_height = game.root.winfo_height()
        x = parent_x + (parent_width - 500) // 2
        y = parent_y + (parent_height - 400) // 2
        self.window.geometry(f"500x400+{x}+{y}")

        # 生成大号骰子图片
        self.dice_images = []
        for i in range(1, 7):
            img = Image.new('RGB', (120, 120), '#e8d6b3')
            self.draw_dice(img, i)
            self.dice_images.append(ImageTk.PhotoImage(img))

        self.dice_container = tk.Frame(self.window, bg='#1e3d59')
        self.dice_container.pack(pady=50)

        self.dice_labels = []
        for _ in range(2):
            lbl = tk.Label(self.dice_container, image=self.dice_images[0], bg='#1e3d59', borderwidth=0)
            lbl.pack(side=tk.LEFT, padx=20)
            self.dice_labels.append(lbl)

        # 初始显示起始骰子
        self.dice_labels[0].config(image=self.dice_images[self.cur_dice1-1])
        self.dice_labels[1].config(image=self.dice_images[self.cur_dice2-1])

        self.status_label = tk.Label(self.window, text="骰子摇动中...", font=("Arial", 18), fg='white', bg='#1e3d59')
        self.status_label.pack(pady=20)

        self.progress = ttk.Progressbar(self.window, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.pack(pady=10)

        self.animation_start_time = time.time()
        self.final_dice = None
        self.result_frame = None   # 用于存放最终结果的框架

        # 计算骰子转动时间：3100到4000毫秒
        total_milliseconds = secrets.randbelow(901) + 3100
        self.total_duration = total_milliseconds / 1000.0

        self.animate_dice()

    def do_nothing(self):
        """忽略关闭窗口的请求"""
        pass

    def draw_dice(self, img, num):
        draw = ImageDraw.Draw(img)
        size = img.size[0]
        dot_size = max(2, size // 10)
        draw.rectangle([0, 0, size-1, size-1], outline='#333', width=1)
        dot_color = '#333'
        dot_positions = {
            1: [(size//2, size//2)],
            2: [(size//4, size//4), (3*size//4, 3*size//4)],
            3: [(size//4, size//4), (size//2, size//2), (3*size//4, 3*size//4)],
            4: [(size//4, size//4), (3*size//4, size//4), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            5: [(size//4, size//4), (3*size//4, size//4), (size//2, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            6: [(size//4, size//4), (3*size//4, size//4), (size//4, size//2), (3*size//4, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)]
        }
        for pos in dot_positions[num]:
            draw.ellipse([pos[0]-dot_size, pos[1]-dot_size, pos[0]+dot_size, pos[1]+dot_size], fill=dot_color)

    def animate_dice(self):
        elapsed = time.time() - self.animation_start_time
        if elapsed < 5:  # 5秒快速变化
            self.progress['value'] = min(100, (elapsed / 5) * 100)

            # 根据规则生成下一组骰子点数
            self.cur_dice1 = self.next_dice_value(self.cur_dice1)
            self.cur_dice2 = self.next_dice_value(self.cur_dice2)

            # 更新显示
            self.dice_labels[0].config(image=self.dice_images[self.cur_dice1-1])
            self.dice_labels[1].config(image=self.dice_images[self.cur_dice2-1])

            # 保存最终结果（当接近5秒时记录）
            if elapsed > 4.9:
                self.final_dice = (self.cur_dice1, self.cur_dice2)

            self.window.after(100, self.animate_dice)

        elif elapsed < 6:  # 1秒静止显示最终结果
            if self.final_dice is None:
                self.final_dice = (self.cur_dice1, self.cur_dice2)

            # 确保显示最终结果
            self.dice_labels[0].config(image=self.dice_images[self.final_dice[0]-1])
            self.dice_labels[1].config(image=self.dice_images[self.final_dice[1]-1])
            self.status_label.config(text="骰子停止中...")
            self.window.after(100, self.animate_dice)

        elif elapsed < 9:  # 3秒显示结果（使用图片形式）
            total = sum(self.final_dice)

            # 如果尚未创建结果框架，则创建
            if self.result_frame is None:
                # 隐藏原来的状态标签
                self.status_label.pack_forget()

                self.result_frame = tk.Frame(self.window, bg='#1e3d59')
                self.result_frame.pack(pady=20)

                # 获取小骰子图片（30x30）
                small_dice_images = self.game.dice_images_small

                # 第一个骰子图片
                self.dice_img1 = tk.Label(self.result_frame, image=small_dice_images[self.final_dice[0]-1], bg='#1e3d59')
                self.dice_img1.pack(side=tk.LEFT, padx=5)

                # 加号
                plus_label = tk.Label(self.result_frame, text="+", font=("Arial", 14, "bold"), fg='white', bg='#1e3d59')
                plus_label.pack(side=tk.LEFT, padx=5)

                # 第二个骰子图片
                self.dice_img2 = tk.Label(self.result_frame, image=small_dice_images[self.final_dice[1]-1], bg='#1e3d59')
                self.dice_img2.pack(side=tk.LEFT, padx=5)

                # 等号
                equal_label = tk.Label(self.result_frame, text="=", font=("Arial", 14, "bold"), fg='white', bg='#1e3d59')
                equal_label.pack(side=tk.LEFT, padx=5)

                # 总和数字
                total_label = tk.Label(self.result_frame, text=str(total), font=("Arial", 16, "bold"), fg='yellow', bg='#1e3d59')
                total_label.pack(side=tk.LEFT, padx=5)

            self.window.after(100, self.animate_dice)

        else:
            self.window.destroy()
            if self.final_dice is not None:
                self.callback(self.final_dice)
            else:
                self.callback()

class CrapsGame:
    def __init__(self, root, username=None, initial_balance=10000):
        self.root = root
        self.username = username
        self.accept_bets = True
        self.game_state = "come_out"  # "come_out" 或 "point"
        self.point_number = None
        self.shooter_active = False
        self.place_bets_on = True  # Place Bets开关状态
        self.new_come_out_round = True  # 标记是否是新进入COME OUT阶段
        self.showing_come_data = True  # 默认显示Come Data

        # 记录上一局掷出的骰子结果（用于下一局的起始种子）
        self.last_dice_pair = None

        # 配置 Notebook 样式
        style = ttk.Style()
        style.configure('TNotebook.Tab', font=('Arial', 12, 'bold'))

        self.root.title("花旗骰 Craps")
        self.root.geometry("1400x800+50+0")
        self.root.resizable(0,0)
        self.root.configure(bg='#0a5f38')
        self.enter_binding = None

        self.dice1 = Dice()
        self.dice2 = Dice()

        # 使用传入的初始余额
        self.balance = initial_balance
        self.final_balance = initial_balance
        self.current_bet = 0
        self.bet_amount = 100
        self.last_win = 0

        # 花旗骰下注类型
        self.multi_roll_bets = {
            "pass_line": 0,
            "dont_pass": 0,
            "come": 0,
            "dont_come": 0,
            "big_6": 0,
            "big_8": 0,
            "place_4": 0,
            "place_5": 0,
            "place_6": 0,
            "place_8": 0,
            "place_9": 0,
            "place_10": 0
        }

        # 用于跟踪本轮新增的多轮下注
        self.current_round_multi_roll_bets = {
            "pass_line": 0,
            "dont_pass": 0,
            "come": 0,
            "dont_come": 0,
            "big_6": 0,
            "big_8": 0,
            "place_4": 0,
            "place_5": 0,
            "place_6": 0,
            "place_8": 0,
            "place_9": 0,
            "place_10": 0
        }

        self.single_roll_bets = {
            "field": 0,
            "any_craps": 0,
            "any_7": 0,
            "horn_2": 0,
            "horn_3": 0,
            "horn_11": 0,
            "horn_12": 0,
            "combo_11": 0,
            "combo_12": 0,
            "combo_22": 0,
            "combo_33": 0,
            "combo_44": 0,
            "combo_55": 0,
            "combo_56": 0,
            "combo_66": 0
        }

        # 存储每个多轮下注的点数
        self.come_points = {}
        self.dont_come_points = {}

        # 创建骰子图片
        self.dice_images_large = []
        self.dice_images_small = []
        self.dice_images_mini = []
        for i in range(1, 7):
            # 大尺寸骰子
            img_large = Image.new('RGB', (70, 70), '#e8d6b3')
            self.draw_dice(img_large, i)
            self.dice_images_large.append(ImageTk.PhotoImage(img_large))

            # 小尺寸骰子
            img_small = Image.new('RGB', (30, 30), '#e8d3b3')
            self.draw_dice(img_small, i)
            self.dice_images_small.append(ImageTk.PhotoImage(img_small))

            # 迷你尺寸骰子
            img_mini = Image.new('RGB', (20, 20), '#e8d3b3')
            self.draw_dice(img_mini, i)
            self.dice_images_mini.append(ImageTk.PhotoImage(img_mini))

        # 筹码值与颜色
        self.chip_values = [
            ('25',   '#00ff00'),
            ('100',  '#000000'),
            ('200',  '#0000ff'),
            ('500',  '#FF7DDA'),
            ('1K',   '#ffffff'),
            ('2K',   '#0000ff'),
            ('5K',   '#ff0000'),
            ('10K',  '#800080'),
            ('20K',  '#ffa500'),
            ('50K',  '#006400')
        ]
        self.chips = [25, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]
        self.history = []
        self.chip_widgets = []

        self.create_widgets()
        self.root.bind('<Return>', lambda event: self.roll_dice())
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.update_bet_areas_state()

    def on_window_close(self):
        """窗口关闭时更新余额到JSON"""
        self.final_balance = self.balance
        if self.username:
            update_balance_in_json(self.username, self.balance)
        self.root.destroy()

    def draw_dice(self, img, num):
        draw = ImageDraw.Draw(img)
        size = img.size[0]
        dot_size = max(2, size // 10)
        draw.rectangle([0, 0, size-1, size-1], outline='#333', width=1)
        dot_color = '#333'
        dot_positions = {
            1: [(size//2, size//2)],
            2: [(size//4, size//4), (3*size//4, 3*size//4)],
            3: [(size//4, size//4), (size//2, size//2), (3*size//4, 3*size//4)],
            4: [(size//4, size//4), (3*size//4, size//4), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            5: [(size//4, size//4), (3*size//4, size//4), (size//2, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            6: [(size//4, size//4), (3*size//4, size//4), (size//4, size//2), (3*size//4, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)]
        }
        for pos in dot_positions[num]:
            draw.ellipse([pos[0]-dot_size, pos[1]-dot_size, pos[0]+dot_size, pos[1]+dot_size], fill=dot_color)

    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg='#0a5f38')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 左侧游戏区域
        left_frame = tk.Frame(main_frame, bg='#0a5f38', width=1000)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 右侧控制面板
        self.right_notebook = ttk.Notebook(main_frame, width=400)
        self.right_notebook.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)

        # 控制标签页
        control_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(control_tab, text='控制面板')
        control_frame = tk.Frame(control_tab, bg='#D0E7FF')
        control_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 游戏状态显示
        self.state_frame = tk.Frame(left_frame, bg='#1e3d59', padx=10, pady=5)
        self.state_frame.pack(fill=tk.X, padx=10, pady=10)

        self.state_label = tk.Label(self.state_frame, text="阶段: COME OUT",
                                  font=("Arial", 16, "bold"), fg='white', bg='#1e3d59')
        self.state_label.pack(side=tk.LEFT)

        self.point_label = tk.Label(self.state_frame, text="点数: -",
                                  font=("Arial", 16, "bold"), fg='white', bg='#1e3d59')
        self.point_label.pack(side=tk.LEFT, padx=20)

        # Shooter状态显示
        self.shooter_label = tk.Label(self.state_frame, text="Shooter: 未激活",
                                    font=("Arial", 14), fg='#FFD700', bg='#1e3d59')
        self.shooter_label.pack(side=tk.LEFT, padx=20)

        # 创建花旗骰赌桌
        self.create_craps_table(left_frame)

        # 控制面板内容
        info_frame = tk.Frame(control_frame, bg='#D0E7FF')
        info_frame.pack(fill=tk.X, pady=10)

        self.balance_label = tk.Label(info_frame, text=f"餘額: ${self.balance:.2f}",
                                     font=("Arial", 14, "bold"), fg='black', bg='#D0E7FF')
        self.balance_label.pack(side=tk.LEFT, padx=10)

        # 筹码区
        chip_frame = tk.Frame(control_frame, bg='#D0E7FF')
        chip_frame.pack(fill=tk.X, pady=(10, 5))

        tk.Label(chip_frame, text="筹码选择", font=("Arial", 14, "bold"),
                fg='black', bg='#D0E7FF').pack(anchor=tk.W, pady=5)

        row1 = tk.Frame(chip_frame, bg='#D0E7FF')
        row1.pack(fill=tk.X, pady=5)
        for idx, (label, color) in enumerate(self.chip_values[:5]):
            value = self.chips[idx]
            canvas = tk.Canvas(row1, width=50, height=50, bg='#D0E7FF', highlightthickness=0)
            canvas.pack(side=tk.LEFT, padx=10)
            oval_id = canvas.create_oval(5, 5, 45, 45, fill=color, outline='#333', width=2)

            text_color = 'white' if label in ['100', '200', '2K', '5K', '10K', '50K'] else 'black'
            canvas.create_text(25, 25, text=label, font=("Arial", 10, "bold"), fill=text_color)

            canvas.bind("<Button-1>", lambda e, c=value: self.set_bet_amount(c))
            self.chip_widgets.append((canvas, oval_id, value))

        row2 = tk.Frame(chip_frame, bg='#D0E7FF')
        row2.pack(fill=tk.X, pady=5)
        for idx, (label, color) in enumerate(self.chip_values[5:]):
            value = self.chips[idx+5]
            canvas = tk.Canvas(row2, width=50, height=50, bg='#D0E7FF', highlightthickness=0)
            canvas.pack(side=tk.LEFT, padx=10)
            oval_id = canvas.create_oval(5, 5, 45, 45, fill=color, outline='#333', width=2)

            text_color = 'white' if label in ['100', '200', '2K', '5K', '10K', '50K'] else 'black'
            canvas.create_text(25, 25, text=label, font=("Arial", 10, "bold"), fill=text_color)

            canvas.bind("<Button-1>", lambda e, c=value: self.set_bet_amount(c))
            self.chip_widgets.append((canvas, oval_id, value))

        # 历史记录
        history_container = tk.Frame(control_frame, bg='#D0E7FF')
        history_container.pack(fill=tk.BOTH, expand=True, pady=(20, 10))

        tk.Label(history_container, text="歷史記錄", font=("Arial", 16, "bold"),
                fg='black', bg='#D0E7FF').pack(anchor=tk.W, pady=5)

        self.history_inner = tk.Frame(history_container, bg='#D0E7FF', height=200)
        self.history_inner.pack(fill=tk.BOTH, expand=True)

        # 添加历史记录标题行
        title_frame = tk.Frame(self.history_inner, bg='#1e3d59', padx=5, pady=3, relief=tk.RAISED, borderwidth=1)
        title_frame.pack(fill=tk.X, padx=2, pady=(0, 5))

        tk.Label(title_frame, text="骰子", font=("Arial", 12, "bold"), fg='white', bg='#1e3d59', width=10).pack(side=tk.LEFT)
        tk.Label(title_frame, text="点数", font=("Arial", 12, "bold"), fg='white', bg='#1e3d59', width=8).pack(side=tk.LEFT)
        tk.Label(title_frame, text="阶段", font=("Arial", 12, "bold"), fg='white', bg='#1e3d59', width=15).pack(side=tk.LEFT)

        # 当前下注信息
        bet_info_frame = tk.Frame(control_frame, bg='#D0E7FF')
        bet_info_frame.pack(fill=tk.X, pady=10)

        self.current_bet_display = tk.Label(bet_info_frame, text="本局下注: $0",
                                          font=("Arial", 14), fg='black', bg='#D0E7FF')
        self.current_bet_display.pack(side=tk.LEFT, padx=10)

        self.last_win_display = tk.Label(bet_info_frame, text="上局获胜: $0.00",
                                       font=("Arial", 14), fg='black', bg='#D0E7FF')
        self.last_win_display.pack(side=tk.LEFT, padx=10)

        # 控制按钮
        btn_frame = tk.Frame(control_frame, bg='#D0E7FF')
        btn_frame.pack(fill=tk.X, pady=10)

        clear_btn = tk.Button(btn_frame, text="清除投注", font=("Arial", 14, "bold"),
                            bg='#ff4444', fg='white', width=10, command=self.clear_bets)
        clear_btn.pack(side=tk.LEFT, padx=10, expand=True)

        roll_btn = tk.Button(btn_frame, text="擲骰子 (Enter)", font=("Arial", 14, "bold"),
                           bg='#FFD700', fg='black', width=15, command=self.roll_dice)
        roll_btn.pack(side=tk.LEFT, padx=10, expand=True)

        # 设置100筹码为默认选中
        self.set_bet_amount(100)

        # 添加游戏规则说明
        self.add_game_rules()

    def add_game_rules(self):
        """添加游戏规则说明"""
        rules_frame = tk.Frame(self.right_notebook, bg='#D0E7FF')
        self.right_notebook.add(rules_frame, text='游戏规则')

        rules_text = """
        花旗骰游戏规则:

        每场花旗骰游戏以"Pass"赌注开始:
        1. Come-out roll阶段:
           - 掷出7或11: Pass赌注赢
           - 掷出2、3或12: Pass赌注输
           - 其他点数: 进入Point阶段

        2. Point阶段:
           - 黑色标记显示为"On"，放置在点数上
           - Shooter继续掷骰直到掷出点数或7
           - 掷出点数: Pass赌注赢
           - 掷出7: Don't Pass赌注赢

        术语:
        - Shooter: 掷骰子的玩家
        - Natural: 掷出7或11
        - Craps: 掷出2、3或12
        - Point: 4、5、6、8、9或10
        - Seven-out: 在Point阶段掷出7

        下注类型:
        - 多轮下注: 持续有效直到满足赢或输的条件
        - 单轮下注: 每次掷骰后立即结算

        赔率:
        - Pass Line/Don't Pass: 1:1
        - 组合下注: 见具体赔率
        """

        rules_label = tk.Label(rules_frame, text=rules_text, font=("Arial", 12),
                             bg='#D0E7FF', fg='black', justify=tk.LEFT)
        rules_label.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

    def create_craps_table(self, parent):
        table_frame = tk.Frame(parent, bg='#0a5f38')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        main_bet_frame = tk.Frame(table_frame, bg='#3e8c47', padx=10, pady=10, relief=tk.RAISED, borderwidth=3)
        main_bet_frame.pack(fill=tk.BOTH, expand=True)

        for i in range(4):
            main_bet_frame.columnconfigure(i, weight=1)
        for i in range(2):
            main_bet_frame.rowconfigure(i, weight=1)

        self.bet_areas = {}

        # 第一行: Pass Line, Come, Come Data, Field
        # Pass Line
        pass_line_frame = tk.Frame(main_bet_frame, bg='#000000', padx=1, pady=1)
        pass_line_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        inner_pass_line = tk.Frame(pass_line_frame, bg='#5cb85c', padx=14, pady=9)
        inner_pass_line.pack(fill=tk.BOTH, expand=True)
        self.create_bet_area(inner_pass_line, "Pass Line", "pass_line", "1:1")

        # Come
        come_frame = tk.Frame(main_bet_frame, bg='#000000', padx=1, pady=1)
        come_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        inner_come = tk.Frame(come_frame, bg='#5bc0de', padx=14, pady=9)
        inner_come.pack(fill=tk.BOTH, expand=True)
        self.create_bet_area(inner_come, "Come", "come", "1:1")

        # Come Data (跨两行的格子)
        come_data_frame = tk.Frame(main_bet_frame, bg='#ffc6fa', padx=1, pady=1, width=250, cursor="hand2")
        come_data_frame.grid(row=0, column=2, rowspan=2, padx=5, pady=5, sticky="nsew")
        come_data_frame.grid_propagate(False)
        come_data_frame.bind("<Button-1>", lambda e: self.switch_come_data_display())

        inner_come_data = tk.Frame(come_data_frame, bg='#ffc6fa', padx=14, pady=9)
        inner_come_data.pack(fill=tk.BOTH, expand=True)
        inner_come_data.bind("<Button-1>", lambda e: self.switch_come_data_display())

        self.come_data_title = tk.Label(inner_come_data, text="Come Data", bg="#ffc6fa", fg='black',
                                        font=("Arial", 14, "bold"), cursor="hand2")
        self.come_data_title.pack(fill=tk.X)
        self.come_data_title.bind("<Button-1>", lambda e: self.switch_come_data_display())

        table_frame_inner = tk.Frame(inner_come_data, bg='#ffa9f8', width=175, height=150, cursor="hand2")
        table_frame_inner.pack(fill=tk.BOTH, expand=True, pady=5)
        table_frame_inner.pack_propagate(False)
        table_frame_inner.bind("<Button-1>", lambda e: self.switch_come_data_display())

        header_frame = tk.Frame(table_frame_inner, bg="#a8d6ff", height=25, cursor="hand2")
        header_frame.pack(fill=tk.X)
        header_frame.bind("<Button-1>", lambda e: self.switch_come_data_display())

        point_header = tk.Label(header_frame, text="点数", font=("Arial", 13, "bold"),
                                bg="#a8d6ff", fg='black', width=7, anchor=tk.CENTER, cursor="hand2")
        point_header.pack(side=tk.LEFT, padx=(0, 1))
        point_header.bind("<Button-1>", lambda e: self.switch_come_data_display())

        bet_header = tk.Label(header_frame, text="下注金额", font=("Arial", 13, "bold"),
                              bg="#a8d6ff", fg='black', width=12, anchor=tk.CENTER, cursor="hand2")
        bet_header.pack(side=tk.LEFT, padx=(1, 0))
        bet_header.bind("<Button-1>", lambda e: self.switch_come_data_display())

        sep_line = tk.Frame(table_frame_inner, height=1, bg='grey', cursor="hand2")
        sep_line.pack(fill=tk.X)
        sep_line.bind("<Button-1>", lambda e: self.switch_come_data_display())

        scroll_frame = tk.Frame(table_frame_inner, bg='#ffc6fa', cursor="hand2")
        scroll_frame.pack(fill=tk.BOTH, expand=True)
        scroll_frame.bind("<Button-1>", lambda e: self.switch_come_data_display())

        row_frames = []
        point_frames = []
        amount_frames = []
        point_labels = []
        sep_lines = []
        amount_labels = []

        points = [4, 5, 6, 8, 9, 10]
        self.come_data_labels = {}
        for point in points:
            row_frame = tk.Frame(scroll_frame, bg="#ffc6fa", height=20, cursor="hand2")
            row_frame.pack(fill=tk.X, pady=0)
            row_frame.pack_propagate(False)
            row_frame.bind("<Button-1>", lambda e, pt=point: self.switch_come_data_display())
            row_frames.append(row_frame)

            point_frame = tk.Frame(row_frame, bg='#ffc6fa', width=65, cursor="hand2")
            point_frame.pack(side=tk.LEFT, fill=tk.Y)
            point_frame.pack_propagate(False)
            point_frame.bind("<Button-1>", lambda e, pt=point: self.switch_come_data_display())
            point_frames.append(point_frame)

            point_label = tk.Label(point_frame, text=f"{point}", font=("Arial", 13),
                                bg='#ffc6fa', fg='black', anchor=tk.CENTER, cursor="hand2")
            point_label.pack(fill=tk.BOTH, expand=True)
            point_label.bind("<Button-1>", lambda e, pt=point: self.switch_come_data_display())
            point_labels.append(point_label)

            sep = tk.Frame(row_frame, width=1, bg='grey', cursor="hand2")
            sep.pack(side=tk.LEFT, fill=tk.Y)
            sep.bind("<Button-1>", lambda e, pt=point: self.switch_come_data_display())
            sep_lines.append(sep)

            amount_frame = tk.Frame(row_frame, bg='#ffc6fa', width=100, cursor="hand2")
            amount_frame.pack(side=tk.LEFT, fill=tk.Y)
            amount_frame.pack_propagate(False)
            amount_frame.bind("<Button-1>", lambda e, pt=point: self.switch_come_data_display())
            amount_frames.append(amount_frame)

            amount_label = tk.Label(amount_frame, text="$0", font=("Arial", 13),
                                    bg='#ffc6fa', fg='blue', anchor=tk.CENTER, cursor="hand2")
            amount_label.pack(fill=tk.BOTH, expand=True)
            amount_label.bind("<Button-1>", lambda e, pt=point: self.switch_come_data_display())
            amount_labels.append(amount_label)

            sep_line_row = tk.Frame(scroll_frame, height=1, bg='grey', cursor="hand2")
            sep_line_row.pack(fill=tk.X)
            sep_line_row.bind("<Button-1>", lambda e, pt=point: self.switch_come_data_display())

            self.come_data_labels[point] = amount_label

        self.come_data_components = {
            "outer_frame": come_data_frame,
            "inner_frame": inner_come_data,
            "table_frame": table_frame_inner,
            "header_frame": header_frame,
            "point_header": point_header,
            "bet_header": bet_header,
            "scroll_frame": scroll_frame,
            "row_frames": row_frames,
            "point_frames": point_frames,
            "amount_frames": amount_frames,
            "point_labels": point_labels,
            "sep_lines": sep_lines,
            "amount_labels": amount_labels
        }

        # Field
        field_frame = tk.Frame(main_bet_frame, bg='#000000', padx=1, pady=1)
        field_frame.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")
        inner_field = tk.Frame(field_frame, bg='#9370db', padx=14, pady=9)
        inner_field.pack(fill=tk.BOTH, expand=True)
        self.create_bet_area(inner_field, "Field", "field", "2/1:1")

        # 第二行: Don't Pass, Don't Come, Big (包含Big6和Big8)
        dont_pass_frame = tk.Frame(main_bet_frame, bg='#000000', padx=1, pady=1)
        dont_pass_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        inner_dont_pass = tk.Frame(dont_pass_frame, bg='#d9534f', padx=14, pady=9)
        inner_dont_pass.pack(fill=tk.BOTH, expand=True)
        self.create_bet_area(inner_dont_pass, "Don't Pass", "dont_pass", "1:1")

        dont_come_frame = tk.Frame(main_bet_frame, bg='#000000', padx=1, pady=1)
        dont_come_frame.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
        inner_dont_come = tk.Frame(dont_come_frame, bg='#f0ad4e', padx=14, pady=9)
        inner_dont_come.pack(fill=tk.BOTH, expand=True)
        self.create_bet_area(inner_dont_come, "Don't Come", "dont_come", "1:1")

        # Big 6 & Big 8
        big_frame = tk.Frame(main_bet_frame, bg='#ff7f50', padx=10, pady=10, relief=tk.RAISED, borderwidth=2)
        big_frame.grid(row=1, column=3, padx=5, pady=5, sticky="nsew")

        big6_frame = tk.Frame(big_frame, bg='#ff7f50', padx=5, pady=5, relief=tk.RAISED, borderwidth=1)
        big6_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.create_bet_area(big6_frame, "Big 6", "big_6", "1:1")

        big8_frame = tk.Frame(big_frame, bg='#ff7f50', padx=5, pady=5, relief=tk.RAISED, borderwidth=1)
        big8_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.create_bet_area(big8_frame, "Big 8", "big_8", "1:1")

        # Place Bets
        place_frame = tk.Frame(main_bet_frame, bg='#20b2aa', padx=10, pady=10, relief=tk.RAISED, borderwidth=2)
        place_frame.grid(row=2, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")

        place_title_frame = tk.Frame(place_frame, bg='#20b2aa')
        place_title_frame.pack(fill=tk.X, pady=(0, 5))

        # Place Bets 按钮 - 带有明显的 On/Off 标志
        self.place_bets_button = tk.Button(
            place_title_frame,
            text="Place Bets: ON",
            font=("Arial", 14, "bold"),
            bg='#2ecc71',  # 绿色表示ON
            fg='white',
            bd=2,
            relief=tk.RAISED,
            command=self.toggle_place_bets,
            disabledforeground='white'
        )
        self.place_bets_button.pack()
        # 初始状态：仅在COME OUT阶段且新的一轮开始时可用
        self.place_bets_button.config(state=tk.DISABLED)

        place_content_frame = tk.Frame(place_frame, bg='#20b2aa')
        place_content_frame.pack(fill=tk.BOTH, expand=True)

        place_bets = [
            ("4", "place_4", "9:5"),
            ("5", "place_5", "7:5"),
            ("6", "place_6", "7:6"),
            ("8", "place_8", "7:6"),
            ("9", "place_9", "7:5"),
            ("10", "place_10", "9:5")
        ]

        for i, (num, bet_type, odds) in enumerate(place_bets):
            container = tk.Frame(place_content_frame, bg='#20b2aa', width=150)
            container.grid(row=0, column=i, padx=2, sticky="nsew")
            container.grid_propagate(False)

            frame = tk.Frame(container, bg="#b2b6b6", padx=5, pady=5, relief=tk.RAISED, borderwidth=1)
            frame.pack(fill=tk.BOTH, expand=True)

            canvas = tk.Canvas(frame, bg=frame.cget('bg'), highlightthickness=0)
            canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
            canvas.bind("<Configure>", lambda e: self.update_bet_areas_state())

            num_label = tk.Label(frame, text=num, font=("Arial", 16, "bold"), bg='#b2b6b6', fg='black')
            num_label.pack(pady=(5, 0))

            odds_label = tk.Label(frame, text=f"{odds}", font=("Arial", 10), bg='#b2b6b6', fg='black')
            odds_label.pack()

            bet_label = tk.Label(frame, text="$0", font=("Arial", 12), bg='#b2b6b6', fg='blue', width=12)
            bet_label.pack(pady=(0, 5))

            frame.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            num_label.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            odds_label.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            bet_label.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            canvas.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))

            frame.bind("<Button-3>", lambda e, bt=bet_type: self.show_bet_rules(bt))
            num_label.bind("<Button-3>", lambda e, bt=bet_type: self.show_bet_rules(bt))
            odds_label.bind("<Button-3>", lambda e, bt=bet_type: self.show_bet_rules(bt))
            bet_label.bind("<Button-3>", lambda e, bt=bet_type: self.show_bet_rules(bt))
            canvas.bind("<Button-3>", lambda e, bt=bet_type: self.show_bet_rules(bt))

            self.bet_areas[bet_type] = {
                "frame": frame,
                "canvas": canvas,
                "label": bet_label,
                "name": num_label,
                "odds": odds_label,
                "cross_line1": None,
                "cross_line2": None,
                "container": container
            }

        # 组合下注区域
        combo_frame = tk.Frame(main_bet_frame, bg='#6aff45', padx=10, pady=10, relief=tk.RAISED, borderwidth=2)
        combo_frame.grid(row=3, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")

        combo_bets = [
            ("1-1", "combo_11", (1, 1), "30:1"),
            ("1-2", "combo_12", (1, 2), "15:1"),
            ("2-2", "combo_22", (2, 2), "7:1"),
            ("3-3", "combo_33", (3, 3), "9:1"),
            ("4-4", "combo_44", (4, 4), "9:1"),
            ("5-5", "combo_55", (5, 5), "7:1"),
            ("5-6", "combo_56", (5, 6), "15:1"),
            ("6-6", "combo_66", (6, 6), "30:1")
        ]

        combo_title_frame = tk.Frame(combo_frame, bg='#6aff45')
        combo_title_frame.pack(fill=tk.X, pady=(0, 5))
        tk.Label(combo_title_frame, text="组合下注", font=("Arial", 14, "bold"),
                bg='#6aff45', fg='#000000').pack()

        combo_content_frame = tk.Frame(combo_frame, bg="#6aff45")
        combo_content_frame.pack(fill=tk.BOTH, expand=True)

        for i, (name, bet_type, dice_pair, odds) in enumerate(combo_bets):
            row = i // 4
            col = i % 4

            if col == 0:
                row_frame = tk.Frame(combo_content_frame, bg='#6aff45')
                row_frame.pack(fill=tk.X, pady=5)

            frame = tk.Frame(row_frame, bg="#4affc0", padx=5, pady=5, relief=tk.RAISED, borderwidth=1)
            frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

            dice_frame = tk.Frame(frame, bg='#4affc0')
            dice_frame.pack(pady=5)

            lbl1 = tk.Label(dice_frame, image=self.dice_images_mini[dice_pair[0]-1], bg='#4affc0')
            lbl1.pack(side=tk.LEFT, padx=2)

            tk.Label(dice_frame, text="-", font=("Arial", 12), bg='#4affc0').pack(side=tk.LEFT, padx=2)

            lbl2 = tk.Label(dice_frame, image=self.dice_images_mini[dice_pair[1]-1], bg='#4affc0')
            lbl2.pack(side=tk.LEFT, padx=2)

            odds_label = tk.Label(frame, text=f"{odds}", font=("Arial", 10), bg='#4affc0', fg='#000000')
            odds_label.pack()

            bet_label = tk.Label(frame, text="$0", font=("Arial", 12), bg='#4affc0', fg='blue')
            bet_label.pack(pady=(0, 5))

            frame.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            odds_label.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            bet_label.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            lbl1.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            lbl2.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))

            frame.bind("<Button-3>", lambda e, bt=bet_type: self.show_bet_rules(bt))

            self.bet_areas[bet_type] = {
                "frame": frame,
                "label": bet_label,
                "odds": odds_label,
                "dice_frame": dice_frame
            }

        # Proposition Bets
        prop_frame = tk.Frame(main_bet_frame, bg='#f08080', padx=10, pady=10, relief=tk.RAISED, borderwidth=2)
        prop_frame.grid(row=0, column=4, rowspan=4, padx=5, pady=5, sticky="nsew")

        prop_bets = [
            ("Any Craps", "any_craps", "7:1"),
            ("Any 7", "any_7", "4:1"),
            ("Horn 2", "horn_2", "30:1"),
            ("Horn 3", "horn_3", "15:1"),
            ("Horn 11", "horn_11", "15:1"),
            ("Horn 12", "horn_12", "30:1")
        ]

        for i, (name, bet_type, odds) in enumerate(prop_bets):
            frame = tk.Frame(prop_frame, bg='#f08080', padx=5, pady=5, relief=tk.RAISED, borderwidth=1)
            frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            name_label = tk.Label(frame, text=name, font=("Arial", 12, "bold"),
                                bg='#f08080', fg='black')
            name_label.pack(pady=(5, 0))

            odds_label = tk.Label(frame, text=f"{odds}", font=("Arial", 10),
                                bg='#f08080', fg='black')
            odds_label.pack()

            bet_label = tk.Label(frame, text="$0", font=("Arial", 12),
                            bg='#f08080', fg='blue')
            bet_label.pack(pady=(0, 5))

            frame.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            name_label.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            odds_label.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            bet_label.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))

            frame.bind("<Button-3>", lambda e, bt=bet_type: self.show_bet_rules(bt))

            self.bet_areas[bet_type] = {
                "frame": frame,
                "label": bet_label,
                "name": name_label,
                "odds": odds_label
            }

        for i in range(5):
            main_bet_frame.columnconfigure(i, weight=1)
        for i in range(4):
            main_bet_frame.rowconfigure(i, weight=1)

    def update_place_bets_button_state(self):
        """更新Place Bets按钮的状态和显示"""
        if self.game_state == "come_out" and self.new_come_out_round:
            self.place_bets_button.config(state=tk.NORMAL)
        else:
            self.place_bets_button.config(state=tk.DISABLED)

        # 更新按钮文本和颜色
        if self.place_bets_on:
            self.place_bets_button.config(text="Place Bets: ON", bg='#2ecc71', fg='white')
        else:
            self.place_bets_button.config(text="Place Bets: OFF", bg='#e74c3c', fg='white')

    def toggle_place_bets(self):
        if self.game_state != "come_out" or not self.new_come_out_round:
            return
        self.place_bets_on = not self.place_bets_on
        self.update_place_bets_button_state()

    def switch_come_data_display(self):
        self.showing_come_data = not self.showing_come_data

        if self.showing_come_data:
            bg_color = '#ffa9f8'
            header_bg = '#a8d6ff'
            title = "Come Data"
        else:
            bg_color = '#a8d6ff'
            header_bg = '#ffa9f8'
            title = "Don't Come Data"

        self.come_data_components["outer_frame"].config(bg=bg_color)
        self.come_data_components["inner_frame"].config(bg=bg_color)
        self.come_data_components["table_frame"].config(bg=bg_color)

        scroll_frame = self.come_data_components["scroll_frame"]
        scroll_frame.config(bg=bg_color)

        self.come_data_components["header_frame"].config(bg=header_bg)
        self.come_data_components["point_header"].config(bg=header_bg)
        self.come_data_components["bet_header"].config(bg=header_bg)

        self.come_data_title.config(text=title, bg=bg_color)

        for row_frame in self.come_data_components["row_frames"]:
            row_frame.config(bg=bg_color)

        for point_frame in self.come_data_components["point_frames"]:
            point_frame.config(bg=bg_color)

        for amount_frame in self.come_data_components["amount_frames"]:
            amount_frame.config(bg=bg_color)

        for point_label in self.come_data_components["point_labels"]:
            point_label.config(bg=bg_color)

        for amount_label in self.come_data_components["amount_labels"]:
            amount_label.config(bg=bg_color)

        self.update_come_data_display()

    def update_come_data_display(self):
        points = [4,5,6,8,9,10]
        for point in points:
            if self.showing_come_data:
                amount = self.come_points.get(point, 0)
            else:
                amount = self.dont_come_points.get(point, 0)
            if point in self.come_data_labels:
                self.come_data_labels[point].config(text=f"${amount}")

    def create_bet_area(self, parent, name, bet_type, odds):
        container = parent

        canvas = tk.Canvas(container, bg=container.cget('bg'), highlightthickness=0)
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        canvas.bind("<Configure>", lambda e: self.update_bet_areas_state())

        self.bet_areas[bet_type] = {
            "frame": container,
            "canvas": canvas,
            "name": None,
            "odds": None,
            "label": None,
            "cross_line1": None,
            "cross_line2": None
        }

        name_label = tk.Label(container, text=name, font=("Arial", 12, "bold"),
                            bg=container.cget('bg'), fg='black')
        name_label.pack(pady=(5, 0))
        self.bet_areas[bet_type]["name"] = name_label

        odds_label = tk.Label(container, text=f"{odds}", font=("Arial", 12),
                            bg=container.cget('bg'), fg='black')
        odds_label.pack()
        self.bet_areas[bet_type]["odds"] = odds_label

        bet_label = tk.Label(container, text="$0", font=("Arial", 12),
                        bg=container.cget('bg'), fg='blue')
        bet_label.pack(pady=(0, 5))
        self.bet_areas[bet_type]["label"] = bet_label

        for widget in [container, canvas, name_label, odds_label, bet_label]:
            widget.bind("<Button-1>", lambda e, bt=bet_type: self.place_bet(bt))
            widget.bind("<Button-3>", lambda e, bt=bet_type: self.show_bet_rules(bt))

    def update_bet_areas_state(self):
        disabled_in_come_out = ["come", "dont_come", "place_4", "place_5", "place_6", "place_8", "place_9", "place_10",
                    "combo_11", "combo_12", "combo_22", "combo_33", "combo_44", "combo_55", "combo_56", "combo_66"]
        disabled_in_point    = ["pass_line", "dont_pass"]

        for bet_type, area in self.bet_areas.items():
            canvas = area.get("canvas")
            if not canvas:
                continue

            if area["cross_line1"]:
                canvas.delete(area["cross_line1"])
                area["cross_line1"] = None
            if area["cross_line2"]:
                canvas.delete(area["cross_line2"])
                area["cross_line2"] = None

            width = canvas.winfo_width()
            height = canvas.winfo_height()

            if width > 1 and height > 1:
                if (self.game_state == "come_out" and bet_type in disabled_in_come_out) or \
                (self.game_state == "point"    and bet_type in disabled_in_point):
                    l1 = canvas.create_line(0, 0, width, height, fill='black', width=2)
                    canvas.tag_raise(l1)
                    l2 = canvas.create_line(width, 0, 0, height, fill='black', width=2)
                    canvas.tag_raise(l2)

                    area["cross_line1"] = l1
                    area["cross_line2"] = l2

    def show_bet_rules(self, bet_type):
        rules = {
            "pass_line": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Come Out阶段", "7 / 11", "2 / 3 / 12", "其他任意点数"],
                ["Point阶段", "设定点数", "7", ""]
            ],
            "dont_pass": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Come Out阶段", "2 / 3 赢 \n12 平局", "7 / 11", "其他任意点数"],
                ["Point阶段", "7", "设定点数", ""]
            ],
            "come": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Point阶段", "7 / 11", "2 / 3 / 12", "其他任意点数"]
            ],
            "dont_come": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Point阶段", "2 / 3\n12（平局）", "7 / 11", "其他任意点数"]
            ],
            "big_6": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "6", "7", "其他点数"]
            ],
            "big_8": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "8", "7", "其他点数"]
            ],
            "field": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "2 / 12 赢 2:1\n3 / 4 / 9 / 10 / 11 赢 1:1", "5 / 6 / 7 / 8", ""]
            ],
            "place_4": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Point阶段", "4", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ On", "4", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ Off", "", "", "全部点数"]
            ],
            "place_5": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Point阶段", "5", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ On", "5", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ Off", "", "", "全部点数"]
            ],
            "place_6": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Point阶段", "6", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ On", "6", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ Off", "", "", "全部点数"]
            ],
            "place_8": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Point阶段", "8", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ On", "8", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ Off", "", "", "全部点数"]
            ],
            "place_9": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Point阶段", "9", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ On", "9", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ Off", "", "", "全部点数"]
            ],
            "place_10": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["Point阶段", "10", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ On", "10", "7", "其他点数"],
                ["Come Out阶段\nPlace Bet ~ Off", "", "", "全部点数"]
            ],
            "any_craps": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "2 / 3 / 12", "其他点数", ""]
            ],
            "any_7": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "7", "其他点数", ""]
            ],
            "horn_2": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "2", "其他点数", ""]
            ],
            "horn_3": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "3", "其他点数", ""]
            ],
            "horn_11": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "11", "其他点数", ""]
            ],
            "horn_12": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "12", "其他点数", ""]
            ],
            "combo_11": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "两个1", "其他组合或7", ""]
            ],
            "combo_12": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "1和2", "其他组合或7", ""]
            ],
            "combo_22": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "两个2", "其他组合或7", ""]
            ],
            "combo_33": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "两个3", "其他组合或7", ""]
            ],
            "combo_44": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "两个4", "其他组合或7", ""]
            ],
            "combo_55": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "两个5", "其他组合或7", ""]
            ],
            "combo_56": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "5和6", "其他组合或7", ""]
            ],
            "combo_66": [
                ["阶段", "获胜", "失败", "保留赌注"],
                ["所有阶段", "两个6", "其他组合或7", ""]
            ]
        }

        rule_table = rules.get(bet_type, [])

        if not rule_table:
            messagebox.showinfo(f"{bet_type} 规则", "暂无规则说明")
            return

        rule_window = tk.Toplevel(self.root)
        rule_window.title(f"{bet_type} 规则")
        rule_window.geometry("600x300")
        rule_window.transient(self.root)
        rule_window.grab_set()

        main_frame = tk.Frame(rule_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        table_frame = tk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)

        for i, row in enumerate(rule_table):
            for j, cell in enumerate(row):
                if i == 0:
                    bg_color = "#1e3d59"
                    fg_color = "white"
                    font = ("Arial", 10, "bold")
                    relief = tk.RAISED
                else:
                    bg_color = "#ffffff"
                    fg_color = "black"
                    font = ("Arial", 10)
                    relief = tk.FLAT

                cell_frame = tk.Frame(
                    table_frame,
                    borderwidth=1,
                    relief=relief,
                    bg=bg_color
                )
                cell_frame.grid(row=i, column=j, sticky="nsew", padx=1, pady=1)

                cell_label = tk.Label(
                    cell_frame,
                    text=cell,
                    font=font,
                    bg=bg_color,
                    fg=fg_color,
                    padx=5,
                    pady=5,
                    anchor=tk.W
                )
                cell_label.pack(fill=tk.BOTH, expand=True)

                table_frame.columnconfigure(j, weight=1)

        for i in range(len(rule_table)):
            table_frame.rowconfigure(i, weight=1)

        close_btn = tk.Button(
            main_frame,
            text="关闭",
            command=rule_window.destroy,
            width=10
        )
        close_btn.pack(pady=(10, 0))

    def set_bet_amount(self, amount):
        self.bet_amount = amount
        for canvas, oval_id, value in self.chip_widgets:
            if value == amount:
                canvas.itemconfig(oval_id, outline='yellow', width=4)
            else:
                canvas.itemconfig(oval_id, outline='#333', width=2)

    def place_bet(self, bet_type):
        if not self.accept_bets:
            return

        disabled_in_come_out = ["come", "dont_come", "place_4", "place_5", "place_6", "place_8", "place_9", "place_10"]
        disabled_in_point = ["pass_line", "dont_pass"]

        if self.game_state == "come_out" and bet_type in disabled_in_come_out:
            messagebox.showinfo("下注错误", "此下注类型仅在Point阶段可用")
            return

        if self.game_state == "point" and bet_type in disabled_in_point:
            messagebox.showinfo("下注错误", "此下注类型仅在Come-Out阶段可用")
            return

        amount = self.bet_amount
        if amount <= 0 or amount > self.balance:
            return

        if bet_type in self.multi_roll_bets:
            self.multi_roll_bets[bet_type] += amount
            self.current_round_multi_roll_bets[bet_type] += amount
        elif bet_type in self.single_roll_bets:
            self.single_roll_bets[bet_type] += amount

        self.current_bet += amount
        self.balance -= amount

        for bt in self.bet_areas:
            total_bet = 0
            if bt in self.multi_roll_bets:
                total_bet += self.multi_roll_bets[bt]
            if bt in self.single_roll_bets:
                total_bet += self.single_roll_bets[bt]
            self.bet_areas[bt]["label"].config(text=f"${total_bet}")

        self.update_display()

        if self.username:
            update_balance_in_json(self.username, self.balance)

    def add_to_history(self, dice, total, phase):
        children = self.history_inner.winfo_children()
        record_count = len(children) - 1

        if record_count >= 6:
            children[1].destroy()

        frame = tk.Frame(self.history_inner, bg='#D0E7FF', padx=5, pady=5, relief=tk.RIDGE, borderwidth=1)
        frame.pack(fill=tk.X, padx=2, pady=2, after=self.history_inner.winfo_children()[0] if len(self.history_inner.winfo_children()) > 1 else None)

        dice_frame = tk.Frame(frame, bg='#D0E7FF')
        dice_frame.pack(side=tk.LEFT, padx=10)
        for d in dice:
            lbl = tk.Label(dice_frame, image=self.dice_images_small[d-1], bg='#D0E7FF')
            lbl.pack(side=tk.LEFT, padx=2)

        total_label = tk.Label(frame, text=f"{total}", font=("Arial", 12), bg='#D0E7FF', width=8)
        total_label.pack(side=tk.LEFT, padx=10)

        phase_label = tk.Label(frame, text=phase, font=("Arial", 12), bg='#D0E7FF', width=15)
        phase_label.pack(side=tk.LEFT, padx=10)

    def update_display(self):
        self.balance_label.config(text=f"餘額: ${self.balance:.2f}")
        self.current_bet_display.config(text=f"本局下注: ${self.current_bet}")
        self.last_win_display.config(text=f"上局获胜: ${self.last_win:.2f}")

        for bet_type, area in self.bet_areas.items():
            total_bet = 0
            if bet_type in self.multi_roll_bets:
                total_bet += self.multi_roll_bets[bet_type]
            if bet_type in self.single_roll_bets:
                total_bet += self.single_roll_bets[bet_type]
            if "label" in area:
                area["label"].config(text=f"${total_bet}")

        self.update_come_data_display()

    def roll_dice(self):
        has_active_bets = (
            any(amount > 0 for amount in self.multi_roll_bets.values()) or
            any(amount > 0 for amount in self.single_roll_bets.values()) or
            self.come_points or
            self.dont_come_points
        )

        if not has_active_bets:
            messagebox.showinfo("无法掷骰", "请先下注")
            return

        if not self.accept_bets:
            return

        self.accept_bets = False

        if not self.shooter_active:
            self.shooter_active = True
            self.shooter_label.config(text="Shooter: 激活中")

        if self.enter_binding:
            self.root.unbind('<Return>')
            self.enter_binding = None

        # 确定起始骰子点数（优先使用上局组合，否则随机两个数字）
        if self.last_dice_pair is not None:
            start_dice1, start_dice2 = self.last_dice_pair
        else:
            start_dice1 = secrets.randbelow(6) + 1
            start_dice2 = secrets.randbelow(6) + 1

        # 启动动画窗口，传入起始骰子值
        DiceAnimationWindow(self, self.calculate_results, start_dice1, start_dice2)

    def calculate_results(self, final_dice=None):
        if final_dice is not None:
            self.dice_results = final_dice

        dice = self.dice_results
        total = sum(dice)

        self.last_win = 0
        for bt in self.current_round_multi_roll_bets:
            self.current_round_multi_roll_bets[bt] = 0

        old_state = self.game_state

        # 单轮下注结算
        refund = 0
        for bt, amt in self.single_roll_bets.items():
            if amt > 0:
                total_return = self.calculate_single_roll_win(bt, amt, dice, total)
                if total_return > 0:
                    refund += total_return
                    self.last_win += total_return
        self.balance += refund
        self.single_roll_bets = {k: 0 for k in self.single_roll_bets}
        self.current_bet = 0

        # Place Bets 结算
        rates = {
            "big_6": 1, "big_8": 1,
            "place_4": 9/5, "place_5": 7/5,
            "place_6": 7/6, "place_8": 7/6,
            "place_9": 7/5, "place_10": 9/5
        }

        # 在Point阶段或Come Out且Place Bets为ON时结算
        if old_state == "point" or (old_state == "come_out" and self.place_bets_on):
            for bt, rate in rates.items():
                amt = self.multi_roll_bets.get(bt, 0)
                if amt > 0:
                    if total == 7:
                        self.multi_roll_bets[bt] = 0
                    elif total == int(bt.split('_')[1] if bt.startswith('place_') else bt.split('_')[1]):
                        total_return = amt * (1 + rate)
                        self.balance += total_return
                        self.last_win += total_return
                        self.multi_roll_bets[bt] = 0

        # 主流程
        phase = ""
        if self.game_state == "come_out":
            if total in (7, 11):
                phase = f"Natural {total}"
                st = self.multi_roll_bets.get("pass_line", 0)
                if st > 0:
                    total_return = st * 2
                    self.balance += total_return
                    self.last_win += total_return
                    self.multi_roll_bets["pass_line"] = 0
                self.multi_roll_bets["dont_pass"] = 0
                self.point_number = None

            elif total in (2, 3, 12):
                phase = f"Craps {total}"
                self.multi_roll_bets["pass_line"] = 0
                dp = self.multi_roll_bets.get("dont_pass", 0)
                if dp > 0:
                    if total == 12:
                        self.balance += dp
                        self.last_win += dp
                    else:
                        total_return = dp * 2
                        self.balance += total_return
                        self.last_win += total_return
                    self.multi_roll_bets["dont_pass"] = 0
                self.point_number = None

            else:
                phase = f"设定点数 {total}"
                self.game_state = "point"
                self.point_number = total
                self.place_bets_on = True
                self.update_place_bets_button_state()

        else:
            if total == self.point_number:
                phase = f"命中点数 {self.point_number}！"
                st = self.multi_roll_bets.get("pass_line", 0)
                if st > 0:
                    total_return = st * 2
                    self.balance += total_return
                    self.last_win += total_return
                    self.multi_roll_bets["pass_line"] = 0
                self.multi_roll_bets["dont_pass"] = 0
                for p, amt in list(self.come_points.items()):
                    if p == self.point_number:
                        total_return = amt * 2
                        self.balance += total_return
                        self.last_win += total_return
                        del self.come_points[p]
                self.dont_come_points.pop(self.point_number, None)
                self.game_state = "come_out"
                self.point_number = None
                self.new_come_out_round = True
                self.update_place_bets_button_state()

            elif total == 7:
                phase = "7点出局"
                self.multi_roll_bets["pass_line"] = 0
                dp = self.multi_roll_bets.get("dont_pass", 0)
                if dp > 0:
                    total_return = dp * 2
                    self.balance += total_return
                    self.last_win += total_return
                    self.multi_roll_bets["dont_pass"] = 0
                self.come_points.clear()
                for p, amt in list(self.dont_come_points.items()):
                    total_return = amt * 2
                    self.balance += total_return
                    self.last_win += total_return
                    del self.dont_come_points[p]
                self.game_state = "come_out"
                self.point_number = None
                self.shooter_active = False
                self.new_come_out_round = True
                self.update_place_bets_button_state()
            elif total in (2, 3, 11, 12):
                phase = f"No Action {total}"
            else:
                phase = f"Point Number {total}"

        # Come / Don't Come 注
        if total == 7:
            self.come_points.clear()
        elif total in self.come_points:
            amt = self.come_points.pop(total)
            total_return = amt * 2
            self.balance += total_return
            self.last_win += total_return

        cm = self.multi_roll_bets.get("come", 0)
        if cm > 0:
            if total in (7, 11):
                payout = cm * 2
                self.balance += payout
                self.last_win += payout
            elif total in (2, 3, 12):
                pass
            else:
                self.come_points[total] = self.come_points.get(total, 0) + cm
            self.multi_roll_bets["come"] = 0

        if total == 7:
            for point, amount in list(self.dont_come_points.items()):
                payout = amount * 2
                self.balance += payout
                self.last_win += payout
            self.dont_come_points.clear()
        elif total in self.dont_come_points:
            del self.dont_come_points[total]

        dcm = self.multi_roll_bets.get("dont_come", 0)
        if dcm > 0:
            if total in (2, 3):
                payout = dcm * 2
                self.balance += payout
                self.last_win += payout
            elif total == 12:
                self.balance += dcm
                self.last_win += dcm
            elif total in (7, 11):
                pass
            else:
                self.dont_come_points[total] = self.dont_come_points.get(total, 0) + dcm
            self.multi_roll_bets["dont_come"] = 0

        self.state_label.config(text=f"阶段: {'POINT' if self.game_state=='point' else 'COME OUT'}")
        self.point_label.config(text=f"点数: {self.point_number if self.point_number else '-'}")
        self.update_bet_areas_state()
        self.add_to_history(dice, total, phase)
        self.update_display()
        self.accept_bets = True

        # 保存本次掷出的骰子结果，作为下一局的起始种子
        self.last_dice_pair = dice

        if self.username:
            update_balance_in_json(self.username, self.balance)
        self.enter_binding = self.root.bind('<Return>', lambda e: self.roll_dice())

    def calculate_single_roll_win(self, bet_type, amount, dice, total):
        dice1, dice2 = dice
        sorted_dice = sorted(dice)

        if bet_type == "field":
            if total in [2, 12]:
                return amount * 3
            elif total in [3, 4, 9, 10, 11]:
                return amount * 2
            return 0

        elif bet_type == "any_craps":
            if total in [2, 3, 12]:
                return amount * 8
            return 0

        elif bet_type == "any_7":
            if total == 7:
                return amount * 5
            return 0

        elif bet_type == "horn_2":
            if total == 2:
                return amount * 31
            return 0
        elif bet_type == "horn_3":
            if total == 3:
                return amount * 16
            return 0
        elif bet_type == "horn_11":
            if total == 11:
                return amount * 16
            return 0
        elif bet_type == "horn_12":
            if total == 12:
                return amount * 31
            return 0

        elif bet_type == "combo_11":
            if sorted_dice == [1, 1]:
                return amount * 31
            return 0
        elif bet_type == "combo_12":
            if sorted_dice == [1, 2]:
                return amount * 16
            return 0
        elif bet_type == "combo_22":
            if sorted_dice == [2, 2]:
                return amount * 8
            return 0
        elif bet_type == "combo_33":
            if sorted_dice == [3, 3]:
                return amount * 10
            return 0
        elif bet_type == "combo_44":
            if sorted_dice == [4, 4]:
                return amount * 10
            return 0
        elif bet_type == "combo_55":
            if sorted_dice == [5, 5]:
                return amount * 8
            return 0
        elif bet_type == "combo_56":
            if sorted_dice == [5, 6]:
                return amount * 16
            return 0
        elif bet_type == "combo_66":
            if sorted_dice == [6, 6]:
                return amount * 31
            return 0

        return 0

    def clear_bets(self):
        if not self.accept_bets:
            return

        for bet_type in self.single_roll_bets:
            if self.single_roll_bets[bet_type] > 0:
                self.balance += self.single_roll_bets[bet_type]
                self.current_bet -= self.single_roll_bets[bet_type]
                self.single_roll_bets[bet_type] = 0

        for bet_type in self.current_round_multi_roll_bets:
            if self.current_round_multi_roll_bets[bet_type] > 0:
                amount = self.current_round_multi_roll_bets[bet_type]
                self.multi_roll_bets[bet_type] -= amount
                self.balance += amount
                self.current_bet -= amount
                self.current_round_multi_roll_bets[bet_type] = 0

        self.update_display()

        if self.username:
            update_balance_in_json(self.username, self.balance)

def main(balance=None, username=None):
    root = tk.Tk()

    if username and balance is None:
        users = load_user_data()
        for user in users:
            if user['user_name'] == username:
                balance = float(user['cash'])
                break
        else:
            balance = 10000.0

    if balance is None:
        balance = 10000.0

    game = CrapsGame(root, username, balance)
    root.mainloop()

    return game.final_balance

if __name__ == "__main__":
    final_balance = main()
    print(f"游戏结束，最终余额: ${final_balance:.2f}")