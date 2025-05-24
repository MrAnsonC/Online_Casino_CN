import random
import json
import os
import time
from collections import Counter
from itertools import combinations
from datetime import datetime

def write_uth_log(
    username, win_lost_amount, participate_jackpot, 
    dealer_hole, community, player_hole,
    dealer_best, dealer_eval, player_best, player_eval, 
    initial_funds, jackpot_amount, 
    play, ante, blind, trips, jp_win
):
    # 确保log目录存在
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log')
    log_path = os.path.join(log_dir, 'uth_log.txt')

    # 创建目录（如果不存在）
    try:
        os.makedirs(log_dir, exist_ok=True)  # exist_ok=True 表示目录存在时不报错
    except Exception as e:
        print(f"|| 创建日志目录失败: {e}")
        return
    
    # 格式化牌面显示
    dealer_cards = " ".join(map(str, dealer_hole))
    community_cards = " ".join(map(str, community))
    player_cards = " ".join(map(str, player_hole))
    
    # 格式化最佳手牌
    dealer_hand_str = f"{format_hand(dealer_best, dealer_eval)}  <{HAND_RANK_NAMES[dealer_eval[0]]}>"
    player_hand_str = f"{format_hand(player_best, player_eval)}  <{HAND_RANK_NAMES[player_eval[0]]}>"
    
    # 时间格式化（强制英文月份）
    now = datetime.now()
    date_str = now.strftime("%d of %B, %Y. %H:%M:%S")

    if participate_jackpot:
        win_lost_amount -= 2.5
    
    # 构建日志内容
    log_lines = [
        f"User: {username}",
        f"Funds: {initial_funds:.2f}",  # 使用initial_funds而非未定义的funds变量
        "=== Bet 下注 ===",
        f"Play: {play}",
        f"Ante/Blind: {ante}",  # 根据实际变量调整
        f"Trips: {trips}",
        f'Jackpot: {participate_jackpot} "MAX: {jackpot_amount:.2f}"',
        f"Total_bet: {play + ante*2 + trips + (2.5 if participate_jackpot else 0):.2f}",
        "=== Card 卡牌 ===",
        f"Dealer Card: {dealer_cards}",
        f"Community: {community_cards}",
        f"Player Card: {player_cards}",
        "=== Best 5 组合 ===",
        f"Dealer: {dealer_hand_str}",
        f"Player: {player_hand_str}",
        "=== Win / Lost ===",
        f"{'Win' if win_lost_amount >=0 else 'Lost'}: {abs(win_lost_amount):.2f}",
    ]
    if jp_win != 0:
        log_lines.append(f"Jackpot win: {jp_win}")
        log_lines.append(f">>Total win: {jp_win + win_lost_amount}")

    log_lines += [
        f"Date and Time: {date_str}",
        "====================\n"
    ]
    
    try:
        # 读取现有内容并分割成条目列表（按分隔符）
        existing_entries = []
        if os.path.exists(log_path):
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    # 按完整分隔符分割条目（注意分隔符末尾的换行）
                    existing_entries = content.split('\n====================\n')

        # 插入新日志到列表开头（确保最新日志在最上面）
        new_entry = '\n'.join(log_lines)
        existing_entries.insert(0, new_entry)  # 插入到第一个位置

        # 限制最多保留20条记录（超过时删除最旧的最后一条）
        if len(existing_entries) > 20:
            existing_entries = existing_entries[:60]  # 保留前30条

        # 重新组合内容（每个条目后添加分隔符）
        updated_content = '\n====================\n'.join(existing_entries) + '\n====================\n'

        # 写入文件
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)

    except Exception as e:
        print(f"|| 日志写入失败: {e}")
    
def get_data_file_path():
    # 用于获取保存数据的文件路径
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), '../saving_data.json')

# Jackpot 文件加载与保存
def load_jackpot():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    default_jackpot = 197301.26
    # 文件不存在时使用默认奖池
    if not os.path.exists(path):
        return True, default_jackpot
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if item.get('Games') == 'UTH':
                    return False, float(item.get('Jackpok', default_jackpot))
    except Exception:
        return True, default_jackpot
    # 未找到 UTH 条目时也使用默认
    return True, default_jackpot

def save_jackpot(amount):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    # 尝试读取现有数据，保留其他游戏的条目
    data = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            data = []
    # 更新或新增 UTH 条目
    found = False
    for item in data:
        if item.get('Games') == 'UTH':
            item['Jackpok'] = f"{amount:.2f}"
            found = True
            break
    if not found:
        data.append({"Games": "UTH", "Jackpok": f"{amount:.2f}"})
    # 写回文件
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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


# 定义扑克牌的花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
HAND_RANK_NAMES = {
    9: '皇家顺', 8: '同花顺', 7: '四条', 6: '葫芦', 5: '同花',
    4: '顺子', 3: '三条', 2: '两对', 1: '对子', 0: '高牌'
}

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES[rank]
    def __repr__(self):
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        # 生成完整牌堆并洗牌
        self.full_deck = [Card(s, r) for s in SUITS for r in RANKS]
        random.shuffle(self.full_deck)
        
        # 生成随机起始位置
        self.start_pos = random.randint(21, 41)
        
        # 创建循环索引列表（52张牌）
        self.indexes = [(self.start_pos + i) % 52 for i in range(52)]
        self.pointer = 0  # 当前发牌位置指针

    def deal(self, n=1):
        # 根据索引获取牌
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

# 手牌评估: 返回 (等级, tiebreaker 列表)
def evaluate_hand(cards):
    values = sorted((c.value for c in cards), reverse=True)
    counts = Counter(values)
    suits = [c.suit for c in cards]

    # 顺子检测
    unique_vals = sorted(set(values), reverse=True)
    if 14 in unique_vals:
        unique_vals.append(1)
    straight_vals = []
    seq = []
    for v in unique_vals:
        if not seq or seq[-1] - 1 == v:
            seq.append(v)
        else:
            seq = [v]
        if len(seq) >= 5:
            straight_vals = seq[:5]
            break

    # 同花检测
    flush_suit = next((s for s in SUITS if suits.count(s) >= 5), None)
    flush_cards = [c for c in cards if c.suit == flush_suit] if flush_suit else []

    # 同花顺 & 皇家同花顺
    if flush_cards and straight_vals:
        flush_vals = sorted({c.value for c in flush_cards}, reverse=True)
        if 14 in flush_vals:
            flush_vals.append(1)
        seq2 = []
        for v in flush_vals:
            if not seq2 or seq2[-1] - 1 == v:
                seq2.append(v)
            else:
                seq2 = [v]
            if len(seq2) >= 5:
                return (9, seq2[:5]) if seq2[0] == 14 else (8, seq2[:5])

    # 统计牌型
    counts_list = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if counts_list[0][1] == 4:
        quad = counts_list[0][0]
        kicker = max(v for v in values if v != quad)
        return (7, [quad, kicker])
    if counts_list[0][1] == 3 and counts_list[1][1] >= 2:
        return (6, [counts_list[0][0], counts_list[1][0]])
    if flush_suit:
        top5 = sorted((c.value for c in flush_cards), reverse=True)[:5]
        return (5, top5)
    if straight_vals:
        return (4, straight_vals)
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, [three] + kickers)
    pairs = [v for v, cnt in counts_list if cnt == 2]
    if len(pairs) >= 2:
        high, low = pairs[0], pairs[1]
        kicker = max(v for v in values if v not in (high, low))
        return (2, [high, low, kicker])
    if counts_list[0][1] == 2:
        pair = counts_list[0][0]
        kickers = [v for v in values if v != pair][:3]
        return (1, [pair] + kickers)
    return (0, values[:5])

# 找到最佳5张牌组合
def find_best_5(cards):
    best_eval = None
    best_hand = None
    for combo in combinations(cards, 5):
        ev = evaluate_hand(combo)
        if best_eval is None or ev > best_eval:
            best_eval = ev
            best_hand = combo
    return best_eval, best_hand

# 格式化最佳牌型输出
def format_hand(best_hand, eval_res):
    rank, tiebreaker = eval_res
    cards = list(best_hand)
    counts = Counter(c.value for c in cards)
    if rank in [4, 8, 9]:
        seq = tiebreaker
        asc = list(reversed(seq))
        vals = [14 if v == 1 else v for v in asc]
        sorted_cards = []
        for v in vals:
            for c in cards:
                if c.value == v and c not in sorted_cards:
                    sorted_cards.append(c)
                    break
        return ' '.join(map(str, sorted_cards))
    sorted_cards = sorted(cards, key=lambda c: (-counts[c.value], -c.value))
    return ' '.join(map(str, sorted_cards))

# 支付表
BLIND_PAYOUT = {4:1, 5:1.5, 6:3, 7:10, 8:50, 9:500}
TRIPS_PAYOUT = {3:3, 4:4, 5:7, 6:9, 7:30, 8:40, 9:50}

# 押注输入与验证
def get_bet(prompt, min_bet, max_bet, funds):
    while True:
        try:
            print('='*40)
            if prompt == "Ante/Blind":
                print("|| 输入0以退出游戏")
            amt = int(input(f"|| 最少: {min_bet} || 最多: {max_bet}\n|| 请输入{prompt}金额: "))
            if amt < 0 or amt > max_bet or amt % 5 != 0:
                raise ValueError
            if  amt == 0 and prompt == "Ante/Blind":
                return amt
            if amt > funds:
                print(f"|| 资金不足，请重新输入！当前资金：{funds}")
                time.sleep(2.5)
                continue
            return amt
        except ValueError:
            print(f"|| 请输入{min_bet}-{max_bet}且为5的倍数")

# UI 展示函数
def ui(player_hole, community, dealer_hole, steps):
    os.system('cls' if os.name == 'nt' else 'clear')
    print('='*40)
    if steps == 'Allop':
        print(f"|| 庄家底牌： {dealer_hole[0]} {dealer_hole[1]}")
    else:
        print("|| 庄家底牌： ?? ??")
    print('='*40)
    if steps == 'Allop' or steps == 'Allpop':
        print(f"|| >>公共牌： {' '.join(map(str, community[:5]))}")
    elif steps == 'Allcl':
        print(f"|| >>公共牌： ?? ?? ?? ?? ??")
    else:
        print(f"|| >>公共牌： {' '.join(map(str, community[:3]))} ?? ??")
    print('='*40)
    print(f"|| 您的底牌： {player_hole[0]} {player_hole[1]}")
    print('='*40)

# 主游戏循环
def play_game(funds, username):
    tempjp = False
    while funds >= 15:
        temp_bet = 0
        initial_funds = funds
        os.system('cls' if os.name == 'nt' else 'clear')
        print(">>> 欢迎游玩Ultimate Texas Hold'em！ <<<")
        print('='*40)
        if tempjp != True:
            tempjp, jackpot_amount = load_jackpot()
        print(f"|| Jackpok奖金高达{jackpot_amount:.2f}！")
        print('='*40)
        print(f"|| 当前资金：{funds} 游戏单位: 5")
        print('='*40)
        ante = get_bet('Ante/Blind', 5, 200, funds)
        if ante == 0:
            print('='*40)
            print(">>> 谢谢游玩Ultimate Texas Hold'em！ <<<")
            print("=======================MAKE=BY=HSC======")
            break
        blind = ante
        if funds - 2*ante < ante:
            print(f"支付Ante和Blind后资金不足以下注Play\n请重新输入。当前资金：{funds}")
            continue
        trips = get_bet('Trips', 0, 50, funds - 2*ante)
        if funds - 2*ante - trips < ante:
            print(f"支付Ante/Blind和Trips后资金不足以下注Play\n请重新输入。当前资金：{funds}")
            continue
        # Jackpot 选项
        participate_jackpot = False
        print('='*40)
        print(f"|| 报名Bonus大奖？ 输入任意数字即可！")
        opt = input("|| 仅需2.50! 要报名吗: ")
        if opt != "":
            if funds < 2.5:
                print(f"|| 资金不足，无法报名Jackpot")
            else:
                funds -= 2.5
                temp_bet += 2.5
                participate_jackpot = True
        # 扣除基础投注
        funds -= (2*ante + trips)
        temp_bet += (2*ante + trips)
        if username != "demo_player":
            update_balance_in_json(username, funds)

        deck = Deck()

        # 按新规则发牌：
        community = deck.deal(5)   # 前5张为公共牌
        player_hole = deck.deal(2) # 接下来2张玩家底牌
        dealer_hole = deck.deal(2) # 最后2张庄家底牌

        play_bet = 0
        showdown = False
        folded = False

        # Pre-flop 阶段
        while True:
            ui(player_hole, community, dealer_hole, 'Allcl')
            print("   DEALER QUALIFY WITH PAIR OR BETTER")
            print('='*40)
            print("|| 选择: ⓪ Check  ① 3X Ante  ② 4X Ante")
            choice = input("|| 请作出Play的选择: ")
            if choice in ['1', '2']:
                factor = int(choice)
                if factor == 1:
                    factor = 3
                else:
                    factor = 4
                needed = factor * ante
                if funds < needed:
                    print(f"资金不足！当前资金：{funds}")
                    continue
                # 扣除Play投注
                funds -= needed
                play_bet = needed
                temp_bet += play_bet
                ui(player_hole, community, dealer_hole, 'Allop')
                showdown = True
                if username != "demo_player":
                    update_balance_in_json(username, funds)
                break
            elif choice == '0':
                print(f"不在Pre-flop下注，翻牌：{' '.join(map(str, community[:3]))}")
                break
            else:
                print("输入无效，请重新输入。")

        # Flop 阶段
        if not showdown:
            ui(player_hole, community, dealer_hole, 'Step2')
            while True:
                print("   DEALER QUALIFY WITH PAIR OR BETTER")
                print('='*40)
                print("|| 选择: ⓪ Check  ① 2X Ante" )
                choice2 = input("|| 请作出Play的选择: ")
                if choice2 == '1':
                    needed = 2 * ante
                    if funds < needed:
                        print(f"资金不足！当前资金：{funds}")
                        continue
                    funds -= needed
                    play_bet = needed
                    temp_bet += play_bet
                    ui(player_hole, community, dealer_hole, 'Allop')
                    showdown = True
                    if username != "demo_player":
                        update_balance_in_json(username, funds)
                    break
                elif choice2 == '0':
                    print("不在Flop下注，进入River。")
                    ui(player_hole, community, dealer_hole, 'Allpop')
                    break
                else:
                    print("输入无效，请重新输入。")

        # River 阶段
        if not showdown and not folded:
            while True:
                ui(player_hole, community, dealer_hole, 'Allpop')
                print("   DEALER QUALIFY WITH PAIR OR BETTER")
                print('='*40)
                print("|| 选择: ⓪ 弃牌 ① 1X Ante")
                choice3 = input("|| 请作出Play的选择: ")
                if choice3 == '1':
                    needed = ante
                    if funds < needed:
                        print(f"资金不足！当前资金：{funds}")
                        continue
                    funds -= needed
                    play_bet = needed
                    temp_bet += play_bet
                    showdown = True
                    if username != "demo_player":
                        update_balance_in_json(username, funds)
                    break
                elif choice3.lower() == '0':
                    print(f"您已弃牌，本局押注全部输掉。当前资金：{funds}")
                    ui(player_hole, community, dealer_hole, 'Allop')
                    folded = True
                    break
                else:
                    print("输入无效，请重新输入。")

        ui(player_hole, community, dealer_hole, 'Allop')
        if folded:
            jackpot_amount += temp_bet*0.1
            save_jackpot(jackpot_amount)
            player_eval, player_best = find_best_5(player_hole + community)
            dealer_eval, dealer_best = find_best_5(dealer_hole + community)
            win_lost_amount = - (ante + blind + trips + (2.5 if participate_jackpot else 0))
            write_uth_log(username, win_lost_amount, participate_jackpot, dealer_hole, community, player_hole, dealer_best, dealer_eval, player_best, player_eval, initial_funds, jackpot_amount, 0, ante, blind, trips, 0)
            print("=======================MAKE=BY=HSC======")
            input("按Enter继续")
            continue

        # 结算
        player_eval, player_best = find_best_5(player_hole + community)
        dealer_eval, dealer_best = find_best_5(dealer_hole + community)

        # 打印牌型及名称
        print("   DEALER QUALIFY WITH PAIR OR BETTER")
        print('='*40)
        print(f"牌|| 庄家: {format_hand(dealer_best, dealer_eval)}  <{HAND_RANK_NAMES[dealer_eval[0]]}>")
        print(f"型|| 玩家: {format_hand(player_best, player_eval)}  <{HAND_RANK_NAMES[player_eval[0]]}>")
        print('='*40)

        # 主注结算
        win_lost_amount = 0
        if player_eval > dealer_eval:
            print("  ||\t\t您赢了！")
            # Play赢利+返还本金
            print("结|| Play:  赔率1:1 赢:",play_bet * 2)
            funds += play_bet * 2
            win_lost_amount += play_bet
            # 如果庄家未合格（高牌），退还Ante赌注（无论输赢）
            if dealer_eval[0] == 0:
                temp_bet -= ante
                print("  || Ante:  庄家为高牌: 退还")
                funds += ante
            else:
                # Ante赢利+返还本金
                if player_eval > dealer_eval:
                    # 玩家赢，返还本金＋1:1收益
                    print("  || Ante:  赔率1:1 赢:", ante * 2)
                    funds += ante * 2
                    win_lost_amount += ante
            # Blind赢利或返还本金
            if player_eval[0] in BLIND_PAYOUT:
                odds = BLIND_PAYOUT[player_eval[0]]
                profit = blind * (1 + odds)
                win_lost_amount += profit
                funds += blind + profit
                profit_str = str(int(profit)) if profit.is_integer() else str(profit)
                print(f"算|| Blind: 赔率{odds}:1 赢: {profit_str}")
            else:
                funds += blind
                print("算|| Blind: Push")
            jackpot_amount += temp_bet*0.01
        elif player_eval == dealer_eval:
            if trips > 0 and player_eval[0] in TRIPS_PAYOUT:
                print("  ||\t庄家玩家和<Trips赢>")
            else:
                print("  ||\t庄家玩家和")
            print("结|| Play:  Push")
            if dealer_eval[0] == 0:
                print("  || Ante:  庄家为高牌: 退还")
                temp_bet -= ante
            else:
                print("  || Ante:  Push")
            print("算|| Blind: Push")
            funds += play_bet + ante + blind
            jackpot_amount += temp_bet*0.015
        else:
            if trips > 0 and player_eval[0] in TRIPS_PAYOUT:
                print("  ||\t\t您没赢<Trips赢>")
            else:
                print("  ||\t\t您没赢")
            print("结|| Play:  未赢")
            win_lost_amount -= play_bet
            if dealer_eval[0] == 0:
                print("  || Ante:  庄家为高牌: 退还")
                temp_bet -= ante
                funds += ante
            else:
                print("  || Ante:  未赢")
                win_lost_amount -= ante
            print("算|| Blind: 未赢")
            win_lost_amount -= blind
            jackpot_amount += temp_bet*0.2

        # Trips 副注结算
        if trips > 0:
            if player_eval[0] in TRIPS_PAYOUT:
                win = trips * TRIPS_PAYOUT[player_eval[0]]
                wins = trips + win
                print(f"  || Trips: 赔率{TRIPS_PAYOUT[player_eval[0]]}:1 赢: {wins}")
                funds += wins
                win_lost_amount += win
            else:
                print("  || Trips: 未赢")
                win_lost_amount -= trips

        # Jackpok 结算
        if participate_jackpot:
            print('='*40)
            jp_cards = player_hole + community[:3]
            jp_eval, jp_hand = evaluate_hand(jp_cards)
            jp_win = 0

            if jp_eval == 9:
                win = max(jackpot_amount, 10000)
                print(f"JP|| JKPK:  赢: {win:.2f}")
                jp_win = win
                funds += win
                jackpot_amount = 197301.26
            elif jp_eval == 8:
                win = max(jackpot_amount * 0.1, 1000)
                jp_win = win
                print(f"JP|| JKPK:  赢: {win:.2f}")
                funds += win
                jackpot_amount = 197301.26
            elif jp_eval == 7:
                print("JP|| JKPK:  赢: 750")
                funds += 750
                jp_win += 750
                jackpot_amount -= 750
            elif jp_eval == 6:
                print(f"JP|| JKPK:  赢: 125")
                funds += 125
                jp_win += 125
                jackpot_amount -= 125
            elif jp_eval == 5:
                print(f"JP|| JKPK:  赢: 100")
                funds += 100
                jp_win += 100
                jackpot_amount -= 100
            elif jp_eval == 4:
                print(f"JP|| JKPK:  赢: 75")
                funds += 75
                jp_win += 75
                jackpot_amount -= 75
            elif jp_eval == 3:
                print(f"JP|| JKPK:  赢: 22.5")
                funds += 22.5
                jp_win += 22.5
                jackpot_amount -= 22.5
            else:
                print("JP|| JKPK:  未赢")

        if tempjp != True:
            save_jackpot(jackpot_amount)
        if username != "demo_player":
            update_balance_in_json(username, funds)
        write_uth_log(username, win_lost_amount, participate_jackpot, dealer_hole, community, player_hole, dealer_best, dealer_eval, player_best, player_eval, initial_funds, jackpot_amount, play_bet, ante, blind, trips, jp_win)

        print('='*40)
        print("=======================MAKE=BY=HSC======")

        print("Debug use")
        print('='*40)
        print(f"|| 当前牌堆起始位置：{deck.start_pos}")
        print("|| 完整牌堆列表：")

        for idx, card in enumerate(deck.full_deck):
            # 判断是否到达起始位置
            if idx == deck.start_pos:
                print("|CUT>>", end='')
            
            # 格式化输出牌面（统一3字符宽度）
            print(f"{str(card):<3}", end='')
            
            # 每10张换行 + 高亮起始行
            if (idx + 1) % 10 == 0:
                print()

        # 处理最后一行未满10张的情况
        if len(deck.full_deck) % 10 != 0:
            print()
        print('='*40)

        input("按Enter继续")
    if funds < 15:
        print('='*40)
        print(">>> 谢谢游玩Ultimate Texas Hold'em！ <<<")
        print("=======================MAKE=BY=HSC======")
    return funds

if __name__ == '__main__':
    play_game(1000, "demo_player")
