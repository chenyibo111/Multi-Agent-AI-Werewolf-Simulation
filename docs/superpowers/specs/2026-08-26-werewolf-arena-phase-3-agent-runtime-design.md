# Werewolf Arena Phase 3 Agent Runtime 设计

**状态：已确认，待实施**  
**日期：2026-08-26**  
**分支：`feature/phase-3-agent-runtime`**

## 1. 目标与边界

Phase 3 交付一个无需 React 界面、但可经由 REST/WebSocket 与 5 名真实 AI 完整对局至结局的后端闭环。模型通过 OpenAI Chat Completions 兼容接口调用，配置只来自 `backend/.env`：`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`。

本阶段新增 Agent Runtime、自动昼夜调度、人类等待状态、模型调用预算与失败降级、调用统计和重启恢复。领域规则仍是唯一能够改变 `GameState` 的组件；模型、浏览器和角色插件不能直接写状态。

本阶段不实现 React 页面、账号、公网部署、多人真人房间、模型流式输出、原始 Prompt/模型文本存档或通用规则编辑器。

## 2. 架构

```text
REST 人类命令 / continue
          ↓
RoomRuntime（单房间 asyncio.Lock）
          ↓
GameOrchestrator（自动行动或等待人类）
          ↓
AgentPolicy ← AgentObservation ← AgentMemory
          ↓
OpenAICompatibleClient（AsyncOpenAI）
          ↓
AgentDecision（受限 JSON）→ GameCommand
          ↓
GameEngine（角色、阶段、目标、资源二次校验）
          ↓
SQLite 快照、事件、AgentRunRecord、权限投影与 WebSocket
```

### 2.1 组件职责

- `domain/`：扩展可完整结束一局所需的讨论、跳过和弃权命令；永不导入 FastAPI、SQLAlchemy 或模型 SDK。
- `agents/`：定义 AI 观察视图、决策模型、私有记忆、模型客户端与策略。模型只生成意图，不能指定 actor 或修改状态。
- `runtime/GameOrchestrator`：按当前阶段决定应自动行动的 AI 或应等待的人类；在每个命令后持久化并继续推进。
- `RoomRuntime`：在同一锁中串行化人类命令、AI 命令与自动阶段推进，向订阅者发布投影事件。
- `persistence/`：保存权威快照、追加事件、私有 Agent 记忆和脱敏模型调用统计；不保存密钥、完整 Prompt、原始模型回答或思维链。
- `api/`：提供 create、command、continue 和安全状态视图；为以后浏览器连接设置房间路径级 HttpOnly Cookie，同时保留 Bearer Token。

## 3. Agent 契约与信息隔离

### 3.1 AgentObservation

每个 AI 只接收以下信息：

- 安全的公共事件摘要、存活玩家、回合和当前阶段；
- 自己的角色、资源、自己收到的私有事件与狼人队友（仅狼人）；
- 与当前阶段匹配的合法动作和合法目标；
- 自己的 `AgentMemory` 摘要及其来源事件序号。

Observation 不包含其他玩家角色、服务器事件、其他 Agent 私有记忆、API 密钥、完整权威快照或模型原始文本。

### 3.2 AgentDecision

模型输出必须是 JSON 对象，字段限定为 `kind`、`target_id`、可选公开 `speech` 与 `public_reason`。服务端固定 actor 为该 Policy 绑定的 AI 玩家，随后构造 `GameCommand` 并让 `GameEngine` 再次校验。

`speech` 仅在 `DAY_DISCUSSION` 使用，并受最大长度限制。`public_reason` 是简短的玩家可见解释，不允许包含模型思维过程或私密事实。

### 3.3 AgentMemory

每个 AI 的记忆保存为服务端私有摘要，包含已知事实、公开承诺、怀疑/投票线索、私有技能结果、资源状态和未完成目标。摘要引用已处理事件的最大序号；旧文本不无限累积。记忆保存在权威快照中，重启时恢复，且永不进入浏览器投影。

## 4. 模型客户端、预算与降级

`OpenAICompatibleClient` 使用 `AsyncOpenAI(api_key, base_url)` 调用 Chat Completions。所有配置缺失时返回不含密钥的配置错误。真实模型仅在 `.env` 配置完整时创建；单元测试一律使用脚本化异步假模型。

每次调用具有超时、一次指数退避重试和一次 JSON 格式修复调用。有效 JSON 仍需通过 Pydantic 验证及领域校验。模型超时、网络错误、格式错误、非法动作或预算耗尽时，调度器生成当前阶段合法的安全降级：夜间 `NOOP` 或确定性协同目标，白天发言为空、投票弃权。任何降级必须写入不泄露供应商细节的权威事件。

预算按房间管理：最大模型调用数、单次最大输出 Token、总输入/输出 Token、可选美元成本上限。每次尝试创建 `AgentRunRecord`，只保存模型名、状态、Token、延迟、成本和失败分类。

## 5. 完整对局调度

### 5.1 夜晚

顺序固定为狼人、预言家、女巫。

- 人类不是当前行动者时，调度器自动驱动对应 AI。
- 人类是当前行动者时，运行时持久化后返回 `waiting_for_human`，不设置等待超时。
- 人类不是狼人时，一名 AI 狼担任当夜协调者，选定合法目标；另一名狼复用目标。
- 人类是狼人时，AI 狼以私有建议事件给出目标，人类提交最终目标，AI 狼提交相同目标。

### 5.2 白天讨论与投票

夜间公告后，所有存活 AI 按稳定座位顺序各生成一次公开陈述。人类可多次 `SPEAK`；每次人类发言后，调度器最多选择一名 AI 公开回应。人类提交 `END_DISCUSSION` 后进入投票。

AI 按稳定座位顺序投票；轮到人类时暂停。`ABSTAIN` 与 `NOOP` 是合法的显式降级/跳过命令，保证任一阶段不会因模型失败而卡死。投票结算处理唯一最高票、平票与无人有效投票。

### 5.3 重启与幂等性

每条已接受的人类或 AI 命令、每次阶段变化、每次模型调用统计和记忆更新均先持久化再发布。`continue` 只从当前快照的下一个未完成步骤推进；已经产生事件的模型决策不会在重启后再次调用或重复写入。

## 6. API 与浏览器认证

- `POST /api/rooms`：创建房间后自动推进，直到人类等待点或结局。
- `POST /api/rooms/{room_id}/commands`：接受人类命令并自动推进，返回安全状态、增量事件与等待提示。
- `POST /api/rooms/{room_id}/continue`：授权恢复未完成房间，不重复已经持久化的决策。
- 投影视图新增 `waiting_for_human`、合法人类操作、可选目标和安全阶段提示。

创建房间仍只在响应中一次性返回原始会话令牌，并同时写入路径为 `/api/rooms/{room_id}` 的 HttpOnly、SameSite=Lax 本地 Cookie。REST 和 WebSocket 都支持该 Cookie 或现有 Bearer Token；多局房间因路径不同不会相互覆盖。

## 7. 测试与验收

自动化测试使用脚本化假模型，验证：

1. Observation 不泄露其他玩家身份或私有事件；
2. 正常 JSON 决策能被转换并经领域校验执行；
3. 格式错误、越权目标、超时、预算耗尽都会安全降级；
4. 假模型可驱动标准六人局到胜负，并在人类操作点暂停；
5. 重启后不会重复模型调用、事件或预算扣减；
6. API/WebSocket 只返回授权投影，Cookie 和 Bearer 均无法跨房间访问。

真实模型 smoke test 不作为默认测试集的一部分，仅在 `.env` 完整且显式启动命令存在时运行，并只报告脱敏的调用统计。

## 8. 完成标准

Phase 3 完成时，开发者可配置一个 OpenAI 兼容服务，在无 React 的情况下使用 REST/WebSocket 创建房间、观察 5 个 AI 自动行动、在自己回合不限时操作，并将一局玩至结局。对局能在服务重启后恢复；模型故障不会造成卡死或权限泄露。
