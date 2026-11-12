# Data Agent 开发步骤

一次只做下面的一项。做完，用该项的验收问题在本机跑通，再开下一项。数据变复杂时，先让连接器能查出新数据，再让 Agent 使用它。提示词不能制造查询能力。

手工验收前，仓库根目录要有一个一直开着的窗口：

```sh
connector\.venv\Scripts\python agent\local_lab.py
```

另一个窗口：

```sh
connector\.venv\Scripts\python -m data_agent 这里写验收问题
```

单元测试不访问模型，也不访问数据库：

```sh
connector\.venv\Scripts\python -m pytest agent
```

## 每一项都按这个顺序

1. 把用户原话写下来，并指出答案来自哪几行、哪个字段。指不出字段，就停，不要改代码。
2. 现有的单编号查询已经能回答：只补种子，不改 Agent。
3. 现有查询形状回答不了：先改连接器的模型和渲染，再改 `SPL_PATTERN`、工具说明和 `SYSTEM`。Agent 不写 SQL，密码不进模型请求。
4. 没有 Docker 时，`local_lab.py` 要能回答这条新 SQL。替身拒绝的语句，Agent 也不能当成查到了。
5. 给新语句加单元测试：非法 SPL 不调用存储；合法 SPL 走到注入的 `execute`；模型给出文字后循环停止。
6. 开着替身，跑该项的验收问题。查一个不存在的编号，结论里要写没查到。
7. 标准错误里的 `[工具]` 和 `[结果]` 对得上，再看标准输出的结论。问题里写明的编号如果没查全，会先出现 `[检查]`，这时还不能看结论。结论多出来的人数、原因、评价，或没查过的编号，都算没做完。

每一项都不改 `third_party/UnifiedModel`。每次调用连接器都新建一个 `Assistant`，因为 `execute_sync` 会关掉 MySQL 连接池。身份用环境变量里的 `Principal("data-agent", "local")`，不放进工具参数。

候选人行要同时改这三处，否则界面、Docker 和本机替身各看各的：

| 谁在读 | 文件 |
|---|---|
| 本机替身（现在的测试路径） | `agent/local_lab.py` 的 `_ROWS` |
| Docker 里的 MySQL（只在空库第一次初始化时执行） | `rms/db/init/003_seed.sql` |
| RMS 页面和后端 | `rms/apps/backend/src/data/candidates.json` |

`resumes.json` 只服务 RMS 的简历打分。Agent 不读它。再加列或第二张表，要等下一项的触发条件出现。

## 项 0. 按一个编号点查

已完成。模型决定查哪个编号，连接器查 `rms.candidate`，一次一个 `ids`。

能回答的问题：某个已知编号的状态、职位、来源、打码后的姓名电话邮箱。`cand-004` 和 `cand-008` 都是面试中，比先后应当并列。`cand-005` 和 `cand-007` 都是已录用。`cand-999` 应当说没查到。

还不能回答、也不要靠提示词回答的问题：总共多少人。没有返回的数字不能写进结论。没有面试评价。淘汰原因只看 `reject_reason`，空值不能补写。

相关代码：

- `agent/src/data_agent/agent.py`：`_SPL_PATTERNS`、`TOOLS`、`SYSTEM`、`MAX_STEPS = 5`
- `connector/src/umodel_assistant/renderers.py`：只渲染 `.entity_set`
- `connector/model/entity_set/rms.candidate.yaml`：含 `reject_reason`

## 项 1. 补对照用的种子

已完成。在原来 6 人之外加了两行：

| 编号 | 作用 |
|---|---|
| cand-007 | 第二个已录用，并且是前端工程师。前端因此有已投递、面试中、已录用 |
| cand-008 | 第二个面试中，并且是后端工程师。和 cand-004 比先后应当并列 |

验收（替身开着）：

```sh
connector\.venv\Scripts\python -m data_agent 比较 cand-004 和 cand-008，谁在招聘流程里更靠后
connector\.venv\Scripts\python -m data_agent 分别查询 cand-005 和 cand-007，谁是已录用
```

第一条的结论是两人阶段相同。第二条两人都是已录用。问「现在总共几个 cand」时，不调用工具，也不回答 8。

## 项 2. 按状态或职位查出一批人

已完成。用户不报编号时，按一个状态或一个职位查。一次只能填一种，不能和编号拼在一起，也不能写成任意 WHERE。

```
.entity_set with(domain='rms', name='rms.candidate', status='HIRED')
.entity_set with(domain='rms', name='rms.candidate', position='前端工程师')
```

`status` 只能是五种状态之一。返回几行就写几行。问「总共几个 cand」时仍然没有对应查询，不能把几次结果加总。

验收：

```sh
connector\.venv\Scripts\python -m data_agent 哪些候选人是已录用
```

`[结果]` 里同时有 cand-005 和 cand-007，没有其他人。结论只点这两人。

不要用提高 `MAX_STEPS` 代替这一项。5 轮够不够，等真的出现「已经查了 5 轮，停止」再处理，那是项 4。

## 项 3. 答案需要新字段

已完成。新增 `reject_reason`（淘汰原因）。只有 cand-006 写了「技能不匹配」，其余为空。这不是个人信息，不打码。面试评价和部门还没有。

验收（替身开着）：

```sh
connector\.venv\Scripts\python -m data_agent cand-006 的淘汰原因是什么
connector\.venv\Scripts\python -m data_agent cand-004 的淘汰原因是什么
connector\.venv\Scripts\python -m data_agent 查询 cand-999
```

第一条的结论是技能不匹配。第二条写没有这项数据。第三条写没查到。不要出现种子里没写过的评价。

## 项 4. 一轮里要合法地查很多次

已检查，不提高 `MAX_STEPS`。同一轮模型可以带上多条合法查询，这些查询只占一轮。问 cand-001 到 cand-008 各自的状态时，8 次编号查询发生在第 1 轮，第 2 轮就写出结论，没有出现「已经查了 5 轮，停止」。

验收（替身开着）：

```sh
connector\.venv\Scripts\python -m data_agent 分别告诉我 cand-001 到 cand-008 各自现在是什么状态
```

结论按查到的行写出这 8 个人的状态。没查到的编号不能补上。上限仍是 5 轮；到了上限必须停止，不能把没查到的人写进结论。

## 项 5. 第二张表

已完成。第二张表是职位编制 `rms.opening`，只能按一个编号查。字段是 opening_id、title、headcount。种子是 job-001 前端工程师 2 人、job-002 后端工程师 1 人、job-003 测试工程师 1 人、job-004 产品经理 1 人。按职位名称列候选人见项 8。按编制编号列出这个编制下的人，见项 11。

验收（替身开着）：

```sh
connector\.venv\Scripts\python -m data_agent job-001 这个职位编制要招几个人
connector\.venv\Scripts\python -m data_agent 查一下 job-999 这个编制
```

第一条写出前端工程师、编制人数 2。第二条写没有这个编制。不要编出人数，也不要列出候选人。

## 项 6. 关系和遍历

先不做。Docker 里的 UModel 能导入招聘模型，只满足环境。还要有一句现有查询抄不出的问题，才开始改代码。不做推荐人。不把「某编制下有哪些候选人」改成图遍历，那是项 8 和项 11。不在 `local_lab.py` 里假造图。`.topo`、`.graph` 现在和其他非法 SPL 一样直接拒绝，不进数据库。

图上的一条关系是模型里的 `entity_set_link`：从对象 A 指向对象 B，两边用同一个字段对上。电商示例是「用户包含订单」，文件是 `connector/model/link/entity_set_link/commerce.user_contains_commerce.order.yaml`。查询走 `.topo` 或 `.entity`。UModel 返回的是图上的对象和边。候选人的 8 行仍在 MySQL，导入不会把这些行装进图。

招聘模型现在没有这种边。候选人和编制只靠 `opening_id` 这一列，已经用项 10、项 11 查完。

开始前要同时满足：

1. 用户写出一句新问题，并指出答案来自哪两个对象、哪个对得上的字段。指不出，就停。
2. 这个字段不能用现有的五种 SPL 查出来。能查出来就不要做项 6。
3. Compose 里的 UModel 已在 `127.0.0.1:8080`，`local_lab.py` 已停。替身占着 8080 和 3308 时，不能导入，也不能把替身的拒绝当成图的结果。
4. 工作区 `rms` 已导入 `/model-packs/rms`。`.umodel` 能看到 `rms.candidate` 和 `rms.opening`。看不到那 8 个人，是对的。

环境准备好之后，按这个顺序做，一次只做这一项：

1. 在 `connector/model/link/entity_set_link/` 写一条边，并复制到 `integration/model-packs/rms/link/entity_set_link/`。字段对照必须是两边真实存在的列。
2. 停掉替身后启动 Compose 的 UModel，再导入一次：

```powershell
docker compose --env-file rms/.env -f integration/compose.yaml up -d umodel
cd third_party\UnifiedModel
go run ./cmd/umctl --addr http://127.0.0.1:8080 health
go run ./cmd/umctl --addr http://127.0.0.1:8080 workspace create rms
go run ./cmd/umctl --addr http://127.0.0.1:8080 umodel import rms --path /model-packs/rms
go run ./cmd/umctl --addr http://127.0.0.1:8080 query run rms ".umodel | limit 20" -o json
```

`workspace create` 已存在就跳过。`health` 必须成功。回包里要有这条新边的两端。

3. 用 `umctl query run` 对这条边跑一句 `.topo` 或 `.entity`。UModel 没有返回能抄进下一次查询的编号，就停。不要为了让演示通过去改 `local_lab.py`。
4. UModel 确实返回了编号：在 `_SPL_PATTERNS` 里只加这一句，工具说明和 `SYSTEM` 各加一句。Agent 仍不写 SQL。`run` 把返回的编号抄进下一次已有的合法查询；抄不进去或结果为空，就停止，不写结论。
5. 单元测试不访问模型和数据库：没拿到编号就写结论时，`run` 不返回那段文字；同一轮里猜的编号不算；UModel 返回空时不要求下一跳。
6. 开着真实 UModel 跑用户的那句原话。标准错误里要先看到图查询的 `[结果]`，再看到用返回编号发出的下一次查询。结论只写这次查到的行。

旧库如果还没有 `opening_id`，先按 `rms/db/migrations/005_openings.sql`、`006_candidate_opening_id.sql` 补列。这是项 9 的遗留，不是项 6。

## 项 7. 点名的编号都要查过

已完成。问题原文里出现的 `cand-` 和 `job-` 编号，每一个都要有一次合法的编号查询，才收下文字结论。查过但 `data` 为空，算查过。`cand-001 到 cand-008` 这种写法会把中间编号也算进去，但只限同一前缀、数字位数相同、两端相差不超过 20。再宽的范围只认写出来的两端。按状态或职位问、原文里没有编号时，不要求先查编号。

没查全时，这一轮的文字不作为结论。标准错误打印 `[检查]`，并把缺的编号放回对话，让模型再查。这仍然占 `MAX_STEPS` 里的一轮。轮数用完仍没查全，就停止，不把那段文字当成结论。

验收（替身开着）：

```sh
connector\.venv\Scripts\python -m data_agent 比较 cand-004 和 cand-005，谁在招聘流程里更靠后
```

标准错误里，结论出现之前要有 cand-004 和 cand-005 各自的 `[工具]` 和 `[结果]`。如果模型先写结论，会先看到 `[检查] 还没查全`，然后再出现缺的那次查询。结论只根据查到的状态写谁更靠后。已淘汰不能拿来比先后。

单元测试不访问模型：只查了其中一个就写结论时，`run` 不返回那段文字，补查之后才返回。`cand-001 到 cand-003` 必须查到中间的 cand-002。非法 SPL 不算查过。只剩最后一轮仍缺编号时，返回停止语。

## 项 8. 查完编制，再用返回的职位查候选人

已完成。问题里同时有一个 `job-` 编号和「候选人」时，先按编号查编制。结果里有 `title`，才允许用这个职位再查一次 `position`。职位名称从返回的行抄出来，和编制写在同一轮里的职位查询不算，因为那时还没看到结果。编制没查到，或 `title` 为空，不再查第二跳，结论写没有这个编制。只问编制人数、问题里没有「候选人」时，不要求第二跳。

这是职位名称对得上。两个编制如果叫同一个职位，这一跳分不开它们。从候选人身上的编制编号再查编制人数，见项 10。还剩几个名额见项 11。

验收（替身开着）：

```sh
connector\.venv\Scripts\python -m data_agent job-001 这个编制对应的职位，现在有哪些候选人
connector\.venv\Scripts\python -m data_agent 查一下 job-999 这个编制有哪些候选人
```

第一条要先有 job-001 的 `[工具]` 和 `[结果]`，`title` 是前端工程师；之后再有一次 `position='前端工程师'`。结论只写这次查到的人：cand-001 已投递、cand-004 面试中、cand-007 已录用。第二条写没有这个编制，不要再查候选人，也不要编出人名。

单元测试不访问模型：查到职位后直接写结论，`run` 不返回那段文字，补上对应的 `position` 之后才返回。同一轮里先猜职位不算。编制结果为空时，不要求第二跳。只问编制人数时，也不要求第二跳。

## 项 9. 候选人所属的编制编号

已完成。候选人表新增 `opening_id`，指向编制表的 `id`。种子是前端 cand-001、cand-004、cand-007 为 job-001，后端 cand-002、cand-005、cand-008 为 job-002，cand-003 为 job-003，cand-006 为 job-004。这一列不是空的，不要根据职位名称另编一个编号。现有的按编号查询会把这一列一并返回。拿它再去查编制人数，见项 10。

验收（替身开着，而且替身是改完列之后重新启动的）：

```sh
connector\.venv\Scripts\python -m data_agent cand-007 属于哪个编制
```

`[结果]` 里 cand-007 的 `opening_id` 是 job-001。结论写 job-001。不要写成别的编号。

## 项 10. 查完人，再用返回的编制编号查编制人数

已完成。问题里有一个 `cand-` 编号，并且在问编制人数、还要招或还剩名额时，先查这个人。结果里的 `opening_id` 要再按编制编号查一次。编号从这一行抄出来，和候选人写在同一轮里的编制查询不算。`opening_id` 为空，不再查第二跳。只问「属于哪个编制」时，这一列已经够回答，不要求第二跳。还剩几个名额要在编制人数之外再数已录用的人，见项 11。

验收（替身开着）：

```sh
connector\.venv\Scripts\python -m data_agent cand-007 的编制人数是多少
```

先有 cand-007 的 `[工具]` 和 `[结果]`，`opening_id` 是 job-001；之后再有一次编制编号 job-001 的查询。结论里的编制人数是 2。不要写成别的编号，也不要根据「前端工程师」去猜。

单元测试不访问模型：查到人后直接写人数，`run` 不返回那段文字，补上 job-001 之后才返回。同一轮里先猜编制编号不算。问「属于哪个编制」时不要求第二跳。查错编号也不算查完。

## 项 11. 用编制人数减去这个编制下已录用的人数

已完成。还剩名额不是一列。它等于这次查到的 `headcount`，减去 `opening_id` 相同、`status` 为 HIRED 的行数。已投递、筛选中、面试中、已淘汰不算已招。job-001 计划 2 人，已录用只有 cand-007，还剩 1。新语句只按一个编制编号列出候选人：

```
.entity_set with(domain='rms', name='rms.candidate', opening_id='job-001')
```

问题里有一个 `cand-` 编号，并且在问还要招几个人或还剩几个名额时，编制编号从候选人那一行抄出来。和这个人写在同一轮里的 `opening_id` 查询不算。查错编号也不算。只问编制人数时，不要求把这个编制下的人再列一遍。

验收（替身开着，而且替身是改完这条语句之后重新启动的）：

```sh
connector\.venv\Scripts\python -m data_agent cand-007 这个人的编制还要招几个人
```

先有 cand-007，`opening_id` 是 job-001；再有编制 job-001，`headcount` 是 2；再有一次 `opening_id='job-001'` 的候选人查询。这次结果里已录用的只有 cand-007。结论写计划 2、已录用 1、还剩 1。不要把 cand-001、cand-004 算进已招，也不要编一个没有返回的差。

单元测试不访问模型：查完编制就写还剩几人，`run` 不返回那段文字，补上对应的 `opening_id` 之后才返回。同一轮里先猜编制编号不算。查错编号也不算查完。只问编制人数时不要求这一跳。

## 什么时候都不做

- 不因为提示词写得更细，就让模型列出它没查过的编号。
- 不把数据库密码、连接串放进工具参数或模型请求。
- 不在 `agent.py` 里拼接 SQL。
- 用户没提出新的问法之前，不加框架。当前循环是 `run`：模型返回工具调用就执行。返回文字时，问题里点名的编号都查过了才结束；问编制下有哪些候选人时，还要用查到的职位再查一次；问编制人数时，还要用查到的编制编号再查一次；问还剩几个名额时，还要用这个编号再列出该编制下的候选人。没做完就把缺的编号或职位放回对话再查。这个循环表达不了的步骤（要人中途确认、做到一半持久化再恢复）出现之后，再单独立项，不提前换 LangGraph。
