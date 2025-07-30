import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import secrets
import subprocess, sys
import time

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, 
    '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11
}
DECKS = 8  # 使用8副牌

# 下注赔率
BET_ODDS = {
    '16': 2.45,
    '17': 1.93,
    '18': 0.95,
    '19': 0.48,
    '20': 0.13,
    'pair': {  # 对子赔率根据类型不同而不同
        'same_suit_AA': 60,   # AA同花
        'same_suit_other': 30,  # 其他同花对子
        'same_color': 15,      # 同色非同花
        'mixed': 7             # 杂色对子
    },
    'small': 1.75,   # 小
    'bj': {          # BJ赔率根据花色不同而不同
        'same_suit': 50,   # 同花
        'same_color': 25,  # 同色
        'mixed': 11        # 杂色
    },
    'twenty_two': {  # 22点赔率
        'same_suit': 50,
        'same_color': 20,
        'mixed': 8
    },
    'big': 3.5       # 大
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
        self.is_joker = False
        
    def __repr__(self):
        if self.is_joker:
            return "JOKER"
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        # 获取当前脚本所在目录的上一级目录
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 新的Card文件夹路径
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle_baccarat.py')
        
        # 保证 Python 输出为 UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        try:
            # 调用外部 shuffle_baccarat.py，超时 30 秒
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
            
            # 在350-380之间的随机位置插入切牌
            cut_card_pos = random.randint(350, 380)
            self.full_deck.insert(cut_card_pos, Card('Joker', 'A'))
            self.full_deck[cut_card_pos].is_joker = True
            self.cut_card_position = cut_card_pos
        
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
                ValueError,
                KeyError) as e:
            print(f"Error calling shuffle_baccarat.py: {e}. Using fallback shuffle.")
            # fallback：标准顺序+安全乱序
            self.full_deck = [Card(s, r) for _ in range(DECKS) for s in SUITS for r in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52 * DECKS)
            
            # 在350-380之间的随机位置插入切牌
            cut_card_pos = random.randint(350, 380)
            self.full_deck.insert(cut_card_pos, Card('Joker', 'A'))
            self.full_deck[cut_card_pos].is_joker = True
            self.cut_card_position = cut_card_pos
        
        # 通用的洗牌后索引 & 发牌序列逻辑
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % (52 * DECKS) for i in range(52 * DECKS)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]
        self.cut_card_reached = False
    
    def _secure_shuffle(self):
        """Fisher–Yates 洗牌，用 secrets 保证随机性"""
        n = len(self.full_deck)
        for i in range(n - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = []
        for i in range(n):
            card = self.full_deck[self.indexes[self.pointer]]
            self.pointer += 1
            dealt.append(card)
            
            # 检查是否切牌
            if card.is_joker:
                self.cut_card_reached = True
        return dealt

class Simple21Game:
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        self.deck = Deck()
        self.dealer_hand = []
        self.bets = {
            '16': 0,
            '17': 0,
            '18': 0,
            '19': 0,
            '20': 0,
            'pair': 0,
            'small': 0,      # 新增
            'bj': 0,         # 新增
            'twenty_two': 0, # 新增
            'big': 0         # 新增
        }
        self.bet_results = {}  # 存储每个下注区域的结果
        self.total_bet = 0
        self.stage = "betting"  # betting, dealing, dealer_turn, showdown
        self.cut_card_shown = False
        self.dealer_finished = False
        self.winnings = 0
        self.dealer_value = 0
        self.dealer_pair = False
        self.dealer_blackjack = False   # 新增：庄家是否Blackjack
        self.dealer_twenty_two = False   # 新增：庄家是否22点
        self.dealer_stopped_at = None    # 新增：庄家停牌时的牌张数
    
    def place_bet(self, bet_type, amount):
        if amount <= 0:
            return False
        self.bets[bet_type] += amount
        self.total_bet += amount
        return True
    
    def deal_initial(self):
        """发初始牌：庄家2张"""
        self.dealer_hand = self.deck.deal(2)
        self.stage = "dealer_turn"
        
        # 检查庄家头两张是否对子
        self.dealer_pair = self.dealer_hand[0].rank == self.dealer_hand[1].rank
        
        # 检查庄家是否Blackjack（两张牌21点）
        self.dealer_blackjack = (self.calculate_hand_value(self.dealer_hand) == 21 and len(self.dealer_hand) == 2)
        
        # 计算庄家点数（只显示第一张）
        self.dealer_value = self.calculate_hand_value([self.dealer_hand[0]])
    
    def dealer_hit(self):
        """庄家补牌"""
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        # 检查庄家是否22点
        self.dealer_twenty_two = (dealer_value == 22)
        
        # 庄家补牌规则：16点及以下补牌，17点及以上停牌
        if dealer_value <= 16:
            new_card = self.deck.deal(1)
            self.dealer_hand.extend(new_card)
            return True, new_card[0]
        return False, None
    
    def calculate_hand_value(self, hand):
        """计算手牌点数，优先选择不爆牌的最大点数"""
        # 先计算所有可能的点数
        possible_values = [0]
        aces = []
        
        # 先处理非Ace牌
        for card in hand:
            if card.rank == 'A':
                aces.append(card)
            else:
                for i in range(len(possible_values)):
                    possible_values[i] += card.value
        
        # 处理Ace牌
        for ace in aces:
            new_values = []
            for val in possible_values:
                # Ace可以作为1或11
                new_values.append(val + 1)  # Ace作为1
                new_values.append(val + 11) # Ace作为11
            possible_values = new_values
        
        # 找出不爆牌的最大点数
        valid_values = [val for val in possible_values if val <= 21]
        if valid_values:
            return max(valid_values)
        
        # 如果所有组合都爆牌，则选择最小点数
        return min(possible_values)
    
    def get_card_color(self, suit):
        """获取花色颜色（红色或黑色），支持符号和英文名称"""
        # 红色：红桃、方片
        if suit in ['♥', '♦', 'Heart', 'Diamond']:
            return 'red'
        # 黑色：黑桃、梅花
        elif suit in ['♠', '♣', 'Spade', 'Club']:
            return 'black'
        # 其他（Joker 等）
        return None
    
    def get_hand_type(self, hand):
        """判断整手牌的花色组合类型（同花、同色、杂色）"""
        suits = [card.suit for card in hand]
        # 同花：所有牌同一花色（符号或英文名称都能比）
        if len(set(suits)) == 1:
            return 'same_suit'

        # 同色：所有牌同一颜色
        colors = [self.get_card_color(card.suit) for card in hand]
        if None not in colors and len(set(colors)) == 1:
            return 'same_color'

        # 其它都算杂色
        return 'mixed'
    
    def get_pair_type(self, card1, card2):
        """获取对子类型：AA同花/其他同花/同色/杂色"""
        # 检查是否同花
        if card1.suit == card2.suit:
            if card1.rank == 'A' and card2.rank == 'A':
                return 'same_suit_AA'
            else:
                return 'same_suit_other'
        
        # 检查是否同色
        color1 = self.get_card_color(card1.suit)
        color2 = self.get_card_color(card2.suit)
        if color1 and color2 and color1 == color2:
            return 'same_color'
        
        # 否则是杂色
        return 'mixed'

    def evaluate_bets(self):
        """评估下注结果"""
        dealer_value = self.calculate_hand_value(self.dealer_hand)
        self.dealer_twenty_two = (dealer_value == 22)
        
        dealer_bust = dealer_value > 21
        
        winnings = 0
        self.bet_results = {}  # 重置结果
        
        # 如果庄家22点（爆牌）
        if self.dealer_twenty_two:
            # 点数下注(16-20)平局退还
            for bet_type in ['16', '17', '18', '19', '20']:
                bet_amount = self.bets[bet_type]
                self.bet_results[bet_type] = (
                    "tie",
                    bet_amount,
                    f"{BET_ODDS[bet_type]}:1"
                )
            
            # 22点下注
            hand_type = self.get_hand_type(self.dealer_hand)
            odds = BET_ODDS['twenty_two'][hand_type]
            if hand_type == 'same_suit':
                odds_type = "同花50:1"
            elif hand_type == 'same_color':
                odds_type = "同色20:1"
            else:
                odds_type = "杂色8:1"
            
            win_amount = self.bets['twenty_two'] * (1 + odds)
            winnings += win_amount
            self.bet_results['twenty_two'] = (
                "win",
                win_amount,
                odds_type
            )
            
            # 对子下注
            if self.dealer_pair and len(self.dealer_hand) >= 2:
                card1, card2 = self.dealer_hand[0], self.dealer_hand[1]
                pair_type = self.get_pair_type(card1, card2)
                odds = BET_ODDS['pair'][pair_type]
                if pair_type == 'same_suit_AA':
                    odds_type = "AA同花60:1"
                elif pair_type == 'same_suit_other':
                    odds_type = "同花对子30:1"
                elif pair_type == 'same_color':
                    odds_type = "同色15:1"
                else:
                    odds_type = "杂色7:1"
                
                win_amount = self.bets['pair'] * (1 + odds)
                winnings += win_amount
                self.bet_results['pair'] = (
                    "win",
                    win_amount,
                    odds_type
                )
            else:
                self.bet_results['pair'] = ("lose", 0, "最高60:1")
            
            # 小下注
            small_win = (
                self.bets['small'] * (1 + BET_ODDS['small'])
                if len(self.dealer_hand) == 2 and not dealer_bust and self.bets['small'] > 0
                else 0
            )
            if small_win > 0:
                winnings += small_win
            self.bet_results['small'] = (
                "win" if small_win > 0 else "lose",
                small_win,
                "1.75:1"
            )
            
            # 大下注
            big_win = (
                self.bets['big'] * (1 + BET_ODDS['big'])
                if len(self.dealer_hand) >= 4 and not dealer_bust and self.bets['big'] > 0
                else 0
            )
            if big_win > 0:
                winnings += big_win
            self.bet_results['big'] = (
                "win" if big_win > 0 else "lose",
                big_win,
                "3.5:1"
            )
            
            # BJ、22点以外的其他注项
            self.bet_results['bj'] = ("lose", 0, "最高50:1")
        
        # 如果庄家Blackjack（头两张牌21点）
        elif self.dealer_blackjack:
            # 点数下注(16-20)输
            for bet_type in ['16', '17', '18', '19', '20']:
                self.bet_results[bet_type] = (
                    "lose",
                    0,
                    f"{BET_ODDS[bet_type]}:1"
                )
            
            # BJ下注
            card1, card2 = self.dealer_hand[0], self.dealer_hand[1]
            if card1.suit == card2.suit:
                pair_type = 'same_suit'
            elif self.get_card_color(card1.suit) == self.get_card_color(card2.suit):
                pair_type = 'same_color'
            else:
                pair_type = 'mixed'
            odds = BET_ODDS['bj'][pair_type]
            if pair_type == 'same_suit':
                odds_type = "同花50:1"
            elif pair_type == 'same_color':
                odds_type = "同色25:1"
            else:
                odds_type = "杂色11:1"
            
            bj_win = self.bets['bj'] * (1 + odds)
            winnings += bj_win
            self.bet_results['bj'] = ("win", bj_win, odds_type)
            
            # 小下注（庄家2张停牌）
            small_win = self.bets['small'] * (1 + BET_ODDS['small'])
            winnings += small_win
            self.bet_results['small'] = ("win", small_win, "1.75:1")
            
            # 对子下注
            if self.dealer_pair and len(self.dealer_hand) >= 2:
                card1, card2 = self.dealer_hand[0], self.dealer_hand[1]
                pair_type = self.get_pair_type(card1, card2)
                odds = BET_ODDS['pair'][pair_type]
                if pair_type == 'same_suit_AA':
                    odds_type = "AA同花60:1"
                elif pair_type == 'same_suit_other':
                    odds_type = "同花对子30:1"
                elif pair_type == 'same_color':
                    odds_type = "同色15:1"
                else:
                    odds_type = "杂色7:1"
                
                pair_win = self.bets['pair'] * (1 + odds)
                winnings += pair_win
                self.bet_results['pair'] = ("win", pair_win, odds_type)
            else:
                self.bet_results['pair'] = ("lose", 0, "最高60:1")
            
            # 大下注
            big_win = (
                self.bets['big'] * (1 + BET_ODDS['big'])
                if len(self.dealer_hand) >= 4 and not dealer_bust and self.bets['big'] > 0
                else 0
            )
            if big_win > 0:
                winnings += big_win
            self.bet_results['big'] = (
                "win" if big_win > 0 else "lose",
                big_win,
                "3.5:1"
            )
            
            # 22点下注
            self.bet_results['twenty_two'] = ("lose", 0, "最高50:1")
        
        # 正常情况（非22点，非Blackjack）
        else:
            # 点数下注
            for bet_type in ['16', '17', '18', '19', '20']:
                bet_value = int(bet_type)
                bet_amount = self.bets[bet_type]
                
                if dealer_bust or bet_value > dealer_value:
                    win_amt = bet_amount * (1 + BET_ODDS[bet_type]) if bet_amount > 0 else 0
                    winnings += win_amt
                    self.bet_results[bet_type] = ("win", win_amt, f"{BET_ODDS[bet_type]}:1")
                elif bet_value == dealer_value:
                    tie_amt = bet_amount
                    winnings += tie_amt
                    self.bet_results[bet_type] = ("tie", tie_amt, f"{BET_ODDS[bet_type]}:1")
                else:
                    self.bet_results[bet_type] = ("lose", 0, f"{BET_ODDS[bet_type]}:1")
            
            # 对子下注
            if self.dealer_pair and len(self.dealer_hand) >= 2:
                card1, card2 = self.dealer_hand[0], self.dealer_hand[1]
                pair_type = self.get_pair_type(card1, card2)
                odds = BET_ODDS['pair'][pair_type]
                if pair_type == 'same_suit_AA':
                    odds_type = "AA同花60:1"
                elif pair_type == 'same_suit_other':
                    odds_type = "同花对子30:1"
                elif pair_type == 'same_color':
                    odds_type = "同色15:1"
                else:
                    odds_type = "杂色7:1"
                
                pair_win = self.bets['pair'] * (1 + odds)
                winnings += pair_win
                self.bet_results['pair'] = ("win", pair_win, odds_type)
            else:
                self.bet_results['pair'] = ("lose", 0, "最高60:1")
            
            # 小下注
            small_win = (
                self.bets['small'] * (1 + BET_ODDS['small'])
                if len(self.dealer_hand) == 2 and not dealer_bust and self.bets['small'] > 0
                else 0
            )
            if small_win > 0:
                winnings += small_win
            self.bet_results['small'] = (
                "win" if small_win > 0 else "lose",
                small_win,
                "1.75:1"
            )
            
            # 大下注
            big_win = (
                self.bets['big'] * (1 + BET_ODDS['big'])
                if len(self.dealer_hand) >= 4 and not dealer_bust and self.bets['big'] > 0
                else 0
            )
            if big_win > 0:
                winnings += big_win
            self.bet_results['big'] = (
                "win" if big_win > 0 else "lose",
                big_win,
                "3.5:1"
            )
            
            # BJ、22点下注
            self.bet_results['bj'] = ("lose", 0, "最高50:1")
            self.bet_results['twenty_two'] = ("lose", 0, "最高50:1")
        
        # 最终返回并存储本局总赢额
        self.winnings = winnings
        return winnings

class Simple21GUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("简单21点")
        self.geometry("1080x680+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = Simple21Game()
        self.card_images = {}
        self.original_images = {}  # 用于存储原始卡片图像
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []  # 追踪所有活动中的卡片标签
        self.selected_chip = None  # 当前选中的筹码
        self.chip_buttons = []  # 筹码按钮列表
        self.chip_texts = {}  # 存储每个筹码按钮的文本
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.cut_card_label = None  # 切牌标签
        self.cut_card_visible = False
        self.bet_labels = {}  # 存储下注标签
        self.dealer_card_labels = []  # 存储庄家牌标签
        self.bet_boxes = {}  # 存储下注框引用
        self.original_bg_colors = {}  # 存储原始背景颜色
        self.original_odds_texts = {}  # 存储原始赔率文本
        self.scrollbar_visible = False  # 滚动条可见状态
        self.replay_button_enabled = True  # 新增：防止"再来一局"按钮连击
        self.dealer_outcome = None  # 新增：记录庄家最终结果

        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
    
    def calculate_card_positions(self, card_count):
        """根据牌张数计算卡片位置"""
        max_width = 690  # 庄家区域最大宽度
        card_width = 100  # 每张牌宽度
        
        # 如果牌数少于6张，使用固定间距
        if card_count < 6:
            return [(i * 120, 0) for i in range(card_count)]
        
        # 计算最大可用空间（减去最后一张牌的宽度）
        available_width = max_width - card_width
        
        # 计算间距（在牌之间平均分配可用空间）
        spacing = available_width / (card_count - 1)
        
        # 生成位置列表
        positions = []
        for i in range(card_count):
            x = i * spacing
            positions.append((x, 0))
        
        return positions
        
    def _load_assets(self):
        card_size = (100, 140)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        
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
            self.original_images["back"] = Image.open(back_path)  # 保存原始图像
        except Exception as e:
            print(f"Error loading back image: {e}")
            # 如果没有背景图，创建一个黑色背景
            img = Image.new('RGB', card_size, 'black')
            self.back_image = ImageTk.PhotoImage(img)
            self.original_images["back"] = img  # 保存原始图像
        
        # 加载扑克牌图片
        for suit in SUITS:
            for rank in RANKS:
                # 获取映射后的文件名
                suit_name = suit_mapping.get(suit, suit)
                
                # 尝试可能的文件名组合
                possible_filenames = [
                    f"{suit_name}{rank}.png",       # 如 "SpadeA.png"
                    f"{suit_name}_{rank}.png",      # 如 "Spade_A.png"
                    f"{suit[0]}{rank}.png",         # 如 "SA.png"
                ]
                
                img_found = False
                for filename in possible_filenames:
                    path = os.path.join(card_dir, filename)
                    if os.path.exists(path):
                        try:
                            img = Image.open(path).resize(card_size)
                            self.card_images[(suit, rank)] = ImageTk.PhotoImage(img)
                            self.original_images[(suit, rank)] = Image.open(path)  # 保存原始图像
                            img_found = True
                            break
                        except Exception as e:
                            print(f"Error loading {path}: {e}")
                
                # 如果没有找到图片，创建一个占位图片
                if not img_found:
                    print(f"Card image not found for {suit}{rank}")
                    img = Image.new('RGB', card_size, 'blue')
                    draw = ImageDraw.Draw(img)
                    # 在图片上绘制花色和点数
                    try:
                        font = ImageFont.truetype("arial.ttf", 24)
                        text = f"{suit}{rank}"
                        draw.text((10, 10), text, font=font, fill="white")
                    except:
                        # 如果字体加载失败，使用简单文本
                        draw.text((10, 10), f"{suit}{rank}", fill="white")
                    
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img)
                    self.original_images[(suit, rank)] = img  # 保存原始图像
        
        # 加载切牌图片
        joker_path = os.path.join(card_dir, 'JOKER-A.png')
        if os.path.exists(joker_path):
            try:
                joker_img = Image.open(joker_path).resize(card_size)
                self.joker_image = ImageTk.PhotoImage(joker_img)
            except:
                img = Image.new('RGB', card_size, 'purple')
                draw = ImageDraw.Draw(img)
                draw.text((30, 60), "CUT CARD", fill="gold", font=ImageFont.load_default())
                self.joker_image = ImageTk.PhotoImage(img)
        else:
            img = Image.new('RGB', card_size, 'purple')
            draw = ImageDraw.Draw(img)
            draw.text((30, 60), "CUT CARD", fill="gold", font=ImageFont.load_default())
            self.joker_image = ImageTk.PhotoImage(img)

    def add_chip_to_bet(self, bet_type):
        """添加筹码到下注区域"""
        if not self.selected_chip:
            return
            
        # 获取筹码金额
        chip_value = self.selected_chip.replace('$', '')
        if chip_value.endswith('K'):
            chip_value = float(chip_value.replace('K', '')) * 1000
        else:
            chip_value = float(chip_value)
        
        # 更新对应的下注
        if self.game.place_bet(bet_type, chip_value):
            self.balance -= chip_value
            self.update_balance()
            # 更新下注金额显示
            self.bet_labels[bet_type]['bet_amount'].config(text=f"${self.game.bets[bet_type]:.2f}")
    
    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d', width=1050, height=680)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域 - 固定高度
        left_frame = tk.Frame(main_frame, bg='#35654d', width=750, height=500)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_frame.pack_propagate(False)  # 固定高度
        
        # 庄家区域 - 固定高度
        dealer_frame = tk.Frame(left_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED, width=730, height=230)
        dealer_frame.pack(fill=tk.X, padx=10, pady=10)
        dealer_frame.pack_propagate(False)  # 固定高度
        
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        
        # 庄家牌区域 - 创建并保存为实例变量
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c', width=690, height=140)
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.dealer_cards_frame.pack_propagate(False)
        
        # 添加提示标签
        rule_label = tk.Label(
            left_frame, 
            text="庄家16点要牌 任何17点停牌 | 庄家22点 点数区平局", 
            font=('Arial', 22, 'bold'), 
            bg='#35654d', 
            fg='#FFD700',
            width=40
        )
        rule_label.pack(pady=(0, 10))
        
        # 下注区域 - 固定高度
        bet_frame = tk.Frame(left_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED, width=730, height=360)
        bet_frame.pack(fill=tk.BOTH, padx=10, pady=10)
        bet_frame.pack_propagate(False)  # 固定高度
        
        bet_label = tk.Label(bet_frame, text="玩家下注区域", font=('Arial', 18), bg='#2a4a3c', fg='white')
        bet_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        
        # 创建下注按钮网格（两行五列）
        bet_grid = tk.Frame(bet_frame, bg='#2a4a3c', width=710, height=320)
        bet_grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        bet_grid.pack_propagate(False)
        
        # 下注类型和赔率（两行五列）
        bet_types = [
            # 第一行 - 点数区域，颜色 #b2b6b6
            ('16点', '16', '#b2b6b6', "2.45:1"),
            ('17点', '17', '#b2b6b6', "1.93:1"),
            ('18点', '18', '#b2b6b6', "0.95:1"),
            ('19点', '19', '#b2b6b6', "0.48:1"),
            ('20点', '20', '#b2b6b6', "0.13:1"),
            # 第二行 - 特殊下注区域，颜色 #ff7f50
            ('小', 'small', '#ff7f50', "1.75:1"),
            ('对子', 'pair', '#ff7f50', "最高60:1"),  # 修改为"最高60:1"
            ('BJ', 'bj', '#ff7f50', "最高50:1"),
            ('22点', 'twenty_two', '#ff7f50', "最高50:1"),
            ('大', 'big', '#ff7f50', "3.5:1")
        ]
        
        self.bet_labels = {}
        for i, (label, bet_type, color, odds) in enumerate(bet_types):
            row = i // 5  # 0或1
            col = i % 5   # 0-4
            
            # 创建固定宽度的下注框 - 统一为120x120
            bet_box = tk.Frame(
                bet_grid, 
                bg=color, 
                bd=2, 
                relief=tk.RAISED,
                width=120,  # 固定宽度
                height=120  # 固定高度
            )
            bet_box.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            bet_box.grid_propagate(False)  # 禁止网格调整大小
            bet_box.pack_propagate(False)   # 新增：禁止子控件影响尺寸  <--- 关键修改
            bet_box.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            self.bet_boxes[bet_type] = bet_box
            
            # 点数标签 - 顶部 (固定宽度)
            point_label = tk.Label(
                bet_box, 
                text=label, 
                font=('Arial', 14, 'bold'), 
                bg=color, 
                fg='black',
                width=8,  # 新增：固定标签宽度 <--- 确保文本不会撑大
                anchor='center'  # 居中显示
            )
            point_label.pack(pady=(10, 0), fill=tk.X)
            point_label.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            
            # 赔率标签 - 中间 (固定宽度)
            odds_label = tk.Label(
                bet_box, 
                text=odds, 
                font=('Arial', 12), 
                bg=color, 
                fg='black',
                width=8,  # 新增：固定标签宽度 <--- 确保文本不会撑大
                anchor='center'  # 居中显示
            )
            odds_label.pack(pady=5, fill=tk.X)
            odds_label.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            
            # 下注金额显示 - 底部 (固定宽度)
            bet_amount = tk.Label(
                bet_box, 
                text="$0.00", 
                font=('Arial', 12, 'bold'), 
                bg=color, 
                fg='black',
                width=8,  # 新增：固定标签宽度 <--- 确保文本不会撑大
                anchor='center'  # 居中显示
            )
            bet_amount.pack(side=tk.BOTTOM, pady=(0, 10), fill=tk.X)
            bet_amount.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            
            # 存储下注金额标签和赔率标签
            self.bet_labels[bet_type] = {
                'bet_amount': bet_amount,
                'odds_label': odds_label,
                'point_label': point_label
            }
            
            # 存储原始背景颜色和赔率文本
            self.original_bg_colors[bet_type] = color
            self.original_odds_texts[bet_type] = odds
        
        # 平均分配网格列宽
        for i in range(5):
            bet_grid.columnconfigure(i, weight=1, uniform="bet_cols")
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=350, height=640)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        control_frame.pack_propagate(False)
        
        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED, width=250, height=50)
        info_frame.pack(fill=tk.X, pady=10)
        info_frame.pack_propagate(False)
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 14),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED, width=300, height=200)
        chips_frame.pack(fill=tk.X, pady=10)
        chips_frame.pack_propagate(False)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 12), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        
        # 第一行筹码：5, 10, 25, 50
        chip_row1 = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row1.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs1 = [
            ("$5", '#ff0000', 'white'),
            ("$10", '#ffa500', 'black'),
            ("$25", '#00ff00', 'black'),
            ("$50", '#ffffff', 'black')
        ]
        
        for text, bg_color, fg_color in chip_configs1:
            chip_canvas = tk.Canvas(chip_row1, width=60, height=60, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 58, 58, fill=bg_color, outline='black')
            text_id = chip_canvas.create_text(30, 30, text=text, fill=fg_color, font=('Arial', 16, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text  # 存储文本
        
        # 第二行筹码：100, 500, 1K, 5K
        chip_row2 = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row2.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs2 = [
            ("$100", '#000000', 'white'),
            ("$500", '#800080', 'white'),
            ("$1K", '#FF69B4', 'black'),
            ("$5K", '#00FFFF', 'black')
        ]
        
        for text, bg_color, fg_color in chip_configs2:
            chip_canvas = tk.Canvas(chip_row2, width=60, height=60, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 58, 58, fill=bg_color, outline='black')
            text_id = chip_canvas.create_text(30, 30, text=text, fill=fg_color, font=('Arial', 16, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text  # 存储文本
        
        # 默认选中$5筹码
        self.select_chip("$5")
        
        # 游戏操作按钮框架
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c', width=250, height=150)
        self.action_frame.pack(fill=tk.X, pady=10)
        self.action_frame.pack_propagate(False)

        # 创建开始游戏按钮
        self.start_button = tk.Button(
            self.action_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=15
        )
        self.start_button.pack(pady=10)
        
        # 添加重设金额按钮
        self.reset_bets_button = tk.Button(
            self.action_frame, text="重设金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=15
        )
        self.reset_bets_button.pack(pady=10)
        
        # 创建再来一局按钮（初始隐藏）
        self.replay_button = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.replay_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=15
        )
        # 初始时不显示
        self.replay_button.pack_forget()
        
        # 状态信息
        self.status_label = tk.Label(
            control_frame, text="请选择下注区域并下注", 
            font=('Arial', 12), bg='#2a4a3c', fg='white',
            width=30
        )
        self.status_label.pack(pady=5, fill=tk.X)
        
        # 结果展示
        self.result_label = tk.Label(
            control_frame, text="", 
            font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', justify='center',
            width=30
        )
        self.result_label.pack(pady=5, fill=tk.X)
        
        # 本局下注和上局获胜金额显示
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED, width=250, height=80)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        bet_info_frame.pack_propagate(False)
        
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
        
        # 切牌标签（初始隐藏）
        self.cut_card_label = tk.Label(self, image=self.joker_image, bg='#35654d')
        
        # 创建滚动条框架（初始隐藏）
        self.scroll_frame = tk.Frame(self.dealer_cards_frame, bg='#2a4a3c', height=20)
        self.scroll_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.scroll_frame.pack_forget()
        
        # 创建滚动条
        self.scrollbar = ttk.Scrollbar(self.scroll_frame, orient=tk.HORIZONTAL)
        self.scrollbar.pack(fill=tk.X, padx=10, pady=2)
    
    def show_game_instructions(self):
        """显示游戏规则说明"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("简单21点游戏规则")
        win.geometry("600x500")
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
        简单21点游戏规则

        1. 游戏开始前下注:
           - 玩家可以在10个下注区域下注: 
             第一行: 16点, 17点, 18点, 19点, 20点
             第二行: 小, 对子, BJ, 22点, 大
           - 每个下注区域有不同赔率:
             * 16点: 2.45:1
             * 17点: 1.93:1
             * 18点: 0.95:1
             * 19点: 0.48:1
             * 20点: 0.13:1
             * 对子: 
                 - AA同花: 60:1
                 - 其他同花对子: 30:1
                 - 同色非同花: 15:1
                 - 杂色对子: 7:1
             * 小: 1.75:1
             * 大: 3.5:1
             * BJ: 最高50:1 (同花50:1, 同色25:1, 杂色11:1)
             * 22点: 最高50:1 (同花50:1, 同色20:1, 杂花8:1)

        2. 游戏流程:
           a. 下注阶段:
               - 玩家选择一个或多个下注区域下注
               - 点击"开始游戏"按钮开始

           b. 发牌:
               - 庄家发两张牌(一张明, 一张暗)
               - 玩家没有手牌

           c. 庄家回合:
               - 庄家按照标准规则补牌: 
                 * 16点及以下必须补牌
                 * 17点及以上停牌(包括Soft 17)
               - 庄家补牌直到停牌或爆牌

           d. 结算:
               - 根据庄家最终点数结算每个下注区域
               - 对子下注只取决于庄家头两张牌
               - BJ下注只取决于庄家头两张牌是否为21点
               - 22点下注取决于庄家最终点数为22点
               - 小/大下注取决于庄家停牌时的牌张数

        3. 特殊规则:
           a. 庄家22点:
               - 点数下注(16-20点)平局退还
               - 22点下注获胜，赔率根据花色组合:
                 * 同花: 所有牌同一花色 (50:1)
                 * 同色: 所有牌同一颜色 (20:1)
                 * 杂色: 混合花色 (8:1)
               - 其他下注正常结算

           b. 庄家Blackjack(头两张牌21点):
               - 点数下注(16-20点)输
               - BJ下注获胜，赔率根据花色组合:
                 * 同花: 两张牌同一花色 (50:1)
                 * 同色: 两张牌同一颜色 (25:1)
                 * 杂色: 混合花色 (11:1)
               - 小下注获胜(赔率1.75:1)

           c. 小/大下注:
               - 小: 庄家刚好2张牌停牌(包括Soft17和庄家BJ)，赔率1.75:1
               - 大: 庄家4张牌或以上停牌，赔率3.5:1
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
    
    def disable_action_buttons(self):
        """禁用所有操作按钮"""
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            widget.config(state=tk.DISABLED)
    
    def enable_action_buttons(self):
        """启用所有操作按钮"""
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            widget.config(state=tk.NORMAL)
    
    def start_game(self):
        """开始新游戏"""
        if self.game.total_bet == 0:
            messagebox.showerror("错误", "请至少在一个区域下注")
            return

        if self.balance < 0:
            self.balance -= 150
            self.update_balance()
            messagebox.showerror("余额不足", "您的余额不足，已扣除150元手续费")
            return

        # 解除下注区域点击
        for bet_type, box in self.bet_boxes.items():
            box.unbind("<Button-1>")
            for lbl in self.bet_labels[bet_type].values():
                lbl.unbind("<Button-1>")

        self.current_bet_label.config(text=f"本局下注: ${self.game.total_bet:.2f}")
        self.disable_action_buttons()
        self.status_label.config(text="发牌中...")
        self.last_win_label.config(text="上局获胜: $0.00")

        self.game.reset_game()
        for bt in self.game.bets:
            amt_text = self.bet_labels[bt]['bet_amount'].cget("text").replace('$', '')
            self.game.bets[bt] = float(amt_text or 0.0)
        self.game.total_bet = sum(self.game.bets.values())

        for w in self.dealer_cards_frame.winfo_children():
            if w is not self.scroll_frame:
                w.destroy()
        self.dealer_card_labels.clear()
        self.scroll_frame.pack_forget()
        self.scrollbar_visible = False

        self.game.deal_initial()
        self.deal_dealer_cards()
    
    def replay_game(self):
        """再来一局"""
        # 检查按钮是否可用
        if not self.replay_button_enabled:
            return
            
        # 禁用按钮防止连击
        self.replay_button_enabled = False
        
        # 隐藏"再来一局"按钮
        self.replay_button.pack_forget()
        
        # 重置游戏状态
        self.reset_for_new_round()
    
    def deal_dealer_cards(self):
        """发庄家牌（带动画）"""
        # 清除旧牌（保留滚动条框架）
        for widget in self.dealer_cards_frame.winfo_children():
            if widget != self.scroll_frame:
                widget.destroy()
        
        # 初始化卡片位置
        self.card_positions = {}
        self.animation_queue = []
        
        # 计算所有牌的目标位置
        card_count = len(self.game.dealer_hand)
        target_positions = self.calculate_card_positions(card_count)
        
        # 添加庄家牌到动画队列
        for i, card in enumerate(self.game.dealer_hand):
            card_id = f"dealer_{i}"
            self.card_positions[card_id] = {
                "current": (50, 50), 
                "target": target_positions[i]  # 使用计算后的位置
            }
            self.animation_queue.append((card_id, card, i == 0))  # 第一张牌需要翻开
        
        # 开始动画
        self.animate_deal()
    
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            # 发牌动画完成后翻开第一张牌
            self.after(500, self.reveal_first_card)
            return
            
        self.animation_in_progress = True
        card_id, card, is_first = self.animation_queue.pop(0)
        
        # 创建卡片标签
        card_label = tk.Label(
            self.dealer_cards_frame, 
            image=self.back_image, 
            bg='#2a4a3c'
        )
        card_label.place(
            x=self.card_positions[card_id]["current"][0],
            y=self.card_positions[card_id]["current"][1] + 20
        )
        
        # 存储卡片信息
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        card_label.is_first = is_first
        
        # 添加到活动卡片列表
        self.active_card_labels.append(card_label)
        self.dealer_card_labels.append(card_label)
        
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
                card_label.place(x=target_x, y=target_y)
                card_label.is_moving = False
                self.after(100, self.animate_deal)  # 处理下一张牌
                return
            
            # 计算移动步长
            step_x = dx * 0.2
            step_y = dy * 0.2
            
            # 更新位置
            new_x = current_x + step_x
            new_y = current_y + step_y
            card_label.place(x=new_x, y=new_y)
            
            # 继续动画
            self.after(20, lambda: self.animate_card_move(card_label))
            
        except tk.TclError:
            # 卡片已被销毁，停止动画
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)
            return
    
    def reveal_first_card(self):
        """翻开庄家第一张牌"""
        if len(self.dealer_card_labels) > 0:
            card_label = self.dealer_card_labels[0]
            self.flip_card_animation(card_label)
        
        # 等待1秒后翻开第二张牌
        self.after(1000, self.reveal_second_card)
    
    def reveal_second_card(self):
        """翻开庄家第二张牌"""
        if len(self.dealer_card_labels) > 1:
            card_label = self.dealer_card_labels[1]
            self.flip_card_animation(card_label)
            
            # 更新庄家点数显示
            self.dealer_label_update()
        
        # 开始庄家回合
        self.after(1000, self.dealer_turn)
    
    def dealer_label_update(self):
        """统一更新庄家标签显示"""
        dealer_value = self.game.calculate_hand_value(self.game.dealer_hand)
        if self.game.dealer_blackjack:
            self.dealer_label.config(text="庄家 - BJ")
        elif self.game.dealer_twenty_two:
            hand_type = self.game.get_hand_type(self.game.dealer_hand)
            type_text = {
                'same_suit': '同花',
                'same_color': '同色',
                'mixed': '杂色'
            }[hand_type]
            self.dealer_label.config(text=f"庄家 - {type_text}Push 22")
        else:
            if dealer_value > 21:
                self.dealer_label.config(text=f"庄家 - {dealer_value}点(爆牌)")
            else:
                self.dealer_label.config(text=f"庄家 - {dealer_value}点")
    
    def flip_card_animation(self, card_label):
        """卡片翻转动画"""
        # 获取卡片正面图像
        card = card_label.card
        if card.is_joker:
            front_img = self.joker_image
        else:
            # 创建新的花色映射，支持符号和英文名称
            suit_mapping = {
                # 符号映射
                '♠': ['Spade', 'S'],
                '♥': ['Heart', 'H'],
                '♦': ['Diamond', 'D'],
                '♣': ['Club', 'C'],
                # 英文名称映射
                'Spade': ['Spade', 'S'],
                'Heart': ['Heart', 'H'],
                'Diamond': ['Diamond', 'D'],
                'Club': ['Club', 'C']
            }
            
            # 获取可能的文件名前缀
            if card.suit in suit_mapping:
                suit_prefixes = suit_mapping[card.suit]
            else:
                # 如果花色不在映射中，默认使用符号
                suit_prefixes = [card.suit, card.suit]
            
            front_img = None
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
            
            # 尝试多种可能的文件名组合
            possible_filenames = [
                f"{suit_prefixes[0]}{card.rank}.png",  # SpadeA.png
                f"{suit_prefixes[0]}_{card.rank}.png", # Spade_A.png
                f"{suit_prefixes[1]}{card.rank}.png",  # SA.png
                f"{suit_prefixes[1]}_{card.rank}.png", # S_A.png
                f"{card.suit}{card.rank}.png"          # ♠A.png
            ]
            
            for filename in possible_filenames:
                path = os.path.join(card_dir, filename)
                if os.path.exists(path):
                    try:
                        img = Image.open(path).resize((100, 140))
                        front_img = ImageTk.PhotoImage(img)
                        break
                    except:
                        continue
            
            # 如果都没找到，使用默认背景
            if front_img is None:
                front_img = self.back_image
        
        # 直接显示正面
        card_label.config(image=front_img)
        card_label.image = front_img  # 保持引用避免垃圾回收
        card_label.is_face_up = True
    
    def dealer_turn(self):
        """庄家回合"""
        self.status_label.config(text="庄家行动中...")
        
        # 庄家补牌
        dealer_value = self.game.calculate_hand_value(self.game.dealer_hand)
        
        # 检查是否需要补牌
        if dealer_value <= 16:
            # 庄家补牌
            hit, new_card = self.game.dealer_hit()
            if hit:
                # 显示新牌
                self.add_dealer_card(new_card)
                
                # 检查切牌
                if new_card.is_joker:
                    self.show_cut_card()
                    # 切牌显示后继续庄家回合
                    self.after(2000, self.continue_dealer_after_cut)
            else:
                # 庄家停牌
                self.status_label.config(text="庄家停牌")
                self.dealer_outcome = "庄家停牌"
                # 确保庄家回合完全结束后再进入结算
                self.after(1000, self.finish_dealer_turn)
        else:
            # 庄家停牌或爆牌
            if dealer_value > 21:
                self.status_label.config(text="庄家爆牌!")
                self.dealer_outcome = "庄家爆牌！"
            else:
                self.status_label.config(text="庄家停牌")
                self.dealer_outcome = "庄家停牌"
            # 确保庄家回合完全结束后再进入结算
            self.after(1000, self.finish_dealer_turn)
    
    def finish_dealer_turn(self):
        """完成庄家回合，进入结算阶段"""
        # 重置状态标签
        self.status_label.config(text="结算中...")
        # 调用结算函数
        self.show_showdown()
    
    def continue_dealer_after_cut(self):
        """切牌显示后继续庄家回合"""
        self.hide_cut_card()
        self.dealer_turn()
    
    def add_dealer_card(self, new_card):
        """添加庄家新牌（带动画）"""
        # 创建新牌标签
        card_id = f"dealer_{len(self.dealer_card_labels)}"
        
        # 计算所有牌的目标位置（包括新牌）
        card_count = len(self.dealer_card_labels) + 1
        target_positions = self.calculate_card_positions(card_count)
        
        # 更新所有牌的目标位置
        for i, card_label in enumerate(self.dealer_card_labels):
            card_id = card_label.card_id
            self.card_positions[card_id]["target"] = target_positions[i]
        
        # 为新牌创建ID和目标位置
        card_id = f"dealer_{len(self.dealer_card_labels)}"
        self.card_positions[card_id] = {
            "current": (50, 50),
            "target": target_positions[-1]  # 新牌放在最后
        }
        
        card_label = tk.Label(
            self.dealer_cards_frame, 
            image=self.back_image, 
            bg='#2a4a3c'
        )
        card_label.place(
            x=self.card_positions[card_id]["current"][0],
            y=self.card_positions[card_id]["current"][1] + 20
        )
        
        # 存储卡片信息
        card_label.card_id = card_id
        card_label.card = new_card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        card_label.is_first = False  # 不是第一张牌
        
        # 添加到活动卡片列表
        self.active_card_labels.append(card_label)
        self.dealer_card_labels.append(card_label)
        
        # 开始移动动画
        self.animate_card_move(card_label)
        
        # 动画完成后翻开新牌并更新点数
        self.after(1000, lambda: self.flip_and_update(card_label))

    def flip_and_update(self, card_label):
        """翻开牌并更新庄家点数显示"""
        self.flip_card_animation(card_label)
        
        # 更新庄家点数显示
        self.dealer_label_update()
    
    def show_cut_card(self):
        """显示切牌"""
        self.cut_card_label.place(x=10, y=10)
        self.cut_card_label.lift()
        self.cut_card_visible = True
        
        # 2秒后隐藏
        self.after(2000, self.hide_cut_card)
    
    def hide_cut_card(self):
        """隐藏切牌"""
        self.cut_card_label.place_forget()
        self.cut_card_visible = False
    
    def show_showdown(self):
        """摊牌并结算"""
        # 确保只结算一次
        if self.game.stage == "showdown":
            return
            
        # 禁用"再来一局"按钮防止提前点击
        self.replay_button_enabled = False
        self.replay_button.config(state=tk.DISABLED)
        
        self.status_label.config(text="结算中...")
        self.game.stage = "showdown"
        
        # 翻开庄家所有牌
        for card_label in self.dealer_card_labels:
            if not card_label.is_face_up:
                card = card_label.card
                if card.is_joker:
                    front_img = self.joker_image
                else:
                    # 尝试多种可能的文件名格式
                    suit_names = {
                        '♠': ['Spade', 'S'],
                        '♥': ['Heart', 'H'],
                        '♦': ['Diamond', 'D'],
                        '♣': ['Club', 'C']
                    }
                    front_img = None
                    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
                    
                    # 尝试多种可能的文件名组合
                    possible_filenames = [
                        f"{suit_names[card.suit][0]}{card.rank}.png",  # SpadeA.png
                        f"{suit_names[card.suit][0]}_{card.rank}.png", # Spade_A.png
                        f"{suit_names[card.suit][1]}{card.rank}.png",  # SA.png
                        f"{suit_names[card.suit][1]}_{card.rank}.png", # S_A.png
                        f"{card.suit}{card.rank}.png"                 # ♠A.png
                    ]
                    
                    for filename in possible_filenames:
                        path = os.path.join(card_dir, filename)
                        if os.path.exists(path):
                            try:
                                img = Image.open(path).resize((100, 140))
                                front_img = ImageTk.PhotoImage(img)
                                break
                            except:
                                continue
                    
                    # 如果都没找到，使用默认背景
                    if front_img is None:
                        front_img = self.back_image
                
                card_label.config(image=front_img)
                card_label.is_face_up = True
        
        # 结算下注
        winnings = self.game.evaluate_bets()
        self.balance += winnings
        self.update_balance()
        
        # 更新下注区域的显示
        self.update_bet_boxes()
        
        # 显示结果 - 简化显示
        dealer_value = self.game.calculate_hand_value(self.game.dealer_hand)
        result_text = ""
        
        # 根据庄家情况显示不同信息
        if self.game.dealer_blackjack:
            # 判断花色组合
            card1 = self.game.dealer_hand[0]
            card2 = self.game.dealer_hand[1]
            if card1.suit == card2.suit:
                pair_text = "同花"
            elif self.game.get_card_color(card1.suit) == self.game.get_card_color(card2.suit):
                pair_text = "同色"
            else:
                pair_text = "杂色"
                
            result_text = f"庄家{pair_text}21点 BlackJack!\n"
        elif self.game.dealer_twenty_two:
            # 判断花色组合
            hand_type = self.game.get_hand_type(self.game.dealer_hand)
            if hand_type == 'same_suit':
                pair_text = "同花"
            elif hand_type == 'same_color':
                pair_text = "同色"
            else:
                pair_text = "杂色"
                
            result_text = f"庄家{pair_text}22点!\n"
        else:
            # 正常情况
            result_text = f"庄家点数: {dealer_value}\n"
                
            # 根据输赢情况添加不同信息
            if winnings > self.game.total_bet:  # 有盈利
                result_text += f"您赢了: ${winnings:.2f}"
            elif winnings == self.game.total_bet:  # 平局
                result_text += "平局！\n"
            else:  # 亏损
                result_text += "送你好运！\n"
        
        self.result_label.config(text=result_text, fg='gold' if winnings > 0 else 'white')
        
        # 更新上局获胜金额
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        
        # 隐藏"开始游戏"和"重设金额"按钮
        self.start_button.pack_forget()
        self.reset_bets_button.pack_forget()
        
        # 显示"再来一局"按钮
        self.replay_button.pack(pady=10)
        
        # 结算完成后再启用按钮
        self.replay_button_enabled = True
        self.replay_button.config(state=tk.NORMAL)
        
    def update_bet_boxes(self):
        """根据结算结果更新所有下注区域的背景色、赔率和下注金额显示（无论是否下注均生效）"""
        for bet_type in self.bet_labels:
            # 直接获取该下注区域的结果
            result, win_amount, odds_text = self.game.bet_results[bet_type]
            
            # 根据结果设置背景色
            if result == "win":
                bg_color = "#FFD700"  # 金色 - 获胜
            elif result == "tie":
                bg_color = "#ADD8E6"   # 浅蓝色 - 平局
            else:
                bg_color = self.original_bg_colors[bet_type]  # 原始颜色 - 输
            
            # 应用背景色
            self.bet_boxes[bet_type].config(bg=bg_color)
            for lbl in self.bet_labels[bet_type].values():
                lbl.config(bg=bg_color)
            
            # 更新赔率显示
            self.bet_labels[bet_type]['odds_label'].config(text=odds_text)
            
            # 更新下注金额显示
            self.bet_labels[bet_type]['bet_amount'].config(text=f"${win_amount:.2f}" if win_amount > 0 else "$0.00")

    def reset_bets(self):
        """重置所有下注"""
        # 退还所有下注金额
        total_bet = sum(self.game.bets.values())
        self.balance += total_bet
        self.update_balance()
        
        # 重置下注记录
        self.game.bets = {
            '16': 0,
            '17': 0,
            '18': 0,
            '19': 0,
            '20': 0,
            'pair': 0,
            'small': 0,
            'bj': 0,
            'twenty_two': 0,
            'big': 0
        }
        self.game.total_bet = 0
        
        # 更新显示
        for bet_type in self.bet_labels:
            original_color = self.original_bg_colors[bet_type]
            original_odds = self.original_odds_texts[bet_type]
            self.bet_labels[bet_type]['bet_amount'].config(text="$0.00", bg=original_color)
            self.bet_labels[bet_type]['odds_label'].config(text=original_odds, bg=original_color)
            self.bet_labels[bet_type]['point_label'].config(bg=original_color)
            self.bet_boxes[bet_type].config(bg=original_color)
        
        self.current_bet_label.config(text="本局下注: $0.00")
        
        # 更新状态
        self.status_label.config(text="已重置所有下注金额")
    
    def reset_for_new_round(self):
        """重置游戏为新一局"""
        # 重置游戏
        self.game.reset_game()
        
        # 清除庄家牌
        for widget in self.dealer_cards_frame.winfo_children():
            if widget != self.scroll_frame:  # 保留滚动条框架
                widget.destroy()
        self.dealer_card_labels = []
        
        # 重置庄家标签
        self.dealer_label.config(text="庄家")
        
        # 隐藏滚动条
        self.scroll_frame.pack_forget()
        self.scrollbar_visible = False
        
        # 重置下注金额显示
        for bet_type in self.bet_labels:
            original_color = self.original_bg_colors[bet_type]
            original_odds = self.original_odds_texts[bet_type]
            self.bet_labels[bet_type]['bet_amount'].config(text="$0.00", bg=original_color)
            self.bet_labels[bet_type]['odds_label'].config(text=original_odds, bg=original_color)
            self.bet_labels[bet_type]['point_label'].config(bg=original_color)
            self.bet_boxes[bet_type].config(bg=original_color)
            
            # 重新绑定下注区域
            self.bet_boxes[bet_type].bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            # 重新绑定内部标签的事件
            for key in self.bet_labels[bet_type]:
                self.bet_labels[bet_type][key].bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
        
        # 重置控制面板显示
        self.current_bet_label.config(text="本局下注: $0.00")
        self.result_label.config(text="")
        self.status_label.config(text="新一局准备完成")
        
        # 重置按钮显示
        self.replay_button.pack_forget()
        self.reset_bets_button.pack(pady=10)
        self.start_button.pack(pady=10)
        self.after(1000, self.enable_action_buttons)
        
        # 重置按钮状态为可用
        self.replay_button_enabled = True

def main(initial_balance=1000, username="Guest"):
    app = Simple21GUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")