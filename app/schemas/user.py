from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    avatar: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
