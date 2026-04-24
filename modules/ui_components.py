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
        </style>
        """,
        unsafe_allow_html=True,
    )


def multiselect_with_all(label: str, options: list[str], key_prefix: str) -> list[str]:
    select_all = st.checkbox(f"{label}：全选", value=True, key=f"{key_prefix}_all")
    if select_all:
        st.multiselect(label, options, default=options, key=f"{key_prefix}_multi", disabled=True)
        return options
    return st.multiselect(label, options, default=options[:1] if options else [], key=f"{key_prefix}_multi")
