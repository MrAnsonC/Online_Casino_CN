import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageTk, ImageOps
import random
import json
import os
import time

# ========== 数据管理函数 ==========
def get_data_file_path():
    """获取用户数据文件路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saving_data.json')

def load_user_data():
    """加载用户数据"""
    try:
        with open(get_data_file_path(), 'r') as f:
            return json.load(f)
    except:
        return []

def update_balance_in_json(username, new_balance):
    """更新用户余额"""
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = float(new_balance)
            break
    with open(get_data_file_path(), 'w') as f:
        json.dump(users, f)

# ========== 游戏核心类 ==========
class Card:
    """卡牌类"""
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = self._get_value()
    
    def _get_value(self):
        """获取卡牌数值"""
        if self.rank in ['J', 'Q', 'K']:
            return 10
        if self.rank == 'A':
            return 11
        return int(self.rank)
    
    def adjust_ace(self):
        """调整A的值为1"""
        return 1 if self.rank == 'A' else self.value

class Deck:
    """牌组类"""
    def __init__(self, decks=4):
        ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
        suits = ['♥','♦','♣','♠']
        self.cards = [Card(r, s) for _ in range(decks) for s in suits for r in ranks]
        random.shuffle(self.cards)
        
    def deal(self):
        """发牌"""
        return self.cards.pop() if self.cards else None

class Player:
    """玩家类"""
    def __init__(self, name, money):
        self.name = name
        self.money = money
        self.hand = []
        self.bet = 0
        self.insurance = 0
    
    def place_bet(self, amount):
        """下注"""
        if amount <= 0 or amount > self.money:
            return False
        self.bet = amount
        self.money -= amount
        return True
    
    def clear_hand(self):
        self.hand = []
        
    def add_card(self, card):
        self.hand.append(card)
        
    def hand_value(self):
        """计算手牌所有可能值"""
        total = sum(c.value for c in self.hand)
        aces = sum(1 for c in self.hand if c.rank == 'A')
        possible_values = [total - 10*i for i in range(aces+1)]
        return [v for v in possible_values if v <= 21] or [min(possible_values)]

class Dealer:
    """庄家类"""
    def __init__(self):
        self.hand = []
        
    def clear_hand(self):
        self.hand = []
        
    def add_card(self, card):
        self.hand.append(card)
        
    def hand_value(self):
        """计算庄家手牌最佳值"""
        total = sum(c.value for c in self.hand)
        aces = sum(1 for c in self.hand if c.rank == 'A')
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        return total
    
    def should_hit(self):
        """判断是否需要继续要牌"""
        return self.hand_value() < 17

# ========== 主界面类 ==========
class BlackjackGUI:
    def __init__(self, master, username, balance):
        self.master = master
        self.username = username
        self.player = Player(username, balance)
        self.dealer = Dealer()
        self.deck = None
        self.game_over = False
        self.insurance_mode = False
        self.animation_in_progress = False
        self.initial_background_shown = True
        self.initial_cards_dealt = False
        self.game_started = False
        
        # 防止自动停牌被重复调用
        self.auto_stand_called = False  
        self.starting_money = balance  
        self.last_bet = 0
        
        # 卡牌图像参数
        self.card_width = 120
        self.card_height = 170
        self.suit_map = {'♥':'Heart', '♦':'Diamond', '♣':'Club', '♠':'Spade'}
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.card_dir = os.path.join(self.current_dir, "Card")
        self._verify_resources()

        self.balance_var = tk.StringVar()
        self.balance_var.set(f"{self.player.money:.2f}")
        
        # 样式配置
        self.style = ttk.Style()
        self._configure_styles()
        self.setup_ui()
        self.new_round()
    
    def _configure_styles(self):
        """配置界面样式"""
        # 圆形按钮样式
        self.style.configure('Round.TButton', 
                           background='#252e3f',
                           foreground='white',
                           borderwidth=0,
                           relief='flat',
                           font=('Arial', 10, 'bold'))
        self.style.map('Round.TButton',
                     background=[('active', '#3a4659')])
        
        # 数学操作按钮样式
        self.style.configure('Math.TButton',
                           background='#3a4659',
                           foreground='white',
                           font=('Arial', 10, 'bold'))
        self.style.map('Math.TButton',
                     background=[('active', '#4a5669')])
        
        # 输入框样式
        self.style.configure('Custom.TEntry',
                          fieldbackground='#252e3f',
                          foreground='white',
                          insertcolor='white')

    def _verify_resources(self):
        """验证必要资源文件"""
        required = ['Background.png']
        if not os.path.exists(self.card_dir):
            messagebox.showerror("错误", f"卡牌目录不存在: {self.card_dir}")
            exit()
        for f in required:
            if not os.path.exists(os.path.join(self.card_dir, f)):
                messagebox.showerror("错误", f"缺少必要文件: {f}")
                exit()

    def _init_background_cards(self):
        """初始化背景卡牌（优化版）"""
        if not self.initial_background_shown:
            return
        
        # 加载背景卡牌图像
        bg_img = self.get_card_image(None, show=False)
        
        # 庄家区域添加2张背景卡
        for _ in range(2):
            ttk.Label(self.dealer_cards, image=bg_img).pack(side=tk.LEFT, padx=5)
        
        # 玩家区域添加2张背景卡
        for _ in range(2):
            ttk.Label(self.player_cards, image=bg_img).pack(side=tk.LEFT, padx=5)

    

    def setup_ui(self):
        """初始化界面"""
        # 背景设置
        bg_path = os.path.join(self.current_dir, "Card/Blackjack_gui.png")
        try:
            self.bg_image = Image.open(bg_path)
            width, height = self.bg_image.size
            self.master.geometry(f"{width}x{height}")
            self.bg_photo = ImageTk.PhotoImage(self.bg_image)
            self.bg_label = ttk.Label(self.master, image=self.bg_photo)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        except FileNotFoundError:
            messagebox.showerror("错误", f"背景图片缺失: {bg_path}")
            exit()

        # ========== 下注控制区 ==========
        self.bet_frame = ttk.Frame(self.master)
        self.bet_frame.place(x=20, y=150)

        # 开始游戏按钮
        self.start_btn = ttk.Button(self.bet_frame, text="开始游戏", command=self.start_game)
        self.start_btn.pack(fill=tk.X, pady=5)

        # 快速下注按钮
        quick_bets_frame = ttk.Frame(self.bet_frame)
        quick_bets_frame.pack(pady=5)
        
        # 第一行按钮
        row1 = ttk.Frame(quick_bets_frame)
        row1.pack()
        ttk.Button(row1, text="10", width=4, command=lambda: self.add_bet(10),
                 style='Round.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="20", width=4, command=lambda: self.add_bet(20),
                 style='Round.TButton').pack(side=tk.LEFT, padx=2)

        # 第二行按钮
        row2 = ttk.Frame(quick_bets_frame)
        row2.pack(pady=3)
        ttk.Button(row2, text="50", width=4, command=lambda: self.add_bet(50),
                 style='Round.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(row2, text="100", width=4, command=lambda: self.add_bet(100),
                 style='Round.TButton').pack(side=tk.LEFT, padx=2)

        # 输入行
        input_row = ttk.Frame(self.bet_frame)
        input_row.pack(pady=(10, 5))
        
        # 输入框
        self.bet_entry = ttk.Entry(input_row, 
                                 validate="key", 
                                 width=10,
                                 style='Custom.TEntry',
                                 font=('Arial', 12))
        self.bet_entry['validatecommand'] = (self.bet_entry.register(self.validate_bet), '%P')
        self.bet_entry.pack(side=tk.LEFT)

        # 数学操作按钮
        math_btn_frame = ttk.Frame(input_row)
        math_btn_frame.pack(side=tk.LEFT, padx=5)
        ttk.Button(math_btn_frame, text="1/2", width=4,
                 command=lambda: self.multiply_bet(0.5),
                 style='Math.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(math_btn_frame, text="2X", width=4,
                 command=lambda: self.multiply_bet(2),
                 style='Math.TButton').pack(side=tk.LEFT, padx=2)

        # ========== 卡牌显示区 ==========
        self.card_frame = ttk.Frame(self.master)
        self.card_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER, y=50)

        # 庄家牌区
        self.dealer_frame = ttk.Frame(self.card_frame)
        self.dealer_frame.pack(pady=5)
        self.dealer_cards = ttk.Frame(self.dealer_frame)
        self.dealer_cards.pack()
        self.dealer_value_label = ttk.Label(self.dealer_frame, text="庄家点数：-", font=('Arial', 12))
        self.dealer_value_label.pack()

        # 玩家牌区
        self.player_frame = ttk.Frame(self.card_frame)
        self.player_frame.pack(pady=5)
        self.player_cards = ttk.Frame(self.player_frame)
        self.player_cards.pack()
        self.player_value_label = ttk.Label(self.player_frame, text="玩家点数：-", font=('Arial', 12))
        self.player_value_label.pack()

        # ========== 操作按钮区 ==========
        self.action_frame = ttk.LabelFrame(self.master, text="游戏操作")
        self.action_frame.place(relx=0.5, rely=0.9, anchor=tk.CENTER, y=-20)
        
        # 游戏操作按钮（修正变量名冲突）
        self.hit_btn = ttk.Button(self.action_frame, text="要牌", command=self.hit, state=tk.DISABLED)
        self.hit_btn.pack(side=tk.LEFT, padx=5)
        self.stand_btn = ttk.Button(self.action_frame, text="停牌", command=self.stand, state=tk.DISABLED)
        self.stand_btn.pack(side=tk.LEFT, padx=5)
        self.player_double_btn = ttk.Button(self.action_frame, text="加倍", command=self.double, state=tk.DISABLED)
        self.player_double_btn.pack(side=tk.LEFT, padx=5)
        self.surrender_btn = ttk.Button(self.action_frame, text="投降", command=self.surrender, state=tk.DISABLED)
        self.surrender_btn.pack(side=tk.LEFT, padx=5)

        # 保险按钮
        self.insurance_frame = ttk.Frame(self.master)
        self.insurance_btn = ttk.Button(self.insurance_frame, text="买保险", command=self.buy_insurance)
        self.no_insurance_btn = ttk.Button(self.insurance_frame, text="不买", command=self.no_insurance)

        # 余额显示
        self.balance_label = tk.Label(self.master, textvariable=self.balance_var, 
                                    font=('Arial', 30), bg="#475364", fg="white")
        self.balance_label.place(relx=0.5, y=10, anchor="n")

        self.update_display()

    # ========== 游戏逻辑方法 ==========
    def new_round(self, reset_bet=True):
        """初始化新回合"""
        self.deck = Deck()
        self.player.clear_hand()
        self.dealer.clear_hand()
        self.player.insurance = 0
        self.game_over = False
        self.insurance_mode = False
        self.game_started = False
        self.initial_background_shown = True
        self.auto_stand_called = False
        if reset_bet:
            self.player.bet = 0
        self.initial_cards_dealt = False
        self.animation_in_progress = False
        self.update_controls()
        self.update_display()
        for frame in [self.dealer_cards, self.player_cards]:
            for widget in frame.winfo_children():
                widget.destroy()

    def validate_bet(self, value):
        """验证下注输入格式"""
        if value == "":
            return True
        try:
            num = float(value)
            if num <= 0:
                return False
            parts = value.split('.')
            if len(parts) > 1 and len(parts[1]) > 2:
                return False
            return True
        except:
            return False

    def add_bet(self, amount):
        """添加下注金额"""
        try:
            current = float(self.bet_entry.get() or 0)
            new_value = current + amount
            self.bet_entry.delete(0, tk.END)
            self.bet_entry.insert(0, f"{new_value:.2f}")
        except ValueError:
            self.bet_entry.delete(0, tk.END)
            self.bet_entry.insert(0, f"{amount:.2f}")

    def multiply_bet(self, factor):
        """乘以系数"""
        try:
            current = float(self.bet_entry.get() or 0)
            new_value = current * factor
            if new_value <= 0:
                return
            self.bet_entry.delete(0, tk.END)
            self.bet_entry.insert(0, f"{new_value:.2f}")
        except ValueError:
            pass

    def start_game(self):
        """开始游戏"""
        try:
            bet = float(self.bet_entry.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效下注金额")
            return
        
        if not self.player.place_bet(bet):
            messagebox.showerror("错误", "余额不足")
            return

        self.last_bet = bet
        self.starting_money = self.player.money + bet
        
        if self.initial_background_shown:
            for frame in [self.dealer_cards, self.player_cards]:
                for widget in frame.winfo_children():
                    widget.destroy()
            self.initial_background_shown = False
        
        self.new_round(reset_bet=False)
        
        delays = [0, 400, 800, 1200]
        for i in range(2):
            self.master.after(delays[i], lambda: self._add_card_with_animation('player'))
            self.master.after(delays[i+2], lambda: self._add_card_with_animation('dealer'))
        
        self.game_started = True
        self.master.after(2000, self._post_initial_deal)

    def _post_initial_deal(self):
        """初始发牌后处理"""
        self.update_controls()
        self._check_insurance_condition()
        
    def _check_insurance_condition(self):
        """检查是否需要提供保险"""
        if len(self.dealer.hand) >= 1 and self.dealer.hand[0].rank == 'A':
            self._show_insurance_buttons()

    def multiply_bet(self, factor):
        """乘以系数"""
        try:
            current = float(self.bet_entry.get() or 0)
            new_value = current * factor
            if new_value <= 0:
                return
            self.bet_entry.delete(0, tk.END)
            self.bet_entry.insert(0, f"{new_value:.2f}")
        except ValueError:
            pass

    def _process_deal_animation(self):
        """处理发牌动画（带背景翻转效果）"""
        if self.current_animation_step >= len(self.deal_animation_queue):
            self.animation_in_progress = False
            self.update_controls()
            return

        target, index = self.deal_animation_queue[self.current_animation_step]
        card = self.player.hand[index] if target == 'player' else self.dealer.hand[index]

        frame = self.player_cards if target == 'player' else self.dealer_cards
        label = ttk.Label(frame, image=self.get_card_image(None, show=False))
        label.pack(side=tk.LEFT, padx=5)

        start_x = -200
        step = 20

        def animate():
            nonlocal start_x
            if start_x < 0:
                label.place(x=start_x, y=0)
                start_x += step
                self.master.after(10, animate)
            else:
                label.configure(image=self.get_card_image(card, show=(target=='player' or self.game_over)))
                label.image = self.get_card_image(card)
                self.current_animation_step += 1
                self._process_deal_animation()

        animate()

    # ========== 保险相关逻辑 ==========
    def _show_insurance_buttons(self):
        """显示保险选项"""
        self.insurance_mode = True
        self.insurance_frame.pack(pady=10)
        self.insurance_btn.pack(side=tk.LEFT, padx=5)
        self.no_insurance_btn.pack(side=tk.LEFT, padx=5)
        self.update_controls()

    def _hide_insurance_buttons(self):
        """隐藏保险选项"""
        self.insurance_mode = False
        self.insurance_frame.pack_forget()
        self.insurance_btn.pack_forget()
        self.no_insurance_btn.pack_forget()
        self.update_controls()

    def buy_insurance(self):
        """购买保险"""
        insurance_amt = self.player.bet // 2
        if self.player.money >= insurance_amt:
            self.player.insurance = insurance_amt
            self.player.money -= insurance_amt
        self._hide_insurance_buttons()
        self._check_blackjack()

    def no_insurance(self):
        """不买保险"""
        self._hide_insurance_buttons()
        self._check_blackjack()

    def _check_blackjack(self):
        """检查Blackjack并处理（优化延迟逻辑）"""
        dealer_bj = len(self.dealer.hand) == 2 and self.dealer.hand_value() == 21
        player_bj = len(self.player.hand) == 2 and 21 in self.player.hand_value()
        
        if (len(self.dealer.hand) == 2 and 
            self.dealer.hand[0].value in [10] and 
            self.dealer.hand[1].rank == 'A' and 
            not self.game_over):
            self.master.after(2000, self._reveal_dealer_hidden_card)
            return False
        
        if dealer_bj:
            self.game_over = True
            self.update_display()
            msg = "庄家Blackjack！"
            if self.player.insurance:
                self.player.money += self.player.insurance * 2
                msg += " 保险赔付！"
            self.show_result(msg)
            return True
        return False
    
    def _reveal_dealer_hidden_card(self):
        """揭示庄家暗牌并结算"""
        self.game_over = True
        self.update_display()
        
        dealer_total = self.dealer.hand_value()
        player_total = max(self.player.hand_value())
        
        if dealer_total == 21 and player_total == 21:
            self.show_result("双方Blackjack！平局！")
        elif dealer_total == 21:
            self.show_result("庄家Blackjack！胜利！")
        else:
            self.compare_hands()

    # ========== 玩家操作处理 ==========
    def hit(self):
        """要牌操作"""
        self._add_card_with_animation('player')
        # 先加入牌后检测是否爆牌
        if min(self.player.hand_value()) > 21:
            self.show_result("玩家爆牌！庄家胜利！")

    def stand(self):
        """停牌操作（增加暗牌翻转）"""
        self.update_controls()
        dealer_labels = self.dealer_cards.winfo_children()
        if len(dealer_labels) >= 2 and not self.game_over:
            hidden_card = dealer_labels[1]
            self._flip_hidden_card(hidden_card)
        self.master.after(500, self._dealer_hit_step)
        
    def _flip_hidden_card(self, label):
        """执行暗牌翻转动画"""
        degree = 0
        def animate():
            nonlocal degree
            if degree < 180:
                img = self._create_hidden_card_image(degree)
                label.configure(image=img)
                label.image = img
                degree += 15
                self.master.after(20, animate)
            else:
                card = self.dealer.hand[1]
                img = self.get_card_image(card)
                label.configure(image=img)
                label.image = img
                self.update_display()
        animate()

    def double(self):
        """加倍下注"""
        if self.player.money >= self.player.bet:
            self.player.place_bet(self.player.bet)
            self.hit()
            if min(self.player.hand_value()) <= 21:
                self.stand()

    def surrender(self):
        """投降操作"""
        self.player.money += self.player.bet // 2
        self.show_result("玩家投降！输一半下注！")

    def _add_card_with_animation(self, target, initial_deal=False):
        self.animation_in_progress = True
        card = self.deck.deal()
        
        # 将牌立即加入手牌，并更新点数显示（保证即时更新）
        if target == 'player':
            self.player.add_card(card)
            frame = self.player_cards
        else:
            self.dealer.add_card(card)
            frame = self.dealer_cards
        self._update_value_labels()
        
        # 修改发牌动画起始位置：从窗口右上角开始（减去卡牌宽度）
        window_width = self.master.winfo_width()
        start_x = window_width - self.card_width  
        start_y = 0
        
        target_x = 0
        target_y = 0
        
        label = ttk.Label(frame)
        label.is_animation = True
        label.place(x=start_x, y=start_y)
        
        total_duration = 1500  # 毫秒
        flip_start = 500       
        flip_end = 1000        
        steps = 60             
        
        x_step = (target_x - start_x) / steps
        y_step = (target_y - start_y) / steps
        
        start_time = time.time()
        
        def animate():
            elapsed = (time.time() - start_time) * 1000
            if elapsed > total_duration:
                label.destroy()
                # 修改：若游戏已结束则不再创建永久牌（避免重复显示同一张牌）
                if not self.game_over:
                    self._create_permanent_card(target, card, frame)
                self.animation_in_progress = False
                self.update_controls()
                return
            
            current_x = start_x + x_step * (elapsed / (total_duration/steps))
            current_y = start_y + y_step * (elapsed / (total_duration/steps))
            
            if flip_start <= elapsed <= flip_end:
                flip_progress = (elapsed - flip_start) / (flip_end - flip_start) * 180
                img = self._create_flip_animation(card, flip_progress)
            else:
                img = self.get_card_image(None, show=False) if elapsed < flip_start else self.get_card_image(card)
            
            label.configure(image=img)
            label.image = img
            label.place(x=int(current_x), y=int(current_y))
            
            self.master.after(20, animate)
        
        animate()

    def _create_flip_animation(self, card, degree):
        """创建翻转动画图像"""
        if degree < 90:
            img = Image.open(os.path.join(self.card_dir, "Background.png"))
        else:
            suit = self.suit_map[card.suit]
            rank = '10' if card.rank == '10' else card.rank
            img = Image.open(os.path.join(self.card_dir, f"{suit}{rank}.png"))
        img = img.resize((self.card_width, self.card_height))
        rotated = img.rotate(degree, expand=True, resample=Image.BICUBIC)
        return ImageTk.PhotoImage(rotated)

    def _create_permanent_card(self, target, card, frame):
        show = True
        if target == 'dealer':
            card_index = self.dealer.hand.index(card)
            show = (card_index == 0) or self.game_over
        img = self.get_card_image(card, show=show)
        permanent_label = ttk.Label(frame, image=img)
        permanent_label.image = img
        permanent_label.pack(side=tk.LEFT, padx=5)
                
    def _create_hidden_card_image(self, degree):
        """创建庄家暗牌旋转特效（旋转到一半后加载真实卡牌图像）"""
        if degree < 90:
            base_img = Image.open(os.path.join(self.card_dir, "Background.png"))
        else:
            card = self.dealer.hand[1]
            suit = self.suit_map[card.suit]
            rank = '10' if card.rank == '10' else card.rank
            filename = f"{suit}{rank}.png"
            base_img = Image.open(os.path.join(self.card_dir, filename))
        base_img = base_img.resize((self.card_width, self.card_height))
        rotated = base_img.rotate(degree, expand=True)
        return ImageTk.PhotoImage(rotated)
    
    def _dealer_hit_step(self):
        if self.dealer.should_hit():
            self._add_card_with_animation('dealer')
            self.master.after(1000, self._dealer_hit_step)
        else:
            self.compare_hands()

    # ========== 胜负判断 ==========
    def compare_hands(self):
        player_bj = len(self.player.hand) == 2 and 21 in self.player.hand_value()
        dealer_bj = len(self.dealer.hand) == 2 and self.dealer.hand_value() == 21
        
        if dealer_bj:
            if player_bj:
                self.player.money += self.player.bet
                msg = "双方Blackjack！平局！"
            else:
                msg = "庄家Blackjack！胜利！"
        elif player_bj:
            self.player.money += self.player.bet * 1.5
            msg = "玩家Blackjack！胜利！"
        else:
            p_max = max(v for v in self.player.hand_value() if v <= 21)
            d_total = self.dealer.hand_value()
            
            if d_total > 21:
                msg = "庄家爆牌！玩家胜利！"
                self.player.money += self.player.bet * 2
            elif p_max > d_total:
                msg = "玩家胜利！"
                self.player.money += self.player.bet * 2
            elif p_max < d_total:
                msg = "庄家胜利！"
            else:
                msg = "平局！"
                self.player.money += self.player.bet
        
        self.show_result(msg)

    # ========== 界面更新方法 ==========
    def get_card_image(self, card, show=True):
        """获取卡牌图像（带缓存）"""
        if not hasattr(self, 'image_cache'):
            self.image_cache = {}
        
        if not show or card is None:
            path = os.path.join(self.card_dir, "Background.png")
        else:
            filename = f"{self.suit_map[card.suit]}{card.rank}.png"
            path = os.path.join(self.card_dir, filename)
        
        if path not in self.image_cache:
            try:
                img = Image.open(path).resize((self.card_width, self.card_height))
                self.image_cache[path] = ImageTk.PhotoImage(img)
            except FileNotFoundError:
                messagebox.showerror("错误", f"缺少卡牌图像: {path}")
                return self.image_cache.get(os.path.join(self.card_dir, "Background.png"))
        
        return self.image_cache[path]

    def update_display(self):
        # 清除非动画标签
        for frame in [self.dealer_cards, self.player_cards]:
            for widget in frame.winfo_children():
                if not hasattr(widget, "is_animation"):
                    widget.destroy()
        
        if self.game_started:
            # 玩家牌始终明牌
            for card in self.player.hand:
                img = self.get_card_image(card, show=True)
                ttk.Label(self.player_cards, image=img).pack(side=tk.LEFT, padx=5)
            
            # 庄家牌显示逻辑
            for i, card in enumerate(self.dealer.hand):
                show = (i == 0) or self.game_over
                img = self.get_card_image(card, show=show)
                ttk.Label(self.dealer_cards, image=img).pack(side=tk.LEFT, padx=5)
        else:
            self._init_background_cards()  # 调用初始化背景卡牌方法
        
        self._update_value_labels()
        self.balance_var.set(f"{self.player.money:.2f}")

    def _update_value_labels(self):
        """更新点数显示，同时处理21点自动停牌（延时1.5秒）"""
        # 庄家点数
        if self.dealer.hand:
            dv = self.dealer.hand_value() if self.game_over else self.dealer.hand[0].value
            self.dealer_value_label.config(text=f"庄家点数: {dv}" + ("" if self.game_over else " + ?"))
        else:
            self.dealer_value_label.config(text="庄家点数: -")

        # 玩家点数
        if self.player.hand:
            p_values = self.player.hand_value()
            if len(self.player.hand) == 2 and 21 in p_values:
                p_text = "BJ"
                # 修改：延时1.5秒后自动调用停牌（仅调用一次）
                if not self.game_over and not self.animation_in_progress and not self.auto_stand_called:
                    self.auto_stand_called = True
                    self.master.after(1500, self.stand)
            else:
                p_text = "/".join(map(str, p_values))
            self.player_value_label.config(text=f"玩家点数: {p_text}")
        else:
            self.player_value_label.config(text="玩家点数: -")

    def update_controls(self):
        """综合更新所有操作按钮状态"""
        self.start_btn['state'] = tk.NORMAL if not self.game_started else tk.DISABLED
        
        base_state = tk.NORMAL if (self.game_started and not self.game_over 
                                and not self.animation_in_progress) else tk.DISABLED
        
        self.hit_btn['state'] = base_state
        self.stand_btn['state'] = base_state
        self.double_btn['state'] = base_state if (len(self.player.hand) == 2 and self.player.money >= self.player.bet) else tk.DISABLED
        self.surrender_btn['state'] = base_state if (len(self.player.hand) == 2) else tk.DISABLED
        
        if self.insurance_mode:
            self.hit_btn['state'] = tk.DISABLED
            self.stand_btn['state'] = tk.DISABLED
            self.double_btn['state'] = tk.DISABLED
            self.surrender_btn['state'] = tk.DISABLED

    # ========== 游戏结果处理 ==========
    def show_result(self, message):
        """显示游戏结果并处理余额动画（当玩家胜利时不使用messagebox）"""
        self.game_over = True
        self.update_display()
        # 如果是玩家胜利（包括Blackjack），则执行余额动画
        if ("玩家胜利" in message or "玩家Blackjack" in message) and "平局" not in message:
            self.animate_balance_update()
        else:
            messagebox.showinfo("游戏结果", message)
            self._reset_for_new_round()

    def animate_balance_update(self, duration=3000, interval=100):
        """余额动画：在duration毫秒内，每interval毫秒更新一次余额显示"""
        steps = duration // interval
        start_balance = self.starting_money - self.last_bet
        end_balance = self.player.money
        increment = (end_balance - start_balance) / steps
        current_step = 0
        def update_animation():
            nonlocal current_step
            if current_step < steps:
                new_balance = start_balance + increment * current_step
                self.balance_var.set(round(new_balance, 2))
                current_step += 1
                self.master.after(interval, update_animation)
            else:
                self.balance_var.set(end_balance)
                self._reset_for_new_round()
        update_animation()

    def _reset_for_new_round(self):
        """完整重置逻辑"""
        if self.username != "demo":
            update_balance_in_json(self.username, self.player.money)
        self.game_started = False
        self.game_over = True
        self.initial_background_shown = True
        self.insurance_mode = False
        self.new_round(reset_bet=False)
        self.update_display()
        self.update_controls()

if __name__ == "__main__":
    root = tk.Tk()
    game = BlackjackGUI(root, "demo", 1000)
    root.mainloop()