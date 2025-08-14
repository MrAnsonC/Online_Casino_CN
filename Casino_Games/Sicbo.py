import tkinter as tk
from tkinter import ttk, messagebox
import secrets  # 使用更安全的随机数生成器
import time
from PIL import Image, ImageTk, ImageDraw
import os, json
import sys
import math
import re

# 获取当前文件所在目录并定位到A_Tools文件夹
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # 上一级目录
a_tools_dir = os.path.join(parent_dir, 'A_Tools')

# 将A_Tools目录添加到系统路径
if a_tools_dir not in sys.path:
    sys.path.append(a_tools_dir)

def get_data_file_path():
    # 用于获取保存数据的文件路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

# 保存用户数据
def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# 读取用户数据
def load_user_data():
    file_path = get_data_file_path()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()  # 先加载现有用户数据
    for user in users:
        if user['user_name'] == username:  # 查找当前用户
            user['cash'] = f"{new_balance:.2f}"  # 更新余额
            break
    save_user_data(users)  # 保存更新后的数据

class Dice:
    """自定义骰子类，确保连续两次结果不是对面数字"""
    def __init__(self, value=None):
        self.last_value = None
        self.value = value or self.roll()
    
    def roll(self):
        if self.last_value is None:
            # 第一次掷骰子，使用secrets安全随机选择
            self.value = secrets.randbelow(6) + 1
        else:
            # 获取当前值的对面值（骰子规则：1对6，2对5，3对4）
            opposite = {1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}
            opposite_value = opposite[self.last_value]
            
            # 从1-6中排除对面值和当前值，然后随机选择
            possible_values = [i for i in range(1, 7) if i != opposite_value and i != self.last_value]
            self.value = secrets.choice(possible_values)
        
        self.last_value = self.value
        return self.value

class DiceAnimationWindow:
    def __init__(self, game, callback, dice_objects):
        # 保存 SicboGame 实例
        self.game = game
        self.callback = callback
        self.dice_objects = dice_objects  # 使用传入的骰子对象

        # 窗口绑定到 SicboGame 的 root
        self.window = tk.Toplevel(game.root)
        self.window.title("骰子摇动中...")
        self.window.geometry("500x400")
        self.window.resizable(0, 0)
        self.window.configure(bg='#1e3d59')
        self.window.grab_set()

        self.window.protocol("WM_DELETE_WINDOW", self.do_nothing)

        # 窗口居中
        parent_x = game.root.winfo_x()
        parent_y = game.root.winfo_y()
        parent_width = game.root.winfo_width()
        parent_height = game.root.winfo_height()
        x = parent_x + (parent_width - 500) // 2
        y = parent_y + (parent_height - 400) // 2
        self.window.geometry(f"500x400+{x}+{y}")

        # 生成大号骰子图片
        self.dice_images = []
        for i in range(1, 7):
            img = Image.new('RGB', (120, 120), '#e8d6b3')
            self.draw_dice(img, i)
            self.dice_images.append(ImageTk.PhotoImage(img))

        self.dice_container = tk.Frame(self.window, bg='#1e3d59')
        self.dice_container.pack(pady=50)

        self.dice_labels = []
        for _ in range(3):
            lbl = tk.Label(self.dice_container, image=self.dice_images[0], bg='#1e3d59', borderwidth=0)
            lbl.pack(side=tk.LEFT, padx=20)
            self.dice_labels.append(lbl)

        self.status_label = tk.Label(self.window, text="骰子摇动中...", font=("Arial", 18), fg='white', bg='#1e3d59')
        self.status_label.pack(pady=20)

        self.progress = ttk.Progressbar(self.window, orient=tk.HORIZONTAL, length=400, mode='determinate')
        self.progress.pack(pady=10)

        self.animation_start_time = time.time()
        self.final_dice = None  # 最终结果将在动画过程中生成
        self.animate_dice()

    def do_nothing(self):
        """忽略关闭窗口的请求"""
        pass

    def draw_dice(self, img, num):
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, img.size[0]-1, img.size[1]-1], outline='#333', width=3)
        dot_color = '#ff0000' if num in [1, 4] else '#333'
        size = img.size[0]
        dot_positions = {
            1: [(size//2, size//2)],
            2: [(size//4, size//4), (3*size//4, 3*size//4)],
            3: [(size//4, size//4), (size//2, size//2), (3*size//4, 3*size//4)],
            4: [(size//4, size//4), (3*size//4, size//4), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            5: [(size//4, size//4), (3*size//4, size//4), (size//2, size//2),
                (size//4, 3*size//4), (3*size//4, 3*size//4)],
            6: [(size//4, size//4), (3*size//4, size//4),
                (size//4, size//2), (3*size//4, size//2),
                (size//4, 3*size//4), (3*size//4, 3*size//4)]
        }
        dot_size = size // 10
        for pos in dot_positions[num]:
            draw.ellipse([pos[0]-dot_size, pos[1]-dot_size, pos[0]+dot_size, pos[1]+dot_size], fill=dot_color)

    def animate_dice(self):
        elapsed = time.time() - self.animation_start_time
        if elapsed < 4:  # 骰子快速滚动阶段
            self.progress['value'] = min(100, (elapsed / 4) * 100)
            current_dice = [dice.roll() for dice in self.dice_objects]
            self.final_dice = current_dice
            for i, lbl in enumerate(self.dice_labels):
                lbl.config(image=self.dice_images[current_dice[i]-1])
            self.window.after(1, self.animate_dice)
        elif elapsed < 5:  # 停顿显示阶段
            for i, lbl in enumerate(self.dice_labels):
                lbl.config(image=self.dice_images[self.final_dice[i]-1])
            self.status_label.config(text="骰子停止中...")
            self.window.after(1, self.animate_dice)
        elif elapsed < 6:
            sorted_dice = sorted(self.final_dice)
            total = sum(sorted_dice)
            rtype = "大" if total >= 11 else "小"
            if sorted_dice[0] == sorted_dice[1] == sorted_dice[2]:
                rtype = "围"

            bg_color = "#FF1616" if rtype == "大" else "#CDB900"
            if rtype == "围":
                bg_color = "#32CD32"

            self.window.configure(bg=bg_color)
            self.dice_container.configure(bg=bg_color)
            self.status_label.configure(bg=bg_color)
            for widget in self.status_label.winfo_children():
                widget.destroy()

            result_frame = tk.Frame(self.status_label, bg=bg_color)
            result_frame.pack()
            tk.Label(result_frame, text="本局结果:", font=("Arial", 18),
                     bg=bg_color, fg="black").pack(side=tk.LEFT, padx=5)

            for i, val in enumerate(sorted_dice):
                tk.Label(result_frame, image=self.game.dice_images_small[val-1],
                         bg=bg_color).pack(side=tk.LEFT, padx=2)
                if i < 2:
                    tk.Label(result_frame, text="+", font=("Arial", 18),
                             bg=bg_color).pack(side=tk.LEFT, padx=2)

            tk.Label(result_frame, text=f"= {total}点 {rtype}",
                     font=("Arial", 18, "bold"), bg=bg_color,
                     fg="black").pack(side=tk.LEFT, padx=5)

            # 显示2秒后自动结算
            self.window.after(2000, self.finish)

    def finish(self):
        """关闭动画窗口并进入结算阶段"""
        try:
            self.window.destroy()
        except:
            pass
        if callable(self.callback):
            self.callback(self.final_dice)

# 颜色常量
COLOR_SMALL = "#FFD700"   # 小（金）
COLOR_TIE = "#32CD32"     # 围（绿）
COLOR_BIG = "#FF4500"     # 大（橙红）
BG_FRAME = "#D0E7FF"

MAX_RECORDS = 100

class SicboGame:
    def __init__(self, root, username=None, initial_balance=10000):
        self.root = root
        self.username = username
        self.accept_bets = True
        # 配置 Notebook 样式，使标签字体加大
        style = ttk.Style()
        style.configure('TNotebook.Tab', font=('Arial', 12, 'bold'))

        self.root.title("Sicbo 骰寶遊戲")
        self.root.geometry("1387x730+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg='#0a5f38')
        self.enter_binding = None

        # 使用传入的初始余额
        self.balance = initial_balance
        self.final_balance = initial_balance  # 添加最终余额属性
        self.current_bet = 0
        self.bet_amount = 100
        self.last_win = 0
        self.last_dice = []  # 存储上局骰子结果
        self.last_triple = [0, 0]  # [点数, 局数前]
        self.bets = {
            "small": 0,
            "all_triples": 0,
            "big": 0,
            "odd": 0,
            "even": 0,
            "double": {i: 0 for i in range(1, 7)},
            "total_points": {i: 0 for i in range(4, 18)},
            "pairs": {f"{i}&{j}": 0 for i in range(1, 7) for j in range(i+1, 7)},
            "triple": {i: 0 for i in range(1, 7)},
            "guess_num": {i: 0 for i in range(1, 7)},
            "number_group": {group: 0 for group in ["1234", "2345", "2356", "3456"]}
        }

        # 创建不同尺寸的骰子图片
        self.dice_images_large = []  # 大尺寸 (70x70)
        self.dice_images_small = []  # 小尺寸 (30x30)
        for i in range(1, 7):
            # 大尺寸骰子
            img_large = Image.new('RGB', (70, 70), '#e8d6b3')
            self.draw_dice(img_large, i)
            self.dice_images_large.append(ImageTk.PhotoImage(img_large))

            # 小尺寸骰子
            img_small = Image.new('RGB', (30, 30), '#e8d6b3')
            self.draw_dice(img_small, i)
            self.dice_images_small.append(ImageTk.PhotoImage(img_small))

        # 筹码值与颜色
        self.chip_values = [
            ('25',   '#00ff00'),
            ('100',  '#000000'),
            ('200',  '#0000ff'),
            ('500',  '#FF7DDA'),
            ('1K',   '#ffffff'),
            ('2K',   '#0000ff'),
            ('5K',   '#ff0000'),
            ('10K',  '#800080'),
            ('20K',  '#ffa500'),
            ('50K',  '#006400')
        ]
        self.chips = [25, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]
        self.history = []
        self.chip_widgets = []  # 存储 (canvas, oval_id, value)
        
        # 初始化骰子对象（使用上一局的结果作为初始值）
        self.dice_objects = [Dice(), Dice(), Dice()]

        # 定位历史记录文件
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logs_dir = os.path.join(parent_dir, 'A_Logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        self.history_file = os.path.join(logs_dir, 'Sicbo.json')
        self.history_data = self.load_history_data()
        
        self.create_widgets()
        self.root.bind('<Return>', lambda event: self.roll_dice())
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
    
    def format_amount(self, amount):
        if amount >= 1000:
            if amount >= 10000:
                return f"{amount / 1000:.1f}K"
            else:
                return str(amount)
        return f"{amount}"

    def ensure_100_Record_structure(self, block):
        """确保 block 包含 01_Data..50_Data 的键，若已有则保留其值（try to map numeric keys）"""
        new_block = {f"{i:02d}_Data": [] for i in range(1, MAX_RECORDS+1)}
        if not block:
            return new_block
        # Try to map existing keys: extract number from key (like '01_Data' or '1_Data' or '1')
        for k, v in block.items():
            m = re.search(r'(\d+)', k)
            if m:
                idx = int(m.group(1))
                if 1 <= idx <= MAX_RECORDS:
                    new_block[f"{idx:02d}_Data"] = v
        # If the block had no numeric keys but was a list-like, try to assign from list values
        # (some legacy formats may store a list)
        if all(not re.search(r'(\d+)', k) for k in block.keys()):
            # if block.values() are lists, try fill from newest->oldest into keys starting at 01
            vals = list(block.values())
            for i, val in enumerate(vals[:MAX_RECORDS]):
                new_block[f"{i+1:02d}_Data"] = val
        return new_block

    def load_history_data(self):
        # 创建默认数据结构，包含所有需要的字段
        default_data = {
            "100_Record": {f"{i:02d}_Data": [] for i in range(1, MAX_RECORDS+1)},
            "Last_Triple": [0, 0],  # [点数, 局数前]
            "H_Small": 0,
            "H_Triple": 0,
            "H_Big": 0,
            # 点数历史
            "H_4": 0, "H_5": 0, "H_6": 0, "H_7": 0, "H_8": 0, "H_9": 0, 
            "H_10": 0, "H_11": 0, "H_12": 0, "H_13": 0, "H_14": 0, "H_15": 0, 
            "H_16": 0, "H_17": 0,
            # 围骰历史
            "H_T1": 0, "H_T2": 0, "H_T3": 0, "H_T4": 0, "H_T5": 0, "H_T6": 0
        }
        
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 确保所有字段都存在，如果不存在则使用默认值
                    for key, default_value in default_data.items():
                        if key not in data:
                            data[key] = default_value
                    
                    # 确保100_Record存在并具有正确的结构
                    old_block = data.get("100_Record", {})
                    data["100_Record"] = self.ensure_100_Record_structure(old_block)
                    
                    # 确保Last_Triple存在
                    if "Last_Triple" not in data:
                        data["Last_Triple"] = [0, 0]
                    
                    return data
            # 文件不存在时返回默认数据
            return default_data
        except Exception as e:
            print(f"加载历史记录失败: {e}")
            return default_data

    def save_history_data(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存历史记录失败: {e}")

    def shift_and_insert_record(self, sorted_dice):
        """
        将 01->02, 02->03, ..., 49->50，然后把 sorted_dice 写入 01_Data
        """
        block = self.history_data.setdefault("100_Record", {f"{i:02d}_Data": [] for i in range(1, MAX_RECORDS+1)})
        # shift
        for i in range(MAX_RECORDS, 1, -1):
            dst = f"{i:02d}_Data"
            src = f"{i-1:02d}_Data"
            block[dst] = list(block.get(src, []))
        # insert new at 01
        block["01_Data"] = list(sorted_dice)
        self.save_history_data()

    def update_history(self, dice):
        sorted_dice = sorted(dice)
        self.shift_and_insert_record(sorted_dice)

        # 这里加上
        self.update_global_stats(sorted_dice)

        self.update_history_display()
        self.update_last_game_display()
        self.update_win_distribution()

        # 新增：每次历史更新后也刷新点数统计（确保"过去100局中出现的点数数量"即时更新）
        try:
            self.update_points_stats()
        except Exception:
            # 保护性容错：若有异常，不阻止主流程
            pass

    def update_global_stats(self, sorted_dice):
        """更新全局历史统计数据"""
        total = sum(sorted_dice)
        is_triple = (sorted_dice[0] == sorted_dice[1] == sorted_dice[2])
        
        # 更新小/围/大历史
        if is_triple:
            self.history_data["H_Triple"] += 1
        else:
            if total <= 10:
                self.history_data["H_Small"] += 1
            else:
                self.history_data["H_Big"] += 1
        
        # 更新点数历史
        if 4 <= total <= 17:
            key = f"H_{total}"
            self.history_data[key] = self.history_data.get(key, 0) + 1
        
        # 更新围骰点数历史
        if is_triple and 1 <= sorted_dice[0] <= 6:
            key = f"H_T{sorted_dice[0]}"
            self.history_data[key] = self.history_data.get(key, 0) + 1
        
        # 保存更新后的数据
        self.save_history_data()

    def update_history_display(self):
        """更新历史记录标签页的显示（读取 self.history_data['100_Record'] 并按 01..50 展示非空）"""
        # 清空当前记录区域（只清除滚动内容）
        for widget in self.history_inner.winfo_children():
            widget.destroy()
        
        records = self.history_data.get("100_Record", {})
        # iterate from 01_Data .. 50_Data (01 newest)
        row = 0
        for i in range(1, MAX_RECORDS+1):
            k = f"{i:02d}_Data"
            dice = records.get(k, [])
            if not dice or len(dice) < 3:
                continue
            total = sum(dice)
            is_triple = (dice[0] == dice[1] == dice[2])
            # determine result type (note dice stored sorted)
            if is_triple:
                rtype = "围"
                bg = COLOR_TIE
            else:
                rtype = "小" if total <= 10 else "大"
                bg = COLOR_SMALL if rtype == "小" else COLOR_BIG

            # 创建记录框架，背景按类型着色
            frame = tk.Frame(self.history_inner, bg=bg, padx=5, pady=5, relief=tk.RIDGE, borderwidth=1)
            frame.pack(fill=tk.X, padx=2, pady=2)

            # 骰子显示（使用小图）, 背景同类型颜色
            dice_frame = tk.Frame(frame, bg=bg)
            dice_frame.pack(side=tk.LEFT, padx=10)
            for d in dice:
                lbl = tk.Label(dice_frame, image=self.dice_images_small[d-1], bg=bg)
                lbl.pack(side=tk.LEFT, padx=1)
            
            # 总点数
            tk.Label(frame, text=f"{total}", font=("Arial", 12), bg=bg, width=13).pack(side=tk.LEFT, padx=10)
            
            # 类型
            tk.Label(frame, text=f"{rtype}", font=("Arial", 12), bg=bg, width=7).pack(side=tk.LEFT, padx=5)

        # 更新 last triple display
        self.update_last_triple_display()
        # 更新获胜分布
        self.update_win_distribution()

    def on_window_close(self):
        """窗口关闭时更新余额到JSON"""
        self.final_balance = self.balance
        if self.username:
            update_balance_in_json(self.username, self.balance)
        self.root.destroy()

    def draw_dice(self, img, num):
        draw = ImageDraw.Draw(img)
        size = img.size[0]
        dot_size = size // 10
        draw.rectangle([0, 0, size-1, size-1], outline='#333', width=2)
        
        # 1和4的点为红色，其他为黑色
        dot_color = "#bf0101" if num in [1, 4] else '#333'
        
        dot_positions = {
            1: [(size//2, size//2)],
            2: [(size//4, size//4), (3*size//4, 3*size//4)],
            3: [(size//4, size//4), (size//2, size//2), (3*size//4, 3*size//4)],
            4: [(size//4, size//4), (3*size//4, size//4), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            5: [(size//4, size//4), (3*size//4, size//4), (size//2, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)],
            6: [(size//4, size//4), (3*size//4, size//4), (size//4, size//2), (3*size//4, size//2), (size//4, 3*size//4), (3*size//4, 3*size//4)]
        }
        for pos in dot_positions[num]:
            draw.ellipse([pos[0]-dot_size, pos[1]-dot_size, pos[0]+dot_size, pos[1]+dot_size], fill=dot_color)

    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg='#0a5f38')
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = tk.Frame(main_frame, bg='#0a5f38')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 右侧面板使用固定宽度的容器（375px）
        right_container = tk.Frame(main_frame, width=375, bg='#F0F0F0', relief=tk.GROOVE, bd=1)
        right_container.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        right_container.pack_propagate(False)  # 锁定宽度 375px

        # Notebook 放入右侧容器
        self.right_notebook = ttk.Notebook(right_container)
        self.right_notebook.pack(fill=tk.BOTH, expand=True)

        # 控制标签页
        control_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(control_tab, text='控制面板')

        # 历史记录标签页
        history_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(history_tab, text='历史记录')
        self.create_history_tab(history_tab)

        # 控制面板内容 背景颜色修改
        control_frame = tk.Frame(control_tab, bg='#D0E7FF')
        control_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 余额和投注信息
        info_frame = tk.Frame(control_frame, bg='#D0E7FF')
        info_frame.pack(fill=tk.X, pady=10)

        self.balance_label = tk.Label(info_frame, text=f"余额: ${self.balance}",
                                    font=("Arial", 14, "bold"), fg='black', bg='#D0E7FF')
        self.balance_label.pack(side=tk.LEFT, padx=10)

        # 筹码区 - 修改筹码大小为60x60，间距调整为5px
        chip_frame = tk.Frame(control_frame, bg='#D0E7FF')
        chip_frame.pack(fill=tk.X, pady=(10, 5))

        tk.Label(chip_frame, text="筹码选择", font=("Arial", 14, "bold"),
                fg='black', bg='#D0E7FF').pack(anchor=tk.W, pady=5)

        row1 = tk.Frame(chip_frame, bg='#D0E7FF')
        row1.pack(fill=tk.X, pady=5)
        for idx, (label, color) in enumerate(self.chip_values[:5]):
            value = self.chips[idx]
            canvas = tk.Canvas(row1, width=60, height=60, bg='#D0E7FF', highlightthickness=0, cursor="hand2")
            canvas.pack(side=tk.LEFT, padx=5)  # 间距调整为5px
            oval_id = canvas.create_oval(5, 5, 55, 55, fill=color, outline='#333', width=2)
            
            # 设置特定筹码的文字颜色为白色
            text_color = 'white' if label in ['100', '200', '2K', '5K', '10K', '50K'] else 'black'
            # 字体大小调整为16
            canvas.create_text(30, 30, text=label, font=("Arial", 16, "bold"), fill=text_color)
            
            canvas.bind("<Button-1>", lambda e, c=value: self.set_bet_amount(c))
            self.chip_widgets.append((canvas, oval_id, value))

        row2 = tk.Frame(chip_frame, bg='#D0E7FF')
        row2.pack(fill=tk.X, pady=5)
        for idx, (label, color) in enumerate(self.chip_values[5:]):
            value = self.chips[idx+5]
            canvas = tk.Canvas(row2, width=60, height=60, bg='#D0E7FF', highlightthickness=0, cursor="hand2")
            canvas.pack(side=tk.LEFT, padx=5)  # 间距调整为5px
            oval_id = canvas.create_oval(5, 5, 55, 55, fill=color, outline='#333', width=2)
            
            text_color = 'white' if label in ['100', '200', '2K', '5K', '10K', '50K'] else 'black'
            # 字体大小调整为16
            canvas.create_text(30, 30, text=label, font=("Arial", 16, "bold"), fill=text_color)
            
            canvas.bind("<Button-1>", lambda e, c=value: self.set_bet_amount(c))
            self.chip_widgets.append((canvas, oval_id, value))

        # 豪华提示栏 - 每注最低/最高
        minmax_frame = tk.Frame(control_frame, bg='#D0E7FF', pady=5)
        minmax_frame.pack(fill=tk.X, pady=(5, 5))

        table_border_color = "#d70000"
        table_bg = '#f9f9f9'

        # 外框
        outer_frame = tk.Frame(minmax_frame, bg=table_border_color, bd=2, relief=tk.SOLID)
        outer_frame.pack(padx=5, pady=5, fill=tk.X)

        # 表头
        header_frame = tk.Frame(outer_frame, bg=table_border_color)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="每注最低", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="每注最高", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="每局最高", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 内容行
        content_frame = tk.Frame(outer_frame, bg=table_bg)
        content_frame.pack(fill=tk.X)
        tk.Label(content_frame, text="25", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="50,000", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="500,000", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)


        # 上局信息 - 创建表格框架
        last_games_container = tk.Frame(control_frame, bg='#D0E7FF')
        last_games_container.pack(fill=tk.X, pady=10)

        # 表格框架（使用 grid）
        table_frame = tk.Frame(last_games_container, bg='#D0E7FF')
        table_frame.pack(fill=tk.X)

        # 设定四列最小宽度，保证标题与内容对齐
        table_frame.columnconfigure(0, minsize=90)   # 类型列
        table_frame.columnconfigure(1, minsize=120)  # 骰子列（放三个小图）
        table_frame.columnconfigure(2, minsize=60)   # 点数列
        table_frame.columnconfigure(3, minsize=80)   # 结果列

        # 标题行（背景色与字体）
        header_bg = '#1e3d59'
        tk.Label(table_frame, text="类型", font=("Arial", 12, "bold"),
                fg='white', bg=header_bg).grid(row=0, column=0, sticky='nsew', pady=4)
        tk.Label(table_frame, text="骰子", font=("Arial", 12, "bold"),
                fg='white', bg=header_bg).grid(row=0, column=1, sticky='nsew', pady=4)
        tk.Label(table_frame, text="点数", font=("Arial", 12, "bold"),
                fg='white', bg=header_bg).grid(row=0, column=2, sticky='nsew', pady=4)
        tk.Label(table_frame, text="结果", font=("Arial", 12, "bold"),
                fg='white', bg=header_bg).grid(row=0, column=3, sticky='nsew', pady=4)

        # -------- 上局点数（第一行） --------
        tk.Label(table_frame, text="上局点数:", font=("Arial", 12),
                bg='#D0E7FF').grid(row=1, column=0, sticky='w', padx=(6,2), pady=4)

        # 骰子放在一个内部 frame 里，用来放三个 image label
        self.last_dice_frame = tk.Frame(table_frame, bg='#D0E7FF')
        self.last_dice_frame.grid(row=1, column=1, sticky='w', padx=2, pady=4)

        self.last_dice_labels = []
        for i in range(3):
            lbl = tk.Label(self.last_dice_frame, bg='#D0E7FF', bd=1, relief=tk.FLAT)
            lbl.pack(side=tk.LEFT, padx=4, pady=2)
            self.last_dice_labels.append(lbl)

        self.last_points_label = tk.Label(table_frame, text="--点", font=("Arial", 12),
                                        bg='#D0E7FF')
        self.last_points_label.grid(row=1, column=2, sticky='n', padx=2, pady=8)

        self.last_result_label = tk.Label(table_frame, text="--", font=("Arial", 12),
                                        bg='#D0E7FF')
        self.last_result_label.grid(row=1, column=3, sticky='n', padx=2, pady=8)

        # 分割线（横跨四列）
        divider = tk.Frame(table_frame, bg='#1e3d59', height=2)
        divider.grid(row=2, column=0, columnspan=4, sticky='ew', padx=2, pady=(4,6))

        # -------- 上次围骰（第二行） --------
        tk.Label(table_frame, text="上次围骰:", font=("Arial", 12),
                bg='#D0E7FF').grid(row=3, column=0, sticky='w', padx=(6,2), pady=4)

        self.last_triple_frame = tk.Frame(table_frame, bg='#D0E7FF')
        self.last_triple_frame.grid(row=3, column=1, sticky='w', padx=2, pady=4)

        self.last_triple_dice_labels = []
        for i in range(3):
            lbl = tk.Label(self.last_triple_frame, bg='#D0E7FF', bd=1, relief=tk.FLAT)
            lbl.pack(side=tk.LEFT, padx=4, pady=2)
            self.last_triple_dice_labels.append(lbl)

        self.last_triple_points_label = tk.Label(table_frame, text="--",
                                                font=("Arial", 12), bg='#D0E7FF')
        self.last_triple_points_label.grid(row=3, column=2, sticky='n', padx=2, pady=8)

        self.last_triple_info_label = tk.Label(table_frame, text="无记录",
                                            font=("Arial", 12), bg='#D0E7FF')
        self.last_triple_info_label.grid(row=3, column=3, sticky='n', padx=2, pady=8)

        # 分割线（横跨四列）
        divider = tk.Frame(table_frame, bg='#1e3d59', height=2)
        divider.grid(row=4, column=0, columnspan=4, sticky='ew', padx=2, pady=(4,6))

        # 当前下注信息
        bet_info_frame = tk.Frame(control_frame, bg='#D0E7FF')
        bet_info_frame.pack(fill=tk.X, pady=10)

        # 统一标题样式
        label_style = {"font": ("Arial", 14, "bold"), "fg": "#333", "bg": "#D0E7FF"}
        value_style = {"font": ("Arial", 14), "fg": "black", "bg": "#D0E7FF"}

        # 本局下注
        lbl_bet_title = tk.Label(bet_info_frame, text="本局下注:", **label_style, anchor="e", width=8)
        lbl_bet_title.grid(row=0, column=0, sticky="e", padx=(10, 5), pady=3)

        self.current_bet_display = tk.Label(bet_info_frame, text="$0", **value_style, anchor="w")
        self.current_bet_display.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=3)

        # 上局获胜
        lbl_win_title = tk.Label(bet_info_frame, text="上局获胜:", **label_style, anchor="e", width=8)
        lbl_win_title.grid(row=1, column=0, sticky="e", padx=(10, 5), pady=3)

        self.last_win_display = tk.Label(bet_info_frame, text="$0", **value_style, anchor="w")
        self.last_win_display.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=3)

        # 列宽自动调整
        bet_info_frame.columnconfigure(0, weight=0)  # 标题列固定
        bet_info_frame.columnconfigure(1, weight=1)  # 金额列自适应

        # 控制按钮
        btn_frame = tk.Frame(control_frame, bg='#D0E7FF')
        btn_frame.pack(fill=tk.X, pady=10)

        # 修改清除按钮样式
        clear_btn = tk.Button(btn_frame, text="清除投注", font=("Arial", 14, "bold"),
                            bg='#ff4444', fg='white', width=10, command=self.clear_bets, cursor="hand2")
        clear_btn.pack(side=tk.LEFT, padx=10, expand=True)

        # 修改掷骰子按钮样式
        roll_btn = tk.Button(btn_frame, text="擲骰子 (Enter)", font=("Arial", 14, "bold"),
                        bg=COLOR_SMALL, fg='black', width=15, command=self.roll_dice, cursor="hand2")
        roll_btn.pack(side=tk.LEFT, padx=10, expand=True)

        def bind_click_widgets(container, handler):
            """把 handler 绑定到 container 和其所有子 widget（递归）。"""
            try:
                container.bind("<Button-1>", handler)
            except Exception:
                pass
            # 遍历已存在的子 widget 并绑定
            for child in container.winfo_children():
                try:
                    child.bind("<Button-1>", handler)
                except Exception:
                    pass
                # 递归绑定子容器里的子项
                if isinstance(child, (tk.Frame, tk.Label, tk.Canvas)):
                    bind_click_widgets(child, handler)

        # 左侧顶部布局
        top_frame = tk.Frame(left_frame, bg='#0a5f38')
        top_frame.pack(fill=tk.X, pady=(10, 10), padx=10)

        # 左边列（小、围骰通杀、单）
        left_col = tk.Frame(top_frame, bg='#0a5f38')
        left_col.grid(row=0, column=0, sticky="n")

        # 小
        self.small_frame = tk.Frame(left_col, bg='#FFD700', padx=20, pady=10, cursor="hand2", height=100, width=300)
        self.small_frame.pack(padx=5, pady=(0, 0))
        self.small_frame.pack_propagate(False)
        small_click = lambda e, bt="small", od=1: self.place_bet(bt, od)
        tk.Label(self.small_frame, text="小（4-10）", font=("Arial", 20, "bold"),
                bg='#FFD700', cursor="hand2").pack(pady=5)
        self.small_bet_label = tk.Label(self.small_frame, text="$0", font=("Arial", 16, "bold"),
                                        bg='#FFD700', cursor="hand2")
        self.small_bet_label.pack()
        bind_click_widgets(self.small_frame, small_click)

        # 围骰通杀（左）
        small_triple_bar = tk.Frame(left_col, bg="#CFA3FF", relief=tk.SUNKEN, bd=1, height=30, width=300)
        small_triple_bar.pack(padx=5, pady=0)
        small_triple_bar.pack_propagate(False)
        tk.Label(small_triple_bar, text="↑↓↑↓ 赔率1:1  围骰通杀 ↑↓↑↓", font=("Arial", 14, "bold"),
                bg="#CFA3FF").pack(fill=tk.BOTH, expand=True)

        # 单
        self.odd_frame = tk.Frame(left_col, bg='#87CEEB', padx=20, pady=10, cursor="hand2", height=100, width=300)
        self.odd_frame.pack(padx=5, pady=0)
        self.odd_frame.pack_propagate(False)
        odd_click = lambda e, bt="odd", od=1: self.place_bet(bt, od)
        tk.Label(self.odd_frame, text="单（奇数）", font=("Arial", 20, "bold"),
                bg='#87CEEB', cursor="hand2").pack(pady=5)
        self.odd_bet_label = tk.Label(self.odd_frame, text="$0", font=("Arial", 16, "bold"),
                                    bg='#87CEEB', cursor="hand2")
        self.odd_bet_label.pack()
        bind_click_widgets(self.odd_frame, odd_click)

        # 中间列（任何围骰 + 基本/组合按钮）
        center_col = tk.Frame(top_frame, bg='#0a5f38')
        center_col.grid(row=0, column=1, padx=5, sticky="ns")  # sticky ns 让列占满上下空间

        # 任何围骰
        self.all_triples_frame = tk.Frame(center_col, bg='#32CD32', cursor="hand2", height=180, width=340)
        self.all_triples_frame.pack(pady=(0, 0), anchor="n")  # 顶部贴合
        self.all_triples_frame.pack_propagate(False)
        triple_click = lambda e, bt="all_triples", od=31: self.place_bet(bt, od)
        tk.Label(self.all_triples_frame, text="~ 任何围骰 赔率1:31 ~", font=("Arial", 16, "bold"),
                bg='#32CD32', cursor="hand2").pack(pady=2)

        dice_container = tk.Frame(self.all_triples_frame, bg='#32CD32', cursor="hand2")
        dice_container.pack(expand=True)
        for pair in [(0, 3), (1, 4), (2, 5)]:
            row_frame = tk.Frame(dice_container, bg='#32CD32')
            row_frame.pack()
            for _ in range(3):
                tk.Label(row_frame, image=self.dice_images_small[pair[0]],
                        bg='#32CD32', cursor="hand2").pack(side=tk.LEFT, padx=1)
            tk.Label(row_frame, text=" ", bg='#32CD32', width=1).pack(side=tk.LEFT)
            for _ in range(3):
                tk.Label(row_frame, image=self.dice_images_small[pair[1]],
                        bg='#32CD32', cursor="hand2").pack(side=tk.LEFT, padx=1)

        self.all_triples_bet_label = tk.Label(self.all_triples_frame, text="$0",
                                            font=("Arial", 16, "bold"), bg='#32CD32', cursor="hand2")
        self.all_triples_bet_label.pack(pady=2)
        bind_click_widgets(self.all_triples_frame, triple_click)

        # 基本 / 组合 按钮（靠下对齐）
        tab_button_frame = tk.Frame(center_col, bg='#0a5f38')
        tab_button_frame.pack(side=tk.BOTTOM, pady=(5, 0))  # 靠下

        # 基本下注按钮
        self.basic_tab_btn = tk.Button(tab_button_frame, text="基本下注", font=("Arial", 16, "bold"),
            bg='#FFA500', fg='black', cursor="hand2", relief=tk.SUNKEN,
            width=10, height=0,
            command=lambda: self.switch_tab_mode("basic"))
        self.basic_tab_btn.grid(row=0, column=0, padx=5)

        # 组合下注按钮
        self.combo_tab_btn = tk.Button(tab_button_frame, text="组合下注", font=("Arial", 16, "bold"),
            bg='#2196F3', fg='black', cursor="hand2", relief=tk.RAISED,
            width=10, height=0,
            command=lambda: self.switch_tab_mode("combo"))
        self.combo_tab_btn.grid(row=0, column=1, padx=5)

        # 右边列（大、围骰通杀、双）
        right_col = tk.Frame(top_frame, bg='#0a5f38')
        right_col.grid(row=0, column=2, sticky="n")

        # 大
        self.big_frame = tk.Frame(right_col, bg='#FF4500', padx=20, pady=10, cursor="hand2", height=100, width=300)
        self.big_frame.pack(padx=5, pady=0)
        self.big_frame.pack_propagate(False)
        big_click = lambda e, bt="big", od=1: self.place_bet(bt, od)
        tk.Label(self.big_frame, text="大（11-17）", font=("Arial", 20, "bold"),
                bg='#FF4500', cursor="hand2").pack(pady=5)
        self.big_bet_label = tk.Label(self.big_frame, text="$0", font=("Arial", 16, "bold"),
                                    bg='#FF4500', cursor="hand2")
        self.big_bet_label.pack()
        bind_click_widgets(self.big_frame, big_click)

        # 围骰通杀（右）
        big_triple_bar = tk.Frame(right_col, bg="#FF7B00", relief=tk.SUNKEN, bd=1, height=30, width=300)
        big_triple_bar.pack(padx=5, pady=0)
        big_triple_bar.pack_propagate(False)
        tk.Label(big_triple_bar, text="↑↓↑↓ 赔率1:1  围骰通杀 ↑↓↑↓", font=("Arial", 14, "bold"),
                bg='#FF7B00').pack(fill=tk.BOTH, expand=True)

        # 双
        self.even_frame = tk.Frame(right_col, bg="#FF6B93", padx=20, pady=10, cursor="hand2", height=100, width=300)
        self.even_frame.pack(padx=5, pady=0)
        self.even_frame.pack_propagate(False)
        even_click = lambda e, bt="even", od=1: self.place_bet(bt, od)
        tk.Label(self.even_frame, text="双（偶数）", font=("Arial", 20, "bold"),
                bg='#FF6B93', cursor="hand2").pack(pady=5)
        self.even_bet_label = tk.Label(self.even_frame, text="$0", font=("Arial", 16, "bold"),
                                    bg='#FF6B93', cursor="hand2")
        self.even_bet_label.pack()
        bind_click_widgets(self.even_frame, even_click)

        # 三列的 grid 配置
        top_frame.grid_columnconfigure(0, weight=0)
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_columnconfigure(2, weight=0)

        # 标签页容器（用普通 Frame 叠放两个面板，视觉上保留白色/浅灰背景）
        # 这里把容器背景设为浅灰（近白），并用 relief/ bd 模拟 Notebook 面板边框
        PANEL_BG = '#F0F0F0'   # -> 如果想要纯白可改为 '#FFFFFF'；或改为 '#D0E7FF'（浅蓝）
        self.tab_container = tk.Frame(left_frame, bg=PANEL_BG, relief=tk.GROOVE, bd=2)
        self.tab_container.pack(expand=1, fill="both", pady=(0, 10), padx=10)
        self.tab_container.grid_rowconfigure(0, weight=1)
        self.tab_container.grid_columnconfigure(0, weight=1)

        # 创建两个下注面板（作为普通 Frame），默认背景也设为 PANEL_BG，
        # 这样外框是浅灰，内部原本自己设置背景的子区块（如 '#0a5f38' 的绿块）仍然显示其颜色
        tab1 = tk.Frame(self.tab_container, bg=PANEL_BG)
        tab2 = tk.Frame(self.tab_container, bg=PANEL_BG)

        # 将两个面板放在同一位置，后续使用 tkraise() 切换
        tab1.grid(row=0, column=0, sticky="nsew")
        tab2.grid(row=0, column=0, sticky="nsew")

        # 保存引用以便 switch_tab_mode 使用（兼容你已有逻辑）
        self.tab1_frame = tab1
        self.tab2_frame = tab2

        # 默认显示基本面板（将其抬到上层）
        try:
            self.tab1_frame.tkraise()
        except Exception:
            pass

        self.tab_container.grid_rowconfigure(0, weight=1)
        self.tab_container.grid_columnconfigure(0, weight=1)

        # 默认显示第一个面板
        tab1.tkraise()
        # 保存引用以便 switch_tab_mode 使用
        self.tab_frames = (tab1, tab2)

        # 创建两个面板的内容（不变）
        self.create_tab1(tab1)
        self.create_tab2(tab2)
                
        # 设置100筹码为默认选中
        self.set_bet_amount(100)
        
        # 初始化历史记录显示
        self.update_history_display()
        # 初始化上局点数显示
        self.update_last_game_display()
        # 初始化上次围骰显示
        self.update_last_triple_display()
        # 初始化获胜分布
        self.update_win_distribution()

    def switch_tab_mode(self, mode):
        # 优先使用自定义的 tab_frames（tk.Frame + tkraise）
        if hasattr(self, 'tab_frames'):
            tab1, tab2 = self.tab_frames
            if mode == "basic":
                tab1.tkraise()
                try:
                    self.basic_tab_btn.config(relief=tk.SUNKEN)
                    self.combo_tab_btn.config(relief=tk.RAISED)
                except Exception:
                    pass
            else:
                tab2.tkraise()
                try:
                    self.basic_tab_btn.config(relief=tk.RAISED)
                    self.combo_tab_btn.config(relief=tk.SUNKEN)
                except Exception:
                    pass
            return

        # 回退到可能存在的旧 notebook（防护：如果 notebook 不存在，忽略异常）
        try:
            if mode == "basic":
                self.tab_control.select(0)
                self.basic_tab_btn.config(relief=tk.SUNKEN)
                self.combo_tab_btn.config(relief=tk.RAISED)
            else:
                self.tab_control.select(1)
                self.basic_tab_btn.config(relief=tk.RAISED)
                self.combo_tab_btn.config(relief=tk.SUNKEN)
        except Exception:
            # 如果两者都不存在或 select 出错，不要抛异常中断程序
            pass

    def create_history_tab(self, parent):
        """创建历史记录标签页（最近50局）"""
        record_frame = tk.Frame(parent, bg='#D0E7FF')
        record_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(record_frame, text="过去100局记录", font=("Arial", 16, "bold"), 
                bg='#D0E7FF').pack(anchor=tk.W, pady=5)
        
        # 标题行（固定，不随滚动）
        self.records_title_frame = tk.Frame(record_frame, bg='#1e3d59', padx=5, pady=3, relief=tk.RAISED, borderwidth=1)
        self.records_title_frame.pack(fill=tk.X, padx=2, pady=(0, 5))
        
        # 使用网格布局确保对齐
        tk.Label(self.records_title_frame, text="骰子", font=("Arial", 12, "bold"), 
                fg='white', bg='#1e3d59', width=12).grid(row=0, column=0, sticky="w")
        tk.Label(self.records_title_frame, text="点数", font=("Arial", 12, "bold"), 
                fg='white', bg='#1e3d59', width=14).grid(row=0, column=1, sticky="w")
        tk.Label(self.records_title_frame, text="结果", font=("Arial", 12, "bold"), 
                fg='white', bg='#1e3d59', width=4).grid(row=0, column=2, sticky="w")

        # 创建滚动容器（记录列表区域）
        container = tk.Frame(record_frame, bg='#D0E7FF')
        container.pack(fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建Canvas用于滚动（减少高度为150）
        self.history_canvas = tk.Canvas(container, bg='#D0E7FF', yscrollcommand=scrollbar.set, height=150)
        self.history_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.history_canvas.yview)
        
        # 创建内部框架用于放置可滚动内容
        self.history_inner = tk.Frame(self.history_canvas, bg='#D0E7FF')
        self.history_window = self.history_canvas.create_window((0, 0), window=self.history_inner, anchor=tk.NW)
        
        # 配置Canvas滚动
        self.history_inner.bind("<Configure>", lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all")))
        self.history_canvas.bind("<Configure>", lambda e: self.history_canvas.itemconfig(self.history_window, width=e.width))
        
        # 获胜分布部分（过去50局）
        distribution_frame = tk.Frame(parent, bg='#D0E7FF', padx=10, pady=10)
        distribution_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(distribution_frame, text="过去100局的获胜分布", font=("Arial", 12, "bold"), 
                bg='#D0E7FF').pack(anchor=tk.W, pady=5)
        
        # 创建进度条容器（宽度限制在375px内）
        progress_container = tk.Frame(distribution_frame, bg='#D0E7FF', width=355, height=30)
        progress_container.pack(fill=tk.X, pady=5)
        
        self.small_progress = tk.Label(progress_container, text="小", bg=COLOR_SMALL,
                                    fg='black', anchor='center', font=("Arial", 10, "bold"))
        self.triple_progress = tk.Label(progress_container, text="围", bg=COLOR_TIE,
                                        fg='black', anchor='center', font=("Arial", 10, "bold"))
        self.big_progress = tk.Label(progress_container, text="大", bg=COLOR_BIG,
                                    fg='black', anchor='center', font=("Arial", 10, "bold"))

        counts_container = tk.Frame(distribution_frame, bg='#D0E7FF', pady=4, width=355)
        counts_container.pack(fill=tk.X, padx=10)

        self.small_count_label = tk.Label(counts_container, text="小: 0", font=("Arial", 10, "bold"),
                                        bg='#D0E7FF', fg='black', anchor='center', width=10)
        self.small_count_label.pack(side=tk.LEFT, expand=True)

        self.triple_count_label = tk.Label(counts_container, text="围: 0", font=("Arial", 10, "bold"),
                                        bg='#D0E7FF', fg='black', anchor='center', width=10)
        self.triple_count_label.pack(side=tk.LEFT, expand=True)

        self.big_count_label = tk.Label(counts_container, text="大: 0", font=("Arial", 10, "bold"),
                                        bg='#D0E7FF', fg='black', anchor='center', width=10)
        self.big_count_label.pack(side=tk.LEFT, expand=True)
        
        # 点数统计部分（使用骰子图标）
        points_frame = tk.Frame(parent, bg='#D0E7FF', padx=10, pady=10)
        points_frame.pack(fill=tk.X, pady=5)

        tk.Label(points_frame, text="过去100局中出现的点数数量：", font=("Arial", 12, "bold"), 
                bg='#D0E7FF').pack(anchor=tk.W, pady=5)

        # 使用网格布局确保对齐
        points_container = tk.Frame(points_frame, bg='#D0E7FF')
        points_container.pack(fill=tk.X, pady=5)

        # 使用网格布局容器
        grid_container = tk.Frame(points_container, bg='#D0E7FF')
        grid_container.pack()

        # 创建骰子图标标签和计数标签
        self.dice_icon_labels = []
        self.point_count_labels = []

        for col, point in enumerate(range(1, 7)):
            # 创建列容器
            col_frame = tk.Frame(grid_container, bg='#D0E7FF')
            col_frame.grid(row=0, column=col, padx=10, pady=5)
            
            # 骰子图标
            icon_frame = tk.Frame(col_frame, bg='#D0E7FF')
            icon_frame.pack()
            lbl_icon = tk.Label(icon_frame, image=self.dice_images_small[point-1], bg='#D0E7FF')
            lbl_icon.pack()
            self.dice_icon_labels.append(lbl_icon)
            
            # 数字计数
            count_frame = tk.Frame(col_frame, bg='#D0E7FF')
            count_frame.pack()
            lbl_count = tk.Label(count_frame, text="0", font=("Arial", 10, "bold"), bg='#D0E7FF')
            lbl_count.pack()
            self.point_count_labels.append(lbl_count)
        
        # 更新点数统计显示
        self.update_points_stats()

    def update_last_game_display(self):
        """更新上局点数显示（使用JSON的01_Data资料）"""
        records = self.history_data.get("100_Record", {})
        latest_record = records.get("01_Data", [])
        
        if latest_record and len(latest_record) >= 3:
            # 显示骰子图片
            for i, lbl in enumerate(self.last_dice_labels):
                lbl.config(image=self.dice_images_small[latest_record[i]-1])
            
            # 计算总点数和结果类型
            total = sum(latest_record)
            is_triple = (latest_record[0] == latest_record[1] == latest_record[2])
            rtype = "围" if is_triple else ("大" if total >= 11 else "小")
            
            # 更新点数标签和结果标签
            self.last_points_label.config(text=f"{total}点")
            self.last_result_label.config(text=rtype)
        else:
            # 没有历史记录，清空显示
            for lbl in self.last_dice_labels:
                lbl.config(image='')
            self.last_points_label.config(text="--点")
            self.last_result_label.config(text="--")

    def update_last_triple_display(self):
        """更新最后一次围骰显示（局数前）"""
        # 直接从历史数据中获取Last_Triple
        last_triple = self.history_data.get("Last_Triple", [0, 0])
        
        if last_triple[0] > 0:
            # 显示三个相同的骰子图片
            for lbl in self.last_triple_dice_labels:
                lbl.config(image=self.dice_images_small[last_triple[0]-1])
            # 显示局数信息
            info_text = f"{last_triple[1]}局前"
            self.last_triple_info_label.config(text=info_text)
        else:
            # 没有围骰记录，清除图片显示
            for lbl in self.last_triple_dice_labels:
                lbl.config(image='')
            # 显示无记录信息
            self.last_triple_info_label.config(text="无记录")

    def update_win_distribution(self):
        """基于最近100局计算分布并显示（使用 place 放置 colored labels）"""
        records = self.history_data.get("100_Record", {})
        small = triple = big = 0
        # 遍历 01..50（01 是最新）
        for i in range(1, MAX_RECORDS+1):
            rec = records.get(f"{i:02d}_Data", [])
            if not rec or len(rec) < 3:
                continue
            
            # 首先检查是否为围骰
            is_triple = (rec[0] == rec[1] == rec[2])
            if is_triple:
                triple += 1
                continue  # 跳过大小判断
            
            # 非围骰情况才判断大小
            total = sum(rec)
            if total <= 10:
                small += 1
            else:
                big += 1
                
        total_games = small + triple + big

        # 计算百分比
        if total_games > 0:
            small_percent = small / total_games
            triple_percent = triple / total_games
            big_percent = big / total_games
        else:
            small_percent = triple_percent = big_percent = 0.0

        # 进度条宽度基于容器宽度（取600为最小视觉长度）
        total_width = max(200, 350)
        small_w = int(total_width * small_percent)
        triple_w = int(total_width * triple_percent)
        big_w = total_width - small_w - triple_w

        # 强制围非零时至少20像素
        if triple > 0 and triple_w < 20:
            diff = 20 - triple_w
            triple_w = 20
            if big_w >= diff:
                big_w -= diff
            elif small_w >= diff:
                small_w -= diff

        # 最小宽度保证
        if small > 0 and small_w < 8:
            small_w = 8
        if big > 0 and big_w < 8:
            big_w = 8

        # place labels
        self.small_progress.place(x=0, y=0, width=small_w, height=30)
        self.triple_progress.place(x=small_w, y=0, width=triple_w, height=30)
        self.big_progress.place(x=small_w+triple_w, y=0, width=big_w, height=30)

        # 更新 counts 文本
        self.small_count_label.config(text=f"小: {small}")
        self.triple_count_label.config(text=f"围: {triple}")
        self.big_count_label.config(text=f"大: {big}")

    def update_points_stats(self):
        """更新点数统计数据（统计各面 1~6 出现次数，基于过去100局）"""
        face_count = {i: 0 for i in range(1, 7)}
        records = self.history_data.get("100_Record", {})
        
        for i in range(1, MAX_RECORDS+1):
            dice = records.get(f"{i:02d}_Data", [])
            for face in dice:
                if 1 <= face <= 6:
                    face_count[face] += 1
        
        # 更新点数计数标签
        for idx, point in enumerate(range(1, 7)):
            self.point_count_labels[idx].config(text=str(face_count[point]))

    def create_tab1(self, parent):
        # 双骰子 1:11
        row1_frame = tk.Frame(parent, bg='#0a5f38')
        row1_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row1_frame, text="双骰子 - 1:11", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        double_frame = tk.Frame(row1_frame, bg='#0a5f38')
        double_frame.pack(fill=tk.X)
        self.double_bet_labels = {}
        
        for i in range(1, 7):
            dice_box = tk.Frame(double_frame, bg='#ffd3b6', padx=5, pady=5, cursor="hand2")
            dice_box.grid(row=0, column=i-1, padx=2, sticky="nsew")
            double_frame.columnconfigure(i-1, weight=1)
            
            dice_box.bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))
            
            dice_pair_frame = tk.Frame(dice_box, bg='#ffd3b6', cursor="hand2")
            dice_pair_frame.pack(pady=5)
            
            img_label1 = tk.Label(dice_pair_frame, image=self.dice_images_small[i-1], bg='#ffd3b6', cursor="hand2")
            img_label1.pack(side=tk.LEFT, padx=2)
            img_label1.bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))
            
            img_label2 = tk.Label(dice_pair_frame, image=self.dice_images_small[i-1], bg='#ffd3b6', cursor="hand2")
            img_label2.pack(side=tk.LEFT, padx=2)
            img_label2.bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))

            self.double_bet_labels[i] = tk.Label(dice_box, text="$0", font=("Arial", 12), bg='#ffd3b6', cursor="hand2")
            self.double_bet_labels[i].pack()
            self.double_bet_labels[i].bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))

        # 点数 4-17 同一行显示
        row_points_frame = tk.Frame(parent, bg='#0a5f38')
        row_points_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row_points_frame, text="点数", font=("Arial", 18, "bold"), 
                fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)

        points_frame_all = tk.Frame(row_points_frame, bg='#0a5f38')
        points_frame_all.pack(fill=tk.X)

        # 更新赔率
        odds = {4: 62, 5: 31, 6: 18, 7: 12, 8: 8, 9: 7, 10: 6,
                11: 6, 12: 7, 13: 8, 14: 12, 15: 18, 16: 31, 17: 62}
        self.total_points_labels = {}

        for point in range(4, 18):
            # 根据点数范围设置背景色
            bg_color = '#FFD700' if 4 <= point <= 10 else '#FF4500'
            
            # 固定宽高，不随内容变化
            point_frame = tk.Frame(points_frame_all, bg=bg_color, width=65, height=90, 
                                relief=tk.RIDGE, bd=1, cursor="hand2")
            point_frame.pack_propagate(False)  # 禁止自动调整大小
            point_frame.pack(side=tk.LEFT, padx=2, pady=2)

            point_frame.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            
            point_label = tk.Label(point_frame, text=f"{point}", font=("Arial", 20, "bold"), bg=bg_color, cursor="hand2")
            point_label.pack()
            point_label.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            
            odds_label = tk.Label(point_frame, text=f"1:{odds[point]}", font=("Arial", 12), bg=bg_color, cursor="hand2")
            odds_label.pack()
            odds_label.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            
            self.total_points_labels[point] = tk.Label(point_frame, text="$0", font=("Arial", 12), bg=bg_color, cursor="hand2")
            self.total_points_labels[point].pack()
            self.total_points_labels[point].bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))

        # 猜点数（固定格子尺寸）
        row4_frame = tk.Frame(parent, bg='#0a5f38')
        row4_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row4_frame, text="三军 - 1颗骰子1:1  2颗骰子1:2  3颗骰子1:12",
                 font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)

        guess_frame = tk.Frame(row4_frame, bg='#0a5f38')
        guess_frame.pack(fill=tk.X, padx=6)

        self.guess_num_labels = {}

        # 每格固定宽高（像素），你可以根据需要调整 width/height
        BOX_W, BOX_H = 157, 100

        for i in range(1, 7):
            # 固定尺寸的盒子（不随内部内容自动缩放）
            guess_box = tk.Frame(guess_frame, bg='#c8e6c9', width=BOX_W, height=BOX_H, relief=tk.RIDGE, bd=1, cursor="hand2")
            guess_box.pack(side=tk.LEFT, padx=1, pady=4)
            guess_box.pack_propagate(False)  # 强制固定宽高

            # handler（用默认参数固定 i）
            handler = lambda e, n=i: self.place_bet("guess_num", 1, n)

            # 将 handler 绑定到容器（额外会绑定到子控件下方）
            guess_box.bind("<Button-1>", handler)

            # 图片与金额都放在顶部顺序排列，图片底部 padding = 5 => 与金额间距为 5px
            img_label = tk.Label(guess_box, image=self.dice_images_small[i-1], bg='#c8e6c9', cursor='hand2')
            img_label.pack(side=tk.TOP, pady=(12, 5))   # 上方留 8px（美观），下方严格 5px
            img_label.bind("<Button-1>", handler)

            # 下注金额紧跟在图片下方（与图片之间就是 5px）
            amt_label = tk.Label(guess_box, text="$0", font=("Arial", 12), bg='#c8e6c9', cursor='hand2')
            amt_label.pack(side=tk.TOP)   # 不再用 side=BOTTOM，这样 amt 就紧跟图片下方
            amt_label.bind("<Button-1>", handler)

            # 保存引用，便于后续更新
            self.guess_num_labels[i] = amt_label

            # 额外保险：把当前已存在的所有子 widget 都也绑定同一 handler
            for child in guess_box.winfo_children():
                try:
                    child.bind("<Button-1>", handler)
                except Exception:
                    pass

    def create_tab2(self, parent):
        # 组合骰子
        row1_frame = tk.Frame(parent, bg='#0a5f38')
        row1_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row1_frame, text="组合骰子 - 1:6", font=("Arial", 18, "bold"),
                fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)

        pairs_frame = tk.Frame(row1_frame, bg='#0a5f38')
        pairs_frame.pack(fill=tk.X)

        self.pairs_labels = {}
        pairs = [
            (1, 2), (1, 3), (1, 4), (1, 5), (1, 6),
            (2, 3), (2, 4), (2, 5), (2, 6),
            (3, 4), (3, 5), (3, 6),
            (4, 5), (4, 6),
            (5, 6)
        ]

        for pair in pairs:
            pair_key = f"{pair[0]}&{pair[1]}"
            
            # 固定宽高的框架
            pair_box = tk.Frame(pairs_frame, bg='#e8e8e8', width=60, height=100, relief=tk.RIDGE, bd=1, cursor="hand2")
            pair_box.pack_propagate(False)  # 禁止自动调整大小
            pair_box.pack(side=tk.LEFT, padx=2, pady=2)
            pair_box.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))

            # 骰子图片上下显示
            dice_frame = tk.Frame(pair_box, bg='#e8e8e8', cursor="hand2")
            dice_frame.pack(pady=3)
            dice_frame.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))

            lbl1 = tk.Label(dice_frame, image=self.dice_images_small[pair[0]-1], bg='#e8e8e8', cursor="hand2")
            lbl1.pack(side=tk.TOP, pady=1)
            lbl1.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))

            lbl2 = tk.Label(dice_frame, image=self.dice_images_small[pair[1]-1], bg='#e8e8e8', cursor="hand2")
            lbl2.pack(side=tk.TOP, pady=1)
            lbl2.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))

            # 下注金额
            self.pairs_labels[pair_key] = tk.Label(pair_box, text="$0", font=("Arial", 10), bg='#e8e8e8', cursor="hand2")
            self.pairs_labels[pair_key].pack()
            self.pairs_labels[pair_key].bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))

        # 围骰
        row2_frame = tk.Frame(parent, bg='#0a5f38')
        row2_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row2_frame, text="围骰 - 1:190", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)  # 赔率改为190
        triple_frame = tk.Frame(row2_frame, bg='#0a5f38')
        triple_frame.pack(fill=tk.X)
        self.triple_labels = {}
        for i in range(1, 7):
            triple_box = tk.Frame(triple_frame, bg='#ffaaa5', padx=5, pady=5, cursor="hand2")
            triple_box.pack(side=tk.LEFT, padx=2, fill=tk.BOTH, expand=True)
            triple_box.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))  # 赔率改为190

            dice_frame = tk.Frame(triple_box, bg='#ffaaa5', cursor="hand2")
            dice_frame.pack(pady=5)
            dice_frame.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))  # 赔率改为190

            lbl1 = tk.Label(dice_frame, image=self.dice_images_small[i-1], bg='#ffaaa5', cursor="hand2")
            lbl1.pack(side=tk.LEFT, padx=2)
            lbl1.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))  # 赔率改为190
            
            lbl2 = tk.Label(dice_frame, image=self.dice_images_small[i-1], bg='#ffaaa5', cursor="hand2")
            lbl2.pack(side=tk.LEFT, padx=2)
            lbl2.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))  # 赔率改为190
            
            lbl3 = tk.Label(dice_frame, image=self.dice_images_small[i-1], bg='#ffaaa5', cursor="hand2")
            lbl3.pack(side=tk.LEFT, padx=2)
            lbl3.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))  # 赔率改为190

            self.triple_labels[i] = tk.Label(triple_box, text="$0", font=("Arial", 12), bg='#ffaaa5', cursor="hand2")
            self.triple_labels[i].pack()
            self.triple_labels[i].bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))  # 赔率改为190

        # 数字组合
        row3_frame = tk.Frame(parent, bg='#0a5f38')
        row3_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row3_frame, text="数字组合 - 1:7", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        group_frame = tk.Frame(row3_frame, bg='#0a5f38')
        group_frame.pack(fill=tk.X)
        self.number_group_labels = {}
        for group in ["1234", "2345", "2356", "3456"]:
            group_box = tk.Frame(group_frame, bg='#5bc0de', padx=10, pady=10, cursor="hand2")
            group_box.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
            group_box.bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))

            dice_frame = tk.Frame(group_box, bg='#5bc0de', cursor="hand2")
            dice_frame.pack(pady=5)
            dice_frame.bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))

            for num in group:
                lbl = tk.Label(dice_frame, image=self.dice_images_small[int(num)-1], bg='#5bc0de', cursor="hand2")
                lbl.pack(side=tk.LEFT, padx=2)
                lbl.bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))

            self.number_group_labels[group] = tk.Label(group_box, text="$0", font=("Arial", 12), bg='#5bc0de', cursor="hand2")
            self.number_group_labels[group].pack(pady=5)
            self.number_group_labels[group].bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))

    def set_bet_amount(self, amount):
        # 更新选择的筹码并发光
        self.bet_amount = amount
        for canvas, oval_id, value in self.chip_widgets:
            if value == amount:
                canvas.itemconfig(oval_id, outline='yellow', width=4)
            else:
                canvas.itemconfig(oval_id, outline='#333', width=2)

    def get_odds(self, point):
        # 更新赔率
        odds = {4: 62, 5: 31, 6: 18, 7: 12, 8: 8, 9: 7, 10: 6, 11: 6, 12: 7, 13: 8, 14: 12, 15: 18, 16: 31, 17: 62}
        return odds.get(point, 1)

    def place_bet(self, bet_type, odds, param=None):
        if not self.accept_bets:
            return

        # 获取当前区域当前下注额
        current_bet_amount = 0
        if param is None:
            current_bet_amount = self.bets[bet_type]
        else:
            if isinstance(self.bets[bet_type], dict):
                current_bet_amount = self.bets[bet_type][param]

        # 获取本局总下注额
        total_bet_amount = self.current_bet

        # 单区域最高下注限制 50K
        if current_bet_amount >= 50000:
            tk.messagebox.showwarning("下注限制", "当前区域已满 50K，不能再下注！")
            return

        # 本局总额最高限制 500K
        if total_bet_amount >= 500000:
            tk.messagebox.showwarning("下注限制", "本局总下注已满 500K，不能再下注！")
            return

        amount = self.bet_amount
        if amount <= 0 or amount > self.balance:
            return

        # 如果下注会超过区域 50K，自动调整下注到剩余可下注额度
        if current_bet_amount + amount > 50000:
            allowed_amount = 50000 - current_bet_amount
            if allowed_amount <= 0:
                tk.messagebox.showwarning("下注限制", "当前区域已满 50K，不能再下注！")
                return
            tk.messagebox.showwarning("下注限制", f"下注已达上限，自动调整为 {allowed_amount}")
            amount = allowed_amount

        # 如果下注会超过本局总额 500K，自动调整下注到剩余额度
        if total_bet_amount + amount > 500000:
            allowed_amount = 500000 - total_bet_amount
            if allowed_amount <= 0:
                tk.messagebox.showwarning("下注限制", "本局总下注已满 500K，不能再下注！")
                return
            tk.messagebox.showwarning("下注限制", f"本局总额已达上限，自动调整为 {allowed_amount}")
            amount = allowed_amount

        # 扣除余额并记录下注
        if param is None:
            self.bets[bet_type] += amount
        else:
            if isinstance(self.bets[bet_type], dict):
                self.bets[bet_type][param] += amount
            else:
                return
        self.current_bet += amount
        self.balance -= amount
        self.update_display()

        if self.username:
            update_balance_in_json(self.username, self.balance)

    def update_display(self):
        self.balance_label.config(text=f"餘額: ${self.balance}")
        self.current_bet_display.config(text=f"${self.current_bet}")
        self.last_win_display.config(text=f"${self.last_win}")
        self.big_bet_label.config(text=f"${self.format_amount(self.bets['big'])}")
        self.small_bet_label.config(text=f"${self.format_amount(self.bets['small'])}")
        self.odd_bet_label.config(text=f"${self.format_amount(self.bets['odd'])}")
        self.even_bet_label.config(text=f"${self.format_amount(self.bets['even'])}")

        self.all_triples_bet_label.config(text=f"${self.format_amount(self.bets['all_triples'])}")

        for i in range(1, 7):
            if i in self.double_bet_labels:
                self.double_bet_labels[i].config(text=f"${self.format_amount(self.bets['double'][i])}")
        for i in range(4, 18):
            if i in self.total_points_labels:
                self.total_points_labels[i].config(text=f"${self.format_amount(self.bets['total_points'][i])}")
        for i in range(1, 7):
            if i in self.guess_num_labels:
                self.guess_num_labels[i].config(text=f"${self.format_amount(self.bets['guess_num'][i])}")
        for pair in self.bets["pairs"]:
            if pair in self.pairs_labels:
                self.pairs_labels[pair].config(text=f"${self.format_amount(self.bets['pairs'][pair])}")
        for i in range(1, 7):
            if i in self.triple_labels:
                self.triple_labels[i].config(text=f"${self.format_amount(self.bets['triple'][i])}")
        for group in self.bets["number_group"]:
            if group in self.number_group_labels:
                self.number_group_labels[group].config(text=f"${self.format_amount(self.bets['number_group'][group])}")
                    
        # 更新上局骰子显示
        self.update_last_game_display()
        # 更新上次围骰显示
        self.update_last_triple_display()

    def roll_dice(self):
        # 即使没有下注，也可以开始游戏
        if not self.accept_bets:
            return
            
        self.accept_bets = False

        if self.enter_binding:
            self.root.unbind('<Return>')
            self.enter_binding = None

        # 创建动画窗口，结果将在动画过程中生成
        # 传递骰子对象，使用上一局的结果作为初始值
        DiceAnimationWindow(self, self.calculate_results, self.dice_objects)

    def calculate_results(self, dice):
        # 保存骰子结果用于显示
        self.last_dice = dice
        
        # 计算时使用原始顺序
        total = sum(dice)
        result_type = "大" if total >= 11 else "小"
        is_triple = (dice[0] == dice[1] == dice[2])
        if is_triple:
            result_type = "围"
        
        # 更新全局历史记录（保存为升序并做 shift）
        self.update_history(dice)

        # 更新Last_Triple
        last_triple = self.history_data.get("Last_Triple", [0, 0])
        
        if is_triple:
            # 如果是围骰，重置局数并更新点数
            last_triple = [dice[0], 1]  # 点数, 局数前=1
        elif last_triple[0] > 0:  # 如果之前有围骰记录
            # 如果不是围骰，增加局数
            last_triple[1] += 1
        
        # 保存更新后的Last_Triple
        self.history_data["Last_Triple"] = last_triple
        self.save_history_data()

        winnings = 0
        
        # 只有当有下注时才计算输赢
        if self.current_bet > 0:
            for bet_type, data in self.bets.items():
                if bet_type == "small" and not is_triple and total < 11:
                    winnings += data * 2 if data > 0 else 0
                if bet_type == "big" and not is_triple and total >= 11:
                    winnings += data * 2 if data > 0 else 0
                if bet_type == "odd" and not is_triple and total % 2 == 1:
                    winnings += data * 2 if data > 0 else 0
                if bet_type == "even" and not is_triple and total % 2 == 0:
                    winnings += data * 2 if data > 0 else 0
                if bet_type == "all_triples" and is_triple:
                    winnings += data * 31 if data > 0 else 0  # 赔率改为31
                if bet_type == "double":
                    for num, amount in data.items():
                        if amount > 0 and dice.count(num) >= 2:
                            winnings += amount * 12
                if bet_type == "total_points" and not is_triple:
                    for point, amount in data.items():
                        if amount > 0 and total == point:
                            odds = self.get_odds(point)
                            winnings += amount * (odds + 1)
                if bet_type == "pairs":
                    for pair, amount in data.items():
                        if amount > 0:
                            a, b = map(int, pair.split('&'))
                            if (dice.count(a) >= 1 and dice.count(b) >= 1) or (dice.count(a) >= 2 and b == a):
                                winnings += amount * 7
                if bet_type == "triple":
                    for num, amount in data.items():
                        if amount > 0 and dice.count(num) == 3:
                            winnings += amount * 191  # 赔率改为190+1
                if bet_type == "guess_num":
                    for num, amount in data.items():
                        if amount > 0:
                            count = dice.count(num)
                            if count == 1:
                                winnings += amount * 2  # 1倍赔率
                            elif count == 2:
                                winnings += amount * 3  # 2倍赔率
                            elif count == 3:
                                winnings += amount * 13  # 12倍赔率
                if bet_type == "number_group":
                    for group, amount in data.items():
                        if amount > 0:
                            group_set = set(int(x) for x in group)
                            # 三颗骰子必须是互不相同且皆在该组合内
                            if len(set(dice)) == 3 and set(dice).issubset(group_set):
                                winnings += amount * 8

        self.balance += winnings
        self.last_win = winnings
        self.current_bet = 0
        self.bets = {
            "small": 0,
            "all_triples": 0,
            "big": 0,
            "odd": 0,
            "even": 0,
            "double": {i: 0 for i in range(1, 7)},
            "total_points": {i: 0 for i in range(4, 18)},
            "pairs": {f"{i}&{j}": 0 for i in range(1, 7) for j in range(i+1, 7)},
            "triple": {i: 0 for i in range(1, 7)},
            "guess_num": {i: 0 for i in range(1, 7)},
            "number_group": {group: 0 for group in ["1234", "2345", "2356", "3456"]}
        }
        self.update_display()
        self.accept_bets = True

        if self.username:
            update_balance_in_json(self.username, self.balance)

        self.enter_binding = self.root.bind('<Return>', lambda event: self.roll_dice())

    def clear_bets(self):
        if not self.accept_bets:
            return
        self.balance += self.current_bet
        self.current_bet = 0
        self.bets = {
            "small": 0,
            "all_triples": 0,
            "big": 0,
            "odd": 0,
            "even": 0,
            "double": {i: 0 for i in range(1, 7)},
            "total_points": {i: 0 for i in range(4, 18)},
            "pairs": {f"{i}&{j}": 0 for i in range(1, 7) for j in range(i+1, 7)},
            "triple": {i: 0 for i in range(1, 7)},
            "guess_num": {i: 0 for i in range(1, 7)},
            "number_group": {group: 0 for group in ["1234", "2345", "2356", "3456"]}
        }
        self.update_display()

        if self.username:
            update_balance_in_json(self.username, self.balance)

def main(username=None, balance=None):
    root = tk.Tk()
    
    # 如果没有提供余额，尝试从JSON加载
    if username and balance is None:
        users = load_user_data()
        for user in users:
            if user['user_name'] == username:
                balance = float(user['cash'])
                break
        else:
            balance = 10000.0
    
    # 如果没有用户名或余额，使用默认值
    if balance is None:
        balance = 10000.0
    
    game = SicboGame(root, username, balance)
    root.mainloop()

    return game.final_balance

if __name__ == "__main__":
    final_balance = main()
    print(f"游戏结束，最终余额: ${final_balance:.2f}")