import tkinter as tk
from tkinter import messagebox
import random
import json
import os

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

emoji_list = ["🏦", "💵", "💲", "🧧", "💰", "💎", "🪙"]
amounts = [10000, 100, 40, 20, 5, 2, 1]
emoji_map = {amount: emoji for amount, emoji in zip(amounts, random.sample(emoji_list, len(amounts)))}

prizes = {0: 451603, 1: 258059, 2: 129030, 5: 96772, 20: 32257, 40: 32257, 100: 15, 10000: 3.0464990000000003}

def generate_prize_pool():
    pool = []
    for prize, count in prizes.items():
        pool.extend([prize] * max(1, int(count)))  # 确保至少有1个，不会出现空
    return pool

def generate_scratch_card():
    pool = generate_prize_pool()
    win_prize = random.choices(list(prizes.keys()), weights=prizes.values(), k=1)[0]

    card = [0] * 9  # 9个格子先填充为0

    win_patterns = {
        1: [0, 1, 2], 2: [0, 3, 6], 5: [3, 4, 5],
        20: [6, 7, 8], 40: [1, 4, 7], 100: [2, 5, 8], 10000: [0, 4, 8]
    }
    same_indices = win_patterns.get(win_prize, [])

    # **填充中奖格子**
    for index in same_indices:
        card[index] = win_prize

    # **填充非中奖格子**
    remaining_indices = [i for i in range(9) if i not in same_indices]
    non_winning_values = [prize for prize in prizes.keys() if prize != win_prize and prize != 0]

    def is_valid_placement(card, index, value):
        """检查放置该数值后，是否会形成新的中奖组合"""
        temp_card = card[:]
        temp_card[index] = value
        formatted_card = [temp_card[i:i+3] for i in range(0, 9, 3)]
        return check_for_win(formatted_card) == 0  

    for index in remaining_indices:
        attempts = 0
        while attempts < 2:
            candidate = random.choice(non_winning_values)
            if is_valid_placement(card, index, candidate):
                card[index] = candidate
                break
            attempts += 1
        else:
            # **如果10次尝试失败，则填充默认的安全值**
            card[index] = random.choice(non_winning_values)

    return [card[i:i+3] for i in range(0, 9, 3)]

def exit_game():
    global exit_balance
    exit_balance = balance  # 存储退出时的余额
    root.destroy()

def check_for_win(card):
    for row in card:
        if row[0] == row[1] == row[2]:
            return row[0]
    for col in range(3):
        if card[0][col] == card[1][col] == card[2][col]:
            return card[0][col]
    if card[0][0] == card[1][1] == card[2][2] or card[0][2] == card[1][1] == card[2][0]:
        return card[1][1]
    return 0

def reveal_tile(row, col):
    if revealed[row][col]:
        return
    revealed[row][col] = True
    buttons[row][col].config(text=emoji_map[card[row][col]])
    if all(all(row) for row in revealed):
        win_amount = check_for_win(card)
        if win_amount > 0:
            messagebox.showinfo("中奖！", f"恭喜！你赢得了 {win_amount} 元!")
            global balance
            balance += win_amount
            update_balance_in_json(username, balance)
            balance_label.config(text=f"余额: {balance:.2f}")
        else:
            messagebox.showinfo("未中奖", "很遗憾，未中奖！")
        start_button.config(state="active")
        exit_button.config(state="active")

def start_game():
    global balance, card, revealed  # Declare balance as global
    if balance < 1:
        messagebox.showerror("余额不足", "你的余额不足以购买刮刮卡！")
        return
    start_button.config(state="disable")
    exit_button.config(state="disable")
    balance -= 1
    update_balance_in_json(username, balance)
    balance_label.config(text=f"余额: {balance:.2f}")
    card = generate_scratch_card()
    revealed = [[False] * 3 for _ in range(3)]
    for r in range(3):
        for c in range(3):
            buttons[r][c].config(text="❓", command=lambda r=r, c=c: reveal_tile(r, c))

def main(initial_balance, username_init):
    global balance, buttons, balance_label, coin_img, card, revealed, root, start_button, exit_button, exit_balance, username
    balance = initial_balance
    username = username_init
    root = tk.Tk()
    root.title("刮刮卡游戏")
    root.geometry("350x480+50+10")
    root.resizable(0,0)

    balance_label = tk.Label(root, text=f"余额: {balance:.2f}", font=("Arial", 14))
    balance_label.grid(row=0, column=0, columnspan=4, pady=10)

    button_frame = tk.Frame(root)
    button_frame.grid(row=1, column=0, columnspan=3)

    # 生成按钮矩阵
    buttons = [[tk.Button(button_frame, text="❓", font=("Arial", 20), width=4, height=2) for _ in range(3)] for _ in range(3)]
    for r in range(3):
        for c in range(3):
            buttons[r][c].grid(row=r, column=c, padx=5, pady=5)

    # 将固定金额的第四列变成 Label
    fixed_amounts = ["→ 1.00", "→ 5.00", "→ 20.00"]
    for r in range(3):
        tk.Label(button_frame, text=fixed_amounts[r], font=("Arial", 14)).grid(row=r, column=3, padx=5, pady=5)

    bottom_frame = tk.Frame(root)
    bottom_frame.grid(row=4, column=0, columnspan=4, pady=10)

    # Set the weight for each column
    for i in range(4):
        bottom_frame.grid_columnconfigure(i, weight=1)  # Default weight for all columns

    # For the 10000 button, set its weight to 4 to make it take up more space
    bottom_frame.grid_columnconfigure(3, weight=4)

    bottom_amounts = ["↓\n2.00", "     ↓\n     40", "     ↓\n     100", "↘\n    10000"]
    for i, amount in enumerate(bottom_amounts):
        padx_value = 0 if amount == "↘\n     10000" else 10  # Extra padding for the 10000 button
        tk.Button(
            bottom_frame, text=amount, font=("Arial", 14), borderwidth=0, highlightthickness=0, bg=root["bg"]
        ).grid(row=0, column=i, padx=padx_value)

    start_button = tk.Button(root, text="购买刮刮卡 (-1元)", font=("Arial", 14), command=start_game)
    start_button.grid(row=5, column=0, pady=10, padx=(0, 10), sticky="ew")  # Add 10px space to the right

    exit_button = tk.Button(root, text="退出游戏", command=exit_game, font=("Arial", 14))
    exit_button.grid(row=5, column=1, pady=10, padx=(10, 0), sticky="ew")  # Add 10px space to the left

    root.mainloop()
    return balance  # 在 main() 结束后返回 balance

if __name__ == "__main__":
    main(100, "demo_player")
