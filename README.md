# Werewolf Arena

面向“1 名人类玩家 + 5 名 AI 玩家”的本地 Web 狼人杀产品。当前已完成服务端权威游戏内核、SQLite 房间、会话授权、REST/WebSocket 事件流、兼容 OpenAI Chat Completions 的 AI 自动运行时，以及可直接游玩的 React 浏览器界面。

产品设计见 [Web 产品方案](docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md)，实施路线见 [Phase 3 计划](docs/superpowers/plans/2026-08-26-werewolf-arena-phase-3-agent-runtime.md)。

## 当前阶段

目前已可在本地浏览器创建标准六人局、与五名 AI 继续对局，并通过 HttpOnly Cookie 保持房间会话。首页仅在当前浏览器保存房间历史；玩家出局后进入公开信息旁观模式；对局结束后可查看安全的完整复盘（获胜阵营、身份揭示和公开事件）。历史卡片可继续或删除对局，删除会同时清理服务端房间与本地记录。

模型运行时仍采用严格的信息隔离：AI 与浏览器只能读取各自被授权的状态，原始模型输出、思维链、其他玩家的存活身份和服务端事件不会通过 API 暴露。

后端运行与验证说明见 [backend/README.md](backend/README.md)。

浏览器界面位于 [frontend](frontend)。开发请先启动后端，再在该目录执行 `npm install` 和 `npm run dev`；完整说明见 [后端启动文档](backend/README.md#启动浏览器界面)。
