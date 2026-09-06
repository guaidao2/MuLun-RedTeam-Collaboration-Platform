# 容器化部署指南（Docker / Docker Compose / Podman）

本平台是纯 Python 项目，官方 `python app.py` 即可跑。
用容器化的好处：**老服务器不用在本机装 `mcp` 等 Python 依赖**——镜像构建时一次装好，
拿到镜像即可运行。数据通过卷持久化在宿主机。

---

## 0. 目录结构（容器相关）

```
├── Dockerfile             # 镜像构建（pip 安装全部依赖，含 mcp）
├── .dockerignore          # 构建上下文排除（data/.git/幕论神图等）
├── docker-compose.yml     # 一键编排
├── .env.example           # 复制为 .env 填写密钥
└── docs/DEPLOY.md         # 本文档
```

---

## 1. 构建镜像

```bash
# 在项目根目录执行
docker build -t mulun-redteam:latest .
# 老服务器无 mcp 依赖也没关系——全部在镜像内安装
```

校验：

```bash
docker image ls | grep mulun-redteam
```

---

## 2. 手工启动（docker run）

```bash
# 准备 .env（或直接内联环境变量）
cp .env.example .env   # 编辑 REDTEAM_JWT_SECRET 为强随机值

docker run -d --name mulun-redteam \
  -p 5000:5000 \
  -e REDTEAM_JWT_SECRET="$(openssl rand -hex 32)" \
  -e REDTEAM_ADMIN_PASSWORD="$(openssl rand -base64 18)" \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  mulun-redteam:latest
```

访问 `http://<宿主机IP>:5000`。

> 未设 `REDTEAM_JWT_SECRET` 时，镜像内服务只监听 `127.0.0.1`（安全护栏）。
> 对外/跨主机访问必须设置该变量。

常用命令：

```bash
docker logs -f mulun-redteam     # 看日志
docker exec -it mulun-redteam sh # 进容器排查
docker restart mulun-redteam
docker rm -f mulun-redteam
```

---

## 3. Docker Compose 启动

```bash
cp .env.example .env      # 编辑密钥
docker compose up -d --build     # 构建并后台启动
docker compose ps                # 状态
docker compose logs -f redteam
docker compose down              # 停止（保留数据卷）
docker compose down -v           # 停止并清数据卷（慎用，会删库）
```

更新到新代码后重建：

```bash
docker compose up -d --build
```

---

## 4. Podman 启动（无守护进程，老服务器友好）

Podman CLI 与 docker 兼容，命令几乎一致：

```bash
# 构建
podman build -t mulun-redteam:latest .

# 手工启动
podman run -d --name mulun-redteam \
  -p 5000:5000 \
  -e REDTEAM_JWT_SECRET="$(openssl rand -hex 32)" \
  -e REDTEAM_ADMIN_PASSWORD="$(openssl rand -base64 18)" \
  -v "$(pwd)/data:/app/data:Z" \
  --restart unless-stopped \
  mulun-redteam:latest
```

> `:Z` 用于开启 SELinux 的容器卷重标（RHEL/CentOS/Fedora 常见）。

日志/停止：

```bash
podman logs -f mulun-redteam
podman rm -f mulun-redteam
```

### 4.1 podman-compose（可选）

```bash
pip install podman-compose   # 或 dnf/apt 安装
podman-compose up -d --build
```

### 4.2 rootless 提示

rootless Podman 下，把 `data/` 目录属主调整为当前用户或使用 podman volume：

```bash
podman volume create mulun-data
podman run -d --name mulun-redteam \
  -p 5000:5000 \
  -e REDTEAM_JWT_SECRET="$(openssl rand -hex 32)" \
  -v mulun-data:/app/data \
  mulun-redteam:latest
```

---

## 5. 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `REDTEAM_JWT_SECRET` | 对外部署必填 | JWT 密钥；未设置 → 容器内只监听 127.0.0.1 |
| `REDTEAM_ADMIN_PASSWORD` | 建议 | 覆盖默认 admin 口令（仅内存，不改源码）|
| `REDTEAM_DEBUG` | 否 | `1` 开 reload（调试），生产保持 `0` |

---

## 6. 数据持久化与备份

- SQLite 库 / 上传 / 报告 / API Token 都在 `/app/data`（挂载宿主机 `./data` 或命名卷）
- 备份：

```bash
# docker
docker cp mulun-redteam:/app/data/platform.db ./backup_$(date +%F).db
# podman
podman cp mulun-redteam:/app/data/platform.db ./backup_$(date +%F).db
```

---

## 7. 常见问题

| 现象 | 处理 |
|------|------|
| 容器内访问不到、curl 连接被拒 | 未设置 `REDTEAM_JWT_SECRET` → 已在容器内只监听回环；设置后重建 |
| `mcp` 模块报错 | 用的是**旧镜像**：重新 `docker build`（Dockerfile 会装 mcp） |
| compose 报 `REDTEAM_JWT_SECRET` 为空 | 复制 `.env.example` 为 `.env` 并填写 |
| 数据不持久 | 确认挂载了 `-v ./data:/app/data` 或命名卷 |
| rootless podman 写权限 | 见 4.2 用命名卷 |

---

## 8. 反向代理（HTTPS，推荐）

Nginx 示例（把 `example.com` 换成你的域名）：

```nginx
server {
  listen 443 ssl;
  server_name example.com;
  # ... ssl_certificate 配置 ...

  location / {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  location /mcp {           # MCP 走同一服务
    proxy_pass http://127.0.0.1:5000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }
}
```
