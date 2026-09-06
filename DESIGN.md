# 幕论红队协同平台 — 设计文档

> 版本: v0.1-draft  
> 日期: 2025-06-24  
> 状态: 待审阅

---

## 设计原则

1. **专业严肃** — 前端不使用任何表情包/emoji，使用纯文字 + 色块区分类型。  
   节点标签支持中英文切换，用户在界面上直接选择，无需重启。

2. **一键启动** — `python app.py` 即可运行，内部使用 uvicorn。

3. **手动为主** — 攻击图由人维护，状态机只给建议不自动执行。

---

## 1. 项目定位

一个面向红队内部的**协同作战平台**，核心解决的问题是：

> 多人同时对同一目标渗透时，发现散落在每个人脑子里/聊天记录里，  
> 没有统一视图看到"打到哪了"和"下一步该打什么"。

**不是**自动化的渗透平台，**不是** AI Agent 平台，  
而是**人记录协同过程**的共享黑板 + 攻击图 + 状态机建议。

---

## 2. 核心概念

### 2.1 项目 (Project)

一次红队任务 = 一个项目。项目之间完全隔离。

```
平台
├── 项目A: "XX银行渗透测试"
├── 项目B: "XX公司红队评估"
└── 项目C: "CTF训练-内网"
```

### 2.2 黑板 (Blackboard)

每个项目下有一个黑板，是所有发现的统一存储。  
数据来源两种：**手工录入** + **文件导入**（Nmap/Nessus/BloodHound等）。

黑板上的每条记录是一个 **BlackboardEntry**，包含：

| 字段 | 说明 |
|------|------|
| author | 谁发现的 |
| category | 类型：asset / service / vulnerability / credential / task / note |
| target_ip | 关联哪个目标 |
| content_json | 具体内容（不同 category 结构不同）|
| status | new / confirmed / exploited / fixed |
| created_at | 发现时间 |

### 2.3 攻击图 (Attack Graph)

**人手动维护**的有向图，从黑板数据手动或半自动构建。

布局方向：**从左到右**，按杀伤链阶段分层：

```
[资产发现] → [服务识别] → [漏洞发现] → [凭据获取] → [横向移动] → [目标达成]
```

**不是**以原点为中心扩散的力导向图，**是**分层流式布局。

### 2.4 状态机 (State Machine)

**只读引擎**，分析当前黑板状态，给出下一步作战建议。  
不修改黑板，不自动执行，人决定做不做。

---

## 3. 技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| 后端 | **FastAPI** | 原生异步、WebSocket、自动OpenAPI文档 |
| 数据库 | **SQLite** | 一键启动，单文件，足够用 |
| 模板 | **Jinja2** | 服务端渲染，零构建步骤 |
| 前端交互 | **HTMX + Alpine.js** | 轻量交互，不用写SPA |
| 攻击图 | **vis.js** | 原生支持层级布局(LR)、节点卡片、拖拽 |
| 认证 | **JWT** | 最简登录，后续可扩展Token鉴权 |
| 启动 | **python app.py** | `python app.py`，内部使用 uvicorn 启动，一条命令搞定 |

---

## 4. 项目结构

```
幕论红队协同平台/
│
├── rules/                      # 状态机规则（YAML）
│   ├── service_rules.yaml
│   ├── vulnerability_rules.yaml
│   ├── credential_rules.yaml
│   ├── lateral_rules.yaml
│   └── general_rules.yaml
│
├── core/                       # 核心引擎
│   ├── models.py               # 所有数据模型（SQLAlchemy）
│   ├── blackboard.py           # 黑板 CRUD 逻辑
│   ├── attack_graph.py         # 攻击图数据操作
│   └── state_machine.py        # 状态机建议引擎
│
├── modules/                    # 从幕论神图复用/移植的分析模块
│   ├── data_importer.py        # 数据导入器（Nmap/Nessus/JSON/CSV）
│   ├── privilege_analyzer.py   # Linux提权分析（移植自幕论神图）
│   └── report_generator.py     # 报告生成（移植自幕论神图）
│
├── api/                        # FastAPI 路由
│   ├── __init__.py
│   ├── auth.py                 # 登录/JWT
│   ├── projects.py             # 项目 CRUD
│   ├── blackboard.py           # 黑板条目 CRUD
│   ├── attack_graph.py         # 攻击图读写
│   ├── import_data.py          # 文件导入接口
│   └── suggestions.py          # 状态机建议接口
│
├── web/                        # Jinja2 页面
│   ├── templates/
│   │   ├── base.html           # 基础布局模板
│   │   ├── login.html          # 登录页
│   │   ├── projects.html       # 项目列表
│   │   ├── dashboard.html      # 项目主页（图+黑板+建议 三栏）
│   │   └── components/         # 可复用模板片段
│   │       ├── graph_panel.html    # 攻击图面板
│   │       ├── detail_panel.html   # 右侧详情面板
│   │       ├── entry_list.html     # 黑板条目列表
│   │       └── suggestion_bar.html # 状态机建议栏
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           ├── graph.js        # vis.js 攻击图渲染+交互
│           └── app.js          # 全局交互逻辑
│
├── data/                       # 运行时数据
│   ├── platform.db             # SQLite 数据库
│   └── uploads/                # 上传的扫描文件
│
├── tests/                      # 测试
│   ├── test_blackboard.py
│   ├── test_state_machine.py
│   └── test_importers.py
│
├── app.py                      # FastAPI 入口，python app.py 启动
├── config.py                   # 配置
├── requirements.txt
├── DESIGN.md                   # 本文档
└── README.md
```

---

## 5. 数据库设计

### 5.1 用户配置 (config.py)

用户账号密码直接写在 `config.py` 里，不存数据库。  
好处：忘了密码直接改文件，不用进数据库，不用跑 SQL。

```python
# config.py

# 用户列表（用户名: 密码明文，内部工具不用搞哈希那套）
USERS = {
    "admin": "admin123",
    "xiaowang": "wang123",
    "laoli": "li123",
}
```

> 后续如果需要注册功能，再考虑数据库存储。当前阶段固定用户列表足够。

### 5.2 项目表 (projects)

```sql
CREATE TABLE projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'active',     -- active / completed / archived
    owner       TEXT NOT NULL,             -- 创建者用户名，对应 config.py USERS
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.3 项目成员表 (project_members)

```sql
CREATE TABLE project_members (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    username    TEXT NOT NULL,               -- 直接存用户名字符串，对应 config.py USERS
    joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, username),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

> 所有成员权限平等（内部团队，无RBAC）。

### 5.4 目标表 (targets)

```sql
CREATE TABLE targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    ip          TEXT NOT NULL,
    hostname    TEXT,
    os          TEXT,
    description TEXT,
    tags        TEXT,                        -- JSON数组，如 ["核心业务","域控"]
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, ip),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

### 5.5 黑板条目表 (blackboard_entries)

核心表，所有发现统一存储。

```sql
CREATE TABLE blackboard_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    author      TEXT NOT NULL,              -- 录入者用户名，对应 config.py USERS
    category    TEXT NOT NULL,               -- asset / service / vulnerability / credential / task / note
    target_id   INTEGER,                    -- 关联目标（可为空，如全局备注）
    status      TEXT DEFAULT 'new',         -- new / confirmed / exploited / fixed
    title       TEXT NOT NULL,              -- 简短标题（显示在图节点上）
    content     TEXT NOT NULL,              -- JSON，详细内容
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (target_id) REFERENCES targets(id)
);
```

**content_json 按 category 的结构定义：**

```jsonc
// category = "service"
{
    "port": 80,
    "protocol": "tcp",
    "service": "IIS",
    "version": "10.0",
    "banner": "Microsoft IIS/10.0"
}

// category = "vulnerability"
{
    "name": "SQL Injection",
    "severity": "high",        -- critical / high / medium / low / info
    "cve_id": "CVE-2024-xxxx",  // 可选
    "port": 80,
    "description": "Login page vulnerable to SQL injection",
    "evidence": "Payload: ' OR 1=1--",
    "cvss": 8.5               // 可选
}

// category = "credential"
{
    "protocol": "MSSQL",
    "username": "sa",
    "password": "P@ssw0rd",    // 或 hash
    "ntlm_hash": "...",        // 可选
    "source": "SQL注入获取",
    "port": 1433
}

// category = "asset"
{
    "ip_range": "192.168.1.0/24",
    "note": "内网业务段"
}

// category = "task"
{
    "title": "测试445端口SMB匿名",
    "status": "todo",          -- todo / doing / done
    "assignee": "小王"         // 可选
}

// category = "note"
{
    "content": "从SQL注入拿到了sa，但是xp_cmdshell被禁了，需要想别的办法提权"
}
```

### 5.6 攻击图边表 (attack_edges)

```sql
CREATE TABLE attack_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id      INTEGER NOT NULL,
    from_entry_id   INTEGER NOT NULL,        -- 从哪个黑板条目
    to_entry_id     INTEGER NOT NULL,        -- 到哪个黑板条目
    label           TEXT,                    -- 边上的文字，如 "利用" "跳转" "凭据"
    created_by      TEXT NOT NULL,           -- 创建者用户名
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (from_entry_id) REFERENCES blackboard_entries(id),
    FOREIGN KEY (to_entry_id) REFERENCES blackboard_entries(id)
);
```

> 攻击图 = 黑板条目(节点) + attack_edges(边)，人手动连线。

---

## 6. API 设计

### 6.1 认证

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/auth/login` | 登录，返回 JWT |

> 无注册接口，用户在 `config.py` 的 `USERS` 字典里直接加。  
> 修改密码也是改 `config.py`，改完重启即生效。

### 6.2 项目

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/projects` | 我参与的项目列表 |
| POST | `/api/projects` | 创建项目 |
| GET | `/api/projects/{id}` | 项目详情 |
| PUT | `/api/projects/{id}` | 更新项目 |
| DELETE | `/api/projects/{id}` | 删除项目 |
| POST | `/api/projects/{id}/join` | 加入项目（输入项目码）|

### 6.3 目标

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/projects/{id}/targets` | 项目下的所有目标 |
| POST | `/api/projects/{id}/targets` | 添加目标 |
| PUT | `/api/projects/{id}/targets/{tid}` | 更新目标 |
| DELETE | `/api/projects/{id}/targets/{tid}` | 删除目标 |

### 6.4 黑板条目

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/projects/{id}/entries` | 条目列表（支持按category/target/status筛选）|
| POST | `/api/projects/{id}/entries` | 新增条目（手工录入）|
| GET | `/api/projects/{id}/entries/{eid}` | 条目详情 |
| PUT | `/api/projects/{id}/entries/{eid}` | 更新条目 |
| DELETE | `/api/projects/{id}/entries/{eid}` | 删除条目 |
| PATCH | `/api/projects/{id}/entries/{eid}/status` | 更新状态 (new→confirmed→exploited→fixed) |

### 6.5 攻击图

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/projects/{id}/graph` | 获取图数据（所有节点+边）|
| POST | `/api/projects/{id}/graph/edges` | 添加边（人手动连线）|
| DELETE | `/api/projects/{id}/graph/edges/{eid}` | 删除边 |

### 6.6 数据导入

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/projects/{id}/import/nmap` | 上传 Nmap XML → 解析 → 写入黑板 |
| POST | `/api/projects/{id}/import/nessus` | 上传 Nessus 报告 |
| POST | `/api/projects/{id}/import/bloodhound` | 上传 BloodHound JSON |
| POST | `/api/projects/{id}/import/json` | 通用 JSON 导入 |

### 6.7 状态机建议

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/projects/{id}/suggestions` | 获取下一步作战建议（只读）|

### 6.8 系统

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/me` | 当前用户信息 |
| PUT | `/api/me/password` | 修改当前用户密码（写入 config.py）|

### 6.9 规则管理

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/rules` | 获取所有规则 |
| POST | `/api/rules` | 新增规则 |
| PUT | `/api/rules/{id}` | 更新规则 |
| DELETE | `/api/rules/{id}` | 删除规则 |
| PATCH | `/api/rules/{id}/toggle` | 启用/禁用规则 |
| POST | `/api/rules/reload` | 手动触发规则热重载 |

---

## 7. 攻击图设计

### 7.1 节点类型与样式

每个黑板条目在图上是一个节点。节点内容 = 条目的 title + 状态标记。

**设计风格：无表情包/emoji，专业严肃，使用纯文字 + 色块区分。**

| category | 英文标签 | 中文标签 | 默认颜色 | 辅助色 |
|----------|---------|---------|---------|--------|
| asset | ASSET | 资产 | #3498db (蓝) | 浅蓝底 |
| service | SERVICE | 服务 | #9b59b6 (紫) | 浅紫底 |
| vulnerability | VULN | 漏洞 | #e74c3c (红) | 浅红底 |
| credential | CRED | 凭据 | #f39c12 (黄) | 浅黄底 |
| task | TASK | 任务 | #95a5a6 (灰) | 浅灰底 |
| note | NOTE | 备注 | #1abc9c (青) | 浅青底 |

> 标签语言支持前端实时切换（中/英），用户点击界面语言按钮即可切换，无需重启服务。

**状态叠加效果：**

| status | 视觉 |
|--------|------|
| new | 节点右上角显示 "NEW" 标签 |
| confirmed | 无特殊标记 |
| exploited | 节点边框加粗 + 高亮 |
| fixed | 节点变灰 + 删除线 |

### 7.2 层级布局 (Left → Right)

vis.js 配置：

```javascript
{
    layout: {
        hierarchical: {
            direction: "LR",          // 从左到右
            sortMethod: "directed",   // 按有向边排序
            levelSeparation: 200,     // 层间距
            nodeSpacing: 150          // 同层节点间距
        }
    }
}
```

**层级自动分配逻辑：**

```
Level 0 (最左):  asset        -- 目标资产
Level 1:         service      -- 服务/端口
Level 2:         vulnerability -- 漏洞
Level 3:         credential   -- 凭据
Level 4 (最右):  task/note    -- 任务和备注
```

边的方向从左到右，天然形成杀伤链视角。

### 7.3 前端语言切换

界面右上角提供语言切换按钮（中/EN），实现方式：

- 纯前端实现，使用 JavaScript 映射表
- 切换时即时刷新所有节点标签和界面文字
- 语言选择保存到 `localStorage`，下次打开自动恢复
- 不涉及后端接口，无需请求服务器

```javascript
// 标签映射表
const LABELS = {
    zh: { asset: "资产", service: "服务", vulnerability: "漏洞",
          credential: "凭据", task: "任务", note: "备注" },
    en: { asset: "ASSET", service: "SERVICE", vulnerability: "VULN",
          credential: "CRED", task: "TASK", note: "NOTE" }
};
```

### 7.4 交互

- **点击节点** → 右侧详情面板显示该条目的完整信息
- **拖拽节点** → 手动调整位置（vis.js 原生支持）
- **连线** → 在图上选中一个节点，再选中另一个节点，点击"添加连线"
- **缩放/平移** → 鼠标滚轮 + 拖拽画布
- **筛选** → 可以按 category 筛选显示哪些节点
- **状态变更** → 右侧面板可以快捷切换条目状态

---

## 8. 状态机设计

### 8.1 原则

- **只读**：只分析，不修改黑板
- **建议性**：输出是建议列表，不是指令
- **可忽略**：人决定做不做

### 8.2 规则存储

所有规则以 YAML 文件存储在 `rules/` 目录下，支持热加载（修改后无需重启）。

```
rules/
├── service_rules.yaml       # 服务相关规则
├── vulnerability_rules.yaml # 漏洞相关规则
├── credential_rules.yaml    # 凭据相关规则
├── lateral_rules.yaml       # 横向移动相关规则
└── general_rules.yaml       # 通用规则（报告等）
```

规则文件结构：

```yaml
# rules/service_rules.yaml

- id: R1
  name: 未识别服务
  category: service
  trigger:
    # 条件定义：当 target 有端口但无关联 service 条目时触发
    condition: "target.has_port AND NOT target.has_service_entry"
  suggestion:
    title: "对 {ip}:{port} 进行服务识别"
    reason: "发现端口但未识别服务类型"
    suggested_tool: "nmap -sV -sC -p {port} {ip}"
  priority: high    # high / medium / low
  enabled: true     # 可临时禁用某条规则

- id: R2
  name: 未做目录扫描
  category: service
  trigger:
    condition: "service.is_web AND NOT service.has_vuln_entry"
  suggestion:
    title: "对 {ip}:{port} 进行目录枚举"
    reason: "Web 服务未做目录扫描"
    suggested_tool: "gobuster dir -u http://{ip}:{port}/ -w /usr/share/wordlists/dirb/common.txt"
  priority: high
  enabled: true
```

**好处：**
- 红队成员可以直接加规则，不用改代码
- 不同项目可以加载不同规则集
- 禁用/启用一条规则只改 `enabled: true/false`
- 触发条件用字符串表达式，状态机引擎解释执行

**前端在线编辑：** 除了直接改 YAML 文件，前端也提供规则编辑页面，支持增删改规则、启用/禁用、拖拽排序优先级。前端编辑的结果同步写回 `rules/` 目录下的 YAML 文件。

**API 接口：**

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/rules` | 获取所有规则 |
| POST | `/api/rules` | 新增规则 |
| PUT | `/api/rules/{id}` | 更新规则 |
| DELETE | `/api/rules/{id}` | 删除规则 |
| PATCH | `/api/rules/{id}/toggle` | 启用/禁用规则 |
| POST | `/api/rules/reload` | 手动触发规则热重载 |

### 8.3 规则列表

| # | 规则名 | 触发条件 | 建议 | 优先级 | 文件 |
|---|--------|---------|------|--------|------|
| R1 | 未识别服务 | target有端口但无关联service条目 | "对 {ip}:{port} 进行服务识别" | [!] high | service_rules.yaml |
| R2 | 未做目录扫描 | 有HTTP/HTTPS服务但无vulnerability关联 | "对 {ip}:{port} 进行目录枚举" | [!] high | service_rules.yaml |
| R3 | 未做漏洞扫描 | 有Web服务但无漏洞条目 | "对 {ip}:{port} 进行漏洞扫描(nikto等)" | [-] medium | vulnerability_rules.yaml |
| R4 | 有漏洞未利用 | 有vulnerability条目status != exploited | "尝试利用漏洞: {title}" | [!] high | vulnerability_rules.yaml |
| R5 | 有凭据未验证 | credential条目status = new | "验证凭据: {username}@{protocol}" | [!] high | credential_rules.yaml |
| R6 | 有凭据未横向 | credential已confirmed但无后续节点 | "使用凭据 {username} 尝试横向移动" | [-] medium | credential_rules.yaml |
| R7 | SMB未测试 | 有445端口但无SMB相关发现 | "检查SMB匿名访问和共享枚举" | [!] high | service_rules.yaml |
| R8 | 提权未尝试 | 有已利用漏洞但无提权任务 | "尝试提权操作" | [-] medium | general_rules.yaml |
| R9 | 域环境未深挖 | 有域相关信息但无域攻击路径 | "分析域环境，寻找域管攻击路径" | [-] medium | general_rules.yaml |
| R10 | 未生成报告 | 项目status = active且有exploited条目 | "建议生成渗透测试报告" | [.] low | general_rules.yaml |

### 8.4 优先级标记规范

| 优先级 | 标记 | 说明 |
|--------|------|------|
| high | [!] | 需要立即关注 |
| medium | [-] | 建议处理 |
| low | [.] | 可以稍后 |

### 8.5 输出格式

```json
{
    "suggestions": [
        {
            "rule_id": "R1",
            "priority": "high",
            "title": "对 192.168.1.1:8080 进行服务识别",
            "reason": "发现端口但未识别服务类型",
            "related_entries": [12, 15],
            "suggested_tool": "nmap -sV -sC -p 8080 192.168.1.1"
        }
    ],
    "summary": {
        "total_suggestions": 5,
        "high_priority": 3,
        "coverage": "已覆盖 60% 攻击面"
    }
}
```

### 8.6 热加载机制

状态机引擎启动时加载所有 YAML 规则文件，同时监听文件变化（watchdog 或简单定时轮询）。
规则文件修改后自动重新加载，无需重启服务。

```python
# core/state_machine.py 概念

class StateMachine:
    def __init__(self, rules_dir: str = "rules/"):
        self.rules_dir = rules_dir
        self.rules = self._load_all_rules()
    
    def _load_all_rules(self):
        """加载 rules/ 目录下所有 .yaml 文件"""
        rules = []
        for yaml_file in Path(self.rules_dir).glob("*.yaml"):
            with open(yaml_file) as f:
                rules.extend(yaml.safe_load(f))
        return [r for r in rules if r.get("enabled", True)]
    
    def reload_rules(self):
        """热重载规则（供 API 调用或文件监听触发）"""
        self.rules = self._load_all_rules()
    
    def suggest(self, project_id) -> List[Suggestion]:
        """分析黑板状态，匹配规则，返回建议"""
        snapshot = self._snapshot(project_id)
        suggestions = []
        for rule in self.rules:
            if self._evaluate(rule["trigger"]["condition"], snapshot):
                suggestions.append(self._build_suggestion(rule, snapshot))
        return sorted(suggestions, key=lambda s: PRIORITY_ORDER[s.priority])
```

---

## 9. 页面设计

### 9.1 登录页

最简：用户名 + 密码 + 登录按钮。

### 9.2 设置页

用户修改自己的登录密码。修改后写入 `config.py` 的 `USERS` 字典。

```
+--------------------------------------------------+
|  Settings                             [Save]     |
+--------------------------------------------------+
|                                                  |
|  Current User: xiaowang                          |
|                                                  |
|  Change Password                                 |
|                                                  |
|  New Password:      [.....................]       |
|                                                  |
|  Confirm Password:  [.....................]       |
|                                                  |
+--------------------------------------------------+
```

**API 接口：**

| Method | Path | 说明 |
|--------|------|------|
| PUT | `/api/me/password` | 修改当前用户密码（写入 config.py）|

**注意：** 改的是 `config.py` 文件里的 `USERS` 字典，不是数据库。  
忘了密码也可以直接手动改 `config.py`，不需要前端。

**前端入口：** 导航栏右侧用户菜单 → "Settings" → 跳转设置页。

### 9.3 规则管理页

前端可视化编辑状态机规则，支持增删改、启用禁用。

```
+--------------------------------------------------+
|  Rules Management           [Add Rule] [Reload]  |
+--------------------------------------------------+
|                                                  |
|  [x] R1  未识别服务           high    [Edit][x]  |
|  [x] R2  未做目录扫描         high    [Edit][x]  |
|  [ ] R3  未做漏洞扫描         medium  [Edit][x]  |
|  [x] R4  有漏洞未利用         high    [Edit][x]  |
|  ...                                             |
|                                                  |
+--------------------------------------------------+
```

勾选框控制 `enabled`，点击 `Edit` 展开编辑触发条件和建议文案，`Reload` 手动触发热重载。

### 9.4 项目列表页

```
+--------------------------------------------------+
|  RedTeam Platform                  [New Project]  |
+--------------------------------------------------+
|                                                  |
|  +--------------------------------------------+  |
|  | XX Bank Pentest                            |  |
|  | Targets: 5  |  Findings: 23  |  3 users    |  |
|  | Last update: 2 hours ago                   |  |
|  +--------------------------------------------+  |
|                                                  |
|  +--------------------------------------------+  |
|  | XX Corp Red Team Assessment                |  |
|  | Targets: 12  |  Findings: 8  |  2 users    |  |
|  | Last update: 1 day ago                     |  |
|  +--------------------------------------------+  |
|                                                  |
+--------------------------------------------------+
```

### 9.5 项目主页（核心页面）

```
+------------------------------------------------------------------+--------------+
|  XX银行渗透测试                              [添加目标] [导入数据] |              |
+------------------------------------------------------------------+   详情面板    |
|                                                                  |              |
|          攻击图 (vis.js, 从左到右分层)                             |  (点击节点后   |
|                                                                  |   显示详情)   |
|  Level 0        Level 1      Level 2    Level 3                 |              |
|                                                                  |  +----------+|
|  [192.168.1.1]-> [80/IIS] -> [SQL注入] -> [sa凭据]              |  | Port: 80 ||
|       |           [22/SSH]                                      |  | Svc: IIS ||
|       |           [445/SMB]-> [SMB共享]                         |  | Ver: 10.0 ||
|       |           [3306/MySQL]                                  |  | Status:NEW||
|                                                                  |  +----------+|
|                                                                  |              |
|                                                                  |  Related:     |
|                                                                  |  - SQL注入    |
|                                                                  |  - sa null    |
|                                                                  |              |
|                                                                  |  Actions:     |
|                                                                  |  [Link] [Edit]|
|                                                                  |  [Set Status] |
+------------------------------------------------------------------+--------------+
|  STATUS SUGGESTIONS                                              |              |
|  [!] Test SMB anonymous on 192.168.1.1:445                       |              |
|  [!] Attempt SQL injection exploitation for DB access            |              |
|  [!] Validate credential sa@MSSQL                                |              |
+------------------------------------------------------------------+--------------+
```

### 9.6 攻击图节点卡片

vis.js 自定义节点，纯文字色块风格（中文模式示例）：

```
+------------------------+
| 服务              NEW  |   <-- category标签 + 状态标记
| 192.168.1.1:80        |   <-- 关联目标:端口
| Severity: High         |   <-- 严重性（漏洞类型才有）
| Author: xiaowang      |   <-- 录入者
+------------------------+
```

英文模式下标签显示为 SERVICE / VULN / CRED 等，通过界面语言切换按钮切换。

---

## 10. 数据导入器设计

### 10.1 导入流程

```
用户上传文件
    ↓
后端接收文件 → 保存到 data/uploads/
    ↓
对应 Importer 解析文件内容
    ↓
生成 BlackboardEntry 列表（批量）
    ↓
写入黑板，返回导入统计
```

### 10.2 支持的导入格式

| 格式 | 来源工具 | 自动生成的条目 |
|------|---------|---------------|
| Nmap XML | nmap -oX | service (端口/服务) + vulnerability (脚本输出) |
| Nessus | Nessus导出 | vulnerability |
| BloodHound JSON | SharpHound | asset + service (域信息) |
| 通用JSON | 手动构造 | 按字段映射 |

### 10.3 Nmap 导入示例逻辑

```
Nmap XML
  ├── <host> → 如目标不存在，创建 target 条目
  ├── <port> → 生成 service 类型的 BlackboardEntry
  │             content = {port, protocol, service, version, banner}
  └── <script> → 如有漏洞发现，生成 vulnerability 类型条目
                   content = {name, severity, description, evidence}
```

导入时**不覆盖已有的同类型条目**，避免重复。  
如果同一端口已有 service 条目，跳过或提示用户。

---

## 11. MCP 预留

当前阶段不实现 MCP，但架构上预留：

```python
# api/mcp_adapter.py (Phase 2 实现)
# 将 REST API 映射为 MCP tools
#
# MCP Tool 定义（伪代码）:
#
# tools:
#   - name: "list_projects"
#     description: "列出所有项目"
#
#   - name: "get_blackboard"
#     description: "获取项目黑板状态"
#     parameters: { project_id: int }
#
#   - name: "get_attack_graph"
#     description: "获取攻击图数据"
#     parameters: { project_id: int }
#
#   - name: "get_suggestions"
#     description: "获取下一步建议"
#     parameters: { project_id: int }
#
#   - name: "add_entry"
#     description: "录入一条发现"
#     parameters: { project_id, category, title, content, target_ip }
#
# 所有 MCP tool 底层调用的就是现有 REST API，加一个适配层即可。
# Token 鉴权复用 JWT 机制。
```

---

## 12. 从幕论神图复用清单

| 模块 | 源文件 | 复用方式 | 改动 |
|------|--------|---------|------|
| Nmap导入 | `modules/data_importer.py:NmapImporter` | 移植 | 输出改为 BlackboardEntry |
| Nessus导入 | `modules/data_importer.py:NessusImporter` | 移植 | 同上 |
| BloodHound导入 | `modules/domain_importer.py:BloodHoundImporter` | 移植 | 同上 |
| Linux提权分析 | `modules/privilege_analyzer.py` | 直接复制 | 独立使用，人输入信息→系统分析 |
| 报告生成 | `modules/report_generator.py` | 移植 | 输入改为黑板数据 |

**不复用的部分：**

| 幕论神图的 | 原因 |
|-----------|------|
| Flask 后端 (app.py) | 换 FastAPI |
| SQLAlchemy models (models.py) | 重新设计表结构 |
| 攻击路径自动分析 (path_analyzer.py) | 改为人工连线 + 状态机建议 |
| vis.js 图数据生成逻辑 | 重新实现（分层布局 vs 力导向）|
| AI集成模块 | 暂不需要 |
| 域攻击路径分析 (domain_analyzer.py) | 后续按需移植 |

---

## 13. 实施计划

### Step 1: 项目骨架 + 数据库

- 创建项目结构
- FastAPI 入口 + 配置
- SQLAlchemy 模型（所有表）
- 数据库初始化
- 登录/JWT 认证

### Step 2: 黑板 CRUD

- 项目 CRUD API + 页面
- 目标 CRUD API
- 黑板条目 CRUD API + 录入页面
- 条目状态流转

### Step 3: 攻击图可视化

- vis.js 集成
- 从黑板数据构建节点
- 分层从左到右布局
- 节点点击 → 右侧详情面板
- 人手动连线（添加/删除边）
- 节点样式（颜色/标签/状态）

### Step 4: 数据导入

- 移植 NmapImporter → 输出到黑板
- 移植 NessusImporter
- 移植 BloodHoundImporter
- 上传文件 API + 前端

### Step 5: 状态机建议

- 实现规则引擎
- 10条核心规则
- 建议列表 API + 前端展示

### Step 6: 打磨 + 报告

- 移植 ReportGenerator
- 前端交互打磨
- 错误处理
- requirements.txt + README

**requirements.txt:**

```
fastapi
uvicorn[standard]
sqlalchemy
python-jose[cryptography]
pyyaml
jinja2
python-multipart
```

---

## 14. 待确认项

- [ ] 项目是否需要"加入码"机制（邀请码），还是直接把人加进去？
- [ ] 攻击图节点是否需要支持拖拽后自动保存位置？
- [ ] 导入时同一端口已有数据，是跳过还是覆盖？
- [ ] 是否需要"项目归档"功能？
- [ ] 前端配色方案偏好？
