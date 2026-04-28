import hashlib
import hmac
import json
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from modules.auth.constants import ALL_PERMISSIONS, PERMISSION_ANALYSIS, PERMISSION_IMPORT, PERMISSION_MANAGEMENT
from modules.auth.repository import get_conn, init_tables, now_str
from modules.auth.settings import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    AUTH_DEV_MODE,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)


def default_permissions(role: str) -> list[str]:
    if role == "admin":
        return list(ALL_PERMISSIONS)
    return [PERMISSION_IMPORT, PERMISSION_MANAGEMENT, PERMISSION_ANALYSIS]


def hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    if "$" not in stored_hash:
        return False
    salt, digest = stored_hash.split("$", 1)
    candidate = hash_password(password, salt=salt).split("$", 1)[1]
    return hmac.compare_digest(candidate, digest)


def parse_permissions(permissions_json: str, role: str) -> list[str]:
    if role == "admin":
        return list(ALL_PERMISSIONS)
    try:
        parsed = json.loads(permissions_json or "[]")
        if not isinstance(parsed, list):
            return default_permissions(role)
        return [p for p in parsed if p in ALL_PERMISSIONS]
    except Exception:
        return default_permissions(role)


def init_auth() -> None:
    init_tables()
    ensure_default_admin()
    backfill_legacy_user_permissions()


def backfill_legacy_user_permissions() -> None:
    """Upgrade older user records created before full permission rollout."""
    full_user_permissions = json.dumps(default_permissions("user"), ensure_ascii=False)
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE users
            SET permissions_json = ?, updated_at = ?
            WHERE role = 'user'
              AND (
                    permissions_json IS NULL
                 OR TRIM(permissions_json) = ''
                 OR permissions_json = '[]'
                 OR permissions_json = '["data_analysis"]'
              )
            """,
            (full_user_permissions, now_str()),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_default_admin() -> None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if row is not None:
            return

        existing_default_user = conn.execute(
            "SELECT id FROM users WHERE username = ? LIMIT 1",
            (ADMIN_USERNAME,),
        ).fetchone()
        if existing_default_user is not None:
            conn.execute(
                """
                UPDATE users
                SET role = 'admin',
                    is_active = 1,
                    permissions_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(default_permissions("admin"), ensure_ascii=False),
                    now_str(),
                    int(existing_default_user[0]),
                ),
            )
            conn.commit()
            return

        created = now_str()
        conn.execute(
            """
            INSERT INTO users (username, email, phone, password_hash, role, is_active, permissions_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'admin', 1, ?, ?, ?)
            """,
            (
                ADMIN_USERNAME,
                None,
                None,
                hash_password(ADMIN_PASSWORD),
                json.dumps(default_permissions("admin"), ensure_ascii=False),
                created,
                created,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def user_exists(email: str | None, phone: str | None, username: str) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT 1
            FROM users
            WHERE username = ?
               OR (? IS NOT NULL AND email = ?)
               OR (? IS NOT NULL AND phone = ?)
            LIMIT 1
            """,
            (username, email, email, phone, phone),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def create_user(username: str, password: str, email: str | None = None, phone: str | None = None) -> None:
    created = now_str()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO users (username, email, phone, password_hash, role, is_active, permissions_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'user', 1, ?, ?, ?)
            """,
            (
                username,
                email,
                phone,
                hash_password(password),
                json.dumps(default_permissions("user"), ensure_ascii=False),
                created,
                created,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def authenticate(identifier: str, password: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT id, username, email, phone, password_hash, role, is_active, permissions_json
            FROM users
            WHERE username = ? OR email = ? OR phone = ?
            LIMIT 1
            """,
            (identifier, identifier, identifier),
        ).fetchone()
        if row is None:
            return None
        if int(row[6]) != 1:
            return None
        if not verify_password(password, row[4]):
            return None
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "phone": row[3],
            "role": row[5],
            "permissions": parse_permissions(row[7], row[5]),
        }
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT id, username, email, phone, role, is_active, permissions_json
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (int(user_id),),
        ).fetchone()
        if row is None or int(row[5]) != 1:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "phone": row[3],
            "role": row[4],
            "permissions": parse_permissions(row[6], row[4]),
        }
    finally:
        conn.close()


def create_verification_code(target: str, channel: str, purpose: str = "register", ttl_minutes: int = 5) -> str:
    code = f"{secrets.randbelow(1000000):06d}"
    expires = (datetime.now() + timedelta(minutes=ttl_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO verification_codes (target, channel, purpose, code, expires_at, used, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (target, channel, purpose, code, expires, now_str()),
        )
        conn.commit()
    finally:
        conn.close()
    return code


def verify_code(target: str, channel: str, code: str, purpose: str = "register") -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT id, expires_at
            FROM verification_codes
            WHERE target = ?
              AND channel = ?
              AND purpose = ?
              AND code = ?
              AND used = 0
            ORDER BY id DESC
            LIMIT 1
            """,
            (target, channel, purpose, code),
        ).fetchone()
        if row is None:
            return False
        if datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S") < datetime.now():
            return False
        conn.execute("UPDATE verification_codes SET used = 1 WHERE id = ?", (row[0],))
        conn.commit()
        return True
    finally:
        conn.close()


def send_email_code(email: str, code: str) -> tuple[bool, str]:
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        if AUTH_DEV_MODE:
            return True, f"开发模式：未配置 SMTP，验证码为 {code}"
        return False, "邮箱服务未配置，请设置 SMTP_HOST / SMTP_USER / SMTP_PASSWORD 环境变量。"

    msg = EmailMessage()
    msg["Subject"] = "注册验证码"
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg.set_content(f"您的注册验证码为：{code}，5分钟内有效。")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True, "验证码已发送，请查收邮箱。"
    except Exception as exc:
        return False, f"发送失败：{exc}"


def send_sms_code(phone: str, code: str) -> tuple[bool, str]:
    if AUTH_DEV_MODE:
        return True, f"开发模式：短信网关未接入，手机号 {phone} 的验证码为 {code}"
    return False, "短信网关未接入。可对接阿里云短信、腾讯云短信、Twilio、Vonage。"


def list_users() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT id, username, email, phone, role, is_active, permissions_json, created_at
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()
        return [
            {
                "id": row[0],
                "username": row[1],
                "email": row[2] or "",
                "phone": row[3] or "",
                "role": row[4],
                "is_active": bool(row[5]),
                "permissions": parse_permissions(row[6], row[4]),
                "created_at": row[7],
            }
            for row in rows
        ]
    finally:
        conn.close()


def update_user_access(user_id: int, role: str, is_active: bool, permissions: list[str]) -> None:
    normalized_permissions = list(ALL_PERMISSIONS) if role == "admin" else [p for p in permissions if p in ALL_PERMISSIONS]
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE users
            SET role = ?, is_active = ?, permissions_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (role, 1 if is_active else 0, json.dumps(normalized_permissions, ensure_ascii=False), now_str(), int(user_id)),
        )
        conn.commit()
    finally:
        conn.close()
