from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Ying+ Backend"
    # 生产环境必须改成随机字符串（至少 32 字节），并通过环境变量注入
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 天
    apple_client_id: str = ""  # Apple Sign In 的 Bundle ID

    # PostgreSQL 数据库连接（Docker 内使用服务名 postgres）
    database_url: str = "postgresql+psycopg2://yingplus_user:yingplus_password@127.0.0.1:5432/yingplus"

    # Tushare Pro Token
    tushare_token: str = ""

    # 开发环境是否使用 mock 股票数据（无 Tushare token 时方便调试）
    mock_stock_data: bool = False

    # SMTP 邮件发送（用于验证码）
    smtp_server: str = "smtp.qq.com"
    smtp_port: int = 465
    smtp_username: str = ""  # 发件邮箱，如 xinfelix@vip.qq.com
    smtp_password: str = ""  # 邮箱授权码，不是登录密码
    smtp_sender: str = ""    # 默认与 smtp_username 一致
    smtp_use_ssl: bool = True

    # Redis 缓存（可选，未配置时不影响运行）
    redis_url: str = ""


settings = Settings()
