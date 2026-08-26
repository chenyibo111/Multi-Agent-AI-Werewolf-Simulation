# Werewolf Arena 本地运行时与 API

当前 Phase 2 在服务端权威规则内核之上提供：

- 标准六人局与版本化 Python 角色插件；
- 不可变 `GameState` 和追加式权威事件；
- SQLite 房间快照、事件、会话令牌摘要持久化与重启恢复；
- 每房间异步锁，避免并发指令产生竞争；
- 基于 Bearer 会话令牌的房间 REST API；
- 按可见性过滤、支持 `after_sequence` 断点回放的 WebSocket 事件流。

不会向 HTTP 或 WebSocket 暴露完整权威 `GameState`、其他玩家身份、服务端事件、原始模型输出或思维链。当前仍不包含 React UI、真实模型调用或 AI 自动行动。

## 启动本地服务

在仓库根目录执行：

```powershell
cd backend
Copy-Item .env.example .env  # 可选：仅在希望指定 SQLite 文件位置时修改
uv sync --all-groups
uv run uvicorn werewolf_arena.api.app:create_app --factory --reload
```

默认监听 `http://127.0.0.1:8000`。SQLite 文件默认为当前 `backend/` 目录中的 `werewolf_arena.db`；也可通过环境变量 `WEREWOLF_ARENA_DATABASE_PATH` 指定。

## 浏览器验证

1. 打开 `http://127.0.0.1:8000/docs`。
2. 在 `POST /api/rooms` 中点击 **Try it out**，可填写 `{"requested_role_id":"wolf"}`，执行后复制响应中的 `session_token` 和 `room_id`。
3. 点击页面右上角 **Authorize**，输入 `Bearer <session_token>`。
4. 执行 `GET /api/rooms/{room_id}`，确认仅看到自己的 `role_id`，其他 `ai-*` 玩家没有身份字段。
5. 执行 `POST /api/rooms/{room_id}/commands`。例如人类身份为狼时提交 `{"kind":"wolf_kill","target_id":"ai-1"}`；用不匹配身份提交会安全地返回 422。
6. 可使用支持自定义 Authorization Header 的 WebSocket 客户端连接 `ws://127.0.0.1:8000/api/rooms/{room_id}/events?after_sequence=0`，携带相同 Bearer 令牌；消息只包含授权范围内的事件。

`session_token` 只会在创建接口的响应中返回一次，数据库只保存其 SHA-256 摘要。请勿将令牌提交到 Git。

## 验证

在仓库根目录执行：

```powershell
cd backend
uv sync --all-groups
uv run pytest -q
uv run ruff check .
uv run mypy src
```

首次同步需要下载依赖；运行时依赖只安装在 `backend/.venv`。
