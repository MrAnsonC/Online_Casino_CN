import os
import secrets
import hashlib
import time
import json
import math
import sys
import threading
from typing import List, Tuple, Optional

# 扑克牌花色和点数
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        
    def __repr__(self):
        return f"{self.rank}{self.suit}"
    
    def to_dict(self):
        return {"suit": self.suit, "rank": self.rank}

# ========================================================
# 硬编码测试用牌序（按您希望出现的顺序排列）
# 注意：这些牌会出现在牌堆的最前面，切牌位置设为 0 时，它们将最先被发出。
# 格式: (花色符号, 点数)  花色符号可使用 ♠ ♥ ♦ ♣
# ========================================================
FIXED_CARDS: List[Tuple[str, str]] = [
    ("♠", "K"),
    ("♣", "J"),
    ("♠", "4"),
    ("♥", "5"),
    ("♥", "7"),
    ("♥", "J"),
    ("♣", "J"),
]

# 切牌位置（从0开始，0表示从第一张牌开始发牌）
FIXED_CUT_POSITION = 1

# ========================================================
# 以下代码与原 shuffle.py 相同（量子熵源、混沌系统、英格玛机）
# 但生成牌组时会优先插入固定牌，其余牌按标准顺序补全（不再洗牌）
# ========================================================

class QuantumEntropySource:
    """量子熵源收集器 - 多源熵混合"""
    def __init__(self):
        self.entropy_pool = bytearray()
        
    def collect(self):
        """从多个系统源收集熵"""
        self._add(os.urandom(64))
        self._collect_time_jitter()
        self._collect_mem_latency()
        self._add(os.getpid().to_bytes(4, 'big'))
        self._add(os.getppid().to_bytes(4, 'big'))
        self._add(time.time_ns().to_bytes(8, 'big'))
        self._add(time.perf_counter_ns().to_bytes(8, 'big'))
        self._collect_scheduling_delay()
        self._collect_filesystem_entropy()
        return hashlib.sha3_512(self.entropy_pool).digest()
    
    def _add(self, data):
        self.entropy_pool.extend(data)
        self.entropy_pool.extend(time.time_ns().to_bytes(8, 'big'))
    
    def _collect_time_jitter(self):
        delays = bytearray()
        for _ in range(1000):
            start = time.perf_counter_ns()
            _ = sum(math.sin(i) for i in range(100))
            end = time.perf_counter_ns()
            delays.extend((end - start).to_bytes(8, 'big'))
        self._add(delays)
    
    def _collect_mem_latency(self):
        arr_size = 1024 * 1024
        arr = bytearray(arr_size)
        for i in range(arr_size):
            arr[i] = (i * 997) & 0xFF
        delays = bytearray()
        for _ in range(1000):
            idx = secrets.randbelow(arr_size)
            start = time.perf_counter_ns()
            _ = arr[idx]
            end = time.perf_counter_ns()
            delays.extend((end - start).to_bytes(8, 'big'))
        self._add(delays)
    
    def _collect_scheduling_delay(self):
        delays = bytearray()
        thread_count = 5
        results = [None] * thread_count
        start_events = [threading.Event() for _ in range(thread_count)]
        done_events = [threading.Event() for _ in range(thread_count)]
        
        def thread_func(idx, start_event, done_event):
            start_event.wait()
            start_time = time.perf_counter_ns()
            _ = sum(i*i for i in range(100))
            results[idx] = start_time
            done_event.set()
        
        threads = []
        for i in range(thread_count):
            t = threading.Thread(target=thread_func, args=(i, start_events[i], done_events[i]))
            t.daemon = True
            threads.append(t)
            t.start()
        
        time.sleep(0.01)
        for i in range(thread_count):
            signal_time = time.perf_counter_ns()
            start_events[i].set()
            done_events[i].wait(timeout=1.0)
            if results[i] is not None:
                delay = results[i] - signal_time
                delays.extend(delay.to_bytes(8, 'big'))
        return delays
    
    def _collect_filesystem_entropy(self):
        fs_entropy = bytearray()
        try:
            files = os.listdir('.')
            for file in files[:10]:
                try:
                    stat = os.stat(file)
                    fs_entropy.extend(stat.st_size.to_bytes(8, 'big'))
                    fs_entropy.extend(int(stat.st_mtime * 1e9).to_bytes(8, 'big'))
                    fs_entropy.extend(int(stat.st_ctime * 1e9).to_bytes(8, 'big'))
                except (OSError, FileNotFoundError):
                    continue
        except OSError:
            pass
        try:
            script_stat = os.stat(__file__)
            fs_entropy.extend(script_stat.st_size.to_bytes(8, 'big'))
            fs_entropy.extend(int(script_stat.st_mtime * 1e9).to_bytes(8, 'big'))
            fs_entropy.extend(int(script_stat.st_ctime * 1e9).to_bytes(8, 'big'))
        except OSError:
            pass
        try:
            fs_stat = os.statvfs('.')
            fs_entropy.extend(fs_stat.f_blocks.to_bytes(8, 'big'))
            fs_entropy.extend(fs_stat.f_bfree.to_bytes(8, 'big'))
            fs_entropy.extend(fs_stat.f_bavail.to_bytes(8, 'big'))
        except (OSError, AttributeError):
            pass
        if fs_entropy:
            self._add(fs_entropy)

class ChaosSystem:
    def __init__(self, seed):
        self.x = float(int.from_bytes(seed[:8], 'big')) / 2**64
        self.r = 3.9 + (int.from_bytes(seed[8:16], 'big') % 100) / 1000.0
        self.fs_factor = float(int.from_bytes(seed[16:24], 'big')) / 2**64 if len(seed) >= 24 else 0.5
    
    def next(self):
        self.x = self.r * self.x * (1.0 - self.x)
        self.x = (self.x + self.fs_factor) % 1.0
        return self.x
    
    def random_bytes(self, length):
        result = bytearray()
        while len(result) < length:
            chaos_val = self.next()
            int_val = int(chaos_val * 2**64)
            result.extend(int_val.to_bytes(8, 'big'))
        return bytes(result[:length])

class EnigmaShuffler:
    def __init__(self, key):
        self.rotors = [
            self._create_rotor(key[0:16]),
            self._create_rotor(key[16:32]),
            self._create_rotor(key[32:48])
        ]
        self.position = [0, 0, 0]
    
    def _create_rotor(self, seed):
        arr = list(range(256))
        seed_int = int.from_bytes(seed, 'big')
        for i in range(255, 0, -1):
            seed_int = (seed_int * 6364136223846793005 + 1) & 0xFFFFFFFFFFFFFFFF
            j = seed_int % (i + 1)
            arr[i], arr[j] = arr[j], arr[i]
        return arr
    
    def _advance(self):
        self.position[0] = (self.position[0] + 1) % 256
        if self.position[0] == 0:
            self.position[1] = (self.position[1] + 1) % 256
            if self.position[1] == 0:
                self.position[2] = (self.position[2] + 1) % 256
    
    def shuffle(self, deck):
        n = len(deck)
        for i in range(n - 1, 0, -1):
            self._advance()
            val = i % 256
            for rotor_idx in range(3):
                rotor = self.rotors[rotor_idx]
                pos = self.position[rotor_idx]
                val = rotor[(val + pos) % 256]
            j = val % (i + 1)
            deck[i], deck[j] = deck[j], deck[i]
        return deck

def generate_full_standard_deck(has_joker=False, deck_count=1):
    """生成标准完整牌组（未洗牌，按花色+点数排序）"""
    deck = []
    for _ in range(deck_count):
        for suit in SUITS:
            for rank in RANKS:
                deck.append(Card(suit, rank))
        if has_joker:
            deck.append(Card('JOKER', 'A'))
    return deck

def generate_test_deck(has_joker=False, deck_count=1):
    """
    生成测试专用牌组：
    1. 先放入硬编码的固定牌序（FIXED_CARDS）
    2. 然后从标准牌组中剔除已经使用过的牌，按标准顺序补充剩余牌
    3. 重复 deck_count 次（如果需要多副牌，固定牌序列会重复出现，然后补全）
    """
    if deck_count != 1:
        # 多副牌情况：简单起见，我们只支持单副牌测试，因为固定牌序列通常用于单副牌测试
        print("Warning: deck_count > 1 时测试固定牌序可能不符合预期，建议 deck_count=1", file=sys.stderr)
    
    # 构建固定牌对象列表
    fixed_cards_obj = [Card(suit, rank) for suit, rank in FIXED_CARDS]
    
    # 生成标准完整牌组
    full_deck = generate_full_standard_deck(has_joker, deck_count=1)
    
    # 从 full_deck 中移除固定牌（按 (suit, rank) 匹配，只移除等量的出现次数）
    remaining_deck = []
    fixed_set = [(card.suit, card.rank) for card in fixed_cards_obj]
    for card in full_deck:
        key = (card.suit, card.rank)
        if key in fixed_set:
            # 移除一个匹配项（只移除第一个出现的）
            fixed_set.remove(key)
        else:
            remaining_deck.append(card)
    
    # 构建最终牌组：固定牌 + 剩余牌（剩余牌保持标准顺序）
    test_deck = fixed_cards_obj + remaining_deck
    
    # 如果需要多副牌，重复上述过程（但固定牌也会重复）
    if deck_count > 1:
        final_deck = []
        for _ in range(deck_count):
            # 重新生成单副测试牌组
            single = generate_test_deck(has_joker, deck_count=1)
            final_deck.extend(single)
        test_deck = final_deck
    
    return test_deck

def generate_shuffled_deck(has_joker=False, deck_count=1):
    """生成测试牌组（固定牌序在前，剩余牌按标准顺序）"""
    # 直接生成测试牌组，不进行洗牌
    deck = generate_test_deck(has_joker, deck_count)
    return [card.to_dict() for card in deck]

if __name__ == "__main__":
    # 解析命令行参数（与原 shuffle.py 兼容）
    has_joker = False
    deck_count = 1
    
    if len(sys.argv) > 1:
        has_joker_arg = sys.argv[1].lower()
        if has_joker_arg in ['true', '1', 'yes']:
            has_joker = True
        if len(sys.argv) > 2:
            try:
                deck_count = int(sys.argv[2])
            except ValueError:
                deck_count = 1
    
    # 生成测试牌组
    shuffled_deck = generate_shuffled_deck(has_joker, deck_count)
    total_cards = len(shuffled_deck)
    
    # 使用硬编码的切牌位置，确保固定牌在最前面
    cut_position = FIXED_CUT_POSITION
    if cut_position >= total_cards:
        cut_position = 0
    
    # 输出 JSON
    print(json.dumps({
        "deck": shuffled_deck,
        "cut_position": cut_position,
        "has_joker": has_joker,
        "deck_count": deck_count,
        "total_cards": total_cards
    }, ensure_ascii=False))