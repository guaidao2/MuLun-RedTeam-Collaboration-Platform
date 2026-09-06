# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - FastAPI 入口
python app.py 启动
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (SERVER_HOST, SERVER_PORT, TEMPLATES_DIR, STATIC_DIR, DATA_DIR,
                    UPLOAD_DIR, REPORTS_DIR, DEBUG, JWT_SECRET)

# 创建数据目录
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# 初始化数据库
from core.models import init_db
init_db()
# 确保初始 API Token 已生成
from core.security import get_or_create_token
get_or_create_token()
# 可选：首次部署用 REDTEAM_ADMIN_PASSWORD 覆盖默认 admin 口令（仅内存，不写文件）
import config as _cfg
_env_pw = os.environ.get('REDTEAM_ADMIN_PASSWORD')
if _env_pw and 'admin' in _cfg.USERS:
    _cfg.USERS['admin'] = _env_pw
    print("[安全] 已通过 REDTEAM_ADMIN_PASSWORD 覆盖 admin 口令")

# 创建 FastAPI 应用
app = FastAPI(title="幕论红队协同平台", version="1.0.0")

# 静态文件
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 模板
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# 注册路由
from api.auth import router as auth_router
from api.projects import router as projects_router
from api.blackboard import router as blackboard_router
from api.attack_graph import router as attack_graph_router
from api.import_data import router as import_router
from api.suggestions import router as suggestions_router
from api.rules import router as rules_router
from api.system import router as system_router
from api.pages import router as pages_router
from api.report import router as report_router
from api.privesc import router as privesc_router

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(blackboard_router)
app.include_router(attack_graph_router)
app.include_router(import_router)
app.include_router(suggestions_router)
app.include_router(rules_router)
app.include_router(system_router)
app.include_router(report_router)
app.include_router(privesc_router)
app.include_router(pages_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "幕论红队协同平台"}


# ==================== MCP 端点（挂载 /mcp，平台 Token 门卫）====================
from core.security import verify_token, get_or_create_token


def _extract_token(request: Request):
    auth = request.headers.get('authorization', '')
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    xk = request.headers.get('x-api-key')
    if xk:
        return xk.strip()
    return None


@app.middleware('http')
async def mcp_token_gate(request: Request, call_next):
    if request.url.path.startswith('/mcp'):
        tok = _extract_token(request)
        if not tok or not verify_token(tok):
            return JSONResponse(status_code=401, content={'detail': '无效的平台 API Token'})
    return await call_next(request)


_mcp_app_ref = None
_mcp_task = None


def setup_mcp():
    """构建并挂载 MCP HTTP/SSE 端点"""
    global _mcp_app_ref
    from rt_mcp import build_mcp_app
    try:
        mcp_app = build_mcp_app()
        app.mount('/mcp', mcp_app, name='mcp')
        _mcp_app_ref = mcp_app
        return True
    except Exception as e:
        import logging
        logging.getLogger('mcp').exception('MCP mount failed: %s', e)
        return False


MCP_ENABLED = setup_mcp()


@app.on_event("startup")
async def _start_mcp_lifespan():
    """挂载的 FastMCP Starlette 需自行运行其 lifespan（session manager）"""
    global _mcp_task
    if not _mcp_app_ref:
        return
    import asyncio

    async def _run():
        async with _mcp_app_ref.router.lifespan_context(_mcp_app_ref):
            await asyncio.Event().wait()   # 保持存活直到关闭

    _mcp_task = asyncio.create_task(_run())


@app.on_event("shutdown")
async def _stop_mcp_lifespan():
    global _mcp_task
    if _mcp_task:
        _mcp_task.cancel()
        _mcp_task = None


if __name__ == '__main__':
    # 安全护栏：使用默认/未显式设置密钥时，一律只监听 127.0.0.1（与 DEBUG 无关）
    host = SERVER_HOST
    if JWT_SECRET == 'redteam-platform-secret-key-change-in-production':
        print("[安全] 未设置 REDTEAM_JWT_SECRET，已强制仅监听 127.0.0.1。")
        print("      局域网/公网部署请设置: REDTEAM_JWT_SECRET=<强随机值>")
        host = '127.0.0.1'
    uvicorn.run("app:app", host=host, port=SERVER_PORT, reload=DEBUG)
