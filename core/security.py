# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 平台 API Token 管理
初始随机 token 永久有效；只有管理员在设置页手动“刷新”才会更换
"""

import json
import secrets
import os
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR

TOKEN_FILE = os.path.join(DATA_DIR, 'api_token.json')


def _read() -> dict:
    try:
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _write(payload: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(TOKEN_FILE, 0o600)   # 仅属主可读写（尽力而为）
    except Exception:
        pass


def get_or_create_token() -> dict:
    """读取当前 token；不存在则生成一个（初始 token 永久有效，直到手动刷新）"""
    data = _read()
    token = data.get('token')
    if not token:
        token = secrets.token_urlsafe(48)   # 384-bit 随机
        data = {
            'token': token,
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'rotated_at': None,
            'permanent_default': True,       # 初始 token 永不过期
        }
        _write(data)
    return data


def rotate_token() -> dict:
    """手动刷新 token（旧 token 立即失效）"""
    token = secrets.token_urlsafe(48)
    data = {
        'token': token,
        'created_at': _read().get('created_at') or datetime.now().isoformat(timespec='seconds'),
        'rotated_at': datetime.now().isoformat(timespec='seconds'),
        'permanent_default': False,          # 已人工刷新，不再是初始 token
    }
    _write(data)
    return data


def verify_token(token: str) -> bool:
    """校验平台 token（用于 MCP / 外部接口）"""
    if not token:
        return False
    current = _read().get('token')
    return bool(current) and secrets.compare_digest(current, token)
