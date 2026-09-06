# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 配置文件
"""

import os

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 数据目录
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_PATH = os.path.join(DATA_DIR, 'platform.db')

# 上传文件目录
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')

# 报告输出目录
REPORTS_DIR = os.path.join(DATA_DIR, 'reports')

# 规则目录
RULES_DIR = os.path.join(PROJECT_ROOT, 'rules')

# Flask 模板和静态文件目录
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, 'web', 'templates')
STATIC_DIR = os.path.join(PROJECT_ROOT, 'web', 'static')

# JWT 配置（生产环境请通过环境变量 REDTEAM_JWT_SECRET 覆盖）
import os as _os
JWT_SECRET = _os.environ.get('REDTEAM_JWT_SECRET', 'redteam-platform-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRE_MINUTES = 60 * 24  # 24小时

# 用户列表（用户名: 密码明文，团队一般共享一个账户）
# 如需新增账号直接在此添加；忘记密码直接改这里重启即可
USERS = {
    "admin": "admin123",
}

# 平台管理员（可修改全局规则等）；请在生产环境保留 admin 并更换口令
ADMIN_USERS = {"admin"}

# 调试模式（开启 reload；生产部署请设为 0）
# 默认关闭更安全；本地开发用 REDTEAM_DEBUG=1 python app.py
DEBUG = _os.environ.get('REDTEAM_DEBUG', '0') == '1'

# 服务端口
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
