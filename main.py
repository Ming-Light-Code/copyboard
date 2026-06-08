"""
Copyboard — Windows 历史剪贴板管理器
主应用程序入口
"""

# ── 单实例互斥锁 ──
import sys
import ctypes
_kernel32 = ctypes.windll.kernel32
_user32 = ctypes.windll.user32
_MUTEX_NAME = 'Copyboard_SingleInstance_Mutex'
_mutex = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
if _kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    _hwnd = _user32.FindWindowW(None, 'Copyboard')
    if _hwnd:
        _user32.ShowWindow(_hwnd, 9)  # SW_RESTORE
        _user32.SetForegroundWindow(_hwnd)
    sys.exit(0)

# ── DPI 感知（必须在 tkinter 之前调用）──
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import os
import json
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db
import settings_manager as settings
from clipboard_monitor import monitor
from file_store import delete_stored_files, get_full_path, read_thumb_base64, delete_thumb
from ui.theme_manager import theme, THEMES
from version import __version__
from tray_manager import create_tray_icon as run_tray
from hotkey_manager import register_hotkey, unregister as unregister_hotkey


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _get_ext_name(ext):
    """将扩展名映射为可读名称"""
    ext_map = {
        '.txt': 'txt文本', '.log': '日志', '.md': 'Markdown', '.py': 'Python',
        '.js': 'JavaScript', '.html': 'HTML', '.css': 'CSS', '.json': 'JSON',
        '.xml': 'XML', '.csv': 'CSV表格', '.pdf': 'PDF', '.doc': 'Word',
        '.docx': 'Word', '.xls': 'Excel', '.xlsx': 'Excel', '.ppt': 'PowerPoint',
        '.pptx': 'PowerPoint', '.zip': 'ZIP压缩', '.rar': 'RAR压缩', '.7z': '7Z压缩',
        '.jpg': 'JPG', '.jpeg': 'JPEG', '.png': 'PNG', '.gif': 'GIF',
        '.bmp': 'BMP', '.webp': 'WebP', '.svg': 'SVG', '.ico': 'ICO图标',
        '.mp4': 'MP4视频', '.avi': 'AVI视频', '.mov': 'MOV视频', '.mp3': 'MP3音频',
        '.wav': 'WAV音频', '.flac': 'FLAC音频', '.exe': '应用程序', '.dll': 'DLL库',
        '.apk': '安卓应用', '.iso': '光盘镜像', '.psd': 'Photoshop', '.ai': 'Illustrator',
        '.ttf': '字体', '.otf': '字体', '.sql': 'SQL数据库', '.db': '数据库',
    }
    return ext_map.get(ext, ext[1:].upper() if ext else '未知')


# ═══════════════════════════════════════════════════════════════
# Toast — 滑入式通知
# ═══════════════════════════════════════════════════════════════

class Toast:
    """轻量级滑入通知"""

    def __init__(self, parent):
        self.parent = parent
        self.widgets = []

    def show(self, message, duration=2000, style='info'):
        """显示 Toast"""
        colors = theme.colors

        # 图标
        icons = {'info': '📋', 'success': '✅', 'delete': '🗑', 'pin': '📌', 'star': '⭐'}
        icon = icons.get(style, '📋')

        # 容器
        frame = tk.Frame(
            self.parent,
            bg=colors['bg_card'],
            highlightthickness=0,
        )

        # 内容
        inner = tk.Frame(frame, bg=colors['bg_card'])
        inner.pack(padx=14, pady=8)

        tk.Label(inner, text=icon, font=('Segoe UI', 12),
                 bg=colors['bg_card']).pack(side='left', padx=(0, 6))

        tk.Label(inner, text=message,
                 font=('Microsoft YaHei UI', 10),
                 bg=colors['bg_card'], fg=colors['text_primary']).pack(side='left')

        # 初始位置（屏幕下方）
        frame.place(relx=0.5, rely=1.05, anchor='s')
        frame.update_idletasks()

        # 滑入动画
        self._animate_in(frame, duration)
        self.widgets.append(frame)

    def _animate_in(self, widget, duration, step=0):
        """滑入动画"""
        target_y = 0.92
        current = 1.05 - step * 0.03
        widget.place(relx=0.5, rely=min(current, target_y), anchor='s')

        if current > target_y and step < 10:
            self.parent.after(20, lambda: self._animate_in(widget, duration, step + 1))
        else:
            self.parent.after(duration, lambda: self._fade_out(widget, 0))

    def _fade_out(self, widget, step):
        """淡出"""
        if step < 5:
            try:
                widget.place(relx=0.5, rely=0.92 + step * 0.02, anchor='s')
                self.parent.after(50, lambda: self._fade_out(widget, step + 1))
            except Exception:
                pass
        else:
            widget.destroy()
            if widget in self.widgets:
                self.widgets.remove(widget)


# ═══════════════════════════════════════════════════════════════
# 设置对话框（美化版）
# ═══════════════════════════════════════════════════════════════

class SettingsDialog:
    """设置对话框"""

    def __init__(self, parent, on_settings_changed=None):
        self.parent = parent
        self.on_settings_changed = on_settings_changed
        self.dialog = None

    def show(self):
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()
            self.dialog.focus()
            return

        colors = theme.colors
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title('Copyboard 设置')
        self.dialog.geometry('400x560')
        self.dialog.resizable(False, False)
        self.dialog.configure(bg=colors['bg_secondary'])
        self.dialog.transient(self.parent)

        # 居中
        self.dialog.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 400) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - 540) // 2
        self.dialog.geometry(f'+{x}+{y}')

        # 标题栏
        title_bar = tk.Frame(self.dialog, bg=colors['bg_primary'], height=44)
        title_bar.pack(fill='x')
        title_bar.pack_propagate(False)

        tk.Label(title_bar, text='⚙  设置', font=('Microsoft YaHei UI', 12, 'bold'),
                 bg=colors['bg_primary'], fg=colors['text_primary'],
                 padx=16).pack(side='left')

        # 可滚动内容区域
        canvas = tk.Canvas(self.dialog, bg=colors['bg_secondary'],
                           highlightthickness=0)
        scrollbar = tk.Scrollbar(self.dialog, orient='vertical', command=canvas.yview)
        content = tk.Frame(canvas, bg=colors['bg_secondary'])

        win_id = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda e: canvas.configure(
            scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True, padx=10, pady=(4, 8))
        scrollbar.pack(side='right', fill='y', pady=(4, 8))

        def _on_mwheel(e):
            # 仅当鼠标在设置窗口内时才滚动
            dx, dy = self.dialog.winfo_pointerxy()
            wx, wy = self.dialog.winfo_x(), self.dialog.winfo_y()
            ww, wh = self.dialog.winfo_width(), self.dialog.winfo_height()
            if wx <= dx <= wx + ww and wy <= dy <= wy + wh:
                canvas.yview_scroll(-1 * (e.delta // 60), 'units')

        self.dialog.bind_all('<MouseWheel>', _on_mwheel, add='+')
        self.dialog.protocol('WM_DELETE_WINDOW', lambda: self._close_dialog())

        # === 设置组 ===
        self._add_section_card(content, '📦 留存设置')
        self._add_radio_card(content, 'retention_days', '保留天数',
                             [('3 天', '3'), ('5 天', '5'), ('7 天', '7')])
        self._add_radio_card(content, 'max_items', '最大条数',
                             [('50 条', '50'), ('100 条', '100'), ('300 条', '300')])

        self._add_section_card(content, '🖥 显示设置')
        self._add_toggle_card(content, 'auto_start', '开机自启', '随 Windows 自动启动')
        self._add_radio_card(content, 'hide_delay_ms', '鼠标离开后隐藏',
                             [('关闭', '0'), ('0.5 秒', '500'), ('1 秒', '1000'), ('2 秒', '2000')])

        self._add_section_card(content, '💾 存储模式')
        self._add_storage_mode_card(content)

        self._add_section_card(content, '🎨 主题配色')

        # 主题色块
        theme_card = tk.Frame(content, bg=colors['bg_card'], padx=16, pady=14)
        theme_card.pack(fill='x', pady=4)
        theme_row = tk.Frame(theme_card, bg=colors['bg_card'])
        theme_row.pack()

        for tid, tinfo in THEMES.items():
            c = tinfo['colors']
            dot = tk.Canvas(theme_row, width=44, height=44,
                            bg=colors['bg_card'], highlightthickness=0)
            dot.create_oval(6, 6, 38, 38, fill=c['accent'],
                            outline=c['border'], width=2)
            if tid == theme.current_theme:
                dot.create_oval(6, 6, 38, 38, outline=c['text_primary'], width=2)
                dot.create_text(22, 22, text='✓', fill='white',
                                font=('Segoe UI', 11, 'bold'))

            # 名称标签
            dot._name = tinfo['name']
            dot._tid = tid
            dot.bind('<Button-1>', lambda e, t=tid: self._on_theme_change(t))
            dot.pack(side='left', padx=5)

            # 悬停
            def _on_enter(e, d=dot, c=c):
                d.create_oval(4, 4, 40, 40, outline=c['accent_hover'], width=2)
            def _on_leave(e, d=dot, c=c):
                if theme.current_theme != d._tid:
                    d.create_oval(6, 6, 38, 38, fill=c['accent'],
                                  outline=c['border'], width=2)
            dot.bind('<Enter>', _on_enter)
            dot.bind('<Leave>', _on_leave)

        # 主题名称
        name_lbl = tk.Label(theme_card, text=THEMES[theme.current_theme]['name'],
                            font=('Microsoft YaHei UI', 9),
                            bg=colors['bg_card'], fg=colors['text_muted'])
        name_lbl.pack(pady=(4, 0))

        # ── 清理数据 ──
        self._add_section_card(content, '🗑 数据管理')
        clear_card = tk.Frame(content, bg=colors['bg_card'], padx=16, pady=12)
        clear_card.pack(fill='x', pady=2)

        tk.Label(clear_card, text='删除所有剪贴板记录和缓存文件',
                 font=('Microsoft YaHei UI', 9),
                 bg=colors['bg_card'], fg=colors['text_muted']).pack(anchor='w')

        clear_btn = tk.Label(clear_card, text='清理所有数据',
                             font=('Microsoft YaHei UI', 10, 'bold'),
                             bg=colors['danger'], fg='white',
                             padx=20, pady=6, cursor='hand2')
        clear_btn.pack(pady=(8, 0))
        clear_btn.bind('<Button-1>', lambda e: self._clear_all_data())

        # 底部间距
        tk.Frame(content, bg=colors['bg_secondary'], height=12).pack()

    def _close_dialog(self):
        """关闭设置对话框并解绑滚轮"""
        try:
            if self.dialog:
                self.dialog.unbind_all('<MouseWheel>')
        except Exception:
            pass
        if self.dialog:
            self.dialog.destroy()
            self.dialog = None

    def _add_section_card(self, parent, title):
        """添加分组标题卡片"""
        colors = theme.colors
        card = tk.Frame(parent, bg=colors['bg_card'])
        card.pack(fill='x', pady=(10, 2))

        tk.Label(card, text=title,
                 font=('Microsoft YaHei UI', 10, 'bold'),
                 bg=colors['bg_card'], fg=colors['accent'],
                 padx=16, pady=10).pack(anchor='w')

    def _add_radio_card(self, parent, key, label, options):
        """添加单选设置卡片"""
        colors = theme.colors
        card = tk.Frame(parent, bg=colors['bg_card'], padx=16, pady=10)
        card.pack(fill='x', pady=2)

        tk.Label(card, text=label,
                 font=('Microsoft YaHei UI', 10),
                 bg=colors['bg_card'], fg=colors['text_primary']).pack(anchor='w')

        btn_row = tk.Frame(card, bg=colors['bg_card'])
        btn_row.pack(fill='x', pady=(8, 0))

        current = settings.get(key)
        for text, value in options:
            sel = (current == value)
            btn = tk.Label(
                btn_row,
                text=text,
                font=('Microsoft YaHei UI', 9),
                bg=colors['accent'] if sel else colors['bg_input'],
                fg='white' if sel else colors['text_secondary'],
                padx=14, pady=5,
                cursor='hand2',
            )
            btn.pack(side='left', padx=3)
            btn._key = key
            btn._val = value
            btn.bind('<Button-1>', lambda e, b=btn: self._on_radio_click(b))

            if not sel:
                btn.bind('<Enter>', lambda e, b=btn: b.configure(
                    bg=colors['accent_light'], fg=colors['accent']))
                btn.bind('<Leave>', lambda e, b=btn, s=sel: (
                    b.configure(bg=colors['bg_input'], fg=colors['text_secondary'])
                    if not s else None))

    def _add_storage_mode_card(self, parent):
        """存储模式卡片 — 轻量/完整 切换（带预警）"""
        colors = theme.colors
        card = tk.Frame(parent, bg=colors['bg_card'], padx=16, pady=10)
        card.pack(fill='x', pady=2)

        row = tk.Frame(card, bg=colors['bg_card'])
        row.pack(fill='x')

        left = tk.Frame(row, bg=colors['bg_card'])
        left.pack(side='left')
        tk.Label(left, text='存储方案', font=('Microsoft YaHei UI', 10),
                 bg=colors['bg_card'], fg=colors['text_primary']).pack(anchor='w')

        current = settings.get('storage_mode')
        light_on = (current == 'light')

        # 轻量 / 完整 选项
        opts = tk.Frame(card, bg=colors['bg_card'])
        opts.pack(fill='x', pady=(8, 0))

        for text, value, desc in [
            ('🌿 轻量', 'light', '仅存路径引用，不复制文件（推荐）'),
            ('📦 完整', 'full', '复制文件到本地，占用更多磁盘空间'),
        ]:
            sel = (current == value)
            opt = tk.Frame(opts, bg=colors['bg_card'])
            opt.pack(fill='x', pady=2)

            btn = tk.Label(opt, text=text, font=('Microsoft YaHei UI', 9),
                           bg=colors['accent'] if sel else colors['bg_input'],
                           fg='white' if sel else colors['text_secondary'],
                           padx=12, pady=4, cursor='hand2')
            btn.pack(side='left')
            btn._key = 'storage_mode'
            btn._val = value

            tk.Label(opt, text=desc, font=('Microsoft YaHei UI', 8),
                     bg=colors['bg_card'], fg=colors['text_muted'],
                     padx=8).pack(side='left')

            if sel:
                btn._selected = True
            else:
                btn.bind('<Enter>', lambda e, b=btn: b.configure(
                    bg=colors['accent_light'], fg=colors['accent']) if not getattr(b, '_selected', False) else None)
                btn.bind('<Leave>', lambda e, b=btn: b.configure(
                    bg=colors['bg_input'], fg=colors['text_secondary']) if not getattr(b, '_selected', False) else None)

            btn.bind('<Button-1>', lambda e, b=btn: self._on_storage_mode_click(b))

    def _on_storage_mode_click(self, btn):
        """存储模式切换 — 完整模式需预警"""
        if btn._val == 'full':
            from tkinter import messagebox
            ok = messagebox.askokcancel(
                '切换存储方案',
                '⚠️ 切换到「完整模式」后：\n\n'
                '• 复制的文件/文件夹会被拷贝到软件数据目录\n'
                '• 会占用额外的磁盘空间\n'
                '• 图片文件会被转为 PNG 格式保存\n\n'
                '建议保留「轻量模式」以节省空间。\n\n'
                '确定要切换吗？',
                icon='warning',
            )
            if not ok:
                return

        settings.set(btn._key, btn._val)

        # 更新按钮样式
        colors = theme.colors
        for child in btn.master.winfo_children():
            for b in child.winfo_children():
                if hasattr(b, '_key') and b._key == 'storage_mode':
                    if b == btn:
                        b._selected = True
                        b.configure(bg=colors['accent'], fg='white')
                    else:
                        b._selected = False
                        b.configure(bg=colors['bg_input'], fg=colors['text_secondary'])
                        b.unbind('<Enter>')
                        b.unbind('<Leave>')
                        b.bind('<Enter>', lambda e, bb=b: bb.configure(
                            bg=colors['accent_light'], fg=colors['accent']) if not getattr(bb, '_selected', False) else None)
                        b.bind('<Leave>', lambda e, bb=b: bb.configure(
                            bg=colors['bg_input'], fg=colors['text_secondary']) if not getattr(bb, '_selected', False) else None)

    def _add_toggle_card(self, parent, key, title, desc=''):
        """添加开关设置卡片"""
        colors = theme.colors
        card = tk.Frame(parent, bg=colors['bg_card'], padx=16, pady=10)
        card.pack(fill='x', pady=2)

        row = tk.Frame(card, bg=colors['bg_card'])
        row.pack(fill='x')

        left = tk.Frame(row, bg=colors['bg_card'])
        left.pack(side='left')
        tk.Label(left, text=title, font=('Microsoft YaHei UI', 10),
                 bg=colors['bg_card'], fg=colors['text_primary']).pack(anchor='w')
        if desc:
            tk.Label(left, text=desc, font=('Microsoft YaHei UI', 9),
                     bg=colors['bg_card'], fg=colors['text_muted']).pack(anchor='w')

        is_on = settings.get(key) == 'true'
        toggle_canvas = tk.Canvas(row, width=44, height=24,
                                  bg=colors['bg_card'], highlightthickness=0)
        toggle_canvas.pack(side='right')

        def draw_toggle(on):
            toggle_canvas.delete('all')
            if on:
                toggle_canvas.create_rectangle(0, 0, 44, 24,
                                               fill=colors['accent'], outline='',
                                               width=0)
                toggle_canvas.create_oval(22, 3, 40, 21,
                                          fill='white', outline='', width=0)
            else:
                toggle_canvas.create_rectangle(0, 0, 44, 24,
                                               fill=colors['border'], outline='',
                                               width=0)
                toggle_canvas.create_oval(3, 3, 21, 21,
                                          fill='white', outline='', width=0)

        draw_toggle(is_on)
        toggle_canvas._key = key
        toggle_canvas._on = is_on

        def toggle_switch(e):
            toggle_canvas._on = not toggle_canvas._on
            draw_toggle(toggle_canvas._on)
            val = 'true' if toggle_canvas._on else 'false'
            settings.set(toggle_canvas._key, val)
            if self.on_settings_changed:
                self.on_settings_changed(toggle_canvas._key, val)

        toggle_canvas.bind('<Button-1>', toggle_switch)
        toggle_canvas.config(cursor='hand2')

    def _clear_all_data(self):
        """清理所有数据 — 弹窗确认后执行"""
        from tkinter import messagebox
        ok = messagebox.askokcancel(
            '清理所有数据',
            '⚠️ 此操作将删除：\n\n'
            '• 所有剪贴板记录\n'
            '• 所有缩略图和缓存文件\n'
            '• 完整模式下复制的文件\n\n'
            '此操作不可撤销，确定继续？',
            icon='warning',
        )
        if not ok:
            return

        import shutil
        from file_store import get_data_dir

        # 清空数据库
        db.conn.execute('DELETE FROM clipboard_items')
        db.conn.commit()

        # 删除缓存目录
        for sub in ['thumbs', 'files', 'images']:
            d = os.path.join(get_data_dir(), sub)
            if os.path.exists(d):
                shutil.rmtree(d)

        self.dialog.destroy()
        self.dialog = None

        if self.on_settings_changed:
            self.on_settings_changed('data_cleared', 'true')

    def _on_radio_click(self, btn):
        """单选按钮点击 — 更新选中状态并修复悬停绑定"""
        settings.set(btn._key, btn._val)
        if self.on_settings_changed:
            self.on_settings_changed(btn._key, btn._val)

        colors = theme.colors
        parent = btn.master
        for child in parent.winfo_children():
            if hasattr(child, '_key') and child._key == btn._key:
                if child == btn:
                    # 选中：高亮 + 清除悬停绑定
                    child.configure(bg=colors['accent'], fg='white')
                    child.unbind('<Enter>')
                    child.unbind('<Leave>')
                    # 添加新的悬停（选中状态下无需变化）
                    child.bind('<Enter>', lambda e, c=child: c.configure(
                        bg=colors['accent'], fg='white'))
                    child.bind('<Leave>', lambda e, c=child: c.configure(
                        bg=colors['accent'], fg='white'))
                else:
                    # 未选中：恢复默认 + 添加悬停绑定
                    child.configure(bg=colors['bg_input'], fg=colors['text_secondary'])
                    child.unbind('<Enter>')
                    child.unbind('<Leave>')
                    child.bind('<Enter>', lambda e, c=child: c.configure(
                        bg=colors['accent_light'], fg=colors['accent']))
                    child.bind('<Leave>', lambda e, c=child: c.configure(
                        bg=colors['bg_input'], fg=colors['text_secondary']))

    def _on_theme_change(self, theme_id):
        """主题切换 — 需要重建 UI"""
        theme.apply_theme(theme_id)
        settings.set('theme', theme_id)
        if self.on_settings_changed:
            self.on_settings_changed('theme', theme_id)
        self.dialog.destroy()
        self.dialog = None


# ═══════════════════════════════════════════════════════════════
# 主应用（美化版）
# ═══════════════════════════════════════════════════════════════

class CopyboardApp:
    """Copyboard 主应用程序"""

    def __init__(self):
        # master: 隐藏的任务栏宿主窗口
        self.master = tk.Tk()
        self.master.withdraw()
        self.master.title('Copyboard')
        self.master.geometry('1x1+0+0')
        self.master.bind('<FocusIn>', lambda e: self.show())

        # root: 实际 UI 面板
        self.root = tk.Toplevel(self.master)
        self.root.withdraw()
        self.root.title('Copyboard')
        self.root.geometry('580x930')
        self.root.resizable(True, True)
        self.root.minsize(340, 420)
        self.root.overrideredirect(True)

        settings.load()
        theme.apply_theme(settings.get('theme'))

        self.items = []
        self.current_filter = {}
        self.toast = Toast(self.root)

        self._build_ui()
        self._add_resize_grip()
        monitor.start(self.root, self._on_new_item)
        self._start_cleanup_timer()
        self._position_window()

        # 设置窗口图标
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.png')
        if os.path.exists(icon_path):
            try:
                icon_img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon_img)
            except Exception:
                pass

        self.root.deiconify()
        self.root.attributes('-topmost', True)
        self.root.after(500, lambda: self.root.attributes('-topmost', False))
        self._load_items()

        self.root.bind('<Escape>', lambda e: self.hide())
        # 鼠标离开窗口后延迟隐藏
        self.root.bind('<Leave>', self._on_mouse_leave)
        self.root.bind('<Enter>', self._on_mouse_enter)
        self._hide_timer = None

        self.root.after(500, self._init_tray_and_hotkey)

    # ── UI 构建 ───────────────────────────────────────────────

    def _build_ui(self):
        """构建主界面"""
        colors = theme.colors
        self.root.configure(bg=colors['bg_secondary'])

        # 主容器（圆角模拟）
        self.container = tk.Frame(self.root, bg=colors['bg_primary'],
                                  highlightthickness=0)
        self.container.place(x=4, y=4, relwidth=0.995, relheight=0.995)

        # 标题栏
        self._build_title_bar()
        # 工具栏
        self._build_toolbar()
        # 分割线
        ttk.Separator(self.container, orient='horizontal').pack(fill='x')
        # 列表
        self._build_item_list()
        # 状态栏
        self._build_status_bar()

    def _build_title_bar(self):
        """构建标题栏"""
        colors = theme.colors
        self.title_bar = tk.Frame(self.container, bg=colors['bg_primary'],
                                  height=40)
        self.title_bar.pack(fill='x')
        self.title_bar.pack_propagate(False)

        # 拖拽
        self.title_bar.bind('<Button-1>', self._start_drag)
        self.title_bar.bind('<B1-Motion>', self._on_drag)
        self.title_bar.bind('<ButtonRelease-1>', self._on_drag_end)

        # Logo + 标题
        left = tk.Frame(self.title_bar, bg=colors['bg_primary'])
        left.pack(side='left', padx=14)

        tk.Label(left, text='📋', font=('Segoe UI', 13),
                 bg=colors['bg_primary']).pack(side='left')
        tk.Label(left, text=' Copyboard', font=('Microsoft YaHei UI', 11, 'bold'),
                 bg=colors['bg_primary'], fg=colors['text_primary']).pack(side='left')

        # 窗口计数
        self.pin_count_lbl = tk.Label(left, text='',
                                      font=('Microsoft YaHei UI', 9),
                                      bg=colors['bg_primary'],
                                      fg=colors['accent'])
        self.pin_count_lbl.pack(side='left', padx=(8, 0))

        # 按钮
        right = tk.Frame(self.title_bar, bg=colors['bg_primary'])
        right.pack(side='right', padx=8)
        self._title_btn(right, '✕', '关闭', lambda e: self.quit_app(), hover_color=colors['danger'])
        tk.Label(left, text=f'v{__version__}',
                 font=('Microsoft YaHei UI', 8),
                 bg=colors['bg_primary'], fg=colors['text_muted']).pack(side='left', padx=4)

        self._title_btn(right, '─', '最小化', lambda e: self.hide())
        self._title_btn(right, '⚙', '设置', lambda e: self._show_settings())
        self._title_btn(right, '🎨', '切换主题', lambda e: self._cycle_theme())

    def _title_btn(self, parent, text, tooltip, cmd, hover_color=None):
        """创建标题栏按钮"""
        colors = theme.colors
        btn = tk.Label(parent, text=text, font=('Segoe UI', 10),
                       bg=colors['bg_primary'], fg=colors['text_muted'],
                       padx=6, cursor='hand2')
        btn.pack(side='right')

        hc = hover_color or colors['text_primary']
        btn.bind('<Enter>', lambda e, b=btn: b.configure(fg=hc, bg=colors['bg_secondary']))
        btn.bind('<Leave>', lambda e, b=btn: b.configure(fg=colors['text_muted'], bg=colors['bg_primary']))
        btn.bind('<Button-1>', cmd)
        return btn

    def _build_toolbar(self):
        """构建搜索和筛选工具栏"""
        colors = theme.colors
        self.toolbar = tk.Frame(self.container, bg=colors['bg_primary'])
        self.toolbar.pack(fill='x', padx=14, pady=(10, 6))

        # 搜索框
        search_frame = tk.Frame(self.toolbar, bg=colors['bg_input'])
        search_frame.pack(fill='x', pady=(0, 8))

        # 搜索图标
        search_icon = tk.Label(search_frame, text='🔍', font=('Segoe UI', 11),
                               bg=colors['bg_input'], fg=colors['text_muted'])
        search_icon.pack(side='left', padx=(10, 6))

        # 输入框
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *a: self._on_search())
        self.search_entry = tk.Entry(
            search_frame, textvariable=self.search_var,
            font=('Microsoft YaHei UI', 11),
            bg=colors['bg_input'], fg=colors['text_primary'],
            insertbackground=colors['accent'],
            relief='flat', bd=0,
        )
        self.search_entry.pack(side='left', fill='x', expand=True, pady=8, padx=(0, 8))

        # 清除按钮
        self.clear_btn = tk.Label(search_frame, text='✕', font=('Segoe UI', 10),
                                   bg=colors['bg_input'], fg=colors['text_muted'],
                                   cursor='hand2')
        self.clear_btn.pack(side='right', padx=10)
        self.clear_btn.bind('<Button-1>', lambda e: self._clear_search())
        self.clear_btn.bind('<Enter>', lambda e: self.clear_btn.configure(
            fg=colors['text_primary']))
        self.clear_btn.bind('<Leave>', lambda e: self.clear_btn.configure(
            fg=colors['text_muted']))

        # 筛选行 — 使用 Chip 风格
        filter_row = tk.Frame(self.toolbar, bg=colors['bg_primary'])
        filter_row.pack(fill='x')

        self.filter_chips = {}
        self._create_filter_chips(filter_row, 'type',
                                  [('全部', ''), ('文字', 'text'), ('图片', 'image'),
                                   ('文件', 'file'), ('文件夹', 'folder')])

        # 收藏夹切换按钮
        self.fav_btn = tk.Label(
            filter_row, text='⭐ 收藏', font=('Microsoft YaHei UI', 9),
            bg=colors['bg_input'], fg=colors['text_secondary'],
            padx=10, pady=4, cursor='hand2',
        )
        self.fav_btn.pack(side='right', padx=2)
        self.fav_btn._active = False
        self.fav_btn.bind('<Button-1>', lambda e: self._toggle_favorites())
        self.fav_btn.bind('<Enter>', lambda e: self.fav_btn.configure(
            bg=colors['favorite_light'], fg=colors['favorite'])
            if not self.fav_btn._active else None)
        self.fav_btn.bind('<Leave>', lambda e: self.fav_btn.configure(
            bg=colors['favorite'] if self.fav_btn._active else colors['bg_input'],
            fg='white' if self.fav_btn._active else colors['text_secondary']))


    def _create_filter_chips(self, parent, key, options):
        """创建 Chip 风格筛选按钮"""
        colors = theme.colors
        chips_frame = tk.Frame(parent, bg=colors['bg_primary'])
        chips_frame.pack(side='left')

        self.filter_chips[key] = {}
        first = True
        for label, value in options:
            chip = tk.Label(
                chips_frame,
                text=label,
                font=('Microsoft YaHei UI', 9),
                bg=colors['accent'] if (first and value == '') else colors['bg_input'],
                fg='white' if (first and value == '') else colors['text_secondary'],
                padx=10, pady=4,
                cursor='hand2',
            )
            chip.pack(side='left', padx=2)
            chip._key = key
            chip._val = value
            chip._selected = (first and value == '')
            chip.bind('<Button-1>', lambda e, c=chip: self._on_chip_click(c))
            chip.bind('<Enter>', lambda e, c=chip: (
                c.configure(bg=colors['accent_light'], fg=colors['accent'])
                if not c._selected else None))
            chip.bind('<Leave>', lambda e, c=chip: (
                c.configure(bg=colors['accent'], fg='white') if c._selected
                else c.configure(bg=colors['bg_input'], fg=colors['text_secondary'])))
            self.filter_chips[key][value] = chip
            first = False

    def _on_chip_click(self, chip):
        """Chip 点击处理"""
        colors = theme.colors
        # 取消同组所有选中
        for v, c in self.filter_chips.get(chip._key, {}).items():
            c._selected = False
            c.configure(bg=colors['bg_input'], fg=colors['text_secondary'])

        # 选中当前
        chip._selected = True
        chip.configure(bg=colors['accent'], fg='white')

        self._on_filter_change()

    def _build_item_list(self):
        """构建条目列表"""
        colors = theme.colors
        self.list_canvas = tk.Canvas(
            self.container, bg=colors['bg_secondary'],
            highlightthickness=0,
        )

        # 自定义滚动条
        self.scrollbar = tk.Canvas(
            self.container, bg=colors['bg_secondary'],
            highlightthickness=0, width=6,
        )
        self.scrollbar.pack(side='right', fill='y')

        self.list_frame = tk.Frame(self.list_canvas, bg=colors['bg_secondary'])
        self.list_frame.bind('<Configure>',
                             lambda e: self.list_canvas.configure(
                                 scrollregion=self.list_canvas.bbox('all')))

        self.canvas_window = self.list_canvas.create_window(
            (0, 0), window=self.list_frame, anchor='nw')

        self.list_canvas.pack(side='left', fill='both', expand=True)

        # ── 滚轮滚动（Windows + Linux 兼容，边界检测） ──
        def _on_mousewheel(event):
            """滚轮滚动，到达顶部/底部时停止"""
            # 获取当前可视区域位置 (0.0 = 顶部, 1.0 = 底部)
            top, bottom = self.list_canvas.yview()

            # 判断滚动方向
            if event.delta:
                scroll_down = event.delta < 0   # Windows: 负值=向下
            elif event.num == 5:
                scroll_down = True
            elif event.num == 4:
                scroll_down = False
            else:
                return

            # 边界检测
            if scroll_down and bottom >= 1.0:
                return  # 已到底部，不继续滚
            if not scroll_down and top <= 0.0:
                return  # 已到顶部，不继续滚

            # 计算滚动量
            if event.delta:
                scroll = -1 * (event.delta // 60)
            elif event.num == 4:
                scroll = -3
            elif event.num == 5:
                scroll = 3
            else:
                scroll = 0

            self.list_canvas.yview_scroll(scroll, 'units')

        # 绑定到 Canvas
        self.list_canvas.bind('<MouseWheel>', _on_mousewheel)
        self.list_canvas.bind('<Button-4>', _on_mousewheel)
        self.list_canvas.bind('<Button-5>', _on_mousewheel)

        # 绑定到整个主窗口，让列表区域外也能滚动
        self.container.bind('<MouseWheel>', _on_mousewheel)
        self.root.bind('<MouseWheel>', _on_mousewheel)

        # 绑定画布大小变化
        self.list_canvas.bind('<Configure>', self._on_canvas_resize)
        self._show_empty_state()

    def _on_canvas_resize(self, event):
        """画布大小变化时调整内框宽度"""
        self.list_canvas.itemconfig(self.canvas_window, width=event.width)

    def _build_status_bar(self):
        """构建底部状态栏"""
        colors = theme.colors
        self.status_bar = tk.Frame(self.container, bg=colors['bg_secondary'],
                                   height=30)
        self.status_bar.pack(fill='x', side='bottom')
        self.status_bar.pack_propagate(False)

        self.status_label = tk.Label(
            self.status_bar,
            text='',
            font=('Microsoft YaHei UI', 9),
            bg=colors['bg_secondary'], fg=colors['text_muted'],
            padx=14,
        )
        self.status_label.pack(side='left')

    # ── 窗口控制 ──────────────────────────────────────────────

    def _start_drag(self, event):
        self._drag_x, self._drag_y = event.x, event.y
        self._dock_edge = None  # 当前吸附的边缘

    def _on_drag(self, event):
        self.root.geometry(f'+{self.root.winfo_x() + event.x - self._drag_x}'
                           f'+{self.root.winfo_y() + event.y - self._drag_y}')

    def _on_drag_end(self, event):
        """拖拽结束后检测是否靠近屏幕边缘，是则自动隐藏"""
        x, y = self.root.winfo_x(), self.root.winfo_y()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        threshold = 30

        edge = None
        if x <= threshold:    edge = 'left'
        elif x + w >= sw - threshold: edge = 'right'
        elif y <= threshold:  edge = 'top'

        if edge:
            self._dock_edge = edge
            self._slide_out(edge, x, y, w, h, sw, sh)
        else:
            self._dock_edge = None
            self._destroy_edge_tab()

    def _slide_out(self, edge, x, y, w, h, sw, sh):
        """窗口滑出屏幕，仅留 6px 标签"""
        tab_size = 6
        targets = {
            'left':   (-w + tab_size, y),
            'right':  (sw - tab_size, y),
            'top':    (x, -h + tab_size),
        }
        tx, ty = targets[edge]

        # 简单动画：10 帧滑出
        for step in range(10):
            px = int(x + (tx - x) * (step + 1) / 10)
            py = int(y + (ty - y) * (step + 1) / 10)
            self.root.after(step * 15, lambda px=px, py=py: self.root.geometry(f'+{px}+{py}'))

        # 显示边缘标签
        self.root.after(200, lambda: self._show_edge_tab(edge, tx, ty, w, h))

    def _show_edge_tab(self, edge, x, y, w, h):
        """在屏幕边缘显示彩色标签条"""
        colors = theme.colors
        if hasattr(self, '_edge_tab') and self._edge_tab:
            self._edge_tab.destroy()

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self._edge_tab = tk.Toplevel(self.master)
        self._edge_tab.overrideredirect(True)
        self._edge_tab.attributes('-topmost', True)
        self._edge_tab.configure(bg=colors['accent'])

        tab = 6
        if edge == 'left':
            self._edge_tab.geometry(f'{tab}x{h}+0+{y}')
        elif edge == 'right':
            self._edge_tab.geometry(f'{tab}x{h}+{sw - tab}+{y}')
        elif edge == 'top':
            self._edge_tab.geometry(f'{w}x{tab}+{x}+0')

        self._edge_tab.bind('<Enter>', lambda e: self._slide_in(edge))
        self._edge_tab.lift()

    def _slide_in(self, edge):
        """鼠标悬停标签 → 窗口滑入"""
        if hasattr(self, '_edge_tab') and self._edge_tab:
            self._edge_tab.destroy()
            self._edge_tab = None

        x, y = self.root.winfo_x(), self.root.winfo_y()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.deiconify()

        targets = {'left': (4, y), 'right': (sw - w - 4, y), 'top': (x, 4)}
        tx, ty = targets[edge]

        for step in range(8):
            px = int(x + (tx - x) * (step + 1) / 8)
            py = int(y + (ty - y) * (step + 1) / 8)
            self.root.after(step * 15, lambda px=px, py=py: self.root.geometry(f'+{px}+{py}'))

        self.root.after(150, lambda: self.root.lift())
        self.root.after(150, lambda: self.root.focus_force())
        self._dock_edge = None

    def _destroy_edge_tab(self):
        if hasattr(self, '_edge_tab') and self._edge_tab:
            self._edge_tab.destroy()
            self._edge_tab = None

    def _on_mouse_leave(self, event):
        """鼠标离开窗口 → 延迟后滑出到边缘"""
        delay = int(settings.get('hide_delay_ms') or '0')
        if delay <= 0:
            return
        if self._hide_timer:
            self.root.after_cancel(self._hide_timer)
        self._hide_timer = self.root.after(delay, self._check_mouse_gone)

    def _on_mouse_enter(self, event):
        """鼠标进入 → 取消隐藏计时"""
        if self._hide_timer:
            self.root.after_cancel(self._hide_timer)
            self._hide_timer = None

    def _check_mouse_gone(self):
        """确认鼠标是否仍在窗口内，不在且窗口靠边时才滑出"""
        x, y = self.root.winfo_pointerxy()
        wx, wy = self.root.winfo_x(), self.root.winfo_y()
        ww, wh = self.root.winfo_width(), self.root.winfo_height()
        if (wx <= x <= wx + ww and wy <= y <= wy + wh):
            return  # 鼠标还在窗口内

        # 仅当窗口已在边缘时才滑出
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        threshold = 30
        if wx <= threshold:
            edge = 'left'
        elif wx + ww >= sw - threshold:
            edge = 'right'
        elif wy <= threshold:
            edge = 'top'
        else:
            return  # 不靠边，不隐藏

        self._dock_edge = edge
        self._slide_out(edge, wx, wy, ww, wh, sw, sh)

    def _position_window(self):
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - 440) // 2
        y = (screen_h - 700) // 2
        self.root.geometry(f'+{x}+{y}')

    def hide(self):
        self.root.withdraw()

    def show(self):
        self._destroy_edge_tab()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self._load_items()
        # 如果窗口处于吸附隐藏状态，滑入到正常位置
        if hasattr(self, '_dock_edge') and self._dock_edge:
            edge = self._dock_edge
            self._dock_edge = None
            x, y = self.root.winfo_x(), self.root.winfo_y()
            w = self.root.winfo_width()
            sw = self.root.winfo_screenwidth()
            targets = {'left': (4, y), 'right': (sw - w - 4, y), 'top': (x, 4)}
            if edge in targets:
                tx, ty = targets[edge]
                self.root.geometry(f'+{tx}+{ty}')
                self.root.lift()
                self.root.focus_force()

    def toggle(self):
        if self.root.state() == 'withdrawn':
            self.show()
        else:
            self.hide()

    def _add_resize_grip(self):
        """右下角拖拽缩放手柄"""
        colors = theme.colors
        self._grip = tk.Label(
            self.root, text='⤡', font=('Segoe UI', 10),
            bg=colors['bg_primary'], fg=colors['text_muted'],
            cursor='bottom_right_corner',
        )
        self._grip.place(relx=1.0, rely=1.0, anchor='se', x=-4, y=-4)
        self._grip.bind('<Button-1>', self._start_resize)
        self._grip.bind('<B1-Motion>', self._on_resize)
        self._grip.lift()

    def _start_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.root.winfo_width()
        self._resize_start_h = self.root.winfo_height()

    def _on_resize(self, event):
        dx = event.x_root - self._resize_start_x
        dy = event.y_root - self._resize_start_y
        new_w = max(340, self._resize_start_w + dx)
        new_h = max(420, self._resize_start_h + dy)
        self.root.geometry(f'{new_w}x{new_h}')

    def quit_app(self):
        monitor.stop()
        unregister_hotkey()
        db.close()
        self.master.destroy()
        sys.exit(0)

    def _init_tray_and_hotkey(self):
        try:
            run_tray(self)
        except Exception as e:
            print(f"[Main] 托盘失败: {e}")
        try:
            register_hotkey(self)
        except Exception as e:
            print(f"[Main] 快捷键失败: {e}")

    # ── 数据加载 ──────────────────────────────────────────────

    def _load_items(self, filter_dict=None):
        if filter_dict is None:
            filter_dict = {}
        self.current_filter = filter_dict

        query = self.search_var.get().strip()
        if query:
            self.items = db.search_items(query, filter_dict)
            if query:
                self.items = self._fuzzy_filter(self.items, query)
        else:
            self.items = db.get_items(filter_dict)

        self._render_list()

    def _fuzzy_filter(self, items, query):
        q = query.lower()
        scored = []
        for item in items:
            s = self._calc_score(item, q)
            if s > 0:
                scored.append((s, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in scored]

    def _calc_score(self, item, q):
        """模糊匹配 — 搜索文字内容 + 图片/文件/文件夹名"""
        # 收集所有可搜索文本
        texts = []
        if item.get('content'):
            texts.append(item['content'])
        if item.get('image_path'):
            texts.append(os.path.basename(item['image_path']))
        if item.get('file_paths'):
            try:
                for p in json.loads(item['file_paths']):
                    texts.append(os.path.basename(p))
            except Exception:
                pass

        best = 0
        for text in texts:
            if not text:
                continue
            t = text.lower()
            if q in t:
                score = 100 if t.startswith(q) else 90
                best = max(best, score)
                continue
            # 顺序模糊匹配
            last_idx, gaps, ok = -1, 0, True
            for ch in q:
                idx = t.find(ch, last_idx + 1)
                if idx == -1:
                    ok = False; break
                gaps += idx - last_idx - 1
                last_idx = idx
            if ok:
                best = max(best, max(1, int((len(t) - gaps) / len(t) * 80)))
        return best

    # ── 列表渲染 ──────────────────────────────────────────────

    def _render_list(self):
        colors = theme.colors
        for w in self.list_frame.winfo_children():
            w.destroy()

        if not self.items:
            self._show_empty_state()
            self._update_status()
            return

        if hasattr(self, 'empty_frame') and self.empty_frame:
            self.empty_frame.destroy()
            self.empty_frame = None

        # 排序
        pinned = [i for i in self.items if i['is_pinned']]
        unpinned = [i for i in self.items if not i['is_pinned']]
        unpinned.sort(key=lambda x: x['created_at'], reverse=True)
        sorted_items = pinned + unpinned

        for item in sorted_items:
            self._create_card(item)

        self._update_status()

    def _create_card(self, item):
        """创建条目卡片 — 三行式布局"""
        colors = theme.colors
        item_id = item['id']
        is_pinned = item['is_pinned']
        is_fav = item['is_favorite']

        # 类型颜色
        type_accent = {
            'text': colors['type_text'],
            'image': colors['type_image'],
            'file': colors['type_file'],
            'folder': colors['type_folder'],
        }.get(item['type'], colors['accent'])

        # 外层
        wrap = tk.Frame(self.list_frame, bg=colors['bg_secondary'])
        wrap.pack(fill='x', padx=12, pady=3)

        card_bg = colors['bg_pinned'] if is_pinned else colors['bg_card']
        card = tk.Frame(wrap, bg=card_bg, cursor='hand2')
        card.pack(fill='x')

        # 左侧色条
        tk.Frame(card, bg=type_accent, width=4).place(x=0, y=0, relheight=1.0, width=4)

        inner = tk.Frame(card, bg=card_bg)
        inner.pack(fill='x', padx=(16, 12), pady=12)

        # ── 第一行：类型图标 + 类型标签 ──
        row1 = tk.Frame(inner, bg=card_bg)
        row1.pack(fill='x')

        type_info = self._get_type_info(item)
        tk.Label(row1, text=f"{type_info['icon']}  {type_info['label']}",
                 font=('Microsoft YaHei UI', 9),
                 bg=card_bg, fg=type_accent, anchor='w').pack(side='left')

        # 元数据标记（置顶/收藏）
        if is_pinned:
            tk.Label(row1, text='📌 置顶', font=('Microsoft YaHei UI', 8),
                     bg=card_bg, fg=colors['pin']).pack(side='right', padx=(4, 0))
        if is_fav:
            tk.Label(row1, text='★', font=('Microsoft YaHei UI', 8),
                     bg=card_bg, fg=colors['favorite']).pack(side='right')

        # ── 第二行：名称/内容（居中放大） ──
        content_text = self._get_display_name(item)
        content_lbl = tk.Label(
            inner, text=content_text,
            font=('Microsoft YaHei UI', 12),
            bg=card_bg, fg=colors['text_primary'],
            anchor='w', justify='left', wraplength=350,
        )
        content_lbl.pack(anchor='w', fill='x', pady=(8, 8))

        # ── 第三行：时间 + 操作按钮 ──
        row3 = tk.Frame(inner, bg=card_bg)
        row3.pack(fill='x')

        tk.Label(row3, text=f'🕐 {self._format_time(item["created_at"])}',
                 font=('Microsoft YaHei UI', 9),
                 bg=card_bg, fg=colors['text_muted'], anchor='w').pack(side='left')

        actions = tk.Frame(row3, bg=card_bg)
        actions.pack(side='right')

        self._action_btn(actions, '📋', 'copy', item_id, item, colors,
                         hover_color=colors['accent'])
        self._action_btn(actions,
                         '★' if is_fav else '☆', 'fav', item_id, item, colors,
                         active_color=colors['favorite'] if is_fav else None,
                         default_color=colors['favorite'] if is_fav else colors['text_muted'])
        self._action_btn(actions, '🗑', 'del', item_id, item, colors,
                         hover_color=colors['danger'])

        # ── 点击卡片主体 = 粘贴 ──
        for w in [card, inner, row1, content_lbl, wrap]:
            w.bind('<Button-1>', lambda e, iid=item_id: self._paste_item(iid))

        # ── 悬停 ──
        hover_bg = colors['bg_card_hover']
        def _enter(e):
            if not is_pinned:
                card.configure(bg=hover_bg); inner.configure(bg=hover_bg)
                row1.configure(bg=hover_bg); content_lbl.configure(bg=hover_bg)
                row3.configure(bg=hover_bg)
        def _leave(e):
            card.configure(bg=card_bg); inner.configure(bg=card_bg)
            row1.configure(bg=card_bg); content_lbl.configure(bg=card_bg)
            row3.configure(bg=card_bg)

        card.bind('<Enter>', _enter)
        card.bind('<Leave>', _leave)

    def _action_btn(self, parent, text, action_type, item_id, item, colors,
                    hover_color=None, default_color=None, active_color=None):
        """创建操作按钮"""
        df = default_color or colors['text_muted']
        btn = tk.Label(parent, text=text, font=('Segoe UI', 10),
                       bg=parent.cget('bg'), fg=df,
                       padx=5, cursor='hand2')
        btn.pack(side='right')
        btn._action_type = action_type
        btn._default_color = df
        btn._active_color = active_color

        hc = hover_color or colors['accent']
        btn.bind('<Enter>', lambda e, b=btn: b.configure(fg=hc))
        btn.bind('<Leave>', lambda e, b=btn: b.configure(
            fg=b._active_color if b._active_color else b._default_color))

        if action_type == 'pin':
            btn.bind('<Button-1>', lambda e, iid=item_id, b=btn: self._toggle_pin(iid, b))
        elif action_type == 'fav':
            btn.bind('<Button-1>', lambda e, iid=item_id, b=btn: self._toggle_favorite(iid, b))
        elif action_type == 'copy':
            btn.bind('<Button-1>', lambda e, iid=item_id: self._quick_copy(iid))
        elif action_type == 'del':
            btn.bind('<Button-1>', lambda e, iid=item_id: self._delete_item(iid))

        return btn

    def _get_type_info(self, item):
        """获取类型图标和描述标签"""
        t = item['type']

        if t == 'text':
            chars = item.get('char_count', 0)
            if chars > 500:
                return {'icon': '📄', 'label': f'长文本 ({chars} 字)'}
            return {'icon': '📝', 'label': f'文本 ({chars} 字)'}

        if t == 'image':
            w = item.get('image_width', 0)
            h = item.get('image_height', 0)
            if item.get('content'):
                # 图片文件，显示扩展名
                ext = os.path.splitext(item['content'])[1].lower()
                ext_name = _get_ext_name(ext)
                size = f'{w}x{h}' if w and h else ''
                return {'icon': '🖼', 'label': f'{ext_name}图片  {size}'.strip()}
            size = f'{w}x{h}' if w and h else ''
            return {'icon': '🖼', 'label': f'图片  {size}'.strip()}

        if t == 'folder':
            count = item.get('char_count', 0) or item.get('file_count', 0)
            return {'icon': '📁', 'label': f'文件夹 ({count} 项)' if count else '文件夹'}

        if t == 'file':
            content = item.get('content', '')
            if content:
                # 提取第一个文件的扩展名
                name = content.split(',')[0].strip()
                ext = os.path.splitext(name)[1].lower()
            else:
                try:
                    paths = json.loads(item.get('file_paths', '[]'))
                    name = os.path.basename(paths[0]) if paths else ''
                    ext = os.path.splitext(name)[1].lower()
                except Exception:
                    ext = ''
            count = item.get('file_count', 0)
            ext_name = _get_ext_name(ext)
            return {'icon': '📄', 'label': f'{ext_name}文件' if not count or count <= 1 else f'{ext_name}文件 ({count} 个)'}

        return {'icon': '📋', 'label': '其他'}

    def _get_display_name(self, item):
        """获取条目显示名称"""
        t = item['type']

        if t == 'text':
            text = item.get('content', '').replace('\n', ' ').replace('\r', '').strip()
            if len(text) > 60:
                text = text[:60] + '…'
            return text if text else '(空内容)'

        if t == 'image':
            if item.get('content'):
                return item['content']  # 文件名
            return f"图片 {item.get('image_width', '?')}×{item.get('image_height', '?')}"

        if t == 'folder':
            return item.get('content', '文件夹')

        if t == 'file':
            content = item.get('content', '')
            if content:
                names = [n.strip() for n in content.split(',')[:3]]
                return ' · '.join(names)
            try:
                paths = json.loads(item.get('file_paths', '[]'))
                names = [os.path.basename(p) for p in paths[:3]]
                result = ' · '.join(names)
                if len(paths) > 3:
                    result += f'  等 {len(paths)} 个'
                return result
            except Exception:
                return '文件列表'

        return '未知条目'

    def _show_empty_state(self):
        """显示空状态"""
        colors = theme.colors
        self.empty_frame = tk.Frame(self.list_frame, bg=colors['bg_secondary'])
        self.empty_frame.pack(fill='both', expand=True)

        # 居中容器
        center = tk.Frame(self.empty_frame, bg=colors['bg_secondary'])
        center.place(relx=0.5, rely=0.45, anchor='center')

        # 图标
        tk.Label(center, text='📋', font=('Segoe UI', 48),
                 bg=colors['bg_secondary']).pack(pady=(0, 12))

        # 标题
        tk.Label(center, text='还没有剪贴板记录',
                 font=('Microsoft YaHei UI', 13, 'bold'),
                 bg=colors['bg_secondary'],
                 fg=colors['text_primary']).pack()

        # 提示
        tk.Label(center, text='复制文字、图片或文件后会自动出现',
                 font=('Microsoft YaHei UI', 10),
                 bg=colors['bg_secondary'],
                 fg=colors['text_muted']).pack(pady=(4, 14))

        # 快捷键
        kb = tk.Frame(center, bg=colors['bg_secondary'])
        kb.pack()
        for text, is_key in [('Alt', True), (' + ', False), ('V', True), ('  呼出面板', False)]:
            if is_key:
                k = tk.Frame(kb, bg=colors['bg_card'],
                             highlightbackground=colors['border'],
                             highlightthickness=1)
                k.pack(side='left')
                tk.Label(k, text=text, font=('Microsoft YaHei UI', 10, 'bold'),
                         bg=colors['bg_card'], fg=colors['text_secondary'],
                         padx=8, pady=4).pack()
            else:
                tk.Label(kb, text=text, font=('Microsoft YaHei UI', 10),
                         bg=colors['bg_secondary'],
                         fg=colors['text_muted']).pack(side='left')

    def _update_status(self):
        """更新状态栏"""
        total = len(self.items)
        pinned_count = sum(1 for i in self.items if i['is_pinned'])
        text_count = sum(1 for i in self.items if i['type'] == 'text')
        img_count = sum(1 for i in self.items if i['type'] == 'image')
        file_count = sum(1 for i in self.items if i['type'] == 'file')
        folder_count = sum(1 for i in self.items if i['type'] == 'folder')

        parts = [f'共 {total} 条']
        if pinned_count:
            parts.append(f'📌 {pinned_count}')
        if text_count:
            parts.append(f'📝 {text_count}')
        if img_count:
            parts.append(f'🖼 {img_count}')
        if file_count:
            parts.append(f'📄 {file_count}')
        if folder_count:
            parts.append(f'📁 {folder_count}')

        self.status_label.config(text='  ·  '.join(parts))

        # 更新标题栏置顶计数
        if pinned_count:
            self.pin_count_lbl.config(text=f'📌{pinned_count}')
        else:
            self.pin_count_lbl.config(text='')

    # ── 操作处理 ──────────────────────────────────────────────

    def _quick_copy(self, item_id):
        """一键复制 — 仅复制到剪贴板，不隐藏窗口"""
        item = db.get_item_by_id(item_id)
        if not item:
            return
        try:
            if item['type'] == 'text':
                self.root.clipboard_clear()
                self.root.clipboard_append(item['content'])
            elif item['type'] in ('image', 'file', 'folder'):
                # 复用粘贴逻辑
                self._do_paste(item)
            db.touch_item(item_id)
            self.toast.show('已复制', style='success')
        except Exception as e:
            self._show_copy_error(item, e)

    def _do_paste(self, item):
        """执行剪贴板写入（不隐藏窗口）"""
        if item['type'] == 'text':
            self.root.clipboard_clear()
            self.root.clipboard_append(item['content'])
        elif item['type'] == 'image':
            self._paste_image(item)
        elif item['type'] in ('folder', 'file'):
            self._paste_files(item)

    def _paste_item(self, item_id):
        """点击卡片 — 复制并隐藏窗口"""
        item = db.get_item_by_id(item_id)
        if not item:
            return
        try:
            self._do_paste(item)
            db.touch_item(item_id)
            self.toast.show('已复制到剪贴板', style='success')
            self.hide()
        except Exception as e:
            self._show_copy_error(item, e)

    def _paste_image(self, item):
        """将图片写入 Windows 剪贴板"""
        import io
        from PIL import Image

        image_path = item.get('image_path')
        if not image_path:
            return

        full_path = get_full_path(image_path)
        if not os.path.exists(full_path):
            return

        # 用 PIL 打开图片
        pil_img = Image.open(full_path)

        # 方式1: 使用 ctypes 将图片转换为 DIB 并写入剪贴板
        try:
            self._set_clipboard_image_dib(pil_img)
            return
        except Exception as e:
            print(f"[Paste] DIB 方式失败，尝试备用: {e}")

        # 方式2: 通过 tkinter PhotoImage（仅限 PNG/GIF）
        try:
            self.root.clipboard_clear()
            # 保存为临时 BMP 来适配 tkinter
            tmp_path = os.path.join(os.path.dirname(full_path), '_clipboard_temp.png')
            pil_img.save(tmp_path, 'PNG')
            photo = tk.PhotoImage(file=tmp_path)
            self.root.clipboard_append(photo)
        except Exception:
            # 方式3: 文本方式（最后备用）
            b64 = read_thumb_base64(image_path)
            if b64:
                self.root.clipboard_clear()
                self.root.clipboard_append(b64)

    def _set_clipboard_image_dib(self, pil_img):
        """使用 Windows API 将 PIL Image 以 DIB 格式写入剪贴板"""
        import ctypes
        import ctypes.wintypes
        from io import BytesIO

        # 转换为 BMP (DIB)
        buf = BytesIO()
        pil_img.convert('RGB').save(buf, format='BMP')
        bmp_data = buf.getvalue()

        # BMP 文件头 14 字节 + DIB 数据
        # DIB 数据 = BMP 数据跳过前 14 字节文件头
        dib_data = bmp_data[14:]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        CF_DIB = 8

        # 分配全局内存
        size = len(dib_data)
        hglobal = kernel32.GlobalAlloc(0x0002, size)  # GMEM_MOVEABLE

        if hglobal:
            ptr = kernel32.GlobalLock(hglobal)
            if ptr:
                ctypes.memmove(ctypes.c_void_p(ptr), dib_data, size)
                kernel32.GlobalUnlock(hglobal)

                if user32.OpenClipboard(0):
                    user32.EmptyClipboard()
                    user32.SetClipboardData(CF_DIB, hglobal)
                    user32.CloseClipboard()
                else:
                    kernel32.GlobalFree(hglobal)

    def _paste_files(self, item):
        """将文件路径写入剪贴板（兼容轻量/完整两种模式）"""
        import ctypes
        import ctypes.wintypes

        # 优先用存储路径（完整模式），其次用原始路径（轻量模式）
        paths = []
        for key in ('stored_paths', 'file_paths'):
            raw = item.get(key)
            if raw:
                try:
                    parsed = json.loads(raw)
                    if key == 'stored_paths':
                        paths = [get_full_path(p) for p in parsed]
                    else:
                        paths = parsed
                    if paths:
                        break
                except Exception:
                    pass

        if not paths:
            return

        # 筛选现存文件
        existing = [p for p in paths if os.path.exists(p)]
        if not existing:
            self.root.clipboard_clear()
            self.root.clipboard_append('\n'.join(paths))
            return

        # 使用 Windows API 写入 CF_HDROP
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32

        # 计算结构大小
        # DROPFILES = { DWORD pFiles; POINT pt; BOOL fNC; BOOL fWide; } + 文件路径列表（双 null 终止）
        DROPFILES_HEADER_SIZE = 20  # sizeof(DROPFILES)
        paths_null_terminated = '\0'.join(existing) + '\0\0'
        paths_bytes = paths_null_terminated.encode('utf-16-le')
        total_size = DROPFILES_HEADER_SIZE + len(paths_bytes)

        hglobal = kernel32.GlobalAlloc(0x0002, total_size)  # GMEM_MOVEABLE
        if hglobal:
            ptr = kernel32.GlobalLock(hglobal)
            if ptr:
                # 写入 DROPFILES 头
                ctypes.memmove(ctypes.c_void_p(ptr),
                               (ctypes.c_uint32 * 5)(20, 0, 0, 0, 1),
                               DROPFILES_HEADER_SIZE)
                # 写入文件路径
                ctypes.memmove(ctypes.c_void_p(ptr + DROPFILES_HEADER_SIZE),
                               paths_bytes, len(paths_bytes))
                kernel32.GlobalUnlock(hglobal)

                if user32.OpenClipboard(0):
                    user32.EmptyClipboard()
                    user32.SetClipboardData(15, hglobal)  # CF_HDROP = 15
                    user32.CloseClipboard()
                else:
                    kernel32.GlobalFree(hglobal)

    def _show_copy_error(self, item, error):
        """复制失败弹窗，说明具体原因"""
        from tkinter import messagebox
        t = item['type']
        if t == 'text':
            reason = '文字内容可能为空，或剪贴板被其他程序占用'
        elif t == 'image':
            thumb = get_full_path(item.get('image_path', ''))
            if not os.path.exists(thumb):
                reason = '图片缩略图文件已丢失'
            else:
                reason = '图片数据无法写入剪贴板，可能被其他程序占用'
        elif t in ('file', 'folder'):
            raw = item.get('file_paths') or item.get('stored_paths') or '[]'
            try:
                paths = json.loads(raw)
                missing = [p for p in paths if not os.path.exists(p)]
                if missing and not item.get('stored_paths'):
                    reason = f'以下文件已不存在:\n{chr(10).join(missing[:3])}'
                    if len(missing) > 3:
                        reason += f'\n...等 {len(missing)} 个'
                else:
                    reason = '文件路径无法写入剪贴板'
            except Exception:
                reason = '文件路径数据已损坏'
        else:
            reason = '未知条目类型'
        messagebox.showerror('复制失败', f'{reason}\n\n详细信息: {str(error)[:200]}')

    def _toggle_pin(self, item_id, btn=None):
        item = db.get_item_by_id(item_id)
        if item:
            new = not item['is_pinned']
            db.pin_item(item_id, new)
            self.toast.show('已置顶' if new else '已取消置顶', style='pin')
            self._load_items(self.current_filter)  # 置顶改变排序，需要刷新

    def _toggle_favorite(self, item_id, btn=None):
        item = db.get_item_by_id(item_id)
        if item:
            new = not item['is_favorite']
            db.favorite_item(item_id, new)
            # 即时更新按钮图标
            if btn:
                colors = theme.colors
                if new:
                    btn.configure(text='★', fg=colors['favorite'])
                    btn._active_color = colors['favorite']
                else:
                    btn.configure(text='☆', fg=colors['text_muted'])
                    btn._active_color = None
            self.toast.show('已收藏' if new else '已取消收藏', style='star')
            # 如果正在看收藏夹且取消收藏，该项应该消失；否则不刷新
            if self.fav_btn._active and not new:
                self._load_items(self.current_filter)

    def _delete_item(self, item_id):
        item = db.delete_item(item_id)
        if item:
            if item.get('image_path'):
                delete_thumb(item['image_path'])
            if item.get('stored_paths'):
                try:
                    delete_stored_files(json.loads(item['stored_paths']))
                except Exception:
                    pass
            self.toast.show('已删除', style='delete')
            self._load_items(self.current_filter)

    def _on_new_item(self, item):
        self.root.after(0, lambda: self._load_items(self.current_filter))

    # ── 搜索筛选 ──────────────────────────────────────────────

    def _on_search(self, *args):
        if hasattr(self, '_search_timer'):
            self.root.after_cancel(self._search_timer)
        self._search_timer = self.root.after(250, self._load_items)

    def _clear_search(self):
        self.search_var.set('')
        self.search_entry.focus()

    def _on_filter_change(self):
        filter_dict = {}

        # 收藏夹筛选
        if hasattr(self, 'fav_btn') and self.fav_btn._active:
            filter_dict['favorites'] = True

        # 类型筛选
        for v, c in self.filter_chips.get('type', {}).items():
            if c._selected and v:
                filter_dict['type'] = v
                break

        self._load_items(filter_dict)

    def _toggle_favorites(self):
        """切换收藏夹视图"""
        colors = theme.colors
        self.fav_btn._active = not self.fav_btn._active
        if self.fav_btn._active:
            self.fav_btn.configure(bg=colors['favorite'], fg='white', text='⭐ 已收藏')
            self.toast.show('仅显示收藏条目', style='star')
        else:
            self.fav_btn.configure(bg=colors['bg_input'], fg=colors['text_secondary'], text='⭐ 收藏')
            self.toast.show('显示全部条目', style='info')
        self._on_filter_change()

    # ── 设置 ──────────────────────────────────────────────────

    def _show_settings(self):
        if not hasattr(self, '_settings_dialog'):
            self._settings_dialog = SettingsDialog(self.root, self._on_setting_changed)
        self._settings_dialog.show()

    def _on_setting_changed(self, key, value):
        if key == 'theme':
            self._apply_theme()
        if key == 'data_cleared':
            self._load_items()
            self.toast.show('所有数据已清理', style='delete')

    def _cycle_theme(self):
        new_theme = theme.cycle_theme()
        settings.set('theme', new_theme)
        self._apply_theme()
        self.toast.show(f'{THEMES[new_theme]["name"]} 主题', style='info')

    def _apply_theme(self):
        for widget in self.container.winfo_children():
            widget.destroy()
        self._build_ui()
        self._add_resize_grip()
        self._load_items(self.current_filter)

    # ── 清理 ──────────────────────────────────────────────────

    def _start_cleanup_timer(self):
        def cleanup():
            while True:
                time.sleep(60)
                try:
                    retention = int(settings.get('retention_days'))
                    max_items = int(settings.get('max_items'))
                    for items in [db.prune_old_items(retention), db.prune_excess_items(max_items)]:
                        for item in items:
                            if item.get('image_path'):
                                delete_thumb(item['image_path'])
                            if item.get('stored_paths'):
                                try:
                                    delete_stored_files(json.loads(item['stored_paths']))
                                except Exception:
                                    pass
                except Exception as e:
                    print(f"[Cleanup] {e}")

        threading.Thread(target=cleanup, daemon=True).start()

    # ── 时间格式化 ────────────────────────────────────────────

    def _format_time(self, iso_string):
        try:
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            diff = now - dt.replace(tzinfo=now.tzinfo) if dt.tzinfo else now - dt
            secs = diff.total_seconds()
            if secs < 5:
                return '刚刚'
            if secs < 60:
                return f'{int(secs)} 秒前'
            if secs < 3600:
                return f'{int(secs / 60)} 分钟前'
            if secs < 86400:
                return f'{int(secs / 3600)} 小时前'
            if secs < 172800:
                return '昨天'
            if secs < 604800:
                return f'{int(secs / 86400)} 天前'
            return f'{dt.month}月{dt.day}日'
        except Exception:
            return ''


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

def main():
    app = CopyboardApp()
    app.master.mainloop()


if __name__ == '__main__':
    main()
