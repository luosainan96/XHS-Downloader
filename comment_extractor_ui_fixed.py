#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书评论提取器 - 修复版Web UI界面
解决点击无反应的问题
"""

import streamlit as st
import time
from pathlib import Path
import json
from datetime import datetime
import threading
import re
import pandas as pd
import asyncio

from dynamic_comment_extractor import DynamicCommentExtractor
from local_comment_loader import LocalCommentLoader
from intelligent_reply_generator import create_intelligent_reply_generator
from comment_selector import CommentSelector, SelectionCriteria, CommentPriority
from comment_status_manager import CommentStatusManager, CommentStatus
import aiohttp
import aiofiles
import hashlib
import urllib.parse

# 同步包装器函数
def run_async_function(async_func, *args, **kwargs):
    """在Streamlit中安全运行异步函数"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(async_func(*args, **kwargs))
    finally:
        # 不要关闭事件循环，因为Streamlit可能还在使用它
        pass

def get_full_comment_data(comment_data: dict, work_dir: str) -> dict:
    """获取完整的评论数据，包括原始数据文件中的详细信息"""
    try:
        # 如果comment_data已经包含完整信息，直接返回
        if 'create_time' in comment_data and 'images' in comment_data:
            return comment_data
        
        # 尝试从用户目录读取原始数据.json
        user_nickname = comment_data.get('nickname', '')
        if user_nickname and work_dir:
            user_dir = Path(work_dir) / user_nickname
            raw_data_file = user_dir / "原始数据.json"
            
            if raw_data_file.exists():
                with open(raw_data_file, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                
                # 合并数据
                full_data = comment_data.copy()
                full_data.update({
                    'create_time': raw_data.get('create_time'),
                    'images': raw_data.get('images', []),
                    'user_info': raw_data.get('user_info', {}),
                    'id': raw_data.get('id')
                })
                return full_data
    except Exception as e:
        print(f"获取完整评论数据失败: {e}")
    
    # 如果获取失败，返回原始数据
    return comment_data

# 页面配置
st.set_page_config(
    page_title="小红书评论提取器",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """初始化会话状态"""
    if 'extraction_status' not in st.session_state:
        st.session_state.extraction_status = 'idle'
    if 'extraction_progress' not in st.session_state:
        st.session_state.extraction_progress = 0
    if 'current_task' not in st.session_state:
        st.session_state.current_task = ""
    if 'extraction_logs' not in st.session_state:
        st.session_state.extraction_logs = []
    if 'results' not in st.session_state:
        st.session_state.results = None
    if 'last_update' not in st.session_state:
        st.session_state.last_update = time.time()
    # 新增评论详细信息状态
    if 'comment_details' not in st.session_state:
        st.session_state.comment_details = []
    if 'current_comment_index' not in st.session_state:
        st.session_state.current_comment_index = 0
    if 'total_comments' not in st.session_state:
        st.session_state.total_comments = 0
    if 'downloaded_images' not in st.session_state:
        st.session_state.downloaded_images = []

def add_log(message: str, level: str = "info"):
    """添加日志消息"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.extraction_logs.append({
        'time': timestamp,
        'level': level,
        'message': message
    })
    st.session_state.last_update = time.time()

def add_comment_detail(nickname: str, time_str: str, content: str, images: list, downloaded_images: list = None, comment_dir: str = ''):
    """添加评论详细信息"""
    st.session_state.comment_details.append({
        'nickname': nickname,
        'time': time_str,
        'content': content,
        'images': images,
        'downloaded_images': downloaded_images or [],
        'comment_dir': comment_dir,
        'timestamp': datetime.now().strftime("%H:%M:%S")
    })
    st.session_state.last_update = time.time()

def update_progress(current: int, total: int, task: str = ""):
    """更新进度信息"""
    st.session_state.current_comment_index = current
    st.session_state.total_comments = total
    st.session_state.extraction_progress = (current / total * 100) if total > 0 else 0
    st.session_state.current_task = task
    st.session_state.last_update = time.time()

async def download_image_if_needed(image_url: str, save_dir: Path, nickname: str, comment_time: str) -> str:
    """智能下载图片：如果本地存在则返回本地路径，否则下载"""
    try:
        # 生成安全的文件名
        url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
        safe_filename = f"{nickname}_{comment_time}_{url_hash}.jpg"
        
        # 清理文件名中的特殊字符
        safe_filename = re.sub(r'[<>:"/\\|?*]', '_', safe_filename)
        safe_filename = safe_filename.replace(' ', '_')
        
        local_path = save_dir / safe_filename
        
        # 如果文件已存在，直接返回本地路径
        if local_path.exists():
            return str(local_path)
        
        # 确保目录存在
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # 下载图片
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Referer': 'https://www.xiaohongshu.com/',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(image_url) as response:
                if response.status == 200:
                    async with aiofiles.open(local_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    return str(local_path)
                else:
                    return None
                    
    except Exception as e:
        print(f"下载图片失败: {e}")
        return None

def load_image_smart(image_url: str, comment_dir: str, nickname: str, comment_time: str) -> tuple:
    """智能加载图片：优先本地，需要时下载
    
    Returns:
        tuple: (图片路径, 是否为新下载)
    """
    try:
        # 首先检查是否有已下载的图片
        comment_path = Path(comment_dir)
        if comment_path.exists():
            # 查找可能的图片文件
            for img_file in comment_path.glob("*.jpg"):
                if img_file.exists():
                    return (str(img_file), False)  # 本地已存在
            for img_file in comment_path.glob("*.png"):
                if img_file.exists():
                    return (str(img_file), False)  # 本地已存在
        
        # 如果没有本地文件，尝试下载到对应的评论目录
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 确保评论目录存在
            comment_path.mkdir(parents=True, exist_ok=True)
            
            # 下载到评论目录，而不是缓存目录
            result = loop.run_until_complete(
                download_image_if_needed(image_url, comment_path, nickname, comment_time.replace(':', '-'))
            )
            if result:
                return (result, True)  # 新下载
            else:
                return (None, False)  # 下载失败
        finally:
            loop.close()
            
    except Exception as e:
        print(f"智能加载图片失败: {e}")
        return (None, False)

def validate_xhs_url(url: str) -> bool:
    """验证小红书URL格式"""
    if not url:
        return False
    
    if 'xiaohongshu.com' not in url:
        return False
    
    if '/explore/' not in url:
        return False
    
    return True

def extract_note_id_simple(url: str) -> str:
    """简单提取笔记ID用于显示"""
    try:
        if '/explore/' in url:
            parts = url.split('/explore/')
            if len(parts) > 1:
                note_part = parts[1].split('?')[0]
                return note_part
    except:
        pass
    return "未知ID"

def run_extraction_simple(urls: list, cookie: str, work_path: str, max_comments: int = None, auto_cookie_enabled: bool = False):
    """简化的提取函数，直接在主线程中运行"""
    try:
        st.session_state.extraction_status = 'running'
        if max_comments:
            add_log(f"开始初始化评论提取器... (限制数量: {max_comments})")
        else:
            add_log("开始初始化评论提取器...")
        
        # 创建进度回调函数
        def progress_callback(callback_data):
            """进度回调函数，更新UI显示"""
            try:
                # 兼容新的数据结构
                if isinstance(callback_data, dict):
                    nickname = callback_data.get('nickname', '')
                    time_str = callback_data.get('time', '')
                    content = callback_data.get('content', '')
                    images = callback_data.get('image_urls', [])
                    downloaded_images = callback_data.get('downloaded_images', [])
                    comment_dir = callback_data.get('comment_dir', '')
                else:
                    # 兼容旧的回调方式 (当callback_data是元组时)
                    if isinstance(callback_data, (tuple, list)) and len(callback_data) >= 4:
                        nickname, time_str, content, images = callback_data[:4]
                        downloaded_images = []
                        comment_dir = ''
                    else:
                        # 处理其他情况
                        nickname = str(callback_data)
                        time_str = ''
                        content = ''
                        images = []
                        downloaded_images = []
                        comment_dir = ''
                
                add_comment_detail(nickname, time_str, content, images, downloaded_images, comment_dir)
                # 更新评论计数
                current_count = len(st.session_state.comment_details)
                update_progress(current_count, st.session_state.total_comments, f"正在处理评论: {nickname}")
                add_log(f"📝 处理评论: {nickname} - {content[:30]}...")
            except Exception as e:
                add_log(f"更新进度时发生错误: {str(e)}", "error")
        
        # 创建一个新的事件循环用于异步操作
        async def async_extraction():
            extractor = DynamicCommentExtractor(
                work_path=work_path,
                cookie=cookie,
                use_persistent_session=True,
                max_comments=max_comments,
                progress_callback=progress_callback,
                auto_cookie=auto_cookie_enabled
            )
            
            total_urls = len(urls)
            results = []
            
            for i, url in enumerate(urls):
                note_id = extract_note_id_simple(url)
                current_task = f"处理作品 {i+1}/{total_urls}: {note_id}"
                
                # 更新进度
                progress = (i / total_urls) * 100
                st.session_state.extraction_progress = progress
                st.session_state.current_task = current_task
                add_log(f"开始{current_task}")
                
                try:
                    success = await extractor.extract_comments(url)
                    
                    if success:
                        add_log(f"✅ 作品 {note_id} 处理成功", "success")
                        results.append({
                            'url': url,
                            'note_id': note_id,
                            'status': 'success',
                            'message': '处理成功'
                        })
                    else:
                        add_log(f"❌ 作品 {note_id} 处理失败", "error")
                        results.append({
                            'url': url,
                            'note_id': note_id,
                            'status': 'failed',
                            'message': '处理失败'
                        })
                except Exception as e:
                    add_log(f"❌ 作品 {note_id} 发生异常: {str(e)}", "error")
                    results.append({
                        'url': url,
                        'note_id': note_id,
                        'status': 'error',
                        'message': f'异常: {str(e)}'
                    })
            
            # 完成处理
            st.session_state.extraction_progress = 100
            st.session_state.current_task = "处理完成"
            st.session_state.extraction_status = 'completed'
            st.session_state.results = results
            
            success_count = len([r for r in results if r['status'] == 'success'])
            add_log(f"🎉 所有作品处理完成！成功: {success_count}/{total_urls}", "success")
        
        # 直接运行异步任务
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(async_extraction())
        finally:
            loop.close()
            
    except Exception as e:
        st.session_state.extraction_status = 'error'
        add_log(f"❌ 提取过程发生错误: {str(e)}", "error")

def main():
    """主界面函数"""
    init_session_state()
    
    # 主标题
    st.title("🖼️ 小红书评论提取器")
    st.markdown("---")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 配置设置")
        
        # Cookie设置
        st.subheader("1. Cookie设置")
        
        # Cookie获取方式选择
        cookie_mode = st.radio(
            "选择Cookie获取方式",
            options=["🤖 自动获取Cookie (推荐)", "📝 手动输入Cookie"],
            index=0,
            help="自动获取模式会智能管理Cookie，推荐使用"
        )
        
        cookie_input = ""
        auto_cookie_enabled = False
        
        if cookie_mode == "🤖 自动获取Cookie (推荐)":
            auto_cookie_enabled = True
            st.info("✨ 自动模式：程序将自动获取和管理Cookie，无需手动操作")
            
            # Cookie管理功能
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("🔍 检查Cookie状态", help="检查当前Cookie是否有效"):
                    with st.spinner("正在检查Cookie状态..."):
                        try:
                            from cookie_manager import CookieManager
                            import asyncio
                            
                            async def check_cookie_status():
                                manager = CookieManager("Comments_Dynamic")
                                cookie, is_new = await manager.get_cookie_automatically()
                                return cookie, is_new
                            
                            cookie, is_new = asyncio.run(check_cookie_status())
                            if cookie:
                                st.success("✅ Cookie状态正常")
                                if is_new:
                                    st.info("🆕 获取到新Cookie")
                                else:
                                    st.info("💾 使用缓存Cookie")
                                # 设置cookie_input以便后续使用
                                st.session_state['auto_cookie'] = cookie
                            else:
                                st.error("❌ 无法获取有效Cookie，建议使用手动模式")
                        except Exception as e:
                            st.error(f"Cookie检查失败: {e}")
            
            with col2:
                if st.button("🗑️ 清理Cookie缓存", help="清理保存的Cookie缓存"):
                    try:
                        from cookie_manager import CookieManager
                        manager = CookieManager("Comments_Dynamic")
                        manager.clear_cache()
                        st.success("✅ Cookie缓存已清理")
                        if 'auto_cookie' in st.session_state:
                            del st.session_state['auto_cookie']
                    except Exception as e:
                        st.error(f"清理失败: {e}")
            
            # 在自动模式下，使用临时cookie_input
            cookie_input = "auto_mode"
        
        else:
            st.info("📝 手动模式：请从浏览器复制Cookie")
            cookie_input = st.text_area(
                "请输入小红书Cookie:",
                height=100,
                help="用于登录验证，可在浏览器开发者工具中获取",
                placeholder="a1=xxx; web_session=xxx; ..."
            )
        
        # 输出路径设置
        st.subheader("2. 输出设置")
        work_path = st.text_input(
            "输出目录:",
            value="Comments_Dynamic",
            help="评论和图片的保存目录"
        )
        
        # 评论数量限制
        st.subheader("3. 评论数量设置")
        limit_comments = st.checkbox("限制评论数量", value=False, help="勾选以只获取最新的n条评论")
        
        max_comments = None
        if limit_comments:
            max_comments = st.number_input(
                "最大评论数量:",
                min_value=1,
                max_value=500,
                value=50,
                step=1,
                help="只获取最新的n条评论，建议不超过100条"
            )
            st.info(f"将只获取最新的 {max_comments} 条评论")
        
        # 功能说明
        st.subheader("📋 功能说明")
        st.markdown("""
        **本工具支持：**
        - 🖼️ 自动下载评论图片
        - 📝 智能文件命名
        - 📁 有序文件组织
        - 🔢 限制获取最新N条评论
        - 🔐 持久化登录状态
        - 📄 分页获取全部评论
        """)
    
    # 主内容区域 - 使用选项卡组织内容
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 输入链接", "📊 提取状态", "📋 评论详情", "📂 本地浏览", "🤖 智能回复"])
    
    with tab1:
        st.header("📝 作品链接输入")
        
        # 链接输入方式选择
        input_method = st.radio(
            "选择输入方式:",
            ["单个链接", "批量链接"],
            horizontal=True
        )
        
        urls = []
        
        if input_method == "单个链接":
            url_input = st.text_input(
                "小红书作品链接:",
                placeholder="https://www.xiaohongshu.com/explore/...",
                help="请输入完整的小红书作品链接",
                value="https://www.xiaohongshu.com/explore/685613550000000010027087?xsec_token=ABsx19iTZOBngP5o8tS4RRtdE2zXnVe4T1-dVE1Kt2joY=&xsec_source=pc_search&source=web_explore_feed"
            )
            if url_input:
                urls = [url_input]
        else:
            url_input = st.text_area(
                "批量链接输入 (每行一个):",
                height=150,
                placeholder="https://www.xiaohongshu.com/explore/...\nhttps://www.xiaohongshu.com/explore/...",
                help="每行输入一个小红书作品链接"
            )
            if url_input:
                urls = [url.strip() for url in url_input.split('\n') if url.strip()]
        
        # URL验证和显示
        if urls:
            st.subheader("🔍 链接验证")
            valid_urls = []
            for i, url in enumerate(urls):
                col_status, col_url, col_id = st.columns([1, 3, 1])
                
                is_valid = validate_xhs_url(url)
                with col_status:
                    if is_valid:
                        st.success("✅ 有效")
                        valid_urls.append(url)
                    else:
                        st.error("❌ 无效")
                
                with col_url:
                    st.text(url[:80] + "..." if len(url) > 80 else url)
                
                with col_id:
                    if is_valid:
                        note_id = extract_note_id_simple(url)
                        st.code(note_id[:12])
            
            urls = valid_urls
        
        # 开始提取按钮
        st.markdown("---")
        
        # 检查是否可以开始
        can_start = (
            len(urls) > 0 and 
            (cookie_input.strip() or auto_cookie_enabled) and 
            st.session_state.extraction_status not in ['running']
        )
        
        # 状态检查和错误提示
        if not auto_cookie_enabled and not cookie_input.strip():
            st.warning("⚠️ 请先输入Cookie或启用自动Cookie模式!")
        if not urls:
            st.warning("⚠️ 请先输入有效的作品链接!")
        
        # 开始按钮
        if st.button(
            f"🚀 开始提取评论 ({len(urls)} 个作品)" if urls else "🚀 开始提取评论",
            disabled=not can_start,
            type="primary"
        ):
            # 立即更新状态
            st.session_state.extraction_status = 'starting'
            st.session_state.extraction_progress = 0
            st.session_state.current_task = "准备开始..."
            st.session_state.extraction_logs = []
            st.session_state.results = None
            # 清空评论详细信息
            st.session_state.comment_details = []
            st.session_state.current_comment_index = 0
            st.session_state.total_comments = 0
            
            # 显示开始信息
            st.info("🚀 开始提取评论，请稍候...")
            
            # 立即重新运行以显示状态更新
            st.rerun()
    
    with tab2:
        st.header("📊 提取状态")
        
        # 状态显示
        if st.session_state.extraction_status == 'idle':
            st.info("💤 等待开始...")
            
        elif st.session_state.extraction_status == 'starting':
            st.warning("🚀 正在启动...")
            # 在这里运行提取
            if 'urls' in locals() and urls and (cookie_input.strip() or auto_cookie_enabled):
                # 传递自动Cookie模式标志
                actual_cookie = cookie_input.strip() if not auto_cookie_enabled else ""
                run_extraction_simple(urls, actual_cookie, work_path, max_comments, auto_cookie_enabled)
                st.rerun()
            
        elif st.session_state.extraction_status == 'running':
            st.warning("⏳ 正在提取中...")
            
            # 总体进度
            if st.session_state.total_comments > 0:
                progress_col1, progress_col2 = st.columns([3, 1])
                with progress_col1:
                    st.progress(st.session_state.extraction_progress / 100)
                with progress_col2:
                    st.write(f"{st.session_state.current_comment_index}/{st.session_state.total_comments}")
            
            # 当前任务
            if st.session_state.current_task:
                st.info(f"📋 当前任务: {st.session_state.current_task}")
            
            # 详细进度显示
            if st.session_state.comment_details:
                st.subheader("💬 实时评论处理")
                
                # 添加实时表格显示
                if len(st.session_state.comment_details) > 0:
                    st.write(f"**已处理评论:** {len(st.session_state.comment_details)} 条")
                    
                    # 创建简化的实时表格
                    table_data = []
                    for comment in st.session_state.comment_details[-5:]:  # 显示最新5条
                        table_data.append({
                            '用户昵称': comment['nickname'],
                            '评论时间': comment['time'],
                            '评论内容': comment['content'][:30] + '...' if len(comment['content']) > 30 else comment['content'],
                            '图片数量': len(comment.get('downloaded_images', comment.get('images', []))),
                        })
                    
                    if table_data:
                        df = pd.DataFrame(table_data)
                        st.dataframe(df, use_container_width=True, height=200)
                
                # 详细展示最新评论
                st.subheader("📝 最新处理的评论")
                recent_comments = st.session_state.comment_details[-3:]
                
                for i, comment in enumerate(recent_comments):
                    with st.expander(f"👤 {comment['nickname']} - {comment['time']}", expanded=(i == len(recent_comments) - 1)):
                        st.write(f"**评论时间:** {comment['time']}")
                        st.write(f"**评论内容:** {comment['content'][:100]}{'...' if len(comment['content']) > 100 else ''}")
                        
                        downloaded_images = comment.get('downloaded_images', [])
                        if downloaded_images:
                            st.write(f"**图片数量:** {len(downloaded_images)} 张")
                        elif comment.get('images'):
                            st.write(f"**图片数量:** {len(comment['images'])} 张")
                            # 显示图片URL（前3张）
                            for idx, img_url in enumerate(comment['images'][:3]):
                                st.text(f"  📸 图片{idx+1}: {img_url[:60]}...")
                            if len(comment['images']) > 3:
                                st.text(f"  ... 还有 {len(comment['images']) - 3} 张图片")
                        else:
                            st.write("**图片数量:** 0 张")
                        
                        st.caption(f"处理时间: {comment['timestamp']}")
            
            # 自动刷新 - 仅在运行状态时每隔一段时间刷新一次
            if st.session_state.extraction_status == 'running':
                # 使用 st.empty() 和定期更新
                if 'last_refresh' not in st.session_state:
                    st.session_state.last_refresh = time.time()
                
                current_time = time.time()
                if current_time - st.session_state.last_refresh > 2:  # 每2秒刷新一次
                    st.session_state.last_refresh = current_time
                    st.rerun()
            
        elif st.session_state.extraction_status == 'completed':
            st.success("✅ 提取完成!")
            
        elif st.session_state.extraction_status == 'error':
            st.error("❌ 提取失败!")
        
        # 日志显示
        if st.session_state.extraction_logs:
            st.subheader("📋 处理日志")
            
            # 创建日志容器
            with st.container():
                # 显示最新的10条日志
                recent_logs = st.session_state.extraction_logs[-10:]
                
                for log in recent_logs:
                    if log['level'] == 'success':
                        st.success(f"{log['time']} - {log['message']}")
                    elif log['level'] == 'error':
                        st.error(f"{log['time']} - {log['message']}")
                    else:
                        st.info(f"{log['time']} - {log['message']}")
    
    with tab3:
        st.header("📋 评论详情")
        
        # 显示评论表格和详情
        if st.session_state.comment_details:
            # 统计信息
            total_comments = len(st.session_state.comment_details)
            total_images = sum(len(comment.get('downloaded_images', [])) for comment in st.session_state.comment_details)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("评论总数", total_comments)
            with col2:
                st.metric("图片总数", total_images)
            with col3:
                comments_with_images = sum(1 for comment in st.session_state.comment_details if comment.get('downloaded_images'))
                st.metric("有图评论", comments_with_images)
            
            st.markdown("---")
            
            # 批量下载功能
            col_batch1, col_batch2 = st.columns([1, 1])
            with col_batch1:
                # 检查是否有未下载的图片
                all_unloaded_images = []
                for comment in st.session_state.comment_details:
                    image_urls = comment.get('images', [])
                    downloaded_images = comment.get('downloaded_images', [])
                    unloaded = [url for url in image_urls if url not in downloaded_images]
                    all_unloaded_images.extend(unloaded)
                
                if all_unloaded_images:
                    if st.button(f"📥 批量下载所有图片 ({len(all_unloaded_images)} 张)", type="primary"):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # 统计新下载的图片数量
                        newly_downloaded_count = 0
                        
                        for i, comment in enumerate(st.session_state.comment_details):
                            image_urls = comment.get('images', [])
                            comment_dir = comment.get('comment_dir', '')
                            nickname = comment.get('nickname', 'unknown')
                            comment_time = comment.get('time', '').replace(':', '-')
                            
                            unloaded = [url for url in image_urls if url not in comment.get('downloaded_images', [])]
                            
                            for img_url in unloaded:
                                status_text.text(f"正在下载: {nickname} 的图片...")
                                local_path, is_newly_downloaded = load_image_smart(img_url, comment_dir, nickname, comment_time)
                                if local_path and local_path not in comment.get('downloaded_images', []):
                                    # 更新下载列表
                                    if 'downloaded_images' not in comment:
                                        comment['downloaded_images'] = []
                                    comment['downloaded_images'].append(local_path)
                                    
                                    # 统计新下载
                                    if is_newly_downloaded:
                                        newly_downloaded_count += 1
                            
                            progress_bar.progress((i + 1) / len(st.session_state.comment_details))
                        
                        status_text.text(f"✅ 批量下载完成！新下载 {newly_downloaded_count} 张图片")
                        st.rerun()
                else:
                    st.info("✅ 所有图片都已下载")
            
            with col_batch2:
                # 清理统一收集目录按钮
                if st.button("🗑️ 清理统一图片目录"):
                    # 清理的是Comments_Dynamic/all_comment_images目录
                    work_path = st.session_state.get('work_path', 'Comments_Dynamic')
                    all_images_dir = Path(work_path) / "all_comment_images"
                    if all_images_dir.exists():
                        import shutil
                        shutil.rmtree(all_images_dir)
                        st.success("统一图片目录已清理")
                    else:
                        st.info("无统一图片目录需要清理")
            
            st.markdown("---")
            
            # 评论详情表格
            st.subheader("📊 评论汇总表格")
            
            # 创建表格数据
            table_data = []
            for i, comment in enumerate(st.session_state.comment_details):
                table_data.append({
                    '序号': i + 1,
                    '用户昵称': comment['nickname'],
                    '评论时间': comment['time'],
                    '评论内容': comment['content'][:50] + '...' if len(comment['content']) > 50 else comment['content'],
                    '图片数量': len(comment.get('downloaded_images', [])),
                    '处理时间': comment['timestamp']
                })
            
            # 显示表格
            if table_data:
                df = pd.DataFrame(table_data)
                st.dataframe(df, use_container_width=True, height=400)
                
                st.markdown("---")
                
                # 详细展示区域
                st.subheader("🖼️ 评论详情展示")
                
                # 添加搜索和筛选功能
                search_col1, search_col2 = st.columns([2, 1])
                with search_col1:
                    search_term = st.text_input("🔍 搜索评论内容", placeholder="输入关键词搜索...")
                with search_col2:
                    show_images_only = st.checkbox("仅显示有图评论", value=False)
                
                # 筛选评论
                filtered_comments = st.session_state.comment_details
                if search_term:
                    filtered_comments = [
                        comment for comment in filtered_comments 
                        if search_term.lower() in comment['content'].lower() or 
                           search_term.lower() in comment['nickname'].lower()
                    ]
                if show_images_only:
                    filtered_comments = [
                        comment for comment in filtered_comments 
                        if comment.get('downloaded_images')
                    ]
                
                st.write(f"显示 {len(filtered_comments)} / {total_comments} 条评论")
                
                # 统计本地vs新下载的图片数量
                local_images_count = 0
                total_images_count = 0
                for comment in st.session_state.comment_details:
                    comment_dir = comment.get('comment_dir', '')
                    image_urls = comment.get('images', [])
                    downloaded_images = comment.get('downloaded_images', [])
                    
                    # 统计总图片数量
                    total_images_count += len(image_urls)
                    
                    # 统计本地已存在的图片数量
                    if comment_dir:
                        comment_path = Path(comment_dir)
                        if comment_path.exists():
                            local_files = list(comment_path.glob("*.jpg")) + list(comment_path.glob("*.png"))
                            local_images_count += len(local_files)
                
                # 计算新下载的图片数量
                newly_downloaded_count = total_images_count - local_images_count
                
                # 显示统计信息
                stats_col1, stats_col2, stats_col3 = st.columns(3)
                with stats_col1:
                    st.metric("📊 总图片数", total_images_count)
                with stats_col2:
                    st.metric("💾 本地已有", local_images_count)
                with stats_col3:
                    st.metric("📥 新下载", newly_downloaded_count)
                
                st.markdown("---")
                
                # 为每个评论创建详细展示
                for i, comment in enumerate(filtered_comments):
                    # 确定评论的状态标识
                    comment_dir = comment.get('comment_dir', '')
                    image_urls = comment.get('images', [])
                    status_indicator = ""
                    
                    if image_urls:
                        # 检查是否有本地图片
                        local_images_exist = False
                        if comment_dir:
                            comment_path = Path(comment_dir)
                            if comment_path.exists():
                                local_files = list(comment_path.glob("*.jpg")) + list(comment_path.glob("*.png"))
                                if local_files:
                                    local_images_exist = True
                        
                        if local_images_exist:
                            status_indicator = "💾"  # 本地已有
                        else:
                            status_indicator = "📥"  # 需要下载
                    else:
                        status_indicator = "📝"  # 纯文本评论
                    
                    with st.expander(f"{status_indicator} 👤 {comment['nickname']} - {comment['time']}", expanded=False):
                        # 使用两列布局
                        detail_col1, detail_col2 = st.columns([3, 2])
                        
                        with detail_col1:
                            st.write(f"**评论内容:**")
                            st.write(comment['content'])
                            st.write(f"**处理时间:** {comment['timestamp']}")
                            
                            # 显示原始图片URL
                            if comment.get('images'):
                                st.write(f"**原始图片URL ({len(comment['images'])}张):**")
                                for idx, url in enumerate(comment['images'][:3]):
                                    # 创建超链接
                                    truncated_url = url[:60] + "..." if len(url) > 60 else url
                                    st.markdown(f"🔗 [图片 {idx+1}: {truncated_url}]({url})")
                                if len(comment['images']) > 3:
                                    st.text(f"... 还有 {len(comment['images']) - 3} 张图片")
                        
                        with detail_col2:
                            # 智能图片加载和显示
                            image_urls = comment.get('images', [])
                            downloaded_images = comment.get('downloaded_images', [])
                            comment_dir = comment.get('comment_dir', '')
                            
                            total_images = max(len(image_urls), len(downloaded_images))
                            st.write(f"**图片数量:** {total_images} 张")
                            
                            if total_images > 0:
                                st.write("**评论图片:**")
                                
                                # 创建一个加载图片的按钮（如果有未加载的图片）
                                unloaded_images = [url for url in image_urls if not any(Path(img).exists() for img in downloaded_images)]
                                if unloaded_images and comment_dir:
                                    if st.button(f"📥 加载 {len(unloaded_images)} 张图片", key=f"load_images_{comment.get('nickname', '')}_{i}"):
                                        with st.spinner("正在下载图片..."):
                                            newly_downloaded = 0
                                            locally_loaded = 0
                                            
                                            for idx, img_url in enumerate(unloaded_images):
                                                local_path, is_newly_downloaded = load_image_smart(
                                                    img_url, 
                                                    comment_dir, 
                                                    comment.get('nickname', 'unknown'),
                                                    comment.get('time', '').replace(':', '-')
                                                )
                                                if local_path:
                                                    if is_newly_downloaded:
                                                        newly_downloaded += 1
                                                        st.success(f"图片 {idx+1} 新下载成功")
                                                    else:
                                                        locally_loaded += 1
                                                        st.info(f"图片 {idx+1} 从本地加载")
                                                else:
                                                    st.error(f"图片 {idx+1} 下载失败")
                                            
                                            # 显示加载统计
                                            if newly_downloaded > 0 or locally_loaded > 0:
                                                st.success(f"✅ 完成！本地加载: {locally_loaded} 张，新下载: {newly_downloaded} 张")
                                        st.rerun()
                                
                                # 显示已有的图片
                                displayed_count = 0
                                
                                # 优先显示已下载的图片
                                for idx, img_path in enumerate(downloaded_images):
                                    try:
                                        img_file = Path(img_path)
                                        if img_file.exists():
                                            st.image(str(img_file), caption=f"图片 {displayed_count+1}", width=250)
                                            displayed_count += 1
                                        else:
                                            st.text(f"图片 {displayed_count+1}: {img_file.name}")
                                            st.caption(f"路径: {img_path}")
                                            displayed_count += 1
                                    except Exception as e:
                                        st.text(f"图片 {displayed_count+1}: 显示失败")
                                        st.caption(f"错误: {str(e)}")
                                        displayed_count += 1
                                
                                # 如果还有URL但没有对应的下载文件，显示占位符
                                remaining_urls = image_urls[displayed_count:] if len(image_urls) > displayed_count else []
                                for idx, img_url in enumerate(remaining_urls):
                                    st.text(f"图片 {displayed_count+1}: 未下载")
                                    st.caption("点击上方按钮下载图片")
                                    displayed_count += 1
                                    
                                    # 只显示前3张的占位符
                                    if displayed_count >= 3:
                                        if len(image_urls) > 3:
                                            st.text(f"... 还有 {len(image_urls) - 3} 张图片")
                                        break
                            else:
                                st.write("无图片")
        else:
            st.info("暂无评论数据，请先执行评论提取。")
    
    with tab4:
        st.header("📂 本地评论浏览")
        
        # 初始化本地加载器
        if 'local_loader' not in st.session_state:
            st.session_state.local_loader = LocalCommentLoader("Comments_Dynamic")
        
        loader = st.session_state.local_loader
        
        # 扫描本地作品
        col_refresh, col_info = st.columns([1, 3])
        with col_refresh:
            if st.button("🔄 刷新作品列表"):
                works = loader.scan_available_works(force_refresh=True)
                st.success(f"✅ 刷新完成，找到 {len(works)} 个作品")
            else:
                works = loader.scan_available_works()
        
        with col_info:
            if works:
                st.info(f"📊 共找到 {len(works)} 个本地作品，总计 {sum(w['comment_count'] for w in works)} 条评论")
            else:
                st.warning("⚠️ 未找到本地评论数据，请先执行评论提取")
        
        if works:
            st.markdown("---")
            
            # 作品选择
            st.subheader("🎯 选择作品")
            
            # 作品列表显示
            work_options = []
            for work in works:
                option_text = f"{work['work_title']} ({work['comment_count']} 条评论)"
                if work['latest_comment_time']:
                    option_text += f" - 最新: {work['latest_comment_time']}"
                work_options.append(option_text)
            
            selected_work_index = st.selectbox(
                "选择要查看的作品",
                range(len(works)),
                format_func=lambda x: work_options[x],
                key="local_work_selector"
            )
            
            if selected_work_index is not None:
                selected_work = works[selected_work_index]
                
                st.markdown("---")
                
                # 显示作品信息
                st.subheader("📖 作品信息")
                work_col1, work_col2 = st.columns([2, 1])
                
                with work_col1:
                    st.write(f"**作品标题**: {selected_work['work_title']}")
                    if selected_work['work_id']:
                        st.write(f"**作品ID**: `{selected_work['work_id']}`")
                    if selected_work['work_link']:
                        st.write(f"**原始链接**: [点击访问]({selected_work['work_link']})")
                
                with work_col2:
                    # 获取统计信息
                    stats = loader.get_work_statistics(selected_work['work_dir'])
                    
                    col_s1, col_s2 = st.columns(2)
                    with col_s1:
                        st.metric("💬 评论数", stats['total_comments'])
                        st.metric("📸 图片数", stats['total_images'])
                    with col_s2:
                        st.metric("🖼️ 有图评论", stats['comments_with_images'])
                        st.metric("💾 已下载", stats['total_downloaded_images'])
                
                st.markdown("---")
                
                # 搜索和筛选
                st.subheader("🔍 搜索和筛选")
                search_col1, search_col2, search_col3 = st.columns([2, 1, 1])
                
                with search_col1:
                    local_search_term = st.text_input(
                        "搜索评论内容", 
                        placeholder="输入关键词搜索...",
                        key="local_search"
                    )
                
                with search_col2:
                    local_show_images_only = st.checkbox(
                        "仅显示有图评论", 
                        value=False,
                        key="local_images_only"
                    )
                
                with search_col3:
                    if st.button("📊 导出摘要"):
                        summary = loader.export_work_summary(selected_work['work_dir'])
                        st.download_button(
                            label="📥 下载摘要文件",
                            data=summary,
                            file_name=f"{selected_work['work_title']}_摘要.md",
                            mime="text/markdown"
                        )
                
                # 加载和显示评论
                with st.spinner("正在加载评论数据..."):
                    comments = loader.search_comments(
                        selected_work['work_dir'],
                        local_search_term,
                        local_show_images_only
                    )
                
                st.markdown("---")
                
                # 显示筛选结果
                st.subheader("📋 评论列表")
                st.write(f"显示 {len(comments)} / {stats['total_comments']} 条评论")
                
                if comments:
                    # 评论汇总表格
                    st.subheader("📊 评论汇总表格")
                    
                    table_data = []
                    for i, comment in enumerate(comments):
                        table_data.append({
                            '序号': i + 1,
                            '用户昵称': comment['nickname'],
                            '评论时间': comment['time'],
                            '评论内容': comment['content'][:50] + '...' if len(comment['content']) > 50 else comment['content'],
                            '图片数量': len(comment.get('downloaded_images', [])),
                        })
                    
                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True, height=400)
                    
                    st.markdown("---")
                    
                    # 评论详情展示
                    st.subheader("🖼️ 评论详情展示")
                    
                    # 为每个评论创建详细展示
                    for i, comment in enumerate(comments):
                        # 确定评论的状态标识
                        comment_dir = comment.get('comment_dir', '')
                        image_urls = comment.get('images', [])
                        status_indicator = ""
                        
                        if image_urls:
                            # 检查是否有本地图片
                            local_images_exist = False
                            if comment_dir:
                                comment_path = Path(comment_dir)
                                if comment_path.exists():
                                    local_files = list(comment_path.glob("*.jpg")) + list(comment_path.glob("*.png"))
                                    if local_files:
                                        local_images_exist = True
                            
                            if local_images_exist:
                                status_indicator = "💾"  # 本地已有
                            else:
                                status_indicator = "📥"  # 需要下载
                        else:
                            status_indicator = "📝"  # 纯文本评论
                        
                        with st.expander(f"{status_indicator} 👤 {comment['nickname']} - {comment['time']}", expanded=False):
                            # 使用两列布局
                            detail_col1, detail_col2 = st.columns([3, 2])
                            
                            with detail_col1:
                                st.write(f"**评论内容:**")
                                st.write(comment['content'])
                                
                                # 显示原始图片URL
                                if comment.get('images'):
                                    st.write(f"**原始图片URL ({len(comment['images'])}张):**")
                                    for idx, url in enumerate(comment['images'][:3]):
                                        # 创建超链接
                                        truncated_url = url[:60] + "..." if len(url) > 60 else url
                                        st.markdown(f"🔗 [图片 {idx+1}: {truncated_url}]({url})")
                                    if len(comment['images']) > 3:
                                        st.text(f"... 还有 {len(comment['images']) - 3} 张图片")
                            
                            with detail_col2:
                                # 显示已下载的图片
                                downloaded_images = comment.get('downloaded_images', [])
                                total_images = len(downloaded_images)
                                st.write(f"**已下载图片:** {total_images} 张")
                                
                                if total_images > 0:
                                    # 显示图片
                                    for idx, img_path in enumerate(downloaded_images):
                                        try:
                                            img_file = Path(img_path)
                                            if img_file.exists():
                                                st.image(str(img_file), caption=f"图片 {idx+1}", width=250)
                                            else:
                                                st.text(f"图片 {idx+1}: {img_file.name}")
                                                st.caption(f"路径: {img_path}")
                                        except Exception as e:
                                            st.text(f"图片 {idx+1}: 显示失败")
                                            st.caption(f"错误: {str(e)}")
                                        
                                        # 只显示前3张图片
                                        if idx >= 2:
                                            if total_images > 3:
                                                st.text(f"... 还有 {total_images - 3} 张图片")
                                            break
                                else:
                                    st.write("无图片")
                                
                                # 添加跳转到作品评论区的按钮
                                st.markdown("---")
                                if st.button("🔗 去作品评论区回复", key=f"local_xiaohongshu_{comment['nickname']}_{comment['time']}"):
                                    # 初始化状态管理器（如果还没有）
                                    if 'local_status_manager' not in st.session_state:
                                        st.session_state.local_status_manager = CommentStatusManager("Comments_Dynamic")
                                    
                                    local_status_manager = st.session_state.local_status_manager
                                    
                                    # 获取完整评论数据用于智能定位
                                    full_comment_data = get_full_comment_data(comment, selected_work['work_dir'])
                                    
                                    work_url, location_guide = local_status_manager.generate_xiaohongshu_work_url(
                                        selected_work['work_dir'], 
                                        comment['nickname'],
                                        full_comment_data
                                    )
                                    
                                    if work_url:
                                        # 显示智能定位信息
                                        st.info(location_guide)
                                        
                                        # 跳转链接
                                        st.markdown(f"[🚀 跳转到作品评论区]({work_url})")
                                        
                                        # 快速搜索指导
                                        st.markdown("**💡 快速定位技巧：**")
                                        st.markdown("1. 点击上方链接进入作品页面")
                                        st.markdown("2. 滚动到评论区")
                                        st.markdown("3. 使用 `Ctrl+F` (Windows) 或 `⌘+F` (Mac) 搜索关键词")
                                        st.markdown("4. 根据时间和图片特征快速定位")
                                        
                                        # 显示完整评论内容
                                        with st.expander("📖 完整评论内容", expanded=False):
                                            st.write(comment['content'])
                                    else:
                                        st.error(f"❌ {location_guide}")
                else:
                    st.info("🔍 没有找到匹配的评论，请尝试调整搜索条件")
        
        else:
            st.info("📂 暂无本地评论数据，请先在'📝 输入链接'选项卡中提取评论")
    
    with tab5:
        st.header("🤖 AI智能回复助手")
        
        # 初始化智能回复组件
        if 'reply_generator' not in st.session_state:
            st.session_state.reply_generator = create_intelligent_reply_generator("mock_gpt4o")
        
        if 'comment_selector' not in st.session_state:
            st.session_state.comment_selector = CommentSelector("Comments_Dynamic")
            
        if 'status_manager' not in st.session_state:
            st.session_state.status_manager = CommentStatusManager("Comments_Dynamic")
        
        # 初始化选择的作品目录（确保统计数据准确）
        if 'selected_work_dir' not in st.session_state:
            st.session_state.selected_work_dir = None
        
        reply_generator = st.session_state.reply_generator
        comment_selector = st.session_state.comment_selector
        status_manager = st.session_state.status_manager
        
        st.markdown("""
        ### 🏠 专业家居改造AI助手
        
        为您的评论提供专业的家居改造建议，包括：
        - 🔍 **智能分析**：深度分析房屋现状和改造需求
        - 🎨 **多风格方案**：现代简约、北欧自然、中式现代、工业复古
        - 🖼️ **效果图生成**：AI生成改造后效果图和前后对比
        - 💬 **智能回复**：生成专业、亲和的回复内容
        """)
        
        # 显示整体统计面板
        st.subheader("📊 整体统计概览")
        
        # 获取统计数据
        model_stats = reply_generator.ai_manager.get_model_statistics()
        daily_stats = reply_generator.get_daily_statistics()
        
        # 获取评论统计数据（如果已选择作品，使用作品统计；否则使用全局统计）
        if 'selected_work_dir' in st.session_state and st.session_state.selected_work_dir:
            comment_stats = status_manager.get_statistics(st.session_state.selected_work_dir)
            # 显示当前统计范围
            work_title = comment_stats.get('work_title', '未知作品')
            st.info(f"📋 当前统计范围：《{work_title}》")
        else:
            comment_stats = status_manager.get_statistics()
            st.info("📋 当前统计范围：全局数据（请先选择作品以查看具体统计）")
        
        # 第一行：AI模型和成本统计
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🤖 可用模型", len([m for m in model_stats.values() if m['enabled']]))
        with col2:
            st.metric("💰 今日成本", f"${daily_stats['cost_used']:.2f}")
        with col3:
            st.metric("📊 预算剩余", f"${daily_stats['budget_total'] - daily_stats['cost_used']:.2f}")
        with col4:
            completion_rate = comment_stats.get('completion_rate', 0)
            st.metric("✅ 完成率", f"{completion_rate:.1f}%")
        
        # 第二行：评论和用户统计
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👥 用户数", comment_stats.get('unique_users', 0))
        with col2:
            st.metric("💬 评论总数", comment_stats.get('total_comments', 0))
        with col3:
            st.metric("✅ 已回复", comment_stats.get('completed_count', 0))
        with col4:
            st.metric("⏳ 待回复", comment_stats.get('pending_count', 0))
        
        # 状态分布饼图
        if comment_stats.get('total_comments', 0) > 0:
            col1, col2 = st.columns([2, 1])
            with col1:
                status_data = {
                    '待处理': comment_stats.get('pending_count', 0),
                    '观察中': comment_stats.get('watching_count', 0),
                    '已完成': comment_stats.get('completed_count', 0)
                }
                
                # 创建状态分布图表
                try:
                    import plotly.express as px
                    if sum(status_data.values()) > 0:
                        df = pd.DataFrame(list(status_data.items()), columns=['状态', '数量'])
                        fig = px.pie(df, values='数量', names='状态', 
                                   title='评论状态分布',
                                   color_discrete_map={
                                       '待处理': '#ff6b6b',
                                       '观察中': '#feca57', 
                                       '已完成': '#48dbfb'
                                   })
                        fig.update_layout(height=300)
                        st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    # 如果没有plotly，使用简单的条形图
                    st.bar_chart(status_data)
            
            with col2:
                st.write("**📈 状态明细**")
                for status, count in status_data.items():
                    percentage = (count / comment_stats['total_comments']) * 100 if comment_stats['total_comments'] > 0 else 0
                    st.write(f"- {status}: {count} 条 ({percentage:.1f}%)")
                
                # 显示标记状态说明（仅当选择了作品时）
                if 'selected_work_dir' in st.session_state and st.session_state.selected_work_dir:
                    st.markdown("---")
                    st.write("**ℹ️ 统计说明**")
                    marked_comments = comment_stats.get('marked_comments', 0)
                    unmarked_comments = comment_stats.get('unmarked_comments', 0)
                    st.write(f"- 已手动标记: {marked_comments} 条")
                    st.write(f"- 未标记(默认待处理): {unmarked_comments} 条")
                    st.caption("💡 未标记的评论会自动归类为'待处理'状态")
        
        st.markdown("---")
        
        # 作品选择
        st.subheader("🎯 选择作品")
        
        # 获取可用作品
        works = comment_selector.comment_loader.scan_available_works()
        if not works:
            st.warning("⚠️ 未找到本地评论数据，请先提取评论")
            st.stop()
        
        # 作品选择下拉框
        work_options = []
        for work in works:
            option_text = f"{work['work_title']} ({work['comment_count']} 条评论)"
            work_options.append(option_text)
        
        selected_work_index = st.selectbox(
            "选择要处理的作品",
            range(len(works)),
            format_func=lambda x: work_options[x],
            key="ai_work_selector"
        )
        
        if selected_work_index is not None:
            selected_work = works[selected_work_index]
            work_dir = selected_work['work_dir']
            
            # 保存当前选择的作品目录到session state，用于统计
            st.session_state.selected_work_dir = work_dir
            
            # 确保评论状态记录存在
            comment_selector.ensure_comment_status_exists(work_dir, selected_work['work_title'])
            
            st.markdown("---")
            
            # 评论筛选策略
            st.subheader("🔍 评论筛选策略")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                selection_criteria = st.multiselect(
                    "选择筛选标准",
                    [
                        "改造需求优先",
                        "有图评论优先", 
                        "高互动潜力",
                        "最新评论优先",
                        "仅未处理评论",
                        "待处理状态",
                        "观察中状态",
                        "已完成状态"
                    ],
                    default=["改造需求优先", "有图评论优先"],
                    key="ai_criteria"
                )
            
            with col2:
                max_comments = st.number_input(
                    "最大处理数量",
                    min_value=1,
                    max_value=50,
                    value=10,
                    key="ai_max_comments"
                )
            
            # 转换选择标准
            criteria_map = {
                "改造需求优先": SelectionCriteria.RENOVATION_REQUESTS,
                "有图评论优先": SelectionCriteria.IMAGE_CONSULTATIONS,
                "高互动潜力": SelectionCriteria.HIGH_ENGAGEMENT,
                "最新评论优先": SelectionCriteria.RECENT_COMMENTS,
                "仅未处理评论": SelectionCriteria.UNPROCESSED_ONLY,
                "待处理状态": SelectionCriteria.STATUS_PENDING,
                "观察中状态": SelectionCriteria.STATUS_WATCHING,
                "已完成状态": SelectionCriteria.STATUS_COMPLETED
            }
            
            selected_criteria = [criteria_map[c] for c in selection_criteria if c in criteria_map]
            
            # 智能选择按钮
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("🔍 智能筛选", key="ai_smart_select"):
                    with st.spinner("正在智能筛选评论..."):
                        selection_batch = run_async_function(comment_selector.smart_auto_select,
                            work_dir, 
                            daily_budget=daily_stats['budget_remaining'],
                            max_comments=max_comments
                        )
                        st.session_state.ai_selection_batch = selection_batch
            
            with col2:
                if st.button("🎲 随机选择", key="ai_random_select"):
                    if selected_criteria:
                        with st.spinner("正在随机筛选评论..."):
                            selection_batch = run_async_function(comment_selector.create_selection_batch,
                                work_dir,
                                selected_criteria,
                                max_comments
                            )
                            st.session_state.ai_selection_batch = selection_batch
                    else:
                        st.warning("请先选择筛选标准")
            
            # 显示筛选结果
            if 'ai_selection_batch' in st.session_state:
                batch = st.session_state.ai_selection_batch
                
                st.markdown("---")
                st.subheader("📋 筛选结果")
                
                # 显示筛选摘要
                summary = batch['summary']
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("总筛选数", summary['total_selected'])
                with col2:
                    st.metric("高优先级", summary['high_priority_count'])
                with col3:
                    st.metric("预估成本", f"${summary['total_estimated_cost']}")
                with col4:
                    st.metric("有图评论", summary['images_available'])
                
                # 评论列表
                st.subheader("🎯 候选评论")
                
                if batch['final_selections']:
                    # 创建评论选择复选框
                    selected_comments = []
                    
                    for i, item in enumerate(batch['final_selections']):
                        comment_data = item['comment_data']
                        analysis = item['analysis']
                        
                        with st.expander(
                            f"{'🔥' if analysis['priority'] == 'high' else '⭐' if analysis['priority'] == 'medium' else '💡'} "
                            f"{comment_data['nickname']} - 得分: {analysis['renovation_score']} - ${analysis['estimated_cost']}"
                        ):
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.write(f"**评论内容：**")
                                st.write(comment_data['content'])
                                
                                if comment_data.get('downloaded_images'):
                                    st.write(f"**图片：** {len(comment_data['downloaded_images'])} 张")
                                
                                st.write(f"**关键词：** {', '.join(analysis['keywords_matched'][:5])}")
                                st.write(f"**处理建议：** {analysis['processing_recommendation']}")
                            
                            with col2:
                                # 状态管理按钮
                                st.write("**状态管理：**")
                                col2_1, col2_2, col2_3 = st.columns(3)
                                
                                user_nickname = comment_data['nickname']
                                comment_content = comment_data['content']
                                work_title = selected_work['work_title']
                                
                                with col2_1:
                                    if st.button("⏳ 待处理", key=f"status_pending_{i}"):
                                        status_manager.add_or_update_comment_status(
                                            user_nickname=user_nickname,
                                            work_title=work_title,
                                            comment_content=comment_content,
                                            status=CommentStatus.PENDING,
                                            notes="手动标记为待处理",
                                            operator="系统用户"
                                        )
                                        st.success("已标记为待处理")
                                        st.rerun()
                                
                                with col2_2:
                                    if st.button("👀 观察中", key=f"status_watching_{i}"):
                                        status_manager.add_or_update_comment_status(
                                            user_nickname=user_nickname,
                                            work_title=work_title,
                                            comment_content=comment_content,
                                            status=CommentStatus.WATCHING,
                                            notes="手动标记为观察中",
                                            operator="系统用户"
                                        )
                                        st.success("已标记为观察中")
                                        st.rerun()
                                
                                with col2_3:
                                    if st.button("✅ 已完成", key=f"status_completed_{i}"):
                                        status_manager.add_or_update_comment_status(
                                            user_nickname=user_nickname,
                                            work_title=work_title,
                                            comment_content=comment_content,
                                            status=CommentStatus.COMPLETED,
                                            notes="手动标记为已完成",
                                            operator="系统用户"
                                        )
                                        st.success("已标记为已完成")
                                        st.rerun()
                                
                                # 小红书跳转按钮
                                if st.button("🔗 去作品评论区回复", key=f"xiaohongshu_direct_{i}"):
                                    # 尝试获取完整的评论数据用于智能定位
                                    full_comment_data = get_full_comment_data(comment_data, work_dir)
                                    
                                    work_url, location_guide = status_manager.generate_xiaohongshu_work_url(
                                        work_dir, user_nickname, full_comment_data
                                    )
                                    
                                    if work_url:
                                        # 显示智能定位信息
                                        st.info(location_guide)
                                        
                                        # 跳转链接
                                        st.markdown(f"[🚀 跳转到作品评论区]({work_url})")
                                        
                                        # 快速搜索指导
                                        st.markdown("**💡 快速定位技巧：**")
                                        st.markdown("1. 点击上方链接进入作品页面")
                                        st.markdown("2. 滚动到评论区")
                                        st.markdown("3. 使用 `Ctrl+F` (Windows) 或 `⌘+F` (Mac) 搜索关键词")
                                        st.markdown("4. 根据时间和图片特征快速定位")
                                        
                                        # 显示完整评论内容
                                        with st.expander("📖 完整评论内容", expanded=False):
                                            st.write(comment_content)
                                    else:
                                        st.error(f"❌ {location_guide}")
                                
                                st.markdown("---")
                                
                                if st.checkbox(
                                    f"选择处理",
                                    key=f"select_comment_{i}",
                                    value=analysis['priority'] == 'high'
                                ):
                                    selected_comments.append((comment_data, analysis))
                    
                    # 批量处理按钮
                    if selected_comments:
                        st.markdown("---")
                        st.subheader("🚀 批量AI处理")
                        
                        col1, col2, col3 = st.columns([1, 1, 2])
                        
                        with col1:
                            generate_images = st.checkbox("生成效果图", value=True, key="ai_generate_images")
                        
                        with col2:
                            styles_to_generate = st.multiselect(
                                "选择风格",
                                ["现代简约", "北欧自然", "中式现代", "工业复古"],
                                default=["现代简约", "北欧自然"],
                                key="ai_styles"
                            )
                        
                        total_cost = sum(analysis['estimated_cost'] for _, analysis in selected_comments)
                        st.write(f"**总预估成本：** ${total_cost:.2f}")
                        
                        if st.button("🤖 开始AI处理", key="ai_start_processing"):
                            if total_cost <= daily_stats['budget_remaining']:
                                # 创建处理任务
                                st.session_state.ai_processing_queue = selected_comments
                                st.session_state.ai_processing_config = {
                                    'generate_images': generate_images,
                                    'styles': styles_to_generate
                                }
                                st.success(f"✅ 已加入处理队列：{len(selected_comments)} 条评论")
                                st.rerun()
                            else:
                                st.error(f"❌ 预算不足！需要 ${total_cost:.2f}，剩余 ${daily_stats['budget_remaining']:.2f}")
            
            # 处理队列执行
            if 'ai_processing_queue' in st.session_state and st.session_state.ai_processing_queue:
                st.markdown("---")
                st.subheader("⚡ AI处理进行中")
                
                processing_queue = st.session_state.ai_processing_queue
                processing_config = st.session_state.ai_processing_config
                
                # 处理进度条
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 处理结果容器
                results_container = st.container()
                
                # 逐个处理评论
                for i, (comment_data, analysis) in enumerate(processing_queue):
                    try:
                        # 更新进度
                        progress = (i + 1) / len(processing_queue)
                        progress_bar.progress(progress)
                        status_text.text(f"正在处理第 {i+1}/{len(processing_queue)} 条评论...")
                        
                        # 处理单个评论
                        with results_container:
                            with st.expander(f"🔄 处理中：{comment_data['nickname']}", expanded=True):
                                result_placeholder = st.empty()
                                
                                # 执行AI处理
                                processing_result = run_async_function(reply_generator.process_renovation_request,
                                    comment_data,
                                    generate_images=processing_config['generate_images'],
                                    styles_to_generate=processing_config['styles']
                                )
                                
                                if processing_result['success']:
                                    # 显示处理结果
                                    result_placeholder.success(f"✅ 处理完成！成本：${processing_result['total_cost']:.4f}")
                                    
                                    # 显示分析结果
                                    if 'analysis' in processing_result['processing_stages']:
                                        st.write("**🔍 房屋分析：**")
                                        st.write(processing_result['processing_stages']['analysis']['analysis'][:300] + "...")
                                    
                                    # 显示改造方案
                                    if 'renovation_planning' in processing_result['processing_stages']:
                                        st.write("**🏗️ 改造方案：**")
                                        st.write(processing_result['processing_stages']['renovation_planning']['renovation_plans'][:300] + "...")
                                    
                                    # 显示生成的图片
                                    if processing_config['generate_images']:
                                        generated_images = processing_result['processing_stages'].get('image_generation', [])
                                        successful_images = [img for img in generated_images if img.get('success')]
                                        if successful_images:
                                            st.write(f"**🎨 生成效果图：** {len(successful_images)} 张")
                                    
                                    # 显示智能回复
                                    if 'reply_generation' in processing_result['processing_stages']:
                                        reply_result = processing_result['processing_stages']['reply_generation']
                                        if reply_result['success']:
                                            st.write("**💬 智能回复选项：**")
                                            
                                            # 创建回复选项的标签页
                                            reply_tabs = st.tabs(["详细专业版", "简洁实用版", "互动引导版"])
                                            
                                            replies = reply_result['replies'].split('## 版本')[1:]  # 分割不同版本
                                            for j, reply_content in enumerate(replies[:3]):
                                                with reply_tabs[j]:
                                                    st.text_area(
                                                        f"回复内容",
                                                        value=reply_content.strip(),
                                                        height=150,
                                                        key=f"reply_{i}_{j}"
                                                    )
                                                    
                                                    col_copy, col_xiaohongshu = st.columns(2)
                                                    with col_copy:
                                                        if st.button(f"📋 复制回复", key=f"copy_reply_{i}_{j}"):
                                                            # TODO: 实现复制到剪贴板功能
                                                            st.success("回复内容已准备，可手动复制")
                                                    
                                                    with col_xiaohongshu:
                                                        if st.button(f"🔗 去作品评论区回复", key=f"xiaohongshu_find_{i}_{j}"):
                                                            # 生成小红书作品评论区URL
                                                            user_nickname = comment_data['nickname']
                                                            work_url, location_guide = status_manager.generate_xiaohongshu_work_url(
                                                                work_dir, user_nickname, comment_data
                                                            )
                                                            
                                                            if work_url:
                                                                # 标记评论状态为已完成（用户手动回复）
                                                                status_manager.add_or_update_comment_status(
                                                                    user_nickname=user_nickname,
                                                                    work_title=selected_work['work_title'],
                                                                    comment_content=comment_data['content'],
                                                                    status=CommentStatus.COMPLETED,
                                                                    notes=f"用户通过小红书手动回复 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                                                    operator="系统用户",
                                                                    reply_content=reply_content.strip()[:100] + "...",
                                                                    xiaohongshu_url=work_url
                                                                )
                                                                
                                                                # 显示智能定位信息
                                                                st.success("✅ 评论状态已标记为已完成")
                                                                
                                                                # 显示详细的定位指导
                                                                st.info(location_guide)
                                                                
                                                                # 跳转链接
                                                                st.markdown(f"[🚀 跳转到作品评论区]({work_url})")
                                                                
                                                                # 快速搜索指导
                                                                st.markdown("**💡 快速定位技巧：**")
                                                                st.markdown("1. 点击上方链接进入作品页面")
                                                                st.markdown("2. 滚动到评论区")
                                                                st.markdown("3. 使用 `Ctrl+F` (Windows) 或 `⌘+F` (Mac) 搜索关键词")
                                                                st.markdown("4. 根据时间和图片特征快速定位")
                                                                
                                                                # 显示完整评论内容
                                                                with st.expander("📖 完整评论内容", expanded=False):
                                                                    st.write(comment_data['content'])
                                                            else:
                                                                st.error(f"❌ {location_guide}")
                                else:
                                    result_placeholder.error(f"❌ 处理失败：{processing_result.get('error', '未知错误')}")
                                
                    except Exception as e:
                        st.error(f"处理评论时发生异常：{str(e)}")
                
                # 处理完成
                progress_bar.progress(1.0)
                status_text.text("✅ 全部处理完成！")
                
                # 清理处理队列
                del st.session_state.ai_processing_queue
                del st.session_state.ai_processing_config
                
                # 更新统计信息
                updated_stats = reply_generator.get_daily_statistics()
                st.success(f"🎉 批量处理完成！今日已使用预算：${updated_stats['cost_used']:.2f}")
        
        # 处理历史
        st.markdown("---")
        st.subheader("📚 处理历史")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🔄 刷新历史", key="ai_refresh_history"):
                st.rerun()
        
        with col2:
            history_limit = st.number_input("显示数量", min_value=5, max_value=100, value=20, key="ai_history_limit")
        
        # 显示选择历史
        selection_history = comment_selector.get_selection_history(history_limit)
        if selection_history:
            st.write("**📋 选择历史**")
            history_df = pd.DataFrame(selection_history)
            st.dataframe(history_df, use_container_width=True)
        
        # 显示处理历史
        processing_history = reply_generator.get_processing_history(history_limit)
        if processing_history:
            st.write("**🤖 处理历史**")
            processing_df = pd.DataFrame(processing_history)
            st.dataframe(processing_df, use_container_width=True)
    
    # 结果显示
    if st.session_state.results:
        st.markdown("---")
        st.header("📈 提取结果")
        
        # 结果统计
        total = len(st.session_state.results)
        success_count = len([r for r in st.session_state.results if r['status'] == 'success'])
        failed_count = total - success_count
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总数", total)
        with col2:
            st.metric("成功", success_count)
        with col3:
            st.metric("失败", failed_count)
        
        # 详细结果表格
        st.subheader("详细结果")
        result_data = []
        for result in st.session_state.results:
            status_emoji = "✅" if result['status'] == 'success' else "❌"
            result_data.append({
                '状态': f"{status_emoji} {result['status']}",
                '作品ID': result['note_id'],
                '链接': result['url'][:50] + "..." if len(result['url']) > 50 else result['url'],
                '消息': result['message']
            })
        
        st.dataframe(result_data, use_container_width=True)
        
        # 输出目录信息
        output_path = Path(work_path)
        if output_path.exists():
            st.subheader("📂 输出目录")
            st.code(str(output_path.absolute()))
            
            # 列出生成的文件夹
            if list(output_path.iterdir()):
                st.write("生成的文件夹:")
                for item in output_path.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        st.write(f"📁 {item.name}")

if __name__ == "__main__":
    main()