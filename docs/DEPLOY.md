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
# （requirements.txt 已把 mcp 锁在 1.x：mcp 2.x 移除了 FastMCP 会导致启动报错）
```

校验：

```bash
docker image ls | grep mulun-redteam
```

### 1.1 国内下载慢 / 换 pip 镜像源

Dockerfile 默认走**清华 PyPI 镜像**（国内快）。仍慢或在内网时，用 `--build-arg PIP_INDEX_URL` 覆盖：

```bash
# 阿里云
docker build --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple -t mulun-redteam:latest .
# 官方源（海外服务器）
docker build --build-arg PIP_INDEX_URL=https://pypi.org/simple -t mulun-redteam:latest .
```

---

## 2. 手工启动（docker run）

```bash
# 准备 .env（或直接内联环境变量）
cp .env.example .env   # 编辑 REDTEAM_JWT_SECRET 为强随机值

docker run -d --name mulun-redteam \
  -p 5000:5000 \
  -e REDTEAM_JWT_SECRET="$(openssl rand -hex 32)" \
  -e REDTEAM_ADMIN_PASSWORD="改成你记得的强密码" \
  -v "$(pwd)/data:/app/data" \
  --restart unless-stopped \
  mulun-redteam:latest
```

访问 `http://<宿主机IP>:5000`，用 `REDTEAM_ADMIN_PASSWORD` 的值登录。

> ⚠️ `REDTEAM_ADMIN_PASSWORD` 只在**启动时**覆盖 admin 口令（仅内存）。
> - 别用随机值——生成后你记不住就登不进去；用**自己记得的固定强密码**。
> - 每次重启都要带**同一个值**，否则回退默认 `admin123`。
> - 忘记/丢失：`docker inspect mulun-redteam --format '{{range .Config.Env}}{{println .}}{{end}}' | grep REDTEAM_ADMIN_PASSWORD` 可找回明文。

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
  -e REDTEAM_ADMIN_PASSWORD="改成你记得的强密码" \
  -v "$(pwd)/data:/app/data:Z" \
  --restart unless-stopped \
  mulun-redteam:latest
```

> ⚠️ 密码同样**用固定值**（别随机），每次重启保持同一个 `REDTEAM_ADMIN_PASSWORD`（见第 2 节说明）。

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
| `REDTEAM_MCP_ALLOWED_HOSTS` | 否 | MCP DNS-rebinding 白名单，逗号分隔。留空=关闭该层（`/mcp` 已有平台 Token 鉴权；默认关闭可避免「公网 IP Host 被 mcp 返回 421」）|

> ⚠️ **修改登录密码的持久化**：页面「设置 → 修改密码」会把新口令**写入容器内的 `config.py`**（镜像可写层，不在 `data` 卷）。
> `docker rm` / `docker compose up -d --build` 重建后会丢回镜像里的旧值。要跨重建持久，选一种：
> 1. **固定 env 流（推荐）**：密码固定在 `.env`/启动命令的 `REDTEAM_ADMIN_PASSWORD`，重启用同一值；
> 2. **源码流**：改 `config.py` 默认口令后重新 `docker build`（烤进镜像）。

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
| `mcp` 模块报错 | 用的是**旧镜像**：重新 `docker build`（requirements.txt 已锁 `mcp>=1.9,<2`） |
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
