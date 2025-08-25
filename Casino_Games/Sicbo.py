import tkinter as tk
from tkinter import ttk, messagebox
import secrets
import time
from PIL import Image, ImageTk, ImageDraw
import os, json
import sys
import math
import re

# 获取当前文件所在目录并定位到A_Tools文件夹
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
a_tools_dir = os.path.join(parent_dir, 'A_Tools')

if a_tools_dir not in sys.path:
    sys.path.append(a_tools_dir)

def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_user_data():
    file_path = get_data_file_path()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

class Dice:
    """自定义骰子类，确保连续两次结果不是对面数字"""
    def __init__(self, value=None):
        self.last_value = None
        self.value = value or self.roll()
    
    def roll(self):
        if self.last_value is None:
            self.value = secrets.randbelow(6) + 1
        else:
            opposite = {1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1}
            opposite_value = opposite[self.last_value]
            possible_values = [i for i in range(1, 7) if i != opposite_value and i != self.last_value]
            self.value = secrets.choice(possible_values)
        
        self.last_value = self.value
        return self.value

class DiceAnimationWindow:
    def __init__(self, game, callback, dice_objects, fixed_dice=None):
        self.game = game
        self.callback = callback
        self.dice_objects = dice_objects
        self.fixed_dice = fixed_dice  # 开发者模式下的固定骰子

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
        self.final_dice = None
        
        # 计算骰子转动时间：3100到4000
        total_milliseconds = secrets.randbelow(901) + 3100
        self.total_duration = total_milliseconds / 1000.0
        # print(f"骰子动画时长: {total_milliseconds}毫秒 ({self.total_duration:.3f}秒)")
        
        self.animate_dice()

    def do_nothing(self):
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
        
        # 根据随机总时长调整动画阶段
        if elapsed < self.total_duration:
            # 更新进度条：基于随机总时长
            progress_percent = min(100, (elapsed / self.total_duration) * 100)
            self.progress['value'] = progress_percent
            
            # 如果开发者模式有固定骰子，使用固定骰子
            if self.fixed_dice:
                current_dice = self.fixed_dice
                self.final_dice = current_dice
            else:
                # 每次动画都重新掷骰子
                current_dice = [dice.roll() for dice in self.dice_objects]
                self.final_dice = current_dice
            
            # 更新骰子图像显示
            for i, lbl in enumerate(self.dice_labels):
                lbl.config(image=self.dice_images[current_dice[i]-1])
            
            # 继续动画（使用1毫秒间隔保持流畅）
            self.window.after(1, self.animate_dice)
        
        # 骰子停止阶段（1秒）
        elif elapsed < self.total_duration + 1.0:
            # 显示最终骰子结果
            for i, lbl in enumerate(self.dice_labels):
                lbl.config(image=self.dice_images[self.final_dice[i]-1])
            
            # 更新状态文本
            self.status_label.config(text="骰子停止中...")
            
            # 继续动画
            self.window.after(1, self.animate_dice)
        
        # 显示结果阶段（2秒）
        elif elapsed < self.total_duration + 3.0:
            # 排序骰子并计算总数
            sorted_dice = sorted(self.final_dice)
            total = sum(sorted_dice)
            
            # 确定结果类型
            rtype = "大" if total >= 11 else "小"
            if sorted_dice[0] == sorted_dice[1] == sorted_dice[2]:
                rtype = "围"
            
            # 设置背景颜色
            bg_color = "#FF1616" if rtype == "大" else "#CDB900"
            if rtype == "围":
                bg_color = "#32CD32"
            
            # 更新窗口颜色
            self.window.configure(bg=bg_color)
            self.dice_container.configure(bg=bg_color)
            self.status_label.configure(bg=bg_color)
            
            # 清除原有子部件
            for widget in self.status_label.winfo_children():
                widget.destroy()
            
            # 创建结果展示框架
            result_frame = tk.Frame(self.status_label, bg=bg_color)
            result_frame.pack()
            
            # 添加"本局结果"标签
            tk.Label(result_frame, text="本局结果:", font=("Arial", 18),
                     bg=bg_color, fg="black").pack(side=tk.LEFT, padx=5)
            
            # 添加骰子图像
            for i, val in enumerate(sorted_dice):
                tk.Label(result_frame, image=self.game.dice_images_small[val-1],
                         bg=bg_color).pack(side=tk.LEFT, padx=2)
                if i < 2:
                    tk.Label(result_frame, text="+", font=("Arial", 18),
                             bg=bg_color).pack(side=tk.LEFT, padx=2)
            
            # 添加总分和结果类型
            tk.Label(result_frame, text=f"= {total}点 {rtype}",
                     font=("Arial", 18, "bold"), bg=bg_color,
                     fg="black").pack(side=tk.LEFT, padx=5)
            
            # 2秒后完成
            self.window.after(2000, self.finish)

    def finish(self):
        try:
            self.window.destroy()
        except:
            pass
        if callable(self.callback):
            self.callback(self.final_dice)

# 颜色常量
COLOR_SMALL = "#FFD700"
COLOR_TIE = "#32CD32"
COLOR_BIG = "#FF4500"
BG_FRAME = "#D0E7FF"

MAX_RECORDS = 500

class SicboGame:
    def __init__(self, root, username=None, initial_balance=10000):
        self.root = root
        self.username = username
        self.accept_bets = True
        
        # 开发者模式相关变量
        self.developer_mode = False
        self.developer_dice = None
        self.clear_right_clicked = False
        
        style = ttk.Style()
        style.configure('TNotebook.Tab', font=('Arial', 12, 'bold'))

        self.root.title("Sicbo 骰寶遊戲")
        self.root.geometry("1387x715+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg='#0a5f38')
        self.enter_binding = None

        # 历史记录显示数量
        self.history_display_count = 50

        # 游戏状态变量
        self.balance = initial_balance
        self.final_balance = initial_balance
        self.current_bet = 0
        self.bet_amount = 100
        self.last_win = 0
        self.last_dice = []
        self.last_triple = [0, 0]
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

        # 骰子图片
        self.dice_images_large = []
        self.dice_images_small = []
        for i in range(1, 7):
            img_large = Image.new('RGB', (70, 70), '#e8d6b3')
            self.draw_dice(img_large, i)
            self.dice_images_large.append(ImageTk.PhotoImage(img_large))

            img_small = Image.new('RGB', (30, 30), '#e8d6b3')
            self.draw_dice(img_small, i)
            self.dice_images_small.append(ImageTk.PhotoImage(img_small))

        # 筹码系统
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
        self.chip_widgets = []
        
        # 骰子对象
        self.dice_objects = [Dice(), Dice(), Dice()]

        # 历史记录文件
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logs_dir = os.path.join(parent_dir, 'A_Logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        self.history_file = os.path.join(logs_dir, 'Sicbo.json')
        self.history_data = self.load_history_data()
        
        # 围骰模式开关 (默认为关)
        self.triple_mode = False
        
        self.create_widgets()
        self.root.bind('<Return>', lambda event: self.roll_dice())
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.update_trend_display()
    
    def on_clear_right_click(self, event):
        """清除投注按钮右键点击事件 - 开发者模式第一步"""
        self.clear_right_clicked = True

    def on_roll_right_click(self, event):
        """掷骰子按钮右键点击事件 - 开发者模式第二步
        替代原来在 shell 中使用 input() 的实现，改为弹出 Tk 窗口让玩家输入 3 个数字（可空）。
        """
        if self.clear_right_clicked:
            self.developer_mode = True
            # 重置清除按钮的右键标记（避免下次不用重复清除再进入）
            self.clear_right_clicked = False

            # 如果窗口已存在就抬到最前
            if getattr(self, 'dev_input_window', None) and tk.Toplevel.winfo_exists(self.dev_input_window):
                try:
                    self.dev_input_window.lift()
                except Exception:
                    pass
                return

            # 打开输入对话框
            self.show_developer_input_dialog()
    
    def show_developer_input_dialog(self):
        """弹出一个小窗口，包含单一输入框（玩家可输入3个数字或留空）。
        输入规则：
         - 空串：使用随机骰子（self.developer_dice = None）
         - 三个数字：每个必须为 1..6（会设置 self.developer_dice = [a,b,c]）
         - 其他或格式错误：弹窗提示并不关闭窗口，让玩家修正
        """
        win = tk.Toplevel(self.root)
        self.dev_input_window = win
        win.title("开发者模式")
        win.resizable(False, False)
        # 小窗口尺寸与父窗口居中
        try:
            win.geometry("100x70")
            win.transient(self.root)
            win.grab_set()
        except Exception:
            pass

        entry = tk.Entry(win, font=("Arial", 14))
        entry.pack(fill="x", padx=10, pady=(6, 4))
        entry.insert(0, "")  # 默认为空

        # 确认与取消按钮
        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=(0, 8))

        def on_confirm():
            txt = entry.get().strip()
            if txt == "":
                # 留空 => 随机
                self.developer_dice = None
                try:
                    win.destroy()
                except Exception:
                    pass
                return

            parts = re.split(r'[\s,;]+', txt)
            try:
                vals = list(map(int, parts))
            except Exception:
                messagebox.showwarning("输入错误", "请输入 3 个 1 到 6 之间的整数（用空格/逗号分隔），或留空。")
                return

            if len(vals) != 3 or not all(1 <= v <= 6 for v in vals):
                messagebox.showwarning("输入错误", "请输入恰好 3 个数字，且每个数字在 1 到 6 之间。")
                return

            # 通过验证 —— 设置 developer_dice（不排序，按玩家输入顺序）
            self.developer_dice = vals
            try:
                win.destroy()
            except Exception:
                pass

        def on_cancel():
            # 取消 => 清除开发者骰子（使用随机）
            self.developer_dice = None
            try:
                win.destroy()
            except Exception:
                pass

        tk.Button(btn_frame, text="确定", width=10, command=on_confirm).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="取消", width=10, command=on_cancel).pack(side=tk.LEFT, padx=6)

        # 快捷键：回车确认，Esc 取消
        win.bind("<Return>", lambda e: on_confirm())
        win.bind("<Escape>", lambda e: on_cancel())

        entry.focus_set()

    def toggle_history_display_count(self):
        """切换显示的历史记录数量"""
        options = [50, 100, 250, 500]
        current_index = options.index(self.history_display_count)
        next_index = (current_index + 1) % len(options)
        self.history_display_count = options[next_index]
        
        # 更新所有相关UI元素
        self.history_tab_button.config(text=f"过去{self.history_display_count}局记录 ▼")
        self.win_distribution_label.config(text=f"最新{self.history_display_count}局的获胜分布")
        self.points_stats_label.config(text=f"最新{self.history_display_count}局中出现的点数数量")
        if self.history_display_count == 50:
            self.latest_records_label.config(text="最新50局记录")
        else:
            self.latest_records_label.config(text="最新100局记录")
        
        # 更新数据展示
        self.update_history_display()
        self.update_win_distribution()
        self.update_points_stats()

    def update_trend_display(self):
        """更新近期趋势显示为具体点数或围骰信息"""
        records = self.history_data.get("500_Record", {})
        trends = []
        
        # 获取最近5局结果
        for i in range(1, 6):
            k = f"{i:02d}_Data"
            dice = records.get(k, [])
            if dice:
                if dice[0] == dice[1] == dice[2]:
                    # 围骰显示为 T+点数 (如 T2)
                    trends.append(f"围{dice[0]}")
                    bg = 'white'
                    fg = "#448D00"
                else:
                    # 非围骰显示为总点数
                    total = sum(dice)
                    trends.append(str(total))
                    if total <= 10:
                        bg = COLOR_SMALL
                        fg = 'black'
                    else:
                        bg = COLOR_BIG   
                        fg = 'white'
            else:
                trends.append("--")
                bg = '#e8e8e8'
                fg = 'black'
            
            # 更新标签显示
            if i-1 < len(self.trend_labels):
                self.trend_labels[i-1].config(
                    text=trends[i-1],
                    bg=bg,
                    fg=fg
                )
    
    def format_amount(self, amount):
        """格式化金额显示"""
        if amount >= 1000:
            if amount >= 10000:
                return f"{amount / 1000:.1f}K"
            else:
                return str(amount)
        return f"{amount}"

    def ensure_500_Record_structure(self, block):
        """确保历史数据结构正确"""
        new_block = {f"{i:02d}_Data": [] for i in range(1, MAX_RECORDS+1)}
        if not block:
            return new_block
        for k, v in block.items():
            m = re.search(r'(\d+)', k)
            if m:
                idx = int(m.group(1))
                if 1 <= idx <= MAX_RECORDS:
                    new_block[f"{idx:02d}_Data"] = v
        if all(not re.search(r'(\d+)', k) for k in block.keys()):
            vals = list(block.values())
            for i, val in enumerate(vals[:MAX_RECORDS]):
                new_block[f"{i+1:02d}_Data"] = val
        return new_block

    def load_history_data(self):
        # 创建默认数据结构
        default_data = {
            "500_Record": {f"{i:02d}_Data": [] for i in range(1, MAX_RECORDS+1)},
            "Last_Triple": [0, 0],
            "H_Small": 0,
            "H_Triple": 0,
            "H_Big": 0,
            "H_4": 0, "H_5": 0, "H_6": 0, "H_7": 0, "H_8": 0, "H_9": 0, 
            "H_10": 0, "H_11": 0, "H_12": 0, "H_13": 0, "H_14": 0, "H_15": 0, 
            "H_16": 0, "H_17": 0,
            "H_T1": 0, "H_T2": 0, "H_T3": 0, "H_T4": 0, "H_T5": 0, "H_T6": 0
        }
        
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, default_value in default_data.items():
                        if key not in data:
                            data[key] = default_value
                    old_block = data.get("500_Record", {})
                    data["500_Record"] = self.ensure_500_Record_structure(old_block)
                    if "Last_Triple" not in data:
                        data["Last_Triple"] = [0, 0]
                    return data
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
        """更新历史记录结构"""
        block = self.history_data.setdefault("500_Record", {f"{i:02d}_Data": [] for i in range(1, MAX_RECORDS+1)})
        for i in range(MAX_RECORDS, 1, -1):
            dst = f"{i:02d}_Data"
            src = f"{i-1:02d}_Data"
            block[dst] = list(block.get(src, []))
        block["01_Data"] = list(sorted_dice)
        self.save_history_data()

    def update_history(self, dice):
        sorted_dice = sorted(dice)
        self.shift_and_insert_record(sorted_dice)
        self.update_global_stats(sorted_dice)
        self.update_history_display()
        self.update_last_game_display()
        self.update_win_distribution()
        try:
            self.update_points_stats()
        except Exception:
            pass
        self.update_trend_display()

    def update_global_stats(self, sorted_dice):
        """更新全局统计数据"""
        total = sum(sorted_dice)
        is_triple = (sorted_dice[0] == sorted_dice[1] == sorted_dice[2])
        
        if is_triple:
            self.history_data["H_Triple"] += 1
        else:
            if total <= 10:
                self.history_data["H_Small"] += 1
            else:
                self.history_data["H_Big"] += 1
        
        if 4 <= total <= 17:
            key = f"H_{total}"
            self.history_data[key] = self.history_data.get(key, 0) + 1
        
        if is_triple and 1 <= sorted_dice[0] <= 6:
            key = f"H_T{sorted_dice[0]}"
            self.history_data[key] = self.history_data.get(key, 0) + 1
        
        self.save_history_data()

    def update_history_display(self):
        """更新历史记录显示"""
        for widget in self.history_inner.winfo_children():
            widget.destroy()

        records = self.history_data.get("500_Record", {})
        display_limit = self.history_display_count if self.history_display_count <= 100 else 100

        for i in range(1, display_limit + 1):
            k = f"{i:02d}_Data"
            dice = records.get(k, [])
            if not dice or len(dice) < 3:
                continue
            total = sum(dice)
            is_triple = (dice[0] == dice[1] == dice[2])

            if is_triple:
                rtype = "围"
                bg = COLOR_TIE
            else:
                rtype = "小" if total <= 10 else "大"
                bg = COLOR_SMALL if rtype == "小" else COLOR_BIG

            frame = tk.Frame(self.history_inner, bg=bg, padx=5, pady=5, relief=tk.RIDGE, borderwidth=1)
            frame.pack(fill=tk.X, padx=2, pady=2)

            dice_frame = tk.Frame(frame, bg=bg)
            dice_frame.pack(side=tk.LEFT, padx=10)
            for d in dice:
                lbl = tk.Label(dice_frame, image=self.dice_images_small[d-1], bg=bg)
                lbl.pack(side=tk.LEFT, padx=1)

            tk.Label(frame, text=f"{total}", font=("Arial", 12), bg=bg, width=13).pack(side=tk.LEFT, padx=10)
            tk.Label(frame, text=f"{rtype}", font=("Arial", 12), bg=bg, width=7).pack(side=tk.LEFT, padx=5)

        self.update_last_triple_display()
        self.update_win_distribution()

    def on_window_close(self):
        """窗口关闭时保存余额"""
        self.final_balance = self.balance
        if self.username:
            update_balance_in_json(self.username, self.balance)
        self.root.destroy()

    def draw_dice(self, img, num):
        """绘制骰子图像"""
        draw = ImageDraw.Draw(img)
        size = img.size[0]
        dot_size = size // 10
        draw.rectangle([0, 0, size-1, size-1], outline='#333', width=2)
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
        """创建游戏界面"""
        main_frame = tk.Frame(self.root, bg='#0a5f38')
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = tk.Frame(main_frame, bg='#0a5f38')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 右侧面板
        right_container = tk.Frame(main_frame, width=375, bg='#F0F0F0', relief=tk.GROOVE, bd=1)
        right_container.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        right_container.pack_propagate(False)

        self.right_notebook = ttk.Notebook(right_container)
        self.right_notebook.pack(fill=tk.BOTH, expand=True)

        # 控制标签页
        control_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(control_tab, text='控制面板')

        # 历史记录标签页
        history_tab = ttk.Frame(self.right_notebook)
        self.right_notebook.add(history_tab, text='历史记录')
        self.create_history_tab(history_tab)

        # 控制面板内容
        control_frame = tk.Frame(control_tab, bg='#D0E7FF')
        control_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 余额和投注信息
        info_frame = tk.Frame(control_frame, bg='#D0E7FF')
        info_frame.pack(fill=tk.X, pady=5)

        self.balance_label = tk.Label(info_frame, text=f"余额: ${self.balance}",
                                    font=("Arial", 18, "bold"), fg='black', bg='#D0E7FF')
        self.balance_label.pack(side=tk.LEFT, padx=10)

        # 筹码区
        chip_frame = tk.Frame(control_frame, bg='#D0E7FF')
        chip_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 筹码选择和围骰模式开关
        chip_title_frame = tk.Frame(chip_frame, bg='#D0E7FF')
        chip_title_frame.pack(fill=tk.X, pady=2)
        
        tk.Label(chip_title_frame, text="筹码选择", font=("Arial", 18, "bold"),
                fg='black', bg='#D0E7FF').pack(side=tk.LEFT, padx=5)
        
        # 围骰模式开关
        switch_frame = tk.Frame(chip_title_frame, bg='#D0E7FF')
        switch_frame.pack(side=tk.RIGHT, padx=10)
        
        tk.Label(switch_frame, text="保险模式:", font=("Arial", 18, "bold"), bg='#D0E7FF').pack(side=tk.LEFT)
        
        # 开关按钮
        self.mode_switch = ttk.Checkbutton(
            switch_frame, 
            text="关", 
            style="Switch.TCheckbutton",
            command=self.toggle_triple_mode
        )
        self.mode_switch.pack(side=tk.LEFT, padx=5)
        self.mode_switch.state(['!alternate'])  # 初始状态为关
        
        # 自定义开关样式
        style = ttk.Style()
        style.configure("Switch.TCheckbutton", font=("Arial", 12, "bold"), width=4, relief=tk.RAISED)
        style.map("Switch.TCheckbutton", 
                 background=[('selected', '#4CAF50'), ('!selected', '#F44336')],
                 foreground=[('selected', 'white'), ('!selected', 'white')])

        row1 = tk.Frame(chip_frame, bg='#D0E7FF')
        row1.pack(fill=tk.X, pady=2)
        for idx, (label, color) in enumerate(self.chip_values[:5]):
            value = self.chips[idx]
            canvas = tk.Canvas(row1, width=60, height=60, bg='#D0E7FF', highlightthickness=0, cursor="hand2")
            canvas.pack(side=tk.LEFT, padx=5)
            oval_id = canvas.create_oval(5, 5, 55, 55, fill=color, outline='#333', width=2)
            text_color = 'white' if label in ['100', '200', '2K', '5K', '10K', '50K'] else 'black'
            canvas.create_text(30, 30, text=label, font=("Arial", 16, "bold"), fill=text_color)
            canvas.bind("<Button-1>", lambda e, c=value: self.set_bet_amount(c))
            self.chip_widgets.append((canvas, oval_id, value))

        row2 = tk.Frame(chip_frame, bg='#D0E7FF')
        row2.pack(fill=tk.X, pady=2)
        for idx, (label, color) in enumerate(self.chip_values[5:]):
            value = self.chips[idx+5]
            canvas = tk.Canvas(row2, width=60, height=60, bg='#D0E7FF', highlightthickness=0, cursor="hand2")
            canvas.pack(side=tk.LEFT, padx=5)
            oval_id = canvas.create_oval(5, 5, 55, 55, fill=color, outline='#333', width=2)
            text_color = 'white' if label in ['100', '200', '2K', '5K', '10K', '50K'] else 'black'
            canvas.create_text(30, 30, text=label, font=("Arial", 16, "bold"), fill=text_color)
            canvas.bind("<Button-1>", lambda e, c=value: self.set_bet_amount(c))
            self.chip_widgets.append((canvas, oval_id, value))

        # 每注限制
        minmax_frame = tk.Frame(control_frame, bg='#D0E7FF')
        minmax_frame.pack(fill=tk.X)

        table_border_color = "#d70000"
        table_bg = '#f9f9f9'

        outer_frame = tk.Frame(minmax_frame, bg=table_border_color, bd=2, relief=tk.SOLID)
        outer_frame.pack(padx=5, pady=5, fill=tk.X)

        header_frame = tk.Frame(outer_frame, bg=table_border_color)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="每注最低", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="每注最高", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="每局最高", font=("Arial", 12, "bold"),
                 bg=table_border_color, fg='white', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)

        content_frame = tk.Frame(outer_frame, bg=table_bg)
        content_frame.pack(fill=tk.X)
        tk.Label(content_frame, text="25", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="50,000", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="500,000", font=("Arial", 12, "bold"),
                 bg=table_bg, fg='black', width=9, pady=5).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 上局信息
        last_games_container = tk.Frame(control_frame, bg='#D0E7FF')
        last_games_container.pack(fill=tk.X, pady=10)

        table_frame = tk.Frame(last_games_container, bg='#D0E7FF')
        table_frame.pack(fill=tk.X)

        table_frame.columnconfigure(0, minsize=90)
        table_frame.columnconfigure(1, minsize=120)
        table_frame.columnconfigure(2, minsize=60)
        table_frame.columnconfigure(3, minsize=80)

        header_bg = '#1e3d59'
        tk.Label(table_frame, text="类型", font=("Arial", 12, "bold"),
                fg='white', bg=header_bg).grid(row=0, column=0, sticky='nsew', pady=4)
        tk.Label(table_frame, text="骰子", font=("Arial", 12, "bold"),
                fg='white', bg=header_bg).grid(row=0, column=1, sticky='nsew', pady=4)
        tk.Label(table_frame, text="点数", font=("Arial", 12, "bold"),
                fg='white', bg=header_bg).grid(row=0, column=2, sticky='nsew', pady=4)
        tk.Label(table_frame, text="结果", font=("Arial", 12, "bold"),
                fg='white', bg=header_bg).grid(row=0, column=3, sticky='nsew', pady=4)

        # 上局点数
        tk.Label(table_frame, text="上局点数:", font=("Arial", 12),
                bg='#D0E7FF').grid(row=1, column=0, sticky='w', padx=(6,2), pady=4)

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

        divider = tk.Frame(table_frame, bg='#1e3d59', height=2)
        divider.grid(row=2, column=0, columnspan=4, sticky='ew', padx=2, pady=(4,6))

        # 上次围骰
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

        divider = tk.Frame(table_frame, bg='#1e3d59', height=2)
        divider.grid(row=4, column=0, columnspan=4, sticky='ew', padx=2, pady=(4,6))

        # 近期趋势框架
        trend_frame = tk.Frame(table_frame, bg='#D0E7FF')
        trend_frame.grid(row=5, column=0, columnspan=4, sticky='ew', padx=2, pady=5)

        tk.Label(trend_frame, text="近期趋势:", font=("Arial", 12), 
                bg='#D0E7FF').pack(side=tk.LEFT, padx=(6, 2))

        # 创建趋势标签容器
        trend_container = tk.Frame(trend_frame, bg='#D0E7FF')
        trend_container.pack(side=tk.LEFT)

        # 创建箭头标签
        self.arrow_labels = []
        for i in range(4):
            lbl = tk.Label(trend_container, text=">", font=("Arial", 12, "bold"), 
                        bg='#D0E7FF', fg='#333')
            lbl.grid(row=0, column=i*2+1)
            self.arrow_labels.append(lbl)

        # 创建趋势点标签
        self.trend_labels = []
        for i in range(5):
            lbl = tk.Label(trend_container, text="--", font=("Arial", 12, "bold"), 
                        bg='#e8e8e8', width=3, relief=tk.SUNKEN)
            lbl.grid(row=0, column=i*2, padx=2)
            self.trend_labels.append(lbl)

        divider = tk.Frame(table_frame, bg='#1e3d59', height=2)
        divider.grid(row=6, column=0, columnspan=4, sticky='ew', padx=2, pady=(4,6))

        # 当前下注信息
        bet_info_frame = tk.Frame(control_frame, bg='#D0E7FF')
        bet_info_frame.pack(fill=tk.X, pady=3)

        label_style = {"font": ("Arial", 14, "bold"), "fg": "#333", "bg": "#D0E7FF"}
        value_style = {"font": ("Arial", 14), "fg": "black", "bg": "#D0E7FF"}

        lbl_bet_title = tk.Label(bet_info_frame, text="本局下注:", **label_style, anchor="e", width=8)
        lbl_bet_title.grid(row=0, column=0, sticky="e", padx=(10, 5), pady=3)

        self.current_bet_display = tk.Label(bet_info_frame, text="$0", **value_style, anchor="w")
        self.current_bet_display.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=3)

        lbl_win_title = tk.Label(bet_info_frame, text="上局获胜:", **label_style, anchor="e", width=8)
        lbl_win_title.grid(row=1, column=0, sticky="e", padx=(10, 5), pady=3)

        self.last_win_display = tk.Label(bet_info_frame, text="$0", **value_style, anchor="w")
        self.last_win_display.grid(row=1, column=1, sticky="w", padx=(0, 10), pady=3)

        bet_info_frame.columnconfigure(0, weight=0)
        bet_info_frame.columnconfigure(1, weight=1)

        # 控制按钮
        btn_frame = tk.Frame(control_frame, bg='#D0E7FF')
        btn_frame.pack(fill=tk.X, pady=10)

        clear_btn = tk.Button(btn_frame, text="清除投注", font=("Arial", 14, "bold"),
                            bg='#ff4444', fg='white', width=10, command=self.clear_bets, cursor="hand2")
        clear_btn.pack(side=tk.LEFT, padx=10, expand=True)
        # 绑定右键点击事件
        clear_btn.bind("<Button-3>", self.on_clear_right_click)

        roll_btn = tk.Button(btn_frame, text="擲骰子 (Enter)", font=("Arial", 14, "bold"),
                        bg=COLOR_SMALL, fg='black', width=15, command=self.roll_dice, cursor="hand2")
        roll_btn.pack(side=tk.LEFT, padx=10, expand=True)
        # 绑定右键点击事件
        roll_btn.bind("<Button-3>", self.on_roll_right_click)

        def bind_click_widgets(container, handler):
            try:
                container.bind("<Button-1>", handler)
                container.bind("<Button-3>", lambda e: self.clear_single_bet_area(container))
            except Exception:
                pass
            for child in container.winfo_children():
                try:
                    child.bind("<Button-1>", handler)
                    child.bind("<Button-3>", lambda e: self.clear_single_bet_area(container))
                except Exception:
                    pass
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
        self.small_triple_bar = tk.Frame(left_col, bg="#CFA3FF", relief=tk.SUNKEN, bd=1, height=30, width=300)
        self.small_triple_bar.pack(padx=5, pady=0)
        self.small_triple_bar.pack_propagate(False)
        self.small_triple_label = tk.Label(self.small_triple_bar, text="↓↑↓↑↓ 赔率1:1  围骰通杀 ↑↓↑↓↑", font=("Arial", 14, "bold"),
                bg="#CFA3FF")
        self.small_triple_label.pack(fill=tk.BOTH, expand=True)

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
        center_col.grid(row=0, column=1, padx=5, sticky="ns")

        # 任何围骰
        self.all_triples_frame = tk.Frame(center_col, bg='#32CD32', cursor="hand2", height=180, width=340)
        self.all_triples_frame.pack(pady=(0, 0), anchor="n")
        self.all_triples_frame.pack_propagate(False)
        triple_click = lambda e, bt="all_triples", od=32: self.place_bet(bt, od)
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

        # 基本 / 组合 按钮
        tab_button_frame = tk.Frame(center_col, bg='#0a5f38')
        tab_button_frame.pack(side=tk.BOTTOM, pady=(5, 0))

        self.basic_tab_btn = tk.Button(tab_button_frame, text="基本下注", font=("Arial", 16, "bold"),
            bg='#FFA500', fg='black', cursor="hand2", relief=tk.SUNKEN,
            width=10, height=0,
            command=lambda: self.switch_tab_mode("basic"))
        self.basic_tab_btn.grid(row=0, column=0, padx=5)

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
        self.big_triple_bar = tk.Frame(right_col, bg="#FF7B00", relief=tk.SUNKEN, bd=1, height=30, width=300)
        self.big_triple_bar.pack(padx=5, pady=0)
        self.big_triple_bar.pack_propagate(False)
        self.big_triple_label = tk.Label(self.big_triple_bar, text="↓↑↓↑↓ 赔率1:1  围骰通杀 ↑↓↑↓↑", font=("Arial", 14, "bold"),
                bg='#FF7B00')
        self.big_triple_label.pack(fill=tk.BOTH, expand=True)

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

        top_frame.grid_columnconfigure(0, weight=0)
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_columnconfigure(2, weight=0)

        # 标签页容器
        PANEL_BG = "#F0F0F0"
        self.tab_container = tk.Frame(left_frame, bg=PANEL_BG, relief=tk.GROOVE, bd=2)
        self.tab_container.pack(expand=1, fill="both", pady=(0, 10), padx=10)
        self.tab_container.grid_rowconfigure(0, weight=1)
        self.tab_container.grid_columnconfigure(0, weight=1)

        tab1 = tk.Frame(self.tab_container, bg=PANEL_BG)
        tab2 = tk.Frame(self.tab_container, bg=PANEL_BG)
        tab1.grid(row=0, column=0, sticky="nsew")
        tab2.grid(row=0, column=0, sticky="nsew")
        self.tab1_frame = tab1
        self.tab2_frame = tab2

        try:
            self.tab1_frame.tkraise()
        except Exception:
            pass

        self.tab_container.grid_rowconfigure(0, weight=1)
        self.tab_container.grid_columnconfigure(0, weight=1)
        tab1.tkraise()
        self.tab_frames = (tab1, tab2)

        self.create_tab1(tab1)
        self.create_tab2(tab2)
                
        # 设置默认筹码
        self.set_bet_amount(100)
        
        # 初始化显示
        self.update_history_display()
        self.update_last_game_display()
        self.update_last_triple_display()
        self.update_win_distribution()
        self.update_points_stats()

    def toggle_triple_mode(self):
        """切换围骰模式"""
        self.triple_mode = not self.triple_mode
        
        # 更新开关文本
        if self.triple_mode:
            self.mode_switch.config(text="开")
            # 更新大小范围显示
            self.small_frame.children['!label'].config(text="小（3-10）")
            self.big_frame.children['!label'].config(text="大（11-18）")
            # 更新围骰通杀条显示
            self.small_triple_label.config(text="↑↓↑↓ 赔率1:0.97 围骰照赔 ↑↓↑↓")
            self.big_triple_label.config(text="↑↓↑↓ 赔率1:0.97 围骰照赔 ↑↓↑↓")
        else:
            self.mode_switch.config(text="关")
            # 恢复大小范围显示
            self.small_frame.children['!label'].config(text="小（4-10）")
            self.big_frame.children['!label'].config(text="大（11-17）")
            # 恢复围骰通杀条显示
            self.small_triple_label.config(text="↓↑↓↑↓ 赔率1:1  围骰通杀 ↑↓↑↓↑")
            self.big_triple_label.config(text="↓↑↓↑↓ 赔率1:1  围骰通杀 ↑↓↑↓↑")

    def switch_tab_mode(self, mode):
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
            pass

    def create_history_tab(self, parent):
        """创建历史记录标签页"""
        record_frame = tk.Frame(parent, bg='#D0E7FF')
        record_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 历史记录数量切换按钮
        self.history_tab_button = tk.Button(
            record_frame, 
            text=f"过去{self.history_display_count}局记录 ▼", 
            font=("Arial", 16, "bold"),
            bg='#D0E7FF',
            relief=tk.FLAT,
            cursor="hand2",
            command=self.toggle_history_display_count
        )
        self.history_tab_button.pack(anchor=tk.W, pady=5)
        
        if self.history_display_count == 50:
            text = "最新50局记录"
        else:
            text = "最新100局记录"
        self.latest_records_label = tk.Label(record_frame, text=text, 
                                        font=("Arial", 14, "bold"), 
                                        bg='#D0E7FF', fg='#333')
        self.latest_records_label.pack(anchor=tk.W, pady=(0, 5))
        
        # 标题行
        self.records_title_frame = tk.Frame(record_frame, bg='#1e3d59', padx=5, pady=3, relief=tk.RAISED, borderwidth=1)
        self.records_title_frame.pack(fill=tk.X, padx=2, pady=(0, 5))
        
        tk.Label(self.records_title_frame, text="骰子", font=("Arial", 12, "bold"), 
                fg='white', bg='#1e3d59', width=12).grid(row=0, column=0, sticky="w")
        tk.Label(self.records_title_frame, text="点数", font=("Arial", 12, "bold"), 
                fg='white', bg='#1e3d59', width=14).grid(row=0, column=1, sticky="w")
        tk.Label(self.records_title_frame, text="结果", font=("Arial", 12, "bold"), 
                fg='white', bg='#1e3d59', width=4).grid(row=0, column=2, sticky="w")

        # 滚动容器
        container = tk.Frame(record_frame, bg='#D0E7FF')
        container.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.history_canvas = tk.Canvas(container, bg='#D0E7FF', yscrollcommand=scrollbar.set, height=150)
        self.history_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.history_canvas.yview)
        
        self.history_inner = tk.Frame(self.history_canvas, bg='#D0E7FF')
        self.history_window = self.history_canvas.create_window((0, 0), window=self.history_inner, anchor=tk.NW)
        
        self.history_inner.bind("<Configure>", lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all")))
        self.history_canvas.bind("<Configure>", lambda e: self.history_canvas.itemconfig(self.history_window, width=e.width))
        
        self.history_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.history_inner.bind("<MouseWheel>", self._on_mousewheel)
        
        # 获胜分布部分
        distribution_frame = tk.Frame(parent, bg='#D0E7FF', padx=10, pady=10)
        distribution_frame.pack(fill=tk.X, pady=5)
        
        # 动态更新分布标题
        self.win_distribution_label = tk.Label(distribution_frame, text=f"最新{self.history_display_count}局的获胜分布", 
                                             font=("Arial", 12, "bold"), 
                                             bg='#D0E7FF')
        self.win_distribution_label.pack(anchor=tk.W, pady=5)
        
        # 小/围/大分布
        group1_frame = tk.Frame(distribution_frame, bg='#D0E7FF')
        group1_frame.pack(fill=tk.X, pady=(5, 2))
        
        self.small_label = tk.Label(group1_frame, text="小", font=("Arial", 10, "bold"), 
                                   bg='#D0E7FF', fg='black', width=3, padx=3)
        self.small_label.pack(side=tk.LEFT)
        
        progress_container = tk.Frame(group1_frame, bg='#D0E7FF', width=290, height=30)
        progress_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.small_progress = tk.Label(progress_container, text="0.0%", bg=COLOR_SMALL,
                                      fg='black', anchor='center', font=("Arial", 10, "bold"))
        self.triple_progress = tk.Label(progress_container, text="0.0%", bg=COLOR_TIE,
                                       fg='black', anchor='center', font=("Arial", 10, "bold"))
        self.big_progress = tk.Label(progress_container, text="0.0%", bg=COLOR_BIG,
                                    fg='black', anchor='center', font=("Arial", 10, "bold"))
        
        self.big_label = tk.Label(group1_frame, text="大", font=("Arial", 10, "bold"), 
                                 bg='#D0E7FF', fg='black', width=3, padx=3)
        self.big_label.pack(side=tk.RIGHT)
        
        # 单/围/双分布
        group2_frame = tk.Frame(distribution_frame, bg='#D0E7FF')
        group2_frame.pack(fill=tk.X, pady=(2, 5))
        
        self.single_label = tk.Label(group2_frame, text="单", font=("Arial", 10, "bold"), 
                                    bg='#D0E7FF', fg='black', width=3, padx=3)
        self.single_label.pack(side=tk.LEFT)
        
        progress_container2 = tk.Frame(group2_frame, bg='#D0E7FF', width=290, height=30)
        progress_container2.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.single_progress = tk.Label(progress_container2, text="0.0%", bg='#87CEEB',
                                       fg='black', anchor='center', font=("Arial", 10, "bold"))
        self.tie2_progress = tk.Label(progress_container2, text="0.0%", bg=COLOR_TIE,
                                     fg='black', anchor='center', font=("Arial", 10, "bold"))
        self.double_progress = tk.Label(progress_container2, text="0.0%", bg='#FF6B93',
                                       fg='black', anchor='center', font=("Arial", 10, "bold"))
        
        self.double_label = tk.Label(group2_frame, text="双", font=("Arial", 10, "bold"), 
                                    bg='#D0E7FF', fg='black', width=3, padx=3)
        self.double_label.pack(side=tk.RIGHT)
        
        # 点数统计
        points_frame = tk.Frame(parent, bg='#D0E7FF', padx=10, pady=5)
        points_frame.pack(fill=tk.X, pady=5)

        # 动态更新点数统计标题
        self.points_stats_label = tk.Label(points_frame, text=f"最新{self.history_display_count}局中出现的点数数量：", 
                                         font=("Arial", 12, "bold"), 
                                         bg="#D0E7FF")
        self.points_stats_label.pack(anchor=tk.W, pady=5)

        points_container = tk.Frame(points_frame, bg='#D0E7FF')
        points_container.pack(fill=tk.X, pady=5)

        grid_container = tk.Frame(points_container, bg='#D0E7FF')
        grid_container.pack()

        # 创建存储框架、排名标签的列表
        self.point_frames = []   # 每个点数一个框架（col_frame）
        self.rank_labels = []    # 每个点数一个排名标签
        self.dice_icon_labels = []  # 重新创建，因为之前是在循环内，现在我们要按顺序存储
        self.point_count_labels = []  # 重新创建

        for col, point in enumerate(range(1, 7)):
            # 每个点数的框架
            col_frame = tk.Frame(grid_container, bg='#D0E7FF')
            col_frame.grid(row=0, column=col, padx=10, pady=1)
            self.point_frames.append(col_frame)

            # 排名标签
            rank_label = tk.Label(col_frame, text="", font=("Arial", 10, "bold"), bg='#D0E7FF')
            rank_label.pack(side=tk.TOP)
            self.rank_labels.append(rank_label)

            # 骰子图标
            icon_frame = tk.Frame(col_frame, bg='#D0E7FF')
            icon_frame.pack(side=tk.TOP)
            lbl_icon = tk.Label(icon_frame, image=self.dice_images_small[point-1], bg='#D0E7FF')
            lbl_icon.pack()
            self.dice_icon_labels.append(lbl_icon)

            # 计数标签
            count_frame = tk.Frame(col_frame, bg='#D0E7FF')
            count_frame.pack(side=tk.TOP)
            lbl_count = tk.Label(count_frame, text="0", font=("Arial", 10, "bold"), bg='#D0E7FF')
            lbl_count.pack()
            self.point_count_labels.append(lbl_count)

    def _on_mousewheel(self, event):
        """处理鼠标滚轮滚动历史记录"""
        if event.delta < 0:
            self.history_canvas.yview_scroll(1, "units")
        elif event.delta > 0:
            self.history_canvas.yview_scroll(-1, "units")

    def update_last_game_display(self):
        """更新上局点数显示"""
        records = self.history_data.get("500_Record", {})
        latest_record = records.get("01_Data", [])
        
        if latest_record and len(latest_record) >= 3:
            for i, lbl in enumerate(self.last_dice_labels):
                lbl.config(image=self.dice_images_small[latest_record[i]-1])
            
            total = sum(latest_record)
            is_triple = (latest_record[0] == latest_record[1] == latest_record[2])
            rtype = "围" if is_triple else ("大" if total >= 11 else "小")
            
            self.last_points_label.config(text=f"{total}点")
            self.last_result_label.config(text=rtype)
        else:
            for lbl in self.last_dice_labels:
                lbl.config(image='')
            self.last_points_label.config(text="--点")
            self.last_result_label.config(text="--")

    def update_last_triple_display(self):
        """更新最后一次围骰显示"""
        last_triple = self.history_data.get("Last_Triple", [0, 0])
        
        if last_triple[0] > 0:
            for lbl in self.last_triple_dice_labels:
                lbl.config(image=self.dice_images_small[last_triple[0]-1])
            # 修改这里：显示为"围X"格式
            self.last_triple_points_label.config(text=f"围{last_triple[0]}")
            info_text = f"{last_triple[1]}局前"
            self.last_triple_info_label.config(text=info_text)
        else:
            for lbl in self.last_triple_dice_labels:
                lbl.config(image='')
            # 保持无记录时的显示
            self.last_triple_points_label.config(text="--")
            self.last_triple_info_label.config(text="无记录")

    def update_win_distribution(self):
        """更新获胜分布显示"""
        records = self.history_data.get("500_Record", {})
        small = triple = big = 0
        single = double = 0
        max_display = min(self.history_display_count, MAX_RECORDS)
        for i in range(1, max_display + 1):
            rec = records.get(f"{i:02d}_Data", [])
            if not rec or len(rec) < 3:
                continue

            is_triple = (rec[0] == rec[1] == rec[2])
            total = sum(rec)

            if is_triple:
                triple += 1   # ← 修复
            else:
                if total <= 10:
                    small += 1   # ← 修复
                else:
                    big += 1     # ← 修复

            if not is_triple:
                if total % 2 == 1:
                    single += 1
                else:
                    double += 1

        tie_count = triple

        # 第一组百分比计算
        if triple == 0:
            total_g1 = small + big
            if total_g1 > 0:
                small_pct = small / total_g1
                triple_pct = 0.0
                big_pct = big / total_g1
            else:
                small_pct = triple_pct = big_pct = 0.0
        else:
            total_g1 = small + triple + big
            if total_g1 > 0:
                small_pct = small / total_g1
                triple_pct = triple / total_g1
                big_pct = big / total_g1
            else:
                small_pct = triple_pct = big_pct = 0.0

        # 第二组百分比计算
        if tie_count == 0:
            total_g2 = single + double
            if total_g2 > 0:
                single_pct = single / total_g2
                tie2_pct = 0.0
                double_pct = double / total_g2
            else:
                single_pct = tie2_pct = double_pct = 0.0
        else:
            total_g2 = single + tie_count + double
            if total_g2 > 0:
                single_pct = single / total_g2
                tie2_pct = tie_count / total_g2
                double_pct = double / total_g2
            else:
                single_pct = tie2_pct = double_pct = 0.0

        # 显示设置
        total_width = 300
        height = 30
        min_triple_width = 30

        # 第一组显示
        if triple == 0:
            small_w = int(total_width * small_pct)
            big_w = total_width - small_w

            if small > 0 and small_w < 8:
                small_w = 8
                big_w = total_width - small_w
            if big > 0 and big_w < 8:
                big_w = 8
                small_w = total_width - big_w

            try:
                self.small_progress.place(x=0, y=0, width=small_w, height=height)
                self.big_progress.place(x=small_w, y=0, width=big_w, height=height)
                try:
                    self.triple_progress.place_forget()
                except Exception:
                    pass
            except Exception:
                pass
        else:
            small_w = int(total_width * small_pct)
            triple_w = int(total_width * triple_pct)
            big_w = total_width - small_w - triple_w

            if triple_w < min_triple_width:
                needed = min_triple_width - triple_w
                if big_w >= needed / 2 and small_w >= needed / 2:
                    big_w -= int(needed / 2)
                    small_w -= needed - int(needed / 2)
                elif big_w >= needed:
                    big_w -= needed
                elif small_w >= needed:
                    small_w -= needed
                else:
                    total_available = big_w + small_w
                    if total_available > 0:
                        big_w -= int(needed * big_w / total_available)
                        small_w -= needed - int(needed * big_w / total_available)
                triple_w = min_triple_width

            if small > 0 and small_w < 8:
                small_w = 8
            if big > 0 and big_w < 8:
                big_w = 8

            try:
                self.small_progress.place(x=0, y=0, width=small_w, height=height)
                self.triple_progress.place(x=small_w, y=0, width=triple_w, height=height)
                self.big_progress.place(x=small_w + triple_w, y=0, width=big_w, height=height)
            except Exception:
                pass

        # 更新第一组文本
        try:
            sp = round(small_pct * 100, 1)
            tp = round(triple_pct * 100, 1) if triple > 0 else 0.0
            bp = round(big_pct * 100, 1)

            # 根据历史记录数量决定显示格式
            if self.history_display_count in [50, 100]:
                sp_display = f"{int(round(sp))}" if sp > 0 else "0"
                tp_display = f"{int(round(tp))}" if triple != 0 and tp > 0 else "0"
                bp_display = f"{int(round(bp))}" if bp > 0 else "0"
            else:
                sp_display = f"{sp:.1f}"
                tp_display = f"{tp:.1f}" if triple != 0 else "0.0"
                bp_display = f"{bp:.1f}"

            self.small_progress.config(text=f"{sp_display}%")
            if triple != 0:
                self.triple_progress.config(text=f"{tp_display}%")
            self.big_progress.config(text=f"{bp_display}%")
        except Exception:
            pass

        # 第二组显示
        if tie_count == 0:
            single_w = int(total_width * single_pct)
            double_w = total_width - single_w

            if single > 0 and single_w < 8:
                single_w = 8
                double_w = total_width - single_w
            if double > 0 and double_w < 8:
                double_w = 8
                single_w = total_width - double_w

            try:
                self.single_progress.place(x=0, y=0, width=single_w, height=height)
                self.double_progress.place(x=single_w, y=0, width=double_w, height=height)
                try:
                    self.tie2_progress.place_forget()
                except Exception:
                    pass
            except Exception:
                pass
        else:
            single_w = int(total_width * single_pct)
            tie2_w = int(total_width * tie2_pct)
            double_w = total_width - single_w - tie2_w

            if tie2_w < min_triple_width:
                needed = min_triple_width - tie2_w
                if double_w >= needed / 2 and single_w >= needed / 2:
                    double_w -= int(needed / 2)
                    single_w -= needed - int(needed / 2)
                elif double_w >= needed:
                    double_w -= needed
                elif single_w >= needed:
                    single_w -= needed
                else:
                    total_available = double_w + single_w
                    if total_available > 0:
                        double_w -= int(needed * double_w / total_available)
                        single_w -= needed - int(needed * double_w / total_available)
                tie2_w = min_triple_width

            if single > 0 and single_w < 8:
                single_w = 8
            if double > 0 and double_w < 8:
                double_w = 8

            try:
                self.single_progress.place(x=0, y=0, width=single_w, height=height)
                self.tie2_progress.place(x=single_w, y=0, width=tie2_w, height=height)
                self.double_progress.place(x=single_w + tie2_w, y=0, width=double_w, height=height)
            except Exception:
                pass

        # 更新第二组文本
        try:
            sp2 = round(single_pct * 100, 1)
            tp2 = round(tie2_pct * 100, 1) if tie_count > 0 else 0.0
            dp2 = round(double_pct * 100, 1)

            # 根据历史记录数量决定显示格式
            if self.history_display_count in [50, 100]:
                sp2_display = f"{int(round(sp2))}" if sp2 > 0 else "0"
                tp2_display = f"{int(round(tp2))}" if tie_count != 0 and tp2 > 0 else "0"
                dp2_display = f"{int(round(dp2))}" if dp2 > 0 else "0"
            else:
                sp2_display = f"{sp2:.1f}"
                tp2_display = f"{tp2:.1f}" if tie_count != 0 else "0.0"
                dp2_display = f"{dp2:.1f}"

            self.single_progress.config(text=f"{sp2_display}%")
            if tie_count != 0:
                self.tie2_progress.config(text=f"{tp2_display}%")
            self.double_progress.config(text=f"{dp2_display}%")
        except Exception:
            pass

    def update_points_stats(self):
        """更新点数统计数据"""
        face_count = {i: 0 for i in range(1, 7)}
        records = self.history_data.get("500_Record", {})
        max_display = min(self.history_display_count, MAX_RECORDS)
        for i in range(1, max_display + 1):
            dice = records.get(f"{i:02d}_Data", [])
            for face in dice:
                if 1 <= face <= 6:
                    face_count[face] += 1
        
        # 更新计数标签
        for idx, point in enumerate(range(1, 7)):
            self.point_count_labels[idx].config(text=str(face_count[point]))
        
        # 热冷号码追踪 - 按出现次数排序
        sorted_counts = sorted(face_count.items(), key=lambda x: x[1], reverse=True)
        
        # 创建排名映射
        rank_map = {}
        current_rank = 1
        prev_count = None
        
        # 为每个点数分配排名
        for i, (num, count) in enumerate(sorted_counts):
            if count != prev_count:
                current_rank = i + 1  # 实际排名（从1开始）
            rank_map[num] = current_rank
            prev_count = count
        
        # 排名标签映射
        rank_labels = {
            1: "1ST",
            2: "2ND",
            3: "3RD",
            4: "4TH",
            5: "5TH",
            6: "6TH"
        }
        
        # 设置背景颜色和排名标签
        for idx, point in enumerate(range(1, 7)):
            rank = rank_map.get(point, 7)  # 7表示超出范围
            
            # 设置排名标签
            rank_text = rank_labels.get(rank, "")
            self.rank_labels[idx].config(text=rank_text)
            
            # 设置背景颜色（前三名使用红色背景）
            bg_color = '#FF7474' if rank <= 3 else '#D0E7FF'
            self.point_frames[idx].config(bg=bg_color)
            self.rank_labels[idx].config(bg=bg_color)
            self.dice_icon_labels[idx].config(bg=bg_color)
            self.point_count_labels[idx].config(bg=bg_color)

    def create_tab1(self, parent):
        """创建基本下注标签页"""
        # 双骰子
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
            dice_box.bind("<Button-3>", lambda e, n=i: self.clear_single_bet("double", n))
            
            dice_pair_frame = tk.Frame(dice_box, bg='#ffd3b6', cursor="hand2")
            dice_pair_frame.pack(pady=5)
            
            img_label1 = tk.Label(dice_pair_frame, image=self.dice_images_small[i-1], bg='#ffd3b6', cursor="hand2")
            img_label1.pack(side=tk.LEFT, padx=2)
            img_label1.bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))
            img_label1.bind("<Button-3>", lambda e, n=i: self.clear_s_single_bet("double", n))
            
            img_label2 = tk.Label(dice_pair_frame, image=self.dice_images_small[i-1], bg='#ffd3b6', cursor="hand2")
            img_label2.pack(side=tk.LEFT, padx=2)
            img_label2.bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))
            img_label2.bind("<Button-3>", lambda e, n=i: self.clear_single_bet("double", n))

            self.double_bet_labels[i] = tk.Label(dice_box, text="$0", font=("Arial", 12), bg='#ffd3b6', cursor="hand2")
            self.double_bet_labels[i].pack()
            self.double_bet_labels[i].bind("<Button-1>", lambda e, n=i: self.place_bet("double", 11, n))
            self.double_bet_labels[i].bind("<Button-3>", lambda e, n=i: self.clear_single_bet("double", n))

        # 点数
        row_points_frame = tk.Frame(parent, bg='#0a5f38')
        row_points_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row_points_frame, text="点数", font=("Arial", 18, "bold"), 
                fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)

        points_frame_all = tk.Frame(row_points_frame, bg='#0a5f38')
        points_frame_all.pack(fill=tk.X)

        # 赔率
        odds = {4: 62, 5: 31, 6: 18, 7: 12, 8: 8, 9: 7, 10: 6, 11: 6, 12: 7, 13: 8, 14: 12, 15: 18, 16: 31, 17: 62}
        self.total_points_labels = {}

        for point in range(4, 18):
            bg_color = '#FFD700' if 4 <= point <= 10 else '#FF4500'
            point_frame = tk.Frame(points_frame_all, bg=bg_color, width=65, height=100, 
                                relief=tk.RIDGE, bd=1, cursor="hand2")
            point_frame.pack_propagate(False)
            point_frame.pack(side=tk.LEFT, padx=2, pady=2)

            point_frame.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            point_frame.bind("<Button-3>", lambda e, p=point: self.clear_single_bet("total_points", p))
            
            point_label = tk.Label(point_frame, text=f"{point}", font=("Arial", 22, "bold"), bg=bg_color, cursor="hand2")
            point_label.pack()
            point_label.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            point_label.bind("<Button-3>", lambda e, p=point: self.clear_single_bet("total_points", p))
            
            odds_label = tk.Label(point_frame, text=f"1:{odds[point]}", font=("Arial", 12), bg=bg_color, cursor="hand2")
            odds_label.pack()
            odds_label.bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            odds_label.bind("<Button-3>", lambda e, p=point: self.clear_single_bet("total_points", p))
            
            self.total_points_labels[point] = tk.Label(point_frame, text="$0", font=("Arial", 12), bg=bg_color, cursor="hand2")
            self.total_points_labels[point].pack()
            self.total_points_labels[point].bind("<Button-1>", lambda e, p=point: self.place_bet("total_points", self.get_odds(p), p))
            self.total_points_labels[point].bind("<Button-3>", lambda e, p=point: self.clear_single_bet("total_points", p))

        # 猜点数
        row4_frame = tk.Frame(parent, bg='#0a5f38')
        row4_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row4_frame, text="三军 - 1颗骰子1:1  2颗骰子1:2  3颗骰子1:12",
                 font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)

        guess_frame = tk.Frame(row4_frame, bg='#0a5f38')
        guess_frame.pack(fill=tk.X, padx=6)

        self.guess_num_labels = {}

        BOX_W, BOX_H = 157, 80

        for i in range(1, 7):
            guess_box = tk.Frame(guess_frame, bg='#c8e6c9', width=157, height=80, relief=tk.RIDGE, bd=1, cursor="hand2")
            guess_box.pack(side=tk.LEFT, padx=1, pady=4)
            guess_box.pack_propagate(False)

            handler = lambda e, n=i: self.place_bet("guess_num", 1, n)
            clear_handler = lambda e, n=i: self.clear_single_bet("guess_num", n)

            guess_box.bind("<Button-1>", handler)
            guess_box.bind("<Button-3>", clear_handler)

            img_label = tk.Label(guess_box, image=self.dice_images_small[i-1], bg='#c8e6c9', cursor='hand2')
            img_label.pack(side=tk.TOP, pady=(12, 5))
            img_label.bind("<Button-1>", handler)
            img_label.bind("<Button-3>", clear_handler)

            amt_label = tk.Label(guess_box, text="$0", font=("Arial", 12), bg='#c8e6c9', cursor='hand2')
            amt_label.pack(side=tk.TOP)
            amt_label.bind("<Button-1>", handler)
            amt_label.bind("<Button-3>", clear_handler)

            self.guess_num_labels[i] = amt_label

            for child in guess_box.winfo_children():
                try:
                    child.bind("<Button-1>", handler)
                    child.bind("<Button-3>", clear_handler)
                except Exception:
                    pass

    def create_tab2(self, parent):
        """创建组合下注标签页"""
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
            pair_box = tk.Frame(pairs_frame, bg='#e8e8e8', width=60, height=100, relief=tk.RIDGE, bd=1, cursor="hand2")
            pair_box.pack_propagate(False)
            pair_box.pack(side=tk.LEFT, padx=2, pady=2)
            pair_box.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))
            pair_box.bind("<Button-3>", lambda e, p=pair_key: self.clear_single_bet("pairs", p))

            dice_frame = tk.Frame(pair_box, bg='#e8e8e8', cursor="hand2")
            dice_frame.pack(pady=3)
            dice_frame.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))
            dice_frame.bind("<Button-3>", lambda e, p=pair_key: self.clear_single_bet("pairs", p))

            lbl1 = tk.Label(dice_frame, image=self.dice_images_small[pair[0]-1], bg='#e8e8e8', cursor="hand2")
            lbl1.pack(side=tk.TOP, pady=1)
            lbl1.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))
            lbl1.bind("<Button-3>", lambda e, p=pair_key: self.clear_single_bet("pairs", p))

            lbl2 = tk.Label(dice_frame, image=self.dice_images_small[pair[1]-1], bg='#e8e8e8', cursor="hand2")
            lbl2.pack(side=tk.TOP, pady=1)
            lbl2.bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))
            lbl2.bind("<Button-3>", lambda e, p=pair_key: self.clear_single_bet("pairs", p))

            self.pairs_labels[pair_key] = tk.Label(pair_box, text="$0", font=("Arial", 10), bg='#e8e8e8', cursor="hand2")
            self.pairs_labels[pair_key].pack()
            self.pairs_labels[pair_key].bind("<Button-1>", lambda e, p=pair_key: self.place_bet("pairs", 6, p))
            self.pairs_labels[pair_key].bind("<Button-3>", lambda e, p=pair_key: self.clear_single_bet("pairs", p))

        # 围骰
        row2_frame = tk.Frame(parent, bg='#0a5f38')
        row2_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row2_frame, text="围骰 - 1:190", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        triple_frame = tk.Frame(row2_frame, bg='#0a5f38')
        triple_frame.pack(fill=tk.X)
        self.triple_labels = {}
        for i in range(1, 7):
            triple_box = tk.Frame(triple_frame, bg='#ffaaa5', padx=5, pady=5, cursor="hand2", 
                                width=145, height=80)
            triple_box.pack_propagate(False)
            triple_box.pack(side=tk.LEFT, padx=2, fill=tk.BOTH, expand=True)
            triple_box.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))
            triple_box.bind("<Button-3>", lambda e, n=i: self.clear_single_bet("triple", n))

            dice_frame = tk.Frame(triple_box, bg='#ffaaa5', cursor="hand2")
            dice_frame.pack(pady=5)
            dice_frame.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))
            dice_frame.bind("<Button-3>", lambda e, n=i: self.clear_single_bet("triple", n))

            lbl1 = tk.Label(dice_frame, image=self.dice_images_small[i-1], bg='#ffaaa5', cursor="hand2")
            lbl1.pack(side=tk.LEFT, padx=2)
            lbl1.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))
            lbl1.bind("<Button-3>", lambda e, n=i: self.clear_single_bet("triple", n))
            
            lbl2 = tk.Label(dice_frame, image=self.dice_images_small[i-1], bg='#ffaaa5', cursor="hand2")
            lbl2.pack(side=tk.LEFT, padx=2)
            lbl2.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))
            lbl2.bind("<Button-3>", lambda e, n=i: self.clear_single_bet("triple", n))
            
            lbl3 = tk.Label(dice_frame, image=self.dice_images_small[i-1], bg='#ffaaa5', cursor="hand2")
            lbl3.pack(side=tk.LEFT, padx=2)
            lbl3.bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))
            lbl3.bind("<Button-3>", lambda e, n=i: self.clear_single_bet("triple", n))

            self.triple_labels[i] = tk.Label(triple_box, text="$0", font=("Arial", 12), bg='#ffaaa5', cursor="hand2")
            self.triple_labels[i].pack()
            self.triple_labels[i].bind("<Button-1>", lambda e, n=i: self.place_bet("triple", 190, n))
            self.triple_labels[i].bind("<Button-3>", lambda e, n=i: self.clear_single_bet("triple", n))

        # 数字组合
        row3_frame = tk.Frame(parent, bg='#0a5f38')
        row3_frame.pack(fill=tk.X, pady=(10, 5))
        tk.Label(row3_frame, text="数字组合 - 1:7", font=("Arial", 18, "bold"), fg='white', bg='#0a5f38').pack(anchor=tk.W, padx=10, pady=5)
        group_frame = tk.Frame(row3_frame, bg='#0a5f38')
        group_frame.pack(fill=tk.X)
        self.number_group_labels = {}
        for group in ["1234", "2345", "2356", "3456"]:
            group_box = tk.Frame(group_frame, bg='#5bc0de', padx=10, pady=10, cursor="hand2", 
                                width=231, height=90)
            group_box.pack(side=tk.LEFT, padx=5)
            group_box.pack_propagate(False)  # 禁止自动调整大小
            group_box.bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))
            group_box.bind("<Button-3>", lambda e, g=group: self.clear_single_bet("number_group", g))

            dice_frame = tk.Frame(group_box, bg='#5bc0de', cursor="hand2")
            dice_frame.pack(pady=5)
            dice_frame.bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))
            dice_frame.bind("<Button-3>", lambda e, g=group: self.clear_single_bet("number_group", g))

            for num in group:
                lbl = tk.Label(dice_frame, image=self.dice_images_small[int(num)-1], bg='#5bc0de', cursor="hand2")
                lbl.pack(side=tk.LEFT, padx=2)
                lbl.bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))
                lbl.bind("<Button-3>", lambda e, g=group: self.clear_single_bet("number_group", g))

            self.number_group_labels[group] = tk.Label(group_box, text="$0", font=("Arial", 12), bg='#5bc0de', cursor="hand2")
            self.number_group_labels[group].pack(pady=5)
            self.number_group_labels[group].bind("<Button-1>", lambda e, g=group: self.place_bet("number_group", 7, g))
            self.number_group_labels[group].bind("<Button-3>", lambda e, g=group: self.clear_single_bet("number_group", g))

    def set_bet_amount(self, amount):
        """设置下注金额并高亮筹码"""
        self.bet_amount = amount
        for canvas, oval_id, value in self.chip_widgets:
            if value == amount:
                canvas.itemconfig(oval_id, outline='yellow', width=4)
            else:
                canvas.itemconfig(oval_id, outline='#333', width=2)

    def get_odds(self, point):
        """获取点数赔率"""
        odds = {4: 62, 5: 31, 6: 18, 7: 12, 8: 8, 9: 7, 10: 6, 11: 6, 12: 7, 13: 8, 14: 12, 15: 18, 16: 31, 17: 62}
        return odds.get(point, 1)

    def place_bet(self, bet_type, odds, param=None):
        """下注逻辑"""
        if not self.accept_bets:
            return

        # 获取当前区域当前下注额
        current_bet_amount = 0
        if param is None:
            current_bet_amount = self.bets[bet_type]
        else:
            if isinstance(self.bets[bet_type], dict):
                current_bet_amount = self.bets[bet_type][param]
            else:
                return

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
        """更新所有UI显示"""
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
                    
        self.update_last_game_display()
        self.update_last_triple_display()

    def roll_dice(self):
        """开始掷骰子"""
        if not self.accept_bets:
            return
            
        self.accept_bets = False

        if self.enter_binding:
            self.root.unbind('<Return>')
            self.enter_binding = None

        # 检查开发者模式
        fixed_dice = None
        if self.developer_dice:
            fixed_dice = self.developer_dice
            self.developer_dice = None

        DiceAnimationWindow(self, self.calculate_results, self.dice_objects, fixed_dice)

    def calculate_results(self, dice):
        """计算游戏结果"""
        self.last_dice = dice
        total = sum(dice)
        is_triple = (dice[0] == dice[1] == dice[2])
        
        # 根据围骰模式调整结果判断
        if self.triple_mode:  # 开模式
            # 小: 3-10点 (包括围骰)
            # 大: 11-18点 (包括围骰)
            result_type = "大" if total >= 11 else "小"
        else:  # 关模式
            # 小: 4-10点 (不包括围骰)
            # 大: 11-17点 (不包括围骰)
            if is_triple:
                result_type = "围"
            else:
                result_type = "大" if total >= 11 else "小"
        
        self.update_history(dice)

        last_triple = self.history_data.get("Last_Triple", [0, 0])
        if is_triple:
            last_triple = [dice[0], 1]
        elif last_triple[0] > 0:
            last_triple[1] += 1
        
        self.history_data["Last_Triple"] = last_triple
        self.save_history_data()

        winnings = 0
        
        if self.current_bet > 0:
            # 根据围骰模式确定赔率
            size_odds = 0.97 if self.triple_mode else 1.0
            
            for bet_type, data in self.bets.items():
                if bet_type == "small":
                    if self.triple_mode:  # 开模式: 3-10点都赢 (包括围骰)
                        if 3 <= total <= 10:
                            winnings += data * (size_odds + 1)
                    else:  # 关模式: 4-10点且不是围骰
                        if not is_triple and 4 <= total <= 10:
                            winnings += data * (size_odds + 1)
                
                if bet_type == "big":
                    if self.triple_mode:  # 开模式: 11-18点都赢 (包括围骰)
                        if 11 <= total <= 18:
                            winnings += data * (size_odds + 1)
                    else:  # 关模式: 11-17点且不是围骰
                        if not is_triple and 11 <= total <= 17:
                            winnings += data * (size_odds + 1)
                
                if bet_type == "odd":
                    if self.triple_mode:  # 开模式: 奇数点都赢 (包括围骰)
                        if total % 2 == 1:
                            winnings += data * (size_odds + 1)
                    else:  # 关模式: 奇数点且不是围骰
                        if not is_triple and total % 2 == 1:
                            winnings += data * (size_odds + 1)
                
                if bet_type == "even":
                    if self.triple_mode:  # 开模式: 偶数点都赢 (包括围骰)
                        if total % 2 == 0:
                            winnings += data * (size_odds + 1)
                    else:  # 关模式: 偶数点且不是围骰
                        if not is_triple and total % 2 == 0:
                            winnings += data * (size_odds + 1)
                
                if bet_type == "all_triples" and is_triple:
                    winnings += data * 32
                if bet_type == "double":
                    for num, amount in data.items():
                        if amount > 0 and dice.count(num) >= 2:
                            winnings += amount * 12
                if bet_type == "total_points":
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
                            winnings += amount * 191
                if bet_type == "guess_num":
                    for num, amount in data.items():
                        if amount > 0:
                            count = dice.count(num)
                            if count == 1:
                                winnings += amount * 2
                            elif count == 2:
                                winnings += amount * 3
                            elif count == 3:
                                winnings += amount * 13
                if bet_type == "number_group":
                    for group, amount in data.items():
                        if amount > 0:
                            group_set = set(int(x) for x in group)
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
        """清除所有下注"""
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
            
    def clear_single_bet(self, bet_type, param=None):
        """清除单个下注区域"""
        if not self.accept_bets:
            return
            
        # 获取当前区域的下注金额
        if param is None:
            amount = self.bets[bet_type]
            if amount == 0:
                return
            # 清零
            self.bets[bet_type] = 0
        else:
            # 对于字典类型的下注
            if isinstance(self.bets[bet_type], dict):
                amount = self.bets[bet_type][param]
                if amount == 0:
                    return
                self.bets[bet_type][param] = 0
            else:
                return

        # 将金额加回余额
        self.balance += amount
        self.current_bet -= amount
        self.update_display()

        if self.username:
            update_balance_in_json(self.username, self.balance)
            
        # 播放清除音效
        # 可选: 添加音效提示
        
    def clear_single_bet_area(self, area):
        """根据区域清除下注"""
        # 根据区域背景色判断下注类型
        bg_color = area.cget('bg')
        
        if bg_color == '#FFD700':  # 小
            self.clear_single_bet("small")
        elif bg_color == '#FF4500':  # 大
            self.clear_single_bet("big")
        elif bg_color == '#87CEEB':  # 单
            self.clear_single_bet("odd")
        elif bg_color == '#FF6B93':  # 双
            self.clear_single_bet("even")
        elif bg_color == '#32CD32':  # 任何围骰
            self.clear_single_bet("all_triples")
        else:
            # 尝试根据子元素判断
            for widget in area.winfo_children():
                if isinstance(widget, tk.Label) and hasattr(widget, 'image'):
                    # 可能是骰子区域
                    return
            # 默认清除整个区域
            self.clear_single_bet_area(area)

def main(balance=None, username=None):
    root = tk.Tk()
    
    if username and balance is None:
        users = load_user_data()
        for user in users:
            if user['user_name'] == username:
                balance = float(user['cash'])
                break
        else:
            balance = 10000.0
    
    if balance is None:
        balance = 10000.0
    
    game = SicboGame(root, username, balance)
    root.mainloop()

    return game.final_balance

if __name__ == "__main__":
    final_balance = main()
    print(f"游戏结束，最终余额: ${final_balance:.2f}")