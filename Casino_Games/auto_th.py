import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
from collections import Counter
from itertools import combinations
import math
import time
import secrets
import subprocess, sys

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '皇家顺', 8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花',
    4: '顺子', 3: '三条', 2: '两对', 1: '对子', 0: '高牌'
}

# 支付表
BET_PAYOUT = {
    # 胜负平
    "cowboy_win": 1,
    "tie": 19,
    "bull_win": 1,
    
    # 手牌组合
    "any_suited_connector": 0.66,
    "any_pair": 7.5,
    "any_ace_pair": 99,
    
    # 赢家牌型
    "high_card": 1.2,
    "two_pair": 2.1,
    "three_kind_straight": 3.7,
    "full_house": 19,
    "four_kind_flush": 247
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
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

def format_money(amount):
    """格式化金额显示，使用逗号分隔"""
    if amount >= 0:
        return "${:,.2f}".format(amount)
    else:
        return "-${:,.2f}".format(abs(amount))

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

def evaluate_hand(cards):
    values = sorted((c.value for c in cards), reverse=True)
    counts = Counter(values)
    suits = [c.suit for c in cards]

    unique_vals = sorted(set(values), reverse=True)
    if 14 in unique_vals:
        unique_vals.append(1)
    straight_vals = []
    seq = []
    for v in unique_vals:
        if not seq or seq[-1] - 1 == v:
            seq.append(v)
        else:
            seq = [v]
        if len(seq) >= 5:
            straight_vals = seq[:5]
            break

    flush_suit = next((s for s in SUITS if suits.count(s) >= 5), None)
    flush_cards = [c for c in cards if c.suit == flush_suit] if flush_suit else []

    if flush_cards and straight_vals:
        flush_vals = sorted({c.value for c in flush_cards}, reverse=True)
        if 14 in flush_vals:
            flush_vals.append(1)
        seq2 = []
        for v in flush_vals:
            if not seq2 or seq2[-1] - 1 == v:
                seq2.append(v)
            else:
                seq2 = [v]
            if len(seq2) >= 5:
                return (9, seq2[:5]) if seq2[0] == 14 else (8, seq2[:5])

    counts_list = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if counts_list[0][1] == 4:
        quad = counts_list[0][0]
        kicker = max(v for v in values if v != quad)
        return (7, [quad, kicker])
    if counts_list[0][1] == 3 and counts_list[1][1] >= 2:
        return (6, [counts_list[0][0], counts_list[1][0]])
    if flush_suit:
        top5 = sorted((c.value for c in flush_cards), reverse=True)[:5]
        return (5, top5)
    if straight_vals:
        return (4, straight_vals)
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, [three] + kickers)
    pairs = [v for v, cnt in counts_list if cnt == 2]
    if len(pairs) >= 2:
        high, low = pairs[0], pairs[1]
        kicker = max(v for v in values if v not in (high, low))
        return (2, [high, low, kicker])
    if counts_list[0][1] == 2:
        pair = counts_list[0][0]
        kickers = [v for v in values if v != pair][:3]
        return (1, [pair] + kickers)
    return (0, values[:5])

def find_best_5(cards):
    best_eval = None
    best_hand = None
    for combo in combinations(cards, 5):
        ev = evaluate_hand(combo)
        if best_eval is None or ev > best_eval:
            best_eval = ev
            best_hand = combo
    return best_eval, best_hand

class TexasHoldemGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.cowboy_hole = []  # 牛仔手牌
        self.bull_hole = []    # 公牛手牌
        self.bets = {bet_type: 0 for bet_type in BET_PAYOUT}
        self.stage = "betting"  # betting, dealing, showdown
        self.cards_revealed = {
            "cowboy": [False, False],
            "bull": [False, False],
            "community": [False, False, False, False, False]
        }
        # 新增：记录牌序信息
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence
    
    def deal_initial(self):
        """发初始牌：牛仔2张，公牛2张，公共牌5张"""
        self.cowboy_hole = self.deck.deal(2)
        self.bull_hole = self.deck.deal(2)
        self.community_cards = self.deck.deal(5)
    
    def evaluate_hands(self):
        """评估牛仔和公牛的手牌"""
        cowboy_cards = self.cowboy_hole + self.community_cards
        bull_cards = self.bull_hole + self.community_cards
        
        cowboy_eval, cowboy_best = find_best_5(cowboy_cards)
        bull_eval, bull_best = find_best_5(bull_cards)
        
        return cowboy_eval, cowboy_best, bull_eval, bull_best
    
    def evaluate_current_hand(self, cards, community_revealed_count):
        """评估当前手牌（只考虑已翻开的牌）"""
        if community_revealed_count == 0:
            return None
        
        # 只使用已翻开的公共牌
        revealed_community = self.community_cards[:community_revealed_count]
        all_cards = cards + revealed_community
        
        # 至少需要2张牌才能评估
        if len(all_cards) < 2:
            return None
            
        best_eval, _ = find_best_5(all_cards)
        return best_eval
    
    def check_hand_combinations(self):
        """检查手牌组合"""
        results = {
            "any_suited_connector": False,
            "any_pair": False,
            "any_ace_pair": False
        }
        
        # 检查牛仔手牌
        c1, c2 = self.cowboy_hole
        # 同花
        if c1.suit == c2.suit:
            results["any_suited_connector"] = True
        # 连牌
        elif abs(c1.value - c2.value) == 1 or (c1.value == 14 and c2.value == 2) or (c1.value == 2 and c2.value == 14):
            results["any_suited_connector"] = True
        # 对子
        if c1.rank == c2.rank:
            results["any_pair"] = True
            if c1.rank == "A":
                results["any_ace_pair"] = True
        
        # 检查公牛手牌
        b1, b2 = self.bull_hole
        # 同花
        if b1.suit == b2.suit:
            results["any_suited_connector"] = True
        # 连牌
        elif abs(b1.value - b2.value) == 1 or (b1.value == 14 and b2.value == 2) or (b1.value == 2 and b2.value == 14):
            results["any_suited_connector"] = True
        # 对子
        if b1.rank == b2.rank:
            results["any_pair"] = True
            if b1.rank == "A":
                results["any_ace_pair"] = True
        
        return results
    
    def get_winner_hand_type(self, cowboy_eval, bull_eval):
        """确定赢家的牌型"""
        # 比较牌力确定赢家
        if cowboy_eval > bull_eval:
            winner_eval = cowboy_eval
        elif bull_eval > cowboy_eval:
            winner_eval = bull_eval
        else:
            # 相同牌型比较具体牌值
            for i in range(len(cowboy_eval[1])):
                if cowboy_eval[1][i] > bull_eval[1][i]:
                    winner_eval = cowboy_eval
                    break
                elif bull_eval[1][i] > cowboy_eval[1][i]:
                    winner_eval = bull_eval
                    break
            else:
                winner_eval = cowboy_eval  # or bull_eval，两者相同
                hand_rank = winner_eval[0]
                if hand_rank in [9, 8, 7]:      # 皇家顺、同花顺、四条
                    return "four_kind_flush", winner_eval
                elif hand_rank == 6:            # 葫芦
                    return "full_house", winner_eval
                elif hand_rank in [5, 4, 3]:     # 同花、顺子、三条
                    return "three_kind_straight", winner_eval
                elif hand_rank == 2:            # 两对
                    return "two_pair", winner_eval
                elif hand_rank in [1, 0]:       # 对子、高牌
                    return "high_card", winner_eval
        
        # 映射到我们的下注类别
        hand_rank = winner_eval[0]
        if hand_rank in [9, 8, 7]:  # 皇家顺、同花顺、四条
            return "four_kind_flush", winner_eval
        elif hand_rank == 6:  # 葫芦
            return "full_house", winner_eval
        elif hand_rank in [5, 4, 3]:  # 同花、顺子、三条
            return "three_kind_straight", winner_eval
        elif hand_rank == 2:  # 两对
            return "two_pair", winner_eval
        elif hand_rank in [1, 0]:  # 对子、高牌
            return "high_card", winner_eval

class TexasHoldemGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("德州扑克双人对决")
        self.geometry("850x755+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = TexasHoldemGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []  # 追踪所有活动中的卡片标签
        self.selected_chip = None  # 当前选中的筹码
        self.chip_buttons = []  # 筹码按钮列表
        self.last_win = 0
        self.auto_reset_timer = None
        self.auto_start_timer = None  # 自动开始游戏的计时器
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.win_details = {bet_type: 0 for bet_type in BET_PAYOUT}
        self.bet_widgets = {}  # 存储下注显示控件
        self.bet_start_time = 0  # 下注开始时间
        self.enter_enabled = True
        self.destroyed = False  # 标记窗口是否已被销毁
        
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 绑定键盘事件
        self.bind("<Return>", self.on_enter_key)

    def on_enter_key(self, event):
        """处理回车键按下事件"""
        if not self.enter_enabled or self.game.stage != "betting":
            return  # 如果Enter键禁用或不在投注阶段，不处理
            
        # 立即将倒计时设为0
        self.timer_label.config(text=f"下注时间: 0秒")
        
        # 取消自动开始计时器（如果存在）
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
            self.auto_start_timer = None
        
        # 禁用Enter键
        self.enter_enabled = False
        
        self.start_game()

    def show_game_instructions(self):
        """显示游戏规则说明"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("游戏规则")
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
        德州扑克双人对决游戏规则

        1. 游戏参与者:
           - 牛仔 (Cowboy): 电脑玩家A
           - 公牛 (Bull): 电脑玩家B

        2. 游戏流程:
           a. 下注阶段:
               - 玩家可以在多个选项上下注
               - 下注完成后点击"开始游戏"
               
           b. 发牌阶段:
               - 系统自动发牌：牛仔2张，公牛2张，公共牌5张
               
           c. 结算阶段:
               - 系统比较牛仔和公牛的牌力
               - 根据下注选项结算输赢

        3. 下注选项:
           a. 胜负平:
               - 牛仔胜 (1X)
               - 平手 (20X)
               - 公牛胜 (1X)
               
           b. 任一人手牌组合:
               - 同花/连牌 (1.66X)
               - 对子 (8.5X)
               - 对子A (100X)
               
           c. 赢家牌型:
               - 高牌/对子 (2.2X)
               - 两对 (3.1X)
               - 三条/顺子 (4.7X)
               - 葫芦 (20X)
               - 四条/同花顺 (248X)
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
    
    def on_close(self):
        """处理窗口关闭事件"""
        self.destroyed = True
        
        # 取消所有可能存在的计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
            self.auto_start_timer = None
        
        self.destroy()
        self.quit()
        
    def _load_assets(self):
        # 缩小卡片尺寸25% (75x105)
        card_size = (75, 105)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        
        # 花色映射：将符号映射为英文名称
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
            back_img_orig = Image.open(back_path)  # 原始尺寸
            self.original_images["back"] = back_img_orig  # 保存原始图像
            back_img = back_img_orig.resize(card_size)  # 缩放
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception as e:
            print(f"Error loading back image: {e}")
            # 创建黑色背景
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
        
        # 加载扑克牌图片
        for suit in SUITS:
            for rank in RANKS:
                # 获取映射后的文件名
                suit_name = suit_mapping.get(suit, suit)
                filename = f"{suit_name}{rank}.png"
                path = os.path.join(card_dir, filename)
                
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        # 保存原始图像
                        self.original_images[(suit, rank)] = img
                        # 创建缩放后的图像用于显示
                        img_resized = img.resize(card_size)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        # 创建占位图片
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        # 绘制卡片文本
                        text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 14)  # 缩小字体
                        except:
                            font = ImageFont.load_default()
                        text_width, text_height = draw.textsize(text, font=font)
                        x = (card_size[0] - text_width) / 2
                        y = (card_size[1] - text_height) / 2
                        draw.text((x, y), text, fill="white", font=font)
                        
                        # 保存原始图像
                        self.original_images[(suit, rank)] = img_orig
                        # 创建缩放后的图像用于显示
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading card image {path}: {e}")
                    # 创建占位图片
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    text = "Error"
                    try:
                        font = ImageFont.truetype("arial.ttf", 14)  # 缩小字体
                    except:
                        font = ImageFont.load_default()
                    text_width, text_height = draw.textsize(text, font=font)
                    x = (card_size[0] - text_width) / 2
                    y = (card_size[1] - text_height) / 2
                    draw.text((x, y), text, fill="white", font=font)
                    
                    # 保存原始图像
                    self.original_images[(suit, rank)] = img_orig
                    # 创建缩放后的图像用于显示
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                    
    def add_chip_to_bet(self, bet_type):
        """添加筹码到下注区域"""
        if not self.selected_chip:
            return
            
        # 获取筹码金额
        chip_value = float(self.selected_chip.replace('$', '').replace('K', '000'))
        
        # 更新对应的下注变量
        bet_var = getattr(self, f"{bet_type}_var", None)
        if bet_var:
            current = float(bet_var.get())
            new_value = current + chip_value
            # 检查总下注是否超过上限
            total_bet = self.get_total_bet() + chip_value
            if total_bet > 500000:  # 500,000上限
                messagebox.showwarning("下注上限", "本局下注总额不能超过500,000")
                return
                
            bet_var.set(str(int(new_value)))
    
    def get_total_bet(self):
        """计算总下注金额"""
        total = 0
        for bet_type in BET_PAYOUT:
            bet_var = getattr(self, f"{bet_type}_var", None)
            if bet_var:
                total += float(bet_var.get())
        return total
    
    def reset_bet_area(self, event, bet_type):
        """重置特定下注区域（右键点击）"""
        bet_var = getattr(self, f"{bet_type}_var", None)
        if bet_var:
            bet_var.set("0")
            self.bet_widgets[bet_type].config(bg='white')
    
    def _create_widgets(self):
        # 主框架 - 上下布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部信息栏
        info_frame = tk.Frame(main_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: {format_money(self.balance)}",
            font=('Arial', 16),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # 牌桌区域
        table_frame = tk.Frame(main_frame, bg='#35654d')
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # 牛仔区域
        cowboy_frame = tk.Frame(table_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        cowboy_frame.place(x=10, y=20, width=180, height=180)
        self.cowboy_label = tk.Label(cowboy_frame, text="牛仔", font=('Arial', 16), bg='#2a4a3c', fg='white')
        self.cowboy_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.cowboy_cards_frame = tk.Frame(cowboy_frame, bg='#2a4a3c')
        self.cowboy_cards_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 公牛区域
        bull_frame = tk.Frame(table_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bull_frame.place(x=640, y=20, width=180, height=180)
        self.bull_label = tk.Label(bull_frame, text="公牛", font=('Arial', 16), bg='#2a4a3c', fg='white')
        self.bull_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.bull_cards_frame = tk.Frame(bull_frame, bg='#2a4a3c')
        self.bull_cards_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 公共牌区域 - 居中显示
        community_frame = tk.Frame(table_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        community_frame.place(x=210, y=20, width=410, height=180)
        community_label = tk.Label(community_frame, text="公共牌", font=('Arial', 16), bg='#2a4a3c', fg='white')
        community_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg='#2a4a3c')
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 下注区域 - 使用新布局
        bet_frame = tk.Frame(main_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=10, padx=10)
        
        # 胜负平区域 (第一行)
        top_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        top_row_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 牛仔赢
        cowboy_win_frame = tk.LabelFrame(top_row_frame, text="牛仔赢 (1X)", 
                                        font=('Arial', 20, 'bold'), bg='#2a4a3c', fg='white', width=150, height=80)
        cowboy_win_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.cowboy_win_var = tk.StringVar(value="0")
        cowboy_win_display = tk.Label(cowboy_win_frame, textvariable=self.cowboy_win_var, 
                                     font=('Arial', 14), bg='white', fg='black', height=2)
        cowboy_win_display.pack(fill=tk.BOTH, expand=True)
        cowboy_win_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("cowboy_win"))
        cowboy_win_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "cowboy_win"))
        self.bet_widgets["cowboy_win"] = cowboy_win_display
        
        # 平手
        tie_frame = tk.LabelFrame(top_row_frame, text="平手 (20X)", 
                                font=('Arial', 20, 'bold'), bg='#2a4a3c', fg='white', width=150, height=80)
        tie_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.tie_var = tk.StringVar(value="0")
        tie_display = tk.Label(tie_frame, textvariable=self.tie_var, 
                             font=('Arial', 14), bg='white', fg='black', height=2)
        tie_display.pack(fill=tk.BOTH, expand=True)
        tie_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("tie"))
        tie_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "tie"))
        self.bet_widgets["tie"] = tie_display
        
        # 公牛赢
        bull_win_frame = tk.LabelFrame(top_row_frame, text="公牛赢 (1X)", 
                                     font=('Arial', 20, 'bold'), bg='#2a4a3c', fg='white', width=150, height=80)
        bull_win_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.bull_win_var = tk.StringVar(value="0")
        bull_win_display = tk.Label(bull_win_frame, textvariable=self.bull_win_var, 
                                  font=('Arial', 14), bg='white', fg='black', height=2)
        bull_win_display.pack(fill=tk.BOTH, expand=True)
        bull_win_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bull_win"))
        bull_win_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "bull_win"))
        self.bet_widgets["bull_win"] = bull_win_display
        
        # 中下部区域 (第二行)
        bottom_row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        bottom_row_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 左边：任一人手牌
        hand_frame = tk.LabelFrame(bottom_row_frame, text="任一人手牌", 
                                 font=('Arial', 20, 'bold'), bg='#2a4a3c', fg='white')
        hand_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # 顺子/同花
        suited_frame = tk.LabelFrame(hand_frame, text="顺子/同花 (1.66X)", 
                                   font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', height=60)
        suited_frame.pack(fill=tk.X, padx=5, pady=2)
        self.any_suited_connector_var = tk.StringVar(value="0")
        suited_display = tk.Label(suited_frame, textvariable=self.any_suited_connector_var, 
                                font=('Arial', 12), bg='white', fg='black', height=1)
        suited_display.pack(fill=tk.BOTH, expand=True)
        suited_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("any_suited_connector"))
        suited_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "any_suited_connector"))
        self.bet_widgets["any_suited_connector"] = suited_display
        
        # 对子
        pair_frame = tk.LabelFrame(hand_frame, text="对子 (8.5X)", 
                                 font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', height=60)
        pair_frame.pack(fill=tk.X, padx=5, pady=2)
        self.any_pair_var = tk.StringVar(value="0")
        pair_display = tk.Label(pair_frame, textvariable=self.any_pair_var, 
                              font=('Arial', 12), bg='white', fg='black', height=1)
        pair_display.pack(fill=tk.BOTH, expand=True)
        pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("any_pair"))
        pair_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "any_pair"))
        self.bet_widgets["any_pair"] = pair_display
        
        # 对子A
        ace_pair_frame = tk.LabelFrame(hand_frame, text="对子A (100X)", 
                                     font=('Arial', 12, 'bold'), bg='#2a4a3c', fg='white', height=60)
        ace_pair_frame.pack(fill=tk.X, padx=5, pady=2)
        self.any_ace_pair_var = tk.StringVar(value="0")
        ace_pair_display = tk.Label(ace_pair_frame, textvariable=self.any_ace_pair_var, 
                                  font=('Arial', 12), bg='white', fg='black', height=1)
        ace_pair_display.pack(fill=tk.BOTH, expand=True)
        ace_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("any_ace_pair"))
        ace_pair_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "any_ace_pair"))
        self.bet_widgets["any_ace_pair"] = ace_pair_display
        
        # 右边：获胜牌型
        win_type_frame = tk.LabelFrame(bottom_row_frame, text="获胜牌型", 
                                     font=('Arial', 20, 'bold'), bg='#2a4a3c', fg='white')
        win_type_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # 第一行：高牌/两对
        win_row1 = tk.Frame(win_type_frame, bg='#2a4a3c')
        win_row1.pack(fill=tk.X, pady=2)
        
        # 高牌
        high_card_frame = tk.LabelFrame(win_row1, text="高牌/对子 (2.2X)", 
                                      font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60)
        high_card_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.high_card_var = tk.StringVar(value="0")
        high_card_display = tk.Label(high_card_frame, textvariable=self.high_card_var, 
                                   font=('Arial', 10), bg='white', fg='black', height=1)
        high_card_display.pack(fill=tk.BOTH, expand=True)
        high_card_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("high_card"))
        high_card_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "high_card"))
        self.bet_widgets["high_card"] = high_card_display
        
        # 两对
        two_pair_frame = tk.LabelFrame(win_row1, text="两对 (3.1X)", 
                                     font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60)
        two_pair_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.two_pair_var = tk.StringVar(value="0")
        two_pair_display = tk.Label(two_pair_frame, textvariable=self.two_pair_var, 
                                  font=('Arial', 10), bg='white', fg='black', height=1)
        two_pair_display.pack(fill=tk.BOTH, expand=True)
        two_pair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("two_pair"))
        two_pair_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "two_pair"))
        self.bet_widgets["two_pair"] = two_pair_display
        
        # 第二行：三条/葫芦
        win_row2 = tk.Frame(win_type_frame, bg='#2a4a3c')
        win_row2.pack(fill=tk.X, pady=2)
        
        # 三条
        three_kind_frame = tk.LabelFrame(win_row2, text="三条/顺子/同花 (4.7X)", 
                                       font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60)
        three_kind_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.three_kind_straight_var = tk.StringVar(value="0")
        three_kind_display = tk.Label(three_kind_frame, textvariable=self.three_kind_straight_var, 
                                    font=('Arial', 10), bg='white', fg='black', height=1)
        three_kind_display.pack(fill=tk.BOTH, expand=True)
        three_kind_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("three_kind_straight"))
        three_kind_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "three_kind_straight"))
        self.bet_widgets["three_kind_straight"] = three_kind_display
        
        # 葫芦
        full_house_frame = tk.LabelFrame(win_row2, text="葫芦 (20X)", 
                                       font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', width=100, height=60)
        full_house_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        self.full_house_var = tk.StringVar(value="0")
        full_house_display = tk.Label(full_house_frame, textvariable=self.full_house_var, 
                                    font=('Arial', 10), bg='white', fg='black', height=1)
        full_house_display.pack(fill=tk.BOTH, expand=True)
        full_house_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("full_house"))
        full_house_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "full_house"))
        self.bet_widgets["full_house"] = full_house_display
        
        # 第三行：四条/同花顺
        four_kind_frame = tk.LabelFrame(win_type_frame, text="四条/同花顺 (248X)", 
                                      font=('Arial', 16, 'bold'), bg='#2a4a3c', fg='white', height=60)
        four_kind_frame.pack(fill=tk.X, padx=5, pady=2)
        self.four_kind_flush_var = tk.StringVar(value="0")
        four_kind_display = tk.Label(four_kind_frame, textvariable=self.four_kind_flush_var, 
                                   font=('Arial', 10), bg='white', fg='black', height=1)
        four_kind_display.pack(fill=tk.BOTH, expand=True)
        four_kind_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("four_kind_flush"))
        four_kind_display.bind("<Button-3>", lambda e: self.reset_bet_area(e, "four_kind_flush"))
        self.bet_widgets["four_kind_flush"] = four_kind_display
        
        # 底部操作区域
        bottom_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        bottom_frame.pack(fill=tk.X, pady=10, padx=10)
        
        # 筹码区域
        chips_frame = tk.Frame(bottom_frame, bg='#2a4a3c')
        chips_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=(10, 5), pady=5, side=tk.LEFT)
        
        # 单行放置筹码
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(side=tk.LEFT, fill=tk.X, pady=5)
        
        # 修改后的筹码配置
        chip_configs = [
            ("$5", '#ff0000', 'white'),     # 红色背景，白色文字
            ('$25', '#00ff00', 'black'),   # 绿色背景，黑色文字
            ("$100", '#000000', 'white'),   # 黑色背景，白色文字
            ("$500", "#FF7DDA", 'black'),   # 粉色背景，黑色文字
            ("$1K", '#ffffff', 'black'),    # 白色背景，黑色文字
        ]
        
        self.chip_buttons = []
        self.chip_texts = {}  # 存储每个筹码按钮的文本
        for text, bg_color, fg_color in chip_configs:
            # 使用Canvas创建圆形筹码 - 尺寸改为55x55
            chip_canvas = tk.Canvas(chip_row, width=55, height=55, bg='#2a4a3c', highlightthickness=0)
            
            # 创建圆形（尺寸调整为51x51，在55x55画布中居中）
            chip_canvas.create_oval(2, 2, 53, 53, fill=bg_color, outline='black')
            
            # 创建文本（位置调整为画布中心）
            text_id = chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 16, 'bold'))
            
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text  # 存储文本
        
        # 默认选中$5筹码
        self.select_chip("$100")
        
        # 信息显示区域
        info_frame = tk.Frame(bottom_frame, bg='#2a4a3c')
        info_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 本局下注金额
        self.current_bet_label = tk.Label(
            info_frame, text="本局下注: $0", 
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(side=tk.TOP, anchor='e', padx=10, pady=5)
        
        # 上局获胜金额
        self.last_win_label = tk.Label(
            info_frame, text="上局获胜: $0", 
            font=('Arial', 14), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(side=tk.TOP, anchor='e', padx=10, pady=5)
        
        # 倒计时标签
        self.timer_label = tk.Label(
            info_frame, text="下注时间: 15秒", 
            font=('Arial', 14, 'bold'), bg='#2a4a3c', fg='#FF0000'
        )
        self.timer_label.pack(side=tk.TOP, anchor='e', padx=10, pady=5)
        
        # 操作按钮区域
        self.action_frame = tk.Frame(bottom_frame, bg='#2a4a3c')
        self.action_frame.pack(side=tk.RIGHT, fill=tk.X, padx=10)
        
        # 创建按钮框架
        button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        button_frame.pack(pady=5)
        
        # 游戏规则按钮
        self.info_button = tk.Button(
            bottom_frame,
            text="游戏规则",
            command=self.show_game_instructions,
            bg='#4B8BBE',
            fg='white',
            font=('Arial', 12),
            width=10,
            relief=tk.RAISED
        )
        self.info_button.pack(side=tk.RIGHT, padx=10, pady=5)
    
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
        self.balance_label.config(text=f"余额: {format_money(self.balance)}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
    
    def start_game(self):
        if self.destroyed:
            return
        
        self.enter_enabled = False
            
        try:
            # 收集所有下注金额
            bet_amounts = {
                "cowboy_win": float(self.cowboy_win_var.get()),
                "tie": float(self.tie_var.get()),
                "bull_win": float(self.bull_win_var.get()),
                "any_suited_connector": float(self.any_suited_connector_var.get()),
                "any_pair": float(self.any_pair_var.get()),
                "any_ace_pair": float(self.any_ace_pair_var.get()),
                "high_card": float(self.high_card_var.get()),
                "two_pair": float(self.two_pair_var.get()),
                "three_kind_straight": float(self.three_kind_straight_var.get()),
                "full_house": float(self.full_house_var.get()),
                "four_kind_flush": float(self.four_kind_flush_var.get())
            }
            
            # 计算总下注金额
            total_bet = sum(bet_amounts.values())
                
            # 修改后的代码 - 确保余额不足时不扣除金额
            if total_bet > self.balance:
                messagebox.showerror("错误", "余额不足")
                # 清空所有下注金额的数据结构
                for bet_type in bet_amounts:
                    bet_amounts[bet_type] = 0

                for bet_type, widget in self.bet_widgets.items():
                    getattr(self, f"{bet_type}_var").set("0")
                    # 背景色恢复白色
                    widget.config(bg='white')
                
                # 重置本局下注显示为0
                self.current_bet_label.config(text=f"本局下注: {format_money(0)}")
                
                # 重新启动15秒倒计时
                self.bet_start_time = time.time()
                if self.auto_start_timer:
                    self.after_cancel(self.auto_start_timer)
                self.auto_start_timer = self.after(1000, self.update_timer)
                total_bet = 0

            self.balance -= total_bet
            self.update_balance()
            
            # 更新本局下注显示
            self.current_bet_label.config(text=f"本局下注: {format_money(total_bet)}")
            
            # 取消自动开始计时器（如果存在）
            if self.auto_start_timer:
                self.after_cancel(self.auto_start_timer)
                self.auto_start_timer = None
            
            self.game.reset_game()
            self.game.deal_initial()
            self.game.bets = bet_amounts
            
            # 清除所有卡片
            for widget in self.cowboy_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.bull_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.community_cards_frame.winfo_children():
                widget.destroy()
            
            # 重置动画状态
            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            
            # 初始化卡片位置
            self.card_positions = {}
            
            # 添加所有卡片到动画队列
            self.animation_queue = []
            
            # 牛仔牌
            for i in range(2):
                card_id = f"cowboy_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 77.5, 0)  # 缩小间距
                }
                self.animation_queue.append(card_id)
            
            # 公牛牌
            for i in range(2):
                card_id = f"bull_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 77.5, 0)  # 缩小间距
                }
                self.animation_queue.append(card_id)
            
            # 公共牌
            for i in range(5):
                card_id = f"community_{i}"
                self.card_positions[card_id] = {
                    "current": (50, 50), 
                    "target": (i * 77.5, 0)  # 缩小间距
                }
                self.animation_queue.append(card_id)
            
            # 开始动画
            self.animate_deal()
            
            # 禁用下注区域
            for widget in self.bet_widgets.values():
                widget.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
    
    def animate_deal(self):
        if self.destroyed:
            return
            
        if not self.animation_queue:
            self.animation_in_progress = False
            # 发牌动画完成后翻开所有牌
            self.after(500, self.reveal_all_cards)
            return
            
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        
        # 创建卡片标签
        if card_id.startswith("cowboy"):
            frame = self.cowboy_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.cowboy_hole[idx] if idx < len(self.game.cowboy_hole) else None
        elif card_id.startswith("bull"):
            frame = self.bull_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.bull_hole[idx] if idx < len(self.game.bull_hole) else None
        elif card_id.startswith("community"):
            frame = self.community_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.community_cards[idx] if idx < len(self.game.community_cards) else None
        
        # 创建卡片标签
        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
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
        
        # 添加到活动卡片列表
        self.active_card_labels.append(card_label)
        
        # 开始移动动画
        self.animate_card_move(card_label)
    
    def animate_card_move(self, card_label):
        if self.destroyed:
            return
            
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
    
    def reveal_all_cards(self):
        if self.destroyed:
            return
            
        """翻开所有牌（带动画）"""
        # 翻牛仔牌
        for i, card_label in enumerate(self.cowboy_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记牌已翻开
                self.game.cards_revealed["cowboy"][i] = True
        
        # 翻公牛牌
        for i, card_label in enumerate(self.bull_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记牌已翻开
                self.game.cards_revealed["bull"][i] = True
                
        # 翻公共牌
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记牌已翻开
                self.game.cards_revealed["community"][i] = True
        
        # 更新牌型标签
        self.update_hand_labels()
        
        # 2秒后结算游戏
        self.after(2000, self.settle_game)
    
    def flip_card_animation(self, card_label):
        """卡片翻转动画"""
        # 获取卡片正面图像
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        
        # 创建动画序列
        self.animate_flip(card_label, front_img, 0)
    
    def animate_flip(self, card_label, front_img, step):
        if self.destroyed:
            return
            
        """执行翻转动画"""
        steps = 10  # 动画总步数
        
        if step > steps:
            # 动画结束
            card_label.is_face_up = True
            return
        
        if step <= steps // 2:
            # 第一阶段：从背面翻转到侧面（宽度减小）
            width = 75 - (step * 15)  # 缩小宽度变化
            if width <= 0:
                width = 1
            # 创建缩放后的背面图像
            card_label.config(image=self.back_image)
        else:
            # 第二阶段：从侧面翻转到正面（宽度增加）
            width = (step - steps // 2) * 15  # 缩小宽度变化
            if width <= 0:
                width = 1
            # 创建缩放后的正面图像
            card_label.config(image=front_img)
        
        # 更新卡片显示
        card_label.place(width=width)
        
        # 下一步
        step += 1
        card_label.after(50, lambda: self.animate_flip(card_label, front_img, step))
    
    def update_hand_labels(self):
        """更新牛仔和公牛的牌型标签"""
        # 计算牛仔当前牌型
        community_revealed_count = sum(self.game.cards_revealed["community"])
        cowboy_eval = self.game.evaluate_current_hand(self.game.cowboy_hole, community_revealed_count)
        cowboy_hand_name = HAND_RANK_NAMES[cowboy_eval[0]] if cowboy_eval else ""
        self.cowboy_label.config(text=f"牛仔 - {cowboy_hand_name}" if cowboy_hand_name else "牛仔")
        
        # 计算公牛当前牌型
        bull_eval = self.game.evaluate_current_hand(self.game.bull_hole, community_revealed_count)
        bull_hand_name = HAND_RANK_NAMES[bull_eval[0]] if bull_eval else ""
        self.bull_label.config(text=f"公牛 - {bull_hand_name}" if bull_hand_name else "公牛")
    
    def settle_game(self):
        if self.destroyed:
            return
            
        """结算游戏"""
        # 评估手牌
        cowboy_eval, cowboy_best, bull_eval, bull_best = self.game.evaluate_hands()
        
        # 确定赢家
        winner = None
        if cowboy_eval > bull_eval:
            winner = "cowboy"
        elif bull_eval > cowboy_eval:
            winner = "bull"
        else:
            # 相同牌型比较具体牌值
            for i in range(len(cowboy_eval[1])):
                if cowboy_eval[1][i] > bull_eval[1][i]:
                    winner = "cowboy"
                    break
                elif bull_eval[1][i] > cowboy_eval[1][i]:
                    winner = "bull"
                    break
            else:
                winner = "tie"  # 完全平局
        
        # 检查手牌组合
        hand_combinations = self.game.check_hand_combinations()
        
        # 确定赢家牌型
        winner_hand_type, winner_hand = self.game.get_winner_hand_type(cowboy_eval, bull_eval)
        
        # 计算赢利
        winnings = 0
        self.win_details = {bet_type: 0 for bet_type in BET_PAYOUT}
        
        # 胜负平下注结算
        if winner == "cowboy":
            winnings += self.game.bets["cowboy_win"] * (1 + BET_PAYOUT["cowboy_win"])
            self.win_details["cowboy_win"] = self.game.bets["cowboy_win"] * (1 + BET_PAYOUT["cowboy_win"])
        elif winner == "bull":
            winnings += self.game.bets["bull_win"] * (1 + BET_PAYOUT["bull_win"])
            self.win_details["bull_win"] = self.game.bets["bull_win"] * (1 + BET_PAYOUT["bull_win"])
        elif winner == "tie":
            winnings += self.game.bets["tie"] * (1 + BET_PAYOUT["tie"])
            self.win_details["tie"] = self.game.bets["tie"] * (1 + BET_PAYOUT["tie"])
        
        # 手牌组合下注结算
        for bet_type in ["any_suited_connector", "any_pair", "any_ace_pair"]:
            if hand_combinations[bet_type]:
                winnings += self.game.bets[bet_type] * (1 + BET_PAYOUT[bet_type])
                self.win_details[bet_type] = self.game.bets[bet_type] * (1 + BET_PAYOUT[bet_type])
        
        # 赢家牌型下注结算
        if winner_hand_type and winner_hand_type != "tie":
            winnings += self.game.bets[winner_hand_type] * (1 + BET_PAYOUT[winner_hand_type])
            self.win_details[winner_hand_type] = self.game.bets[winner_hand_type] * (1 + BET_PAYOUT[winner_hand_type])
        
        # 更新余额
        self.balance += winnings
        self.update_balance()
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: {format_money(winnings)}")
        
        # 显示结果
        result_text = f"游戏结束! {'牛仔' if winner == 'cowboy' else '公牛' if winner == 'bull' else '平手'}获胜"
        
        # 高亮显示获胜的下注选项
        hit_bets = {
            "cowboy_win": winner == "cowboy",
            "tie": winner == "tie",
            "bull_win": winner == "bull",
            "any_suited_connector": hand_combinations["any_suited_connector"],
            "any_pair": hand_combinations["any_pair"],
            "any_ace_pair": hand_combinations["any_ace_pair"],
            "high_card": winner_hand_type == "high_card",
            "two_pair": winner_hand_type == "two_pair",
            "three_kind_straight": winner_hand_type == "three_kind_straight",
            "full_house": winner_hand_type == "full_house",
            "four_kind_flush": winner_hand_type == "four_kind_flush"
        }
        
        # 在获胜格子中显示赔付金额（本金+利润）
        for bet_type, widget in self.bet_widgets.items():
            if hit_bets.get(bet_type, False):
                # 计算赔付金额 = 下注金额 * (1 + 赔率)
                payout_amount = float(getattr(self, f"{bet_type}_var").get()) * (1 + BET_PAYOUT[bet_type])
                # 更新显示
                if payout_amount.is_integer():
                    text = f"{payout_amount:.0f}"
                else:
                    text = f"{payout_amount:.1f}"

                getattr(self, f"{bet_type}_var").set(text)
                widget.config(bg='gold')
            else:
                getattr(self, f"{bet_type}_var").set("0")
                widget.config(bg='white')
        
        # 添加收起卡片的动画
        self.after(5000, self.collect_cards)
    
    def collect_cards(self):
        if self.destroyed:
            return
            
        """收起所有卡片到左上角"""
        # 设置所有卡片的回收位置
        for card_label in self.active_card_labels:
            card_label.target_pos = (50, 50)
            card_label.is_moving = True
        
        # 开始移动动画
        self.animate_card_collection()
    
    def animate_card_collection(self):
        if self.destroyed:
            return
            
        """执行卡片收起动画"""
        if not self.active_card_labels:
            # 所有卡片已收起，重置游戏
            self.auto_next_game()
            return
            
        # 移动所有活动卡片
        for card_label in list(self.active_card_labels):
            if not hasattr(card_label, "target_pos"):
                continue
                
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
                    
                    # 销毁卡片
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                    continue
                
                # 计算移动步长
                step_x = dx * 0.2
                step_y = dy * 0.2
                
                # 更新位置
                new_x = current_x + step_x
                new_y = current_y + step_y
                card_label.place(x=new_x, y=new_y)
            except tk.TclError:
                # 卡片已被销毁，停止动画
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
        
        # 继续动画
        self.after(20, self.animate_card_collection)
    
    def auto_next_game(self):
        if self.destroyed:
            return
            
        """自动开始下一局"""
        # 重置下注区域背景色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 重置游戏
        self.reset_game()
    
    def update_timer(self):
        if self.destroyed:
            return
            
        """更新下注倒计时"""
        elapsed = time.time() - self.bet_start_time
        remaining = max(0, 15 - int(elapsed))  # 修改3: 改为15秒
        self.timer_label.config(text=f"下注时间: {remaining}秒")
        
        if remaining > 0:
            # 继续更新倒计时
            self.auto_start_timer = self.after(1000, self.update_timer)
        else:
            # 时间到，自动开始游戏
            self.enter_enabled = False
            self.start_game()
    
    def reset_bets(self):
        """重置所有下注金额为0"""
        self.cowboy_win_var.set("0")
        self.tie_var.set("0")
        self.bull_win_var.set("0")
        self.any_suited_connector_var.set("0")
        self.any_pair_var.set("0")
        self.any_ace_pair_var.set("0")
        self.high_card_var.set("0")
        self.two_pair_var.set("0")
        self.three_kind_straight_var.set("0")
        self.full_house_var.set("0")
        self.four_kind_flush_var.set("0")
        
        # 更新本局下注显示
        self.current_bet_label.config(text=f"本局下注: {format_money(0)}")
            
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        for widget in self.bet_widgets.values():
            widget.config(bg='#FFCDD2')  # 浅红色
        self.after(500, lambda: [w.config(bg='white') for w in self.bet_widgets.values()])
    
    def reset_game(self, auto_reset=False):
        if self.destroyed:
            return
            
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 重置游戏状态
        self.game.reset_game()
        
        # 重置下注金额为0
        self.reset_bets()
        
        # 清空活动卡片列表
        self.active_card_labels = []
        
        # 清除所有卡片
        for widget in self.cowboy_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.bull_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.community_cards_frame.winfo_children():
            widget.destroy()
        
        # 重置牌型标签
        self.cowboy_label.config(text="牛仔")
        self.bull_label.config(text="公牛")
        
        # 恢复下注区域
        for bet_type, widget in self.bet_widgets.items():
            widget.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            widget.bind("<Button-3>", lambda e, bt=bet_type: self.reset_bet_area(e, bt))
        for chip in self.chip_buttons:
            # 使用存储的文本重新绑定事件
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        
        # 清除操作区域的额外按钮
        for widget in self.action_frame.winfo_children():
            if not isinstance(widget, tk.Frame):
                widget.destroy()
        
        # 启动15秒自动开始计时器
        self.bet_start_time = time.time()
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
        self.auto_start_timer = self.after(1000, self.update_timer)
        self.enter_enabled = True

    def show_card_sequence(self, event):
        """显示本局牌序窗口 - 右键点击时取消15秒计时"""
        # 取消自动开始计时器（如果存在）
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
            self.auto_start_timer = None
        
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

def main(initial_balance=1000, username="Guest"):  # 初始金额改为1000
    app = TexasHoldemGUI(initial_balance, username)
    app.reset_game()  # 初始化游戏并启动计时器
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"最终余额: {final_balance}")