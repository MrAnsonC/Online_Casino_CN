import random
import os
import json
import time

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
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def update_balance_in_json(username, new_balance):
    users = load_user_data()  # 先加载现有用户数据
    for user in users:
        if user['user_name'] == username:  # 查找当前用户
            user['cash'] = f"{new_balance:.2f}"  # 更新余额
            break
    save_user_data(users)  # 保存更新后的数据

# 奖金对应的emoji
emoji_map = {
    10000: "🏦",
    100: "💵",
    40: "💲",
    20: "🧧",
    5: "💰",
    2: "💎",
    1: "🪙"
}

reverse_emoji_map = {v: k for k, v in emoji_map.items()}

# 概率设置
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

# 创建奖池
def generate_prize_pool():
    pool = []
    for prize, count in prizes.items():
        pool.extend([prize] * count)
    return pool

# 随机生成刮刮乐网格
def generate_scratch_card():
    pool = generate_prize_pool()
    
    # 根据概率选择是否中奖
    win_prize = random.choices(
        list(prizes.keys()),
        weights=prizes.values(),
        k=1
    )[0]

    if win_prize != 0:
        card = [win_prize] * 3  # 3个相同的中奖金额
        remaining_pool = [prize for prize in pool if prize != win_prize and prize != 0]
        
        while len(card) < 9:
            candidate = random.choice(remaining_pool)
            if card.count(candidate) < 2:  # 保证其他金额不超过2次
                card.append(candidate)
        random.shuffle(card)
        return [card[i:i+3] for i in range(0, 9, 3)]
    else:
        card = []
        while len(card) < 9:
            remaining_pool = [prize for prize in pool if prize != win_prize and prize != 0]
            candidate = random.choice(remaining_pool)
            if card.count(candidate) < 2:  # 确保每个金额不超过2个
                card.append(candidate)

        random.shuffle(card)
        return [card[i:i+3] for i in range(0, 9, 3)]

def print_winning_symbol():
    print("3个相同图案中奖 🧧🧧🧧 = 20")
    print("🏦🏦🏦 = 10000  💰💰💰 = 05")
    print("💵💵💵 = 100    💎💎💎 = 02") 
    print("💲💲💲 = 40     🪙🪙🪙 = 01")

# 打印刮刮乐网格
def print_scratch_card(card, revealed=None):
    if revealed is None:
        revealed = []
    
    # 统计每种奖品的数量
    prize_count = {prize: 0 for prize in emoji_map.keys()}
    print("===========================")
    
    for row in range(3):
        row_content = " || "
        for col in range(3):
            if (row, col) in revealed:
                prize_emoji = emoji_map[card[row][col]]
                row_content += f" {prize_emoji}  || "
                prize_count[card[row][col]] += 1  # 增加对应奖品的数量
            else:
                row_content += " 🕳️  || "
        
        # 打印每一行的奖品信息
        print(row_content)
        
        # 打印行分隔线
        print("===========================")

# 检查是否中奖
def check_for_win(card):
    # 将网格展平成一个列表，统计相同金额的数量
    flat_card = sum(card, [])
    for prize in set(flat_card):
        if flat_card.count(prize) == 3:
            return prize
    return None

# 随机挖一个未被揭开的洞
def random_uncover(revealed):
    available_slots = [(row, col) for row in range(3) for col in range(3) if (row, col) not in revealed]
    return random.choice(available_slots)

# 主程序
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
        if username != "demo_player":
            update_balance_in_json(username, balance)
        print_winning_symbol()
        print("\n你成功购买：高尔夫球刮刮乐")
        
        card = generate_scratch_card()
        revealed = []
        print_scratch_card(card, revealed)
        
        while len(revealed) < 9:
            # 随机挖开一个洞
            input("按'Enter'打进一颗球")
            os.system('cls' if os.name == 'nt' else 'clear')
            row, col = random_uncover(revealed)
            revealed.append((row, col))
            print_winning_symbol()
            print("\n...你的刮刮卡...")
            print_scratch_card(card, revealed)

        # 最终显示完整的刮刮乐结果
        os.system('cls' if os.name == 'nt' else 'clear')
        print_winning_symbol()
        print("\n最终结果：")
        print_scratch_card(card, revealed=[(i, j) for i in range(3) for j in range(3)])

        # 检查是否中奖
        win_amount = check_for_win(card)
        if win_amount:
            print(f"恭喜！你赢得了 {win_amount} 元!")
        else:
            win_amount = 0
            print("抱歉，你没有中奖。")
        win_amount = int(win_amount)

        balance += win_amount
        if username != "demo_player":
            update_balance_in_json(username, balance)

        if balance <= 0:
            print("你已经输光了本金，游戏结束。")
            return balance
        
        time.sleep(2.5)
    time.sleep(2.5)
    print("感谢您的游玩！")
    return balance  # 返回更新后的余额 

# 运行游戏
if __name__ == "__main__":
    main(100, "demo_player")