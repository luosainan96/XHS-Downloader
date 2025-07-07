#!/bin/bash
# 小红书评论提取器运行脚本

echo "🖼️ 小红书评论提取器 - 启动脚本"
echo "=========================================="

# 检查是否在正确的目录
if [ ! -f "dynamic_comment_extractor.py" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
    
    echo "📦 激活虚拟环境并安装依赖..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install playwright aiohttp streamlit
    playwright install chromium
    echo "✅ 依赖安装完成"
else
    echo "✅ 虚拟环境已存在"
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 检查要运行的脚本
if [ "$1" = "ui" ]; then
    echo "🌐 启动Web UI界面..."
    python start_ui.py
elif [ "$1" = "cli" ]; then
    echo "⌨️ 运行命令行版本..."
    python dynamic_comment_extractor.py
else
    echo "📋 使用方式："
    echo "  ./run_extractor.sh ui   # 启动Web UI界面"
    echo "  ./run_extractor.sh cli  # 运行命令行版本"
    echo ""
    echo "💡 推荐使用UI界面：./run_extractor.sh ui"
fi