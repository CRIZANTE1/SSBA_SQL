import streamlit as st
from datetime import datetime
import json
from database.supabase_operations import SupabaseOperations

def log_action(action: str, details: dict):
    """Registra uma ação no log de auditoria"""
    try:
        user_email = st.session_state.get('user_info', {}).get('email', 'system')
        user_role = st.session_state.get('role', 'N/A')
        target_unit = st.session_state.get('unit_name', 'SingleTenant')
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "user_email": user_email,
            "user_role": user_role,
            "action": action,
            "details": json.dumps(details, ensure_ascii=False),
            "target_unit": target_unit
        }
        
        db = SupabaseOperations()
        if user_email == 'system':
            db.insert_row_without_rls("log_auditoria", log_data)
        else:
            db.insert_row("log_auditoria", log_data)
        
        print(f"LOG SUCCESS: Action '{action}' by '{user_email}' logged.")
    except Exception as e:
        print(f"LOG FAILED: Could not log action '{action}'. Reason: {e}")
