#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试版UI - 验证按钮点击功能
"""

import streamlit as st
import time
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="测试UI - 按钮点击",
    page_icon="🧪",
    layout="wide"
)

def init_session_state():
    """初始化会话状态"""
    if 'test_status' not in st.session_state:
        st.session_state.test_status = 'idle'
    if 'test_logs' not in st.session_state:
        st.session_state.test_logs = []
    if 'click_count' not in st.session_state:
        st.session_state.click_count = 0

def add_test_log(message: str):
    """添加测试日志"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.test_logs.append(f"{timestamp} - {message}")

def main():
    """主界面"""
    init_session_state()
    
    st.title("🧪 UI点击测试")
    st.markdown("---")
    
    # 测试区域
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📝 测试输入")
        
        # 模拟链接输入
        test_url = st.text_input(
            "测试链接:",
            value="https://www.xiaohongshu.com/explore/685613550000000010027087?xsec_token=test",
            help="用于测试URL验证"
        )
        
        # 模拟Cookie输入
        test_cookie = st.text_area(
            "测试Cookie:",
            value="test_cookie=123456",
            height=100,
            help="用于测试Cookie验证"
        )
        
        # 验证逻辑
        url_valid = bool(test_url and 'xiaohongshu.com' in test_url and '/explore/' in test_url)
        cookie_valid = bool(test_cookie and test_cookie.strip())
        
        # 显示验证状态
        if url_valid:
            st.success("✅ URL格式有效")
        else:
            st.error("❌ URL格式无效")
            
        if cookie_valid:
            st.success("✅ Cookie格式有效")
        else:
            st.error("❌ Cookie格式无效")
        
        # 测试按钮
        can_click = url_valid and cookie_valid
        
        st.markdown("---")
        
        if st.button(
            "🧪 测试点击功能",
            disabled=not can_click,
            type="primary"
        ):
            # 立即更新状态
            st.session_state.click_count += 1
            st.session_state.test_status = 'clicked'
            add_test_log(f"按钮被点击了！第 {st.session_state.click_count} 次")
            add_test_log("开始模拟处理...")
            
            # 模拟处理过程
            for i in range(3):
                add_test_log(f"处理步骤 {i+1}/3...")
                time.sleep(0.5)
            
            add_test_log("✅ 模拟处理完成！")
            st.session_state.test_status = 'completed'
            
            # 立即重新运行以显示更新
            st.rerun()
    
    with col2:
        st.header("📊 测试状态")
        
        # 状态显示
        if st.session_state.test_status == 'idle':
            st.info("💤 等待测试...")
        elif st.session_state.test_status == 'clicked':
            st.warning("⏳ 正在处理...")
        elif st.session_state.test_status == 'completed':
            st.success("✅ 处理完成!")
        
        # 点击计数
        if st.session_state.click_count > 0:
            st.metric("点击次数", st.session_state.click_count)
        
        # 日志显示
        if st.session_state.test_logs:
            st.subheader("📋 测试日志")
            for log in st.session_state.test_logs[-10:]:  # 显示最新10条
                st.text(log)
        
        # 重置按钮
        if st.button("🔄 重置测试"):
            st.session_state.test_status = 'idle'
            st.session_state.test_logs = []
            st.session_state.click_count = 0
            add_test_log("测试已重置")
            st.rerun()
    
    # 问题诊断区域
    st.markdown("---")
    st.header("🔍 问题诊断")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("✅ 正常情况")
        st.write("- 按钮可以点击")
        st.write("- 状态立即更新")
        st.write("- 日志正常显示")
        st.write("- 页面自动刷新")
    
    with col2:
        st.subheader("❌ 异常情况")
        st.write("- 按钮点击无反应")
        st.write("- 状态不更新")
        st.write("- 日志不显示")
        st.write("- 页面不刷新")
    
    with col3:
        st.subheader("🔧 解决方案")
        st.write("- 检查JavaScript错误")
        st.write("- 验证网络连接")
        st.write("- 重启Streamlit服务")
        st.write("- 清除浏览器缓存")

if __name__ == "__main__":
    main()