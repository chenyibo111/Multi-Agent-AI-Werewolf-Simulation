# Werewolf Arena

面向“1 名人类玩家 + 5 名 AI 玩家”的本地 Web 狼人杀产品。当前已完成服务端权威游戏内核，以及可在本机启动的 SQLite 房间、会话授权、REST API 与 WebSocket 事件流。

产品设计见 [Web 产品方案](docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md)，实施路线见 [Phase 2 计划](docs/superpowers/plans/2026-08-26-werewolf-arena-phase-2-runtime-api.md)。

## 当前阶段

Phase 2 提供本地 FastAPI 服务，但尚未接入 React 界面、真实大模型行动策略或 AI 自动推进。这些是后续阶段的工作。

后端运行与验证说明见 [backend/README.md](backend/README.md)。
