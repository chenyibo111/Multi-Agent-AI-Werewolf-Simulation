# Werewolf Arena Phase 4 Web UI Design

**状态：已确认设计，待实施计划**  
**日期：2026-08-26**  
**基线：Phase 3 已合并至 `master`**

## 1. 目标与范围

Phase 4 为本地单人六人局交付可完整游玩的浏览器界面。它连接现有 FastAPI、SQLite 房间和 Agent Runtime：用户可创建一局、观看 AI 自动推进、进行所有自身合法行动、在断线后恢复，并在结局看到胜负与身份揭晓。

本阶段包含：

- `frontend/` Vite + React + TypeScript 工程；
- 创建房间、随机/指定身份与浏览器内当前房间恢复；
- 对局时间线、玩家状态、本人的私密身份面板和合法动作面板；
- REST 快照、Cookie 会话、WebSocket 事件流、断线重连与手动恢复；
- 结局状态与再开一局；
- 单元和浏览器端到端验证。

本阶段不包含账号、历史战报列表、多人真人局、移动端专门布局、复杂动画、云部署或规则编辑器。

## 2. 技术架构

前端位于 `frontend/`，采用 Vite、React、TypeScript 与 React Router。开发服务器运行在 `http://127.0.0.1:5173`，通过现有 CORS 与 `http://127.0.0.1:8000` 的 FastAPI 通信。所有 `fetch` 均使用 `credentials: "include"`，依赖后端按房间路径设置的 HttpOnly Cookie。

生产构建写入 `frontend/dist/`。FastAPI 提供该静态目录，并对非 API/非 WebSocket 路径返回 SPA 的入口文件；这使本地服务可一次启动，同时不妨碍未来将前端独立部署。

前端只消费投影后的 API 数据：

- `POST /api/rooms` 创建房间；
- `GET /api/rooms/{room_id}` 读取安全快照；
- `POST /api/rooms/{room_id}/commands` 提交人类意图；
- `POST /api/rooms/{room_id}/continue` 请求恢复自动推进；
- `GET ws://.../api/rooms/{room_id}/events?after_sequence=N` 读取可见事件。

创建响应的 `session_token` 保留给 Swagger 和脚本兼容，React 不读取、不存储它。浏览器不会接触 API Key、模型原始内容、Agent memory、未投影事件或完整权威状态。

## 3. 路由与组件

| 路由 | 内容 | 主要组件 |
|---|---|---|
| `/` | 创建或恢复本浏览器的最近房间 | `CreateGameForm`、`ResumeCard` |
| `/rooms/:roomId` | 主对局与结局 | `GameRoomPage`、`RoomTimeline`、`PlayerRail`、`PrivatePanel`、`ActionPanel`、`ConnectionStatus` |

对局页采用已选择的 A 布局：中央为按事件顺序阅读的叙事时间线，右侧为持续可见的私密身份卡、阶段/连接状态、六位玩家存活状态和当前操作。结局不另建路由；当后端安全状态显示 `finished` 时，在同一页扩展胜负、身份揭晓和再开一局。

风格为“月夜秘仪”：深蓝为背景，紫色表示可操作状态，低饱和金色强调身份和胜负，白天阶段以暖灰改善可读性。动画仅用于等待/连接反馈，不能遮挡文本或操作。

## 4. 状态与事件流

`RoomSession` 是页面唯一的协调状态：安全快照、可见事件、最后事件序号、连接状态及短暂请求错误。规则不在前端复刻，所有动作和目标都由后端响应决定。

1. 页面加载时调用 `GET room`，保存安全状态和完整可见事件。
2. 以最后事件序号建立 WebSocket；收到事件后按 `sequence` 去重后追加到时间线。
3. 命令和 continue 响应同时更新快照与事件；与 WebSocket 到达顺序无关，因为序号全局去重。
4. 连接意外关闭时按受限退避重连并带上最后序号；重连期间保留旧快照，显示“正在重连”。
5. 重连多次失败时显示“刷新局面”和“继续自动推进”按钮；两者始终依赖后端确认。

`waiting_for_human = false` 时仅显示 AI 正在行动的安全状态。为 true 时，`human_actions` 决定动作控件；`legal_target_ids` 决定目标按钮；`phase_text` 为面向玩家的阶段文案。提交开始后禁用同一面板直到收到后端响应，防止重复命令。

## 5. 可行动作

| 后端动作 | 前端交互 |
|---|---|
| `speak` | 最长 500 字的公开发言框与发送按钮 |
| `end_discussion` | 确认结束讨论按钮 |
| `wolf_kill`、`inspect`、`witch_save`、`witch_poison`、`vote` | 从后端候选中选择一个玩家后确认 |
| `abstain`、`noop` | 单击确认安全跳过 |

所有错误由 HTTP 422 或网络异常转换为简短用户提示；不得展示服务端堆栈、原始模型输出或未授权数据。死亡后的投影由后端决定，前端不尝试恢复自己的行动面板。结局状态只以投影中允许的身份和事件渲染。

## 6. 后端静态托管与兼容性

FastAPI 增加静态资源和 SPA fallback，但 API 文档、`/api/*` 与 `/api/rooms/*/events` 的 WebSocket 路由优先于前端回退。开发模式继续支持 Vite 跨源请求；允许的 CORS 来源保留 `localhost:5173` 与 `127.0.0.1:5173`。

静态托管缺少构建目录时不会阻止 API 启动：开发者仍可单独启动 Vite。生产/演示入口的构建文档会明确前后端启动顺序。

## 7. 测试与验收

前端单元测试覆盖 API Cookie 请求选项、事件序号去重、动作到请求体映射、敏感字段不渲染以及网络失败显示。Playwright 端到端测试使用可控的离线模型替身，覆盖：

1. 创建预言家房间并看到 AI 自动推进后的合法查验；
2. 提交人类行动并在时间线看到安全结果；
3. 模拟 WebSocket 断开，恢复后事件不重复；
4. 完成至少一个对局结局视图，并确认其他存活玩家身份和 Agent memory 不出现在 DOM。

验收条件：用户无需手动复制令牌或构造 API 请求，即可在浏览器完成一局标准六人局；页面不会泄露服务端私密信息；断线和后端拒绝不会造成错误的本地状态；开发与生产式本地启动均有文档和自动化验证。
