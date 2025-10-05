# gdrive/config.py

import os
import json
import streamlit as st
import logging

logger = logging.getLogger('abrangencia_app.config')

# --- LÓGICA DE LEITURA DE CONFIGURAÇÕES ATUALIZADA ---

SPREADSHEET_ID = None
PUBLIC_IMAGES_FOLDER_ID = None
RESTRICTED_ATTACHMENTS_FOLDER_ID = None
ACTION_PLAN_EVIDENCE_FOLDER_ID = None
CENTRAL_LOG_SHEET_NAME = "log_auditoria"

# 1. Tenta ler do Streamlit Secrets (para a aplicação web)
is_streamlit_env = hasattr(st, 'secrets')
if is_streamlit_env:
    logger.info("Ambiente Streamlit detectado. Lendo configurações de st.secrets.")
    try:
        app_settings = st.secrets.get("app_settings", {})
        SPREADSHEET_ID = app_settings.get("spreadsheet_id")
        PUBLIC_IMAGES_FOLDER_ID = app_settings.get("public_images_folder_id")
        RESTRICTED_ATTACHMENTS_FOLDER_ID = app_settings.get("restricted_attachments_folder_id")
        ACTION_PLAN_EVIDENCE_FOLDER_ID = app_settings.get("action_plan_evidence_folder_id")
    except Exception as e:
        st.error(f"Erro ao ler as configurações de [app_settings] no secrets.toml: {e}")
        logger.critical(f"Erro inesperado ao ler st.secrets: {e}")

# 2. Se as variáveis ainda estiverem vazias, tenta ler das Variáveis de Ambiente (para GitHub Actions/local)
if not SPREADSHEET_ID:
    logger.info("Configurações não encontradas em st.secrets. Lendo de variáveis de ambiente.")
    SPREADSHEET_ID = os.getenv("MATRIX_SPREADSHEET_ID")
    PUBLIC_IMAGES_FOLDER_ID = os.getenv("PUBLIC_IMAGES_FOLDER_ID")
    RESTRICTED_ATTACHMENTS_FOLDER_ID = os.getenv("RESTRICTED_ATTACHMENTS_FOLDER_ID")
    ACTION_PLAN_EVIDENCE_FOLDER_ID = os.getenv("ACTION_PLAN_EVIDENCE_FOLDER_ID")

# 3. Validação final
# A validação de pastas pode ser específica para a app Streamlit, mas a planilha é essencial para ambos.
if not SPREADSHEET_ID:
    error_message = "Erro Crítico: O ID da planilha principal (MATRIX_SPREADSHEET_ID) não foi configurado nem em st.secrets nem como variável de ambiente."
    if is_streamlit_env:
        st.error(error_message)
    logger.critical(error_message)
    # Lançar um erro aqui pode ser uma boa ideia para parar a execução se o ID for essencial
    # raise ValueError(error_message)


# --- FUNÇÃO DE CREDENCIAIS (permanece a mesma) ---

def get_credentials_dict():
    """
    Retorna as credenciais do serviço do Google.
    """
    # 1. Tenta carregar do Streamlit Cloud Secrets
    if hasattr(st, 'runtime') and st.runtime.exists():
        try:
            creds = dict(st.secrets.connections.gsheets)
            if creds:
                logger.info("Credenciais carregadas com sucesso do Streamlit Cloud Secrets.")
                return creds
        except (AttributeError, KeyError):
            st.error("Erro: As credenciais [connections.gsheets] não foram encontradas nos Secrets do Streamlit.")
            logger.critical("Credenciais [connections.gsheets] não encontradas nos Secrets do Streamlit.")
            raise
    
    # 2. Tenta carregar de Variáveis de Ambiente (para GitHub Actions)
    gcp_credentials_json = os.getenv("GCP_SERVICE_ACCOUNT_CREDENTIALS")
    if gcp_credentials_json:
        logger.info("Credenciais encontradas na variável de ambiente (modo GitHub Actions).")
        try:
            return json.loads(gcp_credentials_json)
        except json.JSONDecodeError:
            logger.critical("A variável de ambiente GCP_SERVICE_ACCOUNT_CREDENTIALS não contém um JSON válido.")
            raise ValueError("A variável de ambiente GCP_SERVICE_ACCOUNT_CREDENTIALS não contém um JSON válido.")

    # 3. Tenta carregar de um arquivo local (para desenvolvimento)
    logger.info("Tentando carregar credenciais do arquivo local 'credentials.json' (modo de desenvolvimento).")
    credentials_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
    try:
        with open(credentials_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.critical("Arquivo 'credentials.json' não encontrado na raiz do projeto.")
        raise FileNotFoundError(
            "Credenciais não encontradas. Para rodar localmente, coloque um arquivo 'credentials.json' na pasta raiz do projeto."
        )
    except Exception as e:
        logger.critical(f"Erro ao carregar credenciais do arquivo local: {e}")
        raise
