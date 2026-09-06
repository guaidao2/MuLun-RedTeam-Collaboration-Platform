# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 攻击图 API
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from core.models import AttackEdge, BlackboardEntry
from api.auth import get_current_user
from api.authz import require_project_member

router = APIRouter(prefix="/api/projects/{project_id}/graph", tags=["attack_graph"])

# 攻击图层级定义
CATEGORY_LEVELS = {
    "asset": 0,
    "service": 1,
    "vulnerability": 2,
    "credential": 3,
    "task": 4,
    "note": 4,
}


class EdgeCreate(BaseModel):
    from_entry_id: int
    to_entry_id: int
    label: str = ""


@router.get("")
def get_graph(project_id: int, user: str = Depends(require_project_member)):
    """获取攻击图数据（节点 + 边）"""
    # 获取所有条目作为节点
    entries = BlackboardEntry.get_by_project(project_id)

    nodes = []
    for entry in entries:
        level = CATEGORY_LEVELS.get(entry['category'], 2)
        nodes.append({
            "id": entry['id'],
            "label": entry['title'],
            "category": entry['category'],
            "status": entry['status'],
            "author": entry['author'],
            "level": level,
            "content": entry['content'],
            "target_id": entry['target_id'],
        })

    # 获取所有边
    edges = AttackEdge.get_by_project(project_id)
    edge_list = []
    for edge in edges:
        edge_list.append({
            "id": edge['id'],
            "from": edge['from_entry_id'],
            "to": edge['to_entry_id'],
            "label": edge['label'],
            "created_by": edge['created_by'],
        })

    return {
        "success": True,
        "data": {
            "nodes": nodes,
            "edges": edge_list,
        }
    }


@router.post("/edges")
def add_edge(project_id: int, req: EdgeCreate, user: str = Depends(require_project_member)):
    """添加攻击图边（人手动连线）"""
    # 验证节点存在且属于该项目（防跨项目引用）
    from_entry = BlackboardEntry.get_by_id(req.from_entry_id)
    to_entry = BlackboardEntry.get_by_id(req.to_entry_id)
    if not from_entry or not to_entry:
        raise HTTPException(status_code=404, detail="节点不存在")
    if from_entry['project_id'] != project_id or to_entry['project_id'] != project_id:
        raise HTTPException(status_code=403, detail="节点不属于该项目")
    if from_entry['id'] == to_entry['id']:
        raise HTTPException(status_code=400, detail="不能连接节点自身")

    edge_id = AttackEdge.create(
        project_id, req.from_entry_id, req.to_entry_id, req.label, user
    )
    return {"success": True, "data": {"id": edge_id}}


@router.delete("/edges/{edge_id}")
def delete_edge(project_id: int, edge_id: int, user: str = Depends(require_project_member)):
    """删除攻击图边"""
    # 验证边属于该项目
    edges = AttackEdge.get_by_project(project_id)
    edge_ids = [e['id'] for e in edges]
    if edge_id not in edge_ids:
        raise HTTPException(status_code=403, detail="无权访问该边")
    AttackEdge.delete(edge_id)
    return {"success": True}
