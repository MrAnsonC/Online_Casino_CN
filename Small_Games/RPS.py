import random
import time
import json
import os

# 获取数据文件的路径
def get_data_file_path():
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

# 更新余额到JSON文件
def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)

# 将用户输入映射到对应的选择
def get_user_choice():
    print("...欢迎游玩剪刀石头布...\n")
    print("①✌ 剪刀  ②✊石头  ③✋布")
    user_input = input("请输入数字来选择你的决定: ")
    if user_input == '2':
        return '✊'
    elif user_input == '1':
        return '✌'
    elif user_input == '3':
        return '✋'
    else:
        print("无效输入，请重新输入。")
        return get_user_choice()

# 生成电脑的随机选择
def get_computer_choice():
    choices = ['✊', '✌', '✋']
    return random.choice(choices)

# 决定胜负
def determine_winner(user_choice, computer_choice):
    if user_choice == computer_choice:
        return "和！ 赔率是1.01X!"
    elif (user_choice == '✊' and computer_choice == '✌') or \
         (user_choice == '✌' and computer_choice == '✋') or \
         (user_choice == '✋' and computer_choice == '✊'):
        return "你赢了！ 赔率是1.95X!"
    else:
        return "下局加油！"

# 主函数
def main(balance, username):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(" 剪刀石头布")
        print(f"\n当前余额：{balance:.2f}")
        try:
            bet_input = input("输入您的下注金额(0退出)：")
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

        os.system('cls' if os.name == 'nt' else 'clear')
        user_choice = get_user_choice()
        computer_choice = get_computer_choice()
        print(f"你选择了: {user_choice}")
        print("\n...请稍等 电脑正在随机生成中...")
        time.sleep(1.2)
        print("...加载中...")
        time.sleep(1.2)
        print(f"电脑选择了: {computer_choice}")
        result = determine_winner(user_choice, computer_choice)
        print()
        if result == "下局加油！":
            print("下局加油！")
        elif result == "你赢了！ 赔率是1.95X!":
            balance += bet_input * 1.95
            print(f"你赢了{bet_input*1.95}！ 赔率是1.95X!")
        else:
            balance += bet_input * 1.05
            print(f"和！")
        if username != "demo_player":
            update_balance_in_json(username, balance)
        time.sleep(3)

# 开始游戏
if __name__ == "__main__":
    main(100, "demo_player")
