import io
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


APP_DIR = Path(__file__).resolve().parents[1]
DB_PATH = APP_DIR / "bi_dashboard.db"
TABLE_NAME = "records"
TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def normalize_column_name(name: str) -> str:
    return str(name).strip().replace("\n", " ").replace("\r", " ")


def _validate_table_name(table_name: str) -> str:
    cleaned = str(table_name).strip()
    if not TABLE_NAME_RE.fullmatch(cleaned):
        raise ValueError(f"不支持的数据表名：{table_name}")
    return cleaned


def _quote_identifier(identifier: str) -> str:
    escaped = str(identifier).replace('"', '""')
    return f'"{escaped}"'


def _count_rows(conn: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(conn, table_name):
        return 0
    quoted_table = _quote_identifier(table_name)
    return int(conn.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0])


def read_excel(uploaded_file: io.BytesIO, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
    df.columns = [normalize_column_name(c) for c in df.columns]
    return df


def import_to_db(df: pd.DataFrame, table_name: str = TABLE_NAME) -> tuple[int, int]:
    safe_table_name = _validate_table_name(table_name)
    conn = get_conn()
    try:
        if df.empty:
            return 0, _count_rows(conn, safe_table_name)

        import_df = df.copy()
        import_df["_imported_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        import_df["_import_batch"] = datetime.now().strftime("%Y%m%d%H%M%S")

        import_df = _ensure_table_compatible(conn, import_df, safe_table_name)
        import_df.to_sql(safe_table_name, conn, if_exists="append", index=False)

        inserted_count = len(import_df)
        total_count = _count_rows(conn, safe_table_name)
        conn.commit()
        return inserted_count, total_count
    finally:
        conn.close()


def load_table(table_name: str = TABLE_NAME, include_rowid: bool = False) -> pd.DataFrame:
    safe_table_name = _validate_table_name(table_name)
    quoted_table = _quote_identifier(safe_table_name)
    conn = get_conn()
    try:
        if include_rowid:
            return pd.read_sql_query(f"SELECT rowid AS _rowid, * FROM {quoted_table}", conn)
        return pd.read_sql_query(f"SELECT * FROM {quoted_table}", conn)
    finally:
        conn.close()


def list_table_columns(table_name: str = TABLE_NAME) -> list[str]:
    safe_table_name = _validate_table_name(table_name)
    quoted_table = _quote_identifier(safe_table_name)
    conn = get_conn()
    try:
        rows = conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()
        return [row[1] for row in rows]
    finally:
        conn.close()


def insert_record(record: dict, table_name: str = TABLE_NAME) -> None:
    if not record:
        return
    safe_table_name = _validate_table_name(table_name)
    columns = list(record.keys())
    placeholders = ", ".join(["?"] * len(columns))
    cols_sql = ", ".join([_quote_identifier(c) for c in columns])
    values = [record[c] for c in columns]
    quoted_table = _quote_identifier(safe_table_name)

    conn = get_conn()
    try:
        conn.execute(
            f"INSERT INTO {quoted_table} ({cols_sql}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def update_record(rowid: int, record: dict, table_name: str = TABLE_NAME) -> None:
    if not record:
        return
    safe_table_name = _validate_table_name(table_name)
    set_sql = ", ".join([f"{_quote_identifier(k)} = ?" for k in record.keys()])
    values = list(record.values()) + [rowid]
    quoted_table = _quote_identifier(safe_table_name)

    conn = get_conn()
    try:
        conn.execute(f"UPDATE {quoted_table} SET {set_sql} WHERE rowid = ?", values)
        conn.commit()
    finally:
        conn.close()


def delete_records(rowids: list[int], table_name: str = TABLE_NAME) -> int:
    if not rowids:
        return 0
    safe_table_name = _validate_table_name(table_name)
    placeholders = ", ".join(["?"] * len(rowids))
    quoted_table = _quote_identifier(safe_table_name)
    conn = get_conn()
    try:
        cur = conn.execute(f"DELETE FROM {quoted_table} WHERE rowid IN ({placeholders})", rowids)
        conn.commit()
        return cur.rowcount if cur.rowcount is not None else 0
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _ensure_table_compatible(conn: sqlite3.Connection, df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    if not _table_exists(conn, table_name):
        # Create table with first import schema.
        df.head(0).to_sql(table_name, conn, if_exists="replace", index=False)
        return df

    quoted_table = _quote_identifier(table_name)
    table_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()]
    incoming_cols = list(df.columns)

    # Add any new columns from incoming file.
    for col in incoming_cols:
        if col not in table_cols:
            conn.execute(f"ALTER TABLE {quoted_table} ADD COLUMN {_quote_identifier(col)} TEXT")

    # Ensure incoming dataframe contains historical columns so append won't fail.
    for col in table_cols:
        if col not in df.columns:
            df[col] = None

    # Keep dataframe column order aligned to table for readability.
    refreshed_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()]
    ordered = [c for c in refreshed_cols if c in df.columns]
    extra = [c for c in df.columns if c not in ordered]
    return df[ordered + extra]
