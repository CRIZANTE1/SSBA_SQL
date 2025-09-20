import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import SPREADSHEET_ID 

@st.cache_data(ttl=300)
def get_user_permissions() -> pd.DataFrame:
    """Carrega a lista de usuários e suas permissões da aba 'usuarios'."""
    try:
        sheet_ops = SheetOperations(SPREADSHEET_ID)
        users_data = sheet_ops.carregar_dados_aba("usuarios")
        if not users_data or len(users_data) < 2:
            return pd.DataFrame(columns=['email', 'role'])
        
        df = pd.DataFrame(users_data[1:], columns=users_data[0])
        df['email'] = df['email'].str.lower().str.strip()
        df['role'] = df['role'].str.lower().str.strip()
        return df
    except Exception as e:
        st.error(f"Erro ao carregar permissões: {e}")
        return pd.DataFrame(columns=['email', 'role'])

def is_user_logged_in():
    return hasattr(st, 'user') and st.user.is_logged_in

def get_user_email() -> str | None:
    if is_user_logged_in() and hasattr(st.user, 'email'):
        return st.user.email.lower().strip()
    return None

def get_user_display_name() -> str:
    if is_user_logged_in() and hasattr(st.user, 'name'):
        return st.user.name
    return get_user_email() or "Usuário Desconhecido"

def get_user_role() -> str:
    """Retorna o papel (role) do usuário logado a partir da aba 'usuarios'."""
    user_email = get_user_email()
    if not user_email:
        return 'viewer'

    permissions_df = get_user_permissions()
    if permissions_df.empty:
        st.error(f"Acesso negado. Seu e-mail ({user_email}) não está na lista de usuários autorizados.")
        st.stop()

    user_entry = permissions_df[permissions_df['email'] == user_email]
    if not user_entry.empty:
        return user_entry.iloc[0]['role']
    else:
        st.error(f"Acesso negado. Seu e-mail ({user_email}) não está na lista de usuários autorizados.")
        st.stop()

def check_permission(level: str = 'editor'):
    user_role = get_user_role()
    if level == 'admin' and user_role != 'admin':
        st.error("Acesso restrito a Administradores.")
        st.stop()
    if level == 'editor' and user_role not in ['admin', 'editor']:
        st.error("Você não tem permissão para editar.")
        st.stop()
    return True
