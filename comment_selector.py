#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能评论选择器
用于筛选和优先排序适合AI回复的评论
"""

import asyncio
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from local_comment_loader import LocalCommentLoader
from intelligent_reply_generator import IntelligentReplyGenerator
from comment_status_manager import CommentStatusManager, CommentStatus
try:
    from utils.error_handler import (
        with_error_handling, ErrorContext, DataValidationError
    )
    from utils.file_operations import safe_file_ops
    from utils.logging_utils import get_logger, get_performance_logger
    from utils.performance_utils import batch_processor
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
    
    class DataValidationError(Exception):
        pass
    
    class MockSafeFileOps:
        def write_json_safe(self, path, data, backup=True):
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
            except:
                return False
        
        def read_json_safe(self, path, default=None):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default
    
    safe_file_ops = MockSafeFileOps()
    
    class MockLogger:
        def info(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
        def warning(self, *args, **kwargs): pass
        def debug(self, *args, **kwargs): pass
    
    def get_logger(name):
        return MockLogger()
    
    def get_performance_logger(name):
        def decorator(operation=None):
            def inner_decorator(func):
                return func
            return inner_decorator
        return decorator
    
    batch_processor = None


class CommentPriority(Enum):
    """评论优先级"""
    HIGH = "high"       # 高优先级 - 改造需求明确且有图片
    MEDIUM = "medium"   # 中等优先级 - 有改造需求或有图片
    LOW = "low"         # 低优先级 - 一般询问


class SelectionCriteria(Enum):
    """选择标准"""
    RENOVATION_REQUESTS = "renovation_requests"     # 改造需求类
    IMAGE_CONSULTATIONS = "image_consultations"     # 图片咨询类
    HIGH_ENGAGEMENT = "high_engagement"             # 高互动潜力
    RECENT_COMMENTS = "recent_comments"             # 最新评论
    UNPROCESSED_ONLY = "unprocessed_only"          # 未处理评论
    # 新增状态筛选
    STATUS_PENDING = "status_pending"               # 待处理状态
    STATUS_WATCHING = "status_watching"             # 观察中状态
    STATUS_COMPLETED = "status_completed"           # 已完成状态


@dataclass
class CommentAnalysis:
    """评论分析结果"""
    comment_id: str
    priority: CommentPriority
    renovation_score: int
    processing_recommendation: str
    estimated_cost: float
    keywords_matched: List[str]
    has_quality_images: bool
    reply_potential: float  # 0-1之间，回复潜力评分


class CommentSelector:
    """智能评论选择器"""
    
    def __init__(self, work_path: str = "Comments_Dynamic"):
        self.work_path = Path(work_path)
        self.selection_history_path = self.work_path / "selection_history"
        self.selection_history_path.mkdir(parents=True, exist_ok=True)
        
        self.comment_loader = LocalCommentLoader(work_path)
        self.status_manager = CommentStatusManager(work_path)
        
        # 家居改造关键词权重
        self.renovation_keywords = {
            # 高权重关键词 (10分)
            '改造': 10, '装修': 10, '设计': 10, '翻新': 10,
            # 中权重关键词 (7分)
            '收纳': 7, '布局': 7, '风格': 7, '搭配': 7,
            # 房间类型 (5分)
            '客厅': 5, '卧室': 5, '厨房': 5, '卫生间': 5, '书房': 5,
            '出租屋': 5, '小户型': 5, '新房': 5, '二手房': 5,
            # 家具类型 (3分)
            '家具': 3, '沙发': 3, '床': 3, '桌子': 3, '柜子': 3,
            '窗帘': 3, '灯具': 3, '地板': 3, '墙面': 3,
            # 预算相关 (8分)
            '预算': 8, '便宜': 5, '性价比': 6, 'diy': 6,
            # 问题描述 (6分)
            '求助': 6, '帮忙': 6, '建议': 6, '推荐': 6, '怎么': 6
        }
        
        # 质量评估关键词
        self.quality_keywords = {
            '详细': 3, '具体': 3, '专业': 5, '经验': 4,
            '谢谢': 2, '请问': 3, '麻烦': 3, '感谢': 2
        }
        
    async def analyze_comment(self, comment_data: Dict) -> CommentAnalysis:
        """分析单个评论的回复潜力"""
        
        content = comment_data.get('content', '').lower()
        images = comment_data.get('downloaded_images', [])
        nickname = comment_data.get('nickname', '')
        
        # 计算改造相关得分
        renovation_score = 0
        matched_keywords = []
        
        for keyword, weight in self.renovation_keywords.items():
            if keyword in content:
                renovation_score += weight
                matched_keywords.append(keyword)
        
        # 图片质量评估
        has_quality_images = len(images) > 0
        if has_quality_images:
            renovation_score += 20  # 有图片加分
            if len(images) > 1:
                renovation_score += 10  # 多图片额外加分
        
        # 内容质量评估
        content_quality_score = 0
        for keyword, weight in self.quality_keywords.items():
            if keyword in content:
                content_quality_score += weight
        
        # 内容长度评估
        content_length = len(content)
        if content_length > 50:
            content_quality_score += 5
        if content_length > 100:
            content_quality_score += 5
        
        # 计算总体回复潜力 (0-1之间)
        base_potential = min(renovation_score / 100, 1.0)  # 基础潜力
        quality_bonus = min(content_quality_score / 20, 0.3)  # 质量加成
        reply_potential = min(base_potential + quality_bonus, 1.0)
        
        # 确定优先级
        if renovation_score >= 40 and has_quality_images:
            priority = CommentPriority.HIGH
            recommendation = "强烈推荐AI回复 - 明确改造需求且有参考图片"
            estimated_cost = 0.5
        elif renovation_score >= 25 or has_quality_images:
            priority = CommentPriority.MEDIUM
            recommendation = "推荐AI回复 - 有改造潜力或图片参考"
            estimated_cost = 0.3
        elif renovation_score >= 15:
            priority = CommentPriority.MEDIUM
            recommendation = "可选AI回复 - 轻度改造相关"
            estimated_cost = 0.2
        else:
            priority = CommentPriority.LOW
            recommendation = "一般回复 - 使用模板回复即可"
            estimated_cost = 0.1
        
        # 生成唯一ID
        comment_id = f"{nickname}_{comment_data.get('time', '')}".replace(' ', '_').replace(':', '-')
        
        return CommentAnalysis(
            comment_id=comment_id,
            priority=priority,
            renovation_score=renovation_score,
            processing_recommendation=recommendation,
            estimated_cost=estimated_cost,
            keywords_matched=matched_keywords,
            has_quality_images=has_quality_images,
            reply_potential=reply_potential
        )
    
    async def select_comments_by_criteria(self, work_dir: str, 
                                        criteria: SelectionCriteria,
                                        limit: int = 20,
                                        min_priority: CommentPriority = CommentPriority.LOW) -> List[Tuple[Dict, CommentAnalysis]]:
        """根据选择标准筛选评论"""
        
        # 加载所有评论
        comments = self.comment_loader.load_comments_from_work(work_dir)
        
        # 分析所有评论
        analyzed_comments = []
        for comment in comments:
            analysis = await self.analyze_comment(comment)
            
            # 应用最低优先级过滤
            priority_order = {CommentPriority.HIGH: 3, CommentPriority.MEDIUM: 2, CommentPriority.LOW: 1}
            if priority_order[analysis.priority] >= priority_order[min_priority]:
                analyzed_comments.append((comment, analysis))
        
        # 根据选择标准进行筛选和排序
        if criteria == SelectionCriteria.RENOVATION_REQUESTS:
            # 按改造得分排序
            analyzed_comments.sort(key=lambda x: x[1].renovation_score, reverse=True)
            analyzed_comments = [item for item in analyzed_comments if item[1].renovation_score >= 20]
            
        elif criteria == SelectionCriteria.IMAGE_CONSULTATIONS:
            # 筛选有图片的评论
            analyzed_comments = [item for item in analyzed_comments if item[1].has_quality_images]
            analyzed_comments.sort(key=lambda x: len(x[0].get('downloaded_images', [])), reverse=True)
            
        elif criteria == SelectionCriteria.HIGH_ENGAGEMENT:
            # 按回复潜力排序
            analyzed_comments.sort(key=lambda x: x[1].reply_potential, reverse=True)
            analyzed_comments = [item for item in analyzed_comments if item[1].reply_potential >= 0.3]
            
        elif criteria == SelectionCriteria.RECENT_COMMENTS:
            # 按时间排序（最新优先）
            analyzed_comments.sort(key=lambda x: x[0].get('create_time', 0), reverse=True)
            
        elif criteria == SelectionCriteria.UNPROCESSED_ONLY:
            # 筛选未处理的评论（这里需要与智能回复历史对比）
            processed_ids = await self.get_processed_comment_ids()
            analyzed_comments = [
                item for item in analyzed_comments 
                if item[1].comment_id not in processed_ids
            ]
            analyzed_comments.sort(key=lambda x: x[1].priority.value == 'high', reverse=True)
            
        elif criteria == SelectionCriteria.STATUS_PENDING:
            # 筛选待处理状态的评论
            analyzed_comments = self.filter_by_comment_status(analyzed_comments, CommentStatus.PENDING)
            
        elif criteria == SelectionCriteria.STATUS_WATCHING:
            # 筛选观察中状态的评论
            analyzed_comments = self.filter_by_comment_status(analyzed_comments, CommentStatus.WATCHING)
            
        elif criteria == SelectionCriteria.STATUS_COMPLETED:
            # 筛选已完成状态的评论
            analyzed_comments = self.filter_by_comment_status(analyzed_comments, CommentStatus.COMPLETED)
        
        return analyzed_comments[:limit]
    
    def filter_by_comment_status(self, analyzed_comments: List[Tuple[Dict, CommentAnalysis]], 
                                target_status: CommentStatus) -> List[Tuple[Dict, CommentAnalysis]]:
        """根据评论状态筛选"""
        filtered_comments = []
        
        for comment, analysis in analyzed_comments:
            # 生成评论ID用于状态查找
            user_nickname = comment.get('nickname', '')
            content = comment.get('content', '')
            
            # 查找或创建状态记录
            comment_id = self.status_manager.generate_comment_id(
                user_nickname, 
                "当前作品",  # 这里可以传入实际的作品标题
                content
            )
            
            # 检查状态记录
            status_record = self.status_manager.get_comment_status(comment_id)
            
            if status_record:
                # 如果状态匹配则包含
                if status_record.status == target_status:
                    filtered_comments.append((comment, analysis))
            else:
                # 如果没有状态记录，且筛选的是待处理状态，则包含
                if target_status == CommentStatus.PENDING:
                    filtered_comments.append((comment, analysis))
        
        return filtered_comments
    
    def ensure_comment_status_exists(self, work_dir: str, work_title: str):
        """确保评论状态记录存在"""
        # 自动导入当前作品的评论状态
        imported_count = self.status_manager.import_comments_from_local_data(work_dir, work_title)
        if imported_count > 0:
            print(f"自动导入了 {imported_count} 条评论状态记录")
    
    async def get_processed_comment_ids(self) -> set:
        """获取已处理的评论ID集合"""
        processed_ids = set()
        
        # 扫描智能回复历史记录
        reply_history_path = self.work_path / "intelligent_replies"
        if reply_history_path.exists():
            for result_file in reply_history_path.glob("*_result.json"):
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                        comment_data = result.get('comment_data', {})
                        nickname = comment_data.get('nickname', '')
                        time_str = comment_data.get('time', '')
                        comment_id = f"{nickname}_{time_str}".replace(' ', '_').replace(':', '-')
                        processed_ids.add(comment_id)
                except Exception:
                    continue
        
        return processed_ids
    
    def __init__(self, work_path: str = "Comments_Dynamic"):
        self.work_path = Path(work_path)
        self.selection_history_path = self.work_path / "selection_history"
        self.selection_history_path.mkdir(parents=True, exist_ok=True)
        
        self.comment_loader = LocalCommentLoader(work_path)
        self.status_manager = CommentStatusManager(work_path)
        
        if UTILS_AVAILABLE:
            self.logger = get_logger("comment_selector")
            self.perf_logger = get_performance_logger("comment_selector")
        else:
            self.logger = MockLogger()
            self.perf_logger = get_performance_logger("comment_selector")
        
        # 初始化关键词权重
        self._init_keywords()
    
    def _init_keywords(self):
        """初始化关键词权重"""
        # 家居改造关键词权重
        self.renovation_keywords = {
            # 高权重关键词 (10分)
            '改造': 10, '装修': 10, '设计': 10, '翻新': 10,
            # 中权重关键词 (7分)
            '收纳': 7, '布局': 7, '风格': 7, '搭配': 7,
            # 房间类型 (5分)
            '客厅': 5, '卧室': 5, '厨房': 5, '卫生间': 5, '书房': 5,
            '出租屋': 5, '小户型': 5, '新房': 5, '二手房': 5,
            # 家具类型 (3分)
            '家具': 3, '沙发': 3, '床': 3, '桌子': 3, '柜子': 3,
            '窗帘': 3, '灯具': 3, '地板': 3, '墙面': 3,
            # 预算相关 (8分)
            '预算': 8, '便宜': 5, '性价比': 6, 'diy': 6,
            # 问题描述 (6分)
            '求助': 6, '帮忙': 6, '建议': 6, '推荐': 6, '怎么': 6
        }
        
        # 质量评估关键词
        self.quality_keywords = {
            '详细': 3, '具体': 3, '专业': 5, '经验': 4,
            '谢谢': 2, '请问': 3, '麻烦': 3, '感谢': 2
        }
    
    @with_error_handling(
        context=ErrorContext("create_selection_batch", "comment_selector")
    )
    async def create_selection_batch(self, work_dir: str, 
                                   criteria_list: List[SelectionCriteria],
                                   total_limit: int = 50) -> Dict:
        """创建选择批次，综合多个标准"""
        
        batch_id = self._generate_batch_id()
        batch_result = self._init_batch_result(batch_id, work_dir, criteria_list)
        
        # 按不同标准选择评论
        all_selected = await self._select_by_criteria(work_dir, criteria_list, total_limit, batch_result)
        
        # 去重并排序
        final_selections = self._deduplicate_and_sort(all_selected, total_limit)
        
        # 生成摘要和最终结果
        batch_result["summary"] = self._generate_summary(final_selections)
        batch_result["final_selections"] = self._format_final_selections(final_selections)
        
        # 保存批次结果
        await self.save_selection_batch(batch_result)
        
        return batch_result
    
    def _generate_batch_id(self) -> str:
        """生成批次ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = secrets.token_hex(4)
        return f"{timestamp}_{random_suffix}"
    
    def _init_batch_result(self, batch_id: str, work_dir: str, 
                          criteria_list: List[SelectionCriteria]) -> Dict:
        """初始化批次结果结构"""
        return {
            "batch_id": batch_id,
            "work_dir": work_dir,
            "timestamp": datetime.now().isoformat(),
            "criteria_used": [c.value for c in criteria_list],
            "selections": {},
            "summary": {}
        }
    
    async def _select_by_criteria(self, work_dir: str, criteria_list: List[SelectionCriteria],
                                 total_limit: int, batch_result: Dict) -> List[Tuple]:
        """按不同标准选择评论"""
        all_selected = []
        
        for criteria in criteria_list:
            limit_per_criteria = max(total_limit // len(criteria_list) + 5, 10)
            selected = await self.select_comments_by_criteria(
                work_dir, criteria, limit=limit_per_criteria
            )
            
            # 记录每个标准的选择结果
            batch_result["selections"][criteria.value] = [
                self._create_selection_item(comment, analysis)
                for comment, analysis in selected
            ]
            
            all_selected.extend(selected)
        
        return all_selected
    
    def _create_selection_item(self, comment: Dict, analysis) -> Dict:
        """创建选择项目"""
        return {
            "comment_id": analysis.comment_id,
            "nickname": comment.get('nickname', ''),
            "content_preview": self._truncate_content(comment.get('content', '')),
            "priority": analysis.priority.value,
            "renovation_score": analysis.renovation_score,
            "reply_potential": analysis.reply_potential,
            "estimated_cost": analysis.estimated_cost,
            "has_images": analysis.has_quality_images,
            "keywords_matched": analysis.keywords_matched,
            "recommendation": analysis.processing_recommendation
        }
    
    def _truncate_content(self, content: str, max_length: int = 100) -> str:
        """截断内容预览"""
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."
    
    def _deduplicate_and_sort(self, all_selected: List[Tuple], total_limit: int) -> List[Tuple]:
        """去重并按优先级排序"""
        # 去重
        unique_selections = {}
        for comment, analysis in all_selected:
            if analysis.comment_id not in unique_selections:
                unique_selections[analysis.comment_id] = (comment, analysis)
        
        # 排序
        final_selections = list(unique_selections.values())
        final_selections.sort(
            key=lambda x: (
                x[1].priority.value == 'high',
                x[1].reply_potential,
                x[1].renovation_score
            ), 
            reverse=True
        )
        
        return final_selections[:total_limit]
    
    def _generate_summary(self, final_selections: List[Tuple]) -> Dict:
        """生成批次摘要"""
        if not final_selections:
            return {
                "total_selected": 0,
                "high_priority_count": 0,
                "medium_priority_count": 0,
                "low_priority_count": 0,
                "total_estimated_cost": 0.0,
                "average_renovation_score": 0.0,
                "images_available": 0
            }
        
        priority_counts = {
            CommentPriority.HIGH: 0,
            CommentPriority.MEDIUM: 0,
            CommentPriority.LOW: 0
        }
        
        total_cost = 0.0
        total_score = 0.0
        images_count = 0
        
        for _, analysis in final_selections:
            priority_counts[analysis.priority] += 1
            total_cost += analysis.estimated_cost
            total_score += analysis.renovation_score
            if analysis.has_quality_images:
                images_count += 1
        
        return {
            "total_selected": len(final_selections),
            "high_priority_count": priority_counts[CommentPriority.HIGH],
            "medium_priority_count": priority_counts[CommentPriority.MEDIUM],
            "low_priority_count": priority_counts[CommentPriority.LOW],
            "total_estimated_cost": round(total_cost, 2),
            "average_renovation_score": round(total_score / len(final_selections), 1),
            "images_available": images_count
        }
    
    def _format_final_selections(self, final_selections: List[Tuple]) -> List[Dict]:
        """格式化最终选择结果"""
        return [
            {
                "comment_data": comment,
                "analysis": {
                    "comment_id": analysis.comment_id,
                    "priority": analysis.priority.value,
                    "renovation_score": analysis.renovation_score,
                    "reply_potential": analysis.reply_potential,
                    "estimated_cost": analysis.estimated_cost,
                    "has_quality_images": analysis.has_quality_images,
                    "keywords_matched": analysis.keywords_matched,
                    "processing_recommendation": analysis.processing_recommendation
                }
            }
            for comment, analysis in final_selections
        ]
    
    @with_error_handling(
        context=ErrorContext("save_selection_batch", "comment_selector")
    )
    async def save_selection_batch(self, batch_result: Dict) -> bool:
        """保存选择批次"""
        batch_id = batch_result["batch_id"]
        save_path = self.selection_history_path / f"batch_{batch_id}.json"
        
        return safe_file_ops.write_json_safe(save_path, batch_result)
    
    @with_error_handling(
        context=ErrorContext("load_selection_batch", "comment_selector"),
        fallback_value=None
    )
    async def load_selection_batch(self, batch_id: str) -> Optional[Dict]:
        """加载选择批次"""
        save_path = self.selection_history_path / f"batch_{batch_id}.json"
        return safe_file_ops.read_json_safe(save_path)
    
    def get_selection_history(self, limit: int = 20) -> List[Dict]:
        """获取选择历史"""
        history_files = sorted(
            self.selection_history_path.glob("batch_*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        history = []
        for file_path in history_files[:limit]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    batch = json.load(f)
                    history.append({
                        "batch_id": batch["batch_id"],
                        "timestamp": batch["timestamp"],
                        "work_dir": batch["work_dir"],
                        "total_selected": batch["summary"]["total_selected"],
                        "high_priority": batch["summary"]["high_priority_count"],
                        "estimated_cost": batch["summary"]["total_estimated_cost"]
                    })
            except Exception as e:
                print(f"读取选择历史失败 {file_path}: {e}")
                continue
        
        return history
    
    async def smart_auto_select(self, work_dir: str, 
                              daily_budget: float = 10.0,
                              max_comments: int = 20) -> Dict:
        """智能自动选择 - 在预算范围内选择最有价值的评论"""
        
        # 综合多种标准
        criteria_list = [
            SelectionCriteria.RENOVATION_REQUESTS,
            SelectionCriteria.IMAGE_CONSULTATIONS,
            SelectionCriteria.HIGH_ENGAGEMENT,
            SelectionCriteria.UNPROCESSED_ONLY
        ]
        
        # 创建初始选择批次
        batch = await self.create_selection_batch(work_dir, criteria_list, max_comments * 2)
        
        # 在预算范围内优化选择
        final_selections = []
        current_cost = 0.0
        
        for item in batch["final_selections"]:
            estimated_cost = item["analysis"]["estimated_cost"]
            if current_cost + estimated_cost <= daily_budget:
                final_selections.append(item)
                current_cost += estimated_cost
                
                if len(final_selections) >= max_comments:
                    break
        
        # 更新批次结果
        batch["final_selections"] = final_selections
        batch["summary"]["total_selected"] = len(final_selections)
        batch["summary"]["total_estimated_cost"] = round(current_cost, 2)
        batch["summary"]["budget_used_percentage"] = round((current_cost / daily_budget) * 100, 1)
        
        # 重新保存
        await self.save_selection_batch(batch)
        
        return batch


# 测试函数
async def test_comment_selector():
    """测试评论选择器"""
    
    selector = CommentSelector("Comments_Dynamic")
    
    print("🧪 开始测试评论选择器")
    print("="*50)
    
    # 获取可用作品
    works = selector.comment_loader.scan_available_works()
    if not works:
        print("❌ 没有找到可用的作品数据")
        return
    
    test_work = works[0]
    work_dir = test_work['work_dir']
    
    print(f"📁 测试作品: {test_work['work_title']}")
    print(f"📊 评论数量: {test_work['comment_count']}")
    
    # 测试不同选择标准
    criteria_tests = [
        SelectionCriteria.RENOVATION_REQUESTS,
        SelectionCriteria.IMAGE_CONSULTATIONS,
        SelectionCriteria.HIGH_ENGAGEMENT
    ]
    
    for criteria in criteria_tests:
        print(f"\n🔍 测试选择标准: {criteria.value}")
        selected = await selector.select_comments_by_criteria(work_dir, criteria, limit=5)
        
        print(f"   选择数量: {len(selected)}")
        for i, (comment, analysis) in enumerate(selected[:3]):
            print(f"   {i+1}. {comment['nickname']} - 得分:{analysis.renovation_score} - 优先级:{analysis.priority.value}")
            print(f"      内容预览: {comment['content'][:50]}...")
            print(f"      关键词: {', '.join(analysis.keywords_matched[:3])}")
    
    # 测试智能自动选择
    print(f"\n🤖 测试智能自动选择...")
    auto_batch = await selector.smart_auto_select(work_dir, daily_budget=5.0, max_comments=10)
    
    print(f"   批次ID: {auto_batch['batch_id']}")
    print(f"   总选择数: {auto_batch['summary']['total_selected']}")
    print(f"   预估成本: ${auto_batch['summary']['total_estimated_cost']}")
    print(f"   预算使用率: {auto_batch['summary'].get('budget_used_percentage', 0)}%")
    
    # 显示前3个选择
    print(f"\n📋 前3个推荐评论:")
    for i, item in enumerate(auto_batch['final_selections'][:3]):
        comment = item['comment_data']
        analysis = item['analysis']
        print(f"   {i+1}. {comment['nickname']} - {analysis['priority']} 优先级")
        print(f"      改造得分: {analysis['renovation_score']}")
        print(f"      回复潜力: {analysis['reply_potential']:.2f}")
        print(f"      预估成本: ${analysis['estimated_cost']}")
        print(f"      推荐理由: {analysis['processing_recommendation']}")
        print()


if __name__ == "__main__":
    asyncio.run(test_comment_selector())