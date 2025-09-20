import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import SPREADSHEET_ID

@st.cache_data(ttl=300)
def get_user_permissions() -> pd.DataFrame:
    """
    Carrega a lista de usuários e suas permissões da aba 'usuarios',
    sendo robusto a colunas extras.
    """
    try:
        sheet_ops = SheetOperations()
        users_data = sheet_ops.carregar_dados_aba("usuarios")
        
        expected_cols = ['email', 'role']
        if not users_data or len(users_data) < 2:
            st.warning("A aba 'usuarios' está vazia ou não contém dados de usuários.")
            return pd.DataFrame(columns=expected_cols)
        
        header = [h.strip().lower() for h in users_data[0]]
        df = pd.DataFrame(users_data[1:], columns=header)
        
        if 'email' not in df.columns or 'role' not in df.columns:
            st.error("ERRO CRÍTICO: A aba 'usuarios' na sua planilha precisa ter as colunas 'email' e 'role'.")
            return pd.DataFrame(columns=expected_cols)

        permissions_df = df[['email', 'role']].copy()
        permissions_df['email'] = permissions_df['email'].str.lower().str.strip()
        permissions_df['role'] = permissions_df['role'].str.lower().str.strip()
        
        return permissions_df
        
    except Exception as e:
        st.error(f"Erro crítico ao carregar permissões de usuário: {e}")
        return pd.DataFrame(columns=['email', 'role'])

def is_user_logged_in():
    """Verifica se o usuário está logado via st.user."""
    return hasattr(st, 'user') and st.user.is_logged_in

def get_user_email() -> str | None:
    """Retorna o e-mail do usuário logado."""
    # --- CORREÇÃO APLICADA AQUI ---
    # A verificação agora é feita em duas etapas, da forma correta.
    if is_user_logged_in() and hasattr(st.user, 'email'):
        return st.user.email.lower().strip()
    return None

def get_user_display_name() -> str:
    """Retorna o nome de exibição do usuário."""
    if is_user_logged_in() and hasattr(st.user, 'name'):
        return st.user.name
    return get_user_email() or "Usuário Desconhecido"

def get_user_role() -> str:
    """
    Retorna o papel (role) do usuário logado. Se o usuário não estiver na lista,
    ele é bloqueado.
    """
    user_email = get_user_email()
    if not user_email:
        return 'viewer'

    permissions_df = get_user_permissions()
    
    st.session_state.user_info = {'email': user_email}

    user_entry = permissions_df[permissions_df['email'] == user_email]
    
    if not user_entry.empty:
        user_role = user_entry.iloc[0]['role']
        st.session_state.role = user_role
        return user_role
    else:
        st.error(f"Acesso negado. Seu e-mail ({user_email}) não está na lista de usuários autorizados.")
        st.stop()

def check_permission(level: str = 'editor'):
    """Verifica o nível de permissão e bloqueia a página se não for atendido."""
    user_role = get_user_role()
    
    if level == 'admin' and user_role != 'admin':
        st.error("Acesso restrito a Administradores.")
        st.stop()
    elif level == 'editor' and user_role not in ['admin', 'editor']:
        st.error("Você não tem permissão para editar.")
        st.stop()
    return True
