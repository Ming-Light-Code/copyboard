"""
Copyboard — 全局快捷键管理模块
使用 Windows 原生 RegisterHotKey API，不安装任何钩子，零鼠标干扰
"""

import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32

# 热键参数
MOD_ALT = 0x0001
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_V = 0x56
WM_HOTKEY = 0x0312

HOTKEY_ID = 1

_callback = None
_registered = False


def _get_hwnd(root):
    """获取 tkinter 窗口的原生 HWND"""
    import tkinter as tk
    root.update_idletasks()
    # 临时显示以获取有效的 HWND
    was_visible = root.state() != 'withdrawn'
    if not was_visible:
        root.deiconify()
        root.update()
    raw = root.winfo_id()
    if isinstance(raw, bytes):
        hwnd = int.from_bytes(raw, 'little')
    elif isinstance(raw, int):
        hwnd = raw
    else:
        hwnd = int(raw)
    if not was_visible:
        root.withdraw()
    return hwnd


def register_hotkey(app):
    """
    注册全局 Alt+V，使用 Windows RegisterHotKey API。
    不安装键盘钩子，不拦截鼠标事件。
    """
    global _callback, _registered

    _callback = lambda: app.master.after(0, app.toggle)

    try:
        hwnd = _get_hwnd(app.master)

        # 尝试 Alt+V
        ok = user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_ALT | MOD_NOREPEAT, VK_V)
        if ok:
            _registered = True
            # 绑定 WM_HOTKEY 消息处理
            app.master.bind('<<Hotkey>>', lambda e: _handle_hotkey())
            # 启动消息轮询（轻量，不安装钩子）
            _poll_messages(app.master, hwnd)
            print("[Hotkey] 已注册: Alt+V (原生 API，无钩子)")
            return True

        # 回退 Alt+Shift+V
        ok = user32.RegisterHotKey(hwnd, HOTKEY_ID,
                                   MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, VK_V)
        if ok:
            _registered = True
            app.master.bind('<<Hotkey>>', lambda e: _handle_hotkey())
            _poll_messages(app.master, hwnd)
            print("[Hotkey] 已注册: Alt+Shift+V (回退)")
            return True

        print("[Hotkey] 注册失败 — 热键可能被其他程序占用")
        return False

    except Exception as e:
        print(f"[Hotkey] 注册异常: {e}")
        return False


def _poll_messages(root, hwnd):
    """
    轻量 Windows 消息轮询。
    使用 tkinter 的 after 定时检查 WM_HOTKEY 消息。
    不需要额外的线程或钩子。
    """
    import tkinter as tk

    # 定义消息结构
    class MSG(ctypes.Structure):
        _fields_ = [
            ('hwnd', ctypes.wintypes.HWND),
            ('message', ctypes.wintypes.UINT),
            ('wParam', ctypes.wintypes.WPARAM),
            ('lParam', ctypes.wintypes.LPARAM),
            ('time', ctypes.wintypes.DWORD),
            ('pt_x', ctypes.wintypes.LONG),
            ('pt_y', ctypes.wintypes.LONG),
        ]

    PM_REMOVE = 1

    def check():
        if not _registered:
            return
        try:
            msg = MSG()
            # PeekMessage: 非阻塞检查是否有 WM_HOTKEY
            while user32.PeekMessageW(ctypes.byref(msg), hwnd, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    root.event_generate('<<Hotkey>>')
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            pass
        root.after(100, check)  # 每 100ms 检查一次

    root.after(100, check)


def _handle_hotkey():
    global _callback
    if _callback:
        _callback()


def unregister():
    """注销热键"""
    global _registered
    if _registered:
        user32.UnregisterHotKey(None, HOTKEY_ID)
        _registered = False
        print("[Hotkey] 已注销")
