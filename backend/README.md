# Werewolf Arena 后端内核

当前 Phase 1 提供可独立测试的服务端权威规则内核：

- 标准六人局与版本化 Python 角色插件；
- 不可变 `GameState` 和追加式权威事件；
- 身份分配、夜晚结算、投票、药物资源和胜负规则；
- 仅输出授权字段的状态/事件投影；
- 基于初始状态与已接受命令的确定性回放。

当前阶段按设计不包含 HTTP 服务、浏览器 UI、数据库或真实模型调用。

## 验证

在仓库根目录执行：

```powershell
cd backend
uv sync --all-groups
uv run pytest -q
uv run ruff check .
uv run mypy src
```

首次同步需要下载依赖；运行时依赖只安装在 `backend/.venv`。Phase 2 将在该领域内核之上加入 SQLite、房间运行时、FastAPI 与 WebSocket。
