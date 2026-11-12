## 2026-11-12 候选人所属编制
- 完成：候选人主表新增 `opening_id` / `openingId`，外键指向 `openings.id`。种子按职位对上：前端 job-001，后端 job-002，测试 job-003，产品 job-004。看板不展示这一列
- 变更文件：db/init/001_schema.sql、db/init/003_seed.sql、db/init/004_openings.sql、db/migrations/006_candidate_opening_id.sql、packages/shared/src/candidate.ts、apps/backend/src/data/candidates.json、apps/backend/src/repositories/mysqlCandidateRepository.ts、apps/backend/tests/candidateRead.test.ts、AGENTS.md、PROGRESS.md
- 遗留 / 风险：已经初始化过的 Docker MySQL 要先有编制表，再手工执行 `db/migrations/006_candidate_opening_id.sql`。本机验收走 `agent/local_lab.py`

## 2026-11-11 职位编制表
- 完成：新增 `openings` 表，供连接器按编号读取编制。种子 4 行：job-001 前端工程师 2、job-002 后端工程师 1、job-003 测试工程师 1、job-004 产品经理 1。候选人主表和看板没有改
- 变更文件：db/init/001_schema.sql、db/init/004_openings.sql、db/migrations/005_openings.sql、PROGRESS.md
- 遗留 / 风险：已经初始化过的 Docker MySQL 不会重跑 init，需要手工执行 `db/migrations/005_openings.sql`。本机验收走 `agent/local_lab.py`，不依赖这张 Docker 表

## 2026-11-11 候选人增加淘汰原因
- 完成：主表新增 `reject_reason` / `rejectReason`。种子里只有 cand-006 为「技能不匹配」，其余为 null。连接器模型、本机替身和 Agent 提示词同步能读到这一列
- 变更文件：db/init/001_schema.sql、db/init/003_seed.sql、db/migrations/004_reject_reason.sql、packages/shared/src/candidate.ts、apps/backend/src/data/candidates.json、apps/backend/src/repositories/mysqlCandidateRepository.ts、apps/backend/tests/candidateRead.test.ts、AGENTS.md、PROGRESS.md
- 遗留 / 风险：已经初始化过的 Docker MySQL 不会重跑 init，需要手工执行 `db/migrations/004_reject_reason.sql`。看板不展示这一列。Agent 侧的文档在仓库 `agent/PROCESS.md`

## 2026-09-23 重写 AI Coding 培训讲义
- 完成：按本仓库真实 RMS（五态线性、8 字段、packages/shared、51 条单测）重写 ai_coding.html。17 张 cursor_screenshot 全部嵌入，点击可全屏、方向键翻页。同步了 Cursor 用法（Agent / Ask / Plan、@ 引用、Skill 靠 description 触发、AGENTS.md 每轮注入）以及国内可用模型的成本口径（DeepSeek、千问、Cursor 内的 Composer 与 Kimi；不含 Codex）。旧的四列 / 6 字段示例已替换为本仓库实录
- 变更文件：ai_coding.html、PROGRESS.md
- 遗留 / 风险：模型标价核对到 2026-09，之后调价需人工改讲义中的价格表；本次未改业务代码

## 2026-09-23 阶段性收尾总结
- 已完成模块：
  - packages/shared：Candidate 8 字段契约、五态 CandidateStatus 枚举、状态机（STATUS_TRANSITIONS / isCandidateStatus / validateStatusTransition / getAvailableTransitions）、AiMatchScore 契约
  - apps/backend：store / service / routes 三层；GET /api/candidates、PATCH /api/candidates/:id/status（非法流转 409 INVALID_TRANSITION）；GET /api/candidates/ai-matches（AI 简历匹配分批量接口：aiParserService 确定性关键词打分 + resumeStore/resumes.json 简历 sidecar）；store 读取优化（id 哈希索引 + 冻结快照复用，写入即失效）
  - apps/frontend：五列看板（已投递 / 筛选中 / 面试中 / 已录用 / 已淘汰），卡片动作由 getAvailableTransitions 驱动（无回退），AI 匹配分三档标签（tooltip 展示命中关键词），409 错误横幅提示
  - 测试：51 条 Jest 单测全绿——状态机 5×5 穷举 28 条、AI 打分 15 条、读取契约 8 条（HTTP 层真实 express 随机端口锁定字段 / 条数 / 顺序）
- Schema 冻结状态：Candidate 8 字段（id / name / phone / email / position / status / source / createdAt）自创建起零变更，与 AGENTS.md §3.2 清单一致；状态机五态线性无回退（6 合法边 / 19 非法边），与 §3.1 流转表及单测一致；功能扩展（AiMatchScore 契约、简历原文 sidecar）均未侵入主表，GET /api/candidates 返回由契约测试锁定
- 遗留事项：无持久化（内存存储、重启丢数据，§3.3 预期行为）；无鉴权 / 权限控制（接口全部匿名可访问）；无候选人创建 / 删除接口；无前端单测（仅后端 Jest）；AI 打分为关键词启发式、未接真实模型；jest worker 退出告警未排查（既有现象）
- 下一步建议：候选人录入接口（POST /api/candidates）并与简历 sidecar 联动；看板按职位 / 来源筛选；打分可解释性增强（命中关键词明细展开）；若引入持久化或鉴权，须先显式评审修改 AGENTS.md §3
- 变更文件：PROGRESS.md（纯文档收尾；代码自 e20b309 起无变更，该提交 npm test 51 passed / tsc 通过）

## 2026-09-23 候选人读取性能优化（store 层）
- 完成：先落地 GET /api/candidates 读取契约测试（HTTP 层真实 express 随机端口：每条恰好 8 个冻结字段 / 条数与种子一致 / 顺序与种子声明一致 / 整体与种子深度一致；store 层：重复读取一致、getCandidate 命中与未命中、写入后读可见兜底），确认 51 tests 全绿后再动实现；优化仅改 apps/backend/src/data/store.ts 内部——candidateById（id → Candidate 哈希索引，O(1)）+ listSnapshot（有序快照冻结复用、写入即失效），listCandidates 从每次 O(n) 重建数组变为摊还 O(1)，函数签名与返回契约零变更；用户约束中的 backend/src/store/candidateStore.ts 在仓库不存在，按 AGENTS.md 目录约定落实于 data/store.ts
- 变更文件：apps/backend（src/data/store.ts、tests/candidateRead.test.ts）、PROGRESS.md
- 遗留 / 风险：无（优化后 `npm test` 51 passed、后端 `tsc --noEmit` 通过；jest worker 退出告警为改动前既有现象）

## 2026-09-23 新增 AI 简历匹配分功能
- 完成：确定性关键词启发式打分（scoreResume 纯函数 + 职位技能词典 + ASCII 边界匹配防 Java/JavaScript 子串假阳性），打分逻辑独立成 aiParserService.ts；简历原文存 sidecar（resumes.json + resumeStore.ts 独立 Map），不进主表；独立批量接口 GET /api/candidates/ai-matches（返回 AiMatchScore[]，仅 candidateId / score / matchedKeywords，未录入简历的候选人不出现）；前端卡片仅新增一个三档配色分数标签（≥80 绿 / ≥60 黄 / 其余灰，tooltip 展示命中关键词），看板核心渲染未动；Candidate 契约与 GET /api/candidates 返回零改动（已在线验证主表接口字段不变）
- 变更文件：packages/shared（src/aiMatch.ts、src/index.ts）、apps/backend（src/services/aiParserService.ts、src/data/resumeStore.ts、src/data/resumes.json、src/routes/candidates.ts、src/app.ts、tests/aiParser.test.ts）、apps/frontend（src/api.ts、src/App.tsx、src/index.css）、PROGRESS.md
- 遗留 / 风险：无（`npm test` 43 passed；`npm run build -w @rms/frontend` 与后端 `tsc --noEmit` 通过；浏览器验证六张卡片分数标签 87/58/70/80/83/20 渲染正确）

## 2026-09-23 实现前端五列看板
- 完成：用户指令（四列、推进/回退按钮、字段以不存在的 backend/src/types/candidate.ts 为准）与 spec.md / AGENTS.md 冲突，经用户确认按文档校正——五列看板（已投递/筛选中/面试中/已录用/已淘汰），卡片按钮由 `getAvailableTransitions()` 驱动（无回退），调 PATCH /api/candidates/:id/status，后端 409 时页面提示；不改后端任何文件
- 变更文件：apps/frontend（package.json、tsconfig.json、vite.config.ts、index.html、src/main.tsx、src/index.css、src/api.ts、src/statusMeta.ts、src/App.tsx）、package-lock.json、PROGRESS.md
- 遗留 / 风险：无（`npm test` 28 passed，`npm run build -w @rms/frontend` 通过；`npm run start:frontend` 现已可用）

## 2026-09-22 实现后端候选人查询与状态流转
- 完成：按 AGENTS.md / spec.md（五态线性、8 字段）实现 store / service / routes 三层；`validateStatusTransition()` 唯一定义于 packages/shared；GET /api/candidates、PATCH /api/candidates/:id/status（非法流转 HTTP 409 INVALID_TRANSITION）；状态机单测穷举 6 条合法边 + 19 条非法边。根目录 `npm test`：28 passed
- 变更文件：package.json、package-lock.json、.gitignore、packages/shared（package.json、src/index.ts、src/statusMachine.ts）、apps/backend（package.json、tsconfig.json、jest.config.js、src/app.ts、src/index.ts、src/data/store.ts、src/services/candidateService.ts、src/routes/candidates.ts、tests/statusMachine.test.ts）、PROGRESS.md
- 遗留 / 风险：尚无 frontend workspace，`npm run start:frontend` 暂不可用；用户口述的四态双向 / 6 字段已按文档校正为五态线性 / 8 字段

## 2026-09-22 创建候选人数据契约与种子数据
- 完成：用户指令（6 字段 / 四态小写 / backend/src 路径）与 AGENTS.md §3 冲突，经用户确认按 AGENTS.md 校正执行——契约建于 packages/shared/src/candidate.ts（8 个软冻结字段、五态大写 CandidateStatus），种子建于 apps/backend/src/data/candidates.json（6 条，覆盖 APPLIED×2 / SCREENING / INTERVIEWING / HIRED / REJECTED）；未写接口与前端代码
- 变更文件：packages/shared/src/candidate.ts、apps/backend/src/data/candidates.json、PROGRESS.md
- 遗留 / 风险：仓库尚无 package.json / tsconfig，npm test 无法执行；契约待 packages/shared 打包配置后才能被前后端 import；种子 JSON 待后续 seed.ts 加载

## 2026-09-22 对齐 docs/spec.md 与 AGENTS.md
- 完成：重写 spec.md，消解与 AGENTS.md 的冲突——五态（APPLIED / SCREENING / INTERVIEWING / HIRED / REJECTED）、线性无回退、非终态可 REJECTED、录用须经面试、非法流转 HTTP 409 INVALID_TRANSITION、候选人 8 字段软冻结、内存 + seed.ts；遗留冲突已消除
- 变更文件：docs/spec.md、PROGRESS.md
- 遗留 / 风险：无（spec 已与 AGENTS.md §3 严格一致；用户口述中的 INTERVIEW / OFFER 已按 AGENTS.md 校正为 INTERVIEWING / HIRED）。本仓库当前无 package.json，本次文档任务无法执行 npm test
