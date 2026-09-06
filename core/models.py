# -*- coding: utf-8 -*-
"""
幕论红队协同平台 - 数据库模型
SQLite 数据库，存储项目、黑板条目、攻击图边等
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    def enable_wal(self):
        """启用 WAL 模式提升并发读性能"""
        with self.get_connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")

    def init_database(self):
        with self.get_connection() as conn:
            c = conn.cursor()

            # 项目表
            c.execute('''
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'active',
                    owner TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 项目成员表
            c.execute('''
                CREATE TABLE IF NOT EXISTS project_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, username),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            ''')

            # 目标表
            c.execute('''
                CREATE TABLE IF NOT EXISTS targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    ip TEXT NOT NULL,
                    hostname TEXT,
                    os TEXT,
                    description TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, ip),
                    FOREIGN KEY (project_id) REFERENCES projects(id)
                )
            ''')

            # 黑板条目表
            c.execute('''
                CREATE TABLE IF NOT EXISTS blackboard_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    author TEXT NOT NULL,
                    category TEXT NOT NULL,
                    target_id INTEGER,
                    status TEXT DEFAULT 'new',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (target_id) REFERENCES targets(id)
                )
            ''')

            # 攻击图边表
            c.execute('''
                CREATE TABLE IF NOT EXISTS attack_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    from_entry_id INTEGER NOT NULL,
                    to_entry_id INTEGER NOT NULL,
                    label TEXT,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (from_entry_id) REFERENCES blackboard_entries(id),
                    FOREIGN KEY (to_entry_id) REFERENCES blackboard_entries(id)
                )
            ''')

            conn.commit()


# 全局数据库实例
db = Database()


def init_db():
    """初始化数据库（供 app.py 调用）"""
    db.init_database()
    try:
        db.enable_wal()   # 提升多读并发
    except Exception as e:
        import logging
        logging.getLogger('db').warning('enable WAL failed: %s', e)


# ==================== 项目操作 ====================

class Project:
    @staticmethod
    def create(name: str, description: str, owner: str) -> int:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO projects (name, description, owner) VALUES (?, ?, ?)",
                (name, description, owner)
            )
            project_id = c.lastrowid
            # 创建者自动成为成员
            c.execute(
                "INSERT OR IGNORE INTO project_members (project_id, username) VALUES (?, ?)",
                (project_id, owner)
            )
            conn.commit()
            return project_id

    @staticmethod
    def get_by_id(project_id: int) -> Optional[Dict]:
        with db.get_connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_all() -> List[Dict]:
        with db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_by_user(username: str) -> List[Dict]:
        with db.get_connection() as conn:
            rows = conn.execute('''
                SELECT p.* FROM projects p
                JOIN project_members pm ON p.id = pm.project_id
                WHERE pm.username = ?
                ORDER BY p.updated_at DESC
            ''', (username,)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update(project_id: int, **kwargs) -> bool:
        allowed = {'name', 'description', 'status'}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return False
        fields['updated_at'] = datetime.now().isoformat()
        set_clause = ', '.join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [project_id]
        with db.get_connection() as conn:
            conn.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return True

    @staticmethod
    def delete(project_id: int) -> bool:
        with db.get_connection() as conn:
            # 按依赖顺序删除关联数据
            conn.execute("DELETE FROM attack_edges WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM blackboard_entries WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM targets WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM project_members WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return True

    @staticmethod
    def add_member(project_id: int, username: str):
        with db.get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO project_members (project_id, username) VALUES (?, ?)",
                (project_id, username)
            )
            conn.commit()

    @staticmethod
    def remove_member(project_id: int, username: str) -> bool:
        with db.get_connection() as conn:
            cur = conn.execute(
                "DELETE FROM project_members WHERE project_id = ? AND username = ?",
                (project_id, username)
            )
            conn.commit()
            return cur.rowcount > 0

    @staticmethod
    def is_member(project_id: int, username: str) -> bool:
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM project_members WHERE project_id = ? AND username = ?",
                (project_id, username)
            ).fetchone()
            return row is not None

    @staticmethod
    def is_owner(project_id: int, username: str) -> bool:
        project = Project.get_by_id(project_id)
        return project is not None and project['owner'] == username

    @staticmethod
    def get_members(project_id: int) -> List[str]:
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT username FROM project_members WHERE project_id = ?",
                (project_id,)
            ).fetchall()
            return [r['username'] for r in rows]

    @staticmethod
    def get_stats(project_id: int) -> Dict:
        with db.get_connection() as conn:
            targets = conn.execute(
                "SELECT COUNT(*) as cnt FROM targets WHERE project_id = ?",
                (project_id,)
            ).fetchone()['cnt']
            entries = conn.execute(
                "SELECT COUNT(*) as cnt FROM blackboard_entries WHERE project_id = ?",
                (project_id,)
            ).fetchone()['cnt']
            return {'targets': targets, 'entries': entries}


# ==================== 目标操作 ====================

class Target:
    @staticmethod
    def create(project_id: int, ip: str, hostname: str = None,
               os_name: str = None, description: str = None, tags: str = None) -> int:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT INTO targets (project_id, ip, hostname, os, description, tags) VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, ip, hostname, os_name, description, tags)
            )
            conn.commit()
            return c.lastrowid

    @staticmethod
    def get_by_project(project_id: int) -> List[Dict]:
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM targets WHERE project_id = ? ORDER BY created_at",
                (project_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_by_id(target_id: int) -> Optional[Dict]:
        with db.get_connection() as conn:
            row = conn.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def delete(target_id: int) -> bool:
        with db.get_connection() as conn:
            conn.execute("DELETE FROM targets WHERE id = ?", (target_id,))
            conn.commit()
            return True

    @staticmethod
    def delete_cascade(project_id: int, target_id: int) -> bool:
        """删除目标及其关联的条目、攻击边"""
        try:
            with db.get_connection() as conn:
                # 删除该目标下所有条目关联的边
                entry_ids = [r['id'] for r in conn.execute(
                    "SELECT id FROM blackboard_entries WHERE project_id = ? AND target_id = ?",
                    (project_id, target_id)
                ).fetchall()]
                for eid in entry_ids:
                    conn.execute(
                        "DELETE FROM attack_edges WHERE from_entry_id = ? OR to_entry_id = ?",
                        (eid, eid)
                    )
                # 删除该目标下的条目
                conn.execute(
                    "DELETE FROM blackboard_entries WHERE project_id = ? AND target_id = ?",
                    (project_id, target_id)
                )
                # 删除目标
                conn.execute(
                    "DELETE FROM targets WHERE id = ? AND project_id = ?",
                    (target_id, project_id)
                )
                conn.commit()
                return True
        except Exception:
            return False


# ==================== 黑板条目操作 ====================

class BlackboardEntry:
    @staticmethod
    def create(project_id: int, author: str, category: str, title: str,
               content: dict, target_id: int = None, status: str = 'new') -> int:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                '''INSERT INTO blackboard_entries
                   (project_id, author, category, target_id, status, title, content)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (project_id, author, category, target_id, status, title, json.dumps(content, ensure_ascii=False))
            )
            conn.commit()
            return c.lastrowid

    @staticmethod
    def get_by_project(project_id: int, category: str = None, target_id: int = None,
                       status: str = None) -> List[Dict]:
        with db.get_connection() as conn:
            query = "SELECT * FROM blackboard_entries WHERE project_id = ?"
            params = [project_id]
            if category:
                query += " AND category = ?"
                params.append(category)
            if target_id:
                query += " AND target_id = ?"
                params.append(target_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at"
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d['content'] = json.loads(d['content']) if d['content'] else {}
                results.append(d)
            return results

    @staticmethod
    def get_by_id(entry_id: int) -> Optional[Dict]:
        with db.get_connection() as conn:
            row = conn.execute("SELECT * FROM blackboard_entries WHERE id = ?", (entry_id,)).fetchone()
            if row:
                d = dict(row)
                d['content'] = json.loads(d['content']) if d['content'] else {}
                return d
            return None

    @staticmethod
    def update_status(entry_id: int, status: str) -> bool:
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE blackboard_entries SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), entry_id)
            )
            conn.commit()
            return True

    @staticmethod
    def update(entry_id: int, **kwargs) -> bool:
        allowed = {'title', 'content', 'status', 'category', 'target_id'}
        fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not fields:
            return False
        if 'content' in fields and isinstance(fields['content'], dict):
            fields['content'] = json.dumps(fields['content'], ensure_ascii=False)
        fields['updated_at'] = datetime.now().isoformat()
        set_clause = ', '.join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [entry_id]
        with db.get_connection() as conn:
            conn.execute(f"UPDATE blackboard_entries SET {set_clause} WHERE id = ?", values)
            conn.commit()
            return True

    @staticmethod
    def delete(entry_id: int) -> bool:
        with db.get_connection() as conn:
            conn.execute("DELETE FROM blackboard_entries WHERE id = ?", (entry_id,))
            conn.commit()
            return True

    @staticmethod
    def delete_cascade(project_id: int, entry_id: int) -> bool:
        """删除条目及其关联的攻击边"""
        try:
            with db.get_connection() as conn:
                conn.execute(
                    "DELETE FROM attack_edges WHERE from_entry_id = ? OR to_entry_id = ?",
                    (entry_id, entry_id)
                )
                conn.execute(
                    "DELETE FROM blackboard_entries WHERE id = ? AND project_id = ?",
                    (entry_id, project_id)
                )
                conn.commit()
                return True
        except Exception:
            return False


# ==================== 攻击图边操作 ====================

class AttackEdge:
    @staticmethod
    def create(project_id: int, from_entry_id: int, to_entry_id: int,
               label: str, created_by: str) -> int:
        with db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                '''INSERT INTO attack_edges
                   (project_id, from_entry_id, to_entry_id, label, created_by)
                   VALUES (?, ?, ?, ?, ?)''',
                (project_id, from_entry_id, to_entry_id, label, created_by)
            )
            conn.commit()
            return c.lastrowid

    @staticmethod
    def get_by_project(project_id: int) -> List[Dict]:
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM attack_edges WHERE project_id = ? ORDER BY created_at",
                (project_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def delete(edge_id: int) -> bool:
        with db.get_connection() as conn:
            conn.execute("DELETE FROM attack_edges WHERE id = ?", (edge_id,))
            conn.commit()
            return True
