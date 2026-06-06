"""
Copyboard — 设置管理模块
内存缓存 + DB 持久化
"""

from database import db

# 默认值
DEFAULTS = {
    'retention_days': '7',
    'max_items': '100',
    'theme': 'light',
    'auto_start': 'false',
    'poll_interval_ms': '750',
    'hotkey': 'alt+v',
    'storage_mode': 'light',  # 'light' = 仅路径引用, 'full' = 复制到本地
}

# 内存缓存
_cache = {}


def load():
    """初始化：加载所有设置，补全缺失的默认值"""
    global _cache
    db_settings = db.get_all_settings()

    for key, default_value in DEFAULTS.items():
        if key not in db_settings:
            _cache[key] = default_value
            db.set_setting(key, default_value)
        else:
            _cache[key] = db_settings[key]

    return _cache


def get(key: str) -> str:
    """获取单个设置"""
    return _cache.get(key, DEFAULTS.get(key, ''))


def get_all() -> dict:
    """获取所有设置"""
    return dict(_cache)


def set(key: str, value: str):
    """更新设置"""
    _cache[key] = value
    db.set_setting(key, value)

    # 处理开机自启
    if key == 'auto_start':
        if value == 'true':
            enable_autostart()
        else:
            disable_autostart()


def enable_autostart():
    """启用开机自启（Windows 启动文件夹方式）"""
    import os
    import sys

    try:
        startup_dir = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
        )

        # 创建快捷方式（使用 .vbs 脚本方式或直接放 bat 文件）
        bat_path = os.path.join(startup_dir, 'Copyboard.bat')

        # 获取 Python 路径和脚本路径
        python_exe = sys.executable
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'main.py'
        )

        with open(bat_path, 'w') as f:
            f.write(f'@echo off\n')
            f.write(f'cd /d "{os.path.dirname(script_path)}"\n')
            f.write(f'start "" "{python_exe}" "{script_path}"\n')

        print(f"[Settings] 开机自启已启用: {bat_path}")
    except Exception as e:
        print(f"[Settings] 启用开机自启失败: {e}")


def disable_autostart():
    """禁用开机自启"""
    import os

    try:
        startup_dir = os.path.join(
            os.getenv('APPDATA'),
            'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
        )
        bat_path = os.path.join(startup_dir, 'Copyboard.bat')

        if os.path.exists(bat_path):
            os.remove(bat_path)
            print("[Settings] 开机自启已禁用")
    except Exception as e:
        print(f"[Settings] 禁用开机自启失败: {e}")
