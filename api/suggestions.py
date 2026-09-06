# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 状态机建议 API
"""

from fastapi import APIRouter, Depends

from api.authz import require_project_member

router = APIRouter(prefix="/api/projects/{project_id}", tags=["suggestions"])

# 复用 rules.py 中的 StateMachine 实例，避免重复加载
from api.rules import sm


@router.get("/suggestions")
def get_suggestions(project_id: int, user: str = Depends(require_project_member)):
    """获取下一步作战建议（只读）"""
    suggestions = sm.suggest(project_id)
    prio_map = {'high': 0, 'medium': 1, 'low': 2}
    summary = {
        'total': len(suggestions),
        'high': sum(1 for s in suggestions if s['priority'] == 'high'),
        'medium': sum(1 for s in suggestions if s['priority'] == 'medium'),
        'low': sum(1 for s in suggestions if s['priority'] == 'low'),
    }
    return {"success": True, "data": suggestions, "summary": summary}
