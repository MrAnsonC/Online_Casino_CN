import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw
import random
import json
import os
import math
import sys
import os

# 获取当前文件所在目录并定位到A_Tools文件夹
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # 上一级目录
a_tools_dir = os.path.join(parent_dir, 'A_Tools')

# 将A_Tools目录添加到系统路径
if a_tools_dir not in sys.path:
    sys.path.append(a_tools_dir)

# 导入真随机骰子模块
from shuffle_dice import Dice

# 骰子组合类型
HAND_TYPES = {
    "five_of_a_kind": "五同",
    "four_of_a_kind": "四同",
    "big_straight": "大顺子(2-3-4-5-6)",
    "small_straight": "小顺子(1-2-3-4-5)",
    "straight": "顺子",
    "high_die": "散牌",
    "full_house": "葫芦",
    "three_of_a_kind": "三同",
    "two_pairs": "两对",
    "one_pair": "一对"
}

# 组合顺序（从强到弱）
HAND_RANK_ORDER = [
    "five_of_a_kind",
    "four_of_a_kind",
    "big_straight",
    "small_straight",
    "straight",
    "high_die",
    "full_house",
    "three_of_a_kind",
    "two_pairs",
    "one_pair"
]

# Bind赔付表
BIND_PAYOUT = {
    "five_of_a_kind": 100,
    "four_of_a_kind": 50,
    "big_straight": 10,
    "small_straight": 10,
    "straight": 5,
    "high_die": 2,
    "other": 1  # 平局或输
}

# Bonus赔付表
BONUS_PAYOUT = {
    "five_of_a_kind": 30,
    "four_of_a_kind": 10,
    "big_straight": 5,
    "small_straight": 5,
    "straight": 3,
    "high_die": 0,   # 平局
    "other": -1      # 输
}

# Progressive赔付表
PROGRESSIVE_PAYOUT = {
    "five_of_a_kind": "$1500 + Prog的10%",
    "four_of_a_kind": "$500 + Prog的5%",
    "big_straight": "$300 + Prog的3%",
    "small_straight": "$300 + Prog的3%",
    "other": -1  # 输
}

# 初始Jackpot金额
INITIAL_JACKPOT = 4200

def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

# Jackpot 文件加载与保存
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    # 文件不存在时使用默认奖池
    if not os.path.exists(path):
        return True, INITIAL_JACKPOT
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'KD':
                    return False, float(item.get('jackpot', INITIAL_JACKPOT))
    except Exception:
        return True, INITIAL_JACKPOT
    # 未找到 KD 条目时也使用默认
    return True, INITIAL_JACKPOT

def save_jackpot(jackpot):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    data = []
    # 如果文件存在，读取原有数据
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    
    # 查找是否已有KD的记录
    found = False
    for item in data:
        if item.get('Games') == 'KD':
            item['jackpot'] = jackpot
            found = True
            break
    
    if not found:
        data.append({"Games": "KD", "jackpot": jackpot})
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

class KlondikeDiceGame:
    def __init__(self):
        self.reset_game()
        # 初始化Jackpot
        self.jackpot_amount = load_jackpot()[1]
        self.initial_jackpot = self.jackpot_amount  # 保存初始值用于重置
    
    def reset_game(self):
        self.dealer_dice = [Dice() for _ in range(5)]
        self.player_dice = [Dice() for _ in range(5)]
        self.ante = 0
        self.blind = 0  # 新增Blind下注
        self.trips = 0  # 新增Trips下注
        self.jackpot_bet = 0
        self.stage = "pre_roll"  # pre_roll, decision, showdown
        self.folded = False
        self.dice_revealed = {
            "player": [False, False, False, False, False],
            "dealer": [False, False, False, False, False]
        }
        self.jackpot_amount = load_jackpot()[1]  # 重新加载jackpot
    
    def roll_all(self):
        """掷所有骰子"""
        for die in self.dealer_dice:
            die.roll()
        for die in self.player_dice:
            die.roll()
    
    def sort_dice(self, dice):
        """对骰子进行排序（从小到大）"""
        return sorted(dice, key=lambda d: d.value)
    
    def evaluate_hand(self, dice):
        """评估骰子组合类型"""
        values = [d.value for d in dice]
        
        # 检查大顺子 (2-3-4-5-6 或 6-5-4-3-2)
        if values == [2, 3, 4, 5, 6] or values == [6, 5, 4, 3, 2]:
            return "big_straight"
        
        # 检查小顺子 (1-2-3-4-5 或 5-4-3-2-1)
        if values == [1, 2, 3, 4, 5] or values == [5, 4, 3, 2, 1]:
            return "small_straight"
        
        sorted_values = sorted(values)
        counts = {i: sorted_values.count(i) for i in set(sorted_values)}
        unique_count = len(counts)
        
        # 检查五同
        if unique_count == 1:
            return "five_of_a_kind"
        
        # 检查四同
        if 4 in counts.values():
            return "four_of_a_kind"
        
        # 检查葫芦 (3+2)
        if 3 in counts.values() and 2 in counts.values():
            return "full_house"
        
        # 检查顺子 (任意顺序的顺子)
        if sorted_values in [[1,2,3,4,5], [2,3,4,5,6]]:
            return "straight"
        
        # 检查散牌（high_die） - 无任何组合的牌型
        if max(counts.values()) == 1 and len(values) == 5:
            return "high_die"
        
        # 检查三同
        if 3 in counts.values():
            return "three_of_a_kind"
        
        # 检查两对
        if list(counts.values()).count(2) == 2:
            return "two_pairs"
        
        # 检查一对
        if 2 in counts.values():
            return "one_pair"
        
        # 如果以上都不是，默认为散牌
        return "high_die"
    
    def compare_hands(self, hand1, hand2):
        """比较两手牌，返回1表示hand1赢，0表示平局，-1表示hand2赢"""
        rank1 = HAND_RANK_ORDER.index(hand1)
        rank2 = HAND_RANK_ORDER.index(hand2)
        
        if rank1 < rank2:  # 组合等级越高（在列表中位置越靠前）越强
            return 1
        elif rank1 > rank2:
            return -1
        else:
            # 相同组合类型，平局
            return 0

class KlondikeDiceGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("Klondike Dice")
        self.geometry("1050x700+50+10")
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = KlondikeDiceGame()
        self.dice_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.active_dice_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.last_jackpot_state = 0
        self.win_details = {
            "ante": 0,
            "blind": 0,
            "trips": 0,
            "progressive": 0
        }
        self.bet_widgets = {}
        self.jackpot_bet_var = tk.IntVar(value=0)
        self.rolling_dice = []
        self.roll_step = 0
        self.roll_count = 0
        self.roll_direction = 1
        self.dice_animation_active = False
        self.fold_button = None
        self.play_button = None
        self.current_bet_area = "ante"  # 当前选中的下注区域

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
    
    def draw_dice(self, img, num):
        """程序绘制骰子图像"""
        draw = ImageDraw.Draw(img)
        size = img.size[0]
        dot_size = max(2, size // 10)  # 确保点大小至少为2像素
        # 绘制骰子边框
        draw.rectangle([0, 0, size-1, size-1], outline='#333', width=1, fill='#e8d6b3')
        dot_color = '#333'
        
        # 定义骰子点数位置
        dot_positions = {
            1: [(size//2, size//2)],
            2: [(size//4, size//4), (3*size//4, 3*size//4)],
            3: [(size//4, size//4), (size//2, size//2), (3*size//4, 3*size//4)],
            4: [(size//4, size//4), (3*size//4, size//4), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            5: [(size//4, size//4), (3*size//4, size//4), (size//2, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            6: [(size//4, size//4), (3*size//4, size//4), (size//4, size//2), (3*size//4, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)]
        }
        
        # 绘制骰子点数
        for pos in dot_positions.get(num, []):
            draw.ellipse([pos[0]-dot_size, pos[1]-dot_size, pos[0]+dot_size, pos[1]+dot_size], fill=dot_color)
    
    def _load_assets(self):
        dice_size = (80, 80)  # 骰子显示大小
        
        # 为1-6每个点数创建图像
        self.dice_images = {}
        for i in range(1, 7):
            # 创建空白图像（使用更大尺寸绘制，然后缩小）
            base_img = Image.new('RGB', (120, 120), '#e8d6b3')
            self.draw_dice(base_img, i)
            # 缩小到显示尺寸
            resized_img = base_img.resize(dice_size, Image.LANCZOS)
            self.dice_images[i] = ImageTk.PhotoImage(resized_img)

    def add_chip_to_bet_area(self, event, bet_type):
        """添加筹码到下注区域"""
        if not self.selected_chip:
            return
            
        # 获取筹码金额
        chip_value = float(self.selected_chip.replace('$', '').replace('K', '000'))
        
        # 右键点击：重置下注区域
        if event.num == 3:  # 右键
            if bet_type == "ante":
                self.ante_var.set("0")
                self.blind_var.set("0")
            elif bet_type == "trips":
                self.trips_var.set("0")
            return
            
        # 左键点击：添加筹码
        # 更新对应的下注变量
        if bet_type == "ante":
            current = float(self.ante_var.get())
            self.ante_var.set(str(int(current + chip_value)))
            # 自动更新Blind的值
            self.blind_var.set(self.ante_var.get())
        elif bet_type == "trips":
            current = float(self.trips_var.get())
            self.trips_var.set(str(int(current + chip_value)))
    
    def select_bet_area(self, area):
        """选择下注区域"""
        self.current_bet_area = area
        # 重置所有下注区域的背景色
        self.ante_display.config(bg='white')
        self.trips_display.config(bg='white')
    
    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=50, width=500, height=200)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_dice_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_dice_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 在庄家和玩家区域之间添加提示文字
        self.info_label = tk.Label(
            table_canvas, 
            text="庄家牌型为对子时不及格\nAnte直接退还，不作比牌",
            font=('Arial', 22), 
            bg='#35654d', 
            fg='#FFD700'
        )
        self.info_label.place(x=300, y=265, anchor='n')
        
        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=350, width=500, height=200)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_dice_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_dice_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=300, padx=10, pady=10)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=10)
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 14),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.stage_label = tk.Label(
            info_frame, 
            text="阶段: 下注",
            font=('Arial', 14, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # Jackpot显示区域
        jackpot_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        jackpot_frame.pack(fill=tk.X, pady=10)
        
        jackpot_inner_frame = tk.Frame(jackpot_frame, bg='#2a4a3c')
        jackpot_inner_frame.pack(expand=True, pady=5)

        jackpot_label = tk.Label(jackpot_inner_frame, text="Progressive:", 
                                font=('Arial', 18), bg='#2a4a3c', fg='gold')
        jackpot_label.pack(side=tk.LEFT, padx=(0, 5))

        self.jackpot_var = tk.StringVar()
        self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")
        self.jackpot_display = tk.Label(jackpot_inner_frame, textvariable=self.jackpot_var, 
                                    font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='gold')
        self.jackpot_display.pack(side=tk.LEFT)
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=10)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        
        # 单行放置5个筹码
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs = [
            ("$5", '#ff0000', 'white'),
            ("$10", '#ffa500', 'black'),
            ("$25", '#00ff00', 'black'),
            ("$50", '#ffffff', 'black'),
            ("$100", '#000000', 'white')
        ]
        
        self.chip_buttons = []
        self.chip_texts = {}
        for text, bg_color, fg_color in chip_configs:
            chip_canvas = tk.Canvas(chip_row, width=60, height=60, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 58, 58, fill=bg_color, outline='black')
            text_id = chip_canvas.create_text(30, 30, text=text, fill=fg_color, font=('Arial', 16, 'bold'))
            # 修改：只选择筹码，不添加到下注区域
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        
        # 默认选中$5筹码
        self.select_chip("$5")
        
        # 下注区域 - 修改为三行布局
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        
        # 第一行：Jackpot选项
        jackpot_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        jackpot_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.jackpot_check = tk.Checkbutton(
            jackpot_frame, 
            text="Progressive ($2.50)", 
            variable=self.jackpot_bet_var,
            font=('Arial', 14),
            bg='#2a4a3c', 
            fg='white', 
            selectcolor='black'
        )
        self.jackpot_check.pack(side=tk.LEFT)
        
        # 第二行：Trips区域
        trips_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        trips_frame.pack(fill=tk.X, padx=20, pady=5)

        trips_label = tk.Label(trips_frame, text="Bonus:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        trips_label.pack(side=tk.LEFT)

        self.trips_var = tk.StringVar(value="0")
        self.trips_display = tk.Label(trips_frame, textvariable=self.trips_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.trips_display.pack(side=tk.LEFT, padx=5)
        # 修改：左键添加筹码，右键重置
        self.trips_display.bind("<Button-1>", lambda e: [self.select_bet_area("trips"), self.add_chip_to_bet_area(e, "trips")])
        self.trips_display.bind("<Button-3>", lambda e: [self.select_bet_area("trips"), self.add_chip_to_bet_area(e, "trips")])
        self.bet_widgets["trips"] = self.trips_display
        
        # 第三行：Ante和Blind区域（等式形式）
        ante_blind_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        ante_blind_frame.pack(fill=tk.X, padx=20, pady=5)

        # Ante 显示区域
        ante_label = tk.Label(ante_blind_frame, text=" Ante:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        ante_label.pack(side=tk.LEFT)

        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(ante_blind_frame, textvariable=self.ante_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        # 修改：左键添加筹码，右键重置
        self.ante_display.bind("<Button-1>", lambda e: [self.select_bet_area("ante"), self.add_chip_to_bet_area(e, "ante")])
        self.ante_display.bind("<Button-3>", lambda e: [self.select_bet_area("ante"), self.add_chip_to_bet_area(e, "ante")])
        self.bet_widgets["ante"] = self.ante_display  # 存储用于背景色更改

        # 等号
        tk.Label(ante_blind_frame, text="=", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=5)

        # Blind 显示区域（只读）
        self.blind_var = tk.StringVar(value="0")
        self.blind_display = tk.Label(ante_blind_frame, textvariable=self.blind_var, font=('Arial', 14), 
                                bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.blind_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["blind"] = self.blind_display  # 存储用于背景色更改
        
        # Blind 文本标签
        blind_label = tk.Label(ante_blind_frame, text=": Blind", font=('Arial', 14), bg='#2a4a3c', fg='white')
        blind_label.pack(side=tk.LEFT, padx=5)

        # 添加提示文字
        tip_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        tip_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        # 游戏操作按钮框架
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X, pady=10)

        # 创建一个框架来容纳重置按钮和开始游戏按钮
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=10)

        # 添加"重置金额"按钮
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重置金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

        # 开始游戏按钮
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        
        # 状态信息
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 12), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)
        
        # 结果展示
        self.result_label = tk.Label(
            control_frame, text="", 
            font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', justify='center'
        )
        self.result_label.pack(pady=5, fill=tk.X)
        
        # 本局下注和上局获胜金额显示
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 本局下注金额
        self.current_bet_label = tk.Label(
            bet_info_frame, text="本局下注: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        
        # 上局获胜金额
        self.last_win_label = tk.Label(
            bet_info_frame, text="上局获胜: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)
        
        # 添加游戏规则按钮到上局获胜的右下角
        rules_btn = tk.Button(
            bet_info_frame, text="ℹ️", 
            command=self.show_game_instructions, 
            font=('Arial', 8), bg='#4B8BBE', fg='white', width=2, height=1
        )
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)

    def show_game_instructions(self):
        """显示游戏规则说明"""
        win = tk.Toplevel(self)
        win.title("Klondike Dice 游戏规则")
        win.geometry("800x650")
        win.resizable(0,0)
        win.configure(bg='#F0F0F0')
        
        # 创建主框架
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建画布用于滚动
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        # 创建内部框架放置所有内容
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        # 游戏规则文本
        rules_text = """
        Klondike Dice 游戏规则

        1. 游戏开始前下注:
           - Ante: 基础下注（必须）
           - Blind: 与Ante等额（强制）
           - Bonus: 可选下注（看玩家牌型）
           - Progressive: 可选$2.50下注（参与Bonus奖励）

        2. 游戏流程:
           a. 下注阶段:
               - 玩家下注Ante（Blind自动等于Ante）
               - 可选择下注Bonus和Progressive
               - 点击"开始游戏"按钮开始

           b. 掷骰子:
               - 庄家和玩家各掷5颗骰子
               - 庄家先开牌
               - 玩家开牌

           c. 结算阶段:
               - 根据庄家和玩家的骰子组合结算

        3. 结算规则:
           a. Ante:
              - 庄家不及格（一对）: 退还Ante
              - 玩家获胜: 1:1
              - 平局: 退还Ante
              - 失败: 失去Ante

           b. Blind:
              - 玩家获胜: 按牌型赔率支付
              - 平局: 退还Blind
              - 失败: 失去Blind

           c. Bonus:
              - 只看玩家牌型:
                 五同: 30:1
                 四同: 10:1
                 大顺: 5:1
                 小顺: 5:1
                 顺子: 3:1
                 散牌: 平局（退还）
                 其他牌型: 输（失去）

           d. Progressive: 保持不变
        """
        
        rules_label = tk.Label(
            content_frame, 
            text=rules_text,
            font=('微软雅黑', 11),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        rules_label.pack(fill=tk.X, padx=10, pady=5)
        
        # Ante赔付表
        tk.Label(
            content_frame, 
            text="Ante 结算规则",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        ante_frame = tk.Frame(content_frame, bg='#F0F0F0')
        ante_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["庄家情况", "玩家情况", "结果"]
        ante_data = [
            ("不及格（一对）", "任何牌型", "退还Ante"),
            ("及格", "玩家获胜", "1:1赔付"),
            ("及格", "平局", "退还Ante"),
            ("及格", "玩家失败", "失去Ante")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                ante_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(ante_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    ante_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度
        for c in range(len(headers)):
            ante_frame.columnconfigure(c, weight=1)
        
        # Blind赔付表
        tk.Label(
            content_frame, 
            text="Blind 赔付表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        blind_frame = tk.Frame(content_frame, bg='#F0F0F0')
        blind_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "赔率"]
        blind_data = [
            ("五同", "100:1"),
            ("四同", "50:1"),
            ("大顺", "10:1"),
            ("小顺", "10:1"),
            ("顺子", "5:1"),
            ("散牌", "2:1"),
            ("葫芦", "1:1"),
            ("三同", "1:1"),
            ("两对", "1:1"),
            ("一对", "1:1")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                blind_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(blind_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    blind_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度
        for c in range(len(headers)):
            blind_frame.columnconfigure(c, weight=1)
        
        # Bonus赔付表
        tk.Label(
            content_frame, 
            text="Bonus 赔付表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        trips_frame = tk.Frame(content_frame, bg='#F0F0F0')
        trips_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["玩家牌型", "结果"]
        trips_data = [
            ("五同", "30:1"),
            ("四同", "10:1"),
            ("大顺", "5:1"),
            ("小顺", "5:1"),
            ("顺子", "3:1"),
            ("散牌", "退还"),
            ("葫芦", "输"),
            ("三同", "输"),
            ("两对", "输"),
            ("一对", "输")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                trips_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(trips_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    trips_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度
        for c in range(len(headers)):
            trips_frame.columnconfigure(c, weight=1)
            
        # Progressive赔付表
        tk.Label(
            content_frame, 
            text="Progressive 赔付表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        prog_frame = tk.Frame(content_frame, bg='#F0F0F0')
        prog_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["玩家牌型", "奖励"]
        prog_data = [
            ("五同", "$1500 + Prog的10%"),
            ("四同", "$500 + Prog的5%"),
            ("大顺", "$300 + Prog的3%"),
            ("小顺", "$300 + Prog的3%"),
            ("其他牌型", "输")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                prog_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(prog_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    prog_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度
        for c in range(len(headers)):
            prog_frame.columnconfigure(c, weight=1)
            
        # 注释
        notes = """
        注: 
        * 庄家不及格指庄家牌型为一对
        * Blind赔付必须打败庄家才可以获胜
        * Bonus赔付只看玩家牌型
        * Progressive的奖池最低为$4200
        """
        
        notes_label = tk.Label(
            content_frame, 
            text=notes,
            font=('微软雅黑', 10),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        notes_label.pack(fill=tk.X, padx=10, pady=5)
        
        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 添加关闭按钮
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)
        
        # 绑定鼠标滚轮滚动
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    
    def select_chip(self, chip_text):
        """选择筹码，并更新筹码的高亮状态"""
        self.selected_chip = chip_text
        # 1. 重置所有筹码的边框
        for chip in self.chip_buttons:
            # 删除之前的高亮
            chip.delete("highlight")
            # 找到 oval 的 id，重画默认黑色边框
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item_id)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break

        # 2. 给选中的筹码加金色高亮
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            # 先分别找到 text 和 oval 的 id
            for item_id in chip.find_all():
                t = chip.type(item_id)
                if t == 'text':
                    text_id = item_id
                elif t == 'oval':
                    oval_id = item_id
            # 如果找到了文字项，并且内容匹配
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                # 拿到对应的 oval 坐标
                x1, y1, x2, y2 = chip.coords(oval_id)
                chip.create_oval(x1, y1, x2, y2, outline='gold', width=3, tags="highlight")
                break
    
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
    
    def update_hand_labels(self):
        """更新玩家和庄家的手牌标签显示组合类型"""
        # 计算玩家当前组合
        if self.game.player_dice and len(self.game.player_dice) == 5:
            player_hand = self.game.evaluate_hand(self.game.player_dice)
            self.player_label.config(text=f"玩家 - {HAND_TYPES[player_hand]}")
        
        # 计算庄家当前组合
        if self.game.dealer_dice and len(self.game.dealer_dice) == 5:
            dealer_hand = self.game.evaluate_hand(self.game.dealer_dice)
            self.dealer_label.config(text=f"庄家 - {HAND_TYPES[dealer_hand]}")
    
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.blind = self.ante  # Blind等于Ante
            self.trips = int(self.trips_var.get())
            self.jackpot_bet = self.jackpot_bet_var.get() * 2.5  # 每局2.50
            self.last_jackpot_state = self.jackpot_bet_var.get()   
            
            # 检查Ante至少5块
            if self.ante < 5:
                messagebox.showerror("错误", "Ante至少需要5块")
                return
                
            # 计算总下注
            total_bet = self.ante + self.blind + self.trips + self.jackpot_bet
                
            if self.balance < total_bet:
                messagebox.showwarning("警告", "余额不足")
                return
                
            self.balance -= total_bet
            self.update_balance()
            
            # 更新本局下注显示
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            
            # 将下注金额的1%加入Progressive奖池
            jackpot_contribution = total_bet * 3.1415926 * 0.01
            self.game.jackpot_amount += jackpot_contribution
            save_jackpot(self.game.jackpot_amount)
            self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")
            
            self.game.reset_game()
            self.game.ante = self.ante
            self.game.blind = self.blind
            self.game.trips = self.trips
            self.game.jackpot_bet = self.jackpot_bet
            
            # 清除所有骰子
            for widget in self.dealer_dice_frame.winfo_children():
                widget.destroy()
            for widget in self.player_dice_frame.winfo_children():
                widget.destroy()
            
            # 重置动画状态
            self.animation_queue = []
            self.animation_in_progress = False
            self.active_dice_labels = []
            self.rolling_dice = []
            self.roll_step = 0
            self.roll_count = 0
            self.roll_direction = 1
            self.dice_animation_active = False
            
            # 初始化骰子位置
            self.dice_positions = {}
            
            # 庄家骰子
            for i in range(5):
                # 庄家骰子
                dealer_dice_id = f"dealer_{i}"
                self.dice_positions[dealer_dice_id] = {
                    "current": (50, 50), 
                    "target": (i * 90, 0)
                }
                
                # 玩家骰子
                player_dice_id = f"player_{i}"
                self.dice_positions[player_dice_id] = {
                    "current": (50, 50), 
                    "target": (i * 90, 0)
                }
                
                # 同时创建骰子
                self.create_dice(dealer_dice_id)
                self.create_dice(player_dice_id)

            # 创建操作按钮 - 替换开始按钮
            for widget in self.action_frame.winfo_children():
                widget.destroy()
                
            # 更新游戏状态
            self.game.stage = "rolling"
            self.stage_label.config(text="阶段: 掷骰子")
            self.status_label.config(text="掷骰子中...")

            # 禁用下注区域
            self.ante_display.unbind("<Button-1>")
            self.ante_display.unbind("<Button-3>")
            self.trips_display.unbind("<Button-1>")
            self.trips_display.unbind("<Button-3>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            
            # 禁用Jackpot的Checkbutton
            self.jackpot_check.config(state=tk.DISABLED)
            
            # 开始动画
            self.animate_deal()
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    def create_dice(self, dice_id):
        """创建单个骰子并添加到动画队列"""
        if dice_id.startswith("player"):
            frame = self.player_dice_frame
            idx = int(dice_id.split("_")[1])
            dice = self.game.player_dice[idx] if idx < len(self.game.player_dice) else None
        elif dice_id.startswith("dealer"):
            frame = self.dealer_dice_frame
            idx = int(dice_id.split("_")[1])
            dice = self.game.dealer_dice[idx] if idx < len(self.game.dealer_dice) else None
        else:
            return
        
        # 创建骰子标签
        dice_label = tk.Label(frame, image=self.dice_images[1], bg='#2a4a3c')
        dice_label.place(
            x=self.dice_positions[dice_id]["current"][0],
            y=self.dice_positions[dice_id]["current"][1] + 20,
            width=80,
            height=80
        )
        
        # 存储骰子信息
        dice_label.dice_id = dice_id
        dice_label.dice = dice
        dice_label.target_pos = self.dice_positions[dice_id]["target"]
        
        # 添加到活动骰子列表
        self.active_dice_labels.append(dice_label)
        self.animation_queue.append(dice_label)
    
    def animate_deal(self):
        """同时动画所有骰子"""
        if not self.animation_queue:
            self.animation_in_progress = False
            # 动画完成后开始掷骰子
            self.after(500, self.roll_dice)
            return
            
        self.animation_in_progress = True
        
        # 同时移动所有骰子
        for dice_label in self.animation_queue[:]:
            if not self.animate_dice_move(dice_label):
                # 如果骰子到达目标位置，从队列中移除
                if dice_label in self.animation_queue:
                    self.animation_queue.remove(dice_label)
        
        # 如果还有骰子在移动，继续动画
        if self.animation_queue:
            self.after(50, self.animate_deal)
        else:
            self.animation_in_progress = False
            self.after(500, self.roll_dice)

    def animate_dice_move(self, dice_label):
        """移动单个骰子，返回True如果还在移动中"""
        try:
            current_x = dice_label.winfo_x()
            current_y = dice_label.winfo_y()
            target_x, target_y = dice_label.target_pos
            
            # 计算移动方向向量
            dx = target_x - current_x
            dy = target_y - current_y
            distance = math.sqrt(dx**2 + dy**2)
            
            # 如果已经到达目标位置
            if distance < 5:
                dice_label.place(x=target_x, y=target_y, width=80, height=80)
                return False
                
            # 计算移动步长
            step_x = dx * 0.2
            step_y = dy * 0.2
            
            # 更新位置
            new_x = current_x + step_x
            new_y = current_y + step_y
            dice_label.place(x=new_x, y=new_y, width=80, height=80)
            
            return True
            
        except tk.TclError:
            # 骰子已被销毁
            if dice_label in self.animation_queue:
                self.animation_queue.remove(dice_label)
            return False
    
    def roll_dice(self):
        """开始掷骰子动画"""
        # 重置骰子值
        self.game.roll_all()
        
        # 收集所有骰子
        self.rolling_dice = self.active_dice_labels[:]
        self.roll_step = 0
        self.roll_count = 0
        self.roll_direction = 1
        self.dice_animation_active = True
        
        # 开始动画
        self.animate_roll()
    
    def animate_roll(self):
        if self.roll_count > 30:  # 总共滚动30次
            # 动画结束，显示最终结果
            self.dice_animation_active = False
            self.game.stage = "showdown"
            self.stage_label.config(text="阶段: 结算")
            
            # 显示庄家骰子
            self.reveal_dealer_dice()
            
            # 显示玩家骰子
            self.reveal_player_dice()
            
            # 更新组合标签
            self.update_hand_labels()
            
            # 结算游戏
            self.after(2000, self.show_showdown)
            return
        
        # 更新骰子显示
        for dice_label in self.rolling_dice:
            if dice_label.winfo_exists():
                # 随机显示骰子面
                value = dice_label.dice.roll()
                dice_label.config(image=self.dice_images[value])
        
        self.roll_count += 1
        self.after(50, self.animate_roll)
    
    def reveal_dealer_dice(self):
        """显示庄家骰子的最终结果"""
        for i, dice_label in enumerate(self.dealer_dice_frame.winfo_children()):
            if hasattr(dice_label, "dice") and dice_label.dice:
                dice_label.config(image=self.dice_images[dice_label.dice.value])
    
    def reveal_player_dice(self):
        """显示玩家骰子的最终结果"""
        for i, dice_label in enumerate(self.player_dice_frame.winfo_children()):
            if hasattr(dice_label, "dice") and dice_label.dice:
                dice_label.config(image=self.dice_images[dice_label.dice.value])
    
    def show_showdown(self):
        """结算游戏"""
        # 获取庄家和玩家的组合
        dealer_hand = self.game.evaluate_hand(self.game.dealer_dice)
        player_hand = self.game.evaluate_hand(self.game.player_dice)
        
        # 计算赢得的金额
        winnings = 0
        details = {
            "ante": 0,
            "blind": 0,
            "trips": 0,
            "progressive": 0
        }
        
        # 1. Ante结算 - 修复问题3：庄家不及格时只退还Ante
        if dealer_hand == "one_pair":  # 庄家不及格（一对）
            details["ante"] = self.game.ante  # 退还Ante
            winnings += self.game.ante
            self.ante_display.config(bg='lightblue')  # 高亮显示
        else:
            # 比较牌型
            comparison = self.game.compare_hands(dealer_hand, player_hand)
            if comparison < 0:  # 玩家赢
                details["ante"] = self.game.ante * 2  # 1:1赔付
                winnings += self.game.ante * 2
                self.ante_display.config(bg='gold')
            elif comparison == 0:  # 平局
                details["ante"] = self.game.ante  # 退还Ante
                winnings += self.game.ante
                self.ante_display.config(bg='lightblue')
            else:  # 庄家赢
                details["ante"] = 0
                self.ante_display.config(bg='white')
        
        # 2. Blind结算 - 不受庄家不及格影响
        comparison = self.game.compare_hands(dealer_hand, player_hand)
        if comparison < 0:  # 玩家赢
            # 根据牌型获取赔率
            payout_multiplier = BIND_PAYOUT.get(player_hand, 1)  # 使用新的赔付表
            if payout_multiplier == 0:  # 其他牌型平局
                details["blind"] = self.game.blind
                winnings += self.game.blind
                self.blind_display.config(bg='lightblue')
            else:
                details["blind"] = self.game.blind * payout_multiplier
                winnings += self.game.blind * payout_multiplier
                self.blind_display.config(bg='gold')
        elif comparison == 0:  # 平局
            details["blind"] = self.game.blind
            winnings += self.game.blind
            self.blind_display.config(bg='lightblue')
        else:  # 庄家赢
            details["blind"] = 0
            self.blind_display.config(bg='white')
        
        # 3. Trips结算 - 不受庄家不及格影响
        # 根据玩家牌型获取赔率
        payout_multiplier = BONUS_PAYOUT.get(player_hand, -1)
        if payout_multiplier == -1:  # 其他牌型输
            details["trips"] = 0
            self.trips_display.config(bg='white')
        elif payout_multiplier == 0:  # 散牌平局
            details["trips"] = self.game.trips
            winnings += self.game.trips
            self.trips_display.config(bg='lightblue')
        else:
            details["trips"] = self.game.trips * payout_multiplier
            winnings += self.game.trips * payout_multiplier
            self.trips_display.config(bg='gold')
        
        # 4. Progressive结算 - 不受庄家不及格影响
        if self.game.jackpot_bet > 0:
            progressive_win = self.calculate_progressive(player_hand)
            winnings += progressive_win
            details["progressive"] = progressive_win
        
        # 更新余额
        self.balance += winnings
        self.update_balance()
        self.last_win = winnings
        
        # 构建结果文本
        result_text = ""
        if details["ante"] > 0:
            result_text += f"Ante: ${details['ante']:.2f} "
        if details["blind"] > 0:
            result_text += f"Blind: ${details['blind']:.2f} "
        if details["trips"] > 0:
            result_text += f"Bonus: ${details['trips']:.2f} "
        if details["progressive"] > 0:
            result_text += f"Progressive: ${details['progressive']:.2f} "
        
        if not result_text:
            result_text = "送您好的运气！"
        else:
            result_text = "恭喜老板赢了！" + result_text

        # 所有文字一律黑色
        self.result_label.config(text=result_text, fg= '#FFD700')
        
        self.status_label.config(text="游戏结束")
        
        # 更新上局赢得金额
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        # 更新Jackpot显示
        self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")
        
        # 重置操作区域
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.reset_game, 
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=10)
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def calculate_progressive(self, player_hand):
        """计算Progressive奖金"""
        win_amount = 0
        if player_hand == "big_straight":
            win_amount = self.game.jackpot_amount * 0.03 + 300
            self.game.jackpot_amount -= win_amount
        elif player_hand == "small_straight":
            win_amount = self.game.jackpot_amount * 0.03 + 300
            self.game.jackpot_amount -= win_amount
        elif player_hand == "five_of_a_kind":
            win_amount = self.game.jackpot_amount * 0.1 + 1500
            self.game.jackpot_amount -= win_amount
        elif player_hand == "four_of_a_kind":
            win_amount = self.game.jackpot_amount * 0.05 + 500
            self.game.jackpot_amount -= win_amount
        
        # 确保奖池不低于4200
        if self.game.jackpot_amount < 4200:
            self.game.jackpot_amount = 4200
        
        # 保存更新后的奖池
        save_jackpot(self.game.jackpot_amount)
        
        return win_amount
    
    def reset_bets(self):
        """重置下注金额为0"""
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.trips_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        self.ante_display.config(bg='#FFCDD2')  # 浅红色
        self.blind_display.config(bg='#FFCDD2')
        self.trips_display.config(bg='#FFCDD2')
        self.after(500, lambda: [
            self.ante_display.config(bg='white'),
            self.blind_display.config(bg='white'),
            self.trips_display.config(bg='white')
        ])
    
    def animate_remove_dice(self, callback):
        """动画移除骰子"""
        # 收集所有骰子标签
        all_dice = []
        for frame in [self.dealer_dice_frame, self.player_dice_frame]:
            for dice_label in frame.winfo_children():
                if hasattr(dice_label, "dice_id"):
                    all_dice.append(dice_label)
        
        if not all_dice:
            callback()
            return
        
        # 目标位置（向右移出屏幕）
        target_x = 1000
        
        def move_dice():
            nonlocal all_dice
            remaining = []
            
            for dice_label in all_dice:
                try:
                    current_x = dice_label.winfo_x()
                    current_y = dice_label.winfo_y()
                    
                    # 计算新位置
                    new_x = current_x + 40  # 每次移动40像素
                    
                    if new_x < target_x:
                        dice_label.place(x=new_x, y=current_y, width=80, height=80)
                        remaining.append(dice_label)
                    else:
                        # 移动到屏幕外，销毁标签
                        dice_label.destroy()
                except tk.TclError:
                    # 标签已被销毁，跳过
                    pass
            
            all_dice = remaining
            
            if all_dice:
                self.after(50, move_dice)
            else:
                callback()
        
        # 开始动画
        move_dice()
    
    def reset_game(self, auto_reset=False):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 先动画移除骰子，然后重置游戏状态
        self.animate_remove_dice(lambda: self._finish_reset(auto_reset))
    
    def _finish_reset(self, auto_reset):
        """在动画移除骰子后完成重置"""
        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="阶段: 下注")
        self.status_label.config(text="设置下注金额并开始游戏")
        self.result_label.config(text="")
        
        # 重置标签显示
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        
        # 重置下注显示为0
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.trips_var.set("0")
        self.jackpot_bet_var.set(self.last_jackpot_state)
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.jackpot_check.config(bg='#2a4a3c')
        
        # 清空活动骰子列表
        self.active_dice_labels = []
        
        # 恢复下注区域
        self.ante_display.bind("<Button-1>", lambda e: [self.select_bet_area("ante"), self.add_chip_to_bet_area(e, "ante")])
        self.ante_display.bind("<Button-3>", lambda e: [self.select_bet_area("ante"), self.add_chip_to_bet_area(e, "ante")])
        self.trips_display.bind("<Button-1>", lambda e: [self.select_bet_area("trips"), self.add_chip_to_bet_area(e, "trips")])
        self.trips_display.bind("<Button-3>", lambda e: [self.select_bet_area("trips"), self.add_chip_to_bet_area(e, "trips")])
        for chip in self.chip_buttons:
            # 使用存储的文本重新绑定事件
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        
        # 恢复操作按钮区域
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=10)

        # 添加"重置金额"按钮
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重置金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

        # 开始游戏按钮
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        
        # 启用Jackpot的Checkbutton
        self.jackpot_check.config(state=tk.NORMAL)
        
        # 重置本局下注显示
        self.current_bet_label.config(text="本局下注: $0.00")
        
        # 如果是自动重置，显示消息
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

def main(initial_balance=1000, username="Guest"):
    app = KlondikeDiceGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")