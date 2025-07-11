#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评论状态管理器
管理评论的回复状态：已完成、观察中、待处理
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import hashlib
import secrets

try:
    from utils.error_handler import (
        with_error_handling, ErrorContext, FileOperationError, 
        DataValidationError, RetryConfig
    )
    from utils.file_operations import safe_file_ops
    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False
    # 降级处理
    def with_error_handling(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    class ErrorContext:
        def __init__(self, *args, **kwargs):
            pass
    
    class FileOperationError(Exception):
        pass
    
    class DataValidationError(Exception):
        pass
    
    class RetryConfig:
        def __init__(self, *args, **kwargs):
            pass
    
    class MockSafeFileOps:
        def read_json_safe(self, path, default=None):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default
        
        def write_json_safe(self, path, data, backup=True):
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
            except:
                return False
    
    safe_file_ops = MockSafeFileOps()


class CommentStatus(Enum):
    """评论回复状态"""
    PENDING = "待处理"      # 待处理 - 新评论，尚未回复
    WATCHING = "观察中"     # 观察中 - 已关注但暂不回复
    COMPLETED = "已完成"    # 已完成 - 已回复完成


@dataclass
class CommentStatusRecord:
    """评论状态记录"""
    comment_id: str
    user_nickname: str
    work_title: str
    comment_content: str
    status: CommentStatus
    created_at: datetime
    updated_at: datetime
    notes: str = ""
    operator: str = ""
    reply_content: str = ""
    xiaohongshu_url: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class CommentStatusManager:
    """评论状态管理器"""
    
    def __init__(self, work_path: str = "Comments_Dynamic"):
        self.work_path = Path(work_path)
        self.status_path = self.work_path / "comment_status"
        self.status_path.mkdir(parents=True, exist_ok=True)
        
        # 状态文件
        self.status_file = self.status_path / "comment_status.json"
        self.history_file = self.status_path / "status_history.json"
        
        # 加载现有状态
        self.status_records = self.load_status_records()
    
    def generate_comment_id(self, user_nickname: str, work_title: str, content: str) -> str:
        """生成评论唯一ID"""
        # 使用更安全的ID生成方式，避免碰撞
        timestamp = str(int(time.time() * 1000))  # 毫秒时间戳
        random_part = secrets.token_hex(4)  # 8位随机字符
        unique_str = f"{user_nickname}_{work_title}_{content[:50]}_{timestamp}_{random_part}"
        return hashlib.sha256(unique_str.encode()).hexdigest()[:16]
    
    @with_error_handling(
        context=ErrorContext("load_status_records", "comment_status_manager"),
        fallback_value={}
    )
    def load_status_records(self) -> Dict[str, CommentStatusRecord]:
        """加载状态记录"""
        data = safe_file_ops.read_json_safe(self.status_file, {})
        
        records = {}
        for comment_id, record_data in data.items():
            try:
                records[comment_id] = CommentStatusRecord(
                    comment_id=record_data['comment_id'],
                    user_nickname=record_data['user_nickname'],
                    work_title=record_data['work_title'],
                    comment_content=record_data['comment_content'],
                    status=CommentStatus(record_data['status']),
                    created_at=datetime.fromisoformat(record_data['created_at']),
                    updated_at=datetime.fromisoformat(record_data['updated_at']),
                    notes=record_data.get('notes', ''),
                    operator=record_data.get('operator', ''),
                    reply_content=record_data.get('reply_content', ''),
                    xiaohongshu_url=record_data.get('xiaohongshu_url', ''),
                    metadata=record_data.get('metadata', {})
                )
            except (ValueError, KeyError) as e:
                raise DataValidationError(
                    f"评论状态记录格式错误: {comment_id}", 
                    data_field=comment_id
                )
        
        return records
    
    @with_error_handling(
        context=ErrorContext("save_status_records", "comment_status_manager")
    )
    def save_status_records(self) -> bool:
        """保存状态记录"""
        data = {}
        for comment_id, record in self.status_records.items():
            data[comment_id] = {
                'comment_id': record.comment_id,
                'user_nickname': record.user_nickname,
                'work_title': record.work_title,
                'comment_content': record.comment_content,
                'status': record.status.value,
                'created_at': record.created_at.isoformat(),
                'updated_at': record.updated_at.isoformat(),
                'notes': record.notes,
                'operator': record.operator,
                'reply_content': record.reply_content,
                'xiaohongshu_url': record.xiaohongshu_url,
                'metadata': record.metadata
            }
        
        return safe_file_ops.write_json_safe(self.status_file, data)
    
    def add_or_update_comment_status(self, user_nickname: str, work_title: str, 
                                   comment_content: str, status: CommentStatus = CommentStatus.PENDING,
                                   notes: str = "", operator: str = "", reply_content: str = "",
                                   xiaohongshu_url: str = "") -> str:
        """添加或更新评论状态"""
        
        # 生成或查找评论ID
        comment_id = self.generate_comment_id(user_nickname, work_title, comment_content)
        
        # 检查是否已存在
        if comment_id in self.status_records:
            # 更新现有记录
            record = self.status_records[comment_id]
            old_status = record.status
            record.status = status
            record.updated_at = datetime.now()
            record.notes = notes
            record.operator = operator
            record.reply_content = reply_content
            record.xiaohongshu_url = xiaohongshu_url
            
            # 记录状态变更历史
            if old_status != status:
                self.log_status_change(comment_id, old_status, status, operator)
        else:
            # 创建新记录
            record = CommentStatusRecord(
                comment_id=comment_id,
                user_nickname=user_nickname,
                work_title=work_title,
                comment_content=comment_content,
                status=status,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                notes=notes,
                operator=operator,
                reply_content=reply_content,
                xiaohongshu_url=xiaohongshu_url
            )
            
            self.status_records[comment_id] = record
            
            # 记录新增历史
            self.log_status_change(comment_id, None, status, operator)
        
        # 保存到文件
        self.save_status_records()
        
        return comment_id
    
    @with_error_handling(
        context=ErrorContext("log_status_change", "comment_status_manager")
    )
    def log_status_change(self, comment_id: str, old_status: CommentStatus, 
                         new_status: CommentStatus, operator: str) -> bool:
        """记录状态变更历史"""
        history_entry = {
            'comment_id': comment_id,
            'old_status': old_status.value if old_status else None,
            'new_status': new_status.value,
            'operator': operator,
            'timestamp': datetime.now().isoformat()
        }
        
        # 加载现有历史
        history = safe_file_ops.read_json_safe(self.history_file, [])
        
        # 添加新记录
        history.append(history_entry)
        
        # 保持最近1000条记录
        if len(history) > 1000:
            history = history[-1000:]
        
        # 保存历史
        return safe_file_ops.write_json_safe(self.history_file, history)
    
    def get_comment_status(self, comment_id: str) -> Optional[CommentStatusRecord]:
        """获取评论状态"""
        return self.status_records.get(comment_id)
    
    def find_comment_by_content(self, user_nickname: str, content_snippet: str) -> List[CommentStatusRecord]:
        """根据用户昵称和内容片段查找评论"""
        results = []
        for record in self.status_records.values():
            if (user_nickname.lower() in record.user_nickname.lower() and 
                content_snippet.lower() in record.comment_content.lower()):
                results.append(record)
        return results
    
    def get_comments_by_status(self, status: CommentStatus) -> List[CommentStatusRecord]:
        """根据状态获取评论列表"""
        return [record for record in self.status_records.values() if record.status == status]
    
    def get_comments_by_work(self, work_title: str) -> List[CommentStatusRecord]:
        """根据作品获取评论列表"""
        return [record for record in self.status_records.values() if work_title in record.work_title]
    
    def search_comments(self, keyword: str = "", status: CommentStatus = None,
                       work_title: str = "", user_nickname: str = "",
                       limit: int = 100) -> List[CommentStatusRecord]:
        """搜索评论"""
        results = []
        
        for record in self.status_records.values():
            # 关键词过滤
            if keyword and keyword.lower() not in record.comment_content.lower():
                continue
            
            # 状态过滤
            if status and record.status != status:
                continue
            
            # 作品过滤
            if work_title and work_title.lower() not in record.work_title.lower():
                continue
            
            # 用户过滤
            if user_nickname and user_nickname.lower() not in record.user_nickname.lower():
                continue
            
            results.append(record)
        
        # 按更新时间排序
        results.sort(key=lambda x: x.updated_at, reverse=True)
        
        return results[:limit]
    
    def get_statistics(self, work_dir: str = None) -> Dict[str, Any]:
        """获取统计信息 - 修复版"""
        if work_dir:
            # 基于特定作品的统计
            return self._get_work_based_statistics(work_dir)
        else:
            # 全局统计（保留原有逻辑用于兼容）
            return self._get_global_statistics()
    
    def _get_global_statistics(self) -> Dict[str, Any]:
        """获取全局统计信息 - 修复版"""
        from local_comment_loader import LocalCommentLoader
        
        try:
            # 加载所有实际评论数据
            loader = LocalCommentLoader(self.work_path)
            works = loader.scan_available_works()
            
            total_actual_comments = 0
            all_actual_users = set()
            
            # 统计所有作品的实际评论数据
            for work in works:
                try:
                    work_comments = loader.load_comments_from_work(work['work_dir'])
                    total_actual_comments += len(work_comments)
                    
                    for comment in work_comments:
                        all_actual_users.add(comment.get('nickname', ''))
                except:
                    continue
            
            # 对状态记录进行去重处理
            # 为每个用户在每个作品下只保留最新的状态记录
            user_work_latest_records = {}
            for record in self.status_records.values():
                key = f"{record.user_nickname}_{record.work_title}"
                if key not in user_work_latest_records or record.updated_at > user_work_latest_records[key].updated_at:
                    user_work_latest_records[key] = record
            
            # 基于去重后的记录进行统计，但只统计实际存在的用户
            status_counts = {status.value: 0 for status in CommentStatus}
            marked_users = set()
            unique_works = set()
            
            for record in user_work_latest_records.values():
                # 只统计实际存在的用户
                if record.user_nickname in all_actual_users:
                    status_counts[record.status.value] += 1
                    marked_users.add(record.user_nickname)
                unique_works.add(record.work_title)
            
            # 计算未标记用户（默认为待处理）
            unmarked_users = all_actual_users - marked_users
            total_marked_comments = sum(status_counts.values())
            
            # 正确计算待处理数量：手动标记的待处理 + 未标记的用户
            actual_pending = status_counts[CommentStatus.PENDING.value] + len(unmarked_users)
            status_counts[CommentStatus.PENDING.value] = actual_pending
            
            # 计算完成率
            completion_rate = (status_counts[CommentStatus.COMPLETED.value] / total_actual_comments * 100) if total_actual_comments > 0 else 0
            
            # 最近活动（基于去重后的记录）
            recent_activities = sorted(
                user_work_latest_records.values(),
                key=lambda x: x.updated_at,
                reverse=True
            )[:10]
            
            return {
                'total_comments': total_actual_comments,
                'unique_users': len(all_actual_users),
                'unique_works': len(unique_works),
                'pending_count': actual_pending,
                'watching_count': status_counts[CommentStatus.WATCHING.value], 
                'completed_count': status_counts[CommentStatus.COMPLETED.value],
                'status_distribution': status_counts,
                'completion_rate': completion_rate,
                'marked_comments': total_marked_comments,
                'unmarked_comments': len(unmarked_users),
                'recent_activities': [
                    {
                        'user_nickname': record.user_nickname,
                        'work_title': record.work_title,
                        'status': record.status.value,
                        'updated_at': record.updated_at.isoformat()
                    }
                    for record in recent_activities
                ]
            }
            
        except Exception as e:
            print(f"获取全局统计信息失败: {e}")
            # 如果获取失败，返回基本的去重统计
            user_work_latest_records = {}
            for record in self.status_records.values():
                key = f"{record.user_nickname}_{record.work_title}"
                if key not in user_work_latest_records or record.updated_at > user_work_latest_records[key].updated_at:
                    user_work_latest_records[key] = record
            
            total_comments = len(user_work_latest_records)
            status_counts = {status.value: 0 for status in CommentStatus}
            unique_users = set()
            unique_works = set()
            
            for record in user_work_latest_records.values():
                status_counts[record.status.value] += 1
                unique_users.add(record.user_nickname)
                unique_works.add(record.work_title)
            
            return {
                'total_comments': total_comments,
                'unique_users': len(unique_users),
                'unique_works': len(unique_works),
                'pending_count': status_counts[CommentStatus.PENDING.value],
                'watching_count': status_counts[CommentStatus.WATCHING.value], 
                'completed_count': status_counts[CommentStatus.COMPLETED.value],
                'status_distribution': status_counts,
                'completion_rate': (status_counts[CommentStatus.COMPLETED.value] / total_comments * 100) if total_comments > 0 else 0,
                'marked_comments': total_comments,
                'unmarked_comments': 0,
                'recent_activities': []
            }
    
    def _get_work_based_statistics(self, work_dir: str) -> Dict[str, Any]:
        """基于特定作品的统计信息"""
        from local_comment_loader import LocalCommentLoader
        
        try:
            # 加载实际的评论数据
            loader = LocalCommentLoader(self.work_path)
            actual_comments = loader.load_comments_from_work(work_dir)
            
            # 获取作品信息
            work_info_file = Path(work_dir) / "作品信息.json"
            work_title = "未知作品"
            if work_info_file.exists():
                try:
                    with open(work_info_file, 'r', encoding='utf-8') as f:
                        work_info = json.load(f)
                        work_title = work_info.get('作品标题', '未知作品')
                except:
                    pass
            
            # 统计实际评论数据
            total_actual_comments = len(actual_comments)
            unique_users = set()
            
            for comment in actual_comments:
                unique_users.add(comment.get('nickname', ''))
            
            # 统计已标记状态的评论 - 修复作品匹配逻辑
            status_counts = {status.value: 0 for status in CommentStatus}
            marked_users = set()
            
            # 生成可能的作品标题变体用于匹配
            work_title_variants = {
                work_title,
                work_title.replace('！', '!'),  # 处理中英文标点
                work_title.replace('～', '~'),
                work_title.replace('，', ','),
                work_title.replace('。', '.'),
            }
            
            # 首先尝试精确匹配
            exact_matches = []
            for record in self.status_records.values():
                record_work_title = record.work_title
                if record_work_title in work_title_variants:
                    exact_matches.append(record)
            
            if exact_matches:
                # 如果有精确匹配，只使用精确匹配的记录，并去重
                # 为每个用户只保留最新的状态记录
                user_latest_records = {}
                for record in exact_matches:
                    user = record.user_nickname
                    if user not in user_latest_records or record.updated_at > user_latest_records[user].updated_at:
                        user_latest_records[user] = record
                
                # 基于去重后的记录进行统计
                for record in user_latest_records.values():
                    status_counts[record.status.value] += 1
                    marked_users.add(record.user_nickname)
            else:
                # 如果没有精确匹配，使用模糊匹配（但要避免过度匹配）
                fuzzy_matches = []
                for record in self.status_records.values():
                    record_work_title = record.work_title
                    # 只有当记录的标题包含目标标题的主要部分时才匹配
                    # 避免短标题匹配长标题的情况
                    is_match = any(
                        variant in record_work_title and len(variant) > len(record_work_title) * 0.6
                        for variant in work_title_variants
                    )
                    
                    if is_match:
                        fuzzy_matches.append(record)
                
                # 对模糊匹配结果也进行去重
                user_latest_records = {}
                for record in fuzzy_matches:
                    user = record.user_nickname
                    if user not in user_latest_records or record.updated_at > user_latest_records[user].updated_at:
                        user_latest_records[user] = record
                
                # 基于去重后的记录进行统计
                for record in user_latest_records.values():
                    status_counts[record.status.value] += 1
                    marked_users.add(record.user_nickname)
            
            # 计算未标记状态的评论（默认为待处理）
            unmarked_users = unique_users - marked_users
            total_marked_comments = sum(status_counts.values())
            
            # 正确计算待处理数量：手动标记的待处理 + 未标记的用户
            actual_pending = status_counts[CommentStatus.PENDING.value] + len(unmarked_users)
            
            # 更新状态分布
            status_counts[CommentStatus.PENDING.value] = actual_pending
            
            # 计算完成率
            completion_rate = (status_counts[CommentStatus.COMPLETED.value] / total_actual_comments * 100) if total_actual_comments > 0 else 0
            
            # 最近活动（限制在当前作品） - 使用去重后的记录
            if exact_matches:
                # 使用精确匹配的去重记录
                work_activities = list(user_latest_records.values()) if 'user_latest_records' in locals() else []
            else:
                # 如果有模糊匹配的去重记录，使用它们
                work_activities = list(user_latest_records.values()) if 'user_latest_records' in locals() else []
            
            recent_activities = sorted(work_activities, key=lambda x: x.updated_at, reverse=True)[:10]
            
            return {
                'total_comments': total_actual_comments,
                'unique_users': len(unique_users),
                'unique_works': 1,  # 当前作品
                'pending_count': actual_pending,
                'watching_count': status_counts[CommentStatus.WATCHING.value],
                'completed_count': status_counts[CommentStatus.COMPLETED.value],
                'status_distribution': status_counts,
                'completion_rate': completion_rate,
                'marked_comments': total_marked_comments,
                'unmarked_comments': len(unmarked_users),
                'work_title': work_title,
                'recent_activities': [
                    {
                        'user_nickname': record.user_nickname,
                        'work_title': record.work_title,
                        'status': record.status.value,
                        'updated_at': record.updated_at.isoformat()
                    }
                    for record in recent_activities
                ]
            }
            
        except Exception as e:
            print(f"获取作品统计信息失败: {e}")
            # 如果获取失败，返回基本信息
            return {
                'total_comments': 0,
                'unique_users': 0,
                'unique_works': 0,
                'pending_count': 0,
                'watching_count': 0,
                'completed_count': 0,
                'status_distribution': {status.value: 0 for status in CommentStatus},
                'completion_rate': 0,
                'marked_comments': 0,
                'unmarked_comments': 0,
                'work_title': '未知作品',
                'recent_activities': []
            }
    
    def bulk_update_status(self, comment_ids: List[str], new_status: CommentStatus, 
                          operator: str = "", notes: str = "") -> int:
        """批量更新状态"""
        updated_count = 0
        
        for comment_id in comment_ids:
            if comment_id in self.status_records:
                record = self.status_records[comment_id]
                old_status = record.status
                record.status = new_status
                record.updated_at = datetime.now()
                record.operator = operator
                if notes:
                    record.notes = notes
                
                # 记录状态变更
                if old_status != new_status:
                    self.log_status_change(comment_id, old_status, new_status, operator)
                
                updated_count += 1
        
        # 保存更改
        if updated_count > 0:
            self.save_status_records()
        
        return updated_count
    
    def import_comments_from_local_data(self, work_dir: str, work_title: str) -> int:
        """从本地评论数据导入状态记录"""
        from local_comment_loader import LocalCommentLoader
        
        loader = LocalCommentLoader(self.work_path)
        comments = loader.load_comments_from_work(work_dir)
        
        imported_count = 0
        for comment in comments:
            user_nickname = comment.get('nickname', '未知用户')
            content = comment.get('content', '')
            
            # 生成评论ID
            comment_id = self.generate_comment_id(user_nickname, work_title, content)
            
            # 如果不存在则添加为待处理状态
            if comment_id not in self.status_records:
                self.add_or_update_comment_status(
                    user_nickname=user_nickname,
                    work_title=work_title,
                    comment_content=content,
                    status=CommentStatus.PENDING,
                    notes="从本地数据自动导入"
                )
                imported_count += 1
        
        return imported_count
    
    def export_status_data(self, format: str = "json") -> str:
        """导出状态数据"""
        if format == "json":
            export_data = []
            for record in self.status_records.values():
                export_data.append({
                    'comment_id': record.comment_id,
                    'user_nickname': record.user_nickname,
                    'work_title': record.work_title,
                    'comment_content': record.comment_content,
                    'status': record.status.value,
                    'created_at': record.created_at.isoformat(),
                    'updated_at': record.updated_at.isoformat(),
                    'notes': record.notes,
                    'operator': record.operator,
                    'reply_content': record.reply_content
                })
            return json.dumps(export_data, ensure_ascii=False, indent=2)
        
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow([
                "评论ID", "用户昵称", "作品标题", "评论内容", "状态", 
                "创建时间", "更新时间", "备注", "操作人", "回复内容"
            ])
            
            # 写入数据
            for record in self.status_records.values():
                writer.writerow([
                    record.comment_id,
                    record.user_nickname,
                    record.work_title,
                    record.comment_content,
                    record.status.value,
                    record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    record.notes,
                    record.operator,
                    record.reply_content
                ])
            
            return output.getvalue()
        
        else:
            return "不支持的导出格式"
    
    def generate_xiaohongshu_work_url(self, work_dir: str, user_nickname: str = "", comment_data: dict = None) -> tuple:
        """生成小红书作品评论区URL和智能定位信息"""
        try:
            # 读取作品信息.json文件
            work_info_file = Path(work_dir) / "作品信息.json"
            if work_info_file.exists():
                with open(work_info_file, 'r', encoding='utf-8') as f:
                    work_info = json.load(f)
                
                # 获取作品链接
                work_url = work_info.get('作品链接', '')
                work_title = work_info.get('作品标题', '未知作品')
                work_id = work_info.get('作品ID', '')
                
                if not work_url and work_id:
                    work_url = f"https://www.xiaohongshu.com/explore/{work_id}"
                
                if work_url:
                    # 构建智能定位指导信息
                    location_info = self._generate_smart_location_guide(user_nickname, comment_data, work_title)
                    return work_url, location_info
            
            # 如果读取失败，返回空
            return "", "无法获取作品链接信息"
            
        except Exception as e:
            print(f"生成小红书作品URL失败: {e}")
            return "", f"生成链接失败: {str(e)}"
    
    def _generate_smart_location_guide(self, user_nickname: str, comment_data: dict, work_title: str) -> str:
        """生成智能定位指导信息"""
        from datetime import datetime
        
        guide_parts = [f"📍 跳转到作品《{work_title}》的评论区"]
        
        if comment_data:
            # 提取关键定位信息
            content = comment_data.get('content', '')
            create_time = comment_data.get('create_time', 0)
            user_info = comment_data.get('user_info', {})
            images = comment_data.get('images', [])
            
            # 时间信息
            if create_time:
                try:
                    # 转换时间戳（毫秒）为可读时间
                    dt = datetime.fromtimestamp(create_time / 1000)
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                    guide_parts.append(f"⏰ 评论时间：{time_str}")
                except:
                    pass
            
            # 用户信息
            if user_nickname:
                guide_parts.append(f"👤 目标用户：【{user_nickname}】")
                
            # 内容关键词（用于Ctrl+F搜索）
            if content:
                # 提取有用的关键词
                content_keywords = self._extract_search_keywords(content)
                if content_keywords:
                    guide_parts.append(f"🔍 搜索关键词：{' 或 '.join(content_keywords)}")
            
            # 图片特征
            if images:
                img_count = len(images)
                guide_parts.append(f"🖼️ 包含图片：{img_count}张")
                
                # 提取图片尺寸特征
                try:
                    first_img = images[0]
                    if 'height' in first_img and 'width' in first_img:
                        h, w = first_img['height'], first_img['width']
                        guide_parts.append(f"📐 图片尺寸：{w}×{h}")
                except:
                    pass
        
        return "\n".join(guide_parts)
    
    def _extract_search_keywords(self, content: str) -> list:
        """提取评论内容中适合搜索的关键词"""
        # 移除常见表情符号
        import re
        content = re.sub(r'\[.*?R?\]', '', content)
        
        # 分词并提取关键词
        keywords = []
        
        # 1. 提取房间类型词汇
        room_keywords = ['客厅', '卧室', '厨房', '卫生间', '书房', '阳台', '玄关', '餐厅']
        for keyword in room_keywords:
            if keyword in content:
                keywords.append(keyword)
        
        # 2. 提取装修相关词汇
        deco_keywords = ['装修', '改造', '设计', '风格', '现代', '简约', '北欧', '中式', '工业', '复古']
        for keyword in deco_keywords:
            if keyword in content:
                keywords.append(keyword)
        
        # 3. 提取特殊词汇（连续汉字，3-8个字符）
        special_words = re.findall(r'[\u4e00-\u9fff]{3,8}', content)
        for word in special_words[:2]:  # 只取前2个
            if word not in keywords and len(word) >= 3:
                keywords.append(word)
        
        # 4. 如果没有找到关键词，使用用户名
        if not keywords:
            # 提取内容前10个字符作为搜索词
            clean_content = re.sub(r'[^\u4e00-\u9fff\w]', '', content)
            if len(clean_content) >= 3:
                keywords.append(clean_content[:10])
        
        return keywords[:3]  # 最多返回3个关键词
    
    def generate_xiaohongshu_search_url(self, user_nickname: str, content_snippet: str = "") -> str:
        """生成小红书搜索URL（备用方法）"""
        import urllib.parse
        
        # 构建搜索关键词
        if content_snippet:
            # 取评论内容的前20个字符作为搜索关键词
            search_keyword = f"{user_nickname} {content_snippet[:20]}"
        else:
            search_keyword = user_nickname
        
        # URL编码
        encoded_keyword = urllib.parse.quote(search_keyword)
        
        # 小红书搜索URL
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={encoded_keyword}&type=54"
        
        return search_url


# 测试函数
def test_comment_status_manager():
    """测试评论状态管理器"""
    
    manager = CommentStatusManager("Comments_Dynamic")
    
    print("🧪 开始测试评论状态管理器")
    print("="*50)
    
    # 添加测试评论状态
    print("1️⃣ 添加测试评论状态...")
    comment_id1 = manager.add_or_update_comment_status(
        user_nickname="测试用户1",
        work_title="出租屋改造",
        comment_content="我想把我的客厅改成现代简约风格，预算大概2万",
        status=CommentStatus.PENDING,
        operator="系统管理员"
    )
    print(f"   添加评论1: {comment_id1}")
    
    comment_id2 = manager.add_or_update_comment_status(
        user_nickname="测试用户2", 
        work_title="出租屋改造",
        comment_content="求推荐北欧风格的家具搭配",
        status=CommentStatus.WATCHING,
        operator="系统管理员"
    )
    print(f"   添加评论2: {comment_id2}")
    
    # 更新状态
    print("\n2️⃣ 测试状态更新...")
    manager.add_or_update_comment_status(
        user_nickname="测试用户1",
        work_title="出租屋改造", 
        comment_content="我想把我的客厅改成现代简约风格，预算大概2万",
        status=CommentStatus.COMPLETED,
        operator="系统管理员",
        reply_content="已为您提供详细的现代简约风格改造方案"
    )
    print("   状态更新完成")
    
    # 获取统计信息
    print("\n3️⃣ 获取统计信息...")
    stats = manager.get_statistics()
    print(f"   总评论数: {stats['total_comments']}")
    print(f"   用户数: {stats['unique_users']}")
    print(f"   待处理: {stats['pending_count']}")
    print(f"   观察中: {stats['watching_count']}")
    print(f"   已完成: {stats['completed_count']}")
    print(f"   完成率: {stats['completion_rate']:.1f}%")
    
    # 搜索功能
    print("\n4️⃣ 测试搜索功能...")
    search_results = manager.search_comments(keyword="现代简约")
    print(f"   搜索'现代简约'结果: {len(search_results)} 条")
    
    # 生成小红书搜索URL
    print("\n5️⃣ 生成小红书搜索URL...")
    search_url = manager.generate_xiaohongshu_search_url("测试用户1", "客厅改成现代简约风格")
    print(f"   搜索URL: {search_url}")
    
    # 测试新的作品链接生成功能
    print("\n6️⃣ 测试作品评论区链接生成...")
    try:
        from pathlib import Path
        comments_dir = Path("Comments_Dynamic")
        if comments_dir.exists():
            work_dirs = [d for d in comments_dir.iterdir() if d.is_dir()]
            if work_dirs:
                test_work_dir = str(work_dirs[0])
                work_url, instruction = manager.generate_xiaohongshu_work_url(test_work_dir, "测试用户1")
                print(f"   作品目录: {test_work_dir}")
                print(f"   作品链接: {work_url}")
                print(f"   指导说明: {instruction}")
            else:
                print("   没有找到作品目录")
        else:
            print("   Comments_Dynamic目录不存在")
    except Exception as e:
        print(f"   测试失败: {e}")
    
    # 导出数据
    print("\n7️⃣ 测试数据导出...")
    exported_data = manager.export_status_data("json")
    print(f"   导出数据长度: {len(exported_data)} 字符")
    
    print("\n✅ 评论状态管理器测试完成!")


if __name__ == "__main__":
    test_comment_status_manager()