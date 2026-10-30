# UModel Go SDK 补全说明

本文只说明 Go SDK 中 `Validate()` 的补全。开源范围见同目录《UModel 开源范围与自行建设说明》，取数执行层见同目录《取数执行层说明与生产接入》。这些 Go 文件位于另行检出的 UnifiedModel 工作副本，不包含在本目录中。

## 交付摘要

本次从公开仓库 `alibaba/UnifiedModel` 拉取了提交
`f065a68c51268c60be941180934462161f89f483`（2026-10-12），审查了全部 Go
实现、Schema、代码生成器和 SDK。发现的明确、可验证的缺口是：

补全后的源码在另行检出的 UnifiedModel 工作副本中，不在本目录。新增的关键文件是该副本里的
`sdk/go/umodel/generated_validation.go` 和
`sdk/go/umodel/generated_validation_test.go`。

- `sdk/go/umodel/` 中有 **75 个** 自动生成的 `Validate()` 方法；
- 它们此前均为 `TODO` 加 `return nil`，即任何不完整或错误的 SDK 对象都会被
  当作合法对象；
- 服务端仍会校验提交的模型包，但 SDK 调用方无法在构造模型时尽早得到错误。

本次已将这 75 个空实现替换为真实校验调用，并保证以后重新生成 SDK 时不会把
修复覆盖掉。

> 边界：这不是对未开源阿里云控制面的猜测式复刻。公开仓库 README 明确将云端
> 控制面、多租户授权、阿里云内部前端包和 Query Service 之外的领域读取 API
> 列在开源核心之外。本次只补齐可由公开 Schema 和公开 Go SDK 严格推导的行为。

## 已补全的代码

### 1. 生成器：让修复可以持续存在

修改 `tools/generators/schema_go_generator_v2.py` 的
`_generate_validate_method`：生成的每个 `Validate()` 不再返回 `nil`，而是调用
统一的 `validateGenerated(s)`。

这很关键：只改生成后的 `.go` 文件会在下一次 `make expand` 时丢失；修改生成器后，
Schema 增加新对象时也会自动拥有相同的基础校验。

### 2. 通用校验运行时

新增 `sdk/go/umodel/generated_validation.go`，提供 `validateGenerated`：

| 校验能力 | 行为 |
| --- | --- |
| 必填字段 | 从生成代码的 JSON tag 推断：没有 `omitempty` 的字段必须存在；字符串不能是空白，指针、map、slice 不能为 nil。 |
| 嵌套对象 | 递归检查必填的 `schema`、`metadata`、`spec` 以及其内部必填对象。错误带路径，例如 `spec.database is required`。 |
| 对象类型 | 对带 `Kind` 和 `GetKind()` 的核心对象，验证 `kind` 与 Schema 对应的固定类型相等，防止将 MySQL 对象伪装成其他类型。 |
| 集合 | 递归检查 slice、array、map 中的嵌套模型对象。 |
| 循环保护 | 记录已经访问的指针，避免未来含引用的对象模型导致无限递归。 |

该实现特意不尝试在 SDK 中重写完整 JSON Schema 引擎。枚举、正则、跨字段约束、
默认值推导等仍以服务端的 Schema 校验为准；SDK 先拦截最常见、最容易导致无效提交的
结构错误。这避免了两个校验器随版本漂移而产生不一致。

### 3. 覆盖的生成对象

本次修复已覆盖 75 个生成类型的 `Validate()`，包括：

- 数据集：`entity_set`、`metric_set`、`log_set`、`trace_set`、`event_set`、
  `profile_set`、`runbook_set`、`explorer`、`entity_source`；
- 存储：MySQL、ClickHouse、Prometheus、VictoriaMetrics、Elasticsearch、SLS 和
  Aliyun Prometheus 等；
- 关系：`data_link`、`storage_link`、`entity_set_link`、`entity_source_link`、
  `explorer_link`、`runbook_link`；
- 共享模型：`Metadata`、`Schema`、字段定义、工具、技能、Runbook 等。

`rg 'TODO: 实现验证逻辑' sdk/go/umodel` 的结果已从 75 处降为 0。

### 4. 新增回归测试

新增 `sdk/go/umodel/generated_validation_test.go`，覆盖：

1. MySQL 存储缺少嵌套必填字段 `spec.database` 时返回带路径的错误；
2. `kind: postgres` 被用于 `MysqlV100` 时被拒绝；
3. 一个满足公开 Schema 最小必填字段的 MySQL 对象可以通过。

## 验证结果

已执行以下操作：

```text
python3 tools/generators/schema_go_generator_v2.py
go fmt ./...
go test ./umodel
git diff --check
```

结果：

- 代码生成成功，75 个 `Validate()` 均生成调用；
- `go test ./umodel` 通过；
- `git diff --check` 通过（无空白错误）。

尝试运行 `go test ./...` 时，`service` 包在当前受限 macOS 沙盒中被系统动态链接器
中止，错误为 `dyld: missing LC_UUID load command`。这是测试二进制的环境加载问题，
不是本次校验代码的编译或断言失败；`umodel` 包测试已独立成功。建议在标准本机 Go
工具链或 CI 中再运行 `cd sdk/go && go test ./...`。

## 对业务 Agent 的接入建议

目标不应是让 Agent 直接理解每个业务系统的表、API、权限和字段，而应将职责
拆为四层：

```text
业务系统 / SaaS / 数据库 / 可观测平台
              ↓  适配器：只负责鉴权、取数、参数绑定
UModel 模型包：实体、字段语义、关系、数据位置、访问约束
              ↓  查询计划：只读、限额、时间范围、脱敏标签
Agent：发现语义 → 请求计划 → 执行已批准的适配器 → 基于结果回答
```

第一期建议优先实现一个最小闭环：

1. 为一个业务域定义 `customer`、`order`、`service` 等 EntitySet；
2. 用 Storage 模型记录数据源位置，但凭据只写 `credential_ref`，绝不写明文；
3. 用 Link 把订单、客户、服务以及日志/指标关联起来；
4. 给 Agent 暴露“发现模型”和“执行已校验查询计划”两个工具，不给自由 SQL；
5. 在执行层强制只读、最大行数、时间范围、字段级脱敏和审计 Trace；
6. 将执行计划、耗时、结果行数、拒绝原因写回 AgentLoop 或你们自己的观测链路，形成
   评估与优化闭环。

这里的关键安全边界是：**UModel 负责语义和计划，连接器负责执行；Agent 不持有数据库
凭据，也不直接拼接跨系统查询。**

## 仍未实现、需要业务决策的部分

以下项目不应由代码生成器或 AI 在没有业务信息时擅自补上：

| 项目 | 需要的业务输入 |
| --- | --- |
| 真实系统连接器 | 各系统的只读 API/数据库端点、身份认证方式、网络边界与限流规则。 |
| 实体语义 | 业务域、主键、字段定义、跨系统 ID 映射和数据新鲜度要求。 |
| 权限策略 | 谁可查询何种实体/字段；PII、财务数据、租户隔离的规则。 |
| 计划执行器 | SQL/API 模板白名单、参数绑定、查询成本上限、超时与重试策略。 |
| 云端能力 | 多租户控制面、组织级授权、托管 UI 与阿里云私有读 API 不属于公开仓库能力。 |

## 上游事实与参考

- UModel 公开仓库：<https://github.com/alibaba/UnifiedModel>
- UModel 架构说明：模型包定义对象词汇；EntityStore 写运行时实体和拓扑；Query Service
  提供统一读取；AgentGateway/MCP 向 Agent 暴露发现与安全工具。
- AgentLoop 官方文档：<https://help.aliyun.com/zh/agentloop/>。其定位是面向企业 Agent
  的观测、审计、评估、实验和持续优化平台，可作为上述执行审计和优化闭环的承载点。
