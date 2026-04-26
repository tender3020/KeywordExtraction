import io
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd


APP_DIR = Path(__file__).resolve().parents[1]
DB_PATH = APP_DIR / "bi_dashboard.db"
TABLE_NAME = "records"


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def normalize_column_name(name: str) -> str:
    return str(name).strip().replace("\n", " ").replace("\r", " ")


def read_excel(uploaded_file: io.BytesIO, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
    df.columns = [normalize_column_name(c) for c in df.columns]
    return df


def import_to_db(df: pd.DataFrame, table_name: str = TABLE_NAME) -> int:
    conn = get_conn()
    try:
        if df.empty:
            return 0

        import_df = df.copy()
        import_df["_imported_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        import_df["_import_batch"] = datetime.now().strftime("%Y%m%d%H%M%S")

        import_df = _ensure_table_compatible(conn, import_df, table_name)
        import_df.to_sql(table_name, conn, if_exists="append", index=False)

        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        conn.commit()
        return int(count)
    finally:
        conn.close()


def load_table(table_name: str = TABLE_NAME, include_rowid: bool = False) -> pd.DataFrame:
    conn = get_conn()
    try:
        if include_rowid:
            return pd.read_sql_query(f"SELECT rowid AS _rowid, * FROM {table_name}", conn)
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    finally:
        conn.close()


def list_table_columns(table_name: str = TABLE_NAME) -> list[str]:
    conn = get_conn()
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return [row[1] for row in rows]
    finally:
        conn.close()


def insert_record(record: dict, table_name: str = TABLE_NAME) -> None:
    if not record:
        return
    columns = list(record.keys())
    placeholders = ", ".join(["?"] * len(columns))
    cols_sql = ", ".join([f'"{c}"' for c in columns])
    values = [record[c] for c in columns]

    conn = get_conn()
    try:
        conn.execute(
            f'INSERT INTO "{table_name}" ({cols_sql}) VALUES ({placeholders})',
            values,
        )
        conn.commit()
    finally:
        conn.close()


def update_record(rowid: int, record: dict, table_name: str = TABLE_NAME) -> None:
    if not record:
        return
    set_sql = ", ".join([f'"{k}" = ?' for k in record.keys()])
    values = list(record.values()) + [rowid]

    conn = get_conn()
    try:
        conn.execute(f'UPDATE "{table_name}" SET {set_sql} WHERE rowid = ?', values)
        conn.commit()
    finally:
        conn.close()


def delete_records(rowids: list[int], table_name: str = TABLE_NAME) -> int:
    if not rowids:
        return 0
    placeholders = ", ".join(["?"] * len(rowids))
    conn = get_conn()
    try:
        cur = conn.execute(f'DELETE FROM "{table_name}" WHERE rowid IN ({placeholders})', rowids)
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

    table_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    incoming_cols = list(df.columns)

    # Add any new columns from incoming file.
    for col in incoming_cols:
        if col not in table_cols:
            conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{col}" TEXT')

    # Ensure incoming dataframe contains historical columns so append won't fail.
    for col in table_cols:
        if col not in df.columns:
            df[col] = None

    # Keep dataframe column order aligned to table for readability.
    refreshed_cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
    ordered = [c for c in refreshed_cols if c in df.columns]
    extra = [c for c in df.columns if c not in ordered]
    return df[ordered + extra]
