import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw
import random
import json
import os, sys
import time
import secrets

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

class Dice:
    def __init__(self):
        self.value = 1

    def roll(self):
        self.value = random.randint(1, 6)
        return self.value

class BacboDice:
    def __init__(self):
        self.player_dice = [Dice(), Dice()]  # 闲家骰子（左边）
        self.banker_dice = [Dice(), Dice()]  # 庄家骰子（右边）
        self.player_score = 0
        self.banker_score = 0
        self.player_values = [0, 0]
        self.banker_values = [0, 0]
        self.winner = None  # 'Player', 'Banker', 'Tie'
        self.tie_total = 0  # 和局时的总点数

    def play_game(self):
        # 掷骰子
        self.player_values = [dice.roll() for dice in self.player_dice]
        self.banker_values = [dice.roll() for dice in self.banker_dice]
        
        self.player_score = sum(self.player_values)
        self.banker_score = sum(self.banker_values)
        
        self.tie_total = self.player_score + self.banker_score

        # 判断胜负
        if self.player_score > self.banker_score:
            self.winner = 'Player'  # 闲家胜
        elif self.banker_score > self.player_score:
            self.winner = 'Banker'  # 庄家胜
        else:
            self.winner = 'Tie'  # 和局


class BacboGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("骰子百家乐")
        self.geometry("1350x720+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.bet_buttons = []
        self.selected_chip = None
        self.chip_buttons = []
        self.result_text_id = None
        self.result_bg_id = None
        
        self.game = BacboDice()
        self.balance = initial_balance
        self.current_bets = {}
        self.player_dice_images = []  # 闲家骰子图片（浅蓝色背景）
        self.banker_dice_images = []  # 庄家骰子图片（浅红色背景）
        
        # 统计属性
        self.stats_counts = {
            'Player': 0,
            'Banker': 0,
            'Tie': 0
        }
        
        # 历史记录
        self.history = []  # 存储过去6局结果
        
        # 珠路图相关属性
        self.marker_results = []
        self.marker_counts = {
            'Player': 0,
            'Banker': 0,
            'Tie': 0
        }
        
        self.max_marker_rows = 6
        self.max_marker_cols = 10  # 改为10列
        
        self._load_dice_assets()
        self._create_widgets()
        self._setup_bindings()
        self.point_labels = {}
        
        self.selected_bet_amount = 1000
        self.current_bet = 0
        self.last_win = 0
        self.username = username
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # 骰子动画相关属性
        self.animation_running = False
        self.animation_start_time = 0
        self.final_player_values = None
        self.final_banker_values = None
        
        # 历史记录文件路径
        self.history_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            'A_Logs', 'Baccarat_Dice.json'
        )
        
        # 加载历史记录
        self._load_history_from_file()
        
        # 创建骰子显示区域
        self._create_dice_display()
        
    def on_close(self):
        self.destroy()
        self.quit()
    
    def _load_history_from_file(self):
        """从文件加载历史记录"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.history_file_path), exist_ok=True)
            
            if os.path.exists(self.history_file_path):
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                
                # 清空现有历史记录
                self.history = []
                self.stats_counts = {'Player': 0, 'Banker': 0, 'Tie': 0}
                self.marker_results = []
                self.marker_counts = {'Player': 0, 'Banker': 0, 'Tie': 0}
                
                # 加载最新的骰子点数（01_Data）
                if "01_Data" in history_data and len(history_data["01_Data"]) >= 4:
                    latest_data = history_data["01_Data"]
                    # 设置骰子点数
                    self.final_player_values = [latest_data[0], latest_data[1]]
                    self.final_banker_values = [latest_data[2], latest_data[3]]
                    
                    # 计算点数和赢家
                    self.game.player_score = sum(self.final_player_values)
                    self.game.banker_score = sum(self.final_banker_values)
                    self.game.tie_total = self.game.player_score + self.game.banker_score
                    
                    if self.game.player_score > self.game.banker_score:
                        self.game.winner = 'Player'
                    elif self.game.banker_score > self.game.player_score:
                        self.game.winner = 'Banker'
                    else:
                        self.game.winner = 'Tie'
                    
                    # 更新骰子显示
                    self.after(100, self._update_initial_dice_display)
                
                # 按编号顺序加载（从01到60，01是最新的）
                for i in range(1, 61):
                    key = f"{i:02d}_Data"
                    if key in history_data:
                        data = history_data[key]
                        if len(data) >= 4:
                            player_dice = [data[0], data[1]]
                            banker_dice = [data[2], data[3]]
                            player_score = sum(player_dice)
                            banker_score = sum(banker_dice)
                            
                            # 确定赢家
                            if player_score > banker_score:
                                winner = 'Player'
                            elif banker_score > player_score:
                                winner = 'Banker'
                            else:
                                winner = 'Tie'
                            
                            # 添加到历史记录
                            record = {
                                'player_dice': player_dice,
                                'banker_dice': banker_dice,
                                'winner': winner
                            }
                            
                            # 修改：直接将记录添加到列表末尾，这样01_Data会在索引0位置
                            self.history.append(record)
                            
                            # 更新统计和标记路
                            self.stats_counts[winner] += 1
                            self.marker_counts[winner] += 1
                            self.marker_results.append(winner)
                
                # 标记路只保留最近60个
                if len(self.marker_results) > 60:
                    self.marker_results = self.marker_results[:60]
                
                # 更新UI显示
                if hasattr(self, 'history_rows'):
                    self.update_history_table()
                if hasattr(self, 'marker_canvas'):
                    self._update_marker_road()
                if hasattr(self, 'stats_rows'):
                    self._update_stats_display()
            else:
                print("历史记录文件不存在，创建新文件")
                # 创建空的JSON文件
                with open(self.history_file_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
        except Exception as e:
            print(f"加载历史记录失败: {e}")

    def _update_initial_dice_display(self):
        """更新初始骰子显示（加载历史记录后）"""
        if hasattr(self, 'final_player_values') and self.final_player_values:
            # 更新闲家骰子
            for i, value in enumerate(self.final_player_values):
                if i < len(self.player_dice_labels):
                    self.player_dice_labels[i].config(image=self.player_dice_images[value-1])
            
            # 更新庄家骰子
            if hasattr(self, 'final_banker_values') and self.final_banker_values:
                for i, value in enumerate(self.final_banker_values):
                    if i < len(self.banker_dice_labels):
                        self.banker_dice_labels[i].config(image=self.banker_dice_images[value-1])
            
            # 更新点数显示
            if hasattr(self, 'player_score_label') and hasattr(self.game, 'player_score'):
                self.player_score_label.config(text=f"{self.game.player_score}")
            if hasattr(self, 'banker_score_label') and hasattr(self.game, 'banker_score'):
                self.banker_score_label.config(text=f"{self.game.banker_score}")
                
    def _save_history_to_file(self):
        """
        将本局历史保存到 JSON，并确保：
        - 若文件中存在 "60_Data"，先删除 55~60_Data 并立即写回磁盘，然后重新从磁盘加载内存（stats/history/marker）。
        - 之后按原逻辑把本局 new_data 插入为 01_Data（做 01..59 -> 02..60 的位移），原子写回磁盘。
        - 写回磁盘后**再次**从磁盘重新加载内存，保证内存与磁盘一致（以 JSON 为唯一真相）。
        """
        try:
            os.makedirs(os.path.dirname(self.history_file_path), exist_ok=True)

            # 先读取现有文件（若不存在则为 {}）
            history_data = {}
            if os.path.exists(self.history_file_path):
                try:
                    with open(self.history_file_path, 'r', encoding='utf-8') as f:
                        history_data = json.load(f)
                except Exception:
                    # 如果文件损坏，保留备份并重建空结构
                    try:
                        backup = self.history_file_path + '.corrupt.bak'
                        os.replace(self.history_file_path, backup)
                        print(f"历史文件损坏已备份到: {backup}")
                    except Exception:
                        pass
                    history_data = {}

            # **关键修改：在删除操作前先保存当前局的数据**
            # 若本局数据不完整则直接返回
            if not (hasattr(self, 'final_player_values') and getattr(self, 'final_player_values', None)
                    and hasattr(self, 'final_banker_values') and getattr(self, 'final_banker_values', None)):
                return

            # 保存当前局数据
            new_data = [
                int(self.final_player_values[0]),
                int(self.final_player_values[1]),
                int(self.final_banker_values[0]),
                int(self.final_banker_values[1])
            ]

            # --------- 第一步：如果文件中存在 60_Data，删除 55~60_Data 并立即原子写回磁盘 ---------
            if "60_Data" in history_data:
                for i in range(55, 61):
                    history_data.pop(f"{i:02d}_Data", None)

                tmp_path = self.history_file_path + '.tmp'
                with open(tmp_path, 'w', encoding='utf-8') as tf:
                    json.dump(history_data, tf, ensure_ascii=False, indent=2)
                    tf.flush()
                    try:
                        os.fsync(tf.fileno())
                    except Exception:
                        pass
                os.replace(tmp_path, self.history_file_path)

                # 立刻从磁盘重新载入内存（以 JSON 为真相）
                try:
                    # 调用现有的加载函数，它会重建 self.history/self.stats_counts/self.marker_results 并更新 UI
                    self._load_history_from_file()
                except Exception:
                    # 如果加载失败，不要中断后续保存本局流程，继续执行
                    pass

            # --------- 第二步：准备并写入本局 new_data（01_Data 插入逻辑） ---------
            # 重新读取文件（以防刚才被其他进程/逻辑修改）
            try:
                with open(self.history_file_path, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
            except Exception:
                history_data = {}

            # 将现有记录后移：59->60, 58->59, ..., 01->02
            for i in range(60, 1, -1):
                old_key = f"{(i-1):02d}_Data"
                new_key = f"{i:02d}_Data"
                if old_key in history_data:
                    history_data[new_key] = history_data[old_key]
                else:
                    # 若没有旧的则确保新的也被删除（避免残留）
                    history_data.pop(new_key, None)

            # 覆盖 01_Data 为本局新数据
            history_data["01_Data"] = new_data

            # 清理非 01..60_Data 的键（防止保留多余键）
            keys_to_remove = []
            for key in list(history_data.keys()):
                if not key.endswith("_Data") or not key[:-5].isdigit():
                    keys_to_remove.append(key)
                else:
                    num = int(key[:-5])
                    if num < 1 or num > 60:
                        keys_to_remove.append(key)
            for k in keys_to_remove:
                history_data.pop(k, None)

            # 原子写入最终更新的文件
            tmp_file = self.history_file_path + '.tmp'
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp_file, self.history_file_path)

            # --------- 第三步（关键）：写回后立即从磁盘重新加载内存和 UI（以 JSON 为单一真相） ---------
            try:
                self._load_history_from_file()
            except Exception:
                # 如果重新加载失败，记录错误但不抛出
                print("警告：写回历史后从磁盘重新加载失败（_load_history_from_file）。")

        except Exception as e:
            print(f"保存历史记录失败: {e}")
    
    def _load_dice_assets(self):
        """加载骰子图片 - 闲家浅蓝色背景，庄家浅红色背景"""
        dice_size = (80, 80)
        
        # 生成闲家骰子图片（浅蓝色背景 #87CEEB）
        for i in range(1, 7):
            img = Image.new('RGB', dice_size, '#87CEEB')  # 浅蓝色背景
            self._draw_dice(img, i)
            self.player_dice_images.append(ImageTk.PhotoImage(img))
        
        # 生成庄家骰子图片（浅红色背景 #FFB6C1）
        for i in range(1, 7):
            img = Image.new('RGB', dice_size, '#FFB6C1')  # 浅红色背景
            self._draw_dice(img, i)
            self.banker_dice_images.append(ImageTk.PhotoImage(img))
    
    def _draw_dice(self, img, num):
        """绘制骰子点数"""
        from PIL import ImageDraw
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
    
    def _create_dice_display(self):
        """创建骰子显示区域"""
        # 清除牌桌区域
        self.table_canvas.delete('all')
        
        # 绘制分隔线
        self.table_canvas.create_line(500, 50, 500, 350, width=3, fill='white', tags='divider')
        
        # 闲家区域标题
        self.table_canvas.create_text(300, 80, text="闲家", font=('微软雅黑', 40, 'bold'), fill='white')
        
        # 庄家区域标题
        self.table_canvas.create_text(700, 80, text="庄家", font=('微软雅黑', 40, 'bold'), fill='white')
        
        # 创建骰子显示框架
        # 闲家骰子框架
        self.player_dice_frame = tk.Frame(self.table_canvas, bg='#35654d', width=200, height=150)
        self.table_canvas.create_window(300, 200, window=self.player_dice_frame)
        
        # 庄家骰子框架
        self.banker_dice_frame = tk.Frame(self.table_canvas, bg='#35654d', width=200, height=150)
        self.table_canvas.create_window(700, 200, window=self.banker_dice_frame)
        
        # 创建骰子标签
        self.player_dice_labels = []
        self.banker_dice_labels = []
        
        # 闲家骰子
        for i in range(2):
            lbl = tk.Label(self.player_dice_frame, image=self.player_dice_images[0], bg='#35654d', borderwidth=0)
            lbl.pack(side=tk.LEFT, padx=20)
            self.player_dice_labels.append(lbl)
        
        # 庄家骰子
        for i in range(2):
            lbl = tk.Label(self.banker_dice_frame, image=self.banker_dice_images[0], bg='#35654d', borderwidth=0)
            lbl.pack(side=tk.LEFT, padx=20)
            self.banker_dice_labels.append(lbl)
        
        # 点数显示（在骰子左方和右方）- 修改字体大小和初始显示
        self.player_score_label = tk.Label(self.table_canvas, text="~", 
                                           font=('微软雅黑', 96, 'bold'), fg='white', bg='#35654d')
        self.table_canvas.create_window(100, 200, window=self.player_score_label)  # 闲家点数在左方
        
        self.banker_score_label = tk.Label(self.table_canvas, text="~", 
                                           font=('微软雅黑', 96, 'bold'), fg='white', bg='#35654d')
        self.table_canvas.create_window(900, 200, window=self.banker_score_label)  # 庄家点数在右方
        
        # 结果显示区域
        self.result_text_id = self.table_canvas.create_text(
            500, 370,
            text="", 
            font=('微软雅黑', 34, 'bold'),
            fill='white',
            tags=('result_text')
        )
        self.result_bg_id = self.table_canvas.create_rectangle(
            0, 0, 0, 0,
            fill='',
            outline='',
            tags=('result_bg')
        )
    
    def update_dice_display(self):
        """更新骰子显示"""
        # 更新闲家骰子
        if self.final_player_values:
            for i, value in enumerate(self.final_player_values):
                self.player_dice_labels[i].config(image=self.player_dice_images[value-1])
        
        # 更新庄家骰子
        if self.final_banker_values:
            for i, value in enumerate(self.final_banker_values):
                self.banker_dice_labels[i].config(image=self.banker_dice_images[value-1])
        
        # 更新点数显示（只显示点数，无文字）
        if self.game.player_score > 0:
            self.player_score_label.config(text=f"{self.game.player_score}")
        if self.game.banker_score > 0:
            self.banker_score_label.config(text=f"{self.game.banker_score}")
    
    def disable_all_buttons(self):
        """禁用所有按钮"""
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
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧主区域
        left_frame = ttk.Frame(main_frame, width=900)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 右侧面板
        right_frame = ttk.Frame(main_frame, width=450)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 骰子显示区域
        self.table_canvas = tk.Canvas(left_frame, bg='#35654d', highlightthickness=0, height=400)
        self.table_canvas.pack(fill=tk.BOTH, expand=False)
        
        # 下注区域
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
        
        # 初始化骰子显示
        self._create_dice_display()
    
    def _create_control_panel(self, parent):
        # 主面板
        control_frame = tk.Frame(parent, bg='#D0E7FF', width=300)
        control_frame.pack(pady=12, padx=10, fill=tk.BOTH, expand=True)
        control_frame.pack_propagate(False)
        
        # 统计显示
        self._create_stats_display(control_frame)
        
        # 历史记录表格
        self._create_history_table(control_frame)
        
        # 标记路
        self._create_marker_road(control_frame)
    
    def _create_history_table(self, parent):
        """
        创建历史记录表格（最近5局），三列：闲家 / 庄家 / 赢方。
        历史用的小骰子图像尺寸为 50x50。
        """
        # ---- 生成 50x50 的历史用骰子图片（Player / Banker）并保存在 self 上 ----
        # 依赖：self.player_dice_images 和 self.banker_dice_images 应该是已存在的 PhotoImage 列表（6张）
        # 尝试使用 PIL 以获得更好缩放质量；如果不可用，使用 subsample 回退。
        try:
            from PIL import Image, ImageTk
            pil_available = True
        except Exception:
            pil_available = False

        # 准备容器
        self.history_player_dice_images = []
        self.history_banker_dice_images = []

        # helper：把已有 PhotoImage 转为 50x50 的 PhotoImage
        if pil_available:
            # 使用 ImageTk.getimage 从 PhotoImage 得到 PIL Image，然后 resize，再转回 PhotoImage
            for img in getattr(self, 'player_dice_images', []):
                try:
                    pil_img = ImageTk.getimage(img)
                    resized = pil_img.resize((30, 30), Image.LANCZOS)
                    tkimg = ImageTk.PhotoImage(resized)
                except Exception:
                    # 出错时退回原图（避免崩溃）
                    tkimg = img
                self.history_player_dice_images.append(tkimg)
            for img in getattr(self, 'banker_dice_images', []):
                try:
                    pil_img = ImageTk.getimage(img)
                    resized = pil_img.resize((30, 30), Image.LANCZOS)
                    tkimg = ImageTk.PhotoImage(resized)
                except Exception:
                    tkimg = img
                self.history_banker_dice_images.append(tkimg)
        else:
            # 回退：使用 subsample 按整数缩小（近似为 50px）
            for img in getattr(self, 'player_dice_images', []):
                try:
                    orig_w = img.width()
                    orig_h = img.height()
                    # 计算整数缩放因子（至少为1）
                    factor_w = max(1, orig_w // 30)
                    factor_h = max(1, orig_h // 30)
                    factor = max(1, min(factor_w, factor_h))
                    tkimg = img.subsample(factor, factor)
                except Exception:
                    tkimg = img
                self.history_player_dice_images.append(tkimg)
            for img in getattr(self, 'banker_dice_images', []):
                try:
                    orig_w = img.width()
                    orig_h = img.height()
                    factor_w = max(1, orig_w // 30)
                    factor_h = max(1, orig_h // 30)
                    factor = max(1, min(factor_w, factor_h))
                    tkimg = img.subsample(factor, factor)
                except Exception:
                    tkimg = img
                self.history_banker_dice_images.append(tkimg)

        # ---- UI：创建表格 ----
        # 标题
        history_title = tk.Label(
            parent,
            text="历史记录",  # 修改为5局
            font=('微软雅黑', 12, 'bold'),
            bg='#D0E7FF',
            fg='#000000'
        )
        history_title.pack(pady=(0, 2))

        # 表格容器
        table_frame = tk.Frame(parent, bg='#F0F4F8')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=1)

        # 表头：闲家 | 庄家 | 赢方
        headers = ['闲家', '庄家', '赢方']
        for i, header in enumerate(headers):
            header_label = tk.Label(
                table_frame,
                text=header,
                font=('微软雅黑', 11, 'bold'),
                bg='#3A7BD5',
                fg='white',
                width=12,
                height=1,
                relief=tk.RAISED,
                bd=1
            )
            header_label.grid(row=0, column=i, padx=2, pady=2, sticky='nsew')

        # 创建5行数据区域（每行：player_frame(两张50x50) | banker_frame(两张50x50) | winner_lbl）
        self.history_rows = []
        for row in range(1, 6):  # 修改为5行
            # 闲家列：包含一个 frame，内含两个 Label （左最小，右最大）
            player_frame = tk.Frame(table_frame, bg='#FFFFFF', relief=tk.FLAT, bd=1)
            player_frame.grid(row=row, column=0, padx=2, pady=2, sticky='nsew')
            # 左小
            p_lbl_min = tk.Label(player_frame, bg='#FFFFFF')
            p_lbl_min.pack(side=tk.LEFT, padx=(4,2), pady=1)
            # 右大
            p_lbl_max = tk.Label(player_frame, bg='#FFFFFF')
            p_lbl_max.pack(side=tk.LEFT, padx=(2,4), pady=1)

            # 庄家列
            banker_frame = tk.Frame(table_frame, bg='#FFFFFF', relief=tk.FLAT, bd=1)
            banker_frame.grid(row=row, column=1, padx=2, pady=2, sticky='nsew')
            b_lbl_min = tk.Label(banker_frame, bg='#FFFFFF')
            b_lbl_min.pack(side=tk.LEFT, padx=(4,2), pady=1)
            b_lbl_max = tk.Label(banker_frame, bg='#FFFFFF')
            b_lbl_max.pack(side=tk.LEFT, padx=(2,4), pady=1 )

            # 赢方列（文本）
            winner_lbl = tk.Label(
                table_frame,
                text="",
                font=('微软雅黑', 11, 'bold'),
                bg='#FFFFFF',
                fg='#000000',
                width=12,
                height=2,
                relief=tk.GROOVE,
                bd=1
            )
            winner_lbl.grid(row=row, column=2, padx=2, pady=2, sticky='nsew')

            # 默认把第1张（index 0）缩小图放进去以占位（若列表非空）
            if len(self.history_player_dice_images) >= 1:
                p_lbl_min.config(image=self.history_player_dice_images[0])
                p_lbl_max.config(image=self.history_player_dice_images[0])
            if len(self.history_banker_dice_images) >= 1:
                b_lbl_min.config(image=self.history_banker_dice_images[0])
                b_lbl_max.config(image=self.history_banker_dice_images[0])

            self.history_rows.append({
                'player_imgs': [p_lbl_min, p_lbl_max],
                'banker_imgs': [b_lbl_min, b_lbl_max],
                'winner_lbl': winner_lbl
            })

        # 网格权重
        for i in range(3):
            table_frame.columnconfigure(i, weight=1)
        for r in range(6):  # 修改为6行（包含表头）
            table_frame.rowconfigure(r, weight=1, minsize=40)
    
    def update_history_table(self):
        """
        使用 self.history（最近的记录）来更新界面（历史骰子图使用 50x50 缩放图）。
        每一行显示：闲家（左小右大图标）、庄家（左小右大图标）、赢方文字（带颜色）。
        """
        # 确保缩放图片存在，否则退回使用原 images
        player_imgs = getattr(self, 'history_player_dice_images', None)
        banker_imgs = getattr(self, 'history_banker_dice_images', None)
        if not player_imgs:
            player_imgs = getattr(self, 'player_dice_images', [])
        if not banker_imgs:
            banker_imgs = getattr(self, 'banker_dice_images', [])

        # 只取最近5局（如果少于5则显示已有）
        # 修改：从历史中取最新的5条记录，01_Data（最新）在最上方
        recent_history = self.history[:5] if len(self.history) >= 5 else self.history

        # 先清空所有行为默认状态（使用第一张图作为占位）
        placeholder_p = player_imgs[0] if player_imgs else None
        placeholder_b = banker_imgs[0] if banker_imgs else None
        for row_widgets in self.history_rows:
            if placeholder_p is not None:
                row_widgets['player_imgs'][0].config(image=placeholder_p)
                row_widgets['player_imgs'][1].config(image=placeholder_p)
            if placeholder_b is not None:
                row_widgets['banker_imgs'][0].config(image=placeholder_b)
                row_widgets['banker_imgs'][1].config(image=placeholder_b)
            row_widgets['winner_lbl'].config(text="", bg='#FFFFFF')

        # 填充数据（最新的在最上方，01_Data在最上方，05_Data在最下方）
        for i, record in enumerate(recent_history):
            if i >= len(self.history_rows):
                break
            row_widgets = self.history_rows[i]
            player_vals = record.get('player_dice', [1, 1])
            banker_vals = record.get('banker_dice', [1, 1])
            winner = record.get('winner', '')

            # 左小右大显示
            p_min, p_max = sorted(player_vals)
            b_min, b_max = sorted(banker_vals)

            # 更新图片（注意下标减1）
            if 0 < p_min <= len(player_imgs):
                row_widgets['player_imgs'][0].config(image=player_imgs[p_min-1])
            if 0 < p_max <= len(player_imgs):
                row_widgets['player_imgs'][1].config(image=player_imgs[p_max-1])

            if 0 < b_min <= len(banker_imgs):
                row_widgets['banker_imgs'][0].config(image=banker_imgs[b_min-1])
            if 0 < b_max <= len(banker_imgs):
                row_widgets['banker_imgs'][1].config(image=banker_imgs[b_max-1])

            # 更新赢家文字和背景色
            if winner == 'Player':
                row_widgets['winner_lbl'].config(text="闲家", bg='#87CEEB')
            elif winner == 'Banker':
                row_widgets['winner_lbl'].config(text="庄家", bg='#FFB6C1')
            else:
                # Tie 或其他
                row_widgets['winner_lbl'].config(text="和局", bg='#D3FFCE')

    def add_history_record(self):
        """添加历史记录"""
        record = {
            'player_dice': self.final_player_values.copy(),
            'banker_dice': self.final_banker_values.copy(),
            'winner': self.game.winner
        }
        # 修改：新记录插入到列表开头（索引0位置），这样最新的显示在第一行
        self.history.insert(0, record)
        
        # 只保留最近5局
        if len(self.history) > 61:
            self.history = self.history[:61]
    
    def _create_marker_road(self, parent):
        """创建标记路"""
        marker_frame = tk.Frame(parent, bg='#D0E7FF')
        marker_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0), padx=10)
        
        # 标题
        marker_title = tk.Label(
            marker_frame,
            text="标记路",
            font=('微软雅黑', 12, 'bold'),
            bg='#D0E7FF',
            fg='#000000'
        )
        marker_title.pack(pady=(0, 5))
        
        # 创建标记路画布
        self.marker_canvas = tk.Canvas(marker_frame, bg='#D0E7FF', highlightthickness=0)
        self.marker_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 绘制标记路网格
        self._draw_marker_grid()
    
    def _draw_marker_grid(self):
        """绘制标记路网格"""
        # 清除现有内容
        self.marker_canvas.delete('all')
        
        # 网格参数 - 改为10列，单元格大小改为26px，移除间隙
        rows, cols = self.max_marker_rows, self.max_marker_cols  # 6行，10列
        cell_size = 26  # 从25px增加到26px
        padding = 0  # 移除间隙
        
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
        
        # 绘制标记
        self._update_marker_road()
    
    def _update_marker_road(self):
        """更新标记路显示"""
        # 清除所有标记
        self.marker_canvas.delete('marker')
        
        # 计算起始索引（如果结果超过60个，只显示最近的60个）
        start_idx = max(0, len(self.marker_results) - (self.max_marker_rows * self.max_marker_cols))
        
        # 绘制标记
        for idx, result in enumerate(reversed(self.marker_results[start_idx:])):
            if idx >= self.max_marker_rows * self.max_marker_cols:
                break
                
            col = idx // self.max_marker_rows
            row = idx % self.max_marker_rows
            
            # 网格参数
            cell_size = 26  # 改为26px
            padding = 0  # 移除间隙
            
            # 计算单元格位置
            x1 = padding + col * (cell_size + padding)
            y1 = padding + row * (cell_size + padding)
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            
            # 计算圆点位置
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            radius = 12  # 改为12px
            
            # 根据结果绘制圆点
            if result == 'Player':
                color = "#87CEEB"
                text = "闲"
                text_color = 'black'
            elif result == 'Banker':
                color = "#FFB6C1"
                text = "庄"
                text_color = 'black'
            else:  # Tie
                color = "#32CD32"
                text = "和"
                text_color = 'black'
            
            # 绘制主圆点
            self.marker_canvas.create_oval(
                center_x - radius, center_y - radius,
                center_x + radius, center_y + radius,
                fill=color,
                outline='#000000',
                width=1,  
                tags='marker'
            )
            
            # 添加文字
            self.marker_canvas.create_text(
                center_x, center_y,
                text=text,
                fill=text_color,
                font=('微软雅黑', '12', 'bold'),
                tags='marker'
            )
    
    def _create_stats_display(self, parent):
        """创建统计显示 - 精致表格形式"""
        # 由于标记路大小增加，统计结果往下移动18px
        self.stats_frame = tk.Frame(parent, bg='#D0E7FF', height=180)
        self.stats_frame.pack(fill=tk.X, pady=(8, 0))
        self.stats_frame.pack_propagate(False)
        
        # 标题
        title_label = tk.Label(
            self.stats_frame, 
            text="统计结果",
            font=('微软雅黑', 12, 'bold'),
            bg='#D0E7FF',
            fg='#000000'
        )
        title_label.pack()
        
        # 创建表格框架
        table_frame = tk.Frame(self.stats_frame, bg='#D0E7FF')
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 表头
        headers = ['赢家', '图标', '数量']
        for i, header in enumerate(headers):
            header_label = tk.Label(
                table_frame,
                text=header,
                font=('微软雅黑', 12, 'bold'),
                bg='#4B8BBE',
                fg='white',
                width=16,
                relief=tk.RAISED,
                bd=2
            )
            header_label.grid(row=0, column=i, padx=1, pady=1, sticky='nsew')
        
        # 定义统计项
        stats_items = [
            {'key': 'player', 'text': '闲家', 'color': '#87CEEB', 'icon_text': '闲', 'text_color': 'black'},
            {'key': 'tie', 'text': '和局', 'color': '#32CD32', 'icon_text': '和', 'text_color': 'black'},
            {'key': 'banker', 'text': '庄家', 'color': '#FFB6C1', 'icon_text': '庄', 'text_color': 'black'}
        ]
        
        # 创建统计行
        self.stats_rows = {}
        for row_idx, item in enumerate(stats_items, 1):
            # 赢家名称
            name_label = tk.Label(
                table_frame,
                text=item['text'],
                font=('微软雅黑', 14, "bold"),
                bg='#FFFFFF',
                fg='#000000',
                width=14,
                height=1,
                relief=tk.RIDGE,
                bd=1
            )
            name_label.grid(row=row_idx, column=0, padx=1, pady=1, sticky='nsew')
            
            # 图标
            icon_frame = tk.Frame(table_frame, bg='#FFFFFF', width=60, height=40)
            icon_frame.grid(row=row_idx, column=1, padx=1, pady=1, sticky='nsew')
            icon_frame.grid_propagate(False)
            
            icon_canvas = tk.Canvas(
                icon_frame, 
                width=30,  # 增大以适应更大的圆
                height=30, 
                bg='#FFFFFF',
                highlightthickness=0
            )
            icon_canvas.place(relx=0.5, rely=0.5, anchor='center')
            
            # 绘制圆圈图标 - center_x, center_y改为15,15，半径改为12
            center_x, center_y = 15, 15
            radius = 12
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
                font=('微软雅黑', 10, 'bold')
            )
            
            # 数量
            count_label = tk.Label(
                table_frame,
                text=str(self.stats_counts.get(item['key'].capitalize(), 0)),  # 初始化时显示当前数量
                font=('微软雅黑', 14, 'bold'),
                bg='#FFFFFF',
                fg='#000000',
                width=8,
                height=2,
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
        for i in range(4):
            table_frame.rowconfigure(i, weight=1, minsize=25)
    
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
            'Small': '小(2-7)',
            'ThreeOfKind': '三个一样',
            'FourOfKind': '四个一样',
            'Large': '大(8-12)',
            'Odd': '单数',
            'PlayerPair': '闲家对子',
            'BankerPair': '庄家对子',
            'Even': '双数',
            'Player': '闲家',
            'Tie': '和局',
            'Banker': '庄家'
        }
        
        # 赔率映射 - 修改：移除AllRed，增加Small和Large
        odds_map = {
            'Small': ('1:1', "#FF0000", "white", "#CC0000"),        # 新增：红色背景，白色文字
            'ThreeOfKind': ('9:1', "#FFD700", "black", "#CCAC00"),
            'FourOfKind': ('205:1', "#FF00FF", "black", "#CC00CC"),
            'Large': ('1:1', "#0000FF", "white", "#0000CC"),        # 新增：蓝色背景，白色文字
            'Odd': ('0.97:1', "#4B0082", "white", "#3A0066"),
            'PlayerPair': ('4.8:1', "#00BFFF", "black", "#0099CC"),
            'BankerPair': ('4.8:1', "#FF69B4", "black", "#CC5480"),
            'Even': ('0.97:1', "#800080", "white", "#660066"),
            'Player': ('1:1', "#87CEEB", "black", "#6BA8D6"),
            'Tie': ('最高88:1', "#32CD32", "black", "#28A428"),
            'Banker': ('1:1', "#FFB6C1", "black", "#E89CA8")
        }
        
        # 第一行：小(2-7) 三个一样 四个一样 大(8-12) - 修改：按照新顺序
        row1_frame = tk.Frame(parent, bg='#D0E7FF', height=60)
        row1_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row1_frame.pack_propagate(False)
        
        # 修改：新的第一行按钮顺序
        buttons_to_show_1 = ['Small', 'ThreeOfKind', 'FourOfKind', 'Large']
        
        for bt in buttons_to_show_1:
            odds, bg_color, text_color, disabled_color = odds_map[bt]
            display_name = bet_display_map.get(bt, bt)
            btn = tk.Button(
                row1_frame,
                text=f"{odds}\n{display_name}\n~~",
                bg=bg_color,
                fg=text_color,
                font=('微软雅黑', 11, 'bold'),
                height=3,
                width=8,  # 宽度调整为8以适应4个按钮
                wraplength=70,
                disabledforeground=text_color,
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
        
        # 第二行：单数 闲家对子 庄家对子 双数 - 保持不变
        row2_frame = tk.Frame(parent, bg='#D0E7FF', height=60)
        row2_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row2_frame.pack_propagate(False)
        
        buttons_to_show_2 = ['Odd', 'PlayerPair', 'BankerPair', 'Even']
        
        for bt in buttons_to_show_2:
            odds, bg_color, text_color, disabled_color = odds_map[bt]
            display_name = bet_display_map.get(bt, bt)
            btn = tk.Button(
                row2_frame,
                text=f"{odds}\n{display_name}\n~~",
                bg=bg_color,
                fg=text_color,
                font=('微软雅黑', 11, 'bold'),
                height=3,
                width=8,
                wraplength=67,
                disabledforeground=text_color,
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
        
        # 第三行：闲家 和局 庄家 - 保持不变
        row3_frame = tk.Frame(parent, bg='#D0E7FF', height=60)
        row3_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        row3_frame.pack_propagate(False)
        
        buttons_to_show_3 = ['Player', 'Tie', 'Banker']
        
        for bt in buttons_to_show_3:
            odds, bg_color, text_color, disabled_color = odds_map[bt]
            display_name = bet_display_map.get(bt, bt)
            btn = tk.Button(
                row3_frame,
                text=f"{odds}\n{display_name}\n~~",
                bg=bg_color,
                fg=text_color,
                font=('微软雅黑', 11, 'bold'),
                height=3,
                width=12,
                wraplength=90,
                disabledforeground=text_color,
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
        
        # 修改说明文本，移除全红的说明
        explanation = "和局赔率：2/12点88:1，3/11点25:1\n4/10点10:1，5/9点6:1，6/7/8点4:1"
        
        explanation_frame = tk.Frame(parent, bg='#D0E7FF', height=40)
        explanation_frame.pack(fill=tk.BOTH, expand=True, pady=2)
        explanation_frame.pack_propagate(False)
        
        tk.Label(
            explanation_frame,
            text=explanation,
            font=('微软雅黑', 14),
            bg='#D0E7FF'
        ).pack(expand=True)
    
    def _populate_betting_center(self, parent):
        """填充中部分：按钮和显示"""
        balance_display_frame = tk.Frame(parent, bg='#D0E7FF')
        balance_display_frame.pack(fill=tk.X)
        
        # 余额标签
        self.balance_label = tk.Label(
            balance_display_frame,
            text=f"余额: ${int(round(self.balance)):,}",
            font=('微软雅黑', 22),
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
            font=('微软雅黑', 8)
        )
        self.info_button.pack(side=tk.RIGHT, padx=5)
        
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
        tk.Label(header_frame, text="边注最高", font=("微软雅黑", 12, "bold"),
                bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="和局最高", font=("微软雅黑", 12, "bold"),
                bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(header_frame, text="主注最高", font=("微软雅黑", 12, "bold"),
                bg=table_border_color, fg='white', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        content_frame = tk.Frame(outer_frame, bg=table_bg)
        content_frame.pack(fill=tk.X)
        tk.Label(content_frame, text="30,000", font=("微软雅黑", 12, "bold"),
                bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="100,000", font=("微软雅黑", 12, "bold"),
                bg=table_bg, fg='black', width=9, pady=2).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(content_frame, text="500,000", font=("微软雅黑", 12, "bold"),
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
            font=('微软雅黑', 18),
            fg='black',
            bg='#D0E7FF'
        )
        self.current_chip_label.pack(side=tk.LEFT, padx=0)
    
    def _create_chip_button(self, parent, text, bg_color):
        size = 60
        canvas = tk.Canvas(parent, width=size, height=size,
                        highlightthickness=0, background='#D0E7FF')
        
        # 绘制圆形筹码
        chip_id = canvas.create_oval(2, 2, size-2, size-2,
                                    fill=bg_color, outline='', width=0)
        
        # 文字颜色计算
        from PIL import ImageColor
        rgb = ImageColor.getrgb(bg_color)
        luminance = 0.299*rgb[0] + 0.587*rgb[1] + 0.114*rgb[2]
        text_color = 'white' if luminance < 140 else 'black'
        
        # 添加文字
        canvas.create_text(size/2, size/2, text=text,
                        fill=text_color, font=('微软雅黑', 16, 'bold'))
        
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
        
        # 设置选中筹码的金色边框
        clicked_canvas.itemconfig(clicked_chip_id, outline='yellow', width=4)
        
        for chip in self.chip_buttons:
            if chip['canvas'] == clicked_canvas:
                self.selected_chip = chip
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
    
    def _set_default_chip(self):
        """设置默认选中的筹码（1千）"""
        for chip in self.chip_buttons:
            if chip['text'] == '1千':
                # 设置金色边框
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
        if bet_type in ('Player', 'Banker'):
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
    
    def reset_bets(self):
        # 将所有当前下注返还给余额
        for bet_type, amt in self.current_bets.items():
            self.balance += amt
        # 清除当前下注
        self.current_bets.clear()
        self.current_bet = 0
        
        # 更新所有UI元素
        self.update_balance()
        self.current_bet_label.config(text=f"${0:,}")
        
        for btn in self.bet_buttons:
            if hasattr(btn, 'bet_type'):
                original_text = btn.cget("text").split('\n')
                new_text = f"{original_text[0]}\n{original_text[1]}\n~~"
                btn.config(text=new_text)
    
    def start_game(self):
        """
        启动一局：初始化并计算每颗骰子的停止时间（随机），
        删除上局结果显示（如果存在），然后启动动画循环。
        """
        # 禁用按钮
        self.disable_all_buttons()

        # 隐藏/删除上局的结果显示（避免 itemconfig 干扰）
        try:
            if getattr(self, 'result_text_id', None) is not None:
                try:
                    self.table_canvas.delete(self.result_text_id)
                except Exception:
                    pass
                self.result_text_id = None
            if getattr(self, 'result_bg_id', None) is not None:
                try:
                    self.table_canvas.delete(self.result_bg_id)
                except Exception:
                    pass
                self.result_bg_id = None
        except Exception:
            pass

        # 重置点数显示
        self.player_score_label.config(text="~")
        self.banker_score_label.config(text="~")

        # 执行一次掷骰子，获取最终值（用于动画结束时显示）
        self.game.play_game()

        self.final_player_values = self.game.player_values.copy()
        self.final_banker_values = self.game.banker_values.copy()

        # 初始化动画控制相关标志
        self.animation_running = True
        self.animation_start_time = time.time()
        # 停止时间字典（相对动画开始的秒数）
        # 先计算 p1 和 b1 的停止时间；后续 p2/b2 在 b1 停止后决定
        t_p1 = random.uniform(3.8, 4.0)                      # 闲家第一颗停止
        t_b1 = t_p1 + random.uniform(1.2, 1.5)               # 庄家第一颗停止（在 p1 后 1.2-1.5s）

        # 先设置 p2 和 b2 为 None，等 b1 停止时决定
        self.stop_times = {
            'p1': t_p1,
            'b1': t_b1,
            'p2': None,
            'b2': None
        }

        # 停止标志，避免重复设置
        self.stopped = {
            'p1': False,
            'b1': False,
            'p2': False,
            'b2': False
        }

        # 骰子停止时的累计点数（用于实时更新）
        self.current_player_points = [None, None]  # 记录每颗骰子的点数，None表示未停止
        self.current_banker_points = [None, None]

        # 在动画开始前，将所有骰子显示为滚动初始图（第1图）
        for i in range(2):
            self.player_dice_labels[i].config(image=self.player_dice_images[0])
            self.banker_dice_labels[i].config(image=self.banker_dice_images[0])

        # 开始循环动画（使用新的实现）
        self.animate_dice_sequence()

    def animate_dice_sequence(self):
        """
        按照预先计算的 self.stop_times 来决定每颗骰子的停止时刻。
        循环每 50ms 更新尚未停止的骰子为随机面，直到所有骰子停止，
        然后进入结算/更新历史等流程。
        """
        if not getattr(self, 'animation_running', False):
            return

        current_time = time.time() - self.animation_start_time

        # ---------- 处理 p1 停止 ----------
        if (not self.stopped['p1']) and current_time >= self.stop_times['p1']:
            # 固定闲家第一颗为最终点数
            final_val = self.final_player_values[0]
            self.player_dice_labels[0].config(image=self.player_dice_images[final_val-1])
            self.current_player_points[0] = final_val
            self.stopped['p1'] = True
            # 更新点数显示
            if self.current_player_points[1] is not None:
                total = final_val + self.current_player_points[1]
                self.player_score_label.config(text=f"{total}")
            else:
                self.player_score_label.config(text=f"{final_val}")

        # ---------- 处理 b1 停止 ----------
        if (not self.stopped['b1']) and current_time >= self.stop_times['b1']:
            final_val = self.final_banker_values[0]
            self.banker_dice_labels[0].config(image=self.banker_dice_images[final_val-1])
            self.current_banker_points[0] = final_val
            self.stopped['b1'] = True
            # 更新点数显示
            if self.current_banker_points[1] is not None:
                total = final_val + self.current_banker_points[1]
                self.banker_score_label.config(text=f"{total}")
            else:
                self.banker_score_label.config(text=f"{final_val}")

            # 在庄家第一颗停止后立即决定第二颗停止的顺序与时间（按照规则）
            # 比较当前"已知"的第一颗点数（即 final p1 与 final b1）
            p1 = self.final_player_values[0]
            b1 = self.final_banker_values[0]

            if p1 < b1:
                t_b2 = current_time + random.uniform(3.1, 3.5)
                t_p2 = t_b2 + random.uniform(1.1, 1.3)
                self.stop_times['b2'] = t_b2
                self.stop_times['p2'] = t_p2
            else:
                t_p2 = current_time + random.uniform(3.1, 3.5)
                t_b2 = t_p2 + random.uniform(1.1, 1.3)
                self.stop_times['p2'] = t_p2
                self.stop_times['b2'] = t_b2

        # ---------- 处理第二颗的停止（根据上面决定的时间） ----------
        # 闲家第二颗
        if (not self.stopped['p2']) and (self.stop_times.get('p2') is not None) and current_time >= self.stop_times['p2']:
            final_val = self.final_player_values[1]
            self.player_dice_labels[1].config(image=self.player_dice_images[final_val-1])
            self.current_player_points[1] = final_val
            self.stopped['p2'] = True
            # 更新点数显示
            if self.current_player_points[0] is not None:
                total = self.current_player_points[0] + final_val
                self.player_score_label.config(text=f"{total}")
            else:
                self.player_score_label.config(text=f"{final_val}")

        # 庄家第二颗
        if (not self.stopped['b2']) and (self.stop_times.get('b2') is not None) and current_time >= self.stop_times['b2']:
            final_val = self.final_banker_values[1]
            self.banker_dice_labels[1].config(image=self.banker_dice_images[final_val-1])
            self.current_banker_points[1] = final_val
            self.stopped['b2'] = True
            # 更新点数显示
            if self.current_banker_points[0] is not None:
                total = self.current_banker_points[0] + final_val
                self.banker_score_label.config(text=f"{total}")
            else:
                self.banker_score_label.config(text=f"{final_val}")

        # 随机滚动尚未停止的骰子（视觉效果）
        # 闲家骰子随机 - 修复：只有未停止的骰子才随机滚动
        if not self.stopped['p1']:
            random_val = random.randint(1, 6)
            self.player_dice_labels[0].config(image=self.player_dice_images[random_val-1])
        if not self.stopped['p2']:
            random_val = random.randint(1, 6)
            self.player_dice_labels[1].config(image=self.player_dice_images[random_val-1])
        # 庄家骰子随机 - 修复：只有未停止的骰子才随机滚动
        if not self.stopped['b1']:
            random_val = random.randint(1, 6)
            self.banker_dice_labels[0].config(image=self.banker_dice_images[random_val-1])
        if not self.stopped['b2']:
            random_val = random.randint(1, 6)
            self.banker_dice_labels[1].config(image=self.banker_dice_images[random_val-1])

        # 检查是否所有骰子都已停止
        if all(self.stopped.values()):
            # 结束动画循环
            self.animation_running = False

            # 确保所有骰子都显示最终结果
            for i, value in enumerate(self.final_player_values):
                self.player_dice_labels[i].config(image=self.player_dice_images[value-1])
            for i, value in enumerate(self.final_banker_values):
                self.banker_dice_labels[i].config(image=self.banker_dice_images[value-1])

            # 更新点数显示
            if self.game.player_score > 0:
                self.player_score_label.config(text=f"{self.game.player_score}")
            if self.game.banker_score > 0:
                self.banker_score_label.config(text=f"{self.game.banker_score}")

            # 更新统计和标记路
            self.add_marker_result(self.game.winner)
            self._update_marker_road()
            
            # 添加到历史记录
            record = {
                'player_dice': self.final_player_values.copy(),
                'banker_dice': self.final_banker_values.copy(),
                'winner': self.game.winner
            }
            # 修改：新记录插入到列表开头（索引0位置）
            self.history.insert(0, record)
            if len(self.history) > 61:
                self.history = self.history[:61]
            
            # 更新历史记录表格
            self.update_history_table()
            
            # 保存历史记录到文件
            self._save_history_to_file()

            # 结算下注
            self.resolve_bets()

            # 显示结果（创建新的画布文本/背景）
            self._show_result_text()

            # 更新统计显示
            self._update_stats_display()

            # 启用按钮（分阶段）
            self.after(100, self.enable_buttons_except_deal)
            self.after(1800, lambda: self.deal_button.config(state=tk.NORMAL))
            self.after(2000, lambda: self.bind('<Return>', lambda e: self.start_game()))
            return

        # 若尚未全部停止，继续循环（50ms）
        self.after(50, self.animate_dice_sequence)
    
    def _update_stats_display(self):
        """更新统计显示"""
        if hasattr(self, 'stats_rows'):
            for key, row in self.stats_rows.items():
                # 修正键名映射
                if key == 'player':
                    count_key = 'Player'
                elif key == 'banker':
                    count_key = 'Banker'
                elif key == 'tie':
                    count_key = 'Tie'
                else:
                    count_key = key
                
                count = self.stats_counts.get(count_key, 0)
                row['count_label'].config(text=str(count))
    
    def resolve_bets(self):
        payouts = 0
        total_bet_amount = sum(self.current_bets.values())
        
        # 获取所有骰子值
        all_dice_values = self.game.player_values + self.game.banker_values
        
        # 检查特殊下注
        # 1. 三个一样（包括四个一样）
        from collections import Counter
        dice_counter = Counter(all_dice_values)
        has_three_of_kind = any(count >= 3 for count in dice_counter.values())
        has_four_of_kind = any(count == 4 for count in dice_counter.values())
        
        # 2. 骰子全红（所有骰子都是1或4）- 移除
        
        # 3. 单数/双数
        if self.game.winner == 'Player':
            winner_total = self.game.player_score
        elif self.game.winner == 'Banker':
            winner_total = self.game.banker_score
        else:
            winner_total = 0
        
        is_odd = winner_total % 2 == 1
        is_even = winner_total % 2 == 0
        
        # 4. 对子
        player_pair = self.game.player_values[0] == self.game.player_values[1]
        banker_pair = self.game.banker_values[0] == self.game.banker_values[1]
        
        # 5. 小大判断 - 新增
        # 根据游戏结果确定检查的点数
        if self.game.winner == 'Player':
            check_points = self.game.player_score
        elif self.game.winner == 'Banker':
            check_points = self.game.banker_score
        else:  # Tie
            check_points = self.game.tie_total
        
        # 结算各种下注
        for bet_type, bet_amount in self.current_bets.items():
            if bet_type == 'Player':
                if self.game.winner == 'Player':
                    payouts += bet_amount * 2  # 1:1赔率
                elif self.game.winner == 'Tie':
                    payouts += bet_amount * 0.9  # 退还90%本金
                    
            elif bet_type == 'Banker':
                if self.game.winner == 'Banker':
                    payouts += bet_amount * 2  # 1:1赔率
                elif self.game.winner == 'Tie':
                    payouts += bet_amount * 0.9  # 退还90%本金
            
            elif bet_type == 'Tie':
                if self.game.winner == 'Tie':
                    # 根据总点数确定赔率
                    total = sum(all_dice_values)
                    if total in [4, 24]:
                        payouts += bet_amount * 89  # 88:1赔率
                    elif total in [6, 22]:
                        payouts += bet_amount * 26  # 25:1赔率
                    elif total in [8, 20]:
                        payouts += bet_amount * 11  # 10:1赔率
                    elif total in [10, 18]:
                        payouts += bet_amount * 7   # 6:1赔率
                    else:  # 6, 7, 8
                        payouts += bet_amount * 5   # 4:1赔率
            
            elif bet_type == 'Small':  # 新增：小(2-7)
                if 2 <= check_points <= 7:
                    payouts += bet_amount * 2  # 1:1赔率
            
            elif bet_type == 'Large':  # 新增：大(8-12)
                if 8 <= check_points <= 12:
                    payouts += bet_amount * 2  # 1:1赔率
            
            elif bet_type == 'ThreeOfKind':
                if has_three_of_kind:
                    payouts += bet_amount * 10  # 9:1赔率
            
            elif bet_type == 'FourOfKind':
                if has_four_of_kind:
                    payouts += bet_amount * 206  # 205:1赔率
            
            # 移除 AllRed 的结算逻辑
            
            elif bet_type == 'Odd':
                if is_odd and self.game.winner != 'Tie':
                    payouts += bet_amount * 1.97  # 0.97:1赔率
            
            elif bet_type == 'Even':
                if is_even and self.game.winner != 'Tie':
                    payouts += bet_amount * 1.97  # 0.97:1赔率
            
            elif bet_type == 'PlayerPair':
                if player_pair:
                    payouts += bet_amount * 5.8  # 4.8:1赔率
            
            elif bet_type == 'BankerPair':
                if banker_pair:
                    payouts += bet_amount * 5.8  # 4.8:1赔率
        
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
    
    def _show_result_text(self):
        """
        局结果显示：在画布上创建新的文字与背景矩形（不依赖旧的 itemconfig）。
        """
        # 构造文本内容与颜色
        if self.game.winner == 'Player':
            text = "闲家获胜"
            text_color = "#000000"
            bg_color = '#87CEEB'
        elif self.game.winner == 'Banker':
            text = "庄家获胜"
            text_color = "#000000"
            bg_color = '#FFB6C1'
        else:
            text = "和局"
            text_color = "#000000"
            bg_color = '#32CD32'

        # 如果已有旧的元素，确保先删除（通常在 start_game 中已删除）
        try:
            if getattr(self, 'result_text_id', None):
                try:
                    self.table_canvas.delete(self.result_text_id)
                except Exception:
                    pass
                self.result_text_id = None
            if getattr(self, 'result_bg_id', None):
                try:
                    self.table_canvas.delete(self.result_bg_id)
                except Exception:
                    pass
                self.result_bg_id = None
        except Exception:
            pass

        # 创建文字（先创建，这样之后能测得 bbox）
        self.result_text_id = self.table_canvas.create_text(
            500, 370,
            text=text,
            font=('微软雅黑', 34, 'bold'),
            fill=text_color,
            tags=('result_text')
        )

        # 强制更新以获取正确bbox
        try:
            self.table_canvas.update_idletasks()
        except Exception:
            pass

        # 计算文字范围并绘制背景矩形
        text_bbox = self.table_canvas.bbox(self.result_text_id)
        if text_bbox:
            padding = 15
            expanded_bbox = (
                text_bbox[0]-padding,
                text_bbox[1]-padding,
                text_bbox[2]+padding,
                text_bbox[3]+padding
            )
        else:
            # 若无法计算 bbox，使用默认区域
            expanded_bbox = (350, 320, 650, 420)

        self.result_bg_id = self.table_canvas.create_rectangle(
            expanded_bbox[0], expanded_bbox[1], expanded_bbox[2], expanded_bbox[3],
            fill=bg_color, outline=bg_color, tags=('result_bg')
        )

        # 确保文字在最上层
        try:
            self.table_canvas.tag_raise(self.result_text_id)
            self.table_canvas.tag_lower(self.result_bg_id)
        except Exception:
            pass
    
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${int(round(self.balance)):,}")
        # 更新JSON文件中的余额
        update_balance_in_json(self.username, self.balance)
    
    def show_game_instructions(self):
        # 创建游戏说明窗口
        win = tk.Toplevel(self)
        win.title("骰子百家乐游戏说明")
        win.geometry("600x500")
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
        popup_height = 500
        
        # 计算居中位置
        x = main_x + (main_width - popup_width) // 2
        y = main_y + (main_height - popup_height) // 2
        
        # 设置弹窗位置
        win.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        
        # 创建文本框架
        text_frame = tk.Frame(win)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        instructions = """
骰子百家乐游戏规则：

1. 游戏使用4颗骰子：闲家2颗，庄家2颗
2. 比较双方总点数，点数大者获胜
3. 点数相同时为和局

下注选项及赔率：

第一行：
- 小(2-7)：1:1（获胜方总点数在2-7之间）
- 三个一样：9:1（任何三颗骰子点数相同，包括四个一样）
- 四个一样：205:1（四颗骰子点数相同）
- 大(8-12)：1:1（获胜方总点数在8-12之间）

第二行：
- 单数：0.97:1（获胜方总点数为单数）
- 闲家对子：4.8:1（闲家两颗骰子点数相同）
- 庄家对子：4.8:1（庄家两颗骰子点数相同）
- 双数：0.97:1（获胜方总点数为双数）

第三行：
- 闲家：1:1（和局退还90%本金）
- 和局：最高88倍（根据总点数确定赔率）
  * 总点数2或12：88:1
  * 总点数3或11：25:1
  * 总点数4或10：10:1
  * 总点数5或9：6:1
  * 总点数6/7/8：4:1
- 庄家：1:1（和局退还90%本金）

投注限制：
- 主注（闲家/庄家）：最高500,000
- 和局：最高100,000
- 边注（大小/对子等）：最高30,000

骰子动画：
- 按下开始按钮后，所有骰子立即随机转动
- 闲家第一颗骰子：3.8-4秒停止转动
- 庄家第一颗骰子：闲家第一颗骰子停止后1.2-1.5秒停止转动
- 根据当前点数决定第二颗骰子停止顺序：
  * 闲家领先（闲家第一颗 > 庄家第一颗）：庄家第二颗先停，闲家第二颗后停
  * 庄家领先或平局：闲家第二颗先停，庄家第二颗后停

标记路说明：
- 显示最近60局结果的标记路
- 闲家：蓝色圆点，标记为"闲"
- 庄家：粉色圆点，标记为"庄"
- 和局：绿色圆点，标记为"和"

历史记录：
- 显示最近5局的详细结果
- 闲家/庄家骰子点数从小到大排列显示
        """
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=('微软雅黑', 12), padx=10, pady=10)
        text_widget.insert(tk.END, instructions)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # 关闭按钮
        close_btn = ttk.Button(win, text="关闭", command=win.destroy)
        close_btn.pack(pady=10)
    
    # 标记路和统计相关方法
    def add_marker_result(self, winner):
        """添加新的标记路结果"""
        if winner not in self.marker_counts:
            self.marker_counts[winner] = 0
        if winner not in self.stats_counts:
            self.stats_counts[winner] = 0
        
        self.marker_counts[winner] += 1
        self.stats_counts[winner] += 1
        
        # 存储到 marker_results（最新的在前面）
        self.marker_results.insert(0, winner)
        
        # 当标记路结果超过60个时，自动删除最旧的6个记录
        if len(self.marker_results) > 60:
            # 删除最后6个记录（最旧的6个）
            self.marker_results = self.marker_results[:60]


# 主函数
def main(initial_balance=1000000, username="Guest"):
    app = BacboGUI(initial_balance, username)
    app.mainloop()
    return app.balance


if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")