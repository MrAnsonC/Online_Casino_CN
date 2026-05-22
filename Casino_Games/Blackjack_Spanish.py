import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import secrets
import json
import os
import math
import subprocess, sys

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

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
        
    def __repr__(self):
        return f"{self.rank}{self.suit}"
    
    def get_value(self):
        if self.rank in ['J', 'Q', 'K']:
            return 10
        elif self.rank == 'A':
            return 11  # 初始值，游戏中会调整
        else:
            return int(self.rank)

class Deck:
    def __init__(self, num_decks=8):
        self.num_decks = num_decks
        self.cards = []
        self.generate_deck()
        self.shuffle()
        # 添加切牌位置（大约45张牌的位置）
        self.cut_card_position = len(self.cards) - 45
    
    def generate_deck(self):
        self.cards = [Card(suit, rank) for _ in range(self.num_decks) for suit in SUITS for rank in RANKS]
    
    def shuffle(self):
        """使用shuffle.py洗牌，失败则使用secrets洗牌"""
        try:
            # 获取shuffle.py的路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            shuffle_script = os.path.join(parent_dir, 'A_Tools', 'Card', 'shuffle.py')
            
            # 构建命令行参数
            cmd = [sys.executable, shuffle_script, 'false', str(self.num_decks)]
            
            # 执行shuffle.py
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # 解析JSON输出
                shuffle_data = json.loads(result.stdout)
                shuffled_deck = shuffle_data['deck']
                
                # 将字典转换为Card对象
                self.cards = []
                for card_dict in shuffled_deck:
                    suit = card_dict['suit']
                    rank = card_dict['rank']
                    self.cards.append(Card(suit, rank))
                
                # 移除所有点数为10的牌
                self.cards = [card for card in self.cards if card.rank != '10']
                return
            else:
                print(f"shuffle.py执行失败，使用secrets洗牌: {result.stderr}")
                
        except Exception as e:
            print(f"调用shuffle.py失败，使用secrets洗牌: {e}")
        
        # 回退到secrets洗牌
        self._secrets_shuffle()
    
    def _secrets_shuffle(self):
        """使用secrets模块进行安全的洗牌"""
        n = len(self.cards)
        for i in range(n - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]
        
        # 移除所有点数为10的牌
        self.cards = [card for card in self.cards if card.rank != '10']
        print(f"使用secrets洗牌完成，移除了10点牌，剩余{len(self.cards)}张牌")
    
    def deal_card(self):
        # 检查是否需要重新洗牌（剩余牌数 <= 45）
        if len(self.cards) <= 45:
            self.generate_deck()
            self.shuffle()
            # 重新设置切牌位置
            self.cut_card_position = len(self.cards) - 45
            
        if len(self.cards) == 0:
            self.generate_deck()
            self.shuffle()
            # 重新设置切牌位置
            self.cut_card_position = len(self.cards) - 45
            
        return self.cards.pop()
    
    def get_remaining_cards_count(self):
        """获取剩余牌堆中每种牌的数量"""
        count_dict = {}
        for suit in SUITS:
            count_dict[suit] = {}
            for rank in RANKS:
                count_dict[suit][rank] = 0
        
        for card in self.cards:
            count_dict[card.suit][card.rank] += 1
            
        return count_dict

class BlackjackGame:
    def __init__(self):
        self.reset_game()
    
    def reset_game(self):
        self.player_hand = []
        self.dealer_hand = []
        self.main_bet = 0
        self.perfect_pair_bet = 0
        self.twenty_one_plus_three_bet = 0
        self.royal_match_bet = 0
        self.twenty_two_side_bet = 0
        self.hot_3_bet = 0
        self.lucky_queen_bet = 0
        self.stage = "betting"  # betting, dealing, insurance, player_turn, dealer_turn, showdown
        self.player_done = False
        self.insurance_bet = 0
        self.insurance_taken = False
        self.player_blackjack = False
        self.dealer_blackjack = False
        self.player_immediate_win = None  # 存储立即结算的结果
        self.dealer_second_card_dealt = False  # 标记庄家第二张牌是否已发
        self.dealer_needs_to_play = False  # 标记庄家是否需要行动
        self.dealer_forced_hit_for_insurance = False  # 标记是否因保险而强制补牌
    
    def deal_initial_cards(self):
        """发初始牌：玩家第1张，庄家第1张，玩家第2张"""
        self.player_hand = [self.deck.deal_card(), self.deck.deal_card()]
        self.dealer_hand = [self.deck.deal_card()]
        # 庄家第二张牌暂不发
    
    def get_hand_value(self, hand):
        """
        返回手牌的最优点数（A 自动在 11 与 1 之间调整以不爆牌）。
        与原实现等价：先把每个 A 记为 11，再在需要时将部分 A 从 11 调整为 1。
        """
        # 初始总和：非 A 按 get_value()，A 先按 11 计算
        total = 0
        num_aces = 0
        for card in hand:
            if card.rank == 'A':
                total += 11
                num_aces += 1
            else:
                total += card.get_value()

        # 如超 21，则逐个把 A 从 11 调为 1（每次减 10），直到不爆或无 A 可调整
        aces_to_adjust = num_aces
        while total > 21 and aces_to_adjust > 0:
            total -= 10
            aces_to_adjust -= 1

        return total


    def is_soft_17(self, hand):
        """
        判断是否为 Soft 17：
        - 手牌的最终（调整后）点数等于 17，且
        - 在该最终点数中至少有一张 A 被计为 11（也就是存在至少一个 A 未被调整为 1）
        返回 True 表示 Soft 17（庄家在此必须要牌）；否则返回 False。

        兼容示例：
        A + 6             -> 17：Soft 17（有一个 A 当作 11） -> 返回 True
        A + A + 5         -> 初始 11+11+5=27 -> 调整一个 A 得到 17（剩下一个 A 仍为 11） -> Soft 17 -> True
        A + A + A + 4     -> 初始 33 -> 调整两个 A 得到 17（仍有一个 A 为 11） -> Soft 17 -> True
        10 + 7            -> 17：非 Soft 17（没有 A 作为 11） -> False
        """
        # 先按同样方式计算最终总点数，并跟踪剩余作为 11 的 A 数量
        total = 0
        num_aces = 0
        for card in hand:
            if card.rank == 'A':
                total += 11
                num_aces += 1
            else:
                total += card.get_value()

        # aces_counted_as_11 表示当前仍按 11 计入总和的 A 数量
        aces_counted_as_11 = num_aces
        while total > 21 and aces_counted_as_11 > 0:
            total -= 10
            aces_counted_as_11 -= 1

        # Soft 17 当且仅当：调整后总点数为 17，并且至少有一张 A 仍被当作 11
        return (total == 17) and (aces_counted_as_11 > 0)
    
    def player_hit(self):
        self.player_hand.append(self.deck.deal_card())
        return self.get_hand_value(self.player_hand)
    
    def dealer_hit(self):
        card = self.deck.deal_card()
        self.dealer_hand.append(card)
        return self.get_hand_value(self.dealer_hand), card
    
    def check_blackjack(self, hand):
        if len(hand) != 2:
            return False
        values = [card.get_value() for card in hand]
        return (11 in values and 10 in values) or (values[0] + values[1] == 21)
    
    def check_player_immediate_win(self):
        """检查玩家是否满足立即结算条件"""
        player_value = self.get_hand_value(self.player_hand)
        card_count = len(self.player_hand)
        
        # 2张牌21点
        if card_count == 2 and player_value == 21:
            return {"type": "blackjack", "payout": 2.5}  # 3:2 胜出，返回总金额（本金+赢额）
        
        # 5龙21点
        if card_count == 5 and player_value == 21:
            return {"type": "5_card_21", "payout": 3.0}  # 2:1 胜出，返回总金额（本金+赢额）
        
        # 任何21点（非2张牌）
        if player_value == 21:
            return {"type": "any_21", "payout": 2.0}  # 1:1 胜出，返回总金额（本金+赢额）
        
        # 5张牌（未爆牌）
        if card_count == 5 and player_value <= 21:
            return {"type": "5_card", "payout": 2.0}  # 1:1 胜出，返回总金额（本金+赢额）
        
        return None
    
    def check_perfect_pair(self):
        if len(self.player_hand) < 2:
            return False
            
        card1, card2 = self.player_hand[0], self.player_hand[1]
        
        # 完美对子 (相同花色和点数)
        if card1.rank == card2.rank and card1.suit == card2.suit:
            return "perfect"
        # 同色对子 (相同颜色和点数)
        elif (card1.rank == card2.rank and 
              ((card1.suit in ['♥', '♦'] and card2.suit in ['♥', '♦']) or 
               (card1.suit in ['♠', '♣'] and card2.suit in ['♠', '♣']))):
            return "colored"
        # 混合对子 (相同点数)
        elif card1.rank == card2.rank:
            return "mixed"
        else:
            return None
    
    def check_twenty_one_plus_three(self):
        if len(self.player_hand) < 2 or len(self.dealer_hand) < 1:
            return None
            
        ranks = [self.player_hand[0].rank, self.player_hand[1].rank, self.dealer_hand[0].rank]
        suits = [self.player_hand[0].suit, self.player_hand[1].suit, self.dealer_hand[0].suit]
        
        # 检查三条
        if ranks[0] == ranks[1] == ranks[2]:
            if len(set(suits)) == 1:
                return "straight_three_of_a_kind"
            else:
                return "three_of_a_kind"
        
        # 将牌面转换为数值
        rank_values = []
        for r in ranks:
            if r == 'A': rank_values.append(14)
            elif r == 'K': rank_values.append(13)
            elif r == 'Q': rank_values.append(12)
            elif r == 'J': rank_values.append(11)
            else: rank_values.append(int(r))
        
        rank_values.sort()
        
        # 检查是否为顺子（包含常规顺子和特殊顺子）
        def is_straight(values):
            # 常规顺子：点数连续
            if values[2] - values[1] == 1 and values[1] - values[0] == 1:
                return True
            
            # 特殊顺子：由于移除了10点牌，检查以下特殊组合
            special_straights = [
                [8, 9, 11],   # 8-9-J
                [9, 11, 12],  # 9-J-Q
                [11, 12, 13], # J-Q-K
                [12, 13, 14]  # Q-K-A
            ]
            
            return values in special_straights
        
        # 检查是否为同花
        is_flush = len(set(suits)) == 1
        
        # 检查是否为顺子
        is_straight_result = is_straight(rank_values)
        
        # 根据结果返回相应类型
        if is_flush and is_straight_result:
            return "straight_flush"
        elif is_flush:
            return "flush"
        elif is_straight_result:
            return "straight"
        else:
            return None
    
    def check_royal_match(self):
        if len(self.player_hand) < 2:
            return False
            
        card1, card2 = self.player_hand[0], self.player_hand[1]
        
        # 检查是否是同花
        if card1.suit != card2.suit:
            return False
            
        # 检查是否是Q和K
        if (card1.rank == 'Q' and card2.rank == 'K') or (card1.rank == 'K' and card2.rank == 'Q'):
            return "royal"
        else:
            return "suited"
    
    
    def check_hot_3(self):
        """检查热门3边注结果，A的值根据具体情况动态调整"""
        if len(self.player_hand) < 2 or len(self.dealer_hand) < 1:
            return None
            
        player_card1 = self.player_hand[0]
        player_card2 = self.player_hand[1]
        dealer_card = self.dealer_hand[0]
        
        # 计算三张牌的总点数，A的值根据具体情况动态调整
        def get_dynamic_value(card, other_cards):
            """根据其他牌的情况动态调整A的值"""
            if card.rank != 'A':
                return card.get_value()
            
            # 计算其他两张牌的总点数
            other_total = 0
            for other_card in other_cards:
                if other_card.rank == 'A':
                    other_total += 11  # 其他A暂时按11算
                else:
                    other_total += other_card.get_value()
            
            # 如果其他两张牌的总点数加上11会超过21，则A按1算
            if other_total + 11 > 21:
                return 1
            else:
                return 11
        
        # 计算三张牌的总点数
        total_value = 0
        cards = [player_card1, player_card2, dealer_card]
        
        for i, card in enumerate(cards):
            other_cards = [c for j, c in enumerate(cards) if j != i]
            total_value += get_dynamic_value(card, other_cards)
        
        # 检查是否都是7点
        all_sevens = (player_card1.rank == '7' and 
                    player_card2.rank == '7' and 
                    dealer_card.rank == '7')
        
        # 检查三张牌花色是否相同
        same_suit = (player_card1.suit == player_card2.suit == dealer_card.suit)
        
        if all_sevens:
            if same_suit:
                return "three_seven_same_suit"  # 500:1
            else:
                return "three_seven_mixed"  # 100:1
        elif total_value == 21:
            if same_suit:
                return "twenty_one_same_suit"  # 20:1
            else:
                return "twenty_one_mixed"  # 4:1
        elif total_value == 20:
            return "twenty"  # 2:1
        elif total_value == 19:
            return "nineteen"  # 1:1
        else:
            return None

    def check_lucky_queen(self):
        """检查幸运女王边注结果"""
        if len(self.player_hand) < 2:
            return None
            
        player_card1 = self.player_hand[0]
        player_card2 = self.player_hand[1]
        
        # 计算玩家头两张牌的总点数
        total_value = player_card1.get_value() + player_card2.get_value()
        
        if total_value != 20:
            return None
        
        # 检查两张牌是否都是Q
        both_queens = (player_card1.rank == 'Q' and player_card2.rank == 'Q')
        
        # 检查花色是否相同
        same_suit = (player_card1.suit == player_card2.suit)
        
        # 检查点数是否相同（注意：10-J这种不算相同点数）
        same_rank = (player_card1.rank == player_card2.rank)
        
        # 检查庄家是否有Blackjack
        dealer_blackjack = self.check_blackjack(self.dealer_hand)
        
        if both_queens and same_suit:
            if dealer_blackjack:
                return "queens_same_suit_dealer_bj"  # 1000:1
            else:
                return "queens_same_suit"  # 100:1
        elif same_rank and same_suit:
            return "same_rank_same_suit"  # 30:1
        elif same_suit:
            return "same_suit"  # 10:1
        else:
            return "mixed"  # 4:1
    
    def check_twenty_two_side_bet(self):
        """检查22点边注结果 - 使用庄家全部手牌"""
        if len(self.dealer_hand) < 2:
            return None
            
        dealer_value = self.get_hand_value(self.dealer_hand)
        
        if dealer_value != 22:
            return None
        
        # 检查庄家所有牌的花色
        suits = [card.suit for card in self.dealer_hand]
        
        # 检查是否同花
        if len(set(suits)) == 1:
            return "same_suit"  # 50:1
        
        # 检查是否同色（所有牌都是红色或所有牌都是黑色）
        red_suits = ['♥', '♦']
        black_suits = ['♠', '♣']
        
        all_red = all(suit in red_suits for suit in suits)
        all_black = all(suit in black_suits for suit in suits)
        
        if all_red or all_black:
            return "same_color"  # 20:1
        else:
            return "mixed_color"  # 8:1

class BlackjackGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("西班牙21点")
        self.geometry("1150x650+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = BlackjackGame()
        self.card_images = {}
        self.card_positions = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.win_details = {
            "main": 0,
            "perfect_pair": 0,
            "twenty_one_plus_three": 0,
            "royal_match": 0,
            "twenty_two_side": 0,
            "hot_3": 0,
            "lucky_queen": 0,
            "insurance": 0
        }
        self.bet_widgets = {}
        self.flipping_cards = []
        self.flip_step = 0
        self._resetting = False
        self.dealer_hidden_card_label = None
        self.insurance_offered = False
        self.player_immediate_settled = False  # 标记玩家是否已立即结算
        self.original_main_bet = 0  # 存储原始主注，用于加倍退款
        
        # 新增：边注复选框变量
        self.side_bet_check_vars = {}
        
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
    
    def _load_assets(self):
        card_size = (100, 150)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 使用Poker1扑克牌
        self.current_poker_folder = 'Poker1'
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        
        # 花色映射
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club'
        }

        self.original_images = {}
        
        # 加载背面图片
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            back_img = back_img_orig.resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception as e:
            print(f"Error loading back image: {e}")
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
        
        # 加载扑克牌图片
        for suit in SUITS:
            for rank in RANKS:
                if rank == '10':
                    continue  # 跳过10点牌
                    
                suit_name = suit_mapping.get(suit, suit)
                filename = f"{suit_name}{rank}.png"
                path = os.path.join(card_dir, filename)
                
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        self.original_images[(suit, rank)] = img
                        img_resized = img.resize(card_size)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        text_width, text_height = draw.textsize(text, font=font)
                        x = (card_size[0] - text_width) / 2
                        y = (card_size[1] - text_height) / 2
                        draw.text((x, y), text, fill="white", font=font)
                        
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading card image {path}: {e}")
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    text = "Error"
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    text_width, text_height = draw.textsize(text, font=font)
                    x = (card_size[0] - text_width) / 2
                    y = (card_size[1] - text_height) / 2
                    draw.text((x, y), text, fill="white", font=font)
                    
                    self.original_images[(suit, rank)] = img_orig
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
    
    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
            
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        
        # 更新对应的下注变量
        if bet_type == "main":
            current = int(self.main_bet_var.get())
            new_value = current + chip_value
            if new_value > 25000:
                new_value = 25000
                messagebox.showwarning("下注限制", f"主注上限为25000，已自动调整")
            self.main_bet_var.set(str(int(new_value)))
        elif bet_type == "perfect_pair":
            current = int(self.perfect_pair_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"完美对子上限为2500，已自动调整")
            self.perfect_pair_var.set(str(int(new_value)))
        elif bet_type == "twenty_one_plus_three":
            current = int(self.twenty_one_plus_three_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"21+3上限为2500，已自动调整")
            self.twenty_one_plus_three_var.set(str(int(new_value)))
        elif bet_type == "royal_match":
            current = int(self.royal_match_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"皇家同花上限为2500，已自动调整")
            self.royal_match_var.set(str(int(new_value)))
        elif bet_type == "twenty_two_side":  # 修改：爆！改为22点
            current = int(self.twenty_two_side_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"22点上限为2500，已自动调整")
            self.twenty_two_side_var.set(str(int(new_value)))
        elif bet_type == "hot_3":
            current = int(self.hot_3_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"热门3上限为2500，已自动调整")
            self.hot_3_var.set(str(int(new_value)))
        elif bet_type == "lucky_queen":
            current = int(self.lucky_queen_var.get())
            new_value = current + chip_value
            if new_value > 2500:
                new_value = 2500
                messagebox.showwarning("下注限制", f"幸运女王上限为2500，已自动调整")
            self.lucky_queen_var.set(str(int(new_value)))
    
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
        dealer_frame.place(x=50, y=20, width=600, height=250)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 提示文字
        self.info_label = tk.Label(
            table_canvas, 
            text="庄家软17点必须补牌 & 庄家22点,主注平局\n玩家允许投降输一半 & 特殊牌型,主注立即结算", 
            font=('Arial', 22), 
            bg='#35654d', 
            fg='#FFD700'
        )
        self.info_label.update_idletasks()
        label_width = self.info_label.winfo_width()
        table_canvas.update_idletasks()
        canvas_width = table_canvas.winfo_width()
        center_x = (canvas_width - label_width) // 2
        self.info_label.place(x=center_x + 355, y=280, anchor='n')
        
        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=365, width=600, height=250)
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
            text="下注阶段",
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
        
        # 单行放置5个筹码
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs = [
            ('$10', '#ffa500', 'black'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black'),
            ("$2.5K", '#ff0000', 'white'),
        ]
        
        self.chip_buttons = []
        self.chip_texts = {}
        for text, bg_color, fg_color in chip_configs:
            chip_canvas = tk.Canvas(chip_row, width=57, height=57, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 55, 55, fill=bg_color, outline='black')
            text_id = chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        
        # 默认选中$10筹码
        self.select_chip("$10")

        # 每注限制
        minmax_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        minmax_frame.pack(fill=tk.X, pady=5)
        
        # 标题行
        header_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        header_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        
        tk.Label(header_frame, text="主注最低", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="主注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="边注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=7).pack(side=tk.LEFT, expand=True)
        
        # 数值行
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$25,000", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=7).pack(side=tk.LEFT, expand=True)
        
        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10)
        
        # 第一行：完美对子 + 21+3 + 复选框
        first_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        first_row_frame.pack(fill=tk.X, padx=10, pady=3)

        # 完美对子
        perfect_pair_label = tk.Label(first_row_frame, text="完美对子:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        perfect_pair_label.pack(side=tk.LEFT, padx=1)

        self.perfect_pair_var = tk.StringVar(value="0")
        self.perfect_pair_display = tk.Label(first_row_frame, textvariable=self.perfect_pair_var, font=('Arial', 14), 
                                            bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.perfect_pair_display.pack(side=tk.LEFT, padx=5)
        self.perfect_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("perfect_pair"))
        self.perfect_pair_display.bind("<Button-3>", lambda e: self.clear_bet("perfect_pair"))  # 右键清零
        self.bet_widgets["perfect_pair"] = self.perfect_pair_display

        # 完美对子复选框
        self.side_bet_check_vars["perfect_pair"] = tk.BooleanVar(value=True)
        perfect_pair_check = tk.Checkbutton(first_row_frame, variable=self.side_bet_check_vars["perfect_pair"], 
                                          bg='#2a4a3c', activebackground='#2a4a3c')
        perfect_pair_check.pack(side=tk.LEFT, padx=2)

        # 添加间距
        tk.Label(first_row_frame, text=" ", bg='#2a4a3c').pack(side=tk.LEFT, padx=11)

        # 21+3
        twenty_one_plus_three_label = tk.Label(first_row_frame, text="21+3:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        twenty_one_plus_three_label.pack(side=tk.LEFT)

        self.twenty_one_plus_three_var = tk.StringVar(value="0")
        self.twenty_one_plus_three_display = tk.Label(first_row_frame, textvariable=self.twenty_one_plus_three_var, font=('Arial', 14), 
                                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.twenty_one_plus_three_display.pack(side=tk.LEFT, padx=5)
        self.twenty_one_plus_three_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("twenty_one_plus_three"))
        self.twenty_one_plus_three_display.bind("<Button-3>", lambda e: self.clear_bet("twenty_one_plus_three"))  # 右键清零
        self.bet_widgets["twenty_one_plus_three"] = self.twenty_one_plus_three_display

        # 21+3复选框
        self.side_bet_check_vars["twenty_one_plus_three"] = tk.BooleanVar(value=True)
        twenty_one_plus_three_check = tk.Checkbutton(first_row_frame, variable=self.side_bet_check_vars["twenty_one_plus_three"], 
                                                   bg='#2a4a3c', activebackground='#2a4a3c')
        twenty_one_plus_three_check.pack(side=tk.LEFT, padx=2)

        # 第二行：皇家同花 + 22点 + 复选框
        second_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        second_row_frame.pack(fill=tk.X, padx=10, pady=3)

        # 皇家同花
        royal_match_label = tk.Label(second_row_frame, text="皇家同花:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        royal_match_label.pack(side=tk.LEFT)

        self.royal_match_var = tk.StringVar(value="0")
        self.royal_match_display = tk.Label(second_row_frame, textvariable=self.royal_match_var, font=('Arial', 14), 
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.royal_match_display.pack(side=tk.LEFT, padx=5)
        self.royal_match_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("royal_match"))
        self.royal_match_display.bind("<Button-3>", lambda e: self.clear_bet("royal_match"))  # 右键清零
        self.bet_widgets["royal_match"] = self.royal_match_display

        # 皇家同花复选框
        self.side_bet_check_vars["royal_match"] = tk.BooleanVar(value=True)
        royal_match_check = tk.Checkbutton(second_row_frame, variable=self.side_bet_check_vars["royal_match"], 
                                         bg='#2a4a3c', activebackground='#2a4a3c')
        royal_match_check.pack(side=tk.LEFT, padx=2)

        # 添加间距
        tk.Label(second_row_frame, text=" ", bg='#2a4a3c').pack(side=tk.LEFT, padx=11)

        # 22点（原爆！）
        twenty_two_side_label = tk.Label(second_row_frame, text="22点:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        twenty_two_side_label.pack(side=tk.LEFT, padx=1)

        self.twenty_two_side_var = tk.StringVar(value="0")
        self.twenty_two_side_display = tk.Label(second_row_frame, textvariable=self.twenty_two_side_var, font=('Arial', 14), 
                                bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.twenty_two_side_display.pack(side=tk.LEFT, padx=5)
        self.twenty_two_side_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("twenty_two_side"))
        self.twenty_two_side_display.bind("<Button-3>", lambda e: self.clear_bet("twenty_two_side"))  # 右键清零
        self.bet_widgets["twenty_two_side"] = self.twenty_two_side_display

        # 22点复选框
        self.side_bet_check_vars["twenty_two_side"] = tk.BooleanVar(value=True)
        twenty_two_side_check = tk.Checkbutton(second_row_frame, variable=self.side_bet_check_vars["twenty_two_side"], 
                                  bg='#2a4a3c', activebackground='#2a4a3c')
        twenty_two_side_check.pack(side=tk.LEFT, padx=2)

        # 第三行：热门3 + 幸运女王 + 复选框
        third_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        third_row_frame.pack(fill=tk.X, padx=10, pady=3)

        # 幸运女王
        lucky_queen_label = tk.Label(third_row_frame, text="幸运女王:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        lucky_queen_label.pack(side=tk.LEFT)

        self.lucky_queen_var = tk.StringVar(value="0")
        self.lucky_queen_display = tk.Label(third_row_frame, textvariable=self.lucky_queen_var, font=('Arial', 14), 
                                        bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.lucky_queen_display.pack(side=tk.LEFT, padx=5)
        self.lucky_queen_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("lucky_queen"))
        self.lucky_queen_display.bind("<Button-3>", lambda e: self.clear_bet("lucky_queen"))
        self.bet_widgets["lucky_queen"] = self.lucky_queen_display

        # 幸运女王复选框
        self.side_bet_check_vars["lucky_queen"] = tk.BooleanVar(value=True)
        lucky_queen_check = tk.Checkbutton(third_row_frame, variable=self.side_bet_check_vars["lucky_queen"], 
                                         bg='#2a4a3c', activebackground='#2a4a3c')
        lucky_queen_check.pack(side=tk.LEFT, padx=2)

        # 添加间距
        tk.Label(third_row_frame, text=" ", bg='#2a4a3c').pack(side=tk.LEFT, padx=8)

        # 热门3
        hot_3_label = tk.Label(third_row_frame, text="热门3:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        hot_3_label.pack(side=tk.LEFT)

        self.hot_3_var = tk.StringVar(value="0")
        self.hot_3_display = tk.Label(third_row_frame, textvariable=self.hot_3_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.hot_3_display.pack(side=tk.LEFT, padx=5)
        self.hot_3_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("hot_3"))
        self.hot_3_display.bind("<Button-3>", lambda e: self.clear_bet("hot_3"))
        self.bet_widgets["hot_3"] = self.hot_3_display

        # 热门3复选框
        self.side_bet_check_vars["hot_3"] = tk.BooleanVar(value=True)
        hot_3_check = tk.Checkbutton(third_row_frame, variable=self.side_bet_check_vars["hot_3"], 
                                   bg='#2a4a3c', activebackground='#2a4a3c')
        hot_3_check.pack(side=tk.LEFT, padx=2)
        
        # 第四行：主注 + 边注全下/保险
        fourth_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        fourth_row_frame.pack(fill=tk.X, padx=10, pady=3)

        # 主注
        main_bet_label = tk.Label(fourth_row_frame, text="主注:", font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='white')
        main_bet_label.pack(side=tk.LEFT, padx=2)

        self.main_bet_var = tk.StringVar(value="0")
        self.main_bet_display = tk.Label(fourth_row_frame, textvariable=self.main_bet_var, font=('Arial', 18, 'bold'), 
                                    bg='white', fg='black', width=8, relief=tk.SUNKEN, padx=5)
        self.main_bet_display.pack(side=tk.LEFT, padx=2)
        self.main_bet_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("main"))
        self.main_bet_display.bind("<Button-3>", lambda e: self.clear_bet("main"))
        self.bet_widgets["main"] = self.main_bet_display

        # 边注全下/保险显示
        self.side_bet_all_in_frame = tk.Frame(fourth_row_frame, bg='#2a4a3c')
        self.side_bet_all_in_frame.pack(side=tk.LEFT, padx=15)
        
        # 边注全下按钮
        self.side_bet_all_in_btn = tk.Button(
            self.side_bet_all_in_frame, text="边注全下", 
            command=self.side_bet_all_in, font=('Arial', 13, 'bold'),
            bg="#00DDFF", fg='black', width=13
        )
        self.side_bet_all_in_btn.pack(side=tk.LEFT, padx=5)
        
        # 保险显示（初始隐藏）
        self.insurance_label = tk.Label(self.side_bet_all_in_frame, text="保险:", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.insurance_var = tk.StringVar(value="0")
        self.insurance_display = tk.Label(self.side_bet_all_in_frame, textvariable=self.insurance_var, font=('Arial', 18), 
                                     bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=3)
        
        # 初始隐藏保险显示，显示边注全下按钮
        self.side_bet_all_in_btn.pack(side=tk.LEFT, padx=5)
        self.insurance_label.pack_forget()
        self.insurance_display.pack_forget()
        
        # 游戏操作按钮框架
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
        self.reset_bets_button.config(state=tk.NORMAL)

        # 开始游戏按钮
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        self.start_button.config(state=tk.NORMAL)
        
        # 状态信息
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)
        
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
        
        # 添加游戏规则按钮
        rules_btn = tk.Button(
            bet_info_frame, text="ℹ️",
            command=self.show_game_instructions,   # 左键（默认 command）
            font=('Arial', 8), bg='#4B8BBE', fg='white', width=2, height=1
        )
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)

        # 右键绑定显示剩余牌堆（注意：show_remaining_cards 接受 event=None）
        rules_btn.bind("<Button-3>", self.show_remaining_cards)
    
    def side_bet_all_in(self):
        """边注全下功能：将当前筹码金额加到所有打勾的边注格子中"""
        if not self.selected_chip:
            messagebox.showinfo("提示", "请先选择筹码")
            return
            
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        
        # 遍历所有边注，如果复选框被选中，则添加筹码
        for bet_type in ["perfect_pair", "twenty_one_plus_three", "royal_match", "twenty_two_side", "hot_3", "lucky_queen"]:
            if self.side_bet_check_vars[bet_type].get():
                current = int(getattr(self, f"{bet_type}_var").get())
                new_value = current + chip_value
                
                # 检查上限
                if new_value > 2500:
                    new_value = 2500
                    messagebox.showwarning("下注限制", f"{bet_type}上限为2500，已自动调整")
                
                getattr(self, f"{bet_type}_var").set(str(int(new_value)))
        
        # 视觉反馈
        for bet_type in ["perfect_pair", "twenty_one_plus_three", "royal_match", "twenty_two_side", "hot_3", "lucky_queen"]:
            if self.side_bet_check_vars[bet_type].get():
                widget = self.bet_widgets[bet_type]
                original_color = widget.cget('bg')
                widget.config(bg='#C8E6C9')  # 浅绿色
                self.after(300, lambda w=widget, c=original_color: w.config(bg=c))
    
    def show_remaining_cards(self, event=None):
        """显示剩余牌堆的统计信息"""
        # 获取剩余牌堆统计
        remaining_cards = self.game.deck.get_remaining_cards_count()
        
        # 创建新窗口
        win = tk.Toplevel(self)
        win.title("剩余牌堆统计")
        win.geometry("600x400")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        
        # 主框架
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题
        title_label = tk.Label(
            main_frame, 
            text=f"剩余{len(self.game.deck.cards)}张牌",
            font=('Arial', 16, 'bold'),
            bg='#F0F0F0',
            fg='#333333'
        )
        title_label.pack(pady=(0, 10))
        
        # 创建表格框架
        table_frame = tk.Frame(main_frame, bg='#F0F0F0')
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # 表头 - 点数
        header_frame = tk.Frame(table_frame, bg='#F0F0F0')
        header_frame.pack(fill=tk.X)
        
        # 空单元格（用于花色列）
        tk.Label(header_frame, text="", width=6, bg='#F0F0F0').pack(side=tk.LEFT)
        
        # 点数标题
        for rank in RANKS:
            if rank == '10':
                continue  # 跳过10点牌
            display_rank = 'X' if rank == '10' else rank
            label = tk.Label(
                header_frame, 
                text=display_rank, 
                width=4, 
                font=('Arial', 10, 'bold'),
                bg='#F0F0F0',
                relief=tk.RAISED,
                bd=1
            )
            label.pack(side=tk.LEFT, padx=1)
        
        # 总计列
        total_label = tk.Label(
            header_frame, 
            text="总计", 
            width=4, 
                font=('Arial', 10, 'bold'),
                bg='#F0F0F0',
                relief=tk.RAISED,
                bd=1
            )
        total_label.pack(side=tk.LEFT, padx=1)
        
        # 花色行和数据
        for suit in SUITS:
            row_frame = tk.Frame(table_frame, bg='#F0F0F0')
            row_frame.pack(fill=tk.X)
            
            # 花色标签
            suit_label = tk.Label(
                row_frame, 
                text=suit, 
                width=4, 
                font=('Arial', 12, 'bold'),
                bg='#F0F0F0',
                relief=tk.RAISED,
                bd=1
            )
            suit_label.pack(side=tk.LEFT, padx=1)
            
            suit_total = 0
            
            # 每种点数的数量
            for rank in RANKS:
                if rank == '10':
                    continue  # 跳过10点牌
                count = remaining_cards[suit][rank]
                suit_total += count
                
                # 根据数量设置背景色
                if count == 0:
                    bg_color = '#FFCCCC'  # 红色，表示没有牌了
                elif count < 4:
                    bg_color = '#FFFFCC'  # 黄色，表示牌较少
                else:
                    bg_color = '#CCFFCC'  # 绿色，表示牌充足
                
                count_label = tk.Label(
                    row_frame, 
                    text=str(count), 
                    width=4,
                    font=('Arial', 10),
                    bg=bg_color,
                    relief=tk.SUNKEN,
                    bd=1
                )
                count_label.pack(side=tk.LEFT, padx=1)
            
            # 花色总计
            total_label = tk.Label(
                row_frame, 
                text=str(suit_total), 
                width=4,
                font=('Arial', 10, 'bold'),
                bg='#DDDDDD',
                relief=tk.RAISED,
                bd=1
            )
            total_label.pack(side=tk.LEFT, padx=1)
        
        # 分隔线
        separator = tk.Frame(table_frame, height=2, bg='#333333')
        separator.pack(fill=tk.X, pady=5)
        
        # 总计行
        total_row_frame = tk.Frame(table_frame, bg='#F0F0F0')
        total_row_frame.pack(fill=tk.X, padx=8)
        
        # 总计标签
        tk.Label(
            total_row_frame, 
            text="总计", 
            width=4, 
            font=('Arial', 10, 'bold'),
            bg='#F0F0F0',
            relief=tk.RAISED,
            bd=1
        ).pack(side=tk.LEFT, padx=1)
        
        # 每种点数的总计
        rank_totals = {}
        for rank in RANKS:
            if rank == '10':
                continue  # 跳过10点牌
            rank_totals[rank] = 0
            for suit in SUITS:
                rank_totals[rank] += remaining_cards[suit][rank]
        
        grand_total = 0
        for rank in RANKS:
            if rank == '10':
                continue  # 跳过10点牌
            total = rank_totals[rank]
            grand_total += total
            
            # 根据总数设置背景色
            if total == 0:
                bg_color = '#FFCCCC'
            elif total < 16:
                bg_color = '#FFFFCC'
            else:
                bg_color = '#CCFFCC'
                
            total_label = tk.Label(
                total_row_frame, 
                text=str(total), 
                width=4,
                font=('Arial', 10, 'bold'),
                bg=bg_color,
                relief=tk.RAISED,
                bd=1
            )
            total_label.pack(side=tk.LEFT, padx=1)
        
        # 总牌数
        grand_total_label = tk.Label(
            total_row_frame, 
            text=str(grand_total), 
            width=4,
            font=('Arial', 10, 'bold'),
            bg='#CCCCFF',
            relief=tk.RAISED,
            bd=1
        )
        grand_total_label.pack(side=tk.LEFT, padx=1)
        
        # 关闭按钮
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)
    
    def clear_bet(self, bet_type):
        """将指定类型的赌注归零"""
        if self.game.stage != "betting":
            return  # 只有在投注阶段才能清零
            
        if bet_type == "main":
            self.main_bet_var.set("0")
        elif bet_type == "perfect_pair":
            self.perfect_pair_var.set("0")
        elif bet_type == "twenty_one_plus_three":
            self.twenty_one_plus_three_var.set("0")
        elif bet_type == "royal_match":
            self.royal_match_var.set("0")
        elif bet_type == "twenty_two_side":  # 修改：爆！改为22点
            self.twenty_two_side_var.set("0")
        elif bet_type == "hot_3":
            self.hot_3_var.set("0")
        elif bet_type == "lucky_queen":
            self.lucky_queen_var.set("0")
        
        # 视觉反馈：短暂变为红色然后恢复
        widget = self.bet_widgets[bet_type]
        original_color = widget.cget('bg')
        widget.config(bg='#FFCDD2')
        self.after(300, lambda: widget.config(bg=original_color))

    def show_game_instructions(self):
        """显示游戏规则说明 - 以表格形式展示边注和立即结算规则"""
        win = tk.Toplevel(self)
        win.title("西班牙21点游戏规则")
        win.geometry("900x500")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        
        # 计算居中位置
        parent_x = self.winfo_x()
        parent_y = self.winfo_y()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()
        
        win_width = 900
        win_height = 500
        x = parent_x + (parent_width - win_width) // 2
        y = parent_y + (parent_height - win_height) // 2
        win.geometry(f"{win_width}x{win_height}+{x}+{y}")
        
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
        scrollable_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor='nw')
        
        # 内部 helper：统一创建三列表格，"条件" 列加宽，"赔率" 列减窄
        def _create_rules_table(parent, headers, data, header_bg, row_color_even, row_color_odd):
            """
            parent: 父容器
            headers: 列标题列表（长度必须为3）
            data: 行数据列表，每项为三元组
            header_bg: 表头背景色
            row_color_even/odd: 交替行背景色（even: r%2==0）
            返回创建的 table frame（以备需要进一步操作）
            """
            table = tk.Frame(parent, bg='#F0F0F0')
            table.pack(fill=tk.X)
            
            # 字符宽度近似值（label width 参数，字符数单位）
            header_widths = [18, 26, 14]  # 类型, 条件（加宽）, 赔率（减窄）
            # 对应像素下限（minsize），可保证在窗口拉伸/字体差异下有较稳定表现
            minsizes = [140, 340, 100]  # 以像素为单位：第2列更宽，第3列更窄
            
            # 表头
            for col, header in enumerate(headers):
                tk.Label(
                    table,
                    text=header,
                    font=('微软雅黑', 14, 'bold'),
                    bg=header_bg,
                    fg='white',
                    padx=15, pady=10,
                    anchor='w',
                    width=header_widths[col]
                ).grid(row=0, column=col, sticky='ew', padx=1, pady=1)
            
            # 表格内容（交替行色）
            for r, row_data in enumerate(data, start=1):
                bg = row_color_even if r % 2 == 0 else row_color_odd
                for c, txt in enumerate(row_data):
                    tk.Label(
                        table,
                        text=txt,
                        font=('微软雅黑', 14),
                        bg=bg,
                        padx=15, pady=8,
                        anchor='w',
                        width=header_widths[c]
                    ).grid(row=r, column=c, sticky='ew', padx=1, pady=1)
            
            # 列宽分配：中间列权重大（占比更高），并设置 minsize
            table.columnconfigure(0, weight=1, minsize=minsizes[0])
            table.columnconfigure(1, weight=2, minsize=minsizes[1])
            table.columnconfigure(2, weight=1, minsize=minsizes[2])
            
            return table
        
        # ===== 第一部分：游戏基本规则 =====
        basic_rules_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        # 左侧距离窗口最左边 15px，右侧不额外留白
        basic_rules_frame.pack(fill=tk.X, padx=(0, 0), pady=10)
        
        tk.Label(
            basic_rules_frame,
            text="西班牙21点游戏基本规则",
            font=('微软雅黑', 20, 'bold'),
            bg='#F0F0F0',
            fg='#2E86AB'
        ).pack(anchor='w', pady=(0, 10))
        
        basic_rules_text = (
            "1. 游戏目标: 使手中牌的点数总和尽可能接近21点，但不能超过21点。\n"
            "2. 牌值计算:\n"
            "- 2-9: 牌面值\n"
            "- J, Q, K: 10点\n"
            "- A: 1点或11点（自动选择最有利的值）\n"
            "3. 游戏流程:\n"
            "a. 下注阶段: 玩家下注主注，可选择下注边注\n"
            "b. 发牌: 玩家第1张，庄家第1张，玩家第2张\n"
            "c. 保险: 如果庄家第一张是A，玩家可选择购买保险\n"
            "d. 玩家回合: 可选择要牌、停牌、加倍、投降\n"
            "e. 庄家回合: 庄家必须补牌直到手牌点数达到17点或更高，Soft 17必须补牌\n"
            "4. 特殊规则:\n"
            "- 使用8副牌，移除所有10点牌\n"
            "- 切牌位置: 剩余45张牌时重新洗牌\n"
            "- 庄家Soft 17必须补牌\n"
            "- 庄家22点且玩家未爆牌（20点以内）时，主注平局\n"
        )
        
        basic_rules_label = tk.Label(
            basic_rules_frame,
            text=basic_rules_text,
            font=('微软雅黑', 14),
            bg='#F0F0F0',
            fg='#333333',
            justify=tk.LEFT,
            wraplength=850
        )
        # 取消 label 的额外横向内边距，使其与 frame 左侧的 15px 间距对齐
        basic_rules_label.pack(fill=tk.X, padx=0, pady=5, anchor='w')
        
        # ===== 第二部分：立即结算规则表格 =====
        immediate_settlement_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        immediate_settlement_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            immediate_settlement_frame,
            text="立即结算规则",
            font=('微软雅黑', 20, 'bold'),
            bg='#F0F0F0',
            fg='#A23B72'
        ).pack(anchor='w', pady=(0, 10))
        
        immediate_headers = ["类型", "条件", "赔率"]
        immediate_data = [
            ("Blackjack", "玩家前2张牌达到21点", "3:2"),
            ("5龙21点", "玩家5张牌且总点数为21点", "2:1"),
            ("任何21点", "玩家任何21点（非2张牌）", "1:1"),
            ("5张牌", "玩家5张牌且未爆牌", "1:1")
        ]
        
        _create_rules_table(
            parent=immediate_settlement_frame,
            headers=immediate_headers,
            data=immediate_data,
            header_bg='#4B8BBE',
            row_color_even='#E8F4FD',
            row_color_odd='#FFFFFF'
        )
        
        # ===== 第三部分：完美对子边注规则表格 =====
        perfect_pair_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        perfect_pair_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            perfect_pair_frame,
            text="完美对子边注规则",
            font=('微软雅黑', 20, 'bold'),
            bg='#F0F0F0',
            fg='#2E86AB'
        ).pack(anchor='w', pady=(0, 10))
        
        pair_headers = ["类型", "条件", "赔率"]
        pair_data = [
            ("完美对子", "相同花色和点数", "21:1"),
            ("同色对子", "相同颜色和点数", "11:1"),
            ("混合对子", "相同点数", "6:1")
        ]
        
        _create_rules_table(
            parent=perfect_pair_frame,
            headers=pair_headers,
            data=pair_data,
            header_bg='#A23B72',
            row_color_even='#F5E6F0',
            row_color_odd='#FFFFFF'
        )
        
        # ===== 第四部分：21+3边注规则表格 =====
        twenty_one_plus_three_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        twenty_one_plus_three_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            twenty_one_plus_three_frame,
            text="21+3边注规则",
            font=('微软雅黑', 20, 'bold'),
            bg='#F0F0F0',
            fg='#F18F01'
        ).pack(anchor='w', pady=(0, 10))
        
        three_headers = ["类型", "条件", "赔率"]
        three_data = [
            ("同花三条", "三张牌同花色且点数相同", "90:1"),
            ("同花顺", "三张牌同花色且点数连续", "35:1"),
            ("三条", "三张牌点数相同", "29:1"),
            ("顺子", "三张牌点数连续", "9:1"),
            ("同花", "三张牌同花色", "9:2")
        ]
        
        _create_rules_table(
            parent=twenty_one_plus_three_frame,
            headers=three_headers,
            data=three_data,
            header_bg='#F18F01',
            row_color_even='#FDF0E0',
            row_color_odd='#FFFFFF'
        )
        
        # ===== 第五部分：皇家同花边注规则表格 =====
        royal_match_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        royal_match_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            royal_match_frame,
            text="皇家同花边注规则",
            font=('微软雅黑', 20, 'bold'),
            bg='#F0F0F0',
            fg='#2E86AB'
        ).pack(anchor='w', pady=(0, 10))
        
        royal_headers = ["类型", "条件", "赔率"]
        royal_data = [
            ("皇家同花", "同花Q和K", "30:1"),
            ("同花", "同花但不是Q和K", "5:2")
        ]
        
        _create_rules_table(
            parent=royal_match_frame,
            headers=royal_headers,
            data=royal_data,
            header_bg='#2E86AB',
            row_color_even='#E8F4FD',
            row_color_odd='#FFFFFF'
        )
        
        # ===== 第六部分：22点边注规则表格 =====
        twenty_two_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        twenty_two_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            twenty_two_frame,
            text="22点边注规则",
            font=('微软雅黑', 20, 'bold'),
            bg='#F0F0F0',
            fg='#A23B72'
        ).pack(anchor='w', pady=(0, 10))
        
        twenty_two_headers = ["类型", "条件", "赔率"]
        twenty_two_data = [
            ("同花", "庄家最终点数为22点且所有牌花色相同", "50:1"),
            ("同色", "庄家最终点数为22点且所有牌颜色相同", "20:1"),
            ("混色", "庄家最终点数为22点但花色不一致", "8:1")
        ]
        
        _create_rules_table(
            parent=twenty_two_frame,
            headers=twenty_two_headers,
            data=twenty_two_data,
            header_bg='#A23B72',
            row_color_even='#F5E6F0',
            row_color_odd='#FFFFFF'
        )
        
        # ===== 第七部分：热门3边注规则表格 =====
        hot_3_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        hot_3_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            hot_3_frame,
            text="热门3边注规则",
            font=('微软雅黑', 20, 'bold'),
            bg='#F0F0F0',
            fg='#F18F01'
        ).pack(anchor='w', pady=(0, 10))
        
        hot_3_headers = ["类型", "条件", "赔率"]
        hot_3_data = [
            ("三张7同花", "三张牌都是7点且同花色", "350:1"),
            ("三张7混花", "三张牌都是7点但花色不同", "75:1"),
            ("21点同花", "三张牌总点数21点且同花色", "19:1"),
            ("21点混花", "三张牌总点数21点但花色不同", "4:1"),
            ("20点", "三张牌总点数20点", "3:2"),
            ("19点", "三张牌总点数19点", "1:1")
        ]
        
        _create_rules_table(
            parent=hot_3_frame,
            headers=hot_3_headers,
            data=hot_3_data,
            header_bg='#F18F01',
            row_color_even='#FDF0E0',
            row_color_odd='#FFFFFF'
        )
        
        # ===== 第八部分：幸运女王边注规则表格 =====
        lucky_queen_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        lucky_queen_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            lucky_queen_frame,
            text="幸运女王边注规则",
            font=('微软雅黑', 20, 'bold'),
            bg='#F0F0F0',
            fg='#2E86AB'
        ).pack(anchor='w', pady=(0, 10))
        
        lucky_headers = ["类型", "条件", "赔率"]
        lucky_data = [
            ("女王同花+庄家BJ", "两张同花Q且庄家Blackjack", "600:1"),
            ("女王同花", "两张同花Q", "60:1"),
            ("同点数同花", "两张同点数同花牌", "20:1"),
            ("同花", "两张总点数20点同花牌(非Q)", "8:1"),
            ("混花", "两张总点数20点但花色不同", "7:2")
        ]
        
        _create_rules_table(
            parent=lucky_queen_frame,
            headers=lucky_headers,
            data=lucky_data,
            header_bg='#2E86AB',
            row_color_even='#E8F4FD',
            row_color_odd='#FFFFFF'
        )
        
        # ===== 第九部分：保险规则说明 =====
        insurance_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        # 同样将 insurance 部分左侧与窗口左边保持 15px 空隙
        insurance_frame.pack(fill=tk.X, padx=(0, 0), pady=10)
        
        tk.Label(
            insurance_frame,
            text="保险规则",
            font=('微软雅黑', 20, 'bold'),
            bg='#F0F0F0',
            fg='#A23B72'
        ).pack(anchor='w', pady=(0, 10))
        
        insurance_text = (
            "1. 保险条件: 当庄家第一张牌是A时，玩家可选择购买保险\n"
            "2. 保险金额: 主注的50%（下注10元可购买5元保险）\n"
            "3. 保险赔付: 2:1（下注5元保险，如果庄家Blackjack则赢10元，共返回15元）\n"
            "4. 保险检查: 庄家第二张牌是J/Q/K时保险获胜\n"
            "5. 特殊情况:\n"
            "- 玩家Blackjack时跳过保险阶段，直接结算\n"
            "- 玩家投降后如果有保险，庄家仍需行动检查保险\n"
        )
        
        insurance_label = tk.Label(
            insurance_frame,
            text=insurance_text,
            font=('微软雅黑', 14),
            bg='#F0F0F0',
            fg='#333333',
            justify=tk.LEFT,
            wraplength=850
        )
        insurance_label.pack(fill=tk.X, padx=0, pady=5, anchor='w')
        
        # ===== 滚动区域更新 =====
        scrollable_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # ===== 关闭按钮 =====
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)
        
        # ===== 绑定鼠标滚轮滚动 =====
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        win.bind("<MouseWheel>", _on_mousewheel)
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
    
    def select_chip(self, chip_text):
        """选择筹码，并更新筹码的高亮状态"""
        self.selected_chip = chip_text
        # 重置所有筹码的边框
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item_id)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break

        # 给选中的筹码加金色高亮
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            for item_id in chip.find_all():
                t = chip.type(item_id)
                if t == 'text':
                    text_id = item_id
                elif t == 'oval':
                    oval_id = item_id
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                x1, y1, x2, y2 = chip.coords(oval_id)
                chip.create_oval(x1, y1, x2, y2, outline='gold', width=3, tags="highlight")
                break
    
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
            
    def update_hand_labels(self):
        """更新玩家和庄家的手牌点数显示"""
        # 计算玩家当前点数
        if self.game.player_hand:
            player_value = self.game.get_hand_value(self.game.player_hand)
            
            if self.player_immediate_settled:
                if self.game.player_immediate_win:
                    win_type = self.game.player_immediate_win["type"]
                    if win_type == "blackjack":
                        player_text = "玩家 - BJ"
                    elif win_type == "5_card_21":
                        player_text = "玩家 - 5龙21点, 已结算"
                    elif win_type == "any_21":
                        player_text = "玩家 - 21点, 已结算"
                    elif win_type == "5_card":
                        player_text = "玩家 - 5张牌, 已结算"
                    else:
                        player_text = f"玩家 - {player_value}点"
                else:
                    player_text = f"玩家 - {player_value}点"
            elif player_value > 21:
                player_text = f"玩家 - {player_value}点，爆牌"
            else:
                player_text = f"玩家 - {player_value}点"
            self.player_label.config(text=player_text)
        
        # 计算庄家当前点数
        if self.game.dealer_hand:
            dealer_value = self.game.get_hand_value(self.game.dealer_hand)
            dealer_text = "庄家"
            if self.game.stage == "showdown" or self.game.player_done:
                if self.game.check_blackjack(self.game.dealer_hand) and len(self.game.dealer_hand) == 2:
                    dealer_text = "庄家 - BJ"
                elif dealer_value == 22:
                    dealer_text = f"庄家 - 22点, 主注退还"
                elif dealer_value > 21:
                    dealer_text = f"庄家 - {dealer_value}点，爆牌"
                else:
                    dealer_text = f"庄家 - {dealer_value}点"
            else:
                # 只显示第一张牌的值
                if self.game.dealer_hand:
                    first_card_value = self.game.dealer_hand[0].get_value()
                    dealer_text = f"庄家 - {first_card_value}点"
            self.dealer_label.config(text=dealer_text)
    
    def disable_action_buttons(self):
        if hasattr(self, 'hit_button'):
            self.hit_button.config(state=tk.DISABLED)
        if hasattr(self, 'stand_button'):
            self.stand_button.config(state=tk.DISABLED)
        if hasattr(self, 'surrender_button'):
            self.surrender_button.config(state=tk.DISABLED)
        if hasattr(self, 'double_button'):
            self.double_button.config(state=tk.DISABLED)
        
    def enable_action_buttons(self):
        """启用所有操作按钮"""
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            if isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)
    
    def _create_scaled_image(self, card, width, height, use_back=False):
        """创建缩放后的图像"""
        if use_back:
            img = self.original_images["back"].copy()
        else:
            img = self.original_images[(card.suit, card.rank)].copy()
        
        img = img.resize((width, height), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    
    def flip_card_animation(self, card_label, card, callback=None):
        """翻牌动画（已修正为使用 100x150 标准尺寸）"""
        def flip_step(step=0):
            if card_label is None:
                return

            steps = 12
            if step > steps:
                # 翻牌完成，显示原始牌面（完整尺寸）
                card_label.config(image=self.card_images.get((card.suit, card.rank), self.back_image))
                # 确保引用防被 GC（通常 self.card_images 已持有）
                if callback:
                    callback()
                return

            # 翻牌动画逻辑（左右缩放）
            half = steps // 2
            if step <= half:
                ratio = 1 - (step / float(half))
                use_back = True
            else:
                ratio = (step - half) / float(half)
                use_back = False

            # 使用标准全尺寸
            full_w, full_h = 100, 150
            w = max(1, int(full_w * ratio))

            # 生成缩放后的图像（宽动态，高保持 full_h，避免变矮）
            img = self._create_scaled_image(card, w, full_h, use_back=use_back)
            if not hasattr(self, '_temp_flip_images'):
                self._temp_flip_images = {}
            # 保持对临时图像的引用，防止被 GC
            self._temp_flip_images[id(card_label)] = img

            card_label.config(image=img)
            # 下一帧
            self.after(20, lambda: flip_step(step + 1))

        flip_step()
    
    def add_card_to_frame(self, frame, card, show_front=True, position=None):
        """添加一张牌到指定框架（统一牌尺寸为 100x150）。
        当为庄家区域（self.dealer_cards_frame）且牌数超过5张时，
        用0.5秒把除第1张以外的牌向左移动，使相邻间距变为 -60（即 x_spacing = 40）。
        返回创建的 card_label（并把它加入 self.active_card_labels）。
        """
        # 图像选择
        if show_front:
            card_img = self.card_images.get((card.suit, card.rank), self.back_image)
        else:
            card_img = self.back_image

        card_label = tk.Label(frame, image=card_img, bg='#2a4a3c')

        full_w, full_h = 100, 150
        # 默认正向间距（当不需要挤压时）
        normal_spacing = full_w + 10  # =110

        if position is None:
            # 默认添加到末尾（pack 保持老行为）
            card_label.pack(side=tk.LEFT, padx=5)
        else:
            # 使用 place 放置，宽高固定
            # 默认按未压缩间距摆放（与原实现保持一致）
            x = position * normal_spacing
            card_label.place(x=x, y=0, width=full_w, height=full_h)

        card_label.card = card
        card_label.is_face_up = show_front

        # 添加到活动卡片列表并保持对 image 的引用
        self.active_card_labels.append(card_label)

        # --- 特殊处理：如果这是庄家区域，并且牌数超过5张（即需要压缩） ---
        try:
            # 当前庄家区内所有卡片（按子控件顺序）
            labels = [w for w in frame.winfo_children() if isinstance(w, tk.Label)]
            count = len(labels)
            # 当超过5张（第6张及以后）时，启动移动动画，使相邻间距 = -70 => x_spacing = full_w - 70
            if count > 5:
                target_spacing = full_w - 70  # 100 - 70 = 30
                duration_ms = 750
                # 动画步数（保证平滑）：每步间隔约20ms
                step_time = 20
                steps = max(1, int(duration_ms / step_time))

                # 计算每个 label 的起始 x 和目标 x（第0张保持在 x=0）
                start_positions = []
                target_positions = []
                for idx, lbl in enumerate(labels):
                    # 读取当前 x（尽量先用 place_info，否则用 winfo_x）
                    pi = {}
                    try:
                        pi = lbl.place_info()
                    except Exception:
                        pi = {}
                    if 'x' in pi and pi['x'] != '':
                        try:
                            sx = int(float(pi['x']))
                        except Exception:
                            sx = lbl.winfo_x()
                    else:
                        # widget 可能是用 pack 放的，使用 winfo_x 作为当前位置
                        try:
                            sx = lbl.winfo_x()
                        except Exception:
                            sx = 0
                    start_positions.append(sx)
                    # 目标位置：第0张固定在0，其余按 index * target_spacing
                    tx = idx * target_spacing
                    target_positions.append(tx)

                # 计算每步偏移量
                deltas = [(target_positions[i] - start_positions[i]) / float(steps) for i in range(len(labels))]

                # 执行动画（只移动第1张及以后的标签；第0张保持不动）
                def do_step(step=1):
                    if self._resetting:
                        # 若正在 reset，立即跳出并把位置设为目标（防止残留动画）
                        for i, lbl in enumerate(labels):
                            try:
                                lbl.place(x=target_positions[i], y=0)
                            except Exception:
                                pass
                        return

                    for i, lbl in enumerate(labels):
                        if i == 0:
                            # 保持第一张不动（但确保放置为 x=0）
                            try:
                                lbl.place(x=0, y=0)
                            except Exception:
                                pass
                            continue
                        # 计算并设置新 x
                        new_x = start_positions[i] + deltas[i] * step
                        try:
                            lbl.place(x=int(round(new_x)), y=0)
                        except Exception:
                            # 若放置失败（例如控件还没 map），尝试使用 place_configure
                            try:
                                lbl.place_configure(x=int(round(new_x)), y=0)
                            except Exception:
                                pass

                    if step < steps:
                        self.after(step_time, lambda: do_step(step + 1))
                    else:
                        # 确保最终位置精确到目标值
                        for i, lbl in enumerate(labels):
                            try:
                                lbl.place(x=target_positions[i], y=0)
                            except Exception:
                                pass

                # 启动动画
                do_step(1)
        except Exception:
            # 任何意外不要中断主流程，仅记录/忽略
            pass

        return card_label
        
    def play_shuffle_animation(self, duration_ms=3500, callback=None):
        """播放洗牌动画，窗口居中且模态"""
        try:
            # 创建模态窗口
            win = tk.Toplevel(self)
            win.title("正在洗牌...")
            win.resizable(False, False)
            win.transient(self)
            win.grab_set()
            win.configure(bg='#2a2a2a')
            
            # 设置窗口居中
            win.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() - 520) // 2
            y = self.winfo_y() + (self.winfo_height() - 220) // 2
            win.geometry(f"520x220+{x}+{y}")
            
            # 移除关闭按钮
            win.protocol("WM_DELETE_WINDOW", lambda: None)  # 禁用关闭按钮
            
            canvas = tk.Canvas(win, width=520, height=220, bg='#2a2a2a', highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # 生成若干张小背面图
            small_w, small_h = 90, 135
            try:
                back_img_orig = self.original_images.get("back")
                if back_img_orig is None:
                    back_img = Image.new('RGBA', (small_w, small_h), (0, 0, 0, 255))
                else:
                    back_img = back_img_orig.copy().resize((small_w, small_h), Image.LANCZOS)
            except Exception:
                back_img = Image.new('RGBA', (small_w, small_h), (0, 0, 0, 255))

            # 创建卡片图像
            num_cards = 10
            center_x = 520 // 2
            center_y = 220 // 2
            spread = 200
            start_x = center_x - spread // 2
            gap = spread // max(1, num_cards - 1)

            if not hasattr(self, '_shuffle_imgs'):
                self._shuffle_imgs = []
            else:
                self._shuffle_imgs.clear()

            items = []
            for i in range(num_cards):
                scale = 0.95 + (i % 3) * 0.03
                iw = max(20, int(small_w * scale))
                ih = max(30, int(small_h * scale))
                try:
                    tmp = back_img.resize((iw, ih), Image.LANCZOS)
                except Exception:
                    tmp = back_img
                tkimg = ImageTk.PhotoImage(tmp)
                self._shuffle_imgs.append(tkimg)
                x = start_x + i * gap
                y = center_y + (i % 2) * 6
                item = canvas.create_image(x, y, image=tkimg, anchor='center')
                items.append({
                    'id': item,
                    'base_x': x,
                    'base_y': y,
                    'phase': (i * 2 * math.pi) / max(1, num_cards),
                    'amp': 10 + (i % 4) * 4,
                    'z': i
                })

            # 顶部文字
            txt = canvas.create_text(520//2, 18, text="正在洗牌，请稍候...", fill='white', font=('Arial', 14, 'bold'))

            # 动画循环
            total_steps = max(1, int(duration_ms / 40))
            step = {'i': 0}

            def anim_step():
                i = step['i']
                frac = i / float(total_steps)
                
                # 卡片动画
                for idx, it in enumerate(items):
                    pid = it['id']
                    phase = it['phase']
                    amp = it['amp']
                    dx = math.sin(phase + frac * 12.0) * amp * (0.8 + 0.4 * math.sin(frac * 2 * math.pi + idx))
                    dy = math.sin(phase * 0.7 + frac * 6.0) * (amp / 6.0)
                    new_x = it['base_x'] + dx * (1.0 - frac * 0.3)
                    new_y = it['base_y'] + dy
                    canvas.coords(pid, new_x, new_y)

                    if (i + idx) % 20 < 10:
                        canvas.tag_raise(pid)
                    else:
                        canvas.tag_lower(pid)

                step['i'] += 1
                if step['i'] <= total_steps:
                    win.after(40, anim_step)
                else:
                    def do_close():
                        try:
                            win.grab_release()
                        except Exception:
                            pass
                        try:
                            win.destroy()
                        except Exception:
                            pass
                        if callback:
                            try:
                                callback()
                            except Exception as e:
                                print(f"洗牌回调错误: {e}")

                    win.after(100, do_close)

            # 启动动画
            anim_step()

        except Exception as e:
            print(f"洗牌动画失败: {e}")
            if callback:
                try:
                    callback()
                except Exception:
                    pass
        
    def start_game(self):
        """开始一局 —— 使用长期牌靴（8 副），仅当剩余卡数 <= 45 时或首次加载时弹出洗牌动画（10秒），动画结束后重洗并继续发牌。"""
        try:
            # 重置赢利详情和上局获胜金额 - 关键修复点！
            self.win_details = {
                "main": 0,
                "perfect_pair": 0,
                "twenty_one_plus_three": 0,
                "royal_match": 0,
                "twenty_two_side": 0,
                "hot_3": 0,
                "lucky_queen": 0,
                "insurance": 0
            }
            self.last_win = 0
            
            # 读取下注数
            self.game.main_bet = int(self.main_bet_var.get())
            self.game.perfect_pair_bet = int(self.perfect_pair_var.get())
            self.game.twenty_one_plus_three_bet = int(self.twenty_one_plus_three_var.get())
            self.game.royal_match_bet = int(self.royal_match_var.get())
            self.game.twenty_two_side_bet = int(self.twenty_two_side_var.get())
            self.game.hot_3_bet = int(self.hot_3_var.get())
            self.game.lucky_queen_bet = int(self.lucky_queen_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
            return

        # 检查最低主注
        if self.game.main_bet < 10:
            messagebox.showerror("错误", "主注至少需要10块")
            return

        total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                    self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                    self.game.twenty_two_side_bet + self.game.hot_3_bet + self.game.lucky_queen_bet)  # 修改：爆！改为22点

        if self.balance < total_bet:
            messagebox.showerror("错误", "余额不足以支付所有下注！")
            return

        # 禁用所有下注区按钮
        self.disable_betting_area()
        self.last_win_label.config(text="上局获胜: $0.00")

        self.start_button.config(state=tk.DISABLED)
        self.reset_bets_button.config(state=tk.DISABLED)
        
        # 隐藏边注全下按钮，显示保险显示
        self.side_bet_all_in_btn.pack_forget()
        self.insurance_label.pack(side=tk.LEFT, padx=5)
        self.insurance_display.pack(side=tk.LEFT, padx=1)
        self.insurance_var.set("0")

        # 存储原始主注，用于加倍退款
        self.original_main_bet = self.game.main_bet

        # 扣除下注
        self.balance -= total_bet
        self.update_balance()
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        # 判断是否需要洗牌
        need_shuffle = False
        
        # 检查是否首次加载游戏（牌堆不存在或为空）
        if not hasattr(self.game, 'deck') or self.game.deck is None:
            need_shuffle = True
        else:
            # 检查剩余牌数
            remaining_cards = len(self.game.deck.cards)
            if remaining_cards <= 45:
                need_shuffle = True

        def continue_after_shuffle():
            """洗牌动画结束后继续游戏"""
            # 重新生成牌堆（洗牌）
            self.game.deck = Deck(8)
            
            # 重置游戏状态（保留下注）
            self.game.reset_game()
            self.game.main_bet = int(self.main_bet_var.get())
            self.game.perfect_pair_bet = int(self.perfect_pair_var.get())
            self.game.twenty_one_plus_three_bet = int(self.twenty_one_plus_three_var.get())
            self.game.royal_match_bet = int(self.royal_match_var.get())
            self.game.twenty_two_side_bet = int(self.twenty_two_side_var.get())  # 修改：爆！改为22点
            self.game.hot_3_bet = int(self.hot_3_var.get())
            self.game.lucky_queen_bet = int(self.lucky_queen_var.get())
            self.game.stage = "dealing"
            self.player_immediate_settled = False
            self.original_main_bet = self.game.main_bet

            # 清空UI牌容器
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()

            # 发初始牌
            try:
                self.game.deal_initial_cards()
            except Exception as e:
                print(f"发牌失败: {e}")
                messagebox.showerror("错误", "发牌失败，请重新开始游戏")
                return
            
            # 更新UI状态
            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            
            # 启动发牌序列
            self.deal_card_sequence()

        def continue_without_shuffle():
            """不需要洗牌，直接继续游戏"""
            # 重置游戏状态（保留下注）
            self.game.reset_game()
            self.game.main_bet = int(self.main_bet_var.get())
            self.game.perfect_pair_bet = int(self.perfect_pair_var.get())
            self.game.twenty_one_plus_three_bet = int(self.twenty_one_plus_three_var.get())
            self.game.royal_match_bet = int(self.royal_match_var.get())
            self.game.twenty_two_side_bet = int(self.twenty_two_side_var.get())  # 修改：爆！改为22点
            self.game.hot_3_bet = int(self.hot_3_var.get())
            self.game.lucky_queen_bet = int(self.lucky_queen_var.get())
            self.game.stage = "dealing"
            self.player_immediate_settled = False
            self.original_main_bet = self.game.main_bet

            # 清空UI牌容器
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()

            # 发初始牌
            try:
                self.game.deal_initial_cards()
            except Exception as e:
                print(f"发牌失败: {e}")
                messagebox.showerror("错误", "发牌失败，请重新开始游戏")
                return
            
            # 更新UI状态
            self.stage_label.config(text="发牌中")
            self.status_label.config(text="正在发牌...")
            
            # 启动发牌序列
            self.deal_card_sequence()

        # 流程控制
        if need_shuffle:
            self.play_shuffle_animation(duration_ms=3500, callback=continue_after_shuffle)
        else:
            # 直接继续游戏
            continue_without_shuffle()
    
    def disable_betting_area(self):
        """禁用下注区域的所有按钮"""
        # 禁用下注标签的点击事件
        for bet_type, widget in self.bet_widgets.items():
            widget.unbind("<Button-1>")
            widget.unbind("<Button-3>")
        
    def enable_betting_area(self):
        # 启用下注标签的点击事件
        for bet_type, widget in self.bet_widgets.items():
            widget.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            widget.bind("<Button-3>", lambda e, bt=bet_type: self.clear_bet(bt))
            # 恢复颜色
            widget.config(bg='white', fg='black')
        
    def deal_card_sequence(self):
        """发牌序列：玩家第1张 → 庄家第1张 → 玩家第2张"""
        # 第一步：发玩家第一张牌
        self.status_label.config(text="发玩家第一张牌")
        player_card1 = self.game.player_hand[0]
        player_card1_label = self.add_card_to_frame(self.player_cards_frame, player_card1, show_front=True, position=0)
        
        # 翻牌动画
        self.flip_card_animation(player_card1_label, player_card1, callback=self.after_player_card1)
    
    def after_player_card1(self):
        """玩家第一张牌发完后"""
        first_card_value = self.game.player_hand[0].get_value()
        player_text = f"玩家 - {first_card_value}点"
        self.player_label.config(text=player_text)
        
        # 第二步：发庄家第一张牌
        self.status_label.config(text="发庄家第一张牌")
        dealer_card1 = self.game.dealer_hand[0]
        dealer_card1_label = self.add_card_to_frame(self.dealer_cards_frame, dealer_card1, show_front=True, position=0)
        
        # 翻牌动画
        self.flip_card_animation(dealer_card1_label, dealer_card1, callback=self.after_dealer_card1)
    
    def after_dealer_card1(self):
        """庄家第一张牌发完后"""
        self.update_hand_labels()
        
        # 第三步：发玩家第二张牌
        self.status_label.config(text="发玩家第二张牌")
        player_card2 = self.game.player_hand[1]
        player_card2_label = self.add_card_to_frame(self.player_cards_frame, player_card2, show_front=True, position=1)
        
        # 翻牌动画
        self.flip_card_animation(player_card2_label, player_card2, callback=self.after_player_card2)
    
    def after_player_card2(self):
        """玩家第二张牌发完后"""
        self.update_hand_labels()
        
        # 检查玩家是否有Blackjack（2张牌21点）
        player_blackjack = self.game.check_blackjack(self.game.player_hand)
        
        # 检查庄家第一张牌是否为A
        dealer_upcard = self.game.dealer_hand[0]
        
        # 修正1: 玩家Blackjack时跳过保险阶段
        if player_blackjack:
            # 玩家有Blackjack，直接立即结算，跳过保险阶段
            self.status_label.config(text="玩家Blackjack！立即结算")
            self.check_immediate_settlement()
        elif dealer_upcard.rank == 'A':
            # 提供保险选项（不发庄家第二张牌）
            self.offer_insurance()
        else:
            # 检查玩家是否满足立即结算条件
            self.check_immediate_settlement()
    
    def offer_insurance(self):
        """提供保险选项"""
        self.game.stage = "insurance"
        self.stage_label.config(text="保险选项")
        self.status_label.config(text="庄家明牌是A，是否购买保险？")
        
        # 清除操作按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        insurance_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        insurance_frame.pack(pady=5)
        
        # 购买保险按钮
        self.insurance_btn = tk.Button(
            insurance_frame, text="购买保险",
            command=self.take_insurance,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=10
        )
        self.insurance_btn.pack(side=tk.LEFT, padx=5)
        
        # 不购买保险按钮
        self.no_insurance_btn = tk.Button(
            insurance_frame, text="不购买",
            command=self.decline_insurance,
            font=('Arial', 14), bg='#F44336', fg='white', width=10
        )
        self.no_insurance_btn.pack(side=tk.LEFT, padx=5)
    
    def take_insurance(self):
        """购买保险"""
        # 立即禁用保险按钮
        if hasattr(self, 'insurance_btn'):
            self.insurance_btn.config(state=tk.DISABLED)
        if hasattr(self, 'no_insurance_btn'):
            self.no_insurance_btn.config(state=tk.DISABLED)
        
        insurance_amount = self.game.main_bet / 2
        if self.balance >= insurance_amount:
            self.balance -= insurance_amount
            self.game.insurance_bet = insurance_amount
            self.game.insurance_taken = True
            self.update_balance()
            
            # 更新保险显示
            self.insurance_var.set(str(int(insurance_amount)))

            total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                    self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                    self.game.twenty_two_side_bet + self.game.hot_3_bet + self.game.lucky_queen_bet + self.game.insurance_bet)  # 修改：爆！改为22点

            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            self.status_label.config(text=f"已购买保险 ${self.game.insurance_bet}")
            self.after(1000, self.check_immediate_settlement)
        else:
            messagebox.showerror("错误", "余额不足以购买保险")
            self.decline_insurance()

    def decline_insurance(self):
        """不购买保险"""
        # 立即禁用保险按钮
        if hasattr(self, 'insurance_btn'):
            self.insurance_btn.config(state=tk.DISABLED)
        if hasattr(self, 'no_insurance_btn'):
            self.no_insurance_btn.config(state=tk.DISABLED)
        
        self.game.insurance_taken = False
        self.status_label.config(text="未购买保险")
        self.after(1000, self.check_immediate_settlement)
    
    def check_immediate_settlement(self):
        """检查玩家是否满足立即结算条件"""
        immediate_win = self.game.check_player_immediate_win()
        if immediate_win:
            self.game.player_immediate_win = immediate_win
            self.player_immediate_settled = True
            
            # 根据赢的类型显示不同消息
            win_type = immediate_win["type"]
            
            if win_type == "blackjack":
                message = "玩家Blackjack！主注立即以3:2胜出"
                # 立即结算主注
                self.immediate_settle_main_bet()
            elif win_type == "5_card_21":
                message = "玩家5龙21点！主注立即以2:1胜出"
                # 立即结算主注
                self.immediate_settle_main_bet()
            elif win_type == "any_21":
                message = "玩家21点！主注立即以1:1胜出"
                # 立即结算主注
                self.immediate_settle_main_bet()
            elif win_type == "5_card":
                message = "玩家5张牌！主注立即以1:1胜出"
                # 立即结算主注
                self.immediate_settle_main_bet()
            else:
                message = "玩家满足立即结算条件"
            
            self.status_label.config(text=message)
            self.update_hand_labels()
            
            # 修正2: 立即结算后检查是否需要庄家行动
            needs_dealer_action = False
            
            # 如果玩家有保险或22点边注，庄家需要行动
            if self.game.insurance_bet > 0 or self.game.twenty_two_side_bet > 0:
                needs_dealer_action = True
                # 标记庄家需要行动的原因
                if self.game.insurance_bet > 0:
                    self.game.dealer_forced_hit_for_insurance = True
                if self.game.twenty_two_side_bet > 0:
                    self.game.dealer_needs_to_play = True
            
            if needs_dealer_action:
                # 延迟后进入庄家回合
                self.after(2000, self.dealer_turn)
            else:
                # 不需要庄家行动，直接结算
                self.after(2000, self.show_showdown)
        else:
            # 检查玩家是否爆牌
            player_value = self.game.get_hand_value(self.game.player_hand)
            if player_value > 21:
                # 玩家爆牌
                self.game.player_done = True
                self.status_label.config(text="玩家爆牌！")
                
                # 判断庄家是否需要行动
                needs_dealer_action = False
                
                # 如果玩家有保险或22点边注，庄家需要行动
                if self.game.insurance_bet > 0 or self.game.twenty_two_side_bet > 0:
                    needs_dealer_action = True
                    # 标记庄家需要行动的原因
                    if self.game.insurance_bet > 0:
                        self.game.dealer_forced_hit_for_insurance = True
                    if self.game.twenty_two_side_bet > 0:
                        self.game.dealer_needs_to_play = True
                
                if needs_dealer_action:
                    # 延迟后进入庄家回合
                    self.after(1000, self.dealer_turn)
                else:
                    # 不需要庄家行动，直接结算
                    self.after(1000, self.show_showdown)
            else:
                # 进入玩家回合
                self.game.stage = "player_turn"
                self.stage_label.config(text="玩家回合")
                self.show_player_actions()
    
    def immediate_settle_main_bet(self):
        """立即结算主注"""
        if not self.game.player_immediate_win:
            return
            
        payout = self.game.player_immediate_win["payout"]
        win_amount = self.game.main_bet * (payout - 1)  # 净赢额
        
        # 退还主注本金 + 赢得的金额
        self.balance += self.game.main_bet + win_amount
        self.update_balance()
        
        # 更新主注显示
        self.win_details["main"] = self.game.main_bet + win_amount
        self.main_bet_var.set(str(int(self.game.main_bet + win_amount)))
        self.main_bet_display.config(bg='gold')
        
        # 标记主注已结算
        self.game.main_bet = 0
    
    def show_player_actions(self):
        """显示玩家操作按钮"""
        # 清除操作按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        action_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        action_frame.pack(pady=5)
        
        # 要牌按钮
        self.hit_button = tk.Button(
            action_frame, text="要牌",
            command=self.hit_action,
            font=('Arial', 14), bg='#4CAF50', fg='white', width=7
        )
        self.hit_button.pack(side=tk.LEFT, padx=5)
        
        # 停牌按钮
        self.stand_button = tk.Button(
            action_frame, text="停牌",
            command=self.stand_action,
            font=('Arial', 14), bg='#2196F3', fg='white', width=7
        )
        self.stand_button.pack(side=tk.LEFT, padx=5)
        
        # 检查是否可以加倍
        can_double = (self.balance >= self.game.main_bet and 
                     len(self.game.player_hand) == 2 and not self.player_immediate_settled)
        
        # 加倍按钮
        self.double_button = tk.Button(
            action_frame, text="加倍",
            command=self.double_action,
            font=('Arial', 14), bg='#FF9800', fg='white', width=7,
            state=tk.NORMAL if can_double else tk.DISABLED
        )
        self.double_button.pack(side=tk.LEFT, padx=5)
        
        # 检查是否可以投降
        can_surrender = len(self.game.player_hand) == 2 and not self.player_immediate_settled
        
        # 投降按钮
        self.surrender_button = tk.Button(
            action_frame, text="投降",
            command=self.surrender_action,
            font=('Arial', 14), bg='#F44336', fg='white', width=7,
            state=tk.NORMAL if can_surrender else tk.DISABLED
        )
        self.surrender_button.pack(side=tk.LEFT, padx=5)
        
        self.status_label.config(text="请选择您的操作")
    
    def hit_action(self):
        """玩家要牌 -- 按下时立刻禁用4个操作按钮，再发一张牌并播放翻牌动画。"""
        # 立刻禁用玩家四个操作按钮（防止重复点击）
        self.hit_button.config(state=tk.DISABLED)
        self.stand_button.config(state=tk.DISABLED)
        self.surrender_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)

        # 玩家要牌（逻辑在 BlackjackGame.player_hit）
        new_value = self.game.player_hit()
        new_card = self.game.player_hand[-1]

        # 把牌的 UI 放上去（先背面，翻牌动画会展示面）
        position = len(self.game.player_hand) - 1
        new_card_label = self.add_card_to_frame(self.player_cards_frame, new_card, show_front=False, position=position)

        # 翻牌动画，回调到 after_hit 处理后续逻辑
        self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_hit(new_value))

    def after_hit(self, new_value):
        """玩家拿到牌后处理：
        - 检查是否满足立即结算条件
        - 若爆牌：判断是否需要庄家行动
        - 若刚好21：自动视为停牌，判断是否需要庄家行动
        - 否则：恢复"要牌/停牌"为可用（投降/加倍仍禁用）。
        """
        self.update_hand_labels()

        # 检查是否满足立即结算条件
        immediate_win = self.game.check_player_immediate_win()
        if immediate_win:
            self.game.player_immediate_win = immediate_win
            self.player_immediate_settled = True
            self.game.player_done = True
            
            win_type = immediate_win["type"]
            if win_type == "blackjack":
                message = "玩家Blackjack！主注立即以3:2胜出"
            elif win_type == "5_card_21":
                message = "玩家5龙21点！主注立即以2:1胜出"
            elif win_type == "any_21":
                message = "玩家21点！主注立即以1:1胜出"
            elif win_type == "5_card":
                message = "玩家5张牌！主注立即以1:1胜出"
            
            self.status_label.config(text=message)
            
            # 立即结算主注
            self.immediate_settle_main_bet()
            
            # 修正2: 检查是否需要庄家行动（保险或22点边注）
            needs_dealer_action = False
            
            # 如果玩家有保险或22点边注，庄家需要行动
            if self.game.insurance_bet > 0 or self.game.twenty_two_side_bet > 0:
                needs_dealer_action = True
                # 标记庄家需要行动的原因
                if self.game.insurance_bet > 0:
                    self.game.dealer_forced_hit_for_insurance = True
                if self.game.twenty_two_side_bet > 0:
                    self.game.dealer_needs_to_play = True
            
            if needs_dealer_action:
                # 延迟后进入庄家回合
                self.after(2000, self.dealer_turn)
            else:
                # 不需要庄家行动，直接结算
                self.after(2000, self.show_showdown)
            return

        # 爆牌情况
        if new_value > 21:
            self.game.player_done = True
            self.status_label.config(text="玩家爆牌！")
            
            # 修正2: 检查是否需要庄家行动（保险或22点边注）
            needs_dealer_action = False
            
            # 如果玩家有保险或22点边注，庄家需要行动
            if self.game.insurance_bet > 0 or self.game.twenty_two_side_bet > 0:
                needs_dealer_action = True
                # 标记庄家需要行动的原因
                if self.game.insurance_bet > 0:
                    self.game.dealer_forced_hit_for_insurance = True
                if self.game.twenty_two_side_bet > 0:
                    self.game.dealer_needs_to_play = True
            
            if needs_dealer_action:
                # 延迟后进入庄家回合
                self.after(1000, self.dealer_turn)
            else:
                # 不需要庄家行动，直接结算
                self.after(1000, self.show_showdown)
            return

        # 刚好21点 -> 自动停牌（不需玩家手动按停）
        if new_value == 21:
            self.game.player_done = True
            self.status_label.config(text="玩家达到21点，自动停牌")
            
            # 修正2: 检查是否需要庄家行动（保险或22点边注）
            needs_dealer_action = True  # 默认需要庄家行动，除非有特殊情况
            
            # 如果玩家有保险或22点边注，庄家需要行动
            if self.game.insurance_bet > 0 or self.game.twenty_two_side_bet > 0:
                needs_dealer_action = True
                # 标记庄家需要行动的原因
                if self.game.insurance_bet > 0:
                    self.game.dealer_forced_hit_for_insurance = True
                if self.game.twenty_two_side_bet > 0:
                    self.game.dealer_needs_to_play = True
            
            if needs_dealer_action:
                # 小延迟后进入庄家回合
                self.after(600, self.dealer_turn)
            else:
                # 不需要庄家行动，直接结算
                self.after(600, self.show_showdown)
            return

        # 否则仍在玩家回合：恢复"要牌"和"停牌"为可用；"加倍"和"投降"保持禁用
        self.hit_button.config(state=tk.NORMAL)
        self.stand_button.config(state=tk.NORMAL)
        self.surrender_button.config(state=tk.DISABLED)
        self.double_button.config(state=tk.DISABLED)

        self.status_label.config(text="请选择您的操作")

    def stand_action(self):
        """玩家停牌：按下立刻禁用四按钮，然后标记停牌并启动庄家回合。"""
        # 立刻禁用防止二次点击
        try:
            self.disable_action_buttons()
        except Exception:
            pass

        self.game.player_done = True
        self.status_label.config(text="玩家停牌")
        # 小延迟后开始庄家回合
        self.after(600, self.dealer_turn)


    def double_action(self):
        """玩家加倍：按下立刻禁用四按钮，扣除加倍金额，发一张牌后进入庄家回合（玩家结束）。"""
        # 立刻禁用
        try:
            self.disable_action_buttons()
        except Exception:
            pass

        # 余额检查
        if self.balance < self.game.main_bet:
            messagebox.showerror("错误", "余额不足以加倍")
            # 恢复按钮
            try:
                self.hit_button.config(state=tk.NORMAL)
                self.stand_button.config(state=tk.NORMAL)
            except Exception:
                pass
            return

        # 扣除加倍金额并把主注翻倍
        self.balance -= self.game.main_bet
        self.game.main_bet *= 2
        self.main_bet_var.set(self.game.main_bet)
        self.update_balance()

        total_bet = (self.game.main_bet + self.game.perfect_pair_bet +
                self.game.twenty_one_plus_three_bet + self.game.royal_match_bet +
                self.game.twenty_two_side_bet + self.game.hot_3_bet + self.game.lucky_queen_bet + self.game.insurance_bet)  # 修改：爆！改为22点

        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")

        # 玩家要一张牌（加倍规则：只要一张牌）
        new_value = self.game.player_hit()
        new_card = self.game.player_hand[-1]

        # 显示牌并翻牌
        position = len(self.game.player_hand) - 1
        new_card_label = self.add_card_to_frame(self.player_cards_frame, new_card, show_front=False, position=position)
        self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_double(new_value))

    def after_double(self, new_value):
        """加倍后处理：更新点数、标记玩家回合结束，检查立即结算条件"""
        self.update_hand_labels()
        self.game.player_done = True

        # 检查是否满足立即结算条件
        immediate_win = self.game.check_player_immediate_win()
        if immediate_win:
            self.game.player_immediate_win = immediate_win
            self.player_immediate_settled = True
            
            win_type = immediate_win["type"]
            if win_type == "blackjack":
                message = "玩家Blackjack！主注立即以3:2胜出"
            elif win_type == "5_card_21":
                message = "玩家5龙21点！主注立即以2:1胜出"
            elif win_type == "any_21":
                message = "玩家21点！主注立即以1:1胜出"
            elif win_type == "5_card":
                message = "玩家5张牌！主注立即以1:1胜出"
            
            self.status_label.config(text=message)
            
            # 立即结算主注
            self.immediate_settle_main_bet()
        
        if new_value > 21:
            self.status_label.config(text="玩家爆牌（加倍）！")
        else:
            self.status_label.config(text="玩家加倍完成")
        
        # 修正1: 加倍后除非玩家是21点（立即结算），否则等同于停牌，进入庄家回合
        # 庄家总是需要行动，除非玩家立即结算并且没有保险/22点边注
        
        # 检查是否需要庄家行动
        needs_dealer_action = True
        
        # 如果玩家立即结算（21点）且没有保险和22点边注，不需要庄家行动
        if self.player_immediate_settled and self.game.insurance_bet == 0 and self.game.twenty_two_side_bet == 0:
            needs_dealer_action = False
        # 如果玩家爆牌，检查是否需要庄家行动
        elif new_value > 21:
            # 玩家爆牌，检查保险和22点边注
            needs_dealer_action = False
            if self.game.insurance_bet > 0 or self.game.twenty_two_side_bet > 0:
                needs_dealer_action = True
        
        if needs_dealer_action:
            # 标记庄家需要行动的原因
            if self.game.insurance_bet > 0:
                self.game.dealer_forced_hit_for_insurance = True
            if self.game.twenty_two_side_bet > 0:
                self.game.dealer_needs_to_play = True
                
            # 进入庄家回合
            self.after(800, self.dealer_turn)
        else:
            # 直接结算
            self.after(800, self.show_showdown)

    def surrender_action(self):
        """玩家投降：按下立刻禁用四按钮，退回一半主注，并在界面将主注显示为'投降'直到 reset。
        如果边注的保险和22点有下注，庄家需要行动。"""
        # 立刻禁用
        try:
            self.disable_action_buttons()
        except Exception:
            pass

        # 退还一半主注
        surrender_amount = 0
        try:
            surrender_amount = self.game.main_bet / 2
        except Exception:
            surrender_amount = 0

        # 加回余额
        self.balance += surrender_amount

        # 立即把退回的这笔加入到“上局获胜”
        try:
            self.last_win += surrender_amount
        except Exception:
            self.last_win = surrender_amount
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")

        # 在游戏内部把主注标记为已投降
        self.game.main_bet = 0

        # UI上显示为"投降"
        try:
            self.main_bet_var.set("投降")
        except Exception:
            pass

        self.update_balance()
        self.game.player_done = True
        self.status_label.config(text="玩家投降，退还一半主注")

        # 修正2: 投降后检查保险和22点边注
        # 如果有保险或22点边注，庄家需要行动
        if self.game.insurance_bet > 0 or self.game.twenty_two_side_bet > 0:
            self.status_label.config(text="玩家投降，庄家行动.")

            # 标记庄家需要行动的原因
            if self.game.insurance_bet > 0:
                self.game.dealer_forced_hit_for_insurance = True
            if self.game.twenty_two_side_bet > 0:
                self.game.dealer_needs_to_play = True

            # 延迟后进入庄家回合
            self.after(800, self.dealer_turn)
        else:
            # 没有保险或22点边注，直接结算
            self.after(800, self.show_showdown)
    
    def dealer_turn(self):
        """庄家回合（如果还没第二张牌则发第二张并翻牌；否则直接进入翻牌后的处理）"""
        self.game.stage = "dealer_turn"
        self.stage_label.config(text="庄家回合")

        # 如果庄家还没有第二张牌，发第二张牌并用翻牌动画
        if len(self.game.dealer_hand) < 2:
            self.status_label.config(text="庄家要牌")
            dealer_card2 = self.game.deck.deal_card()
            self.game.dealer_hand.append(dealer_card2)

            # 把第二张牌加入 UI（背面）
            self.dealer_hidden_card_label = self.add_card_to_frame(
                self.dealer_cards_frame, dealer_card2, show_front=False, position=1
            )
            self.game.dealer_second_card_dealt = True

            # 使用翻牌动画，动画结束后统一走 after_reveal_dealer_card
            # 使用 callback 引用（不要带括号）
            self.flip_card_animation(self.dealer_hidden_card_label, dealer_card2, callback=self.after_reveal_dealer_card)
        else:
            # 已有第二张牌 -> 直接进入翻牌后的处理（例如直接检查是否需要继续要牌）
            # 用短延迟保证 UI 有机会刷新
            self.after(50, self.after_reveal_dealer_card)
    
    def immediate_settle_main_bet(self):
        """立即结算主注"""
        if not self.game.player_immediate_win:
            return

        payout = self.game.player_immediate_win["payout"]
        win_amount = self.game.main_bet * (payout - 1)  # 净赢额

        # 退还主注本金 + 赢得的金额（总返回）
        total_return = self.game.main_bet + win_amount

        # 1) 加到余额
        self.balance += total_return
        self.update_balance()

        # 2) 立即把这笔从下注区回到余额的款项计入“上局获胜”
        try:
            self.last_win += total_return
        except Exception:
            self.last_win = total_return
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")

        # 更新主注显示（界面上显示为返回的总额）并标记已结算（清主注）
        self.win_details["main"] = total_return
        self.main_bet_var.set(str(int(total_return)))
        self.main_bet_display.config(bg='gold')

        # 标记主注已结算
        self.game.main_bet = 0

    def after_reveal_dealer_card(self):
        """
        翻开庄家第二张牌后的统一处理：
        - 处理保险（如果存在强制保险检查）
        - 处理庄家 Blackjack 的加倍退款
        - 决定是否进入 dealer_hit_loop（并用 after() 调度）
        - 否则进入结算 show_showdown()
        """
        # 更新 UI 手牌显示（翻牌后要刷新）
        self.update_hand_labels()

        # 先处理可能由“强制检查保险”引起的特殊逻辑
        if getattr(self.game, "dealer_forced_hit_for_insurance", False):
            # 如果存在第二张牌，检查是否为 J/Q/K（按你的规则）
            if len(self.game.dealer_hand) >= 2:
                dealer_second_card = self.game.dealer_hand[1]
                if dealer_second_card.rank in ['J', 'Q', 'K']:
                    # 保险获胜：按 2:1 支付（此处我们把“本金+净赢”一起返回）
                    insurance_win = self.game.insurance_bet * 3
                    if insurance_win:
                        self.balance += insurance_win
                        self.update_balance()
                        # 立即把这笔也计入“上局获胜”（如果你有这个变量）
                        try:
                            self.last_win += insurance_win
                        except Exception:
                            self.last_win = insurance_win
                        try:
                            self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
                        except Exception:
                            pass
                        self.insurance_var.set(str(int(insurance_win)))
                        self.insurance_display.config(bg='gold')

                    # 清除保险投注，避免重复发放
                    self.win_details['insurance'] = insurance_win
                    self.game.insurance_bet = 0
                    self.game.insurance_taken = False
                    self.status_label.config(text="庄家第二张牌是J/Q/K，保险获胜！")
                else:
                    self.status_label.config(text="庄家第二张牌不是J/Q/K，保险失败")
            # 无论如何，保险强制检查已处理
            self.game.dealer_forced_hit_for_insurance = False

        # 如果庄家有 Blackjack，处理可能的“加倍退款”等并直接结算
        if len(self.game.dealer_hand) == 2 and self.game.check_blackjack(self.game.dealer_hand):
            self.game.dealer_blackjack = True
            self.update_hand_labels()
            self.status_label.config(text="庄家Blackjack！")

            # 如果玩家曾加倍（通过 original_main_bet 记录），退还加倍部分
            if hasattr(self, 'original_main_bet') and getattr(self, 'original_main_bet', 0) > 0 and self.game.main_bet > self.original_main_bet:
                double_amount = self.game.main_bet - self.original_main_bet
                if double_amount:
                    self.balance += double_amount
                    self.update_balance()
                    try:
                        self.last_win += double_amount
                    except Exception:
                        self.last_win = double_amount
                    try:
                        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
                    except Exception:
                        pass
                # 恢复主注为原始金额
                self.game.main_bet = self.original_main_bet
                self.main_bet_var.set(str(int(self.game.main_bet)))
                self.status_label.config(text=f"庄家Blackjack，退还加倍部分 ${double_amount}")

            # Blackjack 情况下一般不继续要牌，直接结算
            self.after(800, self.show_showdown)
            return

        # 到这里：没有因为 Blackjack 直接结束；判断是否需要继续庄家要牌
        # 优先按显式标志（例如 22点边注或其它需要庄家动作的标志）
        if getattr(self.game, "dealer_needs_to_play", False):
            self.after(10, self.dealer_hit_loop)
            return

        # 若没有显式标志，则根据庄家点数判断是否继续要牌（<17 或 Soft 17 需要牌）
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)
        need_hit = False
        if dealer_value < 17:
            need_hit = True
        elif dealer_value == 17 and self.game.is_soft_17(self.game.dealer_hand):
            need_hit = True

        if need_hit:
            self.status_label.config(text="庄家要牌")
            # 小延迟再进入要牌循环，保证界面翻牌已完成显示
            self.after(10, self.dealer_hit_loop)
        else:
            # 否则直接进入结算（给点延迟让玩家看到第二张牌）
            self.status_label.config(text="庄家停牌")
            self.after(800, self.show_showdown)
            
    def dealer_hit_loop(self):
        """
        庄家要牌循环：每次要牌后会执行翻牌动画，翻牌动画结束后由 after_dealer_hit() 再次回到本循环。
        只要满足要牌条件就继续；否则结束并进入结算。
        """
        # 刷新 UI 显示当前牌面和值
        self.update_hand_labels()

        dealer_value = self.game.get_hand_value(self.game.dealer_hand)

        # 判断是否需要继续要牌 (小于17 或 soft17)
        need_hit = False
        if dealer_value < 17:
            need_hit = True
        elif dealer_value == 17 and self.game.is_soft_17(self.game.dealer_hand):
            need_hit = True

        if need_hit:
            self.status_label.config(text=f"庄家要牌")
            # 让 game 执行一次 dealer_hit()，该方法应返回 (new_value, card)
            new_value, new_card = self.game.dealer_hit()

            # 在 UI 上把新牌加入到庄家手牌容器（注意 position 使用当前长度-1）
            position = len(self.game.dealer_hand) - 1
            new_card_label = self.add_card_to_frame(self.dealer_cards_frame, new_card, show_front=False, position=position)

            # 翻牌动画，回调到 after_dealer_hit（动画结束后继续本循环）
            self.flip_card_animation(new_card_label, new_card, callback=lambda: self.after_dealer_hit(new_value))
        else:
            # 庄家停牌 -> 进入结算
            self.status_label.config(text=f"庄家停牌")
            self.after(800, self.show_showdown)
    
    def after_dealer_hit(self, new_value):
        """庄家要牌后"""
        self.update_hand_labels()
        
        # 等待后继续要牌
        self.after(100, self.dealer_hit_loop)
    
    def show_showdown(self):
        """结算阶段"""
        self.game.stage = "showdown"
        self.stage_label.config(text="结算")
        
        # 修正6: 只在结算时移除庄家第二张牌的开牌动作
        # 直接显示庄家第二张牌，没有翻牌动画
        self.reveal_dealer_second_card_no_animation()
        
        # 延迟后进行结算
        self.after(500, self._do_showdown)
    
    def reveal_dealer_second_card_no_animation(self):
        """无动画显示庄家第二张牌（仅在结算时调用）"""
        if len(self.game.dealer_hand) >= 2:
            # 查找庄家第二张牌的标签
            dealer_card_labels = [w for w in self.dealer_cards_frame.winfo_children() if isinstance(w, tk.Label)]
            if dealer_card_labels and len(dealer_card_labels) > 1:
                second_card_label = dealer_card_labels[1]
                dealer_second_card = self.game.dealer_hand[1]
                
                # 如果第二张牌是背面朝上，直接显示正面，没有动画
                if hasattr(second_card_label, 'is_face_up') and not second_card_label.is_face_up:
                    second_card_label.config(image=self.card_images.get((dealer_second_card.suit, dealer_second_card.rank), self.back_image))
                    second_card_label.is_face_up = True

    def _do_showdown(self):
        # 计算赢得的金额（calculate_winnings 会返回总应支付给玩家的金额，包含本金）
        winnings, details = self.calculate_winnings()

        self.balance += winnings
        self.update_balance()

        # 更新下注显示与颜色
        for bet_type, widget in self.bet_widgets.items():
            # 如果是主注且玩家已经立即结算，则跳过更新，保持立即结算的显示
            if bet_type == "main" and self.player_immediate_settled:
                continue
            
            win_amount = details.get(bet_type, 0)
            original_bet = getattr(self.game, f"{bet_type}_bet", 0)

            # 显示文本：如果输为0；如果和局为原下注；如果赢为总返回金额
            if win_amount == 0:
                display_text = "0"
                widget.config(bg='white')
            elif win_amount == original_bet:
                # 和局：退还本金（数字保持为下注金额），浅蓝背景
                display_text = str(int(original_bet))
                widget.config(bg='light blue')
            else:
                # 赢：显示总返回（本金 + 赢额），金色背景
                display_text = str(int(win_amount))
                widget.config(bg='gold')

            # 更新对应的 StringVar
            if bet_type == "main":
                self.main_bet_var.set(display_text)
            elif bet_type == "perfect_pair":
                self.perfect_pair_var.set(display_text)
            elif bet_type == "twenty_one_plus_three":
                self.twenty_one_plus_three_var.set(display_text)
            elif bet_type == "royal_match":
                self.royal_match_var.set(display_text)
            elif bet_type == "twenty_two_side":
                self.twenty_two_side_var.set(display_text)
            elif bet_type == "hot_3":
                self.hot_3_var.set(display_text)
            elif bet_type == "lucky_queen":
                self.lucky_queen_var.set(display_text)

        # 构建结算消息
        player_value = self.game.get_hand_value(self.game.player_hand)
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)

        status_text = ""
        
        self.update_hand_labels()
        
        # 检查是否已经立即结算
        if self.player_immediate_settled:
            status_text = "玩家主注已立即结算"
        elif self.game.player_blackjack:
            status_text = "玩家Blackjack胜利！"
        elif self.game.dealer_blackjack:
            if self.game.insurance_taken:
                status_text = "庄家Blackjack，保险支付"
            else:
                status_text = "庄家Blackjack胜利！"
        elif player_value > 21:
            status_text = "玩家爆牌，庄家胜利"
        elif dealer_value == 22 and player_value <= 20:
            status_text = "庄家22点，主注平局"
        elif dealer_value > 22:
            status_text = "庄家爆牌，玩家胜利"
        elif player_value > dealer_value:
            status_text = "玩家胜利"
        elif player_value < dealer_value:
            status_text = "庄家胜利"
        else:
            status_text = "和局"

        self.status_label.config(text=status_text)

        # 更新上局赢得金额显示 - 关键修复点！
        # winnings 已经是净赢利（总返回 - 总下注）
        self.last_win += winnings
        self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")

        # 显示"再来一局"按钮
        self.show_restart_button()

        # 设置 30 秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))

    def show_restart_button(self):
        """显示再来一局按钮"""
        # 清除操作按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=lambda: self.reset_game(False),
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
        )
        restart_btn.pack(pady=5)
        
    def calculate_winnings(self):
        """计算赢得的金额（返回元组：winnings, details）。"""
        winnings = 0
        details = {
            "main": 0,
            "perfect_pair": 0,
            "twenty_one_plus_three": 0,
            "royal_match": 0,
            "twenty_two_side": 0,
            "hot_3": 0,
            "lucky_queen": 0,
            "insurance": 0
        }

        player_value = self.game.get_hand_value(self.game.player_hand)
        dealer_value = self.game.get_hand_value(self.game.dealer_hand)

        # 1. 结算主注
        main_result = 0
        
        # 检查是否投降
        if self.game.main_bet == 0:  # 标记为投降
            main_result = 0
            details["main"] = 0
        # 检查双方都是21点的情况
        elif player_value == 21 and dealer_value == 21:
            player_card_count = len(self.game.player_hand)
            dealer_card_count = len(self.game.dealer_hand)
            
            # 玩家2张牌21点 vs 庄家2张牌21点 -> 平局
            if player_card_count == 2 and dealer_card_count == 2:
                main_result = self.game.main_bet  # 和局，退还下注
                details["main"] = self.game.main_bet
            # 玩家2张牌21点 vs 庄家3张或以上牌21点 -> 玩家胜利
            elif player_card_count == 2 and dealer_card_count >= 3:
                main_result = self.game.main_bet * 2.5  # Blackjack支付1.5倍
                details["main"] = main_result
            # 玩家3张或以上牌21点 vs 庄家2张牌21点 -> 庄家胜利
            elif player_card_count >= 3 and dealer_card_count == 2:
                main_result = 0
                details["main"] = 0
            # 其他情况（双方都是3张或以上牌21点）-> 平局
            else:
                main_result = self.game.main_bet
                details["main"] = self.game.main_bet
        # 检查玩家Blackjack
        elif self.game.player_blackjack and not self.game.dealer_blackjack:
            main_result = self.game.main_bet * 2.5
            details["main"] = main_result
        # 检查庄家Blackjack
        elif self.game.dealer_blackjack and not self.game.player_blackjack:
            if self.game.insurance_taken:
                main_result = 0
                details["main"] = 0
        elif player_value > 21:  # 玩家爆牌
            main_result = 0
            details["main"] = 0
        elif dealer_value == 22 and player_value <= 20:
            main_result = self.game.main_bet
            details["main"] = self.game.main_bet
        elif dealer_value > 22:  # 庄家爆牌
            main_result = self.game.main_bet * 2
            details["main"] = main_result
        elif player_value > dealer_value:  # 玩家赢
            main_result = self.game.main_bet * 2
            details["main"] = main_result
        elif player_value < dealer_value:  # 玩家输
            main_result = 0
            details["main"] = 0
        else:  # 和局
            main_result = self.game.main_bet
            details["main"] = self.game.main_bet
        
        winnings += main_result
        
        # 2. 结算完美对子 (修改赔率)
        if self.game.perfect_pair_bet > 0:
            pair_result = self.game.check_perfect_pair()
            if pair_result == "perfect":
                win_amount = self.game.perfect_pair_bet * 21  # 21:1
                details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "colored":
                win_amount = self.game.perfect_pair_bet * 11  # 11:1
                details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            elif pair_result == "mixed":
                win_amount = self.game.perfect_pair_bet * 6   # 6:1
                details["perfect_pair"] = win_amount + self.game.perfect_pair_bet
            else:
                win_amount = 0
                details["perfect_pair"] = 0
            winnings += details["perfect_pair"]
        
        # 3. 结算21+3 (修改赔率)
        if self.game.twenty_one_plus_three_bet > 0:
            twenty_one_result = self.game.check_twenty_one_plus_three()
            if twenty_one_result == "straight_three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 90  # 90:1
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight_flush":
                win_amount = self.game.twenty_one_plus_three_bet * 35  # 35:1
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "three_of_a_kind":
                win_amount = self.game.twenty_one_plus_three_bet * 29  # 29:1
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "straight":
                win_amount = self.game.twenty_one_plus_three_bet * 9   # 9:1
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            elif twenty_one_result == "flush":
                win_amount = self.game.twenty_one_plus_three_bet * 4.5  # 9:2 (4.5:1)
                details["twenty_one_plus_three"] = win_amount + self.game.twenty_one_plus_three_bet
            else:
                win_amount = 0
                details["twenty_one_plus_three"] = 0
            winnings += details["twenty_one_plus_three"]
        
        # 4. 结算皇家同花 (修改赔率)
        if self.game.royal_match_bet > 0:
            royal_result = self.game.check_royal_match()
            if royal_result == "royal":
                win_amount = self.game.royal_match_bet * 30  # 30:1
                details["royal_match"] = win_amount + self.game.royal_match_bet
            elif royal_result == "suited":
                win_amount = self.game.royal_match_bet * 2.5  # 5:2 (2.5:1)
                details["royal_match"] = win_amount + self.game.royal_match_bet
            else:
                win_amount = 0
                details["royal_match"] = 0
            winnings += details["royal_match"]
        
        # 5. 结算22点边注 (保持不变)
        if self.game.twenty_two_side_bet > 0:
            t22 = self.game.check_twenty_two_side_bet()
            if t22 == "same_suit":
                win_amount = self.game.twenty_two_side_bet * 50
                details["twenty_two_side"] = win_amount + self.game.twenty_two_side_bet
            elif t22 == "same_color":
                win_amount = self.game.twenty_two_side_bet * 20
                details["twenty_two_side"] = win_amount + self.game.twenty_two_side_bet
            elif t22 == "mixed_color":
                win_amount = self.game.twenty_two_side_bet * 8
                details["twenty_two_side"] = win_amount + self.game.twenty_two_side_bet
            else:
                details["twenty_two_side"] = 0
            winnings += details["twenty_two_side"]
        
        # 6. 结算热门3 (修改赔率)
        if self.game.hot_3_bet > 0:
            hot_3_result = self.game.check_hot_3()
            if hot_3_result == "three_seven_same_suit":
                win_amount = self.game.hot_3_bet * 350  # 350:1
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "three_seven_mixed":
                win_amount = self.game.hot_3_bet * 75   # 75:1
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "twenty_one_same_suit":
                win_amount = self.game.hot_3_bet * 19   # 19:1
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "twenty_one_mixed":
                win_amount = self.game.hot_3_bet * 4    # 4:1
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "twenty":
                win_amount = self.game.hot_3_bet * 1.5  # 3:2 (1.5:1)
                details["hot_3"] = win_amount + self.game.hot_3_bet
            elif hot_3_result == "nineteen":
                win_amount = self.game.hot_3_bet * 1    # 1:1
                details["hot_3"] = win_amount + self.game.hot_3_bet
            else:
                details["hot_3"] = 0
            winnings += details["hot_3"]
        
        # 7. 结算幸运女王 (修改赔率)
        if self.game.lucky_queen_bet > 0:
            lucky_queen_result = self.game.check_lucky_queen()
            if lucky_queen_result == "queens_same_suit_dealer_bj":
                win_amount = self.game.lucky_queen_bet * 600  # 600:1
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            elif lucky_queen_result == "queens_same_suit":
                win_amount = self.game.lucky_queen_bet * 60   # 60:1
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            elif lucky_queen_result == "same_rank_same_suit":
                win_amount = self.game.lucky_queen_bet * 20   # 20:1
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            elif lucky_queen_result == "same_suit":
                win_amount = self.game.lucky_queen_bet * 8    # 8:1
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            elif lucky_queen_result == "mixed":
                win_amount = self.game.lucky_queen_bet * 3.5  # 7:2 (3.5:1)
                details["lucky_queen"] = win_amount + self.game.lucky_queen_bet
            else:
                details["lucky_queen"] = 0
            winnings += details["lucky_queen"]

        # 保险（insurance）
        if self.game.insurance_bet > 0:
            if self.game.dealer_blackjack and not self.game.player_blackjack:
                insurance_win = self.game.insurance_bet * 3  # 2:1 赔付（返回为净赢+本金）
                details["insurance"] = insurance_win
                self.insurance_var.set(str(int(insurance_win)))
                self.insurance_display.config(bg='gold')
            else:
                details["insurance"] = 0
                self.insurance_var.set("0")
            winnings += details["insurance"]

        return winnings, details

    def reset_bets(self):
        """重置下注金额为0"""
        self.main_bet_var.set("0")
        self.perfect_pair_var.set("0")
        self.twenty_one_plus_three_var.set("0")
        self.royal_match_var.set("0")
        self.twenty_two_side_var.set("0")  # 修改：爆！改为22点
        self.hot_3_var.set("0")
        self.lucky_queen_var.set("0")
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        for widget in self.bet_widgets.values():
            widget.config(bg='#FFCDD2')
        self.after(500, lambda: [w.config(bg='white') for w in self.bet_widgets.values()])

    def animate_cards_out(self):
        """将当前所有扑克牌向右移出屏幕的动画"""
        # 收集所有需要动画的卡片标签
        all_card_labels = []
        
        # 收集庄家区域的卡片
        for widget in self.dealer_cards_frame.winfo_children():
            if isinstance(widget, tk.Label) and hasattr(widget, 'card'):
                all_card_labels.append(widget)
        
        # 收集玩家区域的卡片
        for widget in self.player_cards_frame.winfo_children():
            if isinstance(widget, tk.Label) and hasattr(widget, 'card'):
                all_card_labels.append(widget)
        
        if not all_card_labels:
            # 如果没有卡片，直接返回
            return
        
        # 设置动画参数
        total_steps = 20  # 动画总步数
        step_delay = 20   # 每步延迟(毫秒)
        total_distance = 800  # 总移动距离
        
        def move_step(step):
            if step > total_steps:
                # 动画完成，销毁所有卡片
                for card_label in all_card_labels:
                    try:
                        card_label.destroy()
                    except:
                        pass
                return
            
            # 计算当前步的偏移量（使用缓动函数使动画更自然）
            progress = step / total_steps
            # 使用缓出函数
            eased_progress = 1 - (1 - progress) ** 3
            current_offset = int(total_distance * eased_progress)
            
            # 移动所有卡片
            for card_label in all_card_labels:
                try:
                    # 获取当前位置信息
                    place_info = card_label.place_info()
                    if place_info:
                        original_x = int(place_info.get('x', 0))
                        # 设置新位置
                        card_label.place(x=original_x + current_offset)
                except:
                    pass
            
            # 继续下一步
            self.after(step_delay, lambda: move_step(step + 1))
        
        # 开始动画
        move_step(1)
        
    def reset_game(self, auto_reset=False):
        """重置游戏"""
        # 取消自动重置计时器
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except:
                pass
            self.auto_reset_timer = None
        
        # 设置重置标志
        self._resetting = True
        
        # 清除所有挂起的after事件
        for after_id in self.tk.eval('after info').split():
            self.after_cancel(after_id)

        # 先执行卡片移出动画，动画完成后再重置其他状态
        def after_animation():
            # 重置游戏状态
            self.game.reset_game()
            
            # 重置赢利详情 - 关键修复点！
            self.win_details = {
                "main": 0,
                "perfect_pair": 0,
                "twenty_one_plus_three": 0,
                "royal_match": 0,
                "twenty_two_side": 0,
                "hot_3": 0,
                "lucky_queen": 0,
                "insurance": 0
            }
            
            # 重置上局获胜金额
            self.last_win = 0
            self.last_win_label.config(text="上局获胜: $0.00")
            
            self.stage_label.config(text="下注阶段")
            self.status_label.config(text="设置下注金额并开始游戏")
            
            # 重置标签显示
            self.player_label.config(text="玩家")
            self.dealer_label.config(text="庄家")
            
            # 重置下注金额为0
            self.main_bet_var.set("0")
            self.perfect_pair_var.set("0")
            self.twenty_one_plus_three_var.set("0")
            self.royal_match_var.set("0")
            self.twenty_two_side_var.set("0")
            self.hot_3_var.set("0")
            self.lucky_queen_var.set("0")
            
            # 重置保险显示为边注全下按钮
            self.insurance_label.pack_forget()
            self.insurance_display.pack_forget()
            self.insurance_var.set("0")
            self.side_bet_all_in_btn.pack(side=tk.LEFT, padx=5)
            
            # 重置背景色为白色
            for widget in self.bet_widgets.values():
                widget.config(bg='white')
            self.insurance_display.config(bg='white')
            
            # 清空活动卡片列表
            self.active_card_labels = []
            self.dealer_hidden_card_label = None
            
            # 清除所有动画状态
            self.flipping_cards = []
            self.flip_step = 0
            
            # 重置立即结算标志
            self.player_immediate_settled = False
            self.game.player_immediate_win = None
            
            # 恢复下注区域
            self.enable_betting_area()
            
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
            self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
            self.reset_bets_button.config(state=tk.NORMAL)

            # 开始游戏按钮
            self.start_button = tk.Button(
                start_button_frame, text="开始游戏", 
                command=self.start_game, font=('Arial', 14),
                bg='#4CAF50', fg='white', width=10
            )
            self.start_button.pack(side=tk.LEFT)
            self.start_button.config(state=tk.NORMAL)
            
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
        
        # 启动卡片移出动画
        self.animate_cards_out()
        
        # 在动画完成后执行重置逻辑
        self.after(500, after_animation)  # 500ms后执行重置，给动画留出时间

def main(initial_balance=10000, username="Guest"):
    app = BlackjackGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: ${final_balance:.2f}")