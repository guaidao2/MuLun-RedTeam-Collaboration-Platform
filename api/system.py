# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 系统 API
"""

import json
import re

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from api.auth import get_current_user
from api.authz import require_admin
from core.security import get_or_create_token, rotate_token

router = APIRouter(prefix="/api", tags=["system"])

# 密码仅允许安全字符集，禁止引号/反斜杠/换行等可破坏 config.py 字面量的字符
_PW_ALLOW = re.compile(r'^[A-Za-z0-9@#!$%^&*_\-+.=?~]{6,64}$')


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


@router.get("/me")
def get_me(user: str = Depends(get_current_user)):
    """获取当前用户信息"""
    return {"success": True, "data": {"username": user, "is_admin": user in config.ADMIN_USERS}}


@router.get("/platform/token")
def view_token(user: str = Depends(require_admin)):
    """查看平台 API Token（仅管理员）。初始随机 token 永久有效，除非手动刷新"""
    data = get_or_create_token()
    return {"success": True, "data": data}


@router.post("/platform/token/refresh")
def refresh_token(user: str = Depends(require_admin)):
    """手动刷新平台 API Token（仅管理员，旧 token 立即失效）"""
    data = rotate_token()
    return {"success": True, "data": data, "message": "Token 已刷新，旧 Token 立即失效"}


@router.put("/me/password")
def change_password(req: PasswordChange, user: str = Depends(get_current_user)):
    """修改当前用户密码（写入 config.py）"""
    current = config.USERS.get(user)
    if current is None:
        raise HTTPException(status_code=500, detail="配置文件中未找到该用户")
    if current != req.old_password:
        raise HTTPException(status_code=400, detail="当前密码错误")
    if not _PW_ALLOW.match(req.new_password):
        raise HTTPException(status_code=400,
                            detail="新密码需 6-64 位，且仅含字母数字及 @#!$%^&*_-+.=?~ 等安全字符")

    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.py')
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 用 json.dumps 转义为新值（JSON 字符串字面量与 Python 兼容，杜绝注入破坏源文件）
    new_literal = json.dumps(req.new_password, ensure_ascii=False)
    old_pattern = rf'("{re.escape(user)}":\s*")[^"]*(")'
    if not re.search(old_pattern, content):
        raise HTTPException(status_code=500, detail="配置文件中未找到该用户")
    new_content = re.sub(old_pattern, rf'\g<1>{new_literal[1:-1]}\2', content)

    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    config.USERS[user] = req.new_password
    return {"success": True, "message": "密码已更新"}
