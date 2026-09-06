# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - MCP Server
将平台能力以 MCP Tools 暴露（挂载到 /mcp，传输层由平台 Token 门卫鉴权）。
Token 调用方被视作平台管理员（可访问任意项目）。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP

from core.models import (Project, Target, BlackboardEntry, AttackEdge, db)
from core.state_machine import StateMachine
from modules.report_generator import generate_html_report
from modules.privilege_analyzer import analyze_text

mcp = FastMCP("RedTeam-Platform")

# 内部路由锚定在 '/'，由 FastAPI 挂载的 /mcp 作为统一入口（避免 /mcp/mcp 叠合）
try:
    mcp.settings.streamable_http_path = '/'
except Exception:
    pass

ADMIN = 'admin'
VALID_CATEGORIES = {'asset', 'service', 'vulnerability', 'credential', 'task', 'note'}
VALID_STATUSES = {'new', 'confirmed', 'exploited', 'fixed'}


def _err(msg: str) -> None:
    raise RuntimeError(msg)


def _check_project(project_id: int):
    p = Project.get_by_id(project_id)
    if not p:
        _err(f'项目不存在: {project_id}')
    return p


# ---------- 读 ----------

@mcp.tool()
def list_projects() -> dict:
    """列出平台上所有项目及其统计"""
    projects = Project.get_all()
    for p in projects:
        p['stats'] = Project.get_stats(p['id'])
    return {'projects': projects}


@mcp.tool()
def get_project(project_id: int) -> dict:
    """获取项目详情（含成员与统计）"""
    p = _check_project(project_id)
    p['members'] = Project.get_members(project_id)
    p['stats'] = Project.get_stats(project_id)
    return {'project': p}


@mcp.tool()
def list_targets(project_id: int) -> dict:
    """列出项目下所有目标主机"""
    _check_project(project_id)
    return {'targets': Target.get_by_project(project_id)}


@mcp.tool()
def list_entries(project_id: int, category: str = None, status: str = None) -> dict:
    """列出项目黑板条目（可按 category/status 过滤）"""
    _check_project(project_id)
    if category and category not in VALID_CATEGORIES:
        _err(f'非法类别: {category}')
    if status and status not in VALID_STATUSES:
        _err(f'非法状态: {status}')
    return {'entries': BlackboardEntry.get_by_project(project_id, category, None, status)}


@mcp.tool()
def get_attack_graph(project_id: int) -> dict:
    """获取项目攻击图（节点 + 边）"""
    _check_project(project_id)
    entries = BlackboardEntry.get_by_project(project_id)
    nodes = [{'id': e['id'], 'label': e['title'], 'category': e['category'],
              'status': e['status'], 'author': e['author'], 'content': e['content']}
             for e in entries]
    edges = [{'id': ed['id'], 'from': ed['from_entry_id'], 'to': ed['to_entry_id'],
              'label': ed['label']} for ed in AttackEdge.get_by_project(project_id)]
    return {'nodes': nodes, 'edges': edges}


@mcp.tool()
def get_suggestions(project_id: int) -> dict:
    """获取状态机给出的下一步建议（只读）"""
    _check_project(project_id)
    sm = StateMachine()
    data = sm.suggest(project_id)
    prio = {'high': 0, 'medium': 1, 'low': 2}
    return {'suggestions': sorted(data, key=lambda s: prio.get(s['priority'], 9))}


@mcp.tool()
def get_report(project_id: int, plain_text: bool = False) -> dict:
    """生成项目 HTML 报告；plain_text=True 时返回去标签文本"""
    _check_project(project_id)
    html = generate_html_report(project_id)
    if not plain_text:
        return {'html': html}
    import re
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return {'text': text}


@mcp.tool()
def analyze_privilege_escalation(text: str) -> dict:
    """从 Linux 枚举输出分析提权向量（SUID/sudo/docker 等）"""
    if not text or not text.strip():
        _err('文本不能为空')
    return {'findings': analyze_text(text)}


# ---------- 写 ----------

@mcp.tool()
def create_project(name: str, description: str = '') -> dict:
    """创建新项目（当前以平台管理员身份创建）"""
    if not name or not name.strip():
        _err('项目名不能为空')
    pid = Project.create(name.strip(), description or '', ADMIN)
    return {'project_id': pid}


@mcp.tool()
def add_target(project_id: int, ip: str, hostname: str = None, os_name: str = None) -> dict:
    """向项目添加目标主机"""
    _check_project(project_id)
    if not ip or not re_match(ip):
        _err('非法目标地址')
    existing = Target.get_by_project(project_id)
    if any(t['ip'] == ip for t in existing):
        _err(f'目标已存在: {ip}')
    tid = Target.create(project_id, ip, hostname, os_name, 'MCP 添加')
    return {'target_id': tid}


@mcp.tool()
def add_entry(project_id: int, category: str, title: str, content: dict = None,
              target_id: int = None, status: str = 'new') -> dict:
    """向项目黑板添加一条发现（asset/service/vulnerability/credential/task/note）"""
    _check_project(project_id)
    if category not in VALID_CATEGORIES:
        _err(f'非法类别: {category}')
    if status not in VALID_STATUSES:
        _err(f'非法状态: {status}')
    if target_id is not None:
        t = Target.get_by_id(target_id)
        if not t or t['project_id'] != project_id:
            _err(f'目标不存在或不属于该项目: {target_id}')
    content = content or {}
    if not title or not str(title).strip():
        # 文本类允许从 content.text 取首行
        txt = content.get('text') if isinstance(content, dict) else None
        title = str(txt).splitlines()[0][:40] if txt else None
    if not title:
        _err('标题不能为空')
    eid = BlackboardEntry.create(project_id, ADMIN, category, str(title), content,
                                 target_id, status)
    return {'entry_id': eid}


@mcp.tool()
def add_edge(project_id: int, from_entry_id: int, to_entry_id: int, label: str = '') -> dict:
    """在攻击图上为两个条目连线（标注关系）"""
    _check_project(project_id)
    f = BlackboardEntry.get_by_id(from_entry_id)
    t = BlackboardEntry.get_by_id(to_entry_id)
    if not f or not t or f['project_id'] != project_id or t['project_id'] != project_id:
        _err('节点不存在或不属于该项目')
    if from_entry_id == to_entry_id:
        _err('不能连接节点自身')
    if any(e['from_entry_id'] == from_entry_id and e['to_entry_id'] == to_entry_id
           for e in AttackEdge.get_by_project(project_id)):
        _err('该连线已存在')
    eid = AttackEdge.create(project_id, from_entry_id, to_entry_id, label, ADMIN)
    return {'edge_id': eid}


def re_match(ip: str):
    import re
    return bool(re.match(r'^[0-9a-zA-Z.\-_:]+$', ip))


def build_mcp_app():
    """返回可挂载到 FastAPI 的 Starlette 应用"""
    return mcp.streamable_http_app()
