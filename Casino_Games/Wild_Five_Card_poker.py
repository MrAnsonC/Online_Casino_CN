import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import random
import json
import os
from collections import Counter
from itertools import combinations
import math
import hashlib
import time
import secrets
import subprocess, sys

# 扑克牌花色和点数 - 增加鬼牌
SUITS = ['♠', '♥', '♦', '♣', 'JOKER']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, start=2)}
# 鬼牌的值设为15，以便在评估时特殊处理
RANK_VALUES['A'] = 14  # A的值为14
HAND_RANK_NAMES = {
    10: '五条',
    9: '同花大顺',
    8: '同花顺',
    7: '四条',
    6: '葫芦',
    5: '同花',
    4: '顺子',
    3: '三条',
    2: '两对',
    1: '对子',
    0: '高牌'
}

# 支付表 - 根据Wild Five Poker规则调整
ANTE_PAYOUT = 1  # Ante赔率1:1
BONUS_PAYOUT = {
    10: 100,  # 五條 100:1
    9: 50,    # 皇家同花順 50:1
    8: 10,    # 同花順 10:1
    7: 5,     # 四條 5:1
    6: 3,     # 葫蘆 3:1
    5: 2,     # 同花 2:1
    4: 1      # 順子 1:1
    # 其他牌型以Push处理
}

# Wild 5边注赔率
WILD_5_PAYOUT = {
    10: 1000,  # 五條 1000:1
    9: 500,    # 皇家同花順 500:1
    8: 250,    # 同花順 250:1
    7: 100,    # 四條 100:1
    6: 50,     # 葫蘆 50:1
    5: 25,     # 同花 25:1
    4: 10,     # 順子 10:1
    3: 5,      # 三條 5:1
    2: 5       # 兩對 5:1
    # 其他牌型 输
}

def get_data_file_path():
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(parent_dir, 'saving_data.json')

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
                if item.get('Games') == 'W5P':
                    return False, float(item.get('jackpot', default_jackpot))
    except Exception:
        return True, default_jackpot
    # 未找到 W5P 条目时也使用默认
    return True, default_jackpot

def save_jackpot(jackpot):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Jackpot.json')
    data = []
    # 如果文件存在，读取原有数据
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = []
    
    # 查找是否已有WildFive的记录
    found = False
    for item in data:
        if item.get('Games') == 'W5P':
            item['jackpot'] = jackpot
            found = True
            break
    
    if not found:
        data.append({"Games": "W5P", "jackpot": jackpot})
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.value = RANK_VALUES.get(rank, 0)  # 鬼牌的值设为0，特殊处理
        # 鬼牌的特殊标记
        self.is_joker = (suit == 'JOKER')
        
    def __repr__(self):
        if self.is_joker:
            return "JOKER"
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        # 获取当前脚本所在目录的上一级目录
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 新的Card文件夹路径
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        shuffle_script = os.path.join(card_dir, 'shuffle_52+1.py')  # 修改为新的洗牌脚本
        
        # 保证 Python 输出为 UTF-8
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        try:
            # 调用外部 shuffle_52+1.py，超时 30 秒
            result = subprocess.run(
                [sys.executable, shuffle_script],
                capture_output=True,
                text=True,
                encoding='utf-8',
                env=env,
                check=True,
                timeout=30
            )
            shuffle_data = json.loads(result.stdout)
            
            if "deck" not in shuffle_data or "cut_position" not in shuffle_data:
                raise ValueError("Invalid shuffle data format")
            
            # 用本模块的 Card 类实例化
            self.full_deck = []
            for d in shuffle_data["deck"]:
                suit = d["suit"]
                rank = d["rank"]
                self.full_deck.append(Card(suit, rank))
                
            self.cut_position = shuffle_data["cut_position"]
        
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                json.JSONDecodeError,
                ValueError,
                KeyError) as e:
            print(f"Error calling shuffle_52+1.py: {e}. Using fallback shuffle.")
            # fallback：标准顺序+安全乱序
            self.full_deck = [Card(s, r) for s in SUITS[:-1] for r in RANKS]  # 排除JOKER花色
            # 添加鬼牌
            self.full_deck.append(Card('JOKER', 'A'))
            self._secure_shuffle()
            self.cut_position = secrets.randbelow(53)  # 53张牌
        
        # 通用的洗牌后索引 & 发牌序列逻辑
        self.start_pos = self.cut_position
        self.indexes = [(self.start_pos + i) % 53 for i in range(53)]  # 53张牌
        self.pointer = 0
        self.card_sequence = [self.full_deck[i] for i in self.indexes]
    
    def _secure_shuffle(self):
        """Fisher–Yates 洗牌，用 secrets 保证随机性"""
        for i in range(len(self.full_deck) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            self.full_deck[i], self.full_deck[j] = self.full_deck[j], self.full_deck[i]

    def deal(self, n=1):
        dealt = [self.full_deck[self.indexes[self.pointer + i]] for i in range(n)]
        self.pointer += n
        return dealt

def evaluate_hand(cards):
    """评估手牌，考虑鬼牌作为万能牌"""
    # 分离鬼牌和普通牌
    jokers = [c for c in cards if c.is_joker]
    normal_cards = [c for c in cards if not c.is_joker]
    joker_count = len(jokers)
    
    # 如果没有鬼牌，使用标准评估
    if joker_count == 0:
        return _evaluate_normal_hand(normal_cards), []
    
    # 有鬼牌的情况下，尝试所有可能的替换
    best_score = (-1, [])
    best_replacement = []
    possible_replacements = _generate_possible_replacements(joker_count, normal_cards)
    
    for replacement in possible_replacements:
        test_hand = normal_cards + replacement
        score = _evaluate_normal_hand(test_hand)
        if score[0] > best_score[0] or (score[0] == best_score[0] and _compare_hands(score[1], best_score[1]) > 0):
            best_score = score
            best_replacement = replacement
    
    return best_score, best_replacement

def _generate_possible_replacements(joker_count, existing_cards):
    """生成鬼牌可能替换的所有组合（不排除已存在的牌）"""
    if joker_count == 0:
        return [[]]
    
    # 生成所有可能的牌（不排除已存在的牌）
    all_cards = []
    for suit in SUITS[:-1]:  # 排除JOKER花色
        for rank in RANKS:
            all_cards.append(Card(suit, rank))
    
    # 生成所有可能的替换组合
    replacements = []
    for combo in combinations(all_cards, joker_count):
        replacements.append(list(combo))
    
    return replacements

def _compare_hands(hand1, hand2):
    """
    比较两手牌的大小:
    - hand1 > hand2 返回 1
    - hand1 < hand2 返回 -1
    - 相等 返回 0

    hand 参数可以是:
      (rank, [values...])  -> 推荐的格式
      [values...]          -> 只比较 kicker 值时
    """
    # 如果是 tuple (rank, list)
    if isinstance(hand1, tuple) and isinstance(hand2, tuple):
        rank1, values1 = hand1
        rank2, values2 = hand2

        # 先比较牌型等级
        if rank1 > rank2:
            return 1
        elif rank1 < rank2:
            return -1

        # 牌型相同 -> 比较具体数值
        for v1, v2 in zip(values1, values2):
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        return 0

    # 如果只是 [values...] 列表
    if isinstance(hand1, list) and isinstance(hand2, list):
        for v1, v2 in zip(hand1, hand2):
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        return 0

    # 其他情况 -> 转成列表比较
    h1 = hand1 if isinstance(hand1, (list, tuple)) else [hand1]
    h2 = hand2 if isinstance(hand2, (list, tuple)) else [hand2]
    for v1, v2 in zip(h1, h2):
        if v1 > v2:
            return 1
        elif v1 < v2:
            return -1
    return 0


def _evaluate_normal_hand(cards):
    """评估没有鬼牌的手牌"""
    if len(cards) < 5:
        return (0, [])  # 手牌不足5张
    
    values = sorted((c.value for c in cards), reverse=True)
    counts = Counter(values)
    suits = [c.suit for c in cards]

    # 检查同花
    flush_suit = next((s for s in set(suits) if suits.count(s) >= 5), None)
    flush_cards = [c for c in cards if c.suit == flush_suit] if flush_suit else []
    
    # 检查顺子
    unique_vals = sorted(set(values), reverse=True)
    # 处理A可以作为1的情况
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

    # 检查同花顺
    if flush_suit and straight_vals:
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
                if seq2[0] == 14 and seq2[4] == 10:  # A-K-Q-J-10
                    return (9, [14, 13, 12, 11, 10])  # 同花大顺
                return (8, seq2[:5])  # 同花顺

    # 检查五条
    if len(counts) == 1 and len(cards) >= 5:
        return (10, [values[0]] * 5)
    
    # 检查四条
    counts_list = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    if counts_list[0][1] == 4:
        quad = counts_list[0][0]
        kicker = max(v for v in values if v != quad)
        return (7, [quad, kicker])
    
    # 检查葫芦
    if counts_list[0][1] == 3 and counts_list[1][1] >= 2:
        return (6, [counts_list[0][0], counts_list[1][0]])
    
    # 检查同花
    if flush_suit:
        top5 = sorted((c.value for c in flush_cards), reverse=True)[:5]
        return (5, top5)
    
    # 检查顺子
    if straight_vals:
        return (4, straight_vals)
    
    # 检查三条
    if counts_list[0][1] == 3:
        three = counts_list[0][0]
        kickers = [v for v in values if v != three][:2]
        return (3, [three] + kickers)
    
    # 检查两对
    pairs = [v for v, cnt in counts_list if cnt == 2]
    if len(pairs) >= 2:
        high, low = pairs[0], pairs[1]
        kicker = max(v for v in values if v not in (high, low))
        return (2, [high, low, kicker])
    
    # 检查对子
    if counts_list[0][1] == 2:
        pair = counts_list[0][0]
        kickers = [v for v in values if v != pair][:3]
        return (1, [pair] + kickers)
    
    # 高牌
    return (0, values[:5])

def find_best_5(cards):
    """从多张牌中找出最好的5张牌组合"""
    best_eval = None
    best_hand = None
    best_replacement = []
    for combo in combinations(cards, 5):
        ev, replacement = evaluate_hand(combo)
        if best_eval is None or ev[0] > best_eval[0] or (ev[0] == best_eval[0] and _compare_hands(ev[1], best_eval[1]) > 0):
            best_eval = ev
            best_hand = combo
            best_replacement = replacement
    return best_eval, best_hand, best_replacement

def evaluate_progressive(cards):
    """评估Progressive奖励，使用玩家的5张最终手牌，考虑Joker作为万能牌"""
    if len(cards) != 5:
        return None
    
    # 分离鬼牌和普通牌
    jokers = [c for c in cards if getattr(c, 'is_joker', False)]
    normal_cards = [c for c in cards if not getattr(c, 'is_joker', False)]
    joker_count = len(jokers)
    
    # 如果没有鬼牌，使用标准评估
    if joker_count == 0:
        return _evaluate_progressive_normal(normal_cards)
    
    # 有鬼牌的情况下，尝试所有可能的替换
    best_result = None
    best_rank = -1
    possible_replacements = _generate_possible_replacements(joker_count, normal_cards)
    
    for replacement in possible_replacements:
        test_hand = normal_cards + replacement
        result = _evaluate_progressive_normal(test_hand)
        
        if result:
            # 找到最好的牌型
            rank = _get_progressive_rank(result)
            if rank > best_rank:
                best_result = result
                best_rank = rank
    
    return best_result

def _get_progressive_rank(result):
    """获取Progressive牌型的排名"""
    progressive_ranks = {
        "five_of_a_kind": 6,
        "royal_flush": 5,
        "straight_flush": 4,
        "four_of_a_kind": 3,
        "full_house": 2,
        "flush": 1
    }
    return progressive_ranks.get(result, 0)

def _evaluate_progressive_normal(cards):
    """评估没有鬼牌的手牌的Progressive奖励"""
    if len(cards) != 5:
        return None
    
    # 检查五条
    values = [c.value for c in cards]
    counts = Counter(values)
    for value, count in counts.items():
        if count >= 5:
            return "five_of_a_kind"
    
    # 检查皇家同花顺
    royal_values = {14, 13, 12, 11, 10}  # A, K, Q, J, 10
    suits = [c.suit for c in cards]
    
    for suit in set(suits):
        suit_cards = [c for c in cards if c.suit == suit]
        suit_values = {c.value for c in suit_cards}
        
        if royal_values.issubset(suit_values):
            return "royal_flush"
    
    # 检查同花顺
    for suit in set(suits):
        suit_cards = [c for c in cards if c.suit == suit]
        if len(suit_cards) < 5:
            continue
            
        suit_values = sorted([c.value for c in suit_cards], reverse=True)
        
        # 检查是否形成顺子
        seq = []
        for v in suit_values:
            if not seq or seq[-1] - 1 == v:
                seq.append(v)
            else:
                seq = [v]
            if len(seq) >= 5:
                return "straight_flush"
    
    # 检查四条
    counts = Counter(values)
    for value, count in counts.items():
        if count >= 4:
            return "four_of_a_kind"
    
    # 检查葫芦
    three_value = None
    two_value = None
    for value, count in counts.items():
        if count >= 3:
            three_value = value
        elif count >= 2:
            two_value = value
    
    if three_value and two_value:
        return "full_house"
    
    # 检查同花
    flush_suit = next((s for s in set(suits) if suits.count(s) >= 5), None)
    if flush_suit:
        return "flush"
    
    return None
    
def calculate_progressive_payout(progressive_result, jackpot_amount):
    """计算Progressive奖金，确保奖池不低于197301.26"""
    payout_table = {
        "five_of_a_kind": max(jackpot_amount, 50000),  # 100% Progressive或50000，取更高
        "royal_flush": max(jackpot_amount * 0.5, 20000),  # 50% Progressive或20000，取更高
        "straight_flush": max(jackpot_amount * 0.5, 20000),  # 20% Progressive或5000，取更高
        "four_of_a_kind": 3000,
        "full_house": 2000,
        "flush": 1000
    }
    
    if progressive_result in payout_table:
        payout = payout_table[progressive_result]
        return payout
    
    return 0

def sort_hand_with_joker(cards, joker_replacements):
    """根据有无鬼牌对手牌进行排序"""
    # 分离鬼牌和普通牌
    jokers = [c for c in cards if getattr(c, 'is_joker', False)]
    non_jokers = [c for c in cards if not getattr(c, 'is_joker', False)]

    if not jokers:
        # 这里依赖已有的 sort_hand_without_joker(cards) 函数
        return sort_hand_without_joker(non_jokers)

    # 形成用于评估和决定顺序的“虚拟手”：真实非鬼牌 + 替换卡
    virtual_hand = non_jokers + list(joker_replacements)

    # 使用已有的无鬼牌排序逻辑来得到理想顺序（虚拟卡包含在内）
    virtual_sorted = sort_hand_without_joker(virtual_hand)

    # 现在把虚拟排序映射回“显示用”的实际 Card 对象列表：
    # - 如果虚拟位置对应原始非鬼牌（same suit & rank），就把原始对象加入结果
    # - 如果虚拟位置对应替换卡（不是原始非鬼牌），就用一个 Joker 对象占位（保持 Joker 可见）
    final = []
    jokers_copy = jokers.copy()  # 用于按顺序插入 Joker 占位
    # 为了能准确匹配原始非鬼牌对象，按 suit+rank 做匹配
    def find_matching_nonjoker(vcard):
        for c in non_jokers:
            if getattr(c, 'suit', None) == getattr(vcard, 'suit', None) and getattr(c, 'rank', None) == getattr(vcard, 'rank', None):
                # 若已在 final 中（重复），则跳过，保证不重复加入同一张真实卡
                if c in final:
                    continue
                return c
        return None

    for v in virtual_sorted:
        match = find_matching_nonjoker(v)
        if match:
            final.append(match)
        else:
            # 虚拟卡不是现存非鬼牌 => 用 Joker 占位
            if jokers_copy:
                final.append(jokers_copy.pop(0))
            else:
                # 保险回退：若没有 joker 可插入（异常情况），则插入虚拟卡本身
                final.append(v)

        if len(final) >= 5:
            break

    # 保证长度为5：补入还没加入的真实非鬼牌（按 value 降序）
    if len(final) < 5:
        remaining = [c for c in sorted(non_jokers, key=lambda x: x.value, reverse=True) if c not in final]
        for c in remaining:
            final.append(c)
            if len(final) >= 5:
                break

    # 仍不足时补 Joker（理论上不应该发生）
    while len(final) < 5 and jokers_copy:
        final.append(jokers_copy.pop(0))

    # 截断为 5 张并返回
    return final[:5]

def sort_hand_without_joker(cards):
    """没有鬼牌时的排序"""
    # 评估手牌
    eval_result = _evaluate_normal_hand(cards)
    hand_rank = eval_result[0]
    values = eval_result[1]
    
    # 根据牌型排序
    if hand_rank in [0, 5, 7, 10]:  # 高牌、同花、四条、五条：按牌面值从大到小排序
        return sorted(cards, key=lambda x: x.value, reverse=True)
    
    elif hand_rank == 1:  # 对子：对子在前，然后单张从大到小
        pair_value = values[0]
        pair_cards = [c for c in cards if c.value == pair_value]
        kickers = sorted([c for c in cards if c.value != pair_value], key=lambda x: x.value, reverse=True)
        return pair_cards + kickers
    
    elif hand_rank == 2:  # 两对：先大对子再小对子，然后单张
        high_pair_value = values[0]
        low_pair_value = values[1]
        kicker_value = values[2]
        
        high_pair = [c for c in cards if c.value == high_pair_value]
        low_pair = [c for c in cards if c.value == low_pair_value]
        kicker = [c for c in cards if c.value == kicker_value]
        
        return high_pair + low_pair + kicker
    
    elif hand_rank == 3:  # 三条：三条在前，然后单张从大到小
        three_value = values[0]
        three_cards = [c for c in cards if c.value == three_value]
        kickers = sorted([c for c in cards if c.value != three_value], key=lambda x: x.value, reverse=True)
        return three_cards + kickers
    
    elif hand_rank in [4, 8, 9]:  # 顺子、同花顺、皇家顺：按顺序排列
        # 注意A-2-3-4-5这种特殊情况
        if 14 in values and 2 in values and 3 in values and 4 in values and 5 in values:
            # A-2-3-4-5顺子，A应该在最后面
            ace = [c for c in cards if c.value == 14][0]
            other_cards = sorted([c for c in cards if c.value != 14], key=lambda x: x.value)
            return other_cards + [ace]
        else:
            # 正常顺子，从小到大排序
            return sorted(cards, key=lambda x: x.value)
    
    elif hand_rank == 6:  # 葫芦：三条在前，然后对子
        three_value = values[0]
        pair_value = values[1]
        
        three_cards = [c for c in cards if c.value == three_value]
        pair_cards = [c for c in cards if c.value == pair_value]
        
        return three_cards + pair_cards
    
    # 默认情况：按牌面值从大到小排序
    return sorted(cards, key=lambda x: x.value, reverse=True)

def sort_hand_with_joker_special(cards, jokers):
    """有鬼牌时的特殊排序"""
    # 评估手牌
    eval_result = _evaluate_normal_hand(cards)
    hand_rank = eval_result[0]
    values = eval_result[1]
    
    # 根据牌型排序
    if hand_rank == 10:  # 五条：先万能牌，然后四条
        # 找出四条的值
        counts = Counter([c.value for c in cards])
        four_value = max(counts.items(), key=lambda x: (x[1], x[0]))[0]
        
        four_cards = [c for c in cards if c.value == four_value]
        joker_cards = jokers
        
        return joker_cards + four_cards
    
    elif hand_rank in [4, 8, 9]:  # 顺子、同花顺、皇家顺：按顺序排列，万能牌放在它替代的位置
        # 找出顺子的值
        straight_values = values
        
        # 创建排序后的手牌
        sorted_cards = []
        for value in straight_values:
            # 找对应值的牌
            card = next((c for c in cards if c.value == value), None)
            if card:
                sorted_cards.append(card)
            else:
                # 这个位置应该是万能牌替代的
                sorted_cards.append(jokers[0])
                jokers = jokers[1:]  # 移除已使用的万能牌
        
        return sorted_cards
    
    elif hand_rank == 7:  # 四条：先万能牌，然后三条，最后单张
        # 找出三条的值
        counts = Counter([c.value for c in cards])
        three_value = max(counts.items(), key=lambda x: (x[1], x[0]))[0]
        
        three_cards = [c for c in cards if c.value == three_value]
        kicker = [c for c in cards if c.value != three_value][0]
        joker_cards = jokers
        
        return joker_cards + three_cards + [kicker]
    
    elif hand_rank == 6:  # 葫芦：先万能牌，然后大对子再小对子
        # 找出两个对子的值
        counts = Counter([c.value for c in cards])
        pairs = [value for value, count in counts.items() if count >= 2]
        pairs.sort(reverse=True)
        
        high_pair = [c for c in cards if c.value == pairs[0]]
        low_pair = [c for c in cards if c.value == pairs[1]]
        joker_cards = jokers
        
        return joker_cards + high_pair + low_pair
    
    elif hand_rank == 5:  # 同花：先万能牌，然后按牌面值从大到小排序
        joker_cards = jokers
        normal_sorted = sorted([c for c in cards], key=lambda x: x.value, reverse=True)
        return joker_cards + normal_sorted
    
    elif hand_rank == 3:  # 三条：先万能牌，然后对子，最后单张从大到小
        # 找出对子的值
        counts = Counter([c.value for c in cards])
        pair_value = max(counts.items(), key=lambda x: (x[1], x[0]))[0]
        
        pair_cards = [c for c in cards if c.value == pair_value]
        kickers = sorted([c for c in cards if c.value != pair_value], key=lambda x: x.value, reverse=True)
        joker_cards = jokers
        
        return joker_cards + pair_cards + kickers
    
    elif hand_rank == 1:  # 对子：先万能牌，然后按牌面值从大到小排序
        joker_cards = jokers
        normal_sorted = sorted([c for c in cards], key=lambda x: x.value, reverse=True)
        return joker_cards + normal_sorted
    
    # 默认情况：先万能牌，然后按牌面值从大到小排序
    joker_cards = jokers
    normal_sorted = sorted([c for c in cards], key=lambda x: x.value, reverse=True)
    return joker_cards + normal_sorted

class WildFiveGame:
    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.deck = Deck()
        self.community_cards = []  # 2张公共牌
        self.player_hand = []  # 5张玩家手牌
        self.dealer_hand = []  # 5张庄家手牌
        self.ante = 0
        self.bonus = 0
        self.wild5 = 0
        self.progressive = 0
        self.ppair = 0
        self.play_bet = 0
        self.stage = "pre_flop"  # pre_flop, decision, dealer_draw, showdown
        self.folded = False
        self.player_discard = None  # 玩家选择的弃牌
        self.dealer_discard = None  # 庄家选择的弃牌
        self.cards_revealed = {
            "player": [False, False, False, False, False],
            "dealer": [False, False, False, False, False],
            "community": [False, False]
        }
        # 加载Jackpot金额
        self.jackpot_initial, self.jackpot_amount = load_jackpot()
        # 新增：记录牌序信息
        self.cut_position = self.deck.start_pos
        self.card_sequence = self.deck.card_sequence
        # 新增：存储最佳公共牌选择
        self.player_used_community = None
        self.dealer_used_community = None
        # 新增：存储Joker替换信息
        self.player_joker_replacements = []
        self.dealer_joker_replacements = []
        # 新增：存储排序后的手牌
        self.player_sorted_hand = []
        self.dealer_sorted_hand = []
    
    def deal_initial(self):
        """发初始牌：玩家5张，庄家5张，公共牌2张"""
        self.player_hand = self.deck.deal(5)
        self.dealer_hand = self.deck.deal(5)
        self.community_cards = self.deck.deal(2)
        
    def evaluate_hands(self):
        """评估玩家和庄家的最终手牌（考虑弃牌和公共牌）"""
        # 玩家最终手牌
        player_final_hand = self.player_hand.copy()
        if self.player_discard is not None:
            # 玩家弃了一张牌，使用一张公共牌
            player_final_hand.remove(self.player_discard)

            # 找出最佳公共牌选择
            best_eval = None
            best_community = None
            best_replacement = []

            for community_card in self.community_cards:
                test_hand = player_final_hand + [community_card]
                eval_result, _, replacement = find_best_5(test_hand)

                if best_eval is None or eval_result[0] > best_eval[0] or (
                    eval_result[0] == best_eval[0] and _compare_hands(eval_result[1], best_eval[1]) > 0
                ):
                    best_eval = eval_result
                    best_community = community_card
                    best_replacement = replacement

            player_final_hand.append(best_community)
            self.player_used_community = best_community
            self.player_joker_replacements = best_replacement

        # 庄家最终手牌
        dealer_final_hand = self.dealer_hand.copy()
        if self.dealer_discard is not None:
            # 庄家弃了一张牌，使用一张公共牌
            dealer_final_hand.remove(self.dealer_discard)

            # 找出最佳公共牌选择
            best_eval = None
            best_community = None
            best_replacement = []

            # 注意：**允许**庄家使用与玩家相同的公共牌（不再跳过 player_used_community）
            for community_card in self.community_cards:
                test_hand = dealer_final_hand + [community_card]
                eval_result, _, replacement = find_best_5(test_hand)

                if best_eval is None or eval_result[0] > best_eval[0] or (
                    eval_result[0] == best_eval[0] and _compare_hands(eval_result[1], best_eval[1]) > 0
                ):
                    best_eval = eval_result
                    best_community = community_card
                    best_replacement = replacement

            dealer_final_hand.append(best_community)
            self.dealer_used_community = best_community
            self.dealer_joker_replacements = best_replacement

        player_eval, player_best, player_replacement = find_best_5(player_final_hand)
        dealer_eval, dealer_best, dealer_replacement = find_best_5(dealer_final_hand)

        # 更新Joker替换信息（以评估结果为准）
        self.player_joker_replacements = player_replacement
        self.dealer_joker_replacements = dealer_replacement

        # 排序手牌，保存供 GUI 使用
        self.player_sorted_hand = sort_hand_with_joker(player_best, player_replacement)
        self.dealer_sorted_hand = sort_hand_with_joker(dealer_best, dealer_replacement)

        return player_eval, player_best, dealer_eval, dealer_best
    
    def evaluate_current_hand(self, cards):
        """评估当前手牌"""
        if len(cards) < 5:
            return None
        eval_result, _, _ = find_best_5(cards)
        return eval_result

    def dealer_house_way(self):
        """庄家根据 house way 规则决定是否弃牌。
        返回要弃掉的 Card 对象，或返回 None 表示站着（不弃牌）。
        """
        eval_result = self.evaluate_current_hand(self.dealer_hand)
        if eval_result is None:
            return None

        hand_rank = eval_result[0]

        # pat five-card hands: Straight(4), Flush(5), Full House(6), Straight Flush(8), Royal Flush(9), Five of a kind(10)
        if hand_rank in (4, 5, 6, 8, 9, 10):
            # 已成型的五张牌 -> 站着，不弃牌
            return None

        # 优先检查 four-to-a-flush（必须是正好 4 张同花，5 张同花已经被上面拦截）
        discard = self._find_discard_for_four_flush()
        if discard:
            return discard

        # 其次检查 four-to-an-outside-straight（不包含 J-Q-K-A）
        discard = self._find_discard_for_four_outside_straight()
        if discard:
            return discard

        # 否则对 High Card / Pair / Two Pair / Trips / Four of a Kind -> 弃掉最低的 singleton
        return self._get_lowest_singleton_card()
        
    def _find_discard_for_four_flush(self):
        """若存在正好四张同花（考虑鬼牌作为万能牌），返回应该弃掉的那张卡（即不是那四张的那张）。
        如果不存在则返回 None。
        """
        # 分离鬼牌和普通牌
        jokers = [c for c in self.dealer_hand if getattr(c, 'is_joker', False)]
        non_joker_cards = [c for c in self.dealer_hand if not getattr(c, 'is_joker', False)]
        
        # 统计各花色的数量（包括鬼牌可以补充到任何花色）
        suit_counts = {}
        for card in non_joker_cards:
            suit = card.suit
            suit_counts[suit] = suit_counts.get(suit, 0) + 1
        
        joker_count = len(jokers)
        
        # 检查每个花色，看是否可以通过鬼牌补充形成四张同花
        for suit, count in suit_counts.items():
            total_count = count + joker_count
            if total_count >= 4:
                # 找到不是该花色的那张卡（优先弃非鬼牌）
                for card in self.dealer_hand:
                    if not getattr(card, 'is_joker', False) and card.suit != suit:
                        return card
                # 如果没有找到非鬼牌的非该花色卡，则弃一张鬼牌
                if jokers:
                    return jokers[0]
        
        return None

    def _find_discard_for_four_outside_straight(self):
        """检测是否存在 four-to-an-outside-straight（4 张连续的牌，考虑鬼牌作为万能牌），
        若存在返回应该弃掉的那张 Card（即不属于这 4 张的那张），否则返回 None。
        """
        # 分离鬼牌和普通牌
        jokers = [c for c in self.dealer_hand if getattr(c, 'is_joker', False)]
        non_joker_cards = [c for c in self.dealer_hand if not getattr(c, 'is_joker', False)]
        
        if len(non_joker_cards) + len(jokers) < 4:
            return None
        
        # 获取所有牌的值（包括鬼牌可以代表任何值）
        values = sorted([c.value for c in non_joker_cards])
        joker_count = len(jokers)
        
        # 尝试找到4张连续的值
        for i in range(len(values) - 2):  # 减少循环次数
            # 尝试用鬼牌填补空缺
            sequence = [values[i]]
            jokers_used = 0
            
            # 构建可能的连续序列
            for j in range(i + 1, len(values)):
                gap = values[j] - sequence[-1]
                
                # 如果差距大于1，需要用鬼牌填补
                while gap > 1 and jokers_used < joker_count:
                    sequence.append(sequence[-1] + 1)
                    jokers_used += 1
                    gap = values[j] - sequence[-1]
                
                if gap == 1:
                    sequence.append(values[j])
                elif gap > 1:
                    break  # 无法形成连续序列
            
            # 如果序列长度不足，用鬼牌补充到最后
            while len(sequence) < 4 and jokers_used < joker_count:
                sequence.append(sequence[-1] + 1 if sequence else 14)  # 从最高值开始
                jokers_used += 1
            
            # 检查是否形成了4张连续且不是J-Q-K-A
            if len(sequence) >= 4:
                # 检查是否包含J-Q-K-A (11,12,13,14)
                has_royal = any(v >= 11 for v in sequence[-4:])
                if not has_royal or sequence[-4] != 11:  # 不是J-Q-K-A
                    # 找出不在序列中的牌
                    sequence_set = set(sequence[-4:])
                    for card in self.dealer_hand:
                        if not getattr(card, 'is_joker', False) and card.value not in sequence_set:
                            return card
                    # 如果没有找到非鬼牌的非序列卡，则弃一张鬼牌
                    if jokers:
                        return jokers[0]
        
        return None
    
    def _get_lowest_singleton_card(self):
        """返回应该弃掉的最低的 singleton（单张）。
        规则：
        - 对于 High Card：5 张都是单张 -> 弃最低那张；
        - 对于 Pair / Two Pair / Trips / Quads：找到不属于成套（count>1）的单张，弃最低的那一张；
        - 若没有明显的 singleton（极少数异常情况），退回弃最低的非 Joker 卡或最低卡。
        """
        # 忽略 Joker 参与统计（把 Joker 视为特殊牌，通常不会作为 singleton 被弃；若你希望 Joker 被优先弃掉可调整）
        non_joker_cards = [c for c in self.dealer_hand if not getattr(c, 'is_joker', False)]
        if not non_joker_cards:
            # 若全是 Joker（非常罕见），直接弃第一张 Joker
            return self.dealer_hand[0] if self.dealer_hand else None

        vals = [c.value for c in non_joker_cards]
        counts = Counter(vals)

        # 找到单张（count == 1）
        singleton_cards = [c for c in non_joker_cards if counts[c.value] == 1]
        if singleton_cards:
            # 弃掉值最小的单张
            return min(singleton_cards, key=lambda x: x.value)

class WildFiveGUI(tk.Tk):
    def __init__(self, initial_balance, username):
        super().__init__()
        self.title("Wild Five Poker")
        self.geometry("1220x730+50+10")
        self.resizable(0,0)
        self.configure(bg='#35654d')
        
        self.username = username
        self.balance = initial_balance
        self.game = WildFiveGame()
        self.card_images = {}
        self.animation_queue = []
        self.animation_in_progress = False
        self.card_positions = {}
        self.active_card_labels = []  # 追踪所有活动中的卡片标签
        self.selected_chip = None  # 当前选中的筹码
        self.chip_buttons = []  # 筹码按钮列表
        self.last_win = 0
        self.auto_reset_timer = None
        self.buttons_disabled = False  # 跟踪按钮是否被禁用
        self.win_details = {
            "ante": 0,
            "bonus": 0,
            "wild5": 0,
            "progressive": 0,
            "play": 0
        }
        self.bet_widgets = {}  # 存储下注显示控件
        self.player_selected_card = None  # 玩家选择的要弃的牌
        self.player_selected_label = None  # 玩家选择的要弃的牌的标签
        self.auto_showdown = False  # 自动摊牌标志
        self.player_discard_frame = None  # 玩家弃牌区域
        self.dealer_discard_frame = None  # 庄家弃牌区域
        
        self._load_assets()
        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def show_game_instructions(self):
        """显示游戏规则说明"""
        # 创建自定义弹窗
        win = tk.Toplevel(self)
        win.title("游戏规则")
        win.geometry("650x600+80+20")  # 增加窗口高度以容纳更多内容
        win.resizable(False, False)
        win.configure(bg='#F0F0F0')
        
        # 创建主框架
        main_frame = tk.Frame(win, bg='#F0F0F0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建画布用于滚动
        canvas = tk.Canvas(main_frame, bg='#F0F0F0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        # 创建内部框架放置所有内容
        content_frame = tk.Frame(canvas, bg='#F0F0F0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        # 游戏规则文本
        rules_text = """
        Wild Five Poker 游戏规则

        1. 游戏开始前下注:
        - Ante: 基础下注 (最少$5)
        - Bonus: 红利押注 (最终牌型)
        - Wild 5: 边注 (原始的5张牌)
        - PPair: 边注 (公共牌对子)
        - Progressive: 边注 ($1)

        2. 游戏流程:
        a. 初始发牌:
            - 玩家和庄家各发5张牌
            - 发2张公共牌

        b. 玩家决策:
            - 查看手牌后选择:
                * 弃牌: 放弃所有下注
                * 选择是否弃一张牌并获取公共牌的其中一张
                * 下注Play: 下注Ante的1-3倍

        c. 庄家决策:
            - 根据house way规则决定是否弃牌

        d. 摊牌:
            - 比较玩家和庄家的最佳五张牌
                (先比较手牌 再比较踢脚)
            - 需要注意的是 公共牌只能二选一
            - 结算所有下注

        3. 赔付规则:
            - Ante 
                - 庄家手牌是对子或以上
                    - 并且玩家手牌比庄家强 以1:1结算
                    - 但玩家手牌比庄家差 输
                    - 但玩家手牌和庄家持平 平局
                - 庄家手牌是高牌
                    - 无论结果如何 都以平局结算
            - Play
                - 玩家手牌比庄家强 以1:1结算
                - 玩家手牌比庄家差 输
                - 玩家手牌和庄家持平 平局
            - Bonus
                - 玩家牌型比庄家强 根据下方赔率结算
                - 玩家牌型比庄家差 输
                - 玩家牌型和庄家持平 平局
            - Wild 5
                - 只看原始的5张手牌
                - 不和庄家做任何比较
                - 根据下方赔率结算
                - 在玩家第一次开牌后就做赔付
            - PPair
                - 只看2张公共牌是否为对子
                - 不和庄家做任何比较
                - 根据下方赔率结算
                - 无论玩家是否弃牌，只要下注即有效
            - Progressive
                - 只看最后的5张手牌
                - 每局总下注的10%会自动加入Progressive奖池
                - Progressive奖金会从奖池中扣除
                - Progressive奖池有最低保证金额
                - 中奖时会弹出提示窗口通知玩家

        4. 万能牌规则:
        - 鬼牌(JOKER)可作为任何牌使用
        - 系统会自动选择对牌型最有利的替换方式
        - 如果使用公共牌中的万能牌，会显示具体替换的牌
        """
        
        rules_label = tk.Label(
            content_frame, 
            text=rules_text,
            font=('微软雅黑', 11),
            bg='#F0F0F0',
            justify=tk.LEFT,
            padx=10,
            pady=10
        )
        rules_label.pack(fill=tk.X, padx=10, pady=5)
        
        # 赔率表
        tk.Label(
            content_frame, 
            text="赔率表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        odds_frame = tk.Frame(content_frame, bg='#F0F0F0')
        odds_frame.pack(fill=tk.X, padx=20, pady=5)

        headers = ["牌型", "Bonus赔率", "Wild 5赔率", "Progressive奖金"]
        odds_data = [
            ("五条", "100:1", "1000:1", "100% Progressive奖池"),
            ("同花大顺", "50:1", "500:1", "50% Progressive奖池"),
            ("同花顺", "10:1", "250:1", "20% Progressive奖池"),
            ("四条", "5:1", "100:1", "$3,000"),
            ("葫芦", "3:1", "50:1", "$2,000"),
            ("同花", "2:1", "25:1", "$1,000"),
            ("顺子", "1:1", "10:1", "-"),
            ("三条", "平局", "5:1", "-"),
            ("两对", "平局", "5:1", "-"),
            ("对子", "平局", "-", "-"),
            ("高牌", "平局", "-", "-")
        ]

        # 表头
        for col, h in enumerate(headers):
            tk.Label(
                odds_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # 表格内容
        for r, row_data in enumerate(odds_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    odds_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配每列宽度，让 sticky='nsew' 生效
        for c in range(len(headers)):
            odds_frame.columnconfigure(c, weight=1)
        
        # 添加PPair赔率表
        tk.Label(
            content_frame, 
            text="PPair赔率表",
            font=('微软雅黑', 12, 'bold'),
            bg='#F0F0F0'
        ).pack(fill=tk.X, padx=10, pady=(20, 5), anchor='w')
        
        ppair_frame = tk.Frame(content_frame, bg='#F0F0F0')
        ppair_frame.pack(fill=tk.X, padx=20, pady=5)

        ppair_headers = ["公共牌对子类型", "赔率"]
        ppair_data = [
            ("A-A", "30:1"),
            ("A-K (同花)", "25:1"),
            ("A-Q (同花) 或 A-J (同花)", "20:1"),
            ("A-K", "15:1"),
            ("K-K, Q-Q, 或 J-J", "10:1"),
            ("其中一张为Joker", "8:1"),
            ("A-Q 或 A-J", "5:1"),
            ("其他对子 (10-10 到 2-2)", "3:1")
        ]

        # PPair表头
        for col, h in enumerate(ppair_headers):
            tk.Label(
                ppair_frame,
                text=h,
                font=('微软雅黑', 10, 'bold'),
                bg='#4B8BBE',
                fg='white',
                padx=10, pady=5,
                anchor='center',
                justify='center'
            ).grid(row=0, column=col, sticky='nsew', padx=1, pady=1)

        # PPair表格内容
        for r, row_data in enumerate(ppair_data, start=1):
            bg = '#E0E0E0' if r % 2 == 0 else '#F0F0F0'
            for c, txt in enumerate(row_data):
                tk.Label(
                    ppair_frame,
                    text=txt,
                    font=('微软雅黑', 10),
                    bg=bg,
                    padx=10, pady=5,
                    anchor='center',
                    justify='center'
                ).grid(row=r, column=c, sticky='nsew', padx=1, pady=1)

        # 平均分配PPair表每列宽度
        for c in range(len(ppair_headers)):
            ppair_frame.columnconfigure(c, weight=1)
        
        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 添加关闭按钮
        close_btn = ttk.Button(
            win,
            text="关闭",
            command=win.destroy
        )
        close_btn.pack(pady=10)
        
        # 绑定鼠标滚轮滚动
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
    def on_close(self):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
        self.destroy()
        self.quit()
        
    def _load_assets(self):
        card_size = (100, 140)
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        card_dir = os.path.join(parent_dir, 'A_Tools', 'Card')
        
        # 花色映射：将符号映射为英文名称
        suit_mapping = {
            '♠': 'Spade',
            '♥': 'Heart',
            '♦': 'Diamond',
            '♣': 'Club',
            'JOKER': 'JOKER'
        }

        self.original_images = {}
        
        # 加载背面图片
        back_path = os.path.join(card_dir, 'Background.png')
        try:
            back_img_orig = Image.open(back_path)  # 原始尺寸
            self.original_images["back"] = back_img_orig  # 保存原始图像
            back_img = back_img_orig.resize(card_size)  # 缩放
            self.back_image = ImageTk.PhotoImage(back_img)
        except Exception as e:
            print(f"Error loading back image: {e}")
            # 创建黑色背景
            img_orig = Image.new('RGB', card_size, 'black')
            self.original_images["back"] = img_orig
            self.back_image = ImageTk.PhotoImage(img_orig)
        
        # 加载扑克牌图片
        for suit in SUITS:
            for rank in RANKS:
                # 获取映射后的文件名
                suit_name = suit_mapping.get(suit, suit)
                if suit == 'JOKER':
                    filename = f"JOKER-A.png"  # 鬼牌文件名
                else:
                    filename = f"{suit_name}{rank}.png"
                path = os.path.join(card_dir, filename)
                
                try:
                    if os.path.exists(path):
                        img = Image.open(path)
                        # 保存原始图像
                        self.original_images[(suit, rank)] = img
                        # 创建缩放后的图像用于显示
                        img_resized = img.resize(card_size)
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_resized)
                    else:
                        # 创建占位图片
                        img_orig = Image.new('RGB', card_size, 'blue')
                        draw = ImageDraw.Draw(img_orig)
                        # 绘制卡片文本
                        if suit == 'JOKER':
                            text = "JOKER"
                        else:
                            text = f"{rank}{suit}"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()
                        text_width, text_height = draw.textsize(text, font=font)
                        x = (card_size[0] - text_width) / 2
                        y = (card_size[1] - text_height) / 2
                        draw.text((x, y), text, fill="white", font=font)
                        
                        # 保存原始图像
                        self.original_images[(suit, rank)] = img_orig
                        # 创建缩放后的图像用于显示
                        self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                except Exception as e:
                    print(f"Error loading card image {path}: {e}")
                    # 创建占位图片
                    img_orig = Image.new('RGB', card_size, 'red')
                    draw = ImageDraw.Draw(img_orig)
                    text = "Error"
                    try:
                        font = ImageFont.truetype("arial.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                    text_width, text_height = draw.textsize(text, font=font)
                    x = (card_size[0] - text_width) / 2
                    y = (card_size[1] - text_height) / 2
                    draw.text((x, y), text, fill="white", font=font)
                    
                    # 保存原始图像
                    self.original_images[(suit, rank)] = img_orig
                    # 创建缩放后的图像用于显示
                    self.card_images[(suit, rank)] = ImageTk.PhotoImage(img_orig)
                    
    def add_chip_to_bet(self, bet_type):
        """添加筹码到下注区域"""
        if not self.selected_chip:
            return
            
        # 获取筹码金额
        chip_value = float(self.selected_chip.replace('$', '').replace('K', '000'))
        
        # 更新对应的下注变量
        if bet_type == "ante":
            current = float(self.ante_var.get())
            new_ante = int(current + chip_value)
            self.ante_var.set(str(new_ante))
            # Bonus与Ante同步
            self.bonus_var.set(str(new_ante))
        elif bet_type == "wild5":
            current = float(self.wild5_var.get())
            self.wild5_var.set(str(int(current + chip_value)))
        elif bet_type == "ppair":  # 添加PPair处理
            current = float(self.ppair_var.get())
            self.ppair_var.set(str(int(current + chip_value)))
        
    def select_chip(self, chip_text):
        """选择筹码，并更新筹码的高亮状态"""
        self.selected_chip = chip_text
        # 1. 重置所有筹码的边框
        for chip in self.chip_buttons:
            # 删除之前的高亮
            chip.delete("highlight")
            # 找到 oval 的 id，重画默认黑色边框
            for item_id in chip.find_all():
                if chip.type(item_id) == 'oval':
                    x1, y1, x2, y2 = chip.coords(item_id)
                    chip.create_oval(x1, y1, x2, y2, outline='black', width=2)
                    break

        # 2. 给选中的筹码加金色高亮
        for chip in self.chip_buttons:
            text_id = None
            oval_id = None
            # 先分别找到 text 和 oval 的 id
            for item_id in chip.find_all():
                if chip.type(item_id) == 'text':
                    text_id = item_id
                elif chip.type(item_id) == 'oval':
                    oval_id = item_id
            # 如果找到了文字项，并且内容匹配
            if text_id and chip.itemcget(text_id, 'text') == chip_text:
                # 拿到对应的 oval 坐标
                x1, y1, x2, y2 = chip.coords(oval_id)
                chip.create_oval(x1, y1, x2, y2, outline='gold', width=3, tags="highlight")
                break
    
    def update_balance(self):
        self.balance_label.config(text=f"余额: ${self.balance:.2f}")
        if self.username != 'Guest':
            update_balance_in_json(self.username, self.balance)
    
    def update_hand_labels(self):
        """更新玩家和庄家的手牌标签显示牌型（遵循用户要求的格式）"""
        # 玩家牌型（只有在摊牌/弃牌/已翻开时才显示具体牌型）
        player_eval = self.game.evaluate_current_hand(self.game.player_hand)
        player_hand_name = HAND_RANK_NAMES[player_eval[0]] if player_eval else ""

        player_suffix = ""
        player_comm = getattr(self.game, 'player_used_community', None)
        player_joker = getattr(self.game, 'player_joker_replacements', []) or []

        # 规则：若使用了公共牌并且该公共牌本身是万能牌 -> 显示 公共万能牌：具体牌
        if player_comm and getattr(player_comm, 'is_joker', False):
            # 查找这张公共万能牌被替换成了什么牌
            replacement_for_public = None
            for i, card in enumerate(player_joker):
                # 假设替换牌列表中的顺序对应万能牌的顺序
                replacement_for_public = card
                break
            
            if replacement_for_public:
                player_suffix = f" ≈≈>> 公共万能牌： {replacement_for_public}"
            else:
                player_suffix = f" ≈≈>> 公共万能牌： {player_comm}"
        # 否则若手牌含万能牌（替换列表非空） -> 显示 万能牌 列表
        elif player_joker:
            player_suffix = f" ≈≈>> 万能牌： {', '.join([str(c) for c in player_joker])}"

        # 仅在合适阶段显示牌型说明
        if self.game.stage == "showdown" or self.game.folded or any(self.game.cards_revealed.get("player", [])):
            self.player_label.config(text=f"玩家 - {player_hand_name}{player_suffix}" if player_hand_name else "玩家")
        else:
            self.player_label.config(text="玩家")

        # ----- 庄家 -----
        dealer_eval = self.game.evaluate_current_hand(self.game.dealer_hand)
        dealer_hand_name = HAND_RANK_NAMES[dealer_eval[0]] if dealer_eval else ""

        dealer_suffix = ""
        dealer_comm = getattr(self.game, 'dealer_used_community', None)
        dealer_joker = getattr(self.game, 'dealer_joker_replacements', []) or []

        # 同样的优先逻辑：公共牌为万能 => 显示 公共万能牌：具体牌；否则若有万能牌替换则显示 万能牌 列表
        if dealer_comm and getattr(dealer_comm, 'is_joker', False):
            # 查找这张公共万能牌被替换成了什么牌
            replacement_for_public = None
            for i, card in enumerate(dealer_joker):
                # 假设替换牌列表中的顺序对应万能牌的顺序
                replacement_for_public = card
                break
            
            if replacement_for_public:
                dealer_suffix = f" ≈≈>> 公共万能牌： {replacement_for_public}"
            else:
                dealer_suffix = f" ≈≈>> 公共万能牌： {dealer_comm}"
        elif dealer_joker:
            dealer_suffix = f" ≈≈>> 万能牌： {', '.join([str(c) for c in dealer_joker])}"

        if self.game.stage == "showdown" or self.game.folded or any(self.game.cards_revealed.get("dealer", [])):
            self.dealer_label.config(text=f"庄家 - {dealer_hand_name}{dealer_suffix}" if dealer_hand_name else "庄家")
        else:
            self.dealer_label.config(text="庄家")
            
    def disable_action_buttons(self):
        """禁用所有操作按钮"""
        self.buttons_disabled = True
        for widget in self.action_frame.winfo_children():
            if widget.winfo_exists() and isinstance(widget, tk.Button):
                widget.config(state=tk.DISABLED)
    
    def enable_action_buttons(self):
        """启用所有操作按钮"""
        self.buttons_disabled = False
        for widget in self.action_frame.winfo_children():
            if widget.winfo_exists() and isinstance(widget, tk.Button):
                widget.config(state=tk.NORMAL)
    
    def start_game(self):
        """开始一局：校验下注、支付、发牌并初始化UI状态。
        修改点：清除牌区时保留弃牌区标题（不会把'玩家弃牌'/'庄家弃牌'删掉）。
        """
        # 重置上局获胜金额显示
        self.last_win_label.config(text="上局获胜: $0.00")

        try:
            self.ante = int(self.ante_var.get())
            self.bonus = int(self.bonus_var.get())
            self.wild5 = int(self.wild5_var.get())
            self.ppair = int(self.ppair_var.get())
            self.progressive = 10 if self.progressive_var.get() else 0
        except ValueError:
            messagebox.showerror("错误", "下注金额必须为整数")
            return

        # Ante 最少 5
        if self.ante < 5:
            messagebox.showerror("错误", "Ante至少需要5块")
            return

        # 计算总下注（暂时以最小 Play=Ante 作为保留）
        play_bet_min = self.ante
        total_bet = self.ante + self.bonus + self.wild5 + self.progressive + self.ppair + play_bet_min

        if total_bet > self.balance:
            messagebox.showerror("错误", f"余额不足以支付所有下注！需要${total_bet}，当前余额${self.balance}")
            return

        # 扣除 ante/bonus/wild5/progressive（Play 在玩家决策时再扣）
        self.balance -= (self.ante + self.bonus + self.wild5 + self.progressive + self.ppair)
        self.update_balance()

        # 更新本局下注显示
        self.current_bet_label.config(text=f"本局下注: ${self.ante + self.bonus + self.wild5 + self.ppair + self.progressive:.2f}")

        # 禁用开始/重设按钮
        try:
            self.start_button.config(state=tk.DISABLED)
        except:
            pass
        try:
            self.reset_bets_button.config(state=tk.DISABLED)
        except:
            pass

        # 重置游戏逻辑并发初始牌
        self.game.reset_game()
        self.game.deal_initial()
        self.game.ante = self.ante
        self.game.bonus = self.bonus
        self.game.wild5 = self.wild5
        self.game.ppair = self.ppair
        self.game.progressive = self.progressive

        # 清除 各牌区 的“牌”widget —— 注意：**保留弃牌区里的标题 label**（通过检查 widget 是否有 .card 属性）
        for widget in list(self.dealer_cards_frame.winfo_children()):
            try:
                widget.destroy()
            except:
                pass
        for widget in list(self.community_cards_frame.winfo_children()):
            try:
                widget.destroy()
            except:
                pass
        for widget in list(self.player_cards_frame.winfo_children()):
            try:
                widget.destroy()
            except:
                pass

        # 对弃牌区：仅销毁真正的卡片（那些我们给 card label 设置了 .card 属性），保留其它（例如"玩家弃牌"/"庄家弃牌"标题）
        try:
            for widget in list(self.player_discard_frame.winfo_children()):
                try:
                    if hasattr(widget, "card"):
                        widget.destroy()
                except:
                    pass
        except:
            pass

        try:
            for widget in list(self.dealer_discard_frame.winfo_children()):
                try:
                    if hasattr(widget, "card"):
                        widget.destroy()
                except:
                    pass
        except:
            pass

        # 重置动画/活动卡片跟踪
        self.animation_queue = []
        self.animation_in_progress = False
        self.active_card_labels = []

        # 初始化卡片位置 / 重新生成动画队列（保留你原本的 card_positions 逻辑）
        # （下面的部分和原实现一致，确保每张卡按坐标发出）
        self.card_positions = {}
        # 公共牌
        for i in range(2):
            card_id = f"community_{i}"
            self.card_positions[card_id] = {
                "current": (50, 50),
                "target": (i * 125, 0)
            }
            self.animation_queue.append(card_id)
        # 玩家牌
        for i in range(5):
            card_id = f"player_{i}"
            self.card_positions[card_id] = {
                "current": (50, 50),
                "target": (i * 105, 0)
            }
            self.animation_queue.append(card_id)
        # 庄家牌
        for i in range(5):
            card_id = f"dealer_{i}"
            self.card_positions[card_id] = {
                "current": (50, 50),
                "target": (i * 105, 0)
            }
            self.animation_queue.append(card_id)

        # 开始发牌动画
        self.animate_deal()

        # 更新 stage、禁用下注区域交互
        self.stage_label.config(text="初始发牌")
        try:
            self.ante_display.unbind("<Button-1>")
            self.bonus_display.unbind("<Button-1>")
            self.wild5_display.unbind("<Button-1>")
            self.progressive_cb.config(state=tk.DISABLED)
            for chip in self.chip_buttons:
                chip.unbind("<Button-1>")
        except:
            pass
    
    def animate_deal(self):
        if not self.animation_queue:
            self.animation_in_progress = False
            # 发牌动画完成后
            self.after(500, self.reveal_player_cards)
            return
            
        self.animation_in_progress = True
        card_id = self.animation_queue.pop(0)
        
        # 创建卡片标签
        if card_id.startswith("community"):
            frame = self.community_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.community_cards[idx] if idx < len(self.game.community_cards) else None
        elif card_id.startswith("player"):
            frame = self.player_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.player_hand[idx] if idx < len(self.game.player_hand) else None
        elif card_id.startswith("dealer"):
            frame = self.dealer_cards_frame
            idx = int(card_id.split("_")[1])
            card = self.game.dealer_hand[idx] if idx < len(self.game.dealer_hand) else None
        
        # 创建卡片标签
        card_label = tk.Label(frame, image=self.back_image, bg='#2a4a3c')
        card_label.place(
            x=self.card_positions[card_id]["current"][0],
            y=self.card_positions[card_id]["current"][1] + 20
        )
        
        # 存储卡片信息
        card_label.card_id = card_id
        card_label.card = card
        card_label.is_face_up = False
        card_label.is_moving = True
        card_label.target_pos = self.card_positions[card_id]["target"]
        
        # 添加到活动卡片列表
        self.active_card_labels.append(card_label)
        
        # 开始移动动画
        self.animate_card_move(card_label)
    
    def animate_card_move(self, card_label):
        # 检查卡片是否仍然存在
        if not hasattr(card_label, "target_pos") or card_label not in self.active_card_labels:
            return
            
        try:
            current_x, current_y = card_label.winfo_x(), card_label.winfo_y()
            target_x, target_y = card_label.target_pos
            
            # 计算移动方向向量
            dx = target_x - current_x
            dy = target_y - current_y
            distance = math.sqrt(dx**2 + dy**2)
            
            # 如果已经到达目标位置
            if distance < 5:
                card_label.place(x=target_x, y=target_y)
                card_label.is_moving = False
                
                # 如果是回收动画且到达左上角，销毁卡片
                if card_label.target_pos == (50, 50):
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    card_label.destroy()
                    
                self.after(100, self.animate_deal)  # 处理下一张牌
                return
            
            # 计算移动步长
            step_x = dx * 0.2
            step_y = dy * 0.2
            
            # 更新位置
            new_x = current_x + step_x
            new_y = current_y + step_y
            card_label.place(x=new_x, y=new_y)
            
            # 继续动画
            self.after(20, lambda: self.animate_card_move(card_label))
            
        except tk.TclError:
            # 卡片已被销毁，停止动画
            if card_label in self.active_card_labels:
                self.active_card_labels.remove(card_label)
            return
            
    def reveal_player_cards(self):
        """翻开玩家牌（带动画）。在牌全部翻开后，更新牌型并立即进行 Wild5 的即时结算"""
        for i, card_label in enumerate(self.player_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记玩家牌已翻开
                self.game.cards_revealed["player"][i] = True

        # 更新玩家牌型显示
        self.update_hand_labels()

        # 2秒后执行手牌排序
        self.after(2000, self.sort_initial_player_hand)

    def sort_initial_player_hand(self):
        """对玩家的初始手牌进行排序"""
        # 获取玩家手牌
        player_hand = getattr(self.game, 'player_hand', [])
        
        # 分离鬼牌和普通牌
        jokers = [c for c in player_hand if getattr(c, 'is_joker', False)]
        normal_cards = [c for c in player_hand if not getattr(c, 'is_joker', False)]
        
        # 评估手牌以确定最佳排序
        eval_result, replacement = evaluate_hand(player_hand)
        hand_rank = eval_result[0]
        values = eval_result[1]
        
        # 保存Joker替换信息
        self.player_joker_replacements = replacement
        
        # 根据牌型进行排序
        if hand_rank == 10:  # 五条
            # 找出四条的值
            counts = Counter([c.value for c in normal_cards])
            four_value = max(counts.items(), key=lambda x: (x[1], x[0]))[0]
            
            four_cards = [c for c in normal_cards if c.value == four_value]
            joker_cards = jokers
            
            sorted_hand = joker_cards + four_cards
            
        elif hand_rank in [4, 8, 9]:  # 顺子、同花顺、皇家顺
            # 找出顺子的值
            straight_values = values
            
            # 创建排序后的手牌
            sorted_hand = []
            for value in straight_values:
                # 找对应值的牌
                card = next((c for c in normal_cards if c.value == value), None)
                if card:
                    sorted_hand.append(card)
                else:
                    # 这个位置应该是万能牌替代的
                    if jokers:
                        sorted_hand.append(jokers[0])
                        jokers = jokers[1:]  # 移除已使用的万能牌
            
        elif hand_rank == 7:  # 四条
            # 找出三条的值
            counts = Counter([c.value for c in normal_cards])
            three_value = max(counts.items(), key=lambda x: (x[1], x[0]))[0]
            
            three_cards = [c for c in normal_cards if c.value == three_value]
            kicker = [c for c in normal_cards if c.value != three_value][0]
            joker_cards = jokers
            
            sorted_hand = joker_cards + three_cards + [kicker]
            
        elif hand_rank == 6:  # 葫芦
            # 找出两个对子的值
            counts = Counter([c.value for c in normal_cards])
            pairs = [value for value, count in counts.items() if count >= 2]
            pairs.sort(reverse=True)
            
            high_pair = [c for c in normal_cards if c.value == pairs[0]]
            low_pair = [c for c in normal_cards if c.value == pairs[1]]
            joker_cards = jokers
            
            sorted_hand = joker_cards + high_pair + low_pair
            
        elif hand_rank == 5:  # 同花
            joker_cards = jokers
            normal_sorted = sorted(normal_cards, key=lambda x: x.value, reverse=True)
            sorted_hand = joker_cards + normal_sorted
            
        elif hand_rank == 3:  # 三条 - 这是关键修复
            # 找出三条的值
            counts = Counter([c.value for c in normal_cards])
            three_value = values[0]  # 使用评估结果中的三条值
            
            # 分离三条牌和其他牌
            three_cards = [c for c in normal_cards if c.value == three_value]
            kickers = sorted([c for c in normal_cards if c.value != three_value], 
                            key=lambda x: x.value, reverse=True)
            joker_cards = jokers
            
            # 三条在前，然后踢脚牌，Joker放在三条前面
            sorted_hand = joker_cards + three_cards + kickers
            
        elif hand_rank == 2:  # 两对
            high_pair_value = values[0]
            low_pair_value = values[1]
            kicker_value = values[2]
            
            high_pair = [c for c in normal_cards if c.value == high_pair_value]
            low_pair = [c for c in normal_cards if c.value == low_pair_value]
            kicker = [c for c in normal_cards if c.value == kicker_value]
            joker_cards = jokers
            
            sorted_hand = joker_cards + high_pair + low_pair + kicker
            
        elif hand_rank == 1:  # 对子
            pair_value = values[0]
            pair_cards = [c for c in normal_cards if c.value == pair_value]
            kickers = sorted([c for c in normal_cards if c.value != pair_value], 
                            key=lambda x: x.value, reverse=True)
            joker_cards = jokers
            
            sorted_hand = joker_cards + pair_cards + kickers
            
        else:  # 高牌或其他
            joker_cards = jokers
            normal_sorted = sorted(normal_cards, key=lambda x: x.value, reverse=True)
            sorted_hand = joker_cards + normal_sorted
        
        # 保存排序后的手牌
        self.game.player_sorted_hand = sorted_hand
        
        # 先翻面所有玩家牌
        for card_label in self.player_cards_frame.winfo_children():
            if hasattr(card_label, "card") and card_label.is_face_up:
                card_label.config(image=self.back_image)
                card_label.is_face_up = False
        
        # 0.25秒后重新显示排序后的牌
        self.after(250, self.display_sorted_player_hand)

    def display_sorted_player_hand(self):
        """显示排序后的玩家手牌"""
        # 清空当前玩家牌架
        for w in list(self.player_cards_frame.winfo_children()):
            try:
                w.destroy()
            except:
                pass

        # 获取排序后的手牌
        sorted_hand = getattr(self.game, 'player_sorted_hand', []) or []
        
        # 放置排序后的牌
        for i, card in enumerate(sorted_hand):
            card_label = tk.Label(self.player_cards_frame, image=self.back_image, bg='#2a4a3c')
            card_label.place(x=i * 105, y=0)
            card_label.card = card
            card_label.is_face_up = False
            
            # 添加到活动列表
            if card_label not in self.active_card_labels:
                self.active_card_labels.append(card_label)
            
            # 按序翻牌
            self.after(250 + i * 100, lambda cl=card_label: self.flip_card_animation(cl))
        
        # 更新手牌标签显示
        self.update_hand_labels()
        
        # === 立即结算 Wild5 ===
        if not getattr(self, 'wild5_paid', False):
            player_hand = getattr(self.game, 'player_hand', [])
            wild5_bet = getattr(self.game, 'wild5', 0)
            wild5_win = 0
            
            if wild5_bet > 0 and len(player_hand) >= 5:
                # 正确提取牌型等级
                eval_result, _ = evaluate_hand(player_hand)
                player_rank = eval_result[0]  # 现在 player_rank 是一个整数，不是列表
                
                if player_rank in WILD_5_PAYOUT:
                    odds = WILD_5_PAYOUT[player_rank]
                    wild5_win = wild5_bet * (odds + 1)  # 包含本金
                else:
                    wild5_win = 0  # 输

        # 标记已经支付过
        self.wild5_paid = True
        self.wild5_paid_amount = wild5_win
        self.win_details['wild5'] = wild5_win

        # 更新 Wild5 显示 - 使用StringVar设置文本
        try:
            widget = getattr(self, 'wild5_display', None) or self.bet_widgets.get('wild5')
            if widget:
                if wild5_win > wild5_bet:
                    widget.config(bg='gold')
                    self.wild5_var.set(f"{wild5_win}")
                elif wild5_win == wild5_bet and wild5_bet != 0:
                    widget.config(bg='light blue')
                    self.wild5_var.set(f"{wild5_win}")
                else:
                    widget.config(bg='white')
                    if wild5_bet != 0:
                        self.wild5_var.set("未赢")
        except Exception:
            pass

        # 1.5秒后启用决策按钮
        self.after(1500, self.enable_decision_buttons)
    
    def reveal_community_cards(self):
        """翻开公共牌（带动画）"""
        for i, card_label in enumerate(self.community_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记公共牌已翻开
                self.game.cards_revealed["community"][i] = True
    
    def reveal_dealer_cards(self):
        """翻开庄家牌（带动画）"""
        for i, card_label in enumerate(self.dealer_cards_frame.winfo_children()):
            if hasattr(card_label, "card") and not card_label.is_face_up:
                self.flip_card_animation(card_label)
                # 标记庄家牌已翻开
                self.game.cards_revealed["dealer"][i] = True
        
        # 更新庄家牌型
        self.update_hand_labels()
    
    def flip_card_animation(self, card_label):
        """卡片翻转动画"""
        # 获取卡片正面图像
        card = card_label.card
        if card.is_joker:
            front_img = self.card_images.get(('JOKER', 'A'), self.back_image)
        else:
            front_img = self.card_images.get((card.suit, card.rank), self.back_image)
        
        # 创建动画序列
        self.animate_flip(card_label, front_img, 0)
    
    def animate_flip(self, card_label, front_img, step):
        """执行翻转动画"""
        steps = 10  # 动画总步数
        
        if step > steps:
            # 动画结束
            card_label.is_face_up = True
            return
        
        if step <= steps / 2:
            # 第一阶段：从背面翻转到侧面（宽度减小）
            width = 100 - (step * 20)
            if width <= 0:
                width = 1
            # 创建缩放后的背面图像
            back_img = Image.new('RGBA', (width, 140), (0, 0, 0, 0))
            orig_back = self.back_image
            # 这里简化处理，实际应该缩放图片
            card_label.config(image=orig_back)
        else:
            # 第二阶段：从侧面翻转到正面（宽度增加）
            width = (step - steps / 2) * 20
            if width <= 0:
                width = 1
            # 创建缩放后的正面图像
            card_label.config(image=front_img)
        
        # 更新卡片显示
        card_label.place(width=width)
        
        # 下一步
        step += 1
        card_label.after(50, lambda: self.animate_flip(card_label, front_img, step))
    
    def enable_decision_buttons(self):
        """启用玩家决策按钮"""
        # 更新游戏状态
        self.game.stage = "decision"
        self.stage_label.config(text="玩家决策")
        self.status_label.config(text="请选择要弃的牌或直接下注")
        
        # 创建决策按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        buttons_container = tk.Frame(self.action_frame, bg='#2a4a3c')
        buttons_container.pack(expand=True, pady=10)

        self.fold_button = tk.Button(
            buttons_container, text="弃牌", 
            command=lambda: self.player_decision(0), 
            font=('Arial', 14), bg='#F44336', fg='white', width=6
        )
        self.fold_button.pack(side=tk.LEFT, padx=5)
            
        self.bet_1x_button = tk.Button(
            buttons_container, text="1倍", 
            command=lambda: self.player_decision(1), 
            font=('Arial', 14), bg='#2196F3', fg='white', width=6,
            state=tk.DISABLED
        )
        self.bet_1x_button.pack(side=tk.LEFT, padx=5)
            
        self.bet_2x_button = tk.Button(
            buttons_container, text="2倍", 
            command=lambda: self.player_decision(2), 
            font=('Arial', 14), bg='#FF9800', fg='white', width=6,
            state=tk.DISABLED
        )
        self.bet_2x_button.pack(side=tk.LEFT, padx=5)
            
        self.bet_3x_button = tk.Button(
            buttons_container, text="3倍", 
            command=lambda: self.player_decision(3), 
            font=('Arial', 14), bg='#4CAF50', fg='white', width=6,
            state=tk.DISABLED
        )
        self.bet_3x_button.pack(side=tk.LEFT, padx=5)
        
        # 设置Play bet下注范围
        min_bet = self.game.ante
        max_bet = self.game.ante * 3
        
        # 检查余额是否足够支付最大下注
        if self.balance >= max_bet:
            self.bet_3x_button.config(state=tk.NORMAL)
        else:
            self.bet_3x_button.config(state=tk.DISABLED)

        if self.balance >= min_bet * 2:
            self.bet_2x_button.config(state=tk.NORMAL)
        else:
            self.bet_2x_button.config(state=tk.DISABLED)

        if self.balance >= min_bet:
            self.bet_1x_button.config(state=tk.NORMAL)
        else:
            self.bet_1x_button.config(state=tk.DISABLED)

        # 弃牌按钮总是可用
        self.fold_button.config(state=tk.NORMAL)
        
        # 允许玩家选择弃牌
        for card_label in self.player_cards_frame.winfo_children():
            if hasattr(card_label, "card"):
                card_label.bind("<Button-1>", self.select_player_card)

    def select_player_card(self, event):
        """玩家选择要弃的牌"""
        card_label = event.widget
        if not hasattr(card_label, "card"):
            return
            
        # 如果已经选择了这张牌，取消选择
        if self.player_selected_label == card_label:
            card_label.place(y=card_label.winfo_y() - 10)  # 恢复原始位置
            card_label.config(borderwidth=0)
            self.player_selected_label = None
            self.game.player_discard = None
            self.status_label.config(text="已取消选择弃牌")
            return
            
        # 取消之前的选择
        if self.player_selected_label:
            self.player_selected_label.place(y=self.player_selected_label.winfo_y() - 10)  # 恢复原始位置
            self.player_selected_label.config(borderwidth=0)
            
        # 选择新牌
        card_label.place(y=card_label.winfo_y() + 10)  # 下移10px
        card_label.config(borderwidth=3, relief="solid", highlightbackground="red")
        self.player_selected_label = card_label
        self.game.player_discard = card_label.card
        
        self.status_label.config(text=f"已选择弃牌: {card_label.card}")
    
    def player_decision(self, bet_multiplier):

        self.fold_button.config(state=tk.DISABLED)
        self.bet_1x_button.config(state=tk.DISABLED)
        self.bet_2x_button.config(state=tk.DISABLED)
        self.bet_3x_button.config(state=tk.DISABLED)

        """玩家决策：下注或弃牌"""
        if bet_multiplier == 0:  # 弃牌
            self.reveal_community_cards()
            self.game.folded = True
            self.status_label.config(text="您已弃牌。游戏结束。")
            
            # 翻开庄家牌
            self.reveal_dealer_cards()
            
            # 更新庄家牌型
            self.update_hand_labels()

            self.ante_var.set("0")
            self.bonus_var.set("0")
            
            # 结算Progressive/Bonus/Wild5
            winnings = self.calculate_side_bets_only()
            self.last_win = winnings
            
            # 更新余额
            self.balance += winnings
            self.update_balance()
            
            self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")
            
            # 添加重新开始按钮
            for widget in self.action_frame.winfo_children():
                widget.destroy()
                
            restart_btn = tk.Button(
                self.action_frame, text="再来一局", 
                command=self.reset_game, 
                font=('Arial', 14), bg='#2196F3', fg='white', width=15
            )
            restart_btn.pack(pady=10)
            restart_btn.bind("<Button-3>", self.show_card_sequence)
            
            # 设置30秒后自动重置
            self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
            return
        
        # 下注Play bet
        bet_amount = bet_multiplier * self.game.ante
        if bet_amount > self.balance:
            messagebox.showerror("错误", "余额不足以支付下注！")
            return
            
        self.balance -= bet_amount
        self.update_balance()
        self.game.play_bet = bet_amount
        
        # 更新Play bet显示
        self.play_var.set(str(bet_amount))
        
        # 更新本局下注显示
        total_bet = self.ante + self.bonus + self.wild5 + self.progressive + bet_amount
        self.current_bet_label.config(text=f"本局下注: ${total_bet:.2f}")
        
        # 如果玩家选择了弃牌，移动弃牌到弃牌区域
        if self.player_selected_label:
            self.move_discard_to_area(self.player_selected_label, self.player_discard_frame, "player")
        
        # 禁用决策按钮
        self.disable_action_buttons()
        
        # 进入庄家决策阶段
        self.game.stage = "dealer_draw"
        self.stage_label.config(text="庄家决策")
        self.status_label.config(text="庄家正在决策...")
        
        # 先翻开庄家牌
        self.reveal_dealer_cards()
        
        # 2秒后庄家决策
        self.after(2000, self.dealer_decision)
        
    def move_discard_to_area(self, card_label, area_frame, player_type):
        """
        移动弃牌到弃牌区域并启动动画。
        目标：把卡片放在 area_frame 的正中心，并对齐到左边扑克的Y轴高度。
        """
        if card_label is None or not hasattr(card_label, "card"):
            return

        # 强制刷新布局，确保 winfo_* 返回正确值
        self.update_idletasks()

        # 获取左边扑克区域的Y坐标（用于对齐高度）
        if player_type == "dealer":
            hand_frame = self.dealer_cards_frame
            # 获取手牌区域在屏幕上的绝对Y坐标
            hand_y = hand_frame.winfo_rooty() - self.winfo_rooty()
            # 获取手牌区域的高度
            hand_height = hand_frame.winfo_height()
            # 计算手牌区域的中心Y坐标（相对于主窗口）
            hand_center_y = hand_y + hand_height // 2
        else:
            hand_frame = self.player_cards_frame
            # 获取手牌区域在屏幕上的绝对Y坐标
            hand_y = hand_frame.winfo_rooty() - self.winfo_rooty()
            # 获取手牌区域的高度
            hand_height = hand_frame.winfo_height()
            # 计算手牌区域的中心Y坐标（相对于主窗口）
            hand_center_y = hand_y + hand_height // 2

        # 获取弃牌区域的坐标（相对于主窗口）
        area_x = area_frame.winfo_rootx() - self.winfo_rootx()
        area_y = area_frame.winfo_rooty() - self.winfo_rooty()
        area_width = area_frame.winfo_width()
        area_height = area_frame.winfo_height()

        # 计算卡片在弃牌区域内的位置
        # X轴居中
        target_x = area_x + (area_width - 100) // 2  # 100是卡片宽度
        # Y轴与左边扑克对齐（保持相同的高度）
        target_y = hand_center_y - 100  # 70是卡片高度的一半，确保垂直居中

        # 确保目标位置在弃牌区域内
        if target_y < area_y:
            target_y = area_y
        elif target_y + 140 > area_y + area_height:  # 140是卡片高度
            target_y = area_y + area_height - 140

        # 获取卡片当前在屏幕上的位置（相对于主窗口）
        card_x = card_label.winfo_rootx() - self.winfo_rootx()
        card_y = card_label.winfo_rooty() - self.winfo_rooty()

        # 写入目标信息，供 animate_card_to_discard 使用
        card_label.target_pos = (target_x, target_y)
        card_label.start_pos = (card_x, card_y)
        card_label.discard_area = area_frame
        card_label.is_moving = True
        card_label.player_type = player_type  # 保存玩家类型用于后续定位

        # 将卡片记录到活动列表（便于后续收牌/重置）
        if card_label not in self.active_card_labels:
            self.active_card_labels.append(card_label)

        # 启动移动动画
        self.animate_card_to_discard(card_label, player_type)

    def animate_card_to_discard(self, card_label, player_type):
        """将 card_label 平滑移动到 card_label.target_pos。"""
        # Safety checks
        try:
            if not hasattr(card_label, "target_pos"):
                return
        except tk.TclError:
            return

        try:
            current_x = card_label.winfo_x()
            current_y = card_label.winfo_y()
        except tk.TclError:
            # 已被销毁或不可见
            try:
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
            except:
                pass
            return

        target_x, target_y = card_label.target_pos
        dx = target_x - current_x
        dy = target_y - current_y
        distance = math.hypot(dx, dy)

        # 到达目标
        if distance < 6:
            # 最终放到目标位置
            try:
                card = getattr(card_label, "card", None)
            except Exception:
                card = None

            # 销毁原卡片之前移出活动列表
            try:
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
            except Exception:
                pass

            try:
                card_label.destroy()
            except Exception:
                try:
                    card_label.place_forget()
                except:
                    pass

            # 在指定的弃牌区域创建新的卡片 label
            area = getattr(card_label, "discard_area", None)
            if area is None or not isinstance(area, tk.Widget):
                return

            # 取得卡片正面图
            if card is None:
                front_img = self.back_image
            else:
                if getattr(card, "is_joker", False):
                    front_img = self.card_images.get(('JOKER', 'A'), self.back_image)
                else:
                    front_img = self.card_images.get((card.suit, card.rank), self.back_image)

            # 在弃牌区创建 label
            new_label = tk.Label(area, image=front_img, bg=area.cget('bg') if hasattr(area, 'cget') else '#2a4a3c')
            new_label.image = front_img
            new_label.card = card
            new_label.is_face_up = True

            # 计算放置位置 - 确保与左边扑克区域Y轴对齐
            try:
                # 获取左边扑克区域的中心Y坐标（相对于弃牌区域）
                if player_type == "dealer":
                    hand_frame = self.dealer_cards_frame
                else:
                    hand_frame = self.player_cards_frame
                
                # 获取手牌区域在屏幕上的绝对Y坐标
                hand_y = hand_frame.winfo_rooty()
                # 获取弃牌区域在屏幕上的绝对Y坐标
                area_y = area.winfo_rooty()
                # 计算相对Y坐标（手牌中心相对于弃牌区域）
                relative_y = (hand_y + hand_frame.winfo_height() // 2) - area_y - 70
                
                # 确保在弃牌区域内
                if relative_y < 0:
                    relative_y = 0
                elif relative_y + 140 > area.winfo_height():
                    relative_y = area.winfo_height() - 140
                    
                # X轴居中
                center_x = (area.winfo_width() - 100) // 2
                
            except Exception:
                # 如果计算失败，使用默认居中位置
                center_x = (area.winfo_width() - 100) // 2
                relative_y = (area.winfo_height() - 140) // 2

            # 使用 place 确保位置准确
            new_label.place(x=center_x, y=relative_y)

            # 如果是庄家弃牌，继续下一步（添加公共牌并排序）
            if player_type == "dealer":
                self.after(400, self.add_community_card_and_sort)
            return

        # 仍需移动：平滑移动（20ms 每步）
        step_x = dx * 0.22
        step_y = dy * 0.22
        new_x = current_x + step_x
        new_y = current_y + step_y
        try:
            card_label.place(x=new_x, y=new_y)
            self.after(20, lambda: self.animate_card_to_discard(card_label, player_type))
        except tk.TclError:
            # widget 被销毁
            try:
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
            except:
                pass
            return
    
    def dealer_decision(self):
        """庄家根据house way规则决策"""
        # 关键修正：把弃牌保存在 game 对象上（而不是仅保存为 GUI 的 self.dealer_discard）
        self.game.dealer_discard = self.game.dealer_house_way()

        if self.game.dealer_discard:
            self.status_label.config(text=f"庄家弃牌: {self.game.dealer_discard}")
            # 找到对应的卡片标签并移动到弃牌区域
            for card_label in self.dealer_cards_frame.winfo_children():
                if hasattr(card_label, "card") and card_label.card == self.game.dealer_discard:
                    # 把卡片移动到弃牌区（会执行动画并在结束时继续流程）
                    self.move_discard_to_area(card_label, self.dealer_discard_frame, "dealer")
                    break
        else:
            self.status_label.config(text="庄家不弃牌")
            # 直接进入下一步
            self.after(500, self.add_community_card_and_sort)
    
    def add_community_card_and_sort(self):
        """添加公共牌并排序手牌"""
        # 翻开公共牌
        self.reveal_community_cards()
        
        # 评估手牌并排序
        player_eval, player_best, dealer_eval, dealer_best = self.game.evaluate_hands()
        
        # 先翻面所有牌
        self.flip_all_cards_back()
        
        # 0.25秒后排序并翻面
        self.after(250, lambda: self.sort_and_flip_cards())
    
    def flip_all_cards_back(self):
        """将所有牌翻面（背面朝上）"""
        # 玩家牌
        for card_label in self.player_cards_frame.winfo_children():
            if hasattr(card_label, "card") and card_label.is_face_up:
                card_label.config(image=self.back_image)
                card_label.is_face_up = False
        
        # 庄家牌
        for card_label in self.dealer_cards_frame.winfo_children():
            if hasattr(card_label, "card") and card_label.is_face_up:
                card_label.config(image=self.back_image)
                card_label.is_face_up = False
        
        # 公共牌
        for card_label in self.community_cards_frame.winfo_children():
            if hasattr(card_label, "card") and card_label.is_face_up:
                card_label.config(image=self.back_image)
                card_label.is_face_up = False
    
    def sort_and_flip_cards(self):
        """排序并翻面手牌（翻面动画按顺序触发），同时确保界面上的手牌描述及时刷新。"""
        # 清空当前牌架（先销毁旧 widget）
        for w in list(self.player_cards_frame.winfo_children()):
            try:
                w.destroy()
            except:
                pass
        for w in list(self.dealer_cards_frame.winfo_children()):
            try:
                w.destroy()
            except:
                pass

        player_hand = getattr(self.game, 'player_sorted_hand', []) or []
        dealer_hand = getattr(self.game, 'dealer_sorted_hand', []) or []

        # 先把背面卡片放上去，并安排按序翻面动画
        for i, card in enumerate(player_hand):
            card_label = tk.Label(self.player_cards_frame, image=self.back_image, bg='#2a4a3c')
            card_label.place(x=i * 105, y=0)
            card_label.card = card
            card_label.is_face_up = False
            if card_label not in self.active_card_labels:
                self.active_card_labels.append(card_label)
            # 按序翻牌，延迟基准 250 + i*100 ms（与你原实现一致）
            self.after(250 + i * 100, lambda cl=card_label: self.flip_card_animation(cl))

        for i, card in enumerate(dealer_hand):
            card_label = tk.Label(self.dealer_cards_frame, image=self.back_image, bg='#2a4a3c')
            card_label.place(x=i * 105, y=0)
            card_label.card = card
            card_label.is_face_up = False
            if card_label not in self.active_card_labels:
                self.active_card_labels.append(card_label)
            self.after(250 + i * 100, lambda cl=card_label: self.flip_card_animation(cl))

        self.update_hand_labels()

        # 1.25秒后进入摊牌阶段（原逻辑）
        self.after(1250, self.show_showdown)
        
    def show_showdown(self):
        """摊牌阶段"""
        # 评估手牌（考虑公共牌和弃牌）
        player_eval, player_best, dealer_eval, dealer_best = self.game.evaluate_hands()
        
        # 结算
        winnings = self.calculate_winnings(player_eval, dealer_eval)

        # 更新余额
        self.balance += winnings
        self.update_balance()
        
        self.last_win = winnings
        self.last_win_label.config(text=f"上局获胜: ${winnings:.2f}")

        # 显示结果文本 - 使用最终评估结果
        player_hand_name = HAND_RANK_NAMES[player_eval[0]]
        dealer_hand_name = HAND_RANK_NAMES[dealer_eval[0]]
        
        # 添加Joker替换信息
        player_joker_info = ""
        if hasattr(self.game, 'player_joker_replacements') and self.game.player_joker_replacements:
            joker_cards = ", ".join([str(card) for card in self.game.player_joker_replacements])
            # 检查是否使用了公共牌中的万能牌
            if hasattr(self.game, 'player_used_community') and self.game.player_used_community and getattr(self.game.player_used_community, 'is_joker', False):
                player_joker_info = f" ≈≈>> 公共万能牌： {joker_cards}"
            else:
                player_joker_info = f" ≈≈>> 万能牌： {joker_cards}"
        
        dealer_joker_info = ""
        if hasattr(self.game, 'dealer_joker_replacements') and self.game.dealer_joker_replacements:
            joker_cards = ", ".join([str(card) for card in self.game.dealer_joker_replacements])
            # 检查是否使用了公共牌中的万能牌
            if hasattr(self.game, 'dealer_used_community') and self.game.dealer_used_community and getattr(self.game.dealer_used_community, 'is_joker', False):
                dealer_joker_info = f" ≈≈>> 公共万能牌： {joker_cards}"
            else:
                dealer_joker_info = f" ≈≈>> 万能牌： {joker_cards}"
        
        # 组合信息
        player_extra_info = player_joker_info
        dealer_extra_info = dealer_joker_info
        
        player_hand_name += player_extra_info
        dealer_hand_name += dealer_extra_info
        
        # 简化状态显示为固定短句
        player_rank = player_eval[0]
        dealer_rank = dealer_eval[0]
        player_wins = False
        dealer_wins = False
        if player_rank > dealer_rank:
            player_wins = True
        elif player_rank == dealer_rank:
            comparison = _compare_hands(player_eval, dealer_eval)
            if comparison > 0:
                player_wins = True
            elif comparison < 0:
                dealer_wins = True
        else:
            dealer_wins = True

        progressive_win = self.win_details['progressive']
        if progressive_win > 0:
            self.status_label.config(text=f"您赢了Progressive大奖${progressive_win:.2f}!")
        else:
            if player_wins:
                self.status_label.config(text="您赢了!")
            elif dealer_wins:
                self.status_label.config(text="送你好运！")
            else:
                self.status_label.config(text="平局")

        # 更新所有下注格子的显示 - 使用StringVar设置文本
        def update_bet_display(bet_type, amount, original_bet, var_object):
            widget = getattr(self, f"{bet_type}_display", None) or self.bet_widgets.get(bet_type)
            if widget:
                if amount > original_bet:  # 赢
                    widget.config(bg='gold')
                    var_object.set(f"{amount}")
                elif amount == original_bet and original_bet != 0:  # 平局
                    widget.config(bg='light blue')
                    var_object.set(f"{amount}")
                else:  # 输
                    widget.config(bg='white')
                    var_object.set("0")

        # 更新每个下注类型的显示
        update_bet_display('ante', self.win_details['ante'], self.game.ante, self.ante_var)
        update_bet_display('bonus', self.win_details['bonus'], self.game.bonus, self.bonus_var)
        update_bet_display('wild5', self.win_details['wild5'], self.game.wild5, self.wild5_var)
        update_bet_display('progressive', self.win_details['progressive'], self.game.progressive, self.progressive_var)
        update_bet_display('play', self.win_details['play'], self.game.play_bet, self.play_var)
        
        # 更新玩家和庄家的手牌标签显示最终牌型
        self.player_label.config(text=f"玩家 - {player_hand_name}")
        self.dealer_label.config(text=f"庄家 - {dealer_hand_name}")
        
        # 二次开牌时，将使用的公共牌在玩家和庄家区域往下移动10px
        if hasattr(self.game, 'player_used_community') and self.game.player_used_community:
            # 找到玩家使用的公共牌并在玩家区域显示下移效果
            for card_label in self.player_cards_frame.winfo_children():
                if hasattr(card_label, 'card') and card_label.card == self.game.player_used_community:
                    current_y = card_label.winfo_y()
                    card_label.place(y=current_y + 10)
                    # 添加边框突出显示
                    card_label.config(borderwidth=2, relief="solid", highlightbackground="blue")
                    break
        
        if hasattr(self.game, 'dealer_used_community') and self.game.dealer_used_community:
            # 找到庄家使用的公共牌并在庄家区域显示下移效果
            for card_label in self.dealer_cards_frame.winfo_children():
                if hasattr(card_label, 'card') and card_label.card == self.game.dealer_used_community:
                    current_y = card_label.winfo_y()
                    card_label.place(y=current_y + 10)
                    # 添加边框突出显示
                    card_label.config(borderwidth=2, relief="solid", highlightbackground="red")
                    break
        
        # 添加重新开始按钮
        for widget in self.action_frame.winfo_children():
            widget.destroy()
            
        restart_btn = tk.Button(
            self.action_frame, text="再来一局", 
            command=self.reset_game, 
            font=('Arial', 14), bg='#2196F3', fg='white', width=15
            )
        restart_btn.pack(pady=10)
        restart_btn.bind("<Button-3>", self.show_card_sequence)
        
        # 设置30秒后自动重置
        self.auto_reset_timer = self.after(30000, lambda: self.reset_game(True))
    
    def calculate_side_bets_only(self):
        """只结算边注（当玩家弃牌时）"""
        # 重置获胜详情
        self.win_details = {
            "ante": 0,
            "bonus": 0,
            "wild5": 0,
            "progressive": 0,
            "play": 0
        }

        total_winnings = 0

        # 1) Ante: 玩家弃牌 -> Ante 输掉（0）
        self.win_details['ante'] = 0
        total_winnings += self.win_details['ante']

        # 2) Bonus: 玩家弃牌 -> Ante 输掉（0）
        self.win_details['bonus'] = 0
        total_winnings += self.win_details['bonus']

        # 3) Wild5: 根据玩家手牌直接支付（Wild5 通常基于玩家的 5 张牌）
        try:
            player_hand = getattr(self.game, 'player_hand', [])
            # 若玩家手牌已满 5 张，评估手牌，否则视为无牌（输）
            if len(player_hand) >= 5:
                # evaluate_hand 返回 (rank, values)
                player_rank = evaluate_hand(player_hand)[0]
                if player_rank in WILD_5_PAYOUT and getattr(self.game, 'wild5', 0) > 0:
                    odds = WILD_5_PAYOUT[player_rank]
                    self.win_details['wild5'] = self.game.wild5 * odds
                else:
                    self.win_details['wild5'] = 0
            else:
                self.win_details['wild5'] = 0
        except Exception:
            self.win_details['wild5'] = 0

        total_winnings += self.win_details['wild5']

        # 4) Progressive（使用玩家5张手牌）
        progressive_win = 0
        if getattr(self.game, 'progressive', 0) > 0:
            progressive_result = evaluate_progressive(getattr(self.game, 'player_hand', []))
            if progressive_result:
                payout = calculate_progressive_payout(progressive_result, self.game.jackpot_amount)
                progressive_win = payout
                
                # 从奖池中扣除奖金
                self.game.jackpot_amount -= progressive_win
                # 确保奖池不低于197301.26
                if self.game.jackpot_amount < 197301.26:
                    self.game.jackpot_amount = 197301.26
                save_jackpot(self.game.jackpot_amount)
                
                # 显示中奖消息
                hand_name_map = {
                    "five_of_a_kind": "五条",
                    "royal_flush": "皇家同花顺",
                    "straight_flush": "同花顺",
                    "four_of_a_kind": "四条",
                    "full_house": "葫芦",
                    "flush": "同花"
                }
                messagebox.showinfo("恭喜您获得Jackpot大奖！", 
                                f"{hand_name_map.get(progressive_result, progressive_result)}! 赢得Jackpot大奖 ${progressive_win:.2f}!")

            self.win_details['progressive'] = progressive_win
            total_winnings += progressive_win
        
        # 5) 将本局总下注的10%加入Progressive奖池
        total_bet = self.game.ante + self.game.bonus + self.game.wild5 + self.game.progressive + self.game.ppair
        progressive_contribution = total_bet * 0.1
        self.game.jackpot_amount += progressive_contribution
        save_jackpot(self.game.jackpot_amount)
        self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")

        # 结算PPair
        ppair_win = self.calculate_ppair_payout()
        self.win_details['ppair'] = ppair_win
        total_winnings += ppair_win
        
        # 更新PPair显示
        if ppair_win > 0:
            self.ppair_display.config(bg='gold')
            self.ppair_var.set(str(ppair_win))
        else:
            self.ppair_display.config(bg='white')
            self.ppair_var.set("0")

        return total_winnings
            
    def calculate_winnings(self, player_eval, dealer_eval):
        """最终结算（玩家与庄家比较）"""
        # 重置获胜详情
        self.win_details = {
            "ante": 0,
            "bonus": 0,
            "wild5": 0,
            "progressive": 0,
            "play": 0
        }

        total_winnings = 0
        player_rank = player_eval[0]
        dealer_rank = dealer_eval[0]
        player_values = player_eval[1]
        dealer_values = dealer_eval[1]

        # 比较结果判断
        player_wins = False
        dealer_wins = False
        if player_rank > dealer_rank:
            player_wins = True
        elif player_rank < dealer_rank:
            dealer_wins = True
        else:
            # 同牌型时比较具体牌值
            comparison = _compare_hands(player_values, dealer_values)
            if comparison > 0:
                player_wins = True
            elif comparison < 0:
                dealer_wins = True
            else:
                # 平局
                pass

        # 1) Ante 结算
        if dealer_rank == 0:
            # 庄家是高牌，退还Ante
            self.win_details['ante'] = self.game.ante
        else:
            if player_wins:
                self.win_details['ante'] = self.game.ante * 2  # 1:1赔率（本金+赢利）
            elif dealer_wins:
                self.win_details['ante'] = 0  # 输
            else:
                # 平局 -> 退还Ante
                self.win_details['ante'] = self.game.ante

        total_winnings += self.win_details['ante']

        # 2) Bonus 结算 - 与庄家比较
        if player_wins:
            # 玩家赢，根据玩家牌型支付Bonus
            if player_rank in BONUS_PAYOUT:
                odds = BONUS_PAYOUT[player_rank]
                self.win_details['bonus'] = self.game.bonus * (odds + 1)  # 包含本金
            else:
                self.win_details['bonus'] = self.game.bonus  # 退还
        elif dealer_wins:
            self.win_details['bonus'] = 0  # 输
        else:
            # 平局 -> 退还Bonus
            self.win_details['bonus'] = self.game.bonus

        total_winnings += self.win_details['bonus']

        # 3) Wild5 结算 - 已在reveal_player_cards中处理，这里不再重复计算
        if getattr(self, 'wild5_paid', False):
            self.win_details['wild5'] = getattr(self, 'wild5_paid_amount', 0)
        else:
            # 如果尚未支付Wild5，按玩家牌型支付
            if player_rank in WILD_5_PAYOUT:
                odds = WILD_5_PAYOUT[player_rank]
                self.win_details['wild5'] = self.game.wild5 * (odds + 1)  # 包含本金
            else:
                self.win_details['wild5'] = 0  # 输

        total_winnings += self.win_details['wild5']

        # 4) Progressive 结算（使用玩家最终5张手牌）
        progressive_win = 0
        if self.game.progressive > 0:
            # 获取玩家最终手牌（5张）
            player_final_hand = []
            if hasattr(self.game, 'player_sorted_hand') and self.game.player_sorted_hand:
                player_final_hand = self.game.player_sorted_hand
            else:
                # 如果没有排序的手牌，使用原始手牌
                player_final_hand = self.game.player_hand[:5]
            
            progressive_result = evaluate_progressive(player_final_hand)
            if progressive_result:
                payout = calculate_progressive_payout(progressive_result, self.game.jackpot_amount)
                progressive_win = payout
                
                # 从奖池中扣除奖金
                self.game.jackpot_amount -= progressive_win
                # 确保奖池不低于197301.26
                if self.game.jackpot_amount < 197301.26:
                    self.game.jackpot_amount = 197301.26
                save_jackpot(self.game.jackpot_amount)
                
                # 显示中奖消息
                hand_name_map = {
                    "five_of_a_kind": "五条",
                    "royal_flush": "皇家同花顺",
                    "straight_flush": "同花顺",
                    "four_of_a_kind": "四条",
                    "full_house": "葫芦",
                    "flush": "同花"
                }
                messagebox.showinfo("恭喜您获得Jackpot大奖！", 
                                f"{hand_name_map.get(progressive_result, progressive_result)}! 赢得Jackpot大奖 ${progressive_win:.2f}!")

            self.win_details['progressive'] = progressive_win
            total_winnings += progressive_win

        # 5) Play bet 结算
        if player_wins:
            self.win_details['play'] = self.game.play_bet * 2  # 1:1赔率（本金+赢利）
        elif dealer_wins:
            self.win_details['play'] = 0  # 输
        else:
            # 平局 -> 退还Play bet
            self.win_details['play'] = self.game.play_bet

        total_winnings += self.win_details['play']

        # 结算PPair
        ppair_win = self.calculate_ppair_payout()
        self.win_details['ppair'] = ppair_win
        total_winnings += ppair_win
        
        # 更新PPair显示
        if ppair_win > 0:
            self.ppair_display.config(bg='gold')
            self.ppair_var.set(str(ppair_win))
        else:
            self.ppair_display.config(bg='white')
            self.ppair_var.set("0")
        
        # 6) 将本局总下注的10%加入Progressive奖池
        total_bet = self.game.ante + self.game.bonus + self.game.wild5 + self.game.progressive + self.game.ppair
        progressive_contribution = total_bet * 0.1
        self.game.jackpot_amount += progressive_contribution
        save_jackpot(self.game.jackpot_amount)
        self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")

        # 结算PPair
        ppair_win = self.calculate_ppair_payout()
        self.win_details['ppair'] = ppair_win
        total_winnings += ppair_win

        return total_winnings
    
    def calculate_ppair_payout(self):
        """计算PPair边注赔付"""
        if self.game.ppair <= 0:
            return 0
            
        community_cards = self.game.community_cards
        
        # 检查是否有Joker
        has_joker = any(card.is_joker for card in community_cards)
        if has_joker:
            return self.game.ppair * 9  # 8:1赔率 + 本金 = 9倍
            
        # 检查是否是对子
        if len(community_cards) == 2:
            card1, card2 = community_cards
            
            # 获取牌值和花色
            value1 = card1.value if not card1.is_joker else 0
            value2 = card2.value if not card2.is_joker else 0
            suit1 = card1.suit if not card1.is_joker else None
            suit2 = card2.suit if not card2.is_joker else None
            
            # 检查同花
            is_suited = suit1 == suit2 and suit1 is not None and suit2 is not None
            
            # A-A
            if value1 == 14 and value2 == 14:
                return self.game.ppair * 31  # 30:1赔率 + 本金 = 31倍
                
            # 同花A-K
            if is_suited and ((value1 == 14 and value2 == 13) or (value1 == 13 and value2 == 14)):
                return self.game.ppair * 26  # 25:1赔率 + 本金 = 26倍
                
            # 同花A-Q或A-J
            if is_suited and (
                (value1 == 14 and value2 == 12) or (value1 == 12 and value2 == 14) or
                (value1 == 14 and value2 == 11) or (value1 == 11 and value2 == 14)
            ):
                return self.game.ppair * 21  # 20:1赔率 + 本金 = 21倍
                
            # A-K
            if (value1 == 14 and value2 == 13) or (value1 == 13 and value2 == 14):
                return self.game.ppair * 16  # 15:1赔率 + 本金 = 16倍
                
            # K-K, Q-Q, J-J
            if (value1 == 13 and value2 == 13) or (value1 == 12 and value2 == 12) or (value1 == 11 and value2 == 11):
                return self.game.ppair * 11  # 10:1赔率 + 本金 = 11倍
                
            # A-Q或A-J
            if (value1 == 14 and value2 == 12) or (value1 == 12 and value2 == 14) or \
            (value1 == 14 and value2 == 11) or (value1 == 11 and value2 == 14):
                return self.game.ppair * 6  # 5:1赔率 + 本金 = 6倍
                
            # 其他对子 (10-10 through 2-2)
            if value1 == value2 and value1 >= 2 and value1 <= 10:
                return self.game.ppair * 4  # 3:1赔率 + 本金 = 4倍
        
        # 不符合任何赔付条件
        return 0

    def reset_game(self, auto_reset=False):
        # 取消自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 如果当前有牌在桌上，先执行收牌动画
        if self.active_card_labels:
            self.disable_action_buttons()  # 禁用按钮
            self.animate_collect_cards(auto_reset)  # 开始收牌动画，动画完成后会调用真正的重置
            return

        # 否则直接重置
        self._do_reset(auto_reset)
    
    def reset_bets(self):
        """重置所有投注金额为0（不重置Progressive的打勾）"""
        self.ante_var.set("0")
        self.bonus_var.set("0")  # 同时重置Bonus
        self.wild5_var.set("0")
        self.ppair_var.set("0")
        # 注意：不重置progressive_var，保留打勾状态
        
        # 更新显示
        self.status_label.config(text="已重置所有下注金额")
        
        # 重置背景色为白色
        for widget in self.bet_widgets.values():
            widget.config(bg='white')

        for chip in self.chip_buttons:
            chip_text = self.chip_texts.get(chip, "$5")
            chip.bind("<Button-1>", lambda e, t=chip_text: self.select_chip(t))
        
        # 短暂高亮显示重置效果
        self.ante_display.config(bg='#FFCDD2')  # 浅红色
        self.bonus_display.config(bg='#FFCDD2')
        self.wild5_display.config(bg='#FFCDD2')
        self.after(500, lambda: [
            self.ante_display.config(bg='white'), 
            self.bonus_display.config(bg='white'),
            self.wild5_display.config(bg='white')
        ])
    
    def _do_reset(self, auto_reset=False):
        """真正的重置游戏界面：确保所有牌被移除，弃牌区标题被重建，状态复位。"""
        # 取消自动重置计时器（保险）
        if self.auto_reset_timer:
            try:
                self.after_cancel(self.auto_reset_timer)
            except:
                pass
            self.auto_reset_timer = None

        # 重置游戏内部状态
        self.game.reset_game()
        self.stage_label.config(text="初始发牌")

        # 重置牌型标签
        self.player_label.config(text="玩家")
        self.dealer_label.config(text="庄家")

        # 重置下注变量（Play 也恢复为 0）
        self.ante_var.set("0")
        self.bonus_var.set("0")
        self.wild5_var.set("0")
        self.play_var.set("0")
        self.wild5_paid = False
        self.wild5_paid_amount = 0

        # 把本局下注显示也归零
        try:
            self.current_bet_label.config(text="本局下注: $0.00")
        except:
            pass

        # 清空所有牌框内的 widgets（确保没有残留）
        for frame_attr in ('dealer_cards_frame', 'community_cards_frame', 'player_cards_frame',
                        'player_discard_frame', 'dealer_discard_frame'):
            frame = getattr(self, frame_attr, None)
            if frame:
                try:
                    for widget in list(frame.winfo_children()):
                        widget.destroy()
                except:
                    pass

        # 重新在弃牌区创建标题标签（确保 UI 一致性）
        try:
            if self.dealer_discard_frame:
                for w in list(self.dealer_discard_frame.winfo_children()):
                    w.destroy()
                dealer_discard_label = tk.Label(self.dealer_discard_frame, text="庄家弃牌",
                                            font=('Arial', 18), bg=self.dealer_discard_frame.cget('bg'), fg='white')
                dealer_discard_label.pack(side=tk.TOP, pady=5)
        except:
            pass

        try:
            if self.player_discard_frame:
                for w in list(self.player_discard_frame.winfo_children()):
                    w.destroy()
                player_discard_label = tk.Label(self.player_discard_frame, text="玩家弃牌",
                                            font=('Arial', 18), bg=self.player_discard_frame.cget('bg'), fg='white')
                player_discard_label.pack(side=tk.TOP, pady=5)
        except:
            pass

        # 重置动画 & 活动卡片跟踪
        self.animation_queue = []
        self.animation_in_progress = False
        self.active_card_labels = []

        # 其它 GUI 状态重置（保留 progress checkbox 等）
        self.player_selected_card = None
        self.player_selected_label = None
        self.buttons_disabled = False

        # 恢复下注区点击绑定（确保可以继续下注）
        try:
            self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
            self.bonus_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("bonus"))
            self.wild5_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("wild5"))
            self.progressive_cb.config(state=tk.NORMAL)
            for chip in self.chip_buttons:
                chip.bind("<Button-1>", lambda e, c=chip: None)  # 保留绑定/恢复逻辑（视你原始实现）
        except:
            pass

        # 调用 reset_bets 来把下注格子颜色恢复为白色并清零下注数值（保留 Progressive 勾选）
        try:
            self.reset_bets()
        except:
            # 如果 reset_bets 里用到 UI 名称异常，手工做最小恢复
            try:
                for widget in self.bet_widgets.values():
                    widget.config(bg='white')
            except:
                pass

        # 确保本局下注标签为 0
        try:
            self.current_bet_label.config(text="本局下注: $0.00")
        except:
            pass

        # 清除 action_frame 内所有控件（比如“再来一局”按钮），并重建初始的开始/重设按钮
        try:
            for widget in list(self.action_frame.winfo_children()):
                widget.destroy()

            start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
            start_button_frame.pack(pady=10)

            self.reset_bets_button = tk.Button(
                start_button_frame, text="重设金额",
                command=self.reset_bets, font=('Arial', 14),
                bg='#F44336', fg='white', width=10
            )
            self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))

            self.start_button = tk.Button(
                start_button_frame, text="开始游戏",
                command=self.start_game, font=('Arial', 14),
                bg='#4CAF50', fg='white', width=10
            )
            self.start_button.pack(side=tk.LEFT)
        except Exception:
            # 失败也不致命，主要保证程序不崩溃
            pass

        # 恢复余额显示与手牌标签
        try:
            self.update_balance()
        except:
            pass

        try:
            self.update_hand_labels()
        except:
            pass

    def show_card_sequence(self, event):
        """显示本局牌序窗口 - 右键点击时取消30秒计时"""
        # 取消30秒自动重置计时器
        if self.auto_reset_timer:
            self.after_cancel(self.auto_reset_timer)
            self.auto_reset_timer = None
        
        # 确保有牌序信息
        if not hasattr(self.game, 'deck') or not self.game.deck:
            messagebox.showinfo("提示", "没有牌序信息")
            return
            
        win = tk.Toplevel(self)
        win.title("本局牌序")
        win.geometry("650x600+80+20")  # 固定窗口大小
        win.resizable(0,0)
        win.configure(bg='#f0f0f0')
        
        # 显示切牌位置
        cut_pos = self.game.deck.start_pos
        cut_label = tk.Label(
            win, 
            text=f"本局切牌位置: {cut_pos + 1}", 
            font=('Arial', 14, 'bold'),
            bg='#f0f0f0'
        )
        cut_label.pack(pady=(10, 5))
        
        # 创建主框架
        main_frame = tk.Frame(win, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 创建画布用于滚动
        canvas = tk.Canvas(main_frame, bg='#f0f0f0', yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas.yview)
        
        # 创建内部框架放置所有内容
        content_frame = tk.Frame(canvas, bg='#f0f0f0')
        canvas_frame = canvas.create_window((0, 0), window=content_frame, anchor='nw')
        
        # 创建卡片框架
        card_frame = tk.Frame(content_frame, bg='#f0f0f0')
        card_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 创建缩小版卡片图像
        small_size = (60, 90)
        small_images = {}

        # 尝试加载字体
        from PIL import ImageFont, ImageDraw
        
        # 创建卡片图像
        for i, card in enumerate(self.game.deck.full_deck):
            # 使用花色和点数作为键获取原始图片
            if card.is_joker:
                key = ('JOKER', 'A')
            else:
                key = (card.suit, card.rank)
            
            if key in self.original_images:
                # 获取原始图像
                orig_img = self.original_images[key]
                
                # 创建缩小版图像
                small_img = orig_img.resize(small_size, Image.LANCZOS)
                small_images[i] = ImageTk.PhotoImage(small_img)
            else:
                # 创建带文字的占位图像
                img = Image.new('RGB', small_size, 'blue')
                draw = ImageDraw.Draw(img)
                if card.is_joker:
                    text = "JOKER"
                else:
                    text = f"{card.rank}{card.suit}"
                try:
                    font = ImageFont.truetype("arial.ttf", 12)
                except:
                    font = ImageFont.load_default()
                text_width, text_height = draw.textsize(text, font=font)
                x = (small_size[0] - text_width) / 2
                y = (small_size[1] - text_height) / 2
                draw.text((x, y), text, fill="white", font=font)
                small_images[i] = ImageTk.PhotoImage(img)
        
        # 创建表格显示牌序 - 每行8张，共7行
        for row in range(7):  # 7行
            row_frame = tk.Frame(card_frame, bg='#f0f0f0')
            row_frame.pack(fill=tk.X, pady=5)
            
            # 计算该行卡片数量 (前6行8张，最后一行5张)
            cards_in_row = 8 if row < 6 else 5
            
            for col in range(cards_in_row):
                card_index = row * 8 + col
                if card_index >= 53:  # 确保不超过53张
                    break
                    
                # 创建卡片容器
                card_container = tk.Frame(row_frame, bg='#f0f0f0')
                card_container.grid(row=0, column=col, padx=5, pady=5)
                
                # 标记切牌位置 - 显示在原始牌序中的位置
                is_cut_position = card_index == self.game.deck.start_pos
                bg_color = 'light blue' if is_cut_position else '#f0f0f0'
                
                # 显示卡片
                card = self.game.deck.full_deck[card_index]
                card_label = tk.Label(
                    card_container, 
                    image=small_images[card_index], 
                    bg=bg_color,
                    borderwidth=1,
                    relief="solid"
                )
                card_label.image = small_images[card_index]  # 保持引用
                card_label.pack()
                
                # 显示牌位置编号
                pos_label = tk.Label(
                    card_container, 
                    text=str(card_index+1), 
                    bg=bg_color,
                    font=('Arial', 9)
                )
                pos_label.pack()
        
        # 更新滚动区域
        content_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        
        # 绑定鼠标滚轮滚动
        win.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def animate_collect_cards(self, auto_reset):
        """执行收牌动画：先翻转所有牌为背面，然后向右收起（包括弃牌区域的牌）"""
        # 禁用所有按钮
        self.disable_action_buttons()
        
        # 收集所有需要移除的卡片标签（包括手牌区域和弃牌区域的牌）
        all_card_labels = []
        
        # 1. 收集手牌区域的牌
        for card_label in self.active_card_labels[:]:
            try:
                # 检查卡片是否还存在
                if card_label.winfo_exists():
                    all_card_labels.append(card_label)
            except tk.TclError:
                # 卡片已经被销毁，从活动列表中移除
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
                continue
        
        # 2. 收集玩家弃牌区域的牌
        try:
            for widget in self.player_discard_frame.winfo_children():
                if hasattr(widget, "card") and hasattr(widget, "is_face_up"):
                    # 创建虚拟的卡片标签用于动画
                    virtual_label = tk.Label(self, image=widget.winfo_children()[0].cget("image") if widget.winfo_children() else self.back_image)
                    virtual_label.card = getattr(widget, "card", None)
                    virtual_label.is_face_up = True
                    virtual_label.target_pos = (1200, widget.winfo_rooty() - self.winfo_rooty())
                    virtual_label.start_pos = (widget.winfo_rootx() - self.winfo_rootx(), widget.winfo_rooty() - self.winfo_rooty())
                    all_card_labels.append(virtual_label)
                    # 立即销毁原弃牌
                    widget.destroy()
        except Exception as e:
            print(f"Error collecting player discard cards: {e}")
        
        # 3. 收集庄家弃牌区域的牌
        try:
            for widget in self.dealer_discard_frame.winfo_children():
                if hasattr(widget, "card") and hasattr(widget, "is_face_up"):
                    # 创建虚拟的卡片标签用于动画
                    virtual_label = tk.Label(self, image=widget.winfo_children()[0].cget("image") if widget.winfo_children() else self.back_image)
                    virtual_label.card = getattr(widget, "card", None)
                    virtual_label.is_face_up = True
                    virtual_label.target_pos = (1200, widget.winfo_rooty() - self.winfo_rooty())
                    virtual_label.start_pos = (widget.winfo_rootx() - self.winfo_rootx(), widget.winfo_rooty() - self.winfo_rooty())
                    all_card_labels.append(virtual_label)
                    # 立即销毁原弃牌
                    widget.destroy()
        except Exception as e:
            print(f"Error collecting dealer discard cards: {e}")
        
        if not all_card_labels:
            # 没有牌，直接重置
            self._do_reset(auto_reset)
            return
        
        # 设置所有牌的目标位置为屏幕右侧外
        for card_label in all_card_labels:
            # 如果已经有目标位置，保持原样；否则设置默认目标位置
            if not hasattr(card_label, 'target_pos'):
                card_label.target_pos = (1200, card_label.winfo_y() if hasattr(card_label, 'winfo_y') else 300)
            
            # 将卡片添加到活动列表以便跟踪
            if card_label not in self.active_card_labels:
                self.active_card_labels.append(card_label)
            
            # 如果是虚拟标签（弃牌区域的牌），需要先放置到屏幕上
            if not hasattr(card_label, 'winfo_x') or not hasattr(card_label, 'winfo_y'):
                try:
                    start_x, start_y = getattr(card_label, 'start_pos', (card_label.winfo_rootx() - self.winfo_rootx(), 
                                                                        card_label.winfo_rooty() - self.winfo_rooty()))
                    card_label.place(x=start_x, y=start_y)
                except:
                    card_label.place(x=600, y=300)

        # 开始移动
        self.animate_card_out_step(auto_reset, all_card_labels)

    def animate_card_out_step(self, auto_reset, card_labels):
        """移动卡片出屏幕的每一步"""
        all_done = True
        for card_label in card_labels[:]:  # 遍历副本，因为可能删除
            if not hasattr(card_label, 'target_pos'):
                continue

            try:
                current_x = card_label.winfo_x()
                current_y = card_label.winfo_y()
                target_x, target_y = card_label.target_pos

                # 计算新位置
                dx = target_x - current_x
                dy = target_y - current_y
                distance = math.hypot(dx, dy)
                
                if distance < 5:
                    # 到达目标位置，移除卡片
                    try:
                        card_label.destroy()
                    except:
                        pass
                    if card_label in card_labels:
                        card_labels.remove(card_label)
                    if card_label in self.active_card_labels:
                        self.active_card_labels.remove(card_label)
                    continue

                # 计算移动步长
                step_x = dx * 0.2
                step_y = dy * 0.2
                new_x = current_x + step_x
                new_y = current_y + step_y
                
                card_label.place(x=new_x, y=new_y)
                all_done = False
                
            except tk.TclError:
                # 卡片已被销毁，从列表中移除
                if card_label in card_labels:
                    card_labels.remove(card_label)
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
                continue
            except Exception as e:
                # 其他异常，也移除卡片
                if card_label in card_labels:
                    card_labels.remove(card_label)
                if card_label in self.active_card_labels:
                    self.active_card_labels.remove(card_label)
                continue

        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset, card_labels))
        else:
            # 所有动画完成，重置游戏
            self._do_reset(auto_reset)

    def reset_single_bet(self, bet_type):
        """重置单个下注类型的金额为0"""
        if bet_type == "ante":
            self.ante_var.set("0")
            self.bonus_var.set("0")  # 同时重置Bonus
            self.ante_display.config(bg='white')
            self.bonus_display.config(bg='white')
        elif bet_type == "bonus":
            # Bonus不再单独重置，与Ante同步
            pass
        elif bet_type == "wild5":
            self.wild5_var.set("0")
            self.wild5_display.config(bg='white')
        elif bet_type == "ppair":  # 添加PPair处理
            self.ppair_var.set("0")
            self.ppair_display.config(bg='white')
        
        # 短暂高亮显示重置效果
        widget = getattr(self, f"{bet_type}_display", None)
        if widget:
            widget.config(bg='#FFCDD2')  # 浅红色
            self.after(500, lambda: widget.config(bg='white'))

    def _create_widgets(self):
        # 主框架 - 左右布局
        main_frame = tk.Frame(self, bg='#35654d')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧牌桌区域 - 使用Canvas提供更好的控制
        table_canvas = tk.Canvas(main_frame, bg='#35654d', highlightthickness=0)
        table_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 牌桌背景
        table_bg = table_canvas.create_rectangle(0, 0, 800, 600, fill='#35654d', outline='')
        
        # 庄家区域 - 固定高度200
        dealer_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        dealer_frame.place(x=20, y=20, width=570, height=220)
        self.dealer_label = tk.Label(dealer_frame, text="庄家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.dealer_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.dealer_cards_frame = tk.Frame(dealer_frame, bg='#2a4a3c')
        self.dealer_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 庄家弃牌区域 - 调整大小和位置以对齐
        self.dealer_discard_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        self.dealer_discard_frame.place(x=600, y=20, width=150, height=220)
        self.dealer_discard_frame.pack_propagate(False)  # 防止子组件改变框架大小
        dealer_discard_label = tk.Label(self.dealer_discard_frame, text="庄家弃牌", font=('Arial', 18), bg='#2a4a3c', fg='white')
        dealer_discard_label.pack(side=tk.TOP, pady=5)
        
        # 公共牌区域 - 固定高度200
        community_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        community_frame.place(x=20, y=250, width=270, height=220)
        community_label = tk.Label(community_frame, text="公共牌", font=('Arial', 18), bg='#2a4a3c', fg='white')
        community_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.community_cards_frame = tk.Frame(community_frame, bg='#2a4a3c')
        self.community_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.ante_info_label = tk.Label(
            table_canvas, 
            text="庄家最少对子或更好牌型才及格\n不及格的 Ante以平局结算\n\n>>🃏🃏公共牌二选一🃏🃏<<\n>>🃏🃏鬼牌为万能牌🃏🃏<<\n系统自动寻找对牌型最有利的牌", 
            font=('Arial', 24), 
            bg='#35654d', 
            fg='#FFD700',
            anchor='w',
            justify='center'
        )
        self.ante_info_label.place(x=525, y=360, anchor='center')
        
        # 玩家区域 - 固定高度200
        player_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        player_frame.place(x=20, y=480, width=570, height=220)
        self.player_label = tk.Label(player_frame, text="玩家", font=('Arial', 18), bg='#2a4a3c', fg='white')
        self.player_label.pack(side=tk.TOP, anchor='w', padx=10, pady=5)
        self.player_cards_frame = tk.Frame(player_frame, bg='#2a4a3c')
        self.player_cards_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 玩家弃牌区域 - 调整大小和位置以对齐
        self.player_discard_frame = tk.Frame(table_canvas, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        self.player_discard_frame.place(x=600, y=480, width=150, height=220)
        self.player_discard_frame.pack_propagate(False)  # 防止子组件改变框架大小
        player_discard_label = tk.Label(self.player_discard_frame, text="玩家弃牌", font=('Arial', 18), bg='#2a4a3c', fg='white')
        player_discard_label.pack(side=tk.TOP, pady=5)
        
        # 右侧控制面板
        control_frame = tk.Frame(main_frame, bg='#2a4a3c', width=430, padx=10, pady=10)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        control_frame.pack_propagate(False)
        
        # 顶部信息栏
        info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        info_frame.pack(fill=tk.X, pady=10)
        
        self.balance_label = tk.Label(
            info_frame, 
            text=f"余额: ${self.balance:.2f}",
            font=('Arial', 18),
            bg='#2a4a3c',
            fg='white'
        )
        self.balance_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.stage_label = tk.Label(
            info_frame, 
            text="初始发牌",
            font=('Arial', 18, 'bold'),
            bg='#2a4a3c',
            fg='#FFD700'
        )
        self.stage_label.pack(side=tk.LEFT, padx=20, pady=10)
        
        # Jackpot显示区域
        jackpot_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        jackpot_frame.pack(fill=tk.X, pady=5)

        # 创建一个内部框架用于居中
        jackpot_inner_frame = tk.Frame(jackpot_frame, bg='#2a4a3c')
        jackpot_inner_frame.pack(expand=True, pady=5)  # 使用expand和居中

        jackpot_label = tk.Label(jackpot_inner_frame, text="Progressive:", 
                                font=('Arial', 18), bg='#2a4a3c', fg='gold')
        jackpot_label.pack(side=tk.LEFT, padx=(0, 5))  # 右侧留5像素间距

        self.jackpot_var = tk.StringVar()
        self.jackpot_var.set(f"${self.game.jackpot_amount:.2f}")
        self.jackpot_display = tk.Label(jackpot_inner_frame, textvariable=self.jackpot_var, 
                                    font=('Arial', 18, 'bold'), bg='#2a4a3c', fg='gold')
        self.jackpot_display.pack(side=tk.LEFT)
        
        # 筹码区域
        chips_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        chips_frame.pack(fill=tk.X, pady=5)
        
        chips_label = tk.Label(chips_frame, text="筹码:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        chips_label.pack(anchor='w', padx=10, pady=5)
        
        # 单行放置5个筹码 - 增加50%大小
        chip_row = tk.Frame(chips_frame, bg='#2a4a3c')
        chip_row.pack(fill=tk.X, pady=5, padx=5)
        
        chip_configs = [
            ("$5", '#ff0000', 'white'),     # 红色背景，白色文字
            ('$10', '#ffa500', 'black'),   # 橙色背景，黑色文字
            ("$25", '#00ff00', 'black'),    # 绿色背景，黑色文字
            ("$50", '#ffffff', 'black'),    # 白色背景，黑色文字
            ("$100", '#000000', 'white'),   # 黑色背景，白色文字
            ("$500", "#FF7DDA", 'black'),   # 粉色背景，黑色文字
        ]
        
        self.chip_buttons = []
        self.chip_texts = {}  # 存储每个筹码按钮的文本
        for text, bg_color, fg_color in chip_configs:
            # 使用Canvas创建圆形筹码 - 尺寸改为55x55
            chip_canvas = tk.Canvas(chip_row, width=55, height=55, bg='#2a4a3c', highlightthickness=0)
            
            # 创建圆形（尺寸调整为51x51，在55x55画布中居中）
            chip_canvas.create_oval(2, 2, 53, 53, fill=bg_color, outline='black')
            
            # 创建文本（位置调整为画布中心）
            text_id = chip_canvas.create_text(27.5, 27.5, text=text, fill=fg_color, font=('Arial', 15, 'bold'))
            
            chip_canvas.bind("<Button-1>", lambda e, t=text: self.select_chip(t))
            chip_canvas.pack(side=tk.LEFT, padx=5)
            self.chip_buttons.append(chip_canvas)
            self.chip_texts[chip_canvas] = text  # 存储文本
        
        # 默认选中$5筹码
        self.select_chip("$5")
        
        # 下注区域
        bet_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_frame.pack(fill=tk.X, pady=5)

        # 第一行：Progressive选项
        progressive_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        progressive_frame.pack(fill=tk.X, padx=20, pady=5)

        self.progressive_var = tk.IntVar()
        self.progressive_cb = tk.Checkbutton(
            progressive_frame, text="Progressive ($10.00)", 
            variable=self.progressive_var, font=('Arial', 14),
            bg='#2a4a3c', fg='white', selectcolor='#35654d'
        )
        self.progressive_cb.pack(side=tk.LEFT)

        # 第二行：使用 grid 把 Wild5 和 PPair 放在同一行的不同列
        row_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        row_frame.pack(fill=tk.X, padx=20, pady=5)

        # Wild5 (column 0)
        wild5_label = tk.Label(row_frame, text="Wild 5:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        wild5_label.grid(row=0, column=0, sticky='w')
        self.wild5_var = tk.StringVar(value="0")
        self.wild5_display = tk.Label(row_frame, textvariable=self.wild5_var, font=('Arial', 14),
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.wild5_display.grid(row=0, column=1, padx=(5,30), sticky='w')
        self.wild5_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("wild5"))
        self.wild5_display.bind("<Button-3>", lambda e: self.reset_single_bet("wild5"))
        self.bet_widgets["wild5"] = self.wild5_display

        # PPair (column 2)
        ppair_label = tk.Label(row_frame, text=" PPair:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        ppair_label.grid(row=0, column=2, sticky='w')
        self.ppair_var = tk.StringVar(value="0")
        self.ppair_display = tk.Label(row_frame, textvariable=self.ppair_var, font=('Arial', 14),
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ppair_display.grid(row=0, column=3, padx=5, sticky='w')
        self.ppair_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ppair"))
        self.ppair_display.bind("<Button-3>", lambda e: self.reset_single_bet("ppair"))
        self.bet_widgets["ppair"] = self.ppair_display

        # 第三行：Ante和Bonus区域
        ante_bonus_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        ante_bonus_frame.pack(fill=tk.X, padx=20, pady=5)

        # Ante区域
        ante_label = tk.Label(ante_bonus_frame, text="   Ante:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        ante_label.pack(side=tk.LEFT)

        self.ante_var = tk.StringVar(value="0")
        self.ante_display = tk.Label(ante_bonus_frame, textvariable=self.ante_var, font=('Arial', 14), 
                                    bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.ante_display.pack(side=tk.LEFT, padx=5)
        self.ante_display.bind("<Button-1>", lambda e: self.add_chip_to_bet("ante"))
        self.ante_display.bind("<Button-3>", lambda e: self.reset_single_bet("ante"))
        self.bet_widgets["ante"] = self.ante_display

        # 等号
        tk.Label(ante_bonus_frame, text="=", font=('Arial', 14), bg='#2a4a3c', fg='white').pack(side=tk.LEFT, padx=5)

        # Bonus区域（与Ante同步）
        self.bonus_var = tk.StringVar(value="0")
        self.bonus_display = tk.Label(ante_bonus_frame, textvariable=self.bonus_var, font=('Arial', 14), 
                                    fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.bonus_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["bonus"] = self.bonus_display

        bonus_label = tk.Label(ante_bonus_frame, text=": Bonus", font=('Arial', 14), bg='#2a4a3c', fg='white')
        bonus_label.pack(side=tk.LEFT)

        # 第四行：Play区域
        play_frame = tk.Frame(bet_frame, bg='#2a4a3c')
        play_frame.pack(fill=tk.X, padx=18, pady=5)

        play_label = tk.Label(play_frame, text="    Play:", font=('Arial', 14), bg='#2a4a3c', fg='white')
        play_label.pack(side=tk.LEFT)

        self.play_var = tk.StringVar(value="0")
        self.play_display = tk.Label(play_frame, textvariable=self.play_var, font=('Arial', 14), 
                                bg='white', fg='black', width=5, relief=tk.SUNKEN, padx=5)
        self.play_display.pack(side=tk.LEFT, padx=5)
        self.bet_widgets["play"] = self.play_display

        # 提示文字
        self.hint_label = tk.Label(bet_frame, text="选择要弃的牌，然后下注Play", 
                                font=('Arial', 12), bg='#2a4a3c', fg='#FFD700')
        self.hint_label.pack(pady=(0, 10))

        # 游戏操作按钮框架 - 用于放置所有操作按钮
        self.action_frame = tk.Frame(control_frame, bg='#2a4a3c')
        self.action_frame.pack(fill=tk.X, pady=10)

        # 创建一个框架来容纳重置按钮和开始游戏按钮
        start_button_frame = tk.Frame(self.action_frame, bg='#2a4a3c')
        start_button_frame.pack(pady=10)

        # 添加"重设金额"按钮
        self.reset_bets_button = tk.Button(
            start_button_frame, text="重设金额", 
            command=self.reset_bets, font=('Arial', 14),
            bg='#F44336', fg='white', width=10
        )
        self.reset_bets_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # 开始游戏按钮
        self.start_button = tk.Button(
            start_button_frame, text="开始游戏", 
            command=self.start_game, font=('Arial', 14),
            bg='#4CAF50', fg='white', width=10
        )
        self.start_button.pack(side=tk.LEFT)
        
        # 状态信息
        self.status_label = tk.Label(
            control_frame, text="设置下注金额并开始游戏", 
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.status_label.pack(pady=5, fill=tk.X)

        # 本局下注和上局获胜金额显示
        bet_info_frame = tk.Frame(control_frame, bg='#2a4a3c', bd=2, relief=tk.RAISED)
        bet_info_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        # 本局下注金额
        self.current_bet_label = tk.Label(
            bet_info_frame, text="本局下注: $0.00", 
            font=('Arial', 14), bg='#2a4a3c', fg='white'
        )
        self.current_bet_label.pack(pady=5, padx=10, anchor='w')
        
        # 上局获胜金额
        last_win_row = tk.Frame(bet_info_frame, bg='#2a4a3c')
        last_win_row.pack(fill=tk.X, padx=10, pady=5)

        self.last_win_label = tk.Label(
            last_win_row, text="上局获胜: $0.00", 
            font=('Arial', 14), bg='#2a4a3c', fg='#FFD700'
        )
        self.last_win_label.pack(side=tk.LEFT)

        self.info_button = tk.Button(
            last_win_row,
            text="ℹ️",
            command=self.show_game_instructions,
            bg='#4B8BBE',
            fg='white',
            font=('Arial', 12),
            width=3,
            relief=tk.FLAT
        )
        self.info_button.pack(side=tk.RIGHT)

    def animate_collect_cards(self, auto_reset):
        """执行收牌动画：先翻转所有牌为背面，然后向右收起"""
        # 禁用所有按钮
        self.disable_action_buttons()
        
        # 只处理仍然存在的卡片标签
        valid_card_labels = []
        for card_label in self.active_card_labels:
            try:
                # 检查卡片是否还存在
                if card_label.winfo_exists():
                    valid_card_labels.append(card_label)
            except tk.TclError:
                # 卡片已经被销毁，跳过
                continue

        if not valid_card_labels:
            # 没有牌，直接重置
            self._do_reset(auto_reset)
            return

        # 设置所有牌的目标位置为屏幕右侧外
        for card_label in valid_card_labels:
            card_label.target_pos = (1200, card_label.winfo_y())  # 目标x为窗口右侧外

        # 开始移动
        self.animate_card_out_step(auto_reset, valid_card_labels)

    def animate_card_out_step(self, auto_reset, card_labels):
        """移动卡片出屏幕的每一步"""
        all_done = True
        for card_label in card_labels[:]:  # 遍历副本，因为可能删除
            if not hasattr(card_label, 'target_pos'):
                continue

            try:
                current_x = card_label.winfo_x()
                target_x, target_y = card_label.target_pos

                # 计算新位置
                dx = target_x - current_x
                if abs(dx) < 5:
                    card_label.place(x=target_x, y=target_y)
                    # 移除该卡片
                    card_label.destroy()
                    if card_label in card_labels:
                        card_labels.remove(card_label)
                    continue

                new_x = current_x + dx * 0.2
                card_label.place(x=new_x)
                all_done = False
            except tk.TclError:
                # 卡片已被销毁，从列表中移除
                if card_label in card_labels:
                    card_labels.remove(card_label)
                continue

        if not all_done:
            self.after(20, lambda: self.animate_card_out_step(auto_reset, card_labels))
        else:
            # 所有动画完成，重置游戏
            self._do_reset(auto_reset)

def main(initial_balance=1000, username="Guest"):
    app = WildFiveGUI(initial_balance, username)
    app.mainloop()
    return app.balance

if __name__ == "__main__":
    # 独立运行时的示例调用
    final_balance = main()
    print(f"Final balance: {final_balance}")