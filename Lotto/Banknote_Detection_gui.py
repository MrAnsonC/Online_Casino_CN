import tkinter as tk
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

def main(balance, username):
    global exit_balance

    exit_balance = balance

    total_value = None
    real_or_fake = None
    
    def draw_ticket():
        nonlocal balance, total_value, real_or_fake
        if balance < 1:
            balance_label["text"] = "餘額不足"
            return
        balance -= 1
        balance_label["text"] = f"余额: {balance:.2f} 元"
        real_or_fake = random.choices(["真", "假"], weights=[40, 60])[0]

        if username != "demo_player":
            update_balance_in_json(username, balance)  # 更新余额
        left_button.config(state="active", bg="SystemButtonFace")
        right_button.config(state="disabled", bg="SystemButtonFace", disabledforeground="SystemGrayText")
        draw_button.config(state="disabled")
        exit_button.config(state="disabled")
        
        if real_or_fake == "真":
            values = [0.5, 1, 2, 5, 10, 20, 50, 100, 500, 1000]
            probabilities = [29.4, 24.5, 17.2, 12.3, 7.4, 3.7, 1.7, 0.7, 0.5, 0.2]
        else:
            values = [0.5, 1, 2, 5, 10, 20, 50, 100, 500, 1000]
            probabilities = [10, 15, 15, 10, 10, 10, 10, 10, 5, 5]
        
        total_value = random.choices(values, weights=probabilities)[0]
        left_button["text"] = "钞票总值"
        right_button["text"] = "验钞结果"
    
    def reveal_value():
        nonlocal total_value
        if total_value is not None:
            left_button["text"] = f"{total_value:.2f}元"
            check_and_add_balance()
            right_button.config(state="active", bg="SystemButtonFace")

            color_map = {
                10: "#c299ff", 20: "#4d79ff", 50: "#5cd65c", 100: "#ff704d",
                500: "#b35900", 1000: "#cccc00"
            }
            left_button.config(bg=color_map.get(total_value, "#b3b3b3"))
    
    def reveal_authenticity():
        nonlocal real_or_fake
        if real_or_fake is not None:
            right_button["text"] = real_or_fake
            check_and_add_balance()
        left_button.config(state="disabled", disabledforeground="#000000")
        right_button.config(state="disabled", disabledforeground="#000000")
        exit_button.config(state="active")
        draw_button.config(state="active")

        right_button.config(bg="#66ff66" if real_or_fake == "真" else "#ff5c33")
    
    def check_and_add_balance():
        nonlocal balance, total_value, real_or_fake
        if total_value is not None and real_or_fake == "真" and left_button["text"].endswith("元") and right_button["text"] in ["真", "假"]:
            balance += total_value
            balance_label["text"] = f"余额: {balance:.2f} 元"
            if username != "demo_player":
                update_balance_in_json(username, balance)  # 更新余额
    
    def exit_game():
        global exit_balance
        exit_balance = balance  # 存储退出时的余额
        root.destroy()  # 关闭窗口

    root = tk.Tk()
    root.title("验钞刮刮乐")
    root.geometry("650x400")

    title_label = tk.Label(root, text=f"验钞刮刮乐", font=("Arial", 24, "bold"))
    title_label.pack(pady=10)

    balance_label = tk.Label(root, text=f"余额: {balance:.2f} 元", font=("Arial", 24))
    balance_label.pack()

    frame = tk.Frame(root)
    frame.pack(pady=10)

    left_label = tk.Button(frame, text="这次的钞票总值是", font=("Arial", 24), relief="flat")
    left_label.grid(row=0, column=0, padx=10)
    right_label = tk.Button(frame, text="本次验钞结果是", font=("Arial", 24), relief="flat")
    right_label.grid(row=0, column=1, padx=10)

    left_button = tk.Button(frame, text="钞票总值", width=15, height=3, font=("Arial", 24), command=reveal_value)
    left_button.grid(row=1, column=0, padx=10)
    left_button.config(state="disabled", bg="SystemButtonFace")

    right_button = tk.Button(frame, text="验钞结果", width=15, height=3, font=("Arial", 24), command=reveal_authenticity)
    right_button.grid(row=1, column=1, padx=10)
    right_button.config(state="disabled", bg="SystemButtonFace")

    draw_button = tk.Button(root, text="抽取钞票(-1元)", font=("Arial", 24), command=draw_ticket)
    draw_button.pack(side=tk.LEFT, padx=20, pady=10)

    exit_button = tk.Button(root, text="退出游戏", font=("Arial", 24), command=exit_game)
    exit_button.pack(side=tk.RIGHT, padx=20, pady=10)

    root.mainloop()
    return exit_balance  # 在 main() 结束后返回 balance

if __name__ == "__main__":
    main(100, "demo_player")