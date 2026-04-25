import pandas as pd
import plotly.express as px
import streamlit as st

from modules.analysis_service import (
    detect_columns,
    filter_by_product_and_time,
    filter_by_service_and_time,
    parse_dates,
    pie_counts,
    trend_by_last_fault,
)
from modules.data_repository import DB_PATH, import_to_db, load_table, read_excel
from modules.ui_components import multiselect_with_all

SUBPAGES = ["二返分布统计", "产品问题统计", "二返趋势统计"]


def ensure_state_in_options(key: str, options: list[str]) -> None:
    if not options:
        return
    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = options[0]


def get_clicked_product_from_event(event: dict | None) -> str | None:
    if not isinstance(event, dict):
        return None
    points = event.get("selection", {}).get("points", [])
    if not points:
        return None
    return points[0].get("label")


def sync_distribution_to_trend(clicked_product: str, start_date, end_date, top_n: int) -> None:
    st.session_state["analysis_subpage"] = "产品问题统计"
    st.session_state["t2_product"] = clicked_product
    st.session_state["t2_start"] = start_date
    st.session_state["t2_end"] = end_date
    st.session_state["t2_top_n"] = int(top_n)


def render_data_import_page() -> None:
    st.header("数据导入")
    st.caption("上传 Excel，并把指定工作表数据写入数据库。")

    uploaded_file = st.file_uploader("选择 Excel 文件", type=["xlsx", "xls"], key="import_uploader")
    if uploaded_file is not None:
        xl = pd.ExcelFile(uploaded_file)
        sheet_name = st.selectbox("选择工作表", xl.sheet_names, key="import_sheet")
        if st.button("导入到数据库", type="primary", key="import_btn"):
            try:
                df = read_excel(uploaded_file, sheet_name)
                row_count = import_to_db(df)
                st.success(f"导入成功：{row_count} 行")
            except Exception as exc:
                st.error(f"导入失败：{exc}")

    st.divider()
    st.subheader("数据库状态")
    st.write(f"数据库文件：`{DB_PATH}`")
    st.write(f"存在：{'是' if DB_PATH.exists() else '否'}")


def render_analysis_page() -> None:
    st.header("二返数据分析")
    st.caption("按你的新规划，分为 3 个子功能：分布统计、产品问题统计、趋势统计。")

    if not DB_PATH.exists():
        st.info("数据库不存在，请先到“数据导入”栏目导入 Excel。")
        return

    try:
        df = load_table()
    except Exception as exc:
        st.error(f"读取数据库失败：{exc}")
        return

    if df.empty:
        st.warning("数据库为空，请先导入数据。")
        return

    col_map = detect_columns(list(df.columns))
    missing = [k for k, v in col_map.items() if v is None]
    if missing:
        st.error(f"缺少必要字段：{', '.join(missing)}。请确认 Excel 包含对应列。")
        st.write("当前检测到字段：", list(df.columns))
        return

    service_col = col_map["service_provider_col"]
    product_col = col_map["product_series_col"]
    end_time_col = col_map["end_time_col"]
    fault_col = col_map["fault_code_col"]
    parsed_dates = parse_dates(df, end_time_col)
    valid_dates = parsed_dates.dropna()
    if valid_dates.empty:
        st.error(f"时间列 `{end_time_col}` 无法解析日期。")
        return

    min_dt = valid_dates.min().date()
    max_dt = valid_dates.max().date()

    fault_last_col = col_map["fault_code_last_col"]
    if "analysis_subpage" not in st.session_state:
        st.session_state["analysis_subpage"] = "二返分布统计"

    subpage = st.radio(
        "分析子页",
        SUBPAGES,
        horizontal=True,
        key="analysis_subpage",
        label_visibility="collapsed",
    )

    if subpage == "二返分布统计":
        st.subheader("二返分布统计")
        st.markdown('<div class="bi-filter-card">', unsafe_allow_html=True)
        st.markdown('<div class="bi-filter-title">筛选条件</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="bi-filter-subtitle">数据范围：{min_dt} ~ {max_dt}</div>',
            unsafe_allow_html=True,
        )

        a1, a2, a3, a4 = st.columns([1.8, 1.2, 1.2, 0.8])
        with a1:
            service_options = sorted(df[service_col].dropna().astype(str).unique().tolist())
            selected_services = multiselect_with_all("服务商", service_options, "t1_svc")
        with a2:
            t1_start = st.date_input("开始日期", value=min_dt, key="t1_start")
        with a3:
            t1_end = st.date_input("结束日期", value=max_dt, key="t1_end")
        with a4:
            top_n_t1 = st.number_input("产品系列 Top N", min_value=1, max_value=50, value=10, step=1, key="t1_top_n")

        if t1_start > t1_end:
            st.warning("开始日期不能晚于结束日期，已自动交换。")
            t1_start, t1_end = t1_end, t1_start

        st.markdown("</div>", unsafe_allow_html=True)

        if selected_services:
            t1_df = filter_by_service_and_time(
                df=df,
                parsed_dates=parsed_dates,
                service_provider_col=service_col,
                selected_services=selected_services,
                start_date=t1_start,
                end_date=t1_end,
            )
            if t1_df.empty:
                st.warning("当前条件下无数据。")
            else:
                t1_pie = pie_counts(t1_df, product_col, top_n_t1, "产品系列")
                fig = px.pie(t1_pie, names="产品系列", values="次数", hole=0.35, title="产品系列分布")
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(clickmode="event+select")
                event = st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key="t1_product_pie",
                    on_select="rerun",
                    selection_mode=("points",),
                )
                clicked_product = get_clicked_product_from_event(event)
                if clicked_product:
                    sync_distribution_to_trend(clicked_product, t1_start, t1_end, top_n_t1)
                    st.rerun()
                st.dataframe(t1_pie, use_container_width=True)
        else:
            st.info("请至少选择一个服务商。")

    elif subpage == "产品问题统计":
        st.subheader("产品问题统计")
        st.markdown('<div class="bi-filter-card">', unsafe_allow_html=True)
        st.markdown('<div class="bi-filter-title">筛选条件</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="bi-filter-subtitle">数据范围：{min_dt} ~ {max_dt}</div>',
            unsafe_allow_html=True,
        )
        b1, b2, b3, b4 = st.columns([1.8, 1.2, 1.2, 0.8])
        product_options = sorted(df[product_col].dropna().astype(str).unique().tolist())
        ensure_state_in_options("t2_product", product_options)
        with b1:
            selected_product = st.selectbox("产品系列（单选）", product_options, key="t2_product")
        with b2:
            t2_start = st.date_input("开始日期", value=min_dt, key="t2_start")
        with b3:
            t2_end = st.date_input("结束日期", value=max_dt, key="t2_end")
        with b4:
            top_n_t2 = st.number_input("错误码 Top N", min_value=1, max_value=50, value=10, step=1, key="t2_top_n")
        if t2_start > t2_end:
            st.warning("开始日期不能晚于结束日期，已自动交换。")
            t2_start, t2_end = t2_end, t2_start
        st.markdown("</div>", unsafe_allow_html=True)

        t2_df = filter_by_product_and_time(
            df=df,
            parsed_dates=parsed_dates,
            product_series_col=product_col,
            selected_product=selected_product,
            start_date=t2_start,
            end_date=t2_end,
        )
        if t2_df.empty:
            st.warning("当前条件下无数据。")
        else:
            c1, c2 = st.columns(2)
            with c1:
                cur_pie = pie_counts(t2_df, fault_col, top_n_t2, "错误码")
                fig_cur = px.pie(cur_pie, names="错误码", values="次数", hole=0.35, title="错误码分布")
                fig_cur.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig_cur, use_container_width=True)
                st.dataframe(cur_pie, use_container_width=True)
            with c2:
                last_pie = pie_counts(t2_df, fault_last_col, top_n_t2, "错误码（上次）")
                fig_last = px.pie(last_pie, names="错误码（上次）", values="次数", hole=0.35, title="错误码（上次）分布")
                fig_last.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig_last, use_container_width=True)
                st.dataframe(last_pie, use_container_width=True)

    elif subpage == "二返趋势统计":
        st.subheader("二返趋势统计")
        st.markdown('<div class="bi-filter-card">', unsafe_allow_html=True)
        st.markdown('<div class="bi-filter-title">筛选条件</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="bi-filter-subtitle">数据范围：{min_dt} ~ {max_dt}</div>',
            unsafe_allow_html=True,
        )
        product_options = sorted(df[product_col].dropna().astype(str).unique().tolist())
        last_fault_options = sorted(df[fault_last_col].dropna().astype(str).unique().tolist())
        ensure_state_in_options("t3_product", product_options)
        ensure_state_in_options("t3_last_fault", last_fault_options)

        d1, d2, d3, d4 = st.columns([1.6, 1.6, 1.1, 1.1])
        with d1:
            selected_product_t3 = st.selectbox("产品系列", product_options, key="t3_product")
        with d2:
            selected_last_fault = st.selectbox("错误码（上次）", last_fault_options, key="t3_last_fault")
        with d3:
            t3_start = st.date_input("开始日期", value=min_dt, key="t3_start")
        with d4:
            t3_end = st.date_input("结束日期", value=max_dt, key="t3_end")
        if t3_start > t3_end:
            st.warning("开始日期不能晚于结束日期，已自动交换。")
            t3_start, t3_end = t3_end, t3_start
        st.markdown("</div>", unsafe_allow_html=True)

        trend_df = trend_by_last_fault(
            df=df,
            parsed_dates=parsed_dates,
            product_series_col=product_col,
            selected_product=selected_product_t3,
            fault_code_last_col=fault_last_col,
            selected_last_fault=selected_last_fault,
            start_date=t3_start,
            end_date=t3_end,
        )
        if trend_df.empty:
            st.warning("当前条件下无数据。")
        else:
            line_fig = px.line(
                trend_df,
                x="日期",
                y="次数",
                markers=True,
                title=f"{selected_product_t3} / {selected_last_fault} 时间趋势",
            )
            st.plotly_chart(line_fig, use_container_width=True)
            st.dataframe(trend_df, use_container_width=True)
