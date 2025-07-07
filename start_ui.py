#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动小红书评论提取器Web UI
"""

import subprocess
import sys
import os
from pathlib import Path

def main():
    """启动Streamlit应用"""
    print("🖼️ 小红书评论提取器 - Web UI")
    print("=" * 50)
    
    # 获取当前脚本目录
    current_dir = Path(__file__).parent
    
    # 优先使用修复版UI
    ui_file_fixed = current_dir / "comment_extractor_ui_fixed.py"
    ui_file_original = current_dir / "comment_extractor_ui.py"
    
    if ui_file_fixed.exists():
        ui_file = ui_file_fixed
        print("📱 使用修复版UI界面")
    elif ui_file_original.exists():
        ui_file = ui_file_original
        print("📱 使用原版UI界面")
    else:
        ui_file = ui_file_original
    
    if not ui_file.exists():
        print("❌ 错误：找不到UI文件 comment_extractor_ui.py")
        return
    
    print(f"📂 工作目录: {current_dir}")
    print(f"🚀 启动UI应用: {ui_file}")
    print("-" * 50)
    print("💡 提示：")
    print("   - 应用将在浏览器中自动打开")
    print("   - 默认地址：http://localhost:8501")
    print("   - 按 Ctrl+C 停止应用")
    print("-" * 50)
    
    try:
        # 启动Streamlit应用
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            str(ui_file),
            "--server.address", "localhost",
            "--server.port", "8501",
            "--browser.gatherUsageStats", "false"
        ]
        
        subprocess.run(cmd, cwd=str(current_dir))
        
    except KeyboardInterrupt:
        print("\n👋 应用已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        print("\n💡 请确保已安装Streamlit:")
        print("   python3 -m pip install streamlit")

if __name__ == "__main__":
    main()