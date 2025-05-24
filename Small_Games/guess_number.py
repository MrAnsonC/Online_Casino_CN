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

chinese_numbers = ['一', '二', '三', '四', '五']

def guess_number_game(bet, balance):
    # 随机生成1到100之间的目标数字
    target_number = random.randint(1, 100)
    chances = 5  # 最大尝试次数
    
    # 设置赔率列表（第1次猜中到第5次猜中的赔率）
    odds = [196.00, 48.10, 14.24, 3.80, 1.85]
    
    # 游戏开始
    min_guess = 1
    max_guess = 100
    
    for attempt in range(1, chances + 1):
        while True:
            try:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"当前猜中的赔率是{odds[attempt - 1]}")
                print(f"范围是： {min_guess} - {max_guess}")
                guess = int(input(f"\n请输入第{chinese_numbers[attempt - 1]}个猜测的数字： "))
                
                if guess < min_guess or guess > max_guess:
                    print(f"\n请输入 {min_guess}-{max_guess} 之间的数字。")
                    time.sleep(1.5)
                else:
                    break
            except ValueError:
                print("请输入一个有效的整数！")
                time.sleep(1.5)
                
        # 判断猜测是否正确
        if guess == target_number:
            # 根据猜中的次数获取赔率
            winning_odds = odds[attempt - 1]
            winnings = bet * winning_odds
            balance += winnings
            print(f"你猜中了！你赢了{winnings:.2f}元!")
            print(f"赔率为{winning_odds}X")
            return balance
        elif guess < target_number:
            print("猜的数字小了!\n")
            min_guess = guess
        else:
            print("猜的数字大了!\n")
            max_guess = guess
        time.sleep(2)
    
    # 猜测次数用完，游戏结束
    print(f"抱歉你猜错了! 正确的数字是： {target_number}")
    return balance

# 主循环
def main(balance, username):
    while balance > 0:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(" 1-100猜数字")
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
        balance = guess_number_game(bet_input, balance)
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