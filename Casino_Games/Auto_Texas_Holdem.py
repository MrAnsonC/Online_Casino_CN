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

# =========================================================
# Caribbean Stud Poker 风格 UI 配色
# 下注区内部布局与交互保持 Auto Texas Hold'em 原设计
# =========================================================
ROOT_BG = "#1B3D31"
TABLE_PANEL_BG = "#2A4A3C"
TEXT = "#FFFFFF"
GOLD = "#D4AF37"
PANEL_BG = "#F2E6C9"
HEADER_BG = "#D8B46A"
TITLE_FG = "#2A1B08"
ACCENT_GOLD = "#A88100"
CARD_SIZE = (82, 115)
HOLE_CARD_SPACING = 88
COMMUNITY_CARD_SPACING = 84

def measure_text(draw, text, font):
    """兼容新版 Pillow 的文本尺寸计算。"""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '皇家同花顺', 8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花',
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

# 每个下注项目的独立上限。
BET_LIMITS = {
    "cowboy_win": 50000,
    "bull_win": 50000,
    "tie": 10000,
    "any_suited_connector": 25000,
    "any_pair": 25000,
    "any_ace_pair": 25000,
    "high_card": 25000,
    "two_pair": 25000,
    "three_kind_straight": 25000,
    "full_house": 25000,
    "four_kind_flush": 25000,
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
        self.cowboy_hole = []  # 玩家1手牌
        self.bull_hole = []    # 玩家2手牌
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
        """发初始牌：先发5张公共牌，再发玩家1和玩家2各2张。"""
        self.community_cards = self.deck.deal(5)
        self.cowboy_hole = self.deck.deal(2)
        self.bull_hole = self.deck.deal(2)
    
    def evaluate_hands(self):
        """评估玩家1和玩家2的手牌"""
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
        
        # 检查玩家1手牌
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
        
        # 检查玩家2手牌
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
                if hand_rank in [9, 8, 7]:      # 皇家同花顺、同花顺、四条
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
        if hand_rank in [9, 8, 7]:  # 皇家同花顺、同花顺、四条
            return "four_kind_flush", winner_eval
        elif hand_rank == 6:  # 葫芦
            return "full_house", winner_eval
        elif hand_rank in [5, 4, 3]:  # 同花、顺子、三条
            return "three_kind_straight", winner_eval
        elif hand_rank == 2:  # 两对 
            return "two_pair", winner_eval
        elif hand_rank in [1, 0]:  # 对子、高牌
            return "high_card", winner_eval

class TexasHoldemGUI(tk.Frame):
    def __init__(self, parent, initial_balance, username, on_back=None, on_balance_change=None):
        super().__init__(parent, bg=ROOT_BG)
        self.parent = parent
        self.on_back = on_back
        self.on_balance_change = on_balance_change
        self.configure(bg=ROOT_BG)
        
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
        self.last_bet = None
        self.auto_reset_timer = None
        self.auto_start_timer = None  # 自动开始游戏的计时器
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.win_details = {bet_type: 0 for bet_type in BET_PAYOUT}
        self.bet_widgets = {}  # 存储下注显示控件
        self.bet_start_time = 0  # 下注开始时间
        self.enter_enabled = True
        self.destroyed = False  # 标记页面是否已被销毁
        self.freeze_current_bet_display = False
        self._return_bind_id = None
        
        self._load_assets()
        self._create_widgets()

        # 嵌入 Parent 后，Enter 必须绑定到唯一根窗口，才能在任何子控件有焦点时生效。
        root = self.winfo_toplevel()
        self._return_bind_id = root.bind("<Return>", self.on_enter_key, add="+")
        self.bind("<Destroy>", self._handle_widget_destroy, add="+")

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
        win.configure(bg=PANEL_BG)
        
        # 创建主框架
        main_frame = tk.Frame(win, bg=PANEL_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建画布用于滚动
        canvas = tk.Canvas(main_frame, bg=PANEL_BG, yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        # 创建内部框架放置所有内容
        content_frame = tk.Frame(canvas, bg=PANEL_BG)
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        # 游戏规则文本
        rules_text = """
        德州扑克双人对决游戏规则

        1. 游戏参与者:
           - 玩家1 : 电脑玩家A
           - 玩家2 : 电脑玩家B

        2. 游戏流程:
           a. 预发牌阶段:
               - 系统先发公共牌5张，再发玩家1和玩家2各2张暗牌
               - 翻开第1张公共牌后才进入下注阶段

           b. 下注阶段:
               - 玩家可以在多个选项上下注
               - 按回车或等待15秒倒计时结束后停止下注

           c. 开牌与结算阶段:
               - 系统翻开其余公共牌及双方手牌
               - 比较玩家1和玩家2的牌力，并按下注选项结算输赢

        3. 下注选项:
           a. 胜负平:
               - 玩家1胜 (1X)
               - 平手 (20X)
               - 玩家2胜 (1X)
               
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
            bg=PANEL_BG,
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
    
    def _cancel_timers(self):
        for attr in ("auto_reset_timer", "auto_start_timer"):
            timer = getattr(self, attr, None)
            if timer:
                try:
                    self.after_cancel(timer)
                except tk.TclError:
                    pass
                setattr(self, attr, None)

    def _unbind_return_key(self):
        bind_id = getattr(self, "_return_bind_id", None)
        if bind_id:
            try:
                self.winfo_toplevel().unbind("<Return>", bind_id)
            except tk.TclError:
                pass
            self._return_bind_id = None

    def _handle_widget_destroy(self, event):
        """Parent 切换页面时安全停止计时器和键盘绑定。"""
        if event.widget is not self:
            return
        self.destroyed = True
        self._cancel_timers()
        self._unbind_return_key()

    def on_close(self):
        """返回 Parent 的赌场游戏页面，不销毁唯一的 Tk 根窗口。"""
        if self.destroyed:
            return

        self.destroyed = True
        self._cancel_timers()
        self._unbind_return_key()

        try:
            update_balance_in_json(self.username, self.balance)
        except Exception:
            pass

        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))

        if callable(self.on_back):
            self.on_back(float(self.balance))
        else:
            # 仅用于异常的无回调嵌入场景；不会销毁 Parent 根窗口。
            try:
                self.destroy()
            except tk.TclError:
                pass

    def _load_assets(self):
        card_size = CARD_SIZE
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 使用实例变量来跟踪当前使用的扑克牌文件夹
        if not hasattr(self, 'current_poker_folder'):
            # 第一次加载时随机选择
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            # 交替使用 Poker1 和 Poker2
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
        
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        
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
                if suit == 'JOKER':
                    filename = f"JOKER-A.png"  # 鬼牌文件名
                else:
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
                        if suit == 'JOKER':
                            text = "JOKER"
                        else:
                            text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        text_width, text_height = measure_text(draw, text, font)
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
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    text_width, text_height = measure_text(draw, text, font)
                    x = (card_size[0] - text_width) / 2
                    y = (card_size[1] - text_height) / 2
                    draw.text((x, y), text, fill="white", font=font)
                    
                    # 保存原始图像
                    self.original_images[(suit, rank)] = img_orig
                    # 创建缩放后的图像用于显示
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                    
    def _parse_chip_value(self, chip_text):
        raw = chip_text.replace('$', '').upper()
        return float(raw[:-1]) * 1000 if raw.endswith('K') else float(raw)

    def _format_bet_value(self, value):
        if float(value).is_integer():
            return str(int(value))
        return f"{value:.2f}".rstrip('0').rstrip('.')

    def get_bet_amounts(self):
        bet_amounts = {}
        for bet_type in BET_PAYOUT:
            bet_var = getattr(self, f"{bet_type}_var", None)
            if bet_var is not None:
                try:
                    bet_amounts[bet_type] = float(bet_var.get())
                except ValueError:
                    bet_amounts[bet_type] = 0.0
        return bet_amounts

    def _update_repeat_button_state(self):
        if hasattr(self, 'repeat_bet_btn') and self.repeat_bet_btn is not None:
            enabled = self.game.stage == "betting" and self.last_bet is not None
            self.repeat_bet_btn.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def refresh_bet_info(self):
        """刷新下注资讯；结算期间不改动“本局下注”显示。"""
        if not self.freeze_current_bet_display:
            total_bet = self.get_total_bet()
            if hasattr(self, 'current_bet_label'):
                self.current_bet_label.config(text=f"本局下注: {format_money(total_bet)}")
        self._update_repeat_button_state()

    def set_bet_amounts(self, bet_amounts):
        for bet_type in BET_PAYOUT:
            amount = float(bet_amounts.get(bet_type, 0))
            bet_var = getattr(self, f"{bet_type}_var", None)
            if bet_var is not None:
                bet_var.set(self._format_bet_value(amount))
        self.refresh_bet_info()

    def add_chip_to_bet(self, bet_type):
        """按当前选中筹码增加下注，并执行项目上限与余额上限。"""
        if not self.selected_chip or self.game.stage != "betting":
            return

        try:
            chip_value = self._parse_chip_value(self.selected_chip)
        except ValueError:
            return

        bet_var = getattr(self, f"{bet_type}_var", None)
        if bet_var is None:
            return

        current = float(bet_var.get())
        limit = BET_LIMITS[bet_type]
        requested = current + chip_value
        remaining_balance = max(0.0, self.balance - self.get_total_bet())
        max_by_balance = current + remaining_balance
        new_value = min(requested, limit, max_by_balance)

        if current >= limit:
            messagebox.showwarning("下注限制", f"该下注项目上限为 {format_money(limit)}")
            return

        if new_value <= current and remaining_balance <= 0:
            messagebox.showwarning("余额不足", "当前余额不足，无法继续下注。")
            return

        bet_var.set(self._format_bet_value(new_value))
        self.refresh_bet_info()

        if requested > limit:
            messagebox.showwarning("下注限制", f"该下注项目上限为 {format_money(limit)}，已自动调整。")
        elif requested > max_by_balance:
            messagebox.showwarning("余额不足", f"余额不足，已自动调整为当前可下注的最大金额 {format_money(new_value)}。")

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
            self.refresh_bet_info()
    
    def _create_widgets(self):
        """创建 1150×750 的 Caribbean Stud Poker 风格界面。"""
        main_frame = tk.Frame(self, bg=ROOT_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧牌桌。
        table_canvas = tk.Canvas(
            main_frame, bg=ROOT_BG, width=500, height=730,
            highlightthickness=0
        )
        table_canvas.pack(side=tk.LEFT, fill=tk.Y)
        table_canvas.pack_propagate(False)
        table_canvas.create_rectangle(
            3, 3, 496, 726, fill=ROOT_BG, outline=GOLD, width=5
        )

        player1_frame = tk.Frame(table_canvas, bg=TABLE_PANEL_BG, bd=2, relief=tk.RAISED)
        player1_frame.place(x=25, y=45, width=210, height=185)
        self.cowboy_label = tk.Label(
            player1_frame, text="玩家1", font=('Arial', 15, 'bold'),
            bg=TABLE_PANEL_BG, fg=TEXT
        )
        self.cowboy_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.cowboy_cards_frame = tk.Frame(player1_frame, bg=TABLE_PANEL_BG)
        self.cowboy_cards_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        player2_frame = tk.Frame(table_canvas, bg=TABLE_PANEL_BG, bd=2, relief=tk.RAISED)
        player2_frame.place(x=265, y=45, width=210, height=185)
        self.bull_label = tk.Label(
            player2_frame, text="玩家2", font=('Arial', 15, 'bold'),
            bg=TABLE_PANEL_BG, fg=TEXT
        )
        self.bull_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.bull_cards_frame = tk.Frame(player2_frame, bg=TABLE_PANEL_BG)
        self.bull_cards_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        tk.Label(
            table_canvas, text="AUTO TEXAS HOLD'EM",
            font=('Arial', 23, 'bold'), bg=ROOT_BG, fg=GOLD
        ).place(x=250, y=270, anchor='center')
        tk.Label(
            table_canvas, text="玩家1  ·  公共牌  ·  玩家2",
            font=('Arial', 14, 'bold'), bg=ROOT_BG, fg=TEXT
        ).place(x=250, y=310, anchor='center')
        self.table_status_label = tk.Label(
            table_canvas, text="准备发牌",
            font=('Arial', 15, 'bold'), bg=ROOT_BG, fg='#FFD700'
        )
        self.table_status_label.place(x=250, y=355, anchor='center')

        community_frame = tk.Frame(table_canvas, bg=TABLE_PANEL_BG, bd=2, relief=tk.RAISED)
        community_frame.place(x=25, y=410, width=450, height=190)
        tk.Label(
            community_frame, text="公共牌", font=('Arial', 15, 'bold'),
            bg=TABLE_PANEL_BG, fg=TEXT
        ).pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg=TABLE_PANEL_BG)
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        # 右侧控制面板。
        right_panel = tk.Frame(main_frame, bg=ROOT_BG, width=620)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        right_panel.pack_propagate(False)

        info_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        info_card.pack(fill=tk.X, pady=(0, 3))
        header_info = tk.Frame(info_card, bg=HEADER_BG)
        header_info.pack(fill=tk.X)
        header_info.columnconfigure(0, weight=1)
        header_info.columnconfigure(1, weight=0)
        tk.Label(
            header_info, text="游戏信息", font=('Arial', 12, 'bold'),
            bg=HEADER_BG, fg=TITLE_FG
        ).grid(row=0, column=0, sticky="ew", padx=(72, 0), pady=3)
        self.back_button = tk.Button(
            header_info, text="", command=self.on_close,
            font=('Arial', 9, 'bold'), bg=HEADER_BG,
            activebackground=HEADER_BG,
            relief=tk.FLAT, width=0
        )
        self.back_button.grid(row=0, column=1, padx=5, pady=2)
        body_info = tk.Frame(info_card, bg=PANEL_BG)
        body_info.pack(fill=tk.X, padx=10, pady=6)
        for col in range(3):
            body_info.columnconfigure(col, weight=1, uniform='game_info')
        self.balance_label = tk.Label(body_info, text=f"余额: {format_money(self.balance)}", font=('Arial', 13, 'bold'), bg=PANEL_BG, fg='black', anchor='w')
        self.balance_label.grid(row=0, column=0, sticky='w')
        self.timer_label = tk.Label(body_info, text="下注时间: --", font=('Arial', 15, 'bold'), bg=PANEL_BG, fg='#D32F2F', anchor='center')
        self.timer_label.grid(row=0, column=1, sticky='ew')
        self.stage_label = tk.Label(body_info, text="准备发牌", font=('Arial', 13, 'bold'), bg=PANEL_BG, fg=ACCENT_GOLD, anchor='e')
        self.stage_label.grid(row=0, column=2, sticky='e')

        chip_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        chip_card.pack(fill=tk.X, pady=3)
        chip_header = tk.Frame(chip_card, bg=HEADER_BG)
        chip_header.pack(fill=tk.X)
        tk.Label(chip_header, text="筹码区", font=('Arial', 12, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=3)
        self.chip_container = tk.Frame(chip_card, bg=PANEL_BG)
        self.chip_container.pack(fill=tk.X, padx=8, pady=5)
        for i in range(8):
            self.chip_container.columnconfigure(i, weight=1)

        chip_configs = [
            ('$10', '#ffa500', 'black'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black'),
            ("$5K", '#ff0000', 'white'),
            ("$10K", '#00fbff', 'black'),
            ("$50K", '#00ffae', 'black')
        ]
        self.chip_buttons = []
        self.chip_texts = {}
        for i, (chip_text, bg_color, fg_color) in enumerate(chip_configs):
            cell = tk.Frame(self.chip_container, bg=PANEL_BG)
            cell.grid(row=0, column=i, padx=1, pady=1, sticky='nsew')
            chip_canvas = tk.Canvas(cell, width=48, height=48, bg=PANEL_BG, highlightthickness=0)
            chip_canvas.pack(anchor='center')
            chip_canvas.create_oval(2, 2, 46, 46, fill=bg_color, outline='black')
            chip_canvas.create_text(24, 24, text=chip_text, fill=fg_color, font=('Arial', 10, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=chip_text: self.select_chip(t))
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = chip_text
        self.select_chip("$10")

        limit_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_card.pack(fill=tk.X, pady=3)
        limit_header = tk.Frame(limit_card, bg=HEADER_BG)
        limit_header.pack(fill=tk.X)
        tk.Label(limit_header, text="下注上限", font=('Arial', 12, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=3)
        limit_body = tk.Frame(limit_card, bg=PANEL_BG)
        limit_body.pack(fill=tk.X, padx=10, pady=5)
        limit_table = tk.Frame(limit_body, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        limit_table.pack(fill=tk.X)
        limit_items = [("玩家1 / 玩家2赢", "$50,000"), ("平手", "$10,000"), ("其他下注", "$25,000")]
        for col, (title, amount) in enumerate(limit_items):
            limit_table.columnconfigure(col, weight=1, uniform='limits')
            tk.Label(limit_table, text=title, font=('Arial', 10, 'bold'), bg=PANEL_BG, fg=TITLE_FG, borderwidth=1, relief=tk.SOLID, pady=2).grid(row=0, column=col, sticky='nsew')
            tk.Label(limit_table, text=amount, font=('Arial', 11, 'bold'), bg=PANEL_BG, fg=ACCENT_GOLD, borderwidth=1, relief=tk.SOLID, pady=2).grid(row=1, column=col, sticky='nsew')

        bet_card = tk.Frame(right_panel, bg=PANEL_BG, bd=1, relief=tk.SOLID)
        bet_card.pack(fill=tk.BOTH, expand=True, pady=(3, 0))
        bet_header = tk.Frame(bet_card, bg=HEADER_BG)
        bet_header.pack(fill=tk.X)
        tk.Label(bet_header, text="下注区", font=('Arial', 12, 'bold'), bg=HEADER_BG, fg=TITLE_FG).pack(pady=3)

        bet_body = tk.Frame(bet_card, bg=TABLE_PANEL_BG, bd=2, relief=tk.RAISED)
        bet_body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        def create_bet_box(parent, title, bet_type, *, pack_opts=None, grid_opts=None, title_font=12,
                           display_font=12, display_height=1, title_anchor='w'):
            box = tk.Frame(parent, bg='#315546', bd=1, relief=tk.SOLID)
            if pack_opts is not None:
                box.pack(**pack_opts)
            elif grid_opts is not None:
                box.grid(**grid_opts)

            header = tk.Label(box, text=title, font=('Arial', title_font, 'bold'), bg='#345949', fg=TEXT,
                              anchor=title_anchor, padx=6, pady=2)
            header.pack(fill=tk.X)

            var = tk.StringVar(value="0")
            setattr(self, f"{bet_type}_var", var)
            display = tk.Label(box, textvariable=var, font=('Arial', display_font, 'bold'), bg='white',
                               fg='black', height=display_height, relief=tk.SUNKEN, bd=1)
            display.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            display.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
            display.bind("<Button-3>", lambda e, bt=bet_type: self.reset_bet_area(e, bt))
            self.bet_widgets[bet_type] = display
            return box

        top_row = tk.Frame(bet_body, bg=TABLE_PANEL_BG)
        top_row.pack(fill=tk.X, padx=8, pady=(8, 6))
        create_bet_box(top_row, "玩家1赢 (1X)", "cowboy_win", pack_opts={'side': tk.LEFT, 'fill': tk.BOTH, 'expand': True, 'padx': 4}, title_font=15, display_font=16, display_height=2)
        create_bet_box(top_row, "平手 (20X)", "tie", pack_opts={'side': tk.LEFT, 'fill': tk.BOTH, 'expand': True, 'padx': 4}, title_font=15, display_font=16, display_height=2, title_anchor='center')
        create_bet_box(top_row, "玩家2赢 (1X)", "bull_win", pack_opts={'side': tk.LEFT, 'fill': tk.BOTH, 'expand': True, 'padx': 4}, title_font=15, display_font=16, display_height=2)

        middle = tk.Frame(bet_body, bg=TABLE_PANEL_BG)
        middle.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        left_group = tk.Frame(middle, bg=TABLE_PANEL_BG)
        left_group.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))
        left_header = tk.Label(left_group, text="任一人手牌", font=('Arial', 13, 'bold'), bg=TABLE_PANEL_BG, fg=TEXT)
        left_header.pack(anchor='w', pady=(0, 4))
        create_bet_box(left_group, "顺子 / 同花 (1.66X)", "any_suited_connector", pack_opts={'fill': tk.X, 'pady': 3}, title_font=12, display_font=12)
        create_bet_box(left_group, "对子 (8.5X)", "any_pair", pack_opts={'fill': tk.X, 'pady': 3}, title_font=12, display_font=12)
        create_bet_box(left_group, "对子 A (100X)", "any_ace_pair", pack_opts={'fill': tk.X, 'pady': 3}, title_font=12, display_font=12)

        right_group = tk.Frame(middle, bg=TABLE_PANEL_BG)
        right_group.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0))
        right_header = tk.Label(right_group, text="赢家牌型", font=('Arial', 14, 'bold'), bg=TABLE_PANEL_BG, fg=TEXT)
        right_header.pack(anchor='w', pady=(0, 4))
        winner_grid = tk.Frame(right_group, bg=TABLE_PANEL_BG)
        winner_grid.pack(fill=tk.BOTH, expand=True)
        for col in range(2):
            winner_grid.columnconfigure(col, weight=1, uniform='winner_type')
        create_bet_box(winner_grid, "高牌 / 对子 (2.2X)", "high_card", grid_opts={'row': 0, 'column': 0, 'sticky': 'nsew', 'padx': 3, 'pady': 3}, title_font=11, display_font=11, display_height=1)
        create_bet_box(winner_grid, "两对 (3.1X)", "two_pair", grid_opts={'row': 0, 'column': 1, 'sticky': 'nsew', 'padx': 3, 'pady': 3}, title_font=11, display_font=11, display_height=1)
        create_bet_box(winner_grid, "三条 / 顺子 / 同花 (4.7X)", "three_kind_straight", grid_opts={'row': 1, 'column': 0, 'sticky': 'nsew', 'padx': 3, 'pady': 3}, title_font=11, display_font=11, display_height=1)
        create_bet_box(winner_grid, "葫芦 (20X)", "full_house", grid_opts={'row': 1, 'column': 1, 'sticky': 'nsew', 'padx': 3, 'pady': 3}, title_font=11, display_font=11, display_height=1)
        create_bet_box(winner_grid, "四条 / 同花顺 (248X)", "four_kind_flush", grid_opts={'row': 2, 'column': 0, 'columnspan': 2, 'sticky': 'nsew', 'padx': 3, 'pady': 3}, title_font=11, display_font=11, display_height=1)

        footer = tk.Frame(bet_body, bg=TABLE_PANEL_BG)
        footer.pack(fill=tk.X, padx=10, pady=(2, 8))

        row1 = tk.Frame(footer, bg=TABLE_PANEL_BG)
        row1.pack(fill=tk.X, pady=(0, 4))
        self.current_bet_label = tk.Label(row1, text="本局下注: $0.00", font=('Arial', 11, 'bold'), bg=TABLE_PANEL_BG, fg=TEXT)
        self.current_bet_label.pack(side=tk.LEFT)
        buttons_row1 = tk.Frame(row1, bg=TABLE_PANEL_BG)
        buttons_row1.pack(side=tk.RIGHT)
        self.info_button = tk.Button(buttons_row1, text="游戏规则", command=self.show_game_instructions, bg='#4B8BBE', fg='white', font=('Arial', 10, 'bold'), width=8)
        self.info_button.pack(side=tk.LEFT, padx=3)
        self.repeat_bet_btn = tk.Button(buttons_row1, text="重复下注", command=self.apply_last_bet, bg='#FFC107', fg='black', font=('Arial', 10, 'bold'), width=8, state=tk.DISABLED)
        self.repeat_bet_btn.pack(side=tk.LEFT, padx=3)

        row2 = tk.Frame(footer, bg=TABLE_PANEL_BG)
        row2.pack(fill=tk.X)
        self.last_win_label = tk.Label(row2, text="上局获胜: $0.00", font=('Arial', 11, 'bold'), bg=TABLE_PANEL_BG, fg='#FFD700')
        self.last_win_label.pack(side=tk.LEFT)
        buttons_row2 = tk.Frame(row2, bg=TABLE_PANEL_BG)
        buttons_row2.pack(side=tk.RIGHT)
        self.reset_button = tk.Button(buttons_row2, text="重设金额", command=self.reset_bets, bg='#F44336', fg='white', font=('Arial', 10, 'bold'), width=8)
        self.reset_button.pack(side=tk.LEFT, padx=3)
        self.start_button = tk.Button(buttons_row2, text="开始游戏", command=lambda: self.on_enter_key(None), bg='#4CAF50', fg='white', font=('Arial', 10, 'bold'), width=8)
        self.start_button.pack(side=tk.LEFT, padx=3)

        self.bet_vars = [getattr(self, f"{bet_type}_var") for bet_type in BET_PAYOUT]
        for var in self.bet_vars:
            var.trace_add('write', lambda *args: self.refresh_bet_info())
        self.refresh_bet_info()

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
    
    def apply_last_bet(self):
        """重复最近一局的下注；若余额不足则自动按当前最大可下注额回填。"""
        if self.game.stage != "betting" or not self.last_bet:
            return

        applied = {}
        remaining_balance = self.balance
        for bet_type in BET_PAYOUT:
            saved_amount = float(self.last_bet.get(bet_type, 0))
            if saved_amount <= 0:
                applied[bet_type] = 0
                continue
            amount = min(saved_amount, BET_LIMITS[bet_type], remaining_balance)
            applied[bet_type] = amount
            remaining_balance -= amount

        self.set_bet_amounts(applied)

    def update_balance(self):
        self.balance_label.config(text=f"余额: {format_money(self.balance)}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
        if callable(self.on_balance_change):
            self.on_balance_change(float(self.balance))
    
    def start_game(self):
        """结束下注阶段，扣除下注并翻开其余牌。"""
        if self.destroyed or self.game.stage != "betting":
            return

        self.enter_enabled = False
        try:
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

            for bet_type, amount in bet_amounts.items():
                if amount > BET_LIMITS[bet_type]:
                    messagebox.showerror(
                        "下注限制",
                        f"{bet_type} 的下注超过上限 {format_money(BET_LIMITS[bet_type])}"
                    )
                    return

            total_bet = sum(bet_amounts.values())
            if total_bet > self.balance:
                messagebox.showwarning("余额不足", "下注金额已超过余额，请调整后再开始。")
                self.set_bet_amounts(bet_amounts)
                self.bet_start_time = time.time()
                self.enter_enabled = True
                self.auto_start_timer = self.after(1000, self.update_timer)
                return

            if self.auto_start_timer:
                self.after_cancel(self.auto_start_timer)
                self.auto_start_timer = None

            if total_bet > 0:
                self.last_bet = bet_amounts.copy()
            self.balance -= total_bet
            self.update_balance()
            self.game.bets = bet_amounts
            self.refresh_bet_info()
            self.game.stage = "showdown"

            self.timer_label.config(text="下注时间: 0秒")
            self.stage_label.config(text="开牌中")
            self.table_status_label.config(text="下注结束，正在开牌...")
            self._set_betting_controls_enabled(False)
            self.after(300, self.reveal_all_cards)

        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")

    def animate_deal(self):
        if self.destroyed:
            return

        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(300, self.reveal_first_community_card)
            return

        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)

        if card_id.startswith("cowboy"):
            frame = self.cowboy_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.cowboy_hole[idx]
        elif card_id.startswith("bull"):
            frame = self.bull_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.bull_hole[idx]
        else:
            frame = self.community_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.community_cards[idx]

        card_label = tk.Label(frame, image=self.back_image, bg=TABLE_PANEL_BG)
        cx, cy = self.card_positions[card_id]["current"]
        card_label.place(x=cx, y=cy + 20, width=CARD_SIZE[0], height=CARD_SIZE[1])
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        self.active_card_labels.append(card_label)
        self.animate_card_move(card_label)

    def animate_card_move(self, card_label):
        if self.destroyed:
            return
        if not hasattr(card_label, "target_pos") or card_label not in self.active_card_labels:
            return

        try:
            cx, cy = card_label.winfo_x(), card_label.winfo_y()
            tx, ty = card_label.target_pos
            dx, dy = tx - cx, ty - cy
            distance = math.hypot(dx, dy)
            if distance < 5:
                card_label.place(x=tx, y=ty, width=CARD_SIZE[0], height=CARD_SIZE[1])
                card_label.is_moving = False
                self.after(20, self.animate_deal)
                return

            card_label.place(
                x=cx + dx * 0.2, y=cy + dy * 0.2,
                width=CARD_SIZE[0], height=CARD_SIZE[1]
            )
            self.after(20, lambda: self.animate_card_move(card_label))
        except tk.TclError:
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)

    def _set_betting_controls_enabled(self, enabled):
        """统一启用或禁用下注格、筹码与底部操作按钮。"""
        for bet_type, widget in self.bet_widgets.items():
            widget.unbind("<Button-1>")
            widget.unbind("<Button-3>")
            if enabled:
                widget.bind("<Button-1>", lambda e, bt=bet_type: self.add_chip_to_bet(bt))
                widget.bind("<Button-3>", lambda e, bt=bet_type: self.reset_bet_area(e, bt))
        for chip in self.chip_buttons:
            chip.unbind("<Button-1>")
            if enabled:
                chip_text = self.chip_texts[chip]
                chip.bind("<Button-1>", lambda e, t=chip_text: self.select_chip(t))

        button_state = tk.NORMAL if enabled else tk.DISABLED
        if hasattr(self, 'reset_button'):
            self.reset_button.config(state=button_state)
        if hasattr(self, 'start_button'):
            self.start_button.config(state=button_state)
        self._update_repeat_button_state()

    def _find_card_label(self, card_id):
        for label in self.active_card_labels:
            if getattr(label, 'card_id', None) == card_id and label.winfo_exists():
                return label
        return None

    def reveal_first_community_card(self):
        """发牌完成后只翻开第0张公共牌，再开放下注。"""
        if self.destroyed:
            return
        first = self._find_card_label("community_0")
        if first is None:
            self.begin_betting_phase()
            return
        self.stage_label.config(text="准备下注")
        self.table_status_label.config(text="翻开第1张公共牌")
        self.game.cards_revealed["community"][0] = True
        self.flip_card_animation(first)
        self.after(550, self.begin_betting_phase)

    def begin_betting_phase(self):
        if self.destroyed:
            return
        self.game.stage = "betting"
        self.stage_label.config(text="下注中")
        self.table_status_label.config(text="首张公共牌已开，请下注")
        self._set_betting_controls_enabled(True)
        self._update_repeat_button_state()
        self.bet_start_time = time.time()
        self.enter_enabled = True
        self.timer_label.config(text="下注时间: 15秒")
        if self.auto_start_timer:
            self.after_cancel(self.auto_start_timer)
        self.auto_start_timer = self.after(1000, self.update_timer)

    def reveal_all_cards(self):
        """先翻开玩家1和玩家2手牌，再翻开剩余4张公共牌，最后更新标签。"""
        if self.destroyed:
            return

        self.stage_label.config(text="开牌中")
        self.table_status_label.config(text="先翻开玩家手牌")

        hole_labels = []
        for i in range(2):
            lbl = self._find_card_label(f"cowboy_{i}")
            if lbl is not None and not lbl.is_face_up:
                self.game.cards_revealed["cowboy"][i] = True
                hole_labels.append(lbl)
        for i in range(2):
            lbl = self._find_card_label(f"bull_{i}")
            if lbl is not None and not lbl.is_face_up:
                self.game.cards_revealed["bull"][i] = True
                hole_labels.append(lbl)

        for lbl in hole_labels:
            self.flip_card_animation(lbl)

        self.after(700, lambda: self.reveal_remaining_community_cards(1))

    def reveal_remaining_community_cards(self, index):
        if self.destroyed:
            return
        if index >= 5:
            self.after(450, self.update_hand_labels)
            self.after(1500, self.settle_game)
            return

        self.table_status_label.config(text=f"翻开第 {index + 1} 张至第 5 张公共牌")
        lbl = self._find_card_label(f"community_{index}")
        if lbl is not None and not lbl.is_face_up:
            self.game.cards_revealed["community"][index] = True
            self.flip_card_animation(lbl)
        self.after(220, lambda: self.reveal_remaining_community_cards(index + 1))

    def flip_card_animation(self, card_label):
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.animate_flip(card_label, front_img, 0)

    def animate_flip(self, card_label, front_img, step):
        """Caribbean Stud Poker 同款：PIL逐帧缩窄背面，再展开正面。"""
        if self.destroyed or not card_label.winfo_exists():
            return

        steps = 12
        orig_w, orig_h = CARD_SIZE
        if step > steps:
            card_label.is_face_up = True
            tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
            card_label.place(x=tx, y=ty, width=orig_w, height=orig_h)
            card_label.config(image=front_img)
            if hasattr(self, '_temp_flip_images'):
                self._temp_flip_images.pop(card_label, None)
            return

        half = steps // 2
        if step <= half:
            ratio = 1 - step / float(half)
            pil_img = self.original_images.get("back")
        else:
            ratio = (step - half) / float(half)
            card = card_label.card
            pil_img = self.original_images.get((card.suit, card.rank))

        width = max(1, int(orig_w * ratio))
        if pil_img is None:
            pil_img = Image.new('RGB', (orig_w, orig_h), 'gray')
        scaled = pil_img.resize((width, orig_h), Image.LANCZOS)
        scaled_img = ImageTk.PhotoImage(scaled)
        if not hasattr(self, '_temp_flip_images'):
            self._temp_flip_images = {}
        self._temp_flip_images[card_label] = scaled_img

        tx, ty = card_label.target_pos if hasattr(card_label, 'target_pos') else (0, 0)
        offset = (orig_w - width) // 2
        card_label.config(image=scaled_img)
        card_label.place(x=tx + offset, y=ty, width=width, height=orig_h)
        self.after(30, lambda: self.animate_flip(card_label, front_img, step + 1))

    def update_hand_labels(self):
        """开牌完成后显示玩家1和玩家2的最终最佳五张牌型。"""
        all_revealed = (
            all(self.game.cards_revealed["cowboy"]) and
            all(self.game.cards_revealed["bull"]) and
            all(self.game.cards_revealed["community"])
        )
        if not all_revealed:
            self.cowboy_label.config(text="玩家1")
            self.bull_label.config(text="玩家2")
            return

        cowboy_eval, _, bull_eval, _ = self.game.evaluate_hands()
        self.cowboy_label.config(text=f"玩家1 - {HAND_RANK_NAMES[cowboy_eval[0]]}")
        self.bull_label.config(text=f"玩家2 - {HAND_RANK_NAMES[bull_eval[0]]}")

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
        
        self._set_betting_controls_enabled(False)

        # 显示结果
        result_text = f"游戏结束! {'玩家1' if winner == 'cowboy' else '玩家2' if winner == 'bull' else '平手'}获胜"
        if hasattr(self, "stage_label"):
            self.stage_label.config(text="结算完成")
        if hasattr(self, "table_status_label"):
            self.table_status_label.config(text=result_text)
        
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
        
        # 结算时下注格会显示赔付金额，但“本局下注”保持原下注总额。
        self.freeze_current_bet_display = True

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
        if hasattr(self, "stage_label"):
            self.stage_label.config(text="收牌中")
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
        zero_bets = {bet_type: 0 for bet_type in BET_PAYOUT}
        self.set_bet_amounts(zero_bets)

        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        for widget in self.bet_widgets.values():
            widget.config(bg='#FFCDD2')
        self.after(500, lambda: [w.config(bg='white') for w in self.bet_widgets.values()])

    def reset_game(self, auto_reset=False):
        """初始化下一局：先发全部暗牌，翻开首张公共牌后才开始下注。"""
        if self.destroyed:
            return

        self._load_assets()
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except tk.TclError:
                pass
            self.auto_reset_timer = None
        if self.auto_start_timer:
            try:
                self.after_cancel(self.auto_start_timer)
            except tk.TclError:
                pass
            self.auto_start_timer = None

        self.game.reset_game()
        self.game.deal_initial()
        self.game.stage = "dealing"
        self.enter_enabled = False

        # 新一局恢复“本局下注”的正常刷新。
        self.freeze_current_bet_display = False
        self.reset_bets()
        self.active_card_labels = []
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self._temp_flip_images = {}

        for frame in (self.cowboy_cards_frame, self.bull_cards_frame, self.community_cards_frame):
            for widget in frame.winfo_children():
                widget.destroy()

        self.cowboy_label.config(text="玩家1")
        self.bull_label.config(text="玩家2")
        self.stage_label.config(text="发牌中")
        self.timer_label.config(text="下注时间: --")
        self.table_status_label.config(text="先发暗牌，再翻开首张公共牌")
        self._set_betting_controls_enabled(False)

        # 按需求的可视发牌顺序：公共牌5张、玩家1两张、玩家2两张。
        for i in range(5):
            card_id = f"community_{i}"
            self.card_positions[card_id] = {
                "current": (40, 35),
                "target": (i * COMMUNITY_CARD_SPACING, 0)
            }
            self.animation_queue.append(card_id)
        for i in range(2):
            card_id = f"cowboy_{i}"
            self.card_positions[card_id] = {
                "current": (40, 35),
                "target": (i * HOLE_CARD_SPACING, 0)
            }
            self.animation_queue.append(card_id)
        for i in range(2):
            card_id = f"bull_{i}"
            self.card_positions[card_id] = {
                "current": (40, 35),
                "target": (i * HOLE_CARD_SPACING, 0)
            }
            self.animation_queue.append(card_id)

        self.after(150, self.animate_deal)

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
                text_width, text_height = measure_text(draw, text, font)
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

def main(initial_balance=10000, username="Guest", *, parent=None, balance=None, user=None,
         on_back=None, on_balance_change=None):
    """
    Parent 嵌入接口：
        main(parent=..., balance=..., user=..., on_back=..., on_balance_change=...)

    未传 parent 时仍可独立运行。
    """
    actual_balance = float(initial_balance if balance is None else balance)
    actual_user = username if user is None else user

    if parent is not None:
        page = TexasHoldemGUI(
            parent,
            actual_balance,
            actual_user,
            on_back=on_back,
            on_balance_change=on_balance_change,
        )
        page.reset_game()
        return page

    root = tk.Tk()
    root.title("德州扑克双人对决")
    root.geometry("1150x750+50+10")
    root.resizable(False, False)
    root.configure(bg=ROOT_BG)

    page = TexasHoldemGUI(root, actual_balance, actual_user)
    page.pack(fill="both", expand=True)
    page.reset_game()

    def close_standalone(final_balance=None):
        try:
            update_balance_in_json(page.username, page.balance)
        except Exception:
            pass
        page._cancel_timers()
        page._unbind_return_key()
        root.destroy()

    page.on_back = close_standalone
    root.protocol("WM_DELETE_WINDOW", page.on_close)
    root.mainloop()
    return page.balance


if __name__ == "__main__":
    final_balance = main()
    print(f"最终余额: {final_balance}")