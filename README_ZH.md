# 🔬 PaperPal

一款由 AI 驱动的智能论文研究助手，通过个性化评分和交互式终端界面，帮助您高效发现并分析 arXiv 上的最新学术论文。

[English Documentation](README.md)

## ✨ 核心特性

- 🎯 **智能推荐**：AI 深度分析论文内容，根据您的研究兴趣精准打分。
- ⚡ **双搜索模式**：支持**全量遍历搜索**（深度扫描所选领域内的所有论文，确保不漏掉任何相关文献）或快速关键词筛选（速度快）。
- 🗣️ **自然语言交互**：直接说出您的需求（例如："找一下最近一周关于大模型推理的论文"），还能就查找到的结果进行进一步分析和讨论。
- 🧠 **偏好自动学习**：根据您的反馈自动学习研究口味，并动态压缩记忆以优化推荐。
- 📊 **现代化终端 UI**：支持进度条显示、彩色评分面板和富文本渲染。
- 💾 **自动导出**：搜索结果和 AI 综述会自动保存为美观的 Markdown 文件。

![CLI 界面展示](assets/screenshot.jpeg)

---

## 🚀 快速开始

### 1. 安装
```bash
git clone https://github.com/Shenzhi-Wang/PaperPal.git
cd PaperPal
pip install -e .
```

### 2. 配置
首次运行时，程序会自动提示您输入 API 密钥。您也可以手动创建 `.env` 文件：
```env
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://api.openai.com/v1  # 支持 DeepSeek 等兼容接口
OPENAI_MODEL=gpt-4o-mini
```

### 3. 运行
```bash
# 进入交互模式 (推荐)
paper

# 或使用快速搜索命令
paper search -t "3 days" -T "强化学习"
```

---

## 🎮 交互式命令

| 命令          | 说明                                   |
| ------------- | -------------------------------------- |
| `/search`     | 切换搜索模式 (关键词/遍历)             |
| `/categories` | 交互式勾选 ArXiv 搜索类别 (↑↓ + 空格)  |
| `/summary`    | 针对当前或历史搜索结果生成深度研究综述 |
| `/memory`     | 查看或手动调整 AI 记录的个人研究偏好   |
| `/files`      | 浏览并查看历史搜索结果文件             |
| `/settings`   | 调整语言、并发线程数、输出目录等设置   |
| `/quit`       | 退出程序                               |

---

## 🤖 智能特性

### ⌨️ 现代导航体验
无需输入数字。在所有菜单和类别选择列表中，使用：
- **↑ / ↓**：移动光标
- **空格 (Space)**：切换勾选状态（仅类别选择）
- **回车 (Enter)**：确认选择
- **Esc / q**：返回上一级

### 📝 智能研究综述
PaperPal 不仅仅是列出论文。使用 `/summary` 命令，AI 会分析多篇论文，识别研究趋势、通用方法论、以及该领域的关键创新点。

### 🧠 动态偏好记忆
PaperPal 会越用越懂你。它会记录您的反馈（如：“第1篇很有用，我不喜欢第3篇这种类型的”），并维护一个自然语言形式的“研究画像”记忆。

---

## 🛠️ 进阶配置
编辑 `config.py` 可以调整更多高级参数：
- `AUTO_SUMMARY`: 搜索完成后自动生成研究综述 (默认：True)。
- `DEFAULT_ARXIV_CATEGORIES`: 默认搜索的 arXiv 领域。
- `INTEREST_THRESHOLD`: 显示论文的最低评分阈值 (0-10)。
- `MAX_WORKERS`: AI 评分时的并行线程数。

---

## 📄 开源协议
MIT License. Created by [Shenzhi-Wang](https://github.com/Shenzhi-Wang).
