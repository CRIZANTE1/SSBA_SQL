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
# Garante que os módulos do projeto possam ser importados
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# --- Importações do Sistema ---
from auth.login_page import show_login_page, show_user_header, show_logout_button
from auth.auth_utils import authenticate_user, get_user_role, get_user_display_name, get_user_email
from front.dashboard import show_dashboard_page
from front.administracao import show_admin_page
from front.plano_de_acao import show_plano_acao_page
from gdrive.matrix_manager import get_matrix_manager 

def configurar_pagina():
    """Define as configurações globais da página Streamlit."""
    st.set_page_config(
        page_title="Abrangência | Gestão de Incidentes",
        page_icon="⚠️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def show_request_access_form():
    """Exibe o formulário para um novo usuário solicitar acesso ao sistema."""
    st.title("Solicitação de Acesso")
    st.write(f"Olá, **{get_user_display_name()}** ({get_user_email()}).")
    st.info("Seu e-mail ainda não foi autorizado a acessar o sistema. Por favor, preencha o formulário abaixo para solicitar o acesso a um administrador.")
    
    with st.form("request_access_form"):
        # Preenche o nome com o valor da conta Google como sugestão
        user_name = st.text_input("Seu nome completo", value=get_user_display_name())
        user_unit = st.text_input("Sua Unidade Operacional (UO)", placeholder="Ex: Unidade São Paulo")
        submitted = st.form_submit_button("Enviar Solicitação")

        if submitted:
            if not user_name or not user_unit:
                st.error("Por favor, preencha todos os campos.")
            else:
                matrix_manager = get_matrix_manager()
                if matrix_manager.add_access_request(get_user_email(), user_name, user_unit):
                    # Atualiza o status na sessão para mostrar a tela de "pendente"
                    st.session_state.access_status = "pending"
                    st.rerun()
                else:
                    st.error("Ocorreu um erro ao enviar sua solicitação. Tente novamente mais tarde.")

def main():
    """Função principal que orquestra a execução do aplicativo."""
    configurar_pagina()

    # Etapa 1: Garante que o usuário fez login com a conta Google.
    # Se não, exibe o botão de login e interrompe a execução.
    if not show_login_page():
        return

    # Etapa 2: Autentica o usuário no nosso sistema (verifica na planilha).
    # Esta função define st.session_state.access_status.
    is_authorized = authenticate_user()

    # Etapa 3: Lida com usuários não autorizados ou com acesso pendente.
    if not is_authorized:
        access_status = st.session_state.get('access_status')
        
        if access_status == "pending":
            st.title("Acesso Pendente")
            st.success("Sua solicitação de acesso foi recebida e está aguardando aprovação de um administrador.")
            st.info("Você será notificado quando seu acesso for liberado. Você pode fechar esta página.")
            show_logout_button()
        
        elif access_status == "unauthorized":
            show_request_access_form()
            show_logout_button()
        
        return # Impede a renderização do aplicativo principal

    # Etapa 4: Se o usuário está autorizado, renderiza o aplicativo principal.
    user_role = get_user_role()

    with st.sidebar:
        show_user_header()
        
        # Define os itens do menu com base no papel do usuário
        menu_items = {
            "Consultar Abrangência": {"icon": "card-checklist", "function": show_dashboard_page},
            "Plano de Ação": {"icon": "clipboard2-check-fill", "function": show_plano_acao_page},
        }
        if user_role == 'admin':
            menu_items["Administração"] = {"icon": "gear-fill", "function": show_admin_page}

        # Renderiza o menu
        selected_page = option_menu(
            menu_title="Menu Principal",
            options=list(menu_items.keys()),
            icons=[item["icon"] for item in menu_items.values()],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0 !important", "background-color": "transparent"},
                "icon": {"color": "inherit", "font-size": "15px"},
                "nav-link": {"font-size": "12px", "text-align": "left", "margin": "0px", "--hover-color": "#eee"},
                "nav-link-selected": {"background-color": "#0068C9"},
            }
        )
        show_logout_button()
    
    # Executa a função da página selecionada no menu
    page_to_run = menu_items.get(selected_page)
    if page_to_run:
        logger.info(f"Usuário '{get_user_email()}' navegando para a página: {selected_page}")
        page_to_run["function"]()

if __name__ == "__main__":
    main()
