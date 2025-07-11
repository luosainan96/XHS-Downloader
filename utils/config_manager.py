#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
统一管理应用配置、环境变量和设置
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Type
from dataclasses import dataclass, field
from enum import Enum

from utils.file_operations import safe_file_ops
from utils.error_handler import ConfigurationError, ErrorContext


class ConfigSection(Enum):
    """配置段落"""
    BROWSER = "browser"
    NETWORK = "network"
    RETRY = "retry"
    STORAGE = "storage"
    AI = "ai"
    UI = "ui"
    LOGGING = "logging"
    PERFORMANCE = "performance"


@dataclass
class BrowserConfig:
    """浏览器配置"""
    headless: bool = True
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    viewport_width: int = 1280
    viewport_height: int = 720
    timeout: int = 30000
    wait_timeout: int = 10000
    scroll_delay: int = 2000
    profile_path: str = "Comments_Dynamic/browser_profile"


@dataclass
class NetworkConfig:
    """网络配置"""
    request_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    max_concurrent_requests: int = 5
    rate_limit_delay: float = 0.5
    user_agent_rotation: bool = True
    proxy_enabled: bool = False
    proxy_url: Optional[str] = None


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    retry_on_network_error: bool = True
    retry_on_browser_error: bool = True
    retry_on_file_error: bool = False


@dataclass
class StorageConfig:
    """存储配置"""
    base_path: str = "Comments_Dynamic"
    backup_enabled: bool = True
    backup_retention_days: int = 30
    auto_cleanup_temp_files: bool = True
    temp_file_age_hours: int = 24
    max_file_size_mb: int = 100
    compression_enabled: bool = False


@dataclass
class AIConfig:
    """AI配置"""
    enabled: bool = True
    default_model: str = "mock"
    max_tokens: int = 2048
    temperature: float = 0.7
    request_timeout: int = 60
    daily_budget: float = 10.0
    cost_tracking_enabled: bool = True
    batch_size: int = 10


@dataclass
class UIConfig:
    """UI配置"""
    page_title: str = "小红书评论提取器"
    sidebar_width: int = 300
    auto_refresh: bool = False
    refresh_interval: int = 30
    max_display_items: int = 100
    show_debug_info: bool = False
    theme: str = "light"


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    file_enabled: bool = True
    console_enabled: bool = True
    max_file_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_dir: str = "logs"


@dataclass
class PerformanceConfig:
    """性能配置"""
    cache_enabled: bool = True
    cache_size: int = 1000
    cache_ttl_seconds: int = 3600
    connection_pool_size: int = 10
    max_workers: int = 4
    memory_limit_mb: int = 512
    gc_threshold: int = 1000


@dataclass
class ApplicationConfig:
    """应用主配置"""
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Union[str, Path] = "config.json"):
        self.config_path = Path(config_path)
        self.config = ApplicationConfig()
        self._env_prefix = "XHS_"
        
        # 加载配置
        self.load_config()
        self.load_environment_variables()
    
    def load_config(self) -> None:
        """从文件加载配置"""
        try:
            if self.config_path.exists():
                config_data = safe_file_ops.read_json_safe(self.config_path, {})
                self._update_config_from_dict(config_data)
            else:
                # 创建默认配置文件
                self.save_config()
        except Exception as e:
            raise ConfigurationError(
                f"加载配置文件失败: {e}",
                config_key=str(self.config_path),
                context=ErrorContext("load_config", "config_manager")
            )
    
    def save_config(self) -> bool:
        """保存配置到文件"""
        try:
            config_dict = self._config_to_dict()
            return safe_file_ops.write_json_safe(self.config_path, config_dict)
        except Exception as e:
            raise ConfigurationError(
                f"保存配置文件失败: {e}",
                config_key=str(self.config_path),
                context=ErrorContext("save_config", "config_manager")
            )
    
    def load_environment_variables(self) -> None:
        """从环境变量加载配置"""
        env_mappings = {
            f"{self._env_prefix}BROWSER_HEADLESS": ("browser.headless", bool),
            f"{self._env_prefix}BROWSER_TIMEOUT": ("browser.timeout", int),
            f"{self._env_prefix}NETWORK_TIMEOUT": ("network.request_timeout", int),
            f"{self._env_prefix}NETWORK_MAX_RETRIES": ("network.max_retries", int),
            f"{self._env_prefix}AI_MODEL": ("ai.default_model", str),
            f"{self._env_prefix}AI_BUDGET": ("ai.daily_budget", float),
            f"{self._env_prefix}STORAGE_PATH": ("storage.base_path", str),
            f"{self._env_prefix}LOG_LEVEL": ("logging.level", str),
            f"{self._env_prefix}LOG_ENABLED": ("logging.file_enabled", bool),
            f"{self._env_prefix}CACHE_ENABLED": ("performance.cache_enabled", bool),
            f"{self._env_prefix}MAX_WORKERS": ("performance.max_workers", int),
        }
        
        for env_var, (config_path, config_type) in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    # 类型转换
                    if config_type == bool:
                        value = env_value.lower() in ('true', '1', 'yes', 'on')
                    elif config_type == int:
                        value = int(env_value)
                    elif config_type == float:
                        value = float(env_value)
                    else:
                        value = env_value
                    
                    # 设置配置值
                    self.set_config(config_path, value)
                except Exception as e:
                    print(f"警告: 环境变量 {env_var} 值无效: {env_value}, 错误: {e}")
    
    def get_config(self, path: str, default: Any = None) -> Any:
        """获取配置值"""
        try:
            keys = path.split('.')
            current = self.config
            
            for key in keys:
                if hasattr(current, key):
                    current = getattr(current, key)
                else:
                    return default
            
            return current
        except Exception:
            return default
    
    def set_config(self, path: str, value: Any) -> bool:
        """设置配置值"""
        try:
            keys = path.split('.')
            current = self.config
            
            # 导航到目标位置
            for key in keys[:-1]:
                if hasattr(current, key):
                    current = getattr(current, key)
                else:
                    return False
            
            # 设置值
            if hasattr(current, keys[-1]):
                setattr(current, keys[-1], value)
                return True
            
            return False
        except Exception:
            return False
    
    def _config_to_dict(self) -> Dict:
        """将配置对象转换为字典"""
        def dataclass_to_dict(obj):
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    if hasattr(value, '__dict__'):
                        result[key] = dataclass_to_dict(value)
                    else:
                        result[key] = value
                return result
            return obj
        
        return dataclass_to_dict(self.config)
    
    def _update_config_from_dict(self, config_dict: Dict) -> None:
        """从字典更新配置"""
        def update_dataclass(obj, data):
            for key, value in data.items():
                if hasattr(obj, key):
                    attr = getattr(obj, key)
                    if hasattr(attr, '__dict__') and isinstance(value, dict):
                        update_dataclass(attr, value)
                    else:
                        setattr(obj, key, value)
        
        update_dataclass(self.config, config_dict)
    
    def validate_config(self) -> List[str]:
        """验证配置"""
        errors = []
        
        # 验证浏览器配置
        if self.config.browser.timeout <= 0:
            errors.append("browser.timeout 必须大于0")
        
        if self.config.browser.viewport_width <= 0 or self.config.browser.viewport_height <= 0:
            errors.append("browser viewport 尺寸必须大于0")
        
        # 验证网络配置
        if self.config.network.request_timeout <= 0:
            errors.append("network.request_timeout 必须大于0")
        
        if self.config.network.max_retries < 0:
            errors.append("network.max_retries 不能小于0")
        
        # 验证存储配置
        if not self.config.storage.base_path:
            errors.append("storage.base_path 不能为空")
        
        # 验证AI配置
        if self.config.ai.daily_budget < 0:
            errors.append("ai.daily_budget 不能小于0")
        
        # 验证性能配置
        if self.config.performance.max_workers <= 0:
            errors.append("performance.max_workers 必须大于0")
        
        return errors
    
    def get_section(self, section: ConfigSection) -> Any:
        """获取配置段落"""
        return getattr(self.config, section.value)
    
    def update_section(self, section: ConfigSection, **kwargs) -> bool:
        """更新配置段落"""
        try:
            section_obj = getattr(self.config, section.value)
            for key, value in kwargs.items():
                if hasattr(section_obj, key):
                    setattr(section_obj, key, value)
            return True
        except Exception:
            return False
    
    def reset_to_defaults(self) -> None:
        """重置为默认配置"""
        self.config = ApplicationConfig()
    
    def export_config(self, export_path: Union[str, Path]) -> bool:
        """导出配置"""
        try:
            config_dict = self._config_to_dict()
            return safe_file_ops.write_json_safe(export_path, config_dict)
        except Exception:
            return False
    
    def import_config(self, import_path: Union[str, Path]) -> bool:
        """导入配置"""
        try:
            config_data = safe_file_ops.read_json_safe(import_path)
            if config_data:
                self._update_config_from_dict(config_data)
                return True
            return False
        except Exception:
            return False


# 全局配置管理器实例
config_manager = ConfigManager()


# 便捷函数
def get_config(path: str, default: Any = None) -> Any:
    """获取配置值"""
    return config_manager.get_config(path, default)


def set_config(path: str, value: Any) -> bool:
    """设置配置值"""
    return config_manager.set_config(path, value)


def get_browser_config() -> BrowserConfig:
    """获取浏览器配置"""
    return config_manager.config.browser


def get_network_config() -> NetworkConfig:
    """获取网络配置"""
    return config_manager.config.network


def get_ai_config() -> AIConfig:
    """获取AI配置"""
    return config_manager.config.ai


def get_storage_config() -> StorageConfig:
    """获取存储配置"""
    return config_manager.config.storage