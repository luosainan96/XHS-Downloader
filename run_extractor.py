#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小红书评论提取器 - 启动脚本
解决虚拟环境和依赖问题
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """主函数"""
    print("🖼️ 小红书评论提取器 - 启动脚本")
    print("=" * 50)
    
    # 获取项目根目录
    project_root = Path(__file__).parent
    venv_path = project_root / "venv"
    
    # 检查是否在正确目录
    if not (project_root / "dynamic_comment_extractor.py").exists():
        print("❌ 错误：请在项目根目录运行此脚本")
        return 1
    
    # 检查虚拟环境
    if not venv_path.exists():
        print("📦 创建虚拟环境...")
        try:
            subprocess.run([sys.executable, "-m", "venv", "venv"], 
                         cwd=project_root, check=True)
            print("✅ 虚拟环境创建成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ 创建虚拟环境失败: {e}")
            return 1
    
    # 确定Python解释器路径
    if os.name == 'nt':  # Windows
        python_path = venv_path / "Scripts" / "python.exe"
        pip_path = venv_path / "Scripts" / "pip.exe"
    else:  # Unix/Linux/macOS
        python_path = venv_path / "bin" / "python"
        pip_path = venv_path / "bin" / "pip"
    
    if not python_path.exists():
        print("❌ 错误：虚拟环境中的Python解释器不存在")
        return 1
    
    print(f"🔧 使用Python: {python_path}")
    
    # 检查依赖
    print("📦 检查依赖...")
    try:
        # 检查是否需要安装依赖
        result = subprocess.run([str(python_path), "-c", 
                               "import streamlit, playwright, aiohttp; print('依赖已安装')"],
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            print("📦 安装依赖...")
            
            # 升级pip
            subprocess.run([str(pip_path), "install", "--upgrade", "pip"], 
                         check=True)
            
            # 安装requirements.txt
            requirements_file = project_root / "requirements.txt"
            if requirements_file.exists():
                subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], 
                             check=True)
            
            # 安装额外依赖
            subprocess.run([str(pip_path), "install", "playwright", "aiohttp", "streamlit"], 
                         check=True)
            
            # 安装playwright浏览器
            subprocess.run([str(python_path), "-m", "playwright", "install", "chromium"], 
                         check=True)
            
            print("✅ 依赖安装完成")
        else:
            print("✅ 依赖已存在")
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 安装依赖失败: {e}")
        return 1
    
    # 根据参数决定运行方式
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        mode = "help"
    
    try:
        if mode == "ui":
            print("🌐 启动Web UI界面...")
            os.chdir(project_root)
            
            # 优先使用修复版UI并指定端口8502避免冲突
            ui_file_fixed = project_root / "comment_extractor_ui_fixed.py"
            if ui_file_fixed.exists():
                print("📱 使用修复版UI界面 (端口8502)")
                subprocess.run([str(python_path), "-m", "streamlit", "run", 
                               str(ui_file_fixed), "--server.port", "8502"])
            else:
                subprocess.run([str(python_path), "start_ui.py"])
            
        elif mode == "cli":
            print("⌨️ 运行命令行版本...")
            os.chdir(project_root)
            subprocess.run([str(python_path), "dynamic_comment_extractor.py"])
            
        elif mode == "test":
            print("🧪 测试环境...")
            result = subprocess.run([str(python_path), "-c", 
                                   "import dynamic_comment_extractor; print('✅ 环境测试通过')"],
                                  cwd=project_root)
            return result.returncode
            
        else:
            print("\n📋 使用方式：")
            print("  python run_extractor.py ui    # 启动Web UI界面（推荐）")
            print("  python run_extractor.py cli   # 运行命令行版本")
            print("  python run_extractor.py test  # 测试环境")
            print("\n💡 推荐使用：python run_extractor.py ui")
            print("\n🔧 如果遇到问题，请检查：")
            print("  - Python 3.9+ 版本")
            print("  - 网络连接正常")
            print("  - 有足够的磁盘空间")
            
    except KeyboardInterrupt:
        print("\n👋 用户取消操作")
        return 0
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())