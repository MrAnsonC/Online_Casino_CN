import random
import os
import json
import time

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

# 概率分布（金额对应权重）
weights = {
    0: 480,
    5: 230,
    10: 230,
    20: 70,
    25: 60,
    40: 28,
    50: 17,
    100: 15,
    1000: 7,
    50000: 3
}

emoji = ["🏦", "💲", "🧧", "💰", "💵", "🪙"]

emojis = ["👛", "🤑", "💳", "🫰", "💎", "📒"]

def print_game_layout(number_user_input, rows):
    # Top line
    print("=" * 36)
    # Title section with extra play
    print("   ||                             ||")
    print("   ||   20  <  额外玩法 >   40    ||")
    if 0 in number_user_input:
        print(f"00 ||   {rows[0][0]} < 开中💵立刻赢 > {rows[0][1]}    ||")
    else:
        print("00 ||  🕳️  < 开中💵立刻赢 >  🕳️   ||")
    print("   ||                             ||")
    print("=" * 36)

    # Rows for holes and rewards
    for i in range(1, 11):  # 假设你有 10 行数据
        if i in number_user_input:
            print(f"{i:02} || {rows[i][0]}  {rows[i][1]}  {rows[i][2]}  {rows[i][3]}  {rows[i][4]} || {rows[i][5]} ||")
        else:
            print(f"{i:02} || 🕳️  🕳️  🕳️  🕳️  🕳️ ||  奖金 ||")
        if 1 != 11:
            print("=" * 36)

    # Footer
    print("=" * 20 + "Make=By=HSC" + "=" * 5)

# 1. 抽取中奖金额
def draw_amount():
    total_weight = sum(weights.values())
    rand_num = random.uniform(0, total_weight)
    cumulative_weight = 0
    for amount, weight in weights.items():
        cumulative_weight += weight
        if rand_num <= cumulative_weight:
            return amount

# 2. 抽取行数
def draw_row(amount):
    if amount == 0:
        return None  # 跳过行数选择
    elif amount in [20, 40]:
        return random.randint(0, 10)
    else:
        return random.randint(1, 10)

# 3. 生成含有 fixed_emoji 的行
def handle_fixed_emoji_row():
    fixed_emoji = random.choice(emojis)
    remaining_emojis = [e for e in emojis if e != fixed_emoji]

    # 构造固定行，fixed_emoji 出现3次
    row = [fixed_emoji, fixed_emoji, random.choice(remaining_emojis), fixed_emoji, random.choice(remaining_emojis)]
    random.shuffle(row)  # 随机打乱位置
    return row

# 4. 生成其余行的 emoji
def generate_emoji_row(row_index, allow_money=True):
    row = []
    emoji_source = emoji if row_index % 2 == 1 else emojis
    emoji_counts = {e: 0 for e in emoji_source}
    
    for i in range(5):
        while True:
            chosen_emoji = random.choice(emoji_source)
            if emoji_counts[chosen_emoji] < 2 and (allow_money or chosen_emoji != '💵'):
                row.append(chosen_emoji)
                emoji_counts[chosen_emoji] += 1
                break
    return row

# 5. 处理第0行的中奖
def handle_row_zero(amount, row_num):
    if amount == 20 and row_num == 0:
        # 金额为20，第一位是💵，第二位是随机emoji
        return ['💵', random.choice(emojis)]
    elif amount == 40 and row_num == 0:
        # 金额为40，第一位是随机emoji，第二位是💵
        return [random.choice(emojis), '💵']
    return [random.choice(emojis), random.choice(emojis)]

# 6. 生成完整的 emoji 行列，根据抽取的行数进行特殊处理
def generate_emoji_rows(row_num, amount):
    rows = []
    for i in range(11):  # 生成 11 行 (索引 0-9 对应 行数 1-10)
        if i == 0:  # 特殊处理第0行
            row = handle_row_zero(amount, row_num)
        elif i == row_num:
            row = handle_fixed_emoji_row()
            if amount == 5:
                row.append(" 5.00")
            elif amount == 10:
                row.append("10.00")
            elif amount == 20:
                row.append("20.00")
            elif amount == 25:
                row.append("25.00")
            elif amount == 40:
                row.append("40.00")
            elif amount == 50:
                row.append("50.00")
            elif amount == 100:
                row.append("  100")
            elif amount == 1000:
                row.append(" 1000")
            else:
                row.append(amount)
        else:
            row = generate_emoji_row(i)  # 普通生成其他行
            non_zero_weights = [k for k in weights.keys() if k != 0]
            weight = random.choice(non_zero_weights)
            if weight == 5:
                row.append(" 5.00")
            elif weight == 10:
                row.append("10.00")
            elif weight == 20:
                row.append("20.00")
            elif weight == 25:
                row.append("25.00")
            elif weight == 40:
                row.append("40.00")
            elif weight == 50:
                row.append("50.00")
            elif weight == 100:
                row.append("  100")
            elif weight == 1000:
                row.append(" 1000")
            else:
                row.append(weight)
        rows.append(row)
    return rows


# 7. 生成完整的抽奖逻辑
def main(balance, username):
    while balance > 0:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"当前余额：{balance:.2f}")
        try:
            bet_input = input("按'Enter'支付5块购买(输入0退出) ")
            if bet_input.lower() == "0":
                print("退出当前游戏，返回主菜单。")
                return balance 
            elif bet_input == "":
                balance -= 5
        except ValueError:
            print("请输入一个有效的数字。")
            continue
        os.system('cls' if os.name == 'nt' else 'clear')
        if username != "demo_player":
            update_balance_in_json(username, balance)
        amount = draw_amount()  # 步骤1: 抽取中奖金额

        if amount == 0:
            row_num = 0
            rows = generate_emoji_rows(row_num, amount)
            row_num = 10000000
        else:
            row_num = draw_row(amount)  # 步骤2: 抽取行数
            rows = generate_emoji_rows(row_num, amount)  # 步骤3: 生成所有行

        # 输出生成的 emoji 行
        listt = []
        while len(listt) != 11:
            try:
                os.system('cls' if os.name == 'nt' else 'clear')
                print("加载中...")
                time.sleep(0.1)
                os.system('cls' if os.name == 'nt' else 'clear')
                print("...你的刮刮卡...")
                print_game_layout(listt, rows)
                if row_num in listt:
                    print(f"你已经刮开赢奖图案！ 你赢了{amount}块!")
                else:
                    print("加油！ 大奖50 000是你的！")
                print("\n请输入0-10或按'Enter'自动刮开")
                list_input = input("请输入你要刮开的行数： ")
                if list_input == "":  # 如果用户没有输入，自动选择最小的未刮开的行
                    for i in range(11):
                        if i not in listt:
                            list_input = i
                            break
                list_input = int(list_input)
                if list_input not in listt and 0 <= list_input <= 10:
                    listt.append(list_input)
                else:
                    print("\n请输入有效的数字。")
                    time.sleep(2.5)
            
            except ValueError:
                print("请输入有效数字。")
                time.sleep(2.5)

        os.system('cls' if os.name == 'nt' else 'clear')
        print("加载中...")
        time.sleep(0.1)
        os.system('cls' if os.name == 'nt' else 'clear')
        print("...你的刮刮卡...")
        print_game_layout(listt, rows)
        if amount == 0:
            print("很抱歉 你输了")
            time.sleep(2.5)
        else:
            print(f"恭喜你 你赢了{amount}块！")
            balance += amount
            time.sleep(3.5)
        if username != "demo_player":
            update_balance_in_json(username, balance)
        
    time.sleep(2.5)
    print("感谢您的游玩！")
    return balance  # 返回更新后的余额

# 运行游戏
if __name__ == "__main__":
    main(100, "demo_player")