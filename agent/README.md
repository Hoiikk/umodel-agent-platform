# Data Agent

招聘数据助手。用户用中文提问，模型选择一条允许的查询，连接器按 UModel 模型读取招聘库，再根据返回的行写出结论。查询只有 `query_umodel` 这一个工具。助手不写 SQL，数据库密码不进入模型请求。姓名、电话、邮箱在返回前打码。

一轮里可以发出多条查询。模型写出文字之前，问题里点名的编号都要查过。问某个编制有哪些候选人时，先查编制，再用返回的职位名称查候选人。问某个人的编制人数时，先查这个人，再用返回的编制编号查编制。问还剩几个名额时，再用这个编号列出该编制下的候选人，用编制人数减去其中已录用的行数。最多 5 轮。轮数用完仍缺查询时停止，没有返回的内容不写进结论。

## 能回答的问题

候选人可以按一个编号、一个状态、一个职位或一个所属编制查询。编制只能按一个编号查询。一次只能填其中一种。

| 问题 | 结论依据 |
|---|---|
| cand-004 现在是什么状态 | 这一行的 `status` |
| 哪些候选人是已录用 | `status='HIRED'` 返回的行。种子里是 cand-005 和 cand-007 |
| cand-006 的淘汰原因是什么 | `reject_reason`。只有 cand-006 写了「技能不匹配」，空值就写没有这项数据 |
| cand-007 属于哪个编制 | 这一行的 `opening_id`，是 job-001 |
| job-001 这个职位编制要招几个人 | 编制的 `title` 和 `headcount`：前端工程师，2 人 |
| job-001 这个编制对应的职位，现在有哪些候选人 | 先查到职位「前端工程师」，再按这个职位列出 cand-001、cand-004、cand-007 |
| cand-007 的编制人数是多少 | 先查到 job-001，再写出编制人数 2 |
| cand-007 这个人的编制还要招几个人 | job-001 计划 2 人，已录用只有 cand-007，还剩 1。已投递、筛选中、面试中、已淘汰不算已招 |

状态依次是已投递、筛选中、面试中、已录用、已淘汰。已淘汰不和仍在流程中的人比先后。没有列出全部候选人的语句，几次查询的行数不能相加当成总人数。查不到的编号写没查到。

允许的语句：

```
.entity_set with(domain='rms', name='rms.candidate', ids=['cand-001'])
.entity_set with(domain='rms', name='rms.candidate', status='HIRED')
.entity_set with(domain='rms', name='rms.candidate', position='前端工程师')
.entity_set with(domain='rms', name='rms.candidate', opening_id='job-001')
.entity_set with(domain='rms', name='rms.opening', ids=['job-001'])
```

`status` 只能是 `APPLIED`、`SCREENING`、`INTERVIEWING`、`HIRED`、`REJECTED`。

## 配置

复制 `agent/.env.example` 为 `agent/.env`，填上模型网关地址和密钥。可选模型是 `qwen3.8-flash`、`deepseek-v4.1-flash`、`deepseek-v4-flash-0731`、`deepseek-v4-pro-0813`，用 `DATA_AGENT_MODEL` 切换。

数据库只读密码放在 `rms/.env`。Agent 配置里没有 `RMS_READONLY_PASSWORD` 时，启动时从那里读取。

## 运行

在仓库根目录执行。标准错误打印每一轮查询和返回，标准输出是结论。不带问题时，比较 cand-004 和 cand-005 谁在招聘流程里更靠后。

没有 Docker 时，先开一个窗口跑本地替身。它复现开源 UModel 对 `.entity_set` 的拒绝，连接器再按模型生成 SQL，替身用种子数据回答。图查询不经过这个替身。

```sh
connector/.venv/bin/python -m pip install mysql-mimic
connector/.venv/bin/python agent/local_lab.py
```

另一个窗口。默认走 `run`。加上 `--loop graph` 走同一套检查的 LangGraph：

```sh
connector/.venv/bin/python -m data_agent cand-007 这个人的编制还要招几个人
connector/.venv/bin/python -m data_agent --loop graph cand-007 这个人的编制还要招几个人
```

连真实 UModel 和招聘库：

```sh
docker compose --env-file rms/.env -f integration/compose.yaml up --build
connector/.venv/bin/python -m data_agent
```

Windows 把 `bin` 换成 `Scripts`。

## 测试

这组测试不访问模型网关，也不访问数据库。非法查询不会调用存储；合法查询会走到注入的执行函数；编号没查全或后续查询没做完时，不收下文字结论。

```sh
connector/.venv/bin/python -m pip install -e agent
cd agent && ../connector/.venv/bin/python -m pytest && ../connector/.venv/bin/python -m ruff check .
```
