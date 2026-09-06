# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 报告 API
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse

from api.authz import require_project_member
from modules.report_generator import generate_html_report

router = APIRouter(prefix="/api/projects/{project_id}", tags=["report"])


@router.get("/report", response_class=HTMLResponse)
def get_report(project_id: int, user: str = Depends(require_project_member)):
    """生成并返回 HTML 报告"""
    try:
        html = generate_html_report(project_id)
    except Exception:
        raise HTTPException(status_code=500, detail="生成报告失败，请稍后重试")
    return HTMLResponse(content=html)
