import json
import os
import time

## Lotto games import
from tkinter import Tk
from Lotto import golfs_gui
from Lotto import pass_3_level_gui
from Lotto import stacked
from Lotto import num_gui
from Lotto import Banknote_Detection_gui

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
    print(" 欢迎来到刮刮卡中心!\n")
    print("请选择以下的乐透种类(0返回主目录):")
    print("① 验钞机(1块/特易中奖)  - 大奖1000！")
    print("② 高尔夫球(1块)       - 大奖10 000！")  
    print("③ 过三关(1块)         - 大奖10 000！")
    print("④ 叠叠乐(5块)         - 大奖50 000！")
    print("⑤ 100X现金大挑战(5块) - 大奖50 000！")
    
def main(balance, user):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        display_menu()
        try:
            choice = input("\n请输入你的选择(0退出): ")
            if choice == '0':
                return balance
            if choice == '1':
                balance = Banknote_Detection_gui.main(balance, user)
            elif choice == '2':
                root = Tk()
                game = golfs_gui.ScratchGame(root, balance, user)  # 创建游戏实例
                root.mainloop()  # 运行游戏
                balance = game.balance  # 退出后获取余额
            elif choice == '3':
                balance = pass_3_level_gui.main(balance, user)
            elif choice == '4':
                balance = stacked.main(balance, user)
            elif choice == '5':
                balance = num_gui.main(balance, user)
            else:
                print("无效选择，请输入0-5。")
                time.sleep(1.5)
            update_balance_in_json(user, balance)
        except ValueError:
            print("请输入一个有效的数字。")
            continue
    
