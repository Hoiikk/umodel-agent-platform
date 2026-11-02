# UModel Agent Platform

把招聘系统、阿里开源的 UnifiedModel，以及给 Agent 用的受控取数连接器，在本地拼成一套可运行的环境。

## 仓库结构

- `rms/` — 招聘管理系统及其 MySQL 结构。
- `connector/` — 按模型取数的只读执行层和 MCP 服务。
- `integration/` — Compose 环境、语义模型包、冒烟测试和本地 CI。
- `third_party/UnifiedModel` — 钉住版本的上游 UModel Git 子模块。产品代码不要改这里。

## 本地启动

```sh
cp rms/.env.example rms/.env
docker compose --env-file rms/.env -f integration/compose.yaml up --build
integration/scripts/run-smoke.sh
```

## 本地完整检查

```sh
integration/scripts/ci-local.sh
```

它会跑招聘系统和连接器的测试、打包、UModel 环境检查、镜像构建，以及 UModel → 连接器 → MySQL 的完整冒烟测试。

## 云上交付

`Publish release images` 只在打 `v*` 标签或手动发布时，把招聘后端和钉住版本的 UModel 镜像推到 GitHub Container Registry。这一步不部署服务器。`Deploy platform` 是面向 `staging` 和 `production` 的 Docker Compose 部署骨架，默认关闭，并且受环境保护。启用前先看 [`deployment/README.md`](deployment/README.md)。
