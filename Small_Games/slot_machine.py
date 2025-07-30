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
    if not os.path.exists(file_path):
        return []
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

# 计算中奖情况
def calculate_prize(d1, d2, d3):
    # 判断顺子
    if (d1 + 2 == d2 + 1 == d3) or (d1 == d2 + 1 == d3 + 2):
        return 5
    # 两个数字一样
    if d1 == d2 or d2 == d3 or d1 == d3:
        return 5
    # 三个数字一样
    if d1 == d2 == d3:
        if d1 == 1:
            return 30  # 三个1
        if d1 == 7:
            return 100  # 三个7
        return 17  # 其他三个一样
    return 0  # 没有中奖

# ASCII艺术数字
ascii_art_numbers = {
    '0': [' 000 ', '0   0', '0   0', '0   0', ' 000 '],
    '1': ['  11 ', ' 1 1 ', '   1 ', '   1 ', '11111'],
    '2': [' 222 ', '2   2', '  22 ', ' 2   ', '22222'],
    '3': [' 3333', '    3', '  333', '    3', ' 3333'],
    '4': ['4  44', '4  44', ' 4444', '   44', '   44'],
    '5': [' 5555', '5    ', ' 555 ', '    5', ' 555 '],
    '6': ['  66 ', ' 6   ', ' 666 ', '6   6', ' 666 '],
    '7': ['77777', '    7', '   7 ', '  7  ', ' 7   '],
    '8': [' 888 ', '8   8', ' 888 ', '8   8', ' 888 '],
    '9': [' 9999', '9   9', ' 9999', '    9', ' 999 ']
}

# 打印带有外壳的ASCII数字
def print_ascii_with_shell(num1, num2, num3):
    # 顶部边框
    print("=" * 29)
    
    # 打印数字，每行在数字两侧加上边框
    for i in range(5):
        print(f"|| {ascii_art_numbers[str(num1)][i]} || {ascii_art_numbers[str(num2)][i]} || {ascii_art_numbers[str(num3)][i]} ||")
    
    # 底部边框
    print("=" * 29)

# 显示动画
def show_animation(result1, result2, result3, duration1=6, duration2=11, duration3=15):
    start_time = time.time()
    end_time1 = start_time + duration1
    end_time2 = start_time + duration2
    end_time3 = start_time + duration3

    while True:
        current_time = time.time()
        os.system('cls' if os.name == 'nt' else 'clear')  # 清屏

        # 随机生成滚动中的数字或显示结果
        if current_time < end_time1:
            num1 = random.randint(1, 9)
        else:
            num1 = result1

        if current_time < end_time2:
            num2 = random.randint(0, 9)
        else:
            num2 = result2

        if current_time < end_time3:
            num3 = random.randint(1, 9)
        else:
            num3 = result3

        # 打印三个数字的ASCII艺术
        print_ascii_with_shell(num1, num2, num3)

        # 检查是否完成所有动画
        if current_time >= end_time3:
            break
        
        time.sleep(0.05)

def zero_rewards(d1, d2, d3):
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # 奖励列表
    prize_of_zero = [0, 0, 0, 2, 2, 5, 10, 20, 50]
    
    # 随机打乱奖励顺序
    random.shuffle(prize_of_zero)

    while True:
        try:
            # 获取用户输入
            show_animation(d1, d2, d3, 0, 0, 0)
            print("你抽中了0！")
            number = int(input("请输入1-9的任何数字！"))
            
            if number not in range(1, 10):  # 确保输入为 1 到 9 之间的数字
                print("请重新输入有效的数字！\n")
                time.sleep(2)
                os.system('cls' if os.name == 'nt' else 'clear')
            else:
                # 根据输入选择奖励
                selected_prize = prize_of_zero[number - 1]
                print("\n奖品如下：")
                print(" 1  2  3  4  5  6  7  8  9")
                for i in range(9):
                    print(f"{prize_of_zero[i]:02d}", end=" ")
                print()
                return selected_prize  # 返回选择的奖励值
        except ValueError:
            print("无效输入，请输入一个数字！")
        
    

# 游戏主循环
def main(balance, username):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"当前余额：{balance:.2f}")
        bet_input = input("按'Enter'支付1块游玩(输入0退出): ")
        if bet_input == "0":
            print("退出游戏，返回主菜单。")
            if username != "demo_player":
                update_balance_in_json(username, balance)
            break
        elif bet_input == "":
            if balance < 1:
                print("余额不足，无法继续游戏。")
                break
            balance -= 1
        else:
            print("请输入正确的指令！")
            continue
    
        if username != "demo_player":
            update_balance_in_json(username, balance)

        # 生成随机数
        d1, d2, d3 = random.randint(1, 9), random.randint(0, 9), random.randint(1, 9)

        print("开始抽奖！")

        # 显示动画
        show_animation(d1, d2, d3)

        # 打印结果
        prize_multiplier = calculate_prize(d1, d2, d3)
        if d2 == 0:
            prize_multiplier = prize_multiplier + zero_rewards(d1, d2, d3)

        if prize_multiplier > 0:
            prize = prize_multiplier
            balance += prize
            print(f"恭喜！你赢了 {prize} 块！")
        else:
            print("很遗憾，未中奖。")

        time.sleep(3.5)

        if username != "demo_player":
            update_balance_in_json(username, balance)
    
    return balance

# 开始游戏
if __name__ == "__main__":
    main(100, "demo_player")
