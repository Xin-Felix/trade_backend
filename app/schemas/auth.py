from pydantic import BaseModel, EmailStr, Field


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str


class EmailCodeRequest(BaseModel):
    email: EmailStr
    purpose: str | None = Field(default="login", pattern="^(login|register|reset_password)$")


class EmailCodeVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    purpose: str | None = Field(default="login", pattern="^(login|register|reset_password)$")
