import streamlit as st


def apply_custom_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --app-primary: #2563eb;
            --app-primary-soft: #dbeafe;
            --app-bg: #f8fafc;
            --app-surface: #ffffff;
            --app-border: #e5e7eb;
            --app-text-main: #0f172a;
            --app-text-sub: #64748b;
            --app-radius: 12px;
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        .app-shell-top {
            border: 1px solid var(--app-border);
            background: linear-gradient(120deg, #ffffff 0%, #f8fbff 100%);
            border-radius: 14px;
            padding: 12px 14px;
            margin-bottom: 14px;
        }
        .app-shell-title {
            margin: 0;
            font-size: 22px;
            font-weight: 700;
            color: var(--app-text-main);
        }
        .app-shell-subtitle {
            margin: 4px 0 0 0;
            color: var(--app-text-sub);
            font-size: 13px;
        }
        .app-page-title {
            margin: 0;
            font-size: 30px;
            font-weight: 800;
            color: var(--app-text-main);
        }
        .app-page-subtitle {
            margin: 5px 0 12px 0;
            color: var(--app-text-sub);
            font-size: 13px;
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
            background: var(--app-surface);
            border: 1px solid var(--app-border);
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
        .stButton button[kind="secondary"] {
            border-color: #cbd5e1;
            background: #f8fafc;
            color: #1e293b;
        }
        .stButton button[kind="secondary"]:hover {
            border-color: #93c5fd;
            background: #eff6ff;
            color: #1e3a8a;
        }
        /* Keep theme switch menu, hide deploy entry/button */
        button[data-testid="stBaseButton-headerNoPadding"][title="Deploy"],
        a[data-testid="stHeaderActionButton"][aria-label*="Deploy"],
        [data-testid="stToolbar"] button[title="Deploy"] {
            display: none !important;
        }
        [data-testid="stMainMenu"] small {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <h1 class="app-page-title">{title}</h1>
        <div class="app-page-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def render_filter_card_header(title: str, subtitle: str) -> None:
    st.markdown('<div class="bi-filter-card">', unsafe_allow_html=True)
    st.markdown(f'<div class="bi-filter-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="bi-filter-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def close_filter_card() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


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
