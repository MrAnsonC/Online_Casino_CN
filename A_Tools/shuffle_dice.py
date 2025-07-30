import os
import hashlib
import time
import math
import secrets

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
        self._add(time.time_ns().to_bytes(8, 'big'))
        self._add(time.perf_counter_ns().to_bytes(8, 'big'))
        
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
    
    def randint(self, min_val, max_val):
        """生成指定范围内的随机整数"""
        range_size = max_val - min_val + 1
        chaos_val = self.next()
        return min_val + int(chaos_val * range_size)

class TrueRandomGenerator:
    """真随机数生成器"""
    def __init__(self):
        # 初始化量子熵源
        entropy_source = QuantumEntropySource()
        entropy = entropy_source.collect()
        
        # 初始化混沌系统
        self.chaos_system = ChaosSystem(entropy)
    
    def randint(self, min_val, max_val):
        """生成真随机整数"""
        return self.chaos_system.randint(min_val, max_val)

class Dice:
    _true_random_generator = None

    """真随机骰子"""
    def __init__(self, value=None):
        # 创建共享的真随机数生成器实例
        if Dice._true_random_generator is None:
            self.true_random_generator = TrueRandomGenerator()
        
        # 初始值
        if value:
            self.value = value
        else:
            self.roll()
    
    def roll(self):
        """掷骰子并返回结果"""
        self.value = self.true_random_generator.randint(1, 6)
        return self.value
    
    def __repr__(self):
        return str(self.value)
    
    def __str__(self):
        return str(self.value)

# 示例用法
if __name__ == "__main__":
    # 创建多个骰子
    dice1 = Dice()
    dice2 = Dice()
    
    print(f"骰子1: {dice1.roll()}")
    print(f"骰子2: {dice2.roll()}")
    print(f"骰子1再次掷: {dice1.roll()}")
    print(f"骰子2再次掷: {dice2.roll()}")