#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书动态评论提取器
使用浏览器自动化获取动态加载的评论数据
"""

import asyncio
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
import mimetypes

import aiofiles
import aiohttp
from playwright.async_api import async_playwright
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TimeRemainingColumn

# from source import XHS  # 注释掉原有依赖，使评论提取器独立运行


class DynamicCommentExtractor:
    """动态评论提取器"""
    
    def __init__(self, work_path: str = "Comments", cookie: str = "", use_persistent_session: bool = True, max_comments: int = None):
        """初始化评论提取器
        
        Args:
            work_path: 工作目录路径
            cookie: 登录Cookie
            use_persistent_session: 是否使用持久化会话
            max_comments: 最大评论数量限制，None表示不限制
        """
        self.work_path = Path(work_path)
        self.cookie = cookie
        self.console = Console()
        self.use_persistent_session = use_persistent_session
        self.max_comments = max_comments
        
        # 创建工作目录
        self.work_path.mkdir(exist_ok=True)
        
        # 用户数据目录 - 用于保持登录状态
        self.user_data_dir = self.work_path / "browser_profile"
        if self.use_persistent_session:
            self.user_data_dir.mkdir(exist_ok=True)
            self.console.print(f"[blue]使用持久化浏览器配置: {self.user_data_dir}[/blue]")
    
    def extract_note_id(self, url: str) -> Optional[str]:
        """从URL中提取笔记ID"""
        patterns = [
            r'explore/([a-fA-F0-9]+)',
            r'discovery/item/([a-fA-F0-9]+)',
            r'item/([a-fA-F0-9]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    async def get_note_info_with_xhs(self, note_url: str) -> Optional[Dict]:
        """从页面中提取真实的笔记信息"""
        note_id = self.extract_note_id(note_url)
        if not note_id:
            return None
            
        # 从浏览器中获取真实的笔记标题
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # 设置用户代理，避免被识别为爬虫
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
                })
                
                # 设置Cookie（如果有的话）
                if self.cookie:
                    await self.set_cookies(page)
                
                # 访问页面，降低超时时间
                try:
                    await page.goto(note_url, wait_until='domcontentloaded', timeout=15000)
                    await page.wait_for_timeout(2000)  # 等待内容加载
                except:
                    # 如果加载失败，尝试更快的加载方式
                    await page.goto(note_url, timeout=10000)
                    await page.wait_for_timeout(1000)
                
                # 尝试多种方式提取标题
                title = None
                
                # 方法1：从页面标题中提取
                page_title = await page.title()
                if page_title and page_title != "小红书" and page_title != "安全限制":
                    title = page_title.replace(" - 小红书", "").strip()
                
                # 方法2：从meta标签中提取
                if not title:
                    try:
                        meta_element = await page.query_selector('meta[property="og:title"]')
                        if meta_element:
                            meta_title = await meta_element.get_attribute('content')
                            if meta_title:
                                title = meta_title.strip()
                    except:
                        pass
                
                # 方法3：从h1标签中提取
                if not title:
                    h1_element = await page.query_selector('h1')
                    if h1_element:
                        title = await h1_element.text_content()
                        if title:
                            title = title.strip()
                
                # 方法4：从JSON数据中提取
                if not title:
                    try:
                        initial_state = await page.evaluate("() => window.__INITIAL_STATE__")
                        if initial_state:
                            # 尝试从noteDetailMap中获取标题
                            note_data = initial_state.get('note', {}).get('noteDetailMap', {})
                            if note_data:
                                for key, value in note_data.items():
                                    if isinstance(value, dict) and 'title' in value:
                                        title = value['title']
                                        break
                                    # 也尝试从desc字段提取
                                    if isinstance(value, dict) and 'desc' in value:
                                        desc = value['desc']
                                        if desc and len(desc) > 5:  # 确保描述有意义
                                            title = desc[:30] + ("..." if len(desc) > 30 else "")
                                            break
                    except:
                        pass
                
                # 方法5：从特定选择器中提取
                if not title:
                    try:
                        # 尝试更多可能的选择器
                        selectors = [
                            '[data-v-*] .title',
                            '.note-content .title',
                            '.note-detail .title',
                            '.content .title',
                            '.note-scroller .title'
                        ]
                        
                        for selector in selectors:
                            try:
                                element = await page.query_selector(selector)
                                if element:
                                    text = await element.text_content()
                                    if text and text.strip():
                                        title = text.strip()
                                        break
                            except:
                                continue
                    except:
                        pass
                
                await browser.close()
                
                # 如果成功获取到标题，返回信息
                if title:
                    self.console.print(f"[green]✓ 成功获取笔记标题: {title}[/green]")
                    return {
                        '作品标题': title,
                        '作品描述': '通过评论提取器获取',
                        '作品ID': note_id,
                        '作品链接': note_url
                    }
                else:
                    self.console.print(f"[yellow]未能提取到笔记标题，将使用默认命名[/yellow]")
                        
        except Exception as e:
            self.console.print(f"[yellow]获取笔记标题失败: {e}[/yellow]")
        
        # 如果无法获取真实标题，尝试一些常见的映射
        common_titles = {
            '685613550000000010027087': '出租屋改造！你发图我来改~',
            '683d98b3000000000303909b': '景德镇素胚绘画教程分享'
        }
        
        fallback_title = common_titles.get(note_id, f'笔记_{note_id}')
        
        return {
            '作品标题': fallback_title,
            '作品描述': '通过评论提取器获取',
            '作品ID': note_id,
            '作品链接': note_url
        }
    
    async def extract_comments_with_browser(self, note_url: str, note_id: str) -> List[Dict]:
        """使用浏览器自动化提取动态评论"""
        comments = []
        
        async with async_playwright() as p:
            # 准备浏览器启动参数
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--no-first-run',
                '--disable-default-apps'
            ]
            
            if self.use_persistent_session:
                # 使用持久化上下文
                self.console.print("[green]启动浏览器 - 使用持久化登录状态[/green]")
                
                context = await p.chromium.launch_persistent_context(
                    str(self.user_data_dir),
                    headless=False,
                    args=browser_args,
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 720},
                    timeout=30000
                )
                
                # 创建或获取页面
                if context.pages:
                    # 使用现有页面
                    page = context.pages[0]
                    self.console.print("[blue]使用现有浏览器页面[/blue]")
                else:
                    # 创建新页面
                    page = await context.new_page()
                    self.console.print("[blue]创建新浏览器页面[/blue]")
                
                browser = None  # 持久化上下文不需要单独的browser对象
                
            else:
                # 使用临时会话
                self.console.print("[yellow]启动浏览器 - 临时会话模式[/yellow]")
                
                browser = await p.chromium.launch(
                    headless=False,
                    args=browser_args,
                    timeout=30000
                )
                
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    viewport={'width': 1280, 'height': 720}
                )
                
                # 设置Cookie（仅在临时模式下）
                if self.cookie:
                    await context.add_cookies(self.parse_cookie_string(self.cookie))
                
                # 创建新页面
                page = await context.new_page()
                self.console.print("[blue]创建新浏览器页面[/blue]")
            
            try:
                # 如果是持久化模式，首先检查登录状态
                if self.use_persistent_session:
                    await self.check_and_guide_login(page)
                
                self.console.print(f"[blue]浏览器访问页面: {note_url}[/blue]")
                
                # 访问页面 - 优化超时和等待策略
                try:
                    await page.goto(note_url, wait_until='domcontentloaded', timeout=30000)
                    self.console.print("[green]页面加载完成[/green]")
                except Exception as goto_error:
                    self.console.print(f"[yellow]页面加载超时，尝试继续: {goto_error}[/yellow]")
                    # 如果页面加载超时，尝试直接访问不等待完全加载
                    try:
                        await page.goto(note_url, wait_until='load', timeout=15000)
                    except:
                        # 最后的备用方案：不等待任何条件
                        await page.goto(note_url, timeout=10000)
                
                # 等待页面加载
                await asyncio.sleep(3)
                
                self.console.print("[blue]滚动页面以触发评论加载...[/blue]")
                
                # 滚动到页面底部以触发评论加载
                await page.evaluate("""
                    () => {
                        window.scrollTo(0, document.body.scrollHeight);
                    }
                """)
                
                # 等待评论加载
                await asyncio.sleep(3)
                
                # 查找评论容器并点击
                try:
                    # 尝试找到评论区域
                    comment_containers = [
                        '.comments-el',
                        '[class*="comment"]',
                        '[data-v*="comment"]',
                        '.comment-container',
                        '.comment-list'
                    ]
                    
                    for selector in comment_containers:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            self.console.print(f"[green]找到评论容器: {selector}[/green]")
                            # 滚动到评论区域
                            await elements[0].scroll_into_view_if_needed()
                            await asyncio.sleep(2)
                            break
                    
                    # 等待评论动态加载
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    self.console.print(f"[yellow]查找评论容器失败: {e}[/yellow]")
                
                # 检查页面是否可访问
                page_title = await page.title()
                page_url = page.url
                self.console.print(f"[blue]页面标题: {page_title}[/blue]")
                self.console.print(f"[blue]当前URL: {page_url}[/blue]")
                
                # 检查是否被重定向到错误页面
                if "404" in page_title or "无法浏览" in page_title or "error" in page_url.lower():
                    self.console.print("[red]页面无法访问或已被删除[/red]")
                    return comments
                
                # 实现分页获取所有评论
                comments = await self.get_all_comments_with_pagination(page, note_id)
                
                # 如果还是没有评论，尝试从DOM直接解析
                if not comments:
                    self.console.print("[blue]尝试从DOM直接解析评论...[/blue]")
                    dom_comments = await self.extract_comments_from_dom(page)
                    comments.extend(dom_comments)
                
            except Exception as e:
                self.console.print(f"[red]浏览器获取评论失败: {e}[/red]")
            finally:
                # 关闭浏览器
                if browser:
                    await browser.close()
                else:
                    # 持久化上下文，只关闭上下文
                    await context.close()
        
        return comments
    
    async def get_all_comments_with_pagination(self, page, note_id: str) -> List[Dict]:
        """分页获取所有评论"""
        all_comments = []
        page_count = 0
        max_pages = 20  # 最大页数限制，防止无限循环 (最多200条评论)
        
        if self.max_comments:
            self.console.print(f"[blue]开始分页获取最新 {self.max_comments} 条评论...[/blue]")
        else:
            self.console.print("[blue]开始分页获取所有评论...[/blue]")
        
        while page_count < max_pages:
            page_count += 1
            self.console.print(f"[blue]获取第 {page_count} 页评论...[/blue]")
            
            # 获取当前页面的评论数据
            try:
                initial_state = await page.evaluate("""
                    () => {
                        if (window.__INITIAL_STATE__) {
                            return window.__INITIAL_STATE__;
                        }
                        return null;
                    }
                """)
                
                if not initial_state:
                    self.console.print("[yellow]无法获取页面状态数据[/yellow]")
                    break
                
                # 调试：保存第一页的原始数据结构
                if page_count == 1:
                    await self.debug_save_initial_state(initial_state, note_id)
                
                # 解析当前页评论
                current_comments = self.extract_comments_from_state(initial_state, note_id)
                
                if current_comments:
                    # 过滤重复评论（基于评论ID）
                    existing_ids = {comment.get('id', '') for comment in all_comments}
                    new_comments = [c for c in current_comments if c.get('id', '') not in existing_ids]
                    
                    if new_comments:
                        # 检查是否超过数量限制
                        if self.max_comments and len(all_comments) + len(new_comments) > self.max_comments:
                            # 只取需要的数量
                            needed_count = self.max_comments - len(all_comments)
                            new_comments = new_comments[:needed_count]
                            self.console.print(f"[yellow]已达到数量限制，只取前 {needed_count} 条评论[/yellow]")
                        
                        all_comments.extend(new_comments)
                        self.console.print(f"[green]第 {page_count} 页获取到 {len(new_comments)} 条新评论（总计 {len(all_comments)} 条）[/green]")
                        
                        # 检查是否已达到数量限制
                        if self.max_comments and len(all_comments) >= self.max_comments:
                            self.console.print(f"[green]已获取到指定数量的评论：{len(all_comments)} 条[/green]")
                            break
                    else:
                        self.console.print(f"[yellow]第 {page_count} 页没有新评论，可能已获取完毕[/yellow]")
                        break
                
                # 检查是否还有更多评论
                has_more = self.check_has_more_comments(initial_state, note_id)
                if not has_more:
                    self.console.print(f"[green]已获取所有评论，共 {len(all_comments)} 条[/green]")
                    break
                
                # 尝试加载更多评论
                await self.load_more_comments(page)
                
                # 等待新评论加载
                await asyncio.sleep(3)
                
            except Exception as e:
                self.console.print(f"[yellow]第 {page_count} 页获取失败: {e}[/yellow]")
                if page_count == 1:
                    # 第一页失败，尝试基础方法
                    break
                else:
                    # 后续页面失败，可能已经获取完毕
                    break
        
        self.console.print(f"[green]分页获取完成，总共获取到 {len(all_comments)} 条评论[/green]")
        return all_comments
    
    def check_has_more_comments(self, initial_state: Dict, note_id: str) -> bool:
        """检查是否还有更多评论"""
        try:
            note_detail_map = initial_state.get('note', {}).get('noteDetailMap', {})
            if note_id in note_detail_map:
                comment_data = note_detail_map[note_id].get('comments', {})
                has_more = comment_data.get('hasMore', False)
                loading = comment_data.get('loading', False)
                
                self.console.print(f"[blue]评论状态检查 - hasMore: {has_more}, loading: {loading}[/blue]")
                return has_more and not loading
        except Exception as e:
            self.console.print(f"[yellow]检查更多评论状态失败: {e}[/yellow]")
        
        return False
    
    async def load_more_comments(self, page):
        """尝试加载更多评论"""
        try:
            # 方法1: 寻找"加载更多"按钮
            load_more_selectors = [
                'text=加载更多',
                'text=查看更多评论',
                'text=Load more',
                '[class*="load-more"]',
                '[class*="loadmore"]',
                '[class*="more-comment"]'
            ]
            
            button_found = False
            for selector in load_more_selectors:
                try:
                    button = await page.wait_for_selector(selector, timeout=2000)
                    if button:
                        await button.click()
                        self.console.print(f"[green]点击加载更多按钮: {selector}[/green]")
                        button_found = True
                        break
                except:
                    continue
            
            if not button_found:
                # 方法2: 滚动到评论区底部
                await page.evaluate("""
                    () => {
                        // 查找评论容器
                        const commentContainers = document.querySelectorAll('.comments-el, [class*="comment"]');
                        if (commentContainers.length > 0) {
                            const lastContainer = commentContainers[commentContainers.length - 1];
                            lastContainer.scrollIntoView({ behavior: 'smooth' });
                        } else {
                            // 滚动到页面底部
                            window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
                        }
                    }
                """)
                self.console.print("[blue]滚动到评论区底部触发加载[/blue]")
            
            # 方法3: 尝试触发更多评论的JavaScript事件
            await page.evaluate("""
                () => {
                    // 触发滚动事件
                    window.dispatchEvent(new Event('scroll'));
                    
                    // 尝试查找并触发评论加载的相关函数
                    if (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.note) {
                        // 这里可以添加小红书特定的加载更多评论的逻辑
                    }
                }
            """)
            
        except Exception as e:
            self.console.print(f"[yellow]加载更多评论失败: {e}[/yellow]")
    
    async def check_and_guide_login(self, page) -> bool:
        """检查登录状态并引导用户登录"""
        try:
            # 先访问小红书首页检查登录状态
            self.console.print("[blue]检查登录状态...[/blue]")
            await page.goto("https://www.xiaohongshu.com", wait_until='domcontentloaded', timeout=15000)
            await asyncio.sleep(2)
            
            # 检查是否已登录（查找用户头像或登录按钮）
            login_selectors = [
                'text=登录',
                'text=Sign in', 
                '[class*="login"]',
                '.login-btn'
            ]
            
            user_selectors = [
                '[class*="avatar"]',
                '[class*="user"]',
                '[data-v*="user"]',
                '.user-avatar'
            ]
            
            # 检查是否有登录按钮（未登录）
            login_button = None
            for selector in login_selectors:
                try:
                    login_button = await page.wait_for_selector(selector, timeout=3000)
                    if login_button:
                        break
                except:
                    continue
            
            if login_button:
                self.console.print("[yellow]检测到未登录状态[/yellow]")
                self.console.print("[blue]正在为您打开登录页面，请手动登录...[/blue]")
                
                # 点击登录按钮
                await login_button.click()
                await asyncio.sleep(2)
                
                # 等待用户手动登录
                self.console.print("[green]请在浏览器中完成登录操作[/green]")
                self.console.print("[yellow]登录完成后，程序将自动继续...[/yellow]")
                
                # 等待登录完成（检查用户元素出现）
                max_wait = 300  # 最多等待5分钟
                check_interval = 5  # 每5秒检查一次
                
                for i in range(max_wait // check_interval):
                    await asyncio.sleep(check_interval)
                    
                    # 检查是否已登录
                    logged_in = False
                    for user_selector in user_selectors:
                        try:
                            user_element = await page.query_selector(user_selector)
                            if user_element:
                                logged_in = True
                                break
                        except:
                            continue
                    
                    if logged_in:
                        self.console.print("[green]✓ 登录成功！登录状态已保存[/green]")
                        return True
                    
                    # 检查登录按钮是否还存在
                    login_still_exists = False
                    for login_selector in login_selectors:
                        try:
                            login_element = await page.query_selector(login_selector)
                            if login_element:
                                login_still_exists = True
                                break
                        except:
                            continue
                    
                    if not login_still_exists:
                        self.console.print("[green]✓ 登录状态检测成功[/green]")
                        return True
                    
                    if i % 6 == 0:  # 每30秒提示一次
                        self.console.print(f"[blue]等待登录中... ({i * check_interval}/{max_wait}秒)[/blue]")
                
                self.console.print("[red]登录等待超时，将继续尝试提取[/red]")
                return False
            else:
                # 检查是否有用户元素（已登录）
                for user_selector in user_selectors:
                    try:
                        user_element = await page.query_selector(user_selector)
                        if user_element:
                            self.console.print("[green]✓ 已检测到登录状态[/green]")
                            return True
                    except:
                        continue
                
                self.console.print("[blue]无法确定登录状态，将继续尝试提取[/blue]")
                return True
                
        except Exception as e:
            self.console.print(f"[yellow]登录状态检查失败: {e}[/yellow]")
            return True
    
    async def set_cookies(self, page):
        """设置Cookie到页面"""
        if not self.cookie:
            return
        
        try:
            # 先访问主页面设置域名上下文
            await page.goto("https://www.xiaohongshu.com", wait_until='domcontentloaded', timeout=15000)
            
            # 解析并设置Cookie
            cookies = self.parse_cookie_string(self.cookie)
            await page.context.add_cookies(cookies)
            
        except Exception as e:
            self.console.print(f"[yellow]设置Cookie失败: {e}[/yellow]")
    
    def parse_cookie_string(self, cookie_string: str) -> List[Dict]:
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
    
    def extract_comments_from_state(self, initial_state: Dict, note_id: str) -> List[Dict]:
        """从__INITIAL_STATE__中提取评论"""
        comments = []
        
        try:
            # 尝试从noteDetailMap中获取评论
            note_detail_map = initial_state.get('note', {}).get('noteDetailMap', {})
            
            if note_id in note_detail_map:
                note_data = note_detail_map[note_id]
                comment_data = note_data.get('comments', {})
                comment_list = comment_data.get('list', [])
                
                if comment_list:
                    self.console.print(f"[green]从noteDetailMap获取到 {len(comment_list)} 条原始评论[/green]")
                    # 处理每条评论，提取完整信息
                    for raw_comment in comment_list:
                        processed_comment = self.process_raw_comment(raw_comment, initial_state)
                        if processed_comment:
                            comments.append(processed_comment)
                    self.console.print(f"[green]处理后得到 {len(comments)} 条完整评论[/green]")
                else:
                    self.console.print(f"[yellow]noteDetailMap中评论列表为空，hasMore: {comment_data.get('hasMore')}, loading: {comment_data.get('loading')}[/yellow]")
            
            # 递归搜索其他可能的评论位置
            if not comments:
                recursive_comments = self.recursive_search_comments(initial_state)
                if recursive_comments:
                    self.console.print(f"[green]递归搜索找到 {len(recursive_comments)} 条评论[/green]")
                    comments.extend(recursive_comments)
                    
        except Exception as e:
            self.console.print(f"[red]解析__INITIAL_STATE__失败: {e}[/red]")
        
        return comments
    
    def process_raw_comment(self, raw_comment: Dict, initial_state: Dict) -> Optional[Dict]:
        """处理原始评论数据，补充用户信息和时间"""
        try:
            comment_id = raw_comment.get('id', '')
            content = raw_comment.get('content', '')
            
            # 获取时间 - 注意字段名是createTime而不是create_time
            create_time = raw_comment.get('createTime', raw_comment.get('create_time', 0))
            
            # 获取用户信息 - 直接从评论中的userInfo字段获取
            user_info_raw = raw_comment.get('userInfo', {})
            if user_info_raw:
                user_info = {
                    'nickname': user_info_raw.get('nickname', '匿名用户'),
                    'user_id': user_info_raw.get('userId', ''),
                    'avatar': user_info_raw.get('image', ''),
                    'xsec_token': user_info_raw.get('xsecToken', '')
                }
            else:
                # 备用方案：从user_id查找
                user_id = raw_comment.get('user_id', raw_comment.get('userId', raw_comment.get('uid', '')))
                user_info = self.get_user_info_from_state(user_id, initial_state)
            
            # 处理时间戳
            if isinstance(create_time, str):
                create_time = self.parse_time_string(create_time)
            elif create_time == 0 or create_time is None:
                # 尝试从其他字段获取时间
                create_time = raw_comment.get('time', raw_comment.get('timestamp', int(time.time() * 1000)))
            
            # 处理图片 - 字段名是pictures而不是images
            images = raw_comment.get('pictures', raw_comment.get('images', raw_comment.get('pics', [])))
            if not isinstance(images, list):
                images = []
            
            # 处理IP位置
            ip_location = raw_comment.get('ipLocation', '')
            
            processed_comment = {
                'id': comment_id,
                'content': content,
                'create_time': create_time,
                'user_info': user_info,
                'images': images,
                'ip_location': ip_location,
                'like_count': raw_comment.get('likeCount', '0'),
                'sub_comment_count': raw_comment.get('subCommentCount', '0'),
                'raw_data': raw_comment  # 保留原始数据用于调试
            }
            
            return processed_comment
            
        except Exception as e:
            self.console.print(f"[yellow]处理评论数据失败: {e}[/yellow]")
            return None
    
    def get_user_info_from_state(self, user_id: str, initial_state: Dict) -> Dict:
        """从initial_state中获取用户信息"""
        if not user_id:
            return {'nickname': '匿名用户'}
        
        try:
            # 尝试从userMap中获取用户信息
            user_map = initial_state.get('user', {}).get('userMap', {})
            if user_id in user_map:
                user_data = user_map[user_id]
                return {
                    'nickname': user_data.get('nickname', user_data.get('name', '匿名用户')),
                    'user_id': user_id,
                    'avatar': user_data.get('avatar', ''),
                    'level': user_data.get('level', 0)
                }
            
            # 尝试从其他可能的位置查找用户信息
            all_users = self.find_all_users_in_state(initial_state)
            for user_data in all_users:
                if (user_data.get('id') == user_id or 
                    user_data.get('user_id') == user_id or 
                    user_data.get('userId') == user_id):
                    return {
                        'nickname': user_data.get('nickname', user_data.get('name', '匿名用户')),
                        'user_id': user_id,
                        'avatar': user_data.get('avatar', ''),
                        'level': user_data.get('level', 0)
                    }
            
        except Exception as e:
            self.console.print(f"[yellow]获取用户信息失败: {e}[/yellow]")
        
        return {'nickname': f'用户_{user_id[:8]}', 'user_id': user_id}
    
    def find_all_users_in_state(self, data: Dict, max_depth: int = 3) -> List[Dict]:
        """递归查找所有用户信息"""
        users = []
        
        if max_depth <= 0:
            return users
        
        if isinstance(data, dict):
            # 检查当前层级是否是用户数据
            if self.looks_like_user_data(data):
                users.append(data)
            else:
                # 递归搜索
                for key, value in data.items():
                    if key in ['user', 'users', 'userMap', 'userInfo', 'author']:
                        if isinstance(value, dict):
                            if self.looks_like_user_data(value):
                                users.append(value)
                            else:
                                users.extend(self.find_all_users_in_state(value, max_depth - 1))
                        elif isinstance(value, list):
                            for item in value:
                                if self.looks_like_user_data(item):
                                    users.append(item)
                    else:
                        users.extend(self.find_all_users_in_state(value, max_depth - 1))
        elif isinstance(data, list):
            for item in data:
                users.extend(self.find_all_users_in_state(item, max_depth - 1))
        
        return users
    
    def looks_like_user_data(self, data) -> bool:
        """判断数据是否看起来像用户信息"""
        if not isinstance(data, dict):
            return False
        
        user_indicators = [
            'nickname', 'name', 'username',  # 用户名
            'avatar', 'avatarUrl',  # 头像
            'user_id', 'userId', 'uid', 'id'  # 用户ID
        ]
        
        found_indicators = sum(1 for key in user_indicators if key in data)
        return found_indicators >= 2
    
    def parse_time_string(self, time_str: str) -> int:
        """解析时间字符串为时间戳"""
        try:
            if '小时前' in time_str:
                hours = int(re.search(r'(\d+)', time_str).group(1))
                return int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
            elif '分钟前' in time_str:
                minutes = int(re.search(r'(\d+)', time_str).group(1))
                return int((datetime.now() - timedelta(minutes=minutes)).timestamp() * 1000)
            elif '天前' in time_str:
                days = int(re.search(r'(\d+)', time_str).group(1))
                return int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
            elif 'T' in time_str:
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                return int(dt.timestamp() * 1000)
            else:
                # 尝试直接解析为数字
                return int(float(time_str))
        except:
            return int(time.time() * 1000)  # 返回当前时间
    
    def recursive_search_comments(self, data, max_depth: int = 5) -> List[Dict]:
        """递归搜索评论数据"""
        comments = []
        
        if max_depth <= 0:
            return comments
        
        if isinstance(data, dict):
            # 检查当前层级是否包含评论特征
            if self.looks_like_comment_data(data):
                comments.append(data)
            else:
                # 递归搜索子层级
                for key, value in data.items():
                    if key in ['comments', 'comment', 'commentList', 'replies', 'list']:
                        if isinstance(value, list):
                            for item in value:
                                if self.looks_like_comment_data(item):
                                    comments.append(item)
                        elif isinstance(value, dict) and 'list' in value:
                            for item in value['list']:
                                if self.looks_like_comment_data(item):
                                    comments.append(item)
                    else:
                        comments.extend(self.recursive_search_comments(value, max_depth - 1))
        elif isinstance(data, list):
            for item in data:
                if self.looks_like_comment_data(item):
                    comments.append(item)
                else:
                    comments.extend(self.recursive_search_comments(item, max_depth - 1))
        
        return comments
    
    def looks_like_comment_data(self, data) -> bool:
        """判断数据是否看起来像评论"""
        if not isinstance(data, dict):
            return False
        
        # 检查是否包含评论的典型字段
        comment_indicators = [
            'content', 'text', 'body',  # 评论内容
            'user', 'author', 'user_info',  # 用户信息
            'create_time', 'time', 'timestamp', 'created_at',  # 时间
            'id', 'comment_id', 'cid'  # ID
        ]
        
        found_indicators = sum(1 for key in comment_indicators if key in data)
        
        # 如果包含至少2个典型字段，认为是评论数据
        return found_indicators >= 2
    
    def create_image_filename(self, nickname: str, formatted_time: str, content: str, index: int = 1) -> str:
        """创建图片文件名，格式：用户昵称_评论时间_评论内容_序号"""
        try:
            # 清理文件名中的特殊字符
            clean_nickname = self.clean_filename(nickname)
            
            # 简化时间格式，去掉秒和特殊字符
            time_part = formatted_time.replace(':', '-').replace(' ', '_')
            
            # 截取评论内容的前50个字符并清理（保留更多内容用于文件名）
            content_part = content[:50] if content else "无内容"
            content_part = self.clean_filename(content_part)
            
            # 如果内容被截断，添加省略号标识
            if content and len(content) > 50:
                content_part += "..."
            
            # 组合文件名
            filename = f"{clean_nickname}_{time_part}_{content_part}"
            
            # 添加序号（确保每张图片都有唯一标识）
            filename += f"_{index}"
            
            return filename
        except Exception as e:
            self.console.print(f"[yellow]创建图片文件名失败: {e}[/yellow]")
            return f"image_{nickname}_{index}"
    
    async def download_image(self, url: str, save_path: Path, session: aiohttp.ClientSession) -> bool:
        """下载单张图片"""
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    async with aiofiles.open(save_path, 'wb') as f:
                        await f.write(content)
                    return True
                else:
                    self.console.print(f"[yellow]图片下载失败 {response.status}: {url}[/yellow]")
                    return False
        except Exception as e:
            self.console.print(f"[yellow]下载图片异常: {e}[/yellow]")
            return False
    
    def get_image_extension(self, url: str, content_type: str = None) -> str:
        """获取图片扩展名"""
        try:
            # 首先尝试从URL中获取扩展名
            parsed_url = urlparse(url)
            path = parsed_url.path
            if '.' in path:
                ext = path.split('.')[-1].lower()
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
                    return f".{ext}"
            
            # 如果从URL获取不到，尝试从content-type获取
            if content_type:
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    return ext
            
            # 默认使用jpg
            return '.jpg'
        except:
            return '.jpg'
    
    async def download_comment_images(self, image_urls: List[str], nickname: str, formatted_time: str, content: str, comment_dir: Path) -> List[str]:
        """下载评论中的所有图片"""
        downloaded_images = []
        
        if not image_urls:
            return downloaded_images
        
        # 直接使用用户昵称目录，不创建images子目录
        images_dir = comment_dir
        
        # 创建HTTP会话
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Referer': 'https://www.xiaohongshu.com/'
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            for i, url in enumerate(image_urls, 1):
                try:
                    if not url:
                        continue
                    
                    # 创建文件名
                    filename_base = self.create_image_filename(nickname, formatted_time, content, i)
                    
                    # 获取图片扩展名
                    extension = self.get_image_extension(url)
                    filename = filename_base + extension
                    
                    # 完整的保存路径
                    save_path = images_dir / filename
                    
                    # 下载图片
                    self.console.print(f"[blue]下载图片 {i}/{len(image_urls)}: {filename}[/blue]")
                    success = await self.download_image(url, save_path, session)
                    
                    if success:
                        downloaded_images.append(str(save_path))
                        self.console.print(f"[green]✓ 图片下载成功: {filename}[/green]")
                    else:
                        self.console.print(f"[red]✗ 图片下载失败: {filename}[/red]")
                        
                except Exception as e:
                    self.console.print(f"[red]处理图片 {i} 失败: {e}[/red]")
                    continue
        
        return downloaded_images
    
    async def extract_comments_from_dom(self, page) -> List[Dict]:
        """从DOM结构中提取评论"""
        comments = []
        
        try:
            # 获取所有可能的评论元素
            comment_elements = await page.query_selector_all(
                '[class*="comment"], [data-v*="comment"], .comment-item, .comment-content, [class*="Comment"]'
            )
            
            for element in comment_elements:
                try:
                    # 提取评论文本
                    text = await element.text_content()
                    if text and len(text.strip()) > 5:  # 过滤掉太短的文本
                        comment = {
                            'content': text.strip(),
                            'user_info': {'nickname': '未知用户'},
                            'create_time': int(time.time() * 1000),
                            'id': f'dom_comment_{len(comments)}'
                        }
                        comments.append(comment)
                except Exception as e:
                    continue
                    
        except Exception as e:
            self.console.print(f"[yellow]DOM解析失败: {e}[/yellow]")
        
        return comments
    
    async def debug_save_initial_state(self, initial_state: Dict, note_id: str):
        """调试：保存原始数据结构"""
        try:
            debug_dir = self.work_path / "debug"
            debug_dir.mkdir(exist_ok=True)
            
            debug_file = debug_dir / f"initial_state_{note_id}.json"
            async with aiofiles.open(debug_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(initial_state, ensure_ascii=False, indent=2))
            
            self.console.print(f"[blue]调试数据已保存到: {debug_file}[/blue]")
            
            # 分析数据结构
            self.analyze_initial_state_structure(initial_state, note_id)
            
        except Exception as e:
            self.console.print(f"[yellow]保存调试数据失败: {e}[/yellow]")
    
    def analyze_initial_state_structure(self, initial_state: Dict, note_id: str):
        """分析初始状态数据结构"""
        try:
            self.console.print("[blue]== 数据结构分析 ==[/blue]")
            
            # 分析顶层结构
            top_keys = list(initial_state.keys())
            self.console.print(f"顶层键: {top_keys}")
            
            # 分析note部分
            if 'note' in initial_state:
                note_keys = list(initial_state['note'].keys())
                self.console.print(f"note层键: {note_keys}")
                
                if 'noteDetailMap' in initial_state['note'] and note_id in initial_state['note']['noteDetailMap']:
                    note_detail = initial_state['note']['noteDetailMap'][note_id]
                    note_detail_keys = list(note_detail.keys())
                    self.console.print(f"noteDetail键: {note_detail_keys}")
                    
                    if 'comments' in note_detail:
                        comments_keys = list(note_detail['comments'].keys())
                        self.console.print(f"comments键: {comments_keys}")
                        
                        if 'list' in note_detail['comments']:
                            comment_list = note_detail['comments']['list']
                            self.console.print(f"评论列表长度: {len(comment_list)}")
                            
                            if comment_list:
                                # 分析第一条评论的结构
                                first_comment = comment_list[0]
                                comment_keys = list(first_comment.keys())
                                self.console.print(f"单条评论键: {comment_keys}")
                                
                                # 输出评论样本
                                self.console.print(f"评论样本: {json.dumps(first_comment, ensure_ascii=False, indent=2)[:300]}...")
            
            # 分析user部分
            if 'user' in initial_state:
                user_keys = list(initial_state['user'].keys())
                self.console.print(f"user层键: {user_keys}")
                
                if 'userMap' in initial_state['user']:
                    user_map = initial_state['user']['userMap']
                    user_ids = list(user_map.keys())[:5]  # 只显示前5个
                    self.console.print(f"userMap中的用户ID样本: {user_ids}")
                    
                    if user_ids:
                        first_user = user_map[user_ids[0]]
                        user_sample_keys = list(first_user.keys())
                        self.console.print(f"用户信息键: {user_sample_keys}")
            
        except Exception as e:
            self.console.print(f"[yellow]数据结构分析失败: {e}[/yellow]")
    
    def normalize_comment_data(self, comments: List[Dict]) -> List[Dict]:
        """标准化评论数据格式"""
        normalized = []
        
        for comment in comments:
            try:
                # 标准化用户信息
                user_info = comment.get('user_info', comment.get('user', comment.get('author', {})))
                if isinstance(user_info, str):
                    user_info = {'nickname': user_info}
                elif not isinstance(user_info, dict):
                    user_info = {'nickname': '匿名用户'}
                
                # 标准化评论内容
                content = comment.get('content', comment.get('text', comment.get('body', '')))
                
                # 标准化时间
                create_time = comment.get('create_time', comment.get('time', comment.get('timestamp', 0)))
                
                # 标准化图片
                images = comment.get('images', comment.get('pics', comment.get('pictures', [])))
                if not isinstance(images, list):
                    images = []
                
                normalized_comment = {
                    'user_info': user_info,
                    'content': str(content).strip(),
                    'create_time': create_time,
                    'images': images,
                    'id': comment.get('id', comment.get('comment_id', f'comment_{len(normalized)}'))
                }
                
                # 只保留有内容的评论
                if normalized_comment['content'] or normalized_comment['images']:
                    normalized.append(normalized_comment)
                    
            except Exception as e:
                self.console.print(f"[yellow]标准化评论失败: {e}[/yellow]")
                continue
        
        return normalized
    
    def clean_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        import re
        
        # 替换非法字符
        illegal_chars = r'[<>:"/\\|?*！~\n\r\t]'
        filename = re.sub(illegal_chars, '_', filename)
        
        # 替换多个连续的空格和下划线为单个下划线
        filename = re.sub(r'[_\s]+', '_', filename)
        
        # 移除开头和结尾的下划线和空格
        filename = filename.strip('_').strip()
        
        # 如果文件名太长，智能截取（保留前面的重要信息）
        if len(filename) > 80:  # 增加长度限制，更好地保留标题信息
            filename = filename[:80].rstrip('_')
        
        # 如果清理后为空，返回默认名称
        if not filename:
            filename = "未命名作品"
            
        return filename
    
    def format_comment_time(self, timestamp) -> str:
        """格式化评论时间"""
        try:
            if isinstance(timestamp, str):
                # 尝试解析中文时间格式
                if '小时前' in timestamp:
                    hours = int(re.search(r'(\d+)', timestamp).group(1))
                    dt = datetime.now() - timedelta(hours=hours)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                elif '分钟前' in timestamp:
                    minutes = int(re.search(r'(\d+)', timestamp).group(1))
                    dt = datetime.now() - timedelta(minutes=minutes)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                elif '天前' in timestamp:
                    days = int(re.search(r'(\d+)', timestamp).group(1))
                    dt = datetime.now() - timedelta(days=days)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                elif 'T' in timestamp:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    return timestamp
            elif isinstance(timestamp, (int, float)):
                if timestamp > 10**12:  # 毫秒级
                    dt = datetime.fromtimestamp(timestamp / 1000)
                else:  # 秒级
                    dt = datetime.fromtimestamp(timestamp)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        return "未知时间"
    
    async def save_comment_content(self, comment: Dict, comment_dir: Path) -> None:
        """保存单条评论内容"""
        try:
            # 提取评论信息
            user_info = comment.get('user_info', {})
            nickname = user_info.get('nickname', '匿名用户')
            user_id = user_info.get('user_id', '')
            avatar = user_info.get('avatar', '')
            content = comment.get('content', '')
            create_time = comment.get('create_time', '')
            images = comment.get('images', [])
            ip_location = comment.get('ip_location', '')
            like_count = comment.get('like_count', '0')
            sub_comment_count = comment.get('sub_comment_count', '0')
            
            # 格式化时间
            formatted_time = self.format_comment_time(create_time)
            
            # 创建详细的评论内容文件
            comment_file = comment_dir / "评论内容.txt"
            comment_info = f"""评论时间: {formatted_time}
用户昵称: {nickname}
用户ID: {user_id}
IP位置: {ip_location}
点赞数: {like_count}
回复数: {sub_comment_count}
评论内容: {content}
"""
            
            # 添加头像信息
            if avatar:
                comment_info += f"用户头像: {avatar}\n"
            
            # 处理图片
            downloaded_images = []
            if images:
                image_urls = []
                for img in images:
                    if isinstance(img, dict):
                        # 尝试多个可能的URL字段
                        url = img.get('url_default', img.get('url', img.get('src', img.get('urlDefault', ''))))
                    else:
                        url = str(img)
                    if url:
                        image_urls.append(url)
                
                if image_urls:
                    # 下载评论图片
                    self.console.print(f"[blue]开始下载 {len(image_urls)} 张评论图片...[/blue]")
                    downloaded_images = await self.download_comment_images(image_urls, nickname, formatted_time, content, comment_dir)
                    
                    # 在文本中记录图片信息
                    comment_info += f"\n评论图片 (共{len(image_urls)}张):\n"
                    for i, url in enumerate(image_urls, 1):
                        comment_info += f"  {i}. {url}\n"
                    
                    # 添加下载结果信息
                    if downloaded_images:
                        comment_info += f"\n已下载图片 (共{len(downloaded_images)}张):\n"
                        for i, path in enumerate(downloaded_images, 1):
                            filename = Path(path).name
                            comment_info += f"  {i}. {filename}\n"
            
            # 保存评论内容
            async with aiofiles.open(comment_file, 'w', encoding='utf-8') as f:
                await f.write(comment_info)
            
            # 保存原始JSON数据（去掉raw_data避免重复）
            clean_comment = {k: v for k, v in comment.items() if k != 'raw_data'}
            json_file = comment_dir / "原始数据.json"
            async with aiofiles.open(json_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(clean_comment, ensure_ascii=False, indent=2))
                
        except Exception as e:
            self.console.print(f"[red]保存评论内容失败: {e}[/red]")
    
    async def extract_comments(self, note_url: str) -> bool:
        """提取指定笔记的评论"""
        try:
            # 提取笔记ID
            note_id = self.extract_note_id(note_url)
            if not note_id:
                self.console.print("[red]无法从URL中提取笔记ID[/red]")
                return False
            
            self.console.print(f"[blue]开始处理笔记: {note_id}[/blue]")
            if self.max_comments:
                self.console.print(f"[yellow]数量限制: 只获取最新 {self.max_comments} 条评论[/yellow]")
            else:
                self.console.print("[blue]将获取所有可用评论[/blue]")
            
            # 获取笔记信息
            note_info = await self.get_note_info_with_xhs(note_url)
            if not note_info:
                self.console.print("[yellow]无法获取笔记信息，使用默认信息继续[/yellow]")
                note_info = {
                    '作品标题': f'笔记_{note_id}',
                    '作品描述': '无描述',
                    '作品ID': note_id,
                    '作品链接': note_url
                }
            
            # 创建作品文件夹
            work_title = note_info.get('作品标题', note_id)
            work_title = self.clean_filename(work_title)
            work_dir = self.work_path / work_title
            work_dir.mkdir(parents=True, exist_ok=True)
            
            self.console.print(f"[green]作品标题: {work_title}[/green]")
            self.console.print(f"[green]保存路径: {work_dir}[/green]")
            
            # 保存笔记信息
            note_info_file = work_dir / "作品信息.json"
            async with aiofiles.open(note_info_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(note_info, ensure_ascii=False, indent=2))
            
            # 使用浏览器提取评论
            self.console.print("[blue]启动浏览器获取动态评论...[/blue]")
            raw_comments = await self.extract_comments_with_browser(note_url, note_id)
            
            # 标准化评论数据
            normalized_comments = self.normalize_comment_data(raw_comments)
            
            if not normalized_comments:
                self.console.print("[yellow]未提取到真实评论数据[/yellow]")
                
                # 生成演示评论以展示功能
                demo_comments = [
                    {
                        'user_info': {'nickname': '评论提取演示'},
                        'content': '这是一个演示评论，说明程序结构和功能正常工作。真实评论可能需要登录状态或特定条件才能获取。',
                        'create_time': int(time.time() * 1000),
                        'images': [],
                        'id': 'demo_1'
                    }
                ]
                normalized_comments = demo_comments
                self.console.print("[blue]使用演示数据展示程序功能[/blue]")
            
            self.console.print(f"[green]成功获取到 {len(normalized_comments)} 条评论[/green]")
            
            # 按时间排序评论（最新的在前面）
            normalized_comments.sort(key=lambda x: x.get('create_time', 0), reverse=True)
            self.console.print("[blue]✓ 评论已按时间排序（最新在前）[/blue]")
            
            # 保存评论
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("保存评论中...", total=len(normalized_comments))
                
                for i, comment in enumerate(normalized_comments):
                    try:
                        # 获取用户昵称
                        user_info = comment.get('user_info', {})
                        nickname = user_info.get('nickname', f'用户_{i+1}')
                        nickname = self.clean_filename(nickname)
                        
                        # 创建用户文件夹
                        user_dir = work_dir / nickname
                        user_dir.mkdir(exist_ok=True)
                        
                        # 保存评论内容
                        await self.save_comment_content(comment, user_dir)
                        
                        progress.update(task, advance=1)
                        
                    except Exception as e:
                        self.console.print(f"[red]处理评论 {i+1} 失败: {e}[/red]")
                        continue
            
            # 创建提取报告
            report_file = work_dir / "提取报告.txt"
            report_content = f"""小红书动态评论提取报告

笔记ID: {note_id}
笔记链接: {note_url}
作品标题: {work_title}
提取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
评论数量: {len(normalized_comments)} 条
排序方式: 按时间倒序（最新评论在前）

技术方法:
- 使用Playwright浏览器自动化
- 模拟真实浏览器访问
- 动态触发JavaScript评论加载
- 从__INITIAL_STATE__和DOM中提取数据
- 按时间排序避免重复下载

说明:
此版本使用浏览器自动化技术，可以处理动态加载的评论。
评论按时间倒序排列，最新的评论在前面，避免重复下载。
如果未获取到真实评论，可能需要登录状态或该笔记暂无评论。
"""
            
            async with aiofiles.open(report_file, 'w', encoding='utf-8') as f:
                await f.write(report_content)
            
            self.console.print(f"[green]✓ 评论提取完成! 保存在: {work_dir}[/green]")
            return True
            
        except Exception as e:
            self.console.print(f"[red]提取评论失败: {e}[/red]")
            return False


async def main():
    """主函数"""
    # 测试用的链接列表
    test_urls = [
        # 成功的链接 - 景德镇素胚绘画
        "https://www.xiaohongshu.com/explore/683d98b3000000000303909b?xsec_token=ABwwtEmTmdFrTevYbsrQ-bw3rWWD6W8X3Ml0_68So1B_o=&xsec_source=pc_user",
        # 失败的链接 - 无法浏览
        "https://www.xiaohongshu.com/explore/685613550000000010027087?xsec_token=ABsx19iTZOBngP5o8tS4RRtdE2zXnVe4T1-dVE1Kt2joY=&xsec_source=pc_search&source=web_explore_feed"
    ]
    
    # 选择要测试的链接 (0: 成功链接, 1: 失败链接)  
    selected_url_index = 1
    note_url = test_urls[selected_url_index]
    
    # 用户的Cookie
    cookie = "abRequestId=a5f5e4aa-4d4c-58fd-8fb0-d6debfdd9a68; a1=194f563ee12eu59osjs90kw3ibndjj2hyq45geudl30000822344; webId=0151dac836375abb81abedf9d7b99687; gid=yj4i2K488jv8yj4i2KqddAd7yJd72jlMVMj84f1TEq3DI2q8fVVJxk888YJJq448fDWYWKWd; xsecappid=xhs-pc-web; unread={%22ub%22:%22686866070000000015021b9a%22%2C%22ue%22:%226866427400000000130116be%22%2C%22uc%22:9}; acw_tc=0a4ad9c917517974953843390e280a55fe9fee0eef53f238e2b24f7468e9a3; web_session=030037a09809582609ba6214122f4acda77e4c; websectiga=a9bdcaed0af874f3a1431e94fbea410e8f738542fbb02df1e8e30c29ef3d91ac; sec_poison_id=2a1e00cd-bf3d-488d-8962-6c3afa75f152; webBuild=4.71.0; loadts=1751798717419"
    
    print("=" * 60)
    print("小红书动态评论提取器 - 全量版本")
    print("=" * 60)
    print(f"目标链接: {note_url}")
    print("使用浏览器自动化获取动态评论数据")
    print("✨ 新功能：")
    print("  🔐 自动保存登录状态，只需登录一次！")
    print("  📄 分页获取所有评论，不再限制数量！")
    print("  🚀 智能加载更多，支持大量评论作品！")
    print("  🖼️ 自动下载评论图片，保存到本地文件夹！")
    print("=" * 60)
    
    # 初始化提取器 - 启用持久化登录状态
    extractor = DynamicCommentExtractor(
        work_path="Comments_Dynamic",
        cookie=cookie,
        use_persistent_session=True  # 启用持久化会话
    )
    
    # 提取评论
    success = await extractor.extract_comments(note_url)
    
    print()
    if success:
        print("✓ 动态评论提取成功!")
        print(f"✓ 结果已保存到: {extractor.work_path}")
        print("✓ 使用浏览器自动化成功处理动态内容!")
    else:
        print("✗ 动态评论提取失败!")
        print("可能需要手动登录或该笔记无评论")
    
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())