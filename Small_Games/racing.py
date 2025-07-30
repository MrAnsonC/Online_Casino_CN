import tkinter as tk
from tkinter import ttk, messagebox
import random
import json
import os
import time

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
        self.create_text(radius, radius, text=text, fill=fg_color, 
                        font=("Arial", 18, "bold"))
        
        self.bind("<Button-1>", self.on_click)
    
    def on_click(self, event):
        if self.command:
            self.command()

class HorseRacingGame:
    def __init__(self, root, initial_balance, username):
        self.root = root
        self.root.title("赛马骰子游戏")
        self.root.geometry("1000x700+50+10")
        self.root.resizable(0,0)
        self.root.configure(bg="#1a1a2e")
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.balance = float(initial_balance)
        self.username = username
        self.bet_amount = 0
        self.last_win = 0
        self.chip_buttons = []
        self.winner = None
        self.odds = {'win': 5.5, 'place': 1.9}
        self.current_chip = 5
        self.finished_horses = []
        self.accident_count = 0
        
        self.horse_names = ["闪电", "追风", "赤兔", "黑豹", "飞燕", "流星"]
        self.horse_colors = ["#FF5733", "#33FF57", "#3357FF", "#F333FF", "#FF33F3", "#F3FF33"]
        
        # 骰子结果概率分布
        self.dice_probabilities = {
            "一点": 0.25,
            "二点": 0.20,
            "三点": 0.20,
            "空白": 0.25,
            "2X": 0.05,
            "拉停": 0.04,
            "堕马": 0.01
        }
        
        self.horse_bets = [{"win": 0.0, "place": 0.0} for _ in range(6)]
        self.horse_states = [{
            "position": 0,
            "double_count": 0,
            "locked": False,
            "retired": False,
            "dice_result": ""
        } for _ in range(6)]
        
        self.create_widgets()
        self.update_display()
    
    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        left_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        tk.Label(left_frame, text="赛马骰子游戏", font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#e94560").pack(pady=10)
        
        self.track_canvas = tk.Canvas(left_frame, bg="#0f3460", bd=0, highlightthickness=0)
        self.track_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.draw_track()
        
        right_frame = tk.Frame(main_frame, bg="#16213e", bd=2, relief=tk.RIDGE)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        balance_frame = tk.Frame(right_frame, bg="#16213e")
        balance_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(balance_frame, text="余额:", font=("Arial", 14), 
                bg="#16213e", fg="#f1f1f1").pack(side=tk.LEFT)
        
        self.balance_var = tk.StringVar()
        self.balance_var.set(f"${self.balance:.2f}")
        tk.Label(balance_frame, textvariable=self.balance_var, font=("Arial", 14, "bold"), 
                bg="#16213e", fg="#ffd369").pack(side=tk.LEFT, padx=(5, 0))
        
        chips_frame = tk.Frame(right_frame, bg="#16213e")
        chips_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        chips = [
            ("$5", '#ff0000', 'white'),
            ("$25", '#00ff00', 'black'),
            ("$100", '#000000', 'white'),
            ("$500", "#FF7DDA", 'black'),
            ("$1K", '#ffffff', 'black')
        ]
        
        self.chip_buttons = []
        for text, bg_color, fg_color in chips:
            chip_value = int(text[1:]) if text[1:] != "1K" else 1000
            
            btn = CircleButton(
                chips_frame, text=text, bg_color=bg_color, fg_color=fg_color,
                command=lambda val=chip_value: self.select_chip(val)
            )
            btn.pack(side=tk.LEFT, padx=5, pady=5)
            self.chip_buttons.append(btn)
        
        self.current_chip_var = tk.StringVar()
        self.current_chip_var.set(f"当前筹码: ${self.current_chip}")
        tk.Label(chips_frame, textvariable=self.current_chip_var, font=("Arial", 12), 
                bg="#16213e", fg="#ffd369").pack(side=tk.LEFT, padx=(20, 0))
        
        bet_title_frame = tk.Frame(right_frame, bg="#16213e")
        bet_title_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        tk.Label(bet_title_frame, text="赛马", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1", width=8).pack(side=tk.LEFT)
        tk.Label(bet_title_frame, text="独赢", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1", width=8).pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(bet_title_frame, text="位置", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1", width=8).pack(side=tk.LEFT, padx=(10, 0))
        
        self.horse_frames = []
        for i in range(6):
            horse_frame = tk.Frame(right_frame, bg="#16213e")
            horse_frame.pack(fill=tk.X, padx=10, pady=5)
            
            horse_info_frame = tk.Frame(horse_frame, bg="#16213e")
            horse_info_frame.pack(side=tk.LEFT, fill=tk.Y)
            
            color_label = tk.Label(horse_info_frame, text="■", font=("Arial", 16), 
                                 fg=self.horse_colors[i], bg="#16213e")
            color_label.pack(side=tk.LEFT, padx=(0, 5))
            
            name_label = tk.Label(horse_info_frame, text=self.horse_names[i], font=("Arial", 12), 
                                bg="#16213e", fg="#f1f1f1")
            name_label.pack(side=tk.LEFT)
            
            win_frame = tk.Frame(horse_frame, bg="#16213e")
            win_frame.pack(side=tk.LEFT, padx=(20, 0))
            
            win_btn = tk.Button(win_frame, text="独赢", font=("Arial", 10), 
                              bg="#4e9de0", fg="white", width=6,
                              command=lambda idx=i: self.place_bet(idx, "win"))
            win_btn.pack()
            
            win_bet_var = tk.StringVar()
            win_bet_var.set("$0.00")
            win_bet_label = tk.Label(win_frame, textvariable=win_bet_var, font=("Arial", 10), 
                                   bg="#16213e", fg="#ffd369")
            win_bet_label.pack(pady=(5, 0))
            
            place_frame = tk.Frame(horse_frame, bg="#16213e")
            place_frame.pack(side=tk.LEFT, padx=(10, 0))
            
            place_btn = tk.Button(place_frame, text="位置", font=("Arial", 10), 
                                bg="#e74c3c", fg="white", width=6,
                                command=lambda idx=i: self.place_bet(idx, "place"))
            place_btn.pack()
            
            place_bet_var = tk.StringVar()
            place_bet_var.set("$0.00")
            place_bet_label = tk.Label(place_frame, textvariable=place_bet_var, font=("Arial", 10), 
                                     bg="#16213e", fg="#ffd369")
            place_bet_label.pack(pady=(5, 0))
            
            self.horse_frames.append({
                "win_bet_var": win_bet_var,
                "place_bet_var": place_bet_var,
                "win_bet_label": win_bet_label,
                "place_bet_label": place_bet_label
            })
        
        button_frame = tk.Frame(right_frame, bg="#16213e")
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        
        self.start_button = tk.Button(
            button_frame, text="开始比赛", font=("Arial", 12, "bold"),
            bg="#27ae60", fg="white", width=12, command=self.start_race
        )
        self.start_button.pack(pady=5)
        
        self.reset_bet_button = tk.Button(
            button_frame, text="重设下注", font=("Arial", 12),
            bg="#3498db", fg="white", width=12, command=self.reset_bet
        )
        self.reset_bet_button.pack(pady=5)
                
        info_frame = tk.Frame(right_frame, bg="#16213e")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(info_frame, text="游戏规则:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W, pady=(0, 5))
        
        rules = [
            "1. 选择筹码金额后点击投注类型",
            "2. 独赢: 该马获得第一名(赔率5.5倍)",
            "3. 位置: 该马进入前三名(赔率1.9倍)",
            "4. 点击开始比赛按钮",
            "5. 每匹马每回合投掷特色骰子前进",
            "6. 骰子结果:",
            "   - 一点/二点/三点: 前进1/2/3步",
            "   - 空白: 该回合不移动",
            "   - 2X: 该马的赔率翻倍(可叠加)",
            "   - 拉停: 下一回合无法移动",
            "   - 堕马: 立即退出比赛",
            "7. 所有马到达终点后结算奖金"
        ]
        
        for rule in rules:
            tk.Label(info_frame, text=rule, font=("Arial", 10), 
                    bg="#16213e", fg="#bdc3c7", justify=tk.LEFT).pack(anchor=tk.W, pady=2)
            
        bet_win_frame = tk.Frame(right_frame, bg="#16213e")
        bet_win_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        bet_frame = tk.Frame(bet_win_frame, bg="#16213e")
        bet_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        tk.Label(bet_frame, text="下注金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.bet_var = tk.StringVar()
        self.bet_var.set("$0.00")
        tk.Label(bet_frame, textvariable=self.bet_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        win_frame = tk.Frame(bet_win_frame, bg="#16213e")
        win_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        tk.Label(win_frame, text="上局获胜金额:", font=("Arial", 12), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.last_win_var = tk.StringVar()
        self.last_win_var.set("$0.00")
        tk.Label(win_frame, textvariable=self.last_win_var, font=("Arial", 20, "bold"), 
                bg="#16213e", fg="#4cc9f0").pack(anchor=tk.W, pady=(5, 0))
        
        # 骰子结果显示区域
        dice_frame = tk.Frame(right_frame, bg="#16213e")
        dice_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(dice_frame, text="骰子结果:", font=("Arial", 12, "bold"), 
                bg="#16213e", fg="#f1f1f1").pack(anchor=tk.W)
        
        self.dice_vars = [tk.StringVar() for _ in range(6)]
        for i in range(6):
            dice_row = tk.Frame(dice_frame, bg="#16213e")
            dice_row.pack(fill=tk.X, pady=2)
            
            color_label = tk.Label(dice_row, text="■", font=("Arial", 12), 
                                 fg=self.horse_colors[i], bg="#16213e")
            color_label.pack(side=tk.LEFT, padx=(0, 5))
            
            name_label = tk.Label(dice_row, text=self.horse_names[i], font=("Arial", 10), 
                                bg="#16213e", fg="#f1f1f1", width=6)
            name_label.pack(side=tk.LEFT)
            
            result_label = tk.Label(dice_row, textvariable=self.dice_vars[i], font=("Arial", 10), 
                                  bg="#16213e", fg="#ffd369", width=12)
            result_label.pack(side=tk.LEFT, padx=(5, 0))
            
            self.dice_vars[i].set("准备中...")
    
    def draw_track(self):
        self.track_canvas.delete("all")
        
        track_height = 400
        track_width = 600
        start_x = 50
        start_y = 450
        spacing = track_height // 7
        
        # 绘制终点线
        self.track_canvas.create_line(
            start_x, start_y - track_height + 20,
            start_x + track_width, start_y - track_height + 20,
            fill="red", width=3, dash=(5, 2)
        )
        self.track_canvas.create_text(
            start_x + track_width // 2, start_y - track_height - 10,
            text="终点线", font=("Arial", 12, "bold"), fill="red"
        )
        
        # 绘制赛道和马
        self.horse_positions = [0] * 6
        self.horse_ids = []
        self.horse_rank_labels = []
        self.horse_disabled = [False] * 6
        self.rankings = []
        
        for i in range(6):
            y_pos = start_y - spacing * (i + 1)
            
            self.track_canvas.create_line(
                start_x, y_pos,
                start_x + track_width, y_pos,
                fill="#555555", width=2
            )
            
            horse_id = self.track_canvas.create_text(
                start_x, y_pos,
                text="🐎", font=("Arial", 24),
                fill=self.horse_colors[i],
                anchor=tk.W
            )
            self.horse_ids.append(horse_id)
            
            self.track_canvas.create_text(
                start_x - 40, y_pos,
                text=self.horse_names[i], font=("Arial", 10),
                fill=self.horse_colors[i],
                anchor=tk.E
            )
            
            rank_label = self.track_canvas.create_text(
                start_x + track_width + 20, y_pos,
                text="", font=("Arial", 12, "bold"),
                fill="gold"
            )
            self.horse_rank_labels.append(rank_label)
    
    def select_chip(self, amount):
        self.current_chip = amount
        self.current_chip_var.set(f"当前筹码: ${amount}")
    
    def place_bet(self, horse_index, bet_type):
        if self.current_chip <= self.balance:
            self.horse_bets[horse_index][bet_type] += self.current_chip
            
            if bet_type == "win":
                self.horse_frames[horse_index]["win_bet_var"].set(
                    f"${self.horse_bets[horse_index]['win']:.2f}"
                )
            else:
                self.horse_frames[horse_index]["place_bet_var"].set(
                    f"${self.horse_bets[horse_index]['place']:.2f}"
                )
            
            self.bet_amount += self.current_chip
            self.bet_var.set(f"${self.bet_amount:.2f}")
            
            self.balance -= self.current_chip
            self.balance_var.set(f"${self.balance:.2f}")
        else:
            messagebox.showwarning("余额不足", "您的余额不足以进行此下注")
    
    def reset_bet(self):
        self.horse_bets = [{"win": 0.0, "place": 0.0} for _ in range(6)]
        self.bet_amount = 0.0
        
        for frame in self.horse_frames:
            frame["win_bet_var"].set("$0.00")
            frame["place_bet_var"].set("$0.00")
        
        self.balance += self.bet_amount
        self.balance_var.set(f"${self.balance:.2f}")
        self.bet_var.set("$0.00")
    
    def update_display(self):
        self.balance_var.set(f"${self.balance:.2f}")
        self.last_win_var.set(f"${self.last_win:.2f}")
    
    def roll_dice(self):
        """根据概率分布掷骰子"""
        rand = random.random()
        cumulative = 0
        for result, prob in self.dice_probabilities.items():
            cumulative += prob
            if rand < cumulative:
                return result
        return "空白"  # 默认返回
    
    def start_race(self):
        if self.bet_amount <= 0:
            messagebox.showwarning("错误", "请先下注")
            return
        
        self.race_active = True
        self.winner = None
        self.finished_horses = []
        self.rankings = []
        self.accident_count = 0
        
        # 重置马的状态
        self.horse_positions = [0] * 6
        self.horse_disabled = [False] * 6
        self.horse_states = [{
            "position": 0,
            "double_count": 0,
            "locked": False,
            "retired": False,
            "dice_result": ""
        } for _ in range(6)]
        
        self.start_button.config(state=tk.DISABLED)
        self.reset_bet_button.config(state=tk.DISABLED)
        for btn in self.chip_buttons:
            btn.configure(state=tk.DISABLED)
        
        self.draw_track()
        self.run_race()
    
    def run_race(self):
        if not self.race_active:
            return
        
        # 更新骰子结果显示
        for i in range(6):
            if self.horse_disabled[i] or i in self.finished_horses:
                self.dice_vars[i].set("已退赛" if self.horse_disabled[i] else "已完成")
                continue
            
            # 如果马被锁定（拉停效果），跳过掷骰子
            if self.horse_states[i]["locked"]:
                self.horse_states[i]["locked"] = False
                self.dice_vars[i].set("拉停(跳过)")
                continue
            
            # 掷骰子
            result = self.roll_dice()
            self.horse_states[i]["dice_result"] = result
            self.dice_vars[i].set(result)
            
            # 处理骰子结果
            if result == "一点":
                self.horse_positions[i] += 1
            elif result == "二点":
                self.horse_positions[i] += 2
            elif result == "三点":
                self.horse_positions[i] += 3
            elif result == "2X":
                self.horse_states[i]["double_count"] += 1
            elif result == "拉停":
                self.horse_states[i]["locked"] = True
            elif result == "堕马":
                self.horse_disabled[i] = True
                self.accident_count += 1
                # 显示意外信息
                accidents = ["断腿", "失蹄", "堕马", "拉停", "失控"]
                self.track_canvas.create_text(
                    300, self.track_canvas.coords(self.horse_ids[i])[1],
                    text=f"{self.horse_names[i]}{random.choice(accidents)}!",
                    font=("Arial", 12, "bold"), fill="red"
                )
        
        # 更新马的位置
        for i in range(6):
            if self.horse_disabled[i] or i in self.finished_horses:
                continue
            
            # 更新马在画布上的位置
            track_height = 400
            step_size = track_height / 20  # 20步到达终点
            new_y = 450 - self.horse_positions[i] * step_size
            self.track_canvas.coords(self.horse_ids[i], 50, new_y)
            self.track_canvas.coords(self.horse_rank_labels[i], 650, new_y)
            
            # 检查是否到达终点
            if self.horse_positions[i] >= 20:
                if i not in self.finished_horses:
                    self.finished_horses.append(i)
                    self.rankings.append(i)
                    rank = len(self.rankings)
                    self.track_canvas.itemconfig(
                        self.horse_rank_labels[i], 
                        text=f"第{rank}名"
                    )
        
        # 检查比赛是否结束
        finished_count = len(self.finished_horses) + sum(self.horse_disabled)
        if finished_count == 6:
            self.race_active = False
            self.finish_race()
        else:
            self.root.after(500, self.run_race)  # 每500毫秒一个回合
    
    def finish_race(self):
        win_amount = 0
        
        # 获取前三名
        first_three = self.rankings[:3] if len(self.rankings) >= 3 else self.rankings
        
        # 结算独赢投注
        if self.rankings:
            winner = self.rankings[0]
            # 应用2X效果
            multiplier = 2 ** self.horse_states[winner]["double_count"]
            win_amount += self.horse_bets[winner]['win'] * self.odds['win'] * multiplier
        
        # 结算位置投注
        for horse in first_three:
            # 应用2X效果
            multiplier = 2 ** self.horse_states[horse]["double_count"]
            win_amount += self.horse_bets[horse]['place'] * self.odds['place'] * multiplier
        
        self.last_win = win_amount
        self.balance += win_amount
        
        self.update_display()
        update_balance_in_json(self.username, self.balance)
        
        result_message = "比赛结果:\n"
        for i, horse_idx in enumerate(self.rankings):
            double_text = f" (2X×{self.horse_states[horse_idx]['double_count']})" if self.horse_states[horse_idx]['double_count'] > 0 else ""
            result_message += f"第{i+1}名: {self.horse_names[horse_idx]}{double_text}\n"
        
        result_message += "\n"
        
        # 显示意外事件
        for i in range(6):
            if self.horse_disabled[i]:
                result_message += f"{self.horse_names[i]} 发生意外，失去资格\n"
        
        result_message += f"\n您赢得: ${win_amount:.2f}\n总余额: ${self.balance:.2f}"
        
        messagebox.showinfo("比赛结束", result_message)
        
        # 启用按钮
        self.start_button.config(state=tk.NORMAL)
        self.reset_bet_button.config(state=tk.NORMAL)
        for btn in self.chip_buttons:
            btn.configure(state=tk.NORMAL)
    
    def on_closing(self):
        update_balance_in_json(self.username, self.balance)
        self.root.destroy()

def main(initial_balance, username):
    root = tk.Tk()
    game = HorseRacingGame(root, initial_balance, username)
    root.mainloop()
    return game.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = HorseRacingGame(root, 1000.0, "test_user")
    root.mainloop()