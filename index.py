import json
import os
import time

# Account Setting
import register
import charge

# Games import
from Casino_Games import casino_games
from Lotto import lotto
from Small_Games import small_games


def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'saving_data.json')

# 加载用户数据
def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 保存用户数据
def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# User login
def login():
    users = load_user_data()
    os.system('cls' if os.name == 'nt' else 'clear')

    # Track the attempted usernames
    attempted_usernames = []  # List to keep track of attempted usernames

    for attempt in range(3):  # Allow 3 attempts
        username = input("输入登录名称: ")
        password = input("输入你的密码: ")

        attempted_usernames.append(username)  # Add attempted username to the list

        for user in users:
            if user['user_name'] == username:

                # Check if the user is locked
                if user.get('lock', "True") == "True":  # Check if the account is locked
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"你的账号 {username} 被锁定 请联系管理员解锁\n")
                    return None, None, None  # Return if locked

                # Check password
                if user['password'] == password:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"欢迎, {username}! 你现在的余额为 {user['cash']}")
                    return user, users, username  # Return the current user and the full user list for updating

        print("错误登录名称和密码\n")

    # After 3 unsuccessful attempts, lock specific accounts
    for user in users:
        if user['user_name'] in attempted_usernames:
            user['lock'] = "True"  # Lock only those accounts that were attempted

    print("\n账户已被锁定，请联系管理员解锁")
    save_user_data(users)  # Save changes to JSON
    return None, None, None  # Return None since the login failed for all users



# Display the game menu
def display_menu():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("欢迎来到游戏中心!\n")
    print("选择一下游戏:")
    print("① 赌场游戏  ② 街机小游戏  ③ 刮刮乐")

    print("⑨ 账号服务")

    # ⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳
    

def main():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        choice = input("你是要 ① 登录还是 ② 注册? ").strip().lower()

        if choice == '1':
            user, users, username = login()
            if not user:
                return  # 登录失败则退出

        elif choice == '2':
            # 运行注册脚本
            register.main()
            continue  # 注册后重新提示用户输入

        else:
            print("无效选择，请输入 ① 或 ②\n")
            continue

        balance = float(user['cash']) if user['cash'] not in [None, "None"] else 0  # 确保余额为有效数字

        while True:
            display_menu()
            choice = input("\n请输入你的选择: ")

            if choice == '1':
                balance = casino_games.main(balance, username)
            elif choice == '2':
                balance = small_games.main(balance, username)
            elif choice == '3':
                balance = lotto.main(balance, username)  
            elif choice == '9':
                os.system('cls' if os.name == 'nt' else 'clear')
                print("请选择以下的账号服务(0退出):")
                print("① 查询余额  ② 充值  ③ 提款\n④ 更改密码  ⑤ 登出")
                choices = input("\n请输入你的选择: ")
                if choices == '1':
                    print(f"你最新的余额为:{balance:.2f}")
                    time.sleep(5)
                elif choices == '2':
                    recharge_amount = charge.main(user, 'charge')  # 获取充值金额
                    if recharge_amount is None:
                        recharge_amount = 0  # 处理 None 值
                    balance += float(recharge_amount)
                elif choices == '3':
                    recharge_amount = charge.main(user, 'withdraw')  # 获取充值金额
                    if recharge_amount is None:
                        recharge_amount = 0  # 处理 None 值
                    balance -= float(recharge_amount)
                elif choices == '4':
                    while True:
                        password1 = input("\n请输入密码: ")
                        password2 = input("请再次输入密码: ")

                        if password1 != password2:
                            print("两次输入的密码不一致，请重试。")
                        else:
                            print("密码更改成功！")
                            user['password'] = password1
                            time.sleep(3)
                            break
                elif choices == '5':
                    time.sleep(2)
                    os.system('cls' if os.name == 'nt' else 'clear')
                    break
                elif choice == '0':
                    os.system('cls' if os.name == 'nt' else 'clear')
            else:
                print("无效选择，请重试。")
                time.sleep(1.5)
                continue

            if balance is None:  # 如果余额为 None，将其设置为 0
                balance = 0
            
            # 更新用户余额到 JSON 数据
            user['cash'] = f"{balance:.2f}"
            save_user_data(users)

        print("谢谢游玩！ ")
        print(f"你最新的余额为:{balance:.2f}")
        time.sleep(5)

if __name__ == '__main__':
    main()