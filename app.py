import streamlit as st

from modules.data_repository import DB_PATH
from modules.pages import render_analysis_page, render_data_import_page, render_data_management_page
from modules.ui_components import apply_custom_style


def main() -> None:
    st.set_page_config(page_title="二返数据分析", page_icon="assets/favicon.png", layout="wide")
    apply_custom_style()

    with st.sidebar:
        st.markdown('<div class="menu-title">功能菜单</div>', unsafe_allow_html=True)
        page = st.radio(
            "功能栏目",
            ["二返数据管理", "二返数据分析"],
            index=1,
            label_visibility="collapsed",
        )
        st.divider()
        st.caption("数据库")
        st.caption(f"`{DB_PATH}`")

        st.markdown('<div class="import-entry-title">快捷操作</div>', unsafe_allow_html=True)
        if st.button("数据导入", use_container_width=True, type="secondary"):
            page = "数据导入"

    if page == "数据导入":
        render_data_import_page()
    elif page == "二返数据管理":
        render_data_management_page()
    else:
        render_analysis_page()


if __name__ == "__main__":
    main()
