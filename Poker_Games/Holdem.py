from itertools import combinations
import time
import random
import threading
import os
import json

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

suits = ['♥', '♦', '♣', '♠']
ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

def block():
    print("========================================")

def card_random():
    deck = [rank + suit for suit in suits for rank in ranks]
    random.shuffle(deck)
    return deck

RANK_ORDER = {str(i): i for i in range(2, 11)}
RANK_ORDER.update({'J': 11, 'Q': 12, 'K': 13, 'A': 14})
HAND_RANKS = ['0', '高牌', '对子', '两对', '三张', '顺子', '同花', '葫芦', '四张', '同花顺', '皇家同花顺']

## Find the winner
def get_rank_value(card):
    return RANK_ORDER[card[:-1]]  # 去掉花色，返回数值

def hand_rank(hand):
    """ 评估一个五张牌的手牌，返回手牌的等级和数值 """
    ranks = sorted([get_rank_value(card) for card in hand], reverse=True)
    suits = [card[-1] for card in hand]
    
    # 判断是否是同花
    is_flush = len(set(suits)) == 1
    
    # 判断是否是顺子
    is_straight = (ranks == list(range(ranks[0], ranks[0] - 5, -1))) or ranks == [14, 5, 4, 3, 2]  # 处理A, 2, 3, 4, 5
    
    rank_counts = {r: ranks.count(r) for r in ranks}
    counts = sorted(rank_counts.values(), reverse=True)
    unique_ranks = sorted(rank_counts.keys(), reverse=True)
    
    if is_flush and is_straight:
        return (9, ranks) if ranks[0] != 14 else (10, ranks)  # 皇家同花顺 or 同花顺
    
    if counts == [4, 1]:
        return (8, unique_ranks)  # 四条
    
    if counts == [3, 2]:
        return (7, unique_ranks)  # 葫芦
    
    if is_flush:
        return (6, ranks)  # 同花
    
    if is_straight:
        return (5, ranks)  # 顺子
    
    if counts == [3, 1, 1]:
        return (4, unique_ranks)  # 三条
    
    if counts == [2, 2, 1]:
        return (3, unique_ranks)  # 两对
    
    if counts == [2, 1, 1, 1]:
        return (2, unique_ranks)  # 一对
    
    return (1, ranks)  # 高牌

def calculate_winner(p1, p2, d1, d2, f1, f2, f3, f4, f5, bet, bet2):
    player_hand = [p1, p2]
    dealer_hand = [d1, d2]
    community_cards = [f1, f2, f3, f4, f5]
    
    all_player_cards = player_hand + community_cards
    all_dealer_cards = dealer_hand + community_cards

    # 获取所有可能的五张牌组合
    player_combinations = combinations(all_player_cards, 5)
    dealer_combinations = combinations(all_dealer_cards, 5)

    # 找到玩家和庄家的最优组合
    best_player_hand = max(player_combinations, key=hand_rank)
    best_dealer_hand = max(dealer_combinations, key=hand_rank)

    player_score = hand_rank(best_player_hand)
    dealer_score = hand_rank(best_dealer_hand)

    block(), block()
    print("玩家最佳手牌：", best_player_hand, "种类：", HAND_RANKS[player_score[0]])
    print("庄家最佳手牌：", best_dealer_hand, "种类：", HAND_RANKS[dealer_score[0]])
    block()
    
    if player_score > dealer_score:
        print(f"你赢了{bet * 3 + bet2 *2}块！！")
        return bet * 3 + bet2 *2  # 玩家获胜
    elif player_score < dealer_score:
        print("庄家获胜！")
        return 0  # 庄家获胜，玩家输掉赌注
    else:
        print("平局！")
        return bet+bet2  # 平局，玩家拿回赌注

def games(username, bet_input_1, balance):
    deck = card_random()

    player = deck[:2]         # 玩家
    dealer = deck[2:4]        # 庄家
    flop = deck[4:7]          # Flop
    turn_river = deck[7:9]    # Turn 和 River

    os.system('cls' if os.name == 'nt' else 'clear')
    print("...请做出你最明智的决定！...")
    block()
    print(f"你的牌是： {player[0]} 和 {player[1]}")
    block()
    block()
    time.sleep(0.85)
    print(f"公共牌是： {flop[0]} 和 {flop[1]} 和 {flop[2]}")
    block()
    block()

    while True:
        print("① Check(看牌) ② Raise(加注) ③ Fold(弃牌)")
        try:
            choice = int(input("做出你的决定： "))
            if choice not in [1, 2, 3]:
                print("无效的输入，请输入 1、2 或 3。")
                time.sleep(2.25)
                os.system('cls' if os.name == 'nt' else 'clear')
                print("...请做出你最明智的决定！...")
                block()
                print(f"你的牌是： {player[0]} 和 {player[1]}")
                block()
                block()
                print(f"公共牌是： {flop[0]} 和 {flop[1]} 和 {flop[2]}")
                block()
                block()
                continue  # 重新提示用户输入
            if choice == 3:
                print("\n 你选择了： 弃牌")
                return balance + bet_input_1 * 0.25
            elif choice == 2:
                while True:
                    try:
                        os.system('cls' if os.name == 'nt' else 'clear')
                        print("你选择了： 加注")
                        block()
                        print(f"你的牌是： {player[0]} 和 {player[1]}")
                        block()
                        block()
                        print(f"公共牌是： {flop[0]} 和 {flop[1]} 和 {flop[2]}")
                        block()
                        block()
                        print(f"当前余额：{balance:.2f}")
                        bet_input_2 = int(input("输入您加注金额："))
                        if bet_input_2 > balance or bet_input_2 <= 0:
                            print("加注金额无效，请输入有效的金额。")
                            time.sleep(2)
                        else:
                            balance -= bet_input_2
                            if username != "demo_player":
                                update_balance_in_json(username, balance)
                            os.system('cls' if os.name == 'nt' else 'clear')
                            print("你选择了： 加注")
                            break
                    except ValueError:
                        print("请输入一个有效的数字。")
                        time.sleep(2.25)
                        os.system('cls' if os.name == 'nt' else 'clear')
                        print("...请做出你最明智的决定！...")
                        block()
                        print(f"你的牌是： {player[0]} 和 {player[1]}")
                        block()
                        block()
                        print(f"公共牌是： {flop[0]} {flop[1]} {flop[2]}")
                        block()
                        block()
            elif choice == 1:
                os.system('cls' if os.name == 'nt' else 'clear')
                print("你选择了： 看牌")
                bet_input_2 = 0
        except ValueError:
            print("请输入一个有效的数字。")
            time.sleep(2.25)
            os.system('cls' if os.name == 'nt' else 'clear')
            print("...请做出你最明智的决定！...")
            block()
            print(f"你的牌是： {player[0]} 和 {player[1]}")
            block()
            block()
            print(f"公共牌是： {flop[0]} {flop[1]} {flop[2]}")
            block()
            block()
            continue  # 重新提示用户输入

        block()
        print(f"你的牌是： {player[0]} 和 {player[1]}")
        block()
        block()
        time.sleep(0.85)
        print(f"公共牌是： {flop[0]} 和 {flop[1]} 和 {flop[2]} + {turn_river[0]} 和 {turn_river[1]}")
        block()
        block()
        time.sleep(0.85)
        print(f"庄家的牌是： {dealer[0]} 和 {dealer[1]}")
        winning = calculate_winner(player[0], player[1], dealer[0], dealer[1], flop[0], flop[1], flop[2], turn_river[0], turn_river[1], bet_input_1, bet_input_2)
        return balance + winning


def main(balance, username):
    while balance > 0:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"当前余额：{balance:.2f}")
        try:
            bet_input = input("输入您的下注金额(0退出)：")
            if bet_input.lower() == "0":
                print("退出当前游戏，返回主菜单。")
                return balance 
            else:
                bet_input = int(bet_input)

            if bet_input > balance or bet_input <= 0:
                print("下注金额无效，请输入有效的金额。")
                continue
        except ValueError:
            print("请输入一个有效的数字。")
            continue
        
        balance -= bet_input
        if username != "demo_player":
            update_balance_in_json(username, balance)
        
        balance = games(username, bet_input, balance)

        if username != "demo_player":
            update_balance_in_json(username, balance)

        input("\n请按'Enter'确认当局没问题")
        
    time.sleep(2.5)
    print("感谢您的游玩！")
    return balance

if __name__ == "__main__":
    main(100, "demo_player")