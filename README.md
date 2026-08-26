# Werewolf Arena

面向“1 名人类玩家 + 5 名 AI 玩家”的本地 Web 狼人杀产品。当前已完成服务端权威游戏内核、SQLite 房间、会话授权、REST/WebSocket 事件流，以及兼容 OpenAI Chat Completions 的 AI 自动运行时。

产品设计见 [Web 产品方案](docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md)，实施路线见 [Phase 3 计划](docs/superpowers/plans/2026-08-26-werewolf-arena-phase-3-agent-runtime.md)。

## 当前阶段

Phase 3 已提供真实模型适配、严格 AI 观察隔离、自动推进、预算与调用审计，以及浏览器可用的房间 Cookie。React 月夜秘仪界面、对局历史/复盘和部署能力仍是后续阶段工作。

后端运行与验证说明见 [backend/README.md](backend/README.md)。
