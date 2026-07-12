from sqlalchemy import Column, DateTime, Integer, String, func

from app.db.base import Base
from app.models.mixins import SoftDeleteMixin


class VerificationCode(SoftDeleteMixin, Base):
    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    purpose = Column(String(32), nullable=False, default="login")
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
