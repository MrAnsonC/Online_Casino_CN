import os
import secrets
import hashlib
import time
import json
import math

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

class QuantumEntropySource:
    """量子熵源收集器 - 多源熵混合"""
    def __init__(self):
        self.entropy_pool = bytearray()
        
    def collect(self):
        """从多个系统源收集熵"""
        # 1. 系统随机源
        self._add(os.urandom(64))
        
        # 2. 时间抖动熵
        self._collect_time_jitter()
        
        # 3. 内存访问延迟
        self._collect_mem_latency()
        
        # 4. 进程/线程ID混合
        self._add(os.getpid().to_bytes(4, 'big'))
        self._add(os.getppid().to_bytes(4, 'big'))
        
        # 5. 系统时间信息
        self._add(time.time_ns().to_bytes(8, 'big'))  # 当前时间
        self._add(time.perf_counter_ns().to_bytes(8, 'big'))  # 高精度计时器
        
        # 6. 使用SHA3-512进行熵提取
        return hashlib.sha3_512(self.entropy_pool).digest()
    
    def _add(self, data):
        """添加熵到池中"""
        self.entropy_pool.extend(data)
        # 添加当前时间纳秒级精度
        self.entropy_pool.extend(time.time_ns().to_bytes(8, 'big'))
    
    def _collect_time_jitter(self):
        """测量时间抖动熵"""
        delays = bytearray()
        for _ in range(1000):
            start = time.perf_counter_ns()
            # 执行一些计算密集型操作
            _ = sum(math.sin(i) for i in range(100))
            end = time.perf_counter_ns()
            delays.extend((end - start).to_bytes(8, 'big'))
        self._add(delays)
    
    def _collect_mem_latency(self):
        """测量内存访问延迟"""
        # 创建一个大数组 (模拟DRAM)
        arr_size = 1024 * 1024  # 1MB
        arr = bytearray(arr_size)
        
        # 用随机数据填充
        for i in range(arr_size):
            arr[i] = (i * 997) & 0xFF  # 伪随机填充
        
        # 随机访问内存位置
        delays = bytearray()
        for _ in range(1000):
            idx = secrets.randbelow(arr_size)
            start = time.perf_counter_ns()
            _ = arr[idx]  # 读取操作
            end = time.perf_counter_ns()
            delays.extend((end - start).to_bytes(8, 'big'))
        
        self._add(delays)

class ChaosSystem:
    """混沌系统 - 增加不可预测性"""
    def __init__(self, seed):
        # 使用双精度浮点数范围初始化混沌系统
        self.x = float(int.from_bytes(seed[:8], 'big')) / 2**64
        self.r = 3.9 + (int.from_bytes(seed[8:16], 'big') % 100) / 1000.0
    
    def next(self):
        """生成下一个混沌值 (Logistic Map)"""
        self.x = self.r * self.x * (1.0 - self.x)
        return self.x
    
    def random_bytes(self, length):
        """生成随机字节序列"""
        result = bytearray()
        while len(result) < length:
            chaos_val = self.next()
            # 提取混沌值的8个字节
            int_val = int(chaos_val * 2**64)
            result.extend(int_val.to_bytes(8, 'big'))
        return bytes(result[:length])

class EnigmaShuffler:
    """现代版英格玛机洗牌器"""
    def __init__(self, key):
        self.rotors = [
            self._create_rotor(key[0:16]),
            self._create_rotor(key[16:32]),
            self._create_rotor(key[32:48])
        ]
        self.position = [0, 0, 0]
    
    def _create_rotor(self, seed):
        """创建转子映射 (0-255的随机排列)"""
        # 使用种子初始化Fisher-Yates洗牌
        arr = list(range(256))
        seed_int = int.from_bytes(seed, 'big')
        
        for i in range(255, 0, -1):
            # 使用种子相关的伪随机选择
            seed_int = (seed_int * 6364136223846793005 + 1) & 0xFFFFFFFFFFFFFFFF
            j = seed_int % (i + 1)
            arr[i], arr[j] = arr[j], arr[i]
        
        return arr
    
    def _advance(self):
        """推进转子位置"""
        self.position[0] = (self.position[0] + 1) % 256
        if self.position[0] == 0:
            self.position[1] = (self.position[1] + 1) % 256
            if self.position[1] == 0:
                self.position[2] = (self.position[2] + 1) % 256
    
    def shuffle(self, deck):
        """执行英格玛式洗牌"""
        n = len(deck)
        for i in range(n - 1, 0, -1):
            self._advance()
            
            # 通过转子生成随机索引
            val = i % 256
            for rotor_idx in range(3):
                rotor = self.rotors[rotor_idx]
                pos = self.position[rotor_idx]
                val = rotor[(val + pos) % 256]
            
            j = val % (i + 1)
            deck[i], deck[j] = deck[j], deck[i]
        
        return deck

def generate_shuffled_deck():
    """生成加密洗牌后的牌组"""
    # 1. 量子熵源收集
    entropy_source = QuantumEntropySource()
    entropy = entropy_source.collect()
    
    # 2. 混沌系统增强
    chaos = ChaosSystem(entropy)
    chaos_seed = chaos.random_bytes(64)
    
    # 3. 创建英格玛洗牌器
    enigma = EnigmaShuffler(chaos_seed[:48])
    
    # 4. 创建牌组
    deck = [Card(s, r) for s in SUITS for r in RANKS]
    
    # 5. 第一阶段洗牌 - 英格玛机
    deck = enigma.shuffle(deck)
    
    # 6. 第二阶段洗牌 - 混沌系统
    n = len(deck)
    for i in range(n - 1, 0, -1):
        # 使用混沌值选择交换位置
        chaos_val = chaos.next()
        j = int(chaos_val * (i + 1))
        deck[i], deck[j] = deck[j], deck[i]
    
    return [card.to_dict() for card in deck]

if __name__ == "__main__":
    shuffled_deck = generate_shuffled_deck()
    cut_position = secrets.randbelow(52)
    # **Print** the JSON and exit immediately
    print(json.dumps({
        "deck": shuffled_deck,
        "cut_position": cut_position
    }, ensure_ascii=False))