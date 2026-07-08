from pydantic import BaseModel

from app.schemas.user import User


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User
