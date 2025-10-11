import streamlit as st
import json 
import os  
from streamlit_lottie import st_lottie
from .auth_utils import get_user_display_name, get_user_email, is_user_logged_in
from .azure_auth import get_login_button
from operations.audit_logger import log_action

@st.cache_data
def load_lottie_file(filepath: str):
    """Carrega um arquivo Lottie JSON do caminho especificado."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Arquivo de animação não encontrado em: {filepath}")
        return None
    except json.JSONDecodeError:
        st.error(f"Erro ao ler o arquivo de animação. Verifique se é um JSON válido.")
        return None

def show_login_page():
    """
    Mostra uma página de login minimalista com os botões à esquerda e uma animação Lottie local à direita.
    """
    if not is_user_logged_in():
        st.markdown("""
        <style>
            iframe[title="st.login()"] {
                display: none;
            }
        </style>
        """, unsafe_allow_html=True)

        if 'google_login_triggered' not in st.session_state:
            st.session_state.google_login_triggered = False
        if st.session_state.get('google_login_triggered', False):
            st.login()
            st.session_state.google_login_triggered = False

        login_col, lottie_col = st.columns([1, 1.5])

        with login_col:
            st.title("Sistema de Gestão de Incidentes")
            st.markdown("---")
            st.subheader("Por favor, faça login para continuar")
            st.write("")

            # Verifica se o Google OAuth está configurado em [auth]
            google_configured = bool(st.secrets.get("auth", {}).get("client_id"))
            
            if google_configured:
                if st.button("Entrar com Google", width='stretch', type="primary"):
                
                st.markdown("<p style='text-align: center; margin: 10px 0;'>ou</p>", unsafe_allow_html=True)
            else:
                st.warning("⚠️ Login com Google não está disponível. Use o login com Microsoft Azure abaixo.")
            
            get_login_button()
        
        with lottie_col:

            current_dir = os.path.dirname(os.path.abspath(__file__))
            lottie_filepath = os.path.join(current_dir, '..', 'lotties', 'login_animation.json')
            
            lottie_animation = load_lottie_file(lottie_filepath)
            
            if lottie_animation:
                st_lottie(
                    lottie_animation,
                    speed=1,
                    loop=True,
                    quality="high",
                    height=600,
                    width=1000,
                    key="login_lottie"
                )

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
            
            if hasattr(st, 'user') and hasattr(st.user, 'email') and st.user.email:
                st.logout()
            else:
                st.rerun()








