"""文件上传接口。

使用阿里云 OSS 存储，Bucket 为私有读写，返回签名 URL 访问。
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.core.dependencies import get_current_user
from app.schemas.user import User
from app.services import oss_service

router = APIRouter()

# 允许的图片类型
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
# 最大文件大小 5MB
_MAX_FILE_SIZE = 5 * 1024 * 1024


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    folder: str = Query("uploads", description="存储目录: avatars / uploads"),
    user: User = Depends(get_current_user),
) -> dict:
    """上传图片到 OSS，返回 object_key 和签名访问 URL。

    - 支持 jpg/png/gif/webp
    - 最大 5MB
    - 返回的 signed_url 有效期 1 小时，过期后需重新调用 /upload/sign 获取
    """
    # 校验文件类型
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的图片类型: {file.content_type}，支持 jpg/png/gif/webp")

    # 读取文件内容
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大（{len(content) // 1024}KB），最大支持 5MB")

    # 上传到 OSS
    try:
        object_key = oss_service.upload_file(
            file_bytes=content,
            filename=file.filename or "image.jpg",
            content_type=file.content_type,
            folder=folder,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")

    # 拼接公共读 URL
    from app.core.config import settings
    domain = settings.oss_custom_domain or f"{settings.oss_bucket_name}.oss-cn-hangzhou.aliyuncs.com"
    public_url = f"https://{domain}/{object_key}"

    return {
        "success": True,
        "data": {
            "object_key": object_key,
            "signed_url": public_url,
        },
    }


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict:
    """上传用户头像。上传成功后自动更新当前用户的 avatar 字段。"""
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的图片类型: {file.content_type}")

    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件过大，最大支持 5MB")

    try:
        object_key = oss_service.upload_avatar(
            file_bytes=content,
            filename=file.filename or "avatar.jpg",
            content_type=file.content_type,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {e}")

    # 拼接公共读 URL（Bucket 已设为公共读）
    from app.core.config import settings
    domain = settings.oss_custom_domain or f"{settings.oss_bucket_name}.oss-cn-hangzhou.aliyuncs.com"
    public_url = f"https://{domain}/{object_key}"

    # 更新用户头像
    from sqlalchemy.orm import Session
    from app.db.base import SessionLocal
    from app.models.user import User as UserModel

    def extract_object_key(avatar: str | None) -> str | None:
        """从完整 URL 或 object_key 中提取 object_key。"""
        if not avatar:
            return None
        if avatar.startswith("http://") or avatar.startswith("https://"):
            # 去掉协议和域名，保留路径部分作为 object_key
            from urllib.parse import urlparse
            path = urlparse(avatar).path
            return path.lstrip("/") if path else avatar
        return avatar

    db = SessionLocal()
    try:
        db_user = (
            db.query(UserModel)
            .filter(UserModel.public_id == user.id, UserModel.is_deleted == 0)
            .first()
        )
        if db_user:
            # 删除旧头像
            old_avatar = db_user.avatar
            if old_avatar:
                old_key = extract_object_key(old_avatar)
                if old_key and old_key.startswith("avatars/"):
                    oss_service.delete_file(old_key)
            db_user.avatar = public_url
            db.commit()
    finally:
        db.close()

    return {
        "success": True,
        "data": {
            "object_key": object_key,
            "signed_url": public_url,
        },
    }


@router.get("/sign")
async def get_signed_url(
    object_key: str = Query(..., description="OSS 对象 key"),
    expires: int = Query(3600, ge=60, le=86400, description="URL 有效期（秒）"),
    user: User = Depends(get_current_user),
) -> dict:
    """获取 OSS 文件的签名访问 URL（用于已上传文件的重新获取访问链接）。"""
    if not object_key:
        raise HTTPException(status_code=400, detail="object_key 不能为空")

    try:
        signed_url = oss_service.get_signed_url(object_key, expires=expires)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成签名 URL 失败: {e}")

    return {
        "success": True,
        "data": {
            "object_key": object_key,
            "signed_url": signed_url,
        },
    }
