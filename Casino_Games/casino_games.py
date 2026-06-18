import json
import os
import time
import sys
import re
import unicodedata

# 让本文件可直接运行时，也能找到上层项目路径
if __name__ == "__main__" and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

## Casino games import
## Poker
from Casino_Games import Caribbean_Stud_Poker
from Casino_Games import Casino_Holdem
from Casino_Games import Casino_War
from Casino_Games import DJ_Wild
from Casino_Games import Four_Card_Poker
from Casino_Games import Heads_Up_Holdem
from Casino_Games import I_Love_Flush
from Casino_Games import Let_It_Ride
from Casino_Games import Lunar_Poker
from Casino_Games import Mississippi_Stud_Poker
from Casino_Games import Pai_Gow_Poker
from Casino_Games import Super_In_Or_Out
from Casino_Games import Three_Card_Poker
from Casino_Games import Video_Poker
from Casino_Games import Ultimate_Texas_Holdem
from Casino_Games import Ultimate_Three_Card_Poker
from Casino_Games import Ultimate_Omaha_Holdem
from Casino_Games import Wild_Five_Card_Poker

## Baccarat (variant)
from Casino_Games import Baccarat
from Casino_Games import Dragon_Tiger
from Casino_Games import Dragon_Tiger_Phoenix

## Blackjack
from Casino_Games import Blackjack_Easy
from Casino_Games import Blackjack_Classic
from Casino_Games import Blackjack_Multiply
from Casino_Games import Blackjack_Spanish
from Casino_Games import Blackjack_Double_Up
from Casino_Games import Blackjack_Double
from Casino_Games import Blackjack_Premiere

## Dice
from Casino_Games import BacBo
from Casino_Games import Craps
from Casino_Games import Klondike_Dice
from Casino_Games import Sicbo

## Auto Deal and start
from Casino_Games import Auto_Stud_Poker
from Casino_Games import Auto_Texas_Holdem

## Wheel games
from Casino_Games import Big_Six_Wheel
from Casino_Games import Roulette_American
from Casino_Games import Roulette_Europe


def get_data_file_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')


def save_user_data(users):
    file_path = get_data_file_path()
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)


def load_user_data():
    file_path = get_data_file_path()
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def update_balance_in_json(username, new_balance):
    users = load_user_data()
    for user in users:
        if user['user_name'] == username:
            user['cash'] = f"{new_balance:.2f}"
            break
    save_user_data(users)


def display_width(s):
    width = 0
    for ch in s:
        ea = unicodedata.east_asian_width(ch)
        if ea in ('F', 'W'):  # Fullwidth, Wide
            width += 2
        elif ea in ('Na', 'H', 'N', 'A'):  # Narrow, Halfwidth, Neutral, Ambiguous
            width += 1
        else:
            width += 1
    return width


def pad_game_name(name, width, highlight=False):
    """将游戏名格式化为固定显示宽度，左对齐，可选高亮（反色）"""
    name_width = display_width(name)
    padding = ' ' * max(0, width - name_width)
    if highlight:
        return f"\033[7m{name}\033[0m{padding}"
    else:
        return name + padding


def display_menu(selected_global_row, selected_global_col, sections, global_rows, fixed_width):
    """显示分类菜单，选中项根据全局行列高亮，使用固定列宽，且所有分类标题行长度统一为最长的那个"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print(" 欢迎来到赌场中心!\n")
    print("请使用方向键选择游戏，回车确认(ESC返回主目录):\n")

    # 第一步：计算所有分类的最大总宽度
    interval = 2
    global_max_width = 0
    for section_title, rows in sections:
        if not rows:
            continue
        max_cols = max(len(row) for row in rows)
        total_width = max_cols * fixed_width + (max_cols - 1) * interval
        if total_width > global_max_width:
            global_max_width = total_width

    current_global_idx = 0

    for section_title, rows in sections:
        if not rows:
            continue

        max_cols = max(len(row) for row in rows)
        # 使用全局最大宽度来生成标题行
        title = section_title
        title_width = display_width(title)
        left_eq = max(0, (global_max_width - title_width) // 2)
        right_eq = max(0, global_max_width - title_width - left_eq)
        title_line = '=' * left_eq + title + '=' * right_eq
        print(title_line)

        for row in rows:
            line_parts = []
            for col in range(max_cols):
                if col < len(row):
                    game_name = row[col]
                    is_selected = (current_global_idx == selected_global_row and col == selected_global_col)
                else:
                    game_name = ""
                    is_selected = False
                part = pad_game_name(game_name, fixed_width, highlight=is_selected)
                line_parts.append(part)
            line = '  '.join(line_parts)
            print(line)
            current_global_idx += 1
        print()

def get_key():
    """跨平台获取键盘按键"""
    if os.name == 'nt':
        import msvcrt
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch()
                if key == b'\xe0':
                    key = msvcrt.getch()
                    if key == b'H':
                        return 'up'
                    elif key == b'P':
                        return 'down'
                    elif key == b'K':
                        return 'left'
                    elif key == b'M':
                        return 'right'
                elif key == b'\r':
                    return 'enter'
                elif key == b'\x1b':
                    return 'esc'
                elif key == b'0':
                    return '0'
                else:
                    return key
            time.sleep(0.05)
    else:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            if select.select([sys.stdin], [], [], 0.1)[0]:
                key = sys.stdin.read(1)
                if key == '\x1b':
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        rest = sys.stdin.read(2)
                        if rest == '[A':
                            return 'up'
                        elif rest == '[B':
                            return 'down'
                        elif rest == '[C':
                            return 'right'
                        elif rest == '[D':
                            return 'left'
                    else:
                        return 'esc'
                elif key == '\r':
                    return 'enter'
                elif key == '0':
                    return '0'
                else:
                    return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return None


def main(balance, user):
    # ========== 定义菜单结构（每行最多4个游戏） ==========
    sections = [
        ("扑克", [
            ["三张牌扑克", "视频扑克", "加勒比梭哈扑克", "月亮梭哈扑克"],
            ["四张牌扑克", "赌场扑克", "DJ Wild梭哈扑克", "密⻄⻄⽐梭哈撲克"],
            ["任逍遥扑克", "单挑扑克", "终极德州扑克", "终极奥马哈扑克"],
            ["超级内外住", "牌九扑克", "⺩牌五張撲克", "终极三张牌扑克"],
            ["赌场战争", "我爱同花"]
        ]),
        ("百家乐", [
            ["百家乐", "龙虎斗", "龙虎凤"]
        ]),
        ("21点", [
            ["简单21点", "经典21点", "西班牙式21點", "豪赢21点"],
            ["免牌加倍21点", "双向21点", "免牌加倍21点"]
        ]),
        ("骰子", [
            ["花旗骰", "克朗代克", "骰宝", "骰子百家乐"]
        ]),
        ("二人对决", [
            ["德州扑克双人对决", "梭哈扑克双人对决"]
        ]),
        ("轮盘赌", [
            ["美式轮盘", "欧式轮盘", "幸运之轮"]
        ]),
        ("退出游戏", [
            ["ESC 返回主目录"]
        ])
    ]

    # 构建游戏名称到 (ID, 函数) 的映射
    game_config = {
        "超级内外住": ("1", Super_In_Or_Out.main),
        "我爱同花": ("2", I_Love_Flush.main),
        "加勒比梭哈扑克": ("3", Caribbean_Stud_Poker.main),
        "三张牌扑克": ("4", Three_Card_Poker.main),
        "视频扑克": ("5", Video_Poker.main),
        "月亮梭哈扑克": ("6", Lunar_Poker.main),
        "四张牌扑克": ("7", Four_Card_Poker.main),
        "赌场扑克": ("8", Casino_Holdem.main),
        "终极奥马哈扑克": ("9", Ultimate_Omaha_Holdem.main),
        "任逍遥扑克": ("10", Let_It_Ride.main),
        "⺩牌五張撲克": ("11", Wild_Five_Card_Poker.main),
        "终极德州扑克": ("12", Ultimate_Texas_Holdem.main),
        "密⻄⻄⽐梭哈撲克": ("13", Mississippi_Stud_Poker.main),
        "赌场战争": ("14", Casino_War.main),
        "单挑扑克": ("15", Heads_Up_Holdem.main),
        "DJ Wild梭哈扑克": ("16", DJ_Wild.main),
        "终极三张牌扑克": ("17", Ultimate_Three_Card_Poker.main),
        "牌九扑克": ("36", Pai_Gow_Poker.main),

        "百家乐": ("18", Baccarat.main),
        "龙虎斗": ("19", Dragon_Tiger.main),
        "龙虎凤": ("20", Dragon_Tiger_Phoenix.main),

        "简单21点": ("21", Blackjack_Easy.main),
        "经典21点": ("22", Blackjack_Classic.main),
        "西班牙式21點": ("23", Blackjack_Spanish.main),
        "豪赢21点": ("24", Blackjack_Multiply.main),
        "无限加倍21点": ("25", Blackjack_Double_Up.main),
        "免牌加倍21点": ("26", Blackjack_Double.main),
        "双向21点": ("37", Blackjack_Premiere.main),

        "花旗骰": ("27", Craps.main),
        "克朗代克": ("28", Klondike_Dice.main),
        "骰宝": ("29", Sicbo.main),
        "骰子百家乐": ("30", BacBo.main),

        "德州扑克双人对决": ("31", Auto_Texas_Holdem.main),
        "梭哈扑克双人对决": ("32", Auto_Stud_Poker.main),

        "幸运之轮": ("33", Big_Six_Wheel.main),
        "美式轮盘":("34", Roulette_American.main),
        "欧式轮盘":("35", Roulette_Europe.main),

        "ESC 返回主目录": ("return", None)
    }

    # 构建全局游戏行列表
    global_rows = []
    for s_idx, (_, rows) in enumerate(sections):
        for r_idx, row in enumerate(rows):
            global_rows.append((s_idx, r_idx, row))

    # 计算所有游戏名的最大显示宽度，并取至少12
    all_game_names = [name for _, _, row in global_rows for name in row]
    max_width = max(display_width(name) for name in all_game_names)
    fixed_col_width = max(max_width, 12)

    total_game_rows = len(global_rows)
    selected_global_row = 0
    selected_global_col = 0

    while True:
        display_menu(selected_global_row, selected_global_col, sections, global_rows, fixed_col_width)

        key = get_key()

        if key == 'up':
            if selected_global_row == 0:
                selected_global_row = total_game_rows - 1
            else:
                selected_global_row -= 1
            _, _, row_games = global_rows[selected_global_row]
            selected_global_col = min(selected_global_col, len(row_games) - 1)

        elif key == 'down':
            if selected_global_row == total_game_rows - 1:
                selected_global_row = 0
            else:
                selected_global_row += 1
            _, _, row_games = global_rows[selected_global_row]
            selected_global_col = min(selected_global_col, len(row_games) - 1)

        elif key == 'left':
            if selected_global_col > 0:
                selected_global_col -= 1
            else:
                if selected_global_row > 0:
                    selected_global_row -= 1
                else:
                    selected_global_row = total_game_rows - 1
                _, _, row_games = global_rows[selected_global_row]
                selected_global_col = len(row_games) - 1

        elif key == 'right':
            _, _, row_games = global_rows[selected_global_row]
            max_col = len(row_games) - 1
            if selected_global_col < max_col:
                selected_global_col += 1
            else:
                if selected_global_row < total_game_rows - 1:
                    selected_global_row += 1
                else:
                    selected_global_row = 0
                selected_global_col = 0

        elif key == 'enter':
            _, _, row_games = global_rows[selected_global_row]
            game_name = row_games[selected_global_col]
            game_id, game_func = game_config[game_name]

            if game_id in ('27', '28'):
                from tkinter import messagebox
                messagebox.showinfo("维护通知", "本程式正在维护，请按下‘确认’退出")
                continue

            if game_id == 'return':
                return balance

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