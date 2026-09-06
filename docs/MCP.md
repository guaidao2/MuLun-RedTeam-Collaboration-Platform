# MCP 接入指南

幕论红队协同平台内置 **MCP Server**，外部 Agent（Claude / Cursor / Cline / 自研 Agent）
可把平台当“工具箱”直接调用：查项目、看攻击图、读建议、加目标/条目/连线等。

---

## 1. 快速事实

| 项 | 值 |
|----|-----|
| 传输 | MCP **Streamable HTTP** |
| 端点 | `http://<host>:5000/mcp` |
| 鉴权 | 请求头 `Authorization: Bearer <平台Token>` 或 `X-API-Key: <平台Token>` |
| Token 获取 | 登录 → 右上角「设置」→ 平台 API Token（仅管理员）|
| Token 规则 | 首次启动自动生成随机 Token，**永久有效**；仅管理员手动「刷新」后更换，旧 Token 立即失效 |

> 服务用 `python app.py` 启动即已挂载（无需额外进程）。

---

## 2. 内置工具

| 类别 | 工具 |
|------|------|
| 读 | `list_projects` `get_project` `list_targets` `list_entries` |
| 图/建议 | `get_attack_graph` `get_suggestions` |
| 报告/分析 | `get_report` `analyze_privilege_escalation` |
| 写 | `create_project` `add_target` `add_entry` `add_edge` |

调用方视为**平台管理员**（可访问任意项目，管理员即 `ADMIN_USERS`）。

---

## 3. 先自测：Token 门卫

```bash
# 未带 Token -> 401
curl -i http://127.0.0.1:5000/mcp

# 带 Token -> 进入 MCP 协议（200/405 均属正常，说明鉴权已过）
TOKEN=<你的平台Token>
curl -i http://127.0.0.1:5000/mcp -H "Authorization: Bearer $TOKEN"
```

---

## 4. 客户端接入示例

### 4.1 通用 Python（官方 `mcp` 库）

```bash
pip install mcp
python examples/mcp_client_example.py --url http://127.0.0.1:5000/mcp --token "$TOKEN" list_tools
python examples/mcp_client_example.py --url http://127.0.0.1:5000/mcp --token "$TOKEN" call --name list_projects
python examples/mcp_client_example.py --url http://127.0.0.1:5000/mcp --token "$TOKEN" \
    call --name add_entry --arg project_id=1 --arg category=note --arg title=test
```

> 客户端需要能在 HTTP 请求里附加自定义头（`Authorization`/`X-API-Key`）。
> 平台 Token 视为管理员，请勿泄露给不可信调用方。

### 4.2 Cursor / Cline 等支持 HTTP + 自定义头的 MCP 客户端

在对应 MCP 配置中新增（示例 JSON）：

```json
{
  "mcpServers": {
    "redteam": {
      "type": "http",
      "url": "http://127.0.0.1:5000/mcp",
      "headers": {
        "Authorization": "Bearer 你的平台Token"
      },
      "enabled": true
    }
  }
}
```

### 4.3 Claude Desktop / Code（stdio 型客户端）

若客户端只支持 stdio 传输，可让本仓库作为“标准输入/输出 MCP”进程接入 ——
但我们当前提供的是 **HTTP 端点**；请使用你的 MCP 客户端对 **HTTP/SSE（Remote MCP）** 的支持，
或在其配置里以 HTTP `url` + 环境/头部填 Token 的方式接入（各客户端配置语法略有差异，见其官方文档的 Remote MCP 部分）。

---

## 5. 环境变量

| 变量 | 作用 |
|------|------|
| `REDTEAM_JWT_SECRET` | Web 登录 JWT 密钥（对外部署必须设置，否则仅监听 127.0.0.1）|
| `REDTEAM_ADMIN_PASSWORD` | 启动时覆盖默认 admin 口令（仅内存）|
| `REDTEAM_DEBUG` | `1` 开 reload/调试 |

---

## 6. 排查

| 现象 | 原因 |
|------|------|
| 401 `无效的平台 API Token` | Token 缺失/过期（已被刷新）。管理员在「设置」重新查看 |
| 404 | 路径不对：应访问 `/mcp`（Streamable HTTP，走 POST/SSE 子路径）|
| 200/405/400 但非 401 | 鉴权已通过，正在按 MCP 协议握手 —— 属正常 |
| 工具报“项目不存在/无权” | 确认 project_id 存在 |

---

## 7. 安全提示

- 平台 Token 等价管理员（任意项目读写）。仅在可信内网使用，或在 HTTPS + 网络白名单后暴露。
- Token 存放于 `data/api_token.json`（权限尽量 600，已自动忽略入库）。
- 对外部署建议：`REDTEAM_JWT_SECRET` 强随机 + `REDTEAM_ADMIN_PASSWORD` 覆盖 + 反代 HTTPS。
