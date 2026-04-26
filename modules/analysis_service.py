import pandas as pd


def pick_col(columns: list[str], keywords: list[str]) -> str | None:
    lowered = {c: c.lower() for c in columns}
    best_col = None
    best_score = 0
    for col, low in lowered.items():
        score = sum(1 for kw in keywords if kw.lower() in low)
        if score > best_score:
            best_score = score
            best_col = col
    return best_col


def detect_columns(columns: list[str]) -> dict[str, str | None]:
    return {
        "service_provider_col": pick_col(columns, ["服务商", "上次工单号", "服务工单"]),
        "product_series_col": pick_col(columns, ["产品系列"]),
        "end_time_col": pick_col(columns, ["服务结束时间", "完成时间", "关闭时间"]),
        "fault_code_col": pick_col(columns, ["故障码"]),
        "fault_code_last_col": pick_col(columns, ["故障码", "上次工单号", "服务工单"]),
    }


def parse_dates(df: pd.DataFrame, date_col: str) -> pd.Series:
    return pd.to_datetime(df[date_col], errors="coerce")


def apply_filters(
    df: pd.DataFrame,
    parsed_dates: pd.Series,
    service_provider_col: str,
    product_series_col: str,
    fault_code_col: str,
    selected_services: list[str],
    selected_products: list[str],
    selected_fault_codes: list[str],
    start_date,
    end_date,
) -> pd.DataFrame:
    work = df.copy()
    work["_parsed_date"] = parsed_dates
    mask = (
        work[service_provider_col].astype(str).isin(selected_services)
        & work[product_series_col].astype(str).isin(selected_products)
        & work[fault_code_col].astype(str).isin(selected_fault_codes)
        & (work["_parsed_date"].dt.date >= start_date)
        & (work["_parsed_date"].dt.date <= end_date)
    )
    return work.loc[mask]


def fault_pie_counts(df: pd.DataFrame, fault_code_col: str, top_n: int) -> pd.DataFrame:
    return (
        df[fault_code_col]
        .fillna("空值")
        .astype(str)
        .value_counts()
        .head(int(top_n))
        .rename_axis("故障码")
        .reset_index(name="次数")
    )


def fault_trend(df: pd.DataFrame, fault_code_col: str) -> pd.DataFrame:
    # Multi-select fault codes: render one line per fault code.
    return (
        df.assign(日期=df["_parsed_date"].dt.date, 故障码=df[fault_code_col].astype(str))
        .groupby(["日期", "故障码"], as_index=False)
        .size()
        .rename(columns={"size": "次数"})
        .sort_values(["日期", "故障码"])
    )


def filter_by_service_and_time(
    df: pd.DataFrame,
    parsed_dates: pd.Series,
    service_provider_col: str,
    selected_services: list[str],
    start_date,
    end_date,
) -> pd.DataFrame:
    work = df.copy()
    work["_parsed_date"] = parsed_dates
    mask = (
        work[service_provider_col].astype(str).isin(selected_services)
        & (work["_parsed_date"].dt.date >= start_date)
        & (work["_parsed_date"].dt.date <= end_date)
    )
    return work.loc[mask]


def filter_by_product_and_time(
    df: pd.DataFrame,
    parsed_dates: pd.Series,
    product_series_col: str,
    selected_products: list[str],
    start_date,
    end_date,
) -> pd.DataFrame:
    work = df.copy()
    work["_parsed_date"] = parsed_dates
    mask = (
        work[product_series_col].astype(str).isin(selected_products)
        & (work["_parsed_date"].dt.date >= start_date)
        & (work["_parsed_date"].dt.date <= end_date)
    )
    return work.loc[mask]


def pie_counts(df: pd.DataFrame, value_col: str, top_n: int, label_name: str) -> pd.DataFrame:
    return (
        df[value_col]
        .fillna("空值")
        .astype(str)
        .value_counts()
        .head(int(top_n))
        .rename_axis(label_name)
        .reset_index(name="次数")
    )


def trend_by_last_fault(
    df: pd.DataFrame,
    parsed_dates: pd.Series,
    product_series_col: str,
    selected_products: list[str],
    fault_code_last_col: str,
    selected_last_fault: str,
    start_date,
    end_date,
) -> pd.DataFrame:
    work = df.copy()
    work["_parsed_date"] = parsed_dates
    mask = (
        work[product_series_col].astype(str).isin(selected_products)
        & (work[fault_code_last_col].astype(str) == selected_last_fault)
        & (work["_parsed_date"].dt.date >= start_date)
        & (work["_parsed_date"].dt.date <= end_date)
    )
    trend = work.loc[mask]
    if trend.empty:
        return trend
    return (
        trend.assign(日期=trend["_parsed_date"].dt.date)
        .groupby("日期", as_index=False)
        .size()
        .rename(columns={"size": "次数"})
        .sort_values("日期")
    )
