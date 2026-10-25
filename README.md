# 我们的选择——**TaskMate Duo · 能说会做的待办智能助理**

> 队友 A 的「大脑」＋ 成员 B 的「界面与语音」，合并成一个完整项目。

> **两边通过 `bridge/` 适配层共用同一个数据库，谁建的任务对方立刻能看到。**

## 要求

使用现代 AI 工具构建一个具备 语言交互（会说） 和 行动执行（会做） 能力的智能体（Agent）。

智能体应能够在指定场景中接收自然语言输入、理解任务意图，并自动完成相应操作。

## 小组成员

3224004344，3224004347， 3224004382

## 小组分工

3224004344 (Agent 核心逻辑)

3224004347 (工具层开发)

3224004382 (前端与文档)

## 技术要求：

推荐使用 Model Context Protocol (MCP) 框架或兼容框架；

智能体必须能：**自然语言对话（能说）**

执行操作或调用工具（会做），例如调用接口、运行脚本、处理文件等；

选择语言和框架：**Python**

## 核心功能
**🗣 自然语言交互**：无需手动填表，直接说“周三交作业，周五买牙膏”，自动解析入库。

**🛠 自动化任务管理**：自动判断优先级、估算耗时、识别截止时间。

**📅 智能日程规划**：一句“帮我安排今天”，自动按时长和优先级排期。

**📁 导出与记忆**：支持一键导出 Markdown 文件；具备跨会话记忆，永久记住你的称呼和习惯。

具体的说明

| 能力                |  说明                                                                          |
| ----------------- |  --------------------------------------------------------------------------- |
| 自然语言增删查改任务        |  `add_todo` / `list_todos` / `complete_todo` / `delete_todo`，自动推理优先级、耗时、截止时间 |
| 一键导出 Markdown     | `export_markdown`，界面上直接出现下载按钮                                               |
| 长期记忆（记住称呼/习惯）     |  `save_memory` → `data/user_memory.json`，界面侧栏可见                              |
| DSML 乱码自动拦截修复     |  DeepSeek 偶发输出乱码时的容错，原逻辑保留                                                   |
| 任务看板（统计/筛选/排序/导出） |  完成率进度条、逾期高亮、优先级徽章、CSV/Markdown 导出                                           |
| 🗂 多视图筛选 + 智能排序   | 按状态/关键字筛选，逾期优先的智能排序                                                         |
| 🔧 执行轨迹           | 每条回复下可展开，看到 Agent 真调用了哪些工具、传了什么参数                                           |
| 🎤 语音输入           | 按住录音说话 → 本地 faster-whisper 转文字 → 自动发送（离线可用）                                 |
| 🔊 语音播报           | edge-tts 把回复念出来                                                             |
| 离线演示模式            |  `USE_MOCK_LLM=1`，没网没 key 也能跑通全链路                                            |

---

## 技术栈
语言：Python 3.10+

大模型：DeepSeek / 通义千问（OpenAI 兼容协议）

前端界面：Streamlit

数据存储：SQLite3

协议规范：遵循 Model Context Protocol (MCP) Tool Schema

## 如何跑起来

```powershell

# 1. 装依赖
pip install -r requirements.txt

# 2. 配 key（复制模板后填入自己的）
copy .env.example .env
#    编辑 .env，填 DEEPSEEK_API_KEY=sk-xxx

# 3. 启动
.\run.ps1 web        # 网页界面 → http://localhost:8520
```

其他命令：

```powershell
.\run.ps1 cli        # 命令行版（同一个 Agent，不需要浏览器）
.\run.ps1 test       # 全部自动化测试（离线，不需要 key）
.\run.ps1 model      # 下载语音识别模型（145MB，国内镜像，可选）
```

**没有 key 也能演示**：`.env` 里设 `USE_MOCK_LLM=1`，界面会显示「离线演示模式 · 规则大脑」，
对话、建任务、看板刷新全都正常。

---

## 目录结构

```
agent/
├── core/                      ← 队友 A 的后端（功能原样保留，仅修兼容性）
│   ├── todo_mcp_server.py    6 个 MCP 工具 + SQLite(todos 表)
│   └── todo_agent.py         DeepSeek 大脑：工具调用 + 乱码拦截 + 二段式总结
├── bridge/                    ← 适配层（本次合并新写的「翻译官」）
│   ├── config.py             统一 .env（DEEPSEEK_API_KEY ↔ LLM_API_KEY 互认）
│   ├── todo_store.py         看板字段 ⇄ 队友 A 表结构 双向翻译
│   ├── todo_runtime.py       异步 Agent → 前台 chat()；独立线程事件循环
│   └── mock_brain.py         离线规则大脑
├── ui/                        ← 成员 B 的界面（样式/看板/语音）
│   ├── app.py                页面渲染
│   ├── task_views.py         筛选/排序/导出（纯函数，可单测）
│   └── voice.py              语音输入/播报
├── main.py                   命令行入口
├── tests/                    自动化回归
├── scripts/fetch_asr_model.py  语音模型下载脚本
└── docs/                     环境配置、模型说明
```

## 旧版代码与增强版的改动

| #   | 原写法                                          | 问题                                    | 合并后                                                         |
| --- | -------------------------------------------- | ------------------------------------- | ----------------------------------------------------------- |
| 1   | `from mcp.server.mcpserver import MCPServer` | 官方 mcp 包里没有这个模块，直接 `ImportError` 跑不起来 | `from mcp.server.fastmcp import FastMCP`                    |
| 2   | 模块加载时创建 OpenAI 客户端                           | 没 key 时 import 即崩，页面首屏白屏              | 改为懒加载，缺 key 由 UI 提示                                         |
| 3   | 数据库写相对路径 `todos.db`                          | 子进程 cwd 不同 → 数据写到别处 → 界面看不到           | 显式传 `TODO_DB_PATH`，与看板同一份                                   |
| 4   | 原 `run_agent` 只返回文本                          | 新界面的「执行轨迹」需要调用记录                      | 新增 `arun_agent_traced()` 返回 `(文本, 轨迹)`，原 `run_agent()` 签名不变 |
| 5   | Streamlit 里 `asyncio.run`                    | 与 Streamlit 事件循环打架，需 nest_asyncio 打补丁 | 独立线程 + 常驻事件循环，不再需要补丁                                        |

新增能力（不改动任何原有逻辑）：语音输入、语音播报、看板、统计、筛选排序、
CSV/Markdown 导出、执行轨迹可视化、离线演示模式。

---

## 测试

```powershell
.\run.ps1 test
```

- 静态检查 12 项：关键文件齐全、语法通过、6 个工具都在、乱码拦截与二段式总结保留、界面接的是桥接层、
  SQLite 连接跨线程安全、`.env` 不入库
- 桥接层 28 项：字段映射、口语化截止归一（含带时刻的写法）、完成/重开/删除写回、统计、离线大脑全链路、
  导出格式、跨线程访问回归

当前状态：**40 项全部通过**（静态 12/12 · 桥接 28/28）。

> 修复记录：看板曾报 `ProgrammingError: SQLite objects created in a thread can only be used in that same
> thread`——Streamlit 的 `@st.cache_resource` 会在不同 rerun 线程复用同一个连接，已改为
> `check_same_thread=False` + 读写锁（`bridge/todo_store.py`），并补了跨线程回归测试。

真实链路另做过端到端验证：填入真实 DeepSeek Key 后，`add_todo → list_todos → export_markdown → save_memory`
四个工具在一次对话里全部调用成功；网页端在 `http://localhost:8520` 实测可录音、可点按钮改任务。

## 学习资源
MCP 官方文档

Streamlit 官方文档
