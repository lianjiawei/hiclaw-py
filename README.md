# HiClaw Py

HiClaw Py 是一个支持多通道交互和双 Provider 路由的个人智能体项目，统一接入 Telegram、PowerShell TUI、飞书等入口，并支持 Claude Agent SDK / Claude Code 与 OpenAI Provider。

这个项目适合两类用途：

- 作为个人长期运行的多通道 AI Agent。
- 作为学习 Claude Agent SDK、OpenAI Provider、MCP 工具、自定义 Agent 能力的工程样板。

## 功能特性

- Telegram / PowerShell TUI / 飞书多通道消息接入。
- Claude Agent SDK + OpenAI 双 Provider 模型调用。
- Claude Code 内置工具显性化，例如 `Read`、`Write`、`Edit`、`Glob`、`Grep`、`Bash`。
- 联网搜索：基于 Tavily API，Agent 可实时搜索互联网获取最新信息。
- OpenAI Provider 支持普通文本、图片理解、图片生成与图片编辑。
- 自定义 MCP 工具，例如获取时间、读取工作区文件、向当前会话发送消息、联网搜索、任务管理。
- 渠道级访问控制，例如 Telegram Owner 校验与飞书白名单。
- 连续会话，通过本地 `session_id` 维持上下文。
- 分层记忆能力，包含长期记忆、工作记忆、会话摘要、对话归档和记忆治理系统。
- 记忆治理系统：来源/置信度/作用域标记、冲突检测与归档、衰减与过期管理、相关性检索注入。
- 夜间记忆反思：LLM 驱动的记忆重写、候选晋升、过期 slot 归档，规则引擎回落。
- 定时任务，支持一次性、每天、每周任务，支持 session 上下文延续。
- 自然语言创建与取消定时提醒，支持中文数字与口语化时间表达（如"一分钟后"、"半小时后"）。
- Agent 可自主使用 `list_tasks` / `create_task` / `cancel_task` 管理定时任务。
- Skill 能力，包含表格数据分析与校验 Skill、自动化脚本执行 Skill。
- Bash 工具使用场景指导，鼓励 Agent 在复杂任务中编写脚本自动化执行。
- 可选本地 ASR，使用 `ffmpeg` + Vosk 处理语音消息。
- 会话管理优化：文件锁并发保护、超时自动清除、SQLite 统一管理。
- 工作记忆大小控制：字段字符上限、对话日志自动清理。
- 记忆合并优化：混合相似度算法（关键词 + n-gram），预过滤提升性能。

## 项目架构

![HiClaw Py Architecture](assets/hiclaw_architecture.svg)

整体架构可以分成几条清晰的链路：

- `Channels`：`telegram_bot.py`、`tui.py`、`feishu_bot.py` 分别提供 Telegram、PowerShell TUI 和飞书三条交互入口。
- `Boot Layer`：`app.py` 是统一启动入口，负责根据配置组合启动已启用的消息入口。
- `Agent Core`：`agent_client.py` 是统一路由层，根据 `AGENT_PROVIDER` 把请求分发到 Claude 或 OpenAI Provider。
- `Claude Provider`：`claude_client.py` 负责 session、memory、skills、MCP tools、Claude Code 内置工具和 Claude Agent SDK 查询流。
- `OpenAI Provider`：`openai_client.py` 负责普通文本、图片理解，以及图片生成/编辑接口调用。
- `Media Pipeline`：`media_store.py` 处理图片和语音上传；`speech_client.py` 通过 `ffmpeg` + Vosk 做本地语音转文字。
- `Tools`：`agent_tools.py` 提供自定义 MCP tools（时间、文件读取、消息发送、联网搜索、任务管理），同时白名单允许 Claude Code 内置工具，例如 `Read`、`Edit`、`Bash`。
- `State and Knowledge`：`config.py`、`session_store.py`、`memory_store.py`、`memory_intent.py`、`memory_frequency.py` 负责 .env 配置、按通道 session、分层记忆、元数据治理（来源/置信度/作用域）、冲突检测与归档、频率加权、衰减管理、夜间反思重写、相关性检索注入、对话归档和本地运行目录。
- `Skills`：`skill_store.py` 负责本地 Skill prompt 的选择和注入，包含表格分析、自动化脚本执行等 Skill。
- `Scheduler`：`scheduler.py`、`scheduler_store.py` 负责自然语言定时任务解析（支持中文数字与口语化时间）、SQLite 持久化、轮询到期任务、夜间记忆冥想调度，并回到 Agent Core 执行。

## 环境要求

建议使用独立 Conda 环境运行，不要混用系统 Python 或其他项目环境。

基础要求：

- Python `>=3.12`
- Conda 或 Miniconda
- Git
- 至少一种消息入口配置（如 Telegram Bot 或飞书应用）
- 一个兼容 Anthropic API 协议的模型服务

可选语音识别要求：

- `ffmpeg`
- Vosk Python 包
- Vosk 中文模型

## 安装

1. 克隆项目

```powershell
git clone git@github.com:lianjiawei/hiclaw-py.git
cd hiclaw-py
```

2. 创建并激活 Conda 环境

```powershell
conda create -n hiclaw python=3.12 -y
conda activate hiclaw
```

3. 安装项目依赖

```powershell
python -m pip install -e .
```

如果需要语音转文字能力，安装 ASR 可选依赖：

```powershell
python -m pip install -e ".[asr]"
```

4. 确认 Claude Code CLI 可用

本项目通过 Claude Agent SDK 调用 Claude Code 能力。SDK 底层会启动 Claude Code CLI 子进程，通常会优先使用 SDK 包中自带的 bundled CLI，不需要额外手动安装 Claude Code CLI。

如果运行时报 `Claude Code not found`，再安装 Claude Code CLI，或确保系统 PATH 中可以找到 `claude` 命令。也可以用下面的命令检查当前系统是否已经有全局 `claude`：

```powershell
claude --version
```

注意：即使上面的命令不存在，只要 SDK 自带的 bundled CLI 可用，项目仍然可以正常运行。

## 配置

项目通过 `.env` 读取运行配置。仓库只提供 `.env.example`，真实 `.env` 不应该提交到 GitHub。

当前项目支持两条模型 Provider 路线：

- `AGENT_PROVIDER=claude`：完整 Agent 路线，适合 Claude Code 工具、MCP、文件读写、Bash、WebSearch 等复杂能力。
- `AGENT_PROVIDER=openai`：轻量 Provider 路线，适合普通文本、图片理解、图片生成/编辑。

复制配置模板：

```powershell
Copy-Item .env.example .env
```

然后把 `.env` 里的占位值替换成你自己的配置。

最小 Claude 路线配置：

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OWNER_ID=your_telegram_user_id
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_BASE_URL=https://your-compatible-endpoint
ANTHROPIC_MODEL=your_model_name
```

常用配置说明：

- `TELEGRAM_BOT_TOKEN`：Telegram 通道凭据，可以从 BotFather 获取；只启用飞书或 TUI 时可不填。
- `OWNER_ID`：Telegram Owner 用户 ID，Telegram 通道会按这个值限制使用者。
- `ANTHROPIC_API_KEY`：模型服务 API Key。
- `ANTHROPIC_BASE_URL`：兼容 Anthropic API 的服务地址。
- `ANTHROPIC_MODEL`：默认主模型名称。
- `WORKSPACE_DIR`：Agent 可以操作的工作区目录，默认是项目下的 `workspace/`。
- `TUI_OUTPUT_DIR`：PowerShell TUI 保存生成图片的目录，默认是 `workspace/outputs/tui/`。
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`：飞书自建应用的凭据，仅启动飞书机器人通道时需要。
- `FEISHU_ALLOWED_OPEN_IDS` / `FEISHU_ALLOWED_CHAT_IDS`：飞书通道白名单，逗号分隔；两个都为空时允许所有飞书用户/会话，正式使用建议至少配置一项。
- `FEISHU_REPLY_PROCESSING_MESSAGE`：飞书通道收到消息后是否先回复“正在处理”，`1` 开启，`0` 关闭。
- `SHOW_TOOL_TRACE`：是否在支持的消息通道中显示工具调用过程，`1` 开启，`0` 关闭。
- `TAVILY_API_KEY`：Tavily 联网搜索 API Key，在 https://app.tavily.com 注册获取（免费 1000 次/月）。
- `TAVILY_SEARCH_DEPTH`：搜索深度，`basic` 快速（推荐），`advanced` 深度。
- `TAVILY_MAX_RESULTS`：单次搜索返回最大结果数，默认 5。
- `SCHEDULER_INTERVAL_SECONDS`：定时任务轮询间隔，默认 `30` 秒。
- `SESSION_TIMEOUT_SECONDS`：会话超时时间，默认 `86400` 秒（24 小时）。
- `CONVERSATION_RETENTION_DAYS`：对话日志保留天数，默认 `30` 天。

`.env.example` 为了避免暴露本机路径，示例里使用的是相对路径。相对路径会按启动程序时的当前目录解析；推荐始终在项目根目录运行 `hiclaw` 或 `hiclaw-tui`。如果你需要从任意目录启动，也可以在自己的 `.env` 中使用本机绝对路径，真实 `.env` 不会提交到 GitHub。

DeepSeek 模型分组示例：

```env
ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro
ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro
ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash
CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-pro
```

Claude Code 行为控制示例：

```env
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK=1
CLAUDE_CODE_EFFORT_LEVEL=max
```

### OpenAI Provider 配置

项目默认仍使用 Claude Agent SDK：

```env
AGENT_PROVIDER=claude
```

如果想切换到 OpenAI SDK 第一版 Provider，可以配置：

```env
AGENT_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
OPENAI_IMAGE_API_KEY=
OPENAI_IMAGE_BASE_URL=
OPENAI_IMAGE_GENERATE_PATH=/images/generations
OPENAI_IMAGE_EDIT_PATH=/images/edits
OPENAI_IMAGE_TIMEOUT_SECONDS=120
OPENAI_IMAGE_MODEL=gpt-image-2
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=auto
OPENAI_IMAGE_OUTPUT_FORMAT=png
OPENAI_IMAGE_INCLUDE_OPTIONAL_PARAMS=0
```

第一版 OpenAI Provider 支持普通文本、图片理解和图片生成/编辑。文字聊天默认走 `OPENAI_BASE_URL`，图片生成/编辑可以单独配置 `OPENAI_IMAGE_BASE_URL`、`OPENAI_IMAGE_API_KEY` 和图片接口路径；不配置图片专用项时，会复用文本 OpenAI 配置和标准 Images API 路径。部分中转服务不接受 `quality`、`output_format`、`response_format` 等可选字段，可以保持 `OPENAI_IMAGE_INCLUDE_OPTIONAL_PARAMS=0` 只发送最小参数。图片生成或编辑结果会直接以内存 bytes 返回到支持的消息通道，不写入本地文件。Claude Code 内置工具、MCP 工具、文件读写、Bash 等复杂 Agent 能力仍建议使用 `AGENT_PROVIDER=claude`。

### 联网搜索配置

项目默认使用 [Tavily](https://tavily.com/) 作为搜索引擎，Agent 可通过 `web_search` 工具实时搜索互联网。Tavily 专为 AI Agent 设计，返回结构化结果（标题、URL、内容摘要），不需要自己解析 HTML。

注册获取 API Key：

1. 打开 https://app.tavily.com 注册账号
2. 登录后在 Dashboard 复制 API Key
3. 免费额度：每月 1000 次搜索

在 `.env` 中配置：

```env
TAVILY_API_KEY=tvly-your_key_here
TAVILY_SEARCH_DEPTH=basic
TAVILY_MAX_RESULTS=5
```

配置说明：

- `TAVILY_API_KEY`：Tavily API Key，**必须填写**才能使用搜索。
- `TAVILY_SEARCH_DEPTH`：`basic` 快速搜索（推荐），`advanced` 深度搜索（消耗更多配额）。
- `TAVILY_MAX_RESULTS`：单次搜索返回的最大结果数，默认 5。

如果不配置 `TAVILY_API_KEY`，`web_search` 工具会返回提示信息，Agent 会被告知搜索不可用，但不会影响其他功能。

验证搜索是否可用：

```powershell
python -c "from tavily import TavilyClient; from dotenv import load_dotenv; import os; load_dotenv(); c=TavilyClient(api_key=os.getenv('TAVILY_API_KEY')); r=c.search(query='Python教程', max_results=2); [print(f'{i}. {x[\"title\"]}') for i,x in enumerate(r.get('results',[]),1)]"
```

## 语音识别配置

语音识别是可选功能。不开启时，机器人仍然可以正常处理文本和图片。

1. 安装 `ffmpeg`

Windows 可以使用 winget：

```powershell
winget install Gyan.FFmpeg
```

安装后确认：

```powershell
ffmpeg -version
```

2. 安装 ASR 可选依赖

```powershell
python -m pip install -e ".[asr]"
```

3. 下载 Vosk 中文模型

模型下载地址：

[Vosk Models](https://alphacephei.com/vosk/models)

轻量中文模型推荐：

- `vosk-model-small-cn-0.22`

解压后在 `.env` 中配置：

```env
ASR_PROVIDER=vosk
VOSK_MODEL_DIR=models\vosk-model-small-cn-0.22
```

如果暂时不使用语音识别：

```env
ASR_PROVIDER=none
```

## 启动

推荐启动方式：

```powershell
python -m hiclaw
```

如果已经执行过 `python -m pip install -e .`，也可以使用脚本入口：

```powershell
hiclaw
```

`hiclaw` 是通道聚合入口，至少需要配置一种远程消息通道：

- Telegram：只配置 `TELEGRAM_BOT_TOKEN` 也可以启动。
- 飞书：只配置 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 也可以启动。
- Telegram + 飞书：同时配置即可。

如果你暂时不想配置任何远程通道，只想先在本地体验，请直接运行：

```powershell
hiclaw-tui
```

如果运行 `hiclaw` 时一个通道都没有配置，程序会直接提示你改用 `hiclaw-tui`。

启动成功后，终端会显示：

```text
Starting channels: Telegram
```

如果同时配置了多条入口，会显示类似：

```text
Starting channels: Telegram, Feishu
```

本地开发时，按 `Ctrl + C` 可以停止机器人。

## PowerShell TUI 通道

也可以直接在 PowerShell 里启动本地 TUI 通道，与同一个 Agent 交互：

```powershell
python -m hiclaw.tui
```

如果已经执行过 `python -m pip install -e .`，也可以使用脚本入口：

```powershell
hiclaw-tui
```

TUI 复用 `AGENT_PROVIDER`、`WORKSPACE_DIR`、memory、skills 和 Agent 工具链；TUI 使用独立会话文件 `data/hiclaw_session_tui.json`，不会覆盖其他入口的连续会话。每个 TUI 进程都会生成独立实例 scope 和独立 sender 路由，因此多个 TUI 实例可以并行运行而不串消息。当前采用稳定的串行交互模式：单行输入按 `Enter` 直接发送，多行内容建议使用 `/paste`。常用命令：

- `/help`：查看命令。
- `/reset`：清空 TUI 独立连续会话。
- `/provider`：查看当前 Agent Provider。
- `/paste`：进入多行输入，单独一行 `.` 结束。
- `/exit`：退出。

如果 Agent 返回图片，TUI 会把图片保存到 `TUI_OUTPUT_DIR`，默认是 `workspace/outputs/tui/`。这个目录已被 `.gitignore` 忽略，方便本地查看生成结果，同时避免误提交图片文件。

## 飞书机器人通道

飞书通道使用官方 `lark-oapi` SDK 的长连接模式接收事件，不需要本地暴露公网 Webhook 地址。当前支持文本消息和图片输入理解；图片结果回传仍有限制，复杂图片输出建议优先在其他可见图片结果的入口查看。

启动前需要在飞书开放平台完成这些配置：

- 创建自建应用并开启机器人能力。
- 获取 `App ID` 和 `App Secret`，填入 `.env`。
- 在事件订阅里选择“使用长连接接收事件”。
- 订阅接收消息事件 `im.message.receive_v1`。
- 给应用开通接收消息和发送消息相关权限，并发布/安装到目标组织。
- 把机器人拉进群，或直接私聊机器人测试。

`.env` 示例：

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=your_feishu_app_secret
FEISHU_ALLOWED_OPEN_IDS=
FEISHU_ALLOWED_CHAT_IDS=
FEISHU_SESSION_SCOPE_PREFIX=feishu
FEISHU_REPLY_PROCESSING_MESSAGE=1
```

启动：

```powershell
hiclaw-feishu
```

或：

```powershell
python -m hiclaw.feishu_bot
```

飞书通道会按会话隔离连续上下文：私聊使用 `feishu:p2p:{open_id}`，群聊使用 `feishu:chat:{chat_id}`，不会覆盖其他入口的会话。正式使用时建议配置 `FEISHU_ALLOWED_OPEN_IDS` 或 `FEISHU_ALLOWED_CHAT_IDS`，避免组织内其他用户误触发机器人。

当前各入口对应的默认 scope 说明：

- Telegram：`telegram:chat:{chat_id}`
- TUI：`tui:{instance_id}`
- 飞书私聊：`feishu:p2p:{open_id}`
- 飞书群聊：`feishu:chat:{chat_id}`

当前系统内部统一使用 `ConversationRef(channel, target_id, session_scope)` 作为共享会话标识；消息回投优先按 `conversation_key = {channel}:{target_id}` 精确路由。

## 交互入口示例

基础命令：

- `/start`：查看机器人简介。
- `/reset`：清空当前连续会话。
- `/memory`：查看兼容长期记忆文件。
- `/remember 内容`：手动写入一条候选记忆。
- `/skills`：查看可用 Skills。
- `/tasks`：查看待执行定时任务。
- `/cancel 任务ID`：取消定时任务。
- `/schedule_in 秒数 内容`：创建一个命令式延迟任务。

自然语言示例：

```text
30秒后提醒我喝水
明天早上9点提醒我整理日报
每天下午3点提醒我站起来活动一下
每周一早上9点提醒我开例会
```

图片和语音：

- 发送图片时，机器人会把图片内容以内存 bytes 交给 Agent 处理，不依赖本地图片路径。
- 发送语音时，如果开启 ASR，机器人会先转写语音，再把转写文本交给 Agent 处理。

记忆行为：

- 对于"你要记得……""以后都用中文回答""你可以叫我 Boss"这类高置信度自然语言记忆意图，系统会自动识别。
- `profile / preferences / rules` 这类低风险长期记忆会根据意图类型智能提升（立即/1小时/6小时/24小时）。
- 反复强调的内容会被频率加权机制捕获，加速提升为长期记忆。
- 每天凌晨 2:00 系统会"冥想"整理记忆，合并相似条目、清理低价值内容。
- 超过 30 天的旧记忆自动归档到 `archive/` 目录。
- `/memory_candidates`、`/memory_accept`、`/memory_reject` 主要面向维护者做记忆治理，不是普通用户主交互。

## 项目结构

```text
hiclaw-py/
├─ pyproject.toml
├─ .env.example
├─ README.md
├─ COURSE_GUIDE.md
├─ assets/
│  └─ hiclaw_architecture.svg
├─ claw_course_bot.py
├─ skills/
│  └─ table_analysis_skill.md
├─ src/
│  └─ hiclaw/
│     ├─ __main__.py
│     ├─ __init__.py
│     ├─ access.py
│     ├─ agent_client.py
│     ├─ agent_response.py
│     ├─ agent_tools.py
│     ├─ app.py
│     ├─ channel_registry.py
│     ├─ claude_client.py
│     ├─ config.py
│     ├─ delivery.py
│     ├─ feishu_bot.py
│     ├─ media_store.py
│     ├─ memory_frequency.py
│     ├─ memory_intent.py
│     ├─ memory_store.py
│     ├─ openai_client.py
│     ├─ runtime_locks.py
│     ├─ runtime_types.py
│     ├─ scheduler.py
│     ├─ scheduler_runtime.py
│     ├─ scheduler_store.py
│     ├─ session_store.py
│     ├─ skill_store.py
│     ├─ speech_client.py
│     ├─ task_repository.py
│     ├─ task_service.py
│     ├─ telegram_bot.py
│     ├─ telegram_formatting.py
│     └─ tui.py
├─ data/
└─ workspace/
```

说明：

- `workspace/`：本地运行工作区，保存运行过程中产生的上传、输出、记忆、摘要、候选记忆和归档数据，默认不纳入版本控制。
- `workspace_course/`：课程版本地运行目录，同样默认不纳入版本控制。

核心模块说明：

- `app.py`：统一程序入口，当前已收缩为薄组合根，负责 bootstrap、初始化 router、启动 scheduler 和启用的远程通道。
- `channel_registry.py`：集中定义 Telegram / 飞书通道是否启用、如何注册 sender、以及如何启动各自 runner。
- `config.py`：读取 `.env` 并提供全局配置。
- `access.py`：Owner 权限判断。
- `telegram_bot.py`：Telegram 入口的命令、文本、图片、语音和异常处理。
- `feishu_bot.py`：飞书入口的消息接入、白名单校验、图片下载和回复。
- `tui.py`：本地 PowerShell TUI 入口。
- `agent_client.py`：统一 Agent 路由层，根据 `AGENT_PROVIDER` 分发到 Claude 或 OpenAI Provider，并构造各入口对应的 `ConversationRef`。
- `runtime_types.py`：定义 `ConversationRef` 和统一的 `conversation_key` 派生规则。
- `delivery.py`：定义 `MessageSender` 和 `DeliveryRouter`，负责按 conversation 优先、channel 回退的方式路由消息。
- `claude_client.py`：封装 Claude Agent SDK、工具配置、会话恢复、记忆和 Skill 注入。
- `openai_client.py`：封装 OpenAI 文本、图片理解、图片生成/编辑能力。
- `runtime_locks.py`：统一管理运行时会话级锁，保证同会话串行、跨会话并行，并提供锁统计与清理。
- `agent_tools.py`：自定义 MCP 工具。
- `media_store.py`：处理图片和语音上传数据。
- `speech_client.py`：语音识别抽象层，目前支持 Vosk。
- `memory_store.py`：分层记忆、工作记忆、会话摘要、候选记忆治理、对话记录、自动提升、冥想整理、归档和对话日志清理。
- `session_store.py`：连续会话 `session_id` 读写，支持文件锁并发保护、超时自动清除、SQLite 异步 API。
- `task_service.py`：统一处理 `/schedule_in`、`/schedule`、`/tasks`、`/cancel` 等任务命令与自然语言任务入口。
- `task_repository.py`：统一处理任务持久化、due-task 查询、claim、release 和 post-run 更新。
- `scheduler.py`：负责自然语言时间解析、任务执行、周期任务 next-run 计算，以及基于 claim 的到期任务消费。
- `scheduler_runtime.py`：负责后台 scheduler loop 的独立线程生命周期，避免依赖具体通道主循环。
- `scheduler_store.py`：定时任务 SQLite 表初始化与兼容迁移。
- `skill_store.py`：Skill 加载和查询。
- `telegram_formatting.py`：把常见 Markdown 转成 Telegram 可渲染 HTML。
- `agent_response.py`：统一文本/图片回复结果结构。

## 定时任务与调度说明

当前定时任务系统采用一张共享任务表，三个入口共用同一套命令解析和执行模型：

- `task_service.py`：命令入口与校验
- `task_repository.py`：数据库读写、claim、release、状态更新
- `scheduler.py`：扫描、claim 成功后执行、更新 next run

当前任务状态至少包含：

- `active`
- `running`
- `completed`
- `cancelled`

为避免多进程或多实例重复执行，同一条到期任务会先被原子 claim，只有 claim 成功的运行时才会继续执行。

消息回投时，scheduler 会优先判断当前运行时是否拥有该任务的 conversation route：

- TUI 只处理当前实例拥有的 TUI 任务
- app 模式下 Telegram / 飞书各自处理自己能回投的任务

这可以避免多个 TUI 实例串消息，也减少无关运行时对其他通道任务的噪音日志。

## 运行数据

运行过程中会自动生成一些本地数据，这些文件默认不会提交到 GitHub。

```text
data/
├─ hiclaw_session_telegram.json
├─ hiclaw_session_tui.json
├─ hiclaw_session_feishu_*.json
└─ hiclaw_tasks.db

workspace/
├─ memory/
│  ├─ CLAUDE.md
│  ├─ frequency.json
│  ├─ importance.json
│  ├─ working_state_telegram.json
│  ├─ working_state_tui.json
│  ├─ working_state_feishu_*.json
│  ├─ session_summaries/
│  ├─ long_term/
│  ├─ candidates/
│  ├─ archive/
│  └─ conversations/
├─ outputs/
│  └─ tui/
└─ uploads/
   └─ voices/
```

说明：

- `data/hiclaw_session_telegram.json`：保存 Telegram 入口连续会话 ID。
- `data/hiclaw_session_tui.json` / `data/hiclaw_session_feishu_*.json`：保存 TUI / 飞书通道独立会话。
- `data/hiclaw_tasks.db`：保存定时任务。
- `workspace/memory/CLAUDE.md`：兼容长期记忆文件和默认背景说明。
- `workspace/memory/frequency.json`：话题频率统计，用于频率加权机制。
- `workspace/memory/importance.json`：记忆重要性评分记录。
- `workspace/memory/working_state_*.json`：按入口隔离维护工作记忆。
- `workspace/memory/session_summaries/`：按入口隔离维护会话摘要。
- `workspace/memory/long_term/`：结构化长期记忆分区。
- `workspace/memory/candidates/`：候选记忆暂存区。
- `workspace/memory/archive/`：过期记忆归档目录。
- `workspace/memory/conversations/`：按天保存对话记录。
- `workspace/outputs/tui/`：TUI 通道保存生成图片输出。
- `workspace/uploads/voices/`：保存语音上传文件。
- 图片默认走内存处理，不再写入 `workspace/uploads/images/`。

这些目录可能包含隐私信息，部署和备份时要单独处理。

当前默认策略是：整个 `workspace/` 和 `workspace_course/` 都视为本地运行目录，不提交到 GitHub。

## 记忆系统

当前记忆系统模拟人类记忆机制，包含频率加权、智能提升、夜间冥想和自动归档：

### 记忆分层

- `long_term/`：正式长期记忆，用于用户画像、偏好、长期规则。
- `working_state_*.json`：按入口隔离的工作记忆，记录当前目标、最近决策、待确认问题和涉及文件。
- `session_summaries/`：按入口隔离的会话摘要，压缩最近几轮上下文。
- `candidates/`：候选记忆区，暂存需要观察的记忆项。
- `archive/`：归档记忆区，保存过期但可能仍有价值的历史记忆。

### 智能记忆提升

系统根据意图类型自动决定候选记忆的提升时间：

| 意图类型 | 提升时间 | 示例 |
|---------|---------|------|
| 明确记忆 | 立即 | "你要记得我喜欢用 VS Code" |
| 偏好声明 | 1 小时 | "我喜欢用中文回答" |
| 未来规则 | 6 小时 | "以后你要简洁回答" |
| 模糊内容 | 24 小时 | "随便记一下这个" |

### 频率加权机制

- 每次对话自动提取关键词并统计频率。
- 高频话题（默认 ≥3 次）会被标记为重要，加速记忆提升。
- 影响记忆重要性评分，强调词（必须/一定/记住）加分，模糊词（可能/也许/暂时）减分。

### 记忆冥想机制

每天凌晨 2:00 自动执行记忆整理：

1. **合并相似记忆**：使用混合相似度算法（关键词 60% + 字符 n-gram 40%），相似度 >60% 的条目自动合并。
2. **预过滤优化**：先通过关键词快速筛选（30% 重叠阈值），再进行精确相似度计算，大幅提升性能。
3. **重要性评分**：根据频率和关键词强度打分。
4. **清理低价值记忆**：评分过低且记忆过多时自动清理。
5. **生成整理报告**：记录合并/清理的操作日志。

### 自动归档

- 长期记忆超过 30 天自动归档到 `archive/` 目录。
- 按分类（profile/preferences/rules）分别归档。
- 原文件只保留未过期的记忆条目。

### 记忆冲突与去重

- 同一条记忆内容重复出现时会去重，不会重复追加。
- 对 `profile / preferences / rules` 中部分明确槽位采用覆盖式更新：
  - `profile`：用户称呼、Agent 名称。
  - `preferences`：语言偏好、回答风格。
  - `rules`：渠道强调规则、回答规则。
- `general` 默认先进候选区，避免直接把模糊陈述写死到正式长期记忆。

### 维护者命令

- `/memory_candidates`：查看候选记忆列表。
- `/memory_accept 文件名 [profile|preferences|rules|general]`：采纳候选记忆。
- `/memory_reject 文件名`：拒绝并删除候选记忆。

## Skill 能力

当前项目内置一个表格分析 Skill：

```text
skills/table_analysis_skill.md
```

它适合用于：

- 读取表格。
- 提取关键数据。
- 判断表格中的合计、分项、口径是否一致。
- 辅助完成简单的数据校验和分析。

查看 Skills：

```text
/skills
```

查看指定 Skill：

```text
/skills table
```

## 定时任务

定时任务保存在：

```text
data/hiclaw_tasks.db
```

支持类型：

- 一次性任务。
- 每天重复任务。
- 每周重复任务。

定时任务调度器默认每 `30` 秒检查一次到期任务，可以通过 `.env` 调整：

```env
SCHEDULER_INTERVAL_SECONDS=30
```

### 定时任务 Session 延续

定时任务现在支持可选的 session 上下文延续：

- `session_scope`：任务关联的会话通道（如 `telegram`、`tui`）。
- `continue_session`：是否延续之前的对话上下文（默认 `false`）。

创建支持 session 延续的定时任务示例：

```python
await create_scheduled_task(
    chat_id=chat_id,
    prompt="继续昨天的数据分析",
    run_at=run_at,
    session_scope="telegram",
    continue_session=True,
)
```

## 会话管理优化

### 并发保护

- Session 文件读写使用跨平台文件锁（Windows `msvcrt` / Linux `fcntl`）。
- 原子写入机制（临时文件 + `os.replace`），防止并发写入损坏。

### 超时自动清除

- Session 文件超过 `SESSION_TIMEOUT_SECONDS`（默认 24 小时）未更新时，自动清除。
- 避免恢复过期的 Claude session 导致 SDK 错误。

### SQLite 统一管理

- Session 数据现在同时支持文件存储和 SQLite 存储（异步 API）。
- 新增异步 API：`load_session_id_async()`、`save_session_id_async()`、`clear_session_id_async()`。
- 启动时自动初始化 session 数据库。

### 工作记忆大小控制

- 工作记忆字段添加字符上限：`active_goal`（200 字符）、`recent_decisions`（300 字符）、`open_questions`（200 字符）。
- 防止 `working_state.json` 文件膨胀，控制内存占用。

### 对话日志自动清理

- 每天凌晨 3:00 自动清理超过 `CONVERSATION_RETENTION_DAYS`（默认 30 天）的对话日志。
- 控制 `conversations/` 目录磁盘占用。

## 飞书通道增强

- 新增 `/reset` 命令，与 Telegram / TUI 保持一致的 session 重置能力。
- `SEEN_MESSAGE_IDS` 改用 `deque(maxlen=1000)`，消除突然清空导致的重复处理窗口。

## 安全说明

- 不要提交 `.env`。
- 不要提交 `data/` 中的数据库和 session 文件。
- 不要提交整个 `workspace/`。
- 不要提交整个 `workspace_course/`。
- 如果启用 Telegram，建议只给自己的 Telegram 用户 ID 配置 `OWNER_ID`。
- 如果开放给多人使用，需要重新设计权限、配额、审计和数据隔离。

## 常见问题

### `python -m hiclaw` 是什么意思？

`-m` 表示把 `hiclaw` 当作 Python 模块运行。Python 会寻找 `hiclaw/__main__.py`，再从那里启动程序。

### 为什么推荐 `python -m pip install -e .`？

`-e` 是 editable install，表示以可编辑模式安装当前项目。这样源码改动后不需要反复重新安装，适合开发阶段。

### 为什么搜索不工作？

联网搜索依赖 Tavily API，需要先在 https://app.tavily.com 注册并获取 API Key，然后在 `.env` 中配置 `TAVILY_API_KEY`。不配置时 Agent 会被告知搜索不可用，其他功能不受影响。

### Vosk 启动时打印很多 `VoskAPI` 日志正常吗？

正常。那是 Vosk 加载模型时输出的内部日志。只要没有 `ERROR`，通常不影响使用。

### 定时任务日志提示 `missed by 0:00:01` 是错误吗？

通常不是。它表示某次定时检查因为程序当时忙，晚了一两秒执行。只要任务后续正常执行，就可以忽略。

## 开发验证

最小验证命令：

```powershell
python -m compileall src/hiclaw
```

记忆系统测试：

```powershell
python tests/test_memory_system.py
```

会话优化测试：

```powershell
python tests/test_session_optimization.py
```

P2 & P3 优化测试：

```powershell
python tests/test_p2_p3_optimization.py
```

检查文本编码，避免中文注释或 `.env` 配置说明被 Windows 终端写成问号乱码：

```powershell
python scripts/check_text_encoding.py
```

检查 ASR Provider：

```powershell
python -c "from hiclaw.speech_client import build_speech_provider; print(build_speech_provider().name)"
```

查看 git 状态：

```powershell
git status --short
```

## 课程文件

仓库中保留了一个课程版单文件：

```text
claw_course_bot.py
```

配套教程：

```text
COURSE_GUIDE.md
```

课程版适合学习和培训，正式运行建议使用 `src/hiclaw/` 下的工程化版本。
