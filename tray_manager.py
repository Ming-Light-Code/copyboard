"""
Copyboard — 系统托盘管理模块
使用 pystray 创建托盘图标及右键菜单
"""

import threading
import os
from PIL import Image, ImageDraw


def create_tray_icon(app):
    """创建系统托盘图标及菜单，在后台线程中运行"""
    try:
        import pystray
    except ImportError:
        print("[Tray] pystray 未安装")
        return None

    icon_image = _load_icon()

    menu = pystray.Menu(
        pystray.MenuItem('显示/隐藏面板', lambda: app.root.after(0, app.toggle), default=True),
        pystray.MenuItem('设置', lambda: _tray_show_settings(app)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('退出 Copyboard', lambda: app.root.after(0, app.quit_app)),
    )

    tray_icon = pystray.Icon('copyboard', icon_image, 'Copyboard - 历史剪贴板', menu)

    threading.Thread(target=tray_icon.run, daemon=True).start()
    return tray_icon


def _tray_show_settings(app):
    """托盘打开设置：先显示主面板，再弹出设置"""
    app.root.after(0, app.show)
    app.root.after(300, app._show_settings)


def _load_icon():
    """加载 assets/icon.png 并缩放至 16×16，失败则返回默认蓝色圆形图标"""
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets', 'icon.png')
    if os.path.exists(icon_path):
        try:
            img = Image.open(icon_path).resize((16, 16), Image.LANCZOS)
            return img
        except Exception:
            pass
    img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 14, 14], fill=(79, 110, 247, 255))
    return img
