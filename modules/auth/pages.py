import re

import pandas as pd
import streamlit as st

from modules.auth.constants import ALL_PERMISSIONS, PERMISSION_ADMIN, PERMISSION_LABELS
from modules.auth.service import (
    authenticate,
    create_user,
    create_verification_code,
    list_users,
    send_email_code,
    send_sms_code,
    update_user_access,
    user_exists,
    verify_code,
)
from modules.auth.settings import AUTH_DB_PATH


def _valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _valid_phone(phone: str) -> bool:
    normalized = phone.strip().replace(" ", "").replace("-", "")
    return bool(re.match(r"^\+?\d{6,20}$", normalized))


def _auth_style() -> None:
    st.markdown(
        """
        <style>
        .auth-shell {
            max-width: 760px;
            margin: 4vh auto 0 auto;
        }
        .auth-card {
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            background: #ffffff;
            padding: 1.35rem 1.2rem 1rem 1.2rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
        }
        .auth-card-title {
            font-size: 1.9rem;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 0.2rem;
        }
        .auth-card-subtitle {
            color: #64748b;
            margin-bottom: 0.8rem;
        }
        .auth-section-title {
            margin: 0.2rem 0 0.7rem 0;
            font-size: 14px;
            color: #475569;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login_register_page() -> None:
    _auth_style()
    notice = st.session_state.pop("auth_notice", None)
    if notice:
        st.success(notice)
    left_pad, content, right_pad = st.columns([1.2, 3.2, 1.2], gap="large")

    with content:
        st.markdown('<div class="auth-shell">', unsafe_allow_html=True)
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)
        st.markdown('<div class="auth-card-title">二返数据BI平台</div>', unsafe_allow_html=True)

        auth_mode = st.radio(
            "账号操作",
            ["登录", "注册"],
            horizontal=True,
            label_visibility="collapsed",
            key="auth_mode",
        )

        if auth_mode == "登录":
            st.markdown('<div class="auth-section-title">账号登录</div>', unsafe_allow_html=True)
            identifier = st.text_input("用户名 / 邮箱 / 手机号", key="login_identifier")
            password = st.text_input("密码", type="password", key="login_password")
            if st.button("登录", type="primary", width="stretch", key="login_submit"):
                if not identifier.strip() or not password:
                    st.warning("请输入账号和密码。")
                else:
                    user = authenticate(identifier.strip(), password)
                    if user is None:
                        st.error("登录失败：账号不存在、密码错误或已被禁用。")
                    else:
                        st.session_state["auth_user"] = user
                        st.session_state["auth_notice"] = f"登录成功，欢迎你：{user['username']}"
                        st.rerun()
        else:
            st.markdown('<div class="auth-section-title">新用户注册</div>', unsafe_allow_html=True)
            channel = st.radio("注册方式", ["邮箱注册", "手机号注册"], horizontal=True, key="reg_channel")
            username = st.text_input("用户名", key="reg_username")
            password = st.text_input("密码", type="password", key="reg_password")
            confirm_password = st.text_input("确认密码", type="password", key="reg_confirm_password")
            verification_code = st.text_input("验证码", key="reg_verification_code")

            if channel == "邮箱注册":
                email = st.text_input("邮箱", key="reg_email")
                if st.button("发送邮箱验证码", key="send_email_code_btn"):
                    if not _valid_email(email):
                        st.warning("请输入有效邮箱地址。")
                    else:
                        code = create_verification_code(email.strip(), "email", "register")
                        ok, message = send_email_code(email.strip(), code)
                        if ok:
                            st.success(message)
                        else:
                            st.error(message)

                if st.button("提交邮箱注册", type="primary", width="stretch", key="register_email_submit"):
                    if not username.strip() or not password:
                        st.warning("用户名和密码不能为空。")
                    elif password != confirm_password:
                        st.warning("两次密码输入不一致。")
                    elif not _valid_email(email):
                        st.warning("请输入有效邮箱地址。")
                    elif not verify_code(email.strip(), "email", verification_code.strip(), "register"):
                        st.error("验证码无效或已过期。")
                    elif user_exists(email=email.strip(), phone=None, username=username.strip()):
                        st.error("用户名或邮箱已存在。")
                    else:
                        create_user(username=username.strip(), email=email.strip(), phone=None, password=password)
                        st.success("注册成功，请使用账号登录。")
            else:
                phone = st.text_input("手机号", key="reg_phone")
                if st.button("发送短信验证码", key="send_phone_code_btn"):
                    if not _valid_phone(phone):
                        st.warning("请输入有效手机号。")
                    else:
                        code = create_verification_code(phone.strip(), "phone", "register")
                        ok, message = send_sms_code(phone.strip(), code)
                        if ok:
                            st.success(message)
                        else:
                            st.warning(message)

                if st.button("提交手机号注册", type="primary", width="stretch", key="register_phone_submit"):
                    if not username.strip() or not password:
                        st.warning("用户名和密码不能为空。")
                    elif password != confirm_password:
                        st.warning("两次密码输入不一致。")
                    elif not _valid_phone(phone):
                        st.warning("请输入有效手机号。")
                    elif not verify_code(phone.strip(), "phone", verification_code.strip(), "register"):
                        st.error("验证码无效或已过期。")
                    elif user_exists(email=None, phone=phone.strip(), username=username.strip()):
                        st.error("用户名或手机号已存在。")
                    else:
                        create_user(username=username.strip(), email=None, phone=phone.strip(), password=password)
                        st.success("注册成功，请使用账号登录。")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_user_admin_page() -> None:
    st.header("用户与权限管理")
    st.caption("管理员可管理账号启用状态、角色及菜单可见权限。")
    st.caption(f"账号数据库：`{AUTH_DB_PATH}`")

    users = list_users()
    if not users:
        st.info("暂无用户。")
        return

    table_df = pd.DataFrame(
        [
            {
                "ID": u["id"],
                "用户名": u["username"],
                "邮箱": u["email"],
                "手机号": u["phone"],
                "角色": u["role"],
                "启用": "是" if u["is_active"] else "否",
                "权限": "、".join(PERMISSION_LABELS[p] for p in u["permissions"]),
                "创建时间": u["created_at"],
            }
            for u in users
        ]
    )
    st.dataframe(table_df, width="stretch", hide_index=True)

    user_map = {f"{u['id']} - {u['username']}": u for u in users}
    selected_key = st.selectbox("选择用户", list(user_map.keys()), key="admin_selected_user")
    selected = user_map[selected_key]

    role = st.selectbox("角色", ["user", "admin"], index=0 if selected["role"] == "user" else 1, key="admin_edit_role")
    is_active = st.checkbox("启用账号", value=selected["is_active"], key="admin_edit_is_active")

    editable_permissions = [p for p in ALL_PERMISSIONS if p != PERMISSION_ADMIN]
    permission_labels = [PERMISSION_LABELS[p] for p in editable_permissions]
    default_labels = [PERMISSION_LABELS[p] for p in selected["permissions"] if p in editable_permissions]

    selected_labels = st.multiselect(
        "可访问功能",
        options=permission_labels,
        default=default_labels,
        disabled=(role == "admin"),
        key="admin_edit_permissions",
    )
    selected_permissions = [key for key, label in PERMISSION_LABELS.items() if label in selected_labels]

    if st.button("保存权限设置", type="primary", key="admin_save_user_access"):
        if role == "user" and not selected_permissions:
            st.warning("普通用户至少保留一个功能权限。")
            return
        if role == "admin":
            selected_permissions = list(ALL_PERMISSIONS)
        update_user_access(selected["id"], role, is_active, selected_permissions)
        st.success("权限设置已更新。")
        st.rerun()
