import streamlit as st
from gdrive.matrix_manager import get_matrix_manager
from operations.audit_logger import log_action
from gdrive.config import SPREADSHEET_ID

def is_user_logged_in() -> bool:
    """Verifica se o usuário está logado através do objeto st.user do Streamlit."""
    return hasattr(st, 'user') and st.user.is_logged_in

def get_user_email() -> str | None:
    """Retorna o e-mail do usuário logado, normalizado para minúsculas e sem espaços extras."""
    if is_user_logged_in() and hasattr(st.user, 'email'):
        return st.user.email.lower().strip()
    return None

def get_user_display_name() -> str:
    """Retorna o nome de exibição do usuário, ou o e-mail como fallback."""
    if is_user_logged_in() and hasattr(st.user, 'name') and st.user.name:
        return st.user.name
    return get_user_email() or "Usuário Desconhecido"

def authenticate_user() -> bool:
    """
    Verifica se o usuário logado com o Google tem permissão.
    - Se autorizado, carrega suas informações na sessão.
    - Se não autorizado, verifica se já existe uma solicitação pendente.
    - Se não houver solicitação, marca o usuário para o fluxo de solicitação de acesso.
    """
    user_email = get_user_email()
    if not user_email:
        return False

    if st.session_state.get('authenticated_user_email') == user_email:
        return True

    matrix_manager = get_matrix_manager()
    user_info = matrix_manager.get_user_info(user_email)

    if user_info:
        # --- CASO 1: USUÁRIO AUTORIZADO ---
        st.session_state.user_info = user_info
        st.session_state.role = user_info.get('role', 'viewer')
        unit_name_assoc = user_info.get('unidade_associada', 'N/A')
        st.session_state.unit_name = 'Global' if unit_name_assoc == '*' else unit_name_assoc
        
        from gdrive.config import SPREADSHEET_ID, CENTRAL_ALERTS_FOLDER_ID
        st.session_state.spreadsheet_id = SPREADSHEET_ID
        st.session_state.folder_id = CENTRAL_ALERTS_FOLDER_ID
        
        st.session_state.authenticated_user_email = user_email
        st.session_state.access_status = "authorized" # Status explícito
        
        # Loga apenas o primeiro login da sessão
        if not st.session_state.get('login_logged', False):
             log_action("USER_LOGIN", {"message": f"Login de '{user_email}'."})
             st.session_state.login_logged = True
             
        return True
    else:
        # --- CASO 2: USUÁRIO NÃO AUTORIZADO ---
        pending_requests = matrix_manager.get_pending_access_requests()
        if not pending_requests[pending_requests['email'] == user_email].empty:
            # Já existe uma solicitação pendente
            st.session_state.access_status = "pending"
        else:
            # Novo usuário, precisa solicitar acesso
            st.session_state.access_status = "unauthorized"
        
        st.session_state.authenticated_user_email = None # Garante que o usuário não seja considerado autenticado
        return False

def get_user_role() -> str:
    """Retorna o papel (role) do usuário, que foi definido durante a autenticação."""
    return st.session_state.get('role', 'viewer') # Retorna 'viewer' por segurança se não estiver definido

def check_permission(level: str = 'viewer'):
    """
    Verifica se o papel do usuário atende ao nível de permissão mínimo exigido.
    Bloqueia a execução da página com st.stop() se a permissão for negada.

    Args:
        level (str): Nível de permissão requerido ('viewer', 'editor', 'admin').
    """
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
