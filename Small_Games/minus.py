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

# 不同地雷数量对应的赔率
odds_dict = {
    1: [1, 1, 1.04, 1.09, 1.14, 1.20, 1.26, 1.33, 1.41, 1.50, 1.60, 1.71, 1.85, 2.00, 2.18, 2.40, 2.67, 3.00, 3.43, 4.00, 4.80, 6.00, 8.00, 12.00, 24.00],
    3: [1, 1.09, 1.25, 1.43, 1.66, 1.94, 2.28, 2.71, 3.25, 3.94, 4.85, 6.07, 7.72, 10.04, 13.38, 18.40, 26.29, 39.43, 63.09, 110.40, 220.80, 552.00, 2208.00],
    5: [1, 1.20, 1.52, 1.94, 2.51, 3.29, 4.39, 5.95, 8.24, 11.68, 16.98, 25.48, 39.63, 64.40, 110.40, 202.40, 404.80, 910.80, 2428.80, 8500.80, 51004.80],
    10: [1, 1.60, 2.74, 4.85, 8.90, 16.98, 33.97, 71.71, 161.35, 391.86, 1044.96, 3134.87, 10972.06, 47545.60, 285273.60, 3138009.60]
}

# 显示地雷板
def display_board(board):
    print("================================")
    for row in board:
        row_display = "|| " + " || ".join(row) + " ||"
        print(row_display)
        print("================================")

# 生成带有指定地雷数量的地雷板
def generate_board(mines_count, amount):
    board = [["空" for _ in range(5)] for _ in range(5)]
    if mines_count == 98789:
        print("进入手动输入模式，请输入地雷位置。")
        while True:
            positions = []
            amount = int(input("输入地雷数量： "))
            for i in range(amount):  # 允许用户输入5个地雷的位置
                try:
                    cell = int(input(f"请输入第 {i+1} 个地雷的位置 (1-25): "))
                    if cell < 1 or cell > 25:
                        print("无效的位置，请输入1到25之间的数字。")
                        continue
                    positions.append(cell)
                except ValueError:
                    print("请输入有效的数字。")
                    continue

            confirm = input(f"确认地雷位置为 {positions} 吗？(Y/N): ").strip().lower()
            if confirm == 'y':
                break
            else:
                print("请重新输入地雷位置。")

        # 将用户输入的位置转换为炸弹位置
        for pos in positions:
            row, col = divmod(pos - 1, 5)  # 将用户输入的1-25映射到5x5的二维数组
            board[row][col] = "💣"
        return board, amount
    else:
        positions = random.sample(range(25), mines_count)
        for pos in positions:
            row, col = divmod(pos, 5)
            board[row][col] = "💣"
        return board, amount

# 选择格子并揭示内容
def reveal_cell(board, cell):
    row, col = divmod(cell - 1, 5)
    return board[row][col]

# 主函数
def main(balance, username):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(" 扫雷游戏")
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
                print("\n地雷可选数量： 1、3、5、10 ")
                mines_count = int(input("输入地雷数量:  "))
                
                # Validate mines count
                if mines_count in [1, 3, 5, 10, 98789]:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    break  # Valid input, exit the loop
                else:
                    print("无效的地雷数量，请重新输入！")
                    time.sleep(2)
            except ValueError:
                print("请输入一个有效的数字。")
                time.sleep(2)
                continue

        # 初始化游戏板
        board, mines_count = generate_board(mines_count, mines_count)
        
        # 初始化带编号的数字板
        number_board = [[f"{i + 1:02}" for i in range(j * 5, j * 5 + 5)] for j in range(5)]
        
        display_board(number_board)  # 显示数字板
        print("欢迎游玩扫雷！ 祝你好运！")
        odds_index = 0
        odds = odds_dict[mines_count][odds_index]  # 初始赔率

        allow_cash_out = False
        revealed_cells = set()  # 已揭示的格子集合
        while True:
            next_odd = odds_dict[mines_count][odds_index + 1] if odds_index + 1 < len(odds_dict[mines_count]) else odds_dict[mines_count][-1]
            print(f"\n下一个💎： {next_odd:.2f}")
            
            try:
                cell = input("请选择您要打开的格子: ")

                if allow_cash_out:
                    if cell == "":
                        for r in range(5):
                            for c in range(5):
                                if board[r][c] == "💣":
                                    number_board[r][c] = "💣"  # 显示所有地雷
                                elif number_board[r][c] != "💎":
                                    number_board[r][c] = "💎"  # 显示未揭示的格子为💎
                        os.system('cls' if os.name == 'nt' else 'clear')
                        display_board(number_board)
                        print(f"\n您兑现了{bet_input * odds}!")
                        bet_input = bet_input * odds
                        break

                cell = int(cell)
            except ValueError:
                print("请输入一个有效的数字。")
                time.sleep(2)
                os.system('cls' if os.name == 'nt' else 'clear')
                display_board(number_board)
                continue

            if 1 <= cell <= 25:
                os.system('cls' if os.name == 'nt' else 'clear')
                if cell in revealed_cells:  
                    display_board(number_board)
                    print("您已经选择过这个格子，请重新选择。")
                    continue  # 已经选择过，重新选择

                result = reveal_cell(board, cell)

                if result == "💣":
                    # 显示地雷并揭示全局
                    for r in range(5):
                        for c in range(5):
                            if board[r][c] == "💣":
                                number_board[r][c] = "💣"
                            elif number_board[r][c] != "💎":
                                number_board[r][c] = "💎"
                    display_board(number_board)
                    print("💣已激活！")
                    bet_input = 0
                    break
                else:
                    revealed_cells.add(cell)
                    number_board[(cell - 1) // 5][(cell - 1) % 5] = "💎"  # 显示💎
                    odds_index += 1
                    if odds_index < len(odds_dict[mines_count]):
                        odds = odds_dict[mines_count][odds_index]
                    else:
                        odds = odds_dict[mines_count][-1]

                    display_board(number_board)

                    if len(revealed_cells) + mines_count != 25:
                        print(f"按“Enter”兑现： {odds:.2f}")
                        allow_cash_out = True
                    else:
                        print(f"扫雷成功！ 你赢了： {bet_input * odds}")
                        bet_input = bet_input * odds
                        break
            else:
                os.system('cls' if os.name == 'nt' else 'clear')
                display_board(number_board)
                print("\n无效的格子！请重新选择。")


        balance += bet_input
        if username != "demo_player":
            update_balance_in_json(username, balance)
        time.sleep(2.5)

if __name__ == "__main__":
    main(100, "demo_player")
