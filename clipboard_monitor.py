"""
Copyboard — 剪贴板监听模块（低干扰模式）
通过 GetClipboardSequenceNumber 检测变更，仅在内容变化时打开剪贴板
"""

import hashlib
import os
import json
import ctypes
import ctypes.wintypes
from database import db
from file_store import save_image, save_image_file, record_paths, copy_files, classify_paths
import settings_manager as settings

# ── Windows API ──────────────────────────────────────────────

CF_HDROP = 15
IMAGE_FORMATS = {2, 8, 17}  # CF_BITMAP, CF_DIB, CF_DIBV5

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

GetClipboardSequenceNumber = user32.GetClipboardSequenceNumber
GetClipboardSequenceNumber.restype = ctypes.wintypes.DWORD


def _open_and_scan():
    """打开一次剪贴板，同时检查所有格式并提取数据"""
    if not user32.OpenClipboard(0):
        return None, False, False

    files, has_image, has_text, has_files = [], False, False, False
    try:
        fmt, formats = 0, set()
        while True:
            fmt = user32.EnumClipboardFormats(fmt)
            if fmt == 0:
                break
            formats.add(fmt)

        has_files = CF_HDROP in formats
        has_image = bool(formats & IMAGE_FORMATS)
        has_text = 1 in formats or 13 in formats  # CF_TEXT or CF_UNICODETEXT

        if has_files:
            hglobal = user32.GetClipboardData(CF_HDROP)
            if hglobal:
                hdrop = kernel32.GlobalLock(hglobal)
                if hdrop:
                    try:
                        count = shell32.DragQueryFileW(ctypes.c_void_p(hdrop), 0xFFFFFFFF, None, 0)
                        for i in range(count):
                            size = shell32.DragQueryFileW(ctypes.c_void_p(hdrop), i, None, 0)
                            if size > 0:
                                buf = ctypes.create_unicode_buffer(size + 1)
                                shell32.DragQueryFileW(ctypes.c_void_p(hdrop), i, buf, size + 1)
                                if buf.value:
                                    files.append(buf.value)
                    finally:
                        kernel32.GlobalUnlock(hglobal)
    finally:
        user32.CloseClipboard()

    return files, has_image, has_text


def _read_text(root):
    """仅当确认只有文字格式时读取文字内容"""
    try:
        import tkinter as tk
        text = root.clipboard_get()
        return text.strip() if text else ''
    except Exception:
        return ''


# ── 监听器 ───────────────────────────────────────────────────

class ClipboardMonitor:
    """低干扰剪贴板监听器，全部操作在主线程执行"""

    def __init__(self):
        self.last_hash = ''
        self.last_text = ''
        self.last_seq = 0
        self.running = False
        self.on_new_item = None
        self.root = None

    def start(self, root, callback=None):
        self.root = root
        self.on_new_item = callback
        self.running = True
        self._schedule()
        print("[Clipboard] 监听已启动（低干扰模式）")

    def stop(self):
        self.running = False

    def _schedule(self):
        if not self.running or not self.root:
            return
        try:
            interval = int(settings.get('poll_interval_ms'))
            self.root.after(interval, self._tick)
        except Exception:
            self.root.after(750, self._tick)

    def _tick(self):
        if not self.running:
            return
        try:
            seq = GetClipboardSequenceNumber()
            if seq != self.last_seq:
                self.last_seq = seq
                self._process()
        except Exception as e:
            print(f"[Clipboard] {e}")
        finally:
            self._schedule()

    def _process(self):
        """扫描剪贴板并写入数据库"""
        files, has_image, has_text = _open_and_scan()

        if files:
            self._handle_files(files)
            return
        if has_image:
            try:
                from PIL import ImageGrab, Image
                data = ImageGrab.grabclipboard()
                if isinstance(data, Image.Image):
                    self._handle_image(data)
                elif isinstance(data, list) and data:
                    self._handle_files(data)
            except Exception as e:
                print(f"[Clipboard] PIL: {e}")
            return
        if has_text and not files and not has_image:
            text = _read_text(self.root)
            if text:
                self._handle_text(text)

    def _handle_text(self, text):
        if text == self.last_text:
            return
        self.last_text = text
        h = hashlib.sha256(text.encode()).hexdigest()
        if h == self.last_hash:
            return
        self.last_hash = h
        item = db.add_item({'type': 'text', 'content': text, 'content_hash': h, 'char_count': len(text)})
        if self.on_new_item:
            self.on_new_item(item)

    def _handle_image(self, pil_img):
        saved = save_image(pil_img)
        if not saved or saved['hash'] == self.last_hash:
            return
        self.last_hash = saved['hash']
        self.last_text = ''
        item = db.add_item({'type': 'image', 'content_hash': saved['hash'],
                            'image_path': saved['image_path'],
                            'image_width': saved['width'], 'image_height': saved['height']})
        if self.on_new_item:
            self.on_new_item(item)

    def _handle_files(self, paths):
        if not paths:
            return
        h = hashlib.sha256('|'.join(sorted(str(p) for p in paths)).encode()).hexdigest()
        if h == self.last_hash:
            return
        self.last_text = ''

        c = classify_paths(paths)
        imgs, fils, dirs = c['images'], c['files'], c['folders']

        # 图片文件 -> image 类型
        if imgs and not fils and not dirs:
            for p in imgs:
                s = save_image_file(p)
                if s:
                    db.add_item({'type': 'image', 'content_hash': s['hash'],
                                 'image_path': s['image_path'],
                                 'image_width': s['width'], 'image_height': s['height'],
                                 'content': os.path.basename(p)})
                    if self.on_new_item:
                        self.on_new_item(s)
            self.last_hash = h
            return

        # 文件夹 -> folder 类型
        if dirs and not fils and not imgs:
            r = _store(dirs)
            self.last_hash = h
            if r['folder_count'] == 0:
                return
            db.add_item({'type': 'folder', 'content_hash': h,
                         'file_paths': json.dumps(r['original_paths'], ensure_ascii=False),
                         'stored_paths': json.dumps(r.get('stored_paths', []), ensure_ascii=False),
                         'file_count': r['file_count'],
                         'content': ', '.join(os.path.basename(p) for p in dirs)})
            if self.on_new_item:
                self.on_new_item(None)
            return

        # 普通文件或混合 -> file 类型
        r = _store(dirs + fils + imgs)
        self.last_hash = h
        if r['file_count'] + r['folder_count'] == 0:
            return
        db.add_item({'type': 'file', 'content_hash': h,
                     'file_paths': json.dumps(r['original_paths'], ensure_ascii=False),
                     'stored_paths': json.dumps(r.get('stored_paths', []), ensure_ascii=False),
                     'file_count': r['file_count'] + r['folder_count'],
                     'content': ', '.join(os.path.basename(p) for p in (dirs + fils + imgs)[:5])})
        if self.on_new_item:
            self.on_new_item(None)


def _store(paths):
    """根据 storage_mode 选择轻量记录或完整复制"""
    return copy_files(paths) if settings.get('storage_mode') == 'full' else record_paths(paths)


monitor = ClipboardMonitor()
