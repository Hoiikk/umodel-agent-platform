---
name: modify-candidate-state-machine
description: SOP for safely modifying the RMS candidate state machine — adding/removing states, adding/removing transitions, or changing terminal states — with mandatory sync across packages/shared, Jest tests, seed data, frontend label maps, and AGENTS.md. Use when a task involves changing CandidateStatus, the transition table, canTransition/assertTransition, or candidate status flow rules.
---

# 修改候选人状态机 SOP

状态机是本仓库的硬性约束（见 `AGENTS.md` §3.1）。唯一事实源是 `packages/shared` 中的状态枚举与流转校验函数。任何变更必须做到**代码、测试、文档三方同步**，缺一不可。

## 第一步：确认变更类型

| 类型 | 示例 |
| --- | --- |
| A. 新增状态 | 增加 OFFER（Offer 沟通） |
| B. 删除状态 | 去掉某个中间态 |
| C. 新增流转边 | 允许 INTERVIEWING → SCREENING 回退 |
| D. 删除流转边 | 禁止 APPLIED 直接淘汰 |
| E. 修改终态 | 让 HIRED 不再是终态 |

变更类型决定下方 checklist 的影响面，但「标准流程」对所有类型都适用。

## 标准流程（所有类型必做）

```
- [ ] 1. 改 packages/shared：CandidateStatus 枚举 + 流转表（canTransition / assertTransition 的唯一事实源）
- [ ] 2. 同步改状态机单测（AGENTS.md：改状态机不改测试 = 任务未完成）
- [ ] 3. 全仓搜索受影响的状态枚举成员，检查 routes / services / 前端是否有硬编码引用
- [ ] 4. 检查 apps/backend/src/data/seed.ts：种子候选人是否处于受影响的状态
- [ ] 5. 检查前端状态文案 / 颜色映射（label map）是否覆盖新状态
- [ ] 6. 更新 AGENTS.md §3.1 的流转表
- [ ] 7. 按 AGENTS.md §4 收尾：npm test 全绿 → 更新 PROGRESS.md → Conventional Commits 提交
```

## 红线（违反即任务不合格）

- 禁止绕过 `packages/shared` 的统一校验函数，在 routes / services 里手写流转判断。
- 禁止只改代码不改 `AGENTS.md`，或只改文档不改代码。
- 非法流转的 API 响应必须保持 HTTP 409 + `{ "error": { "code": "INVALID_TRANSITION" } }`。
- 前端禁止自行实现流转规则，只能按后端返回的「可用动作」渲染。

## 分类型注意事项

**A. 新增状态**：枚举、流转表（入边 + 出边）、前端文案映射、AGENTS.md 流转表加一行；测试必须覆盖新状态的所有合法入边/出边和至少一条非法边。

**B. 删除状态**：先处理存量——`seed.ts` 中处于该状态的候选人必须迁移或删除；再依赖 TypeScript 编译错误找出所有残留引用，逐一清除。

**C / D. 增删流转边**：改动最小——流转表 + 对应测试 + AGENTS.md 表格。注意删边后，处于该来源状态的存量候选人会失去一条出路，需向用户确认业务上可接受。

**E. 修改终态**：「终态无出边」是校验函数的不变量，改终态等于改不变量，对应测试必须更新。

## 测试用例最低清单

- 每条新增合法边：`canTransition` 返回 `true`
- 每条被禁边（跨级跳、回退、终态出边）：返回 `false` / `assertTransition` 抛错
- 每个终态：对所有其他状态均不可流转

## 提交建议

状态机变更的核心在 `packages/shared`，commit 示例：`feat(shared): 状态机新增 OFFER 状态`。若同时改了前端文案和后端种子，可按 workspace 拆成多个 commit。
