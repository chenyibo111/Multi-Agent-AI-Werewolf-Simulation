# Werewolf Arena

面向“1 名人类玩家 + 5 名 AI 玩家”的本地 Web 狼人杀产品。当前开发位于 `feature/phase-1-foundation` 分支，已完成服务端权威游戏内核、标准六人角色插件、事件审计、权限投影与确定性回放基础。

产品设计见 [Web 产品方案](docs/superpowers/specs/2026-08-25-werewolf-arena-web-design.md)，实施路线见 [Phase 1 计划](docs/superpowers/plans/2026-08-25-werewolf-arena-phase-1-foundation.md)。

## 当前阶段

Phase 1 是纯 Python 领域内核，不提供 HTTP 服务、浏览器界面、SQLite 持久化或真实模型调用。这些能力会在后续 Phase 2～5 分阶段加入。

后端运行与验证说明见 [backend/README.md](backend/README.md)。
