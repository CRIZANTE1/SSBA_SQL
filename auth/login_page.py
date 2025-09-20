import streamlit as st
from .auth_utils import is_user_logged_in, get_user_display_name, get_user_email
from operations.audit_logger import log_action

def show_login_page():
    """Mostra a página de login simplificada para a arquitetura single-tenant."""
    
    # A verificação de OIDC não é mais necessária aqui, pois é tratada em auth_utils
    if not is_user_logged_in():
        st.markdown("### Acesso ao Sistema de Abrangência")
        st.write("Por favor, faça login com sua conta Google para continuar.")
        
        if st.button("Fazer Login com Google", type="primary"):
            try:
                st.login()
            except Exception as e:
                st.error(f"Erro ao iniciar login: {str(e)}")
        return False
        
    return True

def show_user_header():
    """Mostra o cabeçalho com informações do usuário."""
    st.sidebar.write(f"Bem-vindo, **{get_user_display_name()}**!")

def show_logout_button():
    """Mostra o botão de logout no sidebar e registra o evento."""
    with st.sidebar:
        st.divider()
        if st.button("Sair do Sistema"):
            user_email_to_log = get_user_email()
            
            if user_email_to_log:
                log_action(
                    action="USER_LOGOUT",
                    details={"message": f"Usuário '{user_email_to_log}' deslogado."}
                )
            
            try:
                st.logout()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao fazer logout: {str(e)}")
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

