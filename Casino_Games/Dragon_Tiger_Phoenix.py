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

class DragonTigerPhoenixGame:
    def __init__(self, decks=8, external_deck=None):
        if external_deck:
            self.deck = [(card['suit'], card['rank']) for card in external_deck]
        else:
            self.deck = self.create_deck(decks)
            random.shuffle(self.deck)

        self.dragon_hand = []
        self.tiger_hand = []
        self.phoenix_hand = []
        self.dragon_score = 0
        self.tiger_score = 0
        self.phoenix_score = 0
        self.outcome = None
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
        deduct_map = {
            'A':1, 'J':10, 'Q':10, 'K':10,
            '10':10, '2':2, '3':3, '4':4, '5':5,
            '6':6, '7':7, '8':8, '9':9
        }
        deduct = deduct_map.get(first_card[1], 0)
        end_pos = (1 + deduct) % self.total_cards
        self.deck = self.deck[end_pos:] + self.deck[:end_pos]
        self.used_cards = random.randint(28, 48)
        self.cut_position = 0

    def card_value(self, card):
        rank = card[1]
        value_map = {
            'A':1, '2':2, '3':3, '4':4, '5':5, '6':6, '7':7,
            '8':8, '9':9, '10':10, 'J':11, 'Q':12, 'K':13
        }
        return value_map.get(rank, 0)

    def deal_initial(self):
        indices = [(self.cut_position + i) % self.total_cards for i in range(3)]
        self.dragon_hand = [self.deck[indices[0]]]
        self.tiger_hand = [self.deck[indices[1]]]
        self.phoenix_hand = [self.deck[indices[2]]]
        self.cut_position = (self.cut_position + 3) % self.total_cards

    def calculate_score(self, hand):
        if hand:
            return self.card_value(hand[0])
        return 0

    def play_game(self):
        self.deal_initial()
        self.dragon_score = self.calculate_score(self.dragon_hand)
        self.tiger_score = self.calculate_score(self.tiger_hand)
        self.phoenix_score = self.calculate_score(self.phoenix_hand)

        scores = {
            'Dragon': self.dragon_score,
            'Tiger': self.tiger_score,
            'Phoenix': self.phoenix_score
        }
        max_score = max(scores.values())
        winners = [hand for hand, score in scores.items() if score == max_score]
        num_winners = len(winners)

        if num_winners == 1:
            self.outcome = {'type': 'single', 'winner': winners[0]}
        elif num_winners == 2:
            self.outcome = {'type': 'two_tie', 'tied_hands': winners}
        else:  # num_winners == 3
            self.outcome = {'type': 'three_tie'}

class DragonTigerPhoenixGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("龙虎凤")
        self.geometry("1350x700+50+10")
        self.configure(bg='#35654d')

        self.bet_buttons = []
        self.selected_chip = None
        self.chip_buttons = []
        self.result_text_id = None
        self.result_bg_id = None

        self.game_mode = "dragontigerphoenix"
        self.game = DragonTigerPhoenixGame()
        self.balance = initial_balance
        self.current_bets = {}
        self.card_images = {}

        self.current_streak = 0
        self.current_streak_type = None
        self.longest_streaks = {
            'Dragon': 0, 'Tiger': 0, 'Phoenix': 0,
            'two_tie': 0, 'three_tie': 0
        }

        self.stats_counts = {
            'Dragon': 0, 'Tiger': 0, 'Phoenix': 0,
            'two_tie': 0, 'three_tie': 0
        }

        self.marker_results = []
        self.marker_counts = {
            'Dragon': 0, 'Tiger': 0, 'Phoenix': 0,
            'two_tie': 0, 'three_tie': 0
        }
        self.max_marker_rows = 6
        self.max_marker_cols = 9
        self.view_mode = "marker"
        self.bigroad_results = []
        self._max_rows = 6
        self._max_cols = 150
        self._bigroad_occupancy = [[False]*self._max_cols for _ in range(self._max_rows)]

        self._load_assets()
        self._create_widgets()
        self._setup_bindings()
        self.point_labels = {}
        # 调整扑克牌区域位置：龙左，虎中，凤右
        self._dragon_area = (310, 150, 310, 350)      # 中心约250
        self._tiger_area = (560, 150, 560, 350)       # 中心500
        self._phoenix_area = (810, 150, 810, 350)     # 中心750
        self.selected_bet_amount = 1000
        self.current_bet = 0
        self.last_win = 0
        self.username = username
        self.protocol("WM_DELETE_WINDOW", self.on_close)

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
        self.deal_button.config(state=tk.NORMAL)
        self.reset_button.config(state=tk.NORMAL)
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
        ranks = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']

        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1')

        for suit in suits:
            for rank in ranks:
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

        try:
            self.window.protocol("WM_DELETE_WINDOW", self.do_nothing)
        except Exception:
            pass

        if second:
            tk.Label(dialog, text="牌靴已经用完 \n请老板切牌 切牌位置在103-299之间",
                    font=('微软雅黑', 10)).pack(pady=(8, 4))
        else:
            tk.Label(dialog, text="请老板切牌 切牌位置在103-299之间",
                    font=('微软雅黑', 10)).pack(pady=(8, 4))

        entry_frame = tk.Frame(dialog)
        entry_frame.pack(pady=(2, 6))

        tk.Label(entry_frame, text="切牌位置:", font=('微软雅黑', 10)).pack(side=tk.LEFT, padx=(6, 8))

        entry_var = tk.StringVar()
        entry = tk.Entry(entry_frame, font=('Arial', 12), width=8, textvariable=entry_var)
        entry.pack(side=tk.LEFT)
        entry.focus_set()

        scale_var = tk.IntVar(value=200)
        scale = tk.Scale(dialog, from_=103, to=299, orient=tk.HORIZONTAL, length=240,
                        variable=scale_var, showvalue=False)
        scale.pack(pady=(4, 4))

        result = [None]
        self.bigroad_results = []

        def on_scale_change(v):
            try:
                vi = int(float(v))
            except Exception:
                return
            entry_var.set(str(vi))
        scale.configure(command=on_scale_change)

        def on_entry_change(event=None):
            s = entry_var.get().strip()
            if s == "":
                return
            try:
                v = int(s)
            except Exception:
                return
        entry.bind('<KeyRelease>', on_entry_change)

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
                if v < 103:
                    v = 103
                elif v > 299:
                    v = 299
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
                    external_deck = shuffle_mod.generate_shuffled_deck(has_joker=False, deck_count=8)
                    if isinstance(external_deck, (list, tuple)):
                        total_cards = len(external_deck)
                        lower = 103
                        upper = min(299, total_cards - 1)
                        if upper >= lower:
                            external_cut_position = int(_secrets.randbelow(upper - lower + 1)) + lower
                        else:
                            external_cut_position = min(max(total_cards // 2, lower), max(lower, total_cards - 1))
                    else:
                        external_deck = None
                        external_cut_position = None
                except Exception as e:
                    print(f"调用 shuffle.generate_shuffled_deck 出错: {e}")
                    external_deck = None
                    external_cut_position = None
            else:
                print("无法加载 shuffle.py 模块")
        except Exception as e:
            print(f"载入 shuffle.py 时出错: {e}")
            external_deck = None
            external_cut_position = None

        if cut_position is None:
            if external_cut_position is not None and 103 <= external_cut_position <= 299:
                cut_position = external_cut_position
            else:
                cut_position = random.randint(103, 299)

        self.game = DragonTigerPhoenixGame(external_deck=external_deck)
        self.game.advanced_shuffle(cut_position)

        self.marker_results = []
        self.marker_counts = {
            'Dragon':0, 'Tiger':0, 'Phoenix':0, 'two_tie':0, 'three_tie':0
        }
        self.stats_counts = {
            'Dragon':0, 'Tiger':0, 'Phoenix':0, 'two_tie':0, 'three_tie':0
        }
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
                try:
                    self.table_canvas.itemconfig(card_id, image=self.card_images[card])
                except Exception:
                    pass
                deduct_map = {
                    'A':1, 'J':10, 'Q':10, 'K':10,
                    '10':10, '2':2, '3':3, '4':4, '5':5,
                    '6':6, '7':7, '8':8, '9':9
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
            img = self._create_scaled_image(card, w, orig_h, use_back=use_back)
            if not hasattr(self, '_temp_flip_images'):
                self._temp_flip_images = {}
            self._temp_flip_images[card_id] = img
            try:
                self.table_canvas.itemconfig(card_id, image=img)
            except Exception:
                pass
            self.after(20, lambda: flip_step(step+1))
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

    def do_nothing(self):
        pass

    def reset_bigroad(self):
        self.bigroad_results.clear()
        self._bigroad_occupancy = [
            [False] * self._max_cols for _ in range(self._max_rows)
        ]
        if hasattr(self, 'bigroad_canvas'):
            self.bigroad_canvas.delete('data')

    def _create_stats_display(self, parent):
        self.stats_frame = tk.Frame(parent, bg='#D0E7FF', height=200)
        self.stats_frame.pack(fill=tk.X, pady=(0,0))
        self.stats_frame.pack_propagate(False)

        title_label = tk.Label(
            self.stats_frame,
            text="统计结果",
            font=('Arial', 16, 'bold'),
            bg='#D0E7FF',
            fg='#000000'
        )
        title_label.pack(pady=(3,0))

        table_frame = tk.Frame(self.stats_frame, bg='#D0E7FF')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

        headers = ['赢家', '图标', '数量']
        for i, header in enumerate(headers):
            header_label = tk.Label(
                table_frame,
                text=header,
                font=('Arial', 12, 'bold'),
                bg='#4B8BBE',
                fg='white',
                width=12,
                height=1,
                relief=tk.RAISED,
                bd=2
            )
            header_label.grid(row=0, column=i, padx=1, pady=1, sticky='nsew')

        stats_items = [
            {'key':'dragon', 'text':'龙', 'color':'#FF0000', 'icon_text':'龙', 'text_color':'white'},
            {'key':'tiger', 'text':'虎', 'color':'#FFA600', 'icon_text':'虎', 'text_color':'black'},
            {'key':'phoenix', 'text':'凤', 'color':'#007BFF', 'icon_text':'凤', 'text_color':'white'},
            {'key':'two_tie', 'text':'两家和', 'color':'#00FF00', 'icon_text':'和', 'text_color':'black'},
            {'key':'three_tie', 'text':'三家和', 'color':'#FFFFFF', 'icon_text':'和', 'text_color':'black'}
        ]

        self.stats_rows = {}
        for row_idx, item in enumerate(stats_items, 1):
            name_label = tk.Label(
                table_frame,
                text=item['text'],
                font=('Arial', 12),
                bg='#FFFFFF',
                fg='#000000',
                width=10,
                height=1,
                relief=tk.RIDGE,
                bd=1
            )
            name_label.grid(row=row_idx, column=0, padx=1, pady=1, sticky='nsew')

            icon_frame = tk.Frame(table_frame, bg='#FFFFFF', width=40, height=30)
            icon_frame.grid(row=row_idx, column=1, padx=1, pady=1, sticky='nsew')
            icon_frame.grid_propagate(False)

            icon_canvas = tk.Canvas(
                icon_frame,
                width=22,
                height=22,
                bg='#FFFFFF',
                highlightthickness=0
            )
            icon_canvas.place(relx=0.5, rely=0.5, anchor='center')

            center_x, center_y = 11, 11
            radius = 8
            icon_canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill=item['color'],
                outline='#000000',
                width=1
            )
            icon_canvas.create_text(
                center_x, center_y,
                text=item['icon_text'],
                fill=item['text_color'],
                font=('Arial', 8, 'bold')
            )

            count_label = tk.Label(
                table_frame,
                text="0",
                font=('Arial', 12, 'bold'),
                bg='#FFFFFF',
                fg='#000000',
                width=6,
                height=1,
                relief=tk.RIDGE,
                bd=1
            )
            count_label.grid(row=row_idx, column=2, padx=1, pady=1, sticky='nsew')

            self.stats_rows[item['key']] = {
                'name_label': name_label,
                'icon_canvas': icon_canvas,
                'count_label': count_label
            }

        for i in range(3):
            table_frame.columnconfigure(i, weight=1)
        for i in range(6):
            table_frame.rowconfigure(i, weight=1, minsize=25)

    def reset_marker_road(self):
        self.marker_results = []
        self.stats_counts = {
            'Dragon':0, 'Tiger':0, 'Phoenix':0, 'two_tie':0, 'three_tie':0
        }
        self.marker_counts = {
            'Dragon':0, 'Tiger':0, 'Phoenix':0, 'two_tie':0, 'three_tie':0
        }
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

    def _draw_table_labels(self):
        # 清除原有内容
        self.table_canvas.delete('all')
        # 绘制分割线：在龙与虎之间，虎与凤之间
        self.table_canvas.create_line(375, 50, 375, 350, width=3, fill='white', tags='divider')
        self.table_canvas.create_line(625, 50, 625, 350, width=3, fill='white', tags='divider')
        # 标签：龙左，虎中，凤右
        self.table_canvas.create_text(250, 30, text="龙", font=('Arial', 30, 'bold'), fill='white')
        self.table_canvas.create_text(500, 30, text="虎", font=('Arial', 30, 'bold'), fill='white')
        self.table_canvas.create_text(750, 30, text="凤", font=('Arial', 30, 'bold'), fill='white')

        self.result_text_id = self.table_canvas.create_text(
            500, 370,
            text="",
            font=('Arial', 34, 'bold'),
            fill='white',
            tags=('result_text')
        )
        self.result_bg_id = self.table_canvas.create_rectangle(
            0,0,0,0,
            fill='',
            outline='',
            tags=('result_bg')
        )

    def _get_card_positions(self, hand_type):
        if hand_type == "dragon":
            area = self._dragon_area
        elif hand_type == "tiger":
            area = self._tiger_area
        else:  # phoenix
            area = self._phoenix_area
        hand = getattr(self.game, hand_type + '_hand', [])
        card_count = len(hand)
        base_x = area[0] + (area[2]-area[0]-120)/2
        positions = []
        for i in range(card_count):
            x = base_x + i*120
            y = area[1]
            positions.append((int(round(x)), int(round(y))))
        return positions

    def _create_chip_button(self, parent, text, bg_color):
        size = 60
        canvas = tk.Canvas(parent, width=size, height=size,
                        highlightthickness=0, background='#D0E7FF')
        chip_id = canvas.create_oval(2,2, size-2, size-2,
                                    fill=bg_color, outline='', width=0)
        rgb = ImageColor.getrgb(bg_color)
        luminance = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2]
        text_color = 'white' if luminance < 140 else 'black'
        canvas.create_text(size/2, size/2, text=text,
                        fill=text_color, font=('Arial', 16, 'bold'))
        canvas.bind('<Button-1>', lambda e, t=text, c=canvas, cid=chip_id: self._set_bet_amount(t, c, cid))
        self.chip_buttons.append({
            'canvas': canvas,
            'chip_id': chip_id,
            'text': text
        })
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
                self.selected_canvas = chip['canvas']
                self.selected_id = chip['chip_id']
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
            if hasattr(btn, 'bet_type'):
                original_text = btn.cget("text").split('\n')
                new_text = f"{original_text[0]}\n{original_text[1]}\n~~"
                btn.config(text=new_text)

    def _create_control_panel(self, parent):
        control_frame = tk.Frame(parent, bg='#D0E7FF', width=300)
        control_frame.pack(pady=12, padx=10, fill=tk.BOTH, expand=True)
        control_frame.pack_propagate(False)

        self.view_container = tk.Frame(control_frame, bg='#D0E7FF', height=300)
        self.view_container.pack(fill=tk.BOTH, expand=True, pady=(0,10))
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
        try:
            self.bigroad_results.clear()
        except Exception:
            pass
        self.bigroad_results = []
        self._max_rows = 6
        self._max_cols = 150
        self._bigroad_occupancy = [[False]*self._max_cols for _ in range(self._max_rows)]

        cell = 25
        pad = 2
        label_w = 30
        label_h = 20
        total_w = label_w + self._max_cols * (cell + pad) + pad
        total_h = label_h + self._max_rows * (cell + pad) + pad

        marker_frame = tk.Frame(self.marker_view, bg='#D0E7FF')
        marker_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

        self._create_stats_display(marker_frame)

        big_title = tk.Label(
            marker_frame,
            text="大路",
            font=('Arial', 14, 'bold'),
            bg='#D0E7FF'
        )
        big_title.pack(pady=(0,2))

        big_frame = tk.Frame(marker_frame, bg='#D0E7FF')
        big_frame.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)

        hbar = tk.Scrollbar(big_frame, orient=tk.HORIZONTAL)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.bigroad_canvas = tk.Canvas(
            big_frame,
            bg='#FFFFFF',
            width=290,
            height=total_h,
            xscrollcommand=hbar.set,
            scrollregion=(0,0,total_w,total_h),
            highlightthickness=0
        )
        self.bigroad_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        hbar.config(command=self.bigroad_canvas.xview)

        for c in range(self._max_cols):
            x = label_w + pad + c * (cell + pad) + cell/2
            y = label_h/2
            self.bigroad_canvas.create_text(x, y, text=str(c+1), font=('Arial',8), tags=('grid',))
        for r in range(self._max_rows):
            x = label_w/2
            y = label_h + pad + r * (cell + pad) + cell/2
            self.bigroad_canvas.create_text(x, y, text=str(r+1), font=('Arial',8), tags=('grid',))
        for c in range(self._max_cols):
            for r in range(self._max_rows):
                x1 = label_w + pad + c * (cell + pad)
                y1 = label_h + pad + r * (cell + pad)
                x2 = x1 + cell
                y2 = y1 + cell
                self.bigroad_canvas.create_rectangle(x1,y1,x2,y2, outline='#888888', fill='#FFFFFF', tags=('grid',))

        marker_title = tk.Label(marker_frame, text="标记路", font=('Arial',14,'bold'), bg='#D0E7FF')
        marker_title.pack(pady=(6,4))

        self.marker_canvas = tk.Canvas(marker_frame, bg='#D0E7FF', highlightthickness=0)
        self.marker_canvas.pack(fill=tk.BOTH, expand=True, padx=3, pady=(0,0))

    def _update_bigroad(self):
        """按照百家乐大路规则绘制：连续相同的结果在同一列向下，结果改变则新起一列；列满（6行）时相同结果新起一列继续向下。
           同时绘制连线：向下连竖线，向右连横线，颜色与获胜方相同（Tie用绿色）。"""
        if not hasattr(self, 'bigroad_canvas'):
            return

        cell = 25
        pad = 2
        label_w = 32
        label_h = 22
        max_rows = self._max_rows  # 6

        self.bigroad_canvas.delete('data')

        # 辅助函数：根据行列获取中心坐标
        def center_of(r, c):
            x1 = label_w + c * (cell + pad)
            y1 = label_h + r * (cell + pad)
            cx = x1 + cell / 2
            cy = y1 + cell / 2
            return cx, cy

        # 绘制单个赢家的圆
        def draw_single(r, c, winner):
            cx, cy = center_of(r, c)
            radius = cell * 0.4
            color_map = {'Dragon': '#FF0000', 'Tiger': '#FFA600', 'Phoenix': '#007BFF'}
            color = color_map[winner]
            self.bigroad_canvas.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                fill=color, outline='', tags=('data', 'circle')
            )
            return cx, cy, radius

        # 绘制二家和：两个半圆，中间写绿色“和”
        def draw_two_tie(r, c, hands):
            cx, cy = center_of(r, c)
            radius = cell * 0.4
            colors = [{'Dragon': '#FF0000', 'Tiger': '#FFA600', 'Phoenix': '#007BFF'}[h] for h in hands]
            # 两个半圆，角度从0到180，180到360
            self.bigroad_canvas.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=0, extent=180, fill=colors[0], outline='', tags=('data', 'circle')
            )
            self.bigroad_canvas.create_arc(
                cx - radius, cy - radius, cx + radius, cy + radius,
                start=180, extent=180, fill=colors[1], outline='', tags=('data', 'circle')
            )
            self.bigroad_canvas.create_text(
                cx, cy, text="和", fill='#00FF00', font=('Arial', 10, 'bold'), tags=('data', 'text')
            )
            return cx, cy, radius

        # 绘制三家和：三个120°扇形，中间写白色“和”
        def draw_three_tie(r, c):
            cx, cy = center_of(r, c)
            radius = cell * 0.4
            colors = ['#FF0000', '#FFA600', '#007BFF']
            angles = [0, 120, 240, 360]
            for i in range(3):
                self.bigroad_canvas.create_arc(
                    cx - radius, cy - radius, cx + radius, cy + radius,
                    start=angles[i], extent=120, fill=colors[i], outline='', tags=('data', 'circle')
                )
            self.bigroad_canvas.create_text(
                cx, cy, text="和", fill='#FFFFFF', font=('Arial', 10, 'bold'), tags=('data', 'text')
            )
            return cx, cy, radius

        if not self.bigroad_results:
            return

        # 当前列和当前行
        cur_col = 0
        cur_row = 0
        prev_road_type = None
        prev_row = None
        prev_col = None
        prev_center = None
        prev_radius = None

        for idx, res in enumerate(self.bigroad_results):
            # 生成用于连续性判断的 road_type
            if res['type'] == 'single':
                road_type = ('single', res['winner'])
            elif res['type'] == 'two_tie':
                # 将两家排序以保证顺序一致
                hands = sorted(res['tied_hands'])
                road_type = ('two_tie', tuple(hands))
            elif res['type'] == 'three_tie':
                road_type = ('three_tie',)
            else:
                road_type = None

            if idx == 0:
                # 第一个结果放在(0,0)
                cur_col, cur_row = 0, 0
            else:
                # 判断是否与上一个相同
                if road_type == prev_road_type:
                    # 相同：尝试向下
                    if cur_row + 1 < max_rows:
                        cur_row += 1
                    else:
                        # 已满，新起一列
                        cur_col += 1
                        cur_row = 0
                else:
                    # 不同，新起一列
                    cur_col += 1
                    cur_row = 0

            # 绘制当前结果，并获取圆心坐标和半径
            if res['type'] == 'single':
                cx, cy, radius = draw_single(cur_row, cur_col, res['winner'])
            elif res['type'] == 'two_tie':
                cx, cy, radius = draw_two_tie(cur_row, cur_col, res['tied_hands'])
            elif res['type'] == 'three_tie':
                cx, cy, radius = draw_three_tie(cur_row, cur_col)
            else:
                continue

            # 如果与上一个结果相同，绘制连线
            if prev_road_type is not None and road_type == prev_road_type:
                # 确定连线颜色
                if res['type'] == 'single':
                    color_map = {'Dragon': '#FF0000', 'Tiger': '#FFA600', 'Phoenix': '#007BFF'}
                    line_color = color_map[res['winner']]
                else:
                    line_color = '#00FF00'  # 绿色用于 Tie

                # 判断相对位置
                if cur_col == prev_col and cur_row == prev_row + 1:
                    # 向下：从 prev 底部到当前顶部
                    start_x, start_y = prev_cx, prev_cy + prev_radius
                    end_x, end_y = cx, cy - radius
                    self.bigroad_canvas.create_line(
                        start_x, start_y, end_x, end_y,
                        fill=line_color, width=3, tags=('data', 'line')
                    )
                elif cur_col == prev_col + 1 and cur_row == 0:
                    # 向右（新列）：从 prev 右侧到当前左侧
                    start_x, start_y = prev_cx + prev_radius, prev_cy
                    end_x, end_y = cx - radius, cy
                    self.bigroad_canvas.create_line(
                        start_x, start_y, end_x, end_y,
                        fill=line_color, width=3, tags=('data', 'line')
                    )
                # 其他情况（理论上不会出现）忽略

            # 更新前一个结果信息
            prev_road_type = road_type
            prev_row, prev_col = cur_row, cur_col
            prev_cx, prev_cy, prev_radius = cx, cy, radius

        # 调整滚动区域
        self.bigroad_canvas.configure(scrollregion=self.bigroad_canvas.bbox('all'))

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
        except Exception:
            pass
        try:
            self._bigroad_key_scroll_units = 5
        except Exception:
            pass
        canvas.bind("<KeyPress-Left>", lambda e: self._on_bigroad_key(e, canvas))
        canvas.bind("<KeyPress-Right>", lambda e: self._on_bigroad_key(e, canvas))
        canvas.bind("<Button-1>", lambda e: canvas.focus_set())
        canvas.bind("<Enter>", lambda e: canvas.focus_set())

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

    def disable_bigroad_mouse_navigation(self, debug=False):
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

    def _create_stats_panel(self, parent):
        stats_frame = tk.Frame(parent, bg='#D0E7FF')
        stats_frame.pack(fill=tk.BOTH, expand=True, pady=(10,0), padx=10)
        ttk.Separator(stats_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(10,10))

    def _update_stats_display(self):
        if hasattr(self, 'stats_rows'):
            mapping = {
                'Dragon': 'dragon',
                'Tiger': 'tiger',
                'Phoenix': 'phoenix',
                'two_tie': 'two_tie',
                'three_tie': 'three_tie'
            }
            for key, display_key in mapping.items():
                if display_key in self.stats_rows:
                    count = self.stats_counts.get(key, 0)
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
                self.marker_canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline='#888888',
                    fill='#D0E7FF'
                )

    def add_marker_result(self, result_dict):
        if result_dict['type'] == 'single':
            marker_type = result_dict['winner']
        elif result_dict['type'] == 'two_tie':
            marker_type = 'two_tie'
        elif result_dict['type'] == 'three_tie':
            marker_type = 'three_tie'
        else:
            return

        if len(self.marker_results) >= self.max_marker_rows * self.max_marker_cols:
            for _ in range(self.max_marker_rows):
                if self.marker_results:
                    self.marker_results.pop(0)

        self.marker_results.append(marker_type)
        self.marker_counts[marker_type] = self.marker_counts.get(marker_type,0) + 1
        self.stats_counts[marker_type] = self.stats_counts.get(marker_type,0) + 1

        self.bigroad_results.append(result_dict)
        self._update_bigroad()

        self._update_stats_display()
        self._update_marker_road()

    def _update_marker_road(self):
        self.marker_canvas.delete('dot')
        rows, cols = 6, 9
        cell_size = 30
        padding = 0
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
            center_x = (x1 + x2)/2
            center_y = (y1 + y2)/2
            radius = cell_size * 0.4

            if result == 'Dragon':
                color = "#FF0000"
                text = "龙"
                text_color = 'white'
            elif result == 'Tiger':
                color = "#FFA600"
                text = "虎"
                text_color = 'black'
            elif result == 'Phoenix':
                color = "#007BFF"
                text = "凤"
                text_color = 'white'
            elif result == 'two_tie':
                color = "#00FF00"
                text = "和"
                text_color = 'black'
            elif result == 'three_tie':
                color = "#FFFFFF"
                text = "和"
                text_color = 'black'
            else:
                continue

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
        self.betting_left = left
        self.betting_center = center
        self.betting_right = right

        self._populate_betting_left(left)
        self._populate_betting_center(center)
        self._populate_betting_right(right)

    def _populate_betting_left(self, parent):
        bet_display_map = {
            'DiamondFlush': '方片同花',
            'ClubFlush': '梅花同花',
            'HeartFlush': '红心同花',
            'SpadeFlush': '黑桃同花',
            'TripleRed': '三红',
            'Flush': '同花',
            'Tie': '平局',
            'TripleBlack': '三黑',
            'Dragon': '龙',
            'Tiger': '虎',
            'Phoenix': '凤'
        }

        odds_map = {
            'DiamondFlush': ('60:1', '#B0E0E6', 'black', '#8FB0C0'),
            'ClubFlush':    ('60:1', '#228B22', 'white', '#1B6B1B'),
            'HeartFlush':   ('60:1', '#FF69B4', 'black', '#CC5490'),
            'SpadeFlush':   ('60:1', '#000000', 'white', '#333333'),
            'TripleRed':    ('3:1', '#FF0000', 'white', '#CC0000'),
            'Flush':        ('12:1', '#800080', 'white', '#660066'),
            'Tie':          ('7:1/20:1', '#00FF00', 'black', '#00CC00'),
            'TripleBlack':  ('3:1', '#000000', 'white', '#333333'),
            'Dragon':       ('1.8:1', '#FF0000', 'white', '#CC0000'),
            'Tiger':        ('1.8:1', '#FFA600', 'black', '#CC8400'),
            'Phoenix':      ('1.8:1', '#007BFF', 'white', '#0066CC')
        }

        row1_frame = tk.Frame(parent, bg='#D0E7FF', height=80)
        row1_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row1_frame.pack_propagate(False)
        buttons_1 = ['DiamondFlush','ClubFlush','HeartFlush','SpadeFlush']
        for bt in buttons_1:
            odds, bg, fg, disabled = odds_map[bt]
            display = bet_display_map[bt]
            btn = tk.Button(
                row1_frame,
                text=f"{odds}\n{display}\n~~",
                bg=bg, fg=fg,
                font=('Arial', 10, 'bold'),
                height=3, width=10,
                wraplength=80,
                disabledforeground=fg,
                highlightthickness=0
            )
            btn.original_bg = bg
            btn.disabled_bg = disabled
            btn.config(command=lambda t=bt, b=btn: self.place_bet(t, b))
            btn.bind('<Button-3>', lambda e, t=bt, b=btn: self._on_right_click_clear(e, t, b))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        row2_frame = tk.Frame(parent, bg='#D0E7FF', height=80)
        row2_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row2_frame.pack_propagate(False)
        buttons_2 = ['TripleRed','Flush','Tie','TripleBlack']
        for bt in buttons_2:
            odds, bg, fg, disabled = odds_map[bt]
            display = bet_display_map[bt]
            btn = tk.Button(
                row2_frame,
                text=f"{odds}\n{display}\n~~",
                bg=bg, fg=fg,
                font=('Arial', 10, 'bold'),
                height=3, width=10,
                wraplength=80,
                disabledforeground=fg,
                highlightthickness=0
            )
            btn.original_bg = bg
            btn.disabled_bg = disabled
            btn.config(command=lambda t=bt, b=btn: self.place_bet(t, b))
            btn.bind('<Button-3>', lambda e, t=bt, b=btn: self._on_right_click_clear(e, t, b))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        row3_frame = tk.Frame(parent, bg='#D0E7FF', height=80)
        row3_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row3_frame.pack_propagate(False)
        buttons_3 = ['Dragon','Tiger','Phoenix']
        for bt in buttons_3:
            odds, bg, fg, disabled = odds_map[bt]
            display = bet_display_map[bt]
            btn = tk.Button(
                row3_frame,
                text=f"{odds}\n{display}\n~~",
                bg=bg, fg=fg,
                font=('Arial', 12, 'bold'),
                height=3, width=10,
                wraplength=80,
                disabledforeground=fg,
                highlightthickness=0
            )
            btn.original_bg = bg
            btn.disabled_bg = disabled
            btn.config(command=lambda t=bt, b=btn: self.place_bet(t, b))
            btn.bind('<Button-3>', lambda e, t=bt, b=btn: self._on_right_click_clear(e, t, b))
            btn.bet_type = bt
            btn.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=2)
            self.bet_buttons.append(btn)

        explanation = "龙/虎/凤：独赢1.8倍，两家和局1倍，三家和局全输；平局：二家和7倍，三家和20倍"
        explanation_frame = tk.Frame(parent, bg='#D0E7FF', height=40)
        explanation_frame.pack(fill=tk.BOTH, expand=True, pady=2)
        explanation_frame.pack_propagate(False)
        tk.Label(
            explanation_frame,
            text=explanation,
            font=('Arial', 10),
            bg='#D0E7FF'
        ).pack(expand=True)

    def clear_single_bet(self, bet_type):
        if bet_type in self.current_bets:
            bet_amount = self.current_bets[bet_type]
            self.balance += bet_amount
            self.current_bet -= bet_amount
            del self.current_bets[bet_type]
            self.update_balance()
            self.current_bet_label.config(text=f"${self.current_bet:,}")
            for btn in self.bet_buttons:
                if hasattr(btn, 'bet_type') and btn.bet_type == bet_type:
                    original_text = btn.cget("text").split('\n')
                    new_text = f"{original_text[0]}\n{original_text[1]}\n~~"
                    btn.config(text=new_text)

    def _populate_betting_center(self, parent):
        balance_display_frame = tk.Frame(parent, bg='#D0E7FF')
        balance_display_frame.pack(fill=tk.X)

        self.balance_label = tk.Label(
            balance_display_frame,
            text=f"余额: ${int(round(self.balance)):,}",
            font=('Arial', 22),
            fg='black',
            bg='#D0E7FF'
        )
        self.balance_label.pack(side=tk.LEFT)

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
        tk.Label(header_frame, text="边注最高", font=("Arial",12,"bold"),
                 bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="和局最高", font=("Arial",12,"bold"),
                 bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="主注最高", font=("Arial",12,"bold"),
                 bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)

        content_frame = tk.Frame(outer_frame, bg=table_bg)
        content_frame.pack(fill=tk.X)
        tk.Label(content_frame, text="30,000", font=("Arial",12,"bold"),
                 bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="100,000", font=("Arial",12,"bold"),
                 bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="500,000", font=("Arial",12,"bold"),
                 bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)

        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, padx=5, pady=1)

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

        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(3,0), padx=2)

        current_bet_frame = tk.Frame(parent, bg='#D0E7FF')
        current_bet_frame.pack(pady=(0,1))
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
        SUITS = ['Club','Diamond','Heart','Spade']
        RANKS = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
        remaining_deck = self.game.deck[self.game.cut_position:]
        remaining_cards = {suit:{rank:0 for rank in RANKS} for suit in SUITS}
        for card in remaining_deck:
            suit, rank = card
            remaining_cards[suit][rank] += 1

        win = tk.Toplevel(self)
        win.title("剩余牌堆统计")
        win.geometry("600x400")
        win.resizable(False,False)
        win.configure(bg='#F0F0F0')

        self.update_idletasks()
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_width = self.winfo_width()
        main_height = self.winfo_height()
        popup_width = 600
        popup_height = 400
        x = main_x + (main_width - popup_width)//2
        y = main_y + (main_height - popup_height)//2
        win.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        total_remaining = len(remaining_deck)
        title_label = tk.Label(
            main_frame,
            text=f"剩余{total_remaining}张牌",
            font=('Arial',16,'bold'),
            bg='#F0F0F0',
            fg='#333333'
        )
        title_label.pack(pady=(0,10))

        table_frame = tk.Frame(main_frame, bg='#F0F0F0')
        table_frame.pack(fill=tk.BOTH, expand=True)

        header_frame = tk.Frame(table_frame, bg='#F0F0F0')
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="", width=6, bg='#F0F0F0').pack(side=tk.LEFT, padx=3)
        for rank in RANKS:
            display_rank = 'X' if rank=='10' else rank
            label = tk.Label(
                header_frame,
                text=display_rank,
                width=4,
                font=('Arial',10,'bold'),
                bg='#F0F0F0',
                relief=tk.RAISED,
                bd=1
            )
            label.pack(side=tk.LEFT, padx=1)
        total_label = tk.Label(
            header_frame,
            text="总计",
            width=4,
            font=('Arial',10,'bold'),
            bg='#F0F0F0',
            relief=tk.RAISED,
            bd=1
        )
        total_label.pack(side=tk.LEFT, padx=1)

        for suit in SUITS:
            row_frame = tk.Frame(table_frame, bg='#F0F0F0')
            row_frame.pack(fill=tk.X)
            suit_display = {'Club':'梅花','Diamond':'方块','Heart':'红心','Spade':'黑桃'}
            suit_label = tk.Label(
                row_frame,
                text=suit_display[suit],
                width=6,
                font=('Arial',10,'bold'),
                bg='#F0F0F0',
                relief=tk.RAISED,
                bd=1
            )
            suit_label.pack(side=tk.LEFT, padx=1)
            suit_total = 0
            for rank in RANKS:
                count = remaining_cards[suit][rank]
                suit_total += count
                if count==0:
                    bg_color = '#FFCCCC'
                elif count<4:
                    bg_color = '#FFFFCC'
                else:
                    bg_color = '#CCFFCC'
                count_label = tk.Label(
                    row_frame,
                    text=str(count),
                    width=4,
                    font=('Arial',10),
                    bg=bg_color,
                    relief=tk.SUNKEN,
                    bd=1
                )
                count_label.pack(side=tk.LEFT, padx=1)
            total_label = tk.Label(
                row_frame,
                text=str(suit_total),
                width=4,
                font=('Arial',10,'bold'),
                bg='#DDDDDD',
                relief=tk.RAISED,
                bd=1
            )
            total_label.pack(side=tk.LEFT, padx=1)

        separator = tk.Frame(table_frame, height=2, bg='#333333')
        separator.pack(fill=tk.X, pady=5)

        total_row_frame = tk.Frame(table_frame, bg='#F0F0F0')
        total_row_frame.pack(fill=tk.X)
        tk.Label(
            total_row_frame,
            text="总计",
            width=6,
            font=('Arial',10,'bold'),
            bg='#F0F0F0',
            relief=tk.RAISED,
            bd=1
        ).pack(side=tk.LEFT, padx=1)

        rank_totals = {}
        for rank in RANKS:
            rank_totals[rank] = 0
            for suit in SUITS:
                rank_totals[rank] += remaining_cards[suit][rank]
        grand_total = 0
        for rank in RANKS:
            total = rank_totals[rank]
            grand_total += total
            if total==0:
                bg_color = '#FFCCCC'
            elif total<16:
                bg_color = '#FFFFCC'
            else:
                bg_color = '#CCFFCC'
            total_label = tk.Label(
                total_row_frame,
                text=str(total),
                width=4,
                font=('Arial',10,'bold'),
                bg=bg_color,
                relief=tk.RAISED,
                bd=1
            )
            total_label.pack(side=tk.LEFT, padx=1)
        grand_total_label = tk.Label(
            total_row_frame,
            text=str(grand_total),
            width=4,
            font=('Arial',10,'bold'),
            bg='#CCCCFF',
            relief=tk.RAISED,
            bd=1
        )
        grand_total_label.pack(side=tk.LEFT, padx=1)

        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

    def _populate_betting_right(self, parent):
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

        self._set_default_chip()

        self.current_chip_label = tk.Label(
            parent,
            text="筹码: $1,000",
            font=('Arial', 18),
            fg='black',
            bg='#D0E7FF'
        )
        self.current_chip_label.pack(side=tk.LEFT, padx=0)

    def _set_default_chip(self):
        for chip in self.chip_buttons:
            if chip['text'] == '1千':
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
        if btn_widget is not None and str(btn_widget.cget('state')) == 'disabled':
            return
        for b in getattr(self, 'bet_buttons', []):
            if hasattr(b, 'bet_type') and b.bet_type == bet_type:
                if str(b.cget('state')) == 'disabled':
                    return
                break

        amount = int(self.selected_bet_amount)
        existing = int(self.current_bets.get(bet_type, 0))

        if bet_type in ('Dragon', 'Tiger', 'Phoenix'):
            limit = 500_000
        elif bet_type == 'Tie':
            limit = 100_000
        else:
            limit = 30_000

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
                top = original_text[0] if len(original_text)>=1 else btn.cget("text")
                mid = original_text[1] if len(original_text)>=2 else ""
                new_text = f"{top}\n{mid}\n${self.current_bets[bet_type]:,}"
                btn.config(text=new_text)

    def _on_right_click_clear(self, event, bet_type, btn_widget):
        if str(btn_widget.cget('state')) == 'disabled':
            return
        self.clear_single_bet(bet_type)

    def start_game(self):
        self.disable_all_buttons()
        if len(self.game.deck) - self.game.cut_position < 60:
            self._initialize_game(True)
            return

        self.game.play_game()
        self.animate_dealing()

    def animate_dealing(self):
        self.table_canvas.delete('all')
        self.point_labels.clear()
        self._draw_table_labels()

        self.revealed_cards = {'dragon':[], 'tiger':[], 'phoenix':[]}

        self._deal_initial_cards()
        self.after(1000, self._reveal_dragon_card)

    def _deal_initial_cards(self):
        self.initial_card_ids = []
        # 派牌顺序：龙先，虎次，凤最后
        for hand in ['dragon', 'tiger', 'phoenix']:
            for i, pos in enumerate(self._get_card_positions(hand)[:1]):
                self._animate_card_entrance(hand, i, pos)

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
        card_info = self.initial_card_ids[0]  # dragon
        real_card = self.game.dragon_hand[0]
        self._flip_card(card_info, real_card, 0)
        self.after(500, self._reveal_tiger_card)

    def _reveal_tiger_card(self):
        card_info = self.initial_card_ids[1]  # tiger
        real_card = self.game.tiger_hand[0]
        self._flip_card(card_info, real_card, 1)
        self.after(500, self._reveal_phoenix_card)

    def _reveal_phoenix_card(self):
        card_info = self.initial_card_ids[2]  # phoenix
        real_card = self.game.phoenix_hand[0]
        self._flip_card(card_info, real_card, 2)
        self.after(750, self.resolve_bets)

    def _flip_card(self, card_info, real_card, seq, step=0):
        steps = 12
        orig_w, orig_h = 120, 170
        hand_type, card_id = card_info

        if step > steps:
            try:
                self.table_canvas.itemconfig(card_id, image=self.card_images[real_card])
            except Exception:
                pass
            try:
                self.revealed_cards[hand_type].append(real_card)
            except Exception:
                if not hasattr(self,'revealed_cards'):
                    self.revealed_cards = {'dragon':[],'tiger':[],'phoenix':[]}
                self.revealed_cards[hand_type].append(real_card)

            if card_id in getattr(self,'_temp_flip_images',{}):
                try:
                    del self._temp_flip_images[card_id]
                except Exception:
                    pass
            return

        half = steps // 2
        if step <= half:
            ratio = 1 - (step / float(half))
            use_back = True
        else:
            ratio = (step - half) / float(half)
            use_back = False

        w = max(1, int(orig_w * ratio))
        img = self._create_scaled_image(real_card, w, orig_h, use_back=use_back)
        if not hasattr(self, '_temp_flip_images'):
            self._temp_flip_images = {}
        self._temp_flip_images[card_id] = img

        try:
            self.table_canvas.itemconfig(card_id, image=img)
        except Exception:
            pass

        self.after(20, lambda: self._flip_card(card_info, real_card, seq, step+1))

    def _create_scaled_image(self, card, w, h, use_back=False):
        from PIL import Image, ImageTk
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', 'Poker1')
        try:
            if use_back:
                path = os.path.join(card_dir, 'Background.png')
            else:
                path = os.path.join(card_dir, f"{card[0]}{card[1]}.png")
            img = Image.open(path).convert('RGBA')
            w = max(1, int(w))
            img = img.resize((w, int(h)), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception as e:
            try:
                from PIL import Image
                placeholder = Image.new('RGBA', (max(1,int(w)), int(h)), (0,0,0,0))
                return ImageTk.PhotoImage(placeholder)
            except Exception:
                return getattr(self, 'back_image', None)

    def resolve_bets(self):
        payouts = 0
        outcome = self.game.outcome
        dragon_suit = self.game.dragon_hand[0][0]
        tiger_suit = self.game.tiger_hand[0][0]
        phoenix_suit = self.game.phoenix_hand[0][0]
        suits = [dragon_suit, tiger_suit, phoenix_suit]
        red_suits = ['Diamond','Heart']
        black_suits = ['Club','Spade']

        all_red = all(s in red_suits for s in suits)
        all_black = all(s in black_suits for s in suits)
        all_same_suit = len(set(suits)) == 1
        all_hearts = all(s == 'Heart' for s in suits)
        all_diamonds = all(s == 'Diamond' for s in suits)
        all_spades = all(s == 'Spade' for s in suits)
        all_clubs = all(s == 'Club' for s in suits)

        for bet_type, bet_amount in self.current_bets.items():
            if bet_type == 'TripleRed' and all_red:
                payouts += bet_amount * 4
            elif bet_type == 'TripleBlack' and all_black:
                payouts += bet_amount * 4
            elif bet_type == 'Flush' and all_same_suit:
                payouts += bet_amount * 13
            elif bet_type == 'HeartFlush' and all_hearts:
                payouts += bet_amount * 61
            elif bet_type == 'DiamondFlush' and all_diamonds:
                payouts += bet_amount * 61
            elif bet_type == 'SpadeFlush' and all_spades:
                payouts += bet_amount * 61
            elif bet_type == 'ClubFlush' and all_clubs:
                payouts += bet_amount * 61
            elif bet_type in ('Dragon','Tiger','Phoenix'):
                if outcome['type'] == 'single' and outcome['winner'] == bet_type:
                    payouts += bet_amount * 2.8
                elif outcome['type'] == 'two_tie' and bet_type in outcome['tied_hands']:
                    payouts += bet_amount * 2
            elif bet_type == 'Tie':
                if outcome['type'] == 'two_tie':
                    payouts += bet_amount * 8
                elif outcome['type'] == 'three_tie':
                    payouts += bet_amount * 21

        self.balance += payouts
        self.current_bets.clear()
        self.update_balance()

        for btn in getattr(self, 'bet_buttons', []):
            if hasattr(btn, 'bet_type'):
                original_text = btn.cget("text").split('\n')
                top = original_text[0] if len(original_text)>=1 else ""
                mid = original_text[1] if len(original_text)>=2 else ""
                new_text = f"{top}\n{mid}\n~~"
                try:
                    btn.config(text=new_text)
                except Exception:
                    pass

        self.current_bet = 0
        if hasattr(self, 'current_bet_label'):
            try:
                self.current_bet_label.config(text="$0")
            except Exception:
                pass

        try:
            self.last_win = int(payouts)
            if hasattr(self, 'last_win_label'):
                self.last_win_label.config(text=f"${max(self.last_win,0):,}")
        except Exception:
            pass

        self._animate_cards_result()
        self._show_result_text()

        self.add_marker_result(outcome)

        if len(self.game.deck) - self.game.cut_position < 60:
            self._initialize_game(True)
        else:
            self.after(100, self.enable_buttons_except_deal)
            self.after(1800, lambda: self.deal_button.config(state=tk.NORMAL))
            self.after(2000, lambda: self.bind('<Return>', lambda e: self.start_game()))

    def _animate_cards_result(self):
        dragon_id = None
        tiger_id = None
        phoenix_id = None
        for hand_type, card_id in self.initial_card_ids:
            if hand_type == 'dragon':
                dragon_id = card_id
            elif hand_type == 'tiger':
                tiger_id = card_id
            elif hand_type == 'phoenix':
                phoenix_id = card_id

        if not dragon_id or not tiger_id or not phoenix_id:
            return

        dragon_pos = self.table_canvas.coords(dragon_id)
        tiger_pos = self.table_canvas.coords(tiger_id)
        phoenix_pos = self.table_canvas.coords(phoenix_id)
        if not dragon_pos or not tiger_pos or not phoenix_pos:
            return

        dx, dy = dragon_pos
        tx, ty = tiger_pos
        px, py = phoenix_pos

        outcome = self.game.outcome
        if outcome['type'] == 'single':
            winner = outcome['winner']
            if winner == 'Dragon':
                self._animate_card_move(dragon_id, dx, dy, dx, dy+20, 100)
            elif winner == 'Tiger':
                self._animate_card_move(tiger_id, tx, ty, tx, ty+20, 100)
            elif winner == 'Phoenix':
                self._animate_card_move(phoenix_id, px, py, px, py+20, 100)
        elif outcome['type'] == 'two_tie':
            hands = outcome['tied_hands']
            if 'Dragon' in hands:
                self._animate_card_move(dragon_id, dx, dy, dx, dy+20, 100)
            if 'Tiger' in hands:
                self._animate_card_move(tiger_id, tx, ty, tx, ty+20, 100)
            if 'Phoenix' in hands:
                self._animate_card_move(phoenix_id, px, py, px, py+20, 100)
        elif outcome['type'] == 'three_tie':
            # 三家和：所有牌向下移动
            self._animate_card_move(dragon_id, dx, dy, dx, dy+20, 100)
            self._animate_card_move(tiger_id, tx, ty, tx, ty+20, 100)
            self._animate_card_move(phoenix_id, px, py, px, py+20, 100)

    def _animate_card_move(self, card_id, start_x, start_y, end_x, end_y, duration):
        steps = int(duration / 10)
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
        text = ""
        text_color = "white"
        bg_color = "#35654d"
        outcome = self.game.outcome

        if outcome['type'] == 'single':
            if outcome['winner'] == 'Dragon':
                text = "龙获胜"
                bg_color = '#FF0000'
            elif outcome['winner'] == 'Tiger':
                text = "虎获胜"
                bg_color = '#FFA600'
            elif outcome['winner'] == 'Phoenix':
                text = "凤获胜"
                bg_color = '#007BFF'
            text_color = 'white' if outcome['winner']=='Dragon' else 'black'
        elif outcome['type'] == 'two_tie':
            # 将英文名映射为中文
            name_map = {'Dragon': '龙', 'Tiger': '虎', 'Phoenix': '凤'}
            chinese_names = [name_map[h] for h in outcome['tied_hands']]
            text = f"{'/'.join(chinese_names)}平局"
            bg_color = '#00FF00'
            text_color = 'black'
        elif outcome['type'] == 'three_tie':
            text = "三家和局"
            bg_color = '#FFFFFF'
            text_color = 'black'

        try:
            self.table_canvas.itemconfig(self.result_text_id, text=text, fill=text_color)
        except Exception:
            pass

        try:
            self.table_canvas.update_idletasks()
        except Exception:
            pass

        try:
            text_bbox = self.table_canvas.bbox(self.result_text_id)
            if text_bbox:
                padding = 15
                expanded_bbox = (
                    text_bbox[0]-padding, text_bbox[1]-padding,
                    text_bbox[2]+padding, text_bbox[3]+padding
                )
                try:
                    self.table_canvas.coords(self.result_bg_id, expanded_bbox)
                    self.table_canvas.itemconfig(self.result_bg_id, fill=bg_color, outline=bg_color)
                    self.table_canvas.tag_raise(self.result_text_id)
                    self.table_canvas.tag_lower(self.result_bg_id)
                except Exception:
                    pass
        except Exception:
            pass

    def update_balance(self):
        self.balance_label.config(text=f"余额: ${int(round(self.balance)):,}")
        update_balance_in_json(self.username, self.balance)

    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("龙虎凤游戏说明")
        win.geometry("600x400")
        win.resizable(False,False)
        self.update_idletasks()
        main_x = self.winfo_x()
        main_y = self.winfo_y()
        main_width = self.winfo_width()
        main_height = self.winfo_height()
        popup_width = 600
        popup_height = 400
        x = main_x + (main_width - popup_width)//2
        y = main_y + (main_height - popup_height)//2
        win.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        text_frame = tk.Frame(win)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        instructions = """
龙虎凤游戏规则：

1. 游戏发三张牌：龙、虎、凤各一张
2. 比较牌面点数，K最大，A最小
3. 下注选项：
   - 独赢：所选手牌为唯一最大，赔率1.8:1
   - 二家和：所选手牌为并列最大之一，赔率1:1
   - 三家和：所有手牌点数相同，所有主注输，平局注赢20:1
   - 平局注：二家和赢7:1，三家和赢20:1

4. 边注：
   - 三红：三张都是红心或方块，3:1
   - 三黑：三张都是黑桃或梅花，3:1
   - 同花：三张同一花色，12:1
   - 红心同花/方片同花/黑桃同花/梅花同花：60:1

5. 珠路图：
   - 大路：独赢显示对应颜色圆，二家和显示半色圆加绿色“和”，三家和显示三色圆加白色“和”
   - 标记路：独赢显示颜色和文字，二家和绿色“和”，三家和白色“和”
        """
        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=('Arial',12), padx=10, pady=10)
        text_widget.insert(tk.END, instructions)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True)

        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

def main(initial_balance=1000000, username="Guest"):
    app = DragonTigerPhoenixGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")