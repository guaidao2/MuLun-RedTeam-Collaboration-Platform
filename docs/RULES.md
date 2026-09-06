# 状态机规则开发文档（YAML）

幕论红队协同平台的「下一步建议」由 `rules/` 目录下的 **YAML 规则文件** 驱动。
规则引擎会读取当前项目黑板状态，逐条匹配规则，命中即生成一条「建议」——建议只读、不自动执行，最终由成员决定。

---

## 1. 目录与加载

```
rules/
├── service_rules.yaml        # 服务/端口相关
├── vulnerability_rules.yaml  # 漏洞相关
├── credential_rules.yaml     # 凭据相关
├── lateral_rules.yaml        # 横向/域相关
└── general_rules.yaml        # 提权、报告等通用
```

- 引擎启动时加载 `rules/*.yaml`（`yaml` 或 `yml` 后缀均可）
- **热加载**：修改文件后无需重启，可在「规则」页点「重载」，或调用 `POST /api/rules/reload`
- 文件被清空时**不会被删除**（防误删内置规则）；`rules/custom_rules.yaml` 由前端创建的规则生成，不入库

---

## 2. 单条规则结构

```yaml
- id: R4                      # 唯一标识，建议 R1/R2…；自定义用字母数字
  name: 有漏洞未利用            # 规则名（界面展示）
  category: vulnerability      # 见 3.1
  trigger:                     # 触发条件
    condition: "has_vuln_unexploited"   # 布尔表达式，见 4
  suggestion:                  # 命中后产生的建议
    title: "尝试利用已发现的漏洞"       # 建议标题
    reason: "存在尚未标记为已利用的漏洞" # 建议理由
    suggested_tool: "sqlmap ..."       # 可选：推荐命令/工具
  priority: high               # high / medium / low，见 3.2
  enabled: true                # false 则临时停用
```

> 引擎会忽略缺失或非法的字段；`trigger.condition` 为空则该条不参与匹配。

---

## 3. 枚举取值

### 3.1 category
| 值 | 含义 |
|----|------|
| `service` | 服务/端口相关建议 |
| `vulnerability` | 漏洞相关 |
| `credential` | 凭据相关 |
| `lateral` | 横向移动 / 域 |
| `general` | 通用（提权、报告） |

### 3.2 priority
`high`（会排最前） / `medium` / `low`。

> 以上取值在**前后端都会校验**，非法值会被拒绝（HTTP 400）。

---

## 4. 触发条件表达式（condition）

**不使用 `eval`**：由白名单解析器 `SafeConditionEvaluator` 求值，杜绝代码注入。
输入长度 ≤ 1000 字符、括号 ≤ 50 层、token ≤ 200、仅 ASCII 数字。

### 4.1 语法
支持：`and`、`or`、`not`、括号 `( )`、比较 `== != > < >= <=`、整数与布尔字面量。
例：

```text
has_target and service_count == 0
web_port_count > 0 and vuln_count == 0
has_exploited and not has_task
cred_count > 0 and target_count > 1
vuln_unexploited_count >= 1 and vuln_unexploited_count <= 5
has_report_ready
```

### 4.2 可用变量（白名单）

| 变量 | 类型 | 说明 |
|------|------|------|
| `target_count` | int | 目标数量 |
| `has_target` | bool | 是否有目标 |
| `entry_count` | int | 黑板条目总数 |
| `has_entries` | bool | 是否有任何条目 |
| `service_count` | int | 服务条目数 |
| `has_service` | bool | 是否存在服务 |
| `vuln_count` | int | 漏洞条目数 |
| `has_vuln` | bool | 是否存在漏洞 |
| `vuln_unexploited_count` | int | 未标记「已利用」的漏洞数 |
| `has_vuln_unexploited` | bool | 是否存在未利用漏洞 |
| `cred_count` | int | 凭据条目数 |
| `has_credential` | bool | 是否存在凭据 |
| `cred_new_count` | int | 状态为 `new` 的凭据数 |
| `has_cred_new` | bool | 是否存在待验证凭据 |
| `has_task` | bool | 是否有任务条目 |
| `has_note` | bool | 是否有备注条目 |
| `web_port_count` | int | Web 端口数量 |
| `smb_port_count` | int | SMB/445 端口数量 |
| `exploited_count` | int | 已利用条目数 |
| `has_exploited` | bool | 是否存在已利用条目 |
| `domain_entry_count` | int | 域相关信息条目数 |
| `has_report_ready` | bool | 是否已有可利用成果（可出报告） |

> 状态感知：`vuln_unexploited` / `cred_new` / `exploited` 等由**条目的 status** 推导（`new/confirmed/exploited/fixed`），让建议更精确。

### 4.3 常见错误
- 用了白名单外的标识符（如 `os.path`、`__import__`）→ 直接 `ValueError`，保存被拒
- 比较了不存在的变量 → 同上
- 大小写：关键字 `and/or/not` 小写

---

## 5. 前端编写与校验

「规则」页（管理员可见）提供：

- **实时语法校验**：在触发条件输入框输入时（防抖 300ms）自动调用
  `POST /api/rules/validate`，绿色 `✓ 语法正确` / 红色错误提示
- **保存前拦截**：`saveRule()` 先校验，不过则拒绝提交
- **帮助面板**：「[+] 查看可用变量与运算符」→ 拉取
  `GET /api/rules/meta` 渲染变量/运算符列表与示例
- 支持：增删改、启用/禁用（`enabled`）、热重载按钮

相关 API：
| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/rules` | 列出全部规则 |
| POST | `/api/rules` | 新增（admin） |
| PUT | `/api/rules/{id}` | 更新（admin） |
| DELETE | `/api/rules/{id}` | 删除（admin） |
| PATCH | `/api/rules/{id}/toggle` | 启用/禁用（admin） |
| POST | `/api/rules/reload` | 热重载（admin） |
| POST | `/api/rules/validate` | 条件语法校验 |
| GET | `/api/rules/meta` | 变量/运算符/枚举元信息 |

---

## 6. 内置规则速览（rules/*.yaml）

| id | 名称 | 触发条件 | 优先级 |
|----|------|----------|--------|
| R1 | 未识别服务 | `has_target and service_count == 0` | high |
| R2 | 未做目录扫描 | `web_port_count > 0 and vuln_count == 0` | high |
| R3 | 未做漏洞扫描 | `web_port_count > 0 and vuln_count == 0` | medium |
| R4 | 有漏洞未利用 | `has_vuln_unexploited` | high |
| R5 | 有凭据未验证 | `has_cred_new` | high |
| R6 | 有凭据可尝试横向 | `cred_count > 0 and target_count > 1` | medium |
| R7 | SMB未测试 | `smb_port_count > 0 and entry_count >= 0` | high |
| R8 | 提权未尝试 | `has_exploited and not has_task` | medium |
| R9 | 域环境未深挖 | `domain_entry_count > 0` | medium |
| R10 | 未生成报告 | `has_report_ready` | low |

---

## 7. 输出与展示

`GET /api/projects/{id}/suggestions` 返回：

```json
{
  "success": true,
  "data": [
    {"rule_id":"R4","name":"有漏洞未利用","priority":"high",
     "title":"尝试利用已发现的漏洞","reason":"…","suggested_tool":"…"}
  ],
  "summary": {"total": 1, "high": 1, "medium": 0, "low": 0}
}
```

仪表盘「分析」按钮加载并按优先级排序展示（含规则号与推荐命令）。
