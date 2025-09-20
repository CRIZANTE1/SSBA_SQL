
import os
import json
import streamlit as st
import logging

logger = logging.getLogger('abrangencia_app.config')

# --- LEITURA DAS CONFIGURAÇÕES A PARTIR DOS SECRETS ---

SPREADSHEET_ID = None
CENTRAL_ALERTS_FOLDER_ID = None
CENTRAL_LOG_SHEET_NAME = "log_auditoria" 

try:
    if hasattr(st, 'secrets') and 'app_settings' in st.secrets:
        SPREADSHEET_ID = st.secrets.app_settings.get("spreadsheet_id")
        CENTRAL_ALERTS_FOLDER_ID = st.secrets.app_settings.get("central_alerts_folder_id")
        
        if not SPREADSHEET_ID or not CENTRAL_ALERTS_FOLDER_ID:
            st.error("Erro Crítico: As configurações 'spreadsheet_id' e/ou 'central_alerts_folder_id' estão faltando em [app_settings] no seu arquivo secrets.toml.")
            logger.critical("Configurações essenciais (spreadsheet_id, central_alerts_folder_id) ausentes nos secrets.")
    else:
        st.error("Erro Crítico: A seção [app_settings] não foi encontrada no seu arquivo secrets.toml.")
        logger.critical("Seção [app_settings] não encontrada nos secrets.")

except Exception as e:
    st.error(f"Erro ao ler as configurações do secrets.toml: {e}")
    logger.critical(f"Erro inesperado ao ler secrets: {e}")

# --- FUNÇÃO DE CREDENCIAIS ---

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
