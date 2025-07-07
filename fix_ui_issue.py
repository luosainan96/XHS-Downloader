#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复UI点击无反应问题
"""

import sys
from pathlib import Path
import subprocess

def main():
    """主修复函数"""
    print("🔧 小红书评论提取器 - UI问题修复")
    print("=" * 50)
    
    print("🔍 问题分析：")
    print("- 点击'开始提取评论'按钮没有反应")
    print("- 可能原因：Streamlit异步处理和线程池冲突")
    print()
    
    print("✅ 解决方案：")
    print("1. 使用修复版UI界面")
    print("2. 简化异步处理逻辑") 
    print("3. 优化状态管理")
    print()
    
    # 检查文件
    current_dir = Path.cwd()
    fixed_ui = current_dir / "comment_extractor_ui_fixed.py"
    
    if fixed_ui.exists():
        print("✅ 修复版UI文件已存在")
    else:
        print("❌ 修复版UI文件不存在")
        return 1
    
    print("\n🚀 启动修复版UI...")
    print("=" * 50)
    
    # 检查虚拟环境
    venv_path = current_dir / "venv"
    if venv_path.exists():
        if sys.platform == "win32":
            python_path = venv_path / "Scripts" / "python.exe"
        else:
            python_path = venv_path / "bin" / "python"
        
        if python_path.exists():
            print(f"🔧 使用虚拟环境: {python_path}")
            try:
                subprocess.run([
                    str(python_path), "-m", "streamlit", "run",
                    str(fixed_ui),
                    "--server.address", "localhost",
                    "--server.port", "8501",
                    "--browser.gatherUsageStats", "false"
                ])
            except KeyboardInterrupt:
                print("\n👋 UI已关闭")
            except Exception as e:
                print(f"❌ 启动失败: {e}")
                return 1
        else:
            print("❌ 虚拟环境Python不存在")
            return 1
    else:
        # 使用系统Python
        print("🔧 使用系统Python")
        try:
            subprocess.run([
                "python3", "-m", "streamlit", "run",
                str(fixed_ui),
                "--server.address", "localhost", 
                "--server.port", "8501",
                "--browser.gatherUsageStats", "false"
            ])
        except KeyboardInterrupt:
            print("\n👋 UI已关闭")
        except Exception as e:
            print(f"❌ 启动失败: {e}")
            print("\n💡 请先安装Streamlit:")
            print("pip3 install streamlit")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())