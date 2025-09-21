import streamlit as st
from .auth_utils import get_user_display_name, get_user_email, is_user_logged_in
from .azure_auth import get_login_button
from operations.audit_logger import log_action

def show_login_page():
    """
    Mostra a página de login com opções para Google e Azure se o usuário não estiver logado.
    Retorna True se o usuário estiver logado, False caso contrário.
    """
    if not is_user_logged_in():
        st.title("Sistema de Gestão de Incidentes")
        st.markdown("Por favor, faça login com uma das contas abaixo para continuar.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.button("Fazer Login com Google", type="primary", on_click=st.login, use_container_width=True)
        with col2:
            get_login_button() # Esta função do azure_auth já cria o botão
            
        return False
    return True

def show_user_header():
    st.sidebar.write(f"Bem-vindo(a),")
    st.sidebar.write(f"**{get_user_display_name()}**")

def show_logout_button():
    """Mostra o botão de logout e limpa todas as variáveis de sessão relevantes."""
    with st.sidebar:
        st.divider()
        if st.button("Sair do Sistema", width='stretch'):
            user_email_to_log = get_user_email()
            if user_email_to_log:
                log_action("USER_LOGOUT", {"message": f"Usuário '{user_email_to_log}' deslogado."})
            
            # Limpa todas as chaves de sessão relacionadas ao login
            keys_to_clear = [
                'is_logged_in', 'user_info_custom', 'authenticated_user_email', 
                'user_info', 'role', 'unit_name', 'access_status', 'login_logged'
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Chama o logout nativo do Google, se aplicável
            if hasattr(st, 'user') and st.user.is_logged_in:
                st.logout()
            else:
                st.rerun() # Força o rerun para limpar a tela








