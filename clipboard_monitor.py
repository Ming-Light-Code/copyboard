"""
Copyboard — 剪贴板监听模块（低干扰优化版）
使用 GetClipboardSequenceNumber 减少剪贴板打开次数
"""

import hashlib
import os
import json
import ctypes
import ctypes.wintypes
from database import db
from file_store import (
    save_image, save_image_file, record_paths, copy_files, classify_paths
)
import settings_manager as settings


# ── Windows API ──────────────────────────────────────────────

CF_HDROP = 15
IMAGE_FORMATS = {2, 8, 17}  # CF_BITMAP, CF_DIB, CF_DIBV5

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

# GetClipboardSequenceNumber: 返回剪贴板变更计数，无需打开剪贴板
GetClipboardSequenceNumber = user32.GetClipboardSequenceNumber
GetClipboardSequenceNumber.restype = ctypes.wintypes.DWORD


def _check_clipboard_once():
    """
    一次性打开剪贴板，同时检查所有格式并提取数据。
    返回 (files, image, text) — 只有一种非空。
    尽量减少 OpenClipboard/CloseClipboard 调用次数。
    """
    files = []
    has_image = False
    has_text = False
    has_files = False

    if not user32.OpenClipboard(0):
        return None, None, None

    try:
        # 1. 枚举所有格式（一次遍历）
        fmt = 0
        formats = set()
        while True:
            fmt = user32.EnumClipboardFormats(fmt)
            if fmt == 0:
                break
            formats.add(fmt)

        has_files = CF_HDROP in formats
        has_image = bool(formats & IMAGE_FORMATS)
        has_text = (1 in formats) or (13 in formats)  # CF_TEXT or CF_UNICODETEXT

        # 2. 仅提取需要的数据
        if has_files:
            hglobal = user32.GetClipboardData(CF_HDROP)
            if hglobal:
                hdrop = kernel32.GlobalLock(hglobal)
                if hdrop:
                    try:
                        count = shell32.DragQueryFileW(
                            ctypes.c_void_p(hdrop), 0xFFFFFFFF, None, 0)
                        for i in range(count):
                            buf_size = shell32.DragQueryFileW(
                                ctypes.c_void_p(hdrop), i, None, 0)
                            if buf_size > 0:
                                buf = ctypes.create_unicode_buffer(buf_size + 1)
                                shell32.DragQueryFileW(
                                    ctypes.c_void_p(hdrop), i, buf, buf_size + 1)
                                if buf.value:
                                    files.append(buf.value)
                    finally:
                        kernel32.GlobalUnlock(hglobal)
    finally:
        user32.CloseClipboard()

    return files, has_image, has_text


def _get_clipboard_text(root):
    """仅在确认只有文字时读取文字"""
    try:
        import tkinter as tk
        text = root.clipboard_get()
        return text.strip() if text else ''
    except Exception:
        return ''


# ── 剪贴板监听器 ─────────────────────────────────────────────

class ClipboardMonitor:
    """低干扰剪贴板监听器"""

    def __init__(self):
        self.last_hash = ''
        self.last_text = ''
        self.last_seq = 0        # 上次剪贴板序列号
        self.running = False
        self.on_new_item = None
        self.root = None

    def start(self, root, callback=None):
        self.root = root
        self.on_new_item = callback
        self.running = True
        self._schedule_check()
        print("[Clipboard] 监听已启动（低干扰模式）")

    def stop(self):
        self.running = False

    def _schedule_check(self):
        if not self.running or not self.root:
            return
        try:
            interval = int(settings.get('poll_interval_ms'))
            self.root.after(interval, self._check_and_reschedule)
        except Exception:
            self.root.after(750, self._check_and_reschedule)

    def _check_and_reschedule(self):
        if not self.running:
            return
        try:
            # 快速检查：剪贴板序列号是否变化（不打开剪贴板）
            seq = GetClipboardSequenceNumber()
            if seq != self.last_seq:
                self.last_seq = seq
                self._check_clipboard()
        except Exception as e:
            print(f"[Clipboard] {e}")
        finally:
            self._schedule_check()

    def _check_clipboard(self):
        """单次剪贴板访问：打开一次，获取全部数据"""
        files, has_image, has_text = _check_clipboard_once()

        # 1. 文件优先
        if files:
            self._handle_files(files)
            return

        # 2. 图片
        if has_image:
            try:
                from PIL import ImageGrab, Image
                data = ImageGrab.grabclipboard()
                if isinstance(data, Image.Image):
                    self._handle_image(data)
                    return
                elif isinstance(data, list) and data:
                    self._handle_files(data)
                    return
            except Exception as e:
                print(f"[Clipboard] PIL: {e}")

        # 3. 文字
        if has_text and not files and not has_image:
            text = _get_clipboard_text(self.root)
            if text:
                self._handle_text(text)

    def _handle_text(self, text):
        if text == self.last_text:
            return
        self.last_text = text
        h = hashlib.sha256(text.encode('utf-8')).hexdigest()
        if h == self.last_hash:
            return
        self.last_hash = h

        item = db.add_item({
            'type': 'text', 'content': text,
            'content_hash': h, 'char_count': len(text),
        })
        if self.on_new_item:
            self.on_new_item(item)

    def _handle_image(self, pil_image):
        try:
            saved = save_image(pil_image)
            if not saved or saved['hash'] == self.last_hash:
                return
            self.last_hash = saved['hash']
            self.last_text = ''

            item = db.add_item({
                'type': 'image', 'content_hash': saved['hash'],
                'image_path': saved['image_path'],
                'image_width': saved['width'],
                'image_height': saved['height'],
            })
            if self.on_new_item:
                self.on_new_item(item)
        except Exception as e:
            print(f"[Clipboard] 图片: {e}")

    def _handle_files(self, paths):
        if not paths:
            return
        h = hashlib.sha256(
            '|'.join(sorted(str(p) for p in paths)).encode('utf-8')
        ).hexdigest()
        if h == self.last_hash:
            return

        self.last_text = ''
        c = classify_paths(paths)
        imgs, fils, dirs = c['images'], c['files'], c['folders']

        # 纯图片
        if imgs and not fils and not dirs:
            for p in imgs:
                s = save_image_file(p)
                if s:
                    db.add_item({
                        'type': 'image', 'content_hash': s['hash'],
                        'image_path': s['image_path'],
                        'image_width': s['width'],
                        'image_height': s['height'],
                        'content': os.path.basename(p),
                    })
                    if self.on_new_item:
                        self.on_new_item(s)
            self.last_hash = h
            return

        # 选择存储方式
        full_mode = settings.get('storage_mode') == 'full'
        store = copy_files if full_mode else record_paths

        # 纯文件夹
        if dirs and not fils and not imgs:
            r = store(dirs)
            self.last_hash = h
            if r['folder_count'] == 0:
                return
            db.add_item({
                'type': 'folder', 'content_hash': h,
                'file_paths': json.dumps(r['original_paths'], ensure_ascii=False),
                'stored_paths': json.dumps(r.get('stored_paths', []), ensure_ascii=False),
                'file_count': r['file_count'],
                'content': ', '.join(os.path.basename(p) for p in dirs),
            })
            if self.on_new_item:
                self.on_new_item(None)
            return

        # 混合/纯文件
        r = store(dirs + fils + imgs)
        self.last_hash = h
        if r['file_count'] + r['folder_count'] == 0:
            return
        db.add_item({
            'type': 'file', 'content_hash': h,
            'file_paths': json.dumps(r['original_paths'], ensure_ascii=False),
            'stored_paths': json.dumps(r.get('stored_paths', []), ensure_ascii=False),
            'file_count': r['file_count'] + r['folder_count'],
            'content': ', '.join(
                os.path.basename(p) for p in (dirs + fils + imgs)[:5]),
        })
        if self.on_new_item:
            self.on_new_item(None)


# 全局监听器实例
monitor = ClipboardMonitor()
