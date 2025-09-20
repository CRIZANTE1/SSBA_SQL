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

def configurar_pagina():
    st.set_page_config(
        page_title="Abrangência | Gestão de Incidentes",
        page_icon="⚠️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def main():
    configurar_pagina()

    if not show_login_page():
        return
    
    # A função get_user_role já lida com a autenticação e permissões
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
            default_index=0,
            styles={
                "container": {"padding": "0 !important", "background-color": "transparent"},
                "icon": {"color": "inherit", "font-size": "15px"},
                "nav-link": {"font-size": "12px", "text-align": "left", "margin": "0px", "--hover-color": "rgba(255, 255, 255, 0.1)" if st.get_option("theme.base") == "dark" else "#f0f2f6"},
                "nav-link-selected": {"background-color": st.get_option("theme.primaryColor")},
            }
        )
        show_logout_button()
    
    # Executa a página selecionada
    page_to_run = menu_items.get(selected_page)
    if page_to_run:
        logger.info(f"Navegando para a página: {selected_page}")
        page_to_run["function"]()

if __name__ == "__main__":
    main()
