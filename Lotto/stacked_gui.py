import tkinter as tk
from tkinter import messagebox
import random
import os
import json

def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

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

def draw_amount():
    prize_probabilities = {
        0: 60000, 5: 22000, 10: 10000, 20: 5000, 25: 2000,
        40: 700, 50: 200, 100: 100, 1000: 10, 2000: 5,
        20000: 3, 50000: 1
    }
    total_weight = sum(prize_probabilities.values())
    rand_num = random.uniform(0, total_weight)
    cumulative_weight = 0
    for amount, weight in prize_probabilities.items():
        cumulative_weight += weight
        if rand_num <= cumulative_weight:
            return amount

def generate_emoji_grid(amount):
    emojis = ["🏦", "💲", "🧧", "💰", "💵", "🪙"]
    grid = []
    winning_row = random.randint(1, 10) if amount > 0 else None
    for i in range(1, 11):
        row = random.choices(emojis, k=5)
        if amount > 0 and i == winning_row:
            chosen_emoji = random.choice(emojis)
            row[:3] = [chosen_emoji] * 3
        grid.append([f"游戏{i}"] + row + ["奖金"])
    return grid, winning_row

def scratch_card(row, col):
    if (row, col) in revealed_cells:
        return
    revealed_cells.add((row, col))
    if col == 6:  # 07格子，显示奖金
        buttons[row][col].config(text=str(row_prizes[row]))
    else:  # Emoji格子
        buttons[row][col].config(text=emoji_grid[row-1][col])

def start_game():
    global balance, emoji_grid, revealed_cells, winning_row, winning_amount, row_prizes
    if balance < 5:
        messagebox.showerror("错误", "余额不足！")
        return
    balance -= 5
    balance_label.config(text=f"余额: {balance:.2f} 元")
    update_balance_in_json(username, balance)
    winning_amount = draw_amount()
    emoji_grid, winning_row = generate_emoji_grid(winning_amount)
    row_prizes = {i: random.choice(list(prize_random.keys())) if i != winning_row else winning_amount for i in range(1, 11)}
    revealed_cells.clear()
    update_display()

def update_display():
    for i in range(1, 11):
        for j in range(7):
            text = "🕳️" if j in range(1, 6) else "奖金"
            buttons[i][j].config(text=text)

root = tk.Tk()
root.title("刮刮乐游戏")

username = "demo_player"
balance = 100
prize_random = {5: 100, 10: 100, 20: 100, 25: 75, 40: 75, 50: 75, 100: 75, 1000: 75, 2000: 75, 20000: 50, 50000: 50}
emoji_grid, winning_row = generate_emoji_grid(0)
revealed_cells = set()
row_prizes = {}

balance_label = tk.Label(root, text=f"余额: {balance:.2f} 元", font=("Arial", 16))
balance_label.pack()

game_frame = tk.Frame(root)
game_frame.pack()

buttons = {}
for i in range(1, 11):
    buttons[i] = {}
    for j in range(7):
        btn_text = "游戏" + str(i) if j == 0 else "🕳️" if j in range(1, 6) else "奖金"
        btn = tk.Button(game_frame, text=btn_text, font=("Arial", 14), width=10, height=2,
                         command=lambda r=i, c=j: scratch_card(r, c) if j in range(1, 7) else None)
        btn.grid(row=i, column=j)
        buttons[i][j] = btn

start_button = tk.Button(root, text="购买刮刮卡 (5元)", font=("Arial", 16), command=start_game)
start_button.pack()

root.mainloop()
