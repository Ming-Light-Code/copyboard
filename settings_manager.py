"""
Copyboard — 设置管理模块
内存缓存 + SQLite 持久化 + 开机自启管理
"""

from database import db

# ── 默认值 ────────────────────────────────────────────────────
DEFAULTS = {
    'retention_days': '7',
    'max_items': '100',
    'theme': 'light',
    'auto_start': 'false',
    'poll_interval_ms': '750',
    'hotkey': 'alt+v',
    'storage_mode': 'light',  # light: 仅路径引用 / full: 复制到本地
}

_cache = {}


def load():
    """从数据库加载全部设置，缺失项用默认值补齐"""
    global _cache
    for key, default in DEFAULTS.items():
        value = db.get_setting(key)
        if value is None:
            _cache[key] = default
            db.set_setting(key, default)
        else:
            _cache[key] = value
    return _cache


def get(key: str) -> str:
    """读取单个设置项"""
    return _cache.get(key, DEFAULTS.get(key, ''))


def get_all() -> dict:
    """读取全部设置（返回副本）"""
    return dict(_cache)


def set(key: str, value: str):
    """写入设置项并即时持久化"""
    _cache[key] = value
    db.set_setting(key, value)
    if key == 'auto_start':
        if value == 'true':
            _enable_autostart()
        else:
            _disable_autostart()


def _enable_autostart():
    """在 Windows 启动文件夹中创建 Copyboard 快捷方式"""
    import os, sys
    try:
        startup = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
        )
        bat_path = os.path.join(startup, 'Copyboard.bat')
        with open(bat_path, 'w') as f:
            f.write(f'@echo off\n')
            f.write(f'cd /d "{os.path.dirname(os.path.abspath(__file__))}"\n')
            f.write(f'start "" "{sys.executable}" "{os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")}"\n')
    except Exception as e:
        print(f"[Settings] 开机自启启用失败: {e}")


def _disable_autostart():
    """移除 Windows 启动文件夹中的快捷方式"""
    import os
    try:
        bat = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup',
            'Copyboard.bat'
        )
        if os.path.exists(bat):
            os.remove(bat)
    except Exception as e:
        print(f"[Settings] 开机自启禁用失败: {e}")
