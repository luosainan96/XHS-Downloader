#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一日志管理模块
提供结构化日志记录、性能监控和错误追踪
"""

import logging
import logging.handlers
import json
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import sys
import os

try:
    from utils.config_manager import get_config
except ImportError:
    def get_config(key: str, default: Any = None) -> Any:
        return default


class LogLevel(Enum):
    """日志级别"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class LogEntry:
    """结构化日志条目"""
    timestamp: float
    level: str
    module: str
    operation: str
    message: str
    duration: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    error_details: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str, log_dir: str = "logs"):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # 配置日志记录器
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self._get_log_level())
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers()
        
        # 操作计时器
        self._timers = {}
        self._timer_lock = threading.RLock()
    
    def _get_log_level(self) -> int:
        """获取日志级别"""
        level_str = get_config('logging.level', 'INFO').upper()
        return getattr(logging, level_str, logging.INFO)
    
    def _setup_handlers(self):
        """设置日志处理器"""
        formatter = self._create_formatter()
        
        # 控制台处理器
        if get_config('logging.console_enabled', True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(self._get_log_level())
            self.logger.addHandler(console_handler)
        
        # 文件处理器
        if get_config('logging.file_enabled', True):
            file_handler = self._create_file_handler()
            file_handler.setFormatter(formatter)
            file_handler.setLevel(self._get_log_level())
            self.logger.addHandler(file_handler)
        
        # JSON结构化日志处理器
        json_handler = self._create_json_handler()
        self.logger.addHandler(json_handler)
    
    def _create_formatter(self) -> logging.Formatter:
        """创建日志格式化器"""
        format_str = get_config('logging.format', 
                               '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        return logging.Formatter(format_str)
    
    def _create_file_handler(self) -> logging.Handler:
        """创建文件处理器"""
        log_file = self.log_dir / f"{self.name}.log"
        max_bytes = get_config('logging.max_file_size_mb', 10) * 1024 * 1024
        backup_count = get_config('logging.backup_count', 5)
        
        handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        return handler
    
    def _create_json_handler(self) -> logging.Handler:
        """创建JSON结构化日志处理器"""
        json_log_file = self.log_dir / f"{self.name}_structured.jsonl"
        max_bytes = get_config('logging.max_file_size_mb', 10) * 1024 * 1024
        backup_count = get_config('logging.backup_count', 5)
        
        handler = logging.handlers.RotatingFileHandler(
            json_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # 自定义格式化器，输出JSON
        handler.setFormatter(JSONFormatter())
        return handler
    
    def debug(self, message: str, operation: str = "", **kwargs):
        """记录DEBUG级别日志"""
        self._log(LogLevel.DEBUG, message, operation, **kwargs)
    
    def info(self, message: str, operation: str = "", **kwargs):
        """记录INFO级别日志"""
        self._log(LogLevel.INFO, message, operation, **kwargs)
    
    def warning(self, message: str, operation: str = "", **kwargs):
        """记录WARNING级别日志"""
        self._log(LogLevel.WARNING, message, operation, **kwargs)
    
    def error(self, message: str, operation: str = "", error: Exception = None, **kwargs):
        """记录ERROR级别日志"""
        error_details = None
        if error:
            error_details = {
                'type': type(error).__name__,
                'message': str(error),
                'traceback': traceback.format_exc() if error.__traceback__ else None
            }
        
        self._log(LogLevel.ERROR, message, operation, error_details=error_details, **kwargs)
    
    def critical(self, message: str, operation: str = "", error: Exception = None, **kwargs):
        """记录CRITICAL级别日志"""
        error_details = None
        if error:
            error_details = {
                'type': type(error).__name__,
                'message': str(error),
                'traceback': traceback.format_exc() if error.__traceback__ else None
            }
        
        self._log(LogLevel.CRITICAL, message, operation, error_details=error_details, **kwargs)
    
    def _log(self, level: LogLevel, message: str, operation: str = "",
            duration: float = None, metadata: Dict = None, 
            error_details: Dict = None):
        """内部日志记录方法"""
        
        # 创建结构化日志条目
        log_entry = LogEntry(
            timestamp=time.time(),
            level=level.name,
            module=self.name,
            operation=operation,
            message=message,
            duration=duration,
            metadata=metadata,
            error_details=error_details
        )
        
        # 使用标准日志记录器记录
        self.logger.log(level.value, message, extra={'structured_data': log_entry})
    
    def start_timer(self, operation: str) -> str:
        """开始计时"""
        timer_id = f"{operation}_{time.time()}_{id(threading.current_thread())}"
        
        with self._timer_lock:
            self._timers[timer_id] = {
                'operation': operation,
                'start_time': time.time()
            }
        
        return timer_id
    
    def end_timer(self, timer_id: str, message: str = "", **kwargs) -> Optional[float]:
        """结束计时并记录"""
        with self._timer_lock:
            if timer_id not in self._timers:
                self.warning(f"计时器不存在: {timer_id}")
                return None
            
            timer_info = self._timers.pop(timer_id)
        
        duration = time.time() - timer_info['start_time']
        
        if not message:
            message = f"操作 {timer_info['operation']} 完成"
        
        self.info(
            message, 
            operation=timer_info['operation'],
            duration=duration,
            **kwargs
        )
        
        return duration
    
    def log_performance(self, operation: str, duration: float, 
                       metadata: Dict = None):
        """记录性能信息"""
        self.info(
            f"性能监控: {operation} 耗时 {duration:.3f}s",
            operation=operation,
            duration=duration,
            metadata=metadata or {}
        )
    
    def log_user_action(self, action: str, user_id: str = "anonymous",
                       details: Dict = None):
        """记录用户操作"""
        metadata = {
            'user_id': user_id,
            'action_type': 'user_action',
            **(details or {})
        }
        
        self.info(
            f"用户操作: {action}",
            operation="user_action",
            metadata=metadata
        )
    
    def log_api_call(self, endpoint: str, method: str, status_code: int,
                    duration: float, request_size: int = None,
                    response_size: int = None):
        """记录API调用"""
        metadata = {
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'request_size': request_size,
            'response_size': response_size
        }
        
        level = LogLevel.INFO if 200 <= status_code < 400 else LogLevel.WARNING
        
        self._log(
            level,
            f"API调用: {method} {endpoint} -> {status_code}",
            operation="api_call",
            duration=duration,
            metadata=metadata
        )


class JSONFormatter(logging.Formatter):
    """JSON格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON"""
        
        # 获取结构化数据
        structured_data = getattr(record, 'structured_data', None)
        
        if structured_data and isinstance(structured_data, LogEntry):
            return structured_data.to_json()
        else:
            # 降级到基本JSON格式
            log_data = {
                'timestamp': record.created,
                'level': record.levelname,
                'module': record.name,
                'message': record.getMessage(),
                'pathname': record.pathname,
                'lineno': record.lineno
            }
            
            if record.exc_info:
                log_data['exception'] = self.formatException(record.exc_info)
            
            return json.dumps(log_data, ensure_ascii=False, default=str)


class PerformanceLogger:
    """性能日志记录器"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.operation_stats = {}
        self.stats_lock = threading.RLock()
    
    def __call__(self, operation: str = None):
        """装饰器使用"""
        def decorator(func):
            op_name = operation or f"{func.__module__}.{func.__name__}"
            
            def wrapper(*args, **kwargs):
                timer_id = self.logger.start_timer(op_name)
                try:
                    result = func(*args, **kwargs)
                    duration = self.logger.end_timer(
                        timer_id, 
                        f"函数 {op_name} 执行完成"
                    )
                    
                    # 更新统计信息
                    self._update_stats(op_name, duration, success=True)
                    
                    return result
                except Exception as e:
                    self.logger.end_timer(timer_id)
                    self.logger.error(
                        f"函数 {op_name} 执行失败",
                        operation=op_name,
                        error=e
                    )
                    
                    # 更新统计信息
                    self._update_stats(op_name, None, success=False)
                    
                    raise
            
            return wrapper
        return decorator
    
    def _update_stats(self, operation: str, duration: Optional[float], 
                     success: bool):
        """更新操作统计"""
        with self.stats_lock:
            if operation not in self.operation_stats:
                self.operation_stats[operation] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'failed_calls': 0,
                    'total_duration': 0.0,
                    'avg_duration': 0.0,
                    'min_duration': float('inf'),
                    'max_duration': 0.0
                }
            
            stats = self.operation_stats[operation]
            stats['total_calls'] += 1
            
            if success:
                stats['successful_calls'] += 1
                if duration is not None:
                    stats['total_duration'] += duration
                    stats['avg_duration'] = stats['total_duration'] / stats['successful_calls']
                    stats['min_duration'] = min(stats['min_duration'], duration)
                    stats['max_duration'] = max(stats['max_duration'], duration)
            else:
                stats['failed_calls'] += 1
    
    def get_stats(self) -> Dict[str, Dict]:
        """获取性能统计"""
        with self.stats_lock:
            return dict(self.operation_stats)
    
    def log_stats_summary(self):
        """记录统计摘要"""
        stats = self.get_stats()
        for operation, data in stats.items():
            self.logger.info(
                f"性能统计 - {operation}: "
                f"总调用{data['total_calls']}次, "
                f"成功{data['successful_calls']}次, "
                f"失败{data['failed_calls']}次, "
                f"平均耗时{data['avg_duration']:.3f}s",
                operation="performance_stats",
                metadata=data
            )


# 全局日志管理器
_loggers = {}
_logger_lock = threading.Lock()


def get_logger(name: str) -> StructuredLogger:
    """获取日志记录器实例"""
    with _logger_lock:
        if name not in _loggers:
            _loggers[name] = StructuredLogger(name)
        return _loggers[name]


def get_performance_logger(name: str) -> PerformanceLogger:
    """获取性能日志记录器"""
    logger = get_logger(name)
    return PerformanceLogger(logger)


# 常用日志记录器实例
main_logger = get_logger("xhs_downloader")
browser_logger = get_logger("browser")
network_logger = get_logger("network")
file_logger = get_logger("file_operations")

# 性能监控
performance_logger = get_performance_logger("performance")