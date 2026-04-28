import streamlit as st

from modules.auth import (
    PERMISSION_ADMIN,
    PERMISSION_ANALYSIS,
    PERMISSION_IMPORT,
    PERMISSION_MANAGEMENT,
    get_user_by_id,
    init_auth,
    render_login_register_page,
    render_user_admin_page,
)
from modules.data_repository import DB_PATH
from modules.pages import render_analysis_page, render_data_import_page, render_data_management_page
from modules.ui_components import apply_custom_style


PAGE_CONFIG = {
    "二返数据分析": {"group": "分析", "permission": PERMISSION_ANALYSIS},
    "二返数据管理": {"group": "数据", "permission": PERMISSION_MANAGEMENT},
    "数据导入": {"group": "数据", "permission": PERMISSION_IMPORT},
    "用户权限管理": {"group": "管理", "permission": PERMISSION_ADMIN},
}


def _nav_label(page_name: str) -> str:
    page_meta = PAGE_CONFIG.get(page_name, {})
    group = page_meta.get("group", "功能")
    return f"{group} · {page_name}"


def _render_top_shell(current_user: dict) -> bool:
    left, right = st.columns([8.5, 1.5], vertical_alignment="center")
    with left:
        st.markdown(
            """
            <div class="app-shell-top">
                <h1 class="app-shell-title">二返数据分析平台</h1>
                <p class="app-shell-subtitle">统一账号登录、权限可控、导入管理分析一体化</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        with st.popover(f"👤 {current_user['username']}"):
            st.caption(f"角色：{current_user['role']}")
            st.caption(f"账号：{current_user['username']}")
            st.divider()
            return st.button("退出登录", type="secondary", width="stretch", key="logout_action")
    return False


def main() -> None:
    st.set_page_config(page_title="二返数据分析", page_icon="assets/favicon.png", layout="wide")
    apply_custom_style()
    init_auth()

    if "auth_user" not in st.session_state:
        render_login_register_page()
        return

    session_user = st.session_state["auth_user"]
    refreshed_user = get_user_by_id(int(session_user["id"]))
    if refreshed_user is None:
        st.session_state.pop("auth_user", None)
        st.warning("当前账号状态已变化，请重新登录。")
        st.rerun()
    current_user = refreshed_user
    st.session_state["auth_user"] = refreshed_user
    permissions = set(current_user.get("permissions", []))

    if _render_top_shell(current_user):
        st.session_state.pop("auth_user", None)
        st.rerun()

    page_options = [
        page_name
        for page_name, config in PAGE_CONFIG.items()
        if config.get("permission") in permissions
    ]

    if not page_options:
        st.error("当前账号没有可访问的功能，请联系管理员授权。")
        return

    with st.sidebar:
        st.markdown('<div class="menu-title">功能菜单</div>', unsafe_allow_html=True)
        nav_options = [p for p in page_options if p != "数据导入"] or page_options
        if nav_options:
            page = st.radio(
                "功能栏目",
                nav_options,
                index=0,
                label_visibility="collapsed",
                format_func=_nav_label,
            )
        else:
            page = "数据导入"
            st.caption("仅授权数据导入功能")
        st.divider()
        st.caption("数据库")
        st.caption(f"`{DB_PATH}`")

        if PERMISSION_IMPORT in permissions:
            st.markdown('<div class="import-entry-title">快捷操作</div>', unsafe_allow_html=True)
            if st.button("打开数据导入", width="stretch", type="secondary"):
                page = "数据导入"

    if page == "数据导入":
        render_data_import_page()
    elif page == "二返数据管理":
        render_data_management_page()
    elif page == "用户权限管理":
        render_user_admin_page()
    else:
        render_analysis_page()


if __name__ == "__main__":
    main()
