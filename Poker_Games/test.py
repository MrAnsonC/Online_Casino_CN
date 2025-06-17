import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import os
import time
import math

class DiceAnimationWindow:
    def __init__(self, parent, callback, final_dice):
        self.parent = parent
        self.callback = callback
        self.final_dice = final_dice  # 两个骰子的结果
        self.window = tk.Toplevel(parent)
        self.window.title("骰子摇动中...")
        self.window.geometry("400x350")
        self.window.configure(bg='#1e3d59')
        self.window.resizable(False, False)
        self.window.grab_set()

        # 窗口居中
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent_x + (parent_width - 400) // 2
        y = parent_y + (parent_height - 350) // 2
        self.window.geometry(f"400x350+{x}+{y}")

        # 生成骰子图片
        self.dice_images = []
        for i in range(1, 7):
            img = Image.new('RGB', (120, 120), '#e8d6b3')
            self.draw_dice(img, i)
            self.dice_images.append(ImageTk.PhotoImage(img))

        self.dice_container = tk.Frame(self.window, bg='#1e3d59')
        self.dice_container.pack(pady=50)

        self.dice_labels = []
        for _ in range(2):  # 两个骰子
            lbl = tk.Label(self.dice_container, image=self.dice_images[0], bg='#1e3d59', borderwidth=0)
            lbl.pack(side=tk.LEFT, padx=30)
            self.dice_labels.append(lbl)

        self.status_label = tk.Label(self.window, text="骰子摇动中...", font=("Arial", 18), fg='white', bg='#1e3d59')
        self.status_label.pack(pady=20)

        self.progress = ttk.Progressbar(self.window, orient=tk.HORIZONTAL, length=350, mode='determinate')
        self.progress.pack(pady=10)

        self.animation_start_time = time.time()
        self.animate_dice()

    def draw_dice(self, img, num):
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 119, 119], outline='#333', width=3)
        dot_color = '#333'
        dot_positions = {
            1: [(60, 60)],
            2: [(30, 30), (90, 90)],
            3: [(30, 30), (60, 60), (90, 90)],
            4: [(30, 30), (90, 30), (30, 90), (90, 90)],
            5: [(30, 30), (90, 30), (60, 60), (30, 90), (90, 90)],
            6: [(30, 30), (90, 30), (30, 60), (90, 60), (30, 90), (90, 90)]
        }
        for pos in dot_positions[num]:
            draw.ellipse([pos[0]-15, pos[1]-15, pos[0]+15, pos[1]+15], fill=dot_color)

    def animate_dice(self):
        elapsed = time.time() - self.animation_start_time
        if elapsed < 3:  # 3秒快速变化
            self.progress['value'] = min(100, (elapsed / 6) * 100)
            for lbl in self.dice_labels:
                v = random.randint(1, 6)
                lbl.config(image=self.dice_images[v-1])
            self.window.after(100, self.animate_dice)
        elif elapsed < 5:  # 2秒静止显示最终结果
            for i, lbl in enumerate(self.dice_labels):
                lbl.config(image=self.dice_images[self.final_dice[i]-1])
            self.status_label.config(text="骰子停止中...")
            self.window.after(100, self.animate_dice)
        elif elapsed < 7:  # 2秒显示结果
            total = sum(self.final_dice)
            txt = f"骰子结果: {self.final_dice[0]} + {self.final_dice[1]} = {total}"
            self.status_label.config(text=txt)
            self.window.after(100, self.animate_dice)
        else:
            self.window.destroy()
            self.callback()


class TuiTongziGame:
    """麻将推筒子游戏逻辑类"""
    def __init__(self):
        self.reset_game()
        
    def reset_game(self):
        """重置游戏"""
        # 创建两个牌堆（Deck1和Deck2），每个包含20张牌（1-9筒各4张，但只使用部分）
        self.deck1 = list(range(1, 10)) * 2  # 每个数字出现2次
        self.deck2 = list(range(1, 10)) * 2  # 每个数字出现2次
        self.shuffle_decks()
        self.history = []
        self.dice_value = 0
        self.banker_cards = []
        self.player1_cards = []
        self.player2_cards = []
        self.player3_cards = []
        self.winners = []
    
    def shuffle_decks(self):
        """洗牌"""
        random.shuffle(self.deck1)
        random.shuffle(self.deck2)
    
    def roll_dice(self):
        """掷骰子"""
        self.dice_value = random.randint(1, 6) + random.randint(1, 6)
        return self.dice_value
    
    def determine_dealing_order(self):
        """根据骰子点数确定发牌顺序"""
        if self.dice_value in [5, 9]:
            return ['banker', 'player1', 'player2', 'player3']
        elif self.dice_value in [2, 6, 10]:
            return ['player1', 'player2', 'player3', 'banker']
        elif self.dice_value in [3, 7, 11]:
            return ['player2', 'player3', 'banker', 'player1']
        elif self.dice_value in [4, 8, 12]:
            return ['player3', 'banker', 'player1', 'player2']
    
    def deal_cards(self):
        """根据顺序发牌"""
        order = self.determine_dealing_order()
        
        for position in order:
            if position == 'banker':
                self.banker_cards = [self.deck1.pop(0), self.deck2.pop(0)]
            elif position == 'player1':
                self.player1_cards = [self.deck1.pop(0), self.deck2.pop(0)]
            elif position == 'player2':
                self.player2_cards = [self.deck1.pop(0), self.deck2.pop(0)]
            elif position == 'player3':
                self.player3_cards = [self.deck1.pop(0), self.deck2.pop(0)]
    
    def is_pair(self, hand):
        """检查是否是对子"""
        return hand[0] == hand[1]
    
    def is_ebang(self, hand):
        """检查是否是二八杠 (2和8的组合)"""
        return sorted(hand) == [2, 8]
    
    def calculate_score(self, hand):
        """计算点数 (两张牌相加取个位数)"""
        return (hand[0] + hand[1]) % 10
    
    def compare_hands(self, player_hand, banker_hand):
        """比较玩家和庄家的牌"""
        # 检查二八杠
        player_ebang = self.is_ebang(player_hand)
        banker_ebang = self.is_ebang(banker_hand)
        
        if player_ebang and banker_ebang:
            return 'push'  # 平局
        elif player_ebang:
            return 'player'  # 玩家赢
        elif banker_ebang:
            return 'banker'  # 庄家赢
        
        # 检查对子
        player_pair = self.is_pair(player_hand)
        banker_pair = self.is_pair(banker_hand)
        
        if player_pair and banker_pair:
            # 比较对子大小
            if player_hand[0] > banker_hand[0]:
                return 'player'
            elif player_hand[0] < banker_hand[0]:
                return 'banker'
            else:
                return 'push'
        elif player_pair:
            return 'player'
        elif banker_pair:
            return 'banker'
        
        # 比较点数
        player_score = self.calculate_score(player_hand)
        banker_score = self.calculate_score(banker_hand)
        
        if player_score > banker_score:
            return 'player'
        elif player_score < banker_score:
            return 'banker'
        else:
            # 点数相同，比较最大单张
            player_max = max(player_hand)
            banker_max = max(banker_hand)
            
            if player_max > banker_max:
                return 'player'
            elif player_max < banker_max:
                return 'banker'
            else:
                # 最大单张相同，比较最小单张
                player_min = min(player_hand)
                banker_min = min(banker_hand)
                
                if player_min > banker_min:
                    return 'player'
                elif player_min < banker_min:
                    return 'banker'
                else:
                    return 'push'
    
    def determine_winners(self):
        """确定所有赢家"""
        self.winners = []
        
        # 比较庄家与每个玩家
        result1 = self.compare_hands(self.player1_cards, self.banker_cards)
        result2 = self.compare_hands(self.player2_cards, self.banker_cards)
        result3 = self.compare_hands(self.player3_cards, self.banker_cards)
        
        # 记录结果
        self.winners = [result1, result2, result3]
        
        return self.winners
    
    def calculate_payout(self, bet_amount, player_index):
        """计算赔付金额"""
        result = self.winners[player_index]
        player_hand = [self.player1_cards, self.player2_cards, self.player3_cards][player_index]
        
        if result == 'player':
            if self.is_pair(player_hand):
                return bet_amount * 2.29  # 对子获胜 229% (129%利润)
            else:
                return bet_amount * 1.99  # 普通获胜 199% (99%利润)
        elif result == 'push':
            return bet_amount  # 平局返还本金
        else:
            return 0  # 输牌
        
    def calculate_banker_payout(self, bet_amount):
        """计算庄家赔付金额"""
        win_count = sum(1 for result in self.winners if result == 'banker')
        push_count = sum(1 for result in self.winners if result == 'push')
        loss_count = 3 - win_count - push_count
        
        # 计算基础赔付
        if win_count == 0:
            return 0
        elif win_count == 1 and push_count == 0:
            return bet_amount  # 保本
        elif win_count == 1 and push_count == 1:
            return bet_amount  # 保本
        elif win_count == 1 and push_count == 2:
            return bet_amount * 1.48  # 赢48%
        elif win_count == 2 and push_count == 0:
            return bet_amount * 1.97  # 赢97%
        elif win_count == 2 and push_count == 1:
            return bet_amount * 2.46  # 赢146%
        elif win_count == 3:
            return bet_amount * 2.95  # 赢195%
        
        return 0
    
    def add_to_history(self):
        """添加当前结果到历史记录"""
        self.history.append({
            'banker': self.banker_cards.copy(),
            'player1': self.player1_cards.copy(),
            'player2': self.player2_cards.copy(),
            'player3': self.player3_cards.copy(),
            'results': self.winners.copy()
        })


class TuiTongziGUI(tk.Tk):
    """麻将推筒子游戏GUI - 左右布局"""
    def __init__(self, initial_balance=10000):
        super().__init__()
        self.title("麻将推筒子")
        self.geometry("1200x800")
        self.configure(bg='#35654d')
        
        # 游戏参数
        self.balance = initial_balance
        self.current_bets = {
            'banker': 0,
            'player1': 0,
            'player2': 0,
            'player3': 0
        }
        self.selected_bet_amount = 100
        self.card_images = {}
        self.back_image = None
        
        # 创建游戏实例
        self.game = TuiTongziGame()
        
        # 加载图片资源
        self.load_card_images()
        
        # 创建UI
        self.create_widgets()
        
        # 绑定事件
        self.bind('<Return>', lambda e: self.start_game())
    
    def load_card_images(self):
        """加载麻将牌图片"""
        # 获取当前脚本所在目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
        tile_dir = os.path.join(base_dir, 'Tuitong')
        
        # 确保目录存在
        if not os.path.exists(tile_dir):
            os.makedirs(tile_dir)
            messagebox.showwarning("图片目录创建", "已创建Tuitong目录，请放入麻将牌图片")
        
        # 加载牌面图片 (1-9筒)
        tile_size = (80, 120)
        for i in range(1, 10):
            img_path = os.path.join(tile_dir, f'{i}.jpg')
            if os.path.exists(img_path):
                try:
                    img = Image.open(img_path).resize(tile_size)
                    self.card_images[i] = ImageTk.PhotoImage(img)
                except:
                    self.card_images[i] = self.create_placeholder_image(i, tile_size)
            else:
                # 如果图片不存在，创建替代图片
                self.card_images[i] = self.create_placeholder_image(i, tile_size)
        
        # 加载背面图片
        back_path = os.path.join(tile_dir, 'bg.jpg')
        if os.path.exists(back_path):
            try:
                img = Image.open(back_path).resize(tile_size)
                self.back_image = ImageTk.PhotoImage(img)
            except:
                self.back_image = self.create_placeholder_image("B", tile_size)
        else:
            # 如果背面图片不存在，创建替代图片
            self.back_image = self.create_placeholder_image("B", tile_size)
    
    def create_placeholder_image(self, value, size):
        """创建替代图片 - 修复textsize问题"""
        img = Image.new('RGB', size, '#d9c8a9')
        draw = ImageDraw.Draw(img)
        
        # 尝试使用默认字体
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        # 在图片中心绘制值
        text = str(value)
        
        # 使用textbbox获取文本尺寸 (修复textsize问题)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
        draw.text(position, text, fill="black", font=font)
        
        return ImageTk.PhotoImage(img)
    
    def create_widgets(self):
        """创建游戏界面组件 - 左右布局"""
        # 主框架
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧游戏区域
        left_frame = tk.Frame(main_frame, bg='#35654d')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # 右侧控制区域
        right_frame = tk.Frame(main_frame, bg='#35654d', width=400)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        
        # ===== 左侧游戏区域 =====
        # 骰子区域
        dice_frame = tk.Frame(left_frame, bg='#35654d')
        dice_frame.pack(fill=tk.X, pady=10)
        
        self.dice_label = tk.Label(dice_frame, text="骰子点数: 等待开局", font=('Arial', 14), 
                                  bg='#35654d', fg='white')
        self.dice_label.pack(pady=5)
        
        # 牌桌区域
        table_frame = tk.Frame(left_frame, bg='#35654d', bd=2, relief=tk.RAISED)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 庄家区域
        banker_frame = tk.LabelFrame(table_frame, text="庄家", font=('Arial', 14, 'bold'), 
                                    bg='#35654d', fg='white')
        banker_frame.pack(side=tk.TOP, fill=tk.X, padx=20, pady=20)
        
        self.banker_canvas = tk.Canvas(banker_frame, width=300, height=150, bg='#2a4d3a', 
                                      highlightthickness=0)
        self.banker_canvas.pack(pady=10)
        
        # 玩家区域 (三列布局)
        players_frame = tk.Frame(table_frame, bg='#35654d')
        players_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=10)
        
        # 玩家1
        player1_frame = tk.LabelFrame(players_frame, text="闲家 1", font=('Arial', 12, 'bold'), 
                                     bg='#35654d', fg='white')
        player1_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        self.player1_canvas = tk.Canvas(player1_frame, width=200, height=150, bg='#2a4d3a', 
                                       highlightthickness=0)
        self.player1_canvas.pack(pady=10)
        
        self.player1_bet_label = tk.Label(player1_frame, text="下注: $0", font=('Arial', 10), 
                                         bg='#35654d', fg='white')
        self.player1_bet_label.pack()
        
        # 玩家2
        player2_frame = tk.LabelFrame(players_frame, text="闲家 2", font=('Arial', 12, 'bold'), 
                                     bg='#35654d', fg='white')
        player2_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        self.player2_canvas = tk.Canvas(player2_frame, width=200, height=150, bg='#2a4d3a', 
                                       highlightthickness=0)
        self.player2_canvas.pack(pady=10)
        
        self.player2_bet_label = tk.Label(player2_frame, text="下注: $0", font=('Arial', 10), 
                                         bg='#35654d', fg='white')
        self.player2_bet_label.pack()
        
        # 玩家3
        player3_frame = tk.LabelFrame(players_frame, text="闲家 3", font=('Arial', 12, 'bold'), 
                                     bg='#35654d', fg='white')
        player3_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        self.player3_canvas = tk.Canvas(player3_frame, width=200, height=150, bg='#2a4d3a', 
                                       highlightthickness=0)
        self.player3_canvas.pack(pady=10)
        
        self.player3_bet_label = tk.Label(player3_frame, text="下注: $0", font=('Arial', 10), 
                                         bg='#35654d', fg='white')
        self.player3_bet_label.pack()
        
        # 结果区域
        result_frame = tk.Frame(left_frame, bg='#35654d')
        result_frame.pack(side=tk.TOP, fill=tk.X, pady=10)
        
        self.result_label = tk.Label(result_frame, text="等待开局", font=('Arial', 16, 'bold'), 
                                    bg='#35654d', fg='gold')
        self.result_label.pack()
        
        # ===== 右侧控制区域 =====
        # 余额和筹码选择
        info_frame = tk.LabelFrame(right_frame, text="账户信息", font=('Arial', 12, 'bold'), 
                                 bg='#35654d', fg='white')
        info_frame.pack(fill=tk.X, pady=10, padx=5)
        
        self.balance_label = tk.Label(info_frame, text=f"余额: ${self.balance:,}", 
                                     font=('Arial', 12), bg='#35654d', fg='white')
        self.balance_label.pack(side=tk.TOP, padx=10, pady=5, anchor='w')
        
        self.chip_label = tk.Label(info_frame, text="筹码: $100", 
                                  font=('Arial', 12), bg='#35654d', fg='white')
        self.chip_label.pack(side=tk.TOP, padx=10, pady=5, anchor='w')
        
        chip_frame = tk.Frame(info_frame, bg='#35654d')
        chip_frame.pack(fill=tk.X, pady=10)
        
        chip_values = [10, 50, 100, 500, 1000]
        for value in chip_values:
            btn = tk.Button(chip_frame, text=f"${value}", width=5,
                           command=lambda v=value: self.select_chip(v),
                           bg='#d9c8a9', font=('Arial', 10))
            btn.pack(side=tk.LEFT, padx=5)
        
        # 下注区域
        bet_frame = tk.LabelFrame(right_frame, text="下注区域", font=('Arial', 12, 'bold'), 
                                 bg='#35654d', fg='white')
        bet_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        # 下注按钮
        bet_buttons_frame = tk.Frame(bet_frame, bg='#35654d')
        bet_buttons_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 第一排按钮：庄家和玩家
        row1_frame = tk.Frame(bet_buttons_frame, bg='#35654d')
        row1_frame.pack(fill=tk.X, pady=5)
        
        bet_types1 = [
            ("庄家", '#ffcc00'),
            ("闲家 1", '#6666ff'),
            ("闲家 2", '#6666ff'),
            ("闲家 3", '#6666ff'),
        ]
        
        for i, (text, color) in enumerate(bet_types1):
            btn = tk.Button(row1_frame, text=text, width=10, height=2,
                           command=lambda idx=i: self.place_bet(idx),
                           bg=color, font=('Arial', 12, 'bold'))
            btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 操作按钮
        action_frame = tk.Frame(bet_frame, bg='#35654d')
        action_frame.pack(fill=tk.X, pady=10)
        
        self.reset_btn = tk.Button(action_frame, text="重置下注", width=12,
                                  command=self.reset_bets, bg='#aaaaaa',
                                  font=('Arial', 12))
        self.reset_btn.pack(side=tk.LEFT, padx=5)
        
        self.deal_btn = tk.Button(action_frame, text="开牌 (Enter)", width=15,
                                 command=self.start_game, bg='#4CAF50',
                                 font=('Arial', 12, 'bold'))
        self.deal_btn.pack(side=tk.RIGHT, padx=5)
        
        # 历史记录区域
        history_frame = tk.LabelFrame(right_frame, text="历史记录", font=('Arial', 12, 'bold'), 
                                     bg='#35654d', fg='white')
        history_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        # 创建历史记录的Canvas和滚动条
        self.history_canvas = tk.Canvas(history_frame, bg='#2a4d3a', highlightthickness=0)
        scrollbar = ttk.Scrollbar(history_frame, orient="vertical", command=self.history_canvas.yview)
        self.history_canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.history_canvas.pack(side="left", fill="both", expand=True)
        
        # 创建用于历史记录的框架
        self.history_content = tk.Frame(self.history_canvas, bg='#2a4d3a')
        self.history_canvas.create_window((0, 0), window=self.history_content, anchor="nw")
        
        # 绑定Canvas大小变化事件
        self.history_content.bind("<Configure>", self.on_frame_configure)
    
    def on_frame_configure(self, event):
        """更新滚动区域"""
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
    
    def select_chip(self, amount):
        """选择筹码面额"""
        self.selected_bet_amount = amount
        self.chip_label.config(text=f"筹码: ${amount}")
    
    def place_bet(self, position_index):
        """下注"""
        position_map = {
            0: 'banker',
            1: 'player1',
            2: 'player2',
            3: 'player3'
        }
        
        position = position_map[position_index]
        
        if self.selected_bet_amount > self.balance:
            messagebox.showerror("余额不足", "您的余额不足以进行此下注！")
            return
        
        # 更新余额和下注信息
        self.balance -= self.selected_bet_amount
        self.current_bets[position] += self.selected_bet_amount
        
        # 更新UI
        self.update_balance()
        self.update_bet_info()
    
    def reset_bets(self):
        """重置下注"""
        # 返还所有下注金额
        for position, amount in self.current_bets.items():
            self.balance += amount
        
        # 清空下注
        self.current_bets = {
            'banker': 0,
            'player1': 0,
            'player2': 0,
            'player3': 0
        }
        
        # 更新UI
        self.update_balance()
        self.update_bet_info()
    
    def update_balance(self):
        """更新余额显示"""
        self.balance_label.config(text=f"余额: ${self.balance:,}")
    
    def update_bet_info(self):
        """更新下注信息显示"""
        self.player1_bet_label.config(text=f"下注: ${self.current_bets['player1']}")
        self.player2_bet_label.config(text=f"下注: ${self.current_bets['player2']}")
        self.player3_bet_label.config(text=f"下注: ${self.current_bets['player3']}")
    
    def start_game(self):
        """开始游戏"""
        if not any(self.current_bets.values()):
            messagebox.showwarning("未下注", "请先下注再开始游戏！")
            return
        
        # 禁用按钮
        self.deal_btn.config(state=tk.DISABLED)
        self.reset_btn.config(state=tk.DISABLED)
        
        # 重置结果显示
        self.result_label.config(text="游戏进行中...")
        
        # 检查是否需要重新洗牌
        if len(self.game.deck1) < 4 or len(self.game.deck2) < 4:
            self.game.reset_game()
            messagebox.showinfo("重新洗牌", "牌已用完，正在重新洗牌...")
        
        # 掷骰子
        dice_value = self.game.roll_dice()
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        
        # 显示骰子动画
        DiceAnimationWindow(self, self.after_dice_animation, [dice1, dice2])
    
    def after_dice_animation(self):
        """骰子动画结束后的回调函数"""
        # 更新骰子点数显示
        self.dice_label.config(text=f"骰子点数: {self.game.dice_value}")
        
        # 发牌
        self.game.deal_cards()
        
        # 显示牌面（背面）
        self.show_cards_back()
        
        # 延迟后显示牌面并结算
        self.after(1500, self.show_cards_and_settle)
    
    def show_cards_back(self):
        """显示牌背面"""
        # 庄家牌背面
        self.banker_canvas.delete("all")
        self.banker_canvas.create_image(100, 75, image=self.back_image)
        self.banker_canvas.create_image(200, 75, image=self.back_image)
        
        # 玩家牌背面
        self.player1_canvas.delete("all")
        self.player1_canvas.create_image(70, 75, image=self.back_image)
        self.player1_canvas.create_image(130, 75, image=self.back_image)
        
        self.player2_canvas.delete("all")
        self.player2_canvas.create_image(70, 75, image=self.back_image)
        self.player2_canvas.create_image(130, 75, image=self.back_image)
        
        self.player3_canvas.delete("all")
        self.player3_canvas.create_image(70, 75, image=self.back_image)
        self.player3_canvas.create_image(130, 75, image=self.back_image)
    
    def show_cards_and_settle(self):
        """显示牌面并结算"""
        # 显示庄家牌
        self.banker_canvas.delete("all")
        self.banker_canvas.create_image(100, 75, image=self.card_images[self.game.banker_cards[0]])
        self.banker_canvas.create_image(200, 75, image=self.card_images[self.game.banker_cards[1]])
        
        # 显示玩家牌
        self.player1_canvas.delete("all")
        self.player1_canvas.create_image(70, 75, image=self.card_images[self.game.player1_cards[0]])
        self.player1_canvas.create_image(130, 75, image=self.card_images[self.game.player1_cards[1]])
        
        self.player2_canvas.delete("all")
        self.player2_canvas.create_image(70, 75, image=self.card_images[self.game.player2_cards[0]])
        self.player2_canvas.create_image(130, 75, image=self.card_images[self.game.player2_cards[1]])
        
        self.player3_canvas.delete("all")
        self.player3_canvas.create_image(70, 75, image=self.card_images[self.game.player3_cards[0]])
        self.player3_canvas.create_image(130, 75, image=self.card_images[self.game.player3_cards[1]])
        
        # 确定赢家
        self.game.determine_winners()
        
        # 结算下注
        self.settle_bets()
        
        # 添加历史记录
        self.game.add_to_history()
        self.update_history()
        
        # 重新启用按钮
        self.deal_btn.config(state=tk.NORMAL)
        self.reset_btn.config(state=tk.NORMAL)
    
    def settle_bets(self):
        """结算下注"""
        total_winnings = 0
        
        # 结算庄家下注
        if self.current_bets['banker'] > 0:
            payout = self.game.calculate_banker_payout(self.current_bets['banker'])
            total_winnings += payout
            if payout > 0:
                self.result_label.config(text=f"庄家赢! 获得 ${payout:,.2f}", fg='gold')
        
        # 结算玩家下注
        for i, player in enumerate(['player1', 'player2', 'player3']):
            if self.current_bets[player] > 0:
                payout = self.game.calculate_payout(self.current_bets[player], i)
                total_winnings += payout
                
                if payout > self.current_bets[player]:
                    win_text = f"闲家 {i+1} 赢! 获得 ${payout:,.2f}"
                    if self.game.is_pair([self.game.player1_cards, self.game.player2_cards, self.game.player3_cards][i]):
                        win_text += " (对子获胜!)"
                    self.result_label.config(text=win_text, fg='#66ff66')
        
        # 更新余额
        self.balance += total_winnings
        self.update_balance()
        
        # 重置下注
        self.current_bets = {
            'banker': 0,
            'player1': 0,
            'player2': 0,
            'player3': 0
        }
        self.update_bet_info()
    
    def update_history(self):
        """更新历史记录显示"""
        # 清除旧的历史记录
        for widget in self.history_content.winfo_children():
            widget.destroy()
        
        # 添加标题行
        title_frame = tk.Frame(self.history_content, bg='#2a4d3a')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Label(title_frame, text="局数", width=6, bg='#2a4d3a', fg='white').pack(side=tk.LEFT)
        tk.Label(title_frame, text="庄家", width=15, bg='#2a4d3a', fg='white').pack(side=tk.LEFT)
        tk.Label(title_frame, text="闲家1", width=15, bg='#2a4d3a', fg='white').pack(side=tk.LEFT)
        tk.Label(title_frame, text="闲家2", width=15, bg='#2a4d3a', fg='white').pack(side=tk.LEFT)
        tk.Label(title_frame, text="闲家3", width=15, bg='#2a4d3a', fg='white').pack(side=tk.LEFT)
        
        # 添加历史记录行（从最新到最旧）
        for idx, record in enumerate(reversed(self.game.history)):
            if idx >= 10:  # 只显示最近10条记录
                break
                
            history_frame = tk.Frame(self.history_content, bg='#2a4d3a')
            history_frame.pack(fill=tk.X, pady=5)
            
            # 局数
            tk.Label(history_frame, text=f"{len(self.game.history)-idx}", width=6, 
                    bg='#2a4d3a', fg='white').pack(side=tk.LEFT)
            
            # 庄家牌
            banker_frame = tk.Frame(history_frame, bg='#ffcc66')  # 庄家背景色
            banker_frame.pack(side=tk.LEFT, padx=2)
            for card in record['banker']:
                img_label = tk.Label(banker_frame, image=self.card_images[card], bg='#ffcc66')
                img_label.pack(side=tk.LEFT)
            
            # 玩家牌（根据结果设置背景色）
            for i, player in enumerate(['player1', 'player2', 'player3']):
                result = record['results'][i]
                bg_color = '#ff9999' if result == 'banker' else '#99ccff' if result == 'player' else '#99ff99'
                
                player_frame = tk.Frame(history_frame, bg=bg_color)
                player_frame.pack(side=tk.LEFT, padx=2)
                for card in record[player]:
                    img_label = tk.Label(player_frame, image=self.card_images[card], bg=bg_color)
                    img_label.pack(side=tk.LEFT)
        
        # 更新滚动区域
        self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))


if __name__ == "__main__":
    app = TuiTongziGUI(initial_balance=10000)
    app.mainloop()