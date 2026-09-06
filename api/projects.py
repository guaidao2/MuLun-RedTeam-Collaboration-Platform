# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 项目 API
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from core.models import Project
from api.auth import get_current_user
from api.authz import require_project_member, require_project_owner

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@router.get("")
def list_projects(user: str = Depends(get_current_user)):
    """获取当前用户参与的项目列表"""
    projects = Project.get_by_user(user)
    for p in projects:
        p['stats'] = Project.get_stats(p['id'])
    return {"success": True, "data": projects}


@router.post("")
def create_project(req: ProjectCreate, user: str = Depends(get_current_user)):
    """创建项目"""
    project_id = Project.create(req.name, req.description, user)
    return {"success": True, "data": {"id": project_id}}


@router.get("/{project_id}")
def get_project(project_id: int, user: str = Depends(require_project_member)):
    """获取项目详情（需成员）"""
    project = Project.get_by_id(project_id)
    project['members'] = Project.get_members(project_id)
    project['stats'] = Project.get_stats(project_id)
    project['is_owner'] = (project['owner'] == user)
    return {"success": True, "data": project}


@router.put("/{project_id}")
def update_project(project_id: int, req: ProjectUpdate,
                   user: str = Depends(require_project_owner)):
    """更新项目（需 owner）"""
    kwargs = {k: v for k, v in req.dict().items() if v is not None}
    Project.update(project_id, **kwargs)
    return {"success": True}


@router.delete("/{project_id}")
def delete_project(project_id: int, user: str = Depends(require_project_owner)):
    """删除项目（需 owner）"""
    Project.delete(project_id)
    return {"success": True}


class MemberAdd(BaseModel):
    username: str


@router.post("/{project_id}/join")
def join_project(project_id: int, user: str = Depends(get_current_user)):
    """加入项目（需项目创建者审核；此处仅对已存在成员幂等返回）"""
    project = Project.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 禁止任意用户自行加入：非成员一律 403，由 owner 通过 /members 添加
    raise HTTPException(status_code=403,
                        detail="需由项目创建者添加成员，不能自行加入")


@router.post("/{project_id}/members")
def add_member(project_id: int, req: MemberAdd,
               user: str = Depends(require_project_owner)):
    """添加成员（需 owner）"""
    from config import USERS
    if req.username not in USERS:
        raise HTTPException(status_code=404, detail="用户不存在")
    Project.add_member(project_id, req.username)
    return {"success": True}


@router.delete("/{project_id}/members/{username}")
def remove_member(project_id: int, username: str,
                  user: str = Depends(require_project_owner)):
    """移除成员（需 owner，不能移除自己）"""
    if username == user:
        raise HTTPException(status_code=400, detail="不能移除自己")
    if not Project.is_member(project_id, username):
        raise HTTPException(status_code=404, detail="该用户不是项目成员")
    Project.remove_member(project_id, username)
    return {"success": True}
