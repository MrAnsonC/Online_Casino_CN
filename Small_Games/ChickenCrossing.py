import random
import json
import time
import os

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

# 各难度对应死亡几率和赔率
difficulty_settings = {
    '1': {'death_rate': 1/25, 'multipliers': [1, 1.04, 1.09, 1.14, 1.20, 1.26, 1.33, 1.41, 1.50, 1.60, 1.71, 1.85, 2, 2.18, 2.40, 2.67, 3.00, 3.43, 4.00, 4.80, 6.00, 8.00, 12.00, 24.00]},
    '2': {'death_rate': 3/25, 'multipliers': [1, 1.09, 1.25, 1.43, 1.66, 1.94, 2.28, 2.71, 3.25, 3.94, 4.85, 6.07, 7.72, 10.04, 13.28, 18.40, 26.29, 39.43, 63.09, 110.40, 220.80, 552.00, 2208.00]},
    '3': {'death_rate': 5/25, 'multipliers': [1, 1.20, 1.52, 1.94, 2.51, 3.29, 4.39, 5.95, 8.24, 11.68, 16.98, 25.48, 39.63, 64.40, 110.40, 202.40, 404.80, 910.80, 2428.00, 8500.00, 51004.80]},
    '4': {'death_rate': 10/25, 'multipliers': [1, 1.60, 2.74, 4.85, 8.90, 16.98, 33.67, 71.71, 161.35, 391.86, 1044.96, 3134.87, 10972.06, 47545.60, 285273.60, 3138009.60]}
}

def format_multiplier(multiplier):
    if multiplier >= 1000000:
        return f"X{multiplier / 1000000:.1f}M  "
    if multiplier >= 100000:
        return f"X{int(multiplier / 1000)}K  "
    elif multiplier >= 10000:
        return f"X{multiplier / 1000:.1f}K "
    elif multiplier >= 1000:
        return f"X{multiplier / 1000:.1f}K  "
    elif multiplier >= 100:
        return f"X{multiplier:.2f}"
    elif multiplier >= 10:
        return f"X{multiplier:.2f} "
    else:
        return f"X{multiplier:.2f}  "

# 打印游戏界面
def display_stage(multiplier_list, current_stage, status="🐥  ", is_win=False):
    num_cols = len(multiplier_list)  # 实际列数
    # 打印 SART 行
    print("S   ||" + "        ||" * num_cols)
    
    # 打印赔率行
    formatted_multipliers = [format_multiplier(mult) for mult in multiplier_list]
    print(f"T   || " + "|| ".join(formatted_multipliers) + "||")
    
    # 打印状态行
    print(f"A   ||  {status}  ||" + "        ||" * (num_cols - 1))
    
    # 打印 R 行
    print("R   ||" + "        ||" * num_cols)
    
    # 打印 T 行
    print("T   ||" + "        ||" * num_cols + "\n")

def display_stages(multiplier_list, current_stage, status="🐥  ", is_win=False):
    num_cols = len(multiplier_list)  # 实际列数
    formatted_multipliers = [format_multiplier(mult) for mult in multiplier_list]
    formatted_multiplierss = [format_multiplier(mult) for mult in multiplier_list[1:]]

    # 第一次动画
    os.system('cls' if os.name == 'nt' else 'clear')
    print("你不要过来啊！！！！！！")
    print("\nS   ||" + " |____| ||" + "        ||" * (num_cols - 1)) 
    print(f"T   || " + "|| ".join(formatted_multipliers) + "||")
    print(f"A   ||  {status}  ||" + "        ||" * (num_cols - 1))
    print("R   ||" + "        ||" * num_cols)
    print("T   ||" + "        ||" * num_cols + "\n")
    time.sleep(0.88)

    # 第二次动画
    os.system('cls' if os.name == 'nt' else 'clear')
    print("你不要过来啊！！！！！！")
    print("\nS   ||" + " |    | ||" + "        ||" * (num_cols - 1))
    if num_cols != 0:
        print(f"T   || " + "|____| || " + "|| ".join(formatted_multiplierss) + "||")
    else:
        print(f"T   || " + " |____| ||")
    print(f"A   ||  {status}  ||" + "        ||" * (num_cols - 1))
    print("R   ||" + "        ||" * num_cols)
    print("T   ||" + "        ||" * num_cols + "\n")
    time.sleep(0.88)

    # 第三次动画
    os.system('cls' if os.name == 'nt' else 'clear')
    print("你不要过来啊！！！！！！")
    
    print("\nS   ||" + " |    | ||" + "        ||" * (num_cols - 1))
    if num_cols != 0:
        print(f"T   || " + "|    | || " + "|| ".join(formatted_multiplierss) + "||")
    else:
        print(f"T   || " + "|    |  ||")
    print(f"A   ||" + " |____| ||" +  "        ||" * (num_cols-1))
    print("R   ||" + "        ||" * num_cols)
    print("T   ||" + "        ||" * num_cols + "\n")
    time.sleep(0.88)

    # 第四次动画
    os.system('cls' if os.name == 'nt' else 'clear')
    print("丸辣！！！！！！！！！")
    
    print("\nS   ||" + " ______ ||" + "        ||" * (num_cols - 1))
    if num_cols != 0:
        print(f"T   || " + "|    | || " + "|| ".join(formatted_multiplierss) + "||")
    else:
        print(f"T   || " + "|    |  ||")
    print("A   ||" + " |    | ||" +  "        ||" * (num_cols-1))
    print("R   ||" + " |____| ||" + "        ||" * (num_cols-1))
    print("T   ||" + "        ||" * num_cols + "\n")
    time.sleep(0.88)

    # 第五次动画
    os.system('cls' if os.name == 'nt' else 'clear')
    print("丸辣！！！！！！！！！")
    print("\nS   ||" + "        ||" * num_cols)
    if num_cols != 0:
        print(f"T   || " + "______ || " + "|| ".join(formatted_multiplierss) + "||")
    else:
        print(f"T   || " + "______  ||")
    print("A   ||" + " |    | ||" +  "        ||" * (num_cols-1))
    print("R   ||" + " |    | ||" +  "        ||" * (num_cols-1))
    print("T   ||" + " |____| ||" + "        ||" * (num_cols-1) + "\n")
    time.sleep(0.88)

    # 第六次动画
    os.system('cls' if os.name == 'nt' else 'clear')
    print("丸辣！！！！！！！！！")
    print("\nS   ||" + "        ||" * num_cols)
    print(f"T   || " + "|| ".join(formatted_multipliers) + "||")
    print("A   ||" + " ______ ||" +  "        ||" * (num_cols-1))
    print("R   ||" + " |    | ||" +  "        ||" * (num_cols-1))
    print("T   ||" + " |    | ||" + "        ||" * (num_cols-1) + "\n")
    time.sleep(0.88)

    # 第七次动画
    os.system('cls' if os.name == 'nt' else 'clear')
    status="💀  "
    print("丸辣！！！！！！！！！")
    print("\nS   ||" + "        ||" * num_cols)
    print(f"T   || " + "|| ".join(formatted_multipliers) + "||")
    print(f"A   ||  {status}  ||" + "        ||" * (num_cols - 1))
    print("R   ||" + " ______ ||" +  "        ||" * (num_cols-1))
    print("T   ||" + " |    | ||" + "        ||" * (num_cols-1) + "\n")
    time.sleep(0.88)

    # 第八次动画
    os.system('cls' if os.name == 'nt' else 'clear')
    print("丸辣！！！！！！！！！")
    print("\nS   ||" + "        ||" * num_cols)
    print(f"T   || " + "|| ".join(formatted_multipliers) + "||")
    print(f"A   ||  {status}  ||" + "        ||" * (num_cols - 1))
    print("R   ||" + "        ||" * num_cols)
    print("T   ||" + " ______ ||" + "        ||" * (num_cols - 1) + "\n")
    time.sleep(0.88)
    os.system('cls' if os.name == 'nt' else 'clear')


# 处理每次过关
def play_game(bet, difficulty, balance):
    settings = difficulty_settings[difficulty]
    multipliers = settings['multipliers']
    death_rate = settings['death_rate']
    
    current_stage = 0
    display_stage(multipliers[current_stage:current_stage + 3], current_stage)

    while current_stage < len(multipliers) - 1:

        print("按 ① 前进  按 ② 停止")
        action = input('请选择：')
        if action != '1':
            time.sleep(0.68)
        
        if action == '2':
            os.system('cls' if os.name == 'nt' else 'clear')
            print("请选择：2\n")
            display_stage(multipliers[current_stage:current_stage + 3], current_stage, status="✔   ", is_win=True)
            print(f"恭喜！你赢了: {bet * multipliers[current_stage]:.2f}")
            winnings = bet * multipliers[current_stage]
            balance += winnings
            break
        elif action == '1':
            os.system('cls' if os.name == 'nt' else 'clear')
            print("请选择：1\n")
            current_stage += 1
            if random.random() < death_rate:
                display_stage(multipliers[current_stage:current_stage + 3], current_stage)
                time.sleep(1.25)
                display_stages(multipliers[current_stage:current_stage + 3], current_stage)
                print("丸辣！！！！！！！！！！！\n")
                display_stage(multipliers[current_stage:current_stage + 3], current_stage, status="💀  ")
                print("很遗憾，你失败了！")
                return balance
            else:
                if current_stage != len(multipliers) - 1:
                    display_stage(multipliers[current_stage:current_stage + 3], current_stage)
                    time.sleep(1.25)
                    print(f"你成功过关！你现在赢了：{bet * multipliers[current_stage]:.2f}")
                else:
                    display_stage(multipliers[current_stage:current_stage + 3], current_stage)
                    time.sleep(1.25)
                    print(f"恭喜你完成所有关卡，赢得奖金: {bet * multipliers[-1]:.2f}")
                    balance += bet * multipliers[-1]
                    display_stage(multipliers[current_stage:current_stage + 3], current_stage)
                    display_stage(multipliers[current_stage:current_stage + 3], current_stage, status="✔   ", is_win=True)
                    break
        elif action == '999':
            os.system('cls' if os.name == 'nt' else 'clear')
            print("请选择：1\n")
            current_stage += 1
            display_stage(multipliers[current_stage:current_stage + 3], current_stage)
            time.sleep(1.25)
            display_stages(multipliers[current_stage:current_stage + 3], current_stage)
            display_stage(multipliers[current_stage:current_stage + 3], current_stage, status="💀  ")
            print("\n很遗憾，你失败了！")
            return balance
        elif action == '888':
            os.system('cls' if os.name == 'nt' else 'clear')
            print("请选择：1\n")
            current_stage += 7
            if current_stage != len(multipliers) - 1:
                display_stage(multipliers[current_stage:current_stage + 3], current_stage)
                time.sleep(1.25)
                print(f"你成功过关！你现在赢了：{bet * multipliers[current_stage]:.2f}")
            else:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"恭喜你完成所有关卡，赢得奖金: {bet * multipliers[-1]:.2f}")
                winnings = bet * multipliers[-1]
                balance += winnings
                display_stage(multipliers[current_stage:current_stage + 3], current_stage)
                display_stage(multipliers[current_stage:current_stage + 3], current_stage, status="✔   ", is_win=True)
                break
        elif action == '88':
            os.system('cls' if os.name == 'nt' else 'clear')
            print("请选择：1\n")
            current_stage += 1
            if current_stage != len(multipliers) - 1:
                display_stage(multipliers[current_stage:current_stage + 3], current_stage)
                time.sleep(1.25)
                print(f"你成功过关！你现在赢了：{bet * multipliers[current_stage]:.2f}")
            else:
                os.system('cls' if os.name == 'nt' else 'clear')
                display_stage(multipliers[current_stage:current_stage + 3], current_stage)
                print(f"恭喜你完成所有关卡，赢得奖金: {bet * multipliers[-1]:.2f}")
                balance += bet * multipliers[-1]
                display_stage(multipliers[current_stage:current_stage + 3], current_stage)
                display_stage(multipliers[current_stage:current_stage + 3], current_stage, status="✔   ", is_win=True)
                winnings = bet * multipliers[-1]
                balance += winnings
        else:
            print("无效输入，请按 ① 或 ②\n")

    time.sleep(2.5)
    return balance

# 主循环
def main(balance, username):
    while balance > 0:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(" 小鸡过马路")
        print(f"当前余额：{balance:.2f}")
        try:
            bet_input = input("输入您的下注金额(0退出)：")
            if bet_input.lower() == "0":
                print("退出当前游戏，返回主菜单。")
                return balance 
            else:
                bet_input = int(bet_input)

            if bet_input > balance or bet_input <= 0:
                print("下注金额无效，请输入有效的金额。")
                continue
        except ValueError:
            print("请输入一个有效的数字。")
            continue
        
        balance -= bet_input
        if username != "demo_player":
            update_balance_in_json(username, balance)
        difficulty = ""
        while difficulty not in difficulty_settings:
            print("\n① 简单  ② 中等  ③ 困难  ④ 地狱")
            difficulty = input("请选择难度：").strip()
            if difficulty not in difficulty_settings:
                print("无效的难度选择，请重新选择。")
        os.system('cls' if os.name == 'nt' else 'clear')
        print("开始游戏 祝你好运！\n")
        balance = play_game(bet_input, difficulty, balance)
        if username != "demo_player":
            update_balance_in_json(username, balance)
        time.sleep(2)
        
        if balance <= 0:
            print("你已经输光了本金，游戏结束。")
            return balance

    print("感谢您的游玩！")
    return balance  # 返回更新后的余额 

if __name__ == "__main__":
    main(100, "demo_player")