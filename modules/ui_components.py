import streamlit as st


def apply_custom_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        .stMetric {
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 10px 14px;
        }
        .menu-title {
            font-weight: 700;
            font-size: 20px;
            margin-bottom: 8px;
        }
        .bi-filter-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 14px 16px 8px 16px;
            margin-bottom: 14px;
        }
        .bi-filter-title {
            font-size: 15px;
            font-weight: 700;
            color: #111827;
            margin-bottom: 4px;
        }
        .bi-filter-subtitle {
            color: #6b7280;
            font-size: 12px;
            margin-bottom: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def multiselect_with_all(label: str, options: list[str], key_prefix: str) -> list[str]:
    all_label = "全部"
    combined = [all_label] + options
    selected = st.multiselect(
        label,
        combined,
        default=[all_label],
        key=f"{key_prefix}_multi",
    )

    # "全部" is represented as selecting all real options.
    if all_label in selected or not selected:
        return options
    return [item for item in selected if item != all_label]
