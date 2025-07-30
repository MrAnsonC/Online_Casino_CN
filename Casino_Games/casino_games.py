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

def get_display_width(text):
    """计算文本的显示宽度（考虑中文字符）"""
    width = 0
    for char in text:
        # 中文字符占2个宽度，其他占1个
        if '\u4e00' <= char <= '\u9fff':
            width += 2
        else:
            width += 1
    return width

def display_menu(selected_index):
    # 定义游戏菜单项
    menu_items = [
        "德州扑克双人对决", "百家乐",
        "加勒比梭哈扑克", "花旗骰",
        "终极德州扑克", "视频扑克",
        "法罗（变种）", "赌场扑克",
        "三张牌扑克", "高牌同花",
        "21点", "骰宝",
        "返回主目录"
    ]
    
    os.system('cls' if os.name == 'nt' else 'clear')
    print("欢迎来到赌场!")
    print("请使用方向键选择游戏，回车确认(ESC返回主目录):\n")
    
    # 计算最大宽度（包括选中状态）
    max_item_width = 0
    for item in menu_items:
        # 计算选中状态时的最大宽度
        selected_width = get_display_width(f">> {item} <<")
        if selected_width > max_item_width:
            max_item_width = selected_width
    
    # 每行显示2个项目
    for i in range(0, len(menu_items), 2):
        line = ""
        for j in range(2):
            idx = i + j
            if idx < len(menu_items):
                item = menu_items[idx]
                
                # 创建显示文本（选中或未选中）
                if idx == selected_index:
                    display_text = f">> {item} <<"
                else:
                    display_text = f"   {item}   "
                
                # 计算当前文本宽度
                current_width = get_display_width(display_text)
                
                # 添加填充空格使所有项目等宽
                padding = max_item_width - current_width
                display_text += ' ' * padding
                
                line += display_text
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
                else:
                    return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None

def main(balance, user):
    # 定义游戏菜单项和对应的函数
    menu_items = [
        ("德州扑克双人对决", lambda: auto_th.main(balance, user)),
        ("百家乐", lambda: transfer_baccarat.play_game(balance, user)),
        ("加勒比梭哈扑克", lambda: Caribbean_Stud_Poker.main(balance, user)),
        ("花旗骰", lambda: craps.main(user, balance)),
        ("终极德州扑克", lambda: UTH_GUI.main(balance, user)),
        ("视频扑克", lambda: Video_Poker.main(balance, user)),
        ("法罗（变种）", lambda: Faro_match.main(balance, user)),
        ("赌场扑克", lambda: Casino_Holdem.main(balance, user)),
        ("三张牌扑克", lambda: Three_Card_Poker.main(balance, user)),
        ("高牌同花", lambda: flush.main(balance, user)),
        ("21点", lambda: Blackjack.main(balance, user)),
        ("骰宝", lambda: Sicbo.main(user, balance)),
        ("返回主目录", None)
    ]
    
    selected_index = 0
    total_items = len(menu_items)
    
    while True:
        display_menu(selected_index)
        
        key = get_key()
        
        if key == 'up':
            # 向上移动一行（2个位置）
            selected_index = max(0, selected_index - 2)
        elif key == 'down':
            # 向下移动一行（2个位置）
            selected_index = min(total_items - 1, selected_index + 2)
            # 如果到达最后一行且是奇数位置，调整到最后一个有效位置
            if selected_index == total_items - 2 and total_items % 2 == 1:
                selected_index = total_items - 1
        elif key == 'left':
            # 向左移动一个位置（如果可能）
            if selected_index % 2 == 1:  # 当前在右侧
                selected_index -= 1
        elif key == 'right':
            # 向右移动一个位置（如果可能）
            if selected_index % 2 == 0 and selected_index + 1 < total_items:  # 当前在左侧且有右侧项
                selected_index += 1
        elif key == 'enter':
            item_name, action = menu_items[selected_index]
            if action:
                try:
                    if item_name == "返回主目录":
                        return balance
                    new_balance = action()
                    if new_balance is not None:
                        balance = new_balance
                        update_balance_in_json(user, balance)
                except Exception as e:
                    print(f"游戏运行出错: {e}")
                    time.sleep(2)
            else:
                return balance  # 返回主目录
        elif key == 'esc':
            return balance