# AGENTS.md

> 本文件是所有 AI 编码代理（以及人类贡献者）在本仓库工作的最高准则。
> 文档与代码冲突时，以本文件为准；修改「§3 硬性约束」必须显式评审，不得顺手改。

## 1. 项目简介

RMS（Recruitment Management System，招聘流程管理系统）：管理候选人从投递到录用 / 淘汰的全流程。

技术栈：

- 前端：React 18 + Vite
- 后端：Express + TypeScript
- 测试：Jest（仅后端单测）
- 存储：本地 MySQL + 版本化迁移与种子数据
- 仓库：单仓库 monorepo，npm workspaces 管理

### 目录结构约定

```
RMS_demo/
├── apps/
│   ├── frontend/            # React 18 + Vite 前端
│   │   └── src/
│   └── backend/             # Express + TypeScript 后端
│       └── src/
│           ├── routes/      # 路由层：只做参数解析、调用 service、组装响应
│           ├── services/    # 业务编排层
│           ├── domain/      # 领域逻辑（纯函数，禁止依赖 Express）
│           ├── repositories/ # 数据访问层：SQL 与映射只允许出现在这里
│           └── data/        # 仅保留测试 fixture 与非主表 sidecar 数据
├── db/                      # MySQL schema、迁移和开发种子数据
├── packages/
│   └── shared/              # 前后端共享：类型定义、状态枚举、状态机校验函数
├── AGENTS.md                # 本文件
├── PROGRESS.md              # 任务进度日志（见 §4）
└── package.json             # npm workspaces 根
```

约定：

- 凡前后端都要用的类型 / 枚举 / 常量，只允许定义在 `packages/shared`，禁止前后端各自重复定义。
- `domain/` 必须是纯 TypeScript，禁止 import Express 或任何 HTTP 相关库，保证可单测。
- 生产代码只能通过 repository 访问 MySQL；测试可注入内存 repository，不得让路由直接访问数据库。
- schema 与种子数据集中在 `db/`，以版本化 SQL 管理；应用启动不得隐式建表或重置数据。

## 2. 启动与测试命令

所有命令一律在**仓库根目录**执行：

| 命令 | 作用 |
| --- | --- |
| `npm test` | 运行后端 Jest 单测 |
| `npm run start:backend` | 启动后端（默认 http://localhost:3001） |
| `npm run start:frontend` | 启动前端（默认 http://localhost:5173，开发代理 `/api` → 后端） |
| `docker compose up -d mysql` | 启动本地 RMS MySQL（默认仅绑定 127.0.0.1） |

- 以上三个命令必须在任何时候保持可用；由根 `package.json` 的脚本转发到各 workspace。
- 依赖统一在根目录 `npm install` 安装，禁止在子包内单独执行安装。

## 3. 硬性约束（禁止事项）

### 3.1 状态流转必须走统一校验函数

候选人状态机（五态线性，无回退）：

| 当前状态 | 允许流转到 |
| --- | --- |
| APPLIED（已投递） | SCREENING、REJECTED |
| SCREENING（筛选中） | INTERVIEWING、REJECTED |
| INTERVIEWING（面试中） | HIRED、REJECTED |
| HIRED（已录用） | —（终态） |
| REJECTED（已淘汰） | —（终态） |

规则：

- 状态枚举 `CandidateStatus` 与流转校验函数（`canTransition` / `assertTransition`）**唯一定义在 `packages/shared`**。
- 后端任何修改 `candidate.status` 的代码路径，必须调用统一校验函数；禁止在路由 / service 内手写流转合法性判断。
- 前端禁止自行实现流转规则，只能根据后端返回的「可用动作」渲染操作按钮。
- 非法流转一律返回 HTTP 409，错误体格式：`{ "error": { "code": "INVALID_TRANSITION", "message": "..." } }`。

### 3.2 候选人主表字段冻结（软冻结）

冻结字段清单（`Candidate` 类型，定义于 `packages/shared`）：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `id` | `string` | 唯一标识 |
| `name` | `string` | 姓名 |
| `phone` | `string` | 电话 |
| `email` | `string` | 邮箱 |
| `position` | `string` | 应聘职位 |
| `status` | `CandidateStatus` | 当前状态（五态之一） |
| `source` | `string` | 来源渠道 |
| `rejectReason` | `string \| null` | 淘汰原因；没写就是 `null` |
| `createdAt` | `string`（ISO 8601） | 创建时间 |

规则：

- 禁止对上述字段**改名、删除、修改类型或语义**。
- 允许新增字段，但必须在**同一任务内**同步更新本节清单，否则视为违规。
- 所有 API 出入参中，候选人对象的字段名必须与本清单一致。

### 3.3 存储约束

- 本地开发数据库固定为 Compose 管理的 MySQL 8；不得连接生产或未明确批准的外部数据库。
- schema 变更必须以 `db/migrations/` 下的追加式 SQL 迁移提交；不得靠应用启动时建表、改表或重置数据。
- RMS 后端使用最小权限应用账号；供 UModel Connector 使用的账号必须是单独的只读账号，禁止写入、删表或管理权限。
- 测试默认使用隔离的测试数据库或注入 repository；不得依赖开发库中的残留数据。

### 3.4 测试约束

- 核心领域逻辑（含状态流转校验函数）必须有 Jest 单测；**改了状态机但没同步改测试 = 任务未完成**。
- 路由层 / service 层测试可选，鼓励但不强制。
- 提交前 `npm test` 必须全绿。

### 3.5 分层约束

- 业务规则只允许出现在 `domain/` 与 `services/`；路由回调和 React 组件里禁止写业务判断。
- 禁止绕过 service 层，在路由里直接读写 repository 或数据库。

## 4. 每次任务的收尾要求（Definition of Done）

每次任务（一个功能点 / 一轮对话）结束前，必须按顺序完成：

1. **测试**：`npm test` 通过。
2. **更新 `PROGRESS.md`**：在文件顶部追加一条记录，格式：

   ```markdown
   ## YYYY-MM-DD <任务简述>
   - 完成：……
   - 变更文件：……
   - 遗留 / 风险：……（无则写「无」）
   ```

3. **git 提交**：一个任务至少一个 commit，消息遵循 Conventional Commits：
   - 格式：`<type>(<scope>): <简述>`
   - `type` ∈ `feat` / `fix` / `test` / `docs` / `refactor` / `chore`
   - `scope` ∈ `frontend` / `backend` / `shared` / `repo`
   - 示例：`feat(backend): 增加候选人状态流转接口`
4. **文档同步自查**：若本次任务触碰了状态机或候选人字段，确认 §3 已同步更新，否则不许提交。
