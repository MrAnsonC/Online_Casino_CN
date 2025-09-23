import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
from collections import Counter
from itertools import combinations
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
    9: '皇家顺', 8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花',
    4: '顺子', 3: '三条', 2: '两对', 1: '对子', 0: '高牌'
}

# 支付表
BLIND_PAYOUT = {
    9: 500,  # 皇家顺 500:1
    8: 50,   # 同花顺 50:1
    7: 10,   # 四条 10:1
    6: 3,    # 葫芦 3:1
    5: 1.5,  # 同花 3:2 (1.5)
    4: 1     # 顺子 1:1
}

TRIPS_PAYOUT = {
    9: 50,   # 皇家顺 50:1
    8: 40,   # 同花顺 40:1
    7: 30,   # 四条 30:1
    6: 8,    # 葫芦 8:1
    5: 6,    # 同花 6:1
    4: 5,    # 顺子 5:1
    3: 3     # 三条 3:1
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

# Jackpot 文件加载与保存
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    default_progressive = 327301.26
    # 文件不存在时使用默认奖池
    if not os.path.exists(path):
        return True, default_progressive
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'UTH':
                    return False, float(item.get('jackpot', default_progressive))
    except Exception:
        return True, default_progressive
    # 未找到 UTH 条目时也使用默认
    return True, default_progressive

def save_progressive(jackpot):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    data = []
    # 如果文件存在，读取原有数据
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    
    # 查找是否已有UTH的记录
    found = False
    for item in data:
        if item.get('Games') == 'UTH':
            item['jackpot'] = jackpot
            found = True
            break
    
    if not found:
        data.append({"Games": "UTH", "jackpot": jackpot})
    
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

class UTHGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []
        self.player_hole = []
        self.dealer_hole = []
        self.ante = 0
        self.blind = 0
        self.trips = 0
        self.play_bet = 0
        self.participate_jackpot = False
        self.stage = "pre_flop"  # pre_flop, flop, river, showdown
        self.folded = False
        self.cards_revealed = {
            "player": [False, False],
            "dealer": [False, False],
            "community": [False, False, False, False, False]
        }
        # 加载Jackpot金额
        self.jackpot_initial, self.progressive_amount = load_jackpot()
        # 新增：记录牌序信息
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence
    
    def deal_initial(self):
        """发初始牌：玩家2张，庄家2张，公共牌5张"""
        self.community_cards = self.deck.deal(5)
        self.player_hole = self.deck.deal(2)
        self.dealer_hole = self.deck.deal(2)
    
    def evaluate_hands(self):
        """评估玩家和庄家的手牌"""
        player_cards = self.player_hole + self.community_cards
        dealer_cards = self.dealer_hole + self.community_cards
        
        player_eval, player_best = find_best_5(player_cards)
        dealer_eval, dealer_best = find_best_5(dealer_cards)
        
        return player_eval, player_best, dealer_eval, dealer_best
    
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

class UTHGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("终极德州扑克")
        self.geometry("1150x735+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = UTHGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []  # 追踪所有活动中的卡片标签
        self.selected_chip = None  # 当前选中的筹码
        self.chip_buttons = []  # 筹码按钮列表
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.win_details = {
            "ante": 0,
            "blind": 0,
            "bet": 0,
            "trips": 0,
            "jackpot": 0
        }
        self.bet_widgets = {}  # 存储下注显示控件
        self.last_jackpot_selection = False  # 记录上局Jackpot选择
        self.auto_showdown = False  # 自动摊牌标志
        
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_game_instructions(self):
        """显示游戏规则说明"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("游戏规则")
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
        终极德州扑克 游戏规则

        1. 游戏开始前下注:
           - 加注: 可选下注 - 下注底注的3倍/4倍或取消下注
           - 底注: 基础下注
           - 盲注: 自动等于底注
           - 三条注: 可选副注
           - 累进大奖: 可选参与($20)

        2. 游戏流程:
           a. 翻牌前:
               - 查看手牌后选择:
                 * 过牌: 进入翻牌圈
                 * 下注3倍: 下注底注的3倍到加注
                 * 下注4倍: 下注底注的4倍到加注

           b. 翻牌圈:
               - 查看前三张公共牌后选择:
                 * 过牌: 进入河牌圈
                 * 下注2倍: 下注底注的2倍到加注

           c. 河牌圈:
               - 查看所有公共牌后选择:
                 * 弃牌: 放弃所有的下注(除三条注和累进大奖)
                 * 下注1倍: 下注底注的1倍到加注

        3. 摊牌:
           - 比较玩家和庄家的最佳五张牌
           - 结算所有下注

        4. 支付表:
           - 底注:
             * 玩家赢: 支付2倍
             * 平局: 退还
             * 庄家高牌: 退还
             * 其他情况: 输掉

           - 加注:
             * 玩家赢: 支付2倍
             * 平局: 退还
             * 其他情况: 输掉
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
        
        # 赔率表
        tk.Label(
            content_frame, 
            text="赔率表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        odds_frame = tk.Frame(content_frame, bg='#F0F0F0')
        odds_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "盲注", "三条注", "累进大奖#"]
        odds_data = [
            ("皇家顺", "500:1", "50:1", "100%累进大奖/$350,000"),
            ("同花顺", "50:1", "40:1", "10%累进大奖/$35,000"),
            ("四条", "10:1", "30:1", "$25,000"),
            ("葫芦", "3:1", "8:1", "$4000"),
            ("同花", "1.5:1", "6:1", "$3000"),
            ("顺子", "1:1", "5:1", "-"),
            ("三条", "-", "3:1", "-")
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
        
        # 注释
        notes = """
        注: 
        # 玩家的牌和头3张公共牌组成牌型才获胜
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
        
    def on_close(self):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
        
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
        
        # 加载扑克牌图片 - 修复这里
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
                            font = ImageFont.truetype("arial.ttf", 20)
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
                        font = ImageFont.truetype("arial.ttf", 20)
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
            
        # 获取筹码金额 - 处理K表示1000的情况
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            # 处理带K的筹码，如1K或2.5K
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        
        # 更新对应的下注变量
        if bet_type == "ante":
            current = float(self.ante_var.get())
            max_bet = 10000  # Ante最大下注限制
            
            # 检查是否已超过上限
            if current >= max_bet:
                messagebox.showwarning("下注限制", "底注已满，不能再下注！")
                return
            
            # 检查下注后是否会超过上限
            if current + chip_value > max_bet:
                allowed_amount = max_bet - current
                if allowed_amount > 0:
                    # 自动调整到下注上限
                    chip_value = allowed_amount
                    messagebox.showwarning("下注限制", f"底注已达上限，自动调整为 {int(allowed_amount)}")
                else:
                    messagebox.showwarning("下注限制", "底注已满，不能再下注！")
                    return
            
            self.ante_var.set(str(int(current + chip_value)))
            # Blind 自动等于 Ante
            self.blind_var.set(self.ante_var.get())
            
            # 检查Blind是否超过上限
            blind_current = float(self.blind_var.get())
            blind_max_bet = 10000  # Blind最大下注限制
            
            if blind_current > blind_max_bet:
                # 如果Blind超过上限，调整Ante和Blind
                self.ante_var.set(str(blind_max_bet))
                self.blind_var.set(str(blind_max_bet))
                messagebox.showwarning("下注限制", f"盲注上限为{blind_max_bet}，已自动调整底注和盲注")
                
        elif bet_type == "trips":
            current = float(self.trips_var.get())
            max_bet = 2500  # Trips最大下注限制
            
            # 检查是否已超过上限
            if current >= max_bet:
                messagebox.showwarning("下注限制", "三条注已满，不能再下注！")
                return
            
            # 检查下注后是否会超过上限
            if current + chip_value > max_bet:
                allowed_amount = max_bet - current
                if allowed_amount > 0:
                    # 自动调整到下注上限
                    chip_value = allowed_amount
                    messagebox.showwarning("下注限制", f"三条注已达上限，自动调整为 {int(allowed_amount)}")
                else:
                    messagebox.showwarning("下注限制", "三条注已满，不能再下注！")
                    return
            
            self.trips_var.set(str(int(current + chip_value)))
    
    def cycle_bet_amount(self, event):
        """循环设置Bet下注金额：0 -> 3倍Ante -> 4倍Ante -> 0"""
        # 获取当前Ante金额
        try:
            ante = int(self.ante_var.get())
        except ValueError:
            ante = 0
        
        # 如果Ante为0，则无法设置Bet，直接返回
        if ante == 0:
            return
        
        # 获取当前Bet金额，如果为空或无效则视为0
        try:
            current_bet = int(self.bet_var.get())
        except ValueError:
            current_bet = 0
        
        # 确定下一个Bet金额
        if current_bet == 0:
            new_bet = ante * 3
        elif current_bet == ante * 3:
            new_bet = ante * 4
        else:
            new_bet = 0
        
        # 更新Bet显示
        self.bet_var.set(str(new_bet))
    
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
        dealer_frame.place(x=150, y=20, width=400, height=210)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 公共牌区域 - 固定高度200
        community_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        community_frame.place(x=50, y=250, width=600, height=210)
        community_label = tk.Label(community_frame, text="公共牌", font=('Arial', 18), bg='#2a4a3c', fg='white')
        community_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg='#2a4a3c')
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 玩家区域 - 固定高度200
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=150, y=480, width=400, height=210)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=300, padx=10, pady=2)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=10)
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 18),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.stage_label = tk.Label(
            info_frame, 
            text="翻牌前",
            font=('Arial', 18, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=10)
        
        # Progressive显示区域 - 修改后的代码
        progressive_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        progressive_frame.pack(fill=tk.X, pady=5)

        # 使用网格布局确保标签在左边，金额在中间
        progressive_frame.columnconfigure(0, weight=1)  # 标签列
        progressive_frame.columnconfigure(1, weight=2)  # 金额列（更宽）
        progressive_frame.columnconfigure(2, weight=1)  # 空白列（平衡布局）

        # 标签放在左边
        progressive_label = tk.Label(progressive_frame, text="累进大奖:", 
                                font=('Arial', 18), bg='#2a4a3c', fg='gold')
        progressive_label.grid(row=0, column=0, sticky='w', padx=(10, 0), pady=5)

        # 金额放在中间 - 使用StringVar
        self.progressive_amount_var = tk.StringVar()
        self.progressive_amount_var.set(f"${self.game.progressive_amount:.2f}")
        self.progressive_display = tk.Label(progressive_frame, textvariable=self.progressive_amount_var, 
                                    font=('Arial', 22, 'bold'), bg='#2a4a3c', fg='gold')
        self.progressive_display.grid(row=0, column=1, sticky='w', pady=3)
        
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
            chip_canvas = tk.Canvas(chip_row, width=55, height=55, bg='#2a4a3c', highlightthickness=0)
            
            # 创建圆形（尺寸调整为51x51，在55x55画布中居中）
            chip_canvas.create_oval(2, 2, 54, 54, fill=bg_color, outline='black')
            
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
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="底注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(header_frame, text="边注最高", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='white', width=10).pack(side=tk.LEFT, expand=True)
        
        # 数值行
        value_frame = tk.Frame(minmax_frame, bg='#2a4a3c')
        value_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        tk.Label(value_frame, text="$10", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$10,000", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        tk.Label(value_frame, text="$2,500", font=('Arial', 12, 'bold'), 
                bg='#2a4a3c', fg='#FFD700', width=10).pack(side=tk.LEFT, expand=True)
        
        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=5)

        # 第一行：Progressive选项
        progressive_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        progressive_frame.pack(fill=tk.X, padx=20, pady=5)

        self.progressive_var = tk.IntVar()
        self.progressive_cb = tk.Checkbutton(
            progressive_frame, text="累进大奖 ($20.00)", 
            variable=self.progressive_var, font=('Arial', 14),
            bg='#2a4a3c', fg='white', selectcolor='#35654d'
        )
        self.progressive_cb.pack(side=tk.LEFT)
        
        # 第二行：Trips区域
        trips_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        trips_frame.pack(fill=tk.X, padx=20, pady=5)

        trips_label = tk.Label(trips_frame, text="三条注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        trips_label.pack(side=tk.LEFT)

        self.trips_var = tk.StringVar(value="0")
        self.trips_display = tk.Label(trips_frame, textvariable=self.trips_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.trips_display.pack(side=tk.LEFT, padx=5)
        self.trips_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("trips"))
        self.bet_widgets["trips"] = self.trips_display
        
        # 第三行：Ante和Blind区域（等式形式）
        ante_blind_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        ante_blind_frame.pack(fill=tk.X, padx=20, pady=5)

        # Ante 显示区域
        ante_label = tk.Label(ante_blind_frame, text="    底注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        ante_label.pack(side=tk.LEFT)

        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(ante_blind_frame, textvariable=self.ante_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
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
        blind_label = tk.Label(ante_blind_frame, text=": 盲注", font=('Arial', 14), bg='#2a4a3c', fg='white')
        blind_label.pack(side=tk.LEFT, padx=5)
        
        # 新增Bet行
        bet_play_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        bet_play_frame.pack(fill=tk.X, padx=20, pady=5)
        
        bet_play_label = tk.Label(bet_play_frame, text="    加注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        bet_play_label.pack(side=tk.LEFT)
        
        self.bet_var = tk.StringVar(value="0")
        self.bet_display = tk.Label(bet_play_frame, textvariable=self.bet_var, font=('Arial', 14), 
                                   bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.bet_display.pack(side=tk.LEFT, padx=5)
        self.bet_display.bind("<Button-1>", self.cycle_bet_amount)  # 绑定点击事件
        self.bet_widgets["bet"] = self.bet_display

        # 游戏操作按钮框架 - 用于放置所有操作按钮
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X, pady=5)

        # 创建一个框架来容纳重置按钮和开始游戏按钮
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

        # 添加"重设金额"按钮
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重设金额", 
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
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 状态信息 - 调整高度属性以匹配开始游戏后的状态
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 14, 'bold'), bg='#2a4a3c', fg='white', height=1  # 这里将height从1改为2
        )
        self.status_label.pack(pady=5, fill=tk.X, anchor='n')

        # 本局下注和上局获胜金额显示
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(fill=tk.X, pady=20)
        
        # 本局下注金额
        self.current_bet_label = tk.Label(
            bet_info_frame, text="本局下注: $0.00", 
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        
        # 上局获胜金额
        last_win_row = tk.Frame(bet_info_frame, bg='#2a4a3c')
        last_win_row.pack(fill=tk.X, padx=10, pady=5)

        self.last_win_label = tk.Label(
            last_win_row, text="上局获胜: $0.00", 
            font=('Arial', 14), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(side=tk.LEFT)

        self.info_button = tk.Button(
            last_win_row,
            text="ℹ️",
            command=self.show_game_instructions,
            bg='#4B8BBE',
            fg='white',
            font=('Arial', 12),
            width=2,
            relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)
    
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
        community_revealed_count = sum(self.game.cards_revealed["community"])
        player_eval = self.game.evaluate_current_hand(self.game.player_hole, community_revealed_count)
        player_hand_name = HAND_RANK_NAMES[player_eval[0]] if player_eval else ""
        self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")
        
        # 计算庄家当前牌型（只有在摊牌或弃牌时，或者庄家牌已经翻开）
        if self.game.stage == "showdown" or self.game.folded or any(self.game.cards_revealed["dealer"]):
            dealer_eval = self.game.evaluate_current_hand(self.game.dealer_hole, community_revealed_count)
            dealer_hand_name = HAND_RANK_NAMES[dealer_eval[0]] if dealer_eval else ""
            self.dealer_label.config(text=f"庄家 - {dealer_hand_name}" if dealer_hand_name else "庄家")
        else:
            # 在游戏过程中，庄家牌未翻开，不显示牌型
            self.dealer_label.config(text="庄家")
    
    def disable_action_buttons(self):
        """禁用所有操作按钮"""
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            if widget.winfo_exists():
                widget.config(state=tk.DISABLED)
    
    def enable_action_buttons(self):
        """启用所有操作按钮"""
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            if widget.winfo_exists():
                widget.config(state=tk.NORMAL)
    
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.blind = int(self.blind_var.get())
            self.trips = int(self.trips_var.get())
            self.participate_jackpot = bool(self.progressive_var.get())
            self.last_jackpot_selection = bool(self.progressive_var.get())  # 记录当前选择
            # 读取Bet金额
            self.bet = int(self.bet_var.get())   # 如果为空字符串，会触发ValueError，所以下面捕获异常
        except ValueError:
            # 如果转换失败，将Bet设为0
            self.bet = 0
            
        # 检查Ante至少5块
        if self.ante < 5:
            messagebox.showerror("错误", "底注至少需要10块")
            return
        
        # 计算总下注（包括Bet）
        total_bet = self.ante + self.blind + self.trips + self.bet
        if self.participate_jackpot:
            total_bet += 20
            
        # 检查余额是否足够（包括Bet）
        if total_bet > self.balance:
            messagebox.showerror("错误", "余额不足以支付所有下注！")
            return
            
        self.balance -= total_bet
        self.update_balance()
        
        # 更新本局下注显示
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        # 如果Play Bet不为0，禁用重设金额和开始游戏按钮
        if self.bet > 0:
            self.reset_bets_button.config(state=tk.DISABLED)
            self.start_button.config(state=tk.DISABLED)
        
        self.game.reset_game()
        self.game.deal_initial()
        self.game.ante = self.ante
        self.game.blind = self.blind
        self.game.trips = self.trips
        self.game.participate_jackpot = self.participate_jackpot
        
        # 设置自动摊牌标志
        self.auto_showdown = (self.bet > 0)
        
        # 清除所有卡片
        for widget in self.dealer_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.community_cards_frame.winfo_children():
            widget.destroy()
        for widget in self.player_cards_frame.winfo_children():
            widget.destroy()
        
        # 重置动画状态
        self.animation_queue = []
        self.animation_in_progress = False
        self.active_card_labels = []
        
        # 初始化卡片位置
        self.card_positions = {}
        
        # 添加所有卡片到动画队列
        self.animation_queue = []
        
        # 公共牌 - 放置在中心位置
        for i in range(5):
            card_id = f"community_{i}"
            self.card_positions[card_id] = {
                "current": (50, 50), 
                "target": (i * 110, 0)  # 水平排列
            }
            self.animation_queue.append(card_id)
        
        # 玩家牌 - 放置在中心位置
        for i in range(2):
            card_id = f"player_{i}"
            self.card_positions[card_id] = {
                "current": (50, 50), 
                "target": (i * 150, 0)  # 水平排列
            }
            self.animation_queue.append(card_id)
        
        # 庄家牌 - 放置在中心位置
        for i in range(2):
            card_id = f"dealer_{i}"
            self.card_positions[card_id] = {
                "current": (50, 50), 
                "target": (i * 150, 0)  # 水平排列
            }
            self.animation_queue.append(card_id)
        
        # 开始动画
        self.animate_deal()
        
        # 更新游戏状态
        self.stage_label.config(text="翻牌前")
        
        # 如果Bet有下注金额，则直接进入摊牌阶段
        if self.auto_showdown:
            # 记录Play Bet
            self.game.play_bet = self.bet
            # 设置游戏阶段为摊牌
            self.game.stage = "showdown"
            # 更新状态标签
            self.status_label.config(text=f"已下注: ${self.bet}，将在牌到位后自动摊牌。")
            # 不创建操作按钮
            return
        
        # 创建操作按钮 - 替换开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        buttons_container = tk.Frame(self.action_frame, bg='#2a4a3c')
        buttons_container.pack(pady=5)

        self.check_button = tk.Button(
            buttons_container, text="过牌", 
            command=lambda: self.play_action(0), 
            font=('Arial', 14), bg='#2196F3', fg='white', width=9,
            state=tk.DISABLED
        )
        self.check_button.pack(side=tk.LEFT, padx=9)
            
        self.bet_3x_button = tk.Button(
            buttons_container, text="下注3倍", 
            command=lambda: self.play_action(3), 
            font=('Arial', 14), bg='#FF9800', fg='white', width=9,
            state=tk.DISABLED
        )
        self.bet_3x_button.pack(side=tk.LEFT, padx=9)
            
        self.bet_4x_button = tk.Button(
            buttons_container, text="下注4倍", 
            command=lambda: self.play_action(4), 
            font=('Arial', 14), bg='#F44336', fg='white', width=9,
            state=tk.DISABLED
        )
        self.bet_4x_button.pack(side=tk.LEFT, padx=9)
        
        # 禁用下注区域
        self.ante_display.unbind("<Button-1>")
        self.trips_display.unbind("<Button-1>")
        self.bet_display.unbind("<Button-1>")
        self.progressive_cb.config(state=tk.DISABLED)
        for chip in self.chip_buttons:
            chip.unbind("<Button-1>")
    
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            # 发牌动画完成后
            if self.auto_showdown:
                # 自动摊牌：翻开所有牌
                self.after(500, self.show_showdown)
            else:
                # 正常流程：翻开玩家牌
                self.after(500, self.reveal_player_cards)
            return
            
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        
        # 创建卡片标签
        if card_id.startswith("community"):
            frame = self.community_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.community_cards[idx] if idx < len(self.game.community_cards) else None
        elif card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hole[idx] if idx < len(self.game.player_hole) else None
        elif card_id.startswith("dealer"):
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hole[idx] if idx < len(self.game.dealer_hole) else None
        
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
    
    def reveal_player_cards(self):
        """翻开玩家牌（带动画）"""
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记玩家牌已翻开
                self.game.cards_revealed["player"][i] = True
        
        # 更新玩家牌型
        self.update_hand_labels()
        
        # 1.5秒后启用翻牌前按钮
        self.after(1500, self.enable_preflop_buttons)
    
    def reveal_flop(self):
        """翻开翻牌圈的三张公共牌（带动画）"""
        # 安全地获取社区牌框架中的卡片
        self.flop_revealed = 0
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up and i < 3:
                self.flip_card_animation(card_label)
                # 标记公共牌已翻开
                self.game.cards_revealed["community"][i] = True
                self.flop_revealed += 1
        
        # 更新玩家牌型
        self.update_hand_labels()
        
        # 2秒后启用翻牌圈按钮
        self.after(2000, self.enable_flop_buttons)

    def reveal_turn_river(self):
        """翻开转牌和河牌（带动画）"""
        # 安全地获取社区牌框架中的卡片
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up and i >= 3:
                self.flip_card_animation(card_label)
                # 标记公共牌已翻开
                self.game.cards_revealed["community"][i] = True
        
        # 更新玩家牌型
        self.update_hand_labels()
        
        # 1.5秒后启用河牌圈按钮
        self.after(1500, self.enable_river_buttons)
    
    def reveal_dealer_cards(self):
        """翻开庄家牌（带动画）"""
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记庄家牌已翻开
                self.game.cards_revealed["dealer"][i] = True
        
        # 更新庄家牌型
        self.update_hand_labels()
    
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
            
            # 检查是否所有翻牌动画都已完成
            if hasattr(self, 'flop_revealed') and self.flop_revealed > 0:
                self.flop_revealed -= 1
                if self.flop_revealed == 0:
                    # 所有翻牌动画完成
                    pass
            return
        
        if step <= steps // 2:
            # 第一阶段：从背面翻转到侧面（宽度减小）
            width = 100 - (step * 20)
            if width <= 0:
                width = 1
            # 创建缩放后的背面图像
            back_img = Image.new('RGBA', (width, 140), (0, 0, 0, 0))
            orig_back = self.back_image
            # 这里简化处理，实际应该缩放图片
            card_label.config(image=orig_back)
        else:
            # 第二阶段：从侧面翻转到正面（宽度增加）
            width = (step - steps // 2) * 20
            if width <= 0:
                width = 1
            # 创建缩放后的正面图像
            card_label.config(image=front_img)
        
        # 更新卡片显示
        card_label.place(width=width)
        
        # 下一步
        step += 1
        card_label.after(50, lambda: self.animate_flip(card_label, front_img, step))
    
    def enable_preflop_buttons(self):
        """启用翻牌前的操作按钮，并根据余额设置状态"""
        # 检查按钮是否还存在
        if not hasattr(self, 'bet_3x_button') or not self.bet_3x_button.winfo_exists():
            return
            
        ante = self.game.ante
        # 检查余额是否足够支付3倍Ante
        if self.balance >= ante * 3:
            self.bet_3x_button.config(state=tk.NORMAL)
        else:
            self.bet_3x_button.config(state=tk.DISABLED)

        # 检查余额是否足够支付4倍Ante
        if self.balance >= ante * 4:
            self.bet_4x_button.config(state=tk.NORMAL)
        else:
            self.bet_4x_button.config(state=tk.DISABLED)

        # 过牌按钮总是可用
        self.check_button.config(state=tk.NORMAL)

    def enable_flop_buttons(self):
        """启用翻牌圈的操作按钮，并根据余额设置状态"""
        # 检查按钮是否还存在
        if not hasattr(self, 'bet_2x_button') or not self.bet_2x_button.winfo_exists():
            return
            
        ante = self.game.ante
        # 检查余额是否足够支付2倍Ante
        if self.balance >= ante * 2:
            self.bet_2x_button.config(state=tk.NORMAL)
        else:
            self.bet_2x_button.config(state=tk.DISABLED)

        # 过牌按钮总是可用
        self.check_button.config(state=tk.NORMAL)

    def enable_river_buttons(self):
        """启用河牌圈的操作按钮"""
        # 检查按钮是否还存在
        if not hasattr(self, 'bet_1x_button') or not self.bet_1x_button.winfo_exists():
            return
            
        ante = self.game.ante
        # 检查余额是否足够支付1倍Ante
        if self.balance >= ante:
            self.bet_1x_button.config(state=tk.NORMAL)
        else:
            self.bet_1x_button.config(state=tk.DISABLED)

        # 弃牌按钮总是可用
        self.fold_button.config(state=tk.NORMAL)
    
    def play_action(self, bet_multiplier):
        if bet_multiplier > 0:
            bet_amount = bet_multiplier * self.game.ante
            self.balance -= bet_amount
            self.update_balance()
            self.game.play_bet = bet_amount
            # 更新Bet显示
            self.bet_var.set(str(int(bet_amount)))
            self.status_label.config(text=f"已下注: ${bet_amount}")
            
            # 更新本局下注显示
            total_bet = self.ante + self.blind + self.trips + bet_amount
            if self.participate_jackpot:
                total_bet += 20
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        # 根据当前阶段决定下一步
        if self.game.stage == "pre_flop":
            if bet_multiplier > 0:
                # 直接进入摊牌
                if hasattr(self, 'bet_4x_button') and self.bet_4x_button.winfo_exists():
                    self.bet_4x_button.config(state=tk.DISABLED)
                if hasattr(self, 'bet_3x_button') and self.bet_3x_button.winfo_exists():
                    self.bet_3x_button.config(state=tk.DISABLED)
                if hasattr(self, 'check_button') and self.check_button.winfo_exists():
                    self.check_button.config(state=tk.DISABLED)
                self.game.stage = "showdown"
                self.after(1000, self.show_showdown)
            else:
                # 进入翻牌圈
                self.game.stage = "flop"
                self.stage_label.config(text="翻牌圈")
                self.status_label.config(text="翻牌已发出。做出决策: 过牌或下注2倍")
                
                # 翻开翻牌圈的三张牌
                self.reveal_flop()
                
                # 更新操作按钮
                for widget in self.action_frame.winfo_children():
                    widget.destroy()
                    
                buttons_container = tk.Frame(self.action_frame, bg='#2a4a3c')
                buttons_container.pack(pady=5)

                self.check_button = tk.Button(
                    buttons_container, text="过牌", 
                    command=lambda: self.play_action(0), 
                    state=tk.DISABLED,
                    font=('Arial', 14), bg='#2196F3', fg='white', width=9
                )
                self.check_button.pack(side=tk.LEFT, padx=9)
                    
                self.bet_2x_button = tk.Button(
                    buttons_container, text="下注2倍", 
                    command=lambda: self.play_action(2),
                    state=tk.DISABLED,
                    font=('Arial', 14), bg='#FF9800', fg='white', width=9
                )
                self.bet_2x_button.pack(side=tk.LEFT, padx=9)
        
        elif self.game.stage == "flop":
            if bet_multiplier > 0:
                # 直接进入摊牌
                if hasattr(self, 'bet_2x_button') and self.bet_2x_button.winfo_exists():
                    self.bet_2x_button.config(state=tk.DISABLED)
                if hasattr(self, 'check_button') and self.check_button.winfo_exists():
                    self.check_button.config(state=tk.DISABLED)
                self.game.stage = "showdown"
                self.after(1000, self.show_showdown)
            else:
                # 进入河牌圈
                self.game.stage = "river"
                self.stage_label.config(text="河牌圈")
                self.status_label.config(text="河牌已发出。做出最终决策: 弃牌或下注1倍")
                
                # 翻开转牌和河牌
                self.reveal_turn_river()
                
                # 更新操作按钮
                for widget in self.action_frame.winfo_children():
                    widget.destroy()
                    
                buttons_container = tk.Frame(self.action_frame, bg='#2a4a3c')
                buttons_container.pack(pady=5)

                self.fold_button = tk.Button(
                    buttons_container, text="弃牌", 
                    command=self.fold_action, 
                    state=tk.DISABLED,
                    font=('Arial', 14), bg='#F44336', fg='white', width=9
                )
                self.fold_button.pack(side=tk.LEFT, padx=10)
                    
                self.bet_1x_button = tk.Button(
                    buttons_container, text="下注1倍", 
                    command=lambda: self.play_action(1), 
                    state=tk.DISABLED,
                    font=('Arial', 14), bg='#4CAF50', fg='white', width=9
                )
                self.bet_1x_button.pack(side=tk.LEFT, padx=9)
        
        # 在河牌圈下注1倍时进入结算
        elif self.game.stage == "river":
            if bet_multiplier == 1:
                if hasattr(self, 'bet_1x_button') and self.bet_1x_button.winfo_exists():
                    self.bet_1x_button.config(state=tk.DISABLED)
                if hasattr(self, 'fold_button') and self.fold_button.winfo_exists():
                    self.fold_button.config(state=tk.DISABLED)
                self.update_balance()
                self.game.play_bet = bet_amount
                # 更新Bet显示
                self.bet_var.set(str(int(bet_amount)))
                self.status_label.config(text=f"已下注: ${bet_amount}")
                
                # 更新本局下注显示
                total_bet = self.ante + self.blind + self.trips + bet_amount
                if self.participate_jackpot:
                    total_bet += 20
                self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
                
                # 进入摊牌
                self.game.stage = "showdown"
                self.after(1000, self.show_showdown)
            else:
                # 弃牌
                self.fold_action()
        
    def fold_action(self):
        self.game.folded = True
        self.status_label.config(text="您已弃牌。游戏结束。")

        # 翻开庄家牌
        self.reveal_dealer_cards()
        
        # 更新庄家牌型
        self.update_hand_labels()
        
        # 翻开所有公共牌和玩家牌，以便评估Trips和Progressive
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["community"][i] = True
        
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["player"][i] = True
        
        # 更新所有牌型标签
        self.update_hand_labels()
        
        # 等待1秒后结算Trips和Progressive
        self.after(1000, self.settle_trips_and_progressive_after_fold)

    def settle_trips_and_progressive_after_fold(self):
        """弃牌后结算Trips和Progressive"""
        # 评估玩家手牌
        player_cards = self.game.player_hole + self.game.community_cards
        player_eval, player_best = find_best_5(player_cards)
        
        # 结算Trips
        trips_winnings = 0
        if self.game.trips > 0:
            player_hand_rank = player_eval[0]
            if player_hand_rank >= 3:  # 三条及以上
                if player_hand_rank in TRIPS_PAYOUT:
                    odds = TRIPS_PAYOUT[player_hand_rank]
                    trips_winnings = self.game.trips * (1 + odds)
                else:
                    # 如果没有匹配的赔率，退还本金
                    trips_winnings = self.game.trips
        
        # 结算Progressive
        progressive_winnings = 0
        if self.game.participate_jackpot:
            progressive_cards = self.game.player_hole + self.game.community_cards[:3]
            pg_eval, _ = evaluate_hand(progressive_cards)
            
            # 定义奖金规则
            jackpot_rules = {
                9: {"amount": lambda: max(self.game.progressive_amount, 350000), "message": "皇家顺! 赢得累进大奖 ${amount:.2f}!"},
                8: {"amount": lambda: max(self.game.progressive_amount * 0.1, 35000), "message": "同花顺! 赢得累进大奖 ${amount:.2f}!"},
                7: {"amount": 25000, "message": "四条! 赢得累进大奖 $25,000!"},
                6: {"amount": 4000, "message": "葫芦! 赢得累进大奖 $4,000!"},
                5: {"amount": 3000, "message": "同花! 赢得累进大奖 $3,000!"}
            }
            
            if pg_eval in jackpot_rules:
                rule = jackpot_rules[pg_eval]
                
                # 计算奖金金额
                if callable(rule["amount"]):
                    amount = rule["amount"]()
                else:
                    amount = rule["amount"]
                
                progressive_winnings = amount
                
                # 从奖池扣除
                self.game.progressive_amount -= amount
                
                # 显示消息
                messagebox.showinfo("恭喜您获得累进大奖！", rule["message"].format(amount=amount))
        
        # 计算总赢取金额
        total_winnings = trips_winnings + progressive_winnings
        self.last_win = total_winnings
        
        # 更新余额
        self.balance += total_winnings
        self.update_balance()
        
        # 更新Trips显示
        self.trips_var.set(str(int(trips_winnings)))
        
        # 设置背景色
        if trips_winnings > 0:
            self.trips_display.config(bg='gold')  # 赢 - 金色背景
        elif trips_winnings == self.game.trips:
            self.trips_display.config(bg='light blue')  # 退还 - 浅蓝色背景
        else:
            self.trips_display.config(bg='white')  # 输 - 白色背景
        
        # 显示结果
        if total_winnings > 0:
            result_text = f"弃牌但赢得三条注: ${total_winnings:.2f}"
            self.status_label.config(text=result_text)
        else:
            self.status_label.config(text="您已弃牌。游戏结束。")
        
        # 更新上局获胜金额
        self.last_win_label.config(text=f"上局获胜: ${total_winnings:.2f}")
        
        # 计算Progressive增量
        total_bet = self.game.ante + self.game.blind + self.game.trips + self.game.play_bet
        progressive_increase = total_bet * 0.08
        
        # 如果玩家购买了Progressive，将20元中的95%加入奖池
        if self.game.participate_jackpot:
            progressive_increase += 19
        
        self.game.progressive_amount += progressive_increase
        
        # 确保奖池最低金额为327301.26
        if self.game.progressive_amount < 327301.26:
            self.game.progressive_amount = 327301.26
        
        # 更新Progressive金额
        save_progressive(self.game.progressive_amount)
        
        # 确保界面上的奖池金额实时更新
        self.progressive_amount_var.set(f"${self.game.progressive_amount:.2f}")
        if hasattr(self, 'progressive_display'):
            self.progressive_display.config(text=f"${self.game.progressive_amount:.2f}")
        
        # 更新下注显示
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.bet_var.set("0")
        
        # 设置背景色为白色（输）
        for widget_type, widget in self.bet_widgets.items():
            if widget_type != "trips":  # Trips已经单独处理
                widget.config(bg='white')
        
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
    
    def show_showdown(self):
        """摊牌阶段：一次性翻开所有牌"""
        # 翻开所有公共牌
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["community"][i] = True
        
        # 翻开玩家牌
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["player"][i] = True
        
        # 翻开庄家牌
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["dealer"][i] = True
        
        # 更新所有牌型标签
        self.update_hand_labels()
        
        # 等待2秒后结算
        self.after(2000, self.final_reveal)
    
    def final_reveal(self):
        """摊牌后结算"""
        # 评估手牌
        player_eval, player_best, dealer_eval, dealer_best = self.game.evaluate_hands()
        
        # 结算
        winnings = self.calculate_winnings(player_eval, dealer_eval)
        self.last_win = winnings
        
        # 更新余额
        self.balance += winnings
        self.update_balance()
        
        # 更新下注显示金额
        self.ante_var.set(str(int(self.win_details['ante'])))
        self.blind_var.set(str(int(self.win_details['blind'])))
        self.bet_var.set(str(int(self.win_details['bet'])))
        self.trips_var.set(str(int(self.win_details['trips'])))
        
        # 设置背景色：赢为金色，Push为浅蓝色，输为白色
        for bet_type, widget in self.bet_widgets.items():
            # 对于输的部分，金额设为0
            if self.win_details[bet_type] == 0:
                if bet_type == "ante":
                    self.ante_var.set("0")
                elif bet_type == "blind":
                    self.blind_var.set("0")
                elif bet_type == "bet":
                    self.bet_var.set("0")
                widget.config(bg='white')  # 输 - 白色背景
            else:
                # 判断是赢还是Push
                principal = 0
                if bet_type == "ante":
                    principal = self.game.ante
                elif bet_type == "blind":
                    principal = self.game.blind
                elif bet_type == "bet":
                    principal = self.game.play_bet
                elif bet_type == "trips":
                    principal = self.game.trips
                
                # 如果赢取金额等于本金，则是Push（平局）
                if self.win_details[bet_type] == principal:
                    widget.config(bg='light blue')  # Push - 浅蓝色背景
                else:
                    widget.config(bg='gold')  # 赢 - 金色背景
        
        # 显示结果
        result_text = f"赢取金额: ${winnings:.2f}"
        self.status_label.config(text="游戏结束。")
        
        # 更新上局获胜金额
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
        
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
    
    def calculate_winnings(self, player_eval, dealer_eval):
        # 重置获胜详情
        self.win_details = {
            "ante": 0,
            "blind": 0,
            "bet": 0,
            "trips": 0,
            "jackpot": 0
        }
        
        total_winnings = 0
        
        # 1. Ante 结算
        if player_eval > dealer_eval:
            # 玩家获胜
            if dealer_eval[0] == 0:
                # 庄家为高牌 -> 仅退还Ante
                self.win_details['ante'] = self.game.ante
            else:
                # 庄家不是高牌 -> 支付2倍Ante（本金+盈利）
                self.win_details['ante'] = self.game.ante * 2
        elif player_eval == dealer_eval:
            # 平局 -> 退还Ante
            self.win_details['ante'] = self.game.ante
        else:
            # 玩家输
            if dealer_eval[0] == 0:
                # 庄家为高牌 -> 退还Ante
                self.win_details['ante'] = self.game.ante
            else:
                # 庄家不是高牌 -> 输掉Ante
                self.win_details['ante'] = 0
        total_winnings += self.win_details['ante']
            
        # 2. Blind 结算（独立于Ante结果）
        player_hand_rank = player_eval[0]

        # 判断玩家手牌是否在Blind支付表中
        if player_hand_rank in BLIND_PAYOUT:
            # 玩家手牌在支付表中
            if player_eval > dealer_eval:  # 玩家赢
                odds = BLIND_PAYOUT[player_hand_rank]
                self.win_details['blind'] = self.game.blind * (1 + odds)
            elif player_eval == dealer_eval:  # 平局
                self.win_details['blind'] = self.game.blind  # 退还本金
            else:  # 玩家输
                self.win_details['blind'] = 0
        else:
            # 玩家手牌不在支付表中
            if player_eval > dealer_eval:  # 玩家赢
                self.win_details['blind'] = self.game.blind  # 退还本金
            elif player_eval == dealer_eval:  # 平局
                self.win_details['blind'] = self.game.blind  # 退还本金
            else:  # 玩家输
                self.win_details['blind'] = 0

        total_winnings += self.win_details['blind']
                
        # 3. Play Bet 结算
        if player_eval > dealer_eval:
            # Play赢利+返还本金
            self.win_details['bet'] = self.game.play_bet * 2
            total_winnings += self.win_details['bet']
        elif player_eval == dealer_eval:
            # Play平局 - 退还本金
            self.win_details['bet'] = self.game.play_bet
            total_winnings += self.win_details['bet']
        else:
            # 玩家输 - 输掉Play Bet
            self.win_details['bet'] = 0
        
        # 4. Trips 副注结算（独立于主注）
        if self.game.trips > 0:
            player_hand_rank = player_eval[0]
            if player_hand_rank >= 3:  # 三条及以上
                if player_hand_rank in TRIPS_PAYOUT:
                    odds = TRIPS_PAYOUT[player_hand_rank]
                    self.win_details['trips'] = self.game.trips * (1 + odds)
                    total_winnings += self.win_details['trips']
                else:
                    # 如果没有匹配的赔率，退还本金
                    self.win_details['trips'] = self.game.trips
                    total_winnings += self.win_details['trips']
            else:
                # 两对及以下，Trips输
                self.win_details['trips'] = 0
        
        # 5. Jackpot 结算 - 简化版
        if self.game.participate_jackpot:
            progressive_cards = self.game.player_hole + self.game.community_cards[:3]
            pg_eval, _ = evaluate_hand(progressive_cards)
            
            # 定义奖金规则
            jackpot_rules = {
                9: {"amount": lambda: max(self.game.progressive_amount, 350000), "message": "皇家顺! 赢得累进大奖 ${amount:.2f}!"},
                8: {"amount": lambda: max(self.game.progressive_amount * 0.1, 35000), "message": "同花顺! 赢得累进大奖 ${amount:.2f}!"},
                7: {"amount": 25000, "message": "四条! 赢得累进大奖 $25,000!"},
                6: {"amount": 4000, "message": "葫芦! 赢得累进大奖 $4,000!"},
                5: {"amount": 3000, "message": "同花! 赢得累进大奖 $3,000!"}
            }
            
            if pg_eval in jackpot_rules:
                rule = jackpot_rules[pg_eval]
                
                # 计算奖金金额
                if callable(rule["amount"]):
                    amount = rule["amount"]()
                else:
                    amount = rule["amount"]
                
                self.win_details['jackpot'] = amount
                total_winnings += amount
                
                # 从奖池扣除
                self.game.progressive_amount -= amount
                
                # 显示消息
                messagebox.showinfo("恭喜您获得累进大奖！", rule["message"].format(amount=amount))
            
            # 保存Progressive金额
            save_progressive(self.game.progressive_amount)
            self.progressive_var.set(f"${self.game.progressive_amount:.2f}")

        # 计算Progressive增量
        total_bet = self.game.ante + self.game.blind + self.game.trips + self.game.play_bet
        progressive_increase = total_bet * 0.08
        
        # 如果玩家购买了Progressive，将20元中的95%加入奖池
        if self.game.participate_jackpot:
            progressive_increase += 19
        
        self.game.progressive_amount += progressive_increase
        
        # 确保奖池最低金额为327301.26
        if self.game.progressive_amount < 327301.26:
            self.game.progressive_amount = 327301.26
        
        # 更新Progressive金额
        save_progressive(self.game.progressive_amount)

        # 确保界面上的奖池金额实时更新
        self.progressive_amount_var.set(f"${self.game.progressive_amount:.2f}")

        # 更新Progressive显示（如果存在）
        if hasattr(self, 'progressive_display'):
            self.progressive_display.config(text=f"${self.game.progressive_amount:.2f}")
        
        return total_winnings

    def animate_collect_cards(self, auto_reset):
        """执行收牌动画：先翻转所有牌为背面，然后向右收起"""
        # 禁用所有按钮
        self.disable_action_buttons()
        
        self.animate_move_cards_out(auto_reset)

    def animate_move_cards_out(self, auto_reset):
        """将所有牌向右移出屏幕"""
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
        for card_label in self.active_card_labels[:]:  # 遍历副本，因为可能删除
            if not hasattr(card_label, 'target_pos'):
                continue

            current_x = card_label.winfo_x()
            target_x, target_y = card_label.target_pos

            # 计算新位置
            dx = target_x - current_x
            if abs(dx) < 5:
                card_label.place(x=target_x, y=target_y)
                # 移除该卡片
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
        """重置Trips和Ante的投注金额为0"""
        self.ante_var.set("0")
        self.blind_var.set("0")  # Blind会自动等于Ante，所以也要重置
        self.trips_var.set("0")
        self.bet_var.set("0")  # 同时重置Bet金额
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        
        # 短暂高亮显示重置效果
        self.ante_display.config(bg='#FFCDD2')  # 浅红色
        self.trips_display.config(bg='#FFCDD2')
        self.bet_display.config(bg='#FFCDD2')
        self.after(500, lambda: [
            self.ante_display.config(bg='white'), 
            self.trips_display.config(bg='white'),
            self.bet_display.config(bg='white')
        ])
    
    def _do_reset(self, auto_reset=False):
        """真正的重置游戏界面"""
        # 重置游戏状态
        self.game.reset_game()
        self.stage_label.config(text="翻牌前")
        
        # 重置标签显示
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        
        # 重置下注金额为0
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.trips_var.set("0")
        self.bet_var.set("0")
        # 设置Jackpot复选框为上一局的选择
        self.progressive_var.set(1 if self.last_jackpot_selection else 0)
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.trips_display.config(bg='white')
        
        # 清空活动卡片列表（在收牌动画后已经清空，这里确保一下）
        self.active_card_labels = []
        
        # 恢复下注区域
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.trips_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("trips"))
        self.bet_display.bind("<Button-1>", self.cycle_bet_amount)
        self.progressive_cb.config(state=tk.NORMAL)
        for chip in self.chip_buttons:
            # 使用存储的文本重新绑定事件
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        
        # 恢复操作按钮区域
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)

        # 添加"重设金额"按钮
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重设金额", 
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
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 重置本局下注显示
        self.current_bet_label.config(text="本局下注: $0.00")
        
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
    app = UTHGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")