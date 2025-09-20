import streamlit as st
import sys
import os
import logging

# --- Configuração do Logging e Path ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('abrangencia_app')
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# --- Importações do Sistema ---
from auth.login_page import show_login_page, show_user_header, show_logout_button
from auth.auth_utils import authenticate_user, get_user_role, get_user_display_name, get_user_email
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
    """Função principal que atua como roteador da aplicação."""
    configurar_pagina()

    # --- Bloco de Autenticação ---
    if not show_login_page():
        return

    is_authorized = authenticate_user()

    # <<< MUDANÇA IMPORTANTE: O botão de logout agora fica na sidebar para todas as telas de "não autorizado" >>>
    if not is_authorized:
        access_status = st.session_state.get('access_status')
        if access_status == "pending":
            st.title("Acesso Pendente")
            st.success("Sua solicitação de acesso foi recebida e está aguardando aprovação.")
        elif access_status == "unauthorized":
            show_request_access_form()
        
        # Coloca o botão de logout na sidebar, que ainda está visível
        with st.sidebar:
            show_logout_button()
        return

    # --- Definição das Páginas ---
    user_role = get_user_role()

    pages = {
        "Menu Principal": [
            st.Page("pages/dashboard_page.py", title="Consultar Abrangência", icon="🗂️", default=True),
            st.Page("pages/plano_acao_page.py", title="Plano de Ação", icon="📋"),
        ]
    }

    if user_role == 'admin':
        pages["Configurações"] = [
            st.Page("pages/admin_page.py", title="Administração", icon="⚙️")
        ]

    # --- Criação da Navegação no TOPO da página ---
    pg = st.navigation(pages, position="top")
    
    # --- Conteúdo da Sidebar (agora separada da navegação) ---
    with st.sidebar:
        show_user_header()
        st.divider()
        # Adicione aqui outros filtros ou informações que você queira que sejam persistentes
        st.info("Filtros globais ou outras informações podem ser adicionados aqui.")
        st.divider()
        show_logout_button()

    # --- Execução da Página Selecionada ---
    st.header(pg.title)
    logger.info(f"Usuário '{get_user_email()}' executando a página: {pg.title}")
    pg.run()


if __name__ == "__main__":
    main()
