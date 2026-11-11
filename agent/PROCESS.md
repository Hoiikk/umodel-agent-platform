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
7. 标准错误里的 `[工具]` 和 `[结果]` 对得上，再看标准输出的结论。结论多出来的人数、原因、评价，都算没做完。

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

已完成。第二张表是职位编制 `rms.opening`，只能按一个编号查。字段是 opening_id、title、headcount。种子是 job-001 前端工程师 2 人、job-002 后端工程师 1 人、job-003 测试工程师 1 人、job-004 产品经理 1 人。没有按编制去列候选人的语句。

验收（替身开着）：

```sh
connector\.venv\Scripts\python -m data_agent job-001 这个职位编制要招几个人
connector\.venv\Scripts\python -m data_agent 查一下 job-999 这个编制
```

第一条写出前端工程师、编制人数 2。第二条写没有这个编制。不要编出人数，也不要列出候选人。

## 项 6. 关系和遍历

不做。没有推荐关系，也没有「某编制下有哪些候选人」这种查询。不在 `local_lab.py` 里假造图，也不为 `.topo`、`.graph` 单写一套拒绝。这类句子和其他非法 SPL 一样，直接拒绝，不进数据库。

## 什么时候都不做

- 不因为提示词写得更细，就让模型列出它没查过的编号。
- 不把数据库密码、连接串放进工具参数或模型请求。
- 不在 `agent.py` 里拼接 SQL。
- 用户没提出新的问法之前，不加框架。当前循环是 `run`：模型返回工具调用就执行，返回文字就结束。这个循环表达不了的步骤（要人中途确认、做到一半持久化再恢复）出现之后，再单独立项，不提前换 LangGraph。
