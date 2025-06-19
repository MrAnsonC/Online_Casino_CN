import tkinter as tk
from tkinter import ttk
import random
import time
from PIL import Image, ImageTk, ImageDraw
import re, os, json

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

class DiceAnimationWindow:
    def __init__(self, parent, callback, final_dice):
        self.parent = parent
        self.callback = callback
        # 保存原始骰子顺序，不排序
        self.final_dice = final_dice
        self.window = tk.Toplevel(parent)
        self.window.title("骰子摇动中...")
        self.window.geometry("500x400")
        self.window.configure(bg='#1e3d59')
        self.window.resizable(False, False)
        self.window.grab_set()

        # 窗口居中
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent_x + (parent_width - 500) // 2
        y = parent_y + (parent_height - 400) // 2
        self.window.geometry(f"500x400+{x}+{y}")

        # 生成骰子图片
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
        if elapsed < 8:  # 8秒快速变化
            self.progress['value'] = min(100, (elapsed / 8) * 100)
            for lbl in self.dice_labels:
                v = random.randint(1, 6)
                lbl.config(image=self.dice_images[v-1])
            self.window.after(100, self.animate_dice)
        elif elapsed < 10:  # 2秒静止显示最终结果（不排序）
            for i, lbl in enumerate(self.dice_labels):
                lbl.config(image=self.dice_images[self.final_dice[i]-1])
            self.status_label.config(text="骰子停止中...")
            self.window.after(100, self.animate_dice)
        elif elapsed < 13:  # 3秒显示结果（排序后）
            sorted_dice = sorted(self.final_dice)
            total = sum(sorted_dice)
            rtype = "大" if total >= 11 else "小"
            if sorted_dice[0] == sorted_dice[1] == sorted_dice[2]:
                rtype = "围"
            txt = f"骰子结果: {' '.join(map(str, sorted_dice))}  {total}({rtype})"
            self.status_label.config(text=txt)
            self.window.after(100, self.animate_dice)
        else:
            self.window.destroy()
            self.callback()

class SicboGame:
    def __init__(self, root, username=None, initial_balance=10000):
        self.root = root
        self.username = username
        self.accept_bets = True
        # 配置 Notebook 样式，使标签字体加大
        style = ttk.Style()
        style.configure('TNotebook.Tab', font=('Arial', 12, 'bold'))

        self.root.title("Sicbo 骰寶遊戲")
        self.root.geometry("1350x780")
        self.root.configure(bg='#0a5f38')
        self.enter_binding = None

        # 使用传入的初始余额
        self.balance = initial_balance
        self.final_balance = initial_balance  # 添加最终余额属性
        self.current_bet = 0
        self.bet_amount = 100
        self.last_win = 0
        self.bets = {
            "small": 0,
            "all_triples": 0,
            "big": 0,
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

        self.create_widgets()
        self.root.bind('<Return>', lambda event: self.roll_dice())
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

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
        dot_color = '#333'
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

        # 右侧面板使用Notebook
        self.right_notebook = ttk.Notebook(main_frame)
        self.right_notebook.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)

        # 控制标签页
        control_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(control_tab, text='控制面板')

        # 控制面板内容 背景颜色修改
        control_frame = tk.Frame(control_tab, bg='#D0E7FF')
        control_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 余额和投注信息
        info_frame = tk.Frame(control_frame, bg='#D0E7FF')
        info_frame.pack(fill=tk.X, pady=10)

        self.balance_label = tk.Label(info_frame, text=f"餘額: ${self.balance}",
                                     font=("Arial", 14, "bold"), fg='black', bg='#D0E7FF')
        self.balance_label.pack(side=tk.LEFT, padx=10)

        # 筹码区
        chip_frame = tk.Frame(control_frame, bg='#D0E7FF')
        chip_frame.pack(fill=tk.X, pady=(10, 5))

        tk.Label(chip_frame, text="筹码选择", font=("Arial", 14, "bold"),
                fg='black', bg='#D0E7FF').pack(anchor=tk.W, pady=5)

        row1 = tk.Frame(chip_frame, bg='#D0E7FF')
        row1.pack(fill=tk.X, pady=5)
        for idx, (label, color) in enumerate(self.chip_values[:5]):
            value = self.chips[idx]
            canvas = tk.Canvas(row1, width=50, height=50, bg='#D0E7FF', highlightthickness=0)
            canvas.pack(side=tk.LEFT, padx=10)
            oval_id = canvas.create_oval(5, 5, 45, 45, fill=color, outline='#333', width=2)
            
            # 设置特定筹码的文字颜色为白色
            text_color = 'white' if label in ['100', '200', '2K', '5K', '10K', '50K'] else 'black'
            canvas.create_text(25, 25, text=label, font=("Arial", 10, "bold"), fill=text_color)
            
            canvas.bind("<Button-1>", lambda e, c=value: self.set_bet_amount(c))
            self.chip_widgets.append((canvas, oval_id, value))

        row2 = tk.Frame(chip_frame, bg='#D0E7FF')
        row2.pack(fill=tk.X, pady=5)
        for idx, (label, color) in enumerate(self.chip_values[5:]):
            value = self.chips[idx+5]
            canvas = tk.Canvas(row2, width=50, height=50, bg='#D0E7FF', highlightthickness=0)
            canvas.pack(side=tk.LEFT, padx=10)
            oval_id = canvas.create_oval(5, 5, 45, 45, fill=color, outline='#333', width=2)
            
            # 设置特定筹码的文字颜色为白色
            text_color = 'white' if label in ['100', '200', '2K', '5K', '10K', '50K'] else 'black'
            canvas.create_text(25, 25, text=label, font=("Arial", 10, "bold"), fill=text_color)
            
            canvas.bind("<Button-1>", lambda e, c=value: self.set_bet_amount(c))
            self.chip_widgets.append((canvas, oval_id, value))

        # 历史记录放在筹码选择下方，使用自定义Frame代替Treeview
        history_container = tk.Frame(control_frame, bg='#D0E7FF')
        history_container.pack(fill=tk.BOTH, expand=True, pady=(20, 10))

        tk.Label(history_container, text="歷史記錄", font=("Arial", 16, "bold"),
                fg='black', bg='#D0E7FF').pack(anchor=tk.W, pady=5)
        
        self.history_inner = tk.Frame(history_container, bg='#D0E7FF', height=200)
        self.history_inner.pack(fill=tk.BOTH, expand=True)
        
        # 添加历史记录标题行
        title_frame = tk.Frame(self.history_inner, bg='#1e3d59', padx=5, pady=3, relief=tk.RAISED, borderwidth=1)
        title_frame.pack(fill=tk.X, padx=2, pady=(0, 5))
       
        # 当前下注信息
        bet_info_frame = tk.Frame(control_frame, bg='#D0E7FF')
        bet_info_frame.pack(fill=tk.X, pady=10)

        self.current_bet_display = tk.Label(bet_info_frame, text="本局下注: $0",
                                          font=("Arial", 14), fg='black', bg='#D0E7FF')
        self.current_bet_display.pack(side=tk.LEFT, padx=10)

        self.last_win_display = tk.Label(bet_info_frame, text="上局获胜: $0",
                                       font=("Arial", 14), fg='black', bg='#D0E7FF')
        self.last_win_display.pack(side=tk.LEFT, padx=10)

        # 控制按钮
        btn_frame = tk.Frame(control_frame, bg='#D0E7FF')
        btn_frame.pack(fill=tk.X, pady=10)

        # 修改清除按钮样式
        clear_btn = tk.Button(btn_frame, text="清除投注", font=("Arial", 14, "bold"),
                            bg='#ff4444', fg='white', width=10, command=self.clear_bets)
        clear_btn.pack(side=tk.LEFT, padx=10, expand=True)

        # 修改掷骰子按钮样式
        roll_btn = tk.Button(btn_frame, text="擲骰子 (Enter)", font=("Arial", 14, "bold"),
                           bg='#FFD700', fg='black', width=15, command=self.roll_dice)
        roll_btn.pack(side=tk.LEFT, padx=10, expand=True)

        # 左侧顶部：小 / 围骰 / 大
        top_frame = tk.Frame(left_frame, bg='#0a5f38')
        top_frame.pack(fill=tk.X, pady=(10, 10), padx=10)

        # 小框
        self.small_frame = tk.Frame(top_frame, bg='#5cb85c', padx=20, pady=10)
        self.small_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        small_click = lambda e: self.place_bet("small", 1)
        self.small_frame.bind("<Button-1>", small_click)
        small_label1 = tk.Label(self.small_frame, text="小（4-10）", font=("Arial", 16, "bold"), bg='#5cb85c')
        small_label1.pack()
        small_label1.bind("<Button-1>", small_click)
        small_label2 = tk.Label(self.small_frame, text="围骰通杀", font=("Arial", 14), bg='#5cb85c')
        small_label2.pack(pady=5)
        small_label2.bind("<Button-1>", small_click)
        self.small_bet_label = tk.Label(self.small_frame, text="$0", font=("Arial", 14), bg='#5cb85c')
        self.small_bet_label.pack(pady=5)
        self.small_bet_label.bind("<Button-1>", small_click)

        # 围骰框 (三颗一样)
        self.all_triples_frame = tk.Frame(top_frame, bg='#f0ad4e', padx=20, pady=10)
        self.all_triples_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        triple_click = lambda e: self.place_bet("all_triples", 30)
        self.all_triples_frame.bind("<Button-1>", triple_click)
        triple_label1 = tk.Label(self.all_triples_frame, text="围骰（3颗一样）", font=("Arial", 16, "bold"), bg='#f0ad4e')
        triple_label1.pack()
        triple_label1.bind("<Button-1>", triple_click)
        triple_label2 = tk.Label(self.all_triples_frame, text="1：30", font=("Arial", 14), bg='#f0ad4e')
        triple_label2.pack()
        triple_label2.bind("<Button-1>", triple_click)
        self.all_triples_bet_label = tk.Label(self.all_triples_frame, text="$0", font=("Arial", 14), bg='#f0ad4e')
        self.all_triples_bet_label.pack(pady=5)
        self.all_triples_bet_label.bind("<Button-1>", triple_click)

        # 大框
        self.big_frame = tk.Frame(top_frame, bg='#d9534f', padx=20, pady=10)
        self.big_frame.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        big_click = lambda e: self.place_bet("big", 1)
        self.big_frame.bind("<Button-1>", big_click)
        big_label1 = tk.Label(self.big_frame, text="大（11-17）", font=("Arial", 16, "bold"), bg='#d9534f')
        big_label1.pack()
        big_label1.bind("<Button-1>", big_click)
        big_label2 = tk.Label(self.big_frame, text="围骰通杀", font=("Arial", 14), bg='#d9534f')
        big_label2.pack(pady=5)
        big_label2.bind("<Button-1>", big_click)
        self.big_bet_label = tk.Label(self.big_frame, text="$0", font=("Arial", 14), bg='#d9534f')
        self.big_bet_label.pack(pady=5)
        self.big_bet_label.bind("<Button-1>", big_click)

        # 标签页
        self.tab_control = ttk.Notebook(left_frame)
        tab1 = ttk.Frame(self.tab_control)
        tab2 = ttk.Frame(self.tab_control)
        self.tab_control.add(tab1, text='基本下注')
        self.tab_control.add(tab2, text='组合下注')
        self.tab_control.pack(expand=1, fill="both", pady=(0, 10), padx=10)

        self.create_tab1(tab1)
        self.create_tab2(tab2)
        
        # 设置100筹码为默认选中
        self.set_bet_amount(100)

    def create_tab1(self, parent):
        # 双骰子 1:11
        row1_frame = tk.Frame(parent, bg='#0a5f38')
        row1_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row1_frame, text="双骰子 - 1:11", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        double_frame = tk.Frame(row1_frame, bg='#0a5f38')
        double_frame.pack(fill=tk.X)
        self.double_bet_labels = {}
        
        # 修复1: 为整个骰子盒子添加点击事件绑定
        for i in range(1, 7):
            dice_box = tk.Frame(double_frame, bg='#ffd3b6', padx=5, pady=5)
            dice_box.grid(row=0, column=i-1, padx=2, sticky="nsew")
            double_frame.columnconfigure(i-1, weight=1)
            
            # 绑定整个盒子区域
            dice_box.bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))
            
            dice_pair_frame = tk.Frame(dice_box, bg='#ffd3b6')
            dice_pair_frame.pack(pady=5)
            
            img_label1 = tk.Label(dice_pair_frame, image=self.dice_images_small[i-1], bg='#ffd3b6')
            img_label1.pack(side=tk.LEFT, padx=2)
            img_label1.bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))
            
            img_label2 = tk.Label(dice_pair_frame, image=self.dice_images_small[i-1], bg='#ffd3b6')
            img_label2.pack(side=tk.LEFT, padx=2)
            img_label2.bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))

            self.double_bet_labels[i] = tk.Label(dice_box, text="$0", font=("Arial", 12), bg='#ffd3b6')
            self.double_bet_labels[i].pack()
            self.double_bet_labels[i].bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))

        # 点数 4-10 第一行
        row2_frame = tk.Frame(parent, bg='#0a5f38')
        row2_frame.pack(fill=tk.X, pady=(10, 2))
        tk.Label(row2_frame, text="点数", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        points_frame1 = tk.Frame(row2_frame, bg='#0a5f38')
        points_frame1.pack(fill=tk.X)
        odds = {4: 60, 5: 20, 6: 18, 7: 12, 8: 8, 9: 6, 10: 6, 11: 6, 12: 6, 13: 8, 14: 12, 15: 18, 16: 20, 17: 60}
        self.total_points_labels = {}
        
        # 修复2: 为整个点数框添加点击事件绑定
        for point in range(4, 11):
            point_frame = tk.Frame(points_frame1, bg='#d4c1ec', padx=5, pady=5, relief=tk.RIDGE, bd=1)
            point_frame.pack(side=tk.LEFT, padx=2, fill=tk.BOTH, expand=True)
            
            # 绑定整个点数框
            point_frame.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            
            point_label = tk.Label(point_frame, text=f"{point}", font=("Arial", 20, "bold"), bg='#d4c1ec')
            point_label.pack()
            point_label.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            
            odds_label = tk.Label(point_frame, text=f"1:{odds[point]}", font=("Arial", 12), bg='#d4c1ec')
            odds_label.pack()
            odds_label.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            
            self.total_points_labels[point] = tk.Label(point_frame, text="$0", font=("Arial", 12), bg='#d4c1ec')
            self.total_points_labels[point].pack()
            self.total_points_labels[point].bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))

        # 黑色分割线
        separator = tk.Frame(parent, bg='black', height=2)
        separator.pack(fill=tk.X, padx=10, pady=2)

        # 点数 11-17 第二行
        row3_frame = tk.Frame(parent, bg='#0a5f38')
        row3_frame.pack(fill=tk.X, pady=(2, 5))
        points_frame2 = tk.Frame(row3_frame, bg='#0a5f38')
        points_frame2.pack(fill=tk.X)
        
        # 修复3: 为第二行点数框添加点击事件绑定
        for point in range(11, 18):
            point_frame = tk.Frame(points_frame2, bg='#d4c1ec', padx=5, pady=5, relief=tk.RIDGE, bd=1)
            point_frame.pack(side=tk.LEFT, padx=2, fill=tk.BOTH, expand=True)
            
            # 绑定整个点数框
            point_frame.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            
            point_label = tk.Label(point_frame, text=f"{point}", font=("Arial", 20, "bold"), bg='#d4c1ec')
            point_label.pack()
            point_label.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            
            odds_label = tk.Label(point_frame, text=f"1:{odds[point]}", font=("Arial", 12), bg='#d4c1ec')
            odds_label.pack()
            odds_label.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            
            self.total_points_labels[point] = tk.Label(point_frame, text="$0", font=("Arial", 12), bg='#d4c1ec')
            self.total_points_labels[point].pack()
            self.total_points_labels[point].bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))

        # 猜点数
        row4_frame = tk.Frame(parent, bg='#0a5f38')
        row4_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row4_frame, text="猜点数 - 1颗骰子1:1  2颗骰子1:2  3颗骰子1:3", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        guess_frame = tk.Frame(row4_frame, bg='#0a5f38')
        guess_frame.pack(fill=tk.X)
        self.guess_num_labels = {}
        
        # 修复4: 为整个猜点数框添加点击事件绑定
        for i in range(1, 7):
            guess_box = tk.Frame(guess_frame, bg='#c8e6c9', padx=5, pady=5)
            guess_box.pack(side=tk.LEFT, padx=2, fill=tk.BOTH, expand=True)
            
            # 绑定整个猜点数框
            guess_box.bind("<Button-1>", lambda e, n=i: self.place_bet("guess_num", 1, n))
            
            img_label = tk.Label(guess_box, image=self.dice_images_small[i-1], bg='#c8e6c9')
            img_label.pack(pady=5)
            img_label.bind("<Button-1>", lambda e, n=i: self.place_bet("guess_num", 1, n))

            self.guess_num_labels[i] = tk.Label(guess_box, text="$0", font=("Arial", 12), bg='#c8e6c9')
            self.guess_num_labels[i].pack()
            self.guess_num_labels[i].bind("<Button-1>", lambda e, n=i: self.place_bet("guess_num", 1, n))

    def create_tab2(self, parent):
        # 组合骰子
        row1_frame = tk.Frame(parent, bg='#0a5f38')
        row1_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row1_frame, text="组合骰子 - 1:6", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        pairs_frame = tk.Frame(row1_frame, bg='#0a5f38')
        pairs_frame.pack(fill=tk.X)
        pairs = [(1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (2, 3), (2, 4), (2, 5), (2, 6), (3, 4), (3, 5), (3, 6), (4, 5), (4, 6), (5, 6)]
        self.pairs_labels = {}
        for i in range(0, 15, 5):
            row_frame = tk.Frame(pairs_frame, bg='#0a5f38')
            row_frame.pack(fill=tk.X, pady=2)
            for pair in pairs[i:i+5]:
                pair_key = f"{pair[0]}&{pair[1]}"
                pair_box = tk.Frame(row_frame, bg='#e8e8e8', padx=5, pady=5)
                pair_box.pack(side=tk.LEFT, padx=2, fill=tk.BOTH, expand=True)
                pair_box.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))

                # 使用骰子图片代替文字
                dice_frame = tk.Frame(pair_box, bg='#e8e8e8')
                dice_frame.pack(pady=5)
                dice_frame.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))

                # 显示两个骰子
                lbl1 = tk.Label(dice_frame, image=self.dice_images_small[pair[0]-1], bg='#e8e8e8')
                lbl1.pack(side=tk.LEFT, padx=2)
                lbl1.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))
                
                lbl2 = tk.Label(dice_frame, image=self.dice_images_small[pair[1]-1], bg='#e8e8e8')
                lbl2.pack(side=tk.LEFT, padx=2)
                lbl2.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))

                self.pairs_labels[pair_key] = tk.Label(pair_box, text="$0", font=("Arial", 12), bg='#e8e8e8')
                self.pairs_labels[pair_key].pack()
                self.pairs_labels[pair_key].bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))

        # 围骰
        row2_frame = tk.Frame(parent, bg='#0a5f38')
        row2_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row2_frame, text="围骰 - 1:180", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        triple_frame = tk.Frame(row2_frame, bg='#0a5f38')
        triple_frame.pack(fill=tk.X)
        self.triple_labels = {}
        for i in range(1, 7):
            triple_box = tk.Frame(triple_frame, bg='#ffaaa5', padx=5, pady=5)
            triple_box.pack(side=tk.LEFT, padx=2, fill=tk.BOTH, expand=True)
            triple_box.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 180, n))

            # 使用骰子图片代替文字
            dice_frame = tk.Frame(triple_box, bg='#ffaaa5')
            dice_frame.pack(pady=5)
            dice_frame.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 180, n))

            # 显示三个骰子
            lbl1 = tk.Label(dice_frame, image=self.dice_images_small[i-1], bg='#ffaaa5')
            lbl1.pack(side=tk.LEFT, padx=2)
            lbl1.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 180, n))
            
            lbl2 = tk.Label(dice_frame, image=self.dice_images_small[i-1], bg='#ffaaa5')
            lbl2.pack(side=tk.LEFT, padx=2)
            lbl2.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 180, n))
            
            lbl3 = tk.Label(dice_frame, image=self.dice_images_small[i-1], bg='#ffaaa5')
            lbl3.pack(side=tk.LEFT, padx=2)
            lbl3.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 180, n))

            self.triple_labels[i] = tk.Label(triple_box, text="$0", font=("Arial", 12), bg='#ffaaa5')
            self.triple_labels[i].pack()
            self.triple_labels[i].bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 180, n))

        # 数字组合
        row3_frame = tk.Frame(parent, bg='#0a5f38')
        row3_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row3_frame, text="数字组合 - 1:7", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        group_frame = tk.Frame(row3_frame, bg='#0a5f38')
        group_frame.pack(fill=tk.X)
        self.number_group_labels = {}
        for group in ["1234", "2345", "2356", "3456"]:
            group_box = tk.Frame(group_frame, bg='#5bc0de', padx=10, pady=10)
            group_box.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
            group_box.bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))

            # 使用骰子图片显示组合
            dice_frame = tk.Frame(group_box, bg='#5bc0de')
            dice_frame.pack(pady=5)
            dice_frame.bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))

            # 显示组合中的四个骰子
            for num in group:
                lbl = tk.Label(dice_frame, image=self.dice_images_small[int(num)-1], bg='#5bc0de')
                lbl.pack(side=tk.LEFT, padx=2)
                lbl.bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))

            self.number_group_labels[group] = tk.Label(group_box, text="$0", font=("Arial", 12), bg='#5bc0de')
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
        odds = {4: 60, 5: 20, 6: 18, 7: 12, 8: 8, 9: 6, 10: 6, 11: 6, 12: 6, 13: 8, 14: 12, 15: 18, 16: 20, 17: 60}
        return odds.get(point, 1)

    def place_bet(self, bet_type, odds, param=None):
        if not self.accept_bets:
            return
        amount = self.bet_amount
        if amount <= 0 or amount > self.balance:
            return
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

    def add_to_history(self, dice, total, rtype):
        sorted_dice = sorted(dice)
        children = self.history_inner.winfo_children()
        record_count = len(children) - 1  # 减去标题行
        
        # 修复：当记录达到6条时，移除最旧的记录（最下面的记录行）
        if record_count >= 6:
            # 找到最旧的记录（索引为1的记录行，因为索引0是标题行）
            oldest_record = children[1]
            oldest_record.destroy()
        
        self._render_history(sorted_dice, total, rtype)

    def _render_history(self, dice, total, rtype):
        # 创建记录框架
        frame = tk.Frame(self.history_inner, bg='#D0E7FF', padx=5, pady=5, relief=tk.RIDGE, borderwidth=1)
        
        # 将新记录添加到标题行之后（最上面）
        if len(self.history_inner.winfo_children()) > 1:  # 已经有记录行
            frame.pack(fill=tk.X, padx=2, pady=2, after=self.history_inner.winfo_children()[0])
        else:
            frame.pack(fill=tk.X, padx=2, pady=2)
        
        # 骰子显示（已排序）
        dice_frame = tk.Frame(frame, bg='#D0E7FF')
        dice_frame.pack(side=tk.LEFT, padx=10)
        for d in dice:  # 使用排序后的骰子
            lbl = tk.Label(dice_frame, image=self.dice_images_small[d-1], bg='#D0E7FF')
            lbl.pack(side=tk.LEFT, padx=2)
        
        # 总点数
        total_label = tk.Label(frame, text=f"{total}", font=("Arial", 12), bg='#D0E7FF', width=5)
        total_label.pack(side=tk.LEFT, padx=10)
        
        # 类型
        type_label = tk.Label(frame, text=f"{rtype}", font=("Arial", 12), bg='#D0E7FF', width=10)
        type_label.pack(side=tk.LEFT, padx=10)

    def update_display(self):
        self.balance_label.config(text=f"餘額: ${self.balance}")
        self.current_bet_display.config(text=f"本局下注: ${self.current_bet}")
        self.last_win_display.config(text=f"上局获胜: ${self.last_win}")
        self.big_bet_label.config(text=f"${self.bets['big']}")
        self.small_bet_label.config(text=f"${self.bets['small']}")
        self.all_triples_bet_label.config(text=f"${self.bets['all_triples']}")

        for i in range(1, 7):
            if i in self.double_bet_labels:
                self.double_bet_labels[i].config(text=f"${self.bets['double'][i]}")  
        for i in range(4, 18):
            if i in self.total_points_labels:
                self.total_points_labels[i].config(text=f"${self.bets['total_points'][i]}")
        for i in range(1, 7):
            if i in self.guess_num_labels:
                self.guess_num_labels[i].config(text=f"${self.bets['guess_num'][i]}")
        for pair in self.bets["pairs"]:
            if pair in self.pairs_labels:
                self.pairs_labels[pair].config(text=f"${self.bets['pairs'][pair]}")
        for i in range(1, 7):
            if i in self.triple_labels:
                self.triple_labels[i].config(text=f"${self.bets['triple'][i]}")
        for group in self.bets["number_group"]:
            if group in self.number_group_labels:
                self.number_group_labels[group].config(text=f"${self.bets['number_group'][group]}")

    def roll_dice(self):
        if self.current_bet == 0 or not self.accept_bets:
            return
        self.accept_bets = False

        if self.enter_binding:
            self.root.unbind('<Return>')
            self.enter_binding = None

        # 生成随机骰子结果（不排序）
        dice = [random.randint(1, 6) for _ in range(3)]
        self.dice_results = dice  # 保存原始顺序
        DiceAnimationWindow(self.root, self.calculate_results, dice)

    def calculate_results(self):
        # 计算时使用原始顺序
        dice = self.dice_results
        total = sum(dice)
        result_type = "大" if total >= 11 else "小"
        if dice[0] == dice[1] == dice[2]:
            result_type = "围"
        
        self.add_to_history(dice, total, result_type)

        is_triple = (dice[0] == dice[1] == dice[2])
        winnings = 0
        for bet_type, data in self.bets.items():
            if bet_type == "small" and not is_triple and total < 11:
                winnings += data * 2 if data > 0 else 0
            if bet_type == "big" and not is_triple and total >= 11:
                winnings += data * 2 if data > 0 else 0
            if bet_type == "all_triples" and is_triple:
                winnings += data * 31 if data > 0 else 0
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
                        winnings += amount * 181
            if bet_type == "guess_num":
                for num, amount in data.items():
                    if amount > 0:
                        count = dice.count(num)
                        if count > 0:
                            winnings += amount * (count + 1)
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

        if self.balance <= 0:
            self.add_to_history([0,0,0], 0, "結束:餘額用完")

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