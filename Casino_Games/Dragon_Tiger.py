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

class DragonTiger:
    def __init__(self, decks=8, external_deck=None):
        if external_deck:
            self.deck = [(card['suit'], card['rank']) for card in external_deck]
        else:
            self.deck = self.create_deck(decks)
            random.shuffle(self.deck)
            
        self.dragon_hand = []
        self.tiger_hand = []
        self.dragon_score = 0
        self.tiger_score = 0
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
        # 龙虎斗中A最小，K最大
        value_map = {
            'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
            '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13
        }
        return value_map.get(rank, 0)

    def deal_initial(self):
        # 龙虎斗只发两张牌
        indices = [(self.cut_position + i) % self.total_cards for i in range(2)]
        self.dragon_hand = [self.deck[indices[0]]]
        self.tiger_hand = [self.deck[indices[1]]]
        self.cut_position = (self.cut_position + 2) % self.total_cards

    def calculate_score(self, hand):
        # 龙虎斗中只比较单张牌的大小
        if hand:
            return self.card_value(hand[0])
        return 0

    def play_game(self):
        self.deal_initial()
        self.dragon_score = self.calculate_score(self.dragon_hand)
        self.tiger_score = self.calculate_score(self.tiger_hand)

        # 判断胜负
        if self.dragon_score > self.tiger_score:
            self.winner = 'Dragon'
        elif self.tiger_score > self.dragon_score:
            self.winner = 'Tiger'
        else:
            # 判断是否同花和局（花色相同）
            if self.dragon_hand[0][0] == self.tiger_hand[0][0]:
                self.winner = 'SameSuitTie'
            else:
                self.winner = 'Tie'

class DragonTigerGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("龙虎斗")
        self.geometry("1350x700+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')

        self.bet_buttons = []
        self.selected_chip = None
        self.chip_buttons = []
        self.result_text_id = None
        self.result_bg_id = None

        self.game_mode = "dragontiger"
        self.game = DragonTiger()
        self.balance = initial_balance
        self.current_bets = {}
        self.card_images = {}

        # 新增連勝記錄追蹤屬性
        self.current_streak = 0
        self.current_streak_type = None
        self.longest_streaks = {
            'Dragon': 0,
            'Tie': 0,
            'Tiger': 0,
            'SameSuitTie': 0
        }

        # 新增统计属性
        self.stats_counts = {
            'Dragon': 0,
            'Tiger': 0,
            'Tie': 0,
            'SameSuitTie': 0
        }

        # 新增珠路图相关属性
        self.marker_results = []  # 存储每局结果
        self.marker_counts = {
            'Dragon': 0,
            'Tiger': 0,
            'Tie': 0,
            'SameSuitTie': 0
        }

        self.max_marker_rows = 6  # 最大行数
        self.max_marker_cols = 11  # 最大列数
        self.view_mode = "marker"  # 默认显示珠路图
        self.bigroad_results = []
        self._max_rows = 6
        self._max_cols = 150  # 修改为150列
        self._bigroad_occupancy = [[False]*self._max_cols for _ in range(self._max_rows)]
        
        self._load_assets()
        self._create_widgets()
        self._setup_bindings()
        self.point_labels = {}
        self._dragon_area = (310, 150, 400, 350)  # 调整扑克牌区域位置
        self._tiger_area = (720, 150, 800, 350)  # 调整扑克牌区域位置
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

    def disable_all_buttons(self):
        """禁用所有按钮（除info_button外）"""
        for btn in self.bet_buttons:
            btn.config(state=tk.DISABLED, bg=btn.disabled_bg)
        self.deal_button.config(state=tk.DISABLED)
        self.reset_button.config(state=tk.DISABLED)
        self.unbind('<Return>')

    def enable_all_buttons(self):
        """启用所有按钮"""
        for btn in self.bet_buttons:
            btn.config(state=tk.NORMAL, bg=btn.original_bg)
        self.deal_button.config(state=tk.NORMAL)
        self.reset_button.config(state=tk.NORMAL)
        # 重新绑定筹码按钮
        for chip in self.chip_buttons:
            chip['canvas'].bind('<Button-1>', 
                lambda e, t=chip['text'], c=chip['canvas'], cid=chip['chip_id']: self._set_bet_amount(t, c, cid))
        self.bind('<Return>', lambda e: self.start_game())

    def enable_buttons_except_deal(self):
        """启用除deal_button外的所有按钮"""
        for btn in self.bet_buttons:
            btn.config(state=tk.NORMAL, bg=btn.original_bg)
        self.reset_button.config(state=tk.NORMAL)
        # 重新绑定筹码按钮
        for chip in self.chip_buttons:
            chip['canvas'].bind('<Button-1>', 
                lambda e, t=chip['text'], c=chip['canvas'], cid=chip['chip_id']: self._set_bet_amount(t, c, cid))

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

        # 初始化游戏：把外部牌组传入 DragonTiger（如果 external_deck 为 None 则由 DragonTiger 内部自行生成）
        self.game = DragonTiger(external_deck=external_deck)
        self.game.advanced_shuffle(cut_position)

        # 重新洗牌时重置
        self.marker_results = []
        self.marker_counts = {
            'Dragon': 0, 'Tiger': 0, 'Tie': 0, 'SameSuitTie': 0
        }
        self.stats_counts = {
            'Dragon': 0, 'Tiger': 0, 'Tie': 0, 'SameSuitTie': 0
        }
        self.reset_marker_road()
        self.reset_bigroad()
        
        # 开局抽牌和弃牌流程
        self._initial_draw_and_discard()

    def _initial_draw_and_discard(self):
        """开局抽牌和弃牌流程"""
        # 禁用所有按钮
        self.disable_all_buttons()
        
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
        """完成开局流程，启用所有按钮"""
        # 清除牌桌
        self.table_canvas.delete('all')
        self._draw_table_labels()
        
        # 启用所有按钮
        self.enable_all_buttons()

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

    def _create_stats_display(self, parent):
        """创建统计显示 - 精致表格形式"""
        self.stats_frame = tk.Frame(parent, bg='#D0E7FF', height=180)
        self.stats_frame.pack(fill=tk.X, pady=(0, 0))
        self.stats_frame.pack_propagate(False)
        
        # 标题
        title_label = tk.Label(
            self.stats_frame, 
            text="统计结果",
            font=('Arial', 16, 'bold'),
            bg='#D0E7FF',
            fg='#000000'
        )
        title_label.pack(pady=(3, 0))
        
        # 创建表格框架
        table_frame = tk.Frame(self.stats_frame, bg='#D0E7FF')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 表头
        headers = ['赢家', '图标', '数量']
        for i, header in enumerate(headers):
            header_label = tk.Label(
                table_frame,
                text=header,
                font=('Arial', 14, 'bold'),
                bg='#4B8BBE',
                fg='white',
                width=16,
                height=1,  # 增加高度
                relief=tk.RAISED,
                bd=2
            )
            header_label.grid(row=0, column=i, padx=1, pady=1, sticky='nsew')

        # 定义统计项
        stats_items = [
            {'key': 'dragon', 'text': '龙', 'color': '#FF0000', 'icon_text': '龙', 'text_color': 'white'},
            {'key': 'tiger', 'text': '虎', 'color': '#FFA600', 'icon_text': '虎', 'text_color': 'black'},
            {'key': 'tie', 'text': '和局', 'color': '#00FFFF', 'icon_text': '和', 'text_color': 'black'},
            {'key': 'samesuit_tie', 'text': '同花和局', 'color': "#FFFFFF", 'icon_text': '花', 'text_color': 'black'}
        ]

        # 创建统计行
        self.stats_rows = {}
        for row_idx, item in enumerate(stats_items, 1):
            # 赢家名称
            name_label = tk.Label(
                table_frame,
                text=item['text'],
                font=('Arial', 14),
                bg='#FFFFFF',
                fg='#000000',
                width=14,
                height=2,  # 增加高度
                relief=tk.RIDGE,
                bd=1
            )
            name_label.grid(row=row_idx, column=0, padx=1, pady=1, sticky='nsew')
            
            # 图标
            icon_frame = tk.Frame(table_frame, bg='#FFFFFF', width=60, height=40)  # 高度从30增加到40
            icon_frame.grid(row=row_idx, column=1, padx=1, pady=1, sticky='nsew')
            icon_frame.grid_propagate(False)
            
            icon_canvas = tk.Canvas(
                icon_frame, 
                width=26, 
                height=26, 
                bg='#FFFFFF',
                highlightthickness=0
            )
            icon_canvas.place(relx=0.5, rely=0.5, anchor='center')
            
            # 绘制圆圈图标
            center_x, center_y = 13, 13
            radius = 10
            icon_canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill=item['color'],
                outline='#000000',
                width=2
            )
            
            # 在圆圈中间添加文字
            icon_canvas.create_text(
                center_x, center_y,
                text=item['icon_text'],
                fill=item['text_color'],
                font=('Arial', 10, 'bold')
            )
            
            # 数量
            count_label = tk.Label(
                table_frame,
                text="0",
                font=('Arial', 14, 'bold'),
                bg='#FFFFFF',
                fg='#000000',
                width=8,
                height=2,  # 增加高度
                relief=tk.RIDGE,
                bd=1
            )
            count_label.grid(row=row_idx, column=2, padx=1, pady=1, sticky='nsew')
            
            # 保存引用
            self.stats_rows[item['key']] = {
                'name_label': name_label,
                'icon_canvas': icon_canvas,
                'count_label': count_label
            }

        # 配置网格权重
        for i in range(3):
            table_frame.columnconfigure(i, weight=1)
        for i in range(5):
            table_frame.rowconfigure(i, weight=1, minsize=25)  # 设置最小行高为40

    def reset_marker_road(self):
        """重置珠路图数据"""
        # 清空所有结果
        self.marker_results = []
        
        # 重置统计
        self.stats_counts = {
            'Dragon': 0,
            'Tiger': 0, 
            'Tie': 0,
            'SameSuitTie': 0
        }
        
        # 重置所有统计键
        self.marker_counts = {
            'Dragon': 0,
            'Tiger': 0,
            'Tie': 0,
            'SameSuitTie': 0
        }
        
        # 更新统计显示
        self._update_stats_display()
        
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
        self.table_canvas.create_text(300, 30, text="龙", font=('Arial', 30, 'bold'), fill='white')
        self.table_canvas.create_text(700, 30, text="虎", font=('Arial', 30, 'bold'), fill='white')

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
        area = self._dragon_area if hand_type == "dragon" else self._tiger_area
        hand = self.game.dragon_hand if hand_type == "dragon" else self.game.tiger_hand
        card_count = len(hand)
        base_x = area[0] + (area[2]-area[0]-120)/2
        positions = []
        for i in range(card_count):
            x = base_x + i*120  # 减少卡片间距
            y = area[1]
            positions.append((int(round(x)), int(round(y))))
        return positions
    
    def _create_chip_button(self, parent, text, bg_color):
        size = 60
        canvas = tk.Canvas(parent, width=size, height=size,
                        highlightthickness=0, background='#D0E7FF')

        # 绘制圆形筹码
        chip_id = canvas.create_oval(2, 2, size-2, size-2,
                                    fill=bg_color, outline='', width=0)

        # 文字颜色计算
        rgb = ImageColor.getrgb(bg_color)
        luminance = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2]
        text_color = 'white' if luminance < 140 else 'black'

        # 添加文字
        canvas.create_text(size/2, size/2, text=text,
                        fill=text_color, font=('Arial', 16, 'bold'))

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
        # 取消所有对 canvas outline 的修改和发光效果
        for chip in self.chip_buttons:
            if chip['canvas'] != clicked_canvas:
                chip['canvas'].itemconfig(chip['chip_id'], outline='', width=0)
                # 移除发光效果
                chip['canvas'].delete('glow')
        
        # 设置选中筹码的金色边框和发光效果
        clicked_canvas.itemconfig(clicked_chip_id, outline='yellow', width=4)
        
        for chip in self.chip_buttons:
            if chip['canvas'] == clicked_canvas:
                self.selected_chip = chip
                # 保留这两个属性以兼容其它代码
                self.selected_canvas = chip['canvas']
                self.selected_id = chip['chip_id']
                break

        # 金额转换逻辑
        if '千' in chip_text:
            amount = int(chip_text.replace('千', '')) * 1000
        elif '万' in chip_text:
            amount = int(chip_text.replace('万', '')) * 10000
        else:
            amount = int(chip_text)

        self.selected_bet_amount = amount
        # 更新显示标签
        if hasattr(self, 'current_chip_label'):
            self.current_chip_label.config(text=f"筹码: ${amount:,}")

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

    def _create_control_panel(self, parent):
        # main panel with light-blue background - 固定宽度
        control_frame = tk.Frame(parent, bg='#D0E7FF', width=300)
        control_frame.pack(pady=12, padx=10, fill=tk.BOTH, expand=True)
        control_frame.pack_propagate(False)  # 禁止自动调整大小

        # 创建一个统一大小的 view_container - 固定高度
        self.view_container = tk.Frame(control_frame, bg='#D0E7FF', height=300)
        self.view_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.view_container.pack_propagate(False)  # 禁止自动调整大小

        # 只创建珠路图视图
        self.marker_view = tk.Frame(self.view_container, bg='#D0E7FF')
        self.marker_view.pack(fill=tk.BOTH, expand=True)

        # 创建珠路图
        self._create_marker_road()
        self.enable_bigroad_navigation()

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
        """创建包含 Big Road + Marker Road + 统计面板的复合视图（UI 与百家乐一致）"""
        # 初始化 bigroad 数据（防护）
        try:
            self.bigroad_results.clear()
        except Exception:
            pass
        self.bigroad_results = []
        self._max_rows = 6
        self._max_cols = 150  # 修改为150列
        self._bigroad_occupancy = [[False] * self._max_cols for _ in range(self._max_rows)]

        # 基本尺寸（与百家乐一致）
        cell = 25
        pad = 2
        label_w = 30
        label_h = 20

        total_w = label_w + self._max_cols * (cell + pad) + pad
        total_h = label_h + self._max_rows * (cell + pad) + pad

        # 容器（背景色与百家乐保持一致）
        marker_frame = tk.Frame(self.marker_view, bg='#D0E7FF')
        marker_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 在标志路下方创建统计显示
        self._create_stats_display(marker_frame)

        # ──【Big Road 标题】（可选，如果想给 Big Road 单独一个标题，可以加上）
        big_title = tk.Label(
            marker_frame,
            text="大路",
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

        # Marker Road 标题与画布（放在 Big Road 下面）
        marker_title = tk.Label(marker_frame, text="标记路", font=('Arial', 14, 'bold'), bg='#D0E7FF')
        marker_title.pack(pady=(6, 4))

        self.marker_canvas = tk.Canvas(marker_frame, bg='#D0E7FF', highlightthickness=0)
        self.marker_canvas.pack(fill=tk.BOTH, expand=True, padx=3, pady=(0, 0))

    def _update_bigroad(self):
        """
        将 self.bigroad_results 绘制到 self.bigroad_canvas 上（严格符合你的要求）：
        - 圆圈内不显示文字（仅用颜色区分：Dragon 红, Tiger 橙）
        - 仅当上一个非 Tie 的胜方与当前相同且位置为"同列且行号为 prev_row+1"时才画连线
        - Tie 不占新格，在最后一个非 Tie 的格子上叠加斜线与计数（和局不破链）
        """
        if not hasattr(self, 'bigroad_canvas'):
            return

        # 布局参数（与创建时保持一致）
        cell = 25
        pad = 2
        label_w = 32
        label_h = 22

        # 清除上次 data 层（保留 grid）
        self.bigroad_canvas.delete('data')

        # 重新初始化占用矩阵与 tie_tracker
        self._bigroad_occupancy = [[False] * self._max_cols for _ in range(self._max_rows)]
        tie_tracker = {}  # (r,c) -> tie count

        # 记录上一个非 Tie 的位置和胜方
        last_non_tie_pos = None      # (row, col)
        last_non_tie_winner = None  # 'Dragon' 或 'Tiger'
        last_run_start_col = -1

        def occupy(r, c):
            if 0 <= r < self._max_rows and 0 <= c < self._max_cols:
                self._bigroad_occupancy[r][c] = True

        def center_of(r, c):
            x1 = label_w + c * (cell + pad)
            y1 = label_h + r * (cell + pad)
            cx = x1 + cell / 2
            cy = y1 + cell / 2
            return cx, cy

        def draw_circle(r, c, winner):
            cx, cy = center_of(r, c)
            radius = cell * 0.42
            # 颜色按要求
            color = "#FF0000" if winner == 'Dragon' else "#FFA600"
            # 圆（data 层），无文字，无边框
            self.bigroad_canvas.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                fill=color, outline='', tags=('data', 'circle')
            )

        def draw_connect(prev_r, prev_c, cur_r, cur_c, winner):
            # 获取圆心坐标
            px, py = center_of(prev_r, prev_c)
            cx, cy = center_of(cur_r, cur_c)
            
            # 计算半径
            radius = cell * 0.42
            
            # 判断连线方向并计算起点和终点
            if prev_c == cur_c:  # 垂直方向（向下）
                # 从上一个圆点的底部到下一个圆点的顶部
                start_x, start_y = px, py + radius
                end_x, end_y = cx, cy - radius
            else:  # 水平方向（向右）
                # 从上一个圆点的右侧到下一个圆点的左侧
                start_x, start_y = px + radius, py
                end_x, end_y = cx - radius, cy
            
            # 连线颜色同胜方颜色
            line_color = "#FF0000" if winner == 'Dragon' else "#FFA600"
            # 连线与斜线同一层
            self.bigroad_canvas.create_line(start_x, start_y, end_x, end_y, width=4, fill=line_color, tags=('data', 'connect', 'tie_line'))

        def draw_tie_overlay(r, c, count):
            cx, cy = center_of(r, c)
            tie_tag = f"tie_{r}_{c}"
            # 删除旧的同 tag（避免重复）
            self.bigroad_canvas.delete(tie_tag)
            # 画斜线 - 斜线与连线同一层
            self.bigroad_canvas.create_line(cx - 10, cy + 10, cx + 10, cy - 10, width=3, fill="#03ABAB", tags=('data', 'tie_line', tie_tag))
            if count > 1:
                # 在中央显示次数 - 文字在斜线的上层，字体大小改为14
                self.bigroad_canvas.create_text(cx, cy, text=str(count), font=('Arial', 14, 'bold'), fill="#000000", tags=('data', 'tie_text', tie_tag))

        # 主循环：按 bigroad_results 顺序放格子
        col = 0
        row = 0
        for entry in (self.bigroad_results or []):
            # 兼容 dict 或简单字符串
            if isinstance(entry, dict):
                winner = entry.get('winner')
                tcount = entry.get('tie_count', 0)
            else:
                winner = entry
                tcount = 0

            # Tie：不占新格，在最后一次非 Tie 的格子上叠加
            if winner == 'Tie' or winner =="SameSuitTie":
                if last_non_tie_pos is None:
                    # 全部为 Tie 的极端情况：使用 (0,0) 作为锚点
                    anchor_r, anchor_c = 0, 0
                    if not self._bigroad_occupancy[anchor_r][anchor_c]:
                        occupy(anchor_r, anchor_c)
                        # 画一个默认圆（便于显示 overlay），使用 Dragon 颜色不会对逻辑有影响
                        draw_circle(anchor_r, anchor_c, 'Dragon')
                        tie_tracker[(anchor_r, anchor_c)] = tie_tracker.get((anchor_r, anchor_c), 0) + 1
                        draw_tie_overlay(anchor_r, anchor_c, tie_tracker[(anchor_r, anchor_c)])
                    else:
                        tie_tracker[(anchor_r, anchor_c)] = tie_tracker.get((anchor_r, anchor_c), 0) + 1
                        draw_tie_overlay(anchor_r, anchor_c, tie_tracker[(anchor_r, anchor_c)])
                else:
                    lr, lc = last_non_tie_pos
                    tie_tracker[(lr, lc)] = tie_tracker.get((lr, lc), 0) + (tcount or 1)
                    draw_tie_overlay(lr, lc, tie_tracker[(lr, lc)])
                # Tie 不改变连胜逻辑，继续处理下一个 entry
                continue

            # 非 Tie：放格子（考虑新跑道或连胜）
            # 记录放置前的 last_non_tie_pos（用于决定是否连线）
            prev_non_tie_pos = last_non_tie_pos
            prev_non_tie_winner = last_non_tie_winner

            if last_non_tie_winner is None or winner != last_non_tie_winner:
                # 新跑道：在 row=0, 从 last_run_start_col+1 找第一列可用位置
                start_c = last_run_start_col + 1
                found = False
                for c_try in range(start_c, self._max_cols):
                    if not self._bigroad_occupancy[0][c_try]:
                        col = c_try
                        row = 0
                        found = True
                        break
                if not found:
                    for c_try in range(0, self._max_cols):
                        if not self._bigroad_occupancy[0][c_try]:
                            col = c_try
                            row = 0
                            found = True
                            break
                    if not found:
                        # 画布已满，停止绘制
                        break
                last_run_start_col = col
                # 更新当前位置并画圆
                occupy(row, col)
                draw_circle(row, col, winner)
                # 更新 last_non_tie_*（新跑道不会连到前一个不同胜方）
                last_non_tie_pos = (row, col)
                last_non_tie_winner = winner
            else:
                # 连胜：优先向下放（同列）
                down_row = row + 1
                if down_row < self._max_rows and not self._bigroad_occupancy[down_row][col]:
                    row = down_row
                    occupy(row, col)
                    draw_circle(row, col, winner)
                    # 只有在 prev_non_tie_pos 存在且正好位于 (row-1, col)（即垂直相邻）且 prev 勝方相同时才连线
                    if prev_non_tie_pos and prev_non_tie_winner == winner:
                        prev_r, prev_c = prev_non_tie_pos
                        if prev_c == col and prev_r == row - 1:
                            draw_connect(prev_r, prev_c, row, col, winner)
                    # 更新 last_non_tie_pos（连胜中的新格为新的 last）
                    last_non_tie_pos = (row, col)
                    last_non_tie_winner = winner
                else:
                    # 若不能向下（被占或越界），向右找本行空位（同一 row）
                    next_col = col + 1
                    found = False
                    for c_try in range(next_col, self._max_cols):
                        if not self._bigroad_occupancy[row][c_try]:
                            col = c_try
                            found = True
                            break
                    if not found:
                        # 退回到在 row=0 寻找新列
                        for c_try in range(last_run_start_col + 1, self._max_cols):
                            if not self._bigroad_occupancy[0][c_try]:
                                row = 0
                                col = c_try
                                last_run_start_col = c_try
                                found = True
                                break
                    if not found:
                        break
                    occupy(row, col)
                    draw_circle(row, col, winner)
                    # 这里通常不是垂直相邻（同列）情形，所以一般不连线（除非前一个非 Tie 恰好是左侧相邻且同列）
                    if prev_non_tie_pos and prev_non_tie_winner == winner:
                        prev_r, prev_c = prev_non_tie_pos
                        # 现在支持水平相邻的连线（同一行，列相邻）
                        if prev_r == row and prev_c == col - 1:
                            draw_connect(prev_r, prev_c, row, col, winner)
                    last_non_tie_pos = (row, col)
                    last_non_tie_winner = winner

            # 如果 entry 自带 tie_count（罕见），在当前格显示
            if tcount and isinstance(tcount, int) and tcount > 0:
                lr, lc = last_non_tie_pos
                tie_tracker[(lr, lc)] = tie_tracker.get((lr, lc), 0) + tcount
                draw_tie_overlay(lr, lc, tie_tracker[(lr, lc)])

        # 调整层级：连线与斜线在同一层，文字在最上层
        self.bigroad_canvas.tag_raise('tie_text')

        # 刷新画布
        try:
            self.bigroad_canvas.update_idletasks()
        except Exception:
            pass

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
        """创建空的统计信息面板"""
        # 主框架
        stats_frame = tk.Frame(parent, bg='#D0E7FF')
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0), padx=10)
        
        # 添加外边框
        ttk.Separator(stats_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10, 10))

    def _update_stats_display(self):
        """更新统计显示"""
        if hasattr(self, 'stats_rows'):
            for key, row in self.stats_rows.items():
                count = self.stats_counts.get(key, 0)
                row['count_label'].config(text=str(count))

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

    def add_marker_result(self, winner):
        """
        添加新的珠路/标志路结果（同时把结果写入 bigroad_results 并触发 bigroad 更新）
        winner: 'Dragon' / 'Tiger' / 'Tie' / 'SameSuitTie'（你程序使用的命名）
        """
        # 如果珠路图已满，移除最旧的一行数据（按行移除）
        try:
            if len(self.marker_results) >= self.max_marker_rows * self.max_marker_cols:
                for _ in range(self.max_marker_rows):
                    if self.marker_results:
                        self.marker_results.pop(0)
        except Exception:
            # 若没有 max_marker_rows 等属性，则忽略该步
            pass

        # 更新计数（确保键存在）
        if winner not in self.marker_counts:
            self.marker_counts[winner] = 0
        if not hasattr(self, 'stats_counts'):
            self.stats_counts = {}
        if winner not in self.stats_counts:
            self.stats_counts[winner] = 0

        self.marker_counts[winner] += 1
        self.stats_counts[winner] += 1

        # 存储到 marker_results
        self.marker_results.append(winner)

        # --- 关键：也更新 bigroad_results 并触发绘制（解决"大路没有更新"） ---
        try:
            if not hasattr(self, 'bigroad_results') or self.bigroad_results is None:
                self.bigroad_results = []
            self.bigroad_results.append(winner)
            if hasattr(self, '_update_bigroad'):
                self._update_bigroad()
        except Exception:
            pass

        # 更新统计显示（如果存在）
        try:
            if hasattr(self, '_update_stats_display'):
                self._update_stats_display()
        except Exception:
            pass

        # 重新绘制标记路（如果存在对应函数）
        try:
            if hasattr(self, '_update_marker_road'):
                self._update_marker_road()
        except Exception:
            pass

    def _update_stats_display(self):
        """更新统计显示"""
        if hasattr(self, 'stats_rows'):
            # 定义统计项与显示键的映射
            stats_mapping = {
                'Dragon': 'dragon',
                'Tiger': 'tiger', 
                'Tie': 'tie',
                'SameSuitTie': 'samesuit_tie'
            }
            
            for winner_key, display_key in stats_mapping.items():
                if display_key in self.stats_rows:
                    count = self.stats_counts.get(winner_key, 0)
                    self.stats_rows[display_key]['count_label'].config(text=str(count))

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
            if result == 'Dragon':
                color = "#FF0000"
                text = "龙"
                text_color = 'white'
            elif result == 'Tiger':
                color = "#FFA600"
                text = "虎"
                text_color = 'black'
            elif result == 'SameSuitTie':
                color = "#FFFFFF"
                text = "花"
                text_color = 'black'
            else:  # Tie
                color = "#00FFFF"
                text = "和"
                text_color = 'black'
            
            # 绘制主圆点
            self.marker_canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill=color,
                outline='#000000',
                width=2,  
                tags='dot'
            )

            self.marker_canvas.create_text(
                center_x, center_y,
                text=text,
                fill=text_color,
                font=('Arial', '12', 'bold'),
                tags='dot'
            )

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
        """填充左部分：下注格子"""
        # 显示用的中文映射
        bet_display_map = {
            'DoubleRed': '双红',
            'RedBlack': '红黑各一',
            'DoubleBlack': '双黑',
            'Small': '小(A-6)',
            'SameSuitTie': '同花和局',
            'Big': '大(8-K)',
            'Dragon': '龙',
            'Tie': '和局',
            'Tiger': '虎'
        }

        # 赔率映射 - 修改背景颜色和文字颜色，添加禁用状态颜色
        odds_map = {
            'DoubleRed': ('3:1#', "#FF0000", "black", "#CC0000"),        # 正常红色，禁用时深红色
            'RedBlack': ('1:1#', "#C8FF00", "black", "#A0CC00"),         # 正常黄绿色，禁用时深黄绿色
            'DoubleBlack': ('3:1#', "#000000", "white", "#333333"),      # 正常黑色，禁用时深灰色
            'Small': ('1:1*', "#FFD700", "black", "#CCAC00"),            # 正常金色，禁用时深金色
            'SameSuitTie': ('50:1', "#44ff44", "black", "#33CC33"),     # 正常绿色，禁用时深绿色
            'Big': ('1:1*', "#ff00bb", "black", "#CC0099"),              # 正常粉红色，禁用时深粉红色
            'Dragon': ('1:1#', "#FF0000", "white", "#CC0000"),           # 正常红色，禁用时深红色
            'Tie': ('10:1', "#00FFFF", "black", "#00CCCC"),             # 正常青色，禁用时深青色
            'Tiger': ('1:1#', "#FFA600", "black", "#CC8400")             # 正常橙色，禁用时深橙色
        }

        # 创建三行下注按钮
        row1_frame = tk.Frame(parent, bg='#D0E7FF', height=80)
        row1_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row1_frame.pack_propagate(False)

        buttons_to_show_1 = ['DoubleRed','RedBlack','DoubleBlack']

        for bt in buttons_to_show_1:
            odds, bg_color, text_color, disabled_color = odds_map[bt]
            display_name = bet_display_map.get(bt, bt)
            btn = tk.Button(
                row1_frame,
                text=f"{odds}\n{display_name}\n~~",
                bg=bg_color,
                fg=text_color,
                font=('Arial', 12, 'bold'),
                height=3,
                width=12,
                wraplength=90,
                disabledforeground=text_color,  # 禁用状态也保持相同文字颜色
                highlightthickness=0
            )
            # 存储按钮的原始颜色和禁用颜色
            btn.original_bg = bg_color
            btn.disabled_bg = disabled_color
            
            # 左键下注
            btn.config(command=lambda t=bt, b=btn: self.place_bet(t, b))
            # 右键清除
            btn.bind('<Button-3>', lambda e, t=bt, b=btn: self._on_right_click_clear(e, t, b))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        row2_frame = tk.Frame(parent, bg='#D0E7FF', height=80)
        row2_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row2_frame.pack_propagate(False)

        buttons_to_show_2 = ['Small','SameSuitTie','Big']

        for bt in buttons_to_show_2:
            odds, bg_color, text_color, disabled_color = odds_map[bt]
            display_name = bet_display_map.get(bt, bt)
            btn = tk.Button(
                row2_frame,
                text=f"{odds}\n{display_name}\n~~",
                bg=bg_color,
                fg=text_color,
                font=('Arial', 12, 'bold'),
                height=3,
                width=12,
                wraplength=90,
                disabledforeground=text_color,  # 禁用状态也保持相同文字颜色
                highlightthickness=0
            )
            # 存储按钮的原始颜色和禁用颜色
            btn.original_bg = bg_color
            btn.disabled_bg = disabled_color
            
            btn.config(command=lambda t=bt, b=btn: self.place_bet(t, b))
            btn.bind('<Button-3>', lambda e, t=bt, b=btn: self._on_right_click_clear(e, t, b))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        row3_frame = tk.Frame(parent, bg='#D0E7FF', height=80)
        row3_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row3_frame.pack_propagate(False)

        buttons_to_show_3 = ['Dragon','Tie','Tiger']

        for bt in buttons_to_show_3:
            odds, bg_color, text_color, disabled_color = odds_map[bt]
            display_name = bet_display_map.get(bt, bt)
            btn = tk.Button(
                row3_frame,
                text=f"{odds}\n{display_name}\n~~",
                bg=bg_color,
                fg=text_color,
                font=('Arial', 12, 'bold'),
                height=3,
                width=12,
                wraplength=80,
                disabledforeground=text_color,  # 禁用状态也保持相同文字颜色
                highlightthickness=0,
                highlightbackground='black'
            )
            # 存储按钮的原始颜色和禁用颜色
            btn.original_bg = bg_color
            btn.disabled_bg = disabled_color
            
            btn.config(command=lambda t=bt, b=btn: self.place_bet(t, b))
            btn.bind('<Button-3>', lambda e, t=bt, b=btn: self._on_right_click_clear(e, t, b))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

            # 说明
            explanation = "*和局时 小/大输 ||| #和局时 龙/虎/双红/红黑各一/双黑退还一半本金"

            explanation_frame = tk.Frame(parent, bg='#D0E7FF', height=40)
            explanation_frame.pack(fill=tk.BOTH, expand=True, pady=2)
            explanation_frame.pack_propagate(False)

            tk.Label(
                explanation_frame,
                text=explanation,
                font=('Arial', 12),
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
        balance_display_frame.pack(fill=tk.X)
        
        # 余额标签
        self.balance_label = tk.Label(
            balance_display_frame,
            text=f"余额: ${int(round(self.balance)):,}",
            font=('Arial', 22),
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
        separator.pack(fill=tk.X, padx=2, pady=2)

        # 每注限制
        minmax_frame = tk.Frame(parent, bg='#D0E7FF')
        minmax_frame.pack(fill=tk.X)

        table_border_color = "#d70000"
        table_bg = '#f9f9f9'

        outer_frame = tk.Frame(minmax_frame, bg=table_border_color, bd=2, relief=tk.SOLID)
        outer_frame.pack(padx=5, pady=2, fill=tk.X)

        header_frame = tk.Frame(outer_frame, bg=table_border_color)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="边注最高", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="和局最高", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="主注最高", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)

        content_frame = tk.Frame(outer_frame, bg=table_bg)
        content_frame.pack(fill=tk.X)
        tk.Label(content_frame, text="30,000", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="100,000", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="500,000", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 分隔线
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5, pady=1)

        # DEAL/RESET 按钮行
        btn_frame = tk.Frame(parent, bg='#D0E7FF')
        btn_frame.pack(fill=tk.X, pady=2)
        self.reset_button = tk.Button(
            btn_frame, text="重设金额", command=self.reset_bets,
            bg='#ff4444', fg='white',
            font=('微软雅黑', 16, 'bold')
        )
        self.reset_button.pack(side=tk.TOP, expand=True, fill=tk.X, padx=10, pady=3)
        self.deal_button = tk.Button(
            btn_frame, text="开始游戏 (Enter)", command=self.start_game,
            bg='gold', fg='black',
            font=('微软雅黑', 16, 'bold')
        )
        self.deal_button.pack(side=tk.TOP, expand=True, fill=tk.X, padx=10, pady=1)

        # 分隔线 + 当前/上次下注显示
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(3, 0), padx=2)

        current_bet_frame = tk.Frame(parent, bg='#D0E7FF')
        current_bet_frame.pack(pady=(0, 1))
        tk.Label(
            current_bet_frame, text="当前下注:", width=12,
            font=('微软雅黑', 16), bg='#D0E7FF'
        ).pack(side=tk.LEFT)
        self.current_bet_label = tk.Label(
            current_bet_frame, text="$0", width=10,
            font=('微软雅黑', 16), bg='#D0E7FF'
        )
        self.current_bet_label.pack(side=tk.RIGHT)

        last_win_frame = tk.Frame(parent, bg='#D0E7FF')
        last_win_frame.pack()
        tk.Label(
            last_win_frame, text="上局获胜:", width=12,
            font=('微软雅黑', 16), bg='#D0E7FF'
        ).pack(side=tk.LEFT)
        self.last_win_label = tk.Label(
            last_win_frame, text="$0", width=10,
            font=('微软雅黑', 16), bg='#D0E7FF'
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
            ('3万', '#ffa500')
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

        # 预设选中1000筹码并设置发光效果
        self._set_default_chip()

        # 当前选中筹码显示
        self.current_chip_label = tk.Label(
            parent,
            text="筹码: $1,000",
            font=('Arial', 18),
            fg='black',
            bg='#D0E7FF'
        )
        self.current_chip_label.pack(side=tk.LEFT, padx=0)

    def _set_default_chip(self):
        """设置默认选中的筹码（1千），显示发光效果"""
        for chip in self.chip_buttons:
            if chip['text'] == '1千':
                # 设置金色边框和发光效果
                chip['canvas'].itemconfig(chip['chip_id'], outline='yellow', width=4)
                self.selected_canvas = chip['canvas']
                self.selected_id = chip['chip_id']
                self.selected_chip = chip
                self.selected_bet_amount = 1000
                if hasattr(self, 'current_chip_label'):
                    self.current_chip_label.config(text="筹码: $1,000")
                break

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

        # 读取当前想要下的筹码金额
        amount = int(self.selected_bet_amount)

        # 计算该 bet_type 已有的投注
        existing = int(self.current_bets.get(bet_type, 0))

        # 决定该投注类型的上限
        if bet_type in ('Dragon', 'Tiger'):
            limit = 500_000
        elif bet_type == 'Tie':
            limit = 100_000
        else:
            limit = 30_000

        allowed_remaining = limit - existing
        if allowed_remaining <= 0:
            # 已经达到上限，提示并返回
            messagebox.showwarning("投注上限", f"当前投注已达到上限${limit:,}，无法再下注。")
            return

        # 实际可以放下的量（先按上限限制，再按余额限制）
        to_place = min(amount, allowed_remaining, self.balance)

        if to_place <= 0:
            # 余额不足或已达上限
            if self.balance <= 0:
                messagebox.showerror("Error", "余额不足")
            return

        # 扣款并记录下注
        self.balance -= to_place
        self.current_bet += to_place
        self.current_bets[bet_type] = self.current_bets.get(bet_type, 0) + to_place

        # 更新界面显示
        self.update_balance()
        self.current_bet_label.config(text=f"${self.current_bet:,}")

        # 更新对应按钮上显示的数额
        for btn in self.bet_buttons:
            if hasattr(btn, 'bet_type') and btn.bet_type == bet_type:
                original_text = btn.cget("text").split('\n')
                # 如果原文本不足三行，保底填充
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
        # 禁用所有按钮和键盘绑定
        self.disable_all_buttons()
        
        # 检查牌堆剩余张数，如果少于60张则重新初始化
        if len(self.game.deck) - self.game.cut_position < 60:
            # 重新初始化游戏
            self._initialize_game(True)
            return

        self.game.play_game()
        self.animate_dealing()

    def animate_dealing(self):
        self.table_canvas.delete('all')
        self.point_labels.clear()
        self._draw_table_labels()

        # 创建两个"点数"显示
        self.dragon_total_id = self.table_canvas.create_text(
            120, 200, text="~", font=('Arial', 80, 'bold'), fill='white')
        self.tiger_total_id = self.table_canvas.create_text(
            880, 200, text="~", font=('Arial', 80, 'bold'), fill='white')

        # track which cards we've flipped face-up
        self.revealed_cards = {'dragon': [], 'tiger': []}

        self._deal_initial_cards()
        self.after(1000, self._reveal_dragon_card)

    def _deal_initial_cards(self):
        self.initial_card_ids = []
        # Dragon card
        for i, pos in enumerate(self._get_card_positions("dragon")[:1]):
            self._animate_card_entrance("dragon", i, pos)
        # Tiger card
        for i, pos in enumerate(self._get_card_positions("tiger")[:1]):
            self._animate_card_entrance("tiger", i, pos)

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

    def _reveal_dragon_card(self):
        card_info = self.initial_card_ids[0]
        real_card = self.game.dragon_hand[0]
        self._flip_card(card_info, real_card, 0)
        self.after(500, self._reveal_tiger_card)

    def _reveal_tiger_card(self):
        card_info = self.initial_card_ids[1]
        real_card = self.game.tiger_hand[0]
        self._flip_card(card_info, real_card, 1)
        self.after(750, self.resolve_bets)

    def _flip_card(self, card_info, real_card, seq, step=0):
        """
        用水平缩放模拟翻牌。
        card_info: (hand_type, canvas_image_id)
        real_card: ('Club','A') 形式或类似 tuple，用于打开正面图片
        seq: 序号（原来代码传的）
        step: 内部递归帧计数，外部调用不需要传
        """
        # 参数/帧设置
        steps = 12               # 总帧数（偶数更好）
        orig_w, orig_h = 120, 170  # 与 _load_assets 中使用的大小一致

        hand_type, card_id = card_info

        # 结束条件：最后一帧将真实牌面放回缓存的 full-size 图
        if step > steps:
            try:
                # 用缓存的完整图片作为最终帧
                self.table_canvas.itemconfig(card_id, image=self.card_images[real_card])
            except Exception:
                # 容错：如果出错，忽略
                pass

            # 记录已翻开的牌并更新点数显示
            try:
                self.revealed_cards[hand_type].append(real_card)
            except Exception:
                # 初始化保护
                if not hasattr(self, 'revealed_cards'):
                    self.revealed_cards = {'dragon': [], 'tiger': []}
                self.revealed_cards[hand_type].append(real_card)

            # 更新已翻开的点数显示
            try:
                # 龙虎斗中显示牌面值
                card_value = real_card[1]
                # 特殊牌面显示
                if card_value == 'A':
                    display_text = "A"
                elif card_value == 'J':
                    display_text = "J"
                elif card_value == 'Q':
                    display_text = "Q"
                elif card_value == 'K':
                    display_text = "K"
                else:
                    display_text = card_value
                    
                if hand_type == 'dragon':
                    self.table_canvas.itemconfig(self.dragon_total_id, text=display_text)
                else:
                    self.table_canvas.itemconfig(self.tiger_total_id, text=display_text)
            except Exception:
                pass

            # 清理临时图像引用
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

        # 生成缩放后的 PhotoImage
        img = self._create_scaled_image(real_card, w, orig_h, use_back=use_back)
        # 保存引用避免被回收
        if not hasattr(self, '_temp_flip_images'):
            self._temp_flip_images = {}
        self._temp_flip_images[card_id] = img

        # 更新 canvas 上的图像
        try:
            self.table_canvas.itemconfig(card_id, image=img)
        except Exception:
            pass

        # 下一帧
        self.after(20, lambda: self._flip_card(card_info, real_card, seq, step+1))

    def _create_scaled_image(self, card, w, h, use_back=False):
        """
        按宽度 w、高度 h 生成 ImageTk.PhotoImage。
        如果 use_back=True 则读取背面 Background.png，否则读取正面 card 的图片文件。
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
            # 出问题时返回一个占位图
            try:
                from PIL import Image
                placeholder = Image.new('RGBA', (max(1, int(w)), int(h)), (0,0,0,0))
                return ImageTk.PhotoImage(placeholder)
            except Exception:
                # 最后兜底：返回已有的 back_image
                return getattr(self, 'back_image', None)

    def resolve_bets(self):
        payouts = 0
        total_bet_amount = sum(self.current_bets.values())

        # 判断花色
        dragon_suit = self.game.dragon_hand[0][0]
        tiger_suit = self.game.tiger_hand[0][0]
        
        # 判断颜色
        red_suits = ['Diamond', 'Heart']
        black_suits = ['Club', 'Spade']
        dragon_color = 'red' if dragon_suit in red_suits else 'black'
        tiger_color = 'red' if tiger_suit in red_suits else 'black'
        
        # 判断大小
        dragon_score = self.game.dragon_score
        tiger_score = self.game.tiger_score
        max_score = max(dragon_score, tiger_score)
        is_small = max_score <= 6  # A-6为小
        is_big = max_score >= 8    # 8-K为大

        # 结算各种下注
        for bet_type, bet_amount in self.current_bets.items():
            if bet_type == 'Dragon':
                if self.game.winner == 'Dragon':
                    payouts += bet_amount * 2
                elif self.game.winner in ['Tie', 'SameSuitTie']:
                    payouts += bet_amount * 0.5  # 和局退还一半
                    
            elif bet_type == 'Tiger':
                if self.game.winner == 'Tiger':
                    payouts += bet_amount * 2
                elif self.game.winner in ['Tie', 'SameSuitTie']:
                    payouts += bet_amount * 0.5  # 和局退还一半
                    
            elif bet_type == 'SameSuitTie':
                if self.game.winner == 'SameSuitTie':
                    payouts += bet_amount * 51  # 50:1赔率

            elif bet_type == 'Tie':
                if self.game.winner == 'Tie':
                    payouts += bet_amount * 11  # 10:1赔率
                    
            elif bet_type == 'DoubleRed':
                if dragon_color == 'red' and tiger_color == 'red':
                    if self.game.winner in ['Dragon', 'Tiger']:
                        payouts += bet_amount * 4  # 3:1赔率
                    elif self.game.winner in ['Tie', 'SameSuitTie']:
                        payouts += bet_amount * 0.5  # 和局退还一半
                        
            elif bet_type == 'DoubleBlack':
                if dragon_color == 'black' and tiger_color == 'black':
                    if self.game.winner in ['Dragon', 'Tiger']:
                        payouts += bet_amount * 4  # 3:1赔率
                    elif self.game.winner in ['Tie', 'SameSuitTie']:
                        payouts += bet_amount * 0.5  # 和局退还一半
                        
            elif bet_type == 'RedBlack':
                if ((dragon_color == 'red' and tiger_color == 'black') or 
                    (dragon_color == 'black' and tiger_color == 'red')):
                    if self.game.winner in ['Dragon', 'Tiger']:
                        payouts += bet_amount * 2  # 1:1赔率
                    elif self.game.winner in ['Tie', 'SameSuitTie']:
                        payouts += bet_amount * 0.5  # 和局退还一半
                        
            elif bet_type == 'Small':
                if is_small and self.game.winner in ['Dragon', 'Tiger']:
                    payouts += bet_amount * 2  # 1:1赔率
                    
            elif bet_type == 'Big':
                if is_big and self.game.winner in ['Dragon', 'Tiger']:
                    payouts += bet_amount * 2  # 1:1赔率

        # 将赔付加入余额并清空当前投注
        self.balance += payouts
        self.current_bets.clear()
        self.update_balance()

        # 更新按钮文字显示为 ~~
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

        # 更新 last_win
        try:
            self.last_win = int(payouts)
            if hasattr(self, 'last_win_label'):
                self.last_win_label.config(text=f"${max(self.last_win, 0):,}")
        except Exception:
            pass

        # 卡片动画
        self._animate_cards_result()

        # 显示结果文本
        self._show_result_text()

        # 添加珠路图结果
        self.add_marker_result(self.game.winner)
        
        # 检查牌堆剩余张数，如果少于60张则重新初始化
        if len(self.game.deck) - self.game.cut_position < 60:
            # 重新初始化游戏
            self._initialize_game(True)
        else:
            # 启用按钮（分阶段）
            self.after(100, self.enable_buttons_except_deal)  # 立即启用除deal外的按钮
            self.after(1800, lambda: self.deal_button.config(state=tk.NORMAL))  # 1.8秒后启用deal按钮
            self.after(2000, lambda: self.bind('<Return>', lambda e: self.start_game()))  # 2秒后启用Enter键

    def _animate_cards_result(self):
        """根据游戏结果移动扑克牌位置"""
        # 获取龙和虎的扑克牌ID
        dragon_card_id = None
        tiger_card_id = None
        
        for hand_type, card_id in self.initial_card_ids:
            if hand_type == 'dragon':
                dragon_card_id = card_id
            elif hand_type == 'tiger':
                tiger_card_id = card_id
        
        if not dragon_card_id or not tiger_card_id:
            return
            
        # 获取当前卡片位置
        dragon_pos = self.table_canvas.coords(dragon_card_id)
        tiger_pos = self.table_canvas.coords(tiger_card_id)
        
        if not dragon_pos or not tiger_pos:
            return
            
        dragon_x, dragon_y = dragon_pos
        tiger_x, tiger_y = tiger_pos
        
        # 根据胜方决定移动方向
        if self.game.winner == 'Dragon':
            # 龙获胜，龙牌下移20px
            target_dragon_y = dragon_y + 20
            self._animate_card_move(dragon_card_id, dragon_x, dragon_y, dragon_x, target_dragon_y, 100)
            
        elif self.game.winner == 'Tiger':
            # 虎获胜，虎牌下移20px
            target_tiger_y = tiger_y + 20
            self._animate_card_move(tiger_card_id, tiger_x, tiger_y, tiger_x, target_tiger_y, 100)
            
        elif self.game.winner in ['Tie', 'SameSuitTie']:
            # 和局或同花和局，龙牌左移20px，虎牌右移20px
            target_dragon_x = dragon_x + 50
            target_tiger_x = tiger_x - 50
            self._animate_card_move(dragon_card_id, dragon_x, dragon_y, target_dragon_x, dragon_y, 100)
            self._animate_card_move(tiger_card_id, tiger_x, tiger_y, target_tiger_x, tiger_y, 100)

    def _animate_card_move(self, card_id, start_x, start_y, end_x, end_y, duration):
        """移动单张扑克牌的动画"""
        steps = int(duration / 10)  # 每10毫秒一帧
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps

        def move_step(step=0):
            if step < steps:
                new_x = start_x + dx * step
                new_y = start_y + dy * step
                self.table_canvas.coords(card_id, new_x, new_y)
                self.after(10, move_step, step+1)
                
        move_step()

    def _show_result_text(self):
        """显示结果文本"""
        text = ""
        text_color = "white"
        bg_color = "#35654d"

        # 条件判断逻辑 - 显示正确的文本
        if self.game.winner == 'Dragon':
            text = "龙获胜"
            text_color = "#FFFFFF"  # 白色文字
            bg_color = '#FF0000'    # 红色背景
        elif self.game.winner == 'Tiger':
            text = "虎获胜"
            text_color = "#000000"  # 黑色文字
            bg_color = '#FFA600'    # 橙色背景
        elif self.game.winner == 'SameSuitTie':
            text = "同花和局"
            text_color = "#000000"  # 黑色文字
            bg_color = '#44FF44'    # 绿色背景
        else:  # Tie
            text = "和局"
            text_color = "#000000"  # 黑色文字
            bg_color = '#00FFFF'    # 青色背景

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

        # 再次更新文字背景
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

    def _animate_result_cards(self):
        # 结果动画后不启用按钮，因为已经在resolve_bets中分阶段启用了
        pass

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${int(round(self.balance)):,}")
        # 更新JSON文件中的余额
        update_balance_in_json(self.username, self.balance)

    def show_game_instructions(self):
        # 创建游戏说明窗口
        win = tk.Toplevel(self)
        win.title("龙虎斗游戏说明")
        win.geometry("600x400")
        win.resizable(False, False)
        
        # 计算窗口居中位置
        self.update_idletasks()
        
        # 获取主窗口位置和尺寸
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_width = self.winfo_width()
        main_height = self.winfo_height()
        
        # 获取弹窗尺寸
        popup_width = 600
        popup_height = 400
        
        # 计算居中位置
        x = main_x + (main_width - popup_width) // 2
        y = main_y + (main_height - popup_height) // 2
        
        # 设置弹窗位置
        win.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        
        # 创建文本框架
        text_frame = tk.Frame(win)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        instructions = """
龙虎斗游戏规则：

1. 游戏发两张牌：龙一张，虎一张
2. 比较两张牌的大小，A最小，K最大
3. 下注选项：
   - 双红：两张牌都是红色，赔率3:1
   - 红黑各一：一红一黑，赔率1:1  
   - 双黑：两张牌都是黑色，赔率3:1
   - 小：最大牌是A-6，赔率1:1
   - 大：最大牌是8-K，赔率1:1
   - 同花和局：两张牌花色相同，赔率50:1
   - 和局：两张牌点数相同，赔率10:1
   - 龙/虎：龙或虎获胜，赔率1:1

4. 特殊规则：
   - 和局时龙/虎下注退还一半本金
   - 和局时双红/双黑/红黑各一下注退还一半本金

5. 牌面显示：
   - A、J、Q、K显示为字母
   - 其他数字显示数字本身
        """
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=('Arial', 12), padx=10, pady=10)
        text_widget.insert(tk.END, instructions)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # 关闭按钮
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

# 在Baccarat.py中的main函数
def main(initial_balance=1000000, username="Guest"):
    app = DragonTigerGUI(initial_balance, username)
    app.mainloop()
    return app.balance  # 正确返回数值

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")