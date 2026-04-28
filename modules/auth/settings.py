import os
from pathlib import Path


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# 开发环境下可不开 SMTP，验证码会显示在页面提示里。
AUTH_DEV_MODE = bool_env("AUTH_DEV_MODE", default=True)

APP_DIR = Path(__file__).resolve().parents[2]
AUTH_DB_PATH = Path(os.getenv("AUTH_DB_PATH", str(APP_DIR / "auth.db"))).expanduser()
LEGACY_BI_DB_PATH = APP_DIR / "bi_dashboard.db"
