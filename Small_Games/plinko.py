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

# 定义挡板形状
def print_board(ball_pos=None, payout = None):
    os.system('cls' if os.name == 'nt' else 'clear')
    
    board = [
        "                 ||                        ||",
        "                //  ^  ^  ^  ^  ^  ^  ^  ^  \\\\",
        "               //  ^  ^  ^  ^  ^  ^  ^  ^  ^ \\\\",
        "              //  ^  ^  ^  ^  ^  ^  ^  ^  ^  /\\\\",
        "             //  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  \\\\",
        "            //  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^   /\\\\",
        "           //  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^   \\\\",
        "          //\   ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^   \\\\",
        "         //   ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^   \\\\",
        "        //  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^   \\\\",
        "       //  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  \\\\",
        "      //  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^  ^   /\\\\",
        "      ||\    ^    ^    ^    ^    ^    ^    ^    ^    /||",
        "      ||     |    |    |    |    |    |    |    |     ||",
        "      =================================================="
    ]

    if payout:
        payout_str = "|".join([f"{p:.1f}" if p >= 10 else f"{p:.2f}" for p in payout])
        board.append(f"      || {payout_str.ljust(42)} ||")

    # 打印游戏板，并在特定位置打印弹珠
    for i, line in enumerate(board):
        if ball_pos and i == ball_pos[0]:
            line = list(line)
            line[ball_pos[1]] = '⊙'  # 将弹珠放置在当前位置
            print("".join(line))
        else:
            print(line)

    return board  # 返回 board 数组以便在其他地方获取其长度

# 初始化弹珠位置（在第0行的||和||之间随机掉落）
def get_random_start(board):
    valid_cols = []
    
    # 第 0 行的有效位置在 '||' 之间
    top_row = board[0]
    for col in range(18, 43):  # 限制在 || 和 || 之间的范围
        if top_row[col] == ' ':  # 空白区域是有效的起始位置
            valid_cols.append(col)
    
    return 0, random.choice(valid_cols)  # 返回随机起点（行, 列）

def get_payout(previous_choice):
    if previous_choice == 3:
        return [29, 4, 1.5, 0.3, 0.2, 0.3, 1.5, 4, 29]
    elif previous_choice == 2:
        return [13, 3, 1.3, 0.7, 0.4, 0.7, 1.3, 3, 13]
    elif previous_choice == 1:
        return [5.6, 2.1, 1.1, 1, 0.5, 1, 1.1, 2.1, 5.6]
    else:
        raise ValueError("无效的选择")

# 主游戏函数
def main(balance, username):
    previous_choice = None
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(" 小钢珠跌落")
        print(f"\n当前余额：{balance:.2f}")
        try:
            if previous_choice != None:
                print("\n不输入任何东西以更改风险")
            bet_input = input("输入您的下注金额(0退出)：")
            if bet_input == "0":
                print("退出当前游戏，返回主菜单。")
                time.sleep(2.5)
                return balance
            elif bet_input == "":
                previous_choice = None
                continue
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

        if previous_choice is None:
            print("\n ① 低风险  ② 中风险 ③ 高风险")
            try:
                previous_choice = int(input("输入您的下注风险："))
                if previous_choice not in [1, 2, 3]:
                    print("输入无效 请输入1/2/3。")
                    continue
            except ValueError:
                print("请输入一个有效的数字。")
                time.sleep(2)
                continue

        # 初始化
        payout = get_payout(previous_choice)
        board = print_board()
        ball_row, ball_col = get_random_start(board)
        max_col = len(board[0])

        # 游戏循环 - 弹珠下落过程
        while ball_row < 13:  # 弹珠还没有到最底部
            print_board((ball_row, ball_col), payout)  # 打印当前板子和弹珠位置
            time.sleep(0.15)  # 每0.15秒更新一次
            
            if ball_row < 12:
                direction = random.choice([-3, 3])  # 左移或右移
                next_col = max(0, min(ball_col + direction, max_col - 1))
                
                if board[ball_row + 1][next_col] not in ['^', '/', '\\']:
                    ball_col = next_col
                
                ball_row += 1  # 弹珠下落一行
            else:
                ball_row += 1

        print_board((ball_row, ball_col), payout)
        ball_col += 1

        # 奖励计算（简单逻辑）
        if ball_col <= 14:
            slot = 0
        elif ball_col <= 19:
            slot = 1
        elif ball_col <= 24:
            slot = 2
        elif ball_col <= 29:
            slot = 3
        elif ball_col <= 34:
            slot = 4
        elif ball_col <= 39:
            slot = 3
        elif ball_col <= 44:
            slot = 2
        elif ball_col <= 49:
            slot = 1
        elif ball_col <= 55:
            slot = 0
        else:
            slot = None
            print("Error")

        if 0 <= slot < len(payout):
            winnings = bet_input * payout[slot]
            balance += winnings
            if winnings > bet_input:
                print(f"\n您赢了{winnings:.2f}块！")
            elif winnings == bet_input:
                print("\n和局！")
            else:
                print("\n下次加油")
        else:
            print("弹珠落在无效区域，未赢得任何奖金。")
        
        if username != "demo_player":
            update_balance_in_json(username, balance)

        time.sleep(3)

# 开始游戏
if __name__ == "__main__":
    main(100, "demo_player")
