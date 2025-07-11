#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书Cookie自动管理器
支持自动获取、保存、验证和刷新Cookie
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from playwright.async_api import async_playwright
from rich.console import Console
import asyncio

try:
    from utils.error_handler import (
        with_error_handling, ErrorContext, NetworkError, BrowserError, 
        FileOperationError, RetryConfig
    )
    from utils.file_operations import safe_file_ops
    from utils.performance_utils import cached_with_ttl, rate_limit_async
    from utils.config_manager import get_browser_config, get_network_config
    UTILS_AVAILABLE = True
except ImportError:
    UTILS_AVAILABLE = False
    # 降级处理
    def with_error_handling(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def cached_with_ttl(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    class ErrorContext:
        def __init__(self, *args, **kwargs):
            pass
    
    class NetworkError(Exception):
        pass
    
    class BrowserError(Exception):
        pass
    
    class FileOperationError(Exception):
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
    
    def get_browser_config():
        class MockConfig:
            headless = True
            user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            viewport_width = 1280
            viewport_height = 720
            timeout = 30000
            scroll_delay = 2000
        return MockConfig()
    
    def get_network_config():
        class MockConfig:
            request_timeout = 30
        return MockConfig()


class CookieManager:
    """Cookie自动管理器"""
    
    def __init__(self, work_path: str = "Comments_Dynamic"):
        """初始化Cookie管理器
        
        Args:
            work_path: 工作目录路径
        """
        self.work_path = Path(work_path)
        self.console = Console()
        
        # Cookie存储文件
        self.cookie_file = self.work_path / "cookie_cache.json"
        self.browser_profile = self.work_path / "browser_profile"
        
        # 确保目录存在
        self.work_path.mkdir(exist_ok=True)
        
        # Cookie缓存
        self._cached_cookie = None
        self._last_check_time = None
    
    @with_error_handling(
        context=ErrorContext("get_cookie_automatically", "cookie_manager"),
        retry_config=RetryConfig(max_attempts=2, base_delay=2.0),
        fallback_value=("", False)
    )
    async def get_cookie_automatically(self) -> Tuple[str, bool]:
        """自动获取Cookie
        
        Returns:
            tuple: (cookie_string, is_newly_obtained)
        """
        # 首先尝试从缓存获取有效Cookie
        cached_cookie = self._load_cached_cookie()
        if cached_cookie and await self._validate_cookie(cached_cookie):
            self.console.print("[green]✓ 使用缓存的有效Cookie[/green]")
            return cached_cookie, False
        
        # 尝试从浏览器会话获取Cookie
        session_cookie = await self._extract_cookie_from_session()
        if session_cookie and await self._validate_cookie(session_cookie):
            self.console.print("[green]✓ 从浏览器会话获取Cookie成功[/green]")
            self._save_cookie_to_cache(session_cookie)
            return session_cookie, True
        
        # 启动交互式Cookie获取
        interactive_cookie = await self._interactive_cookie_acquisition()
        if interactive_cookie and await self._validate_cookie(interactive_cookie):
            self.console.print("[green]✓ 交互式Cookie获取成功[/green]")
            self._save_cookie_to_cache(interactive_cookie)
            return interactive_cookie, True
        
        # 如果所有方法都失败，抛出网络错误
        raise NetworkError(
            "无法获取有效Cookie，请检查网络连接和登录状态",
            context=ErrorContext("cookie_acquisition", "cookie_manager")
        )
    
    @with_error_handling(
        context=ErrorContext("extract_cookie_from_session", "cookie_manager"),
        fallback_value=None
    )
    async def _extract_cookie_from_session(self) -> Optional[str]:
        """从浏览器会话中提取Cookie"""
        browser_config = get_browser_config()
        network_config = get_network_config()
        
        async with async_playwright() as p:
            try:
                # 使用配置中的浏览器设置
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(self.browser_profile),
                    headless=browser_config.headless,
                    viewport={
                        'width': browser_config.viewport_width, 
                        'height': browser_config.viewport_height
                    },
                    user_agent=browser_config.user_agent
                )
                
                page = await context.new_page()
                
                # 检查是否已经登录
                await page.goto(
                    "https://www.xiaohongshu.com", 
                    wait_until='domcontentloaded', 
                    timeout=browser_config.timeout
                )
                await page.wait_for_timeout(browser_config.scroll_delay)
                
                # 检查登录状态
                is_logged_in = await self._check_login_status(page)
                
                if is_logged_in:
                    # 获取Cookie
                    cookies = await context.cookies()
                    cookie_string = self._format_cookies_to_string(cookies)
                    
                    await context.close()
                    return cookie_string
                else:
                    self.console.print("[yellow]检测到未登录状态，需要手动登录[/yellow]")
                    await context.close()
                    return None
                    
            except Exception as e:
                if 'context' in locals():
                    await context.close()
                raise BrowserError(
                    f"浏览器Cookie提取失败: {str(e)}",
                    context=ErrorContext("browser_session", "cookie_manager")
                )
    
    async def _interactive_cookie_acquisition(self) -> Optional[str]:
        """交互式Cookie获取"""
        try:
            self.console.print("\n[blue]🚀 启动交互式Cookie获取...[/blue]")
            self.console.print("[yellow]将打开浏览器，请按以下步骤操作：[/yellow]")
            self.console.print("1. 在打开的浏览器中登录小红书")
            self.console.print("2. 登录成功后，程序会自动检测并获取Cookie")
            self.console.print("3. 请保持浏览器打开，等待自动检测完成")
            
            async with async_playwright() as p:
                # 启动浏览器
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(self.browser_profile),
                    headless=False,
                    viewport={'width': 1280, 'height': 720}
                )
                
                page = await context.new_page()
                
                # 导航到小红书登录页面
                await page.goto("https://www.xiaohongshu.com", wait_until='domcontentloaded')
                
                # 等待用户登录
                login_detected = False
                max_wait_time = 300  # 最多等待5分钟
                check_interval = 5   # 每5秒检查一次
                
                for _ in range(max_wait_time // check_interval):
                    await page.wait_for_timeout(check_interval * 1000)
                    
                    if await self._check_login_status(page):
                        login_detected = True
                        self.console.print("[green]✓ 检测到登录成功！[/green]")
                        break
                    else:
                        self.console.print("[blue]⏳ 等待登录中...[/blue]")
                
                if login_detected:
                    # 获取Cookie
                    cookies = await context.cookies()
                    cookie_string = self._format_cookies_to_string(cookies)
                    
                    await context.close()
                    return cookie_string
                else:
                    self.console.print("[red]❌ 登录超时，请重试[/red]")
                    await context.close()
                    return None
                    
        except Exception as e:
            self.console.print(f"[red]交互式Cookie获取失败: {e}[/red]")
            return None
    
    async def _check_login_status(self, page) -> bool:
        """检查登录状态"""
        try:
            # 方法1：检查是否存在登录用户相关的元素
            login_indicators = [
                '[data-v-*] .user-info',  # 用户信息区域
                '.user-avatar',            # 用户头像
                '.login-box .user',        # 用户框
                '[class*="avatar"]',       # 头像类
            ]
            
            for selector in login_indicators:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        return True
                except:
                    continue
            
            # 方法2：检查URL是否包含用户相关信息
            current_url = page.url
            if any(indicator in current_url for indicator in ['/user/', '/profile/', '/personal']):
                return True
            
            # 方法3：检查Cookie中的关键字段
            cookies = await page.context.cookies()
            key_cookie_names = ['web_session', 'a1', 'webId']
            
            for cookie in cookies:
                if cookie['name'] in key_cookie_names and cookie['value']:
                    return True
            
            # 方法4：检查页面标题
            title = await page.title()
            if title and '登录' not in title and '小红书' in title:
                return True
                
            return False
            
        except Exception as e:
            self.console.print(f"[yellow]登录状态检查失败: {e}[/yellow]")
            return False
    
    def _format_cookies_to_string(self, cookies: List[Dict]) -> str:
        """将Cookie列表格式化为字符串"""
        cookie_pairs = []
        for cookie in cookies:
            cookie_pairs.append(f"{cookie['name']}={cookie['value']}")
        return '; '.join(cookie_pairs)
    
    async def _validate_cookie(self, cookie_string: str) -> bool:
        """验证Cookie是否有效"""
        if not cookie_string:
            return False
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                
                # 解析并设置Cookie
                cookies = self._parse_cookie_string(cookie_string)
                await context.add_cookies(cookies)
                
                page = await context.new_page()
                
                # 尝试访问需要登录的页面
                await page.goto("https://www.xiaohongshu.com", wait_until='domcontentloaded', timeout=10000)
                await page.wait_for_timeout(2000)
                
                # 检查是否成功登录
                is_valid = await self._check_login_status(page)
                
                await browser.close()
                return is_valid
                
        except Exception as e:
            self.console.print(f"[yellow]Cookie验证失败: {e}[/yellow]")
            return False
    
    def _parse_cookie_string(self, cookie_string: str) -> List[Dict]:
        """解析Cookie字符串为Playwright格式"""
        cookies = []
        for item in cookie_string.split(';'):
            if '=' in item:
                name, value = item.strip().split('=', 1)
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': '.xiaohongshu.com',
                    'path': '/'
                })
        return cookies
    
    @cached_with_ttl(ttl=86400, max_size=1)  # 24小时TTL缓存
    def _load_cached_cookie(self) -> Optional[str]:
        """从缓存加载Cookie"""
        cache_data = safe_file_ops.read_json_safe(self.cookie_file)
        if not cache_data:
            return None
        
        # 检查Cookie是否过期
        try:
            saved_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
            if datetime.now() - saved_time > timedelta(hours=24):  # 24小时过期
                self.console.print("[yellow]缓存Cookie已过期[/yellow]")
                return None
        except (ValueError, TypeError):
            return None
        
        return cache_data.get('cookie', '')
    
    @with_error_handling(
        context=ErrorContext("save_cookie_to_cache", "cookie_manager")
    )
    def _save_cookie_to_cache(self, cookie_string: str) -> bool:
        """保存Cookie到缓存"""
        browser_config = get_browser_config()
        
        cache_data = {
            'cookie': cookie_string,
            'timestamp': datetime.now().isoformat(),
            'user_agent': browser_config.user_agent
        }
        
        success = safe_file_ops.write_json_safe(self.cookie_file, cache_data)
        if success:
            self.console.print(f"[green]✓ Cookie已保存到缓存[/green]")
            # 清理缓存
            self._load_cached_cookie.cache_clear()
        return success
    
    async def refresh_cookie_if_needed(self) -> Tuple[str, bool]:
        """根据需要刷新Cookie"""
        # 检查是否需要刷新（每小时检查一次）
        current_time = time.time()
        if (self._last_check_time and 
            current_time - self._last_check_time < 3600):  # 1小时
            if self._cached_cookie:
                return self._cached_cookie, False
        
        # 获取最新Cookie
        cookie, is_new = await self.get_cookie_automatically()
        
        # 更新缓存
        self._cached_cookie = cookie
        self._last_check_time = current_time
        
        return cookie, is_new
    
    def clear_cache(self):
        """清理Cookie缓存"""
        try:
            if self.cookie_file.exists():
                self.cookie_file.unlink()
                self.console.print("[green]✓ Cookie缓存已清理[/green]")
            
            self._cached_cookie = None
            self._last_check_time = None
            
        except Exception as e:
            self.console.print(f"[yellow]清理Cookie缓存失败: {e}[/yellow]")


# 测试函数
async def test_cookie_manager():
    """测试Cookie管理器"""
    manager = CookieManager()
    
    print("🧪 测试Cookie自动获取...")
    cookie, is_new = await manager.get_cookie_automatically()
    
    if cookie:
        print(f"✅ Cookie获取成功: {cookie[:50]}...")
        print(f"是否为新获取: {is_new}")
        
        # 测试Cookie验证
        print("\n🧪 测试Cookie验证...")
        is_valid = await manager._validate_cookie(cookie)
        print(f"Cookie有效性: {is_valid}")
        
    else:
        print("❌ Cookie获取失败")


if __name__ == "__main__":
    asyncio.run(test_cookie_manager())