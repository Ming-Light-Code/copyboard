"""
Copyboard — 系统托盘管理模块
使用 pystray 创建托盘图标和右键菜单
"""

import threading
from PIL import Image, ImageDraw


def create_tray_icon(app):
    """
    创建系统托盘图标
    app: CopyboardApp 实例
    """
    try:
        import pystray
    except ImportError:
        print("[Tray] pystray 未安装，跳过托盘创建")
        return None

    # 创建简单的托盘图标
    icon_image = _create_icon_image()

    # 构建菜单
    menu = pystray.Menu(
        pystray.MenuItem(
            '显示/隐藏面板',
            lambda: _toggle_app(app),
            default=True,
        ),
        pystray.MenuItem(
            '设置',
            lambda: _show_settings(app),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            '退出 Copyboard',
            lambda: _quit_app(app),
        ),
    )

    tray_icon = pystray.Icon(
        'copyboard',
        icon_image,
        'Copyboard - 历史剪贴板',
        menu,
    )

    # 在单独的线程中运行托盘
    tray_thread = threading.Thread(
        target=tray_icon.run,
        daemon=True,
    )
    tray_thread.start()

    return tray_icon


def _create_icon_image():
    """加载应用图标"""
    import os
    icon_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'assets', 'icon.png'
    )
    if os.path.exists(icon_path):
        try:
            img = Image.open(icon_path)
            img = img.resize((16, 16), Image.LANCZOS)
            return img
        except Exception:
            pass
    # 回退：简单蓝色方块
    img = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 14, 14], fill=(79, 110, 247, 255))
    return img


def _toggle_app(app):
    """切换主面板显隐"""
    app.root.after(0, app.toggle)


def _show_settings(app):
    """显示设置"""
    app.root.after(0, app.show)
    app.root.after(300, app._show_settings)


def _quit_app(app):
    """退出应用"""
    app.root.after(0, app.quit_app)


def run_tray(app):
    """在后台线程运行托盘"""
    create_tray_icon(app)
