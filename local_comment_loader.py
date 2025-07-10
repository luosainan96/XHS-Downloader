#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地评论数据加载器
从Comments_Dynamic目录中加载历史评论数据
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import re


class LocalCommentLoader:
    """本地评论数据加载器"""
    
    def __init__(self, base_path: str = "Comments_Dynamic"):
        """初始化加载器
        
        Args:
            base_path: Comments_Dynamic目录路径
        """
        self.base_path = Path(base_path)
        self._works_cache = None
        self._last_scan_time = None
    
    def scan_available_works(self, force_refresh: bool = False) -> List[Dict]:
        """扫描可用的作品目录
        
        Args:
            force_refresh: 是否强制刷新缓存
            
        Returns:
            作品信息列表
        """
        # 检查缓存
        current_time = time.time()
        if (not force_refresh and 
            self._works_cache and 
            self._last_scan_time and 
            current_time - self._last_scan_time < 60):  # 1分钟缓存
            return self._works_cache
        
        works = []
        
        if not self.base_path.exists():
            return works
        
        # 扫描所有子目录
        for work_dir in self.base_path.iterdir():
            if not work_dir.is_dir():
                continue
            
            # 跳过特殊目录
            skip_dirs = ['browser_profile', 'debug', 'test_work', 'all_comment_images']
            if work_dir.name in skip_dirs:
                continue
            
            # 检查是否包含作品信息文件
            work_info_file = work_dir / "作品信息.json"
            if not work_info_file.exists():
                continue
            
            try:
                # 读取作品信息
                with open(work_info_file, 'r', encoding='utf-8') as f:
                    work_info = json.load(f)
                
                # 统计评论数量
                comment_count = self._count_comments_in_work(work_dir)
                
                # 获取最新评论时间
                latest_comment_time = self._get_latest_comment_time(work_dir)
                
                # 检查是否有图片
                has_images = self._check_work_has_images(work_dir)
                
                work_data = {
                    'work_title': work_info.get('作品标题', work_dir.name),
                    'work_id': work_info.get('作品ID', ''),
                    'work_link': work_info.get('作品链接', ''),
                    'work_description': work_info.get('作品描述', ''),
                    'work_dir': str(work_dir),
                    'comment_count': comment_count,
                    'latest_comment_time': latest_comment_time,
                    'has_images': has_images,
                    'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                works.append(work_data)
                
            except Exception as e:
                print(f"读取作品信息失败 {work_dir.name}: {e}")
                continue
        
        # 按最新评论时间排序
        works.sort(key=lambda x: x['latest_comment_time'] or '', reverse=True)
        
        # 更新缓存
        self._works_cache = works
        self._last_scan_time = current_time
        
        return works
    
    def load_comments_from_work(self, work_dir: str) -> List[Dict]:
        """从指定作品目录加载评论数据
        
        Args:
            work_dir: 作品目录路径
            
        Returns:
            评论数据列表
        """
        work_path = Path(work_dir)
        if not work_path.exists():
            return []
        
        comments = []
        
        # 遍历所有用户目录
        for user_dir in work_path.iterdir():
            if not user_dir.is_dir():
                continue
            
            # 跳过特殊文件
            if user_dir.name in ['作品信息.json', '提取报告.txt']:
                continue
            
            # 读取评论数据
            comment_data = self._load_single_comment(user_dir)
            if comment_data:
                comments.append(comment_data)
        
        # 按时间排序（最新在前）
        comments.sort(key=lambda x: x.get('create_time', 0), reverse=True)
        
        return comments
    
    def _load_single_comment(self, user_dir: Path) -> Optional[Dict]:
        """加载单个评论数据
        
        Args:
            user_dir: 用户评论目录
            
        Returns:
            评论数据字典
        """
        try:
            # 读取原始数据
            raw_data_file = user_dir / "原始数据.json"
            if not raw_data_file.exists():
                return None
            
            with open(raw_data_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            
            # 提取基本信息
            user_info = raw_data.get('user_info', {})
            nickname = user_info.get('nickname', user_dir.name)
            content = raw_data.get('content', '')
            create_time = raw_data.get('create_time', 0)
            
            # 转换时间格式
            if create_time:
                try:
                    # 转换毫秒时间戳为可读格式
                    time_str = datetime.fromtimestamp(create_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    time_str = str(create_time)
            else:
                time_str = '未知时间'
            
            # 提取图片URL
            image_urls = []
            images_data = raw_data.get('images', [])
            for img_data in images_data:
                if isinstance(img_data, dict):
                    # 优先使用urlDefault，其次使用urlPre
                    url = img_data.get('urlDefault') or img_data.get('urlPre')
                    if url:
                        image_urls.append(url)
                elif isinstance(img_data, str):
                    image_urls.append(img_data)
            
            # 查找已下载的图片
            downloaded_images = []
            for file_path in user_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                    downloaded_images.append(str(file_path))
            
            # 构造评论数据（与现有格式兼容）
            comment_data = {
                'nickname': nickname,
                'time': time_str,
                'content': content,
                'images': image_urls,
                'downloaded_images': downloaded_images,
                'comment_dir': str(user_dir),
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'create_time': create_time,
                'user_info': user_info,
                'raw_data': raw_data
            }
            
            return comment_data
            
        except Exception as e:
            print(f"加载评论数据失败 {user_dir.name}: {e}")
            return None
    
    def _count_comments_in_work(self, work_dir: Path) -> int:
        """统计作品中的评论数量"""
        count = 0
        for user_dir in work_dir.iterdir():
            if user_dir.is_dir() and (user_dir / "原始数据.json").exists():
                count += 1
        return count
    
    def _get_latest_comment_time(self, work_dir: Path) -> Optional[str]:
        """获取作品中最新的评论时间"""
        latest_time = None
        latest_timestamp = 0
        
        for user_dir in work_dir.iterdir():
            if not user_dir.is_dir():
                continue
            
            raw_data_file = user_dir / "原始数据.json"
            if not raw_data_file.exists():
                continue
            
            try:
                with open(raw_data_file, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                
                create_time = raw_data.get('create_time', 0)
                if create_time > latest_timestamp:
                    latest_timestamp = create_time
                    try:
                        latest_time = datetime.fromtimestamp(create_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        latest_time = str(create_time)
                        
            except Exception:
                continue
        
        return latest_time
    
    def _check_work_has_images(self, work_dir: Path) -> bool:
        """检查作品是否包含图片"""
        for user_dir in work_dir.iterdir():
            if not user_dir.is_dir():
                continue
            
            # 检查是否有图片文件
            for file_path in user_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                    return True
        
        return False
    
    def get_work_statistics(self, work_dir: str) -> Dict:
        """获取作品统计信息
        
        Args:
            work_dir: 作品目录路径
            
        Returns:
            统计信息字典
        """
        comments = self.load_comments_from_work(work_dir)
        
        total_comments = len(comments)
        total_images = sum(len(comment.get('images', [])) for comment in comments)
        comments_with_images = sum(1 for comment in comments if comment.get('downloaded_images'))
        total_downloaded_images = sum(len(comment.get('downloaded_images', [])) for comment in comments)
        
        return {
            'total_comments': total_comments,
            'total_images': total_images,
            'comments_with_images': comments_with_images,
            'total_downloaded_images': total_downloaded_images,
            'comments_without_images': total_comments - comments_with_images
        }
    
    def search_comments(self, work_dir: str, search_term: str = "", 
                       show_images_only: bool = False) -> List[Dict]:
        """搜索和筛选评论
        
        Args:
            work_dir: 作品目录路径
            search_term: 搜索关键词
            show_images_only: 是否只显示有图评论
            
        Returns:
            筛选后的评论列表
        """
        comments = self.load_comments_from_work(work_dir)
        
        # 关键词搜索
        if search_term:
            search_term = search_term.lower()
            comments = [
                comment for comment in comments 
                if (search_term in comment.get('content', '').lower() or 
                    search_term in comment.get('nickname', '').lower())
            ]
        
        # 筛选有图评论
        if show_images_only:
            comments = [
                comment for comment in comments 
                if comment.get('downloaded_images') or comment.get('images')
            ]
        
        return comments
    
    def export_work_summary(self, work_dir: str) -> str:
        """导出作品摘要信息
        
        Args:
            work_dir: 作品目录路径
            
        Returns:
            摘要文本
        """
        work_path = Path(work_dir)
        
        # 读取作品信息
        work_info_file = work_path / "作品信息.json"
        try:
            with open(work_info_file, 'r', encoding='utf-8') as f:
                work_info = json.load(f)
        except:
            work_info = {'作品标题': work_path.name}
        
        # 获取统计信息
        stats = self.get_work_statistics(work_dir)
        comments = self.load_comments_from_work(work_dir)
        
        # 生成摘要
        summary = f"""
# {work_info.get('作品标题', '未知作品')} - 评论摘要

## 基本信息
- 作品ID: {work_info.get('作品ID', '未知')}
- 提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 作品链接: {work_info.get('作品链接', '未知')}

## 统计信息
- 总评论数: {stats['total_comments']} 条
- 有图评论: {stats['comments_with_images']} 条
- 纯文本评论: {stats['comments_without_images']} 条
- 总图片数: {stats['total_images']} 张
- 已下载图片: {stats['total_downloaded_images']} 张

## 最新评论预览
"""
        
        # 添加最新3条评论
        for i, comment in enumerate(comments[:3]):
            summary += f"\n### {i+1}. {comment['nickname']} ({comment['time']})\n"
            summary += f"{comment['content']}\n"
            if comment.get('images'):
                summary += f"📸 包含 {len(comment['images'])} 张图片\n"
        
        if len(comments) > 3:
            summary += f"\n... 还有 {len(comments) - 3} 条评论\n"
        
        return summary