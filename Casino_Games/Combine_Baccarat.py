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
        self.title("Baccarat")
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
            'B Fabulous 4': 0
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

    def show_game_instructions(self):
        if self.game_mode == "classic":
            instructions = """
            🎮 Classic Baccarat game rules 🎮

            [Basic gameplay]
            1. Players bet on the Player, Tie, Banker
            2. Both sides are dealt 2-3 cards, and the one with the closest to 9 wins
            3. Point calculation: A=1, 10/J/Q/K=0, others are calculated at face value
            4. Only the single digit value is taken (such as 7+8=15→5)

            💰 Odds table 💰
            Player                           1:1
            Tie                                 8:1
            Banker                          0.95:1
            == Side bet == 
            Player pair                   11:1
            Any pair#                     5:1
            Banker pair                  11:1
            Dragon P(Player)        1-30:1
            Quik^                           1-30:1
            Dragon B(Banker)       1-30:1*

            📌 Special Rules 📌
            # Any pair means rather Player or Banker is pair

            *Dragon bet:
            Win more than other side 9 points  30:1
            Win more than other side 8 points  10:1
            Win more than other side 7 points  6:1
            Win more than other side 6 points  4:1
            Win more than other side 5 points  2:1
            Win more than other side 4 points  1:1
            Win in natural (Tie Push)                     1:1

            ^Quik:
            Combined final Player and Banker points. (such as 7+8=15)
            combine number is 0                                        50:1
            combine number is 18                                      25:1
            combine number is 1, 2, 3, 15, 16, 17            1:1
            """
        elif self.game_mode == "tiger":
            instructions = """
            🎮 Tiger Baccarat game rules 🎮

            [Basic gameplay]
            1. Players bet on the Player, Tie, Banker
            2. Both sides are dealt 2-3 cards, and the one with the closest to 9 wins
            3. Point calculation: A=1, 10/J/Q/K=0, others are calculated at face value
            4. Only the single digit value is taken (such as 7+8=15→5)

            ⚡ Special card types ⚡
            ▪ Small Tiger: Banker has a winning two-card total of 6.
            ▪ Big Tiger: Banker has a winning three-card total of 6.

            💰 Odds table 💰
            Player           1:1
            Tie                 8:1
            Banker          1:1*
            == Side bet ==
            Tiger pair     4-100:1#
            Tiger             12/20:1^
            Small Tiger   22:1
            Big Tiger       50:1
            Tiger Tie       35:1

            📌 Special Rules 📌
            * Banker's has a winning card of 6 are reduced to 0.5:1

            # 4:1 for single pair
            # 20:1 for double pairs
            # 100:1 for twins pairs

            ^ 12:1 for Small Tiger and 20:1 for Big Tiger
            """
        elif self.game_mode == "ez":
            instructions = """
            🎮 EZ Baccarat game rules 🎮

            [Basic gameplay]
            1. Players bet on the Player, Tie, Banker
            2. Both sides are dealt 2-3 cards, and the one with the closest to 9 wins
            3. Point calculation: A=1, 10/J/Q/K=0, others are calculated at face value
            4. Only the single digit value is taken (such as 7+8=15→5)

            ⚡ Special card types ⚡
            ▪ Panda 8: Player has a winning three-card total of 8.
            ▪ Dragon 7: Banker has a winning three-card total of 7.

            💰 Odds table 💰
            Player                  1:1
            Tie                        8:1
            Banker                 1:1*
            == Side bet ==
            Monkey 6          12:1△
            Monkey Tie       150:1△
            Big Monkey       5000:1△
            Panda 8              25:1^
            Divine 9             10/75:1#^
            Dragon 7           40:1^

            📌 Special Rules 📌
            * Banker PUSH when Banker winning three-card total of 7.

            △ Monkey means 'J' 'Q' 'K' only.
            Requirment to win Monkey 6: 
                - Player draw a non-monkey card.
                - Banker draw a monkey card.
                - Result of this round is NOT Tie.
            Requirment to win Monkey 6 Tie: 
                - Player draw a non-monkey card.
                - Banker draw a monkey card.
                - Result of this round is Tie.
            Requirment to win Big Monkey: 
                - 6 monkey cards.

            # 10:1 for either side winning three-card total of 9.
            # 75:1 for both side winning three-card total of 9.

            ^ Must be winning three-card.
            """
        elif self.game_mode == "2to1":
            instructions = """
            🎮 2 To 1 Baccarat game rules 🎮

            [Basic gameplay]
            1. Players bet on the Player, Tie, Banker
            2. Both sides are dealt 2-3 cards, and the one with the closest to 9 wins
            3. Point calculation: A=1, 10/J/Q/K=0, others are calculated at face value
            4. Only the single digit value is taken (such as 7+8=15→5)

            💰 Odds table 💰
            Player           1:1 (or 2:1 if win with 3-card 8/9)
            Tie              8:1 (Lose)
            Banker          1:1 (or 2:1 if win with 3-card 8/9)

            == Side bet == 
            Dragon P(Player)        1-30:1
            Quik^                   1-50:1
            Dragon B(Banker)        1-30:1*
            Pair Player             11:1
            Any pair#               5:1
            Pair Banker             11:1

            📌 Special Rules 📌
            * 2:1 payout for Player or Banker winning with 3-card 8 or 9.
            * Tie is considered lose (no push).

            # Any pair means rather Player or Banker is pair

            *Dragon bet:
            Win more than other side 9 points  30:1
            Win more than other side 8 points  10:1
            Win more than other side 7 points  6:1
            Win more than other side 6 points  4:1
            Win more than other side 5 points  2:1
            Win more than other side 4 points  1:1
            Win in natural (Tie Push)                     1:1

            ^Quik:
            Combined final Player and Banker points. (such as 7+8=15)
            combine number is 0                                        50:1
            combine number is 18                                      25:1
            combine number is 1, 2, 3, 15, 16, 17            1:1
            """
        elif self.game_mode == "fabulous4":
            instructions = """
            🎮 神奇4點百家樂遊戲規則 🎮

            [基本玩法]
            1. 玩家押注莊家、閒家或和局
            2. 雙方發2-3張牌，點數最接近9者勝
            3. 點數計算：A=1, 10/J/Q/K=0, 其他按面值計算
            4. 只取個位數值(如7+8=15→5)

            [主注賠率]
            莊家(Banker):
              • 以1點勝出：2:1
              • 以4點勝出：平手(Push)
              • 其他點數勝出：1:1

            閒家(Player):
              • 以1點勝出：2:1
              • 以4點勝出：0.5:1
              • 其他點數勝出：1:1

            和局(Tie): 8:1

            [邊注]
            1. 閒家神奇對子(Player Fab Pair):
              • 同花對子：7:1
              • 非同花對子：4:1
              • 同花非對子：1:1
              • 輸牌：失去下注

            2. 莊家神奇對子(Banker Fab Pair):
              • 同花對子：7:1
              • 非同花對子：4:1
              • 同花非對子：1:1
              • 輸牌：失去下注

            3. 閒家神奇4點(P Fabulous 4):
              • 閒家以4點勝出：50:1

            4. 莊家神奇4點(B Fabulous 4):
              • 莊家以4點勝出：25:1
            """

        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("Menu")
        win.geometry("700x650")
        win.resizable(False, False)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(win)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 使用Text组件支持格式
        text_area = tk.Text(
            win, 
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            font=('微软雅黑', 11),
            padx=15,
            pady=15,
            bg='#F0F0F0'
        )
        text_area.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_area.yview)

        # 插入带格式的文本
        text_area.insert(tk.END, instructions)

        # 禁用编辑
        text_area.config(state=tk.DISABLED)

        # 添加关闭按钮
        close_btn = ttk.Button(
            win,
            text="Close",
            command=win.destroy
        )
        close_btn.pack(pady=10)

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
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker0')
        
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
        dialog.title("Cut Card")
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
            tk.Label(dialog, text="Deck finish. \nShuffle and cut the card from 103 to 299",
                    font=('Arial', 10)).pack(pady=(8, 4))
        else:
            tk.Label(dialog, text="Please cut the card from 103 to 299",
                    font=('Arial', 10)).pack(pady=(8, 4))

        # UI 行：Entry 与 Scale（大小条）同步
        entry_frame = tk.Frame(dialog)
        entry_frame.pack(pady=(2, 6))

        tk.Label(entry_frame, text="Cut position:", font=('Arial', 10)).pack(side=tk.LEFT, padx=(6, 8))

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

        tk.Button(btn_frame, text="RANDOM", width=8, command=on_cancel).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="OK", width=8, command=on_ok).pack(side=tk.LEFT, padx=10)

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
            'P Fabulous 4': 0, 'B Fabulous 4': 0
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
        """翻开第一张牌并计算弃牌数"""
        # 翻牌动画
        def flip_step(step=0):
            steps = 12
            if step > steps:
                # 翻牌完成，显示牌面
                self.table_canvas.itemconfig(card_id, image=self.card_images[card])
                
                # 计算弃牌数
                deduct_map = {
                    'A': 1, 'J': 10, 'Q': 10, 'K': 10, 
                    '10': 10, '2':2, '3':3, '4':4, '5':5,
                    '6':6, '7':7, '8':8, '9':9
                }
                discard_count = deduct_map.get(card[1], 0)
                
                # 开始弃牌动画
                self.after(500, lambda: self._discard_cards_animation(discard_count))
                return
                
            # 翻牌动画逻辑
            half = steps // 2
            if step <= half:
                ratio = 1 - (step / float(half))
                use_back = True
            else:
                ratio = (step - half) / float(half)
                use_back = False

            w = max(1, int(150 * ratio))
            
            # 生成缩放后的图像
            img = self._create_scaled_image(card, w, 170, use_back=use_back)
            if not hasattr(self, '_temp_flip_images'):
                self._temp_flip_images = {}
            self._temp_flip_images[card_id] = img
            
            self.table_canvas.itemconfig(card_id, image=img)
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
            {'key': 'player_only', 'text': 'Player Pair', 'dots': ['blue']},
            {'key': 'banker_only', 'text': 'Banker Pair', 'dots': ['red']}
        ]
        
        second_row_items = [
            {'key': 'both_diff', 'text': 'Double Pairs', 'dots': ['blue', 'red']},
            {'key': 'both_same', 'text': 'Twins Pairs', 'dots': ['black_top_left', 'black_bottom_right']}  # 修改为只有两个黑点
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
    
        # 更新对子统计显示
        if hasattr(self, 'player_only_label'):
            self.player_only_label.config(text="0")
            self.banker_only_label.config(text="0") 
            self.both_diff_label.config(text="0")
            self.both_same_label.config(text="0")

        # 重置所有统计键（Tiger + EZ 两套都要清零）
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
            'B Fabulous 4': 0
        }

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
            
            # 总计标签
            self.basic_total_label.config(text="0")
            if hasattr(self, 'tiger_total_label' ) and self.tiger_total_label.winfo_exists():
                self.tiger_total_label.config(text="0")
            elif hasattr(self, 'ez_total_label') and self.ez_total_label.winfo_exists():
                self.ez_total_label.config(text="0")
            elif hasattr(self, 'fab4_total_label') and self.fab4_total_label.winfo_exists():
                self.fab4_total_label.config(text="0")
        
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
        self.table_canvas.create_text(300, 30, text="PLAYER", font=('Arial', 30, 'bold'), fill='white')
        self.table_canvas.create_text(700, 30, text="BANKER", font=('Arial', 30, 'bold'), fill='white')

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
                        fill=text_color, font=('Arial', 15, 'bold'))

        # 绑定点击事件
        canvas.bind('<Button-1>', lambda e, t=text, c=canvas, cid=chip_id: self._set_bet_amount(t, c, cid))

        # 存储按钮信息
        self.chip_buttons.append({
            'canvas': canvas,
            'chip_id': chip_id,
            'text': text
        })
        return canvas

    def _set_bet_amount(self, chip_text, clicked_canvas, clicked_chip_id):
        # 取消所有对 canvas outline 的修改（不再使用发光/外圈）
        # 仅记录当前选中状态以供后续使用
        for chip in self.chip_buttons:
            if chip['canvas'] == clicked_canvas:
                self.selected_chip = chip
                # 保留这两个属性以兼容其它代码
                self.selected_canvas = chip['canvas']
                self.selected_id = chip['chip_id']
                break

        # 金额转换逻辑（不变）
        if 'K' in chip_text:
            amount = int(chip_text.replace('K', '')) * 1000
        else:
            amount = int(chip_text)

        self.selected_bet_amount = amount
        # 更新显示标签
        if hasattr(self, 'current_chip_label'):
            self.current_chip_label.config(text=f"Select: ${amount:,}")

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
        style.configure('Bold.TCombobox', font=('Arial', 15, 'bold'))
        
        # ===== 游戏模式切换 =====
        mode_frame = tk.Frame(control_frame, bg='#D0E7FF')
        mode_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(
            mode_frame, 
            text="Game Mode:", 
            font=('Arial', 14, 'bold'),
            bg='#D0E7FF'
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        self.mode_var = tk.StringVar(value=self.game_mode)
        
        # 定义显示文本和内部值的映射
        self.mode_display_map = {
            "tiger": "Tiger",
            "2to1": "2 To 1",
            "ez": "EZ",
            "classic": "Classic",
            "fabulous4": "Fabulous 4"
        }
        
        # 使用显示文本作为组合框的值
        display_values = [self.mode_display_map["classic"], 
                        self.mode_display_map["2to1"], 
                        self.mode_display_map["tiger"], 
                        self.mode_display_map["ez"],
                        self.mode_display_map["fabulous4"]
                        ]
        
        # 创建组合框 - 使用显示文本作为选项
        self.mode_combo = ttk.Combobox(
            mode_frame,
            textvariable=self.mode_var,
            values=display_values,
            state='readonly',
            font=('Arial', 14, 'bold'),
            width=15
        )
        self.mode_combo.pack(side=tk.LEFT)
        
        # 设置当前显示文本
        self.mode_combo.set(self.mode_display_map.get(self.game_mode, self.game_mode))
        
        # 绑定选择事件
        self.mode_combo.bind("<<ComboboxSelected>>", self.change_game_mode)

        # ===== 修改部分：视图切换按钮 - 只保留Road和Static =====
        view_frame = tk.Frame(control_frame, bg='#D0E7FF')
        view_frame.pack(fill=tk.X, pady=(5, 5))
        
        self.marker_view_btn = tk.Button(
            view_frame, 
            text="Road", 
            command=self.show_marker_view,
            bg='#4B8BBE',  # 蓝色背景
            fg='white',
            font=('Arial', 14, 'bold'),
            relief=tk.RAISED,
            width=10
        )
        self.marker_view_btn.pack(side=tk.LEFT, padx=5)

        self.bigroad_view_btn = tk.Button(
            view_frame, text="Static", command=self.show_bigroad_view,
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

        # 默认显示珠路图视图
        self.show_marker_view()

    def change_game_mode(self, event=None):
        """切换游戏模式后，立即重绘并刷新静态统计面板"""
        selected_display = self.mode_combo.get()
        # 将显示文本映射到真实模式值
        real_mode = {
            self.mode_display_map["classic"]: "classic",
            self.mode_display_map["2to1"]: "2to1",
            self.mode_display_map["tiger"]: "tiger",
            self.mode_display_map["ez"]: "ez",
            self.mode_display_map["fabulous4"]: "fabulous4"
        }.get(selected_display, "classic")

        if real_mode != self.game_mode:
            # 只重置下注，不重置珠路图统计
            self.reset_bets()
            self.game_mode = real_mode
            # 重新加载下注按钮布局（注意加上括号）
            self._reload_betting_buttons()

        # —— 立刻销毁旧的静态统计面板并重建 —— #
        for widget in self.bigroad_view.winfo_children():
            widget.destroy()
        self._create_stats_panel(self.bigroad_view)

        # —— 切换模式后，立刻根据现有的 marker_counts 把所有标签刷新一次 —— #
        # 基本三项
        self.player_count_label.config(text=str(self.marker_counts.get('Player', 0)))
        self.banker_count_label.config(text=str(self.marker_counts.get('Banker', 0)))
        self.tie_count_label.config(text=str(self.marker_counts.get('Tie', 0)))

        # 根据当前模式，刷新右侧对应的三行和总计
        if self.game_mode == "tiger":
            # Tiger 模式下显示 Small Tiger / Tiger Tie / Big Tiger
            # 确保对应标签都已经在 _create_stats_panel 中创建
            self.stiger_count_label.config(text=str(self.marker_counts.get('Small Tiger', 0)))
            self.ttiger_count_label.config(text=str(self.marker_counts.get('Tiger Tie', 0)))
            self.btiger_count_label.config(text=str(self.marker_counts.get('Big Tiger', 0)))

            # 更新总计
            basic_total = (
                self.marker_counts.get('Player', 0)
                + self.marker_counts.get('Tie', 0)
                + self.marker_counts.get('Banker', 0)
            )
            tiger_total = (
                self.marker_counts.get('Small Tiger', 0)
                + self.marker_counts.get('Tiger Tie', 0)
                + self.marker_counts.get('Big Tiger', 0)
            )
            self.basic_total_label.config(text=str(basic_total))
            self.tiger_total_label.config(text=str(tiger_total))

        elif self.game_mode == "ez":  # EZ 模式
            # EZ 模式下显示 Panda 8 / Divine 9 / Dragon 7
            self.panda_count_label.config(text=str(self.marker_counts.get('Panda 8', 0)))
            self.divine_count_label.config(text=str(self.marker_counts.get('Divine 9', 0)))
            self.dragon_count_label.config(text=str(self.marker_counts.get('Dragon 7', 0)))

            # 更新总计
            basic_total = (
                self.marker_counts.get('Player', 0)
                + self.marker_counts.get('Tie', 0)
                + self.marker_counts.get('Banker', 0)
            )
            ez_total = (
                self.marker_counts.get('Panda 8', 0)
                + self.marker_counts.get('Divine 9', 0)
                + self.marker_counts.get('Dragon 7', 0)
            )
            self.basic_total_label.config(text=str(basic_total))
            self.ez_total_label.config(text=str(ez_total))  

        elif self.game_mode == "fabulous4":
            if hasattr(self, 'fab4p_count_label'):
                self.fab4p_count_label.config(text=str(self.marker_counts.get('P Fabulous 4', 0)))
                self.fab4b_count_label.config(text=str(self.marker_counts.get('B Fabulous 4', 0)))
            fab4_total = (
                self.marker_counts.get('P Fabulous 4', 0) +
                self.marker_counts.get('B Fabulous 4', 0)
            )
            self.fab4_total_label.config(text=str(fab4_total))

        self._update_marker_road()


    def _reload_betting_buttons(self):
        """根据当前模式重新加载下注按钮"""
        # 清除所有按钮和状态
        self.selected_chip = None
        self.chip_buttons = []
        self.bet_buttons = []
        
        # 销毁 betting_view 中的所有组件
        for widget in self.betting_left.winfo_children():
            widget.destroy()
        
        # 重新创建下注视图
        self._populate_betting_left(self.betting_left)

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
        # （原本在 _create_bigroad_view 中的代码，现在搬到这里；parent 改为 marker_frame）
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
        marker_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ──【Big Road 标题】（可选，如果想给 Big Road 单独一个标题，可以加上）
        big_title = tk.Label(
            marker_frame,
            text="Big Road",
            font=('Arial', 14, 'bold'),
            bg='#D0E7FF'
        )
        big_title.pack(pady=(0, 5))  # 与上方留一些空隙

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
            text="Marker Road", 
            font=('Arial', 14, 'bold'),
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
            table_frame, text="BASIC",
            font=('Arial', 14, 'bold'),
            bg='#D0E7FF', width=12
        )

        if self.game_mode == "classic" or self.game_mode == "2to1":
            # 如果是 classic 模式，让 BASIC 占满所有列并水平居中
            basic_label.grid(row=0, column=0, columnspan=3, sticky='ew')
            ttk.Separator(table_frame, orient=tk.HORIZONTAL).grid(
                row=5, column=0, columnspan=1, sticky='ew', pady=2
            )
            tk.Label(
                table_frame, text="Total:",
                font=('Arial', 13, 'bold'), bg='#D0E7FF', anchor='w'
            ).grid(row=6, column=0, sticky='w', pady=(2, 5))
            
            self.basic_total_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.basic_total_label.grid(row=6, column=0, sticky='e', pady=(2, 5))
        else:
            # 非 classic 时，保持原来的左对齐和内边距
            basic_label.grid(row=0, column=0, sticky='w', padx=(0, 10))

        # 右侧列要根据当前模式决定标题：Tiger 模式下显示 "TIGER"，EZ 模式下显示 "EZ"
        if self.game_mode == "tiger":
            right_header = "TIGER"
        elif self.game_mode == "ez":
            right_header = "EZ"
        elif self.game_mode == "fabulous4":
            right_header = "Fabulous 4"
        else:
            right_header = None

        if right_header:
            tk.Label(
                table_frame, text=right_header,
                font=('Arial', 14, 'bold'),
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
            table_frame, text="Player:",
            font=('Arial', 12), bg='#D0E7FF', anchor='w'
        ).grid(row=2, column=0, sticky='w', pady=2)
        self.player_count_label = tk.Label(
            table_frame, text="0",
            font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
        )
        self.player_count_label.grid(row=2, column=0, sticky='e')

        # Tie
        tk.Label(
            table_frame, text="Tie:",
            font=('Arial', 12), bg='#D0E7FF', anchor='w'
        ).grid(row=3, column=0, sticky='w', pady=2)
        self.tie_count_label = tk.Label(
            table_frame, text="0",
            font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
        )
        self.tie_count_label.grid(row=3, column=0, sticky='e')

        # Banker
        tk.Label(
            table_frame, text="Banker:",
            font=('Arial', 12), bg='#D0E7FF', anchor='w'
        ).grid(row=4, column=0, sticky='w', pady=2)
        self.banker_count_label = tk.Label(
            table_frame, text="0",
            font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
        )
        self.banker_count_label.grid(row=4, column=0, sticky='e')

        # ── 右侧 列，根据模式分开布局 ── #
        if self.game_mode == "tiger":
            # Tiger 模式：显示 Small Tiger、Tiger Tie、Big Tiger 三行
            tk.Label(
                table_frame, text="Small Tiger:",
                font=('Arial', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=2, column=2, sticky='w', pady=2)
            self.stiger_count_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.stiger_count_label.grid(row=2, column=2, sticky='e')

            tk.Label(
                table_frame, text="Tiger Tie:",
                font=('Arial', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=3, column=2, sticky='w', pady=2)
            self.ttiger_count_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.ttiger_count_label.grid(row=3, column=2, sticky='e')
            tk.Label(
                table_frame, text="Big Tiger:",
                font=('Arial', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=4, column=2, sticky='w', pady=2)
            self.btiger_count_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.btiger_count_label.grid(row=4, column=2, sticky='e')
        elif self.game_mode == "ez":  # EZ 模式：显示 Panda 8、Divine 9、Dragon 7 三行
            tk.Label(
                table_frame, text="Panda 8:",
                font=('Arial', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=2, column=2, sticky='w', pady=2)
            self.panda_count_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.panda_count_label.grid(row=2, column=2, sticky='e')

            tk.Label(
                table_frame, text="Divine 9:",
                font=('Arial', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=3, column=2, sticky='w', pady=2)
            self.divine_count_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.divine_count_label.grid(row=3, column=2, sticky='e')

            tk.Label(
                table_frame, text="Dragon 7:",
                font=('Arial', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=4, column=2, sticky='w', pady=2)
            self.dragon_count_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.dragon_count_label.grid(row=4, column=2, sticky='e')

        elif self.game_mode == "fabulous4":  # 添加这个分支
            # P Fabulous 4
            tk.Label(
                table_frame, text="P Fabulous 4:",
                font=('Arial', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=2, column=2, sticky='w', pady=2)
            self.fab4p_count_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.fab4p_count_label.grid(row=2, column=2, sticky='e')
            
            # B Fabulous 4
            tk.Label(
                table_frame, text="B Fabulous 4:",
                font=('Arial', 12), bg='#D0E7FF', anchor='w'
            ).grid(row=3, column=2, sticky='w', pady=2)
            self.fab4b_count_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 12), bg='#D0E7FF', width=5, anchor='e'
            )
            self.fab4b_count_label.grid(row=3, column=2, sticky='e')
            
            # 不需要第三行，留空
            ttk.Separator(table_frame, orient=tk.HORIZONTAL).grid(
                row=5, column=0, columnspan=3, sticky='ew', pady=2  # 跨越3列
            )
        
        # ===== 总计行 =====
        # BASIC 总计
        ttk.Separator(table_frame, orient=tk.HORIZONTAL).grid(
            row=5, column=0, columnspan=3, sticky='ew', pady=2
        )

        # BASIC 总计（所有模式都需要）
        tk.Label(
            table_frame, text="Total:",
            font=('Arial', 13, 'bold'), bg='#D0E7FF', anchor='w'
        ).grid(row=6, column=0, sticky='w', pady=(2, 5))
        self.basic_total_label = tk.Label(
            table_frame, text="0",
            font=('Arial', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
        )
        self.basic_total_label.grid(row=6, column=0, sticky='e', pady=(2, 5))

        # 右侧列总计：根据模式决定是 tiger_total_label 还是 ez_total_label
        if self.game_mode == "tiger" or self.game_mode == "ez" or self.game_mode == "fabulous4":
            tk.Label(
                table_frame, text="Total:",
                font=('Arial', 13, 'bold'), bg='#D0E7FF', anchor='w'
            ).grid(row=6, column=2, sticky='w', pady=(2, 5))

        if self.game_mode == "tiger":
            self.tiger_total_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.tiger_total_label.grid(row=6, column=2, sticky='e', pady=(2, 5))
        elif self.game_mode == "ez":
            self.ez_total_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.ez_total_label.grid(row=6, column=2, sticky='e', pady=(2, 5))
        elif self.game_mode == "fabulous4":  # 添加这个分支
            self.fab4_total_label = tk.Label(
                table_frame, text="0",
                font=('Arial', 13, 'bold'), bg='#D0E7FF', width=5, anchor='e'
            )
            self.fab4_total_label.grid(row=6, column=2, sticky='e', pady=(2, 5))
            
            # 现在安全更新值
            fab4_total = (
                self.marker_counts.get('P Fabulous 4', 0) +
                self.marker_counts.get('B Fabulous 4', 0)
            )
            self.fab4_total_label.config(text=str(fab4_total))
        
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
            pie_frame, text="History Distribution", 
            font=('Arial', 16, 'bold'), 
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
            text="PLAYER: 0.0%",
            font=('Arial', 12),
            bg='#D0E7FF',
            fg='#4444ff',  # 蓝色
            anchor='w'
        )
        self.player_percent_label.pack(fill=tk.X, pady=2)

        self.tie_percent_label = tk.Label(
            percent_frame,
            text="TIE: 0.0%",
            font=('Arial', 12),
            bg='#D0E7FF',
            fg="#009700",  # 绿色
            anchor='w'
        )
        self.tie_percent_label.pack(fill=tk.X, pady=2)

        self.banker_percent_label = tk.Label(
            percent_frame,
            text="BANKER: 0.0%",
            font=('Arial', 12),
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
            streak_frame, text="Longest Winning Streak", 
            font=('Arial', 14, 'bold'), 
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
            player_frame, text="PLAYER:", 
            font=('Arial', 12), 
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
            tie_frame, text="TIE:", 
            font=('Arial', 12), 
            bg='#D0E7FF', fg='#009700'
        ).pack(side=tk.LEFT)
        self.longest_tie_label = tk.Label(
            tie_frame, text=str(self.longest_streaks['Tie']),
            font=('Arial', 12, 'bold'), 
            bg='#D0E7FF'
        )
        self.longest_tie_label.pack(side=tk.LEFT)
        
        # BANKER 记录
        banker_frame = tk.Frame(record_frame, bg='#D0E7FF')
        banker_frame.grid(row=0, column=2, padx=10)
        tk.Label(
            banker_frame, text="BANKER:", 
            font=('Arial', 12), 
            bg='#D0E7FF', fg='#ff4444'
        ).pack(side=tk.LEFT)
        self.longest_banker_label = tk.Label(
            banker_frame, text=str(self.longest_streaks['Banker']),
            font=('Arial', 12, 'bold'), 
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
        self.player_percent_label.config(text=f"PLAYER: {probabilities['Player']:.2f}%")
        self.tie_percent_label.config(text=f"TIE: {probabilities['Tie']:.2f}%")
        self.banker_percent_label.config(text=f"BANKER: {probabilities['Banker']:.2f}%")
        
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
                        is_player_pair=False, is_banker_pair=False, is_same_rank_pair=False):
        """添加新的珠路图结果"""
        # 如果珠路图已满-，移除最旧的一行数据-）
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
        
        # 存储结果到 marker_results（新增对子信息）
        self.marker_results.append((
            winner, is_natural, is_stiger, is_btiger,
            player_hand_len, banker_hand_len,
            player_score, banker_score,
            is_player_pair, is_banker_pair, is_same_rank_pair  # 新增对子参数
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
            is_player_pair, is_banker_pair, is_same_rank_pair) = result  # 新增对子参数
            
            outline_color = ''
            if self.game_mode == "classic" or self.game_mode == "2to1" or self.game_mode == "fabulous4":
                if winner == 'Player':
                    color = "#0091FF" if is_natural else '#0000FF'  # 浅蓝(例牌)或深蓝
                    text = "P"
                    text_color = 'white'
                    outline_color = '#0000FF'
                elif winner == 'Banker':
                    text = "B"
                    text_color = 'white'
                    color = "#E06800" if is_natural else '#FF0000'
                    outline_color = '#FF0000'
                else:  # Tie
                    color = '#00FF00'
                    text = "T"
                    text_color = 'black'
            elif self.game_mode == "tiger":
                if winner == 'Player':
                    color = "#0091FF" if is_natural else '#0000FF'  # 浅蓝(例牌)或深蓝
                    text = "P"
                    text_color = 'white'
                    outline_color = '#0000FF'
                elif winner == 'Banker':
                    if banker_score == 6:
                        if banker_hand_len == 2:
                            color = '#FF0000'
                            text_color = 'white'
                            text = "ST"
                        elif banker_hand_len == 3:
                            text = "BT"
                            color = '#FF0000'
                            text_color = 'white'
                    else:
                        text = "B"
                        text_color = 'white'
                        color = "#E06800" if is_natural else '#FF0000'
                        outline_color = '#FF0000'
                else:  # Tie
                    color = '#00FF00'
                    if is_stiger:
                        text = "TT"
                    else:
                        text = "T"
                    text_color = 'black'

            elif self.game_mode == "ez":
                if winner == 'Player':
                    if player_hand_len == 3 and player_score == 8:
                        color = "#FFFFFF"  # 浅蓝(例牌)或深蓝
                        text = "8"
                        text_color = 'black'
                    else:
                        color = "#0091FF" if is_natural else '#0000FF'  # 浅蓝(例牌)或深蓝
                        text = "P"
                        text_color = 'white'
                    outline_color = '#0000FF'
                elif winner == 'Banker':
                    if banker_hand_len == 3 and banker_score == 7:
                        text = "7"
                        color = '#FFFF00'
                        text_color = 'black'
                        outline_color = '#FF0000'
                    else:
                        text = "B"
                        text_color = 'white'
                        color = "#E06800" if is_natural else '#FF0000'
                        outline_color = '#FF0000'
                else:  # Tie
                    color = '#00FF00'
                    text = "T"
                    text_color = 'black'
                
            # 绘制主圆点
            self.marker_canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill=color,
                outline=outline_color,
                width=0.1,  
                tags='dot'
            )

            # 绘制对子标记点
            pair_radius = cell_size * 0.13  # 对子点半径
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
                # 玩家对子 - 左上角蓝色点（带白色边框）
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

            if text == "TT" or text == "ST" or text == "BT" :
                font_size = 10  # 稍微增大字体
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
        """填充左部分：下注格子 - 固定高度长度"""
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
                'Monkey 6':    ('12:1', '#ff5f5f'),
                'Monkey Tie':  ('150:1', '#88ccff'),
                'Big Monkey':  ('5000:1', '#e4ff4b'),
                'Panda 8':     ('25:1', '#ffffff'),
                'Divine 9':    ('10:1/75:1', '#86ff94'),
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
                'Banker':      ('0.95:1', '#ff4444')
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
                'P Fab Pair': ('1-7:1', '#ff8ef6'),
                'B Fab Pair': ('1-7:1', '#44ff44'),
                'P Fabulous 4': ('50:1', '#44ffff'),
                'B Fabulous 4': ('25:1', '#ffaa44'),
                'Player': ('1:1*', '#4444ff'),
                'Tie': ('8:1', '#44ff44'),
                'Banker': ('1:1*', '#ff4444')
            }

        # 创建三行下注按钮 - 固定高度和宽度
        row1_frame = tk.Frame(parent, bg='#D0E7FF', height=80)  # 固定高度
        row1_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row1_frame.pack_propagate(False)  # 防止框架收缩

        # 根据模式选择要显示的按钮
        if self.game_mode == "tiger":
            buttons_to_show_1 = ['Small Tiger','Tiger Tie','Big Tiger']
        elif self.game_mode == "ez":
            buttons_to_show_1 = ['Monkey 6','Monkey Tie','Big Monkey']
        elif self.game_mode == "classic" or self.game_mode == "2to1":
            buttons_to_show_1 = ['Dragon P', 'Quik', 'Dragon B']
        elif self.game_mode == "fabulous4":
            buttons_to_show_1 = ['P Fab Pair', 'B Fab Pair']

        for bt in buttons_to_show_1:
            odds, color = odds_map[bt]
            btn = tk.Button(
                row1_frame,
                text=f"{odds}\n{bt}\n~~",
                bg=color,
                font=('Arial', 12, 'bold'),  # 减小字体
                height=3,  # 固定高度
                width=12,   # 固定宽度
                wraplength=90
            )
            # 绑定左键点击事件（下注）
            btn.bind('<Button-1>', lambda e, t=bt: self.place_bet(t))
            # 绑定右键点击事件（清除下注）
            btn.bind('<Button-3>', lambda e, t=bt: self.clear_single_bet(t))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)  # 使用fill=tk.BOTH
            self.bet_buttons.append(btn)

        row2_frame = tk.Frame(parent, bg='#D0E7FF', height=80)  # 固定高度
        row2_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row2_frame.pack_propagate(False)

        if self.game_mode == "tiger":
            buttons_to_show_2 = ['Tiger','Tiger Pair']
        elif self.game_mode == "ez":
            buttons_to_show_2 = ['Panda 8','Divine 9','Dragon 7']
        elif self.game_mode == "classic" or self.game_mode == "2to1":
            buttons_to_show_2 = ['Pair Player', 'Any Pair', 'Pair Banker']
        elif self.game_mode == "fabulous4":
            buttons_to_show_2 = ['P Fabulous 4', 'B Fabulous 4']

        for bt in buttons_to_show_2:
            odds, color = odds_map[bt]
            btn = tk.Button(
                row2_frame,
                text=f"{odds}\n{bt}\n~~",
                bg=color,
                font=('Arial', 12, 'bold'),
                height=3,  # 固定高度
                width=12,   # 固定宽度
                wraplength=100
            )
            # 绑定左键点击事件（下注）
            btn.bind('<Button-1>', lambda e, t=bt: self.place_bet(t))
            # 绑定右键点击事件（清除下注）
            btn.bind('<Button-3>', lambda e, t=bt: self.clear_single_bet(t))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        row3_frame = tk.Frame(parent, bg='#D0E7FF', height=80)  # 固定高度
        row3_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row3_frame.pack_propagate(False)
        
        for bt in ['Player','Tie','Banker']:
            odds, color = odds_map[bt]
            text_color = 'white' if bt in ['Player','Banker'] else 'black'
            disabled_color = 'white' if bt in ['Player','Banker'] else 'grey'
            btn = tk.Button(
                row3_frame,
                text=f"{odds}\n{bt}\n~~",
                bg=color,
                font=('Arial', 12, 'bold'),
                height=3,  # 固定高度
                width=12,   # 固定宽度
                fg=text_color,
                disabledforeground=disabled_color,
                highlightthickness=0,
                highlightbackground='black',
                wraplength=80
            )
            # 绑定左键点击事件（下注）
            btn.bind('<Button-1>', lambda e, t=bt: self.place_bet(t))
            # 绑定右键点击事件（清除下注）
            btn.bind('<Button-3>', lambda e, t=bt: self.clear_single_bet(t))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        # 说明 - 根据模式显示不同的说明
        if self.game_mode == "tiger":
            explanation = "*BANKER PAYS 50% WHEN BANKER WIN ON 6 "
        elif self.game_mode == "ez":
            explanation = "*BANKER PUSH WHEN BANKER WIN WITH 3-CARD 7"
        elif self.game_mode == "classic":
            explanation = "BANKER PAYS 5% COMMISSION EVERY WIN"
        elif self.game_mode == "2to1":
            explanation = "*WIN WITH 3-CARD 8/9 PAYS 200% | TIE LOSE"
        elif self.game_mode == "fabulous4":
            explanation = "*WIN ON 1 PAYS 200% | P(B) WIN ON 4 PAYS 50%(PUSH)"
            
        explanation_frame = tk.Frame(parent, bg='#D0E7FF', height=40)  # 固定高度
        explanation_frame.pack(fill=tk.BOTH, expand=True, pady=2)
        explanation_frame.pack_propagate(False)
        
        tk.Label(
            explanation_frame,
            text=explanation,
            font=('Arial', 12),  # 减小字体
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
        balance_display_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 余额标签
        self.balance_label = tk.Label(
            balance_display_frame,
            text=f"Balance: ${int(round(self.balance)):,}",
            font=('Arial', 19),
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
            font=('Arial', 12)
        )
        self.info_button.pack(side=tk.RIGHT, padx=5)

        # 分隔线 + 当前/上次下注显示
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5)

        # DEAL/RESET 按钮行
        btn_frame = tk.Frame(parent, bg='#D0E7FF')
        btn_frame.pack(fill=tk.X, pady=10)
        self.reset_button = tk.Button(
            btn_frame, text="RESET", command=self.reset_bets,
            bg='#ff4444', fg='white',
            font=('Arial', 18, 'bold')
        )
        self.reset_button.pack(side=tk.TOP, expand=True, fill=tk.X, padx=10, pady=5)
        self.deal_button = tk.Button(
            btn_frame, text="DEAL (Enter)", command=self.start_game,
            bg='gold', fg='black',
            font=('Arial', 18, 'bold')
        )
        self.deal_button.pack(side=tk.TOP, expand=True, fill=tk.X, padx=10, pady=5)

        # 分隔线 + 当前/上次下注显示
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(5, 0), padx=5)

        current_bet_frame = tk.Frame(parent, bg='#D0E7FF')
        current_bet_frame.pack(pady=(0, 5))
        tk.Label(
            current_bet_frame, text="Current Bet:", width=12,
            font=('Arial', 18), bg='#D0E7FF'
        ).pack(side=tk.LEFT)
        self.current_bet_label = tk.Label(
            current_bet_frame, text="$0", width=10,
            font=('Arial', 18), bg='#D0E7FF'
        )
        self.current_bet_label.pack(side=tk.RIGHT)

        last_win_frame = tk.Frame(parent, bg='#D0E7FF')
        last_win_frame.pack(pady=5)
        tk.Label(
            last_win_frame, text="Last Win:", width=12,
            font=('Arial', 18), bg='#D0E7FF'
        ).pack(side=tk.LEFT)
        self.last_win_label = tk.Label(
            last_win_frame, text="$0", width=10,
            font=('Arial', 18), bg='#D0E7FF'
        )
        self.last_win_label.pack(side=tk.RIGHT)

    def _populate_betting_right(self, parent):
        """填充右部分：筹码区域（取消任何 outline / 发光 设置）"""
        # 筹码区
        chips_frame = tk.Frame(parent, bg='#D0E7FF')
        chips_frame.pack(pady=5)
        row1 = tk.Frame(chips_frame, bg='#D0E7FF')
        row1.pack()
        for text, bg_color in [
            ('100', '#000000'),
            ('500', "#FF7DDA"),
            ('1K', '#ffffff')
        ]:
            btn = self._create_chip_button(row1, text, bg_color)
            btn.pack(side=tk.LEFT, padx=2)
        row2 = tk.Frame(chips_frame, bg='#D0E7FF')
        row2.pack(pady=3)
        for text, bg_color in [
            ('2K', '#0000ff'),
            ('5K', '#ff0000'),
            ('10K', '#800080')
        ]:
            btn = self._create_chip_button(row2, text, bg_color)
            btn.pack(side=tk.LEFT, padx=2)
        row3 = tk.Frame(chips_frame, bg='#D0E7FF')
        row3.pack(pady=3)
        for text, bg_color in [
            ('20K', '#ffa500'),
            ('50K', '#006400'),
            ('100K', '#00ff00'),
        ]:
            btn = self._create_chip_button(row3, text, bg_color)
            btn.pack(side=tk.LEFT, padx=2)

        # pre-select default chip（不设置 outline，只设置选中状态变量）
        for chip in self.chip_buttons:
            if chip['text'] == '1K':
                self.selected_canvas = chip['canvas']
                self.selected_id = chip['chip_id']
                self.selected_chip = chip
                # 确保设置了金额
                self.selected_bet_amount = 1000
                break

        # 当前选中筹码显示
        self.current_chip_label = tk.Label(
            parent,
            text="Select: $1,000",
            font=('Arial', 18),
            fg='black',
            bg='#D0E7FF'
        )
        self.current_chip_label.pack(side=tk.LEFT, padx=0)

    def _set_default_chip(self):
        """设置默认选中的筹码（1K），但不显示任何发光/外圈效果"""
        # 不再清除/设置 canvas outline；仅设置选中引用
        for chip in self.chip_buttons:
            if chip['text'] == '1K':
                self.selected_canvas = chip['canvas']
                self.selected_id = chip['chip_id']
                self.selected_chip = chip
                self.selected_bet_amount = 1000
                if hasattr(self, 'current_chip_label'):
                    self.current_chip_label.config(text="Select: $1,000")
                break

    def _setup_bindings(self):
        self.bind('<Return>', lambda e: self.start_game())

    def place_bet(self, bet_type):
        amount = self.selected_bet_amount
        if amount > self.balance:
            messagebox.showerror("Error", "Insufficient balance")
            return
        
        self.balance -= amount
        self.current_bet += amount  # 累加当前回合下注总额
        self.current_bets[bet_type] = self.current_bets.get(bet_type, 0) + amount

        for btn in self.bet_buttons:
            if hasattr(btn, 'bet_type') and btn.bet_type == bet_type:
                current_amount = self.current_bets.get(bet_type, 0)
                original_text = btn.cget("text").split('\n')
                new_text = f"{original_text[0]}\n{original_text[1]}\n${current_amount}"
                btn.config(text=new_text)

        self.update_balance()
        self.current_bet_label.config(text=f"${self.current_bet:,}")

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
        self.after(500, self._process_extra_cards)

    def _process_extra_cards(self):
        if len(self.game.player_hand) > 2:
            self._deal_extra_card("player", 2)
            self.after(1500, self._process_banker_extra)
        else:
            self._process_banker_extra()

    def _process_banker_extra(self):
        if len(self.game.banker_hand) > 2:
            self._deal_extra_card("banker", 2)
            self.after(1500, self.resolve_bets)
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
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker0')

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
            bg_path = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker0', 'Background.png')
            img = Image.open(bg_path)
        else:
            # 修改为使用绝对路径
            card_path = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker0', f"{card[0]}{card[1]}.png")
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
            elif self.game_mode == "ez":
                # EZ模式：庄家三张牌7点视为和局
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
                payouts += t_bet * 9 + p_bet + b_bet  # Tie赔付+退还本金

        side_results = self._check_side_bets()

        if self.game_mode == "tiger":
            tiger_bet = self.current_bets.get('Tiger Pair', 0)
            if tiger_bet and 'Tiger Pair' in side_results:
                odds = side_results['Tiger Pair']
                # "Win X:1" means profit = bet * X, total returned = (X + 1) * bet
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

        if self.game_mode == "ez":
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

        if self.game_mode == "classic" or self.game_mode == "2to1":
            #Player Pair
            ppair = self.current_bets.get('Pair Player', 0)
            if 'Pair Player' in side_results:
                payouts +=  ppair * 12

            #Banker Pair
            bpair = self.current_bets.get('Pair Banker', 0)
            if 'Pair Banker' in side_results:
                payouts +=  bpair * 12

            #Any Pair
            apair = self.current_bets.get('Any Pair', 0)
            if 'Any Pair' in side_results:
                payouts +=  apair * 6

            #Player Dragon
            pdragon = self.current_bets.get('Dragon P', 0)
            if 'Dragon P' in side_results:
                odds = side_results['Dragon P']
                payouts += pdragon * odds

            #Quik
            quik = self.current_bets.get('Quik', 0)
            if 'Quik' in side_results:
                odds = side_results['Quik']
                payouts += quik * odds

            #Banker Dragon
            bdragon = self.current_bets.get('Dragon B', 0)
            if 'Dragon B' in side_results:
                odds = side_results['Dragon B']
                payouts += bdragon * odds

        if self.game_mode == "fabulous4":
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

        self.balance += payouts
        self.current_bets.clear()
        self.update_balance()
        self.after(1000, self._animate_result_cards)
        self.update_balance()

        for btn in self.bet_buttons:
            if hasattr(btn, 'bet_type'):
                original_text = btn.cget("text").split('\n')
                new_text = f"{original_text[0]}\n{original_text[1]}\n~~"
                btn.config(text=new_text)

        # 修复1：立即重置当前总下注
        self.current_bet = 0  # 新增这行
        self.current_bet_label.config(text="$0")

        # 修复2：正确更新last_win
        self.last_win = int(payouts)  # 计算净盈利
        self.last_win_label.config(text=f"${max(self.last_win, 0):,}")  # 新增这行

        if self.game.winner == 'Tie':
            self.last_win = payouts  # 显示总赔付金额（包含本金）
        else:
            self.last_win = max(payouts, 0) 

        # 判断显示条件（保持原逻辑）
        winner = self.game.winner
        p_score = self.game.player_score
        b_score = self.game.banker_score
        b_hand_len = len(self.game.banker_hand)

        def enable_buttons():
            for btn in self.bet_buttons:
                btn.config(state=tk.NORMAL)
            self.reset_button.config(state=tk.NORMAL)
            self.mode_combo.config(state='readonly')
            self.after(2000, lambda: self.deal_button.config(state=tk.NORMAL))
            self.after(2000, lambda: self.bind('<Return>', lambda e: self.start_game()))
                
        time.sleep(1)
        
        text = ""
        text_color = "black"
        bg_color = "#35654d"
        
        # 条件判断逻辑
        if winner == 'Player':
            if self.game_mode == "fabulous4":
                if p_score == 1:
                    text = "PLAYER WIN ON 1 (PAY 2:1)"
                elif p_score == 4:
                    text = "PLAYER WIN ON 4 (PAY 0.5:1)"
                else:
                    text = "PLAYER WIN"
            else:
                text = "PLAYER WIN"
            bg_color = '#4444ff'
            text_color = 'white'
        elif winner == 'Banker':
            if b_score == 6 and self.game_mode == "tiger":
                text = "SMALL TIGER" if b_hand_len == 2 else "BIG TIGER"
            elif b_score == 7 and b_hand_len == 3 and self.game_mode == "ez":
                text = "BANKER WIN AND PUSH ON 7"
            elif self.game_mode == "fabulous4":
                if b_score == 1:
                    text = "BANKER WIN ON 1 (PAY 2:1)"
                elif b_score == 4:
                    text = "BANKER WIN AND PUSH ON 4"
                else:
                    text = "BANKER WIN"
            else:
                text = "BANKER WIN"
            bg_color = '#ff4444'
            text_color = 'black'
        elif winner == 'Tie':
            if b_score == 6 and self.game_mode == "tiger":
                text = "TIGER TIE"
            else:
                text = "TIE"
            bg_color = '#44ff44'
            text_color = 'black'

        # 更新文字
        self.table_canvas.itemconfig(
            self.result_text_id,
            text=text,
            fill=text_color
        )
        
        # 强制Canvas更新布局
        self.table_canvas.update_idletasks()

        # 获取文字边界并更新背景框
        text_bbox = self.table_canvas.bbox(self.result_text_id)
        if text_bbox:
            # 扩展边界增加内边距
            padding = 15
            expanded_bbox = (
                text_bbox[0]-padding, 
                text_bbox[1]-padding,
                text_bbox[2]+padding, 
                text_bbox[3]+padding
            )
            
            # 更新背景框
            self.table_canvas.coords(self.result_bg_id, expanded_bbox)
            self.table_canvas.itemconfig(
                self.result_bg_id,
                fill=bg_color,
                outline=bg_color
            )
            
            # 确保层级顺序
            self.table_canvas.tag_raise(self.result_text_id)  # 文字置顶
            self.table_canvas.tag_lower(self.result_bg_id)   # 背景置底

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
        player_hand_len = len(self.game.player_hand)
        banker_hand_len = len(self.game.banker_hand)
        player_score = self.game.player_score
        banker_score = self.game.banker_score
        p0, p1 = self.game.player_hand[:2]
        b0, b1 = self.game.banker_hand[:2]
        is_player_pair = (p0[1] == p1[1])
        is_banker_pair = (b0[1] == b1[1])
        is_same_rank_pair = (is_player_pair and is_banker_pair and p0[1] == b0[1])

        self.add_marker_result(
            self.game.winner, is_natural, is_stiger, is_btiger,
            player_hand_len, banker_hand_len,
            player_score, banker_score,
            is_player_pair, is_banker_pair, is_same_rank_pair
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
            self.save_game_result(result_char)
        
        # 获取文字边界并更新背景框
        text_bbox = self.table_canvas.bbox(self.result_text_id)
        if text_bbox:
            # 扩展边界增加内边距
            padding = 10
            expanded_bbox = (
                text_bbox[0]-padding, 
                text_bbox[1]-padding,
                text_bbox[2]+padding, 
                text_bbox[3]+padding
            )
            
            # 更新背景框
            self.table_canvas.coords(self.result_bg_id, expanded_bbox)
            self.table_canvas.itemconfig(
                self.result_bg_id,
                fill=bg_color,
                outline=bg_color
            )
            
            # 确保层级顺序
            self.table_canvas.tag_raise(self.result_text_id)  # 文字置顶
            self.table_canvas.tag_lower(self.result_bg_id)   # 背景置底

        # 添加到大路结果
        tie_count = 1 if self.game.winner == 'Tie' else 0
        self.bigroad_results.append({
            'winner': self.game.winner,
            'tie_count': tie_count
        })
        self._update_bigroad()
        self.update_pie_chart()
        
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
        self.update_streak_labels()
   
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
        else:
            self.after(1000, enable_buttons)

    def _update_bigroad(self):
        """
        更新"大路" (3 行测试版)：
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
                        width=2, fill='#00AA00', tags=('data', tie_tag)
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
                self.bigroad_canvas.create_line(
                    prev_cx, prev_cy, cx, cy,
                    width=2, fill=line_color, tags=('data',)
                )

            # B.4 绘制圆点：庄家用红 (#FF3C00)，闲家用蓝 (#0091FF)
            dot_color = "#FF3C00" if winner == 'Banker' else "#0091FF"
            self.bigroad_canvas.create_oval(
                cx - 8, cy - 8, cx + 8, cy + 8,
                fill=dot_color, outline='', tags=('data',)
            )

            # B.5 如果该 (row, col) 之前已有 Tie 次数，就在圆点上叠加斜线与数字
            if (row, col) in tie_tracker:
                tcnt = tie_tracker[(row, col)]
                self.bigroad_canvas.create_line(prev_cx, prev_cy, cx, cy, width=2, tags=('data', 'connect'))
                tie_tag = f"tie_{row}_{col}"
                self.bigroad_canvas.tag_raise(tie_tag)
                # 删除旧的 tie tag 元素（这样连续 Tie 不会保留旧数字）
                self.bigroad_canvas.delete(tie_tag)

                # 画斜线（也加上 tie_tag）
                self.bigroad_canvas.create_line(
                    cx - 10, cy + 10,
                    cx + 10, cy - 10,
                    width=2,
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

            # Monkey 6
            monkey_cards = ['J', 'Q', 'K']
            # 检查第一张牌是否不是J/Q/K，第二张牌是J/Q/K
            if self.game.winner != 'Tie':
                # 定义Monkey卡牌
                # 检查Player的第一张牌不是Monkey，Banker的第一张牌是Monkey
                if p[0][1] not in monkey_cards and b[0][1] in monkey_cards:
                    results['Monkey 6'] = 12  # 12:1

            # Monkey Tie
            if self.game.winner == 'Tie':
                # 检查Player的第一张牌不是Monkey，Banker的第一张牌是Monkey
                if p[0][1] not in monkey_cards and b[0][1] in monkey_cards:
                    results['Monkey Tie'] = 150  # 150:1

            # Big Monkey
            # 检查所有6张牌都是J/Q/K
            all_cards = p + b
            if len(all_cards) == 6 and all(card[1] in monkey_cards for card in all_cards):
                results['Big Monkey'] = 5000  # 5000:1

        elif self.game_mode == "classic" or self.game_mode == "2to1":
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
            if self.game.winner == 'Player' and len(all_cards) != 4:
                odds_map = {4:2, 5:3, 6:5, 7:7, 8:11, 9:31}
                results['Dragon P'] = odds_map.get(diff, 0)
            elif self.game.winner == 'Player' and len(all_cards) == 4 and self.game.player_score == 8 or self.game.player_score == 9:
                if self.game.banker_score != self.game.player_score:
                    results['Dragon P'] = 2
                else:
                    results['Dragon P'] = 1

            # Dragon Banker
            diff = self.game.banker_score - self.game.player_score
            if self.game.winner == 'Banker' and len(all_cards) != 4:
                odds_map = {4:2, 5:3, 6:5, 7:7, 8:11, 9:31}
                results['Dragon B'] = odds_map.get(diff, 0)
            elif self.game.winner == 'Banker' and len(all_cards) == 4 and self.game.banker_score == 8 or self.game.banker_score == 9:
                if self.game.banker_score != self.game.player_score:
                    results['Dragon B'] = 2
                else:
                    results['Dragon B'] = 1

            # Quik
            combined = self.game.player_score + self.game.banker_score
            if combined == 0:
                results['Quik'] = 50  # 50:1
            elif combined == 18:
                results['Quik'] = 25  # 25:1
            elif combined in [1,2,3,15,16,17]:
                results['Quik'] = 1   # 1:1

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

        return results

    def update_balance(self):
        self.balance_label.config(text=f"Balance: ${int(round(self.balance)):,}")
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