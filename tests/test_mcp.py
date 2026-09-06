# -*- coding: utf-8 -*-
"""MCP mount + token gate smoke test"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('REDTEAM_DEBUG', '0')
from app import app
from fastapi.testclient import TestClient
from core.security import get_or_create_token

print('MCP_ENABLED =', app.state if hasattr(app,'state') else '?')

client = TestClient(app)
# /mcp without token -> 401
r = client.get('/mcp/sse')
print('no token /mcp/sse ->', r.status_code)
assert r.status_code == 401, r.text[:200]

tok = get_or_create_token()['token']
r = client.get('/mcp/sse', headers={'Authorization': f'Bearer {tok}'})
print('with token /mcp/sse ->', r.status_code, r.headers.get('content-type'))
# SSE endpoint should upgrade (not 401); tolerate 200/404 depending transport
assert r.status_code != 401

# normal API unaffected
r2 = client.post('/api/auth/login', json={'username':'admin','password':'admin123'})
assert r2.status_code == 200
print('MCP GATE OK')
