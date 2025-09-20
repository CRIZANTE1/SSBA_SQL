import streamlit as st
from gdrive.matrix_manager import get_matrix_manager
from operations.audit_logger import log_action
from gdrive.config import SPREADSHEET_ID 

def is_user_logged_in() -> bool:
    """Verifica se o usuário está logado através do objeto st.user do Streamlit."""
    return hasattr(st, 'user') and st.user.is_logged_in

def get_user_email() -> str | None:
    """Retorna o e-mail do usuário logado, normalizado para minúsculas e sem espaços extras."""
    if is_user_logged_in() and hasattr(st, 'user', 'email'):
        return st.user.email.lower().strip()
    return None

def get_user_display_name() -> str:
    """Retorna o nome de exibição do usuário, ou o e-mail como fallback."""
    if is_user_logged_in() and hasattr(st, 'user', 'name') and st.user.name:
        return st.user.name
    return get_user_email() or "Usuário Desconhecido"

def authenticate_user() -> bool:
    """
    Verifica se o usuário logado com o Google tem permissão.
    """
    user_email = get_user_email()
    if not user_email:
        return False

    if st.session_state.get('authenticated_user_email') == user_email:
        return True

    matrix_manager = get_matrix_manager()
    user_info = matrix_manager.get_user_info(user_email)

    if user_info:
        # --- USUÁRIO AUTORIZADO ---
        st.session_state.user_info = user_info
        st.session_state.role = user_info.get('role', 'viewer')
        unit_name_assoc = user_info.get('unidade_associada', 'N/A')
        st.session_state.unit_name = 'Global' if unit_name_assoc == '*' else unit_name_assoc
        
        st.session_state.spreadsheet_id = SPREADSHEET_ID
        
        st.session_state.authenticated_user_email = user_email
        st.session_state.access_status = "authorized"
        
        if not st.session_state.get('login_logged', False):
             log_action("USER_LOGIN", {"message": f"Login de '{user_email}'."})
             st.session_state.login_logged = True
             
        return True
    else:
        # --- USUÁRIO NÃO AUTORIZADO ---
        pending_requests = matrix_manager.get_pending_access_requests()
        if not pending_requests.empty and not pending_requests[pending_requests['email'] == user_email].empty:
            st.session_state.access_status = "pending"
        else:
            st.session_state.access_status = "unauthorized"
        
        st.session_state.authenticated_user_email = None
        return False

def get_user_role() -> str:
    """Retorna o papel (role) do usuário."""
    return st.session_state.get('role', 'viewer')

def check_permission(level: str = 'viewer'):
    """Verifica o nível de permissão."""
    user_role = get_user_role()
    
    if level == 'admin' and user_role != 'admin':
        st.warning("🔒 Acesso restrito a Administradores.", icon="🔒")
        st.stop()
    elif level == 'editor' and user_role not in ['admin', 'editor']:
        st.warning("🔒 Você não tem permissão para editar. Acesso somente leitura.", icon="🔒")
        st.stop()
    elif level == 'viewer' and user_role not in ['admin', 'editor', 'viewer']:
        st.error("🚫 Acesso Negado. Você não tem permissão para visualizar esta página.", icon="🚫")
        st.stop()
        
    return True
