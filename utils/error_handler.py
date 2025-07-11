#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
错误处理工具模块
提供统一的错误处理、重试机制和日志记录
"""

import functools
import logging
import time
import traceback
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
from pathlib import Path
import asyncio


class ErrorSeverity(Enum):
    """错误严重性级别"""
    LOW = "low"          # 轻微错误，不影响主要功能
    MEDIUM = "medium"    # 中等错误，影响部分功能
    HIGH = "high"        # 严重错误，影响核心功能
    CRITICAL = "critical" # 致命错误，需要立即处理


class RetryConfig:
    """重试配置"""
    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0, 
                 max_delay: float = 60.0, exponential_base: float = 2.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base


class ErrorContext:
    """错误上下文信息"""
    def __init__(self, operation: str, module: str, additional_info: Dict = None):
        self.operation = operation
        self.module = module
        self.additional_info = additional_info or {}
        self.timestamp = time.time()


class XHSError(Exception):
    """小红书下载器基础异常"""
    def __init__(self, message: str, error_code: str = None, 
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM, 
                 context: ErrorContext = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.context = context
        self.timestamp = time.time()


class NetworkError(XHSError):
    """网络相关错误"""
    def __init__(self, message: str, status_code: int = None, **kwargs):
        super().__init__(message, error_code="NETWORK_ERROR", 
                        severity=ErrorSeverity.HIGH, **kwargs)
        self.status_code = status_code


class FileOperationError(XHSError):
    """文件操作错误"""
    def __init__(self, message: str, file_path: str = None, **kwargs):
        super().__init__(message, error_code="FILE_ERROR", 
                        severity=ErrorSeverity.MEDIUM, **kwargs)
        self.file_path = file_path


class BrowserError(XHSError):
    """浏览器操作错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_code="BROWSER_ERROR", 
                        severity=ErrorSeverity.HIGH, **kwargs)


class DataValidationError(XHSError):
    """数据验证错误"""
    def __init__(self, message: str, data_field: str = None, **kwargs):
        super().__init__(message, error_code="VALIDATION_ERROR", 
                        severity=ErrorSeverity.MEDIUM, **kwargs)
        self.data_field = data_field


class ConfigurationError(XHSError):
    """配置错误"""
    def __init__(self, message: str, config_key: str = None, **kwargs):
        super().__init__(message, error_code="CONFIG_ERROR", 
                        severity=ErrorSeverity.HIGH, **kwargs)
        self.config_key = config_key


class ErrorHandler:
    """统一错误处理器"""
    
    def __init__(self, logger: logging.Logger = None):
        self.logger = logger or self._setup_logger()
        self.error_stats = {
            "total_errors": 0,
            "by_severity": {severity.value: 0 for severity in ErrorSeverity},
            "by_module": {},
            "recent_errors": []
        }
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger("xhs_error_handler")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def handle_error(self, error: Exception, context: ErrorContext = None) -> None:
        """处理错误并记录"""
        if isinstance(error, XHSError):
            severity = error.severity
            error_code = error.error_code
            context = context or error.context
        else:
            severity = ErrorSeverity.MEDIUM
            error_code = type(error).__name__
        
        # 更新统计信息
        self._update_error_stats(error, severity, context)
        
        # 记录错误日志
        self._log_error(error, severity, error_code, context)
        
        # 根据严重性决定处理方式
        if severity == ErrorSeverity.CRITICAL:
            self._handle_critical_error(error, context)
        elif severity == ErrorSeverity.HIGH:
            self._handle_high_severity_error(error, context)
    
    def _update_error_stats(self, error: Exception, severity: ErrorSeverity, 
                           context: ErrorContext = None):
        """更新错误统计"""
        self.error_stats["total_errors"] += 1
        self.error_stats["by_severity"][severity.value] += 1
        
        if context:
            module = context.module
            if module not in self.error_stats["by_module"]:
                self.error_stats["by_module"][module] = 0
            self.error_stats["by_module"][module] += 1
        
        # 保留最近50个错误
        self.error_stats["recent_errors"].append({
            "timestamp": time.time(),
            "error_type": type(error).__name__,
            "message": str(error),
            "severity": severity.value,
            "module": context.module if context else "unknown"
        })
        if len(self.error_stats["recent_errors"]) > 50:
            self.error_stats["recent_errors"].pop(0)
    
    def _log_error(self, error: Exception, severity: ErrorSeverity, 
                   error_code: str, context: ErrorContext = None):
        """记录错误日志"""
        log_message = f"[{severity.value.upper()}] {error_code}: {str(error)}"
        
        if context:
            log_message += f" | Module: {context.module} | Operation: {context.operation}"
            if context.additional_info:
                log_message += f" | Info: {context.additional_info}"
        
        if severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
            self.logger.error(log_message)
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def _handle_critical_error(self, error: Exception, context: ErrorContext = None):
        """处理致命错误"""
        self.logger.critical(f"CRITICAL ERROR DETECTED: {str(error)}")
        # 在实际应用中，这里可能需要发送告警、保存状态等
    
    def _handle_high_severity_error(self, error: Exception, context: ErrorContext = None):
        """处理高严重性错误"""
        self.logger.error(f"HIGH SEVERITY ERROR: {str(error)}")
        # 可以添加额外的处理逻辑，如重试、降级等


def with_error_handling(context: ErrorContext = None, 
                       retry_config: RetryConfig = None,
                       fallback_value: Any = None,
                       error_handler: ErrorHandler = None):
    """错误处理装饰器"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            handler = error_handler or ErrorHandler()
            
            if retry_config:
                return _execute_with_retry(
                    func, args, kwargs, retry_config, handler, context, fallback_value
                )
            else:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    handler.handle_error(e, context)
                    if fallback_value is not None:
                        return fallback_value
                    raise
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            handler = error_handler or ErrorHandler()
            
            if retry_config:
                return await _execute_with_retry_async(
                    func, args, kwargs, retry_config, handler, context, fallback_value
                )
            else:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    handler.handle_error(e, context)
                    if fallback_value is not None:
                        return fallback_value
                    raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def _execute_with_retry(func: Callable, args: tuple, kwargs: dict, 
                       retry_config: RetryConfig, handler: ErrorHandler,
                       context: ErrorContext = None, fallback_value: Any = None):
    """执行带重试的同步函数"""
    last_exception = None
    
    for attempt in range(retry_config.max_attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            handler.handle_error(e, context)
            
            if attempt < retry_config.max_attempts - 1:
                delay = min(
                    retry_config.base_delay * (retry_config.exponential_base ** attempt),
                    retry_config.max_delay
                )
                time.sleep(delay)
            else:
                break
    
    if fallback_value is not None:
        return fallback_value
    raise last_exception


async def _execute_with_retry_async(func: Callable, args: tuple, kwargs: dict, 
                                   retry_config: RetryConfig, handler: ErrorHandler,
                                   context: ErrorContext = None, fallback_value: Any = None):
    """执行带重试的异步函数"""
    last_exception = None
    
    for attempt in range(retry_config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            handler.handle_error(e, context)
            
            if attempt < retry_config.max_attempts - 1:
                delay = min(
                    retry_config.base_delay * (retry_config.exponential_base ** attempt),
                    retry_config.max_delay
                )
                await asyncio.sleep(delay)
            else:
                break
    
    if fallback_value is not None:
        return fallback_value
    raise last_exception


def safe_file_operation(operation: str, default_return=None):
    """安全文件操作装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except FileNotFoundError as e:
                raise FileOperationError(
                    f"文件未找到: {str(e)}", 
                    context=ErrorContext(operation, "file_system")
                )
            except PermissionError as e:
                raise FileOperationError(
                    f"文件权限错误: {str(e)}", 
                    context=ErrorContext(operation, "file_system")
                )
            except OSError as e:
                raise FileOperationError(
                    f"文件系统错误: {str(e)}", 
                    context=ErrorContext(operation, "file_system")
                )
            except Exception as e:
                if default_return is not None:
                    return default_return
                raise
        return wrapper
    return decorator


def validate_data(validation_rules: Dict[str, Callable]):
    """数据验证装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 验证输入参数
            for param_name, validator in validation_rules.items():
                if param_name in kwargs:
                    value = kwargs[param_name]
                    if not validator(value):
                        raise DataValidationError(
                            f"参数 {param_name} 验证失败: {value}",
                            data_field=param_name
                        )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


# 全局错误处理器实例
global_error_handler = ErrorHandler()