import random
import os
import json
import time

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

# 所有可用的emoji列表
emoji_list = ["🏦", "💵", "💲", "🧧", "💰", "💎", "🪙"]

# 数字和emoji之间的映射
amounts = [10000, 100, 40, 20, 5, 2, 1]

# 随机分配emoji给每个数字
emoji_map = {amount: emoji for amount, emoji in zip(amounts, random.sample(emoji_list, len(amounts)))}

prizes = {
    0: 600,
    1: 325,
    2: 175,
    5: 120,
    20: 40,
    40: 25,
    100: 10,
    10000: 5
}
total_tickets = sum(prizes.values())

def generate_prize_pool():
    pool = []
    for prize, count in prizes.items():
        pool.extend([prize] * count)
    return pool

def generate_scratch_card():
    pool = generate_prize_pool()
    win_prize = random.choices(list(prizes.keys()), weights=prizes.values(), k=1)[0]

    card = [None] * 9  # 创建9个空格子
    
    # 根据win_prize的不同设置需要相同图案的格子索引
    if win_prize == 1:
        same_indices = [0, 1, 2]  # 123
    elif win_prize == 2:
        same_indices = [0, 3, 6]  # 147
    elif win_prize == 5:
        same_indices = [3, 4, 5]  # 456
    elif win_prize == 20:
        same_indices = [6, 7, 8]  # 789
    elif win_prize == 40:
        same_indices = [1, 4, 7]  # 258
    elif win_prize == 100:
        same_indices = [2, 5, 8]  # 369
    elif win_prize == 10000:
        same_indices = [0, 4, 8]  # 159
    else:
        same_indices = []  # 0代表没有相同的图案

    # 为相同格子设置相同的图案
    for index in same_indices:
        card[index] = win_prize

    # 选择剩余格子，不能使用相同的图案，且每个图案最多重复两次
    remaining_pool = [prize for prize in pool if prize != win_prize and prize != 0]

    for i in range(9):
        if card[i] is None:
            candidate = random.choice(remaining_pool)
            # 确保每个图案最多重复两次
            while card.count(candidate) >= 2:
                candidate = random.choice(remaining_pool)
            card[i] = candidate

    return [card[i:i+3] for i in range(0, 9, 3)]


def print_scratch_card(card, revealed=None):
    if revealed is None:
        revealed = []

    print("=======================")
    
    for row in range(3):
        row_content = "|| "
        for col in range(3):
            if (row, col) in revealed:
                prize_emoji = emoji_map[card[row][col]]
                row_content += f"{prize_emoji}  || "
            else:
                row_content += "🕳️  || "
        
        print(row_content, end='')
        if row == 0:
            print(" 1.00")
        elif row == 1:
            print(" 5.00")
        elif row == 2:
            print("20.00")

        print("=======================")
    print("  2.00    40     100    10000")

def check_for_win(card):
    # 横向检查
    winning_conditions = [
        (card[0][0], card[0][1], card[0][2], 1),  # 第一行
        (card[1][0], card[1][1], card[1][2], 5),  # 第二行
        (card[2][0], card[2][1], card[2][2], 20), # 第三行
        (card[0][0], card[1][0], card[2][0], 2),  # 第一列
        (card[0][1], card[1][1], card[2][1], 40), # 第二列
        (card[0][2], card[1][2], card[2][2], 100),# 第三列
        (card[0][0], card[1][1], card[2][2], 10000), # 斜线1
        (card[0][2], card[1][1], card[2][0], 10000)  # 斜线2
    ]
    
    for condition in winning_conditions:
        if condition[0] == condition[1] == condition[2]:
            return condition[3]  # 返回对应的奖励
    return None

def random_uncover(revealed):
    available_slots = [(row, col) for row in range(3) for col in range(3) if (row, col) not in revealed]
    return random.choice(available_slots)

def main(balance, username):
    while balance > 0:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"当前余额：{balance:.2f}")
        try:
            bet_input = input("按'Enter'支付1块购买(输入0退出) ")
            if bet_input.lower() == "0":
                print("退出当前游戏，返回主菜单。")
                return balance 
            elif bet_input == "":
                balance -= 1
        except ValueError:
            print("请输入一个有效的数字。")
            continue
        
        os.system('cls' if os.name == 'nt' else 'clear')
        print("你成功购买：过三关")

        if username != "demo_player":
            update_balance_in_json(username, balance)
        
        card = generate_scratch_card()
        revealed = []
        print_scratch_card(card, revealed)
        
        while len(revealed) < 9:
            input("按'Enter'随机刮开 ")
            os.system('cls' if os.name == 'nt' else 'clear')
            row, col = random_uncover(revealed)
            revealed.append((row, col))
            print("...你的刮刮卡...")
            print_scratch_card(card, revealed)

        os.system('cls' if os.name == 'nt' else 'clear')
        print("最终结果：")
        print_scratch_card(card, revealed=[(i, j) for i in range(3) for j in range(3)])

        win_amount = check_for_win(card)
        if win_amount:
            print(f"恭喜！你赢得了 {win_amount} 元!")
        else:
            win_amount = 0
            print("抱歉，你没有中奖。")
        
        balance += win_amount
        if username != "demo_player":
            update_balance_in_json(username, balance)

        if balance <= 0:
            print("你已经输光了本金，游戏结束。")
            return balance
        
        time.sleep(2.5)
    time.sleep(2.5)
    print("感谢您的游玩！")
    return balance

if __name__ == "__main__":
    main(100, "demo_player")