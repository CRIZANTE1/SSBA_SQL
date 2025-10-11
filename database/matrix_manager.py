import streamlit as st
import pandas as pd
import logging
from datetime import datetime
from database.supabase_operations import SupabaseOperations
from operations.audit_logger import log_action

logger = logging.getLogger('abrangencia_app.matrix_manager')

@st.cache_resource
def get_matrix_manager():
    return MatrixManager()


class MatrixManager:
    """Gerencia operações de usuários, unidades e solicitações de acesso"""
    
    def __init__(self):
        self.db = SupabaseOperations()
        if not self.db.engine:
            raise ConnectionError("Falha na conexão com o Supabase.")

    @st.cache_data(ttl=1800)  # 30 minutos - dados de usuários mudam pouco
    def get_utilities_users(_self) -> tuple[dict, list]:
        """Carrega usuários da tabela utilities (permite sem unidade)"""
        utilities_df = _self.db.get_table_data("utilities")
        
        if utilities_df.empty or 'nome' not in utilities_df.columns:
            return {}, []
        
        # Remove apenas linhas completamente vazias
        utilities_df = utilities_df.dropna(subset=['nome', 'email'])
        utilities_df = utilities_df[utilities_df['nome'].str.strip() != '']
        utilities_df = utilities_df[utilities_df['email'].str.strip() != '']
        
        # <<< MUDANÇA: Não filtra por unidade, aceita null/vazio >>>
        user_map = pd.Series(utilities_df.email.values, index=utilities_df.nome).to_dict()
        user_names = sorted(utilities_df['nome'].tolist())
        
        return user_map, user_names

    def get_all_users_df(self) -> pd.DataFrame:
        """Retorna todos os usuários"""
        return self.db.get_table_data("usuarios")

    def get_user_info(self, email: str) -> dict | None:
        """Busca informações de um usuário pelo email"""
        if not email:
            return None
        
        email_clean = str(email).lower().strip()
        
        # <<< MUDANÇA: Usa método sem RLS para autenticação >>>
        users_df = self.db.get_by_field_no_rls("usuarios", "email", email_clean)
        
        return users_df.iloc[0].to_dict() if not users_df.empty else None

    def add_user(self, user_data: list) -> bool:
        """Adiciona um novo usuário"""
        logger.info(f"Adicionando usuário: {user_data[0]}")
        
        user_dict = {
            "email": user_data[0],
            "nome": user_data[1],
            "role": user_data[2],
            "unidade_associada": user_data[3]
        }
        
        result = self.db.insert_row("usuarios", user_dict)
        if result:
            log_action("ADD_USER", {"email": user_data[0], "role": user_data[2]})
            st.cache_data.clear()
        return result is not None

    def update_user(self, email: str, updates: dict) -> bool:
        """Atualiza um usuário existente"""
        users_df = self.db.get_by_field("usuarios", "email", email)
        
        if users_df.empty:
            logger.warning(f"Usuário {email} não encontrado")
            return False
        
        user_id = users_df.iloc[0]['id']
        success = self.db.update_row("usuarios", user_id, updates)
        
        if success:
            log_action("UPDATE_USER", {"email": email, "updates": updates})
            st.cache_data.clear()
        
        return success

    def remove_user(self, user_email: str) -> bool:
        """Remove um usuário"""
        users_df = self.db.get_by_field("usuarios", "email", user_email.strip())
        
        if users_df.empty:
            return False
        
        user_id = users_df.iloc[0]['id']
        success = self.db.delete_row("usuarios", user_id)
        
        if success:
            log_action("REMOVE_USER", {"email": user_email})
            st.cache_data.clear()
        
        return success

    def get_all_units(self) -> list[str]:
        """Retorna lista de unidades operacionais"""
        users_df = self.get_all_users_df()
        
        if users_df.empty or 'unidade_associada' not in users_df.columns:
            return []
        
        units = users_df['unidade_associada'].dropna().unique()
        return sorted([str(u) for u in units if u and str(u).strip() and str(u) != '*'])

    def add_access_request(self, email: str, name: str, unit: str) -> bool:
        """Adiciona uma solicitação de acesso"""
        request_data = {
            "email": email,
            "nome": name,
            "unidade_solicitada": unit,
            "data_solicitacao": datetime.now().isoformat(),
            "status": "pendente"
        }
        
        return self.db.insert_row("solicitacoes_acesso", request_data) is not None

    def get_pending_access_requests(self) -> pd.DataFrame:
        """Retorna solicitações pendentes"""
        # <<< MUDANÇA: Usa método sem RLS para verificação de solicitações >>>
        return self.db.get_by_field_no_rls("solicitacoes_acesso", "status", "pendente")

    def approve_access_request(self, email: str, role: str) -> bool:
        """Aprova uma solicitação de acesso"""
        requests_df = self.get_pending_access_requests()
        request_info = requests_df[requests_df['email'].str.lower() == email.lower()]
        
        if request_info.empty:
            return False
        
        user_data = request_info.iloc[0]
        new_user = [user_data['email'], user_data['nome'], role, user_data['unidade_solicitada']]
        
        if not self.add_user(new_user):
            return False
        
        request_id = user_data['id']
        success = self.db.update_row("solicitacoes_acesso", request_id, {"status": "aprovado"})
        
        if success:
            log_action("APPROVE_ACCESS_REQUEST", {"email": email, "assigned_role": role})
            st.cache_data.clear()
        
        return success

    def reject_access_request(self, email: str) -> bool:
        """Rejeita uma solicitação de acesso"""
        requests_df = self.get_pending_access_requests()
        request_info = requests_df[requests_df['email'].str.lower() == email.lower()]
        
        if request_info.empty:
            return False
        
        request_id = request_info.iloc[0]['id']
        success = self.db.update_row("solicitacoes_acesso", request_id, {"status": "rejeitado"})
        
        if success:
            log_action("REJECT_ACCESS_REQUEST", {"email": email})
            st.cache_data.clear()
        
        return success

    def get_audit_logs(self) -> pd.DataFrame:
        """Retorna os logs de auditoria"""
        return self.db.get_table_data("log_auditoria")