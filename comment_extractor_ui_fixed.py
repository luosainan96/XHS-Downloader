#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书评论提取器 - 修复版Web UI界面
解决点击无反应的问题
"""

import asyncio
import streamlit as st
import time
from pathlib import Path
import json
from datetime import datetime
import threading
import re

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

def add_log(message: str, level: str = "info"):
    """添加日志消息"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.extraction_logs.append({
        'time': timestamp,
        'level': level,
        'message': message
    })
    st.session_state.last_update = time.time()

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

def run_extraction_simple(urls: list, cookie: str, work_path: str, max_comments: int = None):
    """简化的提取函数，直接在主线程中运行"""
    try:
        st.session_state.extraction_status = 'running'
        if max_comments:
            add_log(f"开始初始化评论提取器... (限制数量: {max_comments})")
        else:
            add_log("开始初始化评论提取器...")
        
        # 创建一个新的事件循环用于异步操作
        async def async_extraction():
            extractor = DynamicCommentExtractor(
                work_path=work_path,
                cookie=cookie,
                use_persistent_session=True,
                max_comments=max_comments
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
        
        # 在新的事件循环中运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
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
        
        # Cookie输入
        st.subheader("1. Cookie设置")
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
            cookie_input.strip() and 
            st.session_state.extraction_status not in ['running']
        )
        
        # 状态检查和错误提示
        if not cookie_input.strip():
            st.warning("⚠️ 请先输入Cookie!")
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
            
            # 显示开始信息
            st.info("🚀 开始提取评论，请稍候...")
            
            # 立即重新运行以显示状态更新
            st.rerun()
    
    with col2:
        st.header("📊 提取状态")
        
        # 状态显示
        if st.session_state.extraction_status == 'idle':
            st.info("💤 等待开始...")
            
        elif st.session_state.extraction_status == 'starting':
            st.warning("🚀 正在启动...")
            # 在这里运行提取
            if 'urls' in locals() and 'cookie_input' in locals() and urls and cookie_input.strip():
                run_extraction_simple(urls, cookie_input.strip(), work_path, max_comments)
                st.rerun()
            
        elif st.session_state.extraction_status == 'running':
            st.warning("⏳ 正在提取中...")
            
            # 进度条
            if st.session_state.extraction_progress > 0:
                st.progress(st.session_state.extraction_progress / 100)
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