import json
import os
import time
import sys
import getpass  # 用于安全输入密码

# 只在 Unix-like 系统上导入这些模块
if os.name != 'nt':  # 不是 Windows 系统
    import select
    import termios
    import tty

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

def get_key():
    """跨平台获取键盘按键"""
    # Windows系统
    if os.name == 'nt':
        import msvcrt
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'\xe0':  # 扩展键（方向键）
                    key = msvcrt.getch()
                    if key == b'H': return 'up'
                    elif key == b'P': return 'down'
                    elif key == b'K': return 'left'
                    elif key == b'M': return 'right'
                elif key == b'\r':  # 回车键
                    return 'enter'
                elif key == b'\x1b':  # ESC键
                    return 'esc'
                elif key == b'0':
                    return '0'
                else:
                    return key
            time.sleep(0.05)  # 减少CPU占用
    
    # Unix-like系统 (Mac/Linux)
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            if select.select([sys.stdin], [], [], 0.1)[0]:
                key = sys.stdin.read(1)
                if key == '\x1b':  # 可能是方向键
                    # 读取接下来的字符
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        rest = sys.stdin.read(2)
                        if rest == '[A':  # 上箭头
                            return 'up'
                        elif rest == '[B':  # 下箭头
                            return 'down'
                        elif rest == '[C':  # 右箭头
                            return 'right'
                        elif rest == '[D':  # 左箭头
                            return 'left'
                    else:
                        return 'esc'  # ESC键
                elif key == '\r':  # 回车键
                    return 'enter'
                elif key == '0':
                    return '0'
                else:
                    return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None

def display_login_register_menu(selected_option):
    os.system('cls' if os.name == 'nt' else 'clear')
    print("欢迎来到游戏中心!\n")
    print("使用左右方向键选择，回车确认")
    print("\n请选择操作：")
    if selected_option == 0:
        print(">> 登录 <<       注册")
    else:
        print("   登录       >> 注册 <<")
    print("\n按0或ESC返回")

def display_main_menu(selected_row, selected_col):
    os.system('cls' if os.name == 'nt' else 'clear')
    print("欢迎来到游戏中心!\n")
    print("请选择游戏类别：")
    
    # 主菜单布局 - 更新为一行三个选项，第二行两个选项
    menu_layout = [
        ["赌场游戏", "刮刮乐", "街机小游戏"],    # 第一行
        ["账号服务", "登出"]                   # 第二行
    ]
    
    # 打印菜单
    for row_idx, row in enumerate(menu_layout):
        line = ""
        for col_idx, item in enumerate(row):
            if selected_row == row_idx and selected_col == col_idx:
                line += f">> {item} <<  "  # 高亮显示
            else:
                line += f"   {item}     "  # 普通显示
        print(line)
    
    print("\n按0或ESC返回")

# User login
def login():
    users = load_user_data()
    os.system('cls' if os.name == 'nt' else 'clear')

    # Track the attempted usernames
    attempted_usernames = []  # List to keep track of attempted usernames

    for attempt in range(3):  # Allow 3 attempts
        username = input("输入登录名称: ")
        # 使用 getpass 安全输入密码（不显示输入内容）
        password = getpass.getpass("输入你的密码: ")

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

def display_account_menu(selected_row, selected_col):
    os.system('cls' if os.name == 'nt' else 'clear')
    print("请选择账号服务：")
    
    # 账号服务菜单布局
    menu_layout = [
        ["查询余额", "充值"],     # 第一行
        ["更改密码", "提款"]      # 第二行
    ]
    
    # 打印菜单
    for row_idx, row in enumerate(menu_layout):
        line = ""
        for col_idx, item in enumerate(row):
            if selected_row == row_idx and selected_col == col_idx:
                line += f">> {item} <<  "  # 高亮显示
            else:
                line += f"   {item}     "  # 普通显示
        print(line)
    
    print("\n按0或ESC返回")

def account_services(user, users, balance):
    selected_row = 0
    selected_col = 0
    
    while True:
        display_account_menu(selected_row, selected_col)
        
        key = get_key()
        
        # 处理方向键
        if key == 'up':
            selected_row = max(0, selected_row - 1)
        elif key == 'down':
            selected_row = min(1, selected_row + 1)
        elif key == 'left':
            selected_col = max(0, selected_col - 1)
        elif key == 'right':
            selected_col = min(1, selected_col + 1)
        elif key == 'enter':
            # 第一行第一列：查询余额
            if selected_row == 0 and selected_col == 0:
                print(f"你最新的余额为:{balance:.2f}")
                time.sleep(3)
            # 第一行第二列：充值
            elif selected_row == 0 and selected_col == 1:
                recharge_amount = charge.main(user, 'charge')
                if recharge_amount is not None:
                    balance += float(recharge_amount)
                    print(f"充值成功！当前余额: {balance:.2f}")
                    time.sleep(3)
            # 第二行第一列：更改密码
            elif selected_row == 1 and selected_col == 0:
                while True:
                    password1 = getpass.getpass("\n请输入新密码: ")
                    password2 = getpass.getpass("请再次输入新密码: ")

                    if password1 != password2:
                        print("两次输入的密码不一致，请重试。")
                    else:
                        print("密码更改成功！")
                        user['password'] = password1
                        time.sleep(3)
                        break
            # 第二行第二列：提款
            elif selected_row == 1 and selected_col == 1:
                recharge_amount = charge.main(user, 'withdraw')
                if recharge_amount is not None:
                    balance -= float(recharge_amount)
                    print(f"提款成功！当前余额: {balance:.2f}")
                    time.sleep(3)
            
            # 更新用户余额
            user['cash'] = f"{balance:.2f}"
            save_user_data(users)
        elif key == '0' or key == 'esc':  # 0 或 ESC 键返回
            return balance, False
            
    return balance, False

def main():
    while True:
        # 登录/注册选择菜单
        selected_option = 0  # 0: 登录, 1: 注册
        login_register_choice = None
        
        while login_register_choice is None:
            display_login_register_menu(selected_option)
            key = get_key()
            
            if key == 'left':
                selected_option = 0
            elif key == 'right':
                selected_option = 1
            elif key == 'enter':
                login_register_choice = selected_option
            elif key == '0' or key == 'esc':
                return  # 退出程序
        
        if login_register_choice == 0:  # 登录
            user, users, username = login()
            if not user:
                continue  # 登录失败则重新开始
        else:  # 注册
            register.main()
            continue  # 注册后重新提示用户输入

        balance = float(user['cash']) if user['cash'] not in [None, "None"] else 0  # 确保余额为有效数字
        
        # 主菜单选择
        selected_row = 0
        selected_col = 0
        logout = False
        
        # 主菜单布局
        menu_layout = [
            ["赌场游戏", "刮刮乐", "街机小游戏"],    # 第一行
            ["账号服务", "登出"]                   # 第二行
        ]
        
        while not logout:
            display_main_menu(selected_row, selected_col)
            
            key = get_key()
            
            # 处理方向键
            if key == 'up':
                if selected_row == 0:  # 在第一行按上键
                    selected_row = 1  # 跳到第二行
                else:
                    selected_row -= 1
                # 确保列在有效范围内
                if selected_row == 0:  # 第一行最多三列
                    selected_col = min(selected_col, 2)
                else:  # 第二行最多二列
                    selected_col = min(selected_col, 1)
                    
            elif key == 'down':
                if selected_row == 1:  # 在第二行按下键
                    selected_row = 0  # 跳到第一行
                else:
                    selected_row += 1
                # 确保列在有效范围内
                if selected_row == 0:  # 第一行最多三列
                    selected_col = min(selected_col, 2)
                else:  # 第二行最多二列
                    selected_col = min(selected_col, 1)
                    
            elif key == 'left':
                if selected_col > 0:  # 同一行内向左移动
                    selected_col -= 1
                else:
                    # 移动到上一行的最后一个选项
                    if selected_row > 0:
                        selected_row -= 1
                        selected_col = len(menu_layout[selected_row]) - 1
                    else:  # 在第一行按左键
                        selected_row = 1  # 跳到最后一行
                        selected_col = 1  # 最后一行的最后一个选项
                        
            elif key == 'right':
                if selected_col < len(menu_layout[selected_row]) - 1:  # 同一行内向右移动
                    selected_col += 1
                else:
                    # 移动到下一行的第一个选项
                    if selected_row < len(menu_layout) - 1:
                        selected_row += 1
                        selected_col = 0
                    else:  # 在最后一行按右键
                        selected_row = 0  # 跳到第一行
                        selected_col = 0  # 第一行的第一个选项
                        
            elif key == 'enter':
                # 第一行第一列：赌场游戏
                if selected_row == 0 and selected_col == 0:
                    balance = casino_games.main(balance, username)
                # 第一行第二列：刮刮乐
                elif selected_row == 0 and selected_col == 1:
                    balance = lotto.main(balance, username)
                # 第一行第三列：街机小游戏
                elif selected_row == 0 and selected_col == 2:
                    balance = small_games.main(balance, username)
                # 第二行第一列：账号服务
                elif selected_row == 1 and selected_col == 0:
                    balance, logout = account_services(user, users, balance)
                # 第二行第二列：登出
                elif selected_row == 1 and selected_col == 1:
                    logout = True
            elif key == '0' or key == 'esc':  # 0 或 ESC 键返回
                logout = True
            
            # 更新用户余额
            if balance is None:  # 如果余额为 None，将其设置为 0
                balance = 0
            user['cash'] = f"{balance:.2f}"
            save_user_data(users)

        print("谢谢游玩！ ")
        print(f"你最新的余额为:{balance:.2f}")
        time.sleep(5)

if __name__ == '__main__':
    main()