# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 规则管理 API
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

from api.auth import get_current_user
from api.authz import require_admin
from core.state_machine import StateMachine, SafeConditionEvaluator

router = APIRouter(prefix="/api/rules", tags=["rules"])

sm = StateMachine()


VALID_PRIORITIES = {'high', 'medium', 'low'}
VALID_CATEGORIES = {'service', 'vulnerability', 'credential', 'lateral', 'general'}

# 前端帮助/校验用：条件里可用变量的说明
RULE_VARS = [
    {'name': 'target_count', 'type': 'int', 'desc': '目标数量'},
    {'name': 'has_target', 'type': 'bool', 'desc': '是否有目标'},
    {'name': 'entry_count', 'type': 'int', 'desc': '黑板条目总数'},
    {'name': 'has_entries', 'type': 'bool', 'desc': '是否有任何条目'},
    {'name': 'service_count', 'type': 'int', 'desc': '服务条目数'},
    {'name': 'has_service', 'type': 'bool', 'desc': '是否存在服务发现'},
    {'name': 'vuln_count', 'type': 'int', 'desc': '漏洞条目数'},
    {'name': 'has_vuln', 'type': 'bool', 'desc': '是否存在漏洞'},
    {'name': 'vuln_unexploited_count', 'type': 'int', 'desc': '尚未标记已利用的漏洞数'},
    {'name': 'has_vuln_unexploited', 'type': 'bool', 'desc': '是否存在未利用漏洞'},
    {'name': 'cred_count', 'type': 'int', 'desc': '凭据条目数'},
    {'name': 'has_credential', 'type': 'bool', 'desc': '是否存在凭据'},
    {'name': 'cred_new_count', 'type': 'int', 'desc': '状态为 new 的凭据数'},
    {'name': 'has_cred_new', 'type': 'bool', 'desc': '是否存在待验证凭据'},
    {'name': 'has_task', 'type': 'bool', 'desc': '是否有任务条目'},
    {'name': 'has_note', 'type': 'bool', 'desc': '是否有备注条目'},
    {'name': 'web_port_count', 'type': 'int', 'desc': 'Web 端口(80/443/8080…)数'},
    {'name': 'smb_port_count', 'type': 'int', 'desc': 'SMB/445 端口数'},
    {'name': 'exploited_count', 'type': 'int', 'desc': '已利用状态条目数'},
    {'name': 'has_exploited', 'type': 'bool', 'desc': '是否存在已利用条目'},
    {'name': 'domain_entry_count', 'type': 'int', 'desc': '域相关信息条目数'},
    {'name': 'has_report_ready', 'type': 'bool', 'desc': '是否已有可利用成果(可出报告)'},
]
RULE_OPERATORS = ['and', 'or', 'not', '==', '!=', '>', '<', '>=', '<=', '(', ')']

# 条件校验用的完整上下文（与 SafeConditionEvaluator.IDENT_WHITELIST 同步）
_COND_CTX = {
    'target_count': 0, 'has_target': False, 'entry_count': 0,
    'has_entries': False, 'has_service': False, 'has_vuln': False,
    'has_credential': False, 'has_task': False, 'has_note': False,
    'web_port_count': 0, 'smb_port_count': 0,
    'service_count': 0, 'vuln_count': 0, 'cred_count': 0,
    'has_vuln_unexploited': False, 'vuln_unexploited_count': 0,
    'has_cred_new': False, 'cred_new_count': 0,
    'has_exploited': False, 'exploited_count': 0,
    'has_report_ready': False, 'domain_entry_count': 0,
}


def _validate_condition(condition: str):
    """校验规则条件表达式是否合法（白名单，无 eval）"""
    if not condition or not condition.strip():
        raise HTTPException(status_code=400, detail="触发条件不能为空")
    try:
        SafeConditionEvaluator.evaluate(condition, _COND_CTX)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"条件表达式非法: {e}")


def _validate_meta(name: str, category: str, priority: str):
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400,
                            detail=f"非法类别: {category}，可选 {sorted(VALID_CATEGORIES)}")
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400,
                            detail=f"非法优先级: {priority}，可选 {sorted(VALID_PRIORITIES)}")


class RuleCreate(BaseModel):
    name: str
    category: str
    trigger_condition: str
    suggestion_title: str
    suggestion_reason: str = ""
    suggested_tool: str = ""
    priority: str = "medium"
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    trigger_condition: Optional[str] = None
    suggestion_title: Optional[str] = None
    suggestion_reason: Optional[str] = None
    suggested_tool: Optional[str] = None
    priority: Optional[str] = None
    enabled: Optional[bool] = None


class RuleValidate(BaseModel):
    condition: str


@router.post("/validate")
def validate_condition(req: RuleValidate, user: str = Depends(get_current_user)):
    """前端实时校验规则条件语法（返回 ok/error，不抛异常）"""
    if not req.condition or not req.condition.strip():
        return {"ok": False, "error": "触发条件不能为空"}
    try:
        SafeConditionEvaluator.evaluate(req.condition, _COND_CTX)
        return {"ok": True, "error": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/meta")
def rule_meta(user: str = Depends(get_current_user)):
    """规则编写帮助元信息（变量/运算符/枚举）"""
    return {
        "variables": RULE_VARS,
        "operators": RULE_OPERATORS,
        "categories": sorted(VALID_CATEGORIES),
        "priorities": sorted(VALID_PRIORITIES),
    }


@router.get("")
def list_rules(user: str = Depends(get_current_user)):
    """获取所有规则"""
    rules = sm.get_all_rules()
    return {"success": True, "data": rules}


@router.post("")
def create_rule(req: RuleCreate, user: str = Depends(require_admin)):
    """新增规则"""
    _validate_meta(req.name, req.category, req.priority)
    _validate_condition(req.trigger_condition)
    rule_id = sm.create_rule(req.dict())
    return {"success": True, "data": {"id": rule_id}}


@router.put("/{rule_id}")
def update_rule(rule_id: str, req: RuleUpdate, user: str = Depends(require_admin)):
    """更新规则"""
    if req.category and req.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="非法类别")
    if req.priority and req.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="非法优先级")
    if req.trigger_condition:
        _validate_condition(req.trigger_condition)
    kwargs = {k: v for k, v in req.dict().items() if v is not None}
    updated = sm.update_rule(rule_id, kwargs)
    if not updated:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"success": True}


@router.delete("/{rule_id}")
def delete_rule(rule_id: str, user: str = Depends(require_admin)):
    """删除规则"""
    deleted = sm.delete_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"success": True}


@router.patch("/{rule_id}/toggle")
def toggle_rule(rule_id: str, user: str = Depends(require_admin)):
    """启用/禁用规则"""
    toggled = sm.toggle_rule(rule_id)
    if not toggled:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"success": True}


@router.post("/reload")
def reload_rules(user: str = Depends(require_admin)):
    """手动触发规则热重载"""
    sm.reload_rules()
    return {"success": True, "message": "规则已重载"}
