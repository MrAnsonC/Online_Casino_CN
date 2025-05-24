import tkinter as tk
import tkinter.messagebox as messagebox
import random
import json
import os
import sys

# 中奖金额及其概率
prize_probabilities = {
    0: 60000,   # 60.0%- 
    5: 22000,   # 22.0%
    10: 10000,  # 10.0%
    20: 5000,   # 5.0%
    25: 2000,   # 2.0%
    40: 700,    # 0.7%
    50: 200,    # 0.2%
    100: 100,   # 0.1%
    1000: 10,   # 0.01%
    2000: 5,    # 0.005%
    20000: 3,   # 0.003%
    50000: 1    # 0.001%
}

your_prize_options = [5, 10, 25, 50, 100, 1000, 2000, 20000, 50000]

hidden_values = {}
revealed_count = 0

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

def generate_prize():
    total = sum(prize_probabilities.values())
    rand = random.randint(1, total)
    cumulative = 0
    for prize, prob in prize_probabilities.items():
        cumulative += prob
        if rand <= cumulative:
            return prize
    return 0

def generate_numbers():
    lucky_numbers = random.sample(range(1, 41), 6)
    prize_amount = generate_prize()

    if prize_amount == 0:
        your_numbers = random.sample([n for n in range(1, 41) if n not in lucky_numbers], 10)
        your_prizes = random.choices(your_prize_options, k=10)
    else:
        winning_number = random.choice(lucky_numbers)
        non_winning_numbers = random.sample([n for n in range(1, 41) if n not in lucky_numbers], 9)
        your_numbers = non_winning_numbers + [winning_number]
        your_prizes = random.choices(your_prize_options, k=9) + [prize_amount]

        # 让中奖号码和对应奖金对齐
        combined = list(zip(your_numbers, your_prizes))
        random.shuffle(combined)
        your_numbers, your_prizes = zip(*combined)

    return lucky_numbers, list(your_numbers), list(your_prizes), prize_amount

def format_prize(value):
    return f"{value:,.0f}" if value >= 100 else f"{value:,.2f}"

def reveal_single_number(index):
    global revealed_count, balance

    # 确保 index 在合理范围内
    if index < 0 or index >= 10:
        return  

    # 处理上方 5 个数字
    if index < 5:
        label = your_labels[index]
    else:
        label = your_labels_bottom[index - 5]

    # 避免重复点击
    if label.cget("text") != "??\n????":
        return  

    if index in hidden_values:
        number, display_prize, actual_win = hidden_values[index]
        label.config(text=f"{number:02d}\n{format_prize(display_prize)}", bg="#80ff80" if actual_win > 0 else "#ffff80")

        revealed_count += 1

        if revealed_count == 10:
            total_win = sum(actual_win for _, _, actual_win in hidden_values.values())
            if total_win > 0:
                balance += total_win  # 中奖金额加到余额
                balance_label.config(text=f"余额: {balance} 元")  # 更新 UI
                if username != "demo_player":
                    update_balance_in_json(username, balance)  # 更新余额
                messagebox.showinfo("刮刮乐结果", f"你赢了 {total_win} 元！")
            else:
                messagebox.showinfo("刮刮乐结果", "送你一个好运气！")
            buy_button.config(state="active")
            reveal_all_button.config(state="disable")
            exit_button.config(state="active")

def reveal_numbers():
    global lucky_numbers, your_numbers, hidden_values, revealed_count
    revealed_count = 0  
    lucky_numbers, your_numbers, your_prizes, prize_amount = generate_numbers()

    hidden_values.clear()
    for i in range(10):
        actual_win = prize_amount if your_numbers[i] in lucky_numbers else 0
        hidden_values[i] = (your_numbers[i], your_prizes[i], actual_win)

    lucky_numbers_label_top.config(text=" ".join(f"{num:02d}" for num in lucky_numbers[:3]))
    lucky_numbers_label_bottom.config(text=" ".join(f"{num:02d}" for num in lucky_numbers[3:]))

    for label in your_labels + your_labels_bottom:
        label.config(text="??\n????", bg="SystemButtonFace")

def buy_ticket():
    global balance  # 声明 balance 为全局变量
    if balance >= 5:
        balance -= 5
        balance_label.config(text=f"余额: {balance} 元")
        if username != "demo_player":
            update_balance_in_json(username, balance)  # 更新余额
        reveal_numbers()
        buy_button.config(state="disabled")
        reveal_all_button.config(state="active")
        exit_button.config(state="disabled")
    else:
        result_label.config(text="余额不足！")

def reveal_all_numbers():
    global revealed_count

    reveal_all_button.config(state="disabled")

    # 检查是否有手动打开的匹配幸运号码
    manually_revealed_match = any(
        label.cget("text") != "??\n????" and hidden_values[i][0] in lucky_numbers
        for i, label in enumerate(your_labels + your_labels_bottom)
    )

    if manually_revealed_match:
        # 如果已经手动打开了匹配的幸运号码，立即翻开所有格子
        for i in range(10):
            reveal_single_number(i)
    else:
        # 否则，每秒打开一个格子
        reveal_step(0)

def reveal_step(index):
    """逐步打开未揭开的格子，每秒打开一个"""
    while index < 10:
        # 获取当前格子的 Label
        label = your_labels[index] if index < 5 else your_labels_bottom[index - 5]

        # 如果当前格子未打开，则打开它
        if label.cget("text") == "??\n????":
            reveal_single_number(index)
            root.after(1000, reveal_step, index + 1)  # 1 秒后处理下一个
            return  # 立即返回，等待下一次调用
        
        # 如果当前格子已经打开，继续检查下一个
        index += 1

def exit_game():
    global exit_balance
    exit_balance = balance  # 存储退出时的余额
    root.destroy()  # 关闭窗口

def main(balance_init, username_init):
    global root, your_labels, your_labels_bottom, balance_label, buy_button, exit_button, reveal_all_button, result_label, lucky_numbers_label_top, lucky_numbers_label_bottom, balance, username, exit_balance

    balance = balance_init
    username = username_init

    root = tk.Tk()
    root.title("100X 现金大挑战!")
    root.geometry("850x450")

    frame1 = tk.Frame(root)
    frame1.grid(row=0, column=0, padx=10, pady=10)
    title_label = tk.Label(frame1, text="100X 现金大挑战!\n最高赢 200,000！", font=("Arial", 14, "bold"))
    title_label.pack()

    frame3 = tk.Frame(root)
    frame3.grid(row=1, column=0, padx=10, pady=10)
    lucky_title = tk.Label(frame3, text="幸运号码:", font=("Arial", 14, "bold"))
    lucky_title.pack()

    lucky_numbers_label_top = tk.Label(frame3, text="? ? ?", font=("Arial", 14))
    lucky_numbers_label_top.pack()
    lucky_numbers_label_bottom = tk.Label(frame3, text="? ? ?", font=("Arial", 14))
    lucky_numbers_label_bottom.pack()

    frame4 = tk.Frame(root)
    frame4.grid(row=1, column=1, padx=10, pady=10)

    your_title = tk.Label(frame4, text="你的数字", font=("Arial", 14, "bold"))
    your_title.grid(row=0, column=0, columnspan=5)

    your_labels = []
    your_labels_bottom = []

    for i in range(5):
        label = tk.Label(frame4, text="??\n????", font=("Arial", 14, "bold"), width=9, height=5, borderwidth=2, relief="solid")
        label.grid(row=1, column=i, padx=5, pady=5)
        label.bind("<Button-1>", lambda event, index=i: reveal_single_number(index))
        your_labels.append(label)

    for i in range(5):
        label = tk.Label(frame4, text="??\n????", font=("Arial", 14, "bold"), width=9, height=5, borderwidth=2, relief="solid")
        label.grid(row=2, column=i, padx=5, pady=5)
        label.bind("<Button-1>", lambda event, index=i+5: reveal_single_number(index))
        your_labels_bottom.append(label)

    frame5 = tk.Frame(root)
    frame5.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

    balance_label = tk.Label(frame5, text=f"余额: {balance:.2f} 元", font=("Arial", 12, "bold"))
    balance_label.pack()

    button_frame = tk.Frame(frame5)
    button_frame.pack()

    buy_button = tk.Button(button_frame, text="购买刮刮卡 (-5元)", font=("Arial", 14), command=buy_ticket, )
    buy_button.grid(row=0, column=0, padx=5)

    reveal_all_button = tk.Button(button_frame, text="打开全部", font=("Arial", 14), command=reveal_all_numbers, state="disabled")
    reveal_all_button.grid(row=0, column=1, padx=5)

    exit_button = tk.Button(button_frame, text="退出游戏", font=("Arial", 14), command=exit_game)
    exit_button.grid(row=0, column=2, padx=5)

    result_label = tk.Label(root, text="", font=("Arial", 14, "bold"))
    result_label.grid(row=3, column=0, columnspan=2)

    root.mainloop()
    return exit_balance  # 在 main() 结束后返回 balance

# 运行游戏
if __name__ == "__main__":
    main(100, "demo_player")