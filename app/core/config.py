from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Ying+ Backend"
    # 生产环境必须改成随机字符串（至少 32 字节），并通过 .env 或环境变量注入
    # 不再提供默认值，防止未配置时意外使用弱密钥
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 天
    apple_client_id: str = ""  # Apple Sign In 的 Bundle ID

    # PostgreSQL 数据库连接（Docker 内使用服务名 postgres）
    database_url: str = "postgresql+psycopg2://yingplus_user:yingplus_password@127.0.0.1:5432/yingplus"

    # Tushare Pro Token
    tushare_token: str = ""

    # Tushare 代理地址（咸鱼积分代理，用于分时等高级接口）
    tushare_proxy_url: str = ""
    tushare_proxy_token: str = ""  # 代理专用 token（与 tushare_token 不同）

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

    # 阿里云 OSS（用于头像、图片等文件存储）
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_bucket_name: str = "ying-trade"
    oss_endpoint: str = "https://oss-cn-hangzhou.aliyuncs.com"
    oss_custom_domain: str = "ying-trade.oss-cn-hangzhou.aliyuncs.com"  # CNAME 自定义域名（用于生成访问 URL）
    oss_sign_expire: int = 3600  # 签名 URL 有效期（秒），默认 1 小时

    # AI 模型配置
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"  # deepseek-chat / deepseek-reasoner


settings = Settings()
