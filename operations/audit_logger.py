import streamlit as st
from datetime import datetime
import json
from operations.sheet import SheetOperations
from gdrive.config import SPREADSHEET_ID, CENTRAL_LOG_SHEET_NAME

def log_action(action: str, details: dict):
    """
    Registra uma ação do usuário na aba de log central da Planilha Principal.
    """
    try:
        user_email = st.session_state.get('user_info', {}).get('email', 'system')
        user_role = st.session_state.get('role', 'N/A')
        target_unit = st.session_state.get('unit_name', 'SingleTenant') # Ajustado para single-tenant
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        details_str = json.dumps(details, ensure_ascii=False)
        log_row = [timestamp, user_email, user_role, action, details_str, target_unit]


        main_sheet_ops = SheetOperations()
        main_sheet_ops.adc_linha_simples(CENTRAL_LOG_SHEET_NAME, log_row)
        
        print(f"LOG SUCCESS: Action '{action}' by '{user_email}' logged.")

    except Exception as e:
        print(f"LOG FAILED: Could not log action '{action}'. Reason: {e}")
