# HiClaw Py

HiClaw Py 是一个面向个人长期运行与工程扩展的多通道 AI Agent 项目。

它已经从“单 Provider 聊天机器人”演进为一个具备以下能力的工程基础：

- 多通道接入：Telegram、Feishu、PowerShell TUI
- 双 Provider 路由：Claude / OpenAI
- 统一 capability registry：tools / workflows / skills
- 分层记忆、定时任务、联网搜索、文件与命令执行
- 可视化 dashboard
- 多 Agent 集群的 **runtime foundation**（当前处于基础阶段）

当前项目既可以作为个人智能体直接运行，也适合作为多 Agent / tool system / memory system 的工程样板。

## 当前定位

这个仓库现在不是“纯聊天机器人”，也不是“完整自治 Agent swarm”。

它当前最准确的定位是：

- 一个已经稳定支持多通道、多 Provider、多工具编排的个人 Agent 平台
- 一个已经具备 cluster runtime foundation 的多 Agent 演进中系统
- 一个强调可扩展性和可测试性的 Python 工程

## 当前能力

### 交互入口

- Telegram Bot
- Feishu 长连接机器人
- PowerShell TUI

### Provider 与执行能力

- Claude Provider：适合复杂工具调用、文件修改、Bash、workflow、长链执行
- OpenAI Provider：适合文本、图像理解、图像生成与编辑

### 能力系统

- 统一 `ToolSpec` registry
- registry-backed tool discovery
- capability watcher / 热刷新
- declarative workflow definitions
- user-defined workflow CRUD
- natural-language workflow compilation
- workflow schema v2（支持 input / constant / step_output）

### 运行时能力

- decision layer：意图理解、能力候选排序、策略路由
- runtime confirmation：高风险工具确认
- scheduler：定时任务、提醒、夜间任务
- memory system：长期记忆、工作记忆、对话归档、记忆治理
- monitor dashboard：实时 activity snapshot

### 多 Agent 集群（当前阶段）

当前已经落地：

- planner / executor / reviewer 角色模型
- cluster runtime store
- cluster run / tasks / messages / events 基础结构
- dashboard cluster projection

当前尚未完全落地：

- planner 的独立真实推理链
- reviewer 的独立真实执行链
- 多 executor 并行协作
- 完整 task DAG / dependency scheduler

也就是说，项目已经进入多 Agent 演进阶段，但还没有完成最终形态的自治协作系统。

## 工程结构

```text
src/hiclaw/
  app.py                    统一启动入口
  config.py                 环境配置与路径定义

  agents/                   Provider 执行层
    runtime.py              单轮执行总入口
    router.py               Provider 路由
    claude.py               Claude 执行
    openai.py               OpenAI 执行

  decision/                 意图理解与能力决策层
    interpreter.py
    router.py
    models.py
    trace.py

  capabilities/             统一能力注册与 workflow 系统
    tools.py
    workflows.py
    catalog.py
    runtime.py

  cluster/                  多 Agent 集群基础层
    models.py
    coordinator.py
    store.py

  memory/                   分层记忆系统
  tasks/                    定时任务与调度
  channels/                 Telegram / Feishu / TUI
  monitor/                  dashboard server 与前端资源
  core/                     公共类型、delivery、activity、confirmation
  skills/                   skill 加载与管理
  media/                    图片/语音相关处理
```

## 核心架构

### 1. Channel Layer

消息首先从 channel 进入：

- `channels/telegram/`
- `channels/feishu/`
- `channels/tui.py`

这些入口最终统一成 `ConversationRef`，然后进入 agent runtime。

### 2. Decision Layer

`decision/` 负责：

- 解析任务意图
- 识别 request style
- 生成 capability candidates
- 决定走 `answer_directly / prefer_tools / prefer_workflow / prefer_skill`

这是当前系统里最稳定、最像“中枢大脑”的一层。

### 3. Execution Layer

`agents/runtime.py::run_agent_for_conversation()` 是当前执行总入口。

它负责：

- 构建 decision plan
- 尝试 workflow-first
- 调用 Claude 或 OpenAI provider
- 记录 trace / outcome / task line / memory preference

### 4. Capability Layer

`capabilities/tools.py` 是统一 registry 基础：

- 工具元数据
- provider projection
- MCP/OpenAI 定义生成
- confirmation policy
- availability / risk / category

`capabilities/workflows.py` 在这个 registry 之上提供 workflow 能力，而不是另起一套 provider stack。

### 5. Cluster Runtime Foundation

当前多 Agent 相关逻辑由两层组成：

- `cluster/coordinator.py`：cluster blueprint 与角色编排
- `cluster/store.py`：cluster runtime source of truth

当前 cluster store 已保存：

- `runs`
- `tasks`
- `messages`
- `agents`
- `events`

dashboard 不再直接依赖 monitor 侧零散事件，而开始从 cluster runtime projection 读取 cluster 状态。

### 6. Monitor Layer

`monitor/server.py` 暴露 `/api/activity`，dashboard 从这个 API 拉取 snapshot。

当前前端重点界面是：

- `http://127.0.0.1:8765/v2`

`v2` 已经开始承载 cluster 可视化演进。

## 安装

### 环境要求

- Python `>= 3.12`
- Conda 或 venv
- Git
- 至少一种消息入口配置，或者仅使用 TUI

### 安装步骤

```powershell
git clone git@github.com:lianjiawei/hiclaw-py.git
cd hiclaw-py

conda create -n hiclaw python=3.12 -y
conda activate hiclaw

python -m pip install -e .
```

如果需要本地语音识别：

```powershell
python -m pip install -e ".[asr]"
```

## 启动方式

### 主应用

```powershell
python -m hiclaw
```

或：

```powershell
hiclaw
```

### TUI

```powershell
hiclaw-tui
```

### Feishu only

```powershell
hiclaw-feishu
```

### Dashboard only

```powershell
hiclaw-dashboard
```

## 配置

先复制：

```powershell
Copy-Item .env.example .env
```

### 最常用配置

```env
AGENT_PROVIDER=claude

TELEGRAM_BOT_TOKEN=
OWNER_ID=

FEISHU_APP_ID=
FEISHU_APP_SECRET=

ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=
ANTHROPIC_MODEL=

OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4.1-mini

WORKSPACE_DIR=./workspace
TAVILY_API_KEY=
SHOW_TOOL_TRACE=0
```

### Cluster 相关配置

```env
AGENT_CLUSTER_ENABLED=1
AGENT_CLUSTER_REVIEW_ENABLED=1
AGENT_CLUSTER_MAX_EVENTS=40
```

说明：

- `AGENT_CLUSTER_ENABLED=1`：启用 cluster foundation
- `AGENT_CLUSTER_REVIEW_ENABLED=1`：启用 reviewer 角色
- `AGENT_CLUSTER_MAX_EVENTS`：dashboard 投影保留的最近 cluster 事件数

### Dashboard 配置

```env
HICLAW_DASHBOARD_HOST=127.0.0.1
HICLAW_DASHBOARD_PORT=8765
```

打开：

- `http://127.0.0.1:8765/v2`

## 推荐运行模式

### 模式 A：本地开发 / 调试

- 使用 `hiclaw-tui`
- 打开 `/v2` dashboard
- 开启 `SHOW_TOOL_TRACE=1`
- 如需 cluster，可开启 `AGENT_CLUSTER_ENABLED=1`

### 模式 B：Telegram / Feishu 长期运行

- 使用 `python -m hiclaw`
- 配置至少一个 channel
- dashboard 可同时启用

### 模式 C：复杂文件与工具链任务

- 优先使用 `AGENT_PROVIDER=claude`
- 因为当前复杂工具执行和 workflow 路线更适合 Claude 路径

### 模式 D：图像任务

- 可使用 `AGENT_PROVIDER=openai`
- 配置 OpenAI 图片相关参数

## 测试

运行全量测试：

```powershell
python -m pytest test/ tests/ -q
```

当前工程已经有较完整的回归测试覆盖，包括：

- tool registry
- memory system
- session optimization
- semantic understanding
- cluster runtime foundation

## 当前已知边界

### 已经稳定的部分

- 多通道入口
- 双 Provider 基础路由
- tool/workflow registry
- memory / scheduler / dashboard
- cluster runtime foundation

### 正在演进的部分

- 多 Agent 的真实独立执行链
- planner / reviewer 真正成为独立 agent
- task DAG / dependency scheduling
- agent-to-agent message protocol
- dashboard 完整 cluster 可视化

## 推荐的下一步架构演进

当前最合理的演进顺序是：

1. `Cluster Runtime Foundation` 已完成
2. 实现真实 `planner / reviewer` 执行链
3. 引入 `ClusterTask` dependency graph
4. 引入 agent-to-agent message protocol
5. 支持多 executor 并行
6. 让 dashboard 完整基于 cluster projection 展示 tasks/messages

## 适合谁使用

这个项目适合：

- 想长期运行个人 Agent 的开发者
- 想研究 Claude / OpenAI 双 Provider 编排的人
- 想做 tool registry / workflow / memory / scheduler / cluster runtime 的工程实践者
- 想把单 Agent 系统演进成多 Agent 系统的团队

如果你的目标是“直接拿来当最终成品 swarm 平台”，当前仓库还在演进中；
如果你的目标是“在一个真实工程里继续向多 Agent 体系推进”，它现在已经是一个合适的基础。
