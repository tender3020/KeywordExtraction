import io
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "bi_dashboard.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn


def normalize_column_name(name: str) -> str:
    return str(name).strip().replace("\n", " ").replace("\r", " ")


def infer_date_columns(df: pd.DataFrame) -> list[str]:
    candidates: list[str] = []
    for col in df.columns:
        series = pd.to_datetime(df[col], errors="coerce")
        if series.notna().sum() >= max(3, int(len(series) * 0.3)):
            candidates.append(col)
    return candidates


def read_excel(uploaded_file: io.BytesIO, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
    df.columns = [normalize_column_name(c) for c in df.columns]
    return df


def import_to_db(df: pd.DataFrame, table_name: str = "records") -> int:
    conn = get_conn()
    try:
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        conn.commit()
        return int(count)
    finally:
        conn.close()


def load_table(table_name: str = "records") -> pd.DataFrame:
    conn = get_conn()
    try:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    finally:
        conn.close()


def main() -> None:
    st.set_page_config(page_title="Excel BI 看板", layout="wide")
    st.title("Excel 导入 + BI 扇形图")
    st.caption("上传 Excel 后，数据会进入 SQLite。然后按时间范围统计某列内容出现次数。")

    with st.sidebar:
        st.header("1) 导入数据")
        uploaded_file = st.file_uploader("选择 Excel 文件", type=["xlsx", "xls"])
        if uploaded_file is not None:
            xl = pd.ExcelFile(uploaded_file)
            sheet_name = st.selectbox("选择工作表", xl.sheet_names)
            if st.button("导入到数据库", type="primary"):
                try:
                    df = read_excel(uploaded_file, sheet_name)
                    row_count = import_to_db(df)
                    st.success(f"导入成功：{row_count} 行")
                except Exception as exc:
                    st.error(f"导入失败：{exc}")

        st.divider()
        st.header("数据库状态")
        st.write(f"数据库文件：`{DB_PATH}`")
        st.write(f"存在：{'是' if DB_PATH.exists() else '否'}")

    if not DB_PATH.exists():
        st.info("请先在左侧上传并导入 Excel。")
        return

    try:
        df = load_table()
    except Exception as exc:
        st.error(f"读取数据库失败：{exc}")
        return

    if df.empty:
        st.warning("数据库为空，请先导入数据。")
        return

    st.subheader("2) 统计配置")
    cols = list(df.columns)
    date_candidates = infer_date_columns(df)

    c1, c2, c3 = st.columns(3)
    with c1:
        value_col = st.selectbox("统计列（按这个列做分类计数）", cols)
    with c2:
        date_col = st.selectbox(
            "时间列（用于筛选日期范围）",
            cols,
            index=cols.index(date_candidates[0]) if date_candidates else 0,
        )
    with c3:
        top_n = st.number_input("Top N（0=全部）", min_value=0, max_value=200, value=10, step=1)

    parsed_dates = pd.to_datetime(df[date_col], errors="coerce")
    valid_dates = parsed_dates.dropna()
    if valid_dates.empty:
        st.error("所选时间列无法解析为日期，请换一个时间列。")
        return

    min_dt = valid_dates.min().date()
    max_dt = valid_dates.max().date()
    date_range = st.date_input(
        "选择统计时间范围",
        value=(min_dt, max_dt),
        min_value=min_dt,
        max_value=max_dt,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = min_dt

    work_df = df.copy()
    work_df["_parsed_date"] = parsed_dates
    mask = (work_df["_parsed_date"].dt.date >= start_date) & (work_df["_parsed_date"].dt.date <= end_date)
    work_df = work_df.loc[mask]

    if work_df.empty:
        st.warning("该时间范围内没有数据。")
        return

    counts = (
        work_df[value_col]
        .fillna("空值")
        .astype(str)
        .value_counts(dropna=False)
        .rename_axis("category")
        .reset_index(name="count")
    )

    if top_n > 0:
        counts = counts.head(int(top_n))

    st.subheader("3) 统计结果")
    k1, k2, k3 = st.columns(3)
    k1.metric("筛选后总行数", f"{len(work_df):,}")
    k2.metric("分类数量", f"{counts['category'].nunique():,}")
    k3.metric("统计列", value_col)

    fig = px.pie(
        counts,
        values="count",
        names="category",
        title=f"{value_col} 在 {start_date} ~ {end_date} 的分布",
        hole=0.25,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("查看明细数据（可下载）", expanded=True):
        st.dataframe(counts, use_container_width=True)
        csv_bytes = counts.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="下载统计结果 CSV",
            data=csv_bytes,
            file_name=f"stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

    with st.expander("导入配置快照"):
        st.code(
            json.dumps(
                {
                    "db_path": str(DB_PATH),
                    "rows_total": len(df),
                    "rows_filtered": len(work_df),
                    "value_col": value_col,
                    "date_col": date_col,
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "top_n": int(top_n),
                },
                ensure_ascii=False,
                indent=2,
            ),
            language="json",
        )


if __name__ == "__main__":
    main()
