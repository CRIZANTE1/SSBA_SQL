# gdrive/config.py
import os
import streamlit as st
import logging

logger = logging.getLogger('abrangencia_app.gdrive.config')

# Deprecated Google Drive/Sheets configuration adapter.
# During the migration to Supabase these values are kept for backward compatibility,
# but no longer raise errors if not configured.
SPREADSHEET_ID = os.getenv("MATRIX_SPREADSHEET_ID", "") or (st.secrets.get("app_settings", {}).get("spreadsheet_id") if hasattr(st, "secrets") else "")
PUBLIC_IMAGES_FOLDER_ID = os.getenv("PUBLIC_IMAGES_FOLDER_ID", "") or (st.secrets.get("app_settings", {}).get("public_images_folder_id") if hasattr(st, "secrets") else "")
RESTRICTED_ATTACHMENTS_FOLDER_ID = os.getenv("RESTRICTED_ATTACHMENTS_FOLDER_ID", "") or (st.secrets.get("app_settings", {}).get("restricted_attachments_folder_id") if hasattr(st, "secrets") else "")
ACTION_PLAN_EVIDENCE_FOLDER_ID = os.getenv("ACTION_PLAN_EVIDENCE_FOLDER_ID", "") or (st.secrets.get("app_settings", {}).get("action_plan_evidence_folder_id") if hasattr(st, "secrets") else "")
CENTRAL_LOG_SHEET_NAME = "log_auditoria"

def get_deprecated_google_credentials():
    """Retorna None — esta função existe apenas para compatibilidade durante a migração."""
    logger.warning("get_deprecated_google_credentials() called — Google credentials are deprecated in this project.")
    return None
# Tenta ler do Streamlit Secrets (quando rodando na web)
