
import streamlit as st
from .auth_utils import get_user_display_name, get_user_email, is_user_logged_in
from .azure_auth import get_login_url
from operations.audit_logger import log_action

# --- URLs dos Logos ---
GOOGLE_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Google_%22G%22_logo.svg/2048px-Google_%22G%22_logo.svg.png"
MICROSOFT_LOGO_URL = "https://cdn-icons-png.flaticon.com/512/732/732221.png"

def show_login_page():
    """
    Mostra a página de login com um design minimalista usando logos.
    """
    if not is_user_logged_in():
        st.title("Sistema de Gestão de Incidentes")
        st.write("") 

        # --- CSS Customizado para os botões ---
        st.markdown(f"""
        <style>
            /* Esconde o botão IFrame do Google Login */
            iframe[title="st.login()"] {{
                display: none;
            }}
            /* Estilo base para os containers de botão */
            .login-container {{
                padding: 10px 15px;
                border: 1px solid #dcdcdc;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                text-decoration: none;
                color: #333 !important;
                margin-bottom: 10px;
                transition: background-color 0.2s, box-shadow 0.2s;
            }}
            .login-container:hover {{
                background-color: #f5f5f5;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .login-container img {{
                width: 28px;
                margin-right: 15px;
            }}
            .login-container span {{
                font-weight: 500;
                font-size: 16px;
            }}
        </style>
        """, unsafe_allow_html=True)
        
        # Centraliza a área de login
        _, col, _ = st.columns([1, 1.5, 1])

        with col:
            st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>Entrar no Sistema</h3>", unsafe_allow_html=True)

            # --- Botão Google ---
            # O st.login() não tem URL, então usamos um truque: um botão que o chama.
            # E um container para estilizar, mas que não é clicável.
            if st.button("Fazer Login com Google", key="google_login_main_button", use_container_width=True):
                 st.login()

            st.markdown("<p style='text-align: center; margin: 10px 0;'>ou</p>", unsafe_allow_html=True)
            
            # --- Botão Azure ---
            azure_login_url = get_login_url()
            if azure_login_url:
                # O st.link_button funciona perfeitamente para o Azure
                st.link_button("Fazer Login com Microsoft", azure_login_url, use_container_width=True)
            else:
                st.warning("O login com Microsoft Azure não está configurado.")

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
                'user_info', 'role', 'unit_name', 'access_status', 'login_logged'
            ]
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            if hasattr(st, 'user') and st.user.is_logged_in:
                st.logout()
            else:
                st.rerun()




