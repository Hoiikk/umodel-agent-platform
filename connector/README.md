# umodel-assistant-py

开源 UModel 前面的取数执行层。开源服务负责把业务系统建模成对象图，并生成查询计划；本目录按计划访问业务系统，把行交回 Agent。Agent 不编写 SQL，不提交数据库地址或密码，也不在工具参数里声明自己的身份。

审阅所依据的开源版本是 `alibaba/UnifiedModel` 提交 `f065a68c51268c60be941180934462161f89f483`（2026-10-12，v0.6.0）。本目录不重写该仓库的对象图、SPL 和官方 MCP。Go 服务需要单独检出运行，不在这个目录里。

## 和开源 UModel 怎么分工

| 步骤 | 谁来做 |
|---|---|
| 描述实体、字段、存储位置和关联 | 开源 UModel 的模型；本目录用 `model/` 里的 YAML 举例 |
| 保存对象图，编译查询计划 | 开源 Go 服务。本进程每次查询都先问它，只发 `mode=plan` |
| 按计划查询 MySQL、HTTP、PromQL、Elasticsearch、ClickHouse | 本目录。`mode=data` 才真正连接；`mode=plan` 只返回计划 |
| 把自然语言变成 SPL，并调用工具 | Agent。工具名是 `query_spl_execute` |

新业务系统通过增加模型 YAML 接入，不在代码里为单个系统写分支。Go 没启动时本进程直接失败，不会跳过 Go 自己查库。

## 目录结构

```text
umodel-assistant-py/
├── README.md
├── pyproject.toml              可安装包、依赖范围、测试与静态检查配置
├── requirements.lock           已验证开发环境的锁定依赖
├── src/umodel_assistant/
│   ├── mcp_server.py           MCP 入口：query_spl_execute、query_spl_explain、query_spl_examples
│   ├── dispatch.py             查询编排和执行器分发
│   ├── model_pack.py           模型包解析与存储绑定
│   ├── renderers.py            受控、参数化的取数计划生成
│   ├── policy.py               字段和实体访问策略
│   └── executors/              MySQL、HTTP、PromQL、ES、ClickHouse 执行器
├── model/                     电商示例。example 字段不是查询结果
│   ├── entity_set/            commerce.user、commerce.order、commerce.payment
│   ├── event_set/             一行的字段。用户姓名标了 pii.name
│   ├── storage/               订单 MySQL、用户 REST、支付 REST
│   └── link/                  data_link、storage_link、entity_set_link
├── tests/
│   ├── integration/            MCP、模型包、执行器的集成测试
│   └── support/                仅供测试的模拟后端
└── docs/
    ├── 取数执行层说明与生产接入.md
    ├── UModel开源范围与自行建设说明.md
    └── UModel_Go_SDK_补全说明.md
```

## 一次查询怎么走

Agent 调用 `query_spl_execute`。订单示例：

```text
.entity_set with(domain='commerce', name='commerce.order', ids=['U-1001'])
```

1. 本进程请求 Go 生成计划。
2. Go 对这种不带 entity-call 的 `.entity_set` 返回 `requires entity-call`，不给出表名或数据库地址。
3. 本进程读 `model/`：订单记录在 MySQL `commerce.t_order`，查找字段是 `user_id`。`U-1001` 进入参数，不写进 SQL 文本。密码只保存为 `secret://COMMERCE_MYSQL_PASSWORD`。
4. `mode=plan` 到此结束。
5. `mode=data` 从环境变量读密码，用 `aiomysql` 连接 YAML 里的地址。未安装驱动或没有密码则失败。
6. 去掉模型未声明的列，按 `fields_mapping` 把列名改回字段名，再按标签脱敏。用户资料的 `name` 标了 `pii.name` 时，「张三」返回为「张*」。审计日志写到 stderr。

对象图查询（`.umodel`、`.entity`、`.topo`）由 Go 返回行，本进程确认调用方后转发，不连接业务库。PromQL、Elasticsearch、ClickHouse 使用 Go 计划里的地址，该地址必须在 `ALLOWED_HTTP_HOSTS` 中。

另外两个工具：`query_spl_explain` 只把 SPL 转给 Go 的 `/explain`，不在本地取数；`query_spl_examples` 返回示例 SPL。

## 模型里有什么

`model/` 是格式示例，启动时由 Python 直接读取。业务对象查询不依赖把这些 YAML 导入 Go。要在对象图里看到它们，才需要按《取数执行层说明与生产接入》第 4 节导入。`--quickstart` 装入的是开源示例，不是这里的 commerce。

正式接入时保留这几类元素，不要合成一个随意命名的文件：

| 元素 | 内容 |
|---|---|
| `entity_set` | 业务对象，如用户、订单 |
| `event_set` | 一行的字段。需要脱敏的字段设置 `tags.classification` |
| `storage` | 地址、库名、表名、账号。密码只写 `credential_ref: secret://某个名字` |
| `data_link` | 对象对应哪一个数据集 |
| `storage_link` | 字段对应哪一列。一个数据集只能有一条 |
| `entity_set_link` | 对象之间的关系，如用户包含订单。取数不依赖它 |

示例里有三个业务对象。查 `commerce.order` 且 `ids=['U-1001']` 时，条件是 `user_id = U-1001`，因为存储上的 `lookup_field` 是 `user_id`。MySQL 账号名写在 `username`，示例为 `readonly`。查 `commerce.user` 走用户 REST。查 `commerce.payment` 且 `ids=['P-3001']` 走支付 REST：`http://127.0.0.1:8001/api/payments/P-3001`。支付和用户共用这个端口，已在默认白名单里。

## 环境要求

- Python 3.10 及以上。
- 已运行的开源 UModel。默认地址 `http://localhost:8080`，工作区 `demo`。
- 开发安装（含 MySQL smoke test）：`python -m pip install -r requirements.lock -e ".[dev,mysql]"`。
- 真正连接 MySQL：`python -m pip install -e ".[dev,mysql]"`。测试不连接生产库。

常用环境变量。完整说明、导入命令和生产替换步骤见 [取数执行层说明与生产接入](docs/取数执行层说明与生产接入.md)。

| 变量 | 作用 |
|---|---|
| `UMODEL_ADDR` | Go 地址，默认 `http://localhost:8080` |
| `UMODEL_WORKSPACE` | 工作区，默认 `demo`。工具参数留空时用这个值；写成别的值会被拒绝 |
| `UMODEL_AUTH_MODE` | 默认 `deny`。本地开发设为 `dev_header` |
| `UMODEL_DEV_USER`、`UMODEL_DEV_TENANT` | 仅 `dev_header` 使用，从进程环境读取 |
| `COMMERCE_MYSQL_PASSWORD` | 对应模型中的 `secret://COMMERCE_MYSQL_PASSWORD` |
| `RMS_READONLY_PASSWORD` | RMS 模型中只读账号 `umodel_reader` 的密码 |
| `RMS_MYSQL_ENDPOINT` | 覆盖 RMS 模型的本地默认地址，用于 Compose、预发等部署环境，例如 `127.0.0.1:3308` |
| `ALLOWED_HTTP_HOSTS` | HTTP、Prometheus、Elasticsearch、ClickHouse 的 `主机:端口`。默认 `127.0.0.1:8001`。不约束 MySQL |
| `MAX_SQL_LIMIT` | 单条 SQL 最多返回的行数，默认 `1000` |
| `ENABLE_AUDIT_LOG` | 默认开启。设为 `0` 或 `false` 则不写 |

缺配置、未知方言、空壳计划或密钥不存在时返回错误，不返回空列表、假密码或示例行。

## 本地检查

在本目录执行：

```powershell
$env:UMODEL_AUTH_MODE = "dev_header"
$env:UMODEL_DEV_USER = "dev"
$env:UMODEL_DEV_TENANT = "acme"
python -m pytest
python -m umodel_assistant --self-test
```

`--self-test` 只检查订单 SQL 是否把 `U-1001` 放进参数，不连接 Go，也不返回样例行。pytest 里的 MySQL 使用注入的执行函数，HTTP 使用进程内接口。

## 启动

开发身份示例：

```powershell
$env:UMODEL_AUTH_MODE = "dev_header"
$env:UMODEL_DEV_USER = "dev"
$env:UMODEL_DEV_TENANT = "acme"
python -m umodel_assistant
```

进程通过标准输入输出接入 Agent，不监听端口。在 Cursor 或企业 Agent 平台中添加该 MCP 服务后，使用 `query_spl_execute`。

上线前用只读账号对预发库执行一次 `mode=data`，并核对 stderr 里是带占位符的语句和 `secret://` 名称，不出现密码或令牌。

## 说明文档

- [取数执行层说明与生产接入](docs/取数执行层说明与生产接入.md)：现有代码、正式使用步骤、尚未接入的企业能力
- [UModel 开源范围与自行建设说明](docs/UModel开源范围与自行建设说明.md)：哪些能力已经开源，哪些需要自行建设
- [UModel Go SDK 补全说明](docs/UModel_Go_SDK_补全说明.md)：Go SDK 中 `Validate()` 的补全，发生在用 Go 拼模型、提交之前。对应 Go 文件不在本目录

## 这个目录没有做的事

员工登录（OIDC、JWT、mTLS）、Vault、KMS、集中审计、按人授权、限流和高可用都还没接。未接入时调用失败，不返回示例数据。云端控制面、多租户产品和内部前端不在本目录范围内。跨数据源 Join 也不在这里做，关联应先落在数仓或业务服务中。
