# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 数据导入器
支持 Nmap XML、Nessus、JSON 导入
移植自幕论神图，输出改为 BlackboardEntry
"""

import defusedxml.ElementTree as ET
import json
from typing import Dict, Any

from core.models import BlackboardEntry, Target


class BaseImporter:
    def import_from_bytes(self, content: bytes, project_id: int, author: str) -> Dict[str, Any]:
        raise NotImplementedError


class NmapImporter(BaseImporter):
    """Nmap XML 导入器（自动去重，重复导入同一端口跳过）"""

    def import_from_bytes(self, content: bytes, project_id: int, author: str) -> Dict[str, Any]:
        root = ET.fromstring(content)
        stats = {'targets': 0, 'services': 0, 'vulnerabilities': 0, 'skipped': 0}

        # 现有目标 IP 集合
        existing_ips = {t['ip'] for t in Target.get_by_project(project_id)}
        # 现有 service 条目 key: (ip, port) 用于去重
        existing_svc = {(e.get('target_id'), (e.get('content') or {}).get('port'))
                        for e in BlackboardEntry.get_by_project(project_id, 'service')}

        for host in root.findall('.//host'):
            status = host.find('status')
            if status is not None and status.get('state') != 'up':
                continue

            ip = None
            for addr in host.findall('address'):
                if addr.get('addrtype') == 'ipv4':
                    ip = addr.get('addr')
                    break
            if not ip:
                continue

            hostname = None
            hostname_el = host.find('.//hostname')
            if hostname_el is not None:
                hostname = hostname_el.get('name')

            os_name = None
            os_el = host.find('.//osmatch')
            if os_el is not None:
                os_name = os_el.get('name')

            # 目标存在则复用，否则创建
            if ip in existing_ips:
                target = next((t for t in Target.get_by_project(project_id) if t['ip'] == ip), None)
                target_id = target['id'] if target else None
            else:
                target_id = Target.create(project_id, ip, hostname, os_name, "Nmap 自动导入")
                existing_ips.add(ip)
                stats['targets'] += 1

            ports = host.find('ports')
            if ports is None:
                continue

            for port_el in ports.findall('port'):
                port_num = int(port_el.get('portid', 0))
                protocol = port_el.get('protocol', 'tcp')

                state_el = port_el.find('state')
                state = state_el.get('state', 'unknown') if state_el is not None else 'unknown'
                if state != 'open':
                    continue

                # 去重：同目标同端口已存在则跳过
                if (target_id, port_num) in existing_svc:
                    stats['skipped'] += 1
                    continue

                service_el = port_el.find('service')
                service_name = service_el.get('name', '') if service_el is not None else ''
                version = service_el.get('product', '') if service_el is not None else ''
                if service_el is not None and service_el.get('version'):
                    version += ' ' + service_el.get('version')

                BlackboardEntry.create(
                    project_id, author, 'service',
                    f"{port_num}/{protocol} {service_name}",
                    {
                        'port': port_num,
                        'protocol': protocol,
                        'service': service_name,
                        'version': version.strip(),
                        'state': state,
                    },
                    target_id
                )
                existing_svc.add((target_id, port_num))
                stats['services'] += 1

                for script_el in port_el.findall('script'):
                    script_id = script_el.get('id', '')
                    script_output = script_el.get('output', '')
                    if any(kw in script_id.lower() for kw in ['vuln', 'exploit', 'cve']):
                        BlackboardEntry.create(
                            project_id, author, 'vulnerability',
                            f"Script: {script_id}",
                            {
                                'name': script_id,
                                'severity': 'medium',
                                'description': script_output[:500],
                                'source': f"nmap script on port {port_num}",
                            },
                            target_id
                        )
                        stats['vulnerabilities'] += 1

        return stats


class NessusImporter(BaseImporter):
    """Nessus 报告导入器（支持 .nessus XML 和自定义 JSON）"""

    def import_from_bytes(self, content: bytes, project_id: int, author: str) -> Dict[str, Any]:
        # 尝试 JSON 解析；失败则按 .nessus XML 解析
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError("无法解析文件编码")
        stripped = text.lstrip()
        if stripped.startswith('{') or stripped.startswith('['):
            return self._import_json(content, project_id, author)
        return self._import_xml(text, project_id, author)

    def _import_json(self, content: bytes, project_id: int, author: str) -> Dict[str, Any]:
        data = json.loads(content)
        stats = {'targets': 0, 'vulnerabilities': 0, 'skipped': 0}
        existing_ips = {t['ip'] for t in Target.get_by_project(project_id)}

        for host in data.get('hosts', []):
            ip = host.get('host', '')
            if not ip:
                continue
            if ip in existing_ips:
                target_id = next((t['id'] for t in Target.get_by_project(project_id)
                                  if t['ip'] == ip), None)
            else:
                target_id = Target.create(project_id, ip, None, None, "Nessus 自动导入")
                existing_ips.add(ip)
                stats['targets'] += 1

            for item in host.get('items', []):
                name = item.get('plugin_name', '')
                existing = BlackboardEntry.get_by_project(project_id, 'vulnerability', None)
                if any((e.get('content') or {}).get('name') == name
                       and e.get('title') == name for e in existing):
                    stats['skipped'] += 1
                    continue
                severity_map = {
                    'critical': 'critical', 'high': 'high', 'medium': 'medium',
                    'low': 'low', 'info': 'info',
                }
                severity = severity_map.get(item.get('severity', '').lower(), 'info')
                BlackboardEntry.create(
                    project_id, author, 'vulnerability', name or 'Unknown',
                    {
                        'name': name,
                        'severity': severity,
                        'cve_id': item.get('cve', ''),
                        'description': item.get('description', '')[:500],
                        'cvss': item.get('cvss3_base_score') or item.get('cvss_base_score'),
                        'source': 'nessus',
                    },
                    target_id
                )
                stats['vulnerabilities'] += 1
        return stats

    def _import_xml(self, text: str, project_id: int, author: str) -> Dict[str, Any]:
        """解析标准 .nessus XML 格式"""
        root = ET.fromstring(text)
        stats = {'targets': 0, 'vulnerabilities': 0, 'skipped': 0}
        existing_ips = {t['ip'] for t in Target.get_by_project(project_id)}

        for report in root.findall('.//Report'):
            for host in report.findall('.//ReportHost'):
                ip = host.get('name', '')
                if not ip:
                    continue
                if ip in existing_ips:
                    target_id = next((t['id'] for t in Target.get_by_project(project_id)
                                      if t['ip'] == ip), None)
                else:
                    target_id = Target.create(project_id, ip, None, None, "Nessus 自动导入")
                    existing_ips.add(ip)
                    stats['targets'] += 1

                for item in host.findall('.//ReportItem'):
                    plugin_name = item.get('pluginName', '') or item.get('plugin_name', '')
                    severity_str = (item.get('severity', '0'))
                    sev_map = {'0': 'info', '1': 'low', '2': 'medium', '3': 'high', '4': 'critical'}
                    severity = sev_map.get(severity_str, 'info')

                    # 去重
                    existing = BlackboardEntry.get_by_project(project_id, 'vulnerability', None)
                    if any((e.get('content') or {}).get('name') == plugin_name
                           for e in existing):
                        stats['skipped'] += 1
                        continue

                    BlackboardEntry.create(
                        project_id, author, 'vulnerability', plugin_name or 'Unknown',
                        {
                            'name': plugin_name,
                            'severity': severity,
                            'cve_id': item.get('cve', ''),
                            'description': item.findtext('description', '')[:500],
                            'source': 'nessus',
                        },
                        target_id
                    )
                    stats['vulnerabilities'] += 1
        return stats


class JsonImporter(BaseImporter):
    """通用 JSON 导入器（校验类别/状态，防止绕过 API 枚举限制）"""

    VALID_CATEGORIES = {'asset', 'service', 'vulnerability', 'credential', 'task', 'note'}
    VALID_STATUSES = {'new', 'confirmed', 'exploited', 'fixed'}

    def import_from_bytes(self, content: bytes, project_id: int, author: str) -> Dict[str, Any]:
        data = json.loads(content)
        stats = {'entries': 0}

        entries = data if isinstance(data, list) else data.get('entries', [])
        for entry in entries:
            category = entry.get('category', 'note')
            title = entry.get('title', 'Imported entry')
            entry_content = entry.get('content', entry)
            target_id = entry.get('target_id')
            status = entry.get('status', 'new')
            if category not in self.VALID_CATEGORIES:
                raise ValueError(f"非法类别: {category}")
            if status not in self.VALID_STATUSES:
                raise ValueError(f"非法状态: {status}")
            if target_id is not None:
                # 目标必须属于本项目
                t = Target.get_by_id(target_id)
                if not t or t['project_id'] != project_id:
                    raise ValueError(f"目标不存在或不属于本项目: {target_id}")

            BlackboardEntry.create(
                project_id, author, category, title, entry_content, target_id, status
            )
            stats['entries'] += 1

        return stats


def get_importer(format_type: str) -> BaseImporter:
    importers = {
        'nmap': NmapImporter,
        'nessus': NessusImporter,
        'json': JsonImporter,
    }
    cls = importers.get(format_type)
    if not cls:
        raise ValueError(f"不支持的导入格式: {format_type}")
    return cls()
