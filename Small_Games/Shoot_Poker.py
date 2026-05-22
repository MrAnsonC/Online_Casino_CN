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

class ShootDragonGate:
    def __init__(self, decks=3, external_deck=None):
        if external_deck:
            self.deck = [(card['suit'], card['rank']) for card in external_deck]
            self.total_cards = len(self.deck)
        else:
            self.create_deck(decks)
        self.first_card = None
        self.second_card = None
        self.third_card = None
        self.diff = None
        self.result = None
        self.cut_position = 0
        self.used_cards = 0
        self.decks = decks
        self.round_counter = 0

    def create_deck(self, decks=3):
        suits = ['Club', 'Diamond', 'Heart', 'Spade']
        ranks = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
        self.deck = [(suit, rank) for _ in range(decks) for suit in suits for rank in ranks]
        random.shuffle(self.deck)
        self.total_cards = len(self.deck)
        return self.deck

    def advanced_shuffle(self, cut_pos):
        if self.total_cards == 0:
            self.create_deck(self.decks)
        self.deck = self.deck[cut_pos:] + self.deck[:cut_pos]
        first_card = self.deck[0]
        deduct_map = {
            'A': 1, 'J': 10, 'Q': 10, 'K': 10,
            '10': 10, '2':2, '3':3, '4':4, '5':5,
            '6':6, '7':7, '8':8, '9':9
        }
        deduct = deduct_map.get(first_card[1], 0)
        end_pos = (1 + deduct) % self.total_cards
        self.deck = self.deck[end_pos:] + self.deck[:end_pos]
        self.used_cards = random.randint(28, 48)
        self.cut_position = 0
        self.round_counter = 0

    def card_value(self, card):
        rank = card[1]
        value_map = {
            'A': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7,
            '8': 8, '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13
        }
        return value_map.get(rank, 0)

    def deal_initial(self):
        indices = [(self.cut_position + i) % self.total_cards for i in range(3)]
        self.first_card = self.deck[indices[0]]
        self.second_card = self.deck[indices[1]]
        self.third_card = self.deck[indices[2]]
        self.cut_position = (self.cut_position + 3) % self.total_cards

        val1 = self.card_value(self.first_card)
        val2 = self.card_value(self.second_card)
        val3 = self.card_value(self.third_card)
        self.diff = abs(val1 - val2)

        if val3 == val1 or val3 == val2:
            self.result = '撞柱'
        else:
            low = min(val1, val2)
            high = max(val1, val2)
            if low < val3 < high:
                self.result = '射中'
            else:
                self.result = '射偏'

    def get_odds_for_shoot(self):
        diff = self.diff
        if diff == 0:
            odds_hit = 13.5
        else:
            odds_hit = 5.6

        odds_table = {
            0: (None, 0.1, odds_hit),
            1: (None, 0.1, odds_hit),
            2: (11, 0.2, odds_hit),
            3: (5, 0.35, odds_hit),
            4: (3, 0.5, odds_hit),
            5: (2, 0.75, odds_hit),
            6: (1.5, 1, odds_hit),
            7: (1, 1.5, odds_hit),
            8: (0.75, 2, odds_hit),
            9: (0.5, 3, odds_hit),
            10: (0.35, 5, odds_hit),
            11: (0.2, 11, odds_hit),
            12: (0.1, None, odds_hit),
        }
        diff = max(0, min(12, diff))
        odds_mid, odds_miss, odds_hit_val = odds_table[diff]
        return (odds_mid, odds_miss, odds_hit_val)

class ShootDragonGateGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("射龙门")
        self.geometry("1350x700+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')

        self.bet_buttons = []
        self.selected_chip = None
        self.chip_buttons = []
        self.result_text_id = None
        self.result_bg_id = None

        self.game_mode = "shootdragon"
        self.game = ShootDragonGate()
        self.balance = initial_balance
        self.current_bets = {}
        self.card_images = {}

        self.current_streak = 0
        self.current_streak_type = None
        self.longest_streaks = {'射中': 0, '射偏': 0, '撞柱': 0}
        self.stats_counts = {'射中': 0, '射偏': 0, '撞柱': 0}
        self.marker_results = []
        self.marker_counts = {'射中': 0, '射偏': 0, '撞柱': 0}
        self.max_marker_rows = 6
        self.max_marker_cols = 11
        self.view_mode = "marker"
        self.bigroad_results = []
        self._max_rows = 6
        self._max_cols = 40
        self._bigroad_occupancy = [[False]*self._max_cols for _ in range(self._max_rows)]

        self._load_assets()
        self._create_widgets()
        self._setup_bindings()
        self.selected_bet_amount = 1000
        self.current_bet = 0
        self.last_win = 0
        self.username = username
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.first_two_revealed = False
        self.betting_enabled = False
        self._initialize_game(False)

    def on_close(self):
        self.destroy()
        self.quit()

    def disable_all_buttons(self):
        for btn in self.bet_buttons:
            btn.config(state=tk.DISABLED, bg=btn.disabled_bg)
        self.deal_button.config(state=tk.DISABLED)
        self.reset_button.config(state=tk.DISABLED)
        self.unbind('<Return>')

    def enable_all_buttons(self):
        for btn in self.bet_buttons:
            btn.config(state=tk.NORMAL, bg=btn.original_bg)
        self.deal_button.config(state=tk.DISABLED)
        self.reset_button.config(state=tk.DISABLED)
        for chip in self.chip_buttons:
            chip['canvas'].bind('<Button-1>',
                lambda e, t=chip['text'], c=chip['canvas'], cid=chip['chip_id']: self._set_bet_amount(t, c, cid))
        self.bind('<Return>', lambda e: self.start_game())

    def enable_buttons_except_deal(self):
        for btn in self.bet_buttons:
            btn.config(state=tk.NORMAL, bg=btn.original_bg)
        self.reset_button.config(state=tk.NORMAL)
        for chip in self.chip_buttons:
            chip['canvas'].bind('<Button-1>',
                lambda e, t=chip['text'], c=chip['canvas'], cid=chip['chip_id']: self._set_bet_amount(t, c, cid))

    def _load_assets(self):
        card_size = (120, 170)
        suits = ['Club', 'Diamond', 'Heart', 'Spade']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1')

        self.card_image_paths = {}

        for suit in suits:
            for rank in ranks:
                filename = f"{suit}{rank}.png"
                path = os.path.join(card_dir, filename)
                if not os.path.exists(path):
                    print(f"[Shoot] 缺少正面牌文件: {path}")
                    continue
                try:
                    img = Image.open(path).convert('RGBA').resize(card_size, Image.LANCZOS)
                    key = (suit, rank)
                    self.card_images[key] = ImageTk.PhotoImage(img)
                    self.card_image_paths[key] = path
                except Exception as e:
                    print(f"[Shoot] 载入正面牌失败 {path}: {e}")

        back_path = os.path.join(card_dir, 'Background.png')
        try:
            self.back_image = ImageTk.PhotoImage(
                Image.open(back_path).convert('RGBA').resize(card_size, Image.LANCZOS)
            )
        except Exception as e:
            print(f"[Shoot] 载入背面失败 {back_path}: {e}")
            self.back_image = None

    def _initialize_game(self, second):
        self.unbind('<Return>')
        dialog_w, dialog_h = 360, 190
        dialog = tk.Toplevel(self)
        dialog.title("切牌")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.update_idletasks()
        try:
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_w = self.winfo_width()
            parent_h = self.winfo_height()
        except Exception:
            parent_x = parent_y = 0
            parent_w = parent_h = 0
        if parent_w <= 1 or parent_h <= 1:
            screen_w = dialog.winfo_screenwidth()
            screen_h = dialog.winfo_screenheight()
            x = (screen_w - dialog_w) // 2
            y = (screen_h - dialog_h) // 2
        else:
            x = parent_x + (parent_w - dialog_w) // 2
            y = parent_y + (parent_h - dialog_h) // 2
        dialog.geometry(f"{dialog_w}x{dialog_h}+{int(x)}+{int(y)}")
        if second:
            tk.Label(dialog, text="牌靴已经用完 \n请老板切牌 切牌位置在15-140之间",
                    font=('微软雅黑', 10)).pack(pady=(8, 4))
        else:
            tk.Label(dialog, text="请老板切牌 切牌位置在15-140之间",
                    font=('微软雅黑', 10)).pack(pady=(8, 4))
        entry_frame = tk.Frame(dialog)
        entry_frame.pack(pady=(2, 6))
        tk.Label(entry_frame, text="切牌位置:", font=('微软雅黑', 10)).pack(side=tk.LEFT, padx=(6, 8))
        entry_var = tk.StringVar()
        entry = tk.Entry(entry_frame, font=('Arial', 12), width=8, textvariable=entry_var)
        entry.pack(side=tk.LEFT)
        entry.focus_set()
        scale_var = tk.IntVar(value=80)
        scale = tk.Scale(dialog, from_=15, to=140, orient=tk.HORIZONTAL, length=240,
                        variable=scale_var, showvalue=False)
        scale.pack(pady=(4, 4))
        result = [None]
        def on_scale_change(v):
            try:
                vi = int(float(v))
            except Exception:
                return
            entry_var.set(str(vi))
        scale.configure(command=on_scale_change)
        def on_ok():
            s = entry_var.get().strip()
            if s == "":
                result[0] = None
            else:
                try:
                    v = int(s)
                except Exception:
                    result[0] = None
                    dialog.destroy()
                    return
                if v < 15:
                    v = 15
                elif v > 140:
                    v = 140
                entry_var.set(str(v))
                scale_var.set(v)
                result[0] = v
            dialog.destroy()
        def on_cancel():
            result[0] = None
            dialog.destroy()
        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="随机", width=8, command=on_cancel).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="确认", width=8, command=on_ok).pack(side=tk.LEFT, padx=10)
        dialog.bind('<Return>', lambda e: on_ok())
        self.wait_window(dialog)
        cut_position = result[0]

        current_dir = os.path.dirname(os.path.abspath(__file__))
        tools_dir = os.path.join(os.path.dirname(current_dir), 'A_Tools')
        card_dir = os.path.join(tools_dir, 'Card')
        shuffle_py = os.path.join(card_dir, 'shuffle.py')
        external_deck = None
        external_cut_position = None
        try:
            import importlib.util
            import secrets as _secrets
            spec = importlib.util.spec_from_file_location("shuffle_mod", shuffle_py)
            if spec and spec.loader:
                shuffle_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(shuffle_mod)
                try:
                    external_deck = shuffle_mod.generate_shuffled_deck(has_joker=False, deck_count=3)
                    if isinstance(external_deck, (list, tuple)):
                        total_cards = len(external_deck)
                        lower = 15
                        upper = min(140, total_cards - 1)
                        if upper >= lower:
                            external_cut_position = int(_secrets.randbelow(upper - lower + 1)) + lower
                        else:
                            external_cut_position = min(max(total_cards // 2, lower), max(lower, total_cards - 1))
                    else:
                        external_deck = None
                except Exception as e:
                    print(f"调用 shuffle.generate_shuffled_deck 出错: {e}")
                    external_deck = None
        except Exception as e:
            print(f"载入 shuffle.py 时出错: {e}")

        if cut_position is None:
            if external_cut_position is not None and 15 <= external_cut_position <= 140:
                cut_position = external_cut_position
            else:
                cut_position = random.randint(15, 140)

        self.game = ShootDragonGate(external_deck=external_deck)
        self.game.advanced_shuffle(cut_position)

        self.marker_results = []
        self.marker_counts = {'射中': 0, '射偏': 0, '撞柱': 0}
        self.stats_counts = {'射中': 0, '射偏': 0, '撞柱': 0}
        self.reset_marker_road()
        self.reset_bigroad()

        self._initial_draw_and_discard()

    def _initial_draw_and_discard(self):
        self.disable_all_buttons()
        self.table_canvas.delete('all')
        self._draw_table_labels()
        first_card = self.game.deck[0]
        self.game.deck = self.game.deck[1:]
        first_card_id = self.table_canvas.create_image(500, 0, image=self.back_image)
        def move_first_card(step=0):
            if step <= 30:
                x = 500 + (120 - 500) * (step / 30)
                y = 0 + (225 - 0) * (step / 30)
                self.table_canvas.coords(first_card_id, x, y)
                self.after(10, move_first_card, step+1)
            else:
                self._flip_first_card(first_card_id, first_card)
        move_first_card()

    def _flip_first_card(self, card_id, card):
        def flip_step(step=0):
            steps = 12
            if step > steps:
                card_key = self._normalize_card(card)
                final_img = self.card_images.get(card_key)
                if final_img is None:
                    try:
                        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1')
                        filename = f"{card_key[0]}{card_key[1]}.png"
                        path = os.path.join(card_dir, filename)
                        img = Image.open(path).convert('RGBA').resize((120, 170), Image.LANCZOS)
                        final_img = ImageTk.PhotoImage(img)
                        self.card_images[card_key] = final_img
                    except Exception as e:
                        print(f"[Burn] 加载正面牌失败 {card} -> {card_key}: {e}")
                        final_img = self.back_image
                try:
                    self.table_canvas.itemconfig(card_id, image=final_img)
                except Exception:
                    pass
                if not hasattr(self, '_temp_flip_images'):
                    self._temp_flip_images = {}
                self._temp_flip_images[card_id] = final_img
                deduct_map = {
                    'A': 1, 'J': 10, 'Q': 10, 'K': 10,
                    '10': 10, '2': 2, '3': 3, '4': 4, '5': 5,
                    '6': 6, '7': 7, '8': 8, '9': 9
                }
                discard_count = deduct_map.get(card[1], 0)
                self.after(500, lambda: self._discard_cards_animation(discard_count))
                return
            half = steps // 2
            if step <= half:
                ratio = 1 - (step / float(half))
                use_back = True
            else:
                ratio = (step - half) / float(half)
                use_back = False
            orig_w, orig_h = 120, 170
            w = max(1, int(orig_w * ratio))
            img = self._create_scaled_image(self._normalize_card(card), w, orig_h, use_back=use_back)
            if not hasattr(self, '_temp_flip_images'):
                self._temp_flip_images = {}
            self._temp_flip_images[card_id] = img
            try:
                self.table_canvas.itemconfig(card_id, image=img)
            except Exception:
                pass
            self.after(20, lambda: flip_step(step + 1))
        flip_step()

    def _discard_cards_animation(self, discard_count):
        if discard_count == 0:
            self._finish_initial_discard()
            return
        self.discard_cards = []
        self.current_discard_index = 0
        self._animate_single_discard_card(discard_count)

    def _animate_single_discard_card(self, total_discard_count):
        if self.current_discard_index >= total_discard_count:
            self.after(5000, self._remove_discard_cards)
            return
        start_x, start_y = 500, 0
        card_id = self.table_canvas.create_image(start_x, start_y, image=self.back_image)
        self.discard_cards.append(card_id)
        i = self.current_discard_index
        row = i // 5
        col = i % 5
        if total_discard_count <= 5:
            target_x = 260 + col * 120
            target_y = 225
        else:
            target_x = 260 + col * 120
            target_y = 130 + row * 170
        def move_single_card(step=0):
            if step <= 30:
                x = start_x + (target_x - start_x) * (step / 30)
                y = start_y + (target_y - start_y) * (step / 30)
                self.table_canvas.coords(card_id, x, y)
                self.after(10, move_single_card, step+1)
            else:
                self.current_discard_index += 1
                self.after(200, lambda: self._animate_single_discard_card(total_discard_count))
        move_single_card()

    def _remove_discard_cards(self):
        for card_id in self.discard_cards:
            self.table_canvas.delete(card_id)
        discard_count = len(self.discard_cards)
        if discard_count > 0:
            self.game.deck = self.game.deck[discard_count:]
        self.discard_cards = []
        self._finish_initial_discard()

    def _finish_initial_discard(self):
        self.table_canvas.delete('all')
        self._draw_table_labels()
        self.enable_all_buttons()
        self.unbind('<Return>')
        self.after(500, self.start_game)

    def do_nothing(self):
        pass

    def reset_bigroad(self):
        self.bigroad_results.clear()
        self._bigroad_occupancy = [[False] * self._max_cols for _ in range(self._max_rows)]
        if hasattr(self, 'bigroad_canvas'):
            self.bigroad_canvas.delete('data')

    def _create_stats_display(self, parent):
        self.stats_frame = tk.Frame(parent, bg='#D0E7FF', height=180)
        self.stats_frame.pack(fill=tk.X, pady=(0, 0))
        self.stats_frame.pack_propagate(False)
        title_label = tk.Label(self.stats_frame, text="统计结果", font=('Arial', 16, 'bold'), bg='#D0E7FF', fg='#000000')
        title_label.pack(pady=(3, 0))
        table_frame = tk.Frame(self.stats_frame, bg='#D0E7FF')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        headers = ['赢家', '图标', '数量']
        for i, header in enumerate(headers):
            header_label = tk.Label(table_frame, text=header, font=('Arial', 14, 'bold'),
                                    bg='#4B8BBE', fg='white', width=16, height=1, relief=tk.RAISED, bd=2)
            header_label.grid(row=0, column=i, padx=1, pady=1, sticky='nsew')
        stats_items = [
            {'key': 'shoot', 'text': '射中', 'color': '#FF0000', 'icon_text': '中', 'text_color': 'white'},
            {'key': 'miss', 'text': '射偏', 'color': '#FFA600', 'icon_text': '偏', 'text_color': 'black'},
            {'key': 'hit', 'text': '撞柱', 'color': '#00FFFF', 'icon_text': '柱', 'text_color': 'black'}
        ]
        self.stats_rows = {}
        for row_idx, item in enumerate(stats_items, 1):
            name_label = tk.Label(table_frame, text=item['text'], font=('Arial', 14),
                                  bg='#FFFFFF', fg='#000000', width=14, height=2, relief=tk.RIDGE, bd=1)
            name_label.grid(row=row_idx, column=0, padx=1, pady=1, sticky='nsew')
            icon_frame = tk.Frame(table_frame, bg='#FFFFFF', width=60, height=40)
            icon_frame.grid(row=row_idx, column=1, padx=1, pady=1, sticky='nsew')
            icon_frame.grid_propagate(False)
            icon_canvas = tk.Canvas(icon_frame, width=26, height=26, bg='#FFFFFF', highlightthickness=0)
            icon_canvas.place(relx=0.5, rely=0.5, anchor='center')
            center_x, center_y = 13, 13
            radius = 10
            icon_canvas.create_oval(center_x - radius, center_y - radius, center_x + radius, center_y + radius,
                                    fill=item['color'], outline='#000000', width=2)
            icon_canvas.create_text(center_x, center_y, text=item['icon_text'],
                                    fill=item['text_color'], font=('Arial', 10, 'bold'))
            count_label = tk.Label(table_frame, text="0", font=('Arial', 14, 'bold'),
                                   bg='#FFFFFF', fg='#000000', width=8, height=2, relief=tk.RIDGE, bd=1)
            count_label.grid(row=row_idx, column=2, padx=1, pady=1, sticky='nsew')
            self.stats_rows[item['key']] = {'name_label': name_label, 'icon_canvas': icon_canvas, 'count_label': count_label}
        for i in range(3):
            table_frame.columnconfigure(i, weight=1)
        for i in range(5):
            table_frame.rowconfigure(i, weight=1, minsize=25)

    def reset_marker_road(self):
        self.marker_results = []
        self.stats_counts = {'射中': 0, '射偏': 0, '撞柱': 0}
        self.marker_counts = {'射中': 0, '射偏': 0, '撞柱': 0}
        self._update_stats_display()
        self._draw_marker_grid()

    def _create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)
        left_frame = ttk.Frame(main_frame, width=900)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_frame = ttk.Frame(main_frame, width=450)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.table_canvas = tk.Canvas(left_frame, bg='#35654d', highlightthickness=0, height=400)
        self.table_canvas.pack(fill=tk.BOTH, expand=False)
        self._draw_table_labels()

        betting_area = tk.Frame(left_frame, bg='#D0E7FF', height=180)
        betting_area.pack(fill=tk.BOTH, expand=True, pady=5)

        betting_left = tk.Frame(betting_area, bg='#D0E7FF', width=500)
        betting_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        betting_center = tk.Frame(betting_area, bg='#D0E7FF', width=200)
        betting_center.pack(side=tk.LEFT, fill=tk.BOTH, padx=5)
        betting_right = tk.Frame(betting_area, bg='#D0E7FF', width=200)
        betting_right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5)

        self._populate_betting_area(betting_left, betting_center, betting_right)
        self._create_control_panel(right_frame)

    # ================== 足球网绘制（从 tt.py 移植并适配边界） ==================
    def draw_soccer_net(self, canvas, left=240, right=760, top=45, bottom=350):
        """在指定canvas上绘制3D足球门网，位置限定在(left, top)-(right, bottom)区域内"""
        # 清除旧网格（使用标签方便管理）
        canvas.delete('soccer_net')

        # ---------- 原始3D坐标定义（与tt.py完全一致） ----------
        # 前框 (z = 40)
        flt = (60, 75, 40)
        frt = (196, 75, 40)
        flb = (60, 176, 40)
        frb = (196, 176, 40)
        # 后框 (z = 0)
        blt = (40, 55, 0)
        brt = (216, 55, 0)
        blb = (40, 156, 0)
        brb = (216, 156, 0)

        # ---------- 辅助函数：原始tp映射 + 线性缩放到目标矩形 ----------
        # 原始tp: (x, -y+200)   (根据tt.py中的transform+project)
        def orig_tp(p):
            x, y, z = p
            return (x, -y + 200)

        # 计算原始坐标的范围（通过经验值）
        # 原始x范围: 40~216, 原始y范围(经过tp后): y_min=24, y_max=145
        orig_x_min, orig_x_max = 40, 216
        orig_y_min, orig_y_max = 24, 145
        target_x_min, target_x_max = left, right
        target_y_min, target_y_max = top, bottom

        def map_point(p):
            ox, oy = orig_tp(p)
            nx = target_x_min + (ox - orig_x_min) / (orig_x_max - orig_x_min) * (target_x_max - target_x_min)
            ny = target_y_min + (oy - orig_y_min) / (orig_y_max - orig_y_min) * (target_y_max - target_y_min)
            return (nx, ny)

        def draw_line(p1, p2, **kwargs):
            x1, y1 = map_point(p1)
            x2, y2 = map_point(p2)
            canvas.create_line(x1, y1, x2, y2, tags='soccer_net', **kwargs)

        def draw_polygon(points, **kwargs):
            pts = []
            for p in points:
                x, y = map_point(p)
                pts.extend([x, y])
            # 只画轮廓，不填充（避免覆盖原有背景）
            canvas.create_polygon(pts, tags='soccer_net', outline=kwargs.get('outline', 'white'),
                                  fill='', width=kwargs.get('width', 1))

        # ---------- 绘制门框（白色粗线） ----------
        edges = [
            (flt, frt), (flt, flb), (frt, frb), (flb, frb),
            (flt, blt), (frt, brt), (flb, blb), (frb, brb),
            (blb, brb), (blt, blb), (brt, brb),
        ]
        for e in edges:
            draw_line(e[0], e[1], fill="white", width=3)

        # ---------- 网格辅助函数 ----------
        def grid(p1, p2, p3, p4, cols, rows):
            for i in range(1, cols):
                t = i / cols
                a = (
                    p1[0] + (p2[0] - p1[0]) * t,
                    p1[1] + (p2[1] - p1[1]) * t,
                    p1[2] + (p2[2] - p1[2]) * t,
                )
                b = (
                    p4[0] + (p3[0] - p4[0]) * t,
                    p4[1] + (p3[1] - p4[1]) * t,
                    p4[2] + (p3[2] - p4[2]) * t,
                )
                draw_line(a, b, fill="#c8ffd0", width=1)

            for i in range(1, rows):
                t = i / rows
                a = (
                    p1[0] + (p4[0] - p1[0]) * t,
                    p1[1] + (p4[1] - p1[1]) * t,
                    p1[2] + (p4[2] - p1[2]) * t,
                )
                b = (
                    p2[0] + (p3[0] - p2[0]) * t,
                    p2[1] + (p3[1] - p2[1]) * t,
                    p2[2] + (p3[2] - p2[2]) * t,
                )
                draw_line(a, b, fill="#c8ffd0", width=1)

        # 绘制四个面的网格（前、左、右、底）
        grid(flt, frt, frb, flb, 18, 10)   # 前
        grid(flt, blt, blb, flb, 6, 10)    # 左
        grid(brt, frt, frb, brb, 6, 10)    # 右
        grid(flb, frb, brb, blb, 18, 6)    # 底

        # 将网格置于底层（不影响后续卡片等元素）
        canvas.tag_lower('soccer_net')
    # ================== 足球网结束 ==================

    def _draw_table_labels(self):
        # 每次重新绘制画布时，先绘制足球网（作为背景）
        self.draw_soccer_net(self.table_canvas, left=240, right=760, top=45, bottom=350)

        # 再绘制其他文字标签
        self.table_canvas.create_text(270, 30, text="第一张", font=('Arial', 20, 'bold'), fill='white', tags='static_label')
        self.table_canvas.create_text(730, 30, text="第二张", font=('Arial', 20, 'bold'), fill='white', tags='static_label')
        self.table_canvas.create_text(500, 30, text="第三张", font=('Arial', 20, 'bold'), fill='white', tags='static_label')
        self.result_text_id = self.table_canvas.create_text(500, 370, text="", font=('Arial', 34, 'bold'),
                                                            fill='white', tags=('result_text', 'static_label'))
        self.result_bg_id = self.table_canvas.create_rectangle(0, 0, 0, 0, fill='', outline='', tags=('result_bg', 'static_label'))

    def draw_odds_table(self):
        """根据前两张牌的点数绘制13格的赔率提示表"""
        self.clear_odds_table()
        val1 = self.game.card_value(self.game.first_card)
        val2 = self.game.card_value(self.game.second_card)
        low = min(val1, val2)
        high = max(val1, val2)
        pillar_points = {val1, val2}
        rank_names = {
            1: 'A', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7',
            8: '8', 9: '9', 10: '10', 11: 'J', 12: 'Q', 13: 'K'
        }
        start_x = 210
        y = 350
        cell_width = 44
        cell_height = 36
        self.odds_table_items = []
        for point in range(1, 14):
            if point in pillar_points:
                bg_color = '#00FFFF'
                fg_color = '#000000'
            elif low < point < high:
                bg_color = '#FF0000'
                fg_color = '#FFFFFF'
            else:
                bg_color = '#FFA600'
                fg_color = '#000000'
            x1 = start_x + (point - 1) * cell_width
            y1 = y
            x2 = x1 + cell_width
            y2 = y1 + cell_height
            rect_id = self.table_canvas.create_rectangle(
                x1, y1, x2, y2, fill=bg_color, outline='#333333', width=1,
                tags='odds_table'
            )
            text_id = self.table_canvas.create_text(
                (x1 + x2) / 2, (y1 + y2) / 2,
                text=rank_names[point], fill=fg_color,
                font=('Arial', 12, 'bold'), tags='odds_table'
            )
            self.odds_table_items.append((rect_id, text_id))

    def clear_odds_table(self):
        if hasattr(self, 'odds_table_items'):
            for rect_id, text_id in self.odds_table_items:
                try:
                    self.table_canvas.delete(rect_id)
                    self.table_canvas.delete(text_id)
                except:
                    pass
            self.odds_table_items = []
        self.table_canvas.delete('odds_table')

    def _get_card_positions(self, card_index):
        if card_index == 0:
            x = 270
        elif card_index == 1:
            x = 730
        else:
            x = 500
        y = 200
        return (x, y)

    def _create_chip_button(self, parent, text, bg_color):
        size = 60
        canvas = tk.Canvas(parent, width=size, height=size, highlightthickness=0, background='#D0E7FF')
        chip_id = canvas.create_oval(2, 2, size-2, size-2, fill=bg_color, outline='', width=0)
        rgb = ImageColor.getrgb(bg_color)
        luminance = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2]
        text_color = 'white' if luminance < 140 else 'black'
        canvas.create_text(size/2, size/2, text=text, fill=text_color, font=('Arial', 16, 'bold'))
        canvas.bind('<Button-1>', lambda e, t=text, c=canvas, cid=chip_id: self._set_bet_amount(t, c, cid))
        self.chip_buttons.append({'canvas': canvas, 'chip_id': chip_id, 'text': text})
        return canvas

    def _set_bet_amount(self, chip_text, clicked_canvas, clicked_chip_id):
        for chip in self.chip_buttons:
            if chip['canvas'] != clicked_canvas:
                chip['canvas'].itemconfig(chip['chip_id'], outline='', width=0)
                chip['canvas'].delete('glow')
        clicked_canvas.itemconfig(clicked_chip_id, outline='yellow', width=4)
        for chip in self.chip_buttons:
            if chip['canvas'] == clicked_canvas:
                self.selected_chip = chip
                break
        if '千' in chip_text:
            amount = int(chip_text.replace('千', '')) * 1000
        elif '万' in chip_text:
            amount = int(chip_text.replace('万', '')) * 10000
        else:
            amount = int(chip_text)
        self.selected_bet_amount = amount
        if hasattr(self, 'current_chip_label'):
            self.current_chip_label.config(text=f"筹码: ${amount:,}")

    def reset_bets(self):
        for bet_type, amt in self.current_bets.items():
            self.balance += amt
        self.current_bets.clear()
        self.current_bet = 0
        self.update_balance()
        self.current_bet_label.config(text=f"${0:,}")
        for btn in self.bet_buttons:
            if hasattr(btn, 'bet_key'):
                original_text = btn.cget("text").split('\n')
                new_text = f"{original_text[0]}\n{original_text[1]}\n~~"
                btn.config(text=new_text)

    def _create_control_panel(self, parent):
        control_frame = tk.Frame(parent, bg='#D0E7FF', width=300)
        control_frame.pack(pady=12, padx=10, fill=tk.BOTH, expand=True)
        control_frame.pack_propagate(False)
        self.view_container = tk.Frame(control_frame, bg='#D0E7FF', height=300)
        self.view_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.view_container.pack_propagate(False)
        self.marker_view = tk.Frame(self.view_container, bg='#D0E7FF')
        self.marker_view.pack(fill=tk.BOTH, expand=True)
        self._create_marker_road()
        self.enable_bigroad_navigation()

    def show_bigroad_view(self):
        self.marker_view.pack_forget()
        self.bigroad_view.pack(fill=tk.BOTH, expand=True)
        self.marker_view_btn.config(relief=tk.FLAT, bg='#888888')
        self.bigroad_view_btn.config(relief=tk.RAISED, bg='#4B8BBE')
        self.view_mode = "bigroad"

    def show_marker_view(self):
        self.bigroad_view.pack_forget()
        self.marker_view.pack(fill=tk.BOTH, expand=True)
        self.marker_view_btn.config(relief=tk.RAISED, bg='#4B8BBE')
        self.bigroad_view_btn.config(relief=tk.FLAT, bg='#888888')
        self.view_mode = "marker"

    def _create_marker_road(self):
        self.bigroad_results = []
        self._max_rows = 6
        self._max_cols = 60
        self._bigroad_occupancy = [[False] * self._max_cols for _ in range(self._max_rows)]
        cell = 25
        pad = 2
        label_w = 30
        label_h = 20
        total_w = label_w + self._max_cols * (cell + pad) + pad
        total_h = label_h + self._max_rows * (cell + pad) + pad
        marker_frame = tk.Frame(self.marker_view, bg='#D0E7FF')
        marker_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._create_stats_display(marker_frame)
        big_title = tk.Label(marker_frame, text="大路", font=('Arial', 14, 'bold'), bg='#D0E7FF')
        big_title.pack(pady=(0, 5))
        big_frame = tk.Frame(marker_frame, bg='#D0E7FF')
        big_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)
        hbar = tk.Scrollbar(big_frame, orient=tk.HORIZONTAL)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.bigroad_canvas = tk.Canvas(big_frame, bg='#FFFFFF', width=290, height=total_h,
                                        xscrollcommand=hbar.set, scrollregion=(0, 0, total_w, total_h),
                                        highlightthickness=0)
        self.bigroad_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        hbar.config(command=self.bigroad_canvas.xview)
        for c in range(self._max_cols):
            x = label_w + pad + c * (cell + pad) + cell / 2
            y = label_h / 2
            self.bigroad_canvas.create_text(x, y, text=str(c + 1), font=('Arial', 8), tags=('grid',))
        for r in range(self._max_rows):
            x = label_w / 2
            y = label_h + pad + r * (cell + pad) + cell / 2
            self.bigroad_canvas.create_text(x, y, text=str(r + 1), font=('Arial', 8), tags=('grid',))
        for c in range(self._max_cols):
            for r in range(self._max_rows):
                x1 = label_w + pad + c * (cell + pad)
                y1 = label_h + pad + r * (cell + pad)
                x2 = x1 + cell
                y2 = y1 + cell
                self.bigroad_canvas.create_rectangle(x1, y1, x2, y2, outline='#888888', fill='#FFFFFF', tags=('grid',))
        marker_title = tk.Label(marker_frame, text="标记路", font=('Arial', 14, 'bold'), bg='#D0E7FF')
        marker_title.pack(pady=(6, 4))
        self.marker_canvas = tk.Canvas(marker_frame, bg='#D0E7FF', highlightthickness=0)
        self.marker_canvas.pack(fill=tk.BOTH, expand=True, padx=3, pady=(0, 0))

    def _update_bigroad(self):
        if not hasattr(self, 'bigroad_canvas'):
            return
        cell = 25
        pad = 2
        label_w = 32
        label_h = 22
        self.bigroad_canvas.delete('data')
        self._bigroad_occupancy = [[False] * self._max_cols for _ in range(self._max_rows)]
        tie_tracker = {}
        last_non_tie_pos = None
        last_non_tie_winner = None
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
            color = "#FF0000" if winner == '射中' else "#FFA600" if winner == '射偏' else "#00FFFF"
            self.bigroad_canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                                            fill=color, outline='', tags=('data', 'circle'))
        def draw_connect(prev_r, prev_c, cur_r, cur_c, winner):
            px, py = center_of(prev_r, prev_c)
            cx, cy = center_of(cur_r, cur_c)
            radius = cell * 0.42
            if prev_c == cur_c:
                start_x, start_y = px, py + radius
                end_x, end_y = cx, cy - radius
            else:
                start_x, start_y = px + radius, py
                end_x, end_y = cx - radius, cy
            line_color = "#FF0000" if winner == '射中' else "#FFA600" if winner == '射偏' else "#00FFFF"
            self.bigroad_canvas.create_line(start_x, start_y, end_x, end_y, width=4, fill=line_color, tags=('data', 'connect'))
        col = 0
        row = 0
        for winner in self.bigroad_results:
            if winner not in ('射中', '射偏', '撞柱'):
                continue
            prev_non_tie_pos = last_non_tie_pos
            prev_non_tie_winner = last_non_tie_winner
            if last_non_tie_winner is None or winner != last_non_tie_winner:
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
                        break
                last_run_start_col = col
                occupy(row, col)
                draw_circle(row, col, winner)
                last_non_tie_pos = (row, col)
                last_non_tie_winner = winner
            else:
                down_row = row + 1
                if down_row < self._max_rows and not self._bigroad_occupancy[down_row][col]:
                    row = down_row
                    occupy(row, col)
                    draw_circle(row, col, winner)
                    if prev_non_tie_pos and prev_non_tie_winner == winner:
                        prev_r, prev_c = prev_non_tie_pos
                        if prev_c == col and prev_r == row - 1:
                            draw_connect(prev_r, prev_c, row, col, winner)
                    last_non_tie_pos = (row, col)
                    last_non_tie_winner = winner
                else:
                    next_col = col + 1
                    found = False
                    for c_try in range(next_col, self._max_cols):
                        if not self._bigroad_occupancy[row][c_try]:
                            col = c_try
                            found = True
                            break
                    if not found:
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
                    if prev_non_tie_pos and prev_non_tie_winner == winner:
                        prev_r, prev_c = prev_non_tie_pos
                        if prev_r == row and prev_c == col - 1:
                            draw_connect(prev_r, prev_c, row, col, winner)
                    last_non_tie_pos = (row, col)
                    last_non_tie_winner = winner
        self.bigroad_canvas.tag_raise('tie_text')
        try:
            self.bigroad_canvas.update_idletasks()
        except Exception:
            pass

    def enable_bigroad_navigation(self, debug=False):
        canvas = getattr(self, 'bigroad_canvas', None)
        if canvas is None:
            return
        try:
            canvas.unbind("<MouseWheel>")
            canvas.unbind("<Button-4>")
            canvas.unbind("<Button-5>")
            root = canvas.winfo_toplevel()
            root.unbind_all("<MouseWheel>")
            root.unbind_all("<Button-4>")
            root.unbind_all("<Button-5>")
        except Exception:
            pass
        try:
            canvas.unbind("<KeyPress-Left>")
            canvas.unbind("<KeyPress-Right>")
            self._bigroad_key_scroll_units = 5
            canvas.bind("<KeyPress-Left>", lambda e: self._on_bigroad_key(e, canvas))
            canvas.bind("<KeyPress-Right>", lambda e: self._on_bigroad_key(e, canvas))
            canvas.bind("<Button-1>", lambda e: canvas.focus_set())
            canvas.bind("<Enter>", lambda e: canvas.focus_set())
        except Exception:
            pass

    def _on_bigroad_key(self, event, canvas):
        try:
            units = getattr(self, "_bigroad_key_scroll_units", 5)
            keysym = getattr(event, 'keysym', '')
            if keysym == 'Left':
                canvas.xview_scroll(-units, "units")
            elif keysym == 'Right':
                canvas.xview_scroll(units, "units")
        except Exception:
            pass

    def _update_stats_display(self):
        if hasattr(self, 'stats_rows'):
            mapping = {'射中': 'shoot', '射偏': 'miss', '撞柱': 'hit'}
            for winner_key, display_key in mapping.items():
                if display_key in self.stats_rows:
                    count = self.stats_counts.get(winner_key, 0)
                    self.stats_rows[display_key]['count_label'].config(text=str(count))

    def _draw_marker_grid(self):
        self.marker_canvas.delete('all')
        rows, cols = 6, 9
        cell_size = 30
        padding = 0
        self.max_marker_rows = rows
        self.max_marker_cols = cols
        width = cols * (cell_size + padding) + padding
        height = rows * (cell_size + padding) + padding
        self.marker_canvas.config(width=width, height=height)
        for col in range(cols):
            for row in range(rows):
                x1 = padding + col * (cell_size + padding)
                y1 = padding + row * (cell_size + padding)
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                self.marker_canvas.create_rectangle(x1, y1, x2, y2, outline='#888888', fill='#D0E7FF')

    def add_marker_result(self, winner):
        if winner not in self.marker_counts:
            self.marker_counts[winner] = 0
        if winner not in self.stats_counts:
            self.stats_counts[winner] = 0
        self.marker_counts[winner] += 1
        self.stats_counts[winner] += 1
        self.marker_results.append(winner)
        try:
            if not hasattr(self, 'bigroad_results') or self.bigroad_results is None:
                self.bigroad_results = []
            self.bigroad_results.append(winner)
            if hasattr(self, '_update_bigroad'):
                self._update_bigroad()
        except Exception:
            pass
        try:
            self._update_stats_display()
        except Exception:
            pass
        try:
            self._update_marker_road()
        except Exception:
            pass

    def _update_marker_road(self):
        self.marker_canvas.delete('dot')
        rows, cols = 6, 9
        cell_size = 30
        padding = 0
        width = cols * (cell_size + padding) + padding
        height = rows * (cell_size + padding) + padding
        self.marker_canvas.config(width=width, height=height)
        for col in range(cols):
            for row in range(rows):
                x1 = padding + col * (cell_size + padding)
                y1 = padding + row * (cell_size + padding)
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                self.marker_canvas.create_rectangle(x1, y1, x2, y2, outline='#888888', fill='#D0E7FF')
        start_idx = max(0, len(self.marker_results) - rows * cols)
        for idx, result in enumerate(self.marker_results[start_idx:]):
            if idx >= rows * cols:
                break
            col = idx // rows
            row = idx % rows
            x1 = padding + col * (cell_size + padding)
            y1 = padding + row * (cell_size + padding)
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            radius = cell_size * 0.4
            if result == '射中':
                color = "#FF0000"
                text = "中"
                text_color = 'white'
            elif result == '射偏':
                color = "#FFA600"
                text = "偏"
                text_color = 'black'
            else:
                color = "#00FFFF"
                text = "柱"
                text_color = 'black'
            self.marker_canvas.create_oval(center_x - radius, center_y - radius, center_x + radius, center_y + radius,
                                           fill=color, outline='#000000', width=2, tags='dot')
            self.marker_canvas.create_text(center_x, center_y, text=text, fill=text_color,
                                           font=('Arial', '12', 'bold'), tags='dot')

    def _populate_betting_area(self, left, center, right):
        self.betting_left = left
        self.betting_center = center
        self.betting_right = right
        self._populate_betting_left(left)
        self._populate_betting_center(center)
        self._populate_betting_right(right)

    def _populate_betting_left(self, parent):
        suit_frame = tk.Frame(parent, bg='#D0E7FF', height=80)
        suit_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        suit_frame.pack_propagate(False)
        suits = [('Club', '♣梅花♣'), ('Diamond', '♦方块♦'), ('Heart', '♥红心♥'), ('Spade', '♠黑桃♠')]
        suit_odds = "3.5:1"
        for suit_code, suit_name in suits:
            if suit_code in ('Club', 'Spade'):
                bg_color = '#2C2C2C'
                fg_color = '#FFFFFF'
                disabled_bg = '#555555'
            else:
                bg_color = '#C62828'
                fg_color = '#FFFFFF'
                disabled_bg = '#8B0000'
            btn = tk.Button(suit_frame,
                            text=f"{suit_odds}\n{suit_name}\n~~",
                            bg=bg_color, fg=fg_color,
                            font=('Arial', 12, 'bold'), height=3, width=9,
                            wraplength=90, disabledforeground='#CCCCCC',
                            highlightthickness=0)
            btn.original_bg = bg_color
            btn.disabled_bg = disabled_bg
            btn.bet_key = f'suit_{suit_code}'
            btn.bet_type = 'suit'
            btn.suit = suit_code
            btn.config(command=lambda t=btn.bet_key, b=btn, s=suit_code: self.place_bet(t, b, suit=s))
            btn.bind('<Button-3>', lambda e, t=btn.bet_key, b=btn: self._on_right_click_clear(e, t, b))
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        misc_frame = tk.Frame(parent, bg='#D0E7FF', height=80)
        misc_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        misc_frame.pack_propagate(False)
        misc_options = [
            ('red', '红色', '#FF0000', '#FFFFFF', '#B30000'),
            ('small', '小(A-7)', '#87CEEB', '#000000', '#6BA3C4'),
            ('big', '大(8-K)', '#FF6B93', '#000000', '#CC5676'),
            ('black', '黑色', '#000000', '#FFFFFF', '#333333')
        ]
        misc_odds = "0.95:1"
        for key, name, bg_color, fg_color, disabled_bg in misc_options:
            btn = tk.Button(misc_frame,
                            text=f"{misc_odds}\n{name}\n~~",
                            bg=bg_color, fg=fg_color,
                            font=('Arial', 12, 'bold'), height=3, width=9,
                            wraplength=90, disabledforeground='#CCCCCC',
                            highlightthickness=0)
            btn.original_bg = bg_color
            btn.disabled_bg = disabled_bg
            btn.bet_key = f'misc_{key}'
            btn.bet_type = 'misc'
            btn.misc_key = key
            btn.config(command=lambda t=btn.bet_key, b=btn, k=key: self.place_bet(t, b, misc_key=k))
            btn.bind('<Button-3>', lambda e, t=btn.bet_key, b=btn: self._on_right_click_clear(e, t, b))
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        shoot_frame = tk.Frame(parent, bg='#D0E7FF', height=80)
        shoot_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        shoot_frame.pack_propagate(False)
        self.shoot_buttons = {}
        shoot_options = [
            ('射中', '#FF0000', '#FFFFFF', '#B30000'),
            ('射偏', '#FFA600', '#000000', '#CC8400'),
            ('撞柱', '#00FFFF', '#000000', '#00CCCC')
        ]
        for bet_name, bg_color, fg_color, disabled_bg in shoot_options:
            btn = tk.Button(shoot_frame,
                            text=f"??:1\n{bet_name}\n~~",
                            bg=bg_color, fg=fg_color,
                            font=('Arial', 12, 'bold'), height=3, width=9,
                            wraplength=90, disabledforeground='#CCCCCC',
                            highlightthickness=0)
            btn.original_bg = bg_color
            btn.disabled_bg = disabled_bg
            btn.bet_key = f'shoot_{bet_name}'
            btn.bet_type = 'shoot'
            btn.shoot_name = bet_name
            btn.config(command=lambda t=btn.bet_key, b=btn, n=bet_name: self.place_bet(t, b, shoot_name=n))
            btn.bind('<Button-3>', lambda e, t=btn.bet_key, b=btn: self._on_right_click_clear(e, t, b))
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)
            self.shoot_buttons[bet_name] = btn

        explanation = "3副标准移除鬼牌的扑克牌，A为最小，K为最大"
        explanation_frame = tk.Frame(parent, bg='#D0E7FF', height=40)
        explanation_frame.pack(fill=tk.BOTH, expand=True, pady=2)
        explanation_frame.pack_propagate(False)
        tk.Label(explanation_frame, text=explanation, font=('Arial', 10), bg='#D0E7FF').pack(expand=True)

    def update_shoot_odds(self):
        if not hasattr(self, 'game') or self.game.diff is None:
            return
        diff = self.game.diff
        odds_mid, odds_miss, odds_hit = self.game.get_odds_for_shoot()
        self.shoot_buttons['撞柱'].config(text=f"{odds_hit:.2f}:1\n撞柱\n~~", state=tk.NORMAL)
        if odds_mid is None:
            self.shoot_buttons['射中'].config(text=f"不可下注\n射中\n~~", state=tk.DISABLED)
        else:
            self.shoot_buttons['射中'].config(text=f"{odds_mid:.2f}:1\n射中\n~~", state=tk.NORMAL)
        if odds_miss is None:
            self.shoot_buttons['射偏'].config(text=f"不可下注\n射偏\n~~", state=tk.DISABLED)
        else:
            self.shoot_buttons['射偏'].config(text=f"{odds_miss:.2f}:1\n射偏\n~~", state=tk.NORMAL)
        self.current_shoot_odds = {'射中': odds_mid, '射偏': odds_miss, '撞柱': odds_hit}

    def clear_single_bet(self, bet_key, btn_widget):
        if str(btn_widget.cget('state')) == 'disabled':
            return
        if bet_key in self.current_bets:
            bet_amount = self.current_bets[bet_key]
            self.balance += bet_amount
            self.current_bet -= bet_amount
            del self.current_bets[bet_key]
            self.update_balance()
            self.current_bet_label.config(text=f"${self.current_bet:,}")
            original_text = btn_widget.cget("text").split('\n')
            new_text = f"{original_text[0]}\n{original_text[1]}\n~~"
            btn_widget.config(text=new_text)

    def _populate_betting_center(self, parent):
        balance_display_frame = tk.Frame(parent, bg='#D0E7FF')
        balance_display_frame.pack(fill=tk.X)
        self.balance_label = tk.Label(balance_display_frame, text=f"余额: ${int(round(self.balance)):,}",
                                      font=('Arial', 22), fg='black', bg='#D0E7FF')
        self.balance_label.pack(side=tk.LEFT)
        self.info_button = tk.Button(balance_display_frame, text="ℹ️", command=self.show_game_instructions,
                                     bg='#4B8BBE', fg='white', font=('Arial', 8))
        self.info_button.pack(side=tk.RIGHT, padx=5)
        self.info_button.bind('<Button-3>', self.show_remaining_cards)

        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=2, pady=2)

        minmax_frame = tk.Frame(parent, bg='#D0E7FF')
        minmax_frame.pack(fill=tk.X)

        table_border_color = "#d70000"
        table_bg = '#f9f9f9'

        outer_frame = tk.Frame(minmax_frame, bg=table_border_color, bd=2, relief=tk.SOLID)
        outer_frame.pack(padx=5, pady=2, fill=tk.X)

        header_frame = tk.Frame(outer_frame, bg=table_border_color)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="花色大小最高", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="射击最高", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)

        content_frame = tk.Frame(outer_frame, bg=table_bg)
        content_frame.pack(fill=tk.X)
        tk.Label(content_frame, text="50,000", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="250,000", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)

        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5, pady=1)

        btn_frame = tk.Frame(parent, bg='#D0E7FF')
        btn_frame.pack(fill=tk.X, pady=2)
        self.reset_button = tk.Button(btn_frame, text="重设金额", command=self.reset_bets,
                                      bg='#ff4444', fg='white', font=('微软雅黑', 16, 'bold'), state=tk.DISABLED,)
        self.reset_button.pack(side=tk.TOP, expand=True, fill=tk.X, padx=10, pady=3)
        self.deal_button = tk.Button(btn_frame, text="开始游戏 (Enter)", command=self.start_game,
                                     bg='gold', fg='black', font=('微软雅黑', 16, 'bold'), state=tk.DISABLED)
        self.deal_button.pack(side=tk.TOP, expand=True, fill=tk.X, padx=10, pady=1)

        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(3, 0), padx=2)

        current_bet_frame = tk.Frame(parent, bg='#D0E7FF')
        current_bet_frame.pack(pady=(0, 1))
        tk.Label(current_bet_frame, text="当前下注:", width=12, font=('微软雅黑', 16), bg='#D0E7FF').pack(side=tk.LEFT)
        self.current_bet_label = tk.Label(current_bet_frame, text="$0", width=10, font=('微软雅黑', 16), bg='#D0E7FF')
        self.current_bet_label.pack(side=tk.RIGHT)

        last_win_frame = tk.Frame(parent, bg='#D0E7FF')
        last_win_frame.pack()
        tk.Label(last_win_frame, text="上局获胜:", width=12, font=('微软雅黑', 16), bg='#D0E7FF').pack(side=tk.LEFT)
        self.last_win_label = tk.Label(last_win_frame, text="$0", width=10, font=('微软雅黑', 16), bg='#D0E7FF')
        self.last_win_label.pack(side=tk.RIGHT)

    def show_remaining_cards(self, event=None):
        SUITS = ['Club', 'Diamond', 'Heart', 'Spade']
        RANKS = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
        remaining_deck = self.game.deck[self.game.cut_position:]
        remaining_cards = {suit: {rank: 0 for rank in RANKS} for suit in SUITS}
        suit_map = {
            '♣': 'Club', '♦': 'Diamond', '♥': 'Heart', '♠': 'Spade',
            'Club': 'Club', 'Diamond': 'Diamond', 'Heart': 'Heart', 'Spade': 'Spade'
        }
        for card in remaining_deck:
            suit, rank = card
            suit_std = suit_map.get(suit, suit)
            if suit_std not in remaining_cards:
                continue
            remaining_cards[suit_std][rank] += 1
        win = tk.Toplevel(self)
        win.title("剩余牌堆统计")
        win.geometry("600x400")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
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
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        total_remaining = len(remaining_deck)
        title_label = tk.Label(main_frame, text=f"剩余{total_remaining}张牌", font=('Arial', 16, 'bold'),
                            bg='#F0F0F0', fg='#333333')
        title_label.pack(pady=(0, 10))
        table_frame = tk.Frame(main_frame, bg='#F0F0F0')
        table_frame.pack(fill=tk.BOTH, expand=True)
        header_frame = tk.Frame(table_frame, bg='#F0F0F0')
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="", width=6, bg='#F0F0F0').pack(side=tk.LEFT, padx=3)
        for rank in RANKS:
            display_rank = 'X' if rank == '10' else rank
            label = tk.Label(header_frame, text=display_rank, width=4, font=('Arial', 10, 'bold'),
                            bg='#F0F0F0', relief=tk.RAISED, bd=1)
            label.pack(side=tk.LEFT, padx=1)
        total_label = tk.Label(header_frame, text="总计", width=4, font=('Arial', 10, 'bold'),
                            bg='#F0F0F0', relief=tk.RAISED, bd=1)
        total_label.pack(side=tk.LEFT, padx=1)
        for suit in SUITS:
            row_frame = tk.Frame(table_frame, bg='#F0F0F0')
            row_frame.pack(fill=tk.X)
            suit_display = {'Club': '梅花', 'Diamond': '方块', 'Heart': '红心', 'Spade': '黑桃'}
            suit_label = tk.Label(row_frame, text=suit_display.get(suit, suit), width=6, font=('Arial', 10, 'bold'),
                                bg='#F0F0F0', relief=tk.RAISED, bd=1)
            suit_label.pack(side=tk.LEFT, padx=1)
            suit_total = 0
            for rank in RANKS:
                count = remaining_cards[suit][rank]
                suit_total += count
                if count == 0:
                    bg_color = '#FFCCCC'
                elif count < 4:
                    bg_color = '#FFFFCC'
                else:
                    bg_color = '#CCFFCC'
                count_label = tk.Label(row_frame, text=str(count), width=4, font=('Arial', 10),
                                    bg=bg_color, relief=tk.SUNKEN, bd=1)
                count_label.pack(side=tk.LEFT, padx=1)
            total_label = tk.Label(row_frame, text=str(suit_total), width=4, font=('Arial', 10, 'bold'),
                                bg='#DDDDDD', relief=tk.RAISED, bd=1)
            total_label.pack(side=tk.LEFT, padx=1)
        separator = tk.Frame(table_frame, height=2, bg='#333333')
        separator.pack(fill=tk.X, pady=5)
        total_row_frame = tk.Frame(table_frame, bg='#F0F0F0')
        total_row_frame.pack(fill=tk.X)
        tk.Label(total_row_frame, text="总计", width=6, font=('Arial', 10, 'bold'),
                bg='#F0F0F0', relief=tk.RAISED, bd=1).pack(side=tk.LEFT, padx=1)
        rank_totals = {}
        for rank in RANKS:
            rank_totals[rank] = 0
            for suit in SUITS:
                rank_totals[rank] += remaining_cards[suit][rank]
        grand_total = 0
        for rank in RANKS:
            total = rank_totals[rank]
            grand_total += total
            if total == 0:
                bg_color = '#FFCCCC'
            elif total < 16:
                bg_color = '#FFFFCC'
            else:
                bg_color = '#CCFFCC'
            total_label = tk.Label(total_row_frame, text=str(total), width=4, font=('Arial', 10, 'bold'),
                                bg=bg_color, relief=tk.RAISED, bd=1)
            total_label.pack(side=tk.LEFT, padx=1)
        grand_total_label = tk.Label(total_row_frame, text=str(grand_total), width=4, font=('Arial', 10, 'bold'),
                                    bg='#CCCCFF', relief=tk.RAISED, bd=1)
        grand_total_label.pack(side=tk.LEFT, padx=1)
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

    def _populate_betting_right(self, parent):
        chips_frame = tk.Frame(parent, bg='#D0E7FF')
        chips_frame.pack(pady=5)
        row1 = tk.Frame(chips_frame, bg='#D0E7FF')
        row1.pack()
        for text, bg_color in [('10', '#ffa500'), ("25", '#00ff00'), ("100", '#000000')]:
            btn = self._create_chip_button(row1, text, bg_color)
            btn.pack(side=tk.LEFT, padx=2)
        row2 = tk.Frame(chips_frame, bg='#D0E7FF')
        row2.pack(pady=3)
        for text, bg_color in [("500", "#FF7DDA"), ("1千", '#ffffff'), ('5千', '#ff0000') ]:
            btn = self._create_chip_button(row2, text, bg_color)
            btn.pack(side=tk.LEFT, padx=2)
        row3 = tk.Frame(chips_frame, bg='#D0E7FF')
        row3.pack(pady=3)
        for text, bg_color in [('1万', '#800080'), ('3万', '#ffa500'), ('5万', '#006400')]:
            btn = self._create_chip_button(row3, text, bg_color)
            btn.pack(side=tk.LEFT, padx=2)
        self._set_default_chip()
        self.current_chip_label = tk.Label(parent, text="筹码: $1,000", font=('Arial', 18), fg='black', bg='#D0E7FF')
        self.current_chip_label.pack(side=tk.LEFT, padx=0)

    def _set_default_chip(self):
        for chip in self.chip_buttons:
            if chip['text'] == '1千':
                chip['canvas'].itemconfig(chip['chip_id'], outline='yellow', width=4)
                self.selected_chip = chip
                self.selected_bet_amount = 1000
                if hasattr(self, 'current_chip_label'):
                    self.current_chip_label.config(text="筹码: $1,000")
                break

    def _setup_bindings(self):
        self.bind('<Return>', lambda e: self.start_game())

    def place_bet(self, bet_key, btn_widget, **kwargs):
        if str(btn_widget.cget('state')) == 'disabled':
            return
        amount = int(self.selected_bet_amount)
        existing = int(self.current_bets.get(bet_key, 0))
        if bet_key.startswith('suit') or bet_key.startswith('misc'):
            limit = 50000
        else:
            limit = 250000
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
        self.current_bets[bet_key] = self.current_bets.get(bet_key, 0) + to_place
        self.update_balance()
        self.current_bet_label.config(text=f"${self.current_bet:,}")
        original_text = btn_widget.cget("text").split('\n')
        top = original_text[0] if len(original_text) >= 1 else ""
        mid = original_text[1] if len(original_text) >= 2 else ""
        new_text = f"{top}\n{mid}\n${self.current_bets[bet_key]:,}"
        btn_widget.config(text=new_text)

    def _on_right_click_clear(self, event, bet_key, btn_widget):
        if str(btn_widget.cget('state')) == 'disabled':
            return
        self.clear_single_bet(bet_key, btn_widget)

    def start_game(self):
        self.game.round_counter += 1
        if self.game.round_counter >= 20 or len(self.game.deck) - self.game.cut_position < 60:
            self._initialize_game(True)
            return
        self.disable_all_buttons()
        self.betting_enabled = False
        self.deal_button.config(state=tk.DISABLED, text="发牌中...")
        self.unbind('<Return>')
        self.after(1000, self._start_shoot_round)

    def _start_shoot_round(self):
        self.game.deal_initial()
        self.update_shoot_odds()
        self.animate_initial_two_cards()

    def animate_initial_two_cards(self):
        self.table_canvas.delete('all')
        self._draw_table_labels()
        self.card_ids = []
        pos0 = self._get_card_positions(0)
        card_id0 = self.table_canvas.create_image(500, 0, image=self.back_image)
        self._animate_card_entrance(card_id0, pos0)
        pos1 = self._get_card_positions(1)
        card_id1 = self.table_canvas.create_image(500, 0, image=self.back_image)
        self._animate_card_entrance(card_id1, pos1)
        self.card_ids = [(0, card_id0), (1, card_id1)]
        self.after(800, self._reveal_first_two_cards)

    def _animate_card_entrance(self, card_id, target_pos):
        start_x, start_y = 500, 0
        def move_step(step=0):
            if step <= 30:
                x = start_x + (target_pos[0]-start_x)*(step/30)
                y = start_y + (target_pos[1]-start_y)*(step/30)
                self.table_canvas.coords(card_id, x, y)
                self.after(10, move_step, step+1)
        move_step()

    def _reveal_first_two_cards(self):
        real_card0 = self.game.first_card
        real_card1 = self.game.second_card
        self._flip_card(self.card_ids[0][1], real_card0, 0, is_third=False)
        self.after(500, lambda: self._flip_card(self.card_ids[1][1], real_card1, 1, is_third=False))
        self.after(1200, self.enable_betting_phase)

    def enable_betting_phase(self):
        for btn in self.bet_buttons:
            if btn.bet_type in ('suit', 'misc', 'shoot'):
                if btn.bet_type == 'shoot':
                    if btn.cget('state') == tk.DISABLED:
                        continue
                btn.config(state=tk.NORMAL, bg=btn.original_bg)
        self.reset_button.config(state=tk.NORMAL)
        self.betting_enabled = True
        self.table_canvas.delete('bet_prompt')
        self.draw_odds_table()
        self.deal_button.config(text="开牌 (Enter)", command=self.reveal_third_card, state=tk.NORMAL)
        self.bind('<Return>', lambda e: self.reveal_third_card())

    def reveal_third_card(self):
        if not self.betting_enabled:
            return
        self.betting_enabled = False
        self.disable_all_buttons()
        self.table_canvas.delete('bet_prompt')
        self.clear_odds_table()
        pos2 = self._get_card_positions(2)
        third_card_id = self.table_canvas.create_image(500, 0, image=self.back_image)
        self._animate_card_entrance(third_card_id, pos2)
        self.after(800, lambda: self._flip_card(third_card_id, self.game.third_card, 2, is_third=True))

    def _normalize_card(self, card):
        suit_map = {
            '♣': 'Club',
            '♦': 'Diamond',
            '♥': 'Heart',
            '♠': 'Spade'
        }
        suit, rank = card
        suit = suit_map.get(suit, suit)
        return (suit, str(rank))
        
    def _flip_card(self, card_id, real_card, seq, is_third=False, step=0):
        steps = 12
        orig_w, orig_h = 120, 170
        card_key = self._normalize_card(real_card)
        if step > steps:
            final_img = self.card_images.get(card_key)
            if final_img is None:
                try:
                    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1')
                    filename = f"{card_key[0]}{card_key[1]}.png"
                    path = os.path.join(card_dir, filename)
                    img = Image.open(path).convert('RGBA').resize((orig_w, orig_h), Image.LANCZOS)
                    final_img = ImageTk.PhotoImage(img)
                    self.card_images[card_key] = final_img
                except Exception as e:
                    print(f"[Shoot] 最后一帧加载正面牌失败: {card_key} → {e}")
                    final_img = self.back_image
            try:
                self.table_canvas.itemconfig(card_id, image=final_img)
            except Exception as e:
                print(f"[Shoot] 最后一帧写回失败: {e}")
            if not hasattr(self, '_temp_flip_images'):
                self._temp_flip_images = {}
            self._temp_flip_images[card_id] = final_img
            if is_third:
                self.after(350, self._play_shot_animation)
            return
        half = steps // 2
        if step <= half:
            ratio = 1 - (step / float(half))
            use_back = True
        else:
            ratio = (step - half) / float(half)
            use_back = False
        w = max(1, int(orig_w * ratio))
        img = self._create_scaled_image(card_key, w, orig_h, use_back=use_back)
        if not hasattr(self, '_temp_flip_images'):
            self._temp_flip_images = {}
        self._temp_flip_images[card_id] = img
        try:
            self.table_canvas.itemconfig(card_id, image=img)
        except Exception:
            pass
        self.after(20, lambda: self._flip_card(card_id, real_card, seq, is_third, step + 1))

    def _build_shot_plan(self):
        """
        根据前三张牌，决定足球的射门路径。
        射偏时：根据第三张牌大于高牌或小于低牌，决定飞向高牌或低牌所在侧的外侧。
        """
        v1 = self.game.card_value(self.game.first_card)
        v2 = self.game.card_value(self.game.second_card)
        v3 = self.game.card_value(self.game.third_card)

        low = min(v1, v2)
        high = max(v1, v2)

        # 第一张牌的位置 x=270，第二张牌的位置 x=730
        left_pos_x = 270
        right_pos_x = 730

        # 判断 low 和 high 分别对应哪一张牌
        low_is_left = (v1 == low)
        high_is_left = (v1 == high)

        start = (500, 385)
        approach_ctrl = (500, 155)

        # 1) 射中：第三张在两者之间
        if low < v3 < high:
            t = (v3 - low) / float(high - low) if high != low else 0.5
            target_x = int(320 + 360 * t)   # 320~680
            target_y = int(205 - 35 * (1 - abs(2 * t - 1)))
            return {
                "kind": "hit",
                "start": start,
                "control": approach_ctrl,
                "end": (target_x, target_y),
            }

        # 2) 撞柱：第三张等于其中一张
        if v3 == v1 or v3 == v2:
            match_is_left = (left_pos_x if v3 == v1 else right_pos_x) < 500
            impact_x = 248 if match_is_left else 752
            impact_y = int(105 + ((v3 - 1) / 12.0) * 150)
            bounce_end_x = 185 if match_is_left else 815
            bounce_end_y = max(85, impact_y - 25)
            bounce_ctrl_x = impact_x - 55 if match_is_left else impact_x + 55
            bounce_ctrl_y = impact_y - 60
            return {
                "kind": "pillar",
                "start": start,
                "control": approach_ctrl,
                "impact": (impact_x, impact_y),
                "bounce_control": (bounce_ctrl_x, bounce_ctrl_y),
                "bounce_end": (bounce_end_x, bounce_end_y),
            }

        # 3) 射偏
        # 根据 v3 与 low/high 的关系决定飞向哪一侧
        if v3 > high:
            # 大于高牌：飞向高牌所在侧的外侧
            if high_is_left:
                # 高牌在左边，球飞向左侧外部
                side = "left"
            else:
                # 高牌在右边，球飞向右侧外部
                side = "right"
        else:  # v3 < low
            # 小于低牌：飞向低牌所在侧的外侧
            if low_is_left:
                side = "left"
            else:
                side = "right"

        # 确定落点坐标范围
        if side == "left":
            # 左侧外部范围 x: 40~250，y 根据 v3 点数映射
            end_x = random.randint(140, 200)
        else:
            # 右侧外部范围 x: 750~900
            end_x = random.randint(800, 860)

        # y 坐标随点数变化（点数越小越靠上，点数越大越靠下）
        end_y = int(75 + ((v3 - 1) / 12.0) * 195)

        return {
            "kind": "miss",
            "start": start,
            "control": approach_ctrl,
            "end": (end_x, end_y),
        }

    def _draw_soccer_ball(self, cx, cy, r, tag='shot_ball', with_shadow=False):
        """
        绘制足球，with_shadow 参数保留用于其他场景，下落动画中阴影由单独方法控制。
        """
        c = self.table_canvas
        c.delete(tag)

        if with_shadow:
            # 简单阴影（保留兼容，但当前不使用）
            shadow_w = r * 1.9
            shadow_h = max(3, r * 0.32)
            c.create_oval(
                cx - shadow_w / 2, cy + r * 0.65,
                cx + shadow_w / 2, cy + r * 0.65 + shadow_h,
                fill='#123b18', outline='', tags=tag
            )

        # 球体主色
        c.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill='#F0F0F0', outline='#111111',
            width=max(1, int(r * 0.1)), tags=tag
        )
        # 左下暗部增加立体感
        c.create_arc(
            cx - r, cy - r, cx + r, cy + r,
            start=180, extent=180, fill='#DDDDDD', outline='', tags=tag
        )

        # 黑色五边形风格
        pts_center = [
            cx, cy - r * 0.42,
            cx + r * 0.38, cy - r * 0.12,
            cx + r * 0.22, cy + r * 0.34,
            cx - r * 0.22, cy + r * 0.34,
            cx - r * 0.38, cy - r * 0.12,
        ]
        c.create_polygon(pts_center, fill='#111111', outline='#333333', width=1, tags=tag)

        c.create_polygon(
            cx - r * 0.72, cy - r * 0.04,
            cx - r * 0.47, cy - r * 0.28,
            cx - r * 0.31, cy - r * 0.02,
            cx - r * 0.45, cy + r * 0.28,
            fill='#111111', outline='#333333', width=1, tags=tag
        )
        c.create_polygon(
            cx + r * 0.72, cy - r * 0.04,
            cx + r * 0.47, cy - r * 0.28,
            cx + r * 0.31, cy - r * 0.02,
            cx + r * 0.45, cy + r * 0.28,
            fill='#111111', outline='#333333', width=1, tags=tag
        )
        c.create_polygon(
            cx, cy + r * 0.72,
            cx + r * 0.25, cy + r * 0.50,
            cx + r * 0.12, cy + r * 0.22,
            cx - r * 0.12, cy + r * 0.22,
            cx - r * 0.25, cy + r * 0.50,
            fill='#111111', outline='#333333', width=1, tags=tag
        )

        # 缝线
        line_width = max(1, int(r * 0.06))
        c.create_line(cx, cy - r * 0.42, cx, cy + r * 0.22,
                      fill='#555555', width=line_width, tags=tag)
        c.create_line(cx - r * 0.35, cy - r * 0.18, cx + r * 0.35, cy - r * 0.18,
                      fill='#555555', width=line_width, tags=tag)
        c.create_line(cx - r * 0.22, cy + r * 0.20, cx + r * 0.22, cy + r * 0.20,
                      fill='#555555', width=line_width, tags=tag)

        # 高光
        highlight_r = r * 0.32
        c.create_oval(
            cx - r * 0.45, cy - r * 0.45,
            cx - r * 0.45 + highlight_r, cy - r * 0.45 + highlight_r,
            fill='#FFFFFF', outline='', tags=tag
        )
        c.create_oval(
            cx - r * 0.58, cy - r * 0.58,
            cx - r * 0.58 + highlight_r * 0.5, cy - r * 0.58 + highlight_r * 0.5,
            fill='#FFFFFF', outline='', tags=tag
        )

    def _play_shot_animation(self):
        """
        第三张牌翻开后播放足球射门动画，射门结束后下落，下落完成后结算。
        """
        self.table_canvas.delete('shot_ball')
        plan = self._build_shot_plan()

        if plan["kind"] == "pillar":
            # 撞柱：先飞向门柱，再弹出，最后下落
            def after_bounce(end_x, end_y, final_r):
                # 弹出动画结束，开始下落
                self._drop_ball_and_settle(end_x, end_y, final_r, self.resolve_bets)

            def do_bounce():
                self._animate_shot_phase(
                    plan["impact"],
                    plan["bounce_control"],
                    plan["bounce_end"],
                    frames=12,
                    start_r=25,
                    end_r=25,
                    on_done=after_bounce
                )

            self._animate_shot_phase(
                plan["start"],
                plan["control"],
                plan["impact"],
                frames=16,
                start_r=60,
                end_r=25,
                on_done=lambda x, y, r: do_bounce()
            )
        else:
            # 射中 / 射偏：直接飞向目标点，然后下落
            def after_shot(end_x, end_y, final_r):
                self._drop_ball_and_settle(end_x, end_y, final_r, self.resolve_bets)

            self._animate_shot_phase(
                plan["start"],
                plan["control"],
                plan["end"],
                frames=22,
                start_r=60,
                end_r=25,
                on_done=after_shot
            )

    def _animate_shot_phase(self, start, control, end, frames=22, start_r=60, end_r=25, on_done=None):
        """
        二次贝塞尔曲线动画，足球半径从 start_r 线性变化到 end_r。
        动画结束时调用 on_done(终点x, 终点y, 最终半径)
        """
        canvas = self.table_canvas

        def step(i=0):
            t = i / float(frames)
            inv = 1.0 - t

            x = inv * inv * start[0] + 2 * inv * t * control[0] + t * t * end[0]
            y = inv * inv * start[1] + 2 * inv * t * control[1] + t * t * end[1]

            r = max(25, start_r + (end_r - start_r) * t)

            canvas.delete('shot_ball')
            # 飞行阶段不画阴影（避免空中阴影）
            self._draw_soccer_ball(x, y, r, tag='shot_ball', with_shadow=False)

            if i < frames:
                self.after(20, step, i + 1)
            else:
                if on_done:
                    on_done(end[0], end[1], r)

        step()

    def _drop_ball_and_settle(self, x, y, r, on_complete):
        """
        足球从当前位置 (x, y) 垂直下落至 y=300，同时阴影从小变大。
        下落完成后足球停留在落地位置，然后调用 on_complete。
        """
        canvas = self.table_canvas
        target_y = 325
        frames = 15
        start_y = y
        start_shadow_scale = 0.2   # 阴影初始很小
        end_shadow_scale = 1.5     # 落地时阴影较大

        def step(i=0):
            t = i / float(frames)
            current_y = start_y + (target_y - start_y) * t
            shadow_scale = start_shadow_scale + (end_shadow_scale - start_shadow_scale) * t
            shadow_w = r * 1.8 * shadow_scale
            shadow_h = max(3, r * 0.32 * shadow_scale)

            canvas.delete('shot_ball')
            # 画阴影（在足球下方）
            shadow_x = x
            shadow_y = current_y + r * 0.65
            canvas.create_oval(
                shadow_x - shadow_w / 2, shadow_y,
                shadow_x + shadow_w / 2, shadow_y + shadow_h,
                fill='#123b18', outline='', tags='shot_ball'
            )
            # 画足球（不带阴影，阴影已单独绘制）
            self._draw_soccer_ball(x, current_y, r, tag='shot_ball', with_shadow=False)

            if i < frames:
                self.after(20, step, i + 1)
            else:
                # 下落完成，足球停留在当前位置，不要删除
                if on_complete:
                    on_complete()

        step()

    def _create_scaled_image(self, card, w, h, use_back=False):
        from PIL import Image, ImageTk
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1')
        try:
            if use_back:
                path = os.path.join(card_dir, 'Background.png')
            else:
                card_key = self._normalize_card(card)
                filename = f"{card_key[0]}{card_key[1]}.png"
                path = os.path.join(card_dir, filename)
            img = Image.open(path).convert('RGBA')
            img = img.resize((max(1, int(w)), int(h)), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"[Shoot] 图片加载失败: {card} → {e}")
            return self.back_image

    def resolve_bets(self):
        payouts = 0
        for bet_key, bet_amount in self.current_bets.items():
            if bet_key.startswith('suit'):
                expected_suit = bet_key.split('_')[1]
                if self.game.third_card[0] == expected_suit:
                    payouts += bet_amount * (1 + 3.5)
            elif bet_key.startswith('misc'):
                key = bet_key.split('_')[1]
                if key == 'red':
                    if self.game.third_card[0] in ('Diamond', 'Heart'):
                        payouts += bet_amount * (1 + 0.95)
                elif key == 'black':
                    if self.game.third_card[0] in ('Club', 'Spade'):
                        payouts += bet_amount * (1 + 0.95)
                elif key == 'small':
                    val = self.game.card_value(self.game.third_card)
                    if 1 <= val <= 7:
                        payouts += bet_amount * (1 + 0.95)
                elif key == 'big':
                    val = self.game.card_value(self.game.third_card)
                    if 8 <= val <= 13:
                        payouts += bet_amount * (1 + 0.95)
            elif bet_key.startswith('shoot'):
                shoot_name = bet_key.split('_')[1]
                if shoot_name == self.game.result:
                    odds = self.current_shoot_odds[shoot_name]
                    if odds is not None:
                        payouts += bet_amount * (1 + odds)
        self.balance += payouts
        self.current_bets.clear()
        self.current_bet = 0
        self.update_balance()
        self.current_bet_label.config(text="$0")
        self.last_win = int(payouts)
        self.last_win_label.config(text=f"${max(self.last_win, 0):,}")
        for btn in self.bet_buttons:
            if hasattr(btn, 'bet_key'):
                original_text = btn.cget("text").split('\n')
                new_text = f"{original_text[0]}\n{original_text[1]}\n~~"
                btn.config(text=new_text)
        self._show_result_text()
        self.add_marker_result(self.game.result)
        self.after(2000, self.clear_table_and_prepare_next)

    def clear_table_and_prepare_next(self):
        self.table_canvas.delete('all')
        self._draw_table_labels()
        self.betting_enabled = False
        self.clear_odds_table()
        if self.game.round_counter >= 20 or len(self.game.deck) - self.game.cut_position < 60:
            self.deal_button.config(state=tk.DISABLED, text="发牌中...")
            self.after(1000, lambda: self._initialize_game(True))
            return
        self.deal_button.config(state=tk.DISABLED, text="发牌中...")
        self.disable_all_buttons()
        self.after(1000, self._start_shoot_round)

    def _show_result_text(self):
        text = ""
        text_color = "white"
        bg_color = "#35654d"
        if self.game.result == '射中':
            text = "射中！"
            text_color = "#FFFFFF"
            bg_color = '#FF0000'
        elif self.game.result == '射偏':
            text = "射偏！"
            text_color = "#000000"
            bg_color = '#FFA600'
        else:
            text = "撞柱！"
            text_color = "#000000"
            bg_color = '#00FFFF'
        try:
            self.table_canvas.itemconfig(self.result_text_id, text=text, fill=text_color)
        except Exception:
            pass
        try:
            self.table_canvas.update_idletasks()
            text_bbox = self.table_canvas.bbox(self.result_text_id)
            if text_bbox:
                padding = 15
                expanded_bbox = (text_bbox[0]-padding, text_bbox[1]-padding, text_bbox[2]+padding, text_bbox[3]+padding)
                self.table_canvas.coords(self.result_bg_id, expanded_bbox)
                self.table_canvas.itemconfig(self.result_bg_id, fill=bg_color, outline=bg_color)
                self.table_canvas.tag_raise(self.result_text_id)
                self.table_canvas.tag_lower(self.result_bg_id)
        except Exception:
            pass

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${int(round(self.balance)):,}")
        update_balance_in_json(self.username, self.balance)

    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("射龙门游戏说明")
        win.geometry("600x400")
        win.resizable(False, False)
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
        text_frame = tk.Frame(win)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        instructions = """
射龙门游戏规则：

1. 游戏发三张牌：第一张、第二张、第三张。
2. 先翻开第一张和第二张牌，玩家根据这两张牌的点数差下注第三张牌的结果。
3. 下注选项：
   - 花色：猜第三张牌的花色（梅花、方块、红心、黑桃），赔率3.5:1
   - 红/黑/小/大：红色（红心/方块）、黑色（梅花/黑桃）、小(A-7)、大(8-K)，赔率0.95:1
   - 射中/射偏/撞柱：根据前两张牌差值决定赔率（详见流动赔率表）
4. 流动赔率：
   差值0：撞柱13.5，射偏0.1，射中不可下注
   差值1：撞柱5.6，射偏0.1，射中不可下注
   差值2：撞柱5.6，射中11，射偏0.2
   差值3：撞柱5.6，射中5，射偏0.35
   差值4：撞柱5.6，射中3，射偏0.5
   差值5：撞柱5.6，射中2，射偏0.75
   差值6：撞柱5.6，射中1.5，射偏1
   差值7：撞柱5.6，射中1，射偏1.5
   差值8：撞柱5.6，射中0.75，射偏2
   差值9：撞柱5.6，射中0.5，射偏3
   差值10：撞柱5.6，射中0.35，射偏5
   差值11：撞柱5.6，射中0.2，射偏11
   差值12：撞柱5.6，射中0.1，射偏不可下注
5. 每20局重新洗牌，切牌范围15-140。
        """
        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=('Arial', 12), padx=10, pady=10)
        text_widget.insert(tk.END, instructions)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True)
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

def main(initial_balance=1000000, username="Guest"):
    app = ShootDragonGateGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")