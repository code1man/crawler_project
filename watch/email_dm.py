# watch/email_dm.py
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr  # ✅ 新增

def send_email(to_email: str, subject: str, content: str):
    host = os.getenv("DM_SMTP_HOST", "smtpdm.aliyun.com")
    port = int(os.getenv("DM_SMTP_PORT", "465"))  # 465=SSL, 587=STARTTLS
    user = os.getenv("DM_SMTP_USER")
    password = os.getenv("DM_SMTP_PASS")
    from_addr = os.getenv("DM_FROM_ADDRESS", user)
    alias = os.getenv("DM_FROM_ALIAS", "舆情监控系统")

    if not user or not password:
        raise RuntimeError("缺少 DM_SMTP_USER 或 DM_SMTP_PASS")

    # ✅ QQ 很严格：From 必须是合法 addr-spec + 可选显示名
    from_header = formataddr((str(Header(alias, "utf-8")), from_addr))

    msg = MIMEText(content, "plain", "utf-8")
    msg["From"] = from_header
    msg["To"] = to_email
    msg["Subject"] = str(Header(subject, "utf-8"))

    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=20)
        try:
            server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        finally:
            server.quit()
    else:
        server = smtplib.SMTP(host, port, timeout=20)
        try:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        finally:
            server.quit()
