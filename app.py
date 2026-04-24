import streamlit as st

from modules.data_repository import DB_PATH
from modules.pages import render_analysis_page, render_data_import_page
from modules.ui_components import apply_custom_style


def main() -> None:
    st.set_page_config(page_title="二返数据分析", layout="wide")
    apply_custom_style()

    with st.sidebar:
        st.markdown('<div class="menu-title">功能菜单</div>', unsafe_allow_html=True)
        page = st.radio("请选择栏目", ["数据导入", "二返数据分析"], index=1)
        st.divider()
        st.caption(f"数据库：`{DB_PATH}`")

    if page == "数据导入":
        render_data_import_page()
    else:
        render_analysis_page()


if __name__ == "__main__":
    main()
