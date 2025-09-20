import streamlit as st
from .auth_utils import get_user_display_name, get_user_email
from operations.audit_logger import log_action

def show_login_page():
    """
    Mostra a página de login se o usuário ainda não estiver logado.
    Retorna True se o usuário estiver logado, False caso contrário.
    """
    if not (hasattr(st, 'user') and st.user.is_logged_in):
        st.title("Sistema de Gestão de Incidentes")
        st.markdown("Por favor, faça login com sua conta Google para continuar.")
        
        # O botão de login deve ser o único elemento interativo principal nesta tela.
        st.button("Fazer Login com Google", type="primary", on_click=st.login)
        
        return False
    return True

def show_user_header():
    """Mostra o cabeçalho com informações do usuário na barra lateral."""
    st.sidebar.write(f"Bem-vindo(a),")
    st.sidebar.write(f"**{get_user_display_name()}**")

def show_logout_button():
    """Mostra o botão de logout na barra lateral e lida com o evento de logout."""
    with st.sidebar:
        st.divider()
        if st.button("Sair do Sistema", use_container_width=True):
            user_email_to_log = get_user_email()
            if user_email_to_log:
                log_action("USER_LOGOUT", {"message": f"Usuário '{user_email_to_log}' deslogado."})
            
            # Limpa o estado da sessão antes de deslogar
            keys_to_keep = [] # Mantenha chaves se necessário entre logins, mas geralmente é melhor limpar tudo.
            for key in list(st.session_state.keys()):
                if key not in keys_to_keep:
                    del st.session_state[key]
            
            st.logout()

