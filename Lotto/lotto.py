import json
import os
import time
import sys

# 只在 Unix-like 系统上导入这些模块
if os.name != 'nt':  # 不是 Windows 系统
    import select
    import termios
    import tty

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

def display_menu(selected_row):
    # 定义游戏菜单布局（每行一个选项）
    menu_items = [
        "验钞机(1块/特易中奖)  - 大奖1000！",
        "高尔夫球(1块)       - 大奖10 000！",
        "过三关(1块)         - 大奖10 000！",
        "叠叠乐(5块)         - 大奖50 000！",
        "100X现金大挑战(5块) - 大奖50 000！",
        "返回主目录"
    ]
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print(" 欢迎来到刮刮卡中心!\n")
    print("请使用方向键选择游戏，回车确认(ESC返回主目录):\n")
    
    # 打印菜单，高亮显示选中的游戏
    for idx, item in enumerate(menu_items):
        if idx == selected_row:
            print(f">> {item} <<")  # 高亮显示选中的选项
        else:
            print(f"   {item}   ")
    print("\n")

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

def main(balance, user):
    # 初始选择位置 (第0行)
    selected_row = 0
    
    # 定义游戏映射
    game_map = {
        0: ('1', Banknote_Detection_gui.main),
        1: ('2', lambda bal, usr: run_golf_game(bal, usr)),
        2: ('3', pass_3_level_gui.main),
        3: ('4', stacked.main),
        4: ('5', num_gui.main),
        5: ('return', None)  # 返回主目录选项
    }
    
    # 高尔夫游戏的特殊处理函数
    def run_golf_game(bal, usr):
        root = Tk()
        game = golfs_gui.ScratchGame(root, bal, usr)  # 创建游戏实例
        root.mainloop()  # 运行游戏
        return game.balance  # 退出后获取余额
    
    while True:
        display_menu(selected_row)
        
        # 获取当前选择对应的游戏
        current_game = game_map.get(selected_row)
        
        # 获取按键
        key = get_key()
        
        # 处理方向键
        if key == 'up':
            selected_row = (selected_row - 1) % 6  # 循环选择，共6个选项
            
        elif key == 'down':
            selected_row = (selected_row + 1) % 6  # 循环选择，共6个选项
            
        elif key == 'left':
            selected_row = (selected_row - 1) % 6  # 左键等同于上键
            
        elif key == 'right':
            selected_row = (selected_row + 1) % 6  # 右键等同于下键
            
        # 处理回车键
        elif key == 'enter':
            if current_game and current_game[1]:
                try:
                    if selected_row == 1:  # 高尔夫球游戏特殊处理
                        balance = run_golf_game(balance, user)
                    else:
                        balance = current_game[1](balance, user)
                    update_balance_in_json(user, balance)
                except Exception as e:
                    print(f"游戏运行出错: {e}")
                    time.sleep(2)
            elif current_game and current_game[0] == 'return':
                return balance  # 返回主目录
                
        # 处理退出键
        elif key == '0' or key == 'esc':  # 0 或 ESC 键
            return balance