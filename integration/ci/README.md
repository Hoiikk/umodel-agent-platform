# CI 与 CD 的边界

仓库根目录的 GitHub Actions 负责单元测试和集成检查。本目录是本地集成检查的依据。

本地流水线会检查招聘系统测试、连接器测试和静态检查、Data Agent 单元测试、打包、UModel 环境、容器镜像构建、Compose 启动，以及按模型取数的端到端冒烟测试。运行方式：

```sh
./scripts/ci-local.sh
```

设置 `KEEP_STACK=1` 可以在流水线结束后留下 Compose 服务继续运行。

云上交付是另一套骨架，仓库管理员把 `CD_ENABLED` 设上之前保持关闭。镜像发布和部署分别是 `.github/workflows/release.yml` 和 `.github/workflows/deploy.yml`。启用前先看 [`../../deployment/README.md`](../../deployment/README.md)。
