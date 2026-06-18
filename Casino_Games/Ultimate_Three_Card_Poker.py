import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
import math
import time
import secrets
import subprocess, sys

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    7: '迷你皇家同花顺',
    6: '同花顺', 
    5: '三条', 
    4: '顺子', 
    3: '同花', 
    2: '对子', 
    1: '高牌'
}

# Pair Plus支付表（不变）
PAIR_PLUS_PAYOUT = {
    7: 100,  # 迷你皇家同花顺 100:1
    6: 40,   # 同花顺 40:1
    5: 30,   # 三条 30:1
    4: 6,    # 顺子 6:1
    3: 3,    # 同花 3:1
    2: 1     # 对子 1:1
}

# 盲注支付表（打败庄家时）
BLIND_PAYOUT = {
    7: 100,   # 迷你皇家同花顺 100:1
    6: 20,    # 同花顺 20:1
    5: 10,    # 三条 10:1
    4: 1,     # 顺子 1:1
    3: 1,     # 同花 1:1
    2: 0,     # 一对或更少 Push（退还）
    1: 0
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
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

# Progressive 文件加载与保存
def load_progressive():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    default_progressive = 201074.31   # 最低保底金额
    min_progressive = 201074.31
    
    if not os.path.exists(path):
        return True, max(default_progressive, min_progressive)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == '3UP':
                    progressive_amount = float(item.get('jackpot', default_progressive))
                    return False, max(progressive_amount, min_progressive)
    except Exception:
        return True, max(default_progressive, min_progressive)
    return True, max(default_progressive, min_progressive)

def save_progressive(progressive):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Progressive.json')
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    
    found = False
    for item in data:
        if item.get('Games') == '3UP':
            item['jackpot'] = progressive
            found = True
            break
    
    if not found:
        data.append({"Games": "3UP", "jackpot": progressive})
    
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
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle.py')
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        try:
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
            self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(52)
        
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]
    
    def _secure_shuffle(self):
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

def evaluate_three_card_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits = [c.suit for c in cards]
    
    if len(set(suits)) == 1 and values == [14, 13, 12]:
        return (7, [14])
    
    if len(set(suits)) == 1:
        if values == [14, 3, 2]:
            return (6, [3])
        if values[0] - values[1] == 1 and values[1] - values[2] == 1:
            return (6, [values[0]])
    
    if values[0] == values[1] == values[2]:
        return (5, [values[0]])
    
    if values == [14, 3, 2]:
        return (4, [3])
    if values[0] - values[1] == 1 and values[1] - values[2] == 1:
        return (4, [values[0]])
    
    if len(set(suits)) == 1:
        return (3, values)
    
    if values[0] == values[1]:
        return (2, [values[0], values[2]])
    elif values[1] == values[2]:
        return (2, [values[1], values[0]])
    
    return (1, values)

def compare_hands(hand1, hand2):
    rank1, values1 = evaluate_three_card_hand(hand1)
    rank2, values2 = evaluate_three_card_hand(hand2)
    
    if rank1 > rank2:
        return 1
    elif rank1 < rank2:
        return -1
    else:
        for v1, v2 in zip(values1, values2):
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        return 0

class ThreeCardPokerGame:
    def __init__(self):
        self.reset_game()
        self.progressive_amount = load_progressive()[1]
        self.initial_progressive = self.progressive_amount
    
    def reset_game(self):
        self.deck = Deck()
        self.player_hand = []
        self.dealer_hand = []
        self.ante = 0          # 底注
        self.blind = 0         # 盲注（与底注相同）
        self.pair_plus = 0
        self.play_bet = 0      # 加注（1倍或3倍底注）
        self.progressive_bet = 0   # Progressive下注（固定5元）
        self.stage = "pre_flop"
        self.folded = False
        self.cards_revealed = {
            "player": [False, False, False],
            "dealer": [False, False, False]
        }
    
    def deal_initial(self):
        self.player_hand = self.deck.deal(3)
        self.dealer_hand = self.deck.deal(3)
    
    def dealer_qualifies(self):
        hand_rank, _ = evaluate_three_card_hand(self.dealer_hand)
        if hand_rank != 1:
            return True
        max_value = max(card.value for card in self.dealer_hand)
        return max_value >= 12

class ProgressiveWheelWindow:
    """三张牌 Progressive 抽奖窗口：Roulette 风格圆形轮盘，所有奖品文字始终保持水平正立。"""

    def __init__(self, parent, progressive_amount, callback):
        self.parent = parent
        self.progressive_amount = progressive_amount
        self.callback = callback

        self.selected_number = None
        self.stage = "select"

        self.win_value = 0
        self.current_prizes = []
        self.current_prize_index = -1
        self.highlight_index = -1          # 高亮扇区索引

        self.wheel_canvas = None
        self.wheel_angle = 0.0
        self.wheel_velocity = 0.0
        self.wheel_acceleration = 0.0
        self._last_physics_time = None
        self._spin_job = None

        self.wheel_photo = None
        self.pointer = None
        self.result_label = None

        self.canvas_w = 700
        self.canvas_h = 660
        self.cx = self.canvas_w // 2
        self.cy = self.canvas_h // 2 - 6
        self.wheel_size = 560
        self.outer_r = 245
        self.inner_r = 78
        self.base_start_angle = 270.0

        try:
            self._resample = Image.Resampling.BICUBIC
        except Exception:
            self._resample = Image.BICUBIC

        self.win = tk.Toplevel(parent)
        self.win.title("累进大奖抽奖")
        self.win.geometry("760x770")
        self.win.resizable(False, False)
        self.win.configure(bg="#2a4a3c")
        self.win.transient(parent)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

        # =========================
        # Progressive 豪华显示区
        # =========================
        self.progressive_main_var = tk.StringVar()
        self.progressive_second_var = tk.StringVar()
        self._refresh_progressive_header()

        self.jackpot_frame = tk.Frame(self.win, bg="#2a4a3c")
        self.jackpot_frame.pack(fill=tk.X, padx=18, pady=(12, 2))

        self.main_jackpot_frame = tk.Frame(
            self.jackpot_frame, bg="#1B1408",
            highlightbackground="#D4AF37", highlightthickness=3, bd=0
        )
        self.main_jackpot_frame.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(
            self.main_jackpot_frame, text="💎 大奖 💎", font=("Arial", 12, "bold"),
            bg="#1B1408", fg="#FFE07A"
        ).pack(padx=18, pady=(8, 0))
        self.main_amount_label = tk.Label(
            self.main_jackpot_frame, textvariable=self.progressive_main_var,
            font=("Arial", 22, "bold"), bg="#1B1408", fg="#FFD700"
        )
        self.main_amount_label.pack(padx=18, pady=(0, 10))

        self.second_jackpot_frame = tk.Frame(
            self.jackpot_frame, bg="#111827",
            highlightbackground="#7FDBFF", highlightthickness=3, bd=0
        )
        self.second_jackpot_frame.pack(side=tk.RIGHT, padx=(8, 0))
        tk.Label(
            self.second_jackpot_frame, text="✨ 二奖 ✨", font=("Arial", 12, "bold"),
            bg="#111827", fg="#AEEBFF"
        ).pack(padx=18, pady=(8, 0))
        self.second_amount_label = tk.Label(
            self.second_jackpot_frame, textvariable=self.progressive_second_var,
            font=("Arial", 20, "bold"), bg="#111827", fg="#7FDBFF"
        )
        self.second_amount_label.pack(padx=18, pady=(0, 10))

        self.select_frame = tk.Frame(self.win, bg="#2a4a3c")
        self.select_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            self.select_frame, text="请选择 1 - 6 中的一个数字：",
            font=("Arial", 18), bg="#2a4a3c", fg="white"
        ).pack(pady=30)

        btn_frame = tk.Frame(self.select_frame, bg="#2a4a3c")
        btn_frame.pack(pady=20)
        for i in range(1, 7):
            btn = tk.Button(
                btn_frame, text=str(i), font=("Arial", 20), width=4,
                command=lambda n=i: self.select_number(n)
            )
            btn.pack(side=tk.LEFT, padx=15)

    # ---------------------------- 辅助方法 ----------------------------
    def on_close(self):
        if self.callback:
            self.callback(0)
        if self.win and self.win.winfo_exists():
            self.win.destroy()

    def _refresh_progressive_header(self):
        self.progressive_main_var.set(f"${self.progressive_amount:,.2f}")
        self.progressive_second_var.set(f"${self.progressive_amount * 0.11:,.2f}")

    def _safe_font(self, size):
        # 尝试多个候选字体路径（按优先级）
        font_paths = [
            "C:/Windows/Fonts/seguiemj.ttf",     # Windows: Segoe UI Emoji (支持 emoji)
            "C:/Windows/Fonts/arial.ttf",        # Windows: Arial
            "/System/Library/Fonts/Apple Color Emoji.ttc",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "arial.ttf",
            "Arial.ttf"
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size=size)
            except:
                continue
        # 最后的保底：默认字体（可能很小或不可用）
        return ImageFont.load_default()

    # ---------------------------- 选择数字 ----------------------------
    def select_number(self, num):
        self.selected_number = num
        if self.select_frame.winfo_exists():
            self.select_frame.destroy()
        self.stage = "spinning_first"
        self.start_first_wheel()

    # ---------------------------- 轮盘阶段切换 ----------------------------
    def start_first_wheel(self):
        self.current_prizes = [1, 2, 3, 4, 5, 6]
        self._build_wheel(self.current_prizes)
        self._start_spin()

    def start_middle_wheel(self):
        self.current_prizes = [275, 500, 350, 250, "💎", 200, 450, 400, 300, "✨"]
        self._build_wheel(self.current_prizes)
        self._start_spin()

    def start_right_wheel(self):
        self.current_prizes = [150, 40, 100, 60, 120, 50, 75, 50]
        self._build_wheel(self.current_prizes)
        self._start_spin()

    # ---------------------------- 构建 / 动态刷新轮盘（文字始终水平） ----------------------------
    def _build_wheel(self, prizes):
        """创建 Canvas，初始化轮盘角度，清空高亮，刷新图像"""
        if self.wheel_canvas is not None and self.wheel_canvas.winfo_exists():
            self.wheel_canvas.destroy()

        self.wheel_canvas = tk.Canvas(
            self.win, width=self.canvas_w, height=self.canvas_h,
            bg="#2a4a3c", highlightthickness=0, bd=0
        )
        self.wheel_canvas.pack(pady=(10, 8))

        self.wheel_angle = 0.0
        self.highlight_index = -1
        self._refresh_wheel_image()

        # 绘制固定指针（三角形）
        self.pointer = self.wheel_canvas.create_polygon(
            self.cx - 18, self.cy - self.outer_r - 12,
            self.cx + 18, self.cy - self.outer_r - 12,
            self.cx,      self.cy - self.outer_r + 14,
            fill="#F8F4E8", outline="#B08B2D", width=2, tags=("pointer",)
        )
        self.wheel_canvas.tag_raise("pointer")

    def _refresh_wheel_image(self):
        """根据当前 wheel_angle 和高亮索引，重新绘制整个轮盘（文字始终水平）"""
        if not self.wheel_canvas or not self.wheel_canvas.winfo_exists():
            return
        if not self.current_prizes:
            return

        size = self.wheel_size
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx = cy = size / 2
        outer_r = self.outer_r
        inner_r = self.inner_r
        n = len(self.current_prizes)
        angle_step = 360.0 / n

        # 起始偏移角度（实现旋转效果）
        start_offset = self.base_start_angle + self.wheel_angle

        palette = [
            "#FF6B6B", "#4ECDC4", "#F7B801", "#845EC2",
            "#2ECC71", "#E67E22", "#3498DB", "#C0392B",
            "#16A085", "#8E44AD"
        ]

        # 外圈装饰底座（与扇形一起旋转，文字不旋转）
        draw.ellipse(
            (cx - outer_r - 28, cy - outer_r - 28, cx + outer_r + 28, cy + outer_r + 28),
            fill="#2D2214", outline="#D4AF37", width=6
        )
        draw.ellipse(
            (cx - outer_r - 14, cy - outer_r - 14, cx + outer_r + 14, cy + outer_r + 14),
            fill="#1A1A1A", outline="#8B6B24", width=2
        )

        # 绘制每个扇区
        for i, prize in enumerate(self.current_prizes):
            start_deg = start_offset + i * angle_step
            fill = palette[i % len(palette)]

            # 如果是高亮扇区，换用更亮的颜色
            if i == self.highlight_index:
                fill = "#FFE066"

            pts = [(cx, cy)]
            steps = max(10, int(angle_step / 4))
            for j in range(steps + 1):
                a = math.radians(start_deg + (angle_step * j / steps))
                x = cx + outer_r * math.cos(a)
                y = cy + outer_r * math.sin(a)
                pts.append((x, y))

            draw.polygon(pts, fill=fill)
            draw.line(pts[1:], fill="white", width=2)

            # 文字位置（扇区中线，半径方向约 70% 处）
            mid_deg = start_deg + angle_step / 2
            text_r = outer_r * 0.70
            mid_rad = math.radians(mid_deg)
            tx = cx + text_r * math.cos(mid_rad)
            ty = cy + text_r * math.sin(mid_rad)

            text = str(prize)
            font_size = 30
            font = self._safe_font(font_size)

            # 关键：文字始终水平正立，不旋转
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((tx - tw / 2, ty - th / 2), text, font=font, fill="black")

        # 中心圆与装饰
        draw.ellipse(
            (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
            fill="#2a4a3c", outline="#D4AF37", width=3
        )
        draw.ellipse(
            (cx - inner_r - 10, cy - inner_r - 10, cx + inner_r + 10, cy + inner_r + 10),
            outline="#F8F4E8", width=1
        )
        center_text = "?" if self.stage == "spinning_first" else "🎲"
        center_font = self._safe_font(28)
        bbox = draw.textbbox((0, 0), center_text, font=center_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((cx - tw / 2, cy - th / 2), center_text, fill="white", font=center_font)

        # 更新 PhotoImage
        self.wheel_photo = ImageTk.PhotoImage(img)

        # 替换 Canvas 上的图像
        self.wheel_canvas.delete("wheel")
        self.wheel_canvas.create_image(self.cx, self.cy, image=self.wheel_photo, tags=("wheel",))
        if self.pointer is not None:
            self.wheel_canvas.tag_raise("pointer")

    # ---------------------------- 旋转动画 ----------------------------
    def _start_spin(self):
        self.wheel_velocity = random.uniform(400, 700)
        self.wheel_acceleration = -random.uniform(60, 110)
        self._last_physics_time = time.time()
        self._physics_update()

    def _physics_update(self):
        if not self.wheel_canvas or not self.wheel_canvas.winfo_exists():
            return

        now = time.time()
        dt = min(0.04, now - self._last_physics_time)
        self._last_physics_time = now

        self.wheel_velocity += self.wheel_acceleration * dt
        if self.wheel_velocity < 0:
            self.wheel_velocity = 0

        self.wheel_angle = (self.wheel_angle + self.wheel_velocity * dt) % 360.0
        self._refresh_wheel_image()          # 每帧重绘，文字始终水平

        if self.wheel_velocity <= 0:
            self._finish_spin()
            return

        self._spin_job = self.wheel_canvas.after(16, self._physics_update)

    # ---------------------------- 停止并计算结果 ----------------------------
    def _finish_spin(self):
        n = len(self.current_prizes)
        angle_step = 360.0 / n

        pointer_angle = 270.0
        relative = (pointer_angle - self.wheel_angle - self.base_start_angle) % 360.0
        self.current_prize_index = int(relative // angle_step) % n
        prize = self.current_prizes[self.current_prize_index]

        # 高亮中奖扇区
        self.highlight_index = self.current_prize_index
        self._refresh_wheel_image()

        if isinstance(prize, int):
            self.win_value = prize
            msg = f"🎉 赢得 ${prize}！ 🎉"
        elif prize == "💎":
            self.win_value = self.progressive_amount
            msg = f"🎉 恭喜赢得累进大奖！ (${self.win_value:.2f}) 🎉"
        elif prize == "✨":
            self.win_value = self.progressive_amount * 0.11
            msg = f"🎉 恭喜赢得累进二奖！ (${self.win_value:.2f})！ 🎉"
        else:
            self.win_value = 0
            msg = "未中奖"

        if self.result_label is not None and self.result_label.winfo_exists():
            self.result_label.destroy()
        self.result_label = tk.Label(
            self.win, text=msg, font=("Arial", 16, "bold"),
            bg="#2a4a3c", fg="gold"
        )
        self.result_label.pack(pady=(6, 12))

        if self.stage == "spinning_first":
            if prize == self.selected_number:
                self.stage = "spinning_middle"
                self.wheel_canvas.destroy()
                self.result_label.destroy()
                self.result_label = None
                self.start_middle_wheel()
            else:
                self.stage = "spinning_right"
                self.wheel_canvas.destroy()
                self.result_label.destroy()
                self.result_label = None
                self.start_right_wheel()
        else:
            self.win.after(2500, self.finish)

    def finish(self):
        if self._spin_job is not None and self.wheel_canvas and self.wheel_canvas.winfo_exists():
            try:
                self.wheel_canvas.after_cancel(self._spin_job)
            except Exception:
                pass
            self._spin_job = None

        if self.win and self.win.winfo_exists():
            self.win.destroy()

        if self.callback:
            self.callback(self.win_value)

class ThreeCardPokerGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("终极三张牌扑克")
        self.geometry("1020x640+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = ThreeCardPokerGame()
        self.card_images = {}
        self.original_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []
        self.selected_chip = None
        self.chip_buttons = []
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False
        self.last_progressive_state = 0   # 保存上局是否下注Progressive
        self.win_details = {
            "ante": 0,
            "blind": 0,
            "pair_plus": 0,
            "play": 0,
            "progressive": 0
        }
        self.bet_widgets = {}
        self.progressive_bet_var = tk.IntVar(value=0)  # 是否下注Progressive
        
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def on_close(self):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
        
    def _load_assets(self):
        card_size = (100, 140)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        if not hasattr(self, 'current_poker_folder'):
            self.current_poker_folder = random.choice(['Poker1', 'Poker2'])
        else:
            self.current_poker_folder = 'Poker2' if self.current_poker_folder == 'Poker1' else 'Poker1'
        
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card', self.current_poker_folder)
        
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club'
        }

        self.original_images = {}
        
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)
            self.original_images["back"] = back_img_orig
            back_img = back_img_orig.resize(card_size)
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception as e:
            print(f"Error loading back image: {e}")
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
        
        for suit in SUITS:
            for rank in RANKS:
                suit_name = suit_mapping.get(suit, suit)
                filename = f"{suit_name}{rank}.png"
                path = os.path.join(card_dir, filename)
                
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        self.original_images[(suit, rank)] = img
                        img_resized = img.resize(card_size)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        bbox = draw.textbbox((0, 0), text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                        x = (card_size[0] - text_width) / 2
                        y = (card_size[1] - text_height) / 2
                        draw.text((x, y), text, fill="white", font=font)
                        self.original_images[(suit, rank)] = img_orig
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading card image {path}: {e}")
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    text = "Error"
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    x = (card_size[0] - text_width) / 2
                    y = (card_size[1] - text_height) / 2
                    draw.text((x, y), text, fill="white", font=font)
                    self.original_images[(suit, rank)] = img_orig
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)

    def add_chip_to_bet(self, bet_type):
        if not self.selected_chip:
            return
            
        chip_text = self.selected_chip.replace('$', '')
        if 'K' in chip_text:
            chip_value = float(chip_text.replace('K', '')) * 1000
        else:
            chip_value = float(chip_text)
        
        bet_limits = {
            "ante": 10000,       # 底注上限10000
            "pair_plus": 10000,  # 对子加注上限10000
        }
        
        if bet_type == "ante":
            current = float(self.ante_var.get())
            limit = bet_limits["ante"]
            if current >= limit:
                messagebox.showwarning("下注限制", "底注已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                messagebox.showwarning("下注限制", f"底注已达上限，自动调整为 {limit}")
                self.ante_var.set(str(limit))
            else:
                self.ante_var.set(str(int(new_amount)))
            # 盲注自动同步
            self.blind_var.set(self.ante_var.get())
        elif bet_type == "pair_plus":
            current = float(self.pair_plus_var.get())
            limit = bet_limits["pair_plus"]
            if current >= limit:
                messagebox.showwarning("下注限制", "对子加注已满，不能再下注！")
                return
            new_amount = current + chip_value
            if new_amount > limit:
                messagebox.showwarning("下注限制", f"对子加注已达上限，自动调整为 {limit}")
                self.pair_plus_var.set(str(limit))
            else:
                self.pair_plus_var.set(str(int(new_amount)))
    
    def _create_widgets(self):
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 庄家区域
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=50, y=40, width=400, height=230)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 提示文字
        self.ante_info_label = tk.Label(
            table_canvas, 
            text="庄家需有Q高或以上才合格\n不合格的，底注退还", 
            font=('Arial', 26), 
            bg='#35654d', 
            fg='#FFD700'
        )
        self.ante_info_label.place(relx=0.47, y=275, anchor='n')
        
        # 玩家区域
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=50, y=360, width=400, height=230)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=250, padx=10, pady=5)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=5)
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 18),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=5)
        
        self.stage_label = tk.Label(
            info_frame, 
            text="下注阶段",
            font=('Arial', 18, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.RIGHT, padx=20, pady=5)
        
        # Progressive显示
        progressive_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        progressive_frame.pack(fill=tk.X, pady=5)
        progressive_frame.columnconfigure(0, weight=1)
        progressive_frame.columnconfigure(1, weight=2)
        progressive_frame.columnconfigure(2, weight=1)
        
        progressive_label = tk.Label(progressive_frame, text="累进大奖:", 
                                font=('Arial', 18), bg='#2a4a3c', fg='gold')
        progressive_label.grid(row=0, column=0, sticky='w', padx=(10, 0), pady=5)
        
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
        
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs = [
            ('$10', '#ffa500', 'black'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black'),
            ("$2.5K", '#ff0000', 'white'),
        ]
        
        self.chip_buttons = []
        self.chip_texts = {}
        for text, bg_color, fg_color in chip_configs:
            chip_canvas = tk.Canvas(chip_row, width=57, height=57, bg='#2a4a3c', highlightthickness=0)
            chip_canvas.create_oval(2, 2, 55, 55, fill=bg_color, outline='black')
            chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 14, 'bold'))
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text
        
        self.select_chip("$10")
        
        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=5)
        
        # Progressive选项（5元）
        prog_check_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        prog_check_frame.pack(fill=tk.X, padx=20, pady=5)
        self.progressive_cb = tk.Checkbutton(
            prog_check_frame, text="累进大奖 ($5)", 
            variable=self.progressive_bet_var, font=('Arial', 14),
            bg='#2a4a3c', fg='white', selectcolor='#35654d'
        )
        self.progressive_cb.pack(side=tk.LEFT)
        
        # Pair Plus
        pair_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        pair_frame.pack(fill=tk.X, padx=20, pady=5)
        pair_plus_label = tk.Label(pair_frame, text="对子加注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        pair_plus_label.pack(side=tk.LEFT)
        self.pair_plus_var = tk.StringVar(value="0")
        self.pair_plus_display = tk.Label(pair_frame, textvariable=self.pair_plus_var, font=('Arial', 14), 
                                        bg='white', fg='black', width=6, relief=tk.SUNKEN, padx=5)
        self.pair_plus_display.pack(side=tk.LEFT, padx=5)
        self.pair_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("pair_plus"))
        self.bet_widgets["pair_plus"] = self.pair_plus_display
            
        # 底注和盲注行
        ante_blind_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        ante_blind_frame.pack(fill=tk.X, padx=60, pady=5)
        
        # 底注
        ante_label = tk.Label(ante_blind_frame, text="底注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        ante_label.pack(side=tk.LEFT, padx=0)
        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(ante_blind_frame, textvariable=self.ante_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=6, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display
        
        # 盲注（自动同步）
        blind_label = tk.Label(ante_blind_frame, text=" = ", font=('Arial', 14), bg='#2a4a3c', fg='white')
        blind_label.pack(side=tk.LEFT, padx=(0))
        self.blind_var = tk.StringVar(value="0")
        self.blind_display = tk.Label(ante_blind_frame, textvariable=self.blind_var, font=('Arial', 14), 
                                     bg='white', fg='black', width=6, relief=tk.SUNKEN, padx=5)
        self.blind_display.pack(side=tk.LEFT, padx=5)
        # 盲注自动跟随底注，不可手动点击
        self.bet_widgets["blind"] = self.blind_display
        
        # Blind 文本标签
        blind_label = tk.Label(ante_blind_frame, text=": 盲注", font=('Arial', 14), bg='#2a4a3c', fg='white')
        blind_label.pack(side=tk.LEFT, padx=5)

        # 加注显示区域
        play_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        play_frame.pack(fill=tk.X, padx=60, pady=5)
        self.play_label = tk.Label(play_frame, text="加注:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        self.play_label.pack(side=tk.LEFT)
        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(play_frame, textvariable=self.play_var, font=('Arial', 14), 
                                   bg='white', fg='black', width=6, relief=tk.SUNKEN, padx=5)
        self.play_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["play"] = self.play_display
        
        # 操作按钮区
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X, pady=5)
        
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)
        
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重设金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(fill=tk.X, pady=(0, 10))
        
        # 本局下注和上局获胜
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 0))
        
        self.current_bet_label = tk.Label(
            bet_info_frame, text="本局下注: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        
        self.last_win_label = tk.Label(
            bet_info_frame, text="上局获胜: $0.00", 
            font=('Arial', 12), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(pady=5, padx=10, anchor='w', side=tk.LEFT)
        
        rules_btn = tk.Button(
            bet_info_frame, text="ℹ️", 
            command=self.show_game_instructions, 
            font=('Arial', 8), bg='#4B8BBE', fg='white', width=2, height=1
        )
        rules_btn.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def show_game_instructions(self):
        win = tk.Toplevel(self)
        win.title("终极三张牌扑克游戏规则")
        win.geometry("750x650")
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        rules_text = """
        终极三张牌扑克 游戏规则

        1. 下注阶段:
           - 底注和盲注必须相同（金额自动同步）
           - 可选择对子加注和累进大奖（$5）
           - 点击"开始游戏"开始

        2. 发牌与决策:
           - 玩家和庄家各发三张牌，玩家牌朝上
           - 玩家可选择:
               * 弃牌：输掉底注、盲注，保留对子加注和累进大奖结果
               * 下注1倍：加注金额等于底注
               * 下注3倍：只有当手牌为"一对"或更好时才可选用

        3. 结算规则:
           - 庄家必须有一张Q高或更好才合格
           
           - 底注:
               * 庄家不合格: 退还
               * 庄家合格且玩家赢: 1:1
               * 庄家合格且玩家输: 输
               * 平局: 退还
               
           - 加注:
               * 玩家赢: 1:1
               * 玩家输: 输
               * 平局: 退还
               
           - 盲注: 按支付表
               
           - 对子加注: 按原支付表（与庄家无关）
           
           - 累进大奖:
               * 需下注$5
               * 只有当庄家手牌为顺子或以上牌型时触发
               * 触发后玩家需要点击“累进挑战”按钮进行抽奖
               
        4. 抽奖轮盘规则:
           - 玩家先选择1-4中的一个数字
           - 第一轮抽1-4，若抽中玩家数字则进入中级轮盘，否则进入普通轮盘
           - 中级轮盘包含金额和符号（💎=100%奖池，💸=11%奖池）
           - 普通轮盘为固定金额
        """
        
        tk.Label(content_frame, text=rules_text, font=('微软雅黑', 11),
                 bg='#F0F0F0', justify=tk.LEFT, padx=10, pady=10).pack(fill=tk.X)
        
        # 支付表
        tk.Label(content_frame, text="对子加注支付表", font=('微软雅黑', 12, 'bold'),
                 bg='#F0F0F0').pack(anchor='w', padx=10, pady=(10,0))
        pp_frame = tk.Frame(content_frame, bg='#F0F0F0')
        pp_frame.pack(fill=tk.X, padx=20, pady=5)
        headers = ["牌型", "赔率"]
        data = [
            ("迷你皇家同花顺", "100:1"),
            ("同花顺", "40:1"),
            ("三条", "30:1"),
            ("顺子", "6:1"),
            ("同花", "3:1"),
            ("对子", "1:1"),
        ]
        for col, h in enumerate(headers):
            tk.Label(pp_frame, text=h, font=('微软雅黑', 10, 'bold'),
                     bg='#4B8BBE', fg='white', padx=10, pady=5).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r, row_data in enumerate(data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(pp_frame, text=txt, font=('微软雅黑', 10),
                         bg=bg, padx=10, pady=5).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(headers)):
            pp_frame.columnconfigure(c, weight=1)
        
        tk.Label(content_frame, text="盲注支付表（打败庄家时）", font=('微软雅黑', 12, 'bold'),
                 bg='#F0F0F0').pack(anchor='w', padx=10, pady=(10,0))
        blind_frame = tk.Frame(content_frame, bg='#F0F0F0')
        blind_frame.pack(fill=tk.X, padx=20, pady=5)
        headers = ["牌型", "赔率"]
        blind_data = [
            ("迷你皇家同花顺", "100:1"),
            ("同花顺", "20:1"),
            ("三条", "10:1"),
            ("顺子", "1:1"),
            ("同花", "1:1"),
            ("一对或更少", "平局"),
        ]
        for col, h in enumerate(headers):
            tk.Label(blind_frame, text=h, font=('微软雅黑', 10, 'bold'),
                     bg='#4B8BBE', fg='white', padx=10, pady=5).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        for r, row_data in enumerate(blind_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(blind_frame, text=txt, font=('微软雅黑', 10),
                         bg=bg, padx=10, pady=5).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)
        for c in range(len(headers)):
            blind_frame.columnconfigure(c, weight=1)
        
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    
    def select_chip(self, chip_text):
        self.selected_chip = chip_text
        for chip in self.chip_buttons:
            chip.delete("highlight")
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item_id)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            for item_id in chip.find_all():
                t = chip.type(item_id)
                if t == 'text':
                    text_id = item_id
                elif t == 'oval':
                    oval_id = item_id
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                x1, y1, x2, y2 = chip.coords(oval_id)
                chip.create_oval(x1, y1, x2, y2, outline='gold', width=3, tags="highlight")
                break
    
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
    
    def update_hand_labels(self):
        if self.game.player_hand:
            player_eval = evaluate_three_card_hand(self.game.player_hand)
            player_hand_name = HAND_RANK_NAMES[player_eval[0]] if player_eval else ""
            self.player_label.config(text=f"玩家 - {player_hand_name}" if player_hand_name else "玩家")
        if self.game.stage == "showdown" or self.game.folded:
            if self.game.dealer_hand:
                dealer_eval = evaluate_three_card_hand(self.game.dealer_hand)
                dealer_hand_name = HAND_RANK_NAMES[dealer_eval[0]] if dealer_eval else ""
                self.dealer_label.config(text=f"庄家 - {dealer_hand_name}" if dealer_hand_name else "庄家")
    
    def disable_action_buttons(self):
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            widget.config(state=tk.DISABLED)
    
    def enable_action_buttons(self):
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            widget.config(state=tk.NORMAL)
    
    def start_game(self):
        try:
            self.ante = int(self.ante_var.get())
            self.blind = int(self.blind_var.get())
            self.pair_plus = int(self.pair_plus_var.get())
            self.progressive_bet = 5 if self.progressive_bet_var.get() == 1 else 0
            self.last_progressive_state = self.progressive_bet_var.get()
            
            # 检查底注盲注是否相同
            if self.ante != self.blind:
                messagebox.showerror("错误", "底注和盲注必须相等！")
                self.blind_var.set(self.ante_var.get())
                self.blind = self.ante
                return
            
            # 检查金额限制
            if self.ante > 10000:
                messagebox.showwarning("下注限制", "底注不能超过$10,000")
                self.ante_var.set("10000")
                self.blind_var.set("10000")
                self.ante = 10000
                self.blind = 10000
                return
            if self.pair_plus > 10000:
                messagebox.showwarning("下注限制", "对子加注不能超过$10,000")
                self.pair_plus_var.set("10000")
                self.pair_plus = 10000
                return
            
            if self.ante < 5 and self.pair_plus < 5:
                messagebox.showerror("错误", "底注/对子加注至少需要5元")
                return
            
            total_bet = self.ante + self.blind + self.pair_plus + self.progressive_bet
            if self.balance < total_bet:
                messagebox.showwarning("警告", "余额不足")
                return
            
            self.balance -= total_bet
            self.update_balance()
            
            self.last_win_label.config(text="上局获胜: $0.00")
            self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
            
            self.game.reset_game()
            self.game.deal_initial()
            self.game.ante = self.ante
            self.game.blind = self.blind
            self.game.pair_plus = self.pair_plus
            self.game.progressive_bet = self.progressive_bet
            
            # 清空卡片区域
            for widget in self.dealer_cards_frame.winfo_children():
                widget.destroy()
            for widget in self.player_cards_frame.winfo_children():
                widget.destroy()
            
            self.animation_queue = []
            self.animation_in_progress = False
            self.active_card_labels = []
            self.card_positions = {}
            
            for i in range(3):
                card_id = f"player_{i}"
                self.card_positions[card_id] = {"current": (50, 50), "target": (i * 120, 0)}
                self.animation_queue.append(card_id)
            for i in range(3):
                card_id = f"dealer_{i}"
                self.card_positions[card_id] = {"current": (50, 50), "target": (i * 120, 0)}
                self.animation_queue.append(card_id)
            
            self.animate_deal()
            
            self.stage_label.config(text="阶段: 决策")
            self.status_label.config(text="做出决策: 弃牌 或 下注1倍/3倍")
            
            # 禁用下注控件
            self.ante_display.unbind("<Button-1>")
            self.pair_plus_display.unbind("<Button-1>")
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
            self.progressive_cb.config(state=tk.DISABLED)
            
            if self.ante == 0:
                self.game.stage = "showdown"
                self.stage_label.config(text="阶段: 摊牌")
                self.status_label.config(text="摊牌中...")
                self.after(5000, self.show_showdown)
                self.start_button.config(state=tk.DISABLED)
                self.reset_bets_button.config(state=tk.DISABLED)
                return
            
            # 创建决策按钮
            for widget in self.action_frame.winfo_children():
                widget.destroy()
            action_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
            action_button_frame.pack(pady=5)
            
            self.fold_button = tk.Button(
                action_button_frame, text="弃牌",
                command=self.fold_action,
                state=tk.DISABLED,
                font=('Arial', 14), bg='#F44336', fg='white', width=10
            )
            self.fold_button.pack(side=tk.LEFT, padx=(0, 10))
            
            self.play_button_1x = tk.Button(
                action_button_frame, text="下注1倍",
                command=lambda: self.play_action(1),
                state=tk.DISABLED,
                font=('Arial', 14), bg='#4CAF50', fg='white', width=10
            )
            self.play_button_1x.pack(side=tk.LEFT, padx=(0, 10))
            
            # 3倍按钮初始禁用，等玩家牌翻开后根据牌型启用
            self.play_button_3x = tk.Button(
                action_button_frame, text="下注3倍",
                command=lambda: self.play_action(3),
                state=tk.DISABLED,
                font=('Arial', 14), bg='#2196F3', fg='white', width=10
            )
            self.play_button_3x.pack(side=tk.LEFT)
            
        except ValueError:
            messagebox.showerror("错误", "请输入有效的下注金额")
    
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            self.after(500, self.reveal_player_cards)
            return
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        if card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hand[idx] if idx < len(self.game.player_hand) else None
        else:
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hand[idx] if idx < len(self.game.dealer_hand) else None
        
        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(x=self.card_positions[card_id]["current"][0],
                         y=self.card_positions[card_id]["current"][1] + 20)
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        self.active_card_labels.append(card_label)
        self.animate_card_move(card_label)
    
    def animate_card_move(self, card_label):
        if not hasattr(card_label, "target_pos") or card_label not in self.active_card_labels:
            return
        try:
            current_x, current_y = card_label.winfo_x(), card_label.winfo_y()
            target_x, target_y = card_label.target_pos
            dx = target_x - current_x
            dy = target_y - current_y
            distance = math.sqrt(dx**2 + dy**2)
            if distance < 5:
                card_label.place(x=target_x, y=target_y)
                card_label.is_moving = False
                if card_label.target_pos == (50, 50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                self.after(100, self.animate_deal)
                return
            step_x = dx * 0.2
            step_y = dy * 0.2
            new_x = current_x + step_x
            new_y = current_y + step_y
            card_label.place(x=new_x, y=new_y)
            self.after(20, lambda: self.animate_card_move(card_label))
        except tk.TclError:
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)
            return
    
    def reveal_player_cards(self):
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["player"][i] = True
        self.update_hand_labels()
        
        # 检查牌型，决定是否启用3倍按钮
        player_rank, _ = evaluate_three_card_hand(self.game.player_hand)
        can_3x = (player_rank >= 2)  # 对子或更好
        
        if hasattr(self, 'fold_button') and self.fold_button.winfo_exists():
            self.fold_button.config(state=tk.NORMAL)
        if hasattr(self, 'play_button_1x') and self.play_button_1x.winfo_exists():
            self.play_button_1x.config(state=tk.NORMAL)
        if hasattr(self, 'play_button_3x') and self.play_button_3x.winfo_exists():
            if can_3x:
                self.play_button_3x.config(state=tk.NORMAL)
            else:
                self.play_button_3x.config(state=tk.DISABLED, text="下注3倍")
    
    def reveal_dealer_cards(self):
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                self.game.cards_revealed["dealer"][i] = True
        self.update_hand_labels()
    
    def flip_card_animation(self, card_label):
        card = card_label.card
        front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        self.animate_flip(card_label, front_img, 0)
    
    def animate_flip(self, card_label, front_img, step):
        steps = 10
        if step > steps:
            card_label.is_face_up = True
            return
        if step <= steps / 2:
            width = 100 - (step * 20)
            if width <= 0:
                width = 1
            card_label.config(image=self.back_image)
        else:
            width = (step - steps / 2) * 20
            if width <= 0:
                width = 1
            card_label.config(image=front_img)
        card_label.place(width=width)
        step += 1
        card_label.after(50, lambda: self.animate_flip(card_label, front_img, step))
    
    def play_action(self, multiplier):
        """multiplier 为1或3"""
        play_bet = self.game.ante * multiplier
        if play_bet > self.balance:
            messagebox.showerror("错误", "余额不足")
            return
        self.balance -= play_bet
        self.update_balance()
        self.game.play_bet = play_bet
        self.play_var.set(str(play_bet))
        
        total_bet = self.game.ante + self.game.blind + self.game.pair_plus + play_bet + self.game.progressive_bet
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        # 禁用所有决策按钮
        if hasattr(self, 'fold_button'): self.fold_button.config(state=tk.DISABLED)
        if hasattr(self, 'play_button_1x'): self.play_button_1x.config(state=tk.DISABLED)
        if hasattr(self, 'play_button_3x'): self.play_button_3x.config(state=tk.DISABLED)
        
        self.game.stage = "showdown"
        self.stage_label.config(text="阶段: 摊牌")
        self.status_label.config(text="摊牌中...")
        self.after(1000, self.show_showdown)
    
    def fold_action(self):
        self.game.folded = True
        self.status_label.config(text="您已弃牌 ~ 游戏结束")
        
        # 禁用所有决策按钮
        if hasattr(self, 'fold_button'): self.fold_button.config(state=tk.DISABLED)
        if hasattr(self, 'play_button_1x'): self.play_button_1x.config(state=tk.DISABLED)
        if hasattr(self, 'play_button_3x'): self.play_button_3x.config(state=tk.DISABLED)

        ante_bet = self.game.ante
        blind_bet = self.game.blind
        pair_plus_bet = self.game.pair_plus

        self.ante_var.set("0")
        self.blind_var.set("0")
        self.play_var.set("0")

        self.reveal_dealer_cards()
        self.update_hand_labels()

        # 结算Pair Plus
        player_eval = evaluate_three_card_hand(self.game.player_hand)
        pair_plus_win = 0
        if player_eval[0] in PAIR_PLUS_PAYOUT:
            payout = PAIR_PLUS_PAYOUT[player_eval[0]]
            pair_plus_win = pair_plus_bet * (payout + 1)
            self.balance += pair_plus_win
            self.update_balance()
            self.pair_plus_var.set(str(int(pair_plus_win)))
        else:
            self.pair_plus_var.set("0")

        # 更新Progressive贡献（总下注1% + 若下了progressive加4.76）
        self.update_progressive()

        # 设置背景色
        self.ante_display.config(bg='white')
        self.blind_display.config(bg='white')
        self.pair_plus_display.config(bg='gold' if pair_plus_win > 0 else 'white')

        total_win = pair_plus_win
        self.last_win = total_win
        self.last_win_label.config(text=f"上局获胜: ${total_win:.2f}")

        # 累进大奖触发（只有当玩家下注了progressive且庄家为顺子及以上）
        if self.game.progressive_bet > 0:
            dealer_rank, _ = evaluate_three_card_hand(self.game.dealer_hand)
            if dealer_rank in (4, 5, 6, 7):
                # 取消自动重置计时器
                if self.auto_reset_timer:
                    self.after_cancel(self.auto_reset_timer)
                    self.auto_reset_timer = None
                # 显示累进挑战按钮，而不是直接抽奖
                self.show_progressive_challenge_button()
                return  # 等待玩家点击挑战，不继续显示重启按钮
        
        # 如果没有触发累进大奖，直接显示重启按钮
        self.show_restart_button()
    
    def show_showdown(self):
        self.reveal_dealer_cards()
        self.update_hand_labels()

        winnings, details = self.calculate_winnings()
        self.last_win = winnings
        self.balance += winnings
        self.update_balance()

        self.ante_var.set(str(int(details["ante"])))
        self.blind_var.set(str(int(details["blind"])))
        self.pair_plus_var.set(str(int(details["pair_plus"])))
        self.play_var.set(str(int(details["play"])))

        # 背景色
        for bet_type in ["ante", "blind", "pair_plus", "play"]:
            widget = self.bet_widgets.get(bet_type)
            if not widget:
                continue
            win_amount = details[bet_type]
            if bet_type == "ante":
                bet_amt = self.game.ante
            elif bet_type == "blind":
                bet_amt = self.game.blind
            elif bet_type == "pair_plus":
                bet_amt = self.game.pair_plus
            else:
                bet_amt = self.game.play_bet
            if win_amount > bet_amt:
                widget.config(bg='gold')
            elif win_amount == bet_amt and bet_amt > 0:
                widget.config(bg='light blue')
            else:
                widget.config(bg='white')

        # 更新Progressive贡献
        self.update_progressive()

        # 累进大奖触发（只有当玩家下注了progressive且庄家为顺子及以上）
        if self.game.progressive_bet > 0:
            dealer_rank, _ = evaluate_three_card_hand(self.game.dealer_hand)
            if dealer_rank in (4, 5, 6, 7):
                # 取消自动重置计时器
                if self.auto_reset_timer:
                    self.after_cancel(self.auto_reset_timer)
                    self.auto_reset_timer = None
                # 显示累进挑战按钮，而不是直接抽奖
                self.show_progressive_challenge_button()
                return  # 等待玩家点击挑战，不继续显示重启按钮
        
        # 没有触发累进大奖，显示重启按钮
        self.show_restart_button()
    
    def calculate_winnings(self):
        winnings = 0
        details = {
            "ante": 0,
            "blind": 0,
            "pair_plus": 0,
            "play": 0,
            "progressive": 0
        }
        
        # 1. Pair Plus
        player_eval = evaluate_three_card_hand(self.game.player_hand)
        if player_eval[0] in PAIR_PLUS_PAYOUT:
            payout = PAIR_PLUS_PAYOUT[player_eval[0]]
            pair_plus_win = self.game.pair_plus * (payout + 1)
            winnings += pair_plus_win
            details["pair_plus"] = pair_plus_win
        else:
            details["pair_plus"] = 0
        
        # 2. 牌型比较（全局使用）
        dealer_qualifies = self.game.dealer_qualifies()
        comparison = compare_hands(self.game.player_hand, self.game.dealer_hand)
        
        # ----- 底注（受庄家合格影响）-----
        ante_win = 0
        if not dealer_qualifies:
            ante_win = self.game.ante          # 庄家不合格 → 退还底注
        else:
            if comparison > 0:                # 玩家赢
                ante_win = self.game.ante * 2
            elif comparison == 0:             # 平局
                ante_win = self.game.ante
            else:                             # 玩家输
                ante_win = 0
        winnings += ante_win
        details["ante"] = ante_win
        
        # ----- 加注（不受庄家合格影响，只按牌型比较）-----
        play_win = 0
        if comparison > 0:
            play_win = self.game.play_bet * 2
        elif comparison == 0:
            play_win = self.game.play_bet
        else:
            play_win = 0
        winnings += play_win
        details["play"] = play_win
        
        # ----- 盲注（只按牌型比较，不依赖庄家合格）-----
        blind_win = 0
        if comparison > 0:                    # 玩家牌型 > 庄家牌型
            hand_rank, _ = player_eval
            payout = BLIND_PAYOUT.get(hand_rank, 0)
            blind_win = self.game.blind * (payout + 1)   # 包含本金
        elif comparison == 0:                 # 平局 → Push
            blind_win = self.game.blind
        else:                                 # 玩家牌型 < 庄家牌型 → 输
            blind_win = 0
        winnings += blind_win
        details["blind"] = blind_win
        
        return winnings, details
    
    def update_progressive(self):
        # 总下注 = 底注+盲注+加注+对子加注+progressive下注
        total_bet = self.game.ante + self.game.blind + self.game.play_bet + self.game.pair_plus + self.game.progressive_bet
        # 1% 贡献
        contribution = total_bet * 0.01
        if self.game.progressive_bet > 0:
            contribution += 4.76  # 额外加4.76
        self.game.progressive_amount += contribution
        min_prog = 201074.31
        if self.game.progressive_amount < min_prog:
            self.game.progressive_amount = min_prog
        self.progressive_amount_var.set(f"${self.game.progressive_amount:.2f}")
        save_progressive(self.game.progressive_amount)
    
    def show_progressive_challenge_button(self):
        """显示累进挑战按钮，取代再来一局按钮"""
        # 清空 action_frame 中的所有控件
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        # 创建累进挑战按钮
        challenge_btn = tk.Button(
            self.action_frame, 
            text="🔥 累进挑战 🔥", 
            command=self.start_progressive_challenge,
            font=('Arial', 14, 'bold'), 
            bg='#FF6600', 
            fg='white', 
            width=15,
            relief=tk.RAISED
        )
        challenge_btn.pack(pady=20)
        
        # 更新状态
        self.status_label.config(text="庄家手牌满足条件！点击「累进挑战」参与抽奖")
        # 确保没有倒计时运行
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
    
    def start_progressive_challenge(self):
        """玩家点击累进挑战按钮后，打开抽奖窗口"""
        # 禁用按钮，防止重复点击
        for widget in self.action_frame.winfo_children():
            widget.config(state=tk.DISABLED)
        
        self.status_label.config(text="正在进行累进挑战抽奖...")
        # 打开抽奖窗口
        ProgressiveWheelWindow(self, self.game.progressive_amount, self.on_progressive_challenge_complete)
    
    def on_progressive_challenge_complete(self, award_amount):
        """抽奖结束回调，更新余额和奖池，然后显示再来一局按钮"""
        if award_amount > 0:
            # 更新余额
            self.balance += award_amount
            self.update_balance()
            # 从累进奖池中扣除中奖金额
            self.game.progressive_amount -= award_amount
            min_prog = 201074.31
            if self.game.progressive_amount < min_prog:
                self.game.progressive_amount = min_prog
            self.progressive_amount_var.set(f"${self.game.progressive_amount:.2f}")
            save_progressive(self.game.progressive_amount)
            # 更新上局获胜金额显示
            self.last_win += award_amount
            self.last_win_label.config(text=f"上局获胜: ${self.last_win:.2f}")
            self.status_label.config(text=f"累进挑战获得 ${award_amount:.2f}！")
        else:
            self.status_label.config(text="累进挑战未中奖")
        
        # 显示再来一局按钮并启动30秒倒计时
        self.show_restart_button()
    
    def show_restart_button(self):
        # 取消任何现有的计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 清空 action_frame 中的所有控件
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        
        # 创建再来一局按钮
        restart_btn = tk.Button(
            self.action_frame, 
            text="再来一局", 
            command=self.reset_game,
            font=('Arial', 14), 
            bg='#2196F3', 
            fg='white', 
            width=15
        )
        restart_btn.pack(pady=5)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        
        # 重新设置30秒自动重置计时器
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def animate_collect_cards(self, auto_reset):
        self.disable_action_buttons()
        self.flip_all_to_back()
        self.after(1000, lambda: self.animate_move_cards_out(auto_reset))
    
    def flip_all_to_back(self):
        self.flipping_cards = []
        for card_label in self.active_card_labels:
            if card_label.is_face_up:
                self.flipping_cards.append(card_label)
        if not self.flipping_cards:
            self.after(500, lambda: self.animate_move_cards_out(False))
            return
        self.animate_flip_to_back_step(0)
    
    def animate_flip_to_back_step(self, step):
        if step >= 10:
            for card_label in self.flipping_cards:
                card_label.config(image=self.back_image)
                card_label.is_face_up = False
            self.after(500, lambda: self.animate_move_cards_out(False))
            return
        width = 100 - (step * 10) if step < 5 else (step - 5) * 10
        if width <= 0:
            width = 1
        for card_label in self.flipping_cards:
            card_label.place(width=width)
        step += 1
        self.after(50, lambda: self.animate_flip_to_back_step(step))
    
    def animate_move_cards_out(self, auto_reset):
        if not self.active_card_labels:
            self._do_reset(auto_reset)
            return
        for card_label in self.active_card_labels:
            card_label.target_pos = (1200, card_label.winfo_y())
        self.animate_card_out_step(auto_reset)
    
    def animate_card_out_step(self, auto_reset):
        all_done = True
        for card_label in self.active_card_labels[:]:
            if not hasattr(card_label, 'target_pos'):
                continue
            current_x = card_label.winfo_x()
            target_x, target_y = card_label.target_pos
            dx = target_x - current_x
            if abs(dx) < 5:
                card_label.place(x=target_x, y=target_y)
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
            self._do_reset(auto_reset)
    
    def reset_game(self, auto_reset=False):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if self.active_card_labels:
            self.disable_action_buttons()
            self.animate_move_cards_out(auto_reset)
            return
        self._do_reset(auto_reset)
    
    def reset_bets(self):
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.pair_plus_var.set("0")
        self.status_label.config(text="已重置所有下注金额")
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.ante_display.config(bg='#FFCDD2')
        self.blind_display.config(bg='#FFCDD2')
        self.pair_plus_display.config(bg='#FFCDD2')
        self.after(500, lambda: [self.ante_display.config(bg='white'),
                                 self.blind_display.config(bg='white'),
                                 self.pair_plus_display.config(bg='white')])
    
    def _do_reset(self, auto_reset=False):
        self._load_assets()
        self.game.reset_game()
        self.stage_label.config(text="下注阶段")
        self.status_label.config(text="设置下注金额并开始游戏")
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")
        self.ante_var.set("0")
        self.blind_var.set("0")
        self.pair_plus_var.set("0")
        self.play_var.set("0")
        self.progressive_bet_var.set(self.last_progressive_state)
        for widget in self.bet_widgets.values():
            widget.config(bg='white')
        self.active_card_labels = []
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.pair_plus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("pair_plus"))
        for chip in self.chip_buttons:
            text = self.chip_texts[chip]
            chip.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
        for widget in self.action_frame.winfo_children():
            widget.destroy()
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=5)
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重设金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        self.progressive_cb.config(state=tk.NORMAL)
        self.current_bet_label.config(text="本局下注: $0.00")
        if auto_reset:
            self.status_label.config(text="30秒已到，自动开始新游戏")
            self.after(1500, lambda: self.status_label.config(text="设置下注金额并开始游戏"))
        else:
            self.status_label.config(text="设置下注金额并开始游戏")
    
    def show_card_sequence(self, event):
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示", "没有牌序信息")
            return
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600")
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        cut_pos = self.game.deck.start_pos
        cut_label = tk.Label(win, text=f"本局切牌位置: {cut_pos + 1}", 
                            font=('Arial', 14, 'bold'), bg='light blue')
        cut_label.pack(pady=(10, 5), fill=tk.X)
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        small_size = (60, 90)
        small_images = {}
        for i, card in enumerate(self.game.deck.full_deck):
            key = (card.suit, card.rank)
            if key in self.original_images:
                small_img = self.original_images[key].resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small_img)
            else:
                if "back" in self.original_images:
                    small_img = self.original_images["back"].resize(small_size, Image.LANCZOS)
                    small_images[i] = ImageTk.PhotoImage(small_img)
                else:
                    small_img = Image.new('RGB', small_size, 'black')
                    small_images[i] = ImageTk.PhotoImage(small_img)
        for row in range(7):
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)
            cards_in_row = 8 if row < 6 else 4
            for col in range(cards_in_row):
                card_index = row * 8 + col
                if card_index >= 52:
                    break
                card_container = tk.Frame(row_frame, bg='#f0f0f0')
                card_container.grid(row=0, column=col, padx=5, pady=5)
                is_cut = card_index == self.game.deck.start_pos
                bg_color = 'light blue' if is_cut else '#f0f0f0'
                if card_index in small_images:
                    card_label = tk.Label(card_container, image=small_images[card_index], bg=bg_color,
                                         borderwidth=1, relief="solid")
                    card_label.image = small_images[card_index]
                    card_label.pack()
                else:
                    card = self.game.deck.full_deck[card_index]
                    card_label = tk.Label(card_container, text=f"{card.rank}{card.suit}",
                                         bg=bg_color, width=8, height=3, borderwidth=1, relief="solid")
                    card_label.pack()
                pos_label = tk.Label(card_container, text=str(card_index+1), bg=bg_color, font=('Arial', 9))
                pos_label.pack()
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)

def main(initial_balance=10000, username="Guest"):
    app = ThreeCardPokerGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    final_balance = main()
    print(f"Final balance: {final_balance}")