import streamlit as st
from .auth_utils import get_user_display_name, get_user_email, is_user_logged_in
from .azure_auth import get_login_button
from operations.audit_logger import log_action

def show_login_page():
    """
    Mostra uma página de login minimalista com os botões alinhados à esquerda.
    """
    if not is_user_logged_in():
        # CSS para esconder o IFrame do Google que aparece no topo após o clique
        st.markdown("""
        <style>
            iframe[title="st.login()"] {
                display: none;
            }
        </style>
        """, unsafe_allow_html=True)

        # Lógica para acionar o login do Google
        if 'google_login_triggered' not in st.session_state:
            st.session_state.google_login_triggered = False

        if st.session_state.get('google_login_triggered', False):
            st.login()
            st.session_state.google_login_triggered = False

        # --- Layout para alinhar no canto ---
        # Criamos duas colunas: uma estreita para o conteúdo e uma larga e vazia.
        login_col, empty_col = st.columns([1, 2]) # Proporção 1:2

        with login_col:
            st.title("Sistema de Gestão de Incidentes")
            st.markdown("---")
            st.subheader("Por favor, faça login para continuar")
            st.write("")

            # Botão Google
            if st.button("Entrar com Google", use_container_width=True, type="primary"):
                st.session_state.google_login_triggered = True

            st.markdown("<p style='text-align: center; margin: 10px 0;'>ou</p>", unsafe_allow_html=True)
            
            # Botão Azure
            get_login_button()

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
            
            keys_to_clear = [
                'is_logged_in', 'user_info_custom', 'authenticated_user_email', 
                'user_info', 'role', 'unit_name', 'access_status', 'login_logged',
                'google_login_triggered'
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            if hasattr(st, 'user') and st.user.is_logged_in:
                st.logout()
            else:
                st.rerun()









