#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全文件操作工具模块
提供原子文件操作、文件锁、并发安全等功能
"""

import json
import time
import fcntl
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Union, Callable
from contextlib import contextmanager
import hashlib
import shutil


class FileLockManager:
    """文件锁管理器"""
    
    def __init__(self):
        self._locks = {}
        self._thread_lock = threading.RLock()
    
    @contextmanager
    def acquire_lock(self, file_path: Union[str, Path], timeout: float = 30.0):
        """获取文件锁"""
        file_path = str(file_path)
        
        with self._thread_lock:
            if file_path not in self._locks:
                self._locks[file_path] = threading.RLock()
            file_lock = self._locks[file_path]
        
        acquired = file_lock.acquire(timeout=timeout)
        if not acquired:
            raise TimeoutError(f"无法在 {timeout} 秒内获取文件锁: {file_path}")
        
        try:
            yield
        finally:
            file_lock.release()


class AtomicFileWriter:
    """原子文件写入器"""
    
    def __init__(self, target_path: Union[str, Path], encoding: str = 'utf-8'):
        self.target_path = Path(target_path)
        self.encoding = encoding
        self.temp_path = None
        self.temp_file = None
    
    def __enter__(self):
        # 创建临时文件
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 在同一目录下创建临时文件
        self.temp_path = self.target_path.with_suffix(
            self.target_path.suffix + f'.tmp.{int(time.time())}'
        )
        
        self.temp_file = open(self.temp_path, 'w', encoding=self.encoding)
        return self.temp_file
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.temp_file:
                self.temp_file.close()
            
            if exc_type is None:
                # 没有异常，原子性移动文件
                shutil.move(str(self.temp_path), str(self.target_path))
            else:
                # 有异常，清理临时文件
                if self.temp_path and self.temp_path.exists():
                    self.temp_path.unlink()
        except Exception as e:
            # 确保临时文件被清理
            if self.temp_path and self.temp_path.exists():
                try:
                    self.temp_path.unlink()
                except:
                    pass
            raise e


class SafeFileOperations:
    """安全文件操作类"""
    
    def __init__(self):
        self.lock_manager = FileLockManager()
    
    def read_json_safe(self, file_path: Union[str, Path], 
                      default_value: Any = None, 
                      lock_timeout: float = 30.0) -> Any:
        """安全读取JSON文件"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return default_value
        
        with self.lock_manager.acquire_lock(file_path, lock_timeout):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                if default_value is not None:
                    return default_value
                raise ValueError(f"JSON文件格式错误: {file_path}, 错误: {e}")
            except Exception as e:
                if default_value is not None:
                    return default_value
                raise
    
    def write_json_safe(self, file_path: Union[str, Path], data: Any, 
                       lock_timeout: float = 30.0, 
                       backup: bool = True) -> bool:
        """安全写入JSON文件"""
        file_path = Path(file_path)
        
        with self.lock_manager.acquire_lock(file_path, lock_timeout):
            try:
                # 创建备份
                if backup and file_path.exists():
                    backup_path = file_path.with_suffix(file_path.suffix + '.backup')
                    shutil.copy2(file_path, backup_path)
                
                # 原子写入
                with AtomicFileWriter(file_path) as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                return True
                
            except Exception as e:
                # 如果写入失败且有备份，尝试恢复
                if backup:
                    backup_path = file_path.with_suffix(file_path.suffix + '.backup')
                    if backup_path.exists():
                        try:
                            shutil.copy2(backup_path, file_path)
                        except:
                            pass
                raise e
    
    def read_text_safe(self, file_path: Union[str, Path], 
                      encoding: str = 'utf-8',
                      default_value: str = None,
                      lock_timeout: float = 30.0) -> str:
        """安全读取文本文件"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            return default_value
        
        with self.lock_manager.acquire_lock(file_path, lock_timeout):
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError as e:
                if default_value is not None:
                    return default_value
                raise ValueError(f"文件编码错误: {file_path}, 错误: {e}")
            except Exception as e:
                if default_value is not None:
                    return default_value
                raise
    
    def write_text_safe(self, file_path: Union[str, Path], content: str,
                       encoding: str = 'utf-8',
                       lock_timeout: float = 30.0,
                       backup: bool = True) -> bool:
        """安全写入文本文件"""
        file_path = Path(file_path)
        
        with self.lock_manager.acquire_lock(file_path, lock_timeout):
            try:
                # 创建备份
                if backup and file_path.exists():
                    backup_path = file_path.with_suffix(file_path.suffix + '.backup')
                    shutil.copy2(file_path, backup_path)
                
                # 原子写入
                with AtomicFileWriter(file_path, encoding) as f:
                    f.write(content)
                
                return True
                
            except Exception as e:
                # 如果写入失败且有备份，尝试恢复
                if backup:
                    backup_path = file_path.with_suffix(file_path.suffix + '.backup')
                    if backup_path.exists():
                        try:
                            shutil.copy2(backup_path, file_path)
                        except:
                            pass
                raise e
    
    def update_json_field(self, file_path: Union[str, Path], 
                         field_path: str, value: Any,
                         lock_timeout: float = 30.0,
                         create_if_missing: bool = True) -> bool:
        """安全更新JSON文件中的特定字段"""
        file_path = Path(file_path)
        
        with self.lock_manager.acquire_lock(file_path, lock_timeout):
            try:
                # 读取现有数据
                if file_path.exists():
                    data = self.read_json_safe(file_path, {}, 0.1)
                elif create_if_missing:
                    data = {}
                else:
                    return False
                
                # 更新字段
                current = data
                keys = field_path.split('.')
                
                # 导航到目标位置
                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # 设置值
                current[keys[-1]] = value
                
                # 写回文件
                return self.write_json_safe(file_path, data, 0.1, backup=True)
                
            except Exception as e:
                raise ValueError(f"更新JSON字段失败: {field_path}, 错误: {e}")
    
    def copy_file_safe(self, source: Union[str, Path], 
                      destination: Union[str, Path],
                      verify_checksum: bool = True) -> bool:
        """安全文件复制"""
        source = Path(source)
        destination = Path(destination)
        
        if not source.exists():
            raise FileNotFoundError(f"源文件不存在: {source}")
        
        # 确保目标目录存在
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # 计算源文件校验和
        if verify_checksum:
            source_checksum = self._calculate_file_checksum(source)
        
        with self.lock_manager.acquire_lock(destination):
            try:
                # 使用临时文件进行复制
                temp_path = destination.with_suffix(
                    destination.suffix + f'.tmp.{int(time.time())}'
                )
                
                shutil.copy2(source, temp_path)
                
                # 验证校验和
                if verify_checksum:
                    temp_checksum = self._calculate_file_checksum(temp_path)
                    if source_checksum != temp_checksum:
                        temp_path.unlink()
                        raise ValueError("文件复制校验失败，校验和不匹配")
                
                # 原子性移动
                shutil.move(str(temp_path), str(destination))
                return True
                
            except Exception as e:
                # 清理临时文件
                if 'temp_path' in locals() and temp_path.exists():
                    temp_path.unlink()
                raise e
    
    def _calculate_file_checksum(self, file_path: Path, algorithm: str = 'md5') -> str:
        """计算文件校验和"""
        hash_func = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_func.update(chunk)
        
        return hash_func.hexdigest()
    
    def cleanup_temp_files(self, directory: Union[str, Path], 
                          age_hours: float = 24) -> int:
        """清理临时文件"""
        directory = Path(directory)
        current_time = time.time()
        cleanup_count = 0
        
        if not directory.exists():
            return 0
        
        for file_path in directory.glob("*.tmp.*"):
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > age_hours * 3600:  # 转换为秒
                    file_path.unlink()
                    cleanup_count += 1
            except Exception:
                # 忽略清理过程中的错误
                continue
        
        return cleanup_count
    
    def ensure_directory_exists(self, directory: Union[str, Path], 
                               mode: int = 0o755) -> bool:
        """确保目录存在"""
        directory = Path(directory)
        try:
            directory.mkdir(parents=True, exist_ok=True, mode=mode)
            return True
        except Exception:
            return False


# 全局安全文件操作实例
safe_file_ops = SafeFileOperations()


# 便捷函数
def read_json_safe(file_path: Union[str, Path], default_value: Any = None) -> Any:
    """便捷的安全JSON读取"""
    return safe_file_ops.read_json_safe(file_path, default_value)


def write_json_safe(file_path: Union[str, Path], data: Any, backup: bool = True) -> bool:
    """便捷的安全JSON写入"""
    return safe_file_ops.write_json_safe(file_path, data, backup=backup)


def update_json_field(file_path: Union[str, Path], field_path: str, value: Any) -> bool:
    """便捷的JSON字段更新"""
    return safe_file_ops.update_json_field(file_path, field_path, value)