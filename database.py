"""
Copyboard — 数据库模块
SQLite 初始化、建表索引、CRUD 操作、数据清理
"""

import sqlite3
import os
from datetime import datetime, timezone


def _db_path():
    """数据库统一存放在 APPDATA/Copyboard"""
    data_dir = os.path.join(os.getenv('APPDATA'), 'Copyboard')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'copyboard.db')


class Database:
    """剪贴板历史数据库"""

    def __init__(self):
        os.makedirs(os.path.dirname(_db_path()), exist_ok=True)
        self.conn = sqlite3.connect(_db_path(), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        """建表 + 索引 + 性能 pragma"""
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

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

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        self.conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_items_created   ON clipboard_items(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_items_type       ON clipboard_items(type);
            CREATE INDEX IF NOT EXISTS idx_items_pinned     ON clipboard_items(is_pinned) WHERE is_pinned = 1;
            CREATE INDEX IF NOT EXISTS idx_items_favorite   ON clipboard_items(is_favorite) WHERE is_favorite = 1;
            CREATE UNIQUE INDEX IF NOT EXISTS idx_items_hash ON clipboard_items(content_hash);
        """)
        self.conn.commit()

    # ── 条目 CRUD ───────────────────────────────────────────

    def add_item(self, item: dict) -> dict:
        """插入新条目，若 content_hash 已存在则更新 last_used_at"""
        now = datetime.now(timezone.utc).isoformat()
        existing = self.conn.execute(
            "SELECT id FROM clipboard_items WHERE content_hash = ?",
            (item['content_hash'],)
        ).fetchone()

        if existing:
            self.conn.execute(
                "UPDATE clipboard_items SET last_used_at = ?, created_at = ? WHERE id = ?",
                (now, now, existing['id'])
            )
            self.conn.commit()
            return self.get_item_by_id(existing['id'])

        cur = self.conn.execute("""
            INSERT INTO clipboard_items
                (type, content, image_path, file_paths, stored_paths, content_hash,
                 source_app, char_count, image_width, image_height, file_count,
                 is_pinned, is_favorite, created_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
        """, (
            item['type'], item.get('content'), item.get('image_path'),
            item.get('file_paths'), item.get('stored_paths'), item['content_hash'],
            item.get('source_app'), item.get('char_count', 0),
            item.get('image_width'), item.get('image_height'),
            item.get('file_count', 0), now, now
        ))
        self.conn.commit()
        return self.get_item_by_id(cur.lastrowid)

    def get_items(self, filters: dict = None) -> list:
        """按条件查询条目，支持 type / since / favorites / 分页"""
        filters = filters or {}
        sql = "SELECT * FROM clipboard_items WHERE 1=1"
        params = []

        if filters.get('type'):
            sql += " AND type = ?"; params.append(filters['type'])
        if filters.get('since'):
            sql += " AND created_at >= ?"; params.append(filters['since'])
        if filters.get('favorites'):
            sql += " AND is_favorite = 1"

        sql += " ORDER BY is_pinned DESC, created_at DESC"
        sql += " LIMIT ? OFFSET ?"
        params.extend([filters.get('limit', 100), filters.get('offset', 0)])

        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def get_item_by_id(self, item_id: int) -> dict:
        row = self.conn.execute("SELECT * FROM clipboard_items WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None

    def search_items(self, query: str, filters: dict = None) -> list:
        """LIKE 搜索 content / image_path / file_paths / stored_paths"""
        filters = filters or {}
        q = f"%{query}%"
        sql = """SELECT * FROM clipboard_items
                 WHERE content LIKE ? OR image_path LIKE ? OR file_paths LIKE ? OR stored_paths LIKE ?"""
        params = [q, q, q, q]

        if filters.get('type'):
            sql += " AND type = ?"; params.append(filters['type'])
        if filters.get('since'):
            sql += " AND created_at >= ?"; params.append(filters['since'])

        sql += " ORDER BY is_pinned DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([filters.get('limit', 100), filters.get('offset', 0)])

        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def pin_item(self, item_id: int, pinned: bool):
        self.conn.execute("UPDATE clipboard_items SET is_pinned = ? WHERE id = ?", (1 if pinned else 0, item_id))
        self.conn.commit()

    def favorite_item(self, item_id: int, favorited: bool):
        self.conn.execute("UPDATE clipboard_items SET is_favorite = ? WHERE id = ?", (1 if favorited else 0, item_id))
        self.conn.commit()

    def touch_item(self, item_id: int):
        self.conn.execute("UPDATE clipboard_items SET last_used_at = ? WHERE id = ?",
                          (datetime.now(timezone.utc).isoformat(), item_id))
        self.conn.commit()

    def delete_item(self, item_id: int) -> dict:
        item = self.get_item_by_id(item_id)
        if item:
            self.conn.execute("DELETE FROM clipboard_items WHERE id = ?", (item_id,))
            self.conn.commit()
        return item

    def get_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS c FROM clipboard_items").fetchone()['c']

    # ── 清理 ────────────────────────────────────────────────

    def prune_old_items(self, days: int) -> list:
        """删除超过保留天数的非置顶条目"""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        items = [dict(r) for r in self.conn.execute(
            "SELECT * FROM clipboard_items WHERE is_pinned = 0 AND created_at < ?", (cutoff,)
        ).fetchall()]
        self.conn.execute("DELETE FROM clipboard_items WHERE is_pinned = 0 AND created_at < ?", (cutoff,))
        self.conn.commit()
        return items

    def prune_excess_items(self, max_items: int) -> list:
        """删除超出上限的最旧非置顶条目"""
        excess = self.get_count() - max_items
        if excess <= 0:
            return []
        items = [dict(r) for r in self.conn.execute(
            "SELECT * FROM clipboard_items WHERE is_pinned = 0 ORDER BY created_at ASC LIMIT ?", (excess,)
        ).fetchall()]
        self.conn.execute(
            "DELETE FROM clipboard_items WHERE id IN (SELECT id FROM clipboard_items WHERE is_pinned = 0 ORDER BY created_at ASC LIMIT ?)",
            (excess,)
        )
        self.conn.commit()
        return items

    # ── 设置 ────────────────────────────────────────────────

    def get_setting(self, key: str) -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row['value'] if row else None

    def set_setting(self, key: str, value: str):
        self.conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                          (key, value))
        self.conn.commit()

    def close(self):
        self.conn.close()


db = Database()
