import streamlit as st
import pandas as pd
from operations.sheet import SheetOperations
from gdrive.config import SPREADSHEET_ID # Usa o ID da planilha principal

@st.cache_data(ttl=300)
def get_user_permissions() -> pd.DataFrame:
    """
    Carrega a lista de usuários e suas permissões da aba 'usuarios' da planilha principal.
    """
    try:
        sheet_ops = SheetOperations(SPREADSHEET_ID)
        users_data = sheet_ops.carregar_dados_aba("usuarios")
        
        # A aba 'usuarios' agora só precisa de 'email' e 'role'
        expected_cols = ['email', 'role']
        if not users_data or len(users_data) < 2:
            return pd.DataFrame(columns=expected_cols)
        
        df = pd.DataFrame(users_data[1:], columns=users_data[0])
        
        # Garante que as colunas essenciais existam
        if 'email' not in df.columns or 'role' not in df.columns:
            st.error("A aba 'usuarios' na sua planilha precisa ter as colunas 'email' and 'role'.")
            return pd.DataFrame(columns=expected_cols)

        df['email'] = df['email'].str.lower().str.strip()
        df['role'] = df['role'].str.lower().str.strip()
        return df[['email', 'role']] # Retorna apenas as colunas necessárias
    except Exception as e:
        st.error(f"Erro crítico ao carregar permissões de usuário: {e}")
        return pd.DataFrame(columns=['email', 'role'])

def is_user_logged_in():
    """Verifica se o usuário está logado via st.user."""
    return hasattr(st, 'user') and st.user.is_logged_in

def get_user_email() -> str | None:
    """Retorna o e-mail do usuário logado."""
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
    ele não tem acesso.
    """
    user_email = get_user_email()
    if not user_email:
        return 'viewer' # Padrão seguro para não logado

    permissions_df = get_user_permissions()
    if permissions_df.empty:
        st.error(f"Acesso negado. Nenhuma permissão configurada no sistema.")
        st.stop()

    user_entry = permissions_df[permissions_df['email'] == user_email]
    
    if not user_entry.empty:
        # Armazena a role na sessão para uso em outros locais, se necessário
        st.session_state.role = user_entry.iloc[0]['role']
        return st.session_state.role
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
