<div align="center">

# 幕论红队协同平台

**RedTeam Collaboration Platform** —— 面向红队内部的黑板式协同作战平台

攻击图 · 共享黑板 · 状态机建议 · 数据导入 · 报告生成 · 提权分析

> 玄幕安全团队（Xuanmu Security Team）出品 · 开发：guaidao2

</div>

---

## 简介

幕论红队协同平台把一次红队任务做成**一个独立项目**：成员在共享「黑板」上实时记录目标、服务、漏洞、凭据等发现，系统自动把它们呈现为一张**可手动连线的攻击图**，并按团队进度**只读地给出「下一步建议」**。

> 定位：人记录协同过程，而非自动攻击。攻击图由人连线维护，状态机只建议不执行。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| 🗂️ 多项目隔离 | 一次任务 = 一个项目；成员与权限（owner/member）分级，项目数据互不可见 |
| 🧱 共享黑板 | 手工录入（结构化表单，可按类别）或导入（Nmap/Nessus/JSON） |
| 🕸️ 攻击图 | 力导向自动布局 + 自由拖拽 + **手动连线**标注杀伤链；多人**4s 实时同步** |
| 🧭 状态机建议 | YAML 规则引擎（热加载、前端在线编辑 + **实时语法校验**） |
| ⚙️ 录入表单 | service/vuln/credential/note 等按类别渲染字段，笔记可直接粘贴整段 |
| 📄 报告生成 | 一键 HTML 报告：概览 / 攻击链 / 分类详情 |
| 🚀 提权分析 | 粘贴 Linux 枚举输出，识别 SUID / sudo / Docker 等向量 |
| 🔐 安全 | JWT、成员/管理员授权、登录限速、安全表达式引擎（无 eval）、输入校验 |
| 🤖 MCP Server | 挂载 `/mcp`，平台 API Token 鉴权，外部 Agent 可直接调用平台能力 |

---

## 快速开始

### 环境要求
- Python 3.10+（开发环境已验证 3.11）
- 无需外部数据库/服务；依赖极少，均为常见库

### 安装与启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动（本地开发）
python app.py
# -> 打开 http://localhost:5000
```

默认管理员账号：**admin / admin123**（请在首次使用后于 `config.py` 修改，或页面右上角「设置」修改）。

> 生产部署（对外提供服务）请设置：
> ```bash
> export REDTEAM_JWT_SECRET="$(openssl rand -hex 32)"   # 强随机密钥
> export REDTEAM_ADMIN_PASSWORD="$(openssl rand -base64 18)"  # 覆盖默认 admin 口令（仅内存）
> export REDTEAM_DEBUG=0                                # 关闭 reload/调试
> python app.py
> ```
> 只要 `REDTEAM_JWT_SECRET` 未显式设置，服务一律只监听 `127.0.0.1`（与 DEBUG 无关），
> 避免默认密钥暴露。

---

## 容器化部署（Docker / Docker Compose / Podman）

老服务器无需本机安装 Python 与 `mcp` 等依赖 —— **镜像构建时一次装好**：

```bash
# 构建镜像
docker build -t mulun-redteam:latest .

# 方式一：docker run
docker run -d --name mulun-redteam -p 5000:5000 \
  -e REDTEAM_JWT_SECRET="$(openssl rand -hex 32)" \
  -v "$(pwd)/data:/app/data" mulun-redteam:latest

# 方式二：docker compose
cp .env.example .env      # 填 REDTEAM_JWT_SECRET
docker compose up -d --build

# 方式三：podman（老服务器友好，命令与 docker 一致）
podman build -t mulun-redteam:latest .
podman run -d --name mulun-redteam -p 5000:5000 \
  -e REDTEAM_JWT_SECRET="$(openssl rand -hex 32)" \
  -v "$(pwd)/data:/app/data:Z" mulun-redteam:latest
```

📘 构建 / 手工启动 / Compose / Podman / 数据备份 / HTTPS 反代详见 **[docs/DEPLOY.md](docs/DEPLOY.md)**。

---

---

## 用户与团队协作

- 默认仅一个账户 `admin`（团队通常共享）；在 `config.py` 的 `USERS` 增加即可新增
- 项目 owner 可在仪表盘「成员」管理里添加/移除成员
- 权限：
  - **项目成员**：查看 / 录入 / 连图 / 导入 / 报告
  - **项目 owner**：改 / 删项目、管理成员
  - **平台管理员**（`ADMIN_USERS`，默认 admin）：编辑全局规则

---

## 使用流程

1. 登录 → 新建项目 → 拉成员
2. 添加目标（IP/主机名）→ 可「导入数据」批量灌 Nmap/Nessus/JSON
3. 逐条录入发现：服务、漏洞、凭据、备注（可用结构化表单）
4. 在攻击图上把「漏洞 → 凭据 → 横向」连起来，形成攻击链
5. 点「分析」看状态机建议 → 按 R1-R10 推进
6. 打不动时粘贴枚举输出到「提权分析」找向量
7. 完结后「报告」一键导出 HTML

---

## 技术栈与结构

```
幕论红队协同平台/
├── app.py               # FastAPI 入口（python app.py）
├── config.py            # 用户、密钥、路径、DEBUG（可用环境变量覆盖）
├── core/
│   ├── models.py        # SQLite 数据层（WAL、事务、级联删除）
│   ├── state_machine.py # 规则引擎 + 安全表达式解析器（无 eval）
├── api/
│   ├── authz.py         # 成员/owner/管理员 授权依赖
│   ├── projects.py      # 项目与成员
│   ├── blackboard.py    # 目标 + 黑板条目
│   ├── attack_graph.py  # 攻击图节点与边
│   ├── rules.py         # 规则 CRUD + /validate /meta
│   ├── import_data.py   # Nmap/Nessus/JSON 导入
│   ├── report.py        # 报告
│   ├── privesc.py       # 提权分析
│   └── system.py        # 个人设置/改密
├── modules/
│   ├── data_importer.py        # 解析器（去重、defusedxml）
│   ├── report_generator.py     # HTML 报告
│   └── privilege_analyzer.py   # 提权向量识别
├── rules/*.yaml        # 状态机规则（可热加载）
├── web/                # Jinja2 + 本地化静态资源
│   ├── templates/      # 登录/项目/仪表盘/规则/设置
│   └── static/         # css/js + vendor(vis.js, bootstrap 本地)
├── data/               # platform.db 等运行时数据（不入库）
└── tests/test_e2e.py   # 端到端回归套件
```

**技术选型**
- 后端：FastAPI + SQLite（WAL），JWT 鉴权
- 前端：Jinja2 服务端渲染 + Bootstrap 5 / vis.js（均本地化，无 CDN 依赖）
- 规则：YAML + 白名单表达式引擎（安全、可热加载）

---

## 实时协作

仪表盘每 **4 秒** 轮询攻击图与目标列表：
- 仅当数据有变化（签名 diff）才重绘，视图与选中不丢失
- 节点拖拽位置按项目保存在本地（`localStorage`），刷新保持；「自动排版」一键重新布局

---

## 规则引擎

状态机规则写在 `rules/*.yaml`，支持**前端在线编辑 + 实时语法校验 + 热重载**。

```yaml
- id: R4
  name: 有漏洞未利用
  category: vulnerability
  trigger:
    condition: "has_vuln_unexploited"
  suggestion:
    title: "尝试利用已发现的漏洞"
    reason: "存在尚未标记为已利用的漏洞"
  priority: high
  enabled: true
```

📘 完整编写规范见 **[docs/RULES.md](docs/RULES.md)**（变量表、运算符、枚举、校验 API、内置规则速览）。
设计文档见 [DESIGN.md](DESIGN.md)。

---

## 平台 API Token 与 MCP

平台内置 **MCP Server**（挂载于 `/mcp`），供外部 Agent（如 Claude/GPT）以工具方式直接读写平台：

- Token 在「设置 → 平台 API Token」（仅管理员）查看 / 复制 / 刷新
- **初始随机 Token 永久有效**，只有管理员手动「刷新」才会更换，旧 Token 立即失效
- MCP 请求头：`Authorization: Bearer <token>` 或 `X-API-Key: <token>`

内置工具：
`list_projects` `get_project` `list_targets` `list_entries` `get_attack_graph`
`get_suggestions` `get_report` `analyze_privilege_escalation`
`create_project` `add_target` `add_entry` `add_edge`

> 平台 Token 调用方视作平台管理员；同时管理员（`ADMIN_USERS`）可访问任意项目。

📘 完整接入步骤、客户端配置（通用 Python / Cursor / Cline）与排查见 **[docs/MCP.md](docs/MCP.md)**；
开箱即用示例见 **examples/mcp_client_example.py**：
```bash
python examples/mcp_client_example.py --url http://127.0.0.1:5000/mcp --token "$TOKEN" list_tools
```

---

## 测试

```bash
python tests/test_e2e.py
# => ALL E2E TESTS PASSED
```

覆盖：登录限速、越权 403、owner/成员管理、CRUD、状态回退拒绝、
攻击图连线、规则语法安全、IP 注入、报告/提权 API 等。

---

## 安全说明

- 用户口令按你的选择存于 `config.py`（明文，内部工具）；对外请务必：
  - 用强 `REDTEAM_JWT_SECRET`，并关闭 `DEBUG`
  - 放在 HTTPS 反向代理之后
  - 定期轮换 `admin` 口令（前端「设置」或直接改 config）
- 规则条件走**白名单解析器**，不使用 `eval`，不存在 RCE
- 项目数据按「成员/owner」隔离；攻击图边、目标、条目均有归属校验
- 上传限制 10MB、XML 用 `defusedxml`、输出 HTML 全量转义

---

## Roadmap（建议）

- [x] MCP 接口层（/mcp，平台 Token 鉴权）
- [ ] C/S 客户端（离线录入/扫描结果自动回填）
- [ ] 攻击图布局持久化到服务端、多分支编辑冲突合并
- [ ] 报告导出 PDF/Markdown

---

## 许可与声明

本项目采用 **Apache License 2.0** 开源许可，详见 [LICENSE](LICENSE)。

仅用于**已授权**的渗透测试 / 红队评估 / 教学研究。使用者须自行遵守当地法律与目标授权范围，本项目作者与团队不对任何未授权使用负责。
