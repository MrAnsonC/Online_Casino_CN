import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageColor
import random
import json
import os, sys
import time

def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')

# 保存用户数据
def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# 读取用户数据
def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def update_balance_in_json(username, new_balance):
    users = load_user_data()  # 先加载现有用户数据
    for user in users:
        if user['user_name'] == username:  # 查找当前用户
            user['cash'] = f"{new_balance:.2f}"  # 更新余额
            break
    save_user_data(users)  # 保存更新后的数据

class Baccarat:
    def __init__(self, decks=8, external_deck=None):
        if external_deck:
            self.deck = [(card['suit'], card['rank']) for card in external_deck]
        else:
            self.deck = self.create_deck(decks)
            random.shuffle(self.deck)
            
        self.player_hand = []
        self.banker_hand = []
        self.player_score = 0
        self.banker_score = 0
        self.winner = None
        self.cut_position = 0
        self.used_cards = 0
        self.total_cards = 0
        self.create_deck(decks)
        random.shuffle(self.deck)

        self.high_bet_mode = False
        self._bet_limit_widgets = []
        
    def create_deck(self, decks=8):
        suits = ['Club', 'Diamond', 'Heart', 'Spade']
        ranks = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
        self.deck = [(suit, rank) for _ in range(decks) for suit in suits for rank in ranks]
        random.shuffle(self.deck)
        self.total_cards = len(self.deck)
        return self.deck

    def advanced_shuffle(self, cut_pos):
        self.deck = self.deck[cut_pos:] + self.deck[:cut_pos]
        first_card = self.deck[0]
        
        # 修复的扣除值计算逻辑
        deduct_map = {
            'A': 1, 'J': 10, 'Q': 10, 'K': 10, 
            '10': 10, '2':2, '3':3, '4':4, '5':5,
            '6':6, '7':7, '8':8, '9':9
        }
        
        # 安全获取扣除值
        deduct = deduct_map.get(first_card[1], 0)  # 默认扣除0张
        
        end_pos = (1 + deduct) % self.total_cards
        self.deck = self.deck[end_pos:] + self.deck[:end_pos]
        self.used_cards = random.randint(28, 48)
        self.cut_position = 0

    def card_value(self, card):
        rank = card[1]
        if rank in ['J','Q','K']: return 0
        if rank == 'A': return 1
        try:
            return int(rank)
        except:
            return 0

    def deal_initial(self):
        indices = [(self.cut_position + i) % self.total_cards for i in range(4)]
        self.player_hand = [self.deck[indices[0]], self.deck[indices[2]]]
        self.banker_hand = [self.deck[indices[1]], self.deck[indices[3]]]
        self.cut_position = (self.cut_position + 4) % self.total_cards

    def calculate_score(self, hand):
        return sum(self.card_value(c) for c in hand) % 10

    def play_game(self):
        self.deal_initial()
        p_initial = self.calculate_score(self.player_hand[:2])
        b_initial = self.calculate_score(self.banker_hand[:2])

        if p_initial >= 8 or b_initial >= 8:
            self.player_score = p_initial
            self.banker_score = b_initial
        else:
            if p_initial <= 5:
                self.player_hand.append(self.deck.pop())
            self._banker_draw_logic()

        self._determine_winner()

    def _banker_draw_logic(self):
        b_score = self.calculate_score(self.banker_hand[:2])
        if len(self.player_hand) == 2:
            if b_score <= 5:
                self.banker_hand.append(self.deck.pop())
        else:
            third_val = self.card_value(self.player_hand[2])
            if b_score <= 2:
                self.banker_hand.append(self.deck.pop())
            elif b_score == 3 and third_val != 8:
                self.banker_hand.append(self.deck.pop())
            elif b_score == 4 and 2 <= third_val <= 7:
                self.banker_hand.append(self.deck.pop())
            elif b_score == 5 and 4 <= third_val <= 7:
                self.banker_hand.append(self.deck.pop())
            elif b_score == 6 and 6 <= third_val <= 7:
                self.banker_hand.append(self.deck.pop())

    def _determine_winner(self):
        self.player_score = self.calculate_score(self.player_hand)
        self.banker_score = self.calculate_score(self.banker_hand)
        if self.player_score > self.banker_score:
            self.winner = 'Player'
        elif self.banker_score > self.player_score:
            self.winner = 'Banker'
        else:
            self.winner = 'Tie'

class BaccaratGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("百家乐")
        self.geometry("1350x700+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')

        self.data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../', 'A_Logs')
        self.data_file = os.path.join(self.data_dir, 'Baccarant.json')
        self._ensure_data_file()
        
        self.bet_buttons = []
        self.selected_chip = None
        self.chip_buttons = []
        self.result_text_id = None
        self.result_bg_id = None

        self.game_mode = "classic"
        self.game = Baccarat()
        self.balance = initial_balance
        self.current_bets = {}
        self.card_images = {}

        # 新增連勝記錄追蹤屬性
        self.current_streak = 0
        self.current_streak_type = None
        self.longest_streaks = {
            'Player': 0,
            'Tie': 0,
            'Banker': 0
        }

        # 新增对子统计属性
        self.pair_stats = {
            'player_only': 0,   # 只有玩家对子
            'banker_only': 0,   # 只有庄家对子  
            'both_diff': 0,     # 双方对子但点数不同
            'both_same': 0      # 双方对子且点数相同
        }
        
        # 加載最長連勝記錄
        self._load_longest_streaks()

        # 添加累进大奖属性
        self.jackpot_amount = 5000000
        self.jackpot_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
        self._load_jackpot()

        # 新增珠路图相关属性
        self.marker_results = []  # 存储每局结果
        self.marker_counts = {
            'Player': 0,
            'Banker': 0,
            'Tie': 0,
            'Small Tiger': 0,
            'Tiger Tie': 0,
            'Big Tiger': 0,
            'Panda 8': 0,
            'Divine 9': 0,
            'Dragon 7': 0,
            'P Fabulous 4': 0,
            'B Fabulous 4': 0,
            'Player 7': 0,
            'Player 7 Banker 6': 0,
            'Banker 6': 0,
            'Monkey 6': 0,
            'Monkey Tie': 0,
            'Monkey 7': 0
        }

        self.max_marker_rows = 6  # 最大行数
        self.max_marker_cols = 11  # 最大列数
        self.view_mode = "marker"  # 默认显示珠路图
        self.bigroad_results = []
        self._max_rows = 6
        self._max_cols = 50
        self._bigroad_occupancy = [[False]*self._max_cols for _ in range(self._max_rows)]
        
        self._load_assets()
        self._create_widgets()
        self._setup_bindings()
        self.point_labels = {}
        self._player_area = (200, 150, 400, 350)  # 调整扑克牌区域位置
        self._banker_area = (600, 150, 800, 350)  # 调整扑克牌区域位置
        self.selected_bet_amount = 1000
        self.current_bet = 0
        self.last_win = 0
        self.game = None
        self.username = username
        self.protocol("WM_DELETE_WINDOW", self.on_close)
   
        self._initialize_game(False)
        
    def on_close(self):
        self.destroy()
        self.quit()

    def _get_high_bet_password(self):
        return time.strftime("%H%M")

    def _get_bet_limits(self):
        """根据当前模式返回下注上限"""
        if getattr(self, "high_bet_mode", False):
            return {
                "side": 100_000,   # 边注
                "tie": 300_000,    # 和局
                "main": 1_500_000  # 闲/庄
            }
        return {
            "side": 30_000,
            "tie": 100_000,
            "main": 500_000
        }

    def _update_bet_limit_display(self):
        """刷新上限显示文字"""
        if not hasattr(self, "limit_value_labels"):
            return

        limits = self._get_bet_limits()
        values = [
            f"{limits['side']:,}",
            f"{limits['tie']:,}",
            f"{limits['main']:,}"
        ]

        for lbl, txt in zip(self.limit_value_labels, values):
            try:
                lbl.config(text=txt)
            except Exception:
                pass

        if hasattr(self, "high_bet_button"):
            try:
                if self.high_bet_mode:
                    self.high_bet_button.config(text="恢复原始下注上限")
                else:
                    self.high_bet_button.config(text="高额下注")
            except Exception:
                pass

    def _toggle_high_bet_limits(self, event=None):
        if not getattr(self, "high_bet_mode", False):
            password = simpledialog.askstring(
                "高额下注",
                "请输入密码：",
                parent=self
            )
            if password is None:
                return

            if password.strip() != self._get_high_bet_password():
                return

            self.high_bet_mode = True
        else:
            self.high_bet_mode = False

        self._update_bet_limit_display()

    def _load_jackpot(self):
        """读取累进大奖金额 - 如果文件不存在，使用默认值"""
        try:
            if os.path.exists(self.jackpot_file):
                with open(self.jackpot_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 查找BCT游戏的数据
                    if isinstance(data, list):
                        # JSON数组格式
                        for game_data in data:
                            if game_data.get('Games') == 'BCT':
                                self.jackpot_amount = game_data.get('jackpot', 5000000)
                                break
                        else:
                            # 如果找不到BCT数据，使用默认值
                            self.jackpot_amount = 5000000
                    elif isinstance(data, dict):
                        # 单个对象格式
                        if data.get('Games') == 'BCT':
                            self.jackpot_amount = data.get('jackpot', 5000000)
                        else:
                            self.jackpot_amount = 5000000
                    else:
                        self.jackpot_amount = 5000000
            else:
                # 文件不存在，使用默认值
                self.jackpot_amount = 5000000
        except (json.JSONDecodeError, KeyError, IndexError, Exception):
            # 如果读取失败，使用默认值
            self.jackpot_amount = 5000000

    def _save_jackpot(self):
        """保存累进大奖金额 - 只更新BCT游戏的数据"""
        try:
            # 读取现有数据或创建新数据
            if os.path.exists(self.jackpot_file):
                with open(self.jackpot_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []
            
            # 确保data是列表
            if not isinstance(data, list):
                data = []
            
            # 查找并更新BCT游戏的数据
            found = False
            for i, game_data in enumerate(data):
                if isinstance(game_data, dict) and game_data.get('Games') == 'BCT':
                    data[i]['jackpot'] = self.jackpot_amount
                    found = True
                    break
            
            # 如果没找到BCT数据，添加新的
            if not found:
                data.append({
                    "Games": "BCT",
                    "jackpot": self.jackpot_amount
                })
            
            # 写回文件
            with open(self.jackpot_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
        except Exception as e:
            # 如果保存失败，只在内存中保存，不写入文件
            print(f"保存jackpot失败: {e}")

    def _update_jackpot(self, bet_amount):
        """更新累进大奖 - 每局下注的1%加入奖池"""
        jackpot_increase = bet_amount * 0.01
        self.jackpot_amount += jackpot_increase
        self._save_jackpot()
        
        # 确保奖池不低于500万
        if self.jackpot_amount < 5000000:
            self.jackpot_amount = 5000000
        
        # 更新界面显示
        self._update_jackpot_display()

    def _update_jackpot_display(self):
        """更新累进大奖显示"""
        if hasattr(self, 'jackpot_major_label') and self.jackpot_major_label.winfo_exists():
            # 修改这两行的显示格式，添加.2f显示两位小数
            self.jackpot_major_label.config(text=f"大奖: ${self.jackpot_amount:,.2f}")
            self.jackpot_minor_label.config(text=f"次奖: ${(self.jackpot_amount * 0.03):,.2f}")

    def show_game_instructions(self):
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("游戏说明")
        win.geometry("900x700")
        win.resizable(False, False)
        
        # 计算窗口居中位置
        self.update_idletasks()  # 确保获取正确的窗口尺寸
        
        # 获取主窗口位置和尺寸
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_width = self.winfo_width()
        main_height = self.winfo_height()
        
        # 获取弹窗尺寸
        popup_width = 900
        popup_height = 700
        
        # 计算居中位置
        x = main_x + (main_width - popup_width) // 2
        y = main_y + (main_height - popup_height) // 2
        
        # 设置弹窗位置
        win.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        
        # 创建主框架和滚动条
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建画布和滚动条
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#F0F0F0')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 打包画布和滚动条
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # ===== 第一部分：基本玩法（文字） =====
        basic_rules_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        basic_rules_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(
            basic_rules_frame,
            text="🎮 百家乐基本玩法",
            font=('微软雅黑', 16, 'bold'),
            bg='#F0F0F0',
            fg='#2E86AB'
        ).pack(anchor='w', pady=(0, 10))
        
        basic_rules_text = """
        百家乐是一种比较扑克牌点数的赌博游戏，目标是预测哪一方的手牌点数最接近9点，
        或者双方是否以相同点数打成平局。

        【游戏流程】
        1. 玩家在闲家、庄家或和局下注
        2. 双方各发2张牌，根据需要可能补发第三张牌
        3. 计算双方牌面点数，最接近9点的一方获胜
        4. 点数计算：A=1点，2-9按面值计算，10/J/Q/K=0点
        5. 如果总点数超过9，只取个位数（如7+8=15→5点）

        【胜负判定】
        • 闲家胜：闲家点数大于庄家点数
        • 庄家胜：庄家点数大于闲家点数  
        • 和局：双方点数相同
        • 如果任何一方前两张牌点数为8或9（天牌），双方都不补牌
            """
        
        basic_label = tk.Label(
            basic_rules_frame,
            text=basic_rules_text,
            font=('微软雅黑', 14),
            bg='#F0F0F0',
            justify=tk.LEFT,
            wraplength=850
        )
        basic_label.pack(fill=tk.X, padx=10)

        # ===== 第二部分：补牌规则（三个表格） =====
        drawing_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        drawing_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(
            drawing_frame,
            text="⚡ 补牌规则表",
            font=('微软雅黑', 14, 'bold'),
            bg='#F0F0F0',
            fg='#A23B72'
        ).pack(anchor='w', pady=(0, 10))

        # ===== 表格1：闲家补牌处理 =====
        player_drawing_frame = tk.Frame(drawing_frame, bg='#F0F0F0')
        player_drawing_frame.pack(fill=tk.X, padx=10, pady=(0, 15))

        tk.Label(
            player_drawing_frame,
            text="🎯 闲家补牌规则",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0',
            fg='#2E86AB'
        ).pack(anchor='w', pady=(0, 8))

        # 闲家补牌规则表头
        player_headers = ["初始点数", "补牌规则", "备注"]
        player_data = [
            ("0-5点", "必须补一张牌", "强制补牌"),
            ("6-7点", "停止补牌", "停牌"),
            ("8-9点", "自然赢，不补牌", "天牌")
        ]

        # 创建闲家补牌规则表格
        player_table = tk.Frame(player_drawing_frame, bg='#F0F0F0')
        player_table.pack(fill=tk.X)

        # 表头
        for col, header in enumerate(player_headers):
            tk.Label(
                player_table,
                text=header,
                font=('微软雅黑', 16, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=12, pady=8,
                anchor='center',
                width=18
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(player_data, start=1):
            bg = '#E8F4FD' if r % 2 == 0 else '#FFFFFF'
            for c, txt in enumerate(row_data):
                tk.Label(
                    player_table,
                    text=txt,
                    font=('微软雅黑', 14),
                    bg=bg,
                    padx=12, pady=6,
                    anchor='center',
                    width=18
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配列宽度
        for c in range(len(player_headers)):
            player_table.columnconfigure(c, weight=1)

        # ===== 表格2：庄家在闲家没有补牌下的处理 =====
        banker_no_draw_frame = tk.Frame(drawing_frame, bg='#F0F0F0')
        banker_no_draw_frame.pack(fill=tk.X, padx=10, pady=(0, 15))

        tk.Label(
            banker_no_draw_frame,
            text="🎯 庄家补牌规则（闲家没有补牌）",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0',
            fg='#A23B72'
        ).pack(anchor='w', pady=(0, 8))

        # 庄家无补牌规则表头
        banker_no_draw_headers = ["庄家初始点数", "补牌规则", "备注"]
        banker_no_draw_data = [
            ("0-5点", "必须补一张牌", "强制补牌"),
            ("6-7点", "停止补牌", "停牌"),
            ("8-9点", "自然赢，不补牌", "天牌")
        ]

        # 创建庄家无补牌规则表格
        banker_no_draw_table = tk.Frame(banker_no_draw_frame, bg='#F0F0F0')
        banker_no_draw_table.pack(fill=tk.X)

        # 表头
        for col, header in enumerate(banker_no_draw_headers):
            tk.Label(
                banker_no_draw_table,
                text=header,
                font=('微软雅黑', 16, 'bold'),
                bg='#A23B72',
                fg='white',
                padx=12, pady=8,
                anchor='center',
                width=18
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(banker_no_draw_data, start=1):
            bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
            for c, txt in enumerate(row_data):
                tk.Label(
                    banker_no_draw_table,
                    text=txt,
                    font=('微软雅黑', 14),
                    bg=bg,
                    padx=12, pady=6,
                    anchor='center',
                    width=18
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配列宽度
        for c in range(len(banker_no_draw_headers)):
            banker_no_draw_table.columnconfigure(c, weight=1)

        # ===== 表格3：庄家在闲家有补牌下的处理 =====
        banker_with_draw_frame = tk.Frame(drawing_frame, bg='#F0F0F0')
        banker_with_draw_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Label(
            banker_with_draw_frame,
            text="🎯 庄家补牌规则（闲家有补牌）",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0',
            fg='#F18F01'
        ).pack(anchor='w', pady=(0, 8))

        # 庄家有补牌规则表头
        banker_with_draw_headers = ["庄家初始点数", "闲家第三张牌条件", "备注"]
        banker_with_draw_data = [
            ("0-2点", "任何牌", "强制补牌"),
            ("3点", "不是8点", "闲家第三张是8点则不补"),
            ("4点", "2-7点", "闲家第三张是0-1、8-9点则不补"),
            ("5点", "4-7点", "闲家第三张是0-3、8-9点则不补"),
            ("6点", "6-7点", "闲家第三张是0-5、8-9点则不补"),
            ("7点", "任何牌", "停止补牌")
        ]

        # 创建庄家有补牌规则表格
        banker_with_draw_table = tk.Frame(banker_with_draw_frame, bg='#F0F0F0')
        banker_with_draw_table.pack(fill=tk.X)

        # 表头
        for col, header in enumerate(banker_with_draw_headers):
            tk.Label(
                banker_with_draw_table,
                text=header,
                font=('微软雅黑', 16, 'bold'),
                bg='#F18F01',
                fg='white',
                padx=10, pady=8,
                anchor='center',
                width=15
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(banker_with_draw_data, start=1):
            bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
            for c, txt in enumerate(row_data):
                tk.Label(
                    banker_with_draw_table,
                    text=txt,
                    font=('微软雅黑', 14),
                    bg=bg,
                    padx=10, pady=6,
                    anchor='center',
                    width=15
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配列宽度
        for c in range(len(banker_with_draw_headers)):
            banker_with_draw_table.columnconfigure(c, weight=1)

        # 补牌规则说明文字
        drawing_explanation = tk.Label(
            drawing_frame,
            text="💡 说明：当闲家前两张牌点数为8或9点（天牌）时，双方都不补牌，直接比较点数决定胜负。",
            font=('微软雅黑', 14),
            bg='#F0F0F0',
            fg='#666666',
            justify=tk.LEFT,
            wraplength=850
        )
        drawing_explanation.pack(fill=tk.X, padx=10, pady=(15, 0))

        # ===== 第三部分：当前模式特色玩法（文字） =====
        special_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        special_frame.pack(fill=tk.X, padx=10, pady=10)

        # 根据游戏模式设置特色标题和内容
        if self.game_mode == "classic":
            special_title = "🎯 经典百家乐特色玩法"
            special_text = """
        经典百家乐是最传统的玩法，保持原始的游戏规则和赔率结构。

        【主要特色】
        • 庄家获胜时支付0.95:1，收取5%佣金
        • 提供多种边注选项，包括对子和龙宝投注
        • 龙宝投注根据赢方点数差提供不同赔率
        • 快合投注基于双方点数总和提供特殊赔率
                """
        elif self.game_mode == "tiger":
            special_title = "🐯 老虎百家乐特色玩法"
            special_text = """
        老虎百家乐以庄家6点获胜时的特殊赔付规则为特色，增加了游戏的刺激性。

        【主要特色】
        • 庄家以6点获胜时赔付降低为50%
        • 引入老虎系列边注：小老虎、大老虎、老虎和
        • 老虎对子投注提供三种不同层级的赔率
        • 专门针对庄家6点情况的多种投注选项
                """
        elif self.game_mode == "ez":
            special_title = "🎪 简单百家乐特色玩法"
            special_text = """
        简单百家乐取消了庄家佣金，但引入了特殊的平局规则和特色边注。

        【主要特色】
        • 取消庄家5%佣金，庄家赔率为1:1
        • 庄家以3张牌7点获胜时视为平局
        • 引入熊猫8点、神之9点、金龙7点等特色边注
        • 猴子系列投注基于特殊牌型组合
                """
        elif self.game_mode == "2to1":
            special_title = "💰 1赔2百家乐特色玩法"
            special_text = """
        1赔2百家乐在主注获胜条件上增加了特殊赔付，提高了获胜时的回报。

        【主要特色】
        • 闲家或庄家以3张牌8点或9点获胜时赔付2:1
        • 和局时主注视为输注，不退还本金
        • 保留经典百家乐的所有边注选项
        • 高风险高回报的游戏体验
                """
        elif self.game_mode == "fabulous4":
            special_title = "✨ 神奇4点百家乐特色玩法"
            special_text = """
        神奇4点百家乐专注于4点获胜时的特殊规则，增加了策略性和趣味性。

        【主要特色】
        • 以1点获胜时赔付2:1
        • 闲家以4点获胜时赔付0.5:1
        • 庄家以4点获胜时视为平局
        • 引入神奇对子系列投注，区分同花和非同花
        • 专门的神奇4点边注提供高额赔率
                """
        elif self.game_mode == "lucky7":
            special_title = "🍀 幸运7百家乐特色玩法"
            special_text = """
        幸运7百家乐围绕数字7和6设计特色玩法，并引入大奖机制。

        【主要特色】
        • 闲家7点获胜时的特殊赔率
        • 庄家6点获胜时的分级赔付
        • 闲家7点杀庄家6点的超级7投注
        • 下注超级7自动参与大奖
        • 多种幸运6和幸运7边注选项
                """
        elif self.game_mode == "monkey":
            special_title = "🐵 猴子百家乐特色玩法"
            special_text = """
        猴子百家乐以猴子牌（J、Q、K）的特殊规则为核心，增加了游戏的趣味性和策略性。

        【主要特色】
        • 庄家以3张牌7点获胜时触发猴7点赔付
        • 闲家补牌不是猴子牌且庄家补牌是猴子牌时触发猴老六
        • 猴老六条件下出现和局时触发猴老六和
        • 双方6张牌都是猴子牌时触发猴子六仙大奖
        • 新增幸运猴子边注，根据补牌情况提供多级赔付
        • 保留经典对子投注选项
                """

        tk.Label(
            special_frame,
            text=special_title,
            font=('微软雅黑', 16, 'bold'),
            bg='#F0F0F0',
            fg='#F18F01'
        ).pack(anchor='w', pady=(0, 10))

        special_label = tk.Label(
            special_frame,
            text=special_text,
            font=('微软雅黑', 14),
            bg='#F0F0F0',
            justify=tk.LEFT,
            wraplength=850
        )
        special_label.pack(fill=tk.X, padx=10)

        # ===== 第四部分：当前模式赔率表（表格） =====
        payout_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        payout_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(
            payout_frame,
            text="💰 赔率表",
            font=('微软雅黑', 16, 'bold'),
            bg='#F0F0F0',
            fg='#C73E1D'
        ).pack(anchor='w', pady=(0, 10))

        # 根据游戏模式设置赔率表
        if self.game_mode == "classic":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "0.95:1", "庄家获胜（抽水5%）"),
                ("龙宝", "1-30:1", "根据自然点数或点数差获胜"),
                ("快合", "1-50:1", "两家牌最终点数相加 符合获胜要求"),
                ("闲家对子", "11:1", "闲家前两张牌点数相同"),
                ("庄家对子", "11:1", "庄家前两张牌点数相同"),
                ("任意对子", "5:1", "任一方前两张牌点数相同")
            ]
            
            # 龙宝赔率详细说明
            dragon_headers = ["点数差", "闲家龙宝赔率", "庄家龙宝赔率"]
            dragon_data = [
                ("自然点和", "退还", "退还"),
                ("自然点赢", "1:1", "1:1"),
                ("4点", "1:1", "1:1"),
                ("5点", "2:1", "2:1"),
                ("6点", "4:1", "4:1"),
                ("7点", "6:1", "6:1"),
                ("8点", "10:1", "10:1"),
                ("9点", "30:1", "30:1")
            ]
            
            # 快合赔率详细说明
            quik_headers = ["点数总和", "赔率"]
            quik_data = [
                ("0点", "50:1"),
                ("18点", "25:1"),
                ("1、2、3、15、16、17点", "1:1")
            ]
            
        elif self.game_mode == "tiger":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "1:1*", "庄家获胜（6点赔付50%）"),
                ("小老虎", "22:1", "庄家2张牌6点获胜"),
                ("老虎和", "35:1", "和局且闲家庄家6点"),
                ("大老虎", "50:1", "庄家3张牌6点获胜"),
                ("老虎", "12(20):1", "庄家2(3)张牌6点获胜"),
                ("虎对子", "4/20/100:1", "对子投注")
            ]
            
            # 老虎对子详细说明
            tiger_pair_headers = ["对子类型", "赔率"]
            tiger_pair_data = [
                ("单方对子", "4:1"),
                ("双方不同对子", "20:1"),
                ("双方相同对子", "100:1")
            ]
            
        elif self.game_mode == "ez":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "1:1*", "庄家获胜（3张牌7点获胜 平局）"),
                ("龙宝", "1-30:1", "根据自然点数或点数差获胜"),
                ("熊猫8点", "25:1", "闲家3张牌8点获胜"),
                ("神之9点", "10/75:1", "9点获胜"),
                ("金龙7点", "40:1", "庄家3张牌7点获胜"),
                ("闲家对子", "11:1", "闲家前两张牌点数相同"),
                ("庄家对子", "11:1", "庄家前两张牌点数相同")
            ]

            # 龙宝赔率详细说明
            dragon_headers = ["点数差", "闲家龙宝赔率", "庄家龙宝赔率"]
            dragon_data = [
                ("自然点和", "退还", "退还"),
                ("自然点赢", "1:1", "1:1"),
                ("4点", "1:1", "1:1"),
                ("5点", "2:1", "2:1"),
                ("6点", "4:1", "4:1"),
                ("7点", "6:1", "6:1"),
                ("8点", "10:1", "10:1"),
                ("9点", "30:1", "30:1")
            ]
            
            # 神之9点详细说明
            divine_headers = ["获胜情况", "赔率"]
            divine_data = [
                ("闲家3张牌9点获胜", "10:1"),
                ("庄家3张牌9点获胜", "10:1"),
                ("双方3张牌9点和局", "75:1")
            ]
            
        elif self.game_mode == "2to1":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1*", "闲家获胜（3张牌8/9点2:1）"),
                ("和局", "8:1", "和局（主注输）"),
                ("庄家", "1:1*", "庄家获胜（3张牌8/9点2:1）"),
                ("龙宝", "1-30:1", "根据自然点数或点数差获胜"),
                ("闲家对子", "11:1", "闲家前两张牌点数相同"),
                ("庄家对子", "11:1", "庄家前两张牌点数相同"),
                ("任意对子", "5:1", "任一方前两张牌点数相同")
            ]

            # 龙宝赔率详细说明
            dragon_headers = ["点数差", "闲家龙宝赔率", "庄家龙宝赔率"]
            dragon_data = [
                ("自然点和", "退还", "退还"),
                ("自然点赢", "1:1", "1:1"),
                ("4点", "1:1", "1:1"),
                ("5点", "2:1", "2:1"),
                ("6点", "4:1", "4:1"),
                ("7点", "6:1", "6:1"),
                ("8点", "10:1", "10:1"),
                ("9点", "30:1", "30:1")
            ]
            
            # 快合赔率详细说明
            quik_headers = ["点数总和", "赔率"]
            quik_data = [
                ("0点", "50:1"),
                ("18点", "25:1"),
                ("1、2、3、15、16、17点", "1:1")
            ]
            
        elif self.game_mode == "fabulous4":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1*", "主注分级赔付"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "1:1*", "主注分级赔付"),
                ("龙宝", "1-30:1", "根据自然点数或点数差获胜"),
                ("闲家神对", "1-7:1", "分级对子赔付"),
                ("庄家神对", "1-7:1", "分级对子赔付"),
                ("闲神4点", "50:1", "闲家以4点获胜"),
                ("庄神4点", "25:1", "庄家以4点获胜")
            ]
            
            # 神奇对子详细说明
            fab_pair_headers = ["对子类型", "赔率"]
            fab_pair_data = [
                ("同花对子", "7:1"),
                ("非同花对子", "4:1"),
                ("同花非对子", "1:1")
            ]
            
        elif self.game_mode == "lucky7":
            payout_headers = ["投注类型", "赔率", "说明", "大奖参与"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜", "-"),
                ("和局", "8:1", "双方点数相同", "-"),
                ("庄家", "1:1*", "庄家获胜（6点赔付50%）", "-"),
                ("小幸运6", "22:1", "庄家2张牌6点获胜", "-"),
                ("幸运6", "12(20):1", "庄家2(3)张牌6点获胜", "-"),
                ("大幸运6", "50:1", "庄家3张牌6点获胜", "-"),
                ("闲对", "11:1", "闲家前两张牌点数相同", "-"),
                ("幸运7", "6/15:1", "闲家7点获胜", "-"),
                ("超级7", "30/40/100:1", "闲家7点庄家6点", "下注1千或以上参与"),
                ("庄对", "11:1", "庄家前两张牌点数相同", "-")
            ]
            
            # 幸运6和幸运7详细说明
            lucky67_headers = ["获胜情况", "赔率"]
            lucky67_data = [
                ("庄家2张牌6点", "12:1（幸运6）"),
                ("庄家3张牌6点", "20:1（幸运6）"),
                ("闲家2张牌7点", "6:1（幸运7）"),
                ("闲家3张牌7点", "15:1（幸运7）")
            ]
            
            # 超级7详细说明
            super7_headers = ["总牌数", "超级7赔率"]
            super7_data = [
                ("4张牌", "30:1"),
                ("5张牌", "40:1"),
                ("6张牌", "100:1")
            ]

            # 超级7大奖说明
            super7_progressive_headers = ["闲家扑克牌要求", "庄家扑克牌要求", "百分比"]
            super7_progressive_data = [
                ("3张方片♦共7点", "3张黑桃♠共6点", "100%大奖"),
                ("3张红色共7点", "3张黑色共6点", "100%次奖")
            ]

        elif self.game_mode == "monkey":
            payout_headers = ["投注类型", "赔率", "说明"]
            payout_data = [
                ("闲家", "1:1", "闲家获胜"),
                ("和局", "8:1", "双方点数相同"),
                ("庄家", "1:1*", "庄家获胜（3张牌7点平局）"),
                ("猴老六", "12:1", "闲家补牌不是猴子 庄家补牌是猴子"),
                ("猴老六和", "150:1", "满足猴老六条件 + 本局结果为和局"),
                ("猴子六仙", "5000:1", "闲家庄家6张牌都是猴子牌"),
                ("猴7点", "40:1", "庄家3张牌7点获胜"),
                ("幸运猴子", "1-75:1", "根据补牌情况多级赔付"),  # 新增幸运猴子
                ("闲家对子", "11:1", "闲家前两张牌点数相同"),
                ("庄家对子", "11:1", "庄家前两张牌点数相同")
            ]
            
            # 猴子牌定义说明
            monkey_def_headers = ["猴子牌类型", "牌面", "说明"]
            monkey_def_data = [
                ("猴子牌", "J、Q、K", "所有花色的J、Q、K都算猴子牌")
            ]
            
            # 猴子边注触发条件说明
            monkey_trigger_headers = ["边注类型", "触发条件"]
            monkey_trigger_data = [
                ("猴老六", "闲家补牌不是猴子牌 + 庄家补牌是猴子牌"),
                ("猴老六和", "满足猴老六条件 + 本局结果为和局"),
                ("猴子六仙", "闲家3张牌 + 庄家3张牌 = 6张牌都是猴子牌"),
                ("猴7点", "庄家3张牌组成7点并获胜"),
                ("幸运猴子", "根据双方补牌是否为猴子牌决定赔付等级")  # 新增幸运猴子说明
            ]

            # 幸运猴子详细赔率说明
            lucky_monkey_headers = ["补牌情况", "赔付条件", "赔率"]
            lucky_monkey_data = [
                ("双方都补牌", "只有一方是猴子", "1:1"),
                ("仅闲家补牌", "补牌为猴子", "3:1"),
                ("仅庄家补牌", "补牌为猴子", "8:1"),
                ("双方都补牌", "双方都是猴子", "10:1"),
                ("双方都补牌", "双方猴子牌点数相同", "25:1"),
                ("双方都补牌", "双方猴子牌点数花色相同", "75:1")
            ]

        # 创建主赔率表格
        payout_table = tk.Frame(payout_frame, bg='#F0F0F0')
        payout_table.pack(fill=tk.X, padx=10)

        # 表头
        for col, header in enumerate(payout_headers):
            tk.Label(
                payout_table,
                text=header,
                font=('微软雅黑', 16, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=8, pady=6,
                anchor='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(payout_data, start=1):
            bg = '#E8F4FD' if r % 2 == 0 else '#FFFFFF'
            for c, txt in enumerate(row_data):
                tk.Label(
                    payout_table,
                    text=txt,
                    font=('微软雅黑', 14),
                    bg=bg,
                    padx=8, pady=4,
                    anchor='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配列宽度
        for c in range(len(payout_headers)):
            payout_table.columnconfigure(c, weight=1)

        # 添加多赔率边注的详细说明表格
        if self.game_mode in ["classic", "tiger", "ez", "2to1", "fabulous4", "lucky7", "monkey"]:
            detail_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
            detail_frame.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(
                detail_frame,
                text="📊 边注详细赔率说明",
                font=('微软雅黑', 16, 'bold'),
                bg='#F0F0F0',
                fg='#2E86AB'
            ).pack(anchor='w', pady=(10, 5))

            # 根据模式显示相应的详细赔率表
            if self.game_mode == "classic" or self.game_mode == "2to1" or self.game_mode == "ez":
                # 龙宝赔率表
                dragon_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                dragon_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    dragon_frame,
                    text="🐉 龙宝赔率（根据赢方点数差）",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建龙宝表格
                dragon_table = tk.Frame(dragon_frame, bg='#F0F0F0')
                dragon_table.pack(fill=tk.X)
                
                for col, header in enumerate(dragon_headers):
                    tk.Label(
                        dragon_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(dragon_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            dragon_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(dragon_headers)):
                    dragon_table.columnconfigure(c, weight=1)
                    
                # 快合赔率表
                quik_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                quik_frame.pack(fill=tk.X, padx=20, pady=5)
                
                if not self.game_mode == "ez":
                    tk.Label(
                        quik_frame,
                        text="⚡ 快合赔率（双方点数总和）",
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F0F0F0'
                    ).pack(anchor='w', pady=(10, 5))
                
                    quik_table = tk.Frame(quik_frame, bg='#F0F0F0')
                    quik_table.pack(fill=tk.X)
                    
                    for col, header in enumerate(quik_headers):
                        tk.Label(
                            quik_table,
                            text=header,
                            font=('微软雅黑', 16, 'bold'),
                            bg='#F18F01',
                            fg='white',
                            padx=6, pady=4,
                            anchor='center'
                        ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                    
                    for r, row_data in enumerate(quik_data, start=1):
                        bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
                        for c, txt in enumerate(row_data):
                            tk.Label(
                                quik_table,
                                text=txt,
                                font=('微软雅黑', 14),
                                bg=bg,
                                padx=6, pady=3,
                                anchor='center'
                            ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                    
                    for c in range(len(quik_headers)):
                        quik_table.columnconfigure(c, weight=1)
                else:
                    # 神之9点赔率表
                    divine_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                    divine_frame.pack(fill=tk.X, padx=20, pady=5)
                    
                    tk.Label(
                        divine_frame,
                        text="✨ 神之9点赔率",
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F0F0F0'
                    ).pack(anchor='w', pady=(0, 5))
                    
                    # 创建神之9点表格
                    divine_table = tk.Frame(divine_frame, bg='#F0F0F0')
                    divine_table.pack(fill=tk.X)
                    
                    for col, header in enumerate(divine_headers):
                        tk.Label(
                            divine_table,
                            text=header,
                            font=('微软雅黑', 16, 'bold'),
                            bg='#A23B72',
                            fg='white',
                            padx=6, pady=4,
                            anchor='center'
                        ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                    
                    for r, row_data in enumerate(divine_data, start=1):
                        bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                        for c, txt in enumerate(row_data):
                            tk.Label(
                                divine_table,
                                text=txt,
                                font=('微软雅黑', 14),
                                bg=bg,
                                padx=6, pady=3,
                                anchor='center'
                            ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                    
                    for c in range(len(divine_headers)):
                        divine_table.columnconfigure(c, weight=1)
                        
            elif self.game_mode == "tiger":
                # 老虎对子赔率表
                tiger_pair_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                tiger_pair_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    tiger_pair_frame,
                    text="🐯 老虎对子赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建老虎对子表格
                tiger_pair_table = tk.Frame(tiger_pair_frame, bg='#F0F0F0')
                tiger_pair_table.pack(fill=tk.X)
                
                for col, header in enumerate(tiger_pair_headers):
                    tk.Label(
                        tiger_pair_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(tiger_pair_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            tiger_pair_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(tiger_pair_headers)):
                    tiger_pair_table.columnconfigure(c, weight=1)
                    
            elif self.game_mode == "fabulous4":
                # 神奇对子赔率表
                fab_pair_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                fab_pair_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    fab_pair_frame,
                    text="✨ 神奇对子赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建神奇对子表格
                fab_pair_table = tk.Frame(fab_pair_frame, bg='#F0F0F0')
                fab_pair_table.pack(fill=tk.X)
                
                for col, header in enumerate(fab_pair_headers):
                    tk.Label(
                        fab_pair_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(fab_pair_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            fab_pair_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(fab_pair_headers)):
                    fab_pair_table.columnconfigure(c, weight=1)
                    
            elif self.game_mode == "lucky7":
                # 幸运6和幸运7赔率表
                lucky67_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                lucky67_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    lucky67_frame,
                    text="🍀 幸运6和幸运7赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建幸运6和幸运7表格
                lucky67_table = tk.Frame(lucky67_frame, bg='#F0F0F0')
                lucky67_table.pack(fill=tk.X)
                
                for col, header in enumerate(lucky67_headers):
                    tk.Label(
                        lucky67_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(lucky67_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            lucky67_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(lucky67_headers)):
                    lucky67_table.columnconfigure(c, weight=1)
                    
                # 超级7赔率表
                super7_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                super7_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    super7_frame,
                    text="🎰 超级7赔率（根据总牌数）",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(10, 5))
                
                # 创建超级7表格
                super7_progressive_table = tk.Frame(super7_frame, bg='#F0F0F0')
                super7_progressive_table.pack(fill=tk.X)
                
                for col, header in enumerate(super7_headers):
                    tk.Label(
                        super7_progressive_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F18F01',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(super7_data, start=1):
                    bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            super7_progressive_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(super7_headers)):
                    super7_progressive_table.columnconfigure(c, weight=1)

                # 超级7大奖说明表
                super7_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                super7_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    super7_frame,
                    text="🎰 超级7累进大奖赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(10, 5))
                
                # 创建超级7大奖表格
                super7_progressive_table = tk.Frame(super7_frame, bg='#F0F0F0')
                super7_progressive_table.pack(fill=tk.X)
                
                for col, header in enumerate(super7_progressive_headers):
                    tk.Label(
                        super7_progressive_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F18F01',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(super7_progressive_data, start=1):
                    bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            super7_progressive_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(super7_progressive_headers)):
                    super7_progressive_table.columnconfigure(c, weight=1)

            elif self.game_mode == "monkey":
                # 猴子牌定义说明表
                monkey_def_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                monkey_def_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    monkey_def_frame,
                    text="🐵 猴子牌定义说明",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(0, 5))
                
                # 创建猴子牌定义表格
                monkey_def_table = tk.Frame(monkey_def_frame, bg='#F0F0F0')
                monkey_def_table.pack(fill=tk.X)
                
                for col, header in enumerate(monkey_def_headers):
                    tk.Label(
                        monkey_def_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#A23B72',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(monkey_def_data, start=1):
                    bg = '#F5E6F0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            monkey_def_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(monkey_def_headers)):
                    monkey_def_table.columnconfigure(c, weight=1)
                    
                # 猴子边注触发条件说明表
                monkey_trigger_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                monkey_trigger_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    monkey_trigger_frame,
                    text="🐵 猴子边注触发条件",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(10, 5))
                
                # 创建猴子边注触发条件表格
                monkey_trigger_table = tk.Frame(monkey_trigger_frame, bg='#F0F0F0')
                monkey_trigger_table.pack(fill=tk.X)
                
                for col, header in enumerate(monkey_trigger_headers):
                    tk.Label(
                        monkey_trigger_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#F18F01',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(monkey_trigger_data, start=1):
                    bg = '#FDF0E0' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            monkey_trigger_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(monkey_trigger_headers)):
                    monkey_trigger_table.columnconfigure(c, weight=1)

                # 新增：幸运猴子详细赔率表
                lucky_monkey_frame = tk.Frame(detail_frame, bg='#F0F0F0')
                lucky_monkey_frame.pack(fill=tk.X, padx=20, pady=5)
                
                tk.Label(
                    lucky_monkey_frame,
                    text="🍀 幸运猴子详细赔率",
                    font=('微软雅黑', 16, 'bold'),
                    bg='#F0F0F0'
                ).pack(anchor='w', pady=(10, 5))
                
                # 创建幸运猴子详细赔率表格
                lucky_monkey_table = tk.Frame(lucky_monkey_frame, bg='#F0F0F0')
                lucky_monkey_table.pack(fill=tk.X)
                
                for col, header in enumerate(lucky_monkey_headers):
                    tk.Label(
                        lucky_monkey_table,
                        text=header,
                        font=('微软雅黑', 16, 'bold'),
                        bg='#FF69B4',
                        fg='white',
                        padx=6, pady=4,
                        anchor='center'
                    ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                
                for r, row_data in enumerate(lucky_monkey_data, start=1):
                    bg = '#FFE6F2' if r % 2 == 0 else '#FFFFFF'
                    for c, txt in enumerate(row_data):
                        tk.Label(
                            lucky_monkey_table,
                            text=txt,
                            font=('微软雅黑', 14),
                            bg=bg,
                            padx=6, pady=3,
                            anchor='center'
                        ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
                
                for c in range(len(lucky_monkey_headers)):
                    lucky_monkey_table.columnconfigure(c, weight=1)

        # ===== 第五部分：特别赔付细节（文字） =====
        special_payout_frame = tk.Frame(scrollable_frame, bg='#F0F0F0')
        special_payout_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(
            special_payout_frame,
            text="💎 特别赔付细节",
            font=('微软雅黑', 14, 'bold'),
            bg='#F0F0F0',
            fg='#C73E1D'
        ).pack(anchor='w', pady=(0, 10))

        # 根据游戏模式设置特别赔付细节
        if self.game_mode == "classic":
            special_payout_text = """
        【特别注意事项】
        • 庄家获胜时支付0.95:1，即收取5%佣金
        • 龙宝投注基于赢方与输方的点数差计算赔率
        • 快合投注基于闲家和庄家的最终点数总和
        • 对子投注只考虑前两张牌是否点数相同
                """
        elif self.game_mode == "tiger":
            special_payout_text = """
        【特别注意事项】
        • 庄家以6点获胜时赔付降低为50%（即0.5:1）
        • 小老虎：庄家以2张牌6点获胜
        • 大老虎：庄家以3张牌6点获胜  
        • 老虎和：和局且庄家点数为6点
        • 老虎对子：单方对子4:1，双方不同对子20:1，双方相同对子100:1
                """
        elif self.game_mode == "ez":
            special_payout_text = """
        【特别注意事项】
        • 庄家以3张牌7点获胜时视为平局，退还本金
        • 熊猫8点：闲家必须用3张牌组成8点并获胜
        • 神之9点：任何一方用3张牌组成9点即赔付，双方都9点赔付更高
        • 金龙7点：庄家必须用3张牌组成7点并获胜
        • 龙宝投注基于赢方与输方的点数差计算赔率
                """
        elif self.game_mode == "2to1":
            special_payout_text = """
        【特别注意事项】
        • 闲家或庄家以3张牌8点或9点获胜时赔付2:1
        • 和局时主注视为输注，不退还本金
        • 其他情况下主注按1:1赔付
                """
        elif self.game_mode == "fabulous4":
            special_payout_text = """
        【特别注意事项】
        • 闲家以1点获胜时赔付2:1，以4点获胜时赔付0.5:1
        • 庄家以1点获胜时赔付2:1，以4点获胜时视为平局
        • 神奇对子区分同花对子、非同花对子和同花非对子
        • 同花指相同花色，对子指相同点数
        • 神奇4点边注不需要同花或对子，只看获胜点数
                """
        elif self.game_mode == "lucky7":
            special_payout_text = """
        【特别注意事项】
        • 庄家以6点获胜时赔付降低为50%（即0.5:1）
        • 下注1000或以上在超级7上自动参与累进大奖
        • 累进大奖头奖条件：闲家3张方片7点 + 庄家3张黑桃6点
        • 累进大奖次奖条件：闲家3张红色7点 + 庄家3张黑色6点
        • 每局下注的1%加入累进大奖池，最低保障500万
                """
        elif self.game_mode == "monkey":
            special_payout_text = """
        【特别注意事项】
        • 庄家以3张牌7点获胜时视为平局，退还本金
        • 猴子牌指J、Q、K，所有花色都算猴子牌
        • 猴老六：闲家补牌不是猴子牌且庄家补牌是猴子牌
        • 猴老六和：满足猴老六条件且本局结果为和局
        • 猴子六仙：双方6张牌都是猴子牌（闲家3张+庄家3张）
        • 猴7点：庄家3张牌组成7点并获胜
        • 幸运猴子：根据补牌情况提供1:1至75:1多级赔付
        • 只有补发的第三张牌才参与猴子牌判定
                """

        special_payout_label = tk.Label(
            special_payout_frame,
            text=special_payout_text,
            font=('微软雅黑', 14),
            bg='#FFF9E6',
            fg='#8B4513',
            justify=tk.LEFT,
            wraplength=850,
            padx=15,
            pady=10,
            relief=tk.RAISED,
            bd=1
        )
        special_payout_label.pack(fill=tk.X, padx=10)

        # 更新滚动区域
        canvas.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        # 添加关闭按钮
        close_btn = ttk.Button(
            scrollable_frame,
            text="关闭说明",
            command=win.destroy
        )
        close_btn.pack(pady=20)

        # 绑定鼠标滚轮滚动
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def _load_longest_streaks(self):
        """加載最長連勝記錄"""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                try:
                    data = json.load(f)
                    # 兼容舊數據格式
                    if isinstance(data, list) and len(data) > 0:
                        data = data[0]
                    
                    # 讀取最長連勝記錄
                    self.longest_streaks['Player'] = data.get('L_Player', 0)
                    self.longest_streaks['Tie'] = data.get('L_Tie', 0)
                    self.longest_streaks['Banker'] = data.get('L_Banker', 0)
                except json.JSONDecodeError:
                    # 文件格式錯誤時使用默認值
                    pass

    def _ensure_data_file(self):
        """确保数据目录和文件存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        if not os.path.exists(self.data_file):
            # 创建初始JSON结构 - 直接是一个字典，不是数组
            initial_data = {"Player": 0, "Tie": 0, "Banker": 0}
            with open(self.data_file, 'w') as f:
                json.dump(initial_data, f)

    def save_game_result(self, result):
        """保存遊戲結果到數據文件"""
        # 讀取現有數據
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                try:
                    data = json.load(f)
                    # 如果讀取到的是數組（舊格式），轉換為字典
                    if isinstance(data, list) and len(data) > 0:
                        data = data[0]
                except json.JSONDecodeError:
                    data = {
                        "Player": 0, "Tie": 0, "Banker": 0,
                        "L_Player": 0, "L_Tie": 0, "L_Banker": 0
                    }
        else:
            data = {
                "Player": 0, "Tie": 0, "Banker": 0,
                "L_Player": 0, "L_Tie": 0, "L_Banker": 0
            }
        
        # 更新對應結果
        if result == 'P':
            data["Player"] = int(data.get("Player", 0)) + 1
        elif result == 'T':
            data["Tie"] = int(data.get("Tie", 0)) + 1
        elif result == 'B':
            data["Banker"] = int(data.get("Banker", 0)) + 1
        
        # 更新最長連勝記錄
        data["L_Player"] = self.longest_streaks['Player']
        data["L_Tie"] = self.longest_streaks['Tie']
        data["L_Banker"] = self.longest_streaks['Banker']
        
        # 寫回文件 - 直接保存字典
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=4)

        self.update_pie_chart()

    # 修改 calculate_probabilities 方法
    def calculate_probabilities(self):
        """计算并返回各结果的概率"""
        if not os.path.exists(self.data_file):
            return {'Player': 0, 'Banker': 0, 'Tie': 0}
        
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                # 如果读取到的是数组（旧格式），转换为字典
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
        except (json.JSONDecodeError, FileNotFoundError):
            return {'Player': 0, 'Banker': 0, 'Tie': 0}
        
        # 确保值是整数
        player_count = int(data.get("Player", 0))
        tie_count = int(data.get("Tie", 0))
        banker_count = int(data.get("Banker", 0))
        
        total = player_count + tie_count + banker_count
        if total == 0:
            return {'Player': 0, 'Banker': 0, 'Tie': 0}
        
        return {
            'Player': player_count / total * 100,
            'Banker': banker_count / total * 100,
            'Tie': tie_count / total * 100
        }
    def update_streak_labels(self):
        """更新最长连胜记录标签"""
        if hasattr(self, 'longest_player_label'):
            self.longest_player_label.config(text=str(self.longest_streaks['Player']))
            self.longest_tie_label.config(text=str(self.longest_streaks['Tie']))
            self.longest_banker_label.config(text=str(self.longest_streaks['Banker']))

    def _load_assets(self):
        card_size = (120, 170)
        suits = ['Club', 'Diamond', 'Heart', 'Spade']
        ranks = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']

        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1')
        
        for suit in suits:
            for rank in ranks:
                # 构建完整文件路径
                filename = f"{suit}{rank}.png"
                path = os.path.join(card_dir, filename)
                try:
                    img = Image.open(path).resize(card_size)
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img)
                except Exception as e:
                    print(f"Error loading {path}: {e}")

        back_path = os.path.join(card_dir, 'Background.png')
        try:
            self.back_image = ImageTk.PhotoImage(Image.open(back_path).resize(card_size))
        except Exception as e:
            print(f"Error loading back image: {e}")

    def _initialize_game(self, second):
        self.unbind('<Return>')
        # dialog size
        dialog_w, dialog_h = 360, 190

        # 创建自定义对话框
        dialog = tk.Toplevel(self)
        dialog.title("切牌")
        dialog.resizable(False, False)
        dialog.transient(self)  # 设置为主窗口的子窗口
        dialog.grab_set()  # 模态对话框

        # 先调用 update_idletasks 确保 geometry 信息是最新的
        dialog.update_idletasks()

        # 尝试用父窗口坐标来居中对话框（优先）
        try:
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width()
            parent_h = self.winfo_height()
        except Exception:
            parent_x = parent_y = 0
            parent_w = parent_h = 0

        # 如果父窗口尚未正确给出尺寸（例如为 0 或 1），退回屏幕居中
        if parent_w <= 1 or parent_h <= 1:
            screen_w = dialog.winfo_screenwidth()
            screen_h = dialog.winfo_screenheight()
            x = (screen_w - dialog_w) // 2
            y = (screen_h - dialog_h) // 2
        else:
            x = parent_x + (parent_w - dialog_w) // 2
            y = parent_y + (parent_h - dialog_h) // 2

        dialog.geometry(f"{dialog_w}x{dialog_h}+{int(x)}+{int(y)}")

        # 保证主窗口关闭事件被替换为 do_nothing（与你原逻辑相同）
        try:
            self.window.protocol("WM_DELETE_WINDOW", self.do_nothing)
        except Exception:
            # 如果没有 self.window 属性则忽略（保持健壮性）
            pass

        # 提示标签
        if second:
            tk.Label(dialog, text="牌靴已经用完 \n请老板切牌 切牌位置在103-299之间",
                    font=('微软雅黑', 10)).pack(pady=(8, 4))
        else:
            tk.Label(dialog, text="请老板切牌 切牌位置在103-299之间",
                    font=('微软雅黑', 10)).pack(pady=(8, 4))

        # UI 行：Entry 与 Scale（大小条）同步
        entry_frame = tk.Frame(dialog)
        entry_frame.pack(pady=(2, 6))

        tk.Label(entry_frame, text="切牌位置:", font=('微软雅黑', 10)).pack(side=tk.LEFT, padx=(6, 8))

        entry_var = tk.StringVar()
        entry = tk.Entry(entry_frame, font=('Arial', 12), width=8, textvariable=entry_var)
        entry.pack(side=tk.LEFT)
        entry.focus_set()  # 自动聚焦

        # Scale：从 103 到 299（水平条），同步显示位置
        scale_var = tk.IntVar(value=200)  # 默认值：中位
        scale = tk.Scale(dialog, from_=103, to=299, orient=tk.HORIZONTAL, length=240,
                        variable=scale_var, showvalue=False)
        scale.pack(pady=(4, 4))

        # 存储结果
        result = [None]  # 使用列表以便在闭包中修改
        self.bigroad_results = []

        # 当 scale 移动时：更新 entry（同步；entry 会显示被 clamp 到 scale 范围内的值）
        def on_scale_change(v):
            # v 可能是字符串形式
            try:
                vi = int(float(v))
            except Exception:
                return
            # 把 scale 的数值设置到 entry（保持同步）
            entry_var.set(str(vi))

        scale.configure(command=on_scale_change)

        # 当 entry 内容改变时：如果数字在 [103,299] 内则更新 scale；否则不改变 scale（保持当前大小条位置）
        def on_entry_change(event=None):
            s = entry_var.get().strip()
            if s == "":
                # 空输入不改 scale
                return
            try:
                v = int(s)
            except Exception:
                # 非整数输入忽略（不改 scale）
                return

        # 绑定 Entry 的键松开事件（实时检测）
        entry.bind('<KeyRelease>', on_entry_change)

        # 确定按钮回调（按下确定时：处理 entry，保证 clamp 到 [103,299]；空输入表示使用外部切牌）
        def on_ok():
            s = entry_var.get().strip()
            if s == "":
                # 保持 None：代表使用外部切牌位置（或后续随机）
                result[0] = None
            else:
                try:
                    v = int(s)
                except Exception:
                    # 非整数或非法输入，使用外部切牌位置
                    result[0] = None
                    dialog.destroy()
                    return
                # 按用户要求：按下"确定"后 clamp 到合法范围
                if v < 103:
                    v = 103
                elif v > 299:
                    v = 299
                # 更新 entry 与 scale 显示为被 clamp 后的值（让用户看到结果）
                entry_var.set(str(v))
                scale_var.set(v)
                result[0] = v
            dialog.destroy()

        # 取消按钮回调（RANDOM：保持 None，表示后续使用外部或随机）
        def on_cancel():
            result[0] = None
            dialog.destroy()

        # 添加按钮
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=8)

        tk.Button(btn_frame, text="随机", width=8, command=on_cancel).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="确认", width=8, command=on_ok).pack(side=tk.LEFT, padx=10)

        # 绑定 Enter 键触发确定
        dialog.bind('<Return>', lambda e: on_ok())

        # 等待对话框关闭（模态）
        self.wait_window(dialog)

        # 获取切牌位置（用户输入或 None）
        cut_position = result[0]

        # 准备载入 A_Tools/Card/shuffle.py，并直接调用其生成函数（使用 8 副牌、不含 Joker）
        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_dir = os.path.join(os.path.dirname(current_dir), 'A_Tools')
        card_dir = os.path.join(tools_dir, 'Card')
        shuffle_py = os.path.join(card_dir, 'shuffle.py')

        external_deck = None
        external_cut_position = None

        try:
            # 动态导入 shuffle.py 模块
            import importlib.util
            import secrets as _secrets
            spec = importlib.util.spec_from_file_location("shuffle_mod", shuffle_py)
            if spec and spec.loader:
                shuffle_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(shuffle_mod)
                # 调用 generate_shuffled_deck，强制使用 8 副、不含 Joker
                try:
                    # 期望 shuffle.py 提供 generate_shuffled_deck(has_joker=False, deck_count=8)
                    external_deck = shuffle_mod.generate_shuffled_deck(has_joker=False, deck_count=8)
                    # external_deck 应为序列（如每张牌的列表），计算总张数
                    if isinstance(external_deck, (list, tuple)):
                        total_cards = len(external_deck)
                        # 生成一个位于 [103,299] 的外部切牌位置（受牌堆实际大小限制）
                        lower = 103
                        upper = min(299, total_cards - 1)
                        if upper >= lower:
                            external_cut_position = int(_secrets.randbelow(upper - lower + 1)) + lower
                        else:
                            # 若牌数太少则使用总数中位（并保证在合法范围内）
                            external_cut_position = min(max(total_cards // 2, lower), max(lower, total_cards - 1))
                    else:
                        external_deck = None
                        external_cut_position = None
                except Exception as e:
                    print(f"调用 shuffle.generate_shuffled_deck 出错: {e}")
                    external_deck = None
                    external_cut_position = None
            else:
                print("无法加载 shuffle.py 模块（spec loader 缺失）")
        except Exception as e:
            print(f"载入 shuffle.py 时出错: {e}")
            external_deck = None
            external_cut_position = None

        # 如果用户没有提供切牌位置，使用外部切牌位置（否则在 103-299 随机）
        if cut_position is None:
            if external_cut_position is not None and 103 <= external_cut_position <= 299:
                cut_position = external_cut_position
            else:
                cut_position = random.randint(103, 299)

        # 初始化游戏：把外部牌组传入 Baccarat（如果 external_deck 为 None 则由 Baccarat 内部自行生成）
        self.game = Baccarat(external_deck=external_deck)
        self.game.advanced_shuffle(cut_position)

        # 重新洗牌时重置
        self.marker_results = []
        self.marker_counts = {
            'Player': 0, 'Banker': 0, 'Tie': 0,
            'Small Tiger': 0, 'Tiger Tie': 0, 'Big Tiger': 0,
            'Panda 8': 0, 'Divine 9': 0, 'Dragon 7': 0,
            'P Fabulous 4': 0, 'B Fabulous 4': 0, 
            'Monkey 6': 0,'Monkey Tie': 0,'Monkey 7': 0
        }
        self.reset_marker_road()
        self.reset_bigroad()
        
        # 开局抽牌和弃牌流程
        self._initial_draw_and_discard()

    def _initial_draw_and_discard(self):
        """开局抽牌和弃牌流程"""
        # 禁用按钮
        for btn in self.bet_buttons:
            btn.config(state=tk.DISABLED)
        self.deal_button.config(state=tk.DISABLED)
        self.reset_button.config(state=tk.DISABLED)
        self.mode_combo.config(state='disabled')
        
        # 清除牌桌
        self.table_canvas.delete('all')
        self._draw_table_labels()
        
        # 抽第一张牌
        first_card = self.game.deck[0]
        self.game.deck = self.game.deck[1:]  # 从牌堆中移除
        
        # 创建第一张牌的动画
        first_card_id = self.table_canvas.create_image(500, 0, image=self.back_image)
        
        # 移动第一张牌到(120, 225)位置
        def move_first_card(step=0):
            if step <= 30:
                x = 500 + (120 - 500) * (step / 30)
                y = 0 + (225 - 0) * (step / 30)
                self.table_canvas.coords(first_card_id, x, y)
                self.after(10, move_first_card, step+1)
            else:
                # 移动完成后翻开牌
                self._flip_first_card(first_card_id, first_card)
        
        move_first_card()

    def _flip_first_card(self, card_id, card):
        """翻开第一张牌并计算弃牌数（翻牌动画基准尺寸 120x170）"""
        # 翻牌动画
        def flip_step(step=0):
            steps = 12
            if step > steps:
                # 翻牌完成，显示牌面（使用缓存的 full-size 图）
                try:
                    self.table_canvas.itemconfig(card_id, image=self.card_images[card])
                except Exception:
                    pass

                # 计算弃牌数（与你原来的 mapping 一致）
                deduct_map = {
                    'A': 1, 'J': 10, 'Q': 10, 'K': 10,
                    '10': 10, '2': 2, '3': 3, '4': 4, '5': 5,
                    '6': 6, '7': 7, '8': 8, '9': 9
                }
                discard_count = deduct_map.get(card[1], 0)

                # 开始弃牌动画
                self.after(500, lambda: self._discard_cards_animation(discard_count))
                return

            # 翻牌动画逻辑 — 使用与 _load_assets 中相同的基准宽 orig_w=120
            half = steps // 2
            if step <= half:
                ratio = 1 - (step / float(half))
                use_back = True
            else:
                ratio = (step - half) / float(half)
                use_back = False

            orig_w, orig_h = 120, 170
            w = max(1, int(orig_w * ratio))

            # 生成缩放后的图像（始终使用 orig_h = 170）
            img = self._create_scaled_image(card, w, orig_h, use_back=use_back)
            if not hasattr(self, '_temp_flip_images'):
                self._temp_flip_images = {}
            # 保持引用，key 用 canvas id
            self._temp_flip_images[card_id] = img

            # 更新 canvas 上的图像
            try:
                self.table_canvas.itemconfig(card_id, image=img)
            except Exception:
                pass

            # 下一帧
            self.after(20, lambda: flip_step(step+1))

        flip_step()

    def _discard_cards_animation(self, discard_count):
        """弃牌动画 - 一张一张地从500,0位置抽出来"""
        if discard_count == 0:
            # 没有弃牌，直接完成
            self._finish_initial_discard()
            return
            
        self.discard_cards = []
        self.current_discard_index = 0
        
        # 开始逐张动画
        self._animate_single_discard_card(discard_count)
    
    def _animate_single_discard_card(self, total_discard_count):
        """动画单张弃牌"""
        if self.current_discard_index >= total_discard_count:
            # 所有弃牌动画完成，等待5秒后删除
            self.after(5000, self._remove_discard_cards)
            return
            
        # 创建单张弃牌
        start_x, start_y = 500, 0
        card_id = self.table_canvas.create_image(start_x, start_y, image=self.back_image)
        self.discard_cards.append(card_id)
        
        # 计算目标位置
        i = self.current_discard_index
        row = i // 5
        col = i % 5
        
        # 根据行数调整位置
        if total_discard_count <= 5:  # 只有一行
            target_x = 260 + col * 120
            target_y = 225  # 使用与第一张牌相同的Y轴位置
        else:  # 有多行
            target_x = 260 + col * 120
            target_y = 130 + row * 170  # 每5张换行
        
        # 移动单张弃牌
        def move_single_card(step=0):
            if step <= 30:
                x = start_x + (target_x - start_x) * (step / 30)
                y = start_y + (target_y - start_y) * (step / 30)
                self.table_canvas.coords(card_id, x, y)
                self.after(10, move_single_card, step+1)
            else:
                # 当前弃牌移动完成，开始下一张
                self.current_discard_index += 1
                self.after(200, lambda: self._animate_single_discard_card(total_discard_count))
        
        move_single_card()

    def _remove_discard_cards(self):
        """删除弃牌"""
        for card_id in self.discard_cards:
            self.table_canvas.delete(card_id)
        
        # 从牌堆中移除弃牌
        discard_count = len(self.discard_cards)
        if discard_count > 0:
            self.game.deck = self.game.deck[discard_count:]
        
        self.discard_cards = []
        self._finish_initial_discard()

    def _finish_initial_discard(self):
        """完成开局流程，启用按钮"""
        # 清除牌桌
        self.table_canvas.delete('all')
        self._draw_table_labels()
        
        # 启用按钮
        for btn in self.bet_buttons:
            btn.config(state=tk.NORMAL)
        self.deal_button.config(state=tk.NORMAL)
        self.reset_button.config(state=tk.NORMAL)
        self.mode_combo.config(state='readonly')
        self.bind('<Return>', lambda e: self.start_game())

    def do_nothing(self):
        pass

    def reset_bigroad(self):
        """重置大路数据与视图"""
        self.bigroad_results.clear()
        self.bigroad_results = []
        self._bigroad_occupancy = [
            [False] * self._max_cols for _ in range(self._max_rows)
        ]
        if hasattr(self, 'bigroad_canvas'):
            self.bigroad_canvas.delete('data')
    
    # 新增：更新对子统计显示的方法
    def _update_pair_stats_display(self):
        """更新对子统计显示"""
        if hasattr(self, 'pair_stats_frame'):
            # 更新数字标签
            self.player_only_label.config(text=str(self.pair_stats['player_only']))
            self.banker_only_label.config(text=str(self.pair_stats['banker_only']))
            self.both_diff_label.config(text=str(self.pair_stats['both_diff']))
            self.both_same_label.config(text=str(self.pair_stats['both_same']))

    def _create_pair_stats_display(self, parent):
        """在对子统计行创建对子统计显示"""
        self.pair_stats_frame = tk.Frame(parent, bg='#D0E7FF', height=99)
        self.pair_stats_frame.pack(fill=tk.X, pady=(0, 0))
        self.pair_stats_frame.pack_propagate(False)
        # （其余代码保持不变 — 使用 self.pair_stats_frame 作为父容器）
        # 第一行框架
        first_row_frame = tk.Frame(self.pair_stats_frame, bg='#D0E7FF')
        first_row_frame.pack(fill=tk.X, pady=(5, 0))
        # 第二行框架
        second_row_frame = tk.Frame(self.pair_stats_frame, bg='#D0E7FF')
        second_row_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 第二行框架
        second_row_frame = tk.Frame(self.pair_stats_frame, bg='#D0E7FF')
        second_row_frame.pack(fill=tk.X, pady=(5, 0))
        
        # 定义统计项
        first_row_items = [
            {'key': 'player_only', 'text': '闲家对子', 'dots': ['blue']},
            {'key': 'banker_only', 'text': '庄家对子', 'dots': ['red']}
        ]
        
        second_row_items = [
            {'key': 'both_diff', 'text': '双生对子', 'dots': ['blue', 'red']},
            {'key': 'both_same', 'text': '孖生对子', 'dots': ['black_top_left', 'black_bottom_right']}  # 修改为只有两个黑点
        ]
        
        # 创建第一行统计项
        for item in first_row_items:
            item_frame = tk.Frame(first_row_frame, bg='#D0E7FF')
            item_frame.pack(side=tk.LEFT, padx=10, expand=True)  # 修改padx=10
            
            # 创建画布用于显示圆圈和点
            canvas = tk.Canvas(
                item_frame, 
                width=40, 
                height=40, 
                bg='#D0E7FF',
                highlightthickness=0
            )
            canvas.pack(side=tk.LEFT)
            
            # 绘制灰色实体圆圈
            center_x, center_y = 20, 20
            radius = 12
            canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill='#888888',  # 灰色
                outline='#666666',
                width=2
            )
            
            # 绘制对应的点
            dot_radius = 4  # 点的大小
            border_width = 1.5  # 白色边框宽度
            
            if 'blue' in item['dots']:
                # 左上角蓝点（带白色边框）
                pos_x = center_x - radius * 0.9
                pos_y = center_y - radius * 0.9
                
                # 白色边框
                canvas.create_oval(
                    pos_x - dot_radius - border_width, 
                    pos_y - dot_radius - border_width,
                    pos_x + dot_radius + border_width, 
                    pos_y + dot_radius + border_width,
                    fill='#FFFFFF',  # 白色边框
                    outline=''
                )
                # 蓝色点
                canvas.create_oval(
                    pos_x - dot_radius, pos_y - dot_radius,
                    pos_x + dot_radius, pos_y + dot_radius,
                    fill='#0000FF',  # 蓝色
                    outline=''
                )
            
            if 'red' in item['dots']:
                # 右下角红点（带白色边框）
                pos_x = center_x + radius * 0.9
                pos_y = center_y + radius * 0.9
                
                # 白色边框
                canvas.create_oval(
                    pos_x - dot_radius - border_width, 
                    pos_y - dot_radius - border_width,
                    pos_x + dot_radius + border_width, 
                    pos_y + dot_radius + border_width,
                    fill='#FFFFFF',  # 白色边框
                    outline=''
                )
                # 红色点
                canvas.create_oval(
                    pos_x - dot_radius, pos_y - dot_radius,
                    pos_x + dot_radius, pos_y + dot_radius,
                    fill='#FF0000',  # 红色
                    outline=''
                )
            
            # 文本标签和数字
            text_frame = tk.Frame(item_frame, bg='#D0E7FF')
            text_frame.pack(side=tk.LEFT, padx=(5, 0))
            
            # 描述文本
            desc_label = tk.Label(
                text_frame, 
                text=item['text'],
                font=('Arial', 9),
                bg='#D0E7FF'
            )
            desc_label.pack(anchor='w')
            
            # 数字显示
            count_label = tk.Label(
                text_frame, 
                text="0",
                font=('Arial', 12, 'bold'),
                bg='#D0E7FF',
                fg='#000000'
            )
            count_label.pack(anchor='w')
            
            # 保存数字标签的引用
            if item['key'] == 'player_only':
                self.player_only_label = count_label
            elif item['key'] == 'banker_only':
                self.banker_only_label = count_label
        
        # 创建第二行统计项
        for item in second_row_items:
            item_frame = tk.Frame(second_row_frame, bg='#D0E7FF')
            item_frame.pack(side=tk.LEFT, padx=10, expand=True)  # 修改padx=10
            
            # 创建画布用于显示圆圈和点
            canvas = tk.Canvas(
                item_frame, 
                width=40, 
                height=40, 
                bg='#D0E7FF',
                highlightthickness=0
            )
            canvas.pack(side=tk.LEFT)
            
            # 绘制灰色实体圆圈
            center_x, center_y = 20, 20
            radius = 12
            canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill='#888888',  # 灰色
                outline='#666666',
                width=2
            )
            
            # 绘制对应的点
            dot_radius = 4  # 点的大小
            border_width = 1.5  # 白色边框宽度
            
            if 'blue' in item['dots'] and 'red' in item['dots'] and item['key'] != 'both_same':
                # 左上角蓝点（带白色边框）
                pos_x = center_x - radius * 0.9
                pos_y = center_y - radius * 0.9
                
                # 白色边框
                canvas.create_oval(
                    pos_x - dot_radius - border_width, 
                    pos_y - dot_radius - border_width,
                    pos_x + dot_radius + border_width, 
                    pos_y + dot_radius + border_width,
                    fill='#FFFFFF',  # 白色边框
                    outline=''
                )
                # 蓝色点
                canvas.create_oval(
                    pos_x - dot_radius, pos_y - dot_radius,
                    pos_x + dot_radius, pos_y + dot_radius,
                    fill='#0000FF',  # 蓝色
                    outline=''
                )
                
                # 右下角红点（带白色边框）
                pos_x = center_x + radius * 0.9
                pos_y = center_y + radius * 0.9
                
                # 白色边框
                canvas.create_oval(
                    pos_x - dot_radius - border_width, 
                    pos_y - dot_radius - border_width,
                    pos_x + dot_radius + border_width, 
                    pos_y + dot_radius + border_width,
                    fill='#FFFFFF',  # 白色边框
                    outline=''
                )
                # 红色点
                canvas.create_oval(
                    pos_x - dot_radius, pos_y - dot_radius,
                    pos_x + dot_radius, pos_y + dot_radius,
                    fill='#FF0000',  # 红色
                    outline=''
                )
            
            if item['key'] == 'both_same':
                # 只绘制左上角和右下角的黑色点
                positions = [
                    (center_x - radius * 0.9, center_y - radius * 0.9),  # 左上
                    (center_x + radius * 0.9, center_y + radius * 0.9)   # 右下
                ]
                
                for pos_x, pos_y in positions:
                    # 白色边框
                    canvas.create_oval(
                        pos_x - dot_radius - border_width, 
                        pos_y - dot_radius - border_width,
                        pos_x + dot_radius + border_width, 
                        pos_y + dot_radius + border_width,
                        fill='#FFFFFF',  # 白色边框
                        outline=''
                    )
                    # 黑色点
                    canvas.create_oval(
                        pos_x - dot_radius, pos_y - dot_radius,
                        pos_x + dot_radius, pos_y + dot_radius,
                        fill='#000000',  # 黑色
                        outline=''
                    )
            
            # 文本标签和数字
            text_frame = tk.Frame(item_frame, bg='#D0E7FF')
            text_frame.pack(side=tk.LEFT, padx=(5, 0))
            
            # 描述文本
            desc_label = tk.Label(
                text_frame, 
                text=item['text'],
                font=('Arial', 9),
                bg='#D0E7FF'
            )
            desc_label.pack(anchor='w')
            
            # 数字显示
            count_label = tk.Label(
                text_frame, 
                text="0",
                font=('Arial', 12, 'bold'),
                bg='#D0E7FF',
                fg='#000000'
            )
            count_label.pack(anchor='w')
            
            # 保存数字标签的引用
            if item['key'] == 'both_diff':
                self.both_diff_label = count_label
            elif item['key'] == 'both_same':
                self.both_same_label = count_label

    def reset_marker_road(self):
        """重置珠路图数据"""
        # 清空所有结果
        self.marker_results = []
        
        # 重置对子统计
        self.pair_stats = {
            'player_only': 0,
            'banker_only': 0, 
            'both_diff': 0,
            'both_same': 0
        }
        
        # 重置所有统计键（Tiger + EZ + 幸运7 + 猴子模式 都要清零）
        self.marker_counts = {
            'Player': 0,
            'Banker': 0,
            'Tie': 0,
            'Small Tiger': 0,
            'Tiger Tie': 0,
            'Big Tiger': 0,
            'Panda 8': 0,
            'Divine 9': 0,
            'Dragon 7': 0,
            'P Fabulous 4': 0,
            'B Fabulous 4': 0,
            # 幸运7新增统计
            'Player 7': 0,
            'Player 7 Banker 6': 0,
            'Banker 6': 0,
            # 猴子模式相关键
            'Monkey 6': 0,
            'Monkey Tie': 0,
            'Monkey 7': 0
        }
        
        # 更新对子统计显示
        self._update_pair_stats_display()
        
        # 更新统计标签，如果对应标签存在就把它清为 0
        if hasattr(self, 'player_count_label') and self.player_count_label.winfo_exists():
            # 基本三项
            self.player_count_label.config(text="0")
            self.banker_count_label.config(text="0")
            self.tie_count_label.config(text="0")
            # Tiger 相关
            if hasattr(self, 'stiger_count_label') and self.stiger_count_label.winfo_exists():
                self.stiger_count_label.config(text="0")
                self.ttiger_count_label.config(text="0")
                self.btiger_count_label.config(text="0")
            # EZ 相关
            if hasattr(self, 'panda_count_label') and self.panda_count_label.winfo_exists():
                self.panda_count_label.config(text="0")
                self.divine_count_label.config(text="0")
                self.dragon_count_label.config(text="0")
            # Fabulous 4
            if hasattr(self, 'fab4p_count_label') and self.fab4p_count_label.winfo_exists():
                self.fab4p_count_label.config(text="0")
                self.fab4b_count_label.config(text="0")
            # 猴子模式统计
            if hasattr(self, 'monkey_old6_count_label') and self.monkey_old6_count_label.winfo_exists():
                self.monkey_old6_count_label.config(text="0")
                self.monkey_old6_tie_count_label.config(text="0")
                self.monkey7_count_label.config(text="0")
            # 幸运7模式统计
            if self.game_mode == "lucky7":
                self.player7_count_label.config(text="0")
                self.player7_banker6_count_label.config(text="0")
                self.banker6_count_label.config(text="0")
            
            # 总计标签
            self.basic_total_label.config(text="0")
            if hasattr(self, 'tiger_total_label' ) and self.tiger_total_label.winfo_exists():
                self.tiger_total_label.config(text="0")
            elif hasattr(self, 'ez_total_label') and self.ez_total_label.winfo_exists():
                self.ez_total_label.config(text="0")
            elif hasattr(self, 'fab4_total_label') and self.fab4_total_label.winfo_exists():
                self.fab4_total_label.config(text="0")
            elif hasattr(self, 'lucky7_total_label') and self.lucky7_total_label.winfo_exists():
                self.lucky7_total_label.config(text="0")
            elif hasattr(self, 'monkey_total_label') and self.monkey_total_label.winfo_exists():
                self.monkey_total_label.config(text="0")
        
        # 重新绘制珠路图网格
        self._draw_marker_grid()

    def _create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 左侧主区域
        left_frame = ttk.Frame(main_frame, width=900)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 右侧面板
        right_frame = ttk.Frame(main_frame, width=450)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # 扑克牌区域
        self.table_canvas = tk.Canvas(left_frame, bg='#35654d', highlightthickness=0, height=400)
        self.table_canvas.pack(fill=tk.BOTH, expand=False)
        self._draw_table_labels()

        # 下注区域 - 在扑克牌区域下方
        betting_area = tk.Frame(left_frame, bg='#D0E7FF', height=180)
        betting_area.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 下注区域分为左中右三部分
        betting_left = tk.Frame(betting_area, bg='#D0E7FF', width=500)
        betting_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        betting_center = tk.Frame(betting_area, bg='#D0E7FF', width=200)
        betting_center.pack(side=tk.LEFT, fill=tk.BOTH, padx=5)
        
        betting_right = tk.Frame(betting_area, bg='#D0E7FF', width=200)
        betting_right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5)
        
        # 填充下注区域
        self._populate_betting_area(betting_left, betting_center, betting_right)

        # 右侧控制面板
        self._create_control_panel(right_frame)

    def _draw_table_labels(self):
        self.table_canvas.create_line(500, 50, 500, 350, width=3, fill='white', tags='divider')
        self.table_canvas.create_text(300, 30, text="闲家", font=('Arial', 30, 'bold'), fill='white')
        self.table_canvas.create_text(700, 30, text="庄家", font=('Arial', 30, 'bold'), fill='white')

        # 添加结果显示区域 - 在扑克牌区域下方
        self.result_text_id = self.table_canvas.create_text(
            500, 370,  # 位置调整到扑克牌区域下方
            text="", 
            font=('Arial', 34, 'bold'),
            fill='white',
            tags=('result_text')
        )
        self.result_bg_id = self.table_canvas.create_rectangle(
            0, 0, 0, 0,  # 初始不可见
            fill='',
            outline='',
            tags=('result_bg')
        )

    def _get_card_positions(self, hand_type):
        area = self._player_area if hand_type == "player" else self._banker_area
        hand = self.game.player_hand if hand_type == "player" else self.game.banker_hand
        card_count = len(hand)
        base_x = area[0] + (area[2]-area[0]-120)/2
        positions = []
        for i in range(card_count):
            x = base_x + i*120  # 减少卡片间距
            y = area[1]
            if i == 2:
                if hand_type == "player":
                    x = (((positions[0][0] + positions[1][0]) / 2) - 10)
                else:
                    x = (((positions[0][0] + positions[1][0]) / 2) + 10)
                y = area[1] + 80
            positions.append((int(round(x)), int(round(y))))
        return positions
            
    def _create_chip_button(self, parent, text, bg_color):
        size = 60
        canvas = tk.Canvas(parent, width=size, height=size,
                        highlightthickness=0, background='#D0E7FF')

        # 绘制不带发光/外圈的圆形
        chip_id = canvas.create_oval(2, 2, size-2, size-2,
                                    fill=bg_color, outline='', width=0)

        # 文字颜色计算（保持不变）
        rgb = ImageColor.getrgb(bg_color)
        luminance = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2]
        text_color = 'white' if luminance < 140 else 'black'

        # 添加文字
        canvas.create_text(size/2, size/2, text=text,
                        fill=text_color, font=('Arial', 16, 'bold'))

        # 绑定点击事件
        canvas.bind('<Button-1>', lambda e, t=text, c=canvas, cid=chip_id: self._set_bet_amount(t, c, cid))

        # 存储按钮信息 - 确保包含所有必要字段
        chip_info = {
            'canvas': canvas,
            'chip_id': chip_id,
            'text': text
        }
        self.chip_buttons.append(chip_info)
        return canvas

    def _set_bet_amount(self, chip_text, clicked_canvas, clicked_chip_id):
        """
        点击筹码时：
        1) 清除所有筹码的金色边框
        2) 记录新的选中状态
        3) 给新选中筹码加上金色边框并更新显示标签
        """
        # 1) 清除所有筹码的边框
        for chip in self.chip_buttons:
            try:
                # 确保chip字典包含必要的键
                if 'canvas' in chip and 'chip_id' in chip:
                    chip['canvas'].itemconfig(chip['chip_id'], outline='', width=0)
            except Exception as e:
                # 如果筹码已被销毁，忽略错误
                print(f"Error clearing chip border: {e}")
                continue

        # 2) 记录当前选中状态
        self.selected_chip = None
        self.selected_canvas = None
        self.selected_id = None
        
        for chip in self.chip_buttons:
            if 'canvas' in chip and chip['canvas'] == clicked_canvas:
                self.selected_chip = chip
                self.selected_canvas = chip['canvas']
                self.selected_id = chip['chip_id']
                break

        # 3) 金额转换逻辑
        if '千' in chip_text:
            amount = int(chip_text.replace('千', '')) * 1000
        elif '万' in chip_text:
            amount = int(chip_text.replace('万', '')) * 10000
        else:
            try:
                amount = int(chip_text)
            except Exception:
                amount = getattr(self, 'selected_bet_amount', 1000)

        self.selected_bet_amount = amount

        # 给新选中筹码加上金色边框
        try:
            if (getattr(self, 'selected_canvas', None) and 
                getattr(self, 'selected_id', None) is not None):
                self.selected_canvas.itemconfig(self.selected_id, outline='yellow', width=4)
        except Exception as e:
            print(f"Error setting chip border: {e}")

        # 更新显示标签
        if hasattr(self, 'current_chip_label'):
            self.current_chip_label.config(text=f"筹码: ${amount:,}")

    def _set_chip_by_amount(self, amount):
        """根据金额设置选中的筹码"""
        # 先清除所有筹码的边框
        for chip in self.chip_buttons:
            try:
                if 'canvas' in chip and 'chip_id' in chip:
                    chip['canvas'].itemconfig(chip['chip_id'], outline='', width=0)
            except Exception as e:
                print(f"Error clearing chip border: {e}")
                continue
        
        # 根据金额找到对应的筹码
        target_chip = None
        for chip in self.chip_buttons:
            chip_text = chip.get('text', '')
            chip_amount = 0
            
            # 计算筹码对应的金额
            if '千' in chip_text:
                chip_amount = int(chip_text.replace('千', '')) * 1000
            elif '万' in chip_text:
                chip_amount = int(chip_text.replace('万', '')) * 10000
            else:
                try:
                    chip_amount = int(chip_text)
                except Exception:
                    continue
            
            if chip_amount == amount:
                target_chip = chip
                break
        
        # 如果找到对应的筹码，选中它
        if target_chip:
            self.selected_chip = target_chip
            self.selected_canvas = target_chip.get('canvas')
            self.selected_id = target_chip.get('chip_id')
            
            # 显示金色边框
            try:
                if self.selected_canvas and self.selected_id is not None:
                    self.selected_canvas.itemconfig(self.selected_id, outline='yellow', width=4)
            except Exception as e:
                print(f"Error setting chip border: {e}")
            
            # 更新显示标签
            if hasattr(self, 'current_chip_label'):
                self.current_chip_label.config(text=f"筹码: ${amount:,}")
        else:
            # 如果没有找到对应金额的筹码，使用默认的1千
            self._set_default_chip()

    def reset_bets(self):
        # Give all current bets back to the balance
        for bet_type, amt in self.current_bets.items():
            self.balance += amt
        # Clear the current bets
        self.current_bets.clear()
        self.current_bet = 0

        # Update all the UI elements
        self.update_balance()                            # refresh balance label
        self.current_bet_label.config(text=f"${0:,}")    # reset bet display

        for btn in self.bet_buttons:
            if hasattr(btn, 'bet_type'):
                original_text = btn.cget("text").split('\n')
                # 恢复初始文本格式（最后一行显示~~）
                new_text = f"{original_text[0]}\n{original_text[1]}\n~~"
                btn.config(text=new_text)

    def update_mode_display(self):
        """更新组合框显示文本"""
        current_value = self.mode_var.get()
        display_text = self.mode_display_map.get(current_value, current_value)
        self.mode_combo.set(display_text)

    # 添加新方法：处理组合框弹出事件
    def on_combobox_popup(self, event):
        """当组合框弹出时更新选项显示文本"""
        # 获取当前值
        current_value = self.mode_var.get()
        
        # 更新下拉列表选项
        self.mode_combo['values'] = [
            self.mode_display_map.get("tiger", "Tiger Baccarat"),
            self.mode_display_map.get("ez", "EZ Baccarat")
        ]
        
        # 设置当前显示文本
        self.mode_combo.set(self.mode_display_map.get(current_value, current_value))

    def _create_control_panel(self, parent):
        # main panel with light-blue background - 固定宽度
        control_frame = tk.Frame(parent, bg='#D0E7FF', width=300)
        control_frame.pack(pady=12, padx=10, fill=tk.BOTH, expand=True)
        control_frame.pack_propagate(False)  # 禁止自动调整大小

        style = ttk.Style()
        
        # 配置组合框的样式 - 完全匹配浅蓝色背景
        style.configure('TCombobox', 
                    font=('微软雅黑', 14, 'bold'),
                    fieldbackground='#D0E7FF',  # 输入框背景色
                    background='#D0E7FF',       # 整体背景色
                    selectbackground='#D0E7FF', # 选中项背景色
                    selectforeground='black',   # 选中项文字颜色
                    borderwidth=0,              # 去除边框
                    focuscolor='none')          # 去除焦点颜色
        
        # 配置状态映射
        style.map('TCombobox',
                fieldbackground=[('readonly', '#D0E7FF'),
                            ('active', '#D0E7FF'),
                            ('focus', '#D0E7FF')],
                background=[('readonly', '#D0E7FF'),
                        ('active', '#D0E7FF'), 
                        ('focus', '#D0E7FF')],
                selectbackground=[('readonly', '#D0E7FF'),
                                ('active', '#D0E7FF'),
                                ('focus', '#D0E7FF')],
                selectforeground=[('readonly', 'black'),
                                ('active', 'black'),
                                ('focus', 'black')])
        
        # ===== 游戏模式切换 =====
        mode_frame = tk.Frame(control_frame, bg='#D0E7FF')
        mode_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            mode_frame, 
            text="游戏模式:", 
            font=('微软雅黑', 14, 'bold'),
            bg='#D0E7FF'
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.mode_var = tk.StringVar(value=self.game_mode)
        
        # 定义显示文本和内部值的映射
        self.mode_display_map = {
            "classic": "经典百家乐",
            "tiger": "老虎百家乐", 
            "lucky7": "幸运7百家乐",
            "ez": "简单百家乐",
            "2to1": "1赔2百家乐",
            "fabulous4": "神奇4点百家乐",
            "monkey": "猴子百家乐"
        }
        
        # 使用显示文本作为组合框的值
        display_values = [self.mode_display_map["classic"],
                        self.mode_display_map["tiger"], 
                        self.mode_display_map["lucky7"],
                        self.mode_display_map["ez"], 
                        self.mode_display_map["monkey"],
                        self.mode_display_map["2to1"], 
                        self.mode_display_map["fabulous4"],
                        ]
        
        # 创建组合框 - 使用显示文本作为选项
        self.mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=display_values,
            state='readonly',
            font=('微软雅黑', 14, 'bold'),
            width=15,
            style='TCombobox'  # 应用自定义样式
        )
        self.mode_combo.pack(side=tk.LEFT)
        
        # 设置当前显示文本
        self.mode_combo.set(self.mode_display_map.get(self.game_mode, self.game_mode))
        
        # 绑定选择事件
        self.mode_combo.bind("<<ComboboxSelected>>", self.change_game_mode)
        
        # 额外设置下拉列表样式
        self.option_add('*TCombobox*Listbox.font', ('微软雅黑', 14, 'bold'))
        self.option_add('*TCombobox*Listbox.background', 'white')
        self.option_add('*TCombobox*Listbox.selectBackground', '#D0E7FF')
        self.option_add('*TCombobox*Listbox.selectForeground', 'black')
        
        # 添加一个技巧：在选择后立即将焦点转移到其他控件
        def on_mode_select(event):
            # 延迟一点时间后将焦点转移到其他控件
            self.after(100, lambda: self.focus_set())
        
        self.mode_combo.bind("<<ComboboxSelected>>", lambda e: (self.change_game_mode(e), self.after(100, lambda: self.focus_set())))

        # ===== 修改部分：视图切换按钮 - 只保留Road和Static =====
        view_frame = tk.Frame(control_frame, bg='#D0E7FF')
        view_frame.pack(fill=tk.X, pady=(5, 5))
        
        self.marker_view_btn = tk.Button(
            view_frame, 
            text="路径", 
            command=self.show_marker_view,
            bg='#4B8BBE',  # 蓝色背景
            fg='white',
            font=('Arial', 14, 'bold'),
            relief=tk.RAISED,
            width=10
        )
        self.marker_view_btn.pack(side=tk.LEFT, padx=5)

        self.bigroad_view_btn = tk.Button(
            view_frame, text="统计", command=self.show_bigroad_view,
            bg='#888888', fg='white', font=('Arial',14,'bold'),
            relief=tk.FLAT, width=10
        )
        self.bigroad_view_btn.pack(side=tk.LEFT, padx=5)
        
        # 创建一个统一大小的 view_container - 固定高度
        self.view_container = tk.Frame(control_frame, bg='#D0E7FF', height=300)
        self.view_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.view_container.pack_propagate(False)  # 禁止自动调整大小

        # 1) marker_view
        self.marker_view = tk.Frame(self.view_container, bg='#D0E7FF')

        # 2) bigroad_view
        self.bigroad_view = tk.Frame(self.view_container, bg='#D0E7FF')

        # 之后调用生成大路和珠路图等方法
        self._create_marker_road()
        self.enable_bigroad_navigation()

        # 默认显示珠路图视图
        self.show_marker_view()
    
    def refresh_all_stat_labels(self):
        """
        将 self.marker_counts 的值写入所有已创建的统计标签（不依赖当前 game_mode）。
        只更新已经存在的标签（使用 hasattr 判断），因此安全且不会抛异常。
        """
        try:
            # 基本三项（英文 key）
            if hasattr(self, 'player_count_label'):
                self.player_count_label.config(text=str(self.marker_counts.get('Player', 0)))
            if hasattr(self, 'banker_count_label'):
                self.banker_count_label.config(text=str(self.marker_counts.get('Banker', 0)))
            if hasattr(self, 'tie_count_label'):
                self.tie_count_label.config(text=str(self.marker_counts.get('Tie', 0)))
        except Exception:
            pass

        # Tiger 模式相关
        try:
            if hasattr(self, 'stiger_count_label'):
                self.stiger_count_label.config(text=str(self.marker_counts.get('Small Tiger', 0)))
            if hasattr(self, 'ttiger_count_label'):
                self.ttiger_count_label.config(text=str(self.marker_counts.get('Tiger Tie', 0)))
            if hasattr(self, 'btiger_count_label'):
                self.btiger_count_label.config(text=str(self.marker_counts.get('Big Tiger', 0)))
            if hasattr(self, 'tiger_total_label'):
                tiger_total = (
                    self.marker_counts.get('Small Tiger', 0)
                    + self.marker_counts.get('Tiger Tie', 0)
                    + self.marker_counts.get('Big Tiger', 0)
                )
                self.tiger_total_label.config(text=str(tiger_total))
        except Exception:
            pass

        # EZ / Monkey-like special (Panda/Divine/Dragon and Monkey series)
        try:
            if hasattr(self, 'panda_count_label'):
                self.panda_count_label.config(text=str(self.marker_counts.get('Panda 8', 0)))
            if hasattr(self, 'divine_count_label'):
                self.divine_count_label.config(text=str(self.marker_counts.get('Divine 9', 0)))
            if hasattr(self, 'dragon_count_label'):
                self.dragon_count_label.config(text=str(self.marker_counts.get('Dragon 7', 0)))
            if hasattr(self, 'ez_total_label'):
                ez_total = (
                    self.marker_counts.get('Panda 8', 0)
                    + self.marker_counts.get('Divine 9', 0)
                    + self.marker_counts.get('Dragon 7', 0)
                )
                self.ez_total_label.config(text=str(ez_total))
        except Exception:
            pass

        # Monkey 系列（兼容不同命名）
        try:
            # 兼容英文 key
            if hasattr(self, 'monkey6_count_label'):
                self.monkey6_count_label.config(text=str(self.marker_counts.get('Monkey 6', 0)))
            if hasattr(self, 'monkey_tie_count_label'):
                self.monkey_tie_count_label.config(text=str(self.marker_counts.get('Monkey Tie', 0)))
            if hasattr(self, 'big_monkey_count_label'):
                self.big_monkey_count_label.config(text=str(self.marker_counts.get('Big Monkey', 0)))
            if hasattr(self, 'monkey_total_label'):
                monkey_total = (
                    self.marker_counts.get('Monkey 6', 0)
                    + self.marker_counts.get('Monkey Tie', 0)
                    + self.marker_counts.get('Big Monkey', 0)
                )
                self.monkey_total_label.config(text=str(monkey_total))
        except Exception:
            pass

        # Fabulous4
        try:
            if hasattr(self, 'fab4p_count_label'):
                self.fab4p_count_label.config(text=str(self.marker_counts.get('P Fabulous 4', 0)))
            if hasattr(self, 'fab4b_count_label'):
                self.fab4b_count_label.config(text=str(self.marker_counts.get('B Fabulous 4', 0)))
            if hasattr(self, 'fab4_total_label'):
                fab4_total = (
                    self.marker_counts.get('P Fabulous 4', 0)
                    + self.marker_counts.get('B Fabulous 4', 0)
                )
                self.fab4_total_label.config(text=str(fab4_total))
        except Exception:
            pass

        # Lucky7 专属统计（Player 7 / Banker 6 / Player7 vs Banker6）
        try:
            if hasattr(self, 'player7_count_label'):
                self.player7_count_label.config(text=str(self.marker_counts.get('Player 7', 0)))
            if hasattr(self, 'player7_banker6_count_label'):
                self.player7_banker6_count_label.config(text=str(self.marker_counts.get('Player 7 Banker 6', 0)))
            if hasattr(self, 'banker6_count_label'):
                self.banker6_count_label.config(text=str(self.marker_counts.get('Banker 6', 0)))
            if hasattr(self, 'lucky7_total_label'):
                lucky7_total = (
                    self.marker_counts.get('Player 7', 0)
                    + self.marker_counts.get('Player 7 Banker 6', 0)
                    + self.marker_counts.get('Banker 6', 0)
                )
                self.lucky7_total_label.config(text=str(lucky7_total))
        except Exception:
            pass

        # 最后，更新 BASIC 总计（总是有）
        try:
            if hasattr(self, 'basic_total_label'):
                basic_total = (
                    self.marker_counts.get('Player', 0)
                    + self.marker_counts.get('Tie', 0)
                    + self.marker_counts.get('Banker', 0)
                )
                self.basic_total_label.config(text=str(basic_total))
        except Exception:
            pass

    def change_game_mode(self, event=None):
        selected_display = self.mode_combo.get()
        # 将显示文本映射到真实模式值（更稳健的反查）
        real_mode = None
        for k, v in getattr(self, 'mode_display_map', {}).items():
            if v == selected_display:
                real_mode = k
                break
        if real_mode is None:
            real_mode = "classic"

        if real_mode != getattr(self, 'game_mode', None):
            # 只重置下注，不重置珠路图统计
            try:
                self.reset_bets()
            except Exception:
                pass
            self.game_mode = real_mode
            try:
                self._reload_betting_buttons()
            except Exception:
                pass

        # ------------- 关键：在重建统计面板之前，用 marker_results 重新计算统计 -------------
        try:
            # 初始化所有可能的统计键（与 reset_marker_road 中一致）
            recomputed_counts = {
                'Player': 0, 'Banker': 0, 'Tie': 0,
                'Small Tiger': 0, 'Tiger Tie': 0, 'Big Tiger': 0,
                'Panda 8': 0, 'Divine 9': 0, 'Dragon 7': 0,
                'P Fabulous 4': 0, 'B Fabulous 4': 0,
                'Player 7': 0, 'Player 7 Banker 6': 0, 'Banker 6': 0,
                'Monkey 6': 0, 'Monkey Tie': 0, 'Monkey 7': 0
            }
            # Reset pair stats counters
            recomputed_pairs = {
                'player_only': 0,
                'banker_only': 0,
                'both_diff': 0,
                'both_same': 0
            }

            # Iterate marker_results（每项由 add_marker_result append）
            for entry in getattr(self, 'marker_results', []):
                # 向后兼容：entry 可能是不同长度的 tuple/list，补齐到 13 个字段
                try:
                    (winner, is_natural, is_stiger, is_btiger,
                    player_hand_len, banker_hand_len,
                    player_score, banker_score,
                    is_player_pair, is_banker_pair, is_same_rank_pair,
                    is_player_monkey, is_banker_monkey) = entry
                except Exception:
                    # 补齐不足字段
                    fields = list(entry) + [False] * (13 - len(entry))
                    (winner, is_natural, is_stiger, is_btiger,
                    player_hand_len, banker_hand_len,
                    player_score, banker_score,
                    is_player_pair, is_banker_pair, is_same_rank_pair,
                    is_player_monkey, is_banker_monkey) = fields[:13]

                # 基本三项计数
                if winner in ('Player', 'Banker', 'Tie'):
                    recomputed_counts[winner] = recomputed_counts.get(winner, 0) + 1

                # Tiger 相关
                if winner == 'Banker' and (is_stiger or is_btiger):
                    if is_stiger:
                        recomputed_counts['Small Tiger'] = recomputed_counts.get('Small Tiger', 0) + 1
                    if is_btiger:
                        recomputed_counts['Big Tiger'] = recomputed_counts.get('Big Tiger', 0) + 1
                elif winner == 'Tie' and is_stiger:
                    recomputed_counts['Tiger Tie'] = recomputed_counts.get('Tiger Tie', 0) + 1

                # EZ 模式特殊（Panda8 / Divine9 / Dragon7）
                if winner == 'Player' and player_hand_len == 3 and player_score == 8 and banker_score < 8:
                    recomputed_counts['Panda 8'] = recomputed_counts.get('Panda 8', 0) + 1
                if (player_score == 9 or banker_score == 9) and (player_hand_len == 3 or banker_hand_len == 3):
                    recomputed_counts['Divine 9'] = recomputed_counts.get('Divine 9', 0) + 1
                if winner == 'Banker' and banker_hand_len == 3 and banker_score == 7 and player_score < 7:
                    recomputed_counts['Dragon 7'] = recomputed_counts.get('Dragon 7', 0) + 1

                # Fabulous4
                if winner == 'Player' and player_score == 4:
                    recomputed_counts['P Fabulous 4'] = recomputed_counts.get('P Fabulous 4', 0) + 1
                if winner == 'Banker' and banker_score == 4:
                    recomputed_counts['B Fabulous 4'] = recomputed_counts.get('B Fabulous 4', 0) + 1

                # Lucky7 相关
                if player_score == 7 and winner == 'Player' and banker_score != 6:
                    recomputed_counts['Player 7'] = recomputed_counts.get('Player 7', 0) + 1
                if banker_score == 6 and winner == 'Banker':
                    recomputed_counts['Banker 6'] = recomputed_counts.get('Banker 6', 0) + 1
                if player_score == 7 and banker_score == 6:
                    recomputed_counts['Player 7 Banker 6'] = recomputed_counts.get('Player 7 Banker 6', 0) + 1

                # Monkey 模式相关
                if winner == 'Banker' and banker_hand_len == 3 and banker_score == 7:
                    recomputed_counts['Monkey 7'] = recomputed_counts.get('Monkey 7', 0) + 1
                if (player_hand_len == 3 and not is_player_monkey) and (banker_hand_len == 3 and is_banker_monkey):
                    if winner == 'Tie':
                        recomputed_counts['Monkey Tie'] = recomputed_counts.get('Monkey Tie', 0) + 1
                    else:
                        recomputed_counts['Monkey 6'] = recomputed_counts.get('Monkey 6', 0) + 1

                # 对子统计（pair_stats）
                if is_same_rank_pair:
                    recomputed_pairs['both_same'] += 1
                elif is_player_pair and is_banker_pair:
                    recomputed_pairs['both_diff'] += 1
                elif is_player_pair:
                    recomputed_pairs['player_only'] += 1
                elif is_banker_pair:
                    recomputed_pairs['banker_only'] += 1

            # 把重算好的结果写回实例属性
            self.marker_counts = recomputed_counts
            self.pair_stats = recomputed_pairs

        except Exception:
            # 若出现任何错误，不要阻塞模式切换；保守起见不改变现有计数
            pass

        # ------------- 重建统计面板并用现有 marker_counts 填充标签 -------------
        # 重新创建统计面板（销毁旧面板）
        try:
            for widget in self.bigroad_view.winfo_children():
                widget.destroy()
        except Exception:
            pass

        try:
            self._create_stats_panel(self.bigroad_view)
        except Exception:
            pass

        # 关键：重建完面板后立刻把 marker_counts 的当前值写入所有已创建的标签
        try:
            # refresh_all_stat_labels 假定会使用 self.marker_counts/self.pair_stats 填充所有标签
            self.refresh_all_stat_labels()
        except Exception:
            # 如果没有 refresh_all_stat_labels 或其内部出错，尽量手动写入常见标签（容错）
            try:
                if hasattr(self, 'player_count_label'):
                    self.player_count_label.config(text=str(self.marker_counts.get('Player', 0)))
                if hasattr(self, 'banker_count_label'):
                    self.banker_count_label.config(text=str(self.marker_counts.get('Banker', 0)))
                if hasattr(self, 'tie_count_label'):
                    self.tie_count_label.config(text=str(self.marker_counts.get('Tie', 0)))
                # Lucky7 常用
                if hasattr(self, 'player7_count_label'):
                    self.player7_count_label.config(text=str(self.marker_counts.get('Player 7', 0)))
                if hasattr(self, 'banker6_count_label'):
                    self.banker6_count_label.config(text=str(self.marker_counts.get('Banker 6', 0)))
                # Monkey 常用
                if hasattr(self, 'monkey_old6_count_label'):
                    self.monkey_old6_count_label.config(text=str(self.marker_counts.get('Monkey 6', 0)))
            except Exception:
                pass

        # 其它刷新（pair stats / pie / marker road 等）
        try:
            self._update_pair_stats_display()
        except Exception:
            pass
        try:
            self.update_pie_chart()
        except Exception:
            pass
        try:
            self._update_marker_road()
        except Exception:
            pass

    def _reload_betting_buttons(self):
        """根据当前模式重新加载下注按钮"""
        # 保存当前选中的筹码金额
        current_amount = getattr(self, 'selected_bet_amount', 1000)
        
        # 清除所有按钮和状态
        self.selected_chip = None
        self.selected_canvas = None
        self.selected_id = None
        self.chip_buttons = []  # 重置筹码按钮列表
        self.bet_buttons = []   # 重置下注按钮列表
        
        # 销毁 betting_view 中的所有组件
        for widget in self.betting_left.winfo_children():
            widget.destroy()
        
        for widget in self.betting_center.winfo_children():
            widget.destroy()
            
        for widget in self.betting_right.winfo_children():
            widget.destroy()
        
        # 重新创建下注视图
        self._populate_betting_area(self.betting_left, self.betting_center, self.betting_right)
        
        # 确保jackpot显示正确
        self._update_jackpot_display()
        
        # 根据之前选中的金额设置筹码，而不是总是使用默认值
        self._set_chip_by_amount(current_amount)

    def show_bigroad_view(self):
        self.marker_view.pack_forget()
        self.bigroad_view.pack(fill=tk.BOTH, expand=True)
        self.marker_view_btn.config(relief=tk.FLAT, bg='#888888')
        self.bigroad_view_btn.config(relief=tk.RAISED, bg='#4B8BBE')
        self.view_mode = "bigroad"

    def show_marker_view(self):
        """显示珠路图视图"""
        # 切换按钮样式
        self.bigroad_view.pack_forget()
        self.marker_view.pack(fill=tk.BOTH, expand=True)
        self.marker_view_btn.config(relief=tk.RAISED, bg='#4B8BBE')
        self.bigroad_view_btn.config(relief=tk.FLAT, bg='#888888')
        self.view_mode = "marker"

    def _create_marker_road(self):
        """创建包含 Big Road + Marker Road + 统计面板的复合视图"""
        # ↓↓↓ ① 整合 Big Road 部分 ↓↓↓
        # 初始化 bigroad 数据
        self.bigroad_results.clear
        self.bigroad_results = []
        self._max_rows = 6
        self._max_cols = 50
        self._bigroad_occupancy = [
            [False] * self._max_cols for _ in range(self._max_rows)
        ]

        # 基本尺寸
        cell    = 25    # 每个格子内部大小
        pad     = 2     # 格子间距
        label_w = 30    # 左侧行号列宽
        label_h = 20    # 顶部列号行高

        # 计算总尺寸
        total_w = label_w + self._max_cols * (cell + pad) + pad
        total_h = label_h + self._max_rows * (cell + pad) + pad

        # 创建 Big Road 的容器——使用同一个 marker_frame 作为父级
        marker_frame = tk.Frame(self.marker_view, bg='#D0E7FF')
        marker_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ──【Big Road 标题】（可选，如果想给 Big Road 单独一个标题，可以加上）
        big_title = tk.Label(
            marker_frame,
            text="大路",
            font=('微软雅黑', 14, 'bold'),
            bg='#D0E7FF'
        )
        big_title.pack(pady=(0, 2))  # 与上方留一些空隙

        # ──【Big Road 画布及滚动条】
        big_frame = tk.Frame(marker_frame, bg='#D0E7FF')
        big_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

        hbar = tk.Scrollbar(big_frame, orient=tk.HORIZONTAL)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.bigroad_canvas = tk.Canvas(
            big_frame,
            bg='#FFFFFF',
            width=290,   # 初始可见宽度，可根据窗口调整
            height=total_h,
            xscrollcommand=hbar.set,
            scrollregion=(0, 0, total_w, total_h),
            highlightthickness=0
        )
        self.bigroad_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        hbar.config(command=self.bigroad_canvas.xview)

        # 画 Big Road 顶部列号
        for c in range(self._max_cols):
            x = label_w + pad + c * (cell + pad) + cell / 2
            y = label_h / 2
            self.bigroad_canvas.create_text(
                x, y,
                text=str(c + 1),
                font=('Arial', 8),
                tags=('grid',)
            )

        # 画 Big Road 左侧行号
        for r in range(self._max_rows):
            x = label_w / 2
            y = label_h + pad + r * (cell + pad) + cell / 2
            self.bigroad_canvas.create_text(
                x, y,
                text=str(r + 1),
                font=('Arial', 8),
                tags=('grid',)
            )

        # 画 Big Road 网格
        for c in range(self._max_cols):
            for r in range(self._max_rows):
                x1 = label_w + pad + c * (cell + pad)
                y1 = label_h + pad + r * (cell + pad)
                x2 = x1 + cell
                y2 = y1 + cell
                self.bigroad_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline='#888888', fill='#FFFFFF',
                    tags=('grid',)
                )

        # ↓↓↓ ② 紧接着绘制 Marker Road ↓↓↓
        # 添加 Marker Road 的标题
        marker_title = tk.Label(
            marker_frame, 
            text="标记路", 
            font=('微软雅黑', 14, 'bold'),
            bg='#D0E7FF'
        )
        marker_title.pack(pady=(0, 5))  # 与 Big Road 画布之间留出一些空间
        
        # 创建 Marker Road 画布
        self.marker_canvas = tk.Canvas(
            marker_frame, 
            bg='#D0E7FF',
            highlightthickness=0
        )
        self.marker_canvas.pack(fill=tk.BOTH, expand=True, padx=3, pady=(0, 0))

        self._create_pair_stats_display(marker_frame)

        # ↓↓↓ ③ 最后再绘制"统计面板"↓↓↓
        # 注意：这里调用依然是 self._create_stats_panel(self.bigroad_view)
        #      但将它放在 Marker Road 视图的逻辑末尾，也就是 Big Road + Marker Road 画布 之后。
        self._create_stats_panel(self.bigroad_view)

    def enable_bigroad_navigation(self, debug=False):
        """
        仅启用“大路”键盘左右键导航（不再绑定鼠标滚轮）。
        - 自动查找 self.bigroad_canvas（或常见候选属性）
        - 解除所有鼠标滚轮绑定（canvas 本身与顶层 root 的 bind_all）
        - 绑定键盘 Left/Right 到 canvas（仅当 canvas 有焦点时生效）
        调用时机：确保 bigroad_canvas 已创建并且 scrollregion 已设置后调用一次。
        """
        # 找 canvas（优先 self.bigroad_canvas）
        canvas = getattr(self, 'bigroad_canvas', None)
        if canvas is None:
            candidates = ('bigroad_canvas', 'bigroad_view', 'bigroad_frame', 'bigroad_scrollable_canvas')
            for name in candidates:
                obj = getattr(self, name, None)
                if obj is None:
                    continue
                if hasattr(obj, 'xview_scroll') and callable(getattr(obj, 'xview_scroll')):
                    canvas = obj
                    break
                try:
                    for child in getattr(obj, 'winfo_children')():
                        if hasattr(child, 'xview_scroll') and callable(getattr(child, 'xview_scroll')):
                            canvas = child
                            break
                    if canvas:
                        break
                except Exception:
                    pass

        if canvas is None:
            if debug:
                print("enable_bigroad_navigation: 找不到可横向滚动的 Canvas")
            return

        # 1) 解除所有与鼠标滚轮相关的绑定（防止残留）
        try:
            # canvas 层
            try:
                canvas.unbind("<MouseWheel>")
            except Exception:
                pass
            try:
                canvas.unbind("<Button-4>")
                canvas.unbind("<Button-5>")
            except Exception:
                pass

            # 顶层 root 全局解绑（若之前使用了 bind_all）
            try:
                root = canvas.winfo_toplevel()
                root.unbind_all("<MouseWheel>")
                root.unbind_all("<Button-4>")
                root.unbind_all("<Button-5>")
            except Exception:
                pass

            if debug:
                print("BigRoad: cleared mouse wheel bindings on canvas and root.")
        except Exception:
            # 忽略任何解绑错误
            if debug:
                print("BigRoad: error while clearing mouse bindings (ignored).")

        # 2) 绑定键盘左右键（绑定到 canvas，使其只在 canvas 有焦点时生效）
        try:
            # 先解除旧的键绑定（避免重复）
            try:
                canvas.unbind("<KeyPress-Left>")
                canvas.unbind("<KeyPress-Right>")
            except Exception:
                pass

            # 将每次按键移动单位保存为实例属性（方便将来调整）
            try:
                self._bigroad_key_scroll_units = 5
            except Exception:
                pass

            canvas.bind("<KeyPress-Left>", lambda e: self._on_bigroad_key(e, canvas))
            canvas.bind("<KeyPress-Right>", lambda e: self._on_bigroad_key(e, canvas))
            # 鼠标点击或进入 canvas 时给它 focus，方便直接按键
            canvas.bind("<Button-1>", lambda e: canvas.focus_set())
            canvas.bind("<Enter>", lambda e: canvas.focus_set())

            # 标记已启用，避免重复启用
            try:
                setattr(canvas, "_bigroad_keyboard_nav_enabled", True)
            except Exception:
                pass

            if debug:
                print("BigRoad keyboard navigation enabled on:", canvas)
                try:
                    print("  canvas.winfo_width():", canvas.winfo_width())
                    print("  scrollregion:", canvas.cget("scrollregion"))
                except Exception:
                    pass
        except Exception as e:
            if debug:
                print("BigRoad: failed to bind keyboard navigation:", e)

    def _on_bigroad_key(self, event, canvas):
        """
        处理左右键：Left -> 向左移动；Right -> 向右移动。
        使用 self._bigroad_key_scroll_units（默认 5）作为步幅。
        """
        try:
            # 默认步幅（如未设置在 enable 中，则使用 5）
            units = getattr(self, "_bigroad_key_scroll_units", 5)
            keysym = getattr(event, 'keysym', '')
            if keysym == 'Left':
                canvas.xview_scroll(-units, "units")
            elif keysym == 'Right':
                canvas.xview_scroll(units, "units")
        except Exception:
            # 忽略异常，防止程序中断
            pass

    def disable_bigroad_mouse_navigation(self, debug=False):
        """
        明确移除所有与大路相关的鼠标滚轮绑定（可在需要彻底禁用鼠标时调用）。
        """
        canvas = getattr(self, 'bigroad_canvas', None)
        if canvas is None:
            if debug:
                print("disable_bigroad_mouse_navigation: canvas not found")
            return
        try:
            try:
                canvas.unbind("<MouseWheel>")
            except Exception:
                pass
            try:
                canvas.unbind("<Button-4>")
                canvas.unbind("<Button-5>")
            except Exception:
                pass
            try:
                root = canvas.winfo_toplevel()
                root.unbind_all("<MouseWheel>")
                root.unbind_all("<Button-4>")
                root.unbind_all("<Button-5>")
            except Exception:
                pass
            if debug:
                print("BigRoad: mouse wheel bindings removed (canvas and root).")
        except Exception:
            if debug:
                print("BigRoad: error while removing mouse bindings (ignored).")

    def _create_stats_panel(self, parent):
        """创建统计信息面板 - 使用网格布局实现表格效果"""
        # 主框架
        stats_frame = tk.Frame(parent, bg='#D0E7FF')
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0), padx=10)
        
        # 创建表格样式的框架
        table_frame = tk.Frame(stats_frame, bg='#D0E7FF')
        table_frame.pack(fill=tk.X)
        
        # ===== 表头 =====
        # 左侧永远显示 BASIC 列
        basic_label = tk.Label(
            table_frame, text="基本",
            font=('微软雅黑', 14, 'bold'),
            bg='#D0E7FF', width=12
        )

        if self.game_mode == "classic" or self.game_mode == "2to1":
            # 如果是 classic 模式，让 BASIC 占满所有列并水平居中
            basic_label.grid(row=0, column=0, columnspan=3, sticky='ew')
            ttk.Separator(table_frame, orient=tk.HORIZONTAL).grid(
                row=5, column=0, columnspan=1, sticky='ew', pady=2
            )
            tk.Label(
                table_frame, text="总计:",
                font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', anchor='w'
            ).grid(row=6, column=0, sticky='w', pady=(2, 5))
            
            self.basic_total_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.basic_total_label.grid(row=6, column=0, sticky='e', pady=(2, 5))
        else:
            # 非 classic 时，保持原来的左对齐和内边距
            basic_label.grid(row=0, column=0, sticky='w', padx=(0, 10))

        # 右侧列要根据当前模式决定标题：Tiger 模式下显示 "TIGER"，EZ 模式下显示 "EZ"
        if self.game_mode == "tiger":
            right_header = "老虎"
        elif self.game_mode == "ez":
            right_header = "简单"
        elif self.game_mode == "fabulous4":
            right_header = "神奇4点"
        elif self.game_mode == "lucky7":
            right_header = "幸运6幸运7"
        elif self.game_mode == "monkey":
            right_header = "猴子"
        else:
            right_header = None

        if right_header:
            tk.Label(
                table_frame, text=right_header,
                font=('微软雅黑', 14, 'bold'),
                bg='#D0E7FF', width=12
            ).grid(row=0, column=2, sticky='w')  # 放在第 2 列
        
        # 表头分隔线
        ttk.Separator(table_frame, orient=tk.HORIZONTAL).grid(
            row=1, column=0, columnspan=3, sticky='ew', pady=2  # 改为跨越3列
        )
        
        # ===== 内容区域 =====
        # 在BASIC和Tiger之间添加垂直分隔线（贯穿整个内容区域）
        vertical_separator = ttk.Separator(table_frame, orient=tk.VERTICAL)
        vertical_separator.grid(
            row=2, column=1, rowspan=5, sticky='ns', padx=5, pady=2
        )

        # ── 左侧 BASIC 列（不变） ── #
        # Player
        tk.Label(
            table_frame, text="闲家:",
            font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
        ).grid(row=2, column=0, sticky='w', pady=2)
        self.player_count_label = tk.Label(
            table_frame, text="0",
            font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
        )
        self.player_count_label.grid(row=2, column=0, sticky='e')

        # Tie
        tk.Label(
            table_frame, text="和局:",
            font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
        ).grid(row=3, column=0, sticky='w', pady=2)
        self.tie_count_label = tk.Label(
            table_frame, text="0",
            font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
        )
        self.tie_count_label.grid(row=3, column=0, sticky='e')

        # Banker
        tk.Label(
            table_frame, text="庄家:",
            font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
        ).grid(row=4, column=0, sticky='w', pady=2)
        self.banker_count_label = tk.Label(
            table_frame, text="0",
            font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
        )
        self.banker_count_label.grid(row=4, column=0, sticky='e')

        # ── 右侧 列，根据模式分开布局 ── #
        if self.game_mode == "tiger":
            # Tiger 模式：显示 Small Tiger、Tiger Tie、Big Tiger 三行
            tk.Label(
                table_frame, text="小老虎:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=2, column=2, sticky='w', pady=2)
            self.stiger_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.stiger_count_label.grid(row=2, column=2, sticky='e')

            tk.Label(
                table_frame, text="老虎和:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=3, column=2, sticky='w', pady=2)
            self.ttiger_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.ttiger_count_label.grid(row=3, column=2, sticky='e')
            tk.Label(
                table_frame, text="大老虎:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=4, column=2, sticky='w', pady=2)
            self.btiger_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.btiger_count_label.grid(row=4, column=2, sticky='e')
        
        elif self.game_mode == "ez":  # EZ 模式：显示 Panda 8、Divine 9、Dragon 7 三行
            tk.Label(
                table_frame, text="熊猫8点:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=2, column=2, sticky='w', pady=2)
            self.panda_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.panda_count_label.grid(row=2, column=2, sticky='e')

            tk.Label(
                table_frame, text="神之9点:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=3, column=2, sticky='w', pady=2)
            self.divine_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.divine_count_label.grid(row=3, column=2, sticky='e')

            tk.Label(
                table_frame, text="金龙7点:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=4, column=2, sticky='w', pady=2)
            self.dragon_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.dragon_count_label.grid(row=4, column=2, sticky='e')

        elif self.game_mode == "fabulous4":  # 添加这个分支
            # P Fabulous 4
            tk.Label(
                table_frame, text="闲神4点:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=2, column=2, sticky='w', pady=2)
            self.fab4p_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.fab4p_count_label.grid(row=2, column=2, sticky='e')
            
            # B Fabulous 4
            tk.Label(
                table_frame, text="庄神4点:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=3, column=2, sticky='w', pady=2)
            self.fab4b_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.fab4b_count_label.grid(row=3, column=2, sticky='e')
            
            # 不需要第三行，留空
            ttk.Separator(table_frame, orient=tk.HORIZONTAL).grid(
                row=5, column=0, columnspan=3, sticky='ew', pady=2  # 跨越3列
            )
        
        elif self.game_mode == "lucky7":  # 幸运7模式
            # 闲家7点
            tk.Label(
                table_frame, text="闲家7点:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=2, column=2, sticky='w', pady=2)
            self.player7_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.player7_count_label.grid(row=2, column=2, sticky='e')
            
            # 闲7杀6
            tk.Label(
                table_frame, text="闲7杀6:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=3, column=2, sticky='w', pady=2)
            self.player7_banker6_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.player7_banker6_count_label.grid(row=3, column=2, sticky='e')
            
            # 庄家6点
            tk.Label(
                table_frame, text="庄家6点:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=4, column=2, sticky='w', pady=2)
            self.banker6_count_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.banker6_count_label.grid(row=4, column=2, sticky='e')

        elif self.game_mode == "monkey":
            # 右侧列标题为 "猴子"，下方三行：猴老六、猴老六和、猴7点
            # 猴老六
            tk.Label(
                table_frame, text="猴老六:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=2, column=2, sticky='w', pady=2)
            self.monkey_old6_count_label = tk.Label(
                table_frame, text=str(self.marker_counts.get('Monkey 6', 0)),
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.monkey_old6_count_label.grid(row=2, column=2, sticky='e')

            # 猴老六和
            tk.Label(
                table_frame, text="猴老六和:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=3, column=2, sticky='w', pady=2)
            self.monkey_old6_tie_count_label = tk.Label(
                table_frame, text=str(self.marker_counts.get('Monkey Tie', 0)),
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.monkey_old6_tie_count_label.grid(row=3, column=2, sticky='e')

            # 猴7点
            tk.Label(
                table_frame, text="猴7点:",
                font=('微软雅黑', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=4, column=2, sticky='w', pady=2)
            self.monkey7_count_label = tk.Label(
                table_frame, text=str(self.marker_counts.get('Monkey 7', 0)),
                font=('微软雅黑', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.monkey7_count_label.grid(row=4, column=2, sticky='e')

        # ===== 总计行 =====
        # BASIC 总计
        ttk.Separator(table_frame, orient=tk.HORIZONTAL).grid(
            row=5, column=0, columnspan=3, sticky='ew', pady=2
        )

        # BASIC 总计（所有模式都需要）
        tk.Label(
            table_frame, text="总计:",
            font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', anchor='w'
        ).grid(row=6, column=0, sticky='w', pady=(2, 5))
        self.basic_total_label = tk.Label(
            table_frame, text="0",
            font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
        )
        self.basic_total_label.grid(row=6, column=0, sticky='e', pady=(2, 5))

        # 右侧列总计：根据模式决定是 tiger_total_label 还是 ez_total_label
        if self.game_mode == "tiger" or self.game_mode == "ez" or self.game_mode == "fabulous4" or self.game_mode == "lucky7" or self.game_mode == "monkey":
            tk.Label(
                table_frame, text="总计:",
                font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', anchor='w'
            ).grid(row=6, column=2, sticky='w', pady=(2, 5))

        if self.game_mode == "tiger":
            self.tiger_total_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.tiger_total_label.grid(row=6, column=2, sticky='e', pady=(2, 5))
        elif self.game_mode == "ez":
            self.ez_total_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.ez_total_label.grid(row=6, column=2, sticky='e', pady=(2, 5))
        elif self.game_mode == "fabulous4":  # 添加这个分支
            self.fab4_total_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.fab4_total_label.grid(row=6, column=2, sticky='e', pady=(2, 5))
            
            # 现在安全更新值
            fab4_total = (
                self.marker_counts.get('P Fabulous 4', 0) +
                self.marker_counts.get('B Fabulous 4', 0)
            )
            self.fab4_total_label.config(text=str(fab4_total))
        elif self.game_mode == "lucky7":
            self.lucky7_total_label = tk.Label(
                table_frame, text="0",
                font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.lucky7_total_label.grid(row=6, column=2, sticky='e', pady=(2, 5))
        elif self.game_mode == "monkey":
            # monkey 的总计标签
            monkey_total = (
                self.marker_counts.get('Monkey 6', 0) +
                self.marker_counts.get('Monkey Tie', 0) +
                self.marker_counts.get('Monkey 7', 0)
            )
            self.monkey_total_label = tk.Label(
                table_frame, text=str(monkey_total),
                font=('微软雅黑', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.monkey_total_label.grid(row=6, column=2, sticky='e', pady=(2, 5))
        
        # 配置列权重，使BASIC和Tiger列宽度相等，中间列固定宽度
        if self.game_mode == "classic" or self.game_mode == "2to1":
            table_frame.columnconfigure(0, weight=1, uniform="group")
        else:
            table_frame.columnconfigure(0, weight=1, uniform="group")
            table_frame.columnconfigure(1, weight=0, minsize=10)  # 中间列用于分隔线
            table_frame.columnconfigure(2, weight=1, uniform="group")
        
        # 添加外边框
        ttk.Separator(stats_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 10))

        pie_frame = tk.Frame(stats_frame, bg='#D0E7FF')
        pie_frame.pack(fill=tk.X, pady=(10, 0))
        
        # 标题
        tk.Label(
            pie_frame, text="历史记录", 
            font=('微软雅黑', 16, 'bold'), 
            bg='#D0E7FF'
        ).pack(pady=(0, 5))
        
        # 创建饼图画布
        self.pie_canvas = tk.Canvas(
            pie_frame, 
            width=150, 
            height=150,
            bg='#D0E7FF',
            highlightthickness=0
        )
        self.pie_canvas.pack(side=tk.LEFT)

        # 创建一个空行（占位符） - 新增这行
        tk.Frame(pie_frame, height=30, bg='#D0E7FF').pack(side=tk.TOP, fill=tk.X)

        # 创建百分比标签框架 - 位置调整
        percent_frame = tk.Frame(pie_frame, bg='#D0E7FF')
        percent_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(10, 0))

        # 创建右侧百分比标签框架
        percent_frame = tk.Frame(pie_frame, bg='#D0E7FF')
        percent_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 创建三个百分比标签
        self.player_percent_label = tk.Label(
            percent_frame,
            text="闲家: 0.0%",
            font=('微软雅黑', 12, 'bold'),
            bg='#D0E7FF',
            fg='#4444ff',  # 蓝色
            anchor='w'
        )
        self.player_percent_label.pack(fill=tk.X, pady=2)

        self.tie_percent_label = tk.Label(
            percent_frame,
            text="和局: 0.0%",
            font=('微软雅黑', 12, 'bold'),
            bg='#D0E7FF',
            fg="#009700",  # 绿色
            anchor='w'
        )
        self.tie_percent_label.pack(fill=tk.X, pady=2)

        self.banker_percent_label = tk.Label(
            percent_frame,
            text="庄家: 0.0%",
            font=('微软雅黑', 12, 'bold'),
            bg='#D0E7FF',
            fg='#ff4444',  # 红色
            anchor='w'
        )
        self.banker_percent_label.pack(fill=tk.X, pady=2)

        ttk.Separator(stats_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)

        # 在饼图下方添加最长连胜记录
        streak_frame = tk.Frame(stats_frame, bg='#D0E7FF')
        streak_frame.pack(fill=tk.X, pady=(15, 5))
        
        # 标题 - 居中显示
        tk.Label(
            streak_frame, text="最长连胜记录", 
            font=('微软雅黑', 14, 'bold'), 
            bg='#D0E7FF'
        ).pack(fill=tk.X, pady=(5, 5))  # 使用fill=tk.X使标签占据整个宽度
        
        # 创建记录显示框架
        record_frame = tk.Frame(streak_frame, bg='#D0E7FF')
        record_frame.pack(fill=tk.X, padx=5)
        
        # 使用网格布局使三个记录水平居中
        # PLAYER 记录
        player_frame = tk.Frame(record_frame, bg='#D0E7FF')
        player_frame.grid(row=0, column=0, padx=5)
        tk.Label(
            player_frame, text="闲家:", 
            font=('微软雅黑', 12, 'bold'), 
            bg='#D0E7FF', fg='#4444ff'
        ).pack(side=tk.LEFT)
        self.longest_player_label = tk.Label(
            player_frame, text=str(self.longest_streaks['Player']),
            font=('Arial', 12, 'bold'), 
            bg='#D0E7FF'
        )
        self.longest_player_label.pack(side=tk.LEFT)
        
        # TIE 记录
        tie_frame = tk.Frame(record_frame, bg='#D0E7FF')
        tie_frame.grid(row=0, column=1, padx=10)
        tk.Label(
            tie_frame, text="和局:", 
            font=('微软雅黑', 12, 'bold'), 
            bg='#D0E7FF', fg='#009700'
        ).pack(side=tk.LEFT)
        self.longest_tie_label = tk.Label(
            tie_frame, text=str(self.longest_streaks['Tie']),
            font=('微软雅黑', 12, 'bold'), 
            bg='#D0E7FF'
        )
        self.longest_tie_label.pack(side=tk.LEFT)
        
        # BANKER 记录
        banker_frame = tk.Frame(record_frame, bg='#D0E7FF')
        banker_frame.grid(row=0, column=2, padx=10)
        tk.Label(
            banker_frame, text="庄家:", 
            font=('微软雅黑', 12, 'bold'), 
            bg='#D0E7FF', fg='#ff4444'
        ).pack(side=tk.LEFT)
        self.longest_banker_label = tk.Label(
            banker_frame, text=str(self.longest_streaks['Banker']),
            font=('微软雅黑', 12, 'bold'), 
            bg='#D0E7FF'
        )
        self.longest_banker_label.pack(side=tk.LEFT)
        
        # 配置网格列权重使内容居中
        record_frame.columnconfigure(0, weight=1)
        record_frame.columnconfigure(1, weight=1)
        record_frame.columnconfigure(2, weight=1)
        
        # 添加外边框
        ttk.Separator(stats_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)
        
        # 初始绘制饼图
        self.update_pie_chart()
        
    def update_pie_chart(self):
        # 清除现有内容
        self.pie_canvas.delete('all')
        
        # 计算概率
        probabilities = self.calculate_probabilities()
        
        # 更新百分比标签
        self.player_percent_label.config(text=f"闲家: {probabilities['Player']:.2f}%")
        self.tie_percent_label.config(text=f"和局: {probabilities['Tie']:.2f}%")
        self.banker_percent_label.config(text=f"庄家: {probabilities['Banker']:.2f}%")
        
        # 饼图参数 - 中心点调整到新画布中心
        center_x, center_y = 75, 75  # 因为画布宽度从200改为150
        radius = 50
        
        # 如果没有数据，显示空饼图
        if sum(probabilities.values()) == 0:
            self.pie_canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill='#888888',
                outline=''
            )
            self.pie_canvas.create_text(
                center_x, center_y,
                text="No Data",
                font=('Arial', 10)
            )
            return
        
        # 初始化起始角度
        start_angle = 0  # 添加这行初始化变量
        
        # 绘制饼图
        # Player 部分
        player_angle = 360 * probabilities['Player'] / 100
        self.pie_canvas.create_arc(
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius,
            start=start_angle,
            extent=player_angle,
            fill='#4444ff',
            outline=''
        )
        start_angle += player_angle
        
        # Banker 部分
        banker_angle = 360 * probabilities['Banker'] / 100
        self.pie_canvas.create_arc(
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius,
            start=start_angle,
            extent=banker_angle,
            fill='#ff4444',
            outline=''
        )
        start_angle += banker_angle
        
        # Tie 部分
        tie_angle = 360 * probabilities['Tie'] / 100
        self.pie_canvas.create_arc(
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius,
            start=start_angle,
            extent=tie_angle,
            fill='#00ff00',
            outline=''
        )
        
        # 中心空白圆（甜甜圈效果）
        self.pie_canvas.create_oval(
            center_x - radius/2, center_y - radius/2,
            center_x + radius/2, center_y + radius/2,
            fill='#D0E7FF',
            outline=''
        )

    def _draw_marker_grid(self):
        """绘制珠路图网格 - 修改为每行7个格子"""
        # 清除现有内容
        self.marker_canvas.delete('all')
        
        # 网格参数 - 修改为每行7个格子，每个格子放大1.5倍
        rows, cols = 6, 9  # 改为7列
        cell_size = 30  # 从20放大到30 (1.5倍)
        padding = 0     # 相应增加内边距
        
        # 更新实例变量
        self.max_marker_rows = rows
        self.max_marker_cols = cols
        
        # 计算画布所需大小
        width = cols * (cell_size + padding) + padding
        height = rows * (cell_size + padding) + padding
        
        # 设置画布大小
        self.marker_canvas.config(width=width, height=height)
        
        # 绘制网格
        for col in range(cols):
            for row in range(rows):
                x1 = padding + col * (cell_size + padding)
                y1 = padding + row * (cell_size + padding)
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                
                self.marker_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline='#888888',
                    fill='#D0E7FF'
                )

    def add_marker_result(self, winner, is_natural=False, is_stiger=False, is_btiger=False, 
                    player_hand_len=0, banker_hand_len=0, player_score=0, banker_score=0,
                    is_player_pair=False, is_banker_pair=False, is_same_rank_pair=False,
                    is_player_monkey=False, is_banker_monkey=False):
        """添加新的珠路图结果"""
        # 如果珠路图已满，移除最旧的一行数据
        if len(self.marker_results) >= self.max_marker_rows * self.max_marker_cols:
            # 移除最旧的一行（7个点）
            for _ in range(self.max_marker_rows):
                if self.marker_results:
                    self.marker_results.pop(0)
        
        # 先更新 Player/Tie/Banker 基本计数
        self.marker_counts[winner] += 1
        
        # 更新 Tiger 模式下的 stiger/btiger
        if winner == 'Banker' and (is_stiger or is_btiger):
            if is_stiger:
                self.marker_counts['Small Tiger'] += 1
            if is_btiger:
                self.marker_counts['Big Tiger'] += 1
        elif winner == 'Tie' and is_stiger:  # Tiger Tie
            self.marker_counts['Tiger Tie'] += 1
        
        # 存储结果到 marker_results（新增对子信息和猴子牌信息）
        self.marker_results.append((
            winner, is_natural, is_stiger, is_btiger,
            player_hand_len, banker_hand_len,
            player_score, banker_score,
            is_player_pair, is_banker_pair, is_same_rank_pair,
            is_player_monkey, is_banker_monkey  # 新增猴子牌信息
        ))
        
        # 如果触发 EZ 模式下的 Panda 8/Divine 9/Dragon 7，则累加对应键
        if winner == 'Player' and player_hand_len == 3 and player_score == 8 and banker_score < 8:
            self.marker_counts['Panda 8'] += 1

        if (player_score == 9 or banker_score == 9) and (player_hand_len == 3 or banker_hand_len == 3):
            self.marker_counts['Divine 9'] += 1

        if winner == 'Banker' and banker_hand_len == 3 and banker_score == 7 and player_score < 7:
            self.marker_counts['Dragon 7'] += 1

        if self.game_mode == "fabulous4":
            if winner == 'Player' and player_score == 4:
                self.marker_counts['P Fabulous 4'] += 1
            elif winner == 'Banker' and banker_score == 4:
                self.marker_counts['B Fabulous 4'] += 1

        # 新增：幸运7模式统计
        if self.game_mode == "lucky7":
            # 闲家7点统计
            if player_score == 7 and winner == 'Player' and banker_score != 6:
                self.marker_counts['Player 7'] += 1
            # 庄家6点统计
            if banker_score == 6 and winner == 'Banker':
                self.marker_counts['Banker 6'] += 1
            # 闲7杀6统计
            if player_score == 7 and banker_score == 6:
                self.marker_counts['Player 7 Banker 6'] += 1
        
        # 新增：猴子模式统计
        if self.game_mode == "monkey":
            # 猴7点：庄家3张牌7点获胜
            if winner == 'Banker' and banker_hand_len == 3 and banker_score == 7:
                self.marker_counts['Monkey 7'] += 1
            
            # 猴老六：闲家补牌不是猴子牌，庄家补牌是猴子牌
            if (player_hand_len == 3 and not is_player_monkey and 
                banker_hand_len == 3 and is_banker_monkey):
                
                # 猴老六和：同时满足猴老六条件且本局结果是和
                if winner == 'Tie':
                    self.marker_counts['Monkey Tie'] += 1
                else:
                    self.marker_counts['Monkey 6'] += 1
        
        # 更新幸运7统计显示
        if self.game_mode == "lucky7":
            if hasattr(self, 'player7_count_label'):
                self.player7_count_label.config(text=str(self.marker_counts['Player 7']))
                self.player7_banker6_count_label.config(text=str(self.marker_counts['Player 7 Banker 6']))
                self.banker6_count_label.config(text=str(self.marker_counts['Banker 6']))
            
            lucky7_total = (
                self.marker_counts['Player 7'] +
                self.marker_counts['Player 7 Banker 6'] +
                self.marker_counts['Banker 6']
            )
            if hasattr(self, 'lucky7_total_label'):
                self.lucky7_total_label.config(text=str(lucky7_total))
        
        # 更新猴子模式统计显示
        if self.game_mode == "monkey":
            if hasattr(self, 'monkey_old6_count_label'):
                self.monkey_old6_count_label.config(text=str(self.marker_counts.get('Monkey 6', 0)))
                self.monkey_old6_tie_count_label.config(text=str(self.marker_counts.get('Monkey Tie', 0)))
                self.monkey7_count_label.config(text=str(self.marker_counts.get('Monkey 7', 0)))
            
            monkey_total = (
                self.marker_counts.get('Monkey 6', 0) +
                self.marker_counts.get('Monkey Tie', 0) +
                self.marker_counts.get('Monkey 7', 0)
            )
            if hasattr(self, 'monkey_total_label'):
                self.monkey_total_label.config(text=str(monkey_total))
        
        # 更新顶部的 Player/Tie/Banker 标签
        self.player_count_label.config(text=str(self.marker_counts['Player']))
        self.banker_count_label.config(text=str(self.marker_counts['Banker']))
        self.tie_count_label.config(text=str(self.marker_counts['Tie']))

        # 新增：更新对子统计
        if is_same_rank_pair:
            self.pair_stats['both_same'] += 1
        elif is_player_pair and is_banker_pair:
            self.pair_stats['both_diff'] += 1
        elif is_player_pair:
            self.pair_stats['player_only'] += 1
        elif is_banker_pair:
            self.pair_stats['banker_only'] += 1
        
        # 更新对子统计显示
        self._update_pair_stats_display()

        # 根据当前模式，更新右侧统计面板对应的标签和值
        if self.game_mode == "tiger":
            if hasattr(self, 'stiger_count_label'):
                self.stiger_count_label.config(text=str(self.marker_counts['Small Tiger']))
                self.ttiger_count_label.config(text=str(self.marker_counts['Tiger Tie']))
                self.btiger_count_label.config(text=str(self.marker_counts['Big Tiger']))
            tiger_total = (
                self.marker_counts['Small Tiger'] +
                self.marker_counts['Tiger Tie'] +
                self.marker_counts['Big Tiger']
            )
            self.tiger_total_label.config(text=str(tiger_total))
        elif self.game_mode == "ez":
            if hasattr(self, 'panda_count_label'):
                self.panda_count_label.config(text=str(self.marker_counts['Panda 8']))
                self.divine_count_label.config(text=str(self.marker_counts['Divine 9']))
                self.dragon_count_label.config(text=str(self.marker_counts['Dragon 7']))
            ez_total = (
                self.marker_counts['Panda 8'] +
                self.marker_counts['Divine 9'] +
                self.marker_counts['Dragon 7']
            )
            self.ez_total_label.config(text=str(ez_total))
        elif self.game_mode == "fabulous4":
            if hasattr(self, 'fab4p_count_label') and self.fab4p_count_label.winfo_exists():
                self.fab4p_count_label.config(text=str(self.marker_counts['P Fabulous 4']))
                self.fab4b_count_label.config(text=str(self.marker_counts['B Fabulous 4']))
            fab4_total = (
                self.marker_counts['P Fabulous 4'] +
                self.marker_counts['B Fabulous 4']
            )
            self.fab4_total_label.config(text=str(fab4_total))
        
        # 计算并更新总计
        basic_total = (
            self.marker_counts['Player'] +
            self.marker_counts['Tie'] +
            self.marker_counts['Banker']
        )
        self.basic_total_label.config(text=str(basic_total))
        
        # 重新绘制珠路图
        self._update_marker_road()

    def _update_marker_road(self):
        """更新珠路图显示"""
        # 保留网格线，只删除圆点
        self.marker_canvas.delete('dot')  # 只删除圆点，保留网格
        
        # 网格参数 - 修改为每行7个格子，每个格子放大1.5倍
        rows, cols = 6, 9
        cell_size = 30  # 从20放大到30 (1.5倍)
        padding = 0     # 相应增加内边距
        
        # 计算画布所需大小
        width = cols * (cell_size + padding) + padding
        height = rows * (cell_size + padding) + padding
        
        # 设置画布大小
        self.marker_canvas.config(width=width, height=height)
        
        # 绘制网格
        for col in range(cols):
            for row in range(rows):
                x1 = padding + col * (cell_size + padding)
                y1 = padding + row * (cell_size + padding)
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                
                self.marker_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline='#888888',
                    fill='#D0E7FF'
                )

        # 计算起始索引（如果结果超过42个，只显示最近的42个）
        start_idx = max(0, len(self.marker_results) - rows * cols)
        
        # 绘制圆点
        for idx, result in enumerate(self.marker_results[start_idx:]):
            if idx >= rows * cols:  # 超过网格容量
                break
                
            col = idx // rows
            row = idx % rows
            
            # 计算单元格位置
            x1 = padding + col * (cell_size + padding)
            y1 = padding + row * (cell_size + padding)
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            
            # 计算圆点位置
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            radius = cell_size * 0.4
            
            # 根据结果绘制圆点
            (winner, is_natural, is_stiger, is_btiger, 
            player_hand_len, banker_hand_len, 
            player_score, banker_score,
            is_player_pair, is_banker_pair, is_same_rank_pair, 
            is_player_monkey, is_banker_monkey) = result  # 新增对子参数
            
            outline_color = ''
            if winner == 'Player':
                if self.game_mode == "ez" and player_hand_len == 3 and player_score == 8:  ## 简单模式
                    color = "#FFFFFF"
                    text = "8"
                    text_color = '#0000FF'
                    outline_color = '#0000FF'
                elif self.game_mode == "ez" and player_hand_len == 3 and player_score == 9:  ## 简单模式
                    color = "#F2FF00"
                    text = "神"
                    text_color = '#0000FF'
                    outline_color = '#0000FF'
                elif self.game_mode == "lucky7" and player_score == 7:  ## 幸运7模式
                    if banker_score == 6:  ## 7杀6
                        color = "#FFFFFF"
                        text = "7-6"
                        text_color = '#0000FF'
                        outline_color = '#0000FF'
                    else:  ## 闲家7点Only
                        color = "#F2FF00"
                        text = "7"
                        text_color = '#0000FF'
                        outline_color = '#0000FF'
                elif self.game_mode == "monkey" and is_banker_monkey and not is_player_monkey and player_hand_len == 3 and banker_hand_len == 3:  ## 猴子模式
                    color = "#FFFFFF"
                    text = "猴"
                    outline_color = "#0000FF"
                    text_color = "#0000FF"
                else:
                    color = "#95D1FF" if is_natural else '#0000FF'
                    text = "闲"
                    text_color = 'black' if is_natural else 'white'
                    outline_color = '#0000FF'
            elif winner == 'Banker':
                if (self.game_mode == "tiger" and banker_score == 6 or  ## 老虎模式
                            self.game_mode == "lucky7" and banker_score == 6):  ## 幸运7模式
                    if banker_hand_len == 2:
                        color = "#FFFFFF"
                        text_color = '#FF0000'
                        outline_color = '#FF0000'
                        text = "小"
                    elif banker_hand_len == 3:
                        text = "大"
                        color = "#FFFFFF"
                        outline_color = '#FF0000'
                        text_color = '#FF0000'
                elif self.game_mode == "ez" and banker_hand_len == 3 and banker_score == 9:  ## 简单模式
                    color = "#F2FF00"
                    text = "神"
                    text_color = '#FF0000'
                    outline_color = '#FF0000'
                elif (self.game_mode == "ez" and banker_hand_len == 3 and banker_score == 7 or   ## 简单模式
                                self.game_mode == "monkey" and banker_hand_len == 3 and banker_score == 7):  ## 猴子模式
                    text = "7"
                    color = '#FFFF00'
                    text_color = '#FF0000'
                    outline_color = '#FF0000'
                elif self.game_mode == "monkey" and is_banker_monkey and not is_player_monkey and player_hand_len == 3 and banker_hand_len == 3:  ## 猴子模式
                    color = "#FFFFFF"
                    text = "猴"
                    outline_color = "#FF0000"
                    text_color = "#FF0000"
                else:
                    text = "庄"
                    text_color = 'black' if is_natural else 'white'
                    color = "#FF7700" if is_natural else '#FF0000'
            else:
                if self.game_mode == "tiger" and is_stiger:  ## 老虎模式
                    text = "和"
                    text_color = "#00A100"
                    outline_color = '#00A100'
                    color = "#FFFFFF"
                elif self.game_mode == "monkey" and is_banker_monkey and not is_player_monkey and player_hand_len == 3 and banker_hand_len == 3:  ## 猴子模式
                    color = "#FFFFFF"
                    text = "猴"
                    outline_color = "#00A100"
                    text_color = "#00A100"
                elif self.game_mode == "ez" and player_hand_len == 3 and player_score == 9 and banker_hand_len == 3 and banker_score == 9:  ## 简单模式
                    color = "#F2FF00"
                    text = "神"
                    text_color = '#00A100'
                    outline_color = '#00A100'
                else:  # Tie
                    color = '#00FF00'
                    text = "和"
                    text_color = 'black'
                    outline_color = 'black'
            
            # 绘制主圆点
            self.marker_canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill=color,
                outline=outline_color,
                width=2,  
                tags='dot'
            )

            # 绘制对子标记点
            pair_radius = cell_size * 0.12  # 对子点半径
            border_width = 2.5  # 白色边框宽度

            # 双方对子且点数相同 - 在四个角都显示黑色点（带白色边框）
            if is_same_rank_pair:
                # 两个角的位置
                positions = [
                    (x1 + pair_radius * 1.25, y1 + pair_radius * 1.25),  # 左上角
                    (x2 - pair_radius * 1.25, y2 - pair_radius * 1.25)   # 右下角
                ]
                
                for pos_x, pos_y in positions:
                    # 先绘制白色边框
                    self.marker_canvas.create_oval(
                        pos_x - pair_radius - border_width/2, 
                        pos_y - pair_radius - border_width/2,
                        pos_x + pair_radius + border_width/2, 
                        pos_y + pair_radius + border_width/2,
                        fill='#FFFFFF',  # 白色边框
                        outline='',
                        tags='dot'
                    )
                    
                    # 再绘制黑色点
                    self.marker_canvas.create_oval(
                        pos_x - pair_radius, pos_y - pair_radius,
                        pos_x + pair_radius, pos_y + pair_radius,
                        fill='#000000',  # 黑色
                        outline='',
                        tags='dot'
                    )
            else:
                # 闲家对子 - 左上角蓝色点（带白色边框）
                if is_player_pair:
                    pair_x = x1 + pair_radius * 1.25
                    pair_y = y1 + pair_radius * 1.25
                    
                    # 先绘制白色边框
                    self.marker_canvas.create_oval(
                        pair_x - pair_radius - border_width/2, 
                        pair_y - pair_radius - border_width/2,
                        pair_x + pair_radius + border_width/2, 
                        pair_y + pair_radius + border_width/2,
                        fill='#FFFFFF',  # 白色边框
                        outline='',
                        tags='dot'
                    )
                    
                    # 再绘制蓝色点
                    self.marker_canvas.create_oval(
                        pair_x - pair_radius, pair_y - pair_radius,
                        pair_x + pair_radius, pair_y + pair_radius,
                        fill="#0000FF",  # 蓝色
                        outline='',
                        tags='dot'
                    )
                
                # 庄家对子 - 右下角红色点（带白色边框）
                if is_banker_pair:
                    pair_x = x2 - pair_radius * 1.25
                    pair_y = y2 - pair_radius * 1.5
                    
                    # 先绘制白色边框
                    self.marker_canvas.create_oval(
                        pair_x - pair_radius - border_width/2, 
                        pair_y - pair_radius - border_width/2,
                        pair_x + pair_radius + border_width/2, 
                        pair_y + pair_radius + border_width/2,
                        fill='#FFFFFF',  # 白色边框
                        outline='',
                        tags='dot'
                    )
                    
                    # 再绘制红色点
                    self.marker_canvas.create_oval(
                        pair_x - pair_radius, pair_y - pair_radius,
                        pair_x + pair_radius, pair_y + pair_radius,
                        fill='#FF0000',  # 红色
                        outline='',
                        tags='dot'
                    )

            if text == "7-6":
                font_size = 10  # 稍微增大字体
            elif text == "猴和" and text == "猴闲" and text == "猴庄":
                font_size = 10
            else:
                font_size = 12  # 稍微增大字体

            self.marker_canvas.create_text(
                center_x, center_y,
                text=text,
                fill=text_color,
                font=('Arial', font_size, 'bold'),
                tags='dot'
            )

    def read_data_file(self):
        """读取数据文件内容"""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r') as f:
                return f.read().strip()
        return ''
        
    def _populate_betting_area(self, left, center, right):
        """填充下注区域的三部分"""
        self.betting_left = left
        self.betting_center = center
        self.betting_right = right
        
        # 左部分：下注格子
        self._populate_betting_left(left)
        
        # 中部分：按钮和显示
        self._populate_betting_center(center)
        
        # 右部分：筹码区域
        self._populate_betting_right(right)

    def _populate_betting_left(self, parent):
        """填充左部分：下注格子 - 固定高度长度（显示中文但保留内部键不变）"""
        # 显示用的中文映射（内部key不变）
        bet_display_map = {
            # Tiger 模式显示
            'Small Tiger': '小老虎',
            'Tiger Tie':   '老虎和',
            'Big Tiger':   '大老虎',
            'Tiger':       '老虎',
            'Tiger Pair':  '虎对子',
            # Monkey 模式显示
            'Monkey 6':    '猴老六',
            'Monkey Tie':  '猴老六和',
            'Big Monkey':  '猴子六仙',
            'Monkey 7':    '猴7点',
            'Lucky Monkey': '幸运猴子',
            # EZ 模式显示
            'Panda 8':     '熊猫8点',
            'Divine 9':    '神之9点',
            'Dragon 7':    '金龙7点',
            # classic / 2to1 模式显示
            'Dragon P': '闲家龙宝',
            'Quik': '快合',
            'Dragon B': '庄家龙宝',
            'Pair Player': '闲家对子',
            'Any Pair':   '任意对子',
            'Pair Banker': '庄家对子',
            # fabulous4 显示
            'P Fab Pair': '闲家神对',
            'B Fab Pair': '庄家神对',
            'P Fabulous 4': '闲神4点',
            'B Fabulous 4': '庄神4点',
            # 幸运7模式显示
            'Small Lucky 6': '小幸运6',
            'Lucky 6': '幸运6', 
            'Big Lucky 6': '大幸运6',
            'Lucky 7': '幸运7',
            'Super 7': '超级幸运7',
            # 通用三项
            'Player': '闲家',
            'Tie':    '和局',
            'Banker': '庄家'
        }

        # 根据模式选择赔率映射（保留原有键）
        if self.game_mode == "tiger":
            odds_map = {
                'Small Tiger': ('22:1', "#ff8ef6"),
                'Tiger Tie':   ('35:1', '#44ff44'),
                'Big Tiger':   ('50:1', '#44ffff'),
                'Tiger':       ('12/20:1', '#ffaa44'),
                'Tiger Pair':  ('4/20/100:1', '#ff44ff'),
                'Player':      ('1:1', '#4444ff'),
                'Tie':         ('8:1', '#44ff44'),
                'Banker':      ('1:1*', '#ff4444')
            }
        elif self.game_mode == "ez":
            odds_map = {
                'Pair Player': ('11:1', '#ff44ff'),
                'Pair Banker': ('11:1', '#ff44ff'),
                'Dragon P':    ('1-30:1', "#a08fff"),
                'Dragon B':    ('1-30:1', "#ff7158"),
                'Panda 8':     ('25:1', '#ffffff'),
                'Divine 9':    ('10/75:1', '#86ff94'),
                'Dragon 7':    ('40:1', '#ff8c00'),
                'Player':      ('1:1', '#4444ff'),
                'Tie':         ('8:1', '#44ff44'),
                'Banker':      ('1:1*', '#ff4444')
            }
        elif self.game_mode == "classic":
            odds_map = {
                'Dragon P': ('1-30:1', "#a08fff"),
                'Quik': ('1-50:1', "#ffab3e"),
                'Dragon B': ('1-30:1', "#ff7158"),
                'Pair Player': ('11:1', '#ff44ff'),
                'Any Pair':   ('5:1', '#44ffff'),
                'Pair Banker': ('11:1', '#ff44ff'),
                'Player':      ('1:1', '#4444ff'),
                'Tie':         ('8:1', '#44ff44'),
                'Banker':      ('0.95:1*', '#ff4444')
            }
        elif self.game_mode == "2to1":
            odds_map = {
                'Dragon P': ('1-30:1', "#a08fff"),
                'Quik': ('1-50:1', "#ffab3e"),
                'Dragon B': ('1-30:1', "#ff7158"),
                'Pair Player': ('11:1', '#ff44ff'),
                'Any Pair':   ('5:1', '#44ffff'),
                'Pair Banker': ('11:1', '#ff44ff'),
                'Player':      ('1:1*', '#4444ff'),
                'Tie':         ('8:1', '#44ff44'),
                'Banker':      ('1:1*', '#ff4444')
            }
        elif self.game_mode == "fabulous4":
            odds_map = {
                'P Fab Pair': ('1/4/7:1', '#ff8ef6'),
                'B Fab Pair': ('1/4/7:1', '#44ff44'),
                'P Fabulous 4': ('50:1', '#44ffff'),
                'B Fabulous 4': ('25:1', '#ffaa44'),
                'Player': ('1:1*', '#4444ff'),
                'Tie': ('8:1', '#44ff44'),
                'Banker': ('1:1*', '#ff4444')
            }
        elif self.game_mode == "lucky7":
            odds_map = {
                'Small Lucky 6': ('22:1', "#ff8ef6"),
                'Lucky 6 Tie':   ('35:1', '#44ff44'),
                'Big Lucky 6':   ('50:1', '#44ffff'),
                'Lucky 6':       ('12/20:1', '#ffaa44'),
                'Pair Player': ('11:1', '#ff44ff'),
                'Lucky 7': ('6/15:1', '#ffff00'),
                'Super 7': ('30/40/100:1#', "#00FFA2"),
                'Pair Banker': ('11:1', '#ff44ff'),
                'Player': ('1:1', '#4444ff'),
                'Tie': ('8:1', '#44ff44'),
                'Banker': ('1:1*', '#ff4444')
            }
        elif self.game_mode == "monkey":
            # 新增 monkey 的赔率显示
            odds_map = {
                'Monkey 6': ('12:1', '#FFD580'),
                'Monkey Tie': ('150:1', '#FFFF66'),
                'Big Monkey': ('5000:1', '#FFB6C1'),
                'Monkey 7': ('40:1', '#FF8C00'),
                'Lucky Monkey': ('1-75:1', '#FF69B4'),
                'Pair Player': ('11:1', '#ff44ff'),
                'Pair Banker': ('11:1', '#ff44ff'),
                'Player': ('1:1', '#4444ff'),
                'Tie': ('8:1', '#44ff44'),
                'Banker': ('1:1*', '#ff4444')
            }
            
        # 幸运7模式特别处理 - 添加奖池显示
        if self.game_mode == "lucky7":
            # 奖池显示框架 - 修改边框为黑色
            jackpot_frame = tk.Frame(parent, bg='black', height=40, bd=2, relief=tk.SOLID)  # 修改边框为黑色
            jackpot_frame.pack(fill=tk.BOTH, expand=True, pady=2)
            jackpot_frame.pack_propagate(False)
            
            # 创建内部框架用于放置两个标签
            inner_frame = tk.Frame(jackpot_frame, bg='#00FFA2')
            inner_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)  # 添加内边距显示黑色边框
            
            # 大奖标签 - 16号字体靠左显示
            self.jackpot_major_label = tk.Label(
                inner_frame,
                text=f"大奖: ${self.jackpot_amount:,.2f}",
                font=('Arial', 18, 'bold'),
                bg='#00FFA2',
                fg='black',
                anchor='w'  # 靠左对齐
            )
            self.jackpot_major_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            # 次奖标签 - 12号字体靠中间显示
            self.jackpot_minor_label = tk.Label(
                inner_frame,
                text=f"次奖: ${(self.jackpot_amount * 0.03):,.2f}",
                font=('Arial', 14, 'bold'),
                bg='#00FFA2',
                fg='black',
                anchor='center'  # 居中对齐
            )
            self.jackpot_minor_label.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)
        
        # 创建三行下注按钮 - 根据模式调整高度
        if self.game_mode == "lucky7":
            row_height = 67
        else:
            row_height = 80

        # 创建三行下注按钮 - 固定高度和宽度
        row1_frame = tk.Frame(parent, bg='#D0E7FF', height=row_height)
        row1_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row1_frame.pack_propagate(False)

        # 根据模式选择要显示的按钮（内部键不变）
        if self.game_mode == "tiger":
            buttons_to_show_1 = ['Small Tiger','Tiger Tie','Big Tiger']
        elif self.game_mode == "ez":
            buttons_to_show_1 = ['Panda 8','Divine 9','Dragon 7']
        elif self.game_mode == "classic" or self.game_mode == "2to1":
            buttons_to_show_1 = ['Dragon P', 'Quik', 'Dragon B']
        elif self.game_mode == "fabulous4":
            buttons_to_show_1 = ['P Fab Pair', 'B Fab Pair']
        elif self.game_mode == "lucky7":
            buttons_to_show_1 = ['Small Lucky 6', 'Lucky 6', 'Big Lucky 6']
        elif self.game_mode == "monkey":
            buttons_to_show_1 = ['Monkey 6', 'Monkey Tie', 'Big Monkey']

        for bt in buttons_to_show_1:
            odds, color = odds_map[bt]
            display_name = bet_display_map.get(bt, bt)
            btn = tk.Button(
                row1_frame,
                text=f"{odds}\n{display_name}\n~~",
                bg=color,
                font=('Arial', 12, 'bold'),
                height=3,
                width=12,
                wraplength=90,
                disabledforeground='#666666'
            )
            # 左键下注：传原始内部key bt（不改变）
            btn.config(command=lambda t=bt, b=btn: self.place_bet(t, b))
            # 右键清除：同样传原始key
            btn.bind('<Button-3>', lambda e, t=bt, b=btn: self._on_right_click_clear(e, t, b))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        row2_frame = tk.Frame(parent, bg='#D0E7FF', height=row_height)
        row2_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row2_frame.pack_propagate(False)

        row2_width = 12
        if self.game_mode == "tiger":
            buttons_to_show_2 = ['Tiger','Tiger Pair']
        elif self.game_mode == "ez":
            buttons_to_show_2 = ['Pair Player', 'Dragon P', 'Dragon B', 'Pair Banker']
            row2_width = 9
        elif self.game_mode == "classic" or self.game_mode == "2to1":
            buttons_to_show_2 = ['Pair Player', 'Any Pair', 'Pair Banker']
        elif self.game_mode == "fabulous4":
            buttons_to_show_2 = ['P Fabulous 4', 'B Fabulous 4']
        elif self.game_mode == "lucky7":
            buttons_to_show_2 = ['Pair Player', 'Lucky 7', 'Super 7', 'Pair Banker']
            row2_width = 9
        elif self.game_mode == "monkey":
            buttons_to_show_2 = ['Pair Player', 'Lucky Monkey', 'Monkey 7', 'Pair Banker']
            row2_width = 9

        for bt in buttons_to_show_2:
            odds, color = odds_map[bt]
            display_name = bet_display_map.get(bt, bt)
            btn = tk.Button(
                row2_frame,
                text=f"{odds}\n{display_name}\n~~",
                bg=color,
                font=('Arial', 12, 'bold'),
                height=3,
                width=row2_width,
                wraplength=100,
                disabledforeground='#666666'
            )
            btn.config(command=lambda t=bt, b=btn: self.place_bet(t, b))
            btn.bind('<Button-3>', lambda e, t=bt, b=btn: self._on_right_click_clear(e, t, b))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        row3_frame = tk.Frame(parent, bg='#D0E7FF', height=row_height)
        row3_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row3_frame.pack_propagate(False)

        for bt in ['Player','Tie','Banker']:
            odds, color = odds_map[bt]
            display_name = bet_display_map.get(bt, bt)
            text_color = 'white' if bt in ['Player','Banker'] else 'black'
            disabled_color = 'white' if bt in ['Player','Banker'] else '#666666'
            btn = tk.Button(
                row3_frame,
                text=f"{odds}\n{display_name}\n~~",
                bg=color,
                font=('Arial', 12, 'bold'),
                height=3,
                width=12,
                fg=text_color,
                disabledforeground=disabled_color,
                highlightthickness=0,
                highlightbackground='black',
                wraplength=80
            )
            btn.config(command=lambda t=bt, b=btn: self.place_bet(t, b))
            btn.bind('<Button-3>', lambda e, t=bt, b=btn: self._on_right_click_clear(e, t, b))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        # 说明 - 保持原来英文说明不变（如果要中文化可以单独替换这段）
        if self.game_mode == "tiger":
            explanation = "*庄家获胜点数为6点 赔付50%"
        elif self.game_mode == "lucky7":
            explanation = "#下注1千自动参加大奖 | *庄家获胜点数为6点 赔付50%"
        elif self.game_mode == "ez" or self.game_mode == "monkey":
            explanation = "*庄家获胜点数为3张牌7点 平局"
        elif self.game_mode == "classic":
            explanation = "*庄家每局支付5%佣金"
        elif self.game_mode == "2to1":
            explanation = "*3张牌8点或9点 赔付200% | 平局输"
        elif self.game_mode == "fabulous4":
            explanation = "*以1点获胜 赔付200% | 闲家4点赔付50% | 庄家4点平局"

        explanation_frame = tk.Frame(parent, bg='#D0E7FF', height=40)
        explanation_frame.pack(fill=tk.BOTH, expand=True, pady=2)
        explanation_frame.pack_propagate(False)

        tk.Label(
            explanation_frame,
            text=explanation,
            font=('微软雅黑', 12),
            bg='#D0E7FF'
        ).pack(expand=True)

    def clear_single_bet(self, bet_type):
        """清除单个下注类型的全部下注"""
        if bet_type in self.current_bets:
            # 获取该下注类型的总金额
            bet_amount = self.current_bets[bet_type]
            
            # 将金额加回余额
            self.balance += bet_amount
            
            # 从当前总下注中减去这个金额
            self.current_bet -= bet_amount
            
            # 从当前下注字典中移除这个下注类型
            del self.current_bets[bet_type]
            
            # 更新UI
            self.update_balance()
            self.current_bet_label.config(text=f"${self.current_bet:,}")
            
            # 更新按钮文本
            for btn in self.bet_buttons:
                if hasattr(btn, 'bet_type') and btn.bet_type == bet_type:
                    original_text = btn.cget("text").split('\n')
                    new_text = f"{original_text[0]}\n{original_text[1]}\n~~"
                    btn.config(text=new_text)

    def _populate_betting_center(self, parent):
        """填充中部分：按钮和显示"""
        balance_display_frame = tk.Frame(parent, bg='#D0E7FF')
        balance_display_frame.pack(fill=tk.X)  # 减少pady
        
        # 余额标签 - 减小字体
        self.balance_label = tk.Label(
            balance_display_frame,
            text=f"余额: ${int(round(self.balance)):,}",
            font=('Arial', 22),  # 从19改为16
            fg='black',
            bg='#D0E7FF'
        )
        self.balance_label.pack(side=tk.LEFT)
        
        # 信息按钮
        self.info_button = tk.Button(
            balance_display_frame,
            text="ℹ️",
            command=self.show_game_instructions,
            bg='#4B8BBE',
            fg='white',
            font=('Arial', 8)
        )
        self.info_button.pack(side=tk.RIGHT, padx=5)
        self.info_button.bind('<Button-3>', self.show_remaining_cards)

        # 分隔线
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=2, pady=2)  # 减少pady

        # 每注限制
        minmax_frame = tk.Frame(parent, bg='#D0E7FF')
        minmax_frame.pack(fill=tk.X)

        table_border_color = "#d70000"
        table_bg = '#f9f9f9'

        outer_frame = tk.Frame(minmax_frame, bg=table_border_color, bd=2, relief=tk.SOLID)
        outer_frame.pack(padx=5, pady=2, fill=tk.X)

        header_frame = tk.Frame(outer_frame, bg=table_border_color)
        header_frame.pack(fill=tk.X)

        content_frame = tk.Frame(outer_frame, bg=table_bg)
        content_frame.pack(fill=tk.X)

        # 标题
        tk.Label(
            header_frame,
            text="边注最高",
            font=("Arial", 12, "bold"),
            bg=table_border_color,
            fg='white',
            width=9,
            pady=2
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            header_frame,
            text="和局最高",
            font=("Arial", 12, "bold"),
            bg=table_border_color,
            fg='white',
            width=9,
            pady=2
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            header_frame,
            text="主注最高",
            font=("Arial", 12, "bold"),
            bg=table_border_color,
            fg='white',
            width=9,
            pady=2
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 数值显示
        self.limit_value_labels = []

        for txt in ["30,000", "100,000", "500,000"]:
            lbl = tk.Label(
                content_frame,
                text=txt,
                font=("Arial", 12, "bold"),
                bg=table_bg,
                fg='black',
                width=9,
                pady=2
            )
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.limit_value_labels.append(lbl)

        # 整块都可以点击
        click_targets = [minmax_frame, outer_frame, header_frame, content_frame] + self.limit_value_labels
        for w in click_targets:
            w.bind("<Button-1>", self._toggle_high_bet_limits)

        # 初始化显示
        self._update_bet_limit_display()

        # 分隔线
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5, pady=2)  # 减少pady

        # DEAL/RESET 按钮行 - 减小字体
        btn_frame = tk.Frame(parent, bg='#D0E7FF')
        btn_frame.pack(fill=tk.X)  # 减少pady
        self.reset_button = tk.Button(
            btn_frame, text="重设金额", command=self.reset_bets,
            bg='#ff4444', fg='white',
            font=('微软雅黑', 16, 'bold')  # 从18改为16
        )
        self.reset_button.pack(side=tk.TOP, expand=True, fill=tk.X, padx=10, pady=2)  # 减少pady
        self.deal_button = tk.Button(
            btn_frame, text="开始游戏 (Enter)", command=self.start_game,
            bg='gold', fg='black',
            font=('微软雅黑', 16, 'bold')  # 从18改为16
        )
        self.deal_button.pack(side=tk.TOP, expand=True, fill=tk.X, padx=10, pady=(0,2))  # 减少pady

        # 分隔线 + 当前/上次下注显示
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5)  # 减少pady

        current_bet_frame = tk.Frame(parent, bg='#D0E7FF')
        current_bet_frame.pack()
        tk.Label(
            current_bet_frame, text="当前下注:", width=12,
            font=('微软雅黑', 16), bg='#D0E7FF'  # 从18改为16
        ).pack(side=tk.LEFT)
        self.current_bet_label = tk.Label(
            current_bet_frame, text="$0", width=10,
            font=('微软雅黑', 16), bg='#D0E7FF'  # 从18改为16
        )
        self.current_bet_label.pack(side=tk.RIGHT)

        last_win_frame = tk.Frame(parent, bg='#D0E7FF')
        last_win_frame.pack(pady=3)  # 减少pady
        tk.Label(
            last_win_frame, text="上局获胜:", width=12,
            font=('微软雅黑', 16), bg='#D0E7FF'  # 从18改为16
        ).pack(side=tk.LEFT)
        self.last_win_label = tk.Label(
            last_win_frame, text="$0", width=10,
            font=('微软雅黑', 16), bg='#D0E7FF'  # 从18改为16
        )
        self.last_win_label.pack(side=tk.RIGHT)

    def show_remaining_cards(self, event=None):
        """显示剩余牌堆的统计信息"""
        # 定义花色和点数
        SUITS = ['Club', 'Diamond', 'Heart', 'Spade']
        RANKS = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
        
        # 统计剩余牌堆（从当前位置到末尾）
        remaining_deck = self.game.deck[self.game.cut_position:]
        
        remaining_cards = {suit: {rank: 0 for rank in RANKS} for suit in SUITS}
        
        # 遍历剩余牌堆进行统计
        for card in remaining_deck:
            suit, rank = card
            remaining_cards[suit][rank] += 1
        
        # 创建新窗口
        win = tk.Toplevel(self)
        win.title("剩余牌堆统计")
        win.geometry("600x400")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        
        # 计算窗口居中位置
        self.update_idletasks()
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_width = self.winfo_width()
        main_height = self.winfo_height()
        
        popup_width = 600
        popup_height = 400
        x = main_x + (main_width - popup_width) // 2
        y = main_y + (main_height - popup_height) // 2
        win.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        
        # 主框架
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 标题 - 显示剩余牌数
        total_remaining = len(remaining_deck)
        title_label = tk.Label(
            main_frame, 
            text=f"剩余{total_remaining}张牌",
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
        tk.Label(header_frame, text="", width=6, bg='#F0F0F0').pack(side=tk.LEFT, padx=3)
        
        # 点数标题
        for rank in RANKS:
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
            suit_display = {'Club': '梅花', 'Diamond': '方块', 'Heart': '红心', 'Spade': '黑桃'}
            suit_label = tk.Label(
                row_frame, 
                text=suit_display.get(suit, suit), 
                width=6, 
                font=('Arial', 10, 'bold'),
                bg='#F0F0F0',
                relief=tk.RAISED,
                bd=1
            )
            suit_label.pack(side=tk.LEFT, padx=1)
            
            suit_total = 0
            
            # 每种点数的数量
            for rank in RANKS:
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
        total_row_frame.pack(fill=tk.X)
        
        # 总计标签
        tk.Label(
            total_row_frame, 
            text="总计", 
            width=6, 
            font=('Arial', 10, 'bold'),
            bg='#F0F0F0',
            relief=tk.RAISED,
            bd=1
        ).pack(side=tk.LEFT, padx=1)
        
        # 每种点数的总计
        rank_totals = {}
        for rank in RANKS:
            rank_totals[rank] = 0
            for suit in SUITS:
                rank_totals[rank] += remaining_cards[suit][rank]
        
        grand_total = 0
        for rank in RANKS:
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

    def _populate_betting_right(self, parent):
        """填充右部分：筹码区域"""
        # 筹码区
        chips_frame = tk.Frame(parent, bg='#D0E7FF')
        chips_frame.pack(pady=5)
        row1 = tk.Frame(chips_frame, bg='#D0E7FF')
        row1.pack()
        for text, bg_color in [
            ('100', '#000000'),
            ('500', "#FF7DDA"),
            ('1千', "#ab0058")
        ]:
            btn = self._create_chip_button(row1, text, bg_color)
            btn.pack(side=tk.LEFT, padx=2)
        row2 = tk.Frame(chips_frame, bg='#D0E7FF')
        row2.pack(pady=3)
        for text, bg_color in [
            ('5千', '#ff0000'),
            ('1万', '#800080'),
            ('3万', '#ffbf00')
        ]:
            btn = self._create_chip_button(row2, text, bg_color)
            btn.pack(side=tk.LEFT, padx=2)
        row3 = tk.Frame(chips_frame, bg='#D0E7FF')
        row3.pack(pady=3)
        for text, bg_color in [
            ('5万', '#006400'),
            ('10万', '#00ff00'),
            ('50万', '#0000ff')
        ]:
            btn = self._create_chip_button(row3, text, bg_color)
            btn.pack(side=tk.LEFT, padx=2)

        # 当前选中筹码显示
        self.current_chip_label = tk.Label(
            parent,
            text="筹码: $1,000",
            font=('Arial', 18),
            fg='black',
            bg='#D0E7FF'
        )
        self.current_chip_label.pack(side=tk.LEFT, padx=0)

        # 设置默认选中的筹码（1千）
        self._set_default_chip()

    def _set_default_chip(self):
        """设置默认选中的筹码（1千），并显示金色边框"""
        self._set_chip_by_amount(1000)

    def _setup_bindings(self):
        self.bind('<Return>', lambda e: self.start_game())

    def place_bet(self, bet_type, btn_widget=None):
        # 如果是通过 command 调用并传入了按钮，先检查按钮是否已被禁用
        if btn_widget is not None and str(btn_widget.cget('state')) == 'disabled':
            return

        # 额外保险：查找对应 bet_type 的按钮，若存在且 disabled，则忽略
        for b in getattr(self, 'bet_buttons', []):
            if hasattr(b, 'bet_type') and b.bet_type == bet_type:
                if str(b.cget('state')) == 'disabled':
                    return
                break

        amount = int(self.selected_bet_amount)
        existing = int(self.current_bets.get(bet_type, 0))

        limits = self._get_bet_limits()
        if bet_type in ('Player', 'Banker'):
            limit = limits["main"]
        elif bet_type == 'Tie':
            limit = limits["tie"]
        else:
            limit = limits["side"]

        allowed_remaining = limit - existing
        if allowed_remaining <= 0:
            messagebox.showwarning("投注上限", f"当前投注已达到上限${limit:,}，无法再下注。")
            return

        to_place = min(amount, allowed_remaining, self.balance)

        if to_place <= 0:
            if self.balance <= 0:
                messagebox.showerror("Error", "余额不足")
            return

        self.balance -= to_place
        self.current_bet += to_place
        self.current_bets[bet_type] = self.current_bets.get(bet_type, 0) + to_place

        self.update_balance()
        self.current_bet_label.config(text=f"${self.current_bet:,}")

        for btn in self.bet_buttons:
            if hasattr(btn, 'bet_type') and btn.bet_type == bet_type:
                original_text = btn.cget("text").split('\n')
                top = original_text[0] if len(original_text) >= 1 else btn.cget("text")
                mid = original_text[1] if len(original_text) >= 2 else ""
                new_text = f"{top}\n{mid}\n${self.current_bets[bet_type]:,}"
                btn.config(text=new_text)

    def _on_right_click_clear(self, event, bet_type, btn_widget):
        # 当按钮 disabled 时不处理右键清除
        if str(btn_widget.cget('state')) == 'disabled':
            return
        # 否则调用原来的清除函数
        self.clear_single_bet(bet_type)

    def start_game(self):
        self.table_canvas.itemconfig(self.result_bg_id, fill='', outline='')
        self.table_canvas.itemconfig(self.result_text_id, text='')
        
        # 检查牌堆剩余张数，如果少于60张则重新初始化
        if len(self.game.deck) - self.game.cut_position < 60:
            # 禁用按钮和键盘绑定
            for btn in self.bet_buttons:
                btn.config(state=tk.DISABLED)
            self.deal_button.config(state=tk.DISABLED)
            self.reset_button.config(state=tk.DISABLED)
            self.mode_combo.config(state='disabled')
            self.unbind('<Return>')
            
            # 重新初始化游戏
            self._initialize_game(True)
            return

        # 禁用按钮
        for btn in self.bet_buttons:
            btn.config(state=tk.DISABLED)
        self.deal_button.config(state=tk.DISABLED)
        self.reset_button.config(state=tk.DISABLED)
        self.unbind('<Return>')
        self.mode_combo.config(state='disabled')
        
        self.game.play_game()
        self.animate_dealing()

    def animate_dealing(self):
        self.table_canvas.delete('all')
        self.point_labels.clear()
        self._draw_table_labels()

        # ← NEW: create two "total" displays
        # positions chosen below the "PLAYER" and "BANKER" areas:
        self.player_total_id = self.table_canvas.create_text(
            120, 200, text="~", font=('Arial', 80, 'bold'), fill='white')
        self.banker_total_id = self.table_canvas.create_text(
            880, 200, text="~", font=('Arial', 80, 'bold'), fill='white')

        # track which cards we've flipped face-up
        self.revealed_cards = {'player': [], 'banker': []}

        self._deal_initial_cards()
        self.after(1000, self._reveal_initial_phase1)

    def _deal_initial_cards(self):
        self.initial_card_ids = []
        # Player cards
        for i, pos in enumerate(self._get_card_positions("player")[:2]):
            self._animate_card_entrance("player", i, pos)
        # Banker cards
        for i, pos in enumerate(self._get_card_positions("banker")[:2]):
            self._animate_card_entrance("banker", i, pos)

    def _animate_card_entrance(self, hand_type, index, target_pos):
        start_x, start_y = 500, 0
        card_id = self.table_canvas.create_image(start_x, start_y, image=self.back_image)
        
        def move_step(step=0):
            if step <= 30:
                x = start_x + (target_pos[0]-start_x)*(step/30)
                y = start_y + (target_pos[1]-start_y)*(step/30)
                self.table_canvas.coords(card_id, x, y)
                self.after(10, move_step, step+1)
        
        move_step()
        self.initial_card_ids.append((hand_type, card_id))

    def _reveal_initial_phase1(self):
        card_info = self.initial_card_ids[0]
        real_card = self.game.player_hand[0]
        self._flip_card(card_info, real_card, 0)
        self.after(500, self._reveal_initial_phase3)

    def _reveal_initial_phase2(self):
        card_info = self.initial_card_ids[1]
        real_card = self.game.player_hand[1]
        self._flip_card(card_info, real_card, 1)
        self.after(500, self._reveal_initial_phase4)

    def _reveal_initial_phase3(self):
        card_info = self.initial_card_ids[2]
        real_card = self.game.banker_hand[0]
        self._flip_card(card_info, real_card, 2)
        self.after(500, self._reveal_initial_phase2)

    def _reveal_initial_phase4(self):
        card_info = self.initial_card_ids[3]
        real_card = self.game.banker_hand[1]
        self._flip_card(card_info, real_card, 3)
        self.after(750, self._process_extra_cards)

    def _process_extra_cards(self):
        if len(self.game.player_hand) > 2:
            self._deal_extra_card("player", 2)
            self.after(1200, self._process_banker_extra)
        else:
            self._process_banker_extra()

    def _process_banker_extra(self):
        if len(self.game.banker_hand) > 2:
            self._deal_extra_card("banker", 2)
            self.after(1200, self.resolve_bets)
        else:
            self.resolve_bets()

    def _flip_card(self, card_info, real_card, seq, step=0):
        """
        用水平缩放模拟翻牌。
        card_info: (hand_type, canvas_image_id)
        real_card: ('Club','A') 形式或类似 tuple，用于打开正面图片
        seq: 序号（原来代码传的）
        step: 内部递归帧计数，外部调用不需要传
        """
        # 参数/帧设置（可以微调）
        steps = 12               # 总帧数（偶数更好）
        orig_w, orig_h = 120, 170  # 与 _load_assets 中使用的大小一致

        hand_type, card_id = card_info

        # 结束条件：最后一帧将真实牌面放回缓存的 full-size 图
        if step > steps:
            try:
                # 用缓存的完整图片作为最终帧（避免再次读取）
                self.table_canvas.itemconfig(card_id, image=self.card_images[real_card])
            except Exception:
                # 容错：如果出错，忽略
                pass

            # 记录已翻开的牌并更新总点数显示（与原逻辑一致）
            try:
                self.revealed_cards[hand_type].append(real_card)
            except Exception:
                # 初始化保护
                if not hasattr(self, 'revealed_cards'):
                    self.revealed_cards = {'player': [], 'banker': []}
                self.revealed_cards[hand_type].append(real_card)

            # 更新已翻开的点数显示（复用你原来计算/显示逻辑）
            try:
                total = sum(self.game.card_value(c) for c in self.revealed_cards[hand_type]) % 10
                display_text = "~" if total is None or str(total) == "~" else str(total)
                if hand_type == 'player':
                    self.table_canvas.itemconfig(self.player_total_id, text=display_text)
                else:
                    self.table_canvas.itemconfig(self.banker_total_id, text=display_text)
            except Exception:
                pass

            # 清理临时图像引用（可选）
            if card_id in getattr(self, '_temp_flip_images', {}):
                try:
                    del self._temp_flip_images[card_id]
                except Exception:
                    pass

            return

        # 计算当前帧显示哪一侧（前/背）和当前宽度
        half = steps // 2
        if step <= half:
            # 缩窄阶段：显示背面（从 full -> 1px）
            ratio = 1 - (step / float(half))
            use_back = True
        else:
            # 展开阶段：显示正面（从 1px -> full）
            ratio = (step - half) / float(half)
            use_back = False

        w = max(1, int(orig_w * ratio))

        # 生成缩放后的 PhotoImage（会缓存到 self._temp_flip_images 防止 GC）
        img = self._create_scaled_image(real_card, w, orig_h, use_back=use_back)
        # 保存引用避免被回收（key 用 canvas id）
        if not hasattr(self, '_temp_flip_images'):
            self._temp_flip_images = {}
        self._temp_flip_images[card_id] = img

        # 更新 canvas 上的图像
        try:
            self.table_canvas.itemconfig(card_id, image=img)
        except Exception:
            pass

        # 下一帧（延迟值可调，值越小越流畅但消耗更多）
        self.after(20, lambda: self._flip_card(card_info, real_card, seq, step+1))

    def _create_scaled_image(self, card, w, h, use_back=False):
        """
        按宽度 w、高度 h 生成 ImageTk.PhotoImage。
        如果 use_back=True 则读取背面 Background.png，否则读取正面 card 的图片文件。
        card: ('Club','A') 形式（当 use_back 为 True 时可以传 None）
        返回：ImageTk.PhotoImage
        注意：此函数每帧会打开并缩放图片，代价在可接受范围内；若担心性能可改为在 _load_assets 时缓存 PIL 原图。
        """
        from PIL import Image, ImageTk
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1')

        try:
            if use_back:
                path = os.path.join(card_dir, 'Background.png')
            else:
                # card 预期为 ('Club','A') 或类似
                path = os.path.join(card_dir, f"{card[0]}{card[1]}.png")

            img = Image.open(path).convert('RGBA')
            # 防止 w == 0
            w = max(1, int(w))
            img = img.resize((w, int(h)), Image.LANCZOS)

            return ImageTk.PhotoImage(img)
        except Exception as e:
            # 出问题时返回一个占位图（1px x h）以避免崩溃
            try:
                from PIL import Image
                placeholder = Image.new('RGBA', (max(1, int(w)), int(h)), (0,0,0,0))
                return ImageTk.PhotoImage(placeholder)
            except Exception:
                # 最后兜底：返回已有的 back_image 或任一缓存图片
                return getattr(self, 'back_image', None)

    def _create_flip_image(self, card, angle):
        # 获取当前脚本所在目录的绝对路径
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if angle < 90:
            # 修改为使用绝对路径
            bg_path = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1', 'Background.png')
            img = Image.open(bg_path)
        else:
            # 修改为使用绝对路径
            card_path = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1', f"{card[0]}{card[1]}.png")
            img = Image.open(card_path)
        
        img = img.resize((120, 170))
        return ImageTk.PhotoImage(img.rotate(angle if angle < 90 else 180-angle))

    def _deal_extra_card(self, hand_type, index):
        hand = self.game.player_hand if hand_type == "player" else self.game.banker_hand
        card = hand[index]
        target_pos = self._get_card_positions(hand_type)[index]
        card_id = self.table_canvas.create_image(500, 0, image=self.back_image)  # 从中心位置开始
        self.initial_card_ids.append((hand_type, card_id))
        for step in range(30):
            x = 500 + (target_pos[0]-500)*(step/30)  # 从500开始移动到目标x坐标
            y = 0 + (target_pos[1]-0)*(step/30)      # 从0开始移动到目标y坐标
            self.table_canvas.coords(card_id, x, y)
            self.update()
            self.after(10)
        self._flip_card((hand_type, card_id), card, index+4)

    def resolve_bets(self):
        is_natural = False
        is_stiger = False
        is_btiger = False

        p_bet = self.current_bets.get('Player', 0)
        b_bet = self.current_bets.get('Banker', 0)
        t_bet = self.current_bets.get('Tie', 0)
        payouts = 0

        # 更新累进大奖 - 每局下注的1%加入奖池（或你 _update_jackpot 实现的规则）
        total_bet_amount = sum(self.current_bets.values())
        self._update_jackpot(total_bet_amount)

        # 辅助函数：重新读取 jackpot 并更新 UI；采取立即读取 + 延迟再次读取的策略以保证文件写入完成后能读到最新值
        def _reload_jackpot():
            try:
                # 尝试从持久化位置读取最新值
                if hasattr(self, "_load_jackpot"):
                    self._load_jackpot()
                # 更新界面标签（若存在）
                if hasattr(self, 'jackpot_label'):
                    try:
                        ja = int(getattr(self, 'jackpot_amount', 0))
                    except Exception:
                        ja = getattr(self, 'jackpot_amount', 0) or 0
                    try:
                        self.jackpot_label.config(text=f"大奖: ${ja:,}")
                    except Exception:
                        pass
            except Exception:
                # 忽略读取错误
                pass

        # 如果为 lucky7 模式，立即尝试 reload，一并安排一次短延迟的再次 reload（防止文件写入延后）
        if getattr(self, 'game_mode', None) == "lucky7":
            try:
                _reload_jackpot()
            except Exception:
                pass
            try:
                # 延迟一次确保写入完成后能读到最新值（100ms）
                self.after(100, _reload_jackpot)
            except Exception:
                # 如果 self.after 不可用则忽略
                pass

        if self.game.winner == 'Player':
            if self.game_mode == "2to1" and len(self.game.player_hand) == 3 and self.game.player_score in (8, 9):
                payouts += p_bet * 3
            elif self.game_mode == "fabulous4":
                if self.game.player_score == 1:
                    payouts += p_bet * 3
                elif self.game.player_score == 4:
                    payouts += p_bet * 1.5
                else:
                    payouts += p_bet * 2
            else:
                payouts += p_bet * 2
        elif self.game.winner == 'Banker':
            if self.game_mode == "tiger":
                # 老虎模式：庄家6点赔付50%
                if self.game.banker_score == 6:
                    payouts += b_bet * 1.5
                else:
                    payouts += b_bet * 2
            elif self.game_mode == "lucky7":
                if self.game.banker_score == 6:
                    payouts += b_bet * 1.5
                else:
                    payouts += b_bet * 2
            elif self.game_mode == "ez":
                # EZ模式：庄家三张牌7点视为和局（退还本金）
                if len(self.game.banker_hand) == 3 and self.game.banker_score == 7:
                    payouts += b_bet  # 退还本金
                else:
                    payouts += b_bet * 2
            elif self.game_mode == "classic":
                payouts += b_bet * 1.95
            elif self.game_mode == "2to1":
                if len(self.game.banker_hand) == 3 and self.game.banker_score in (8, 9):
                    payouts += b_bet * 3
                else:
                    payouts += b_bet * 2
            elif self.game_mode == "fabulous4":
                if self.game.banker_score == 1:
                    payouts += b_bet * 3
                elif self.game.banker_score == 4:
                    payouts += b_bet
                else:
                    payouts += b_bet * 2
        elif self.game.winner == 'Tie':
            if self.game_mode == "2to1":
                payouts += t_bet * 9
            else:
                payouts += t_bet * 9 + p_bet + b_bet  # Tie赔付 + 退还本金

        side_results = self._check_side_bets()

        if self.game_mode == "tiger":
            tiger_bet = self.current_bets.get('Tiger Pair', 0)
            if tiger_bet and 'Tiger Pair' in side_results:
                odds = side_results['Tiger Pair']
                payouts += tiger_bet * (odds + 1)

            # Small Tiger
            st_bet = self.current_bets.get('Small Tiger', 0)
            if st_bet and 'Small Tiger' in side_results:
                odds = side_results['Small Tiger']
                payouts += st_bet * (odds + 1)

            # Big Tiger
            bt_bet = self.current_bets.get('Big Tiger', 0)
            if bt_bet and 'Big Tiger' in side_results:
                odds = side_results['Big Tiger']
                payouts += bt_bet * (odds + 1)

            # Tiger赔付
            tigers_bet = self.current_bets.get('Tiger', 0)
            if 'Tiger' in side_results:
                odds = side_results['Tiger']
                payouts += tigers_bet * (odds + 1)

            tiger_tie_bet = self.current_bets.get('Tiger Tie', 0)
            if 'Tiger Tie' in side_results:
                payouts += tiger_tie_bet * 36
        elif self.game_mode == "ez":
            # Dragon 7
            Dragon_bet = self.current_bets.get('Dragon 7', 0)
            if Dragon_bet and 'Dragon 7' in side_results:
                payouts += Dragon_bet * 41

            # Divine 9
            divine_bet = self.current_bets.get('Divine 9', 0)
            if divine_bet and 'Divine 9' in side_results:
                odds = side_results['Divine 9']
                payouts += divine_bet * (odds + 1)

            # Panda 8
            panda_bet = self.current_bets.get('Panda 8', 0)
            if 'Panda 8' in side_results:
                payouts += panda_bet * 26

            # 闲对
            ppair = self.current_bets.get('Pair Player', 0)
            if 'Pair Player' in side_results:
                payouts += ppair * 12  # 11:1 + 本金

            # 庄对
            bpair = self.current_bets.get('Pair Banker', 0)
            if 'Pair Banker' in side_results:
                payouts += bpair * 12  # 11:1 + 本金
            
            # Player Dragon
            pdragon = self.current_bets.get('Dragon P', 0)
            if 'Dragon P' in side_results:
                odds = side_results['Dragon P']
                payouts += pdragon * odds

            # Banker Dragon
            bdragon = self.current_bets.get('Dragon B', 0)
            if 'Dragon B' in side_results:
                odds = side_results['Dragon B']
                payouts += bdragon * odds

        elif self.game_mode == "monkey":
            # Monkey 6
            monkey_bet = self.current_bets.get('Monkey 6', 0)
            if 'Monkey 6' in side_results:
                payouts += monkey_bet * 13

            # Monkey Tie
            Monkey_Tie_bet = self.current_bets.get('Monkey Tie', 0)
            if 'Monkey Tie' in side_results:
                payouts += Monkey_Tie_bet * 151

            # Big Monkey
            BMonkey_bet = self.current_bets.get('Big Monkey', 0)
            if 'Big Monkey' in side_results:
                payouts += BMonkey_bet * 5001

            # Monkey 7 (40:1)
            monkey7_bet = self.current_bets.get('Monkey 7', 0)
            if monkey7_bet and 'Monkey 7' in side_results:
                payouts += monkey7_bet * 41  # 40:1 + 本金

            # Lucky Monkey 幸运猴子 - 新增赔付逻辑
            lucky_monkey_bet = self.current_bets.get('Lucky Monkey', 0)
            if lucky_monkey_bet and 'Lucky Monkey' in side_results:
                odds = side_results['Lucky Monkey']
                payouts += lucky_monkey_bet * (odds + 1)

            # 闲对
            ppair = self.current_bets.get('Pair Player', 0)
            if 'Pair Player' in side_results:
                payouts += ppair * 12  # 11:1 + 本金

            # 庄对
            bpair = self.current_bets.get('Pair Banker', 0)
            if 'Pair Banker' in side_results:
                payouts += bpair * 12  # 11:1 + 本金

        elif self.game_mode == "classic" or self.game_mode == "2to1":
            # Player Pair
            ppair = self.current_bets.get('Pair Player', 0)
            if 'Pair Player' in side_results:
                payouts += ppair * 12

            # Banker Pair
            bpair = self.current_bets.get('Pair Banker', 0)
            if 'Pair Banker' in side_results:
                payouts += bpair * 12

            # Any Pair
            apair = self.current_bets.get('Any Pair', 0)
            if 'Any Pair' in side_results:
                payouts += apair * 6

            # Player Dragon
            pdragon = self.current_bets.get('Dragon P', 0)
            if 'Dragon P' in side_results:
                odds = side_results['Dragon P']
                payouts += pdragon * odds

            # Quik
            quik = self.current_bets.get('Quik', 0)
            if 'Quik' in side_results:
                odds = side_results['Quik']
                payouts += quik * odds

            # Banker Dragon
            bdragon = self.current_bets.get('Dragon B', 0)
            if 'Dragon B' in side_results:
                odds = side_results['Dragon B']
                payouts += bdragon * odds
        elif self.game_mode == "fabulous4":
            # Player Fab Pair
            fab_pair_p = self.current_bets.get('P Fab Pair', 0)
            if 'P Fab Pair' in side_results:
                odds = side_results['P Fab Pair']
                payouts += fab_pair_p * (odds + 1)

            # Banker Fab Pair
            fab_pair_b = self.current_bets.get('B Fab Pair', 0)
            if 'B Fab Pair' in side_results:
                odds = side_results['B Fab Pair']
                payouts += fab_pair_b * (odds + 1)

            # P Fabulous 4
            fab4_p = self.current_bets.get('P Fabulous 4', 0)
            if 'P Fabulous 4' in side_results:
                payouts += fab4_p * 51

            # B Fabulous 4
            fab4_b = self.current_bets.get('B Fabulous 4', 0)
            if 'B Fabulous 4' in side_results:
                payouts += fab4_b * 26
        elif self.game_mode == "lucky7":
            # 小幸运6
            small_lucky6_bet = self.current_bets.get('Small Lucky 6', 0)
            if 'Small Lucky 6' in side_results:
                payouts += small_lucky6_bet * 23  # 22:1 + 本金

            # 幸运6
            lucky6_bet = self.current_bets.get('Lucky 6', 0)
            if 'Lucky 6' in side_results:
                odds = side_results['Lucky 6']
                payouts += lucky6_bet * (odds + 1)

            # 大幸运6
            big_lucky6_bet = self.current_bets.get('Big Lucky 6', 0)
            if 'Big Lucky 6' in side_results:
                payouts += big_lucky6_bet * 51  # 50:1 + 本金

            # 闲对
            ppair = self.current_bets.get('Pair Player', 0)
            if 'Pair Player' in side_results:
                payouts += ppair * 12  # 11:1 + 本金

            # 庄对
            bpair = self.current_bets.get('Pair Banker', 0)
            if 'Pair Banker' in side_results:
                payouts += bpair * 12  # 11:1 + 本金

            # 幸运7
            lucky7_bet = self.current_bets.get('Lucky 7', 0)
            if 'Lucky 7' in side_results:
                odds = side_results['Lucky 7']
                payouts += lucky7_bet * (odds + 1)

            # 超级7
            super7_bet = self.current_bets.get('Super 7', 0)
            if 'Super 7' in side_results:
                odds = side_results['Super 7']
                payouts += super7_bet * (odds + 1)

            # 累进大奖
            if 'Jackpot' in side_results:
                jackpot_share = side_results['Jackpot']
                jackpot_win = self.jackpot_amount * jackpot_share
                payouts += jackpot_win
                
                # 更新界面显示
                self._update_jackpot_display()

                # 从奖池中扣除并保存
                try:
                    self.jackpot_amount -= jackpot_win
                except Exception:
                    # 保底处理
                    try:
                        self.jackpot_amount = max(0, getattr(self, 'jackpot_amount', 0) - jackpot_win)
                    except Exception:
                        self.jackpot_amount = getattr(self, 'jackpot_amount', 0) or 0
                try:
                    if hasattr(self, "_save_jackpot"):
                        self._save_jackpot()
                except Exception:
                    pass

                # jackpot 被修改后立刻 reload（立即 + 延迟再次）
                self._save_jackpot()
                _reload_jackpot()
                self.after(100, _reload_jackpot)

                # 显示大奖信息
                try:
                    if jackpot_share == 1.0:
                        messagebox.showinfo("大奖", f"恭喜！获得头奖 ${int(jackpot_win):,}!")
                    else:
                        messagebox.showinfo("大奖", f"恭喜！获得次奖 ${int(jackpot_win):,}!")
                except Exception:
                    pass

        _reload_jackpot()
        self.after(100, _reload_jackpot)

        # 将赔付加入余额并清空当前投注
        self.balance += payouts
        self.current_bets.clear()
        self.update_balance()
        self.after(1000, self._animate_result_cards)

        # 更新按钮文字显示为 ~~（恢复初始状态）
        for btn in getattr(self, 'bet_buttons', []):
            if hasattr(btn, 'bet_type'):
                original_text = btn.cget("text").split('\n')
                top = original_text[0] if len(original_text) >= 1 else ""
                mid = original_text[1] if len(original_text) >= 2 else ""
                new_text = f"{top}\n{mid}\n~~"
                try:
                    btn.config(text=new_text)
                except Exception:
                    pass

        # 立即重置当前总下注
        self.current_bet = 0
        if hasattr(self, 'current_bet_label'):
            try:
                self.current_bet_label.config(text="$0")
            except Exception:
                pass

        # 更新 last_win（净盈利或总赔付，根据既有逻辑）
        try:
            if self.game.winner == 'Tie':
                self.last_win = int(payouts)
            else:
                self.last_win = int(max(payouts, 0))
            if hasattr(self, 'last_win_label'):
                self.last_win_label.config(text=f"${max(self.last_win, 0):,}")
        except Exception:
            pass

        # 判断显示条件（保持原逻辑）
        winner = self.game.winner
        p_score = self.game.player_score
        b_score = self.game.banker_score
        b_hand_len = len(self.game.banker_hand)

        def enable_buttons():
            for btn in getattr(self, 'bet_buttons', []):
                try:
                    btn.config(state=tk.NORMAL)
                except Exception:
                    pass
            try:
                self.reset_button.config(state=tk.NORMAL)
            except Exception:
                pass
            try:
                self.mode_combo.config(state='readonly')
            except Exception:
                pass

        # 保持原来行为：短暂暂停显示（注意：time.sleep 会阻塞 UI）
        try:
            time.sleep(1)
        except Exception:
            pass

        text = ""
        text_color = "black"
        bg_color = "#35654d"

        # 条件判断逻辑
        if winner == 'Player':
            if self.game_mode == "fabulous4":
                if p_score == 1:
                    text = "闲家1点获胜&闲家1赔2"
                elif p_score == 4:
                    text = "闲家4点获胜&闲家2赔1"
                else:
                    text = "闲家获胜"
            elif self.game_mode == "lucky7":
                if p_score == 7 and b_score == 6:
                    text = "闲家7点杀庄家6点 闲赢"
                elif p_score == 7:
                    text = "闲家7点获胜"
                else:
                    text = "闲家获胜"
            else:
                text = "闲家获胜"
            bg_color = '#4444ff'
            text_color = 'white'
        elif winner == 'Banker':
            if b_score == 6 and self.game_mode == "tiger":
                text = "小老虎" if b_hand_len == 2 else "大老虎"
            elif b_score == 7 and b_hand_len == 3 and self.game_mode == "ez" or b_score == 7 and b_hand_len == 3 and self.game_mode == "monkey":
                text = "庄家三张牌7点获胜 平局"
            elif b_score == 6 and self.game_mode == "lucky7":
                text = "小幸运6" if b_hand_len == 2 else "大幸运6"
            elif self.game_mode == "fabulous4":
                if b_score == 1:
                    text = "庄家1点获胜&庄家1赔2"
                elif b_score == 4:
                    text = "庄家4点获胜&庄家平局"
                else:
                    text = "庄家获胜"
            else:
                text = "庄家获胜"
            bg_color = '#ff4444'
            text_color = 'black'
        elif winner == 'Tie':
            if b_score == 6 and self.game_mode == "tiger":
                text = "老虎和"
            else:
                text = "和局"
            bg_color = '#44ff44'
            text_color = 'black'

        # 更新文字
        try:
            self.table_canvas.itemconfig(
                self.result_text_id,
                text=text,
                fill=text_color
            )
        except Exception:
            pass

        # 强制Canvas更新布局
        try:
            self.table_canvas.update_idletasks()
        except Exception:
            pass

        # 获取文字边界并更新背景框
        try:
            text_bbox = self.table_canvas.bbox(self.result_text_id)
            if text_bbox:
                padding = 15
                expanded_bbox = (
                    text_bbox[0]-padding,
                    text_bbox[1]-padding,
                    text_bbox[2]+padding,
                    text_bbox[3]+padding
                )
                try:
                    self.table_canvas.coords(self.result_bg_id, expanded_bbox)
                    self.table_canvas.itemconfig(
                        self.result_bg_id,
                        fill=bg_color,
                        outline=bg_color
                    )
                    self.table_canvas.tag_raise(self.result_text_id)
                    self.table_canvas.tag_lower(self.result_bg_id)
                except Exception:
                    pass
        except Exception:
            pass

        is_natural = False
        if self.game.winner != 'Tie':
            # 检查是否为例牌(2张牌8或9点)
            if self.game.winner == 'Player':
                is_natural = len(self.game.player_hand) == 2 and self.game.player_score >= 8
            else:  # Banker
                is_natural = len(self.game.banker_hand) == 2 and self.game.banker_score >= 8
                is_stiger = len(self.game.banker_hand) == 2 and self.game.banker_score == 6
                is_btiger = len(self.game.banker_hand) == 3 and self.game.banker_score == 6

        if self.game.winner == 'Tie' and self.game.banker_score == 6:
            is_stiger = True

        # 添加珠路图结果
        p0, p1 = self.game.player_hand[:2]
        b0, b1 = self.game.banker_hand[:2]
        is_player_pair = (p0[1] == p1[1])
        is_banker_pair = (b0[1] == b1[1])
        is_same_rank_pair = (is_player_pair and is_banker_pair and p0[1] == b0[1])

        def is_monkey_card(card):
            """判断是否为猴子牌（J、Q、K）"""
            return card[1] in ['J', 'Q', 'K']
        
        # 在调用 add_marker_result 的地方，添加猴子牌信息：
        player_third_card_monkey = False
        banker_third_card_monkey = False

        if len(self.game.player_hand) > 2:
            player_third_card_monkey = is_monkey_card(self.game.player_hand[2])
        if len(self.game.banker_hand) > 2:
            banker_third_card_monkey = is_monkey_card(self.game.banker_hand[2])

        self.add_marker_result(
            winner,
            is_natural=is_natural,
            is_stiger=is_stiger,
            is_btiger=is_btiger,
            player_hand_len=len(self.game.player_hand),
            banker_hand_len=len(self.game.banker_hand),
            player_score=self.game.player_score,
            banker_score=self.game.banker_score,
            is_player_pair=is_player_pair,
            is_banker_pair=is_banker_pair,
            is_same_rank_pair=is_same_rank_pair,
            # 添加猴子牌信息
            is_player_monkey=player_third_card_monkey,
            is_banker_monkey=banker_third_card_monkey
        )

        # 保存结果到数据文件
        result_char = ''
        if self.game.winner == 'Player':
            result_char = 'P'
        elif self.game.winner == 'Banker':
            result_char = 'B'
        elif self.game.winner == 'Tie':
            result_char = 'T'

        if result_char:
            try:
                self.save_game_result(result_char)
            except Exception:
                pass

        # 再次更新文字背景（保留原有两个阶段更新的行为）
        try:
            text_bbox = self.table_canvas.bbox(self.result_text_id)
            if text_bbox:
                padding = 10
                expanded_bbox = (
                    text_bbox[0]-padding,
                    text_bbox[1]-padding,
                    text_bbox[2]+padding,
                    text_bbox[3]+padding
                )
                try:
                    self.table_canvas.coords(self.result_bg_id, expanded_bbox)
                    self.table_canvas.itemconfig(
                        self.result_bg_id,
                        fill=bg_color,
                        outline=bg_color
                    )
                    self.table_canvas.tag_raise(self.result_text_id)
                    self.table_canvas.tag_lower(self.result_bg_id)
                except Exception:
                    pass
        except Exception:
            pass

        # 添加到大路结果
        tie_count = 1 if self.game.winner == 'Tie' else 0
        self.bigroad_results.append({
            'winner': self.game.winner,
            'tie_count': tie_count
        })
        try:
            self._update_bigroad()
        except Exception:
            pass
        try:
            self.update_pie_chart()
        except Exception:
            pass

        # 更新連勝記錄
        winner = self.game.winner
        if winner == self.current_streak_type:
            self.current_streak += 1
        else:
            self.current_streak = 1
            self.current_streak_type = winner

        # 更新最長連勝記錄
        if self.current_streak > self.longest_streaks.get(winner, 0):
            self.longest_streaks[winner] = self.current_streak
        try:
            self.update_streak_labels()
        except Exception:
            pass

        if not len(self.game.deck) - self.game.cut_position < 60:
            try:
                self.after(500, enable_buttons)
                self.after(2000, lambda: self.deal_button.config(state=tk.NORMAL))
                self.after(2000, lambda: self.bind('<Return>', lambda e: self.start_game()))
            except Exception:
                pass

        # 检查牌堆剩余张数，如果少于60张则重新初始化
        if len(self.game.deck) - self.game.cut_position < 60:
            # 禁用按钮和键盘绑定
            for btn in self.bet_buttons:
                btn.config(state=tk.DISABLED)
            self.deal_button.config(state=tk.DISABLED)
            self.reset_button.config(state=tk.DISABLED)
            self.mode_combo.config(state='disabled')
            self.unbind('<Return>')

            # 重新初始化游戏
            self._initialize_game(True)
            return

    def _update_bigroad(self):
        """
        更新"大路"
        • 先向下；如果向下越界或目标被占，则保持行不变、向右一格。
        • 新跑道 (胜方切换时)：起始列 = last_run_start_col + 1，在 row=0 放；若(0,col)被占则向右依次找。
        • 连胜时：只有当当前 winner == last_winner（都为非 Tie）才绘制连线。
        • Tie(和局)不占新格，在"最后一次非 Tie"所在格子累加：若整个开局都 Tie，则把(0,0)当隐形锚点，先画斜线再累加数字。
        """
        # 如果画布不存在，直接 return
        if not hasattr(self, 'bigroad_canvas'):
            return

        # 单元格与间距设置
        cell    = 25      # 每个格子的宽/高
        pad     = 2       # 格子之间的间距
        label_w = 30      # 左侧留给行号的宽度
        label_h = 20      # 顶部留给列号的高度

        # 1. 清空上一轮绘制的"data"层：删除 tags=('data',) 的所有元素
        self.bigroad_canvas.delete('data')

        # 2. 重置占用矩阵 (重新标记哪些格子已被占)
        self._bigroad_occupancy = [
            [False] * self._max_cols for _ in range(self._max_rows)
        ]

        # 3. 用于追踪"最后一次非 Tie" 的信息
        last_winner = None         # 上一次胜方 ('Player' / 'Banker')
        last_run_start_col = -1    # 上一次跑道的起始列 (初值 -1)
        prev_row, prev_col = None, None   # 上一次非 Tie 所占用的 (row, col)
        prev_cx, prev_cy = None, None     # 上一次非 Tie 圆点在 Canvas 上的中心

        # 4. Tie 累计字典：key=(row, col), value=已经累积的 Tie 次数
        tie_tracker = {}

        # 5. 遍历所有结果，逐局绘制
        for res in self.bigroad_results:
            winner = res.get('winner')  # 'Player', 'Banker' 或 'Tie'

            # —— A. 处理 Tie (和局) —— 
            if winner == 'Tie':
                # A.1 如果此前"从没出现过非 Tie" (prev_row / prev_col 皆为 None)，
                #     就把 (0,0) 当作"隐形锚点"并绘制第一条斜线
                if prev_row is None and prev_col is None:
                    r0, c0 = 0, 0
                    # 标记(0,0)被占
                    self._bigroad_occupancy[r0][c0] = True

                    # 计算 (0,0) 在 Canvas 上的中心坐标
                    x0 = label_w + pad + c0 * (cell + pad)
                    y0 = label_h + pad + r0 * (cell + pad)
                    cx0 = x0 + cell / 2
                    cy0 = y0 + cell / 2

                    # 更新"最后一次非 Tie" 指向 (0,0)，用于后续连线与 Tie 累加
                    prev_row, prev_col = r0, c0
                    prev_cx, prev_cy = cx0, cy0

                    # 记录这是第 1 次 Tie
                    tie_tracker[(r0, c0)] = 1

                    # 使用唯一 tag 管理此格的 Tie 绘制，先删除旧的（如果有）
                    tie_tag = f"tie_{r0}_{c0}"
                    self.bigroad_canvas.delete(tie_tag)

                    # 画绿色斜线（第一次通常不显示数字）
                    self.bigroad_canvas.create_line(
                        cx0 - 6, cy0 + 6, cx0 + 6, cy0 - 6,
                        width=4, fill='#00AA00', tags=('data', tie_tag)
                    )
                    continue  # 跳过本手圆点放置

                # A.2 已经出现过非 Tie，则把本局 Tie 累加到上一次非 Tie 所在格
                r0, c0 = prev_row, prev_col
                tie_tracker[(r0, c0)] = tie_tracker.get((r0, c0), 0) + 1
                cnt = tie_tracker[(r0, c0)]

                # 计算该格在 Canvas 上中心
                x0 = label_w + pad + c0 * (cell + pad)
                y0 = label_h + pad + r0 * (cell + pad)
                cx0 = x0 + cell / 2
                cy0 = y0 + cell / 2

                # 使用唯一 tag 管理此格的 Tie 绘制，先删除旧的（确保旧数字被清掉）
                tie_tag = f"tie_{r0}_{c0}"
                self.bigroad_canvas.delete(tie_tag)

                # 绘制绿色斜线（用 tie_tag 标记，便于后续删除/替换）
                self.bigroad_canvas.create_line(
                    cx0 - 10, cy0 + 10,   # 起点坐标
                    cx0 + 10, cy0 - 10,   # 终点坐标
                    width=4,
                    fill="#00AA00",
                    tags=('data', tie_tag)
                )

                # 如果 Tie 次数 > 1，再在中央画数字（并把数字置顶）
                if cnt > 1:
                    txt_id = self.bigroad_canvas.create_text(
                        cx0, cy0, text=str(cnt),
                        font=('Arial', 16, 'bold'), fill="#000000",
                        tags=('data', tie_tag)
                    )
                    # 确保数字在最上层
                    self.bigroad_canvas.tag_raise(txt_id)
                continue  # 本局仅是叠加 Tie，不放新圆点

            # —— B. 处理非 Tie (庄家 or 闲家) —— 

            # B.1 判断是否"新的跑道"（胜方切换，或之前尚未出现任何非 Tie）
            if last_winner is None or winner != last_winner:
                # 新跑道：跑道起始列 = 上一次跑道起始列 + 1
                run_start_col = last_run_start_col + 1
                last_run_start_col = run_start_col

                # 从 (row=0, col=run_start_col) 开始尝试放置；如果(0, run_start_col)已被占，就向右查找第一个未占列
                col0 = run_start_col
                while col0 < self._max_cols and self._bigroad_occupancy[0][col0]:
                    col0 += 1
                if col0 >= self._max_cols:
                    # 若找不到可用列，就跳出，不再绘制后续
                    break
                row0 = 0

                row, col = row0, col0

            else:
                # 同一跑道内连胜：优先"向下" -> (row = prev_row + 1, col = prev_col)
                # 如果"向下"越界或被占，就改为"行不变，列 + 1"
                nr = prev_row + 1
                nc = prev_col
                if nr < self._max_rows and not self._bigroad_occupancy[nr][nc]:
                    row, col = nr, nc
                else:
                    row = prev_row
                    col = prev_col + 1

            # B.2 如果计算出的 col >= 最大列数，就直接退出循环
            if col >= self._max_cols:
                break

            # 标记此 (row, col) 已被占
            self._bigroad_occupancy[row][col] = True

            # 计算此格在 Canvas 上的中心 (cx, cy)
            x0 = label_w + pad + col * (cell + pad)
            y0 = label_h + pad + row * (cell + pad)
            cx = x0 + cell / 2
            cy = y0 + cell / 2

            # B.3 如果是连胜 (winner == last_winner)，并且 prev_cx/prev_cy 已初始化，就画连线
            if prev_cx is not None and prev_cy is not None and winner == last_winner:
                line_color = "#FF3C00" if winner == 'Banker' else "#0091FF"
                
                # 判断移动方向并计算连线起点和终点
                if row == prev_row + 1 and col == prev_col:  # 向下移动
                    # 从上一个点的最下方连接到当前点的最上方
                    start_x, start_y = prev_cx, prev_cy + 9   # 上一个点的底部
                    end_x, end_y = cx, cy - 9                 # 当前点的顶部
                elif row == prev_row and col == prev_col + 1:  # 向右移动
                    # 从上一个点的最右方连接到当前点的最左方
                    start_x, start_y = prev_cx + 9, prev_cy   # 上一个点的右侧
                    end_x, end_y = cx - 9, cy                 # 当前点的左侧
                else:
                    # 其他情况（理论上不会出现），使用原来的直接连线
                    start_x, start_y = prev_cx, prev_cy
                    end_x, end_y = cx, cy
                
                self.bigroad_canvas.create_line(
                    start_x, start_y, end_x, end_y,
                    width=4, fill=line_color, tags=('data',)
                )

            # B.4 绘制圆点：庄家用红 (#FF3C00)，闲家用蓝 (#0091FF)
            dot_color = "#FF3C00" if winner == 'Banker' else "#0091FF"
            self.bigroad_canvas.create_oval(
                cx - 9, cy - 9, cx + 9, cy + 9,
                fill=dot_color, outline='', tags=('data',)
            )

            # B.5 如果该 (row, col) 之前已有 Tie 次数，就在圆点上叠加斜线与数字
            if (row, col) in tie_tracker:
                tcnt = tie_tracker[(row, col)]
                tie_tag = f"tie_{row}_{col}"
                self.bigroad_canvas.delete(tie_tag)

                # 画斜线（也加上 tie_tag）
                self.bigroad_canvas.create_line(
                    cx - 10, cy + 10,
                    cx + 10, cy - 10,
                    width=4,
                    fill='#00AA00',
                    tags=('data', tie_tag)
                )

                # 如果计数大于1，画数字并置顶
                if tcnt > 1:
                    txt_id = self.bigroad_canvas.create_text(
                        cx, cy, text=str(tcnt),
                        font=('Arial', 16, 'bold'), fill="#FFFFFF",
                        tags=('data', tie_tag)
                    )
                    self.bigroad_canvas.tag_raise(txt_id)

            # B.6 更新"最后一次非 Tie"的各项信息，以便下一局画连线或累计 Tie
            prev_row, prev_col = row, col
            prev_cx, prev_cy = cx, cy
            last_winner = winner

    def _animate_result_cards(self):
        offset = 25
        # 显式获取需要移动的卡片ID
        self.cards_to_move = {
            'player': [cid for htype, cid in self.initial_card_ids if htype == 'player'],
            'banker': [cid for htype, cid in self.initial_card_ids if htype == 'banker']
        }
        
        if self.game.winner == 'Player':
            self._move_cards('player', 0, offset)
        elif self.game.winner == 'Banker':
            self._move_cards('banker', 0, offset)
        elif self.game.winner == 'Tie':
            self._move_cards('player', offset, 0)
            self._move_cards('banker', -offset, 0)

    # 在类中添加这个方法
    def _move_cards(self, hand_type, dx, dy):
        """移动卡片动画效果"""
        # 获取所有卡片的最终位置（包含补牌）
        final_positions = self._get_card_positions(hand_type)
        
        # 确保有卡片需要移动
        if hand_type not in self.cards_to_move:
            return
            
        card_ids = self.cards_to_move[hand_type]
        
        # 确保卡片数量和位置数量匹配
        if len(card_ids) != len(final_positions):
            # 使用安全的方式处理
            n = min(len(card_ids), len(final_positions))
            card_ids = card_ids[:n]
            final_positions = final_positions[:n]
        
        # 建立卡片ID与最终位置的映射
        card_positions = {}
        for i, cid in enumerate(card_ids):
            if i < len(final_positions):
                card_positions[cid] = final_positions[i]
        
        # 执行同步动画
        for step in range(10):  # 10步动画
            for cid in card_ids:
                if cid in card_positions:  # 确保有位置信息
                    orig_x, orig_y = card_positions[cid]
                    new_x = orig_x + dx * (step/10)
                    new_y = orig_y + dy * (step/10)
                    self.table_canvas.coords(cid, new_x, new_y)
            self.update()
            self.after(30)

    def _check_side_bets(self):
        results = {}
        p = self.game.player_hand
        b = self.game.banker_hand
        p0, p1 = self.game.player_hand[:2]
        b0, b1 = self.game.banker_hand[:2]
        player_pair = (p0[1] == p1[1])
        banker_pair = (b0[1] == b1[1])

        if self.game_mode == "tiger":
            # 老虎百家乐边注检查
            # Any‐side pair (exactly one side)
            if player_pair ^ banker_pair:
                results['Tiger Pair'] = 4  # win 4:1
            # Both sides pair but different ranks
            elif player_pair and banker_pair and p0[1] != b0[1]:
                results['Tiger Pair'] = 20  # win 20:1
            # Both sides the same pair rank (rare)
            elif player_pair and banker_pair and p0[1] == b0[1]:
                results['Tiger Pair'] = 100  # win 100:1

            # 新的Tiger逻辑
            if self.game.winner == 'Banker' and self.game.banker_score == 6:
                if len(b) == 2:  # 两张牌
                    results['Tiger'] = 12  # 12:1
                else:  # 三张牌
                    results['Tiger'] = 20  # 20:1

            # now Small/Big Tiger
            # "Banker wins on a 6":
            if self.game.winner == 'Banker' and self.game.banker_score == 6:
                # length 2 ⇒ no third card dealt ⇒ Small Tiger
                if len(b) == 2:
                    results['Small Tiger'] = 22   # pays 22:1
                else:  # length 3 ⇒ Big Tiger
                    results['Big Tiger'] = 50     # pays 50:1

            # "Tie with 6" ⇒ Tiger Tie
            if self.game.winner == 'Tie' and self.game.banker_score == 6:
                results['Tiger Tie'] = 35   # pays 35:1

        elif self.game_mode == "ez":
            # EZ百家乐边注检查
            # Dragon 7
            if self.game.winner == 'Banker' and len(b) == 3 and self.game.banker_score == 7:
                results['Dragon 7'] = 40  # 40:1

            # Divine 9
            if self.game.winner == 'Player' and len(p) == 3 and self.game.player_score == 9:
                results['Divine 9'] = 10  # 10:1
            elif self.game.winner == 'Banker' and len(b) == 3 and self.game.banker_score == 9:
                results['Divine 9'] = 10  # 10:1
            elif self.game.winner == 'Tie' and len(p) == 3 and len(b) == 3 and self.game.player_score == 9 and self.game.banker_score == 9:
                results['Divine 9'] = 75  # 75:1

            # Panda 8
            if self.game.winner == 'Player' and len(p) == 3 and self.game.player_score == 8:
                results['Panda 8'] = 25  # 25:1

            # Player Pair
            if player_pair:
                results['Pair Player'] = 11  # 11:1

            # Banker Pair
            if banker_pair:
                results['Pair Banker'] = 11  # 11:1

            # Dragon Player
            all_cards = p + b
            diff = self.game.player_score - self.game.banker_score
            if self.game.winner == 'Tie' and len(all_cards) == 4 and self.game.player_score in (8, 9):
                results['Dragon P'] = 1
            elif self.game.winner == 'Player' and len(all_cards) != 4:
                odds_map = {4:2, 5:3, 6:5, 7:7, 8:11, 9:31}
                results['Dragon P'] = odds_map.get(diff, 0)
            elif self.game.winner == 'Player' and len(all_cards) == 4 and self.game.player_score in (8, 9):
                # 自然 8/9 获胜 —— 龙宝按 1:1（即结算处会以 bet * 2 支付）
                results['Dragon P'] = 2

            # Dragon Banker
            diff = self.game.banker_score - self.game.player_score
            if self.game.winner == 'Tie' and len(all_cards) == 4 and self.game.banker_score in (8, 9):
                results['Dragon B'] = 1
            elif self.game.winner == 'Banker' and len(all_cards) != 4:
                odds_map = {4:2, 5:3, 6:5, 7:7, 8:11, 9:31}
                results['Dragon B'] = odds_map.get(diff, 0)
            elif self.game.winner == 'Banker' and len(all_cards) == 4 and self.game.banker_score in (8, 9):
                # 自然 8/9 获胜 —— 龙宝按 1:1（即结算处会以 bet * 2 支付）
                results['Dragon B'] = 2

        elif self.game_mode == "monkey":
            # 猴子牌定义
            monkey_ranks = ['J', 'Q', 'K']
            
            player_hand = self.game.player_hand
            banker_hand = self.game.banker_hand
            
            # 获取第三张牌（如果存在）
            player_third_card = player_hand[2] if len(player_hand) >= 3 else None
            banker_third_card = banker_hand[2] if len(banker_hand) >= 3 else None
            
            # Monkey 6: 闲家的补牌不是猴子牌，庄家的补牌是猴子牌
            if len(player_hand) >= 3 and len(banker_hand) >= 3:
                # 闲家补牌不是猴子牌 AND 庄家补牌是猴子牌
                if (player_third_card[1] not in monkey_ranks and 
                    banker_third_card[1] in monkey_ranks):
                    results['Monkey 6'] = 12  # 12:1赔率
            
            # Monkey Tie: 闲家的补牌不是猴子牌，庄家的补牌是猴子牌，同时本局结果为Tie
            if (len(player_hand) >= 3 and len(banker_hand) >= 3 and 
                self.game.winner == 'Tie'):
                if (player_third_card[1] not in monkey_ranks and 
                    banker_third_card[1] in monkey_ranks):
                    results['Monkey Tie'] = 150  # 150:1赔率
            
            # Big Monkey: 闲家庄家6张牌都是猴子牌
            if len(player_hand) == 3 and len(banker_hand) == 3:
                # 检查所有6张牌是否都是猴子牌
                all_cards = player_hand + banker_hand
                if all(card[1] in monkey_ranks for card in all_cards):
                    results['Big Monkey'] = 5000  # 5000:1赔率

            # Monkey 7 庄家3张牌7点获胜   
            if len(b) == 3 and self.game.banker_score == 7 and self.game.winner == 'Banker':
                results['Monkey 7'] = 40  # 40:1赔率

            # Lucky Monkey 幸运猴子 - 新增逻辑
            if len(player_hand) >= 3 or len(banker_hand) >= 3:
                player_drew = len(player_hand) >= 3
                banker_drew = len(banker_hand) >= 3
                
                player_monkey = player_third_card[1] in monkey_ranks if player_drew else False
                banker_monkey = banker_third_card[1] in monkey_ranks if banker_drew else False
                
                # 双方都补牌
                if player_drew and banker_drew:
                    # 双方补牌都是猴子且花色相同
                    if (player_monkey and banker_monkey and 
                        player_third_card[0] == banker_third_card[0] and
                        player_third_card[1] == banker_third_card[1]):
                        results['Lucky Monkey'] = 75  # 75:1
                    # 双方补牌都是猴子且点数相同
                    elif (player_monkey and banker_monkey and 
                        player_third_card[1] == banker_third_card[1]):
                        results['Lucky Monkey'] = 25  # 25:1
                    # 双方补牌都是猴子
                    elif player_monkey and banker_monkey:
                        results['Lucky Monkey'] = 10  # 10:1
                    # 只有一方是猴子
                    elif player_monkey ^ banker_monkey:
                        results['Lucky Monkey'] = 1   # 1:1
                # 仅玩家补牌且为猴子
                elif player_drew and player_monkey:
                    results['Lucky Monkey'] = 3  # 3:1
                # 仅庄家补牌且为猴子  
                elif banker_drew and banker_monkey:
                    results['Lucky Monkey'] = 8  # 8:1

            # Player Pair
            if player_pair:
                results['Pair Player'] = 11  # 11:1

            # Banker Pair
            if banker_pair:
                results['Pair Banker'] = 11  # 11:1

        elif self.game_mode in ("classic", "2to1"):
            # 经典百家乐边注检查
            # Player Pair
            if player_pair:
                results['Pair Player'] = 11  # 11:1

            # Banker Pair
            if banker_pair:
                results['Pair Banker'] = 11  # 11:1

            # Any Pair
            if player_pair or banker_pair:
                results['Any Pair'] = 5  # 5:1

            all_cards = p + b

            # Dragon Player
            diff = self.game.player_score - self.game.banker_score
            if self.game.winner == 'Tie' and len(all_cards) == 4 and self.game.player_score in (8, 9):
                results['Dragon P'] = 1
            elif self.game.winner == 'Player' and len(all_cards) != 4:
                odds_map = {4:2, 5:3, 6:5, 7:7, 8:11, 9:31}
                results['Dragon P'] = odds_map.get(diff, 0)
            elif self.game.winner == 'Player' and len(all_cards) == 4 and self.game.player_score in (8, 9):
                # 自然 8/9 获胜 —— 龙宝按 1:1（即结算处会以 bet * 2 支付）
                results['Dragon P'] = 2

            # Dragon Banker
            diff = self.game.banker_score - self.game.player_score
            if self.game.winner == 'Tie' and len(all_cards) == 4 and self.game.banker_score in (8, 9):
                results['Dragon B'] = 1
            elif self.game.winner == 'Banker' and len(all_cards) != 4:
                odds_map = {4:2, 5:3, 6:5, 7:7, 8:11, 9:31}
                results['Dragon B'] = odds_map.get(diff, 0)
            elif self.game.winner == 'Banker' and len(all_cards) == 4 and self.game.banker_score in (8, 9):
                # 自然 8/9 获胜 —— 龙宝按 1:1（即结算处会以 bet * 2 支付）
                results['Dragon B'] = 2

            # Quik
            combined = self.game.player_score + self.game.banker_score
            if combined == 0:
                results['Quik'] = 51  # 50:1
            elif combined == 18:
                results['Quik'] = 26  # 25:1
            elif combined in [1,2,3,15,16,17]:
                results['Quik'] = 2   # 1:1

        elif self.game_mode == "fabulous4":
            # Player Fab Pair
            if player_pair:
                if p0[0] == p1[0]:  # 同花对子
                    results['P Fab Pair'] = 7  # 7:1
                else:  # 非同花对子
                    results['P Fab Pair'] = 4  # 4:1
            elif p0[0] == p1[0]:  # 同花非对子
                results['P Fab Pair'] = 1  # 1:1

            # Banker Fab Pair
            if banker_pair:
                if b0[0] == b1[0]:  # 同花对子
                    results['B Fab Pair'] = 7  # 7:1
                else:  # 非同花对子
                    results['B Fab Pair'] = 4  # 4:1
            elif b0[0] == b1[0]:  # 同花非对子
                results['B Fab Pair'] = 1  # 1:1

            # P Fabulous 4
            if self.game.winner == 'Player' and self.game.player_score == 4:
                results['P Fabulous 4'] = 50  # 50:1

            # B Fabulous 4
            if self.game.winner == 'Banker' and self.game.banker_score == 4:
                results['B Fabulous 4'] = 25  # 25:1
        elif self.game_mode == "lucky7":
            # 小幸运6 - 庄家2张牌6点获胜
            if self.game.winner == 'Banker' and len(b) == 2 and self.game.banker_score == 6:
                results['Small Lucky 6'] = 22  # 22:1
            
            # 幸运6
            if self.game.winner == 'Banker' and self.game.banker_score == 6:
                if len(b) == 2:
                    results['Lucky 6'] = 12  # 12:1
                else:  # 3张牌
                    results['Lucky 6'] = 20  # 20:1
            
            # 大幸运6 - 庄家3张牌6点获胜
            if self.game.winner == 'Banker' and len(b) == 3 and self.game.banker_score == 6:
                results['Big Lucky 6'] = 50  # 50:1
            
            # 闲对
            if player_pair:
                results['Pair Player'] = 11  # 11:1
            
            # 庄对  
            if banker_pair:
                results['Pair Banker'] = 11  # 11:1
            
            # 幸运7
            if self.game.winner == 'Player' and self.game.player_score == 7:
                if len(p) == 2:
                    results['Lucky 7'] = 6  # 6:1
                else:  # 3张牌
                    results['Lucky 7'] = 15  # 15:1
            
            # 超级7 - 闲家7点 & 庄家6点
            if self.game.player_score == 7 and self.game.banker_score == 6:
                total_cards = len(p) + len(b)
                if total_cards == 4:
                    results['Super 7'] = 30  # 30:1
                elif total_cards == 5:
                    results['Super 7'] = 40  # 40:1
                elif total_cards == 6:
                    results['Super 7'] = 100  # 100:1
                
                # 累进大奖检查
                super7_bet = self.current_bets.get('Super 7', 0)
                if super7_bet >= 1000:
                    # 检查头奖条件
                    if (len(p) == 3 and self.game.player_score == 7 and 
                        all(card[0] == 'Diamond' for card in p) and
                        len(b) == 3 and self.game.banker_score == 6 and
                        all(card[0] == 'Spade' for card in b)):
                        results['Jackpot'] = 1.0  # 100%
                    
                    # 检查次奖条件
                    elif (len(p) == 3 and self.game.player_score == 7 and
                        all(card[0] in ['Diamond', 'Heart'] for card in p) and
                        len(b) == 3 and self.game.banker_score == 6 and
                        all(card[0] in ['Spade', 'Club'] for card in b)):
                        results['Jackpot'] = 0.03  # 3%

        return results

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${int(round(self.balance)):,}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
        return self.balance

# 在Baccarat.py中的main函数
def main(initial_balance=1000000, username="Guest"):
    app = BaccaratGUI(initial_balance, username)
    app.mainloop()
    return app.balance  # 正确返回数值

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")