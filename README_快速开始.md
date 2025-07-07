# 小红书评论提取器 - 快速开始 🚀

## 🎯 解决终端运行报错

如果遇到 `zsh: no such file or directory: .../venv/bin/python` 错误，请使用以下方法：

## ✅ 推荐方法（一键启动）

```bash
# 方法1: 使用Python启动脚本（推荐）
python3 run_extractor.py ui

# 方法2: 使用Shell脚本
./run_extractor.sh ui
```

## 🛠️ 手动方法

如果自动脚本无法使用，可以手动执行：

```bash
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install --upgrade pip
pip install -r requirements.txt
pip install playwright aiohttp streamlit
playwright install chromium

# 4. 运行程序
python dynamic_comment_extractor.py  # 命令行版本
# 或
python start_ui.py  # Web UI版本
```

## 📋 启动选项

| 命令 | 说明 |
|------|------|
| `python3 run_extractor.py ui` | 启动Web UI界面（推荐） |
| `python3 run_extractor.py cli` | 运行命令行版本 |
| `python3 run_extractor.py test` | 测试环境配置 |

## 🌐 Web UI界面

启动后会自动打开浏览器，访问：`http://localhost:8501`

### UI功能特色：
- 📝 手动输入链接（单个或批量）
- 🔍 自动验证链接格式
- 📊 实时进度显示
- 📋 详细处理日志
- 📈 结果统计和导出

## ⚠️ 常见问题

### Q: Python版本问题
A: 需要Python 3.9或更高版本
```bash
python3 --version  # 检查版本
```

### Q: 虚拟环境创建失败
A: 确保有python3-venv包
```bash
# Ubuntu/Debian
sudo apt install python3-venv

# macOS (通常已包含)
brew install python3
```

### Q: 依赖安装失败
A: 检查网络连接，或使用国内镜像
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple/
```

### Q: Playwright浏览器下载失败
A: 可能需要设置代理或手动下载
```bash
playwright install chromium --force
```

## 🎉 功能特性

- 🖼️ **评论图片自动下载** - 智能命名和组织
- 📁 **有序文件管理** - 按作品和用户分类
- 🔐 **持久化登录** - 一次登录，长期使用
- 📄 **全量评论获取** - 支持大量评论的作品
- 🌐 **现代Web界面** - 友好的用户体验

## 📂 输出结构

```
Comments_Dynamic/
├── 作品标题1/
│   ├── 用户昵称1/
│   │   ├── images/
│   │   │   ├── 用户昵称_时间_内容_1.jpg
│   │   │   └── 用户昵称_时间_内容_2.png
│   │   ├── 评论内容.txt
│   │   └── 原始数据.json
│   └── 用户昵称2/
└── 作品标题2/
```

## 🤝 获取帮助

如果仍有问题，请：
1. 检查Python版本和网络连接
2. 查看详细日志信息
3. 使用 `python3 run_extractor.py test` 测试环境

享受便捷的评论提取体验！🎉