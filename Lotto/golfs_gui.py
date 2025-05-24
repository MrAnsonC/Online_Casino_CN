import tkinter as tk
from tkinter import messagebox
import random
import json
import os

def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def update_balance_in_json(username, new_balance):
    users = load_user_data()  # 先加载现有用户数据
    for user in users:
        if user['user_name'] == username:  # 查找当前用户
            user['cash'] = f"{new_balance:.2f}"  # 更新余额
            break
    save_user_data(users)  # 保存更新后的数据

emoji_map = {10000: "🏦", 100: "💵", 40: "💲", 20: "🧧", 5: "💰", 2: "💎", 1: "🪙"}
prizes = {0: 451603, 1: 258059, 2: 129030, 5: 96772, 20: 32257, 40: 32257, 100: 11, 10000: 11, 1000000: 3.0464990000000003}

def generate_scratch_card():
    pool = []
    for prize, count in prizes.items():
        if prize in emoji_map:
            pool.extend([prize] * count)
    win_prize = random.choices(list(prizes.keys()), weights=prizes.values(), k=1)[0]
    if win_prize in emoji_map:
        card = [win_prize] * 3
    else:
        card = []
    
    remaining_pool = [p for p in pool if p != win_prize]
    while len(card) < 9:
        candidate = random.choice(remaining_pool)
        if card.count(candidate) < 2:
            card.append(candidate)
    
    random.shuffle(card)
    return [card[i:i+3] for i in range(0, 9, 3)]

def check_for_win(card):
    flat_card = sum(card, [])
    for prize in set(flat_card):
        if flat_card.count(prize) == 3:
            return prize
    return None

class ScratchGame:
    def __init__(self, root, balance, username):
        self.root = root
        self.root.title("刮刮乐游戏")
        self.username = username
        self.balance = int(balance)
        self.card = None
        self.revealed = set()

        # 余额显示
        self.balance_label = tk.Label(root, text=f"余额: {self.balance}", font=("Arial", 14))
        self.balance_label.pack()

        # 创建主要框架
        self.main_frame = tk.Frame(root)
        self.main_frame.pack()

        # 左侧 - 九宫格
        self.grid_frame = tk.Frame(self.main_frame)
        self.grid_frame.pack(side=tk.LEFT)

        self.buttons = [[tk.Button(self.grid_frame, text="❓", font=("Arial", 20), width=5, height=2, state=tk.DISABLED,
                                   command=lambda r=r, c=c: self.reveal(r, c)) for c in range(3)] for r in range(3)]
        for r in range(3):
            for c in range(3):
                self.buttons[r][c].grid(row=r, column=c)

        # 右侧 - 中奖规则信息
        self.right_frame = tk.Frame(self.main_frame)
        self.right_frame.pack(side=tk.LEFT, padx=10)

        self.prize_info = tk.Label(self.right_frame, text="中奖规则:\n🏦🏦🏦 = 10000\n💵💵💵 = 100\n💲💲💲 = 40\n🧧🧧🧧 = 20\n💰💰💰 = 5\n💎💎💎 = 2\n🪙🪙🪙 = 1", font=("Arial", 12), justify=tk.LEFT)
        self.prize_info.pack()

        # 按钮框架
        self.button_frame = tk.Frame(root)
        self.button_frame.pack()

        self.buy_button = tk.Button(self.button_frame, text="购买刮刮卡 (-1元)", command=self.buy_ticket, font=("Arial", 14))
        self.buy_button.pack(side=tk.LEFT, padx=5)

        self.open_all_button = tk.Button(self.button_frame, text="打开全部", command=self.open_all, font=("Arial", 14), state= "disabled")
        self.open_all_button.pack(side=tk.LEFT, padx=5)

        self.exit_button = tk.Button(self.button_frame, text="退出游戏", command=self.exit_game, font=("Arial", 14))
        self.exit_button.pack(side=tk.LEFT, padx=5)

    def open_all(self):
        self.open_all_button.config(state=tk.DISABLED)
        # 如果有 3 个相同图案已经完全揭示，则立即显示所有格子
        if self.check_three_revealed():
            for r in range(3):
                for c in range(3):
                    if (r, c) not in self.revealed:
                        self.reveal(r, c)
        else:
            # 如果没有完全揭示，逐个揭示格子
            self.auto_reveal_next(0, 0)

    def check_three_revealed(self):
        # 检查是否有 3 个相同图案已经完全被揭示
        for prize in set(sum(self.card, [])):
            positions = [(r, c) for r in range(3) for c in range(3) if self.card[r][c] == prize]
            if len(positions) == 3:
                revealed_positions = [pos for pos in positions if pos in self.revealed]
                if len(revealed_positions) == 3:
                    return True
        return False

    def auto_reveal_next(self, row, col):
        if row == 3:
            return
        if col == 3:
            self.auto_reveal_next(row + 1, 0)
            return

        if (row, col) in self.revealed:  # 如果当前格子已经被揭示，跳过
            self.auto_reveal_next(row, col + 1)
            return

        self.reveal(row, col)

        # 如果所有格子都已揭示，则停止
        if len(self.revealed) == 9:
            return

        # 每 0.75 秒揭示下一个格子
        self.root.after(750, self.auto_reveal_next, row, col + 1)

    def reveal(self, row, col):
        if (row, col) in self.revealed:
            return
        self.revealed.add((row, col))

        prize = self.card[row][col]

        if prize in emoji_map:
            self.buttons[row][col].config(text=emoji_map[prize], bg="#e6ffff")
        
        # 检查每个图案是否已完全揭示（即3个相同图案是否全部揭示）
        for prize in set(sum(self.card, [])):  # 遍历所有奖品
            # 获取当前图案在卡片上的位置
            positions = [(r, c) for r in range(3) for c in range(3) if self.card[r][c] == prize]
            if len(positions) == 3:  # 确保此图案在卡片上出现 3 次
                revealed_positions = [pos for pos in positions if pos in self.revealed]
                if len(revealed_positions) == 3:  # 确保3个相同图案都已揭示
                    # 如果3个相同图案都已揭示，更新它们的背景色
                    for r, c in positions:
                        self.buttons[r][c].config(bg="#33ffad")
        
        # 判断是否揭示完所有格子
        if len(self.revealed) == 9:
            self.check_results()

    def buy_ticket(self):
        if self.balance < 1:
            messagebox.showerror("错误", "余额不足！")
            return
        self.balance -= 1
        self.update_balance()
        self.card = generate_scratch_card()
        self.revealed.clear()
        
        for r in range(3):
            for c in range(3):
                self.buttons[r][c].config(text="❓", state=tk.NORMAL, bg="SystemButtonFace")
        
        self.buy_button.config(state=tk.DISABLED)
        self.open_all_button.config(state=tk.NORMAL)
        self.exit_button.config(state=tk.DISABLED)

    def check_results(self):
        win_amount = check_for_win(self.card)
        if win_amount:
            messagebox.showinfo("中奖！", f"恭喜！你赢得了 {win_amount} 元!")
            self.balance += win_amount
        else:
            messagebox.showinfo("未中奖", "很遗憾，你没有中奖！")
        self.update_balance()
        
        for r in range(3):
            for c in range(3):
                self.buttons[r][c].config(state=tk.DISABLED)
        
        self.buy_button.config(state=tk.NORMAL)
        self.open_all_button.config(state=tk.DISABLED)
        self.exit_button.config(state=tk.NORMAL)

    def update_balance(self):
        self.balance_label.config(text=f"余额: {self.balance}")
        if self.username != "demo_player":
            update_balance_in_json(self.username, self.balance)

    def exit_game(self):
        self.root.destroy()
        return self.balance

if __name__ == "__main__":
    root = tk.Tk()
    game = ScratchGame(root, 100, "demo_player")
    root.mainloop()
