import json
import os
import time

## Poker games import
from Casino_Games import Blackjack
from Casino_Games import UTH_GUI
from Casino_Games import transfer_baccarat
from Casino_Games import Three_Card_Poker
from Casino_Games import Sicbo
from Casino_Games import Casino_Holdem
from Casino_Games import Caribbean_Stud_Poker

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
    print("欢迎来到赌场!\n")
    print("请选择以下的游戏种类(0返回主目录):")
    print("① 21点 ② 终极德州扑克 ③ 百家乐")
    print("④ 三張牌撲克 ⑤ 骰宝 ⑥ 赌场扑克")
    print("⑦ 加勒⽐梭哈撲克")

def main(balance, user):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        display_menu()
        try:
            choice = input("\n请输入你的选择: ")
            if choice == "0":
                return balance 
            elif choice == "1":
                balance = Blackjack.main(balance, user)
            elif choice == "2":
                balance = UTH_GUI.main(balance, user)
            elif choice == "3":
                balance = transfer_baccarat.play_game(balance, user)
            elif choice == "4":
                balance = Three_Card_Poker.main(balance, user)
            elif choice == "5":
                balance = Sicbo.main(user, balance)
            elif choice == "6":
                balance = Casino_Holdem.main(balance, user)
            elif choice == "7":
                balance = Caribbean_Stud_Poker.main(balance, user)
            else:
                print("无效选择，请输入1到6。")
                time.sleep(1.5)
            update_balance_in_json(user, balance)
        except ValueError:
            print("请输入一个有效的数字。")
            continue