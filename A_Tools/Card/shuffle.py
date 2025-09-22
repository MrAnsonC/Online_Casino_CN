import os
import secrets
import hashlib
import time
import json
import math
import sys
import threading

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
        
        # 6. 进程调度延迟熵
        self._collect_scheduling_delay()
        
        # 7. 文件系统元数据熵
        self._collect_filesystem_entropy()
        
        # 8. 使用SHA3-512进行熵提取
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
    
    def _collect_scheduling_delay(self):
        """收集进程调度延迟熵"""
        delays = bytearray()
        
        # 使用更简单的方法测量调度延迟
        # 创建多个线程并测量它们的启动延迟
        thread_count = 5  # 减少线程数量以提高稳定性
        results = [None] * thread_count
        start_events = [threading.Event() for _ in range(thread_count)]
        done_events = [threading.Event() for _ in range(thread_count)]
        
        def thread_func(idx, start_event, done_event):
            # 等待主线程的信号
            start_event.wait()
            # 记录线程实际开始执行的时间
            start_time = time.perf_counter_ns()
            # 执行一些简单操作
            _ = sum(i*i for i in range(100))
            results[idx] = start_time
            # 通知主线程已完成
            done_event.set()
        
        # 创建并启动所有线程
        threads = []
        for i in range(thread_count):
            t = threading.Thread(target=thread_func, args=(i, start_events[i], done_events[i]))
            t.daemon = True  # 设置为守护线程，确保程序退出时线程也会退出
            threads.append(t)
            t.start()
        
        # 给线程一些时间启动
        time.sleep(0.01)
        
        # 测量每个线程的调度延迟
        for i in range(thread_count):
            # 记录发送信号前的时间
            signal_time = time.perf_counter_ns()
            # 通知线程开始
            start_events[i].set()
            # 等待线程完成
            done_events[i].wait(timeout=1.0)  # 设置超时防止死锁
            
            # 检查线程是否成功设置了结果
            if results[i] is not None:
                # 计算调度延迟
                delay = results[i] - signal_time
                delays.extend(delay.to_bytes(8, 'big'))
        
        return delays
    
    def _collect_filesystem_entropy(self):
        """收集文件系统元数据熵"""
        fs_entropy = bytearray()
        
        try:
            # 获取当前工作目录的文件列表
            files = os.listdir('.')
            for file in files[:10]:  # 只取前10个文件，避免过多处理
                try:
                    stat = os.stat(file)
                    # 收集文件元数据：大小、修改时间、创建时间
                    fs_entropy.extend(stat.st_size.to_bytes(8, 'big'))
                    fs_entropy.extend(int(stat.st_mtime * 1e9).to_bytes(8, 'big'))
                    fs_entropy.extend(int(stat.st_ctime * 1e9).to_bytes(8, 'big'))
                except (OSError, FileNotFoundError):
                    continue
        except OSError:
            pass
        
        # 添加当前脚本文件的元数据
        try:
            script_stat = os.stat(__file__)
            fs_entropy.extend(script_stat.st_size.to_bytes(8, 'big'))
            fs_entropy.extend(int(script_stat.st_mtime * 1e9).to_bytes(8, 'big'))
            fs_entropy.extend(int(script_stat.st_ctime * 1e9).to_bytes(8, 'big'))
        except OSError:
            pass
        
        # 添加文件系统统计信息
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
    """混沌系统 - 增加不可预测性"""
    def __init__(self, seed):
        # 使用双精度浮点数范围初始化混沌系统
        self.x = float(int.from_bytes(seed[:8], 'big')) / 2**64
        self.r = 3.9 + (int.from_bytes(seed[8:16], 'big') % 100) / 1000.0
        # 添加文件系统熵作为混沌系统的额外输入
        self.fs_factor = float(int.from_bytes(seed[16:24], 'big')) / 2**64 if len(seed) >= 24 else 0.5
    
    def next(self):
        """生成下一个混沌值 (Logistic Map)"""
        self.x = self.r * self.x * (1.0 - self.x)
        # 引入文件系统熵因子增加混沌性
        self.x = (self.x + self.fs_factor) % 1.0
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

def generate_shuffled_deck(has_joker=False, deck_count=1):
    """生成加密洗牌后的牌组
    
    Args:
        has_joker: 是否包含鬼牌
        deck_count: 牌副数
    """
    # 1. 量子熵源收集
    entropy_source = QuantumEntropySource()
    entropy = entropy_source.collect()
    
    # 2. 混沌系统增强
    chaos = ChaosSystem(entropy)
    chaos_seed = chaos.random_bytes(64)
    
    # 3. 创建英格玛洗牌器
    enigma = EnigmaShuffler(chaos_seed[:48])
    
    # 4. 创建牌组
    deck = []
    for _ in range(deck_count):
        # 添加标准52张牌
        deck.extend([Card(s, r) for s in SUITS for r in RANKS])
        # 如果需要，添加鬼牌
        if has_joker:
            deck.append(Card('JOKER', 'A'))
    
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
    # 默认参数
    has_joker = False
    deck_count = 1
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        # 第一个参数：是否包含鬼牌
        has_joker_arg = sys.argv[1].lower()
        if has_joker_arg in ['true', '1', 'yes']:
            has_joker = True
        
        # 第二个参数：牌副数
        if len(sys.argv) > 2:
            try:
                deck_count = int(sys.argv[2])
            except ValueError:
                deck_count = 1
    
    shuffled_deck = generate_shuffled_deck(has_joker, deck_count)
    total_cards = len(shuffled_deck)
    cut_position = secrets.randbelow(total_cards)
    
    # **Print** the JSON and exit immediately
    print(json.dumps({
        "deck": shuffled_deck,
        "cut_position": cut_position,
        "has_joker": has_joker,
        "deck_count": deck_count,
        "total_cards": total_cards
    }, ensure_ascii=False))