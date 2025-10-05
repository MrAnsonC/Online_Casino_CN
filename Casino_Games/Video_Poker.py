import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import time, hashlib
import secrets
import subprocess, sys

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '同花大顺', 
    8: '同花顺', 
    7: '四条', 
    6: '葫芦', 
    5: '同花', 
    4: '顺子', 
    3: '三条', 
    2: '两对', 
    1: '对子', 
    0: '高牌'
}

# 视频扑克赔付表
VIDEO_POKER_PAYOUT = {
    9: 800,  # 皇家同花顺
    8: 50,   # 同花顺
    7: 25,   # 四条
    6: 9,    # 葫芦
    5: 6,    # 同花
    4: 4,    # 顺子
    3: 3,    # 三条
    2: 2,    # 两对
    1: 1     # J对子或以上
}

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

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]
    def __repr__(self):
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        # 获取当前脚本所在目录的上一级目录
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 新的Card文件夹路径
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        
        # 保证 Python 输出为 UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        try:
            # 调用外部 shuffle.py，超时 30 秒
            result = subprocess.run(
                [sys.executable, shuffle_script, "false", "1"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30
            )
            shuffle_data = json.loads(result.stdout)
            
            if "deck" not in shuffle_data or "cut_position" not in shuffle_data:
                raise ValueError("Invalid shuffle data format")
            
            # 用本模块的 Card 类实例化
            self.full_deck = [
                Card(d["suit"], d["rank"])
                for d in shuffle_data["deck"]
            ]
            self.cut_position = shuffle_data["cut_position"]
        
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
                ValueError,
                KeyError) as e:
            print(f"Error calling shuffle.py: {e}. Using fallback shuffle.")
            # fallback：标准顺序+安全乱序
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)
        
        # 通用的洗牌后索引 & 发牌序列逻辑
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]
    
    def _secure_shuffle(self):
        """Fisher–Yates 洗牌，用 secrets 保证随机性"""
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

def evaluate_five_card_hand(cards):
    """评估五张牌的手牌"""
    # 按牌面值排序（从大到小）
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    
    # 检查同花
    is_flush = len(set(suits)) == 1
    
    # 检查顺子
    values_sorted_asc = sorted([c.value for c in cards])  # 升序排序
    is_straight = False
    straight_values = None
    
    # 检查普通顺子
    if len(set(values_sorted_asc)) == 5:
        # 检查最大减最小是否为4
        if values_sorted_asc[-1] - values_sorted_asc[0] == 4:
            is_straight = True
            straight_values = sorted(values, reverse=True)  # 降序排列
        # 检查特殊顺子 A-2-3-4-5
        elif values_sorted_asc == [2, 3, 4, 5, 14]:
            is_straight = True
            straight_values = [5, 4, 3, 2, 1]  # 作为5-high顺子
    
    # 检查同花大顺（A,K,Q,J,10 同花）
    is_royal = is_straight and is_flush and values[0] == 14 and values[4] == 10
    
    # 同花顺（包括同花大顺）
    if is_straight and is_flush:
        return (9 if is_royal else 8, straight_values)
    
    # 计算每种点数的出现次数
    value_count = {}
    for v in values:
        value_count[v] = value_count.get(v, 0) + 1
    
    # 按出现次数和点数排序
    sorted_counts = sorted(value_count.items(), key=lambda x: (x[1], x[0]), reverse=True)
    sorted_values = [item[0] for item in sorted_counts]
    
    # 检查四条
    if sorted_counts[0][1] == 4:
        return (7, sorted_values)
    
    # 检查葫芦（三条+一对）
    if sorted_counts[0][1] == 3 and sorted_counts[1][1] == 2:
        return (6, sorted_values)
    
    # 同花
    if is_flush:
        return (5, values)
    
    # 顺子
    if is_straight:
        return (4, straight_values)
    
    # 三条
    if sorted_counts[0][1] == 3:
        return (3, sorted_values)
    
    # 两对
    if sorted_counts[0][1] == 2 and sorted_counts[1][1] == 2:
        return (2, sorted_values)
    
    # 对子（仅J以上）
    if sorted_counts[0][1] == 2:
        # 检查是否J以上
        pair_value = sorted_counts[0][0]
        if pair_value >= 11:  # J=11, Q=12, K=13, A=14
            return (1, sorted_values)
    
    # 高牌
    return (0, values)

class VideoPokerGame:
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.bet_amount = 0
        self.stage = "betting"  # betting, dealt, drawing, showdown
        self.hold_status = [False] * 5  # 每张牌的保留状态
        self.cards_revealed = [False] * 5
        self.final_hand = False

    def deal_initial(self):
        """发初始牌：玩家5张"""
        self.player_hand = self.deck.deal(5)
    
    def draw_cards(self):
        """替换未保留的牌"""
        for i in range(5):
            if not self.hold_status[i]:
                self.player_hand[i] = self.deck.deal(1)[0]
        self.final_hand = True

class VideoPokerGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("视频扑克")
        self.geometry("700x750+50+10")  # 增加高度以适应新布局
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = VideoPokerGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_buttons = []  # 跟踪所有活动中的卡片按钮
        self.selected_chip = None  # 当前选中的筹码
        self.chip_buttons = []  # 筹码按钮列表
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.card_buttons = []  # 存储牌按钮
        self.bet_widgets = {}  # 存储下注显示控件
        self.hold_labels = []  # 存储保留标签

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
        
    def _load_assets(self):
        card_size = (100, 140)  # 稍微增大卡片尺寸
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1')
        
        # 花色映射：将符号映射为英文名称
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club'
        }
        
        # 加载背面图片
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img = Image.open(back_path).resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception as e:
            print(f"Error loading back image: {e}")
            # 如果没有背景图，创建一个黑色背景
            img = Image.new('RGB', card_size, 'black')
            self.back_image = ImageTk.PhotoImage(img)
        
        # 加载扑克牌图片
        for suit in SUITS:
            for rank in RANKS:
                # 获取映射后的文件名
                suit_name = suit_mapping.get(suit, suit)
                
                # 尝试可能的文件名组合
                possible_filenames = [
                    f"{suit_name}{rank}.png",       # 如 "SpadeA.png"
                ]
                
                img_found = False
                for filename in possible_filenames:
                    path = os.path.join(card_dir, filename)
                    if os.path.exists(path):
                        try:
                            img = Image.open(path).resize(card_size)
                            self.card_images[(suit, rank)] = ImageTk.PhotoImage(img)
                            img_found = True
                            break
                        except Exception as e:
                            print(f"Error loading {path}: {e}")
                
                # 如果没有找到图片，创建一个占位图
                if not img_found:
                    print(f"Card image not found for {suit}{rank}")
                    img = Image.new('RGB', card_size, 'blue')
                    draw = ImageDraw.Draw(img)
                    # 在图片上绘制花色和点数
                    try:
                        font = ImageFont.truetype("arial.ttf", 18)
                        text = f"{suit}{rank}"
                        draw.text((10, 10), text, font=font, fill="white")
                    except:
                        # 如果字体加载失败，使用简单文本
                        draw.text((10, 10), f"{suit}{rank}", fill="white")
                    
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img)

    def add_chip_to_bet(self, bet_type):
        """添加筹码到下注区域"""
        if not self.selected_chip:
            return
            
        # 获取筹码金额
        chip_value = float(self.selected_chip.replace('$', '').replace('K', '000'))
        
        # 更新对应的下注变量
        if bet_type == "bet":
            current = float(self.bet_var.get())
            self.bet_var.set(str(int(current + chip_value)))
    
    def _create_widgets(self):
        # 主框架 - 上下布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部信息栏
        info_frame = tk.Frame(main_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
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
        
        # 扑克牌区域 - 使用Canvas提供更好的控制
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0, height=300)
        table_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 1050, 400, fill='#35654d', outline='')
        
        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER, width=700, height=250)
        
        # 扑克牌框架
        self.cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=30)
        
        # 创建5个牌按钮和保留标签
        self.card_buttons = []
        self.hold_labels = []
        for i in range(5):
            # 创建牌容器框架
            card_container = tk.Frame(self.cards_frame, bg='#2a4a3c')
            card_container.pack(side=tk.LEFT, padx=15)
            
            # 创建保留标签
            hold_label = tk.Label(
                card_container, 
                text="保留", 
                font=('Arial', 10, 'bold'), 
                bg='gold', 
                fg='black',
                padx=5
            )
            hold_label.pack(side=tk.TOP, fill=tk.X)
            hold_label.pack_forget()  # 初始隐藏
            self.hold_labels.append(hold_label)
            
            # 创建按钮并设置初始背面图片
            card_btn = tk.Button(
                card_container,
                image=self.back_image,
                command=lambda idx=i: self.toggle_hold(idx),
                bg='#2a4a3c',
                bd=0,
                relief='flat',
                highlightthickness=0
            )
            card_btn.pack(side=tk.TOP)
            self.card_buttons.append(card_btn)
        
        # 底部控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', height=200)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        
        # 单行放置5个筹码
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs = [
            ("$5", '#ff0000', 'white'),     # 红色背景，白色文字
            ('$10', '#ffa500', 'black'),   # 橙色背景，黑色文字
            ("$25", '#00ff00', 'black'),    # 绿色背景，黑色文字
            ("$50", '#ffffff', 'black'),    # 白色背景，黑色文字
            ("$100", '#000000', 'white'),   # 黑色背景，白色文字
        ]
        
        self.chip_buttons = []
        self.chip_texts = {}  # 存储每个筹码按钮的文本
        for text, bg_color, fg_color in chip_configs:
            # 使用Canvas创建圆形筹码
            chip_canvas = tk.Canvas(chip_row, width=60, height=60, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 58, 58, fill=bg_color, outline='black')
            text_id = chip_canvas.create_text(30, 30, text=text, fill=fg_color, font=('Arial', 16, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text  # 存储文本
        
        # 默认选中$5筹码
        self.select_chip("$5")
        
        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=5)
        
        # Bet 区域
        bet_inner_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        bet_inner_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.bet_label = tk.Label(bet_inner_frame, text="下注金额:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        self.bet_label.pack(side=tk.LEFT)
        
        self.bet_var = tk.StringVar(value="0")
        self.bet_display = tk.Label(bet_inner_frame, textvariable=self.bet_var, font=('Arial', 12), 
                                   bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.bet_display.pack(side=tk.LEFT, padx=5)
        self.bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet"))
        self.bet_widgets["bet"] = self.bet_display
        
        # 游戏操作按钮框架
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X, pady=10)

        # 创建按钮框架
        button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        button_frame.pack(pady=10)

        # 添加"重置金额"按钮
        self.reset_bets_button = tk.Button(
            button_frame, text="重置金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

        # 开始游戏按钮
        self.start_button = tk.Button(
            button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        
        # 抽牌按钮 (初始禁用)
        self.draw_button = tk.Button(
            button_frame, text="抽牌", 
            command=self.draw_action,
            state=tk.DISABLED,
            font=('Arial', 14), bg='#2196F3', fg='white', width=10
        )
        self.draw_button.pack(side=tk.LEFT, padx=(10, 0))
        
        # 状态信息
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 12), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)
        
        # 添加游戏规则按钮到上局获胜的右下角
        rules_btn = tk.Button(
            control_frame, text="ℹ️", 
            command=self.show_game_instructions, 
            font=('Arial', 18), bg='#4B8BBE', fg='white', width=2, height=1
        )
        rules_btn.pack(side=tk.RIGHT)
    
    def show_game_instructions(self):
        """显示游戏规则说明"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("视频扑克游戏规则")
        win.geometry("800x650")
        win.resizable(False, False)
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
        视频扑克 游戏规则

        1. 游戏开始前下注:
           - 选择下注金额（至少$5）

        2. 游戏流程:
           a. 下注阶段:
               - 玩家下注
               - 点击"开始游戏"按钮开始

           b. 发牌:
               - 玩家获得五张牌
               - 牌面朝上显示

           c. 保留阶段:
               - 点击牌选择保留（再次点击取消）
               - 点击"抽牌"按钮替换未保留的牌

           d. 结算:
               - 根据最终牌型按支付表赔付
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
        
        # 赔付表
        tk.Label(
            content_frame, 
            text="赔付表 (每单位下注)",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        payout_frame = tk.Frame(content_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "赔付"]
        payout_data = [
            ("皇家同花顺", "800:1"),
            ("同花顺", "50:1"),
            ("四条", "25:1"),
            ("葫芦", "9:1"),
            ("同花", "6:1"),
            ("顺子", "4:1"),
            ("三条", "3:1"),
            ("两对", "2:1"),
            ("J对子或以上", "1:1")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                payout_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(payout_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    payout_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度
        for c in range(len(headers)):
            payout_frame.columnconfigure(c, weight=1)
            
        # 注释
        notes = """
        注: 
        * 皇家同花顺: A,K,Q,J,10 同花
        * 同花顺: 同花色的顺子
        * 四条: 四张相同点数的牌
        * 葫芦: 三张相同点数的牌加一对
        * 同花: 五张同花色的牌
        * 顺子: 五张连续的牌（不同花色）
        * 三条: 三张相同点数的牌
        * 两对: 两个对子
        * J对子或以上: 一对J、Q、K或A
        * 点击扑克牌选择保留/取消保留
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
    
    def update_hand_label(self):
        """更新玩家的手牌标签显示牌型"""
        if self.game.player_hand:
            player_eval = evaluate_five_card_hand(self.game.player_hand)
            player_hand_name = HAND_RANK_NAMES[player_eval[0]] if player_eval else ""
            # 不再需要单独标签，因为牌型会显示在结果标签中
    
    def disable_action_buttons(self):
        """禁用所有操作按钮"""
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            # 只对按钮控件禁用
            if isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)
        
    def enable_action_buttons(self):
        """启用所有操作按钮"""
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            # 只对按钮控件启用
            if isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)
    
    def toggle_hold(self, idx):
        """切换牌的保留状态"""
        if self.game.stage != "dealt" or self.buttons_disabled:
            return
            
        # 切换保留状态
        self.game.hold_status[idx] = not self.game.hold_status[idx]
        
        # 更新保留标签显示状态
        if self.game.hold_status[idx]:
            self.hold_labels[idx].pack(side=tk.TOP, fill=tk.X)
        else:
            self.hold_labels[idx].pack_forget()
    
    def start_game(self):
        try:
            bet_amount = int(self.bet_var.get())
            
            # 检查下注金额至少5块
            if bet_amount < 5:
                messagebox.showerror("错误", "下注金额至少需要5块")
                return
                
            if self.balance < bet_amount:
                messagebox.showwarning("警告", "余额不足")
                return
                
            self.balance -= bet_amount
            self.update_balance()
            
            # 重置游戏状态
            self.game.reset_game()
            self.game.bet_amount = bet_amount
            self.game.deal_initial()
            
            # 重置所有牌按钮和保留标签
            for btn in self.card_buttons:
                btn.config(image=self.back_image)
            for label in self.hold_labels:
                label.pack_forget()
            
            # 设置动画队列
            self.animation_queue = [i for i in range(5)]  # 初始化动画队列为5张牌的索引
            
            # 更新游戏状态
            self.stage_label.config(text="阶段: 发牌")
            self.status_label.config(text="发牌中...")

            # 禁用下注区域
            self.bet_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            
            # 禁用开始按钮
            self.start_button.config(state=tk.DISABLED)
            self.draw_button.config(state=tk.DISABLED)
            
            # 开始动画
            self.animate_deal()
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
    
    def animate_deal(self):
        """执行发牌动画"""
        if not self.animation_queue:
            self.animation_in_progress = False
            # 发牌动画完成后翻开玩家牌
            self.after(500, self.reveal_player_cards)
            return
            
        self.animation_in_progress = True
        idx = self.animation_queue.pop(0)
        card = self.game.player_hand[idx]
        
        # 更新按钮图像
        self.card_buttons[idx].config(image=self.card_images.get((card.suit, card.rank), self.back_image))
        
        # 继续处理下一张牌
        self.after(200, self.animate_deal)
    
    def reveal_player_cards(self):
        """翻开玩家牌（带动画）"""
        # 更新玩家牌型
        self.update_hand_label()
        
        # 更新游戏阶段
        self.game.stage = "dealt"
        self.stage_label.config(text="阶段: 选择保留牌")
        self.status_label.config(text="选择要保留的牌，然后点击抽牌")
        
        # 启用抽牌按钮
        self.draw_button.config(state=tk.NORMAL)
        
        # 允许玩家点击牌进行保留
        self.buttons_disabled = False
    
    def draw_action(self):
        """玩家选择抽牌"""
        # 禁用抽牌按钮
        self.draw_button.config(state=tk.DISABLED)
        
        # 禁用牌按钮（防止在动画期间点击）
        for btn in self.card_buttons:
            btn.config(state=tk.DISABLED)
        
        # 抽牌
        self.game.draw_cards()
        self.stage_label.config(text="阶段: 结算")
        self.status_label.config(text="抽牌中...")
        
        # 创建动画队列（只包含需要替换的牌）
        self.animation_queue = []
        for i in range(5):
            if not self.game.hold_status[i]:
                self.animation_queue.append(i)
        
        # 开始动画
        self.animate_draw()

    def animate_draw(self):
        """执行抽牌动画"""
        if not self.animation_queue:
            self.animation_in_progress = False
            # 动画完成后结算
            self.after(500, self.show_showdown)
            return
            
        self.animation_in_progress = True
        idx = self.animation_queue.pop(0)
        card = self.game.player_hand[idx]
        
        # 更新按钮图像（显示新牌）
        self.card_buttons[idx].config(
            image=self.card_images.get((card.suit, card.rank), self.back_image)
        )
        
        # 继续处理下一张牌
        self.after(200, self.animate_draw)
    
    def show_showdown(self):
        # 更新所有牌图像
        for i, card in enumerate(self.game.player_hand):
            self.card_buttons[i].config(image=self.card_images.get((card.suit, card.rank), self.back_image))
        
        # 结算
        winnings = self.calculate_winnings()
        self.last_win = winnings
        
        # 更新余额
        self.balance += winnings
        self.update_balance()
        
        # 构建消息
        rank, _ = evaluate_five_card_hand(self.game.player_hand)
        hand_name = HAND_RANK_NAMES.get(rank, "高牌")
        payout = VIDEO_POKER_PAYOUT.get(rank, 0)
        
        # 根据输赢设置消息和下注金额显示控件的背景色
        if winnings > 0:
            # 赢了，将下注金额显示控件背景设为金色
            self.bet_display.config(bg='gold')
            self.bet_var.set(f"{winnings}")
            message = f"本局是{hand_name}，赔率为{payout}:1，你赢了${winnings}！"
        else:
            # 输了，设为灰色
            self.bet_display.config(bg="#ffffff")
            self.bet_var.set("0")
            message = f"送您好运气。"
        
        # 更新状态标签
        self.status_label.config(text=message)
        
        # 清空操作按钮区域
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        # 添加再来一局按钮
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.reset_game, 
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=10)
        
        # 设置30秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def calculate_winnings(self):
        """计算赢得的金额"""
        rank, _ = evaluate_five_card_hand(self.game.player_hand)
        payout = VIDEO_POKER_PAYOUT.get(rank, 0)
        if payout > 0:
            return self.game.bet_amount + (self.game.bet_amount * payout)
        else:
            return 0

    def animate_collect_cards(self, auto_reset):
        """执行收牌动画：先翻转所有牌为背面，然后向右收起"""
        # 禁用所有按钮
        self.disable_action_buttons()
        
        # 第一步：翻转所有牌为背面
        self.flip_all_to_back()
        
        # 第二步：设置动画完成后执行真正的重置
        self.after(1000, lambda: self.animate_move_cards_out(auto_reset))

    def flip_all_to_back(self):
        """将所有牌翻转为背面"""
        for btn in self.card_buttons:
            btn.config(image=self.back_image)
            btn.config(state=tk.NORMAL)
        for label in self.hold_labels:
            label.pack_forget()
        
        # 开始移动动画
        self.after(500, lambda: self.animate_move_cards_out(False))

    def animate_move_cards_out(self, auto_reset):
        """将所有牌向右移出屏幕"""
        # 这里简化处理，直接重置
        self._do_reset(auto_reset)

    def reset_game(self, auto_reset=False):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 如果当前有牌在桌上，先执行收牌动画
        if self.game.stage != "betting":
            self.disable_action_buttons()  # 禁用按钮
            self.animate_collect_cards(auto_reset)  # 开始收牌动画，动画完成后会调用真正的重置
            return

        # 否则直接重置
        self._do_reset(auto_reset)
    
    def reset_bets(self):
        """重置下注金额为0"""
        self.bet_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        self.bet_display.config(bg='#FFCDD2')  # 浅红色
        self.after(500, lambda: self.bet_display.config(bg='white'))
    
    def _do_reset(self, auto_reset=False):
        """真正的重置游戏界面"""
        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="阶段: 下注")
        self.status_label.config(text="设置下注金额并开始游戏")

        # 重置牌按钮和保留标签
        for btn in self.card_buttons:
            btn.config(image=self.back_image)
        for label in self.hold_labels:
            label.pack_forget()

        # 重置下注金额为0
        self.bet_var.set("0")

        # 重置背景色为白色
        self.bet_display.config(bg='white')

        # 恢复下注区域
        self.bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bet"))
        for chip in self.chip_buttons:
            # 使用存储的文本重新绑定事件
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))

        # 恢复操作按钮区域
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        button_frame.pack(pady=10)

        # 添加"重置金额"按钮
        self.reset_bets_button = tk.Button(
            button_frame, text="重置金额",
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

        # 开始游戏按钮
        self.start_button = tk.Button(
            button_frame, text="开始游戏",
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)

        # 抽牌按钮 (初始禁用)
        self.draw_button = tk.Button(
            button_frame, text="抽牌",
            command=self.draw_action,
            state=tk.DISABLED,            # 初始禁用
            font=('Arial', 14), bg='#2196F3', fg='white', width=10
        )
        self.draw_button.pack(side=tk.LEFT, padx=(10, 0))

        # 启用按钮操作（将禁用标志设为False）
        self.buttons_disabled = False

        # 如果是自动重置，显示消息
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))

def main(initial_balance=1000, username="Guest"):
    app = VideoPokerGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")