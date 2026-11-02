# UModel 开源范围与自行建设说明

本文说明 `alibaba/UnifiedModel` 哪些能力已经开源、哪些没有随仓库交付因而需要自行建设，以及本工作区已经补上的部分。取数执行层的实现和生产接入步骤见 [取数执行层说明与生产接入.md](取数执行层说明与生产接入.md)。

审阅对象固定为提交 [`f065a68c51268c60be941180934462161f89f483`](https://github.com/alibaba/UnifiedModel/tree/f065a68c51268c60be941180934462161f89f483)（2026-10-12，v0.6.0）。开源仓库中看不到未公开实现的源码。下文只使用三类结论：

1. 维护者在 README 中写明该能力不属于公开核心。
2. 公开代码或测试明确拒绝该能力，或写明只返回计划、不执行。
3. 设计文档把凭据、工具绑定和执行交给外部 Runtime，并列为不做项。这能说明它不是当前仓库的职责，不能据此断定外部组件一定是某一阿里云闭源产品。

目录中没有某个模块，只作为线索，不单独作为结论。`umodel-assistant` 出现在错误信息中，仓库没有给出它的源码或发布状态。

## 1. 已经开源、应直接使用

| 能力 | 依据 |
|---|---|
| 本地服务、CLI、MCP、OpenAPI、React Web UI、SDK、Docker 与测试 | [README.md 第 33–35 行](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/README.md#L33-L35) |
| Python 模型 SDK | 根 README 及 `sdk/python/`。它是模型类型，不是 Query Service 的 HTTP 客户端 |
| 对象图存储与拓扑查询 | memory、file、Neo4j、Gremlin，见 [overview.md 第 49–57 行](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/docs/zh/architecture/overview.md#L47-L57)。这些 provider 保存 UModel 对象图，不是业务库连接器 |
| 模型、实体、拓扑的统一查询 | Query Service，见 [query-service.md 第 67–82 行](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/docs/zh/guides/query-service.md#L67-L82) |
| 下游查询计划 | `get_logs`、`get_metrics` 按字段映射生成计划。缺的是执行，不是计划编译 |
| 公开 Web UI | 与下文「阿里内部前端包未公开」是两件事。公开 UI 可以用于本地模型管理 |

工作区、UModel、实体写入、查询和 AgentGateway 已在 `internal/` 中装配，见 `internal/bootstrap/app.go`。计划渲染器覆盖 PromQL、Elasticsearch DSL 和 sql-table，渲染过程不连接后端。测试代码中的 fake、Mock 用于单元测试，不是生产数据源。

因此不建议用 Python 重写图存储、SPL、官方 MCP 或公开 SDK。那样不能补上取数缺口。

## 2. 未纳入开源、需要自行建设

### 2.1 README 明确排除

[README.md 第 33–37 行](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/README.md#L33-L37) 与中文 README 一致，下列四项不属于公开核心：

| 能力 | 可以确定的范围 | 不能从本仓库确定的事 |
|---|---|---|
| 云端控制面 | 租户与组织、工作区生命周期、集中策略、发布审批、连接器注册等管理能力未作为本地核心交付。本地 workspace 不是完整控制面 | 内部 API、是否单独发售 |
| 多租户授权 | 开源核心不提供。workspace 只是数据范围，不是登录主体、组织、行列权限和审批 | 商业产品中的具体策略模型 |
| 阿里内部前端包 | 仓库有公开 React UI，内部前端包不随仓库公开 | 内部设计系统或产品工作流 |
| Query Service 之外的领域读 API | 模型、实体、拓扑的公共读路径是 Query Service，见 overview.md 第 73–75 行 | 是否另有未公开的业务读接口 |

### 2.2 真实存储查询未在开源服务中执行

这是取数场景的主要缺口。文档、代码和测试一致：

| 层次 | 位置 | 内容 |
|---|---|---|
| Agent 文档 | [agent-integration.md 第 132–142 行](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/docs/zh/guides/agent-integration.md#L132-L142) | `get_metrics`、`get_logs` 返回计划；开源版只产出计划，由下游执行 |
| Query 文档 | [query-service.md 第 67–82 行](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/docs/zh/guides/query-service.md#L67-L82) | 按字段映射产生计划，不直接查询存储 |
| 服务端 | [internal/query/service.go 第 12–58 行](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/internal/query/service.go#L12-L58) | 只接受 `plan`；其他模式返回 `CodeNotImplemented`，并指向 `umodel-assistant` |
| 测试 | [internal/query/mode_test.go 第 34–43 行](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/internal/query/mode_test.go#L34-L43) | `TestExecuteRejectsDataMode` 锁定该行为 |

`go.mod` 中与图存储相关的依赖是 Neo4j 和 Gremlin。未发现 MySQL、ClickHouse、Elasticsearch、Prometheus 或通用业务 HTTP 的读取驱动。Schema 可以描述这些存储，渲染器可以生成计划文本，服务端不执行它们。

### 2.3 凭据、外部工具与自动生成可执行工具

Skill 设计写明：UModel 返回定义，不解释并执行外部工具，不绑定 provider 凭据；工具、授权、确认和沙箱由 Agent Runtime 负责。Non-Goals 包括 CapabilityService、provider Binding、credentials、人工确认和业务工具实现。见 list-skills 设计第 16–20 行、第 200–207 行，以及 list-knowledge 设计第 23–35 行、第 217–240 行。

[query-service.md 第 80–82 行](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/docs/zh/guides/query-service.md#L80-L82) 写明本阶段不加入 `list_tools`。模型中的允许列表不能据此创建工具绑定或授予权限。

### 2.4 安全治理、检索与联邦查询

[SECURITY.md](https://github.com/alibaba/UnifiedModel/blob/f065a68c51268c60be941180934462161f89f483/SECURITY.md) 要求生产部署另行加入认证、授权、传输安全、限流和审计。OpenAPI 未声明安全方案。`internal/bootstrap/app.go` 对 `Authorization` 头的处理是 CORS 允许列表，不校验身份。扫描未发现服务端的字段脱敏、行级策略或配额服务。

开源侧已有的保护限于本地服务：导入路径限制在 import root 内，MCP 写工具默认关闭，AgentGateway 资源默认只给元数据。SQL 渲染器会拒绝无法表达的过滤，避免生成约束不足的计划。这些不是企业数据访问控制。

其他可核对的缺口：

| 项 | 状态 | 是否由取数执行层承担 |
|---|---|---|
| 跨数据源 Join | 渲染器针对一个库表生成计划，没有联邦执行器。SLS notebook 的 Join 描述是存储元数据，仓库不执行该 notebook | 不承担。关联放在数仓或业务服务 |
| 语义检索 | Search Provider 仅注册 memory；Embedder 只有 Noop | 不承担。若需要，对接企业搜索或向量库 |
| Common Schema Pack | `internal/umodel/import.go` 中的 loader 返回 `CodeNotImplemented` | 不承担。依赖公共模型包时另行提供 loader |
| Ladybug 图存储 | 未带构建标签时为不可用 stub | 不承担。图存储选用 file、Neo4j 或 Gremlin |
| Link 高级数据检查 | `schemas/includes/link.schema.yaml` 中相关检查仍是 TODO | 发布前由模型校验流程处理 |
| Python、Java SDK 校验 | 扫描时 `validate()` 为空；Java Link 的 `getSrc()`、`getDest()` 返回 null | 本次未改。使用这些 SDK 时仍需服务端校验 |
| Go SDK `Validate()` | 生成代码仍是 `return nil` | 不承担。导入模型时由 UModel 服务端校验 |

计划中的 `aggregate`、`storage_*` 由开源执行器回显，供外部执行层使用，开源 planner 本身不消费。

## 3. 本工作区已经补上的部分

`connector` 补的是第 2.2 节的执行层，以及其中能在本进程完成的最小安全控制。已实现的内容包括：向开源服务只请求计划、转发对象图结果、执行 PromQL、Elasticsearch 和 ClickHouse 计划、按模型包生成并执行 MySQL 与 HTTP 查询、参数化只读 SQL、出站白名单、环境变量密钥、按标签脱敏和本进程审计日志。

它没有实现云端控制面，也没有把开发用身份当成企业登录。尚未接入的 OIDC、Vault、KMS、远程审计、按人授权、限流和高可用，列在《取数执行层说明与生产接入》第 5 节。

## 4. 建议的建设边界

1. 继续使用开源 UModel 做建模、对象图和计划编译。
2. 由 `connector` 按计划取数。生产接入时替换身份、密钥和审计，不在 Agent 侧保存 SQL 或密码。
3. 企业控制面、多租户产品、内部前端、跨源 Join、生产级检索，单独建设或对接现有平台。
4. 某项云上能力能否采购或是否有开放接口，向产品方索取说明。不能从公开仓库反推。

向业务或管理层说明时，可以采用下面的范围：

> 开源 UModel 提供语义建模、对象图和查询计划，不执行对业务数据源的查询，也不包含生产级多租户授权。公开仓库没有给出 `umodel-assistant` 的实现。本工作区用 Python 补了受控取数：按模型访问 MySQL、HTTP 以及 Go 已生成的 PromQL、Elasticsearch 和 ClickHouse 计划，并在缺密钥或未授权时失败。员工登录、密钥中心和集中审计仍需接入企业系统后才能对内提供。
