import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import hashlib
import time
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

# 加勒比扑克赔付表
CARIBBEAN_STUD_PAYOUT = {
    9: 100,  # 同花大顺 100:1
    8: 50,   # 同花顺 50:1
    7: 20,   # 四条 20:1
    6: 7,    # 葫芦 7:1
    5: 5,    # 同花 5:1
    4: 4,    # 顺子 4:1
    3: 3,    # 三条 3:1
    2: 2,    # 两对 2:1
    1: 1,    # 对子 1:1
    0: 1     # 高牌 1:1
}

# Bonus赔付表
BONUS_PAYOUT = {
    "royal_flush": "赢得整个Jackpot",
    "straight_flush": "赢得Jackpot的10%",
    "four_of_a_kind": "$500",
    "full_house": "$100",
    "flush": "$75"
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

# Jackpot 文件加载与保存
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    default_jackpot = 197301.26
    # 文件不存在时使用默认奖池
    if not os.path.exists(path):
        return True, default_jackpot
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'CSP':
                    return False, float(item.get('jackpot', default_jackpot))
    except Exception:
        return True, default_jackpot
    # 未找到 CSP 条目时也使用默认
    return True, default_jackpot

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
    
    # 查找是否已有CSP的记录
    found = False
    for item in data:
        if item.get('Games') == 'CSP':
            item['jackpot'] = jackpot
            found = True
            break
    
    if not found:
        data.append({"Games": "CSP", "jackpot": jackpot})
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

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
                [sys.executable, shuffle_script],
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

def sort_hand_by_rank(hand):
    """根据牌型对手牌进行排序"""
    # 获取牌型
    if not hand or len(hand) < 5:  # 确保手牌完整
        return hand
        
    rank, sorted_values = evaluate_five_card_hand(hand)
    
    # 根据牌型进行排序：
    if rank in [0, 5, 7]:  # 高牌、同花、四条：按牌面值从大到小
        return sorted(hand, key=lambda c: c.value, reverse=True)
    
    elif rank == 1:  # 对子
        # 找出对子的点数
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        pair_value = None
        singles = []
        for value, count in counts.items():
            if count == 2:
                pair_value = value
            else:
                singles.append(value)
        # 对子在前，然后单张从大到小
        sorted_hand = []
        # 先添加对子（两张）
        for card in hand:
            if card.value == pair_value:
                sorted_hand.append(card)
        # 再添加单张，按值从大到小
        singles_sorted = sorted(singles, reverse=True)
        for value in singles_sorted:
            for card in hand:
                if card.value == value and card not in sorted_hand:
                    sorted_hand.append(card)
                    break
        return sorted_hand
    
    # 两对：先大对子再小对子，然后单张
    elif rank == 2:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        pair_values = []
        single_value = None
        for value, count in counts.items():
            if count == 2:
                pair_values.append(value)
            else:
                single_value = value
        # 对子按从大到小排序
        pair_values_sorted = sorted(pair_values, reverse=True)
        sorted_hand = []
        # 先添加大对子
        for value in pair_values_sorted:
            for card in hand:
                if card.value == value and card not in sorted_hand:
                    sorted_hand.append(card)
        # 再添加小对子
        for value in pair_values_sorted:
            for card in hand:
                if card.value == value and card not in sorted_hand:
                    sorted_hand.append(card)
        # 然后添加单张
        for card in hand:
            if card.value == single_value and card not in sorted_hand:
                sorted_hand.append(card)
        return sorted_hand
    
    # 三条：三条在前，然后单张从大到小
    elif rank == 3:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        three_value = None
        singles = []
        for value, count in counts.items():
            if count == 3:
                three_value = value
            else:
                singles.append(value)
        singles_sorted = sorted(singles, reverse=True)
        sorted_hand = []
        # 先添加三条
        for card in hand:
            if card.value == three_value:
                sorted_hand.append(card)
        # 再添加单张，按值从大到小
        for value in singles_sorted:
            for card in hand:
                if card.value == value and card not in sorted_hand:
                    sorted_hand.append(card)
                    break
        return sorted_hand
    
    # 顺子：按顺序排列
    elif rank in [4, 8, 9]:  # 包括同花顺和皇家顺
        # 先按点数排序（升序）
        sorted_by_value = sorted(hand, key=lambda c: c.value)
        # 检查是否是A-2-3-4-5（即最小的顺子，其中A是1）
        if sorted_by_value[0].value == 2 and sorted_by_value[-1].value == 14:
            # 将A移到最前面
            aces = [card for card in sorted_by_value if card.value == 14]
            non_aces = [card for card in sorted_by_value if card.value != 14]
            sorted_hand = aces + non_aces
            return sorted_hand
        else:
            # 普通顺子，按升序排列（最小在左，最大在右）
            return sorted_by_value
    
    # 葫芦：三条在前，然后对子
    elif rank == 6:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        three_value = None
        pair_value = None
        for value, count in counts.items():
            if count == 3:
                three_value = value
            else:
                pair_value = value
        sorted_hand = []
        # 先添加三条
        for card in hand:
            if card.value == three_value:
                sorted_hand.append(card)
        # 再添加对子
        for card in hand:
            if card.value == pair_value:
                sorted_hand.append(card)
        return sorted_hand
    
    # 默认按牌面值从大到小
    return sorted(hand, key=lambda c: c.value, reverse=True)

def evaluate_five_card_hand(cards):
    """评估五张牌的手牌"""
    if not cards or len(cards) < 5:  # 确保手牌完整
        return (0, [])
    
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
    
    # 一对
    if sorted_counts[0][1] == 2:
        return (1, sorted_values)
    
    # 高牌
    return (0, values)

def compare_hands(hand1, hand2):
    """比较两手牌，返回1表示hand1赢，0表示平局，-1表示hand2赢"""
    # 确保两手牌完整
    if not hand1 or len(hand1) < 5 or not hand2 or len(hand2) < 5:
        return 0
        
    rank1, values1 = evaluate_five_card_hand(hand1)
    rank2, values2 = evaluate_five_card_hand(hand2)
    
    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1
    else:
        # 相同牌型，比较点数
        # 对于对子、两对等牌型，values列表长度可能不同
        min_len = min(len(values1), len(values2))
        for i in range(min_len):
            if values1[i] > values2[i]:
                return 1
            elif values1[i] < values2[i]:
                return -1
        
        # 如果前min_len个值相同，比较原始牌值
        values1_full = sorted([c.value for c in hand1], reverse=True)
        values2_full = sorted([c.value for c in hand2], reverse=True)
        for i in range(len(values1_full)):
            if values1_full[i] > values2_full[i]:
                return 1
            elif values1_full[i] < values2_full[i]:
                return -1
        return 0

class CaribbeanStudGame:
    def __init__(self):
        self.reset_game()
        # 初始化Jackpot
        self.jackpot_amount = load_jackpot()[1]
        self.initial_jackpot = self.jackpot_amount  # 保存初始值用于重置
        # 添加牌序记录
        self.card_sequence = []  # 记录整副牌的序列
        self.cut_position = 0    # 切牌位置
    
    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.ante = 0
        self.jackpot_bet = 0
        self.play_bet = 0
        self.stage = "pre_flop"  # pre_flop, decision, showdown
        self.folded = False
        self.cards_revealed = {
            "player": [False, False, False, False, False],
            "dealer": [False, False, False, False, False]
        }
        # 记录牌序和切牌位置
        self.card_sequence = self.deck.full_deck.copy()
        self.cut_position = self.deck.cut_position
    
    def deal_initial(self):
        """发初始牌：玩家5张，庄家5张"""
        self.player_hand = self.deck.deal(5)
        self.dealer_hand = self.deck.deal(5)
    
    def dealer_qualifies(self):
        """庄家是否合格（高牌且同时包含A和K）"""
        # 确保手牌完整
        if not self.dealer_hand or len(self.dealer_hand) < 5:
            return False
            
        # 评估庄家手牌牌型
        rank, _ = evaluate_five_card_hand(self.dealer_hand)
        
        # 如果牌型高于高牌（即至少是对子），则合格
        if rank >= 1:
            return True
        
        # 如果是高牌，检查是否同时包含A和K
        has_ace = any(card.rank == 'A' for card in self.dealer_hand)
        has_king = any(card.rank == 'K' for card in self.dealer_hand)
        
        # 只有同时有A和K才算合格
        return has_ace and has_king

class CaribbeanStudGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("加勒比扑克")
        self.geometry("1050x660+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = CaribbeanStudGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []  # 跟踪所有活动中的卡片标签
        self.selected_chip = None  # 当前选中的筹码
        self.chip_buttons = []  # 筹码按钮列表
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.last_jackpot_state = 0
        self.win_details = {
            "ante": 0,
            "play": 0,
            "bonus": 0
        }
        self.bet_widgets = {}  # 存储下注显示控件
        self.jackpot_bet_var = tk.IntVar(value=0)  # Jackpot下注变量
        self.flipping_cards = []  # 存储正在翻转的卡片
        self.flip_step = 0  # 翻转动画的当前步骤
        self.moved_cards = []  # 存储下移的卡片
        self.ak_moved = False  # 标记是否移动了AK牌
        self.fold_button = None  # 弃牌按钮引用
        self.play_button = None  # 下注按钮引用
        self.ak_animation_active = False  # 标记AK动画是否进行中

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
        card_size = (80, 120)  # 缩小卡片尺寸以适应5张牌
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        
        # 花色映射：将符号映射为英文名称
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club'
        }
        
        # 存储原始图像对象
        self.original_images = {}
        
        # 加载背面图片
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img = Image.open(back_path)
            # 使用新的图像缩放方法
            self.back_image = ImageTk.PhotoImage(back_img.resize(card_size, Image.LANCZOS))
            self.original_images["back"] = back_img  # 保存原始背面图像
        except Exception as e:
            print(f"Error loading back image: {e}")
            # 如果没有背景图，创建一个黑色背景
            img = Image.new('RGB', card_size, 'black')
            self.back_image = ImageTk.PhotoImage(img)
            self.original_images["back"] = img
        
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
                            img = Image.open(path)
                            # 保存原始图像
                            self.original_images[(suit, rank)] = img
                            # 使用新的图像缩放方法
                            resized_img = img.resize(card_size, Image.LANCZOS)
                            self.card_images[(suit, rank)] = ImageTk.PhotoImage(resized_img)
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
                    self.original_images[(suit, rank)] = img.copy()

    def add_chip_to_bet(self, bet_type):
        """添加筹码到下注区域"""
        if not self.selected_chip:
            return
            
        # 获取筹码金额
        chip_value = float(self.selected_chip.replace('$', '').replace('K', '000'))
        
        # 更新对应的下注变量
        if bet_type == "ante":
            current = float(self.ante_var.get())
            self.ante_var.set(str(int(current + chip_value)))
            # 如果Play已经有值，则更新Play为Ante的2倍
            if int(self.play_var.get()) > 0:
                self.play_var.set(str(int((current + chip_value) * 2)))
    
    def toggle_play_bet(self, event):
        """切换Play下注状态"""
        # 如果游戏已经开始，则忽略点击
        if self.game.stage != "pre_flop":
            return
            
        try:
            ante_value = int(self.ante_var.get())
        except:
            ante_value = 0
            
        current_play = self.play_var.get()
        try:
            current_play_value = int(current_play)
        except:
            current_play_value = 0
            
        # 如果Ante为0，不做任何操作
        if ante_value == 0:
            return
            
        # 如果Play当前为0，则设置为Ante的2倍
        if current_play_value == 0:
            self.play_var.set(str(ante_value * 2))
        # 如果Play已有值，则重置为0
        else:
            self.play_var.set("0")
    
    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域 - 使用Canvas提供更好的控制
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 庄家区域 - 固定高度200
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=50, width=500, height=230)  # 加宽以适应5张牌
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 在庄家和玩家区域之间添加提示文字
        self.ante_info_label = tk.Label(
            table_canvas, 
            text="庄家不合格 玩家赢Ante 退还Play", 
            font=('Arial', 20), 
            bg='#35654d', 
            fg='#FFD700'
        )

        # 更新以获取宽度
        self.ante_info_label.update_idletasks()
        label_width = self.ante_info_label.winfo_width()

        # 获取 canvas 宽度
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()

        # 居中放置在庄家和玩家区域之间（然后向左偏移50像素）
        center_x = (canvas_width - label_width) // 2
        self.ante_info_label.place(x=center_x + 300, y=300, anchor='n')  # 向左移动50像素
        
        # 玩家区域 - 固定高度200
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=350, width=500, height=230)  # 加宽以适应5张牌
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
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
        
        # 创建一个内部框架用于居中
        jackpot_inner_frame = tk.Frame(jackpot_frame, bg='#2a4a3c')
        jackpot_inner_frame.pack(expand=True, pady=5)  # 使用expand和居中

        jackpot_label = tk.Label(jackpot_inner_frame, text="Progressive:", 
                                font=('Arial', 18), bg='#2a4a3c', fg='gold')
        jackpot_label.pack(side=tk.LEFT, padx=(0, 5))  # 右侧留5像素间距

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
        
        # 单行放置5个筹码 - 增加50%大小
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
            # 使用Canvas创建圆形筹码 - 增加50%大小 (60x60)
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
        bet_frame.pack(fill=tk.X, pady=10)
        
        # Jackpot下注区域
        bonus_bet_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        bonus_bet_frame.pack(fill=tk.X, padx=20, pady=5)
        
        # Jackpot下注
        self.jackpot_check = tk.Checkbutton(
            bonus_bet_frame, 
            text="Progressive ($1)", 
            variable=self.jackpot_bet_var,
            font=('Arial', 12), 
            bg='#2a4a3c', 
            fg='white', 
            selectcolor='black'
        )
        self.jackpot_check.pack(side=tk.LEFT)
        
        # Ante 和 Play 在同一行
        ante_play_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        ante_play_frame.pack(fill=tk.X, padx=20, pady=5)
        
        # Ante 部分
        ante_label = tk.Label(ante_play_frame, text="Ante:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        ante_label.pack(side=tk.LEFT)
        
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(ante_play_frame, textvariable=self.ante_var, font=('Arial', 12), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display
        
        # 添加间距
        tk.Label(ante_play_frame, text="   ", bg='#2a4a3c').pack(side=tk.LEFT)
        
        # Play 部分
        self.play_label = tk.Label(ante_play_frame, text="Play:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        self.play_label.pack(side=tk.LEFT)
        
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(ante_play_frame, textvariable=self.play_var, font=('Arial', 12), 
                                bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.play_display.pack(side=tk.LEFT, padx=5)
        # Play Bet 点击事件
        self.play_display.bind("<Button-1>", self.toggle_play_bet)
        self.bet_widgets["play"] = self.play_display
        
        # 添加提示文字
        tip_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        tip_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        tip_label = tk.Label(
            tip_frame, 
            text="庄家A和K的高牌或以上牌型合格", 
            font=('Arial', 14, 'bold'), 
            bg='#2a4a3c', 
            fg='#FFD700'
        )
        tip_label.pack(side=tk.LEFT)
        
        # 游戏操作按钮框架 - 用于放置所有操作按钮
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
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("加勒比扑克游戏规则")
        win.geometry("800x650")
        win.resizable(0,0)
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
        加勒比扑克 (Caribbean Stud Poker) 游戏规则

        1. 游戏开始前下注:
           - Ante: 基础下注（必须）
           - Progressive: 可选$1下注（参与Bonus奖励）

        2. 游戏流程:
           a. 下注阶段:
               - 玩家下注Ante
               - 可选择下注$1参与Jackpot奖金
               - 点击"开始游戏"按钮开始

           b. 发牌:
               - 玩家和庄家各发五张牌
               - 玩家牌面朝上，庄家牌面朝下（只显示第一张）

           c. 决策阶段:
               - 玩家查看自己的五张牌后选择:
                 * 弃牌: 输掉Ante下注，但Progressive可能赢
                 * 下注2X: 下注金额等于Ante

           d. 摊牌:
               - 庄家开牌
               - 庄家必须有一张A和K才能合格
               - 结算所有下注

        3. 结算规则:
           - Ante和Bet:
             * 如果庄家不合格:
                 - Ante支付1:1
                 - Bet: 退还
             * 如果庄家合格:
                 - 比较玩家和庄家的牌:
                   - 玩家赢: Ante支付1:1，Bet根据玩家牌型支付（见赔率表）
                   - 平局: Ante和Bet都退还
                   - 玩家输: 输掉Ante和Bet
                   
           - Progressive (需下注Progressive):
             * 根据玩家手牌支付（无论庄家是否合格）
             * 赔付表见下方
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
        
        # Bet赔付表
        tk.Label(
            content_frame, 
            text="Bet 赔付表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        odds_frame = tk.Frame(content_frame, bg='#F0F0F0')
        odds_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "赔率"]
        odds_data = [
            ("同花大顺", "100:1"),
            ("同花顺", "50:1"),
            ("四条", "20:1"),
            ("葫芦", "7:1"),
            ("同花", "5:1"),
            ("顺子", "4:1"),
            ("三条", "3:1"),
            ("两对", "2:1"),
            ("对子", "1:1"),
            ("高牌", "1:1")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                odds_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(odds_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    odds_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度，让 sticky='nsew' 生效
        for c in range(len(headers)):
            odds_frame.columnconfigure(c, weight=1)
        # 可选：也给行设置权重，支持垂直拉伸
        for r in range(len(odds_data) + 1):
            odds_frame.rowconfigure(r, weight=1)
            
        # Jackpot赔付表
        tk.Label(
            content_frame, 
            text="Jackpot 赔付表 (需下注Jackpot)",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        jackpot_frame = tk.Frame(content_frame, bg='#F0F0F0')
        jackpot_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "奖励"]
        jackpot_data = [
            ("同花大顺", "赢得整个Jackpot"),
            ("同花顺", "赢得Jackpot的10%"),
            ("四条", "$500"),
            ("葫芦", "$100"),
            ("同花", "$75")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                jackpot_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(jackpot_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    jackpot_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度
        for c in range(len(headers)):
            jackpot_frame.columnconfigure(c, weight=1)
            
        # 注释
        notes = """
        注: 
        * 庄家必须至少有一张A和K才合格
        * Bet 金额等于Ante下注金额
        * Progressive奖励需要下注Progressive($1)才有效
        * 同花大顺赢得整个Progressive后，Progressive将重置为初始值
        * 同花顺赢得当前Progressive的10%
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
        """更新玩家和庄家的手牌标签显示牌型"""
        # 计算玩家当前牌型
        if self.game.player_hand and len(self.game.player_hand) == 5:
            player_eval = evaluate_five_card_hand(self.game.player_hand)
            player_hand_name = HAND_RANK_NAMES[player_eval[0]] if player_eval else ""
            self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")
        
        # 计算庄家当前牌型（只有在摊牌时）
        if (self.game.stage == "showdown" or self.game.folded) and self.game.dealer_hand and len(self.game.dealer_hand) == 5:
            dealer_eval = evaluate_five_card_hand(self.game.dealer_hand)
            dealer_hand_name = HAND_RANK_NAMES[dealer_eval[0]] if dealer_eval else ""
            self.dealer_label.config(text=f"庄家 - {dealer_hand_name}" if dealer_hand_name else "庄家")
    
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
    
    def sort_player_hand(self):
        """根据牌型对玩家手牌进行排序并更新显示"""
        # 排序玩家手牌
        sorted_hand = sort_hand_by_rank(self.game.player_hand)
        self.game.player_hand = sorted_hand
        
        # 清除玩家区域的卡片
        for widget in self.player_cards_frame.winfo_children():
            widget.destroy()
        
        # 重新放置玩家卡片（按新顺序），确保完整显示
        for i, card in enumerate(sorted_hand):
            # 确保卡片标签有足够的空间显示
            card_label = tk.Label(
                self.player_cards_frame, 
                image=self.back_image,  # 先显示背面
                bg='#2a4a3c',
                width=90,  # 增加宽度确保完整显示
                height=130  # 增加高度确保完整显示
            )
            # 使用place布局并设置合适的偏移量
            card_label.place(x=i*90, y=0, width=90, height=130)
            card_label.card = card
            card_label.is_face_up = False
            # 添加到活动卡片列表
            self.active_card_labels.append(card_label)
        
        # 更新玩家牌型标签
        self.update_hand_labels()
        
        # 将所有玩家牌翻到正面
        self.flip_all_player_cards_to_front()
    
    def flip_all_player_cards_to_front(self):
        """将所有玩家牌翻转到正面"""
        # 收集所有玩家牌
        self.flipping_cards = []
        for card_label in self.player_cards_frame.winfo_children():
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flipping_cards.append(card_label)
        
        # 如果没有需要翻转的卡片，直接返回
        if not self.flipping_cards:
            # 动画完成，启用决策按钮（如果不是自动下注模式）
            if self.fold_button and self.play_button and self.game.play_bet == 0:
                self.fold_button.config(state=tk.NORMAL)
                self.play_button.config(state=tk.NORMAL)
            else:
                # 自动下注模式：等待2秒后自动下注
                if self.game.stage == "pre_flop" and self.game.play_bet > 0:
                    self.after(2000, self.auto_play_action)
            return
            
        # 开始翻转动画
        self.flip_step = 0
        self.animate_flip_to_front_step()
    
    def animate_flip_to_front_step(self):
        """执行翻转动画的每一步（翻到正面）"""
        if self.flip_step > 10:  # 假设10步完成
            # 翻转完成，将所有正在翻转的卡片设为正面
            for card_label in self.flipping_cards:
                if hasattr(card_label, "card"):
                    card = card_label.card
                    front_img = self.card_images.get((card.suit, card.rank), self.back_image)
                    card_label.config(image=front_img)
                    card_label.is_face_up = True
                    # 重置宽度为正常值 - 关键修复
                    card_label.place(width=80, height=120)
                    
            # 修改开始：安全地检查按钮状态
            try:
                # 动画完成，启用决策按钮（如果不是自动下注模式）
                if (self.fold_button and self.play_button and 
                    self.fold_button.winfo_exists() and 
                    self.play_button.winfo_exists() and 
                    self.game.play_bet == 0):
                    
                    self.fold_button.config(state=tk.NORMAL)
                    self.play_button.config(state=tk.NORMAL)
                else:
                    # 自动下注模式：等待2秒后自动下注
                    if self.game.stage == "pre_flop" and self.game.play_bet > 0:
                        self.after(2000, self.auto_play_action)
            except tk.TclError:
                # 按钮已被销毁，忽略错误
                pass
            # 修改结束
            
            return

        # 模拟翻转效果
        width = 80 - (self.flip_step * 8) if self.flip_step < 5 else (self.flip_step - 5) * 8
        if width <= 0:
            width = 1

        for card_label in self.flipping_cards:
            if card_label.winfo_exists():  # 确保组件还存在
                card_label.place(width=width)

        self.flip_step += 1
        self.after(50, self.animate_flip_to_front_step)
    
    def flip_all_player_cards_to_back(self):
        """将所有玩家牌翻转到背面"""
        # 收集所有玩家牌
        self.flipping_cards = []
        for card_label in self.player_cards_frame.winfo_children():
            if hasattr(card_label, "card") and card_label.is_face_up:
                self.flipping_cards.append(card_label)
        
        # 如果没有需要翻转的卡片，直接返回
        if not self.flipping_cards:
            self.after(100, self.sort_player_hand)
            return
            
        # 开始翻转动画
        self.flip_step = 0
        self.animate_flip_to_back_step()
    
    def animate_flip_to_back_step(self):
        """执行翻转动画的每一步（翻到背面）"""
        if self.flip_step > 10:  # 假设10步完成
            # 翻转完成，将所有正在翻转的卡片设为背面
            for card_label in self.flipping_cards:
                if hasattr(card_label, "card") and card_label.winfo_exists():
                    card_label.config(image=self.back_image)
                    card_label.is_face_up = False
                    # 重置宽度为正常值
                    card_label.place(width=80, height=120)
            
            # 根据当前是否在处理庄家，调用不同的排序方法
            if getattr(self, '_flipping_dealer', False):
                # 清除标记，避免影响后续操作
                self._flipping_dealer = False
                # 庄家翻背后排序
                self.after(100, self.sort_dealer_hand)
            else:
                # 玩家翻背后排序
                self.after(100, self.sort_player_hand)
            return

        # 模拟翻转效果
        width = 80 - (self.flip_step * 8) if self.flip_step < 5 else (self.flip_step - 5) * 8
        if width <= 0:
            width = 1

        for card_label in self.flipping_cards:
            if card_label.winfo_exists():
                card_label.place(width=width)

        self.flip_step += 1
        self.after(50, self.animate_flip_to_back_step)
    
    def flip_all_dealer_cards_to_back(self):
        """将所有庄家牌翻转到背面"""
        # 标记当前为庄家翻转
        self._flipping_dealer = True
        self.flipping_cards = []
        for lbl in self.dealer_cards_frame.winfo_children():
            if hasattr(lbl, 'card') and lbl.is_face_up:
                self.flipping_cards.append(lbl)

        if not self.flipping_cards:
            # 如果没有牌需要翻背，直接调用庄家排序
            self.after(100, self.sort_dealer_hand)
            return

        self.flip_step = 0
        self.animate_flip_to_back_step()
    
    def flip_all_dealer_cards_to_front(self, callback=None):
        """将所有庄家牌翻转到正面，完成后调用回调"""
        # 收集所有未翻面的庄家牌
        self.flipping_cards = []
        for card_label in self.dealer_cards_frame.winfo_children():
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flipping_cards.append(card_label)

        # 如果没有需要翻转的卡片
        if not self.flipping_cards:
            # 全部翻开后再调用回调
            if callback:
                callback()
            return

        # 开始翻转动画（动画完成后会调用 animate_flip_to_front_step）
        self.flip_step = 0
        self.callback_after_flip = callback
        self.animate_flip_to_front_step_for_dealer()
    
    def animate_flip_to_front_step_for_dealer(self):
        """庄家牌翻转动画的每一步（翻到正面）"""
        if self.flip_step > 10:  # 假设10步完成
            # 翻转完成，将所有正在翻转的卡片设为正面
            for card_label in self.flipping_cards:
                if hasattr(card_label, "card") and card_label.winfo_exists():
                    card = card_label.card
                    front_img = self.card_images.get((card.suit, card.rank), self.back_image)
                    card_label.config(image=front_img)
                    card_label.is_face_up = True
                    # 重置宽度为正常值
                    card_label.place(width=80, height=120)
            
            # 动画完成，调用回调函数
            if hasattr(self, 'callback_after_flip') and self.callback_after_flip:
                self.callback_after_flip()
            return

        # 模拟翻转效果
        width = 80 - (self.flip_step * 8) if self.flip_step < 5 else (self.flip_step - 5) * 8
        if width <= 0:
            width = 1

        for card_label in self.flipping_cards:
            if card_label.winfo_exists():  # 确保组件还存在
                card_label.place(width=width)

        self.flip_step += 1
        self.after(50, self.animate_flip_to_front_step_for_dealer)
    
    def sort_dealer_hand(self):
        """根据牌型对庄家手牌进行排序并更新显示"""
        # 排序庄家手牌
        sorted_hand = sort_hand_by_rank(self.game.dealer_hand)
        self.game.dealer_hand = sorted_hand
        
        # 清除庄家区域的卡片
        for widget in self.dealer_cards_frame.winfo_children():
            widget.destroy()
        
        # 重新放置庄家卡片（按新顺序），确保完整显示
        for i, card in enumerate(sorted_hand):
            # 确保卡片标签有足够的空间显示
            card_label = tk.Label(
                self.dealer_cards_frame, 
                image=self.back_image,  # 先显示背面
                bg='#2a4a3c',
                width=90,  # 增加宽度确保完整显示
                height=130  # 增加高度确保完整显示
            )
            # 使用place布局并设置合适的偏移量
            card_label.place(x=i*90, y=0, width=90, height=130)
            card_label.card = card
            card_label.is_face_up = False
            # 添加到活动卡片列表
            self.active_card_labels.append(card_label)
        
        # 更新庄家牌型标签
        self.update_hand_labels()
        
        # 将所有庄家牌翻到正面（二次开牌）
        self.flip_all_dealer_cards_to_front(self.after_dealer_flip)
    
    def after_dealer_flip(self):
        """庄家牌翻开后的回调函数"""
        # 检查庄家是否高牌且同时有A和K
        if (self.game.dealer_hand and len(self.game.dealer_hand) == 5 and
            not self.ak_animation_active):  # 确保没有正在进行的动画
            
            dealer_rank, _ = evaluate_five_card_hand(self.game.dealer_hand)
            if dealer_rank == 0:  # 高牌
                has_ace = any(card.rank == 'A' for card in self.game.dealer_hand)
                has_king = any(card.rank == 'K' for card in self.game.dealer_hand)
                
                if has_ace and has_king:
                    # 等待1秒后移动AK牌
                    self.after(1000, self.move_ak_cards)
                    return
        
        # 如果不需要移动AK牌，直接显示重新开始按钮
        self.show_restart_button()
    
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.jackpot_bet = self.jackpot_bet_var.get()  # 获取Jackpot下注
            self.last_jackpot_state = self.jackpot_bet_var.get()   
            
            # 检查Ante至少5块
            if self.ante < 5:
                messagebox.showerror("错误", "Ante至少需要5块")
                return
                
            # 获取Play下注
            play_bet = 0
            try:
                play_bet = int(self.play_var.get())
            except:
                play_bet = 0
                
            # 计算总下注
            total_bet = self.ante + self.jackpot_bet + play_bet
                
            if self.balance < total_bet:
                messagebox.showwarning("警告", "余额不足")
                return
                
            self.balance -= total_bet
            self.update_balance()
            
            # 更新本局下注显示
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            
            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.jackpot_bet = self.jackpot_bet  # 保存Jackpot下注
            self.game.play_bet = play_bet   # 保存Play下注
            
            # 清除所有卡片
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()
            
            # 重置动画状态
            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            self.moved_cards = []
            self.ak_moved = False
            self.ak_animation_active = False
            
            # 初始化卡片位置
            self.card_positions = {}
            
            # 玩家牌 - 放置在中中心位置
            for i in range(5):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 90, 0)  # 水平排列
                }
                self.animation_queue.append(card_id)
            
            # 庄家牌 - 放置在中中心位置
            for i in range(5):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 90, 0)  # 水平排列
                }
                self.animation_queue.append(card_id)

            # 创建操作按钮 - 替换开始按钮
            for widget in self.action_frame.winfo_children():
                widget.destroy()
                
            # 如果Play下注非0，则自动执行“下注2X”操作
            if play_bet > 0:
                # 更新游戏状态
                self.stage_label.config(text="阶段: 派牌")
                self.status_label.config(text="Play已下注 等待结算")

                # 自动选择下注2X - 不立即执行，等待玩家牌排序动画完成
            else:
                # 更新游戏状态
                self.stage_label.config(text="阶段: 决策")
                self.status_label.config(text="做出决策: 弃牌或下注2X")

                # 正常显示决策按钮
                action_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
                action_button_frame.pack(pady=10)

                self.fold_button = tk.Button(
                    action_button_frame, text="弃牌",
                    command=self.fold_action,
                    state=tk.DISABLED,
                    font=('Arial', 14), bg='#F44336', fg='white', width=10
                )
                self.fold_button.pack(side=tk.LEFT, padx=(0, 10))

                self.play_button = tk.Button(
                    action_button_frame, text="下注2X",
                    command=self.play_action,
                    state=tk.DISABLED,
                    font=('Arial', 14), bg='#4CAF50', fg='white', width=10
                )
                self.play_button.pack(side=tk.LEFT)

            # 禁用下注区域
            self.ante_display.unbind("<Button-1>")
            self.play_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            
            # 禁用Jackpot的Checkbutton
            self.jackpot_check.config(state=tk.DISABLED)
            
            # 开始动画
            self.animate_deal()
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
        
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            # 发牌动画完成后翻开玩家牌
            self.after(500, self.reveal_player_cards)
            return
            
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        
        # 创建卡片标签
        if card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hand[idx] if idx < len(self.game.player_hand) else None
        elif card_id.startswith("dealer"):
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hand[idx] if idx < len(self.game.dealer_hand) else None
        
        # 创建卡片标签 - 确保设置正确的宽度和高度 - 关键修复
        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(
            x=self.card_positions[card_id]["current"][0],
            y=self.card_positions[card_id]["current"][1] + 20,
            width=80,
            height=120
        )
        
        # 存储卡片信息
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        
        # 添加到活动卡片列表
        self.active_card_labels.append(card_label)
        
        # 开始移动动画
        self.animate_card_move(card_label)

    def animate_card_move(self, card_label):
        # 检查卡片是否仍然存在
        if not hasattr(card_label, "target_pos") or card_label not in self.active_card_labels:
            return
            
        try:
            current_x, current_y = card_label.winfo_x(), card_label.winfo_y()
            target_x, target_y = card_label.target_pos
            
            # 计算移动方向向量
            dx = target_x - current_x
            dy = target_y - current_y
            distance = math.sqrt(dx**2 + dy**2)
            
            # 如果已经到达目标位置
            if distance < 5:
                # 确保设置正确的宽度和高度
                card_label.place(x=target_x, y=target_y, width=80, height=120)
                card_label.is_moving = False
                
                # 如果是回收动画且到达左上角，销毁卡片
                if card_label.target_pos == (50, 50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                    
                self.after(100, self.animate_deal)  # 处理下一张牌
                return
            
            # 计算移动步长
            step_x = dx * 0.2
            step_y = dy * 0.2
            
            # 更新位置 - 确保保持宽度和高度
            new_x = current_x + step_x
            new_y = current_y + step_y
            card_label.place(x=new_x, y=new_y, width=80, height=120)
            
            # 继续动画
            self.after(20, lambda: self.animate_card_move(card_label))
            
        except tk.TclError:
            # 卡片已被销毁，停止动画
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)
            return
    
    def reveal_player_cards(self):
        """翻开玩家牌（带动画）"""
        if self.animation_in_progress:
            return
        
        # 翻开庄家第一张牌（新增加的功能）
        self.reveal_dealer_first_card()
        
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                # 确保卡片标签有足够的空间
                card_label.place(width=90, height=130)
                self.flip_card_animation(card_label)
                # 标记玩家牌已翻开
                self.game.cards_revealed["player"][i] = True
        
        # 更新玩家牌型
        self.update_hand_labels()
        
        # 等待2秒后开始排序动画
        self.after(2000, self.start_player_sort_animation)
    
    def start_player_sort_animation(self):
        """开始玩家手牌排序动画"""
        # 禁用决策按钮
        if self.fold_button and self.fold_button.winfo_exists():
            self.fold_button.config(state=tk.DISABLED)
        if self.play_button and self.play_button.winfo_exists():
            self.play_button.config(state=tk.DISABLED)
        
        # 先将所有玩家牌翻到背面
        self.flip_all_player_cards_to_back()
    
    def reveal_dealer_first_card(self):
        """只翻开庄家第一张牌"""
        # 确保没有动画在进行
        if self.animation_in_progress:
            return
        
        dealer_cards = self.dealer_cards_frame.winfo_children()
        if dealer_cards:
            first_card = dealer_cards[0]
            if hasattr(first_card, "card") and not first_card.is_face_up:
                # 设置动画标志
                self.animation_in_progress = True
                self.flip_card_animation(first_card)
    
    def reveal_dealer_cards_for_autobet(self):
        """自动下注模式：直接进入摊牌阶段，翻开所有庄家牌，2秒后结算"""
        # 切换到摊牌阶段
        self.game.stage = "showdown"
        self.stage_label.config(text="阶段: 摊牌")
        self.status_label.config(text="摊牌中…")
        
        # 翻开庄家所有牌（带动画）
        self.after(2000, self.reveal_dealer_cards_with_animation)
    
    def reveal_dealer_cards_with_animation(self):
        """翻开庄家牌并带动画"""
        # 禁用再来一局按钮
        self.disable_action_buttons()
        
        # 翻开庄家所有牌（带动画）
        self.reveal_dealer_cards()
        
        # 更新标签显示玩家和庄家牌型
        self.update_hand_labels()
        
        # 等待2秒再进行结算
        self.after(2000, self.show_showdown)

    def reveal_dealer_cards(self):
        """翻开庄家所有牌（带动画）"""
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                # 在摊牌阶段翻开所有牌
                if self.game.stage == "showdown" or self.game.folded:
                    self.flip_card_animation(card_label)
                # 标记庄家牌已翻开
                self.game.cards_revealed["dealer"][i] = True
        
        # 更新庄家牌型
        self.update_hand_labels()
        
        # 等待2秒后开始庄家手牌排序动画
        self.after(2000, self.start_dealer_sort_animation)
    
    def start_dealer_sort_animation(self):
        """开始庄家手牌排序动画"""
        # 先将所有庄家牌翻到背面
        self.flip_all_dealer_cards_to_back()
        
    def flip_card_animation(self, card_label):
        """卡片翻转动画"""
        # 获取卡片正面图像
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        
        # 创建动画序列
        self.animate_flip(card_label, front_img, 0)
    
    def animate_flip(self, card_label, front_img, step):
        """执行翻转动画"""
        steps = 10  # 动画总步数
        
        if step > steps:
            # 动画结束
            card_label.is_face_up = True
            self.animation_in_progress = False  # 清除动画标志
            return
            
        if step <= steps // 2:
            # 第一阶段：从背面翻转到侧面（宽度减小）
            width = 80 - (step * 16)
            if width <= 0:
                width = 1
            # 创建缩放后的背面图像
            back_img = Image.new('RGBA', (width, 120), (0, 0, 0, 0))
            orig_back = self.back_image
            # 这里简化处理，实际应该缩放图像
            card_label.config(image=orig_back)
        else:
            # 第二阶段：从侧面翻转到正面（宽度增加）
            width = (step - steps // 2) * 16
            if width <= 0:
                width = 1
            # 创建缩放后的正面图像
            card_label.config(image=front_img)
        
        # 更新卡片显示
        card_label.place(width=width)
        
        # 下一步
        step += 1
        self.after(50, lambda: self.animate_flip(card_label, front_img, step))
    
    def auto_play_action(self):
        """自动执行下注2X操作（盲注模式）"""
        # 立即禁用决策按钮
        if self.fold_button and self.fold_button.winfo_exists():
            self.fold_button.config(state=tk.DISABLED)
        if self.play_button and self.play_button.winfo_exists():
            self.play_button.config(state=tk.DISABLED)
            
        # 进入摊牌阶段
        self.game.stage = "showdown"
        self.stage_label.config(text="阶段: 摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)
    
    def play_action(self):
        """玩家选择下注2X（或者自动下注）"""
        # 立即禁用决策按钮
        if self.fold_button and self.fold_button.winfo_exists():
            self.fold_button.config(state=tk.DISABLED)
        if self.play_button and self.play_button.winfo_exists():
            self.play_button.config(state=tk.DISABLED)
            
        # 如果是自动下注（即已经通过开始游戏时设置了Play下注），则不需要再扣除金额，也不需要重复进入结算
        if self.game.play_bet > 0:
            # 自动下注模式
            # 进入摊牌阶段
            self.game.stage = "showdown"
            self.stage_label.config(text="阶段: 摊牌")
            self.status_label.config(text="摊牌中…")
            # 翻开庄家牌并结算
            self.after(1000, self.reveal_dealer_cards_for_autobet)
            return

        # 手动下注模式
        play_bet = self.game.ante * 2
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet

        # 更新Play Bet显示（如果之前没有显示，现在显示）
        self.play_var.set(str(play_bet))
        
        # 更新本局下注显示
        total_bet = self.ante + play_bet + self.jackpot_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        # 进入摊牌阶段
        self.game.stage = "showdown"
        self.stage_label.config(text="阶段: 摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)
    
    def fold_action(self):
        self.game.folded = True
        self.status_label.config(text="您已弃牌 ~ 游戏结束")

        # 保存下注金额用于结算
        ante_bet = int(self.ante_var.get())
        
        # 重置显示金额为0
        self.ante_var.set("0")
        self.play_var.set("0")
        
        # 翻开庄家牌
        self.reveal_dealer_cards()
        
        # 更新庄家牌型
        self.update_hand_labels()
        
        # 计算Jackpot (如果下注了Jackpot)
        bonus_win = 0
        if self.game.jackpot_bet:
            bonus_win = self.calculate_bonus()
            if bonus_win > 0:
                self.balance += bonus_win
                self.update_balance()
                player_eval = evaluate_five_card_hand(self.game.player_hand)
                player_hand_type = HAND_RANK_NAMES.get(player_eval[0], "高牌")
                messagebox.showinfo("恭喜您获得Jackpot大奖！", 
                                f"{player_hand_type}! 恭喜中了JP大奖${bonus_win:.2f}")
        
        # 设置背景色
        self.ante_display.config(bg='white')  # 输
        
        # 计算总赢得金额
        total_win = bonus_win
        self.last_win = total_win
        
        # 更新上局赢得金额显示
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")
        
        # 构建主消息
        result_text = "本局您选择弃牌"

        self.result_label.config(text=result_text, fg='white')
        
        # 添加重新开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.reset_game, 
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=10)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        
        # 设置30秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def show_showdown(self):
        # 翻开庄家牌
        self.reveal_dealer_cards()
        
        # 结算
        winnings, details = self.calculate_winnings()
        self.last_win = winnings
        
        # 更新余额
        self.balance += winnings
        self.update_balance()
        
        # 更新下注显示金额
        self.ante_var.set(str(int(details["ante"])))
        self.play_var.set(str(int(details["play"])))
        
        # 设置背景色：赢为金色，平局为浅蓝色，输为白色
        for bet_type in ["ante", "play"]:
            widget = self.bet_widgets.get(bet_type)
            if not widget:
                continue

            # 对应的下注金额
            if bet_type == "ante":
                bet_amount = self.game.ante
            else:  # "play"
                bet_amount = self.game.play_bet
                
            win_amount = details[bet_type]

            # 赢（任何注项赢都染金色）
            if win_amount > bet_amount:  # 赢
                widget.config(bg='gold')
            # 平局并且确实有下注（注金>0）
            elif win_amount == bet_amount and bet_amount > 0:
                widget.config(bg='light blue')
            # 其他情况（输了，或根本没下注）保持白色
            else:
                widget.config(bg='white')
        
        # 构建主消息
        dealer_qualifies = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)
        
        if not dealer_qualifies:
            base_text = "庄家不合格，只支付Ante，退还Play"
        else:
            if comparison > 0:  # 玩家赢
                base_text = "本局您赢了"
            elif comparison < 0:  # 玩家输
                base_text = "本局您输了"
            else:  # 平局
                base_text = "本局Push"
        
        bonus_win = 0
        if self.game.jackpot_bet:
            bonus_win = self.calculate_bonus()
            if bonus_win > 0:
                self.balance += bonus_win
                self.update_balance()
                player_eval = evaluate_five_card_hand(self.game.player_hand)
                player_hand_type = HAND_RANK_NAMES.get(player_eval[0], "高牌")
                messagebox.showinfo("恭喜您获得Jackpot大奖！", 
                                f"{player_hand_type}! 恭喜中了JP大奖${bonus_win:.2f}")
        
        # 组合消息
        result_text = base_text

        self.result_label.config(text=result_text, fg='white')
        self.status_label.config(text="游戏结束")
        
        # 更新上局赢得金额
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
    
    def move_ak_cards(self):
        """将庄家手牌中的A和K牌向下移动20px"""
        self.ak_animation_active = True
        self.moved_cards = []
        self.ak_moved = True
        
        # 遍历庄家的牌
        for card_label in self.dealer_cards_frame.winfo_children():
            if hasattr(card_label, 'card'):
                card = card_label.card
                if card.rank in ['A', 'K']:
                    # 记录原始位置
                    original_y = card_label.winfo_y()
                    # 添加移动动画到队列
                    self.moved_cards.append((card_label, original_y))
        
        # 如果没有符合条件的牌，直接返回
        if not self.moved_cards:
            self.ak_animation_active = False
            self.show_restart_button()
            return
        
        # 开始移动动画
        self.animate_move_down_step(0)
    
    def animate_move_down_step(self, step):
        """执行向下移动动画的每一步"""
        if step > 5:  # 5步完成移动 (0.5秒)
            # 移动完成，显示重新开始按钮
            self.ak_animation_active = False
            self.show_restart_button()
            return
        
        # 移动所有符合条件的牌
        for card_label, original_y in self.moved_cards:
            if card_label.winfo_exists():  # 确保组件还存在
                current_y = card_label.winfo_y()
                new_y = current_y + 4  # 每步移动4px
                card_label.place(y=new_y)
        
        # 下一步
        step += 1
        self.after(100, lambda: self.animate_move_down_step(step))
    
    def show_restart_button(self):
        """显示重新开始按钮"""
        # 添加重新开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.reset_game, 
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=10)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        
        # 设置30秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def calculate_winnings(self):
        """计算赢得的金额"""
        winnings = 0
        details = {
            "ante": 0,
            "play": 0,
            "bonus": 0
        }
        bonus_win = 0
        
        # 1. 结算Ante和Bet
        dealer_qualifies = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)
        
        ante_result = 0
        play_result = 0
        
        if not dealer_qualifies:
            # 庄家不合格：Ante支付1:1（即赢Ante下注额），Play退还
            ante_result = self.game.ante * 2   # 赢1倍，加上本金共2倍
            play_result = self.game.play_bet   # 退还Play下注额（即1倍，因为已经扣除，所以加回1倍即可）
        else:
            if comparison > 0:  # 玩家赢
                ante_result = self.game.ante * 2
                # Bet根据玩家牌型支付
                player_rank, _ = evaluate_five_card_hand(self.game.player_hand)
                payout = CARIBBEAN_STUD_PAYOUT.get(player_rank, 1)
                play_result = self.game.play_bet * (payout + 1)
            elif comparison == 0:  # 平局
                ante_result = self.game.ante
                play_result = self.game.play_bet
            else:  # 玩家输
                ante_result = 0
                play_result = 0
        
        winnings += ante_result + play_result
        details["ante"] = ante_result
        details["play"] = play_result
        
        # 2. 结算Jackpot (如果下注了)
        if self.game.jackpot_bet:
            bonus_win = self.calculate_bonus()
            winnings += bonus_win
            details["bonus"] = bonus_win
        
        # 3. 更新Jackpot奖池
        self.update_jackpot(winnings, details["ante"], self.game.ante, details["play"], self.game.play_bet)
        
        return winnings, details
    
    def update_jackpot(self, winnings, ante_win, ante_bet, play_win, play_bet):
        """更新Jackpot奖池金额"""
        # 计算本局贡献：(赢得金额 * 0.01 + Push金额 * 0.05 + 输的金额 * 0.1)
        # 赢得金额 = 玩家赢得的纯利润（不包括本金）
        win_amount = winnings - (ante_bet + play_bet + self.game.jackpot_bet)
        
        # Push金额 = 平局时退还的本金部分
        push_amount = 0
        if ante_win == ante_bet:  # Ante平局
            push_amount += ante_bet
        if play_win == play_bet:  # Bet平局
            push_amount += play_bet
        
        # 输的金额 = 输掉的下注金额
        loss_amount = 0
        if ante_win == 0:  # Ante输
            loss_amount += ante_bet
        if play_win == 0:  # Bet输
            loss_amount += play_bet
        
        # 计算贡献值
        jackpot_contribution = (win_amount * 0.01) + (push_amount * 0.05) + (loss_amount * 0.1)
        
        # 更新Jackpot金额
        self.game.jackpot_amount += jackpot_contribution
        self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")
        
        # 保存到文件
        save_jackpot(self.game.jackpot_amount)
    
    def calculate_bonus(self):
        """计算Jackpot奖金"""
        if not self.game.player_hand or len(self.game.player_hand) < 5:
            return 0
            
        cards = self.game.player_hand
        hand_rank, _ = evaluate_five_card_hand(cards)
        
        # 同花大顺
        if hand_rank == 9:
            bonus = self.game.jackpot_amount
            # 重置Jackpot为初始值
            self.game.jackpot_amount = self.game.initial_jackpot
            self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")
            save_jackpot(self.game.jackpot_amount)
            return bonus
        
        # 同花顺
        if hand_rank == 8:
            return self.game.jackpot_amount * 0.1
        
        # 四条
        if hand_rank == 7:
            return 500
        
        # 葫芦
        if hand_rank == 6:
            return 100
        
        # 同花
        if hand_rank == 5:
            return 75
        
        return 0

    def animate_collect_cards(self, auto_reset):
        """执行收牌动画：先翻转所有牌为背面，然后向右收起"""
        # 如果有下移的AK牌，先复位
        if self.ak_moved and self.moved_cards:
            self.animate_move_up_step(0, auto_reset)
            return
        
        # 否则直接开始收牌
        self.animate_move_cards_out(auto_reset)
    
    def animate_move_up_step(self, step, auto_reset):
        """执行向上移动动画的每一步（复位AK牌）"""
        if step > 5:  # 5步完成移动 (0.5秒)
            # 复位完成，开始收牌
            self.animate_move_cards_out(auto_reset)
            return
        
        # 移动所有之前下移的牌
        for card_label, original_y in self.moved_cards:
            if card_label.winfo_exists():  # 确保组件还存在
                current_y = card_label.winfo_y()
                new_y = current_y - 4  # 每步向上移动4px
                card_label.place(y=new_y)
        
        # 下一步
        step += 1
        self.after(100, lambda: self.animate_move_up_step(step, auto_reset))
    
    def animate_move_cards_out(self, auto_reset):
        """将所有牌向右移出屏幕"""
        # 过滤掉已经不存在的卡片
        self.active_card_labels = [label for label in self.active_card_labels if label.winfo_exists()]
        
        if not self.active_card_labels:
            # 没有牌，直接重置
            self._do_reset(auto_reset)
            return

        # 设置所有牌的目标位置为屏幕右侧外
        for card_label in self.active_card_labels:
            card_label.target_pos = (1200, card_label.winfo_y())  # 目标x为窗口右侧外

        # 开始移动
        self.animate_card_out_step(auto_reset)

    def animate_card_out_step(self, auto_reset):
        """移动卡片出屏幕的每一步"""
        all_done = True
        for card_label in self.active_card_labels[:]:  # 遍历副本
            if not hasattr(card_label, 'target_pos') or not card_label.winfo_exists():
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
                continue

            current_x = card_label.winfo_x()
            target_x, target_y = card_label.target_pos

            # 计算新位置
            dx = target_x - current_x
            if abs(dx) < 5:
                card_label.place(x=target_x, y=target_y)
                # 移除此卡片
                card_label.destroy()
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
                continue

            new_x = current_x + dx * 0.2
            card_label.place(x=new_x)
            all_done = False

        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset))
        else:
            # 所有动画完成，重置游戏
            self._do_reset(auto_reset)

    def reset_game(self, auto_reset=False):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 如果当前有牌在桌上，先执行收牌动画
        if self.active_card_labels:
            self.disable_action_buttons()  # 禁用按钮
            self.animate_collect_cards(auto_reset)  # 开始收牌动画，动画完成后会调用真正的重置
            return

        # 否则直接重置
        self._do_reset(auto_reset)
    
    def reset_bets(self):
        """重置下注金额为0"""
        self.ante_var.set("0")
        self.play_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        self.ante_display.config(bg='#FFCDD2')  # 浅红色
        self.play_display.config(bg='#FFCDD2')  # 浅红色
        self.after(500, lambda: self.ante_display.config(bg='white'))
        self.after(500, lambda: self.play_display.config(bg='white'))
    
    def _do_reset(self, auto_reset=False):
        """真正的重置游戏界面"""

        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None

        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="阶段: 下注")
        self.status_label.config(text="设置下注金额并开始游戏")
        self.result_label.config(text="")
        
        # 重置标签显示
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        
        # 重置下注金额为0
        self.ante_var.set("0")
        self.play_var.set("0")
        self.jackpot_bet_var.set(self.last_jackpot_state)
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 清空活动卡片列表（在收牌动画后已清空）
        self.active_card_labels = []
        self.moved_cards = []
        self.ak_moved = False
        self.ak_animation_active = False
        
        # 恢复下注区域
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.play_display.bind("<Button-1>", self.toggle_play_bet)
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
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))  # 右侧留出10像素间距

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

    def show_card_sequence(self, event):
        """显示本局牌序窗口 - 右键点击时取消30秒计时"""
        # 取消30秒自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600")  # 固定窗口大小
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        
        # 显示切牌位置
        cut_pos = self.game.cut_position
        cut_label = tk.Label(
            win, 
            text=f"本局切牌位置: {cut_pos + 1}", 
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0'
        )
        cut_label.pack(pady=(10, 5))
        
        # 创建主框架
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建画布用于滚动
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        # 创建内部框架放置所有内容
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        # 创建卡片框架
        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 创建缩小版卡片图像
        small_size = (60, 90)  # 卡片尺寸
        small_images = {}  # 存储缩小后的卡片图像
        
        for i, card in enumerate(self.game.card_sequence):
            key = (card.suit, card.rank)
            if key in self.original_images:
                orig_img = self.original_images[key]
                # 使用新的图像缩放方法
                small_img = orig_img.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small_img)
            else:
                # 如果没有找到原始图像，使用背面图像
                back_img = self.original_images.get("back", None)
                if back_img:
                    # 使用新的图像缩放方法
                    small_img = back_img.resize(small_size, Image.LANCZOS)
                    small_images[i] = ImageTk.PhotoImage(small_img)
        
        # 创建表格显示牌序 - 每行8张，共7行
        for row in range(7):  # 7行
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)
            
            # 计算该行卡片数量 (前6行8张，最后一行4张)
            cards_in_row = 8 if row < 6 else 4
            
            for col in range(cards_in_row):
                card_index = row * 8 + col
                if card_index >= 52:  # 确保不超过52张
                    break
                    
                # 创建卡片容器
                card_container = tk.Frame(row_frame, bg='#f0f0f0')
                card_container.grid(row=0, column=col, padx=5, pady=5)
                
                # 标记切牌位置
                bg_color = 'light blue' if card_index == self.game.cut_position else '#f0f0f0'
                
                # 显示卡片
                if card_index in small_images:
                    card_label = tk.Label(
                        card_container, 
                        image=small_images[card_index], 
                        bg=bg_color,
                        borderwidth=1,
                        relief="solid"
                    )
                    card_label.image = small_images[card_index]  # 保持引用
                    card_label.pack()
                else:
                    # 如果无法创建图像，显示文字表示
                    card = self.game.card_sequence[card_index]
                    card_label = tk.Label(
                        card_container, 
                        text=f"{card.rank}{card.suit}",
                        bg=bg_color,
                        width=6,
                        height=3,
                        borderwidth=1,
                        relief="solid"
                    )
                    card_label.pack()
                
                # 显示牌位置编号
                pos_label = tk.Label(
                    card_container, 
                    text=str(card_index+1), 
                    bg=bg_color,
                    font=('Arial', 9)
                )
                pos_label.pack()
        
        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 绑定鼠标滚轮滚动
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

def main(initial_balance=1000, username="Guest"):
    app = CaribbeanStudGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")