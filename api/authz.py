# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 授权模块
项目成员/owner 鉴权依赖
"""

from fastapi import HTTPException, Depends, Path

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ADMIN_USERS

from api.auth import get_current_user
from core.models import Project


def require_admin(user: str = Depends(get_current_user)) -> str:
    """要求调用者是平台管理员（修改全局规则/平台 Token 等）"""
    if user not in ADMIN_USERS:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def require_project_member(project_id: int = Path(...),
                           user: str = Depends(get_current_user)) -> str:
    """要求调用者是项目成员（读操作）；平台管理员可访问任意项目"""
    project = Project.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if user in ADMIN_USERS:
        return user
    if not Project.is_member(project_id, user):
        raise HTTPException(status_code=403, detail="无权访问该项目")
    return user


def require_project_owner(project_id: int = Path(...),
                          user: str = Depends(get_current_user)) -> str:
    """要求调用者是项目 owner（写操作）；平台管理员视为 owner"""
    project = Project.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if user in ADMIN_USERS:
        return user
    if not Project.is_owner(project_id, user):
        raise HTTPException(status_code=403, detail="只有项目创建者可执行此操作")
    return user
