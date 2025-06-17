import json
import os
import time

## Poker games import
from Small_Games import ChickenCrossing
from Small_Games import tower
from Small_Games import keno
from Small_Games import rocket
from Small_Games import guess_number
from Small_Games import minus
from Small_Games import RPS
from Small_Games import plinko
from Small_Games import slot_machine
from Small_Games import Sicbo

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
    
def display_menu():
    print(" 欢迎来到街机小游戏中心!\n")
    print("请选择以下的乐透种类(0返回主目录):")
    print("① 小鸡过马路  ② 上塔游戏  ③ 基诺")
    print("④ 剪刀石头布  ⑤ 飞天倍数  ⑥ 扫雷")
    print("⑦ 小钢珠跌落  ⑧ 猜数字1-100")
    print("⑨ 数字老虎机  ⑩ 骰宝")
    
def main(balance, user):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        display_menu()
        try:
            choice = input("\n请输入你的选择(0退出): ")
            if choice == '0':
                return balance
            if choice == '1':
                balance = ChickenCrossing.main(balance, user)
            elif choice == '2':
                balance = tower.main(balance, user)
            elif choice == '3':
                balance = keno.main(balance, user)
            elif choice == '4':
                balance = RPS.main(balance, user)
            elif choice == '5':
                balance = rocket.main(balance, user)
            elif choice == '6':
                balance = minus.main(balance, user)
            elif choice == "7":
                balance = plinko.main(balance, user)
            elif choice == '8':
                balance = guess_number.main(balance, user) 
            elif choice == '9':
                balance = slot_machine.main(balance, user)
            elif choice == '10':
                balance = Sicbo.main(user, balance)
            else:
                print("无效选择，请输入1-10。")
                time.sleep(1.5)
            update_balance_in_json(user, balance)
        except ValueError:
            print("请输入一个有效的数字。")
            continue
    