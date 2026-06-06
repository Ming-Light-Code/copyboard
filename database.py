"""
Copyboard — 数据库模块
SQLite 初始化、建表、所有 CRUD 操作
"""

import sqlite3
import os
from datetime import datetime, timezone


def get_db_path():
    """获取数据库文件路径"""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'copyboard.db')


class Database:
    """剪贴板数据库管理类"""

    def __init__(self):
        self.db_path = get_db_path()
        self.conn = None
        self.init()

    def init(self):
        """初始化数据库：打开连接、建表、创建索引"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 让查询结果可以通过列名访问
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

        # 创建主表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS clipboard_items (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                type          TEXT NOT NULL CHECK(type IN ('text','image','file','folder')),
                content       TEXT,
                image_path    TEXT,
                file_paths    TEXT,
                stored_paths  TEXT,
                content_hash  TEXT NOT NULL,
                source_app    TEXT,
                char_count    INTEGER DEFAULT 0,
                image_width   INTEGER,
                image_height  INTEGER,
                file_count    INTEGER DEFAULT 0,
                is_pinned     INTEGER DEFAULT 0,
                is_favorite   INTEGER DEFAULT 0,
                created_at    TEXT NOT NULL,
                last_used_at  TEXT NOT NULL
            )
        """)

        # 创建设置表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # 创建索引
        self.conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_items_created
                ON clipboard_items(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_items_type
                ON clipboard_items(type);
            CREATE INDEX IF NOT EXISTS idx_items_pinned
                ON clipboard_items(is_pinned) WHERE is_pinned = 1;
            CREATE INDEX IF NOT EXISTS idx_items_favorite
                ON clipboard_items(is_favorite) WHERE is_favorite = 1;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_items_hash
                ON clipboard_items(content_hash);
        """)

        self.conn.commit()

    # ========== 条目 CRUD ==========

    def add_item(self, item: dict) -> dict:
        """添加条目（自动去重：相同 hash 则更新 last_used_at）"""
        now = datetime.now(timezone.utc).isoformat()

        # 检查哈希是否已存在
        cursor = self.conn.execute(
            "SELECT id FROM clipboard_items WHERE content_hash = ?",
            (item['content_hash'],)
        )
        existing = cursor.fetchone()

        if existing:
            self.conn.execute(
                "UPDATE clipboard_items SET last_used_at = ?, created_at = ? WHERE id = ?",
                (now, now, existing['id'])
            )
            self.conn.commit()
            return self.get_item_by_id(existing['id'])

        # 插入新条目
        cursor = self.conn.execute("""
            INSERT INTO clipboard_items
                (type, content, image_path, file_paths, stored_paths, content_hash,
                 source_app, char_count, image_width, image_height, file_count,
                 is_pinned, is_favorite, created_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
        """, (
            item['type'],
            item.get('content'),
            item.get('image_path'),
            item.get('file_paths'),
            item.get('stored_paths'),
            item['content_hash'],
            item.get('source_app'),
            item.get('char_count', 0),
            item.get('image_width'),
            item.get('image_height'),
            item.get('file_count', 0),
            now, now
        ))
        self.conn.commit()
        return self.get_item_by_id(cursor.lastrowid)

    def get_items(self, filter_dict: dict = None) -> list:
        """获取条目列表（支持筛选、排序、分页）"""
        if filter_dict is None:
            filter_dict = {}

        sql = "SELECT * FROM clipboard_items WHERE 1=1"
        params = []

        if filter_dict.get('type'):
            sql += " AND type = ?"
            params.append(filter_dict['type'])

        if filter_dict.get('since'):
            sql += " AND created_at >= ?"
            params.append(filter_dict['since'])

        if filter_dict.get('favorites'):
            sql += " AND is_favorite = 1"

        sql += " ORDER BY is_pinned DESC, created_at DESC"

        limit = filter_dict.get('limit', 100)
        offset = filter_dict.get('offset', 0)
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_item_by_id(self, item_id: int) -> dict:
        """根据 ID 获取单个条目"""
        cursor = self.conn.execute(
            "SELECT * FROM clipboard_items WHERE id = ?", (item_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def search_items(self, query: str, filter_dict: dict = None) -> list:
        """搜索条目（LIKE 匹配）"""
        if filter_dict is None:
            filter_dict = {}

        q = f"%{query}%"
        sql = """
            SELECT * FROM clipboard_items WHERE 1=1
            AND (
                content LIKE ?
                OR image_path LIKE ?
                OR file_paths LIKE ?
                OR stored_paths LIKE ?
            )
        """
        params = [q, q, q, q]

        if filter_dict.get('type'):
            sql += " AND type = ?"
            params.append(filter_dict['type'])
        if filter_dict.get('since'):
            sql += " AND created_at >= ?"
            params.append(filter_dict['since'])

        sql += " ORDER BY is_pinned DESC, created_at DESC"
        sql += " LIMIT ? OFFSET ?"
        params.extend([filter_dict.get('limit', 100), filter_dict.get('offset', 0)])

        cursor = self.conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def pin_item(self, item_id: int, pinned: bool):
        """更新条目置顶状态"""
        self.conn.execute(
            "UPDATE clipboard_items SET is_pinned = ? WHERE id = ?",
            (1 if pinned else 0, item_id)
        )
        self.conn.commit()

    def favorite_item(self, item_id: int, favorited: bool):
        """更新条目收藏状态"""
        self.conn.execute(
            "UPDATE clipboard_items SET is_favorite = ? WHERE id = ?",
            (1 if favorited else 0, item_id)
        )
        self.conn.commit()

    def touch_item(self, item_id: int):
        """更新条目最后使用时间"""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE clipboard_items SET last_used_at = ? WHERE id = ?",
            (now, item_id)
        )
        self.conn.commit()

    def delete_item(self, item_id: int) -> dict:
        """删除条目（返回被删除的条目信息）"""
        item = self.get_item_by_id(item_id)
        if item:
            self.conn.execute("DELETE FROM clipboard_items WHERE id = ?", (item_id,))
            self.conn.commit()
        return item

    def get_count(self) -> int:
        """获取条目总数"""
        cursor = self.conn.execute("SELECT COUNT(*) as count FROM clipboard_items")
        return cursor.fetchone()['count']

    # ========== 清理操作 ==========

    def prune_old_items(self, days: int) -> list:
        """删除超过留存天数的非置顶条目"""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor = self.conn.execute(
            "SELECT * FROM clipboard_items WHERE is_pinned = 0 AND created_at < ?",
            (cutoff,)
        )
        items = [dict(row) for row in cursor.fetchall()]

        self.conn.execute(
            "DELETE FROM clipboard_items WHERE is_pinned = 0 AND created_at < ?",
            (cutoff,)
        )
        self.conn.commit()
        return items

    def prune_excess_items(self, max_items: int) -> list:
        """删除超出最大条数的旧条目（非置顶）"""
        count = self.get_count()
        excess = count - max_items
        if excess <= 0:
            return []

        cursor = self.conn.execute("""
            SELECT * FROM clipboard_items
            WHERE is_pinned = 0
            ORDER BY created_at ASC
            LIMIT ?
        """, (excess,))
        items = [dict(row) for row in cursor.fetchall()]

        self.conn.execute("""
            DELETE FROM clipboard_items
            WHERE id IN (
                SELECT id FROM clipboard_items
                WHERE is_pinned = 0
                ORDER BY created_at ASC
                LIMIT ?
            )
        """, (excess,))
        self.conn.commit()
        return items

    # ========== 设置操作 ==========

    def get_all_settings(self) -> dict:
        """获取所有设置"""
        cursor = self.conn.execute("SELECT * FROM settings")
        return {row['key']: row['value'] for row in cursor.fetchall()}

    def get_setting(self, key: str) -> str:
        """获取单个设置"""
        cursor = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row['value'] if row else None

    def set_setting(self, key: str, value: str):
        """设置/更新设置项"""
        self.conn.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        self.conn.commit()

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()


# 全局数据库实例
db = Database()
