# pixel-office-core

从 `pixel-agents` 提取出来的独立像素办公室渲染模块。

目标：
- 不依赖 VS Code
- 只负责场景渲染、人物移动、环境素材加载
- 通过命令接口接收外部 Agent 系统控制

## 当前能力

- Canvas 像素场景渲染
- 地板、墙体、家具、角色素材加载
- 网格寻路与角色移动
- 座位系统与基础工作/游走状态
- 独立命令接口 `dispatch()`
- 点击角色事件 `agentClick`

## 目录

- `src/`: 核心源码
- `public/assets/`: 提取出的默认素材
- `examples/`: 最小接入示例

## 快速使用

```ts
import { PixelOfficeController, loadAssetBundleFromBaseUrl } from './dist/index.js'

const container = document.getElementById('app')!
const office = new PixelOfficeController(container, { zoom: 3 })
const bundle = await loadAssetBundleFromBaseUrl('./public/assets')

office.loadAssets(bundle)
office.dispatch({
  type: 'setAgents',
  agents: [
    { id: 1, label: 'Planner', palette: 0, isActive: true },
    { id: 2, label: 'Researcher', palette: 1, isActive: false }
  ]
})

office.dispatch({ type: 'moveAgentTo', id: 2, col: 8, row: 6 })
office.on('agentClick', ({ id }) => console.log('clicked', id))
```

## 推荐的 Python 对接方式

Python Agent 后端不要直接操纵画布，只需要输出命令 JSON。

例如：

```json
{ "type": "upsertAgent", "agent": { "id": 101, "label": "dispatcher", "palette": 2 } }
{ "type": "setAgentActive", "id": 101, "isActive": true, "tool": "Plan" }
{ "type": "moveAgentTo", "id": 101, "col": 12, "row": 4 }
{ "type": "focusAgent", "id": 101 }
```

前端只要拿到这些 JSON，调用：

```ts
office.dispatch(command)
```

这样你的 Python 项目可以通过：
- WebSocket
- SSE
- HTTP polling
- Electron preload bridge

任何一种方式驱动前端。

如果你走 WebSocket，可以直接用：

```ts
import { bindWebSocketCommandStream } from './dist/index.js'

bindWebSocketCommandStream(office, ws)
```

后端只要持续发送单条 JSON 命令即可。

## 后续建议

下一步可以继续补：
- WebSocket adapter
- tooltip / label overlay
- 选中高亮与编辑器模式
- 更细的 Agent 状态气泡
- 多场景地图切换
