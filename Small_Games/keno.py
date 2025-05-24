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

# 赔率表
odds_easy = {
    1: [0.70, 1.85],
    2: [0, 2, 3.80],
    3: [0, 1.10, 1.38, 26],
    4: [0, 0, 2.2, 7.9, 90],
    5: [0, 0, 1.5, 4.2, 13, 300],
    6: [0, 0, 1.1, 2, 6.2, 100, 700],
    7: [0, 0, 1.1, 1.6, 3.5, 15, 225, 700],
    8: [0, 0, 1.1, 1.5, 2, 5.5, 39, 100, 800],
    9: [0, 0, 1.1, 1.3, 1.7, 2.5, 7.5, 50, 250, 1000],
    10: [0, 0, 1.1, 1.2, 1.3, 1.8, 3.5, 13, 50, 250, 1000]
}

odds_medium = {
    1: [0.4, 2.75],
    2: [0, 1.8, 5.1],
    3: [0, 0, 2.8, 50],
    4: [0, 0, 1.7, 10, 100],
    5: [0, 0, 1.4, 4, 14, 390],
    6: [0, 0, 0, 3, 9, 180, 710],
    7: [0, 0, 0, 2, 7, 30, 400, 800],
    8: [0, 0, 0, 2, 4, 11, 67, 400, 900],
    9: [0, 0, 0, 2, 2.5, 5, 15, 100, 500, 1000],
    10: [0, 0, 0, 1.6, 2, 4, 7, 26, 100, 500, 1000]
}

odds_difficult = {
    1: [0, 3.96],
    2: [0, 0, 17.10],
    3: [0, 0, 0, 81.50],
    4: [0, 0, 0, 10, 259],
    5: [0, 0, 0, 4.50, 48, 450],
    6: [0, 0, 0, 0, 11, 350, 710],
    7: [0, 0, 0, 0, 7, 90, 400, 800],
    8: [0, 0, 0, 0, 5, 20, 270, 600, 900],
    9: [0, 0, 0, 0, 4, 11, 56, 500, 800, 1000],
    10: [0, 0, 0, 0, 3.5, 8, 13, 63, 500, 800, 1000]
}

def game_round(difficulty, bet_amount, balance):
    # 根据难度选择赔率表
    if difficulty == "1":
        odds = odds_easy
        odds_word = "简单"
    elif difficulty == "2":
        odds = odds_medium
        odds_word = "中等"
    else:
        odds = odds_difficult
        odds_word = "地狱"

    # 用户选择的数字
    user_numbers = []
    i = 1
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\t{odds_word}模式")
    print("请输入数字1-50，不输入结束")
    print(" 输入数字88，获得幸运数字！\n")

    while i <= 10:
        try:
            user_input = input(f"请输入第{i}个数字: ")
            if user_input == "88":  # 用户输入88，随机生成一个数字
                random_number = random.randint(1, 50)
                while random_number in user_numbers:  # 确保随机数字不重复
                    random_number = random.randint(1, 50)
                print(f"幸运生成的第{i}个数字为: {random_number}\n")
                number = int(random_number)
            elif user_input == "":
                break
            else:
                number = int(user_input)

            if 1 <= number <= 50:
                if number not in user_numbers:
                    user_numbers.append(number)
                    i += 1
                else:
                    print("数字已选，请选择其他数字!\n")
            else:
                print("请输入1到50之间的数字!\n")
        except ValueError:
            print("请输入一个有效的数字!\n")
        if i == 11:
            time.sleep(3)
    
    if len(user_numbers) == 0:
        print("您没有选择任何数字，本轮下注作废。")
        time.sleep(5)
        return balance
    
    user_numbers.sort()
    formatted_numbers = ""
    for i in range(len(user_numbers)):
        # 在第6个数字之后换行
        if i > 0 and i % 5 == 0:
            formatted_numbers += "\n"
            
        # 格式化数字，单个数字时前面加0
        formatted_numbers += f"{user_numbers[i]:02}"
        
        # 每行最后一个数字不加逗号和空格，其他加逗号和空格
        if (i + 1) % 5 != 0 and i < len(user_numbers) - 1:
            formatted_numbers += ", "

    # 系统随机生成10个数字
    # 初始化一个空列表用于存储中奖数字
    system_numbers = []

    # 循环直到生成10个不重复的中奖数字
    while len(system_numbers) < 10:
        number = random.randint(1, 50)  # 随机生成1到50之间的数字
        if number not in system_numbers:  # 检查数字是否已存在
            system_numbers.append(number)  # 添加到中奖数字列表

    system_numbers_sorted = sorted(system_numbers)  # 对数字排序

    # 数字对应的中文数字
    chinese_numbers = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

    # 显示每个中奖数字（两位数格式）
    drawn_numbers = []
    for i, number in enumerate(system_numbers, start=1):
        os.system('cls' if os.name == 'nt' else 'clear')
        drawn_numbers.append(number)
        print("你的中奖数字是...")
        print(f"{formatted_numbers}\n")
        print("中奖详情：")
        print(f"第{chinese_numbers[i-1]}个中奖数字为： {number:02d}")
        print("\n==========")
        print("现在抽中的幸运数字有：")
        for index, num in enumerate(sorted(drawn_numbers)):
            if index > 0 and index % 5 == 0:  # 每5个数字换行
                print()  # 换行
            if index == len(drawn_numbers) - 1 or index % 5 == 4:  # 如果是最后一个数字或是行的最后一个数字
                print(f"{num:02d}", end="")  # 不加逗号
            else:
                print(f"{num:02d}", end=", ")  # 加逗号
        time.sleep(1.25)

    
    # 显示排序后的中奖数字
    os.system('cls' if os.name == 'nt' else 'clear')
    print("...你的中奖数字是...")
    print(f"{formatted_numbers}\n")
    print("所有中奖数字分别为：")
    for index, num in enumerate(system_numbers_sorted):
        if index % 5 == 4:  # 每5个数字后换行
            print(f"{num:02d}")
        else:
            print(f"{num:02d}, ", end="")

    # 计算匹配的数字数量
    matches_set = set(user_numbers) & set(system_numbers)
    matches = len(set(user_numbers) & set(system_numbers))
    print(f"\n您匹配了 {matches} 个数字。")
    if matches > 0:
        print(f"分别为： \n{' '.join([f'{num:02d}' for num in sorted(matches_set)])}")

    # 根据匹配的数量计算奖金
    num_choices = len(user_numbers)
    if matches < len(odds[num_choices]):
        multiplier = odds[num_choices][matches]
        winnings = bet_amount * multiplier
        balance += winnings
        print()
        if winnings > bet_amount:
            print(f"您赢得了 {winnings:.2f} 元，赔率为 {multiplier:.2f}")
        elif multiplier > 0:
            print(f"安慰奖：获得奖金的{multiplier:.2f}X")
        else:
            print("没有匹配足够的数字，未获得奖金。")

    time.sleep(5)
    return balance

def main(balance, username):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(" 基诺游戏")
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

        while True:
            try:
                print("\n①简单 ②中等 ③地狱")
                difficulty = input("请选择难度：")

                if difficulty not in ["1", "2", "3"]:
                    print("无效选择，请重新选择难度。")
                    time.sleep(2)
                    continue
                break
            except ValueError:
                print("请输入一个有效的数字。")
                time.sleep(2)
                continue

        balance = game_round(difficulty, bet_input, balance)
        if username != "demo_player":
            update_balance_in_json(username, balance)

        if balance <= 0:
            print("你已经输光了本金，游戏结束。")
            return balance

if __name__ == "__main__":
    main(100, "demo_player")