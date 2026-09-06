# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 认证模块
JWT 登录，用户存在 config.py
"""

from datetime import datetime, timedelta
from typing import Optional

import secrets

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import USERS, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

# 简易登录限速：每用户名每分钟最多 8 次尝试
_attempts = {}  # username -> [timestamps]
_MAX_ATTEMPTS = 8
_WINDOW = 60


def _check_rate_limit(username: str):
    import time
    now = time.time()
    ts = [t for t in _attempts.get(username, []) if now - t < _WINDOW]
    if len(ts) >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="尝试过于频繁，请稍后再试")
    ts.append(now)
    _attempts[username] = ts


def _clear_rate_limit(username: str):
    _attempts.pop(username, None)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


def create_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """从 JWT token 中提取当前用户名"""
    if not credentials:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="无效的token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="token已过期或无效")


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """登录"""
    _check_rate_limit(req.username)
    password = USERS.get(req.username)
    ok = password is not None and secrets.compare_digest(
        password.encode('utf-8'), req.password.encode('utf-8'))
    if not ok:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    _clear_rate_limit(req.username)
    token = create_token(req.username)
    return TokenResponse(access_token=token, username=req.username)
