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
    7: '四条', 
    6: '同花顺', 
    5: '三条', 
    4: '同花', 
    3: '顺子', 
    2: '两对', 
    1: '对子', 
    0: '高牌'
}

# Super Bonus赔付表
SUPER_BONUS_PAYOUT = {
    7: {'A': 200, 'other': 30},  # 四条A: 200, 其他四条: 30
    6: 15,  # 同花顺 15:1
    5: 2,   # 三条 2:1
    4: 1.5, # 同花 1.5:1
    3: 1    # 顺子 1:1
}

# Queens+赔付表
QUEENS_PLUS_PAYOUT = {
    7: 50,  # 四条 50:1
    6: 30,  # 同花顺 30:1
    5: 9,   # 三条 9:1
    4: 4,   # 同花 4:1
    3: 3,   # 顺子 3:1
    2: 2,   # 两对 2:1
    1: 1    # Queens对子或以上 1:1
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
    if not hand or len(hand) < 4:  # 确保手牌完整
        return hand
        
    rank, sorted_values = evaluate_four_card_hand(hand)
    
    # 根据牌型进行排序：
    if rank in [0, 4]:  # 高牌、同花：按牌面值从大到小
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
    
    # 两对：先大对子再小对子
    elif rank == 2:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        pair_values = []
        for value, count in counts.items():
            if count == 2:
                pair_values.append(value)
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
        return sorted_hand
    
    # 三条：三条在前，然后单张
    elif rank == 5:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        three_value = None
        single_value = None
        for value, count in counts.items():
            if count == 3:
                three_value = value
            else:
                single_value = value
        sorted_hand = []
        # 先添加三条
        for card in hand:
            if card.value == three_value:
                sorted_hand.append(card)
        # 再添加单张
        for card in hand:
            if card.value == single_value and card not in sorted_hand:
                sorted_hand.append(card)
                break
        return sorted_hand
    
    # 顺子：按顺序排列（从小到大）
    elif rank in [3, 6]:  # 包括同花顺
        # 先按点数排序（升序）
        sorted_by_value = sorted(hand, key=lambda c: c.value)
        # 检查是否是A-2-3-4（即最小的顺子，其中A是1）
        if sorted_by_value[0].value == 2 and sorted_by_value[-1].value == 14:
            # 将A移到最前面（A作为1是最小的）
            aces = [card for card in sorted_by_value if card.value == 14]
            non_aces = [card for card in sorted_by_value if card.value != 14]
            sorted_hand = aces + non_aces  # A-2-3-4
            return sorted_hand
        else:
            # 普通顺子，按升序排列（最小在左，最大在右）
            return sorted_by_value
    
    # 四条：四条在前
    elif rank == 7:
        counts = {}
        for card in hand:
            counts[card.value] = counts.get(card.value, 0) + 1
        four_value = None
        for value, count in counts.items():
            if count == 4:
                four_value = value
                break
        sorted_hand = []
        # 添加四条
        for card in hand:
            if card.value == four_value:
                sorted_hand.append(card)
        return sorted_hand
    
    # 默认按牌面值从大到小
    return sorted(hand, key=lambda c: c.value, reverse=True)

def evaluate_four_card_hand(cards):
    """评估四张牌的手牌"""
    if not cards or len(cards) < 4:  # 确保手牌完整
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
    if len(set(values_sorted_asc)) == 4:
        # 检查最大减最小是否为3
        if values_sorted_asc[-1] - values_sorted_asc[0] == 3:
            is_straight = True
            straight_values = sorted(values, reverse=True)  # 降序排列
        # 检查特殊顺子 A-2-3-4
        elif values_sorted_asc == [2, 3, 4, 14]:
            is_straight = True
            straight_values = [4, 3, 2, 1]  # 作为4-high顺子
    
    # 同花顺
    if is_straight and is_flush:
        return (6, straight_values)
    
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
    
    # 检查三条
    if sorted_counts[0][1] == 3:
        return (5, sorted_values)
    
    # 同花
    if is_flush:
        return (4, values)
    
    # 顺子
    if is_straight:
        return (3, straight_values)
    
    # 两对
    if sorted_counts[0][1] == 2 and sorted_counts[1][1] == 2:
        return (2, sorted_values)
    
    # 对子
    if sorted_counts[0][1] == 2:
        return (1, sorted_values)
    
    # 高牌
    return (0, values)

def compare_hands(hand1, hand2):
    """比较两手牌，返回1表示hand1赢，0表示平局，-1表示hand2赢"""
    # 确保两手牌完整
    if not hand1 or len(hand1) < 4 or not hand2 or len(hand2) < 4:
        return 0
        
    rank1, values1 = evaluate_four_card_hand(hand1)
    rank2, values2 = evaluate_four_card_hand(hand2)
    
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

def get_best_four_card_hand(cards):
    """从5张牌中选出最佳的4张牌组合"""
    from itertools import combinations
    
    best_hand = None
    best_rank = -1
    best_values = []
    
    # 尝试所有可能的4张牌组合
    for combo in combinations(cards, 4):
        rank, values = evaluate_four_card_hand(list(combo))
        if rank > best_rank or (rank == best_rank and values > best_values):
            best_hand = list(combo)
            best_rank = rank
            best_values = values
    
    return best_hand, best_rank, best_values

def has_pair_of_queens_or_better(cards):
    """检查是否有至少一对Q或更好的牌型"""
    if not cards or len(cards) < 5:
        return False
    
    # 获取最佳4张牌
    best_hand, rank, _ = get_best_four_card_hand(cards)
    
    # 检查是否有至少一对Q
    if rank >= 1:  # 至少是对子
        values = [c.value for c in best_hand]
        value_count = {}
        for v in values:
            value_count[v] = value_count.get(v, 0) + 1
        
        # 检查是否有对子Q或以上 (Q的点数是12, K是13, A是14)
        for value, count in value_count.items():
            if count >= 2 and value >= 12:  # Q=12, K=13, A=14
                return True
        
        # 检查是否有更好的牌型（两对、三条、顺子、同花、同花顺、四条）
        if rank >= 2:
            return True
    
    return False

def dealer_qualifies(dealer_hand):
    """检查庄家是否有至少一张K（庄家资格）"""
    max_card_value = max(card.value for card in dealer_hand)
    return max_card_value >= 13  # K的点数是13

class CrazyFourGame:
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.player_best_hand = []  # 玩家最佳的4张牌
        self.dealer_best_hand = []  # 庄家最佳的4张牌
        self.player_discarded = []  # 玩家弃掉的牌
        self.dealer_discarded = []  # 庄家弃掉的牌
        self.ante = 0
        self.super_bonus_bet = 0
        self.queens_plus_bet = 0
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
    
    def select_best_hands(self):
        """为玩家和庄家选择最佳的4张牌"""
        # 玩家从5张牌中选4张最佳
        self.player_best_hand, player_rank, player_values = get_best_four_card_hand(self.player_hand)
        self.player_discarded = [card for card in self.player_hand if card not in self.player_best_hand]
        
        # 庄家从5张牌中选4张最佳
        self.dealer_best_hand, dealer_rank, dealer_values = get_best_four_card_hand(self.dealer_hand)
        self.dealer_discarded = [card for card in self.dealer_hand if card not in self.dealer_best_hand]
        
        return player_rank, dealer_rank

class CrazyFourGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("疯狂4张牌扑克")
        self.geometry("1250x650+50+10")  # 增加窗口尺寸以适应更大的卡片
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = CrazyFourGame()
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
        self.super_bonus_win = 0
        self.queens_plus_win = 0
        self.win_details = {
            "ante": 0,
            "play": 0,
            "super_bonus": 0,
            "queens_plus": 0
        }
        self.bet_widgets = {}  # 存储下注显示控件
        self.super_bonus_bet_var = tk.IntVar(value=0)  # Super Bonus下注变量
        self.queens_plus_bet_var = tk.IntVar(value=0)  # Queens+下注变量
        self.flipping_cards = []  # 存储正在翻转的卡片
        self.flip_step = 0  # 翻转动画的当前步骤
        self.moved_cards = []  # 存储下移的卡片
        self.fold_button = None  # 弃牌按钮引用
        self.play_1x_button = None  # 下注1倍按钮引用
        self.play_2x_button = None  # 下注2倍按钮引用
        self.play_3x_button = None  # 下注3倍按钮引用
        self._resetting = False
        self.discarded_labels = []  # 弃牌标签列表

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def cancel_auto_reset_timer(self):
        """安全地取消自动重置计时器"""
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except:
                # 忽略任何异常，确保计时器被标记为已取消
                pass
            finally:
                self.auto_reset_timer = None
    
    def on_close(self):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
        
    def _load_assets(self):
        card_size = (100, 150)  # 修改卡片尺寸为120x180
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
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            # 处理带K的筹码，如1K或2.5K
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        
        # 更新对应的下注变量
        if bet_type == "ante":
            current = float(self.ante_var.get())
            new_value = current + chip_value
            # 检查上限
            if new_value > 10000:
                new_value = 10000
                messagebox.showwarning("下注限制", f"底注上限为10000，已自动调整")
            self.ante_var.set(str(int(new_value)))
            # Super Bonus金额等于Ante
            self.super_bonus_var.set(str(int(new_value)))
        elif bet_type == "queens_plus":
            current = float(self.queens_plus_var.get())
            new_value = current + chip_value
            # 检查上限
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"Queens+上限为2500，已自动调整")
            self.queens_plus_var.set(str(int(new_value)))
    
    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域 - 使用Canvas提供更好的控制
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 庄家区域 - 增加高度以适应更大的卡片
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=30, y=20, width=720, height=250)  # 加宽以适应5张更大的牌
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 在庄家和玩家区域之间添加提示文字
        self.ante_info_label = tk.Label(
            table_canvas, 
            text="庄家需至少一张K才能开牌\n玩家和庄家比较最佳4张牌", 
            font=('Arial', 22), 
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
        self.ante_info_label.place(x=center_x + 385, y=280, anchor='n')  # 调整Y位置以适应更大的卡片
        
        # 玩家区域 - 增加高度以适应更大的卡片
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=90, y=365, width=600, height=250)  # 加宽以适应5张更大的牌
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=250, padx=10, pady=5)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 18),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=5)
        
        self.stage_label = tk.Label(
            info_frame, 
            text="翻牌前",
            font=('Arial', 18, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=5)
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        
        # 单行放置5个筹码 - 增加50%大小
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs = [
            ('$10', '#ffa500', 'black'),   # 橙色背景，黑色文字
            ("$25", '#00ff00', 'black'),    # 绿色背景，黑色文字
            ("$100", '#000000', 'white'),   # 黑色背景，白色文字
            ("$500", "#FF7DDA", 'black'),   # 粉色背景，黑色文字
            ("$1K", '#ffffff', 'black'),    # 白色背景，黑色文字
            ("$2.5K", '#ff0000', 'white'),     # 红色背景，白色文字
        ]
        
        self.chip_buttons = []
        self.chip_texts = {}  # 存储每个筹码按钮的文本
        for text, bg_color, fg_color in chip_configs:
            # 使用Canvas创建圆形筹码 - 尺寸改为55x55
            chip_canvas = tk.Canvas(chip_row, width=57, height=57, bg='#2a4a3c', highlightthickness=0)
            
            # 创建圆形（尺寸调整为51x51，在55x55画布中居中）
            chip_canvas.create_oval(2, 2, 55, 55, fill=bg_color, outline='black')
            
            # 创建文本（位置调整为画布中心）
            text_id = chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text  # 存储文本
        
        # 默认选中$10筹码
        self.select_chip("$10")

        # 每注限制
        minmax_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        minmax_frame.pack(fill=tk.X, pady=5)
        
        # 标题行
        header_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        
        tk.Label(header_frame, text="底注最低", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="底注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="边注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        
        # 数值行
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$10,000", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        
        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        
        # 第一行：Queen+
        queens_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        queens_frame.pack(fill=tk.X, padx=15, pady=3)

        queens_plus_label = tk.Label(queens_frame, text="Q对子+:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        queens_plus_label.pack(side=tk.LEFT)

        self.queens_plus_var = tk.StringVar(value="0")
        self.queens_plus_display = tk.Label(queens_frame, textvariable=self.queens_plus_var, font=('Arial', 14), 
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.queens_plus_display.pack(side=tk.LEFT, padx=5)
        self.queens_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("queens_plus"))
        self.bet_widgets["queens_plus"] = self.queens_plus_display

        # 第二行：底注 = 超级红利
        ante_super_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        ante_super_frame.pack(fill=tk.X, padx=40, pady=3)

        # 底注部分
        ante_label = tk.Label(ante_super_frame, text="底注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        ante_label.pack(side=tk.LEFT)

        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(ante_super_frame, textvariable=self.ante_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display

        # 等号
        equals_label = tk.Label(ante_super_frame, text=" = ", font=('Arial', 14), bg='#2a4a3c', fg='white')
        equals_label.pack(side=tk.LEFT, padx=5)

        # 超级红利部分
        self.super_bonus_var = tk.StringVar(value="0")
        self.super_bonus_display = tk.Label(ante_super_frame, textvariable=self.super_bonus_var, font=('Arial', 14), 
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.super_bonus_display.pack(side=tk.LEFT, padx=5)
        self.super_bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))  # 与Ante绑定
        self.bet_widgets["super_bonus"] = self.super_bonus_display

        super_bonus_label = tk.Label(ante_super_frame, text=":超级红利", font=('Arial', 14), bg='#2a4a3c', fg='white')
        super_bonus_label.pack(side=tk.LEFT)

        # 第三行：加注
        play_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        play_frame.pack(fill=tk.X, padx=40, pady=3)

        # 加注部分
        self.play_label = tk.Label(play_frame, text="加注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.play_label.pack(side=tk.LEFT)

        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(play_frame, textvariable=self.play_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.play_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["play"] = self.play_display
        
        # 游戏操作按钮框架 - 用于放置所有操作按钮
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X)

        # 创建一个框架来容纳重置按钮和开始游戏按钮
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

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
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)

        self.text_label = tk.Label(
            control_frame, text="牌型顺序:四条>同花顺>三条\n同花>顺子>两对>对子>高牌", 
            font=('Arial', 18, "bold"), bg="#2a4a3c", fg="#e1ff00"
        )
        self.text_label.pack(pady=5, fill=tk.X)
        
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
        win.title("疯狂4张牌扑克游戏规则")
        win.geometry("900x700")  # 增加窗口宽度以适应合并的表格
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
        疯狂4张牌扑克 游戏规则

        1. 游戏开始前下注:
           - 底注: 基础下注（必须）
           - 超级红利: 必须等于底注金额
           - Q对子+: 可选边注

        2. 游戏流程:
           a. 下注阶段:
               - 玩家下注底注
               - 超级红利自动等于底注金额
               - 可选择下注Q对子+
               - 点击"开始游戏"按钮开始

           b. 发牌:
               - 玩家发5张牌，庄家发5张牌
               - 玩家牌面朝上，庄家牌面朝下（只显示第一张）
               - 系统自动为玩家选择最佳4张牌，弃掉最小的一张

           c. 决策阶段:
               - 玩家查看自己的五张牌后选择:
                 * 弃牌: 输掉所有下注
                 * 下注1倍: 下注金额等于底注*1
                 * 下注2倍: 下注金额等于底注*2（需要至少一对Q或更好牌型）
                 * 下注3倍: 下注金额等于底注*3（需要至少一对Q或更好牌型）

           d. 摊牌:
               - 庄家开牌（需至少一张K才能开牌）
               - 系统自动为庄家选择最佳4张牌，弃掉最小的一张
               - 结算所有下注

        3. 结算规则:
           - 底注:
             * 庄家没有开牌: 底注退还
             * 庄家开牌，玩家赢: 底注1:1赔付
             * 庄家开牌，平局: 底注退还
             * 庄家开牌，玩家输: 底注输

           - 加注:
             * 玩家赢: 加注1:1赔付
             * 平局: 加注退还
             * 玩家输: 加注输

           - 超级红利:
             * 与加注绑定，加注赢则超级红利赢，加注平则超级红利平，加注输则超级红利输
             * 赔付根据玩家手牌牌型:
               - 四条A: 200:1
               - 四条2-K: 30:1
               - 同花顺: 15:1
               - 三条: 2:1
               - 同花: 1.5:1
               - 顺子: 1:1
               - 其他: 平局

           - Q对子+:
             * 独立结算，不受庄家影响
             * 赔付根据玩家手牌牌型:
               - 四条: 50:1
               - 同花顺: 30:1
               - 三条: 9:1
               - 同花: 4:1
               - 顺子: 3:1
               - 两对: 2:1
               - Queen对子或以上: 1:1

        4. 牌型大小顺序 (从大到小):
           四条 > 同花顺 > 三条 > 同花 > 顺子 > 两对 > 对子 > 高牌
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
            text="赔付表",
            font=('微软雅黑', 14, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 10), anchor='center')
        
        # 创建赔付表
        payout_frame = tk.Frame(content_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "超级红利赔率", "Queens+赔率"]
        payout_data = [
            ("四条A", "200:1", "50:1"),
            ("四条2-K", "30:1", "50:1"),
            ("同花顺", "15:1", "30:1"),
            ("三条", "2:1", "9:1"),
            ("同花", "1.5:1", "4:1"),
            ("顺子", "1:1", "3:1"),
            ("两对", "-", "2:1"),
            ("Queens对子或以上", "-", "1:1")
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
        * 庄家需至少一张K才能开牌
        * 玩家需至少一对Q或更好牌型才能下注2倍或3倍
        * 玩家和庄家平局时，底注和加注退还
        * 超级红利与加注绑定，加注结果决定超级红利结果
        * Queens+独立结算，只要玩家手牌达标即赔付
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
        if self.game.player_best_hand and len(self.game.player_best_hand) == 4:
            player_eval = evaluate_four_card_hand(self.game.player_best_hand)
            player_hand_name = HAND_RANK_NAMES[player_eval[0]] if player_eval else ""
            self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")
        
        # 计算庄家当前牌型（只有在摊牌时）
        if (self.game.stage == "showdown" or self.game.folded) and self.game.dealer_best_hand and len(self.game.dealer_best_hand) == 4:
            dealer_eval = evaluate_four_card_hand(self.game.dealer_best_hand)
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
        # 选择最佳4张牌
        player_rank, dealer_rank = self.game.select_best_hands()
        
        # 对最佳4张牌按牌型排序
        self.game.player_best_hand = sort_hand_by_rank(self.game.player_best_hand)
        
        # 对弃牌按值从大到小排序
        self.game.player_discarded = sorted(self.game.player_discarded, key=lambda c: c.value, reverse=True)
        
        # 清除玩家区域的卡片
        for widget in self.player_cards_frame.winfo_children():
            widget.destroy()
        
        # 显示玩家最佳4张牌（背面）
        for i, card in enumerate(self.game.player_best_hand):
            card_label = tk.Label(
                self.player_cards_frame, 
                image=self.back_image,
                bg='#2a4a3c',
                width=110,
                height=180
            )
            card_label.place(x=i*110, y=0, width=110, height=180)
            card_label.card = card
            card_label.is_face_up = False
            self.active_card_labels.append(card_label)
        
        # 显示玩家弃掉的牌（背面）
        if self.game.player_discarded:
            discarded_card = self.game.player_discarded[0]
            discarded_label = tk.Label(
                self.player_cards_frame, 
                image=self.back_image,
                bg='#2a4a3c',
                width=110,
                height=180
            )
            # 放置弃牌在最佳牌之后
            discarded_label.place(x=4*110, y=0, width=110, height=180)
            discarded_label.card = discarded_card
            discarded_label.is_face_up = False
            discarded_label.is_discarded = True
            self.active_card_labels.append(discarded_label)
            self.discarded_labels.append(discarded_label)
        
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
            # 动画完成，启用决策按钮
            self.after(500, self.enable_decision_buttons)
            return
            
        # 开始翻转动画
        self.flip_step = 0
        self.animate_flip_to_front_step()
    
    def animate_flip_to_front_step(self):
        """执行翻转动画的每一步（翻到正面）"""
        if self._resetting:  # 如果正在重置，停止动画
            return
    
        if self.flip_step > 10:  # 假设10步完成
            # 翻转完成，将所有正在翻转的卡片设为正面
            for card_label in self.flipping_cards:
                if hasattr(card_label, "card"):
                    card = card_label.card
                    front_img = self.card_images.get((card.suit, card.rank), self.back_image)
                    card_label.config(image=front_img)
                    card_label.is_face_up = True
                    # 重置宽度为正常值 - 关键修复
                    card_label.place(width=120, height=180)
                    
                    # 如果是弃牌，旋转45度
                    if hasattr(card_label, 'is_discarded') and card_label.is_discarded:
                        # 创建旋转后的图像
                        original_img = self.original_images.get((card.suit, card.rank), self.original_images["back"])
                        rotated_img = original_img.rotate(45, expand=True)
                        resized_rotated_img = rotated_img.resize((120, 180), Image.LANCZOS)
                        rotated_photo = ImageTk.PhotoImage(resized_rotated_img)
                        card_label.config(image=rotated_photo)
                        card_label.image = rotated_photo  # 保持引用
                    
            # 动画完成，启用决策按钮
            self.after(500, self.enable_decision_buttons)
            return

        # 模拟翻转效果
        width = 120 - (self.flip_step * 12) if self.flip_step < 5 else (self.flip_step - 5) * 12
        if width <= 0:
            width = 1

        for card_label in self.flipping_cards:
            if card_label.winfo_exists():  # 确保组件还存在
                card_label.place(width=width)

        self.flip_step += 1
        self.after(50, self.animate_flip_to_front_step)
    
    def enable_decision_buttons(self):
        """启用决策按钮，只根据余额动态禁用不可用的下注倍数按钮"""
        # 计算当前余额可以支持的最大下注倍数
        max_multiplier = 0
        ante_amount = self.game.ante
        
        # 检查每个倍数是否可用 - 只根据余额判断，不检查手牌
        for multiplier in [1, 2, 3]:
            play_bet_needed = ante_amount * multiplier
            if self.balance >= play_bet_needed:
                max_multiplier = multiplier
            else:
                break
        
        # 设置按钮状态
        if self.fold_button and self.fold_button.winfo_exists():
            self.fold_button.config(state=tk.NORMAL)
        
        if self.play_1x_button and self.play_1x_button.winfo_exists():
            if max_multiplier >= 1:
                self.play_1x_button.config(state=tk.NORMAL)
            else:
                self.play_1x_button.config(state=tk.DISABLED)
        
        if self.play_2x_button and self.play_2x_button.winfo_exists():
            if max_multiplier >= 2:
                self.play_2x_button.config(state=tk.NORMAL)
            else:
                self.play_2x_button.config(state=tk.DISABLED)
        
        if self.play_3x_button and self.play_3x_button.winfo_exists():
            if max_multiplier >= 3:
                self.play_3x_button.config(state=tk.NORMAL)
            else:
                self.play_3x_button.config(state=tk.DISABLED)
    
    def sort_dealer_hand(self):
        """根据牌型对庄家手牌进行排序并更新显示"""
        # 对最佳4张牌按牌型排序
        self.game.dealer_best_hand = sort_hand_by_rank(self.game.dealer_best_hand)
        
        # 对弃牌按值从大到小排序
        self.game.dealer_discarded = sorted(self.game.dealer_discarded, key=lambda c: c.value, reverse=True)
        
        # 清除庄家区域的卡片
        for widget in self.dealer_cards_frame.winfo_children():
            widget.destroy()
        
        # 显示庄家最佳4张牌（背面）
        for i, card in enumerate(self.game.dealer_best_hand):
            card_label = tk.Label(
                self.dealer_cards_frame, 
                image=self.back_image,
                bg='#2a4a3c',
                width=110,
                height=180
            )
            card_label.place(x=i*110, y=0, width=110, height=180)
            card_label.card = card
            card_label.is_face_up = False
            self.active_card_labels.append(card_label)
        
        # 显示庄家弃掉的牌（背面）
        if self.game.dealer_discarded:
            discarded_card = self.game.dealer_discarded[0]
            discarded_label = tk.Label(
                self.dealer_cards_frame, 
                image=self.back_image,
                bg='#2a4a3c',
                width=110,
                height=180
            )
            # 放置弃牌在最佳牌之后
            discarded_label.place(x=4*110, y=0, width=110, height=180)
            discarded_label.card = discarded_card
            discarded_label.is_face_up = False
            discarded_label.is_discarded = True
            self.active_card_labels.append(discarded_label)
            self.discarded_labels.append(discarded_label)
        
        # 更新庄家牌型标签
        self.update_hand_labels()
        
        # 将所有庄家牌翻到正面
        self.flip_all_dealer_cards_to_front(self.after_dealer_flip)
    
    def after_dealer_flip(self):
        """庄家牌翻开后的回调函数"""
        # 显示重新开始按钮
        self.show_restart_button()
        
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.super_bonus_bet = int(self.super_bonus_var.get())  # 获取Super Bonus下注
            self.queens_plus_bet = int(self.queens_plus_var.get())  # 获取Queens+下注
            
            # 检查Ante至少10块
            if self.ante < 10:
                messagebox.showerror("错误", "底注至少需要10块")
                return
                
            # 检查Ante上限
            if self.ante > 10000:
                self.ante = 10000
                self.ante_var.set("10000")
                self.super_bonus_var.set("10000")  # 同步更新Super Bonus
                messagebox.showwarning("下注限制", "底注上限为10000，已自动调整")
                
            # 检查Super Bonus是否等于Ante
            if self.super_bonus_bet != self.ante:
                self.super_bonus_bet = self.ante
                self.super_bonus_var.set(str(self.ante))
                messagebox.showwarning("下注限制", "超级红利必须等于底注金额，已自动调整")
                
            # 检查Queens+上限
            if self.queens_plus_bet > 2500:
                self.queens_plus_bet = 2500
                self.queens_plus_var.set("2500")
                messagebox.showwarning("下注限制", "Queens+上限为2500，已自动调整")
                
            # 计算总下注
            total_bet = self.ante + self.super_bonus_bet + self.queens_plus_bet
            
            # 检查余额是否足够支付所有下注
            if self.balance < total_bet:
                messagebox.showerror("错误", "余额不足以支付所有下注！")
                return
                    
            # 扣除当前下注
            self.balance -= total_bet
            self.update_balance()
            
            # 更新本局下注显示
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.last_win_label.config(text="上局获胜: $0.00")
            
            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.super_bonus_bet = self.super_bonus_bet  # 保存Super Bonus下注
            self.game.queens_plus_bet = self.queens_plus_bet  # 保存Queens+下注
            
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
            self.discarded_labels = []
            
            # 初始化卡片位置
            self.card_positions = {}
            
            # 玩家牌 - 放置在中中心位置
            for i in range(5):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 110, 0)  # 水平排列，增加间距
                }
                self.animation_queue.append(card_id)
            
            # 庄家牌 - 放置在中中心位置
            for i in range(5):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 110, 0)  # 水平排列，增加间距
                }
                self.animation_queue.append(card_id)

            # 创建操作按钮 - 替换开始按钮
            for widget in self.action_frame.winfo_children():
                widget.destroy()
                
            # 更新游戏状态
            self.stage_label.config(text="派牌")
            self.status_label.config(text="派牌中...")

            # 显示决策按钮
            action_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
            action_button_frame.pack(pady=5)

            self.fold_button = tk.Button(
                action_button_frame, text="弃牌",
                command=self.fold_action,
                state=tk.DISABLED,
                font=('Arial', 14), bg='#F44336', fg='white', width=7
            )
            self.fold_button.pack(side=tk.LEFT, padx=5)

            self.play_1x_button = tk.Button(
                action_button_frame, text="下注1倍",
                command=lambda: self.play_action(1),
                state=tk.DISABLED,
                font=('Arial', 14), bg='#4CAF50', fg='white', width=7
            )
            self.play_1x_button.pack(side=tk.LEFT, padx=5)

            self.play_2x_button = tk.Button(
                action_button_frame, text="下注2倍",
                command=lambda: self.play_action(2),
                state=tk.DISABLED,
                font=('Arial', 14), bg='#2196F3', fg='white', width=7
            )
            self.play_2x_button.pack(side=tk.LEFT, padx=5)

            self.play_3x_button = tk.Button(
                action_button_frame, text="下注3倍",
                command=lambda: self.play_action(3),
                state=tk.DISABLED,
                font=('Arial', 14), bg='#FF9800', fg='white', width=7
            )
            self.play_3x_button.pack(side=tk.LEFT, padx=5)

            # 禁用下注区域
            self.ante_display.unbind("<Button-1>")
            self.super_bonus_display.unbind("<Button-1>")
            self.queens_plus_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            
            # 开始动画
            self.animate_deal()
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
        
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            # 发牌动画完成后翻开玩家牌和庄家第一张牌
            self.after(500, self.reveal_initial_cards)
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
            width=120,
            height=180
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
                card_label.place(x=target_x, y=target_y, width=120, height=180)
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
            card_label.place(x=new_x, y=new_y, width=120, height=180)
            
            # 继续动画
            self.after(20, lambda: self.animate_card_move(card_label))
            
        except tk.TclError:
            # 卡片已被销毁，停止动画
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)
            return
    
    def reveal_initial_cards(self):
        """翻开玩家所有牌和庄家第一张牌"""
        if self.animation_in_progress:
            return
        
        # 翻开玩家所有牌
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                card_label.place(width=110, height=180)
                self.flip_card_animation(card_label)
                # 标记玩家牌已翻开
                self.game.cards_revealed["player"][i] = True
        
        # 翻开庄家第一张牌
        dealer_cards = self.dealer_cards_frame.winfo_children()
        if dealer_cards:
            first_card = dealer_cards[0]
            if hasattr(first_card, "card") and not first_card.is_face_up:
                self.flip_card_animation(first_card)
                # 标记庄家第一张牌已翻开
                self.game.cards_revealed["dealer"][0] = True
        
        # 等待2秒后开始排序动画
        self.after(2000, self.start_player_sort_animation)
    
    def start_player_sort_animation(self):
        """开始玩家手牌排序动画"""
        # 禁用决策按钮
        self.disable_decision_buttons()
        
        # 先将所有玩家牌翻到背面
        self.flip_all_player_cards_to_back()
    
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
                    card_label.place(width=120, height=180)
            
            # 玩家翻背后排序
            self.after(100, self.sort_player_hand)
            return

        # 模拟翻转效果
        width = 120 - (self.flip_step * 12) if self.flip_step < 5 else (self.flip_step - 5) * 12
        if width <= 0:
            width = 1

        for card_label in self.flipping_cards:
            if card_label.winfo_exists():
                card_label.place(width=width)

        self.flip_step += 1
        self.after(50, self.animate_flip_to_back_step)
    
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
                    card_label.place(width=120, height=180)
                    
                    # 如果是弃牌，旋转45度
                    if hasattr(card_label, 'is_discarded') and card_label.is_discarded:
                        # 创建旋转后的图像
                        original_img = self.original_images.get((card.suit, card.rank), self.original_images["back"])
                        rotated_img = original_img.rotate(45, expand=True)
                        resized_rotated_img = rotated_img.resize((120, 180), Image.LANCZOS)
                        rotated_photo = ImageTk.PhotoImage(resized_rotated_img)
                        card_label.config(image=rotated_photo)
                        card_label.image = rotated_photo  # 保持引用
            
            # 动画完成，调用回调函数
            if hasattr(self, 'callback_after_flip') and self.callback_after_flip:
                self.callback_after_flip()
            return

        # 模拟翻转效果
        width = 120 - (self.flip_step * 12) if self.flip_step < 5 else (self.flip_step - 5) * 12
        if width <= 0:
            width = 1

        for card_label in self.flipping_cards:
            if card_label.winfo_exists():  # 确保组件还存在
                card_label.place(width=width)

        self.flip_step += 1
        self.after(50, self.animate_flip_to_front_step_for_dealer)
    
    def disable_decision_buttons(self):
        """禁用决策按钮"""
        if self.fold_button and self.fold_button.winfo_exists():
            self.fold_button.config(state=tk.DISABLED)
        if self.play_1x_button and self.play_1x_button.winfo_exists():
            self.play_1x_button.config(state=tk.DISABLED)
        if self.play_2x_button and self.play_2x_button.winfo_exists():
            self.play_2x_button.config(state=tk.DISABLED)
        if self.play_3x_button and self.play_3x_button.winfo_exists():
            self.play_3x_button.config(state=tk.DISABLED)
    
    def fold_action(self):
        """玩家选择弃牌"""
        self.game.folded = True
        self.status_label.config(text="您已弃牌 ~ 游戏结束")

        # 保存下注金额用于结算
        ante_bet = int(self.ante_var.get())
        super_bonus_bet = int(self.super_bonus_var.get())
        queens_plus_bet = int(self.queens_plus_var.get())
        
        # 重置显示金额为0
        self.ante_var.set("0")
        self.play_var.set("0")
        self.super_bonus_var.set("0")
        self.queens_plus_var.set("0")
        
        # 翻开庄家牌
        self.reveal_dealer_cards()
        
        # 更新庄家牌型
        self.update_hand_labels()
        
        # 设置背景色
        self.ante_display.config(bg='white')  # 输
        self.play_display.config(bg='white')  # 输
        self.super_bonus_display.config(bg='white')  # 输
        self.queens_plus_display.config(bg='white')  # 输
        
        # 计算总赢得金额（弃牌全输）
        total_win = 0
        self.last_win = total_win
        
        # 更新余额
        self.balance += total_win
        self.update_balance()
        
        # 更新上局赢得金额显示
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")
        
        # 添加重新开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.reset_game, 
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=5)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        
        # 设置30秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def play_action(self, multiplier):
        """玩家选择下注N倍"""
        # 立即禁用决策按钮
        self.disable_decision_buttons()
            
        play_bet = self.game.ante * multiplier
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet

        # 更新Play Bet显示
        self.play_var.set(str(play_bet))
        
        # 更新本局下注显示
        total_bet = self.ante + play_bet + self.game.super_bonus_bet + self.game.queens_plus_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        # 进入摊牌阶段
        self.game.stage = "showdown"
        self.stage_label.config(text="摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)
    
    def show_showdown(self):
        # 翻开庄家牌
        self.reveal_dealer_cards()
        
        # 结算
        winnings, details = self.calculate_winnings()
        
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
        
        # 更新Super Bonus显示
        super_bonus_win = details["super_bonus"]
        if super_bonus_win > self.game.super_bonus_bet:
            # 显示赢得的金额
            self.super_bonus_var.set(str(int(super_bonus_win)))
            self.super_bonus_display.config(bg='gold')
        elif super_bonus_win == self.game.super_bonus_bet:
            self.super_bonus_var.set(str(int(super_bonus_win)))
            self.super_bonus_display.config(bg='light blue')
        else:
            self.super_bonus_var.set("0")
            self.super_bonus_display.config(bg='white')
        
        # 更新Queens+显示
        queens_plus_win = details["queens_plus"]
        if queens_plus_win > self.game.queens_plus_bet:
            # 显示赢得的金额
            self.queens_plus_var.set(str(int(queens_plus_win)))
            self.queens_plus_display.config(bg='gold')
        elif queens_plus_win == self.game.queens_plus_bet:
            self.queens_plus_var.set(str(int(queens_plus_win)))
            self.queens_plus_display.config(bg='light blue')
        else:
            self.queens_plus_var.set("0")
            self.queens_plus_display.config(bg='white')
        
        # 构建主消息
        dealer_qualifies_flag = dealer_qualifies(self.game.dealer_hand)
        comparison = compare_hands(self.game.player_best_hand, self.game.dealer_best_hand)
        
        if not dealer_qualifies_flag:
            status_label = "庄家未开牌"
        elif comparison >= 0:  # 玩家赢或平局
            status_label = "本局您赢了"
        else:  # 玩家输
            status_label = "本局您输了"
        
        self.status_label.config(text=status_label)
        
        # 更新上局赢得金额
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
    
    def reveal_dealer_cards(self):
        """翻开庄家所有牌（带动画）"""
        # 先一次性翻开所有庄家牌
        self.flip_all_dealer_cards_at_once()
        
    def flip_all_dealer_cards_at_once(self):
        """一次性翻开所有庄家牌，带动画效果"""
        # 收集所有未翻面的庄家牌
        self.flipping_cards = []
        dealer_cards = self.dealer_cards_frame.winfo_children()
        
        for card_label in dealer_cards:
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flipping_cards.append(card_label)
        
        # 如果没有需要翻转的卡片
        if not self.flipping_cards:
            # 等待1秒后开始排序
            self.after(1000, self.start_dealer_sort_animation)
            return
        
        # 开始翻转动画
        self.flip_step = 0
        self.animate_flip_to_front_step_for_dealer_all_at_once()

    def animate_flip_to_front_step_for_dealer_all_at_once(self):
        """庄家牌一次性翻转动画的每一步（翻到正面）"""
        if self._resetting:  # 如果正在重置，停止动画
            return
        
        if self.flip_step > 10:  # 假设10步完成
            # 翻转完成，将所有正在翻转的卡片设为正面
            for card_label in self.flipping_cards:
                if hasattr(card_label, "card") and card_label.winfo_exists():
                    card = card_label.card
                    front_img = self.card_images.get((card.suit, card.rank), self.back_image)
                    card_label.config(image=front_img)
                    card_label.is_face_up = True
                    # 重置宽度为正常值
                    card_label.place(width=120, height=180)
            
            # 动画完成，等待1秒后开始排序
            self.after(1000, self.start_dealer_sort_animation)
            return

        # 模拟翻转效果
        width = 120 - (self.flip_step * 12) if self.flip_step < 5 else (self.flip_step - 5) * 12
        if width <= 0:
            width = 1

        for card_label in self.flipping_cards:
            if card_label.winfo_exists():  # 确保组件还存在
                card_label.place(width=width)

        self.flip_step += 1
        self.after(50, self.animate_flip_to_front_step_for_dealer_all_at_once)
    
    def start_dealer_sort_animation(self):
        """开始庄家手牌排序动画"""
        # 先将所有庄家牌翻到背面
        self.flip_all_dealer_cards_to_back()
    
    def flip_all_dealer_cards_to_back(self):
        """将所有庄家牌翻转到背面"""
        self.flipping_cards = []
        for lbl in self.dealer_cards_frame.winfo_children():
            if hasattr(lbl, 'card') and lbl.is_face_up:
                self.flipping_cards.append(lbl)

        if not self.flipping_cards:
            # 如果没有牌需要翻背，直接调用庄家排序
            self.after(100, self.sort_dealer_hand)
            return

        self.flip_step = 0
        self.animate_flip_to_back_step_for_dealer()
    
    def animate_flip_to_back_step_for_dealer(self):
        """庄家牌翻转动画的每一步（翻到背面）"""
        if self.flip_step > 10:  # 假设10步完成
            # 翻转完成，将所有正在翻转的卡片设为背面
            for card_label in self.flipping_cards:
                if hasattr(card_label, "card") and card_label.winfo_exists():
                    card_label.config(image=self.back_image)
                    card_label.is_face_up = False
                    # 重置宽度为正常值
                    card_label.place(width=120, height=180)
            
            # 庄家翻背后排序
            self.after(100, self.sort_dealer_hand)
            return

        # 模拟翻转效果
        width = 120 - (self.flip_step * 12) if self.flip_step < 5 else (self.flip_step - 5) * 12
        if width <= 0:
            width = 1

        for card_label in self.flipping_cards:
            if card_label.winfo_exists():
                card_label.place(width=width)

        self.flip_step += 1
        self.after(50, self.animate_flip_to_back_step_for_dealer)
    
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
            # 动画结束 - 关键修复：确保设置正确的宽度和高度
            card_label.config(image=front_img)
            card_label.is_face_up = True
            self.animation_in_progress = False  # 清除动画标志
            # 确保设置正确的宽度和高度 - 关键修复
            card_label.place(width=120, height=180)
            return
            
        if step <= steps / 2:
            # 第一阶段：从背面翻转到侧面（宽度减小）
            width = 120 - (step * 12)
            if width <= 0:
                width = 1
            # 使用背面图像
            card_label.config(image=self.back_image)
        else:
            # 第二阶段：从侧面翻转到正面（宽度增加）
            width = (step - steps / 2) * 12
            if width <= 0:
                width = 1
            # 使用正面图像
            card_label.config(image=front_img)
        
        # 更新卡片显示 - 确保保持高度不变
        card_label.place(width=width, height=180)
        
        # 下一步
        step += 1
        self.after(50, lambda: self.animate_flip(card_label, front_img, step))
    
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
        restart_btn.pack(pady=5)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        
        # 设置30秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def calculate_winnings(self):
        """计算赢得的金额"""
        winnings = 0
        details = {
            "ante": 0,
            "play": 0,
            "super_bonus": 0,
            "queens_plus": 0
        }
        
        # 检查庄家资格
        dealer_qualifies_flag = dealer_qualifies(self.game.dealer_hand)
        
        # 1. 结算Ante
        comparison = compare_hands(self.game.player_best_hand, self.game.dealer_best_hand)
        
        ante_result = 0
        play_result = 0
        
        if not dealer_qualifies_flag:
            # 庄家未开牌
            ante_result = self.game.ante  # 底注退还
            play_result = self.game.play_bet  # 加注退还
        else:
            if comparison > 0:  # 玩家赢
                ante_result = self.game.ante * 2
            elif comparison == 0:  # 平局
                ante_result = self.game.ante  # 底注退还
            else:
                ante_result = 0
            
        # 庄家开牌
        if comparison >= 0:  # 玩家赢或平局
            if comparison > 0:  # 玩家赢
                play_result = self.game.play_bet * 2  # 赢1倍，加上本金共2倍
            else:  # 平局
                play_result = self.game.play_bet  # 加注退还
        else:  # 玩家输
            play_result = 0
        
        winnings += ante_result + play_result
        details["ante"] = ante_result
        details["play"] = play_result
        
        # 2. 结算Super Bonus (与加注绑定)
        if self.game.super_bonus_bet > 0:
            # Super Bonus的结果与加注相同
            if play_result > self.game.play_bet:  # 加注赢
                super_bonus_win = self.calculate_super_bonus()
                winnings += super_bonus_win
                details["super_bonus"] = super_bonus_win
            elif play_result == self.game.play_bet:  # 加注平局
                super_bonus_win = self.game.super_bonus_bet  # 退还
                winnings += super_bonus_win
                details["super_bonus"] = super_bonus_win
            else:  # 加注输
                details["super_bonus"] = 0
        
        # 3. 结算Queens+ (独立结算)
        if self.game.queens_plus_bet > 0:
            queens_plus_win = self.calculate_queens_plus()
            winnings += queens_plus_win
            details["queens_plus"] = queens_plus_win
        
        return winnings, details
    
    def calculate_super_bonus(self):
        """计算Super Bonus奖金"""
        if not self.game.player_best_hand or len(self.game.player_best_hand) < 4:
            return 0
            
        cards = self.game.player_best_hand
        hand_rank, _ = evaluate_four_card_hand(cards)
        
        # 根据赔付表计算奖金
        if hand_rank in SUPER_BONUS_PAYOUT:
            if hand_rank == 7:  # 四条
                # 检查是否是四条A
                values = [c.value for c in cards]
                if values.count(14) == 4:  # 四条A
                    bonus = self.game.super_bonus_bet * (SUPER_BONUS_PAYOUT[7]['A'] + 1)  # +1 因为包括本金
                else:
                    bonus = self.game.super_bonus_bet * (SUPER_BONUS_PAYOUT[7]['other'] + 1)
            else:
                bonus = self.game.super_bonus_bet * (SUPER_BONUS_PAYOUT[hand_rank] + 1)
        else:
            # 其他牌型，退还本金
            bonus = self.game.super_bonus_bet
        
        return bonus

    def calculate_queens_plus(self):
        """计算Queens+奖金"""
        if not self.game.player_best_hand or len(self.game.player_best_hand) < 4:
            return 0
            
        cards = self.game.player_best_hand
        hand_rank, _ = evaluate_four_card_hand(cards)
        
        # 检查是否是对子Q或以上
        is_pair_queens_or_better = False
        if hand_rank == 1:  # 对子
            values = [c.value for c in cards]
            value_count = {}
            for v in values:
                value_count[v] = value_count.get(v, 0) + 1
            
            # 检查是否有对子Q或以上
            for value, count in value_count.items():
                if count >= 2 and value >= 12:  # Q=12, K=13, A=14
                    is_pair_queens_or_better = True
                    break
        
        # 根据赔付表计算奖金
        if hand_rank in QUEENS_PLUS_PAYOUT:
            if hand_rank == 1 and not is_pair_queens_or_better:
                # 普通对子（低于Q）不支付
                bonus = 0
            else:
                bonus = self.game.queens_plus_bet * (QUEENS_PLUS_PAYOUT[hand_rank] + 1)  # +1 因为包括本金
        else:
            # 高牌，不支付
            bonus = 0
        
        return bonus

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
        # 安全地取消自动重置计时器
        self.cancel_auto_reset_timer()
        
        # 设置重置标志，停止所有动画
        self._resetting = True
        
        # 清除所有挂起的after事件
        for after_id in self.tk.eval('after info').split():
            self.after_cancel(after_id)
        
        # 如果当前有牌在桌上，先执行收牌动画
        if self.active_card_labels:
            self.disable_action_buttons()  # 禁用按钮
            self.animate_move_cards_out(auto_reset)  # 开始收牌动画，动画完成后会调用真正的重置
            return

        # 否则直接重置
        self._do_reset(auto_reset)
    
    def reset_bets(self):
        """重置下注金额为0"""
        self.ante_var.set("0")
        self.play_var.set("0")
        self.super_bonus_var.set("0")
        self.queens_plus_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        self.ante_display.config(bg='#FFCDD2')  # 浅红色
        self.play_display.config(bg='#FFCDD2')  # 浅红色
        self.super_bonus_display.config(bg='#FFCDD2')  # 浅红色
        self.queens_plus_display.config(bg='#FFCDD2')  # 浅红色
        self.after(500, lambda: self.ante_display.config(bg='white'))
        self.after(500, lambda: self.play_display.config(bg='white'))
        self.after(500, lambda: self.super_bonus_display.config(bg='white'))
        self.after(500, lambda: self.queens_plus_display.config(bg='white'))
    
    def _do_reset(self, auto_reset=False):
        # 重新加载资源（切换扑克牌图片）
        self._load_assets()
        
        """真正的重置游戏界面"""
        self.cancel_auto_reset_timer()
        
        # 清除所有挂起的after事件
        for after_id in self.tk.eval('after info').split():
            self.after_cancel(after_id)

        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="翻牌前")
        self.status_label.config(text="设置下注金额并开始游戏")
        
        # 重置标签显示
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        
        # 重置下注金额为0
        self.ante_var.set("0")
        self.play_var.set("0")
        self.super_bonus_var.set("0")
        self.queens_plus_var.set("0")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 清空活动卡片列表（在收牌动画后已清空）
        self.active_card_labels = []
        self.moved_cards = []
        self.discarded_labels = []
        
        # 清除所有动画状态
        self.animation_queue = []
        self.animation_in_progress = False
        self.flipping_cards = []
        self.flip_step = 0
        
        # 恢复下注区域
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.super_bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))  # 与Ante绑定
        self.queens_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("queens_plus"))
        for chip in self.chip_buttons:
            # 使用存储的文本重新绑定事件
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        
        # 恢复操作按钮区域
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

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
        
        # 重置本局下注显示
        self.current_bet_label.config(text="本局下注: $0.00")
        
        # 重置标志
        self._resetting = False
        
        # 如果是自动重置，显示消息
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
        else:
            self.status_label.config(text="设置下注金额并开始游戏")

    def show_card_sequence(self, event):
        """显示本局牌序窗口 - 右键点击时取消30秒计时"""
        # 取消30秒自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 确保有牌序信息
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示", "没有牌序信息")
            return
            
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600")  # 固定窗口大小
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        
        # 显示切牌位置
        cut_pos = self.game.deck.start_pos
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
        small_size = (60, 90)
        small_images = {}

        # 尝试加载字体
        from PIL import ImageFont, ImageDraw
        
        # 创建卡片图像
        for i, card in enumerate(self.game.deck.full_deck):
            # 使用花色和点数作为键获取原始图片
            key = (card.suit, card.rank)
            
            if key in self.original_images:
                # 获取原始图像
                orig_img = self.original_images[key]
                
                # 创建缩小版图像
                small_img = orig_img.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small_img)
            else:
                # 创建带文字的占位图像
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                text = f"{card.rank}{card.suit}"
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                text_width, text_height = draw.textsize(text, font=font)
                x = (small_size[0] - text_width) / 2
                y = (small_size[1] - text_height) / 2
                draw.text((x, y), text, fill="white", font=font)
                small_images[i] = ImageTk.PhotoImage(img)
        
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
                
                # 标记切牌位置 - 显示在原始牌序中的位置
                is_cut_position = card_index == self.game.deck.start_pos
                bg_color = 'light blue' if is_cut_position else '#f0f0f0'
                
                # 显示卡片
                card = self.game.deck.full_deck[card_index]
                card_label = tk.Label(
                    card_container, 
                    image=small_images[card_index], 
                    bg=bg_color,
                    borderwidth=1,
                    relief="solid"
                )
                card_label.image = small_images[card_index]  # 保持引用
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

def main(initial_balance=10000, username="Guest"):
    app = CrazyFourGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")