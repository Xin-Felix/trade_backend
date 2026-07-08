import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings


def _build_login_code_email(code: str) -> tuple[str, str]:
    subject = f"Ying+ 登录验证码：{code}"
    body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #333; }}
        .container {{ max-width: 480px; margin: 40px auto; padding: 24px; border: 1px solid #eee; border-radius: 12px; }}
        .code {{ font-size: 32px; font-weight: bold; letter-spacing: 4px; color: #007AFF; margin: 16px 0; }}
        .footer {{ font-size: 12px; color: #999; margin-top: 24px; }}
    </style>
</head>
<body>
    <div class="container">
        <p>你正在登录 Ying+，请在 5 分钟内输入以下验证码：</p>
        <div class="code">{code}</div>
        <p class="footer">如不是你本人操作，请忽略此邮件。</p>
    </div>
</body>
</html>"""
    return subject, body


def send_login_code_email(to_email: str, code: str) -> None:
    """发送登录验证码邮件。若 SMTP 未配置则直接打印到日志（开发环境）。"""
    if not settings.smtp_username or not settings.smtp_password:
        print(f"[VerificationCode] email={to_email} code={code} (SMTP not configured)")
        return

    subject, html = _build_login_code_email(code)
    sender = settings.smtp_sender or settings.smtp_username

    msg = MIMEText(html, "html", "utf-8")
    msg["From"] = formataddr(("Ying+", sender))
    msg["To"] = formataddr(("", to_email))
    msg["Subject"] = subject

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_server, settings.smtp_port, timeout=10) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(sender, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=10) as server:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.sendmail(sender, [to_email], msg.as_string())

    print(f"[EmailSent] email={to_email} code={code}")
