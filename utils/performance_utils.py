#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能优化工具模块
提供缓存、连接池、内存管理等性能优化功能
"""

import time
import weakref
import threading
import asyncio
from functools import wraps, lru_cache
from typing import Any, Dict, Optional, Callable, Union, TypeVar, Generic
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc
import os

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

try:
    from utils.config_manager import get_config
except ImportError:
    def get_config(key: str, default: Any = None) -> Any:
        return default


T = TypeVar('T')


@dataclass
class CacheStats:
    """缓存统计"""
    hits: int = 0
    misses: int = 0
    size: int = 0
    max_size: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class TTLCache(Generic[T]):
    """带TTL的缓存"""
    
    def __init__(self, max_size: int = 1000, ttl: float = 3600):
        self.max_size = max_size
        self.ttl = ttl
        self.cache: Dict[str, tuple] = {}  # key -> (value, timestamp)
        self.access_times: Dict[str, float] = {}
        self.lock = threading.RLock()
        self.stats = CacheStats(max_size=max_size)
    
    def get(self, key: str) -> Optional[T]:
        """获取缓存值"""
        with self.lock:
            if key not in self.cache:
                self.stats.misses += 1
                return None
            
            value, timestamp = self.cache[key]
            current_time = time.time()
            
            # 检查是否过期
            if current_time - timestamp > self.ttl:
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
                self.stats.misses += 1
                self.stats.size -= 1
                return None
            
            # 更新访问时间
            self.access_times[key] = current_time
            self.stats.hits += 1
            return value
    
    def set(self, key: str, value: T) -> None:
        """设置缓存值"""
        with self.lock:
            current_time = time.time()
            
            # 如果缓存已满，清理最久未访问的项
            if len(self.cache) >= self.max_size and key not in self.cache:
                self._evict_lru()
            
            # 设置新值
            self.cache[key] = (value, current_time)
            self.access_times[key] = current_time
            
            if key not in self.cache:
                self.stats.size += 1
    
    def delete(self, key: str) -> bool:
        """删除缓存项"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
                self.stats.size -= 1
                return True
            return False
    
    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            self.stats.size = 0
    
    def _evict_lru(self) -> None:
        """清理最久未访问的项"""
        if not self.access_times:
            return
        
        # 找到最久未访问的键
        oldest_key = min(self.access_times.keys(), 
                        key=lambda k: self.access_times[k])
        
        del self.cache[oldest_key]
        del self.access_times[oldest_key]
        self.stats.size -= 1
    
    def cleanup_expired(self) -> int:
        """清理过期项"""
        with self.lock:
            current_time = time.time()
            expired_keys = []
            
            for key, (_, timestamp) in self.cache.items():
                if current_time - timestamp > self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
            
            self.stats.size -= len(expired_keys)
            return len(expired_keys)


class AsyncConnectionPool:
    """异步连接池"""
    
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.pool = asyncio.Queue(maxsize=max_connections)
        self.active_connections = 0
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> Any:
        """获取连接"""
        try:
            # 尝试从池中获取连接
            connection = self.pool.get_nowait()
            return connection
        except asyncio.QueueEmpty:
            async with self.lock:
                if self.active_connections < self.max_connections:
                    # 创建新连接
                    connection = await self._create_connection()
                    self.active_connections += 1
                    return connection
                else:
                    # 等待可用连接
                    return await self.pool.get()
    
    async def release(self, connection: Any) -> None:
        """释放连接"""
        if await self._is_connection_valid(connection):
            try:
                self.pool.put_nowait(connection)
            except asyncio.QueueFull:
                # 池已满，关闭连接
                await self._close_connection(connection)
                async with self.lock:
                    self.active_connections -= 1
        else:
            # 连接无效，关闭并减少计数
            await self._close_connection(connection)
            async with self.lock:
                self.active_connections -= 1
    
    async def _create_connection(self) -> Any:
        """创建新连接（需要子类实现）"""
        raise NotImplementedError
    
    async def _is_connection_valid(self, connection: Any) -> bool:
        """检查连接是否有效（需要子类实现）"""
        return True
    
    async def _close_connection(self, connection: Any) -> None:
        """关闭连接（需要子类实现）"""
        pass
    
    async def close_all(self) -> None:
        """关闭所有连接"""
        while not self.pool.empty():
            try:
                connection = self.pool.get_nowait()
                await self._close_connection(connection)
            except asyncio.QueueEmpty:
                break
        
        async with self.lock:
            self.active_connections = 0


class MemoryManager:
    """内存管理器"""
    
    def __init__(self, memory_limit_mb: int = 512):
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.warning_threshold = 0.8  # 80%警告阈值
        self.critical_threshold = 0.95  # 95%强制清理阈值
        
        if PSUTIL_AVAILABLE:
            self.process = psutil.Process(os.getpid())
        else:
            self.process = None
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """获取内存使用情况"""
        if not PSUTIL_AVAILABLE or not self.process:
            # 降级到基本内存信息
            return {
                'rss': 0,
                'vms': 0,
                'percent': 0.0,
                'limit_bytes': self.memory_limit_bytes,
                'usage_ratio': 0.0,
                'available_bytes': self.memory_limit_bytes
            }
        
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            return {
                'rss': memory_info.rss,
                'vms': memory_info.vms,
                'percent': memory_percent,
                'limit_bytes': self.memory_limit_bytes,
                'usage_ratio': memory_info.rss / self.memory_limit_bytes,
                'available_bytes': self.memory_limit_bytes - memory_info.rss
            }
        except Exception:
            # 如果psutil调用失败，返回默认值
            return {
                'rss': 0,
                'vms': 0,
                'percent': 0.0,
                'limit_bytes': self.memory_limit_bytes,
                'usage_ratio': 0.0,
                'available_bytes': self.memory_limit_bytes
            }
    
    def check_memory_status(self) -> str:
        """检查内存状态"""
        usage = self.get_memory_usage()
        ratio = usage['usage_ratio']
        
        if ratio >= self.critical_threshold:
            return 'critical'
        elif ratio >= self.warning_threshold:
            return 'warning'
        else:
            return 'normal'
    
    def force_garbage_collection(self) -> Dict[str, int]:
        """强制垃圾回收"""
        collected = {}
        for generation in range(3):
            collected[f'gen_{generation}'] = gc.collect(generation)
        
        return collected
    
    def is_memory_available(self, required_bytes: int) -> bool:
        """检查是否有足够内存"""
        usage = self.get_memory_usage()
        return usage['available_bytes'] >= required_bytes


class BatchProcessor:
    """批处理器"""
    
    def __init__(self, batch_size: int = 10, max_workers: int = 4):
        self.batch_size = batch_size
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def process_batch(self, items: list, processor_func: Callable, 
                     **kwargs) -> list:
        """批量处理项目"""
        results = []
        
        # 分批处理
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            
            # 并发处理批次内的项目
            futures = []
            for item in batch:
                future = self.executor.submit(processor_func, item, **kwargs)
                futures.append(future)
            
            # 收集结果
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    print(f"批处理项目失败: {e}")
        
        return results
    
    async def process_batch_async(self, items: list, 
                                 processor_func: Callable,
                                 **kwargs) -> list:
        """异步批量处理项目"""
        results = []
        
        # 分批处理
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            
            # 创建任务
            tasks = []
            for item in batch:
                if asyncio.iscoroutinefunction(processor_func):
                    task = processor_func(item, **kwargs)
                else:
                    task = asyncio.create_task(
                        asyncio.to_thread(processor_func, item, **kwargs)
                    )
                tasks.append(task)
            
            # 等待批次完成
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for result in batch_results:
                if not isinstance(result, Exception) and result is not None:
                    results.append(result)
                elif isinstance(result, Exception):
                    print(f"异步批处理项目失败: {result}")
        
        return results
    
    def close(self):
        """关闭线程池"""
        self.executor.shutdown(wait=True)


def cached_with_ttl(ttl: float = 3600, max_size: int = 1000):
    """带TTL的缓存装饰器"""
    cache = TTLCache(max_size=max_size, ttl=ttl)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
            
            # 尝试从缓存获取
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result
        
        # 添加缓存管理方法
        wrapper.cache_clear = cache.clear
        wrapper.cache_stats = lambda: cache.stats
        wrapper.cache_cleanup = cache.cleanup_expired
        
        return wrapper
    return decorator


def rate_limit(calls_per_second: float = 1.0):
    """限流装饰器"""
    min_interval = 1.0 / calls_per_second
    last_call_time = [0.0]
    lock = threading.Lock()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                current_time = time.time()
                time_since_last_call = current_time - last_call_time[0]
                
                if time_since_last_call < min_interval:
                    sleep_time = min_interval - time_since_last_call
                    time.sleep(sleep_time)
                
                last_call_time[0] = time.time()
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


async def rate_limit_async(calls_per_second: float = 1.0):
    """异步限流装饰器"""
    min_interval = 1.0 / calls_per_second
    last_call_time = [0.0]
    lock = asyncio.Lock()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with lock:
                current_time = time.time()
                time_since_last_call = current_time - last_call_time[0]
                
                if time_since_last_call < min_interval:
                    sleep_time = min_interval - time_since_last_call
                    await asyncio.sleep(sleep_time)
                
                last_call_time[0] = time.time()
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = {}
        self.memory_manager = MemoryManager(
            get_config('performance.memory_limit_mb', 512)
        )
    
    def start_timing(self, operation: str) -> str:
        """开始计时"""
        timing_id = f"{operation}_{time.time()}"
        self.metrics[timing_id] = {
            'operation': operation,
            'start_time': time.time(),
            'memory_before': self.memory_manager.get_memory_usage()
        }
        return timing_id
    
    def end_timing(self, timing_id: str) -> Dict[str, Any]:
        """结束计时"""
        if timing_id not in self.metrics:
            return {}
        
        metric = self.metrics[timing_id]
        end_time = time.time()
        memory_after = self.memory_manager.get_memory_usage()
        
        result = {
            'operation': metric['operation'],
            'duration': end_time - metric['start_time'],
            'memory_before': metric['memory_before'],
            'memory_after': memory_after,
            'memory_delta': memory_after['rss'] - metric['memory_before']['rss']
        }
        
        del self.metrics[timing_id]
        return result
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = {
            'memory': self.memory_manager.get_memory_usage(),
            'memory_status': self.memory_manager.check_memory_status(),
            'active_timings': len(self.metrics)
        }
        
        # 添加系统指标（如果可用）
        if PSUTIL_AVAILABLE:
            try:
                status['cpu_percent'] = psutil.cpu_percent()
                status['disk_usage'] = psutil.disk_usage('/').percent
            except Exception:
                status['cpu_percent'] = 0.0
                status['disk_usage'] = 0.0
        else:
            status['cpu_percent'] = 0.0
            status['disk_usage'] = 0.0
        
        return status


# 全局实例
performance_monitor = PerformanceMonitor()
batch_processor = BatchProcessor(
    batch_size=get_config('performance.batch_size', 10),
    max_workers=get_config('performance.max_workers', 4)
)