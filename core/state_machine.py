# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 状态机规则引擎
从 rules/ 目录加载 YAML 规则，分析黑板状态给出建议
"""

import os
import uuid
from typing import List, Dict

import yaml

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import RULES_DIR

from core.models import db


# ==================== 安全条件求值器 ====================
# 支持布尔代数：and/or/not/比较(== != > < >= <=)/括号/整数
# 完全白名单，不使用 eval，杜绝 RCE

class _Token:
    __slots__ = ('type', 'value')

    def __init__(self, type, value):
        self.type = type    # 'num' | 'ident' | 'op' | 'lparen' | 'rparen'
        self.value = value


class SafeConditionEvaluator:
    IDENT_WHITELIST = {
        'target_count', 'has_target', 'entry_count', 'has_entries',
        'has_service', 'has_vuln', 'has_credential', 'has_task', 'has_note',
        'web_port_count', 'smb_port_count',
        'service_count', 'vuln_count', 'cred_count',
        # 状态感知
        'has_vuln_unexploited', 'vuln_unexploited_count',
        'has_cred_new', 'cred_new_count',
        'has_exploited', 'exploited_count',
        'has_report_ready', 'domain_entry_count',
        'True', 'False',
    }

    @staticmethod
    def _tokenize(s: str):
        if len(s) > 1000:
            raise ValueError("表达式过长")
        tokens = []
        i = 0
        n = len(s)
        depth = 0
        while i < n:
            c = s[i]
            if c.isspace():
                i += 1
                continue
            if c == '(':
                depth += 1
                if depth > 50:
                    raise ValueError("括号嵌套过深")
                tokens.append(_Token('lparen', c)); i += 1; continue
            if c == ')':
                depth -= 1
                if depth < 0:
                    raise ValueError("括号不匹配")
                tokens.append(_Token('rparen', c)); i += 1; continue
            if c.isdigit():
                if ord(c) > 0x7F:
                    raise ValueError(f"非法数字字符: {c!r}")
                j = i
                while j < n and '0' <= s[j] <= '9':
                    j += 1
                tokens.append(_Token('num', int(s[i:j]))); i = j; continue
            if c.isalpha() or c == '_':
                j = i
                while j < n and (s[j].isalnum() or s[j] == '_'):
                    j += 1
                tokens.append(_Token('ident', s[i:j])); i = j; continue
            # 运算符
            two = s[i:i+2]
            if two in ('==', '!=', '>=', '<='):
                tokens.append(_Token('op', two)); i += 2; continue
            if c in ('=', '>', '<'):
                tokens.append(_Token('op', c)); i += 1; continue
            # 未知字符 -> 非法
            raise ValueError(f"非法字符: {c!r}")
        if depth != 0:
            raise ValueError("括号不匹配")
        if len(tokens) > 200:
            raise ValueError("表达式过于复杂")
        return tokens

    @staticmethod
    def evaluate(expr: str, ctx: Dict) -> bool:
        """安全求值布尔表达式。非法输入抛 ValueError。"""
        tokens = SafeConditionEvaluator._tokenize(expr)
        pos = [0]

        def peek():
            return tokens[pos[0]] if pos[0] < len(tokens) else None

        def consume():
            t = tokens[pos[0]]
            pos[0] += 1
            return t

        def parse_or():
            left = parse_and()
            while peek() and peek().type == 'ident' and peek().value == 'or':
                consume()
                right = parse_and()
                left = bool(left) or bool(right)
            return left

        def parse_and():
            left = parse_not()
            while peek() and peek().type == 'ident' and peek().value == 'and':
                consume()
                right = parse_not()
                left = bool(left) and bool(right)
            return left

        def parse_not():
            if peek() and peek().type == 'ident' and peek().value == 'not':
                consume()
                return not parse_not()
            return parse_cmp()

        def parse_cmp():
            val = parse_atom()
            t = peek()
            if t and t.type == 'op':
                consume()
                rhs = parse_atom()
                if t.value == '==': return val == rhs
                if t.value == '!=': return val != rhs
                if t.value == '>': return val > rhs
                if t.value == '<': return val < rhs
                if t.value == '>=': return val >= rhs
                if t.value == '<=': return val <= rhs
                raise ValueError(f"未知运算符: {t.value}")
            return val

        def parse_atom():
            t = peek()
            if not t:
                raise ValueError("表达式不完整")
            if t.type == 'num':
                consume()
                return t.value
            if t.type == 'lparen':
                consume()
                v = parse_or()
                if not peek() or peek().type != 'rparen':
                    raise ValueError("缺少右括号")
                consume()
                return v
            if t.type == 'ident':
                consume()
                if t.value not in SafeConditionEvaluator.IDENT_WHITELIST:
                    raise ValueError(f"非法标识符: {t.value}")
                if t.value in ('True', 'False'):
                    return t.value == 'True'
                if t.value not in ctx:
                    raise ValueError(f"未知变量: {t.value}")
                return ctx[t.value]
            raise ValueError(f"非法 token: {t.value}")

        if not tokens:
            return False
        result = parse_or()
        if pos[0] != len(tokens):
            raise ValueError("表达式后有多余内容")
        return bool(result)


class StateMachine:
    def __init__(self, rules_dir: str = None):
        self.rules_dir = rules_dir or RULES_DIR
        os.makedirs(self.rules_dir, exist_ok=True)
        self.rules = self._load_all_rules()

    def _load_all_rules(self) -> List[Dict]:
        """加载 rules/ 目录下所有 .yaml 文件"""
        rules = []
        if not os.path.exists(self.rules_dir):
            return rules
        for fname in os.listdir(self.rules_dir):
            if fname.endswith('.yaml') or fname.endswith('.yml'):
                fpath = os.path.join(self.rules_dir, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, list):
                        for rule in data:
                            rule['_file'] = fname
                            rules.append(rule)
        return rules

    def reload_rules(self):
        """热重载规则"""
        self.rules = self._load_all_rules()

    def get_all_rules(self) -> List[Dict]:
        return [r for r in self.rules]

    def _get_snapshot(self, project_id: int) -> Dict:
        """获取项目黑板快照"""
        with db.get_connection() as conn:
            targets = [dict(r) for r in conn.execute(
                "SELECT * FROM targets WHERE project_id = ?", (project_id,)
            ).fetchall()]

            entries = []
            for r in conn.execute(
                "SELECT * FROM blackboard_entries WHERE project_id = ?", (project_id,)
            ).fetchall():
                d = dict(r)
                entries.append(d)

            # 构建摘要
            categories = {}
            for e in entries:
                cat = e['category']
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(e)

            # 按端口建立索引
            services_by_port = {}
            vulns_by_target = {}
            creds = []
            for e in entries:
                import json
                content = json.loads(e['content']) if e['content'] else {}
                if e['category'] == 'service':
                    port = content.get('port')
                    if port:
                        services_by_port[port] = {**e, 'content': content}
                elif e['category'] == 'vulnerability':
                    tid = e.get('target_id')
                    if tid:
                        if tid not in vulns_by_target:
                            vulns_by_target[tid] = []
                        vulns_by_target[tid].append({**e, 'content': content})
                elif e['category'] == 'credential':
                    creds.append({**e, 'content': content})

            # 检查哪些端口有 web 服务
            web_ports = []
            for port, svc in services_by_port.items():
                svc_name = (svc['content'].get('service', '') or '').lower()
                if any(w in svc_name for w in ['http', 'www', 'apache', 'nginx', 'iis']):
                    web_ports.append(port)

            # 检查哪些端口有 SMB
            smb_ports = []
            for port, svc in services_by_port.items():
                svc_name = (svc['content'].get('service', '') or '').lower()
                if any(s in svc_name for s in ['smb', 'netbios', 'microsoft-ds']):
                    smb_ports.append(port)
                elif port == 445:
                    smb_ports.append(port)

            # 状态感知统计
            vuln_entries = categories.get('vulnerability', [])
            cred_entries = categories.get('credential', [])
            vuln_unexploited = [e for e in vuln_entries if e.get('status') != 'exploited']
            cred_new = [e for e in cred_entries if e.get('status') == 'new']
            exploited_all = [e for e in entries if e.get('status') == 'exploited']
            domain_entries = categories.get('asset', []) + categories.get('note', [])
            domain_count = sum(1 for e in entries
                               if 'domain' in str(e.get('title', '')).lower()
                               or (e.get('content') or '').find('domain') >= 0)

            return {
                'targets': targets,
                'entries': entries,
                'categories': categories,
                'services_by_port': services_by_port,
                'vulns_by_target': vulns_by_target,
                'creds': creds,
                'web_ports': web_ports,
                'smb_ports': smb_ports,
                'target_ids': [t['id'] for t in targets],
                # 状态感知字段
                'vuln_unexploited_count': len(vuln_unexploited),
                'has_vuln_unexploited': len(vuln_unexploited) > 0,
                'cred_new_count': len(cred_new),
                'has_cred_new': len(cred_new) > 0,
                'exploited_count': len(exploited_all),
                'has_exploited': len(exploited_all) > 0,
                'domain_entry_count': domain_count,
                'has_report_ready': len(exploited_all) > 0,
            }

    def _evaluate_condition(self, condition: str, snapshot: Dict) -> bool:
        """评估规则条件（安全表达式，无 eval）"""
        try:
            ctx = {
                'target_count': len(snapshot['targets']),
                'has_target': len(snapshot['targets']) > 0,
                'entry_count': len(snapshot['entries']),
                'has_entries': len(snapshot['entries']) > 0,
                'has_service': len(snapshot['categories'].get('service', [])) > 0,
                'has_vuln': len(snapshot['categories'].get('vulnerability', [])) > 0,
                'has_credential': len(snapshot['categories'].get('credential', [])) > 0,
                'has_task': len(snapshot['categories'].get('task', [])) > 0,
                'has_note': len(snapshot['categories'].get('note', [])) > 0,
                'web_port_count': len(snapshot['web_ports']),
                'smb_port_count': len(snapshot['smb_ports']),
                'service_count': len(snapshot['categories'].get('service', [])),
                'vuln_count': len(snapshot['categories'].get('vulnerability', [])),
                'cred_count': len(snapshot['categories'].get('credential', [])),
                # 状态感知（由 _get_snapshot 预计算）
                'has_vuln_unexploited': snapshot.get('has_vuln_unexploited', False),
                'vuln_unexploited_count': snapshot.get('vuln_unexploited_count', 0),
                'has_cred_new': snapshot.get('has_cred_new', False),
                'cred_new_count': snapshot.get('cred_new_count', 0),
                'has_exploited': snapshot.get('has_exploited', False),
                'exploited_count': snapshot.get('exploited_count', 0),
                'has_report_ready': snapshot.get('has_report_ready', False),
                'domain_entry_count': snapshot.get('domain_entry_count', 0),
            }
            return SafeConditionEvaluator.evaluate(condition, ctx)
        except Exception:
            return False

    def suggest(self, project_id: int) -> List[Dict]:
        """分析黑板状态，匹配规则，返回建议"""
        snapshot = self._get_snapshot(project_id)
        suggestions = []

        for rule in self.rules:
            if not rule.get('enabled', True):
                continue

            condition = rule.get('trigger', {}).get('condition', '')
            if not condition:
                continue

            if self._evaluate_condition(condition, snapshot):
                suggestion = rule.get('suggestion', {})
                suggestions.append({
                    'rule_id': rule.get('id', ''),
                    'name': rule.get('name', ''),
                    'priority': rule.get('priority', 'medium'),
                    'title': suggestion.get('title', ''),
                    'reason': suggestion.get('reason', ''),
                    'suggested_tool': suggestion.get('suggested_tool', ''),
                })

        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        suggestions.sort(key=lambda s: priority_order.get(s['priority'], 9))
        return suggestions

    def create_rule(self, rule_data: Dict) -> str:
        """新增规则"""
        rule_id = f"R{str(uuid.uuid4())[:6]}"
        rule = {
            'id': rule_id,
            'name': rule_data.get('name', ''),
            'category': rule_data.get('category', 'general'),
            'trigger': {'condition': rule_data.get('trigger_condition', 'False')},
            'suggestion': {
                'title': rule_data.get('suggestion_title', ''),
                'reason': rule_data.get('suggestion_reason', ''),
                'suggested_tool': rule_data.get('suggested_tool', ''),
            },
            'priority': rule_data.get('priority', 'medium'),
            'enabled': rule_data.get('enabled', True),
        }
        # 写入 YAML 文件
        fpath = os.path.join(self.rules_dir, 'custom_rules.yaml')
        existing = []
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                existing = yaml.safe_load(f) or []
        existing.append(rule)
        with open(fpath, 'w', encoding='utf-8') as f:
            yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)
        self.reload_rules()
        return rule_id

    def update_rule(self, rule_id: str, updates: Dict) -> bool:
        """更新规则，返回是否存在"""
        found = False
        for rule in self.rules:
            if rule.get('id') == rule_id:
                found = True
                if 'name' in updates:
                    rule['name'] = updates['name']
                if 'priority' in updates:
                    rule['priority'] = updates['priority']
                if 'enabled' in updates:
                    rule['enabled'] = updates['enabled']
                if 'trigger_condition' in updates:
                    rule.setdefault('trigger', {})['condition'] = updates['trigger_condition']
                if 'suggestion_title' in updates:
                    rule.setdefault('suggestion', {})['title'] = updates['suggestion_title']
                if 'suggestion_reason' in updates:
                    rule.setdefault('suggestion', {})['reason'] = updates['suggestion_reason']
                if 'suggested_tool' in updates:
                    rule.setdefault('suggestion', {})['suggested_tool'] = updates['suggested_tool']
                self._save_rule_to_file(rule)
                break
        if found:
            self.reload_rules()
        return found

    def delete_rule(self, rule_id: str) -> bool:
        """删除规则，返回是否存在"""
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.get('id') != rule_id]
        if len(self.rules) == before:
            return False
        self._save_all_rules()
        self.reload_rules()
        return True

    def toggle_rule(self, rule_id: str) -> bool:
        """启用/禁用规则，返回是否存在"""
        found = False
        for rule in self.rules:
            if rule.get('id') == rule_id:
                rule['enabled'] = not rule.get('enabled', True)
                self._save_rule_to_file(rule)
                found = True
                break
        if found:
            self.reload_rules()
        return found

    def _save_rule_to_file(self, rule: Dict):
        """将单条规则写回对应文件"""
        fname = rule.get('_file', 'custom_rules.yaml')
        fpath = os.path.join(self.rules_dir, fname)
        # 重读该文件，替换对应规则
        existing = []
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                existing = yaml.safe_load(f) or []
        for i, r in enumerate(existing):
            if r.get('id') == rule.get('id'):
                existing[i] = {k: v for k, v in rule.items() if not k.startswith('_')}
                break
        with open(fpath, 'w', encoding='utf-8') as f:
            yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)

    def _save_all_rules(self):
        """重建所有规则文件（保留空的内置文件，不删除磁盘上的规则文件）"""
        by_file = {}
        for rule in self.rules:
            fname = rule.get('_file', 'custom_rules.yaml')
            if fname not in by_file:
                by_file[fname] = []
            by_file[fname].append({k: v for k, v in rule.items() if not k.startswith('_')})
        # 合并磁盘上已有的规则文件名（即使规则删光也保留文件占位）
        if os.path.exists(self.rules_dir):
            for fname in os.listdir(self.rules_dir):
                if (fname.endswith('.yaml') or fname.endswith('.yml')) and fname not in by_file:
                    by_file[fname] = []
        # 写入（含空列表也写出，避免误删内置文件）
        for fname, rules in by_file.items():
            fpath = os.path.join(self.rules_dir, fname)
            with open(fpath, 'w', encoding='utf-8') as f:
                yaml.dump(rules, f, allow_unicode=True, default_flow_style=False)
