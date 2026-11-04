# Data Agent

不使用 LangGraph。模型决定查一个编号、一个状态或一个职位，以及最后怎么写结论。真正的查询交给 `connector`，密码不进模型请求。后面数据变复杂时按 [`PROCESS.md`](PROCESS.md) 一项一项做。

配置在 `agent/.env`。数据库只读密码留在 `rms/.env`，启动时如果 Agent 配置里没有这一项，会从那里读取。

可用模型：`qwen3.8-flash`、`deepseek-v4.1-flash`、`deepseek-v4-flash-0731`、`deepseek-v4-pro-0813`。改 `DATA_AGENT_MODEL` 即可。

## 单元测试

在仓库根目录，使用连接器的虚拟环境：

```sh
connector/.venv/bin/python -m pip install -e agent
cd agent && ../connector/.venv/bin/python -m pytest && ../connector/.venv/bin/python -m ruff check .
```

Windows 把 `bin` 换成 `Scripts`。这组测试不访问模型网关，也不访问数据库。

## 没有 Docker 时

这条招聘查询在开源 UModel 里会被拒绝执行，连接器再按模型生成 SQL。`local_lab.py` 用同样的拒绝，加上种子里的候选人，代替 Docker 里的 UModel 和 MySQL。图查询不会经过这个替身。

先装一次协议库，再开着这个窗口：

```sh
connector/.venv/bin/python -m pip install mysql-mimic
connector/.venv/bin/python agent/local_lab.py
```

另一个窗口再运行下面的 `python -m data_agent`。

## 连真实环境

先启动本地 UModel 和招聘库，再在仓库根目录运行：

```sh
docker compose --env-file rms/.env -f integration/compose.yaml up --build
connector/.venv/bin/python -m data_agent
```

不带参数时，比较 `cand-004` 和 `cand-005`。也可以把问题放在命令后面。终端标准错误会打印每一轮查询和返回；标准输出是最后的结论。
