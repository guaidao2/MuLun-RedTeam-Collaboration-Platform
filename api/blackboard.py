# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 黑板条目 API
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from core.models import BlackboardEntry, Target
from api.auth import get_current_user
from api.authz import require_project_member

import re

router = APIRouter(prefix="/api/projects/{project_id}", tags=["blackboard"])

# IP 或主机名：仅允许数字/字母/点/横线/下划线/冒号，杜绝 HTML 注入字符
_TARGET_CHARS = re.compile(r'^[0-9a-zA-Z.\-_:]+$')


def _validate_target_ip(ip: str):
    if not ip or not _TARGET_CHARS.match(ip):
        raise HTTPException(status_code=400, detail="非法目标地址格式")

# 合法值枚举
VALID_CATEGORIES = {'asset', 'service', 'vulnerability', 'credential', 'task', 'note'}
VALID_STATUSES = {'new', 'confirmed', 'exploited', 'fixed'}
STATUS_ORDER = {'new': 0, 'confirmed': 1, 'exploited': 2, 'fixed': 3}


class EntryCreate(BaseModel):
    category: str
    title: str
    content: dict
    target_id: Optional[int] = None
    status: str = "new"


class EntryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[dict] = None
    status: Optional[str] = None
    category: Optional[str] = None
    target_id: Optional[int] = None


class StatusUpdate(BaseModel):
    status: str


class TargetCreate(BaseModel):
    ip: str
    hostname: Optional[str] = None
    os: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None


def _validate_entry(category: str, status: str, content: dict = None):
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400,
                            detail=f"非法类别: {category}，可选 {sorted(VALID_CATEGORIES)}")
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400,
                            detail=f"非法状态: {status}，可选 {sorted(VALID_STATUSES)}")


def _validate_target_belongs(project_id: int, target_id: int):
    if target_id is None:
        return
    target = Target.get_by_id(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="目标不存在")
    if target['project_id'] != project_id:
        raise HTTPException(status_code=403, detail="目标不属于该项目")


# ==================== 目标 ====================

@router.get("/targets")
def list_targets(project_id: int, user: str = Depends(require_project_member)):
    targets = Target.get_by_project(project_id)
    return {"success": True, "data": targets}


@router.post("/targets")
def create_target(project_id: int, req: TargetCreate, user: str = Depends(require_project_member)):
    _validate_target_ip(req.ip)
    target_id = Target.create(project_id, req.ip, req.hostname, req.os, req.description, req.tags)
    return {"success": True, "data": {"id": target_id}}


@router.delete("/targets/{target_id}")
def delete_target(project_id: int, target_id: int, user: str = Depends(require_project_member)):
    target = Target.get_by_id(target_id)
    if not target:
        raise HTTPException(status_code=404, detail="目标不存在")
    if target['project_id'] != project_id:
        raise HTTPException(status_code=403, detail="无权访问该目标")
    # 级联删除该目标下的条目及关联边
    if not Target.delete_cascade(project_id, target_id):
        raise HTTPException(status_code=500, detail="删除目标失败")
    return {"success": True}


# ==================== 黑板条目 ====================

@router.get("/entries")
def list_entries(project_id: int, category: str = None, target_id: int = None,
                 status: str = None, user: str = Depends(require_project_member)):
    entries = BlackboardEntry.get_by_project(project_id, category, target_id, status)
    return {"success": True, "data": entries}


@router.post("/entries")
def create_entry(project_id: int, req: EntryCreate, user: str = Depends(require_project_member)):
    _validate_entry(req.category, req.status, req.content)
    _validate_target_belongs(project_id, req.target_id)
    entry_id = BlackboardEntry.create(
        project_id, user, req.category, req.title, req.content, req.target_id, req.status
    )
    return {"success": True, "data": {"id": entry_id}}


@router.get("/entries/{entry_id}")
def get_entry(project_id: int, entry_id: int, user: str = Depends(require_project_member)):
    entry = BlackboardEntry.get_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    if entry['project_id'] != project_id:
        raise HTTPException(status_code=403, detail="无权访问该条目")
    return {"success": True, "data": entry}


@router.put("/entries/{entry_id}")
def update_entry(project_id: int, entry_id: int, req: EntryUpdate,
                 user: str = Depends(require_project_member)):
    entry = BlackboardEntry.get_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    if entry['project_id'] != project_id:
        raise HTTPException(status_code=403, detail="无权访问该条目")

    # 校验类别/状态
    new_category = req.category or entry['category']
    new_status = req.status or entry['status']
    _validate_entry(new_category, new_status)
    # 校验目标归属
    if 'target_id' in req.dict() and req.target_id is not None:
        _validate_target_belongs(project_id, req.target_id)

    kwargs = {k: v for k, v in req.dict().items() if v is not None}
    BlackboardEntry.update(entry_id, **kwargs)
    return {"success": True}


@router.patch("/entries/{entry_id}/status")
def update_entry_status(project_id: int, entry_id: int, req: StatusUpdate,
                        user: str = Depends(require_project_member)):
    entry = BlackboardEntry.get_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    if entry['project_id'] != project_id:
        raise HTTPException(status_code=403, detail="无权访问该条目")
    # 只允许向前流转
    if STATUS_ORDER.get(req.status, -1) < STATUS_ORDER.get(entry['status'], 0):
        raise HTTPException(status_code=400,
                            detail=f"状态不能回退: {entry['status']} → {req.status}")
    if req.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"非法状态: {req.status}")
    BlackboardEntry.update_status(entry_id, req.status)
    return {"success": True}


@router.delete("/entries/{entry_id}")
def delete_entry(project_id: int, entry_id: int, user: str = Depends(require_project_member)):
    entry = BlackboardEntry.get_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    if entry['project_id'] != project_id:
        raise HTTPException(status_code=403, detail="无权访问该条目")
    # 先删除关联的边再删条目
    if not BlackboardEntry.delete_cascade(project_id, entry_id):
        raise HTTPException(status_code=500, detail="删除条目失败")
    return {"success": True}
