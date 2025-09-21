import streamlit as st
from .auth_utils import get_user_display_name, get_user_email, is_user_logged_in
from .azure_auth import get_login_url
from operations.audit_logger import log_action

# --- URLs dos Logos ---
GOOGLE_LOGO_URL = "https://img.icons8.com/?size=512&id=17949&format=png"
MICROSOFT_LOGO_URL = "https://cdn-icons-png.flaticon.com/512/732/732221.png"

def show_login_page():
    """
    Mostra a página de login com um design limpo, funcional e com logos.
    """
    if not is_user_logged_in():
        st.title("Sistema de Gestão de Incidentes")
        st.write("") 

        # CSS para esconder o IFrame do Google que aparece no topo após o clique
        st.markdown("""
        <style>
            iframe[title="st.login()"] {
                display: none;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # Centraliza a área de login
        _, col, _ = st.columns([1, 1.5, 1])

        with col:
            st.markdown("<h3 style='text-align: center; margin-bottom: 25px;'>Entrar no Sistema</h3>", unsafe_allow_html=True)

            # --- Botão Google Funcional ---
            # A forma mais robusta é usar o st.button para acionar o st.login()
            if 'google_login_triggered' not in st.session_state:
                st.session_state.google_login_triggered = False

            # Usamos colunas para alinhar o logo e o botão
            logo_col, button_col = st.columns([0.15, 0.85])
            with logo_col:
                st.image(GOOGLE_LOGO_URL, width=35)
            with button_col:
                if st.button("Entrar com Google", use_container_width=True, key="google_login_btn"):
                    st.session_state.google_login_triggered = True

            # Lógica para chamar o st.login() após o clique
            if st.session_state.get('google_login_triggered', False):
                st.login()
                st.session_state.google_login_triggered = False # Reseta o estado

            st.markdown("<p style='text-align: center; margin: 10px 0;'>ou</p>", unsafe_allow_html=True)
            
            # --- Botão Azure Funcional ---
            azure_login_url = get_login_url()
            if azure_login_url:
                # Usamos colunas para alinhar o logo e o botão
                logo_col_az, button_col_az = st.columns([0.15, 0.85])
                with logo_col_az:
                    st.image(MICROSOFT_LOGO_URL, width=35)
                with button_col_az:
                    st.link_button("Entrar com Microsoft", azure_login_url, use_container_width=True)
            else:
                st.warning("O login com Microsoft Azure não está configurado.")

        return False
    return True

def show_user_header():
    st.sidebar.write(f"Bem-vindo(a),")
    st.sidebar.write(f"**{get_user_display_name()}**")

def show_logout_button():
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







