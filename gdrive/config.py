# gdrive/config.py

import os
import json
import streamlit as st
import logging
import sys # <--- CORREÇÃO AQUI: Adicionar a importação do módulo sys

logger = logging.getLogger('abrangencia_app.config')

# --- LÓGICA DE LEITURA DE CONFIGURAÇÕES ATUALIZADA ---

SPREADSHEET_ID = None
# Como você só usa uma planilha, as pastas não são críticas para o script de notificação,
# mas mantemos a estrutura para a aplicação web.
PUBLIC_IMAGES_FOLDER_ID = None
RESTRICTED_ATTACHMENTS_FOLDER_ID = None
ACTION_PLAN_EVIDENCE_FOLDER_ID = None 
CENTRAL_LOG_SHEET_NAME = "log_auditoria" 

# Tenta ler do Streamlit Secrets (quando rodando na web)
try:
    if hasattr(st, 'secrets') and 'app_settings' in st.secrets:
        logger.info("Lendo configurações de st.secrets (ambiente Streamlit).")
        app_settings = st.secrets.app_settings
        SPREADSHEET_ID = app_settings.get("spreadsheet_id")
        PUBLIC_IMAGES_FOLDER_ID = app_settings.get("public_images_folder_id")
        RESTRICTED_ATTACHMENTS_FOLDER_ID = app_settings.get("restricted_attachments_folder_id")
        ACTION_PLAN_EVIDENCE_FOLDER_ID = app_settings.get("action_plan_evidence_folder_id")
except Exception as e:
    # Em um ambiente não-Streamlit, isso pode falhar, o que é esperado.
    logger.warning(f"Não foi possível ler de st.secrets: {e}. Tentando variáveis de ambiente.")

# Se SPREADSHEET_ID não foi encontrado, tenta ler das variáveis de ambiente
# (quando rodando no GitHub Actions ou localmente com .env)
if not SPREADSHEET_ID:
    logger.info("Lendo SPREADSHEET_ID de variável de ambiente (ambiente de script).")
    SPREADSHEET_ID = os.getenv("MATRIX_SPREADSHEET_ID")

# Validação final: SPREADSHEET_ID é absolutamente necessário
if not SPREADSHEET_ID:
    error_message = "Erro Crítico: ID da planilha principal não encontrado. Configure-o em st.secrets [app_settings].spreadsheet_id ou na variável de ambiente MATRIX_SPREADSHEET_ID."
    logger.critical(error_message)
    # Se estiver no Streamlit, mostra o erro na tela
    if 'streamlit' in sys.modules:
        st.error(error_message)
    # Para o script, é melhor parar a execução com um erro claro
    raise ValueError(error_message)

# --- FUNÇÃO DE CREDENCIAIS (permanece a mesma, já é compatível) ---

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
