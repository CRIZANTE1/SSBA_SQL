import streamlit as st
import sys
import os
import logging
from streamlit_option_menu import option_menu

# --- Configuração do Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('abrangencia_app')

# --- Configuração do Caminho (Path) ---
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# --- Importações do Sistema Single-Tenant ---
from auth.login_page import show_login_page, show_user_header, show_logout_button
from auth.auth_utils import is_user_logged_in, get_user_role
from front.dashboard import show_dashboard_page
from front.administracao import show_admin_page
from front.plano_de_acao import show_plano_acao_page
from gdrive.matrix_manager import get_matrix_manager 

def configurar_pagina():
    st.set_page_config(
        page_title="Abrangência | Gestão de Incidentes",
        page_icon="⚠️",
        layout="wide",
        initial_sidebar_state="expanded"
    )




def show_request_access_form():
    """Exibe o formulário para um novo usuário solicitar acesso."""
    st.title("Solicitação de Acesso")
    st.write(f"Olá, **{get_user_display_name()}** ({get_user_email()}).")
    st.info("Seu e-mail ainda não foi autorizado a acessar o sistema. Por favor, preencha o formulário abaixo para solicitar o acesso.")
    
    with st.form("request_access_form"):
        user_name = st.text_input("Seu nome completo", value=get_user_display_name())
        user_unit = st.text_input("Sua Unidade Operacional (UO)", placeholder="Ex: Unidade São Paulo")
        submitted = st.form_submit_button("Enviar Solicitação")

        if submitted:
            if not user_name or not user_unit:
                st.error("Por favor, preencha todos os campos.")
            else:
                matrix_manager = get_matrix_manager()
                if matrix_manager.add_access_request(get_user_email(), user_name, user_unit):
                    st.session_state.access_status = "pending"
                    st.rerun()
                else:
                    st.error("Ocorreu um erro ao enviar sua solicitação. Tente novamente mais tarde.")

def main():
    configurar_pagina()

    if not show_login_page():
        return

    # A autenticação agora define um 'access_status' na sessão
    if not authenticate_user():
        access_status = st.session_state.get('access_status')
        if access_status == "pending":
            st.title("Acesso Pendente")
            st.success("Sua solicitação de acesso foi recebida e está aguardando aprovação de um administrador.")
            st.info("Você será notificado quando seu acesso for liberado.")
            show_logout_button()
        elif access_status == "unauthorized":
            show_request_access_form()
            show_logout_button()
        return # Impede a renderização do resto da página

    # Se chegou aqui, o usuário está autorizado. O código abaixo permanece o mesmo.
    user_role = get_user_role()

    with st.sidebar:
        show_user_header()
        
        menu_items = {
            "Consultar Abrangência": {"icon": "card-checklist", "function": show_dashboard_page},
            "Plano de Ação": {"icon": "clipboard2-check-fill", "function": show_plano_acao_page},
        }
        if user_role == 'admin':
            menu_items["Administração"] = {"icon": "gear-fill", "function": show_admin_page}

        selected_page = option_menu(
            menu_title="Menu Principal",
            options=list(menu_items.keys()),
            icons=[item["icon"] for item in menu_items.values()],
            menu_icon="cast",
            default_index=0
        )
        show_logout_button()
    
    page_to_run = menu_items.get(selected_page)
    if page_to_run:
        logger.info(f"Navegando para a página: {selected_page}")
        page_to_run["function"]()
