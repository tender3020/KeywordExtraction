import io
import sqlite3
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
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        conn.commit()
        return int(count)
    finally:
        conn.close()


def load_table(table_name: str = TABLE_NAME) -> pd.DataFrame:
    conn = get_conn()
    try:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    finally:
        conn.close()
