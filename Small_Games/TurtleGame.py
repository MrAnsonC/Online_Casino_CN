import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import subprocess
import sys
import secrets
import math
from PIL import Image, ImageTk, ImageDraw, ImageFont

# ---------- 数据持久化 ----------
def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

def save_user_data(users):
    with open(get_data_file_path(), 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    with open(get_data_file_path(), 'r', encoding='utf-8') as f:
        return json.load(f)

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

# ---------- 圆形筹码按钮 ----------
class CircleButton(tk.Canvas):
    def __init__(self, master, text, bg_color, fg_color, command=None, radius=30, *args, **kwargs):
        super().__init__(master, width=radius*2, height=radius*2,
                         highlightthickness=0, bg="#16213e", *args, **kwargs)
        self.radius = radius
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.text = text
        self.command = command
        self.create_oval(0, 0, radius*2, radius*2, fill=bg_color, outline="#16213e", width=2)
        self.create_text(radius, radius, text=text, fill=fg_color, font=("Arial", 18, "bold"))
        self.bind("<Button-1>", self.on_click)

    def on_click(self, event):
        if self.command:
            self.command()

# ---------- 扑克牌相关 ----------
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i+2 for i, r in enumerate(RANKS)}  # A=14

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES.get(rank, 0)  # 炸弹牌值为0
        self.is_bomb = (suit == 'JOKER')      # 炸弹标记

    def __str__(self):
        if self.is_bomb:
            return f"炸弹{self.rank}"
        return f"{self.rank}{self.suit}"
    __repr__ = __str__

# ---------- 洗牌（参考 Wild Five Poker）----------
def get_shuffled_deck():
    # 生成初始牌组：52张普通牌 + 2张炸弹牌
    base_deck = []
    for suit in SUITS:
        for rank in RANKS:
            base_deck.append({"suit": suit, "rank": rank})
    base_deck.append({"suit": "JOKER", "rank": "A"})
    base_deck.append({"suit": "JOKER", "rank": "B"})
    
    # 尝试调用外部 shuffle.py
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shuffle_script = os.path.join(parent_dir, 'A_Tools', 'Card', 'shuffle.py')
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    
    try:
        result = subprocess.run(
            [sys.executable, shuffle_script, "true", "1"],
            capture_output=True, text=True, encoding='utf-8', env=env, check=True, timeout=30
        )
        shuffle_data = json.loads(result.stdout)
        # 使用 shuffle.py 返回的牌序顺序，但保持我们牌的内容（炸弹标记）
        # 注意：shuffle.py 返回的 deck 可能不是我们想要的（它只包含普通牌+单张鬼牌）
        # 这里我们只利用它的随机顺序，将 base_deck 按返回的索引重排
        if "deck" in shuffle_data:
            # 获取顺序索引：根据 shuffle_data["deck"] 中牌的花色点数映射到 base_deck
            order = []
            for d in shuffle_data["deck"]:
                for i, bd in enumerate(base_deck):
                    if bd["suit"] == d["suit"] and bd["rank"] == d["rank"]:
                        order.append(i)
                        break
            # 如果长度匹配，则按 order 重排 base_deck
            if len(order) == 54:
                base_deck = [base_deck[i] for i in order]
    except Exception as e:
        print(f"调用 shuffle.py 失败: {e}，使用本地安全洗牌")
        # Fisher-Yates 安全洗牌
        for i in range(len(base_deck)-1, 0, -1):
            j = secrets.randbelow(i+1)
            base_deck[i], base_deck[j] = base_deck[j], base_deck[i]
    
    # 转换成 Card 对象
    return [Card(d["suit"], d["rank"]) for d in base_deck]

# ---------- 主游戏 ----------
class BombGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("炸弹扑克 · 比大小")
        self.root.geometry("1300x750+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.balance = float(initial_balance)
        self.username = username
        self.current_bet = 0.0
        self.last_win = 0.0
        self.game_active = False          # 是否已下注并等待开牌
        self.cards = []                   # 洗好后的54张Card对象
        self.card_labels = []             # 所有卡片Label（按网格顺序）
        self.selected_index = None        # 玩家选中的牌索引
        self.dealer_index = None
        self.all_face_up = False

        # 加载图片资源
        self._load_images()
        # 洗牌并生成网格
        self._new_shuffle()
        self.create_widgets()
        self.update_display()

    # ---------- 加载扑克图片和炸弹图片 ----------
    def _load_images(self):
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        poker_folder = random.choice(['Poker1', 'Poker2'])
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', poker_folder)
        self.card_size = (70, 98)
        suit_map = {'♠': 'Spade', '♥': 'Heart', '♦': 'Diamond', '♣': 'Club'}
        self.front_images = {}
        self.back_image = None
        self.bomb_images = {}   # 炸弹图片

        # 背面
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img = Image.open(back_path).resize(self.card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
        except:
            img = Image.new('RGB', self.card_size, 'black')
            self.back_image = ImageTk.PhotoImage(img)

        # 普通牌正面
        for suit in SUITS:
            for rank in RANKS:
                try:
                    path = os.path.join(card_dir, f"{suit_map[suit]}{rank}.png")
                    img = Image.open(path).resize(self.card_size)
                    self.front_images[(suit, rank)] = ImageTk.PhotoImage(img)
                except:
                    # 占位
                    img = Image.new('RGB', self.card_size, 'white')
                    draw = ImageDraw.Draw(img)
                    text = f"{rank}{suit}"
                    try:
                        font = ImageFont.truetype("arial.ttf", 16)
                    except:
                        font = ImageFont.load_default()
                    bbox = draw.textbbox((0,0), text, font=font)
                    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
                    draw.text(((self.card_size[0]-tw)//2, (self.card_size[1]-th)//2), text, fill="black", font=font)
                    self.front_images[(suit, rank)] = ImageTk.PhotoImage(img)

        # 炸弹图片（JOKER-A.png, JOKER-B.png）
        for bomb_name in ['A', 'B']:
            try:
                path = os.path.join(card_dir, f"JOKER-{bomb_name}.png")
                img = Image.open(path).resize(self.card_size)
                self.bomb_images[bomb_name] = ImageTk.PhotoImage(img)
            except:
                # 生成占位炸弹图
                img = Image.new('RGB', self.card_size, 'purple')
                draw = ImageDraw.Draw(img)
                draw.text((10, 40), f"JOKER\n{bomb_name}", fill="yellow", font=ImageFont.load_default())
                self.bomb_images[bomb_name] = ImageTk.PhotoImage(img)

    # ---------- 新的一局：重新洗牌，重置界面 ----------
    def _new_shuffle(self):
        self.cards = get_shuffled_deck()
        self.selected_index = None
        self.dealer_index = None
        self.all_face_up = False
        # 重新创建网格（若已存在则更新图片）
        if hasattr(self, 'cards_frame'):
            self._refresh_grid()

    def _refresh_grid(self):
        # 更新所有卡片为背面
        for i, label in enumerate(self.card_labels):
            label.config(image=self.back_image, borderwidth=2, relief="solid",
                         highlightthickness=0)
            label.card = self.cards[i]
        self.selected_index = None

    # ---------- UI 构建 ----------
    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 左侧牌桌（9列6行）
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,10))

        tk.Label(left_frame, text="点击任意牌选择你的牌", font=("Arial", 16, "bold"),
                bg="#16213e", fg="#e94560").pack(pady=5)

        canvas = tk.Canvas(left_frame, bg="#16213e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
        self.cards_frame = tk.Frame(canvas, bg="#16213e")
        canvas.create_window((0,0), window=self.cards_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 9列6行
        rows, cols = 6, 9
        self.card_labels = []
        for idx, card in enumerate(self.cards):
            row = idx // cols
            col = idx % cols
            label = tk.Label(self.cards_frame, image=self.back_image, bg="#16213e",
                             borderwidth=2, relief="solid")
            label.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            label.bind("<Button-1>", lambda e, i=idx: self.select_card(i))
            label.card = card
            label.card_index = idx
            self.card_labels.append(label)

        # 列权重
        for c in range(cols):
            self.cards_frame.columnconfigure(c, weight=1)
        self.cards_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))

        # ---------- 右侧控制面板 ----------
        right_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10,0))

        # 余额
        balance_frame = tk.Frame(right_frame, bg="#16213e")
        balance_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(balance_frame, text="余额:", font=("Arial", 14),
                bg="#16213e", fg="#f1f1f1").pack(side=tk.LEFT)
        self.balance_var = tk.StringVar()
        self.balance_var.set(f"${self.balance:.2f}")
        tk.Label(balance_frame, textvariable=self.balance_var, font=("Arial", 14, "bold"),
                bg="#16213e", fg="#ffd369").pack(side=tk.LEFT, padx=(5,0))

        # 筹码按钮
        chips_frame = tk.Frame(right_frame, bg="#16213e")
        chips_frame.pack(fill=tk.X, padx=10, pady=(0,10))
        chips = [("$5", '#ff0000', 'white'), ("$25", '#00ff00', 'black'),
                 ("$100", '#000000', 'white'), ("$500", "#FF7DDA", 'black'),
                 ("$1K", '#ffffff', 'black')]
        self.chip_buttons = []
        for text, bg, fg in chips:
            btn = CircleButton(chips_frame, text=text, bg_color=bg, fg_color=fg,
                               command=lambda t=text: self.add_chip(t[1:]))
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)

        # 下注金额显示
        bet_frame = tk.Frame(right_frame, bg="#16213e")
        bet_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(bet_frame, text="下注金额:", font=("Arial", 12),
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        self.bet_var = tk.StringVar()
        self.bet_var.set("$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"),
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5,0))

        # 上局获胜
        win_frame = tk.Frame(right_frame, bg="#16213e")
        win_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(win_frame, text="上局获胜:", font=("Arial", 12),
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")
        tk.Label(win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"),
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5,0))

        # 按钮容器（动态切换）
        self.button_container = tk.Frame(right_frame, bg="#16213e")
        self.button_container.pack(fill=tk.X, padx=10, pady=20)

        # 初始状态：显示「重设下注」和「开牌」
        self.reset_bet_btn = tk.Button(self.button_container, text="重设下注", font=("Arial", 12),
                                       bg="#3498db", fg="white", width=12, command=self.reset_bet)
        self.reset_bet_btn.pack(side=tk.LEFT, padx=5)
        self.confirm_btn = tk.Button(self.button_container, text="开牌", font=("Arial", 12, "bold"),
                                     bg="#27ae60", fg="white", width=12, command=self.confirm_and_play)
        self.confirm_btn.pack(side=tk.LEFT, padx=5)

        # 「再来一局」按钮（初始隐藏）
        self.restart_btn = tk.Button(self.button_container, text="再来一局", font=("Arial", 12, "bold"),
                                     bg="#e67e22", fg="white", width=12, command=self.restart_round)
        self.restart_btn.pack_forget()

        # 简单状态提示
        self.status_label = tk.Label(right_frame, text="请选牌并下注", font=("Arial", 12),
                                     bg="#16213e", fg="#ffd369")
        self.status_label.pack(pady=10, fill=tk.X)

        # 规则说明（精简）
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"),
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        rules = [
            "• 选一张牌，下注后点击「开牌」",
            "• 庄家随机从剩余牌中抽一张",
            "• 炸弹规则：",
            "  - 玩家炸弹 → 玩家输",
            "  - 庄家炸弹 → 玩家赢 25:1",
            "  - 双炸弹 → 玩家赢 1200:1",
            "• 无炸弹时比点数（A最大）",
            "  玩家大 → 赢 1:1，否则输"
        ]
        for r in rules:
            tk.Label(info_frame, text=r, font=("Arial", 10),
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=2)

    # ---------- 筹码逻辑 ----------
    def add_chip(self, amount):
        if self.game_active:
            messagebox.showwarning("提示", "请先结束当前对局")
            return
        try:
            if amount == "1K":
                amount_val = 1000.0
            else:
                amount_val = float(amount)
            new_bet = self.current_bet + amount_val
            if new_bet <= self.balance:
                self.current_bet = new_bet
                self.bet_var.set(f"${self.current_bet:.2f}")
        except:
            pass

    def reset_bet(self):
        if self.game_active:
            messagebox.showwarning("提示", "请先结束当前对局")
            return
        self.current_bet = 0.0
        self.bet_var.set("$0.00")
        self.status_label.config(text="下注已重置")

    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")

    # ---------- 选牌 ----------
    def select_card(self, idx):
        if self.game_active:
            messagebox.showwarning("提示", "游戏已开牌，请按「再来一局」")
            return
        if self.all_face_up:
            messagebox.showwarning("提示", "请按「再来一局」开始新对局")
            return
        # 清除之前的高亮（仅改变边框颜色，不改变宽度）
        if self.selected_index is not None:
            old = self.card_labels[self.selected_index]
            old.config(highlightbackground="", highlightcolor="", highlightthickness=0,
                       borderwidth=2, relief="solid")
        # 高亮新选中的牌（金色边框）
        self.selected_index = idx
        new_label = self.card_labels[idx]
        new_label.config(highlightbackground="gold", highlightcolor="gold",
                         highlightthickness=2, borderwidth=2, relief="solid")
        self.status_label.config(text=f"已选牌: {self.cards[idx]}")

    # ---------- 开牌并结算 ----------
    def confirm_and_play(self):
        if self.selected_index is None:
            messagebox.showwarning("错误", "请先选择一张牌")
            return
        if self.current_bet <= 0:
            messagebox.showwarning("错误", "请下注")
            return
        if self.current_bet > self.balance:
            messagebox.showwarning("错误", "余额不足")
            return

        self.game_active = True
        # 扣除下注金额
        self.balance -= self.current_bet
        update_balance_in_json(self.username, self.balance)
        self.update_display()

        # 庄家随机选一张牌（不能与玩家相同）
        available = [i for i in range(54) if i != self.selected_index]
        self.dealer_index = random.choice(available)
        player_card = self.cards[self.selected_index]
        dealer_card = self.cards[self.dealer_index]

        # 全部翻开正面
        self.all_face_up = True
        for idx, label in enumerate(self.card_labels):
            card = self.cards[idx]
            if card.is_bomb:
                img = self.bomb_images.get(card.rank, self.back_image)
            else:
                img = self.front_images.get((card.suit, card.rank), self.back_image)
            label.config(image=img, borderwidth=2, relief="solid")
        # 高亮玩家牌（金色）、庄家牌（红色）
        self.card_labels[self.selected_index].config(highlightbackground="gold", highlightthickness=3)
        self.card_labels[self.dealer_index].config(highlightbackground="red", highlightthickness=3)

        # 判定胜负
        player_bomb = player_card.is_bomb
        dealer_bomb = dealer_card.is_bomb
        win = False
        multiplier = 0
        result_text = ""

        if player_bomb and dealer_bomb:
            win = True
            multiplier = 1200
            result_text = f"💣 双炸弹！玩家赢 {multiplier}:1"
        elif player_bomb:
            win = False
            result_text = f"💥 你抽中炸弹，输掉 ${self.current_bet:.2f}"
        elif dealer_bomb:
            win = True
            multiplier = 25
            result_text = f"💣 庄家炸弹！玩家赢 {multiplier}:1"
        else:
            # 比点数
            if player_card.value > dealer_card.value:
                win = True
                multiplier = 1
                result_text = f"🎉 点数胜利！{player_card} > {dealer_card} 赢 1:1"
            else:
                win = False
                result_text = f"😞 点数失败！{player_card} {'≤' if player_card.value == dealer_card.value else '<'} {dealer_card} 输"

        # 计算奖金
        if win:
            # 净赢 = 下注 * multiplier，总返还 = 下注 + 净赢
            net_win = self.current_bet * multiplier
            total_back = self.current_bet + net_win
            self.balance += total_back
            self.last_win = net_win
            result_text += f"  获得 ${net_win:.2f}"
        else:
            self.last_win = 0.0

        update_balance_in_json(self.username, self.balance)
        self.update_display()
        messagebox.showinfo("开牌结果", result_text)

        # 切换按钮：隐藏「重设下注」「开牌」，显示「再来一局」
        self.reset_bet_btn.pack_forget()
        self.confirm_btn.pack_forget()
        self.restart_btn.pack(side=tk.LEFT, padx=5)
        self.status_label.config(text="点击「再来一局」继续")

    # ---------- 再来一局：洗牌、重置所有状态 ----------
    def restart_round(self):
        # 重新洗牌
        self._new_shuffle()
        # 重置界面
        self._refresh_grid()
        self.selected_index = None
        self.dealer_index = None
        self.game_active = False
        self.all_face_up = False
        # 切换按钮
        self.restart_btn.pack_forget()
        self.reset_bet_btn.pack(side=tk.LEFT, padx=5)
        self.confirm_btn.pack(side=tk.LEFT, padx=5)
        self.status_label.config(text="请选牌并下注")
        # 不清空下注金额（保留上次金额可手动重置）
        # 但保留下注金额可能导致余额不足，由玩家自行处理

    # ---------- 关闭窗口 ----------
    def on_closing(self):
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

# ---------- 启动入口 ----------
def main(initial_balance, username):
    root = tk.Tk()
    game = BombGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = BombGame(root, 1000.0, "test_user")
    root.mainloop()