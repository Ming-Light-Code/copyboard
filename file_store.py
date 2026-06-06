"""
Copyboard — 文件存储模块
轻量模式：剪贴板图片存 JPEG 缩略图，文件/文件夹仅记录路径
完整模式：复制文件/文件夹到 data 目录
"""

import os
import hashlib
import shutil

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.ico', '.tiff', '.tif', '.svg', '.heic', '.heif',
}

THUMB_MAX = 400
JPEG_QUALITY = 55


def is_image_path(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def classify_paths(paths: list) -> dict:
    """将路径列表按类型分为 images / files / folders"""
    images, files, folders = [], [], []
    for p in paths:
        if not os.path.exists(p):
            files.append(p)
        elif os.path.isdir(p):
            folders.append(p)
        elif is_image_path(p):
            images.append(p)
        else:
            files.append(p)
    return {'images': images, 'files': files, 'folders': folders}


def _data_dir():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(d, exist_ok=True)
    return d


def _thumb_dir():
    d = os.path.join(_data_dir(), 'thumbs')
    os.makedirs(d, exist_ok=True)
    return d


# ═══════════════════════════════════════════════════════════════
# 图片存储（压缩缩略图）
# ═══════════════════════════════════════════════════════════════

def save_image(pil_image) -> dict:
    """
    将 PIL Image 缩放至 THUMB_MAX 以内，以 JPEG 格式保存。
    返回 { image_path, width, height, hash }
    """
    from PIL import Image
    import io

    if not isinstance(pil_image, Image.Image):
        return None

    w, h = pil_image.width, pil_image.height
    if max(w, h) > THUMB_MAX:
        ratio = THUMB_MAX / max(w, h)
        pil_image = pil_image.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    if pil_image.mode in ('RGBA', 'LA', 'P'):
        pil_image = pil_image.convert('RGB')

    buf = io.BytesIO()
    pil_image.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True)
    data = buf.getvalue()

    hash_val = hashlib.sha256(data).hexdigest()
    path = os.path.join(_thumb_dir(), f"{hash_val}.jpg")
    if not os.path.exists(path):
        with open(path, 'wb') as f:
            f.write(data)

    return {'image_path': os.path.join('thumbs', f"{hash_val}.jpg"),
            'width': pil_image.width, 'height': pil_image.height, 'hash': hash_val}


def save_image_file(src_path: str) -> dict:
    """
    对从文件系统复制的图片，生成缩略图预览但不复制原文件。
    返回 { image_path, width, height, hash, original_path }
    """
    from PIL import Image
    import io

    try:
        img = Image.open(src_path)
        w, h = img.width, img.height

        if max(w, h) > THUMB_MAX:
            ratio = THUMB_MAX / max(w, h)
            thumb = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        else:
            thumb = img

        if thumb.mode in ('RGBA', 'LA', 'P'):
            thumb = thumb.convert('RGB')

        buf = io.BytesIO()
        thumb.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        data = buf.getvalue()

        hash_val = hashlib.sha256(data).hexdigest()
        path = os.path.join(_thumb_dir(), f"{hash_val}.jpg")
        if not os.path.exists(path):
            with open(path, 'wb') as f:
                f.write(data)

        return {'image_path': os.path.join('thumbs', f"{hash_val}.jpg"),
                'width': w, 'height': h, 'hash': hash_val, 'original_path': src_path}
    except Exception as e:
        print(f"[FileStore] 图片读取失败: {src_path} - {e}")
        return {'width': 0, 'height': 0,
                'hash': hashlib.sha256(src_path.encode()).hexdigest(),
                'original_path': src_path}


# ═══════════════════════════════════════════════════════════════
# 文件/文件夹路径记录
# ═══════════════════════════════════════════════════════════════

def record_paths(paths: list) -> dict:
    """轻量模式：仅记录路径，不复制实体文件"""
    orig, fc, dc = [], 0, 0
    for p in paths:
        if not os.path.exists(p):
            continue
        orig.append(p)
        if os.path.isdir(p):
            dc += 1
        else:
            fc += 1
    return {'original_paths': orig, 'stored_paths': [], 'file_count': fc, 'folder_count': dc}


def copy_files(paths: list) -> dict:
    """完整模式：复制文件/文件夹到 data/files 目录"""
    import uuid
    files_dir = os.path.join(_data_dir(), 'files')
    os.makedirs(files_dir, exist_ok=True)

    orig, stored, fc, dc = [], [], 0, 0
    data_root = _data_dir()

    for src in paths:
        try:
            if not os.path.exists(src) or os.path.abspath(src).startswith(data_root):
                continue
            if os.path.isdir(src):
                dest = os.path.join(files_dir, f"{uuid.uuid4().hex[:12]}_{os.path.basename(src)}")
                if not os.path.abspath(dest).startswith(os.path.abspath(src)):
                    shutil.copytree(src, dest)
                    orig.append(src); stored.append(os.path.join('files', os.path.basename(dest))); dc += 1
            elif os.path.isfile(src):
                dest = os.path.join(files_dir, f"{uuid.uuid4().hex[:12]}_{os.path.basename(src)}")
                shutil.copy2(src, dest)
                orig.append(src); stored.append(os.path.join('files', os.path.basename(dest))); fc += 1
        except Exception as e:
            print(f"[FileStore] 复制失败: {src} - {e}")

    return {'original_paths': orig, 'stored_paths': stored, 'file_count': fc, 'folder_count': dc}


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def get_full_path(rel: str) -> str:
    return os.path.join(_data_dir(), rel)


def read_thumb_base64(rel: str) -> str:
    import base64
    try:
        full = get_full_path(rel)
        if os.path.exists(full):
            with open(full, 'rb') as f:
                return 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()
    except Exception:
        pass
    return None


def delete_thumb(rel: str):
    try:
        full = get_full_path(rel)
        if os.path.exists(full):
            os.remove(full)
    except Exception:
        pass


def delete_stored_files(paths: list):
    """删除存储的文件/文件夹（兼容旧版本完整模式数据）"""
    for rel in (paths or []):
        try:
            full = get_full_path(rel)
            if os.path.exists(full):
                (shutil.rmtree if os.path.isdir(full) else os.remove)(full)
        except Exception:
            pass


# 旧 API 兼容
read_image_as_base64 = read_thumb_base64
save_image_file_path = save_image_file
