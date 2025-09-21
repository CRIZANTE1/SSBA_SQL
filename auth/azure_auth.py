import streamlit as st
import msal
import logging

logger = logging.getLogger('abrangencia_app.azure_auth')

CLIENT_ID = st.secrets.get("azure", {}).get("client_id")
CLIENT_SECRET = st.secrets.get("azure", {}).get("client_secret")
TENANT_ID = st.secrets.get("azure", {}).get("tenant_id")
REDIRECT_URI = st.secrets.get("azure", {}).get("redirect_uri")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["User.Read"]

@st.cache_resource
def get_msal_app():
    if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID]):
        logger.error("Credenciais do Azure não configuradas nos secrets.")
        return None
    return msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )

def get_login_url():
    """Gera e retorna apenas a URL de login do Azure."""
    msal_app = get_msal_app()
    if not msal_app:
        return None
    return msal_app.get_authorization_request_url(
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )

def handle_redirect():
    msal_app = get_msal_app()
    if not msal_app:
        return False
    try:
        auth_code = st.query_params.get("code")
        if not auth_code:
            return False

        result = msal_app.acquire_token_by_authorization_code(
            code=auth_code,
            scopes=SCOPE,
            redirect_uri=REDIRECT_URI
        )

        if "error" in result:
            logger.error(f"Erro ao adquirir token do Azure: {result.get('error_description')}")
            st.error(f"Erro de autenticação: {result.get('error_description')}")
            return False

        id_token_claims = result.get('id_token_claims', {})
        user_email = id_token_claims.get('preferred_username')
        user_name = id_token_claims.get('name')

        if not user_email:
            logger.error("Não foi possível obter o e-mail do usuário do token do Azure.")
            st.error("Erro: E-mail não encontrado no perfil do Azure.")
            return False

        st.session_state.is_logged_in = True
        st.session_state.user_info_custom = {
            "email": user_email.lower().strip(),
            "name": user_name or user_email.split('@')[0]
        }
        
        st.query_params.clear()
        
        logger.info(f"Usuário '{user_email}' autenticado com sucesso via Azure AD.")
        return True

    except Exception as e:
        logger.error(f"Erro inesperado durante o handle_redirect do Azure: {e}")
        st.error("Ocorreu um erro inesperado durante a autenticação.")
        return False
