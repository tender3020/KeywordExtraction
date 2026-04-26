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
            margin-bottom: 10px;
            letter-spacing: 0.2px;
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
        }
        section[data-testid="stSidebar"] .stRadio > label {
            font-size: 13px;
            color: #64748b;
            margin-bottom: 6px;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label {
            border: 1px solid #dbe5ff;
            border-radius: 10px;
            padding: 6px 8px;
            margin-bottom: 6px;
            background: #ffffff;
            transition: all 0.2s ease;
        }
        section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
            border-color: #93c5fd;
            background: #f8fbff;
        }
        .import-entry-title {
            font-size: 13px;
            font-weight: 600;
            color: #475569;
            margin: 10px 0 6px 0;
        }
        section[data-testid="stSidebar"] .stButton button {
            border-radius: 10px;
            border: 1px solid #bfdbfe;
            background: #eff6ff;
            color: #1e3a8a;
            font-weight: 600;
        }
        section[data-testid="stSidebar"] .stButton button:hover {
            border-color: #60a5fa;
            background: #dbeafe;
            color: #1e40af;
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
