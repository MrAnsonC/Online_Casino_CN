import random
import time
import threading
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

game_running = True

def player_press_enter():
    global game_running
    input()
    game_running = False

def simulate_enter_key_press():
    global game_running
    game_running = False  # 模拟按下 Enter

def generate_probability_table(max_multiplier, C=100, k=1.5):
    probability_table = []
    multiplier = 1.01
    while multiplier <= max_multiplier:
        prob = C / (multiplier ** k)
        probability_table.append((round(multiplier, 2), prob))
        multiplier += 0.01 if multiplier < 2 else 0.1 if multiplier < 10 else 1
    total_prob = sum(prob for _, prob in probability_table)
    probability_table = [(m, (p / total_prob) * 100) for m, p in probability_table]
    return probability_table

def generate_boom_multiplier(probability_table):
    random_number = random.uniform(0, 100)
    cumulative_probability = 0
    for multiplier, prob in probability_table:
        cumulative_probability += prob
        if random_number <= cumulative_probability:
            return multiplier
    return probability_table[-1][0]

def start_game(bet_amount, target_multiplier):
    global game_running
    game_running = True

    probability_table = generate_probability_table(1000000)
    boom_multiplier = generate_boom_multiplier(probability_table)

    if target_multiplier == 98789:
        boom_multiplier = float(input(f"原本的赔率是 {boom_multiplier}，更新赔率为: ") or boom_multiplier)
        target_multiplier = boom_multiplier - 0.03
        time.sleep(1.5)
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print("游戏将在3秒后开始...")
    for i in range(3, 0, -1):
        print(f"倒计时 {i}...")
        time.sleep(1)
    print("开始!")
    time.sleep(1)
    os.system('cls' if os.name == 'nt' else 'clear')

    current_multiplier = 0.95
    time_to_increase = 0.4

    enter_thread = threading.Thread(target=player_press_enter)
    enter_thread.start()

    while game_running and current_multiplier < boom_multiplier:
        time.sleep(time_to_increase)

        # 增加倍数
        current_multiplier += 0.01  # 每次增加0.01

        # 根据当前倍数调整时间间隔
        if time_to_increase > 0.15:
            time_to_increase *= 0.999

        # 打印倍数逻辑
        if round(current_multiplier) % 1 == 0:
            os.system('cls' if os.name == 'nt' else 'clear')
            print("任何时间按 'Enter' 结束...\n")
            print("......现在的倍数是......")
            print(f" 新的赔率为：{current_multiplier-0.05:.2f}x")
            print(f" 新的赔率为：{current_multiplier-0.04:.2f}x")
            print(f" 新的赔率为：{current_multiplier-0.03:.2f}x")
            print(f" 新的赔率为：{current_multiplier-0.02:.2f}x")
            print(f" 新的赔率为：{current_multiplier-0.01:.2f}x")

        if target_multiplier <= current_multiplier:
            print(f"\n{target_multiplier:.2f}x已到！ 自动兑现成功！")
            print(f"本次最高可赢 {boom_multiplier:.2f}X")
            print("请按'Enter'继续游戏")
            simulate_enter_key_press()
            enter_thread.join()  # 确保线程完成
            return bet_amount * target_multiplier
        
        if current_multiplier >= boom_multiplier:
            print(f"\n爆了💣! 本次的最高倍数是 {boom_multiplier:.2f}x.\n")
            print("请按'Enter'继续游戏")
            game_running = False
            simulate_enter_key_press()
            enter_thread.join()  # 确保线程完成
            return 0
    
    enter_thread.join()
    
    if not game_running:
        print(f"\n你选择兑现的倍数是 {current_multiplier:.2f}x!")
        print(f"本次最高可赢 {boom_multiplier:.2f}X")
        input("请按'Enter'继续游戏")
        return bet_amount * current_multiplier

    

def main(balance, username):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(" 飞天倍数")
        print(f"\n当前余额：{balance:.2f}")
        try:
            bet_input = input("输入您的下注金额(0退出)： ")
            if bet_input == "0":
                print("退出当前游戏，返回主菜单。")
                return balance
            else:
                bet_input = int(bet_input)

            if bet_input > balance or bet_input <= 0:
                print("下注金额无效，请输入有效的金额。")
                time.sleep(2)
                continue
        except ValueError:
            print("请输入一个有效的数字。")
            time.sleep(2)
            continue

        balance -= bet_input
        if username != "demo_player":
            update_balance_in_json(username, balance)

        try:
            target_multiplier = input("输入自动兑现倍数(可选)：  ")
            
            # 如果用户输入为空，设置默认值
            if target_multiplier == "":
                target_multiplier = 100000000000
            else:
                target_multiplier = float(target_multiplier)  # 转换为浮点数
            
            # 检查是否大于1
            if target_multiplier < 1.01:
                print("输入无效，请输入大于1.01的倍数。")
                time.sleep(2)
                continue

        except ValueError:
            print("请输入一个有效的数字。")
            time.sleep(2)
            continue

        winnings = start_game(bet_input, target_multiplier)
        balance += winnings

        if username != "demo_player":
            update_balance_in_json(username, balance)

        if balance <= 0:
            print("你已经输光了本金，游戏结束。")
            return balance

        time.sleep(2.5)
        
if __name__ == "__main__":
    main(100, "demo_player")