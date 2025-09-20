
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

# --- Importações do Sistema ---
from auth.login_page import show_login_page, show_user_header, show_logout_button
from auth.auth_utils import authenticate_user, is_user_logged_in, get_user_role
from gdrive.matrix_manager import MatrixManager as GlobalMatrixManager
from front.dashboard import show_dashboard_page
from front.administracao import show_admin_page
from front.plano_de_acao import show_plano_acao_page
from operations.incident_manager import IncidentManager # Adicionado para consistência

def configurar_pagina():
    st.set_page_config(
        page_title="Abrangência | Gestão de Incidentes",
        page_icon="⚠️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def initialize_unit_managers():
    """
    Inicializa os managers específicos da unidade apenas quando uma unidade
    está selecionada.
    """
    unit_id = st.session_state.get('spreadsheet_id')
    
    # Se há uma unidade selecionada e os managers não foram inicializados para ela
    if unit_id and st.session_state.get('managers_unit_id') != unit_id:
        logger.info(f"Inicializando managers para a unidade: ...{unit_id[-6:]}")
        with st.spinner("Configurando ambiente da unidade..."):
            st.session_state.incident_manager = IncidentManager(unit_id)
            # Adicione outros managers de unidade aqui se necessário no futuro
            
        st.session_state.managers_unit_id = unit_id
        st.session_state.managers_initialized = True
        logger.info("Managers da unidade inicializados com sucesso.")
    
    # Se a visão mudou para Global, limpa os managers da unidade
    elif not unit_id and st.session_state.get('managers_initialized', False):
        logger.info("Visão Global ativada. Resetando managers da unidade.")
        keys_to_delete = ['incident_manager', 'managers_unit_id']
        for key in keys_to_delete:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.managers_initialized = False

def main():
    configurar_pagina()

    if not is_user_logged_in():
        show_login_page()
        st.stop()
    
    # --- AUTENTICAÇÃO CORRIGIDA ---
    # Esta função agora é a responsável por carregar a role e a unidade na sessão.
    if not authenticate_user():
        st.stop()

    # Inicializa os managers da unidade (se aplicável) após a autenticação
    initialize_unit_managers()

    with st.sidebar:
        show_user_header()
        user_role = get_user_role()

        # Lógica para admin trocar de unidade
        if user_role == 'admin':
            # O MatrixManager global é usado para listar as unidades
            matrix_manager = GlobalMatrixManager()
            
            all_units = matrix_manager.get_all_units()
            unit_options = [unit['nome_unidade'] for unit in all_units]
            unit_options.insert(0, 'Global')
            current_unit_name = st.session_state.get('unit_name', 'Global')
            
            try:
                default_index = unit_options.index(current_unit_name)
            except ValueError:
                default_index = 0

            selected_admin_unit = st.selectbox(
                "Visão da Unidade:", options=unit_options,
                index=default_index, key="admin_unit_selector"
            )

            if selected_admin_unit != current_unit_name:
                logger.info(f"Admin trocando de unidade: de '{current_unit_name}' para '{selected_admin_unit}'.")
                
                if selected_admin_unit == 'Global':
                    st.session_state.unit_name = 'Global'
                    st.session_state.spreadsheet_id = None
                    st.session_state.folder_id = None
                else:
                    unit_info = matrix_manager.get_unit_info(selected_admin_unit)
                    if unit_info:
                        st.session_state.unit_name = unit_info['nome_unidade']
                        st.session_state.spreadsheet_id = unit_info['spreadsheet_id']
                        st.session_state.folder_id = unit_info['folder_id']
                
                # Força a re-inicialização dos managers no próximo ciclo
                st.session_state.managers_unit_id = None
                st.rerun()

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

if __name__ == "__main__":
    main()
