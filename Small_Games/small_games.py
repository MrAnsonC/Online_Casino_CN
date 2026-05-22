import json
import os
import time
import sys
import unicodedata

# 让本文件可直接运行时，也能找到上层项目路径
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 只在 Unix-like 系统上导入这些模块
if os.name != 'nt':  # 不是 Windows 系统
    import select
    import termios
    import tty

## Small games import
from Small_Games import ChickenCrossing_tk
from Small_Games import tower
from Small_Games import keno
from Small_Games import rocket_GUI
from Small_Games import guess_number
from Small_Games import minus
from Small_Games import RPS
from Small_Games import plinko
from Small_Games import slot_machine
from Small_Games import Guess_color
from Small_Games import Thimbles
from Small_Games import lucky_num
from Small_Games import stock_market
from Small_Games import Shoot_Poker
from Small_Games import deal_or_no_deal

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

def display_width(s):
    width = 0
    for ch in s:
        ea = unicodedata.east_asian_width(ch)
        if ea in ('F', 'W'):  # Fullwidth, Wide
            width += 2
        elif ea in ('Na', 'H', 'N', 'A'):  # Narrow, Halfwidth, Neutral, Ambiguous
            # 对于 Ambiguous 通常按 1 处理（视终端而定）
            width += 1
        else:
            width += 1
    return width

def pad_game_name(name, width, highlight=False):
    """将游戏名格式化为固定显示宽度，左对齐，可选高亮（反色）"""
    name_width = display_width(name)
    padding = ' ' * (width - name_width)
    if highlight:
        # 反色显示
        return f"\033[7m{name}\033[0m{padding}"
    else:
        return name + padding

def display_menu(sections, selected_row, selected_col, fixed_width):
    """显示分类菜单，选中项根据全局行列高亮，使用固定列宽"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print(" 欢迎来到街机小游戏中心!\n")
    print("请使用方向键选择游戏，回车确认(ESC返回主目录):\n")

    current_global_idx = 0  # 当前输出的全局游戏行索引
    interval = 2  # 列之间的空格数

    for section_title, rows in sections:
        if not rows:
            continue

        # 该分类的最大列数
        max_cols = max(len(row) for row in rows)

        # 计算标题线的总宽度
        total_width = max_cols * fixed_width + (max_cols - 1) * interval

        # 生成标题线
        title = section_title
        title_width = display_width(title)
        left_eq = (total_width - title_width) // 2
        right_eq = total_width - title_width - left_eq
        title_line = '=' * left_eq + title + '=' * right_eq
        print(title_line)

        # 输出该分类下的所有游戏行
        for row in rows:
            line_parts = []
            for col in range(max_cols):
                if col < len(row):
                    game_name = row[col]
                    # 判断当前游戏是否为选中项
                    is_selected = (current_global_idx == selected_row and col == selected_col)
                else:
                    game_name = ""
                    is_selected = False
                # 格式化游戏名（固定宽度）
                part = pad_game_name(game_name, fixed_width, highlight=is_selected)
                line_parts.append(part)
            # 用两个空格连接各列
            line = '  '.join(line_parts)
            print(line)
            current_global_idx += 1
        print()  # 分类间空一行

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
    # ========== 定义菜单结构（分类 + 游戏行） ==========
    sections = [
        ("街机动作", [
            ["小鸡过马路", "上塔游戏", "飞天倍数"],
            ["扫雷"]
        ]),
        ("运气&博弈", [
            ["小钢珠跌落", "幸运数字", "猜颜色"],
            ["数字老虎机", "三杯球", "猜数字"],
            ["基诺", "剪刀石头布"]
        ]),
        ("模拟&策略", [
            ["股市大风云", "扑克足球", "成交与否"]
        ]),
        ("退出游戏", [
            ["Esc 返回主目录"]
        ])
    ]

    # ========== 游戏名称 -> (ID, 函数) 映射 ==========
    game_config = {
        "小鸡过马路": ("1", ChickenCrossing_tk.main),
        "上塔游戏": ("2", tower.main),
        "飞天倍数": ("3", rocket_GUI.main),
        "扫雷": ("4", minus.main),
        "小钢珠跌落": ("5", plinko.main),
        "幸运数字": ("6", lucky_num.main),
        "猜颜色": ("7", Guess_color.main),
        "数字老虎机": ("8", slot_machine.main),
        "三杯球": ("9", Thimbles.main),
        "猜数字": ("10", guess_number.main),
        "基诺": ("11", keno.main),
        "剪刀石头布": ("12", RPS.main),
        "股市大风云": ("13", stock_market.main),
        "扑克足球": ("14", Shoot_Poker.main),
        "成交与否": ("15", deal_or_no_deal.main),
        "Esc 返回主目录": ("return", None)
    }

    # ========== 构建全局平排行列表，用于导航 ==========
    # 每个元素格式: (section_index, row_index, game_names_list)
    global_rows = []
    for s_idx, (_, rows) in enumerate(sections):
        for r_idx, row in enumerate(rows):
            global_rows.append((s_idx, r_idx, row))

    total_game_rows = len(global_rows)       # 总游戏行数
    # 计算所有游戏名的最大显示宽度，并取至少12
    all_game_names = [name for _, _, row in global_rows for name in row]
    max_width = max(display_width(name) for name in all_game_names)
    fixed_col_width = max(max_width, 12)     # 固定列宽

    # 初始选中位置
    selected_row = 0
    selected_col = 0

    while True:
        # 显示菜单（根据分类 + 高亮选中项）
        display_menu(sections, selected_row, selected_col, fixed_col_width)

        key = get_key()

        # 上下左右移动逻辑（支持边界循环）
        if key == 'up':
            if selected_row == 0:
                selected_row = total_game_rows - 1
            else:
                selected_row -= 1
            # 修正列索引，防止超出新行的范围
            _, _, row_games = global_rows[selected_row]
            selected_col = min(selected_col, len(row_games) - 1)

        elif key == 'down':
            if selected_row == total_game_rows - 1:
                selected_row = 0
            else:
                selected_row += 1
            _, _, row_games = global_rows[selected_row]
            selected_col = min(selected_col, len(row_games) - 1)

        elif key == 'left':
            if selected_col > 0:
                selected_col -= 1
            else:
                # 移动到上一行的最右列
                if selected_row > 0:
                    selected_row -= 1
                else:
                    selected_row = total_game_rows - 1
                _, _, row_games = global_rows[selected_row]
                selected_col = len(row_games) - 1

        elif key == 'right':
            _, _, row_games = global_rows[selected_row]
            max_col = len(row_games) - 1
            if selected_col < max_col:
                selected_col += 1
            else:
                # 移动到下一行的最左列
                if selected_row < total_game_rows - 1:
                    selected_row += 1
                else:
                    selected_row = 0
                selected_col = 0

        elif key == 'enter':
            # 获取当前选中的游戏名称
            _, _, row_games = global_rows[selected_row]
            game_name = row_games[selected_col]
            game_id, game_func = game_config[game_name]

            # 如果是返回主目录
            if game_id == 'return':
                return balance

            # 运行游戏
            if game_func:
                try:
                    balance = game_func(balance, user)
                    update_balance_in_json(user, balance)
                except Exception as e:
                    print(f"游戏运行出错: {e}")
                    time.sleep(2)

        elif key == '0' or key == 'esc':
            return balance
        
def standalone_run_warning():
    from tkinter import messagebox
    messagebox.showinfo("提示", "本程式不能独立运作，请按下‘确认’退出")

if __name__ == "__main__":
    standalone_run_warning()