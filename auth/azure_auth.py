import streamlit as st
import msal
import logging

logger = logging.getLogger('abrangencia_app.azure_auth')

# --- Configuração ---
CLIENT_ID = st.secrets.get("azure", {}).get("client_id")
CLIENT_SECRET = st.secrets.get("azure", {}).get("client_secret")
TENANT_ID = st.secrets.get("azure", {}).get("tenant_id")
REDIRECT_URI = st.secrets.get("azure", {}).get("redirect_uri")

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["User.Read"] # Permissões básicas para ler o perfil do usuário

@st.cache_resource
def get_msal_app():
    """Inicializa e retorna a aplicação MSAL Confidential Client."""
    if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID]):
        logger.error("Credenciais do Azure não configuradas nos secrets.")
        return None
    return msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )

def get_login_button():
    """Gera a URL de login do Azure e retorna um st.link_button."""
    msal_app = get_msal_app()
    if not msal_app:
        st.error("O login com Azure não está configurado corretamente.")
        return

    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )
    st.link_button("Fazer Login com Microsoft Azure", auth_url, use_container_width=True)

def handle_redirect():
    """
    Processa o redirecionamento de volta do Azure. Se o login for bem-sucedido,
    armazena as informações do usuário no session_state e retorna True.
    """
    msal_app = get_msal_app()
    if not msal_app:
        return False
        
    try:
        # Pega o código de autorização da URL
        auth_code = st.query_params.get("code")
        if not auth_code:
            return False

        # Troca o código por um token
        result = msal_app.acquire_token_by_authorization_code(
            code=auth_code,
            scopes=SCOPE,
            redirect_uri=REDIRECT_URI
        )

        if "error" in result:
            logger.error(f"Erro ao adquirir token do Azure: {result.get('error_description')}")
            st.error(f"Erro de autenticação: {result.get('error_description')}")
            return False

        # Decodifica o ID token para obter as informações do usuário
        id_token_claims = result.get('id_token_claims', {})
        user_email = id_token_claims.get('preferred_username')
        user_name = id_token_claims.get('name')

        if not user_email:
            logger.error("Não foi possível obter o e-mail do usuário do token do Azure.")
            st.error("Erro: E-mail não encontrado no perfil do Azure.")
            return False

        # Salva as informações do usuário na sessão (nosso próprio sistema de login)
        st.session_state.is_logged_in = True
        st.session_state.user_info_custom = {
            "email": user_email.lower().strip(),
            "name": user_name or user_email.split('@')[0]
        }
        
        # Limpa os parâmetros da URL para evitar loops de login
        st.query_params.clear()
        
        logger.info(f"Usuário '{user_email}' autenticado com sucesso via Azure AD.")
        return True

    except Exception as e:
        logger.error(f"Erro inesperado durante o handle_redirect do Azure: {e}")
        st.error("Ocorreu um erro inesperado durante a autenticação.")
        return False
