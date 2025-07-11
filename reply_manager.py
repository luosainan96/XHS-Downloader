#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能回复管理器
提供回复内容的编辑、保存、模板管理等功能
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import hashlib
import re


class ReplyStatus(Enum):
    """回复状态"""
    DRAFT = "draft"           # 草稿
    REVIEWED = "reviewed"     # 已审核
    APPROVED = "approved"     # 已批准
    SENT = "sent"            # 已发送
    ARCHIVED = "archived"     # 已归档


class ReplyTemplate(Enum):
    """回复模板类型"""
    PROFESSIONAL = "professional"     # 专业型
    FRIENDLY = "friendly"            # 友好型
    DETAILED = "detailed"            # 详细型
    CONCISE = "concise"              # 简洁型
    INTERACTIVE = "interactive"       # 互动型


@dataclass
class Reply:
    """回复数据结构"""
    reply_id: str
    original_comment_id: str
    user_nickname: str
    content: str
    template_type: ReplyTemplate
    status: ReplyStatus
    created_at: datetime
    updated_at: datetime
    tags: List[str] = None
    notes: str = ""
    approval_notes: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


class ReplyManager:
    """智能回复管理器"""
    
    def __init__(self, work_path: str = "Comments_Dynamic"):
        self.work_path = Path(work_path)
        self.replies_path = self.work_path / "reply_management"
        self.templates_path = self.replies_path / "templates"
        self.drafts_path = self.replies_path / "drafts"
        self.approved_path = self.replies_path / "approved"
        
        # 创建必要的目录
        for path in [self.replies_path, self.templates_path, self.drafts_path, self.approved_path]:
            path.mkdir(parents=True, exist_ok=True)
        
        # 预定义模板
        self.default_templates = {
            ReplyTemplate.PROFESSIONAL: {
                "name": "专业建议型",
                "description": "提供专业的家居改造建议",
                "template": """感谢您的信任！🏠 根据您分享的{房间类型}图片和需求，我为您提供以下专业建议：

{改造分析}

{具体建议}

希望这些建议对您有帮助！如需更详细的方案或产品推荐，欢迎私信咨询～

#家居改造 #室内设计 #装修建议"""
            },
            ReplyTemplate.FRIENDLY: {
                "name": "友好亲切型", 
                "description": "温暖友好的日常交流风格",
                "template": """亲爱的小伙伴！😊 看了你的{房间类型}，真的很有改造潜力呢！

{改造重点}

{温馨提示}

改造路上有任何问题都可以来找我哦，一起让家变得更美好！💕

#温馨家居 #改造分享 #生活美学"""
            },
            ReplyTemplate.DETAILED: {
                "name": "详细指导型",
                "description": "提供详细的步骤和具体指导",
                "template": """详细改造方案来啦！📋 

**现状分析：**
{现状分析}

**改造方案：**
{详细方案}

**实施步骤：**
{实施步骤}

**预算参考：**
{预算建议}

有任何细节问题都可以继续问我哦！

#详细攻略 #家居改造 #实用指南"""
            },
            ReplyTemplate.CONCISE: {
                "name": "简洁实用型",
                "description": "简洁明了，突出重点",
                "template": """{核心建议} 💡

{关键要点}

{行动建议}

#简洁实用 #家居tips"""
            },
            ReplyTemplate.INTERACTIVE: {
                "name": "互动引导型",
                "description": "引导用户参与和后续互动",
                "template": """哇，你的{房间类型}好有改造潜力！🤩

{互动问题}

{引导建议}

你觉得哪个方向比较感兴趣？评论区告诉我，我们一起讨论～

记得关注我，更多改造案例持续分享！✨

#互动讨论 #家居改造 #关注更多"""
            }
        }
        
        # 初始化模板
        self.init_default_templates()
    
    def init_default_templates(self):
        """初始化默认模板"""
        for template_type, template_data in self.default_templates.items():
            template_file = self.templates_path / f"{template_type.value}.json"
            if not template_file.exists():
                with open(template_file, 'w', encoding='utf-8') as f:
                    json.dump(template_data, f, ensure_ascii=False, indent=2)
    
    def generate_reply_id(self, user_nickname: str, timestamp: str = None) -> str:
        """生成回复ID"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        unique_str = f"{user_nickname}_{timestamp}_{time.time()}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    def create_reply(self, original_comment_id: str, user_nickname: str, 
                    content: str, template_type: ReplyTemplate = ReplyTemplate.PROFESSIONAL,
                    tags: List[str] = None) -> Reply:
        """创建新回复"""
        
        reply_id = self.generate_reply_id(user_nickname)
        
        reply = Reply(
            reply_id=reply_id,
            original_comment_id=original_comment_id,
            user_nickname=user_nickname,
            content=content,
            template_type=template_type,
            status=ReplyStatus.DRAFT,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            tags=tags or []
        )
        
        # 保存草稿
        self.save_reply(reply)
        
        return reply
    
    def save_reply(self, reply: Reply):
        """保存回复"""
        # 根据状态选择保存路径
        if reply.status == ReplyStatus.DRAFT:
            save_path = self.drafts_path
        elif reply.status in [ReplyStatus.REVIEWED, ReplyStatus.APPROVED]:
            save_path = self.approved_path
        else:
            save_path = self.replies_path
        
        reply_file = save_path / f"{reply.reply_id}.json"
        
        # 更新时间
        reply.updated_at = datetime.now()
        
        # 序列化保存
        reply_data = {
            "reply_id": reply.reply_id,
            "original_comment_id": reply.original_comment_id,
            "user_nickname": reply.user_nickname,
            "content": reply.content,
            "template_type": reply.template_type.value,
            "status": reply.status.value,
            "created_at": reply.created_at.isoformat(),
            "updated_at": reply.updated_at.isoformat(),
            "tags": reply.tags,
            "notes": reply.notes,
            "approval_notes": reply.approval_notes,
            "metadata": reply.metadata
        }
        
        with open(reply_file, 'w', encoding='utf-8') as f:
            json.dump(reply_data, f, ensure_ascii=False, indent=2)
    
    def load_reply(self, reply_id: str) -> Optional[Reply]:
        """加载回复"""
        # 在各个目录中查找
        search_paths = [self.drafts_path, self.approved_path, self.replies_path]
        
        for path in search_paths:
            reply_file = path / f"{reply_id}.json"
            if reply_file.exists():
                try:
                    with open(reply_file, 'r', encoding='utf-8') as f:
                        reply_data = json.load(f)
                    
                    return Reply(
                        reply_id=reply_data['reply_id'],
                        original_comment_id=reply_data['original_comment_id'],
                        user_nickname=reply_data['user_nickname'],
                        content=reply_data['content'],
                        template_type=ReplyTemplate(reply_data['template_type']),
                        status=ReplyStatus(reply_data['status']),
                        created_at=datetime.fromisoformat(reply_data['created_at']),
                        updated_at=datetime.fromisoformat(reply_data['updated_at']),
                        tags=reply_data.get('tags', []),
                        notes=reply_data.get('notes', ''),
                        approval_notes=reply_data.get('approval_notes', ''),
                        metadata=reply_data.get('metadata', {})
                    )
                except Exception as e:
                    print(f"加载回复失败 {reply_id}: {e}")
                    return None
        
        return None
    
    def update_reply(self, reply_id: str, content: str = None, tags: List[str] = None, 
                    notes: str = None, status: ReplyStatus = None) -> bool:
        """更新回复"""
        reply = self.load_reply(reply_id)
        if not reply:
            return False
        
        # 更新字段
        if content is not None:
            reply.content = content
        if tags is not None:
            reply.tags = tags
        if notes is not None:
            reply.notes = notes
        if status is not None:
            old_status = reply.status
            reply.status = status
            
            # 如果状态改变，可能需要移动文件
            if old_status != status:
                self.move_reply(reply, old_status, status)
        
        # 保存更新
        self.save_reply(reply)
        return True
    
    def move_reply(self, reply: Reply, old_status: ReplyStatus, new_status: ReplyStatus):
        """移动回复文件到新的状态目录"""
        old_paths = {
            ReplyStatus.DRAFT: self.drafts_path,
            ReplyStatus.REVIEWED: self.approved_path,
            ReplyStatus.APPROVED: self.approved_path
        }
        
        old_file = old_paths.get(old_status, self.replies_path) / f"{reply.reply_id}.json"
        if old_file.exists():
            old_file.unlink()  # 删除旧文件
    
    def delete_reply(self, reply_id: str) -> bool:
        """删除回复"""
        reply = self.load_reply(reply_id)
        if not reply:
            return False
        
        # 根据状态找到文件路径并删除
        search_paths = [self.drafts_path, self.approved_path, self.replies_path]
        
        for path in search_paths:
            reply_file = path / f"{reply_id}.json"
            if reply_file.exists():
                reply_file.unlink()
                return True
        
        return False
    
    def get_replies_by_status(self, status: ReplyStatus, limit: int = 50) -> List[Reply]:
        """按状态获取回复列表"""
        if status == ReplyStatus.DRAFT:
            search_path = self.drafts_path
        elif status in [ReplyStatus.REVIEWED, ReplyStatus.APPROVED]:
            search_path = self.approved_path
        else:
            search_path = self.replies_path
        
        replies = []
        reply_files = sorted(
            search_path.glob("*.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for reply_file in reply_files[:limit]:
            reply = self.load_reply(reply_file.stem)
            if reply and reply.status == status:
                replies.append(reply)
        
        return replies
    
    def search_replies(self, keyword: str = "", user_nickname: str = "", 
                      tags: List[str] = None, status: ReplyStatus = None,
                      limit: int = 50) -> List[Reply]:
        """搜索回复"""
        all_replies = []
        
        # 收集所有回复
        search_paths = [self.drafts_path, self.approved_path, self.replies_path]
        for path in search_paths:
            for reply_file in path.glob("*.json"):
                reply = self.load_reply(reply_file.stem)
                if reply:
                    all_replies.append(reply)
        
        # 应用过滤条件
        filtered_replies = []
        for reply in all_replies:
            # 关键词过滤
            if keyword and keyword.lower() not in reply.content.lower():
                continue
            
            # 用户昵称过滤
            if user_nickname and user_nickname.lower() not in reply.user_nickname.lower():
                continue
            
            # 标签过滤
            if tags and not any(tag in reply.tags for tag in tags):
                continue
            
            # 状态过滤
            if status and reply.status != status:
                continue
            
            filtered_replies.append(reply)
        
        # 按更新时间排序
        filtered_replies.sort(key=lambda x: x.updated_at, reverse=True)
        
        return filtered_replies[:limit]
    
    def get_reply_templates(self) -> Dict[str, Dict]:
        """获取所有回复模板"""
        templates = {}
        
        for template_file in self.templates_path.glob("*.json"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                templates[template_file.stem] = template_data
            except Exception as e:
                print(f"加载模板失败 {template_file}: {e}")
        
        return templates
    
    def create_template(self, template_name: str, template_content: str, 
                       description: str = "", tags: List[str] = None) -> bool:
        """创建自定义模板"""
        template_file = self.templates_path / f"custom_{template_name}.json"
        
        template_data = {
            "name": template_name,
            "description": description,
            "template": template_content,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "is_custom": True
        }
        
        try:
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"创建模板失败: {e}")
            return False
    
    def apply_template(self, template_name: str, variables: Dict[str, str]) -> str:
        """应用模板生成回复内容"""
        templates = self.get_reply_templates()
        
        if template_name not in templates:
            return f"模板 '{template_name}' 不存在"
        
        template_content = templates[template_name]['template']
        
        # 替换变量
        for var_name, var_value in variables.items():
            placeholder = f"{{{var_name}}}"
            template_content = template_content.replace(placeholder, var_value)
        
        return template_content
    
    def get_reply_statistics(self) -> Dict:
        """获取回复统计信息"""
        stats = {
            "total_replies": 0,
            "drafts": 0,
            "reviewed": 0,
            "approved": 0,
            "sent": 0,
            "archived": 0,
            "templates_count": len(self.get_reply_templates()),
            "recent_activity": []
        }
        
        # 统计各状态的回复数量
        for status in ReplyStatus:
            replies = self.get_replies_by_status(status, limit=1000)
            count = len(replies)
            stats[status.value] = count
            stats["total_replies"] += count
            
            # 记录最近活动
            for reply in replies[:5]:  # 取最近5个
                stats["recent_activity"].append({
                    "reply_id": reply.reply_id,
                    "user_nickname": reply.user_nickname,
                    "status": reply.status.value,
                    "updated_at": reply.updated_at.isoformat()
                })
        
        # 按时间排序最近活动
        stats["recent_activity"].sort(key=lambda x: x["updated_at"], reverse=True)
        stats["recent_activity"] = stats["recent_activity"][:10]
        
        return stats
    
    def export_replies(self, status: ReplyStatus = None, format: str = "json") -> str:
        """导出回复数据"""
        if status:
            replies = self.get_replies_by_status(status, limit=1000)
        else:
            replies = self.search_replies(limit=1000)
        
        if format == "json":
            export_data = []
            for reply in replies:
                export_data.append({
                    "reply_id": reply.reply_id,
                    "user_nickname": reply.user_nickname,
                    "content": reply.content,
                    "status": reply.status.value,
                    "created_at": reply.created_at.isoformat(),
                    "tags": reply.tags
                })
            return json.dumps(export_data, ensure_ascii=False, indent=2)
        
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow(["回复ID", "用户昵称", "回复内容", "状态", "创建时间", "标签"])
            
            # 写入数据
            for reply in replies:
                writer.writerow([
                    reply.reply_id,
                    reply.user_nickname,
                    reply.content,
                    reply.status.value,
                    reply.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    ", ".join(reply.tags)
                ])
            
            return output.getvalue()
        
        else:
            return "不支持的导出格式"
    
    def cleanup_old_drafts(self, days: int = 30) -> int:
        """清理旧的草稿"""
        from datetime import timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        drafts = self.get_replies_by_status(ReplyStatus.DRAFT, limit=1000)
        for draft in drafts:
            if draft.created_at < cutoff_date:
                if self.delete_reply(draft.reply_id):
                    deleted_count += 1
        
        return deleted_count


# 测试函数
def test_reply_manager():
    """测试回复管理器"""
    
    manager = ReplyManager("Comments_Dynamic")
    
    print("🧪 开始测试回复管理器")
    print("="*50)
    
    # 创建测试回复
    print("1️⃣ 创建测试回复...")
    reply = manager.create_reply(
        original_comment_id="test_comment_1",
        user_nickname="测试用户",
        content="感谢您的咨询！根据您的需求，我建议...",
        template_type=ReplyTemplate.PROFESSIONAL,
        tags=["家居改造", "专业建议"]
    )
    print(f"   创建回复: {reply.reply_id}")
    
    # 测试模板应用
    print("\n2️⃣ 测试模板应用...")
    templates = manager.get_reply_templates()
    print(f"   可用模板数量: {len(templates)}")
    
    template_content = manager.apply_template("professional", {
        "房间类型": "客厅",
        "改造分析": "空间布局合理，需要优化色彩搭配",
        "具体建议": "建议使用现代简约风格，增加收纳功能"
    })
    print(f"   应用模板结果: {template_content[:100]}...")
    
    # 测试回复更新
    print("\n3️⃣ 测试回复更新...")
    success = manager.update_reply(
        reply.reply_id,
        content="更新后的回复内容",
        status=ReplyStatus.REVIEWED,
        notes="已审核通过"
    )
    print(f"   更新结果: {'成功' if success else '失败'}")
    
    # 测试搜索功能
    print("\n4️⃣ 测试搜索功能...")
    search_results = manager.search_replies(keyword="回复", limit=10)
    print(f"   搜索结果数量: {len(search_results)}")
    
    # 测试统计信息
    print("\n5️⃣ 测试统计信息...")
    stats = manager.get_reply_statistics()
    print(f"   总回复数: {stats['total_replies']}")
    print(f"   草稿数: {stats['drafts']}")
    print(f"   已审核数: {stats['reviewed']}")
    print(f"   模板数: {stats['templates_count']}")
    
    # 测试导出功能
    print("\n6️⃣ 测试导出功能...")
    exported_data = manager.export_replies(format="json")
    print(f"   导出数据长度: {len(exported_data)} 字符")
    
    print("\n✅ 回复管理器测试完成!")


if __name__ == "__main__":
    test_reply_manager()