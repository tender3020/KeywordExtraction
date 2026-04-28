import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from modules.analysis_service import (
    detect_columns,
    filter_by_product_and_time,
    filter_by_service_and_time,
    parse_dates,
    pie_counts,
    pick_col,
    sankey_pair_counts,
    trend_by_last_fault,
)
from modules.data_repository import (
    DB_PATH,
    delete_records,
    import_to_db,
    insert_record,
    list_table_columns,
    load_table,
    read_excel,
    update_record,
)
from modules.ui_components import close_filter_card, multiselect_with_all, render_filter_card_header, render_page_header

SUBPAGES = ["二返分布统计", "产品问题统计", "二返趋势统计"]


def ensure_state_in_options(key: str, options: list[str]) -> None:
    if not options:
        return
    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = options[0]


def detect_workorder_col(columns: list[str]) -> str | None:
    for c in columns:
        if "工单号" in str(c):
            return c
    return None


def detect_service_last_col(columns: list[str]) -> str | None:
    def _normalize(name: str) -> str:
        return (
            str(name)
            .replace(" ", "")
            .replace("（", "(")
            .replace("）", ")")
            .lower()
        )

    normalized = [(c, _normalize(c)) for c in columns]

    # Strong match: must include both "服务商" and "上次工单号"
    strong = [c for c, n in normalized if "服务商" in n and "上次工单号" in n]
    if strong:
        with_service_ticket = [c for c in strong if "服务工单" in _normalize(c)]
        return with_service_ticket[0] if with_service_ticket else strong[0]

    # Fallback: keep "服务商" as hard requirement
    fallback = [c for c, n in normalized if "服务商" in n and "上次" in n]
    if fallback:
        return fallback[0]

    return None


def invalid_workorder_mask(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.lower()
    return series.isna() | s.isin(["", "none", "null", "nan"])


def multi_select_editable(label: str, options: list[str], key: str, max_items: int | None = None):
    """
    Editable select:
    - Uses multiselect with optional max limit.
    - Supports keyboard backspace deletion directly in the field.
    """
    state_key = f"{key}_multi"
    current = [v for v in st.session_state.get(state_key, []) if v in options]
    selected_list = st.multiselect(
        label,
        options=options,
        default=current,
        max_selections=max_items,
        key=state_key,
        placeholder="请选择",
    )
    return selected_list


def get_clicked_product_from_event(event: dict | None) -> str | None:
    if not isinstance(event, dict):
        return None
    points = event.get("selection", {}).get("points", [])
    if not points:
        return None
    return points[0].get("label")


def sync_distribution_to_trend(clicked_product: str, start_date, end_date, top_n: int) -> None:
    st.session_state["analysis_subpage"] = "产品问题统计"
    st.session_state["t2_product_multi"] = [clicked_product]
    st.session_state["t2_start"] = start_date
    st.session_state["t2_end"] = end_date
    st.session_state["t2_top_n"] = int(top_n)


def render_data_import_page() -> None:
    render_page_header("数据导入", "上传 Excel 并写入数据库，支持导入前自动清洗无效工单号。")

    uploaded_file = st.file_uploader("选择 Excel 文件", type=["xlsx", "xls"], key="import_uploader")
    if uploaded_file is not None:
        xl = pd.ExcelFile(uploaded_file)
        sheet_name = st.selectbox("选择工作表", xl.sheet_names, key="import_sheet")
        preview_df = read_excel(uploaded_file, sheet_name)
        wo_col = detect_workorder_col(list(preview_df.columns))
        invalid_count = 0
        if wo_col is not None:
            invalid_count = int(invalid_workorder_mask(preview_df[wo_col]).sum())
        auto_drop_invalid = st.checkbox(
            "导入前自动剔除工单号为空/None 的行",
            value=True,
            help="推荐开启，避免无效记录进入数据库。",
            key="import_drop_invalid_wo",
        )
        if invalid_count > 0:
            st.warning(f"检测到 {invalid_count} 行工单号为空/None。")

        if st.button("导入到数据库", type="primary", key="import_btn"):
            try:
                df = preview_df.copy()
                dropped = 0
                if wo_col is not None and auto_drop_invalid:
                    mask = invalid_workorder_mask(df[wo_col])
                    dropped = int(mask.sum())
                    df = df.loc[~mask].copy()
                inserted_count, total_count = import_to_db(df)
                if dropped > 0:
                    st.success(
                        f"导入成功：新增 {inserted_count} 行，已自动剔除 {dropped} 行无效工单号，数据库当前共 {total_count} 行。"
                    )
                else:
                    st.success(f"导入成功：新增 {inserted_count} 行，数据库当前共 {total_count} 行。")
            except Exception as exc:
                st.error(f"导入失败：{exc}")

    st.divider()
    st.subheader("数据库状态")
    st.write(f"数据库文件：`{DB_PATH}`")
    st.write(f"存在：{'是' if DB_PATH.exists() else '否'}")


def _clean_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    return str(v)


def render_data_management_page() -> None:
    render_page_header("二返数据管理", "支持查询、手动新增、编辑和删除，适合日常数据维护。")

    if not DB_PATH.exists():
        st.info("数据库不存在，请先到“数据导入”栏目导入 Excel。")
        return

    try:
        df = load_table(include_rowid=True)
    except Exception as exc:
        st.error(f"读取数据库失败：{exc}")
        return

    if df.empty:
        st.warning("当前数据库无数据，请先导入。")
        return

    all_cols = [c for c in df.columns if c != "_rowid"]
    default_cols = [c for c in ["工单号", "产品系列", "服务结束时间", "故障码", "故障码（上次）", "_imported_at"] if c in df.columns]
    display_cols = st.multiselect(
        "显示字段",
        options=all_cols,
        default=default_cols if default_cols else all_cols[:10],
    )

    week_col = pick_col(all_cols, ["周次", "周"])
    service_last_col = detect_service_last_col(all_cols)
    if service_last_col is None:
        service_last_col = pick_col(all_cols, ["服务商", "上次工单号", "服务工单"])

    f1, f2, f3 = st.columns([1.2, 1.8, 2.0])
    with f1:
        week_options = sorted(df[week_col].dropna().astype(str).unique().tolist()) if week_col else []
        selected_weeks = st.multiselect(
            "周次",
            options=week_options,
            key="mgmt_week_filter",
            placeholder="全部周次",
            disabled=week_col is None,
        )
    with f2:
        service_last_options = (
            sorted(df[service_last_col].dropna().astype(str).unique().tolist()) if service_last_col else []
        )
        selected_service_last = st.multiselect(
            "服务商_上次",
            options=service_last_options,
            key="mgmt_service_last_filter",
            placeholder="全部服务商(上次)",
            disabled=service_last_col is None,
        )
    with f3:
        keyword = st.text_input("关键词搜索（全字段模糊）", placeholder="输入工单号/产品系列/故障码等")

    view_df = df.copy()
    if week_col and selected_weeks:
        view_df = view_df[view_df[week_col].astype(str).isin(selected_weeks)]
    if service_last_col and selected_service_last:
        view_df = view_df[view_df[service_last_col].astype(str).isin(selected_service_last)]
    if keyword.strip():
        key = keyword.strip().lower()
        mask = view_df.apply(lambda row: row.astype(str).str.lower().str.contains(key, na=False).any(), axis=1)
        view_df = view_df.loc[mask]
    matched_count = len(view_df)
    limit = int(st.session_state.get("mgmt_limit", 200))
    view_df = view_df.head(limit)

    st.subheader("数据列表")
    st.dataframe(view_df[["_rowid"] + display_cols] if display_cols else view_df, width="stretch", hide_index=True)
    p1, p2 = st.columns([5, 3])
    with p2:
        st.markdown(
            """
            <style>
            .mgmt-footer-text {
                font-size: 0.9rem;
                color: rgba(49, 51, 63, 0.8);
                line-height: 2.2rem;
                white-space: nowrap;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        p2_1, p2_2, p2_3 = st.columns([1.8, 0.9, 1.1])
        with p2_1:
            st.markdown(
                f'<div class="mgmt-footer-text">共匹配 {matched_count} 行（数据库总行数 {len(df)}）</div>',
                unsafe_allow_html=True,
            )
        with p2_2:
            st.markdown('<div class="mgmt-footer-text">显示条数</div>', unsafe_allow_html=True)
        with p2_3:
            st.number_input(
                "显示条数",
                min_value=20,
                max_value=2000,
                value=200,
                step=20,
                key="mgmt_limit",
                label_visibility="collapsed",
            )

    st.subheader("手动维护")
    ops = st.tabs(["新增", "编辑", "删除"])

    editable_cols = [c for c in list_table_columns() if c not in ["_imported_at", "_import_batch"]]

    with ops[0]:
        st.markdown("**新增记录**")
        add_payload = {}
        f1, f2 = st.columns(2)
        for idx, col in enumerate(editable_cols):
            target = f1 if idx % 2 == 0 else f2
            with target:
                add_payload[col] = st.text_input(f"{col}", key=f"add_{col}")
        if st.button("保存新增", type="primary"):
            payload = {k: _clean_text(v) for k, v in add_payload.items()}
            try:
                insert_record(payload)
                st.success("新增成功。")
                st.rerun()
            except Exception as exc:
                st.error(f"新增失败：{exc}")

    with ops[1]:
        st.markdown("**编辑记录**")
        row_options = view_df["_rowid"].astype(int).tolist()
        if not row_options:
            st.info("当前筛选结果无可编辑记录。")
        else:
            selected_rowid = st.selectbox("选择要编辑的 _rowid", row_options, key="edit_rowid")
            source = df[df["_rowid"] == selected_rowid].iloc[0]
            edit_payload = {}
            e1, e2 = st.columns(2)
            for idx, col in enumerate(editable_cols):
                target = e1 if idx % 2 == 0 else e2
                with target:
                    edit_payload[col] = st.text_input(
                        f"{col}",
                        value=_clean_text(source.get(col)),
                        key=f"edit_{selected_rowid}_{col}",
                    )
            if st.button("保存编辑", type="primary"):
                payload = {k: _clean_text(v) for k, v in edit_payload.items()}
                try:
                    update_record(int(selected_rowid), payload)
                    st.success("编辑成功。")
                    st.rerun()
                except Exception as exc:
                    st.error(f"编辑失败：{exc}")

    with ops[2]:
        st.markdown("**删除记录**")
        del_options = view_df["_rowid"].astype(int).tolist()
        delete_ids = st.multiselect("选择要删除的 _rowid（可多选）", del_options)
        if st.button("执行删除", type="primary"):
            if not delete_ids:
                st.warning("请先选择要删除的记录。")
            else:
                try:
                    deleted = delete_records([int(i) for i in delete_ids])
                    st.success(f"删除成功：{deleted} 行。")
                    st.rerun()
                except Exception as exc:
                    st.error(f"删除失败：{exc}")


def render_analysis_page() -> None:
    render_page_header("二返数据分析", "分布统计、问题统计、趋势统计")

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
    week_col = pick_col(list(df.columns), ["周次", "周"])
    customer_resp_col = pick_col(list(df.columns), ["是否客责", "是否客责任", "客责任"])
    week_options = sorted(df[week_col].dropna().astype(str).unique().tolist()) if week_col else []
    customer_resp_options = (
        sorted(df[customer_resp_col].dropna().astype(str).unique().tolist()) if customer_resp_col else []
    )
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
        render_filter_card_header("筛选条件", f"数据范围：{min_dt} ~ {max_dt}")

        a1, a2, a3, a4, a5, a6 = st.columns([1.0, 1.6, 1.2, 1.0, 1.0, 0.7])
        with a1:
            selected_weeks_t1 = st.multiselect(
                "周次",
                options=week_options,
                key="t1_week_filter",
                placeholder="全部周次",
                disabled=week_col is None,
            )
        with a2:
            service_options = sorted(df[service_col].dropna().astype(str).unique().tolist())
            selected_services = multiselect_with_all("服务商", service_options, "t1_svc")
        with a3:
            selected_customer_resp = st.multiselect(
                "是否客责",
                options=customer_resp_options,
                key="t1_customer_resp_filter",
                placeholder="全部",
                disabled=customer_resp_col is None,
            )
        with a4:
            t1_start = st.date_input("开始日期", value=min_dt, key="t1_start")
        with a5:
            t1_end = st.date_input("结束日期", value=max_dt, key="t1_end")
        with a6:
            top_n_t1 = st.number_input("产品系列 Top N", min_value=1, max_value=50, value=10, step=1, key="t1_top_n")

        if t1_start > t1_end:
            st.warning("开始日期不能晚于结束日期，已自动交换。")
            t1_start, t1_end = t1_end, t1_start

        close_filter_card()

        if selected_services:
            t1_df = filter_by_service_and_time(
                df=df,
                parsed_dates=parsed_dates,
                service_provider_col=service_col,
                selected_services=selected_services,
                start_date=t1_start,
                end_date=t1_end,
            )
            if week_col and selected_weeks_t1:
                t1_df = t1_df[t1_df[week_col].astype(str).isin(selected_weeks_t1)]
            if customer_resp_col and selected_customer_resp:
                t1_df = t1_df[t1_df[customer_resp_col].astype(str).isin(selected_customer_resp)]
            if t1_df.empty:
                st.warning("当前条件下无数据。")
            else:
                t1_pie = pie_counts(t1_df, product_col, top_n_t1, "产品系列")
                fig = px.pie(t1_pie, names="产品系列", values="次数", hole=0.35, title="产品系列分布")
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(clickmode="event+select")
                event = st.plotly_chart(
                    fig,
                    width="stretch",
                    key="t1_product_pie",
                    on_select="rerun",
                    selection_mode=("points",),
                )
                clicked_product = get_clicked_product_from_event(event)
                if clicked_product:
                    sync_distribution_to_trend(clicked_product, t1_start, t1_end, top_n_t1)
                    st.rerun()
                st.dataframe(t1_pie, width="stretch")
        else:
            st.info("请至少选择一个服务商。")

    elif subpage == "产品问题统计":
        st.subheader("产品问题统计")
        render_filter_card_header("筛选条件", f"数据范围：{min_dt} ~ {max_dt}")
        b1, b2, b3, b4, b5, b6 = st.columns([1.0, 1.5, 1.2, 1.0, 1.0, 0.7])
        product_options = sorted(df[product_col].dropna().astype(str).unique().tolist())
        with b1:
            selected_weeks_t2 = st.multiselect(
                "周次",
                options=week_options,
                key="t2_week_filter",
                placeholder="全部周次",
                disabled=week_col is None,
            )
        with b2:
            selected_products = multi_select_editable("产品系列（可多选）", product_options, "t2_product")
        with b3:
            selected_customer_resp_t2 = st.multiselect(
                "是否客责",
                options=customer_resp_options,
                key="t2_customer_resp_filter",
                placeholder="全部",
                disabled=customer_resp_col is None,
            )
        with b4:
            t2_start = st.date_input("开始日期", value=min_dt, key="t2_start")
        with b5:
            t2_end = st.date_input("结束日期", value=max_dt, key="t2_end")
        with b6:
            top_n_t2 = st.number_input("错误码 Top N", min_value=1, max_value=50, value=10, step=1, key="t2_top_n")
        if not selected_products:
            st.info("请先选择至少一个产品系列。")
            return
        if t2_start > t2_end:
            st.warning("开始日期不能晚于结束日期，已自动交换。")
            t2_start, t2_end = t2_end, t2_start
        close_filter_card()

        t2_df = filter_by_product_and_time(
            df=df,
            parsed_dates=parsed_dates,
            product_series_col=product_col,
            selected_products=selected_products,
            start_date=t2_start,
            end_date=t2_end,
        )
        if week_col and selected_weeks_t2:
            t2_df = t2_df[t2_df[week_col].astype(str).isin(selected_weeks_t2)]
        if customer_resp_col and selected_customer_resp_t2:
            t2_df = t2_df[t2_df[customer_resp_col].astype(str).isin(selected_customer_resp_t2)]
        if t2_df.empty:
            st.warning("当前条件下无数据。")
        else:
            cur_unique_count = t2_df[fault_col].fillna("空值").astype(str).str.strip().replace("", "空值").nunique()
            last_unique_count = (
                t2_df[fault_last_col].fillna("空值").astype(str).str.strip().replace("", "空值").nunique()
            )
            if int(top_n_t2) > cur_unique_count or int(top_n_t2) > last_unique_count:
                st.info(
                    f"当前筛选条件下，错误码唯一值为 {cur_unique_count} 个，错误码（上次）唯一值为 {last_unique_count} 个；"
                    f"Top N={int(top_n_t2)} 时会按实际唯一值数量展示，超出 Top 的会在桑基图中归纳到“其他”。"
                )

            c1, c2 = st.columns(2)
            with c1:
                cur_pie = pie_counts(t2_df, fault_col, top_n_t2, "错误码")
                fig_cur = px.pie(cur_pie, names="错误码", values="次数", hole=0.35, title="错误码分布")
                fig_cur.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig_cur, width="stretch")
                st.dataframe(cur_pie, width="stretch")
            with c2:
                last_pie = pie_counts(t2_df, fault_last_col, top_n_t2, "错误码（上次）")
                fig_last = px.pie(last_pie, names="错误码（上次）", values="次数", hole=0.35, title="错误码（上次）分布")
                fig_last.update_traces(textposition="inside", textinfo="percent+label")
                st.plotly_chart(fig_last, width="stretch")
                st.dataframe(last_pie, width="stretch")

            st.subheader("错误码（上次）与错误码关联关系")
            sankey_df = sankey_pair_counts(
                df=t2_df,
                source_col=fault_last_col,
                target_col=fault_col,
                top_n=int(top_n_t2),
                source_label="错误码（上次）",
                target_label="错误码",
            )
            if sankey_df.empty:
                st.info("当前条件下无可用的桑基图数据。")
            else:
                source_order = (
                    sankey_df.groupby("错误码（上次）", as_index=False)["次数"]
                    .sum()
                    .sort_values("次数", ascending=False)["错误码（上次）"]
                    .tolist()
                )
                target_order = (
                    sankey_df.groupby("错误码", as_index=False)["次数"]
                    .sum()
                    .sort_values("次数", ascending=False)["错误码"]
                    .tolist()
                )

                def _move_other_last(items: list[str]) -> list[str]:
                    if "其他" in items:
                        return [v for v in items if v != "其他"] + ["其他"]
                    return items

                source_order = _move_other_last(source_order)
                target_order = _move_other_last(target_order)

                source_labels = [f"{name}" for name in source_order]
                target_labels = [f"{name}" for name in target_order]
                all_nodes = source_labels + target_labels
                max_side_nodes = max(len(source_labels), len(target_labels), 1)
                # 使用 Plotly snap 自动防重叠排布，避免手动 y 坐标在大流量节点下重叠。
                if max_side_nodes <= 12:
                    node_pad = 14
                    node_thickness = 18
                elif max_side_nodes <= 24:
                    node_pad = 11
                    node_thickness = 16
                else:
                    node_pad = 8
                    node_thickness = 14
                dynamic_height = int(min(2600, max(720, 260 + max_side_nodes * 44)))
                top_margin = 56
                bottom_margin = 20

                source_index = {name: idx for idx, name in enumerate(source_order)}
                target_index = {name: idx + len(source_order) for idx, name in enumerate(target_order)}

                sankey_fig = go.Figure(
                    data=[
                        go.Sankey(
                            arrangement="snap",
                            node=dict(
                                label=all_nodes,
                                x=[0.02] * len(source_labels) + [0.98] * len(target_labels),
                                pad=node_pad,
                                thickness=node_thickness,
                                line=dict(color="rgba(0,0,0,0.18)", width=0.7),
                            ),
                            link=dict(
                                source=sankey_df["错误码（上次）"].map(source_index).tolist(),
                                target=sankey_df["错误码"].map(target_index).tolist(),
                                value=sankey_df["次数"].tolist(),
                            ),
                        )
                    ]
                )
                sankey_fig.update_layout(
                    title="错误码（上次） → 错误码 桑基图",
                    font_size=12,
                    height=dynamic_height,
                    margin=dict(l=180, r=180, t=top_margin, b=bottom_margin),
                )
                st.plotly_chart(sankey_fig, width="stretch")
                st.dataframe(sankey_df.head(30), width="stretch", hide_index=True)

    elif subpage == "二返趋势统计":
        st.subheader("二返趋势统计")
        render_filter_card_header("筛选条件", f"数据范围：{min_dt} ~ {max_dt}")
        product_options = sorted(df[product_col].dropna().astype(str).unique().tolist())
        last_fault_options = sorted(df[fault_last_col].dropna().astype(str).unique().tolist())

        d1, d2, d3, d4, d5 = st.columns([1.1, 1.6, 1.6, 1.1, 1.1])
        with d1:
            selected_weeks_t3 = st.multiselect(
                "周次",
                options=week_options,
                key="t3_week_filter",
                placeholder="全部周次",
                disabled=week_col is None,
            )
        with d2:
            selected_products_t3 = multi_select_editable("产品系列（可多选）", product_options, "t3_product")
        with d3:
            selected_last_fault_list = multi_select_editable("错误码（上次）", last_fault_options, "t3_last_fault", max_items=1)
        with d4:
            t3_start = st.date_input("开始日期", value=min_dt, key="t3_start")
        with d5:
            t3_end = st.date_input("结束日期", value=max_dt, key="t3_end")
        selected_last_fault = selected_last_fault_list[0] if selected_last_fault_list else None
        if not selected_products_t3 or not selected_last_fault:
            st.info("请先选择至少一个产品系列和一个错误码（上次）。")
            return
        if t3_start > t3_end:
            st.warning("开始日期不能晚于结束日期，已自动交换。")
            t3_start, t3_end = t3_end, t3_start
        close_filter_card()

        t3_source_df = df
        if week_col and selected_weeks_t3:
            t3_source_df = t3_source_df[t3_source_df[week_col].astype(str).isin(selected_weeks_t3)]

        trend_df = trend_by_last_fault(
            df=t3_source_df,
            parsed_dates=parsed_dates,
            product_series_col=product_col,
            selected_products=selected_products_t3,
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
                title=f"{'、'.join(selected_products_t3)} / {selected_last_fault} 时间趋势",
            )
            st.plotly_chart(line_fig, width="stretch")
            st.dataframe(trend_df, width="stretch")
