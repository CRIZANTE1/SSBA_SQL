import streamlit as st
from gdrive.matrix_manager import get_matrix_manager
from operations.audit_logger import log_action
from gdrive.config import SPREADSHEET_ID, CENTRAL_ALERTS_FOLDER_ID

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
    Verifica se o usuário logado com o Google tem permissão para usar o sistema.
    Se sim, carrega suas informações de `role` e `unidade` na sessão.
    Esta é a única fonte da verdade para autorização no app.
    """
    user_email = get_user_email()
    if not user_email:
        return False

    # Se a autenticação já foi feita nesta sessão para o mesmo usuário, não repete.
    if st.session_state.get('authenticated_user_email') == user_email:
        return True

    matrix_manager = get_matrix_manager()
    user_info = matrix_manager.get_user_info(user_email)

    if not user_info:
        st.error(f"Acesso Negado. Seu e-mail ({user_email}) não está autorizado a usar este sistema. Contate o administrador.")
        st.session_state.clear() # Limpa a sessão para evitar acesso indevido
        return False

    # --- Armazena as informações essenciais na sessão ---
    st.session_state.user_info = user_info
    st.session_state.role = user_info.get('role', 'viewer') # 'viewer' como padrão de segurança
    
    # Define a unidade do usuário. '*' é um caso especial para acesso global/admin.
    unit_name_assoc = user_info.get('unidade_associada', 'N/A')
    st.session_state.unit_name = 'Global' if unit_name_assoc == '*' else unit_name_assoc
    
    # Na arquitetura single-tenant, estes IDs são sempre os mesmos, vindos do config.
    st.session_state.spreadsheet_id = SPREADSHEET_ID
    st.session_state.folder_id = CENTRAL_ALERTS_FOLDER_ID

    # Marca o usuário como autenticado com sucesso nesta sessão.
    st.session_state.authenticated_user_email = user_email
    
    log_action(
        action="USER_LOGIN",
        details={
            "message": f"Usuário '{user_email}' logado com sucesso.",
            "assigned_role": st.session_state.role,
            "associated_unit": st.session_state.unit_name
        }
    )
    
    return True

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
