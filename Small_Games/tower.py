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

# 定义赔率和骷髅的分布
odds = {
    "1": [1.28, 1.64, 2.10, 2.68, 3.44, 4.40, 5.63, 7.21],  # 入门赔率
    "2": [1.44, 2.07, 2.99, 4.30, 6.19, 8.92, 12.84, 18.49],  # 简单赔率
    "3": [1.92, 3.69, 7.08, 13.59, 26.09, 50.10, 96.19, 184.68],  # 中等赔率
    "4": [2.88, 8.29, 23.89, 68.80, 198.14, 570.63, 1643.42, 4733.04],  # 困难赔率
    "5": [3.84, 14.75, 56.62, 217.43, 834.94, 3206.18, 12311.72, 47276.99],  # 地狱赔率
}

# 定义每行骷髅的数量
skull_distribution = {
    "1": (1, 3),  # 入门：1个骷髅，3个宝石
    "2": (1, 2),  # 简单：1个骷髅，2个宝石
    "3": (1, 1),  # 中等：1个骷髅，1个宝石
    "4": (2, 1),  # 困难：2个骷髅，1个宝石
    "5": (3, 1),  # 地狱：3个骷髅，1个宝石
}

def display_board(difficulty, hidden=True, board=None, revealed_rows=None, failed_row=None, failed_choice=None):
    if board is None:  # 确保board不为None
        print("错误：游戏板未初始化！")
        return
    
    if revealed_rows is None:  # 确保revealed_rows不为None
        revealed_rows = []

    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 33)
    for i in range(len(board)-1 , -1, -1):  # 动态行数
        row = f"{i + 1} "
        for j in range(len(board[i])):  # 动态列数
            if hidden and (i, j) not in revealed_rows:  # 只显示已经揭示的正确宝石
                row += "| ❓ "  # 隐藏未揭示的行和位置
            else:
                if (i, j) in revealed_rows:  # 显示玩家揭示的宝石
                    row += "| 💎 "
                else:
                    # 如果当前行是失败的行，显示“💥”，否则显示骷髅或安全位置
                    if failed_row is not None and i == failed_row:
                        row += "| 💥 " if j == failed_choice else "| 💀 " if board[i][j] == "☠" else "| 💰 "
                    else:
                        row += "| 💀 " if board[i][j] == "☠" else "| 💰 "  # 显示骷髅或安全位置
        print(row + f"| X{odds[difficulty][i]:.2f}")  # 打印赔率
        print("=" * 33)
    if len(board[i]) ==  4:
        print("行|  1 |  2 |  3 |  4 | 赔率")
    elif len(board[i]) == 3:
        print("行|  1 |  2 |  3 | 赔率")
    else:
        print("行|  1 |  2 | 赔率")


def generate_board(difficulty):
    # 生成游戏板，每行根据骷髅的数量来设置骷髅和宝石
    board = []

    skull_count, gem_count = skull_distribution[difficulty]  # 根据难度获取骷髅和宝石的数量

    for _ in range(8):  # 生成8行
        row = ["💎"] * gem_count + ["☠"] * skull_count  # 创建包含骷髅和宝石的行
        random.shuffle(row)  # 随机打乱行中的元素
        board.append(row)

    return board

def game_round(difficulty, bet_amount, balance):
    board = generate_board(difficulty)
    revealed_rows = []  # 记录玩家成功揭示的行
    max_columns = len(board[0])

    for round_num in range(8):
        display_board(difficulty, hidden=True, board=board, revealed_rows=revealed_rows)

        while True:
            if round_num == 0:
                user_choice = input(f"\n选择 1 到 {max_columns} : ")
            else:
                user_choice = input(f"\n选择 1 到 {max_columns} (5 结束游戏): ")

            if user_choice == '98789':
                if round_num < len(board):
                    next_row_skeletons = [index + 1 for index, cell in enumerate(board[round_num]) if cell == "☠"]
                    if next_row_skeletons:
                        print(f"\n下一行骷髅的位置：{next_row_skeletons}\n")
                    else:
                        print("下一行没有骷髅！")
                else:
                    print("已经是最后一行，无法显示下一行骷髅。")
                continue  # 再次提示玩家输入选择
            
            if user_choice == '5' and round_num != 0:
                print("游戏结束。")
                if revealed_rows:
                    # 获取最后揭示行的赔率
                    last_revealed_row = revealed_rows[-1][0]  # 获取最后揭示行的索引
                    odds_multiplier = odds[difficulty][last_revealed_row]
                    win_amount = bet_amount * odds_multiplier
                    balance += win_amount
                display_board(difficulty, hidden=False, board=board, revealed_rows=revealed_rows)
                print(f"\n你赢了：{win_amount:.2f}!!\n\n")
                time.sleep(3)
                return balance  # 返回更新后的余额
            elif user_choice.isdigit() and 1 <= int(user_choice) <= max_columns:
                user_choice = int(user_choice)
                time.sleep(1)
                break
            else:
                print(f"输入无效，请选择 1 到 {max_columns} 之间的数字。\n")
                
        if board[round_num][user_choice - 1] == "☠":
            print("\n失败！")
            failed_choice = user_choice - 1  # 记录失败的选择
            board[round_num][user_choice - 1] = "💀"
            display_board(difficulty, hidden=False, board=board, revealed_rows=revealed_rows, failed_row=round_num, failed_choice=failed_choice)
            time.sleep(3)
            return balance

        print("\n没问题！")
        revealed_rows.append((round_num, user_choice - 1))  # 记录成功的选择

    # 全部顺利通过，赢得赌注*赔率
    win_amount = int(bet_amount * odds[difficulty][-1])
    display_board(difficulty, hidden=False, board=board, revealed_rows=revealed_rows)
    print(f"\n你赢了：{win_amount:.2f}!!\n\n")
    time.sleep(3)
    return balance + win_amount

def main(balance, username):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(" 上塔游戏")
        print(f"\n当前余额：{balance:.2f}")
        try:
            bet_input = input("输入您的下注金额(0退出)：")
            if bet_input.lower() == "0":
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

        print("\n①入门 ②简单 ③中等 ④困难 ⑤地狱")
        difficulty = input("请选择难度：")

        if difficulty not in ["1", "2", "3", "4", "5"]:
            print("无效选择，请重新选择难度。")
            continue

        balance = game_round(difficulty, bet_input, balance)
        if username != "demo_player":
            update_balance_in_json(username, balance)

        if balance <= 0:
            print("你已经输光了本金，游戏结束。")
            return balance

if __name__ == "__main__":
    main(100, "demo_player")