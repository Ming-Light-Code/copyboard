"""
Copyboard — 轻量存储模块
图片存压缩缩略图，文件/文件夹仅存路径引用
"""

import os
import hashlib
import shutil

# 图片文件扩展名
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
    '.ico', '.tiff', '.tif', '.svg', '.heic', '.heif',
}

THUMB_MAX = 400   # 缩略图最大边长
JPEG_QUALITY = 55  # JPEG 压缩质量


def is_image_path(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTENSIONS


def classify_paths(paths: list) -> dict:
    """将路径列表分类为 images / files / folders"""
    images, files, folders = [], [], []
    for p in paths:
        if not os.path.exists(p):
            files.append(p)
        elif os.path.isdir(p):
            folders.append(p)
        elif os.path.isfile(p):
            if is_image_path(p):
                images.append(p)
            else:
                files.append(p)
        else:
            files.append(p)
    return {'images': images, 'files': files, 'folders': folders}


def get_data_dir():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_thumb_dir():
    d = os.path.join(get_data_dir(), 'thumbs')
    os.makedirs(d, exist_ok=True)
    return d


# ═══════════════════════════════════════════════════════════════
# 图片存储（仅缩略图）
# ═══════════════════════════════════════════════════════════════

def save_image(pil_image) -> dict:
    """
    保存剪贴板图片为压缩 JPEG 缩略图。
    返回 { image_path, width, height, hash }
    """
    from PIL import Image
    import io

    if not isinstance(pil_image, Image.Image):
        return None

    # 缩放到最大 THUMB_MAX
    w, h = pil_image.width, pil_image.height
    if w > THUMB_MAX or h > THUMB_MAX:
        ratio = THUMB_MAX / max(w, h)
        pil_image = pil_image.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    # JPEG 压缩
    if pil_image.mode in ('RGBA', 'LA', 'P'):
        pil_image = pil_image.convert('RGB')
    buf = io.BytesIO()
    pil_image.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True)
    jpg_data = buf.getvalue()

    hash_val = hashlib.sha256(jpg_data).hexdigest()
    filename = f"{hash_val}.jpg"
    filepath = os.path.join(get_thumb_dir(), filename)

    if not os.path.exists(filepath):
        with open(filepath, 'wb') as f:
            f.write(jpg_data)

    return {
        'image_path': os.path.join('thumbs', filename),
        'width': pil_image.width,
        'height': pil_image.height,
        'hash': hash_val,
    }


def save_image_file(src_path: str) -> dict:
    """
    对于从文件系统复制的图片文件，不复制文件本体，
    仅记录原始路径 + 读取尺寸。如果需要缩略图预览则生成。
    返回 { width, height, hash, original_path }
    """
    from PIL import Image

    try:
        pil_img = Image.open(src_path)
        w, h = pil_img.width, pil_img.height

        # 生成缩略图（用于预览）
        if w > THUMB_MAX or h > THUMB_MAX:
            ratio = THUMB_MAX / max(w, h)
            thumb = pil_img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        else:
            thumb = pil_img

        import io
        if thumb.mode in ('RGBA', 'LA', 'P'):
            thumb = thumb.convert('RGB')
        buf = io.BytesIO()
        thumb.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        jpg_data = buf.getvalue()

        hash_val = hashlib.sha256(jpg_data).hexdigest()
        filename = f"{hash_val}.jpg"
        filepath = os.path.join(get_thumb_dir(), filename)

        if not os.path.exists(filepath):
            with open(filepath, 'wb') as f:
                f.write(jpg_data)

        return {
            'image_path': os.path.join('thumbs', filename),
            'width': w,
            'height': h,
            'hash': hash_val,
            'original_path': src_path,
        }
    except Exception as e:
        print(f"[FileStore] 读取图片信息失败: {src_path}, {e}")
        # 即使失败也记录路径
        return {
            'width': 0, 'height': 0,
            'hash': hashlib.sha256(src_path.encode()).hexdigest(),
            'original_path': src_path,
        }


# ═══════════════════════════════════════════════════════════════
# 文件/文件夹（仅路径引用，不复制）
# ═══════════════════════════════════════════════════════════════

def record_paths(paths: list) -> dict:
    """
    轻量模式：仅记录文件/文件夹路径（不复制）。
    返回 { original_paths, file_count, folder_count }
    """
    original_paths = []
    file_count = 0
    folder_count = 0

    for p in paths:
        if not os.path.exists(p):
            continue
        original_paths.append(p)
        if os.path.isdir(p):
            folder_count += 1
        else:
            file_count += 1

    return {
        'original_paths': original_paths,
        'stored_paths': [],
        'file_count': file_count,
        'folder_count': folder_count,
    }


def copy_files(paths: list) -> dict:
    """
    完整模式：复制文件/文件夹到 data 目录。
    返回 { original_paths, stored_paths, file_count, folder_count }
    """
    import uuid

    data_dir = get_data_dir()
    files_dir = os.path.join(data_dir, 'files')
    os.makedirs(files_dir, exist_ok=True)

    original_paths = []
    stored_paths = []
    file_count = 0
    folder_count = 0

    for src_path in paths:
        try:
            if not os.path.exists(src_path):
                continue
            src_abs = os.path.abspath(src_path)
            if src_abs.startswith(data_dir):
                continue

            if os.path.isdir(src_path):
                folder_name = os.path.basename(src_path)
                unique_name = f"{uuid.uuid4().hex[:12]}_{folder_name}"
                dest_path = os.path.join(files_dir, unique_name)
                if not os.path.abspath(dest_path).startswith(src_abs):
                    shutil.copytree(src_path, dest_path)
                    original_paths.append(src_path)
                    stored_paths.append(os.path.join('files', unique_name))
                    folder_count += 1
            elif os.path.isfile(src_path):
                original_name = os.path.basename(src_path)
                unique_name = f"{uuid.uuid4().hex[:12]}_{original_name}"
                dest_path = os.path.join(files_dir, unique_name)
                shutil.copy2(src_path, dest_path)
                original_paths.append(src_path)
                stored_paths.append(os.path.join('files', unique_name))
                file_count += 1
        except Exception as e:
            print(f"[FileStore] 复制失败: {src_path}, {e}")

    return {
        'original_paths': original_paths,
        'stored_paths': stored_paths,
        'file_count': file_count,
        'folder_count': folder_count,
    }


def get_full_path(rel_path: str) -> str:
    return os.path.join(get_data_dir(), rel_path)


def read_thumb_base64(rel_path: str) -> str:
    """读取缩略图为 base64 data URL"""
    import base64
    try:
        full = get_full_path(rel_path)
        if not os.path.exists(full):
            return None
        with open(full, 'rb') as f:
            return 'data:image/jpeg;base64,' + base64.b64encode(f.read()).decode()
    except Exception:
        return None


def delete_thumb(rel_path: str):
    """删除缩略图文件"""
    if not rel_path:
        return
    try:
        full = get_full_path(rel_path)
        if os.path.exists(full):
            os.remove(full)
    except Exception:
        pass


def delete_stored_files(stored_paths: list):
    """删除存储的文件/文件夹（兼容旧数据）"""
    if not stored_paths:
        return
    for rel_path in stored_paths:
        try:
            full = get_full_path(rel_path)
            if os.path.exists(full):
                if os.path.isdir(full):
                    shutil.rmtree(full)
                else:
                    os.remove(full)
        except Exception:
            pass


# 旧 API 别名
read_image_as_base64 = read_thumb_base64
save_image_file_path = save_image_file
