#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书评论提取器 - Web UI界面
使用Streamlit创建用户友好的界面
"""

import asyncio
import streamlit as st
import time
from pathlib import Path
import json
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor
import queue

from dynamic_comment_extractor import DynamicCommentExtractor

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
        st.session_state.extraction_status = 'idle'  # idle, running, completed, error
    if 'extraction_progress' not in st.session_state:
        st.session_state.extraction_progress = 0
    if 'current_task' not in st.session_state:
        st.session_state.current_task = ""
    if 'extraction_logs' not in st.session_state:
        st.session_state.extraction_logs = []
    if 'extractor' not in st.session_state:
        st.session_state.extractor = None
    if 'results' not in st.session_state:
        st.session_state.results = None
    if 'progress_queue' not in st.session_state:
        st.session_state.progress_queue = queue.Queue()

def add_log(message: str, level: str = "info"):
    """添加日志消息"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.extraction_logs.append({
        'time': timestamp,
        'level': level,
        'message': message
    })

def validate_xhs_url(url: str) -> bool:
    """验证小红书URL格式"""
    if not url:
        return False
    
    # 检查是否包含小红书域名
    if 'xiaohongshu.com' not in url:
        return False
    
    # 检查是否包含explore路径
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

def update_progress(progress: float, task: str):
    """更新进度和任务信息"""
    try:
        st.session_state.progress_queue.put({
            'type': 'progress',
            'progress': progress,
            'task': task
        })
    except:
        pass

def update_log(message: str, level: str = "info"):
    """更新日志"""
    try:
        st.session_state.progress_queue.put({
            'type': 'log',
            'message': message,
            'level': level
        })
    except:
        pass

async def run_extraction(urls: list, cookie: str, work_path: str):
    """运行评论提取的异步函数"""
    try:
        # 通过队列更新状态
        st.session_state.progress_queue.put({'type': 'status', 'status': 'running'})
        update_log("开始初始化评论提取器...")
        
        # 创建提取器实例
        extractor = DynamicCommentExtractor(
            work_path=work_path,
            cookie=cookie,
            use_persistent_session=True
        )
        
        total_urls = len(urls)
        results = []
        
        for i, url in enumerate(urls):
            note_id = extract_note_id_simple(url)
            current_task = f"处理作品 {i+1}/{total_urls}: {note_id}"
            update_progress((i / total_urls) * 100, current_task)
            update_log(f"开始{current_task}")
            
            try:
                # 提取评论
                success = await extractor.extract_comments(url)
                
                if success:
                    update_log(f"✅ 作品 {note_id} 处理成功", "success")
                    results.append({
                        'url': url,
                        'note_id': note_id,
                        'status': 'success',
                        'message': '处理成功'
                    })
                else:
                    update_log(f"❌ 作品 {note_id} 处理失败", "error")
                    results.append({
                        'url': url,
                        'note_id': note_id,
                        'status': 'failed',
                        'message': '处理失败'
                    })
            except Exception as e:
                update_log(f"❌ 作品 {note_id} 发生异常: {str(e)}", "error")
                results.append({
                    'url': url,
                    'note_id': note_id,
                    'status': 'error',
                    'message': f'异常: {str(e)}'
                })
        
        # 完成处理
        update_progress(100, "处理完成")
        st.session_state.progress_queue.put({'type': 'status', 'status': 'completed'})
        st.session_state.progress_queue.put({'type': 'results', 'results': results})
        success_count = len([r for r in results if r['status'] == 'success'])
        update_log(f"🎉 所有作品处理完成！成功: {success_count}/{total_urls}", "success")
        
    except Exception as e:
        st.session_state.progress_queue.put({'type': 'status', 'status': 'error'})
        update_log(f"❌ 提取过程发生错误: {str(e)}", "error")

def run_extraction_sync(urls: list, cookie: str, work_path: str):
    """同步包装器，用于在线程中运行异步函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_extraction(urls, cookie, work_path))
    finally:
        loop.close()

def main():
    """主界面函数"""
    init_session_state()
    
    # 主标题
    st.title("🖼️ 小红书评论提取器")
    st.markdown("---")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("⚙️ 配置设置")
        
        # Cookie输入
        st.subheader("1. Cookie设置")
        cookie_input = st.text_area(
            "请输入小红书Cookie:",
            height=100,
            help="用于登录验证，可在浏览器开发者工具中获取"
        )
        
        # 输出路径设置
        st.subheader("2. 输出设置")
        work_path = st.text_input(
            "输出目录:",
            value="Comments_Dynamic",
            help="评论和图片的保存目录"
        )
        
        # 功能说明
        st.subheader("📋 功能说明")
        st.markdown("""
        **本工具支持：**
        - 🖼️ 自动下载评论图片
        - 📝 智能文件命名
        - 📁 有序文件组织
        - 🔐 持久化登录状态
        - 📄 分页获取全部评论
        """)
    
    # 主内容区域
    col1, col2 = st.columns([2, 1])
    
    with col1:
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
                help="请输入完整的小红书作品链接"
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
        
        can_start = (
            len(urls) > 0 and 
            cookie_input.strip() and 
            st.session_state.extraction_status != 'running'
        )
        
        if st.button(
            f"🚀 开始提取评论 ({len(urls)} 个作品)" if urls else "🚀 开始提取评论",
            disabled=not can_start,
            type="primary"
        ):
            if not cookie_input.strip():
                st.error("请先输入Cookie!")
            elif not urls:
                st.error("请先输入有效的作品链接!")
            else:
                # 重置状态
                st.session_state.extraction_status = 'idle'
                st.session_state.extraction_progress = 0
                st.session_state.current_task = ""
                st.session_state.extraction_logs = []
                st.session_state.results = None
                # 清空队列
                while not st.session_state.progress_queue.empty():
                    try:
                        st.session_state.progress_queue.get_nowait()
                    except:
                        break
                
                # 在后台线程中运行提取
                executor = ThreadPoolExecutor(max_workers=1)
                executor.submit(run_extraction_sync, urls, cookie_input.strip(), work_path)
                
                st.rerun()
    
    with col2:
        st.header("📊 提取状态")
        
        # 处理队列中的更新
        updates_processed = 0
        while not st.session_state.progress_queue.empty() and updates_processed < 100:
            try:
                update = st.session_state.progress_queue.get_nowait()
                updates_processed += 1
                
                if update['type'] == 'status':
                    st.session_state.extraction_status = update['status']
                elif update['type'] == 'progress':
                    st.session_state.extraction_progress = update['progress']
                    st.session_state.current_task = update['task']
                elif update['type'] == 'log':
                    add_log(update['message'], update['level'])
                elif update['type'] == 'results':
                    st.session_state.results = update['results']
            except:
                break
        
        # 状态指示器
        if st.session_state.extraction_status == 'idle':
            st.info("等待开始...")
        elif st.session_state.extraction_status == 'running':
            st.warning("正在提取中...")
            
            # 进度条
            progress_bar = st.progress(st.session_state.extraction_progress / 100)
            st.write(f"进度: {st.session_state.extraction_progress:.1f}%")
            
            # 当前任务
            if st.session_state.current_task:
                st.write(f"当前任务: {st.session_state.current_task}")
            
            # 自动刷新
            time.sleep(2)
            st.rerun()
            
        elif st.session_state.extraction_status == 'completed':
            st.success("✅ 提取完成!")
        elif st.session_state.extraction_status == 'error':
            st.error("❌ 提取失败!")
        
        # 日志显示
        if st.session_state.extraction_logs:
            st.subheader("📋 处理日志")
            
            # 创建日志容器
            log_container = st.container()
            
            with log_container:
                # 只显示最新的10条日志
                recent_logs = st.session_state.extraction_logs[-10:]
                
                for log in recent_logs:
                    if log['level'] == 'success':
                        st.success(f"{log['time']} - {log['message']}")
                    elif log['level'] == 'error':
                        st.error(f"{log['time']} - {log['message']}")
                    else:
                        st.info(f"{log['time']} - {log['message']}")
    
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
            st.metric("成功", success_count, delta=None, delta_color="normal")
        with col3:
            st.metric("失败", failed_count, delta=None, delta_color="inverse")
        
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