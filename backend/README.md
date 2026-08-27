# Werewolf Arena 本地运行时与 API

当前版本在服务端权威规则内核之上提供：

- 标准六人局与版本化 Python 角色插件；
- 不可变 `GameState` 和追加式权威事件；
- SQLite 房间快照、事件、会话令牌摘要持久化与重启恢复；
- 每房间异步锁，避免并发指令产生竞争；
- 基于 Bearer 会话令牌和房间路径 HttpOnly Cookie 的 REST API；
- 按可见性过滤、支持 `after_sequence` 断点回放的 WebSocket 事件流。
- OpenAI Chat Completions 兼容的 AI 调度、每角色信息隔离、预算降级和调用指标持久化；
- 创建、玩家指令或 `continue` 后自动推进 AI，直至需要人类行动。
- React 浏览器对局界面、仅存储房间 ID 的本地历史、死亡后的安全全局旁观、终局复盘和房间删除。

不会向 HTTP 或 WebSocket 暴露完整权威 `GameState`、服务端事件、原始模型输出、思维链或密钥。存活玩家仍无法获取其他未公开身份和私密事件；玩家死亡后会转为安全全局视角，可查看所有游戏身份和非服务端事件。未配置模型时，服务可用于离线规则/API 验证，但 AI 不会请求外部服务。

## 启动本地服务

在仓库根目录执行：

```powershell
cd backend
Copy-Item .env.example .env
uv sync --all-groups
uv run uvicorn werewolf_arena.api.app:create_app --factory --reload
```

默认监听 `http://127.0.0.1:8000`。SQLite 文件默认为当前 `backend/` 目录中的 `werewolf_arena.db`；也可通过环境变量 `WEREWOLF_ARENA_DATABASE_PATH` 指定。

## 启动浏览器界面

开发时请打开两个终端：

```powershell
# 终端一
cd backend
uv run uvicorn werewolf_arena.api.app:create_app --factory --reload

# 终端二
cd frontend
npm install
npm run dev
```

打开 Vite 输出的本地地址（默认 `http://127.0.0.1:5173`）。前端会通过开发代理连接 API，房间 HttpOnly Cookie 会自动随请求和 WebSocket 发送，无需复制令牌。

首页会在浏览器 `localStorage` 中保存已打开房间的 ID 与时间，用于“继续对局”；它不保存会话令牌、身份或私密游戏状态。删除历史卡片会向服务端删除对应的房间，再移除本地记录。

若要用 FastAPI 单独托管构建后的页面：

```powershell
cd frontend
npm run build
cd ../backend
uv run uvicorn werewolf_arena.api.app:create_app --factory
```

此时访问 `http://127.0.0.1:8000`。需要另行托管 API 时，在 `frontend/.env` 设置 `VITE_API_BASE_URL`；本地代理模式保持为空。

若要启用 AI 对局，在 `backend/.env` 中配置：

```dotenv
LLM_BASE_URL=https://your-provider.example/v1
LLM_API_KEY=replace-with-local-secret
LLM_MODEL=your-chat-model
```

该接口采用标准 Chat Completions 协议。密钥只由服务端读取；不要提交 `.env`。

## 浏览器验证

1. 打开 `http://127.0.0.1:8000/docs`。
2. 在 `POST /api/rooms` 中点击 **Try it out**，可填写 `{"requested_role_id":"wolf"}`，执行后复制响应中的 `session_token` 和 `room_id`。浏览器同时收到仅适用于该房间路径的 HttpOnly Cookie。
3. 点击页面右上角 **Authorize**，输入 `Bearer <session_token>`；本地浏览器请求也可直接使用 Cookie。
4. 执行 `GET /api/rooms/{room_id}`。响应中的 `waiting_for_human`、`human_actions`、`legal_target_ids` 和 `phase_text` 是前端唯一应据以渲染操作的安全状态。
5. 执行 `POST /api/rooms/{room_id}/commands`。例如人类身份为狼时提交 `{"kind":"wolf_kill","target_id":"ai-1"}`。合法人类命令后服务会自动行动至下一次人类等待点；`POST /api/rooms/{room_id}/continue` 可用于重连后的显式恢复。
6. WebSocket 连接 `ws://127.0.0.1:8000/api/rooms/{room_id}/events?after_sequence=0` 可使用同一 Cookie 或 Bearer 令牌；消息只包含授权范围内的事件。

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

## 可选：真实模型 smoke 检查

此命令会实际调用配置的模型，可能产生费用；它不是常规测试的一部分。它只输出房间 ID、阶段、等待状态和脱敏的调用统计，不输出 Prompt、原始模型文本或密钥。

```powershell
uv run python scripts/smoke_real_game.py --requested-role villager --max-agent-calls 8
```

未完成 `.env` 配置时，命令会在联网前失败并列出缺少的环境变量。`--max-agent-calls` 是本次 smoke 的硬上限。
