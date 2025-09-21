# auth/login_page.py

import streamlit as st
from .auth_utils import get_user_display_name, get_user_email, is_user_logged_in
from .azure_auth import get_login_url
from operations.audit_logger import log_action

# --- URLs dos Logos ---
GOOGLE_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Google_%22G%22_logo.svg/2048px-Google_%22G%22_logo.svg.png"
MICROSOFT_LOGO_URL = "https://cdn-icons-png.flaticon.com/512/732/732221.png"

def show_login_page():
    """
    Mostra a página de login com um design minimalista usando logos e botões customizados.
    """
    if not is_user_logged_in():
        st.title("Sistema de Gestão de Incidentes")
        st.write("") 

        # --- CSS Customizado para os botões ---
        st.markdown(f"""
        <style>
            /* Esconde o botão IFrame do Google Login que aparece no topo */
            iframe[title="st.login()"] {{
                display: none;
            }}
            /* Estilo base para os containers de botão */
            .login-container {{
                padding: 12px;
                border: 1px solid #dcdcdc;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                text-decoration: none;
                color: #4f4f4f !important;
                margin-bottom: 12px;
                cursor: pointer;
                transition: background-color 0.2s, box-shadow 0.2s;
            }}
            .login-container:hover {{
                background-color: #f5f5f5;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .login-container img {{
                width: 25px;
                margin-right: 12px;
            }}
            .login-container span {{
                font-weight: 500;
                font-size: 16px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            }}
            .login-container a {{
                text-decoration: none;
                display: contents;
            }}
        </style>
        """, unsafe_allow_html=True)
        
        # Centraliza a área de login
        _, col, _ = st.columns([1, 1.5, 1])

        with col:
            st.markdown("<h3 style='text-align: center; margin-bottom: 25px;'>Entrar no Sistema</h3>", unsafe_allow_html=True)

            # --- Botão Google (Truque com session_state) ---
            # Este botão visível é apenas um gatilho
            if st.button("Entrar com Google", key="google_login_button", use_container_width=True):
                st.session_state['google_login_triggered'] = True
            
            # Se o gatilho foi acionado, chama st.login()
            if st.session_state.get('google_login_triggered', False):
                st.login()
                # Reseta o gatilho para evitar loop
                st.session_state['google_login_triggered'] = False

            st.markdown("<p style='text-align: center; margin: 10px 0;'>ou</p>", unsafe_allow_html=True)
            
            # --- Botão Azure (com Markdown) ---
            azure_login_url = get_login_url()
            if azure_login_url:
                st.markdown(
                    f'''
                    <a href="{azure_login_url}" target="_self" class="login-container">
                        <img src="{MICROSOFT_LOGO_URL}">
                        <span>Entrar com Microsoft</span>
                    </a>
                    ''',
                    unsafe_allow_html=True
                )
            else:
                st.warning("O login com Microsoft Azure não está configurado.")

            # CSS para customizar o botão do Google
            st.markdown(f"""
            <style>
                button[data-testid="stButton"][key="google_login_button"] > div {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                button[data-testid="stButton"][key="google_login_button"]::before {{
                    content: "";
                    display: inline-block;
                    width: 25px;
                    height: 25px;
                    background-image: url({GOOGLE_LOGO_URL});
                    background-size: contain;
                    background-repeat: no-repeat;
                    margin-right: 12px;
                }}
                /* Esconde o texto original do botão */
                button[data-testid="stButton"][key="google_login_button"] p {{
                    font-weight: 500 !important;
                    font-size: 16px !important;
                }}
            </style>
            """, unsafe_allow_html=True)

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





