
import streamlit as st
from gdrive.matrix_manager import MatrixManager
from operations.audit_logger import log_action

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

def authenticate_user() -> bool:
    """
    Verifica o usuário na Planilha Matriz, carrega o contexto do tenant (unidade),
    e armazena as informações na sessão. Esta é a única fonte da verdade para permissões.
    """
    user_email = get_user_email()
    if not user_email:
        return False

    # Se o usuário já foi autenticado nesta sessão, não faz nada.
    if st.session_state.get('authenticated_user_email') == user_email:
        return True

    matrix_manager = MatrixManager()
    user_info = matrix_manager.get_user_info(user_email)

    if not user_info:
        st.error(f"Acesso negado. Seu e-mail ({user_email}) não está autorizado a usar este sistema.")
        st.session_state.clear()
        return False

    # Armazena as informações do usuário na sessão.
    st.session_state.user_info = user_info
    st.session_state.role = user_info.get('role', 'viewer')
    unit_name = user_info.get('unidade_associada')

    if unit_name == '*':
        st.session_state.unit_name = 'Global'
        st.session_state.spreadsheet_id = None
        st.session_state.folder_id = None
    else:
        unit_info = matrix_manager.get_unit_info(unit_name)
        if not unit_info:
            st.error(f"Erro de configuração: A unidade '{unit_name}' associada ao seu usuário não foi encontrada na Planilha Matriz.")
            st.session_state.clear()
            return False
        st.session_state.unit_name = unit_info.get('nome_unidade')
        st.session_state.spreadsheet_id = unit_info.get('spreadsheet_id')
        st.session_state.folder_id = unit_info.get('folder_id')

    st.session_state.authenticated_user_email = user_email
    
    log_action(
        action="USER_LOGIN",
        details={
            "message": f"Usuário '{user_email}' logado com sucesso.",
            "assigned_role": st.session_state.role,
            "initial_unit": st.session_state.unit_name
        }
    )
    
    return True

def get_user_role() -> str:
    """Retorna o papel (role) do usuário que foi definido durante a autenticação."""
    return st.session_state.get('role', 'viewer')

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
