#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能回复生成器 - AI家居改造助手
专注于家居改造评论的智能分析和回复生成
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import re

from ai_model_manager import AIModelManager, TaskRequest, TaskType


class AIModelInterface(ABC):
    """AI模型接口抽象类"""
    
    @abstractmethod
    async def analyze_room_image(self, image_path: str, user_comment: str) -> Dict:
        """分析房屋图片"""
        pass
    
    @abstractmethod
    async def generate_renovation_plans(self, room_analysis: str, user_requirements: str) -> Dict:
        """生成改造方案"""
        pass
    
    @abstractmethod
    async def generate_renovation_image(self, renovation_plan: str, style_name: str) -> Dict:
        """生成改造效果图"""
        pass
    
    @abstractmethod
    async def create_before_after_comparison(self, original_image: str, generated_image: str) -> Dict:
        """创建前后对比图"""
        pass
    
    @abstractmethod
    async def generate_professional_reply(self, original_comment: str, analysis: str, plans: str) -> Dict:
        """生成专业回复"""
        pass


class MockAIModel(AIModelInterface):
    """模拟AI模型 - 用于开发和测试"""
    
    def __init__(self):
        self.call_count = 0
        self.mock_delay = 2  # 模拟处理时间
    
    async def analyze_room_image(self, image_path: str, user_comment: str) -> Dict:
        """模拟房屋图片分析"""
        await asyncio.sleep(self.mock_delay)
        self.call_count += 1
        
        return {
            "success": True,
            "analysis": f"""
## 1. 空间基本信息
- 房间类型：客厅
- 估算面积：25-30平方米
- 层高情况：2.7米标准层高
- 采光条件：南向采光良好
- 现有布局：传统三件套布局

## 2. 现状问题诊断
- 空间利用问题：角落空间未充分利用
- 功能性不足：缺乏充足的收纳空间
- 美观性问题：色彩搭配较为单调
- 收纳整理问题：物品摆放缺乏系统性

## 3. 改造潜力评估
- 结构改动可能性：无需大型结构改动
- 预算友好改造点：家具重新布局、色彩搭配优化
- 风格转换建议：适合现代简约或北欧风格改造
- 功能提升空间：可增加30%的收纳空间

## 4. 用户需求匹配度
- 具体需求分析：{user_comment}
- 预算考虑：中等预算即可实现理想效果
- 生活方式适配：适合现代都市生活方式
            """,
            "processing_time": self.mock_delay,
            "cost_estimate": 0.05,
            "model_used": "mock_gpt4o"
        }
    
    async def generate_renovation_plans(self, room_analysis: str, user_requirements: str) -> Dict:
        """模拟改造方案生成"""
        await asyncio.sleep(self.mock_delay)
        self.call_count += 1
        
        return {
            "success": True,
            "renovation_plans": """
## 🏠 方案1：现代简约风格
**设计理念**：简洁、实用、现代感
**色彩搭配**：主色调-白色和浅灰，辅助色-木色，点缀色-深蓝
**家具选择**：简约沙发、茶几、电视柜，宜家或无印良品风格
**装饰元素**：绿植、简约挂画、几何图案抱枕
**功能优化**：隐藏式收纳、LED灯带、智能家居
**预算估算**：总计15000-20000元
**实施步骤**：1.墙面重刷 2.家具更换 3.软装搭配
**预期效果**：清爽明亮，空间感增强30%

## 🌿 方案2：北欧自然风格
**设计理念**：自然、温馨、简约
**色彩搭配**：主色调-白色和米色，辅助色-原木色，点缀色-绿色
**家具选择**：实木家具、羊毛地毯、藤编收纳篮
**装饰元素**：大型绿植、北欧风挂画、毛绒抱枕
**功能优化**：自然采光最大化、木质收纳系统
**预算估算**：总计18000-25000元
**实施步骤**：1.地板处理 2.家具选购 3.绿植布置
**预期效果**：温馨自然，居住舒适度提升

## 🏮 方案3：中式现代风格
**设计理念**：传统与现代结合，雅致韵味
**色彩搭配**：主色调-暖白和浅木色，辅助色-中国红，点缀色-墨绿
**家具选择**：现代中式家具、实木茶桌、布艺沙发
**装饰元素**：中式屏风、字画、青瓷装饰
**功能优化**：茶室功能区、中式收纳系统
**预算估算**：总计25000-35000元
**实施步骤**：1.色彩调整 2.家具定制 3.文化元素添加
**预期效果**：文化底蕴深厚，彰显个人品味

## 🎨 方案4：工业复古风格
**设计理念**：个性、复古、实用主义
**色彩搭配**：主色调-灰色和黑色，辅助色-金属色，点缀色-橙色
**家具选择**：铁艺家具、皮质沙发、复古装饰
**装饰元素**：工业风灯具、金属装饰、复古海报
**功能优化**：开放式收纳、工业风照明系统
**预算估算**：总计20000-28000元
**实施步骤**：1.管线外露处理 2.金属元素添加 3.复古装饰
**预期效果**：个性鲜明，彰显独特生活态度
            """,
            "processing_time": self.mock_delay,
            "cost_estimate": 0.08,
            "model_used": "mock_gpt4o"
        }
    
    async def generate_renovation_image(self, renovation_plan: str, style_name: str) -> Dict:
        """模拟图片生成"""
        await asyncio.sleep(self.mock_delay * 2)  # 图片生成耗时更长
        self.call_count += 1
        
        # 模拟本地保存路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mock_image_path = f"Comments_Dynamic/generated_images/{style_name}_{timestamp}.png"
        
        return {
            "success": True,
            "image_url": f"https://mock-generated-image.com/{style_name}_{timestamp}.png",
            "local_path": mock_image_path,
            "style": style_name,
            "generation_time": self.mock_delay * 2,
            "cost_estimate": 0.08,
            "model_used": "mock_dalle3"
        }
    
    async def create_before_after_comparison(self, original_image: str, generated_image: str) -> Dict:
        """模拟对比图创建"""
        await asyncio.sleep(self.mock_delay)
        self.call_count += 1
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        comparison_path = f"Comments_Dynamic/generated_images/comparison_{timestamp}.png"
        
        return {
            "success": True,
            "comparison_image_url": f"https://mock-comparison.com/comparison_{timestamp}.png",
            "local_path": comparison_path,
            "processing_time": self.mock_delay,
            "cost_estimate": 0.03,
            "model_used": "mock_gpt4o"
        }
    
    async def generate_professional_reply(self, original_comment: str, analysis: str, plans: str) -> Dict:
        """模拟专业回复生成"""
        await asyncio.sleep(self.mock_delay)
        self.call_count += 1
        
        return {
            "success": True,
            "replies": """
## 版本1：详细专业版
亲爱的！看了你分享的图片，这个空间确实很有改造潜力呢！🏠 根据专业分析，你的客厅属于标准户型，采光条件不错，主要问题在于空间利用率和风格统一性。

我为你设计了4个改造方案：现代简约最适合你的需求，预算控制在2万以内就能实现很好的效果。重点是优化收纳系统和色彩搭配，可以让空间感增强30%！具体的家具清单和实施步骤我都帮你整理好了，如果需要详细的购买链接和施工建议，可以私信我哦！✨

## 版本2：简洁实用版
看了你的图片，空间基础很好！💪 建议你选择现代简约风格改造，主要更换家具和调整色彩搭配，预算2万左右就能搞定。重点是增加隐藏收纳和优化布局，效果会很棒的！需要具体的改造清单可以联系我～

## 版本3：互动引导版
哇，你的房子好有潜力！😍 我刚刚用AI帮你生成了4个改造方案的效果图，每种风格都有不同的魅力呢！你比较偏向哪种风格？我可以针对你的喜好提供更详细的改造指导和产品推荐。

另外，我这边有很多成功改造案例，如果你想看更多参考，记得关注我哦！后续改造过程中有任何问题都可以随时咨询～ 🤝
            """,
            "processing_time": self.mock_delay,
            "cost_estimate": 0.05,
            "model_used": "mock_gpt4o"
        }


class IntelligentReplyGenerator:
    """智能回复生成器核心类"""
    
    def __init__(self, work_path: str = "Comments_Dynamic", preferred_model: str = None):
        # 使用新的AI模型管理器
        self.ai_manager = AIModelManager()
        self.preferred_model = preferred_model
        
        self.work_path = Path(work_path)
        self.reply_history_path = self.work_path / "intelligent_replies"
        self.reply_history_path.mkdir(parents=True, exist_ok=True)
        
        # 家居改造专业配置
        self.renovation_styles = [
            "现代简约", "北欧自然", "中式现代", "工业复古"
        ]
        
        # 成本控制
        self.daily_budget = 50.0  # 每日预算
        self.current_daily_cost = 0.0
        self.last_cost_reset = datetime.now().date()
        
    def reset_daily_cost_if_needed(self):
        """如果是新的一天，重置成本计算"""
        today = datetime.now().date()
        if today > self.last_cost_reset:
            self.current_daily_cost = 0.0
            self.last_cost_reset = today
    
    def can_afford_operation(self, estimated_cost: float) -> bool:
        """检查是否在预算范围内"""
        self.reset_daily_cost_if_needed()
        return (self.current_daily_cost + estimated_cost) <= self.daily_budget
    
    def add_cost(self, cost: float):
        """添加成本记录"""
        self.reset_daily_cost_if_needed()
        self.current_daily_cost += cost
    
    async def analyze_comment_for_renovation(self, comment_data: Dict) -> Dict:
        """分析评论是否适合家居改造处理"""
        content = comment_data.get('content', '').lower()
        images = comment_data.get('downloaded_images', [])
        
        # 家居改造关键词
        renovation_keywords = [
            '改造', '装修', '设计', '房间', '客厅', '卧室', '厨房', '卫生间',
            '收纳', '空间', '风格', '家具', '布局', '色彩', '搭配',
            '出租屋', '小户型', '预算', 'diy'
        ]
        
        # 计算匹配分数
        keyword_matches = sum(1 for keyword in renovation_keywords if keyword in content)
        has_room_images = len(images) > 0
        
        renovation_score = keyword_matches * 10
        if has_room_images:
            renovation_score += 30
        
        # 分类评论类型
        if renovation_score >= 40:
            comment_type = "high_priority_renovation"
        elif renovation_score >= 20:
            comment_type = "potential_renovation"
        elif has_room_images:
            comment_type = "image_consultation"
        else:
            comment_type = "general_inquiry"
        
        return {
            "comment_type": comment_type,
            "renovation_score": renovation_score,
            "keyword_matches": keyword_matches,
            "has_images": has_room_images,
            "image_count": len(images),
            "processing_priority": "high" if renovation_score >= 40 else "medium" if renovation_score >= 20 else "low"
        }
    
    async def process_renovation_request(self, comment_data: Dict, 
                                       generate_images: bool = True,
                                       styles_to_generate: List[str] = None) -> Dict:
        """处理家居改造请求的完整流程"""
        
        # 估算成本
        estimated_cost = 0.5 if generate_images else 0.2
        if not self.can_afford_operation(estimated_cost):
            return {
                "success": False,
                "error": "今日预算已用完，请明天再试",
                "daily_cost_used": self.current_daily_cost,
                "daily_budget": self.daily_budget
            }
        
        project_id = self.generate_project_id(comment_data)
        processing_result = {
            "project_id": project_id,
            "timestamp": datetime.now().isoformat(),
            "comment_data": comment_data,
            "processing_stages": {},
            "total_cost": 0.0,
            "success": True
        }
        
        try:
            # 阶段1：分析评论和图片
            print(f"🔍 正在分析评论和房屋图片...")
            
            # 获取第一张图片作为主要分析对象
            main_image = None
            if comment_data.get('downloaded_images'):
                main_image = comment_data['downloaded_images'][0]
            
            if main_image and Path(main_image).exists():
                # 使用AI模型管理器进行图片分析
                analysis_request = TaskRequest(
                    task_id=f"{project_id}_analysis",
                    task_type=TaskType.IMAGE_ANALYSIS,
                    prompt=f"""
                    作为专业室内设计师，请对用户提供的房屋图片进行全面分析。
                    
                    用户需求：{comment_data.get('content', '')}
                    
                    请按以下格式进行详细分析：
                    ## 1. 空间基本信息
                    ## 2. 现状问题诊断  
                    ## 3. 改造潜力评估
                    ## 4. 用户需求匹配度
                    """,
                    image_paths=[main_image]
                )
                analysis_result_obj = await self.ai_manager.process_task(analysis_request, self.preferred_model)
                
                if analysis_result_obj.success:
                    analysis_result = {
                        "success": True,
                        "analysis": analysis_result_obj.result.get("analysis", str(analysis_result_obj.result)),
                        "cost_estimate": analysis_result_obj.cost_estimate
                    }
                else:
                    analysis_result = {
                        "success": False,
                        "error": analysis_result_obj.error
                    }
            else:
                # 仅基于文字内容分析
                text_analysis_request = TaskRequest(
                    task_id=f"{project_id}_text_analysis",
                    task_type=TaskType.TEXT_GENERATION,
                    prompt=f"""
                    基于用户的改造需求描述，提供专业的家居改造分析：
                    
                    用户需求：{comment_data.get('content', '')}
                    
                    请分析房屋类型、改造重点、预算建议等方面。
                    """
                )
                analysis_result_obj = await self.ai_manager.process_task(text_analysis_request, self.preferred_model)
                
                if analysis_result_obj.success:
                    analysis_result = {
                        "success": True,
                        "analysis": analysis_result_obj.result.get("generated_text", str(analysis_result_obj.result)),
                        "cost_estimate": analysis_result_obj.cost_estimate
                    }
                else:
                    analysis_result = {
                        "success": False,
                        "error": analysis_result_obj.error
                    }
            
            if not analysis_result["success"]:
                return {"success": False, "error": "房屋分析失败", "details": analysis_result}
            
            processing_result["processing_stages"]["analysis"] = analysis_result
            processing_result["total_cost"] += analysis_result.get("cost_estimate", 0)
            
            # 阶段2：生成改造方案
            print(f"🏗️ 正在生成改造方案...")
            plans_request = TaskRequest(
                task_id=f"{project_id}_plans",
                task_type=TaskType.TEXT_GENERATION,
                prompt=f"""
                基于以下房屋分析结果，请设计4个不同风格的改造方案：

                【房屋分析结果】
                {analysis_result["analysis"]}

                【用户具体需求】
                {comment_data.get('content', '')}

                请为每个风格设计完整的改造方案，包括：现代简约、北欧自然、中式现代、工业复古风格。
                每个方案要包含设计理念、色彩搭配、家具选择、预算估算等详细信息。
                """
            )
            plans_result_obj = await self.ai_manager.process_task(plans_request, self.preferred_model)
            
            if plans_result_obj.success:
                plans_result = {
                    "success": True,
                    "renovation_plans": plans_result_obj.result.get("generated_text", str(plans_result_obj.result)),
                    "cost_estimate": plans_result_obj.cost_estimate
                }
            else:
                plans_result = {
                    "success": False,
                    "error": plans_result_obj.error
                }
            
            if not plans_result["success"]:
                return {"success": False, "error": "改造方案生成失败", "details": plans_result}
            
            processing_result["processing_stages"]["renovation_planning"] = plans_result
            processing_result["total_cost"] += plans_result.get("cost_estimate", 0)
            
            # 阶段3：生成效果图（可选）
            generated_images = []
            if generate_images:
                print(f"🎨 正在生成改造效果图...")
                styles = styles_to_generate or self.renovation_styles
                
                for style in styles:
                    print(f"   正在生成{style}风格效果图...")
                    
                    # 生成效果图
                    image_request = TaskRequest(
                        task_id=f"{project_id}_{style}_image",
                        task_type=TaskType.IMAGE_GENERATION,
                        prompt=f"""
                        请根据以下改造方案生成专业的室内设计效果图：
                        
                        风格：{style}
                        改造方案：{plans_result["renovation_plans"]}
                        原房间描述：{analysis_result["analysis"]}
                        
                        要求：专业室内设计渲染图，高质量，体现{style}风格特点。
                        """,
                        parameters={"style": style}
                    )
                    image_result_obj = await self.ai_manager.process_task(image_request, self.preferred_model)
                    
                    if image_result_obj.success:
                        image_result = {
                            "success": True,
                            "image_url": image_result_obj.result.get("image_url", ""),
                            "local_path": image_result_obj.result.get("local_path", ""),
                            "style": style,
                            "cost_estimate": image_result_obj.cost_estimate
                        }
                        processing_result["total_cost"] += image_result_obj.cost_estimate
                    else:
                        image_result = {
                            "success": False,
                            "error": image_result_obj.error,
                            "style": style
                        }
                    
                    generated_images.append(image_result)
                    
                    # 生成对比图
                    if image_result["success"] and main_image and Path(main_image).exists():
                        comparison_request = TaskRequest(
                            task_id=f"{project_id}_{style}_comparison",
                            task_type=TaskType.COMPARISON_CREATION,
                            prompt=f"""
                            请创建{style}风格的改造前后对比图。
                            突出关键改造变化点，专业布局。
                            """,
                            image_paths=[main_image, image_result.get("local_path", "")]
                        )
                        comparison_result_obj = await self.ai_manager.process_task(comparison_request, self.preferred_model)
                        
                        if comparison_result_obj.success:
                            comparison_result = {
                                "success": True,
                                "comparison_image_url": comparison_result_obj.result.get("comparison_url", ""),
                                "local_path": comparison_result_obj.result.get("local_path", ""),
                                "style": style,
                                "cost_estimate": comparison_result_obj.cost_estimate
                            }
                            processing_result["total_cost"] += comparison_result_obj.cost_estimate
                        else:
                            comparison_result = {
                                "success": False,
                                "error": comparison_result_obj.error,
                                "style": style
                            }
                        
                        generated_images.append(comparison_result)
            
            processing_result["processing_stages"]["image_generation"] = generated_images
            
            # 阶段4：生成智能回复
            print(f"💬 正在生成智能回复...")
            reply_request = TaskRequest(
                task_id=f"{project_id}_reply",
                task_type=TaskType.TEXT_GENERATION,
                prompt=f"""
                作为小红书家居博主，请为用户的改造需求生成专业回复：

                【用户原评论】
                {comment_data.get('content', '')}

                【专业分析结果】
                {analysis_result["analysis"]}

                【改造方案】
                {plans_result["renovation_plans"]}

                【生成的效果图】
                已为您生成了以下风格的改造效果图：{', '.join([img.get('style', '') for img in generated_images if img.get('success')])}

                请生成3个不同版本的回复：
                1. 详细专业版（200-300字）
                2. 简洁实用版（100-150字）  
                3. 互动引导版（150-200字）

                要求语言亲和友好，体现专业性，适当引导用户互动。
                """
            )
            reply_result_obj = await self.ai_manager.process_task(reply_request, self.preferred_model)
            
            if reply_result_obj.success:
                reply_result = {
                    "success": True,
                    "replies": reply_result_obj.result.get("generated_text", str(reply_result_obj.result)),
                    "cost_estimate": reply_result_obj.cost_estimate
                }
                processing_result["total_cost"] += reply_result_obj.cost_estimate
            else:
                reply_result = {
                    "success": False,
                    "error": reply_result_obj.error
                }
            
            processing_result["processing_stages"]["reply_generation"] = reply_result
            if reply_result["success"]:
                processing_result["total_cost"] += reply_result.get("cost_estimate", 0)
            
            # 记录成本
            self.add_cost(processing_result["total_cost"])
            
            # 保存处理结果
            await self.save_processing_result(processing_result)
            
            return processing_result
            
        except Exception as e:
            processing_result["success"] = False
            processing_result["error"] = f"处理异常: {str(e)}"
            return processing_result
    
    def generate_project_id(self, comment_data: Dict) -> str:
        """生成项目ID"""
        unique_str = f"{comment_data.get('nickname', 'unknown')}_{comment_data.get('time', '')}_{datetime.now().isoformat()}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    async def save_processing_result(self, result: Dict):
        """保存处理结果"""
        project_id = result["project_id"]
        save_path = self.reply_history_path / f"{project_id}_result.json"
        
        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    async def load_processing_result(self, project_id: str) -> Optional[Dict]:
        """加载处理结果"""
        save_path = self.reply_history_path / f"{project_id}_result.json"
        
        if save_path.exists():
            with open(save_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def get_processing_history(self, limit: int = 50) -> List[Dict]:
        """获取处理历史"""
        history_files = sorted(
            self.reply_history_path.glob("*_result.json"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        history = []
        for file_path in history_files[:limit]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    history.append({
                        "project_id": result["project_id"],
                        "timestamp": result["timestamp"],
                        "user_nickname": result["comment_data"].get("nickname", "未知"),
                        "comment_preview": result["comment_data"].get("content", "")[:50] + "...",
                        "total_cost": result["total_cost"],
                        "success": result["success"]
                    })
            except Exception as e:
                print(f"读取历史记录失败 {file_path}: {e}")
                continue
        
        return history
    
    def get_daily_statistics(self) -> Dict:
        """获取每日统计"""
        self.reset_daily_cost_if_needed()
        
        return {
            "date": self.last_cost_reset.isoformat(),
            "cost_used": self.current_daily_cost,
            "budget_total": self.daily_budget,
            "budget_remaining": self.daily_budget - self.current_daily_cost,
            "usage_percentage": (self.current_daily_cost / self.daily_budget) * 100
        }


# 工厂函数
def create_intelligent_reply_generator(preferred_model: str = "mock_gpt4o", **kwargs) -> IntelligentReplyGenerator:
    """创建智能回复生成器实例"""
    
    work_path = kwargs.get('work_path', 'Comments_Dynamic')
    
    return IntelligentReplyGenerator(
        work_path=work_path, 
        preferred_model=preferred_model
    )


# 测试函数
async def test_intelligent_reply_generator():
    """测试智能回复生成器"""
    
    # 创建生成器实例
    generator = create_intelligent_reply_generator("mock_gpt4o")
    
    # 模拟评论数据
    test_comment = {
        "nickname": "测试用户",
        "time": "2024-01-01 10:00:00",
        "content": "老家的房子，想改成现代简约风，增加收纳空间，预算2万左右",
        "downloaded_images": [],  # 暂无图片
        "comment_dir": "test_dir"
    }
    
    print("🧪 开始测试智能回复生成器")
    print("="*50)
    
    # 分析评论类型
    analysis = await generator.analyze_comment_for_renovation(test_comment)
    print(f"📊 评论分析结果: {analysis}")
    
    # 处理改造请求
    print(f"\n🚀 开始处理改造请求...")
    result = await generator.process_renovation_request(
        test_comment, 
        generate_images=True,
        styles_to_generate=["现代简约", "北欧自然"]
    )
    
    if result["success"]:
        print(f"✅ 处理成功!")
        print(f"📋 项目ID: {result['project_id']}")
        print(f"💰 总成本: ${result['total_cost']:.4f}")
        print(f"📊 处理阶段: {list(result['processing_stages'].keys())}")
    else:
        print(f"❌ 处理失败: {result.get('error', '未知错误')}")
    
    # 查看统计信息
    stats = generator.get_daily_statistics()
    print(f"\n📈 每日统计: {stats}")
    
    return result


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_intelligent_reply_generator())