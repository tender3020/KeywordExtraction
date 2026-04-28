import sqlite3
from datetime import datetime

from modules.auth.settings import AUTH_DB_PATH, LEGACY_BI_DB_PATH


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(AUTH_DB_PATH, check_same_thread=False)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_tables() -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                phone TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                permissions_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target TEXT NOT NULL,
                channel TEXT NOT NULL,
                purpose TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        _migrate_legacy_auth_data(conn)
        conn.commit()
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_names(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return [row[1] for row in rows]


def _copy_table_rows(
    source_conn: sqlite3.Connection,
    target_conn: sqlite3.Connection,
    table_name: str,
) -> int:
    if not _table_exists(source_conn, table_name):
        return 0

    target_columns = _column_names(target_conn, table_name)
    source_columns = _column_names(source_conn, table_name)
    common_columns = [c for c in target_columns if c in source_columns]
    if not common_columns:
        return 0

    quoted_cols = ", ".join([f'"{c}"' for c in common_columns])
    rows = source_conn.execute(f'SELECT {quoted_cols} FROM "{table_name}"').fetchall()
    if not rows:
        return 0

    placeholders = ", ".join(["?"] * len(common_columns))
    target_conn.executemany(
        f'INSERT OR IGNORE INTO "{table_name}" ({quoted_cols}) VALUES ({placeholders})',
        rows,
    )
    return len(rows)


def _migrate_legacy_auth_data(target_conn: sqlite3.Connection) -> None:
    """将旧版业务库中的认证数据迁移到独立 auth 库（仅首次）。"""
    if AUTH_DB_PATH.resolve() == LEGACY_BI_DB_PATH.resolve():
        return
    if not LEGACY_BI_DB_PATH.exists():
        return

    existing_user_count = target_conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if int(existing_user_count) > 0:
        return

    legacy_conn = sqlite3.connect(LEGACY_BI_DB_PATH, check_same_thread=False)
    try:
        _copy_table_rows(legacy_conn, target_conn, "users")
        _copy_table_rows(legacy_conn, target_conn, "verification_codes")
    finally:
        legacy_conn.close()
