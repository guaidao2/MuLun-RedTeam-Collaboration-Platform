# -*- coding: utf-8 -*-
"""端到端综合测试：覆盖所有修复点"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('REDTEAM_DEBUG', '0')
from app import app
from fastapi.testclient import TestClient
from core.state_machine import SafeConditionEvaluator

# 默认仅 admin；动态注入一个临时用户用于越权/成员测试
import config as _cfg
_cfg.USERS['laoli'] = 'li123'

client = TestClient(app)

# 1. 登录
r = client.post('/api/auth/login', json={'username':'admin','password':'admin123'})
assert r.status_code == 200
H = {'Authorization': f"Bearer {r.json()['access_token']}"}
r2 = client.post('/api/auth/login', json={'username':'laoli','password':'li123'})
H2 = {'Authorization': f"Bearer {r2.json()['access_token']}"}

# 2. 项目 CRUD
r = client.post('/api/projects', headers=H, json={'name':'e2e','description':'测试'})
pid = r.json()['data']['id']
# 3. 越权：laoli 非成员访问 403
assert client.get(f'/api/projects/{pid}', headers=H2).status_code == 403
# laoli 不能自行加入（self-join 已关闭）
assert client.post(f'/api/projects/{pid}/join', headers=H2).status_code == 403
# owner 添加 laoli 为成员后可访问
assert client.post(f'/api/projects/{pid}/members', headers=H, json={'username':'laoli'}).status_code == 200
assert client.get(f'/api/projects/{pid}', headers=H2).status_code == 200
# laoli 不是 owner 不能改/删
assert client.put(f'/api/projects/{pid}', headers=H2, json={'name':'x'}).status_code == 403
assert client.delete(f'/api/projects/{pid}', headers=H2).status_code == 403
# owner 移除 laoli 后 403
assert client.delete(f'/api/projects/{pid}/members/laoli', headers=H).status_code == 200
assert client.get(f'/api/projects/{pid}', headers=H2).status_code == 403
# 重新加回供后续测试
client.post(f'/api/projects/{pid}/members', headers=H, json={'username':'laoli'})

# 4. 目标 + 删除
tid = client.post(f'/api/projects/{pid}/targets', headers=H, json={'ip':'10.0.0.1'}).json()['data']['id']
assert client.delete(f'/api/projects/{pid}/targets/{tid}', headers=H).status_code == 200

# 5. 条目结构化字段 + 状态机 + 回退拒绝
tid = client.post(f'/api/projects/{pid}/targets', headers=H, json={'ip':'10.0.0.2'}).json()['data']['id']
e1 = client.post(f'/api/projects/{pid}/entries', headers=H,
                 json={'category':'service','title':'iis','content':{'port':80,'service':'IIS'},'target_id':tid,'status':'confirmed'}).json()['data']['id']
e2 = client.post(f'/api/projects/{pid}/entries', headers=H,
                 json={'category':'vulnerability','title':'SQLi','content':{'name':'SQLi','severity':'high'},'target_id':tid,'status':'exploited'}).json()['data']['id']
e3 = client.post(f'/api/projects/{pid}/entries', headers=H,
                 json={'category':'credential','title':'sa','content':{'username':'sa'},'target_id':tid}).json()['data']['id']
# 回退拒绝
assert client.patch(f'/api/projects/{pid}/entries/{e1}/status', headers=H, json={'status':'new'}).status_code == 400
# 非法类别/状态
assert client.post(f'/api/projects/{pid}/entries', headers=H, json={'category':'hack','title':'x','content':{}}).status_code == 400
# target_id 编辑 (H5)
assert client.put(f'/api/projects/{pid}/entries/{e3}', headers=H, json={'target_id':None}).status_code == 200

# 6. 攻击图连线
ed = client.post(f'/api/projects/{pid}/graph/edges', headers=H,
                 json={'from_entry_id':e1,'to_entry_id':e2,'label':'打'}).json()['data']['id']
g = client.get(f'/api/projects/{pid}/graph', headers=H).json()['data']
assert len(g['edges']) == 1
# 越权删边: laoli 已加入 可以删(成员), 删除成功
assert client.delete(f'/api/projects/{pid}/graph/edges/{ed}', headers=H2).status_code == 200

# 7. 建议
s = client.get(f'/api/projects/{pid}/suggestions', headers=H).json()
assert 'summary' in s

# 7b. 规则安全：非法 priority 拒绝、超深嵌套拒绝、新状态 key 可用
assert client.post('/api/rules', headers=H, json={
    'name':'x','category':'service','priority':'javascript:alert(1)',
    'suggestion_title':'t','trigger_condition':'has_target'}).status_code == 400
assert client.post('/api/rules', headers=H, json={
    'name':'x','category':'service','priority':'high','suggestion_title':'t',
    'trigger_condition':'('*60 + 'has_target'}).status_code == 400
r = client.post('/api/rules', headers=H, json={
    'name':'x','category':'general','priority':'low','suggestion_title':'t',
    'trigger_condition':'has_report_ready'})
assert r.status_code == 200, r.text
rid = r.json()['data']['id']
assert client.delete(f'/api/rules/{rid}', headers=H).status_code == 200

# 规则语法校验接口
assert client.post('/api/rules/validate', headers=H,
                   json={'condition':'has_vuln_unexploited and vuln_count > 0'}).json()['ok'] is True
assert client.post('/api/rules/validate', headers=H,
                   json={'condition':"__import__('os').system('id')"}).json()['ok'] is False
assert client.post('/api/rules/validate', headers=H,
                   json={'condition':'unknown_var > 1'}).json()['ok'] is False
meta = client.get('/api/rules/meta', headers=H).json()
assert 'has_report_ready' in [v['name'] for v in meta['variables']]
assert 'and' in meta['operators']
# IP 注入校验
assert client.post(f'/api/projects/{pid}/targets', headers=H,
                   json={'ip':'"><script>alert(1)</script>'}).status_code == 400

# 7c. 非 admin (laoli) 不能改规则；admin 改密注入字符被拒
assert client.post('/api/rules', headers=H2, json={
    'name':'x','category':'service','priority':'high','suggestion_title':'t',
    'trigger_condition':'has_target'}).status_code == 403
assert client.put('/api/me/password', headers=H,
                  json={'old_password':'admin123','new_password':'x\", \"admin\": \"evil'}).status_code == 400

# 7d. 平台 Token：仅 admin 可见；刷新后旧 token 失效
assert client.get('/api/platform/token', headers=H2).status_code == 403
tok0 = client.get('/api/platform/token', headers=H).json()['data']['token']
assert tok0
tok1 = client.post('/api/platform/token/refresh', headers=H).json()['data']['token']
assert tok1 != tok0
from core.security import verify_token
assert verify_token(tok0) is False
assert verify_token(tok1) is True

# 8. 报告 + 提权
assert client.get(f'/api/projects/{pid}/report', headers=H).status_code == 200
pv = client.post('/api/privilege-escalation/analyze', headers=H, json={'text':'-rwsr-xr-x /usr/bin/find'})
assert pv.status_code == 200 and len(pv.json()['data']) > 0

# 9. 条目删除级联
assert client.delete(f'/api/projects/{pid}/entries/{e2}', headers=H).status_code == 200

# 10. 清理项目(owner)
assert client.delete(f'/api/projects/{pid}', headers=H).status_code == 200

print('ALL E2E TESTS PASSED')
