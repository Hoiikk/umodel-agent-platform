# UModel 与招聘系统的本地集成

这个目录负责把下面三部分在本地接到一起：

- `../third_party/UnifiedModel`：钉住版本的上游 UModel 语义运行时；
- `../rms`：招聘管理系统；
- `../connector`：按模型取数的执行层。

这里有 Compose 定义、招聘系统模型包、冒烟测试和本地 CI。业务逻辑留在 `rms/` 和 `connector/`。

## 本地依赖

- 带 Docker Compose v2 的 Docker Desktop；
- UModel 需要 Go 1.22 或更新版本；
- 招聘系统需要 Node.js 和 npm；
- 连接器需要 Python 3.10 或更新版本。

## 安全边界

真实业务系统的账号、生产数据和公网部署配置不要放进这个目录。本地环境只用种子数据和权限最小的服务账号。

## 第一次把环境拉起来

把 `../rms/.env.example` 复制成 `../rms/.env`，填上只在本机使用的密码，然后在本目录执行 `docker compose --env-file ../rms/.env up --build`。这会启动 MySQL、端口 3001 上的招聘系统，以及端口 8080 上的 UModel。接着用上游命令行检查服务，并导入挂载进来的招聘模型包：

```sh
cd ../third_party/UnifiedModel
go run ./cmd/umctl --addr http://127.0.0.1:8080 health
go run ./cmd/umctl --addr http://127.0.0.1:8080 workspace create rms
go run ./cmd/umctl --addr http://127.0.0.1:8080 umodel import rms --path /model-packs/rms
go run ./cmd/umctl --addr http://127.0.0.1:8080 query run rms '.umodel | limit 10'
```

UModel 只能从只读挂载的 `/model-packs` 导入，不要把导入路径指到容器里的其他位置。连接器按设计是单独的标准输入输出 MCP 进程。

## 端到端冒烟测试

服务起来之后执行：

```sh
./scripts/run-smoke.sh
```

这个脚本可以重复跑。它先检查 UModel 是否健康，需要时创建并导入 `rms` 工作区，再经连接器和 MySQL 做一次按模型的候选人查询。它确认只读路径返回一行，并且姓名、电话、邮箱保持打码。Compose 里的 MySQL 只绑定 `127.0.0.1:3308`。连接器通过 `RMS_MYSQL_ENDPOINT` 使用这个地址，模型文件本身仍保留本地开发的默认地址。
