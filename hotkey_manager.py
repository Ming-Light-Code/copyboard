"""
Copyboard — 全局快捷键模块
使用 Windows RegisterHotKey API，不安装键盘钩子，避免干扰鼠标事件
"""

import ctypes
import ctypes.wintypes

user32 = ctypes.windll.user32

# Windows 常量
MOD_ALT = 0x0001
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_V = 0x56
WM_HOTKEY = 0x0312
HOTKEY_ID = 1

_callback = None
_registered = False


def _acquire_hwnd(root):
    """获取 tkinter 窗口的原生 HWND 句柄"""
    root.update_idletasks()
    was_hidden = root.state() == 'withdrawn'
    if was_hidden:
        root.deiconify()
        root.update()
    raw = root.winfo_id()
    if isinstance(raw, bytes):
        hwnd = int.from_bytes(raw, 'little')
    else:
        hwnd = int(raw)
    if was_hidden:
        root.withdraw()
    return hwnd


def register_hotkey(app):
    """注册全局 Alt+V，失败则回退到 Alt+Shift+V"""
    global _callback, _registered
    _callback = lambda: app.root.after(0, app.toggle)

    try:
        hwnd = _acquire_hwnd(app.master)
        ok = user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_ALT | MOD_NOREPEAT, VK_V)
        if ok:
            _registered = True
            app.root.bind('<<Hotkey>>', lambda e: _callback and _callback())
            _pump_messages(app.root, hwnd)
            print("[Hotkey] Alt+V 已注册 (原生 API)")
            return True

        ok = user32.RegisterHotKey(hwnd, HOTKEY_ID, MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, VK_V)
        if ok:
            _registered = True
            app.root.bind('<<Hotkey>>', lambda e: _callback and _callback())
            _pump_messages(app.root, hwnd)
            print("[Hotkey] Alt+Shift+V 已注册 (回退)")
            return True

        print("[Hotkey] 注册失败，热键可能被占用")
        return False
    except Exception as e:
        print(f"[Hotkey] 异常: {e}")
        return False


def _pump_messages(root, hwnd):
    """通过 tkinter after 定时轮询 WM_HOTKEY 消息"""
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
            while user32.PeekMessageW(ctypes.byref(msg), hwnd, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    root.event_generate('<<Hotkey>>')
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            pass
        root.after(100, check)

    root.after(100, check)


def unregister():
    """注销全局快捷键"""
    global _registered
    if _registered:
        user32.UnregisterHotKey(None, HOTKEY_ID)
        _registered = False
