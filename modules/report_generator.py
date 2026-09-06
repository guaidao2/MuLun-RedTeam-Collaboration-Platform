# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 报告生成模块
从项目黑板数据生成 HTML 报告
"""

import json
from datetime import datetime
from typing import Dict, List

from core.models import db


def _esc(s):
    if s is None:
        return ''
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') \
                 .replace('"', '&quot;').replace("'", '&#39;')


def _category_label(cat: str) -> str:
    return {'asset': '资产', 'service': '服务', 'vulnerability': '漏洞',
            'credential': '凭据', 'task': '任务', 'note': '备注'}.get(cat, cat)


def _status_label(s: str) -> str:
    return {'new': '新发现', 'confirmed': '已确认', 'exploited': '已利用',
            'fixed': '已修复'}.get(s, s)


def _render_entry_rows(entries: List[Dict]) -> str:
    rows = []
    for e in entries:
        sev = (e.get('content') or {}).get('severity', '') if isinstance(e.get('content'), dict) else ''
        color = {'critical': '#dc2626', 'high': '#dc2626', 'medium': '#d97706',
                 'low': '#2563eb'}.get(str(sev).lower(), '')
        sev_html = f' <span style="color:{color};font-weight:bold;">[{_esc(sev)}]</span>' if sev else ''
        rows.append(f'''<tr>
            <td>{_esc(e.get('title'))}{sev_html}</td>
            <td>{_esc(e.get('author'))}</td>
            <td>{_status_label(e.get('status'))}</td>
            <td><code style="font-size:11px;">{_esc(json.dumps(e.get('content'), ensure_ascii=False, default=str))}</code></td>
        </tr>''')
    return '\n'.join(rows)


def generate_html_report(project_id: int) -> str:
    """生成项目的 HTML 报告"""
    with db.get_connection() as conn:
        project = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
        targets = [dict(r) for r in conn.execute(
            "SELECT * FROM targets WHERE project_id = ?", (project_id,)).fetchall()]
        entries = []
        for r in conn.execute(
            "SELECT * FROM blackboard_entries WHERE project_id = ? ORDER BY category, status",
            (project_id,)).fetchall():
            d = dict(r)
            d['content'] = json.loads(d['content']) if d['content'] else {}
            entries.append(d)
        edges = [dict(r) for r in conn.execute(
            "SELECT * FROM attack_edges WHERE project_id = ?", (project_id,)).fetchall()]

    # 汇总统计
    vulns = [e for e in entries if e['category'] == 'vulnerability']
    creds = [e for e in entries if e['category'] == 'credential']
    exploited = [e for e in entries if e['status'] == 'exploited']
    critical = [e for e in vulns if (e.get('content') or {}).get('severity') in ('critical', 'high')]

    # 攻击链
    node_map = {e['id']: e for e in entries}
    chain_html = '<div style="color:#6b7280;">无</div>'
    if edges:
        parts = []
        for edge in edges:
            f = node_map.get(edge['from_entry_id'])
            t = node_map.get(edge['to_entry_id'])
            parts.append(f"<div>{_esc(f['title']) if f else '?'} → {_esc(t['title']) if t else '?'}"
                         f"{_esc(' (' + edge['label'] + ')') if edge.get('label') else ''}</div>")
        chain_html = '\n'.join(parts)

    # 分组条目
    by_cat = {}
    for e in entries:
        by_cat.setdefault(e['category'], []).append(e)
    cat_html = []
    for cat in ['asset', 'service', 'vulnerability', 'credential', 'task', 'note']:
        if cat not in by_cat:
            continue
        cat_html.append(f'''<h3 style="font-size:14px;border-bottom:1px solid #eee;padding-bottom:6px;">{_category_label(cat)} ({len(by_cat[cat])})</h3>
        <table style="width:100%;border-collapse:collapse;font-size:12px;">
            <tr style="background:#f5f5f5;">
                <th style="padding:6px;text-align:left;">名称</th><th style="padding:6px;text-align:left;">录入人</th>
                <th style="padding:6px;text-align:left;">状态</th><th style="padding:6px;text-align:left;">内容</th>
            </tr>
            {_render_entry_rows(by_cat[cat])}
        </table>''')

    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>渗透测试报告 - {_esc(project['name'])}</title></head>
<body style="font-family:-apple-system,Segoe UI,Microsoft YaHei,sans-serif;max-width:900px;margin:0 auto;padding:30px;color:#111827;line-height:1.6;">
    <div style="text-align:center;border-bottom:3px solid #2563eb;padding-bottom:16px;margin-bottom:24px;">
        <h1 style="margin:0;font-size:22px;">幕论红队协同平台 · 渗透测试报告</h1>
        <div style="color:#6b7280;margin-top:6px;">项目：{_esc(project['name'])} &nbsp;|&nbsp; 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
    </div>

    <h2 style="font-size:16px;">一、项目概览</h2>
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <tr><td style="padding:4px;background:#f5f5f5;">项目描述</td><td style="padding:4px;">{_esc(project.get('description') or '无')}</td></tr>
        <tr><td style="padding:4px;background:#f5f5f5;">目标数</td><td style="padding:4px;">{len(targets)}</td></tr>
        <tr><td style="padding:4px;background:#f5f5f5;">发现总数</td><td style="padding:4px;">{len(entries)}（漏洞 {len(vulns)} / 凭据 {len(creds)}）</td></tr>
        <tr><td style="padding:4px;background:#f5f5f5;">已利用</td><td style="padding:4px;">{len(exploited)}</td></tr>
        <tr><td style="padding:4px;background:#f5f5f5;">高危以上漏洞</td><td style="padding:4px;">{len(critical)}</td></tr>
    </table>

    <h2 style="font-size:16px;margin-top:20px;">二、攻击链</h2>
    {chain_html}

    <h2 style="font-size:16px;margin-top:20px;">三、发现详情</h2>
    {''.join(cat_html)}

    <div style="margin-top:30px;padding-top:12px;border-top:1px solid #eee;color:#9ca3af;font-size:11px;text-align:center;">
        本报告由幕论红队协同平台自动生成 · 仅限授权测试
    </div>
</body></html>'''
