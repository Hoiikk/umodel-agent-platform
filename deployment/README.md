# 云上部署骨架

这个目录是 Docker Compose 的部署目标，使用 `.github/workflows/release.yml` 发布的固定版本镜像。仓库管理员配好受保护的 GitHub Environment 之前，这套流程不会真正部署。

## 预发机器的一次性准备

1. 准备一台 Linux 主机，装好 Docker Engine、Docker Compose v2、`curl`，并准备一个用于 SSH 部署的用户。
2. 在这台主机上创建受保护的部署目录，例如 `/opt/umodel-agent-platform/deployment`。
3. 在主机上把 `.env.example` 复制成 `.env`，把每个值换成足够强的密钥，并且不要提交这个文件。
4. 如果 GHCR 镜像包仍是私有的，第一次部署前先用带 `read:packages` 权限的令牌在主机上登录。

## GitHub Environment 配置

在仓库设置里创建 `staging` 和 `production` 两个 Environment。每个 Environment 添加这些密钥：

- `DEPLOY_HOST` — 服务器主机名或 IP。
- `DEPLOY_USER` — SSH 部署用户。
- `DEPLOY_PATH` — 部署根目录的绝对路径，例如 `/opt/umodel-agent-platform`。
- `DEPLOY_SSH_KEY` — 部署用户的私钥。
- `DEPLOY_KNOWN_HOSTS` — 从 `known_hosts` 取出的那一行服务器主机密钥。

这些密钥和服务器上的 `.env` 都准备好之后，再把仓库变量 `CD_ENABLED` 设为 `true`。配置过程中保持不设：部署任务会被跳过。`production` 需要审批人批准，并且只走发布流程。

## 发布和部署

1. 打一个发布标签，例如 `v0.1.0`，或者手动运行 **Publish release images** 并填上这个版本。输出里包含 `sha-*` 标签。
2. 运行 **Deploy platform**，选择 `staging`，并使用确切的 `sha-*` 标签。
3. 验证通过后，用同一个固定标签部署 `production`，在确认框里输入 `DEPLOY`。如果配了 GitHub Environment 审批，仍然需要批准。

部署流程只上传公开的部署定义和语义模型文件。数据库密码留在服务器的 `deployment/.env` 里。
