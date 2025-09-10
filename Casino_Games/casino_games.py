import json
import os
import time
import sys

# 只在 Unix-like 系统上导入这些模块
if os.name != 'nt':  # 不是 Windows 系统
    import select
    import termios
    import tty

## Poker games import
from Casino_Games import Blackjack
from Casino_Games import UTH_GUI
from Casino_Games import transfer_baccarat
from Casino_Games import Three_Card_Poker
from Casino_Games import Sicbo
from Casino_Games import Casino_Holdem
from Casino_Games import Caribbean_Stud_Poker
from Casino_Games import auto_th
from Casino_Games import Video_Poker
from Casino_Games import Faro_match
from Casino_Games import craps
from Casino_Games import flush
from Casino_Games import EZ_21
from Casino_Games import Let_It_Ride
from Casino_Games import Klondike_Dice
from Casino_Games import Wild_Five_Card_poker

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

def display_menu(selected_row, selected_col):
    # 定义游戏菜单布局（每行3个，选项间2个空格分隔）
    menu_layout = [
        ["法罗(变种)", "高牌同花", "德州扑克双人对决"],
        ["三张牌扑克", "视频扑克", "加勒比梭哈扑克"],
        ["任逍遥扑克", "赌场扑克", "终极德州扑克"],
        ["简单21点  ", "21点    ", "百家乐"],
        ["⺩五張撲克"],
        ["花旗骰    ", "克朗代克", "骰宝"],
        ["返回主目录", "", ""]  # 新增返回选项
    ]
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print(" 欢迎来到街机小游戏中心!\n")
    print("请使用方向键选择游戏，回车确认(ESC返回主目录):\n")
    
    # 打印菜单，高亮显示选中的游戏
    for row_idx, row in enumerate(menu_layout):
        line = ""
        for col_idx, game in enumerate(row):
            if game:  # 跳过空项
                if row_idx == selected_row and col_idx == selected_col:
                    # 高亮显示选中的游戏
                    line += f">> {game} <<  "  # 选项间2个空格
                else:
                    line += f"   {game}     "  # 选项间2个空格
            else:
                line += " " * 12  # 空项占位
        print(line)
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
    # 初始选择位置 (第0行，第0列)
    selected_row = 0
    selected_col = 0
    
    # 定义游戏映射
    game_map = {
        (0, 0): ('1', Faro_match.main),
        (0, 1): ('2', flush.main),
        (0, 2): ('3', auto_th.main),
        (1, 0): ('4', Three_Card_Poker.main),
        (1, 1): ('5', Video_Poker.main),
        (1, 2): ('6', Caribbean_Stud_Poker.main),
        (2, 0): ('7', Let_It_Ride.main),
        (2, 1): ('8', Casino_Holdem.main),
        (2, 2): ('9', UTH_GUI.main),
        (3, 0): ('10', EZ_21.main),
        (3, 1): ('11', Blackjack.main),
        (3, 2): ('12', transfer_baccarat.play_game),
        (4, 0): ('13', Wild_Five_Card_poker.main),
        (5, 0): ('14', craps.main),
        (5, 1): ('15', Klondike_Dice.main),
        (5, 2): ('16', Sicbo.main),
        (6, 0): ('return', None)  # 返回主目录选项
    }
    
    # 定义每行的列数
    row_cols = [3, 3, 3, 3, 1, 3, 1]  # 每行的列数
    
    while True:
        display_menu(selected_row, selected_col)
        
        # 获取当前选择对应的游戏
        current_game = game_map.get((selected_row, selected_col))
        
        # 获取按键
        key = get_key()
        
        # 处理方向键
        if key == 'up':
            if selected_row == 0:  # 在第一行按上键
                selected_row = 6  # 跳到最后一行
            else:
                selected_row -= 1
            # 确保列在有效范围内
            selected_col = min(selected_col, row_cols[selected_row] - 1)
            
        elif key == 'down':
            if selected_row == 6:  # 在最后一行按下键
                selected_row = 0  # 跳到第一行
            else:
                selected_row += 1
            # 确保列在有效范围内
            selected_col = min(selected_col, row_cols[selected_row] - 1)
            
        elif key == 'left':
            if selected_col > 0:  # 同一行内向左移动
                selected_col -= 1
            else:
                # 移动到上一行的最后一个选项
                if selected_row > 0:
                    selected_row -= 1
                    selected_col = row_cols[selected_row] - 1
                else:  # 在第一行按左键
                    selected_row = 6  # 跳到最后一行
                    selected_col = 0  # 最后一行的第一个选项
                    
        elif key == 'right':
            if selected_col < row_cols[selected_row] - 1:  # 同一行内向右移动
                selected_col += 1
            else:
                # 移动到下一行的第一个选项
                if selected_row < 6:
                    selected_row += 1
                    selected_col = 0
                else:  # 在最后一行按右键
                    selected_row = 0  # 跳到第一行
                    selected_col = 0  # 第一行的第一个选项
                    
        # 处理回车键
        elif key == 'enter':
            if current_game and current_game[0] == '14' or current_game and current_game[0] == '15':
                print("维护中 请稍后再试")
                time.sleep(2)
                continue
            if current_game and current_game[1]:
                try:
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