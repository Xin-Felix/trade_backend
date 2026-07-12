"""阿里云 OSS 文件存储服务。

Bucket 为私有读写，所有文件访问需通过签名 URL。
支持上传文件、生成签名访问 URL、删除文件等操作。
使用 CNAME 自定义域名生成访问 URL。
"""

import logging
import uuid
from datetime import datetime

import oss2

from app.core.config import settings

logger = logging.getLogger(__name__)

# 全局 OSS 客户端（懒加载）
_bucket = None
_bucket_cname = None


def _get_bucket() -> oss2.Bucket:
    """获取 OSS Bucket 实例（用于上传/删除，走官方 endpoint）。"""
    global _bucket
    if _bucket is None:
        if not settings.oss_access_key_id or not settings.oss_access_key_secret:
            raise RuntimeError("OSS 未配置：请在 .env 中设置 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET")
        auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        _bucket = oss2.Bucket(auth, settings.oss_endpoint, settings.oss_bucket_name)
    return _bucket


def _get_bucket_cname() -> oss2.Bucket:
    """获取使用 CNAME 自定义域名的 Bucket 实例（用于生成签名 URL）。"""
    global _bucket_cname
    if _bucket_cname is None:
        if not settings.oss_access_key_id or not settings.oss_access_key_secret:
            raise RuntimeError("OSS 未配置")
        auth = oss2.Auth(settings.oss_access_key_id, settings.oss_access_key_secret)
        # 使用 CNAME 域名时，is_cname=True
        domain = settings.oss_custom_domain or f"{settings.oss_bucket_name}.oss-cn-hangzhou.aliyuncs.com"
        _bucket_cname = oss2.Bucket(auth, f"https://{domain}", settings.oss_bucket_name, is_cname=True)
    return _bucket_cname


def upload_file(file_bytes: bytes, filename: str, content_type: str = "image/jpeg", folder: str = "uploads") -> str:
    """上传文件到 OSS。

    Args:
        file_bytes: 文件二进制内容
        filename: 原始文件名（用于提取扩展名）
        content_type: MIME 类型
        folder: 存储目录，如 avatars / uploads

    Returns:
        OSS 对象 key（相对路径），如 avatars/2026/07/uuid.jpg
    """
    bucket = _get_bucket()

    # 生成唯一文件名，按年月归档
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    now = datetime.now()
    object_key = f"{folder}/{now.strftime('%Y/%m')}/{uuid.uuid4().hex}.{ext}"

    # 上传
    headers = {"Content-Type": content_type}
    bucket.put_object(object_key, file_bytes, headers=headers)
    logger.info(f"[OSS] 上传成功: {object_key} ({len(file_bytes)} bytes)")

    return object_key


def get_signed_url(object_key: str, expires: int = None) -> str:
    """获取文件的公共访问 URL。

    Bucket 已设为公共读，直接拼接 URL 即可，无需签名。

    Args:
        object_key: OSS 对象 key
        expires: 忽略（公共读不需要过期时间）

    Returns:
        公共访问 URL
    """
    if not object_key:
        return ""

    domain = settings.oss_custom_domain or f"{settings.oss_bucket_name}.oss-cn-hangzhou.aliyuncs.com"
    return f"https://{domain}/{object_key}"


def resolve_avatar_url(avatar: str | None) -> str | None:
    """将 avatar 字段解析为可访问的 URL。

    - 如果是 http/https 开头（外部 URL），直接返回
    - 如果是 OSS object_key（如 avatars/2026/07/xxx.jpg），拼接公共访问 URL
    - 如果为空，返回 None
    """
    if not avatar:
        return None
    if avatar.startswith("http://") or avatar.startswith("https://"):
        return avatar
    return get_signed_url(avatar)


def delete_file(object_key: str) -> bool:
    """删除 OSS 文件。

    Args:
        object_key: OSS 对象 key

    Returns:
        是否删除成功
    """
    if not object_key:
        return False

    try:
        bucket = _get_bucket()
        bucket.delete_object(object_key)
        logger.info(f"[OSS] 删除成功: {object_key}")
        return True
    except Exception as e:
        logger.error(f"[OSS] 删除失败 {object_key}: {e}")
        return False


def upload_avatar(file_bytes: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """上传用户头像（存放在 avatars/ 目录）。"""
    return upload_file(file_bytes, filename, content_type, folder="avatars")
