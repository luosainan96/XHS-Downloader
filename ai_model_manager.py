#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI模型管理器
统一管理不同AI服务的接口和调用
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import hashlib


class ModelType(Enum):
    """AI模型类型"""
    MOCK = "mock"                    # 模拟模型
    GPT_88_WEB = "88gpt_web"        # 88gpt.vip 网页版
    GPT_88_API = "88gpt_api"        # 88gpt.vip API版（如果有）
    OPENAI_API = "openai_api"       # OpenAI 官方API
    CLAUDE_API = "claude_api"       # Claude API
    LOCAL_MODEL = "local_model"     # 本地模型


class TaskType(Enum):
    """任务类型"""
    IMAGE_ANALYSIS = "image_analysis"           # 图片分析
    TEXT_GENERATION = "text_generation"         # 文本生成
    IMAGE_GENERATION = "image_generation"       # 图片生成
    COMPARISON_CREATION = "comparison_creation" # 对比图创建


@dataclass
class ModelCapability:
    """模型能力描述"""
    can_analyze_images: bool = False
    can_generate_text: bool = False
    can_generate_images: bool = False
    can_create_comparisons: bool = False
    max_image_size: int = 20971520  # 20MB
    max_tokens: int = 4096
    cost_per_request: float = 0.0
    requests_per_hour: int = 1000
    supports_batch: bool = False


@dataclass
class ModelConfig:
    """模型配置"""
    model_type: ModelType
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    capabilities: Optional[ModelCapability] = None
    priority: int = 1  # 优先级，1最高
    enabled: bool = True
    timeout: int = 300
    max_retries: int = 3


@dataclass
class TaskRequest:
    """任务请求"""
    task_id: str
    task_type: TaskType
    prompt: str
    image_paths: List[str] = None
    parameters: Dict[str, Any] = None
    priority: int = 1
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.image_paths is None:
            self.image_paths = []
        if self.parameters is None:
            self.parameters = {}


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    success: bool
    result: Any = None
    error: str = None
    model_used: str = None
    processing_time: float = 0.0
    cost_estimate: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class BaseAIModel(ABC):
    """AI模型基类"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.request_count = 0
        self.total_cost = 0.0
        self.last_request_time = None
        self.error_count = 0
        
    @abstractmethod
    async def process_task(self, request: TaskRequest) -> TaskResult:
        """处理任务"""
        pass
    
    def can_handle_task(self, task_type: TaskType) -> bool:
        """检查是否能处理指定类型的任务"""
        if not self.config.capabilities:
            return False
            
        capability_map = {
            TaskType.IMAGE_ANALYSIS: self.config.capabilities.can_analyze_images,
            TaskType.TEXT_GENERATION: self.config.capabilities.can_generate_text,
            TaskType.IMAGE_GENERATION: self.config.capabilities.can_generate_images,
            TaskType.COMPARISON_CREATION: self.config.capabilities.can_create_comparisons
        }
        
        return capability_map.get(task_type, False)
    
    def update_stats(self, processing_time: float, cost: float, success: bool):
        """更新统计信息"""
        self.request_count += 1
        self.total_cost += cost
        self.last_request_time = datetime.now()
        if not success:
            self.error_count += 1
    
    def get_health_score(self) -> float:
        """获取健康评分 (0-1)"""
        if self.request_count == 0:
            return 1.0
        
        error_rate = self.error_count / self.request_count
        health_score = max(0.0, 1.0 - error_rate)
        
        # 如果最近没有请求，稍微降低评分
        if self.last_request_time:
            time_since_last = datetime.now() - self.last_request_time
            if time_since_last > timedelta(hours=1):
                health_score *= 0.9
        
        return health_score


class MockAIModel(BaseAIModel):
    """模拟AI模型 - 用于开发测试"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.mock_delay = 2
        
        # 设置默认能力
        if not config.capabilities:
            config.capabilities = ModelCapability(
                can_analyze_images=True,
                can_generate_text=True,
                can_generate_images=True,
                can_create_comparisons=True,
                cost_per_request=0.05
            )
    
    async def process_task(self, request: TaskRequest) -> TaskResult:
        """处理模拟任务"""
        start_time = time.time()
        
        try:
            # 模拟处理时间
            await asyncio.sleep(self.mock_delay)
            
            if request.task_type == TaskType.IMAGE_ANALYSIS:
                result = self._mock_image_analysis(request)
            elif request.task_type == TaskType.TEXT_GENERATION:
                result = self._mock_text_generation(request)
            elif request.task_type == TaskType.IMAGE_GENERATION:
                result = self._mock_image_generation(request)
            elif request.task_type == TaskType.COMPARISON_CREATION:
                result = self._mock_comparison_creation(request)
            else:
                raise ValueError(f"不支持的任务类型: {request.task_type}")
            
            processing_time = time.time() - start_time
            cost = self.config.capabilities.cost_per_request
            
            self.update_stats(processing_time, cost, True)
            
            return TaskResult(
                task_id=request.task_id,
                success=True,
                result=result,
                model_used=self.config.model_name,
                processing_time=processing_time,
                cost_estimate=cost
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.update_stats(processing_time, 0, False)
            
            return TaskResult(
                task_id=request.task_id,
                success=False,
                error=str(e),
                model_used=self.config.model_name,
                processing_time=processing_time
            )
    
    def _mock_image_analysis(self, request: TaskRequest) -> Dict:
        """模拟图片分析"""
        return {
            "analysis": f"""
## 房屋分析结果 (模拟)

基于用户提示：{request.prompt[:100]}...

### 空间基本信息
- 房间类型：客厅
- 估算面积：25平方米
- 采光条件：良好
- 现有风格：简约现代

### 改造建议
- 优化空间布局
- 增加收纳功能
- 调整色彩搭配
- 提升整体美观度

### 预算估算
- 经济型改造：1-2万元
- 标准型改造：2-3万元
- 豪华型改造：3-5万元
            """,
            "confidence": 0.85,
            "detected_objects": ["沙发", "茶几", "电视", "窗帘"],
            "room_type": "客厅",
            "estimated_area": 25
        }
    
    def _mock_text_generation(self, request: TaskRequest) -> Dict:
        """模拟文本生成"""
        return {
            "generated_text": f"""
## 🏠 专业改造建议

根据您的需求：{request.prompt[:50]}...

### 方案一：现代简约风格
- **设计理念**：简洁、实用、现代
- **色彩搭配**：白色主调，木色点缀
- **家具建议**：宜家简约系列
- **预算范围**：15000-20000元

### 方案二：北欧自然风格
- **设计理念**：自然、温馨、舒适
- **色彩搭配**：米白色，原木色
- **家具建议**：实木家具，绿植装饰
- **预算范围**：18000-25000元

### 实施建议
1. 优先处理功能性问题
2. 其次考虑美观性提升
3. 最后进行细节优化

希望这些建议对您有帮助！如需更详细的方案，欢迎进一步咨询～
            """,
            "word_count": 200,
            "sentiment": "积极",
            "style": "专业友好"
        }
    
    def _mock_image_generation(self, request: TaskRequest) -> Dict:
        """模拟图片生成"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mock_path = f"Comments_Dynamic/generated_images/mock_{timestamp}.png"
        
        return {
            "image_url": f"https://mock-image-service.com/generated_{timestamp}.png",
            "local_path": mock_path,
            "style": request.parameters.get("style", "现代简约"),
            "resolution": "1024x1024",
            "quality": "high"
        }
    
    def _mock_comparison_creation(self, request: TaskRequest) -> Dict:
        """模拟对比图创建"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        comparison_path = f"Comments_Dynamic/generated_images/comparison_{timestamp}.png"
        
        return {
            "comparison_url": f"https://mock-comparison.com/comparison_{timestamp}.png",
            "local_path": comparison_path,
            "layout": "side_by_side",
            "highlights": ["空间布局变化", "色彩搭配优化", "家具更新"]
        }


class WebAutomationModel(BaseAIModel):
    """网页自动化模型基类 - 用于88gpt.vip等网页版AI服务"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.browser = None
        self.page = None
        self.is_logged_in = False
        self.daily_usage_count = 0
        self.daily_limit = 150  # 88gpt.vip的8小时150次限制
        self.last_reset_time = datetime.now().date()
    
    async def init_browser(self):
        """初始化浏览器"""
        if self.browser is None:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,  # 可以改为False来调试
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.page = await self.browser.new_page()
            
            # 设置用户代理
            await self.page.set_user_agent(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
    
    async def close_browser(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()
            self.browser = None
            self.page = None
    
    def check_daily_limit(self) -> bool:
        """检查每日使用限制"""
        today = datetime.now().date()
        if today > self.last_reset_time:
            self.daily_usage_count = 0
            self.last_reset_time = today
        
        return self.daily_usage_count < self.daily_limit
    
    def update_daily_usage(self):
        """更新每日使用量"""
        self.daily_usage_count += 1


class GPT88WebModel(WebAutomationModel):
    """88gpt.vip 网页版模型"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        
        # 设置能力
        if not config.capabilities:
            config.capabilities = ModelCapability(
                can_analyze_images=True,
                can_generate_text=True,
                can_generate_images=True,
                can_create_comparisons=True,
                cost_per_request=0.0,  # 88gpt按次数计费，不是token
                requests_per_hour=18   # 150次/8小时 ≈ 18次/小时
            )
    
    async def process_task(self, request: TaskRequest) -> TaskResult:
        """处理88gpt.vip任务"""
        start_time = time.time()
        
        try:
            # 检查使用限制
            if not self.check_daily_limit():
                raise Exception("已达到88gpt.vip每日使用限制")
            
            # 初始化浏览器
            await self.init_browser()
            
            # 导航到88gpt.vip
            await self._navigate_to_88gpt()
            
            # 根据任务类型处理
            if request.task_type == TaskType.IMAGE_ANALYSIS:
                result = await self._process_image_analysis(request)
            elif request.task_type == TaskType.TEXT_GENERATION:
                result = await self._process_text_generation(request)
            elif request.task_type == TaskType.IMAGE_GENERATION:
                result = await self._process_image_generation(request)
            else:
                raise ValueError(f"88gpt.vip暂不支持任务类型: {request.task_type}")
            
            # 更新使用统计
            self.update_daily_usage()
            processing_time = time.time() - start_time
            self.update_stats(processing_time, 0, True)
            
            return TaskResult(
                task_id=request.task_id,
                success=True,
                result=result,
                model_used=self.config.model_name,
                processing_time=processing_time,
                cost_estimate=0
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            self.update_stats(processing_time, 0, False)
            
            return TaskResult(
                task_id=request.task_id,
                success=False,
                error=str(e),
                model_used=self.config.model_name,
                processing_time=processing_time
            )
        finally:
            # 关闭浏览器（可选，也可以保持连接）
            # await self.close_browser()
            pass
    
    async def _navigate_to_88gpt(self):
        """导航到88gpt.vip"""
        await self.page.goto("https://www.88gpt.vip/")
        await self.page.wait_for_load_state("networkidle")
        
        # TODO: 如果需要登录，在这里处理登录逻辑
        # await self._login_if_needed()
    
    async def _process_image_analysis(self, request: TaskRequest) -> Dict:
        """处理图片分析任务"""
        # TODO: 实现88gpt.vip的图片分析
        # 1. 上传图片
        # 2. 发送分析提示词
        # 3. 等待响应
        # 4. 解析结果
        
        # 占位符实现
        await asyncio.sleep(5)  # 模拟处理时间
        
        return {
            "analysis": f"88gpt.vip分析结果：{request.prompt}",
            "source": "88gpt.vip",
            "model": "gpt-4o"
        }
    
    async def _process_text_generation(self, request: TaskRequest) -> Dict:
        """处理文本生成任务"""
        # TODO: 实现88gpt.vip的文本生成
        # 1. 输入提示词
        # 2. 点击发送
        # 3. 等待响应
        # 4. 提取生成的文本
        
        # 占位符实现
        await asyncio.sleep(3)
        
        return {
            "generated_text": f"88gpt.vip生成：{request.prompt[:50]}...",
            "source": "88gpt.vip",
            "model": "gpt-4o"
        }
    
    async def _process_image_generation(self, request: TaskRequest) -> Dict:
        """处理图片生成任务"""
        # TODO: 实现88gpt.vip的图片生成
        # 1. 切换到图片生成模式
        # 2. 输入图片描述
        # 3. 等待图片生成
        # 4. 下载图片
        
        # 占位符实现
        await asyncio.sleep(10)
        
        return {
            "image_url": "https://88gpt.vip/generated_image.png",
            "local_path": "Comments_Dynamic/generated_images/88gpt_image.png",
            "source": "88gpt.vip",
            "model": "dall-e-3"
        }


class AIModelManager:
    """AI模型管理器"""
    
    def __init__(self, config_path: str = "config/ai_models.json"):
        self.config_path = Path(config_path)
        self.models: Dict[str, BaseAIModel] = {}
        self.task_queue = asyncio.Queue()
        self.processing_tasks = {}
        self.history_path = Path("Comments_Dynamic/ai_model_history")
        self.history_path.mkdir(parents=True, exist_ok=True)
        
        # 加载模型配置
        self.load_model_configs()
    
    def load_model_configs(self):
        """加载模型配置"""
        # 默认配置
        default_configs = [
            ModelConfig(
                model_type=ModelType.MOCK,
                model_name="mock_gpt4o",
                capabilities=ModelCapability(
                    can_analyze_images=True,
                    can_generate_text=True,
                    can_generate_images=True,
                    can_create_comparisons=True,
                    cost_per_request=0.05
                ),
                priority=2,
                enabled=True
            ),
            ModelConfig(
                model_type=ModelType.GPT_88_WEB,
                model_name="88gpt_web_gpt4o",
                base_url="https://www.88gpt.vip/",
                capabilities=ModelCapability(
                    can_analyze_images=True,
                    can_generate_text=True,
                    can_generate_images=True,
                    can_create_comparisons=True,
                    cost_per_request=0.0,
                    requests_per_hour=18
                ),
                priority=1,
                enabled=False  # 默认禁用，需要手动启用
            )
        ]
        
        # 如果配置文件存在，加载配置
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                # TODO: 解析配置文件并更新default_configs
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        
        # 初始化模型
        for config in default_configs:
            if config.enabled:
                self.register_model(config)
    
    def register_model(self, config: ModelConfig):
        """注册模型"""
        if config.model_type == ModelType.MOCK:
            model = MockAIModel(config)
        elif config.model_type == ModelType.GPT_88_WEB:
            model = GPT88WebModel(config)
        else:
            raise ValueError(f"不支持的模型类型: {config.model_type}")
        
        self.models[config.model_name] = model
        print(f"✅ 注册模型: {config.model_name}")
    
    def get_available_models(self, task_type: TaskType) -> List[BaseAIModel]:
        """获取可用的模型列表"""
        available = []
        for model in self.models.values():
            if (model.config.enabled and 
                model.can_handle_task(task_type) and 
                model.get_health_score() > 0.5):
                available.append(model)
        
        # 按优先级和健康评分排序
        available.sort(key=lambda m: (m.config.priority, -m.get_health_score()))
        return available
    
    def select_best_model(self, task_type: TaskType) -> Optional[BaseAIModel]:
        """选择最佳模型"""
        available_models = self.get_available_models(task_type)
        return available_models[0] if available_models else None
    
    async def process_task(self, request: TaskRequest, 
                          preferred_model: str = None) -> TaskResult:
        """处理任务"""
        
        # 如果指定了首选模型，优先使用
        if preferred_model and preferred_model in self.models:
            model = self.models[preferred_model]
            if model.can_handle_task(request.task_type):
                return await model.process_task(request)
        
        # 自动选择最佳模型
        model = self.select_best_model(request.task_type)
        if not model:
            return TaskResult(
                task_id=request.task_id,
                success=False,
                error=f"没有可用的模型处理任务类型: {request.task_type}"
            )
        
        # 处理任务
        result = await model.process_task(request)
        
        # 保存历史记录
        await self.save_task_history(request, result)
        
        return result
    
    async def save_task_history(self, request: TaskRequest, result: TaskResult):
        """保存任务历史"""
        history_record = {
            "request": {
                "task_id": request.task_id,
                "task_type": request.task_type.value,
                "prompt": request.prompt[:200] + "..." if len(request.prompt) > 200 else request.prompt,
                "timestamp": request.timestamp.isoformat()
            },
            "result": {
                "success": result.success,
                "model_used": result.model_used,
                "processing_time": result.processing_time,
                "cost_estimate": result.cost_estimate,
                "error": result.error,
                "timestamp": result.timestamp.isoformat()
            }
        }
        
        history_file = self.history_path / f"task_{request.task_id}.json"
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_record, f, ensure_ascii=False, indent=2)
    
    def get_model_statistics(self) -> Dict:
        """获取模型统计信息"""
        stats = {}
        for name, model in self.models.items():
            stats[name] = {
                "model_type": model.config.model_type.value,
                "enabled": model.config.enabled,
                "request_count": model.request_count,
                "total_cost": model.total_cost,
                "error_count": model.error_count,
                "health_score": model.get_health_score(),
                "last_request": model.last_request_time.isoformat() if model.last_request_time else None
            }
        return stats
    
    async def enable_model(self, model_name: str):
        """启用模型"""
        if model_name in self.models:
            self.models[model_name].config.enabled = True
            print(f"✅ 启用模型: {model_name}")
        else:
            print(f"❌ 模型不存在: {model_name}")
    
    async def disable_model(self, model_name: str):
        """禁用模型"""
        if model_name in self.models:
            self.models[model_name].config.enabled = False
            print(f"⏸️ 禁用模型: {model_name}")
        else:
            print(f"❌ 模型不存在: {model_name}")


# 测试函数
async def test_ai_model_manager():
    """测试AI模型管理器"""
    
    manager = AIModelManager()
    
    print("🧪 开始测试AI模型管理器")
    print("="*50)
    
    # 显示可用模型
    print("📋 可用模型:")
    stats = manager.get_model_statistics()
    for name, stat in stats.items():
        print(f"   {name}: {stat['model_type']} - {'启用' if stat['enabled'] else '禁用'}")
    
    # 测试不同类型的任务
    test_tasks = [
        TaskRequest(
            task_id="test_1",
            task_type=TaskType.IMAGE_ANALYSIS,
            prompt="请分析这个客厅的改造潜力",
            image_paths=["test_room.jpg"]
        ),
        TaskRequest(
            task_id="test_2",
            task_type=TaskType.TEXT_GENERATION,
            prompt="为用户生成客厅改造建议"
        ),
        TaskRequest(
            task_id="test_3",
            task_type=TaskType.IMAGE_GENERATION,
            prompt="生成现代简约风格的客厅效果图",
            parameters={"style": "现代简约"}
        )
    ]
    
    # 处理测试任务
    for task in test_tasks:
        print(f"\n🔄 处理任务: {task.task_type.value}")
        result = await manager.process_task(task)
        
        if result.success:
            print(f"   ✅ 成功 - 模型: {result.model_used}")
            print(f"   ⏱️ 耗时: {result.processing_time:.2f}秒")
            print(f"   💰 成本: ${result.cost_estimate:.4f}")
        else:
            print(f"   ❌ 失败: {result.error}")
    
    # 显示更新后的统计信息
    print(f"\n📈 模型统计:")
    updated_stats = manager.get_model_statistics()
    for name, stat in updated_stats.items():
        if stat['request_count'] > 0:
            print(f"   {name}:")
            print(f"      请求次数: {stat['request_count']}")
            print(f"      健康评分: {stat['health_score']:.2f}")
            print(f"      总成本: ${stat['total_cost']:.4f}")


if __name__ == "__main__":
    asyncio.run(test_ai_model_manager())